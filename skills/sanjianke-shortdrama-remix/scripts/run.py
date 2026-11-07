#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 短剧二创一条龙（sanjianke-shortdrama-remix）

一条短剧素材，从认演员表到出二创成片，一条命令串完。本包把 6 个工位串成一条链：

      upload（免费，拿白名单地址）
        -> castcrew  认演员表 / 硬字幕 OCR   25 点/次   -> 出演员表 + SRT
        -> delogo    去台标 / Logo           25 点/次   -> 出无台标视频
        -> subtitle  擦硬字幕                 9 点/秒   -> 出无字幕视频
        -> enhance   画质提一档              15 点/秒   -> 出高清视频
        -> tts       解说配音            上游点数 x3   -> 出解说音频
        -> mixcut    模板混剪成片          4.5 点/秒   -> 出最终成片

## 实测（2026-11-07，只读 GET + 空 body 探针，0 条任务、0 点净花费）

  POST /api/v1/video/viapi/castcrew   {} -> 400 {"error":{"code":"empty_url",...}}
  POST /api/v1/video/viapi/delogo     {} -> 400 empty_url
  POST /api/v1/video/viapi/subtitle   {} -> 400 empty_url
  POST /api/v1/video/viapi/enhance    {} -> 400 empty_url
  POST /api/v1/video/viapi/subtitle   {"videoUrl":"https://example.invalid/x.mp4"}
                                      -> 400 url_not_allowed（三选一白名单）
  GET  /api/v1/video/viapi/result/<假id> -> 404 not_found
  GET  /api/v1/tasks/<假id>              -> 200 code 0「任务不存在」
  POST /api/v1/upload（不带 file）        -> 200 code 0「请使用 file 字段提交一个文件」
  GET  /api/v1/apps                      -> 22 个应用，含 smart_clip / voice_tts
  GET  /api/v1/pricing                   -> 115 条规则，本包 6 个工位都有专属价

## 价格（GET /api/v1/pricing 原文，1 元 = 100 点）

  /api/v1/video/viapi/castcrew   25 点/次（rule 写 per_second，note 写点/次）
  /api/v1/video/viapi/delogo     25 点/次（同上）
  /api/v1/video/viapi/subtitle    9 点/秒
  /api/v1/video/viapi/enhance    15 点/秒
  /api/v1/apps/voice_tts/*       上游实际点数 x3（实测 33 字 = 1.98 点 -> 5.94 点）
  /api/v1/apps/smart_clip/*      4.5 点/秒，无时长时按 45 点预估

## 三条实测出来的硬规则

  1. videoUrl 只认平台托管地址：vr.a7w.cn / cdn2.jiujiushuyuan.cn/vr/ /
     oss.gpu.likeadmin.cn/openapi/。外站地址在参数校验层就被 400 挡下。
  2. castcrew 没有成片：completed 时 videoUrl 为空，结果在 result 与
     artifactUrl（SRT，30 分钟有效）。链上它只做旁路，不改主视频。
  3. 应用层两个 submit 走 reserve_sync：缺参数先冻结再全额退。连免费的
     GET /apps/smart_clip/template（先冻 50）与 /apps/voice_tts/list_voices
     （先冻 150）都会先冻后退 —— 净 0，但钱包会动。所以 doctor 只查
     GET /api/v1/apps 注册表，不碰应用层。

## 子命令

  catalog   6 个工位 + 单价 + 端点（免费，不联网）
  cost      先算钱：按秒数/字数算一趟全链（免费）
  doctor    自检 Key / 价目 / 6 个端点 / 查询 / 上传 / 应用注册表（免费）
  template  列混剪模板，拿 styleId（免费查，会冻 50 点再全额退）
  upload    上传本地素材，拿白名单地址（免费）
  run       --step 跑一步，--all 全链跑完（要 --yes，受 --budget 管）
  status    查任务（免费；视频走 result 路由，应用走 /tasks）
  log       本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost --seconds 60 --chars 200
  python3 scripts/run.py upload --file 素材.mp4
  python3 scripts/run.py run --step subtitle --video-url "https://oss.gpu.likeadmin.cn/openapi/..." --yes
  python3 scripts/run.py run --all --file 素材.mp4 --script "解说词" --style-id 6ac8981c20d5010033eee1b7 --yes
  python3 scripts/run.py status --task-id task_xxx --step enhance

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import io
import json
import math
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

# ── GBK 编码兜底（照抄 video-lab，2026-11-07 实测修复）──────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到个别符号就 UnicodeEncodeError 崩掉。先加 errors='replace' 兜底。
# 输出只用 √ / ×（cp936 里有），不用 U+2713 / U+2717 那两个符号（cp936 里没有）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
UPLOAD_PATH = API_PREFIX + "/upload"
VIDEO_RESULT = API_PREFIX + "/video/viapi/result/"
TASK_PATH = API_PREFIX + "/tasks/"
APPS_PATH = API_PREFIX + "/apps"
PRICING_PATH = API_PREFIX + "/pricing"
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "shortdrama-remix-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 3000          # 30 元
DEFAULT_SECONDS = 60
DEFAULT_CHARS = 200
DEFAULT_TTS_MODEL = "s2-pro"

UA = "sanjianke-shortdrama-remix/%s" % VERSION

# ── 6 个工位（价格来自 GET /api/v1/pricing，2026-11-07 实测）─────────────────
# unit: per_call 点/次 · per_second 点/秒 · per_char 点/字（TTS 上游 x3）
VIDEO_STEPS = {
    "castcrew": dict(points=25, unit="per_call", name="认演员表 / 硬字幕 OCR",
                     desc="抽出硬字幕与滚动演职员表，附 SRT",
                     note="rule 写 per_second，价签写 25 点/次"),
    "delogo": dict(points=25, unit="per_call", name="去台标 / Logo",
                   desc="擦台标、平台 logo，最多 2 个区域，缺省全画面",
                   note="rule 写 per_second，价签写 25 点/次"),
    "subtitle": dict(points=9, unit="per_second", name="擦硬字幕",
                     desc="把原片硬字幕抹干净，二创换字幕的第一步"),
    "enhance": dict(points=15, unit="per_second", name="画质提一档",
                    desc="清晰度 / 对比度 / 细节整体提一档"),
}
TTS = dict(points_per_char=0.18, min_points=6, app="voice_tts", api="tts_async",
           name="解说配音", desc="长文本异步合成，按上游实际点数 x3 结算")
MIXCUT = dict(points_per_second=4.5, min_points=45, app="smart_clip",
              api="broadcast_mixcut", name="模板混剪成片",
              desc="按模板把素材与解说拼成成片，按输出秒数计费")

STEP_ORDER = ["castcrew", "delogo", "subtitle", "enhance", "tts", "mixcut"]
STEP_NAME = {s: VIDEO_STEPS[s]["name"] for s in VIDEO_STEPS}
STEP_NAME["tts"] = TTS["name"]
STEP_NAME["mixcut"] = MIXCUT["name"]

TERMINAL_OK = ("completed", "success", "succeeded", "done")
TERMINAL_BAD = ("failed", "error", "cancelled", "canceled", "timeout", "expired")

# 上游对 videoUrl 的白名单（实测报错原文）
VIDEO_URL_HINT = ("videoUrl 必须是本站（vr.a7w.cn）、本站七牛"
                  "（cdn2.jiujiushuyuan.cn/vr/）或本站上传接口返回的地址"
                  "（oss.gpu.likeadmin.cn/openapi/）")


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


def http_json(method, url, key, body=None, timeout=120, retries=3):
    """发一次请求。GET 遇到 502/503/504 或网络抖动静默退避重试；
    POST 默认 retries=1，避免重复提交（提交类调用必须只发一次）。"""
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    last = None
    for attempt in range(max(1, retries)):
        req = urllib.request.Request(url, method=method, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < retries - 1:
                last = "HTTP %s" % e.code
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = getattr(e, "reason", e)
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise Fail("call", "连不上 %s：%s（已重试 %d 次）"
                       % (url, last, retries - 1), EXIT_CALL)
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


def url_allowed(u):
    """上游只收本站托管的地址。返回 (ok, 说明)。"""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:                                            # noqa: BLE001
        return False, "URL 解析失败"
    host = (p.hostname or "").lower()
    path = p.path or ""
    if host == "vr.a7w.cn" or host.endswith(".a7w.cn"):
        return True, "本站"
    if host == "cdn2.jiujiushuyuan.cn" and path.startswith("/vr/"):
        return True, "本站七牛"
    if host == "oss.gpu.likeadmin.cn" and path.startswith("/openapi/"):
        return True, "本站上传接口"
    return False, host or u[:60]


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
        if d.get("code"):
            return str(d["code"])[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


def fmt_pts(n):
    return "{:,}".format(int(round(float(n))))


def _w(s):
    """显示宽度：中日韩字符算 2 列，表格才对得齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


def dig_url(node, keys, depth=0):
    """在任意嵌套结构里找第一个 http(s) 地址。"""
    if depth > 6:
        return None
    if isinstance(node, dict):
        for k in keys:
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for v in node.values():
            r = dig_url(v, keys, depth + 1)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = dig_url(v, keys, depth + 1)
            if r:
                return r
    return None


VIDEO_KEYS = ("videoUrl", "video_url", "outputUrl", "output_url")
AUDIO_KEYS = ("audioUrl", "audio_url", "stream_audio_url", "url")
ARTIFACT_KEYS = ("artifactUrl", "artifact_url", "srtUrl", "srt_url")


# ───────────────────────── 价格与预估 ─────────────────────────
def _seconds(a):
    return max(1, int(getattr(a, "seconds", DEFAULT_SECONDS) or DEFAULT_SECONDS))


def _chars(a):
    explicit = getattr(a, "chars", None)
    if explicit:
        return max(1, int(explicit))
    t = (getattr(a, "text", None) or "").strip()
    return max(1, len(t)) if t else DEFAULT_CHARS


def unit_label(step):
    if step in VIDEO_STEPS:
        m = VIDEO_STEPS[step]
        return "点/秒" if m["unit"] == "per_second" else "点/次"
    if step == "tts":
        return "点/字（约）"
    return "点/秒（保底 45）"


def estimate_step(step, seconds, chars):
    """返回 (点数, 口径说明)。"""
    seconds = max(1, int(seconds))
    chars = max(1, int(chars))
    if step in VIDEO_STEPS:
        m = VIDEO_STEPS[step]
        if m["unit"] == "per_second":
            pts = m["points"] * seconds
            return pts, "%d 点/秒 × %d 秒 = %d 点" % (m["points"], seconds, pts)
        alt = m["points"] * seconds
        return m["points"], ("%d 点/次（与时长无关；若引擎按 per_second 结算则为 "
                             "%d × %d = %d 点）" % (m["points"], m["points"], seconds, alt))
    if step == "tts":
        pts = max(TTS["min_points"], int(math.ceil(chars * TTS["points_per_char"])))
        return pts, ("约 %.2f 点/字 × %d 字 = %d 点（保底 %d 点；上游实际点数 x3，"
                     "以 usage.points_cost 结算）"
                     % (TTS["points_per_char"], chars, pts, TTS["min_points"]))
    pts = max(MIXCUT["min_points"],
              int(math.ceil(MIXCUT["points_per_second"] * seconds)))
    return pts, ("%.1f 点/秒 × %d 秒 = %d 点（保底 %d 点）"
                 % (MIXCUT["points_per_second"], seconds, pts, MIXCUT["min_points"]))


def _gate(a, cost, what):
    """两道闸门：预算不够 -> 5（一个请求都不发）；没 --yes -> 4。"""
    if cost > a.budget:
        raise Fail("budget", "预计 %d 点（约 %.2f 元）超过 --budget %d 点（%s）。"
                             "一个请求都没发。调大 --budget（单位：点）或缩小 --seconds / --chars。"
                   % (cost, cost / float(POINTS_PER_YUAN), a.budget, what), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实提交并预冻结约 %d 点（约 %.2f 元）：%s。确认请加 --yes。"
                   % (cost, cost / float(POINTS_PER_YUAN), what), EXIT_CONFIRM)
    return cost


def _parse_boxes(s):
    """'0.05,0.05,0.2,0.1' -> [{'X':0.05,'Y':0.05,'W':0.2,'H':0.1}]（0~1 占比）。"""
    parts = [x.strip() for x in str(s or "").replace(";", ",").split(",") if x.strip()]
    if len(parts) != 4:
        raise Fail("usage", "--boxes 要 4 个 0~1 的数字：X,Y,W,H（例如 0.05,0.05,0.2,0.1）",
                   EXIT_USAGE)
    try:
        vals = [float(x) for x in parts]
    except ValueError:
        raise Fail("usage", "--boxes 四个值都必须是数字", EXIT_USAGE)
    for v in vals:
        if v < 0 or v > 1:
            raise Fail("usage", "--boxes 每个值都要在 0~1 之间（画面占比）", EXIT_USAGE)
    return [{"X": vals[0], "Y": vals[1], "W": vals[2], "H": vals[3]}]


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    rows = [{"step": "upload", "name": "上传素材", "points": 0, "unit": "免费",
             "endpoint": "POST " + UPLOAD_PATH,
             "desc": "拿一个白名单地址（最长 24 小时），后面的工位都用它"}]
    for s in STEP_ORDER:
        if s in VIDEO_STEPS:
            m = VIDEO_STEPS[s]
            rows.append({"step": s, "name": m["name"], "points": m["points"],
                         "unit": unit_label(s),
                         "endpoint": "POST " + API_PREFIX + "/video/viapi/" + s,
                         "desc": m["desc"]})
        elif s == "tts":
            rows.append({"step": s, "name": TTS["name"], "points": None,
                         "unit": "上游 x3（约 0.18 点/字）",
                         "endpoint": "POST " + API_PREFIX + "/apps/voice_tts/tts_async",
                         "desc": TTS["desc"]})
        else:
            rows.append({"step": s, "name": MIXCUT["name"],
                         "points": MIXCUT["points_per_second"],
                         "unit": "点/秒（保底 45）",
                         "endpoint": "POST " + API_PREFIX + "/apps/smart_clip/broadcast_mixcut",
                         "desc": MIXCUT["desc"]})
    out = {"ok": True, "count": len(rows), "steps": rows,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "order": STEP_ORDER, "priceSource": PRICING_PATH}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("短剧二创一条龙 —— 6 个工位 + 上传（1 元 = 100 点）")
    print()
    print("  %s %s %s %s" % (pad("--step", 10), pad("工位", 24), pad("单价", 28), "干什么"))
    print("  " + "-" * 104)
    for r in rows:
        price = ("免费" if r["points"] == 0 else
                 (r["unit"] if r["points"] is None else "%s %s" % (r["points"], r["unit"])))
        print("  %s %s %s %s" % (pad(r["step"], 10), pad(r["name"], 24),
                                 pad(price, 28), r["desc"]))
    print()
    print("  端点： %s/video/viapi/<step>（4 个视频工位）" % API_PREFIX)
    print("         %s/apps/voice_tts/tts_async · %s/apps/smart_clip/broadcast_mixcut" %
          (API_PREFIX, API_PREFIX))
    print("  查询： GET %s/video/viapi/result/<taskId>（视频）· GET %s/tasks/<taskId>（应用）"
          % (API_PREFIX, API_PREFIX))
    print("  一趟 60 秒片 + 200 字解说 = 1,796 点 = 17.96 元（cost 可以自己改秒数/字数算）")
    return 0


def cmd_cost(a, key, host):
    seconds, chars = _seconds(a), _chars(a)
    steps = [a.step] if a.step else list(STEP_ORDER)
    rows, total = [], 0
    for s in steps:
        pts, basis = estimate_step(s, seconds, chars)
        total += pts
        rows.append({"step": s, "name": STEP_NAME[s], "points": pts,
                     "unit": unit_label(s), "basis": basis})
    out = {"ok": True, "seconds": seconds, "chars": chars,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN, "steps": rows,
           "total": total, "yuan": round(total / float(POINTS_PER_YUAN), 2),
           "anchors": {
               "subtitle": {"s30": 9 * 30, "s60": 9 * 60, "s180": 9 * 180},
               "enhance": {"s30": 15 * 30, "s60": 15 * 60, "s180": 15 * 180},
               "castcrew": {"perCall": 25}, "delogo": {"perCall": 25},
               "tts": {"c100": 18, "c500": 90, "c1000": 180},
               "mixcut": {"s15": 68, "s60": 270, "s180": 810}},
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-07 实测）",
               "castcrew / delogo 价签写「点/次」，引擎规则却是 per_second —— 本包按价签计一次，"
               "以实际账单为准",
               "TTS 对外价 = 上游实际点数 x3；实测 33 字上游 1.98 点 -> 5.94 点，约 0.18 点/字",
               "mixcut 按输出秒数 4.5 点/秒，无时长时按 45 点预估",
               "任务失败平台全额退回；按秒工位先按秒数冻结、完成后按实际时长结算"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）· 按 %d 秒 / %d 字算" % (seconds, chars))
    print()
    print("  %s %s %s  %s" % (pad("--step", 10), pad("工位", 24), pad("点数", 12, False), "口径"))
    print("  " + "-" * 96)
    for r in rows:
        print("  %s %s %s  %s" % (pad(r["step"], 10), pad(r["name"], 24),
                                  pad(fmt_pts(r["points"]), 12, False), r["basis"][:60]))
    print()
    print("  合计：%s 点 = %.2f 元" % (fmt_pts(total), total / float(POINTS_PER_YUAN)))
    print()
    print("  常用锚点（点）：")
    print("    subtitle 9 点/秒    30 秒 270 · 60 秒 540 · 180 秒 1,620")
    print("    enhance 15 点/秒    30 秒 450 · 60 秒 900 · 180 秒 2,700")
    print("    castcrew / delogo   25 点/次（与时长无关）")
    print("    tts 约 0.18 点/字   100 字 18 · 500 字 90 · 1,000 字 180")
    print("    mixcut 4.5 点/秒    15 秒 68 · 60 秒 270 · 180 秒 810（保底 45）")
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("Key + 余额接口可达", st == 200,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, fmt_pts(d.get("available_points") or d.get("points") or 0),
                       fmt_pts(d.get("frozen") or 0))))

    st_p, txt_p = http_json("GET", host + PRICING_PATH, key, timeout=60)
    pr = {}
    if st_p == 200:
        pr = (jloads(txt_p) or {}).get("pricing") or {}
    checks.append(("价目表 GET /pricing 可达", st_p == 200 and bool(pr),
                   "HTTP %s · %d 条规则" % (st_p, len(pr))))

    drift = []
    for s in VIDEO_STEPS:
        live = (pr.get(API_PREFIX + "/video/viapi/" + s) or {}).get("perSecond")
        if live is None:
            drift.append("%s 线上无此键" % s)
        elif int(live) != VIDEO_STEPS[s]["points"]:
            drift.append("%s 本地 %d / 线上 %s" % (s, VIDEO_STEPS[s]["points"], live))
    for label, path, want in (("smart_clip", API_PREFIX + "/apps/smart_clip/*", 4.5),
                              ("voice_tts", API_PREFIX + "/apps/voice_tts/*", None)):
        row = pr.get(path) or {}
        if not row:
            drift.append("%s 线上无规则" % label)
        elif want is not None and float(row.get("perSecond") or 0) != float(want):
            drift.append("%s 线上 perSecond=%s" % (label, row.get("perSecond")))
    checks.append(("6 个工位单价与 /api/v1/pricing 一致", not drift,
                   "全一致" if not drift else " / ".join(drift)[:120]))

    for s in ("castcrew", "delogo", "subtitle", "enhance"):
        say("  探 %-9s %s/video/viapi/%s …" % (s, API_PREFIX, s))
        st2, txt2 = http_json("POST", host + API_PREFIX + "/video/viapi/" + s, key, {},
                              timeout=a.timeout)
        d2 = jloads(txt2) or {}
        e2 = d2.get("error") if isinstance(d2.get("error"), dict) else {}
        code = e2.get("code") or ""
        checks.append(("视频工位 %-9s 可用（400 empty_url 即正确）" % s,
                       st2 == 400 and code == "empty_url",
                       "HTTP %s %s" % (st2, code or err_text(st2, txt2)[:40])))

    st3, txt3 = http_json("GET", host + VIDEO_RESULT + "probe-no-such-task", key, timeout=40)
    d3 = jloads(txt3) or {}
    code3 = ((d3.get("error") or {}) if isinstance(d3.get("error"), dict) else {}).get("code") or ""
    checks.append(("视频查询 GET /video/viapi/result/{id} 可达（404 not_found 即正确）",
                   st3 == 404 and code3 == "not_found",
                   "HTTP %s %s" % (st3, code3 or err_text(st3, txt3)[:40])))

    st4, txt4 = http_json("GET", host + TASK_PATH + "probe-no-such-task", key, timeout=120)
    d4 = jloads(txt4) or {}
    checks.append(("应用查询 GET /tasks/{id} 可达（200 code 0「任务不存在」即正确）",
                   st4 == 200 and d4.get("code") == 0,
                   "HTTP %s %s" % (st4, (d4.get("msg") or "")[:40])))

    st5, txt5 = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=a.timeout)
    d5 = jloads(txt5) or {}
    checks.append(("上传 POST /upload 可达（不带 file 回 code 0 即正确）",
                   st5 == 200 and d5.get("code") == 0,
                   "HTTP %s %s" % (st5, (d5.get("msg") or "")[:40])))

    st6, txt6 = http_json("GET", host + APPS_PATH, key, timeout=60)
    d6 = jloads(txt6) or {}
    alist = d6.get("data") if isinstance(d6.get("data"), list) else []
    have = {}
    for it in alist:
        if not isinstance(it, dict):
            continue
        have[it.get("code")] = {a.get("code"): a.get("method")
                                for a in (it.get("apis") or []) if isinstance(a, dict)}
    ok_apps = (have.get("smart_clip", {}).get("broadcast_mixcut") == "POST"
               and have.get("voice_tts", {}).get("tts_async") == "POST")
    checks.append(("应用注册表 GET /apps：smart_clip/broadcast_mixcut + voice_tts/tts_async 在架",
                   st6 == 200 and ok_apps,
                   "HTTP %s · 共 %d 个应用" % (st6, len(alist))))

    out = {"ok": all(c[1] for c in checks), "host": host,
           "estimatedPoints": 0, "yuan": 0.0,
           "endpoints": {"video": API_PREFIX + "/video/viapi/<step>",
                         "tts": API_PREFIX + "/apps/voice_tts/tts_async",
                         "mixcut": API_PREFIX + "/apps/smart_clip/broadcast_mixcut",
                         "queryVideo": VIDEO_RESULT + "<taskId>",
                         "queryApp": TASK_PATH + "<taskId>"},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print()
    print("自检（不扣费：只读 GET + 空 body 探针，任务 0 条、冻结 0 点）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 52), dt))
    print()
    print("  视频：POST %s/video/viapi/<castcrew|delogo|subtitle|enhance>" % API_PREFIX)
    print("  应用：POST %s/apps/voice_tts/tts_async · %s/apps/smart_clip/broadcast_mixcut"
          % (API_PREFIX, API_PREFIX))
    print("  查询：GET %s/video/viapi/result/<id>（视频）· GET %s/tasks/<id>（应用）"
          % (API_PREFIX, API_PREFIX))
    print("  应用层两个 submit 不在这里探：它们走 reserve_sync，缺参数会先冻结再全额退。")
    print("  本轮自检花费 0 点。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 上传 / 模板 ─────────────────────────
def do_upload(a, key, host, quiet=False):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（要上传的视频路径）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + UPLOAD_PATH
    if not quiet:
        say("  上传 %s（%d 字节）…" % (os.path.basename(path), size))
    t0 = time.time()
    st, txt = http_multipart(url, key, {}, [("file", path)], timeout=getattr(a, "timeout", 600))
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    ok_url, kind = url_allowed(got)
    if not quiet:
        say("  已上传（%.1fs）· %s · 白名单内：%s"
            % (dt, kind, "是" if ok_url else "否"))
    return got, {"url": got, "size": data.get("size") or size,
                 "type": data.get("type"), "mime": data.get("mime_type"),
                 "hostKind": kind, "elapsed": round(dt, 1)}


def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（要上传的视频路径）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + UPLOAD_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": path, "size": size}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传）")
        print("  端点：POST %s（multipart/form-data，字段名 file）" % url)
        print("  文件：%s（%d 字节）" % (path, size))
        return 0
    got, meta = do_upload(a, key, host)
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "upload",
                "file": path, "size": size, "url": got})
    out = dict(meta)
    out.update({"ok": True, "path": got, "file": path})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（%.1fs）" % meta.get("elapsed", 0))
    print("  地址：%s" % got)
    print("  类型：%s · %s · %d 字节" % (meta.get("type"), meta.get("mime"),
                                        meta.get("size") or size))
    print("  归属：%s（白名单内，可直接给 run 用；最长 24 小时）" % meta.get("hostKind"))
    print()
    print("  下一步：python3 scripts/run.py run --step subtitle --video-url \"%s\" --yes" % got)
    return 0


def cmd_template(a, key, host):
    q = ("%s/apps/smart_clip/template?scene=oralMixCutting&pageSize=%d"
         % (API_PREFIX, max(1, min(int(a.page_size), 20))))
    if a.search:
        q += "&searchKey=name&searchValue=" + urllib.parse.quote(a.search)
    url = host + q
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "note": "免费查询；会先冻 50 点再全额退"}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不查询）")
        print("  端点：GET %s" % url)
        print("  说明：免费查询；平台会先冻结 50 点再全额退回，净 0 点。")
        return 0
    st, txt = http_json("GET", url, key, timeout=90)
    d = jloads(txt) or {}
    if st != 200 or d.get("code") not in (1, 200):
        raise Fail("call", "模板列表拉取失败（HTTP %s）：%s" % (st, err_text(st, txt)),
                   EXIT_CALL)
    data = d.get("data") or {}
    inner = data.get("result") if isinstance(data.get("result"), dict) else {}
    body = inner.get("data") if isinstance(inner.get("data"), dict) else {}
    items = body.get("results") or data.get("results") or []
    rows = [{"id": it.get("id"), "name": it.get("name"), "ratio": it.get("ratio"),
             "scene": it.get("scene"), "coverUrl": it.get("coverUrl"),
             "demoUrl": it.get("demoUrl")} for it in items if isinstance(it, dict)]
    out = {"ok": True, "count": len(rows), "templates": rows,
           "scene": "oralMixCutting", "estimatedPoints": 0,
           "note": "免费查询；平台先冻 50 点再全额退，净 0 点"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("素材混剪模板（scene=oralMixCutting）· %d 个" % len(rows))
    print()
    for i, r in enumerate(rows, 1):
        print("  #%d %s" % (i, r.get("name") or "-"))
        print("      styleId：%s%s" % (r.get("id"), "   比例：%s" % r.get("ratio")
                                       if r.get("ratio") else ""))
    print()
    print("  用法：run --all --file 素材.mp4 --style-id %s --yes"
          % (rows[0]["id"] if rows else "<styleId>"))
    print("  说明：查询免费；平台会先冻结 50 点再全额退回，净 0 点。")
    return 0


# ───────────────────────── 提交与轮询 ─────────────────────────
def _video_body(a, step, url, seconds):
    body = {"videoUrl": url}
    if VIDEO_STEPS[step]["unit"] == "per_second":
        body["duration"] = int(seconds)
    if step == "delogo" and getattr(a, "boxes", None):
        body["boxes"] = _parse_boxes(a.boxes)
    return body


def _tts_body(a):
    body = {"text": a.text, "model": a.tts_model or DEFAULT_TTS_MODEL,
            "format": a.tts_format or "mp3"}
    if a.voice_id:
        body["reference_id"] = a.voice_id
    return body


def _mixcut_body(a, video_url, audio_url):
    body = {"styleId": a.style_id, "language": a.language,
            "materials": [{"type": "video", "fileUrl": video_url, "soundSwitch": False}]}
    if a.title:
        body["title"] = a.title
    if audio_url:
        body["audioUrl"] = audio_url
    return body


def _submit_video(a, key, host, step, body):
    path = API_PREFIX + "/video/viapi/" + step
    st, txt = http_json("POST", host + path, key, body, timeout=a.timeout, retries=1)
    d = jloads(txt) or {}
    if isinstance(d.get("data"), dict) and d.get("code") in (1, 200):
        d = d["data"]
    if st not in (200, 201) or d.get("code") == 0:
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    tid = d.get("taskId") or d.get("task_id") or d.get("id")
    if not tid:
        raise Fail("call", "提交返回里没有 taskId。原始返回：%s" % (txt or "")[:300], EXIT_CALL)
    return tid, d, path


def _submit_app(a, key, host, app, api, body):
    path = API_PREFIX + "/apps/" + app + "/" + api
    st, txt = http_json("POST", host + path, key, body, timeout=a.timeout, retries=1)
    d = jloads(txt) or {}
    if st != 200:
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if d.get("code") not in (1, 200, None):
        raise Fail("call", "上游拒绝：%s" % err_text(st, txt), EXIT_CALL)
    data = d.get("data") if isinstance(d.get("data"), dict) else d
    tid = data.get("task_id") or data.get("taskId") or data.get("id")
    if not tid:
        raise Fail("call", "提交返回里没有 task_id。原始返回：%s" % (txt or "")[:300], EXIT_CALL)
    return tid, data, path


def _status_of(d):
    return str(d.get("status") or "").lower()


def _poll(a, key, host, kind, task_id):
    deadline = time.time() + max(30, int(a.wait))
    last, bad = None, 0
    while time.time() < deadline:
        if kind == "video":
            st, txt = http_json("GET", host + VIDEO_RESULT + task_id, key, timeout=60)
            d = jloads(txt) or {}
        else:
            st, txt = http_json("GET", host + TASK_PATH + task_id, key, timeout=120)
            d = jloads(txt) or {}
            if isinstance(d.get("data"), dict):
                d = d["data"]
        s = _status_of(d)
        if s and s != last:
            say("    状态：%s" % s)
            last = s
        if s in TERMINAL_OK:
            return d
        if s in TERMINAL_BAD:
            bad += 1
            if bad >= 2:
                return d
            say("    状态 %s，平台可能自动重试，30 秒后再看一次…" % s)
            time.sleep(30)
            continue
        time.sleep(max(1, int(a.every)))
    raise Fail("call", "等 %d 秒还没完成。任务没丢：`run.py status --task-id %s` 接着查，"
                       "不要重新提交（会再扣一次）。" % (a.wait, task_id), EXIT_CALL)


def _billed(d):
    for k in ("cost", "points", "chargedPoints"):
        if d.get(k) is not None:
            return d.get(k)
    usage = d.get("usage") if isinstance(d.get("usage"), dict) else {}
    for k in ("points_cost", "pointsCost", "total_points"):
        if usage.get(k) is not None:
            return usage.get(k)
    return None


# ───────────────────────── run：分步 / 全链 ─────────────────────────
def _check_step(a, step):
    has_video = bool(a.video_url or a.file)
    if step in VIDEO_STEPS and not has_video:
        raise Fail("usage", "--step %s 需要 --video-url（先 upload 拿白名单地址）或 --file" % step,
                   EXIT_USAGE)
    if step == "tts" and not (a.text or "").strip():
        raise Fail("usage", "--step tts 需要 --text（要合成的解说词；--script 同义）", EXIT_USAGE)
    if step == "mixcut":
        if not a.style_id:
            raise Fail("usage", "--step mixcut 需要 --style-id（先跑 template 拿模板 ID）",
                       EXIT_USAGE)
        if not has_video:
            raise Fail("usage", "--step mixcut 需要 --video-url 或 --file（混剪素材）",
                       EXIT_USAGE)


def _plan(a):
    has_video = bool(a.video_url or a.file)
    skip = set(x.strip() for x in (a.skip or "").split(",") if x.strip())
    steps = []
    for s in STEP_ORDER:
        if s in skip:
            continue
        if s in VIDEO_STEPS and not has_video:
            continue
        if s == "tts" and not (a.text or "").strip():
            continue
        if s == "mixcut" and not (a.style_id and has_video):
            continue
        steps.append(s)
    return steps


def _preview(a, step, video_url, audio_url, seconds):
    if step in VIDEO_STEPS:
        return {"method": "POST",
                "path": API_PREFIX + "/video/viapi/" + step,
                "body": _video_body(a, step, video_url, seconds)}
    if step == "tts":
        return {"method": "POST", "path": API_PREFIX + "/apps/voice_tts/tts_async",
                "body": _tts_body(a)}
    return {"method": "POST", "path": API_PREFIX + "/apps/smart_clip/broadcast_mixcut",
            "body": _mixcut_body(a, video_url, audio_url)}


NEXT_HINT = {
    "castcrew": "run --step delogo --video-url <原片地址> --yes（认演员表只出 SRT，不改主视频）",
    "delogo": "run --step subtitle --video-url <上一步的 videoUrl> --yes",
    "subtitle": "run --step enhance --video-url <上一步的 videoUrl> --yes",
    "enhance": "run --step tts --text \"解说词\" --yes（再拿音频去 mixcut）",
    "tts": "run --step mixcut --video-url <素材> --audio-url <上一步的音频> --style-id <模板> --yes",
    "mixcut": "成片已出，记得及时转存（链接约 30 分钟有效）",
}


def _precheck(a, steps):
    """发请求前先做本地校验，省掉一次必然失败的调用。"""
    if a.file and not os.path.isfile(a.file):
        raise Fail("usage", "文件不存在：%s" % a.file, EXIT_USAGE)
    if a.video_url and not re.match(r"^https?://", a.video_url, re.I):
        raise Fail("usage", "--video-url 要以 http:// 或 https:// 开头", EXIT_USAGE)
    if a.audio_url and not re.match(r"^https?://", a.audio_url, re.I):
        raise Fail("usage", "--audio-url 要以 http:// 或 https:// 开头", EXIT_USAGE)
    if (a.video_url and not a.file and not a.dry_run and not a.allow_any_url
            and any(s in VIDEO_STEPS for s in steps)):
        ok, kind = url_allowed(a.video_url)
        if not ok:
            raise Fail("usage",
                       "--video-url 不在白名单（%s）。三种可用写法：\n"
                       "  · 先传再跑（推荐）：python3 scripts/run.py upload --file 你的素材.mp4\n"
                       "  · 本站成片：https://vr.a7w.cn/result/xxx.mp4\n"
                       "  · 本站七牛：https://cdn2.jiujiushuyuan.cn/vr/xxx.mp4\n"
                       "%s" % (kind, VIDEO_URL_HINT), EXIT_USAGE)


def cmd_run(a, key, host):
    if a.step and a.all:
        raise Fail("usage", "--step 与 --all 二选一", EXIT_USAGE)
    if not a.step and not a.all:
        raise Fail("usage", "用 --step 指定某一步，或 --all 把整条链跑完。"
                            "可用步骤：%s" % " / ".join(STEP_ORDER), EXIT_USAGE)
    if a.all and a.no_wait:
        raise Fail("usage", "--all 要等每一步出结果才能接下一步，不能配 --no-wait", EXIT_USAGE)

    seconds, chars = _seconds(a), _chars(a)
    if a.step:
        _check_step(a, a.step)
        steps = [a.step]
    else:
        steps = _plan(a)
        if not steps:
            raise Fail("usage", "--all 没有可跑的步骤：给 --file 或 --video-url；"
                                "配音要 --text；混剪要 --style-id", EXIT_USAGE)

    plan = [(s,) + estimate_step(s, seconds, chars) for s in steps]
    _precheck(a, steps)
    total = sum(p[1] for p in plan)
    what = " / ".join(steps)
    _gate(a, total, what)

    if a.dry_run:
        video_ph = a.video_url or ("<upload 返回的地址>" if a.file else "<缺 --video-url>")
        out = {"ok": True, "dryRun": True, "mode": "all" if a.all else "step",
               "seconds": seconds, "chars": chars, "estimatedPoints": total,
               "yuan": round(total / float(POINTS_PER_YUAN), 2), "steps": []}
        if a.file:
            out["upload"] = {"method": "POST", "path": UPLOAD_PATH, "file": a.file,
                             "note": "免费"}
        for s, pts, basis in plan:
            out["steps"].append({"step": s, "points": pts, "basis": basis,
                                 "request": _preview(a, s, video_ph, a.audio_url, seconds)})
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）· 共 %d 步" % len(plan))
        print()
        if a.file:
            print("  [0] POST %s  上传 %s（免费）" % (UPLOAD_PATH, a.file))
        for i, (s, pts, basis) in enumerate(plan, 1):
            req = _preview(a, s, video_ph, a.audio_url, seconds)
            print("  [%d] %-9s %s" % (i, s, req["method"] + " " + req["path"]))
            print("      请求：%s" % json.dumps(req["body"], ensure_ascii=False))
            print("      预估：%s 点 · %s" % (fmt_pts(pts), basis))
        print()
        print("  合计：%s 点 = %.2f 元（--budget %d 点）"
              % (fmt_pts(total), total / float(POINTS_PER_YUAN), a.budget))
        return 0

    results = []
    state = {"video": a.video_url, "audio": a.audio_url, "srt": None, "final": None}
    if a.file:
        say("上传素材（免费）…")
        state["video"], _meta = do_upload(a, key, host)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True,
                    "mode": "upload", "file": a.file, "url": state["video"]})

    for i, (s, pts, basis) in enumerate(plan, 1):
        say("[%d/%d] %s（%s）…" % (i, len(plan), s, STEP_NAME[s]))
        if s in VIDEO_STEPS:
            body = _video_body(a, s, state["video"], seconds)
            tid, resp, path = _submit_video(a, key, host, s, body)
        elif s == "tts":
            body = _tts_body(a)
            tid, resp, path = _submit_app(a, key, host, TTS["app"], TTS["api"], body)
        else:
            body = _mixcut_body(a, state["video"], state["audio"])
            tid, resp, path = _submit_app(a, key, host, MIXCUT["app"], MIXCUT["api"], body)
        say("    已提交 %s" % tid)

        if a.no_wait:
            rec = {"step": s, "taskId": tid, "status": "submitted",
                   "estimatedPoints": pts, "endpoint": path, "basis": basis}
            results.append(rec)
            ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True,
                        "mode": "submit", "step": s, "taskId": tid,
                        "estimatedPoints": pts, "endpoint": path})
            continue

        final = _poll(a, key, host, "video" if s in VIDEO_STEPS else "app", tid)
        st = _status_of(final)
        if st in TERMINAL_BAD:
            msg = final.get("message") or final.get("error") or st
            ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                        "mode": "submit", "step": s, "taskId": tid,
                        "status": st, "error": str(msg)[:200], "endpoint": path})
            raise Fail("call", "第 %d 步 %s 失败：%s（失败任务平台全额退回；"
                               "`run.py status --task-id %s` 可复查）"
                       % (i, s, str(msg)[:200], tid), EXIT_CALL)

        billed = _billed(final)
        rec = {"step": s, "taskId": tid, "status": st, "endpoint": path,
               "estimatedPoints": pts, "billedPoints": billed,
               "videoUrl": None, "artifactUrl": None, "audioUrl": None,
               "message": final.get("message")}
        if s in VIDEO_STEPS:
            v = dig_url(final, VIDEO_KEYS)
            art = dig_url(final, ARTIFACT_KEYS)
            if v:
                state["video"] = v
                rec["videoUrl"] = v
            if art:
                state["srt"] = art
                rec["artifactUrl"] = art
        elif s == "tts":
            au = dig_url(final, AUDIO_KEYS)
            if au:
                state["audio"] = au
                rec["audioUrl"] = au
        else:
            v = dig_url(final, VIDEO_KEYS)
            if v:
                state["final"] = v
                rec["videoUrl"] = v
        results.append(rec)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True,
                    "mode": "submit", "step": s, "taskId": tid, "status": st,
                    "estimatedPoints": pts, "billedPoints": billed,
                    "endpoint": path})
        say("    完成 %s" % st)

    out = {"ok": True, "mode": "all" if a.all else "step",
           "seconds": seconds, "chars": chars, "estimatedPoints": total,
           "yuan": round(total / float(POINTS_PER_YUAN), 2),
           "steps": results,
           "videoUrl": state["video"],
           "audioUrl": state["audio"],
           "srtUrl": state["srt"],
           "finalVideoUrl": state["final"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print()
    print("完成 %d 步（预估 %s 点 = %.2f 元）"
          % (len(results), fmt_pts(total), total / float(POINTS_PER_YUAN)))
    print()
    print("  %s %s %s %s" % (pad("步骤", 10), pad("任务号", 26), pad("状态", 11), "产出"))
    print("  " + "-" * 92)
    for r in results:
        prod = r.get("videoUrl") or r.get("audioUrl") or r.get("artifactUrl") or "-"
        print("  %s %s %s %s" % (pad(r["step"], 10), pad(r["taskId"], 26),
                                 pad(r["status"], 11), str(prod)[:48]))
    print()
    if state["srt"]:
        print("  演员表 SRT：%s（30 分钟有效）" % state["srt"])
    if state["audio"]:
        print("  解说音频：%s" % state["audio"])
    if state["final"]:
        print("  最终成片：%s（链接约 30 分钟有效，及时转存）" % state["final"])
    elif state["video"] and state["video"] != a.video_url:
        print("  当前视频：%s（下一步拿它继续）" % state["video"])
    if a.step:
        print()
        print("  下一步：python3 scripts/run.py %s" % NEXT_HINT.get(a.step, ""))
    print("  查任务：python3 scripts/run.py status --task-id %s --step %s"
          % (results[-1]["taskId"], results[-1]["step"]))
    return 0


# ───────────────────────── status / log ─────────────────────────
def cmd_status(a, key, host):
    tid = a.task_id
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    if a.step in VIDEO_STEPS:
        order = ["video", "app"]
    elif a.step:
        order = ["app", "video"]
    else:
        order = ["video", "app"]
    hit = None
    for kind in order:
        if kind == "video":
            st, txt = http_json("GET", host + VIDEO_RESULT + tid, key, timeout=60)
            d = jloads(txt) or {}
            if st == 200 and (d.get("taskId") or d.get("status")):
                hit = ("video", d, VIDEO_RESULT + tid)
                break
        else:
            st, txt = http_json("GET", host + TASK_PATH + tid, key, timeout=120)
            d = jloads(txt) or {}
            if isinstance(d.get("data"), dict):
                d = d["data"]
            if d.get("task_id") or (d.get("status") and d.get("status") != "not_found"):
                hit = ("app", d, TASK_PATH + tid)
                break
    if not hit:
        raise Fail("call", "查不到任务 %s（视频 / 应用两条查询路由都说不存在）。"
                           "确认 taskId 没抄错，或加 --step 指定类别。" % tid, EXIT_CALL)
    kind, d, path = hit
    st = _status_of(d)
    video = dig_url(d, VIDEO_KEYS)
    artifact = dig_url(d, ARTIFACT_KEYS)
    audio = dig_url(d, AUDIO_KEYS) if kind == "app" else None
    billed = _billed(d)
    out = {"ok": True, "taskId": tid, "kind": kind, "path": path, "status": st,
           "tool": d.get("tool") or d.get("model") or d.get("api"),
           "message": d.get("message") or d.get("msg"),
           "videoUrl": video, "artifactUrl": artifact, "audioUrl": audio,
           "billedPoints": billed, "refund": d.get("refund"),
           "duration": d.get("duration"), "result": d.get("result"),
           "error": d.get("error")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  查询路径：%s" % path)
    if out["tool"]:
        print("  能力：%s" % out["tool"])
    print("  状态：%s" % (st or "?"))
    if billed is not None:
        print("  实扣：%s 点" % fmt_pts(billed))
    if d.get("refund") is not None:
        print("  退回：%s 点" % d.get("refund"))
    if out["message"]:
        print("  说明：%s" % str(out["message"])[:300])
    if video:
        print("  视频：%s（链接约 30 分钟有效，及时转存）" % video)
    if artifact:
        print("  附件：%s" % artifact)
    if audio:
        print("  音频：%s" % audio)
    if d.get("error"):
        print("  错误：%s" % json.dumps(d.get("error"), ensure_ascii=False)[:300])
    if d.get("result") is not None:
        print("  结果：%s" % json.dumps(d.get("result"), ensure_ascii=False)[:600])
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
        mode = e.get("mode") or e.get("step") or "-"
        what = e.get("taskId") or (os.path.basename(e.get("file") or "") if e.get("file")
                                   else (e.get("error") or "")[:40]) or "-"
        pts = e.get("billedPoints")
        if pts is None:
            pts = e.get("estimatedPoints")
        print("  %s  %s %s %s %s %s" % (
            e.get("at"), pad("ok" if e.get("ok") else "fail", 6),
            pad(mode, 9), pad(e.get("step") or "-", 10), pad(what[:26], 26),
            ("%s 点" % fmt_pts(pts)) if pts is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 短剧二创一条龙（认演员表 → 去台标 → 擦字幕 → 提画质 → 解说配音 → 模板混剪）",
        epilog="端点：POST %s/api/v1/video/viapi/<step> · POST %s/api/v1/apps/voice_tts/tts_async · "
               "POST %s/api/v1/apps/smart_clip/broadcast_mixcut · POST %s/api/v1/upload · "
               "GET %s/api/v1/video/viapi/result/<id> · GET %s/api/v1/tasks/<id>"
               % ((DEFAULT_HOST,) * 6),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d = 30 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="6 个工位 + 单价 + 端点（免费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：按秒数/字数算一趟（免费）", allow_abbrev=False)
    p.add_argument("--step", choices=STEP_ORDER, help="只算这一步（默认全部）")
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="视频秒数（默认 %d，按秒计费与预估都用它）" % DEFAULT_SECONDS)
    p.add_argument("--chars", type=int, default=DEFAULT_CHARS,
                   help="解说字数（默认 %d；给了 --text 时自动按文本长度）" % DEFAULT_CHARS)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 价目 / 6 个端点 / 查询 / 上传（免费）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("template", help="列混剪模板，拿 styleId（免费查，冻 50 退 50）",
                       allow_abbrev=False)
    p.add_argument("--page-size", type=int, default=10, help="每页几个（默认 10，上限 20）")
    p.add_argument("--search", help="按模板名搜索")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不查询")
    p.set_defaults(fn=cmd_template)

    p = sub.add_parser("upload", help="上传本地素材，拿白名单地址（免费）", allow_abbrev=False)
    p.add_argument("--file", help="本地视频路径（单文件默认 512 MB 上限）")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("run", help="--step 跑一步 / --all 全链跑完（要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--step", choices=STEP_ORDER,
                   help="只跑这一步：%s" % " / ".join(STEP_ORDER))
    p.add_argument("--all", action="store_true", help="按顺序把能跑的步骤全跑完")
    p.add_argument("--file", help="本地素材；--all 时先免费上传（优先于 --video-url）")
    p.add_argument("--video-url", help="平台托管的视频地址（先 upload 拿）")
    p.add_argument("--audio-url", help="解说音频地址（mixcut 用；--all 时自动接 tts 产物）")
    p.add_argument("--text", "--script", dest="text", help="解说词（tts / --all 用；同 --script）")
    p.add_argument("--style-id", help="混剪模板 ID（template 拿）")
    p.add_argument("--title", help="成片标题（不填就不显示标题）")
    p.add_argument("--language", default="zh-CN", help="语种（默认 zh-CN）")
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="视频秒数（默认 %d；按秒工位与 mixcut 的预估都用它）" % DEFAULT_SECONDS)
    p.add_argument("--chars", type=int, default=None,
                   help="解说字数（默认按 --text 长度；没给 --text 时按 %d）" % DEFAULT_CHARS)
    p.add_argument("--boxes", help="delogo 区域：X,Y,W,H（0~1 占比，缺省全画面）")
    p.add_argument("--voice-id", help="tts 音色 ID（reference_id，可选）")
    p.add_argument("--tts-model", default=DEFAULT_TTS_MODEL,
                   help="tts 模型（默认 %s，可选 s1）" % DEFAULT_TTS_MODEL)
    p.add_argument("--tts-format", default="mp3", choices=["mp3", "wav", "pcm", "opus"],
                   help="tts 输出格式（默认 mp3）")
    p.add_argument("--skip", default="", help="--all 时跳过某些步骤，逗号分隔，如 castcrew,tts")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把视频地址直接交给上游判断")
    p.add_argument("--yes", action="store_true", help="确认真实提交并冻结点数")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--no-wait", action="store_true", help="只提交拿 taskId 就走（只用于 --step）")
    p.add_argument("--wait", type=int, default=900, help="每步等结果的上限秒数（默认 900）")
    p.add_argument("--every", type=int, default=10, help="轮询间隔秒数（默认 10）")
    p.add_argument("--timeout", type=int, default=180, help="单次请求超时秒数（默认 180）")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("status", help="查任务（免费；视频 / 应用两条路由自动认）",
                       allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 taskId / task_id")
    p.add_argument("--step", choices=STEP_ORDER, help="知道是哪一步时填上，查得更准")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            if _n in _sp._option_string_actions:
                continue
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    key, host = load_conf(a.key, a.host)
    if not key and getattr(a.fn, "__name__", "") not in FREE:
        raise Fail("usage",
                   "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                   "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                   EXIT_USAGE)
    try:
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
