#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 新闻资讯短视频（sanjianke-news-shorts）

媒体号一天要交的资讯短视频。本包不新造接口，把 api.a7w.cn 上已有的六条能力
按「新闻体结构」重新排了顺序，并且把「一条快讯 / 一条深度」的钱算在前面：

  采集参考  watermark_removal  POST /api/v1/apps/watermark_removal/douyin_search_video
                               POST /api/v1/apps/watermark_removal/xhs_search_note
                               100 点/次（flat，失败亦计）
  配图      gpt-image-2.6      POST /api/v1/images/generations              6 点/张
  播报      voice_tts          POST /api/v1/apps/voice_tts/tts              约 0.18 点/字
  配乐      media_services_33  POST /api/v1/apps/media_services_33/music_generate  50 点起
  成片镜头  full_video         POST /api/v1/apps/full_video/submit          按秒 x 分辨率
  新闻体混剪 smart_clip        POST /api/v1/apps/smart_clip/news_mixcut     4.5 点/秒
  查进度    GET /api/v1/tasks/<task_id>                                     0 点
  传素材    POST /api/v1/upload                                             0 点

## 单价（GET /api/v1/pricing 2026-11-08 现查，单位：点，1 元 = 100 点）

  full_video        480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒
  smart_clip/*      perSecond 4.5，estimate 45（body 不带 duration 时按 45 点预冻结）
  watermark_removal 固定 100 点/次，8 个接口同价
  voice_tts/*       mode=flat、markupPercent=200，对外 = 上游真实点数 x 3
  media_services_33 落通配 *：上游 x 2、单笔保底 50 点
  出图              6 点/张（实测 1024x1024 一张 43.6 秒、扣 6 点）

## 一条快讯 / 一条深度的钱（1080P）

  快讯 30 秒：混剪 135 + 播报 19.8（110 字）+ 配图 18（3 张）        = 172.8 点 = 1.73 元
  深度 90 秒：混剪 405 + 补镜头 900（15 秒）+ 播报 64.8 + 配图 36     = 1,405.8 点 = 14.06 元
  一天 8 条快讯 + 2 条深度 + 1 首配乐（可复用）= 4,244 点 = 42.44 元

## 三条用钱换来的规矩（都做成了默认动作）

  1. 轮询只走 GET /api/v1/tasks/<id>（价目表 cost:0）。应用层 /query 每查一次都按
     该应用单价结算（nano_banana/query 实测 72 点/次），等十分钟能烧掉一条片的钱。
  2. 要目录只看 GET /api/v1/apps 与 GET /api/v1/pricing。GET /api/v1/apps/<app> 命中
     /apps/<app>/* 的通配计价，即时结算、不退（实测 dressing_diffusion 200 点、
     nano_banana 72 点各一笔）。采集类接口失败亦计，所以本包一次都不拿它做探针。
  3. videoUrl / 首帧图 / 混剪素材都必须是平台托管地址。外站地址一律 400
     url_not_allowed，只认 vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/ 一类本站域名与
     oss.gpu.likeadmin.cn/openapi/（POST /api/v1/upload 的返回）。所以本地素材先
     upload（免费）换地址，film / mix 会自动做这一步。

## 本地零成本的部分（0 点，不联网）

  plan  一单的完整交付：五段结构（标题 3 秒 / 事件 / 背景 / 影响 / 来源）、播报稿、
        字幕 SRT、3 条标题、平台描述、6 个标签、配图 prompt、命名、成本单
  qc    交付前合规检查：来源标注、三要素、数字口径、AI 生成标注、五段结构、
        播报语速、平台时长、标题长度、绝对化用语、传闻词、夸张词

## 子命令

  catalog  六道工序 + 端点 + 单价 + 模板 + 平台尺寸（免费）
  cost     一条快讯 / 一条深度 / 一天要多少钱（免费）
  plan     一单的播报稿、字幕、文案、配图 prompt、交付单（免费，纯本地）
  qc       合规与结构检查（免费，纯本地）
  hunt     找热点素材参考，100 点/次（要 --yes）
  cover    配图，6 点/张（要 --yes）
  voice    播报，约 0.18 点/字（要 --yes）
  music    配乐，50 点起（要 --yes）
  film     补镜头 / 生成镜头，按秒计费（要 --yes）
  mix      新闻体混剪，4.5 点/秒（要 --yes）
  upload   上传素材，拿白名单地址（免费）
  status   查任务进度（免费）
  doctor   自检 Key / 应用 / 价目 / 端点（免费，不扣费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --flash 8 --depth 2
  python3 scripts/run.py plan --topic "地铁 3 号线今起延长运营" \\
      --when "今天起" --where "杭州" --subject "市地铁集团" \\
      --event "把末班车延到 23:30" --figure "日均多运 1.2 万人次" \\
      --source "市地铁集团通报" --platform douyin --template flash
  python3 scripts/run.py qc --plan ~/.a7w/news-shorts/flash-20261108/plan.json
  python3 scripts/run.py hunt --platform dy --keyword "地铁 延长运营" --yes
  python3 scripts/run.py cover --template flash --topic "地铁延长运营" --yes
  python3 scripts/run.py voice --text "杭州地铁 3 号线今起延长运营……" --yes
  python3 scripts/run.py mix --title "地铁 3 号线延长运营" --material a.png --yes
  python3 scripts/run.py status --task-id tsk_xxx

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

sys.dont_write_bytecode = True
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")     # 中文控制台不因个别符号崩掉
    except Exception:                        # noqa: BLE001
        pass

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "news-shorts")
LEDGER = os.path.join(HOME_DIR, "ledger.json")
OUT_ROOT = os.path.join(HOME_DIR, "out")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-news-shorts/%s" % VERSION

# ── 六条能力（单价：GET /api/v1/pricing 2026-11-08 现查）────────────────────
APP_VIDEO = "full_video"
VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}
VIDEO_CLIP_MIN = 4
VIDEO_CLIP_MAX = 15

APP_IMAGE = "gpt-image-2.6"
IMG_POINTS = 6
IMAGE_PATH = API_PREFIX + "/images/generations"

APP_TTS = "voice_tts"
TTS_PER_CHAR = 0.18          # 点/字（实测 tts_live 33 字 = 5.94 点，上游真实点数 x 3）
TTS_MAX_CHARS = 500

APP_MUSIC = "media_services_33"
MUSIC_FLOOR = 50
MUSIC_MODEL = "V6"

APP_CLIP = "smart_clip"
MIX_PER_SEC = 4.5            # smart_clip/* perSecond（实测 1.5 x 3）
MIX_ESTIMATE = 45            # body 不带 duration 时的预冻结点数
MIX_PATH = API_PREFIX + "/apps/" + APP_CLIP + "/news_mixcut"
DEFAULT_STYLE_ID = "68aebb91b8619ed6f4168f40"

APP_HUNT = "watermark_removal"
HUNT_POINTS = 100            # flat 100 点/次，上游按请求 20 点、失败亦计
HUNT_APIS = {"dy": "douyin_search_video", "xhs": "xhs_search_note"}

UPLOAD_PATH = API_PREFIX + "/upload"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 6000        # 点 = 60 元，一天 8 快讯 + 2 深度还留余量

RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]
RATIOS = ["9:16", "16:9", "1:1", "4:3", "adaptive"]

# ── 平台尺寸（发布页当期口径）；快讯竖屏，深度可横可竖 ────────────────────
PLATFORMS = {
    "douyin": dict(name="抖音", ratio="9:16", size="1080x1920",
                   maxSeconds=180, tag="#抖音"),
    "kuaishou": dict(name="快手", ratio="9:16", size="1080x1920",
                     maxSeconds=180, tag="#快手"),
    "xhs": dict(name="小红书", ratio="9:16", size="1080x1920",
                maxSeconds=180, tag="#小红书"),
    "channels": dict(name="视频号", ratio="9:16", size="1080x1920",
                     maxSeconds=180, tag="#视频号"),
    "bilibili": dict(name="B 站", ratio="16:9", size="1920x1080",
                     maxSeconds=480, tag="#B站"),
}
PLATFORM_KEYS = list(PLATFORMS)

# ── 两套模板：快讯 30 秒竖屏、深度 90 秒横屏 ─────────────────────────────
# chars 是「按这个字数报价」的设计值；rateMin / rateMax 是这类片的播报语速窗口。
TEMPLATES = {
    "flash": dict(name="快讯", seconds=30, chars=150, images=3, shots=0,
                  ratio="9:16", size="1080x1920", maxSeconds=60,
                  rateMin=4.4, rateMax=6.0, weights=[3, 8, 8, 7, 4]),
    "depth": dict(name="深度", seconds=90, chars=300, images=6, shots=1,
                  ratio="16:9", size="1920x1080", maxSeconds=180,
                  rateMin=2.9, rateMax=4.2, weights=[3, 15, 22, 30, 20]),
}
TEMPLATE_KEYS = ["flash", "depth"]

BEATS = ["标题", "事件", "背景", "影响", "来源"]

VISUALS = {
    "flash": [
        "开场定格：主体标识 / 现场空镜，大字标题压在上三分之一",
        "事件现场：事发地点、相关人群、可核对的画面",
        "背景素材：同主题旧画面、数据板、官方通报截图",
        "影响画面：受影响的人群、路口、站台、办事窗口",
        "片尾字幕板：来源单位 + 通报时间 + AI 辅助生成标注",
    ],
    "depth": [
        "开场定格：主体标识 + 双行标题（≤ 16 字 / 行）",
        "事件现场：多机位素材，3 个以上镜头，交代时间与地点",
        "背景梳理：时间轴动画、公开数据板、旧闻素材",
        "影响拆解：三方视角（当事人 / 主管方 / 旁观者）+ 数据图",
        "片尾字幕板：来源单位 + 通报时间 + 记者署名 + AI 辅助生成标注",
    ],
}

# ── 配图：快讯 3 张、深度 6 张，prompt 直接可用 ───────────────────────────
IMAGE_SETS = {
    "flash": [
        dict(kind="cover", name="封面图", size="1024x1536",
             prompt="{topic}——新闻资讯封面，竖屏构图，主体在画面中部，"
                    "冷色调新闻质感，留出上三分之一标题区，画面无文字、无水印"),
        dict(kind="scene", name="事件现场", size="1024x1536",
             prompt="{where}{subject}{event}，手机竖屏实拍质感，自然光，"
                    "现场人群与标识清晰，纪实新闻摄影风格，画面无文字、无水印"),
        dict(kind="chart", name="数据板", size="1024x1536",
             prompt="新闻数据板示意：干净深色底、单色强调、留白足够放一行数字与单位，"
                    "极简信息图质感，画面无文字、无水印"),
    ],
    "depth": [
        dict(kind="cover", name="横版封面", size="1536x1024",
             prompt="{topic}——资讯专题横版封面，主体偏右，左侧留标题区，"
                    "新闻纪实质感，画面无文字、无水印"),
        dict(kind="scene", name="事件现场", size="1536x1024",
             prompt="{where}{subject}{event}，纪实新闻摄影，多主体层次，自然光，"
                    "画面无文字、无水印"),
        dict(kind="people", name="当事方", size="1536x1024",
             prompt="新闻人物采访感：半身、自然光、浅景深，背景是{where}的日常场景，"
                    "画面无文字、无水印"),
        dict(kind="chart", name="数据图", size="1536x1024",
             prompt="新闻数据图示意：横向柱状结构、单色强调、留白足够放三行数字，"
                    "极简信息图质感，画面无文字、无水印"),
        dict(kind="timeline", name="时间轴", size="1536x1024",
             prompt="新闻时间轴示意：横向四节点、节点间留白、深色底浅色线，"
                    "画面无文字、无水印"),
        dict(kind="ending", name="片尾板", size="1536x1024",
             prompt="资讯片尾板示意：居中留白、低调深色底、右下角预留来源与标注位置，"
                    "画面无文字、无水印"),
    ],
}

MUSIC_STYLE = {
    "flash": "新闻快讯片头感：短促电子鼓点加铜管重音，118 BPM，8 秒一个循环，收尾干净",
    "depth": "新闻专题底乐：低频脉冲加弦乐铺底，88 BPM，情绪克制，不抢人声",
}

# ── 合规词表（qc 用正向提示，不用负面句式）────────────────────────────
ABS_PAT = re.compile(r"(最(?!新|近|后)[好佳强优惠大低高快严]|第一(?!时间)|唯一|顶级|绝对|全网|"
                     r"史无前例|绝无仅有|百分之百|100\s*%)")
RUMOR_PAT = re.compile(r"(据说|网传|传闻|疑似|内部消息|内幕|小道消息|有人爆料|听朋友说)")
HYPE_PAT = re.compile(r"(震惊|惊呆了|炸了|刷屏|史上最|疯狂|逆天|太吓人|恐怖)")

AI_LABEL_DEFAULT = "AI 辅助生成"
SOURCE_TAIL = "，以官方最新通报为准。"


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
        except Exception:                                            # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=120, retries=3):
    """JSON 请求。只读 GET 与付费 POST 都走这里；连接被掐时退避重试。"""
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
            return e.code, e.read().decode("utf-8", "replace")
        except urllib.error.URLError as e:
            last = "连不上 %s：%s" % (url, e.reason)
        except Exception as e:                                       # noqa: BLE001
            last = "请求异常：%s: %s" % (type(e).__name__, e)
        if attempt < retries - 1:
            time.sleep(0.5 if attempt == 0 else 1.2)
    raise Fail("call", last or "请求失败", EXIT_CALL)


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
    except Exception as e:                                           # noqa: BLE001
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def url_allowed(u):
    """上游只收平台托管的地址。返回 (ok, 说明)。"""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:                                                # noqa: BLE001
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
    except Exception:                                                # noqa: BLE001
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
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


def payload_of(d):
    """拆信封：{"code":1,"data":{…}} / {"data":{…}} / 裸对象，三种都兜住。"""
    if not isinstance(d, dict):
        return {}
    if d.get("code") in (0, 1) and isinstance(d.get("data"), (dict, list)):
        return d["data"]
    return d


def find_media_url(node, depth=0):
    if depth > 8:
        return None
    if isinstance(node, str):
        low = node.lower()
        if node.startswith("http") and any(x in low for x in (".mp3", ".wav", ".m4a")):
            return node
        return None
    if isinstance(node, dict):
        for k in ("audio_url", "audioUrl", "audio", "url", "source_url"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                if any(x in v.lower() for x in (".mp3", ".wav", ".m4a")):
                    return v
        for v in node.values():
            got = find_media_url(v, depth + 1)
            if got:
                return got
    elif isinstance(node, list):
        for v in node:
            got = find_media_url(v, depth + 1)
            if got:
                return got
    return None


def find_item_list(node, depth=0):
    """采集接口的返回层级各家不同，找第一个「看起来是作品列表」的数组。"""
    if depth > 6:
        return []
    if isinstance(node, list):
        if node and isinstance(node[0], dict) and any(
                k in node[0] for k in ("title", "desc", "note_title", "aweme_id", "id")):
            return node
        for v in node:
            got = find_item_list(v, depth + 1)
            if got:
                return got
        return []
    if isinstance(node, dict):
        for k in ("list", "items", "data", "results", "videos", "notes"):
            if isinstance(node.get(k), (list, dict)):
                got = find_item_list(node[k], depth + 1)
                if got:
                    return got
        for v in node.values():
            got = find_item_list(v, depth + 1)
            if got:
                return got
    return []


def fmt_pts(n, dec=False):
    """点数格式化。dec=True 时保留一位小数（播报这类按字算出来的不是整数）。"""
    try:
        v = float(n)
    except Exception:                                                # noqa: BLE001
        return str(n)
    if dec and abs(v - round(v)) > 1e-9:
        return "{:,.1f}".format(v)
    return "{:,}".format(int(round(v)))


def yuan(pts):
    return round(float(pts) / POINTS_PER_YUAN, 2)


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def today():
    return time.strftime("%Y%m%d")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dir(p):
    try:
        os.makedirs(p, exist_ok=True)
        return p
    except Exception as e:                                           # noqa: BLE001
        raise Fail("internal", "建目录失败：%s（%s）" % (p, e), EXIT_INTERNAL)


def write_text(path, text):
    ensure_dir(os.path.dirname(path) or ".")
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return path


def ledger_add(rec):
    try:
        ensure_dir(HOME_DIR)
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                                # noqa: BLE001
        pass


def gate(a, cost, basis):
    """两道闸门：超预算退 5（一个请求都不发）；没 --yes 退 4（并报要花多少）。"""
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


def clips_for(seconds):
    """把总秒数拆成 4~15 秒的段（full_video 的单段上限）。"""
    out, left = [], int(seconds)
    while left > 0:
        take = min(VIDEO_CLIP_MAX, left)
        out.append(take)
        left -= take
    return out


def video_points(seconds, resolution):
    return VIDEO_RATES[resolution] * int(seconds)


def _trim(v):
    v = round(float(v), 1)
    return int(v) if abs(v - int(v)) < 1e-6 else v


def _slug(s):
    s = re.sub(r"[\\/:*?\"<>|\s]+", "", str(s or ""))
    return s[:24] or "未命名"


def _short(s, n=12):
    s = str(s or "").strip()
    return s if len(s) <= n else s[:n]


# ───────────────────────── 一单的钱（纯本地）─────────────────────────
def item_cost(tpl_key, resolution, shots=None):
    """一条片的点数拆分。shots 为 None 时按模板默认（快讯 0 段、深度 1 段）。"""
    tpl = TEMPLATES[tpl_key]
    shots = tpl["shots"] if shots is None else int(shots)
    mix = _trim(MIX_PER_SEC * tpl["seconds"])
    film = video_points(shots * VIDEO_CLIP_MAX, resolution) if shots else 0
    tts = _trim(tpl["chars"] * TTS_PER_CHAR)
    img = IMG_POINTS * tpl["images"]
    return dict(template=tpl_key, name=tpl["name"], seconds=tpl["seconds"],
                chars=tpl["chars"], images=tpl["images"], shots=shots,
                mix=mix, film=film, tts=tts, img=img,
                subtotal=_trim(mix + film + tts + img))


def day_cost(flash, depth, resolution, shots=None, bgm=1):
    f = item_cost("flash", resolution, shots)
    dd = item_cost("depth", resolution, shots)
    music = MUSIC_FLOOR if bgm else 0
    total = _trim(f["subtotal"] * int(flash) + dd["subtotal"] * int(depth) + music)
    return dict(flash=f, depth=dd, flashCount=int(flash), depthCount=int(depth),
                music=music, total=total, yuan=yuan(total))


# ───────────────────────── 免费：catalog ─────────────────────────
def cmd_catalog(a, key, host):
    ops = [
        dict(op="hunt", name="采集热点参考", points="100 点/次",
             path="POST " + API_PREFIX + "/apps/watermark_removal/douyin_search_video",
             note="flat 100 点/次，8 个接口同价；上游按请求 20 点、失败亦计"),
        dict(op="cover", name="配图", points="6 点/张",
             path="POST " + IMAGE_PATH, note="与尺寸、格式无关，按实际返回张数计"),
        dict(op="voice", name="播报", points="约 0.18 点/字",
             path="POST " + API_PREFIX + "/apps/voice_tts/tts",
             note="markup 200，对外 = 上游真实点数 x 3，以 usage.points_cost 为准"),
        dict(op="music", name="配乐", points="50 点起/首",
             path="POST " + API_PREFIX + "/apps/media_services_33/music_generate",
             note="落通配 *：上游 x 2、单笔保底 50 点"),
        dict(op="film", name="补镜头", points="14~80 点/秒",
             path="POST " + API_PREFIX + "/apps/full_video/submit",
             note="480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80，单段 4~15 秒"),
        dict(op="mix", name="新闻体混剪", points="4.5 点/秒",
             path="POST " + MIX_PATH,
             note="smart_clip/* perSecond 4.5；body 无 duration 时按 45 点预冻结"),
        dict(op="upload", name="传素材", points="0 点",
             path="POST " + UPLOAD_PATH, note="multipart，字段名 file，返回白名单地址"),
        dict(op="status", name="查进度", points="0 点",
             path="GET " + API_PREFIX + "/tasks/<task_id>",
             note="价目表 cost:0，反复查都是 0 点"),
        dict(op="plan", name="出稿 / 字幕 / 文案", points="0 点",
             path="本地", note="五段结构 + 播报稿 + SRT + 标题 + 标签 + 交付单"),
        dict(op="qc", name="合规检查", points="0 点",
             path="本地", note="来源标注 / 三要素 / 数字口径 / AI 标注 / 语速 / 时长"),
    ]
    rowscost = []
    for tk in TEMPLATE_KEYS:
        for r in ("480P", "1080P"):
            it = item_cost(tk, r)
            rowscost.append(dict(template=tk, name=it["name"], seconds=it["seconds"],
                                 resolution=r, mix=it["mix"], film=it["film"],
                                 tts=it["tts"], img=it["img"], subtotal=it["subtotal"],
                                 yuan=yuan(it["subtotal"])))
    out = {"ok": True, "ops": ops, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "templates": [dict(key=k, name=TEMPLATES[k]["name"],
                              seconds=TEMPLATES[k]["seconds"], ratio=TEMPLATES[k]["ratio"],
                              size=TEMPLATES[k]["size"], chars=TEMPLATES[k]["chars"],
                              images=TEMPLATES[k]["images"], shots=TEMPLATES[k]["shots"],
                              maxSeconds=TEMPLATES[k]["maxSeconds"])
                         for k in TEMPLATE_KEYS],
           "platforms": [dict(key=k, name=v["name"], ratio=v["ratio"], size=v["size"],
                              maxSeconds=v["maxSeconds"]) for k, v in PLATFORMS.items()],
           "sampleCosts": rowscost, "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 新闻资讯短视频 —— 六道工序（1 元 = 100 点）")
    print()
    print("  %-8s %-14s %-16s %s" % ("--op", "工序", "单价", "端点"))
    print("  " + "-" * 104)
    for it in ops:
        print("  %-8s %-14s %-16s %s" % (it["op"], it["name"], it["points"], it["path"]))
    print()
    print("  模板")
    for k in TEMPLATE_KEYS:
        t = TEMPLATES[k]
        print("    %-6s %s · %d 秒 · %s · %s · 播报 %d 字 · 配图 %d 张 · 补镜头 %d 段"
              % (k, t["name"], t["seconds"], t["ratio"], t["size"], t["chars"],
                 t["images"], t["shots"]))
    print()
    print("  平台尺寸")
    for k, v in PLATFORMS.items():
        print("    %-9s %-6s %-10s %s %d 秒内" % (k, v["name"], v["size"], v["ratio"],
                                                  v["maxSeconds"]))
    print()
    print("  一条片的钱（成品点数，未含配乐）")
    print("    %-8s %-7s %10s %10s %10s %10s %12s"
          % ("模板", "分辨率", "混剪", "补镜头", "播报", "配图", "合计"))
    print("    " + "-" * 72)
    for r in rowscost:
        print("    %-8s %-7s %10s %10s %10s %10s %12s"
              % (r["name"], r["resolution"], fmt_pts(r["mix"], True),
                 fmt_pts(r["film"], True), fmt_pts(r["tts"], True),
                 fmt_pts(r["img"], True),
                 "%s 点" % fmt_pts(r["subtotal"], True)))
    print()
    print("  配乐另计 50 点起/首，一天一条可复用；一条快讯不含配乐是 172.8 点（1.73 元）。")
    return 0


# ───────────────────────── 免费：cost ─────────────────────────
def cmd_cost(a, key, host):
    res = a.resolution
    shots = a.shots
    day = day_cost(a.flash, a.depth, res, shots, a.bgm)
    table = []
    for r in RESOLUTIONS:
        d = day_cost(a.flash, a.depth, r, shots, a.bgm)
        table.append(dict(resolution=r, flash=d["flash"]["subtotal"],
                          depth=d["depth"]["subtotal"], total=d["total"],
                          yuan=yuan(d["total"])))
    out = {"ok": True, "resolution": res, "flashCount": a.flash, "depthCount": a.depth,
           "bgm": a.bgm, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "flash": day["flash"], "depth": day["depth"], "music": day["music"],
           "dayTotal": day["total"], "dayYuan": day["yuan"], "table": table,
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-08 现查）",
               "混剪按秒：smart_clip/* perSecond 4.5（实测 realman_broadcast 1.5 x 3）",
               "播报按字：0.18 点/字（voice_tts markup 200，以返回 usage.points_cost 为准）",
               "补镜头按秒 x 分辨率：full_video 单段 4~15 秒，深度默认 1 段 15 秒",
               "配乐 50 点起/首，一天一条可复用，所以一天只算一次",
               "采集参考 100 点/次，按次算，不在这张表里",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）")
    print()
    for tk in ("flash", "depth"):
        it = day[tk]
        print("  一条%s（%d 秒，%s）" % (it["name"], it["seconds"], res))
        print("    混剪 %s 秒 x 4.5 = %s 点" % (fmt_pts(it["seconds"]),
                                                fmt_pts(it["mix"], True)))
        if it["film"]:
            print("    补镜头 %d 段 x 15 秒 x %d 点/秒 = %s 点"
                  % (it["shots"], VIDEO_RATES[res], fmt_pts(it["film"], True)))
        print("    播报 %d 字 x 0.18 = %s 点" % (it["chars"], fmt_pts(it["tts"], True)))
        print("    配图 %d 张 x 6 = %s 点" % (it["images"], fmt_pts(it["img"], True)))
        print("    = %s 点 = %.2f 元" % (fmt_pts(it["subtotal"], True),
                                         yuan(it["subtotal"])))
        print()
    print("  一天 %d 条快讯 + %d 条深度 + 配乐 %d 首（可复用）"
          % (a.flash, a.depth, a.bgm))
    print("    = %s 点 = %.2f 元" % (fmt_pts(day["total"], True), day["yuan"]))
    print()
    print("  %-9s %12s %12s %12s %10s" % ("分辨率", "一条快讯", "一条深度", "一天合计", "折合元"))
    print("  " + "-" * 60)
    for r in table:
        mark = "  ← 当前" if r["resolution"] == res else ""
        print("  %-9s %12s %12s %12s %10s%s"
              % (r["resolution"], fmt_pts(r["flash"], True),
                 fmt_pts(r["depth"], True), fmt_pts(r["total"], True),
                 "%.2f" % r["yuan"], mark))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


# ───────────────────────── 免费：plan（纯本地）─────────────────────────
def _meta(a):
    plat = PLATFORMS[a.platform]
    tpl = TEMPLATES[a.template]
    seconds = int(a.seconds) if a.seconds else tpl["seconds"]
    return dict(
        topic=(a.topic or "示例新闻标题").strip(),
        when=(a.when or "今天上午").strip(),
        where=(a.where or "本市").strip(),
        subject=(a.subject or "相关部门").strip(),
        event=(a.event or "发布最新通报").strip(),
        figure=(a.figure or "").strip(),
        background=(a.background or "此前同类情况已有公开通报，本次通报给出了最新口径。").strip(),
        impact=(a.impact or "相关安排自通报发布之日起执行，涉及人群按通报口径办理。").strip(),
        source=(a.source or "待填").strip(),
        quote=(a.quote or "").strip(),
        aiLabel=(a.ai_label or AI_LABEL_DEFAULT).strip(),
        reporter=(a.reporter or "").strip(),
        template=a.template, templateName=tpl["name"], seconds=seconds,
        platform=a.platform, platformName=plat["name"], platformTag=plat["tag"],
        ratio=(a.ratio or (tpl["ratio"] if a.template == "flash" else plat["ratio"])),
        size=(a.size or tpl["size"]),
        maxSeconds=tpl["maxSeconds"], rateMin=tpl["rateMin"], rateMax=tpl["rateMax"],
        designChars=tpl["chars"], designImages=tpl["images"],
    )


def _beat_rows(m):
    ws = TEMPLATES[m["template"]]["weights"]
    total = float(sum(ws))
    secs = float(m["seconds"])
    visuals = VISUALS[m["template"]]
    deeper = m["template"] == "depth"
    event = "%s，%s%s%s。" % (m["when"], m["where"], m["subject"], m["event"])
    if m["figure"]:
        event = "%s%s。" % (event, m["figure"])
    if m["quote"]:
        event = "%s%s。" % (event, m["quote"])
    background = m["background"]
    impact = m["impact"]
    source = "以上信息来自%s%s" % (m["source"], SOURCE_TAIL)
    source = "%s画面与数据均取自公开信息，%s。" % (source, m["aiLabel"])
    if deeper:
        event = "%s通报由%s发布，同步说明了执行时间与适用范围。" % (event, m["subject"])
        background = ("%s同主题的公开信息按时间排列，逐条都能对上通报原文。"
                      "相关时间与范围以通报原文为准，公开渠道都可以核对。" % background)
        impact = "%s沿线单位与社区已同步接到通知，办理窗口按通报里的时间节点受理。" % impact
        source = "%s片尾字幕板标注来源单位与通报时间。" % source
    voice = {
        "标题": "%s。" % _clip(m["topic"], 20),
        "事件": event,
        "背景": background,
        "影响": impact,
        "来源": source,
    }
    rows, t = [], 0.0
    for i, name in enumerate(BEATS):
        dur = round(secs * ws[i] / total, 1)
        start = round(t, 1)
        t = round(t + dur, 1)
        txt = voice[name]
        rows.append(dict(beat=name, start=start, end=round(start + dur, 1),
                         seconds=dur, visual=visuals[i], voice=txt,
                         chars=len(txt),
                         pause="段末停 0.4 秒，换段前留一拍"
                         if i < len(BEATS) - 1 else "片尾定格 1 秒"))
    return rows


def _clip(s, n=20):
    """按字数截断，避开把数字切断、把标点留在末尾。"""
    s = str(s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    while cut and len(s) > len(cut) and cut[-1] in "0123456789." and \
            (s[len(cut)].isdigit() or s[len(cut)] == "."):
        cut = cut[:-1]
    cut = cut.rstrip("，。：；、|｜ .")
    return cut or s[:n]


def _titles(m):
    """三条标题：主体 + 动作 / 事件本体 / 主体 + 数字，每条 ≤ 20 字。"""
    t1 = "%s%s%s" % (m["where"], m["subject"], m["event"])
    if m["figure"] and len(t1) + len(m["figure"]) + 1 <= 20:
        t1 = "%s，%s" % (t1, m["figure"])
    t2 = m["topic"]
    t3 = "%s：%s" % (m["subject"], m["figure"] or m["impact"])
    return [_clip(x, 20) for x in (t1, t2, t3)]


def _tags(m):
    return ["#新闻", "#资讯", "#" + m["where"], "#" + _short(m["subject"], 8),
            "#今日热点", m["platformTag"]]


def _description(m):
    bits = ["%s，%s%s%s。" % (m["when"], m["where"], m["subject"], m["event"])]
    if m["figure"]:
        bits.append("%s。" % m["figure"])
    if m["impact"]:
        bits.append("%s" % m["impact"])
    bits.append("来源：%s。" % m["source"])
    bits.append("（%s）" % m["aiLabel"])
    return "".join(bits)


def _naming(m, kind="full"):
    return "%s_%s_%s_%s_%ds" % (today(), _slug(m["subject"]), _slug(m["templateName"]),
                                m["platform"], m["seconds"])


def _srt_time(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    mnt = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        ms, s = 0, s + 1
    return "%02d:%02d:%02d,%03d" % (h, mnt, s, ms)


def _chunks(text, limit=16):
    """按 16 字切字幕，优先切在标点 / 空格上，切完不留行首空格、不切断数字。"""
    text = (text or "").strip()
    marks = "，。、；：！？ ,.!?;:"
    out = []
    while len(text) > limit:
        cut = limit
        for i in range(limit, max(7, limit // 2), -1):
            if text[i - 1] in marks:
                cut = i
                break
        while 0 < cut < len(text) and (text[cut - 1].isdigit() or text[cut - 1] in ".%") \
                and (text[cut].isdigit() or text[cut] in ".%"):
            cut -= 1
        chunk = text[:cut].strip()
        if chunk:
            out.append(chunk)
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out or [""]


def _subtitle_cues(m, beats):
    """字幕规范：一行 ≤ 16 字，一条 ≤ 32 字，按段落均匀切分。"""
    cues, idx = [], 1
    for b in beats:
        chunks = _chunks(b["voice"], 16)
        span = (b["end"] - b["start"]) / float(len(chunks))
        for j, ch in enumerate(chunks):
            st = b["start"] + span * j
            en = st + span
            cues.append(dict(index=idx, start=_srt_time(st), end=_srt_time(en),
                             text=ch, beat=b["beat"]))
            idx += 1
    return cues


def _srt_text(cues):
    out = []
    for c in cues:
        out.append("%d\n%s --> %s\n%s\n" % (c["index"], c["start"], c["end"], c["text"]))
    return "\n".join(out)


def build_plan(a):
    m = _meta(a)
    beats = _beat_rows(m)
    cues = _subtitle_cues(m, beats)
    shots = TEMPLATES[m["template"]]["shots"] if a.shots is None else int(a.shots)
    cost = item_cost(m["template"], a.resolution, shots)
    # 播报按稿子的实际字数结算，和 designChars 会有一点差
    spoken = sum(b["chars"] for b in beats)
    cost["chars"] = spoken
    cost["tts"] = _trim(spoken * TTS_PER_CHAR)
    cost["subtotal"] = _trim(cost["mix"] + cost["film"] + cost["tts"] + cost["img"])
    imgs = []
    for it in IMAGE_SETS[m["template"]]:
        imgs.append(dict(kind=it["kind"], name=it["name"], size=it["size"],
                         prompt=it["prompt"].format(**m)))
    base = _naming(m)
    naming = dict(video=base + ".mp4", cover=base + "_cover.png",
                  subtitle=base + ".srt", voice=base + "_voice.mp3",
                  copy=base + "_文案.md", delivery=base + "_交付单.md")
    return dict(
        version=VERSION, generatedAt=now_iso(), outdir=a.outdir or OUT_ROOT,
        meta=m, beats=beats, subtitles=cues, titles=_titles(m), tags=_tags(m),
        description=_description(m), images=imgs, naming=naming,
        copy={
            "titles": _titles(m), "description": _description(m), "tags": _tags(m),
            "sourceLine": "来源：%s（%s）" % (m["source"], m["aiLabel"]),
            "aiLabel": m["aiLabel"],
        },
        spec=dict(seconds=m["seconds"], ratio=m["ratio"], size=m["size"],
                  fps=25, codec="H.264", audio="AAC 44.1kHz",
                  subtitleLineChars=16, subtitleLines=2, subtitleMaxChars=32),
        cost=dict(template=m["template"], resolution=a.resolution,
                  mix=cost["mix"], film=cost["film"], tts=cost["tts"], img=cost["img"],
                  subtotal=cost["subtotal"], yuan=yuan(cost["subtotal"]),
                  chars=cost["chars"], images=cost["images"], seconds=cost["seconds"],
                  misc="配乐 50 点起/首（一天一条可复用）；采集参考 100 点/次",
                  shots=cost["shots"]),
    )


def cmd_plan(a, key, host):
    if a.template == "depth" and a.platform not in PLATFORMS:
        raise Fail("usage", "--platform 取 %s" % " / ".join(PLATFORM_KEYS), EXIT_USAGE)
    plan = build_plan(a)
    m = plan["meta"]
    if m["seconds"] > m["maxSeconds"]:
        raise Fail("usage", "%s 模板最长 %d 秒，%d 秒要拆片或换模板。"
                   % (m["templateName"], m["maxSeconds"], m["seconds"]), EXIT_USAGE)
    outdir = ensure_dir(a.outdir or os.path.join(OUT_ROOT, "%s-%s"
                                                % (m["template"], today())))
    plan["outdir"] = outdir
    json_path = os.path.join(outdir, "plan.json")
    write_text(json_path, json.dumps(plan, ensure_ascii=False, indent=1) + "\n")
    voice_path = write_text(os.path.join(outdir, "播报稿.md"), plan_voice_markdown(plan))
    copy_path = write_text(os.path.join(outdir, "文案.md"), plan_copy_markdown(plan))
    srt_path = write_text(os.path.join(outdir, plan["naming"]["subtitle"]),
                          _srt_text(plan["subtitles"]))
    deliver_path = write_text(os.path.join(outdir, plan["naming"]["delivery"]),
                              plan_delivery_markdown(plan))
    out = {"ok": True, "mode": "plan", "outdir": outdir, "planJson": json_path,
           "voice": voice_path, "copy": copy_path, "subtitle": srt_path,
           "delivery": deliver_path, "template": m["template"],
           "seconds": m["seconds"], "beats": len(plan["beats"]),
           "subtitles": len(plan["subtitles"]), "titles": plan["titles"],
           "estimatedPoints": plan["cost"]["subtotal"],
           "yuan": plan["cost"]["yuan"], "estimatedPointsTotal": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("一单的稿子写好了（0 点，纯本地）")
    print("  目录：%s" % outdir)
    print("  plan.json / 播报稿.md / 文案.md / %s" % plan["naming"]["subtitle"])
    print("  %s" % plan["naming"]["delivery"])
    print()
    print("  %-6s %-8s %-9s %s" % ("段", "时长", "起止", "播报"))
    print("  " + "-" * 96)
    for b in plan["beats"]:
        print("  %-6s %-8s %-9s %s" % (b["beat"], "%.1fs" % b["seconds"],
                                       "%.1f-%.1f" % (b["start"], b["end"]),
                                       b["voice"][:52]))
    print()
    print("  标题三条")
    for t in plan["titles"]:
        print("    · %s（%d 字）" % (t, len(t)))
    print("  标签：%s" % " ".join(plan["tags"]))
    print()
    print("  这条片的点数：%s 点 = %.2f 元（不含配乐）"
          % (fmt_pts(plan["cost"]["subtotal"], True), plan["cost"]["yuan"]))
    print("  下一步：python3 scripts/run.py qc --plan \"%s\"" % json_path)
    return 0


def plan_voice_markdown(plan):
    m = plan["meta"]
    lines = ["# 播报稿 · %s" % m["topic"], "",
             "> %s · %d 秒 · %s · %s" % (m["templateName"], m["seconds"],
                                         m["ratio"], m["size"]),
             "> 语速按 4.6~5.8 字/秒设计，数字前后各留一个空格，单位念全。", "",
             "| 段落 | 起止 | 秒 | 播报 | 字数 | 停顿 |",
             "|---|---|---|---|---|---|"]
    for b in plan["beats"]:
        lines.append("| %s | %.1f-%.1f | %.1f | %s | %d | %s |"
                     % (b["beat"], b["start"], b["end"], b["seconds"],
                        b["voice"], b["chars"], b["pause"]))
    total_chars = sum(b["chars"] for b in plan["beats"])
    lines += ["", "合计 %d 字 / %d 秒 = %.1f 字/秒。"
              % (total_chars, m["seconds"], total_chars / float(m["seconds"])), "",
              "## 画面提示", ""]
    for b in plan["beats"]:
        lines.append("- **%s**（%.1f-%.1f 秒）：%s"
                     % (b["beat"], b["start"], b["end"], b["visual"]))
    lines += ["", "## 念读要点", "",
              "- 标题段一口气念完，尾字收干净，做一个 0.3 秒的静场。",
              "- 数字前后各留一个空格，例如「多运 1.2 万人次」，TTS 断句更稳。",
              "- 来源段语速放慢半拍，把发布主体与通报时间念清楚。",
              "- 段与段之间停 0.4 秒，片尾定格 1 秒留给字幕板。", ""]
    return "\n".join(lines)


def plan_copy_markdown(plan):
    m = plan["meta"]
    lines = ["# 文案 · %s" % m["topic"], "", "## 标题（三选一）", ""]
    for i, t in enumerate(plan["titles"], 1):
        lines.append("%d. %s" % (i, t))
    lines += ["", "## 平台描述", "", plan["description"], "",
              "## 标签", "", " ".join(plan["tags"]), "",
              "## 来源与标注", "",
              "- 来源行：%s" % plan["copy"]["sourceLine"],
              "- 片尾字幕板：来源 %s + 通报时间 %s + %s"
              % (m["source"], m["when"], m["aiLabel"]),
              "- 口播收尾：以上信息来自%s%s" % (m["source"], SOURCE_TAIL), ""]
    return "\n".join(lines)


def plan_delivery_markdown(plan):
    m = plan["meta"]
    c = plan["cost"]
    imgs = plan["images"]
    lines = ["# 交付单 · %s" % m["topic"], "",
             "> %s · %s · %d 秒 · %s · %s"
             % (m["templateName"], m["platformName"], m["seconds"], m["ratio"], m["size"]), "",
             "## 一、交付清单", "",
             "| # | 交付物 | 规格 | 数量 | 命名 |", "|---|---|---|---|---|",
             "| 1 | 成片 | %s / H.264 / 25fps / %d 秒 / %s | 1 | `%s` |"
             % (m["size"], m["seconds"], m["ratio"], plan["naming"]["video"]),
             "| 2 | 封面图 | %s png | 1 | `%s` |" % (imgs[0]["size"],
                                                   plan["naming"]["cover"]),
             "| 3 | 配图 | %s png | %d | `%s_scene.png` 等 |"
             % (imgs[-1]["size"], len(imgs), _naming(m)),
             "| 4 | 播报音频 | mp3 / 44.1kHz / 单条 500 字内 | 1 | `%s` |"
             % plan["naming"]["voice"],
             "| 5 | 字幕 | SRT，一行 ≤ 16 字、一条 ≤ 32 字 | 1 | `%s` |"
             % plan["naming"]["subtitle"],
             "| 6 | 文案包 | 标题 3 条 + 描述 1 条 + 标签 6 个 + 来源行 | 1 | `%s` |"
             % plan["naming"]["copy"],
             "| 7 | 交付单 | 结构 / 成本 / 合规 / 命名 | 1 | `%s` |"
             % plan["naming"]["delivery"],
             "",
             "## 二、五段结构", "",
             "| 段 | 起止 | 画面 | 播报 |", "|---|---|---|---|"]
    for b in plan["beats"]:
        lines.append("| %s | %.1f-%.1f 秒 | %s | %s |"
                     % (b["beat"], b["start"], b["end"], b["visual"], b["voice"]))
    lines += ["", "## 三、配图 prompt（可直接喂 cover）", ""]
    for it in imgs:
        lines.append("- **%s**（%s，%s）：%s" % (it["name"], it["kind"], it["size"],
                                               it["prompt"]))
    lines += ["", "## 四、成本（1 元 = 100 点）", "",
              "| 项 | 点数 | 口径 |", "|---|---|---|",
              "| 新闻体混剪 | %s | 4.5 点/秒 x %d 秒 |"
              % (fmt_pts(c["mix"], True), m["seconds"]),
              "| 补镜头 | %s | full_video %s x %d 段 x 15 秒 |"
              % (fmt_pts(c["film"], True), c["resolution"], c["shots"]),
              "| 播报 | %s | 0.18 点/字 x %d 字 |"
              % (fmt_pts(c["tts"], True), c["chars"]),
              "| 配图 | %s | 6 点/张 x %d 张 |"
              % (fmt_pts(c["img"], True), c["images"]),
              "| **合计** | **%s 点 = %.2f 元** | 不含配乐与采集参考 |"
              % (fmt_pts(c["subtotal"], True), c["yuan"]), "",
              "## 五、合规四项", "",
              "- **来源标注**：口播念发布主体，画面挂来源字幕板，描述写「来源：%s」。" % m["source"],
              "- **事实口径**：数字带单位与时间，官方通报口径照抄，「以官方最新通报为准」收尾。",
              "- **AI 生成标注**：片尾字幕板写「%s」，混剪按 `watermarkShow` 打标。" % m["aiLabel"],
              "- **平台规范**：%s 上限 %d 秒，本条 %d 秒，字幕一行 ≤ 16 字。"
              % (m["platformName"], m["maxSeconds"], m["seconds"]), ""]
    return "\n".join(lines)


# ───────────────────────── 免费：qc（纯本地）─────────────────────────
def _scan(pat, texts, name, hint, checks):
    hit = []
    for t in texts:
        for m in pat.finditer(t or ""):
            hit.append(m.group(0))
    checks.append((name, not hit,
                   "命中了「%s」" % " / ".join(sorted(set(hit))[:5]) if hit else hint))


def _qc_word_checks(texts, checks):
    _scan(ABS_PAT, texts, "无绝对化用语",
          "换成可核对表述，例如「12.6 万人次，同比 3.2%」", checks)
    _scan(RUMOR_PAT, texts, "无传闻与猜测词",
          "用发布主体与时间代替传闻，例如「据 XX 通报」", checks)
    _scan(HYPE_PAT, texts, "无夸张与情绪词",
          "把情绪词换成现场动作，例如「站台排队到楼梯口」", checks)


def cmd_qc(a, key, host):
    checks = []
    if a.plan:
        if not os.path.isfile(a.plan):
            raise Fail("usage", "找不到 plan.json：%s" % a.plan, EXIT_USAGE)
        plan = json.load(io.open(a.plan, encoding="utf-8"))
        m = plan["meta"]
        voices = [b["voice"] for b in plan["beats"]]
        alltext = voices + [plan["description"]] + plan["titles"] + plan["tags"]
        checks.append(("来源标注写在口播与描述里",
                       m["source"] not in ("", "待填")
                       and any(m["source"] in v for v in voices)
                       and m["source"] in plan["description"],
                       "来源：%s" % m["source"]))
        checks.append(("时间 / 地点 / 主体三要素齐全",
                       all(m[k] not in ("", "待填") for k in ("when", "where", "subject")),
                       "%s · %s · %s" % (m["when"], m["where"], m["subject"])))
        checks.append(("关键数字带单位与时间",
                       bool(m["figure"]) or bool(re.search(r"\d", "".join(voices))),
                       m["figure"] or "口播里有数字"))
        checks.append(("AI 生成标注在描述与片尾",
                       bool(m["aiLabel"]) and m["aiLabel"] in plan["description"],
                       "标注：%s" % m["aiLabel"]))
        names = [b["beat"] for b in plan["beats"]]
        checks.append(("五段结构齐全（标题 3 秒 → 事件 → 背景 → 影响 → 来源）",
                       names == BEATS,
                       " / ".join(names)))
        total_chars = sum(b["chars"] for b in plan["beats"])
        rate = total_chars / float(max(1, m["seconds"]))
        checks.append(("播报语速在 %.1f~%.1f 字/秒" % (m["rateMin"], m["rateMax"]),
                       m["rateMin"] <= rate <= m["rateMax"],
                       "%d 字 / %d 秒 = %.1f 字/秒"
                       % (total_chars, m["seconds"], rate)))
        checks.append(("时长在模板上限内",
                       m["seconds"] <= m["maxSeconds"],
                       "%d 秒 / 上限 %d 秒" % (m["seconds"], m["maxSeconds"])))
        checks.append(("标题三条且每条 ≤ 20 字",
                       len(plan["titles"]) == 3
                       and all(len(t) <= 20 for t in plan["titles"]),
                       " / ".join("%s(%d 字)" % (t, len(t)) for t in plan["titles"])))
        checks.append(("字幕一行 ≤ 16 字",
                       all(len(c["text"]) <= 16 for c in plan["subtitles"]),
                       "%d 条字幕，最长 %d 字"
                       % (len(plan["subtitles"]),
                          max([len(c["text"]) for c in plan["subtitles"]] or [0]))))
        _qc_word_checks(alltext, checks)
        payload = {"ok": all(c[1] for c in checks), "mode": "plan",
                   "plan": a.plan, "topic": m["topic"],
                   "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
                   "estimatedPoints": 0}
    else:
        text = (a.text or "").strip()
        if not text:
            raise Fail("usage", "给 --plan plan.json 或 --text \"一条文案\"", EXIT_USAGE)
        _qc_word_checks([text], checks)
        checks.append(("文案长度在平台上限内",
                       len(text) <= (PLATFORMS[a.platform]["maxSeconds"] * 8),
                       "%d 字" % len(text)))
        checks.append(("有来源与 AI 标注",
                       ("来源" in text) and ("AI" in text or "辅助生成" in text),
                       "来源行 + AI 辅助生成"))
        payload = {"ok": all(c[1] for c in checks), "mode": "text",
                   "platform": a.platform,
                   "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
                   "estimatedPoints": 0}
    if a.json:
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload["ok"] else EXIT_GATE
    print("合规与结构检查（0 点，纯本地）")
    print()
    for c in payload["checks"]:
        print("  %s %s %s" % ("√" if c["ok"] else "×", pad(c["name"], 40), c["detail"]))
    bad = [c for c in payload["checks"] if not c["ok"]]
    print()
    if bad:
        print("  要改的地方：")
        for c in bad:
            print("    · %s —— %s" % (c["name"], c["detail"]))
        print()
        print("  改完重跑：python3 scripts/run.py qc --plan plan.json")
        return EXIT_GATE
    print("  全部通过，可以进下一步。本条片子的点数见交付单第四节。")
    return 0


# ───────────────────────── 采集参考（100 点/次）─────────────────────────
def cmd_hunt(a, key, host):
    api = HUNT_APIS[a.platform]
    kw = (a.keyword or "").strip()
    if not kw:
        raise Fail("usage", "给 --keyword \"搜索词\"（要查的那条新闻主体）", EXIT_USAGE)
    cost = HUNT_POINTS
    gate(a, cost, "采集 1 次 = 100 点/次（flat，8 个接口同价，失败亦计）")
    url = host + API_PREFIX + "/apps/" + APP_HUNT + "/" + api
    body = {"keyword": kw}
    if a.page:
        body["page"] = str(a.page)
    if a.platform == "xhs" and a.sort:
        body["sort"] = a.sort
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "api": api, "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不采集、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）—— 一次拿一页，与条数无关"
              % (cost, yuan(cost)))
        return 0

    say("正在采集参考（%s，100 点/次）…" % api)
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201) or (isinstance(d, dict) and d.get("code") == 0):
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "hunt", "api": api,
                    "http": st, "error": msg})
        raise Fail("call", "采集失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    items = find_item_list(d)
    rows = []
    for it in items[:a.top]:
        rows.append({"title": it.get("title") or it.get("desc") or it.get("note_title")
                     or it.get("caption") or "",
                     "author": it.get("author") or it.get("nickname")
                     or it.get("user_name") or "",
                     "likes": it.get("digg_count") or it.get("liked_count")
                     or it.get("likes") or "",
                     "url": it.get("url") or it.get("share_url")
                     or it.get("note_url") or ""})
    outdir = ensure_dir(a.outdir or os.path.join(OUT_ROOT, "hunt-%s" % today()))
    snap = write_text(os.path.join(outdir, "%s-%s.json" % (today(), api)),
                      json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    points = HUNT_POINTS
    ledger_add({"at": now_iso(), "ok": True, "mode": "hunt", "api": api,
                "keyword": kw, "items": len(items), "points": points})
    out = {"ok": True, "mode": "hunt", "api": api, "keyword": kw, "count": len(items),
           "items": rows, "snapshot": snap, "elapsed": round(dt, 1),
           "estimatedPoints": cost, "billedPoints": points, "yuan": yuan(points)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已采集（%.1fs，%d 点）" % (dt, points))
    print("  关键词：%s · 接口：%s · 返回 %d 条" % (kw, api, len(items)))
    print("  快照：%s" % snap)
    print()
    if rows:
        print("  %-3s %-42s %-14s %s" % ("#", "标题", "作者", "点赞"))
        print("  " + "-" * 78)
        for i, r in enumerate(rows, 1):
            print("  %-3s %-42s %-14s %s" % (i, str(r["title"])[:40],
                                             str(r["author"])[:12], r["likes"]))
        print()
    print("  参考用：只看结构与节奏，画面自己拍、自己核。")
    print("  一次 100 点，换个关键词就是新的一次，先想好词再发。")
    return 0


# ───────────────────────── 配图（6 点/张）─────────────────────────
def _save_image(outdir, prefix, idx, item):
    ensure_dir(outdir)
    b64 = item.get("b64_json") or item.get("b64") or item.get("image_base64")
    url = item.get("url") or item.get("image_url")
    path = os.path.join(outdir, "%s-%02d.png" % (prefix, idx))
    if b64:
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(b64))
        return path, None
    if url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                with open(path, "wb") as fh:
                    fh.write(r.read())
            return path, url
        except Exception:                                            # noqa: BLE001
            return None, url
    return None, None


def cmd_cover(a, key, host):
    tpl = TEMPLATES[a.template]
    m = dict(topic=(a.topic or "今日资讯").strip(),
             where=(a.where or "本市").strip(),
             subject=(a.subject or "相关部门").strip(),
             event=(a.event or "发布最新通报").strip(),
             when=(a.when or "今天").strip())
    all_imgs = IMAGE_SETS[a.template]
    if a.kind == "all":
        picked = all_imgs
    else:
        picked = [it for it in all_imgs if it["kind"] == a.kind]
        if not picked:
            raise Fail("usage", "--kind 取 all 或 %s"
                       % " / ".join([it["kind"] for it in all_imgs]), EXIT_USAGE)
    n = max(1, min(4, a.n))
    cost = IMG_POINTS * len(picked) * n
    gate(a, cost, "%d 张图 x 6 点/张（%s）"
         % (len(picked) * n, " / ".join([it["name"] for it in picked])))
    url = host + IMAGE_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url,
               "requestBody": {"model": APP_IMAGE, "n": n, "size": picked[0]["size"],
                               "prompt": picked[0]["prompt"].format(**m)},
               "kinds": [it["kind"] for it in picked], "requests": len(picked),
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不出图、不扣费）")
        print("  端点：POST %s" % url)
        print("  张数：%d 个图种 x 每组 %d 张 = %d 张" % (len(picked), n, len(picked) * n))
        for it in picked:
            print("  · %s：%s" % (it["name"], it["prompt"].format(**m)[:70]))
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    outdir = ensure_dir(a.outdir or os.path.join(OUT_ROOT, "%s-%s"
                                                % (a.template, today())))
    base = "%s_%s" % (today(), _slug(m["topic"]))
    files, urls, done = [], [], []
    for it in picked:
        prompt = it["prompt"].format(**m)
        body = {"model": APP_IMAGE, "prompt": prompt, "n": n,
                "size": it.get("size") or "1024x1536"}
        say("正在出「%s」（%d 张）…" % (it["name"], n))
        st, txt = http_json("POST", url, key, body, timeout=600)
        d = jloads(txt) or {}
        items = []
        if isinstance(d.get("data"), list):
            items = d["data"]
        elif isinstance(d.get("data"), dict) and isinstance(d["data"].get("data"), list):
            items = d["data"]["data"]
        if st not in (200, 201) or not items:
            msg = err_text(st, txt)
            ledger_add({"at": now_iso(), "ok": False, "mode": "cover",
                        "kind": it["kind"], "http": st, "error": msg})
            raise Fail("call", "出图失败（%s，HTTP %s）：%s"
                       % (it["kind"], st, msg), EXIT_CALL)
        for i, one in enumerate(items, 1):
            p, u = _save_image(outdir, "%s_%s" % (base, it["kind"]), i, one)
            if p:
                files.append(p)
            if u:
                urls.append(u)
        done.append({"kind": it["kind"], "name": it["name"], "returned": len(items),
                     "prompt": prompt})
    billed = IMG_POINTS * len(files)
    ledger_add({"at": now_iso(), "ok": True, "mode": "cover", "template": a.template,
                "kinds": [x["kind"] for x in done], "files": files, "points": billed})
    out = {"ok": True, "mode": "cover", "template": a.template, "kinds": done,
           "requested": len(picked) * n, "returned": len(files), "files": files,
           "urls": urls, "billedPoints": billed, "estimatedPoints": cost,
           "endpoint": IMAGE_PATH}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已出图（%d 张，%d 点）" % (len(files), billed))
    for x in done:
        print("  · %s：%d 张" % (x["name"], x["returned"]))
    for p in files:
        print("  文件：%s" % p)
    for u in urls:
        print("  链接：%s（约 3 小时有效，及时下载）" % u)
    print()
    print("  下一步：`mix --title \"...\" --material <封面图> --yes` 进混剪，")
    print("  图会先 upload（免费）换成白名单地址。")
    return 0


# ───────────────────────── 播报（约 0.18 点/字）─────────────────────────
def cmd_voice(a, key, host):
    text = (a.text or "").strip()
    if not text and a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "找不到播报稿：%s" % a.script, EXIT_USAGE)
        text = io.open(a.script, encoding="utf-8").read().strip()
    if not text:
        raise Fail("usage", "给 --text \"播报文案\" 或 --script 播报稿.md；"
                   "也可以先 `plan` 生成播报稿.md", EXIT_USAGE)
    if len(text) > TTS_MAX_CHARS:
        raise Fail("usage", "这条 %d 字，同步 tts 建议 %d 字内；超过就按段落拆成两三条。"
                   % (len(text), TTS_MAX_CHARS), EXIT_USAGE)
    cost = max(1, int(round(len(text) * TTS_PER_CHAR)))
    gate(a, cost, "播报 %d 字 x 0.18 点/字（上游真实点数 x 3，以 usage.points_cost 为准）"
         % len(text))
    url = host + API_PREFIX + "/apps/" + APP_TTS + "/tts"
    body = {"text": text, "model": a.tts_model, "format": a.tts_format}
    if a.reference_id:
        body["reference_id"] = a.reference_id
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "chars": len(text), "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不合成、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（约 %.2f 元）· %d 字" % (cost, yuan(cost), len(text)))
        return 0

    say("正在合成播报（%d 字）…" % len(text))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=300)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d) if isinstance(d, dict) else {}
    audio = data.get("audio_url") or data.get("audioUrl") or data.get("url")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("points_cost") or data.get("points_cost") or data.get("actual_points")
    if st not in (200, 201) or not audio:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "voice", "http": st,
                    "error": msg})
        raise Fail("call", "播报合成失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = ensure_dir(a.outdir or os.path.join(OUT_ROOT, "voice-%s" % today()))
    txt_path = write_text(os.path.join(outdir, "%s-voice.txt" % (a.prefix or "news")),
                          text + "\n")
    ledger_add({"at": now_iso(), "ok": True, "mode": "voice", "chars": len(text),
                "audio": audio, "points": real if real is not None else cost})
    out = {"ok": True, "mode": "voice", "audioUrl": audio, "chars": len(text),
           "elapsed": round(dt, 1), "textFile": txt_path,
           "billedPoints": real, "estimatedPoints": cost, "yuan": yuan(cost),
           "endpoint": API_PREFIX + "/apps/" + APP_TTS + "/tts"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已合成（%.1fs）" % dt)
    print("  音频：%s" % audio)
    print("  稿子：%s" % txt_path)
    if real is not None:
        print("  实际点数：%s（返回里的 usage.points_cost）" % fmt_pts(real))
    else:
        print("  预估点数：%d 点（约 %.2f 元）" % (cost, yuan(cost)))
    return 0


# ───────────────────────── 配乐（50 点起）─────────────────────────
def cmd_music(a, key, host):
    prompt = a.style or MUSIC_STYLE[a.mood]
    cost = MUSIC_FLOOR
    gate(a, cost, "配乐 1 首，通配保底 50 点（上游 x 2，以 usage.points_cost 为准）")
    url = host + API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate"
    body = {"model": a.music_model, "custom_mode": False,
            "instrumental": True, "prompt": prompt}
    if a.title:
        body["title"] = a.title
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不生成、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点起（%.2f 元起）" % (cost, yuan(cost)))
        return 0

    say("正在生成配乐…")
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=600)
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201) or (isinstance(d, dict) and d.get("code") == 0):
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "music", "http": st,
                    "error": msg})
        raise Fail("call", "配乐失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    data = payload_of(d)
    audio = find_media_url(data) or find_media_url(d)
    task_id = data.get("task_id") or data.get("taskId") or d.get("task_id")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("points_cost") or data.get("points_cost")
    out = {"ok": bool(audio or task_id), "mode": "music", "audioUrl": audio,
           "taskId": task_id, "elapsed": round(dt, 1), "style": prompt,
           "billedPoints": real, "estimatedPoints": cost, "yuan": yuan(cost)}
    ledger_add({"at": now_iso(), "ok": bool(audio or task_id), "mode": "music",
                "audio": audio, "taskId": task_id,
                "points": real if real is not None else cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if (audio or task_id) else EXIT_CALL
    if audio:
        print("已生成配乐（%.1fs）" % dt)
        print("  音频：%s" % audio)
    elif task_id:
        print("已提交配乐任务（%.1fs）" % dt)
        print("  任务：%s" % task_id)
        print("  查进度：python3 scripts/run.py status --task-id %s" % task_id)
    else:
        print("返回里没有音频地址，原始返回前 600 字：")
        print("  " + json.dumps(d, ensure_ascii=False)[:600])
        return EXIT_CALL
    print("  点数：%s" % (fmt_pts(real) if real is not None
                          else "%d 点起" % cost))
    return 0


# ───────────────────────── 上传（免费）─────────────────────────
def upload_file(key, host, path, timeout=600):
    if not path or not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    say("正在上传 %s（%d 字节，免费）…" % (os.path.basename(path), size))
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [("file", path)],
                             timeout=timeout)
    d = jloads(txt) or {}
    data = payload_of(d)
    got = data.get("url") or data.get("path") if isinstance(data, dict) else None
    if st not in (200, 201) or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    ok, kind = url_allowed(got)
    return {"url": got, "size": data.get("size") or size,
            "mime": data.get("mime_type"), "allowed": ok, "hostKind": kind}


def cmd_upload(a, key, host):
    if not a.file:
        raise Fail("usage", "必须给 --file（本地图片/视频路径）", EXIT_USAGE)
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": host + UPLOAD_PATH,
               "file": a.file, "estimatedPoints": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传、不扣费）")
        print("  端点：POST %s（multipart，字段名 file）" % (host + UPLOAD_PATH))
        print("  文件：%s" % a.file)
        return 0
    r = upload_file(key, host, a.file, timeout=a.timeout)
    out = {"ok": True, "url": r["url"], "size": r["size"], "mime": r["mime"],
           "urlAllowed": r["allowed"], "hostKind": r["hostKind"],
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（0 点）")
    print("  地址：%s" % r["url"])
    print("  归属：%s（在平台白名单内，可以直接给 film / mix 用）" % r["hostKind"])
    return 0


# ───────────────────────── 补镜头（按秒计费）─────────────────────────
def cmd_film(a, key, host):
    text = (a.text or "").strip()
    if not text:
        raise Fail("usage", "给 --text \"画面与运镜描述\"（把交付单里的画面提示粘过来）",
                   EXIT_USAGE)
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds))
    if seconds > VIDEO_CLIP_MAX:
        raise Fail("usage", "full_video 单段 4~15 秒；%d 秒分 %s 两段提交。"
                   % (seconds, "+".join(str(x) for x in clips_for(seconds))), EXIT_USAGE)
    ratio = a.ratio or (PLATFORMS[a.platform]["ratio"] if a.platform else "9:16")
    cost = video_points(seconds, a.resolution)
    gate(a, cost, "补镜头 %d 秒 x %d 点/秒（%s）"
         % (seconds, VIDEO_RATES[a.resolution], a.resolution))

    image_url = None
    if a.image:
        if a.image.startswith("http"):
            ok, kind = url_allowed(a.image)
            if not ok and not a.allow_any_url:
                raise Fail("usage",
                           "首帧图要在平台白名单内（%s 不在）。两种写法：\n"
                           "  · 本地图直接给路径：--image cover.png（自动 upload，免费）\n"
                           "  · 平台地址：https://oss.gpu.likeadmin.cn/openapi/…" % kind,
                           EXIT_USAGE)
            image_url = a.image
        elif not os.path.isfile(a.image):
            raise Fail("usage", "找不到首帧图：%s" % a.image, EXIT_USAGE)

    content = [{"type": "text", "text": text}]
    body = {"model": "full-video", "content": content, "duration": seconds,
            "resolution": a.resolution, "ratio": ratio, "aigc_watermark": True}
    if image_url:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})
    url = host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit"
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        if a.image and not image_url:
            print("  首帧：%s（会先用 upload 换白名单地址，免费）" % a.image)
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    if a.image and not image_url:
        r = upload_file(key, host, a.image, timeout=a.timeout)
        image_url = r["url"]
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})

    say("正在提交补镜头（%s，%d 秒）…" % (a.resolution, seconds))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=180)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d)
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "film", "http": st,
                    "error": msg, "seconds": seconds})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    out = {"ok": True, "mode": "film", "taskId": task_id, "status": data.get("status"),
           "resolution": a.resolution, "seconds": seconds, "ratio": ratio,
           "firstFrame": image_url, "elapsed": round(dt, 1),
           "estimatedPoints": cost,
           "billedPoints": usage.get("points_cost") or data.get("points_cost")}
    ledger_add({"at": now_iso(), "ok": True, "mode": "film", "taskId": task_id,
                "seconds": seconds, "resolution": a.resolution, "points": cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：%s · %d 秒 · %s" % (a.resolution, seconds, ratio))
    if image_url:
        print("  首帧：%s" % image_url)
    print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 新闻体混剪（4.5 点/秒）─────────────────────────
def _aic_metadata(producer="三剪客 api.a7w.cn"):
    return json.dumps({"Label": "1", "ContentProducer": producer,
                       "ProduceID": "NS%s" % time.strftime("%Y%m%d%H%M%S")},
                      ensure_ascii=False)


def cmd_mix(a, key, host):
    title = (a.title or "").strip()
    if not title:
        raise Fail("usage", "给 --title \"标题\"（3~1800 字，快讯标题建议 20 字内）",
                   EXIT_USAGE)
    if len(title) < 3 or len(title) > 1800:
        raise Fail("usage", "标题 %d 字，接口要求 3~1800 字。" % len(title), EXIT_USAGE)
    mats = [x for x in (a.material or []) if x]
    if not mats:
        raise Fail("usage", "给至少一个 --material（本地图片/视频路径，或平台地址）；"
                   "可以重复给多个", EXIT_USAGE)
    seconds = int(a.seconds) if a.seconds else TEMPLATES[a.template]["seconds"]
    if seconds < 5 or seconds > 300:
        raise Fail("usage", "news_mixcut 的 videoDuration 是 5~300 秒，%d 秒越界。"
                   % seconds, EXIT_USAGE)
    cost = int(round(MIX_PER_SEC * seconds))
    gate(a, cost, "新闻体混剪 %d 秒 x 4.5 点/秒（smart_clip/* perSecond）" % seconds)

    items, need_upload = [], []
    for p in mats:
        if p.startswith("http"):
            ok, kind = url_allowed(p)
            if not ok and not a.allow_any_url:
                raise Fail("usage",
                           "素材要在平台白名单内（%s 不在）。两种写法：\n"
                           "  · 本地文件直接给路径：--material cover.png（自动 upload，免费）\n"
                           "  · 平台地址：https://oss.gpu.likeadmin.cn/openapi/…" % kind,
                           EXIT_USAGE)
            kindv = "video" if re.search(r"\.(mp4|mov)(\?|$)", p, re.I) else "image"
            items.append({"type": kindv, "fileUrl": p, "soundSwitch": False})
        else:
            if not os.path.isfile(p):
                raise Fail("usage", "找不到素材：%s" % p, EXIT_USAGE)
            need_upload.append(p)

    style = a.style_id or DEFAULT_STYLE_ID
    body = {
        "styleId": style,
        "title": title,
        "materials": items or [{"type": "image", "fileUrl": "<upload 后填>",
                                "soundSwitch": False}],
        "processRules": {"watermarkShow": True, "videoDuration": seconds,
                         "materialComposition": a.composition,
                         "metadata": {"AIGC": _aic_metadata()}},
        "packRules": {"headerSwitch": True, "materialSwitch": True,
                      "subtitleSwitch": True, "keywordSwitch": True,
                      "backgroundMusic": {"audioSwitch": bool(a.bgm),
                                          "audioUrl": a.bgm or "<bgm.mp3 的地址>",
                                          "volume": 0.3}},
        "introduceCard": {"name": a.reporter or "三剪客资讯",
                          "description": a.column or "每日资讯精选"},
    }
    url = host + MIX_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "pendingUpload": need_upload, "estimatedPoints": cost,
               "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False)[:700])
        for p in need_upload:
            print("  待上传：%s（先 POST /upload 换白名单地址，免费）" % p)
        print("  预估：%d 点（%.2f 元）· %d 秒 x 4.5 点/秒"
              % (cost, yuan(cost), seconds))
        return 0

    uploaded = []
    for p in need_upload:
        r = upload_file(key, host, p, timeout=a.timeout)
        kindv = "video" if re.search(r"\.(mp4|mov)$", p, re.I) else "image"
        items.append({"type": kindv, "fileUrl": r["url"], "soundSwitch": False})
        uploaded.append(r["url"])
    body["materials"] = items
    if not a.bgm:
        body["packRules"]["backgroundMusic"] = {"audioSwitch": False}

    say("正在提交新闻体混剪（%d 秒，%d 个素材）…" % (seconds, len(items)))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=300)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d)
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or d.get("task_id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "mix", "http": st,
                    "error": msg, "seconds": seconds})
        raise Fail("call", "混剪提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    out = {"ok": True, "mode": "mix", "taskId": task_id, "status": data.get("status"),
           "seconds": seconds, "materials": len(items), "uploaded": uploaded,
           "styleId": style, "watermarkShow": True, "elapsed": round(dt, 1),
           "estimatedPoints": cost,
           "billedPoints": usage.get("points_cost") or data.get("points_cost")}
    ledger_add({"at": now_iso(), "ok": True, "mode": "mix", "taskId": task_id,
                "seconds": seconds, "materials": len(items), "points": cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：%d 秒 · %d 个素材 · 模板 %s" % (seconds, len(items), style))
    print("  标注：watermarkShow=true（画面挂 AI 生成字样）+ metadata.AIGC")
    for u in uploaded:
        print("  已上传：%s" % u)
    print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 查任务（免费）─────────────────────────
def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    path = API_PREFIX + "/tasks/" + a.task_id
    st, txt = http_json("GET", host + path, key, timeout=40)
    d = jloads(txt) or {}
    out = {"ok": True, "taskId": a.task_id, "path": path, "http": st,
           "status": None, "result": None, "estimatedPoints": 0}
    if st == 200 and d.get("code") == 0 and not d.get("data"):
        out.update({"status": "not_found", "message": d.get("msg") or "任务不存在"})
    elif st == 200:
        data = payload_of(d) if isinstance(d, dict) else {}
        data = data if isinstance(data, dict) else {}
        out.update({"status": data.get("status"), "message": data.get("message"),
                    "videoUrl": data.get("video_url") or data.get("videoUrl"),
                    "coverUrl": data.get("cover_url"), "cost": data.get("cost"),
                    "refund": data.get("refund"), "result": data.get("result")})
    else:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  查询端点：GET %s（0 点）" % path)
    print("  状态：%s" % out.get("status"))
    if out.get("message"):
        print("  说明：%s" % str(out["message"])[:200])
    if out.get("cost") is not None:
        print("  实扣：%s 点" % fmt_pts(out["cost"]))
    if out.get("refund") is not None:
        print("  退回：%s 点" % fmt_pts(out["refund"]))
    if out.get("videoUrl"):
        print("  成片：%s（及时转存）" % out["videoUrl"])
    if out.get("coverUrl"):
        print("  封面：%s" % out["coverUrl"])
    if out.get("result") is not None:
        print("  结果：%s" % json.dumps(out["result"], ensure_ascii=False)[:600])
    return 0


# ───────────────────────── 自检（0 点）─────────────────────────
def _last_log(key, host):
    st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d = jloads(txt) or {}
    logs = d.get("logs") or []
    if not logs:
        return None
    row = logs[0]
    return (row.get("at"), row.get("points"), row.get("reference"))


def cmd_doctor(a, key, host):
    checks = []
    first0 = _last_log(key, host)

    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("Key + 余额接口可达", st == 200 and "available_points" in d,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点"
                   % (st, fmt_pts(d.get("available_points") or 0),
                      fmt_pts(d.get("frozen") or 0))))

    st2, txt2 = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d2 = jloads(txt2) or {}
    listing = d2.get("data") if isinstance(d2.get("data"), list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    need = [APP_VIDEO, APP_TTS, APP_MUSIC, APP_CLIP, APP_HUNT]
    miss = [c for c in need if c not in online]
    checks.append(("5 个底层应用在架（成片 / 播报 / 配乐 / 混剪 / 采集）",
                   bool(listing) and not miss,
                   "目录 %d 个应用%s" % (len(listing),
                                        "，缺 " + ",".join(miss) if miss else "")))
    counts = {c: len((online.get(c) or {}).get("apis") or []) for c in need}
    ok_counts = (counts[APP_MUSIC] == 29 and counts[APP_CLIP] == 5
                 and counts[APP_HUNT] == 8)
    checks.append(("接口数齐全（配乐 29 / 混剪 5 / 采集 8）", ok_counts,
                   "media_services_33 %d · smart_clip %d · watermark_removal %d"
                   % (counts[APP_MUSIC], counts[APP_CLIP], counts[APP_HUNT])))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt3) or {}).get("pricing") or {}
    vrule = pricing.get(API_PREFIX + "/apps/full_video/submit") or {}
    live = vrule.get("resolutionRates") or {}
    drift = ["%s 本地 %d / 线上 %s" % (r, p, live.get(r))
             for r, p in VIDEO_RATES.items() if int(live.get(r) or -1) != p]
    checks.append(("full_video 5 档按秒价与线上一致",
                   st3 == 200 and bool(live) and not drift,
                   "HTTP %s · %s" % (st3, "5 档全一致" if not drift
                                     else " / ".join(drift)[:110])))

    clip = pricing.get(API_PREFIX + "/apps/smart_clip/*") or {}
    per_sec = float(clip.get("perSecond") or 0)
    checks.append(("smart_clip 4.5 点/秒与线上一致",
                   st3 == 200 and abs(per_sec - MIX_PER_SEC) < 1e-6,
                   "perSecond %s · estimate %s" % (clip.get("perSecond"),
                                                   clip.get("estimate"))))

    hunt = pricing.get(API_PREFIX + "/apps/watermark_removal/*") or {}
    tts = pricing.get(API_PREFIX + "/apps/voice_tts/*") or {}
    wild = pricing.get("*") or {}
    up_rule = pricing.get(API_PREFIX + "/upload") or {}
    ok_price = (int(hunt.get("cost") or 0) == HUNT_POINTS
                and int(tts.get("markupPercent") or 0) == 200
                and int(wild.get("minPoints") or 0) == MUSIC_FLOOR
                and int(up_rule.get("cost") if up_rule.get("cost") is not None
                        else 999) == 0)
    checks.append(("采集 100 点/次 + 播报 x3 + 配乐保底 50 + upload 0 点", ok_price,
                   "采集 %s · 播报 markup %s%% · 通配保底 %s · upload %s"
                   % (hunt.get("cost"), tts.get("markupPercent"),
                      wild.get("minPoints"), up_rule.get("cost"))))

    st4, txt4 = http_json("POST", host + IMAGE_PATH, key,
                          {"model": APP_IMAGE, "prompt": ""}, timeout=60)
    d4 = jloads(txt4) or {}
    e4 = d4.get("error") if isinstance(d4.get("error"), dict) else {}
    msg4 = (e4.get("message") or err_text(st4, txt4))
    checks.append(("出图端点可用（422 即正确，零扣费）",
                   st4 == 422 and "prompt" in str(msg4).lower(),
                   "HTTP %s %s" % (st4, str(msg4)[:52])))

    st5, txt5 = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-ns-doctor-probe",
                          key, timeout=40)
    d5 = jloads(txt5) or {}
    checks.append(("任务查询 GET /tasks/<id> 可用（假 id 说任务不存在）",
                   st5 == 200 and d5.get("code") == 0,
                   "HTTP %s %s" % (st5, (d5.get("msg") or "")[:40])))

    st6, txt6 = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=60)
    d6 = jloads(txt6) or {}
    checks.append(("上传口 POST /upload 可用（缺 file 时提示补字段）",
                   st6 == 200 and d6.get("code") == 0,
                   "HTTP %s %s" % (st6, (d6.get("msg") or "")[:40])))

    last = _last_log(key, host)
    checks.append(("本轮没有新增流水（扣 0 点）", first0 == last,
                   "自检前后最新一笔流水一致" if first0 == last
                   else "出现新流水，请发出来排查"))

    out = {"ok": all(c[1] for c in checks), "requests": 10,
           "estimatedPoints": 0, "yuan": 0.0, "apps": need,
           "apiCounts": counts, "videoRates": live or VIDEO_RATES,
           "mixPerSecond": clip.get("perSecond"), "huntPoints": hunt.get("cost"),
           "endpoints": {"hunt": host + API_PREFIX + "/apps/" + APP_HUNT
                         + "/douyin_search_video",
                         "image": host + IMAGE_PATH,
                         "tts": host + API_PREFIX + "/apps/" + APP_TTS + "/tts",
                         "music": host + API_PREFIX + "/apps/" + APP_MUSIC
                         + "/music_generate",
                         "film": host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit",
                         "mix": host + MIX_PATH,
                         "upload": host + UPLOAD_PATH,
                         "task": host + API_PREFIX + "/tasks/<task_id>"},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（2 个目录 / 价目只读 GET + 1 个空 prompt 422 + 1 个假 id 查询 + "
          "1 个缺 file 上传，全部停在扣费之前）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 52), dt))
    print()
    print("  本次自检 0 点、0 冻结：10 个请求里没有一条会建任务。")
    print("  采集类接口（watermark_removal）失败亦计，所以自检一次都不发它。")
    print()
    print("  端点：POST /apps/smart_clip/news_mixcut（混剪 4.5 点/秒）")
    print("        POST /apps/full_video/submit（补镜头）· /images/generations（配图）")
    print("        POST /apps/voice_tts/tts（播报）· /apps/media_services_33/music_generate（配乐）")
    print("  查询：GET /api/v1/tasks/<task_id>（0 点；应用层 /query 每次都是钱）")
    return 0 if out["ok"] else EXIT_GATE


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
        mode = e.get("mode") or "-"
        what = e.get("taskId") or e.get("audio") or e.get("error") or e.get("api") or "-"
        pts = e.get("points")
        print("  %s  %-5s %-6s %-34s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", mode,
            str(what)[:34], ("%s 点" % fmt_pts(pts)) if pts is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def add_story_args(p, with_out=True):
    p.add_argument("--template", choices=TEMPLATE_KEYS, default="flash",
                   help="flash 快讯 30 秒 / depth 深度 90 秒（默认 flash）")
    p.add_argument("--platform", choices=PLATFORM_KEYS, default="douyin",
                   help="发布平台（默认 douyin）")
    p.add_argument("--topic", help="新闻标题 / 主体一句话")
    p.add_argument("--when", default="今天上午", help="事件时间（默认 今天上午）")
    p.add_argument("--where", default="本市", help="地点（默认 本市）")
    p.add_argument("--subject", default="相关部门", help="发布主体（默认 相关部门）")
    p.add_argument("--event", default="发布最新通报", help="动作 / 事件（默认 发布最新通报）")
    p.add_argument("--figure", default="", help="关键数字，例如「日均多运 1.2 万人次」")
    p.add_argument("--background", default="", help="背景一段（默认给一句通用背景）")
    p.add_argument("--impact", default="", help="影响一段（默认给一句通用影响）")
    p.add_argument("--source", default="待填", help="来源单位，例如「市地铁集团通报」")
    p.add_argument("--quote", default="", help="官方原话一句（可选）")
    p.add_argument("--ai-label", dest="ai_label", default=AI_LABEL_DEFAULT,
                   help="AI 生成标注文案（默认 %s）" % AI_LABEL_DEFAULT)
    p.add_argument("--reporter", default="", help="记者 / 栏目署名（可选）")
    p.add_argument("--seconds", type=int, default=0, help="覆盖模板秒数（默认按模板）")
    p.add_argument("--ratio", choices=RATIOS, default=None, help="画幅（默认按模板 / 平台）")
    p.add_argument("--size", default=None, help="尺寸（默认按模板）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="报价用的分辨率（默认 1080P）")
    p.add_argument("--shots", type=int, default=None,
                   help="补镜头段数（默认快讯 0 段、深度 1 段；每段 15 秒）")
    if with_out:
        p.add_argument("--outdir", help="输出目录（默认 ~/.a7w/news-shorts/<模板>-<日期>）")


def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 新闻资讯短视频（媒体号快讯 / 深度，走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/apps/smart_clip/news_mixcut · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/images/generations · "
               "POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/media_services_33/music_generate · "
               "GET %s/api/v1/tasks/<task_id> · POST %s/api/v1/upload"
               % ((DEFAULT_HOST,) * 7),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 60 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="六道工序 + 端点 + 单价 + 模板 + 平台（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一条快讯 / 一条深度 / 一天要多少钱（免费）",
                       allow_abbrev=False)
    p.add_argument("--flash", type=int, default=8, help="一天几条快讯（默认 8）")
    p.add_argument("--depth", type=int, default=2, help="一天几条深度（默认 2）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="补镜头分辨率（默认 1080P）")
    p.add_argument("--shots", type=int, default=None,
                   help="补镜头段数（默认快讯 0、深度 1；每段 15 秒）")
    p.add_argument("--bgm", type=int, default=1, choices=[0, 1],
                   help="配乐 1 首（默认 1，一天可复用）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="一单的播报稿 / 字幕 / 文案 / 交付单（免费，纯本地）",
                       allow_abbrev=False)
    add_story_args(p)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("qc", help="合规与结构检查（免费，纯本地）", allow_abbrev=False)
    p.add_argument("--plan", help="plan.json 路径")
    p.add_argument("--text", help="直接检查一条文案")
    p.add_argument("--platform", choices=PLATFORM_KEYS, default="douyin",
                   help="--text 模式下的平台（默认 douyin）")
    p.set_defaults(fn=cmd_qc)

    p = sub.add_parser("hunt", help="找热点素材参考（100 点/次，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--platform", choices=["dy", "xhs"], default="dy",
                   help="dy 抖音 / xhs 小红书（默认 dy）")
    p.add_argument("--keyword", help="搜索词")
    p.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    p.add_argument("--sort", default=None,
                   help="xhs 排序：general / popularity_descending / time_descending")
    p.add_argument("--top", type=int, default=10, help="显示前几条（默认 10）")
    p.add_argument("--timeout", type=int, default=120, help="超时秒数（默认 120）")
    p.add_argument("--outdir", help="快照目录（默认 ~/.a7w/news-shorts/hunt-<日期>）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_hunt)

    p = sub.add_parser("cover", help="配图（6 点/张，要 --yes）", allow_abbrev=False)
    p.add_argument("--kind", default="all",
                   help="all / cover / scene / chart / people / timeline / ending（默认 all）")
    p.add_argument("--n", type=int, default=1, help="每个图种出几张 1~4（默认 1）")
    p.add_argument("--topic", default="今日资讯", help="主题（进 prompt）")
    p.add_argument("--where", default="本市", help="地点（进 prompt）")
    p.add_argument("--subject", default="相关部门", help="主体（进 prompt）")
    p.add_argument("--event", default="发布最新通报", help="事件（进 prompt）")
    p.add_argument("--when", default="今天", help="时间（进 prompt）")
    p.add_argument("--template", choices=TEMPLATE_KEYS, default="flash",
                   help="flash 3 张 / depth 6 张（默认 flash）")
    p.add_argument("--outdir", help="输出目录（默认 ~/.a7w/news-shorts/<模板>-<日期>）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_cover)

    p = sub.add_parser("voice", help="播报（约 0.18 点/字，要 --yes）", allow_abbrev=False)
    p.add_argument("--text", help="播报文案（500 字内）")
    p.add_argument("--script", help="从文本文件读播报稿")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro", help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3",
                   help="mp3 / wav / opus")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色 ID（可选）")
    p.add_argument("--prefix", default="news", help="稿子文件名前缀")
    p.add_argument("--outdir", help="稿子目录（默认 ~/.a7w/news-shorts/voice-<日期>）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="配乐（50 点起/首，要 --yes）", allow_abbrev=False)
    p.add_argument("--style", help="风格描述，例如「新闻快讯片头，短促鼓点」")
    p.add_argument("--title", help="曲名（可选）")
    p.add_argument("--mood", choices=["flash", "depth"], default="flash",
                   help="按模板选默认风格（默认 flash）")
    p.add_argument("--music-model", dest="music_model", default=MUSIC_MODEL,
                   help="Suno 模型（默认 %s）" % MUSIC_MODEL)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_music)

    p = sub.add_parser("film", help="补镜头 / 生成镜头（按秒计费，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--text", help="画面与运镜描述（把交付单里的画面提示粘过来）")
    p.add_argument("--image", help="首帧图：本地路径（自动上传）或平台地址")
    p.add_argument("--seconds", type=int, default=15, help="单段秒数 4~15（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--ratio", choices=RATIOS, default=None, help="画幅（默认 9:16）")
    p.add_argument("--platform", choices=PLATFORM_KEYS, help="按平台取默认画幅（可选）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把地址交给上游判断")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_film)

    p = sub.add_parser("mix", help="新闻体混剪（4.5 点/秒，要 --yes）", allow_abbrev=False)
    p.add_argument("--title", help="标题（3~1800 字，快讯 20 字内）")
    p.add_argument("--material", action="append",
                   help="素材：本地图片/视频路径或平台地址；可重复给")
    p.add_argument("--template", choices=TEMPLATE_KEYS, default="flash",
                   help="按模板取默认秒数（默认 flash 30 秒）")
    p.add_argument("--seconds", type=int, default=0, help="成片秒数 5~300（默认按模板）")
    p.add_argument("--style-id", dest="style_id", default=None,
                   help="模板 ID（默认 %s，来自 smart_clip/template）" % DEFAULT_STYLE_ID)
    p.add_argument("--composition", choices=["random", "order"], default="order",
                   help="素材组合方式（默认 order 按顺序）")
    p.add_argument("--bgm", default=None, help="背景音乐地址（可选，给了才开音乐）")
    p.add_argument("--reporter", default="", help="身份栏名称（默认 三剪客资讯）")
    p.add_argument("--column", default="", help="身份栏描述（默认 每日资讯精选）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把地址交给上游判断")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_mix)

    p = sub.add_parser("upload", help="上传素材，拿白名单地址（免费）", allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("status", help="查任务进度（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 task_id")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 价目 / 端点（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_qc", "cmd_log")
LOCAL_ONLY = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_qc", "cmd_log")


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
        if not key and fn_name not in LOCAL_ONLY:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                       EXIT_USAGE)
        return a.fn(a, key or "", host)
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
    except Exception:                                                # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
