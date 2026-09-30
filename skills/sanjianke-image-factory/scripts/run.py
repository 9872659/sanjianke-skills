#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 新媒体配图工厂（sanjianke-image-factory）。

给一篇文稿或一个主题，产出一整套配图：先出方案（plan），成本前置确认后再批量出图（gen）。
只花文本钱的那一步与真花钱的那一步是分开的，这是刻意的。

子命令
    plan    出配图方案（只花文本钱）
    gen     按方案批量出图（真花钱，跑之前先报价并要求 --yes）
    cost    只算钱不出图
    models  列出在架应用与模型

设计上的四条硬约束（都不是「警告」而是「拦截」）
    1. 比例真伪：**读回真实图片文件的像素**再算比例，不信接口自报字段
    2. 成本上限：超 --budget 直接停，不提交
    3. 违禁词：广告法绝对化用语命中即拦
    4. prompt_echo：出图提示词与提示词里的示例高度相似即拦
       （实测教训：模型会照抄提示词里的示例，哪怕示例标着「这是错的写法」）

零第三方依赖：只用标准库。图片裁剪（--snap）在有 PIL 时用 PIL，
没有 PIL 时回落到内置的 8 位 PNG 裁剪器，都没有就如实报告「没能裁」而不是假装成功。
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import traceback
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w        # noqa: E402  ← 共用零依赖客户端，**逐字节等于规范版，本包不许改它**
import imgprobe   # noqa: E402  ← 本包自己的图片头探针（读真实像素），独立模块

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"       # 实测可用（会路由到 deepseek-flash）
CHAT_RETRIES = 4
STATE_NAME = "image-factory-state.json"

# ---------------------------------------------------------------------------
# nano_banana 出图应用相关（本包业务，**放在这里而不是 a7w.py**）
#
# 【约定】`scripts/a7w.py` 是所有 Skill 包共用的零依赖客户端，我们靠
# 「包内副本 SHA256 == 规范版」批量校验 60+ 个包有没有被改坏。
# 所以**任何包都不许为了自己的业务往 a7w.py 里加东西**：
#   · 需要读图片像素     → 独立模块 `imgprobe.py`
#   · 需要应用专属的接口 → 就写在下面这一段里
# 上一版我把这些直接加进了 a7w.py（23825 B，哈希对不上），已按此约定拆出来。
# ---------------------------------------------------------------------------

APP_IMAGE = "nano_banana"                   # 出图应用编码
API_SUBMIT = "submit"                       # POST /api/v1/apps/nano_banana/submit
API_QUERY = "query"                         # GET  /api/v1/apps/nano_banana/query（备用）
TASK_URL = a7w.HOST + "/api/v1/tasks/{}"    # GET  /api/v1/tasks/<task_id>（统一任务查询，实际用它）

# 参数可选值。用 `python a7w.py schema nano_banana` 可现查核对（写代码前先跑这个，别猜）。
RESOLUTIONS = ("1K", "2K", "4K")
ASPECT_RATIOS = ("auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
                 "5:4", "4:5", "21:9")
ACTIONS = ("generate", "edit")
IMAGE_MODELS = ("nano-banana", "nano-banana-2", "nano-banana-2-lite",
                "nano-banana-pro", "nano-banana:official",
                "nano-banana-2-lite:official", "nano-banana-2:official",
                "nano-banana-pro:official")

# 单张轮询上限（秒）。**本包自己的口径，不改 a7w.py 里那个 1800**——
# 那里是给视频任务调的；出图实测 5~30 秒完成，600 秒足够且能更快暴露卡死。
POLL_TIMEOUT_DEFAULT = 600

# 实测单价：nano_banana 1K 出图 24 点/张（= 0.24 元，1 元 = 100 点）。
# 只有 1K 是我们真金白银打出来的数，2K/4K 没实测过，所以不给默认价——
# 想估算 2K/4K 必须自己传 --points-per-image，宁可拒绝估算也不编一个数。
POINTS_PER_IMAGE_1K = 24
POINTS_PER_YUAN = 100
UNTESTED_RESOLUTIONS = ("2K", "4K")

# 输出文件后缀白名单说明：Skill 包本身**只收文本文件**，出图一律落在包外。
OUT_EXT = ".png"

PLATFORMS = {
    "xiaohongshu": {
        "name": "小红书",
        "design_ratio": "3:4",
        "gen_ratio": "3:4",
        "pixel_hint": "1080x1440",
        "note": "竖版笔记首图。3:4 是信息流里占位最高的比例，标题区留在上方 1/4，"
                "不要把主体压在左上角（会被平台角标盖住）。",
    },
    "wechat": {
        "name": "公众号",
        "design_ratio": "2.35:1",
        "gen_ratio": "21:9",
        # 2.35:1 不在上游 aspect_ratio 可选值里（可选值最宽只到 21:9 = 2.333:1）。
        # 所以生成用 21:9，设计口径记 2.35:1，中间差值在 --snap 里裁掉。
        "pixel_hint": "900x383",
        "note": "公众号头图 2.35:1（900x383）。上游不支持 2.35:1（最宽 21:9=2.333:1），"
                "所以产出用 21:9 生成、再用 --snap 精确裁到 2.35:1。",
    },
    "douyin": {
        "name": "抖音",
        "design_ratio": "9:16",
        "gen_ratio": "9:16",
        "pixel_hint": "1080x1920",
        "note": "全屏竖版。上下各留 12% 安全区，字幕/贴纸区不要放主体。",
    },
    "toutiao": {
        "name": "头条",
        "design_ratio": "16:9",
        "gen_ratio": "16:9",
        "pixel_hint": "1280x720",
        "note": "横版封面。主体居中偏右，左侧留出标题压字区。",
    },
    "square": {
        "name": "通用方图",
        "design_ratio": "1:1",
        "gen_ratio": "1:1",
        "pixel_hint": "1024x1024",
        "note": "头像、商品主图、社群分享卡用。",
    },
}

# 上游实际能给的像素（1K 档，实测 10 种比例）。留作文档与排错依据。
MEASURED_1K_PIXELS = {
    "1:1": [1024, 1024], "3:4": [864, 1184], "4:3": [1184, 864],
    "16:9": [1344, 768], "9:16": [768, 1344], "21:9": [1536, 672],
    "2:3": [832, 1248], "3:2": [1248, 832], "4:5": [896, 1152],
    "5:4": [1152, 896],
}

ROLE_NOTES = {
    "cover": "封面：第一眼要能读懂这篇文章讲什么，主体大、留白够、不堆字",
    "inline": "内文配图：负责把某一段抽象内容变具体，可以更自由",
    "step": "步骤图：讲清一个动作或流程，构图简单、焦点单一",
    "compare": "对比图：左右或上下分栏呈现两个状态的差别",
    "data": "数据图：把一组数字视觉化（**只画文稿里真实出现过的数字**）",
    "quote": "金句图：一句核心判断 + 大量留白",
    "ending": "结尾图：引导关注/收藏，克制不吆喝",
}


# ---------------------------------------------------------------------------
# nano_banana 接口封装
#
# 为什么要单独这一段：这些是**出图应用专属**的东西，而 `a7w.py` 是 60+ 个包
# 共用的客户端（靠 SHA256 校验一致性），不许往里加业务代码。
# 通用能力（_request / _unwrap / load_key / save / A7wError / HOST）继续用 a7w 的。
#
# 平台文档写的是 `data.result.status`，**实测不对**：status 在 `data` 顶层。
# 照文档写会永远读不到状态、一路轮询到超时，所以这里按实测结构取。
# ---------------------------------------------------------------------------

def submit_image(prompt, aspect_ratio="1:1", resolution="1K",
                 model="nano-banana", action="generate", image_urls=None,
                 callback_url=None, key=None, timeout=180):
    """提交一个出图任务，返回网关 data（含 task_id 与预冻结点数）。

    请求体字段用 `python a7w.py schema nano_banana` 实查过，不要凭记忆加字段：
        prompt / action / model / image_urls / resolution / aspect_ratio / callback_url
    """
    if action not in ACTIONS:
        raise a7w.A7wError("action 只能是 {}，收到 {!r}".format(" / ".join(ACTIONS), action))
    if resolution not in RESOLUTIONS:
        raise a7w.A7wError("resolution 只能是 {}，收到 {!r}".format(" / ".join(RESOLUTIONS), resolution))
    if aspect_ratio not in ASPECT_RATIOS:
        raise a7w.A7wError("aspect_ratio 只能是 {}，收到 {!r}".format(
            " / ".join(ASPECT_RATIOS), aspect_ratio))
    if action == "edit" and not image_urls:
        raise a7w.A7wError("action=edit 时必须提供 image_urls")
    body = {"prompt": prompt, "action": action, "model": model,
            "resolution": resolution, "aspect_ratio": aspect_ratio}
    if image_urls:
        body["image_urls"] = list(image_urls)
    if callback_url:
        body["callback_url"] = callback_url
    url = "{}/api/v1/apps/{}/{}".format(a7w.HOST, APP_IMAGE, API_SUBMIT)
    return a7w._unwrap(a7w._request("POST", url, a7w.load_key(key), body=body, timeout=timeout))


def task_state(task_id, key=None):
    """查一次任务，返回 (状态, 归一化 data, 原始信封)。"""
    payload = a7w._request("GET", TASK_URL.format(task_id), a7w.load_key(key))
    data = a7w._unwrap(payload) or {}
    return data.get("status"), data, payload


def poll_task(task_id, key=None, timeout=POLL_TIMEOUT_DEFAULT,
              interval=a7w.POLL_INTERVAL, on_tick=None):
    """轮询任务到终态。

    **必须有超时上限**：出图会卡在 processing，无限等会把批处理挂死。
    返回 (状态, data, 原始信封, 轮询次数)。

    `on_tick(状态, data)` 用于把中间态写进断点文件——中途 Ctrl+C 也能续跑。
    """
    deadline = time.time() + timeout
    ticks = 0
    last = None
    while True:
        time.sleep(interval)
        ticks += 1
        status, data, payload = task_state(task_id, key)
        if status != last and on_tick:
            on_tick(status, data)
        last = status
        if status in a7w.TERMINAL:
            return status, data, payload, ticks
        if time.time() >= deadline:
            return "timeout", data, payload, ticks


def points_cost(data):
    """从任务返回里取**实际扣费**。

    ⚠️ 只信 usage.points_cost。平台的 pricing_matrix / tenant_* 字段我们验证过半数不可信
    （`image_human` 字段写 1.5/2/4/8 点/秒、实测 2/3/6/12；`voice_tts/stt` 字段写 30、实扣 40），
    所以那些字段只当参考，绝不写进结算口径。
    提交响应里的 frozen_points 也只是**预冻结**（实测 31.2），失败全额退回，不是最终扣费。
    """
    usage = (data or {}).get("usage") or {}
    for k in ("points_cost", "actual_points"):
        v = usage.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    res = (data or {}).get("result") or {}
    v = res.get("actual_points")
    return float(v) if isinstance(v, (int, float)) else None


def find_image_urls(data):
    """把任务结果里所有图片地址挖出来（结构会有差异，做深度搜索）。

    实测 completed 返回同时给了三处：`result.image_url`、
    `result.data[0].image_url`、`result.results[0].image_url`。只取第一处也能跑，
    但结构一变就瞎，所以这里按深度优先把所有 `image_url` 都收齐再去重保序。
    """
    found = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("image_url", "url", "output_url") and isinstance(v, str) \
                        and v.startswith("http"):
                    if v not in found:
                        found.append(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk((data or {}).get("result"))
    return found

# ---------------------------------------------------------------------------
# 闸门一：比例真伪（读真实像素，不信自报值）
#
# 事故来源：标题工坊上一版只信模型自报的 `formula` 字段做模板污染判定，
# 结果那个真该被判命的标题恰好漏判——闸门是**假绿**的。
# 同一个错误在出图场景的形态是：接口/模型自报 `aspect_ratio=3:4`，
# 但真实像素是 1024x1024。只信自报值 → 用户拿去排版才发现全错了。
#
# 所以这里**只认文件头里的宽高**。
#
# ⚠️ 实测到的上游特性（必须写进文档，否则闸门天天误报）：
#   上游不是按比例给像素，而是先定总像素、再把每边向下取整到 32 的倍数。
#   所以 10 种比例里有 5 种给不出像素级精确比例：
#       请求 3:4  → 864x1184   = 0.7297（3:4 = 0.75）  偏差 2.7%
#       请求 16:9 → 1344x768   = 1.7500（16:9 = 1.778）偏差 1.6%
#       请求 9:16 → 768x1344   = 0.5714（9:16 = 0.5625）偏差 1.6%
#       请求 4:5  → 896x1152   = 0.7778（4:5 = 0.8）    偏差 2.8%
#       请求 5:4  → 1152x896   = 1.2857（5:4 = 1.25）   偏差 2.9%
#   精确的 5 种：1:1 / 4:3 / 21:9 / 2:3 / 3:2
#   这**不是**网关 bug，是扩散模型按 32 对齐的常规做法。但它意味着
#   「请求比例 == 产出比例」这个断言对一半的比例天然不成立。
#
# 处理方式（三条一起用，缺一条闸门就会变成天天误报的噪音）：
#   a) 默认容差 3%：容差内不算「假」，但会**明确打印真实像素与偏差**，不藏
#   b) 超过容差 → 标红 + 计入闸门失败 + 退出码 3
#   c) `--snap`：出图后按请求比例精确裁掉多余像素，让产出真的等于请求比例；
#      裁剪结果再次读文件头复核，裁成功才记 exact
# ---------------------------------------------------------------------------

RATIO_TOLERANCE = 0.03        # 默认 3%（实测最大偏差 2.9%，留一点余量）

# 容差地板：**像素只能是整数**，所以「裁到精确比例」本身就有量化误差。
# 实测（--snap 之后复核）：2.35:1 @宽 864 → 高 368，偏差 0.0925%；
# 相邻整数像素间隔约 0.27%。所以用户把 --ratio-tolerance 调到比这还小时，
# 会把「本来就必须存在」的舍入误差判成不合格。0.0025 是保守地板，仍能抓住真错：
# 请求 3:4 却给 2:3 的偏差是 11%，比地板大 40 倍。
RATIO_TOLERANCE_FLOOR = 0.0025

# 提示词里出现过的示例文本。**新增示例必须登记到这里。**
# 这些是「跨主题」的假例子，正常不该出现在真实产出里（真实主题不会是这个）。
PROMPT_SAMPLES = [
    "一只黄色香蕉形状的蓝牙音箱，纯白背景，柔光棚拍，主体居中",
    "a yellow banana-shaped bluetooth speaker on a pure white background, soft studio light",
    "橙色渐变背景上一个白色圆形图标，极简扁平插画风，无文字",
]


# 比例换算（parse_ratio / ratio_label / image_size）都在 `imgprobe.py`：
# 那是本包自己的图片探针模块，a7w.py 保持逐字节等于规范版。
# 下面统一用 `imgprobe.` 前缀调用，方便一眼看出「真实像素是从哪来的」。
parse_ratio = imgprobe.parse_ratio
ratio_label = imgprobe.ratio_label


def check_ratio(path, want_ratio, tolerance=None):
    """闸门一：读真实像素，判是否等于请求比例。

    返回 dict（`ok` 为闸门结论）：
        real_px / real_label / real_ratio / want_ratio / deviation / ok
    """
    tol = RATIO_TOLERANCE if tolerance is None else float(tolerance)
    clamped = max(tol, RATIO_TOLERANCE_FLOOR)
    rec_floor = clamped > tol
    tol = clamped
    # ⚠️ 这里**只认文件头里的宽高**，不采信任何接口返回的自报字段。
    w, h, fmt = imgprobe.image_size(path)
    rec = {"file": str(path), "format": fmt, "real_px": [w, h],
           "want_ratio": want_ratio, "tolerance": tol,
           "tolerance_floor_applied": rec_floor,
           "real_label": ratio_label(w, h), "ok": False, "deviation": None}
    if not w or not h:
        rec["why"] = "读不出真实像素（可能不是图片、或被截断下载）"
        return rec
    want = parse_ratio(want_ratio)
    real = w / float(h)
    rec["real_ratio"] = round(real, 4)
    if not want:
        rec["why"] = "请求比例 %r 无法解析" % (want_ratio,)
        rec["deviation"] = abs(real - 1.0)
        return rec
    dev = abs(real - want) / want
    rec["deviation"] = round(dev, 5)
    rec["ok"] = dev <= tol
    if not rec["ok"]:
        rec["why"] = ("真实像素 %dx%d（%s = %.4f）与请求比例 %s（%.4f）偏差 %.2f%%，"
                      "超过容差 %.2f%%——上游没有按请求比例出图"
                      % (w, h, rec["real_label"], real, want_ratio, want,
                         dev * 100, tol * 100))
    else:
        rec["why"] = "真实像素 %dx%d（%s = %.4f），与请求比例偏差 %.2f%%，在容差内" % (
            w, h, rec["real_label"], real, dev * 100)
    return rec


# ---------------------------------------------------------------------------
# 可选：把产出精确裁到请求比例（--snap）
#
# 为什么值得做：上游按 32 对齐，3:4 实测给 864x1184（偏差 2.7%）。
# 自媒体平台对封面比例是有像素级要求的，差 2% 在 3:4 上就是 27 像素，
# 上传后会被平台二次裁切、位置不可控。与其让平台裁，不如本地裁准。
#
# 优先用 PIL；没有 PIL 时回落到内置的 8 位 PNG 裁剪器（只用 zlib + struct）。
# 两条路都走不通时**如实返回失败**，不做「假装裁过」。
# ---------------------------------------------------------------------------

def _try_pil_crop(src, dst, want_ratio):
    try:
        from PIL import Image  # noqa
    except ImportError:
        return None
    try:
        im = Image.open(src)
        w, h = im.size
        want = parse_ratio(want_ratio)
        if w / float(h) > want:          # 太宽 → 裁左右
            nw, nh = max(1, int(round(h * want))), h
        else:                            # 太高 → 裁上下
            nw, nh = w, max(1, int(round(w / want)))
        left, top = (w - nw) // 2, (h - nh) // 2
        im.crop((left, top, left + nw, top + nh)).save(dst)
        return "pil", (left, top, nw, nh)
    except Exception:
        return None


def _png_chunks(blob):
    pos = 8
    while pos + 8 <= len(blob):
        ln = struct.unpack(">I", blob[pos:pos + 4])[0]
        typ = blob[pos + 4:pos + 8]
        data = blob[pos + 8:pos + 8 + ln]
        yield typ, data
        pos += 12 + ln


def _unfilter(raw, stride, height, bpp):
    """还原 PNG 扫描线（只支持 bpp ∈ {3,4} 的 8 位真彩/真彩+alpha）。"""
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def _png_write(dst, w, h, bpp, rows):
    ctype = 6 if bpp == 4 else 2

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    blob = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))
    Path(dst).write_bytes(blob)


def _try_stdlib_png_crop(src, dst, want_ratio):
    """内置 8 位 PNG 裁剪（仅支持 color_type 2/6）。"""
    try:
        blob = Path(src).read_bytes()
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        idat, idepth, ctype = bytearray(), None, None
        for typ, data in _png_chunks(blob):
            if typ == b"IHDR":
                w, h, idepth, ctype = struct.unpack(">IIBB", data[:10])
            elif typ == b"IDAT":
                idat.extend(data)
            elif typ == b"IEND":
                break
        if idepth != 8 or ctype not in (2, 6):
            return None
        bpp = 3 if ctype == 2 else 4
        stride = w * bpp
        pixels = _unfilter(zlib.decompress(bytes(idat)), stride, h, bpp)
        want = parse_ratio(want_ratio)
        if w / float(h) > want:
            nw, nh = max(1, int(round(h * want))), h
        else:
            nw, nh = w, max(1, int(round(w / want)))
        left, top = (w - nw) // 2, (h - nh) // 2
        rows = []
        for y in range(top, top + nh):
            off = y * stride + left * bpp
            rows.append(pixels[off:off + nw * bpp])
        _png_write(dst, nw, nh, bpp, rows)
        return "stdlib-png", (left, top, nw, nh)
    except Exception:
        return None


def snap_to_ratio(src, dst, want_ratio):
    """把图片按请求比例居中裁剪到 dst。返回 (方式, 裁剪框) 或 None。"""
    for fn in (_try_pil_crop, _try_stdlib_png_crop):
        got = fn(src, dst, want_ratio)
        if got:
            return got
    return None


# ---------------------------------------------------------------------------
# 闸门三：违禁词（广告法 + 平台高压线）
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    (r"国家级|世界级|最高级|最佳|最优|最强|第一品牌|全国第一|排名第一|销量第一", "高",
     "广告法第九条绝对化用语，出图文字与提示词都不许带"),
    (r"最[好棒优佳强低价]|最便宜|最先进|最领先|顶级|极品|绝无仅有|独一无二", "高",
     "绝对化用语，无法举证"),
    (r"100%|百分之百|百分百|全网最低|绝对(有效|安全|可靠|不会)", "高",
     "绝对化承诺，属虚假宣传高风险表述"),
    (r"国家级|国家(认证|认可|免检)|央视(推荐|上榜)|官方(推荐|指定)|权威认证", "高",
     "虚构权威背书"),
    (r"根治|治愈|药到病除|包治|特效|无副作用|抗癌|降(血压|血糖|血脂)", "高",
     "医疗功效宣称，普通内容不得使用"),
    (r"稳赚|保本|保收益|零风险|躺赚|日入过万|月入百万|包过", "高",
     "投资/收益承诺，金融敏感表述"),
    (r"首[个创]|独家|唯一|填补空白", "中",
     "排他性表述，需有可举证依据"),
    (r"免费领|免费送|0\s*元购|白送|扫码(加|进|领)|加微信|私信我|vx|VX", "中",
     "诱导分享或站外导流，平台普遍限制"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天", "中",
     "促销时限表述需与真实活动一致"),
    (r"纯天然|无添加|零添加|无毒无害", "中",
     "成分/材质宣称需与检测报告一致"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看", "低",
     "标题党式诱导"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}


def compliance_scan(text):
    """扫违禁词，返回命中列表。"""
    hits = []
    for rx, lvl, why in BANNED_RE:
        m = rx.search(text or "")
        if m:
            hits.append({"word": m.group(0), "level": lvl, "why": why})
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits


# ---------------------------------------------------------------------------
# 闸门四：prompt_echo（照抄提示词示例）
#
# 事故复盘（来自标题工坊的实测）：提示词里写过的示例，
# 哪怕明确标着「这是错的写法」，模型照样照抄——公众号那一轮最高分 89.0 的标题
# **一字不差就是提示词里的示例**。最高分变成「抄标准答案」，排序就废了。
#
# 出图场景下这条更隐蔽：你不会一眼看出这张图和测试用例长得一样，
# 而是「看起来挺正常」，直到发现整套配图是同一个模子。所以必须是硬闸门。
#
# 判定：去标点后相等 → 命中；字符二元组 Jaccard ≥ 0.75 → 命中；
#       示例的二元组覆盖度 ≥ ECHO_CONTAIN → 命中（第三条，见下）。
# 阈值标定依据：标题工坊实测 196 条正常产出与跨主题示例的最高相似度只有 0.174，
# 而「少两个字的同构照抄」是 0.765。0.75 既能兜住轻改写，离正常上限还有 4 倍余量。
# 这里额外加一条**相对**长度守卫：目标归一化长度 < max(ECHO_MIN_LEN_FLOOR, len(示例)//2)
# 就不比相似度与覆盖度，因为短串的二元组集合太小、指标会虚高（比如两个都只有几个字）。
ECHO_MIN_LEN_FLOOR = 6


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)
#
# 【为什么还要第三条】出图提示词动辄 60~120 字，示例只有 25 字，Jaccard 的分母是
# 两份二元组的**并集**，示例那一侧被长提示词摊薄得极狠 —— 示例原样塞进去也照样放行。
# 本包实测（`_test_echo_contain.py`，示例1「一只黄色香蕉形状的蓝牙音箱，纯白背景，
# 柔光棚拍，主体居中」，去标点后 25 字 / 24 个二元组）：
#   · 示例原样嵌入 + 补 9 个字（34 字）→ Jaccard 24/33 = 0.727（旧判据放行 ❌）
#                                        覆盖度 24/24 = 1.000（新判据拦下 ✓）
#   · 示例原样嵌进一条 102 字的六段结构提示词
#     → Jaccard 0.245（漏）              覆盖度 1.000（抓住）
# 覆盖度只看"示例被抄了多少"，不看提示词有多长，摊薄对它无效。
# 阈值 0.60 的余量实测：17 条真实历史提示词里覆盖度最大只有 0.547
# （上游文档里那条与英文示例同源的句子），误伤 0 条，余量 1.1 倍。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _bigrams(s):
    s = _norm_for_echo(s)
    if len(s) < 2:
        return set(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _similarity(a, b):
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(len(ba | bb))


def prompt_echo(prompt, samples=None):
    """提示词是否与登记过的示例「抄得太近」。

    三条命中路径（任一即命中）：
      · 去标点后**完全相同**（最直接的照抄）
      · 字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
      · 示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（把示例夹带进更长的提示词里；
        Jaccard 会被长度摊薄，只有覆盖度抓得住，依据见常量区）

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"，
    没命中时后两项为 (0.0, "", "")。
    """
    target = _norm_for_echo(prompt)
    if not target:
        return False, 0.0, "", ""
    best_score, best_sample, best_rule = 0.0, "", ""
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        if target == _norm_for_echo(s):
            return True, 1.0, s, "exact"
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(prompt, s)
        base = _bigrams(s)
        contain = (len(_bigrams(prompt) & base) / float(len(base))) if base else 0.0
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        if contain >= ECHO_CONTAIN and contain >= best_score:
            best_score, best_sample, best_rule = contain, s, "contain"
    if best_rule:
        return True, best_score, best_sample, best_rule
    return False, best_score, best_sample, ""


def prompt_gate(prompt):
    """对一个出图提示词跑两道本地闸门，返回命中列表。"""
    leaks = []
    for h in compliance_scan(prompt):
        leaks.append(("banned_word", "命中违禁词「%s」（%s 风险）：%s"
                      % (h["word"], h["level"], h["why"])))
    for ch in "{}":
        if ch in (prompt or ""):
            leaks.append(("placeholder", "提示词里残留占位符 `%s`，模板没被替换干净" % ch))
            break
    echoed, score, sample, rule = prompt_echo(prompt)
    if echoed:
        if rule == "contain":
            leaks.append(("prompt_echo",
                          "提示词有 %.0f%% 的内容来自示例「%s」（覆盖度 ≥ %.2f 即判照抄／"
                          "同构改写；Jaccard 会随提示词变长被摊薄）"
                          % (score * 100, sample[:28], ECHO_CONTAIN)))
        else:
            leaks.append(("prompt_echo",
                          "提示词与示例「%s」相似度 %.2f，属照抄/同构改写"
                          "（模型会锚定提示词里的示例）" % (sample[:28], score)))
    return leaks


# ---------------------------------------------------------------------------
# 成本
# ---------------------------------------------------------------------------

def unit_points(resolution, override=None):
    """单张成本（点）。只有 1K 有实测价；2K/4K 不给默认值。"""
    if override is not None:
        return float(override)
    if (resolution or "1K").upper() == "1K":
        return float(POINTS_PER_IMAGE_1K)
    return None


def estimate_cost(count, resolution="1K", override=None):
    """返回预估成本 dict。拿不到可信单价时诚实返回 None 单价。"""
    pts = unit_points(resolution, override)
    rec = {"count": int(count), "resolution": resolution,
           "points_per_image": pts, "source": "override" if override is not None else "实测",
           "points_per_yuan": POINTS_PER_YUAN, "notes": []}
    if pts is None:
        rec["total_points"] = None
        rec["total_yuan"] = None
        rec["notes"].append(
            "%s 档没有实测单价，拒绝凭猜估算：请用 --points-per-image 指定单价后重算" % resolution)
        return rec
    if override is None and resolution.upper() in UNTESTED_RESOLUTIONS:
        rec["notes"].append("该档单价来自 --points-per-image，不是我们实测的数")
    rec["total_points"] = pts * rec["count"]
    rec["total_yuan"] = rec["total_points"] / float(POINTS_PER_YUAN)
    rec["notes"].append("按实测价 24 点/张（1K）计算；实际扣费以任务返回的 usage.points_cost 为准")
    rec["notes"].append("提交时会先冻结（实测 frozen_points=31.2），完成后按 24 点结算，"
                        "失败全额退回；只信 usage.points_cost")
    return rec


def fmt_cost(rec):
    if rec.get("total_points") is None:
        return "无法估算（%s）" % "；".join(rec.get("notes") or [])
    return "%d 张 × %g 点 = %g 点 = %.2f 元" % (
        rec["count"], rec["points_per_image"], rec["total_points"], rec["total_yuan"])


# ---------------------------------------------------------------------------
# 提示词：出配图方案
#
# 【铁律】提示词里不许出现任何一条可直接复制的完整出图提示词。
# 举例只用**登记在 PROMPT_SAMPLES 里的跨主题示例**（香蕉音箱、橙色圆形图标），
# 与真实业务主题明显不搭；万一将来有人把真实示例加进去，prompt_echo 闸门会兜住。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是三剪客团队的视觉编辑，负责给新媒体文章配图。\n"
    "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
    "你写的出图提示词必须能被真实使用：不编造文稿里没有的数据或事实，"
    "不使用广告法违禁词（最/第一/国家级/100%/根治/绝对 等一律不许出现），"
    "不要在图上要求生成文字（AI 出图的文字基本都是错的）。"
)


def platform_block(keys):
    lines = []
    for k in keys:
        pf = PLATFORMS[k]
        lines.append("- {key}（{name}）：设计比例 {dr}，实际生成比例 {gr}，"
                     "目标像素约 {px}。{note}".format(
                         key=k, name=pf["name"], dr=pf["design_ratio"],
                         gr=pf["gen_ratio"], px=pf["pixel_hint"], note=pf["note"]))
    return "\n".join(lines)


def build_plan_prompt(subject, platforms, count, article=None, style=None):
    roles = "\n".join("- {k}：{v}".format(k=k, v=v) for k, v in ROLE_NOTES.items())
    body = article.strip() if article else ""
    if len(body) > 6000:
        body = body[:6000] + "\n…（文稿过长，已截断到前 6000 字）"
    src = ("以下是文稿正文：\n\n" + body) if body else \
          ("没有给文稿，主题是：{}".format(subject))
    return """给下面的内容出一份**新媒体配图方案**，共 {count} 张。

{src}

要覆盖的平台：
{platforms}

每张图的 role 从下面这些里选，含义如下：
{roles}

出方案的口径：
- 第 1 张必须是 cover（封面）
- 每张图的 `prompt` 是**直接发给文生图模型的出图提示词**，用中文写，
  长度 40~120 字，必须具体：主体、动作/状态、构图与视角、背景、光线、色调、画风
- **不要在 prompt 里要求生成任何文字或标题**（AI 出图的文字必错，文字后期自己压）
- 不要编造文稿里没有的数字、人名、品牌、检测结论
- 同一套配图要视觉统一：{style}
- aspect_ratio 只能用这些值：auto / 1:1 / 16:9 / 9:16 / 4:3 / 3:4 / 3:2 / 2:3 / 5:4 / 4:5 / 21:9

只输出一个 JSON 对象，结构如下（不要输出别的任何东西）：
{{"items":[{{"id":1,"role":"cover","platform":"xiaohongshu","aspect_ratio":"3:4",
"resolution":"1K","prompt":"出图提示词原文","place":"放在文章哪里 + 一句话用途",
"alt":"给这张图配的图注，一句话"}}]}}""".format(
        count=count, src=src, platforms=platform_block(platforms), roles=roles,
        style=style or "同一组色板（建议 2 主色 + 1 点缀色）、同一种光线方向、同一种画风，"
                       "相邻两张的构图不要重复")


# 最近一次模型调用的 `finish_reason`。**必须记它**，且**初值不猜**（None）。
# 它是区分「该加大 --max-tokens」（=length）与「模型自己写错了 / 响应在路上断了」
# （stop / None）的**唯一**依据 —— 拿 content 长度去猜是错的：
# 同一端点实测在 2989 / 3898 / 3984 字符都能返回完整内容（finish_reason='stop'）。
_LAST_FINISH = {"reason": None, "chars": None}


def _fr_hint():
    """按 `_LAST_FINISH` 给出可执行的处置建议。只认 finish_reason，不认长度。"""
    fr = _LAST_FINISH.get("reason")
    if fr == "length":
        return ("；finish_reason=length —— 输出**确实**被 max_tokens 截断了，"
                "加大 --max-tokens 重试")
    return ("；finish_reason={!r}（**不是 length**）—— **加大 --max-tokens 没用**："
            "这是模型写错了或响应在路上断了，换模型或把这一稿拆段跑".format(fr))


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么要自带退避重试：网关的 upstream timeout / HTTP 502 实测很常见，
    一次抖动打断要重跑整批方案，很亏。5xx 与网络类错误退避重试；4xx 是业务错误，直接报。
    """
    import urllib.error
    import urllib.request
    key = a7w.load_key(key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + key,
               "Content-Type": "application/json", "Accept": "application/json"}

    last_exc = None
    payload = None
    for attempt in range(CHAT_RETRIES):
        req = urllib.request.Request(CHAT_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            break
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in (502, 503, 504) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("上游 {}，{}s 后重试 {}/{}…\n".format(
                    exc.code, 3 * (attempt + 1), attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
            try:
                err = json.loads(text)
            except ValueError:
                err = {}
            msg = err.get("msg") or err.get("error") or text[:200]
            if exc.code == 401:
                raise a7w.A7wError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise a7w.A7wError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise a7w.A7wError("模型不存在（404）：{}  用 `run.py models` 现查在架模型。".format(msg))
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise a7w.A7wError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    if payload is None:
        raise a7w.A7wError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise a7w.A7wError("模型没返回 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    finish_reason = (choices[0] or {}).get("finish_reason")
    _LAST_FINISH["reason"] = finish_reason
    _LAST_FINISH["chars"] = len(content)
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    return content, usage


def parse_first_json(text):
    """从模型输出里抠出第一个完整 JSON。

    为什么要这么写：模型经常在合法 JSON 后面多吐字符（```、解释、第二个对象），
    直接 json.loads 会炸。用 raw_decode 从每个 { / [ 位置试解码。
    """
    if not text:
        raise a7w.A7wError("模型返回空内容")
    dec = json.JSONDecoder()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = [fenced.group(1).strip()] if fenced else []
    candidates.append(text)
    for cand in candidates:
        # ⚠️ 第一优先：按**括号配平**取最外层那个完整值，再解析。
        # 否则外层坏了时会从嵌套结构里解出一个**内层**对象交出去，
        # 上层报的错就指向了错误的方向（这一条是同族实测踩出来的）。
        start = None
        for i, ch in enumerate(cand):
            if ch in "{[":
                start = i
                break
        if start is not None:
            depth, in_str, esc, end = 0, False, False, None
            for i in range(start, len(cand)):
                ch = cand[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch in "{[":
                    depth += 1
                elif ch in "}]":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end is not None:
                try:
                    obj = json.loads(cand[start:end])
                    if isinstance(obj, (dict, list)):
                        return obj
                except ValueError:
                    pass
        for i, ch in enumerate(cand):
            if ch not in "{[":
                continue
            try:
                obj, _ = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    raise a7w.A7wError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


def normalize_plan(obj, platforms, count):
    """把模型产出收拾成内部结构：补齐比例、限制张数、跑本地闸门。"""
    items = obj.get("items") if isinstance(obj, dict) else obj
    if not isinstance(items, list):
        raise a7w.A7wError("方案里没有 items 列表：%s" % json.dumps(obj, ensure_ascii=False)[:200])
    out = []
    for i, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            continue
        platform = str(raw.get("platform") or platforms[0]).strip()
        if platform not in PLATFORMS:
            platform = platforms[0]
        pf = PLATFORMS[platform]
        ar = str(raw.get("aspect_ratio") or pf["gen_ratio"]).strip()
        if ar not in ASPECT_RATIOS:
            ar = pf["gen_ratio"]
        prompt = re.sub(r"\s+", " ", str(raw.get("prompt") or "")).strip()
        role = str(raw.get("role") or ("cover" if i == 1 else "inline")).strip()
        out.append({
            "id": int(raw.get("id") or i),
            "role": role,
            "platform": platform,
            "platform_name": pf["name"],
            "design_ratio": pf["design_ratio"],
            "aspect_ratio": ar,
            "resolution": str(raw.get("resolution") or "1K").strip().upper(),
            "prompt": prompt,
            "place": str(raw.get("place") or "").strip(),
            "alt": str(raw.get("alt") or "").strip(),
            "leaks": prompt_gate(prompt),
        })
    if count and len(out) > count:
        out = out[:count]
    return out


# ---------------------------------------------------------------------------
# 断点续跑
#
# 出图是**异步 + 按次扣费**的：一次抖动、一次 Ctrl+C，都会让「已经提交并冻结了点数」
# 的任务悬在那里。如果没有断点记录，重跑会把同一张图再买一遍。
#
# 所以每张图提交前先落一条 pending（带 task_id），完成后再写 completed + points_cost。
# 重跑时：
#   · completed 的项直接跳过，并把上次的真实扣费累计进来（不再花钱）
#   · pending 的项用 task_id 去**续查**，而不是重新提交（这正是省钱的那一步）
#   · key = 提示词 + 比例 + 分辨率 + 模型的哈希，改了提示词就是新的一项，天然重出
# ---------------------------------------------------------------------------

def state_key(item):
    payload = "|".join([item["prompt"], item["aspect_ratio"], item["resolution"],
                        item.get("model") or "nano-banana"])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def load_state(path):
    p = Path(path)
    if not p.is_file():
        return {"version": 1, "items": {}}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or "items" not in obj:
            return {"version": 1, "items": {}}
        return obj
    except (OSError, ValueError):
        sys.stderr.write("⚠ 断点文件读不动（%s），按空处理——注意这会导致重出图\n" % path)
        return {"version": 1, "items": {}}


def save_state(path, state):
    p = Path(path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "!! " + s
    return "\033[31m" + s + "\033[0m"


def _load_article(a):
    """文稿来源：--article 文件 / --topic 主题 / 位置参数。"""
    parts = []
    for f in (a.files or []):
        p = Path(f)
        if not p.is_file():
            raise a7w.A7wError("找不到文稿文件：%s" % f)
        parts.append(p.read_text(encoding="utf-8", errors="replace"))
    if a.article:
        p = Path(a.article)
        if not p.is_file():
            raise a7w.A7wError("找不到文稿文件：%s" % a.article)
        parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n\n".join(parts).strip() or None


def _resolve_platforms(names):
    out = []
    for n in names or ["xiaohongshu"]:
        key = str(n).strip()
        if key not in PLATFORMS:
            raise a7w.A7wError("未知平台 %r；可选：%s" % (key, " / ".join(PLATFORMS)))
        if key not in out:
            out.append(key)
    return out


def cmd_plan(a):
    platforms = _resolve_platforms(a.platform)
    article = _load_article(a)
    subject = a.topic or (article[:60].replace("\n", " ") if article else "")
    if not subject:
        raise a7w.A7wError("请用 --topic 给主题，或用 --article <文稿文件> / 位置参数给文稿")
    prompt = build_plan_prompt(subject, platforms, a.count, article, a.style)
    if a.dry_run:
        # --json 时 stdout 必须是**单个完整 JSON**，所以 dry-run 也包成 JSON
        if a.json:
            _json_out({"dry_run": True, "system": SYSTEM_PROMPT, "user": prompt}, a, indent=1)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (SYSTEM_PROMPT, prompt))
        return 0
    sys.stderr.write("正在用 `%s` 出 %d 张图的配图方案…\n" % (a.model, a.count))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    items = normalize_plan(parse_first_json(content), platforms, a.count)
    if not items:
        raise a7w.A7wError("模型没产出任何配图条目")
    plan = {"subject": subject, "platforms": platforms, "count": len(items),
            "model": a.model, "usage": usage, "elapsed_sec": round(elapsed, 1),
            "style": a.style, "items": items}
    if a.out:
        Path(a.out).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        _json_out(plan, a, indent=1)
    else:
        _render_plan(plan)
    cost = estimate_cost(len(items), items[0]["resolution"], a.points_per_image)
    # --json 时 stdout 必须是**单个完整 JSON**：人读的报价说明改走 stderr
    if a.json:
        sys.stderr.write("\n预估出图成本（这一步还没出图，只花了文本钱）：\n  %s\n"
                         % fmt_cost(cost))
    else:
        print("\n预估出图成本（这一步还没出图，只花了文本钱）：")
        print("  " + fmt_cost(cost))
    if a.out and not a.json:
        sys.stderr.write("方案已写入 %s\n" % a.out)
    return 3 if any(it["leaks"] for it in items) else 0


def _render_plan(plan):
    print("配图方案：%s" % plan["subject"])
    print("平台：%s   共 %d 张   模型：%s   耗时 %.1fs"
          % ("、".join(PLATFORMS[p]["name"] for p in plan["platforms"]),
             plan["count"], plan["model"], plan["elapsed_sec"]))
    print()
    for it in plan["items"]:
        head = "#%-3d %-8s %-6s %-5s %s" % (it["id"], it["role"],
                                            it["aspect_ratio"], it["resolution"],
                                            it["platform_name"])
        print(head)
        print("     出图提示词：%s" % it["prompt"])
        if it["place"]:
            print("     位置/用途：%s" % it["place"])
        if it["alt"]:
            print("     图注：%s" % it["alt"])
        for kind, why in it["leaks"]:
            print("     " + _red("✗ %s：%s" % (kind, why)))
    hits = [it for it in plan["items"] if it["leaks"]]
    if hits:
        sys.stderr.write("\n!! %d 张图的提示词命中本地闸门（违禁词 / prompt_echo / 占位符），"
                         "改掉后再出图\n" % len(hits))


def cmd_cost(a):
    rec = estimate_cost(a.count, a.resolution, a.points_per_image)
    # 先定结论：估不出价、超预算都算「不放行」。发出的 JSON 里的 ok 必须与退出码一致，
    # 所以这里先算 rc，再带着 ok 输出。
    no_price = rec.get("total_points") is None
    over = (a.budget is not None and rec.get("total_points") is not None
            and rec["total_points"] > a.budget)
    if no_price:
        rc = _fail(3, "budget", "拿不到该档的可信单价，拒绝凭猜估算")
    elif over:
        rc = _fail(3, "budget", "预估成本 %g 点超过 --budget 上限 %g 点"
                    % (rec["total_points"], a.budget))
    else:
        rc = 0
    if a.json:
        _json_out(rec, a, indent=1, ok=not rc)
    else:
        print("预估成本：%s" % fmt_cost(rec))
        for n in rec.get("notes") or []:
            print("  · %s" % n)
        if a.budget is not None and rec.get("total_points") is not None:
            print("  · 预算 %g 点：%s" % (a.budget, "超了，gen 会被拦下" if over else "在预算内"))
    # 估不出价也是「闸门不放行」：拿不到可信单价就往流水线里放行，等于没有成本前置。
    if no_price:
        sys.stderr.write("!! 拿不到该档的可信单价，无法完成成本前置检查\n")
    return rc


def cmd_models(a):
    import urllib.request
    import urllib.error
    key = a7w.load_key(a.key)
    out = {}
    for label, url, pick in (
            ("apps", a7w.HOST + "/api/v1/apps", None),
            ("models", a7w.HOST + "/api/v1/models", None)):
        try:
            data = a7w._unwrap(a7w._request("GET", url, key))
        except (a7w.A7wError, urllib.error.URLError) as exc:
            sys.stderr.write("取 %s 失败：%s\n" % (url, exc))
            out[label] = []
            continue
        lst = data.get("list") if isinstance(data, dict) and "list" in data else data
        out[label] = lst if isinstance(lst, list) else []
    if a.json:
        _json_out(out, a, indent=1)
        return 0
    apps = out.get("apps") or []
    print("在架应用 %d 个：" % len(apps))
    for x in apps:
        if not isinstance(x, dict):
            continue
        n = len(x.get("apis") or [])
        mark = "  ← 本包用这个" if x.get("code") == APP_IMAGE else ""
        print("  %-22s %-22s %2d 接口%s" % (x.get("code"), x.get("name"), n, mark))
    models = out.get("models") or []
    kinds = {}
    for m in models:
        if isinstance(m, dict):
            kinds.setdefault(m.get("type_code") or "-", []).append(
                m.get("model_code") or m.get("id"))
    print("\n在架模型 %d 个，按类型：" % len(models))
    for k in sorted(kinds):
        print("  %-12s %2d 个   %s" % (k, len(kinds[k]), "、".join(kinds[k][:6])
                                       + ("…" if len(kinds[k]) > 6 else "")))
    print("\n出图应用 nano_banana 的可选模型（来自 submit 的 schema）：")
    for m in IMAGE_MODELS:
        print("  %s" % m)
    print("\n注意：平台文档里的价格字段（pricing_matrix / tenant_*）我们验证过半数不可信，")
    print("     结算价只认任务返回的 usage.points_cost。")
    return 0


def _print_gen_plan(items, outdir, resolution, override):
    print("将要出图：%d 张" % len(items))
    for it in items:
        print("  #%-3d %-8s %-8s %-5s %-6s %s" % (
            it["id"], it["role"], it["platform_name"], it["aspect_ratio"],
            it["resolution"], it["prompt"][:44] + ("…" if len(it["prompt"]) > 44 else "")))
    print("  输出目录：%s  （**必须不在 Skill 包内**）" % outdir)
    print("  单张成本：%s" % ("%g 点" % unit_points(resolution, override)
                              if unit_points(resolution, override) is not None
                              else "未知（%s 档无实测价）" % resolution))


def cmd_gen(a):
    """入口：`--json` 时把人读输出（报价、进度、逐张结果）整体导向 stderr。

    这样 stdout 里只剩一个完整 JSON，`json.loads` 才能直接用。
    实现方式是把原函数体整体搬进 `_cmd_gen_impl`，由这里临时换掉 `sys.stdout`，
    最后用**真正的** stdout 写结果。
    """
    out_raw = sys.stdout
    if getattr(a, "json", False):
        sys.stdout = sys.stderr
    try:
        return _cmd_gen_impl(a, out_raw)
    finally:
        sys.stdout = out_raw


def _cmd_gen_impl(a, out_raw):
    plan_path = Path(a.plan)
    if not plan_path.is_file():
        raise a7w.A7wError("找不到方案文件：%s（先用 `plan` 生成）" % a.plan)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # 手改坏了 / 不是本包产出的文件：这是输入错，不该崩成 exit 1 + stdout 空
        raise a7w.A7wError("方案文件读不动或不是合法 JSON：%s（%s）"
                           % (a.plan, exc))
    items = plan.get("items") or []
    if not items:
        raise a7w.A7wError("方案文件里没有 items：%s" % a.plan)
    # 顺序很重要：**先按平台筛，再截断**。
    # 反过来的话 `--platform wechat --count 1` 会先把方案截成第 1 条（小红书），
    # 再筛 wechat → 一条不剩，看着像「方案里没有公众号图」。
    platforms = [str(x) for x in (a.platform or [])]
    if platforms:
        items = [it for it in items if it.get("platform") in platforms]
        if not items:
            raise a7w.A7wError("按 --platform %s 过滤后没有条目" % "、".join(platforms))
    if a.count:
        items = items[:a.count]
    if a.resolution:
        for it in items:
            it["resolution"] = a.resolution.upper()
    for it in items:
        it.setdefault("resolution", "1K")
        it.setdefault("model", a.model)

    # 闸门三/四：出图前把提示词再扫一遍（方案文件可能是手改过的）
    blocked = []
    for it in items:
        it["leaks"] = it.get("leaks") or prompt_gate(it["prompt"])
        if it["leaks"]:
            blocked.append(it)
    if blocked and not a.allow_prompt_hits:
        for it in blocked:
            sys.stderr.write("!! #%s 出图提示词命中闸门：\n" % it["id"])
            for kind, why in it["leaks"]:
                sys.stderr.write("     %s\n" % _red("%s：%s" % (kind, why)))
        sys.stderr.write(
            "\n共 %d 张被判不合格，**已拦截，未提交任何任务**（不花一分钱）。\n"
            "改掉提示词后重跑；确实要带违禁词出图才加 --allow-prompt-hits。\n" % len(blocked))
        return _fail(3, "gate", "有出图提示词命中本地闸门，已拦截、未提交任何任务")

    outdir = Path(a.outdir).resolve()
    pkg_dir = Path(__file__).resolve().parent.parent
    try:
        outdir.relative_to(pkg_dir)
        raise a7w.A7wError(
            "输出目录 %s 在 Skill 包内。包内不许有任何图片（上传白名单只收文本），"
            "请换到包外，例如 %s" % (outdir,
                                     Path(os.environ.get("TEMP") or ".") / "image-factory-out"))
    except ValueError:
        pass
    outdir.mkdir(parents=True, exist_ok=True)
    state_path = a.state or str(outdir / STATE_NAME)
    state = load_state(state_path)

    resolution = items[0]["resolution"]
    cost = estimate_cost(len(items), resolution, a.points_per_image)
    _print_gen_plan(items, outdir, resolution, a.points_per_image)
    print("\n预估成本：%s" % fmt_cost(cost))
    for n in cost.get("notes") or []:
        print("  · %s" % n)

    # 闸门二：成本上限。**在提交任何任务之前**判，超了直接停。
    if cost.get("total_points") is None:
        sys.stderr.write("\n!! 没有 %s 档的可信单价，拒绝盲跑。"
                         "用 --points-per-image <点数> 指定单价后重试。\n" % resolution)
        return _fail(3, "budget", "%s 档没有实测单价，拒绝凭猜估算" % resolution)
    if a.budget is not None and cost["total_points"] > a.budget:
        sys.stderr.write("\n!! 预估 %g 点超过预算上限 %g 点，**已中断，未提交任何任务**。\n"
                         % (cost["total_points"], a.budget))
        return _fail(3, "budget", "预估 %g 点超过 --budget 上限 %g 点，未提交任何任务"
                     % (cost["total_points"], a.budget))
    if a.budget is not None:
        print("  预算 %g 点：在预算内" % a.budget)

    if not a.yes:
        sys.stderr.write("\n这是一次**真花钱**的操作（约 %.2f 元）。确认后加 --yes 重跑。\n"
                         % (cost["total_yuan"] or 0))
        return _fail(4, "usage", "这是一次真花钱的操作，确认后加 --yes 重跑")

    total_points = 0.0
    spent_this_run = 0.0
    done, skipped, failed, ratio_bad = [], [], [], []
    run_deadline = time.time() + a.max_seconds if a.max_seconds else None

    for n, it in enumerate(items, 1):
        key = state_key(it)
        prev = state["items"].get(key)
        if prev and prev.get("status") == "completed" and not a.force:
            pts = prev.get("points_cost")
            total_points += float(pts or 0)
            skipped.append((it, prev))
            print("[%d/%d] #%s 已完成，跳过（上次扣费 %s 点，不再重复扣）"
                  % (n, len(items), it["id"], pts))
            continue
        if run_deadline and time.time() > run_deadline:
            sys.stderr.write("\n!! 达到 --max-seconds 上限，中断。已完成的都在断点文件里，"
                             "直接重跑即可续（不会重复扣费）。\n")
            save_state(state_path, state)
            return _fail(5, "interrupt", "达到 --max-seconds 上限，已中断（可续跑）")

        task_id = (prev or {}).get("task_id") if prev else None
        if task_id and prev.get("status") == "pending" and not a.force:
            # 续查上一轮已经提交（点数已冻结）的任务，而不是重新提交
            print("[%d/%d] #%s 发现未完成的 task_id=%s，续查而不重新提交"
                  % (n, len(items), it["id"], task_id))
        else:
            # 逐张再核一次预算：前面的真实扣费可能比预估高，
            # 超过 --budget 就地停，别再往下买（预估闸门只能保证「开头不超」）。
            if a.budget is not None:
                spent_so_far = total_points + (cost["points_per_image"] or 0)
                if spent_so_far > a.budget:
                    sys.stderr.write(
                        "\n!! 已花/待花 %g 点将超过预算 %g 点，**就此停下**（不再提交新任务）。\n"
                        "   已完成的图与断点都在 %s。\n" % (spent_so_far, a.budget, state_path))
                    save_state(state_path, state)
                    return _fail(3, "budget",
                                 "已花/待花 %g 点将超过 --budget %g 点，就此停下"
                                 % (spent_so_far, a.budget))
            sys.stderr.write("[%d/%d] #%s 提交：aspect_ratio=%s resolution=%s model=%s\n"
                             % (n, len(items), it["id"], it["aspect_ratio"],
                                it["resolution"], it.get("model") or "nano-banana"))
            try:
                data = submit_image(it["prompt"], aspect_ratio=it["aspect_ratio"],
                                        resolution=it["resolution"],
                                        model=it.get("model") or "nano-banana",
                                        key=a.key)
            except a7w.A7wError as exc:
                sys.stderr.write("    提交失败：%s\n" % exc)
                failed.append({"id": it["id"], "stage": "submit", "error": str(exc)})
                if a.stop_on_error:
                    save_state(state_path, state)
                    return _fail(2, "call", "一张失败就整体停（--stop-on-error）")
                continue
            task_id = data.get("task_id")
            state["items"][key] = {
                "id": it["id"], "role": it["role"], "platform": it["platform"],
                "prompt": it["prompt"], "aspect_ratio": it["aspect_ratio"],
                "resolution": it["resolution"], "model": it.get("model"),
                "task_id": task_id, "status": "pending",
                "frozen_points": data.get("frozen_points"),
                "request": {"prompt": it["prompt"], "action": "generate",
                            "resolution": it["resolution"],
                            "aspect_ratio": it["aspect_ratio"],
                            "model": it.get("model")},
                "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            save_state(state_path, state)      # 先落盘：崩了也能续查这个 task_id

        if a.no_wait:
            continue

        def on_tick(status, data, _key=key):
            state["items"][_key]["last_status"] = status
            save_state(state_path, state)

        try:
            status, data, payload, ticks = poll_task(
                task_id, key=a.key, timeout=a.poll_timeout, interval=a.poll_interval,
                on_tick=on_tick)
        except a7w.A7wError as exc:
            sys.stderr.write("    轮询失败：%s（task_id=%s 可用 `a7w.py task` 续查）\n"
                             % (exc, task_id))
            failed.append({"id": it["id"], "stage": "poll", "task_id": task_id,
                           "error": str(exc)})
            if a.stop_on_error:
                save_state(state_path, state)
                return _fail(2, "call", "一张失败就整体停（--stop-on-error）")
            continue

        rec = state["items"][key]
        rec["last_status"] = status
        rec["raw_task"] = payload
        if status != "completed":
            err = data.get("error") or (data.get("result") or {}).get("error") or ""
            sys.stderr.write("    任务未成功：%s  %s\n" % (status, err))
            rec["status"] = "failed"
            rec["error"] = "%s %s" % (status, err)
            save_state(state_path, state)
            failed.append({"id": it["id"], "stage": "task", "task_id": task_id,
                           "error": rec["error"], "raw_task": payload})
            if a.stop_on_error:
                return _fail(2, "call", "一张失败就整体停（--stop-on-error）")
            continue

        pts = points_cost(data)
        rec["points_cost"] = pts
        if pts:
            total_points += float(pts)
            spent_this_run += float(pts)

        urls = find_image_urls(data)
        if not urls:
            rec["status"] = "failed"
            rec["error"] = "任务完成但没找到图片地址"
            save_state(state_path, state)
            failed.append({"id": it["id"], "stage": "no_url", "task_id": task_id,
                           "raw_task": payload})
            continue

        url = urls[0]
        dest = outdir / ("%s-%s-%s-%s%s" % (it["id"], it["platform"],
                                            it["aspect_ratio"].replace(":", "x"),
                                            key, OUT_EXT))
        try:
            a7w.save(url, str(dest))
        except a7w.A7wError as exc:
            rec["status"] = "failed"
            rec["error"] = "下载失败：%s" % exc
            rec["image_url"] = url
            save_state(state_path, state)
            failed.append({"id": it["id"], "stage": "download", "task_id": task_id,
                           "error": str(exc), "image_url": url})
            continue

        want = PLATFORMS[it["platform"]]["design_ratio"] if a.snap_on_design \
            else it["aspect_ratio"]
        check = check_ratio(str(dest), want, a.ratio_tolerance)
        # 保留**裁剪前**的原始判定。这份证据很重要：它记录了上游真实给了什么像素，
        # 裁过之后就不该再拿 `raw_ratio_check` 冒充「上游原始产出」。
        first_check = dict(check)
        rec["image_url"] = url
        rec["file"] = str(dest)
        rec["first_check"] = first_check
        rec["real_px"] = check["real_px"]
        rec["real_ratio"] = check.get("real_ratio")
        rec["want_ratio"] = want
        rec["ratio_deviation"] = check["deviation"]

        if a.snap and not check["ok"]:
            snapped = str(dest.with_name(dest.stem + "-snapped" + dest.suffix))
            got = snap_to_ratio(str(dest), snapped, want)
            if got:
                way, box = got
                after = check_ratio(snapped, want, a.ratio_tolerance)
                rec["snap"] = {"method": way, "box": box, "file": snapped,
                               "after": after}
                if after["ok"]:
                    dest = Path(snapped)
                    check = after
                    rec["real_px"] = after["real_px"]
                    rec["real_ratio"] = after.get("real_ratio")
                    rec["ratio_deviation"] = after["deviation"]
                    rec["file"] = str(snapped)
            else:
                rec["snap"] = {"method": None,
                               "why": "没有 PIL，内置裁剪器也不支持这个 PNG（需 8 位真彩/真彩+alpha）"}
        rec["raw_ratio_check"] = check

        rec["ratio_ok"] = bool(check["ok"])
        rec["status"] = "completed"
        save_state(state_path, state)
        if check["ok"]:
            done.append((it, rec))
            print("    完成 真实像素 %sx%s  比例 %s  扣费 %s 点  → %s"
                  % (check["real_px"][0], check["real_px"][1],
                     check.get("real_label"), pts, rec["file"]))
        else:
            ratio_bad.append((it, rec))
            print("    " + _red("完成但比例不合格：%s" % check.get("why")))
            print("    " + _red("  → %s" % rec["file"]))

    # ------------------------------------------------------------------
    # 收尾
    # ------------------------------------------------------------------
    summary = {
        "plan": str(plan_path), "outdir": str(outdir), "state": state_path,
        "planned_images": len(items),
        "completed": [{"id": it["id"], "task_id": r.get("task_id"),
                       "file": r.get("file"), "real_px": r.get("real_px"),
                       "want_ratio": r.get("want_ratio"),
                       "real_ratio": r.get("real_ratio"),
                       "deviation": r.get("ratio_deviation"),
                       "points_cost": r.get("points_cost"),
                       "image_url": r.get("image_url"),
                       "request": r.get("request"),
                       # 上游给的原始像素与判定（裁剪前的证据，别被裁后结果覆盖）
                       "first_check": r.get("first_check"),
                       # 裁剪记录：方式、裁剪框、裁后复核。没裁就是 null
                       "snap": r.get("snap"),
                       "raw_task": r.get("raw_task")}
                      for it, r in done],
        "skipped_already_done": [{"id": it["id"], "task_id": r.get("task_id"),
                                  "file": r.get("file"), "points_cost": r.get("points_cost"),
                                  "real_px": r.get("real_px")}
                                 for it, r in skipped],
        "ratio_failed": [{"id": it["id"], "file": r.get("file"),
                          "real_px": r.get("real_px"), "want_ratio": it["aspect_ratio"],
                          "why": (r.get("raw_ratio_check") or {}).get("why")}
                         for it, r in ratio_bad],
        "failed": failed,
        "points_cost_total": total_points,
        "points_cost_this_run": spent_this_run,
        "yuan_this_run": round(spent_this_run / float(POINTS_PER_YUAN), 3),
        "estimate": cost,
    }
    if a.json:
        # 结果写到**真正的** stdout（本函数里 sys.stdout 已经被换成了 stderr）；
        # ok 如实反映"这一批是否全绿"：有失败或比例不合格就是 false，退出码照旧
        _json_write(_json_text(summary, indent=1, ok=not (failed or ratio_bad)))
    else:
        print("\n=== 出图小结 ===")
        print("  本次真花钱：%g 点 = %.2f 元（预估 %s）"
              % (spent_this_run, spent_this_run / float(POINTS_PER_YUAN),
                 cost["total_points"]))
        print("  成功 %d 张 / 跳过（已完成）%d 张 / 比例不合格 %d 张 / 失败 %d 张"
              % (len(done), len(skipped), len(ratio_bad), len(failed)))
        print("  断点文件：%s（重跑直接续，不会重复扣费）" % state_path)
        for it, r in ratio_bad:
            print("  " + _red("✗ #%s 比例不合格：真实 %sx%s 请求 %s"
                              % (it["id"], r["real_px"][0], r["real_px"][1],
                                 it["aspect_ratio"])))
        for f in failed:
            print("  " + _red("✗ #%s %s 失败：%s" % (f["id"], f["stage"], f["error"])))
    if a.report:
        Path(a.report).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        sys.stderr.write("证据报告已写入 %s\n" % a.report)

    if failed:
        return _fail(2, "call", "%d 张出图失败（明细见 stderr）" % len(failed))
    if ratio_bad:
        return _fail(3, "gate", "%d 张真实比例与请求不符" % len(ratio_bad))
    return 0


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封（已经吐过结果的，ok 写在那个结果里）
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#
# 信封必须落在**真 stdout**：本包的 cmd_gen 会在执行期间把 sys.stdout 临时换成 stderr，
# 所以 JSON 文本统一经 `_json_write` 写到进 main() 时记住的那份真 stdout。
# ---------------------------------------------------------------------------

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}

# 退出码 → 失败类别（与 SKILL.md 里公示的退出码表一致）
_KIND_BY_EXIT = {2: "call", 3: "gate", 4: "usage", 5: "interrupt", 130: "interrupt"}


def _json_payload(obj, ok=True):
    """结果对象补 ok；顶层是数组时包成 {"ok": …, "data": […] }。"""
    if isinstance(obj, dict):
        out = {"ok": bool(ok)}
        out.update(obj)
        return out
    return {"ok": bool(ok), "data": obj}


def _json_text(obj, indent=1, ok=True):
    return json.dumps(_json_payload(obj, ok), ensure_ascii=False, indent=indent)


def _json_write(text):
    """把 JSON 文本写到**真 stdout** 并记账（绕开 cmd_gen 里的 stdout 重定向）。"""
    (_JSON["stdout"] or sys.stdout).write(text + "\n")
    _JSON["emitted"] = True


def _json_want(a=None):
    if a is not None:
        return bool(getattr(a, "json", False))
    return bool(_JSON["want"])


def _json_out(obj, a=None, indent=1, ok=True):
    """`--json` 模式的成功出口。返回是否已输出。"""
    if not _json_want(a):
        return False
    _json_write(_json_text(obj, indent=indent, ok=ok))
    return True


def _json_fail(rc, kind=None, message=None, detail=None, a=None):
    """`--json` 模式的失败出口：只在本次还没输出过 JSON 结果时补信封。"""
    if _JSON["emitted"] or not _json_want(a):
        return
    err = {"kind": kind or _KIND_BY_EXIT.get(rc, "call"),
           "message": message or "命令以退出码 %s 结束（人读原因见 stderr）" % rc}
    if detail is not None:
        err["detail"] = detail
    _json_write(json.dumps({"ok": False, "exit": rc, "error": err},
                           ensure_ascii=False, indent=1))


def _json_internal(exc):
    """未预料异常的兜底信封 —— **报 bug，不藏 bug**。

    只写 stdout（真 stdout）；完整 traceback 由 main() 的兜底层原样打到 stderr，
    这里不重复、也不吞。`detail.where` 只取**最后一帧**的文件名:行号，整条栈不进 JSON。
    如果本次已经吐过结果，就**不再补信封**（守住"stdout 永远只有一个 JSON"这条不变量）。
    """
    if _JSON["emitted"]:
        return
    tb = sys.exc_info()[2]
    frames = traceback.extract_tb(tb) if tb else []
    detail = {"type": type(exc).__name__}
    if frames:
        last = frames[-1]
        detail["where"] = "%s:%d" % (os.path.basename(last.filename), last.lineno)
    err = {"kind": "internal",
           "message": "%s: %s" % (type(exc).__name__, exc),
           "detail": detail}
    _json_write(json.dumps({"ok": False, "exit": 1, "error": err},
                           ensure_ascii=False, indent=1))


def _fail(rc, kind, message, detail=None):
    """命令函数决定失败时调它：记下原因，返回原退出码（退出码语义不变）。"""
    if _JSON["reason"] is None:
        _JSON["reason"] = {"kind": kind, "message": message, "detail": detail}
    return rc


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与 sanjianke-portrait-studio 同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py plan --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 新媒体配图工厂：给文稿/主题出一整套配图，跑之前先告诉你花多少钱",
        allow_abbrev=False)
    ap.add_argument("--key", help="临时指定 api.a7w.cn 的 Key（别写进脚本或文档）")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --- plan ---
    p = sub.add_parser("plan", help="出配图方案（只花文本钱）", allow_abbrev=False)
    _add_json(p)
    p.add_argument("files", nargs="*", help="文稿文件（可多份）")
    p.add_argument("--topic", help="没文稿时给一个主题")
    p.add_argument("--article", help="文稿文件路径")
    p.add_argument("--platform", action="append",
                   choices=list(PLATFORMS), help="目标平台，可重复；默认 xiaohongshu")
    p.add_argument("--count", type=int, default=8, help="要几张图，默认 8")
    p.add_argument("--style", help="视觉风格统一口径（会给到模型）")
    p.add_argument("--model", default=DEFAULT_MODEL, help="文本模型，默认 %s" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--out", help="把方案写到这个 JSON 文件（gen 要用它）")
    p.add_argument("--dry-run", action="store_true", help="只打印提示词，不调模型、不花钱")
    p.add_argument("--no-json-mode", action="store_true", help="不要求上游返回 JSON 对象")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.set_defaults(func=cmd_plan)

    # --- cost ---
    p = sub.add_parser("cost", help="只算钱不出图", allow_abbrev=False)
    _add_json(p)
    p.add_argument("--count", type=int, required=True, help="要出几张")
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--budget", type=float, help="预算上限（点），超了退出码非 0")
    p.set_defaults(func=cmd_cost)

    # --- models ---
    p = sub.add_parser("models", help="列出在架应用与模型", allow_abbrev=False)
    _add_json(p)
    p.set_defaults(func=cmd_models)

    # --- gen ---
    p = sub.add_parser("gen", help="按方案批量出图（真花钱，先报价再确认）", allow_abbrev=False)
    _add_json(p)
    p.add_argument("--plan", required=True, help="plan 产出的方案 JSON")
    p.add_argument("--platform", action="append", choices=list(PLATFORMS),
                   help="只出某平台的比例 preset，可重复")
    p.add_argument("--resolution", choices=list(RESOLUTIONS), help="覆盖分辨率")
    p.add_argument("--count", type=int, help="最多出几张（截断方案）")
    p.add_argument("--model", default="nano-banana", help="出图模型，默认 nano-banana")
    p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".") / "image-factory-out"),
                   help="图片输出目录（**必须在 Skill 包外**）")
    p.add_argument("--state", help="断点文件路径，默认 <outdir>/%s" % STATE_NAME)
    p.add_argument("--budget", type=float, help="成本上限（点）：超了直接停，不提交")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--yes", action="store_true", help="确认真的花钱（不加就只报价）")
    p.add_argument("--snap", action="store_true",
                   help="出图后按请求比例精确裁剪（上游按 32 对齐，5/10 种比例拿不到精确比例）")
    p.add_argument("--snap-on-design", action="store_true",
                   help="按平台设计比例裁（如公众号 2.35:1），而不是按生成比例")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   help="比例容差，默认 %.3f（实测最大偏差 2.9 个百分点）" % RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT,
                   help="单张轮询超时秒数，默认 %g" % POLL_TIMEOUT_DEFAULT)
    p.add_argument("--poll-interval", type=float, default=a7w.POLL_INTERVAL,
                   help="轮询间隔秒数，默认 %g" % a7w.POLL_INTERVAL)
    p.add_argument("--max-seconds", type=float, help="整批最长耗时（秒），到点中断可续跑")
    p.add_argument("--force", action="store_true", help="忽略断点，全部重出（会重复扣费）")
    p.add_argument("--no-wait", action="store_true", help="只提交不等结果（稍后用 task 续查）")
    p.add_argument("--stop-on-error", action="store_true", help="一张失败就整体停")
    p.add_argument("--allow-prompt-hits", action="store_true",
                   help="即使提示词命中闸门也出图（默认拦截）")
    p.add_argument("--report", help="把本次证据（请求参数/任务原文/真实像素）写成 JSON")
    p.set_defaults(func=cmd_gen)
    return ap


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与以前完全一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout          # 记住真 stdout（信封不许被重定向吞掉）
    _JSON["want"] = "--json" in argv_eff  # argparse 失败时还没有 a，先按命令行判断
    _JSON["emitted"] = False
    _JSON["reason"] = None
    try:
        return _main(argv_eff)
    except Exception as exc:                      # noqa: BLE001 —— 故意的：契约要求给信封
        if not _JSON["want"]:
            raise                                 # 非 --json：原样冒泡
        traceback.print_exc()                     # 完整栈 → stderr（不吞、不截断）
        _json_internal(exc)
        return 1


def _main(argv_eff):
    ap = build_parser()
    try:
        a = ap.parse_args(argv_eff)
    except SystemExit as exc:
        # argparse 的参数错（退出码 2）也要给信封；--help（0）不算失败
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    kind, msg = None, None
    try:
        rc = a.func(a)
    except a7w.A7wError as exc:
        sys.stderr.write("\n错误：%s\n" % exc)
        rc, kind, msg = 2, "call", str(exc)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（已提交的任务记在断点文件里，重跑可续查）\n")
        rc, kind, msg = 130, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        _json_fail(rc, reason.get("kind") or kind,
                   reason.get("message") or msg, reason.get("detail"), a)
    return rc


if __name__ == "__main__":
    sys.exit(main())
