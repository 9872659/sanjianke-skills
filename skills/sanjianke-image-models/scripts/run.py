#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 文生图模型台（sanjianke-image-models）

一句话：同一句 prompt，先让 3 个出图模型各报一次价，再决定跑哪一个。

## 这一台和普通出图包差在哪

普通出图包把「一张图」写死成一个模型。这一台先回答「用哪个模型」：
`cost --models a,b,c` 逐个报价、按价钱排序、给出最贵与最便宜的倍数；
`gen --models a,b,c` 用同一句 prompt 逐个出图，落盘带命名规范，并生成一张对比清单。

## 2026-11-08 实测原文（本账号，本轮 0 点）

  GET  /api/v1/models                316 条 = 221 条目录 + 95 条裸模型层 ID
                                     type_code=image 50 条，其中 14 条记录（13 个型号）已上架
  POST /api/v1/images/generations    {"model":"gpt-image-2.6","prompt":""}
                                     -> 422 prompt: String should have at least 1 character
  POST /api/v1/images/generations    {"model":"flux-2-flex","prompt":""}
                                     -> 404 HTML（网关 SPA 兜底：目录里有这个型号，路由没有）
  POST /api/v1/images/generations    {"model":"qwen-image-3.0","prompt":""}
                                     -> 502 百炼提交失败，流水先 reserve_sync -20 再 refund +20，净 0
  GET  /api/v1/tasks/probe-no-such-task
                                     -> 200 {"code":0,"msg":"任务不存在"}
  GET  /api/v1/pricing               -> 115 条规则，没有 /api/v1/images/* 这一条
  GET  /user/balance/logs            最近 1000 条里 images/generations 共 73 条（71 笔结算）：
                                     -6 x43 / -10.54 x11 / -10.6 x7 / -13.78 x5 / -12 / -7.8 / -4 x2

## 单价从哪来（价目表里没有）

图片线按「型号」计次，`/api/v1/pricing` 里没有这条路径的专属规则，所以单价只能反推：

  1. GET /api/v1/me/tasks 按 model 归集 actualPrice（免费，source=live）
  2. 没跑过的型号用同路成交区间 4 - 13.78 点/张（source=baseline，预算按上界）
  3. 每跑成功一次，下一次报价就换成你自己的成交价

## 子命令

  catalog  图片模型清单：单价 / 来源 / 是否已上架（免费）
  cost     同一句 prompt 多模型逐个报价（免费）
  doctor   自检 7 个只读端点 + 422 探针 + 余额（免费，0 点）
  gen      多模型出图（要 --yes，受 --budget 管）
  status   查任务（免费，只走 GET /api/v1/tasks/<id>）
  sheet    用 manifest 生成对比清单（免费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --models gpt-image-2.6,seedream-5-0-flash,gpt-image-2 --n 2
  python3 scripts/run.py gen  --models gpt-image-2.6,seedream-5-0-flash --prompt "雨夜街头" --yes
  python3 scripts/run.py status --task-id task_xxx

Key：`--key` -> 环境变量 `A7W_API_KEY` -> `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import base64
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

# ── GBK 编码兜底（家族统一写法）──────────────────────────────────────────────
# Windows 上 stdout 走管道/重定向时用 cp936，个别符号编不出来就 UnicodeEncodeError。
# 先 reconfigure(errors="replace") 兜底；本包全文只用 cp936 覆盖得到的字符：
#   √ × · 「」 与中文标点；金额写「元」或全角 ￥，两种都在 cp936 里。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
IMAGE_PATH = API_PREFIX + "/images/generations"
TASKS_PATH = API_PREFIX + "/tasks"
DEFAULT_MODEL = "gpt-image-2.6"
DEFAULT_MODELS = ["gpt-image-2.6", "seedream-5-0-flash", "gpt-image-2"]
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 200
PAGE_SIZE = 20
MAX_PAGES = 70
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "image-models-ledger.json")
PRICE_CACHE = os.path.join(os.path.expanduser("~"), ".a7w", "image-models-prices.json")
CACHE_TTL = 6 * 3600
DEFAULT_PAGES = 10

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-image-models/%s" % VERSION

# ── 型号基线：每条都带证据，不是拍出来的 ────────────────────────────────────
# low/high 单位「点/张」；layer=model 表示走 /api/v1/tasks 或 /images/generations 记账，
# layer=app 表示这条是应用层同型号成交价，只作参考。
MODEL_BASELINE = {
    "gpt-image-2.6": dict(low=6.0, high=6.0, n=43, layer="model",
                          ev="本账号流水 sync:/api/v1/images/generations 43 笔各 -6"),
    "gpt-image-2": dict(low=26.0, high=26.0, n=1, layer="model",
                        ev="me/tasks actualPrice 26.00（path /api/v1/tasks）"),
    "gpt-image-2-pro": dict(low=39.0, high=104.0, n=17, layer="model",
                            ev="me/tasks actualPrice 39 / 78 / 104（17 笔）"),
    "seedream-5-0-flash": dict(low=15.6, high=15.6, n=1, layer="model",
                               ev="me/tasks actualPrice 15.60（path /api/v1/tasks）"),
    "nano-banana-2": dict(low=72.0, high=72.0, n=3, layer="app",
                          ev="应用层 nano_banana submit 72 点/次（3 笔）"),
    "nano-banana-pro": dict(low=72.0, high=72.0, n=14, layer="app",
                            ev="应用层 nano_banana submit 72 点/次（14 笔）"),
    "qwen-image-3.0-pro": dict(low=105.0, high=105.0, n=16, layer="app",
                               ev="应用层 aigc_photo_restore 105 点/张（16 笔）"),
}

# 同一条图片路径的成交区间（本账号最近 1000 条流水里的 70 笔，剔除 1 笔 199.9998 异常）
IMAGE_BAND = dict(low=4.0, high=13.78, n=70,
                  ev="images/generations 70 笔成交：-4 / -6 / -7.8 / -10.54 / -10.6 / -12 / -13.78")

# 目录里已上架的图片型号（channel_code 不是 official 的那批，2026-11-08 现查 50 条里的 14 条记录）
STATIC_READY = [
    ("gpt-image-2.6", "GPT Image 2.6", 6, "OpenAIYI"),
    ("gpt-image-2", "GPT Image 2", 12, "OpenAIYI"),
    ("gpt-image-2-fast", "GPT Image 2 Fast", 12, "openaiD"),
    ("gpt-image-2-pro", "GPT Image 2 Pro", 12, "OpenaiM"),
    ("gpt-image-2-vip", "GPT Image 2 VIP", 12, "OpenAIYI"),
    ("gpt-image-2.5", "GPT Image 2.5", 12, "OpenAIYI"),
    ("gpt-image-2.5-flare", "GPT Image 2.5 Flare", 12, "OpenAIYI"),
    ("gpt-image-2.5-sunburst", "GPT Image 2.5 Sunburst", 12, "OpenAIYI"),
    ("nano-banana-2", "Nano-Banana 2", 12, "Google"),
    ("nano-banana-2.1", "Nano-Banana 2.1", 10, "Google"),
    ("nano-banana-pro", "Nano-Banana Pro", 12, "Google"),
    ("qwen-image-3.0", "Qwen Image 3.0", 3, "dashscope_compatible"),
    ("qwen-image-3.0-pro", "Qwen Image 3.0 Pro", 3, "dashscope_compatible"),
]
STATIC_READY_CODES = [x[0] for x in STATIC_READY]

# gpt-image 系的自定义尺寸四条硬约束
SIZE_PRESETS = ("auto", "1k", "2k", "4k")
SIZE_REASON = ("宽高都是 16 的倍数 / 长边短边不超过 3:1 / 单边不超过 3840 / "
               "总像素 655,360 - 8,294,400")

DONE = ("completed", "complete", "done", "success", "succeeded")
FAILED = ("failed", "error", "canceled", "cancelled", "timeout", "refunded")


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


def http_json(method, url, key, body=None, timeout=120):
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise Fail("call", "连不上 %s：%s" % (url, e.reason), EXIT_CALL)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


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
                return s[:300]
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:300]
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


def fmt_pts(n):
    """点数显示：整数不带小数，10.54 这种保留两位。"""
    try:
        f = float(n)
    except Exception:                                            # noqa: BLE001
        return "-"
    if abs(f - round(f)) < 1e-9:
        return "{:,}".format(int(round(f)))
    return "{:,.2f}".format(f)


def money(points):
    """点 -> 元字符串。金额一律写「元」或全角 ￥。"""
    try:
        return "%.2f 元" % (float(points) / POINTS_PER_YUAN)
    except Exception:                                            # noqa: BLE001
        return "-"


def _w(s):
    """显示宽度：中文算 2 列，表格才对得齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def cache_load(pages):
    """本机价格缓存：省掉每次重扫 me/tasks（一次 10 页要几十秒）。"""
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


def check_size(size):
    """gpt-image 系自定义尺寸。返回 (ok, 原因)。"""
    if not size or size in SIZE_PRESETS:
        return True, ""
    if "x" not in size.lower():
        return False, "size 只能是 auto / 1k / 2k / 4k / 宽x高"
    try:
        w, h = [int(x) for x in size.lower().split("x", 1)]
    except Exception:                                            # noqa: BLE001
        return False, "size 格式不对：%s" % size
    if w % 16 or h % 16:
        return False, "宽高都要是 16 的倍数（%dx%d）" % (w, h)
    lo, hi = min(w, h), max(w, h)
    if hi > 3 * lo:
        return False, "长边与短边比例要在 3:1 以内（%dx%d）" % (w, h)
    if max(w, h) > 3840:
        return False, "单边要在 3840 以内（%dx%d）" % (w, h)
    px = w * h
    if px < 655360 or px > 8294400:
        return False, "总像素要在 655,360 - 8,294,400 之间（当前 %d）" % px
    return True, ""


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


def layer_of(paths):
    ps = [p or "" for p in (paths or [])]
    if ps and all(p.startswith(API_PREFIX + "/apps/") for p in ps):
        return "app"
    return "model"


class Ctx(object):
    """一次调用的共享缓存。所有 GET 免费，写请求只在 gen 里发一次。"""

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
            self._models = [dict(model_code=c, model_name=n, max_reference_images=r,
                                 channel_code=ch, type_code="image")
                            for c, n, r, ch in STATIC_READY]
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

    def image_models(self):
        """去重后的图片型号；同一个 code 有多条记录时保留已上架的那条。"""
        out, by_code = [], {}
        for m in self.models():
            if m.get("type_code") != "image":
                continue
            code = m.get("model_code")
            if not code:
                continue
            if code in by_code:
                i = by_code[code]
                if out[i].get("channel_code") == "official" and m.get("channel_code") != "official":
                    out[i] = m
                continue
            by_code[code] = len(out)
            out.append(m)
        return out

    def pricing(self):
        if self._pricing is None:
            st, txt = http_json("GET", self.host + API_PREFIX + "/pricing", self.key, timeout=60)
            self.requests += 1
            d = jloads(txt) or {}
            if st != 200 or not isinstance(d.get("pricing"), dict):
                raise Fail("call", "价目表拉取失败（HTTP %s）：%s"
                           % (st, err_text(st, txt)), EXIT_CALL)
            self._pricing = d
        return self._pricing

    def agg(self, pages):
        """GET /api/v1/me/tasks 按 model 归集 actualPrice（免费）。

        分页固定 20 条一页，一次 10 页要几十秒，所以本机存 6 小时缓存；
        `--refresh` 强制重扫，`--pages` 加大窗口。
        """
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
        for pg in range(1, pages + 1):
            if pages >= 6 and pg in (1, pages // 2, pages):
                say("  扫任务台账第 %d / %d 页（免费）…" % (pg, pages))
            st, txt = http_json("GET", self.host + API_PREFIX + "/me/tasks?limit=2000&page=%d" % pg,
                                self.key, timeout=40)
            self.requests += 1
            if st != 200:
                break
            d = jloads(txt) or {}
            ts = d.get("tasks") or []
            if not ts:
                break
            for t in ts:
                m = (t.get("model") or "").strip()
                if not m:
                    continue
                try:
                    v = float(t.get("actualPrice") or 0)
                except Exception:                                # noqa: BLE001
                    continue
                if v <= 0:
                    continue
                a = agg.setdefault(m, {"vals": [], "paths": set()})
                a["vals"].append(round(v, 2))
                a["paths"].add(t.get("path") or "")
            if len(ts) < PAGE_SIZE:
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


def price_of(ctx, model, agg):
    """单价：先看自己流水（live），再看基线（baseline）。返回 dict。"""
    live = (agg or {}).get(model)
    if live and live.get("vals"):
        vals = sorted(live["vals"])
        return dict(low=vals[0], high=vals[-1], n=len(vals), source="live",
                    layer=layer_of(live.get("paths")),
                    ev="%d 笔 actualPrice" % len(vals))
    b = MODEL_BASELINE.get(model)
    if b:
        return dict(low=b["low"], high=b["high"], n=b.get("n", 0),
                    source="baseline", layer=b.get("layer", "model"),
                    ev=b.get("ev", ""))
    return dict(low=IMAGE_BAND["low"], high=IMAGE_BAND["high"], n=IMAGE_BAND["n"],
                source="baseline", layer="band", ev=IMAGE_BAND["ev"])


def ready_of(model, live):
    if live and live.get("vals"):
        return True
    b = MODEL_BASELINE.get(model)
    if b and b.get("layer") == "model":
        return True
    return model in STATIC_READY_CODES


def note_of(pr):
    if pr["layer"] == "app":
        return "应用层成交价（同型号参考）"
    if pr["source"] == "live":
        return "本账号 %s 笔成交" % pr["n"]
    if pr["layer"] == "band":
        return "同路 %d 笔区间，预算按上界" % pr["n"]
    return "本账号流水 %s 笔" % pr["n"]


def gate_common(a, ctx, models, n, size, prompt_required=False):
    """报价与出图共用的预检：型号、目录、尺寸。返回 (rows, total_high)。"""
    if not models:
        raise Fail("usage", "至少给一个型号：--models a,b,c 或 --model a（列目录用 catalog）",
                   EXIT_USAGE)
    if prompt_required and not (a.prompt or "").strip():
        raise Fail("usage", "必须给 --prompt（一句画面描述）", EXIT_USAGE)
    if not (1 <= int(n) <= 4):
        raise Fail("usage", "n 只能是 1-4（默认 1）", EXIT_USAGE)
    catalog = {}
    offline = not ctx.online()
    if not offline:
        for m in ctx.image_models():
            catalog[m.get("model_code")] = m
    unknown = [m for m in models if catalog and m not in catalog]
    if unknown:
        raise Fail("usage", "目录里没有这些型号：%s（用 catalog 看现查清单）"
                   % "、".join(unknown), EXIT_USAGE)
    agg = ctx.agg(getattr(a, "pages", DEFAULT_PAGES))
    rows = []
    for m in models:
        meta = catalog.get(m) or {}
        pr = price_of(ctx, m, agg)
        pr.update(model=m, name=meta.get("model_name") or m,
                  refs=meta.get("max_reference_images"),
                  channel=meta.get("channel_code") or "")
        pr["ready"] = ready_of(m, agg.get(m))
        pr["note"] = note_of(pr)
        if str(m).lower().startswith("gpt-image"):
            ok, why = check_size(size)
            if not ok:
                raise Fail("usage", "尺寸不合法：%s（%s）" % (why, SIZE_REASON), EXIT_USAGE)
        rows.append(pr)
    rows.sort(key=lambda r: (r["high"], r["low"], r["model"]))
    total = sum(float(r["high"]) * int(n) for r in rows)
    return rows, total


# ───────────────────────── catalog ─────────────────────────
def cmd_catalog(a, key, host):
    ctx = Ctx(key, host, a)
    models = ctx.image_models()
    agg = ctx.agg(getattr(a, "pages", DEFAULT_PAGES)) if ctx.online() else {}
    rows = []
    for m in models:
        code = m.get("model_code")
        pr = price_of(ctx, code, agg)
        row = dict(model=code, name=m.get("model_name") or code,
                   refs=m.get("max_reference_images"), channel=m.get("channel_code") or "",
                   low=pr["low"], high=pr["high"], source=pr["source"], layer=pr["layer"],
                   ready=ready_of(code, agg.get(code)), note=note_of(pr))
        rows.append(row)
    rows.sort(key=lambda r: (not r["ready"], r["high"], r["model"]))
    shown = rows if a.all else [r for r in rows if r["ready"]]
    out = {"ok": True, "total": len(rows),
           "ready": sum(1 for r in rows if r["ready"]),
           "waiting": sum(1 for r in rows if not r["ready"]),
           "online": ctx.online(), "models": shown,
           "note": "单价来自 me/tasks 的 actualPrice；没跑过的型号用同路成交区间，标 source=baseline"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("文生图模型清单（%s）" % ("GET /api/v1/models 现查" if ctx.online() else "离线基线"))
    print("  图片型号 %d 个 · 已上架 %d 个 · 待验证 %d 个%s"
          % (out["total"], out["ready"], out["waiting"],
             " · 单价读本机缓存" if ctx.cached else ""))
    print()
    print("  %s %s %s %s %s %s" % (
        pad("model", 26), pad("名称", 20), pad("参考图", 7),
        pad("单价（点/张）", 15), pad("来源", 8), "状态"))
    print("  " + "-" * 100)
    for r in shown:
        span = pnum(r["low"]) if r["low"] == r["high"] else "%s-%s" % (
            pnum(r["low"]), pnum(r["high"]))
        print("  %s %s %s %s %s %s" % (
            pad(r["model"][:26], 26), pad((r["name"] or "")[:20], 20),
            pad(r["refs"] if r["refs"] is not None else "-", 7),
            pad(span, 15), pad("实测" if r["source"] == "live" else "基线", 8),
            "可调用" if r["ready"] else "目录待验证"))
    print()
    if not a.all:
        print("  只列可调用的 %d 个；--all 把目录里 %d 个图片型号全列出来（含待验证的）。"
              % (len(shown), len(rows)))
    print("  1 元 = 100 点。单价按张，n 张就是 n 倍。")
    return 0


# ───────────────────────── cost ─────────────────────────
def cmd_cost(a, key, host):
    models = parse_models(a.models) or DEFAULT_MODELS
    ctx = Ctx(key, host, a)
    rows, total = gate_common(a, ctx, models, a.n, a.size)
    lo = min(float(r["low"]) for r in rows)
    hi = max(float(r["high"]) for r in rows)
    spread = (hi / lo) if lo else 0.0
    out = {"ok": True, "models": rows, "n": a.n, "size": a.size,
           "totalPoints": round(total, 2), "totalYuan": round(total / POINTS_PER_YUAN, 2),
           "cheapest": rows[0]["model"] if rows else None,
           "spread": round(spread, 2), "online": ctx.online(),
           "note": "预算是按每个型号的上界单价 x n 相加；实际以扣费流水为准"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("同一句 prompt，%d 个型号逐个报价（1 元 = 100 点）" % len(rows))
    print("=" * 88)
    print("  %s %s %s %s %s %s" % (
        pad("型号", 26), pad("单价（点/张）", 15), pad("来源", 8),
        pad("参考图", 7), pad("%d 张合计" % a.n, 11), "口径"))
    print("  " + "-" * 84)
    for r in rows:
        span = pnum(r["low"]) if r["low"] == r["high"] else "%s-%s" % (
            pnum(r["low"]), pnum(r["high"]))
        print("  %s %s %s %s %s %s" % (
            pad(r["model"][:26], 26), pad(span, 15),
            pad("实测" if r["source"] == "live" else "基线", 8),
            pad(r["refs"] if r["refs"] is not None else "-", 7),
            pad("%s 点" % fmt_pts(float(r["high"]) * a.n), 11), r["note"]))
    print()
    print("  合计（按上界）：%s 点 = %s" % (fmt_pts(total), money(total)))
    print("  最便宜 %s · 最贵 %s 的单价相差 %.1f 倍"
          % (rows[0]["model"], rows[-1]["model"], spread))
    print("  选一个：gen --models %s；全跑：gen --models %s"
          % (rows[0]["model"], ",".join(r["model"] for r in rows)))
    if ctx.cached:
        print()
        print("  单价来自本机缓存（6 小时内）；--refresh 强制重扫 me/tasks。")
    if not ctx.online():
        print()
        print("  离线模式：只用了基线价。带上 Key 跑一次，这里会换成你自己账号的成交价。")
    return 0


# ───────────────────────── doctor ─────────────────────────
def cmd_doctor(a, key, host):
    if not key:
        raise Fail("usage", "doctor 需要一个 API Key：--key / A7W_API_KEY / a7w.py login",
                   EXIT_USAGE)
    ctx = Ctx(key, host, a)
    checks = []

    models, img, ready = [], [], 0
    try:
        models = ctx.models()
        img = ctx.image_models()
        ready = sum(1 for m in img if ready_of(m.get("model_code"), None))
        checks.append(("模型目录 GET /api/v1/models", len(models) >= 300,
                       "HTTP 200 · 共 %d 条 · 图片型号 %d 个（已上架 %d）"
                       % (len(models), len(img), ready)))
    except Fail as e:
        checks.append(("模型目录 GET /api/v1/models", False, e.message[:70]))

    try:
        st, txt = http_json("GET", host + API_PREFIX + "/me/tasks?limit=2000&page=1",
                            key, timeout=40)
        d = jloads(txt) or {}
        checks.append(("任务台账 GET /api/v1/me/tasks", st == 200 and bool(d.get("tasks")),
                       "HTTP %s · 共 %s 条 · 本页 %d 条"
                       % (st, d.get("total"), len(d.get("tasks") or []))))
    except Fail as e:
        checks.append(("任务台账 GET /api/v1/me/tasks", False, e.message[:70]))

    try:
        pr = ctx.pricing()
        rules = pr.get("pricing") or {}
        wild = rules.get("*") or {}
        has_img = IMAGE_PATH in rules
        checks.append(("价目表 GET /api/v1/pricing", len(rules) >= 100 and not has_img,
                       "HTTP 200 · %d 条规则 · 图片路径%s · 通配保底 %s 点"
                       % (len(rules), "有" if has_img else "无", pnum(wild.get("minPoints")))))
    except Fail as e:
        checks.append(("价目表 GET /api/v1/pricing", False, e.message[:70]))

    # 只探 gpt-image-2.6：空 prompt 停在参数校验（422），不冻结、不扣费
    st, txt = http_json("POST", host + IMAGE_PATH, key,
                        {"model": DEFAULT_MODEL, "prompt": ""}, timeout=a.timeout)
    d = jloads(txt) or {}
    e = d.get("error") if isinstance(d.get("error"), dict) else {}
    msg = e.get("message") or err_text(st, txt)
    checks.append(("出图端点探针 %s（422 即正确）" % DEFAULT_MODEL,
                   st == 422 and "at least 1 character" in msg,
                   "HTTP %s · %s" % (st, msg[:54])))

    st, txt = http_json("GET", host + TASKS_PATH + "/probe-no-such-task", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("任务查询路由 GET /api/v1/tasks/<id>",
                   st == 200 and d.get("code") == 0,
                   "HTTP %s · %s" % (st, (d.get("msg") or "")[:30])))

    try:
        b = ctx.balance()
        checks.append(("余额 GET /user/balance", b.get("available_points") is not None,
                       "可用 %s 点 · 冻结 %s 点 · 1 元 = %s 点"
                       % (fmt_pts(b.get("available_points") or 0), fmt_pts(b.get("frozen") or 0),
                          b.get("rate"))))
    except Fail as e:
        checks.append(("余额 GET /user/balance", False, e.message[:70]))

    # 余额前后对比：本轮 0 点最直接的证据
    try:
        before = float(ctx.balance().get("available_points") or 0)
        st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
        d = jloads(txt) or {}
        after = float(d.get("available_points") or 0)
        delta = round(after - before, 6)
        checks.append(("余额前后对比（本轮 0 点）", abs(delta) < 1e-6,
                       "前 %s 点 -> 后 %s 点 · 差 %s 点 · 冻结 %s 点"
                       % (fmt_pts(before), fmt_pts(after), fmt_pts(delta),
                          fmt_pts(d.get("frozen") or 0))))
    except Fail as e:
        checks.append(("余额前后对比（本轮 0 点）", False, e.message[:70]))

    cnt, net = 0, 0.0
    try:
        st, txt = http_json("GET", host + "/user/balance/logs?limit=100", key, timeout=40)
        d = jloads(txt) or {}
        logs = d.get("logs") or []
        imgs = [x for x in logs if "images/generations" in (x.get("reference") or "")]
        cnt = len(imgs)
        lt = time.localtime()
        today0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) * 1000
        for x in imgs:
            if float(x.get("at") or 0) >= today0:
                net += float(x.get("points") or 0)
        checks.append(("流水 GET /user/balance/logs", st == 200 and bool(logs),
                       "HTTP %s · 最近 100 条里图片流水 %d 笔 · 今日图片线净 %s 点"
                       % (st, cnt, fmt_pts(net))))
    except Fail as e:
        checks.append(("流水 GET /user/balance/logs", False, e.message[:70]))

    out = {"ok": all(c[1] for c in checks), "requests": ctx.requests,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks],
           "todayImageNetPoints": net, "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（7 个只读端点 + 1 个 422 探针，全部免费）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 44), dd))
    print()
    print("  出图端点：POST %s%s（JSON，同步）" % (host, IMAGE_PATH))
    print("  单价：价目表里没有这条路径，实际单价看 me/tasks 的 actualPrice")
    print("  本轮花费 0 点：探针停在参数校验，没有建任务、没有冻结。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 图片落盘 ─────────────────────────
def _ext_of(raw, fallback="png"):
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:3] == b"\xff\xd8\xff":
        return "jpg"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return fallback


def save_b64(b64, path_base):
    raw = base64.b64decode(b64)
    p = "%s.%s" % (path_base, _ext_of(raw))
    with open(p, "wb") as fh:
        fh.write(raw)
    return p


def download(url, path_base, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as x:
        raw = x.read()
    p = "%s.%s" % (path_base, _ext_of(raw))
    with open(p, "wb") as fh:
        fh.write(raw)
    return p


def deep_urls(obj, out=None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("http") and (
                    k.endswith("url") or k.endswith("urls") or k in ("image", "images")):
                out.append(v)
            elif isinstance(v, (dict, list)):
                deep_urls(v, out)
    elif isinstance(obj, list):
        for it in obj:
            if isinstance(it, str) and it.startswith("http"):
                out.append(it)
            else:
                deep_urls(it, out)
    return out


def deep_cost(obj):
    if isinstance(obj, dict):
        for k in ("points_cost", "pointsCost", "actualPrice", "cost", "points"):
            v = obj.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                got = deep_cost(v)
                if got is not None:
                    return got
    elif isinstance(obj, list):
        for it in obj:
            got = deep_cost(it)
            if got is not None:
                return got
    return None


# ───────────────────────── status ─────────────────────────
def cmd_status(a, key, host):
    tid = (a.task_id or "").strip()
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    st, txt = http_json("GET", host + TASKS_PATH + "/" + tid, key, timeout=40)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    ok = st in (200, 201) and (d.get("code") != 0 or bool(data))
    out = {"ok": True, "taskId": tid, "http": st,
           "status": data.get("status") or d.get("status"),
           "images": deep_urls(data)[:12], "cost": deep_cost(data),
           "message": d.get("msg") or d.get("message") or ""}
    if not ok:
        raise Fail("call", "查不到任务 %s（HTTP %s）：%s" % (tid, st, err_text(st, txt)),
                   EXIT_CALL)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  状态：%s" % out["status"])
    if out["cost"] is not None:
        print("  点数：%s 点" % pnum(out["cost"]))
    for u in out["images"]:
        print("  图：%s（约 3 小时有效，及时转存）" % u)
    return 0


# ───────────────────────── gen ─────────────────────────
def _poll(key, host, tid, every, wait):
    deadline = time.time() + wait
    data, status = {}, ""
    while True:
        st, txt = http_json("GET", host + TASKS_PATH + "/" + tid, key, timeout=40)
        d = jloads(txt) or {}
        data = d.get("data") if isinstance(d.get("data"), dict) else {}
        status = (data.get("status") or d.get("status") or "").lower()
        if status in DONE or status in FAILED or time.time() > deadline:
            return data, status
        say("  %s 状态 %s，%d 秒后再查…" % (tid, status or "-", every))
        time.sleep(every)


def _save_one(d, outdir, base, idx, a):
    """同步返回的图落盘。返回 (files, source)。"""
    files, src = [], "none"
    data = d.get("data") if isinstance(d, dict) else None
    items = data if isinstance(data, list) else []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        b64 = it.get("b64_json")
        if b64:
            files.append(save_b64(b64, "%s-%02d" % (base, i + 1)))
            src = "b64_json"
            continue
        u = it.get("url")
        if u:
            try:
                files.append(download(u, "%s-%02d" % (base, i + 1)))
                src = "url"
            except Exception as e:                               # noqa: BLE001
                say("  下载失败：%s: %s" % (type(e).__name__, e))
    return files, src


def _write_manifest(run_dir, man, rows):
    io.open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(man, ensure_ascii=False, indent=1))
    lines = ["# 对比清单 · %s" % (man.get("runId") or "-"), "",
             "prompt：%s" % (man.get("prompt") or "-"), "",
             "张数：每型号 %s 张 · 尺寸：%s" % (man.get("n") or 1, man.get("size") or "auto"), "",
             "| 型号 | 状态 | 单价（点/张） | 来源 | 用时 | 出图 | 实际点数 |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %ss | %d | %s |" % (
            r["model"], r["status"],
            pnum(r["unitPoints"]) if r.get("unitPoints") is not None else "-",
            "实测" if r.get("source") == "live" else "基线",
            r.get("elapsed") or "-", len(r.get("files") or []),
            pnum(r.get("actualPoints")) if r.get("actualPoints") is not None else "-"))
    lines.append("")
    lines.append("合计预估 %s 点，实际 %s 点。" % (
        pnum(man.get("totalEstimated")), pnum(man.get("totalActual"))))
    lines.append("")
    for r in rows:
        if r.get("files"):
            lines.append("## %s" % r["model"])
            for f in r["files"]:
                lines.append("- %s" % os.path.basename(f))
            lines.append("")
    io.open(os.path.join(run_dir, "对比清单.md"), "w", encoding="utf-8",
            newline="\n").write("\n".join(lines) + "\n")


def cmd_gen(a, key, host):
    if not key:
        raise Fail("usage", "gen 需要 API Key：--key / A7W_API_KEY / a7w.py login",
                   EXIT_USAGE)
    models = parse_models(a.models) or parse_models(a.model)
    if not models:
        raise Fail("usage",
                   "给要跑的型号：--models gpt-image-2.6,seedream-5-0-flash（列目录用 catalog）",
                   EXIT_USAGE)
    ctx = Ctx(key, host, a)
    rows, total = gate_common(a, ctx, models, a.n, a.size, prompt_required=True)
    not_ready = [r["model"] for r in rows if not r["ready"]]
    if not_ready and not a.allow_any_model:
        ready_list = [m for m in STATIC_READY_CODES if m in
                      {x.get("model_code") for x in ctx.image_models()}]
        raise Fail("usage",
                   "这些型号在目录里还是待验证状态：%s。\n"
                   "已上架、可直接跑的：%s\n"
                   "确定要试的型号加 --allow-any-model，或者先跑 catalog 看一眼。"
                   % ("、".join(not_ready), "、".join(ready_list[:8])),
                   EXIT_USAGE)
    if total > a.budget:
        raise Fail("budget", "预计 %s 点（%s）超过 --budget %d 点。"
                   "这一条只读了免费台账，一个出图请求都没发。"
                   "调大 --budget 或减型号 / 减 n。"
                   % (fmt_pts(total), money(total), a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实出图：%d 个型号 x %d 张，按上界约 %s 点（%s）。确认请加 --yes。"
                   % (len(rows), a.n, fmt_pts(total), money(total)), EXIT_CONFIRM)

    bodies = []
    for r in rows:
        body = {"model": r["model"], "prompt": a.prompt, "n": a.n}
        if a.size and a.size != "auto":
            body["size"] = a.size
        if a.output_format and a.output_format != "png":
            body["output_format"] = a.output_format
        if a.want_url:
            body["response_format"] = "url"
        bodies.append((r, body))

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "n": a.n, "size": a.size,
               "models": [{"model": r["model"], "unitPoints": r["high"],
                           "source": r["source"], "estimatedPoints": round(r["high"] * a.n, 2)}
                          for r, _ in bodies],
               "estimatedPoints": round(total, 2), "totalYuan": round(total / POINTS_PER_YUAN, 2),
               "requests": [{"url": host + IMAGE_PATH, "body": b} for _, b in bodies]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（一个请求都不发，不扣费）")
        for r, b in bodies:
            print("  -> POST %s%s" % (host, IMAGE_PATH))
            print("     %s" % json.dumps(b, ensure_ascii=False))
            print("     %s · %s 点/张 · 预计 %s 点"
                  % (r["model"], pnum(r["high"]), fmt_pts(r["high"] * a.n)))
        print("  合计：%s 点（%s）" % (fmt_pts(total), money(total)))
        return 0

    run_id = time.strftime("%Y%m%d-%H%M%S")
    outdir = os.path.abspath(a.outdir or ".")
    run_dir = os.path.join(outdir, "run-" + run_id)
    os.makedirs(run_dir, exist_ok=True)
    results = []
    for seq, (r, body) in enumerate(bodies, 1):
        model = r["model"]
        say("正在出图 %d/%d：%s（%s，%d 张）…" % (seq, len(bodies), model, r["source"], a.n))
        t0 = time.time()
        res = dict(model=model, status="failed", source=r["source"],
                   unitPoints=r["high"], files=[], actualPoints=None,
                   taskId=None, error=None, elapsed=0.0)
        try:
            st, txt = http_json("POST", host + IMAGE_PATH, key, body,
                                timeout=max(180, a.timeout))
            d = jloads(txt) or {}
            data = d.get("data") if isinstance(d.get("data"), dict) else {}
            task_id = data.get("task_id") or data.get("taskId") or d.get("task_id") or d.get("taskId")
            base = os.path.join(run_dir, "%02d-%s" % (seq, model_slug(model)))
            if st in (200, 201) and isinstance(d.get("data"), list) and d["data"]:
                files, src = _save_one(d, run_dir, base, seq, a)
                res.update(status="ok" if files else "no_image", files=files,
                           actualPoints=deep_cost(d), returned=len(d["data"]))
            elif st in (200, 201) and task_id:
                res["taskId"] = task_id
                say("  异步任务 %s，查询只走 GET /api/v1/tasks/<id>（免费）" % task_id)
                info, status = _poll(key, host, task_id, a.every, a.wait)
                urls = deep_urls(info)
                files = []
                for i, u in enumerate(urls[:a.n]):
                    try:
                        files.append(download(u, "%s-%02d" % (base, i + 1)))
                    except Exception as e:                       # noqa: BLE001
                        say("  下载失败：%s: %s" % (type(e).__name__, e))
                res.update(status=status or "unknown", files=files,
                           actualPoints=deep_cost(info), returned=len(urls))
            else:
                res["status"] = "failed"
                res["error"] = err_text(st, txt)
        except Fail as e:
            res["error"] = e.message
        except Exception as e:                                   # noqa: BLE001
            res["error"] = "%s: %s" % (type(e).__name__, e)
        res["elapsed"] = round(time.time() - t0, 1)
        if res.get("source") == "baseline" and res.get("actualPoints"):
            res["learnedFrom"] = "本次 actualPrice"
        results.append(res)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "gen",
                    "model": model, "n": a.n, "size": a.size, "status": res["status"],
                    "files": len(res["files"]), "actualPoints": res["actualPoints"],
                    "estimatedPoints": round(r["high"] * a.n, 2), "elapsed": res["elapsed"],
                    "runId": run_id})

    ok_results = [x for x in results if x["status"] == "ok"]
    actual_total = sum(float(x["actualPoints"] or 0) for x in results)
    man = dict(runId=run_id, at=time.strftime("%Y-%m-%dT%H:%M:%S"), prompt=a.prompt,
               n=a.n, size=a.size, outdir=run_dir, results=results,
               totalEstimated=round(total, 2),
               totalActual=round(actual_total, 2) if actual_total else None)
    _write_manifest(run_dir, man, results)
    out = {"ok": bool(ok_results), "runId": run_id, "dir": run_dir, "n": a.n,
           "size": a.size, "results": results,
           "totalEstimated": round(total, 2), "totalActual": round(actual_total, 2) if actual_total else None,
           "manifest": os.path.join(run_dir, "manifest.json"),
           "sheet": os.path.join(run_dir, "对比清单.md")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok_results else EXIT_CALL
    print()
    print("出图结果（%d/%d 个型号成功）" % (len(ok_results), len(results)))
    print("  %-26s %-10s %-8s %-8s %-10s %s" % ("型号", "状态", "用时", "出图", "实际点数", "文件名"))
    print("  " + "-" * 92)
    for x in results:
        f = os.path.basename(x["files"][0]) if x["files"] else (x.get("error") or "-")
        print("  %-26s %-10s %-8s %-8d %-10s %s" % (
            x["model"][:26], x["status"], "%ss" % x["elapsed"],
            len(x["files"]), pnum(x["actualPoints"]) if x["actualPoints"] is not None else "-",
            str(f)[:40]))
    print()
    print("  落盘目录：%s" % run_dir)
    print("  对比清单：%s" % out["sheet"])
    print("  合计：预估 %s 点，实际 %s 点"
          % (fmt_pts(total), fmt_pts(actual_total) if actual_total else "见流水"))
    return 0 if ok_results else EXIT_CALL


# ───────────────────────── sheet ─────────────────────────
def cmd_sheet(a, key, host):
    path = a.manifest
    run_dir = a.run
    if run_dir and not path:
        path = os.path.join(run_dir, "manifest.json")
    if not path or not os.path.isfile(path):
        raise Fail("usage", "给 --run 目录或 --manifest manifest.json 路径", EXIT_USAGE)
    man = json.load(io.open(path, encoding="utf-8"))
    rows = man.get("results") or []
    run_dir = os.path.dirname(os.path.abspath(path))
    _write_manifest(run_dir, man, rows)
    out = {"ok": True, "runId": man.get("runId"), "dir": run_dir,
           "models": [{"model": x.get("model"), "status": x.get("status"),
                       "files": len(x.get("files") or []),
                       "actualPoints": x.get("actualPoints")} for x in rows]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("对比清单已生成：%s" % os.path.join(run_dir, "对比清单.md"))
    print("  %-26s %-10s %-6s %s" % ("型号", "状态", "出图", "实际点数"))
    for x in rows:
        print("  %-26s %-10s %-6d %s" % (
            str(x.get("model"))[:26], x.get("status"),
            len(x.get("files") or []),
            pnum(x.get("actualPoints")) if x.get("actualPoints") is not None else "-"))
    return 0


# ───────────────────────── log ─────────────────────────
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
        print("  %s %-6s %-26s %-8s %2d 张 %s 点 %.1fs" % (
            e.get("at"), e.get("status"), str(e.get("model"))[:26],
            e.get("size") or "-", e.get("n") or 0,
            pnum(e.get("actualPoints")) if e.get("actualPoints") is not None else "-",
            e.get("elapsed") or 0))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 文生图模型台：一个 prompt，多模型先报价再出图",
        epilog="端点：POST %s/api/v1/images/generations（出图）· GET %s/api/v1/tasks/<id>（查任务，0 点）· "
               "GET %s/api/v1/me/tasks（单价反推，0 点）· GET %s/api/v1/models（型号，0 点）"
               % ((DEFAULT_HOST,) * 4),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 2 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    def add_gate(p):
        p.add_argument("--yes", action="store_true", help="确认真实出图并扣点")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，一个都不发")

    p = sub.add_parser("catalog", help="图片模型清单：单价 / 来源 / 是否已上架（免费）",
                       allow_abbrev=False)
    p.add_argument("--all", action="store_true", help="连目录里待验证的型号一起列")
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页 = %d 条）" % (DEFAULT_PAGES, DEFAULT_PAGES * PAGE_SIZE))
    p.add_argument("--refresh", action="store_true", help="忽略本机价格缓存，重扫 me/tasks")
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="多模型逐个报价（免费）", allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔的型号，默认 %s" % ",".join(DEFAULT_MODELS))
    p.add_argument("--n", type=int, default=1, help="每个型号出几张 1-4（默认 1）")
    p.add_argument("--size", default="auto", help="auto / 1k / 2k / 4k / 宽x高（默认 auto）")
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页）" % DEFAULT_PAGES)
    p.add_argument("--refresh", action="store_true", help="忽略本机价格缓存，重扫 me/tasks")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检端点 / 单价来源 / 余额（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("gen", help="多模型出图（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔的型号，例如 gpt-image-2.6,seedream-5-0-flash")
    p.add_argument("--model", help="只跑一个型号（--models 的单数写法）")
    p.add_argument("--prompt", help="提示词，所有型号共用同一句")
    p.add_argument("--n", type=int, default=1, help="每个型号出几张 1-4（默认 1）")
    p.add_argument("--size", default="auto", help="auto / 1k / 2k / 4k / 宽x高（默认 auto）")
    p.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"],
                   help="输出格式（默认 png）")
    p.add_argument("--want-url", action="store_true", help="让网关返回 url（默认 b64 落盘）")
    p.add_argument("--outdir", default=".", help="落盘根目录（默认当前目录）")
    p.add_argument("--allow-any-model", action="store_true",
                   help="跳过「目录待验证」预检，把型号直接交给上游")
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页）" % DEFAULT_PAGES)
    p.add_argument("--refresh", action="store_true", help="忽略本机价格缓存，重扫 me/tasks")
    p.add_argument("--timeout", type=int, default=240, help="单次请求超时秒数（默认 240）")
    p.add_argument("--every", type=int, default=5, help="异步任务轮询间隔秒数（默认 5）")
    p.add_argument("--wait", type=int, default=600, help="异步任务最长等待秒数（默认 600）")
    add_gate(p)
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("status", help="查任务（免费，只走 GET /api/v1/tasks/<id>）",
                       allow_abbrev=False)
    p.add_argument("--task-id", help="异步出图返回的 task id")
    p.set_defaults(fn=cmd_status)

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


# 不需要 Key 的子命令（只是读不到线上数据，会退回离线基线）
OFFLINE_OK = ("cmd_catalog", "cmd_cost", "cmd_log", "cmd_sheet")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
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
