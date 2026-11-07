#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 广告投放素材（sanjianke-ad-creative）

投手一天要交的不是「一张图」，是「一个卖点的一组素材」：
**一个卖点 x 5 个平台尺寸 x 3 个钩子 = 15 条**，两个卖点正好一批 30 条。

本包不新造接口，把 api.a7w.cn 上已有的五条能力按投放习惯重新排：

  出图     gpt-image-2.6      POST /api/v1/images/generations   6 点/张（n 1~4 一次多图）
  改图     gpt-image-2.6      POST /api/v1/images/edits         6 点/张（有实拍图，主体不走样）
  参考图   nano_banana        POST /api/v1/apps/nano_banana/submit  72 点/次（异步）
  视频素材 full_video         POST /api/v1/apps/full_video/submit  按秒 x 分辨率
  口播     voice_tts          POST /api/v1/apps/voice_tts/tts      约 0.18 点/字
  配乐     media_services_33  POST /api/v1/apps/media_services_33/music_generate  50 点起
  查进度   GET /api/v1/tasks/<task_id>                             0 点
  传图     POST /api/v1/upload                                     0 点

## 一批 30 条到底多少钱（1 元 = 100 点，2026-11-08 现查价目）

  全静态 30 张 6 点/张          180 点 = 1.80 元
  全视频 30 条 15 秒 1080P      27,000 点 = 270.00 元
  15 图 + 15 条 15 秒 1080P     13,590 点 = 135.90 元
  15 图 + 15 次 nano 多角度     1,170 点 = 11.70 元

## 投放尺寸（requests 都满足 gpt-image 的 16 倍数 / 3:1 / 655,360~8,294,400 像素）

  9x16  720x1280 -> 上架 1080x1920  巨量千川 / 抖音 / 视频号
  1x1   1024x1024 -> 上架 1080x1080 千川信息流 / 朋友圈 / 小红书
  16x9  1280x720 -> 上架 1920x1080  腾讯广告 / 激励视频
  3x4   1152x1536 -> 上架 1242x1660 小红书笔记
  4x5   1024x1280 -> 上架 1080x1350 朋友圈 / Instagram

## 三条用钱换来的规矩（都做成了默认动作）

  1. 轮询只走 GET /api/v1/tasks/<id>（cost:0）。应用层 /query 每查一次按该应用单价结算，
     nano_banana/query 实测 72 点/次，一天轮询 30 次就是 2,160 点。
  2. 要目录只看 GET /api/v1/apps 列表和 GET /api/v1/pricing。GET /api/v1/apps/<app>
     命中 /apps/<app>/* 通配计价，按 flat 单价即时扣费、不退（实测 dressing_diffusion
     200 点、nano_banana 72 点各一笔）。
  3. 首帧图与参考图必须是平台托管地址。外站地址一律 400 url_not_allowed，只认
     vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。
     本地图先 POST /api/v1/upload（免费）换地址，本包 film / img --ref 会自动做。

## 本地零成本的部分（0 点，不联网）

  plan  矩阵脚本：卖点 x 尺寸 x 钩子、主标副标、前 3 秒台词、命名、交付清单、A/B 排期
  qc    交付前检查：广告法用语、价格、钩子差异、行动号召、命名、尺寸、版本完整

## 子命令

  catalog  五条能力 + 端点 + 现查单价 + 尺寸表（免费）
  cost     一批 30 条多少钱，四种走法对比（免费）
  plan     素材矩阵与交付清单（免费，纯本地）
  qc       交付前检查（免费，纯本地）
  img      按尺寸出图，6 点/张（nano 72 点；要 --yes）
  film     视频素材，按秒计费（要 --yes）
  voice    口播配音，约 0.18 点/字（要 --yes）
  music    素材配乐，50 点起（要 --yes）
  upload   上传本地图，拿白名单地址（免费）
  status   查任务进度（免费）
  doctor   自检 Key / 应用 / 价目 / 端点（免费，不扣费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --sellpoints 2
  python3 scripts/run.py plan --sell "冰丝凉感" --sell "速干不皱"
  python3 scripts/run.py qc --plan ~/.a7w/ad-creative/20261108/plan.json
  python3 scripts/run.py img --size 9x16 --hook H1 --n 2 --yes
  python3 scripts/run.py film --size 9x16 --hook H1 --seconds 15 --yes
  python3 scripts/run.py voice --text "79 元到手，原价 129 元" --yes
  python3 scripts/run.py music --style "电子鼓点，节奏明快，适合 15 秒竖版" --yes
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

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "ad-creative")
LEDGER = os.path.join(HOME_DIR, "ledger.json")
OUT_ROOT = os.path.join(HOME_DIR, "out")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-ad-creative/%s" % VERSION

# ── 五条能力（单价：GET /api/v1/pricing 与流水实测，2026-11-08）────────────────
APP_IMAGE = "gpt-image-2.6"
IMG_POINTS = 6                        # 点/张，与尺寸 / 质量 / 格式无关（实测扣 6 点）
IMAGE_PATH = API_PREFIX + "/images/generations"
EDIT_PATH = API_PREFIX + "/images/edits"

APP_NANO = "nano_banana"
NANO_POINTS = 72                      # 点/次，flat（价目表 /apps/nano_banana/* cost 72）
NANO_VIEW_POINTS = 25                 # 商品多角度：25 点 x 选中视角数
NANO_PATH = API_PREFIX + "/apps/nano_banana/submit"
NANO_MODEL = "nano-banana"

APP_VIDEO = "full_video"
VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}   # 点/秒
VIDEO_CLIP_MIN, VIDEO_CLIP_MAX = 4, 15

APP_TTS = "voice_tts"
TTS_PER_CHAR = 0.18                   # 点/字（上游真实点数 x 3）
TTS_MAX_CHARS = 500

APP_MUSIC = "media_services_33"
MUSIC_FLOOR = 50                      # 点/首（落通配：上游 x 2、保底 50）
MUSIC_MODEL = "V6"

UPLOAD_PATH = API_PREFIX + "/upload"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 3000                 # 点 = 30 元，一天一批素材的默认上限

RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]

# ── 五个投放尺寸（requests 都是 gpt-image 合法尺寸）──────────────────────────
SIZES = {
    "9x16": dict(ratio="9:16", req="720x1280", publish="1080x1920",
                 platforms="巨量千川 / 抖音 / 视频号",
                 safe="顶部 12% 放角标，底部 18% 留白放行动号召"),
    "1x1": dict(ratio="1:1", req="1024x1024", publish="1080x1080",
                platforms="千川信息流 / 朋友圈 / 小红书",
                safe="主体居中偏上，四角留白放价格角标"),
    "16x9": dict(ratio="16:9", req="1280x720", publish="1920x1080",
                 platforms="腾讯广告 / 激励视频 / 开屏",
                 safe="主体居中，左侧 1/4 留白给标题"),
    "3x4": dict(ratio="3:4", req="1152x1536", publish="1242x1660",
                platforms="小红书笔记 / 蒲公英",
                safe="上 1/3 放主标，底部 15% 留白"),
    "4x5": dict(ratio="4:5", req="1024x1280", publish="1080x1350",
                platforms="朋友圈广告 / Instagram",
                safe="中心构图，顶部与底部各留 10%"),
}
SIZE_ORDER = ["9x16", "1x1", "16x9", "3x4", "4x5"]

# ── 三个钩子：投放素材前 3 秒抓人的三条路（同一个卖点，换三种说法）────────────
HOOKS = [
    dict(code="H1", name="价格钩", focus="到手价与差价摆在一起",
         why="价格是投放里最稳的钩子，前 3 秒报数字，点击率最好归因"),
    dict(code="H2", name="痛点钩", focus="场景里的具体难受",
         why="把用户当下的处境说出来，评论区会替你把痛点补完"),
    dict(code="H3", name="效果钩", focus="可验证的使用结果",
         why="用能复现的细节换信任，退货率比喊口号低"),
]
HOOK_ORDER = ["H1", "H2", "H3"]

ABSOLUTE_WORDS = ["最", "第一", "顶级", "唯一", "绝对", "全网", "史低", "永久",
                  "100%", "国家级", "零差评", "天花板", "秒杀"]
CTA_WORDS = ["领券", "点击", "下单", "购买", "进入", "立即", "搜索", "查看", "抢"]


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


# ───────────────────────── 矩阵（纯本地，0 点）─────────────────────────
def _hook_meta(code):
    for h in HOOKS:
        if h["code"] == code:
            return h
    raise Fail("usage", "--hook 取 %s" % " / ".join(HOOK_ORDER), EXIT_USAGE)


def _sell_meta(a, sell, no):
    price = float(a.price)
    listprice = float(a.list)
    if listprice <= price:
        listprice = round(price * 1.6)
    return dict(no="SP%02d" % no, sell=sell,
                price="%d" % int(round(price)), list="%d" % int(round(listprice)),
                save="%d" % int(round(listprice - price)),
                offer=a.offer, pain=a.pain, proof=a.proof,
                audience=a.audience, scene=a.scene, brand=a.brand)


def _copy(meta, hook):
    """一个卖点 x 一个钩子 = 一条素材的话术（前 3 秒、主标、副标、行动号召）。"""
    m = meta
    if hook["code"] == "H1":
        return dict(line="%s 元到手，原价 %s 元" % (m["price"], m["list"]),
                    headline="券后 %s 元" % m["price"],
                    subline="原价 %s · %s" % (m["list"], m["offer"]),
                    cta="点下方领券")
    if hook["code"] == "H2":
        return dict(line="%s，%s，还要忍到第几个夏天" % (m["scene"], m["pain"]),
                    headline="别再%s" % m["pain"],
                    subline="%s 的%s" % (m["audience"], m["sell"]),
                    cta="点击看 3 秒对比")
    return dict(line="%s，%s" % (m["proof"], m["sell"]),
                headline=m["proof"][:12],
                subline="%s 的实拍记录" % m["brand"] if m["brand"] else "实拍记录",
                cta="看实测再下单")


def _image_prompt(meta, hook, size):
    m = meta
    if hook["code"] == "H1":
        scene = "产品主体居中，旁边立价格牌位置留白，背景干净明亮"
    elif hook["code"] == "H2":
        scene = "%s 的场景还原，人物局部，情绪写在动作里" % m["scene"]
    else:
        scene = "产品使用前后对比构图，细节清晰，光线自然"
    return ("商业投放素材，%s，%s，%s，%s，真实质感，主体占画面六成，"
            "无文字无水印，%s 比例，%s"
            % (m["sell"], scene, m["audience"], m["brand"] or "简洁场景",
               size["ratio"], size["safe"]))


def _video_prompt(meta, hook, size, seconds):
    m = meta
    head = {
        "H1": "0-3 秒 产品特写 + 价格数字特写",
        "H2": "0-3 秒 场景里的具体难受，人物动作特写",
        "H3": "0-3 秒 使用结果对比，细节微距",
    }[hook["code"]]
    mid = "3-9 秒 产品细节与使用过程，%s" % m["sell"]
    tail = "9-%d 秒 价格与行动号召，画面定格产品" % int(seconds)
    return ("竖屏投放素材，%s，%s，%s，镜头稳定，真实质感，画面无文字无水印，"
            "整段 %d 秒内" % (head, mid, tail, int(seconds)))


def build_plan(a):
    sells = [s.strip() for s in (a.sell or []) if s.strip()]
    if not sells:
        raise Fail("usage", "先给 --sell（卖点，可重复给多个），例如 "
                   "--sell \"冰丝凉感\" --sell \"速干不皱\"", EXIT_USAGE)
    hooks = [_hook_meta(h) for h in (a.hooks or HOOK_ORDER)]
    sizes = [a.sizes] if a.sizes and a.sizes != "all" else SIZE_ORDER
    version = max(1, int(a.version))
    seconds = max(VIDEO_CLIP_MIN, min(VIDEO_CLIP_MAX, int(a.seconds)))

    assets, no = [], 0
    for i, sell in enumerate(sells, 1):
        meta = _sell_meta(a, sell, i)
        for hk in hooks:
            cp = _copy(meta, hk)
            for key in sizes:
                no += 1
                size = SIZES[key]
                name = "%s-%s_%s_v%d" % (meta["no"], hk["code"], key, version)
                assets.append({
                    "no": no, "sellNo": meta["no"], "sell": sell,
                    "hook": hk["code"], "hookName": hk["name"],
                    "hookWhy": hk["why"], "size": key,
                    "ratio": size["ratio"], "requestSize": size["req"],
                    "publishSize": size["publish"], "platforms": size["platforms"],
                    "safe": size["safe"], "version": "v%d" % version,
                    "headline": cp["headline"], "subline": cp["subline"],
                    "line": cp["line"], "cta": cp["cta"],
                    "imagePrompt": _image_prompt(meta, hk, size),
                    "videoPrompt": _video_prompt(meta, hk, size, seconds),
                    "seconds": seconds,
                    "filename": name + ".png",
                    "videoName": name + ".mp4",
                    "voiceName": name + "_voice.mp3",
                })

    with_video = bool(getattr(a, "with_video", False))
    n_img = len(assets)
    n_vid = len(sells) * len(hooks) if with_video else 0
    imgs_pts = IMG_POINTS * n_img
    vid_pts = video_points(seconds, a.resolution) * n_vid
    tts_chars = int(round(sum(len(x["line"]) for x in assets) / float(len(assets))))
    tts_pts = int(round(tts_chars * len(sells) * len(hooks) * TTS_PER_CHAR)) if with_video else 0
    music_pts = MUSIC_FLOOR if with_video else 0
    total = imgs_pts + vid_pts + tts_pts + music_pts
    full = (imgs_pts + video_points(seconds, a.resolution) * len(sells) * len(hooks)
            + int(round(tts_chars * len(sells) * len(hooks) * TTS_PER_CHAR)) + MUSIC_FLOOR)

    deliverables = [
        ("静态素材", "5 个尺寸 / png / 上架尺寸见矩阵", len(assets),
         assets[0]["filename"]),
        ("视频素材", "9:16 / H.264 / %d 秒 / 1080P" % seconds, len(sells) * len(hooks),
         assets[0]["videoName"]),
        ("口播", "mp3 / 单条约 %d 字（5 秒左右）" % tts_chars, len(sells) * len(hooks),
         assets[0]["voiceName"]),
        ("配乐", "30 秒循环 / 一条素材复用", 1, "bgm.mp3"),
        ("A/B 排期", "钩子 x 尺寸 x 版本，含预算比例", 1, "ab-plan.csv"),
        ("素材矩阵", "全量素材清单，可直接导入素材库", 1, "素材矩阵.csv"),
        ("迭代台账", "上线日 / CTR / 衰减判定 / 迭代日", 1, "迭代台账.md"),
    ]
    return {"ok": True, "generatedAt": now_iso(), "sells": sells,
            "hooks": [h["code"] for h in hooks], "sizes": sizes,
            "version": "v%d" % version, "seconds": seconds,
            "resolution": a.resolution, "withVideo": with_video, "assets": assets,
            "totals": {"assets": len(assets), "sells": len(sells),
                       "hooks": len(hooks), "sizes": len(sizes), "seconds": seconds,
                       "resolution": a.resolution,
                       "imagePoints": imgs_pts, "videoCount": len(sells) * len(hooks),
                       "videoPoints": vid_pts, "ttsChars": tts_chars,
                       "ttsPoints": tts_pts, "musicPoints": music_pts,
                       "estimatedPoints": total, "yuan": yuan(total),
                       "fullPoints": full, "fullYuan": yuan(full)},
            "deliverables": [{"name": n, "spec": s, "count": c, "naming": f}
                             for n, s, c, f in deliverables]}


def plan_markdown(plan, a):
    L = []
    L.append("# 投放素材 · 当天交付单（%s）" % today())
    L.append("")
    L.append("卖点：%s　｜　钩子：%s　｜　尺寸：%s　｜　版本：%s"
             % ("、".join(plan["sells"]), " / ".join(plan["hooks"]),
                " / ".join(plan["sizes"]), plan["version"]))
    L.append("")
    L.append("素材总数：%d 条（%d 卖点 x %d 钩子 x %d 尺寸），视频素材 %d 条"
             % (plan["totals"]["assets"], plan["totals"]["sells"],
                plan["totals"]["hooks"], plan["totals"]["sizes"],
                plan["totals"]["videoCount"]))
    L.append("")
    L.append("## 交付清单")
    L.append("")
    L.append("| # | 交付物 | 规格 | 数量 | 命名 |")
    L.append("|---|---|---|---|---|")
    for i, d in enumerate(plan["deliverables"], 1):
        L.append("| %d | %s | %s | %d | %s |"
                 % (i, d["name"], d["spec"], d["count"], d["naming"]))
    L.append("")
    L.append("## 矩阵总表（卖点 x 钩子 x 尺寸）")
    L.append("")
    L.append("| # | 卖点 | 钩子 | 尺寸 | 平台 | 上架尺寸 | 命名 |")
    L.append("|---|---|---|---|---|---|---|")
    for x in plan["assets"]:
        L.append("| %d | %s | %s %s | %s | %s | %s | %s |"
                 % (x["no"], x["sell"], x["hook"], x["hookName"], x["size"],
                    x["platforms"], x["publishSize"], x["filename"]))
    L.append("")
    L.append("## 每条素材的话术（前 3 秒 / 主标 / 副标 / 行动号召）")
    L.append("")
    for x in plan["assets"]:
        L.append("### %02d · %s · %s %s · %s" % (x["no"], x["sell"],
                                                 x["hook"], x["hookName"], x["size"]))
        L.append("")
        L.append("- 前 3 秒：%s" % x["line"])
        L.append("- 主标：%s（不超过 12 字）" % x["headline"])
        L.append("- 副标：%s（不超过 20 字）" % x["subline"])
        L.append("- 行动号召：%s" % x["cta"])
        L.append("- 出图提示词：%s" % x["imagePrompt"])
        L.append("- 视频提示词：%s" % x["videoPrompt"])
        L.append("")
    L.append("## 成本预估（1 元 = 100 点）")
    L.append("")
    L.append("| 项 | 本次计入 | 全量 | 口径 |")
    L.append("|---|---|---|---|")
    t = plan["totals"]
    vid_full = video_points(t["seconds"], t["resolution"]) * t["videoCount"]
    L.append("| 静态素材 %d 张 | %s | %s | 6 点/张（与尺寸无关） |"
             % (t["assets"], fmt_pts(t["imagePoints"]), fmt_pts(t["imagePoints"])))
    L.append("| 视频素材 %d 条 x %d 秒 | %s | %s | %d 点/秒 x %d 秒 |"
             % (t["videoCount"], t["seconds"], fmt_pts(t["videoPoints"]),
                fmt_pts(vid_full), VIDEO_RATES[t["resolution"]], t["seconds"]))
    L.append("| 口播 %d 条 | %s | %s | 约 0.18 点/字 |"
             % (t["sells"] * t["hooks"], fmt_pts(t["ttsPoints"]),
                fmt_pts(int(round(t["ttsChars"] * t["sells"] * t["hooks"]
                                 * TTS_PER_CHAR)))))
    L.append("| 配乐 1 首 | %s | %s | 50 点起/首 |"
             % (fmt_pts(t["musicPoints"]), fmt_pts(MUSIC_FLOOR)))
    L.append("| **合计** | **%s（%.2f 元）** | **%s（%.2f 元）** | 本次 = 只做静态；"
             "全量 = 加视频与口播 |"
             % (fmt_pts(t["estimatedPoints"]), t["yuan"],
                fmt_pts(t["fullPoints"]), t["fullYuan"]))
    L.append("")
    if not plan.get("withVideo"):
        L.append("本次只计静态素材：%d 张 x 6 点 = %d 点 = %.2f 元。"
                 % (t["assets"], t["imagePoints"], yuan(t["imagePoints"])))
        L.append("要让视频与口播也进预算，plan 加 `--with-video`（全量 %s 点 = %.2f 元）。"
                 % (fmt_pts(t["fullPoints"]), t["fullYuan"]))
        L.append("")
    L.append("## 素材衰减与迭代节奏")
    L.append("")
    L.append("| 时间 | 动作 | 判据 |")
    L.append("|---|---|---|")
    L.append("| D0 | 全部钩子各分 1/3 预算，等比跑量 | 每个钩子至少 3,000 次展示再判断 |")
    L.append("| D3 | 保留 CTR 前两名，预算集中 | 低于平均点击率 60% 的钩子先停 |")
    L.append("| D7 | 衰减判定 | CTR 比首日掉 30%，或 CPM 涨 50%，进淘汰位 |")
    L.append("| D14 | 出 v2：只换钩子，尺寸与卖点不动 | 一次只改一个变量，A/B 才归因 |")
    L.append("| 每两周 | 新一批 30 条 | 老素材留 2 条跑量，其余换新 |")
    L.append("")
    return "\n".join(L) + "\n"


def matrix_csv(plan):
    L = ["素材名,卖点编号,卖点,钩子,钩子名,尺寸,比例,请求尺寸,上架尺寸,平台,版本,"
         "主标,副标,行动号召,状态"]
    for x in plan["assets"]:
        L.append(",".join(['"%s"' % str(v).replace('"', "'") for v in (
            x["filename"], x["sellNo"], x["sell"], x["hook"], x["hookName"],
            x["size"], x["ratio"], x["requestSize"], x["publishSize"],
            x["platforms"], x["version"], x["headline"], x["subline"],
            x["cta"], "待出图")]))
    return "\n".join(L) + "\n"


def ab_csv(plan):
    L = ["轮次,钩子,尺寸,版本,素材名,预算比例,观察指标"]
    share = round(100.0 / max(1, len(plan["hooks"])), 1)
    for x in plan["assets"]:
        L.append(",".join(['"%s"' % str(v).replace('"', "'") for v in (
            "D0-%s" % x["size"], x["hook"], x["size"], x["version"],
            x["filename"], "%.1f%%" % share, "CTR / CVR / CPM")]))
    return "\n".join(L) + "\n"


def cmd_plan(a, key, host):
    plan = build_plan(a)
    outdir = a.outdir or os.path.join(HOME_DIR, today())
    jp = os.path.join(outdir, "plan.json")
    dp = os.path.join(outdir, "交付清单.md")
    mp = os.path.join(outdir, "素材矩阵.csv")
    ap = os.path.join(outdir, "ab-plan.csv")
    write_text(jp, json.dumps(plan, ensure_ascii=False, indent=1))
    write_text(dp, plan_markdown(plan, a))
    write_text(mp, matrix_csv(plan))
    write_text(ap, ab_csv(plan))
    out = {"ok": True, "mode": "plan", "sells": len(plan["sells"]),
           "assets": len(plan["assets"]), "version": plan["version"],
           "estimatedPoints": plan["totals"]["estimatedPoints"],
           "yuan": plan["totals"]["yuan"],
           "files": {"plan": jp, "delivery": dp, "matrix": mp, "ab": ap}}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    t = plan["totals"]
    print("素材矩阵 · %d 条（%d 卖点 x %d 钩子 x %d 尺寸，%s）"
          % (t["assets"], t["sells"], t["hooks"], t["sizes"], plan["version"]))
    print("=" * 90)
    print("  %s %s %s %s %s" % (pad("#", 3), pad("卖点", 12), pad("钩子", 12),
                                pad("尺寸", 8), "命名"))
    print("  " + "-" * 86)
    for x in plan["assets"][:12]:
        print("  %s %s %s %s %s" % (pad(x["no"], 3), pad(x["sell"][:10], 12),
                                    pad("%s %s" % (x["hook"], x["hookName"]), 12),
                                    pad(x["size"], 8), x["filename"]))
    if len(plan["assets"]) > 12:
        print("  …… 其余 %d 条见 素材矩阵.csv" % (len(plan["assets"]) - 12))
    print()
    print("  交付：%d 张静态 / %d 条视频 / %d 条口播 / 1 首配乐 / A/B 排期 / 迭代台账"
          % (t["assets"], t["videoCount"], t["sells"] * t["hooks"]))
    print("  本次预算：%s 点 = %.2f 元（只算静态，6 点/张）"
          % (fmt_pts(t["estimatedPoints"]), t["yuan"]))
    print("  含视频与口播：%s 点 = %.2f 元（%d 条 %d 秒 %s，plan 加 --with-video 计入）"
          % (fmt_pts(t["fullPoints"]), t["fullYuan"], t["videoCount"], t["seconds"],
             t["resolution"]))
    print()
    print("  已写：")
    for p in (jp, dp, mp, ap):
        print("    %s" % p)
    print()
    print("  下一步（0 点）：`qc --plan %s` 过一遍检查，再 `img` / `film` 按矩阵出。" % jp)
    return 0


def cmd_qc(a, key, host):
    problems, checks = [], []

    def bad(scope, what, tag):
        problems.append({"scope": scope, "problem": what, "tag": tag})

    plan = None
    if a.plan:
        if not os.path.isfile(a.plan):
            raise Fail("usage", "找不到 plan.json：%s（先跑 plan）" % a.plan, EXIT_USAGE)
        plan = json.load(io.open(a.plan, encoding="utf-8"))
        assets = plan.get("assets") or []
    elif a.text:
        assets = [{"no": 1, "sell": "手工文案", "hook": "H1", "hookName": "价格钩",
                   "size": "9x16", "requestSize": "720x1280", "version": "v1",
                   "headline": a.text, "subline": a.text, "line": a.text,
                   "cta": a.text, "filename": "SP01-H1_9x16_v1.png"}]
    else:
        raise Fail("usage", "给 --plan plan.json 或 --text \"一条文案\" 再检查", EXIT_USAGE)
    if not assets:
        raise Fail("usage", "这份 plan 里没有素材，先补 --sell 再生成", EXIT_USAGE)

    # 1) 广告法用语
    for x in assets:
        blob = " ".join([x.get("headline") or "", x.get("subline") or "",
                         x.get("line") or "", x.get("cta") or ""])
        hits = [w for w in ABSOLUTE_WORDS if w in blob]
        if hits:
            bad("%02d 文案" % x.get("no", 0), "绝对化用语：%s" % "、".join(hits),
                "absolute")

    # 2) 具体价格：每个卖点至少一条素材带价格锚（价格钩负责报价）
    by_sell = {}
    for x in assets:
        by_sell.setdefault(x.get("sellNo") or x.get("sell") or "-", []).append(x)
    for k, group in (by_sell.items() if plan is not None else []):
        has = False
        for x in group:
            blob = " ".join([x.get("headline") or "", x.get("subline") or "",
                             x.get("line") or ""])
            if re.search(r"\d+\s*元|\d+\s*折|券后", blob):
                has = True
                break
        if not has:
            bad("%s 卖点" % k, "这个卖点没有一条素材报价格（价格钩要带「N 元」）", "price")

    # 3) 钩子差异 + 前 3 秒长度
    seen_lines = {}
    for x in assets:
        ln = (x.get("line") or "").strip()
        if ln and ln in seen_lines and seen_lines[ln] != x.get("hook"):
            bad("钩子 %s" % x.get("hook"),
                "台词和 %s 完全一样，A/B 会测不出差异" % seen_lines[ln], "hook")
        if ln:
            seen_lines[ln] = x.get("hook")
    for x in assets:
        if len(x.get("line") or "") > 24:
            bad("%02d 前 3 秒" % x.get("no", 0),
                "台词 %d 字，3 秒念不完（控制在 24 字内）" % len(x.get("line") or ""),
                "hook")

    # 4) 行动号召
    for x in assets:
        if not any(w in (x.get("cta") or "") for w in CTA_WORDS):
            bad("%02d 行动号召" % x.get("no", 0),
                "结尾没有动作词（领券 / 点击 / 下单 / 立即 / 查看）", "cta")

    # 5) 命名规范：卖点码-钩子码_尺寸_v版本
    for x in assets:
        fn = x.get("filename") or ""
        if not re.match(r"^SP\d{2}-H\d_\d+x\d+_v\d+\.(png|jpg|jpeg|webp)$", fn):
            bad("%02d 命名" % x.get("no", 0), "不符合「卖点-钩子_尺寸_v版本」：%s" % fn,
                "naming")

    # 6) 尺寸合规
    for x in assets:
        prob = size_problem(x.get("requestSize"))
        if prob:
            bad("%02d 尺寸" % x.get("no", 0), prob, "size")
        if not SIZES.get(x.get("size")):
            bad("%02d 尺寸" % x.get("no", 0), "尺寸代号 %s 不在五档里" % x.get("size"),
                "size")

    # 7) 版本与矩阵完整（每个卖点 x 尺寸 x 钩子都要有一条）
    if plan is not None:
        sells = plan.get("sells") or []
        sizes = plan.get("sizes") or []
        hooks = plan.get("hooks") or []
        need = len(sells) * len(sizes) * len(hooks)
        if len(assets) != need:
            bad("矩阵", "应有 %d 条（%d 卖点 x %d 尺寸 x %d 钩子），实际 %d 条"
                % (need, len(sells), len(sizes), len(hooks), len(assets)), "matrix")
        seen = set((x.get("sellNo"), x.get("size"), x.get("hook")) for x in assets)
        for i in range(1, len(sells) + 1):
            for s in sizes:
                for h in hooks:
                    if ("SP%02d" % i, s, h) not in seen:
                        bad("矩阵", "缺一条：SP%02d / %s / %s" % (i, s, h), "matrix")
        if len(set(x.get("version") for x in assets)) > 1:
            bad("版本", "同一批里混了多个版本，A/B 会串味", "matrix")

    checks = [
        ("广告法用语", not any(p["tag"] == "absolute" for p in problems),
         "最 / 第一 / 全网 / 100% 这类词换成可验证描述"),
        ("具体价格", not any(p["tag"] == "price" for p in problems),
         "每个卖点至少一条带「N 元」或「券后」价格锚"),
        ("钩子差异", not any(p["tag"] == "hook" for p in problems),
         "三个钩子三套说法，前 3 秒台词 24 字内"),
        ("行动号召", not any(p["tag"] == "cta" for p in problems),
         "领券 / 点击 / 下单 / 立即 / 查看，至少一个"),
        ("命名规范", not any(p["tag"] == "naming" for p in problems),
         "卖点码-钩子_尺寸_v版本，例如 SP01-H1_9x16_v1.png"),
        ("尺寸合规", not any(p["tag"] == "size" for p in problems),
         "16 的倍数 / 3:1 / 单边 3840 / 总像素 655,360~8,294,400"),
        ("矩阵完整", not any(p["tag"] == "matrix" for p in problems),
         "卖点 x 尺寸 x 钩子，一条不少，版本统一"),
    ]
    out = {"ok": not problems, "checkedAssets": len(assets),
           "problems": problems,
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("交付前检查 · %d 条（纯本地，0 点）" % len(assets))
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
    print("  7 项全过，可以按矩阵开跑。")
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
        {"step": "出图", "app": APP_IMAGE, "cmd": "img",
         "endpoint": "POST %s/images/generations" % API_PREFIX,
         "price": "%d 点/张" % IMG_POINTS,
         "note": "n 1~4 一次多图；尺寸按五档 requests 走"},
        {"step": "改图", "app": APP_IMAGE, "cmd": "img --ref",
         "endpoint": "POST %s/images/edits" % API_PREFIX,
         "price": "%d 点/张" % IMG_POINTS,
         "note": "有实拍图时走这条，产品主体不走样"},
        {"step": "参考图", "app": APP_NANO, "cmd": "img --engine nano",
         "endpoint": "POST %s/apps/nano_banana/submit" % API_PREFIX,
         "price": "%d 点/次" % NANO_POINTS,
         "note": "异步；商品多角度 %d 点 x 视角数" % NANO_VIEW_POINTS},
        {"step": "视频素材", "app": APP_VIDEO, "cmd": "film",
         "endpoint": "POST %s/apps/full_video/submit" % API_PREFIX,
         "price": "480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒",
         "note": "单段 4~15 秒，15 秒一条 1080P = 900 点"},
        {"step": "口播", "app": APP_TTS, "cmd": "voice",
         "endpoint": "POST %s/apps/voice_tts/tts" % API_PREFIX,
         "price": "约 %.2f 点/字" % TTS_PER_CHAR,
         "note": "上游真实点数 x 3，以 usage.points_cost 为准"},
        {"step": "配乐", "app": APP_MUSIC, "cmd": "music",
         "endpoint": "POST %s/apps/media_services_33/music_generate" % API_PREFIX,
         "price": "%d 点起/首" % MUSIC_FLOOR,
         "note": "落通配：上游 x 2，保底 50 点"},
        {"step": "查进度", "app": "网关", "cmd": "status",
         "endpoint": "GET %s/tasks/<task_id>" % API_PREFIX,
         "price": "0 点", "note": "应用层 query 每查一次都是钱"},
        {"step": "传图", "app": "网关", "cmd": "upload",
         "endpoint": "POST %s/upload" % API_PREFIX,
         "price": "0 点", "note": "换 oss.gpu.likeadmin.cn 白名单地址"},
        {"step": "矩阵 / 检查", "app": "本地", "cmd": "plan / qc",
         "endpoint": "纯本地，不发请求", "price": "0 点",
         "note": "矩阵 / 话术 / 命名 / 合规"},
    ]
    for r in rows:
        r["online"] = (r["app"] in online) or r["app"] in ("网关", "本地")
        r["apis"] = len(online.get(r["app"], {}).get("apis") or [])
    out = {"ok": True, "rows": rows, "appsOnline": len(apps),
           "pricingRead": st == 200,
           "nanoCost": _flat(pr, API_PREFIX + "/apps/nano_banana/submit") or NANO_POINTS,
           "uploadCost": _flat(pr, API_PREFIX + "/upload"),
           "musicFloor": (pr.get("*") or {}).get("minPoints") or MUSIC_FLOOR,
           "videoRates": live or VIDEO_RATES,
           "sizes": {k: dict(SIZES[k]) for k in SIZE_ORDER},
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 广告投放素材 —— 一个卖点 15 条，用到的 9 个动作（1 元 = 100 点）")
    print()
    print("  %s %s %s %s" % (pad("动作", 12), pad("子命令", 16), pad("端点", 52), "单价"))
    print("  " + "-" * 112)
    for r in rows:
        print("  %s %s %s %s" % (pad(r["step"], 12), pad(r["cmd"], 16),
                                  pad(r["endpoint"], 52), r["price"]))
        print("        %s" % r["note"])
    print()
    print("  五个投放尺寸（requests 都在 gpt-image 的合法区间内）")
    print("    %s %s %s %s" % (pad("--size", 8), pad("比例", 7),
                                pad("请求 / 上架", 20), "平台"))
    print("    " + "-" * 76)
    for k in SIZE_ORDER:
        s = SIZES[k]
        print("    %s %s %s %s" % (pad(k, 8), pad(s["ratio"], 7),
                                    pad("%s / %s" % (s["req"], s["publish"]), 20),
                                    s["platforms"]))
    print()
    print("  本站应用目录 %d 个；media_services_33 在架 %d 个接口。"
          % (len(apps), len(online.get(APP_MUSIC, {}).get("apis") or [])))
    print("  full_video 现查按秒价：%s" % " · ".join(
        "%s %s" % (r, (live or VIDEO_RATES).get(r)) for r in RESOLUTIONS))
    print("  一个卖点 15 张静态 = 90 点 = 0.90 元；两个卖点一批 30 条 = 180 点 = 1.80 元。")
    return 0


def cmd_cost(a, key, host):
    sells = max(1, int(a.sellpoints))
    n_sizes = max(1, min(5, int(a.sizes)))
    n_hooks = max(1, min(3, int(a.hooks)))
    images = sells * n_sizes * n_hooks
    videos = sells * n_hooks
    seconds = max(VIDEO_CLIP_MIN, min(VIDEO_CLIP_MAX, int(a.seconds)))
    res = a.resolution
    kind = a.kind
    if kind == "image":
        # 只做静态素材时不配口播与配乐，预算表才对得上「30 张 180 点」
        voices = 0
        music = 0
    else:
        voices = max(0, int(a.voices))
        music = 1 if a.music else 0
    nano = max(0, int(a.nano))

    ipts = IMG_POINTS * images
    vpts = video_points(seconds, res) * (videos if kind in ("video", "mixed") else 0)
    if kind == "image":
        vpts = 0
    tpts = int(round(voices * a.tts_chars * TTS_PER_CHAR))
    mpts = MUSIC_FLOOR * music
    npts = nano * NANO_POINTS
    total = ipts + vpts + tpts + mpts + npts

    items = [
        ("静态素材 %d 张" % (images if kind in ("image", "mixed") else 0),
         ipts if kind in ("image", "mixed") else 0, "%d 点/张（与尺寸无关）" % IMG_POINTS),
        ("视频素材 %d 条 x %d 秒" % (videos if kind in ("video", "mixed") else 0,
                                     seconds),
         vpts, "%d 点/秒 x %d 秒" % (VIDEO_RATES[res], seconds)),
        ("口播 %d 条" % voices, tpts, "%d 字/条 x %.2f 点/字" % (a.tts_chars, TTS_PER_CHAR)),
        ("配乐 %d 首" % music, mpts, "50 点起/首（上游 x 2，保底 50）"),
        ("参考图 %d 次" % nano, npts, "nano_banana 72 点/次"),
    ]

    # 一批 30 条的四种走法（同一批 30 条，换个做法差 10 倍）
    batch = max(1, images)
    ways = [
        {"name": "全静态 6 点/张", "count": batch, "points": batch * IMG_POINTS},
        {"name": "全视频 15 秒 1080P", "count": batch,
         "points": batch * video_points(min(15, VIDEO_CLIP_MAX), "1080P")},
        {"name": "一半静态 + 一半 15 秒视频", "count": batch,
         "points": (batch // 2) * IMG_POINTS
                   + (batch // 2) * video_points(min(15, VIDEO_CLIP_MAX), "1080P")},
        {"name": "一半静态 + 一半 nano 多角度", "count": batch,
         "points": (batch // 2) * IMG_POINTS + (batch // 2) * NANO_POINTS},
    ]
    for w in ways:
        w["yuan"] = yuan(w["points"])

    out = {"ok": True, "sellpoints": sells, "sizes": n_sizes, "hooks": n_hooks,
           "assets": images, "videos": videos, "kind": kind, "seconds": seconds,
           "clipsPerVideo": len(clips_for(seconds)), "resolution": res,
           "voices": voices, "music": music, "nano": nano,
           "items": [{"name": n, "points": p, "basis": b} for n, p, b in items],
           "total": total, "yuan": yuan(total),
           "yuanPerAsset": yuan(total / float(max(1, images))),
           "batchWays": ways,
           "unitPrice": {"image": IMG_POINTS, "nano": NANO_POINTS,
                         "ttsPerChar": TTS_PER_CHAR, "musicFloor": MUSIC_FLOOR,
                         "video": VIDEO_RATES},
           "notes": ["1 元 = 100 点；单价取自 GET /api/v1/pricing 与流水实测（2026-11-08）",
                     "gpt-image 按张计费，与尺寸、质量、输出格式无关",
                     "full_video 按总秒数 x 分辨率计费，单段 4~15 秒",
                     "口播按上游真实点数 x 3，实测 33 字 5.94 点，按 0.18 点/字估",
                     "配乐落通配规则，50 点是下限，实际以 usage.points_cost 为准",
                     "nano_banana 72 点/次是 flat，带 views 时 25 点 x 视角数"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("素材批次要多少钱（1 元 = 100 点）")
    print()
    print("  %d 卖点 x %d 尺寸 x %d 钩子 = %d 条素材，视频 %d 条 x %d 秒，%s"
          % (sells, n_sizes, n_hooks, images, videos, seconds, res))
    print("  " + "-" * 78)
    for n, p, b in items:
        if p:
            print("  %s %s 点   %s" % (pad(n, 30), pad(fmt_pts(p), 9, left=False), b))
    print("  " + "-" * 78)
    print("  %s %s 点   = %.2f 元（单条约 %.2f 元）"
          % (pad("合计", 30), pad(fmt_pts(total), 9, left=False), yuan(total),
             yuan(total / float(max(1, images)))))
    print()
    print("  同一批 %d 条，四种走法（这是投手最常问的一句话）" % batch)
    print("    %s %s %s %s" % (pad("走法", 30), pad("条数", 6, left=False),
                                pad("点数", 10, left=False), pad("元", 10, left=False)))
    print("    " + "-" * 66)
    for w in ways:
        print("    %s %s %s %s" % (pad(w["name"], 30), pad(w["count"], 6, left=False),
                                    pad(fmt_pts(w["points"]), 10, left=False),
                                    pad("%.2f" % w["yuan"], 10, left=False)))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


# ───────────────────────── 出图（6 点/张 · nano 72 点/次）─────────────────────────
def _save_images(d, outdir, prefix, timeout=180):
    """把返回里的 b64 / url 落成 png。返回 (文件列表, 张数, 来源)。"""
    items = []
    data = d.get("data")
    if isinstance(data, list):
        items = data
    elif isinstance(d, dict) and isinstance(data.get("data"), list):
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


def cmd_img(a, key, host):
    size = SIZES.get(a.size)
    if not size:
        raise Fail("usage", "--size 取 %s" % " / ".join(SIZE_ORDER), EXIT_USAGE)
    hook = _hook_meta(a.hook)
    prob = size_problem(size["req"])
    if prob:
        raise Fail("internal", "尺寸表配错了：%s" % prob, EXIT_INTERNAL)
    n = 1 if a.engine == "nano" else max(1, min(4, int(a.n)))
    meta = _sell_meta(a, a.sell, 1)
    prompt = (a.prompt or _image_prompt(meta, hook, size)).strip()
    if not prompt:
        raise Fail("usage", "给 --sell 或 --prompt（提示词不能为空）", EXIT_USAGE)
    ref_ok = None
    if a.ref:
        if a.ref.startswith("http"):
            ok, kind = url_allowed(a.ref)
            if not ok:
                raise Fail("usage",
                           "参考图必须是平台托管地址（%s 不在白名单）。"
                           "本地图直接给路径：--ref 实拍.jpg（会自动 upload，免费）" % kind,
                           EXIT_USAGE)
            ref_ok = a.ref
        elif not os.path.isfile(a.ref):
            raise Fail("usage", "找不到参考图：%s" % a.ref, EXIT_USAGE)

    if a.engine == "nano":
        cost = NANO_POINTS
        basis = "参考图 1 次 x %d 点/次（nano_banana，flat）" % NANO_POINTS
        endpoint = NANO_PATH
        body = {"prompt": prompt, "model": NANO_MODEL, "resolution": a.nano_resolution,
                "aspect_ratio": size["ratio"]}
    else:
        cost = IMG_POINTS * n
        basis = "出图 %d 张 x %d 点/张（%s，%s）" % (n, IMG_POINTS, a.size, size["req"])
        endpoint = EDIT_PATH if (a.ref or ref_ok) else IMAGE_PATH
        body = {"model": APP_IMAGE, "prompt": prompt, "n": n, "size": size["req"],
                "output_format": a.output_format}
    gate(a, cost, basis)
    url = host + endpoint

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "engine": a.engine, "url": url,
               "requestBody": body, "estimatedPoints": cost, "yuan": yuan(cost),
               "size": a.size, "requestSize": size["req"],
               "publishSize": size["publish"]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不出图、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  尺寸：%s -> 请求 %s，上架 %s" % (a.size, size["req"], size["publish"]))
        print("  预估：%d 点（%.2f 元）· %s" % (cost, yuan(cost), basis))
        return 0

    # 本地参考图：先 upload 换白名单地址（免费）
    if a.ref and not ref_ok:
        r = upload_file(key, host, a.ref, timeout=a.timeout)
        ref_ok = r["url"]

    say("正在出素材（%s，%s）…" % (a.size, a.engine))
    t0 = time.time()
    if a.engine == "nano":
        if ref_ok:
            body["action"] = "edit"
            body["image_urls"] = [ref_ok]
        st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    elif ref_ok:
        fields = {"model": APP_IMAGE, "prompt": prompt, "n": str(n),
                  "size": size["req"], "output_format": a.output_format}
        st, txt = http_multipart(url, key, fields, [("image", a.ref)], timeout=a.timeout)
    else:
        st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}

    if a.engine == "nano":
        flat = payload_of(d) if isinstance(d, dict) else {}
        flat = flat if isinstance(flat, dict) else {}
        tid = flat.get("task_id") or flat.get("taskId") or flat.get("id")
        if st not in (200, 201) or not tid:
            msg = err_text(st, txt)
            ledger_add({"at": now_iso(), "ok": False, "mode": "img", "engine": "nano",
                        "http": st, "error": msg})
            raise Fail("call", "参考图提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
        rec = {"at": now_iso(), "ok": True, "mode": "img", "engine": "nano",
               "taskId": tid, "size": a.size, "points": cost}
        ledger_add(rec)
        out = {"ok": True, "engine": "nano", "taskId": tid, "status": flat.get("status"),
               "size": a.size, "endpoint": endpoint, "elapsed": round(dt, 1),
               "estimatedPoints": cost, "yuan": yuan(cost),
               "next": "python3 scripts/run.py status --task-id %s" % tid}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("已提交参考图任务（%.1fs）" % dt)
        print("  任务：%s   状态：%s" % (tid, flat.get("status")))
        print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % tid)
        return 0

    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "img", "http": st,
                    "error": msg, "size": a.size})
        raise Fail("call", "出图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = a.outdir or OUT_ROOT
    prefix = "%s-%s_%s_%s" % (a.prefix or "SP01", a.hook, a.size, a.version)
    files, got, src = _save_images(d, outdir, prefix, timeout=a.timeout)
    if not got:
        raise Fail("call", "响应里没有图：%s" % (txt or "")[:300], EXIT_CALL)
    billed = IMG_POINTS * got
    out = {"ok": True, "engine": "gpt", "mode": "img", "size": a.size,
           "requestSize": size["req"], "publishSize": size["publish"],
           "requested": n, "returned": got, "files": files, "source": src,
           "prompt": prompt, "elapsed": round(dt, 1),
           "billedPoints": billed, "estimatedPoints": cost, "endpoint": endpoint}
    ledger_add({"at": now_iso(), "ok": True, "mode": "img", "files": files,
                "size": a.size, "points": billed, "engine": "gpt"})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已出图（%.1fs · %d 点）" % (dt, billed))
    for p in files:
        print("  文件：%s" % p)
    print("  尺寸：请求 %s，上架 %s（%s）" % (size["req"], size["publish"], size["platforms"]))
    print()
    print("  下一步：`film --size %s --hook %s --image <文件> --yes` 让它动起来。"
          % (a.size, a.hook))
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
                   "也可以先 `plan` 生成交付清单再粘过来", EXIT_USAGE)
    if len(text) > TTS_MAX_CHARS:
        raise Fail("usage", "这条 %d 字，同步 tts 建议 %d 字内；超过就按 3 秒 / 9 秒拆成两三条。"
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
    txt_path = os.path.join(outdir, "%s-voice.txt" % (a.prefix or "ad"))
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
    prompt = a.style or "电子鼓点，节奏明快，适合 15 秒竖版投放"
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
    print("  归属：%s（在上游白名单内，可以直接给 img --ref / film --image 用）" % r["hostKind"])
    return 0


# ───────────────────────── 视频素材（按秒计费）─────────────────────────
def cmd_film(a, key, host):
    size = SIZES.get(a.size)
    if not size:
        raise Fail("usage", "--size 取 %s" % " / ".join(SIZE_ORDER), EXIT_USAGE)
    hook = _hook_meta(a.hook)
    meta = _sell_meta(a, a.sell, 1)
    text = (a.text or _video_prompt(meta, hook, size, a.seconds)).strip()
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds))
    if seconds > VIDEO_CLIP_MAX:
        raise Fail("usage", "full_video 单段 4~15 秒；%d 秒分 %s 两段提交。"
                   % (seconds, "+".join(str(x) for x in clips_for(seconds))), EXIT_USAGE)
    cost = video_points(seconds, a.resolution)
    gate(a, cost, "视频素材 %d 秒 x %d 点/秒（%s）"
         % (seconds, VIDEO_RATES[a.resolution], a.resolution))

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
        elif not os.path.isfile(a.image):
            raise Fail("usage", "找不到首帧图：%s" % a.image, EXIT_USAGE)

    content = [{"type": "text", "text": text}]
    body = {"model": "full-video", "content": content, "duration": seconds,
            "resolution": a.resolution, "ratio": size["ratio"], "aigc_watermark": False}
    if image_url:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})
    url = host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit"
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost), "size": a.size}
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
           "status": data.get("status"), "resolution": a.resolution,
           "seconds": seconds, "size": a.size, "clips": clips_for(seconds),
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
    print("  规格：%s · %d 秒 · %s（%s）" % (a.resolution, seconds, a.size, size["ratio"]))
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
    need = [APP_VIDEO, APP_TTS, APP_MUSIC, APP_NANO]
    miss = [c for c in need if c not in online]
    checks.append(("4 个底层应用在架（视频 / 口播 / 配乐 / 参考图）",
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

    nano_rule = pricing.get(API_PREFIX + "/apps/nano_banana/*") or {}
    wild = pricing.get("*") or {}
    up_rule = pricing.get(API_PREFIX + "/upload") or {}
    ok_price = (int(nano_rule.get("cost") or 0) == NANO_POINTS
                and int(wild.get("minPoints") or 0) == MUSIC_FLOOR
                and int(up_rule.get("cost") if up_rule.get("cost") is not None else 999) == 0)
    checks.append(("参考图 72 点 + 配乐保底 50 点 + upload 0 点", ok_price,
                   "nano %s · 通配保底 %s · upload %s"
                   % (nano_rule.get("cost"), wild.get("minPoints"), up_rule.get("cost"))))

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

    out = {"ok": all(c[1] for c in checks), "requests": 10,
           "estimatedPoints": 0, "yuan": 0.0, "lastLedger": last,
           "apps": need, "videoRates": live or VIDEO_RATES,
           "endpoints": {"image": host + IMAGE_PATH,
                         "edit": host + EDIT_PATH,
                         "nano": host + NANO_PATH,
                         "film": host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit",
                         "tts": host + API_PREFIX + "/apps/" + APP_TTS + "/tts",
                         "music": host + API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate",
                         "task": host + API_PREFIX + "/tasks/<task_id>",
                         "upload": host + UPLOAD_PATH},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（5 个只读 GET + 1 个空 prompt 422 + 1 个空 body 视频探针 + 1 个缺 file 上传，"
          "全部停在扣费之前）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 60), dt))
    print()
    if last:
        print("  最近一笔流水：%s  %s  %s 点  余额 %s"
              % (time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime((last["at"] or 0) / 1000.0)),
                 last.get("type") or "-", fmt_pts(last.get("points") or 0),
                 fmt_pts(last.get("balanceAfter") or 0)))
    print("  本次自检 0 点、0 冻结：10 个请求里没有一条会建任务。")
    print()
    print("  端点：POST /images/generations（出图）· /images/edits（改图）")
    print("        POST /apps/nano_banana/submit（参考图）· /apps/full_video/submit（视频）")
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
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 广告投放素材（一个卖点 x 5 尺寸 x 3 钩子，走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/images/generations · "
               "POST %s/api/v1/apps/nano_banana/submit · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/media_services_33/music_generate · "
               "GET %s/api/v1/tasks/<task_id>" % ((DEFAULT_HOST,) * 6),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 30 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="五条能力 + 端点 + 现查单价 + 尺寸表（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一批 30 条多少钱，四种走法（免费）", allow_abbrev=False)
    p.add_argument("--sellpoints", type=int, default=2, help="卖点数（默认 2）")
    p.add_argument("--sizes", type=int, default=5, help="每卖点几个尺寸（1~5，默认 5）")
    p.add_argument("--hooks", type=int, default=3, help="每卖点几个钩子（1~3，默认 3）")
    p.add_argument("--kind", choices=["image", "video", "mixed"], default="image",
                   help="image 全静态 / video 全视频 / mixed 一半静态一半视频")
    p.add_argument("--seconds", type=int, default=15, help="视频单条秒数（4~15，默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="视频分辨率（默认 1080P）")
    p.add_argument("--voices", type=int, default=3, help="口播条数（默认 3）")
    p.add_argument("--tts-chars", dest="tts_chars", type=int, default=20,
                   help="每条口播字数（默认 20，约 5 秒）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1], help="配乐 1 首（默认 1）")
    p.add_argument("--nano", type=int, default=0, help="nano 参考图几次（72 点/次）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="素材矩阵与交付清单（免费，纯本地）",
                       allow_abbrev=False)
    p.add_argument("--sell", action="append", help="卖点，可重复给多个")
    p.add_argument("--price", type=float, default=79, help="到手价（元，默认 79）")
    p.add_argument("--list", type=float, default=129, help="原价（元，默认 129）")
    p.add_argument("--offer", default="第二件半价", help="优惠形式（默认 第二件半价）")
    p.add_argument("--pain", default="闷热贴背", help="痛点（默认 闷热贴背）")
    p.add_argument("--proof", default="洗 30 次仍凉感", help="可验证的效果证据")
    p.add_argument("--audience", default="通勤上班族", help="人群（默认 通勤上班族）")
    p.add_argument("--scene", default="地铁通勤", help="场景（默认 地铁通勤）")
    p.add_argument("--brand", default="", help="品牌 / 系列名（可空）")
    p.add_argument("--sizes", default="all",
                   help="尺寸，all 或 %s（默认 all）" % " / ".join(SIZE_ORDER))
    p.add_argument("--hooks", action="append",
                   help="钩子，可重复给 %s（默认全部）" % " / ".join(HOOK_ORDER))
    p.add_argument("--version", type=int, default=1, help="版本号（默认 1）")
    p.add_argument("--seconds", type=int, default=15, help="视频单条秒数（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="成本预估用分辨率（默认 1080P）")
    p.add_argument("--with-video", dest="with_video", action="store_true",
                   help="把视频素材与口播也算进本次预算（默认只算静态）")
    p.add_argument("--outdir", help="输出目录（默认 ~/.a7w/ad-creative/<日期>）")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("qc", help="交付前检查：7 项（免费，纯本地）", allow_abbrev=False)
    p.add_argument("--plan", help="plan.json 路径")
    p.add_argument("--text", help="直接检查一条文案")
    p.set_defaults(fn=cmd_qc)

    p = sub.add_parser("img", help="按尺寸出图（6 点/张，nano 72 点/次，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--size", default="9x16", help="尺寸：%s" % " / ".join(SIZE_ORDER))
    p.add_argument("--hook", default="H1", help="钩子：H1 价格 / H2 痛点 / H3 效果")
    p.add_argument("--sell", default="冰丝凉感", help="卖点（拼进提示词）")
    p.add_argument("--price", type=float, default=79, help="到手价（元）")
    p.add_argument("--list", type=float, default=129, help="原价（元）")
    p.add_argument("--offer", default="第二件半价", help="优惠形式")
    p.add_argument("--pain", default="闷热贴背", help="痛点")
    p.add_argument("--proof", default="洗 30 次仍凉感", help="效果证据")
    p.add_argument("--audience", default="通勤上班族", help="人群")
    p.add_argument("--scene", default="地铁通勤", help="场景")
    p.add_argument("--brand", default="", help="品牌 / 系列名")
    p.add_argument("--prompt", help="直接给提示词，覆盖内置模板")
    p.add_argument("--engine", choices=["gpt", "nano"], default="gpt",
                   help="gpt 同步 6 点/张 / nano 异步 72 点/次")
    p.add_argument("--n", type=int, default=1, help="张数 1~4（默认 1）")
    p.add_argument("--ref", help="参考图：本地路径（自动上传）或平台地址")
    p.add_argument("--output-format", dest="output_format", default="png",
                   help="png / jpeg / webp")
    p.add_argument("--nano-resolution", dest="nano_resolution", default="1K",
                   help="nano 分辨率：1K / 2K / 4K")
    p.add_argument("--version", type=int, default=1, help="版本号（默认 1）")
    p.add_argument("--prefix", default="SP01", help="文件名前缀（默认 SP01）")
    p.add_argument("--outdir", help="图片目录（默认 ~/.a7w/ad-creative/out）")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_img)

    p = sub.add_parser("film", help="视频素材（按秒计费，要 --yes）", allow_abbrev=False)
    p.add_argument("--size", default="9x16", help="尺寸：%s" % " / ".join(SIZE_ORDER))
    p.add_argument("--hook", default="H1", help="钩子：H1 / H2 / H3")
    p.add_argument("--sell", default="冰丝凉感", help="卖点")
    p.add_argument("--price", type=float, default=79, help="到手价（元）")
    p.add_argument("--list", type=float, default=129, help="原价（元）")
    p.add_argument("--offer", default="第二件半价", help="优惠形式")
    p.add_argument("--pain", default="闷热贴背", help="痛点")
    p.add_argument("--proof", default="洗 30 次仍凉感", help="效果证据")
    p.add_argument("--audience", default="通勤上班族", help="人群")
    p.add_argument("--scene", default="地铁通勤", help="场景")
    p.add_argument("--brand", default="", help="品牌 / 系列名")
    p.add_argument("--text", help="画面与运镜描述，覆盖内置模板")
    p.add_argument("--image", help="首帧图：本地路径（自动上传）或平台地址")
    p.add_argument("--seconds", type=int, default=15, help="单段秒数 4~15（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把地址交给上游判断")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_film)

    p = sub.add_parser("voice", help="口播配音（约 0.18 点/字，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--text", help="口播文案（500 字内）")
    p.add_argument("--script", help="从文本文件读口播稿")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro", help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3", help="mp3 / wav / opus")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色 ID（可选）")
    p.add_argument("--prefix", default="ad", help="稿子文件名前缀")
    p.add_argument("--outdir", help="稿子目录（默认 ~/.a7w/ad-creative/out）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="素材配乐（50 点起/首，要 --yes）", allow_abbrev=False)
    p.add_argument("--style", help="风格描述，例如「电子鼓点，节奏明快」")
    p.add_argument("--title", help="曲名（可选）")
    p.add_argument("--music-model", dest="music_model", default=MUSIC_MODEL,
                   help="Suno 模型（默认 %s）" % MUSIC_MODEL)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_music)

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
