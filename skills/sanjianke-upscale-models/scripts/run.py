#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 超分模型台（sanjianke-upscale-models）

一条命令比较三条视频超分线，外加 4 个模型层超分模型：

  VIAPI 线    /api/v1/video/viapi/superres     9 点/秒（1080P）
              /api/v1/video/viapi/superres2k  15 点/秒（2K）
              /api/v1/video/viapi/superres4k  20 点/秒（4K）
  腾讯 MPS 线 /api/v1/video/tencent1080         2 点/秒（保底 10 点）   ← 502 InvalidMpsUser
              /api/v1/video/tencent2k           4 点/秒（保底 10 点）   ← 502
              /api/v1/video/tencent4k           8 点/秒（保底 10 点）   ← 502
  模型层      topaz-video-upscale / topaz-image-upscale /
              recraft-crisp-upscale / grok-imagine-upscale
              价目表里没有单价，只有通配规则「上游点数 x 2，单笔保底 50 点」

## 为什么有这一层

同一个「把 480P 提到 1080P」，三条线的价差是 4.5 倍：

  腾讯 1080P   2 点/秒   60 秒 =   120 点 =  1.20 元
  VIAPI 1080P  9 点/秒   60 秒 =   540 点 =  5.40 元
  4K 旗舰版   30 点/秒   60 秒 = 1,800 点 = 18.00 元

但最便宜那条**现在提交就 502**（网关凭据坏），所以本包把「能用 / 暂时不通」
做成第一列，而不是让用户点下去才发现。

## 实测（2026-11-08，本账号真实流水）

  POST /video/tencent1080  完整参数 → 502 FailedOperation.InvalidMpsUser
  本账号 3 条腾讯 4K 任务：status=refunded，chargedPoints=0，实扣 0 点
  本账号 1 条 FlashVSR 任务：status=settled，actualPrice=72.348 点
  POST /api/v1/videos  {"model":"topaz-video-upscale"}
        → 404 model_not_found（目录里有，当前 Key 没授权）
  POST /api/v1/images/generations {"model":"recraft-crisp-upscale"}
        → 同端点流水出现过先 reserve_sync 冻 20 点，再 refund 20 点（净 0）
  POST /video/viapi/superres {} → 400 empty_url（停在参数校验，零扣费）

## 模型层单价从哪来

`GET /api/v1/pricing` 的 115 条规则里**没有** /videos、/videos/generations、
/images/generations 的专属规则，它们命中通配 *：

  {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
   "note":"未单独定价的接口：对外 = 上游实际点数 x 2，单笔保底 50 点"}

所以模型层单价只能从自己的流水反推：`GET /api/v1/me/tasks`（免费）按 model
归集 `actualPrice`，取实测最低/中位/最高。有成交样本标 source=live；
没有就标 source=baseline，只报「50 点起（通配保底）」，不编单价。

## 子命令

  catalog  12 条路线：单价 / 状态 / 实际路径（免费，不用 Key）
  cost     先算钱：1/5/10/30/60 分钟价目（免费，不用 Key）
  compare  三线比价 + 推荐（免费；--live 时读模型层成交价）
  models   同一需求多模型横评（要 Key；--models a,b）
  doctor   自检 Key / 价目表 / 4 个模型 / 7 个端点（免费，不扣费）
  upload   上传本地视频/图片，拿平台托管地址（免费）
  submit   提交一单（要 --yes，受 --budget 管）
  status   查任务（免费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --seconds 600
  python3 scripts/run.py compare --target 1080p --seconds 60
  python3 scripts/run.py models --models topaz-video-upscale,recraft-crisp-upscale
  python3 scripts/run.py doctor
  python3 scripts/run.py upload --file low.mp4
  python3 scripts/run.py submit --tier superres --video-url "https://..." --seconds 60 --yes
  python3 scripts/run.py status --task-id task_xxx

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import io
import json
import mimetypes
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.dont_write_bytecode = True
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")     # 中文控制台不因个别符号崩掉
    except Exception:                        # noqa: BLE001
        pass

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 5000
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "upscale-models-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-upscale-models/%s" % VERSION

# ── GBK 兜底：把 cp936 编不出的字符替换成 '-'，而不是 '?' ─────────────────────
# Windows 管道下 Python 用 cp936 输出，遇到 U+00A5 / en dash 这类字符会变 '?'。
# 本包所有输出都过一遍 safe()，GBK 严格解码后问号数为 0。
_GBK_CACHE = {}


def _gbk_ok(ch):
    v = _GBK_CACHE.get(ch)
    if v is None:
        try:
            ch.encode("gbk")
            v = True
        except Exception:                                        # noqa: BLE001
            v = False
        _GBK_CACHE[ch] = v
    return v


def safe(s):
    s = str(s)
    try:
        s.encode("gbk")
        return s
    except Exception:                                            # noqa: BLE001
        return "".join(c if _gbk_ok(c) else "-" for c in s)


def emit(line=""):
    sys.stdout.write(safe(line) + "\n")


def jout(obj):
    emit(json.dumps(obj, ensure_ascii=False))


def say(msg):
    sys.stderr.write(safe(msg) + "\n")


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


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


def yuan(points):
    try:
        return "%.2f" % (float(points) / POINTS_PER_YUAN)
    except Exception:                                            # noqa: BLE001
        return "-"


# ── 路线表：单价来自 GET /api/v1/pricing（2026-11-08 实测）────────────────────
# status: ok=路由在且价目表对得上；broken=上游 502/未授权；watch=先小样验
TIERS = {
    "superres": dict(
        line="VIAPI", name="标准超分 1080P", path=API_PREFIX + "/video/viapi/superres",
        mode="per_second", points=9, minPoints=0, status="ok", kind="video",
        bodyKey="videoUrl", res="1080P", probe="empty_url",
        note="输入 2 倍；空 body 实测 400 empty_url，路由在架"),
    "superres2k": dict(
        line="VIAPI", name="高清超分 2K", path=API_PREFIX + "/video/viapi/superres2k",
        mode="per_second", points=15, minPoints=0, status="ok", kind="video",
        bodyKey="videoUrl", res="2K", probe="empty_url",
        note="60 帧档；空 body 实测 400 empty_url"),
    "superres4k": dict(
        line="VIAPI", name="超清 4K", path=API_PREFIX + "/video/viapi/superres4k",
        mode="per_second", points=20, minPoints=0, status="ok", kind="video",
        bodyKey="videoUrl", res="4K", probe="empty_url",
        note="1080P 输入到 2160P；空 body 实测 400 empty_url"),
    "tencent1080": dict(
        line="腾讯 MPS", name="腾讯 1080P", path=API_PREFIX + "/video/tencent1080",
        mode="per_second", points=2, minPoints=10, status="broken", kind="video",
        bodyKey="video_url", res="1080P", probe="video_url_required",
        note="最便宜；完整参数实测 502 InvalidMpsUser，3 条任务 refunded、实扣 0"),
    "tencent2k": dict(
        line="腾讯 MPS", name="腾讯 2K", path=API_PREFIX + "/video/tencent2k",
        mode="per_second", points=4, minPoints=10, status="broken", kind="video",
        bodyKey="video_url", res="2K", probe="video_url_required",
        note="完整参数实测 502 InvalidMpsUser；失败全额退"),
    "tencent4k": dict(
        line="腾讯 MPS", name="腾讯 4K", path=API_PREFIX + "/video/tencent4k",
        mode="per_second", points=8, minPoints=10, status="broken", kind="video",
        bodyKey="video_url", res="4K", probe="video_url_required",
        note="完整参数实测 502 InvalidMpsUser；3 条历史任务全部 refunded"),
    "flashvsr": dict(
        line="FlashVSR 应用", name="FlashVSR 超分", path=API_PREFIX + "/apps/flashvsr/submit",
        mode="per_second", points=10, minPoints=20, status="ok", kind="video",
        bodyKey="input_url", res="1080P", probe=None,
        note="实测 1 条 settled：actualPrice 72.348 点；已有 a7w-flashvsr 专包"),
    "upscale4k": dict(
        line="4K 旗舰", name="4K 旗舰版", path=API_PREFIX + "/video/upscale",
        mode="per_second", points=30, minPoints=0, status="watch", kind="video",
        bodyKey="videoUrl", res="4K", probe="pixverse_empty_url",
        note="价目表 30 点/秒；本账号 7 条历史任务全部 refunded（实扣 0），先小样验"),
}

MODEL_TIERS = {
    "topaz-video-upscale": dict(
        line="模型层", name="Topaz 视频优化", path=API_PREFIX + "/videos",
        mode="per_call", points=None, minPoints=50, status="blocked", kind="video",
        bodyKey="video_url", field="video_url", res="4K",
        note="POST /videos 传该 model 实测 404 model_not_found（当前 Key 未授权）"),
    "topaz-image-upscale": dict(
        line="模型层", name="Topaz 图像优化", path=API_PREFIX + "/images/generations",
        mode="per_call", points=None, minPoints=50, status="watch", kind="image",
        bodyKey="image_url", field="image_url", res="image",
        note="目录在架；同族图像放大，按上游点数 x 2、保底 50 点"),
    "recraft-crisp-upscale": dict(
        line="模型层", name="Recraft 图像优化", path=API_PREFIX + "/images/generations",
        mode="per_call", points=None, minPoints=50, status="watch", kind="image",
        bodyKey="image", field="image", res="image",
        note="同端点流水出现过先冻 20 点再全额退；补 image 后再验"),
    "grok-imagine-upscale": dict(
        line="模型层", name="放大 Grok Imagine 视频", path=API_PREFIX + "/videos",
        mode="per_call", points=None, minPoints=50, status="watch", kind="video",
        bodyKey="task_id", field="task_id", res="4K",
        note="只收本账号已完成的 Grok 视频 task_id，不收外部视频"),
}

TIER_ORDER = ["superres", "superres2k", "superres4k",
              "tencent1080", "tencent2k", "tencent4k",
              "flashvsr", "upscale4k"]
MODEL_ORDER = ["topaz-video-upscale", "topaz-image-upscale",
               "recraft-crisp-upscale", "grok-imagine-upscale"]
ALL_TIERS = dict(TIERS)
ALL_TIERS.update(MODEL_TIERS)
TIER_CHOICES = TIER_ORDER + MODEL_ORDER

# ── 模型层基线：没有成交样本时只报通配保底，不编单价 ─────────────────────────
MODEL_BASELINE = {
    "topaz-video-upscale": dict(low=50.0, high=None, n=0,
                                route="/api/v1/videos",
                                note="通配保底 50 点/次起，上限按上游实际点数 x 2"),
    "topaz-image-upscale": dict(low=50.0, high=None, n=0,
                                route="/api/v1/images/generations",
                                note="通配保底 50 点/次起，上限按上游实际点数 x 2"),
    "recraft-crisp-upscale": dict(low=50.0, high=None, n=0,
                                  route="/api/v1/images/generations",
                                  note="通配保底 50 点/次起；同端点流水出现过冻 20 点后退回"),
    "grok-imagine-upscale": dict(low=50.0, high=None, n=0,
                                 route="/api/v1/videos",
                                 note="通配保底 50 点/次起；只收本账号 Grok 视频 task_id"),
}

STATUS_CN = {"ok": "可用", "broken": "暂时不通", "watch": "待验证",
             "blocked": "未授权", "unpriced": "价目待定"}
STATUS_MARK = {"ok": "√", "broken": "×", "watch": "≈", "blocked": "×", "unpriced": "≈"}


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


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
            with open(cfg, encoding="utf-8") as f:
                d = json.load(f)
            if not key:
                k = d.get("key") or d.get("api_key")
                if k:
                    key = str(k).strip()
            if not host and d.get("host"):
                host = str(d["host"]).rstrip("/")
        except Exception:                                        # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=90):
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
                return s[:300]
        for k in ("message", "msg", "failReason", "error"):
            v = d.get(k)
            if isinstance(v, dict):
                v = v.get("message") or v.get("code")
            if v:
                return str(v)[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该 JSON 端点" % st
    return (txt or "").replace("\n", " ")[:240]


def unit_label(t):
    if t["mode"] == "per_second":
        return "点/秒"
    if t["mode"] == "per_call":
        return "点/次起"
    return "点"


def is_model(tier):
    return tier in MODEL_TIERS


def tier_cost(tier, seconds):
    """返回 (点数, 口径)。模型层没有成交价时按通配保底 50 点报。"""
    t = ALL_TIERS[tier]
    if t["mode"] == "per_second":
        secs = max(1, int(seconds or 1))
        pts = t["points"] * secs
        floor = t.get("minPoints") or 0
        if floor and pts < floor:
            return floor, "%d 点/秒 x %d 秒，不足保底 %d 点" % (
                t["points"], secs, floor)
        return pts, "%d 点/秒 x %d 秒" % (t["points"], secs)
    base = MODEL_BASELINE.get(tier) or {}
    low = float(base.get("low") or 50)
    return low, "按次保底 %s 点起（价目表通配：上游点数 x 2）；真实价看流水" % pnum(low)


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        with open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


def get_json(key, host, path, what, timeout=60):
    st, txt = http_json("GET", host + path, key, timeout=timeout)
    d = jloads(txt)
    if st != 200 or not isinstance(d, (dict, list)):
        raise Fail("call", "%s 拉取失败（HTTP %s）：%s"
                   % (what, st, err_text(st, txt)), EXIT_CALL)
    return d


def _gate(a, cost, requests=1, what="本次"):
    """两道闸门：预算先拦，再要 --yes。一个请求都不发。"""
    if requests > 0 and a.budget <= 0:
        raise Fail("budget",
                   "--budget 是 %d 点（单位：点）。0 点预算等于不授权任何调用；"
                   "给 1 点以上就放行。" % a.budget, EXIT_BUDGET)
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %d 点超过 --budget %d 点（%s），一个请求都没发。"
                   "调大 --budget 或减小时长。" % (cost, a.budget, what), EXIT_BUDGET)
    if cost > 0 and not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实提交任务，预计 / 冻结 %d 点（%.2f 元）。确认请加 --yes。"
                   % (cost, cost / float(POINTS_PER_YUAN)), EXIT_CONFIRM)
    if requests >= 30 and not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "%s要连发 %d 个只读请求（花费 0 点）。确认请加 --yes。"
                   % (what, requests), EXIT_CONFIRM)


def layer_prices(key, host, pages):
    """读 /api/v1/me/tasks，按 model 归集非应用层任务的 actualPrice。"""
    agg = {}
    for pg in range(1, pages + 1):
        d = get_json(key, host, API_PREFIX + "/me/tasks?limit=2000&page=%d" % pg,
                     "任务台账")
        ts = d.get("tasks") or []
        if not ts:
            break
        for t in ts:
            p = t.get("path") or ""
            m = (t.get("model") or "").strip()
            if not m or "/apps/" in p:
                continue
            try:
                v = float(t.get("actualPrice") or 0)
            except Exception:                                    # noqa: BLE001
                continue
            if v <= 0:
                continue
            a = agg.setdefault(m, {"model": m, "route": p, "samples": []})
            a["samples"].append(round(v, 2))
        if len(ts) < 20:
            break
    out = {}
    for m, a in agg.items():
        s = sorted(a["samples"])
        out[m] = dict(route=a["route"], low=s[0], high=s[-1], n=len(s), samples=s)
    return out


def model_price(tier, live):
    """模型层报价：live 优先，否则 baseline。绝不编单价。"""
    src = (live or {}).get(tier)
    if src:
        s = sorted(src["samples"])
        return dict(points=s[0], low=s[0], high=s[-1], n=len(s), source="live",
                    span=("%s" % pnum(s[0])) if s[0] == s[-1]
                    else "%s - %s" % (pnum(s[0]), pnum(s[-1])),
                    route=src.get("route") or (MODEL_BASELINE.get(tier) or {}).get("route", ""))
    b = MODEL_BASELINE.get(tier) or dict(low=50.0, high=None, n=0, note="")
    return dict(points=b["low"], low=b["low"], high=b.get("high"), n=0,
                source="baseline", span="%s 点起" % pnum(b["low"]),
                route=b.get("route", ""), note=b.get("note", ""))


# ───────────────────────── catalog ─────────────────────────
def cmd_catalog(a, key, host):
    rows = []
    for tid in TIER_CHOICES:
        t = ALL_TIERS[tid]
        if is_model(tid):
            q = model_price(tid, None)
            rows.append(dict(tier=tid, line=t["line"], name=t["name"], path=t["path"],
                             unit="点/次起", points=q["points"], pointsLive=False,
                             status=t["status"], statusCn=STATUS_CN[t["status"]],
                             source=q["source"], note=t.get("note", ""),
                             kind=t["kind"], field=t.get("field")))
        else:
            rows.append(dict(tier=tid, line=t["line"], name=t["name"], path=t["path"],
                             unit=unit_label(t), points=t["points"], pointsLive=True,
                             minPoints=t.get("minPoints") or 0, status=t["status"],
                             statusCn=STATUS_CN[t["status"]], source="pricing",
                             note=t.get("note", ""), kind=t["kind"]))
    out = {"ok": True, "count": len(rows), "tiers": rows,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "pricingSource": "GET /api/v1/pricing（2026-11-08 实测）",
           "modelPricingSource": "GET /api/v1/me/tasks 的 actualPrice；无样本用通配保底",
           "roundPoints": 0}
    if a.json:
        jout(out)
        return 0
    emit("三剪客 · 超分模型台 —— 12 条路线（按线路分组）")
    emit()
    emit("  %s %s %s %s %s" % (pad("--tier", 24), pad("线路", 14),
                               pad("单价", 11), pad("保底", 7), "状态 / 一句话"))
    emit("  " + "-" * 108)
    last = None
    for r in rows:
        if r["line"] != last:
            emit()
            last = r["line"]
        price = ("%s %s" % (pnum(r["points"]), r["unit"])) if r.get("points") is not None else "-"
        floor = ("%s 点" % pnum(r["minPoints"])) if r.get("minPoints") else "-"
        emit("  %s %s %s %s %s %s" % (
            pad(r["tier"], 24), pad(r["line"], 14), pad(price, 11),
            pad(floor, 7), pad(r["statusCn"], 9), r["note"][:62]))
    emit()
    emit("  1 元 = 100 点。按秒线里最便宜的是腾讯 1080P 2 点/秒（0.02 元/秒），")
    emit("  但它现在提交就 502；现可用的最便宜是 VIAPI 标准超分 9 点/秒。")
    emit("  模型层不在价目表里：4 个模型都按「上游点数 x 2、保底 50 点」结算，")
    emit("  真实单价要跑过一单后从 /api/v1/me/tasks 的 actualPrice 反推。")
    emit()
    emit("  已有专包（本包只做比价，不替代）：")
    emit("    VIAPI 三档 → sanjianke-vr-superres / -2k / -4k")
    emit("    腾讯 MPS   → sanjianke-mps-upscale")
    emit("    FlashVSR   → a7w-flashvsr")
    emit("    4K 旗舰    → sanjianke-vr-upscale-4k")
    return 0


# ───────────────────────── cost ─────────────────────────
def cmd_cost(a, key, host):
    detail = None
    if a.tier:
        pts, basis = tier_cost(a.tier, a.seconds)
        detail = {"tier": a.tier, "seconds": a.seconds, "points": pts,
                  "yuan": round(pts / float(POINTS_PER_YUAN), 2), "basis": basis}
    table = []
    marks = (60, 300, 600, 1800, 3600)
    for tid in TIER_CHOICES:
        t = ALL_TIERS[tid]
        row = {"tier": tid, "line": t["line"], "unit": unit_label(t),
               "status": t["status"], "statusCn": STATUS_CN[t["status"]]}
        if t["mode"] == "per_second":
            row["points"] = t["points"]
            row["cols"] = [tier_cost(tid, s)[0] for s in marks]
        else:
            q = model_price(tid, None)
            row["points"] = q["points"]
            row["cols"] = [q["points"]] * len(marks)
            row["perCall"] = True
        table.append(row)
    out = {"ok": True, "marks": list(marks), "tiers": table, "detail": detail,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-08 实测）",
               "按秒线按输入视频秒数计费，最小计 1 秒；腾讯保底 10 点、FlashVSR 保底 20 点",
               "腾讯三档当前 502 InvalidMpsUser，提交失败全额退，实扣 0 点",
               "模型层按次计，50 点是通配保底，不是 60 秒价；真实价看 actualPrice",
           ]}
    if a.json:
        jout(out)
        return 0
    emit("预估成本（1 元 = 100 点；单位：点）")
    emit()
    if detail:
        emit("  --tier %s（%s）" % (a.tier, ALL_TIERS[a.tier]["name"]))
        emit("  %s = %s 点 = %s 元" % (detail["basis"], pnum(detail["points"]),
                                       pnum(detail["yuan"])))
        emit()
    emit("  %s %s %s %s %s %s %s" % (pad("--tier", 24), pad("状态", 9),
                                     pad("1 分钟", 8, False), pad("5 分钟", 9, False),
                                     pad("10 分钟", 10, False), pad("30 分钟", 10, False),
                                     pad("60 分钟", 10, False)))
    emit("  " + "-" * 92)
    for r in table:
        emit("  %s %s %s %s %s %s %s" % (
            pad(r["tier"], 24), pad("%s%s" % (STATUS_MARK.get(r["status"], " "),
                                              r["statusCn"]), 9),
            pad(pnum(r["cols"][0]), 8, False), pad(pnum(r["cols"][1]), 9, False),
            pad(pnum(r["cols"][2]), 10, False), pad(pnum(r["cols"][3]), 10, False),
            pad(pnum(r["cols"][4]), 10, False)))
    emit()
    for n in out["notes"]:
        emit("  · %s" % n)
    return 0


# ───────────────────────── compare ─────────────────────────
def cmd_compare(a, key, host):
    target = "1080P" if a.target == "1080p" else a.target.upper()
    live = {}
    reqs = 0
    if a.live:
        if not key:
            raise Fail("usage", "--live 要读你账号的 /api/v1/me/tasks，请给 --key 或 "
                       "A7W_API_KEY", EXIT_USAGE)
        pages = 70 if a.all else a.pages
        reqs = pages
        _gate(a, 0, reqs, "横评要读 %d 页任务台账" % pages)
        if a.dry_run:
            return _plan(a, reqs, ["GET %s/me/tasks?limit=2000&page=%d"
                                   % (API_PREFIX, i) for i in range(1, pages + 1)])
        live = layer_prices(key, host, pages)

    cands = []
    for tid in TIER_CHOICES:
        t = ALL_TIERS[tid]
        if a.target == "image":
            if t["kind"] != "image":
                continue
        else:
            if t["kind"] != "video":
                continue
            # 模型层不按分辨率分档，视频目标里都保留；按秒线只留同分辨率
            if not is_model(tid) and t.get("res") != target:
                continue
        if is_model(tid):
            q = model_price(tid, live)
            pts = q["points"]
            basis = "按次保底 %s 点起（%s）" % (pnum(pts), q["source"])
            src = q["source"]
        else:
            pts, basis = tier_cost(tid, a.seconds)
            src = "pricing"
        cands.append(dict(tier=tid, line=t["line"], name=t["name"], points=pts,
                          yuan=round(pts / float(POINTS_PER_YUAN), 2),
                          basis=basis, source=src, status=t["status"],
                          statusCn=STATUS_CN[t["status"]], note=t.get("note", ""),
                          path=t["path"], perCall=is_model(tid)))
    cands.sort(key=lambda r: (r["points"], r["status"] != "ok"))
    usable = [c for c in cands if c["status"] == "ok"]
    broken = [c for c in cands if c["status"] == "broken"]
    rec = usable[0] if usable else (cands[0] if cands else None)
    saving = None
    if usable and broken and broken[0]["points"] < usable[0]["points"]:
        diff = usable[0]["points"] - broken[0]["points"]
        saving = {"points": diff, "yuan": round(diff / float(POINTS_PER_YUAN), 2),
                  "pct": round(diff * 100.0 / usable[0]["points"], 1),
                  "ifTier": broken[0]["tier"]}
    out = {"ok": True, "target": target, "seconds": a.seconds,
           "candidates": cands, "recommended": rec, "savingIfFixed": saving,
           "live": bool(a.live), "estimatedPoints": 0,
           "note": "点数为预付估算；失败任务全额退回，实扣以 /me/tasks 的 netPoints 为准"}
    if a.json:
        jout(out)
        return 0
    label = "图片" if a.target == "image" else target
    scope = "按次" if a.target == "image" else "%s 秒" % a.seconds
    emit("三线比价 · 目标 %s · %s（1 元 = 100 点）" % (label, scope))
    emit("=" * 100)
    emit("  %s %s %s %s %s" % (pad("线路", 16), pad("档位", 28),
                               pad("点数", 10, False), pad("折合", 10, False), "状态 / 说明"))
    emit("  " + "-" * 96)
    for c in cands:
        emit("  %s %s %s %s %s" % (
            pad(c["line"], 16), pad(c["name"], 28), pad(pnum(c["points"]), 10, False),
            pad(yuan(c["points"]) + " 元", 10, False),
            "%s %s" % (STATUS_MARK.get(c["status"], " "), c["statusCn"])))
        if c["status"] != "ok":
            emit("  %s %s" % (" " * 16, c["note"][:88]))
    emit()
    if rec:
        emit("  推荐：%s（%s）%s 点 = %s 元" % (rec["name"], rec["line"],
                                              pnum(rec["points"]), yuan(rec["points"])))
        emit("  口径：%s" % rec["basis"])
    if saving:
        emit("  如果 %s 修好：只要 %s 点（%s 元），省 %s 点（%s%%）。"
             % (saving["ifTier"], pnum(usable[0]["points"] - saving["points"]),
                yuan(usable[0]["points"] - saving["points"]),
                pnum(saving["points"]), saving["pct"]))
    if a.target == "image":
        emit("  图片线只有模型层：Recraft / Topaz 图像放大，50 点是按次保底，")
        emit("  不是按秒价；补 image 素材后可先跑一单，真实价从流水反推。")
    else:
        emit("  模型层 50 点是按次保底，不能直接和按秒线比大小。")
    emit("  本轮花费 0 点（只读 GET + 本地价目表）。")
    return 0


def _plan(a, reqs, lines):
    out = {"ok": True, "dryRun": True, "requests": lines, "requestCount": reqs,
           "estimatedPoints": 0, "yuan": 0.0}
    if a.json:
        jout(out)
        return 0
    emit("干跑（一个请求都不发）")
    emit("  请求数：%d" % reqs)
    emit("  预估：0 点（0.00 元）—— 全部是只读 GET")
    for ln in lines:
        emit("  -> %s" % ln)
    return 0


# ───────────────────────── models ─────────────────────────
def cmd_models(a, key, host):
    picks = MODEL_ORDER
    if a.models:
        picks = [x.strip() for x in a.models.split(",") if x.strip()]
        bad = [x for x in picks if x not in MODEL_TIERS]
        if bad:
            raise Fail("usage", "未知模型：%s。可选：%s"
                       % ("、".join(bad), "、".join(MODEL_ORDER)), EXIT_USAGE)
    pages = 70 if a.all else a.pages
    _gate(a, 0, pages, "横评要读 %d 页任务台账" % pages)
    if a.dry_run:
        return _plan(a, pages, ["GET %s/me/tasks?limit=2000&page=%d"
                                % (API_PREFIX, i) for i in range(1, pages + 1)])
    live = layer_prices(key, host, pages)
    rows = []
    for tid in picks:
        t = MODEL_TIERS[tid]
        q = model_price(tid, live)
        rows.append(dict(tier=tid, name=t["name"], path=t["path"],
                         points=q["points"], source=q["source"], span=q["span"],
                         n=q["n"], route=q.get("route") or t["path"],
                         status=t["status"], statusCn=STATUS_CN[t["status"]],
                         kind=t["kind"], field=t.get("field"), note=t.get("note", "")))
    rows.sort(key=lambda r: (r["points"], r["status"] != "watch"))
    out = {"ok": True, "models": rows, "liveCount": sum(1 for r in rows if r["source"] == "live"),
           "baselineCount": sum(1 for r in rows if r["source"] == "baseline"),
           "pagesScanned": pages, "estimatedPoints": 0,
           "note": "live = 你账号 /api/v1/me/tasks 的真实 actualPrice；"
                   "baseline = 价目表通配保底 50 点起，不是编出来的单价"}
    if a.json:
        jout(out)
        return 0
    emit("同一需求 · 模型层多模型横评（%d 个模型，扫描 %d 页台账）"
         % (len(rows), pages))
    emit("=" * 100)
    emit("  %s %s %s %s %s" % (pad("模型", 30), pad("调用路径", 30),
                               pad("报价", 10, False), pad("来源", 9), "状态 / 素材"))
    emit("  " + "-" * 96)
    for r in rows:
        emit("  %s %s %s %s %s" % (
            pad(r["tier"], 30), pad(r["path"].replace(API_PREFIX, ""), 30),
            pad(pnum(r["points"]), 10, False), pad(r["source"], 9),
            "%s %s" % (STATUS_MARK.get(r["status"], " "), r["statusCn"])))
        emit("  %s 素材：%s；%s" % (" " * 30, r["field"] or "-", r["note"][:80]))
    emit()
    emit("  有历史成交价：%d 个；用基线：%d 个。" % (
        out["liveCount"], out["baselineCount"]))
    emit("  模型层单价不在 /api/v1/pricing（115 条规则里没有 /videos、")
    emit("  /images/generations），只能从 /api/v1/me/tasks 的 actualPrice 反推。")
    emit("  本轮花费 0 点（只读 GET）。")
    return 0


# ───────────────────────── doctor ─────────────────────────
def cmd_doctor(a, key, host):
    reqs = 14
    _gate(a, 0, reqs, "自检要发 %d 个只读/参数校验请求" % reqs)
    if a.dry_run:
        return _plan(a, reqs, ["GET /user/balance", "GET %s/pricing" % API_PREFIX,
                               "GET %s/models" % API_PREFIX,
                               "GET %s/apps" % API_PREFIX,
                               "POST 7 个端点空 body（只到参数校验）",
                               "GET %s/tasks/<fake>" % API_PREFIX,
                               "GET %s/videos/<fake>" % API_PREFIX,
                               "GET /user/balance/logs?limit=20"])
    checks = []

    def chk(name, ok, detail):
        checks.append((name, bool(ok), detail))

    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    chk("Key + 余额接口可达", st == 200,
        "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
            st, pnum(d.get("available_points") or d.get("points") or 0),
            pnum(d.get("frozen") or 0)))

    st_p, txt_p = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=40)
    pricing = {}
    if st_p == 200:
        try:
            pricing = (jloads(txt_p) or {}).get("pricing") or {}
        except Exception:                                        # noqa: BLE001
            pricing = {}
    drift = []
    for tid in TIER_ORDER:
        t = TIERS[tid]
        row = pricing.get(t["path"]) or {}
        live = row.get("perSecond")
        if live is None:
            drift.append("%s 线上无此键" % tid)
        elif int(live) != int(t["points"]):
            drift.append("%s 本地 %s / 线上 %s" % (tid, t["points"], live))
    chk("8 条按秒线单价与 /api/v1/pricing 一致", st_p == 200 and not drift,
        "HTTP %s · %s" % (st_p, "全一致" if not drift else " / ".join(drift)[:100]))

    st_m, txt_m = http_json("GET", host + API_PREFIX + "/models", key, timeout=60)
    md = jloads(txt_m) or {}
    ms = md.get("data") or []
    codes = set(m.get("model_code") or m.get("id") for m in ms)
    have = [m for m in MODEL_ORDER if m in codes]
    chk("4 个模型层模型在目录里", st_m == 200 and len(have) == 4,
        "目录 %d 条 · 命中 %d / 4（%s）" % (len(ms), len(have), "、".join(have) or "-"))

    st_a, txt_a = http_json("GET", host + API_PREFIX + "/apps", key, timeout=40)
    ad = jloads(txt_a) or {}
    aps = ad.get("data") or []
    fv = [x for x in aps if (x.get("code") or "") == "flashvsr"]
    chk("FlashVSR 应用在架（对照线）", st_a == 200 and bool(fv),
        "应用 %d 个 · flashvsr %s" % (len(aps), "在" if fv else "缺失"))

    probes = [
        ("superres", "empty_url"), ("superres2k", "empty_url"),
        ("superres4k", "empty_url"), ("tencent1080", "video_url_required"),
        ("tencent2k", "video_url_required"), ("tencent4k", "video_url_required"),
        ("upscale4k", "pixverse_empty_url"),
    ]
    probe_ok = 0
    for tid, want in probes:
        t = TIERS[tid]
        say("  探 %-12s %s …" % (tid, t["path"]))
        st2, txt2 = http_json("POST", host + t["path"], key, {}, timeout=a.timeout)
        e2 = (jloads(txt2) or {}).get("error") if isinstance(jloads(txt2), dict) else {}
        code = (e2 or {}).get("code") or ""
        ok2 = st2 == 400 and code == want
        probe_ok += 1 if ok2 else 0
        chk("端点 %-12s 可用（400 %s）" % (tid, want), ok2,
            "HTTP %s %s" % (st2, code or err_text(st2, txt2)[:40]))
    chk("7 个超分端点全部停在参数校验", probe_ok == len(probes),
        "%d / %d 命中预期错误码；空 body 不建任务" % (probe_ok, len(probes)))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/tasks/probe-no-such-task",
                          key, timeout=40)
    d3 = jloads(txt3) or {}
    chk("通用任务查询 GET /tasks/{id} 可达", st3 == 200 and d3.get("code") == 0,
        "HTTP %s %s" % (st3, (d3.get("msg") or "")[:30]))

    st4, txt4 = http_json("GET", host + API_PREFIX + "/videos/probe-no-such-task",
                          key, timeout=40)
    d4 = jloads(txt4) or {}
    chk("模型层任务查询 GET /videos/{id} 可达", st4 == 400
        and d4.get("code") == "task_not_exist",
        "HTTP %s %s" % (st4, d4.get("code") or ""))

    st5, txt5 = http_json("GET", host + "/user/balance/logs?limit=20", key, timeout=40)
    d5 = jloads(txt5) or {}
    logs = d5.get("logs") or []
    win = [x for x in logs if int(x.get("at") or 0) >= int(time.time() * 1000) - 3600000]
    net = sum(float(x.get("points") or 0) for x in win)
    chk("流水接口可达 + 近 1 小时净额", st5 == 200 and isinstance(logs, list),
        "%d 条流水 · 近 1 小时 %s 点" % (len(logs), pnum(net)))

    out = {"ok": all(c[1] for c in checks), "host": host,
           "tierCount": len(TIER_CHOICES), "modelCount": len(MODEL_ORDER),
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks],
           "estimatedPoints": 0, "yuan": 0.0,
           "note": "全部只读 GET 或空 body POST；空 body 停在参数校验，不建任务、不冻结"}
    if not out["ok"]:
        out["exit"] = EXIT_GATE
        out["error"] = {"kind": "gate", "message": "自检有 %d 项未通过"
                        % sum(1 for c in checks if not c[1])}
    if a.json:
        jout(out)
        return 0 if out["ok"] else EXIT_GATE
    emit()
    emit("自检（不扣费：只读 GET + 7 个空 body POST，空 body 停在参数校验）")
    emit()
    for n, o, dd in checks:
        emit("  %s %s %s" % ("√" if o else "×", pad(n, 40), dd))
    emit()
    emit("  三线现状：")
    emit("    VIAPI 9/15/20 点每秒  → 路由在，按秒计费")
    emit("    腾讯 2/4/8 点每秒     → 端点通，上游 502 InvalidMpsUser（任务全退）")
    emit("    模型层 50 点起         → 目录在，Topaz 视频 404、Recraft/Topaz 图待素材")
    emit("  本轮花费 0 点（没有建任何任务）。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── upload ─────────────────────────
def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（要上传的本地视频/图片）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + API_PREFIX + "/upload"
    _gate(a, 0, 1)
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": path, "size": size,
               "estimatedPoints": 0}
        if a.json:
            jout(out)
            return 0
        emit("干跑（不上传）")
        emit("  端点：POST %s（multipart，字段名 file）" % url)
        emit("  文件：%s（%s 字节）" % (path, pnum(size)))
        return 0
    say("正在上传 %s（%s 字节）…" % (os.path.basename(path), pnum(size)))
    st, txt = http_multipart(url, key, {}, [("file", path)], timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    out = {"ok": True, "url": got, "size": data.get("size"),
           "mime": data.get("mime_type"), "type": data.get("type"),
           "estimatedPoints": 0}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True,
                "mode": "upload", "file": path, "url": got})
    if a.json:
        jout(out)
        return 0
    emit("已上传（免费）")
    emit("  地址：%s" % got)
    emit("  类型：%s · %s · %s 字节" % (data.get("type"), data.get("mime_type"),
                                        pnum(data.get("size") or size)))
    emit()
    emit("  下一步：python3 scripts/run.py submit --tier superres --video-url \"%s\" "
         "--seconds 10 --yes" % got)
    return 0


# ───────────────────────── submit ─────────────────────────
def _submit_body(tid, a):
    t = ALL_TIERS[tid]
    if is_model(tid):
        body = {"model": tid}
        key = t.get("field")
        if key == "task_id":
            if not a.task_id:
                raise Fail("usage", "%s 要 --task-id（本账号已完成的 Grok 视频任务号）"
                           % tid, EXIT_USAGE)
            body["task_id"] = a.task_id
        else:
            url = _pick_url(a, t)
            body[key] = url
        return body
    url = _pick_url(a, t)
    body = {t["bodyKey"]: url}
    if t["mode"] == "per_second":
        body["duration"] = int(a.seconds)
    return body


def _pick_url(a, t):
    if t["kind"] == "image":
        url = a.image_url
    else:
        url = a.video_url
    if not url:
        raise Fail("usage", "必须给 %s（%s 的输入素材地址；先用 upload 拿）"
                   % ("--image-url" if t["kind"] == "image" else "--video-url", t["name"]),
                   EXIT_USAGE)
    if not (url.startswith("http://") or url.startswith("https://")):
        raise Fail("usage", "素材地址要以 http:// 或 https:// 开头", EXIT_USAGE)
    return url


def cmd_submit(a, key, host):
    tid = a.tier
    t = ALL_TIERS[tid]
    if t["mode"] == "per_second" and not a.seconds:
        raise Fail("usage", "按秒计费的档位必须给 --seconds（输入视频秒数），"
                   "否则没法先算钱", EXIT_USAGE)
    if t["status"] in ("broken", "blocked") and not a.allow_blocked:
        hint = ("腾讯 MPS 当前 502 InvalidMpsUser，提交会失败并全额退回，"
                "但会先冻结点数。建议改用 --tier superres（9 点/秒，现可用）。"
                if t["status"] == "broken" else
                "POST /videos 传该 model 实测 404 model_not_found，当前 Key 没有这个模型。")
        raise Fail("usage",
                   "%s 当前%s：%s\n确实要试一次就加 --allow-blocked；失败全额退，净 0 点。"
                   % (tid, STATUS_CN[t["status"]], hint), EXIT_USAGE)
    body = _submit_body(tid, a)
    cost, basis = tier_cost(tid, a.seconds)
    _gate(a, cost, 1, basis)
    url = host + t["path"]
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "tier": tid, "url": url,
               "requestBody": body, "estimatedPoints": cost,
               "yuan": round(cost / float(POINTS_PER_YUAN), 2), "basis": basis,
               "status": t["status"]}
        if a.json:
            jout(out)
            return 0
        emit("干跑（不提交、不冻结、不扣费）")
        emit("  端点：%s" % url)
        emit("  请求：%s" % json.dumps(body, ensure_ascii=False))
        emit("  预估：%s 点（%s 元）· %s" % (pnum(cost), pnum(cost / 100.0), basis))
        return 0
    say("正在提交 %s（%s）…" % (tid, t["name"]))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    task_id = (d.get("task_id") or d.get("taskId") or d.get("id")
               or data.get("task_id") or data.get("taskId") or data.get("id"))
    if st not in (200, 201) or (score_fail(d) and not task_id):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "mode": "submit", "tier": tid, "http": st, "error": msg})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real_cost = (d.get("cost") or d.get("points") or usage.get("points_cost")
                 or data.get("points"))
    out = {"ok": bool(task_id), "tier": tid, "taskId": task_id,
           "status": d.get("status") or data.get("status"),
           "estimatedPoints": cost, "actualPoints": real_cost,
           "elapsed": round(dt, 1), "endpoint": t["path"],
           "query": "python3 scripts/run.py status --task-id %s --tier %s"
                    % (task_id, tid)}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(task_id),
                "mode": "submit", "tier": tid, "taskId": task_id,
                "estimatedPoints": cost, "actualPoints": real_cost})
    if a.json:
        jout(out)
        return 0 if task_id else EXIT_CALL
    if not task_id:
        say("  响应里没有 taskId。原始返回：")
        emit(txt[:800])
        return EXIT_CALL
    emit("已提交（%.1fs）" % dt)
    emit("  档位：%s（%s）" % (tid, t["name"]))
    emit("  任务：%s   状态：%s" % (task_id, d.get("status") or data.get("status")))
    emit("  预估：%s 点（%s 元）" % (pnum(cost), pnum(cost / 100.0)))
    if real_cost is not None:
        emit("  返回点数：%s 点（失败全额退，实扣看 status）" % pnum(real_cost))
    emit()
    emit("  查进度：python3 scripts/run.py status --task-id %s --tier %s" % (task_id, tid))
    return 0


def score_fail(d):
    """老接口 code=0 表示失败；OpenAI 风格没有 code，靠 HTTP 状态判断。"""
    if not isinstance(d, dict):
        return True
    if "code" in d and d.get("code") == 0:
        return True
    if d.get("error"):
        return True
    return False


# ───────────────────────── status ─────────────────────────
def cmd_status(a, key, host):
    tid = a.task_id
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    _gate(a, 0, 3)
    cands = [("通用任务", "GET", API_PREFIX + "/tasks/" + tid),
             ("模型层任务", "GET", API_PREFIX + "/videos/" + tid),
             ("VIAPI 结果", "GET", API_PREFIX + "/video/viapi/result/" + tid)]
    if a.tier and a.tier == "flashvsr":
        cands.insert(0, ("FlashVSR 查询", "POST", API_PREFIX + "/apps/flashvsr/query"))
    hit = None
    for name, method, path in cands:
        body = {"task_id": tid} if method == "POST" else None
        st, txt = http_json(method, host + path, key, body, timeout=40)
        d = jloads(txt) or {}
        e = d.get("error") if isinstance(d.get("error"), dict) else {}
        empty = ((st == 200 and d.get("code") == 0 and not d.get("data"))
                 or (st == 400 and (d.get("code") == "task_not_exist"))
                 or (st == 404 and e.get("code") == "not_found"))
        if empty:
            continue
        hit = (name, method, path, st, txt, d)
        break
    if hit is None:
        raise Fail("call", "查不到任务 %s（试过 %d 条查询路由，都说不存在）"
                   % (tid, len(cands)), EXIT_CALL)
    name, method, path, st, txt, d = hit
    if st not in (200, 201):
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    data = d.get("data") if isinstance(d.get("data"), dict) else d
    urls = data.get("resultUrls") or data.get("result_urls") or []
    out = {"ok": True, "taskId": tid, "route": name, "path": path,
           "status": data.get("status"), "cost": data.get("actualPrice"),
           "refund": data.get("refund") or data.get("refundedPoints"),
           "netPoints": data.get("netPoints"),
           "videoUrl": data.get("video_url") or data.get("videoUrl"),
           "imageUrl": data.get("image_url") or data.get("imageUrl"),
           "resultUrls": urls, "error": data.get("error"),
           "message": data.get("message") or data.get("failReason")}
    if a.json:
        jout(out)
        return 0
    emit("任务 %s" % tid)
    emit("  查询路由：%s %s" % (method, path))
    emit("  状态：%s" % data.get("status"))
    if data.get("actualPrice") is not None:
        emit("  标价：%s 点" % pnum(data.get("actualPrice")))
    if data.get("refundedPoints") is not None:
        emit("  已退：%s 点" % pnum(data.get("refundedPoints")))
    if data.get("netPoints") is not None:
        emit("  净额：%s 点" % pnum(data.get("netPoints")))
    for k in ("video_url", "videoUrl"):
        if data.get(k):
            emit("  成片：%s（链接有时效，及时转存）" % data[k])
    for k in ("image_url", "imageUrl"):
        if data.get(k):
            emit("  图片：%s" % data[k])
    if urls:
        emit("  产物：%s" % "、".join(str(u) for u in urls[:4]))
    if out.get("message"):
        emit("  说明：%s" % str(out["message"])[:200])
    return 0


# ───────────────────────── log ─────────────────────────
def cmd_log(a, key, host):
    if not os.path.isfile(LEDGER):
        out = {"ok": True, "count": 0, "entries": []}
    else:
        arr = json.load(open(LEDGER, encoding="utf-8"))
        out = {"ok": True, "count": len(arr), "entries": arr[-a.limit:]}
    if a.json:
        jout(out)
        return 0
    emit("本地台账（显示 %d / 共 %d 条）" % (len(out["entries"]), out["count"]))
    for e in out["entries"]:
        emit("  %s  %-4s %-6s %-22s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            (e.get("tier") or os.path.basename(e.get("file") or "-"))[:22],
            e.get("taskId") or e.get("url") or (e.get("error") or "")[:40]))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 超分模型台：VIAPI / 腾讯 / 模型层三条线比价，一条命令选最划算",
        epilog="端点：POST %s/api/v1/video/viapi/superres（1080P）· "
               "POST %s/api/v1/video/tencent1080（腾讯）· POST %s/api/v1/videos（模型层）· "
               "GET %s/api/v1/tasks/<id>（查任务，免费）"
               % ((DEFAULT_HOST,) * 4),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 50 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    def gate_args(p, dry=True):
        p.add_argument("--yes", action="store_true", help="确认执行")
        if dry:
            p.add_argument("--dry-run", action="store_true", help="只打印请求，不执行")

    p = sub.add_parser("catalog", help="12 条路线：单价 / 状态 / 实际路径（免费）",
                       allow_abbrev=False)
    gate_args(p)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：1/5/10/30/60 分钟价目（免费）",
                       allow_abbrev=False)
    p.add_argument("--tier", choices=TIER_CHOICES, help="只看这一档（默认全部）")
    p.add_argument("--seconds", type=int, default=60, help="按多少秒估算（默认 60）")
    gate_args(p)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("compare", help="三线比价 + 推荐（免费；--live 读模型层成交价）",
                       allow_abbrev=False)
    p.add_argument("--target", choices=["1080p", "2k", "4k", "image"], default="1080p",
                   help="目标：1080p / 2k / 4k / image（默认 1080p）")
    p.add_argument("--seconds", type=int, default=60, help="按多少秒比（默认 60）")
    p.add_argument("--live", action="store_true", help="读 /me/tasks 的真实模型层成交价")
    p.add_argument("--pages", type=int, default=10, help="--live 时翻几页台账（默认 10）")
    p.add_argument("--all", action="store_true", help="翻完全部台账（约 70 页，要 --yes）")
    gate_args(p)
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("models", help="同一需求多模型横评（--models a,b）",
                       allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔，默认 4 个全看：%s" % "、".join(MODEL_ORDER))
    p.add_argument("--pages", type=int, default=10, help="翻几页台账找成交价（默认 10）")
    p.add_argument("--all", action="store_true", help="翻完全部台账（约 70 页，要 --yes）")
    gate_args(p)
    p.set_defaults(fn=cmd_models)

    p = sub.add_parser("doctor", help="自检 Key / 价目表 / 模型 / 7 个端点（不扣费）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    gate_args(p)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("upload", help="上传本地素材，拿平台托管地址（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地视频/图片路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    gate_args(p)
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("submit", help="提交一单（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    p.add_argument("--tier", choices=TIER_CHOICES, required=True,
                   help="档位，见 catalog")
    p.add_argument("--video-url", help="视频地址（视频档用）")
    p.add_argument("--image-url", help="图片地址（图像放大档用）")
    p.add_argument("--task-id", help="Grok 视频任务号（只 grok-imagine-upscale 用）")
    p.add_argument("--seconds", type=int, default=0,
                   help="输入视频秒数（按秒档必填，用于先算钱）")
    p.add_argument("--allow-blocked", action="store_true",
                   help="对已知 502/404 的档位仍尝试一次（失败全额退，净 0 点）")
    p.add_argument("--timeout", type=int, default=180, help="提交超时秒数（默认 180）")
    gate_args(p)
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("status", help="查任务（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 taskId")
    p.add_argument("--tier", choices=TIER_CHOICES, help="知道哪一档时填上，查得更快")
    gate_args(p)
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    gate_args(p)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


LOCAL_OK = ("cmd_catalog", "cmd_cost", "cmd_compare", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0),
                       ("yes", False), ("dry_run", False), ("seconds", 60),
                       ("tier", None), ("timeout", 90), ("limit", 20),
                       ("pages", 10), ("all", False), ("live", False),
                       ("target", "1080p"), ("models", None),
                       ("video_url", None), ("image_url", None),
                       ("task_id", None), ("allow_blocked", False), ("file", None)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    try:
        key, host = load_conf(a.key, a.host)
        fn_name = getattr(a.fn, "__name__", "")
        if not key and fn_name not in LOCAL_OK:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                       EXIT_USAGE)
        return a.fn(a, key, host)
    except Fail as e:
        if a.json:
            jout({"ok": False, "exit": e.exit_code,
                  "error": {"kind": e.kind, "message": e.message}})
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
