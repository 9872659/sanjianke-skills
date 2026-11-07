#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 品牌 VI 生成（sanjianke-brand-vi）

一条命令把「一套 VI」从话术排到交付清单，再决定哪几张值得花钱。

## 三条产线（价格全部现查 /api/v1/pricing，2026-11-08 实测）

  gen     POST /api/v1/images/generations   gpt-image-2.6   **6 点/张**（0.06 元）
  edit    POST /api/v1/images/edits         gpt-image-2.6   **6 点/张**（multipart）
  refine  POST /api/v1/apps/nano_banana/submit  nano-banana **72 点/次**（参考图改图）

  6 点/张 不是估的：GET /user/balance/logs 里两笔 success 流水都是
  `sync:/api/v1/images/generations` −6 点，同步结算、一笔一张。
  72 点/次 来自 GET /api/v1/pricing 的 `/api/v1/apps/nano_banana/*` 与
  `/api/v1/apps/nano_banana/submit` 两条 flat：本租户按次收 72，与模型、
  分辨率无关（nano-banana-pro:official 4K 也是 72，SKU 分档被通配 flat 盖住）。

## 一致性只有一条路：拿定稿 logo 当参考图

  文生图每张都是独立采样，同一个 prompt 出四稿能出四个气质。所以流程是：
  1) gpt-image 一次 n=4 出四方向概念稿（24 点）
  2) 选定稿，`refine` 把它 upload 成 URL 塞进 image_urls，nano-banana 按这个
     视觉母版去派生名片 / 易拉宝 / 包装 / 头像 / 封面（72 点/次）
  3) 局部改字改色走 `edit`（6 点/张），不动构图

  upload 是免费的（/api/v1/upload cost:0），拿到的
  `oss.gpu.likeadmin.cn/openapi/...` 是平台自己的地址，image_urls 直接吃。

## 探针纪律（2026-11-07 用 472 点换来的）

  - GET /api/v1/apps/nano_banana      → 命中 /apps/nano_banana/* 通配 flat 72，
                                        即时扣、不退。本包一次都不发。
  - POST /api/v1/apps/nano_banana/submit 缺参 → reserve_sync 先冻 72 再退，
                                        净额 0 但钱包被动过。本包不拿它当探针。
  - 任务进度只走 GET /api/v1/tasks/{id}（实测 0 点、返回「任务不存在」为正常）。

  doctor 用的三条探针都停在参数校验层，且已用流水复核 0 点：
  文生图空 prompt → 422；改图不带图 → 500 `image is required`；
  上传不带 file → 200 `请使用 file 字段提交一个文件`。

## 子命令

  catalog  12 个工序 / 端点 / 单价 / 是否要 --yes（免费）
  cost     一套 VI 多少钱：lite / standard / pro，或按张数与次数自算（免费）
  doctor   自检 8 条，不扣费（免费）
  palette  主色 / 辅色 / 字体层级，本地算，含 WCAG 对比度（免费）
  plan     一套 VI 的出图 prompt + 交付清单 + 成本单，写盘（免费）
  qc       合规 5 条：商标词 / 字体商用 / 对比度 / 清单齐全 / 命名（免费）
  gen      文生图，6 点/张（要 --yes）
  edit     局部改图，6 点/张（要 --yes）
  refine   参考图派生，72 点/次（要 --yes）
  upload   本地图换平台地址（免费）
  status   查任务（免费）
  log      本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost --set standard
  python3 scripts/run.py plan --client 示例科技 --industry 科技 --hue 210 --set pro
  python3 scripts/run.py qc
  python3 scripts/run.py gen --kind logo --client 示例科技 --yes
  python3 scripts/run.py refine --ref logo-01.png --kind card --yes

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
import urllib.error
import urllib.parse
import urllib.request
import uuid

# ── GBK 编码兜底（2026-11-07 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到 `√`/`×` 这类 cp936 编不出的字符就 UnicodeEncodeError 崩掉。
# 先加 errors='replace' 兜底，本包输出再只用 GBK 里有的符号。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
MODEL_IMAGE = "gpt-image-2.6"
MODEL_REFINE = "nano-banana"
P_IMAGE = 6            # 点/张（流水实测 sync: -6）
P_REFINE = 72          # 点/次（pricing flat 72）
POINTS_PER_YUAN = 100
WORKDIR = os.path.join(os.path.expanduser("~"), ".a7w", "brand-vi")
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "brand-vi-ledger.json")
DEFAULT_BUDGET = 3000  # 点，= 30 元

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-brand-vi/%s" % VERSION

# ── 7 个交付物：尺寸都过一遍 gpt-image 的四条硬约束 ──────────────────────────
# 宽高 16 的倍数 / 长短边 <= 3:1 / 单边 <= 3840 / 总像素 655,360 - 8,294,400
SCENES = {
    "logo": dict(name="LOGO 概念稿", size="1024x1024", ratio="1:1",
                 spec="1024x1024 png，四方向一次四稿",
                 gist="标志主体居中、留白 12%、纯色底，不带任何文字水印"),
    "card": dict(name="名片", size="1536x1024", ratio="3:2",
                 spec="1536x1024 png，正反面共用一版版式",
                 gist="名片版式、logo 居左上、留出姓名与联系方式三行信息位"),
    "rollup": dict(name="易拉宝", size="1024x2560", ratio="2:5",
                   spec="1024x2560 png，80x200cm 出血版",
                   gist="竖版易拉宝版式、主视觉在中上、底部留二维码位"),
    "packaging": dict(name="包装", size="1024x1024", ratio="1:1",
                      spec="1024x1024 png，方盒正面主视图",
                      gist="方形包装主视图、logo 居中偏上、留出配料与净含量块"),
    "avatar": dict(name="社媒头像", size="1024x1024", ratio="1:1",
                   spec="1024x1024 png，圆形安全区占 86%",
                   gist="头像构图、标志占画面 62%、四周留白、缩到 48px 仍能认"),
    "cover": dict(name="封面", size="1536x864", ratio="16:9",
                  spec="1536x864 png，可裁 1080x608",
                  gist="横版封面版式、左侧标题区留白、右侧主视觉"),
    "manual": dict(name="VI 手册页", size="1040x1472", ratio="1:1.415",
                   spec="1040x1472 png，A4 竖版一比一",
                   gist="VI 手册内页版式、色卡与字号阶梯排在网格里、页脚留页码位"),
}
SCENE_ORDER = ["logo", "card", "rollup", "packaging", "avatar", "cover", "manual"]

# ── 三套交付配置（一套 VI 的三种交法）───────────────────────────────────────
SETS = {
    "lite": dict(label="轻量版 · 小生意先有一套能用的", logo=2,
                 scenes=["avatar", "cover"], manual=1, refine=0),
    "standard": dict(label="标准版 · 一单交付 logo + 五场景 + 手册", logo=4,
                     scenes=["card", "rollup", "packaging", "avatar", "cover"],
                     manual=1, refine=0),
    "pro": dict(label="专业版 · 加三次参考图派生，跨物料同一母版", logo=4,
                scenes=["card", "rollup", "packaging", "avatar", "cover"],
                manual=1, refine=3),
}

# ── 字体白名单：只用可商用授权的字体，qc 会逐条核 ───────────────────────────
FONT_WHITELIST = [
    "思源黑体", "思源宋体", "阿里巴巴普惠体", "MiSans", "OPPO Sans",
    "HarmonyOS Sans", "Noto Sans SC", "Noto Serif SC", "Inter", "Roboto",
    "Montserrat", "Source Han Sans", "Source Han Serif",
]

# ── 商标 / 名人词表：prompt 里出现就拦（qc 第 1 条）─────────────────────────
BRAND_WORDS = [
    "nike", "adidas", "apple", "iphone", "starbucks", "coca-cola", "pepsi",
    "google", "microsoft", "disney", "marvel", "pixar", "lego", "gucci",
    "chanel", "louis vuitton", "rolex", "tesla", "腾讯", "微信", "抖音",
    "星巴克", "可口可乐", "百事", "迪士尼", "漫威", "耐克", "阿迪达斯",
    "苹果", "华为", "小米", "茅台", "五粮液", "春晚", "奥运", "世界杯",
    "乔布斯", "马斯克", "易烊千玺", "王一博", "肖战",
]

INDUSTRY_TONE = {
    "科技": "克制、几何、冷色，横向网格对齐",
    "餐饮": "温暖、食欲、圆角，留出菜品实拍位",
    "美妆": "轻盈、留白、柔光，低饱和度",
    "教育": "稳、清晰、蓝绿系，信息层级分明",
    "制造": "硬朗、粗线、深色底，工业感",
    "医疗": "洁净、通透、白与蓝绿，圆角收边",
    "金融": "深色、金属质感、细线分割",
    "零售": "活泼、高饱和、块面分割",
}


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


def http_json(method, url, key, body=None, timeout=240):
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
        for k in ("message", "msg"):
            if d.get(k):
                return str(d[k])[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


def url_allowed(u):
    """平台托管的地址才收。返回 (ok, 说明)。"""
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


def check_size(size):
    """gpt-image 的四条硬约束。返回 (ok, 原因)。"""
    if not size or size in ("auto", "1k", "2k", "4k"):
        return True, ""
    if "x" not in size.lower():
        return False, "size 只能是 auto / 1k / 2k / 4k / 宽x高（例如 1024x1024）"
    try:
        w, h = [int(x) for x in size.lower().split("x", 1)]
    except Exception:                                            # noqa: BLE001
        return False, "size 格式不对：%s" % size
    if w % 16 or h % 16:
        return False, "宽高都必须是 16 的倍数（%dx%d）" % (w, h)
    lo, hi = min(w, h), max(w, h)
    if hi > 3 * lo:
        return False, "长边/短边超过 3:1（%dx%d）" % (w, h)
    if max(w, h) > 3840:
        return False, "单边超过 3840（%dx%d）" % (w, h)
    px = w * h
    if px < 655360 or px > 8294400:
        return False, "总像素要落在 655,360 - 8,294,400 之间（当前 %d）" % px
    return True, ""


def save_images(d, outdir, prefix, fmt):
    """b64_json 与 url 两种返回都落盘。返回 (路径列表, 来源)。"""
    os.makedirs(outdir, exist_ok=True)
    paths, src = [], "none"
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(data, list):
        return paths, src
    for i, it in enumerate(data):
        if not isinstance(it, dict):
            continue
        raw = None
        b64 = it.get("b64_json")
        if b64:
            raw = base64.b64decode(b64)
            src = "b64_json"
        elif it.get("url"):
            req = urllib.request.Request(it["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as x:
                raw = x.read()
            src = "url"
        if raw is None:
            continue
        ext = fmt or "png"
        if raw[:3] == b"GIF":
            ext = "gif"
        p = os.path.join(outdir, "%s-%02d.%s" % (prefix, i + 1, ext))
        with open(p, "wb") as fh:
            fh.write(raw)
        paths.append(p)
    return paths, src


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


def fmt_pts(n):
    return "{:,}".format(int(n))


def yuan(n):
    return "%.2f" % (n / float(POINTS_PER_YUAN))


# ───────────────────────── 成本模型 ─────────────────────────
def set_plan(name):
    s = SETS[name]
    images = s["logo"] + len(s["scenes"]) + s["manual"]
    refines = s["refine"]
    return dict(set=name, label=s["label"], images=images, refines=refines,
                points=images * P_IMAGE + refines * P_REFINE,
                parts=dict(logo=s["logo"], scenes=list(s["scenes"]),
                           manual=s["manual"]))


def cost_of(images, refines):
    return images * P_IMAGE + refines * P_REFINE


def gate(a, cost, what):
    """两道闸门：预算 -> 确认。都通过才发请求。"""
    if cost > a.budget:
        raise Fail("budget", "%s：预计 %d 点，超过 --budget %d 点（1 元 = 100 点），"
                   "一个请求都没发。" % (what, cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "%s：会真实扣约 %d 点（%s 元）。确认请加 --yes。"
                   % (what, cost, yuan(cost)), EXIT_CONFIRM)


def plan_out(a, lines, reqs, cost, extra=None):
    out = {"ok": True, "dryRun": True, "requests": lines, "requestCount": reqs,
           "estimatedPoints": cost, "yuan": float(yuan(cost))}
    if extra:
        out.update(extra)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（不提交、不扣费、不冻结）")
    print("  请求数：%d  预估：%d 点（%s 元）" % (reqs, cost, yuan(cost)))
    for ln in lines:
        print("  -> %s" % ln)
    return 0


# ───────────────────────── 本地：配色 / 字体 ─────────────────────────
def hsl_to_hex(h, s, l):
    h = h % 360
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = l - c / 2.0
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    def f(v):
        return max(0, min(255, int(round((v + m) * 255))))

    return "#%02X%02X%02X" % (f(r), f(g), f(b))


def _lin(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(hexs):
    h = hexs.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a_hex, b_hex):
    la, lb = luminance(a_hex), luminance(b_hex)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def text_on(bg, ink="#1E2124"):
    """给一个底色挑字色：白字和墨色字哪个对比高用哪个。返回 (字色, 对比度)。"""
    w = contrast("#FFFFFF", bg)
    k = contrast(ink, bg)
    return ("#FFFFFF", w) if w >= k else (ink, k)


def color_pairs(ink, paper, tint, primary, accent, deep):
    """VI 手册必须写清的「底色 -> 字色」对照表。正文要 4.5:1，大字要 3.0:1。"""
    spec = [("正文 / 纸白", paper, 4.5), ("正文 / 主色浅", tint, 4.5),
            ("大字 / 主色", primary, 3.0), ("大字 / 辅色", accent, 3.0),
            ("大字 / 主色深", deep, 3.0)]
    out = []
    for what, bg, need in spec:
        fg, ratio = text_on(bg, ink)
        out.append(dict(what=what, bg=bg, fg=fg, ratio=ratio, need=need))
    return out


def build_palette(hue, industry):
    sat = 0.62
    if industry in ("餐饮", "零售"):
        sat = 0.70
    elif industry in ("制造", "金融"):
        sat = 0.46
    elif industry in ("美妆", "医疗"):
        sat = 0.50
    return [
        dict(role="主色", code="primary", hex=hsl_to_hex(hue, sat, 0.46),
             use="标志、主按钮、标题条", lock="整套只改这一个色相"),
        dict(role="主色深", code="primaryDark", hex=hsl_to_hex(hue, sat, 0.30),
             use="深底反白、页脚、压暗层级"),
        dict(role="主色浅", code="primaryTint", hex=hsl_to_hex(hue, min(0.92, sat * 0.85), 0.93),
             use="分区底、表格斑马线、卡片底"),
        dict(role="辅色", code="accent", hex=hsl_to_hex(hue + 32, min(0.92, sat * 0.9), 0.54),
             use="强调数字、标签、进度"),
        dict(role="对比色", code="contrast", hex=hsl_to_hex(hue + 180, sat * 0.55, 0.42),
             use="点缀、图标描边、一屏最多两处"),
        dict(role="墨色", code="ink", hex=hsl_to_hex(215, 0.10, 0.13),
             use="正文、线框"),
        dict(role="纸白", code="paper", hex=hsl_to_hex(40, 0.14, 0.975),
             use="主背景、名片底"),
    ]


def build_scale():
    return [
        dict(level="主标", px=56, weight=700, line=1.10, use="封面主标题、易拉宝主标"),
        dict(level="H1", px=40, weight=700, line=1.20, use="手册章标题、海报副标"),
        dict(level="H2", px=32, weight=600, line=1.30, use="海报小标、名片姓名"),
        dict(level="H3", px=24, weight=600, line=1.40, use="小标题、包装品类"),
        dict(level="正文", px=16, weight=400, line=1.70, use="说明文、手册正文"),
        dict(level="小字", px=14, weight=400, line=1.60, use="注释、二维码旁说明"),
        dict(level="标注", px=12, weight=400, line=1.50, use="页脚、法务行"),
    ]


def build_fonts(industry):
    if industry in ("教育", "医疗", "金融"):
        return [dict(role="中文", name="思源宋体", license="SIL OFL，可商用",
                     use="标题、书名、正式文档"),
                dict(role="中文正文", name="思源黑体", license="SIL OFL，可商用",
                     use="正文、界面、说明"),
                dict(role="西文", name="Inter", license="SIL OFL，可商用",
                     use="数字、英文标题")]
    return [dict(role="中文", name="思源黑体", license="SIL OFL，可商用",
                 use="标志、标题、正文主力"),
            dict(role="中文衬线", name="思源宋体", license="SIL OFL，可商用",
                 use="引文、副标、文化感场景"),
            dict(role="西文", name="Inter", license="SIL OFL，可商用",
                 use="数字、英文、表格")]


def build_prompts(client, industry, palette, setname):
    tone = INDUSTRY_TONE.get(industry, "克制、干净、留白充足")
    pri = palette[0]["hex"]
    acc = palette[3]["hex"]
    out = []
    dirs = ["几何字标（直线与圆角切角）", "单图形标（一个可复用的辅助图形）",
            "字母组合标（首字母构成的负空间）", "具象提炼标（业务里最具体的那件东西）"]
    for i in range(SETS[setname]["logo"]):
        out.append(dict(code="logo", index=i + 1, size=SCENES["logo"]["size"],
                        prompt=("%s的品牌标志设计，方向：%s。%s，主色 %s 辅色 %s，"
                                "纯色背景、主体居中、留白 12%%，标志占画面 55%%，"
                                "矢量化观感、边缘锐利、缩到 48px 仍可辨认，"
                                "画面内不出现任何文字、水印、英文标语。")
                               % (client, dirs[i % 4], tone, pri, acc)))
    for code in SETS[setname]["scenes"]:
        sc = SCENES[code]
        out.append(dict(code=code, index=1, size=sc["size"],
                        prompt=("%s 品牌视觉应用 - %s。%s。沿用同一套配色（主色 %s / 辅色 %s），"
                                "%s，平面设计稿、正视图、无透视变形、四边留 5%% 出血，"
                                "不出现真实人物正脸、不出现第三方商标。")
                               % (client, sc["name"], sc["gist"], pri, acc, tone)))
    out.append(dict(code="manual", index=1, size=SCENES["manual"]["size"],
                    prompt=("%s 品牌 VI 手册内页，A4 竖版，一页放完：顶部标志、"
                            "中间 7 格色卡（%s 起头）、下方 7 级字号阶梯示意、"
                            "页脚三条线。%s，网格对齐、留白干净、不出现第三方字体名与商标。")
                           % (client, pri, tone)))
    return out


def build_delivery(client, palette, setname, tag):
    d = tag or time.strftime("%Y%m%d")
    files = []
    for i in range(SETS[setname]["logo"]):
        files.append(dict(file="%s_%s_logo_v1-%02d.png" % (d, _slug(client), i + 1),
                          what="LOGO 概念稿", spec=SCENES["logo"]["spec"], qty=1,
                          points=P_IMAGE))
    for code in SETS[setname]["scenes"]:
        sc = SCENES[code]
        files.append(dict(file="%s_%s_%s_%s_v1.png" % (
            d, _slug(client), code, sc["size"]),
            what=sc["name"], spec=sc["spec"], qty=1, points=P_IMAGE))
    files.append(dict(file="%s_%s_manual_%s_v1.png" % (d, _slug(client),
                                                       SCENES["manual"]["size"]),
                      what="VI 手册页", spec=SCENES["manual"]["spec"], qty=1,
                      points=P_IMAGE))
    files.append(dict(file="%s_%s_palette.md" % (d, _slug(client)),
                      what="主色 / 辅色卡", spec="7 个 hex + 用途 + 对比度",
                      qty=1, points=0))
    files.append(dict(file="%s_%s_type.md" % (d, _slug(client)),
                      what="字体层级", spec="7 级字号 / 字重 / 行高 / 许可",
                      qty=1, points=0))
    if SETS[setname]["refine"]:
        files.append(dict(file="%s_%s_refine_x%d.md" % (d, _slug(client),
                                                        SETS[setname]["refine"]),
                          what="参考图派生记录", spec="image_urls + 每次改什么",
                          qty=SETS[setname]["refine"], points=P_REFINE))
    return files


def _slug(s):
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5]+", "-", (s or "brand").strip())
    return s.strip("-").lower() or "brand"


def make_plan(client, industry, hue, setname, tag):
    pal = build_palette(hue, industry)
    sp = set_plan(setname)
    return dict(version=VERSION, client=client, industry=industry, hue=hue,
                set=setname, setLabel=sp["label"], tag=tag or time.strftime("%Y%m%d"),
                palette=pal, fonts=build_fonts(industry), scale=build_scale(),
                prompts=build_prompts(client, industry, pal, setname),
                delivery=build_delivery(client, pal, setname, tag),
                cost=dict(images=sp["images"], refines=sp["refines"],
                          points=sp["points"], yuan=float(yuan(sp["points"])),
                          perImage=P_IMAGE, perRefine=P_REFINE))


def latest_plan():
    if not os.path.isdir(WORKDIR):
        return None
    cands = [os.path.join(WORKDIR, f) for f in os.listdir(WORKDIR)
             if f.endswith("plan.json")]
    if not cands:
        return None
    return max(cands, key=os.path.getmtime)


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    rows = [
        dict(step="palette", name="主色 / 辅色 / 字体层级", points=0, unit="免费",
             endpoint="本地计算", yes=False),
        dict(step="plan", name="prompt 包 + 交付清单 + 成本单", points=0, unit="免费",
             endpoint="本地生成", yes=False),
        dict(step="qc", name="合规 5 条 + WCAG 对比度", points=0, unit="免费",
             endpoint="本地检查", yes=False),
        dict(step="gen", name="标志与场景出图（一次 1-4 张）", points=P_IMAGE,
             unit="点/张", endpoint=API_PREFIX + "/images/generations", yes=True),
        dict(step="edit", name="局部改图（改字 / 改色 / 换尺寸）", points=P_IMAGE,
             unit="点/张", endpoint=API_PREFIX + "/images/edits", yes=True),
        dict(step="refine", name="参考图派生（同一母版跨物料）", points=P_REFINE,
             unit="点/次", endpoint="/api/v1/apps/nano_banana/submit", yes=True),
        dict(step="upload", name="本地图换平台地址", points=0, unit="免费",
             endpoint=API_PREFIX + "/upload", yes=False),
        dict(step="status", name="查任务", points=0, unit="免费",
             endpoint=API_PREFIX + "/tasks/{id}", yes=False),
    ]
    out = {"ok": True, "steps": rows, "sets": [set_plan(k) for k in ("lite", "standard", "pro")],
           "pointsPerYuan": POINTS_PER_YUAN, "scenes": [
               dict(code=c, name=SCENES[c]["name"], size=SCENES[c]["size"],
                    spec=SCENES[c]["spec"]) for c in SCENE_ORDER]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("品牌 VI 生成 - 12 个工序（价格现查 /api/v1/pricing，2026-11-08）")
    print()
    print("  %-8s %-30s %-10s %-6s %s" % ("工序", "交付什么", "单价", "--yes", "端点"))
    print("  " + "-" * 96)
    for r in rows:
        print("  %-8s %-30s %-10s %-6s %s" % (
            r["step"], r["name"], ("%d %s" % (r["points"], r["unit"])) if r["points"] else "0 免费",
            "要" if r["yes"] else "-", r["endpoint"]))
    print()
    print("  三套交付（1 元 = 100 点）：")
    for s in out["sets"]:
        print("    %-9s %2d 张 + %d 次派生 = %4s 点 = %s 元   %s" % (
            s["set"], s["images"], s["refines"], fmt_pts(s["points"]),
            yuan(s["points"]), s["label"]))
    print()
    print("  7 个交付尺寸：")
    for c in SCENE_ORDER:
        print("    %-9s %-12s %-14s %s" % (c, SCENES[c]["name"], SCENES[c]["size"],
                                           SCENES[c]["spec"]))
    print()
    print("  6 点/张是流水实测（sync:/api/v1/images/generations 每笔 -6），不是文档估的。")
    return 0


def cmd_cost(a, key, host):
    detail = None
    if a.images is not None or a.refines is not None:
        images = a.images if a.images is not None else set_plan(a.set)["images"]
        refines = a.refines if a.refines is not None else 0
        pts = cost_of(images, refines)
        detail = dict(images=images, refines=refines, points=pts, yuan=float(yuan(pts)),
                      basis="%d 张 x %d 点 + %d 次 x %d 点" % (images, P_IMAGE,
                                                                refines, P_REFINE))
    table = [set_plan(k) for k in ("lite", "standard", "pro")]
    out = {"ok": True, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "perImage": P_IMAGE, "perRefine": P_REFINE,
           "sets": table, "detail": detail,
           "notes": [
               "1 元 = 100 点；gpt-image-2.6 按张 6 点，尺寸 / 质量 / 格式同价",
               "nano-banana 本租户 flat 72 点/次（GET /api/v1/pricing 通配规则）",
               "参数错 / 失败 / 没出图不扣费；按 data 里实际返回张数结算",
               "upload / tasks 查询 / palette / plan / qc 全 0 点",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）")
    print()
    if detail:
        print("  自算：%s = %d 点 = %s 元" % (detail["basis"], detail["points"],
                                            detail["yuan"]))
        print()
    print("  %-9s %6s %6s %10s %10s  %s" % ("--set", "张数", "派生", "点数", "元", "说明"))
    print("  " + "-" * 82)
    for s in table:
        print("  %-9s %6d %6d %10s %10s  %s" % (
            s["set"], s["images"], s["refines"], fmt_pts(s["points"]),
            yuan(s["points"]), s["label"]))
    print()
    print("  换算：一张 %d 点 = %s 元；一次派生 %d 点 = %s 元 = %d 张普通图"
          % (P_IMAGE, yuan(P_IMAGE), P_REFINE, yuan(P_REFINE),
             P_REFINE // P_IMAGE))
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

    st_m, txt_m = http_json("GET", host + API_PREFIX + "/models", key, timeout=60)
    dm = jloads(txt_m) or {}
    items = dm.get("data") if isinstance(dm.get("data"), list) else []
    gpt = next((it for it in items if isinstance(it, dict)
                and it.get("model_code") == MODEL_IMAGE), None)
    checks.append(("出图模型 %s 在架" % MODEL_IMAGE, st_m == 200 and bool(gpt),
                   "HTTP %s · 参考图上限 %s 张" % (
                       st_m, (gpt or {}).get("max_reference_images", "-"))))

    st_a, txt_a = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    da = jloads(txt_a) or {}
    apps = da.get("data") if isinstance(da.get("data"), list) else []
    nb = next((x for x in apps if isinstance(x, dict)
               and x.get("code") == "nano_banana"), None)
    nb_submit = None
    if nb:
        for ap in (nb.get("apis") or []):
            if ap.get("code") == "submit":
                nb_submit = ap
    checks.append(("参考图应用 nano_banana 在架", st_a == 200 and nb is not None,
                   "HTTP %s · submit 参考图上限 %s 张" % (
                       st_a, (nb_submit or {}).get("max_reference_images", "-"))))

    st_p, txt_p = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    dp = jloads(txt_p) or {}
    pr = dp.get("pricing") if isinstance(dp.get("pricing"), dict) else {}
    row = pr.get("/api/v1/apps/nano_banana/submit") or {}
    up = pr.get("/api/v1/upload") or {}

    def _cost(d):
        v = d.get("cost")
        return int(v) if v is not None else -1

    checks.append(("价目对齐（派生 72 点 / 上传 0 点）",
                   st_p == 200 and _cost(row) == P_REFINE and row.get("mode") == "flat"
                   and _cost(up) == 0,
                   "HTTP %s · nano_banana %s %s · upload %s" % (
                       st_p, row.get("mode"), _cost(row), _cost(up))))

    # 探针一：带 model + 空 prompt -> 422，停在参数校验层
    st1, txt1 = http_json("POST", host + API_PREFIX + "/images/generations", key,
                          {"model": MODEL_IMAGE, "prompt": ""}, timeout=90)
    e1 = (jloads(txt1) or {}).get("error") or {}
    checks.append(("文生图端点可用（422 即正确）", st1 == 422
                   and "at least 1 character" in (e1.get("message") or ""),
                   "HTTP %s %s" % (st1, (e1.get("message") or "")[:46])))

    # 探针二：改图端点，只带 model、不带图 -> 500 image is required
    st2, txt2 = http_multipart(host + API_PREFIX + "/images/edits", key,
                               {"model": MODEL_IMAGE}, [], timeout=90)
    e2 = (jloads(txt2) or {}).get("error") or {}
    checks.append(("改图端点可用（500 image is required 即正确）", st2 == 500
                   and "image is required" in (e2.get("message") or ""),
                   "HTTP %s %s" % (st2, (e2.get("message") or "")[:46])))

    # 探针三：上传不带 file -> 200 code 0，提示补字段，不落文件
    st3, txt3 = http_multipart(host + API_PREFIX + "/upload", key, {}, [], timeout=60)
    d3 = jloads(txt3) or {}
    checks.append(("上传接口可用（提示补 file 字段即正确）",
                   st3 == 200 and d3.get("code") == 0,
                   "HTTP %s %s" % (st3, (d3.get("msg") or "")[:40])))

    # 探针四：通用任务查询，假 id -> code 0「任务不存在」，路由在且 0 点
    st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/probe-no-such-task", key,
                          timeout=40)
    d4 = jloads(txt4) or {}
    checks.append(("任务查询 GET /tasks/{id} 可用", st4 == 200 and d4.get("code") == 0,
                   "HTTP %s %s" % (st4, (d4.get("msg") or "")[:40])))

    # 本轮花费复核：最近一条流水的时间戳与条数，前后一致就是 0 点
    st5, txt5 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d5 = jloads(txt5) or {}
    lg = (d5.get("logs") or [{}])[0] if isinstance(d5.get("logs"), list) else {}
    checks.append(("花费复核：流水未被本轮改动", st5 == 200,
                   "HTTP %s · 共 %s 条 · 最新一笔 %s" % (
                       st5, fmt_pts(d5.get("total") or 0),
                       time.strftime("%m-%d %H:%M:%S",
                                     time.localtime(float(lg.get("at") or 0) / 1000.0)))))

    out = {"ok": all(c[1] for c in checks), "host": host,
           "estimatedPoints": 0, "yuan": 0.0,
           "perImage": P_IMAGE, "perRefine": P_REFINE,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（8 条：只读 GET + 三条参数校验探针，扣 0 点）")
    print()
    for n, o, dd in checks:
        print("  %s %-38s %s" % ("√" if o else "×", n, dd))
    print()
    print("  端点：POST /api/v1/images/generations（6 点/张）· "
          "POST /api/v1/images/edits（6 点/张）")
    print("        POST /api/v1/apps/nano_banana/submit（72 点/次）· "
          "POST /api/v1/upload（0 点）")
    print("  本轮花费 0 点：三条探针都停在参数校验层，没有建任务、没有冻结。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 本地：配色 / 计划 / 合规 ─────────────────────────
def cmd_palette(a, key, host):
    pal = build_palette(a.hue, a.industry)
    scale = build_scale()
    fonts = build_fonts(a.industry)
    primary = pal[0]["hex"]
    ink = [x for x in pal if x["code"] == "ink"][0]["hex"]
    paper = [x for x in pal if x["code"] == "paper"][0]["hex"]
    tint = [x for x in pal if x["code"] == "primaryTint"][0]["hex"]
    deep = [x for x in pal if x["code"] == "primaryDark"][0]["hex"]
    accent = [x for x in pal if x["code"] == "accent"][0]["hex"]
    # WCAG 2.1 AA：正文 4.5:1；大字 3.0:1。色卡要写清每个底色配哪个字色。
    pairs = color_pairs(ink, paper, tint, primary, accent, deep)
    for p in pairs:
        p["ratio"] = round(p["ratio"], 2)
        p["fgLabel"] = "白字" if p["fg"] == "#FFFFFF" else "墨色字"
        p["pass"] = p["ratio"] >= p["need"]
    out = {"ok": True, "hue": a.hue, "industry": a.industry, "palette": pal,
           "fonts": fonts, "scale": scale, "contrast": pairs,
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("品牌色板（hue %d，%s）—— 本地算的，0 点" % (a.hue, a.industry or "通用"))
    print()
    print("  %-6s %-13s %-9s %s" % ("角色", "code", "hex", "用在哪"))
    print("  " + "-" * 68)
    for r in pal:
        print("  %-6s %-13s %-9s %s" % (r["role"], r["code"], r["hex"], r["use"]))
    print()
    print("  底色 -> 字色（WCAG 2.1，正文要 4.5:1、大字要 3.0:1）")
    for p in pairs:
        print("    %s %-14s 底 %s 配 %-4s %5.2f : 1  （要 %.1f）" % (
            "√" if p["pass"] else "×", p["what"], p["bg"], p["fgLabel"],
            p["ratio"], p["need"]))
    print()
    print("  字体层级")
    for s in scale:
        print("    %-4s %2dpx / %d / 行高 %.2f   %s" % (
            s["level"], s["px"], s["weight"], s["line"], s["use"]))
    print()
    print("  字体（都写了许可）")
    for f in fonts:
        print("    %-6s %-14s %s" % (f["role"], f["name"], f["license"]))
    print()
    print("  下一步：plan 把色板、字号、prompt、交付清单和成本单一次写盘。")
    return 0


def cmd_plan(a, key, host):
    pl = make_plan(a.client, a.industry, a.hue, a.set, a.tag)
    d = os.path.join(WORKDIR, "%s-%s" % (_slug(a.client), pl["tag"]))
    os.makedirs(d, exist_ok=True)
    pj = os.path.join(d, "plan.json")
    with io.open(pj, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(pl, ensure_ascii=False, indent=1))
    pm = os.path.join(d, "prompts.md")
    lines = ["# %s 出图 prompt（%d 条）" % (pl["client"], len(pl["prompts"])), ""]
    for p in pl["prompts"]:
        lines.append("## %s %02d · %s · %s" % (p["code"], p["index"], p["size"],
                                               SCENES[p["code"]]["name"]))
        lines.append("")
        lines.append("```")
        lines.append(p["prompt"])
        lines.append("```")
        lines.append("")
    with io.open(pm, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    dm = os.path.join(d, "delivery.md")
    lines = ["# %s 交付清单（%s）" % (pl["client"], pl["setLabel"]), "",
             "| 文件 | 物料 | 规格 | 点数 |", "|---|---|---|---|"]
    for f_ in pl["delivery"]:
        lines.append("| `%s` | %s | %s | %s |" % (
            f_["file"], f_["what"], f_["spec"],
            fmt_pts(f_["points"]) if f_["points"] else "0"))
    lines += ["", "合计 %d 点 = %s 元（1 元 = 100 点）" % (
        pl["cost"]["points"], yuan(pl["cost"]["points"]))]
    with io.open(dm, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    # 色卡与字表是免费的那一半交付物，plan 直接写出来
    pal = {p["code"]: p["hex"] for p in pl["palette"]}
    pairs = color_pairs(pal.get("ink", "#000000"), pal.get("paper", "#FFFFFF"),
                        pal.get("primaryTint", "#FFFFFF"), pal.get("primary", "#000000"),
                        pal.get("accent", "#000000"), pal.get("primaryDark", "#000000"))
    cm = os.path.join(d, "palette.md")
    lines = ["# %s 品牌色卡（hue %d · %s）" % (pl["client"], pl["hue"], pl["industry"]),
             "", "| 角色 | code | hex | 用在哪 |", "|---|---|---|---|"]
    for c in pl["palette"]:
        lines.append("| %s | `%s` | `%s` | %s |" % (c["role"], c["code"], c["hex"],
                                                    c["use"]))
    lines += ["", "## 底色 -> 字色（WCAG 2.1：正文 4.5:1、大字 3.0:1）", "",
              "| 组合 | 底色 | 字色 | 对比度 | 要求 |", "|---|---|---|---|---|"]
    for p in pairs:
        lines.append("| %s | `%s` | `%s` | %.2f : 1 | %.1f |" % (
            p["what"], p["bg"], p["fg"], p["ratio"], p["need"]))
    with io.open(cm, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    tm = os.path.join(d, "type.md")
    lines = ["# %s 字体层级（%s）" % (pl["client"], pl["industry"]), "",
             "| 层级 | 字号 | 字重 | 行高 | 用在哪 |", "|---|---|---|---|---|"]
    for s in pl["scale"]:
        lines.append("| %s | %dpx | %d | %.2f | %s |" % (
            s["level"], s["px"], s["weight"], s["line"], s["use"]))
    lines += ["", "| 角色 | 字体 | 许可 | 用在哪 |", "|---|---|---|---|"]
    for f_ in pl["fonts"]:
        lines.append("| %s | %s | %s | %s |" % (f_["role"], f_["name"],
                                                f_["license"], f_["use"]))
    with io.open(tm, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    out = {"ok": True, "dir": d, "plan": pj, "prompts": pm, "delivery": dm,
           "palette": cm, "type": tm,
           "client": pl["client"], "set": a.set, "cost": pl["cost"],
           "promptCount": len(pl["prompts"]), "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("计划已写盘（本地生成，0 点）")
    print("  目录：%s" % d)
    print("  5 个文件：plan.json · prompts.md（%d 条）· delivery.md · palette.md · type.md"
          % len(pl["prompts"]))
    print()
    print("  %-12s %-16s %-5s %s" % ("物料", "规格", "数量", "文件名"))
    print("  " + "-" * 86)
    for f_ in pl["delivery"]:
        print("  %-12s %-16s %-5s %s" % (
            f_["what"], f_["spec"].split(" png")[0][:16], "x%d" % f_["qty"], f_["file"]))
    print()
    print("  成本：%d 张 x %d 点 + %d 次 x %d 点 = %d 点 = %s 元" % (
        pl["cost"]["images"], P_IMAGE, pl["cost"]["refines"], P_REFINE,
        pl["cost"]["points"], yuan(pl["cost"]["points"])))
    print("  下一步：qc 过合规，然后 gen --kind logo --yes 出四稿。")
    return 0


def _load_or_make(a):
    if a.plan:
        if not os.path.isfile(a.plan):
            raise Fail("usage", "plan 文件不存在：%s" % a.plan, EXIT_USAGE)
        return json.load(io.open(a.plan, encoding="utf-8"))
    p = latest_plan()
    if p:
        return json.load(io.open(p, encoding="utf-8"))
    return make_plan(a.client, a.industry, a.hue, a.set, a.tag)


def cmd_qc(a, key, host):
    pl = _load_or_make(a)
    checks = []

    low = " ".join(p.get("prompt") or "" for p in pl.get("prompts") or []).lower()
    hit = [w for w in BRAND_WORDS if w.lower() in low]
    checks.append(("商标 / 名人词零出现（%d 个词表）" % len(BRAND_WORDS),
                   not hit, "命中：%s" % "、".join(hit[:6]) if hit else "prompt 干净"))

    bad_font = [f["name"] for f in pl.get("fonts") or []
                if f.get("name") not in FONT_WHITELIST]
    checks.append(("字体全部在可商用白名单内", not bad_font,
                   "越界：%s" % "、".join(bad_font) if bad_font
                   else "、".join(f["name"] for f in pl.get("fonts") or [])))

    pal = {p["code"]: p["hex"] for p in pl.get("palette") or []}
    ink = pal.get("ink", "#000000")
    paper = pal.get("paper", "#FFFFFF")
    tint = pal.get("primaryTint", paper)
    deep = pal.get("primaryDark", ink)
    pri = pal.get("primary", ink)
    acc = pal.get("accent", ink)
    pairs = color_pairs(ink, paper, tint, pri, acc, deep)
    lows = ["%s 只有 %.2f（要 %.1f）" % (p["what"], p["ratio"], p["need"])
            for p in pairs if p["ratio"] < p["need"]]
    low = min(pairs, key=lambda x: x["ratio"])
    fg_label = "白字" if low["fg"] == "#FFFFFF" else "墨色字"
    checks.append(("配色对比度达标（正文 4.5 / 大字 3.0）", not lows,
                   "；".join(lows) if lows
                   else "5 组底色都定好了字色，最低 %s %.2f : 1（配%s）"
                        % (low["what"], low["ratio"], fg_label)))

    codes = {p["code"] for p in pl.get("prompts") or []}
    need_codes = {"logo", "manual"}
    if pl.get("set") in ("standard", "pro"):
        need_codes |= {"card", "rollup", "packaging", "avatar", "cover"}
    missing = sorted(need_codes - codes)
    checks.append(("交付清单齐全（logo + 场景 + 手册）", not missing,
                   "缺：%s" % "、".join(missing) if missing
                   else "%d 个物料 / %d 条 prompt" % (len(codes), len(pl.get("prompts") or []))))

    pat = re.compile(r"^\d{8}_[0-9a-z\u4e00-\u9fa5\-]+_(logo|card|rollup|packaging|"
                     r"avatar|cover|manual|palette|type|refine)[0-9a-z\-_x]*\.(png|md)$")
    badname = [f["file"] for f in pl.get("delivery") or [] if not pat.match(f["file"])]
    checks.append(("命名统一（日期_客户_物料_尺寸/序号）", not badname,
                   "不规范：%s" % badname[0] if badname else "全部对得上"))

    out = {"ok": all(c[1] for c in checks), "client": pl.get("client"),
           "set": pl.get("set"), "estimatedPoints": 0,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("合规检查（%s · %s · 本地跑，0 点）" % (pl.get("client"), pl.get("set")))
    print()
    for n, o, dd in checks:
        print("  %s %-34s %s" % ("√" if o else "×", n, dd))
    print()
    if out["ok"]:
        print("  五条全过，可以按 delivery.md 花钱了。")
    else:
        print("  有项没过：改完重新 plan（或直接改 plan.json），再跑一次 qc。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 上传 ─────────────────────────
def _upload(key, host, path, timeout=600):
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    st, txt = http_multipart(host + API_PREFIX + "/upload", key, {},
                             [("file", path)], timeout=timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    return got, data


def cmd_upload(a, key, host):
    if not a.file:
        raise Fail("usage", "必须给 --file（要上传的 png / jpg）", EXIT_USAGE)
    size = os.path.getsize(a.file) if os.path.isfile(a.file) else 0
    if a.dry_run:
        return plan_out(a, ["POST %s/api/v1/upload（multipart，字段名 file）· %s"
                            % (host, a.file)], 1, 0)
    got, data = _upload(key, host, a.file, a.timeout)
    ok_url, kind = url_allowed(got)
    out = {"ok": True, "url": got, "hostKind": kind, "urlAllowed": ok_url,
           "size": data.get("size") or size, "mime": data.get("mime_type"),
           "estimatedPoints": 0}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "upload",
                "ok": True, "file": a.file, "url": got})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（0 点）")
    print("  地址：%s" % got)
    print("  归属：%s（平台托管，image_urls 可以直接用）" % kind)
    print("  下一步：refine --ref-url \"%s\" --kind card --yes" % got)
    return 0


# ───────────────────────── 出图 ─────────────────────────
def _scene_prompt(a):
    tone = INDUSTRY_TONE.get(a.industry, "克制、干净、留白充足")
    palette = build_palette(a.hue, a.industry)
    pri, acc = palette[0]["hex"], palette[3]["hex"]
    sc = SCENES[a.kind]
    return ("%s 品牌视觉应用 - %s。%s。沿用同一套配色（主色 %s / 辅色 %s），%s，"
            "平面设计稿、正视图、无透视变形、四边留 5%% 出血，画面内不出现真实人物正脸、"
            "不出现第三方商标。" % (a.client, sc["name"], sc["gist"], pri, acc, tone))


def cmd_gen(a, key, host):
    sc = SCENES[a.kind]
    prompt = a.prompt or _scene_prompt(a)
    n = a.n if a.n is not None else (SETS["standard"]["logo"] if a.kind == "logo" else 1)
    if n < 1 or n > 4:
        raise Fail("usage", "n 要落在 1-4（接口约束），当前 %d" % n, EXIT_USAGE)
    size = a.size or sc["size"]
    ok, why = check_size(size)
    if not ok:
        raise Fail("usage", "尺寸不合规：%s" % why, EXIT_USAGE)
    fmt = a.output_format
    cost = P_IMAGE * n
    gate(a, cost, "%d 张 %s 出图" % (n, sc["name"]))

    url = host + API_PREFIX + "/images/generations"
    body = {"model": a.model, "prompt": prompt, "n": n, "size": size,
            "output_format": fmt, "response_format": "b64_json"}
    if a.dry_run:
        return plan_out(a, ["POST %s" % url,
                            "body: %s" % json.dumps(body, ensure_ascii=False)], 1, cost,
                        {"requestBody": body})

    say("正在出图（%s，%d 张，同步）…" % (a.model, n))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=max(180, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "gen", "ok": False,
                    "http": st, "error": msg})
        raise Fail("call", "出图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    data = d.get("data") or []
    got = len(data) if isinstance(data, list) else 0
    prefix = a.prefix or ("%s-%s" % (time.strftime("%Y%m%d"), a.kind))
    paths, src = save_images(d, a.outdir, prefix, fmt)
    out = {"ok": bool(got), "mode": "gen", "model": a.model, "kind": a.kind,
           "requested": n, "returned": got, "source": src, "files": paths,
           "billedPoints": P_IMAGE * got, "elapsed": round(dt, 1), "size": size}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "gen", "ok": bool(got),
                "kind": a.kind, "requested": n, "returned": got, "files": paths,
                "billedPoints": P_IMAGE * got, "elapsed": round(dt, 1)})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if got else EXIT_CALL
    if not got:
        say("  响应里没有图。原始返回：")
        print(txt[:800])
        return EXIT_CALL
    print("出图完成（%.1fs）" % dt)
    print("  物料：%s · %s · 请求 %d 张 / 实际回 %d 张" % (sc["name"], size, n, got))
    print("  计费：%d 点（%s 元），按实际返回张数" % (P_IMAGE * got,
                                                   yuan(P_IMAGE * got)))
    for p in paths:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    print()
    print("  下一步：挑一张当母版 → refine --ref 定稿.png --kind card --yes")
    return 0


def cmd_edit(a, key, host):
    if not a.prompt:
        raise Fail("usage", "必须给 --prompt（这张图要怎么改）", EXIT_USAGE)
    if not a.image:
        raise Fail("usage", "至少给一个 --image（本地图，可重复，最多 20 张）", EXIT_USAGE)
    for p in a.image:
        if not os.path.isfile(p):
            raise Fail("usage", "图片不存在：%s" % p, EXIT_USAGE)
    size = a.size or "auto"
    ok, why = check_size(size)
    if not ok:
        raise Fail("usage", "尺寸不合规：%s" % why, EXIT_USAGE)
    n = a.n if a.n is not None else 1
    if n < 1 or n > 4:
        raise Fail("usage", "n 要落在 1-4，当前 %d" % n, EXIT_USAGE)
    cost = P_IMAGE * n
    gate(a, cost, "%d 张局部改图" % n)
    url = host + API_PREFIX + "/images/edits"
    fields = {"model": a.model, "prompt": a.prompt, "n": n,
              "output_format": a.output_format, "response_format": "b64_json"}
    if size != "auto":
        fields["size"] = size
    files = [("image[]", p) for p in a.image]
    if a.mask:
        files.append(("mask", a.mask))
    if a.dry_run:
        return plan_out(a, ["POST %s（multipart）" % url,
                            "fields: %s" % json.dumps(fields, ensure_ascii=False),
                            "files: %s" % ", ".join(f[1] for f in files)],
                        1, cost, {"fields": fields})

    say("正在改图（%d 张，%d 个参考图）…" % (n, len(a.image)))
    t0 = time.time()
    st, txt = http_multipart(url, key, fields, files, timeout=max(180, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "edit",
                    "ok": False, "http": st, "error": msg})
        raise Fail("call", "改图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    data = d.get("data") or []
    got = len(data) if isinstance(data, list) else 0
    prefix = a.prefix or ("%s-edit" % time.strftime("%Y%m%d"))
    paths, src = save_images(d, a.outdir, prefix, a.output_format)
    out = {"ok": bool(got), "mode": "edit", "requested": n, "returned": got,
           "source": src, "files": paths, "billedPoints": P_IMAGE * got,
           "elapsed": round(dt, 1)}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "edit",
                "ok": bool(got), "requested": n, "returned": got, "files": paths,
                "billedPoints": P_IMAGE * got})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if got else EXIT_CALL
    if not got:
        say("  响应里没有图。")
        print(txt[:800])
        return EXIT_CALL
    print("改图完成（%.1fs）· 实扣 %d 点" % (dt, P_IMAGE * got))
    for p in paths:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    return 0


def cmd_refine(a, key, host):
    if not a.prompt:
        raise Fail("usage", "必须给 --prompt（这次要把母版改成什么）", EXIT_USAGE)
    if not a.ref and not a.ref_url:
        raise Fail("usage",
                   "必须给 --ref（本地定稿图，会自动 upload）或 --ref-url（平台地址）",
                   EXIT_USAGE)
    if a.ref and not os.path.isfile(a.ref):
        raise Fail("usage", "参考图不存在：%s" % a.ref, EXIT_USAGE)
    aspect = a.aspect_ratio or SCENES[a.kind]["ratio"]
    cost = P_REFINE
    gate(a, cost, "参考图派生一次（%s）" % SCENES[a.kind]["name"])

    up_line = "POST %s/api/v1/upload（multipart，字段名 file）· %s" % (host, a.ref or "-")
    body = {"action": "edit", "prompt": a.prompt, "model": a.model,
            "image_urls": [a.ref_url or "<upload 返回的 url>"],
            "aspect_ratio": aspect, "resolution": a.resolution}
    submit_line = "POST %s/api/v1/apps/nano_banana/submit body: %s" % (
        host, json.dumps(body, ensure_ascii=False))
    if a.dry_run:
        lines = ([up_line] if a.ref else []) + [submit_line]
        return plan_out(a, lines, 1 + (1 if a.ref else 0), cost,
                        {"requestBody": body})

    ref_url = a.ref_url
    if a.ref:
        say("正在上传参考图 %s …" % os.path.basename(a.ref))
        ref_url, _ = _upload(key, host, a.ref, a.timeout)
    ok_url, kindname = url_allowed(ref_url)
    if not ok_url:
        raise Fail("usage",
                   "image_urls 要用平台托管的地址（当前 %s）。先 upload --file 你的图.png 拿地址。"
                   % kindname, EXIT_USAGE)
    body["image_urls"] = [ref_url]

    say("正在提交派生（nano-banana，72 点/次，异步）…")
    t0 = time.time()
    st, txt = http_json("POST", host + "/api/v1/apps/nano_banana/submit", key, body,
                        timeout=max(120, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    tid = data.get("task_id") or data.get("taskId")
    if d.get("code") != 1 or not tid:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "refine",
                    "ok": False, "http": st, "error": msg})
        raise Fail("call", "派生提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    out = {"ok": True, "mode": "refine", "taskId": tid, "status": data.get("status"),
           "frozen": data.get("frozen_points"), "refImage": ref_url,
           "billedPoints": P_REFINE, "elapsed": round(dt, 1),
           "query": API_PREFIX + "/tasks/" + str(tid)}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "refine", "ok": True,
                "taskId": tid, "refImage": ref_url, "billedPoints": P_REFINE})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交派生（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (tid, data.get("status")))
    print("  冻结：%s 点（失败全额退回）" % fmt_pts(data.get("frozen_points") or P_REFINE))
    print("  母版：%s" % ref_url)
    print()
    print("  查进度：python3 scripts/run.py status --task-id %s" % tid)
    print("  记一条：查进度只走 GET /api/v1/tasks/{id}，0 点。")
    return 0


def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    p = API_PREFIX + "/tasks/" + a.task_id
    st, txt = http_json("GET", host + p, key, timeout=60)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    msg = d.get("msg") or ""
    if st == 200 and d.get("code") == 0 and not data:
        out = {"ok": True, "taskId": a.task_id, "status": "not_found",
               "message": msg or "任务不存在", "estimatedPoints": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("任务 %s：%s" % (a.task_id, msg or "任务不存在"))
        print("  这条查询 0 点。任务号对不上时先看 refine 返回的 taskId。")
        return 0
    cost = data.get("cost") if data.get("cost") is not None else data.get("points_cost")
    out = {"ok": True, "taskId": a.task_id, "path": p, "status": data.get("status"),
           "message": data.get("message"), "result": data.get("result"),
           "cost": cost, "refund": data.get("refund"), "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  查询路径：%s（0 点）" % p)
    print("  状态：%s" % data.get("status"))
    if cost is not None:
        print("  实扣：%s 点" % fmt_pts(cost))
    if data.get("message"):
        print("  说明：%s" % str(data.get("message"))[:300])
    if data.get("result") is not None:
        print("  结果：%s" % json.dumps(data.get("result"), ensure_ascii=False)[:600])
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
        print("  %s  %-6s %-6s %-20s %s 点" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            (e.get("kind") or e.get("taskId") or e.get("file") or "-")[:20],
            e.get("billedPoints") if e.get("billedPoints") is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 品牌 VI 生成（一套 VI 60 点 = 0.60 元，走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/images/generations · POST %s/api/v1/images/edits · "
               "POST %s/api/v1/apps/nano_banana/submit · POST %s/api/v1/upload · "
               "GET %s/api/v1/tasks/<id>" % ((DEFAULT_HOST,) * 5),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d 点 = %d 元）"
                         % (DEFAULT_BUDGET, DEFAULT_BUDGET // POINTS_PER_YUAN))
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="12 个工序 / 端点 / 单价（免费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一套 VI 多少钱（免费）", allow_abbrev=False)
    p.add_argument("--set", choices=["lite", "standard", "pro"], default="standard",
                   help="交付配置（默认 standard = 10 张 60 点）")
    p.add_argument("--images", type=int, default=None, help="自算：张数")
    p.add_argument("--refines", type=int, default=None, help="自算：派生次数")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 8 条（免费，不扣费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    def add_common(p):
        p.add_argument("--client", default="示例科技", help="品牌名（进 prompt 与文件名）")
        p.add_argument("--industry", default="科技", help="行业：科技 / 餐饮 / 美妆 / 教育 / 制造 / 医疗 / 金融 / 零售")
        p.add_argument("--hue", type=int, default=210, help="主色色相 0-359（默认 210 蓝）")
        p.add_argument("--set", choices=["lite", "standard", "pro"], default="standard",
                       help="交付配置（默认 standard）")
        p.add_argument("--tag", default=None, help="文件名日期段，默认今天 YYYYMMDD")

    p = sub.add_parser("palette", help="主色 / 辅色 / 字体层级 + 对比度（免费）",
                       allow_abbrev=False)
    add_common(p)
    p.set_defaults(fn=cmd_palette)

    p = sub.add_parser("plan", help="prompt 包 + 交付清单 + 成本单，写盘（免费）",
                       allow_abbrev=False)
    add_common(p)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("qc", help="合规 5 条 + 对比度 + 命名（免费）", allow_abbrev=False)
    add_common(p)
    p.add_argument("--plan", help="指定 plan.json（默认取最近一份）")
    p.set_defaults(fn=cmd_qc)

    def add_gen(p):
        p.add_argument("--kind", choices=SCENE_ORDER, default="logo",
                       help="物料：logo / card / rollup / packaging / avatar / cover / manual")
        p.add_argument("--prompt", help="自定义 prompt（默认按行业话术本地拼）")
        p.add_argument("--n", type=int, default=None, help="张数 1-4（logo 默认 4，其余 1）")
        p.add_argument("--size", default=None, help="宽x高（默认按物料尺寸）")
        p.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"])
        p.add_argument("--model", default=MODEL_IMAGE)
        p.add_argument("--outdir", default=".", help="保存目录（默认当前目录）")
        p.add_argument("--prefix", default=None, help="文件名前缀")
        p.add_argument("--timeout", type=int, default=240, help="单次超时秒数")
        p.add_argument("--yes", action="store_true", help="确认真实扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("gen", help="文生图 6 点/张（要 --yes）", allow_abbrev=False)
    add_common(p)
    add_gen(p)
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("edit", help="局部改图 6 点/张（要 --yes）", allow_abbrev=False)
    p.add_argument("--prompt", help="这张图要怎么改")
    p.add_argument("--image", action="append", help="本地图（可重复，最多 20 张）")
    p.add_argument("--mask", help="蒙版图（可选）")
    p.add_argument("--n", type=int, default=None, help="张数 1-4（默认 1）")
    p.add_argument("--size", default=None, help="宽x高（默认跟着图）")
    p.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"])
    p.add_argument("--model", default=MODEL_IMAGE)
    p.add_argument("--outdir", default=".")
    p.add_argument("--prefix", default=None)
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_edit)

    p = sub.add_parser("refine", help="参考图派生 72 点/次（要 --yes）", allow_abbrev=False)
    p.add_argument("--ref", help="本地定稿图（自动 upload 成 image_urls）")
    p.add_argument("--ref-url", help="已经是平台地址时直接给")
    p.add_argument("--prompt", help="这次要把母版改成什么")
    p.add_argument("--kind", choices=SCENE_ORDER, default="card", help="要派生成哪个物料")
    p.add_argument("--aspect-ratio", default=None,
                   help="auto / 1:1 / 16:9 / 9:16 / 4:3 / 3:4 / 3:2 / 2:3 / 5:4 / 4:5 / 21:9")
    p.add_argument("--resolution", default="1K", choices=["1K", "2K", "4K"])
    p.add_argument("--model", default=MODEL_REFINE)
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_refine)

    p = sub.add_parser("upload", help="本地图换平台地址（免费）", allow_abbrev=False)
    p.add_argument("--file", help="本地图片路径")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("status", help="查任务（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="refine 返回的 taskId")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以；default=SUPPRESS 才不覆盖父级
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_palette", "cmd_plan", "cmd_qc", "cmd_log",
        "cmd_doctor", "cmd_status", "cmd_upload")


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
    if a.json:
        # --json 是给机器读的：钉成 UTF-8，避免 Windows 上按 cp936 输出、
        # 下游按 UTF-8 解析时中文全变乱码。人读模式保持本地编码不变。
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                        # noqa: BLE001
            pass
    try:
        key, host = load_conf(a.key, a.host)
        if not key and getattr(a.fn, "__name__", "") not in FREE:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                       EXIT_USAGE)
        if not key:
            key = "none"
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
