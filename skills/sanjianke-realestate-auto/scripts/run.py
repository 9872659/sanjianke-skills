#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 房产汽车（sanjianke-realestate-auto）

中介与 4S 店的房源 / 车源短视频。本包不新造接口，把 api.a7w.cn 上已有的四条能力
按「一个经纪人 / 一个销售顾问一天要交的东西」重新排了顺序：

  出图     gpt-image-2.6      POST /api/v1/images/generations                    6 点/张
  口播     voice_tts          POST /api/v1/apps/voice_tts/tts                    约 0.18 点/字
  配乐     media_services_33  POST /api/v1/apps/media_services_33/music_generate 50 点起/首
  成片     full_video         POST /api/v1/apps/full_video/submit                按秒 x 分辨率
  查进度   GET /api/v1/tasks/<task_id>                                           0 点
  传图     POST /api/v1/upload                                                   0 点

## 成片单价（GET /api/v1/pricing 现查，单位：点/秒）

  480P 14   768P 28   1080P 60   2K 80   4K 80
  一单 = 30 秒主片 + 15 秒快切 = 45 秒，1080P 是 60 x 45 = 2,700 点 = 27 元。

## 三条用钱换来的规矩（都做成了默认动作）

  1. 轮询只走 GET /api/v1/tasks/<id>（cost:0）。应用层 /query 每查一次都按该应用单价
     结算；nano_banana/query 实测 72 点/次，等十分钟能烧掉一条片的钱。
  2. 要目录只看 GET /api/v1/apps 列表和 GET /api/v1/pricing。GET /api/v1/apps/<app>
     命中 /apps/<app>/* 的通配计价，按 flat 单价即时扣费、不退（实测 dressing_diffusion
     200 点、nano_banana 72 点各一笔）。
  3. videoUrl / 首帧图必须是平台托管地址。外站地址一律 400 url_not_allowed，只认
     vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。
     所以本地图先 POST /api/v1/upload（免费）换地址，film 会自动做这一步。

## 本地零成本的部分（0 点，不联网）

  plan  一单的完整交付：房源七段 / 车源五段结构、口播、标题、平台描述、标签、
        图片 prompt、命名规范、成本单
  qc    交付前合规检查：绝对化用语、承诺类表述、核验信息、价格口径、事实口径、
        行动号召、平台规格、正向表述

## 子命令

  catalog  四条能力 + 端点 + 现查单价 + 平台尺寸（免费）
  cost     一单 / 一天要多少钱（免费）
  plan     一单的脚本、文案、命名与交付单（免费，纯本地）
  qc       合规与交付检查（免费，纯本地）
  cover    出图：大门 / 楼栋 / 户型图 / 采光 / 外观 / 内饰 / 仪表，6 点/张（要 --yes）
  voice    口播讲解，约 0.18 点/字（要 --yes）
  music    配乐，50 点起（要 --yes）
  film     一键成片，按秒计费（要 --yes）
  upload   上传本地图，拿白名单地址（免费）
  status   查任务进度（免费）
  doctor   自检 Key / 应用 / 价目 / 端点（免费，不扣费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --orders 1 --seconds 30 --short-seconds 15
  python3 scripts/run.py plan --vertical house --name "万科金域华府" --layout "89平三居" \\
      --area 89 --price 268 --city 杭州 --district 余杭 --verify "HZ2026-8871" --platform beike
  python3 scripts/run.py qc --plan ~/.a7w/realestate/house-20261108/plan.json
  python3 scripts/run.py cover --vertical house --kind all --yes
  python3 scripts/run.py voice --text "万科金域华府，89 平三居，总价 268 万……" --yes
  python3 scripts/run.py music --vertical house --yes
  python3 scripts/run.py film --text "竖屏房源漫游，大门推到楼栋……" --image gate.png --yes
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

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "realestate")
LEDGER = os.path.join(HOME_DIR, "ledger.json")
OUT_ROOT = os.path.join(HOME_DIR, "out")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-realestate-auto/%s" % VERSION

# ── 四条能力（单价：GET /api/v1/pricing 2026-11-08 现查）─────────────────────
APP_VIDEO = "full_video"
VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}
VIDEO_CLIP_MAX = 15                  # full_video 单段 4~15 秒
VIDEO_CLIP_MIN = 4

APP_IMAGE = "gpt-image-2.6"
IMG_POINTS = 6                       # 点/张，与尺寸无关
IMAGE_PATH = API_PREFIX + "/images/generations"

APP_TTS = "voice_tts"
TTS_PER_CHAR = 0.18                  # 点/字（实测 tts_live 33 字 = 5.94 点，上游真实点数 x 3）
TTS_MAX_CHARS = 500                  # 同步 tts 建议 500 字内

APP_MUSIC = "media_services_33"
MUSIC_FLOOR = 50                     # 点/首，落通配：上游 x 2、单笔保底 50 点
MUSIC_MODEL = "V6"

UPLOAD_PATH = API_PREFIX + "/upload"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 6000                # 点 = 60 元，一天 10 单的默认上限

RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]
RATIOS = ["9:16", "16:9", "1:1", "4:3", "3:4", "adaptive"]

# ── 平台尺寸（发布页当前口径；覆盖 7 个字段就够开拍）───────────────────────
PLATFORMS = {
    "beike": dict(name="贝壳找房", vertical="house", ratio="9:16",
                  size="1080x1920", maxSeconds=60, tag="#贝壳找房"),
    "anjuke": dict(name="安居客", vertical="house", ratio="9:16",
                   size="1080x1920", maxSeconds=60, tag="#安居客"),
    "dcd": dict(name="懂车帝", vertical="car", ratio="9:16",
                size="1080x1920", maxSeconds=60, tag="#懂车帝"),
    "autohome": dict(name="汽车之家", vertical="car", ratio="16:9",
                     size="1920x1080", maxSeconds=120, tag="#汽车之家"),
}
PLATFORM_KEYS = list(PLATFORMS)

# ── 房源七段：小区大门 → 楼栋 → 户型图 → 采光 → 配套 → 价格 → 联系方式 ──────
HOUSE_BEATS = [
    dict(key="gate", name="小区大门", weight=8,
         shot="街边推到小区大门，门禁、招牌、门口绿化",
         line="「{name}」，{city}{district}，{layout}，{price} 万。"),
    dict(key="building", name="楼栋与楼位", weight=12,
         shot="楼栋外立面 + 单元门 + 楼层指示",
         line="{floor} 层，{orientation}向，单元门在楼栋中间。"),
    dict(key="floorplan", name="户型图", weight=18,
         shot="户型图动画，手指沿动线走一遍",
         line="户型图展开，{area} 平，动静分区清楚。"),
    dict(key="light", name="采光", weight=18,
         shot="客厅窗户推到阳台，白天自然光实拍",
         line="客厅{orientation}向，采光直进阳台。"),
    dict(key="amenity", name="配套", weight=16,
         shot="小区内景 + 门口地铁口 / 学校门头",
         line="{subway}，{school}，配套齐。"),
    dict(key="price", name="价格", weight=18,
         shot="挂牌页截图 + 单价对比 + 同小区在挂数",
         line="总价 {price} 万，单价 {unit} 万/平。"),
    dict(key="contact", name="联系方式", weight=12,
         shot="定格房源封面 + 二维码 / 私信入口",
         line="核验码 {verify}，看房{contact}。"),
]

# ── 车源五段：外观环绕 → 内饰 → 参数 → 试驾 → 落地价 ────────────────────────
CAR_BEATS = [
    dict(key="exterior", name="外观环绕", weight=24,
         shot="绕车 45 度，车头灯、轮毂、腰线一路带到车尾",
         line="{name} {variant}，{price} 万，{mileage} 万公里，一手车。"),
    dict(key="interior", name="内饰", weight=20,
         shot="车门拉开，中控屏、座椅、方向盘点一遍",
         line="内饰{interior}，座椅成色好，原厂脚垫还在。"),
    dict(key="spec", name="参数", weight=20,
         shot="仪表台特写 + 参数牌（年份 / 排量 / 过户）",
         line="{year} 年上牌，{displacement} {gearbox}，{transfer} 次过户。"),
    dict(key="drive", name="试驾", weight=20,
         shot="起步、掉头、倒车影像，一镜到底",
         line="试一段，底盘紧致，转向跟手，刹车线性。"),
    dict(key="landing", name="落地价", weight=16,
         shot="报价单 + 落地价明细（车价 / 过户 / 保险）",
         line="车价 {price} 万，过户 {fee} 万，保险 {ins} 万，落地 {landing} 万。"),
]

BEATS = {"house": HOUSE_BEATS, "car": CAR_BEATS}

# 一单两条片：主片走全结构，快切版留转化最硬的几段
CUTS = {
    "house": [
        dict(key="full", name="房源全片", arg="seconds",
             keys=["gate", "building", "floorplan", "light", "amenity", "price", "contact"]),
        dict(key="short", name="快切版", arg="short_seconds",
             keys=["gate", "floorplan", "price", "contact"]),
    ],
    "car": [
        dict(key="full", name="车源全片", arg="seconds",
             keys=["exterior", "interior", "spec", "drive", "landing"]),
        dict(key="short", name="快切版", arg="short_seconds",
             keys=["exterior", "interior", "landing"]),
    ],
}

# ── 出图清单：房源 6 张 / 车源 5 张 ─────────────────────────────────────────
IMAGE_SETS = {
    "house": [
        dict(kind="gate", name="小区大门",
             prompt="手机竖屏实拍，{city}{district}{name}小区大门，门禁与招牌清晰，"
                    "门口绿化和人行通道，傍晚暖光，真实街景质感，画面无文字水印"),
        dict(kind="building", name="楼栋外立面",
             prompt="手机竖屏实拍，{name}楼栋外立面，{floor} 层位置可见，米白色墙面与阳台，"
                    "楼下绿化步道，白天自然光，真实楼盘质感，画面无文字水印"),
        dict(kind="floorplan", name="户型图",
             prompt="室内设计师风格{layout}户型图，黑白线稿配浅木色家具示意，"
                    "标注客厅、主卧、次卧、厨房、阳台，俯视正交视角，干净纸白背景，无文字水印"),
        dict(kind="living", name="客厅采光",
             prompt="手机竖屏实拍，{name}{layout}客厅，{orientation}向落地窗，白纱帘，"
                    "白天自然光铺满地板，简约家具，真实样板间质感，画面无文字水印"),
        dict(kind="bedroom", name="主卧",
             prompt="手机竖屏实拍，{name}主卧，双人床与飘窗，{orientation}向采光，"
                    "浅色木地板，整洁无杂物，真实房源质感，画面无文字水印"),
        dict(kind="amenity", name="配套街景",
             prompt="手机竖屏实拍，小区门口街道，地铁口指示牌与便利店招牌，"
                    "步行人流，傍晚暖光，真实城市街景，画面无文字水印"),
    ],
    "car": [
        dict(kind="front45", name="前 45 度外观",
             prompt="手机竖屏实拍，{name} {variant}，车头 45 度，大灯与格栅清晰，"
                    "漆面有反光，4S 店展厅浅灰地面，柔光，真实车源质感，画面无文字水印"),
        dict(kind="interior", name="内饰中控",
             prompt="手机竖屏实拍，{name}车内{interior}内饰，中控屏与挡把，"
                    "方向盘细节，白天侧光，整洁无杂物，真实车源质感，画面无文字水印"),
        dict(kind="rear", name="后排空间",
             prompt="手机竖屏实拍，{name}后排空间，坐垫与靠背成色，"
                    "后排空调出风口，腿托位置，白天自然光，真实车源质感，画面无文字水印"),
        dict(kind="detail", name="漆面与轮毂",
             prompt="手机竖屏特写，{name}轮毂与翼子板漆面，金属反光，"
                    "胎纹清晰，浅灰背景虚化，真实车源质感，画面无文字水印"),
        dict(kind="dash", name="仪表里程",
             prompt="手机竖屏特写，{name}仪表盘，里程与油量可读，方向盘正对镜头，"
                    "车内白天侧光，真实车源质感，画面无文字水印"),
    ],
}

ABSOLUTE_WORDS = ["最", "第一", "顶级", "唯一", "绝对", "全网", "史低", "永久",
                  "100%", "国家级", "零差评", "天花板"]
HYPE_WORDS = ["必涨", "暴涨", "抄底", "稳赚", "包过户", "包落户", "包上学",
              "零首付", "返租", "保本"]
HEDGE_WORDS = ["凶宅", "漏水", "泡水", "火烧", "事故车", "调表", "瑕疵", "贬值"]


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


# ───────────────────────── 一单的脚本（纯本地，0 点）─────────────────────────
def _wan(v):
    v = float(v)
    return ("%d" % int(v)) if abs(v - int(v)) < 1e-9 else ("%.1f" % v)


def _trim(v):
    v = round(float(v), 1)
    return int(v) if abs(v - int(v)) < 1e-6 else v


def _slug(s):
    s = re.sub(r"[\\/:*?\"<>|\s]+", "", str(s or ""))
    return s[:24] or "未命名"


def _meta(a):
    """把命令行参数整理成口播 / 标题 / 图 prompt 都要用的字段表。"""
    plat = PLATFORMS[a.platform]
    m = dict(city=a.city, district=a.district, name=a.name or "示例楼盘",
             price=_wan(a.price), platform=plat["name"], platformTag=plat["tag"],
             contact=("电话 " + a.phone) if a.phone else "私信我",
             verify=(a.verify or "待填"))
    if a.vertical == "house":
        area = float(a.area) if a.area else 1.0
        m.update(layout=a.layout, area=_wan(a.area),
                 unit="%.2f" % (float(a.price) / area if area else 0),
                 floor=a.floor, orientation=a.orientation, subway=a.subway,
                 school=a.school, compare=str(a.compare))
    else:
        m.update(variant=a.variant, mileage=_wan(a.mileage), year=str(a.year),
                 displacement=a.displacement, gearbox=a.gearbox,
                 transfer=str(a.transfer), interior=a.interior,
                 fee=_wan(a.fee), ins=_wan(a.ins),
                 landing=_wan(float(a.price) + float(a.fee) + float(a.ins)))
    return m


def _beats(vertical, keys, m, seconds):
    """按权重把秒数分给每一段，返回 [{at, beat, shot, line}]。"""
    table = {b["key"]: b for b in BEATS[vertical]}
    picked = [table[k] for k in keys if k in table]
    tw = float(sum(b["weight"] for b in picked)) or 1.0
    out, acc = [], 0.0
    for b in picked:
        start = acc
        acc += float(seconds) * b["weight"] / tw
        out.append({"key": b["key"], "at": "%s-%s 秒" % (_trim(start), _trim(acc)),
                    "beat": b["name"], "shot": b["shot"],
                    "line": b["line"].format(**m)})
    return out


def _titles(m, vertical, cut):
    if vertical == "house":
        pool = [
            "{city}{district}｜{name} {layout}，{price} 万，{orientation}向",
            "{name} {area} 平，单价 {unit} 万/平，{school}在片区内",
            "{city}买房｜{name} {layout} 一条看完：大门、户型、采光、价格",
        ]
        if cut == "short":
            pool = [
                "{city}{name} {layout}，{price} 万，15 秒看完",
                "{layout}｜{price} 万｜核验码 {verify}",
                "{city}{district}买房｜{name} 快切版",
            ]
    else:
        pool = [
            "{year} 年 {name} {variant}，{mileage} 万公里，{price} 万",
            "一手{name}，{transfer} 次过户，落地 {landing} 万",
            "{city}二手车｜{name} {variant} 环绕一圈，内饰和底盘都在这",
        ]
        if cut == "short":
            pool = [
                "{name} {variant}，{price} 万，一手车",
                "{mileage} 万公里｜{year} 年上牌｜落地 {landing} 万",
                "{city}二手车｜{name} 15 秒快看",
            ]
    return [t.format(**m) for t in pool]


def _description(m, vertical):
    if vertical == "house":
        return ("{name}｜{layout}｜建筑面积 {area} 平｜{floor} 层 {orientation}向｜"
                "总价 {price} 万，单价 {unit} 万/平（同小区在挂 {compare} 套）｜"
                "{subway}｜{school}（划片以当年公示为准）｜"
                "房源核验码 {verify}｜看房{contact}").format(**m)
    return ("{name} {variant}｜{year} 年上牌｜表显 {mileage} 万公里｜"
            "{displacement} {gearbox}｜{transfer} 次过户｜"
            "车价 {price} 万，落地 {landing} 万（含过户 {fee} 万、保险 {ins} 万）｜"
            "检测报告 {verify}｜看车{contact}").format(**m)


def _tags(m, vertical):
    if vertical == "house":
        return ["#%s买房" % m["city"], "#%s%s二手房" % (m["city"], m["district"]),
                "#%s" % m["name"], "#%s" % m["layout"], "#%s万" % m["price"],
                m["platformTag"]]
    return ["#%s二手车" % m["city"], "#%s" % m["name"],
            "#%s" % m["variant"].replace(" ", ""),
            "#%s万公里" % m["mileage"], "#%s万" % m["price"], m["platformTag"]]


def _video_prompt(m, vertical, cut, seconds):
    if vertical == "house":
        focus = ("街边推到小区大门，楼栋外立面，户型图，客厅采光，门口地铁与学校，"
                 "价格牌，最后定格房源封面")
        style = "竖屏手机实拍房源漫游，%s，真实光线，镜头稳定，画面无文字与水印" % focus
        if cut == "short":
            style = "竖屏手机实拍房源快切，大门、户型图、价格牌三段落，真实光线，画面无文字与水印"
    else:
        focus = "绕车 45 度外观，内饰中控，仪表参数，起步试驾，报价单落地价"
        style = "竖屏手机实拍车源环绕，%s，展厅柔光，镜头稳定，画面无文字与水印" % focus
        if cut == "short":
            style = "竖屏手机实拍车源快切，外观、内饰、落地价三段落，展厅柔光，画面无文字与水印"
    return "%s，整段 %d 秒内" % (style, seconds)


def _naming(m, vertical, cut, seconds, platform_key):
    if vertical == "house":
        base = "%s_%s_%s_%s万_%s_%ds" % (today(), _slug(m["name"]), _slug(m["layout"]),
                                         _slug(m["price"]), platform_key, seconds)
    else:
        base = "%s_%s_%s_%s万公里_%s_%ds" % (today(), _slug(m["name"]), _slug(m["variant"]),
                                             _slug(m["mileage"]), platform_key, seconds)
    if cut == "short":
        base += "_short"
    return base


def build_plan(a):
    if not a.name:
        raise Fail("usage", "先给 --name（楼盘名 / 车型），例如 "
                   "--name \"万科金域华府\" 或 --name \"大众迈腾\"", EXIT_USAGE)
    vertical = a.vertical
    m = _meta(a)
    plat = PLATFORMS[a.platform]
    videos = []
    for cut in CUTS[vertical]:
        raw = int(getattr(a, cut["arg"]) or 0)
        if cut["key"] == "short" and raw <= 0:
            continue                                  # 只交主片
        seconds = max(VIDEO_CLIP_MIN, raw)
        beats = _beats(vertical, cut["keys"], m, seconds)
        voice = "".join([b["line"] for b in beats])
        base = _naming(m, vertical, cut["key"], seconds, a.platform)
        videos.append({
            "no": len(videos) + 1, "cut": cut["key"], "cutName": cut["name"],
            "seconds": seconds, "clips": clips_for(seconds), "beats": beats,
            "voiceover": voice, "voiceChars": len(voice),
            "titles": _titles(m, vertical, cut["key"]),
            "description": _description(m, vertical),
            "tags": _tags(m, vertical),
            "videoPrompt": _video_prompt(m, vertical, cut["key"], seconds),
            "filename": base + ".mp4", "coverName": base + "_cover.png",
            "voiceName": base + "_voice.mp3",
        })
    images = []
    for it in IMAGE_SETS[vertical]:
        base = _naming(m, vertical, "full", getattr(a, "seconds"), a.platform)
        images.append({"kind": it["kind"], "name": it["name"],
                       "prompt": it["prompt"].format(**m),
                       "filename": "%s_%s.png" % (base, it["kind"]),
                       "size": "1024x1536"})
    music = 1 if a.music else 0
    tts_total = int(round(sum(v["voiceChars"] for v in videos) * TTS_PER_CHAR))
    vpts = sum(video_points(v["seconds"], a.resolution) for v in videos)
    ipts = len(images) * IMG_POINTS
    total = vpts + ipts + tts_total + MUSIC_FLOOR * music
    totals = {"videos": len(videos), "videoSeconds": sum(v["seconds"] for v in videos),
              "resolution": a.resolution, "videoPoints": vpts,
              "images": len(images), "imagePoints": ipts,
              "ttsPoints": tts_total, "musicPoints": MUSIC_FLOOR * music,
              "estimatedPoints": total, "yuan": yuan(total)}
    deliverables = [
        ("图片", "1024x1536 / png（可裁 %s 封面）" % plat["size"], len(images),
         images[0]["filename"] if images else "-"),
        ("文案包", "标题 3 条 + 平台描述 1 条 + 标签 6 个", 1, "文案.md"),
        ("配乐", "一首 30 秒循环", music, "bgm.mp3"),
        ("交付单", "结构表 / 合规 / 成本 / 命名", 1, "交付单.md"),
    ]
    for v in videos:
        deliverables.insert(
            0 if v["cut"] == "full" else 1,
            ("%s成片" % ("主片" if v["cut"] == "full" else "快切版"),
             "%s / H.264 / %d 秒 / %s" % (plat["size"], v["seconds"], plat["ratio"]), 1,
             v["filename"]))
    deliverables.insert(2 if len(videos) > 1 else 1,
                        ("口播音频", "mp3 / 44.1kHz / 单条 %d 字内" % TTS_MAX_CHARS, 1,
                         videos[0]["voiceName"]))
    return {"ok": True, "generatedAt": now_iso(), "vertical": vertical,
            "verticalName": "房源" if vertical == "house" else "车源",
            "platform": a.platform, "platformName": plat["name"],
            "ratio": plat["ratio"], "size": plat["size"],
            "maxSeconds": plat["maxSeconds"],
            "meta": m, "videos": videos, "images": images, "totals": totals,
            "deliverables": [{"name": n, "spec": s, "count": c, "naming": f}
                             for n, s, c, f in deliverables]}


def plan_markdown(plan, a):
    L = []
    L.append("# %s · 交付单（%s）" % (plan["verticalName"], today()))
    L.append("")
    L.append("房源 / 车源：%s　｜　平台：%s（%s / %s）　｜　成片：%d 条　｜　合计 %d 秒"
             % (plan["meta"]["name"], plan["platformName"], plan["size"], plan["ratio"],
                plan["totals"]["videos"], plan["totals"]["videoSeconds"]))
    L.append("")
    L.append("## 交付清单（一单）")
    L.append("")
    L.append("| # | 交付物 | 规格 | 数量 | 命名 |")
    L.append("|---|---|---|---|---|")
    for i, d in enumerate(plan["deliverables"], 1):
        L.append("| %d | %s | %s | %d | %s |"
                 % (i, d["name"], d["spec"], d["count"], d["naming"]))
    L.append("")
    L.append("## 拍摄顺序")
    L.append("")
    L.append("| # | 版本 | 段落 | 主镜头 |")
    L.append("|---|---|---|---|")
    for v in plan["videos"]:
        for b in v["beats"]:
            L.append("| %d | %s | %s | %s |" % (v["no"], v["cutName"], b["beat"], b["shot"]))
    L.append("")
    for v in plan["videos"]:
        L.append("## %02d · %s（%d 秒 · %s）" % (v["no"], v["cutName"], v["seconds"],
                                             v["filename"]))
        L.append("")
        L.append("| 时间 | 段落 | 画面 | 口播 |")
        L.append("|---|---|---|---|")
        for b in v["beats"]:
            L.append("| %s | %s | %s | %s |" % (b["at"], b["beat"], b["shot"], b["line"]))
        L.append("")
        L.append("- 口播总字数：%d 字 / 片长 %d 秒 = %.1f 字/秒（短视频口播常见 4~6 字/秒）"
                 % (v["voiceChars"], v["seconds"],
                    v["voiceChars"] / float(max(1, v["seconds"]))))
        L.append("- 拆分提交：%s（单段 4~15 秒）"
                 % " + ".join(str(x) for x in v["clips"]))
        L.append("- 成片提示词：%s" % v["videoPrompt"])
        L.append("")
    L.append("## 出图清单（%d 张，6 点/张）" % len(plan["images"]))
    L.append("")
    L.append("| # | 图 | 尺寸 | 命名 |")
    L.append("|---|---|---|---|")
    for i, im in enumerate(plan["images"], 1):
        L.append("| %d | %s | %s | %s |" % (i, im["name"], im["size"], im["filename"]))
    L.append("")
    L.append("## 成本预估（1 元 = 100 点）")
    L.append("")
    L.append("| 项 | 点数 | 口径 |")
    L.append("|---|---|---|")
    t = plan["totals"]
    L.append("| 成片 %d 条 / 共 %d 秒 | %s | %d 点/秒 x %d 秒 |"
             % (t["videos"], t["videoSeconds"], fmt_pts(t["videoPoints"]),
                VIDEO_RATES[t["resolution"]], t["videoSeconds"]))
    L.append("| 图片 %d 张 | %s | 6 点/张 |" % (t["images"], fmt_pts(t["imagePoints"])))
    L.append("| 口播 | %s | 0.18 点/字 |" % fmt_pts(t["ttsPoints"]))
    L.append("| 配乐 | %s | 50 点起/首 |" % fmt_pts(t["musicPoints"]))
    L.append("| **合计** | **%s** | **%.2f 元** |"
             % (fmt_pts(t["estimatedPoints"]), t["yuan"]))
    L.append("")
    L.append("## 合规四项（qc 会逐条验）")
    L.append("")
    L.append("- 房源核验码 / 车源检测报告编号：%s" % plan["meta"]["verify"])
    L.append("- 价格口径：%s" % ("总价 + 单价" if plan["vertical"] == "house"
                                 else "车价 + 落地价"))
    L.append("- 事实口径：%s" % ("建筑面积" if plan["vertical"] == "house"
                                 else "表显里程 + 上牌年份"))
    L.append("- 正向表述：一手车 / 原厂漆面 / 保养记录齐全，不用负面词")
    L.append("")
    return "\n".join(L) + "\n"


def copy_markdown(plan, a):
    L = []
    L.append("# %s · 文案包（%s）" % (plan["verticalName"], today()))
    L.append("")
    for v in plan["videos"]:
        L.append("## %02d · %s" % (v["no"], v["cutName"]))
        L.append("")
        L.append("### 标题（三选一，平台里轮着用）")
        for i, t in enumerate(v["titles"], 1):
            L.append("%d. %s" % (i, t))
        L.append("")
        L.append("### 平台描述")
        L.append("")
        L.append(v["description"])
        L.append("")
        L.append("### 标签（6 个）")
        L.append("")
        L.append(" ".join(v["tags"]))
        L.append("")
        L.append("### 口播（%d 字 / %d 秒）" % (v["voiceChars"], v["seconds"]))
        L.append("")
        L.append(v["voiceover"])
        L.append("")
    L.append("## 出图 prompt（%d 张）" % len(plan["images"]))
    L.append("")
    for im in plan["images"]:
        L.append("### %s · %s" % (im["name"], im["filename"]))
        L.append("")
        L.append(im["prompt"])
        L.append("")
    return "\n".join(L) + "\n"


def cmd_plan(a, key, host):
    plan = build_plan(a)
    outdir = a.outdir or os.path.join(
        HOME_DIR, "%s-%s" % ("house" if a.vertical == "house" else "car", today()))
    jp = os.path.join(outdir, "plan.json")
    dp = os.path.join(outdir, "交付单.md")
    cp = os.path.join(outdir, "文案.md")
    write_text(jp, json.dumps(plan, ensure_ascii=False, indent=1))
    write_text(dp, plan_markdown(plan, a))
    write_text(cp, copy_markdown(plan, a))
    out = {"ok": True, "mode": "plan", "vertical": plan["vertical"],
           "name": plan["meta"]["name"], "platform": plan["platform"],
           "videos": len(plan["videos"]), "images": len(plan["images"]),
           "videoSeconds": plan["totals"]["videoSeconds"],
           "estimatedPoints": plan["totals"]["estimatedPoints"],
           "yuan": plan["totals"]["yuan"],
           "files": {"plan": jp, "delivery": dp, "copy": cp}}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("一单的完整脚本 · %s（%s，纯本地，0 点）"
          % (plan["meta"]["name"], plan["verticalName"]))
    print("=" * 78)
    print("  %s %s %s %s" % (pad("#", 3), pad("版本", 14), pad("主镜头", 30), "命名"))
    print("  " + "-" * 74)
    for v in plan["videos"]:
        print("  %s %s %s %s" % (pad(v["no"], 3), pad("%s %d 秒" % (v["cutName"], v["seconds"]), 14),
                                 pad(v["beats"][0]["shot"][:28], 30), v["filename"]))
    print()
    print("  交付清单：%d 条成片 / %d 张图 / 1 条口播 / %d 首配乐 / 1 份交付单"
          % (len(plan["videos"]), len(plan["images"]), plan["totals"]["musicPoints"] // MUSIC_FLOOR))
    print("  预估成本：%s 点 = %.2f 元（%s，%d 点/秒）"
          % (fmt_pts(plan["totals"]["estimatedPoints"]), plan["totals"]["yuan"],
             plan["totals"]["resolution"], VIDEO_RATES[plan["totals"]["resolution"]]))
    print()
    print("  已写：")
    print("    %s" % jp)
    print("    %s" % dp)
    print("    %s" % cp)
    print()
    print("  下一步：`qc --plan %s` 过一遍合规，再 cover / voice / music / film。" % jp)
    return 0


def cmd_qc(a, key, host):
    problems, checks = [], []

    def bad(scope, what):
        problems.append({"scope": scope, "problem": what})

    if a.plan:
        if not os.path.isfile(a.plan):
            raise Fail("usage", "找不到 plan.json：%s（先跑 plan）" % a.plan, EXIT_USAGE)
        plan = json.load(io.open(a.plan, encoding="utf-8"))
        videos = plan.get("videos") or []
        meta = plan.get("meta") or {}
        vertical = plan.get("vertical") or "house"
        plat = PLATFORMS.get(plan.get("platform") or "beike") or PLATFORMS["beike"]
    elif a.text:
        vertical = a.vertical
        plat = PLATFORMS[a.platform]
        videos = [{"no": 1, "cutName": "手工文案", "seconds": a.seconds,
                   "titles": [a.text], "description": a.text, "tags": [],
                   "voiceover": a.text, "voiceChars": len(a.text), "beats": []}]
        meta = {"verify": a.verify or "", "vertical": vertical}
    else:
        raise Fail("usage", "给 --plan plan.json 或 --text \"一条文案\" 再检查", EXIT_USAGE)

    if not videos:
        raise Fail("usage", "这份 plan 里没有成片，先补 --short-seconds 再生成", EXIT_USAGE)

    verify = str(meta.get("verify") or "")
    for v in videos:
        blob = " ".join([str(x) for x in v.get("titles") or []])
        blob += " " + str(v.get("description") or "")
        blob += " " + " ".join(v.get("tags") or [])
        blob += " " + str(v.get("voiceover") or "")
        for b in v.get("beats") or []:
            blob += " " + str(b.get("line") or "")

        hits = [w for w in ABSOLUTE_WORDS if w in blob]
        if hits:
            bad("%02d 标题/文案" % v.get("no", 0), "绝对化用语：%s" % "、".join(hits))
        hype = [w for w in HYPE_WORDS if w in blob]
        if hype:
            bad("%02d 文案" % v.get("no", 0), "承诺类表述：%s（改成可核对的事实）" % "、".join(hype))
        hedge = [w for w in HEDGE_WORDS if w in blob]
        if hedge:
            bad("%02d 文案" % v.get("no", 0),
                "负面词：%s（改成正向表述：一手车 / 原厂漆面 / 保养记录齐全）" % "、".join(hedge))
        if not verify or "待填" in verify:
            bad("%02d 核验" % v.get("no", 0), "缺核验信息：房源核验码 / 车源检测报告编号")
        if vertical == "house":
            if not re.search(r"\d+(\.\d+)?\s*万", blob):
                bad("%02d 价格" % v.get("no", 0), "没看到总价（写「268 万」而不是「很划算」）")
            if not re.search(r"\d+(\.\d+)?\s*万/平", blob):
                bad("%02d 价格" % v.get("no", 0), "没看到单价（写「3.01 万/平」）")
            if "建筑面积" not in blob:
                bad("%02d 事实口径" % v.get("no", 0), "面积要标「建筑面积」，和产证口径对齐")
        else:
            if not re.search(r"\d+(\.\d+)?\s*万", blob):
                bad("%02d 价格" % v.get("no", 0), "没看到车价（写「12.8 万」）")
            if "落地" not in blob:
                bad("%02d 价格" % v.get("no", 0), "没看到落地价（车价 + 过户 + 保险）")
            if "表显里程" not in blob and "万公里" not in blob:
                bad("%02d 事实口径" % v.get("no", 0), "里程要写「表显里程 N 万公里」")
            if not re.search(r"20\d{2}\s*年上牌", blob):
                bad("%02d 事实口径" % v.get("no", 0), "要写上牌年份（「2021 年上牌」）")
        if not re.search(r"私信|电话|看房|看车|预约|试驾|到店", blob):
            bad("%02d 文案" % v.get("no", 0), "缺行动号召（私信 / 电话 / 看房 / 试驾）")
        if int(v.get("seconds") or 0) > plat["maxSeconds"]:
            bad("%02d 时长" % v.get("no", 0),
                "单条 %d 秒超过 %s 的 %d 秒" % (int(v.get("seconds") or 0),
                                              plat["name"], plat["maxSeconds"]))

    checks.append(("绝对化用语", not any("绝对化用语" in p["problem"] for p in problems),
                   "最 / 第一 / 顶级 这类词换成可核对描述"))
    checks.append(("承诺类表述", not any("承诺类表述" in p["problem"] for p in problems),
                   "涨 / 赚 / 包过户 这类词交给官方口径"))
    checks.append(("正向表述", not any("负面词" in p["problem"] for p in problems),
                   "一手车 / 原厂漆面 / 保养记录齐全，事实用正向说法"))
    checks.append(("核验信息", not any("缺核验信息" in p["problem"] for p in problems),
                   "房源核验码 / 车源检测报告编号写进文案"))
    checks.append(("价格口径", not any("价格" in p["problem"] for p in problems),
                   "房源总价 + 单价；车源车价 + 落地价"))
    checks.append(("事实口径", not any("事实口径" in p["problem"] for p in problems),
                   "建筑面积 / 表显里程 + 上牌年份"))
    checks.append(("行动号召", not any("行动号召" in p["problem"] for p in problems),
                   "私信 / 电话 / 看房 / 试驾，至少一个"))
    checks.append(("平台规格", not any("超过" in p["problem"] for p in problems),
                   "%s：%s，%d 秒内" % (plat["name"], plat["ratio"], plat["maxSeconds"])))
    out = {"ok": not problems, "vertical": vertical, "platform": plat["name"],
           "checkedVideos": len(videos), "problems": problems,
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("交付前检查 · %d 条（纯本地，0 点）" % len(videos))
    print()
    for n, o, d in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 12), d))
    if problems:
        print()
        print("  要改的地方：")
        for p in problems:
            print("    · %s：%s" % (p["scope"], p["problem"]))
        print()
        print("  改完重跑：qc --plan <plan.json>")
        return EXIT_GATE
    print()
    print("  8 项全过，可以按交付单开拍。")
    return 0


# ───────────────────────── 免费：目录与成本 ─────────────────────────
def cmd_catalog(a, key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    listing = (jloads(txt) or {}).get("data")
    listing = listing if isinstance(listing, list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    st2, txt2 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt2) or {}).get("pricing") or {}
    vrule = pricing.get(API_PREFIX + "/apps/full_video/submit") or {}
    live = vrule.get("resolutionRates") or {}

    rows = [
        {"step": "出图", "app": APP_IMAGE, "cmd": "cover",
         "endpoint": "POST /api/v1/images/generations",
         "price": "%d 点/张" % IMG_POINTS, "note": "大门 / 楼栋 / 户型图 / 采光 / 内饰 / 仪表"},
        {"step": "口播", "app": APP_TTS, "cmd": "voice",
         "endpoint": "POST /api/v1/apps/voice_tts/tts",
         "price": "约 %.2f 点/字" % TTS_PER_CHAR, "note": "上游真实点数 x 3，单笔保底 > 0"},
        {"step": "配乐", "app": APP_MUSIC, "cmd": "music",
         "endpoint": "POST /api/v1/apps/media_services_33/music_generate",
         "price": "%d 点起/首" % MUSIC_FLOOR, "note": "落通配：上游 x 2，保底 50 点"},
        {"step": "成片", "app": APP_VIDEO, "cmd": "film",
         "endpoint": "POST /api/v1/apps/full_video/submit",
         "price": "480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒",
         "note": "单段 4~15 秒；一单 30 + 15 秒按总秒数计费"},
        {"step": "查进度", "app": "网关", "cmd": "status",
         "endpoint": "GET /api/v1/tasks/<task_id>",
         "price": "0 点", "note": "应用层 /query 每查一次都是钱"},
        {"step": "传图", "app": "网关", "cmd": "upload",
         "endpoint": "POST /api/v1/upload",
         "price": "0 点", "note": "换 oss.gpu.likeadmin.cn 白名单地址"},
        {"step": "脚本 / 检查", "app": "本地", "cmd": "plan / qc",
         "endpoint": "纯本地，不发请求", "price": "0 点", "note": "七段结构 / 五段结构 / 合规"},
    ]
    for r in rows:
        r["online"] = (r["app"] in online) or r["app"] in ("网关", "本地")
        r["apis"] = len(online.get(r["app"], {}).get("apis") or [])
    plats = [{"key": k, "name": v["name"], "vertical": v["vertical"],
              "ratio": v["ratio"], "size": v["size"], "maxSeconds": v["maxSeconds"]}
             for k, v in PLATFORMS.items()]
    out = {"ok": True, "rows": rows, "platforms": plats,
           "appsOnline": len(listing),
           "musicApis": len(online.get(APP_MUSIC, {}).get("apis") or []),
           "videoRates": live or VIDEO_RATES, "pricingRead": st2 == 200,
           "imageSets": {k: len(v) for k, v in IMAGE_SETS.items()},
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 房产汽车 —— 一单房源 / 车源用到的 7 个动作（1 元 = 100 点）")
    print()
    print("  %s %s %s %s" % (pad("动作", 10), pad("子命令", 12), pad("端点", 56), "单价"))
    print("  " + "-" * 112)
    for r in rows:
        print("  %s %s %s %s" % (pad(r["step"], 10), pad(r["cmd"], 12),
                                 pad(r["endpoint"], 56), r["price"]))
        print("        %s" % r["note"])
    print()
    print("  本站应用目录 %d 个；media_services_33 在架 %d 个接口（配乐取 music_generate）。"
          % (len(listing), out["musicApis"]))
    print("  full_video 现查按秒价：%s" % " · ".join(
        "%s %s" % (r, (live or VIDEO_RATES).get(r)) for r in RESOLUTIONS))
    print("  一单 30 秒主片 + 15 秒快切 = 45 秒，1080P 是 2,700 点 = 27 元。")
    print()
    print("  平台尺寸（发布页当期口径）")
    print("  %s %s %s %s %s" % (pad("--platform", 12), pad("平台", 12), pad("画幅", 8),
                                pad("尺寸", 12), "时长上限"))
    print("  " + "-" * 60)
    for p in plats:
        print("  %s %s %s %s %d 秒" % (pad(p["key"], 12), pad(p["name"], 12),
                                       pad(p["ratio"], 8), pad(p["size"], 12),
                                       p["maxSeconds"]))
    print()
    print("  出图清单：房源 %d 张 / 车源 %d 张（cover --kind all 一次出齐）。"
          % (len(IMAGE_SETS["house"]), len(IMAGE_SETS["car"])))
    return 0


def cmd_cost(a, key, host):
    orders = max(1, int(a.orders))
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds))
    short = max(0, int(a.short_seconds))
    if short and short < VIDEO_CLIP_MIN:
        short = VIDEO_CLIP_MIN
    res = a.resolution
    imgs = max(0, a.images)
    tts_chars = max(0, a.tts_chars)
    music = 1 if a.music else 0

    per_video = video_points(seconds, res) + (video_points(short, res) if short else 0)
    vpts = per_video * orders
    ipts = imgs * IMG_POINTS * orders
    tpts = int(round(tts_chars * orders * TTS_PER_CHAR))
    mpts = MUSIC_FLOOR * music
    total = vpts + ipts + tpts + mpts

    items = [
        ("成片 %d 单 / 每单 %d+%d 秒" % (orders, seconds, short), vpts,
         "%d 点/秒 x %d 秒 x %d 单" % (VIDEO_RATES[res], seconds + short, orders)),
        ("图片 %d 张" % (imgs * orders), ipts, "6 点/张 x %d 单" % orders),
        ("口播 %d 条" % orders, tpts, "%d 字/单 x 0.18 点/字" % tts_chars),
        ("配乐 %d 首" % music, mpts, "50 点起/首（上游 x 2，保底 50）"),
    ]
    matrix = [{"resolution": r, "rate": VIDEO_RATES[r],
               "oneOrder": (video_points(seconds, r)
                            + (video_points(short, r) if short else 0)
                            + imgs * IMG_POINTS + int(round(tts_chars * TTS_PER_CHAR))
                            + mpts),
               "dayPoints": ((video_points(seconds, r)
                              + (video_points(short, r) if short else 0)) * orders
                             + ipts + tpts + mpts)}
              for r in RESOLUTIONS]
    out = {"ok": True, "orders": orders, "seconds": seconds, "shortSeconds": short,
           "clipsPerFull": len(clips_for(seconds)),
           "resolution": res, "images": imgs, "ttsChars": tts_chars, "music": music,
           "items": [{"name": n, "points": p, "basis": b} for n, p, b in items],
           "total": total, "yuan": yuan(total),
           "yuanPerOrder": yuan(total / float(orders)),
           "matrix": matrix, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "plans": [{"platform": k, "name": v["name"], "ratio": v["ratio"],
                      "size": v["size"], "maxSeconds": v["maxSeconds"]}
                     for k, v in PLATFORMS.items()],
           "unitPrice": {"image": IMG_POINTS, "ttsPerChar": TTS_PER_CHAR,
                         "musicFloor": MUSIC_FLOOR, "video": VIDEO_RATES},
           "notes": ["1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-08 现查）",
                     "full_video 按总秒数 x 分辨率计费，单段 4~15 秒",
                     "口播按上游真实点数 x 3；实测 33 字 5.94 点，按 0.18 点/字估",
                     "配乐落通配规则，50 点是下限，实际以返回 usage.points_cost 为准",
                     "图片 6 点/张，与尺寸无关，按实际返回张数计费"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("%d 单要多少钱（1 元 = 100 点）" % orders)
    print()
    print("  每单 %d 秒主片 + %d 秒快切 = %d 秒，%s（主片拆 %d 段）"
          % (seconds, short, seconds + short, res, len(clips_for(seconds))))
    print("  " + "-" * 78)
    for n, p, b in items:
        print("  %s %s 点   %s" % (pad(n, 30), pad(fmt_pts(p), 9, left=False), b))
    print("  " + "-" * 78)
    print("  %s %s 点   = %.2f 元（单条约 %.2f 元）"
          % (pad("合计", 30), pad(fmt_pts(total), 9, left=False), yuan(total),
             yuan(total / float(orders))))
    print()
    print("  同一批按分辨率（成片部分变，出图 / 口播 / 配乐不变）")
    print("    %s %s %s" % (pad("分辨率", 10), pad("一单", 12, left=False), "全天合计"))
    for r in matrix:
        print("    %s %s %s 点 = %.2f 元"
              % (pad(r["resolution"], 10), pad(fmt_pts(r["oneOrder"]), 12, left=False),
                 pad(fmt_pts(r["dayPoints"]), 9, left=False), yuan(r["dayPoints"])))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


# ───────────────────────── 出图（6 点/张）─────────────────────────
def _save_image(outdir, prefix, idx, item):
    ensure_dir(outdir)
    b64 = item.get("b64_json") or item.get("b64") or item.get("image_base64")
    url = item.get("url") or item.get("image_url")
    path = os.path.join(outdir, "%s-%02d.png" % (prefix, idx))
    if b64:
        raw = base64.b64decode(b64)
        with open(path, "wb") as fh:
            fh.write(raw)
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
    if not a.name:
        raise Fail("usage", "先给 --name（楼盘名 / 车型），文案里的名字要一致", EXIT_USAGE)
    vertical = a.vertical
    m = _meta(a)
    all_imgs = IMAGE_SETS[vertical]
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
        body = {"model": APP_IMAGE, "n": n, "size": "1024x1536",
                "prompt": picked[0]["prompt"].format(**m)}
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
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

    outdir = ensure_dir(a.outdir or OUT_ROOT)
    base = _naming(m, vertical, "full", max(VIDEO_CLIP_MIN, int(a.seconds)), a.platform)
    files, urls, done, billed = [], [], [], 0
    for it in picked:
        prompt = it["prompt"].format(**m)
        body = {"model": APP_IMAGE, "prompt": prompt,
                "n": n, "size": it.get("size") or "1024x1536"}
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
        billed += IMG_POINTS * len(items)
        for i, one in enumerate(items, 1):
            p, u = _save_image(outdir, "%s_%s" % (base, it["kind"]), i, one)
            if p:
                files.append(p)
            if u:
                urls.append(u)
        done.append({"kind": it["kind"], "name": it["name"], "returned": len(items),
                     "prompt": prompt})
    ledger_add({"at": now_iso(), "ok": True, "mode": "cover", "vertical": vertical,
                "kinds": [x["kind"] for x in done], "files": files, "points": billed})
    out = {"ok": True, "mode": "cover", "vertical": vertical, "kinds": done,
           "requested": len(picked) * n, "returned": len(files),
           "files": files, "urls": urls, "billedPoints": billed,
           "estimatedPoints": cost, "endpoint": IMAGE_PATH}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已出图（%d 张）" % len(files))
    for x in done:
        print("  · %s：%d 张" % (x["name"], x["returned"]))
    for p in files:
        print("  文件：%s" % p)
    for u in urls:
        print("  链接：%s（约 3 小时有效，及时下载）" % u)
    print()
    print("  下一步：`film --image <文件> --text \"...\" --yes` 让这张图动起来。")
    return 0


# ───────────────────────── 口播（约 0.18 点/字）─────────────────────────
def cmd_voice(a, key, host):
    text = (a.text or "").strip()
    if not text and a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "找不到口播稿：%s" % a.script, EXIT_USAGE)
        text = io.open(a.script, encoding="utf-8").read().strip()
    if not text:
        raise Fail("usage", "给 --text \"口播文案\" 或 --script 稿子.txt；"
                   "也可以先 `plan` 生成 plan.json，把 voiceover 粘过来", EXIT_USAGE)
    if len(text) > TTS_MAX_CHARS:
        raise Fail("usage", "这条 %d 字，同步 tts 建议 %d 字内；超过就按段落拆成两三条口播。"
                   % (len(text), TTS_MAX_CHARS), EXIT_USAGE)
    cost = max(1, int(round(len(text) * TTS_PER_CHAR)))
    gate(a, cost, "口播 %d 字 x 0.18 点/字（上游真实点数 x 3，以 usage.points_cost 为准）"
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

    say("正在合成口播（%d 字）…" % len(text))
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
        ledger_add({"at": now_iso(), "ok": False, "mode": "voice", "http": st, "error": msg})
        raise Fail("call", "配音失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = ensure_dir(a.outdir or OUT_ROOT)
    txt_path = os.path.join(outdir, "%s-voice.txt" % (a.prefix or "listing"))
    write_text(txt_path, text + "\n")
    out = {"ok": True, "mode": "voice", "audioUrl": audio, "chars": len(text),
           "elapsed": round(dt, 1), "textFile": txt_path,
           "billedPoints": real, "estimatedPoints": cost, "yuan": yuan(cost),
           "endpoint": API_PREFIX + "/apps/" + APP_TTS + "/tts"}
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


MUSIC_STYLE = {
    "house": "温暖钢琴加轻弦乐，92 BPM，节奏平稳，适合 30 秒房源漫游",
    "car": "城市电子加清楚鼓点，108 BPM，适合 30 秒车源环绕",
}


def cmd_music(a, key, host):
    prompt = a.style or MUSIC_STYLE[a.vertical]
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
        ledger_add({"at": now_iso(), "ok": False, "mode": "music", "http": st, "error": msg})
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
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [("file", path)], timeout=timeout)
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
    print("  归属：%s（在上游白名单内，可以直接给 film 用）" % r["hostKind"])
    return 0


# ───────────────────────── 成片（按秒计费）─────────────────────────
def cmd_film(a, key, host):
    text = (a.text or "").strip()
    if not text:
        raise Fail("usage", "给 --text \"画面与运镜描述\"（把 plan 里的 videoPrompt 粘过来）",
                   EXIT_USAGE)
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds))
    if seconds > VIDEO_CLIP_MAX:
        raise Fail("usage", "full_video 单段 4~15 秒；%d 秒分 %s 两段提交。"
                   % (seconds, "+".join(str(x) for x in clips_for(seconds))), EXIT_USAGE)
    ratio = a.ratio or (PLATFORMS[a.platform]["ratio"] if a.platform else "9:16")
    cost = video_points(seconds, a.resolution)
    gate(a, cost, "成片 %d 秒 x %d 点/秒（%s）" % (seconds, VIDEO_RATES[a.resolution],
                                                 a.resolution))

    image_url = None
    if a.image:
        if a.image.startswith("http"):
            ok, kind = url_allowed(a.image)
            if not ok and not a.allow_any_url:
                raise Fail("usage",
                           "首帧图必须是平台托管地址（%s 不在白名单）。两种写法：\n"
                           "  · 本地图直接给路径：--image gate.png（film 会自动 upload，免费）\n"
                           "  · 本站地址：https://oss.gpu.likeadmin.cn/openapi/…" % kind,
                           EXIT_USAGE)
            image_url = a.image
        else:
            if not os.path.isfile(a.image):
                raise Fail("usage", "找不到首帧图：%s" % a.image, EXIT_USAGE)

    content = [{"type": "text", "text": text}]
    body = {"model": "full-video", "content": content, "duration": seconds,
            "resolution": a.resolution, "ratio": ratio, "aigc_watermark": False}
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

    say("正在提交成片（%s，%d 秒）…" % (a.resolution, seconds))
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
           "status": data.get("status"), "resolution": a.resolution,
           "seconds": seconds, "clips": clips_for(seconds), "ratio": ratio,
           "firstFrame": image_url, "elapsed": round(dt, 1),
           "estimatedPoints": cost,
           "billedPoints": usage.get("points_cost") or data.get("points_cost"),
           "next": "python3 scripts/run.py status --task-id %s" % task_id}
    ledger_add({"at": now_iso(), "ok": True, "mode": "film", "taskId": task_id,
                "seconds": seconds, "resolution": a.resolution, "points": cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：%s · %d 秒（拆 %s）· %s" % (a.resolution, seconds,
                                              "+".join(str(x) for x in clips_for(seconds)),
                                              ratio))
    if image_url:
        print("  首帧：%s" % image_url)
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
           "status": None, "result": None}
    if st == 200 and d.get("code") == 0 and not d.get("data"):
        out.update({"status": "not_found", "message": d.get("msg") or "任务不存在"})
    elif st == 200:
        data = payload_of(d) if isinstance(d, dict) else {}
        data = data if isinstance(data, dict) else {}
        out.update({"status": data.get("status"), "message": data.get("message"),
                    "videoUrl": data.get("videoUrl") or data.get("video_url"),
                    "audioUrl": data.get("audioUrl") or data.get("audio_url"),
                    "cost": data.get("cost"), "refund": data.get("refund"),
                    "result": data.get("result")})
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
    if out.get("audioUrl"):
        print("  音频：%s" % out["audioUrl"])
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
    need = [APP_VIDEO, APP_TTS, APP_MUSIC]
    miss = [c for c in need if c not in online]
    checks.append(("3 个底层应用在架（成片 / 口播 / 配乐）",
                   bool(listing) and not miss,
                   "目录 %d 个应用%s" % (len(listing),
                                        "，缺 " + ",".join(miss) if miss else "")))
    music_apis = len(online.get(APP_MUSIC, {}).get("apis") or [])
    checks.append(("media_services_33 的 29 个接口齐全", music_apis >= 29,
                   "在架 %d 个接口（配乐取 music_generate）" % music_apis))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt3) or {}).get("pricing") or {}
    vrule = pricing.get(API_PREFIX + "/apps/full_video/submit") or {}
    live = vrule.get("resolutionRates") or {}
    drift = ["%s 本地 %d / 线上 %s" % (r, p, live.get(r))
             for r, p in VIDEO_RATES.items() if int(live.get(r) or -1) != p]
    checks.append(("full_video 5 档按秒价与线上一致",
                   st3 == 200 and bool(live) and not drift,
                   "HTTP %s · %s" % (st3, "5 档全一致" if not drift else " / ".join(drift)[:110])))

    wild = pricing.get("*") or {}
    up_rule = pricing.get(API_PREFIX + "/upload") or {}
    ok_price = (int(wild.get("minPoints") or 0) == MUSIC_FLOOR
                and int(up_rule.get("cost") if up_rule.get("cost") is not None else 999) == 0)
    checks.append(("配乐保底 50 点 + upload 0 点", ok_price,
                   "通配保底 %s · upload %s"
                   % (wild.get("minPoints"), up_rule.get("cost"))))

    st4, txt4 = http_json("POST", host + IMAGE_PATH, key,
                          {"model": APP_IMAGE, "prompt": ""}, timeout=60)
    d4 = jloads(txt4) or {}
    e4 = d4.get("error") if isinstance(d4.get("error"), dict) else {}
    msg4 = (e4.get("message") or err_text(st4, txt4))
    checks.append(("出图端点可用（422 即正确，零扣费）",
                   st4 == 422 and "prompt" in str(msg4).lower(),
                   "HTTP %s %s" % (st4, str(msg4)[:52])))

    st5, txt5 = http_json("POST", host + API_PREFIX + "/video/viapi/enhance", key, {},
                          timeout=60)
    d5 = jloads(txt5) or {}
    e5 = d5.get("error") if isinstance(d5.get("error"), dict) else {}
    code5 = e5.get("code") or ""
    checks.append(("视频线在参数校验就停（400 empty_url 即正确）",
                   st5 == 400 and code5 == "empty_url",
                   "HTTP %s %s" % (st5, code5 or err_text(st5, txt5)[:40])))

    st6, txt6 = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-re-doctor-probe",
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

    first8 = _last_log(key, host)
    checks.append(("本轮没有新增流水（扣 0 点）", first0 == first8,
                   "自检前后最新一笔流水一致" if first0 == first8
                   else "出现新流水，请发出来排查"))

    st9, txt9 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d9 = jloads(txt9) or {}
    last = None
    if (d9.get("logs") or []):
        row = d9["logs"][0]
        last = {"at": row.get("at"), "type": row.get("type"),
                "points": row.get("points"), "balanceAfter": row.get("balanceAfter"),
                "reference": row.get("reference")}

    out = {"ok": all(c[1] for c in checks), "requests": 9,
           "estimatedPoints": 0, "yuan": 0.0, "lastLedger": last,
           "apps": need, "videoRates": live or VIDEO_RATES,
           "platforms": [{"key": k, "name": v["name"], "ratio": v["ratio"],
                          "size": v["size"]} for k, v in PLATFORMS.items()],
           "endpoints": {"image": host + IMAGE_PATH,
                         "tts": host + API_PREFIX + "/apps/" + APP_TTS + "/tts",
                         "music": host + API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate",
                         "film": host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit",
                         "task": host + API_PREFIX + "/tasks/<task_id>",
                         "upload": host + UPLOAD_PATH},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（3 个只读 GET + 1 个空 prompt 422 + 1 个空 body 视频探针 + 1 个缺 file 上传，"
          "全部停在扣费之前）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 52), dt))
    print()
    if last:
        print("  最近一笔流水：%s  %s  %s 点  余额 %s"
              % (time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime((last["at"] or 0) / 1000.0)),
                 last.get("type") or "-", fmt_pts(last.get("points") or 0),
                 fmt_pts(last.get("balanceAfter") or 0)))
    print("  本次自检 0 点、0 冻结：9 个请求里没有一条会建任务。")
    print()
    print("  端点：POST /images/generations（出图）· /apps/full_video/submit（成片）")
    print("        POST /apps/voice_tts/tts（口播）· /apps/media_services_33/music_generate（配乐）")
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
        what = e.get("taskId") or e.get("audio") or e.get("error") or "-"
        pts = e.get("points")
        print("  %s  %-5s %-6s %-34s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", mode,
            str(what)[:34], ("%s 点" % fmt_pts(pts)) if pts is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def add_listing_args(p):
    p.add_argument("--vertical", choices=["house", "car"], default="house",
                   help="house 房源 / car 车源（默认 house）")
    p.add_argument("--name", help="楼盘名 / 车型，例如 万科金域华府 / 大众迈腾")
    p.add_argument("--city", default="杭州", help="城市（默认 杭州）")
    p.add_argument("--district", default="余杭", help="区域 / 商圈（默认 余杭）")
    p.add_argument("--platform", choices=PLATFORM_KEYS, default="beike",
                   help="发布平台（默认 beike 贝壳找房）")
    p.add_argument("--price", type=float, default=268, help="总价 / 车价（万）")
    p.add_argument("--verify", default="", help="房源核验码 / 车源检测报告编号")
    p.add_argument("--phone", default="", help="联系方式（电话或微信号，留空写「私信我」）")
    p.add_argument("--layout", default="89平三居", help="房源户型（house）")
    p.add_argument("--area", type=float, default=89, help="建筑面积（平，house）")
    p.add_argument("--floor", default="12/18", help="楼层（house）")
    p.add_argument("--orientation", default="南", help="朝向（house）")
    p.add_argument("--subway", default="地铁 3 号线 200 米", help="交通（house）")
    p.add_argument("--school", default="实验小学", help="教育配套（house）")
    p.add_argument("--compare", type=int, default=12, help="同小区在挂套数（house）")
    p.add_argument("--variant", default="2021款 330TSI", help="车款（car）")
    p.add_argument("--mileage", type=float, default=3.6, help="表显里程（万公里，car）")
    p.add_argument("--year", type=int, default=2021, help="上牌年份（car）")
    p.add_argument("--displacement", default="2.0T", help="排量（car）")
    p.add_argument("--gearbox", default="湿式双离合", help="变速箱（car）")
    p.add_argument("--transfer", type=int, default=0, help="过户次数（car）")
    p.add_argument("--interior", default="黑色真皮", help="内饰（car）")
    p.add_argument("--fee", type=float, default=0.3, help="过户费（万，car）")
    p.add_argument("--ins", type=float, default=0.5, help="保险（万，car）")
    p.add_argument("--seconds", type=int, default=30, help="主片秒数（默认 30）")
    p.add_argument("--short-seconds", dest="short_seconds", type=int, default=15,
                   help="快切版秒数（默认 15；给 0 就只交主片）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1],
                   help="配乐 1 首（默认 1）")
    p.add_argument("--outdir", help="输出目录（默认 ~/.a7w/realestate/<kind>-<日期>）")


def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 房产汽车（中介房源 / 4S 车源短视频，走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/images/generations · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/media_services_33/music_generate · "
               "GET %s/api/v1/tasks/<task_id> · POST %s/api/v1/upload"
               % ((DEFAULT_HOST,) * 6),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 60 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="四条能力 + 端点 + 现查单价 + 平台尺寸（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一单 / 一天要多少钱（免费）", allow_abbrev=False)
    p.add_argument("--orders", type=int, default=1, help="几单（默认 1，一天 10 单是常规量）")
    p.add_argument("--seconds", type=int, default=30, help="主片秒数（默认 30）")
    p.add_argument("--short-seconds", dest="short_seconds", type=int, default=15,
                   help="快切版秒数（默认 15；给 0 就只算主片）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="成片分辨率（默认 1080P）")
    p.add_argument("--images", type=int, default=6, help="每单几张图（默认 6）")
    p.add_argument("--tts-chars", dest="tts_chars", type=int, default=250,
                   help="每单口播总字数（主片 + 快切版，默认 250）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1], help="配乐 1 首（默认 1）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="一单的脚本 / 文案 / 命名 / 交付单（免费，纯本地）",
                       allow_abbrev=False)
    add_listing_args(p)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("qc", help="交付前合规与结构检查（免费，纯本地）",
                       allow_abbrev=False)
    p.add_argument("--plan", help="plan.json 路径")
    p.add_argument("--text", help="直接检查一条文案")
    p.add_argument("--vertical", choices=["house", "car"], default="house",
                   help="--text 模式下的品类（默认 house）")
    p.add_argument("--platform", choices=PLATFORM_KEYS, default="beike",
                   help="--text 模式下的平台（默认 beike）")
    p.add_argument("--verify", default="", help="--text 模式下的核验码 / 报告编号")
    p.add_argument("--seconds", type=int, default=30, help="--text 模式下的时长")
    p.set_defaults(fn=cmd_qc)

    p = sub.add_parser("cover", help="出图：大门 / 户型图 / 内饰 / 仪表（6 点/张，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--kind", default="all",
                   help="all / gate / building / floorplan / living / bedroom / amenity / "
                        "front45 / interior / rear / detail / dash（默认 all）")
    p.add_argument("--n", type=int, default=1, help="每个图种出几张 1~4（默认 1）")
    add_listing_args(p)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_cover)

    p = sub.add_parser("voice", help="口播讲解（约 0.18 点/字，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--text", help="口播文案（500 字内）")
    p.add_argument("--script", help="从文本文件读口播稿")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro", help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3", help="mp3 / wav / opus")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色 ID（可选）")
    p.add_argument("--prefix", default="listing", help="稿子文件名前缀")
    p.add_argument("--outdir", help="稿子目录（默认 ~/.a7w/realestate/out）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="配乐（50 点起/首，要 --yes）", allow_abbrev=False)
    p.add_argument("--style", help="风格描述，例如「温暖钢琴加轻弦乐，92 BPM」")
    p.add_argument("--title", help="曲名（可选）")
    p.add_argument("--vertical", choices=["house", "car"], default="house",
                   help="按品类选默认风格（默认 house）")
    p.add_argument("--music-model", dest="music_model", default=MUSIC_MODEL,
                   help="Suno 模型（默认 %s）" % MUSIC_MODEL)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_music)

    p = sub.add_parser("film", help="一键成片（按秒计费，要 --yes）", allow_abbrev=False)
    p.add_argument("--text", help="画面与运镜描述（把 plan 的 videoPrompt 粘过来）")
    p.add_argument("--image", help="首帧图：本地路径（自动上传）或平台地址")
    p.add_argument("--seconds", type=int, default=15, help="单段秒数 4~15（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--ratio", choices=RATIOS, default=None,
                   help="画幅（默认按 --platform；不给平台就是 9:16）")
    p.add_argument("--platform", choices=PLATFORM_KEYS,
                   help="按平台取默认画幅（可选）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把地址交给上游判断")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_film)

    p = sub.add_parser("upload", help="上传本地图，拿白名单地址（免费）",
                       allow_abbrev=False)
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


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_qc", "cmd_log", "cmd_doctor")
LOCAL_ONLY = ("cmd_plan", "cmd_qc")      # 纯本地，没有 Key 也能跑


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
