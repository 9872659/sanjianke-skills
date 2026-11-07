#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 电商详情页（sanjianke-ecom-detail）

一张商品实拍，出「一整页」详情图：主图 5 + 卖点 3 + 场景 2 + 细节 2 + 参数 1 = 13 位。
本包不是新接口，是把已有出图线按电商详情页的岗位流程重排一遍：

  ① 文生图   gpt-image-2.6   6 点/张   POST /api/v1/images/generations（同步）
  ② 改图     gpt-image-2.6   6 点/张   POST /api/v1/images/edits（multipart，带实拍图保商品不走样）
  ③ 参考图   nano_banana    72 点/次   POST /api/v1/apps/nano_banana/submit（异步，2K/4K）
  ④ 换装     dressing       200 点/次   POST /api/v1/apps/dressing_diffusion/submit（异步，模特试穿）
  ⑤ 上传     /api/v1/upload   0 点      multipart 字段名 file，回 oss.gpu.likeadmin.cn 白名单地址

## 价格（GET /api/v1/pricing 2026-11-08 现查，共 115 条规则）

  /api/v1/upload                          flat 0    「上传不计费」
  /api/v1/apps/nano_banana/*              flat 72   「AI 商品图固定 72 点/次」
  /api/v1/apps/dressing_diffusion/*       flat 200  「固定 200 点/次」
  POST /api/v1/images/generations         6 点/张（文档 + 2026-11-07 实测一笔 -6）
  —— 价目表 115 条规则里**没有** images/generations 这一条，所以本包用 422 探针验端点，
     不拿价格表当证据；6 点/张来自文档口径与流水实扣。

## 两条探针纪律（一次读错就是一次的钱）

  ❌ GET /api/v1/apps/<app>   → 命中 /apps/<app>/* 通配计价，nano 72 / 换装 200，sync 不退
  ⛔ 应用层 /query 轮询        → nano_banana/query 72 点/次，查一次就是一张商品图的价
  ✅ 只读白名单：/models /apps /pricing /tasks/<id> /user/balance /user/balance/logs
  ✅ 写探针：POST /upload 空表单（0 点）、POST /images/generations 空 prompt（422）
  本包 doctor 只打这两类；status 只走 GET /api/v1/tasks/<id>。

## 尺寸（这是电商详情页最容易白跑的一张表）

  800×800 只有 640,000 像素，低于 gpt-image 的 655,360 下限 → 请求改成 1024×1024，
  1024 方图本身就是「1:1 且不小于 800」的合法主图，可直接上架。
  抖音 1200×1600（3:4）本身合法，原样请求。参数图 750 宽 → 请求 768×1024。

## 子命令

  catalog   13 位结构 + 五个平台的尺寸表 + 四条线的价（免费）
  cost      先算钱：13 位 / 一页 / 四种走法（免费）
  doctor    自检 Key / 端点 / 价目 / 上传 / 流水，并证明本轮 0 点（免费）
  plan      出整页结构单：13 个位的画面、文案位、尺寸、文件名（免费）
  upload    本地实拍图传平台，拿白名单地址（免费）
  gen       按位出图（6 点/张，要 --yes，受 --budget 管）
  check     交付验收：齐不齐 / 命名 / 像素 / 文案合规（免费）
  status    查异步任务（免费，只走 GET /api/v1/tasks/<id>）
  log       本地台账（免费）

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --platform taobao
  python3 scripts/run.py doctor
  python3 scripts/run.py plan --product "白色亚麻衬衫" --sku SHIRT01 --platform taobao --write
  python3 scripts/run.py upload --file shot.jpg
  python3 scripts/run.py gen --plan out/plan.json --ref shot.jpg --outdir out --yes
  python3 scripts/run.py check --dir out --plan out/plan.json

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import base64
import io
import json
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

# ── GBK 编码兜底（2026-11-07 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时 Python 用本地编码（cp936），
# 遇到 cp936 编不出的字符会 UnicodeEncodeError 崩掉；先加 replace 兜底。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "ecom-detail-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-ecom-detail/%s" % VERSION

POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 500            # 点（5 元）
POINTS_GPT = 6                  # 6 点/张，与尺寸 / 质量 / 格式无关
POINTS_NANO = 72                # nano_banana 固定 72 点/次
POINTS_NANO_VIEW = 25           # 商品多角度：25 点 × 选中视角数（views[] 时生效）
POINTS_DRESS = 200              # dressing_diffusion 固定 200 点/次

DEFAULT_MODEL = "gpt-image-2.6"
NANO_MODEL = "nano-banana"
DEFAULT_TIMEOUT = 240
DEFAULT_RESOLUTION = "1K"

GEN_PATH = API_PREFIX + "/images/generations"
EDIT_PATH = API_PREFIX + "/images/edits"
NANO_PATH = API_PREFIX + "/apps/nano_banana/submit"
DRESS_PATH = API_PREFIX + "/apps/dressing_diffusion/submit"
UPLOAD_PATH = API_PREFIX + "/upload"
TASKS_PATH = API_PREFIX + "/tasks/"

# ── 五个平台的尺寸（req = 发给模型的 size，pub = 平台上架口径）──────────────
# 800×800 = 640,000 像素 < 655,360 下限，所以 1:1 位统一请求 1024×1024。
PLATFORMS = {
    "taobao": dict(name="淘宝 / 天猫", ratio="1:1",
                   main_req=(1024, 1024), main_pub=(800, 800),
                   param_req=(768, 1024), param_pub=(750, 1000),
                   note="主图 1:1、不小于 800 方图；详情页宽 750"),
    "douyin": dict(name="抖音商城", ratio="3:4",
                   main_req=(1200, 1600), main_pub=(1200, 1600),
                   param_req=(768, 1024), param_pub=(750, 1000),
                   note="主图 3:4 竖版 1200x1600；详情页宽 750"),
    "pinduoduo": dict(name="拼多多", ratio="1:1",
                      main_req=(1024, 1024), main_pub=(800, 800),
                      param_req=(768, 1024), param_pub=(750, 1000),
                      note="主图 1:1 方图；详情页宽 750"),
    "jd": dict(name="京东", ratio="1:1",
               main_req=(1024, 1024), main_pub=(800, 800),
               param_req=(768, 1024), param_pub=(750, 1000),
               note="主图 1:1、不小于 800 方图；详情页宽 750"),
    "1688": dict(name="1688", ratio="1:1",
                 main_req=(1024, 1024), main_pub=(800, 800),
                 param_req=(768, 1024), param_pub=(750, 1000),
                 note="主图 1:1 方图；详情页宽 750"),
}
PLATFORM_ORDER = ["taobao", "douyin", "pinduoduo", "jd", "1688"]

# ── 13 位结构（行业顺序：主图 5 → 卖点 3 → 场景 2 → 细节 2 → 参数 1）──────
SLOTS = [
    dict(no=1, kind="main", name="主图1 正面白底",
         aim="搜索结果里第一眼看到的图，纯白底、商品占画面 80%",
         prompt="纯白背景商品正面图，柔和顶光，商品居中占画面 80%，无文字无水印",
         copy=["角标：品牌或品类（不超过 6 字）"]),
    dict(no=2, kind="main", name="主图2 核心卖点",
         aim="一句话讲清为什么买它",
         prompt="商品正面图，右侧留白放一行大字，纯色背景，画面干净",
         copy=["标题：一句话核心卖点（不超过 10 字）", "角标：价格锚点或赠品"]),
    dict(no=3, kind="main", name="主图3 使用场景",
         aim="让买家看见自己在用的那一刻",
         prompt="商品在真实使用场景中的中景，自然光，生活化布景，主体清晰",
         copy=["标题：谁在什么场景用（不超过 10 字）"]),
    dict(no=4, kind="main", name="主图4 细节特写",
         aim="用材质与工艺打消「便宜货」的念头",
         prompt="材质与工艺微距特写，浅景深，纹理清晰，背景干净",
         copy=["标注 2 处：材质名 / 工艺名"]),
    dict(no=5, kind="main", name="主图5 规格尺寸",
         aim="把尺寸说清，减少退货",
         prompt="商品平铺俯拍，浅灰背景，留出尺寸标注线的位置",
         copy=["标题：规格型号", "标注 3 处：长 / 宽 / 高（cm）"]),
    dict(no=6, kind="point", name="卖点1 痛点对比",
         aim="先让买家认出自己的麻烦",
         prompt="左右对比构图，同一光线：左边旧方案的麻烦，右边使用本品后的结果",
         copy=["标题：痛点（不超过 8 字）", "副标题：解决后的结果（不超过 18 字）"]),
    dict(no=7, kind="point", name="卖点2 材质工艺",
         aim="把卖点写成可验证的参数",
         prompt="材质剖面与工艺特写，干净背景，留出参数文字位",
         copy=["标题：材质（不超过 8 字）",
               "副标题：可验证参数（克重 / 密度 / 工艺）"]),
    dict(no=8, kind="point", name="卖点3 信任背书",
         aim="检测报告、认证、销量，选一个最硬的",
         prompt="商品与检测报告 / 资质证书的静物摆拍，暖光，留出证书位置",
         copy=["标题：背书类型（不超过 8 字）",
               "副标题：报告编号 / 认证名称（不超过 18 字）"]),
    dict(no=9, kind="scene", name="场景1 生活场景",
         aim="详情页第一屏的场景氛围",
         prompt="家居生活场景中景，商品在使用状态，暖色调，背景有生活细节但不抢主体",
         copy=["副标题：使用时刻（不超过 12 字）"]),
    dict(no=10, kind="scene", name="场景2 出行 / 送礼",
         aim="把使用半径从家里扩到外面",
         prompt="户外或送礼场景，自然光，商品与人物手部互动，画面松弛",
         copy=["副标题：出行 / 送礼场景（不超过 12 字）"]),
    dict(no=11, kind="detail", name="细节1 材质微距",
         aim="放大到能看清纹理的那一档",
         prompt="布料或材质 45 度微距，纹理与光泽清晰，纯色背景",
         copy=["标注 2 处：材质 / 触感"]),
    dict(no=12, kind="detail", name="细节2 工艺走线",
         aim="用走线、五金、接口证明做工",
         prompt="缝线 / 接口 / 五金件特写，微距，质感清晰",
         copy=["标注 2 处：工艺名词"]),
    dict(no=13, kind="param", name="参数图 规格表",
         aim="详情页最后一屏，客服少回答一半问题",
         prompt="浅灰底参数表版式，标题在上，8 行参数留白，无插画",
         copy=["表格 8 行：型号 / 材质 / 尺寸 / 重量 / 颜色 / 包装 / 产地 / 保修"]),
]
SLOT_BY_NO = {s["no"]: s for s in SLOTS}
KINDS = ["main", "point", "scene", "detail", "param"]
KIND_CN = {"main": "主图", "point": "卖点", "scene": "场景", "detail": "细节", "param": "参数"}
STRUCTURE = {"main": 5, "point": 3, "scene": 2, "detail": 2, "param": 1}

# 命名规范：<SKU>_D<位号两位>_<类型>_<宽x高>_v<版本两位>.<扩展名>
NAME_RE = re.compile(
    r"^(?P<sku>[A-Za-z0-9]{2,12})_D(?P<no>\d{2})"
    r"_(?P<kind>main|point|scene|detail|param)_(?P<spec>\d{3,4}x\d{3,4})"
    r"_v(?P<ver>\d{2})\.(?P<ext>png|jpg|jpeg|webp)$")

# 绝对化用语 / 功效词：平台审核会驳回，`check` 逐条扫文案位
ABSOLUTE_WORDS = [
    "最好", "最佳", "最强", "最低", "最高", "最优", "最便宜", "最先进", "最流行",
    "第一品牌", "全国第一", "销量第一", "顶级", "极致", "国家级", "世界级", "全网",
    "唯一", "绝对", "100%", "百分百", "永久", "纯天然", "根治", "特效", "万能",
    "史上", "无副作用", "包治", "秒杀全场",
]

# 合规改写对照（写进 page.md，照着改就行）
REWRITE = [
    ("全网最低价", "同款比价截图 + 到手价（附链接）"),
    ("销量第一", "近 30 天成交 N 单（后台截图）"),
    ("顶级面料", "成分 100% 亚麻，克重 180g（检测报告编号）"),
    ("永久不掉色", "色牢度 4 级（GB/T 5713 检测）"),
    ("纯天然无添加", "配料表仅 3 项：…（见包装）"),
    ("一秒见效", "连续使用 14 天的对比图（同光线同角度）"),
]


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


def _w(s):
    """显示宽度：中日韩字符算 2 列，表格才对得齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
               for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def cut(s, width):
    """按显示宽度截断，表格才不会被中文撑破。"""
    out, used = "", 0
    for ch in str(s):
        w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + w > width:
            break
        out += ch
        used += w
    return out


def fmt_pts(n):
    if isinstance(n, float) and abs(n - round(n)) > 1e-9:
        return "{:,.2f}".format(n)
    return "{:,}".format(int(round(n)))


def fmt_yuan(pts):
    return "{:,.2f} 元".format(float(pts) / POINTS_PER_YUAN)


def wh(size):
    return "%dx%d" % (size[0], size[1])


def parse_wh(text):
    m = re.match(r"^(\d{2,5})x(\d{2,5})$", (text or "").strip().lower())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def size_problem(size):
    """gpt-image 自定义尺寸四条约束。返回 None 表示合规，否则返回原因。"""
    w, h = size
    if w % 16 or h % 16:
        return "宽高要是 16 的倍数（%dx%d）" % (w, h)
    if max(w, h) > 3840:
        return "单边超过 3840（%dx%d）" % (w, h)
    if max(w, h) > min(w, h) * 3:
        return "长边 / 短边超过 3:1（%dx%d）" % (w, h)
    px = w * h
    if px < 655360 or px > 8294400:
        return "总像素要在 655,360 - 8,294,400（%dx%d = %s）" % (w, h, "{:,}".format(px))
    return None


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                        # noqa: BLE001
        return None


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
            with open(cfg, encoding="utf-8") as f:
                d = json.load(f)
            if not key:
                k = d.get("key") or d.get("api_key")
                if k:
                    key = str(k).strip()
            if not host and d.get("host"):
                host = str(d["host"]).rstrip("/")
        except Exception:                                    # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=120):
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
    except Exception as e:                                   # noqa: BLE001
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


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
        ext = os.path.splitext(fn)[1].lower()
        ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".webp": "image/webp"}.get(ext, "application/octet-stream")
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
    except Exception as e:                                   # noqa: BLE001
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def url_allowed(u):
    """上游对素材地址的白名单。返回 (ok, 说明)。"""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:                                        # noqa: BLE001
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


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or ""]
            s = " · ".join([b for b in bits if b])
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


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            with open(LEDGER, encoding="utf-8") as f:
                arr = json.load(f)
        arr.append(rec)
        with io.open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(arr[-300:], ensure_ascii=False, indent=1))
    except Exception:                                        # noqa: BLE001
        pass


def image_size(path):
    """只读文件头拿像素，零依赖。"""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return (int.from_bytes(head[16:20], "big"),
                        int.from_bytes(head[20:24], "big"))
            if head[:2] != b"\xff\xd8":
                return None
            f.seek(2)
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                while b == b"\xff":
                    b = f.read(1)
                if not b:
                    return None
                marker = b[0]
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    continue
                ln = f.read(2)
                if len(ln) < 2:
                    return None
                seg = int.from_bytes(ln, "big")
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    data = f.read(5)
                    if len(data) < 5:
                        return None
                    return (int.from_bytes(data[3:5], "big"),
                            int.from_bytes(data[1:3], "big"))
                f.seek(seg - 2, 1)
    except OSError:
        return None


# ───────────────────────── 结构单 ─────────────────────────
def slot_sizes(plat, slot):
    """返回 (请求尺寸, 上架尺寸)。"""
    p = PLATFORMS[plat]
    if slot["kind"] == "param":
        return p["param_req"], p["param_pub"]
    return p["main_req"], p["main_pub"]


def slot_fname(sku, slot, size, ver=1, ext="png"):
    return "%s_D%02d_%s_%s_v%02d.%s" % (sku, slot["no"], slot["kind"],
                                        wh(size), int(ver), ext)


def slot_prompt(slot, product, sells, plat):
    bits = [slot["prompt"], "商品：%s" % product]
    if sells:
        bits.append("可以入画的卖点关键词：%s" % "、".join(sells))
    p = PLATFORMS[plat]
    bits.append("画面比例 %s，%s 详情页用图，画面干净，无平台 logo、无水印"
                % (p["ratio"] if slot["kind"] != "param" else "3:4", p["name"]))
    return "；".join(bits) + "。"


def build_plan(product, sku, plat, sells, ver=1):
    slots, total = [], 0
    for s in SLOTS:
        req, pub = slot_sizes(plat, s)
        total += POINTS_GPT
        slots.append({"no": s["no"], "kind": s["kind"], "kindName": KIND_CN[s["kind"]],
                      "name": s["name"], "aim": s["aim"], "copy": s["copy"],
                      "prompt": slot_prompt(s, product, sells, plat),
                      "requestSize": wh(req), "publishSize": wh(pub),
                      "file": slot_fname(sku, s, req, ver), "points": POINTS_GPT})
    return {"ok": True, "sku": sku, "product": product, "platform": plat,
            "platformName": PLATFORMS[plat]["name"], "ratio": PLATFORMS[plat]["ratio"],
            "structure": dict(STRUCTURE), "slots": slots,
            "perPage": total, "yuan": round(total / float(POINTS_PER_YUAN), 2),
            "naming": "%s_D<位号两位>_<类型>_<宽x高>_v<版本两位>.<png|jpg|webp>" % sku,
            "deliver": [
                {"kind": k, "label": KIND_CN[k], "count": STRUCTURE[k],
                 "requestSize": wh(slot_sizes(plat, {"kind": k} if k != "param"
                                               else {"kind": "param"})[0]),
                 "publishSize": wh(slot_sizes(plat, {"kind": k} if k != "param"
                                               else {"kind": "param"})[1])}
                for k in KINDS]}


def load_plan(path):
    if not path:
        return None
    if not os.path.isfile(path):
        raise Fail("usage", "结构单不存在：%s（先跑 plan --write）" % path, EXIT_USAGE)
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:                                   # noqa: BLE001
        raise Fail("usage", "结构单读不了：%s: %s" % (type(e).__name__, e), EXIT_USAGE)


def select_slots(plan, a):
    slots = plan.get("slots") or []
    want = []
    if a.slot:
        for chunk in str(a.slot).split(","):
            t = chunk.strip().lower()
            if not t:
                continue
            t = t[1:] if t.startswith("d") else t
            if not t.isdigit():
                raise Fail("usage", "--slot 写法：1,2,3 或 D01,D02", EXIT_USAGE)
            n = int(t)
            if n not in SLOT_BY_NO:
                raise Fail("usage", "--slot 取 1 到 13（详情页 13 个位）", EXIT_USAGE)
            want.append(n)
    if a.kind:
        kinds = [k.strip() for k in str(a.kind).split(",") if k.strip()]
        bad = [k for k in kinds if k not in KINDS]
        if bad:
            raise Fail("usage", "不认识的位类型：%s（可选 %s）"
                       % (",".join(bad), " / ".join(KINDS)), EXIT_USAGE)
        if not want:
            want = [s["no"] for s in slots if s["kind"] in kinds]
    if not want:
        want = [s["no"] for s in slots]
    picked = [s for s in slots if s["no"] in want]
    if not picked:
        raise Fail("usage", "没选中任何位", EXIT_USAGE)
    return sorted(picked, key=lambda s: s["no"])


# ───────────────────────── 闸门 ─────────────────────────
def gate(a, cost, what):
    """两道闸门：超预算先退 5（一个请求都不发），再要 --yes 退 4。"""
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %s 点超过 --budget %s 点（%s）。调大 --budget 或减少位数。"
                   % (fmt_pts(cost), fmt_pts(a.budget), what), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "%s预计 %s 点（%s）。这会真实提交并冻结点数，确认请加 --yes。"
                   % (what, fmt_pts(cost), fmt_yuan(cost)), EXIT_CONFIRM)


def save_images(d, outdir, name, timeout=180):
    """把 data[] 里的 b64_json / url 落成文件，返回 (文件列表, 张数, 来源)。"""
    items = d.get("data") or []
    files, src = [], "none"
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        target = os.path.join(outdir, name if len(items) == 1
                              else "%s-%02d%s" % (os.path.splitext(name)[0], i + 1,
                                                  os.path.splitext(name)[1]))
        if it.get("b64_json"):
            src = "b64_json"
            try:
                raw = base64.b64decode(it["b64_json"])
            except Exception:                                # noqa: BLE001
                continue
            with open(target, "wb") as f:
                f.write(raw)
            files.append(target)
        elif it.get("url"):
            src = "url"
            try:
                req = urllib.request.Request(it["url"], headers={
                    "User-Agent": "Mozilla/5.0 (compatible; sanjianke-ecom-detail)"})
                with urllib.request.urlopen(req, timeout=timeout) as x:
                    raw = x.read()
                with open(target, "wb") as f:
                    f.write(raw)
                files.append(target)
            except Exception:                                # noqa: BLE001
                continue
    return files, len(files), src


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    rows = []
    for s in SLOTS:
        req, pub = slot_sizes(a.platform, s)
        rows.append({"no": s["no"], "kind": s["kind"], "kindName": KIND_CN[s["kind"]],
                     "name": s["name"], "aim": s["aim"], "copy": s["copy"],
                     "requestSize": wh(req), "publishSize": wh(pub),
                     "points": POINTS_GPT})
    lines = []
    for code in PLATFORM_ORDER:
        p = PLATFORMS[code]
        lines.append({"platform": code, "name": p["name"], "ratio": p["ratio"],
                      "mainRequest": wh(p["main_req"]), "mainPublish": wh(p["main_pub"]),
                      "paramRequest": wh(p["param_req"]),
                      "paramPublish": wh(p["param_pub"]), "note": p["note"]})
    engines = [
        {"engine": "gpt", "name": "gpt-image-2.6 文生图", "path": GEN_PATH,
         "points": POINTS_GPT, "unit": "点/张", "mode": "同步"},
        {"engine": "gpt-edit", "name": "gpt-image-2.6 改图（带实拍图）", "path": EDIT_PATH,
         "points": POINTS_GPT, "unit": "点/张", "mode": "同步 / multipart"},
        {"engine": "nano", "name": "nano_banana 参考图出图", "path": NANO_PATH,
         "points": POINTS_NANO, "unit": "点/次", "mode": "异步"},
        {"engine": "dress", "name": "dressing_diffusion 换装", "path": DRESS_PATH,
         "points": POINTS_DRESS, "unit": "点/次", "mode": "异步"},
        {"engine": "upload", "name": "上传（拿白名单地址）", "path": UPLOAD_PATH,
         "points": 0, "unit": "点/次", "mode": "同步 / multipart"},
    ]
    out = {"ok": True, "slots": rows, "structure": STRUCTURE,
           "platforms": lines, "engines": engines,
           "perPagePoints": len(SLOTS) * POINTS_GPT,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("电商详情页 · 13 位结构（主图 5 + 卖点 3 + 场景 2 + 细节 2 + 参数 1）")
    print()
    print("  %s %s %s %s %s" % (pad("位号", 6), pad("类型", 6), pad("画面", 24),
                                pad("文案位", 40), "一句话"))
    print("  " + "-" * 118)
    for r in rows:
        print("  %s %s %s %s %s" % (
            pad("D%02d" % r["no"], 6), pad(r["kindName"], 6), pad(r["name"], 24),
            pad(cut(" / ".join(r["copy"]), 34), 36), r["aim"]))
    print()
    print("  五个平台：主图请求尺寸 / 上架尺寸（800x800 只有 640,000 像素，低于下限 655,360，")
    print("  所以 1:1 位统一请求 1024x1024，1024 方图本身就是合法的 1:1 主图）")
    print()
    print("  %s %s %s %s %s" % (pad("平台", 10), pad("比例", 6), pad("主图请求", 12),
                                pad("主图上架", 12), "详情页"))
    print("  " + "-" * 78)
    for r in lines:
        print("  %s %s %s %s %s" % (pad(r["platform"], 10), pad(r["ratio"], 6),
                                     pad(r["mainRequest"], 12), pad(r["mainPublish"], 12),
                                     "%s / 参数图 %s" % (r["paramRequest"], r["paramPublish"])))
    print()
    print("  %s %s %s %s %s" % (pad("--engine", 10), pad("能力", 26), pad("端点", 34),
                                pad("单价", 10), "形态"))
    print("  " + "-" * 96)
    for e in engines:
        print("  %s %s %s %s %s" % (
            pad(e["engine"], 10), pad(e["name"], 26),
            pad(e["path"].replace(API_PREFIX + "/", ""), 34),
            pad(("%d %s" % (e["points"], e["unit"])), 10), e["mode"]))
    print()
    print("  一整页 13 位全走 gpt：%d 点 = %s。1 元 = 100 点。"
          % (len(SLOTS) * POINTS_GPT, fmt_yuan(len(SLOTS) * POINTS_GPT)))
    return 0


def cost_ways(plat, dress, count=None):
    """四种走法的总账。"""
    n = len(SLOTS) if count is None else int(count)
    ways = []
    ways.append({"way": "全 gpt（默认）", "points": n * POINTS_GPT,
                 "basis": "%d 位 × %d 点/张" % (n, POINTS_GPT)})
    d = int(dress)
    if d:
        ways.append({"way": "换装 %d 位 + 其余 gpt" % d,
                     "points": d * POINTS_DRESS + max(0, n - d) * POINTS_GPT,
                     "basis": "%d × 200 + %d × 6" % (d, max(0, n - d))})
    ways.append({"way": "全 nano_banana", "points": n * POINTS_NANO,
                 "basis": "%d 位 × %d 点/次" % (n, POINTS_NANO)})
    main_n = min(5, n)
    rest = max(0, n - main_n)
    ways.append({"way": "主图 %d 位走多角度（各 3 视角）+ 其余 gpt" % main_n,
                 "points": main_n * POINTS_NANO_VIEW * 3 + rest * POINTS_GPT,
                 "basis": "%d × 25 × 3 + %d × 6（多角度按 25 点 × 视角数）"
                          % (main_n, rest)})
    for w in ways:
        w["yuan"] = round(w["points"] / float(POINTS_PER_YUAN), 2)
    return ways


def cmd_cost(a, key, host):
    plat = a.platform
    plan = build_plan(a.product or "商品", a.sku or "SKU01", plat,
                      [], 1) if a.product else None
    n = len(SLOTS) if plan is None else len(plan["slots"])
    ways = cost_ways(plat, getattr(a, "dress", 0) or 0, n)
    base = ways[0]["points"]
    out = {"ok": True, "platform": plat, "platformName": PLATFORMS[plat]["name"],
           "slots": n, "perSlotPoints": POINTS_GPT, "perPagePoints": base,
           "perPageYuan": round(base / float(POINTS_PER_YUAN), 2),
           "ways": ways,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing 与 images API 文档（2026-11-08 现查）",
               "gpt-image-2.6 按张计费，与尺寸、质量、输出格式都无关：13 位同为 78 点",
               "nano_banana：AI 商品图固定 72 点/次；商品多角度 25 点 × 选中视角数（带 views[] 时生效）",
               "dressing_diffusion 固定 200 点/次，服装类目只用它出「穿在身上」那一位",
               "上传 POST /api/v1/upload 价格表 cost 0，传实拍图拿白名单地址不花钱",
               "参数错误 / 请求失败 / 没出图不扣费；客户端中途断开仍按请求张数计费",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("预估成本 · %s · 一整页 %d 位（1 元 = 100 点）" % (PLATFORMS[plat]["name"], n))
    print()
    print("  %s %s %s %s" % (pad("位号", 6), pad("类型", 6), pad("画面", 24),
                              "请求 / 上架 / 点数"))
    print("  " + "-" * 78)
    for s in SLOTS:
        req, pub = slot_sizes(plat, s)
        print("  %s %s %s %s" % (pad("D%02d" % s["no"], 6), pad(KIND_CN[s["kind"]], 6),
                                 pad(s["name"], 24),
                                 "%s / %s / %d" % (wh(req), wh(pub), POINTS_GPT)))
    print("  " + "-" * 78)
    print("  %s %s %s" % (pad("合计", 6), pad("%d 位" % n, 30),
                          "%d 点 = %s" % (base, fmt_yuan(base))))
    print()
    print("  四种走法对照")
    for w in ways:
        print("    %s %s 点（%s 元）  %s"
              % (pad(w["way"], 38), pad(fmt_pts(w["points"]), 8, left=False),
                 "{:,.2f}".format(w["yuan"]), w["basis"]))
    print()
    for x in out["notes"]:
        print("  · %s" % x)
    return 0


def cmd_doctor(a, key, host):
    checks = []
    t0 = time.time()
    ms0 = int(time.time() * 1000)

    # 1) 余额（开账）
    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    bal0 = d.get("available_points")
    checks.append(("Key + 余额 /user/balance", st == 200 and bal0 is not None,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点"
                   % (st, fmt_pts(bal0 or 0), fmt_pts(d.get("frozen") or 0))))

    # 2) 流水（只读，limit=1）—— 记下条数与最新时间，收尾比对
    st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d = jloads(txt) or {}
    logs0 = d.get("total")
    latest0 = ((d.get("logs") or [{}])[0] or {}).get("at")
    checks.append(("流水 /user/balance/logs", st == 200 and isinstance(d.get("logs"), list),
                   "HTTP %s · 共 %s 条 · 最新一条 %s"
                   % (st, fmt_pts(logs0 or 0), latest0 or "-")))

    # 3) 价目表：upload 0 / nano 72 / dressing 200
    st, txt = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=40)
    pr = (jloads(txt) or {}).get("pricing") or {} if st == 200 else {}
    up = pr.get(UPLOAD_PATH) or {}
    na = pr.get(API_PREFIX + "/apps/nano_banana/*") or {}
    dr = pr.get(API_PREFIX + "/apps/dressing_diffusion/*") or {}
    price_ok = (int(up.get("cost", -1)) == 0 and int(na.get("cost", -1)) == POINTS_NANO
                and int(dr.get("cost", -1)) == POINTS_DRESS)
    checks.append(("价目 upload 0 / nano 72 / 换装 200", st == 200 and price_ok,
                   "HTTP %s · upload=%s nano=%s dress=%s · 共 %d 条规则"
                   % (st, up.get("cost"), na.get("cost"), dr.get("cost"), len(pr))))

    # 4) 模型目录：gpt-image-2.6 在架
    st, txt = http_json("GET", host + API_PREFIX + "/models", key, timeout=60)
    md = jloads(txt) or {}
    arr = md.get("data") if isinstance(md, dict) else None
    ids = [m.get("id") or m.get("model") for m in (arr or []) if isinstance(m, dict)]
    checks.append(("模型目录 gpt-image-2.6 在架", st == 200 and DEFAULT_MODEL in ids,
                   "HTTP %s · 目录 %d 个模型" % (st, len(ids))))

    # 5) 应用注册表：两个应用在架（只读列表，不读 /apps/<app>）
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    apps = (jloads(txt) or {}).get("data") or []
    codes = {x.get("code") for x in apps if isinstance(x, dict)}
    miss = [c for c in ("nano_banana", "dressing_diffusion") if c not in codes]
    checks.append(("应用注册表 nano / dressing 在架", st == 200 and not miss,
                   "HTTP %s · %d 个应用%s"
                   % (st, len(apps), (" · 缺 " + ",".join(miss)) if miss else "")))

    # 6) 文生图端点：带 model 的空 prompt → 422，停在校验层
    st, txt = http_json("POST", host + GEN_PATH, key,
                        {"model": DEFAULT_MODEL, "prompt": ""}, timeout=a.timeout)
    dd = jloads(txt) or {}
    e = dd.get("error") if isinstance(dd.get("error"), dict) else {}
    msg = (e.get("message") or err_text(st, txt))
    checks.append(("文生图端点（422 即正确）", st == 422 and "prompt" in msg.lower(),
                   "HTTP %s · %s" % (st, msg[:60])))

    # 7) 上传：空表单 → code 0「请使用 file 字段提交一个文件」，0 点
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=a.timeout)
    d = jloads(txt) or {}
    checks.append(("上传 POST /upload（价目 cost 0）",
                   st == 200 and d.get("code") == 0,
                   "HTTP %s · %s" % (st, (d.get("msg") or err_text(st, txt))[:40])))

    # 8) 查询路由：假 taskId → 结构化「任务不存在」
    st, txt = http_json("GET", host + TASKS_PATH + "probe-no-such-task", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("查询路由 GET /tasks/{id}（本包唯一轮询口）",
                   st == 200 and d.get("code") == 0,
                   "HTTP %s · %s" % (st, (d.get("msg") or "")[:40])))

    # 9) 收尾：余额与流水都没动，才算本轮真 0 点
    st2, txt2 = http_json("GET", host + "/user/balance", key, timeout=40)
    d2 = jloads(txt2) or {}
    bal1 = d2.get("available_points")
    st3, txt3 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d3 = jloads(txt3) or {}
    logs1 = d3.get("total")
    latest1 = ((d3.get("logs") or [{}])[0] or {}).get("at")
    same_bal = (st2 == 200 and bal0 is not None and bal1 is not None
                and abs(float(bal1) - float(bal0)) < 0.0001)
    same_logs = (logs1 == logs0 and latest1 == latest0)
    checks.append(("余额与流水前后一致 = 本轮 0 点", same_bal and same_logs,
                   "%s -> %s · 流水 %s -> %s 条 · 新增 %s"
                   % (fmt_pts(bal0 or 0), fmt_pts(bal1 or 0), fmt_pts(logs0 or 0),
                      fmt_pts(logs1 or 0), "0" if same_logs else "有")))

    # 10) 本次会话窗口内有没有新流水（最直接的花费证据）
    st4, txt4 = http_json("GET", host + "/user/balance/logs?limit=20", key, timeout=40)
    d4 = jloads(txt4) or {}
    fresh = [x for x in (d4.get("logs") or [])
             if int(x.get("at") or 0) >= ms0]
    checks.append(("本次会话窗口内新流水 0 条", st4 == 200 and not fresh,
                   "窗口起点 %d · 命中 %d 条（%s）"
                   % (ms0, len(fresh),
                      ",".join("%s:%s" % (x.get("type"), x.get("points"))
                               for x in fresh[:4]) or "无")))

    ok = all(c[1] for c in checks)
    out = {"ok": ok, "host": host, "estimatedPoints": 0, "yuan": 0.0,
           "slotCount": len(SLOTS), "model": DEFAULT_MODEL,
           "balance": {"before": bal0, "after": bal1},
           "logs": {"before": logs0, "after": logs1, "freshInWindow": len(fresh)},
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok else EXIT_GATE
    print()
    print("自检（只读 GET + 空 prompt / 空表单两类写探针，0 条任务、冻结 0 点）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 40), dd))
    print()
    print("  一次 GET /api/v1/apps/<app> 都没发，一次应用层 query 都没发 —— 这两个口子会真扣点。")
    print("  本轮花费 0 点：余额 %s -> %s，流水 %s -> %s 条，窗口内新增 0 条（%.1fs）。"
          % (fmt_pts(bal0 or 0), fmt_pts(bal1 or 0), fmt_pts(logs0 or 0),
             fmt_pts(logs1 or 0), time.time() - t0))
    return 0 if ok else EXIT_GATE


# ───────────────────────── 结构单（免费，只写本地）─────────────────────────
def render_page(plan):
    lines = ["# %s · 详情页结构单（%s）" % (plan["product"], plan["platformName"]), "",
             "整页 %d 位：主图 5 / 卖点 3 / 场景 2 / 细节 2 / 参数 1　·　"
             "%d 点（%.2f 元）" % (len(plan["slots"]), plan["perPage"], plan["yuan"]), "",
             "命名：`%s`" % plan["naming"], "",
             "## 交付清单", "",
             "| 类型 | 张数 | 请求尺寸 | 上架尺寸 |", "|---|---|---|---|"]
    for d in plan["deliver"]:
        lines.append("| %s | %d | %s | %s |"
                     % (d["label"], d["count"], d["requestSize"], d["publishSize"]))
    lines += ["", "## 13 个位", "",
              "| 位号 | 类型 | 画面 | 文案位 | 请求 / 上架 | 文件名 | 点数 |",
              "|---|---|---|---|---|---|---|"]
    for s in plan["slots"]:
        lines.append("| D%02d | %s | %s | %s | %s / %s | `%s` | %d |"
                     % (s["no"], s["kindName"], s["name"], " / ".join(s["copy"]),
                        s["requestSize"], s["publishSize"], s["file"], s["points"]))
    lines += ["", "## 每个位的出图提示词", ""]
    for s in plan["slots"]:
        lines += ["**D%02d %s**" % (s["no"], s["name"]), "", "```", s["prompt"], "```", ""]
    lines += ["## 合规改写对照（平台审核口径，写成可验证事实）", "",
              "| 原来会写 | 改成 |", "|---|---|"]
    for a_, b_ in REWRITE:
        lines.append("| %s | %s |" % (a_, b_))
    return "\n".join(lines) + "\n"


def cmd_plan(a, key, host):
    plat = a.platform
    product = (a.product or "").strip()
    if not product:
        raise Fail("usage", "必须给 --product（商品名，写进每个位的提示词）", EXIT_USAGE)
    sku = (a.sku or "").strip()
    if not re.match(r"^[A-Za-z0-9]{2,12}$", sku):
        raise Fail("usage", "--sku 要 2 到 12 位字母或数字（命名规范第一位），例如 SHIRT01",
                   EXIT_USAGE)
    sells = []
    for s in (a.sell or []):
        for piece in str(s).split(","):
            piece = piece.strip()
            if piece:
                sells.append(piece)
    plan = build_plan(product, sku, plat, sells, a.ver)

    outdir = a.outdir or "."
    if a.write:
        try:
            os.makedirs(outdir, exist_ok=True)
            with io.open(os.path.join(outdir, "plan.json"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(plan, ensure_ascii=False, indent=1))
            with io.open(os.path.join(outdir, "page.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(render_page(plan))
        except OSError as e:                                 # noqa: BLE001
            raise Fail("usage", "写不进 %s：%s" % (outdir, e), EXIT_USAGE)

    if a.json:
        print(json.dumps(plan, ensure_ascii=False))
        return 0

    print("详情页结构单 · %s · %s · %d 位" % (product, PLATFORMS[plat]["name"],
                                              len(plan["slots"])))
    print()
    print("  %s %s %s %s" % (pad("位号", 6), pad("类型", 6), pad("画面", 24),
                              "请求 / 上架"))
    print("  " + "-" * 76)
    for s in plan["slots"]:
        print("  %s %s %s %s" % (pad("D%02d" % s["no"], 6), pad(s["kindName"], 6),
                                 pad(s["name"], 22),
                                 "%s / %s" % (s["requestSize"], s["publishSize"])))
    print()
    print("  一整页 %d 点（%s）。命名：%s" % (plan["perPage"], fmt_yuan(plan["perPage"]),
                                             plan["naming"]))
    if a.write:
        print()
        print("  已写：%s\\plan.json（机器读，gen 与 check 都用它）" % outdir)
        print("  已写：%s\\page.md（人读，13 位 + 文案位 + 合规改写表）" % outdir)
        print("  下一步：gen --plan %s\\plan.json --ref 实拍图.jpg --outdir %s --yes"
              % (outdir, outdir))
    else:
        print()
        print("  加 --write 才会落盘（默认只打印，不写文件）。")
    return 0


# ───────────────────────── 上传（免费）─────────────────────────
def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（商品实拍图 / 参考图）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + UPLOAD_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": path, "size": size,
               "estimatedPoints": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传）")
        print("  端点：POST %s（multipart，字段名 file，价目 cost 0）" % url)
        print("  文件：%s（%d 字节）" % (path, size))
        return 0
    say("正在上传 %s（%d 字节）…" % (os.path.basename(path), size))
    t0 = time.time()
    st, txt = http_multipart(url, key, {}, [("file", path)], timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") not in (1, 0) or not got:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "mode": "upload", "file": path, "http": st, "error": msg})
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    ok_url, kind = url_allowed(got)
    out = {"ok": True, "url": got, "size": data.get("size"), "mime": data.get("mime_type"),
           "type": data.get("type"), "hostKind": kind, "urlAllowed": ok_url,
           "elapsed": round(dt, 1), "estimatedPoints": 0}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "upload",
                "file": path, "size": size, "url": got, "elapsed": round(dt, 1)})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（%.1fs，0 点）" % dt)
    print("  地址：%s" % got)
    print("  归属：%s（白名单内，可给 nano / 换装的素材地址用）" % kind)
    print()
    print("  下一步：gen --plan out/plan.json --ref %s --outdir out --yes"
          % os.path.basename(path))
    return 0


# ───────────────────────── 出图（付费）─────────────────────────
def slot_points(engine):
    if engine == "nano":
        return POINTS_NANO
    if engine == "dress":
        return POINTS_DRESS
    return POINTS_GPT


def gen_body(slot, a, plan):
    engine = a.engine
    if engine == "nano":
        body = {"prompt": slot["prompt"], "model": a.model or NANO_MODEL,
                "resolution": a.resolution, "aspect_ratio": a.aspect_ratio}
        if a.images:
            body["action"] = "edit"
            body["image_urls"] = list(a.images)
        return body
    if engine == "dress":
        return {"model_url": a.model_url,
                "garment": {"data": [{"category": a.garment_category,
                                      "url": a.garment_url}]}}
    body = {"model": DEFAULT_MODEL, "prompt": slot["prompt"], "n": 1,
            "size": slot["requestSize"], "output_format": a.output_format}
    return body


def preflight_gen(a, slots, plan):
    if a.engine == "gpt" and a.ref:
        for p in a.ref:
            if not os.path.isfile(p):
                raise Fail("usage", "--ref 文件不存在：%s" % p, EXIT_USAGE)
    if a.engine == "nano" and a.ref:
        raise Fail("usage",
                   "nano 走的是地址：先 upload --file 实拍图，再把返回地址用 --images 传进来",
                   EXIT_USAGE)
    if a.engine == "dress":
        if not a.model_url or not a.garment_url:
            raise Fail("usage",
                       "dress 要 --model-url（模特图）与 --garment-url（服装图），"
                       "两张都先用 upload 传，拿 oss.gpu.likeadmin.cn 的地址", EXIT_USAGE)
        for flag, val in (("--model-url", a.model_url), ("--garment-url", a.garment_url)):
            if not re.match(r"^https?://", val or "", re.I):
                raise Fail("usage", "%s 要以 http:// 或 https:// 开头" % flag, EXIT_USAGE)
            ok, why = url_allowed(val)
            if not ok:
                say("  提示：%s 的域名是 %s，不在本站白名单里，上游可能拒收" % (flag, why))
    if a.engine == "gpt":
        for s in slots:
            size = parse_wh(s["requestSize"])
            prob = size_problem(size) if size else "尺寸读不出来"
            if prob:
                raise Fail("usage", "第 %d 位尺寸不合规：%s" % (s["no"], prob), EXIT_USAGE)


def run_slot(a, key, host, slot, plan):
    """跑一个位。返回结果 dict；失败记台账并抛 Fail。"""
    engine = a.engine
    t0 = time.time()
    outdir = a.outdir or "."
    if a.ref and engine == "gpt":
        fields = {"model": DEFAULT_MODEL, "prompt": slot["prompt"], "n": "1",
                  "size": slot["requestSize"], "output_format": a.output_format}
        st, txt = http_multipart(host + EDIT_PATH, key, fields,
                                 [("image", p) for p in a.ref], timeout=a.timeout)
        endpoint = EDIT_PATH
    elif engine == "gpt":
        st, txt = http_json("POST", host + GEN_PATH, key,
                            gen_body(slot, a, plan), timeout=a.timeout)
        endpoint = GEN_PATH
    else:
        endpoint = NANO_PATH if engine == "nano" else DRESS_PATH
        st, txt = http_json("POST", host + endpoint, key,
                            gen_body(slot, a, plan), timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "gen", "no": slot["no"],
           "engine": engine, "endpoint": endpoint, "elapsed": round(dt, 1)}

    if engine in ("nano", "dress"):
        data = d.get("data") if isinstance(d.get("data"), dict) else {}
        flat = data or d
        tid = flat.get("task_id") or flat.get("taskId") or flat.get("id")
        ok = st in (200, 201) and bool(tid)
        if not ok:
            msg = err_text(st, txt)
            rec.update({"ok": False, "error": msg})
            ledger_add(rec)
            raise Fail("call", "D%02d 提交失败（HTTP %s）：%s" % (slot["no"], st, msg),
                       EXIT_CALL)
        rec.update({"ok": True, "taskId": tid})
        ledger_add(rec)
        return {"no": slot["no"], "name": slot["name"], "engine": engine,
                "taskId": tid, "status": flat.get("status"),
                "endpoint": endpoint, "elapsed": round(dt, 1),
                "estimatedPoints": slot_points(engine)}

    if st not in (200, 201):
        msg = err_text(st, txt)
        rec.update({"ok": False, "error": msg})
        ledger_add(rec)
        raise Fail("call", "D%02d 出图失败（HTTP %s）：%s" % (slot["no"], st, msg),
                   EXIT_CALL)
    if not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    files, n, src = save_images(d, outdir, slot["file"], timeout=a.timeout)
    if n == 0:
        rec.update({"ok": False, "error": "响应里没有图"})
        ledger_add(rec)
        raise Fail("call", "D%02d 响应里没有图：%s" % (slot["no"], txt[:200]), EXIT_CALL)
    billed = n * POINTS_GPT
    rec.update({"ok": True, "files": files, "returned": n, "billedPoints": billed,
                "source": src})
    ledger_add(rec)
    return {"no": slot["no"], "name": slot["name"], "engine": engine,
            "files": files, "returned": n, "source": src,
            "billedPoints": billed, "requestSize": slot["requestSize"],
            "publishSize": slot["publishSize"], "endpoint": endpoint,
            "elapsed": round(dt, 1)}


def cmd_gen(a, key, host):
    plan = load_plan(a.plan)
    if plan is None:
        product = (a.product or "").strip()
        if not product:
            raise Fail("usage",
                       "要么 --plan（先跑 plan --write），要么 --product + --sku + --platform",
                       EXIT_USAGE)
        sku = (a.sku or "SKU01").strip()
        plan = build_plan(product, sku, a.platform, list(a.sell or []), a.ver)
    slots = select_slots(plan, a)
    per = slot_points(a.engine)
    total = per * len(slots)
    if a.engine == "dress":
        what = "换装 %d 位（%d × 200 点）" % (len(slots), len(slots))
    else:
        what = "一整页 %d 位 × %d 点 = %d 点" % (len(slots), per, total)
    gate(a, total, what)
    preflight_gen(a, slots, plan)

    reqs = []
    for s in slots:
        body = gen_body(s, a, plan)
        endpoint = (EDIT_PATH if (a.ref and a.engine == "gpt")
                    else GEN_PATH if a.engine == "gpt"
                    else NANO_PATH if a.engine == "nano" else DRESS_PATH)
        reqs.append({"no": s["no"], "name": s["name"], "endpoint": endpoint,
                     "size": s["requestSize"], "file": s["file"],
                     "requestBody": body if not (a.ref and a.engine == "gpt")
                     else {"multipart": {"model": DEFAULT_MODEL, "prompt": s["prompt"],
                                         "n": "1", "size": s["requestSize"],
                                         "output_format": a.output_format,
                                         "image": [os.path.basename(p) for p in a.ref]}},
                     "points": per})

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "engine": a.engine, "slots": reqs,
               "estimatedPoints": total, "yuan": round(total / float(POINTS_PER_YUAN), 2)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  引擎：%s　位数：%d" % (a.engine, len(slots)))
        for r in reqs:
            print("  D%02d -> %s" % (r["no"], r["endpoint"]))
            print("    %s" % json.dumps(r["requestBody"], ensure_ascii=False)[:260])
        print("  预估：%s 点（%s）" % (fmt_pts(total), fmt_yuan(total)))
        return 0

    done, failed = [], None
    for s in slots:
        say("正在出 D%02d %s（%s）…" % (s["no"], s["name"], a.engine))
        try:
            done.append(run_slot(a, key, host, s, plan))
        except Fail as e:
            failed = e
            break

    billed = sum(r.get("billedPoints") or 0 for r in done)
    out = {"ok": failed is None, "engine": a.engine, "slots": done,
           "returned": sum(r.get("returned") or 0 for r in done),
           "billedPoints": billed,
           "estimatedPoints": total, "yuan": round(total / float(POINTS_PER_YUAN), 2),
           "outdir": a.outdir or "."}
    if a.json:
        if failed is not None:
            out["exit"] = failed.exit_code
            out["error"] = {"kind": failed.kind, "message": failed.message}
        print(json.dumps(out, ensure_ascii=False))
        return 0 if failed is None else failed.exit_code
    print()
    print("已出 %d 位" % len(done))
    for r in done:
        if r.get("taskId"):
            print("  D%02d %s  任务 %s（异步，跑 status 查）"
                  % (r["no"], r["name"], r["taskId"]))
        else:
            print("  D%02d %s  %s  %s  计费 %d 点"
                  % (r["no"], r["name"], r["requestSize"],
                     ", ".join(os.path.basename(f) for f in r["files"]),
                     r.get("billedPoints") or 0))
    print()
    print("  实扣 %d 点（按响应里实际返回的张数计），清单 %d 点（%s）"
          % (billed, total, fmt_yuan(total)))
    print("  下一步：check --dir %s --plan %s" % (a.outdir or ".", a.plan or "out/plan.json"))
    if failed is not None:
        say("失败：%s" % failed.message)
        return failed.exit_code
    return 0


# ───────────────────────── 交付验收（免费，只读本地）─────────────────────────
def copy_lines(copy):
    out = []
    if isinstance(copy, str):
        out.append(copy)
    elif isinstance(copy, dict):
        for k, v in copy.items():
            if isinstance(v, (str, int, float)):
                out.append("%s: %s" % (k, v))
            elif isinstance(v, dict):
                for k2, v2 in v.items():
                    if isinstance(v2, (str, int, float)):
                        out.append("%s.%s: %s" % (k, k2, v2))
            elif isinstance(v, list):
                for v2 in v:
                    if isinstance(v2, str):
                        out.append(v2)
    elif isinstance(copy, list):
        for v in copy:
            out += copy_lines(v)
    return out


def scan_copy(texts):
    hits = []
    for t in texts:
        for w in ABSOLUTE_WORDS:
            if w in t:
                hits.append({"word": w, "text": t[:60]})
    return hits


def cmd_check(a, key, host):
    root = a.dir or "."
    if not os.path.isdir(root):
        raise Fail("usage", "目录不存在：%s" % root, EXIT_USAGE)
    plan = load_plan(a.plan)

    files = []
    for base, _dirs, names in os.walk(root):
        for nm in names:
            files.append((os.path.join(base, nm), nm))
    files.sort()

    have = {}
    bad_names = []
    for full, nm in files:
        m = NAME_RE.match(nm)
        if not m:
            if nm.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                bad_names.append(nm)
            continue
        have[int(m.group("no"))] = (full, nm, m)

    if plan and plan.get("slots"):
        want = plan["slots"]
    else:
        want = [{"no": s["no"], "kind": s["kind"], "kindName": KIND_CN[s["kind"]],
                 "name": s["name"], "requestSize": wh(slot_sizes(a.platform, s)[0]),
                 "publishSize": wh(slot_sizes(a.platform, s)[1]),
                 "file": None} for s in SLOTS]

    rows, problems = [], []
    for w in want:
        item = {"no": w["no"], "name": w.get("name"), "kind": w.get("kindName"),
                "file": None, "ok": True, "detail": ""}
        hit = have.get(int(w["no"]))
        if not hit:
            item["ok"] = False
            item["detail"] = "缺图"
            problems.append("D%02d %s：缺图" % (w["no"], w.get("name")))
            rows.append(item)
            continue
        full, nm, m = hit
        item["file"] = nm
        det = []
        expect = w["publishSize"] if a.publish else w["requestSize"]
        if m.group("kind") != w.get("kind"):
            item["ok"] = False
            det.append("类型写的是 %s" % m.group("kind"))
        if m.group("spec") != w["requestSize"]:
            item["ok"] = False
            det.append("文件名规格 %s，结构单请求 %s" % (m.group("spec"), w["requestSize"]))
        pixels = image_size(full)
        item["pixels"] = list(pixels) if pixels else None
        if not pixels:
            item["ok"] = False
            det.append("读不出像素")
        else:
            exp = parse_wh(expect)
            if exp and pixels != exp:
                item["ok"] = False
                det.append("实际 %s，结构单要 %s" % (wh(pixels), expect))
        mb = os.path.getsize(full) / 1048576.0
        item["sizeMb"] = round(mb, 2)
        if mb > 10:
            item["ok"] = False
            det.append("体积 %.1f MB 偏大" % mb)
        item["detail"] = "；".join(det) if det else "ok"
        if not item["ok"]:
            problems.append("D%02d %s：%s" % (w["no"], item["detail"], nm))
        rows.append(item)

    # 文案合规：结构单里的文案位 + 可选 --copy 传入的实际文案
    texts = []
    for w in want:
        texts += [t for t in (w.get("copy") or [])]
    if a.copy:
        if not os.path.isfile(a.copy):
            raise Fail("usage", "--copy 文件不存在：%s" % a.copy, EXIT_USAGE)
        try:
            texts += copy_lines(json.load(io.open(a.copy, encoding="utf-8-sig")))
        except Exception as e:                               # noqa: BLE001
            raise Fail("usage", "--copy 要 JSON：%s" % e, EXIT_USAGE)
    hits = scan_copy(texts)

    ok = not problems and not hits
    out = {"ok": ok, "dir": root, "slots": len(want), "found": len(have),
           "mode": "publish" if a.publish else "request",
           "rows": rows, "badNames": bad_names[:20], "problems": problems,
           "copyHits": hits, "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok else EXIT_GATE

    print("交付验收 · %s · 结构单 %d 位 · 目录里认出 %d 位" % (root, len(want), len(have)))
    print()
    print("  %s %s %s %s %s" % (pad("位号", 6), pad("类型", 6), pad("文件", 40),
                                pad("像素", 12), "说明"))
    print("  " + "-" * 88)
    for r in rows:
        px = wh(r["pixels"]) if r["pixels"] else "-"
        print("  %s %s %s %s %s" % (pad("D%02d" % r["no"], 6), pad(r["kind"], 6),
                                    pad(cut(r["file"] or "-", 38), 40), pad(px, 12),
                                    r["detail"]))
    print()
    if bad_names:
        print("  命名不合规范（%d 个）：%s" % (len(bad_names), ", ".join(bad_names[:6])))
        print("  规范：<SKU>_D<位号两位>_<类型>_<宽x高>_v<版本两位>.<png|jpg|webp>")
        print()
    if hits:
        print("  文案位命中 %d 处，按合规改写表换成可验证事实：" % len(hits))
        for h_ in hits[:10]:
            print("    %s  <- %s" % (h_["word"], h_["text"]))
        print()
    if problems or hits:
        if problems:
            print("  × %d 处要补：" % len(problems))
            for p in problems[:15]:
                print("    %s" % p)
            print()
        print("  本轮花费 0 点（只读本地文件）。")
        return EXIT_GATE
    print("  √ %d 位齐、命名合规、像素对得上（%s口径）。"
          % (len(rows), "上架尺寸" if a.publish else "出图尺寸"))
    print("  本轮花费 0 点（只读本地文件）。")
    return 0


# ───────────────────────── 查任务 / 台账 ─────────────────────────
def cmd_status(a, key, host):
    tid = a.task_id
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    # 只走免费的通用查询；应用层 query 按次计费（nano_banana/query 72 点/次）。
    st, txt = http_json("GET", host + TASKS_PATH + tid, key, timeout=60)
    d = jloads(txt) or {}
    if st != 200:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    flat = data or d
    usage = flat.get("usage") if isinstance(flat.get("usage"), dict) else {}
    out = {"ok": True, "taskId": tid, "status": flat.get("status"),
           "message": flat.get("message"), "url": flat.get("url") or flat.get("imageUrl"),
           "cost": flat.get("cost") or usage.get("points_cost"),
           "result": flat.get("result"), "error": flat.get("error")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  状态：%s" % flat.get("status"))
    if out["cost"] is not None:
        print("  实扣：%s 点" % out["cost"])
    if flat.get("message"):
        print("  说明：%s" % str(flat.get("message"))[:300])
    if out["url"]:
        print("  结果：%s（链接有时效，及时转存）" % out["url"])
    if flat.get("result") is not None:
        print("  明细：%s" % json.dumps(flat.get("result"), ensure_ascii=False)[:600])
    print()
    print("  本轮花费 0 点（只读 GET /tasks/{id}）。")
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
    print("本地台账（显示 %d / 共 %d 条）· %s" % (len(out["entries"]), out["count"], LEDGER))
    for e in out["entries"]:
        what = e.get("taskId") or ",".join(os.path.basename(f) for f in
                                           (e.get("files") or [])) or \
            os.path.basename(e.get("url") or "") or \
            (e.get("error") or "")[:36] or "-"
        pts = e.get("billedPoints")
        print("  %s  %-4s %-7s %-4s %-44s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            ("D%02d" % e.get("no")) if e.get("no") else "-", what[:44],
            ("%s 点" % pts) if pts is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 电商详情页：一张商品实拍出整页 13 位详情图（走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/images/generations（6 点/张）· "
               "POST %s/api/v1/images/edits（改图 6 点/张）· "
               "POST %s/api/v1/apps/nano_banana/submit（72 点/次）· "
               "POST %s/api/v1/apps/dressing_diffusion/submit（200 点/次）· "
               "POST %s/api/v1/upload（0 点）· GET %s/api/v1/tasks/<id>"
               % ((DEFAULT_HOST,) * 6),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 5 元；1 元 = 100 点）"
                         % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="13 位结构 + 五平台尺寸表 + 四条线的价（免费）",
                       allow_abbrev=False)
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                   help="按哪个平台算尺寸（默认 taobao）")
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：一页 13 位 + 四种走法（免费）",
                       allow_abbrev=False)
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                   help="平台（默认 taobao）")
    p.add_argument("--dress", type=int, default=0,
                   help="有几位要走换装（200 点/位，默认 0）")
    p.add_argument("--product", help="商品名（只影响尺寸展示，不影响算钱）")
    p.add_argument("--sku", help="商品编码（同上）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 端点 / 价目 / 上传 / 流水（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("plan", help="出整页结构单：13 位的画面 / 文案位 / 尺寸 / 文件名（免费）",
                       allow_abbrev=False)
    p.add_argument("--product", required=True, help="商品名，写进每个位的提示词")
    p.add_argument("--sku", default="SKU01", help="商品编码，命名规范第一位（默认 SKU01）")
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                   help="平台（默认 taobao）")
    p.add_argument("--sell", action="append", help="卖点关键词，可多次给，逗号分隔")
    p.add_argument("--ver", type=int, default=1, help="版本号（默认 1）")
    p.add_argument("--outdir", default=".", help="写到哪里（默认当前目录）")
    p.add_argument("--write", action="store_true", help="落盘 plan.json + page.md")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("upload", help="上传实拍图，拿白名单地址（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地图片路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    def add_gen(p):
        p.add_argument("--plan", help="结构单路径（plan --write 产出的 plan.json）")
        p.add_argument("--product", help="没有结构单时直接给商品名")
        p.add_argument("--sku", default="SKU01", help="商品编码（命名用，默认 SKU01）")
        p.add_argument("--sell", action="append", help="卖点关键词，可多次给")
        p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                       help="平台（决定尺寸，默认 taobao）")
        p.add_argument("--engine", choices=["gpt", "nano", "dress"], default="gpt",
                       help="gpt 6 点/张 · nano 72 点/次 · dress 200 点/次")
        p.add_argument("--slot", help="只跑这几个位：1,2,3 或 D01,D02（默认全 13 位）")
        p.add_argument("--kind", help="按类型选位：main,point,scene,detail,param")
        p.add_argument("--ref", action="append",
                       help="商品实拍图（gpt 走改图线；nano 转 image_urls），可多张")
        p.add_argument("--model", help="nano 模型代号（默认 nano-banana）")
        p.add_argument("--resolution", default=DEFAULT_RESOLUTION,
                       choices=["1K", "2K", "4K"], help="nano 分辨率（默认 1K）")
        p.add_argument("--aspect-ratio", default="auto",
                       help="nano 画幅（默认 auto）")
        p.add_argument("--images", action="append",
                       help="nano 参考图地址（http(s)，可多张，自动转 edit）")
        p.add_argument("--model-url", help="dress：模特图地址")
        p.add_argument("--garment-url", help="dress：服装图地址")
        p.add_argument("--garment-category", default="upper",
                       choices=["upper", "bottom", "full"],
                       help="dress：服装部位（默认 upper）")
        p.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"],
                       help="输出格式（默认 png）")
        p.add_argument("--ver", type=int, default=1, help="版本号（默认 1）")
        p.add_argument("--outdir", default=".", help="出图落到哪（默认当前目录）")
        p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                       help="单次请求超时秒数（默认 240）")
        p.add_argument("--yes", action="store_true", help="确认真实提交并冻结点数")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("gen", help="按位出图（6 点/张，要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    add_gen(p)
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("check", help="交付验收：齐不齐 / 命名 / 像素 / 文案合规（免费）",
                       allow_abbrev=False)
    p.add_argument("--dir", help="出图目录（默认当前目录）")
    p.add_argument("--plan", help="结构单路径（对得上 plan 才算过）")
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                   help="没有结构单时按这个平台的尺寸验（默认 taobao）")
    p.add_argument("--publish", action="store_true",
                   help="按上架尺寸验（默认按出图尺寸验）")
    p.add_argument("--copy", help="实际文案 JSON，逐条扫绝对化用语")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("status", help="查异步任务（免费，只走 /tasks/{id}）", allow_abbrev=False)
    p.add_argument("--task-id", help="gen --engine nano/dress 返回的 task_id")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="显示最近多少条（默认 20）")
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以（子命令上用 SUPPRESS，避免覆盖父级默认值）
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_check", "cmd_log")


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
        if not key and getattr(a.fn, "__name__", "") not in FREE:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n"
                       "注册领 Key：https://api.a7w.cn/", EXIT_USAGE)
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
    except Exception:                                        # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
