#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 游戏宣发（sanjianke-game-promo）

游戏上线期的素材生产台：把「预约期 / 上线期 / 长线运营」三个节奏点，按岗位真实交付
拆成 6 类素材、5 个平台、5 个语种，先在本地排矩阵，再决定哪几条值得花钱。

## 本包用的 6 条能力（单价 2026-11-08 现查 /api/v1/pricing + 流水实测）

  出图      gpt-image-2.6      POST /api/v1/images/generations       6 点/张
  改图      gpt-image-2.6      POST /api/v1/images/edits             6 点/张
  买量片    full_video         POST /api/v1/apps/full_video/submit   1080P 60 点/秒（15 秒 900 点）
  预告片    seedance           POST /api/v1/apps/seedance/create     11,000 点/次（flat）
  素材托管  seedance           createGroup / createAsset / getAsset / updateAsset / deleteAsset
  多语言配音 voice_tts          POST /api/v1/apps/voice_tts/tts       约 0.18 点/字
  宣发配乐  media_services_33  POST /api/v1/apps/media_services_33/music_generate  50 点起/首
  查进度    GET /api/v1/tasks/<task_id>                              0 点
  传文件    POST /api/v1/upload                                      0 点

## 三条用钱换来的口径（都做成了默认动作）

  1. 轮询只走 GET /tasks/<id>（0 点）。seedance/query 落 /apps/seedance/* = 11,000 点/次，
     本包 --action query 直接转成 status，一次 0 点。
  2. 目录只读 GET /api/v1/apps 与 /api/v1/pricing。GET /api/v1/apps/<app> 命中通配计价、
     即时扣费不退，本包一次都不打。
  3. 首帧图 / 参考图只认本站托管地址（vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、
     oss.gpu.likeadmin.cn/openapi/），本地图先 POST /upload（免费）换地址。

## 子命令

  catalog  6 类素材 + 3 个节奏点 + 5 个平台规格 + 现查单价（免费）
  cost     一个上线期素材包多少钱，四种走法对比（免费）
  plan     宣发矩阵、多语言文案、命名、交付清单、排期（免费，纯本地）
  qc       交付前九道检查（免费，纯本地）
  img      主视觉 / 角色立绘 / 商店五图 / 战报图，6 点/张（要 --yes）
  film     15 秒买量片 / 30 秒品牌片，60 点/秒（要 --yes）
  seedance 预告片 create + 5 个素材托管接口 + query（要 --yes）
  voice    多语言配音，约 0.18 点/字（要 --yes）
  music    宣发配乐，50 点起（要 --yes）
  upload   上传本地素材，换白名单地址（免费）
  status   查任务进度，只走 GET /tasks/<id>（免费）
  doctor   自检 Key / 应用 / 价目 / 端点（免费，不扣费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --phase T1 --locales 2
  python3 scripts/run.py plan --game "代号：山海" --code GL01 --phase T1 --locale zh-CN --locale en-US
  python3 scripts/run.py qc --plan ~/.a7w/game-promo/20261108/plan.json
  python3 scripts/run.py img --asset kv --size 16x9 --locale zh-CN --yes
  python3 scripts/run.py film --asset ad15 --seconds 15 --image kv.png --yes
  python3 scripts/run.py seedance --action create --text "角色大招定格" --budget 12000 --yes
  python3 scripts/run.py voice --text "今日公测，登录领限定角色" --yes
  python3 scripts/run.py status --task-id tsk_xxx

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import base64
import datetime
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

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "game-promo")
LEDGER = os.path.join(HOME_DIR, "ledger.json")
OUT_ROOT = os.path.join(HOME_DIR, "out")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-game-promo/%s" % VERSION

# ── 6 条能力（单价：GET /api/v1/pricing 与流水实测，2026-11-08）───────────────
APP_IMAGE = "gpt-image-2.6"
IMG_POINTS = 6                        # 点/张，与尺寸 / 质量 / 格式无关
IMAGE_PATH = API_PREFIX + "/images/generations"
EDIT_PATH = API_PREFIX + "/images/edits"

APP_VIDEO = "full_video"
VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}   # 点/秒
VIDEO_CLIP_MIN, VIDEO_CLIP_MAX = 4, 15

APP_SEEDANCE = "seedance"
SEEDANCE_POINTS = 11000               # 点/次，flat（价目表 /apps/seedance/* cost 11000）
SEEDANCE_MODEL = "seedance-2-text-2-video"

APP_TTS = "voice_tts"
TTS_PER_CHAR = 0.18                   # 点/字（上游真实点数 x 3）
TTS_MAX_CHARS = 500

APP_MUSIC = "media_services_33"
MUSIC_FLOOR = 50                      # 点/首（落通配：上游 x 2、保底 50）
MUSIC_MODEL = "V6"

UPLOAD_PATH = API_PREFIX + "/upload"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 8000                 # 点 = 80 元，一个上线期素材包的默认上限

RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]

# ── 五个平台规格（上架尺寸按各平台现行要求换算，请求尺寸守住 gpt-image 四条）──
PLATFORMS = {
    "taptap": dict(name="TapTap", sizes=["9x16", "3x4"],
                   note="预约页头图 9:16、详情页竖版 3:4、论坛活动图",
                   spec="截图 1080x1920 / 详情竖图 1242x1660"),
    "bilibili": dict(name="B站", sizes=["16x9", "3x4", "1x1"],
                     note="视频封面 16:9、动态图 3:4、UP 主头像 1:1",
                     spec="封面 1920x1080 / 动态 1242x1660 / 头像 1080x1080"),
    "douyin": dict(name="抖音", sizes=["9x16", "1x1"],
                   note="买量片 9:16、直播预约 1:1、星图任务",
                   spec="竖版 1080x1920 / 方图 1080x1080"),
    "steam": dict(name="Steam", sizes=["16x9", "1x1"],
                  note="商店页头图 16:9、库页胶囊 1:1、活动图",
                  spec="头图 1920x1080 / 胶囊 1080x1080"),
    "wechat": dict(name="微信小游戏", sizes=["9x16", "1x1"],
                   note="小游戏入口 9:16、朋友圈 1:1",
                   spec="入口 1080x1920 / 方图 1080x1080"),
}
PLATFORM_ORDER = ["taptap", "bilibili", "douyin", "steam", "wechat"]

# ── 五档尺寸（请求值都满足 gpt-image 的 16 倍数 / 3:1 / 像素区间）─────────────
SIZES = {
    "9x16": dict(ratio="9:16", req="720x1280", publish="1080x1920",
                 safe="上 12% 放活动角标，下 18% 留下载按钮位"),
    "16x9": dict(ratio="16:9", req="1280x720", publish="1920x1080",
                 safe="主体居中，左侧 1/4 留给主标"),
    "1x1": dict(ratio="1:1", req="1024x1024", publish="1080x1080",
                safe="主体居中，四角各留 10% 放分级标识"),
    "3x4": dict(ratio="3:4", req="1152x1536", publish="1242x1660",
                safe="上 1/3 放角色名，底部 15% 留白"),
    "4x5": dict(ratio="4:5", req="1024x1280", publish="1080x1350",
                safe="中心构图，上下各留 10%"),
}
SIZE_ORDER = ["9x16", "16x9", "1x1", "3x4", "4x5"]

# ── 五个语种：多语言版本按这套 CTA 与标签出，命名里带 locale ──────────────────
LOCALES = {
    "zh-CN": dict(name="简体中文", short="简中",
                  cta={"T0": "立即预约", "T1": "立即下载", "T2": "更新版本"},
                  stage={"T0": "预约中", "T1": "今日公测", "T2": "版本更新"}),
    "zh-TW": dict(name="繁体中文", short="繁中",
                  cta={"T0": "立即預約", "T1": "立即下載", "T2": "更新版本"},
                  stage={"T0": "預約中", "T1": "今日公測", "T2": "版本更新"}),
    "en-US": dict(name="英文", short="英文",
                  cta={"T0": "Pre-register now", "T1": "Play free now",
                       "T2": "Update now"},
                  stage={"T0": "Pre-registration", "T1": "Out now",
                         "T2": "New update"}),
    "ja-JP": dict(name="日文", short="日文",
                  cta={"T0": "事前登録はこちら", "T1": "今すぐプレイ",
                       "T2": "アップデート"},
                  stage={"T0": "事前登録中", "T1": "正式リリース",
                         "T2": "アップデート"}),
    "ko-KR": dict(name="韩文", short="韩文",
                  cta={"T0": "사전예약 하기", "T1": "지금 플레이",
                       "T2": "업데이트"},
                  stage={"T0": "사전예약 중", "T1": "정식 출시",
                         "T2": "업데이트"}),
}
LOCALE_ORDER = ["zh-CN", "zh-TW", "en-US", "ja-JP", "ko-KR"]

# ── 六类素材：每类自带交付口径（平台 x 尺寸 x 张数 / 秒数）─────────────────────
ASSETS = {
    "kv": dict(tag="KV", name="主视觉", kind="image", unit="张",
               blueprint=[("taptap", "9x16", 1), ("bilibili", "16x9", 1),
                          ("steam", "16x9", 1)],
               role="预约页头图 / 视频首帧 / 商店首图",
               scene="主角与世界观同框，天空与光效做情绪，构图留主标位"),
    "portrait": dict(tag="CHAR", name="角色立绘", kind="image", unit="张",
                     blueprint=[("taptap", "3x4", 1), ("bilibili", "1x1", 1)],
                     role="角色介绍页 / 卡池预告 / 社交头像",
                     scene="半身立绘，服装材质与武器细节清晰，背景纯色渐变"),
    "store": dict(tag="STORE", name="商店五图", kind="image", unit="张",
                  blueprint=[("taptap", "9x16", 5), ("steam", "16x9", 5)],
                  role="TapTap 详情五图 / Steam 商店页五图",
                  scene="按 世界观 / 角色 / 战斗 / 福利 / 里程碑 五格排"),
    "report": dict(tag="RPT", name="战报图", kind="image", unit="张",
                   blueprint=[("bilibili", "16x9", 1), ("douyin", "9x16", 1)],
                   role="预约里程碑 / 首日战报 / 版本成绩",
                   scene="大数字与奖杯构图，留数据位，背景暗色显质感"),
    "ad15": dict(tag="AD15", name="15 秒买量片", kind="video", unit="条",
                 platform="douyin", size="9x16", seconds=15,
                 reuse="抖音 / TapTap / 微信小游戏 / 视频号",
                 scene="0-3 秒 战斗高光，3-9 秒 角色技能，9-15 秒 下载引导"),
    "brand30": dict(tag="BR30", name="30 秒品牌片", kind="video", unit="条",
                    platform="bilibili", size="16x9", seconds=30,
                    reuse="B站 / Steam / YouTube",
                    scene="0-5 秒 世界观，5-20 秒 玩法与角色，20-30 秒 品牌落版"),
    "trailer": dict(tag="TR", name="预告片", kind="seedance", unit="条",
                    platform="douyin", size="9x16", seconds=10,
                    reuse="抖音 / TapTap / B站",
                    scene="角色大招定格 + 镜头快推，结尾留版本号"),
}
ASSET_ORDER = ["kv", "portrait", "store", "report", "ad15", "brand30", "trailer"]

# ── 三个宣发节奏点：每个阶段要交的素材是行业习惯，不是拍脑袋 ──────────────────
PHASES = {
    "T0": dict(name="预约期", window="上线前 30 天", lead=-30,
               assets=["kv", "portrait", "store", "report"],
               focus="预约转化：主视觉 + 角色立绘 + 商店五图 + 里程碑战报"),
    "T1": dict(name="上线期", window="上线日到上线后 14 天", lead=0,
               assets=["kv", "portrait", "store", "report", "ad15", "brand30"],
               focus="买量放量：买量片、品牌片、上线战报，三套素材同时跑"),
    "T2": dict(name="长线运营", window="上线后 15 天起", lead=14,
               assets=["kv", "report", "ad15"],
               focus="版本节奏：每个版本一套 KV + 战报 + 一条买量片"),
}
PHASE_ORDER = ["T0", "T1", "T2"]

RATINGS = ["all", "12+", "16+", "18+"]

ABSOLUTE_WORDS = ["最", "第一", "唯一", "绝对", "全网", "100%", "稳赚", "躺赚",
                  "必出", "包过", "零氪通关", "日赚", "秒到账", "天花板", "永久"]
PROB_WORDS = ["抽卡", "十连", "概率", "保底", "UP"]
STORE_SHOTS = ["世界观", "角色", "战斗", "福利", "里程碑"]


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
        except Exception as e:                                       # noqa: BLE001
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
    except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
        raise Fail("call", "连不上 %s：%s" % (url, getattr(e, "reason", e)), EXIT_CALL)
    except Exception as e:                                           # noqa: BLE001
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def url_allowed(u):
    """平台只收本站托管的地址。返回 (ok, 归属说明)。"""
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
            s = " · ".join([b for b in (e.get("message") or "", e.get("code") or "") if b])
            if s:
                return s[:300]
        for k in ("message", "msg"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code"):
            return str(d["code"])[:300]
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


def fmt_pts(n):
    try:
        return "{:,}".format(int(round(float(n))))
    except Exception:                                                # noqa: BLE001
        return str(n)


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


def size_problem(req):
    """校验 gpt-image 的请求尺寸：16 的倍数 / 3:1 / 单边 3840 / 总像素区间。"""
    try:
        w, h = [int(x) for x in str(req).lower().split("x")]
    except Exception:                                                # noqa: BLE001
        return "尺寸读不出来（要写成 宽x高，例如 720x1280）"
    if w % 16 or h % 16:
        return "宽高都要是 16 的倍数（%dx%d）" % (w, h)
    if max(w, h) / float(min(w, h)) > 3.0:
        return "长短边超过 3:1（%dx%d）" % (w, h)
    if max(w, h) > 3840:
        return "单边超过 3840（%dx%d）" % (w, h)
    total = w * h
    if total < 655360 or total > 8294400:
        return "总像素 %d 不在 655,360 ~ 8,294,400 之间（%dx%d）" % (total, w, h)
    return None


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


def parse_day(s):
    s = (s or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except Exception:                                            # noqa: BLE001
            continue
    return None


def phase_dates(launch):
    d = parse_day(launch)
    if not d:
        d = datetime.date.today() + datetime.timedelta(days=30)
    def fmt(x):
        return x.strftime("%Y-%m-%d")
    return {"launch": fmt(d),
            "T0": (fmt(d - datetime.timedelta(days=30)), fmt(d - datetime.timedelta(days=1))),
            "T1": (fmt(d), fmt(d + datetime.timedelta(days=13))),
            "T2": (fmt(d + datetime.timedelta(days=14)), fmt(d + datetime.timedelta(days=90)))}


# ───────────────────────── 矩阵（纯本地，0 点）─────────────────────────
def _game_code(code):
    c = (code or "").strip().upper()
    if not re.match(r"^[A-Z0-9]{2,6}$", c):
        raise Fail("usage", "--code 取 2~6 位大写字母或数字，例如 GL01", EXIT_USAGE)
    return c


def _locales(vals):
    out = []
    for v in (vals or []):
        for x in str(v).split(","):
            x = x.strip()
            if not x:
                continue
            if x not in LOCALES:
                raise Fail("usage", "--locale 取 %s" % " / ".join(LOCALE_ORDER), EXIT_USAGE)
            if x not in out:
                out.append(x)
    return out or ["zh-CN"]


def _phase(p):
    if p not in PHASES:
        raise Fail("usage", "--phase 取 %s" % " / ".join(PHASE_ORDER), EXIT_USAGE)
    return p


def _cta(loc, phase, override):
    if override:
        return override
    return LOCALES[loc]["cta"][phase]


def _headline(asset_code, loc, a, phase):
    L = LOCALES[loc]
    base = a.slogan or "%s %s" % (a.game, L["stage"][phase])
    if asset_code == "kv":
        return base
    if asset_code == "portrait":
        return "%s 登场" % (a.character or "限定角色")
    if asset_code == "store":
        return "%s 商店图" % a.game
    if asset_code == "report":
        return "%s 战报" % L["stage"][phase]
    if asset_code == "ad15":
        return "%s %s" % (a.game, L["stage"][phase])
    if asset_code == "brand30":
        return a.slogan or a.game
    return "%s 预告" % a.game


def _subline(asset_code, loc, a, phase):
    if asset_code == "kv":
        return "%s · %s · %s" % (a.genre, a.rating, LOCALES[loc]["name"])
    if asset_code == "portrait":
        return "%s · %s" % (a.genre, a.role)
    if asset_code == "store":
        return "%s · 五图按世界观到里程碑排" % a.genre
    if asset_code == "report":
        return "%s · %s" % (a.genre, a.rating)
    if asset_code == "ad15":
        return "0-3 秒战斗高光 · 3-9 秒技能 · 9-15 秒下载引导"
    if asset_code == "brand30":
        return "0-5 秒世界观 · 5-20 秒玩法 · 20-30 秒品牌落版"
    return "角色大招定格 · 结尾留版本号"


def _prompt(asset_code, loc, a, size_key):
    m = ASSETS[asset_code]
    size = SIZES[size_key]
    extra = ""
    if asset_code == "store":
        extra = "五格分别对应世界观、角色、战斗、福利、里程碑，构图统一"
    if asset_code == "report":
        extra = "大字留白给数据，奖杯与光效做质感"
    return ("%s，%s，%s，%s，画面无文字无水印（文案后期排版），%s 比例，%s"
            % (m["name"], m["scene"], extra or "商业质感", a.genre,
               size["ratio"], size["safe"]))


def _store_caption(i):
    idx = (i - 1) % len(STORE_SHOTS)
    return "第 %d 图：%s" % (i, STORE_SHOTS[idx])


def build_plan(a):
    code = _game_code(a.code)
    phase = _phase(a.phase)
    locales = _locales(a.locales)
    version = max(1, int(a.version))
    dates = phase_dates(a.launch_date)
    rows, no = [], 0
    img_pts = vid_pts = seed_pts = 0
    for loc in locales:
        for asset_code in PHASES[phase]["assets"]:
            m = ASSETS[asset_code]
            if m["kind"] == "image":
                for (plat, size_key, count) in m["blueprint"]:
                    for i in range(1, count + 1):
                        no += 1
                        name = "%s-%s_%s_%s_%s_v%d%s" % (
                            code, m["tag"], plat, size_key, loc, version,
                            ("_%d" % i) if count > 1 else "")
                        head = _headline(asset_code, loc, a, phase)
                        if asset_code == "store":
                            head = _store_caption(i)
                        rows.append({
                            "no": no, "phase": phase, "phaseName": PHASES[phase]["name"],
                            "locale": loc, "localeName": LOCALES[loc]["name"],
                            "asset": asset_code, "assetName": m["name"], "tag": m["tag"],
                            "kind": "image", "platform": plat,
                            "platformName": PLATFORMS[plat]["name"],
                            "size": size_key, "ratio": SIZES[size_key]["ratio"],
                            "requestSize": SIZES[size_key]["req"],
                            "publishSize": SIZES[size_key]["publish"],
                            "count": 1, "seconds": 0,
                            "headline": head,
                            "subline": _subline(asset_code, loc, a, phase),
                            "cta": _cta(loc, phase, a.cta),
                            "naming": name + ".png",
                            "prompt": _prompt(asset_code, loc, a, size_key),
                            "reuse": PLATFORMS[plat]["note"],
                            "points": IMG_POINTS,
                        })
                        img_pts += IMG_POINTS
            elif m["kind"] == "video":
                no += 1
                size_key = m["size"]
                name = "%s-%s_%s_%s_%s_v%d" % (code, m["tag"], m["platform"],
                                               size_key, loc, version)
                pts = video_points(m["seconds"], a.resolution)
                rows.append({
                    "no": no, "phase": phase, "phaseName": PHASES[phase]["name"],
                    "locale": loc, "localeName": LOCALES[loc]["name"],
                    "asset": asset_code, "assetName": m["name"], "tag": m["tag"],
                    "kind": "video", "platform": m["platform"],
                    "platformName": PLATFORMS[m["platform"]]["name"],
                    "size": size_key, "ratio": SIZES[size_key]["ratio"],
                    "requestSize": SIZES[size_key]["req"],
                    "publishSize": SIZES[size_key]["publish"],
                    "count": 1, "seconds": m["seconds"],
                    "headline": _headline(asset_code, loc, a, phase),
                    "subline": _subline(asset_code, loc, a, phase),
                    "cta": _cta(loc, phase, a.cta),
                    "naming": name + ".mp4",
                    "prompt": "%s，%s，%s" % (m["name"], m["scene"], a.genre),
                    "reuse": m["reuse"],
                    "points": pts,
                    "clips": clips_for(m["seconds"]),
                })
                vid_pts += pts
            else:
                no += 1
                size_key = m["size"]
                name = "%s-%s_%s_%s_%s_v%d" % (code, m["tag"], m["platform"],
                                               size_key, loc, version)
                rows.append({
                    "no": no, "phase": phase, "phaseName": PHASES[phase]["name"],
                    "locale": loc, "localeName": LOCALES[loc]["name"],
                    "asset": asset_code, "assetName": m["name"], "tag": m["tag"],
                    "kind": "seedance", "platform": m["platform"],
                    "platformName": PLATFORMS[m["platform"]]["name"],
                    "size": size_key, "ratio": SIZES[size_key]["ratio"],
                    "requestSize": SIZES[size_key]["req"],
                    "publishSize": SIZES[size_key]["publish"],
                    "count": 1, "seconds": m["seconds"],
                    "headline": _headline(asset_code, loc, a, phase),
                    "subline": _subline(asset_code, loc, a, phase),
                    "cta": _cta(loc, phase, a.cta),
                    "naming": name + ".mp4",
                    "prompt": "%s，%s，%s" % (m["name"], m["scene"], a.genre),
                    "reuse": m["reuse"],
                    "points": SEEDANCE_POINTS,
                })
                seed_pts += SEEDANCE_POINTS

    n_video_rows = len([r for r in rows if r["kind"] in ("video", "seedance")])
    voice_chars = max(1, int(a.voice_chars))
    voice_pts = sum(int(round(voice_chars * TTS_PER_CHAR)) for _ in range(n_video_rows))
    music_count = len(locales) if (n_video_rows and a.music) else 0
    music_pts = MUSIC_FLOOR * music_count
    with_video = bool(getattr(a, "with_video", False))
    counted = img_pts + (vid_pts + voice_pts + music_pts if with_video else 0)
    full = img_pts + vid_pts + seed_pts + voice_pts + music_pts

    deliverables = [
        ("主视觉 KV", "16:9 + 9:16 / png / 上架尺寸见矩阵",
         len([r for r in rows if r["asset"] == "kv"]), "%s-KV_taptap_9x16_zh-CN_v%d.png"
         % (code, version)),
        ("角色立绘", "1:1 + 3:4 / png / 半身立绘", len([r for r in rows
                                                    if r["asset"] == "portrait"]),
         "%s-CHAR_taptap_3x4_zh-CN_v%d.png" % (code, version)),
        ("商店五图", "9:16（TapTap）/ 16:9（Steam）/ 每组 5 张",
         len([r for r in rows if r["asset"] == "store"]),
         "%s-STORE_taptap_9x16_zh-CN_v%d_1.png" % (code, version)),
        ("战报图", "16:9 + 9:16 / png / 留数据位", len([r for r in rows
                                                    if r["asset"] == "report"]),
         "%s-RPT_bilibili_16x9_zh-CN_v%d.png" % (code, version)),
        ("15 秒买量片", "9:16 / H.264 / 1080P / 15 秒", len([r for r in rows
                                                       if r["asset"] == "ad15"]),
         "%s-AD15_douyin_9x16_zh-CN_v%d.mp4" % (code, version)),
        ("30 秒品牌片", "16:9 / H.264 / 1080P / 2 段 15 秒拼", len([r for r in rows
                                                            if r["asset"] == "brand30"]),
         "%s-BR30_bilibili_16x9_zh-CN_v%d.mp4" % (code, version)),
        ("多语言配音", "mp3 / 每条约 %d 字 / 与视频条数一致" % voice_chars,
         n_video_rows, "%s-AD15_douyin_9x16_zh-CN_v%d_voice.mp3" % (code, version)),
        ("宣发配乐", "mp3 / 30 秒循环 / 一个语种一首", music_count, "bgm_zh-CN.mp3"),
        ("宣发排期", "T0 / T1 / T2 三段，含交付动作与日期", 1, "宣发排期.csv"),
        ("素材矩阵", "全量素材清单，可直接导入素材库", 1, "素材矩阵.csv"),
        ("交付单", "项目信息 / 节奏 / 清单 / 成本 / 平台规格", 1, "交付单.md"),
    ]
    schedule = [
        {"phase": "T0", "name": "预约期", "window": PHASES["T0"]["window"],
         "dates": "%s ~ %s" % dates["T0"],
         "action": "主视觉 + 角色立绘 + 商店五图 + 预约里程碑战报",
         "kpi": "预约转化率 / 商店页访问"},
        {"phase": "T1", "name": "上线期", "window": PHASES["T1"]["window"],
         "dates": "%s ~ %s" % dates["T1"],
         "action": "15 秒买量片放量 + 30 秒品牌片 + 上线战报",
         "kpi": "首日 ROI / 买量成本 / 首日留存"},
        {"phase": "T2", "name": "长线运营", "window": PHASES["T2"]["window"],
         "dates": "%s ~ %s" % dates["T2"],
         "action": "每个版本一套 KV + 战报 + 一条买量片",
         "kpi": "版本回流 / 版本付费率"},
    ]
    return {"ok": True, "generatedAt": now_iso(), "code": code, "game": a.game,
            "genre": a.genre, "phase": phase, "phaseName": PHASES[phase]["name"],
            "phaseFocus": PHASES[phase]["focus"], "launchDate": dates["launch"],
            "dates": dates, "licenseNo": a.license_no, "rating": a.rating,
            "slogan": a.slogan, "character": a.character, "role": a.role,
            "locales": locales, "version": "v%d" % version,
            "resolution": a.resolution, "withVideo": with_video,
            "voiceChars": voice_chars, "music": music_count, "rows": rows,
            "schedule": schedule,
            "totals": {"rows": len(rows), "locales": len(locales),
                       "imageRows": len([r for r in rows if r["kind"] == "image"]),
                       "videoRows": len([r for r in rows if r["kind"] == "video"]),
                       "seedanceRows": len([r for r in rows if r["kind"] == "seedance"]),
                       "imagePoints": img_pts, "videoPoints": vid_pts,
                       "seedancePoints": seed_pts, "voicePoints": voice_pts,
                       "musicPoints": music_pts,
                       "estimatedPoints": counted, "yuan": yuan(counted),
                       "fullPoints": full, "fullYuan": yuan(full)},
            "deliverables": [{"name": n, "spec": s, "count": c, "naming": f}
                             for n, s, c, f in deliverables]}


def plan_markdown(plan, a):
    t = plan["totals"]
    L = []
    L.append("# 游戏宣发 · %s交付单（%s）" % (plan["phaseName"], today()))
    L.append("")
    L.append("| 项目 | 内容 |")
    L.append("|---|---|")
    L.append("| 游戏 | %s（%s） |" % (plan["game"], plan["code"]))
    L.append("| 品类 | %s |" % plan["genre"])
    L.append("| 节奏点 | %s · %s |" % (plan["phase"], plan["phaseName"]))
    L.append("| 上线日 | %s |" % plan["launchDate"])
    L.append("| 版号 | %s |" % (plan["licenseNo"] or "待补"))
    L.append("| 适龄 | %s |" % plan["rating"])
    L.append("| 语种 | %s |" % " / ".join(plan["locales"]))
    L.append("| 版本 | %s |" % plan["version"])
    L.append("")
    L.append("本阶段目标：%s" % plan["phaseFocus"])
    L.append("")
    L.append("## 宣发节奏")
    L.append("")
    L.append("| 阶段 | 窗口 | 日期 | 交付动作 | 观察指标 |")
    L.append("|---|---|---|---|---|")
    for s in plan["schedule"]:
        L.append("| %s %s | %s | %s | %s | %s |"
                 % (s["phase"], s["name"], s["window"], s["dates"],
                    s["action"], s["kpi"]))
    L.append("")
    L.append("## 交付清单")
    L.append("")
    L.append("| # | 交付物 | 规格 | 数量 | 命名 |")
    L.append("|---|---|---|---|---|")
    for i, d in enumerate(plan["deliverables"], 1):
        L.append("| %d | %s | %s | %d | %s |"
                 % (i, d["name"], d["spec"], d["count"], d["naming"]))
    L.append("")
    L.append("## 素材矩阵（%d 条文件）" % t["rows"])
    L.append("")
    L.append("| # | 语种 | 素材 | 平台 | 尺寸 | 上架尺寸 | 命名 |")
    L.append("|---|---|---|---|---|---|---|")
    for r in plan["rows"]:
        L.append("| %d | %s | %s | %s | %s | %s | %s |"
                 % (r["no"], r["localeName"], r["assetName"], r["platformName"],
                    r["size"], r["publishSize"], r["naming"]))
    L.append("")
    L.append("## 文案（主标 / 副标 / 行动号召 / 画面提示）")
    L.append("")
    seen = set()
    for r in plan["rows"]:
        key = (r["locale"], r["asset"])
        if key in seen:
            continue
        seen.add(key)
        L.append("### %s · %s" % (r["localeName"], r["assetName"]))
        L.append("")
        L.append("- 主标：%s" % r["headline"])
        L.append("- 副标：%s" % r["subline"])
        L.append("- 行动号召：%s" % r["cta"])
        L.append("- 画面：%s" % r["prompt"])
        L.append("")
    L.append("## 成本（1 元 = 100 点）")
    L.append("")
    L.append("| 项 | 点数 | 口径 |")
    L.append("|---|---|---|")
    L.append("| 静图 %d 张 | %s | %d 点/张 |"
             % (t["imageRows"], fmt_pts(t["imagePoints"]), IMG_POINTS))
    L.append("| 视频 %d 条 | %s | %d 点/秒（%s） |"
             % (t["videoRows"], fmt_pts(t["videoPoints"]),
                VIDEO_RATES[plan["resolution"]], plan["resolution"]))
    L.append("| 口播 %d 条 | %s | 约 0.18 点/字 x %d 字 |"
             % (t["videoRows"] + t["seedanceRows"], fmt_pts(t["voicePoints"]),
                plan["voiceChars"]))
    L.append("| 配乐 %d 首 | %s | 50 点起/首 |"
             % (plan["music"], fmt_pts(t["musicPoints"])))
    if t["seedancePoints"]:
        L.append("| seedance 预告片 %d 条 | %s | 11,000 点/次 |"
                 % (t["seedanceRows"], fmt_pts(t["seedancePoints"])))
    L.append("| **本次计入** | **%s（%.2f 元）** | 只算静图 |"
             % (fmt_pts(t["estimatedPoints"]), t["yuan"]))
    L.append("| **全量** | **%s（%.2f 元）** | 加视频、口播、配乐、预告片 |"
             % (fmt_pts(t["fullPoints"]), t["fullYuan"]))
    L.append("")
    if not plan.get("withVideo"):
        L.append("本次预算只计静图：%d 张 x %d 点 = %d 点 = %.2f 元。"
                 % (t["imageRows"], IMG_POINTS, t["imagePoints"], yuan(t["imagePoints"])))
        L.append("把视频与配音也计进来：plan 加 `--with-video`（全量 %s 点 = %.2f 元）。"
                 % (fmt_pts(t["fullPoints"]), t["fullYuan"]))
        L.append("")
    L.append("## 平台规格")
    L.append("")
    L.append("| 平台 | 尺寸 | 规格 | 用途 |")
    L.append("|---|---|---|---|")
    for k in PLATFORM_ORDER:
        p = PLATFORMS[k]
        L.append("| %s | %s | %s | %s |"
                 % (p["name"], " / ".join(p["sizes"]), p["spec"], p["note"]))
    L.append("")
    L.append("## 多语言交付")
    L.append("")
    L.append("每个语种一套完整素材，命名里带语种标签，同一个文件只出一种语言。")
    L.append("配音按语种分别合成，字幕按语种分别出，视频画面可复用一套。")
    L.append("")
    L.append("| 语种 | 标签 | 当期行动号召 |")
    L.append("|---|---|---|")
    for loc in plan["locales"]:
        L.append("| %s | %s | %s |"
                 % (LOCALES[loc]["name"], loc, LOCALES[loc]["cta"][plan["phase"]]))
    L.append("")
    return "\n".join(L) + "\n"


def matrix_csv(plan):
    L = ["文件名,阶段,语种,素材,平台,尺寸,请求尺寸,上架尺寸,类型,时长,主标,副标,行动号召,状态"]
    for r in plan["rows"]:
        vals = (r["naming"], r["phase"], r["locale"], r["assetName"],
                r["platformName"], r["size"], r["requestSize"], r["publishSize"],
                r["kind"], r["seconds"], r["headline"], r["subline"], r["cta"], "待出")
        L.append(",".join(['"%s"' % str(v).replace('"', "'") for v in vals]))
    return "\n".join(L) + "\n"


def schedule_csv(plan):
    L = ["阶段,名称,窗口,日期,交付动作,观察指标"]
    for s in plan["schedule"]:
        L.append(",".join(['"%s"' % str(v).replace('"', "'") for v in (
            s["phase"], s["name"], s["window"], s["dates"], s["action"], s["kpi"])]))
    return "\n".join(L) + "\n"


def cmd_plan(a, key, host):
    plan = build_plan(a)
    outdir = a.outdir or os.path.join(HOME_DIR, today())
    jp = os.path.join(outdir, "plan.json")
    dp = os.path.join(outdir, "交付单.md")
    mp = os.path.join(outdir, "素材矩阵.csv")
    sp = os.path.join(outdir, "宣发排期.csv")
    write_text(jp, json.dumps(plan, ensure_ascii=False, indent=1))
    write_text(dp, plan_markdown(plan, a))
    write_text(mp, matrix_csv(plan))
    write_text(sp, schedule_csv(plan))
    t = plan["totals"]
    out = {"ok": True, "mode": "plan", "code": plan["code"], "phase": plan["phase"],
           "locales": plan["locales"], "rows": t["rows"],
           "imageRows": t["imageRows"], "videoRows": t["videoRows"],
           "seedanceRows": t["seedanceRows"],
           "estimatedPoints": t["estimatedPoints"], "yuan": t["yuan"],
           "fullPoints": t["fullPoints"], "fullYuan": t["fullYuan"],
           "files": {"plan": jp, "delivery": dp, "matrix": mp, "schedule": sp}}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("宣发矩阵 · %s %s（%s）" % (plan["phase"], plan["phaseName"], plan["game"]))
    print("=" * 96)
    print("  %s %s %s %s %s %s" % (pad("#", 4), pad("语种", 10), pad("素材", 14),
                                   pad("平台", 10), pad("尺寸", 8), "命名"))
    print("  " + "-" * 92)
    for r in plan["rows"][:14]:
        print("  %s %s %s %s %s %s"
              % (pad(r["no"], 4), pad(r["locale"], 10), pad(r["assetName"], 14),
                 pad(r["platformName"], 10), pad(r["size"], 8), r["naming"]))
    if len(plan["rows"]) > 14:
        print("  …… 其余 %d 条见 素材矩阵.csv" % (len(plan["rows"]) - 14))
    print()
    print("  文件 %d 条：静图 %d 张 / 视频 %d 条 / 预告片 %d 条（%d 个语种）"
          % (t["rows"], t["imageRows"], t["videoRows"], t["seedanceRows"],
             len(plan["locales"])))
    print("  本次计入：%s 点 = %.2f 元（只算静图，6 点/张）"
          % (fmt_pts(t["estimatedPoints"]), t["yuan"]))
    print("  全量：%s 点 = %.2f 元（plan 加 --with-video 计入视频与配音）"
          % (fmt_pts(t["fullPoints"]), t["fullYuan"]))
    print()
    print("  已写：")
    for p in (jp, dp, mp, sp):
        print("    %s" % p)
    print()
    print("  下一步（0 点）：`qc --plan %s` 过九道检查，再按矩阵开跑。" % jp)
    return 0


# ───────────────────────── 交付前检查（纯本地，0 点）─────────────────────────
NAMING_RE = (r"^[A-Z0-9]{2,6}-[A-Z0-9]+_(taptap|bilibili|douyin|steam|wechat)"
             r"_(9x16|1x1|16x9|3x4|4x5)_(zh-CN|zh-TW|en-US|ja-JP|ko-KR)"
             r"_v\d+(_\d+)?\.(png|jpg|jpeg|mp4)$")


def cmd_qc(a, key, host):
    problems = []
    plan = None
    synthetic = bool(a.text) and not a.plan
    if a.plan:
        if not os.path.isfile(a.plan):
            raise Fail("usage", "找不到 plan.json：%s（先跑 plan）" % a.plan, EXIT_USAGE)
        plan = json.load(io.open(a.plan, encoding="utf-8"))
        rows = plan.get("rows") or []
    elif a.text:
        rows = [{"no": 1, "phase": "T1", "phaseName": "上线期",
                 "locale": "zh-CN", "localeName": "简体中文",
                 "asset": "kv", "assetName": "主视觉", "tag": "KV", "kind": "image",
                 "platform": "taptap", "platformName": "TapTap", "size": "9x16",
                 "ratio": "9:16", "requestSize": "720x1280", "publishSize": "1080x1920",
                 "count": 1, "seconds": 0, "headline": a.text, "subline": a.text,
                 "cta": a.text, "naming": "GL01-KV_taptap_9x16_zh-CN_v1.png",
                 "prompt": a.text, "reuse": ""}]
        plan = {"code": "GL01", "phase": "T1", "locales": ["zh-CN"],
                "licenseNo": "待补", "rating": "all", "version": "v1",
                "rows": rows, "totals": {"rows": 1}}
    else:
        raise Fail("usage", "给 --plan plan.json 或 --text \"一条文案\" 再检查", EXIT_USAGE)
    if not rows:
        raise Fail("usage", "这份 plan 里没有素材，先补 --code 再生成", EXIT_USAGE)

    def bad(scope, what, tag):
        problems.append({"scope": scope, "problem": what, "tag": tag})

    rating = plan.get("rating") or "all"
    license_no = (plan.get("licenseNo") or "").strip()
    if not synthetic and (not license_no or license_no == "待补"):
        bad("交付单", "版号一栏还是空的，境内运营的游戏交付单要写上限号", "license")
    if not synthetic and rating not in RATINGS:
        bad("交付单", "适龄标识 %s 不在 %s 里" % (rating, " / ".join(RATINGS)), "license")

    for r in rows:
        blob = " ".join([r.get("headline") or "", r.get("subline") or "",
                         r.get("cta") or "", r.get("prompt") or ""])
        hits = [w for w in ABSOLUTE_WORDS if w in blob]
        if hits:
            bad("%02d 文案" % r.get("no", 0), "绝对化用语：%s（换成可验证描述）"
                % "、".join(hits), "absolute")
        prob = [w for w in PROB_WORDS if w in blob]
        if prob and "公示" not in blob:
            bad("%02d 文案" % r.get("no", 0),
                "提到 %s 却没带概率公示口径" % "、".join(prob), "prob")
        if len((r.get("cta") or "").strip()) < 4:
            bad("%02d 行动号召" % r.get("no", 0), "结尾缺一句行动号召", "cta")
        if not re.match(NAMING_RE, r.get("naming") or ""):
            bad("%02d 命名" % r.get("no", 0),
                "不符合「游戏码-素材_平台_尺寸_语种_v版本」：%s" % (r.get("naming") or ""),
                "naming")
        prob_size = size_problem(r.get("requestSize"))
        if prob_size:
            bad("%02d 尺寸" % r.get("no", 0), prob_size, "size")
        plat = PLATFORMS.get(r.get("platform") or "")
        if not plat:
            bad("%02d 平台" % r.get("no", 0),
                "平台代号 %s 不在五个平台里" % r.get("platform"), "size")
        elif r.get("size") not in plat["sizes"]:
            bad("%02d 平台尺寸" % r.get("no", 0),
                "%s 这一版出图只走 %s，当前是 %s"
                % (plat["name"], " / ".join(plat["sizes"]), r.get("size")), "size")
        if rating == "18+" and r.get("platform") in ("wechat", "douyin"):
            bad("%02d 分级" % r.get("no", 0),
                "18+ 素材上 %s 要单独提交分级材料" % PLATFORMS[r["platform"]]["name"],
                "rating")
        phase = plan.get("phase") or "T1"
        if phase == "T0":
            for w in ("已上线", "公测开启", "开服"):
                if w in blob:
                    bad("%02d 阶段口径" % r.get("no", 0),
                        "预约期素材写了「%s」，排期会对不上" % w, "phase")
        else:
            for w in ("预约有礼", "立即预约", "预约突破"):
                if w in blob:
                    bad("%02d 阶段口径" % r.get("no", 0),
                        "上线后素材仍在写「%s」，换成当期说法" % w, "phase")

    if plan.get("rows") and not synthetic:
        locs = plan.get("locales") or sorted(set(r.get("locale") for r in rows))
        sets = {}
        for loc in locs:
            sets[loc] = set((r.get("asset"), r.get("platform"), r.get("size"),
                             r.get("naming", "").split("_")[-1])
                            for r in rows if r.get("locale") == loc)
        base = sets.get(locs[0], set())
        for loc in locs:
            missing = base - sets.get(loc, set())
            extra = sets.get(loc, set()) - base
            if missing or extra:
                bad("多语言", "%s 与 %s 的素材组不一致（差 %d / 多 %d）"
                    % (LOCALES.get(loc, {}).get("name", loc),
                       LOCALES.get(locs[0], {}).get("name", locs[0]),
                       len(missing), len(extra)), "locale")
        versions = set()
        for r in rows:
            m2 = re.search(r"_v(\d+)", r.get("naming") or "")
            versions.add(m2.group(1) if m2 else "?")
        if len(versions) > 1:
            bad("版本", "同一批里混了多个版本，A/B 会串味", "matrix")
        phase = plan.get("phase") or "T1"
        need = 0
        for asset_code in PHASES[phase]["assets"]:
            m = ASSETS[asset_code]
            if m["kind"] == "image":
                need += sum(c for (_p, _s, c) in m["blueprint"]) * len(locs)
            else:
                need += len(locs)
        if len(rows) != need:
            bad("矩阵", "按 %s 应有 %d 条文件，实际 %d 条" % (phase, need, len(rows)),
                "matrix")

    checks = [
        ("版号与适龄", not any(p["tag"] in ("license", "rating") for p in problems),
         "交付单写上限号与 12+ / 16+ / 18+ 适龄标识"),
        ("概率公示", not any(p["tag"] == "prob" for p in problems),
         "提到抽卡或概率时同时给公示口径"),
        ("买量话术", not any(p["tag"] == "absolute" for p in problems),
         "最 / 第一 / 100% / 稳赚 换成可验证的结果"),
        ("行动号召", not any(p["tag"] == "cta" for p in problems),
         "每条都有一句当期行动号召"),
        ("命名规范", not any(p["tag"] == "naming" for p in problems),
         "游戏码-素材_平台_尺寸_语种_v版本"),
        ("尺寸与平台", not any(p["tag"] == "size" for p in problems),
         "16 的倍数 / 3:1 / 像素区间 / 平台只收自己的比例"),
        ("多语言覆盖", not any(p["tag"] == "locale" for p in problems),
         "每个语种一套完整素材，组内一致"),
        ("阶段口径", not any(p["tag"] == "phase" for p in problems),
         "预约期不写上线后的状态，上线后不写预约"),
        ("矩阵与版本", not any(p["tag"] == "matrix" for p in problems),
         "阶段应有的素材一条不少，版本统一"),
    ]
    out = {"ok": not problems, "checkedRows": len(rows), "problems": problems,
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("交付前检查 · %d 条文件（纯本地，0 点）" % len(rows))
    print()
    for n, o, d in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 12), d))
    if problems:
        print()
        print("  要改的地方：")
        for p in problems[:20]:
            print("    · %s：%s" % (p["scope"], p["problem"]))
        if len(problems) > 20:
            print("    …… 共 %d 处" % len(problems))
        print()
        print("  改完重跑：qc --plan <plan.json>")
        return EXIT_GATE
    print()
    print("  九项全过，可以按矩阵开跑。")
    return 0


# ───────────────────────── 免费：目录与成本 ─────────────────────────
def _read_pricing(host, key):
    st, txt = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    d = jloads(txt) or {}
    pr = d.get("pricing") if isinstance(d.get("pricing"), dict) else {}
    return st, pr


def _read_apps(host, key):
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d = jloads(txt) or {}
    lst = d.get("data") if isinstance(d.get("data"), list) else []
    return st, lst


def _flat(pr, path):
    return (pr.get(path) or {}).get("cost")


def cmd_catalog(a, key, host):
    st, pr = _read_pricing(host, key)
    st2, apps = _read_apps(host, key)
    online = {it.get("code"): it for it in apps if isinstance(it, dict)}
    vrule = pr.get(API_PREFIX + "/apps/full_video/submit") or {}
    live = vrule.get("resolutionRates") or {}
    rows = [
        {"step": "主视觉 / 立绘 / 商店图 / 战报", "cmd": "img", "app": APP_IMAGE,
         "endpoint": "POST %s/images/generations" % API_PREFIX,
         "price": "%d 点/张" % IMG_POINTS, "note": "n 1~4 一次多图；尺寸按五档走"},
        {"step": "改图（草稿 / 参考图）", "cmd": "img --ref", "app": APP_IMAGE,
         "endpoint": "POST %s/images/edits" % API_PREFIX,
         "price": "%d 点/张" % IMG_POINTS, "note": "有草稿或实拍素材时走这条"},
        {"step": "15 秒买量片", "cmd": "film --asset ad15", "app": APP_VIDEO,
         "endpoint": "POST %s/apps/full_video/submit" % API_PREFIX,
         "price": "1080P 60 点/秒（15 秒 900 点）", "note": "单段 4~15 秒"},
        {"step": "30 秒品牌片", "cmd": "film --asset brand30", "app": APP_VIDEO,
         "endpoint": "POST %s/apps/full_video/submit" % API_PREFIX,
         "price": "2 段 15 秒 = 1,800 点", "note": "本机拼两段，按总秒数计费"},
        {"step": "预告片（分辨率分档）", "cmd": "seedance --action create", "app": APP_SEEDANCE,
         "endpoint": "POST %s/apps/seedance/create" % API_PREFIX,
         "price": "%s 点/次" % fmt_pts(SEEDANCE_POINTS), "note": "flat，与时长无关"},
        {"step": "素材托管", "cmd": "seedance --action group/asset/get/update/delete",
         "app": APP_SEEDANCE, "endpoint": "POST %s/apps/seedance/<接口>" % API_PREFIX,
         "price": "落 11,000 点通配，按次估", "note": "multipart，交付前入库用"},
        {"step": "多语言配音", "cmd": "voice", "app": APP_TTS,
         "endpoint": "POST %s/apps/voice_tts/tts" % API_PREFIX,
         "price": "约 %.2f 点/字" % TTS_PER_CHAR, "note": "上游真实点数 x 3"},
        {"step": "宣发配乐", "cmd": "music", "app": APP_MUSIC,
         "endpoint": "POST %s/apps/media_services_33/music_generate" % API_PREFIX,
         "price": "%d 点起/首" % MUSIC_FLOOR, "note": "落通配：上游 x 2，保底 50"},
        {"step": "查进度", "cmd": "status", "app": "网关",
         "endpoint": "GET %s/tasks/<task_id>" % API_PREFIX,
         "price": "0 点", "note": "seedance/query 一次 11,000 点，只走这条"},
        {"step": "传素材", "cmd": "upload", "app": "网关",
         "endpoint": "POST %s/upload" % API_PREFIX,
         "price": "0 点", "note": "换 oss.gpu.likeadmin.cn 白名单地址"},
        {"step": "排期 / 矩阵 / 质检", "cmd": "plan / qc", "app": "本地",
         "endpoint": "纯本地，不发请求", "price": "0 点",
         "note": "节奏、矩阵、命名、九道检查"},
    ]
    for r in rows:
        r["online"] = (r["app"] in online) or r["app"] in ("网关", "本地")
        r["apis"] = len(online.get(r["app"], {}).get("apis") or [])
    seed_apis = [x.get("code") for x in (online.get(APP_SEEDANCE, {}) or {}).get("apis") or []]
    music_apis = len(online.get(APP_MUSIC, {}).get("apis") or [])
    out = {"ok": True, "rows": rows, "appsOnline": len(apps),
           "pricingRead": st == 200, "appsRead": st2 == 200,
           "seedanceApis": seed_apis, "media33Apis": music_apis,
           "videoRates": live or VIDEO_RATES,
           "assets": [{"code": k, "name": ASSETS[k]["name"],
                       "kind": ASSETS[k]["kind"]} for k in ASSET_ORDER],
           "platforms": {k: dict(PLATFORMS[k]) for k in PLATFORM_ORDER},
           "sizes": {k: dict(SIZES[k]) for k in SIZE_ORDER},
           "locales": [{"code": k, "name": LOCALES[k]["name"]} for k in LOCALE_ORDER],
           "phases": {k: dict(PHASES[k]) for k in PHASE_ORDER},
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 游戏宣发 —— 11 个动作 / 6 类素材 / 5 个平台 / 5 个语种（1 元 = 100 点）")
    print()
    print("  %s %s %s %s" % (pad("动作", 26), pad("子命令", 34),
                              pad("端点", 48), "单价"))
    print("  " + "-" * 122)
    for r in rows:
        print("  %s %s %s %s" % (pad(r["step"], 26), pad(r["cmd"], 34),
                                  pad(r["endpoint"], 48), r["price"]))
        print("        %s" % r["note"])
    print()
    print("  三个节奏点")
    for k in PHASE_ORDER:
        p = PHASES[k]
        print("    %s %s（%s）→ %s"
              % (k, pad(p["name"], 8), p["window"], p["focus"]))
    print()
    print("  六个素材类型")
    for k in ASSET_ORDER:
        m = ASSETS[k]
        if m["kind"] == "image":
            shots = " / ".join("%s %s x%d" % (PLATFORMS[pn]["name"], sz, c)
                               for (pn, sz, c) in m["blueprint"])
        else:
            shots = "%s %s / %d 秒" % (PLATFORMS[m["platform"]]["name"],
                                       m["size"], m["seconds"])
        print("    %s %s %s" % (pad(k, 10), pad(m["name"], 14), shots))
    print()
    print("  五个平台规格")
    print("    %s %s %s" % (pad("--platform", 12), pad("尺寸", 14), "用途"))
    for k in PLATFORM_ORDER:
        p = PLATFORMS[k]
        print("    %s %s %s" % (pad(k, 12), pad(" / ".join(p["sizes"]), 14),
                                 "%s（%s）" % (p["note"], p["spec"])))
    print()
    print("  本站应用目录 %d 个；seedance 在架 %d 个接口（%s）；media_services_33 在架 %d 个。"
          % (len(apps), len(seed_apis), " / ".join(seed_apis[:7]) or "-", music_apis))
    print("  full_video 现查按秒价：%s" % " · ".join(
        "%s %s" % (r, (live or VIDEO_RATES).get(r)) for r in RESOLUTIONS))
    print("  一个上线期双语包：静图 34 张 = 204 点 = 2.04 元；加买量片与品牌片 = 5,748 点 = 57.48 元。")
    return 0


def _phase_counts(phase):
    images = videos = 0
    video_seconds = 0
    for asset_code in PHASES[phase]["assets"]:
        m = ASSETS[asset_code]
        if m["kind"] == "image":
            images += sum(c for (_p, _s, c) in m["blueprint"])
        elif m["kind"] == "video":
            videos += 1
            video_seconds += m["seconds"]
    return images, videos, video_seconds


def cmd_cost(a, key, host):
    phase = _phase(a.phase)
    locales = max(1, int(a.locales))
    img_each, vid_each, _secs = _phase_counts(phase)
    images = img_each * locales
    videos = vid_each * locales
    chars = max(1, int(a.voice_chars))
    voice_one = int(round(chars * TTS_PER_CHAR))
    res = a.resolution
    ad_pts = video_points(15, res) * locales
    br_pts = video_points(30, res) * locales
    seed_pts = SEEDANCE_POINTS * locales if a.trailer else 0
    img_pts = IMG_POINTS * images
    music_pts = MUSIC_FLOOR * locales if a.music else 0
    voice_ad = voice_one * locales
    voice_all = voice_one * videos if videos else 0
    items = [
        ("静图 %d 张" % images, img_pts, "%d 点/张（与尺寸无关）" % IMG_POINTS),
        ("15 秒买量片 %d 条" % locales, ad_pts if vid_each else 0,
         "%d 点/秒 x 15 秒（%s）" % (VIDEO_RATES[res], res)),
        ("30 秒品牌片 %d 条" % locales,
         br_pts if "brand30" in PHASES[phase]["assets"] else 0,
         "%d 点/秒 x 30 秒（两段 15 秒）" % VIDEO_RATES[res]),
        ("多语言口播 %d 条" % max(voice_all, voice_ad), max(voice_all, voice_ad),
         "约 0.18 点/字 x %d 字 x 3" % chars),
        ("宣发配乐 %d 首" % (locales if a.music else 0), music_pts,
         "50 点起/首（上游 x 2，保底 50）"),
        ("seedance 预告片 %d 条" % (locales if a.trailer else 0), seed_pts,
         "11,000 点/次（flat，与时长无关）"),
    ]
    kind = a.kind
    base = img_pts
    if kind in ("video", "mixed"):
        base += (ad_pts if vid_each else 0) + (br_pts if "brand30" in
                                               PHASES[phase]["assets"] else 0)
        base += voice_all + music_pts
    if kind == "mixed" and a.trailer:
        base += seed_pts
    ways = [
        {"name": "全静态（只出图）", "points": img_pts},
        {"name": "静态 + 15 秒买量片", "points": img_pts + (ad_pts if vid_each else 0)
         + voice_ad + music_pts},
        {"name": "静态 + 买量片 + 品牌片", "points": img_pts
         + (ad_pts if vid_each else 0)
         + (br_pts if "brand30" in PHASES[phase]["assets"] else 0)
         + voice_all + music_pts},
        {"name": "再加 seedance 预告片", "points": img_pts
         + (ad_pts if vid_each else 0)
         + (br_pts if "brand30" in PHASES[phase]["assets"] else 0)
         + voice_all + music_pts + (SEEDANCE_POINTS * locales)},
    ]
    for w in ways:
        w["yuan"] = yuan(w["points"])
    out = {"ok": True, "phase": phase, "phaseName": PHASES[phase]["name"],
           "locales": locales, "images": images, "videos": videos,
           "kind": kind, "resolution": res, "trailer": bool(a.trailer),
           "items": [{"name": n, "points": p, "basis": b} for n, p, b in items],
           "total": base, "yuan": yuan(base),
           "perLocalePoints": int(round(base / float(locales))),
           "batchWays": ways,
           "unitPrice": {"image": IMG_POINTS, "ttsPerChar": TTS_PER_CHAR,
                         "musicFloor": MUSIC_FLOOR, "seedance": SEEDANCE_POINTS,
                         "video": VIDEO_RATES},
           "notes": ["1 元 = 100 点；单价取自 GET /api/v1/pricing 与流水实测（2026-11-08）",
                     "gpt-image 按张计费，与尺寸、质量、输出格式无关",
                     "full_video 按总秒数 x 分辨率计费，单段 4~15 秒；30 秒品牌片是两段 15 秒",
                     "口播按上游真实点数 x 3，实测 33 字 5.94 点，按 0.18 点/字估",
                     "配乐落通配规则，50 点是下限，实际以 usage.points_cost 为准",
                     "seedance create 是 flat 11,000 点/次，与分辨率、时长无关"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("宣发素材包要多少钱（1 元 = 100 点）")
    print()
    print("  节奏点 %s %s · %d 个语种 · 静图 %d 张 · 视频 %d 条"
          % (phase, PHASES[phase]["name"], locales, images, videos))
    print("  " + "-" * 80)
    for n, p, b in items:
        if p:
            print("  %s %s 点   %s" % (pad(n, 30), pad(fmt_pts(p), 9, left=False), b))
    print("  " + "-" * 80)
    total = base if kind != "image" else img_pts
    print("  %s %s 点   = %.2f 元（单语种约 %s 点）"
          % (pad("本次合计", 30), pad(fmt_pts(total), 9, left=False), yuan(total),
             fmt_pts(int(round(total / float(locales))))))
    print()
    print("  同一批素材四种走法（宣发负责人最常问的一句话）")
    print("    %s %s %s" % (pad("走法", 30), pad("点数", 10, left=False),
                            pad("元", 10, left=False)))
    print("    " + "-" * 54)
    for w in ways:
        print("    %s %s %s" % (pad(w["name"], 30), pad(fmt_pts(w["points"]), 10, left=False),
                                 pad("%.2f" % w["yuan"], 10, left=False)))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


# ───────────────────────── 出图（6 点/张）─────────────────────────
def _save_images(d, outdir, prefix, timeout=180):
    """把返回里的 b64 / url 落成 png。返回 (文件列表, 张数, 来源)。"""
    items = []
    data = d.get("data")
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("data"), list):
        items = data["data"]
    ensure_dir(outdir)
    files, src = [], None
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            continue
        b64 = it.get("b64_json") or it.get("b64") or it.get("image_base64")
        url = it.get("url") or it.get("image_url")
        path = os.path.join(outdir, "%s-%02d.png" % (prefix, i))
        if b64:
            try:
                with open(path, "wb") as fh:
                    fh.write(base64.b64decode(b64))
                files.append(path)
                src = src or "b64_json"
                continue
            except Exception:                                        # noqa: BLE001
                pass
        if url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    with open(path, "wb") as fh:
                        fh.write(r.read())
                files.append(path)
                src = src or "url"
            except Exception:                                        # noqa: BLE001
                src = src or "url"
    return files, len(files), src


def _download(url, timeout=180):
    """把白名单里的参考图取到本地（改图线接 multipart 文件）。免费，只是下载。"""
    d = ensure_dir(os.path.join(HOME_DIR, "tmp"))
    name = os.path.basename(urllib.parse.urlsplit(url).path) or (
        "ref-" + uuid.uuid4().hex + ".png")
    path = os.path.join(d, name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            with open(path, "wb") as fh:
                fh.write(r.read())
    except Exception as e:                                           # noqa: BLE001
        raise Fail("call", "参考图取不下来：%s（%s）" % (url, e), EXIT_CALL)
    return path


def cmd_img(a, key, host):
    if a.asset not in ASSETS:
        raise Fail("usage", "--asset 取 %s" % " / ".join(ASSET_ORDER), EXIT_USAGE)
    meta = ASSETS[a.asset]
    if meta["kind"] != "image":
        raise Fail("usage", "%s 是视频素材，用 film 或 seedance 出" % meta["name"],
                   EXIT_USAGE)
    if a.size not in SIZES:
        raise Fail("usage", "--size 取 %s" % " / ".join(SIZE_ORDER), EXIT_USAGE)
    size = SIZES[a.size]
    prob = size_problem(size["req"])
    if prob:
        raise Fail("internal", "尺寸表配错了：%s" % prob, EXIT_INTERNAL)
    loc = a.locale or "zh-CN"
    if loc not in LOCALES:
        raise Fail("usage", "--locale 取 %s" % " / ".join(LOCALE_ORDER), EXIT_USAGE)
    prompt = (a.prompt or _prompt(a.asset, loc, a, a.size)).strip()
    if not prompt:
        raise Fail("usage", "给 --game 或 --prompt（提示词不能为空）", EXIT_USAGE)
    n = max(1, min(4, int(a.n)))
    if a.ref and a.ref.startswith("http"):
        ok_ref, kind_ref = url_allowed(a.ref)
        if not ok_ref:
            raise Fail("usage",
                       "参考图要是平台托管地址（%s 不在白名单）。本地图直接给路径："
                       "--ref 草稿.png（会自动 upload，免费）" % kind_ref, EXIT_USAGE)
    elif a.ref and not os.path.isfile(a.ref):
        raise Fail("usage", "找不到参考图：%s" % a.ref, EXIT_USAGE)
    cost = IMG_POINTS * n
    gate(a, cost, "出图 %d 张 x %d 点/张（%s，%s）" % (n, IMG_POINTS, a.size, size["req"]))
    endpoint = EDIT_PATH if a.ref else IMAGE_PATH
    body = {"model": APP_IMAGE, "prompt": prompt, "n": n, "size": size["req"],
            "output_format": a.output_format}
    url = host + endpoint
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost), "size": a.size,
               "requestSize": size["req"], "publishSize": size["publish"]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不出图、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  尺寸：%s -> 请求 %s，上架 %s" % (a.size, size["req"], size["publish"]))
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    say("正在出图（%s，%s）…" % (meta["name"], a.size))
    t0 = time.time()
    ref_path, ref_url = None, None
    if a.ref:
        if a.ref.startswith("http"):
            ok, kind = url_allowed(a.ref)
            if not ok:
                raise Fail("usage",
                           "参考图要是平台托管地址（%s 不在白名单）。本地图直接给路径："
                           "--ref 草稿.png（会自动 upload，免费）" % kind, EXIT_USAGE)
            ref_url = a.ref
            say("正在取参考图（%s）…" % kind)
            ref_path = _download(a.ref, a.timeout)
        else:
            if not os.path.isfile(a.ref):
                raise Fail("usage", "找不到参考图：%s" % a.ref, EXIT_USAGE)
            ref_path = a.ref
            ref_url = upload_file(key, host, a.ref, timeout=a.timeout)["url"]
        fields = {"model": APP_IMAGE, "prompt": prompt, "n": str(n),
                  "size": size["req"], "output_format": a.output_format}
        st, txt = http_multipart(url, key, fields, [("image", ref_path)],
                                 timeout=a.timeout)
    else:
        st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "img", "http": st,
                    "error": msg, "size": a.size})
        raise Fail("call", "出图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = a.outdir or OUT_ROOT
    prefix = "%s-%s_%s_%s_%s_v%d" % (a.code.upper(), meta["tag"], a.platform,
                                      a.size, loc, max(1, int(a.version)))
    files, got, src = _save_images(d, outdir, prefix, timeout=a.timeout)
    if not got:
        raise Fail("call", "响应里没有图：%s" % (txt or "")[:300], EXIT_CALL)
    billed = IMG_POINTS * got
    out = {"ok": True, "mode": "img", "asset": a.asset, "size": a.size,
           "requestSize": size["req"], "publishSize": size["publish"],
           "locale": loc, "requested": n, "returned": got, "files": files,
           "source": src, "refUrl": ref_url, "elapsed": round(dt, 1),
           "billedPoints": billed, "estimatedPoints": cost, "endpoint": endpoint}
    ledger_add({"at": now_iso(), "ok": True, "mode": "img", "files": files,
                "size": a.size, "points": billed})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已出图（%.1fs · %d 点）" % (dt, billed))
    for p in files:
        print("  文件：%s" % p)
    print("  尺寸：请求 %s，上架 %s" % (size["req"], size["publish"]))
    print()
    print("  下一步：`film --asset ad15 --image <主视觉> --yes` 让它动起来。")
    return 0


# ───────────────────────── 视频（60 点/秒）─────────────────────────
def cmd_film(a, key, host):
    if a.asset not in ASSETS:
        raise Fail("usage", "--asset 取 %s" % " / ".join(ASSET_ORDER), EXIT_USAGE)
    meta = ASSETS[a.asset]
    if meta["kind"] != "video":
        raise Fail("usage", "%s 用 img 或 seedance 出" % meta["name"], EXIT_USAGE)
    if a.size not in SIZES:
        raise Fail("usage", "--size 取 %s" % " / ".join(SIZE_ORDER), EXIT_USAGE)
    size = SIZES[a.size]
    seconds = max(VIDEO_CLIP_MIN, min(VIDEO_CLIP_MAX, int(a.seconds)))
    if int(a.seconds) > VIDEO_CLIP_MAX:
        raise Fail("usage",
                   "full_video 单段 4~15 秒；%d 秒请分 %s 两段提交，再在本机拼。"
                   % (int(a.seconds), "+".join(str(x) for x in clips_for(int(a.seconds)))),
                   EXIT_USAGE)
    cost = video_points(seconds, a.resolution)
    loc = a.locale or "zh-CN"
    if loc not in LOCALES:
        raise Fail("usage", "--locale 取 %s" % " / ".join(LOCALE_ORDER), EXIT_USAGE)
    text = (a.text or "%s，%s，%s，整段 %d 秒内，画面无文字无水印"
            % (meta["name"], meta["scene"], LOCALES[loc]["name"], seconds)).strip()
    image_url = None
    if a.image:
        if a.image.startswith("http"):
            ok, kind = url_allowed(a.image)
            if not ok and not a.allow_any_url:
                raise Fail("usage",
                           "首帧图要是平台托管地址（%s 不在白名单）。本地图直接给路径："
                           "--image kv.png（会自动 upload，免费）" % kind, EXIT_USAGE)
            image_url = a.image
        elif not os.path.isfile(a.image):
            raise Fail("usage", "找不到首帧图：%s" % a.image, EXIT_USAGE)
    gate(a, cost, "视频 %d 秒 x %d 点/秒（%s）"
         % (seconds, VIDEO_RATES[a.resolution], a.resolution))
    content = [{"type": "text", "text": text}]
    body = {"model": "full-video", "content": content, "duration": seconds,
            "resolution": a.resolution, "ratio": size["ratio"],
            "aigc_watermark": a.aigc_mark}
    if image_url:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})
    url = host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit"
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost), "asset": a.asset,
               "size": a.size, "seconds": seconds}
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

    say("正在提交视频素材（%s，%d 秒）…" % (a.resolution, seconds))
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
    out = {"ok": True, "mode": "film", "taskId": task_id,
           "status": data.get("status"), "asset": a.asset, "resolution": a.resolution,
           "seconds": seconds, "size": a.size, "firstFrame": image_url,
           "elapsed": round(dt, 1), "estimatedPoints": cost,
           "billedPoints": usage.get("points_cost") or data.get("points_cost"),
           "next": "python3 scripts/run.py status --task-id %s" % task_id}
    ledger_add({"at": now_iso(), "ok": True, "mode": "film", "taskId": task_id,
                "seconds": seconds, "resolution": a.resolution, "points": cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：%s · %d 秒 · %s（%s）" % (a.resolution, seconds, a.size, size["ratio"]))
    if image_url:
        print("  首帧：%s" % image_url)
    print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── seedance：create + 5 个素材托管 + query ─────────────
SEED_ACTIONS = ["create", "group", "asset", "get", "update", "delete", "query"]


def cmd_seedance(a, key, host):
    base = host + API_PREFIX + "/apps/" + APP_SEEDANCE + "/"
    act = a.action
    if act not in SEED_ACTIONS:
        raise Fail("usage", "--action 取 %s" % " / ".join(SEED_ACTIONS), EXIT_USAGE)
    if act == "query":
        # seedance/query 落 /apps/seedance/* = 11,000 点/次；这里直接转成免费的任务查询
        out = {"ok": True, "action": "query", "redirected": "GET " + API_PREFIX +
               "/tasks/<task_id>", "estimatedPoints": 0, "reason":
               "seedance/query 一次 11,000 点，任务查询走 GET /tasks/<id> 是 0 点"}
        if not a.task_id:
            if a.json:
                print(json.dumps(out, ensure_ascii=False))
                return 0
            print("seedance/query 已转成免费查询：给 --task-id 就能查到状态（0 点）。")
            print("  seedance/query 落在 /apps/seedance/* 通配，一次 11,000 点；")
            print("  GET /api/v1/tasks/<task_id> 是 0 点，本包 --action query 就走这条。")
            return 0
        return cmd_status(a, key, host)

    if act == "create":
        if not a.text:
            raise Fail("usage", "create 要给 --text（画面描述）", EXIT_USAGE)
        if a.size not in SIZES:
            raise Fail("usage", "--size 取 %s" % " / ".join(SIZE_ORDER), EXIT_USAGE)
        seconds = max(VIDEO_CLIP_MIN, min(VIDEO_CLIP_MAX, int(a.seconds)))
        body = {"model": a.model or SEEDANCE_MODEL,
                "content": [{"type": "text", "text": a.text}],
                "duration": seconds, "resolution": a.resolution,
                "ratio": SIZES[a.size]["ratio"]}
        if a.generate_audio:
            body["generate_audio"] = True
        cost = SEEDANCE_POINTS
        gate(a, cost, "seedance/create 固定 11,000 点/次（flat，与时长无关）")
        if a.dry_run:
            out = {"ok": True, "dryRun": True, "url": base + "create",
                   "requestBody": body, "estimatedPoints": cost, "yuan": yuan(cost)}
            if a.json:
                print(json.dumps(out, ensure_ascii=False))
                return 0
            print("干跑（不提交、不冻结、不扣费）")
            print("  端点：POST %screate" % base)
            print("  请求：%s" % json.dumps(body, ensure_ascii=False))
            print("  预估：%s 点（%.2f 元）" % (fmt_pts(cost), yuan(cost)))
            return 0
        say("正在提交 seedance 预告片…")
        t0 = time.time()
        st, txt = http_json("POST", base + "create", key, body, timeout=a.timeout)
        dt = time.time() - t0
        d = jloads(txt) or {}
        data = payload_of(d)
        tid = None
        if isinstance(data, dict):
            tid = data.get("task_id") or data.get("taskId") or data.get("id")
        if st not in (200, 201) or not tid:
            msg = err_text(st, txt)
            ledger_add({"at": now_iso(), "ok": False, "mode": "seedance", "http": st,
                        "error": msg})
            raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
        out = {"ok": True, "action": "create", "taskId": tid,
               "status": data.get("status"), "elapsed": round(dt, 1),
               "estimatedPoints": cost, "yuan": yuan(cost),
               "next": "python3 scripts/run.py status --task-id %s" % tid}
        ledger_add({"at": now_iso(), "ok": True, "mode": "seedance", "taskId": tid,
                    "points": cost})
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("seedance 预告片已提交（%.1fs）" % dt)
        print("  任务：%s   状态：%s" % (tid, data.get("status")))
        print("  预估：%s 点（%.2f 元）" % (fmt_pts(cost), yuan(cost)))
        print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % tid)
        return 0

    fields = {"ProjectName": a.project or "default"}
    if act == "group":
        if not a.name:
            raise Fail("usage", "group 要给 --name（分组名，64 字符内）", EXIT_USAGE)
        fields.update({"Name": a.name, "GroupType": a.group_type or "AIGC"})
        if a.description:
            fields["Description"] = a.description
        api = "createGroup"
    elif act == "asset":
        if not (a.url and a.group_id and a.asset_type):
            raise Fail("usage", "asset 要给 --url / --group-id / --asset-type",
                       EXIT_USAGE)
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
    basis = ("seedance 素材托管：官方文档标免费，站内价目表 /api/v1/apps/seedance/* "
             "= 11,000 点/次，按通配估算")
    gate(a, cost, basis)
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": base + api,
               "multipartFields": fields, "estimatedPoints": cost, "basis": basis}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s%s（multipart/form-data）" % (base, api))
        print("  字段：%s" % json.dumps(fields, ensure_ascii=False))
        print("  预估：%s 点（%.2f 元）· %s" % (fmt_pts(cost), yuan(cost), basis))
        return 0
    st, txt = http_multipart(base + api, key, fields, [], timeout=a.timeout)
    d = jloads(txt) or {}
    ok = d.get("code") in (1, 200)
    out = {"ok": ok, "action": act, "api": api, "http": st,
           "data": d.get("data"), "msg": d.get("msg"),
           "estimatedPoints": cost}
    ledger_add({"at": now_iso(), "ok": ok, "mode": "seedance-" + api,
                "points": cost, "detail": (d.get("msg") or "")[:120]})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok else EXIT_CALL
    print("seedance %s：HTTP %s" % (api, st))
    print("  返回：%s" % json.dumps(d.get("data"), ensure_ascii=False)[:600])
    if not ok:
        print("  说明：%s" % err_text(st, txt))
    return 0 if ok else EXIT_CALL


# ───────────────────────── 配音（约 0.18 点/字）─────────────────────────
def cmd_voice(a, key, host):
    text = (a.text or "").strip()
    if not text and a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "找不到配音稿：%s" % a.script, EXIT_USAGE)
        text = io.open(a.script, encoding="utf-8").read().strip()
    if not text:
        raise Fail("usage", "给 --text \"配音文案\" 或 --script 稿子.txt", EXIT_USAGE)
    if len(text) > TTS_MAX_CHARS:
        raise Fail("usage", "这条 %d 字，同步 tts 建议 %d 字内；超过就按 15 秒拆两三条。"
                   % (len(text), TTS_MAX_CHARS), EXIT_USAGE)
    cost = max(1, int(round(len(text) * TTS_PER_CHAR)))
    gate(a, cost, "配音 %d 字 x 0.18 点/字（上游真实点数 x 3，以 usage.points_cost 为准）"
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

    say("正在合成配音（%d 字）…" % len(text))
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
        raise Fail("call", "配音失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = ensure_dir(a.outdir or OUT_ROOT)
    txt_path = os.path.join(outdir, "%s-%s-voice.txt" % (a.prefix or "voice", a.locale))
    write_text(txt_path, text + "\n")
    out = {"ok": True, "mode": "voice", "audioUrl": audio, "chars": len(text),
           "locale": a.locale, "elapsed": round(dt, 1), "textFile": txt_path,
           "billedPoints": real, "estimatedPoints": cost, "yuan": yuan(cost)}
    ledger_add({"at": now_iso(), "ok": True, "mode": "voice", "chars": len(text),
                "audio": audio, "points": real if real is not None else cost})
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
def find_media_url(node, depth=0):
    if depth > 8:
        return None
    if isinstance(node, str):
        low = node.lower()
        if node.startswith("http") and any(x in low for x in (".mp3", ".wav", ".m4a", ".flac")):
            return node
        return None
    if isinstance(node, dict):
        for k in ("audio_url", "audioUrl", "audio", "url", "source_url", "sourceUrl"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                if any(x in v.lower() for x in (".mp3", ".wav", ".m4a", ".flac")):
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


def cmd_music(a, key, host):
    prompt = a.style or "史诗管弦，鼓点推进，适合 30 秒游戏宣发片"
    cost = MUSIC_FLOOR
    gate(a, cost, "配乐 1 首，通配保底 50 点（上游 x 2，实际以 usage.points_cost 为准）")
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
    if real is not None:
        print("  实际点数：%s" % fmt_pts(real))
    else:
        print("  预估点数：%d 点起（约 %.2f 元起）" % (cost, yuan(cost)))
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
        raise Fail("usage", "必须给 --file（本地图片 / 视频路径）", EXIT_USAGE)
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": host + UPLOAD_PATH, "file": a.file,
               "estimatedPoints": 0}
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
    print("  归属：%s（在上游白名单内，可以直接给 film --image 用）" % r["hostKind"])
    return 0


# ───────────────────────── 查任务（免费）─────────────────────────
def pick_asset(node, kind, depth=0):
    ext = {"video": (".mp4", ".mov", ".webm", ".m4v"),
           "image": (".png", ".jpg", ".jpeg", ".webp"),
           "audio": (".mp3", ".wav", ".m4a", ".flac")}[kind]
    if depth > 8:
        return None, None
    if isinstance(node, str):
        low = node.lower().split("?")[0]
        if node.startswith("http") and low.endswith(ext):
            return node, "ext"
        return None, None
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and v.startswith("http"):
                low = v.lower().split("?")[0]
                if low.endswith(ext):
                    return v, k
        for v in node.values():
            got, w = pick_asset(v, kind, depth + 1)
            if got:
                return got, w
    elif isinstance(node, list):
        for v in node:
            got, w = pick_asset(v, kind, depth + 1)
            if got:
                return got, w
    return None, None


def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    path = API_PREFIX + "/tasks/" + a.task_id
    st, txt = http_json("GET", host + path, key, timeout=40)
    d = jloads(txt) or {}
    if st == 200 and d.get("code") == 0 and not d.get("data"):
        out = {"ok": True, "taskId": a.task_id, "path": path, "http": st,
               "status": "not_found", "message": d.get("msg") or "任务不存在",
               "estimatedPoints": 0}
    elif st == 200:
        data = payload_of(d)
        data = data if isinstance(data, dict) else {}
        video, _w1 = pick_asset(data, "video")
        image, _w2 = pick_asset(data, "image")
        audio, _w3 = pick_asset(data, "audio")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        out = {"ok": True, "taskId": a.task_id, "path": path, "http": st,
               "status": str(data.get("status") or "").lower(),
               "progress": data.get("progress"), "message": data.get("message"),
               "videoUrl": video, "imageUrl": image, "audioUrl": audio,
               "cost": data.get("cost"), "refund": data.get("refund"),
               "upstreamPoints": usage.get("points_cost"),
               "result": data.get("result") if isinstance(data.get("result"), dict)
               else None, "estimatedPoints": 0}
    else:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  查询端点：GET %s（0 点）" % path)
    print("  状态：%s%s" % (out.get("status"),
                            ("  %s" % out["progress"]) if out.get("progress") else ""))
    if out.get("message"):
        print("  说明：%s" % str(out["message"])[:200])
    if out.get("cost") is not None:
        print("  实扣：%s 点" % fmt_pts(out["cost"]))
    if out.get("refund") is not None:
        print("  退回：%s 点" % fmt_pts(out["refund"]))
    if out.get("videoUrl"):
        print("  成片：%s（及时转存）" % out["videoUrl"])
    if out.get("imageUrl"):
        print("  图片：%s" % out["imageUrl"])
    if out.get("audioUrl"):
        print("  音频：%s" % out["audioUrl"])
    if out.get("upstreamPoints") is not None:
        print("  上游点数：%s（站内按加价率结算）" % out["upstreamPoints"])
    return 0


# ───────────────────────── 自检（0 点）─────────────────────────
def cmd_doctor(a, key, host):
    checks = []

    st0, txt0 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d0 = jloads(txt0) or {}
    logs0 = d0.get("logs") or []
    first0 = None
    if logs0:
        row = logs0[0]
        first0 = (row.get("at"), row.get("points"), row.get("reference"))

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
    need = [APP_VIDEO, APP_TTS, APP_MUSIC, APP_SEEDANCE]
    miss = [c for c in need if c not in online]
    checks.append(("4 个底层应用在架（视频 / 配音 / 配乐 / 预告片）",
                   bool(listing) and not miss,
                   "目录 %d 个应用%s" % (len(listing),
                                        "，缺 " + ",".join(miss) if miss else "")))
    music_apis = len(online.get(APP_MUSIC, {}).get("apis") or [])
    seed_apis = [x.get("code") for x in (online.get(APP_SEEDANCE, {}) or {}).get("apis") or []]
    checks.append(("media_services_33 的 29 个接口齐全", music_apis >= 29,
                   "在架 %d 个（配乐取 music_generate）" % music_apis))
    checks.append(("seedance 的 7 个接口齐全", len(seed_apis) >= 7,
                   "在架 %d 个：%s" % (len(seed_apis), " / ".join(seed_apis[:7]))))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt3) or {}).get("pricing") or {}
    vrule = pricing.get(API_PREFIX + "/apps/full_video/submit") or {}
    live = vrule.get("resolutionRates") or {}
    drift = ["%s 本地 %d / 线上 %s" % (r, p, live.get(r))
             for r, p in VIDEO_RATES.items() if int(live.get(r) or -1) != p]
    checks.append(("full_video 5 档按秒价与线上一致",
                   st3 == 200 and bool(live) and not drift,
                   "HTTP %s · %s" % (st3, "5 档全一致" if not drift else " / ".join(drift)[:110])))

    seed_rule = pricing.get(API_PREFIX + "/apps/seedance/*") or {}
    wild = pricing.get("*") or {}
    up_rule = pricing.get(API_PREFIX + "/upload") or {}
    ok_price = (int(seed_rule.get("cost") or 0) == SEEDANCE_POINTS
                and int(wild.get("minPoints") or 0) == MUSIC_FLOOR
                and int(up_rule.get("cost") if up_rule.get("cost") is not None else 999) == 0)
    checks.append(("预告片 11,000 点 + 配乐保底 50 点 + upload 0 点", ok_price,
                   "seedance %s · 通配保底 %s · upload %s"
                   % (seed_rule.get("cost"), wild.get("minPoints"), up_rule.get("cost"))))

    st4, txt4 = http_json("POST", host + IMAGE_PATH, key,
                          {"model": APP_IMAGE, "prompt": ""}, timeout=60)
    d4 = jloads(txt4) or {}
    e4 = d4.get("error") if isinstance(d4.get("error"), dict) else {}
    msg4 = (e4.get("message") or err_text(st4, txt4))
    checks.append(("出图端点可用（422 即正确，零扣费）",
                   st4 == 422 and "prompt" in str(msg4).lower(),
                   "HTTP %s %s" % (st4, str(msg4)[:52])))

    st5, txt5 = http_json("POST", host + API_PREFIX + "/video/viapi/shot", key, {},
                          timeout=60)
    d5 = jloads(txt5) or {}
    e5 = d5.get("error") if isinstance(d5.get("error"), dict) else {}
    code5 = e5.get("code") or ""
    checks.append(("视频线在参数校验就停（400 empty_url 即正确）",
                   st5 == 400 and code5 == "empty_url",
                   "HTTP %s %s" % (st5, code5 or err_text(st5, txt5)[:40])))

    st6, txt6 = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-game-probe",
                          key, timeout=40)
    d6 = jloads(txt6) or {}
    checks.append(("任务查询 GET /tasks/<id> 可用（假 id 说任务不存在）",
                   st6 == 200 and d6.get("code") == 0,
                   "HTTP %s %s" % (st6, (d6.get("msg") or "")[:40])))

    st7, txt7 = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=60)
    d7 = jloads(txt7) or {}
    checks.append(("上传口 POST /upload 可用（缺 file 时提示补字段）",
                   st7 == 200 and d7.get("code") == 0,
                   "HTTP %s %s" % (st7, (d7.get("msg") or "")[:40])))

    st8, txt8 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d8 = jloads(txt8) or {}
    logs8 = d8.get("logs") or []
    first8 = None
    if logs8:
        row = logs8[0]
        first8 = (row.get("at"), row.get("points"), row.get("reference"))
    checks.append(("本轮没有新增流水（扣 0 点）", first0 == first8,
                   "自检前后最新一笔流水一致" if first0 == first8
                   else "出现新流水，请发出来排查"))

    last = None
    if logs8:
        row = logs8[0]
        last = {"at": row.get("at"), "type": row.get("type"),
                "points": row.get("points"), "balanceAfter": row.get("balanceAfter"),
                "reference": row.get("reference")}

    out = {"ok": all(c[1] for c in checks), "requests": 9,
           "estimatedPoints": 0, "yuan": 0.0, "lastLedger": last,
           "apps": need, "seedanceApis": seed_apis, "media33Apis": music_apis,
           "videoRates": live or VIDEO_RATES,
           "endpoints": {"image": host + IMAGE_PATH, "edit": host + EDIT_PATH,
                         "film": host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit",
                         "seedance": host + API_PREFIX + "/apps/" + APP_SEEDANCE + "/create",
                         "tts": host + API_PREFIX + "/apps/" + APP_TTS + "/tts",
                         "music": host + API_PREFIX + "/apps/" + APP_MUSIC
                         + "/music_generate",
                         "task": host + API_PREFIX + "/tasks/<task_id>",
                         "upload": host + UPLOAD_PATH},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（4 个只读 GET + 1 个空 prompt 422 + 1 个空 body 视频探针"
          " + 1 个缺 file 上传 + 流水前后比对，全部停在扣费之前）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 58), dt))
    print()
    if last:
        print("  最近一笔流水：%s  %s  %s 点  余额 %s"
              % (time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime((last["at"] or 0) / 1000.0)),
                 last.get("type") or "-", fmt_pts(last.get("points") or 0),
                 fmt_pts(last.get("balanceAfter") or 0)))
    print("  本次自检 0 点、0 冻结：9 个请求里没有一条会建任务。")
    print()
    print("  端点：POST /images/generations（出图）· /images/edits（改图）")
    print("        POST /apps/full_video/submit（买量片 / 品牌片）")
    print("        POST /apps/seedance/create（预告片）· /apps/seedance/createGroup 等 5 个素材托管")
    print("        POST /apps/voice_tts/tts（配音）· /apps/media_services_33/music_generate（配乐）")
    print("  查询：GET /api/v1/tasks/<task_id>（0 点；seedance/query 一次 11,000 点）")
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
        what = e.get("taskId") or e.get("audio") or e.get("error") or "-"
        pts = e.get("points")
        print("  %s  %-5s %-8s %-34s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", mode,
            str(what)[:34], ("%s 点" % fmt_pts(pts)) if pts is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 游戏宣发（预约期 / 上线期 / 长线运营，走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/images/generations · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/apps/seedance/create · "
               "POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/media_services_33/music_generate · "
               "GET %s/api/v1/tasks/<task_id>" % ((DEFAULT_HOST,) * 6),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 80 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="能力 + 节奏点 + 平台规格 + 现查单价（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一个宣发包多少钱，四种走法（免费）", allow_abbrev=False)
    p.add_argument("--phase", default="T1", help="T0 预约期 / T1 上线期 / T2 长线（默认 T1）")
    p.add_argument("--locales", type=int, default=2, help="语种数（默认 2）")
    p.add_argument("--kind", choices=["image", "video", "mixed"], default="mixed",
                   help="image 全静态 / video 含视频 / mixed 再过一遍预告片")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="视频分辨率（默认 1080P）")
    p.add_argument("--voice-chars", dest="voice_chars", type=int, default=60,
                   help="每条配音字数（默认 60，约 15 秒）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1], help="配乐 1 首（默认 1）")
    p.add_argument("--trailer", type=int, default=0, choices=[0, 1],
                   help="把 seedance 预告片也算进来（默认 0）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="宣发矩阵 + 多语言文案 + 交付清单（免费，纯本地）",
                       allow_abbrev=False)
    p.add_argument("--game", default="代号：山海", help="游戏名（默认示例）")
    p.add_argument("--code", default="GL01", help="游戏码 2~6 位，进文件名（默认 GL01）")
    p.add_argument("--genre", default="二次元卡牌", help="品类（默认 二次元卡牌）")
    p.add_argument("--phase", default="T1", help="T0 / T1 / T2（默认 T1）")
    p.add_argument("--locale", dest="locales", action="append",
                   help="语种，可重复给：%s（默认 zh-CN）" % " / ".join(LOCALE_ORDER))
    p.add_argument("--version", type=int, default=1, help="版本号（默认 1）")
    p.add_argument("--launch-date", dest="launch_date", default="",
                   help="上线日 YYYYMMDD（默认今天 + 30 天）")
    p.add_argument("--license-no", dest="license_no", default="",
                   help="版号（交付单里会写进去）")
    p.add_argument("--rating", default="all", help="适龄标识：all / 12+ / 16+ / 18+")
    p.add_argument("--slogan", default="", help="主标一句话（默认用游戏名 + 阶段）")
    p.add_argument("--character", default="限定角色", help="立绘角色名（默认 限定角色）")
    p.add_argument("--role", default="输出位", help="角色定位（默认 输出位）")
    p.add_argument("--cta", default="", help="统一行动号召（默认按语种与阶段给）")
    p.add_argument("--voice-chars", dest="voice_chars", type=int, default=60,
                   help="每条配音字数（默认 60）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="成本预估用分辨率（默认 1080P）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1], help="配乐计入 1 首")
    p.add_argument("--with-video", dest="with_video", action="store_true",
                   help="把视频与配音也计进本次预算（默认只算静图）")
    p.add_argument("--outdir", help="输出目录（默认 ~/.a7w/game-promo/<日期>）")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("qc", help="交付前九道检查（免费，纯本地）", allow_abbrev=False)
    p.add_argument("--plan", help="plan.json 路径")
    p.add_argument("--text", help="直接检查一条文案")
    p.set_defaults(fn=cmd_qc)

    p = sub.add_parser("img", help="主视觉 / 立绘 / 商店图 / 战报图（6 点/张，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--asset", default="kv",
                   help="素材类型：%s" % " / ".join(ASSET_ORDER))
    p.add_argument("--size", default="16x9", help="尺寸：%s" % " / ".join(SIZE_ORDER))
    p.add_argument("--platform", default="taptap",
                   help="平台：%s（进文件名）" % " / ".join(PLATFORM_ORDER))
    p.add_argument("--locale", default="zh-CN", help="语种（默认 zh-CN）")
    p.add_argument("--game", default="代号：山海", help="游戏名")
    p.add_argument("--code", default="GL01", help="游戏码")
    p.add_argument("--genre", default="二次元卡牌", help="品类")
    p.add_argument("--slogan", default="", help="主标")
    p.add_argument("--character", default="限定角色", help="角色名")
    p.add_argument("--role", default="输出位", help="角色定位")
    p.add_argument("--rating", default="all", help="适龄标识")
    p.add_argument("--prompt", help="直接给提示词，覆盖内置模板")
    p.add_argument("--n", type=int, default=1, help="张数 1~4（默认 1）")
    p.add_argument("--ref", help="参考图：本地路径（自动上传）或平台地址")
    p.add_argument("--output-format", dest="output_format", default="png",
                   help="png / jpeg / webp")
    p.add_argument("--version", type=int, default=1, help="版本号（默认 1）")
    p.add_argument("--outdir", help="图片目录（默认 ~/.a7w/game-promo/out）")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_img)

    p = sub.add_parser("film", help="买量片 / 品牌片（60 点/秒，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--asset", default="ad15", help="ad15 买量片 / brand30 品牌片")
    p.add_argument("--size", default="9x16", help="尺寸：%s" % " / ".join(SIZE_ORDER))
    p.add_argument("--locale", default="zh-CN", help="语种（默认 zh-CN）")
    p.add_argument("--game", default="代号：山海", help="游戏名")
    p.add_argument("--genre", default="二次元卡牌", help="品类")
    p.add_argument("--slogan", default="", help="主标")
    p.add_argument("--text", help="画面与运镜描述，覆盖内置模板")
    p.add_argument("--image", help="首帧图：本地路径（自动上传）或平台地址")
    p.add_argument("--seconds", type=int, default=15, help="单段秒数 4~15（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--aigc-mark", dest="aigc_mark", action="store_true",
                   help="画面加生成标识（默认不加）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把地址交给上游判断")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_film)

    p = sub.add_parser("seedance", help="预告片 create + 5 个素材托管 + query（要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--action", default="create",
                   help="%s（默认 create）" % " / ".join(SEED_ACTIONS))
    p.add_argument("--text", help="create：画面描述")
    p.add_argument("--model", default=SEEDANCE_MODEL, help="模型（默认 %s）" % SEEDANCE_MODEL)
    p.add_argument("--size", default="9x16", help="尺寸：%s" % " / ".join(SIZE_ORDER))
    p.add_argument("--seconds", type=int, default=10, help="4~15 秒（默认 10）")
    p.add_argument("--resolution", default="720p", help="480p / 720p / 1080p")
    p.add_argument("--generate-audio", dest="generate_audio", action="store_true",
                   help="生成与画面同步的音频")
    p.add_argument("--name", help="group：分组名；update：素材新名字")
    p.add_argument("--group-type", dest="group_type", default="AIGC",
                   help="group：分组类型（默认 AIGC）")
    p.add_argument("--description", help="group：分组描述")
    p.add_argument("--project", default="default", help="ProjectName（默认 default）")
    p.add_argument("--url", help="asset：素材公网 URL")
    p.add_argument("--group-id", dest="group_id", help="asset：分组 Id")
    p.add_argument("--asset-type", dest="asset_type", choices=["Image", "Video", "Audio"],
                   help="asset：素材类型")
    p.add_argument("--asset-id", dest="asset_id", help="get / update / delete：素材 Id")
    p.add_argument("--task-id", dest="task_id", help="query：任务 Id（走免费查询）")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_seedance)

    p = sub.add_parser("voice", help="多语言配音（约 0.18 点/字，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--text", help="配音文案（500 字内）")
    p.add_argument("--script", help="从文本文件读稿子")
    p.add_argument("--locale", default="zh-CN", help="语种（默认 zh-CN）")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro", help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3", help="mp3 / wav / opus")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色 ID（可选）")
    p.add_argument("--prefix", default="voice", help="稿子文件名前缀")
    p.add_argument("--outdir", help="稿子目录（默认 ~/.a7w/game-promo/out）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="宣发配乐（50 点起/首，要 --yes）", allow_abbrev=False)
    p.add_argument("--style", help="风格描述，例如「史诗管弦，鼓点推进」")
    p.add_argument("--title", help="曲名（可选）")
    p.add_argument("--music-model", dest="music_model", default=MUSIC_MODEL,
                   help="Suno 模型（默认 %s）" % MUSIC_MODEL)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_music)

    p = sub.add_parser("upload", help="上传本地素材，换白名单地址（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("status", help="查任务进度（免费，只走 GET /tasks/<id>）",
                       allow_abbrev=False)
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


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_qc", "cmd_log", "cmd_doctor")
LOCAL_ONLY = ("cmd_plan", "cmd_qc", "cmd_cost")      # 纯本地，没有 Key 也能跑


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
