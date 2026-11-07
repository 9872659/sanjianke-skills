#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 电商图包（sanjianke-ecom-picset）

一张商品图，出一整套能上架的主图 + 场景图 + 细节图：
**主图位规划 → 尺寸适配 → 按位出图 → 批量命名 → 合规清单**，五步一条流水线。

## 两条线，四条路径（价格全部有据可查，见下）

  gpt-image-2.6 文生图   POST /api/v1/images/generations   **6 点/张**（同步）
  gpt-image-2.6 改图     POST /api/v1/images/edits         **6 点/次**（multipart，同步）
  nano_banana 出图       POST /api/v1/apps/nano_banana/submit   **72 点/次**（异步）
  换装                   POST /api/v1/apps/dressing_diffusion/submit  **200 点/次**（异步）

## 价格是怎么核出来的（2026-11-07 本轮实测，零花费）

  ① `GET /api/v1/pricing`（免费）里**没有** `/api/v1/images/*` 的条目 —— 图片线按
     **模型**计次，不按路径 flat。真正的价要去看流水：
       `GET /user/balance/logs` 里 `sync:/api/v1/images/generations` 共 148 笔，
       其中 **82 笔是 -6 点**（1024×1024 一张一张出），另有 -4 / -7.8 / -10.54 /
       -10.6 / -12 / -13.78 / -36 / -60 / -199.9998 等其它模型/尺寸的笔；
       `sync:/api/v1/images/edits` 2 笔，**每笔 -6 点**。
     → 所以本包按 **6 点/张、6 点/次改图** 报价，并且**每张图单独一次请求（n=1）**，
        点数就等于张数，不靠 `n` 打包赌一张的价。
  ② `GET /api/v1/pricing` 里两条应用层规则是明确的 flat：
       /api/v1/apps/nano_banana/*            cost 72   固定 72 点/次
       /api/v1/apps/dressing_diffusion/*     cost 200  固定 200 点/次
  ③ **应用层的 query 不是免费读**：流水里 `sync:/api/v1/apps/nano_banana/query`
     **216 笔、每笔 -72 点、合计 -15,552 点**。所以本包所有异步轮询只走
     `GET /api/v1/tasks/<task_id>`（免费），**从不**打 `apps/<app>/query` 或 `result`。
  ④ **`GET /api/v1/apps/<app>` 一次就是该应用的单价**（换装 200、出图 72），
     所以 `doctor` 刻意不读它，只用免费的 `/api/v1/models`、`/api/v1/apps`、
     `/api/v1/pricing`、`/api/v1/tasks/<id>`，加一次「空 prompt 换 422」的探针。

## 尺寸适配：800×800 这种主图尺寸，gpt-image 直接拒

  gpt-image 的自定义尺寸要同时满足：宽高都是 16 的倍数、长边/短边 ≤ 3:1、
  单边 ≤ 3840、**总像素 655,360 – 8,294,400**。
  淘宝/1688/拼多多要的 800×800 = 640,000 像素，**低于下限**，属于「看着对、其实不合法」。
  本包按平台给的是「最近一个合法且比例精确」的尺寸：

    平台 800×800（1:1）      → 请求 1024×1024（1,048,576 像素，正方）
    平台 750×1000（3:4）     → 请求 768×1024（750 不是 16 的倍数；768×1024 恰好 3:4）
    平台 1200×1600（3:4）    → 请求 1200×1600（本身就合法，原样用）
    详情页 750 宽            → 请求 768×1024，出完统一缩到 750 宽再拼

## 子命令

  catalog  四条路径的价 + 一套素材四种走法 + 尺寸适配表（免费、离线）
  cost     先算钱：本次要多少点，同一套走 nano / 带换装各要多少（免费）
  doctor   自检 Key / 端点 / 价目表（免费，且自己证明「本轮扣 0 点」）
  plan     主图位规划：生成 plan.json（免费、离线）
  gen      按位出图（6 点/张，要 --yes，受 --budget 管）
  names    批量命名：把目录里的图规整成「平台_位_像素」的文件名（免费、本地）
  check    合规清单：像素、比例、命名、体积、计划齐不齐（免费、本地）
  status   查异步任务（免费，只走 /api/v1/tasks/<id>）
  log      本地台账（免费）

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --platform taobao --main 5 --scene 3 --detail 2
  python3 scripts/run.py doctor
  python3 scripts/run.py plan --product "白色亚麻衬衫" --platform taobao --outdir ./out
  python3 scripts/run.py gen  --plan ./out/plan.json --outdir ./out --yes
  python3 scripts/run.py gen  --plan ./out/plan.json --ref 商品实拍.png --outdir ./out --yes
  python3 scripts/run.py names --dir ./out --platform taobao --apply
  python3 scripts/run.py check --dir ./out --platform taobao

## 两道闸门

  `--budget` 单位是「点」（1 元 = 100 点）；`--yes` 是第二道。
  缺 `--yes` → exit 4 并告诉你这一轮要花多少点；预计 > `--budget` → exit 5，
  **一个请求都不发**。`--dry-run` 只打印请求，不提交、不扣费。

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**
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

# ── GBK 编码兜底（照 video-lab 写法，2026-11-07 实测）────────────────────────
# Windows 上 stdout 被管道/重定向时用本地编码（cp936），遇到 `√`/`×` 这类
# cp936 编不出的字符会 UnicodeEncodeError 崩掉；先加 errors='replace' 兜底。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"

MODEL = "gpt-image-2.6"
NANO_MODEL = "nano-banana"
NANO_RES = ["1K", "2K", "4K"]

POINTS_IMAGE = 6            # 流水：sync:/api/v1/images/generations 82 笔都是 -6
POINTS_EDIT = 6             # 流水：sync:/api/v1/images/edits 2 笔，各 -6
POINTS_NANO = 72            # 价格表：/api/v1/apps/nano_banana/*  flat 72
POINTS_DRESS = 200          # 价格表：/api/v1/apps/dressing_diffusion/*  flat 200
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 500

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "ecom-picset-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-ecom-picset/%s" % VERSION

# 平台预设。`size` 是喂给 gpt-image 的合法尺寸，`why` 解释为什么要换这个尺寸。
PLATFORMS = {
    "taobao": dict(name="淘宝 / 天猫", px="800x800", ratio="1:1", size="1024x1024",
                   white=True,
                   why="800x800 = 640,000 像素，低于 gpt-image 下限 655,360；1024×1024 是最近的合法正方"),
    "taobao34": dict(name="淘宝 3:4 竖版主图", px="750x1000", ratio="3:4", size="768x1024",
                     white=False,
                     why="750 不是 16 的倍数；768×1024 既合法又恰好 3:4"),
    "1688": dict(name="1688", px="800x800", ratio="1:1", size="1024x1024", white=True,
                 why="同淘宝：800×800 像素不够，用 1024×1024"),
    "pinduoduo": dict(name="拼多多", px="800x800", ratio="1:1", size="1024x1024",
                      white=True,
                      why="同淘宝：800×800 像素不够，用 1024×1024"),
    "douyin": dict(name="抖音商城", px="1200x1600", ratio="3:4", size="1200x1600",
                   white=False,
                   why="1200 与 1600 都是 16 的倍数、像素 1,920,000，原样合法"),
    "detail": dict(name="详情页单屏", px="750x不限", ratio="3:4", size="768x1024",
                   white=False,
                   why="按屏出图再本地拼；出完统一缩到 750 宽"),
}
PLATFORM_ORDER = ["taobao", "taobao34", "1688", "pinduoduo", "douyin", "detail"]

# 主图位模板：(slot_id, kind, 位名, 画面要求)
SLOTS = [
    ("main01", "main", "白底正面",
     "纯白背景，正面平视，商品居中占画面 75%，四周留白 8%，柔和均匀光，极浅投影，电商白底主图"),
    ("main02", "main", "材质卖点",
     "斜侧 45 度，突出材质纹理与第一卖点，浅景深，浅灰纯色背景，主体占画面 70%"),
    ("main03", "main", "使用场景",
     "真实生活使用场景，自然光，商品占画面 60%，背景干净有生活感"),
    ("main04", "main", "细节工艺",
     "微距特写，缝线、五金、边缘做工清晰，纯色浅背景，柔光棚拍"),
    ("main05", "main", "规格搭配",
     "同款商品与常用配件平铺组合，俯拍构图规整，纯色浅背景，主体不压边"),
    ("scene01", "scene", "室内场景",
     "明亮室内自然光，桌面与织物场景，氛围温暖，商品自然摆放"),
    ("scene02", "scene", "户外场景",
     "户外自然光，绿植与街景虚化，阳光通透，商品自然摆放"),
    ("scene03", "scene", "节日氛围",
     "节日氛围场景，柔和暖光与轻微装饰，商品为主体"),
    ("detail01", "detail", "材质微距",
     "超微距，纤维与纹理颗粒清晰可见，浅景深，纯色背景"),
    ("detail02", "detail", "做工细节",
     "超微距，缝线与包边细节，侧光强调立体感，纯色背景"),
]
SLOT_IDS = [s[0] for s in SLOTS]

# 比例容差：和家族里 ecom-image 的口径一致（3%），像素级舍入误差另算 0.25%。
RATIO_TOL = 0.03
RATIO_FLOOR = 0.0025

NO_TEXT = "画面里不出现文字、水印、logo、二维码"


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


def _w(s):
    """显示宽度：中日韩字符算 2 列，表格才对齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def fmt_pts(n):
    try:
        return "{:,}".format(int(round(float(n))))
    except Exception:                                            # noqa: BLE001
        return str(n)


def yuan(n):
    return round(float(n) / POINTS_PER_YUAN, 2)


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


def http_json(method, url, key, body=None, timeout=240, retries=3):
    """发一次请求。网关会重置空闲连接（WinError 10054），网络类错误退避重试。
    4xx 是业务错误，直接交给调用方判断，不重试。"""
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
                time.sleep(1.5 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise Fail("call", "连不上 %s：%s（已重试 %d 次）"
                       % (url, getattr(e, "reason", e), retries - 1), EXIT_CALL)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


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
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:300]
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or "", e.get("param") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        if isinstance(e, str) and e:
            return e[:300]
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条路径下没有该端点" % st
    return txt.replace("\n", " ")[:240]


def unwrap(st, txt, what):
    """网关信封：`code == 1` 才是成功（0 是失败，别写反）。返回 data。
    OpenAI 兼容接口（images/*）没有 code，直接返回整个对象，由调用方取 data[]。"""
    if st not in (200, 201):
        raise Fail("call", "%s失败（HTTP %s）：%s" % (what, st, err_text(st, txt)), EXIT_CALL)
    d = jloads(txt)
    if not isinstance(d, dict):
        raise Fail("call", "%s返回不是 JSON：%s" % (what, txt[:200]), EXIT_CALL)
    if "code" not in d:
        return d
    if d.get("code") not in (1, "1"):
        raise Fail("call", "%s失败：%s" % (what, err_text(st, txt)), EXIT_CALL)
    return d.get("data") if "data" in d else d


# ───────────────────────── 图片头解析（零依赖） ─────────────────────────
def dims_from_stream(f):
    """从文件头读真实像素，返回 (w, h, fmt) 或 None。只用标准库。"""
    try:
        head = f.read(32)
        if len(head) < 24:
            return None
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return (int.from_bytes(head[16:20], "big"),
                    int.from_bytes(head[20:24], "big"), "png")
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                b = f.read(1)
                if not b:
                    return None
                if b != b"\xff":
                    continue
                m = f.read(1)
                while m == b"\xff":
                    m = f.read(1)
                if not m:
                    return None
                marker = m[0]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    continue
                ln = int.from_bytes(f.read(2), "big")
                if ln < 2:
                    return None
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    seg = f.read(5)
                    if len(seg) < 5:
                        return None
                    h = int.from_bytes(seg[1:3], "big")
                    w = int.from_bytes(seg[3:5], "big")
                    return (w, h, "jpg")
                f.seek(ln - 2, 1)
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            f.seek(12)
            ck = f.read(4)
            f.read(4)
            if ck == b"VP8X":
                d = f.read(10)
                if len(d) < 10:
                    return None
                return (1 + int.from_bytes(d[4:7], "little"),
                        1 + int.from_bytes(d[7:10], "little"), "webp")
            if ck == b"VP8 ":
                d = f.read(10)
                if len(d) < 10:
                    return None
                return (int.from_bytes(d[6:8], "little") & 0x3FFF,
                        int.from_bytes(d[8:10], "little") & 0x3FFF, "webp")
            if ck == b"VP8L":
                d = f.read(5)
                if len(d) < 5 or d[0] != 0x2F:
                    return None
                bits = int.from_bytes(d[1:5], "little")
                return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, "webp")
    except Exception:                                            # noqa: BLE001
        return None
    return None


def dims_of_bytes(raw):
    return dims_from_stream(io.BytesIO(raw))


def read_dims(path):
    try:
        with open(path, "rb") as f:
            return dims_from_stream(f)
    except Exception:                                            # noqa: BLE001
        return None


def guess_ext(raw, ctype=""):
    if raw[:3] == b"GIF":
        return "gif"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:2] == b"\xff\xd8":
        return "jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    if "jpeg" in ctype or "jpg" in ctype:
        return "jpg"
    if "webp" in ctype:
        return "webp"
    return "png"


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=240) as x:
        return x.read(), (x.headers.get("Content-Type") or "")


# ───────────────────────── 尺寸与计划 ─────────────────────────
def check_size(size):
    """按 gpt-image 的四条硬约束校验自定义尺寸。返回 (ok, 原因)。"""
    if not size or size in ("auto", "1k", "2k", "4k"):
        return True, ""
    if "x" not in size.lower():
        return False, "size 只能是 auto / 1k / 2k / 4k / 宽x高"
    try:
        w, h = [int(x) for x in size.lower().split("x", 1)]
    except Exception:                                            # noqa: BLE001
        return False, "size 格式不对：%s" % size
    if w % 16 or h % 16:
        return False, "宽高都必须是 16 的倍数（%dx%d）" % (w, h)
    lo, hi = min(w, h), max(w, h)
    if hi > 3 * lo:
        return False, "长边/短边不能超过 3:1（%dx%d）" % (w, h)
    if hi > 3840:
        return False, "单边不能超过 3840（%dx%d）" % (w, h)
    px = w * h
    if px < 655360 or px > 8294400:
        return False, "总像素需在 655,360–8,294,400 之间（%dx%d = %s 像素）" % (w, h, fmt_pts(px))
    return True, ""


def slot_prompt(product, kind, title, scene, ratio):
    if ratio == "3:4":
        framing = "竖版 3:4 构图，上下各留 8% 安全区，主体居中不压边"
    else:
        framing = "正方形 1:1 构图，四周各留 5%~8% 安全区，主体比例稳定"
    return "%s。%s。%s。%s。产品摄影质感，细节清晰，光线干净。" % (
        product, scene, framing, NO_TEXT)


def build_slots(product, platform, main, scene, detail, engine):
    p = PLATFORMS[platform]
    out = []
    counts = {"main": main, "scene": scene, "detail": detail}
    seen = {"main": 0, "scene": 0, "detail": 0}
    for sid, kind, title, sc in SLOTS:
        if seen[kind] >= counts[kind]:
            continue
        seen[kind] += 1
        out.append({"id": sid, "kind": kind, "index": seen[kind], "title": title,
                    "prompt": slot_prompt(product, kind, title, sc, p["ratio"])})
    return out


def _slot_points(engine, refs=False):
    return POINTS_NANO if engine == "nano" else (POINTS_EDIT if refs else POINTS_IMAGE)


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    lines = []
    lines.append({"path": "gpt-image-2.6 文生图", "endpoint": "/api/v1/images/generations",
                  "points": POINTS_IMAGE, "unit": "张", "sync": True,
                  "how": "一轮请求一次出，n 可 1–4；本包固定 n=1，出几张算几张"})
    lines.append({"path": "gpt-image-2.6 改图", "endpoint": "/api/v1/images/edits",
                  "points": POINTS_EDIT, "unit": "次", "sync": True,
                  "how": "multipart 传实拍图，同样的 6 点，商品不走样"})
    lines.append({"path": "nano_banana 出图", "endpoint": "/api/v1/apps/nano_banana/submit",
                  "points": POINTS_NANO, "unit": "次", "sync": False,
                  "how": "异步；1K / 2K / 4K 与 11 种比例可选"})
    lines.append({"path": "换装 dressing_diffusion",
                  "endpoint": "/api/v1/apps/dressing_diffusion/submit",
                  "points": POINTS_DRESS, "unit": "次", "sync": False,
                  "how": "模特图 + 服装图 → 穿在身上的效果图"})
    total10 = 10 * POINTS_IMAGE
    out = {"ok": True, "lines": lines, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "setSize": 10, "setPoints": total10,
           "walkthroughs": [
               {"name": "全 gpt（默认，10 张）", "points": total10},
               {"name": "gpt 改图（10 张，带实拍图）", "points": 10 * POINTS_EDIT},
               {"name": "全 nano（10 张）", "points": 10 * POINTS_NANO},
               {"name": "换装 1 张 + gpt 10 张", "points": POINTS_DRESS + total10},
           ],
           "platforms": [{"key": k, "name": PLATFORMS[k]["name"],
                          "platformPx": PLATFORMS[k]["px"], "ratio": PLATFORMS[k]["ratio"],
                          "requestSize": PLATFORMS[k]["size"], "why": PLATFORMS[k]["why"]}
                         for k in PLATFORM_ORDER],
           "slots": [{"id": s[0], "kind": s[1], "title": s[2]} for s in SLOTS]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("三剪客 · 电商图包 —— 一张商品图，出一整套上架素材")
    print()
    print("  四条路径（价格 2026-11-07 核过：两条来自价格表，两条来自流水）")
    print("  %s %s %s %s" % (pad("路径", 26), pad("单价", 12), pad("端点", 46), "说明"))
    print("  " + "-" * 108)
    for r in lines:
        print("  %s %s %s %s" % (pad(r["path"], 26),
                                  pad("%d 点/%s" % (r["points"], r["unit"]), 12),
                                  pad(r["endpoint"], 46), r["how"]))
    print()
    print("  一套素材 10 张（主图 5 + 场景 3 + 细节 2）的四种走法")
    print("  " + "-" * 56)
    for w in out["walkthroughs"]:
        print("    %s %s = %.2f 元" % (pad(w["name"], 32),
                                       pad("%d 点" % w["points"], 10, left=False),
                                       yuan(w["points"])))
    print()
    print("  尺寸适配（这是最容易踩的一脚：平台尺寸往往不是合法请求尺寸）")
    print("  %s %s %s %s" % (pad("--platform", 12), pad("平台要求", 14),
                              pad("实际请求 size", 16), "为什么换"))
    print("  " + "-" * 108)
    for r in out["platforms"]:
        print("  %s %s %s %s" % (pad(r["key"], 12), pad(r["platformPx"], 14),
                                  pad(r["requestSize"], 16), r["why"]))
    print()
    print("  主图位模板（--main 取前 N 个，--scene / --detail 同理）")
    for s in out["slots"]:
        print("    %s  %-6s %s" % (pad(s["id"], 8), s["kind"], s["title"]))
    print()
    print("  三条实测干货（写进默认行为，不是建议）")
    print("    · 应用层 query 不免费：流水里 nano_banana/query 216 笔 × 72 点 = 15,552 点，")
    print("      本包轮询只走 GET /api/v1/tasks/<id>（免费）")
    print("    · GET /api/v1/apps/<app> 一次就是该应用单价（200 / 72），doctor 一次都不打")
    print("    · 800×800 不是合法请求尺寸（640,000 像素 < 655,360），必须换 1024×1024")
    return 0


def cmd_cost(a, key, host):
    p = PLATFORMS[a.platform]
    n = a.main + a.scene + a.detail
    engine = a.engine
    per = _slot_points(engine, bool(a.ref))
    total = per * n
    rows = [
        {"name": "本次（%s）" % ("nano_banana" if engine == "nano" else
                                ("gpt 改图" if a.ref else "gpt 文生图")),
         "points": total, "formula": "%d 张 × %d 点" % (n, per)},
        {"name": "同一套全走 gpt", "points": n * POINTS_IMAGE,
         "formula": "%d 张 × %d 点" % (n, POINTS_IMAGE)},
        {"name": "同一套全走 nano", "points": n * POINTS_NANO,
         "formula": "%d 张 × %d 点" % (n, POINTS_NANO)},
    ]
    if a.dress:
        rows.append({"name": "加 1 次换装（在本次之上）", "points": total + POINTS_DRESS,
                     "formula": "200 点 + %d 点" % total})
    over = total > a.budget
    out = {"ok": True, "platform": a.platform, "platformName": p["name"],
           "platformPx": p["px"], "requestSize": p["size"], "ratio": p["ratio"],
           "engine": engine, "ref": bool(a.ref), "count": n,
           "main": a.main, "scene": a.scene, "detail": a.detail,
           "pointsPerImage": per, "total": total, "yuan": yuan(total),
           "budget": a.budget, "overBudget": over, "rows": rows,
           "priceBasis": {"gpt": "流水 sync:/api/v1/images/generations 82 笔 -6",
                          "edit": "流水 sync:/api/v1/images/edits 2 笔 -6",
                          "nano": "价格表 /api/v1/apps/nano_banana/* flat 72",
                          "dress": "价格表 /api/v1/apps/dressing_diffusion/* flat 200"}}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）")
    print("  平台：%s（%s，%s）→ 请求 size %s"
          % (p["name"], p["px"], p["ratio"], p["size"]))
    print("  张数：主图 %d + 场景 %d + 细节 %d = %d 张"
          % (a.main, a.scene, a.detail, n))
    print()
    print("  本次：%d 张 × %d 点 = **%d 点 = %.2f 元**" % (n, per, total, yuan(total)))
    print()
    print("  同一套别的走法")
    for r in rows[1:]:
        print("    %s %s = %.2f 元" % (pad(r["name"], 30),
                                       pad("%d 点" % r["points"], 10, left=False),
                                       yuan(r["points"])))
    print()
    print("  单价出处：gpt 6 点/张与改图 6 点/次来自流水；nano 72、换装 200 来自 /api/v1/pricing。")
    print("  --budget %d 点；超了真跑会被闸门拦下（exit 5，一个请求都不发）。" % a.budget)
    if over:
        say("  这一套 %d 点已经超过 --budget %d 点（真跑会被闸门拦下）" % (total, a.budget))
    return 0


def _apps_index(key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    data = unwrap(st, txt, "拉应用目录")
    lst = data.get("list") if isinstance(data, dict) else data
    idx = {}
    for it in (lst or []):
        if isinstance(it, dict) and it.get("code"):
            idx[it["code"]] = {ap.get("code"): (ap.get("method") or "").upper()
                               for ap in (it.get("apis") or []) if isinstance(ap, dict)}
    return idx


def _flat_cost(pricing, path):
    p = pricing.get(path) if isinstance(pricing, dict) else None
    if isinstance(p, dict) and p.get("mode") == "flat":
        return p.get("cost")
    return None


def _balance(key, host):
    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    if st != 200:
        raise Fail("call", "余额接口失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    return d


def cmd_doctor(a, key, host):
    """全部免费：只读目录 + 价目表 + 一次「空 prompt 换 422」，并自己证明扣 0 点。"""
    checks = []
    before = None
    try:
        before = _balance(key, host)
    except Fail as e:
        checks.append(("余额接口可达", False, e.message[:60]))

    st, txt = http_json("GET", host + API_PREFIX + "/models", key, timeout=60)
    d = jloads(txt) or {}
    checks.append(("Key 有效 + 模型目录可达", st == 200, "HTTP %s" % st))

    models = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("model_code"):
                models.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(d)
    hit = [m for m in models if m.get("model_code") == MODEL]
    ref_max = (hit[0].get("max_reference_images") if hit else None)
    checks.append(("模型 %s 在架（参考图上限 %s 张）" % (MODEL, ref_max),
                   bool(hit), "目录共 %d 个模型" % len(models)))

    apps = {}
    try:
        apps = _apps_index(key, host)
        n_ok = "submit" in apps.get("nano_banana", {})
        d_ok = "submit" in apps.get("dressing_diffusion", {})
        checks.append(("应用 nano_banana 在架（提交接口）", n_ok,
                       "接口：%s" % ",".join(sorted(apps.get("nano_banana", {})))))
        checks.append(("应用 dressing_diffusion 在架（提交接口）", d_ok,
                       "接口：%s" % ",".join(sorted(apps.get("dressing_diffusion", {})))))
        q = ("query" in apps.get("nano_banana", {}))
        checks.append(("已识别「应用层 query 会按次扣费」，本包不走它", q,
                       "query 在架但流水实测 216 笔 × 72 点，轮询改走 /tasks"))
    except Fail as e:
        checks.append(("应用目录可读", False, e.message[:60]))

    try:
        st2, txt2 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
        d2 = jloads(txt2) or {}
        pricing = d2.get("pricing") if isinstance(d2, dict) else None
        if pricing is None:
            pricing = (unwrap(st2, txt2, "拉价格表") or {}).get("pricing") or {}
        n_cost = _flat_cost(pricing, "/api/v1/apps/nano_banana/submit")
        d_cost = _flat_cost(pricing, "/api/v1/apps/dressing_diffusion/submit")
        img_rule = _flat_cost(pricing, "/api/v1/images/generations")
        checks.append(("价格表：nano_banana 固定 %d 点/次" % POINTS_NANO,
                       n_cost == POINTS_NANO, "价格表写 %s 点" % (n_cost,)))
        checks.append(("价格表：换装固定 %d 点/次" % POINTS_DRESS,
                       d_cost == POINTS_DRESS, "价格表写 %s 点" % (d_cost,)))
        checks.append(("价格表：图片线按模型计次（无独立 flat 规则）",
                       img_rule is None,
                       "价格表 %d 条规则里没有 /api/v1/images/generations"
                       % len(pricing)))
    except Fail as e:
        checks.append(("价格表可读", False, e.message[:60]))

    # 端点探针：带 model + 空 prompt → 422「at least 1 character」，停在扣费之前
    st3, txt3 = http_json("POST", host + API_PREFIX + "/images/generations", key,
                          {"model": MODEL, "prompt": ""}, timeout=60)
    d3 = jloads(txt3) or {}
    e3 = d3.get("error") if isinstance(d3.get("error"), dict) else {}
    ok3 = st3 == 422 and "at least 1 character" in (e3.get("message") or "")
    checks.append(("文生图端点可用（422 即正确）", ok3,
                   "HTTP %s %s" % (st3, (e3.get("message") or "")[:44])))

    # 查询路由：假 taskId → code 0「任务不存在」，免费
    st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/picset-doctor-probe",
                          key, timeout=40)
    d4 = jloads(txt4) or {}
    checks.append(("任务查询 GET /tasks/{id} 可用（免费）",
                   st4 == 200 and d4.get("code") == 0,
                   "HTTP %s %s" % (st4, (d4.get("msg") or "")[:24])))

    # 自己证明：余额没动
    delta = None
    if before is not None:
        try:
            after = _balance(key, host)
            b0 = float(before.get("available_points") or 0)
            b1 = float(after.get("available_points") or 0)
            delta = round(b1 - b0, 4)
            checks.append(("本轮自检扣 0 点（余额前后一致）", abs(delta) < 0.0001,
                           "前 %s → 后 %s 点，差 %s" % (fmt_pts(b0), fmt_pts(b1), delta)))
        except Fail as e:
            checks.append(("余额前后对比", False, e.message[:60]))

    out = {"ok": all(c[1] for c in checks), "model": MODEL,
           "endpoints": {"gen": host + API_PREFIX + "/images/generations",
                         "edit": host + API_PREFIX + "/images/edits",
                         "nano": host + API_PREFIX + "/apps/nano_banana/submit",
                         "dress": host + API_PREFIX + "/apps/dressing_diffusion/submit",
                         "task": host + API_PREFIX + "/tasks/<task_id>"},
           "prices": {"gpt": POINTS_IMAGE, "edit": POINTS_EDIT,
                      "nano": POINTS_NANO, "dress": POINTS_DRESS},
           "spentPoints": 0 if delta in (None, 0) else delta,
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        if out["ok"]:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        bad = dict(out)
        bad["exit"] = EXIT_GATE
        bad["error"] = {"kind": "gate",
                        "message": "自检有 %d 项没通过：%s"
                                   % (sum(1 for c in checks if not c[1]),
                                      "；".join(n for n, o, _ in checks if not o)[:200])}
        print(json.dumps(bad, ensure_ascii=False))
        return EXIT_GATE
    print("自检（全免费：只读目录 + 价目表 + 一次 422 参数校验探针；0 建单、0 扣费）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 46), dt))
    print()
    print("  端点：POST %s" % out["endpoints"]["gen"])
    print("        POST %s（改图，multipart）" % out["endpoints"]["edit"])
    print("        POST %s（异步）" % out["endpoints"]["nano"])
    print("        POST %s（异步）" % out["endpoints"]["dress"])
    print("  轮询：GET  %s（免费；应用层 query 会按次扣费）" % out["endpoints"]["task"])
    print("  单价：gpt 6 点/张 · 改图 6 点/次 · nano 72 点/次 · 换装 200 点/次")
    print("  本轮花费：0 点")
    return 0 if out["ok"] else EXIT_GATE


def cmd_plan(a, key, host):
    if not (a.product or "").strip():
        raise Fail("usage", "必须给 --product（商品名，会写进提示词和文件名）", EXIT_USAGE)
    if a.main < 1:
        raise Fail("usage", "--main 至少 1 张（主图位是整套的骨架）", EXIT_USAGE)
    for name, v in (("--main", a.main), ("--scene", a.scene), ("--detail", a.detail)):
        if v < 0 or v > len([s for s in SLOTS if s[1] == name.strip("-")]):
            raise Fail("usage", "%s 只能是 0–%d" % (
                name, len([s for s in SLOTS if s[1] == name.strip("-")])), EXIT_USAGE)
    ok, why = check_size(PLATFORMS[a.platform]["size"])
    if not ok:
        raise Fail("internal", "内置尺寸不合法：%s（%s）" % (why, a.platform), EXIT_INTERNAL)

    p = PLATFORMS[a.platform]
    slots = build_slots(a.product.strip(), a.platform, a.main, a.scene, a.detail, a.engine)
    per = _slot_points(a.engine)
    for s in slots:
        s["points"] = per
        if a.engine == "nano":
            s["request"] = {"endpoint": "/api/v1/apps/nano_banana/submit",
                            "model": NANO_MODEL, "resolution": a.resolution,
                            "aspect_ratio": p["ratio"], "action": "generate"}
        else:
            s["request"] = {"endpoint": "/api/v1/images/generations",
                            "model": MODEL, "n": 1, "size": p["size"]}
    total = per * len(slots)
    plan = {"ok": True, "product": a.product.strip(), "platform": a.platform,
            "platformName": p["name"], "platformPx": p["px"], "ratio": p["ratio"],
            "requestSize": p["size"], "sizeNote": p["why"], "engine": a.engine,
            "slots": slots, "count": len(slots), "totalPoints": total,
            "yuan": yuan(total), "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S")}

    outdir = a.outdir or "."
    path = os.path.join(outdir, "plan.json")
    if os.path.isfile(path) and not a.overwrite:
        raise Fail("usage", "%s 已存在。加 --overwrite 覆盖，或换 --outdir。" % path,
                   EXIT_USAGE)
    if not a.dry_run:
        os.makedirs(outdir, exist_ok=True)
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(plan, ensure_ascii=False, indent=1))
    plan["planFile"] = None if a.dry_run else path
    plan["dryRun"] = bool(a.dry_run)

    if a.json:
        print(json.dumps(plan, ensure_ascii=False))
        return 0
    if a.dry_run:
        print("干跑（不写文件）")
    else:
        print("已生成计划：%s" % path)
    print("  商品：%s" % plan["product"])
    print("  平台：%s（%s，%s）→ 请求 size %s"
          % (p["name"], p["px"], p["ratio"], p["size"]))
    print("  尺寸说明：%s" % p["why"])
    print()
    print("  %s %s %s %s %s" % (pad("位", 9), pad("用途", 10), pad("标题", 12),
                                 pad("点数", 6), "提示词首句"))
    print("  " + "-" * 100)
    for s in slots:
        print("  %s %s %s %s %s" % (pad(s["id"], 9), pad(s["kind"], 10),
                                     pad(s["title"], 12), pad(s["points"], 6),
                                     s["prompt"][:52]))
    print()
    print("  合计 %d 张 = %d 点 = %.2f 元" % (len(slots), total, yuan(total)))
    print("  下一步：python3 scripts/run.py gen --plan %s --outdir %s --yes"
          % (path, outdir))
    return 0


# ───────────────────────── 出图 ─────────────────────────
def _load_plan(path):
    if not path:
        raise Fail("usage", "必须给 --plan（先跑 plan 生成 plan.json）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "计划文件不存在：%s（先跑 `plan --product …`）" % path, EXIT_USAGE)
    try:
        plan = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:                                       # noqa: BLE001
        raise Fail("usage", "计划文件不是合法 JSON：%s（%s）" % (path, e), EXIT_USAGE)
    if not isinstance(plan, dict) or not isinstance(plan.get("slots"), list):
        raise Fail("usage", "计划文件缺 slots：%s" % path, EXIT_USAGE)
    return plan


def _select_slots(a, plan):
    slots = plan["slots"]
    ids = set()
    if a.slot:
        for s in a.slot:
            ids.update([x.strip() for x in str(s).split(",") if x.strip()])
    kinds = set()
    if a.kind:
        kinds.update([x.strip() for x in str(a.kind).split(",") if x.strip()])
    bad = [i for i in ids if i not in [s.get("id") for s in slots]]
    if bad:
        raise Fail("usage", "计划里没有这些位：%s（可选：%s）"
                   % (", ".join(bad), ", ".join([s.get("id") for s in slots])), EXIT_USAGE)
    sel = [s for s in slots if (not ids or s.get("id") in ids)
           and (not kinds or s.get("kind") in kinds)]
    if not sel:
        raise Fail("usage", "--slot / --kind 选出 0 个位", EXIT_USAGE)
    return sel


def _gate(a, cost, what):
    """两道闸门：预算（exit 5，一个请求都不发）→ 确认（exit 4）。"""
    if cost > a.budget:
        raise Fail("budget", "%s预计 %d 点，超过 --budget %d 点。调大 --budget 或减少位；"
                             "一个请求都没发。" % (what, cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "%s这一轮要真实扣约 %d 点（%.2f 元）。确认请加 --yes；"
                              "想先看请求加 --dry-run。"
                   % (what, cost, cost / POINTS_PER_YUAN), EXIT_CONFIRM)


def _save(raw, ctype, outdir, prefix, platform, slot_id):
    """把一张图的字节落盘，文件名里的像素是**读文件头**写的，不抄计划。"""
    os.makedirs(outdir, exist_ok=True)
    dims = dims_of_bytes(raw)
    ext = guess_ext(raw, ctype)
    if dims:
        name = "%s_%s_%s_%dx%d.%s" % (prefix, platform, slot_id, dims[0], dims[1], ext)
    else:
        name = "%s_%s_%s.%s" % (prefix, platform, slot_id, ext)
    path = os.path.join(outdir, name)
    i = 2
    while os.path.isfile(path):
        name = "%s_%s_%s_%d.%s" % (prefix, platform, slot_id, i, ext)
        path = os.path.join(outdir, name)
        i += 1
    with open(path, "wb") as fh:
        fh.write(raw)
    return path


def _save_payload(d, outdir, prefix, platform, slot_id):
    """同步响应里的 b64_json 或 url 都处理。返回文件列表。"""
    files = []
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(data, list):
        return files
    for it in data:
        if not isinstance(it, dict):
            continue
        b64 = it.get("b64_json")
        if b64:
            files.append(_save(base64.b64decode(b64), "", outdir, prefix, platform,
                               slot_id if len(data) == 1 else
                               "%s-%d" % (slot_id, len(files) + 2)))
            continue
        u = it.get("url")
        if u:
            raw, ctype = download(u)
            files.append(_save(raw, ctype, outdir, prefix, platform,
                               slot_id if len(data) == 1 else
                               "%s-%d" % (slot_id, len(files) + 2)))
    return files


def _collect_urls(node, out=None, hint=""):
    if out is None:
        out = []
    if isinstance(node, str):
        h = hint.lower()
        if node.startswith("http") and "callback" not in h and any(
                s in h for s in ("image", "url", "output", "result")):
            if node not in out:
                out.append(node)
    elif isinstance(node, dict):
        for k, v in node.items():
            _collect_urls(v, out, str(k))
    elif isinstance(node, list):
        for v in node:
            _collect_urls(v, out, hint)
    return out


def _get_task(key, host, task_id, timeout=40):
    st, txt = http_json("GET", host + API_PREFIX + "/tasks/"
                        + urllib.parse.quote(str(task_id)), key, timeout=timeout)
    d = jloads(txt) or {}
    if st != 200:
        raise Fail("call", "查询任务失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if d.get("code") not in (1, "1"):
        raise Fail("call", "查询任务失败：%s" % err_text(st, txt), EXIT_CALL)
    return d.get("data") or d


TERMINAL_OK = ("completed", "complete", "done", "success", "succeeded")
TERMINAL_BAD = ("failed", "error", "canceled", "cancelled", "timeout", "refunded")


def _poll(key, host, task_id, wait, every):
    deadline = time.time() + max(30, wait)
    last = None
    while time.time() < deadline:
        time.sleep(max(2, every))
        d = _get_task(key, host, task_id)
        st = str(d.get("status") or "").lower()
        if st != last:
            say("  状态：%s" % (st or "?"))
            last = st
        if st in TERMINAL_OK or st in TERMINAL_BAD:
            return d, st
    raise Fail("call", "等 %d 秒还没完成。任务没丢——用 `status --task-id %s` 接着取，"
                       "不要重新提交（会再扣一次）。" % (wait, task_id), EXIT_CALL)


def cmd_gen(a, key, host):
    plan = _load_plan(a.plan)
    sel = _select_slots(a, plan)
    engine = a.engine or plan.get("engine") or "gpt"
    if engine == "nano":
        per = POINTS_NANO
    elif a.ref:
        per = POINTS_EDIT
    else:
        per = POINTS_IMAGE
    cost = per * len(sel)
    platform = plan.get("platform") or "taobao"
    prefix = a.prefix or "picset"
    outdir = a.outdir or os.path.dirname(os.path.abspath(a.plan))

    refs = []
    for r in (a.ref or []):
        if not os.path.isfile(r):
            raise Fail("usage", "--ref 图片不存在：%s" % r, EXIT_USAGE)
        refs.append(r)
    if len(refs) > 6:
        raise Fail("usage", "--ref 最多 6 张（模型参考图上限 6）", EXIT_USAGE)
    if engine == "nano" and refs:
        raise Fail("usage", "--ref 是 gpt 改图用的；--engine nano 请用 --image-url", EXIT_USAGE)
    if engine == "nano":
        if a.resolution not in NANO_RES:
            raise Fail("usage", "--resolution 只能是 %s" % " / ".join(NANO_RES), EXIT_USAGE)

    _gate(a, cost, "%d 张图" % len(sel))

    if a.dry_run:
        steps = []
        for s in sel:
            if engine == "nano":
                req = {"endpoint": host + API_PREFIX + "/apps/nano_banana/submit",
                       "method": "POST",
                       "body": {"prompt": s["prompt"], "model": NANO_MODEL,
                                "resolution": a.resolution,
                                "aspect_ratio": plan.get("ratio") or "1:1",
                                "action": "edit" if a.image_url else "generate"}}
                if a.image_url:
                    req["body"]["image_urls"] = list(a.image_url)
            elif refs:
                req = {"endpoint": host + API_PREFIX + "/images/edits",
                       "method": "POST", "multipart": True,
                       "fields": {"model": MODEL, "prompt": s["prompt"], "n": 1,
                                  "size": plan.get("requestSize") or "1024x1024",
                                  "output_format": "png", "response_format": "b64_json"},
                       "files": refs}
            else:
                req = {"endpoint": host + API_PREFIX + "/images/generations",
                       "method": "POST",
                       "body": {"model": MODEL, "prompt": s["prompt"], "n": 1,
                                "size": plan.get("requestSize") or "1024x1024",
                                "output_format": "png", "response_format": "b64_json"}}
            steps.append({"slot": s["id"], "points": per, "request": req})
        out = {"ok": True, "dryRun": True, "engine": engine, "count": len(sel),
               "pointsPerImage": per, "estimatedPoints": cost, "yuan": yuan(cost),
               "steps": steps}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）：%d 张，共 %d 点（%.2f 元）"
              % (len(sel), cost, yuan(cost)))
        for i, st in enumerate(steps, 1):
            r = st["request"]
            print("  [%d/%d] %s %d 点 → %s" % (i, len(steps), st["slot"], st["points"],
                                               r["endpoint"]))
            if r.get("multipart"):
                print("        fields=%s" % json.dumps(r["fields"], ensure_ascii=False)[:150])
                print("        files=%s" % ", ".join(r["files"]))
            else:
                print("        body=%s" % json.dumps(r["body"], ensure_ascii=False)[:190])
        return 0

    say("开始出图：%d 张，预计 %d 点（%.2f 元）" % (len(sel), cost, yuan(cost)))
    done, files, spent = [], [], 0
    t_all = time.time()
    for i, s in enumerate(sel, 1):
        t0 = time.time()
        say("[%d/%d] %s（%s）…" % (i, len(sel), s["id"], s.get("title") or ""))
        try:
            if engine == "nano":
                body = {"prompt": s["prompt"], "model": NANO_MODEL,
                        "resolution": a.resolution,
                        "aspect_ratio": plan.get("ratio") or "1:1",
                        "action": "edit" if a.image_url else "generate"}
                if a.image_url:
                    body["image_urls"] = list(a.image_url)
                url = host + API_PREFIX + "/apps/nano_banana/submit"
                st, txt = http_json("POST", url, key, body, timeout=max(60, a.timeout))
                data = unwrap(st, txt, "提交出图任务")
                task_id = (data or {}).get("task_id") if isinstance(data, dict) else None
                if not task_id:
                    raise Fail("call", "提交没拿到 task_id：%s" % txt[:180], EXIT_CALL)
                say("  task_id=%s，轮询 GET /api/v1/tasks/%s（免费）" % (task_id, task_id))
                task, tstate = _poll(key, host, task_id, a.wait, a.every)
                urls = _collect_urls(task)
                got = []
                for u in urls:
                    raw, ctype = download(u)
                    got.append(_save(raw, ctype, outdir, prefix, platform,
                                     s["id"] if len(urls) == 1 else
                                     "%s-%d" % (s["id"], len(got) + 2)))
                if tstate in TERMINAL_BAD and not got:
                    raise Fail("call", "任务 %s 结束状态 %s：%s"
                               % (task_id, tstate,
                                  json.dumps(task.get("error"), ensure_ascii=False)[:160]),
                               EXIT_CALL)
                spent += per
                files += got
                done.append({"slot": s["id"], "kind": s.get("kind"), "taskId": task_id,
                             "status": tstate, "files": got, "points": per,
                             "elapsed": round(time.time() - t0, 1)})
                ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(got),
                            "engine": "nano", "slot": s["id"], "taskId": task_id,
                            "points": per, "files": got,
                            "elapsed": round(time.time() - t0, 1)})
            elif refs:
                url = host + API_PREFIX + "/images/edits"
                fields = {"model": MODEL, "prompt": s["prompt"], "n": 1,
                          "size": plan.get("requestSize") or "1024x1024",
                          "output_format": "png", "response_format": "b64_json"}
                st, txt = http_multipart(url, key, fields,
                                         [("image[]", r) for r in refs],
                                         timeout=max(180, a.timeout))
                d = unwrap(st, txt, "改图")
                got = _save_payload(d, outdir, prefix, platform, s["id"])
                if not got:
                    raise Fail("call", "改图响应里没有图：%s" % txt[:180], EXIT_CALL)
                spent += per
                files += got
                done.append({"slot": s["id"], "kind": s.get("kind"), "files": got,
                             "points": per, "elapsed": round(time.time() - t0, 1)})
                ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True,
                            "engine": "edit", "slot": s["id"], "points": per,
                            "files": got, "elapsed": round(time.time() - t0, 1)})
            else:
                url = host + API_PREFIX + "/images/generations"
                body = {"model": MODEL, "prompt": s["prompt"], "n": 1,
                        "size": plan.get("requestSize") or "1024x1024",
                        "output_format": "png", "response_format": "b64_json"}
                st, txt = http_json("POST", url, key, body, timeout=max(180, a.timeout))
                d = unwrap(st, txt, "出图")
                got = _save_payload(d, outdir, prefix, platform, s["id"])
                if not got:
                    raise Fail("call", "响应里没有图：%s" % txt[:180], EXIT_CALL)
                spent += per
                files += got
                done.append({"slot": s["id"], "kind": s.get("kind"), "files": got,
                             "points": per, "elapsed": round(time.time() - t0, 1)})
                ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True,
                            "engine": "gpt", "slot": s["id"], "points": per,
                            "files": got, "elapsed": round(time.time() - t0, 1)})
        except Fail as e:
            ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                        "engine": engine, "slot": s["id"], "points": 0,
                        "error": e.message[:200]})
            if done:
                e.message = "%s\n已出 %d/%d 张（实际扣 %d 点），剩余未发请求。" % (
                    e.message, len(done), len(sel), spent)
            raise

    dt = time.time() - t_all
    out = {"ok": True, "engine": engine, "count": len(sel), "pointsPerImage": per,
           "billedPoints": spent, "yuan": yuan(spent), "elapsed": round(dt, 1),
           "files": files, "slots": done, "outdir": outdir, "prefix": prefix}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("出图完成（%.1fs）" % dt)
    print("  张数：%d，计费：%d 点（%.2f 元）" % (len(files), spent, yuan(spent)))
    for f in files:
        print("  文件：%s（%d 字节）" % (f, os.path.getsize(f)))
    print()
    print("  下一步：python3 scripts/run.py names --dir %s --platform %s --apply"
          % (outdir, platform))
    print("         python3 scripts/run.py check --dir %s --platform %s"
          % (outdir, platform))
    return 0


# ───────────────────────── 批量命名 / 合规清单 ─────────────────────────
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _list_images(d):
    if not os.path.isdir(d):
        raise Fail("usage", "目录不存在：%s" % d, EXIT_USAGE)
    out = []
    for name in sorted(os.listdir(d)):
        if name.lower().endswith(IMG_EXT):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                out.append(p)
    return out


def _slot_of(name):
    m = re.search(r"(main|scene|detail)0*(\d+)", name)
    if m:
        return "%s%02d" % (m.group(1), int(m.group(2)))
    return None


def cmd_names(a, key, host):
    d = a.dir or "."
    files = _list_images(d)
    if not files:
        raise Fail("usage", "%s 里没有图片（%s）" % (d, " / ".join(IMG_EXT)), EXIT_USAGE)
    platform = a.platform or "taobao"
    prefix = a.prefix or "picset"
    order = []
    for p in files:
        dims = read_dims(p)
        slot = _slot_of(os.path.basename(p))
        order.append({"file": p, "dims": dims, "slot": slot})
    # 没有位号的按顺序编号，保证一批图能被点名
    idx = 0
    for r in order:
        if not r["slot"]:
            idx += 1
            r["slot"] = "img%02d" % idx
    rows = []
    for r in order:
        if r["dims"]:
            name = "%s_%s_%s_%dx%d.%s" % (prefix, platform, r["slot"],
                                          r["dims"][0], r["dims"][1], r["dims"][2])
        else:
            ext = os.path.splitext(r["file"])[1].lstrip(".").lower()
            name = "%s_%s_%s.%s" % (prefix, platform, r["slot"], ext)
        target = os.path.join(d, name)
        rows.append({"file": os.path.basename(r["file"]), "to": name,
                     "dims": ("%dx%d" % (r["dims"][0], r["dims"][1])) if r["dims"] else None,
                     "slot": r["slot"],
                     "skip": os.path.basename(r["file"]) == name})
    out = {"ok": True, "dir": d, "prefix": prefix, "platform": platform,
           "apply": bool(a.apply), "count": len(rows), "renames": rows,
           "skipped": sum(1 for r in rows if r["skip"])}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("批量命名 %s（前缀 %s，平台 %s）" % (d, prefix, platform))
    print()
    prev = 0
    for r in rows:
        if r["skip"]:
            print("  %s 已经是目标名" % r["file"])
            continue
        target = os.path.join(d, r["to"])
        print("  %s → %s%s" % (pad(r["file"], 40), r["to"],
                                "（目标已存在，跳过）" if os.path.isfile(target) else ""))
        prev += 1
    print()
    if not a.apply:
        print("  预览模式：加 --apply 才真的改名。共 %d 个要改。" % prev)
        return 0
    ok, skipped = 0, 0
    for r in rows:
        if r["skip"]:
            continue
        src = os.path.join(d, r["file"])
        dst = os.path.join(d, r["to"])
        if os.path.isfile(dst):
            skipped += 1
            continue
        os.rename(src, dst)
        ok += 1
    print("  已改名 %d 个，跳过 %d 个（目标已存在）。" % (ok, skipped))
    return 0


def _ratio_gap(w, h, want):
    try:
        a_, b_ = [float(x) for x in want.split(":")]
    except Exception:                                            # noqa: BLE001
        return 0.0
    if not h:
        return 1.0
    return abs((float(w) / float(h)) - (a_ / b_)) / (a_ / b_)


def cmd_check(a, key, host):
    d = a.dir or "."
    files = _list_images(d)
    platform = a.platform or "taobao"
    p = PLATFORMS[platform]
    plan = None
    plan_path = a.plan or os.path.join(d, "plan.json")
    if os.path.isfile(plan_path):
        try:
            plan = json.load(io.open(plan_path, encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            plan = None

    rows = []
    for f in files:
        dims = read_dims(f)
        base = os.path.basename(f)
        size_mb = os.path.getsize(f) / 1024.0 / 1024.0
        slot = _slot_of(base)
        named_dims = re.search(r"_(\d+)x(\d+)\.[a-z]+$", base, re.I)
        row = {"file": base, "slot": slot,
               "dims": ("%dx%d" % (dims[0], dims[1])) if dims else None,
               "mb": round(size_mb, 2),
               "gap": round(_ratio_gap(dims[0], dims[1], p["ratio"]) * 100, 2) if dims else None,
               "namedDims": ("%sx%s" % named_dims.groups()) if named_dims else None}
        issues = []
        if not dims:
            issues.append("读不出像素（不是常见图片格式）")
        else:
            gap = _ratio_gap(dims[0], dims[1], p["ratio"])
            if gap > RATIO_TOL + RATIO_FLOOR:
                issues.append("比例偏 %.2f%%（要 %s）" % (gap * 100, p["ratio"]))
            if named_dims and ("%dx%d" % (dims[0], dims[1])) != \
                    ("%sx%s" % named_dims.groups()):
                issues.append("文件名里的像素与真实像素不一致")
        if size_mb > a.max_mb:
            issues.append("%.2f MB 超过 %.1f MB" % (size_mb, a.max_mb))
        if not slot:
            issues.append("文件名里没有位号（main/scene/detail）")
        row["issues"] = issues
        rows.append(row)

    have = set(r["slot"] for r in rows if r["slot"])
    missing = None
    if plan:
        missing = [s["id"] for s in plan.get("slots", []) if s["id"] not in have]
    hard = [r for r in rows if r["issues"]]
    manual = []
    if "main01" in have:
        manual.append("main01 白底位：确认背景是纯白、主体不贴边")
    manual.append("全部图：确认画面里没有文字 / 水印 / logo（AI 出图的文字不可靠）")
    manual.append("主图第 1 位之外的压字：用本地排版加，字数 ≤ 14 字，别压主体")

    ok = not hard and not missing
    out = {"ok": ok, "dir": d, "platform": platform, "platformName": p["name"],
           "ratio": p["ratio"], "platformPx": p["px"], "count": len(rows),
           "images": rows, "planFile": plan_path if plan else None,
           "missingSlots": missing,
           "issues": [{"file": r["file"], "issues": r["issues"]} for r in hard],
           "manualChecklist": manual,
           "tolerancePct": round((RATIO_TOL + RATIO_FLOOR) * 100, 2)}
    if a.json:
        if ok:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        bad = dict(out)
        bad["exit"] = EXIT_GATE
        msg = []
        if hard:
            msg.append("%d 张图有问题" % len(hard))
        if missing:
            msg.append("缺位 %s" % ", ".join(missing))
        bad["error"] = {"kind": "gate",
                        "message": "自动检查没通过：%s（不花钱，改完再跑一次）"
                                   % "；".join(msg)}
        print(json.dumps(bad, ensure_ascii=False))
        return EXIT_GATE
    print("合规清单 %s（平台 %s，要求 %s，比例 %s）"
          % (d, p["name"], p["px"], p["ratio"]))
    print("=" * 84)
    print("  %s %s %s %s %s" % (pad("文件", 38), pad("位", 8), pad("真实像素", 12),
                                 pad("MB", 6), "结论"))
    print("  " + "-" * 80)
    for r in rows:
        print("  %s %s %s %s %s" % (pad(r["file"][:38], 38), pad(r["slot"] or "-", 8),
                                     pad(r["dims"] or "-", 12), pad(r["mb"], 6),
                                     "√" if not r["issues"] else "× " + "；".join(r["issues"])))
    print()
    if missing is None:
        print("  计划齐不齐：没找到 plan.json，跳过计划对比（--plan 指一个即可）")
    else:
        print("  计划齐不齐：%s" % ("√ 全部齐了" if not missing
                                   else "× 缺 %s" % ", ".join(missing)))
    print("  自动检查：%d 张，%d 张有问题（比例容差 %.2f%%）"
          % (len(rows), len(hard), out["tolerancePct"]))
    print()
    print("  人工确认（自动查不了，出完图扫一眼）")
    for m in manual:
        print("    · %s" % m)
    print()
    print("  本轮花费 0 点（纯本地读文件头）。")
    return 0 if ok else EXIT_GATE


def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id（提交时返回的 task_id）", EXIT_USAGE)
    d = _get_task(key, host, a.task_id)
    st = str(d.get("status") or "").lower()
    urls = _collect_urls(d)
    out = {"ok": True, "taskId": a.task_id, "status": st, "urls": urls,
           "error": d.get("error"), "usage": d.get("usage")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s" % (st or "?"))
    if d.get("error"):
        print("  错误：%s" % json.dumps(d["error"], ensure_ascii=False)[:300])
    for u in urls:
        print("  图片：%s" % u)
    if st in TERMINAL_OK and a.outdir:
        files = []
        for u in urls:
            raw, ctype = download(u)
            files.append(_save(raw, ctype, a.outdir, a.prefix or "picset",
                               a.platform or "taobao", "task"))
        for f in files:
            print("  已存：%s（%d 字节）" % (f, os.path.getsize(f)))
    if not urls and st not in TERMINAL_BAD:
        print("  还没出图（未完成就是正常的）。")
    print("  查询免费：GET /api/v1/tasks/<id>。应用层 query 会按次扣费，本包不走。")
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
        print("  %s  %-5s %-6s %s 点  %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("engine") or "-",
            e.get("points"), (e.get("slot") or e.get("error") or "")[:40]))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 电商图包（主图位规划 → 尺寸适配 → 出图 → 批量命名 → 合规清单）",
        epilog="端点：POST %s/api/v1/images/generations · POST %s/api/v1/images/edits · "
               "POST %s/api/v1/apps/nano_banana/submit · "
               "GET %s/api/v1/tasks/<task_id>" % ((DEFAULT_HOST,) * 4),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="四条路径的价 + 一套素材四种走法 + 尺寸适配表（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱（免费，给本次与三条线的对照）",
                       allow_abbrev=False)
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                   help="平台预设（默认 taobao）")
    p.add_argument("--main", type=int, default=5, help="主图张数（默认 5，最多 5）")
    p.add_argument("--scene", type=int, default=3, help="场景图张数（默认 3，最多 3）")
    p.add_argument("--detail", type=int, default=2, help="细节图张数（默认 2，最多 2）")
    p.add_argument("--engine", choices=["gpt", "nano"], default="gpt",
                   help="出图线（gpt 6 点/张；nano 72 点/次）")
    p.add_argument("--ref", action="store_true", help="按 gpt 改图算（6 点/次，与文生图同价）")
    p.add_argument("--dress", action="store_true", help="把 1 次换装（200 点）也算进去")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 端点 / 价目表，并证明扣 0 点（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("plan", help="主图位规划，生成 plan.json（免费、离线）",
                       allow_abbrev=False)
    p.add_argument("--product", help="商品名（必填；写进提示词与文件名）")
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                   help="平台预设（默认 taobao）")
    p.add_argument("--main", type=int, default=5, help="主图张数（默认 5）")
    p.add_argument("--scene", type=int, default=3, help="场景图张数（默认 3）")
    p.add_argument("--detail", type=int, default=2, help="细节图张数（默认 2）")
    p.add_argument("--engine", choices=["gpt", "nano"], default="gpt",
                   help="计划里写哪条线（默认 gpt）")
    p.add_argument("--resolution", choices=NANO_RES, default="1K",
                   help="engine=nano 时的分辨率（默认 1K）")
    p.add_argument("--outdir", default=".", help="plan.json 写到这个目录（默认当前目录）")
    p.add_argument("--overwrite", action="store_true", help="覆盖已有的 plan.json")
    p.add_argument("--dry-run", action="store_true", help="只打印计划，不写文件")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("gen", help="按位出图（6 点/张，要 --yes）", allow_abbrev=False)
    p.add_argument("--plan", help="plan.json 路径（必填，先跑 plan）")
    p.add_argument("--slot", action="append", help="只出这些位，可重复：--slot main01,main02")
    p.add_argument("--kind", help="只出这类位：main / scene / detail（可逗号分隔）")
    p.add_argument("--engine", choices=["gpt", "nano"], default=None,
                   help="覆盖计划里的出图线")
    p.add_argument("--resolution", choices=NANO_RES, default="1K",
                   help="engine=nano 时的分辨率（默认 1K）")
    p.add_argument("--ref", action="append",
                   help="商品实拍图（可重复，最多 6 张）：改图模式，商品不走样")
    p.add_argument("--image-url", action="append",
                   help="engine=nano 时的参考图 URL（可重复，自动转 edit）")
    p.add_argument("--outdir", default=None, help="图片保存目录（默认 plan.json 所在目录）")
    p.add_argument("--prefix", default="picset", help="文件名前缀（默认 picset）")
    p.add_argument("--wait", type=int, default=600, help="异步任务等待上限秒数（默认 600）")
    p.add_argument("--every", type=int, default=5, help="轮询间隔秒数（默认 5）")
    p.add_argument("--timeout", type=int, default=300, help="单次请求超时秒数")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("names", help="批量命名成「平台_位_像素」（免费、本地）",
                       allow_abbrev=False)
    p.add_argument("--dir", default=".", help="图片目录（默认当前目录）")
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                   help="写进文件名里的平台（默认 taobao）")
    p.add_argument("--prefix", default="picset", help="文件名前缀（默认 picset）")
    p.add_argument("--apply", action="store_true", help="真的改名（不给就是预览）")
    p.set_defaults(fn=cmd_names)

    p = sub.add_parser("check", help="合规清单：像素 / 比例 / 命名 / 体积（免费、本地）",
                       allow_abbrev=False)
    p.add_argument("--dir", default=".", help="图片目录（默认当前目录）")
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao",
                   help="对齐哪个平台的比例（默认 taobao）")
    p.add_argument("--plan", help="plan.json 路径（默认找目录下的 plan.json）")
    p.add_argument("--max-mb", type=float, default=3.0,
                   help="单张体积上限 MB（默认 3.0）")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("status", help="查异步任务（免费，只走 /api/v1/tasks/<id>）",
                       allow_abbrev=False)
    p.add_argument("--task-id", help="task_id")
    p.add_argument("--outdir", default=None, help="给了就把结果图下到这个目录")
    p.add_argument("--platform", choices=PLATFORM_ORDER, default="taobao")
    p.add_argument("--prefix", default="picset")
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


NO_KEY_NEEDED = (cmd_catalog, cmd_cost, cmd_plan, cmd_names, cmd_check, cmd_log)


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    # 子命令上的全局选项 default=SUPPRESS，没写就不覆盖父级的值
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    key, host = load_conf(a.key, a.host)
    if not key and a.fn not in NO_KEY_NEEDED:
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


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-300:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


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
