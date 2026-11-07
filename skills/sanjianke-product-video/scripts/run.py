#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 商品视频（sanjianke-product-video）

一张商品图 → 场景图 → 短视频 → 配音 → 字幕，四步一条命令，走 api.a7w.cn。

## 这条链路上的 4 个应用（GET /api/v1/apps 实测，17 个接口）

  nano_banana   2 个接口   submit（生成场景图）      query（文档里的查询口）
  full_video    2 个接口   submit（一键成片，按秒）   query（文档里的查询口）
  voice_tts     6 个接口   tts（同步配音）            tts_async / tts_live / stt / clone_voice / list_voices
  seedance      7 个接口   create（生成）             其余 6 个是素材管理 / 查询，不是生成

seedance 那 7 个接口的真实分工（官方文档 + 平台 schema 实测）：
  create        生成视频，唯一出片的口子（价目表 11,000 点/次）
  createGroup   建素材分组（multipart：Name / GroupType / Description / ProjectName）
  createAsset   把公网 URL 的素材入库（multipart：URL / GroupId / AssetType / Name）
  getAsset      查素材状态 Active / Processing / Failed（multipart：Id）
  updateAsset   改素材名（multipart：Id / Name）
  deleteAsset   删素材（multipart：Id）
  query         任务查询（GET，等价于通用 /api/v1/tasks/<id>）
  → 6 个里 5 个是**素材托管**，不是生成；做商品视频用不到素材托管，一张商品图当首帧就够。

## 价格（GET /api/v1/pricing 实测，单位：点，1 元 = 100 点）

  full_video/submit   按秒 + 按分辨率：480P 14 · 768P 28 · 1080P 60 · 2K 80 · 4K 80
  nano_banana/submit  72 点/次（上游实测 points_cost=24，站内 ×3）
  voice_tts/*         上游真实点数 × 3（实测 tts_live 一条 33 字：上游 2.64 → 站内 7.92 点）
  seedance/create     11,000 点/次（固定）
  字幕               0 点（本包本地生成 SRT，不用接口）

## 三条实测出来的「会白花钱」的坑

  一、`GET /api/v1/apps/<app>` 按该应用 flat 单价扣、且不退。本包一次都不打；目录用
      `GET /api/v1/apps`（价目表 cost:0），价目用 `GET /api/v1/pricing`（只读）。
  二、应用层查询口也在价目表的通配里：`/api/v1/apps/nano_banana/*` = 72 点/次、
      `/api/v1/apps/seedance/*` = 11,000 点/次。所以本包查进度**只用** `GET /api/v1/tasks/<id>`。
  三、`voice_tts/list_voices` 是 GET，但站内会先 reserve 150 点再全额退（实测流水
      reserve_sync → refund，净 0、钱包被短暂冻过）。本包不做这类探针。

## 子命令

  catalog  4 个应用 17 个接口 + 单价（免费，2 个只读 GET）
  cost     先算钱：4/6/10/15 秒 × 5 档分辨率（免费，0 请求）
  doctor   自检 Key / 应用在架 / 5 档按秒价 / 查询路由（免费，4 个只读 GET）
  script   口播文案切分成 SRT 字幕 + 时间轴（免费，0 请求）
  upload   商品图上传拿一个能直接提交的地址（免费，站内 /api/v1/upload cost:0）
  scene    nano_banana 出场景图（72 点/次）
  clip     full_video 一键成片（按秒计费）
  voice    voice_tts 配音（上游点数 × 3）
  make     全链路：场景图 → 成片 → 配音 → SRT（要 --yes，受 --budget 管）
  seedance seedance 7 个接口（create 生成 / 5 个素材管理 / query 说明）
  status   查任务（免费，GET /api/v1/tasks/<id>）
  log      本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost --duration 6 --resolution 768P --chars 24
  python3 scripts/run.py script --text "轻到 0.9 克，戴一天忘了它在耳朵里。" --duration 6 --out shop.srt
  python3 scripts/run.py make --image 商品图.jpg --text "轻到 0.9 克，戴一天忘了它在耳朵里。" \\
      --duration 6 --resolution 768P --ratio 9:16 --scene-prompt "原木桌面，晨光，浅景深" --yes

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
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

# ── GBK 编码兜底（Windows 控制台 / 管道重定向）──────────────────────────────
# 中文 Windows 上 stdout 被重定向时用的是 cp936，遇到编不出的符号会 UnicodeEncodeError 崩掉。
# 先给 errors='replace' 兜底，再把符号收敛到 cp936 里有的 √ / × / · / →。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "product-video-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-product-video/%s" % VERSION

APP_NANO = "nano_banana"
APP_VIDEO = "full_video"
APP_TTS = "voice_tts"
APP_SEEDANCE = "seedance"

# 4 个应用 + 17 个接口（GET /api/v1/apps 实测）
APPS = [
    dict(code=APP_NANO, name="nano-banana", 用途="出场景图", apis=[
        ("submit", "POST", "生成图片", "72 点/次"),
        ("query", "GET", "查图片任务", "落在 72 点通配里，本包不用"),
    ]),
    dict(code=APP_VIDEO, name="全能视频生成", 用途="一键成片", apis=[
        ("submit", "POST", "提交成片任务", "按秒 + 按分辨率"),
        ("query", "POST", "查成片任务", "落在通配里，本包不用"),
    ]),
    dict(code=APP_TTS, name="语音 TTS", 用途="配音", apis=[
        ("tts", "POST", "同步配音", "上游点数 × 3"),
        ("tts_async", "POST", "异步长文本配音", "上游点数 × 3"),
        ("tts_live", "POST", "流式配音", "上游点数 × 3"),
        ("stt", "POST", "语音转文字", "上游点数 × 3"),
        ("clone_voice", "POST", "克隆音色", "上游点数 × 3"),
        ("list_voices", "GET", "音色列表", "GET 也会先冻 150 点再退"),
    ]),
    dict(code=APP_SEEDANCE, name="Seedance 2.0", 用途="备选成片 / 素材托管", apis=[
        ("create", "POST", "生成视频（唯一出片口）", "11,000 点/次"),
        ("createGroup", "POST", "建素材分组（素材管理）", "落 11,000 点通配"),
        ("createAsset", "POST", "素材入库（素材管理）", "落 11,000 点通配"),
        ("getAsset", "POST", "查素材状态（素材管理）", "落 11,000 点通配"),
        ("updateAsset", "POST", "改素材名（素材管理）", "落 11,000 点通配"),
        ("deleteAsset", "POST", "删素材（素材管理）", "落 11,000 点通配"),
        ("query", "GET", "查任务（等价 /tasks/<id>）", "落 11,000 点通配"),
    ]),
]

# full_video 专属定价：按秒 × 分辨率（GET /api/v1/pricing 原文）
FULL_VIDEO_RATES = [("480P", 14), ("768P", 28), ("1080P", 60), ("2K", 80), ("4K", 80)]
RATE_MAP = dict(FULL_VIDEO_RATES)
RESOLUTIONS = [r for r, _ in FULL_VIDEO_RATES]
DUR_MIN, DUR_MAX = 4, 15
RATIOS = ["9:16", "16:9", "1:1", "4:3", "3:4", "adaptive"]

NANO_POINTS = 72          # 点/次
SEEDANCE_POINTS = 11000   # 点/次
TTS_MARKUP = 3            # 上游真实点数 × 3
TTS_POINTS_PER_CHAR = 0.18  # 实测 33 字 → 5.94 点，反推 0.18 点/字
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 3000     # 点，= 30 元

TERMINAL_OK = ("completed", "success", "succeeded", "done")
TERMINAL_BAD = ("failed", "error", "cancelled", "canceled", "timeout", "expired")
VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".pcm")


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
    """发一次请求。网关会重置空闲连接，网络类错误退避重试；4xx 直接返回给调用方。"""
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
    """multipart/form-data。seedance 的素材管理接口与 /upload 都是这个形态。"""
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
    """网关两套错误风格：{code:1,data} 与 {error:{code,message}}，这里都认。"""
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


def api_post_json(key, host, path, body, timeout=120):
    url = host + path
    return envelope(*http_json("POST", url, key, body, timeout=timeout), url=url)


def api_get_json(key, host, path, timeout=60):
    url = host + path
    return envelope(*http_json("GET", url, key, None, timeout=timeout), url=url)


# ───────────────────────── 算钱 ─────────────────────────
def fmt_pts(n):
    return "{:,}".format(int(round(float(n))))


def _w(s):
    """显示宽度：中日韩字符占 2 列，表格才对得齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def yuan(pts):
    return round(float(pts) / POINTS_PER_YUAN, 2)


def tts_points(text):
    """配音点数：上游真实点数 × 3。按 0.18 点/字估（实测 33 字 = 5.94 点反推）。"""
    n = max(1, int(round(len(text or "") * TTS_POINTS_PER_CHAR)))
    return n


def quote(duration, resolution, scene=True, chars=0):
    """一条商品视频的总价明细。返回 (总点数, [明细行])。"""
    rate = RATE_MAP[resolution]
    items = []
    if scene:
        items.append(("场景图 nano-banana", NANO_POINTS, "72 点/次"))
    clip_pts = rate * int(duration)
    items.append(("成片 full_video %s" % resolution, clip_pts,
                  "%d 点/秒 × %d 秒" % (rate, int(duration))))
    if chars:
        tp = tts_points("x" * chars)
        items.append(("配音 voice_tts", tp, "上游点数 × 3，约 0.18 点/字"))
    items.append(("字幕 SRT", 0, "本地生成，0 点"))
    total = sum(p for _, p, _ in items)
    return total, items


def gate(a, cost, basis):
    """两道闸门：超预算退 5（一个请求都不发）；没 --yes 退 4（并告诉你要花多少）。
    --dry-run 只打印请求，两道闸门都放行，方便先看清楚再决定。"""
    if cost > a.budget and not a.dry_run:
        raise Fail("budget",
                   "预计 %d 点超过 --budget %d 点（%s）。调大 --budget（单位：点，1 元 = 100 点）再试，"
                   "一个请求都没发。" % (cost, a.budget, basis), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实扣费约 %d 点（%.2f 元）：%s。确认请加 --yes。"
                   % (cost, yuan(cost), basis), EXIT_CONFIRM)
    return cost


def _dry(a, url, body, cost, basis, extra=None):
    out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
           "estimatedPoints": cost, "yuan": yuan(cost), "basis": basis,
           "overBudget": cost > a.budget}
    if extra:
        out.update(extra)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（不提交、不冻结、不扣费）")
    print("  端点：%s" % url)
    print("  请求：%s" % json.dumps(body, ensure_ascii=False))
    print("  预估：%d 点（%.2f 元）· %s" % (cost, yuan(cost), basis))
    if cost > a.budget:
        print("  这比 --budget %d 点高，真跑要 --budget %d" % (a.budget, cost))
    return 0


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


# ───────────────────────── 任务与产物 ─────────────────────────
def get_task(key, host, tid):
    """查任务只看 GET /api/v1/tasks/<id>（价目表 cost:0）。应用层查询口都在通配价里。"""
    st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + urllib.parse.quote(tid),
                        key, timeout=60)
    d = jloads(txt) or {}
    if st == 200 and d.get("code") == 0:
        raise Fail("call", "查不到任务 %s：%s" % (tid, d.get("msg") or "任务不存在"), EXIT_CALL)
    if st not in (200, 201):
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    data = d.get("data")
    return data if isinstance(data, dict) else d


def wait_task(a, key, host, tid):
    deadline = time.time() + max(60, a.wait)
    seen, ticks = None, 0
    while time.time() < deadline:
        ticks += 1
        d = get_task(key, host, tid)
        st = str(d.get("status") or "").lower()
        if st != seen:
            say("  状态：%s%s" % (st or "?", "（%s）" % d.get("progress")
                                 if d.get("progress") else ""))
            seen = st
        if st in TERMINAL_OK or st in TERMINAL_BAD:
            return d
        time.sleep(max(2, a.every))
    raise Fail("call",
               "等了 %d 秒还没完成。任务没丢：`status --task-id %s` 接着取，"
               "**别重新提交**（会再扣一次）。" % (a.wait, tid), EXIT_CALL)


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
    """在任务返回里找成片地址。返回 (url, 字段路径) 或 (None, None)。"""
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


def download(url, outdir, prefix, idx, ext_hint=None):
    os.makedirs(outdir, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as x:
        raw = x.read()
    ext = ext_hint or ".bin"
    low = url.split("?")[0].lower()
    for e in VIDEO_EXT + IMAGE_EXT + AUDIO_EXT:
        if low.endswith(e):
            ext = e
            break
    p = os.path.join(outdir, "%s-%02d%s" % (prefix, idx, ext))
    io.open(p, "wb").write(raw)
    return p


# ───────────────────────── 字幕（0 点，纯本地） ─────────────────────────
# 只按中文标点与 !?; 切行：`,` 与 `.` 会切断小数（0.9 克）和英文缩写
SPLIT_RE = re.compile(r"[，。！？；、：:!?;\n\r]+")


def srt_time(sec):
    ms = int(round(max(0.0, sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def split_script(text, duration, want_lines=None):
    """把口播文案切成 N 段，按字数分配时间。返回 [(起, 止, 文案)]。"""
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in SPLIT_RE.split(text) if p.strip()]
    if not parts:
        parts = [text]
    if want_lines and want_lines > 0:
        n = want_lines
    else:
        n = max(1, min(len(parts), int(round(float(duration) / 2.2))))
    # 份数比句子多：把最长的句子拆开
    while len(parts) < n:
        i = max(range(len(parts)), key=lambda j: len(parts[j]))
        s = parts[i]
        cut = max(1, len(s) // 2)
        parts[i:i + 1] = [s[:cut], s[cut:]]
    # 份数比句子少：相邻合并
    while len(parts) > n:
        i = min(range(len(parts) - 1), key=lambda j: len(parts[j]) + len(parts[j + 1]))
        parts[i:i + 2] = [parts[i] + "，" + parts[i + 1]]
    total = float(sum(len(p) for p in parts)) or 1.0
    rows, t = [], 0.0
    for p in parts:
        span = duration * len(p) / total
        rows.append((t, t + span, p))
        t += span
    return rows


def write_srt(rows, path):
    lines = []
    for i, (s, e, text) in enumerate(rows, 1):
        lines.append("%d\n%s --> %s\n%s\n" % (i, srt_time(s), srt_time(e), text))
    body = "\n".join(lines)
    io.open(path, "w", encoding="utf-8", newline="\n").write(body)
    return path


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    # 只用目录 GET 与价目 GET：价目表里这两条都是 cost:0
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d = jloads(txt) or {}
    listing = d.get("data") if isinstance(d.get("data"), list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    st2, txt2 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt2) or {}).get("pricing") or {}

    rows = []
    for app in APPS:
        it = online.get(app["code"]) or {}
        live = {x.get("code") for x in (it.get("apis") or []) if isinstance(x, dict)}
        for code, method, name, price in app["apis"]:
            rows.append({"app": app["code"], "appName": app["name"], "purpose": app["用途"],
                         "api": code, "method": method, "name": name, "price": price,
                         "online": code in live})
    rate = (pricing.get(API_PREFIX + "/apps/full_video/submit") or {})
    out = {"ok": True, "apps": len(APPS), "interfaces": len(rows),
           "online": bool(listing), "rows": rows,
           "fullVideoRates": rate.get("resolutionRates") or RATE_MAP,
           "nanoPoints": (pricing.get(API_PREFIX + "/apps/nano_banana/submit") or {}).get("cost"),
           "seedancePoints": (pricing.get(API_PREFIX + "/apps/seedance/create") or {}).get("cost"),
           "pricingRead": st2 == 200, "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 商品视频 —— 4 个应用 %d 个接口（本站目录共 %d 个应用）"
          % (len(rows), len(listing)))
    print()
    print("  %s %s %s %s %s" % (pad("应用", 14), pad("接口", 14), pad("方法", 6),
                                pad("干什么", 26), "价格"))
    print("  " + "-" * 90)
    last = None
    for r in rows:
        if r["app"] != last:
            print("  %s（%s）" % (r["appName"], r["purpose"]))
            last = r["app"]
        print("    %s %s %s %s %s" % (pad("", 12), pad(r["api"], 14), pad(r["method"], 6),
                                      pad(r["name"], 26), r["price"]))
    print()
    print("  full_video 按秒价（GET /api/v1/pricing 现查）：%s" % " · ".join(
        "%s %d 点/秒" % (r, p) for r, p in FULL_VIDEO_RATES))
    print("  nano_banana %s 点/次 · seedance %s 点/次" % (
        fmt_pts(out["nanoPoints"] or NANO_POINTS),
        fmt_pts(out["seedancePoints"] or SEEDANCE_POINTS)))
    print()
    print("  seedance 7 个接口里只有 create 出片，其余 5 个是素材托管 + 1 个查询。")
    print("  一张商品图当首帧就够，素材托管不是必需品 —— 本包默认链路只用 3 个应用接口（+ 免费 upload）。")
    return 0


def cmd_cost(a, key, host):
    dur = max(DUR_MIN, min(DUR_MAX, a.duration))
    res = a.resolution
    chars = a.chars if a.chars is not None else max(1, int(round(dur * 4)))
    total, items = quote(dur, res, scene=not a.no_scene, chars=chars)
    matrix = []
    for d in (4, 6, 10, 15):
        row = {"duration": d, "cells": []}
        for r in RESOLUTIONS:
            pts, _ = quote(d, r, scene=not a.no_scene, chars=int(round(d * 4)))
            row["cells"].append({"resolution": r, "points": pts, "yuan": yuan(pts)})
        matrix.append(row)
    out = {"ok": True, "duration": dur, "resolution": res, "chars": chars,
           "scene": not a.no_scene, "items": [{"name": n, "points": p, "basis": b}
                                             for n, p, b in items],
           "total": total, "yuan": yuan(total), "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "matrix": matrix,
           "unitPrice": {"nano": NANO_POINTS, "fullVideo": RATE_MAP,
                         "ttsPerChar": TTS_POINTS_PER_CHAR, "seedance": SEEDANCE_POINTS},
           "notes": ["1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-07 实测）",
                     "full_video 按秒 + 按分辨率：480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80",
                     "nano-banana 固定 72 点/次（上游实测 points_cost=24，站内 ×3）",
                     "voice_tts 按上游真实点数 × 3；实测一条 33 字 5.94 点，按 0.18 点/字估",
                     "字幕本包本地生成 SRT，0 点"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("一条商品视频多少钱（1 元 = 100 点）")
    print()
    print("  %d 秒 · %s · %s · 口播 %d 字"
          % (dur, res, "带场景图" if not a.no_scene else "不出场景图", chars))
    print("  " + "-" * 62)
    for n, p, b in items:
        print("  %s %s 点   %s" % (pad(n, 26), pad(fmt_pts(p), 8, left=False), b))
    print("  " + "-" * 62)
    print("  %s %s 点   = %.2f 元" % (pad("合计", 26), pad(fmt_pts(total), 8, left=False),
                                    yuan(total)))
    print()
    print("  全档价目（%s + 配音，按 4 字/秒估口播）"
          % ("含场景图 72 点" if not a.no_scene else "不含场景图"))
    print("  %s %s" % (pad("秒数", 8), "".join("%12s" % r for r in RESOLUTIONS)))
    print("  " + "-" * 68)
    for row in matrix:
        print("  %s %s" % (pad("%d 秒" % row["duration"], 8),
                           "".join("%12s" % fmt_pts(c["points"]) for c in row["cells"])))
    print("  %s %s" % (pad("折合元", 8),
                       "".join("%12s" % ("%.1f" % c["yuan"]) for c in matrix[-1]["cells"])))
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

    # 应用目录：价目表 cost:0；一次拿全 4 个应用与 17 个接口
    st2, txt2 = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d2 = jloads(txt2) or {}
    listing = d2.get("data") if isinstance(d2.get("data"), list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    miss = [x["code"] for x in APPS if x["code"] not in online]
    checks.append(("4 个应用在架（nano / video / tts / seedance）",
                   bool(listing) and not miss,
                   "目录 %d 个应用%s" % (len(listing),
                                        "，缺 " + ",".join(miss) if miss else "")))
    matched = 0
    for x in APPS:
        live_codes = {y.get("code") for y in (online.get(x["code"], {}).get("apis") or [])}
        matched += len(live_codes & {c for c, _m, _n, _p in x["apis"]})
    checks.append(("17 个依赖接口全部注册", matched >= 17,
                   "命中 %d / 17 个接口（nano 2 + video 2 + tts 6 + seedance 7）" % matched))

    # 价目：full_video 5 档按秒价 + 两个 flat 价
    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt3) or {}).get("pricing") or {}
    rate = (pricing.get(API_PREFIX + "/apps/full_video/submit") or {})
    live = rate.get("resolutionRates") or {}
    drift = ["%s 本地 %d / 线上 %s" % (r, p, live.get(r))
             for r, p in FULL_VIDEO_RATES if int(live.get(r) or -1) != p]
    checks.append(("full_video 5 档按秒价与线上一致", st3 == 200 and bool(live) and not drift,
                   "HTTP %s · %s" % (st3, "5 档全一致" if not drift else " / ".join(drift)[:110])))
    nano = (pricing.get(API_PREFIX + "/apps/nano_banana/submit") or {}).get("cost")
    seed = (pricing.get(API_PREFIX + "/apps/seedance/create") or {}).get("cost")
    checks.append(("专属定价命中（nano 72 / seedance 11,000）",
                   int(nano or 0) == NANO_POINTS and int(seed or 0) == SEEDANCE_POINTS,
                   "nano %s 点 / seedance %s 点" % (nano, seed)))

    # 查询路由：假 id 返回「任务不存在」，说明路由在且不扣费
    st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/product-video-doctor-probe",
                          key, timeout=40)
    d4 = jloads(txt4) or {}
    checks.append(("任务查询 GET /tasks/<id> 可用", st4 == 200 and d4.get("code") == 0,
                   "HTTP %s %s" % (st4, (d4.get("msg") or "")[:40])))

    out = {"ok": all(c[1] for c in checks), "apps": [x["code"] for x in APPS],
           "interfaceCount": 17, "requests": 4, "estimatedPoints": 0,
           "endpoints": {"scene": host + API_PREFIX + "/apps/nano_banana/submit",
                         "clip": host + API_PREFIX + "/apps/full_video/submit",
                         "voice": host + API_PREFIX + "/apps/voice_tts/tts",
                         "task": host + API_PREFIX + "/tasks/<task_id>"},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（4 个只读 GET：/user/balance · /api/v1/apps · /api/v1/pricing · /api/v1/tasks）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 46), dt))
    print()
    print("  端点：POST /api/v1/apps/full_video/submit（成片）· POST /api/v1/apps/nano_banana/submit（场景图）")
    print("        POST /api/v1/apps/voice_tts/tts（配音）· GET /api/v1/tasks/<task_id>（查进度）")
    print("  价格：480P 14 · 768P 28 · 1080P 60 · 2K 80 · 4K 80 点/秒；场景图 72 点/次；配音 上游×3")
    print("  本轮 4 个请求全是只读 GET，价目表口径 cost:0，扣 0 点、冻 0 点。")
    return 0 if out["ok"] else EXIT_GATE


def cmd_script(a, key, host):
    text = a.text or ""
    if not text.strip():
        raise Fail("usage", "必须给 --text（一句口播文案，例如「轻到 0.9 克，戴一天忘了它在耳朵里。」）",
                   EXIT_USAGE)
    dur = max(1, a.duration)
    rows = split_script(text, dur, a.lines)
    path = None
    if a.out:
        path = write_srt(rows, a.out)
    out = {"ok": True, "duration": dur, "chars": len(text), "lines": len(rows),
           "srt": path, "segments": [{"start": round(s, 2), "end": round(e, 2), "text": t}
                                     for s, e, t in rows],
           "ttsPoints": tts_points(text), "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("口播 %d 字 → %d 行字幕（%d 秒，0 点）" % (len(text), len(rows), dur))
    print()
    for i, (s, e, t) in enumerate(rows, 1):
        print("  %d  %s → %s  %s" % (i, srt_time(s), srt_time(e), t))
    if path:
        print()
        print("  已写：%s（%d 字节）" % (path, os.path.getsize(path)))
        print("  烧进画面（ffmpeg 在你本机跑，不走接口）：")
        print("    ffmpeg -i clip.mp4 -vf subtitles=%s -c:a copy out.mp4" % os.path.basename(path))
    print()
    print("  这条配音约 %d 点（上游点数 × 3，0.18 点/字估）。字幕本身 0 点。" % out["ttsPoints"])
    return 0


# ───────────────────────── 上传（免费） ─────────────────────────
def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（商品图 / 视频路径）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + API_PREFIX + "/upload"
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": path, "size": size,
               "estimatedPoints": 0, "free": True}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传）")
        print("  端点：POST %s（multipart/form-data，字段名 file）" % url)
        print("  文件：%s（%d 字节）" % (path, size))
        print("  费用：0 点（价目表 /api/v1/upload 是 cost:0 的免费路径）")
        return 0
    say("正在上传 %s（%d 字节）…" % (os.path.basename(path), size))
    t0 = time.time()
    st, txt = http_multipart(url, key, {}, [("file", path)], timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    out = {"ok": True, "url": got, "path": data.get("path"), "name": data.get("name"),
           "size": data.get("size"), "mime": data.get("mime_type"), "type": data.get("type"),
           "elapsed": round(dt, 1), "estimatedPoints": 0}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "upload", "ok": True,
                "file": path, "size": size, "url": got})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（%.1fs，0 点）" % dt)
    print("  地址：%s" % got)
    print("  类型：%s · %s · %d 字节" % (data.get("type"), data.get("mime_type"),
                                        data.get("size") or size))
    print()
    print("  下一步：python3 scripts/run.py clip --image \"%s\" --text \"卖点一句\" --yes" % got)
    return 0


# ───────────────────────── 场景图 ─────────────────────────
def _image_url(a, key, host, value, dry):
    """本地文件先 upload（免费）拿地址；已经是 http(s) 就直接用。"""
    if not value:
        raise Fail("usage", "必须给商品图路径或地址", EXIT_USAGE)
    if os.path.isfile(value):
        if dry:
            return "<upload 之后的地址（免费）: %s>" % os.path.basename(value)
        say("上传商品图 %s …" % os.path.basename(value))
        st, txt = http_multipart(host + API_PREFIX + "/upload", key, {},
                                 [("file", value)], timeout=a.timeout)
        d = jloads(txt) or {}
        got = (d.get("data") or {}).get("url") if isinstance(d.get("data"), dict) else None
        if d.get("code") != 1 or not got:
            raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
        return got
    if not re.match(r"^https?://", value, re.I):
        raise Fail("usage", "--image 要么是本机文件路径，要么是 http(s) 地址（当前 %s）" % value,
                   EXIT_USAGE)
    return value


def cmd_scene(a, key, host):
    if not a.prompt:
        raise Fail("usage", "必须给 --prompt（场景描述，例如「原木桌面，晨光，浅景深」）", EXIT_USAGE)
    count = max(1, a.count)
    cost = NANO_POINTS * count
    gate(a, cost, "场景图 %d 点/次 × %d 张" % (NANO_POINTS, count))
    url = host + API_PREFIX + "/apps/" + APP_NANO + "/submit"
    body = {"action": "edit" if a.image else "generate",
            "model": a.model, "prompt": a.prompt, "resolution": a.resolution,
            "aspect_ratio": a.ratio}
    if a.image:
        body["image_urls"] = [_image_url(a, key, host, a.image, a.dry_run)]
    if a.dry_run:
        return _dry(a, url, body, cost, "场景图 %d 点/次 × %d 张" % (NANO_POINTS, count))

    say("正在出场景图（%s）…" % a.model)
    data = api_post_json(key, host, API_PREFIX + "/apps/" + APP_NANO + "/submit", body,
                         timeout=a.timeout)
    tid = data.get("task_id") or data.get("taskId")
    if not tid:
        raise Fail("call", "提交后没拿到 task_id：%s"
                   % json.dumps(data, ensure_ascii=False)[:300], EXIT_CALL)
    say("  task_id=%s" % tid)
    t = wait_task(a, key, host, tid)
    st = str(t.get("status") or "").lower()
    if st in TERMINAL_BAD:
        raise Fail("call", "场景图任务失败：%s" % (t.get("message") or t.get("fail_reason") or st),
                   EXIT_CALL)
    img, where = pick_asset(t, "image")
    paths = []
    if a.out and img:
        paths.append(download(img, a.out, a.prefix or "scene", 1))
    usage = t.get("usage") if isinstance(t.get("usage"), dict) else {}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "scene", "ok": bool(img),
                "taskId": tid, "image": img, "points": cost})
    out = {"ok": bool(img), "taskId": tid, "status": st, "imageUrl": img, "field": where,
           "files": paths, "estimatedPoints": cost, "upstream": usage.get("points_cost")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if img else EXIT_CALL
    print("场景图出来了")
    print("  任务：%s   状态：%s" % (tid, st))
    if img:
        print("  图片：%s" % img)
        print("  字段：%s" % where)
    for p in paths:
        print("  已存：%s（%d 字节）" % (p, os.path.getsize(p)))
    if usage.get("points_cost") is not None:
        print("  上游成本：%s 点（站内按 %d 点/次收）" % (usage.get("points_cost"), NANO_POINTS))
    return 0 if img else EXIT_CALL


# ───────────────────────── 成片 ─────────────────────────
def _clip_body(a, image_url):
    content = [{"type": "text", "text": a.text}]
    if image_url:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})
    for u in (a.ref_image or []):
        content.append({"type": "image_url", "role": "reference_image",
                        "image_url": {"url": u}})
    body = {"model": a.model, "content": content, "duration": int(a.duration),
            "resolution": a.resolution, "ratio": a.ratio,
            "aigc_watermark": bool(a.watermark)}
    return body


def _preflight_clip(a):
    if not a.text:
        raise Fail("usage", "必须给 --text（画面描述 / 卖点一句）", EXIT_USAGE)
    if a.duration < DUR_MIN or a.duration > DUR_MAX:
        raise Fail("usage", "--duration 取 %d~%d 的整数秒（当前 %s）"
                   % (DUR_MIN, DUR_MAX, a.duration), EXIT_USAGE)
    if a.resolution not in RATE_MAP:
        raise Fail("usage", "--resolution 只能是：%s" % " / ".join(RESOLUTIONS), EXIT_USAGE)


def cmd_clip(a, key, host):
    _preflight_clip(a)
    rate = RATE_MAP[a.resolution]
    cost = rate * int(a.duration)
    gate(a, cost, "%d 点/秒 × %d 秒（%s）" % (rate, a.duration, a.resolution))
    url = host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit"
    image_url = _image_url(a, key, host, a.image, True) if a.image else None
    body = _clip_body(a, image_url)
    if a.dry_run:
        return _dry(a, url, body, cost, "%d 点/秒 × %d 秒" % (rate, a.duration))
    if a.image and os.path.isfile(a.image):
        body["content"][1]["image_url"]["url"] = _image_url(a, key, host, a.image, False)

    say("正在提交成片（%s / %d 秒 / %s）…" % (a.resolution, a.duration, a.ratio))
    data = api_post_json(key, host, API_PREFIX + "/apps/" + APP_VIDEO + "/submit", body,
                         timeout=a.timeout)
    tid = data.get("task_id") or data.get("taskId") or data.get("id")
    if not tid:
        raise Fail("call", "提交后没拿到 task_id：%s"
                   % json.dumps(data, ensure_ascii=False)[:300], EXIT_CALL)
    say("  task_id=%s" % tid)
    t = wait_task(a, key, host, tid)
    st = str(t.get("status") or "").lower()
    if st in TERMINAL_BAD:
        raise Fail("call", "成片任务失败：%s" % (t.get("message") or t.get("fail_reason") or st),
                   EXIT_CALL)
    video, where = pick_asset(t, "video")
    paths = []
    if a.out and video:
        paths.append(download(video, a.out, a.prefix or "clip", 1))
    usage = t.get("usage") if isinstance(t.get("usage"), dict) else {}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "clip", "ok": bool(video),
                "taskId": tid, "video": video, "duration": a.duration,
                "resolution": a.resolution, "points": cost})
    out = {"ok": bool(video), "taskId": tid, "status": st, "videoUrl": video, "field": where,
           "files": paths, "duration": a.duration, "resolution": a.resolution,
           "estimatedPoints": cost, "yuan": yuan(cost),
           "upstream": usage.get("points_cost")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if video else EXIT_CALL
    print("成片完成")
    print("  任务：%s   状态：%s" % (tid, st))
    if video:
        print("  视频：%s" % video)
        print("  字段：%s" % where)
    for p in paths:
        print("  已存：%s（%d 字节）" % (p, os.path.getsize(p)))
    print("  预估：%d 点（%.2f 元）· 实际按成片秒数结算" % (cost, yuan(cost)))
    return 0 if video else EXIT_CALL


# ───────────────────────── 配音 ─────────────────────────
def cmd_voice(a, key, host):
    if not a.text:
        raise Fail("usage", "必须给 --text（要念出来的口播文案）", EXIT_USAGE)
    cost = tts_points(a.text)
    gate(a, cost, "配音 %d 字 ≈ %d 点（上游点数 × 3）" % (len(a.text), cost))
    url = host + API_PREFIX + "/apps/" + APP_TTS + "/tts"
    body = {"text": a.text, "model": a.model, "format": a.format}
    for k, v in (("reference_id", a.reference_id), ("sample_rate", a.sample_rate),
                 ("mp3_bitrate", a.bitrate)):
        if v is not None:
            body[k] = v
    if a.dry_run:
        return _dry(a, url, body, cost, "配音 %d 字（上游点数 × 3）" % len(a.text))

    say("正在配音（%s / %d 字）…" % (a.model, len(a.text)))
    data = api_post_json(key, host, API_PREFIX + "/apps/" + APP_TTS + "/tts", body,
                         timeout=a.timeout)
    audio = None
    for k in ("audio_url", "audioUrl", "url"):
        if isinstance(data.get(k), str) and data[k].startswith("http"):
            audio = data[k]
            break
    if not audio:
        audio, _where = pick_asset(data, "audio")
    paths = []
    if a.out and audio:
        paths.append(download(audio, a.out, a.prefix or "voice", 1))
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "voice", "ok": bool(audio),
                "chars": len(a.text), "audio": audio, "points": cost})
    out = {"ok": bool(audio), "audioUrl": audio, "format": data.get("format") or a.format,
           "chars": len(a.text), "files": paths, "estimatedPoints": cost,
           "yuan": yuan(cost)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if audio else EXIT_CALL
    if not audio:
        print("返回里没找到音频地址，原始返回：")
        print(json.dumps(data, ensure_ascii=False)[:800])
        return EXIT_CALL
    print("配音好了（%d 字）" % len(a.text))
    print("  音频：%s" % audio)
    for p in paths:
        print("  已存：%s（%d 字节）" % (p, os.path.getsize(p)))
    print("  预估：%d 点（%.2f 元）· 上游真实点数 × %d 结算" % (cost, yuan(cost), TTS_MARKUP))
    return 0


# ───────────────────────── 全链路 ─────────────────────────
def cmd_make(a, key, host):
    _preflight_clip(a)
    if not a.image:
        raise Fail("usage", "必须给 --image（商品图路径或地址）", EXIT_USAGE)
    scene = bool(a.scene_prompt) and not a.no_scene
    rate = RATE_MAP[a.resolution]
    chars = len(a.text)
    total, items = quote(a.duration, a.resolution, scene=scene, chars=chars)
    basis = " + ".join("%s %s 点" % (n, fmt_pts(p)) for n, p, _b in items if p)
    gate(a, total, basis)

    up = host + API_PREFIX + "/upload"
    scene_url = host + API_PREFIX + "/apps/" + APP_NANO + "/submit"
    clip_url = host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit"
    voice_url = host + API_PREFIX + "/apps/" + APP_TTS + "/tts"

    if a.dry_run:
        img = _image_url(a, key, host, a.image, True)
        rows = [{"step": "scene", "method": "POST", "url": scene_url,
                 "body": {"action": "edit", "model": a.scene_model, "prompt": a.scene_prompt,
                          "image_urls": [img], "aspect_ratio": a.ratio,
                          "resolution": a.scene_resolution}}] if scene else []
        rows.append({"step": "clip", "method": "POST", "url": clip_url,
                     "body": _clip_body(a, img)})
        rows.append({"step": "voice", "method": "POST", "url": voice_url,
                     "body": {"text": a.text, "model": a.tts_model, "format": a.tts_format}})
        rows.append({"step": "subtitle", "method": "LOCAL", "url": "-",
                     "body": {"text": a.text, "duration": a.duration, "lines": a.lines}})
        out = {"ok": True, "dryRun": True, "steps": rows, "estimatedPoints": total,
               "yuan": yuan(total), "basis": basis,
               "uploadUrl": up if os.path.isfile(a.image) else None}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（三步接口 + 一步本地字幕，一个请求都不发）")
        print()
        if os.path.isfile(a.image):
            print("  [0] 上传商品图：POST %s（免费，字段名 file）" % up)
        for r in rows:
            mark = {"scene": "场景图", "clip": "成片", "voice": "配音",
                    "subtitle": "字幕"}[r["step"]]
            if r["method"] == "LOCAL":
                print("  [%s] 本地生成 SRT（0 点，不发请求）" % mark)
                continue
            print("  [%s] %s %s" % (mark, r["method"], r["url"]))
            print("        请求：%s" % json.dumps(r["body"], ensure_ascii=False))
        print()
        print("  预估：%d 点（%.2f 元）· %s" % (total, yuan(total), basis))
        return 0

    # 1) 商品图 → 公网地址（本地文件先免费上传）
    img_url = _image_url(a, key, host, a.image, False)

    # 2) 场景图（可选）
    scene_shot = None
    stid = None
    if scene:
        say("① 出场景图（%s）…" % a.scene_model)
        sbody = {"action": "edit", "model": a.scene_model, "prompt": a.scene_prompt,
                 "image_urls": [img_url], "aspect_ratio": a.ratio,
                 "resolution": a.scene_resolution}
        sdata = api_post_json(key, host, API_PREFIX + "/apps/" + APP_NANO + "/submit", sbody,
                              timeout=a.timeout)
        stid = sdata.get("task_id") or sdata.get("taskId")
        if not stid:
            raise Fail("call", "场景图没拿到 task_id：%s"
                       % json.dumps(sdata, ensure_ascii=False)[:300], EXIT_CALL)
        st_task = wait_task(a, key, host, stid)
        if str(st_task.get("status") or "").lower() in TERMINAL_BAD:
            raise Fail("call", "场景图任务失败：%s"
                       % (st_task.get("message") or st_task.get("fail_reason")), EXIT_CALL)
        scene_shot, _w = pick_asset(st_task, "image")
        if not scene_shot:
            raise Fail("call", "场景图任务完成但没解析到图片地址，用 status --task-id %s 看看" % stid,
                       EXIT_CALL)
        say("   场景图：%s" % scene_shot)
        if a.out:
            download(scene_shot, a.out, "scene", 1)

    # 3) 成片
    say("② 出成片（%s / %d 秒 / %s）…" % (a.resolution, a.duration, a.ratio))
    body = _clip_body(a, scene_shot or img_url)
    cdata = api_post_json(key, host, API_PREFIX + "/apps/" + APP_VIDEO + "/submit", body,
                          timeout=a.timeout)
    ctid = cdata.get("task_id") or cdata.get("taskId") or cdata.get("id")
    if not ctid:
        raise Fail("call", "成片没拿到 task_id：%s"
                   % json.dumps(cdata, ensure_ascii=False)[:300], EXIT_CALL)
    say("   task_id=%s" % ctid)
    ctask = wait_task(a, key, host, ctid)
    if str(ctask.get("status") or "").lower() in TERMINAL_BAD:
        raise Fail("call", "成片任务失败：%s"
                   % (ctask.get("message") or ctask.get("fail_reason")), EXIT_CALL)
    video, _where = pick_asset(ctask, "video")
    if not video:
        raise Fail("call", "成片任务完成但没解析到视频地址，用 status --task-id %s 看看" % ctid,
                   EXIT_CALL)
    say("   成片：%s" % video)

    # 4) 配音
    say("③ 配音（%d 字）…" % chars)
    vdata = api_post_json(key, host, API_PREFIX + "/apps/" + APP_TTS + "/tts",
                          {"text": a.text, "model": a.tts_model, "format": a.tts_format},
                          timeout=a.timeout)
    audio = None
    for k in ("audio_url", "audioUrl", "url"):
        if isinstance(vdata.get(k), str) and vdata[k].startswith("http"):
            audio = vdata[k]
            break
    if not audio:
        audio, _w2 = pick_asset(vdata, "audio")

    # 5) 字幕（本地，0 点）
    rows = split_script(a.text, a.duration, a.lines)
    srt_path = None
    paths = []
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        srt_path = write_srt(rows, os.path.join(a.out, (a.prefix or "shop") + ".srt"))
        try:
            paths.append(download(video, a.out, a.prefix or "shop", 1))
            if audio:
                paths.append(download(audio, a.out, a.prefix or "shop", 2, ext_hint=".mp3"))
        except Exception as e:                                   # noqa: BLE001
            say("  下载失败（链接仍可用）：%s" % e)

    usage = ctask.get("usage") if isinstance(ctask.get("usage"), dict) else {}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "make", "ok": True,
                "clipTaskId": ctid, "video": video, "audio": audio, "srt": srt_path,
                "duration": a.duration, "resolution": a.resolution,
                "pointsFloor": total})
    out = {"ok": True, "videoUrl": video, "audioUrl": audio, "srt": srt_path,
           "clipTaskId": ctid, "sceneTaskId": stid if scene else None,
           "sceneImage": scene_shot, "files": paths,
           "duration": a.duration, "resolution": a.resolution,
           "estimatedPoints": total, "yuan": yuan(total),
           "upstream": usage.get("points_cost")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("成片链路跑完（%d 秒 / %s）" % (a.duration, a.resolution))
    print("  视频：%s" % video)
    if audio:
        print("  配音：%s" % audio)
    if srt_path:
        print("  字幕：%s（%d 行，0 点）" % (srt_path, len(rows)))
    for p in paths:
        print("  已存：%s（%d 字节）" % (p, os.path.getsize(p)))
    print("  预估：%d 点（%.2f 元）· %s" % (total, yuan(total), basis))
    print()
    print("  合成（在你本机跑，不走接口）：")
    print("    ffmpeg -i clip.mp4 -i voice.mp3 -vf subtitles=shop.srt -c:v libx264 -c:a aac out.mp4")
    return 0


# ───────────────────────── seedance 7 接口 ─────────────────────────
SEED_ACTIONS = ["create", "group", "asset", "get", "update", "delete"]


def cmd_seedance(a, key, host):
    base = host + API_PREFIX + "/apps/" + APP_SEEDANCE + "/"
    act = a.action
    if act == "create":
        if not a.text:
            raise Fail("usage", "create 要给 --text（画面描述）", EXIT_USAGE)
        if a.duration < DUR_MIN or a.duration > DUR_MAX:
            raise Fail("usage", "--duration 取 %d~%d 的整数秒" % (DUR_MIN, DUR_MAX), EXIT_USAGE)
        body = {"model": a.model,
                "content": [{"type": "text", "text": a.text}],
                "duration": int(a.duration), "resolution": a.resolution, "ratio": a.ratio}
        if a.image:
            body["content"].append({"type": "image_url", "role": "first_frame",
                                    "image_url": {"url": a.image}})
        cost = SEEDANCE_POINTS
        basis = "seedance/create 固定 11,000 点/次"
        gate(a, cost, basis)
        if a.dry_run:
            return _dry(a, base + "create", body, cost, basis)
        data = api_post_json(key, host, API_PREFIX + "/apps/" + APP_SEEDANCE + "/create",
                             body, timeout=a.timeout)
        tid = data.get("task_id") or data.get("taskId") or data.get("id")
        if not tid:
            raise Fail("call", "没拿到 task_id：%s" % json.dumps(data, ensure_ascii=False)[:300],
                       EXIT_CALL)
        out = {"ok": True, "taskId": tid, "api": "create", "estimatedPoints": cost,
               "next": "python3 scripts/run.py status --task-id %s" % tid}
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "seedance",
                    "ok": True, "taskId": tid, "points": cost})
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("seedance 任务已提交")
        print("  任务：%s" % tid)
        print("  查进度：python3 scripts/run.py status --task-id %s" % tid)
        print("  预估：11,000 点（110.00 元）")
        return 0

    # 5 个素材管理接口 + query：都是 multipart
    fields = {"ProjectName": a.project}
    if act == "group":
        if not a.name:
            raise Fail("usage", "group 要给 --name（分组名，上限 64 字符）", EXIT_USAGE)
        fields.update({"Name": a.name, "GroupType": a.group_type})
        if a.description:
            fields["Description"] = a.description
        api = "createGroup"
    elif act == "asset":
        if not (a.url and a.group_id and a.asset_type):
            raise Fail("usage", "asset 要给 --url / --group-id / --asset-type", EXIT_USAGE)
        fields.update({"URL": a.url, "GroupId": a.group_id, "AssetType": a.asset_type})
        if a.name:
            fields["Name"] = a.name
        api = "createAsset"
    elif act == "get":
        if not a.asset_id:
            raise Fail("usage", "get 要给 --asset-id", EXIT_USAGE)
        fields["Id"] = a.asset_id
        api = "getAsset"
    elif act == "update":
        if not (a.asset_id and a.name):
            raise Fail("usage", "update 要给 --asset-id 和 --name", EXIT_USAGE)
        fields.update({"Id": a.asset_id, "Name": a.name})
        api = "updateAsset"
    else:
        if not a.asset_id:
            raise Fail("usage", "delete 要给 --asset-id", EXIT_USAGE)
        fields["Id"] = a.asset_id
        api = "deleteAsset"

    cost = SEEDANCE_POINTS
    basis = ("seedance 素材管理：官方文档标免费，但站内价目表 /api/v1/apps/seedance/* "
             "= 11,000 点/次，按通配估算")
    gate(a, cost, basis)
    if a.dry_run:
        if a.json:
            print(json.dumps({"ok": True, "dryRun": True, "url": base + api,
                              "multipartFields": fields, "estimatedPoints": cost,
                              "basis": basis}, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s%s（multipart/form-data）" % (base, api))
        print("  字段：%s" % json.dumps(fields, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）· %s" % (cost, yuan(cost), basis))
        if cost > a.budget:
            print("  这比 --budget %d 点高，真跑要 --budget %d" % (a.budget, cost))
        return 0
    st, txt = http_multipart(base + api, key, fields, [], timeout=a.timeout)
    d = jloads(txt) or {}
    out = {"ok": d.get("code") in (1, 200), "api": api, "http": st,
           "data": d.get("data"), "msg": d.get("msg"),
           "estimatedPoints": cost}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "seedance-" + api,
                "ok": bool(out["ok"]), "points": cost,
                "detail": (d.get("msg") or "")[:120]})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_CALL
    print("seedance %s：HTTP %s" % (api, st))
    print("  返回：%s" % json.dumps(d.get("data"), ensure_ascii=False)[:600])
    if not out["ok"]:
        print("  说明：%s" % err_text(st, txt))
    return 0 if out["ok"] else EXIT_CALL


def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    t = get_task(key, host, a.task_id)
    st = str(t.get("status") or "").lower()
    video, _w = pick_asset(t, "video")
    image, _w2 = pick_asset(t, "image")
    audio, _w3 = pick_asset(t, "audio")
    usage = t.get("usage") if isinstance(t.get("usage"), dict) else {}
    out = {"ok": True, "taskId": a.task_id, "model": t.get("model"), "status": st,
           "videoUrl": video, "imageUrl": image, "audioUrl": audio,
           "upstreamPoints": usage.get("points_cost"), "raw": t if a.json else None}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  模型：%s" % (t.get("model") or "-"))
    print("  状态：%s%s" % (st or "?", "  %s" % t.get("progress") if t.get("progress") else ""))
    if video:
        print("  视频：%s" % video)
    if image:
        print("  图片：%s" % image)
    if audio:
        print("  音频：%s" % audio)
    if usage.get("points_cost") is not None:
        print("  上游点数：%s" % usage.get("points_cost"))
    if not (video or image or audio):
        print("  这部还没解析到产物（没完成就是正常的）。原始返回前 600 字：")
        print(json.dumps(t, ensure_ascii=False)[:600])
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
        what = e.get("taskId") or e.get("file") or e.get("srt") or e.get("clipTaskId") or "-"
        print("  %s  %-6s %-14s %-38s %s 点" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            str(what)[:38], fmt_pts(e.get("points") or e.get("pointsFloor") or 0)))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 商品视频（一张商品图 → 场景图 → 短视频 → 配音 → 字幕）",
        epilog="端点：POST %s/api/v1/apps/full_video/submit · POST %s/api/v1/apps/nano_banana/submit · "
               "POST %s/api/v1/apps/voice_tts/tts · GET %s/api/v1/tasks/<task_id>"
               % (DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d = 30 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="4 个应用 17 个接口 + 单价（免费，2 个只读 GET）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：4/6/10/15 秒 × 5 档分辨率（免费，0 请求）",
                       allow_abbrev=False)
    p.add_argument("--duration", type=int, default=6, help="成片秒数 4~15（默认 6）")
    p.add_argument("--resolution", default="768P", choices=RESOLUTIONS,
                   help="分辨率（默认 768P）")
    p.add_argument("--chars", type=int, default=None, help="口播字数（默认 4 字/秒）")
    p.add_argument("--no-scene", action="store_true", help="不估场景图那 72 点")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 5 档按秒价 / 查询路由（免费，4 个只读 GET）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("script", help="口播文案切成分行 SRT 字幕（免费，0 请求）",
                       allow_abbrev=False)
    p.add_argument("--text", help="口播文案（一句话，按标点自动切行）")
    p.add_argument("--duration", type=int, default=6, help="成片秒数（默认 6）")
    p.add_argument("--lines", type=int, default=None, help="强制字幕行数（默认按秒数推）")
    p.add_argument("--out", help="把 SRT 写到这个路径")
    p.set_defaults(fn=cmd_script)

    p = sub.add_parser("upload", help="商品图上传拿地址（免费，站内 /upload 是 cost:0）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    def add_common(p):
        p.add_argument("--yes", action="store_true", help="确认真实扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        p.add_argument("--wait", type=int, default=900, help="等结果的上限秒数（默认 900）")
        p.add_argument("--every", type=int, default=10, help="轮询间隔秒数（默认 10）")
        p.add_argument("--timeout", type=int, default=180, help="单次请求超时秒数（默认 180）")
        p.add_argument("--out", default=None, help="把产物下载到这个目录（可选）")
        p.add_argument("--prefix", default="shop", help="下载文件名前缀（默认 shop）")

    p = sub.add_parser("scene", help="出场景图（nano-banana，72 点/次）", allow_abbrev=False)
    add_common(p)
    p.add_argument("--image", help="商品图（本机路径或 http(s) 地址）")
    p.add_argument("--prompt", help="场景描述，例如「原木桌面，晨光，浅景深」")
    p.add_argument("--model", default="nano-banana",
                   help="nano-banana / nano-banana-2 / nano-banana-pro（默认 nano-banana）")
    p.add_argument("--resolution", default="1K", choices=["1K", "2K", "4K"],
                   help="输出分辨率（默认 1K；2K/4K 只对 :official 档生效）")
    p.add_argument("--ratio", default="9:16", choices=["1:1", "16:9", "9:16", "4:3", "3:4", "auto"],
                   help="宽高比（默认 9:16 竖屏）")
    p.add_argument("--count", type=int, default=1, help="出几张（默认 1，按次叠加）")
    p.set_defaults(fn=cmd_scene)

    p = sub.add_parser("clip", help="一键成片（full_video，按秒 + 按分辨率）", allow_abbrev=False)
    add_common(p)
    p.add_argument("--image", help="首帧图（本机路径或 http(s) 地址）")
    p.add_argument("--text", help="画面描述 / 卖点一句")
    p.add_argument("--model", default="full-video", help="固定 full-video")
    p.add_argument("--duration", type=int, default=6, help="秒数 4~15（默认 6）")
    p.add_argument("--resolution", default="768P", choices=RESOLUTIONS,
                   help="480P/768P/1080P/2K/4K（默认 768P）")
    p.add_argument("--ratio", default="9:16", choices=RATIOS, help="画幅（默认 9:16）")
    p.add_argument("--ref-image", action="append",
                   help="参考图地址，可重复（前 5 张不加价，超出每张 +20 点）")
    p.add_argument("--watermark", action="store_true", help="加生成标识")
    p.set_defaults(fn=cmd_clip)

    p = sub.add_parser("voice", help="配音（voice_tts，上游点数 × 3）", allow_abbrev=False)
    add_common(p)
    p.add_argument("--text", help="要念出来的口播文案")
    p.add_argument("--model", default="s2-pro", help="s1 / s2-pro（默认 s2-pro）")
    p.add_argument("--format", default="mp3", choices=["mp3", "wav", "pcm", "opus"],
                   help="输出格式（默认 mp3）")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色的 model_id")
    p.add_argument("--sample-rate", dest="sample_rate", type=int, default=None,
                   help="采样率 8000/16000/22050/44100")
    p.add_argument("--bitrate", type=int, default=None, help="MP3 比特率 64/128/192")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("make", help="全链路：场景图 → 成片 → 配音 → SRT（要 --yes）",
                       allow_abbrev=False)
    add_common(p)
    p.add_argument("--image", help="商品图（本机路径或 http(s) 地址）")
    p.add_argument("--text", help="口播文案（同时当画面描述的底稿）")
    p.add_argument("--duration", type=int, default=6, help="秒数 4~15（默认 6）")
    p.add_argument("--resolution", default="768P", choices=RESOLUTIONS, help="默认 768P")
    p.add_argument("--ratio", default="9:16", choices=RATIOS, help="默认 9:16")
    p.add_argument("--scene-prompt", dest="scene_prompt", default=None,
                   help="给了就先去 nano-banana 出场景图（多 72 点）")
    p.add_argument("--scene-model", dest="scene_model", default="nano-banana")
    p.add_argument("--scene-resolution", dest="scene_resolution", default="1K",
                   choices=["1K", "2K", "4K"])
    p.add_argument("--no-scene", action="store_true", help="跳过场景图，商品图直接当首帧")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3",
                   choices=["mp3", "wav", "pcm", "opus"])
    p.add_argument("--lines", type=int, default=None, help="强制字幕行数")
    p.add_argument("--model", default="full-video", help="full_video 固定 full-video")
    p.add_argument("--ref-image", action="append", help="参考图地址，可重复")
    p.add_argument("--watermark", action="store_true", help="加生成标识")
    p.set_defaults(fn=cmd_make)

    p = sub.add_parser("seedance", help="seedance 7 个接口（create 生成 / 5 个素材管理）",
                       allow_abbrev=False)
    add_common(p)
    p.add_argument("--action", default="create", choices=SEED_ACTIONS,
                   help="create / group / asset / get / update / delete（默认 create）")
    p.add_argument("--text", help="create：画面描述")
    p.add_argument("--image", help="create：首帧图地址")
    p.add_argument("--model", default="seedance-2-text-2-video",
                   help="seedance-2-text-2-video / -video-2-video / -fast-*")
    p.add_argument("--duration", type=int, default=6, help="秒数 4~15（默认 6）")
    p.add_argument("--resolution", default="720p", choices=["480p", "720p", "1080p"],
                   help="默认 720p")
    p.add_argument("--ratio", default="9:16", choices=RATIOS, help="默认 9:16")
    p.add_argument("--name", help="group/update：名称（上限 64 字符）")
    p.add_argument("--group-type", dest="group_type", default="AIGC",
                   help="group：AIGC（默认）")
    p.add_argument("--description", help="group：描述（上限 300 字符）")
    p.add_argument("--project", default="default", help="ProjectName（默认 default）")
    p.add_argument("--url", help="asset：素材公网 URL")
    p.add_argument("--group-id", dest="group_id", help="asset：分组 Id（来自 group）")
    p.add_argument("--asset-type", dest="asset_type", choices=["Image", "Video", "Audio"],
                   help="asset：素材类型")
    p.add_argument("--asset-id", dest="asset_id", help="get/update/delete：素材 Id")
    p.set_defaults(fn=cmd_seedance)

    p = sub.add_parser("status", help="查任务（免费，GET /api/v1/tasks/<id>）", allow_abbrev=False)
    p.add_argument("--task-id", dest="task_id", help="提交返回的 task_id")
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


FREE = ("cmd_cost", "cmd_script", "cmd_log")


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
    try:
        key, host = load_conf(a.key, a.host)
        fn_name = getattr(a.fn, "__name__", "")
        if not key and fn_name not in FREE and not getattr(a, "dry_run", False):
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
