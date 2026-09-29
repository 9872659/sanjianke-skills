#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 漫画分镜出图（sanjianke-storyboard-art）。

把剧本 / 小说片段变成**漫画分镜序列**：
    剧本 → 角色设定卡（characters）→ 分镜表（shots）→ 逐格出图（images）
         → 跨格一致性自检（consistency）→ 拼页排版（sheet）

与同族包的分工（这是本包存在的理由，别把它做成"给小说出配图"）：
    · sanjianke-image-factory  出的是**文章配图**（封面/内文），格与格之间没有角色关系
    · sanjianke-longform-factory 出的是**长文 + 配图**
    · 本包出的是**分镜图序列 + 拼好的漫画页**：每格有景别/机位，同一角色跨 N 格必须是同一张脸

七个本地硬闸门（都是**拦截 + 标红 + stderr 汇总 + 非 0 退出码**，不是"提示一下"）：
    1. 合规          广告法违禁词；「最X」有可枚举的上下文豁免，句首不许误豁免
    2. 占位符残留    {} / [待填] / XXX …
    3. prompt_echo   出图提示词照抄了提示词里的示例（三条判据 + 相对长度守卫）
    4. 比例真伪      **读回图片文件真实像素**再算比例，不信接口自报字段；容差 3%；--snap 裁准
    5. 分镜结构      每格必须有景别 + 画面描述；缺项标红；格数为 0 → 拦
    6. 角色一致性    **本包重点**：同一角色在 N 格里，设定卡里的特征词必须都出现；
                     某格漏掉哪个词就报出「第几格 漏了 哪个词」
    7. 成本上限 + 产出位置  超 --budget 不提交；--outdir 落在包内 → exit 2

零第三方依赖：出图、闸门、拼页全部只用标准库。
拼页（sheet）内置纯标准库 PNG 解码/缩放/合成，装了 Pillow 会更清晰（走 LANCZOS），
没装就用最近邻/盒式滤波——**如实说明画质差异，不假装两者一样**。

⚠️ 断点 key 的教训（同族踩过两次，这里一次给全）
    key 必须含**全部影响产出的维度**，少一维就是「静默复用旧产物」：
      · 只含 id            → 改提示词不重出（拿到的还是旧图）
      · 只含 id + 提示词    → 改 --resolution 不重出（1K 冒充 4K）
      · 不含 charsheet      → 改角色设定卡不重出（旧脸冒充新设定）
      · 不含 action/refs    → 换个参考图不重出
    所以本包的 key 是：id + 提示词全文摘要 + 比例 + resolution + 模型 + action
                      + 角色设定卡摘要 + 参考图摘要（八维）。
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
import imgprobe   # noqa: E402  ← 图片头探针（读真实像素），独立模块

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"       # 实测可用（会路由到 deepseek-flash）
CHAT_RETRIES = 4
STATE_NAME = "storyboard-state.json"

# ---------------------------------------------------------------------------
# nano_banana 出图应用（本包业务，**放在这里而不是 a7w.py**）
#
# 【约定】`scripts/a7w.py` 是所有 Skill 包共用的零依赖客户端，我们靠
# 「包内副本 SHA256 == 规范版」批量校验各包有没有被改坏。
# 所以任何包都不许为了自己的业务往 a7w.py 里加东西：
#   · 需要读图片像素     → 独立模块 `imgprobe.py`
#   · 需要应用专属接口    → 就写在下面这一段里
# ---------------------------------------------------------------------------

APP_IMAGE = "nano_banana"                   # 出图应用编码
API_SUBMIT = "submit"                       # POST /api/v1/apps/nano_banana/submit
API_QUERY = "query"                         # GET  /api/v1/apps/nano_banana/query（备用）
TASK_URL = a7w.HOST + "/api/v1/tasks/{}"    # GET  /api/v1/tasks/<task_id>（统一任务查询，实际用它）

# 参数可选值。**开工前先现查**：`python3 scripts/a7w.py schema nano_banana`。
RESOLUTIONS = ("1K", "2K", "4K")
ASPECT_RATIOS = ("auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
                 "5:4", "4:5", "21:9")
ACTIONS = ("generate", "edit")
IMAGE_MODELS = ("nano-banana", "nano-banana-2", "nano-banana-2-lite",
                "nano-banana-pro", "nano-banana:official",
                "nano-banana-2-lite:official", "nano-banana-2:official",
                "nano-banana-pro:official")

# schema 实查：`caps.max_reference_images = 12`（max_reference_audios/videos = 0）。
# 参考图是本包压角色一致性的主要手段，所以这个上限要当硬约束用，不能随便塞。
MAX_REFERENCE_IMAGES = 12

# 单张轮询上限（秒）。**本包自己的口径，不改 a7w.py 里那个 1800**——
# 那里是给视频任务调的；出图实测 5~30 秒完成，600 秒足够且能更快暴露卡死。
POLL_TIMEOUT_DEFAULT = 600

# 实测单价：nano_banana 1K 出图 24 点/张（= 0.24 元，1 元 = 100 点）。
# 只有这一档是我们真金白银打出来的数：
#   · 2K/4K        → schema 里 `resolution` 有这三个值，但我们没实测过 2K/4K 的实扣
#   · 其它模型      → schema 的 api_doc 里列了官方模型的文档价（28.03 / 35.76 / 61.52 点起），
#                     但那是**平台文档价**，不是我们实扣的数；同族已经验证过
#                     pricing_matrix / tenant_* 这类字段半数不可信，所以一律不当结算价
# 想估算就给 --points-per-image，**宁可拒绝估算也不编一个数**。
POINTS_PER_IMAGE_1K = 24
POINTS_PER_YUAN = 100
UNTESTED_RESOLUTIONS = ("2K", "4K")
MEASURED_MODELS = ("nano-banana",)

OUT_EXT = ".png"

# ---------------------------------------------------------------------------
# 分镜枚举（闸门五用它判「每格有没有景别」）
#
# 为什么景别要判枚举而不是"非空就行"：景别是分镜表的骨架。
# 一格写"中景"、一格写"看得见人"、一格写"常规"，拼出来就是一锅粥——
# 读者感受不到距离变化，节奏就没了。所以不在枚举里的写法要标红。
# 但常见的口语化写法给别名表兜住（别把"半身"这种正经说法判成错）。
# ---------------------------------------------------------------------------

SHOT_SIZES = ("大远景", "远景", "全景", "中景", "中近景", "近景", "特写", "大特写")
SHOT_SIZE_ALIASES = {
    "大全景": "远景", "大全": "远景", "远镜头": "远景", "广角": "远景",
    "全身": "全景", "全身景": "全景", "full": "全景",
    "medium": "中景", "中": "中景",
    "中近": "中近景", "中特写": "中近景", "半身": "中近景", "半身景": "中近景",
    "近": "近景", "近镜头": "近景",
    "closeup": "特写", "close-up": "特写", "局部": "特写",
    "大特": "大特写", "极特写": "大特写",
}
CAMERAS = ("平视", "微俯", "俯视", "仰视", "过肩", "越肩", "主观视角", "斜侧", "背身", "正面")

# 每页默认格数：条漫 4 格一屏，页漫 2x2 = 4 格
DEFAULT_PER_PAGE = 4

# 拼页预设（只决定画布宽度与默认格宽，不决定内容）
PAGE_PRESETS = {
    "webtoon": {"name": "条漫", "width": 1080, "panel_w": 1080, "panel_h": 720,
                "note": "竖屏条漫，单列从上往下读；一格一屏高约 1080x1350 也可"},
    "page-b5": {"name": "漫画页 B5", "width": 1240, "panel_w": 580, "panel_h": 620,
                "note": "常见单行本内页，2 列 x 2 行"},
    "page-a4": {"name": "漫画页 A4", "width": 1400, "panel_w": 620, "panel_h": 660,
                "note": "投稿/打印用 A4 纵横比接近，2 列 x 2 行"},
    "square": {"name": "方图", "width": 1024, "panel_w": 480, "panel_h": 480,
               "note": "社交平台方图，2 列 x 2 行"},
}
LAYOUTS = ("strip", "grid")
REF_MODES = ("none", "prev", "anchor", "both")

# 上游实际能给的像素（1K 档，实测 10 种比例）。留作文档与排错依据。
MEASURED_1K_PIXELS = {
    "1:1": [1024, 1024], "3:4": [864, 1184], "4:3": [1184, 864],
    "16:9": [1344, 768], "9:16": [768, 1344], "21:9": [1536, 672],
    "2:3": [832, 1248], "3:2": [1248, 832], "4:5": [896, 1152],
    "5:4": [1152, 896],
}


# ---------------------------------------------------------------------------
# nano_banana 接口封装
#
# 平台文档写的是 `data.result.status`，**实测不对**：status 在 `data` 顶层
# （`query` 接口的 api_doc 里也写的是 `result.status`，但我们按实测取顶层）。
# 照文档写会永远读不到状态、一路轮询到超时。
#
# 另一个实测事实：`code == 1` 才是成功，**不是 0**。
# a7w.py 的 `_unwrap` 已经按这个口径判了，这里不重复实现。
# ---------------------------------------------------------------------------

def submit_image(prompt, aspect_ratio="3:4", resolution="1K",
                 model="nano-banana", action="generate", image_urls=None,
                 callback_url=None, key=None, timeout=180):
    """提交一个出图任务，返回网关 data（含 task_id 与预冻结点数）。

    请求体字段用 `python3 scripts/a7w.py schema nano_banana` 实查过，不要凭记忆加字段：
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
        raise a7w.A7wError("action=edit 时必须提供 image_urls（本包用它传上一格/角色锚点图）")
    if image_urls and len(image_urls) > MAX_REFERENCE_IMAGES:
        raise a7w.A7wError("参考图最多 %d 张（schema 的 max_reference_images），收到 %d 张"
                           % (MAX_REFERENCE_IMAGES, len(image_urls)))
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

    ⚠️ 只信 usage.points_cost。平台的 pricing_matrix / tenant_* / fixed_price 字段
    我们验证过半数不可信（`image_human` 字段写 1.5/2/4/8 点/秒、实测 2/3/6/12；
    `voice_tts/stt` 字段写 30、实扣 40），所以那些字段只当参考，绝不写进结算口径。
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
# 闸门四：比例真伪（读真实像素，不信自报值）
#
# 事故来源：标题工坊上一版只信模型自报的 `formula` 字段做模板污染判定，
# 结果那个真该被判命的标题恰好漏判——闸门是**假绿**的。
# 同一个错误在出图场景的形态是：接口/模型自报 `aspect_ratio=3:4`，
# 但真实像素是 1024x1024。只信自报值 → 用户拿去拼页才发现全错了。
#
# ⚠️ 实测到的上游特性（必须写进文档，否则闸门天天误报）：
#   上游不是按比例给像素，而是先定总像素、再把每边向下取整到 32 的倍数。
#   所以 10 种比例里有 5 种给不出像素级精确比例：
#       请求 3:4  → 864x1184   = 0.7297（3:4 = 0.75）   偏差 2.70%
#       请求 16:9 → 1344x768   = 1.7500（16:9 = 1.778） 偏差 1.56%
#       请求 9:16 → 768x1344   = 0.5714（9:16 = 0.5625）偏差 1.56%
#       请求 4:5  → 896x1152   = 0.7778（4:5 = 0.8）    偏差 2.78%
#       请求 5:4  → 1152x896   = 1.2857（5:4 = 1.25）   偏差 2.86%
#   精确的 5 种：1:1 / 4:3 / 21:9 / 2:3 / 3:2
#   这**不是**网关 bug，是扩散模型按 32 对齐的常规做法。
#
# 对漫画分镜的额外含义：格子的宽高比直接决定拼页后的观感，
# 差 2.7% 在 864 宽上就是 23 像素——一格不明显，一整页 4 格错开就很明显。
# 所以拼页前的比例闸门不能省，`--snap` 值得开。
# ---------------------------------------------------------------------------

RATIO_TOLERANCE = 0.03        # 默认 3%（实测最大偏差 2.86%，留一点余量）

# 容差地板：**像素只能是整数**，所以「裁到精确比例」本身就有量化误差。
# 实测（--snap 之后复核）：2.35:1 @宽 864 → 高 368，偏差 0.0925%；
# 相邻整数像素间隔约 0.27%。所以用户把 --ratio-tolerance 调到比这还小时，
# 会把「本来就必须存在」的舍入误差判成不合格。0.0025 是保守地板，仍能抓真错：
# 请求 3:4 却给 2:3 的偏差是 11%，比地板大 40 倍。
RATIO_TOLERANCE_FLOOR = 0.0025

# 提示词里出现过的示例文本。**新增示例必须登记到这里。**
# 这些是「跨主题」的假例子，正常不该出现在真实产出里（真实剧本不会是这个）。
PROMPT_SAMPLES = [
    "一个戴圆顶礼帽的铜制机械猫头鹰停在旧书堆上，暖黄侧光，中景，平视",
    "a brass mechanical owl wearing a bowler hat on a stack of old books, warm side light, medium shot",
]

parse_ratio = imgprobe.parse_ratio
ratio_label = imgprobe.ratio_label


def check_ratio(path, want_ratio, tolerance=None):
    """闸门四：读真实像素，判是否等于请求比例。

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
# 上游按 32 对齐，3:4 实测给 864x1184（偏差 2.70%）。拼页时格子会被缩放，
# 比例不齐会让整页的横向留白一格宽一格窄。与其让后期裁，不如本地裁准。
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
    """还原 PNG 扫描线（只支持 8 位真彩/真彩+alpha：bpp ∈ {3,4}）。"""
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


def _snap_mode(a):
    """本次的裁剪口径：off / tolerance / exact。

    · `off`        不裁，只如实报告真实像素与偏差（容差 3% 内算合格）
    · `tolerance`  `--snap`：**超容差才裁**（同族口径，配图场景够用）
    · `exact`      `--snap-exact`：只要不是像素级精确（偏差 > 0.25% 量化地板）就裁准
                    —— 拼页场景必需：格子比例不齐，整页的留白一格宽一格窄
    """
    if getattr(a, "snap_exact", False):
        return "exact"
    if getattr(a, "snap", False):
        return "tolerance"
    return "off"


def _need_snap(mode, check):
    """这一张要不要裁。"""
    if mode == "off":
        return False
    if not check.get("ok"):
        return True
    return mode == "exact" and (check.get("deviation") or 0.0) > RATIO_TOLERANCE_FLOOR


def apply_snap(dest, want, a, rec):
    """对一张已下载的图做比例复核 + 可选裁剪，把证据写进 rec。

    返回 (最终文件 Path, 最终 check)。**只读改写本地文件，不花任何钱** ——
    所以重跑时改了 --snap 配置也走这条路（见 `_do_images` 的跳过分支），
    不必为了换个裁法把同一张图重买一遍。
    """
    mode = _snap_mode(a)
    check = check_ratio(str(dest), want, a.ratio_tolerance)
    rec["first_check"] = dict(check)      # 裁剪前判定：上游真实给了什么像素
    rec["real_px"] = check["real_px"]
    rec["real_ratio"] = check.get("real_ratio")
    rec["want_ratio"] = want
    rec["ratio_deviation"] = check["deviation"]
    rec["snap_mode"] = mode
    if _need_snap(mode, check):
        snapped = str(Path(dest).with_name(Path(dest).stem + "-snapped" + Path(dest).suffix))
        got = snap_to_ratio(str(dest), snapped, want)
        if got:
            way, box = got
            after = check_ratio(snapped, want, a.ratio_tolerance)
            rec["snap"] = {"method": way, "box": box, "file": snapped,
                           "why": "超容差" if not check.get("ok") else "要求像素级精确",
                           "after": after}
            if after["ok"]:
                dest = Path(snapped)
                check = after
                rec["real_px"] = after["real_px"]
                rec["real_ratio"] = after.get("real_ratio")
                rec["ratio_deviation"] = after["deviation"]
            else:
                # 裁了但复核仍不合格：如实报告，不假装成功
                rec["snap"]["after_failed"] = True
        else:
            rec["snap"] = {"method": None,
                           "why": "没有 PIL，内置裁剪器也不支持这个 PNG（需 8 位真彩/真彩+alpha）"}
    rec["file"] = str(dest)
    rec["raw_ratio_check"] = check
    rec["ratio_ok"] = bool(check["ok"])
    return Path(dest), check


# ---------------------------------------------------------------------------
# 闸门一：合规（广告法 + 平台高压线；「最X」可枚举上下文豁免）
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    (r"国家级|世界级|最高级|最佳|最优|最强|第一品牌|全国第一|排名第一|销量第一", "高",
     "广告法第九条绝对化用语，出图提示词与画面文字都不许带"),
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎|顶尖|厉害)", "高",
     "广告法第九条禁止「最高级」用语"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化用语，无法举证"),
    (r"100%|百分之百|百分百|绝对(有效|安全|可靠|不会)|零风险", "高",
     "绝对化承诺，属虚假宣传高风险表述"),
    (r"国家(认证|认可|免检)|央视(推荐|上榜)|官方(推荐|指定)|权威认证", "高",
     "虚构权威背书"),
    (r"根治|治愈|药到病除|包治|特效|无副作用|抗癌|降(血压|血糖|血脂)", "高",
     "医疗功效宣称，普通内容不得使用"),
    (r"稳赚|保本|保收益|躺赚|日入过万|月入百万|包过", "高",
     "投资/收益承诺，金融敏感表述"),
    (r"首[个创]|独家|唯一|填补空白", "中",
     "排他性表述，需有可举证依据"),
    (r"免费领|免费送|0\s*元购|白送|扫码(加|进|领)|加微信|私信我", "中",
     "诱导分享或站外导流，平台普遍限制"),
    (r"秒杀|抢购|限时(抢|购)|仅限今天|名额有限先到先得", "中",
     "促销时限表述需与真实活动一致"),
    (r"纯天然|无添加|零添加|无毒无害", "中",
     "成分/材质宣称需与检测报告一致"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看", "低",
     "标题党式诱导"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}

# 命中之后再看一眼**后续几个字**：如果接的是比较 / 程度 / 常见这类用法，
# 那它是"普通中文词"而不是"最高级广告语"，放行。
#
# 【实测依据 · 继承同族模板】真机连跑 4 次讲义，1 次被拦，拦下的是
#   「做菜和剪辑**最大**的共同点是：先做减法，再做加法」
# 这是讲义里在讲一件常识，不是给商品贴"最大"的标签。长文/剧本里的形态更常见：
#   「长文和短视频**最大**的区别是……」「新手**最**容易踩的坑是……」
#   「这一幕**最**重要的是沉默」——分镜说明里这种写法非常多，拦下来代价比漏报更大。
# 所以加一层上下文豁免，但**豁免范围写死在代码里、可枚举、可复核**，
# 不是一句"人工判断"了事。
#
# 反过来说，`最好的工具` / `最强的` / `最高级` / `最大优惠` 这类仍然照拦：
# 它们的后文不在豁免表里。
# ⚠️ 句首不许误豁免：`_superlative_is_normal_usage` 只在**命中处不是行首/句首**时才豁免，
#    因为"最大区别是……"这种**句首**写法经常正是标题式的最高级宣称。
SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥",
)
# 一个可选的「的」：「最大的共同点」「最大的区别」都是正文里常见的说法。
#
# 【为什么**没有**为逗号/顿号开豁免】实测踩到过「找出占比最高、且最容易改的那一个环节」
# 被拦下。想放开它只有两条路，两条都不该走：
#   · 豁免表里加「且」——那是在**自行扩张模板的打分口径**，越走越松；
#   · 让分隔标点豁免生效——那样「最好的工具，值得买」也会被放行，
#     等于给最高级广告语开了一个后门（标点后面跟什么都行）。
# 所以这里的口径是：**豁免只允许一个「的」**，与同族模板逐字一致；
# 上面那句会在闸门里被拦下，属**已知的保守行为**，靠改文案解决（把「最高」换成「比较高」），
# 不靠放松规则解决。这一条写在报告里，不藏着。
SUPERLATIVE_OK_RE = re.compile(
    r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")

# 句首判定：命中处前面只有空白，或前一个非空白字符是句末标点/换行 → 视为句首。
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")


def _superlative_is_normal_usage(text, m):
    """「最大/最…」后面接的是比较或程度词，**且不在句首** → 判为普通用法，不拦。

    两个条件缺一不可：
      1. 后文落在可枚举的豁免表里（SUPERLATIVE_OK_AFTER）
      2. 命中处不在句首 —— 句首的「最大区别是…」是标题式最高级宣称，照拦
    """
    if not m.group(0).startswith("最"):
        return False
    before = (text or "")[:m.start()]
    if not before.strip() or _SENT_END_RE.search(before):
        return False                       # 句首 → 不豁免
    return bool(SUPERLATIVE_OK_RE.match((text or "")[m.end():]))


def compliance_scan(text):
    """扫一遍违禁词，返回命中列表（可能为空），按风险等级排序。

    同一个词可能在文中出现多次（一次是广告语、一次是普通用法），
    所以命中判定按**每一处出现**做，任一处未被豁免就算命中。
    """
    hits, seen = [], set()
    t = text or ""
    for rx, lvl, why in BANNED_RE:
        for m in rx.finditer(t):
            if _superlative_is_normal_usage(t, m):
                continue
            word = m.group(0)
            key = (word, lvl)
            if key in seen:
                continue
            seen.add(key)
            hits.append({"word": word, "level": lvl, "why": why})
            break
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
#
# 剧本很长，模型一次吐几十格分镜，模板没替换干净的形态比单张出图多得多：
#   · `{}` / `{{角色}}`         JSON/模板骨架被当画面描述写进去了
#   · `[待填]` / `[待补充]`     模型给自己留的空档
#   · `XXX` / `xxx`             忘了替换的占位
#   · `（此处省略）`            最常见的一种：模型懒得写，直接省略
#
# `[1]`（序号）、`[图 2]`（配图位）是**正常写法**，一刀切按括号内容判会把好分镜全拦下。
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    (re.compile(r"\{\{?\s*[\u4e00-\u9fffA-Za-z0-9_]*\s*\}?\}"), "{}",
     "残留了模板占位符 `{}`，模板没被替换干净"),
    (re.compile(r"[\[【(（]\s*(待填|填空|待补充|待完善|待定)\s*[\]】)）]"), "[]",
     "残留了占位符 `[待填]`，模型给自己留的空档没补"),
    (re.compile(r"[\[【]\s*(略|此处省略)\s*[\]】]"), "[]",
     "残留了「此处省略」类占位"),
    (re.compile(r"[(（]\s*此处省略[^)）]{0,12}[)）]"), "（此处省略）",
     "残留了「（此处省略）」——模型把该写的内容省略了"),
    (re.compile(r"(?<![A-Za-z0-9])X{3,}(?![A-Za-z0-9])"), "XXX",
     "残留了占位符 `XXX`，忘了替换"),
    (re.compile(r"待补充|待完善|后续补充|此处略|TODO|TBD"), "待补充",
     "残留了「待补充」类字样，内容没写完"),
]


def placeholder_hits(text):
    """扫占位符残留，返回命中列表（可能为空）。"""
    hits = []
    t = text or ""
    for rx, label, why in PLACEHOLDER_PATTERNS:
        m = rx.search(t)
        if m:
            hits.append({"kind": label, "word": m.group(0)[:40], "why": why})
    return hits


# ---------------------------------------------------------------------------
# 闸门三：prompt_echo（照抄提示词示例）
#
# 事故复盘（来自标题工坊的实测）：提示词里写过的示例，
# 哪怕明确标着「这是错的写法」，模型照样照抄——公众号那一轮最高分 89.0 的标题
# **一字不差就是提示词里的示例**。最高分变成「抄标准答案」，排序就废了。
#
# 分镜场景下这条更隐蔽：一格长得跟示例一样你不会发现，等到拼页才看出
# "怎么每格都是同一张脸同一个构图"——而那正是本包要防的事。
#
# 判定三条（任一命中即拦）：
#   · 去标点后**完全相同**
#   · 字符二元组 Jaccard ≥ 0.75
#   · 示例的二元组**覆盖度 ≥ 0.60**（补漏第三条，见下）
# 外加**相对**长度守卫：目标归一化长度 < max(6, len(示例)//2) 就不比，
# 因为短串的二元组集合太小、指标会虚高。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6

# 【为什么还要第三条】出图提示词动辄 60~120 字，示例只有 25 字，
# Jaccard 的分母是两份二元组的**并集**，示例那一侧被长提示词摊薄得极狠 ——
# 示例原样塞进去也照样放行。实测（本仓 `_test_echo_contain.py`，示例 25 字 / 24 个二元组）：
#   · 示例原样嵌入 + 补 9 个字（34 字）→ Jaccard 24/33 = 0.727（旧判据放行 ❌）
#                                        覆盖度 24/24 = 1.000（新判据拦下 ✓）
#   · 示例原样嵌进一条 102 字的六段结构提示词
#     → Jaccard 0.245（漏）              覆盖度 1.000（抓住）
# 覆盖度只看"示例被抄了多少"，不看提示词有多长，摊薄对它无效。
# 阈值 0.60 的余量实测：17 条真实历史提示词里覆盖度最大只有 0.547，误伤 0 条。


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    这个归一化同时被**角色一致性闸门**复用（特征词比对也是去标点后比），
    保证两个闸门对"同一个词"的理解一致。
    """
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


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


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
    """对一条**最终出图提示词**跑三道本地闸门，返回命中列表。

    三道 = 合规 + 占位符 + prompt_echo。
    （分镜结构、角色一致性由 `panel_gate` / `consistency_check` 负责，
      它们看的是分镜字段而不是这一条字符串。）
    """
    leaks = []
    for h in compliance_scan(prompt):
        leaks.append(("banned_word", "命中违禁词「%s」（%s 风险）：%s"
                      % (h["word"], h["level"], h["why"])))
    for h in placeholder_hits(prompt):
        leaks.append(("placeholder", "%s（命中 %r）" % (h["why"], h["word"])))
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
# 闸门五：分镜结构（每格要有景别 + 画面描述；格数为 0 → 拦）
#
# 这条闸门是"漫画"与"配图"的分界线：
#   配图只要有一张图；分镜必须能读出**镜头**——景别决定读者离人物多远，
#   机位决定读者站在哪。缺了这一格，拼出来就是"插图集"而不是"漫画"。
# ---------------------------------------------------------------------------

def normalize_shot_size(raw):
    """把模型写的景别收拾成枚举值；认不出来返回 None（闸门会标红）。"""
    s = re.sub(r"[\s·、,，]", "", str(raw or ""))
    if not s:
        return None
    if s in SHOT_SIZES:
        return s
    low = s.lower().replace("镜头", "").replace("景", "") or s
    if low in SHOT_SIZES:
        return low
    for alias, canon in SHOT_SIZE_ALIASES.items():
        if s == alias or low == alias.lower():
            return canon
    for canon in SHOT_SIZES:                     # 兜底：包含关系
        if canon in s:
            return canon
    return None


def panel_gate(panel, card_ids):
    """闸门五：单格结构自检，返回命中列表。

    判据（缺一项就算不合格，**不放过**）：
      · 景别：必填，且要能归一化到 SHOT_SIZES
      · 画面描述：必填且不能过短（<8 字基本等于没写）
      · 出场角色：写了的 id 必须在角色设定卡里存在（指向不存在的角色 = 拼页时没人知道画谁）
    """
    leaks = []
    # 景别归一化**就地进行**：分镜表可能是手工写的（`shots` 产出时才会带
    # `shot_size_norm`），所以不能只信那个字段——不信就等于把好数据判成错。
    ss_norm = panel.get("shot_size_norm") or normalize_shot_size(panel.get("shot_size"))
    if not panel.get("shot_size"):
        leaks.append(("structure", "这一格没有景别（景别决定读者离人物多远，是分镜的骨架）"))
    elif not ss_norm:
        leaks.append(("structure", "景别 %r 不在枚举里（可用：%s）"
                      % (panel.get("shot_size"), " / ".join(SHOT_SIZES))))
    visual = (panel.get("visual") or "").strip()
    if not visual:
        leaks.append(("structure", "这一格没有画面描述"))
    elif len(_norm_for_echo(visual)) < 8:
        leaks.append(("structure", "画面描述只有 %d 个字（少于 8 字基本等于没写）：%r"
                      % (len(_norm_for_echo(visual)), visual[:30])))
    for cid in panel.get("characters") or []:
        if cid not in card_ids:
            leaks.append(("structure", "出场角色 %r 不在角色设定卡里（先用 characters 抽出这个角色）"
                          % cid))
    if not (panel.get("prompt") or "").strip():
        leaks.append(("structure", "这一格没有出图提示词（prompt）"))
    return leaks


# ---------------------------------------------------------------------------
# 闸门六：跨格角色一致性（**本包的核心难点**）
#
# 问题形态：同一个角色在 N 格里要长得一样。
# 现实是——不做约束，N 格就是 N 张脸。
#
# 三道一起用（少一道都压不住）：
#   a) **角色设定卡**：把角色的可视觉特征写成 `features` 列表（4~12 字一条、
#      可逐字复述、只写外貌不写情绪），这是跨格复述的**唯一凭据**。
#   b) **硬约束提示词**：每格的出图提示词里必须**逐字写出**该格出场角色的
#      全部 features —— 模型不写全，脸就会自己长。
#   c) **多参考图**：`action=edit` + `image_urls` 传上一格 / 角色锚点图（见 refs 段）。
#
# 本闸门管的是 (b)：把每格的 prompt 拿出来，逐字核对 features 是否都在。
#
# ⚠️ 为什么**不**替模型自动补特征词：那样闸门永远绿——**假绿闸门**比没有闸门更危险
#    （同族事故：只信自报字段，该判命的漏判）。所以这里只核对、不代写。
#    特征词漏了就是漏了，报出「第几格 漏了 哪个词」，让模型/人来补。
#
# ⚠️ 这里刻意**不**把画风块（style_bible）算进比对范围：
#    画风块是全篇共用的，如果特征词能靠它满足，那某一格漏写特征也照样绿。
#    所以 feature 只在**该格自己的 prompt** 里找。
#
# 配色漂移：设定卡里的配色（name + hex）在该格 prompt 里一个都没出现 → 记 drift。
#    默认**只报告不拦**（`--min-palette-ratio 0`），因为配色是风格软约束；
#    要当硬约束就把它调到 0 以上。
# ---------------------------------------------------------------------------

def charsheet_digest(cards, ids=None):
    """角色设定卡摘要：只看**这一格实际用到的角色**的卡片内容。

    这样"改了一个跟本格无关的角色"不会让这一格重出（省钱），
    而"改了本格出场角色的任何一个字"必定让这一格重出（防静默复用）。"""
    picked = {}
    for cid in sorted(ids or []):
        c = (cards or {}).get(cid) or {}
        picked[cid] = {
            "name": c.get("name"),
            "features": c.get("features"),
            "palette": c.get("palette"),
            "costume": c.get("costume"),
            "appearance": c.get("appearance"),
            "negative": c.get("negative"),
        }
    blob = json.dumps(picked, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def charsheet_version(cards_obj):
    """整份设定卡的版本号：给断点 key 的**可读维度**用（与摘要双保险）。"""
    blob = json.dumps(cards_obj.get("characters") or [], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def _feature_check(prompt, card):
    """核对该角色在这一格 prompt 里的特征词覆盖情况。"""
    feats = [f for f in (card.get("features") or []) if str(f).strip()]
    np_ = _norm_for_echo(prompt)
    present, missing = [], []
    for f in feats:
        (present if _norm_for_echo(f) and _norm_for_echo(f) in np_ else missing).append(f)
    total = len(feats)
    ratio = (len(present) / float(total)) if total else 1.0
    return {"features_total": total, "present": present, "missing": missing,
            "feature_ratio": round(ratio, 4)}


def _palette_check(prompt, card):
    """核对该角色在这一格 prompt 里的配色词覆盖情况（配色漂移）。"""
    pal = [p for p in (card.get("palette") or []) if isinstance(p, dict)]
    np_ = _norm_for_echo(prompt)
    present, missing = [], []
    for p in pal:
        name = str(p.get("name") or "").strip()
        if name and _norm_for_echo(name) in np_:
            present.append(p)
        else:
            missing.append(p)
    total = len(pal)
    ratio = (len(present) / float(total)) if total else 1.0
    return {"palette_total": total, "present": [p.get("name") for p in present],
            "missing": missing, "palette_ratio": round(ratio, 4)}


def consistency_check(cards, panels, min_feature_ratio=1.0, min_palette_ratio=0.0):
    """闸门六：跨格一致性自检（**零成本**，不调任何接口）。

    返回 dict：
        ok               整体结论（会不会拦）
        panels[]         逐格：出场角色的特征词覆盖 / 漏了哪些词 / 配色漂移
        missing_words[]  扁平化的「第几格 哪个角色 漏了 哪个词」（给人看的清单）
        palette_drift[]  扁平化的配色漂移清单
        characters{}     按角色汇总：出现在哪几格、被漏词的格数
    """
    per_panel, missing_words, palette_drift = [], [], []
    summary = {}
    for cid, card in (cards or {}).items():
        summary[cid] = {"name": card.get("name"), "panels": [],
                        "features_total": len(card.get("features") or []),
                        "panels_with_missing": []}

    for p in panels:
        ids = [c for c in (p.get("characters") or []) if c in (cards or {})]
        row = {"id": p.get("id"), "characters": []}
        for cid in ids:
            card = cards[cid]
            fc = _feature_check(p.get("prompt") or "", card)
            pc = _palette_check(p.get("prompt") or "", card)
            row["characters"].append({"id": cid, "name": card.get("name"), **fc, **pc})
            summary[cid]["panels"].append(p.get("id"))
            if fc["missing"]:
                summary[cid]["panels_with_missing"].append(p.get("id"))
                for w in fc["missing"]:
                    missing_words.append({"panel": p.get("id"), "character": cid,
                                          "name": card.get("name"), "word": w})
            if pc["palette_total"] and pc["palette_ratio"] < 1.0:
                palette_drift.append({
                    "panel": p.get("id"), "character": cid, "name": card.get("name"),
                    "missing": [x.get("name") for x in pc["missing"]],
                    "ratio": pc["palette_ratio"]})
        per_panel.append(row)

    feature_bad = [r for row in per_panel for r in row["characters"]
                   if r["feature_ratio"] < float(min_feature_ratio)]
    palette_bad = ([r for row in per_panel for r in row["characters"]
                    if r["palette_total"] and r["palette_ratio"] < float(min_palette_ratio)]
                   if float(min_palette_ratio) > 0 else [])
    return {
        # 格数为 0 直接判不通过（闸门五：分镜表一格都没有，就没有「一致性」可言）
        "ok": bool(panels) and not (feature_bad or palette_bad),
        "reason": None if panels else "分镜表格数为 0（闸门五：每格必须有景别 + 画面描述）",
        "min_feature_ratio": float(min_feature_ratio),
        "min_palette_ratio": float(min_palette_ratio),
        "panels_total": len(panels),
        "panels": per_panel,
        "characters": summary,
        "missing_words": missing_words,
        "palette_drift": palette_drift,
        "feature_failed": feature_bad,
        "palette_failed": palette_bad,
    }


def _consistency_brief(rep, limit=12):
    """把一致性结论压成几行人读文案（标红交给调用方）。"""
    out = []
    for m in rep["missing_words"][:limit]:
        out.append("第 %s 格 · %s（%s）漏了特征词「%s」"
                   % (m["panel"], m["name"] or m["character"], m["character"], m["word"]))
    if len(rep["missing_words"]) > limit:
        out.append("…另有 %d 条漏词未列出（见 --report）"
                   % (len(rep["missing_words"]) - limit))
    return out


# ---------------------------------------------------------------------------
# 成本
# ---------------------------------------------------------------------------

def unit_points(resolution, override=None, model="nano-banana"):
    """单张成本（点）。

    只有 `nano-banana` + `1K` 有这个实测价（24 点/张）。
    其它模型 / 其它分辨率**不给默认值**：宁可拒绝估算，也不编一个数。
    """
    if override is not None:
        return float(override)
    if (resolution or "1K").upper() != "1K":
        return None
    if (model or "nano-banana") not in MEASURED_MODELS:
        return None
    return float(POINTS_PER_IMAGE_1K)


def estimate_cost(count, resolution="1K", override=None, model="nano-banana"):
    """返回预估成本 dict。拿不到可信单价时诚实返回 None 单价。"""
    pts = unit_points(resolution, override, model)
    rec = {"count": int(count), "resolution": resolution, "model": model,
           "points_per_image": pts,
           "source": "override" if override is not None else "实测",
           "points_per_yuan": POINTS_PER_YUAN, "notes": []}
    if pts is None:
        rec["total_points"] = None
        rec["total_yuan"] = None
        if (resolution or "1K").upper() in UNTESTED_RESOLUTIONS:
            rec["notes"].append(
                "%s 档没有实测单价（我们只实测过 1K = 24 点/张），拒绝凭猜估算："
                "请用 --points-per-image 指定单价后重算" % resolution)
        else:
            rec["notes"].append(
                "模型 %s 没有实测单价（实测过的只有 %s），拒绝凭猜估算："
                "请用 --points-per-image 指定单价后重算"
                % (model, " / ".join(MEASURED_MODELS)))
        return rec
    if override is None and resolution.upper() in UNTESTED_RESOLUTIONS:
        rec["notes"].append("该档单价来自 --points-per-image，不是我们实测的数")
    rec["total_points"] = pts * rec["count"]
    rec["total_yuan"] = rec["total_points"] / float(POINTS_PER_YUAN)
    rec["notes"].append("按实测价 24 点/张（nano-banana · 1K）计算；"
                        "实际扣费以任务返回的 usage.points_cost 为准")
    rec["notes"].append("提交时会先冻结（实测 frozen_points=31.2），完成后按 24 点结算，"
                        "失败全额退回；只信 usage.points_cost")
    if (model or "") != "nano-banana":
        rec["notes"].append("注意：--model 不是 nano-banana 时这个估算不成立，"
                            "必须给 --points-per-image")
    return rec


def fmt_cost(rec):
    if rec.get("total_points") is None:
        return "无法估算（%s）" % "；".join(rec.get("notes") or [])
    return "%d 张 × %g 点 = %g 点 = %.2f 元" % (
        rec["count"], rec["points_per_image"], rec["total_points"], rec["total_yuan"])


# ---------------------------------------------------------------------------
# 文本模型：抽角色设定卡 / 出分镜表
#
# 【铁律】提示词里不许出现任何一条可直接复制的完整出图提示词。
# 举例只用**登记在 PROMPT_SAMPLES 里的跨主题示例**（铜制机械猫头鹰），
# 与真实剧本明显不搭；万一将来有人把真实示例加进去，prompt_echo 闸门会兜住。
# ---------------------------------------------------------------------------

SYSTEM_CHARS = (
    "你是三剪客团队的漫画美术指导，负责把剧本整理成**可跨格复述**的角色设定卡。\n"
    "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
    "你写的 features（特征词）是同一角色在第 1 格和第 30 格长得一样的唯一凭据，"
    "所以必须具体、可视觉化、可逐字复述，不许写情绪、不许写剧情、不许写抽象形容词。\n"
    "不使用广告法违禁词（最好/第一/国家级/100%/根治/绝对 等一律不许出现），"
    "不引用真实品牌、真实人物姓名或受保护的既有角色形象。"
)

SYSTEM_SHOTS = (
    "你是三剪客团队的漫画分镜师，负责把剧本切成**可出图的分镜表**。\n"
    "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
    "每格必须有景别与画面描述；出图提示词里必须逐字写出该格出场角色的全部特征词"
    "（会被本地闸门逐字核对）。\n"
    "不要在图上要求生成任何文字、对白气泡或字幕（AI 出图的文字基本都是错的）。\n"
    "不使用广告法违禁词，不引用真实品牌、真实人物姓名或受保护的既有角色形象。"
)


def _read_script(a):
    """剧本来源：位置参数（可多份）/ --script / --from。"""
    parts = []
    for f in (getattr(a, "files", None) or []):
        p = Path(f)
        if not p.is_file():
            raise a7w.A7wError("找不到剧本文件：%s" % f)
        parts.append(p.read_text(encoding="utf-8", errors="replace"))
    for attr in ("script", "src"):
        fp = getattr(a, attr, None)
        if fp:
            p = Path(fp)
            if not p.is_file():
                raise a7w.A7wError("找不到剧本文件：%s" % fp)
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n\n".join(parts).strip() or None


def _clip(text, limit=8000):
    t = (text or "").strip()
    if len(t) > limit:
        return t[:limit] + "\n…（原文过长，已截断到前 %d 字）" % limit
    return t


def build_characters_prompt(script, style=None, max_chars=8, title=None):
    return """读下面的剧本片段，抽出**角色设定卡**（最多 %d 个角色，只抽真正出场的）。

剧本%s：

%s

抽卡的口径（这几条直接决定后面能不能压住一致性，请严格照做）：
- `id`：小写英文或拼音短标识（如 `chen`、`lin_jiu`），全篇唯一，后面每一格都用它点名
- `features`：**3~6 条**，每条 **4~12 个字**，只写**看得见的东西**：
  发型发色、瞳色、脸型/疤痕/痣、体型、固定配饰、惯用道具。
  自检标准：一个画师只看这几条，画 10 次都能画出同一张脸。
  ✗ 反例（不许写）：「性格冷酷」「眼神深邃」「很帅气」「气氛压抑」——这些画不出来
  ✓ 正例方向：「发型 + 发色」「一道具体的疤在具体位置」「某色某款外套 + 某色袖口」
- `costume`：常服与造型，写成一句可复述的话（颜色 + 款式 + 材质）
- `palette`：**1~3 条**配色，每条 `{"name": "中文颜色名", "hex": "#RRGGBB"}`；
  name 会被逐字核对，所以用常用的中文颜色名（深蓝 / 灰白 / 暗红），不要生造词
- `appearance`：整体外形一句话（年龄感 + 体格 + 气质，不要写剧情）
- `negative`：这个角色**不该出现**的元素（例如「不要胡须」「不要眼镜」），可留空
- `anchor_urls`：留空数组 `[]`（这是给你自己后面放角色锚点图的，本步不填）
- `script_title`：给这段剧本起一个 8~16 字的标题
- `style_bible`：一句话交代**全篇统一画风**（画种 + 线条 + 明暗 + 色彩倾向，
  例如"黑白网点漫画，硬朗线稿，高对比明暗，无彩"），后面每一格都会共用它

只输出一个 JSON 对象，结构如下（不要输出别的任何东西）：
{"script_title":"…","style_bible":"…","characters":[{"id":"chen","name":"中文名",
"aliases":["别名1"],"role":"主角/配角/反派","appearance":"…","costume":"…",
"features":["特征词1","特征词2","特征词3"],"palette":[{"name":"深蓝","hex":"#2B3A55"}],
"negative":["不要胡须"],"anchor_urls":[]}]}""" % (
        max_chars, ("（标题：%s）" % title) if title else "", _clip(script),
    ) + (("\n\n全篇画风请靠向：%s" % style) if style else "")


def build_shots_prompt(script, cards_obj, count=None, per_page=DEFAULT_PER_PAGE,
                       style=None, title=None):
    lines = []
    for c in (cards_obj.get("characters") or []):
        feats = "、".join(str(x) for x in (c.get("features") or []))
        pal = "、".join("%s(%s)" % (p.get("name"), p.get("hex"))
                        for p in (c.get("palette") or []) if isinstance(p, dict))
        lines.append("- id=%s 名字=%s；特征词（**必须逐字写进出图提示词**）：%s；配色：%s"
                     % (c.get("id"), c.get("name"), feats or "（无）", pal or "（无）"))
    card_block = "\n".join(lines) or "（角色设定卡为空）"
    n_hint = ("共 %d 格" % count) if count else "格数按剧情需要（建议 6~16 格）"
    return """把下面的剧本切成漫画分镜表，%s，每页约 %d 格。

剧本%s：

%s

角色设定卡（出图提示词里出现的角色必须来自这里，且用 `id` 点名）：
%s

全篇画风（每一格都共用，不要每格换）：
%s

每一格必须齐这些字段：
- `id`：从 1 开始连续编号
- `page` / `panel`：第几页第几格
- `shot_size`：**只能从这些里选**：%s
- `camera`：机位，尽量从这些里选：%s
- `emotion`：这一格的情绪基调（2~6 字）
- `characters`：这一格出场角色的 `id` 数组（没人的空镜写 []）
- `visual`：画面描述，30~80 字，写清谁在哪、在做什么、环境与光线
- `dialogue`：这一格的对白/独白（没有就空字符串；**不要写进 prompt**，出图不画字）
- `narration`：旁白（没有就空字符串）
- `aspect_ratio`：这一格的比例，只能从 %s 里选（条漫常用 9:16 / 3:4）
- `prompt`：**直接发给文生图模型的出图提示词**，中文，60~140 字，
  必须包含：该格全部出场角色的**全部特征词逐字原文** + 景别 + 机位 + 画面描述。
  `characters` 里的每个 id，它的每一条特征词都要在 `prompt` 里出现（会被逐字核对）；
  漏一条，这一格就会被本地闸门拦下。配色词也写进去（至少写主要那一条）。
  **不要在 prompt 里要求生成任何文字、对白气泡或字幕**；
  不要编造剧本里没有的数字与人名。

只输出一个 JSON 对象，结构如下（不要输出别的任何东西；示例里的画面是跨主题的占位例子，
真实产出**不要**照抄这几句）：
{"panels":[{"id":1,"page":1,"panel":1,"shot_size":"中景","camera":"平视",
"emotion":"压抑","characters":["chen"],"visual":"…","dialogue":"…","narration":"",
"aspect_ratio":"3:4","prompt":"…"}]}""" % (
        n_hint, per_page, ("（标题：%s）" % title) if title else "", _clip(script),
        card_block, style or cards_obj.get("style_bible") or "（未指定，按剧本基调自定一种并全篇统一）",
        " / ".join(SHOT_SIZES), " / ".join(CAMERAS), " / ".join(ASPECT_RATIOS),
    )


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么要自带退避重试：网关的 upstream timeout / HTTP 502 实测很常见，
    一次抖动打断要重跑整批分镜，很亏。5xx 与网络类错误退避重试；4xx 是业务错误，直接报。
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
        for i, ch in enumerate(cand):
            if ch not in "{[":
                continue
            try:
                obj, _ = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    raise a7w.A7wError("模型返回的不是合法 JSON：{}".format(text[:300].replace("\n", " ")))


# ---------------------------------------------------------------------------
# 归一化：设定卡 / 分镜表
# ---------------------------------------------------------------------------

def normalize_cards(obj, max_chars=8):
    """把模型产出的设定卡收拾成内部结构，并跑本地闸门。"""
    raw = obj.get("characters") if isinstance(obj, dict) else obj
    if not isinstance(raw, list):
        raise a7w.A7wError("设定卡里没有 characters 列表：%s"
                           % json.dumps(obj, ensure_ascii=False)[:200])
    cards, seen = [], set()
    for i, r in enumerate(raw, 1):
        if not isinstance(r, dict):
            continue
        cid = re.sub(r"[^a-z0-9_]", "", str(r.get("id") or "").strip().lower()) or "char%d" % i
        if cid in seen:
            cid = "%s_%d" % (cid, i)
        seen.add(cid)
        feats = [re.sub(r"\s+", "", str(x)).strip()
                 for x in (r.get("features") or []) if str(x).strip()]
        pal = []
        for p in (r.get("palette") or []):
            if isinstance(p, dict):
                name = re.sub(r"\s+", "", str(p.get("name") or "")).strip()
                hexv = str(p.get("hex") or "").strip()
                if name:
                    pal.append({"name": name,
                                "hex": hexv if re.match(r"^#[0-9A-Fa-f]{6}$", hexv) else ""})
            elif isinstance(p, str) and p.strip():
                pal.append({"name": re.sub(r"\s+", "", p).strip(), "hex": ""})
        cards.append({
            "id": cid,
            "name": str(r.get("name") or cid).strip(),
            "aliases": [str(x).strip() for x in (r.get("aliases") or []) if str(x).strip()],
            "role": str(r.get("role") or "").strip(),
            "appearance": str(r.get("appearance") or "").strip(),
            "costume": str(r.get("costume") or "").strip(),
            "features": feats,
            "palette": pal[:3],
            "negative": [str(x).strip() for x in (r.get("negative") or []) if str(x).strip()],
            "anchor_urls": [str(x).strip() for x in (r.get("anchor_urls") or [])
                            if str(x).startswith("http")],
            "leaks": prompt_gate("%s %s %s" % (r.get("appearance") or "",
                                              r.get("costume") or "",
                                              " ".join(feats))),
        })
    if max_chars and len(cards) > max_chars:
        cards = cards[:max_chars]
    for c in cards:
        if not c["features"]:
            c["leaks"].append(("structure",
                               "角色 %s 没有特征词（features）：跨格一致性没有凭据可用"
                               % c["id"]))
    out = {
        "script_title": str((obj or {}).get("script_title") or "").strip(),
        "style_bible": str((obj or {}).get("style_bible") or "").strip(),
        "characters": cards,
    }
    out["version"] = charsheet_version(out)
    return out


def normalize_panels(obj, card_ids, count=None, per_page=DEFAULT_PER_PAGE,
                     default_ratio="3:4"):
    """把模型产出的分镜表收拾成内部结构，并跑结构与一致性闸门。"""
    raw = obj.get("panels") if isinstance(obj, dict) else obj
    if not isinstance(raw, list):
        raise a7w.A7wError("分镜表里没有 panels 列表：%s"
                           % json.dumps(obj, ensure_ascii=False)[:200])
    panels = []
    for i, r in enumerate(raw, 1):
        if not isinstance(r, dict):
            continue
        ss_raw = str(r.get("shot_size") or "").strip()
        ar = str(r.get("aspect_ratio") or default_ratio).strip()
        if ar not in ASPECT_RATIOS:
            ar = default_ratio
        chars = []
        for c in (r.get("characters") or []):
            cid = re.sub(r"[^a-z0-9_]", "", str(c).strip().lower())
            if cid and cid not in chars:
                chars.append(cid)
        pid = int(r.get("id") or i)
        page = r.get("page")
        panel = {
            "id": pid,
            "page": int(page) if str(page or "").isdigit() else ((i - 1) // max(1, per_page) + 1),
            "panel": int(r.get("panel")) if str(r.get("panel") or "").isdigit()
                     else (i - 1) % max(1, per_page) + 1,
            "shot_size": ss_raw,
            "shot_size_norm": normalize_shot_size(ss_raw),
            "camera": str(r.get("camera") or "").strip(),
            "emotion": str(r.get("emotion") or "").strip(),
            "characters": chars,
            "visual": re.sub(r"\s+", " ", str(r.get("visual") or "")).strip(),
            "dialogue": str(r.get("dialogue") or "").strip(),
            "narration": str(r.get("narration") or "").strip(),
            "aspect_ratio": ar,
            "prompt": re.sub(r"\s+", " ", str(r.get("prompt") or "")).strip(),
        }
        panel["leaks"] = panel_gate(panel, card_ids)
        panels.append(panel)
    if count and len(panels) > count:
        panels = panels[:count]
    for n, p in enumerate(panels, 1):
        if p["id"] <= 0:
            p["id"] = n
    return panels


def final_prompt(panel, style_block=None):
    """真正发给出图模型的提示词 = 画风块 + 该格自己的分镜提示词。

    画风块是全篇共用的（来自设定卡的 style_bible 或 --style）；
    角色特征词只在 `panel["prompt"]` 里核（见 consistency_check 的口径说明），
    这样画风块不会把"某格漏写特征词"这件事掩盖成绿的。
    """
    p = (panel.get("prompt") or "").strip()
    s = (style_block or "").strip()
    if not s:
        return p
    if s in p:
        return p
    return "%s。%s" % (s, p)


# ---------------------------------------------------------------------------
# 断点续跑
#
# 出图是**异步 + 按次扣费**的：一次抖动、一次 Ctrl+C，都会让「已经提交并冻结了点数」
# 的任务悬在那里。没有断点记录，重跑会把同一格再买一遍。
#
# key 必须含**全部影响产出的维度**（同族踩过的三个坑，这里一次给全）：
#   · 只含 id            → 改提示词不重出（静默复用旧图）
#   · 只含 id + 提示词    → 改 --resolution 不重出（1K 冒充 4K）
#   · 不含 charsheet      → 改角色设定卡不重出（旧脸冒充新设定）
#   · 不含 action/refs    → 换参考图不重出
# 所以本包 key 是八维：id + 提示词全文摘要 + 比例 + resolution + 模型 + action
#                    + 角色设定卡摘要 + 参考图摘要
#
# ⚠️ 提示词取**全文**摘要，绝不截断前 N 个字符：
#    上一版按 `prompt[:24]` 取 key 的同族包，提示词只改第 25 字之后时 key 不变
#    → 静默复用旧图，用户以为重出了。这是「静默复用过期产物」，
#    比多扣一次费危险得多（多扣费用户立刻会发现，复用旧图不会）。
# ---------------------------------------------------------------------------

def state_key(panel, resolution, model, action, cs_digest, refs, style_block=None):
    payload = "|".join([
        str(panel.get("id")),
        hashlib.sha1(_norm_for_echo(final_prompt(panel, style_block)).encode("utf-8")).hexdigest(),
        panel.get("aspect_ratio") or "",
        (resolution or "1K").upper(),
        model or "",
        action or "",
        cs_digest or "",
        hashlib.sha1("|".join(refs or []).encode("utf-8")).hexdigest(),
    ])
    return "sb:%s:%s" % (panel.get("id"), hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16])


def load_state(path):
    p = Path(path)
    if not p.is_file():
        return {"version": 1, "items": {}, "stages": {}}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or "items" not in obj:
            return {"version": 1, "items": {}, "stages": {}}
        obj.setdefault("stages", {})
        return obj
    except (OSError, ValueError):
        sys.stderr.write("⚠ 断点文件读不动（%s），按空处理——注意这会导致重出图\n" % path)
        return {"version": 1, "items": {}, "stages": {}}


def save_state(path, state):
    p = Path(path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# 拼页排版（sheet）：纯标准库 PNG 解码 / 缩放 / 合成
#
# 为什么值得自己做：分镜图是**一格一张**，交付物是**一页一页**。
# 中途交给设计工具去拼，就断了"一条命令跑完"这条链路。
#
# 为什么不在图上渲染对白文字：零依赖做不了字体栅格化（标准库没有字库解析与字形光栅化），
#   而且 AI 出图的文字基本都是错的——本包的口径是「图不带字，字另外给」：
#   `sheet` 会产出一份 `dialogue.md`（逐格对白/旁白 + 画面描述），交给后期或设计工具加字。
#   这是**明确的设计取舍**，不是遗漏。
#
# 画质口径：装了 Pillow → 缩放走 LANCZOS（缩小）/ BICUBIC（放大）；
#   没装 → 缩小走盒式均值、放大走最近邻。两条路都**如实标注**用了哪一种。
# ---------------------------------------------------------------------------

class PngImage(object):
    """内存里的一张 8 位 RGB(A) 图：px 是 bytearray，通道数 ch ∈ {3,4}。"""

    def __init__(self, w, h, ch, px):
        self.w, self.h, self.ch, self.px = int(w), int(h), int(ch), px

    @property
    def stride(self):
        return self.w * self.ch


def decode_png_stdlib(path):
    """纯标准库解码 PNG（8 位，color_type 0/2/4/6，非隔行）。

    解不了就返回 None —— 调用方据此**如实报错**，不假装成功。
    """
    try:
        blob = Path(path).read_bytes()
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        idat, idepth, ctype, interlace = bytearray(), None, None, 0
        for typ, data in _png_chunks(blob):
            if typ == b"IHDR":
                w, h, idepth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", data[:13])
            elif typ == b"IDAT":
                idat.extend(data)
            elif typ == b"IEND":
                break
        if idepth != 8 or interlace != 0 or ctype not in (0, 2, 4, 6):
            return None
        src_ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
        stride = w * src_ch
        raw = _unfilter(zlib.decompress(bytes(idat)), stride, h, src_ch)
        if ctype == 2:
            return PngImage(w, h, 3, raw)
        if ctype == 6:
            return PngImage(w, h, 4, raw)
        # 灰度 / 灰度+alpha → 展开成 RGB(A)
        out_ch = 3 if ctype == 0 else 4
        out = bytearray(w * h * out_ch)
        for i in range(w * h):
            g = raw[i * src_ch]
            o = i * out_ch
            out[o] = out[o + 1] = out[o + 2] = g
            if out_ch == 4:
                out[o + 3] = raw[i * src_ch + 1]
        return PngImage(w, h, out_ch, out)
    except Exception:
        return None


def blank_image(w, h, rgb=(255, 255, 255)):
    px = bytearray(w * h * 3)
    px[0::3] = bytes([rgb[0]]) * (w * h)
    px[1::3] = bytes([rgb[1]]) * (w * h)
    px[2::3] = bytes([rgb[2]]) * (w * h)
    return PngImage(w, h, 3, px)


def resize_nn(src, tw, th):
    """最近邻缩放（放大用它，零依赖）。"""
    tw, th = max(1, int(tw)), max(1, int(th))
    out = bytearray(tw * th * src.ch)
    for y in range(th):
        sy = min(src.h - 1, y * src.h // th)
        row = sy * src.stride
        for x in range(tw):
            sx = min(src.w - 1, x * src.w // tw)
            o, i = (y * tw + x) * src.ch, row + sx * src.ch
            out[o:o + src.ch] = src.px[i:i + src.ch]
    return PngImage(tw, th, src.ch, out)


def resize_box(src, tw, th):
    """盒式均值缩放（缩小用它，零依赖；比最近邻干净很多）。"""
    tw, th = max(1, int(tw)), max(1, int(th))
    ch, sw, sh = src.ch, src.w, src.h
    out = bytearray(tw * th * ch)
    for y in range(th):
        y0, y1 = y * sh // th, max(y * sh // th + 1, (y + 1) * sh // th)
        y1 = min(y1, sh)
        for x in range(tw):
            x0, x1 = x * sw // tw, max(x * sw // tw + 1, (x + 1) * sw // tw)
            x1 = min(x1, sw)
            acc = [0] * ch
            n = 0
            for sy in range(y0, y1):
                base = sy * src.stride
                for sx in range(x0, x1):
                    o = base + sx * ch
                    for c in range(ch):
                        acc[c] += src.px[o + c]
                    n += 1
            o2 = (y * tw + x) * ch
            for c in range(ch):
                out[o2 + c] = acc[c] // n if n else 0
    return PngImage(tw, th, ch, out)


def rescale(src, tw, th):
    """缩放：缩小用盒式、放大用最近邻；返回 (图, 方式标签)。"""
    tw, th = max(1, int(tw)), max(1, int(th))
    if tw == src.w and th == src.h:
        return src, "原样"
    if tw <= src.w and th <= src.h:
        return resize_box(src, tw, th), "盒式均值"
    return resize_nn(src, tw, th), "最近邻"


def paste(dst, src, x, y):
    """把 src 贴到 dst 的 (x, y)。src 有 alpha 时做 alpha 合成，否则直接覆盖。"""
    ch, dch = src.ch, dst.ch
    for sy in range(src.h):
        dy = y + sy
        if dy < 0 or dy >= dst.h:
            continue
        srow, drow = sy * src.stride, dy * dst.stride
        for sx in range(src.w):
            dx = x + sx
            if dx < 0 or dx >= dst.w:
                continue
            so = srow + sx * ch
            do = drow + dx * dch
            if ch == 4:
                a = src.px[so + 3]
                if a == 0:
                    continue
                if a == 255:
                    dst.px[do:do + 3] = src.px[so:so + 3]
                else:
                    inv = 255 - a
                    for c in range(3):
                        dst.px[do + c] = (src.px[so + c] * a + dst.px[do + c] * inv) // 255
            else:
                n = min(3, ch, dch)
                dst.px[do:do + n] = src.px[so:so + n]
    return dst


def fill_rect(dst, x, y, w, h, rgb=(255, 255, 255)):
    for yy in range(max(0, y), min(dst.h, y + h)):
        row = yy * dst.stride
        for xx in range(max(0, x), min(dst.w, x + w)):
            o = row + xx * dst.ch
            for c in range(3):
                dst.px[o + c] = rgb[c]
    return dst


def encode_png_stdlib(path, img):
    """纯标准库写 PNG（8 位，ch=3 → color_type 2；ch=4 → 6）。"""
    bpp = 3 if img.ch == 3 else 4
    rows = [bytes(img.px[y * img.stride:(y + 1) * img.stride]) for y in range(img.h)]
    _png_write(path, img.w, img.h, bpp, rows)


def _load_pil(path):
    try:
        from PIL import Image  # noqa
    except ImportError:
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def load_panel_image(path):
    """读一格分镜图，返回 (PngImage, 后端标签)。读不了返回 (None, 原因)。"""
    pil = _load_pil(path)
    if pil is not None:
        px = bytearray(pil.tobytes())
        img = PngImage(pil.width, pil.height, 4 if px and len(px) == pil.width * pil.height * 4 else 3, px)
        return img, "PIL"
    img = decode_png_stdlib(path)
    if img is None:
        return None, ("内置解码器只支持 8 位非隔行 PNG（灰度/真彩/带 alpha）；"
                      "这个文件不是，装 Pillow 就能读")
    return img, "stdlib"


def compose_pages(entries, layout="grid", cols=2, rows=2, panel_w=580, panel_h=620,
                  gutter=18, margin=24, fit="contain", bg=(255, 255, 255)):
    """把 entries（每格一张已加载的图）排成页。

    返回 [(PngImage, [placement...]), ...]；placement 记了每格的落点与缩放，
    便于把证据写进 pages.json（**读回真实像素**再用 imgprobe 复核）。
    """
    n = len(entries)
    if layout == "strip":
        rows_per_page = rows if rows and rows > 0 else n
        cols = 1
        pages, i = [], 0
        while i < n:
            chunk = entries[i:i + rows_per_page]
            cell_w = panel_w
            heights, scaled = [], []
            for e in chunk:
                w, h = e["img"].w, e["img"].h
                tw = cell_w
                th = max(1, int(round(h * tw / float(w))))
                heights.append(th)
                scaled.append((tw, th))
            page_h = margin * 2 + sum(heights) + gutter * (len(chunk) - 1)
            page = blank_image(cell_w + margin * 2, page_h, bg)
            place, y = [], margin
            for k, e in enumerate(chunk):
                tw, th = scaled[k]
                sub, way = rescale(e["img"], tw, th)
                paste(page, sub, margin, y)
                place.append({"id": e["id"], "file": e["file"], "x": margin, "y": y,
                              "w": tw, "h": th, "scaler": way})
                y += th + gutter
            pages.append((page, place))
            i += rows_per_page
        return pages

    per = max(1, cols) * max(1, rows)
    pages, i = [], 0
    while i < n:
        chunk = entries[i:i + per]
        page_w = margin * 2 + cols * panel_w + (cols - 1) * gutter
        page_h = margin * 2 + rows * panel_h + (rows - 1) * gutter
        page = blank_image(page_w, page_h, bg)
        place = []
        for k, e in enumerate(chunk):
            r, c = divmod(k, cols)
            cx = margin + c * (panel_w + gutter)
            cy = margin + r * (panel_h + gutter)
            img = e["img"]
            ratio_cell = panel_w / float(panel_h)
            ratio_img = img.w / float(img.h)
            if fit == "cover":
                if ratio_img > ratio_cell:
                    th = panel_h
                    tw = max(1, int(round(panel_h * ratio_img)))
                else:
                    tw = panel_w
                    th = max(1, int(round(panel_w / ratio_img)))
            else:                                   # contain：整格画进格子，不裁画
                if ratio_img > ratio_cell:
                    tw = panel_w
                    th = max(1, int(round(panel_w / ratio_img)))
                else:
                    th = panel_h
                    tw = max(1, int(round(panel_h * ratio_img)))
            sub, way = rescale(img, tw, th)
            ox = cx + (panel_w - min(tw, panel_w)) // 2
            oy = cy + (panel_h - min(th, panel_h)) // 2
            if fit == "cover":                      # 溢出部分裁掉（居中）
                sub = crop_center(sub, panel_w, panel_h)
                tw, th = sub.w, sub.h
                ox, oy = cx, cy
            paste(page, sub, ox, oy)
            place.append({"id": e["id"], "file": e["file"], "x": ox, "y": oy,
                          "w": tw, "h": th, "scaler": way})
        pages.append((page, place))
        i += per
    return pages


def crop_center(img, w, h):
    """居中裁剪到 w x h（用于 cover 模式）。"""
    w, h = min(w, img.w), min(h, img.h)
    x0 = (img.w - w) // 2
    y0 = (img.h - h) // 2
    out = bytearray(w * h * img.ch)
    for y in range(h):
        src_off = (y0 + y) * img.stride + x0 * img.ch
        out[y * w * img.ch:(y + 1) * w * img.ch] = img.px[src_off:src_off + w * img.ch]
    return PngImage(w, h, img.ch, out)


# ---------------------------------------------------------------------------
# 人读输出小工具
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "!! " + s
    return "\033[31m" + s + "\033[0m"


def _resolve_cards(path):
    p = Path(path)
    if not p.is_file():
        raise a7w.A7wError("找不到角色设定卡：%s（先用 `characters` 生成）" % path)
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise a7w.A7wError("角色设定卡读不动或不是合法 JSON：%s（%s）" % (path, exc))
    return obj


def _cards_index(cards_obj):
    return {c["id"]: c for c in (cards_obj.get("characters") or []) if c.get("id")}


def _resolve_panels(path):
    p = Path(path)
    if not p.is_file():
        raise a7w.A7wError("找不到分镜表：%s（先用 `shots` 生成）" % path)
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise a7w.A7wError("分镜表读不动或不是合法 JSON：%s（%s）" % (path, exc))
    if not isinstance(obj.get("panels"), list):
        # 注意口径：**文件里根本没有 panels 键**是输入错误（exit 2）；
        # `"panels": []` 是「格数为 0」，那是闸门五的事（exit 3），不在这里拦。
        raise a7w.A7wError("分镜表里没有 panels 列表：%s" % path)
    return obj


def _pkg_dir():
    return Path(__file__).resolve().parent.parent


def _guard_outdir(outdir, what="产出"):
    """闸门七的前半：产出目录不许落在 Skill 包内。

    包内塞图片 = 上传白名单（.md .py .txt .json .sh .js .yaml .yml .csv）之外的文件，
    会让整包上传 400。所以这里在**花钱之前**就拦下。
    """
    p = Path(outdir).resolve()
    try:
        p.relative_to(_pkg_dir())
    except ValueError:
        return p
    raise a7w.A7wError(
        "%s目录 %s 在 Skill 包内。包内不许有任何图片（上传白名单只收文本），"
        "请换到包外，例如 %s" % (what, p, Path(os.environ.get("TEMP") or ".") / "storyboard-out"))


def _resolve_anchors(pairs, cards):
    """把 --anchor id=url 与设定卡里的 anchor_urls 合并成 {id: [url...]}。"""
    out = {}
    for c in (cards or {}).values():
        for u in (c.get("anchor_urls") or []):
            out.setdefault(c["id"], []).append(u)
    for raw in pairs or []:
        if "=" not in raw:
            raise a7w.A7wError("--anchor 要写成 id=URL，收到 %r" % raw)
        cid, url = raw.split("=", 1)
        cid, url = cid.strip().lower(), url.strip()
        if cid not in (cards or {}):
            raise a7w.A7wError("--anchor 指定的角色 %r 不在设定卡里（可用：%s）"
                               % (cid, " / ".join(sorted(cards or {}))))
        if not url.startswith("http"):
            raise a7w.A7wError("--anchor 的 URL 必须是 http/https（上游只接受公网地址）")
        out.setdefault(cid, []).append(url)
    return out


def resolve_refs(panel, mode, anchors, prev_url, extra_refs=None):
    """按 --ref-mode 决议这一格的参考图列表。

    返回 (refs, 说明)。refs 非空 → 该格走 action=edit，否则 action=generate。

    ⚠️ 上游的 `image_urls` 只收 HTTP/HTTPS 公网地址（schema 的 `image_urls` 说明），
    所以「参考上一格」用的是**上一格任务返回的 image_url**，不是本地文件。
    本包**不做上传**：a7w 的 schema 里没有实测过的图片上传路径，
    与其编一个，不如把这条边界写清楚——角色锚点图请自己放在公网可访问的地址，
    或者用本包先生成一张角色设定图、拿它返回的 image_url 当锚点。
    """
    refs, why = [], []
    if mode in ("anchor", "both"):
        for cid in (panel.get("characters") or []):
            for u in (anchors.get(cid) or []):
                if u not in refs:
                    refs.append(u)
        if refs:
            why.append("角色锚点图 %d 张" % len(refs))
        elif mode == "anchor":
            why.append("没有可用锚点图 → 回落 generate")
    if mode in ("prev", "both"):
        if prev_url and prev_url not in refs:
            refs.append(prev_url)
            why.append("上一格")
    for u in (extra_refs or []):
        if u not in refs and u.startswith("http"):
            refs.append(u)
    if len(refs) > MAX_REFERENCE_IMAGES:
        why.append("参考图超过 %d 张，已截断（schema max_reference_images）" % MAX_REFERENCE_IMAGES)
        refs = refs[:MAX_REFERENCE_IMAGES]
    return refs, "、".join(why)


# ---------------------------------------------------------------------------
# 子命令：characters
# ---------------------------------------------------------------------------

def _do_characters(a):
    script = _read_script(a)
    if not script:
        raise a7w.A7wError("请用位置参数给剧本文件，或用 --script <文件>")
    prompt = build_characters_prompt(script, a.style, a.max_chars, a.title)
    if getattr(a, "dry_run", False):
        return {"dry_run": True, "system": SYSTEM_CHARS, "user": prompt}
    sys.stderr.write("正在用 `%s` 抽角色设定卡…\n" % a.model)
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_CHARS, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not getattr(a, "no_json_mode", False))
    elapsed = time.time() - t0
    cards = normalize_cards(parse_first_json(content), a.max_chars)
    if not cards["characters"]:
        raise a7w.A7wError("模型没产出任何角色")
    cards["source"] = {"script_chars": len(script), "model": a.model,
                       "usage": usage, "elapsed_sec": round(elapsed, 1)}
    return cards


def cmd_characters(a):
    obj = _do_characters(a)
    if obj.get("dry_run"):
        if a.json:
            _json_out({"dry_run": True, "system": obj["system"], "user": obj["user"]}, a, indent=1)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (obj["system"], obj["user"]))
        return 0
    bad = [c for c in obj["characters"] if c["leaks"]]
    if a.out and not obj.get("dry_run"):
        Path(a.out).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        _json_out(obj, a, indent=1, ok=not bad)
    else:
        _render_cards(obj)
    if a.out and not a.json:
        sys.stderr.write("设定卡已写入 %s\n" % a.out)
    return 3 if bad else 0


def _render_cards(obj):
    print("角色设定卡：%s（版本 %s）" % (obj.get("script_title") or "(未命名)", obj.get("version")))
    print("全篇画风：%s" % (obj.get("style_bible") or "(未定)"))
    if obj.get("source"):
        u = obj["source"].get("usage") or {}
        print("文本用量：prompt=%s completion=%s total=%s，耗时 %ss"
              % (u.get("prompt_tokens"), u.get("completion_tokens"),
                 u.get("total_tokens"), obj["source"].get("elapsed_sec")))
    print()
    for c in obj["characters"]:
        print("# %-10s %s（%s）" % (c["id"], c["name"], c.get("role") or "-"))
        print("     特征词：%s" % ("、".join(c["features"]) or "（无）"))
        if c["palette"]:
            print("     配色：%s" % "、".join("%s %s" % (p["name"], p["hex"]) for p in c["palette"]))
        if c["appearance"]:
            print("     外形：%s" % c["appearance"])
        if c["costume"]:
            print("     服装：%s" % c["costume"])
        if c["negative"]:
            print("     禁项：%s" % "、".join(c["negative"]))
        for kind, why in c["leaks"]:
            print("     " + _red("✗ %s：%s" % (kind, why)))
    bad = [c for c in obj["characters"] if c["leaks"]]
    if bad:
        sys.stderr.write("\n!! %d 个角色的设定卡命中本地闸门（违禁词 / 占位符 / 照抄示例 / 缺特征词）\n"
                         % len(bad))


# ---------------------------------------------------------------------------
# 子命令：shots
# ---------------------------------------------------------------------------

def _do_shots(a, cards_obj=None):
    script = _read_script(a)
    if not script:
        raise a7w.A7wError("请用位置参数给剧本文件，或用 --script <文件>")
    cards_obj = cards_obj or _resolve_cards(a.characters)
    cards = _cards_index(cards_obj)
    style = a.style or cards_obj.get("style_bible")
    prompt = build_shots_prompt(script, cards_obj, a.count, a.per_page, style, a.title)
    if getattr(a, "dry_run", False):
        return {"dry_run": True, "system": SYSTEM_SHOTS, "user": prompt}
    sys.stderr.write("正在用 `%s` 出分镜表…\n" % a.model)
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_SHOTS, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not getattr(a, "no_json_mode", False))
    elapsed = time.time() - t0
    panels = normalize_panels(parse_first_json(content), set(cards), a.count, a.per_page)
    # 格数为 0 **不在这里抛异常**：那是闸门五的判据（退出码 3），
    # 让 consistency（ok=False）与 cmd_shots 的返回值统一走闸门口径。
    cons = consistency_check(cards, panels, a.min_feature_ratio, a.min_palette_ratio)
    return {"script_title": cards_obj.get("script_title"),
            "style_bible": style, "characters": sorted(cards),
            "charset_version": cards_obj.get("version"),
            "count": len(panels), "model": a.model, "usage": usage,
            "elapsed_sec": round(elapsed, 1),
            "consistency": cons, "panels": panels}


def cmd_shots(a):
    obj = _do_shots(a)
    if obj.get("dry_run"):
        if a.json:
            _json_out({"dry_run": True, "system": obj["system"], "user": obj["user"]}, a, indent=1)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (obj["system"], obj["user"]))
        return 0
    bad = [p for p in obj["panels"] if p["leaks"]]
    if a.out:
        Path(a.out).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        _json_out(obj, a, indent=1, ok=not (bad or not obj["consistency"]["ok"]))
    else:
        _render_shots(obj)
    if a.out and not a.json:
        sys.stderr.write("分镜表已写入 %s\n" % a.out)
    return 3 if (bad or not obj["consistency"]["ok"]) else 0


def _render_shots(obj):
    print("分镜表：%s   共 %d 格   模型：%s   耗时 %.1fs"
          % (obj.get("script_title") or "(未命名)", obj["count"], obj["model"],
             obj.get("elapsed_sec") or 0))
    print("全篇画风：%s" % (obj.get("style_bible") or "(未定)"))
    cons = obj["consistency"]
    print("一致性自检：%s（特征词必须全部出现；下面逐格列出）"
          % ("通过" if cons["ok"] else "不通过"))
    print()
    for p in obj["panels"]:
        print("#%-3d p%d-%d  %-6s %-6s %-8s 角色=%s"
              % (p["id"], p["page"], p["panel"], p["shot_size_norm"] or p["shot_size"],
                 p["camera"] or "-", p["emotion"] or "-",
                 "、".join(p["characters"]) or "空镜"))
        print("     画面：%s" % p["visual"])
        if p["dialogue"]:
            print("     对白：%s" % p["dialogue"])
        print("     提示词：%s" % p["prompt"])
        for kind, why in p["leaks"]:
            print("     " + _red("✗ %s：%s" % (kind, why)))
    for line in _consistency_brief(cons):
        print("  " + _red("✗ " + line))
    if cons["palette_drift"]:
        print("  " + _red("配色漂移 %d 处（默认只报告不拦，需要硬拦就设 --min-palette-ratio）："
                          % len(cons["palette_drift"])))
        for d in cons["palette_drift"][:6]:
            print("     " + _red("第 %s 格 · %s 缺配色 %s"
                                 % (d["panel"], d["name"] or d["character"], "、".join(d["missing"]))))
    if not cons["ok"]:
        sys.stderr.write("\n!! 角色一致性闸门不通过：%d 条漏词（%d 处配色漂移）。"
                         "漏了特征词 = 这个角色在这一格会自己长脸，必须补上。\n"
                         % (len(cons["missing_words"]), len(cons["palette_drift"])))


# ---------------------------------------------------------------------------
# 子命令：consistency（零成本自检）
# ---------------------------------------------------------------------------

def _do_consistency(shots_obj, cards_obj, min_feature_ratio=1.0, min_palette_ratio=0.0):
    cards = _cards_index(cards_obj)
    panels = shots_obj.get("panels") or []
    rep = consistency_check(cards, panels, min_feature_ratio, min_palette_ratio)
    rep["shots"] = None
    rep["panels_total"] = len(panels)
    return rep


def cmd_consistency(a):
    shots_obj = _resolve_panels(a.shots)
    cards_obj = _resolve_cards(a.characters)
    rep = _do_consistency(shots_obj, cards_obj, a.min_feature_ratio, a.min_palette_ratio)
    if a.report:
        Path(a.report).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        _json_out(rep, a, indent=1)
    else:
        print("跨格一致性自检（零成本，不调任何接口）")
        print("  格数 %d   出场角色 %d 个   判据：特征词覆盖率 ≥ %.2f，配色覆盖率 ≥ %.2f"
              % (rep["panels_total"], len(rep["characters"]),
                 rep["min_feature_ratio"], rep["min_palette_ratio"]))
        print()
        for cid, s in rep["characters"].items():
            flag = "✗" if s["panels_with_missing"] else "✓"
            print("  %s %-10s 出场 %2d 格，特征词 %d 条，漏词的格：%s"
                  % (flag, cid, len(s["panels"]), s["features_total"],
                     "、".join(str(x) for x in s["panels_with_missing"]) or "无"))
        for line in _consistency_brief(rep, limit=30):
            print("  " + _red("✗ " + line))
        if rep["palette_drift"]:
            print("  " + _red("配色漂移 %d 处：" % len(rep["palette_drift"])))
            for d in rep["palette_drift"][:10]:
                print("     " + _red("第 %s 格 · %s 缺配色 %s"
                                     % (d["panel"], d["name"] or d["character"],
                                        "、".join(d["missing"]))))
        print()
        print("  结论：%s" % ("通过" if rep["ok"] else
                             "不通过（%s）" % (rep.get("reason") or "漏词如上")))
    if not rep["ok"]:
        sys.stderr.write("\n!! 一致性闸门不通过：%d 条特征词漏写%s\n"
                         % (len(rep["missing_words"]),
                            ("，%d 处配色漂移超阈值" % len(rep["palette_failed"]))
                            if rep["palette_failed"] else ""))
    return 0 if rep["ok"] else 3


# ---------------------------------------------------------------------------
# 子命令：images（真花钱）
# ---------------------------------------------------------------------------

def cmd_images(a):
    """入口：`--json` 时把人读输出（报价、进度、逐格结果）整体导向 stderr。

    这样 stdout 里只剩一个完整 JSON，`json.loads` 才能直接用。
    """
    out_raw = sys.stdout
    if getattr(a, "json", False):
        sys.stdout = sys.stderr
    try:
        return _cmd_images_impl(a, out_raw)
    finally:
        sys.stdout = out_raw


def _cmd_images_impl(a, out_raw):
    shots_obj = _resolve_panels(a.shots)
    cards_obj = _resolve_cards(a.characters)
    summary = _do_images(a, shots_obj, cards_obj)
    _emit(summary, a, indent=1,
          ok=not (summary.get("failed") or summary.get("ratio_failed")
                  or summary.get("consistency_failed")))
    return summary["exit"]


def _do_images(a, shots_obj, cards_obj):
    cards = _cards_index(cards_obj)
    style_block = a.style or shots_obj.get("style_bible") or cards_obj.get("style_bible")
    anchors = _resolve_anchors(getattr(a, "anchor", None), cards)
    extra_refs = [u for u in (getattr(a, "ref_urls", None) or []) if u.startswith("http")]
    panels = list(shots_obj.get("panels") or [])
    # `--count` 是**真闸门**（少花钱）：在跑任何闸门与报价之前就截断。
    if getattr(a, "count", None):
        panels = panels[:a.count]
    # 手工/外部工具写的分镜表可能没有 `shot_size_norm`，这里就地补齐（不改内容，只补派生字段）
    for p in panels:
        if not p.get("shot_size_norm"):
            p["shot_size_norm"] = normalize_shot_size(p.get("shot_size"))
    if not panels:
        sys.stderr.write("\n!! 分镜表里一格都没有（格数为 0），**已拦截，未提交任何任务**。\n")
        return _summary_fail("gate", "分镜表格数为 0，已拦截、未提交任何任务")

    # ------------------------------------------------------------------
    # 闸门五：分镜结构（分镜表可能被手工改过，出图前再扫一遍）
    # ------------------------------------------------------------------
    struct_bad = [p for p in panels if panel_gate(p, set(cards))]
    for p in struct_bad:
        for kind, why in panel_gate(p, set(cards)):
            sys.stderr.write("!! 第 %s 格结构问题：%s\n" % (p.get("id"), _red(why)))

    # ------------------------------------------------------------------
    # 闸门六：角色一致性（**本包重点**）
    # 特征词必须都出现；某格漏掉哪个词就报出「第几格 漏了 哪个词」
    # ------------------------------------------------------------------
    cons = consistency_check(cards, panels, a.min_feature_ratio, a.min_palette_ratio)
    if not cons["ok"]:
        for line in _consistency_brief(cons, limit=20):
            sys.stderr.write("!! " + _red(line) + "\n")
        if cons["palette_failed"]:
            sys.stderr.write("!! " + _red("配色覆盖率低于 --min-palette-ratio %.2f 的角色格 %d 处"
                                          % (a.min_palette_ratio, len(cons["palette_failed"]))) + "\n")

    # ------------------------------------------------------------------
    # 闸门一/二/三：合规 + 占位符 + prompt_echo（跑在**最终出图提示词**上）
    # ------------------------------------------------------------------
    prompt_bad = []
    for p in panels:
        fp = final_prompt(p, style_block)
        leaks = prompt_gate(fp)
        if leaks:
            prompt_bad.append((p, leaks))

    blocked_struct = struct_bad and not a.allow_gate_hits
    blocked_cons = (not cons["ok"]) and not a.allow_gate_hits
    blocked_prompt = prompt_bad and not a.allow_prompt_hits
    if blocked_struct or blocked_cons or blocked_prompt:
        if blocked_prompt:
            for p, leaks in prompt_bad:
                sys.stderr.write("!! 第 %s 格出图提示词命中闸门：\n" % p["id"])
                for kind, why in leaks:
                    sys.stderr.write("     %s\n" % _red("%s：%s" % (kind, why)))
        sys.stderr.write(
            "\n共 %d 格结构不合格 / %d 条特征词漏写 / %d 格提示词命中闸门，"
            "**已拦截，未提交任何任务**（不花一分钱）。\n"
            "改完分镜表后重跑；确实要带违禁词出图才加 --allow-prompt-hits，"
            "结构/一致性要放行才加 --allow-gate-hits。\n"
            % (len(struct_bad), len(cons["missing_words"]), len(prompt_bad)))
        return _summary_fail("gate", "分镜结构 / 角色一致性 / 提示词闸门未通过，已拦截、未提交任何任务",
                             consistency=cons, struct_bad=len(struct_bad),
                             prompt_bad=len(prompt_bad))

    outdir = _guard_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state_path = a.state or str(outdir / STATE_NAME)
    state = load_state(state_path)
    resolution = (a.resolution or "1K").upper()
    model = a.model or "nano-banana"

    # 每格的预期请求（先算出来给人看，也用于报价）
    plan_rows = []
    for p in panels:
        plan_rows.append({
            "id": p["id"], "shot_size": p.get("shot_size_norm") or p.get("shot_size"),
            "camera": p.get("camera"), "ratio": p["aspect_ratio"],
            "chars": p.get("characters") or [],
            "ref_mode": a.ref_mode,
        })

    cost = estimate_cost(len(panels), resolution, a.points_per_image, model)
    print("将要出图：%d 格（分镜表 %s）" % (len(panels), a.shots))
    for r in plan_rows:
        print("  #%-3d %-6s %-6s %-5s 角色=%-16s 参考图=%s"
              % (r["id"], r["shot_size"] or "-", r["camera"] or "-", r["ratio"],
                 "、".join(r["chars"]) or "空镜", r["ref_mode"]))
    print("  输出目录：%s  （**必须不在 Skill 包内**）" % outdir)
    print("  出图模型：%s   分辨率：%s   单张成本：%s"
          % (model, resolution,
             ("%g 点" % unit_points(resolution, a.points_per_image, model))
             if unit_points(resolution, a.points_per_image, model) is not None
             else "未知（%s + %s 无实测价）" % (resolution, model)))
    print("\n  一致性口径：特征词覆盖率 ≥ %.2f（漏一条就拦）；配色覆盖率 ≥ %.2f（0 = 只报告）"
          % (a.min_feature_ratio, a.min_palette_ratio))
    print("\n预估成本：%s" % fmt_cost(cost))
    for n in cost.get("notes") or []:
        print("  · %s" % n)

    # ------------------------------------------------------------------
    # 闸门七：成本上限（**在提交任何任务之前**判，超了直接停）
    # ------------------------------------------------------------------
    if cost.get("total_points") is None:
        sys.stderr.write("\n!! 拿不到可信单价，拒绝盲跑。"
                         "用 --points-per-image <点数> 指定单价后重试。\n")
        return _summary_fail("budget", "拿不到可信单价，拒绝凭猜估算", consistency=cons)
    if a.budget is not None and cost["total_points"] > a.budget:
        sys.stderr.write("\n!! 预估 %g 点超过预算上限 %g 点，**已中断，未提交任何任务**。\n"
                         % (cost["total_points"], a.budget))
        return _summary_fail("budget",
                             "预估 %g 点超过 --budget 上限 %g 点，未提交任何任务"
                             % (cost["total_points"], a.budget), consistency=cons)
    if a.budget is not None:
        print("  预算 %g 点：在预算内" % a.budget)

    if not a.yes:
        sys.stderr.write("\n这是一次**真花钱**的操作（约 %.2f 元）。确认后加 --yes 重跑。\n"
                         % (cost["total_yuan"] or 0))
        return _summary_fail("usage", "这是一次真花钱的操作，确认后加 --yes 重跑",
                             consistency=cons, cost=cost)

    total_points = 0.0
    spent_this_run = 0.0
    done, skipped, failed, ratio_bad = [], [], [], []
    run_deadline = time.time() + a.max_seconds if a.max_seconds else None
    prev_url = None
    refs_used = {"prev": 0, "anchor": 0, "none": 0}

    for n, it in enumerate(panels, 1):
        refs, ref_why = resolve_refs(it, a.ref_mode, anchors, prev_url, extra_refs)
        action = "edit" if refs else "generate"
        if refs:
            refs_used["prev" if prev_url in refs else "anchor"] += 1
        else:
            refs_used["none"] += 1
        cs_digest = charsheet_digest(cards, it.get("characters"))
        key = state_key(it, resolution, model, action, cs_digest, refs, style_block)
        fp = final_prompt(it, style_block)
        prev = state["items"].get(key)

        # ---- 二次兜底：key 相同但记录内容与本次不一致 → 绝不复用 ----
        # （断点文件可能被手工改过、或由旧版本生成；静默复用旧图比多扣一次费危险得多）
        if prev:
            mism = []
            if _norm_for_echo(prev.get("final_prompt") or "") != _norm_for_echo(fp):
                mism.append("提示词")
            if (prev.get("resolution") or "1K").upper() != resolution:
                mism.append("分辨率")
            if (prev.get("model") or "nano-banana") != model:
                mism.append("模型")
            if (prev.get("action") or "generate") != action:
                mism.append("action")
            if (prev.get("charsheet_digest") or "") != cs_digest:
                mism.append("角色设定卡")
            if list(prev.get("refs") or []) != list(refs):
                mism.append("参考图")
            if mism:
                sys.stderr.write("    #%s 断点记录里的 %s 与本次不一致 → **不复用旧图**，重新出图\n"
                                 % (it["id"], "、".join(mism)))
                prev = None

        if prev and prev.get("status") == "completed" and not a.force:
            pts = prev.get("points_cost")
            total_points += float(pts or 0)
            # 改了 --snap / --snap-exact 配置 → **本地重裁**（原始下载文件还在），
            # 不重新提交、不重复扣费。少了这一步，换了裁法会静默沿用旧裁法的产物。
            if prev.get("snap_mode") != _snap_mode(a) and prev.get("orig_file") \
                    and Path(prev["orig_file"]).is_file():
                dest2, check2 = apply_snap(Path(prev["orig_file"]), it["aspect_ratio"], a, prev)
                prev["status"] = "completed"
                save_state(state_path, state)
                print("[%d/%d] #%s 已完成，跳过；但 --snap 配置变了 → 本地重裁（零成本）"
                      " 真实像素 %sx%s → %s"
                      % (n, len(panels), it["id"], prev.get("first_check", {}).get("real_px", ["?", "?"])[0],
                         prev.get("first_check", {}).get("real_px", ["?", "?"])[1],
                         prev.get("file")))
            elif prev.get("snap_mode") != _snap_mode(a):
                # 配置变了、但断点里没有原始下载文件（旧版断点）→ 裁不了。
                # **必须说出来**：不说就是"静默沿用旧裁法的产物"，正是本包最防的那种失败。
                sys.stderr.write(
                    "    " + _red("#%s 本次 --snap 口径（%s）与断点记录（%s）不一致，"
                                 "但断点里没有原始下载文件（旧版断点）→ **无法本地重裁**，"
                                 "这一格仍是旧口径的产物。要按新口径拿到图，只能对这几格加 "
                                 "--force（会重新扣费）。" % (it["id"], _snap_mode(a),
                                                              prev.get("snap_mode") or "没记录")) + "\n")
            skipped.append((it, prev))
            if prev.get("image_url"):
                prev_url = prev["image_url"]
            print("[%d/%d] #%s 已完成，跳过（上次扣费 %s 点，不再重复扣）"
                  % (n, len(panels), it["id"], pts))
            continue
        if run_deadline and time.time() > run_deadline:
            sys.stderr.write("\n!! 达到 --max-seconds 上限，中断。已完成的都在断点文件里，"
                             "直接重跑即可续（不会重复扣费）。\n")
            save_state(state_path, state)
            return _summary_fail("interrupt", "达到 --max-seconds 上限，已中断（可续跑）",
                                 consistency=cons, state=state_path, outdir=outdir,
                                 done=done, skipped=skipped, failed=failed,
                                 ratio_bad=ratio_bad, spent=spent_this_run,
                                 total=total_points, cost=cost)

        task_id = (prev or {}).get("task_id") if prev else None
        if task_id and prev.get("status") == "pending" and not a.force:
            print("[%d/%d] #%s 发现未完成的 task_id=%s，续查而不重新提交"
                  % (n, len(panels), it["id"], task_id))
        else:
            # 逐格再核一次预算：前面的真实扣费可能比预估高，
            # 超过 --budget 就地停，别再往下买（预估闸门只能保证「开头不超」）。
            if a.budget is not None:
                spend = total_points + (cost["points_per_image"] or 0)
                if spend > a.budget:
                    sys.stderr.write(
                        "\n!! 已花/待花 %g 点将超过预算 %g 点，**就此停下**（不再提交新任务）。\n"
                        "   已完成的图与断点都在 %s。\n" % (spend, a.budget, state_path))
                    save_state(state_path, state)
                    return _summary_fail("budget",
                                         "已花/待花 %g 点将超过 --budget %g 点，就此停下"
                                         % (spend, a.budget), consistency=cons,
                                         state=state_path, outdir=outdir, done=done,
                                         skipped=skipped, failed=failed, ratio_bad=ratio_bad,
                                         spent=spent_this_run, total=total_points, cost=cost)
            sys.stderr.write("[%d/%d] #%s 提交：action=%s ratio=%s resolution=%s model=%s"
                             " 参考图=%d%s\n"
                             % (n, len(panels), it["id"], action, it["aspect_ratio"],
                                resolution, model, len(refs),
                                ("（%s）" % ref_why) if ref_why else ""))
            try:
                data = submit_image(fp, aspect_ratio=it["aspect_ratio"],
                                    resolution=resolution, model=model, action=action,
                                    image_urls=refs or None, key=a.key)
            except a7w.A7wError as exc:
                sys.stderr.write("    提交失败：%s\n" % exc)
                failed.append({"id": it["id"], "stage": "submit", "error": str(exc)})
                if a.stop_on_error:
                    save_state(state_path, state)
                    return _summary_fail("call", "一格失败就整体停（--stop-on-error）",
                                         consistency=cons, state=state_path, outdir=outdir,
                                         done=done, skipped=skipped, failed=failed,
                                         ratio_bad=ratio_bad, spent=spent_this_run,
                                         total=total_points, cost=cost)
                continue
            task_id = data.get("task_id")
            state["items"][key] = {
                "id": it["id"], "shot_size": it.get("shot_size_norm") or it.get("shot_size"),
                "prompt": it["prompt"], "final_prompt": fp,
                "style_block": style_block,
                "aspect_ratio": it["aspect_ratio"], "resolution": resolution,
                "model": model, "action": action, "refs": list(refs),
                "charsheet_digest": cs_digest,
                "charsheet_version": shots_obj.get("charset_version"),
                "characters": it.get("characters"),
                "task_id": task_id, "status": "pending",
                "frozen_points": data.get("frozen_points"),
                "request": {"prompt": fp, "action": action, "resolution": resolution,
                            "aspect_ratio": it["aspect_ratio"], "model": model,
                            "image_urls": list(refs)},
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
                return _summary_fail("call", "一格失败就整体停（--stop-on-error）",
                                     consistency=cons, state=state_path, outdir=outdir,
                                     done=done, skipped=skipped, failed=failed,
                                     ratio_bad=ratio_bad, spent=spent_this_run,
                                     total=total_points, cost=cost)
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
                return _summary_fail("call", "一格失败就整体停（--stop-on-error）",
                                     consistency=cons, state=state_path, outdir=outdir,
                                     done=done, skipped=skipped, failed=failed,
                                     ratio_bad=ratio_bad, spent=spent_this_run,
                                     total=total_points, cost=cost)
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
        dest = outdir / ("%s-p%02d-%s-%s-%s%s"
                         % (it["id"], it.get("page") or 1, it["aspect_ratio"].replace(":", "x"),
                            a.ref_mode, key.split(":")[-1], OUT_EXT))
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

        want = it["aspect_ratio"]
        rec["orig_file"] = str(dest)      # 裁剪前的原始下载（重裁时零成本复用它）
        rec["image_url"] = url
        dest, check = apply_snap(dest, want, a, rec)
        rec["status"] = "completed"
        save_state(state_path, state)
        prev_url = url                      # 下一格的「参考上一格」用它
        if check["ok"]:
            done.append((it, rec))
            print("    完成 真实像素 %sx%s  比例 %s  扣费 %s 点  → %s"
                  % (check["real_px"][0], check["real_px"][1],
                     check.get("real_label"), pts, rec["file"]))
        else:
            ratio_bad.append((it, rec))
            print("    " + _red("完成但比例不合格：%s" % check.get("why")))
            print("    " + _red("  → %s" % rec["file"]))

    return _summary_from(
        shots=a.shots, outdir=outdir, state=state_path, planned=len(panels),
        done=done, skipped=skipped, failed=failed, ratio_bad=ratio_bad,
        total=total_points, spent=spent_this_run, cost=cost, consistency=cons,
        refs_used=refs_used, a=a)


def _summary_fail(kind, message, consistency=None, state=None, outdir=None, done=None,
                  skipped=None, failed=None, ratio_bad=None, spent=0.0, total=0.0,
                  cost=None, struct_bad=0, prompt_bad=0):
    """失败早早退出时的统一返回体（也让 `all` 能拿到同一个结构）。"""
    rc = {"gate": 3, "budget": 3, "usage": 4, "call": 2, "interrupt": 5}.get(kind, 3)
    return {"exit": rc, "kind": kind, "error": message, "consistency": consistency,
            "consistency_failed": not (consistency or {}).get("ok", True),
            "state": state, "outdir": str(outdir) if outdir else None,
            "planned": len(done or []) + len(skipped or []) + len(failed or []) + len(ratio_bad or []),
            "completed": [], "skipped_already_done": [], "ratio_failed": [],
            "failed": failed or [], "points_cost_total": total,
            "points_cost_this_run": spent, "yuan_this_run": round(spent / float(POINTS_PER_YUAN), 3),
            "estimate": cost, "struct_bad": struct_bad, "prompt_bad": prompt_bad,
            "_fail": True}


def _summary_from(shots, outdir, state, planned, done, skipped, failed, ratio_bad,
                  total, spent, cost, consistency, refs_used, a):
    summary = {
        "shots": str(shots), "outdir": str(outdir), "state": state,
        "planned_panels": planned,
        "ref_mode": a.ref_mode,
        "refs_used": refs_used,
        "completed": [{"id": it["id"], "page": it.get("page"),
                       "shot_size": it.get("shot_size_norm") or it.get("shot_size"),
                       "task_id": r.get("task_id"), "file": r.get("file"),
                       "real_px": r.get("real_px"), "want_ratio": r.get("want_ratio"),
                       "real_ratio": r.get("real_ratio"), "deviation": r.get("ratio_deviation"),
                       "points_cost": r.get("points_cost"), "image_url": r.get("image_url"),
                       "action": r.get("action"), "refs": r.get("refs"),
                       "characters": r.get("characters"),
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
        "ratio_failed": [{"id": it["id"], "file": r.get("file"), "real_px": r.get("real_px"),
                          "want_ratio": it["aspect_ratio"],
                          "why": (r.get("raw_ratio_check") or {}).get("why")}
                         for it, r in ratio_bad],
        "failed": failed,
        "consistency": consistency,
        "consistency_failed": not (consistency or {}).get("ok", True),
        "points_cost_total": total,
        "points_cost_this_run": spent,
        "yuan_this_run": round(spent / float(POINTS_PER_YUAN), 3),
        "estimate": cost,
    }
    # ------------------------------------------------------------------
    # 收尾
    # ------------------------------------------------------------------
    if not getattr(a, "json", False):
        print("\n=== 出图小结 ===")
        print("  本次真花钱：%g 点 = %.2f 元（预估 %s）"
              % (spent, spent / float(POINTS_PER_YUAN), cost["total_points"]))
        print("  成功 %d 格 / 跳过（已完成）%d 格 / 比例不合格 %d 格 / 失败 %d 格"
              % (len(done), len(skipped), len(ratio_bad), len(failed)))
        print("  参考图用法：上一格 %d 格、角色锚点 %d 格、无参考（纯文生图）%d 格"
              % (refs_used.get("prev", 0), refs_used.get("anchor", 0), refs_used.get("none", 0)))
        print("  断点文件：%s（重跑直接续，不会重复扣费）" % state)
        for it, r in ratio_bad:
            print("  " + _red("✗ #%s 比例不合格：真实 %sx%s 请求 %s"
                              % (it["id"], r["real_px"][0], r["real_px"][1], it["aspect_ratio"])))
        for f in failed:
            print("  " + _red("✗ #%s %s 失败：%s" % (f["id"], f["stage"], f["error"])))
    if getattr(a, "report", None):
        Path(a.report).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        sys.stderr.write("证据报告已写入 %s\n" % a.report)

    if failed:
        summary["exit"] = _fail(2, "call", "%d 格出图失败（明细见 stderr）" % len(failed))
    elif ratio_bad:
        summary["exit"] = _fail(3, "gate", "%d 格真实比例与请求不符" % len(ratio_bad))
    elif not (consistency or {}).get("ok", True):
        # 一致性到这一步已经不 ok 只有一种可能：用户加了 --allow-gate-hits 硬放行
        summary["exit"] = _fail(3, "gate",
                                "角色一致性仍有 %d 条特征词漏写（已按 --allow-gate-hits 放行出图）"
                                % len((consistency or {}).get("missing_words") or []))
    else:
        summary["exit"] = 0
    return summary


# ---------------------------------------------------------------------------
# 子命令：sheet（拼页/排版，本地渲染，零成本）
# ---------------------------------------------------------------------------

def collect_panel_images(shots_obj, imgdir, state_path=None, state=None):
    """把每一格对应的图找齐。

    优先用 image（出图）断点里记下的 `file`（那是**真实下载到的那张**，
    不是靠文件名猜的），找不到再按 `<id>-*` 在目录里兜底。
    缺图是**硬闸门**：拼出来少一格，页就废了。
    """
    by_id = {}
    st = state
    if st is None and state_path and Path(state_path).is_file():
        st = load_state(state_path)
    for rec in ((st or {}).get("items") or {}).values():
        if isinstance(rec, dict) and rec.get("status") == "completed" and rec.get("file"):
            rid = rec.get("id")
            if rid is not None and rid not in by_id:
                by_id[rid] = rec["file"]
    entries, missing = [], []
    for p in shots_obj.get("panels") or []:
        fid = p.get("id")
        f = by_id.get(fid)
        if not f or not Path(f).is_file():
            cands = sorted(Path(imgdir).glob("%s-*%s" % (fid, OUT_EXT)))
            f = str(cands[0]) if cands else None
        if not f:
            missing.append(fid)
            continue
        entries.append({"id": fid, "file": f})
    return entries, missing


def _do_sheet(a, shots_obj=None):
    shots_obj = shots_obj or _resolve_panels(a.shots)
    imgdir = Path(a.imgdir).resolve() if a.imgdir else \
        Path(a.state).resolve().parent if a.state else Path(".")
    _guard_outdir(a.outdir, "拼页")
    outdir = Path(a.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    entries, missing = collect_panel_images(
        shots_obj, imgdir, a.state, None)
    if not entries:
        return {"exit": _fail(3, "gate", "一格图都没找到（先在 images 里出图，或用 --imgdir 指向出图目录）"),
                "kind": "gate", "error": "一格图都没找到", "missing": missing,
                "_fail": True}

    # 加载 + 记录真实像素（闸门四的延伸：拼页输入也读真实像素）
    loaded, load_fail = [], []
    for e in entries:
        img, way = load_panel_image(e["file"])
        if img is None:
            load_fail.append({"id": e["id"], "file": e["file"], "why": way})
            continue
        w, h, fmt = imgprobe.image_size(e["file"])
        loaded.append({"id": e["id"], "file": e["file"], "img": img,
                       "real_px": [w, h], "format": fmt, "decoder": way})
    if not loaded:
        return {"exit": _fail(3, "gate", "所有分镜图都读不进来（%s）" % load_fail[:2]),
                "kind": "gate", "error": "分镜图读不进来", "load_failed": load_fail,
                "_fail": True}

    pages = compose_pages(loaded, a.layout, a.cols, a.rows, a.panel_w, a.panel_h,
                          a.gutter, a.margin, a.fit, a.bg_rgb)
    written = []
    for i, (page, place) in enumerate(pages, 1):
        dest = outdir / ("page-%02d%s" % (i, OUT_EXT))
        encoder = "stdlib"
        try:
            from PIL import Image  # noqa
            if page.ch == 4:
                Image.frombytes("RGBA", (page.w, page.h), bytes(page.px)).save(dest)
            else:
                Image.frombytes("RGB", (page.w, page.h), bytes(page.px)).save(dest)
            encoder = "PIL"
        except ImportError:
            encode_png_stdlib(str(dest), page)
        w, h, fmt = imgprobe.image_size(str(dest))
        written.append({"page": i, "file": str(dest), "real_px": [w, h], "format": fmt,
                        "encoder": encoder, "placements": place})
        sys.stderr.write("  第 %d 页 → %s（%sx%s，%s）\n" % (i, dest, w, h, encoder))

    # 对白/旁白清单：本包不在图上渲染文字（见代码顶部说明），字另外给
    dialogue = outdir / "dialogue.md"
    lines = ["# 分镜对白清单（字另外加）", "",
             "本包**不在图上渲染文字**：零依赖做不了字体栅格化，而且 AI 出图的文字基本都是错的。",
             "下面按格列出对白/旁白与画面描述，交给后期或设计工具加字。", ""]
    for p in shots_obj.get("panels") or []:
        lines.append("## 第 %s 格（p%s-%s，%s，%s）"
                     % (p.get("id"), p.get("page"), p.get("panel"),
                        p.get("shot_size") or "-", p.get("camera") or "-"))
        lines.append("")
        if p.get("dialogue"):
            lines.append("- 对白：%s" % p["dialogue"])
        if p.get("narration"):
            lines.append("- 旁白：%s" % p["narration"])
        lines.append("- 画面：%s" % (p.get("visual") or ""))
        lines.append("")
    dialogue.write_text("\n".join(lines), encoding="utf-8")

    summary = {"pages": written, "pages_count": len(written),
               "panels_in": len(loaded), "missing_panels": missing,
               "load_failed": load_fail, "layout": a.layout,
               "cols": a.cols, "rows": a.rows, "panel_w": a.panel_w,
               "panel_h": a.panel_h, "gutter": a.gutter, "margin": a.margin,
               "fit": a.fit, "outdir": str(outdir), "dialogue": str(dialogue),
               "decoders": sorted({e["decoder"] for e in loaded}),
               "note": "拼页输入真实像素逐格读自文件头；页尺寸也读回复核"}
    if missing or load_fail:
        summary["exit"] = _fail(3, "gate",
                                "有 %d 格缺图、%d 格读不进来，拼出来的页不完整"
                                % (len(missing), len(load_fail)))
        summary["_fail"] = True
    else:
        summary["exit"] = 0
    return summary


def cmd_sheet(a):
    summary = _do_sheet(a)
    if a.report:
        Path(a.report).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    if a.json:
        _emit(summary, a, indent=1, ok=not summary.get("_fail"))
    else:
        print("拼页完成：%d 页 / 输入 %d 格 / 布局 %s(%dx%d) / 面板 %dx%d / 间距 %d"
              % (summary.get("pages_count") or 0, summary.get("panels_in") or 0,
                 a.layout, a.cols, a.rows, a.panel_w, a.panel_h, a.gutter))
        for w in summary.get("pages") or []:
            print("  第 %d 页 %s（%sx%s，编码器 %s）"
                  % (w["page"], w["file"], w["real_px"][0], w["real_px"][1], w["encoder"]))
        if summary.get("missing_panels"):
            print("  " + _red("缺图的分镜格：%s"
                              % "、".join(str(x) for x in summary["missing_panels"])))
        if summary.get("load_failed"):
            for lf in summary["load_failed"]:
                print("  " + _red("第 %s 格读不进来：%s（%s）" % (lf["id"], lf["file"], lf["why"])))
        print("  对白清单：%s（本包不在图上渲染文字，字另外加）" % summary.get("dialogue"))
    if summary.get("missing_panels") or summary.get("load_failed"):
        sys.stderr.write("\n!! 有 %d 格缺图、%d 格读不进来，拼出来的页不完整\n"
                         % (len(summary.get("missing_panels") or []),
                            len(summary.get("load_failed") or [])))
    return summary.get("exit", 0)


# ---------------------------------------------------------------------------
# 子命令：all（一条命令串全链路，断点续跑）
# ---------------------------------------------------------------------------

def _stage_key(stage, *parts):
    return "%s:%s" % (stage, hashlib.sha1(
        "|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16])


def cmd_all(a):
    """把 characters → shots → images → consistency → sheet 串起来。

    文本步骤也做断点：**剧本没变就不重抽**（重抽会改设定卡 → 改 key → 全部重出图，
    所以这一步的断点比出图本身更省钱）。
    文本步骤的 key 含：剧本全文摘要 + 模型 + style + 格数等**全部影响产出的维度**。
    """
    script = _read_script(a)
    if not script:
        raise a7w.A7wError("请用位置参数给剧本文件，或用 --script <文件>")
    outdir = _guard_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    imgdir = Path(a.imgdir).resolve() if a.imgdir else outdir / "images"
    state_path = a.state or str(outdir / STATE_NAME)
    state = load_state(state_path)
    steps_done, steps_skipped = [], []

    script_digest = hashlib.sha1(script.encode("utf-8")).hexdigest()[:16]
    cards_path = Path(a.characters) if a.characters else outdir / "characters.json"
    shots_path = Path(a.shots) if a.shots else outdir / "shots.json"

    # 文本步骤用 `--text-model`；出图步骤用 `--image-model`（两者在 `all` 里必须分开，
    # 否则一个 --model 同时指文本与出图，单价与断点 key 都会被搅在一起）。
    def _text_ns(**kw):
        ns = argparse.Namespace(**vars(a))
        ns.model = a.text_model
        ns.json = False
        ns.dry_run = False
        for k, v in kw.items():
            setattr(ns, k, v)
        return ns

    # ---- 1) characters ----
    ckey = _stage_key("chars", script_digest, a.text_model, a.style or "", a.max_chars)
    if (not a.force) and state["stages"].get(ckey, {}).get("status") == "completed" \
            and cards_path.is_file():
        cards_obj = _resolve_cards(str(cards_path))
        steps_skipped.append("characters")
        sys.stderr.write("[1/5] 角色设定卡已完成，跳过（断点续跑，不再重复花文本钱）\n")
    else:
        sys.stderr.write("[1/5] 抽角色设定卡…\n")
        cards_obj = _do_characters(_text_ns(out=str(cards_path)))
        cards_path.write_text(json.dumps(cards_obj, ensure_ascii=False, indent=1),
                              encoding="utf-8")
        state["stages"][ckey] = {"status": "completed", "out": str(cards_path),
                                 "version": cards_obj.get("version")}
        save_state(state_path, state)
        steps_done.append("characters")

    # ---- 2) shots ----
    skey = _stage_key("shots", script_digest, cards_obj.get("version"),
                      a.text_model, a.count or 0, a.per_page, a.style or "")
    if (not a.force) and state["stages"].get(skey, {}).get("status") == "completed" \
            and shots_path.is_file():
        shots_obj = _resolve_panels(str(shots_path))
        steps_skipped.append("shots")
        sys.stderr.write("[2/5] 分镜表已完成，跳过（断点续跑）\n")
    else:
        sys.stderr.write("[2/5] 出分镜表…\n")
        shots_obj = _do_shots(_text_ns(out=str(shots_path), characters=str(cards_path)),
                              cards_obj)
        shots_path.write_text(json.dumps(shots_obj, ensure_ascii=False, indent=1),
                              encoding="utf-8")
        state["stages"][skey] = {"status": "completed", "out": str(shots_path),
                                 "charset_version": cards_obj.get("version")}
        save_state(state_path, state)
        steps_done.append("shots")

    # ---- 3) images ----
    ia = argparse.Namespace(**vars(a))
    ia.shots = str(shots_path)
    ia.characters = str(cards_path)
    ia.outdir = str(imgdir)
    ia.state = str(imgdir / STATE_NAME)
    ia.json = False
    sys.stderr.write("[3/5] 逐格出图（真花钱，先报价）…\n")
    isum = _do_images(ia, shots_obj, cards_obj)
    if isum.get("exit") not in (0,):
        if isum.get("_fail"):
            _fail(isum["exit"], isum.get("kind") or "gate", isum.get("error") or "出图未完成")
            return isum["exit"]
    steps_done.append("images")

    # ---- 4) consistency ----
    sys.stderr.write("[4/5] 跨格一致性自检（零成本）…\n")
    rep = _do_consistency(shots_obj, cards_obj, a.min_feature_ratio, a.min_palette_ratio)
    cpath = outdir / "consistency.json"
    cpath.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 5) sheet ----
    sys.stderr.write("[5/5] 拼页排版（本地渲染，零成本）…\n")
    sa = argparse.Namespace(**vars(a))
    sa.shots = str(shots_path)
    sa.state = str(imgdir / STATE_NAME)
    sa.imgdir = str(imgdir)
    sa.outdir = str(a.page_dir or (outdir / "pages"))
    ssum = _do_sheet(sa, shots_obj)

    result = {
        "outdir": str(outdir), "characters": str(cards_path), "shots": str(shots_path),
        "images": {k: v for k, v in isum.items() if k not in ("consistency",)},
        "consistency": rep, "sheet": ssum,
        "steps_done": steps_done, "steps_skipped": steps_skipped,
        "state": state_path,
    }
    if a.json:
        _json_out(result, a, indent=1,
                  ok=not (isum.get("failed") or isum.get("ratio_failed")
                          or isum.get("consistency_failed") or ssum.get("_fail")
                          or not rep.get("ok")))
    else:
        print("\n=== 全链路小结 ===")
        print("  角色设定卡：%s（版本 %s）" % (cards_path, cards_obj.get("version")))
        print("  分镜表：%s（%d 格）" % (shots_path, len(shots_obj.get("panels") or [])))
        print("  出图：成功 %d / 跳过 %d / 比例不合格 %d / 失败 %d，本次 %g 点"
              % (len(isum.get("completed") or []), len(isum.get("skipped_already_done") or []),
                 len(isum.get("ratio_failed") or []), len(isum.get("failed") or []),
                 isum.get("points_cost_this_run") or 0))
        print("  一致性：%s（漏词 %d 条）"
              % ("通过" if rep["ok"] else "不通过", len(rep["missing_words"])))
        print("  拼页：%d 页 → %s" % (ssum.get("pages_count") or 0, ssum.get("outdir")))
        if steps_skipped:
            print("  跳过的步骤（断点续跑）：%s" % "、".join(steps_skipped))
        print("  断点文件：%s" % state_path)

    # 退出码：先报出图的问题，再报一致性的问题
    if isum.get("failed"):
        _fail(2, "call", "%d 格出图失败" % len(isum["failed"]))
        return 2
    if isum.get("ratio_failed"):
        _fail(3, "gate", "%d 格真实比例与请求不符" % len(isum["ratio_failed"]))
        return 3
    if not rep["ok"]:
        _fail(3, "gate", "角色一致性有 %d 条特征词漏写" % len(rep["missing_words"]))
        return 3
    if ssum.get("_fail"):
        _fail(3, "gate", "拼页不完整（缺图或读不进来）")
        return 3
    return 0


# ---------------------------------------------------------------------------
# 子命令：cost / models
# ---------------------------------------------------------------------------

def cmd_cost(a):
    rec = estimate_cost(a.count, a.resolution, a.points_per_image, a.model)
    # 先定结论：估不出价、超预算都算「不放行」。发出的 JSON 里的 ok 必须与退出码一致，
    # 所以这里先算 rc，再带着 ok 输出。
    no_price = rec.get("total_points") is None
    over = (a.budget is not None and rec.get("total_points") is not None
            and rec["total_points"] > a.budget)
    if no_price:
        rc = _fail(3, "budget", "拿不到该档/该模型的可信单价，拒绝凭猜估算")
    elif over:
        rc = _fail(3, "budget", "预估成本 %g 点超过 --budget 上限 %g 点"
                    % (rec["total_points"], a.budget))
    else:
        rc = 0
    if a.json:
        if rc:
            # 失败走**标准错误信封**（kind 由 _fail 记下），估算明细放 detail 里不丢
            reason = _JSON["reason"] or {}
            err = {"kind": reason.get("kind") or _KIND_BY_EXIT.get(rc, "budget"),
                   "message": reason.get("message") or "成本前置检查未通过",
                   "detail": rec}
            _json_write(json.dumps({"ok": False, "exit": rc, "error": err},
                                   ensure_ascii=False, indent=1))
        else:
            _json_out(rec, a, indent=1, ok=True)
    else:
        print("预估成本：%s" % fmt_cost(rec))
        for n in rec.get("notes") or []:
            print("  · %s" % n)
        if a.budget is not None and rec.get("total_points") is not None:
            print("  · 预算 %g 点：%s" % (a.budget, "超了，images 会被拦下" if over else "在预算内"))
    # 估不出价也是「闸门不放行」：拿不到可信单价就往流水线里放行，等于没有成本前置。
    if no_price:
        sys.stderr.write("!! 拿不到可信单价，无法完成成本前置检查\n")
    return rc


def cmd_models(a):
    import urllib.error
    import urllib.request
    key = a7w.load_key(a.key)
    out = {}
    for label, url in (("apps", a7w.HOST + "/api/v1/apps"),
                       ("models", a7w.HOST + "/api/v1/models")):
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
    print("\n注意：平台文档里的价格字段（pricing_matrix / tenant_* / fixed_price）"
          "我们验证过半数不可信，")
    print("     结算价只认任务返回的 usage.points_cost；2K/4K 与我们没实测过的模型，"
          "本包拒绝凭猜估算。")
    print("     参数现查：python3 scripts/a7w.py schema nano_banana")
    return 0


# ---------------------------------------------------------------------------
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封（已经吐过结果的，ok 写在那个结果里）
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#
# 信封必须落在**真 stdout**：本包的 cmd_images 会在执行期间把 sys.stdout 临时换成 stderr，
# 所以 JSON 文本统一经 `_json_write` 写到进 main() 时记住的那份真 stdout。
# ---------------------------------------------------------------------------

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}

# 退出码 → 失败类别（与 SKILL.md 里公示的退出码表一致）
_KIND_BY_EXIT = {2: "call", 3: "gate", 4: "usage", 5: "interrupt", 130: "interrupt"}


def _json_payload(obj, ok=True):
    """结果对象补 ok；顶层是数组时包成 {"ok": …, "data": […] }。

    下划线开头的键是**内部标记**（`_fail` / `_wrote_json`），不进 JSON 契约。
    """
    if isinstance(obj, dict):
        out = {"ok": bool(ok)}
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            out[k] = v
        return out
    return {"ok": bool(ok), "data": obj}


def _emit(summary, a, indent=1, ok=None):
    """把命令结果按 `--json` 契约输出。

    · 早退型失败（什么都没产出）→ 标准**错误信封** `{"ok": false, "exit": N, "error": {...}}`
    · 有产出的结果 → 结果对象 + `ok`（失败时 ok=false，退出码照旧）
    """
    if not _json_want(a):
        return False
    if summary.get("_fail"):
        rc = summary.get("exit", 3)
        err = {"kind": summary.get("kind") or _KIND_BY_EXIT.get(rc, "gate"),
               "message": summary.get("error") or "命令未完成"}
        _json_write(json.dumps({"ok": False, "exit": rc, "error": err},
                               ensure_ascii=False, indent=indent))
        return True
    return _json_out(summary, a, indent=indent, ok=(True if ok is None else ok))


def _json_text(obj, indent=1, ok=True):
    return json.dumps(_json_payload(obj, ok), ensure_ascii=False, indent=indent)


def _json_write(text):
    """把 JSON 文本写到**真 stdout** 并记账（绕开 cmd_images 里的 stdout 重定向）。"""
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
    """让 `--json` 写在子命令**前后都能用**。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py shots --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_text_opts(p):
    p.add_argument("--model", default=DEFAULT_MODEL, help="文本模型，默认 %s" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--no-json-mode", action="store_true", help="不要求上游返回 JSON 对象")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 漫画分镜出图：剧本 → 角色设定卡 → 分镜表 → 逐格出图 → "
                    "跨格一致性 → 拼页；跑之前先告诉你花多少钱")
    ap.add_argument("--key", help="临时指定 api.a7w.cn 的 Key（别写进脚本或文档）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --- characters ---
    p = sub.add_parser("characters", help="从剧本抽角色设定卡（只花文本钱）")
    _add_json(p)
    p.add_argument("files", nargs="*", help="剧本文件（可多份）")
    p.add_argument("--script", help="剧本文件路径")
    p.add_argument("--title", help="剧本标题（可选，帮模型定调）")
    p.add_argument("--style", help="全篇画风口径（会给到模型）")
    p.add_argument("--max-chars", type=int, default=8, help="最多抽几个角色，默认 8")
    p.add_argument("--out", help="把设定卡写到这个 JSON 文件（shots 要用它）")
    p.add_argument("--dry-run", action="store_true", help="只打印提示词，不调模型、不花钱")
    _add_text_opts(p)
    p.set_defaults(func=cmd_characters)

    # --- shots ---
    p = sub.add_parser("shots", help="出分镜表：每格景别/机位/画面/对白（只花文本钱）")
    _add_json(p)
    p.add_argument("files", nargs="*", help="剧本文件（可多份）")
    p.add_argument("--script", help="剧本文件路径")
    p.add_argument("--characters", required=True, help="characters 产出的设定卡 JSON")
    p.add_argument("--title", help="剧本标题（可选）")
    p.add_argument("--style", help="全篇画风（不传就用设定卡里的 style_bible）")
    p.add_argument("--count", type=int, help="最多几格（截断）")
    p.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE,
                   help="每页几格，默认 %d" % DEFAULT_PER_PAGE)
    p.add_argument("--min-feature-ratio", type=float, default=1.0,
                   help="特征词覆盖率下限，默认 1.0（全部必须出现）")
    p.add_argument("--min-palette-ratio", type=float, default=0.0,
                   help="配色覆盖率下限，默认 0.0（只报告不拦）")
    p.add_argument("--out", help="把分镜表写到这个 JSON 文件（images 要用它）")
    p.add_argument("--dry-run", action="store_true", help="只打印提示词，不调模型、不花钱")
    _add_text_opts(p)
    p.set_defaults(func=cmd_shots)

    # --- consistency ---
    p = sub.add_parser("consistency", help="跨格角色一致性自检（零成本，不调接口）")
    _add_json(p)
    p.add_argument("--shots", required=True, help="分镜表 JSON")
    p.add_argument("--characters", required=True, help="角色设定卡 JSON")
    p.add_argument("--min-feature-ratio", type=float, default=1.0,
                   help="特征词覆盖率下限，默认 1.0（全部必须出现）")
    p.add_argument("--min-palette-ratio", type=float, default=0.0,
                   help="配色覆盖率下限，默认 0.0（只报告不拦）")
    p.add_argument("--report", help="把自检明细写成 JSON")
    p.set_defaults(func=cmd_consistency)

    # --- images ---
    p = sub.add_parser("images", help="逐格出图（真花钱，先报价再确认）")
    _add_json(p)
    p.add_argument("--shots", required=True, help="shots 产出的分镜表 JSON")
    p.add_argument("--characters", required=True, help="characters 产出的设定卡 JSON")
    p.add_argument("--outdir",
                   default=str(Path(os.environ.get("TEMP") or ".") / "storyboard-images"),
                   help="图片输出目录（**必须在 Skill 包外**）")
    p.add_argument("--state", help="断点文件路径，默认 <outdir>/%s" % STATE_NAME)
    p.add_argument("--count", type=int,
                   help="最多出几格（**真闸门**：在报价与提交之前就截断，少花钱）")
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--model", default="nano-banana", help="出图模型，默认 nano-banana")
    p.add_argument("--style", help="覆盖全篇画风块（不传就用分镜表里的 style_bible）")
    p.add_argument("--ref-mode", default="prev", choices=list(REF_MODES),
                   help="参考图模式：prev=参考上一格（默认，压一致性的主要手段）/ "
                        "anchor=角色锚点图 / both / none")
    p.add_argument("--anchor", action="append", metavar="ID=URL",
                   help="角色锚点图（可重复）；URL 必须是公网可访问的 http(s) 地址")
    p.add_argument("--ref-urls", action="append", metavar="URL",
                   help="额外参考图 URL（可重复）")
    p.add_argument("--budget", type=float, help="成本上限（点）：超了直接停，不提交")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--yes", action="store_true", help="确认真的花钱（不加就只报价）")
    p.add_argument("--snap", action="store_true",
                   help="出图后按请求比例精确裁剪（超容差才裁；上游按 32 对齐，5/10 种比例拿不到精确比例）")
    p.add_argument("--snap-exact", action="store_true",
                   help="只要不是像素级精确就裁准（拼页必需：格子比例不齐整页留白就不齐）")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   help="比例容差，默认 %.3f（实测最大偏差 2.86 个百分点）" % RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT,
                   help="单格轮询超时秒数，默认 %g" % POLL_TIMEOUT_DEFAULT)
    p.add_argument("--poll-interval", type=float, default=a7w.POLL_INTERVAL,
                   help="轮询间隔秒数，默认 %g" % a7w.POLL_INTERVAL)
    p.add_argument("--max-seconds", type=float, help="整批最长耗时（秒），到点中断可续跑")
    p.add_argument("--force", action="store_true", help="忽略断点，全部重出（会重复扣费）")
    p.add_argument("--no-wait", action="store_true", help="只提交不等结果（稍后用 task 续查）")
    p.add_argument("--stop-on-error", action="store_true", help="一格失败就整体停")
    p.add_argument("--allow-prompt-hits", action="store_true",
                   help="即使提示词命中违禁词/占位符/照抄示例也出图（默认拦截）")
    p.add_argument("--allow-gate-hits", action="store_true",
                   help="即使分镜结构/角色一致性不合格也出图（默认拦截）")
    p.add_argument("--min-feature-ratio", type=float, default=1.0,
                   help="特征词覆盖率下限，默认 1.0（全部必须出现）")
    p.add_argument("--min-palette-ratio", type=float, default=0.0,
                   help="配色覆盖率下限，默认 0.0（只报告不拦）")
    p.add_argument("--report", help="把本次证据（请求参数/任务原文/真实像素/一致性）写成 JSON")
    p.set_defaults(func=cmd_images)

    # --- sheet ---
    p = sub.add_parser("sheet", help="拼页/排版（本地渲染，零成本）")
    _add_json(p)
    p.add_argument("--shots", required=True, help="shots 产出的分镜表 JSON")
    p.add_argument("--state", help="images 的断点文件（从里面取每格真实下载到的文件）")
    p.add_argument("--imgdir", help="分镜图目录（从断点找不到时按 <id>-* 兜底）")
    p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".") / "storyboard-pages"),
                   help="页面输出目录（**必须在 Skill 包外**）")
    p.add_argument("--layout", default="grid", choices=list(LAYOUTS),
                   help="strip=条漫单列 / grid=页漫网格（默认 grid）")
    p.add_argument("--cols", type=int, default=2, help="网格列数，默认 2")
    p.add_argument("--rows", type=int, default=2, help="网格行数/条漫每页格数，默认 2")
    p.add_argument("--panel-w", type=int, default=580, help="单格宽（像素），默认 580")
    p.add_argument("--panel-h", type=int, default=620, help="单格高（像素），默认 620")
    p.add_argument("--gutter", type=int, default=18, help="格间距（像素），默认 18")
    p.add_argument("--margin", type=int, default=24, help="页边距（像素），默认 24")
    p.add_argument("--fit", default="contain", choices=("contain", "cover"),
                   help="contain=整格画进格子不裁画（默认）/ cover=填满格子并居中裁画")
    p.add_argument("--bg", default="#FFFFFF", help="页底色，默认 #FFFFFF")
    p.add_argument("--report", help="把拼页记录（每格落点/真实像素）写成 JSON")
    p.set_defaults(func=cmd_sheet)

    # --- all ---
    p = sub.add_parser("all", help="一条命令串全链路（断点续跑）")
    _add_json(p)
    p.add_argument("files", nargs="*", help="剧本文件（可多份）")
    p.add_argument("--script", help="剧本文件路径")
    p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".") / "storyboard-out"),
                   help="产出目录（**必须在 Skill 包外**）")
    p.add_argument("--imgdir", help="分镜图目录，默认 <outdir>/images")
    p.add_argument("--page-dir", help="页面目录，默认 <outdir>/pages")
    p.add_argument("--characters", help="复用已有的设定卡 JSON（默认 <outdir>/characters.json）")
    p.add_argument("--shots", help="复用已有的分镜表 JSON（默认 <outdir>/shots.json）")
    p.add_argument("--state", help="断点文件路径，默认 <outdir>/%s" % STATE_NAME)
    p.add_argument("--title", help="剧本标题（可选）")
    p.add_argument("--style", help="全篇画风口径")
    p.add_argument("--max-chars", type=int, default=8, help="最多抽几个角色，默认 8")
    p.add_argument("--count", type=int, help="最多几格（截断）")
    p.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE, help="每页几格")
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--text-model", default=DEFAULT_MODEL,
                   help="文本模型（抽设定卡/出分镜表），默认 %s" % DEFAULT_MODEL)
    p.add_argument("--image-model", dest="model", default="nano-banana",
                   help="出图模型，默认 nano-banana")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--no-json-mode", action="store_true", help="不要求上游返回 JSON 对象")
    p.add_argument("--ref-mode", default="prev", choices=list(REF_MODES))
    p.add_argument("--anchor", action="append", metavar="ID=URL", help="角色锚点图（可重复）")
    p.add_argument("--ref-urls", action="append", metavar="URL", help="额外参考图 URL")
    p.add_argument("--budget", type=float, help="成本上限（点）")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--yes", action="store_true", help="确认真的花钱（不加就只报价）")
    p.add_argument("--snap", action="store_true", help="出图后按请求比例精确裁剪（超容差才裁）")
    p.add_argument("--snap-exact", action="store_true",
                   help="只要不是像素级精确就裁准（拼页必需）")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT)
    p.add_argument("--poll-interval", type=float, default=a7w.POLL_INTERVAL)
    p.add_argument("--max-seconds", type=float, help="整批最长耗时（秒）")
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑（会重复扣费）")
    p.add_argument("--no-wait", action="store_true", help="只提交不等结果")
    p.add_argument("--stop-on-error", action="store_true", help="一格失败就整体停")
    p.add_argument("--allow-prompt-hits", action="store_true")
    p.add_argument("--allow-gate-hits", action="store_true")
    p.add_argument("--min-feature-ratio", type=float, default=1.0)
    p.add_argument("--min-palette-ratio", type=float, default=0.0)
    p.add_argument("--layout", default="grid", choices=list(LAYOUTS))
    p.add_argument("--cols", type=int, default=2)
    p.add_argument("--rows", type=int, default=2)
    p.add_argument("--panel-w", type=int, default=580)
    p.add_argument("--panel-h", type=int, default=620)
    p.add_argument("--gutter", type=int, default=18)
    p.add_argument("--margin", type=int, default=24)
    p.add_argument("--fit", default="contain", choices=("contain", "cover"))
    p.add_argument("--bg", default="#FFFFFF")
    p.add_argument("--report", help="把全链路证据写成 JSON")
    p.set_defaults(func=cmd_all)

    # --- cost ---
    p = sub.add_parser("cost", help="只算钱不出图")
    _add_json(p)
    p.add_argument("--count", type=int, required=True, help="要出几张/几格")
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--model", default="nano-banana", help="出图模型（影响单价）")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--budget", type=float, help="预算上限（点），超了退出码非 0")
    p.set_defaults(func=cmd_cost)

    # --- models ---
    p = sub.add_parser("models", help="列出在架应用与模型")
    _add_json(p)
    p.set_defaults(func=cmd_models)
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
    # --bg #RRGGBB → RGB 三元组（拼页用）
    if getattr(a, "bg", None) is not None:
        m = re.match(r"^#?([0-9A-Fa-f]{6})$", str(a.bg))
        if not m:
            sys.stderr.write("!! --bg 要写成 #RRGGBB，收到 %r\n" % a.bg)
            return _fail(2, "usage", "--bg 要写成 #RRGGBB")
        v = int(m.group(1), 16)
        a.bg_rgb = ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)
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
