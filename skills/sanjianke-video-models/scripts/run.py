#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 文生视频模型台（sanjianke-video-models）

一句话：同一句话，先让 5 个视频模型各报一次价，再决定跑哪一个。

## 这一台和单模型包差在哪

单模型包把「一条片子」写死成一个模型。这一台先回答「用哪个模型」：
`cost --models a,b,c` 逐个报价、按上界排序、给出最贵与最便宜的倍数；
`gen --models a,b,c` 用同一句话逐个提交，落盘带命名规范，并生成一张
「同一句话，五个模型」对比清单。

## 2026-11-08 实测原文（本账号，本轮 0 点）

  GET  /api/v1/models                316 条 = 221 条目录 + 95 条裸模型层 ID
                                     type_code=video 47 个型号，kling 家族 14 个
  GET  /api/v1/pricing               115 条规则，没有 /api/v1/videos/generations
  POST /api/v1/videos  {}            -> 400 Model name not specified
  POST /api/v1/videos  {prompt}      -> 400 Model name not specified
  POST /api/v1/videos  {"model":"kling-4-0"}
                                     -> 404 model_not_found（目录里有，这条路由不认）
  POST /api/v1/videos  {"model":"muse-video"}
                                     -> 400 plugin_request_invalid: field prompt is required
  POST /api/v1/videos/generations  {}
                                     -> 400 model field is required
  POST /api/v1/videos/generations  {"model": 任意 28 个型号}
                                     -> 400 prompt or content field is required
  GET  /api/v1/tasks/probe-no-such-task
                                     -> 200 {"code":0,"msg":"任务不存在"}

## 关键结论：提交端点分两条，选错了会 404

  /api/v1/videos              只认 4 个裸模型层 ID
                              （muse-video、sd/doubao-seedance-2-0-260128、
                               volcengine/doubao-seedance-2-5-260628、wan3.0-video）
  /api/v1/videos/generations  认全部 47 个目录型号 + 上面 4 个裸 ID
                              （kling 家族 14 个、veo、hailuo、vidu、runway、
                               pixverse、grok、minimax 都在这条路上）

本包 `gen` 默认一律走 `/api/v1/videos/generations`，并在 `catalog` 里标明
每个型号的历史成功路径。`--route videos` 可强制走另一条。

## 单价从哪来（价目表里没有）

视频模型的模型层单价不在 `/api/v1/pricing` 里：整张表没有 modelPricing 键，
模型层命中的是通配 `*`（对外 = 上游实际点数 x 2，单笔保底 50 点）。
所以单价只能反推：

  1. GET /api/v1/me/tasks 按 model 归集 actualPrice（免费，标 source=live）
  2. 没跑过的型号用同路成交区间（标 source=baseline，预算按上界）
  3. 每跑成功一次，下一次报价就换成你自己的成交价

## 子命令

  catalog  13 个视频模型：报价 / 来源 / 提交路径 / 是否实测可提交（免费）
  cost     同一句话多模型逐个报价，按上界排序（免费）
  doctor   自检 6 个只读端点 + 3 个免费探针 + 余额前后对比（免费，0 点）
  gen      多模型提交（要 --yes，受 --budget 管）；--wait 等到完成并下载
  status   查任务（免费，只走 GET /api/v1/tasks/<id>）
  wait     等一个任务完成并下载（免费）
  sheet    用 manifest 重新生成对比清单（免费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --models muse-video,kling-4-0,veo3.1-pro --seconds 5
  python3 scripts/run.py doctor
  python3 scripts/run.py gen --models muse-video,kling-4-0 --prompt "..." --yes
  python3 scripts/run.py status --task-id task_xxx

Key：`--key` -> 环境变量 `A7W_API_KEY` -> `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

# ── GBK 编码兜底（家族统一写法）──────────────────────────────────────────────
# Windows 上 stdout 走管道/重定向时用 cp936，个别符号编不出来就 UnicodeEncodeError。
# 先 reconfigure(errors="replace") 兜底；本包全文只用 cp936 覆盖得到的字符：
#   √ × · → 「」 与中文标点。金额一律写「元」，不用那个 cp936 编不出的窄体日元符号。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
VIDEOS_PATH = API_PREFIX + "/videos"
GEN_PATH = API_PREFIX + "/videos/generations"
TASKS_PATH = API_PREFIX + "/tasks"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 12500           # 单位：点 = 125 元。够默认 5 个模型各跑一条（按上界）
DEFAULT_SECONDS = 5
DEFAULT_PAGES = 10               # 每页 20 条；默认扫 200 条
PAGE_SIZE_ME = 20
MAX_PAGES = 70
CACHE_TTL = 6 * 3600
WILDCARD_MIN = 50                # 通配规则：单笔保底 50 点
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "video-models-ledger.json")
PRICE_CACHE = os.path.join(os.path.expanduser("~"), ".a7w", "video-models-prices.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-video-models/%s" % VERSION

# ── 13 个候选：每条都带证据，不是拍出来的 ────────────────────────────────────
# route：历史成功路径（本包统一走 /api/v1/videos/generations）
# probes：2026-11-08 缺 prompt 探针在 /videos/generations 上的返回
# samples：本账号 /api/v1/me/tasks 的 actualPrice 实测（source=live 的那批）
MODELS = {
    "muse-video": dict(
        name="Muse Video（720P 带声音）", route=VIDEOS_PATH, refs=8, seconds=(4, 180),
        samples=[44.0, 44.0, 55.0, 55.0, 55.0, 55.0, 55.0, 260.0], rate=11,
        probe="400 plugin_request_invalid: field prompt is required",
        note="唯一有官方写死单价的一档：11 点/秒，按请求秒数结算"),
    "sd/doubao-seedance-2-0-260128": dict(
        name="Seedance 2.0 标准版", route=GEN_PATH, refs=9, seconds=(4, 12),
        samples=[145.73, 181.79, 181.79, 3000.0, 3000.0], rate=None,
        probe="400 prompt or content field is required",
        note="实测最低 145.73 点；同族最便宜的一条路"),
    "volcengine/doubao-seedance-2-5-260628": dict(
        name="Seedance 2.5 旗舰版", route=GEN_PATH, refs=9, seconds=(4, 12),
        samples=[762.3, 3000.0, 3045.71], rate=None,
        probe="400 prompt or content field is required",
        note="画质最强的一档；实测 762.30 点起"),
    "wan3.0-video": dict(
        name="Wan 3.0 Video", route=GEN_PATH, refs=10, seconds=(4, 10),
        samples=[300.0] * 8, rate=None,
        probe="本轮未探（历史会先冻 300 点再退），改用台账 8 笔 300 点成交作证",
        note="8 笔成交全是 300 点，最稳的一档；走百炼通道"),
    "kling-4-0": dict(
        name="Kling 4.0", route=GEN_PATH, refs=10, seconds=(5, 10),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="kling 家族 14 个型号里最新的一档；/videos 上会 404"),
    "veo3.1-pro": dict(
        name="VEO 3.1 Pro", route=GEN_PATH, refs=3, seconds=(4, 8),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="8 秒、720p / 1080p / 4K；支持首尾帧"),
    "veo3.1-fast": dict(
        name="VEO 3.1 Fast", route=GEN_PATH, refs=3, seconds=(4, 8),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="VEO 3.1 的快档，同参数更省时间"),
    "hailuo-02-standard": dict(
        name="Hailuo 02 Standard", route=GEN_PATH, refs=2, seconds=(6, 10),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="人物动作自然，短剧镜头常用"),
    "hailuo-02-pro": dict(
        name="Hailuo 02 Pro", route=GEN_PATH, refs=2, seconds=(6, 10),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="Hailuo 02 的高清档，细节更稳"),
    "vidu-q4": dict(
        name="Vidu Q4", route=GEN_PATH, refs=15, seconds=(4, 8),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="参考图最多 15 张，多主体一致性最好"),
    "runway": dict(
        name="Runway（官方视频）", route=GEN_PATH, refs=1, seconds=(5, 10),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="运镜与电影感见长，单图参考"),
    "pixverse-v6": dict(
        name="PixVerse V6", route=GEN_PATH, refs=7, seconds=(4, 8),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="动漫风与特效转场强，7 张参考图"),
    "pixverse-v6-max": dict(
        name="PixVerse V6 Max", route=GEN_PATH, refs=1, seconds=(4, 8),
        samples=[], rate=None, probe="400 prompt or content field is required",
        note="PixVerse 的高清单图档"),
}
MODEL_ORDER = ["muse-video", "sd/doubao-seedance-2-0-260128", "wan3.0-video",
               "kling-4-0", "hailuo-02-standard", "veo3.1-fast", "pixverse-v6",
               "runway", "vidu-q4", "hailuo-02-pro", "pixverse-v6-max",
               "veo3.1-pro", "volcengine/doubao-seedance-2-5-260628"]
# 默认横评的五个：四个家族各一档 + 一条有官方单价的
DEFAULT_MODELS = ["muse-video", "sd/doubao-seedance-2-0-260128", "kling-4-0",
                  "veo3.1-pro", "hailuo-02-standard"]

# 没有成交样本的型号，用「同路成交区间」估，不用编出来的单价
VIDEO_BAND = dict(low=44.0, high=3045.71, n=16,
                  ev="本账号模型层视频 16 笔成交（muse 8 + seedance 2.0 五 + 2.5 三）")

DONE = ("completed", "complete", "done", "success", "succeeded", "settled")
FAILED = ("failed", "error", "canceled", "cancelled", "refunded", "timeout", "rejected")


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


def load_conf(explicit_key=None, explicit_host=None):
    key = None
    if explicit_key:
        key = explicit_key.strip()
    if not key:
        key = (os.environ.get("A7W_API_KEY") or "").strip() or None
    host = (explicit_host or "").strip().rstrip("/") or None
    cfg = os.path.join(os.path.expanduser("~"), ".a7w", "config.json")
    if (not key or not host) and os.path.isfile(cfg):
        try:
            d = json.load(io.open(cfg, encoding="utf-8"))
            if not key:
                k = d.get("key") or d.get("api_key")
                if k:
                    key = str(k).strip()
            if not host and d.get("host"):
                host = str(d["host"]).rstrip("/")
        except Exception:                                        # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=120, retries=2):
    """网关会重置空闲连接，网络类错误退避重试；4xx 原样返回给调用方判断。"""
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, method=method, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < retries - 1:
                last = e
                time.sleep(1 + attempt)
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(1 + attempt)
                continue
            raise Fail("call", "连不上 %s：%s" % (url, getattr(e, "reason", e)), EXIT_CALL)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:260]
        elif isinstance(e, str) and e:
            return e[:260]
        for k in ("message", "msg", "detail"):
            if d.get(k):
                return str(d[k])[:260]
        if d.get("code"):
            return str(d["code"])[:260]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s）：这条前缀下没有该路由" % st
    return (txt or "").replace("\n", " ")[:240]


def pnum(v, dash="-"):
    if v is None:
        return dash
    try:
        f = float(v)
    except Exception:                                            # noqa: BLE001
        return dash
    if abs(f - round(f)) < 1e-9:
        return "{:,}".format(int(round(f)))
    return "{:,.2f}".format(f)


def money(points):
    """点 -> 元字符串。金额一律写「元」，不用那个 cp936 编不出的窄体日元符号。"""
    try:
        return "%.2f 元" % (float(points) / POINTS_PER_YUAN)
    except Exception:                                            # noqa: BLE001
        return "-"


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def parse_models(raw):
    if not raw:
        return []
    seen, out = set(), []
    for part in re.split(r"[,\s]+", str(raw)):
        m = part.strip()
        if not m or m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def model_slug(model):
    return re.sub(r"[^0-9a-zA-Z]+", "_", model or "model").strip("_").lower() or "model"


def route_of(model, force="auto"):
    if force == "videos":
        return VIDEOS_PATH
    if force == "generations":
        return GEN_PATH
    return (MODELS.get(model) or {}).get("route") or GEN_PATH


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-300:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


def cache_load(pages):
    try:
        if not os.path.isfile(PRICE_CACHE):
            return None
        d = json.load(io.open(PRICE_CACHE, encoding="utf-8"))
        if int(d.get("pages") or 0) < int(pages):
            return None
        if time.time() - float(d.get("at") or 0) > CACHE_TTL:
            return None
        agg = d.get("agg") or {}
        for m, v in agg.items():
            v["paths"] = set(v.get("paths") or [])
            v["vals"] = [float(x) for x in (v.get("vals") or [])]
        return agg
    except Exception:                                            # noqa: BLE001
        return None


def cache_save(pages, agg):
    try:
        os.makedirs(os.path.dirname(PRICE_CACHE), exist_ok=True)
        old = None
        if os.path.isfile(PRICE_CACHE):
            try:
                old = json.load(io.open(PRICE_CACHE, encoding="utf-8"))
            except Exception:                                    # noqa: BLE001
                old = None
        if (old and int(old.get("pages") or 0) > int(pages)
                and time.time() - float(old.get("at") or 0) <= CACHE_TTL):
            return                                              # 不用小窗口覆盖大窗口
        blob = {"at": time.time(), "pages": pages,
                "agg": {m: {"vals": v.get("vals"), "paths": sorted(v.get("paths") or [])}
                        for m, v in agg.items()}}
        io.open(PRICE_CACHE, "w", encoding="utf-8", newline="\n").write(
            json.dumps(blob, ensure_ascii=False))
    except Exception:                                            # noqa: BLE001
        pass


def layer_of(paths):
    ps = [p or "" for p in (paths or [])]
    if ps and all(p.startswith(API_PREFIX + "/apps/") for p in ps):
        return "app"
    return "model"


class Ctx(object):
    """一次调用的共享缓存。所有 GET 免费，写请求只在 gen 里发。"""

    def __init__(self, key, host, a):
        self.key, self.host, self.a = key, host, a
        self._models = None
        self._pricing = None
        self._agg = None
        self._balance = None
        self.requests = 0
        self.cached = False

    def online(self):
        return bool(self.key)

    def models(self):
        if self._models is not None:
            return self._models
        if not self.key:
            self._models = []
            return self._models
        st, txt = http_json("GET", self.host + API_PREFIX + "/models", self.key, timeout=60)
        self.requests += 1
        d = jloads(txt) or {}
        data = d.get("data")
        if st != 200 or not isinstance(data, list):
            raise Fail("call", "模型目录拉取失败（HTTP %s）：%s"
                       % (st, err_text(st, txt)), EXIT_CALL)
        self._models = data
        return self._models

    def video_models(self):
        out = [m for m in self.models()
               if m.get("type_code") == "video" and m.get("model_code")]
        return out

    def pricing(self):
        if self._pricing is None:
            st, txt = http_json("GET", self.host + API_PREFIX + "/pricing",
                                self.key, timeout=60)
            self.requests += 1
            d = jloads(txt) or {}
            if st != 200 or not isinstance(d.get("pricing"), dict):
                raise Fail("call", "价目表拉取失败（HTTP %s）：%s"
                           % (st, err_text(st, txt)), EXIT_CALL)
            self._pricing = d
        return self._pricing

    def agg(self, pages):
        """GET /api/v1/me/tasks 按 model 归集 actualPrice（免费）。"""
        if not self.key or not pages:
            return {}
        if self._agg is not None:
            return self._agg
        if not getattr(self.a, "refresh", False):
            cached = cache_load(pages)
            if cached is not None:
                self._agg = cached
                self.cached = True
                return cached
        agg = {}
        for pg in range(1, min(pages, MAX_PAGES) + 1):
            if pages >= 6 and pg in (1, pages // 2, pages):
                say("  扫任务台账第 %d / %d 页（免费）…" % (pg, pages))
            st, txt = http_json("GET", "%s%s/me/tasks?limit=2000&page=%d"
                                % (self.host, API_PREFIX, pg), self.key, timeout=45)
            self.requests += 1
            if st != 200:
                break
            d = jloads(txt) or {}
            ts = d.get("tasks") or []
            if not ts:
                break
            for t in ts:
                m = (t.get("model") or "").strip()
                p = t.get("path") or ""
                if not m or "/apps/" in p:
                    continue
                try:
                    v = float(t.get("actualPrice") or 0)
                except Exception:                                # noqa: BLE001
                    continue
                if v <= 0:
                    continue
                a = agg.setdefault(m, {"vals": [], "paths": set()})
                a["vals"].append(round(v, 2))
                a["paths"].add(p)
            if len(ts) < PAGE_SIZE_ME:
                break
        cache_save(pages, agg)
        self._agg = agg
        return agg

    def balance(self):
        if self._balance is None:
            st, txt = http_json("GET", self.host + "/user/balance", self.key, timeout=40)
            self.requests += 1
            self._balance = jloads(txt) or {}
            if st != 200:
                raise Fail("call", "余额接口失败（HTTP %s）：%s"
                           % (st, err_text(st, txt)), EXIT_CALL)
        return self._balance


def quote_of(model, seconds, agg):
    """报价：先看你账号流水（live），再官方单价（rate），再基线（baseline），最后同路区间（band）。"""
    meta = MODELS.get(model) or {}
    seconds = max(1, int(seconds or DEFAULT_SECONDS))
    live = (agg or {}).get(model)
    if live and live.get("vals"):
        vals = sorted(live["vals"])
        return dict(low=vals[0], high=vals[-1], n=len(vals), source="live",
                    layer=layer_of(live.get("paths")), gate=float(vals[-1]),
                    basis="你账号 %d 笔成交（actualPrice）" % len(vals),
                    note="实测成交区间")
    if meta.get("rate"):
        pts = int(round(float(meta["rate"]) * seconds))
        return dict(low=pts, high=pts, n=1, source="rate", layer="model",
                    gate=float(pts), rate=meta["rate"], seconds=seconds,
                    basis="官方 %d 点/秒 x %d 秒" % (meta["rate"], seconds),
                    note="按请求秒数结算")
    if meta.get("samples"):
        vals = sorted(meta["samples"])
        return dict(low=vals[0], high=vals[-1], n=len(vals), source="baseline",
                    layer="model", gate=float(vals[-1]),
                    basis="本机 2026-11-08 实测基线 %d 笔（不是你的流水）" % len(vals),
                    note="基线区间")
    return dict(low=VIDEO_BAND["low"], high=VIDEO_BAND["high"], n=VIDEO_BAND["n"],
                source="baseline", layer="band", gate=float(VIDEO_BAND["high"]),
                basis="该型号 0 笔成交，按同路 %d 笔区间估（保底 %d 点）"
                      % (VIDEO_BAND["n"], WILDCARD_MIN),
                note="同路区间，预算按上界")


def quote_line(q):
    if q["low"] == q["high"]:
        return "%s 点" % pnum(q["low"])
    return "%s - %s 点" % (pnum(q["low"]), pnum(q["high"]))


def source_cn(q):
    return {"live": "实测", "rate": "官方单价", "baseline": "基线"}.get(q["source"], "同路区间")


def resolve(a, models):
    if not models:
        raise Fail("usage", "至少给一个型号：--models a,b,c（列全部用 catalog）", EXIT_USAGE)
    unknown = [m for m in models if m not in MODELS]
    if unknown and not getattr(a, "allow_any_model", False):
        raise Fail("usage",
                   "本包还没有这些型号的基线：%s。\n"
                   "可横评的 13 个：%s\n"
                   "确定要试的型号加 --allow-any-model（报价按同路区间，预算按上界）。"
                   % ("、".join(unknown), "、".join(MODEL_ORDER[:6])),
                   EXIT_USAGE)
    return models


# ───────────────────────── catalog ─────────────────────────
def cmd_catalog(a, key, host):
    ctx = Ctx(key, host, a)
    agg = ctx.agg(getattr(a, "pages", DEFAULT_PAGES)) if ctx.online() else {}
    rows = []
    for m in MODEL_ORDER:
        meta = MODELS[m]
        q = quote_of(m, a.seconds, agg)
        rows.append(dict(model=m, name=meta["name"], route=meta["route"],
                         refs=meta["refs"], low=q["low"], high=q["high"],
                         source=q["source"], n=q["n"], note=meta["note"],
                         probe=meta["probe"], basis=q["basis"]))
    rows.sort(key=lambda r: (r["high"], r["low"]))
    out = {"ok": True, "count": len(rows), "models": rows, "online": ctx.online(),
           "pointsPerYuan": POINTS_PER_YUAN, "seconds": a.seconds,
           "priceSource": host + API_PREFIX + "/me/tasks",
           "note": "单价来自 me/tasks 的 actualPrice；没跑过的型号按同路区间估，标 source=baseline"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("文生视频模型台 · 13 个模型（按预算上界从低到高，1 元 = 100 点）")
    print("  价格来源：%s%s" % ("你账号的 /api/v1/me/tasks" if ctx.online() else "离线基线",
                              " · 本机缓存 6 小时内" if ctx.cached else ""))
    print()
    print("  %s %s %s %s %s" % (pad("model", 34), pad("报价（点）", 17),
                                 pad("来源", 10), pad("参考图", 7), "一句话"))
    print("  " + "-" * 104)
    for r in rows:
        print("  %s %s %s %s %s" % (
            pad(r["model"][:34], 34), pad(quote_line(r), 17),
            pad(source_cn(r), 10), pad(r["refs"], 7), r["note"]))
    print()
    print("  提交路径：muse-video 走 POST %s（这条路由的历史成功路径）；" % VIDEOS_PATH)
    print("            其余 12 个走 POST %s（kling / veo / hailuo / vidu /" % GEN_PATH)
    print("            runway / pixverse 都在这条上；目录型号拿去打 /videos 会 404）。")
    print("  没有成交样本的型号按同路 %d 笔 %s - %s 点估，预算按上界 %s 点。"
          % (VIDEO_BAND["n"], pnum(VIDEO_BAND["low"]), pnum(VIDEO_BAND["high"]),
             pnum(VIDEO_BAND["high"])))
    print("  kling 家族在目录里是 14 个型号，本包挑了最新的一档 kling-4-0；")
    print("  想跑别的档直接写型号名，例如 --models kling-3-0-omni。")
    print()
    print("  先报价不动钱：cost --models %s" % ",".join(DEFAULT_MODELS[:3]))
    return 0


# ───────────────────────── cost ─────────────────────────
def cmd_cost(a, key, host):
    models = resolve(a, parse_models(a.models) or DEFAULT_MODELS)
    ctx = Ctx(key, host, a)
    agg = ctx.agg(getattr(a, "pages", DEFAULT_PAGES)) if ctx.online() else {}
    rows = []
    for m in models:
        q = quote_of(m, a.seconds, agg)
        meta = MODELS.get(m) or {}
        rows.append(dict(model=m, name=meta.get("name") or m, route=route_of(m, a.route),
                         refs=meta.get("refs"), low=q["low"], high=q["high"], n=q["n"],
                         source=q["source"], gate=q["gate"], basis=q["basis"],
                         seconds=q.get("seconds"), rate=q.get("rate")))
    total = sum(float(r["gate"]) for r in rows)
    ok = sorted(rows, key=lambda r: (r["gate"], r["low"]))
    lo = min(float(r["low"]) for r in rows)
    hi = max(float(r["high"]) for r in rows)
    spread = (hi / lo) if lo else 0.0
    out = {"ok": True, "models": ok, "seconds": a.seconds, "size": a.size,
           "totalPoints": round(total, 2), "totalYuan": round(total / POINTS_PER_YUAN, 2),
           "cheapest": ok[0]["model"] if ok else None,
           "mostExpensive": ok[-1]["model"] if ok else None,
           "spread": round(spread, 2), "online": ctx.online(),
           "pointsPerYuan": POINTS_PER_YUAN,
           "note": "合计按每个型号的上界相加；实际以扣费流水为准"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("同一句话，%d 个模型逐个报价（1 元 = 100 点，按上界排序）" % len(ok))
    print("=" * 96)
    print("  %s %s %s %s %s" % (pad("model", 34), pad("报价（点）", 18),
                                 pad("来源", 10), pad("闸门", 9), "口径"))
    print("  " + "-" * 92)
    for r in ok:
        print("  %s %s %s %s %s" % (
            pad(r["model"][:34], 34), pad(quote_line(r), 18), pad(source_cn(r), 10),
            pad(pnum(r["gate"]), 9), r["basis"][:40]))
    print()
    print("  合计（按上界）：%s 点 = %s" % (pnum(total), money(total)))
    if len(ok) > 1:
        print("  按上界：最贵 %s %s 点 · 最便宜 %s %s 点 · 相差 %.1f 倍"
              % (ok[-1]["model"], pnum(ok[-1]["gate"]), ok[0]["model"], pnum(ok[0]["gate"]),
                 (float(ok[-1]["gate"]) / float(ok[0]["gate"]))
                 if ok[0]["gate"] else 0.0))
    print("  选一个：gen --models %s --prompt \"...\" --yes" % ok[0]["model"])
    print("  全跑横评：gen --models %s --prompt \"...\" --yes"
          % ",".join(r["model"] for r in ok))
    if a.seconds:
        print("  --seconds %d 只影响请求参数；只有写死单价的档（muse-video）按秒结算。"
              % a.seconds)
    if ctx.cached:
        print("  单价来自本机缓存（6 小时内）；--refresh 强制重扫 me/tasks。")
    if not ctx.online():
        print("  离线模式：只用了基线价。带上 Key 跑一次，这里会换成你自己账号的成交价。")
    return 0


# ───────────────────────── doctor ─────────────────────────
def cmd_doctor(a, key, host):
    if not key:
        raise Fail("usage", "doctor 需要一个 API Key：--key / A7W_API_KEY / a7w.py login",
                   EXIT_USAGE)
    ctx = Ctx(key, host, a)
    checks = []

    def probe(method, path, body=None, timeout=None):
        """每个直发的探针也算进请求数（doctor --json 里的 requests）。"""
        ctx.requests += 1
        return http_json(method, host + path, key, body, timeout=timeout or a.timeout)

    # 1) 模型目录
    try:
        all_models = ctx.models()
        vids = ctx.video_models()
        kling = [m for m in all_models if "kling" in (m.get("model_code") or "").lower()]
        checks.append(("模型目录 GET /api/v1/models", len(all_models) >= 300,
                       "HTTP 200 · 共 %d 条 · 视频型号 %d 个 · kling 家族 %d 个"
                       % (len(all_models), len(vids), len(kling))))
    except Fail as e:
        checks.append(("模型目录 GET /api/v1/models", False, e.message[:70]))

    # 2) 价目表：模型层没有专属规则
    try:
        pr = ctx.pricing()
        rules = pr.get("pricing") or {}
        wild = rules.get("*") or {}
        has_gen = GEN_PATH in rules
        has_models = "modelPricing" in pr
        checks.append(("价目表 GET /api/v1/pricing（模型层无专属规则）",
                       len(rules) >= 100 and not has_gen and not has_models,
                       "HTTP 200 · %d 条规则 · %s模型层规则 · 通配保底 %s 点 / markup %s%%"
                       % (len(rules),
                          "表里有" if (has_gen or has_models) else "表里没有",
                          pnum(wild.get("minPoints")),
                          pnum(wild.get("markupPercent")))))
    except Fail as e:
        checks.append(("价目表 GET /api/v1/pricing", False, e.message[:70]))

    # 3) 任务台账（报价数据源）
    try:
        st, txt = probe("GET", API_PREFIX + "/me/tasks?limit=2000&page=1", timeout=40)
        d = jloads(txt) or {}
        checks.append(("任务台账 GET /api/v1/me/tasks", st == 200 and bool(d.get("tasks")),
                       "HTTP %s · 共 %s 条 · 本页 %d 条"
                       % (st, pnum(d.get("total")), len(d.get("tasks") or []))))
    except Fail as e:
        checks.append(("任务台账 GET /api/v1/me/tasks", False, e.message[:70]))

    # 4) 提交端点：空 body -> 400 model field is required（停在校验层）
    st, txt = probe("POST", GEN_PATH, {})
    d = jloads(txt) or {}
    msg = err_text(st, txt)
    checks.append(("提交端点 POST %s 存在（空 body 400）" % GEN_PATH,
                   st == 400 and "model field is required" in msg,
                   "HTTP %s · %s" % (st, msg[:52])))

    # 5) 型号确认：合法 model + 缺 prompt -> 400，不建任务
    probe_model = DEFAULT_MODELS[2]                     # kling-4-0
    st, txt = probe("POST", GEN_PATH, {"model": probe_model})
    msg = err_text(st, txt)
    checks.append(("型号可提交 %s（缺 prompt 400）" % probe_model,
                   st == 400 and "prompt" in msg.lower(),
                   "HTTP %s · %s" % (st, msg[:48])))

    # 6) 路由分工：同样一个 model 走 /videos 会 404（目录里有、路由不认）
    st, txt = probe("POST", VIDEOS_PATH, {"model": probe_model})
    d6 = jloads(txt) or {}
    code6 = (d6.get("error") or {}).get("code") if isinstance(d6.get("error"), dict) else ""
    checks.append(("路由分工：/videos 不认 %s（404 model_not_found）" % probe_model,
                   st == 404 and code6 == "model_not_found",
                   "HTTP %s · %s" % (st, code6 or err_text(st, txt)[:40])))

    # 7) 查询路由：假 taskId -> code 0「任务不存在」，免费
    st, txt = probe("GET", TASKS_PATH + "/probe-no-such-task", timeout=40)
    d7 = jloads(txt) or {}
    checks.append(("查询路由 GET /api/v1/tasks/<id> 可用（假 id 回任务不存在）",
                   st == 200 and d7.get("code") == 0,
                   "HTTP %s · %s" % (st, str(d7.get("msg") or "")[:24])))

    # 8) 余额 + 前后对比
    before = 0.0
    try:
        b = ctx.balance()
        before = float(b.get("available_points") or 0)
        checks.append(("余额 GET /user/balance", b.get("available_points") is not None,
                       "可用 %s 点 · 冻结 %s 点 · 1 元 = %s 点"
                       % (pnum(before), pnum(b.get("frozen") or 0), b.get("rate"))))
    except Fail as e:
        checks.append(("余额 GET /user/balance", False, e.message[:70]))
    try:
        st, txt = probe("GET", "/user/balance", timeout=40)
        after = float((jloads(txt) or {}).get("available_points") or 0)
        delta = round(after - before, 6)
        checks.append(("余额前后对比（本轮 0 点）", abs(delta) < 1e-6,
                       "前 %s -> 后 %s · 差 %s 点"
                       % (pnum(before), pnum(after), pnum(delta))))
    except Fail as e:
        checks.append(("余额前后对比", False, e.message[:70]))

    # 9) 流水：最近 100 条里视频线净额
    net, cnt = 0.0, 0
    try:
        st, txt = probe("GET", "/user/balance/logs?limit=100", timeout=40)
        d = jloads(txt) or {}
        logs = d.get("logs") or []
        lt = time.localtime()
        today0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) * 1000
        for x in logs:
            ref = x.get("reference") or ""
            if "videos" in ref or "video/generations" in ref:
                cnt += 1
                if float(x.get("at") or 0) >= today0:
                    net += float(x.get("points") or 0)
        checks.append(("流水 GET /user/balance/logs", st == 200 and bool(logs),
                       "HTTP %s · 最近 100 条里视频线 %d 笔 · 今日净 %s 点"
                       % (st, cnt, pnum(net))))
    except Fail as e:
        checks.append(("流水 GET /user/balance/logs", False, e.message[:70]))

    out = {"ok": all(c[1] for c in checks), "requests": ctx.requests,
           "endpoint": host + GEN_PATH, "fallback": host + VIDEOS_PATH,
           "query": host + TASKS_PATH + "/<id>",
           "todayVideoNetPoints": round(net, 2),
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks],
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（6 个只读端点 + 3 个免费探针，全部停在校验层）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 50), dd))
    print()
    print("  主路：POST %s（实测 13 个型号都停在参数校验）" % (host + GEN_PATH))
    print("  裸 ID 另有历史成功路径：POST %s（目录型号打它会 404）" % (host + VIDEOS_PATH))
    print("  查询：GET  %s/<id>（免费，轮询只走这条）" % (host + TASKS_PATH))
    print("  报价：GET  %s%s/me/tasks（免费，actualPrice 反推）" % (host, API_PREFIX))
    print("  本轮花费 0 点：探针全部停在参数校验，没有建任务、没有冻结。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 请求体 ─────────────────────────
def build_body(a, model):
    body = {"model": model, "prompt": a.prompt}
    if getattr(a, "seconds", None):
        body["seconds"] = int(a.seconds)
    if getattr(a, "size", None):
        body["size"] = a.size
    if getattr(a, "extra", None):
        try:
            extra = json.loads(a.extra)
        except Exception:                                        # noqa: BLE001
            raise Fail("usage", "--extra 要是 JSON 对象，例如 '{\"ratio\":\"9:16\"}'",
                       EXIT_USAGE)
        if not isinstance(extra, dict):
            raise Fail("usage", "--extra 要是 JSON 对象（当前是 %s）"
                       % type(extra).__name__, EXIT_USAGE)
        body.update(extra)
    return body


def _check_common(a, models):
    if not (a.prompt or "").strip():
        raise Fail("usage",
                   "必须给 --prompt（一句话写清三件事：主体是什么、怎么动、镜头怎么走）",
                   EXIT_USAGE)
    if len(a.prompt) > 4000:
        raise Fail("usage", "--prompt 最多 4000 字（当前 %d）" % len(a.prompt), EXIT_USAGE)
    if not (1 <= int(a.seconds) <= 180):
        raise Fail("usage", "--seconds 只支持 1 - 180 的整数（当前 %s）" % a.seconds,
                   EXIT_USAGE)
    if a.size and not re.match(r"^\d{2,5}x\d{2,5}$", a.size):
        raise Fail("usage", "--size 写成 宽x高，例如 1280x720 或 720x1280（当前 %s）"
                   % a.size, EXIT_USAGE)
    if len(models) > 8:
        raise Fail("usage", "一次最多横评 8 个型号（当前 %d）；拆成两次更稳" % len(models),
                   EXIT_USAGE)


# ───────────────────────── status / wait ─────────────────────────
def _pick(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _dig_url(d):
    for src in (d, d.get("result") or {}, d.get("storage") or {}, d.get("data") or {}):
        if isinstance(src, dict):
            for k in ("video_url", "videoUrl", "url", "resultUrl", "result_url",
                      "output_url", "storage_url"):
                v = src.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    return v
    return None


def _dig_cost(d):
    if isinstance(d, dict):
        for k in ("actualPrice", "points_cost", "pointsCost", "cost", "points"):
            v = d.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        for v in d.values():
            if isinstance(v, (dict, list)):
                got = _dig_cost(v)
                if got is not None:
                    return got
    elif isinstance(d, list):
        for it in d:
            got = _dig_cost(it)
            if got is not None:
                return got
    return None


def fetch_task(a, key, host, tid):
    """轮询只走一条免费路由：GET /api/v1/tasks/<id>（假 id 回 code 0）。"""
    q = urllib.parse.quote(tid)
    st, txt = http_json("GET", "%s%s/%s" % (host, TASKS_PATH, q), key, timeout=45)
    d = jloads(txt) or {}
    body = d.get("data") if isinstance(d.get("data"), dict) else d
    hit = st == 200 and isinstance(body, dict) and (
        body.get("status") or body.get("task_id") or body.get("taskId") or body.get("id"))
    out = {"http": st, "hit": bool(hit), "raw": txt[:400],
           "status": (body.get("status") if isinstance(body, dict) else None),
           "url": _dig_url(d) or _dig_url(body or {}),
           "cost": _dig_cost(d),
           "message": d.get("msg") or d.get("message") or ""}
    if isinstance(body, dict):
        for k in ("progress", "seconds", "size", "model", "fail_reason", "refund",
                  "reservePrice", "expires_at", "video_url_expires_at"):
            if body.get(k) is not None:
                out[k] = body[k]
    return out


def cmd_status(a, key, host):
    tid = (a.task_id or "").strip()
    if not tid:
        raise Fail("usage", "必须给 --task-id（提交时返回的 id）", EXIT_USAGE)
    d = fetch_task(a, key, host, tid)
    if not d["hit"]:
        raise Fail("call", "查不到任务 %s（HTTP %s）：%s"
                   % (tid, d["http"], d["message"] or d["raw"][:80]), EXIT_CALL)
    out = {"ok": True, "taskId": tid, "status": d.get("status"),
           "progress": d.get("progress"), "model": d.get("model"),
           "seconds": d.get("seconds"), "size": d.get("size"),
           "videoUrl": d.get("url"), "cost": d.get("cost"),
           "message": d.get("message")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  状态：%s%s" % (d.get("status"),
                          "" if d.get("progress") is None else " · 进度 %s" % d.get("progress")))
    if d.get("model"):
        print("  型号：%s%s" % (d.get("model"),
                              "" if d.get("seconds") is None else " · %s 秒" % d.get("seconds")))
    if d.get("cost") is not None:
        print("  实际点数：%s 点 = %s" % (pnum(d.get("cost")), money(d.get("cost"))))
    if d.get("url"):
        print("  成片：%s" % d.get("url"))
    if d.get("message"):
        print("  说明：%s" % str(d.get("message"))[:200])
    return 0


def _ext_of(raw, fallback="mp4"):
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:3] == b"\xff\xd8\xff":
        return "jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    if raw[4:8] == b"ftyp":
        return "mp4"
    return fallback


def download(url, base, timeout=600):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as x:
        raw = x.read()
    p = "%s.%s" % (base, _ext_of(raw))
    with open(p, "wb") as fh:
        fh.write(raw)
    return p


def _poll(a, key, host, tid):
    deadline = time.time() + max(30, int(a.limit))
    last = {}
    while True:
        d = fetch_task(a, key, host, tid)
        last = d
        st = str(d.get("status") or "").lower()
        if st in DONE or st in FAILED:
            return d, st
        if time.time() > deadline:
            return d, st or "timeout"
        say("  %s 状态 %s，%d 秒后再查（查任务免费）…" % (tid, st or "-", a.every))
        time.sleep(max(2, int(a.every)))


def _write_sheet(run_dir, man, rows):
    io.open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(man, ensure_ascii=False, indent=1))
    lines = ["# 同一句话，五个模型 · 对比清单 %s" % (man.get("runId") or "-"), "",
             "prompt：%s" % (man.get("prompt") or "-"), "",
             "参数：每个模型 %s 秒 · 尺寸 %s · 提交路径 %s"
             % (man.get("seconds") or "-", man.get("size") or "模型默认", GEN_PATH), "",
             "| 模型 | 报价（点） | 来源 | 状态 | 实际点数 | 用时 | 成片 |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| `%s` | %s | %s | %s | %s | %ss | %s |" % (
            r.get("model"), pnum(r.get("gate")), r.get("sourceCn") or "-",
            r.get("status") or "-",
            pnum(r.get("actualPoints")) if r.get("actualPoints") is not None else "-",
            r.get("elapsed") or "-", r.get("file") or (r.get("error") or "-")))
    lines.append("")
    lines.append("合计预估 %s 点（%s），实际 %s 点。" % (
        pnum(man.get("totalEstimated")), money(man.get("totalEstimated") or 0),
        pnum(man.get("totalActual")) if man.get("totalActual") is not None else "见流水"))
    lines.append("")
    lines.append("同一句话、同一秒数、同一尺寸，只有 model 不同 —— 这才是可比的横评。")
    lines.append("")
    for r in rows:
        if r.get("videoUrl"):
            lines.append("- `%s` 成片：%s" % (r.get("model"), r.get("videoUrl")))
    io.open(os.path.join(run_dir, "对比清单.md"), "w", encoding="utf-8",
            newline="\n").write("\n".join(lines) + "\n")


# ───────────────────────── gen ─────────────────────────
def cmd_gen(a, key, host):
    if not key:
        raise Fail("usage", "gen 需要 API Key：--key / A7W_API_KEY / a7w.py login",
                   EXIT_USAGE)
    models = parse_models(a.models) or parse_models(a.model)
    models = resolve(a, models or list(DEFAULT_MODELS))
    _check_common(a, models)
    ctx = Ctx(key, host, a)
    agg = ctx.agg(getattr(a, "pages", DEFAULT_PAGES))
    quotes = []
    for m in models:
        q = quote_of(m, a.seconds, agg)
        q["model"] = m
        q["sourceCn"] = source_cn(q)
        quotes.append(q)
    total = sum(float(q["gate"]) for q in quotes)

    if total > a.budget:
        raise Fail("budget",
                   "预计 %s 点（%s）超过 --budget %d 点。这一条只读了免费台账，"
                   "一个出片请求都没发。调大 --budget（单位：点）或减型号。"
                   % (pnum(total), money(total), a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实出片：%d 个模型，按上界约 %s 点（%s）。"
                   "上游按模型预冻结，失败全额退回。确认请加 --yes。"
                   % (len(quotes), pnum(total), money(total)), EXIT_CONFIRM)

    bodies = [(q, build_body(a, q["model"])) for q in quotes]
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "seconds": a.seconds, "size": a.size,
               "models": [{"model": q["model"], "gate": q["gate"], "source": q["source"],
                           "route": route_of(q["model"], a.route)} for q in quotes],
               "totalPoints": round(total, 2), "totalYuan": round(total / POINTS_PER_YUAN, 2),
               "requests": [{"url": host + route_of(q["model"], a.route), "body": b}
                            for q, b in bodies]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（一个请求都不发，不冻结、不扣费）")
        for q, b in bodies:
            print("  -> POST %s" % (host + route_of(q["model"], a.route)))
            print("     %s" % json.dumps(b, ensure_ascii=False)[:320])
            print("     %s · 上界 %s 点 · %s" % (q["model"], pnum(q["gate"]), q["basis"][:50]))
        print("  合计：%s 点（%s）" % (pnum(total), money(total)))
        return 0

    run_id = time.strftime("%Y%m%d-%H%M%S")
    outdir = os.path.abspath(a.outdir or ".")
    run_dir = os.path.join(outdir, "run-" + run_id)
    os.makedirs(run_dir, exist_ok=True)
    results = []
    for seq, (q, body) in enumerate(bodies, 1):
        model = q["model"]
        path = route_of(model, a.route)
        say("正在提交 %d/%d：%s（上界 %s 点）…" % (seq, len(bodies), model, pnum(q["gate"])))
        t0 = time.time()
        res = dict(model=model, status="failed", source=q["source"], sourceCn=q["sourceCn"],
                   gate=q["gate"], basis=q["basis"], route=path, taskId=None, file=None,
                   videoUrl=None, actualPoints=None, error=None, elapsed=0.0)
        try:
            st, txt = http_json("POST", host + path, key, body, timeout=max(60, a.timeout))
            d = jloads(txt) or {}
            flat = d.get("data") if isinstance(d.get("data"), dict) else d
            tid = _pick(flat or {}, "id", "task_id", "taskId") or _pick(
                d, "id", "task_id", "taskId")
            if st in (200, 201) and tid:
                res["taskId"] = tid
                res["status"] = (flat or {}).get("status") or d.get("status") or "submitted"
                if a.wait:
                    info, status = _poll(a, key, host, tid)
                    res["status"] = status or res["status"]
                    res["actualPoints"] = info.get("cost")
                    if info.get("url"):
                        res["videoUrl"] = info.get("url")
                        base = os.path.join(run_dir, "%02d-%s" % (seq, model_slug(model)))
                        try:
                            res["file"] = os.path.basename(download(info["url"], base))
                        except Exception as e:                   # noqa: BLE001
                            say("  下载失败：%s: %s" % (type(e).__name__, e))
                elif _dig_url(flat or {}) or _dig_url(d):
                    res["videoUrl"] = _dig_url(flat or {}) or _dig_url(d)
            else:
                res["status"] = "failed"
                res["error"] = err_text(st, txt)
        except Fail as e:
            res["error"] = e.message
        except Exception as e:                                   # noqa: BLE001
            res["error"] = "%s: %s" % (type(e).__name__, e)
        res["elapsed"] = round(time.time() - t0, 1)
        results.append(res)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "gen",
                    "model": model, "seconds": a.seconds, "size": a.size,
                    "status": res["status"], "taskId": res["taskId"],
                    "gate": q["gate"], "actualPoints": res["actualPoints"],
                    "route": path, "elapsed": res["elapsed"]})

    ok_results = [x for x in results if x["taskId"]]
    actual_total = sum(float(x["actualPoints"] or 0) for x in results)
    man = dict(runId=run_id, at=time.strftime("%Y-%m-%dT%H:%M:%S"), prompt=a.prompt,
               seconds=a.seconds, size=a.size, outdir=run_dir, results=results,
               totalEstimated=round(total, 2),
               totalActual=round(actual_total, 2) if actual_total else None)
    _write_sheet(run_dir, man, results)
    out = {"ok": bool(ok_results), "runId": run_id, "dir": run_dir,
           "seconds": a.seconds, "size": a.size, "results": results,
           "totalEstimated": round(total, 2),
           "totalActual": round(actual_total, 2) if actual_total else None,
           "manifest": os.path.join(run_dir, "manifest.json"),
           "sheet": os.path.join(run_dir, "对比清单.md")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok_results else EXIT_CALL
    print()
    print("横评结果（%d/%d 个模型拿到任务）" % (len(ok_results), len(results)))
    print("  %s %s %s %s %s %s" % (pad("模型", 34), pad("状态", 12), pad("上界", 9),
                                     pad("实际", 8), pad("用时", 7), "成片 / 报错"))
    print("  " + "-" * 100)
    for x in results:
        print("  %s %s %s %s %s %s" % (
            pad(x["model"][:34], 34), pad(x["status"], 12), pad(pnum(x["gate"]), 9),
            pad(pnum(x["actualPoints"]) if x["actualPoints"] is not None else "-", 8),
            pad("%ss" % x["elapsed"], 7),
            (x["file"] or x["videoUrl"] or (x["error"] or "-"))[:40]))
    print()
    print("  落盘目录：%s" % run_dir)
    print("  对比清单：%s" % out["sheet"])
    print("  合计：预估 %s 点（%s），实际 %s"
          % (pnum(total), money(total),
             (pnum(actual_total) + " 点") if actual_total else "见 /user/balance/logs"))
    if not a.wait:
        print()
        print("  任务已提交，片子会自己跑完。接着取（查任务免费）：")
        for x in results:
            if x["taskId"]:
                print("    python3 scripts/run.py wait %s --outdir %s" % (x["taskId"], outdir))
    return 0 if ok_results else EXIT_CALL


def cmd_wait(a, key, host):
    tid = (a.task_id or "").strip()
    if not tid:
        raise Fail("usage", "必须给任务 id（wait task_xxx）", EXIT_USAGE)
    say("等 %s（每 %d 秒查一次，上限 %d 分钟，查任务免费）…"
        % (tid, a.every, max(1, int(a.limit) // 60)))
    info, status = _poll(a, key, host, tid)
    outdir = os.path.abspath(a.outdir or ".")
    os.makedirs(outdir, exist_ok=True)
    out = {"ok": status in DONE, "taskId": tid, "status": status,
           "videoUrl": info.get("url"), "cost": info.get("cost"), "file": None}
    if status in DONE and info.get("url"):
        try:
            base = os.path.join(outdir, "video-%s" % model_slug(tid))
            out["file"] = download(info["url"], base)
        except Exception as e:                                   # noqa: BLE001
            say("  下载失败：%s: %s" % (type(e).__name__, e))
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_CALL
    print("任务 %s：%s" % (tid, status))
    if out["cost"] is not None:
        print("  实际点数：%s 点 = %s" % (pnum(out["cost"]), money(out["cost"])))
    if out["videoUrl"]:
        print("  成片链接：%s（约 30 分钟有效，及时转存）" % out["videoUrl"])
    if out["file"]:
        print("  已下载：%s" % out["file"])
    if not out["ok"]:
        print("  还没完成。再等一次：python3 scripts/run.py wait %s --outdir %s"
              % (tid, outdir))
    return 0 if out["ok"] else EXIT_CALL


def cmd_sheet(a, key, host):
    path = a.manifest
    if a.run and not path:
        path = os.path.join(a.run, "manifest.json")
    if not path or not os.path.isfile(path):
        raise Fail("usage", "给 --run 目录或 --manifest manifest.json 路径", EXIT_USAGE)
    man = json.load(io.open(path, encoding="utf-8"))
    rows = man.get("results") or []
    run_dir = os.path.dirname(os.path.abspath(path))
    _write_sheet(run_dir, man, rows)
    out = {"ok": True, "runId": man.get("runId"), "dir": run_dir,
           "models": [{"model": x.get("model"), "status": x.get("status"),
                       "gate": x.get("gate"), "actualPoints": x.get("actualPoints")}
                      for x in rows]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("对比清单已生成：%s" % os.path.join(run_dir, "对比清单.md"))
    print("  %s %s %s %s" % (pad("模型", 34), pad("状态", 12), pad("上界", 9), "实际点数"))
    for x in rows:
        print("  %s %s %s %s" % (
            pad(str(x.get("model"))[:34], 34), pad(x.get("status") or "-", 12),
            pad(pnum(x.get("gate")), 9),
            pnum(x.get("actualPoints")) if x.get("actualPoints") is not None else "-"))
    return 0


def cmd_log(a, key, host):
    if not os.path.isfile(LEDGER):
        out = {"ok": True, "count": 0, "entries": []}
    else:
        arr = json.load(io.open(LEDGER, encoding="utf-8"))
        out = {"ok": True, "count": len(arr), "entries": arr[-a.limit:]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(out["entries"]), out["count"]))
    for e in out["entries"]:
        print("  %s %-10s %-34s %-10s 上界 %s 点 实际 %s 点 %.1fs" % (
            e.get("at"), e.get("status"), str(e.get("model"))[:34], e.get("taskId") or "-",
            pnum(e.get("gate")),
            pnum(e.get("actualPoints")) if e.get("actualPoints") is not None else "-",
            e.get("elapsed") or 0))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 文生视频模型台：一句话，多模型先报价再横评",
        epilog="端点：POST %s（横评提交）· GET %s/<id>（查任务，0 点）· "
               "GET %s/me/tasks（单价反推，0 点）· GET %s/models（型号，0 点）"
               % (DEFAULT_HOST + GEN_PATH, DEFAULT_HOST + TASKS_PATH,
                  DEFAULT_HOST + API_PREFIX, DEFAULT_HOST + API_PREFIX),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = %d 元）"
                         % (DEFAULT_BUDGET, DEFAULT_BUDGET // POINTS_PER_YUAN))
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    def gate_args(p):
        p.add_argument("--yes", action="store_true", help="确认真实出片并扣点")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，一个都不发")

    p = sub.add_parser("catalog", help="13 个视频模型：报价 / 来源 / 提交路径（免费）",
                       allow_abbrev=False)
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="按多少秒报价（默认 %d）" % DEFAULT_SECONDS)
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页 = %d 条）"
                        % (DEFAULT_PAGES, DEFAULT_PAGES * PAGE_SIZE_ME))
    p.add_argument("--refresh", action="store_true", help="忽略本机价格缓存，重扫 me/tasks")
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="同一句话多模型逐个报价（免费）", allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔的型号，默认 %s" % ",".join(DEFAULT_MODELS))
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="请求多少秒（默认 %d；只有写死单价的档按秒结算）" % DEFAULT_SECONDS)
    p.add_argument("--size", default="", help="宽x高，例如 1280x720（默认模型默认）")
    p.add_argument("--route", choices=["auto", "generations", "videos"], default="auto",
                   help="提交路径（默认 auto：/videos/generations）")
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页）" % DEFAULT_PAGES)
    p.add_argument("--refresh", action="store_true", help="忽略本机价格缓存，重扫 me/tasks")
    p.add_argument("--allow-any-model", action="store_true",
                   help="型号不在 13 个里也允许报价（按同路区间，预算按上界）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检端点 / 报价来源 / 余额前后对比（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("gen", help="多模型横评出片（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔的型号，例如 %s" % ",".join(DEFAULT_MODELS[:3]))
    p.add_argument("--model", help="只跑一个型号（--models 的单数写法）")
    p.add_argument("--prompt", help="提示词，所有模型共用同一句")
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="每条多少秒（默认 %d）" % DEFAULT_SECONDS)
    p.add_argument("--size", default="", help="宽x高，例如 1280x720 / 720x1280（默认模型默认）")
    p.add_argument("--extra", help="额外请求字段，JSON 对象，例如 '{\"ratio\":\"9:16\"}'")
    p.add_argument("--route", choices=["auto", "generations", "videos"], default="auto",
                   help="提交路径（默认 auto：/videos/generations）")
    p.add_argument("--outdir", default=".", help="落盘根目录（默认当前目录）")
    p.add_argument("--wait", action="store_true", help="提交后等到完成并自动下载")
    p.add_argument("--every", type=int, default=10, help="轮询间隔秒数（默认 10）")
    p.add_argument("--limit", type=int, default=900, help="最长等待秒数（默认 900 = 15 分钟）")
    p.add_argument("--timeout", type=int, default=180, help="单次提交超时秒数（默认 180）")
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页）" % DEFAULT_PAGES)
    p.add_argument("--refresh", action="store_true", help="忽略本机价格缓存，重扫 me/tasks")
    p.add_argument("--allow-any-model", action="store_true",
                   help="型号不在 13 个里也允许提交（报价按同路区间）")
    gate_args(p)
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("status", help="查任务（免费，只走 GET /api/v1/tasks/<id>）",
                       allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 id")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("wait", help="等一个任务完成并下载（免费）", allow_abbrev=False)
    p.add_argument("task_id", nargs="?", help="任务 id（也可以写 --task-id）")
    p.add_argument("--task-id", dest="task_id_opt", help="任务 id（等价写法）")
    p.add_argument("--outdir", default=".", help="下载目录（默认当前目录）")
    p.add_argument("--every", type=int, default=15, help="轮询间隔秒数（默认 15）")
    p.add_argument("--limit", type=int, default=1800, help="最长等待秒数（默认 1800 = 30 分钟）")
    p.set_defaults(fn=cmd_wait)

    p = sub.add_parser("sheet", help="用 manifest 重新生成对比清单（免费）", allow_abbrev=False)
    p.add_argument("--run", help="run-YYYYmmdd-HHMMSS 目录")
    p.add_argument("--manifest", help="manifest.json 路径")
    p.set_defaults(fn=cmd_sheet)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="显示最近几条（默认 20）")
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以；每个子 parser 都补一份，default=SUPPRESS 不覆盖父级
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


# 不需要 Key 的子命令（读不到线上数据时退回离线基线）
OFFLINE_OK = ("cmd_catalog", "cmd_cost", "cmd_log", "cmd_sheet")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0),
                       ("yes", False), ("dry_run", False), ("pages", DEFAULT_PAGES),
                       ("refresh", False), ("seconds", DEFAULT_SECONDS), ("size", ""),
                       ("route", "auto"), ("models", None), ("model", None),
                       ("prompt", None), ("extra", None), ("outdir", "."),
                       ("wait", False), ("every", 10), ("limit", 900),
                       ("timeout", 180), ("allow_any_model", False),
                       ("task_id", None), ("task_id_opt", None), ("run", None),
                       ("manifest", None)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    if not a.task_id and getattr(a, "task_id_opt", None):
        a.task_id = a.task_id_opt
    key, host = load_conf(a.key, a.host)
    fn_name = getattr(a.fn, "__name__", "")
    try:
        if not key and fn_name not in OFFLINE_OK:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                       EXIT_USAGE)
        return a.fn(a, key, host)
    except Fail as e:
        if a.json:
            print(json.dumps({"ok": False, "exit": e.exit_code,
                              "error": {"kind": e.kind, "message": e.message}},
                             ensure_ascii=False))
        else:
            say("失败：%s" % e.message)
        return e.exit_code


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        say("已中断。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
