#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 口播矩阵（sanjianke-talking-matrix）

一段文案 x N 张形象 x M 个音色 = N x M 条口播。配音只做 M 次，视频才做 N x M 次。

## 一条流水线，三个应用（2026-11-07 实测）

  POST /api/v1/apps/voice_tts/tts        同步配音（<=500 字，直接回 audio_url）
  POST /api/v1/apps/pic_lipsync/submit   图片数字人（档位参数真名 quality）
  POST /api/v1/apps/image_human/submit   全驱数字人（mode 四档，必填）
  POST /api/v1/upload                    本地图上传（免费，字段名 file）
  GET  /api/v1/tasks/<task_id>           轮询（免费，唯一合法轮询线）

## 价格（GET /api/v1/pricing 现查，2026-11-07）

  /api/v1/apps/voice_tts/*         markupPercent=200  对外 = 上游实际点数 x 3
    实测锚点：tts_live 33 字 上游 1.98 点 -> 我方 5.94 点，折 0.18 点/字
  /api/v1/apps/pic_lipsync/submit  markupPercent=400  15 点/秒（上游 3 点/秒 x 5）
  /api/v1/apps/image_human/submit  fast 10 / standard 15 / 2k 30 / 4k 60 点/输入秒

  60 字文案约 14 秒，单条 210 点；3 形象 x 4 音色 = 12 条 2,564 点（25.64 元）。

## 两条用钱换来的纪律（做进了默认动作）

  1. 轮询只走 GET /api/v1/tasks/<id>。应用层 POST /apps/<app>/query 每调一次就是一次的钱
     （实测 nano_banana/query 72 点/次）。本包代码里没有 query 这条路。
  2. 付费 submit 只发一次，网络中断不自动重发 —— 重发就是再扣一次。重试只放在免费环节
     （上传、轮询）。中断的条目在 state 里记成 unknown，用 status 对账后再决定。

## 子命令

  catalog  矩阵规格 + 价目 + 两个引擎对照（免费）
  cost     先算钱：N x M 全链路（免费）
  doctor   自检 Key / 应用 / 三张速率卡 / 任务线（免费，一个 POST 都不发）
  voices   音色库（GET list_voices，先冻 150 点再全额退，净 0）
  tts      只做配音：文案 -> M 段音频（约 0.18 点/字/音色）
  run      矩阵主命令：上传 -> 配音 -> N x M 提交 -> 并发轮询 -> 按规范名落盘
  status   查单条，或整张矩阵的对账表（免费）
  log      本地台账（免费）

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --images 3 --voices 4 --chars 60
  python3 scripts/run.py doctor
  python3 scripts/run.py run --workdir ./matrix --images a.png --images b.png \\
      --voices model_a --voices model_b --content "..." --yes
  python3 scripts/run.py status --workdir ./matrix
  python3 scripts/run.py run --workdir ./matrix --yes      # 断点续跑，只补没跑完的

Key：`--key` -> 环境变量 A7W_API_KEY -> ~/.a7w/config.json。
需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
import math
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid


# ── GBK 编码兜底（2026-11-07 实测）──────────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 输出里只要有一个 cp936 编不出的字符就会 UnicodeEncodeError 崩掉。
# 先加 errors='replace' 兜底；正文只使用 √ × 这类 cp936 有的符号，金额写「元」。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
APP_TTS = "voice_tts"
APP_LIP = "pic_lipsync"
APP_HUMAN = "image_human"

POINTS_PER_YUAN = 100
CHARS_PER_SEC = 4.5             # 中文口播估算：约 4.5 字/秒
TTS_MARKUP = 3                  # voice_tts 通配规则：上游实际点数 x 3
TTS_POINTS_PER_CHAR = 0.18      # 实测折算：33 字 -> 5.94 点
LIPSYNC_RATE = 15               # pic_lipsync 15 点/秒（上游 3 x 5）
LIPSYNC_MIN = 50                # 公开文档的单笔保底，预估按它兜底不低估
HUMAN_RATES = {"fast": 10, "standard": 15, "2k": 30, "4k": 60}
RESERVE_TTS = 150               # voice_tts/* 实测预扣 150 点（失败全额退）
VOICE_TOTAL = 58                # list_voices 实测 total=58

QUALITIES = ["standard", "fast", "max"]
MODES = ["fast", "standard", "2k", "4k"]
ENGINES = ["lipsync", "human"]
MAX_SYNC_CHARS = 500            # voice_tts/tts 同步接口上限
DEFAULT_BUDGET = 5000           # 50 元
DEFAULT_CONCURRENCY = 2

STATE_NAME = "matrix-state.json"
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "talking-matrix-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-talking-matrix/%s" % VERSION

TERMINAL_OK = ("completed", "succeeded", "success", "done")
TERMINAL_BAD = ("failed", "error", "cancelled", "canceled", "timeout", "expired")

MEDIA_RE = re.compile(r"\.(mp4|mov|webm|m4v)(\?|#|$)", re.I)
MEDIA_KEYS = ("video_url", "video_uri", "output_url", "result_url", "video")
AUDIO_RE = re.compile(r"\.(mp3|wav|ogg|m4a|flac|opus)(\?|#|$)", re.I)

LOCK = threading.Lock()


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    with LOCK:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()


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
    """发一次请求。网络类错误与 5xx 退避重试；4xx 是业务错误，直接返回。

    **提交类调用传 retries=1** —— 5xx 时任务可能已经建了，重发就是再扣一次。
    """
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
                last = e
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise Fail("call", "连不上 %s：%s（已重试 %d 次）"
                       % (url, getattr(e, "reason", e), retries - 1), EXIT_CALL)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


def http_multipart(url, key, field, path, timeout=600, retries=2):
    """上传本地文件（免费）。手工拼 multipart，不依赖 requests。"""
    boundary = "----sanjianke" + uuid.uuid4().hex
    fn = os.path.basename(path)
    ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
    head = ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
            "Content-Type: %s\r\n\r\n" % (boundary, field, fn, ctype)).encode("utf-8")
    with open(path, "rb") as fh:
        payload = head + fh.read() + ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    hdr = {"Authorization": "Bearer " + key, "Accept": "application/json",
           "Content-Type": "multipart/form-data; boundary=" + boundary,
           "Content-Length": str(len(payload)), "User-Agent": UA}
    last = None
    for attempt in range(max(1, retries)):
        req = urllib.request.Request(url, method="POST", data=payload, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < retries - 1:
                last = e
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise Fail("call", "上传连不上 %s：%s" % (url, getattr(e, "reason", e)), EXIT_CALL)
    raise Fail("call", "上传失败 %s：%s" % (url, last), EXIT_CALL)


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
            bits = [e.get("message") or "", e.get("code") or "", e.get("param") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:300]
    return txt.replace("\n", " ")[:240]


def envelope(d):
    """平台信封：{"code":1,"msg":"success","data":{…}}；出错时 code=0 且 data=null。"""
    if not isinstance(d, dict):
        return False, "响应不是 JSON", None
    code = d.get("code")
    msg = d.get("msg") or d.get("message") or ""
    ok = (code == 1 or code == "1" or code is True) and d.get("data") is not None
    return ok, str(msg), d.get("data")


def find_media(obj, out=None, audio=False):
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and re.match(r"^https?://", v):
                hit = AUDIO_RE.search(v) if audio else MEDIA_RE.search(v)
                if hit or k in MEDIA_KEYS or (audio and "audio" in k.lower()):
                    if v not in out:
                        out.append(v)
            else:
                find_media(v, out, audio)
    elif isinstance(obj, list):
        for it in obj:
            find_media(it, out, audio)
    return out


def find_points(obj):
    if isinstance(obj, dict):
        u = obj.get("usage")
        if isinstance(u, dict):
            for k in ("points_cost", "actual_points", "points"):
                v = u.get(k)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        pass
        for v in obj.values():
            got = find_points(v)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for it in obj:
            got = find_points(it)
            if got is not None:
                return got
    return None


def dig_task(d):
    """返回 (status, payload)。'result' 是双重身份字段，别一路钻丢 status。"""
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(data, dict):
        return None, data
    status = data.get("status")
    node = data
    if not status:
        r = data.get("result")
        if isinstance(r, dict):
            if "code" in r:
                r2 = r.get("data")
                if isinstance(r2, dict):
                    node = r2
                    status = r2.get("status")
                else:
                    node = r2 if r2 is not None else r
            else:
                node = r
                status = r.get("status")
    return status, node


# ───────────────────────── 算钱 ─────────────────────────
def yuan(points):
    return round(float(points) / POINTS_PER_YUAN, 2)


def fmt_pts(n):
    return "{:,}".format(int(round(n)))


def chars_of(a):
    txt = a.content or ""
    if not txt and getattr(a, "content_file", None):
        if not os.path.isfile(a.content_file):
            raise Fail("usage", "--content-file 不存在：%s" % a.content_file, EXIT_USAGE)
        txt = io.open(a.content_file, encoding="utf-8").read()
    if not txt and getattr(a, "chars", None):
        txt = "字" * min(int(a.chars), 200000)   # 只算字数用
    return re.sub(r"\s+", "", txt)


def seconds_of(a, chars):
    if getattr(a, "seconds", None):
        return max(1, int(math.ceil(float(a.seconds))))
    if not chars:
        return 0
    return max(1, int(math.ceil(len(chars) / CHARS_PER_SEC)))


def tts_points(chars):
    if not chars:
        return 0
    return max(1, int(math.ceil(len(chars) * TTS_POINTS_PER_CHAR)))


def video_points(engine, seconds, mode=None):
    sec = max(1, int(math.ceil(float(seconds))))
    if engine == "human":
        return int(math.ceil(HUMAN_RATES[mode] * sec))
    return max(LIPSYNC_MIN, int(math.ceil(LIPSYNC_RATE * sec)))


def gate(a, cost, what):
    """两道闸门：预算（5）在前，确认（4）在后。任何请求都还没发。"""
    if cost > a.budget:
        raise Fail("budget",
                   "本次预计 %d 点（%.2f 元），超过 --budget %d 点。一个请求都没发。\n"
                   "调大 --budget（单位：点，1 元 = 100 点）或减少形象/音色/字数。"
                   % (cost, yuan(cost), a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实提交：%s，预计 **%d 点（%.2f 元）**。确认请加 --yes；"
                   "只想看请求用 --dry-run。" % (what, cost, yuan(cost)), EXIT_CONFIRM)
    return cost


# ───────────────────────── 状态（断点续跑）─────────────────────────
def state_path(a):
    if getattr(a, "state", None):
        return a.state
    return os.path.join(getattr(a, "workdir", ".") or ".", STATE_NAME)


def state_load(a):
    p = state_path(a)
    base = {"meta": {}, "images": {}, "tts": {}, "combos": {}}
    if not os.path.isfile(p):
        return base
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return base
    if not isinstance(d, dict):
        return base
    for k in base:
        if not isinstance(d.get(k), dict):
            d[k] = {}
    return d


def state_save(a, st):
    p = state_path(a)
    try:
        d = os.path.dirname(os.path.abspath(p))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        tmp = p + ".tmp"
        io.open(tmp, "w", encoding="utf-8", newline="\n").write(
            json.dumps(st, ensure_ascii=False, indent=1))
        os.replace(tmp, p)
    except Exception as e:                                       # noqa: BLE001
        say("  （state 写盘失败：%s）" % e)


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8")) or []
        arr.append(rec)
        d = os.path.dirname(LEDGER)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-300:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


def san(text, limit=40):
    s = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(text or "").strip())
    s = s.strip("._") or "x"
    return s[:limit]


def stem_of(path_or_url):
    base = os.path.basename(str(path_or_url).split("?")[0].rstrip("/"))
    return san(os.path.splitext(base)[0] or "img")


def text_sig(chars):
    """文案指纹：换了文案，配音与成片都不会被当成「已完成」复用。"""
    return hashlib.sha1((chars or "").encode("utf-8")).hexdigest()[:6]


def voice_key(ref, chars):
    return san("%s-%s" % (ref, text_sig(chars)), 40) if ref else san("audio", 40)


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    rows = [
        {"engine": "lipsync", "app": APP_LIP, "api": "submit",
         "path": API_PREFIX + "/apps/" + APP_LIP + "/submit",
         "price": "%d 点/秒" % LIPSYNC_RATE, "tier": "quality standard / fast / max",
         "params": ["image_url", "audio_url", "mode=audio", "quality", "prompt"],
         "probe": "缺 image_url 就停在校验层（但会先冻 250 点再退）"},
        {"engine": "human", "app": APP_HUMAN, "api": "submit",
         "path": API_PREFIX + "/apps/" + APP_HUMAN + "/submit",
         "price": "10 / 15 / 30 / 60 点/输入秒", "tier": "mode fast / standard / 2k / 4k",
         "params": ["file_url", "ref_file_url", "duration", "mode", "prompt"],
         "probe": "mode 不传时 schema 写 standard、计费卡写 fast"},
    ]
    combos = []
    for n, m in ((1, 1), (2, 2), (3, 4), (5, 6)):
        sec = 14
        p = m * tts_points("x" * 60) + n * m * video_points("lipsync", sec)
        combos.append({"images": n, "voices": m, "videos": n * m,
                       "points": p, "yuan": yuan(p)})
    out = {"ok": True, "engines": rows, "matrix": combos,
           "tts": {"app": APP_TTS, "api": "tts", "mode": "同步",
                   "limit": MAX_SYNC_CHARS, "pointsPerChar": TTS_POINTS_PER_CHAR,
                   "markup": TTS_MARKUP, "voiceTotal": VOICE_TOTAL,
                   "reserve": RESERVE_TTS},
           "upload": {"path": API_PREFIX + "/upload", "points": 0,
                      "note": "本地图先传平台临时地址，24 小时内有效"},
           "query": {"path": API_PREFIX + "/tasks/<task_id>", "points": 0,
                     "appLevelQuery": "本包不调用（每调一次就是一次的钱）"},
           "pointsPerYuan": POINTS_PER_YUAN,
           "naming": "输出名 {prefix}_{形象序号}-{形象名}_{音色}.mp4",
           "state": STATE_NAME + " 记录每一条的状态，重跑自动只补没跑完的"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 口播矩阵 —— 一段文案 x N 个形象 x M 个音色")
    print()
    print("  矩阵公式：配音 M 次（每个音色一次），视频 N x M 次。别把配音也乘上去。")
    print()
    print("  %-9s %-14s %-26s %s" % ("--engine", "应用", "报价", "档位参数"))
    print("  " + "-" * 92)
    print("  %-9s %-14s %-26s %s" % ("lipsync", APP_LIP, "%d 点/秒" % LIPSYNC_RATE,
                                     "quality standard / fast / max"))
    print("  %-9s %-14s %-26s %s" % ("human", APP_HUMAN, "10/15/30/60 点/输入秒",
                                     "mode fast / standard / 2k / 4k"))
    print()
    print("  配音：POST %s/apps/%s/tts（同步，%d 字以内）"
          % (API_PREFIX, APP_TTS, MAX_SYNC_CHARS))
    print("        %.2f 点/字，上游实际点数 x %d；音色库 %d 个"
          % (TTS_POINTS_PER_CHAR, TTS_MARKUP, VOICE_TOTAL))
    print("  上传：POST %s/upload 0 点/次（本地图先传，拿 oss.gpu.likeadmin.cn 地址）"
          % API_PREFIX)
    print("  轮询：GET  %s/tasks/<task_id> 0 点/次（应用层 query 本包不调用）"
          % API_PREFIX)
    print()
    print("  规模与预算（按 60 字约 14 秒、lipsync 引擎）")
    print("  %-10s %-8s %-9s %-12s %s" % ("形象", "音色", "成片", "点数", "元"))
    print("  " + "-" * 52)
    for r in combos:
        print("  %-10s %-8s %-9s %-12s %s"
              % ("x%d" % r["images"], "x%d" % r["voices"], "%d 条" % r["videos"],
                 fmt_pts(r["points"]), "%.2f" % r["yuan"]))
    print()
    print("  断点续跑：state 记着每条 combo 的 task_id 与成片，重跑只补没跑完的，")
    print("  配过音的音色不会重复付钱。")
    return 0


def cmd_cost(a, key, host):
    chars = chars_of(a)
    if not chars:
        raise Fail("usage", "要算钱得给 --content \"文案\" 或 --chars 字数", EXIT_USAGE)
    if len(chars) > MAX_SYNC_CHARS:
        raise Fail("usage",
                   "文案 %d 字，超过配音同步接口的 %d 字上限。拆成几段分别跑矩阵。"
                   % (len(chars), MAX_SYNC_CHARS), EXIT_USAGE)
    sec = seconds_of(a, chars)
    n, m = max(1, a.images), max(1, a.voices)
    if a.engine == "human" and not a.mode:
        raise Fail("usage",
                   "--engine human 必须给 --mode fast|standard|2k|4k。"
                   "不传 mode 时 schema 写 standard、计费卡写 fast，档位会跟账单对不上。",
                   EXIT_USAGE)

    per_tts = tts_points(chars)
    per_video = video_points(a.engine, sec, a.mode)
    tts_total = per_tts * m
    video_total = per_video * n * m
    total = tts_total + video_total

    table = []
    for ci in (1, 4, 12, 30, 60):
        p = ci * per_video + m * per_tts
        table.append({"videos": ci, "points": p, "yuan": yuan(p)})

    out = {"ok": True, "engine": a.engine, "chars": len(chars), "seconds": sec,
           "images": n, "voices": m, "videos": n * m,
           "perVoiceTtsPoints": per_tts, "perVideoPoints": per_video,
           "ttsPoints": tts_total, "videoPoints": video_total,
           "estimatedPoints": total, "yuan": yuan(total),
           "budget": a.budget, "overBudget": total > a.budget,
           "table": table,
           "basis": {"tts": "%.2f 点/字 x %d 字 x %d 音色" % (
                         TTS_POINTS_PER_CHAR, len(chars), m),
                     "video": ("%d 点/秒 x %d 秒 x %d 条"
                               % (LIPSYNC_RATE, sec, n * m)) if a.engine == "lipsync"
                     else ("%d 点/秒 x %d 秒 x %d 条"
                           % (HUMAN_RATES[a.mode], sec, n * m))},
           "notes": ["1 元 = 100 点",
                     "配音每个音色只做一次，矩阵里复用它 —— 这是矩阵最省的一刀",
                     "lipsync 口径 = 上游实际点数 x 5（上游 standard 3 点/秒），预估按 15 点/秒",
                     "lipsync 单笔保底 50 点按上限兜底，短文案不会被低估",
                     "最终以任务详情里的 usage.points_cost 为准"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）")
    print("  文案 %d 字 约 %d 秒 · %d 形象 x %d 音色 = %d 条"
          % (len(chars), sec, n, m, n * m))
    print()
    print("  配音  %-34s %s 点" % (out["basis"]["tts"], fmt_pts(tts_total)))
    print("  视频  %-34s %s 点" % (out["basis"]["video"], fmt_pts(video_total)))
    print("  " + "-" * 56)
    print("  合计  %-34s %s 点 = %.2f 元" % ("", fmt_pts(total), yuan(total)))
    print()
    print("  不同规模（同一段文案、每音色只配一次）")
    print("  %-10s %-12s %s" % ("成片条数", "点数", "元"))
    print("  " + "-" * 36)
    for r in table:
        print("  %-10s %-12s %s" % ("%d 条" % r["videos"], fmt_pts(r["points"]),
                                     "%.2f" % r["yuan"]))
    print()
    for n2 in out["notes"]:
        print("  · %s" % n2)
    if total > a.budget:
        print()
        print("  已超过 --budget %d 点，真实执行会退 5，一个请求都不发。" % a.budget)
    return 0


def cmd_doctor(a, key, host):
    """全部只读 GET，一个 POST 都不发。

    为什么连「缺必填」的 submit 也不发 —— 实测应用层 submit 是**先预扣再验参**：
    缺 image_url 也会产生「冻结 -250 -> 退款 +250」的一对流水，净 0 但钱包被动过。
    自检不该动钱包，所以端点存在性用 GET /apps 目录 + GET /pricing 的价目规则来证明。
    """
    checks = []

    st, txt = http_json("GET", host + "/user/balance", key, None, 40)
    d = jloads(txt) or {}
    checks.append(("Key 有效 + 余额可读", st == 200 and "available_points" in d,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点"
                   % (st, fmt_pts(d.get("available_points") or 0),
                      fmt_pts(d.get("frozen") or 0))))

    st_a, txt_a = http_json("GET", host + API_PREFIX + "/apps", key, None, 60)
    d_a = jloads(txt_a) or {}
    apps = d_a.get("data") if isinstance(d_a.get("data"), list) else []
    by = {}
    for it in apps:
        if isinstance(it, dict):
            by[it.get("code")] = [x.get("code") for x in (it.get("apis") or [])
                                  if isinstance(x, dict)]
    need = {APP_LIP: ["submit", "query"], APP_HUMAN: ["submit", "query"],
            APP_TTS: ["tts", "clone_voice", "list_voices"]}
    miss = []
    for app, apis in need.items():
        have = set(by.get(app) or [])
        for api_name in apis:
            if api_name not in have:
                miss.append("%s/%s" % (app, api_name))
    checks.append(("三个应用 + 八个接口在架", bool(by) and not miss,
                   "目录 %d 个应用%s" % (len(apps),
                                        "，缺 " + ",".join(miss) if miss else "")))

    # /api/v1/pricing 是**裸对象**（不套 code/data），直接读
    st_p, txt_p = http_json("GET", host + API_PREFIX + "/pricing", key, None, 60)
    d_p = jloads(txt_p) or {}
    pr = d_p.get("pricing") if isinstance(d_p.get("pricing"), dict) else d_p
    pr = pr if isinstance(pr, dict) else {}

    lip = pr.get("/api/v1/apps/pic_lipsync/submit") or {}
    ok_lip = int(lip.get("markupPercent") or 0) == 400
    checks.append(("价目：%s 15 点/秒（上游 x5）" % APP_LIP, ok_lip,
                   "markupPercent=%s · minPoints=%s"
                   % (lip.get("markupPercent"), lip.get("minPoints"))))

    hum = pr.get("/api/v1/apps/image_human/submit") or {}
    rates = hum.get("modelRates") or {}
    live = dict((k, (v or {}).get("*")) for k, v in rates.items()) if rates else {}
    ok_hum = bool(live) and all(live.get(k) == v for k, v in HUMAN_RATES.items())
    checks.append(("价目：%s 10/15/30/60 点/输入秒" % APP_HUMAN, ok_hum,
                   ("live=%s" % json.dumps(live, ensure_ascii=False)) if live
                   else "没读到 modelRates"))

    tts = pr.get("/api/v1/apps/voice_tts/*") or {}
    ok_tts = int(tts.get("markupPercent") or 0) == 200
    checks.append(("价目：%s 配音 x%d（%.2f 点/字）" % (APP_TTS, TTS_MARKUP,
                                                     TTS_POINTS_PER_CHAR),
                   ok_tts, "markupPercent=%s" % tts.get("markupPercent")))

    st_t, txt_t = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-doctor-probe",
                            key, None, 40)
    d_t = jloads(txt_t) or {}
    checks.append(("任务查询线 GET /tasks/{id} 可达（免费轮询）",
                   st_t == 200 and d_t.get("code") == 0
                   and "不存在" in str(d_t.get("msg") or ""),
                   "HTTP %s %s" % (st_t, str(d_t.get("msg") or "")[:40])))

    if a.probe_voices:
        say("  探音色库（GET，实测先冻 %d 点再全额退）…" % RESERVE_TTS)
        st_v, txt_v = http_json("GET", host + API_PREFIX + "/apps/" + APP_TTS
                                + "/list_voices?page_number=1&page_size=1", key, None, 60)
        d_v = jloads(txt_v) or {}
        data = d_v.get("data") if isinstance(d_v.get("data"), dict) else {}
        checks.append(("音色库 list_voices 可达（--probe-voices）",
                       st_v == 200 and d_v.get("code") == 1 and "total" in data,
                       "HTTP %s · 共 %s 个音色" % (st_v, data.get("total"))))

    out = {"ok": all(c[1] for c in checks), "host": host,
           "freeSurface": ["GET /user/balance", "GET %s/apps" % API_PREFIX,
                           "GET %s/pricing" % API_PREFIX,
                           "GET %s/tasks/{task_id}" % API_PREFIX],
           "endpoints": {"tts": API_PREFIX + "/apps/" + APP_TTS + "/tts",
                         "lipsync": API_PREFIX + "/apps/" + APP_LIP + "/submit",
                         "human": API_PREFIX + "/apps/" + APP_HUMAN + "/submit",
                         "upload": API_PREFIX + "/upload"},
           "rates": {"lipsync": LIPSYNC_RATE, "human": HUMAN_RATES,
                     "ttsPointsPerChar": TTS_POINTS_PER_CHAR},
           "voiceTotal": VOICE_TOTAL,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（只有只读 GET，一个 POST 都不发，净花费 0 点）")
    print()
    for n, o, dd in checks:
        print("  %s %-40s %s" % ("√" if o else "×", n, dd))
    print()
    print("  配音：POST %s" % out["endpoints"]["tts"])
    print("  视频：POST %s  ·  POST %s" % (out["endpoints"]["lipsync"],
                                          out["endpoints"]["human"]))
    print("  上传：POST %s（0 点）" % out["endpoints"]["upload"])
    print("  轮询：GET  %s/tasks/<task_id>（0 点）" % API_PREFIX)
    print("  为什么自检不发 submit：缺必填也是先冻 250 点再退，净 0 但钱包会被动一下。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 音色库 ─────────────────────────
def cmd_voices(a, key, host):
    if not a.yes and not a.json:
        raise Fail("confirm",
                   "这条 GET 会先冻结 %d 点、随即全额退回（净 0），钱包会被动一下。"
                   "确认请加 --yes。" % RESERVE_TTS, EXIT_CONFIRM)
    st, txt = http_json("GET", host + API_PREFIX + "/apps/" + APP_TTS
                        + "/list_voices?page_number=1&page_size=100", key, None, 60)
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    if not ok:
        raise Fail("call", "音色库读取失败（HTTP %s）：%s" % (st, msg or err_text(st, txt)),
                   EXIT_CALL)
    data = data if isinstance(data, dict) else {}
    items = data.get("items") or []
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        rows.append({"id": it.get("id") or it.get("model_id") or it.get("reference_id"),
                     "title": it.get("title") or it.get("name"),
                     "language": it.get("language"),
                     "type": it.get("type")})
    out = {"ok": True, "total": data.get("total"), "count": len(rows), "voices": rows,
           "netPoints": 0, "movedPoints": RESERVE_TTS}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("音色库：共 %s 个（本页 %d 个）" % (data.get("total"), len(rows)))
    print()
    for r in rows:
        print("  %-40s %-16s %s" % (r["id"], r["title"] or "-", r["language"] or ""))
    print()
    print("  reference_id 就是上面第一列。把它传给 --voices 即可加入矩阵。")
    return 0


# ───────────────────────── 配音 ─────────────────────────
def _tts_body(a, text, ref):
    body = {"text": text, "format": a.format or "mp3"}
    if ref:
        body["reference_id"] = ref
    if a.tts_model:
        body["model"] = a.tts_model
    if a.speed is not None:
        body["prosody"] = {"speed": float(a.speed)}
    return body


def _tts_one(a, key, host, text, ref):
    url = host + API_PREFIX + "/apps/" + APP_TTS + "/tts"
    st, txt = http_json("POST", url, key, _tts_body(a, text, ref), timeout=max(60, a.timeout),
                        retries=1)
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    if not ok:
        return False, None, (msg or err_text(st, txt))[:300]
    data = data if isinstance(data, dict) else {}
    audio = data.get("audio_url") or data.get("url")
    if not audio:
        got = find_media(data, [], audio=True)
        audio = got[0] if got else None
    if not audio:
        return False, None, "返回里没有 audio_url：%s" % txt.replace("\n", " ")[:200]
    return True, audio, data


def cmd_tts(a, key, host):
    chars = chars_of(a)
    if not chars:
        raise Fail("usage", "必须给 --content \"文案\" 或 --content-file 文件", EXIT_USAGE)
    if len(chars) > MAX_SYNC_CHARS:
        raise Fail("usage", "文案 %d 字，超过同步配音接口 %d 字上限，拆段再跑。"
                   % (len(chars), MAX_SYNC_CHARS), EXIT_USAGE)
    voices = a.voices or []
    if not voices:
        raise Fail("usage", "必须给 --voices <reference_id>（可重复，或用 voices 子命令现查）",
                   EXIT_USAGE)
    st = state_load(a)
    st["meta"].update({"chars": len(chars), "content": chars[:80],
                       "seconds": seconds_of(a, chars), "ttsModel": a.tts_model})
    todo = []
    for v in voices:
        k = voice_key(v, chars)
        old = st["tts"].get(k) or {}
        if old.get("audioUrl") and not a.refresh:
            say("  复用已配音色 %s（不再付费）" % v)
            continue
        todo.append((k, v))
    cost = tts_points(chars) * len(todo)
    gate(a, cost, "%d 个音色 x %d 字配音" % (len(todo), len(chars)))
    if a.dry_run:
        url = host + API_PREFIX + "/apps/" + APP_TTS + "/tts"
        out = {"ok": True, "dryRun": True, "url": url,
               "requests": [{"reference_id": v, "body": _tts_body(a, chars, v)}
                            for _, v in todo],
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s" % url)
        for _, v in todo:
            print("  请求：%s" % json.dumps(_tts_body(a, chars, v), ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    done, bad = 0, 0
    for k, v in todo:
        say("  配音 %s（%d 字）…" % (v, len(chars)))
        ok, audio, info = _tts_one(a, key, host, chars, v)
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "tts", "voice": v,
               "ok": ok, "chars": len(chars)}
        if ok:
            st["tts"][k] = {"ref": v, "audioUrl": audio, "chars": len(chars),
                            "at": rec["at"]}
            rec["audioUrl"] = audio
            done += 1
            if a.save:
                try:
                    p = _save_audio(audio, a.outdir, "%s-%s" % (a.prefix or "tts", k))
                    rec["file"] = p
                    say("  已存：%s" % p)
                except Fail as e:
                    say("  （下载没成功：%s）" % e.message)
        else:
            st["tts"][k] = {"ref": v, "error": info, "chars": len(chars)}
            rec["error"] = info
            bad += 1
            say("  失败：%s" % info)
        ledger_add(rec)
        state_save(a, st)

    out = {"ok": bad == 0, "done": done, "failed": bad, "chars": len(chars),
           "estimatedPoints": cost, "tts": st["tts"], "statePath": state_path(a)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if bad == 0 else EXIT_CALL
    print("配音完成：成功 %d · 失败 %d · 预计 %d 点（%.2f 元）"
          % (done, bad, cost, yuan(cost)))
    print("  清单已写进 %s；run 会直接复用，不再付第二次钱。" % state_path(a))
    return 0 if bad == 0 else EXIT_CALL


# ───────────────────────── 矩阵主命令 ─────────────────────────
def _plan(a, st, chars, seconds):
    """返回 (images, voices, jobs)。jobs 是尚未完成的 combo。"""
    images = []
    for raw in (a.images or []):
        k = stem_of(raw)
        old = st["images"].get(k) or {}
        images.append({"key": k, "file": old.get("file") or raw,
                       "url": old.get("url") or (raw if re.match(r"^https?://", raw) else None)})
    voices = []
    if a.audio:
        voices.append({"key": san(a.voice_label or "audio", 30),
                       "ref": None, "audioUrl": a.audio})
    if a.voices:
        for v in a.voices:
            k = voice_key(v, chars)
            old = st["tts"].get(k) or {}
            voices.append({"key": k, "ref": v, "audioUrl": old.get("audioUrl")})
    jobs = []
    for i, img in enumerate(images, 1):
        for v in voices:
            cid = "%s__%s" % (img["key"], v["key"])
            old = st["combos"].get(cid) or {}
            jobs.append({"id": cid, "imgNo": i, "image": img, "voice": v,
                         "taskId": old.get("taskId"), "status": old.get("status"),
                         "file": old.get("file"), "videoUrl": old.get("videoUrl"),
                         "points": old.get("points")})
    return images, voices, jobs


def _build_body(a, image_url, audio_url, seconds):
    if a.engine == "human":
        body = {"file_url": image_url, "ref_file_url": audio_url,
                "duration": float(seconds), "mode": a.mode}
        if a.resolution:
            body["resolution"] = a.resolution
    else:
        body = {"image_url": image_url, "audio_url": audio_url, "mode": "audio",
                "quality": a.quality, "model": "super-lipsync-pro"}
    if a.prompt:
        body["prompt"] = a.prompt
    return body


def _submit_worker(a, key, host, body):
    url = host + API_PREFIX + "/apps/" + (APP_HUMAN if a.engine == "human" else APP_LIP) + "/submit"
    try:
        st, txt = http_json("POST", url, key, body, timeout=max(60, a.timeout), retries=1)
    except Fail as e:
        return {"ok": False, "unknown": True, "error": e.message}
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    if not ok:
        return {"ok": False, "error": (msg or err_text(st, txt))[:300], "http": st}
    data = data if isinstance(data, dict) else {}
    tid = data.get("task_id") or data.get("taskId") or data.get("id")
    if not tid:
        return {"ok": False, "error": "返回里没有 task_id：%s" % txt.replace("\n", " ")[:200]}
    return {"ok": True, "taskId": tid, "frozen": data.get("frozen_points")}


def _poll_worker(a, key, host, task_id):
    deadline = time.time() + max(30, a.timeout)
    last = None
    while True:
        try:
            st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + str(task_id), key,
                                timeout=60, retries=a.retries)
        except Fail as e:
            return {"status": "poll_error", "error": e.message}
        d = jloads(txt) or {}
        status, node = dig_task(d)
        if status != last:
            say("  [%s] %s -> %s" % (time.strftime("%H:%M:%S"), task_id, status or "?"))
            last = status
        low = str(status or "").lower()
        if low in TERMINAL_OK:
            urls = find_media(node)
            if not urls:
                urls = find_media(d)
            return {"status": low, "urls": urls, "points": find_points(d), "node": node}
        if low in TERMINAL_BAD:
            return {"status": low, "error": str((node or {}).get("error") or low),
                    "node": node}
        if time.time() >= deadline:
            return {"status": "timeout",
                    "error": "等了 %d 秒还没完成；用 status --task-id %s 接着查"
                             % (a.timeout, task_id)}
        time.sleep(max(1, a.interval))


def _save_audio(url, outdir, name):
    ext = ".mp3"
    for e in (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".opus"):
        if e in url.split("?")[0].lower():
            ext = e
            break
    return _download(url, outdir, name + ext)


def _download(url, outdir, filename):
    os.makedirs(outdir or ".", exist_ok=True)
    p = os.path.join(outdir or ".", filename)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=300) as x:
            raw = x.read()
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "下载失败：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    with open(p, "wb") as fh:
        fh.write(raw)
    return p


def _ext_of(url):
    m = MEDIA_RE.search(url.split("?")[0])
    return m.group(1).lower() if m else "mp4"


def cmd_run(a, key, host):
    if not a.images:
        raise Fail("usage", "必须给 --images（可重复：--images a.png --images b.png）",
                   EXIT_USAGE)
    if not (a.voices or a.audio):
        raise Fail("usage", "必须给 --voices <reference_id>（可重复），或 --audio 一个现成音频地址",
                   EXIT_USAGE)
    chars = chars_of(a) if (a.content or a.content_file) else ""
    if a.voices and not chars:
        raise Fail("usage", "要配音就得给 --content \"文案\" 或 --content-file", EXIT_USAGE)
    if chars and len(chars) > MAX_SYNC_CHARS:
        raise Fail("usage", "文案 %d 字，超过同步配音接口 %d 字上限，拆段再跑。"
                   % (len(chars), MAX_SYNC_CHARS), EXIT_USAGE)
    if a.engine == "human" and not a.mode:
        raise Fail("usage",
                   "--engine human 必须给 --mode fast|standard|2k|4k。"
                   "不传 mode 时 schema 写 standard、计费卡写 fast，档位会跟账单对不上。",
                   EXIT_USAGE)
    if a.engine == "lipsync" and a.mode:
        raise Fail("usage", "--mode 只用于 --engine human；lipsync 的档位参数是 --quality",
                   EXIT_USAGE)

    seconds = seconds_of(a, chars)
    if not seconds:
        raise Fail("usage",
                   "没有文案时请用 --seconds 给每条视频的秒数（价格按秒算，估不准就不开工）",
                   EXIT_USAGE)
    if a.engine == "human" and not a.seconds:
        raise Fail("usage", "--engine human 要 --seconds（输入音频的真实秒数），价格才被锁死",
                   EXIT_USAGE)

    st = state_load(a)
    st["meta"].update({"content": chars[:120], "chars": len(chars), "seconds": seconds,
                       "engine": a.engine, "quality": a.quality, "mode": a.mode,
                       "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S")})
    images, voices, jobs = _plan(a, st, chars, seconds)

    pending_tts = [v for v in voices if not v.get("audioUrl")]
    pending_jobs = [j for j in jobs
                    if not j.get("videoUrl") and j.get("status") != "unknown"]
    if a.limit:
        pending_jobs = pending_jobs[:a.limit]

    per_video = video_points(a.engine, seconds, a.mode)
    tts_cost = tts_points(chars) * len(pending_tts) if a.voices else 0
    cost = tts_cost + per_video * len(pending_jobs)
    total_all = (tts_points(chars) * len(voices) if a.voices else 0) + per_video * len(jobs)

    what = ("%d 形象 x %d 音色 = %d 条，本次待做 %d 条 + 待配音 %d 个音色"
            % (len(images), len(voices), len(jobs), len(pending_jobs), len(pending_tts)))
    gate(a, cost, what)

    submit_url = host + API_PREFIX + "/apps/" + (
        APP_HUMAN if a.engine == "human" else APP_LIP) + "/submit"
    tts_url = host + API_PREFIX + "/apps/" + APP_TTS + "/tts"

    if a.dry_run:
        plan = []
        for j in pending_jobs[:5]:
            iu = j["image"].get("url") or "<上传后得到>"
            au = j["voice"].get("audioUrl") or "<配音后得到>"
            plan.append({"id": j["id"], "url": submit_url,
                         "body": _build_body(a, iu, au, seconds)})
        out = {"ok": True, "dryRun": True, "engine": a.engine,
               "images": [i["file"] for i in images], "voices": [v["key"] for v in voices],
               "jobs": len(pending_jobs), "ttsJobs": len(pending_tts),
               "uploads": [i["file"] for i in images if not i.get("url")
                           and not re.match(r"^https?://", i["file"])],
               "ttsUrl": tts_url if pending_tts else None,
               "submitUrl": submit_url, "sampleRequests": plan,
               "estimatedPoints": cost, "yuan": yuan(cost),
               "naming": "%s_<序号>-<形象>_<音色>.mp4" % (a.prefix or "talking")}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传、不配音、不提交、不扣费）")
        print("  引擎：%s%s" % (a.engine, "" if a.engine == "lipsync"
                                else "（%s 档）" % a.mode))
        print("  上传：%d 张图 -> POST %s/upload（0 点）"
              % (len(out["uploads"]), API_PREFIX))
        if pending_tts:
            print("  配音：%d 个音色 -> POST %s（%d 点）"
                  % (len(pending_tts), tts_url, tts_cost))
        print("  提交：%d 条 -> POST %s" % (len(pending_jobs), submit_url))
        for p in plan:
            print("    %-34s %s" % (p["id"], json.dumps(p["body"], ensure_ascii=False)[:160]))
        print("  预估：%d 点（%.2f 元）；全量口径 %d 点（%.2f 元）"
              % (cost, yuan(cost), total_all, yuan(total_all)))
        return 0

    # ① 上传形象图（免费，先做，失败就停，别先进付费环节）
    for img in images:
        if img.get("url"):
            continue
        path = img.get("file")
        if not (path and os.path.isfile(path)):
            raise Fail("usage",
                       "形象 %s 既不是 http(s) 地址也不是本地文件。\n"
                       "本地图会自动上传（0 点）；地址请以 http:// 开头。" % path, EXIT_USAGE)
        say("  上传 %s（0 点）…" % os.path.basename(path))
        up_st, up_txt = http_multipart(host + API_PREFIX + "/upload", key, "file", path)
        up_d = jloads(up_txt) or {}
        up_ok, up_msg, up_data = envelope(up_d)
        up_data = up_data if isinstance(up_data, dict) else {}
        url = up_data.get("url") or up_data.get("file_url")
        if not url:
            got = find_media(up_d)
            url = got[0] if got else None
        if not up_ok or not url:
            raise Fail("call", "上传失败（HTTP %s）：%s"
                       % (up_st, up_msg or err_text(up_st, up_txt)), EXIT_CALL)
        img["url"] = url
        st["images"][img["key"]] = {"file": path, "url": url}
        state_save(a, st)
        say("    -> %s" % url)

    # ② 配音（每个音色一次，带断点续跑）
    for v in voices:
        if v.get("audioUrl"):
            if v.get("ref"):
                say("  复用已配音色 %s（不再付费）" % v["ref"])
            continue
        say("  配音 %s（%d 字）…" % (v.get("ref"), len(chars)))
        ok, audio, info = _tts_one(a, key, host, chars, v.get("ref"))
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "tts",
               "voice": v.get("ref"), "ok": ok, "chars": len(chars)}
        if not ok:
            rec["error"] = info
            ledger_add(rec)
            state_save(a, st)
            raise Fail("call", "配音失败（%s）：%s" % (v.get("ref"), info), EXIT_CALL)
        v["audioUrl"] = audio
        st["tts"][v["key"]] = {"ref": v.get("ref"), "audioUrl": audio,
                               "chars": len(chars),
                               "at": rec["at"]}
        rec["audioUrl"] = audio
        ledger_add(rec)
        state_save(a, st)
        say("    -> %s" % audio)

    # ③ 提交（付费，每条只发一次）
    todo = [j for j in pending_jobs if not j.get("taskId")]
    done_submit, fail_submit = 0, 0
    if todo:
        say("提交 %d 条（并发 %d）…" % (len(todo), max(1, a.concurrency)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.concurrency)) as ex:
            futs = {}
            for j in todo:
                body = _build_body(a, j["image"]["url"], j["voice"]["audioUrl"], seconds)
                futs[ex.submit(_submit_worker, a, key, host, body)] = j
            for fut in concurrent.futures.as_completed(futs):
                j = futs[fut]
                try:
                    res = fut.result()
                except Exception as e:                           # noqa: BLE001
                    res = {"ok": False, "unknown": True,
                           "error": "%s: %s" % (type(e).__name__, e)}
                cid = j["id"]
                if res.get("ok"):
                    done_submit += 1
                    st["combos"][cid] = {"status": "submitted", "taskId": res["taskId"],
                                         "frozen": res.get("frozen"), "image": j["image"]["key"],
                                         "voice": j["voice"]["key"], "engine": a.engine,
                                         "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                    say("  [提交] %s -> %s" % (cid, res["taskId"]))
                    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "submit",
                                "combo": cid, "engine": a.engine, "ok": True,
                                "taskId": res["taskId"], "frozen": res.get("frozen")})
                else:
                    fail_submit += 1
                    st["combos"][cid] = {"status": "unknown" if res.get("unknown") else "failed",
                                         "error": res.get("error"), "image": j["image"]["key"],
                                         "voice": j["voice"]["key"], "engine": a.engine,
                                         "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                    say("  [提交失败] %s：%s" % (cid, res.get("error")))
                    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "submit",
                                "combo": cid, "engine": a.engine, "ok": False,
                                "error": res.get("error")})
                state_save(a, st)

    # ④ 轮询（免费；只走 GET /tasks/<id>）
    wait_jobs = [c for c in st["combos"].values()
                 if c.get("taskId") and c.get("status") not in ("completed", "failed")]
    wait_ids = sorted(set([c["taskId"] for c in wait_jobs]))
    if wait_ids and not a.no_wait:
        say("轮询 %d 条（并发 %d，间隔 %ds）…" % (len(wait_ids), max(1, a.concurrency),
                                                 a.interval))
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.concurrency)) as ex:
            futs = {ex.submit(_poll_worker, a, key, host, tid): tid for tid in wait_ids}
            for fut in concurrent.futures.as_completed(futs):
                tid = futs[fut]
                try:
                    results[tid] = fut.result()
                except Exception as e:                           # noqa: BLE001
                    results[tid] = {"status": "poll_error",
                                    "error": "%s: %s" % (type(e).__name__, e)}
        for cid, c in list(st["combos"].items()):
            tid = c.get("taskId")
            if not tid or tid not in results:
                continue
            r = results[tid]
            c["status"] = r.get("status")
            c["points"] = r.get("points")
            if r.get("urls"):
                c["videoUrl"] = r["urls"][0]
            if r.get("error"):
                c["error"] = r["error"]
            state_save(a, st)

    # ⑤ 落盘（按规范文件名；这个名字可预测，重跑会覆盖同一位置）
    files = []
    if a.save:
        for j in jobs:
            c = st["combos"].get(j["id"]) or {}
            if c.get("status") not in TERMINAL_OK or not c.get("videoUrl"):
                continue
            name = "%s_%02d-%s_%s.%s" % (a.prefix or "talking", j["imgNo"],
                                         j["image"]["key"], j["voice"]["key"],
                                         _ext_of(c["videoUrl"]))
            if c.get("file") and os.path.isfile(c["file"]):
                files.append(c["file"])
                continue
            try:
                p = _download(c["videoUrl"], a.outdir, name)
                c["file"] = p
                files.append(p)
                say("  已存 %s" % p)
            except Fail as e:
                say("  （%s 下载失败：%s）" % (j["id"], e.message))
        state_save(a, st)

    # ⑥ 汇总（只统计本次矩阵的条目，不把历史残留算进来）
    rows = []
    for j in jobs:
        c = st["combos"].get(j["id"]) or {}
        rows.append({"combo": j["id"], "status": c.get("status"),
                     "taskId": c.get("taskId"), "points": c.get("points"),
                     "videoUrl": c.get("videoUrl"), "file": c.get("file"),
                     "error": c.get("error")})
    ok_n = sum(1 for r in rows if r["status"] in TERMINAL_OK)
    bad_n = sum(1 for r in rows if r["status"] in TERMINAL_BAD or r["status"] == "poll_error")
    real = 0.0
    for r in rows:
        try:
            real += float(r.get("points") or 0)
        except (TypeError, ValueError):
            pass
    out = {"ok": bad_n == 0, "engine": a.engine, "images": len(images),
           "voices": len(voices), "videos": len(rows),
           "submitted": done_submit, "completed": ok_n, "failed": bad_n,
           "estimatedPoints": cost, "billedPoints": round(real, 2),
           "points": rows, "files": files, "statePath": state_path(a),
           "unknown": sum(1 for r in rows if r["status"] == "unknown")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if bad_n == 0 and out["unknown"] == 0 else EXIT_CALL
    print()
    print("矩阵结果：%d 形象 x %d 音色 = %d 条 · 完成 %d · 失败 %d · 待对账 %d"
          % (len(images), len(voices), len(rows), ok_n, bad_n, out["unknown"]))
    print("  本次预计 %d 点（%.2f 元）" % (cost, yuan(cost)))
    if real:
        print("  任务上报实扣合计 %.2f 点（%.2f 元）" % (real, yuan(real)))
    print()
    for r in rows:
        mark = "√" if r["status"] in TERMINAL_OK else (
            "×" if r["status"] in TERMINAL_BAD else "-")
        print("  %s %-40s %-10s %s" % (mark, r["combo"], r["status"] or "-",
                                       r["file"] or r["videoUrl"] or ""))
    print()
    print("  state：%s（重跑只补没跑完的，已配过音的音色不再付钱）" % state_path(a))
    if out["unknown"]:
        print("  有 %d 条提交结果未知（网络中断，任务可能已建）。先 status --workdir 对账，"
              "确认没任务再重跑 —— 直接重跑等于再扣一次。" % out["unknown"])
    return 0 if bad_n == 0 and out["unknown"] == 0 else EXIT_CALL


# ───────────────────────── 查任务 / 台账 ─────────────────────────
def cmd_status(a, key, host):
    if a.task_id:
        st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + str(a.task_id), key,
                            None, 60)
        d = jloads(txt) or {}
        status, node = dig_task(d)
        if not status and "不存在" in str(d.get("msg") or ""):
            raise Fail("call", "查不到任务 %s（网关说「任务不存在」）。" % a.task_id,
                       EXIT_CALL)
        urls = find_media(node) or find_media(d)
        out = {"ok": True, "taskId": a.task_id, "status": status, "url": urls[0] if urls else None,
               "points": find_points(d), "raw": node}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("任务 %s" % a.task_id)
        print("  状态：%s" % (status or "未知"))
        if out["points"] is not None:
            print("  点数：%.2f 点（%.2f 元）" % (out["points"], yuan(out["points"])))
        if out["url"]:
            print("  成片：%s" % out["url"])
        return 0

    st = state_load(a)
    combos = st.get("combos") or {}
    if not combos:
        raise Fail("usage", "这个 workdir 里没有矩阵记录：%s" % state_path(a), EXIT_USAGE)
    # 免费刷新：只走 GET /tasks/<id>
    for c in combos.values():
        tid = c.get("taskId")
        if not tid or c.get("status") in TERMINAL_OK or c.get("status") in TERMINAL_BAD:
            continue
        st2, txt2 = http_json("GET", host + API_PREFIX + "/tasks/" + str(tid), key, None, 60)
        d2 = jloads(txt2) or {}
        status, node = dig_task(d2)
        if status:
            c["status"] = str(status).lower()
        urls = find_media(node) or find_media(d2)
        if urls:
            c["videoUrl"] = urls[0]
        pts = find_points(d2)
        if pts is not None:
            c["points"] = pts
    state_save(a, st)
    rows = [dict(c, combo=k) for k, c in sorted(combos.items())]
    ok_n = sum(1 for r in rows if r.get("status") in TERMINAL_OK)
    out = {"ok": True, "videos": len(rows), "completed": ok_n, "combos": rows,
           "statePath": state_path(a)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("矩阵对账（%s）" % state_path(a))
    print("  共 %d 条 · 完成 %d 条" % (len(rows), ok_n))
    print()
    for r in rows:
        mark = "√" if r.get("status") in TERMINAL_OK else (
            "×" if r.get("status") in TERMINAL_BAD else "-")
        print("  %s %-40s %-10s %s" % (mark, r.get("combo"), r.get("status") or "-",
                                       r.get("file") or r.get("videoUrl") or ""))
    return 0


def cmd_log(a, key, host):
    arr = []
    if os.path.isfile(LEDGER):
        try:
            arr = json.load(io.open(LEDGER, encoding="utf-8")) or []
        except Exception:                                        # noqa: BLE001
            arr = []
    entries = arr[-a.limit:] if a.limit else arr
    out = {"ok": True, "count": len(arr), "entries": entries}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(entries), len(arr)))
    for e in entries:
        print("  %s  %-6s %-6s %-38s %s" % (
            e.get("at") or "-", "OK" if e.get("ok") else "FAIL",
            e.get("mode") or "-", (e.get("combo") or e.get("voice") or "-")[:38],
            e.get("taskId") or e.get("error") or ""))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 口播矩阵（一段文案 x N 个形象 x M 个音色）",
        epilog="端点：POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/pic_lipsync/submit · "
               "POST %s/api/v1/apps/image_human/submit · "
               "GET %s/api/v1/tasks/<task_id>" % (
                   DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="矩阵规格 + 价目 + 两个引擎对照（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    def add_plan(p):
        p.add_argument("--images", type=int, default=1,
                       help="形象数量（算钱用，默认 1）")
        p.add_argument("--voices", type=int, default=1,
                       help="音色数量（算钱用，默认 1）")
        p.add_argument("--chars", type=int, help="文案字数（不用 --content 时直接给）")
        p.add_argument("--content", help="文案原文（按 4.5 字/秒估时长）")
        p.add_argument("--seconds", type=float, help="直接给每条视频的秒数")
        p.add_argument("--engine", default="lipsync", choices=ENGINES,
                       help="lipsync（pic_lipsync，15 点/秒）/ human（image_human，四档）")
        p.add_argument("--mode", choices=MODES,
                       help="human 的档位 fast/standard/2k/4k（human 必填）")
        p.add_argument("--quality", default="standard", choices=QUALITIES,
                       help="lipsync 的档位（档位真名是 quality，默认 standard）")

    p = sub.add_parser("cost", help="先算钱：N x M 全链路（免费）", allow_abbrev=False)
    add_plan(p)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 三张速率卡（免费，不扣费）",
                       allow_abbrev=False)
    p.add_argument("--probe-voices", action="store_true",
                   help="额外探一次音色库（先冻 %d 点再全额退，净 0）" % RESERVE_TTS)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("voices", help="音色库清单（GET，先冻 %d 点后全额退）" % RESERVE_TTS,
                       allow_abbrev=False)
    p.add_argument("--yes", action="store_true", help="确认这次 GET 会短暂冻结点数（净 0）")
    p.set_defaults(fn=cmd_voices)

    def add_state(p):
        p.add_argument("--workdir", default=".", help="工作目录（state 与成片都在这里）")
        p.add_argument("--state", help="指定 state 文件路径（默认 <workdir>/%s" % STATE_NAME)
        p.add_argument("--prefix", default="talking", help="成片文件名前缀（默认 talking）")
        p.add_argument("--yes", action="store_true", help="确认真实提交并扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        p.add_argument("--timeout", type=int, default=1800, help="单条等待上限秒数（默认 1800）")
        p.add_argument("--interval", type=int, default=8, help="轮询间隔秒数（默认 8）")
        p.add_argument("--retries", type=int, default=2,
                       help="免费环节（轮询/上传）的重试次数（默认 2）")

    p = sub.add_parser("tts", help="只做配音：文案 -> M 段音频（约 0.18 点/字/音色）",
                       allow_abbrev=False)
    add_state(p)
    p.add_argument("--voices", nargs="+", help="音色 reference_id，可给多个（空格或多写几次）")
    p.add_argument("--content", help="要念的文案（<=500 字）")
    p.add_argument("--content-file", help="文案文件（UTF-8）")
    p.add_argument("--tts-model", default="s2-pro", help="配音引擎，默认 s2-pro")
    p.add_argument("--format", default="mp3", choices=["mp3", "wav", "ogg", "opus", "pcm"],
                   help="音频格式，默认 mp3")
    p.add_argument("--speed", type=float, help="语速（prosody.speed，1.0 为原速）")
    p.add_argument("--refresh", action="store_true", help="已配过音的音色也重新配（会再付费）")
    p.add_argument("--save", action="store_true", help="把音频下载到 --outdir")
    p.add_argument("--outdir", default=".", help="音频保存目录（配合 --save）")
    p.set_defaults(fn=cmd_tts)

    p = sub.add_parser("run", help="矩阵主命令：上传 -> 配音 -> N x M 提交 -> 轮询落盘",
                       allow_abbrev=False)
    add_state(p)
    p.add_argument("--images", action="append",
                   help="形象图：本地路径或 http(s) 地址，可重复（--images a.png --images b.jpg）")
    p.add_argument("--voices", action="append",
                   help="音色 reference_id，可重复（--voices model_a --voices model_b）")
    p.add_argument("--audio", help="已有音频地址：跳过配音，直接用它做矩阵")
    p.add_argument("--voice-label", help="配 --audio 时这条矩阵的音色标签（默认 audio）")
    p.add_argument("--content", help="要念的文案（<=500 字）")
    p.add_argument("--content-file", help="文案文件（UTF-8）")
    p.add_argument("--engine", default="lipsync", choices=ENGINES,
                   help="lipsync（pic_lipsync，15 点/秒）/ human（image_human，四档）")
    p.add_argument("--mode", choices=MODES, help="human 的档位（human 必填）")
    p.add_argument("--quality", default="standard", choices=QUALITIES,
                   help="lipsync 的档位（默认 standard）")
    p.add_argument("--seconds", type=float, help="每条视频秒数（默认按文案字数推算）")
    p.add_argument("--prompt", help="人物动作 / 表情 / 画面风格（可选）")
    p.add_argument("--resolution", choices=["2k", "4k"], help="human 的兼容别名，等价于同档 mode")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help="并发条数（默认 %d）" % DEFAULT_CONCURRENCY)
    p.add_argument("--limit", type=int, help="先只做前 N 条试水（断点续跑也遵它）")
    p.add_argument("--no-wait", action="store_true", help="只提交，不等结果")
    p.add_argument("--save", dest="save", action="store_true", default=True,
                   help="把成片按规范名落盘（默认开）")
    p.add_argument("--no-save", dest="save", action="store_false", help="只留链接不下载")
    p.add_argument("--outdir", default=None, help="成片目录（默认 = --workdir）")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("status", help="查单条，或整张矩阵的对账表（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="单个 task_id")
    p.add_argument("--workdir", default=".", help="矩阵工作目录（对账模式）")
    p.add_argument("--state", help="指定 state 文件路径")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="显示最近几条（默认 20）")
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


LOCAL_CMDS = ("cmd_catalog", "cmd_cost", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    if not hasattr(a, "json"):
        a.json = False
    if a.fn is cmd_run and getattr(a, "outdir", None) is None:
        a.outdir = getattr(a, "workdir", ".") or "."
    key, host = load_conf(getattr(a, "key", None), getattr(a, "host", None))
    if not key and a.fn.__name__ not in LOCAL_CMDS:
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
        say("已中断。已完成的条目都在 state 里，重跑会接着补。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
