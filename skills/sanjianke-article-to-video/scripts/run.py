#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 图文转视频

一篇公众号文章进，一条带旁白与配乐的成片出。五段链路，每段都走 api.a7w.cn：

  1 分镜   本地按段落与句读切镜，0 点（纯本地，不联网）
  2 出图   gpt-image-2.6      POST /api/v1/images/generations      6 点/张
  3 动起来 full_video         POST /api/v1/apps/full_video/submit  480P 14 点/秒
  4 旁白   voice_tts          POST /api/v1/apps/voice_tts/tts      约 0.18 点/字
  5 配乐   media_services_33  POST /api/v1/apps/media_services_33/music_generate

改图另有一条：nano_banana submit（72 点/次），拿参考图改画面风格。

## 价格锚点（GET /api/v1/pricing 实测，2026-11-07，1 元 = 100 点）

  出图      6 点/张          gpt-image-2.6，与尺寸、张数档都无关
  改图     72 点/次          nano_banana
  图生视频 480P 14 点/秒   768P 28 点/秒   1080P 60 点/秒   2K/4K 80 点/秒
  旁白      约 0.18 点/字    上游真实点数 x 3，实测 33 字 = 5.94 点
  配乐     50 点起/首        media_services_33 落通配：上游点数 x 2，单笔保底 50 点

一篇 2000 字文章，默认切成 12 镜、每镜 5 秒（60 秒成片）：
  12 x 6 + 12 x 5 x 14 + 360 x 0.18 + 50 = 1,027 点 = 10.27 元
想要全文照念（67 镜、335 秒），约 5,502 点 = 55.02 元。`cost` 会把两档都算给你。

## 三条用钱换来的规矩（已写进默认动作）

  · 查进度只走 GET /api/v1/tasks/<id>（访客免费）。应用层的 /query 每查一次就是一次的钱，
    nano_banana 这类 72 点/次的接口，历史上有账号靠轮询烧掉 15,552 点。
  · 从不 GET /api/v1/apps/<app> —— 这条读接口命中通配计价，是「即时扣费不退」，
    本包目录信息只取 GET /api/v1/apps（列表，cost:0）与 GET /api/v1/pricing。
  · 图地址先过 POST /api/v1/upload（免费）。videoUrl / image_url 有域名白名单，
    本地图必须换成 oss.gpu.likeadmin.cn 地址再提交，不能拿本机路径硬塞。

## 子命令

  catalog  五段链路的能力、端点、单价（免费）
  cost     按字数先算钱：精华版 / 全文版 / 各分辨率（免费，纯本地）
  doctor   自检 Key、应用、价目、出图端点、查询路由、上传（免费，不扣费）
  plan     文章 → 分镜脚本 storyboard.json + narration.txt（0 点，纯本地）
  image    逐镜出图（6 点/张；带 --ref 改走 nano_banana 72 点/次）
  render   逐镜图生视频，轮询 GET /tasks（480P 14 点/秒起）
  voice    旁白，按 450 字切块调 tts（约 0.18 点/字）
  music    配乐一首（50 点起，下限）
  make     一键跑完 plan → image → render → voice → music → 拼接清单
  task     查任务状态（免费）
  log      本地台账

## 用法

  python3 scripts/run.py cost --chars 2000
  python3 scripts/run.py plan --article article.md
  python3 scripts/run.py image --yes
  python3 scripts/run.py render --resolution 480P --seconds 5 --yes
  python3 scripts/run.py voice --yes
  python3 scripts/run.py make --article article.md --budget 2000 --yes

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import base64
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

# ── GBK 兜底：Windows 上 stdout 被重定向时用 cp936，个别符号编不出会崩 ─────────
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "article-to-video-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-article-to-video/%s" % VERSION

# ── 五段链路（单价全部来自 GET /api/v1/pricing 实测）─────────────────────────
APP_IMAGE = "gpt-image-2.6"
IMG_POINTS = 6                       # 点/张
APP_NANO = "nano_banana"
NANO_POINTS = 72                     # 点/次
APP_VIDEO = "full_video"
VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}   # 点/秒
APP_TTS = "voice_tts"
TTS_PER_CHAR = 0.18                  # 点/字（实测 33 字 = 5.94 点）
APP_MUSIC = "media_services_33"
MUSIC_FLOOR = 50                     # 点/首，通配保底
POINTS_PER_YUAN = 100

RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]
RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "adaptive"]
DUR_MIN, DUR_MAX = 4, 15
NARR_CHARS = 30                      # 每镜旁白上限字数
SCENE_CAP = 60                       # 一篇文章最多切多少镜
CHARS_PER_SCENE = 170                # 自动分镜：多少字给一镜
TTS_CHUNK = 450                      # 同步 tts 建议 500 字内

DEFAULT_BUDGET = 2000                # 点，= 20 元
DEFAULT_OUT = "build"
DEFAULT_SB = os.path.join(DEFAULT_OUT, "storyboard.json")

TERMINAL_OK = ("completed", "success", "succeeded", "done")
TERMINAL_BAD = ("failed", "error", "cancelled", "canceled", "timeout", "expired")
VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac")


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
    """发一次请求。网关会重置空闲连接，网络类错误退避重试；4xx 直接交给调用方判断。"""
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
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise Fail("call", "连不上 %s：%s（已重试 %d 次）"
                       % (url, getattr(e, "reason", e), retries - 1), EXIT_CALL)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


def http_multipart(url, key, fields, files=None, timeout=600):
    """multipart/form-data（/api/v1/upload 的字段名是 file，免费）。"""
    boundary = "----sanjianke" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, val in (fields or {}).items():
        if val is None:
            continue
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                   % (boundary, name, val)).encode("utf-8"))
    for name, path in (files or []):
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
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code"):
            return str(d["code"])[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


def envelope(st, txt, url):
    """网关两套风格都认：{code:1,data:...} 与 {error:{code,message}}。"""
    d = jloads(txt)
    if st not in (200, 201):
        raise Fail("call", "调用失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if not isinstance(d, dict):
        raise Fail("call", "返回不是 JSON：%s" % (txt or "")[:200], EXIT_CALL)
    code = d.get("code")
    if code not in (1, 200, None):
        raise Fail("call", "上游拒绝（%s）：%s" % (url.rsplit("/", 1)[-1],
                                                 d.get("msg") or err_text(st, txt)), EXIT_CALL)
    data = d.get("data")
    return data if isinstance(data, dict) else d


def api_get(key, host, path, timeout=60):
    url = host + path
    return envelope(*http_json("GET", url, key, None, timeout=timeout), url=url)


def api_post(key, host, path, body, timeout=120):
    url = host + path
    return envelope(*http_json("POST", url, key, body, timeout=timeout), url=url)


# ───────────────────────── 任务与产物 ─────────────────────────
def get_task(key, host, tid):
    """查任务只走 GET /api/v1/tasks/<id>；价目表里这条 cost:0，应用层 /query 才收费。"""
    st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + urllib.parse.quote(tid),
                        key, timeout=60)
    d = jloads(txt) or {}
    if st == 200 and d.get("code") == 0:
        raise Fail("call", "查不到任务 %s：%s" % (tid, d.get("msg") or "任务不存在"), EXIT_CALL)
    if st not in (200, 201):
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    data = d.get("data")
    return data if isinstance(data, dict) else d


def wait_task(a, key, host, tid, label=""):
    deadline = time.time() + max(30, a.wait)
    seen = None
    while time.time() < deadline:
        d = get_task(key, host, tid)
        st = str(d.get("status") or "").lower()
        if st != seen:
            say("    %s状态：%s" % (label, st or "?"))
            seen = st
        if st in TERMINAL_OK or st in TERMINAL_BAD:
            return d
        time.sleep(max(2, a.every))
    raise Fail("call", "等了 %d 秒还没完成。任务没丢：`task --task-id %s` 接着取，"
                       "别重新提交（会再扣一次）。" % (a.wait, tid), EXIT_CALL)


def _walk(node, path, out, depth=0):
    if depth > 6:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            _walk(v, path + "." + str(k), out, depth + 1)
    elif isinstance(node, list):
        for i, v in enumerate(node[:8]):
            _walk(v, path + "[%d]" % i, out, depth + 1)
    elif isinstance(node, str) and node.startswith("http"):
        out.append((path, node))


def pick_asset(data, kind):
    """在任务返回里找成片 / 图片 / 音频地址。返回 (url, 字段路径)。"""
    exts = {"video": VIDEO_EXT, "image": IMAGE_EXT, "audio": AUDIO_EXT}[kind]
    rows = []
    _walk(data, "data", rows)
    for p, u in rows:
        if u.split("?")[0].lower().endswith(exts):
            return u, p
    for p, u in rows:
        if kind in p.lower():
            return u, p
    return None, None


def download(url, outdir, name, timeout=300):
    os.makedirs(outdir, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as x:
        raw = x.read()
    path = os.path.join(outdir, name)
    io.open(path, "wb").write(raw)
    return path


def save_b64(text, path):
    raw = base64.b64decode(text)
    if raw[:4] == b"\x89PNG":
        pass
    io.open(path, "wb").write(raw)
    return path


def fmt_pts(n):
    return "{:,}".format(int(round(float(n))))


def yuan(pts):
    return round(float(pts) / POINTS_PER_YUAN, 2)


def _w(s):
    """显示宽度：中日韩字符占 2 列，表格才对得齐。"""
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


# ───────────────────────── 算钱 ─────────────────────────
def auto_scenes(chars):
    """自动分镜：170 字一镜，最少 1 镜，最多 SCENE_CAP 镜。"""
    n = int(round(float(chars) / CHARS_PER_SCENE))
    return max(1, min(SCENE_CAP, n if n > 0 else 1))


def quote(chars, scenes, seconds, resolution, music=True, narr_chars=None):
    """一段一条的成本明细。返回 (总点数, [(名目, 点数, 口径)])。"""
    rate = VIDEO_RATES[resolution]
    if narr_chars is None:
        narr_chars = min(int(chars), int(scenes) * NARR_CHARS)
    items = [
        ("出图 %s" % APP_IMAGE, IMG_POINTS * scenes,
         "%d 镜 x %d 点/张" % (scenes, IMG_POINTS)),
        ("图生视频 %s %s" % (APP_VIDEO, resolution), rate * seconds * scenes,
         "%d 镜 x %d 秒 x %d 点/秒" % (scenes, seconds, rate)),
        ("旁白 %s" % APP_TTS, int(round(narr_chars * TTS_PER_CHAR)),
         "%d 字 x %.2f 点/字" % (narr_chars, TTS_PER_CHAR)),
    ]
    if music:
        items.append(("配乐 %s" % APP_MUSIC, MUSIC_FLOOR, "1 首，通配保底 %d 点" % MUSIC_FLOOR))
    return sum(p for _n, p, _b in items), items


def gate(a, cost, basis):
    """两道闸门：超预算退 5（一个请求都不发）；没 --yes 退 4（并告诉你要花多少）。"""
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %d 点（%.2f 元）超过 --budget %d 点：%s。"
                   "一个请求都没发。调大 --budget（单位：点，1 元 = 100 点）再试。"
                   % (cost, yuan(cost), a.budget, basis), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实扣费约 %d 点（%.2f 元）：%s。确认请加 --yes。"
                   % (cost, yuan(cost), basis), EXIT_CONFIRM)
    return cost


# ───────────────────────── 分镜（纯本地，0 点）─────────────────────────
def read_text(path):
    raw = io.open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except Exception:                                        # noqa: BLE001
            continue
    return raw.decode("utf-8", "replace")


def strip_markup(s):
    s = re.sub(r"```.*?```", " ", s, flags=re.S)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<[^>]{1,200}>", " ", s)
    s = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", s)
    s = re.sub(r"(?m)^\s*[-*+>]\s+", "", s)
    s = re.sub(r"[*_`~]+", "", s)
    s = s.replace("\u3000", " ").replace("\r", "\n")
    return s


def split_sentences(text):
    """按中文句读与换行切句；英文按句号 + 空格切。太短的碎片丢掉。"""
    raw = re.split(r"(?<=[。！？!?；;])|\n+|\s(?=[A-Z][a-z]{2,})", text)
    out = []
    for chunk in raw:
        chunk = (chunk or "").strip(" \t，,、：:。;;")
        chunk = re.sub(r"\s+", " ", chunk)
        if len(chunk) < 8:
            continue
        if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", chunk):
            continue
        out.append(chunk)
    return out


def trim_narration(s, limit):
    if len(s) <= limit:
        return s
    cut = s[:limit]
    for sep in ("，", "、", "；", "：", ",", " "):
        i = cut.rfind(sep)
        if i >= limit // 2:
            return cut[:i]
    return cut


def pick_sentences(sents, n):
    """均匀抽样 n 句，覆盖全文（首尾都要取到）。"""
    if not sents:
        return []
    n = max(1, min(int(n), len(sents)))
    if n == 1:
        return [sents[0]]
    idx, out = [], []
    for i in range(n):
        j = int(round(i * (len(sents) - 1) / float(n - 1)))
        if j not in idx:
            idx.append(j)
    for j in idx:
        out.append(sents[j])
    return out


def build_storyboard(text, scenes, seconds, ratio, style, narr_chars, title=None):
    clean = strip_markup(text or "")
    sents = split_sentences(clean)
    if not sents:
        raise Fail("usage", "文章里没切出可用句子。换 --article 或直接用 --text 传一段。",
                   EXIT_USAGE)
    picked = pick_sentences(sents, scenes)
    rows = []
    for i, sent in enumerate(picked, 1):
        narr = trim_narration(sent, narr_chars)
        visual = re.sub(r"[“”\"']", "", sent)
        rows.append({
            "i": i,
            "narration": narr,
            "imagePrompt": "%s，%s，高清写实摄影，%s 构图，光线自然" % (visual, style, ratio),
            "videoPrompt": "%s，镜头缓慢推近，画面自然流动" % visual,
            "seconds": int(seconds),
            "imagePath": None, "imageUrl": None,
            "videoPath": None, "videoUrl": None,
        })
    return {
        "ok": True,
        "title": title or (sents[0][:30] if sents else "未命名"),
        "chars": len(clean),
        "sentences": len(sents),
        "sceneCount": len(rows),
        "sceneSeconds": int(seconds),
        "totalSeconds": len(rows) * int(seconds),
        "ratio": ratio,
        "style": style,
        "narrationChars": sum(len(r["narration"]) for r in rows),
        "scenes": rows,
    }


def load_sb(path):
    if not os.path.isfile(path):
        raise Fail("usage", "找不到分镜文件 %s。先跑 `plan --article 你的文章.md`。" % path,
                   EXIT_USAGE)
    try:
        sb = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:                                       # noqa: BLE001
        raise Fail("usage", "分镜文件读不了（%s）：%s" % (type(e).__name__, e), EXIT_USAGE)
    if not isinstance(sb, dict) or not isinstance(sb.get("scenes"), list):
        raise Fail("usage", "分镜文件结构不对（缺 scenes）：%s" % path, EXIT_USAGE)
    return sb


def save_sb(path, sb):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(sb, ensure_ascii=False, indent=1))
    return path


def sb_outdir(a, sb_path):
    return a.out or os.path.dirname(os.path.abspath(sb_path)) or "."


# ───────────────────────── 上传（免费）─────────────────────────
def upload_file(key, host, path, timeout=600):
    size = os.path.getsize(path)
    say("    上传 %s（%d 字节，0 点）…" % (os.path.basename(path), size))
    st, txt = http_multipart(host + API_PREFIX + "/upload", key, {},
                             [("file", path)], timeout=timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    return got


def as_url(key, host, value, timeout=600):
    """本地文件先免费上传拿地址；已经是 http(s) 就直接用。"""
    if not value:
        raise Fail("usage", "缺一个图片地址或本地文件路径", EXIT_USAGE)
    if os.path.isfile(value):
        return upload_file(key, host, value, timeout=timeout)
    if not re.match(r"^https?://", value, re.I):
        raise Fail("usage", "%s 既不是本机文件，也不是 http(s) 地址" % value, EXIT_USAGE)
    return value


# ───────────────────────── 出图 ─────────────────────────
def _gpt_image(a, key, host, scene):
    """gpt-image-2.6：同步出图，返回 b64_json；按实际张数 6 点/张。"""
    body = {
        "model": APP_IMAGE,
        "prompt": scene["imagePrompt"],
        "n": 1,
        "size": getattr(a, "size", "1536x1024"),
        "output_format": "png",
        "response_format": "b64_json",
    }
    url = host + API_PREFIX + "/images/generations"
    st, txt = http_json("POST", url, key, body, timeout=max(180, a.timeout))
    d = jloads(txt) or {}
    if st != 200:
        raise Fail("call", "出图失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    items = d.get("data") or []
    if not items:
        raise Fail("call", "出图返回里没有 data：%s" % (txt or "")[:300], EXIT_CALL)
    item = items[0]
    path = os.path.join(a.out, "scene-%02d.png" % scene["i"])
    if item.get("b64_json"):
        save_b64(item["b64_json"], path)
        src = "b64_json"
    elif item.get("url"):
        download(item["url"], a.out, "scene-%02d.png" % scene["i"])
        src = "url"
    else:
        raise Fail("call", "出图返回既没有 b64_json 也没有 url：%s"
                   % json.dumps(item, ensure_ascii=False)[:300], EXIT_CALL)
    return path, IMG_POINTS * len(items), src


def _nano_image(a, key, host, scene, ref_url):
    """nano_banana：参考图改图，异步任务，72 点/次。"""
    body = {
        "action": "edit",
        "model": getattr(a, "ref_model", "nano-banana"),
        "prompt": scene["imagePrompt"],
        "image_urls": [ref_url],
        "resolution": "1K",
        "aspect_ratio": getattr(a, "ratio", "16:9"),
    }
    data = api_post(key, host, API_PREFIX + "/apps/" + APP_NANO + "/submit", body,
                    timeout=a.timeout)
    tid = data.get("task_id") or data.get("taskId") or data.get("id")
    if not tid:
        raise Fail("call", "改图没拿到 task_id：%s"
                   % json.dumps(data, ensure_ascii=False)[:300], EXIT_CALL)
    say("    改图任务 %s" % tid)
    t = wait_task(a, key, host, tid, "改图")
    if str(t.get("status") or "").lower() in TERMINAL_BAD:
        raise Fail("call", "改图任务失败：%s" % (t.get("message") or t.get("fail_reason")),
                   EXIT_CALL)
    url, _where = pick_asset(t, "image")
    if not url:
        raise Fail("call", "改图完成但没解析到图片地址，用 `task --task-id %s` 看看" % tid,
                   EXIT_CALL)
    path = download(url, a.out, "scene-%02d.png" % scene["i"])
    return path, NANO_POINTS, "nano_banana"


def do_images(a, key, host, sb, sb_path):
    force = bool(getattr(a, "force", False))
    ref = getattr(a, "ref", None)
    todo = [s for s in sb["scenes"]
            if force or not s.get("imagePath") or not os.path.isfile(s.get("imagePath") or "")]
    unit = NANO_POINTS if ref else IMG_POINTS
    cost = unit * len(todo)
    gate(a, cost, "%s %d 点/张 x %d 镜" % ("nano_banana" if ref else APP_IMAGE,
                                          unit, len(todo)))
    if not todo:
        return {"ok": True, "mode": "image", "skipped": True, "scenes": len(sb["scenes"]),
                "estimatedPoints": 0, "files": []}

    ref_url = None
    if ref:
        ref_url = "<参考图地址（先免费 upload）>" if a.dry_run else as_url(
            key, host, ref, timeout=a.timeout)

    if a.dry_run:
        reqs = []
        for s in todo:
            if ref:
                reqs.append({"scene": s["i"],
                             "url": host + API_PREFIX + "/apps/" + APP_NANO + "/submit",
                             "body": {"action": "edit",
                                      "model": getattr(a, "ref_model", "nano-banana"),
                                      "prompt": s["imagePrompt"],
                                      "image_urls": [ref_url],
                                      "resolution": "1K",
                                      "aspect_ratio": getattr(a, "ratio", "16:9")}})
            else:
                reqs.append({"scene": s["i"],
                             "url": host + API_PREFIX + "/images/generations",
                             "body": {"model": APP_IMAGE, "prompt": s["imagePrompt"],
                                      "n": 1, "size": getattr(a, "size", "1536x1024"),
                                      "output_format": "png",
                                      "response_format": "b64_json"}})
        return {"ok": True, "dryRun": True, "mode": "image", "requests": reqs,
                "scenes": len(todo), "estimatedPoints": cost, "yuan": yuan(cost)}

    billed, files = 0, []
    for s in todo:
        say("  出图 %d/%d：%s" % (s["i"], len(sb["scenes"]), s["narration"][:24]))
        t0 = time.time()
        if ref:
            path, pts, src = _nano_image(a, key, host, s, ref_url)
        else:
            path, pts, src = _gpt_image(a, key, host, s)
        s["imagePath"] = path
        s["imageSource"] = src
        billed += pts
        files.append(path)
        save_sb(sb_path, sb)
        say("    -> %s（%.1fs，%d 点）" % (path, time.time() - t0, pts))
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "image",
                    "scene": s["i"], "ok": True, "file": path, "points": pts,
                    "source": src})
    return {"ok": True, "mode": "image", "scenes": len(todo), "billedPoints": billed,
            "estimatedPoints": cost, "files": files, "storyboard": sb_path}


# ───────────────────────── 图生视频 ─────────────────────────
def _video_body(scene, image_url, resolution, ratio):
    content = [{"type": "text", "text": scene["videoPrompt"]}]
    if image_url:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})
    return {"model": "full-video", "content": content,
            "duration": int(scene.get("seconds") or 5),
            "resolution": resolution, "ratio": ratio,
            "aigc_watermark": False}


def do_render(a, key, host, sb, sb_path):
    scenes = sb["scenes"]
    missing = [s["i"] for s in scenes if not (s.get("imagePath")
                                              and os.path.isfile(s["imagePath"]))]
    if missing and not a.dry_run:
        raise Fail("usage", "还有 %d 镜没出图（%s）。先跑 `image --yes`，再接 render。"
                   % (len(missing), ",".join(str(x) for x in missing[:8])), EXIT_USAGE)
    todo = [s for s in scenes if getattr(a, "force", False) or not s.get("videoPath")]
    if getattr(a, "seconds", None):
        for s in todo:
            s["seconds"] = max(DUR_MIN, min(DUR_MAX, int(a.seconds)))
    rate = VIDEO_RATES[a.resolution]
    secs_total = sum(int(s.get("seconds") or 5) for s in todo)
    cost = rate * secs_total
    gate(a, cost, "%d 点/秒 x %d 秒合计（%d 镜，%s）"
         % (rate, secs_total, len(todo), a.resolution))
    outdir = sb_outdir(a, sb_path)
    if not todo:
        return {"ok": True, "mode": "render", "skipped": True, "clips": [], "cost": 0}

    if a.dry_run:
        reqs = []
        for s in todo:
            img = s.get("imageUrl") or "<先免费 upload 的 %s>" % os.path.basename(
                s.get("imagePath") or "scene.png")
            reqs.append({"scene": s["i"],
                         "url": host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit",
                         "body": _video_body(s, img, a.resolution, a.ratio)})
        return {"ok": True, "dryRun": True, "mode": "render", "requests": reqs,
                "clips": len(todo), "estimatedPoints": cost, "yuan": yuan(cost)}

    clips, task_ids = [], []
    for s in todo:
        if not s.get("imageUrl"):
            s["imageUrl"] = upload_file(key, host, s["imagePath"], timeout=a.timeout)
            save_sb(sb_path, sb)
        body = _video_body(s, s["imageUrl"], a.resolution, a.ratio)
        say("  视频 %d/%d：%d 秒 %s" % (s["i"], len(scenes), s["seconds"], a.resolution))
        data = api_post(key, host, API_PREFIX + "/apps/" + APP_VIDEO + "/submit", body,
                        timeout=a.timeout)
        tid = data.get("task_id") or data.get("taskId") or data.get("id")
        if not tid:
            raise Fail("call", "视频没拿到 task_id：%s"
                       % json.dumps(data, ensure_ascii=False)[:300], EXIT_CALL)
        task_ids.append(tid)
        say("    task_id=%s" % tid)
        t = wait_task(a, key, host, tid, "视频")
        if str(t.get("status") or "").lower() in TERMINAL_BAD:
            raise Fail("call", "第 %d 镜视频失败：%s"
                       % (s["i"], t.get("message") or t.get("fail_reason")), EXIT_CALL)
        url, _where = pick_asset(t, "video")
        if not url:
            raise Fail("call", "第 %d 镜完成但没解析到视频地址，用 `task --task-id %s` 看看"
                       % (s["i"], tid), EXIT_CALL)
        path = download(url, outdir, "clip-%02d.mp4" % s["i"])
        s["videoPath"] = path
        s["videoUrl"] = url
        s["taskId"] = tid
        save_sb(sb_path, sb)
        clips.append(path)
        say("    -> %s" % path)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "render",
                    "scene": s["i"], "ok": True, "taskId": tid, "points": rate * s["seconds"]})
    concat = write_concat(outdir, [s.get("videoPath") for s in scenes])
    return {"ok": True, "mode": "render", "clips": clips, "taskIds": task_ids,
            "estimatedPoints": cost, "yuan": yuan(cost), "concat": concat,
            "resolution": a.resolution, "seconds": a.seconds}


def _write_file_list(path, names):
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        "\n".join("file '%s'" % n for n in names) + "\n")
    return path


def write_concat(outdir, clips):
    """按分镜顺序写 ffmpeg concat 清单；只认真实存在的片段。"""
    rows = [os.path.basename(c) for c in (clips or []) if c and os.path.isfile(c)]
    if not rows:
        return None
    return _write_file_list(os.path.join(outdir, "concat.txt"), rows)


def write_audio_concat(outdir, files):
    """旁白被切成多段时，给一条把它们拼成单轨的清单。"""
    rows = [os.path.basename(c) for c in (files or []) if c and os.path.isfile(c)]
    if len(rows) < 2:
        return None
    return _write_file_list(os.path.join(outdir, "narration-concat.txt"), rows)


# ───────────────────────── 旁白 ─────────────────────────
def narration_chunks(scenes, limit=TTS_CHUNK):
    """把每镜旁白拼成不超过 limit 字的块；句间补一个句号，念起来才断得开。"""
    chunks, cur = [], []
    for s in scenes:
        text = (s.get("narration") or "").strip()
        if not text:
            continue
        if text[-1] not in "。！？!?；;，,":
            text += "。"
        if cur and sum(len(x) for x in cur) + len(text) > limit:
            chunks.append("".join(cur))
            cur = []
        while len(text) > limit:
            chunks.append(text[:limit])
            text = text[limit:]
        if text:
            cur.append(text)
    if cur:
        chunks.append("".join(cur))
    return chunks


def do_voice(a, key, host, sb, sb_path):
    chunks = narration_chunks(sb["scenes"])
    total_chars = sum(len(c) for c in chunks)
    cost = int(round(total_chars * TTS_PER_CHAR))
    gate(a, cost, "旁白 %d 字 x %.2f 点/字（上游真实点数 x 3）"
         % (total_chars, TTS_PER_CHAR))
    if a.dry_run:
        reqs = [{"chunk": i,
                 "url": host + API_PREFIX + "/apps/" + APP_TTS + "/tts",
                 "body": {"text": c, "model": a.tts_model, "format": a.tts_format}}
                for i, c in enumerate(chunks, 1)]
        return {"ok": True, "dryRun": True, "mode": "voice", "requests": reqs,
                "chunks": len(chunks), "chars": total_chars,
                "estimatedPoints": cost, "yuan": yuan(cost)}

    outdir = sb_outdir(a, sb_path)
    files = []
    for i, chunk in enumerate(chunks, 1):
        name = "narration.mp3" if len(chunks) == 1 else "narration-%02d.mp3" % i
        say("  旁白 %d/%d：%d 字" % (i, len(chunks), len(chunk)))
        data = api_post(key, host, API_PREFIX + "/apps/" + APP_TTS + "/tts",
                        {"text": chunk, "model": a.tts_model, "format": a.tts_format},
                        timeout=a.timeout)
        url = None
        for k in ("audio_url", "audioUrl", "url"):
            if isinstance(data.get(k), str) and data[k].startswith("http"):
                url = data[k]
                break
        if not url:
            url, _w = pick_asset(data, "audio")
        if not url:
            raise Fail("call", "旁白返回里没有音频地址：%s"
                       % json.dumps(data, ensure_ascii=False)[:300], EXIT_CALL)
        path = download(url, outdir, name)
        files.append(path)
        say("    -> %s" % path)
    sb["narrationFiles"] = files
    save_sb(sb_path, sb)
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "voice", "ok": True,
                "chars": total_chars, "files": files, "points": cost})
    return {"ok": True, "mode": "voice", "chunks": len(chunks), "chars": total_chars,
            "files": files, "estimatedPoints": cost, "yuan": yuan(cost)}


# ───────────────────────── 配乐 ─────────────────────────
def do_music(a, key, host, sb, sb_path):
    cost = MUSIC_FLOOR
    gate(a, cost, "配乐 1 首，通配保底 %d 点（下限，按上游点数 x 2 结算）" % MUSIC_FLOOR)
    prompt = a.music_prompt or "轻音乐，舒缓，钢琴与弦乐，适合纪录片旁白垫底"
    body = {"model": a.music_model, "custom_mode": False,
            "instrumental": True, "prompt": prompt}
    url = host + API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate"
    if a.dry_run:
        return {"ok": True, "dryRun": True, "mode": "music",
                "requests": [{"url": url, "body": body}],
                "estimatedPoints": cost, "yuan": yuan(cost)}
    say("  配乐：%s" % prompt[:40])
    data = api_post(key, host, API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate",
                    body, timeout=a.timeout)
    tid = data.get("task_id") or data.get("taskId") or data.get("id")
    if tid:
        say("    task_id=%s" % tid)
        t = wait_task(a, key, host, tid, "配乐")
        if str(t.get("status") or "").lower() in TERMINAL_BAD:
            raise Fail("call", "配乐任务失败：%s"
                       % (t.get("message") or t.get("fail_reason")), EXIT_CALL)
        audio, _where = pick_asset(t, "audio")
    else:
        audio = None
        for k in ("audio_url", "audioUrl", "url"):
            if isinstance(data.get(k), str) and data[k].startswith("http"):
                audio = data[k]
                break
    if not audio:
        raise Fail("call", "配乐完成但没解析到音频地址", EXIT_CALL)
    path = download(audio, sb_outdir(a, sb_path), "bgm.mp3")
    sb["musicFile"] = path
    save_sb(sb_path, sb)
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "music", "ok": True,
                "file": path, "pointsFloor": cost})
    say("    -> %s" % path)
    return {"ok": True, "mode": "music", "file": path, "audioUrl": audio,
            "estimatedPoints": cost, "yuan": yuan(cost), "isLowerBound": True}


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d = jloads(txt) or {}
    listing = d.get("data") if isinstance(d.get("data"), list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    st2, txt2 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt2) or {}).get("pricing") or {}

    rate = (pricing.get(API_PREFIX + "/apps/full_video/submit") or {})
    rows = [
        {"step": "分镜", "app": "本地", "endpoint": "纯本地，不发请求",
         "price": "0 点", "note": "按段落与句读切镜，跑一万次也不花钱"},
        {"step": "出图", "app": APP_IMAGE,
         "endpoint": "POST /api/v1/images/generations",
         "price": "%d 点/张" % IMG_POINTS,
         "note": "同步出图，尺寸与张数档都不改单价"},
        {"step": "改图", "app": APP_NANO,
         "endpoint": "POST /api/v1/apps/%s/submit" % APP_NANO,
         "price": "%d 点/次" % NANO_POINTS, "note": "拿参考图改画面风格 / 动作"},
        {"step": "动起来", "app": APP_VIDEO,
         "endpoint": "POST /api/v1/apps/%s/submit" % APP_VIDEO,
         "price": " / ".join("%s %d" % (r, VIDEO_RATES[r]) for r in RESOLUTIONS[:3]) + " 点/秒",
         "note": "图生视频，4~15 秒一段，按秒 x 分辨率"},
        {"step": "旁白", "app": APP_TTS,
         "endpoint": "POST /api/v1/apps/%s/tts" % APP_TTS,
         "price": "约 %.2f 点/字" % TTS_PER_CHAR, "note": "上游真实点数 x 3，实测 33 字 5.94 点"},
        {"step": "配乐", "app": APP_MUSIC,
         "endpoint": "POST /api/v1/apps/%s/music_generate" % APP_MUSIC,
         "price": "%d 点起/首" % MUSIC_FLOOR, "note": "落通配：上游点数 x 2，单笔保底 50 点"},
    ]
    for r in rows:
        if r["app"] in online:
            r["online"] = True
            r["apis"] = len(online[r["app"]].get("apis") or [])
        else:
            r["online"] = r["app"] == "本地"
            r["apis"] = 0
    checks = {"apps": len(listing),
              "musicApis": len(online.get(APP_MUSIC, {}).get("apis") or []),
              "videoRates": rate.get("resolutionRates") or VIDEO_RATES,
              "nanoPoints": (pricing.get(API_PREFIX + "/apps/nano_banana/submit")
                             or {}).get("cost"),
              "pricingRead": st2 == 200}
    out = {"ok": True, "rows": rows, "live": checks,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 图文转视频 —— 五段链路（1 元 = 100 点）")
    print()
    print("  %s %s %s %s" % (pad("工序", 8), pad("用谁", 20), pad("端点", 54), "单价"))
    print("  " + "-" * 104)
    for r in rows:
        print("  %s %s %s %s" % (pad(r["step"], 8), pad(r["app"], 20),
                                 pad(r["endpoint"], 54), r["price"]))
        print("        %s" % r["note"])
    print()
    print("  本站应用目录 %d 个；media_services_33 在架 %d 个接口（本包只取 music_generate）。"
          % (checks["apps"], checks["musicApis"]))
    live = checks["videoRates"]
    print("  full_video 现查按秒价：%s" % " · ".join(
        "%s %s" % (r, live.get(r)) for r in RESOLUTIONS))
    print("  查询进度统一走 GET /api/v1/tasks/<id>（cost:0），应用层 /query 每次都是钱。")
    return 0


def cmd_cost(a, key, host):
    chars = max(1, a.chars)
    scenes = a.scenes if a.scenes and a.scenes > 0 else auto_scenes(chars)
    scenes = max(1, min(scenes, SCENE_CAP))
    seconds = max(DUR_MIN, min(DUR_MAX, a.seconds))
    res = a.resolution
    music = not a.no_music

    narr = min(chars, scenes * NARR_CHARS)
    total, items = quote(chars, scenes, seconds, res, music=music, narr_chars=narr)
    full_scenes = max(1, min(SCENE_CAP * 2, int(round(chars / float(NARR_CHARS)) + 0.5)))
    full_total, full_items = quote(chars, full_scenes, seconds, res, music=music,
                                   narr_chars=chars)

    matrix = []
    for r in RESOLUTIONS:
        pts, _it = quote(chars, scenes, seconds, r, music=music, narr_chars=narr)
        matrix.append({"resolution": r, "points": pts, "yuan": yuan(pts),
                       "rate": VIDEO_RATES[r]})

    out = {"ok": True, "chars": chars, "scenes": scenes, "sceneSeconds": seconds,
           "totalSeconds": scenes * seconds, "resolution": res, "music": music,
           "narrationChars": narr,
           "items": [{"name": n, "points": p, "basis": b} for n, p, b in items],
           "total": total, "yuan": yuan(total),
           "fullText": {"scenes": full_scenes, "seconds": full_scenes * seconds,
                        "narrationChars": chars, "total": full_total,
                        "yuan": yuan(full_total),
                        "items": [{"name": n, "points": p, "basis": b}
                                  for n, p, b in full_items]},
           "matrix": matrix, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "unitPrice": {"image": IMG_POINTS, "nano": NANO_POINTS,
                         "video": VIDEO_RATES, "ttsPerChar": TTS_PER_CHAR,
                         "musicFloor": MUSIC_FLOOR},
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-07 实测）",
               "gpt-image-2.6 按张计费，与尺寸、质量、输出格式都无关",
               "full_video 按秒 x 分辨率：480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80",
               "voice_tts 按上游真实点数 x 3；实测 33 字 5.94 点，按 0.18 点/字估",
               "配乐落在通配规则：上游点数 x 2，单笔保底 50 点，所以是下限",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("一篇 %d 字文章多少钱（1 元 = 100 点）" % chars)
    print()
    print("  默认 %d 镜 x %d 秒 = %d 秒成片，旁白 %d 字，%s"
          % (scenes, seconds, scenes * seconds, narr,
             "带配乐" if music else "不配乐"))
    print("  " + "-" * 68)
    for n, p, b in items:
        print("  %s %s 点   %s" % (pad(n, 30), pad(fmt_pts(p), 8, left=False), b))
    print("  " + "-" * 68)
    print("  %s %s 点   = %.2f 元" % (pad("合计", 30), pad(fmt_pts(total), 8, left=False),
                                    yuan(total)))
    print()
    print("  两档对照")
    print("    精华版 %3d 镜 · %4d 秒 · 旁白 %4d 字   %8s 点 = %7.2f 元"
          % (scenes, scenes * seconds, narr, fmt_pts(total), yuan(total)))
    print("    全文版 %3d 镜 · %4d 秒 · 旁白 %4d 字   %8s 点 = %7.2f 元"
          % (full_scenes, full_scenes * seconds, chars, fmt_pts(full_total),
             yuan(full_total)))
    print()
    print("  同一篇按分辨率（默认 %d 镜 x %d 秒）" % (scenes, seconds))
    print("    %s %s %s" % (pad("分辨率", 10), pad("点数", 12, left=False), "折合"))
    for row in matrix:
        print("    %s %s %s" % (pad(row["resolution"], 10),
                                pad(fmt_pts(row["points"]), 12, left=False),
                                "%.2f 元" % row["yuan"]))
    print()
    print("  每加 1 镜 = %d 点（%.2f 元）；换分辨率，改的是整条成片每一秒的价。"
          % (IMG_POINTS + VIDEO_RATES[res] * seconds,
             yuan(IMG_POINTS + VIDEO_RATES[res] * seconds)))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("Key + 余额接口可达", st == 200 and "available_points" in d,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, fmt_pts(d.get("available_points") or 0),
                       fmt_pts(d.get("frozen") or 0))))

    st2, txt2 = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d2 = jloads(txt2) or {}
    listing = d2.get("data") if isinstance(d2.get("data"), list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    need = [APP_NANO, APP_VIDEO, APP_TTS, APP_MUSIC]
    miss = [c for c in need if c not in online]
    checks.append(("4 个应用在架（nano / video / tts / music）",
                   bool(listing) and not miss,
                   "目录 %d 个应用%s" % (len(listing),
                                        "，缺 " + ",".join(miss) if miss else "")))
    music_apis = len(online.get(APP_MUSIC, {}).get("apis") or [])
    checks.append(("media_services_33 的 29 个接口齐全",
                   music_apis >= 29,
                   "在架 %d 个接口（配乐取 music_generate）" % music_apis))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt3) or {}).get("pricing") or {}
    vrule = pricing.get(API_PREFIX + "/apps/full_video/submit") or {}
    live = vrule.get("resolutionRates") or {}
    drift = ["%s 本地 %d / 线上 %s" % (r, p, live.get(r))
             for r, p in VIDEO_RATES.items() if int(live.get(r) or -1) != p]
    checks.append(("full_video 5 档按秒价与线上一致", st3 == 200 and bool(live) and not drift,
                   "HTTP %s · %s" % (st3, "5 档全一致" if not drift else " / ".join(drift)[:110])))

    nano = (pricing.get(API_PREFIX + "/apps/nano_banana/submit") or {}).get("cost")
    wild = pricing.get("*") or {}
    up = pricing.get(API_PREFIX + "/upload") or {}
    ok_price = (int(nano or 0) == NANO_POINTS
                and int(wild.get("minPoints") or 0) == MUSIC_FLOOR
                and int(up.get("cost") if up.get("cost") is not None else 999) == 0)
    checks.append(("专属价与免费路径都在", ok_price,
                   "nano %s 点 · 通配保底 %s 点 · upload %s 点"
                   % (nano, wild.get("minPoints"), up.get("cost"))))

    # 出图端点：带 model 的空 prompt，文档规定 422，停在扣费之前
    st4, txt4 = http_json("POST", host + API_PREFIX + "/images/generations", key,
                          {"model": APP_IMAGE, "prompt": ""}, timeout=60)
    d4 = jloads(txt4) or {}
    msg4 = ((d4.get("error") or {}) if isinstance(d4.get("error"), dict) else {}).get("message") or ""
    checks.append(("出图端点可用（422 即正确，零扣费）",
                   st4 == 422 and "prompt" in msg4.lower(),
                   "HTTP %s %s" % (st4, (msg4 or err_text(st4, txt4))[:52])))

    st5, txt5 = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-doctor-probe",
                          key, timeout=40)
    d5 = jloads(txt5) or {}
    checks.append(("任务查询 GET /tasks/<id> 可用（假 id 返回任务不存在）",
                   st5 == 200 and d5.get("code") == 0,
                   "HTTP %s %s" % (st5, (d5.get("msg") or "")[:40])))

    st6, txt6 = http_multipart(host + API_PREFIX + "/upload", key, {}, [], timeout=60)
    d6 = jloads(txt6) or {}
    checks.append(("上传口 POST /upload 可用（缺 file 时提示补字段）",
                   st6 == 200 and d6.get("code") == 0,
                   "HTTP %s %s" % (st6, (d6.get("msg") or "")[:40])))

    last = None
    st7, txt7 = http_json("GET", host + "/user/balance/logs?limit=3", key, timeout=40)
    d7 = jloads(txt7) or {}
    logs = d7.get("logs") or []
    if logs:
        row = logs[0]
        last = {"at": row.get("at"), "type": row.get("type"),
                "points": row.get("points"), "reference": row.get("reference"),
                "balanceAfter": row.get("balanceAfter")}

    out = {"ok": all(c[1] for c in checks), "apps": need, "musicApis": music_apis,
           "requests": 7, "estimatedPoints": 0, "lastLedger": last,
           "endpoints": {"image": host + API_PREFIX + "/images/generations",
                         "video": host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit",
                         "tts": host + API_PREFIX + "/apps/" + APP_TTS + "/tts",
                         "music": host + API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate",
                         "task": host + API_PREFIX + "/tasks/<task_id>"},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（5 个只读 GET + 1 个空 prompt 422 + 1 个缺 file 上传，共 7 个请求，全部停在扣费之前）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 52), dt))
    print()
    if last:
        print("  最近一笔流水：%s  %s  %s 点  余额 %s"
              % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime((last["at"] or 0) / 1000.0)),
                 last.get("type") or "-", fmt_pts(last.get("points") or 0),
                 fmt_pts(last.get("balanceAfter") or 0)))
        print("  本次自检 0 点、0 冻结：7 个请求里没有一条会建任务。")
    print()
    print("  端点：POST /images/generations（出图）· /apps/full_video/submit（出片）")
    print("        POST /apps/voice_tts/tts（旁白）· /apps/media_services_33/music_generate（配乐）")
    print("  查询：GET /api/v1/tasks/<task_id>（cost:0；应用层 /query 每次都是钱）")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── plan / image / render / voice / music ────────
def cmd_plan(a, key, host):
    if a.article:
        if not os.path.isfile(a.article):
            raise Fail("usage", "找不到文章：%s" % a.article, EXIT_USAGE)
        text = read_text(a.article)
    elif a.text:
        text = a.text
    else:
        raise Fail("usage", "给 --article 文章路径，或直接 --text 一段文案", EXIT_USAGE)

    chars = len(strip_markup(text))
    scenes = a.scenes if a.scenes and a.scenes > 0 else auto_scenes(chars)
    scenes = max(1, min(scenes, SCENE_CAP))
    seconds = max(DUR_MIN, min(DUR_MAX, a.seconds))
    sb = build_storyboard(text, scenes, seconds, a.ratio, a.style, a.narration_chars,
                          title=a.title)
    sb_path = a.storyboard or os.path.join(a.out, "storyboard.json")
    save_sb(sb_path, sb)
    narr_chars = sb["narrationChars"]
    total, items = quote(chars, sb["sceneCount"], seconds, a.resolution,
                         music=not a.no_music, narr_chars=narr_chars)
    txt_path = os.path.join(os.path.dirname(os.path.abspath(sb_path)), "narration.txt")
    io.open(txt_path, "w", encoding="utf-8", newline="\n").write(
        "\n".join("%02d %s" % (s["i"], s["narration"]) for s in sb["scenes"]) + "\n")
    out = {"ok": True, "mode": "plan", "storyboard": sb_path, "narration": txt_path,
           "chars": sb["chars"], "sceneCount": sb["sceneCount"],
           "totalSeconds": sb["totalSeconds"], "narrationChars": narr_chars,
           "estimatedPoints": total, "yuan": yuan(total),
           "items": [{"name": n, "points": p, "basis": b} for n, p, b in items],
           "scenes": sb["scenes"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("分镜完成（0 点，纯本地）：%d 字 → %d 镜 × %d 秒 = %d 秒"
          % (sb["chars"], sb["sceneCount"], seconds, sb["totalSeconds"]))
    print()
    print("  %s %s %s" % (pad("#", 3), pad("旁白", 34), "画面提示词（前 40 字）"))
    print("  " + "-" * 80)
    for s in sb["scenes"]:
        print("  %s %s %s" % (pad(s["i"], 3), pad(s["narration"][:32], 34),
                              s["imagePrompt"][:40]))
    print()
    print("  已写：%s" % sb_path)
    print("  已写：%s" % txt_path)
    print("  预估：%d 点 = %.2f 元（下一步 `image --yes`）" % (total, yuan(total)))
    return 0


def cmd_image(a, key, host):
    sb_path = a.storyboard
    sb = load_sb(sb_path)
    a.out = sb_outdir(a, sb_path)
    res = do_images(a, key, host, sb, sb_path)
    out = dict(res)
    out["storyboard"] = sb_path
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    if res.get("dryRun"):
        print("干跑（不出图、不扣费，共 %d 个请求）" % len(res["requests"]))
        for r in res["requests"]:
            print("  #%d POST %s" % (r["scene"], r["url"]))
            print("     %s" % json.dumps(r["body"], ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (res["estimatedPoints"], res["yuan"]))
        return 0
    if res.get("skipped"):
        print("这一篇的 %d 镜都已经有图了，没有新请求。要重出加 --force。" % res["scenes"])
        return 0
    print("出图完成：%d 镜，实扣 %d 点（%.2f 元）"
          % (res["scenes"], res["billedPoints"], yuan(res["billedPoints"])))
    for p in res["files"]:
        print("  %s（%d 字节）" % (p, os.path.getsize(p)))
    print("  分镜已更新：%s" % sb_path)
    secs = sb["scenes"][0]["seconds"] if sb.get("scenes") else 5
    print("  下一步：render --resolution 480P --seconds %d --yes" % secs)
    return 0


def cmd_render(a, key, host):
    sb_path = a.storyboard
    sb = load_sb(sb_path)
    a.out = sb_outdir(a, sb_path)
    res = do_render(a, key, host, sb, sb_path)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if res.get("dryRun"):
        print("干跑（不提交、不扣费，共 %d 个请求）" % len(res["requests"]))
        for r in res["requests"]:
            print("  #%d POST %s" % (r["scene"], r["url"]))
            print("     %s" % json.dumps(r["body"], ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (res["estimatedPoints"], res["yuan"]))
        return 0
    if res.get("skipped"):
        print("每一镜都已有视频，没有新请求。要重出加 --force。")
        return 0
    print("视频完成：%d 段（%.2f 元，%s）" % (len(res["clips"]), res["yuan"],
                                            res["resolution"]))
    for p in res["clips"]:
        print("  %s（%d 字节）" % (p, os.path.getsize(p)))
    if res.get("concat"):
        print("  拼接清单：%s" % res["concat"])
    print()
    print("  下一步：voice --yes（旁白），然后按下面这条合成：")
    print("    %s" % ffmpeg_cmd(res["concat"], None, None))
    return 0


def ffmpeg_cmd(concat, narration, bgm):
    base = "ffmpeg -f concat -safe 0 -i %s" % (os.path.basename(concat) if concat
                                               else "concat.txt")
    if narration and bgm:
        return (base + " -i %s -i %s -filter_complex \"[1:a][2:a]amix=inputs=2:"
                "duration=first[a]\" -map 0:v -map \"[a]\" -c:v copy -c:a aac -shortest "
                "film.mp4" % (os.path.basename(narration), os.path.basename(bgm)))
    if narration:
        return (base + " -i %s -c:v copy -c:a aac -shortest film.mp4"
                % os.path.basename(narration))
    return base + " -c copy film.mp4"


def cmd_voice(a, key, host):
    sb_path = a.storyboard
    sb = load_sb(sb_path)
    a.out = sb_outdir(a, sb_path)
    res = do_voice(a, key, host, sb, sb_path)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if res.get("dryRun"):
        print("干跑（不配音、不扣费，共 %d 个请求）" % len(res["requests"]))
        for r in res["requests"]:
            print("  #%d POST %s" % (r["chunk"], r["url"]))
            print("     %s" % json.dumps(r["body"], ensure_ascii=False)[:400])
        print("  预估：%d 点（%.2f 元）" % (res["estimatedPoints"], res["yuan"]))
        return 0
    print("旁白完成：%d 块 / %d 字，约 %d 点（%.2f 元）"
          % (res["chunks"], res["chars"], res["estimatedPoints"], yuan(res["estimatedPoints"])))
    for p in res["files"]:
        print("  %s（%d 字节）" % (p, os.path.getsize(p)))
    return 0


def cmd_music(a, key, host):
    sb_path = a.storyboard
    sb = load_sb(sb_path)
    a.out = sb_outdir(a, sb_path)
    res = do_music(a, key, host, sb, sb_path)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if res.get("dryRun"):
        print("干跑（不生成、不扣费）")
        for r in res["requests"]:
            print("  POST %s" % r["url"])
            print("     %s" % json.dumps(r["body"], ensure_ascii=False))
        print("  下限：%d 点（%.2f 元，按上游点数 x 2 结算）"
              % (res["estimatedPoints"], res["yuan"]))
        return 0
    print("配乐完成：%s（%d 字节）" % (res["file"], os.path.getsize(res["file"])))
    print("  下限 %d 点，实际按上游点数 x 2 结算（保底 50 点）" % res["estimatedPoints"])
    return 0


# ───────────────────────── 一键全链路 ─────────────────────────
def cmd_make(a, key, host):
    if not a.article:
        raise Fail("usage", "必须给 --article（一篇 .md / .txt 文章）", EXIT_USAGE)
    if not os.path.isfile(a.article):
        raise Fail("usage", "找不到文章：%s" % a.article, EXIT_USAGE)
    text = read_text(a.article)
    chars = len(strip_markup(text))
    scenes = a.scenes if a.scenes and a.scenes > 0 else auto_scenes(chars)
    scenes = max(1, min(scenes, SCENE_CAP))
    seconds = max(DUR_MIN, min(DUR_MAX, a.seconds))
    sb = build_storyboard(text, scenes, seconds, a.ratio, a.style, a.narration_chars,
                          title=a.title)
    sb_path = a.storyboard or os.path.join(a.out, "storyboard.json")
    a.out = os.path.dirname(os.path.abspath(sb_path)) or "."

    music = not a.no_music
    narr = sb["narrationChars"]
    total, items = quote(chars, sb["sceneCount"], seconds, a.resolution,
                         music=music, narr_chars=narr)
    basis = " + ".join("%s %s 点" % (n, fmt_pts(p)) for n, p, _b in items if p)
    gate(a, total, basis)

    img_url = host + API_PREFIX + "/images/generations"
    vid_url = host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit"
    tts_url = host + API_PREFIX + "/apps/" + APP_TTS + "/tts"
    mus_url = host + API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate"

    if a.dry_run:
        reqs = []
        for s in sb["scenes"]:
            reqs.append({"step": "出图", "url": img_url,
                         "body": {"model": APP_IMAGE, "prompt": s["imagePrompt"], "n": 1,
                                  "size": a.size, "output_format": "png",
                                  "response_format": "b64_json"}})
        for s in sb["scenes"]:
            reqs.append({"step": "出片", "url": vid_url,
                         "body": _video_body(s, "<免费 upload 后的地址>", a.resolution,
                                             a.ratio)})
        for i, c in enumerate(narration_chunks(sb["scenes"]), 1):
            reqs.append({"step": "旁白", "url": tts_url,
                         "body": {"text": c, "model": a.tts_model, "format": a.tts_format}})
        if music:
            reqs.append({"step": "配乐", "url": mus_url,
                         "body": {"model": a.music_model, "custom_mode": False,
                                  "instrumental": True,
                                  "prompt": a.music_prompt or "轻音乐，舒缓，钢琴与弦乐，"
                                                              "适合纪录片旁白垫底"}})
        out = {"ok": True, "dryRun": True, "mode": "make",
               "storyboard": sb_path, "chars": chars, "sceneCount": sb["sceneCount"],
               "totalSeconds": sb["totalSeconds"], "narrationChars": narr,
               "requests": reqs, "estimatedPoints": total, "yuan": yuan(total),
               "basis": basis}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（一个请求都不发）：%d 字 → %d 镜 × %d 秒 = %d 秒"
              % (chars, sb["sceneCount"], seconds, sb["totalSeconds"]))
        print()
        print("  [0] 本地分镜（0 点）：%s" % sb_path)
        for r in reqs:
            print("  [%s] POST %s" % (r["step"], r["url"]))
            print("        %s" % json.dumps(r["body"], ensure_ascii=False)[:300])
        print()
        print("  预估：%d 点（%.2f 元）· %s" % (total, yuan(total), basis))
        if total > a.budget:
            print("  比 --budget %d 点高，真跑要 --budget %d" % (a.budget, total))
        return 0

    save_sb(sb_path, sb)
    say("① 分镜：%d 镜 × %d 秒（0 点）→ %s" % (sb["sceneCount"], seconds, sb_path))
    r1 = do_images(a, key, host, sb, sb_path)
    say("② 出图完成：%d 张，%d 点" % (len(r1.get("files") or []),
                                     r1.get("billedPoints") or 0))
    r2 = do_render(a, key, host, sb, sb_path)
    say("③ 出片完成：%d 段，%d 点" % (len(r2.get("clips") or []),
                                     r2.get("estimatedPoints") or 0))
    r3 = do_voice(a, key, host, sb, sb_path)
    say("④ 旁白完成：%d 块，%d 点" % (r3.get("chunks") or 0,
                                     r3.get("estimatedPoints") or 0))
    r4 = do_music(a, key, host, sb, sb_path) if music else None
    if r4:
        say("⑤ 配乐完成：%s" % r4.get("file"))

    outdir = a.out
    concat = write_concat(outdir, [s.get("videoPath") for s in sb["scenes"]])
    nar_files = r3.get("files") or []
    narration = nar_files[0] if nar_files else None
    audio_concat = write_audio_concat(outdir, nar_files)
    ffmpeg_pre = None
    if audio_concat:
        narration = os.path.join(outdir, "narration.mp3")
        ffmpeg_pre = ("ffmpeg -f concat -safe 0 -i narration-concat.txt -c copy "
                      "narration.mp3")
    bgm = (r4 or {}).get("file")
    cmd = ffmpeg_cmd(concat, narration, bgm)
    billed = ((r1.get("billedPoints") or 0) + (r2.get("estimatedPoints") or 0)
              + (r3.get("estimatedPoints") or 0) + ((r4 or {}).get("estimatedPoints") or 0))
    sb["assemble"] = {"concat": concat, "narration": narration, "bgm": bgm,
                      "audioConcat": audio_concat, "ffmpegPre": ffmpeg_pre,
                      "ffmpeg": cmd, "outdir": outdir}
    save_sb(sb_path, sb)
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "make", "ok": True,
                "chars": chars, "scenes": sb["sceneCount"], "points": billed,
                "storyboard": sb_path})
    out = {"ok": True, "mode": "make", "storyboard": sb_path, "chars": chars,
           "sceneCount": sb["sceneCount"], "totalSeconds": sb["totalSeconds"],
           "narrationChars": narr, "clips": r2.get("clips"),
           "narrationFiles": nar_files, "musicFile": bgm,
           "concat": concat, "audioConcat": audio_concat, "ffmpegPre": ffmpeg_pre,
           "ffmpeg": cmd, "estimatedPoints": total,
           "billedPoints": billed, "yuan": yuan(billed)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print()
    print("全链路跑完：%d 镜 / %d 秒成片，实扣 %d 点（%.2f 元）"
          % (sb["sceneCount"], sb["totalSeconds"], billed, yuan(billed)))
    print("  分镜：%s" % sb_path)
    if concat:
        print("  片段：%s（%d 段）" % (concat, len(r2.get("clips") or [])))
    for p in (r3.get("files") or []):
        print("  旁白：%s" % p)
    if bgm:
        print("  配乐：%s" % bgm)
    print()
    print("  最后一刀在本地（零依赖不出片，ffmpeg 在你机器上跑）：")
    print("    cd %s" % outdir)
    if ffmpeg_pre:
        print("    先把 %d 段旁白拼成一条：" % len(nar_files))
        print("    %s" % ffmpeg_pre)
    print("    %s" % cmd)
    return 0


def cmd_task(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    t = get_task(key, host, a.task_id)
    st = str(t.get("status") or "").lower()
    video, vwhere = pick_asset(t, "video")
    image, iwhere = pick_asset(t, "image")
    audio, awhere = pick_asset(t, "audio")
    out = {"ok": True, "taskId": a.task_id, "status": st, "tool": t.get("tool"),
           "videoUrl": video, "imageUrl": image, "audioUrl": audio,
           "cost": t.get("cost"), "refund": t.get("refund"),
           "message": t.get("message"), "usage": t.get("usage"),
           "raw": t if a.json else None}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s" % (st or "?"))
    if t.get("tool"):
        print("  能力：%s" % t.get("tool"))
    if video:
        print("  视频：%s  (%s)" % (video, vwhere))
    if image:
        print("  图片：%s  (%s)" % (image, iwhere))
    if audio:
        print("  音频：%s  (%s)" % (audio, awhere))
    if t.get("cost") is not None:
        print("  实扣：%s 点（退回 %s 点）" % (t.get("cost"), t.get("refund")))
    if t.get("message"):
        print("  说明：%s" % str(t.get("message"))[:300])
    if not any((video, image, audio)):
        print("  还没解析到产物（没完成就是这样，过一会儿再查）")
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
        what = e.get("file") or e.get("taskId") or e.get("storyboard") or "-"
        print("  %s  %-7s %-22s %s" % (e.get("at"), e.get("mode") or "-",
                                       os.path.basename(str(what))[:22],
                                       "%s 点" % e.get("points")))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 图文转视频（一篇公众号文章 → 带旁白与配乐的成片，走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/images/generations · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/media_services_33/music_generate · "
               "GET %s/api/v1/tasks/<taskId>" % (
                   DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="五段链路的能力、端点、单价（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="按字数先算钱：精华版 / 全文版 / 各分辨率（免费）",
                       allow_abbrev=False)
    p.add_argument("--chars", type=int, default=2000, help="文章字数（默认 2000）")
    p.add_argument("--scenes", type=int, default=0, help="切几镜（默认按 170 字一镜自动算）")
    p.add_argument("--seconds", type=int, default=5, help="每镜秒数 4~15（默认 5）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="480P",
                   help="出片分辨率（默认 480P，最便宜的档）")
    p.add_argument("--no-music", action="store_true", help="不算配乐那 50 点")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 价目 / 端点（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("plan", help="文章 → 分镜脚本（0 点，纯本地）", allow_abbrev=False)
    p.add_argument("--article", help="文章路径（.md / .txt，UTF-8 或 GB18030）")
    p.add_argument("--text", help="直接给一段文案（不读文件）")
    p.add_argument("--title", help="片子标题（默认取文章第一句）")
    p.add_argument("--scenes", type=int, default=0, help="切几镜（默认按 170 字一镜自动算）")
    p.add_argument("--seconds", type=int, default=5, help="每镜秒数 4~15（默认 5）")
    p.add_argument("--narration-chars", dest="narration_chars", type=int, default=NARR_CHARS,
                   help="每镜旁白上限字数（默认 %d）" % NARR_CHARS)
    p.add_argument("--ratio", choices=RATIOS, default="16:9", help="画幅（默认 16:9）")
    p.add_argument("--style", default="电影感纪实", help="画面风格词，会拼进提示词")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="480P",
                   help="只用于估算（默认 480P）")
    p.add_argument("--no-music", action="store_true", help="估算时不带配乐")
    p.add_argument("--out", default=DEFAULT_OUT, help="输出目录（默认 build）")
    p.add_argument("--storyboard", default=None, help="分镜文件路径（默认 <out>/storyboard.json）")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("image", help="逐镜出图（6 点/张，要 --yes）", allow_abbrev=False)
    p.add_argument("--storyboard", default=DEFAULT_SB, help="分镜文件（默认 build/storyboard.json）")
    p.add_argument("--out", default=None, help="图片目录（默认分镜文件所在目录）")
    p.add_argument("--size", default="1536x1024", help="出图尺寸（默认 1536x1024）")
    p.add_argument("--ref", default=None, help="参考图：给了就改走 nano_banana（72 点/次）")
    p.add_argument("--ref-model", dest="ref_model", default="nano-banana",
                   help="nano_banana 的模型（默认 nano-banana）")
    p.add_argument("--ratio", choices=RATIOS, default="16:9", help="画幅（改图时用）")
    p.add_argument("--force", action="store_true", help="已有的图也重出")
    p.add_argument("--timeout", type=int, default=180, help="单次请求超时秒数")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_image)

    def add_render(p):
        p.add_argument("--storyboard", default=DEFAULT_SB,
                       help="分镜文件（默认 build/storyboard.json）")
        p.add_argument("--out", default=None, help="片段目录（默认分镜文件所在目录）")
        p.add_argument("--resolution", choices=RESOLUTIONS, default="480P",
                       help="分辨率（默认 480P）")
        p.add_argument("--seconds", type=int, default=None,
                       help="覆盖每段秒数 4~15（默认用分镜里的值）")
        p.add_argument("--ratio", choices=RATIOS, default="16:9", help="画幅（默认 16:9）")
        p.add_argument("--force", action="store_true", help="已有的片段也重出")
        p.add_argument("--wait", type=int, default=900, help="单条任务等结果的秒数（默认 900）")
        p.add_argument("--every", type=int, default=8, help="轮询间隔秒数（默认 8，免费 GET）")
        p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数")
        p.add_argument("--yes", action="store_true", help="确认真实扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("render", help="逐镜图生视频（480P 14 点/秒起，要 --yes）",
                       allow_abbrev=False)
    add_render(p)
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("voice", help="旁白（约 0.18 点/字，要 --yes）", allow_abbrev=False)
    p.add_argument("--storyboard", default=DEFAULT_SB, help="分镜文件（默认 build/storyboard.json）")
    p.add_argument("--out", default=None, help="音频目录（默认分镜文件所在目录）")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro", help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3", help="mp3 / wav / opus")
    p.add_argument("--timeout", type=int, default=180, help="单次请求超时秒数")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="配乐一首（50 点起，要 --yes）", allow_abbrev=False)
    p.add_argument("--storyboard", default=DEFAULT_SB, help="分镜文件（默认 build/storyboard.json）")
    p.add_argument("--out", default=None, help="音频目录（默认分镜文件所在目录）")
    p.add_argument("--music-model", dest="music_model", default="V6", help="Suno 模型（默认 V6）")
    p.add_argument("--music-prompt", dest="music_prompt", default=None,
                   help="配乐风格描述（默认按分镜风格拼）")
    p.add_argument("--wait", type=int, default=600, help="等结果的秒数（默认 600）")
    p.add_argument("--every", type=int, default=8, help="轮询间隔秒数（默认 8）")
    p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_music)

    p = sub.add_parser("make", help="一键全链路：分镜 → 出图 → 出片 → 旁白 → 配乐",
                       allow_abbrev=False)
    p.add_argument("--article", help="文章路径（.md / .txt）")
    p.add_argument("--title", help="片子标题")
    p.add_argument("--scenes", type=int, default=0, help="切几镜（默认按 170 字一镜自动算）")
    p.add_argument("--seconds", type=int, default=5, help="每镜秒数 4~15（默认 5）")
    p.add_argument("--narration-chars", dest="narration_chars", type=int, default=NARR_CHARS,
                   help="每镜旁白上限字数（默认 %d）" % NARR_CHARS)
    p.add_argument("--resolution", choices=RESOLUTIONS, default="480P", help="分辨率（默认 480P）")
    p.add_argument("--ratio", choices=RATIOS, default="16:9", help="画幅（默认 16:9）")
    p.add_argument("--style", default="电影感纪实", help="画面风格词")
    p.add_argument("--size", default="1536x1024", help="出图尺寸（默认 1536x1024）")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro", help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3", help="mp3 / wav / opus")
    p.add_argument("--music-model", dest="music_model", default="V6", help="Suno 模型")
    p.add_argument("--music-prompt", dest="music_prompt", default=None, help="配乐风格描述")
    p.add_argument("--no-music", action="store_true", help="不出配乐（省 50 点起）")
    p.add_argument("--out", default=DEFAULT_OUT, help="输出目录（默认 build）")
    p.add_argument("--storyboard", default=None, help="分镜文件（默认 <out>/storyboard.json）")
    p.add_argument("--force", action="store_true", help="已有的图 / 片段也重出")
    p.add_argument("--wait", type=int, default=900, help="单条任务等结果的秒数")
    p.add_argument("--every", type=int, default=8, help="轮询间隔秒数")
    p.add_argument("--timeout", type=int, default=180, help="单次请求超时秒数")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_make)

    p = sub.add_parser("task", help="查任务状态 / 补取产物（免费）", allow_abbrev=False)
    p.add_argument("--task-id", dest="task_id", help="提交时返回的 taskId")
    p.set_defaults(fn=cmd_task)

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


FREE = ("cmd_cost", "cmd_plan", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    key, host = load_conf(getattr(a, "key", None), getattr(a, "host", None))
    fn_name = getattr(a.fn, "__name__", "")
    if not key and fn_name not in FREE:
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
