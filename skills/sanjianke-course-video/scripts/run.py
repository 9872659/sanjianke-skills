#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 课程视频（一份大纲 → 一整套讲师口播课件）

本包只做一件事：**把「一份课程大纲」变成「一套有进度、能续跑、能拼接的章节视频」**。

## 链路（5 段，每段一条子命令）

    plan    大纲 .md  →  讲稿 + course.json 进度清单          （本地，0 点）
    voice   讲稿      →  分节口播音频    voice_tts/tts_async   （配音，按字计费）
    slide   课件图 + 音频 → 章节视频      image_human/submit     （10/15/30/60 点/输入秒）
    mouth   图 + 参考音色 + 文案 → 口播   pic_lipsync/submit     （15 点/秒）
    stitch  章节视频  →  ffconcat 拼接清单 + 进度回写          （本地，0 点）

## 价目（2026-11-07 用 GET /api/v1/pricing 逐条核对，1 元 = 100 点）

    /api/v1/apps/image_human/submit   per_second，rateFrom=mode
                                      fast 10 / standard 15 / 2k 30 / 4k 60 点/输入秒
                                      defaultModel = fast
    /api/v1/apps/pic_lipsync/submit   flat cost 0，markupPercent 400 → 上游实际点数 ×5
                                      上游实测固定 3 点/秒 → 对外 15 点/秒；minPoints 50 仅声明
    /api/v1/apps/voice_tts/*          flat cost 0，markupPercent 200 → 上游实际点数 ×3
                                      实测 tts_live 33 字 → 上游 1.98 点 → 我方 5.94 点
                                      → 估算口径 0.18 点/字，单笔按 6 点起

## 三条硬规矩（都是买来的）

  ① `image_human` 不传 mode 就出片：schema 默认 standard，计费卡默认 fast
     → **出片按 standard、收钱按 fast**。所以本包 `--mode` 必填，永不下发省略 mode 的请求。
  ② `pic_lipsync` 的档位参数真名是 `quality`（standard/fast/max），`mode` 只切 audio/text；
     且**text 模式省得掉录音、省不掉「参考音色」**，audio_url 仍然必填。
  ③ 应用层 `/query` **一次就是一次的钱**（历史 nano_banana/query 72 点/次，烧掉 7,776 点）。
     本包在 `http_json()` 里直接拦掉任何以 `/query` 结尾的地址，
     轮询一律走 **GET /api/v1/tasks/{task_id}**（只读、免费）。

## 为什么不用「免费」的 list_voices 之类

实测流水：`voice_tts/list_voices` 每次都是「reserve_sync 冻 -150 → refund 退 +150」，
净额 0，但钱包被真动过。所以 `doctor` **一个 POST 都不发**，只用 4 个只读 GET 证明链路通。

## 子命令

  catalog  5 段链路 + 三条路线的价目对照（免费）
  cost     先算钱：按章节数 × 每章秒数（免费）
  doctor   自检 Key / 三条链路已配价 / 速率卡 / 查询线 / 余额（免费，不扣费）
  plan     大纲 → 讲稿 + 进度清单（免费，本地）
  voice    分节口播出音频（付费，要 --yes，受 --budget 管）
  slide    课件图 → 章节视频（付费，--mode 必填）
  mouth    一图 + 参考音色 + 文案 → 口播（付费）
  stitch   章节拼接清单 + 进度回看（免费，本地）
  status   查任务 GET /api/v1/tasks/{id}（免费）
  log      本地台账

## 用法

  python3 scripts/run.py plan --outline course-outline.md -o course.json
  python3 scripts/run.py cost --chapters 10 --seconds 60 --route slide --mode fast
  python3 scripts/run.py doctor
  python3 scripts/run.py voice --course course.json --limit 2 --yes
  python3 scripts/run.py slide --course course.json --image slide.png --mode fast --yes
  python3 scripts/run.py stitch --course course.json

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 references/troubleshooting.md。
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
import urllib.request
import uuid


# ── GBK 编码兜底（2026-11-07 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到 cp936 编不出的字符（对勾 / 叉 / 人民币符号 这类）就 UnicodeEncodeError 崩掉。
# 先加 errors='replace' 兜底；本包输出只用 cp936 里有的符号（√ × —— ·）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"

APP_VOICE = "voice_tts"
APP_SLIDE = "image_human"
APP_MOUTH = "pic_lipsync"

# 价目（单位：点，1 元 = 100 点）
SLIDE_RATES = {"fast": 10, "standard": 15, "2k": 30, "4k": 60}
SLIDE_MODES = ["fast", "standard", "2k", "4k"]
MOUTH_POINTS_PER_SEC = 15          # 上游实际点数 ×5；上游实测固定 3 点/秒
MOUTH_MIN_POINTS = 50              # 公开文档写的「单笔保底」，取上限不低估
TTS_POINTS_PER_CHAR = 0.18         # tts_live 实测：33 字 → 我方 5.94 点
TTS_MIN_POINTS = 6                 # 同口径最低一笔 5.94 点，向上取 6
CHARS_PER_SEC = 4.5                # 中文口播约 4.5 字/秒
QUALITIES = ["standard", "fast", "max"]   # pic_lipsync 的档位真名是 quality

DEFAULT_BUDGET = 5000              # 点，= 50 元
POINTS_PER_YUAN = 100
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "course-video-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-course-video/%s" % VERSION

TERMINAL_OK = ("completed", "succeeded", "success", "done")
TERMINAL_BAD = ("failed", "cancelled", "canceled", "error", "timeout", "expired")

VIDEO_EXT = re.compile(r"\.(mp4|mov|webm|m4v)(\?|#|$)", re.I)
AUDIO_EXT = re.compile(r"\.(mp3|wav|m4a|ogg|opus|flac)(\?|#|$)", re.I)


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
    # 应用层 /query 一次就是一次的钱 —— 在 HTTP 层直接拦死，代码里不该出现第二次。
    if url.rstrip("/").endswith("/query"):
        raise Fail("internal",
                   "本包不调用应用层 /query（每轮询一次就是一次的钱）。"
                   "查询一律走 GET %s/api/v1/tasks/{task_id}。" % DEFAULT_HOST,
                   EXIT_INTERNAL)
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


def http_multipart(url, key, fields, files, timeout=300):
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
            bits = [e.get("message") or "", e.get("code") or "", e.get("param") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:300]
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return txt.replace("\n", " ")[:240]


def envelope(d):
    """平台信封 {"code":1,"msg":"success","data":{…}}；出错 code=0 且 data=null。"""
    if not isinstance(d, dict):
        return False, "响应不是 JSON", None
    code = d.get("code")
    msg = d.get("msg") or d.get("message") or ""
    ok = (code == 1 or code == "1" or code is True) and d.get("data") is not None
    return ok, str(msg), d.get("data")


def find_urls(obj, out=None, depth=0):
    """递归扫所有 http(s) 地址（结果可能在 data / data.result / data.result.data 任一层）。"""
    if out is None:
        out = []
    if depth > 6:
        return out
    if isinstance(obj, dict):
        for v in obj.values():
            find_urls(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            find_urls(v, out, depth + 1)
    elif isinstance(obj, str) and obj.startswith("http") and obj not in out:
        out.append(obj)
    return out


def pick(urls, ext_re):
    for u in urls:
        if ext_re.search(u):
            return u
    return None


def find_points(obj, depth=0):
    if depth > 6:
        return None
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
            got = find_points(v, depth + 1)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for it in obj:
            got = find_points(it, depth + 1)
            if got is not None:
                return got
    return None


def dig_task(d):
    """返回 (status, payload)。兼容「结果里也有一个 result」的双重身份字段。"""
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(data, dict):
        return None, data
    status = data.get("status")
    node = data
    if not status:
        r = data.get("result")
        if isinstance(r, dict):
            if "code" in r:                       # 中转包装层 → 剥掉
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


def fmt_pts(n):
    return "{:,}".format(int(round(float(n))))


def dwidth(s):
    """按终端显示宽度算：中文/全角算 2 列，ASCII 算 1 列。"""
    w = 0
    for ch in str(s):
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def ljust(s, n):
    s = str(s)
    return s + " " * max(0, n - dwidth(s))


def rjust(s, n):
    s = str(s)
    return " " * max(0, n - dwidth(s)) + s


def yuan(points):
    return round(float(points) / POINTS_PER_YUAN, 2)


# ───────────────────────── 台账 ─────────────────────────
def ledger_load():
    if not os.path.isfile(LEDGER):
        return []
    try:
        arr = json.load(io.open(LEDGER, encoding="utf-8"))
        return arr if isinstance(arr, list) else []
    except Exception:                                            # noqa: BLE001
        return []


def ledger_add(rec):
    try:
        arr = ledger_load()
        arr.append(rec)
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


# ───────────────────────── 进度清单 ─────────────────────────
def _read_text(path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return io.open(path, encoding=enc).read()
        except UnicodeDecodeError:
            continue
        except IOError as e:
            raise Fail("usage", "打不开 %s：%s" % (path, e), EXIT_USAGE)
    raise Fail("usage", "%s 编码认不出（试过 utf-8 / gbk）" % path, EXIT_USAGE)


def call_seconds(text):
    t = re.sub(r"\s+", "", text or "")
    return round(len(t) / CHARS_PER_SEC, 1)


def call_points(text):
    """配音估算：0.18 点/字，单笔按 6 点起（实测最低一笔 5.94 点）。"""
    t = re.sub(r"\s+", "", text or "")
    return max(TTS_MIN_POINTS, int(round(len(t) * TTS_POINTS_PER_CHAR)))


def parse_outline(text, title_override=None):
    """把一份大纲 Markdown 切成 章 → 要点。`## ` 是章，`- ` / `1. ` 是要点。"""
    course_title = None
    chapters = []
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        if s.startswith("# ") and course_title is None:
            course_title = s[2:].strip()
            continue
        if s.startswith("## "):
            chapters.append({"title": s[3:].strip(), "bullets": []})
            continue
        m = re.match(r"^(?:[-*+]|\d+[.)、])\s+(.+)$", s)
        if m and chapters:
            chapters[-1]["bullets"].append(m.group(1).strip())
            continue
        if s.startswith("#"):
            # 三级标题（### 小节）也当一条要点收着，别丢内容
            if chapters:
                chapters[-1]["bullets"].append(s.lstrip("#").strip())
            continue
        if chapters and not m:
            # 章下面的散段落，也当一条要点收着，别丢内容
            chapters[-1]["bullets"].append(s)
    if not chapters:
        raise Fail("usage",
                   "大纲里没找到章节。格式：`# 课程名` 一行，然后每个 `## 第 N 章 标题`，"
                   "章下面的 `- 要点` 逐条列。", EXIT_USAGE)
    return (title_override or course_title or "未命名课程"), chapters


def build_script(course_title, index, title, bullets):
    # 标题里如果已经带了「第 N 章」，念的时候就不再重复一遍
    spoken = re.sub(r"^第\s*[0-9一二三四五六七八九十百]+\s*[章节讲]\s*[、.：:]?\s*", "",
                    title or "")
    parts = ["这是《%s》第 %d 章，%s。" % (course_title, index, spoken)]
    if bullets:
        parts.append("这一章讲 %d 件事：%s。" % (len(bullets), "；".join(bullets)))
    else:
        parts.append("这一章我们把这件事拆开讲清楚。")
    parts.append("看完这一章，你应该能自己复述一遍。")
    return "".join(parts)


def course_path(a):
    return a.course


def load_course(a):
    p = course_path(a)
    if not p or not os.path.isfile(p):
        raise Fail("usage",
                   "找不到进度清单 %s。先跑 `plan --outline 大纲.md -o %s`。"
                   % (p or "course.json", p or "course.json"), EXIT_USAGE)
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception as e:                                       # noqa: BLE001
        raise Fail("usage", "进度清单不是合法 JSON：%s" % e, EXIT_USAGE)
    if not isinstance(d, dict) or not isinstance(d.get("chapters"), list):
        raise Fail("usage", "进度清单格式不对（缺 chapters 数组）：%s" % p, EXIT_USAGE)
    return d


def save_course(a, d):
    d["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = course_path(a) + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(tmp, course_path(a))


def done_chapters(d, stage):
    """stage=audio → 已有 audioUrl；stage=video → 已有 videoUrl。"""
    key = "audioUrl" if stage == "audio" else "videoUrl"
    return [c for c in d["chapters"] if c.get(key)]


def todo_chapters(d, stage, only=None):
    key = "audioUrl" if stage == "audio" else "videoUrl"
    rows = []
    for c in d["chapters"]:
        if c.get(key):
            continue
        if only and c.get("index") not in only:
            continue
        rows.append(c)
    return rows


# ───────────────────────── 价格 ─────────────────────────
def slide_points(mode, seconds):
    return int(round(SLIDE_RATES[mode] * float(seconds)))


def mouth_points(seconds):
    return max(MOUTH_MIN_POINTS, int(round(MOUTH_POINTS_PER_SEC * float(seconds))))


# ───────────────────────── 上传 ─────────────────────────
def materialize(a, key, host, value, label):
    """URL 直接用；本地文件先传平台临时地址（POST /upload 不计费，0 点/次）。"""
    v = value
    if re.match(r"^https?://", v or ""):
        return v
    if not v or not os.path.isfile(v):
        raise Fail("usage", "%s 既不是 URL 也不是存在的文件：%s" % (label, v), EXIT_USAGE)
    if not getattr(a, "upload", False):
        raise Fail("usage", "%s 是本地文件。加 --upload 先传平台临时地址（上传不计费），"
                            "或直接给公网 URL。" % label, EXIT_USAGE)
    if getattr(a, "dry_run", False):
        return "<dry-run：本地文件 %s 未上传>" % os.path.basename(v)
    say("正在上传 %s（%s，不计费）…" % (label, os.path.basename(v)))
    st, txt = http_multipart(host + API_PREFIX + "/upload", key, {}, [("file", v)])
    if st not in (200, 201):
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    urls = find_urls(data) if ok else find_urls(d)
    urls = [u for u in urls if not AUDIO_EXT.search(u) and not VIDEO_EXT.search(u)] or urls
    if not urls:
        raise Fail("call", "上传返回里没有 url：%s" % txt.replace("\n", " ")[:300], EXIT_CALL)
    say("  已上传：%s（最长 24 小时有效）" % urls[0])
    return urls[0]


# ───────────────────────── 提交 + 轮询 ─────────────────────────
def _gate(a, points, what):
    """两道闸门：预算（5）→ 确认（4）。到这里还一个请求都没发。"""
    if points > a.budget:
        raise Fail("budget",
                   "预计 %s 点（%.2f 元）超过 --budget %s 点。%s\n"
                   "一个请求都没发。调大 --budget（单位：点，1 元 = 100 点）或减少章节。"
                   % (fmt_pts(points), yuan(points), fmt_pts(a.budget), what), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会产生真实扣费：%s，预计 %s 点（%.2f 元）。确认请加 --yes；"
                   "只想看请求体用 --dry-run。"
                   % (what, fmt_pts(points), yuan(points)), EXIT_CONFIRM)
    return points


def submit(a, key, host, app, api, body, timeout=120):
    url = host + API_PREFIX + "/apps/%s/%s" % (app, api)
    st, txt = http_json("POST", url, key, body, timeout=timeout)
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    if not ok or st not in (200, 201):
        raise Fail("call", "提交失败（%s · HTTP %s）：%s"
                   % (app + "/" + api, st, msg or err_text(st, txt)), EXIT_CALL)
    task_id = data.get("task_id") if isinstance(data, dict) else None
    if not task_id:
        raise Fail("call", "提交成功但没拿到 task_id：%s" % txt.replace("\n", " ")[:300],
                   EXIT_CALL)
    return str(task_id), data


def wait_task(a, key, host, task_id):
    """轮询只走 GET /api/v1/tasks/{id}（只读、免费）。绝不碰应用层 /query。"""
    deadline = time.time() + max(60, a.timeout)
    interval = max(2, a.interval)
    last, empty_hits = None, 0
    while True:
        st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + str(task_id), key,
                            timeout=60)
        d = jloads(txt) or {}
        status, node = dig_task(d)
        s = str(status or "").lower()
        if s != last:
            if not a.json:
                say("  [%s] %s" % (time.strftime("%H:%M:%S"), s or "?"))
            last = s
        if s in TERMINAL_OK:
            # 刚 completed 时结果地址偶尔是空串（实测竞态），多等两次再认。
            if find_urls(node) or find_urls(d):
                return True, s, node, d
            empty_hits += 1
            if empty_hits >= 3:
                return True, s, node, d
        if s in TERMINAL_BAD:
            return False, s, node, d
        if time.time() >= deadline:
            raise Fail("call",
                       "等了 %d 秒还没完成。任务没丢：用 `status --task-id %s` 接着查，"
                       "**不要重新提交**（会再扣一次）。" % (a.timeout, task_id), EXIT_CALL)
        time.sleep(interval)


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    out = {
        "ok": True,
        "stages": [
            {"stage": 1, "cmd": "plan", "does": "大纲 → 讲稿 + course.json", "points": 0},
            {"stage": 2, "cmd": "voice", "does": "讲稿 → 分节口播音频",
             "app": APP_VOICE, "api": "tts_async",
             "points": "0.18 点/字（单笔 6 点起，上游实际点数 ×3）"},
            {"stage": 3, "cmd": "slide", "does": "课件图 + 音频 → 章节视频",
             "app": APP_SLIDE, "api": "submit",
             "points": "10 / 15 / 30 / 60 点/输入秒（fast / standard / 2k / 4k）"},
            {"stage": 4, "cmd": "mouth", "does": "图 + 参考音色 + 文案 → 口播",
             "app": APP_MOUTH, "api": "submit",
             "points": "15 点/秒（上游实际点数 ×5，单笔 50 点起）"},
            {"stage": 5, "cmd": "stitch", "does": "章节视频 → ffconcat 拼接清单", "points": 0},
        ],
        "routes": {
            "slide": {"app": APP_SLIDE, "ratesPerSecond": SLIDE_RATES,
                      "modeRequired": True, "defaultModel": "fast"},
            "mouth": {"app": APP_MOUTH, "pointsPerSecond": MOUTH_POINTS_PER_SEC,
                      "minPoints": MOUTH_MIN_POINTS, "quality": QUALITIES},
        },
        "query": "GET /api/v1/tasks/{task_id}（只读、免费；应用层 /query 一次就是一次的钱）",
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("课程视频 · 5 段链路（1 元 = 100 点）")
    print()
    print("  ① plan    大纲 .md → 讲稿 + course.json 进度清单                 0 点")
    print("  ② voice   讲稿 → 分节口播音频     voice_tts/tts_async            0.18 点/字")
    print("  ③ slide   课件图 + 音频 → 章节视频 image_human/submit            10/15/30/60 点/输入秒")
    print("  ④ mouth   图 + 参考音色 + 文案 → 口播 pic_lipsync/submit         15 点/秒")
    print("  ⑤ stitch  章节视频 → ffconcat 拼接清单                       0 点")
    print()
    print("  两条出片路线，同一章 60 秒：")
    print("    slide fast   10 点/秒 × 60 =   600 点（6.00 元）  ← 最便宜，课件图全驱")
    print("    slide 4k     60 点/秒 × 60 = 3,600 点（36.00 元） ← 超清")
    print("    mouth        15 点/秒 × 60 =   900 点（9.00 元）  ← 一图 + 参考音色，省掉配音")
    print()
    print("  查询一律 GET /api/v1/tasks/{id}。应用层 /query 每轮询一次就是一次的钱，本包不发。")
    print()
    print("  下一步：python3 scripts/run.py cost --chapters 10 --seconds 60 --route slide --mode fast")
    return 0


def cmd_cost(a, key, host):
    route = a.route
    sec = float(a.seconds)
    if route == "slide":
        if not a.mode:
            raise Fail("usage",
                       "slide 路线必须显式给 --mode fast|standard|2k|4k（三个数差 6 倍，"
                       "本包不替你猜档位）", EXIT_USAGE)
        rate = SLIDE_RATES[a.mode]
        per = slide_points(a.mode, sec)
        detail = "每章 %.0f 秒 × %d 点/秒（%s 档）= %d 点/章" % (sec, rate, a.mode, per)
    elif route == "mouth":
        per = mouth_points(sec)
        detail = "每章 %.0f 秒 × %d 点/秒 = %d 点/章（单笔 %d 点起）" % (
            sec, MOUTH_POINTS_PER_SEC, per, MOUTH_MIN_POINTS)
    else:
        raise Fail("usage", "未知的 --route：%s（slide / mouth）" % route, EXIT_USAGE)

    n = int(a.chapters)
    voice_per = max(TTS_MIN_POINTS, int(round(sec * CHARS_PER_SEC * TTS_POINTS_PER_CHAR)))
    voice_total = 0 if a.no_voice else voice_per * n
    total = per * n + voice_total
    rows = []
    for m in SLIDE_MODES:
        p = slide_points(m, sec) * n + voice_total
        rows.append({"mode": m, "ratePerSecond": SLIDE_RATES[m],
                     "chapters": n, "secondsPerChapter": sec,
                     "points": p, "yuan": yuan(p)})
    out = {"ok": True, "route": route, "mode": a.mode, "chapters": n,
           "secondsPerChapter": sec, "perChapter": per, "detail": detail,
           "voicePerChapter": 0 if a.no_voice else voice_per,
           "voiceTotal": voice_total, "totalPoints": total, "yuan": yuan(total),
           "budget": a.budget, "overBudget": total > a.budget,
           "byMode": rows if route == "slide" else [],
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-07 核对）",
               "image_human 按【输入音频秒数】计费，带上 duration 价格才被费率卡锁死",
               "voice_tts 按上游实际点数 ×3，这里按实测 0.18 点/字估算，单笔 6 点起",
               "pic_lipsync 按上游实际点数 ×5，上游实测固定 3 点/秒 → 15 点/秒",
               "画面在真跑时以上游返回的 usage.points_cost 为准",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）")
    print()
    print("  %s" % detail)
    print("  × %d 章 = %s 点（%.2f 元）" % (n, fmt_pts(per * n), yuan(per * n)))
    if voice_total:
        print("  + 配音 %d 点/章 × %d 章 = %s 点（%.2f 元）"
              % (voice_per, n, fmt_pts(voice_total), yuan(voice_total)))
    print("  = **%s 点 = %.2f 元**" % (fmt_pts(total), yuan(total)))
    print()
    if route == "slide":
        print("  换个档位看（含配音）：")
        for r in rows:
            mark = "  ← 当前" if r["mode"] == a.mode else ""
            print("    %-9s %2d 点/秒 × %d 章 = %8s 点 = %7.2f 元%s"
                  % (r["mode"], r["ratePerSecond"], n, fmt_pts(r["points"]),
                     r["yuan"], mark))
        print()
    for nt in out["notes"]:
        print("  · %s" % nt)
    if total > a.budget:
        print()
        print("  已超过 --budget %s 点：真实执行会退 5，一个请求都不发。"
              % fmt_pts(a.budget))
    return 0


def cmd_doctor(a, key, host):
    """只跑 4 个只读 GET：apps / pricing / tasks/{id} / user/balance。

    为什么一个 POST 都不发 —— 实测应用层 submit 会**先同步预扣再验参**，
    连「缺必填」的请求都会产生「冻结 -250 → 退款 +250」的一对流水；
    `list_voices` 这种看着免费的也是「-150 / +150」。
    自检不该动钱包，所以端点存在性改用定价表里已配价的三条规则来证明。
    """
    checks = []

    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    apps = data if isinstance(data, list) else (
        (data or {}).get("apps") if isinstance(data, dict) else None)
    checks.append(("Key 有效 + 应用目录可达", st == 200 and ok,
                   "HTTP %s %s · %s 个应用" % (st, msg[:16] or "",
                                              len(apps) if isinstance(apps, list) else "?")))

    st2, txt2 = http_json("GET", host + API_PREFIX
                          + "/pricing?type=app_api&app_code=%s&api_code=submit"
                          % APP_SLIDE, key, timeout=60)
    d2 = jloads(txt2) or {}
    rows = d2.get("pricing") if isinstance(d2.get("pricing"), dict) else {}
    need = ["/api/v1/apps/%s/submit" % APP_SLIDE, "/api/v1/apps/%s/submit" % APP_MOUTH]
    missing = [p for p in need if p not in rows]
    voice_keys = [k for k in rows if k.startswith("/api/v1/apps/%s/" % APP_VOICE)]
    if not voice_keys:
        missing.append("/api/v1/apps/%s/*" % APP_VOICE)
    checks.append(("三条链路都已在网关配价", (not missing) and bool(rows),
                   "缺 %s" % "、".join(missing[:3]) if missing
                   else "定价表 %d 条，命中 3/3 条链路" % len(rows)))

    ih = rows.get("/api/v1/apps/%s/submit" % APP_SLIDE) or {}
    rates = ih.get("modelRates") or {}
    live = dict((k, (v or {}).get("*")) for k, v in rates.items()) if rates else {}
    match = bool(live) and all(live.get(k) == v for k, v in SLIDE_RATES.items())
    checks.append(("速率卡一致（10/15/30/60 点/输入秒）", match,
                   ("live=%s · defaultModel=%s" % (json.dumps(live, ensure_ascii=False),
                                                   ih.get("defaultModel")))
                   if live else "HTTP %s 没读到 modelRates" % st2))

    pl = rows.get("/api/v1/apps/%s/submit" % APP_MOUTH) or {}
    checks.append(("口播口径一致（上游实际点数 ×5）", pl.get("markupPercent") == 400,
                   "markupPercent=%s · minPoints=%s（声明字段）"
                   % (pl.get("markupPercent"), pl.get("minPoints"))))

    st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-doctor-probe", key,
                          timeout=60)
    d4 = jloads(txt4) or {}
    ok4 = st4 == 200 and "任务不存在" in str(d4.get("msg") or "")
    checks.append(("轮询线 GET /api/v1/tasks/{id} 可用", ok4,
                   "HTTP %s %s" % (st4, str(d4.get("msg") or txt4.replace("\n", " "))[:28])))

    st5, txt5 = http_json("GET", host + "/user/balance", key, timeout=60)
    d5 = jloads(txt5) or {}
    pts = d5.get("available_points")
    if pts is None:
        pts = d5.get("points")
    checks.append(("余额可读", st5 == 200 and pts is not None,
                   "%s 点（%.2f 元）· 冻结 %s 点"
                   % (fmt_pts(pts), yuan(float(pts)), fmt_pts(d5.get("frozen") or 0))
                   if pts is not None else "HTTP %s" % st5))

    out = {"ok": all(c[1] for c in checks),
           "freeSurface": ["GET /api/v1/apps", "GET /api/v1/pricing",
                           "GET /api/v1/tasks/{task_id}", "GET /user/balance"],
           "endpoints": ["POST %s/apps/%s/tts_async" % (API_PREFIX, APP_VOICE),
                         "POST %s/apps/%s/submit" % (API_PREFIX, APP_SLIDE),
                         "POST %s/apps/%s/submit" % (API_PREFIX, APP_MOUTH)],
           "rates": {"slide": SLIDE_RATES, "mouth": MOUTH_POINTS_PER_SEC,
                     "voicePerChar": TTS_POINTS_PER_CHAR},
           "balance": pts,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_CALL
    print("自检（全程免费：4 个只读 GET，一个 submit 都不发）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", ljust(n, 42), dd))
    print()
    print("  三条链路：voice_tts/tts_async · image_human/submit · pic_lipsync/submit")
    print("  查询一律 GET /api/v1/tasks/{id}；应用层 /query 一次就是一次的钱，本包不发")
    print("  价目：课件图 10/15/30/60 点/输入秒 · 口播 15 点/秒 · 配音 0.18 点/字")
    return 0 if out["ok"] else EXIT_CALL


# ───────────────────────── plan（本地，0 点）─────────────────────────
def cmd_plan(a, key, host):
    if not a.outline:
        raise Fail("usage", "必须给 --outline（课程大纲 .md 路径）", EXIT_USAGE)
    if not os.path.isfile(a.outline):
        raise Fail("usage", "大纲文件不存在：%s" % a.outline, EXIT_USAGE)
    title, chapters = parse_outline(_read_text(a.outline), a.title)
    rows = []
    for i, ch in enumerate(chapters, 1):
        script = build_script(title, i, ch["title"], ch["bullets"])
        sec = float(a.seconds) if a.seconds else call_seconds(script)
        rows.append({"index": i, "title": ch["title"], "bullets": ch["bullets"],
                     "script": script, "chars": len(re.sub(r"\s+", "", script)),
                     "seconds": sec, "status": "planned",
                     "slideUrl": None, "audioUrl": None, "videoUrl": None,
                     "voiceTaskId": None, "videoTaskId": None, "spentPoints": 0})
    total_sec = round(sum(r["seconds"] for r in rows), 1)
    doc = {"version": 1, "kind": "sanjianke-course-video",
           "title": title, "outline": os.path.abspath(a.outline),
           "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "route": a.route, "mode": a.mode or "fast", "quality": a.quality,
           "chapters": rows,
           "totals": {"chapters": len(rows), "seconds": total_sec,
                      "chars": sum(r["chars"] for r in rows)}}
    out_path = course_path(a)
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(doc, ensure_ascii=False, indent=1))

    voice_total = sum(call_points(r["script"]) for r in rows)
    slide_total = sum(slide_points(doc["mode"], r["seconds"]) for r in rows)
    mouth_total = sum(mouth_points(r["seconds"]) for r in rows)
    out = {"ok": True, "course": out_path, "title": title, "chapters": len(rows),
           "seconds": total_sec, "chars": doc["totals"]["chars"],
           "estimatedPoints": {"voice": voice_total,
                               "slide_" + doc["mode"]: slide_total,
                               "mouth": mouth_total,
                               "slideTotal": voice_total + slide_total},
           "rows": [{"index": r["index"], "title": r["title"], "chars": r["chars"],
                     "seconds": r["seconds"]} for r in rows]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已切好章节，进度清单写到 %s" % out_path)
    print()
    print("  《%s》%d 章 · 讲稿共 %s 字 · 预估总时长 %.1f 秒（约 %.1f 分钟）"
          % (title, len(rows), fmt_pts(doc["totals"]["chars"]), total_sec, total_sec / 60.0))
    print()
    print("  %s %s %s %s" % (ljust("章", 8), ljust("标题", 32),
                             rjust("字数", 6), rjust("秒数", 7)))
    print("  " + "-" * 57)
    for r in rows:
        print("  %s %s %s %s" % (ljust("第%d章" % r["index"], 8),
                                 ljust(r["title"][:28], 32),
                                 rjust(r["chars"], 6), rjust("%.1f" % r["seconds"], 7)))
    print()
    print("  这一份课要花多少（1 元 = 100 点）：")
    print("    配音      %8s 点（%.2f 元）" % (fmt_pts(voice_total), yuan(voice_total)))
    print("    课件图 %-6s %8s 点（%.2f 元）"
          % (doc["mode"], fmt_pts(slide_total), yuan(slide_total)))
    print("    小计      %8s 点（%.2f 元）"
          % (fmt_pts(voice_total + slide_total), yuan(voice_total + slide_total)))
    print("    换成口播路线 %8s 点（%.2f 元，一图 + 参考音色，省掉配音）"
          % (fmt_pts(mouth_total), yuan(mouth_total)))
    print()
    print("  下一步：python3 scripts/run.py voice --course %s --limit 1 --yes" % out_path)
    return 0


# ───────────────────────── voice（付费）─────────────────────────
def cmd_voice(a, key, host):
    d = load_course(a)
    rows = todo_chapters(d, "audio", _only(a))
    if a.limit:
        rows = rows[:a.limit]
    if not rows:
        out = {"ok": True, "cmd": "voice", "chapters": 0, "points": 0,
               "message": "所有章节都已有配音，0 点"}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
        else:
            print("所有章节都已有配音了，这次 0 点。")
        return 0

    per = [call_points(c.get("script")) for c in rows]
    total = sum(per)
    what = "%d 章配音（%s 字）" % (len(rows), fmt_pts(sum(c.get("chars") or 0 for c in rows)))
    _gate(a, total, what)

    if a.dry_run:
        body = {"text": rows[0].get("script"), "format": a.format}
        if a.model:
            body["model"] = a.model
        out = {"ok": True, "dryRun": True, "cmd": "voice", "chapters": len(rows),
               "url": host + API_PREFIX + "/apps/%s/tts_async" % APP_VOICE,
               "requestBody": body, "estimatedPoints": total,
               "perChapter": dict((c["index"], call_points(c.get("script")))
                                  for c in rows)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s/api/v1/apps/%s/tts_async" % (host, APP_VOICE))
        print("  请求：%s" % json.dumps(body, ensure_ascii=False)[:400])
        print("  章数：%d · 预估 %s 点（%.2f 元）"
              % (len(rows), fmt_pts(total), yuan(total)))
        print("  轮询：GET %s/api/v1/tasks/{task_id}（免费）" % host)
        return 0

    t0 = time.time()
    results = []
    for n, c in enumerate(rows, 1):
        say("[%d/%d] 第 %s 章 配音（%s 字）…" % (n, len(rows), c.get("index"), c.get("chars")))
        body = {"text": c.get("script"), "format": a.format}
        if a.model:
            body["model"] = a.model
        task_id, data = submit(a, key, host, APP_VOICE, "tts_async", body, timeout=a.timeout)
        c["voiceTaskId"] = task_id
        done, status, node, d2 = wait_task(a, key, host, task_id)
        urls = find_urls(node) or find_urls(d2)
        audio = pick(urls, AUDIO_EXT) or pick(urls, re.compile(r"."))
        billed = find_points(d2)
        if not done or not audio:
            c["status"] = "voice_failed"
            save_course(a, d)
            ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "cmd": "voice",
                        "chapter": c.get("index"), "taskId": task_id, "status": status,
                        "error": json.dumps(node, ensure_ascii=False)[:200]})
            raise Fail("call", "第 %s 章配音失败（status=%s）。用 `status --task-id %s` 看详情，"
                               "**不要重新提交**（会再扣一次）。"
                       % (c.get("index"), status, task_id), EXIT_CALL)
        c["audioUrl"] = audio
        c["status"] = "audio"
        c["spentPoints"] = round(float(c.get("spentPoints") or 0) + (billed or 0), 2)
        save_course(a, d)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "cmd": "voice",
                    "chapter": c.get("index"), "taskId": task_id, "status": status,
                    "points": billed, "estimatedPoints": call_points(c.get("script"))})
        results.append({"index": c.get("index"), "title": c.get("title"),
                        "taskId": task_id, "status": status, "audioUrl": audio,
                        "points": billed})
        say("  第 %s 章音频好了：%s" % (c.get("index"), audio))

    elapsed = time.time() - t0
    spent = sum(float(r.get("points") or 0) for r in results)
    out = {"ok": True, "cmd": "voice", "course": course_path(a), "chapters": len(results),
           "estimatedPoints": total, "billedPoints": round(spent, 2),
           "elapsed": round(elapsed, 1), "results": results,
           "next": "python3 scripts/run.py slide --course %s --image 课件图.png --mode %s --yes"
                   % (course_path(a), d.get("mode") or "fast")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("配音完成（%.1fs）" % elapsed)
    for r in results:
        print("  第 %-3s 章 %-22s %s" % (r["index"], (r["title"] or "")[:20], r["audioUrl"]))
    if spent:
        print("  实际扣费：%.2f 点（%.2f 元）" % (spent, yuan(spent)))
    print("  预估：%s 点（%.2f 元）· 进度已写回 %s"
          % (fmt_pts(total), yuan(total), course_path(a)))
    print()
    print("  下一步：python3 scripts/run.py slide --course %s --image 课件图.png --mode %s --yes"
          % (course_path(a), d.get("mode") or "fast"))
    return 0


# ───────────────────────── slide（付费）─────────────────────────
def cmd_slide(a, key, host):
    d = load_course(a)
    stage = "slide"
    rows = todo_chapters(d, "video", _only(a))
    if a.limit:
        rows = rows[:a.limit]
    missing_audio = [c.get("index") for c in rows if not c.get("audioUrl")]
    if not rows:
        out = {"ok": True, "cmd": stage, "chapters": 0, "points": 0,
               "message": "所有章节都已有成片，0 点"}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
        else:
            print("所有章节都已有成片了，这次 0 点。")
        return 0
    if not a.mode:
        raise Fail("usage",
                   "必须显式给 --mode fast|standard|2k|4k。\n"
                   "不传 mode 时：schema 默认 standard、计费卡默认 fast，"
                   "出片档位和账单档位会对不上，所以本包不替你猜。", EXIT_USAGE)

    pad = max(0, int(a.pad or 0))
    per = []
    for c in rows:
        sec = float(c.get("seconds") or 0)
        sec = round(sec * (1 + pad / 100.0), 1)
        per.append(slide_points(a.mode, sec))
    total = sum(per)
    what = "%d 章课件视频（%s 档，%d 点/输入秒）" % (len(rows), a.mode, SLIDE_RATES[a.mode])
    _gate(a, total, what)

    image = a.image or _first_slide(d)
    if not image:
        raise Fail("usage", "必须给 --image（课件图 URL 或本地文件 + --upload），"
                            "或在 course.json 里给每章填 slideUrl。", EXIT_USAGE)

    if a.dry_run:
        first = rows[0]
        body = {"file_url": image, "ref_file_url": first.get("audioUrl"),
                "duration": round(float(first.get("seconds") or 0) * (1 + pad / 100.0), 1),
                "mode": a.mode}
        out = {"ok": True, "dryRun": True, "cmd": stage, "chapters": len(rows),
               "url": host + API_PREFIX + "/apps/%s/submit" % APP_SLIDE,
               "requestBody": body, "estimatedPoints": total,
               "perChapter": dict((c["index"], p) for c, p in zip(rows, per))}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s/api/v1/apps/%s/submit" % (host, APP_SLIDE))
        print("  请求：%s" % json.dumps(body, ensure_ascii=False)[:400])
        print("  章数：%d · 预估 %s 点（%.2f 元）"
              % (len(rows), fmt_pts(total), yuan(total)))
        print("  轮询：GET %s/api/v1/tasks/{task_id}（免费）" % host)
        if missing_audio:
            print("  这几章还没有配音，真跑前要先 voice：第 %s 章"
                  % "、".join(str(i) for i in missing_audio[:6]))
        return 0

    if missing_audio:
        raise Fail("usage",
                   "第 %s 章还没有配音（audioUrl）。先跑 `voice --course %s`："
                   "image_human 要一段真实音频来驱动，按音频秒数计费。"
                   % ("、".join(str(i) for i in missing_audio[:6]), course_path(a)),
                   EXIT_USAGE)

    # 闸门已经过了（预算 + 确认），现在才允许产生请求；上传不计费，0 点/次。
    base_url = materialize(a, key, host, a.image, "--image") if a.image else None
    t0 = time.time()
    results = []
    for n, (c, est) in enumerate(zip(rows, per), 1):
        img_url = base_url or c.get("slideUrl") or image
        sec = round(float(c.get("seconds") or 0) * (1 + pad / 100.0), 1)
        body = {"file_url": img_url, "ref_file_url": c.get("audioUrl"),
                "duration": sec, "mode": a.mode}
        if a.prompt:
            body["prompt"] = a.prompt
        say("[%d/%d] 第 %s 章 出片（%s 档 · %.1f 秒 · 约 %s 点）…"
            % (n, len(rows), c.get("index"), a.mode, sec, fmt_pts(est)))
        task_id, data = submit(a, key, host, APP_SLIDE, "submit", body, timeout=a.timeout)
        c["videoTaskId"] = task_id
        c["slideUrl"] = img_url
        save_course(a, d)
        done, status, node, d2 = wait_task(a, key, host, task_id)
        urls = find_urls(node) or find_urls(d2)
        video = pick(urls, VIDEO_EXT) or pick(urls, re.compile(r"."))
        billed = find_points(d2)
        if not done or not video:
            c["status"] = "video_failed"
            save_course(a, d)
            ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "cmd": stage,
                        "chapter": c.get("index"), "taskId": task_id, "status": status,
                        "error": json.dumps(node, ensure_ascii=False)[:200]})
            raise Fail("call", "第 %s 章出片失败（status=%s）。用 `status --task-id %s` 看详情，"
                               "**不要重新提交**（会再扣一次）。"
                       % (c.get("index"), status, task_id), EXIT_CALL)
        c["videoUrl"] = video
        c["status"] = "video"
        c["spentPoints"] = round(float(c.get("spentPoints") or 0) + (billed or 0), 2)
        save_course(a, d)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "cmd": stage,
                    "chapter": c.get("index"), "taskId": task_id, "status": status,
                    "mode": a.mode, "points": billed, "estimatedPoints": est})
        results.append({"index": c.get("index"), "title": c.get("title"),
                        "taskId": task_id, "status": status, "videoUrl": video,
                        "points": billed})
        say("  第 %s 章成片：%s" % (c.get("index"), video))

    elapsed = time.time() - t0
    spent = sum(float(r.get("points") or 0) for r in results)
    out = {"ok": True, "cmd": stage, "course": course_path(a), "chapters": len(results),
           "mode": a.mode, "estimatedPoints": total, "billedPoints": round(spent, 2),
           "elapsed": round(elapsed, 1), "results": results,
           "next": "python3 scripts/run.py stitch --course %s" % course_path(a)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("出片完成（%.1fs）" % elapsed)
    for r in results:
        print("  第 %-3s 章 %-22s %s" % (r["index"], (r["title"] or "")[:20], r["videoUrl"]))
    if spent:
        print("  实际扣费：%.2f 点（%.2f 元）" % (spent, yuan(spent)))
    print("  预估：%s 点（%.2f 元）· 进度已写回 %s"
          % (fmt_pts(total), yuan(total), course_path(a)))
    print()
    print("  下一步：python3 scripts/run.py stitch --course %s" % course_path(a))
    return 0


def _first_slide(d):
    for c in d.get("chapters") or []:
        if c.get("slideUrl"):
            return c["slideUrl"]
    return None


# ───────────────────────── mouth（付费，单条）─────────────────────────
def cmd_mouth(a, key, host):
    if not a.image:
        raise Fail("usage", "必须给 --image（讲师图 URL，或本地文件 + --upload）", EXIT_USAGE)
    if not a.voice_ref:
        raise Fail("usage",
                   "必须给 --voice-ref（参考音色，3–10 秒单人清晰人声）。"
                   "文案驱动省掉的是录音，省不掉音色样本。", EXIT_USAGE)
    if not a.content:
        raise Fail("usage", "必须给 --content（这一节要念的文案）", EXIT_USAGE)
    if a.quality not in QUALITIES:
        raise Fail("usage", "--quality 只能是 %s（档位真名是 quality，不是 mode）"
                   % " / ".join(QUALITIES), EXIT_USAGE)
    sec = float(a.seconds) if a.seconds else call_seconds(a.content)
    pts = mouth_points(sec)
    _gate(a, pts, "文案 %d 字 ≈ %.1f 秒口播（%s 档）"
          % (len(re.sub(r"\s+", "", a.content)), sec, a.quality))

    if a.dry_run:
        body = {"image_url": a.image, "audio_url": a.voice_ref, "content": a.content,
                "mode": "text", "quality": a.quality}
        out = {"ok": True, "dryRun": True, "cmd": "mouth",
               "url": host + API_PREFIX + "/apps/%s/submit" % APP_MOUTH,
               "requestBody": body, "estimatedPoints": pts, "seconds": sec}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s/api/v1/apps/%s/submit" % (host, APP_MOUTH))
        print("  请求：%s" % json.dumps(body, ensure_ascii=False)[:400])
        print("  预估：%s 点（%.2f 元）· %.1f 秒" % (fmt_pts(pts), yuan(pts), sec))
        return 0

    image_url = materialize(a, key, host, a.image, "--image")
    audio_url = materialize(a, key, host, a.voice_ref, "--voice-ref")
    body = {"image_url": image_url, "audio_url": audio_url, "content": a.content,
            "mode": "text", "quality": a.quality}
    if a.prompt:
        body["prompt"] = a.prompt
    say("正在提交文案驱动口播（%s 档）…" % a.quality)
    t0 = time.time()
    task_id, data = submit(a, key, host, APP_MOUTH, "submit", body, timeout=a.timeout)
    say("  task_id = %s" % task_id)
    if a.no_wait:
        out = {"ok": True, "cmd": "mouth", "taskId": task_id, "status": "submitted",
               "estimatedPoints": pts, "seconds": sec,
               "next": "python3 scripts/run.py status --task-id %s" % task_id}
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "cmd": "mouth",
                    "taskId": task_id, "status": "submitted", "estimatedPoints": pts})
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("已提交，不等待结果")
        print("  task_id：%s" % task_id)
        print("  接着查：python3 scripts/run.py status --task-id %s" % task_id)
        return 0

    done, status, node, d2 = wait_task(a, key, host, task_id)
    urls = find_urls(node) or find_urls(d2)
    video = pick(urls, VIDEO_EXT) or pick(urls, re.compile(r"."))
    billed = find_points(d2)
    elapsed = time.time() - t0
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(done and video),
                "cmd": "mouth", "taskId": task_id, "status": status,
                "points": billed, "estimatedPoints": pts})
    out = {"ok": bool(done and video), "cmd": "mouth", "taskId": task_id, "status": status,
           "videoUrl": video, "estimatedPoints": pts, "billedPoints": billed,
           "seconds": sec, "elapsed": round(elapsed, 1)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if done and video else EXIT_CALL
    if not done:
        say("任务失败（status=%s）：%s" % (status, json.dumps(node, ensure_ascii=False)[:300]))
        return EXIT_CALL
    print("完成（%.1fs）" % elapsed)
    print("  task_id：%s" % task_id)
    if video:
        print("  成片：%s" % video)
    if billed is not None:
        print("  实际扣费：%.2f 点（%.2f 元）" % (billed, yuan(billed)))
    print("  预估：%s 点（%.2f 元）" % (fmt_pts(pts), yuan(pts)))
    return 0


# ───────────────────────── stitch（本地，0 点）─────────────────────────
def cmd_stitch(a, key, host):
    d = load_course(a)
    rows = [c for c in d["chapters"] if c.get("videoUrl")]
    d["stitchedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    out_file = a.out or (os.path.splitext(course_path(a))[0] + "-concat.txt")
    lines = ["ffconcat version 1.0"]
    for c in rows:
        lines.append("file '%s'" % c["videoUrl"])
    io.open(out_file, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    d["concatFile"] = out_file
    save_course(a, d)

    total = len(d["chapters"])
    with_video = len(rows)
    with_audio = len([c for c in d["chapters"] if c.get("audioUrl")])
    seconds = round(sum(float(c.get("seconds") or 0) for c in rows), 1)
    spent = round(sum(float(c.get("spentPoints") or 0) for c in d["chapters"]), 2)
    cmdline = 'ffmpeg -f concat -safe 0 -i "%s" -c copy "%s"' % (
        out_file, a.out or "course.mp4")

    out = {"ok": True, "cmd": "stitch", "course": course_path(a), "concatFile": out_file,
           "chapters": total, "withAudio": with_audio, "withVideo": with_video,
           "seconds": seconds, "spentPoints": spent, "ffmpeg": cmdline,
           "progress": dict((str(c["index"]), c.get("status")) for c in d["chapters"])}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("进度清单 %s" % course_path(a))
    print("  《%s》共 %d 章 · 配音 %d 章 · 成片 %d 章 · 总时长 %.1f 秒（约 %.1f 分钟）"
          % (d.get("title") or "-", total, with_audio, with_video, seconds, seconds / 60.0))
    print()
    print("  %s %s %s %s" % (ljust("章", 8), ljust("标题", 30),
                             ljust("状态", 12), "成片"))
    print("  " + "-" * 66)
    for c in d["chapters"]:
        print("  %s %s %s %s" % (ljust("第%d章" % c["index"], 8),
                                 ljust((c.get("title") or "")[:26], 30),
                                 ljust(c.get("status") or "-", 12),
                                 (c.get("videoUrl") or "-")[:40]))
    print()
    print("  拼接清单：%s（%d 条）" % (out_file, with_video))
    if with_video:
        print("  拼成一条完整课：")
        print("    %s" % cmdline)
    else:
        print("  还没有成片。先跑 slide 或 mouth，再把地址写进 course.json。")
    if spent:
        print("  这一份课累计花了：%.2f 点（%.2f 元）" % (spent, yuan(spent)))
    return 0


# ───────────────────────── status / log ─────────────────────────
def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + str(a.task_id), key,
                        timeout=60)
    d = jloads(txt) or {}
    if st != 200 or d.get("code") not in (0, 1, None):
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if d.get("code") == 0 and not d.get("data"):
        raise Fail("call", "查不到任务 %s：%s" % (a.task_id, d.get("msg") or "任务不存在"),
                   EXIT_CALL)
    status, node = dig_task(d)
    urls = find_urls(node) or find_urls(d)
    billed = find_points(d)
    out = {"ok": True, "cmd": "status", "taskId": a.task_id, "status": status,
           "urls": urls, "videoUrl": pick(urls, VIDEO_EXT),
           "audioUrl": pick(urls, AUDIO_EXT), "points": billed, "raw": node}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s" % (status or "未知"))
    if billed is not None:
        print("  实际点数：%.2f 点（%.2f 元）" % (billed, yuan(billed)))
    v = out["videoUrl"]
    au = out["audioUrl"]
    if v:
        print("  成片：%s" % v)
    if au:
        print("  音频：%s" % au)
    if not v and not au and str(status or "").lower() in TERMINAL_OK:
        print("  刚 completed 时结果地址偶尔是空串，隔几秒再查一次。")
    print("  查询走 GET /api/v1/tasks/{id}，免费；不要用应用层 /query。")
    return 0


def cmd_log(a, key, host):
    arr = ledger_load()
    entries = arr[-a.limit:] if a.limit else arr
    out = {"ok": True, "count": len(arr), "entries": entries}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(entries), len(arr)))
    if not arr:
        print("  还没有记录。跑一次 voice / slide / mouth 就会写进来。")
        return 0
    total = 0.0
    for e in entries:
        try:
            total += float(e.get("points") or 0)
        except (TypeError, ValueError):
            pass
        print("  %s  %-5s %-6s %-3s %-24s %s 点" % (
            e.get("at") or "-", "OK" if e.get("ok") else "FAIL",
            e.get("cmd") or "-", e.get("chapter") or "-",
            str(e.get("taskId") or "-")[:24],
            e.get("points") if e.get("points") is not None else "-"))
    print("  本页合计：%.2f 点（%.2f 元）" % (total, yuan(total)))
    return 0


def _only(a):
    raw = getattr(a, "only", None)
    if not raw:
        return None
    out = set()
    for bit in str(raw).replace("，", ",").split(","):
        bit = bit.strip()
        if not bit:
            continue
        try:
            out.add(int(bit))
        except ValueError:
            raise Fail("usage", "--only 要写章号，比如 3,4", EXIT_USAGE)
    return out or None


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 课程视频（一份大纲 → 一整套讲师口播课件）",
        epilog="端点：POST %s/api/v1/apps/voice_tts/tts_async · "
               "POST %s/api/v1/apps/image_human/submit · "
               "POST %s/api/v1/apps/pic_lipsync/submit · "
               "GET %s/api/v1/tasks/{task_id}" % (DEFAULT_HOST, DEFAULT_HOST,
                                                  DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d = 50 元）"
                         % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="5 段链路 + 三条路线价目对照（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：章节数 × 每章秒数（免费）", allow_abbrev=False)
    p.add_argument("--route", default="slide", choices=["slide", "mouth"],
                   help="算哪条路线（默认 slide）")
    p.add_argument("--mode", choices=SLIDE_MODES,
                   help="slide 档位 fast/standard/2k/4k（算 slide 时必填）")
    p.add_argument("--chapters", type=int, default=10, help="几章（默认 10）")
    p.add_argument("--seconds", type=float, default=60, help="每章多少秒（默认 60）")
    p.add_argument("--no-voice", action="store_true", help="不算配音那一笔")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 三条链路 / 速率卡（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("plan", help="大纲 → 讲稿 + 进度清单（免费，本地）",
                       allow_abbrev=False)
    p.add_argument("--outline", help="课程大纲 .md（`# 课程名` + 每个 `## 第 N 章`）")
    p.add_argument("-o", "--course", default="course.json", help="进度清单输出路径")
    p.add_argument("--title", help="覆盖大纲里的课程名")
    p.add_argument("--route", default="slide", choices=["slide", "mouth"],
                   help="默认出片路线（默认 slide）")
    p.add_argument("--mode", default="fast", choices=SLIDE_MODES,
                   help="默认档位（默认 fast = 10 点/输入秒）")
    p.add_argument("--quality", default="standard", choices=QUALITIES,
                   help="mouth 路线默认档位（默认 standard）")
    p.add_argument("--seconds", type=float, default=None,
                   help="强制每章秒数（默认按讲稿字数 ÷ 4.5 算）")
    p.set_defaults(fn=cmd_plan)

    def add_common(p):
        p.add_argument("--course", default="course.json", help="进度清单路径（默认 course.json）")
        p.add_argument("--limit", type=int, default=0, help="本次最多跑几章（默认全部）")
        p.add_argument("--only", help="只跑这几章，比如 3,4")
        p.add_argument("--timeout", type=int, default=900, help="等待上限秒数（默认 900）")
        p.add_argument("--interval", type=int, default=5, help="轮询间隔秒数（默认 5）")
        p.add_argument("--yes", action="store_true", help="确认真实扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("voice", help="分节口播出音频（voice_tts，0.18 点/字）",
                       allow_abbrev=False)
    add_common(p)
    p.add_argument("--format", default="mp3", choices=["mp3", "wav", "opus", "pcm"],
                   help="输出格式（默认 mp3）")
    p.add_argument("--model", help="TTS 模型（默认用平台配置的 s2-pro）")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("slide", help="课件图 → 章节视频（image_human，按输入秒计费）",
                       allow_abbrev=False)
    add_common(p)
    p.add_argument("--image", help="课件图：公网 URL，或本地文件 + --upload")
    p.add_argument("--mode", required=True, choices=SLIDE_MODES,
                   help="档位 fast 10 / standard 15 / 2k 30 / 4k 60 点/输入秒（必填；"
                        "schema 默认 standard、计费卡默认 fast，不传会对不上）")
    p.add_argument("--prompt", help="画面提示词（默认「人物说话自然，面对镜头…」）")
    p.add_argument("--pad", type=int, default=0,
                   help="给 duration 留余量（百分比，默认 0；建议 10）")
    p.add_argument("--upload", action="store_true",
                   help="本地课件图先传平台临时地址（上传不计费，0 点/次）")
    p.set_defaults(fn=cmd_slide)

    p = sub.add_parser("mouth", help="一图 + 参考音色 + 文案 → 口播（pic_lipsync，15 点/秒）",
                       allow_abbrev=False)
    p.add_argument("--image", help="讲师图：公网 URL，或本地文件 + --upload")
    p.add_argument("--voice-ref", help="参考音色音频：3–10 秒单人清晰人声（必填）")
    p.add_argument("--content", help="这一节要念的文案")
    p.add_argument("--quality", default="standard", choices=QUALITIES,
                   help="standard（默认）/ fast / max（档位真名是 quality）")
    p.add_argument("--prompt", help="人物动作、表情、画面风格（可选）")
    p.add_argument("--seconds", type=float, help="直接给秒数（默认按字数 ÷ 4.5）")
    p.add_argument("--upload", action="store_true",
                   help="本地素材先传平台临时地址（上传不计费）")
    p.add_argument("--no-wait", action="store_true", help="只提交，不等待结果")
    p.add_argument("--timeout", type=int, default=900, help="等待上限秒数（默认 900）")
    p.add_argument("--interval", type=int, default=5, help="轮询间隔秒数（默认 5）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_mouth)

    p = sub.add_parser("stitch", help="章节拼接清单 + 进度回看（免费，本地）",
                       allow_abbrev=False)
    p.add_argument("--course", default="course.json", help="进度清单路径（默认 course.json）")
    p.add_argument("--out", help="拼接清单输出路径（默认 <course>-concat.txt）")
    p.set_defaults(fn=cmd_stitch)

    p = sub.add_parser("status", help="查任务 GET /api/v1/tasks/{id}（免费）",
                       allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 task_id")
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


LOCAL_CMDS = (cmd_catalog, cmd_cost, cmd_plan, cmd_stitch, cmd_log)


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
    key, host = load_conf(getattr(a, "key", None), getattr(a, "host", None))
    if not key and a.fn not in LOCAL_CMDS:
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
        say("已中断。进度已写回 course.json，接着跑同一条命令会从断点继续。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
