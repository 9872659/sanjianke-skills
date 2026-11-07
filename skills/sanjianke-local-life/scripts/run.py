#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 本地生活视频（sanjianke-local-life）

门店 / 餐饮的探店与团购短视频。本包不新造接口，把 api.a7w.cn 上已有的六条能力
按「一个门店运营一天要交的东西」重新排了顺序：

  选参考   watermark_removal  POST /api/v1/apps/watermark_removal/douyin_search_video   100 点/次
                              POST /api/v1/apps/watermark_removal/xhs_search_note       100 点/次
  出图     gpt-image-2.6      POST /api/v1/images/generations                          6 点/张
  口播     voice_tts          POST /api/v1/apps/voice_tts/tts                          约 0.18 点/字
  配乐     media_services_33  POST /api/v1/apps/media_services_33/music_generate       50 点起/首
  成片     full_video         POST /api/v1/apps/full_video/submit                      按秒 x 分辨率
  查进度   GET /api/v1/tasks/<task_id>                                                 0 点
  传图     POST /api/v1/upload                                                         0 点

## 成片单价（GET /api/v1/pricing 现查，单位：点/秒）

  480P 14   768P 28   1080P 60   2K 80   4K 80
  一条 25 秒的 1080P 探店片 = 60 x 25 = 1,500 点 = 15 元
  full_video 单段只能 4~15 秒，25 秒要拆成 15 + 10 两段，按总秒数计费。

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

  plan  一天 N 条门店矩阵：五段结构、口播、团购文案、同城标签、封面 prompt、命名规范
  qc    交付前合规检查：绝对化用语、价格锚、行动号召、同城标签、时长

## 子命令

  catalog  六条能力 + 端点 + 现查单价（免费）
  cost     一天出几条要多少钱（免费）
  plan     门店矩阵脚本与交付单（免费，纯本地）
  qc       合规与交付检查（免费，纯本地）
  ref      同城爆款参考，100 点/次（要 --yes）
  shop     门店图 / 菜品图 / 团购封面，6 点/张（要 --yes）
  voice    口播配音，约 0.18 点/字（要 --yes）
  music    门店配乐，50 点起（要 --yes）
  film     一键成片，按秒计费（要 --yes）
  upload   上传本地图，拿白名单地址（免费）
  status   查任务进度（免费）
  doctor   自检 Key / 应用 / 价目 / 端点（免费，不扣费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --shops 1 --seconds 25 --resolution 1080P
  python3 scripts/run.py plan --shop "老灶门火锅" --city 成都 --category 火锅 \
      --dish "牛油锅底" --price 88 --offer "双人餐"
  python3 scripts/run.py qc --plan ~/.a7w/local-life/20261108/plan.json
  python3 scripts/run.py ref --keyword "成都 火锅 探店" --platform dy --yes
  python3 scripts/run.py shop --kind cover --shop "老灶门火锅" --dish "牛油锅底" --yes
  python3 scripts/run.py voice --text "在成都春熙路，这家老灶门火锅..." --yes
  python3 scripts/run.py music --style "轻快城市探店 vlog" --yes
  python3 scripts/run.py film --text "..." --image cover.png --seconds 15 --yes
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

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "local-life")
LEDGER = os.path.join(HOME_DIR, "ledger.json")
LATEST_REF = os.path.join(HOME_DIR, "latest-ref.json")
OUT_ROOT = os.path.join(HOME_DIR, "out")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-local-life/%s" % VERSION

# ── 六条能力（单价：GET /api/v1/pricing 2026-11-08 现查）────────────────────
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

APP_REF = "watermark_removal"
REF_POINTS = 100                     # 点/次，flat，8 个接口同价

UPLOAD_PATH = API_PREFIX + "/upload"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 6000                # 点 = 60 元，一天 5 条的默认上限

RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]
RATIOS = ["9:16", "16:9", "1:1", "4:3", "3:4", "adaptive"]
PLATFORMS = {"dy": "抖音", "xhs": "小红书"}

PLATFORM_NAME = {"douyin": "抖音", "xhs": "小红书"}

# ── 5 条门店矩阵：一个门店一天要交的五个角度（行业里真这么排）─────────────
MATRIX = [
    dict(key="hook", name="门头钩子篇", focus="门头招牌、街景、排队",
         why="同城流量池先认位置，3 秒内让人知道你在哪条街",
         cta="导航搜「{shop}」，报「抖音来的」送{bonus}"),
    dict(key="dish", name="招牌菜特写篇", focus="招牌菜出锅、锅气、筷子夹起",
         why="馋点怼到镜头前，完播率靠这一条",
         cta="团购在左下角，到店出示核销码"),
    dict(key="price", name="价格锚点篇", focus="团购页、菜量对比、账单",
         why="把团购价和单点价摆一起，转化靠差价说话",
         cta="{price} 元{offer}，点左下角直接拍"),
    dict(key="owner", name="老板出镜篇", focus="老板、手部动作、明档厨房",
         why="一句人话换信任，评论区会替你解释价格",
         cta="到店说「看视频来的」，加一份{bonus}"),
    dict(key="regular", name="老客回头篇", focus="顾客、空盘、回头客",
         why="用别人的嘴替你说话，新客最吃这一套",
         cta="评论区置顶团购链接，今晚 {window} 前可用"),
]

HOT_WORDS = ["人均", "本地人", "藏在", "排队", "不起眼", "几块钱", "吃到撑",
             "回头客", "老店", "现点现做", "闭眼冲", "工作日", "隐藏", "深夜"]

ABSOLUTE_WORDS = ["最", "第一", "顶级", "唯一", "绝对", "全网", "史低", "永久",
                  "100%", "国家级", "零差评", "天花板"]


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


# ───────────────────────── 门店矩阵（纯本地，0 点）─────────────────────────
def _money(n):
    return "%d" % int(round(n))


def _shop_meta(a, shop):
    price = float(a.price)
    listprice = round(price / 0.55 / 5.0) * 5
    if listprice <= price:
        listprice = price * 2
    return dict(
        shop=shop, city=a.city, district=a.district, category=a.category,
        dish=a.dish, price=_money(price), listprice=_money(listprice),
        save=_money(listprice - price), avg=_money(price / 2.0),
        offer=a.offer, bonus=a.bonus, window=a.window,
        address=a.address or "%s%s" % (a.city, a.district),
        years=a.years, people=2, seats=a.seats, phone=a.phone or "")


def _beats(meta, angle_key, seconds):
    """五段结构，秒数按比例分配：门头 12% / 环境 20% / 招牌菜 32% / 价格 24% / 行动号召 12%。"""
    marks = [0.0, 0.12, 0.32, 0.64, 0.88, 1.0]
    edges = [round(seconds * m, 1) for m in marks]
    edges[0], edges[-1] = 0.0, float(seconds)
    spans = []
    for i in range(5):
        spans.append("%s-%s 秒" % (_trim(edges[i]), _trim(edges[i + 1])))

    m = meta
    lines = {
        "hook": [
            "在%s%s，这家%s，中午十一点就开始排队。" % (m["city"], m["district"], m["shop"]),
            "店里 %d 张桌，翻台快，两个人来不用等太久。" % m["seats"],
            "招牌%s，%s %s 元。" % (m["dish"], m["offer"], m["price"]),
            "%s 元，同样的菜单点要 %s 元。" % (m["price"], m["listprice"]),
            "导航搜「%s」，报「抖音来的」，送%s。" % (m["shop"], m["bonus"]),
        ],
        "dish": [
            "先看这份%s，%s。" % (m["dish"], m["offer"]),
            "明档厨房，现点现做，后面那口锅一直在滚。",
            "出锅这一下，热气直接糊镜头，%s份量给到 %d 个人。" % (m["dish"], m["people"]),
            "%s 元这一桌，两个人吃到撑，人均 %s 元。" % (m["price"], m["avg"]),
            "左下角团购，到店出示核销码。",
        ],
        "price": [
            "%s这份%s，%s 元。" % (m["shop"], m["offer"], m["price"]),
            "同样一桌按菜单点要 %s 元，中间差 %s 元。" % (m["listprice"], m["save"]),
            "%s给的是 %d 人份，不是小份试吃。" % (m["dish"], m["people"]),
            "人均 %s 元，%s这个地段算实在。" % (m["avg"], m["city"]),
            "团购点左下角，%s 可用。" % m["window"],
        ],
        "owner": [
            "我是%s的老板，店开了 %d 年。" % (m["shop"], m["years"]),
            "后厨现做，%s每天现熬。" % m["dish"],
            "%s，我不靠这个赚钱，靠你再来。" % m["offer"],
            "%s 元，够两个人吃；单点要 %s 元。" % (m["price"], m["listprice"]),
            "到店说「看视频来的」，加一份%s。" % m["bonus"],
        ],
        "regular": [
            "这家%s，我一个月来四次。" % m["shop"],
            "每次坐同一个位置，冲这口%s。" % m["dish"],
            "%s，两个人吃刚好，%s 元。" % (m["offer"], m["price"]),
            "比我单点便宜 %s 元，人均才 %s 元。" % (m["save"], m["avg"]),
            "评论区置顶团购，%s 前可用。" % m["window"],
        ],
    }[angle_key]

    shots = {
        "hook": ["街边推到门头招牌，门口排队/热气", "推门进店，扫一圈桌椅和明档",
                 "招牌菜出锅特写，筷子夹起", "团购页截图 + 菜量对比", "招牌定格 + 门店定位"],
        "dish": ["门头 1 秒带过，直接进后厨", "明档窗口，师傅手上动作",
                 "出锅、拉丝、汤面翻滚，三个特写", "整桌俯拍 + 团购价字幕", "空盘 + 门店定位"],
        "price": ["门头 + 团购价大字号", "菜单/账单特写", "菜量与手/餐具对比",
                  "团购页滑动 + 价格锚点", "二维码/左下角箭头 + 定位"],
        "owner": ["老板站门口，胸牌/围裙", "后厨手部动作，不拍脸也行",
                  "老板端菜上桌，一句话", "老板指菜单价 + 团购价", "老板说口令 + 定位"],
        "regular": ["门口等位的人", "老客坐下，点单手势", "菜上桌，老客第一口",
                    "空盘 + 账单", "老客对镜头一句话 + 定位"],
    }[angle_key]

    return [{"at": spans[i], "beat": ["门头", "环境", "招牌菜", "价格", "行动号召"][i],
             "shot": shots[i], "line": lines[i]} for i in range(5)]


def _trim(v):
    v = round(float(v), 1)
    return int(v) if abs(v - int(v)) < 1e-6 else v


def _titles(meta, key):
    m = meta
    pool = {
        "hook": [
            "%s本地人带路：%s的%s，%s 元双人餐" % (m["city"], m["shop"], m["dish"], m["price"]),
            "门头不起眼，%s这家%s中午就排队" % (m["city"], m["shop"]),
            "%s｜%s 元吃到人均 %s 元的%s" % (m["shop"], m["price"], m["avg"], m["dish"]),
        ],
        "dish": [
            "%s出锅这一下，%s人懂的都懂" % (m["dish"], m["city"]),
            "%s的%s，%s 元两个人吃到撑" % (m["shop"], m["dish"], m["price"]),
            "%s%s｜这锅%s值一次专程" % (m["city"], m["category"], m["dish"]),
        ],
        "price": [
            "%s 元 vs %s 元：%s这份%s怎么点" % (m["price"], m["listprice"], m["shop"], m["offer"]),
            "%s人均 %s 元的%s，%s 元拿下" % (m["city"], m["avg"], m["dish"], m["price"]),
            "在%s花 %s 元，吃出 %s 元的排面" % (m["shop"], m["price"], m["listprice"]),
        ],
        "owner": [
            "开了 %d 年的%s，老板一句话把价格说透了" % (m["years"], m["shop"]),
            "%s老板：%s 元这份%s，靠你再来" % (m["shop"], m["price"], m["offer"]),
            "%s老店｜%s每天现熬，%s 元双人餐" % (m["city"], m["dish"], m["price"]),
        ],
        "regular": [
            "%s回头客常来的%s，我一个月来四次" % (m["city"], m["shop"]),
            "隔壁桌说：这家%s一个月来四次" % m["shop"],
            "%s｜%s 元，老客带朋友来的那种店" % (m["shop"], m["price"]),
        ],
    }[key]
    return pool


def _group_buy(meta, key):
    m = meta
    points = [
        "%s，%s 元（单点 %s 元）" % (m["offer"], m["price"], m["listprice"]),
        "%s给 %d 人份，人均 %s 元" % (m["dish"], m["people"], m["avg"]),
        "%s%s，到店出示核销码" % (m["address"], m["window"]),
    ]
    return {"title": "【%s%s】%s｜%s 元%s" % (m["city"], m["category"], m["shop"],
                                            m["price"], m["offer"]),
            "points": points,
            "anchor": "%s 元团购 / %s 元单点，省 %s 元" % (m["price"], m["listprice"], m["save"]),
            "cta": MATRIX[[x["key"] for x in MATRIX].index(key)]["cta"].format(**m)}


def _tags(meta):
    m = meta
    return ["#%s美食" % m["city"], "#%s探店" % m["city"],
            "#%s%s" % (m["district"], m["category"]), "#%s" % m["shop"],
            "#%s" % m["dish"], "#%s团购" % m["city"], "#本地人推荐"]


def _cover_prompt(meta, key):
    m = meta
    scene = {
        "hook": "%s街边门头，招牌灯箱亮着，门口两三个人在等位" % m["shop"],
        "dish": "%s的%s刚出锅，热气腾腾，桌面有水汽" % (m["shop"], m["dish"]),
        "price": "%s整桌%s摆满，%s 元团购价签立在桌角" % (m["shop"], m["offer"], m["price"]),
        "owner": "%s老板端着%s站在明档前，围裙上有油点" % (m["shop"], m["dish"]),
        "regular": "%s靠窗座位，老客在吃%s，桌上有空盘" % (m["shop"], m["dish"]),
    }[key]
    return ("手机竖屏实拍，%s，暖黄灯光，真实探店质感，轻微手持感，"
            "画面干净，招牌位置留白后期加字，3:4 封面构图" % scene)


def _video_prompt(meta, key, seconds):
    m = meta
    focus = MATRIX[[x["key"] for x in MATRIX].index(key)]["focus"]
    return ("竖屏手机实拍探店，%s，%s，暖黄灯光，真实街景与店内环境，镜头稳定，"
            "画面无文字无水印，结尾定格门店招牌，整段 %d 秒内" % (m["shop"], focus, seconds))


def build_plan(a):
    shops = a.shop or []
    if not shops:
        raise Fail("usage", "先给 --shop（门店名，可重复给多家店），例如 "
                   "--shop \"老灶门火锅\" --shop \"巷子口串串\"", EXIT_USAGE)
    per = max(1, min(5, a.per_shop))
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds))
    angles = MATRIX[:per]
    videos, idx = [], 0
    for shop in shops:
        meta = _shop_meta(a, shop)
        for angle in angles:
            idx += 1
            beats = _beats(meta, angle["key"], seconds)
            voice = "".join([b["line"] for b in beats])
            name = "%s_%s_%02d_%s_%s_%ds" % (today(), meta["shop"], idx,
                                             angle["name"][:2], a.platform, seconds)
            videos.append({
                "no": idx, "shop": meta["shop"], "angle": angle["name"], "key": angle["key"],
                "why": angle["why"], "seconds": seconds,
                "clips": clips_for(seconds),
                "beats": beats, "voiceover": voice, "voiceChars": len(voice),
                "titles": _titles(meta, angle["key"]),
                "groupBuy": _group_buy(meta, angle["key"]),
                "tags": _tags(meta), "coverPrompt": _cover_prompt(meta, angle["key"]),
                "videoPrompt": _video_prompt(meta, angle["key"], seconds),
                "filename": name + ".mp4",
                "coverName": name + "_cover.png",
                "voiceName": name + "_voice.mp3",
            })
    res = a.resolution
    imgs = max(0, a.images)
    music = 1 if a.music else 0
    tts_total = int(round(sum(v["voiceChars"] for v in videos) * TTS_PER_CHAR))
    total = ((video_points(seconds, res) + imgs * IMG_POINTS) * len(videos)
             + tts_total + MUSIC_FLOOR * music)
    sample = videos[0]["filename"]
    totals = {"videos": len(videos), "videoSeconds": seconds, "clips": len(clips_for(seconds)),
              "resolution": res, "videoPoints": video_points(seconds, res) * len(videos),
              "imagePoints": imgs * IMG_POINTS * len(videos),
              "ttsPoints": tts_total,
              "musicPoints": MUSIC_FLOOR * music,
              "estimatedPoints": total, "yuan": yuan(total)}
    deliverables = [
        ("竖版成片", "1080x1920 / H.264 / %d 秒 / 9:16" % seconds, len(videos), sample),
        ("封面图", "1080x1440 / 3:4 / png", len(videos), sample[:-4] + "_cover.png"),
        ("口播音频", "mp3 / 44.1kHz / 单条 20~30 秒", len(videos),
         sample[:-4] + "_voice.mp3"),
        ("团购文案", "标题 3 条 + 卖点 3 条 + 价格锚 1 条", len(videos), "文案.md"),
        ("同城标签", "抖音 6 个 / 小红书 6 个", len(videos), "文案.md"),
        ("配乐", "一首 30 秒循环", music, "bgm.mp3"),
        ("当天交付单", "拍摄 / 剪辑 / 发布状态", 1, "当天交付单.md"),
    ]
    return {"ok": True, "generatedAt": now_iso(), "city": a.city,
            "district": a.district, "category": a.category, "shops": shops,
            "perShop": per, "videos": videos, "totals": totals,
            "deliverables": [{"name": n, "spec": s, "count": c, "naming": f}
                             for n, s, c, f in deliverables]}


def plan_markdown(plan, a):
    L = []
    L.append("# %s本地生活 · 当天交付单（%s）" % (plan["city"], today()))
    L.append("")
    L.append("门店：%s　｜　品类：%s　｜　条数：%d 条　｜　单条时长：%d 秒"
             % ("、".join(plan["shops"]), plan["category"],
                plan["totals"]["videos"], plan["totals"]["videoSeconds"]))
    L.append("")
    L.append("## 交付清单")
    L.append("")
    L.append("| # | 交付物 | 规格 | 数量 | 命名 |")
    L.append("|---|---|---|---|---|")
    for i, d in enumerate(plan["deliverables"], 1):
        L.append("| %d | %s | %s | %d | %s |"
                 % (i, d["name"], d["spec"], d["count"], d["naming"]))
    L.append("")
    L.append("## 当天拍摄顺序（先门头，再菜品，最后老板与老客）")
    L.append("")
    L.append("| # | 角度 | 为什么这条排这个位置 | 主镜头 |")
    L.append("|---|---|---|---|")
    for v in plan["videos"]:
        L.append("| %d | %s | %s | %s |" % (v["no"], v["angle"], v["why"],
                                            v["beats"][2]["shot"]))
    L.append("")
    for v in plan["videos"]:
        L.append("## %02d · %s（%s）" % (v["no"], v["angle"], v["filename"]))
        L.append("")
        L.append("| 时间 | 段落 | 画面 | 口播 |")
        L.append("|---|---|---|---|")
        for b in v["beats"]:
            L.append("| %s | %s | %s | %s |" % (b["at"], b["beat"], b["shot"], b["line"]))
        L.append("")
        L.append("- 口播总字数：%d 字（约 %d 秒，语速 4 字/秒）"
                 % (v["voiceChars"], max(1, int(v["voiceChars"] / 4))))
        L.append("- 成片提示词：%s" % v["videoPrompt"])
        L.append("- 封面提示词：%s" % v["coverPrompt"])
        L.append("")
    L.append("## 成本预估（1 元 = 100 点）")
    L.append("")
    L.append("| 项 | 点数 | 口径 |")
    L.append("|---|---|---|")
    t = plan["totals"]
    L.append("| 成片 %d 条 x %d 秒 | %s | %d 点/秒 x %d 秒 x %d 条 |"
             % (t["videos"], t["videoSeconds"], fmt_pts(t["videoPoints"]),
                VIDEO_RATES[t["resolution"]], t["videoSeconds"], t["videos"]))
    L.append("| 封面 %d 张 | %s | 6 点/张 |" % (t["videos"], fmt_pts(t["imagePoints"])))
    L.append("| 口播 | %s | 0.18 点/字 |" % fmt_pts(t["ttsPoints"]))
    L.append("| 配乐 | %s | 50 点起/首 |" % fmt_pts(t["musicPoints"]))
    L.append("| **合计** | **%s** | **%.2f 元** |"
             % (fmt_pts(t["estimatedPoints"]), t["yuan"]))
    L.append("")
    return "\n".join(L) + "\n"


def copy_markdown(plan, a):
    L = []
    L.append("# %s本地生活 · 文案包（%s）" % (plan["city"], today()))
    L.append("")
    for v in plan["videos"]:
        L.append("## %02d · %s · %s" % (v["no"], v["shop"], v["angle"]))
        L.append("")
        L.append("### 标题（三选一，同城流量池里轮着用）")
        for i, t in enumerate(v["titles"], 1):
            L.append("%d. %s" % (i, t))
        L.append("")
        g = v["groupBuy"]
        L.append("### 团购文案")
        L.append("")
        L.append("**%s**" % g["title"])
        L.append("")
        for p in g["points"]:
            L.append("- %s" % p)
        L.append("")
        L.append("价格锚点：%s" % g["anchor"])
        L.append("")
        L.append("行动号召：%s" % g["cta"])
        L.append("")
        L.append("### 同城标签")
        L.append("")
        L.append(" ".join(v["tags"]))
        L.append("")
        L.append("### 口播（%d 字）" % v["voiceChars"])
        L.append("")
        L.append(v["voiceover"])
        L.append("")
    return "\n".join(L) + "\n"


def cmd_plan(a, key, host):
    plan = build_plan(a)
    outdir = a.outdir or os.path.join(HOME_DIR, "%s-%s" % (a.city, today()))
    jp = os.path.join(outdir, "plan.json")
    dp = os.path.join(outdir, "当天交付单.md")
    cp = os.path.join(outdir, "文案.md")
    write_text(jp, json.dumps(plan, ensure_ascii=False, indent=1))
    write_text(dp, plan_markdown(plan, a))
    write_text(cp, copy_markdown(plan, a))
    out = {"ok": True, "mode": "plan", "shopCount": len(plan["shops"]),
           "videos": len(plan["videos"]), "seconds": plan["totals"]["videoSeconds"],
           "estimatedPoints": plan["totals"]["estimatedPoints"],
           "yuan": plan["totals"]["yuan"],
           "files": {"plan": jp, "delivery": dp, "copy": cp}}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("一天 %d 条门店矩阵 · %s（纯本地，0 点）"
          % (len(plan["videos"]), "、".join(plan["shops"])))
    print("=" * 76)
    print("  %s %s %s %s" % (pad("#", 3), pad("角度", 18), pad("主镜头", 30), "命名"))
    print("  " + "-" * 72)
    for v in plan["videos"]:
        print("  %s %s %s %s" % (pad(v["no"], 3), pad(v["angle"], 18),
                                 pad(v["beats"][2]["shot"][:28], 30), v["filename"]))
    print()
    print("  交付清单：%d 条成片 / %d 张封面 / %d 条口播 / %d 首配乐 / 1 份交付单"
          % (len(plan["videos"]), len(plan["videos"]), len(plan["videos"]),
             plan["totals"]["musicPoints"] // MUSIC_FLOOR))
    print("  预估成本：%s 点 = %.2f 元（%s，%d 点/秒）"
          % (fmt_pts(plan["totals"]["estimatedPoints"]), plan["totals"]["yuan"],
             plan["totals"]["resolution"], VIDEO_RATES[plan["totals"]["resolution"]]))
    print()
    print("  已写：")
    print("    %s" % jp)
    print("    %s" % dp)
    print("    %s" % cp)
    print()
    print("  下一步：`qc --plan %s` 过一遍合规，再 `shop` / `voice` / `music` / `film`。" % jp)
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
    elif a.text:
        videos = [{"no": 1, "angle": "手工文案", "titles": [a.text],
                   "groupBuy": {"title": a.text, "points": [a.text], "anchor": a.text,
                                "cta": a.text},
                   "tags": [], "voiceover": a.text, "voiceChars": len(a.text),
                   "seconds": a.seconds}]
    else:
        raise Fail("usage", "给 --plan plan.json 或 --text \"一条文案\" 再检查", EXIT_USAGE)

    if not videos:
        raise Fail("usage", "这份 plan 里没有视频，先补 --per-shop 再生成", EXIT_USAGE)

    for v in videos:
        blob = " ".join([str(x) for x in v.get("titles") or []])
        g = v.get("groupBuy") or {}
        blob += " " + str(g.get("title") or "") + " " + " ".join(g.get("points") or [])
        blob += " " + str(g.get("cta") or "") + " " + str(v.get("voiceover") or "")
        hits = [w for w in ABSOLUTE_WORDS if w in blob]
        if hits:
            bad("%02d 标题/文案" % v.get("no", 0), "绝对化用语：%s" % "、".join(hits))
        if not re.search(r"\d+\s*元", blob):
            bad("%02d 文案" % v.get("no", 0), "没看到具体价格（写「88 元」而不是「很便宜」）")
        tags = v.get("tags") or []
        if tags and len(tags) < 3:
            bad("%02d 标签" % v.get("no", 0), "同城标签少于 3 个")
        if not re.search(r"到店|团购|左下角|导航|定位|核销|评论区", blob):
            bad("%02d 文案" % v.get("no", 0), "缺行动号召（到店 / 团购 / 左下角 / 导航）")
        if int(v.get("seconds") or 0) > 60:
            bad("%02d 时长" % v.get("no", 0), "单条超过 60 秒，同城流量池里完播会被拖低")

    checks.append(("绝对化用语", not any("绝对化用语" in p["problem"] for p in problems),
                   "最 / 第一 / 顶级 这类词换成可验证描述"))
    checks.append(("具体价格", not any("具体价格" in p["problem"] for p in problems),
                   "每条文案都有「N 元」价格锚"))
    checks.append(("同城标签", not any("同城标签" in p["problem"] for p in problems),
                   "每条 3 个以上，城市 + 商圈 + 品类"))
    checks.append(("行动号召", not any("行动号召" in p["problem"] for p in problems),
                   "到店 / 团购 / 左下角 / 导航，至少一个"))
    checks.append(("时长", not any("时长" in p["problem"] for p in problems),
                   "单条 15~60 秒，25 秒是探店最稳的档"))
    out = {"ok": not problems, "checkedVideos": len(videos),
           "problems": problems,
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("交付前检查 · %d 条（纯本地，0 点）" % len(videos))
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 12), dt))
    if problems:
        print()
        print("  要改的地方：")
        for p in problems:
            print("    · %s：%s" % (p["scope"], p["problem"]))
        print()
        print("  改完重跑：qc --plan <plan.json>")
        return EXIT_GATE
    print()
    print("  5 项全过，可以按交付单开拍。")
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
        {"step": "选参考", "app": APP_REF, "cmd": "ref",
         "endpoint": "POST /api/v1/apps/watermark_removal/douyin_search_video",
         "price": "%d 点/次" % REF_POINTS, "note": "同城爆款；8 个接口同价，失败亦计"},
        {"step": "出图", "app": APP_IMAGE, "cmd": "shop",
         "endpoint": "POST /api/v1/images/generations",
         "price": "%d 点/张" % IMG_POINTS, "note": "门头图 / 菜品图 / 3:4 团购封面"},
        {"step": "口播", "app": APP_TTS, "cmd": "voice",
         "endpoint": "POST /api/v1/apps/voice_tts/tts",
         "price": "约 %.2f 点/字" % TTS_PER_CHAR, "note": "上游真实点数 x 3，单笔保底 > 0"},
        {"step": "配乐", "app": APP_MUSIC, "cmd": "music",
         "endpoint": "POST /api/v1/apps/media_services_33/music_generate",
         "price": "%d 点起/首" % MUSIC_FLOOR, "note": "落通配：上游 x 2，保底 50 点"},
        {"step": "成片", "app": APP_VIDEO, "cmd": "film",
         "endpoint": "POST /api/v1/apps/full_video/submit",
         "price": "480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒",
         "note": "单段 4~15 秒；25 秒拆 15 + 10，按总秒数计费"},
        {"step": "查进度", "app": "网关", "cmd": "status",
         "endpoint": "GET /api/v1/tasks/<task_id>",
         "price": "0 点", "note": "应用层 /query 每查一次都是钱"},
        {"step": "传图", "app": "网关", "cmd": "upload",
         "endpoint": "POST /api/v1/upload",
         "price": "0 点", "note": "换 oss.gpu.likeadmin.cn 白名单地址"},
        {"step": "脚本 / 检查", "app": "本地", "cmd": "plan / qc",
         "endpoint": "纯本地，不发请求", "price": "0 点", "note": "五段结构 / 文案 / 标签 / 合规"},
    ]
    for r in rows:
        r["online"] = (r["app"] in online) or r["app"] in ("网关", "本地")
        r["apis"] = len(online.get(r["app"], {}).get("apis") or [])
    out = {"ok": True, "rows": rows, "appsOnline": len(listing),
           "musicApis": len(online.get(APP_MUSIC, {}).get("apis") or []),
           "videoRates": live or VIDEO_RATES, "pricingRead": st2 == 200,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 本地生活视频 —— 一天 5 条门店矩阵用到的 8 个动作（1 元 = 100 点）")
    print()
    print("  %s %s %s %s" % (pad("动作", 10), pad("子命令", 12), pad("端点", 58), "单价"))
    print("  " + "-" * 112)
    for r in rows:
        print("  %s %s %s %s" % (pad(r["step"], 10), pad(r["cmd"], 12),
                                 pad(r["endpoint"], 58), r["price"]))
        print("        %s" % r["note"])
    print()
    print("  本站应用目录 %d 个；media_services_33 在架 %d 个接口（配乐取 music_generate）。"
          % (len(listing), out["musicApis"]))
    print("  full_video 现查按秒价：%s" % " · ".join(
        "%s %s" % (r, (live or VIDEO_RATES).get(r)) for r in RESOLUTIONS))
    print("  一条 25 秒 1080P = 60 x 25 = 1,500 点 = 15 元；一天 5 条 = 75 元起。")
    return 0


def cmd_cost(a, key, host):
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds))
    shops = max(1, int(a.shops))
    per = max(1, min(5, a.per_shop))
    videos = shops * per
    res = a.resolution
    imgs = max(0, a.images)
    tts_chars = max(0, a.tts_chars)
    music = 1 if a.music else 0

    vpts = video_points(seconds, res) * videos
    ipts = imgs * IMG_POINTS * videos
    tpts = int(round(tts_chars * videos * TTS_PER_CHAR))
    mpts = MUSIC_FLOOR * music
    refs = max(0, a.refs) * REF_POINTS
    total = vpts + ipts + tpts + mpts + refs

    items = [
        ("成片 %d 条 x %d 秒" % (videos, seconds), vpts,
         "%d 点/秒 x %d 秒 x %d 条（拆 %d 段）"
         % (VIDEO_RATES[res], seconds, videos, len(clips_for(seconds)))),
        ("门店图 %d 张" % (imgs * videos), ipts, "6 点/张 x %d 条" % videos),
        ("口播 %d 条" % videos, tpts, "%d 字/条 x 0.18 点/字" % tts_chars),
        ("配乐 %d 首" % music, mpts, "50 点起/首（上游 x 2，保底 50）"),
    ]
    if refs:
        items.append(("同城参考 %d 次" % (refs // REF_POINTS), refs, "100 点/次"))
    matrix = [{"resolution": r, "rate": VIDEO_RATES[r],
               "oneVideo": video_points(seconds, r),
               "dayPoints": video_points(seconds, r) * videos + ipts + tpts + mpts + refs}
              for r in RESOLUTIONS]
    out = {"ok": True, "shops": shops, "perShop": per, "videos": videos,
           "seconds": seconds, "clipsPerVideo": len(clips_for(seconds)),
           "resolution": res, "images": imgs, "ttsChars": tts_chars, "music": music,
           "items": [{"name": n, "points": p, "basis": b} for n, p, b in items],
           "total": total, "yuan": yuan(total), "yuanPerVideo": yuan(total / float(videos)),
           "matrix": matrix, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "unitPrice": {"image": IMG_POINTS, "ttsPerChar": TTS_PER_CHAR,
                         "musicFloor": MUSIC_FLOOR, "video": VIDEO_RATES,
                         "ref": REF_POINTS},
           "notes": ["1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-08 现查）",
                     "full_video 按总秒数 x 分辨率计费，单段 4~15 秒",
                     "口播按上游真实点数 x 3；实测 33 字 5.94 点，按 0.18 点/字估",
                     "配乐落通配规则，50 点是下限，实际以返回 usage.points_cost 为准",
                     "同城参考 100 点/次是 flat，与返回多少条无关"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("一天 %d 条门店矩阵要多少钱（1 元 = 100 点）" % videos)
    print()
    print("  门店 %d 家 x 每家 %d 条 = %d 条，单条 %d 秒（拆 %d 段），%s"
          % (shops, per, videos, seconds, len(clips_for(seconds)), res))
    print("  " + "-" * 74)
    for n, p, b in items:
        print("  %s %s 点   %s" % (pad(n, 26), pad(fmt_pts(p), 9, left=False), b))
    print("  " + "-" * 74)
    print("  %s %s 点   = %.2f 元（单条约 %.2f 元）"
          % (pad("合计", 26), pad(fmt_pts(total), 9, left=False), yuan(total),
             yuan(total / float(videos))))
    print()
    print("  同一批按分辨率（成片部分变，出图 / 口播 / 配乐不变）")
    print("    %s %s %s" % (pad("分辨率", 10), pad("单条成片", 12, left=False), "全天合计"))
    for r in matrix:
        print("    %s %s %s 点 = %.2f 元"
              % (pad(r["resolution"], 10), pad(fmt_pts(r["oneVideo"]), 12, left=False),
                 pad(fmt_pts(r["dayPoints"]), 9, left=False), yuan(r["dayPoints"])))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


# ───────────────────────── 同城爆款参考（100 点/次）─────────────────────────
def walk_items(node, out, depth=0):
    if depth > 8:
        return
    if isinstance(node, dict):
        title = None
        for k in ("desc", "title", "display_title", "caption", "note_title"):
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                title = v.strip()
                break
        stat = None
        for g in ("statistics", "stats", "interact_info", "count"):
            if isinstance(node.get(g), dict):
                stat = node[g]
                break
        if title and stat is not None:
            out.append((node, stat, title))
            return
        for v in node.values():
            walk_items(v, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            walk_items(v, out, depth + 1)


def _num(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v.strip().isdigit():
            return float(v.strip())
    return 0.0


def norm_items(payload):
    found = []
    walk_items(payload, found)
    items, seen = [], set()
    for node, stat, title in found:
        if title in seen:
            continue
        seen.add(title)
        dur = _num(stat, ("duration", "video_duration", "duration_ms")) or \
            _num(node, ("duration", "video_duration", "duration_ms"))
        if dur > 1000:
            dur = dur / 1000.0
        likes = _num(stat, ("digg_count", "like_count", "liked_count", "likes", "praise_count"))
        collects = _num(stat, ("collect_count", "collects", "collected_count"))
        comments = _num(stat, ("comment_count", "comments", "comments_count"))
        shares = _num(stat, ("share_count", "shares", "forward_count"))
        items.append({"title": title, "likes": likes, "collects": collects,
                      "comments": comments, "shares": shares,
                      "duration": round(dur, 1) if dur else None,
                      "heat": likes + collects * 2 + comments * 3 + shares * 4})
    items.sort(key=lambda x: -x["heat"])
    return items


def save_ref(code, keyword, payload, items, elapsed):
    try:
        ensure_dir(HOME_DIR)
        path = os.path.join(HOME_DIR, "ref-%s-%s.json" % (time.strftime("%Y%m%d-%H%M%S"), code))
        rec = {"at": now_iso(), "api": code, "keyword": keyword,
               "elapsed": round(elapsed, 1), "items": items, "raw": payload}
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(rec, ensure_ascii=False, indent=1))
        io.open(LATEST_REF, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"path": path, "at": rec["at"], "api": code,
                        "keyword": keyword, "count": len(items)},
                       ensure_ascii=False, indent=1))
        return path
    except Exception:                                                # noqa: BLE001
        return None


def bucket(dur):
    if not dur:
        return "未标注"
    if dur <= 15:
        return "15 秒内"
    if dur <= 30:
        return "15-30 秒"
    if dur <= 60:
        return "30-60 秒"
    return "60 秒以上"


def cmd_ref(a, key, host):
    code = "douyin_search_video" if a.platform == "dy" else "xhs_search_note"
    cost = REF_POINTS
    gate(a, cost, "同城参考（%s）1 次 x 100 点/次，flat、失败亦计"
         % PLATFORM_NAME["douyin" if a.platform == "dy" else "xhs"])
    url = host + API_PREFIX + "/apps/" + APP_REF + "/" + code
    body = {"keyword": a.keyword}
    if a.platform == "xhs" and getattr(a, "sort", None):
        body["sort"] = a.sort
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "api": code, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）· 失败亦计" % (cost, yuan(cost)))
        return 0

    say("正在搜同城参考「%s」…" % a.keyword)
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201) or (isinstance(d, dict) and d.get("code") == 0):
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "ref", "api": code,
                    "http": st, "error": msg, "keyword": a.keyword})
        raise Fail("call", "搜索失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    payload = payload_of(d)
    items = norm_items(payload)
    path = save_ref(code, a.keyword, payload, items, dt)
    buckets = {}
    for it in items:
        b = bucket(it.get("duration"))
        buckets[b] = buckets.get(b, 0) + 1
    words = []
    for w in HOT_WORDS:
        n = sum(1 for it in items if w in it["title"])
        if n:
            words.append({"word": w, "count": n})
    words.sort(key=lambda x: -x["count"])
    out = {"ok": True, "api": code, "platform": a.platform, "keyword": a.keyword,
           "count": len(items), "items": items[:a.top], "allCount": len(items),
           "durationBuckets": buckets, "hookWords": words[:8],
           "snapshot": path, "elapsed": round(dt, 1),
           "estimatedPoints": cost, "yuan": yuan(cost)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("%s同城参考「%s」（%.1fs · %d 点）"
          % (PLATFORM_NAME["douyin" if a.platform == "dy" else "xhs"],
             a.keyword, dt, cost))
    print("=" * 78)
    if not items:
        print("  这次没解析出条目，原始返回前 700 字：")
        print("  " + json.dumps(payload, ensure_ascii=False)[:700])
        if path:
            print("  快照：%s" % path)
        return 0
    print("  解析到 %d 条，热度榜（赞 1 + 藏 2 + 评 3 + 转 4）前 %d："
          % (len(items), min(a.top, len(items))))
    for i, it in enumerate(items[:a.top], 1):
        print("  %d. %s" % (i, it["title"][:56]))
        print("     赞 %s · 藏 %s · 评 %s · 时长 %s"
              % (fmt_pts(it["likes"]), fmt_pts(it["collects"]),
                 fmt_pts(it["comments"]),
                 "%ss" % it["duration"] if it["duration"] else "-"))
    print()
    print("  时长分布（照着这个排你的 25 秒）")
    for b in ("15 秒内", "15-30 秒", "30-60 秒", "60 秒以上", "未标注"):
        if buckets.get(b):
            print("    %s %d 条" % (pad(b, 10), buckets[b]))
    if words:
        print()
        print("  标题里出现最多的钩子词（写进你的门头 3 秒）")
        print("    " + " · ".join("%s x%d" % (w["word"], w["count"]) for w in words[:8]))
    print()
    if path:
        print("  快照：%s" % path)
    print("  下一步（0 点）：`plan` 把钩子词写进五段结构，`shop` 出封面，`film` 出片。")
    return 0


# ───────────────────────── 出图（6 点/张）─────────────────────────
KINDS = {
    "storefront": ("门头图", "手机竖屏实拍，{shop}的门头招牌，{city}{district}街边，"
                            "招牌灯箱亮着，门口两三个人等位，傍晚暖光，真实街拍质感，"
                            "店名位置留白后期加字，画面无文字无水印"),
    "dish": ("菜品图", "手机竖屏近距离实拍，{shop}的{dish}刚出锅，热气腾腾，"
                      "筷子夹起/汤汁翻滚，桌面有水汽，暖黄灯光，真实探店质感，无文字"),
    "cover": ("团购封面", "手机竖屏实拍，{shop}的{dish}与{offer}摆满一桌，"
                        "俯拍 3:4 构图，桌角立着价格牌位置留白，暖光，真实、有食欲，无文字"),
    "environment": ("环境图", "手机竖屏实拍，{shop}店内环境，木质桌椅、明档厨房，"
                            "有人在吃饭，暖黄灯光，真实探店质感，画面干净，无文字"),
}


def _save_image(outdir, prefix, idx, item, key, host):
    ensure_dir(outdir)
    b64 = item.get("b64_json") or item.get("b64") or item.get("image_base64")
    url = item.get("url") or item.get("image_url")
    if b64:
        raw = base64.b64decode(b64)
        path = os.path.join(outdir, "%s-%02d.png" % (prefix, idx))
        with open(path, "wb") as fh:
            fh.write(raw)
        return path, None
    if url:
        path = os.path.join(outdir, "%s-%02d.png" % (prefix, idx))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                with open(path, "wb") as fh:
                    fh.write(r.read())
            return path, url
        except Exception:                                            # noqa: BLE001
            return None, url
    return None, None


def cmd_shop(a, key, host):
    if a.kind not in KINDS:
        raise Fail("usage", "--kind 取 %s" % " / ".join(KINDS), EXIT_USAGE)
    n = max(1, min(4, a.n))
    cost = IMG_POINTS * n
    label, tpl = KINDS[a.kind]
    prompt = tpl.format(shop=a.shop, city=a.city, district=a.district,
                        dish=a.dish, offer=a.offer)
    if a.extra:
        prompt = prompt + "，" + a.extra
    body = {"model": APP_IMAGE, "prompt": prompt, "n": n, "size": "1024x1536"}
    gate(a, cost, "%s %d 张 x 6 点/张" % (label, n))
    url = host + IMAGE_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不出图、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）· %d 张" % (cost, yuan(cost), n))
        return 0

    say("正在出%s（%d 张）…" % (label, n))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=600)
    dt = time.time() - t0
    d = jloads(txt) or {}
    items = []
    if isinstance(d.get("data"), list):
        items = d["data"]
    elif isinstance(d.get("data"), dict) and isinstance(d["data"].get("data"), list):
        items = d["data"]["data"]
    if st not in (200, 201) or not items:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "shop", "http": st, "error": msg})
        raise Fail("call", "出图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = a.outdir or OUT_ROOT
    files, urls = [], []
    for i, it in enumerate(items, 1):
        p, u = _save_image(outdir, a.prefix or "shop", i, it, key, host)
        if p:
            files.append(p)
        if u:
            urls.append(u)
    out = {"ok": True, "mode": "shop", "kind": a.kind, "label": label,
           "requested": n, "returned": len(items), "elapsed": round(dt, 1),
           "files": files, "urls": urls, "prompt": prompt,
           "billedPoints": IMG_POINTS * len(items), "estimatedPoints": cost,
           "endpoint": IMAGE_PATH}
    ledger_add({"at": now_iso(), "ok": True, "mode": "shop", "kind": a.kind,
                "files": files, "points": IMG_POINTS * len(items)})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已出图（%.1fs · %d 点）" % (dt, IMG_POINTS * len(items)))
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
                   "也可以先 `plan` 生成文案.md 再粘过来", EXIT_USAGE)
    if len(text) > TTS_MAX_CHARS:
        raise Fail("usage", "这条 %d 字，同步 tts 建议 %d 字内；超过就按五段拆成两三条口播。"
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
    txt_path = os.path.join(outdir, "%s-voice.txt" % (a.prefix or "shop"))
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


def cmd_music(a, key, host):
    prompt = a.style or "轻快城市探店 vlog，鼓点清楚，适合 25 秒竖屏"
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
                           "  · 本地图直接给路径：--image cover.png（film 会自动 upload，免费）\n"
                           "  · 本站地址：https://oss.gpu.likeadmin.cn/openapi/…" % kind,
                           EXIT_USAGE)
            image_url = a.image
        else:
            if not os.path.isfile(a.image):
                raise Fail("usage", "找不到首帧图：%s" % a.image, EXIT_USAGE)

    content = [{"type": "text", "text": text}]
    body = {"model": "full-video", "content": content, "duration": seconds,
            "resolution": a.resolution, "ratio": a.ratio, "aigc_watermark": False}
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
           "seconds": seconds, "clips": clips_for(seconds),
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
    print("  规格：%s · %d 秒（拆 %s）" % (a.resolution, seconds,
                                        "+".join(str(x) for x in clips_for(seconds))))
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
    need = [APP_VIDEO, APP_TTS, APP_MUSIC, APP_REF]
    miss = [c for c in need if c not in online]
    checks.append(("4 个底层应用在架（成片 / 口播 / 配乐 / 参考）",
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

    ref_rule = pricing.get(API_PREFIX + "/apps/watermark_removal/*") or {}
    wild = pricing.get("*") or {}
    up_rule = pricing.get(API_PREFIX + "/upload") or {}
    ok_price = (int(ref_rule.get("cost") or 0) == REF_POINTS
                and int(wild.get("minPoints") or 0) == MUSIC_FLOOR
                and int(up_rule.get("cost") if up_rule.get("cost") is not None else 999) == 0)
    checks.append(("参考 100 点 + 配乐保底 50 点 + upload 0 点", ok_price,
                   "参考 %s · 通配保底 %s · upload %s"
                   % (ref_rule.get("cost"), wild.get("minPoints"), up_rule.get("cost"))))

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

    st6, txt6 = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-doctor-probe",
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
           "apps": need, "videoRates": live or VIDEO_RATES,
           "endpoints": {"ref": host + API_PREFIX + "/apps/" + APP_REF + "/douyin_search_video",
                         "image": host + IMAGE_PATH,
                         "tts": host + API_PREFIX + "/apps/" + APP_TTS + "/tts",
                         "music": host + API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate",
                         "film": host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit",
                         "task": host + API_PREFIX + "/tasks/<task_id>",
                         "upload": host + UPLOAD_PATH},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（4 个只读 GET + 1 个空 prompt 422 + 1 个空 body 视频探针 + 1 个缺 file 上传，"
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
    print("        POST /apps/watermark_removal/douyin_search_video（同城参考，100 点）")
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
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 本地生活视频（门店 / 餐饮的探店与团购短视频，走 api.a7w.cn）",
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

    p = sub.add_parser("catalog", help="六条能力 + 端点 + 现查单价（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一天出几条要多少钱（免费）", allow_abbrev=False)
    p.add_argument("--shops", type=int, default=1, help="门店数（默认 1）")
    p.add_argument("--per-shop", type=int, default=5, help="每家店几条（1~5，默认 5）")
    p.add_argument("--seconds", type=int, default=25, help="单条时长秒数（默认 25）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="成片分辨率（默认 1080P）")
    p.add_argument("--images", type=int, default=1, help="每条配几张图（默认 1 张封面）")
    p.add_argument("--tts-chars", type=int, default=90, help="每条口播字数（默认 90）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1], help="配乐 1 首（默认 1）")
    p.add_argument("--refs", type=int, default=0, help="同城参考搜索几次（100 点/次）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="一天 N 条门店矩阵脚本与交付单（免费，纯本地）",
                       allow_abbrev=False)
    p.add_argument("--shop", action="append", help="门店名（可重复给多家店）")
    p.add_argument("--city", default="成都", help="城市（默认 成都）")
    p.add_argument("--district", default="春熙路", help="商圈（默认 春熙路）")
    p.add_argument("--category", default="火锅", help="品类（默认 火锅）")
    p.add_argument("--dish", default="招牌锅底", help="招牌菜（默认 招牌锅底）")
    p.add_argument("--price", type=float, default=88, help="团购价（元，默认 88）")
    p.add_argument("--offer", default="双人餐", help="团购内容（默认 双人餐）")
    p.add_argument("--bonus", default="一份冰粉", help="到店口令赠品（默认 一份冰粉）")
    p.add_argument("--window", default="21:00", help="团购可用时间窗（默认 21:00）")
    p.add_argument("--address", help="门店地址（默认 城市+商圈）")
    p.add_argument("--phone", help="门店电话（可选）")
    p.add_argument("--years", type=int, default=5, help="开店年数（默认 5）")
    p.add_argument("--seats", type=int, default=12, help="店内桌数（默认 12）")
    p.add_argument("--per-shop", type=int, default=5, help="每家店几条（1~5，默认 5）")
    p.add_argument("--seconds", type=int, default=25, help="单条时长秒数（默认 25）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="成本预估用分辨率（默认 1080P）")
    p.add_argument("--images", type=int, default=1, help="每条配几张图（默认 1）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1], help="配乐 1 首（默认 1）")
    p.add_argument("--platform", choices=["dy", "xhs"], default="dy",
                   help="发布平台（默认 dy 抖音）")
    p.add_argument("--outdir", help="输出目录（默认 ~/.a7w/local-life/<城市>-<日期>）")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("qc", help="交付前合规与结构检查（免费，纯本地）",
                       allow_abbrev=False)
    p.add_argument("--plan", help="plan.json 路径")
    p.add_argument("--text", help="直接检查一条文案")
    p.add_argument("--seconds", type=int, default=25, help="--text 模式下的时长")
    p.set_defaults(fn=cmd_qc)

    p = sub.add_parser("ref", help="同城爆款参考（100 点/次，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--keyword", required=True, help="搜索词，例如「成都 火锅 探店」")
    p.add_argument("--platform", choices=["dy", "xhs"], default="dy",
                   help="dy 抖音 / xhs 小红书（默认 dy）")
    p.add_argument("--sort", help="小红书排序：popularity_descending / time_descending")
    p.add_argument("--top", type=int, default=5, help="看前几条（默认 5）")
    p.add_argument("--timeout", type=int, default=180, help="超时秒数（默认 180）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_ref)

    p = sub.add_parser("shop", help="门店图 / 菜品图 / 团购封面（6 点/张，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--kind", default="cover", help="storefront / dish / cover / environment")
    p.add_argument("--shop", default="本店", help="门店名（默认 本店）")
    p.add_argument("--city", default="成都", help="城市")
    p.add_argument("--district", default="春熙路", help="商圈")
    p.add_argument("--dish", default="招牌菜", help="招牌菜")
    p.add_argument("--offer", default="双人餐", help="团购内容")
    p.add_argument("--extra", help="追加到 prompt 的补充描述")
    p.add_argument("--n", type=int, default=1, help="张数 1~4（默认 1）")
    p.add_argument("--prefix", default="shop", help="文件名前缀（默认 shop）")
    p.add_argument("--outdir", help="图片目录（默认 ~/.a7w/local-life/out）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_shop)

    p = sub.add_parser("voice", help="口播配音（约 0.18 点/字，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--text", help="口播文案（500 字内）")
    p.add_argument("--script", help="从文本文件读口播稿")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro", help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3", help="mp3 / wav / opus")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色 ID（可选）")
    p.add_argument("--prefix", default="shop", help="稿子文件名前缀")
    p.add_argument("--outdir", help="稿子目录（默认 ~/.a7w/local-life/out）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="门店配乐（50 点起/首，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--style", help="风格描述，例如「轻快城市探店 vlog」")
    p.add_argument("--title", help="曲名（可选）")
    p.add_argument("--music-model", dest="music_model", default=MUSIC_MODEL,
                   help="Suno 模型（默认 %s）" % MUSIC_MODEL)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_music)

    p = sub.add_parser("film", help="一键成片（按秒计费，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--text", help="画面与运镜描述（把 plan 的 videoPrompt 粘过来）")
    p.add_argument("--image", help="首帧图：本地路径（自动上传）或平台地址")
    p.add_argument("--seconds", type=int, default=15, help="单段秒数 4~15（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--ratio", choices=RATIOS, default="9:16", help="画幅（默认 9:16）")
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
