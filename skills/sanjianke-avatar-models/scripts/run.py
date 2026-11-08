#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 数字人模型台（sanjianke-avatar-models）

一句话：同一张图 + 同一段音频，让 5 个数字人模型先各报一次价，再决定跑哪一个。

## 2026-11-08 实测原文（本账号，免费探针，0 点）

  GET  /api/v1/models
       316 条 = 221 条目录模型 + 95 条裸模型层 ID
       数字人相关 8 个 ID（全部 type_code=other）：
         omnihuman-2-0                        数字人驱动（图 + 音频）
         omnihuman-1-5                        数字人驱动（图 + 音频 + 可选 mask）
         infinitalk-from-audio                音频驱动口播（图 + 音频）
         kling-ai-avatar-standard             数字人口播（图 + 音频）
         kling-ai-avatar-pro                  数字人口播（图 + 音频）
         omnihuman-1-5-human-identification   主体识别（前置，图）
         omnihuman-1-5-subject-detection      主体检测（前置，图）
         volcengine-video-to-video-lip-sync   视频对口型（视频 + 音频）

  POST /api/v1/videos/generations  {"model":"omnihuman-2-0"}
       -> 400 {"error":"prompt or content field is required","type":"invalid_request_error"}
     其余 7 个数字人 ID 逐条相同：全部 400 prompt or content field is required。
     这条返回说明「路由认这个型号、参数校验拦下」，不建任务、不冻结。

  POST /api/v1/videos  {"model":"omnihuman-2-0"}
       -> 404 {"error":{"code":"model_not_found",
                "message":"The model `omnihuman-2-0` does not exist ..."}}
     目录里的数字人型号走 /videos 会 404，只有 4 个裸视频 ID 认这条。

  POST /api/v1/videos/generations  {}   -> 400 model field is required
  GET  /api/v1/tasks/probe-no-such-task -> 200 {"code":0,"msg":"任务不存在"}

  探针前后：余额 999,997,393,470.2579 -> 999,997,393,470.2579（差 0 点）；
  流水最新一条时间戳 1794100561106 未变（total 7885）。

## 字段名不统一（逐条读 /api/v1/models 的 material_capabilities 得到的）

  omnihuman-2-0    图片字段是 image_urls（数组，1 张）
  omnihuman-1-5    图片字段是 image_url（单值），另有 mask_url（0-5）
  infinitalk / kling-ai-avatar-*   图片字段是 image_url
  volcengine-video-to-video-lip-sync  视频字段是 video_url
  音频统一 audio_url。

  把 omnihuman-2-0 的图传成 image_url，会被上游当成「缺图」；
  本包按型号自动切换字段名，不让人肉记。

## 单价从哪来（价目表里没有模型层）

  GET /api/v1/pricing 115 条规则，没有 /api/v1/videos/generations，
  也没有 modelPricing 键。模型层命中通配 *：
    {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
     "note":"未单独定价的接口：对外 = 上游实际点数 x 2，单笔保底 50 点"}

  所以模型层单价只能反推：
    1) GET /api/v1/me/tasks 按 model 归集 actualPrice（免费，source=live）
    2) 没跑过的型号按基线：上游数字人 2-12 点/秒 x 通配加价 100%
       = 4-24 点/秒，单笔保底 50 点（source=baseline）
    3) 跑成功一次，下一次报价自动换成你自己账号的成交价

  本账号 1,398 条台账里，模型层只有 7 个模型、43 笔成交
  （gpt-image 系 / muse-video / wan3.0 / seedance 1 个 / seedance 2.5 个），
  数字人模型层 0 笔 —— 所以这一轮 5 个模型全部标 baseline，不编单价。

## 应用层锚点（只比价，不提交）

  image_human   fast 10 / standard 15 / 2k 30 / 4k 60 点/输入秒
  pic_lipsync   15 点/秒，单笔保底 50 点
  lipsync       上游 x3：xiaojiayu1.0 2.7 点/秒，2.0 / 3.0 13.5 点/秒

  同一段 10 秒音频：应用层 100 - 600 点，模型层基线 50 - 240 点。

## 子命令

  catalog  8 个数字人 ID + 5 个可横评模型 + 3 个应用锚点（免费）
  cost     同一段音频多模型逐个报价，按上界排序（免费）
  doctor   11 项自检：端点 / 字段 / 通配规则 / 余额前后 / 流水（免费，0 点）
  gen      同一张图 + 同一段音频，多模型提交并出对比清单（要 --yes，受 --budget 管）
  status   查任务（免费，只走 GET /api/v1/tasks/<id>）
  sheet    用 manifest 重新生成对比清单（免费）
  log      本地台账（免费）

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --models omnihuman-2-0,kling-ai-avatar-pro --seconds 10
  python3 scripts/run.py doctor
  python3 scripts/run.py gen --models omnihuman-2-0,infinitalk-from-audio \\
      --image face.png --audio speech.mp3 --upload --wait --yes
  python3 scripts/run.py status --task-id task_xxx

Key：`--key` -> 环境变量 `A7W_API_KEY` -> `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import io
import json
import mimetypes
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid

# ── GBK 编码兜底（家族统一写法）──────────────────────────────────────────────
# Windows 上 stdout 走管道/重定向时用 cp936，个别符号编不出来就 UnicodeEncodeError。
# 先 reconfigure(errors="replace") 兜底；本包正文只用 cp936 覆盖得到的字符：
#   √ × · → 「」 与中文标点。金额一律写「元」，不用 cp936 编不出的窄体日元符号。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
MODELS_PATH = API_PREFIX + "/models"
PRICING_PATH = API_PREFIX + "/pricing"
GEN_PATH = API_PREFIX + "/videos/generations"
VIDEOS_PATH = API_PREFIX + "/videos"
TASKS_PATH = API_PREFIX + "/tasks"
UPLOAD_PATH = API_PREFIX + "/upload"

POINTS_PER_YUAN = 100
DEFAULT_SECONDS = 10
DEFAULT_BUDGET = 2000            # 单位：点 = 20 元；够默认 5 个模型各跑一条（按上界）
DEFAULT_PAGES = 10               # 每页 20 条；默认扫 200 条
PAGE_SIZE_ME = 20
MAX_PAGES = 70
WILDCARD_MIN = 50                # 通配规则：单笔保底 50 点
BASE_LOW_PER_SEC = 4             # 上游数字人 2 点/秒 x 通配加价 100%
BASE_HIGH_PER_SEC = 24           # 上游数字人 12 点/秒 x 通配加价 100%

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "avatar-models-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-avatar-models/%s" % VERSION

DEFAULT_PROMPT = "人物面对镜头自然口播，口型与表情跟着音频，画面稳定，半身构图"

# ── 5 个可横评的音频驱动数字人模型（全部实测停在 400 prompt required）──────────
# imageField：该型号要的图片字段名（omnihuman-2-0 是数组 image_urls，其余是 image_url）
# probe：2026-11-08 在 /videos/generations 上「只带 model、缺 prompt」的真实返回
MODELS = {
    "omnihuman-2-0": dict(
        name="OmniHuman 2.0", vendor="字节 OmniHuman", imageField="image_urls",
        op="数字人驱动", refs=1,
        note="一张图 + 一段音频出全身表情动作；图片字段是 image_urls 数组",
        probe="400 prompt or content field is required"),
    "omnihuman-1-5": dict(
        name="OmniHuman 1.5", vendor="字节 OmniHuman", imageField="image_url",
        op="数字人驱动", refs=1,
        note="表情、口型、头部动作一起动；另收 mask_url（0-5）做局部处理",
        probe="400 prompt or content field is required"),
    "infinitalk-from-audio": dict(
        name="Infinitalk 音频驱动", vendor="Infinitalk", imageField="image_url",
        op="音频驱动口播", refs=1,
        note="长音频口播稳，人物一致性优先",
        probe="400 prompt or content field is required"),
    "kling-ai-avatar-standard": dict(
        name="Kling AI Avatar Standard", vendor="可灵 Kling", imageField="image_url",
        op="数字人口播", refs=1,
        note="可灵数字人标准档，画面质感稳，适合日常口播",
        probe="400 prompt or content field is required"),
    "kling-ai-avatar-pro": dict(
        name="Kling AI Avatar Pro", vendor="可灵 Kling", imageField="image_url",
        op="数字人口播", refs=1,
        note="可灵数字人 Pro 档，细节与运镜更好，单价更高",
        probe="400 prompt or content field is required"),
}
MODEL_ORDER = ["omnihuman-2-0", "omnihuman-1-5", "infinitalk-from-audio",
               "kling-ai-avatar-standard", "kling-ai-avatar-pro"]
DEFAULT_MODELS = list(MODEL_ORDER)

# ── 前置 2 个 + 视频对口型 1 个（catalog 里标清楚，不混进出片横评）──────────────
PRE_STEPS = {
    "omnihuman-1-5-human-identification": dict(
        name="Omnihuman 1.5 主体识别", op="主体识别",
        note="先认出肖像里的人物信息，给后续驱动用；只吃图，不出视频"),
    "omnihuman-1-5-subject-detection": dict(
        name="Omnihuman 1.5 主体检测", op="主体检测",
        note="检测主体并回蒙版，给后续局部处理用；只吃图，不出视频"),
}
VIDEO_LANE = {
    "volcengine-video-to-video-lip-sync": dict(
        name="Volcengine 视频对口型", vendor="火山引擎", op="视频对口型",
        imageField="video_url", refs=0, video=True,
        note="已有视频 + 新音频换口型；对应应用层 lipsync 的模型层走法",
        probe="400 prompt or content field is required"),
}
QUOTABLE = dict(MODELS)
QUOTABLE.update(VIDEO_LANE)

# 8 个数字人 ID（5 可横评 + 2 前置 + 1 视频对口型）
ALL_DH_IDS = set(MODELS) | set(PRE_STEPS) | set(VIDEO_LANE)

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
    """GET 只读；POST 只在 gen / 免费探针里出现。5xx 退避重试，4xx 原样返回。"""
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
        except urllib.error.URLError as e:
            last = e
            if attempt < retries - 1:
                time.sleep(1 + attempt)
                continue
            raise Fail("call", "连不上 %s：%s" % (url, getattr(e, "reason", e)), EXIT_CALL)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


def http_multipart(url, key, fields, files, timeout=600):
    boundary = "----sanjianke" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, val in fields.items():
        if val is None:
            continue
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                   % (boundary, name, val)).encode("utf-8"))
    for name, path in files:
        fn = os.path.basename(path)
        ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                   "Content-Type: %s\r\n\r\n" % (boundary, name, fn, ctype)).encode("utf-8"))
        with open(path, "rb") as fh:
            buf.write(fh.read())
        buf.write(b"\r\n")
    buf.write(("--%s--\r\n" % boundary).encode("utf-8"))
    payload = buf.getvalue()
    req = urllib.request.Request(url, method="POST", data=payload, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json",
        "Content-Type": "multipart/form-data; boundary=" + boundary,
        "Content-Length": str(len(payload)), "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise Fail("call", "连不上 %s：%s" % (url, e.reason), EXIT_CALL)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


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
    """点 -> 元字符串。金额一律写「元」，不用 cp936 编不出的窄体日元符号。"""
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


class Ctx(object):
    """一次调用的共享缓存。所有 GET 免费；写请求只在 gen 里发。"""

    def __init__(self, key, host, a):
        self.key, self.host, self.a = key, host, a
        self._models = None
        self._pricing = None
        self._agg = None
        self._balance = None
        self.requests = 0

    def online(self):
        return bool(self.key)

    def models(self):
        if self._models is not None:
            return self._models
        if not self.key:
            self._models = []
            return self._models
        st, txt = http_json("GET", self.host + MODELS_PATH, self.key, timeout=60)
        self.requests += 1
        d = jloads(txt) or {}
        data = d.get("data")
        if st != 200 or not isinstance(data, list):
            raise Fail("call", "模型目录拉取失败（HTTP %s）：%s"
                       % (st, err_text(st, txt)), EXIT_CALL)
        self._models = data
        return self._models

    def dh_models(self):
        return [m for m in self.models() if m.get("model_code") in ALL_DH_IDS]

    def pricing(self):
        if self._pricing is None:
            st, txt = http_json("GET", self.host + PRICING_PATH, self.key, timeout=60)
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
        agg = {}
        for pg in range(1, min(int(pages), MAX_PAGES) + 1):
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
        self._agg = agg
        return agg

    def balance(self):
        if self._balance is None:
            st, txt = http_json("GET", self.host + "/user/balance", self.key, timeout=40)
            self.requests += 1
            if st != 200:
                raise Fail("call", "余额接口失败（HTTP %s）：%s"
                           % (st, err_text(st, txt)), EXIT_CALL)
            self._balance = jloads(txt) or {}
        return self._balance


def quote_of(model, seconds, agg):
    """报价：先账号流水（live），再按秒基线（baseline）。模型层没有价目表价。"""
    seconds = max(1, int(seconds or DEFAULT_SECONDS))
    live = (agg or {}).get(model)
    if live and live.get("vals"):
        vals = sorted(live["vals"])
        return dict(low=vals[0], high=vals[-1], n=len(vals), source="live",
                    gate=float(vals[-1]), rate=None,
                    basis="你账号 %d 笔成交（/api/v1/me/tasks 的 actualPrice）" % len(vals),
                    note="实测成交区间")
    low = max(WILDCARD_MIN, BASE_LOW_PER_SEC * seconds)
    high = max(WILDCARD_MIN, BASE_HIGH_PER_SEC * seconds)
    return dict(low=float(low), high=float(high), n=0, source="baseline",
                gate=float(high), rate=None,
                basis="基线：上游数字人 2-12 点/秒 x 通配加价 100% = 4-24 点/秒，"
                      "单笔保底 50 点",
                note="该型号在你这儿 0 笔成交，预算按上界")


def quote_line(q):
    if abs(float(q["low"]) - float(q["high"])) < 1e-9:
        return "%s 点" % pnum(q["low"])
    return "%s - %s 点" % (pnum(q["low"]), pnum(q["high"]))


def source_cn(q):
    return {"live": "实测", "baseline": "基线", "rate": "官方单价"}.get(q["source"], "基线")


def app_anchors(ctx, seconds):
    """应用层锚点：同一段音频走应用层要多少点。只比价，不提交。"""
    sec = max(1, int(seconds or DEFAULT_SECONDS))
    rates = {"fast": 10, "standard": 15, "2k": 30, "4k": 60}
    pic_rate, pic_min = 15, 50
    lip = {"xiaojiayu1.0": 2.7, "xiaojiayu2.0": 13.5, "xiaojiayu3.0": 13.5}
    src = "本机常量（2026-11-08 版）"
    if ctx.online():
        try:
            rules = (ctx.pricing().get("pricing") or {})
            r = rules.get(API_PREFIX + "/apps/image_human/submit") or {}
            mr = r.get("modelRates") or {}
            got = {}
            for k, v in mr.items():
                if isinstance(v, dict) and v.get("*") is not None:
                    got[k] = float(v["*"])
            if got:
                rates = dict((k, got.get(k, rates[k])) for k in rates)
                src = "GET /api/v1/pricing（现查）"
        except Fail:
            pass
    rows = []
    for mode in ("fast", "standard", "2k", "4k"):
        rows.append(dict(lane="image_human %s" % mode, app="image_human",
                         rate=rates[mode], unit="点/输入秒", sameInput=True,
                         points=round(float(rates[mode]) * sec, 2),
                         note="全驱动数字人，图 + 音频"))
    rows.append(dict(lane="pic_lipsync", app="pic_lipsync", rate=pic_rate,
                     unit="点/秒（保底 50）", sameInput=True,
                     points=round(max(pic_min, float(pic_rate) * sec), 2),
                     note="图片数字人，文案或音频驱动"))
    for k in ("xiaojiayu1.0", "xiaojiayu2.0"):
        rows.append(dict(lane="lipsync %s" % k, app="lipsync", rate=lip[k],
                         unit="点/秒（上游 x3）", sameInput=False,
                         points=round(float(lip[k]) * sec, 2),
                         note="已有视频换口型（输入是视频，不参与同图报价池）"))
    return rows, src


def resolve(a, models):
    if not models:
        raise Fail("usage", "至少给一个型号：--models a,b,c（列全部用 catalog）", EXIT_USAGE)
    unknown = [m for m in models if m not in QUOTABLE]
    if unknown and not getattr(a, "allow_any_model", False):
        raise Fail("usage",
                   "本包还没有这些型号的基线：%s。\n"
                   "可横评的 5 个：%s\n"
                   "另有视频对口型 1 个：%s\n"
                   "确定要试别的型号加 --allow-any-model（按同一条基线报价）。"
                   % ("、".join(unknown), "、".join(MODEL_ORDER),
                      "、".join(VIDEO_LANE)),
                   EXIT_USAGE)
    return models


# ───────────────────────── catalog ─────────────────────────
def cmd_catalog(a, key, host):
    ctx = Ctx(key, host, a)
    agg = ctx.agg(a.pages) if ctx.online() else {}
    rows = []
    for m in MODEL_ORDER:
        meta = MODELS[m]
        q = quote_of(m, a.seconds, agg)
        rows.append(dict(model=m, name=meta["name"], vendor=meta["vendor"],
                         op=meta["op"], imageField=meta["imageField"],
                         refs=meta["refs"], low=q["low"], high=q["high"],
                         source=q["source"], n=q["n"], note=meta["note"],
                         probe=meta["probe"], route=GEN_PATH))
    anchors, anchor_src = app_anchors(ctx, a.seconds)
    found = [m.get("model_code") for m in (ctx.dh_models() if ctx.online() else [])]
    out = {"ok": True, "seconds": a.seconds, "models": rows,
           "preSteps": [dict(model=k, name=v["name"], op=v["op"], note=v["note"])
                        for k, v in PRE_STEPS.items()],
           "videoLane": [dict(model=k, name=v["name"], op=v["op"], note=v["note"],
                              route=GEN_PATH) for k, v in VIDEO_LANE.items()],
           "appAnchors": anchors, "appAnchorSource": anchor_src,
           "digitalHumanIdsFound": sorted(found), "digitalHumanIdCount": len(ALL_DH_IDS),
           "online": ctx.online(), "pointsPerYuan": POINTS_PER_YUAN,
           "note": "模型层单价来自 me/tasks 的 actualPrice；0 笔成交按 4-24 点/秒基线，"
                   "标 source=baseline"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("数字人模型台 · 8 个数字人 ID / 5 个可横评模型（1 元 = 100 点）")
    print("  价格来源：%s" % ("你账号的 /api/v1/me/tasks" if ctx.online() else "离线基线"))
    print("  目录命中：%s"
          % ("离线（未读到 Key，按基线报价）" if not ctx.online()
             else "%d / %d 个数字人 ID%s"
             % (len(found), len(ALL_DH_IDS),
                "" if len(found) == len(ALL_DH_IDS)
                else "（缺 %s）" % "、".join(sorted(ALL_DH_IDS - set(found))))))
    print()
    print("  可横评：同一张图 + 同一段 %d 秒音频" % a.seconds)
    print("  %s %s %s %s %s" % (pad("model", 40), pad("报价（点）", 18),
                                pad("来源", 8), pad("图片字段", 14), "一句话"))
    print("  " + "-" * 110)
    for r in rows:
        print("  %s %s %s %s %s" % (
            pad(r["model"][:40], 40), pad(quote_line(q_of(r)), 18),
            pad(source_cn(r), 8), pad(r["imageField"], 14), r["note"]))
    print()
    print("  前置 2 个（只吃图，不出视频，横评时先别选）")
    for k, v in PRE_STEPS.items():
        print("    %-38s %s" % (k, v["note"]))
    print()
    print("  视频对口型 1 个（要 --video，不要 --image）")
    for k, v in VIDEO_LANE.items():
        print("    %-38s %s" % (k, v["note"]))
    print()
    print("  应用层锚点（只比价，本包不提交；同一段 %d 秒音频）" % a.seconds)
    print("    %s %s %s" % (pad("路线", 22), pad("单价", 22, False), "折合"))
    for r in anchors:
        print("    %s %s %s 点%s" % (pad(r["lane"], 22),
                                     pad("%s %s" % (pnum(r["rate"]), r["unit"]), 22, False),
                                     pnum(r["points"]),
                                     "" if r.get("sameInput") else " *"))
    print("    * 输入是已有视频，只做参考，不计入同图报价池")
    print()
    print("  提交路径：POST %s（8 个数字人 ID 全部认这条；%s 会 404）"
          % (GEN_PATH, VIDEOS_PATH))
    print("  单价来源：%s" % anchor_src)
    print("  下一步：python3 scripts/run.py cost --seconds %d" % a.seconds)
    return 0


def q_of(row):
    """catalog 行 -> quote_of 形状（便于复用 quote_line / source_cn）。"""
    return dict(low=row["low"], high=row["high"], source=row["source"])


# ───────────────────────── cost ─────────────────────────
def cmd_cost(a, key, host):
    models = resolve(a, parse_models(a.models) or DEFAULT_MODELS)
    ctx = Ctx(key, host, a)
    agg = ctx.agg(a.pages) if ctx.online() else {}
    rows = []
    for m in models:
        q = quote_of(m, a.seconds, agg)
        meta = QUOTABLE.get(m) or {}
        rows.append(dict(model=m, name=meta.get("name") or m,
                         route=GEN_PATH, low=q["low"], high=q["high"], n=q["n"],
                         source=q["source"], gate=q["gate"], basis=q["basis"],
                         note=meta.get("note") or "", video=bool(meta.get("video"))))
    anchors, anchor_src = app_anchors(ctx, a.seconds)
    total = sum(float(r["gate"]) for r in rows)
    ok = sorted(rows, key=lambda r: (r["gate"], r["low"]))
    same = [x for x in anchors if x.get("sameInput")]
    pool_low = min([float(r["low"]) for r in rows] + [float(x["points"]) for x in same])
    pool_high = max([float(r["high"]) for r in rows] + [float(x["points"]) for x in same])
    spread = (pool_high / pool_low) if pool_low else 0.0
    out = {"ok": True, "models": ok, "seconds": a.seconds,
           "totalPoints": round(total, 2), "totalYuan": round(total / POINTS_PER_YUAN, 2),
           "cheapest": ok[0]["model"] if ok else None,
           "mostExpensive": ok[-1]["model"] if ok else None,
           "appAnchors": anchors, "appAnchorSource": anchor_src,
           "poolLow": round(pool_low, 2), "poolHigh": round(pool_high, 2),
           "spread": round(spread, 2), "online": ctx.online(),
           "pointsPerYuan": POINTS_PER_YUAN,
           "note": "合计按每个型号的上界相加；模型层 0 笔成交按 4-24 点/秒基线，"
                   "跑过一次自动换 live"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("同一张图 + 同一段 %d 秒音频，%d 个模型逐个报价（1 元 = 100 点，按上界排序）"
          % (a.seconds, len(ok)))
    print("=" * 100)
    print("  %s %s %s %s %s" % (pad("model", 40), pad("报价（点）", 18),
                                pad("来源", 8), pad("闸门", 8), "口径"))
    print("  " + "-" * 96)
    for r in ok:
        print("  %s %s %s %s %s" % (
            pad(r["model"][:40], 40), pad(quote_line(r), 18), pad(source_cn(r), 8),
            pad(pnum(r["gate"]), 8), r["basis"][:44]))
    print()
    print("  合计（按上界）：%s 点 = %s" % (pnum(total), money(total)))
    print("  同一张图 + 同一段音频的报价池：最低 %s 点 · 最高 %s 点 · 相差 %.1f 倍"
          % (pnum(pool_low), pnum(pool_high), spread))
    print("  （lipsync 的输入是视频，只列在下面做参考，不计入这个倍数）")
    print()
    print("  应用层锚点（同一段 %d 秒音频，只比价，不提交）" % a.seconds)
    print("    %s %s %s" % (pad("路线", 22), pad("单价", 22, False), "折合"))
    for r in anchors:
        print("    %s %s %s 点%s" % (pad(r["lane"], 22),
                                     pad("%s %s" % (pnum(r["rate"]), r["unit"]), 22, False),
                                     pnum(r["points"]),
                                     "" if r.get("sameInput") else " *"))
    print("    * 输入是已有视频，只做参考，不计入同图报价池")
    print("  锚点来源：%s" % anchor_src)
    print()
    print("  选一个：gen --models %s --image face.jpg --audio speech.mp3 --yes"
          % ok[0]["model"])
    print("  全跑横评：gen --models %s --image face.jpg --audio speech.mp3 --yes"
          % ",".join(r["model"] for r in ok))
    print("  --seconds 只影响报价与预算闸门；模型按音频实际时长结算。")
    return 0


# ───────────────────────── doctor ─────────────────────────
def cmd_doctor(a, key, host):
    if not key:
        raise Fail("usage", "doctor 需要一个 API Key：--key / A7W_API_KEY / a7w.py login",
                   EXIT_USAGE)
    ctx = Ctx(key, host, a)
    checks = []

    def probe(method, path, body=None, timeout=None):
        ctx.requests += 1
        return http_json(method, host + path, key, body, timeout=timeout or a.timeout)

    # 0) 探针前先记一笔流水（total + 最新 at），结束时对比，证明本轮 0 条新增
    logs0 = None
    try:
        st0, txt0 = probe("GET", "/user/balance/logs?limit=1", timeout=40)
        d0 = jloads(txt0) or {}
        lg0 = (d0.get("logs") or [{}])[0]
        logs0 = {"total": d0.get("total"), "at": lg0.get("at"),
                 "reference": lg0.get("reference")}
    except Fail as e:
        checks.append(("流水基线 GET /user/balance/logs", False, e.message[:70]))

    # 1) 模型目录 + 8 个数字人 ID 在位
    try:
        all_models = ctx.models()
        found = [m.get("model_code") for m in ctx.dh_models()]
        missing = sorted(ALL_DH_IDS - set(found))
        checks.append(("模型目录 GET /api/v1/models（数字人 8 个 ID）",
                       len(all_models) >= 300 and not missing,
                       "HTTP 200 · 共 %d 条 · 数字人 %d 个%s"
                       % (len(all_models), len(found),
                          "" if not missing else " · 缺 " + "、".join(missing))))
    except Fail as e:
        checks.append(("模型目录 GET /api/v1/models", False, e.message[:70]))

    # 2) 价目表：模型层没有专属规则，通配保底 50 点
    try:
        pr = ctx.pricing()
        rules = pr.get("pricing") or {}
        wild = rules.get("*") or {}
        has_gen = GEN_PATH in rules
        has_model_pricing = "modelPricing" in pr
        checks.append(("价目表 GET /api/v1/pricing（模型层无专属规则）",
                       len(rules) >= 100 and not has_gen and not has_model_pricing,
                       "HTTP 200 · %d 条规则 · %s模型层规则 · 通配保底 %s 点 / 加价 %s%%"
                       % (len(rules),
                          "表里有" if (has_gen or has_model_pricing) else "表里没有",
                          pnum(wild.get("minPoints")), pnum(wild.get("markupPercent")))))
    except Fail as e:
        checks.append(("价目表 GET /api/v1/pricing", False, e.message[:70]))

    # 3) 任务台账：数字人有几笔真实成交（这就是报价的数据源）
    try:
        st, txt = probe("GET", API_PREFIX + "/me/tasks?limit=2000&page=1", timeout=40)
        d = jloads(txt) or {}
        agg = {}
        for t in (d.get("tasks") or []):
            m = (t.get("model") or "").strip()
            if m in QUOTABLE and float(t.get("actualPrice") or 0) > 0:
                agg[m] = agg.get(m, 0) + 1
        checks.append(("任务台账 GET /api/v1/me/tasks（数字人成交样本）",
                       st == 200 and isinstance(d.get("tasks"), list),
                       "HTTP %s · 共 %s 条 · 数字人模型层 %d 笔（0 笔就按基线报价）"
                       % (st, pnum(d.get("total")), sum(agg.values()))))
    except Fail as e:
        checks.append(("任务台账 GET /api/v1/me/tasks", False, e.message[:70]))

    # 4) 空 body -> 400 model field is required（停在校验层）
    st, txt = probe("POST", GEN_PATH, {})
    msg = err_text(st, txt)
    checks.append(("提交端点 POST %s 存在（空 body 400）" % GEN_PATH,
                   st == 400 and "model field is required" in msg,
                   "HTTP %s · %s" % (st, msg[:52])))

    # 5/6) 合法 model + 缺 prompt -> 400，不建任务、不冻结
    for m in ("omnihuman-2-0", "infinitalk-from-audio"):
        st, txt = probe("POST", GEN_PATH, {"model": m})
        msg = err_text(st, txt)
        checks.append(("型号可提交 %s（缺 prompt 400）" % m,
                       st == 400 and "prompt" in msg.lower(),
                       "HTTP %s · %s" % (st, msg[:48])))

    # 7) 路由分工：目录型号打 /videos 会 404
    st, txt = probe("POST", VIDEOS_PATH, {"model": "omnihuman-2-0"})
    d7 = jloads(txt) or {}
    code7 = (d7.get("error") or {}).get("code") if isinstance(d7.get("error"), dict) else ""
    checks.append(("路由分工：/videos 不认 omnihuman-2-0（404 model_not_found）",
                   st == 404 and code7 == "model_not_found",
                   "HTTP %s · %s" % (st, code7 or err_text(st, txt)[:40])))

    # 8) 查询路由：假 taskId -> code 0「任务不存在」，免费
    st, txt = probe("GET", TASKS_PATH + "/probe-no-such-task", timeout=40)
    d8 = jloads(txt) or {}
    checks.append(("查询路由 GET /api/v1/tasks/<id> 可用（假 id 回任务不存在）",
                   st == 200 and d8.get("code") == 0,
                   "HTTP %s · %s" % (st, str(d8.get("msg") or "")[:24])))

    # 9) 余额可读 + 再采一次（用于第 11 项解释变动）
    before = 0.0
    after_val = 0.0
    try:
        b = ctx.balance()
        before = float(b.get("available_points") or 0)
        after_val = before
        checks.append(("余额 GET /user/balance", b.get("available_points") is not None,
                       "可用 %s 点 · 冻结 %s 点 · 1 元 = %s 点"
                       % (pnum(before), pnum(b.get("frozen") or 0), b.get("rate"))))
    except Fail as e:
        checks.append(("余额 GET /user/balance", False, e.message[:70]))
    try:
        st, txt = probe("GET", "/user/balance", timeout=40)
        after_val = float((jloads(txt) or {}).get("available_points") or 0)
    except Fail:
        pass

    # 10) 流水：本包视频线新增 0 条 + 视频线今日净额；外部流水单独统计
    net, cnt, latest = 0.0, 0, None
    delta = round(after_val - before, 6)
    video_new, other_new, other_points = [], [], 0.0
    total_after = None
    logs_ok = False
    d = {}
    try:
        st, txt = probe("GET", "/user/balance/logs?limit=100", timeout=40)
        d = jloads(txt) or {}
        logs = d.get("logs") or []
        total_after = d.get("total")
        logs_ok = st == 200 and bool(logs)
        base_at = float((logs0 or {}).get("at") or 0)
        lt = time.localtime()
        today0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) * 1000
        for x in logs:
            blob = " ".join(str(x.get(k) or "") for k in
                            ("reference", "path", "note", "model", "taskId")).lower()
            is_video = any(w in blob for w in ("/videos", "videos/generations",
                                               "omnihuman", "infinitalk",
                                               "kling-ai-avatar", "avatar"))
            at = float(x.get("at") or 0)
            pts = float(x.get("points") or 0)
            if is_video:
                cnt += 1
                if at >= today0:
                    net += pts
            if at > base_at:
                if is_video:
                    video_new.append(x)
                else:
                    other_new.append(x)
                    other_points += pts
        if logs:
            latest = logs[0].get("at")
        # ⚠️ 这里只断言「**本包**没新增视频线任务」。
        # 全局「今日视频线净额」会受**同账号其它会话**影响（实测今天就出现过 -165 点），
        # 拿它当通过条件是错的设计 —— 那会把别人的花费算成本包的失败。
        checks.append(("流水：本包视频线新增 0 条",
                       logs_ok and not video_new,
                       "总流水 %s -> %s · 新增 %d 条（本包视频线 %d 条 / 外部 %d 条）"
                       " · 视频线今日净 %s 点（含外部，仅供参考）"
                       % (pnum((logs0 or {}).get("total")), pnum(total_after),
                          len(video_new) + len(other_new), len(video_new),
                          len(other_new), pnum(net))))
    except Fail as e:
        checks.append(("流水 GET /user/balance/logs", False, e.message[:70]))

    # 11) 余额变动必须能全部由外部流水解释；本包 0 点
    explained = logs_ok and abs(delta - other_points) < 0.01 and not video_new
    checks.append(("余额变动全部来自外部流水（本包 0 点）", explained,
                   "前 %s -> 后 %s · 差 %s 点 = 外部 %d 条流水 %s 点 + 本包 0 点"
                   % (pnum(before), pnum(after_val), pnum(delta),
                      len(other_new), pnum(other_points))))

    out = {"ok": all(c[1] for c in checks), "requests": ctx.requests,
           "endpoint": host + GEN_PATH, "fallback": host + VIDEOS_PATH,
           "query": host + TASKS_PATH + "/<id>", "todayVideoNetPoints": round(net, 2),
           "balanceBefore": before, "balanceAfter": after_val, "latestLogAt": latest,
           "logsBefore": logs0,
           "logsAfter": {"total": total_after, "at": latest},
           "videoLineNewEntries": len(video_new),
           "externalNewEntries": len(other_new),
           "externalPoints": round(other_points, 2),
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks],
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（只读 GET + 免费探针 + 余额前后对比，全部停在校验层）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 54), dd))
    print()
    print("  主路：POST %s（8 个数字人 ID 都停在这个 400）" % (host + GEN_PATH))
    print("  分工：POST %s 只认 4 个裸视频 ID（数字人型号会 404）" % (host + VIDEOS_PATH))
    print("  查询：GET  %s/<id>（免费，轮询只走这条）" % (host + TASKS_PATH))
    print("  报价：GET  %s%s/me/tasks（免费，actualPrice 反推）" % (host, API_PREFIX))
    if abs(delta) < 1e-6:
        print("  本轮花费 0 点：余额 %s 未变；本包视频线新增 0 条。" % pnum(before))
    elif explained:
        print("  本包花费 0 点：视频线新增 0 条；账户余额 %s -> %s，差 %s 点全部来自"
              "外部 %d 条流水（%s 点）。"
              % (pnum(before), pnum(after_val), pnum(delta),
                 len(other_new), pnum(other_points)))
    else:
        print("  本包视频线新增 0 条；账户余额 %s -> %s，差 %s 点（外部 %d 条 %s 点，"
              "差异未能完全解释）。"
              % (pnum(before), pnum(after_val), pnum(delta),
                 len(other_new), pnum(other_points)))
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 素材 ─────────────────────────
def upload_file(host, key, path, timeout=600):
    say("  上传 %s（POST /api/v1/upload，0 点）…" % os.path.basename(path))
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [("file", path)], timeout=timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    url = data.get("url")
    if st not in (200, 201) or not url:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    say("  已上传：%s（24 小时内有效）" % url)
    return url


def materialize(a, key, host, value, label, dry):
    v = (value or "").strip()
    if re.match(r"^https?://", v, re.I):
        return v
    if not os.path.isfile(v):
        raise Fail("usage", "%s 既不是 http(s) 地址，也不是存在的文件：%s" % (label, v),
                   EXIT_USAGE)
    if not a.upload:
        raise Fail("usage",
                   "%s 是本地文件。加 --upload 先传到平台临时地址（上传 0 点），"
                   "或换成公网 http(s) 地址。" % label, EXIT_USAGE)
    if dry:
        return "<dry-run：本地文件 %s 未上传>" % os.path.basename(v)
    return upload_file(host, key, v)


# ───────────────────────── 请求体 ─────────────────────────
def build_body(a, model, image_url, audio_url, video_url):
    meta = QUOTABLE.get(model) or {}
    body = {"model": model, "prompt": (a.prompt or DEFAULT_PROMPT)}
    if meta.get("video"):
        body["video_url"] = video_url
    elif meta.get("imageField") == "image_urls":
        body["image_urls"] = [image_url]
    else:
        body["image_url"] = image_url
    body["audio_url"] = audio_url
    if a.extra:
        try:
            extra = json.loads(a.extra)
        except Exception:                                        # noqa: BLE001
            raise Fail("usage",
                       "--extra 要是 JSON 对象，例如 '{\"resolution\":\"1080p\"}'",
                       EXIT_USAGE)
        if not isinstance(extra, dict):
            raise Fail("usage", "--extra 要是 JSON 对象（当前是 %s）"
                       % type(extra).__name__, EXIT_USAGE)
        body.update(extra)
    return body


def check_inputs(a, models):
    if len(models) > 5:
        raise Fail("usage", "一次最多横评 5 个型号（当前 %d）；拆成两次更稳" % len(models),
                   EXIT_USAGE)
    if not (1 <= int(a.seconds) <= 180):
        raise Fail("usage", "--seconds 只支持 1 - 180 的整数（当前 %s）" % a.seconds,
                   EXIT_USAGE)
    if len(a.prompt or "") > 4000:
        raise Fail("usage", "--prompt 最多 4000 字（当前 %d）" % len(a.prompt), EXIT_USAGE)
    need_video = any((QUOTABLE.get(m) or {}).get("video") for m in models)
    need_image = any(not (QUOTABLE.get(m) or {}).get("video") for m in models)
    if need_image and not a.image:
        raise Fail("usage", "必须给 --image（人物图片 URL，或本地文件 + --upload）",
                   EXIT_USAGE)
    if need_video and not a.video:
        raise Fail("usage", "视频对口型型号需要 --video（已有视频 URL，或本地文件 + --upload）",
                   EXIT_USAGE)
    if not a.audio:
        raise Fail("usage", "必须给 --audio（驱动音频 URL，或本地文件 + --upload）",
                   EXIT_USAGE)


# ───────────────────────── status / wait ─────────────────────────
def _pick(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _dig_url(d):
    for src in (d, d.get("result") or {}, d.get("data") or {}, d.get("storage") or {}):
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
        for k in ("progress", "seconds", "duration", "size", "model", "fail_reason",
                  "refund", "reservePrice", "expires_at", "video_url_expires_at"):
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
           "seconds": d.get("seconds") or d.get("duration"),
           "videoUrl": d.get("url"), "cost": d.get("cost"),
           "message": d.get("message")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  状态：%s%s" % (d.get("status"),
                          "" if d.get("progress") is None else " · 进度 %s" % d.get("progress")))
    if d.get("model"):
        print("  型号：%s" % d.get("model"))
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


# ───────────────────────── 对比清单 ─────────────────────────
def _write_sheet(run_dir, man, rows):
    io.open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(man, ensure_ascii=False, indent=1))
    lines = ["# 一张图 + 一段音频 · 数字人模型横评 %s" % (man.get("runId") or "-"), "",
             "图片：%s" % (man.get("image") or "-"), "",
             "音频：%s" % (man.get("audio") or "-"), "",
             "参数：按 %s 秒报价 · 提交路径 POST %s"
             % (man.get("seconds") or "-", GEN_PATH), "",
             "| 模型 | 上界（点） | 来源 | 状态 | 实际（点） | 用时 | 成片 |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| `%s` | %s | %s | %s | %s | %ss | %s |" % (
            r.get("model"), pnum(r.get("gate")), r.get("sourceCn") or "-",
            r.get("status") or "-",
            pnum(r.get("actualPoints")) if r.get("actualPoints") is not None else "-",
            r.get("elapsed") or "-", r.get("file") or (r.get("error") or "-")))
    lines.append("")
    lines.append("合计预估（按上界）%s 点（%s），实际 %s。" % (
        pnum(man.get("totalEstimated")), money(man.get("totalEstimated") or 0),
        (pnum(man.get("totalActual")) + " 点") if man.get("totalActual") is not None
        else "见 /user/balance/logs"))
    lines.append("")
    anchors = man.get("anchors") or []
    if anchors:
        lines.append("## 同一段音频的应用层锚点（只比价，本包不提交）")
        lines.append("")
        lines.append("| 路线 | 单价 | %s 秒折合 |" % (man.get("seconds") or "-"))
        lines.append("|---|---|---|")
        for x in anchors:
            lines.append("| %s | %s %s | %s 点 |" % (
                x.get("lane"), pnum(x.get("rate")), x.get("unit"), pnum(x.get("points"))))
        lines.append("")
    lines.append("同一张图、同一段音频、同一句提示词，只有 model 不同 —— 这才是可比的横评。")
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
    check_inputs(a, models)

    # 第一道：先用基线报价拦预算。这一步一个请求都不发（严格 0 请求）。
    base_total = sum(float(quote_of(m, a.seconds, {})["gate"]) for m in models)
    if base_total > a.budget:
        raise Fail("budget",
                   "预计 %s 点（%s）超过 --budget %d 点。预算按每个型号的上界相加，"
                   "这一步一个请求都没发。调大 --budget（单位：点，1 元 = 100 点）或减型号。"
                   % (pnum(base_total), money(base_total), a.budget), EXIT_BUDGET)

    ctx = Ctx(key, host, a)
    agg = {} if a.dry_run else ctx.agg(a.pages)
    quotes = []
    for m in models:
        q = quote_of(m, a.seconds, agg)
        q["model"] = m
        q["sourceCn"] = source_cn(q)
        quotes.append(q)
    total = sum(float(q["gate"]) for q in quotes)

    # 第二道：有 live 成交价时重算一次；仍然只发了免费只读 GET。
    if total > a.budget:
        raise Fail("budget",
                   "按你账号的成交价重算，预计 %s 点（%s）超过 --budget %d 点。"
                   "只发了免费只读 GET，一个出片请求都没发。调大 --budget 或减型号。"
                   % (pnum(total), money(total), a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实出片：%d 个模型，按上界约 %s 点（%s）。"
                   "平台按音频时长预冻结，失败全额退回。确认请加 --yes。"
                   % (len(quotes), pnum(total), money(total)), EXIT_CONFIRM)

    if a.dry_run:
        reqs = []
        for q in quotes:
            meta = QUOTABLE.get(q["model"]) or {}
            body = {"model": q["model"], "prompt": a.prompt or DEFAULT_PROMPT}
            if meta.get("video"):
                body["video_url"] = a.video or "<--video>"
            elif meta.get("imageField") == "image_urls":
                body["image_urls"] = [a.image or "<--image>"]
            else:
                body["image_url"] = a.image or "<--image>"
            body["audio_url"] = a.audio or "<--audio>"
            reqs.append({"url": host + GEN_PATH, "body": body})
        out = {"ok": True, "dryRun": True, "seconds": a.seconds,
               "models": [{"model": q["model"], "gate": q["gate"], "source": q["source"],
                           "route": GEN_PATH} for q in quotes],
               "totalPoints": round(total, 2),
               "totalYuan": round(total / POINTS_PER_YUAN, 2),
               "requests": reqs}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（一个请求都不发，不冻结、不扣费）")
        for r in reqs:
            print("  -> POST %s" % r["url"])
            print("     %s" % json.dumps(r["body"], ensure_ascii=False)[:360])
        print("  合计：%s 点（%s）" % (pnum(total), money(total)))
        print("  本地文件在干跑里不真上传；去掉 --dry-run 再加 --upload 才会传（上传 0 点）。")
        return 0

    anchors, anchor_src = app_anchors(ctx, a.seconds)

    image_url = materialize(a, key, host, a.image, "--image", False) if a.image else None
    audio_url = materialize(a, key, host, a.audio, "--audio", False)
    video_url = materialize(a, key, host, a.video, "--video", False) if a.video else None

    run_id = time.strftime("%Y%m%d-%H%M%S")
    outdir = os.path.abspath(a.outdir or ".")
    run_dir = os.path.join(outdir, "run-" + run_id)
    os.makedirs(run_dir, exist_ok=True)
    results = []
    for seq, q in enumerate(quotes, 1):
        model = q["model"]
        body = build_body(a, model, image_url, audio_url, video_url)
        say("正在提交 %d/%d：%s（上界 %s 点）…" % (seq, len(quotes), model, pnum(q["gate"])))
        t0 = time.time()
        res = dict(model=model, status="failed", source=q["source"], sourceCn=q["sourceCn"],
                   gate=q["gate"], basis=q["basis"], route=GEN_PATH, taskId=None, file=None,
                   videoUrl=None, actualPoints=None, error=None, elapsed=0.0)
        try:
            st, txt = http_json("POST", host + GEN_PATH, key, body,
                                timeout=max(60, a.timeout))
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
                        if a.save:
                            base = os.path.join(run_dir, "%02d-%s" % (seq, model_slug(model)))
                            try:
                                res["file"] = os.path.basename(download(info["url"], base))
                            except Exception as e:               # noqa: BLE001
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
                    "model": model, "seconds": a.seconds,
                    "status": res["status"], "taskId": res["taskId"],
                    "gate": q["gate"], "actualPoints": res["actualPoints"],
                    "route": GEN_PATH, "elapsed": res["elapsed"]})

    ok_results = [x for x in results if x["taskId"]]
    actual_total = sum(float(x["actualPoints"] or 0) for x in results)
    man = dict(runId=run_id, at=time.strftime("%Y-%m-%dT%H:%M:%S"),
               image=image_url, audio=audio_url, video=video_url,
               prompt=a.prompt or DEFAULT_PROMPT, seconds=a.seconds,
               outdir=run_dir, results=results, anchors=anchors,
               appAnchorSource=anchor_src,
               totalEstimated=round(total, 2),
               totalActual=round(actual_total, 2) if actual_total else None)
    _write_sheet(run_dir, man, results)
    out = {"ok": bool(ok_results), "runId": run_id, "dir": run_dir,
           "seconds": a.seconds, "results": results,
           "totalEstimated": round(total, 2),
           "totalActual": round(actual_total, 2) if actual_total else None,
           "manifest": os.path.join(run_dir, "manifest.json"),
           "sheet": os.path.join(run_dir, "对比清单.md")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok_results else EXIT_CALL
    print()
    print("横评结果（%d/%d 个模型拿到任务）" % (len(ok_results), len(results)))
    print("  %s %s %s %s %s %s" % (pad("模型", 36), pad("状态", 12), pad("上界", 8),
                                    pad("实际", 8), pad("用时", 7), "成片 / 报错"))
    print("  " + "-" * 100)
    for x in results:
        print("  %s %s %s %s %s %s" % (
            pad(x["model"][:36], 36), pad(x["status"], 12), pad(pnum(x["gate"]), 8),
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
        print("  任务已提交，片子会自己跑完。逐个查（查任务免费）：")
        for x in results:
            if x["taskId"]:
                print("    python3 scripts/run.py status --task-id %s" % x["taskId"])
    return 0 if ok_results else EXIT_CALL


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
    print("  %s %s %s %s" % (pad("模型", 36), pad("状态", 12), pad("上界", 8), "实际点数"))
    for x in rows:
        print("  %s %s %s %s" % (
            pad(str(x.get("model"))[:36], 36), pad(x.get("status") or "-", 12),
            pad(pnum(x.get("gate")), 8),
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
        print("  %s %-10s %-36s %-10s 上界 %s 点 实际 %s 点 %.1fs" % (
            e.get("at"), e.get("status"), str(e.get("model"))[:36],
            e.get("taskId") or "-", pnum(e.get("gate")),
            pnum(e.get("actualPoints")) if e.get("actualPoints") is not None else "-",
            e.get("elapsed") or 0))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 数字人模型台：同一张图 + 同一段音频，5 个模型先报价再横评",
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

    p = sub.add_parser("catalog", help="8 个数字人 ID / 5 个模型 / 应用锚点（免费）",
                       allow_abbrev=False)
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="按多少秒报价（默认 %d）" % DEFAULT_SECONDS)
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页 = %d 条）"
                        % (DEFAULT_PAGES, DEFAULT_PAGES * PAGE_SIZE_ME))
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="同一段音频多模型逐个报价（免费）", allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔的型号，默认 5 个音频驱动模型")
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="音频多少秒（默认 %d，用于报价与预算）" % DEFAULT_SECONDS)
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页）" % DEFAULT_PAGES)
    p.add_argument("--allow-any-model", action="store_true",
                   help="型号不在清单里也允许报价（按同一条基线）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="11 项自检：端点 / 字段 / 余额 / 流水（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("gen", help="多模型横评出片（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔的型号，默认 5 个音频驱动模型")
    p.add_argument("--model", help="只跑一个型号（--models 的单数写法）")
    p.add_argument("--image", help="人物图片：http(s) 地址，或本地文件 + --upload")
    p.add_argument("--audio", help="驱动音频：http(s) 地址，或本地文件 + --upload")
    p.add_argument("--video", help="已有视频（只视频对口型型号用）")
    p.add_argument("--prompt", help="提示词，所有模型共用同一句")
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="音频秒数（默认 %d，只用于报价与预算）" % DEFAULT_SECONDS)
    p.add_argument("--extra", help="额外请求字段，JSON 对象，例如 '{\"resolution\":\"1080p\"}'")
    p.add_argument("--upload", action="store_true",
                   help="本地文件先传平台临时地址（POST /upload，0 点）")
    p.add_argument("--outdir", default=".", help="落盘根目录（默认当前目录）")
    p.add_argument("--wait", action="store_true", help="提交后等到完成")
    p.add_argument("--save", action="store_true", help="完成后把成片下载到 run 目录")
    p.add_argument("--every", type=int, default=10, help="轮询间隔秒数（默认 10）")
    p.add_argument("--limit", type=int, default=900, help="最长等待秒数（默认 900 = 15 分钟）")
    p.add_argument("--timeout", type=int, default=180, help="单次提交超时秒数（默认 180）")
    p.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                   help="翻几页 me/tasks 找实测价（默认 %d 页）" % DEFAULT_PAGES)
    p.add_argument("--allow-any-model", action="store_true",
                   help="型号不在清单里也允许提交（报价按同一条基线）")
    gate_args(p)
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("status", help="查任务（免费，只走 GET /api/v1/tasks/<id>）",
                       allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 id")
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
                       ("seconds", DEFAULT_SECONDS), ("models", None), ("model", None),
                       ("image", None), ("audio", None), ("video", None),
                       ("prompt", None), ("extra", None), ("upload", False),
                       ("outdir", "."), ("wait", False), ("save", False),
                       ("every", 10), ("limit", 900), ("timeout", 180),
                       ("allow_any_model", False), ("task_id", None),
                       ("run", None), ("manifest", None)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
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
