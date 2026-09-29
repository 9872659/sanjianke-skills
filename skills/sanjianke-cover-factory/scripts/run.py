#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 封面图批量生成（sanjianke-cover-factory）。

给**一批标题 / 选题**，一条链路批量产出**各平台封面图**：

    specs   →  出方案（plan）  →  批量出图（images）  →  本地叠大字标题（overlay）
    平台规格    每张画什么 /          背景图（真花钱，      把大字标题压到图上
    零网络      大字写什么 / 放哪     先报价·断点续跑）     （PIL 本地渲染，零成本）

子命令
    specs    各平台封面规格（比例 / 目标像素 / 安全区 / 大字上限），**零网络、零成本**
    plan     按标题清单出封面方案（每张画什么、大字写什么、放哪）——只花文本钱
    images   按方案批量出背景图（真花钱，跑之前先报价并要求 --yes / --budget）
    overlay  把大字标题本地渲染到图上（**零成本、零网络**，需要 PIL）
    all      串起全流程（plan → images → overlay），断点续跑
    cost     只算钱，一次调用都不发
    models   列出 api.a7w.cn 在架的插件与模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）
    大模型       POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单     GET  https://api.a7w.cn/api/v1/models
    出图（异步） POST https://api.a7w.cn/api/v1/apps/nano_banana/submit
    任务轮询     GET  https://api.a7w.cn/api/v1/tasks/<task_id>

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py models --key sk-xxxx
    export A7W_API_KEY=sk-xxxx      # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

本包与同族两个包的边界（**改代码前先读这一段**）
    · `sanjianke-image-factory` 的输入是**一篇文章稿**，产出是文章各段的配图（封面只是其中一种角色）；
      文字一律交给出图模型写进画面（它的提示词里明确写「图上文字」）。
    · `sanjianke-xhs-note-factory` 的输入是一份母稿，产出是 N 篇笔记 + 每篇一张 3:4 封面；
      封面大字标题**也是交给模型画进画面**的（`cover_text` 进提示词），它本地只用 PIL 做裁剪。
    · 本包的输入是**一批标题清单**（不是文稿），产出是**同一个标题 × 5 个平台的封面矩阵**；
      而且**背景图与文字是分开的**：先出「无字背景图」，再用 **PIL 本地渲染**把大字标题压上去
      （字号 / 换行 / 描边 / 安全区全部本地可控），所以文字清晰度不依赖出图模型。
      同族前两个包都**没有**本地叠字的代码路径（全库 grep `ImageDraw`/`truetype` 只有裁剪）。

七道本地硬闸门（都是**拦截**：标红 + stderr 汇总 + 退出码非 0，不是"提示一下"）
    1. 合规          广告法违禁词；「最X」有可枚举的上下文豁免，**句首不许误豁免**
    2. 占位符残留    `{}`、`[待填]`、`XXX`、`（此处省略）`、`TODO`/`TBD`
    3. prompt_echo   去标点相等 / 二元组 Jaccard ≥ 0.75 / 示例覆盖度 ≥ 0.60
    4. 出图比例真伪  读**真实像素**，不许信接口自报；容差 3%（地板 0.25%），`--snap` 裁准
    5. **叠字可读性** 大字标题超长（按平台给上限）→ **拦截并报出实际长度**，
                      **绝不静默截断**；叠字框超出安全区 → 标红
    6. 成本上限      出图前必须先报价，超 `--budget` 停
    7. `--outdir`    落在包内 → exit=2（产出图不许进包，包内白名单只收文本）

设计取舍
    · 闸门判定全部在本地做确定性判定，不采信模型自评（"我检查过了"不算数）。
    · 大字标题**在花钱之前**就校验（`plan` 与 `images` 都校验）：标题太长就别出图，
      免得钱花了才发现字放不下。
    · 出图提示词**不含任何文字**（背景图 + 本地叠字），所以不给模型写错字的机会。
    · 字号由平台档位固定（不是"塞得下就无限放大"），产出可复现；塞不下就往下缩，
      缩到仍然溢出**即拦截**，不做静默截断。
    · 文本成本只出 **token**：网关不公布文本模型单价（pricing 表不含文本模型、
      models 无价格字段、usage 无 points_cost），所以**金额必须用户自填单价**。
    · 出图成本用**实测价**：nano_banana 1K = 24 点/张。2K/4K 没实测过，不给默认价。
    · 叠字是本地渲染：**有 PIL 就用 PIL**；没有 PIL 就**明确报降级（exit=2）并说明**，
      绝不静默出一张没有字的图。
"""

import argparse
import hashlib
import io
import json
import os
import re
import struct
import sys
import traceback
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w        # noqa: E402  ← 共用零依赖客户端；**逐字节等于规范版，本包不改它**
import imgprobe   # noqa: E402  ← 本包自己的图片头探针（读真实像素），独立模块

# 控制台统一按 UTF-8 输出，避免 Windows 代码页把中文和 emoji 打成乱码
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"       # 实测可用（会路由到 deepseek-flash）
CHAT_RETRIES = 4
STATE_NAME = "cover-factory-state.json"
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# nano_banana 出图应用相关（本包业务，**放在这里而不是 a7w.py**）
#
# 【约定】`scripts/a7w.py` 是所有 Skill 包共用的零依赖客户端，我们靠
# 「包内副本 SHA256 == 规范版」批量校验 60+ 个包有没有被改坏。
# 所以**任何包都不许为了自己的业务往 a7w.py 里加东西**：
#   · 需要读图片像素     → 独立模块 `imgprobe.py`（已独立）
#   · 需要应用专属的接口 → 就写在下面这一段里
#
# 平台文档写的是 `data.result.status`，**实测不对**：status 在 `data` 顶层。
# 照文档写会永远读不到状态、一路轮询到超时，所以这里按实测结构取。
# ---------------------------------------------------------------------------

APP_IMAGE = "nano_banana"                   # 出图应用编码
API_SUBMIT = "submit"                       # POST /api/v1/apps/nano_banana/submit
TASK_URL = a7w.HOST + "/api/v1/tasks/{}"    # GET  /api/v1/tasks/<task_id>（统一任务查询，实际用它）

RESOLUTIONS = ("1K", "2K", "4K")
ASPECT_RATIOS = ("auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
                 "5:4", "4:5", "21:9")
ACTIONS = ("generate", "edit")
POINTS_PER_IMAGE_1K = 24.0                  # 实测：nano_banana 1K = 24 点/张
POINTS_PER_YUAN = 100                       # 算力集市的充值比例：1 元 = 100 点
UNTESTED_RESOLUTIONS = ("2K", "4K")
POLL_TIMEOUT_DEFAULT = 600

OUT_EXT = ".png"

# ===========================================================================
# 平台封面规格（`specs` 子命令的数据源，**零网络**）
# ===========================================================================
#
# 安全区 / 字号 / 大字上限三者是**互相咬合**的，改一个要复核另外两个：
#   max_chars  = 按 font_size 在可用宽度里放得下的字数（见 `text_fits()` 自检）
#   超出 max_chars 就拦截，而不是缩小字号硬塞 —— 同族 `xhs-note-factory`
#   刚因为「静默截断」被修过，本包连"静默缩到看不清"也不做。
#
# `safe` 是**叠字安全区**（相对宽高的比例，不是绝对像素）：
#   上边界要避开平台角标，下边界要避开互动条 / 作者信息，左右要避开按钮区。
# ---------------------------------------------------------------------------

PLATFORMS = {
    "xiaohongshu": {
        "name": "小红书",
        "design_ratio": "3:4",
        "gen_ratio": "3:4",
        "target_px": "1080x1440",
        "gen_ratio_note": "",
        "max_chars": 16,
        "font_size": 80,
        "stroke": 5,
        "text_anchor": 0.58,
        "align": "center",
        "safe": {"top": 0.06, "bottom": 0.14, "left": 0.07, "right": 0.07},
        "text_pos": "居中偏下（垂直 58% 处），压在主体上方的留白里",
        "note": "竖版笔记首图。3:4 是信息流里占位最高的比例。左上角是账号角标、"
                "底部 1/8 是互动条，两块都不能放字。",
    },
    "wechat": {
        "name": "公众号",
        "design_ratio": "2.35:1",
        "gen_ratio": "21:9",
        "target_px": "900x383",
        "gen_ratio_note": "上游没有 2.35:1（最宽只到 21:9 = 2.333:1），所以用 21:9 生成、"
                          "`--snap` 居中裁到 2.35:1",
        "max_chars": 14,
        "font_size": 76,
        "stroke": 4,
        "text_anchor": 0.50,
        "align": "left",
        "safe": {"top": 0.10, "bottom": 0.14, "left": 0.05, "right": 0.05},
        "text_pos": "左侧压字区，垂直居中（分享到会话时只显示左半部分）",
        "note": "公众号头图 2.35:1（900x383）。长条形横向信息带，适合「一个主体 + 大片留白」。"
                "分享到会话时只显示左半部分，所以主体靠左中、字压左侧。",
    },
    "shipinhao": {
        "name": "视频号",
        "design_ratio": "16:9",
        "gen_ratio": "16:9",
        "target_px": "1080x608",
        "gen_ratio_note": "",
        "max_chars": 16,
        "font_size": 78,
        "stroke": 5,
        "text_anchor": 0.56,
        "align": "center",
        "safe": {"top": 0.09, "bottom": 0.13, "left": 0.06, "right": 0.06},
        "text_pos": "居中偏下，主体上方",
        "note": "视频号横版封面 16:9（1080x608）。信息流里封面高度常被压缩，"
                "所以字要大、行数要少，最多两行。",
    },
    "douyin": {
        "name": "抖音",
        "design_ratio": "9:16",
        "gen_ratio": "9:16",
        "target_px": "1080x1920",
        "gen_ratio_note": "",
        "max_chars": 14,
        "font_size": 96,
        "stroke": 6,
        "text_anchor": 0.42,
        "align": "center",
        "safe": {"top": 0.09, "bottom": 0.22, "left": 0.07, "right": 0.16},
        "text_pos": "垂直 42% 处（避开底部作者信息与右侧按钮），水平居中",
        "note": "全屏竖版 9:16（1080x1920）。下方约 20% 被作者信息 / 评论区入口遮挡，"
                "右侧约 15% 是点赞评论按钮区，主体与字都要躲开。",
    },
    "bilibili": {
        "name": "B站",
        "design_ratio": "16:9",
        "gen_ratio": "16:9",
        "target_px": "1146x717",
        "gen_ratio_note": "",
        "max_chars": 16,
        "font_size": 78,
        "stroke": 5,
        "text_anchor": 0.56,
        "align": "center",
        "safe": {"top": 0.09, "bottom": 0.13, "left": 0.06, "right": 0.06},
        "text_pos": "居中偏下，主体上方",
        "note": "B站视频封面 16:9（推荐 1146x717）。信息流里会与 UP 主名、播放量、"
                "时长角标叠在一起，主体与字都往中间收。",
    },
}

PLATFORM_CHOICES = list(PLATFORMS.keys())
DEFAULT_PLATFORMS = ["xiaohongshu", "wechat", "shipinhao", "douyin", "bilibili"]

# 上游实际能给的像素（1K 档，实测 10 种比例）。留作文档与排错依据。
MEASURED_1K_PIXELS = {
    "1:1": [1024, 1024], "3:4": [864, 1184], "4:3": [1184, 864],
    "16:9": [1344, 768], "9:16": [768, 1344], "21:9": [1536, 672],
    "2:3": [832, 1248], "3:2": [1248, 832], "4:5": [896, 1152],
    "5:4": [1152, 896],
}

# ===========================================================================
# 本地叠字：字体与字号
# ===========================================================================
#
# 【为什么要本地叠字】出图模型画中文大字基本是错的（缺笔画、错字、糊成一团）。
# 同族两个包把大字标题写进出图提示词，靠模型「画」出字来；本包改成
# **背景图无字 + 本地渲染压字**，文字清晰度就与出图模型无关了。
#
# 字体只从**系统字体**里找（不下载、不打包字体文件 —— 字体有授权问题，
# 包内也不许有字体这种二进制资源）。找不到就报降级，不静默出无字的图。
# ---------------------------------------------------------------------------

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyhbd.ttc",     # 微软雅黑 Bold（Windows 首选）
    r"C:\Windows\Fonts\msyh.ttc",       # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",     # 黑体
    r"C:\Windows\Fonts\Deng.ttf",       # 等线 Bold
    r"C:\Windows\Fonts\simsun.ttc",     # 宋体（兜底）
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
)

# 叠字可读性的**绝对**下限（像素，按 1080 宽的目标图算）。低于它就不叫大字了。
MIN_FONT_FLOOR = 36

# emoji 覆盖范围（粗判，只用于**报告**字体是否覆盖到，不做替换）
EMOJI_RANGES = (
    (0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0x1F000, 0x1F2FF),
    (0xFE00, 0xFE0F), (0x1F1E6, 0x1F1FF),
)


def has_emoji(text):
    """文本里有没有 emoji / 符号类字符。"""
    for ch in text or "":
        cp = ord(ch)
        for lo, hi in EMOJI_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def find_font(explicit=None):
    """找一个能渲染中文的系统字体。返回 (路径, 排序后的候选表)；找不到返回 (None, 表)。"""
    if explicit:
        return (explicit if Path(explicit).is_file() else None), list(FONT_CANDIDATES)
    for p in FONT_CANDIDATES:
        if Path(p).is_file():
            return p, list(FONT_CANDIDATES)
    return None, list(FONT_CANDIDATES)


# ===========================================================================
# 闸门一：比例真伪（读真实像素，不信自报值）
# ===========================================================================
#
# 事故来源：标题工坊上一版只信模型自报的 `formula` 字段做模板污染判定，
# 结果那个真该被判命的标题恰好漏判——闸门是**假绿**的。
# 同一个错误在出图场景的形态是：接口/模型自报 `aspect_ratio=3:4`，
# 但真实像素是 1024x1024。只信自报值 → 用户拿去排版才发现全错了。
#
# ⚠️ 实测到的上游特性（必须写进文档，否则闸门天天误报）：
#   上游不是按比例给像素，而是先定总像素、再把每边向下取整到 32 的倍数。
#   所以 10 种比例里有 5 种给不出像素级精确比例：
#       请求 3:4  → 864x1184   = 0.7297（3:4 = 0.75）  偏差 2.7%
#       请求 16:9 → 1344x768   = 1.7500（16:9 = 1.778）偏差 1.6%
#       请求 9:16 → 768x1344   = 0.5714（9:16 = 0.5625）偏差 1.6%
#       请求 21:9 → 1536x672   = 2.2857（21:9 = 2.333）偏差 2.0%
#       请求 4:5  → 896x1152   = 0.7778（4:5 = 0.8）    偏差 2.8%
#   精确的 5 种：1:1 / 4:3 / 2:3 / 3:2（还有非整比的 auto）
#   这**不是**网关 bug，是扩散模型按 32 对齐的常规做法。但它意味着
#   「请求比例 == 产出比例」这个断言对一半的比例天然不成立。
#
# 处理方式（三条一起用，缺一条闸门就会变成天天误报的噪音）：
#   a) 默认容差 3%：容差内不算「假」，但会**明确打印真实像素与偏差**，不藏
#   b) 超过容差 → 标红 + 计入闸门失败 + 退出码 3
#   c) `--snap`：出图后按**平台设计比例**精确裁掉多余像素，让产出真的等于设计比例
# ---------------------------------------------------------------------------

RATIO_TOLERANCE = 0.03        # 默认 3%（实测最大偏差 2.9%）
# 容差地板：**像素只能是整数**，所以「裁到精确比例」本身就有量化误差。
# 实测（--snap 之后复核）：2.35:1 裁后偏差 0.0925%；相邻整数像素间隔约 0.27%。
# 0.0025 是保守地板，仍能抓住真错：请求 3:4 却给 2:3 的偏差是 11%，比地板大 40 倍。
RATIO_TOLERANCE_FLOOR = 0.0025

# 提示词里出现过的示例文本。**新增示例必须登记到这里。**
# 这些是「跨主题」的假例子，正常不该出现在真实产出里（真实封面主题不会是这个）。
PROMPT_SAMPLES = [
    "一只黄色香蕉形状的蓝牙音箱，纯白背景，柔光棚拍，主体居中",
    "阳台上种的小番茄，清晨侧光，木质栏杆，浅景深纪实摄影",
    "a yellow banana-shaped bluetooth speaker on a pure white background, soft studio light",
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
# 可选：把产出精确裁到平台设计比例（--snap）
#
# 为什么值得做：上游按 32 对齐，3:4 实测给 864x1184（偏差 2.7%）。
# 封面比例是平台硬要求，差 2% 在 3:4 上就是 27 像素，上传后会被平台二次裁切、
# 位置不可控。与其让平台裁，不如本地裁准。
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


# ===========================================================================
# 闸门一：合规（广告法 + 平台高压线）
# ===========================================================================
#
# 【「最X」的豁免：口径照抄同族模板，一处不改】
#   命中之后再看一眼**后续几个字**：如果接的是比较 / 程度 / 常见这类用法，
#   那它是"普通中文词"而不是"最高级广告语"，放行。
#   实测依据（继承课程 / 长文生产线）：真机连跑 4 次讲义，1 次被拦，拦下的是
#     「做菜和剪辑**最大**的共同点是：先做减法，再做加法」
#   这是讲义里在讲一件常识，不是给商品贴"最大"的标签。所以加一层上下文豁免，
#   但**豁免范围写死在代码里、可枚举、可复核**，不是一句"人工判断"了事。
#
#   ⚠️ **句首不许误豁免**：只在命中处**不是行首/句首**时才豁免，
#      因为"最大区别是……"这种**句首**写法经常正是标题式的最高级宣称。
#      ——封面大字标题恰恰几乎全在句首，所以这条对本包比对同族更关键。
#
#   反过来说，`最好的工具` / `最强的` / `最高级` / `最大优惠` 这类仍然照拦：
#   它们的后文不在豁免表里。
#
# 【为什么没有为逗号/顿号开豁免】实测踩到过「找出占比最高、且最容易改的那一个环节」
# 被拦下。想放开它只有两条路，两条都不该走：
#   · 豁免表里加「且」——那是在**自行扩张模板的打分口径**，越走越松；
#   · 让分隔标点豁免生效——那样「最好的工具，值得买」也会被放行，
#     等于给最高级广告语开了一个后门（标点后面跟什么都行）。
# 所以口径是：**豁免只允许一个「的」**，与同族模板逐字一致；
# 上面那句会在闸门里被拦下，属**已知的保守行为**，靠改文案解决。
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    (r"国家级|世界级|最高级|最佳|最优|最强|第一品牌|全国第一|排名第一|销量第一", "高",
     "广告法第九条绝对化用语，封面大字与提示词都不许带"),
    (r"最[好棒优佳强低价]|最便宜|最先进|最领先|顶级|极品|绝无仅有|独一无二", "高",
     "绝对化用语，无法举证"),
    (r"100%|百分之百|百分百|全网最低|绝对(有效|安全|可靠|不会)", "高",
     "绝对化承诺，属虚假宣传高风险表述"),
    (r"国家(认证|认可|免检)|央视(推荐|上榜)|官方(推荐|指定)|权威认证", "高",
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

SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥",
)
SUPERLATIVE_OK_RE = re.compile(
    r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")

# 句首判定：命中处前面只有空白，或前一个非空白字符是句末标点/换行 → 视为句首。
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")


def _superlative_is_normal_usage(text, m):
    """「最大/最…」后面接的是比较或程度词，**且不在句首** → 判为普通用法，不拦。

    两个条件缺一不可：
      1. 后文落在可枚举的豁免表里（SUPERLATIVE_OK_AFTER）
      2. 命中处**不在句首** —— 句首的「最大区别是…」是标题式最高级宣称，照拦
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


# ===========================================================================
# 闸门二：占位符残留
# ===========================================================================
#
# 封面方案是模型吐的 JSON，模板没替换干净的形态与同族一致：
#   · `{}` / `{{标题}}`        JSON 骨架被当正文写进去了
#   · `[待填]` / `[待补充]`    模型给自己留的空档
#   · `XXX` / `xxx`            忘了替换的占位
#   · `（此处省略）`           模型懒得写，直接省略
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
    hits = []
    for rx, tag, why in PLACEHOLDER_PATTERNS:
        m = rx.search(text or "")
        if m:
            hits.append({"tag": tag, "word": m.group(0), "why": why})
    return hits


# ===========================================================================
# 闸门三：prompt_echo（照抄提示词示例）
# ===========================================================================
#
# 事故复盘（来自标题工坊的实测）：提示词里写过的示例，
# 哪怕明确标着「这是错的写法」，模型照样照抄——公众号那一轮最高分 89.0 的标题
# **一字不差就是提示词里的示例**。最高分变成「抄标准答案」，排序就废了。
#
# 出图场景下这条更隐蔽：你不会一眼看出这张图和测试用例长得一样，
# 而是「看起来挺正常」，直到发现整套封面是同一个模子。所以必须是硬闸门。
#
# 判定：去标点后相等 → 命中；字符二元组 Jaccard ≥ 0.75 → 命中；
#       示例的二元组覆盖度 ≥ 0.60 → 命中（第三条，见下）。
#
# 【为什么还要第三条】出图提示词动辄 60~120 字，示例只有 25 字，Jaccard 的分母是
# 两份二元组的**并集**，示例那一侧被长提示词摊薄得极狠 —— 示例原样塞进去也照样放行。
# 同族实测：示例原样嵌入 + 补 9 个字（34 字）→ Jaccard 0.727（旧判据放行 ❌）
# 但覆盖度 1.000（新判据拦下 ✓）；示例嵌进 102 字提示词 → Jaccard 0.245（漏）、
# 覆盖度 1.000（抓住）。覆盖度只看"示例被抄了多少"，不看提示词有多长，摊薄对它无效。
#
# 阈值 0.75 的标定依据（同族实测）：逐字照抄 1.000 / 只改标点 1.000 / 少两个字 0.840 /
# 加一个尾巴 0.857 / 同构照抄 0.778 / 英文示例近亲 0.766 —— 全部拦；
# 而真实业务提示词只有 0.042 / 0.000 —— 放行。17 倍以上安全距离。
# 覆盖度阈值的误伤侧代价为 0：17 条真实提示词里覆盖度最大只有 0.547。
#
# 长度守卫是**相对**的：max(6, len(示例)//2)，短串不比（二元组集合太小、指标虚高）。
# ---------------------------------------------------------------------------

ECHO_MIN_LEN_FLOOR = 6
ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


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
        Jaccard 会被长度摊薄，只有覆盖度抓得住）

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"。
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


def prompt_gate(prompt, where="提示词"):
    """对一个出图提示词跑三道本地检查（合规 / 占位符 / 照抄示例）。"""
    leaks = []
    for h in compliance_scan(prompt):
        leaks.append(("banned_word", "%s命中违禁词「%s」（%s 风险）：%s"
                      % (where, h["word"], h["level"], h["why"])))
    for h in placeholder_hits(prompt):
        leaks.append(("placeholder", "%s里%s" % (where, h["why"])))
    echoed, score, sample, rule = prompt_echo(prompt)
    if echoed:
        if rule == "contain":
            leaks.append(("prompt_echo",
                          "%s有 %.0f%% 的内容来自示例「%s」（覆盖度 ≥ %.2f 即判照抄／"
                          "同构改写；Jaccard 会随提示词变长被摊薄）"
                          % (where, score * 100, sample[:28], ECHO_CONTAIN)))
        else:
            leaks.append(("prompt_echo",
                          "%s与示例「%s」相似度 %.2f，属照抄/同构改写"
                          "（模型会锚定提示词里的示例）" % (where, sample[:28], score)))
    return leaks


# ===========================================================================
# 闸门五：叠字可读性（本包独有的那道）
# ===========================================================================
#
# 【事故来源 · 同族刚翻过的车】`sanjianke-xhs-note-factory` 1.0.4 及以前写的是
# `cover_text[:20]` —— **静默截断**：用户改了封面文案、付了钱重出图，
# 只有第 21 字之后被砍掉，图看起来一模一样，用户以为"我的改动生效了"。
# 1.0.5 起改成超限直接拦下（EXIT_GATE）并报出实际长度与多出来的部分。
# 本包从一开始就照修好的口径做：**超限即拦截，一个字都不许静默丢**。
#
# 【上限是怎么来的】不是拍的，是三件事算出来的：
#   1. 可用宽度 = 目标宽 × (1 - safe.left - safe.right)
#   2. 一个中文字在 PIL 里的宽度 ≈ font_size（实测：80px 字体下 16 个汉字
#      的 bbox 宽 1280px = 16 × 80，一字一格）
#   3. max_chars = 可用宽度 // font_size，再取整到一个"一眼能读完"的行数
# 所以 `text_fits()` 会在运行时用**真实字体**复核这条自洽性：
#   把 max_chars 个字符按 font_size 排版，必须落在安全区内。
# 复核不通过 = 代码与文档口径脱节，属于 bug，会以闸门形式报出来（不静默）。
#
# 【叠字超出安全区】同样标红。理论上 max_chars 已经保证放得下，
# 但 emoji / 全角标点 / 用户自定义字体都会改变实际宽度，所以渲染后**再量一次**。
# ---------------------------------------------------------------------------


def overlay_text_of(item):
    """取一条封面的**大字标题**。

    ⚠️ 这个函数存在的原因是实测踩过一次**最危险的那种 bug**：`plan_overlay` 一开始读的是
    `item["text"]`，而方案条目的结构是 `item["overlay"]["text"]` —— 读到的一直是空字符串。
    后果不是报错，而是 `wrap_text("")` 返回 `[""]`，于是：
      · 字号循环一次就通过（空文本当然放得下）
      · 渲染出来的图**一个字都没有**
      · 叠字闸门**全绿**（长度 0 当然不超限）
    也就是说 **静默产出了一张没有字的封面，还报告成功** —— 这正是本包最不允许的失败模式。
    同族教训是「静默截断」，这里是它的兄弟形态「静默留空」。
    所以取文本只有这一个入口，并且空文本在 `plan_overlay` 里会被当成硬错误报出来。
    """
    ov = item.get("overlay") or {}
    for k in ("text", "cover_text"):
        v = ov.get(k) if isinstance(ov, dict) else None
        if isinstance(v, str) and v.strip():
            return v
    for k in ("text", "cover_text", "title"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def text_width(font, s):
    """量一段文字的真实像素宽。

    ⚠️ 两个坑都实测踩过：
      · `font.getbbox()` 在某些字形上会返回 `None`（PIL 未渲染时），
        `None[2]` 直接抛 `TypeError`；也可能返回 `(0,0,0,0)`（例如字体里没有这个字形）。
      · 老版本 PIL 没有 `getbbox`，只有 `getsize`。
    这里把三条路都兜住，取不到就返回 0（宁可判"窄"，也不要崩在渲染阶段）。
    """
    try:
        bb = font.getbbox(s)
        if bb:
            return max(0, bb[2] - bb[0])
    except Exception:
        pass
    try:
        return max(0, font.getsize(s)[0])
    except Exception:
        return 0


def safe_rect(plat, width=None, height=None):
    """算平台的叠字安全区（像素矩形）。不传宽高就按平台目标像素算。"""
    if width is None or height is None:
        width, height = target_size(plat)
    s = PLATFORMS[plat]["safe"]
    return {
        "left": int(round(width * s["left"])),
        "right": int(round(width * (1.0 - s["right"]))),
        "top": int(round(height * s["top"])),
        "bottom": int(round(height * (1.0 - s["bottom"]))),
    }


def text_fits(text, plat, font_path=None):
    """闸门五的**确定性预检**：`max_chars` 这个口径在真实字体下自洽吗？

    返回 dict：ok / n_chars / limit / overflow / width_px / safe_w / why
    只做长度与宽度的算术，不加载字体也能用（font_path 给了就用真字体量）。
    """
    spec = PLATFORMS[plat]
    limit = spec["max_chars"]
    text = text or ""
    n = len(text)
    rec = {"text": text, "n_chars": n, "limit": limit,
           "overflow": max(0, n - limit), "ok": n <= limit, "why": ""}
    if not rec["ok"]:
        rec["why"] = ("大字标题 %d 字，超过 %s 上限 %d 字（多出 %d 字：%s）"
                      % (n, spec["name"], limit, rec["overflow"], text[limit:]))
    return rec


def glyph_height(font):
    """字形的实际高度（不带上/下行留白）。

    `font.getmetrics()` 给的是 `(ascent, descent)`，两者相加比字形本身高出一截
    （实测 76px 字：85+21=106，而字形只有 80）。用它当行距会让多行文字比排版框高，
    字就画到框外面去了 —— 所以行距与框高统一走这个函数。
    """
    try:
        bb = font.getbbox("字测国")          # 用几个"满格"汉字量
        if bb:
            return max(1, bb[3] - bb[1])
    except Exception:
        pass
    try:
        asc, desc = font.getmetrics()
        return max(1, asc + desc - max(4, (asc + desc) // 8))
    except Exception:
        return 1


def measure_lines(lines, font, stroke_width=0):
    """量一组已经断好行的文本的真实像素宽高（含描边）。

    ⚠️ 高度口径必须与 `render_overlay` 的行距**一致**（都用 `glyph_height`），
    否则"框"和"字"两个尺寸来自两套算法，多行就会溢出（实测踩过）。
    """
    if not lines:
        return 0, 0
    line_h = glyph_height(font)
    width = 0
    for ln in lines:
        width = max(width, text_width(font, ln))
    height = line_h * len(lines) + 4 * max(0, len(lines) - 1)
    pad = 2 * stroke_width
    return width + pad, height + pad


def wrap_text(text, font, max_width):
    """按字符贪心断行（中文封面不需要词级断行），返回行列表。

    **不截断**：断不下的字符照样留在最后一行，由闸门去报"超了"。
    空文本返回 `[""]`（由调用方按"没有大字标题"报错，不在这里静默吞掉）。
    """
    lines, cur = [], ""
    for ch in text or "":
        trial = cur + ch
        w = text_width(font, trial)
        if cur and w > max_width:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur or not lines:
        lines.append(cur)
    return lines


def plan_overlay(item, font_path=None, probe_pil=True):
    """把一条「叠字任务」算成可渲染的排版方案（字号 / 断行 / 位置 / 安全区）。

    返回 dict，`ok` 为 False 时 `why` 说明原因：
      · 大字标题超长 → kind="text_too_long"（闸门五，拦）
      · 系统里没有中文字体 → kind="no_font"（降级，exit=2）
      · 字体缩小到地板上限仍放不下 → kind="no_fit"（闸门五，拦）
    `safe_ok` 为 False 表示渲染框越出安全区（标红）。
    """
    plat = item["platform"]
    spec = PLATFORMS[plat]
    text = overlay_text_of(item)
    rec = {"id": item.get("id"), "platform": plat, "platform_name": spec["name"],
           "text": text, "n_chars": len(text), "limit": spec["max_chars"],
           "ok": True, "safe_ok": True, "kind": "", "why": "",
           "font": None, "font_size": None, "lines": [], "box": None,
           "safe_rect": None, "image_px": None}
    # ⚠️ 空大字标题 = 硬错误。**绝不**继续渲染出一张没有字的图（见 overlay_text_of 的注释）。
    if not text.strip():
        rec["ok"] = False
        rec["kind"] = "empty_text"
        rec["why"] = ("没有大字标题（`overlay.text` 与 `title` 都是空）—— "
                      "**拒绝产出一张没有字的封面**，请先在方案里给标题")
        return rec
    d = text_fits(text, plat)
    if not d["ok"]:
        rec["ok"] = False
        rec["kind"] = "text_too_long"
        rec["why"] = d["why"] + "。**不截断**——把超出的部分移到正文，或拆成两张封面"
        return rec

    if not probe_pil:
        return rec
    try:
        from PIL import ImageFont  # noqa
    except ImportError:
        rec["ok"] = False
        rec["kind"] = "no_font"
        rec["why"] = ("没有 PIL，无法本地叠中文大字（纯标准库渲染不了中文点阵）")
        return rec

    path, candidates = find_font(font_path)
    if not path:
        rec["ok"] = False
        rec["kind"] = "no_font"
        rec["why"] = ("系统里没找到可用的中文字体，试过：%s。"
                      "用 --font 指定一个中文字体文件（.ttf/.ttc/.otf）"
                      % " / ".join(candidates[:4]))
        return rec
    rec["font"] = path

    w, h = target_size(plat)
    safe = safe_rect(plat, w, h)
    rec["safe_rect"] = safe
    rec["image_px"] = [w, h]
    avail_w = safe["right"] - safe["left"]
    avail_h = safe["bottom"] - safe["top"]

    size = int(spec["font_size"])
    stroke = int(spec["stroke"])
    floor = MIN_FONT_FLOOR
    chosen = None
    while size >= floor:
        try:
            font = ImageFont.truetype(path, size)
        except Exception as exc:
            rec["ok"] = False
            rec["kind"] = "no_font"
            rec["why"] = "字体 %s 打不开：%s" % (path, exc)
            return rec
        lines = wrap_text(text, font, avail_w - 2 * stroke)
        bw, bh = measure_lines(lines, font, stroke)
        if len(lines) <= 3 and bw <= avail_w and bh <= avail_h:
            chosen = (size, font, lines, bw, bh)
            break
        size -= 2
    if not chosen:
        rec["ok"] = False
        rec["kind"] = "no_fit"
        rec["why"] = ("%s 的大字标题在 %dx%d 上缩小到 %dpx 仍然放不下"
                      "（安全区 %dx%d）：**不静默缩小**，请减少字数或拆两张"
                      % (spec["name"], w, h, floor, avail_w, avail_h))
        return rec

    size, font, lines, bw, bh = chosen
    box = layout_box(plat, safe, bw, bh, w, h, stroke)
    rec.update({"font_size": size, "lines": lines, "box": box,
                "box_px": [bw, bh], "stroke_width": stroke,
                "align": PLATFORMS[plat].get("align", "center"),
                "anchor_y_ratio": PLATFORMS[plat].get("text_anchor", 0.5)})
    # 渲染框必须落在安全区里，否则标红（闸门五的第二条）
    if (box[0] < safe["left"] or box[2] > safe["right"]
            or box[1] < safe["top"] or box[3] > safe["bottom"]):
        rec["safe_ok"] = False
        rec["ok"] = False
        rec["kind"] = "outside_safe"
        rec["why"] = ("叠字框 %s 越出安全区 %s（%s）"
                      % (box, [safe["left"], safe["top"], safe["right"], safe["bottom"]],
                         spec["name"]))
    return rec


def layout_box(plat, safe, bw, bh, want_w, want_h, stroke=0):
    """算叠字块的像素框。

    水平：按平台的 `align`（`center` / `left`）——公众号要**压左侧**，因为分享到会话时
          只显示左半部分；竖版/横版封面居中。
    垂直：按 `text_anchor`（h 的比例），再夹进安全区，保证框完整落在里面。

    ⚠️ `stroke` 要留出内缩：实测把左对齐的框直接钉在 `safe["left"]` 上时，
    第一笔的外描边正好落在边界上、**看起来像被切掉半个字**（真机截图确认过）。
    所以左对齐时额外内缩一个描边宽度 + 2px 阴影偏移。居中时对称，不用管。
    """
    align = PLATFORMS[plat].get("align", "center")
    inset = int(stroke) + 2
    if align == "left":
        # 左边内缩两个描边宽（外描边 + 阴影各占一份），右边同样留一点
        span = max(1, safe["right"] - safe["left"] - 2 * inset)
        if bw > span:
            return [safe["left"] + inset, safe["top"], safe["left"] + inset + bw,
                    safe["top"] + bh]
        x0 = safe["left"] + inset
    else:
        x0 = (safe["left"] + safe["right"]) // 2 - bw // 2
    cy = int(round(want_h * float(PLATFORMS[plat].get("text_anchor", 0.5))))
    cy = min(max(cy, safe["top"] + bh // 2), safe["bottom"] - bh // 2)
    return [x0, cy - bh // 2, x0 + bw, cy + bh // 2]


def target_size(plat):
    """平台的目标产出像素（从 `target_px` 解析）。"""
    txt = PLATFORMS[plat].get("target_px") or "1080x1080"
    a, _, b = txt.partition("x")
    try:
        return int(a), int(b)
    except ValueError:
        return 1080, 1080


# ===========================================================================
# 叠字渲染（PIL 本地渲染；没有 PIL 就明确降级）
# ===========================================================================

# 各平台默认配色（大字色 / 描边色 / 可选底板色）。用户可以 --text-color / --stroke-color 覆盖。
PALETTE = {
    "xiaohongshu": {"text": "#FFFFFF", "stroke": "#1F1F1F", "badge": None},
    "wechat":      {"text": "#FFFFFF", "stroke": "#12263A", "badge": None},
    "shipinhao":   {"text": "#FFFFFF", "stroke": "#101010", "badge": None},
    "douyin":      {"text": "#FFFFFF", "stroke": "#0A0A0A", "badge": None},
    "bilibili":    {"text": "#FFFFFF", "stroke": "#0A0A0A", "badge": None},
}


def _hex_rgb(s, default=(255, 255, 255)):
    s = (s or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return default
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return default


def render_overlay(src, dst, spec_rec, text_color=None, stroke_color=None,
                   shadow=True, font_path=None):
    """把大字标题渲染到 src 上，写出 dst。

    返回 dict：ok / why / out_px / box / font / font_size / lines / shadow
    **渲染后复量一次输出像素**（闸门：产出必须等于目标像素）。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa
    except ImportError:
        return {"ok": False, "kind": "no_font",
                "why": "没有 PIL：本地叠中文大字需要 PIL（pip install pillow）。"
                       "**拒绝静默产出一张没有字的图**"}

    plat = spec_rec["platform"]
    path = font_path or spec_rec.get("font")
    if not path:
        return {"ok": False, "kind": "no_font", "why": "没有可用的中文字体"}

    want_w, want_h = target_size(plat)
    try:
        im = Image.open(src)
    except Exception as exc:
        return {"ok": False, "kind": "call", "why": "打不开底图 %s：%s" % (src, exc)}

    # 底图若不是目标像素，先按比例缩放到目标尺寸（叠字前统一画布）
    if im.size != (want_w, want_h):
        try:
            im = im.convert("RGB").resize((want_w, want_h), Image.LANCZOS)
        except Exception as exc:
            return {"ok": False, "kind": "call", "why": "缩放底图失败：%s" % exc}
    else:
        im = im.convert("RGB")

    size = int(spec_rec["font_size"])
    stroke = int(spec_rec.get("stroke_width") or PLATFORMS[plat]["stroke"])
    font = ImageFont.truetype(path, size)

    # ⚠️ 用 `overlay_text_of` 取文本（不是 `spec_rec["text"]` 就直接用）：
    #    字体文件可能与 plan 阶段不同，口径以实际渲染为准；文本统一走同一个入口。
    otext = spec_rec.get("text") or overlay_text_of({"overlay": spec_rec})
    if not str(otext).strip():
        return {"ok": False, "kind": "empty_text",
                "why": "没有大字标题 —— **拒绝产出一张没有字的封面**"}

    # 用**真实字体重新断行**
    safe = safe_rect(plat, want_w, want_h)
    avail_w = safe["right"] - safe["left"]
    lines = wrap_text(otext, font, avail_w - 2 * stroke)
    bw, bh = measure_lines(lines, font, stroke)
    # 渲染后再量一次：断出来的行**必须**比安全区窄，否则如实报出来（不静默画出去）
    if bw > avail_w or bh > (safe["bottom"] - safe["top"]):
        return {"ok": False, "kind": "no_fit",
                "why": ("大字标题 %d 字在 %dpx 下渲染出 %dx%d 像素，超出安全区 %dx%d —— "
                        "**不静默画出安全区**，请减少字数或调大平台安全区"
                        % (len(str(otext)), size, bw, bh, avail_w,
                           safe["bottom"] - safe["top"]))}
    box = layout_box(plat, safe, bw, bh, want_w, want_h, stroke)
    align = PLATFORMS[plat].get("align", "center")

    pal = PALETTE.get(plat, {})
    fill = _hex_rgb(text_color, _hex_rgb(pal.get("text"), (255, 255, 255)))
    sc = _hex_rgb(stroke_color, _hex_rgb(pal.get("stroke"), (0, 0, 0)))

    dr = ImageDraw.Draw(im, "RGBA")
    # ⚠️ 行距必须由 `measure_lines` **同一套口径**算出来，否则框按 A 算、字按 B 排：
    #    旧写法用 `asc+desc`（85+21=106）当行距，而 measure_lines 用字形高度（80），
    #    两行时字就比框高出 26px、画到框外面去。这里统一按"字形高 + 4px 余量"。
    line_h = glyph_height(font) + 4
    top = box[1] + stroke
    for i, ln in enumerate(lines):
        lw = text_width(font, ln)
        # `align=left` 时 box[0] 是**左边界**（不是中心），必须直接用；
        # 早期写成 `box[0] - lw//2` 会把整行字画到画布外面（真机实测：x 变成负数）。
        x = box[0] if align == "left" else box[0] + (bw - lw) // 2
        y = top + i * line_h
        if shadow:
            # 先画一层偏移的深色描边，再画白字 —— 亮背景上也能读
            dr.text((x + 2, y + 2), ln, font=font, fill=(0, 0, 0, 140),
                    stroke_width=stroke, stroke_fill=(0, 0, 0, 140))
        dr.text((x, y), ln, font=font, fill=fill,
                stroke_width=stroke, stroke_fill=sc)

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    if str(dst).lower().endswith((".jpg", ".jpeg")):
        im.save(dst, quality=92)
    else:
        im.save(dst)

    out_px = imgprobe.image_size(dst)
    return {"ok": True, "out_px": [out_px[0], out_px[1]], "want_px": [want_w, want_h],
            "box": box, "font": path, "font_size": size, "lines": lines,
            "stroke_width": stroke, "shadow": bool(shadow),
            "fill": "#%02X%02X%02X" % fill, "stroke_fill": "#%02X%02X%02X" % sc,
            "safe_ok": (box[0] >= safe["left"] and box[2] <= safe["right"]
                        and box[1] >= safe["top"] and box[3] <= safe["bottom"])}


# ===========================================================================
# 成本
# ===========================================================================

def unit_points(resolution, override=None):
    """单张成本（点）。只有 1K 有实测价；2K/4K 不给默认值。"""
    if override is not None:
        return float(override)
    if (resolution or "1K").upper() == "1K":
        return float(POINTS_PER_IMAGE_1K)
    return None


def estimate_cost(count, resolution="1K", override=None):
    """出图成本预估。2K/4K 没实测价 → points 为 None（**拒绝估算**）。"""
    pts = unit_points(resolution, override)
    rec = {"count": int(count), "resolution": resolution,
           "points_per_image": pts, "total_points": None, "total_yuan": None,
           "measured": (resolution or "1K").upper() == "1K" and override is None}
    if pts is not None:
        rec["total_points"] = round(pts * count, 2)
        rec["total_yuan"] = round(pts * count / float(POINTS_PER_YUAN), 2)
    return rec


def fmt_cost(rec):
    if rec["total_points"] is None:
        return ("%d 张 × %s：**没有实测单价，拒绝估算**（只有 1K 有实测价 24 点/张）。"
                "给 --points-per-image 指定单价后才能算" % (rec["count"], rec["resolution"]))
    tag = "实测价" if rec["measured"] else "指定价"
    return ("%d 张 × %g 点/张（%s，%s）= **%g 点 = %.2f 元**"
            % (rec["count"], rec["points_per_image"], rec["resolution"], tag,
               rec["total_points"], rec["total_yuan"]))


# ===========================================================================
# 接口封装
# ===========================================================================

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


def download(url, dst, timeout=180, key=None, retries=3):
    """把图下载到 dst（零依赖）。

    ⚠️ **不要走 `a7w._request` 下图片**，它有两个坑，两个都实测踩过：
      1. `_request(..., raw=X)` 里的 `raw` 是**原始请求体**，不是"要原始响应"。
         传 `raw=True` 会让 `headers["Content-Type"] = None`，`putheader` 直接抛
         `TypeError: expected string or bytes-like object, got 'NoneType'`；
         就算绕过去，`_request` 末尾做的是 `json.loads(resp.read())` —— **PNG 不是 JSON**。
      2. 传 `key=None` 时它会做 `"Bearer " + key` → `TypeError: can only concatenate
         str (not "NoneType") to str`。发生在**图已经出好、钱已经扣了**之后，最亏。
    所以这里自带一小段 urllib 下载：拿字节、不解析 JSON、Key 走 `a7w.load_key` 兜底、
    网络类错误退避重试。**它就是本包自己的业务代码，不污染共用的 a7w.py。**
    """
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + (a7w.load_key(key) or ""),
                      "Accept": "image/*,*/*"})
    last = None
    for attempt in range(max(1, retries)):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                blob = resp.read()
            if not blob:
                raise a7w.A7wError("下载到的内容是空的：%s" % url)
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_bytes(blob)
            return len(blob)
        except urllib.error.HTTPError as exc:
            raise a7w.A7wError("下载图片失败（HTTP %s）：%s" % (exc.code, url))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
    raise a7w.A7wError("下载图片失败（已重试 %d 次）：%s（%s）" % (retries, url, last))


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, json_mode=True, retries=CHAT_RETRIES):
    """一次文本调用（OpenAI 兼容）。返回 (content, usage)。"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"model": model, "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(retries):
        try:
            payload = a7w._request("POST", CHAT_URL, a7w.load_key(key), body=body, timeout=300)
            if isinstance(payload, dict) and payload.get("choices"):
                content = ((payload["choices"][0].get("message") or {}).get("content")) or ""
                return content, payload.get("usage") or {}
            last = a7w.A7wError("模型没返回 choices：%s" % json.dumps(
                payload, ensure_ascii=False)[:200])
        except a7w.A7wError as exc:
            last = exc
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
    raise last or a7w.A7wError("文本调用失败")


def parse_first_json(text):
    """从模型输出里抠出第一个完整 JSON 对象（前后有多余字符也能救）。"""
    if not text:
        raise a7w.A7wError("模型返回为空")
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except ValueError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, _ = dec.raw_decode(s[i:])
                return obj
            except ValueError:
                continue
    raise a7w.A7wError("模型返回的不是合法 JSON（前 200 字：%s）" % s[:200])


# ===========================================================================
# 方案生成（plan）
# ===========================================================================

SYSTEM_PROMPT = (
    "你是三剪客的内容封面设计助手，为「同一个标题 × 多个平台」产出封面出图方案。\n"
    "硬性要求：\n"
    "1. 只输出 JSON 对象，不要解释、不要 Markdown 代码块。\n"
    "2. `desc` 是**画面**描述：写清主体、构图、光线、色调、质感，95~150 个中文字。\n"
    "   **绝对不许描述任何文字、字母、数字、logo、水印**——大字标题由本地渲染压上去，\n"
    "   背景图必须是**纯画面、无字**。\n"
    "3. `keywords` 给 3~6 个英文或中文的**视觉关键词**（不要句子）。\n"
    "4. `colors` 给 2~3 个十六进制色值（形如 #1B3A4B），作为整套封面的统一色板。\n"
    "5. 不许出现广告法绝对化用语（最 / 第一 / 国家级 / 100% 之类），\n"
    "   不许出现占位符（{} / [待填] / XXX），不许编造不存在的品牌或数据。\n"
    "6. 同一批里所有封面必须**同一色板、同一光线方向、同一画风**，避免风格打架。"
)


def build_plan_prompt(titles, platforms, style=None, brief=None):
    """构造出方案的用户提示词。

    ⚠️ 这里**不出现任何一句可复制的完整中文画面描述**（举例只用描述性语言），
    示例一律登记在 `PROMPT_SAMPLES` 里并由闸门兜底 —— 这是 prompt_echo 事故的直接对策。
    """
    lines = []
    lines.append("下面是 %d 个标题，请为每个标题在指定平台上各出一张封面的画面方案。"
                 % len(titles))
    lines.append("")
    lines.append("标题清单：")
    for i, t in enumerate(titles, 1):
        lines.append("  %d. %s" % (i, t))
    lines.append("")
    lines.append("目标平台（每个标题每个平台各一条）：")
    for p in platforms:
        spec = PLATFORMS[p]
        lines.append("  · %s（%s）：比例 %s，目标像素 %s。构图提示：%s"
                     % (p, spec["name"], spec["design_ratio"], spec["target_px"],
                        spec["note"]))
    lines.append("")
    if style:
        lines.append("统一视觉风格（必须遵守）：%s" % style)
    else:
        lines.append("统一视觉风格：2 个主色 + 1 个点缀色、同一光线方向、同一画风"
                     "（例如「干净的实拍质感」或「扁平插画」），相邻两张构图不重复。")
    if brief:
        lines.append("作者补充要求：%s" % brief)
    lines.append("")
    lines.append("输出 JSON，形如（把 <> 里的内容换成你的实际内容，不要照抄这段结构以外的东西）：")
    lines.append('{"covers": [{"title": "<标题原文，一字不改>", "platform": "<平台 key>",')
    lines.append('             "desc": "<95~150 字的画面描述，纯画面、无任何文字>",')
    lines.append('             "keywords": ["<视觉关键词>", "..."],')
    lines.append('             "colors": ["#RRGGBB", "#RRGGBB"]}]}')
    lines.append("")
    lines.append("条数必须正好是 %d 条（%d 个标题 × %d 个平台），"
                 "`title` 必须与标题清单里的写法**完全一致**，`platform` 必须是上面列的 key。"
                 % (len(titles) * len(platforms), len(titles), len(platforms)))
    return "\n".join(lines)


def build_background_prompt(item):
    """把模型给的画面要素拼成**最终出图提示词**（不含任何文字）。

    拼装放在本地做（而不是让模型直接给成品提示词），是为了让"无字"这条约束
    由脚本保证，不依赖模型自觉。
    """
    spec = PLATFORMS[item["platform"]]
    parts = [item.get("desc") or ""]
    if item.get("keywords"):
        parts.append("关键词：" + "、".join(item["keywords"]))
    if item.get("colors"):
        parts.append("主色调：" + "、".join(item["colors"]))
    parts.append("比例 %s，目标像素 %s" % (spec["design_ratio"], spec["target_px"]))
    parts.append("构图位置：%s" % spec["text_pos"])
    parts.append("**画面中不要出现任何文字、字母、数字、水印、logo**")
    parts.append("高清、干净、主体明确、留白充足，适合作为封面底图")
    return "，".join(p.strip("，,。 ") for p in parts if p)


def norm_title(s):
    return re.sub(r"\s+", "", str(s or "")).strip()


def normalize_plan(obj, titles, platforms, style=None):
    """把模型返回归一化成方案条目，并跑**闸门二 / 闸门三**。

    返回 (items, notes)；items 里的每一项都带 `leaks`（本地闸门命中）。
    """
    if isinstance(obj, dict) and isinstance(obj.get("covers"), list):
        raw = obj["covers"]
    elif isinstance(obj, list):
        raw = obj
    else:
        raw = []
    want = {}
    for t in titles:
        for p in platforms:
            want[(norm_title(t), p)] = t
    items, notes = [], []
    seen = set()
    for n, r in enumerate(raw, 1):
        if not isinstance(r, dict):
            continue
        title = r.get("title") or r.get("topic") or ""
        plat = str(r.get("platform") or "").strip()
        if plat not in PLATFORMS:
            notes.append("第 %d 条的 platform=%r 不认识，已跳过" % (n, plat))
            continue
        key = (norm_title(title), plat)
        if key in seen:
            continue
        seen.add(key)
        spec = PLATFORMS[plat]
        desc = str(r.get("desc") or r.get("description") or "").strip()
        kws = [str(k).strip() for k in (r.get("keywords") or []) if str(k).strip()]
        cols = [str(c).strip() for c in (r.get("colors") or []) if str(c).strip()]
        overlay_text = want.get(key, title)
        item = {
            "id": "%s-%02d" % (plat[:4], len(items) + 1),
            "title": str(title),
            "platform": plat,
            "platform_name": spec["name"],
            "design_ratio": spec["design_ratio"],
            "gen_ratio": spec["gen_ratio"],
            "resolution": "1K",
            "model": "nano-banana",
            "target_px": spec["target_px"],
            "desc": desc,
            "keywords": kws[:6],
            "colors": cols[:3],
            "overlay": {"text": overlay_text, "pos": spec["text_pos"],
                        "font_size": spec["font_size"], "stroke": spec["stroke"],
                        "max_chars": spec["max_chars"],
                        "safe": spec["safe"]},
            "leaks": [],
        }
        item["prompt"] = build_background_prompt(item)
        item["leaks"] = prompt_gate(item["prompt"], "出图提示词")
        # 叠字可读性（闸门五）在方案阶段就查 —— 标题超标就别出图，免得白花钱
        fit = text_fits(item["overlay"]["text"], plat)
        if not fit["ok"]:
            item["leaks"].append(("text_too_long", fit["why"]))
        items.append(item)
    # 补齐模型漏掉的条目（用中性画面描述，并标出"需要人工确认"）
    for t in titles:
        for p in platforms:
            if (norm_title(t), p) in seen:
                continue
            spec = PLATFORMS[p]
            item = {
                "id": "%s-%02d" % (p[:4], len(items) + 1),
                "title": t, "platform": p, "platform_name": spec["name"],
                "design_ratio": spec["design_ratio"], "gen_ratio": spec["gen_ratio"],
                "resolution": "1K", "model": "nano-banana",
                "target_px": spec["target_px"],
                "desc": "干净简洁的主体特写，大面积留白，柔和自然光，色调统一，质感真实",
                "keywords": ["minimal", "clean"], "colors": ["#F5F5F5", "#2B2B2B"],
                "overlay": {"text": t, "pos": spec["text_pos"],
                            "font_size": spec["font_size"], "stroke": spec["stroke"],
                            "max_chars": spec["max_chars"], "safe": spec["safe"]},
                "leaks": [], "synthesized": True,
            }
            item["prompt"] = build_background_prompt(item)
            item["leaks"] = prompt_gate(item["prompt"], "出图提示词")
            fit = text_fits(item["overlay"]["text"], p)
            if not fit["ok"]:
                item["leaks"].append(("text_too_long", fit["why"]))
            items.append(item)
            notes.append("模型漏了「%s / %s」，已用中性画面描述补齐（建议人工确认）"
                         % (t, spec["name"]))
    return items, notes


# ===========================================================================
# 断点续跑
# ===========================================================================
#
# ⚠️ **断点 key 必须含全部影响产出的维度**，这是同族踩过三次的地方：
#   · 内容截断：`_norm_for_echo(prompt)[:24]` → 提示词只改第 25 字之后时 key 不变
#     → **静默复用旧图**（同族 longform-factory 实测踩过）
#   · `resolution` 不入 key：先跑 1K、改成 4K 重跑 → 复用 1K 的图，用户以为拿到 4K
#   · 死参数：key 里的维度与实际请求无关时，改了参数 key 不变 → 还是静默复用
#
# 本包的出图产出由 6 个维度决定，**一个都不能少**：
#   提示词全文摘要（不是前缀截断） + 比例 + resolution + 模型 + **叠字内容** + **叠字样式**
# 后两维是本包特有的：这就是「标题清单驱动 + 本地叠字」的直接后果 ——
# 只改了大字标题（背景图一个字没改）也必须重出，否则图上的字是旧的。
#
# 另外，命中 key 之后还会**逐维复核**记录里的值（同族口径）：
# 说不清来历的旧记录一律重出，绝不静默复用。
# ---------------------------------------------------------------------------

def prompt_digest(prompt):
    """提示词**全文**摘要（归一化后 sha1 前 16 位十六进制）。

    绝不用 `prompt[:N]`：那样只改后半句时 key 不变。
    """
    return hashlib.sha1(_norm_for_echo(prompt).encode("utf-8")).hexdigest()[:16]


def overlay_style_sig(item, font_path=None):
    """叠字样式签名：字体 + 内容 + 描边 + 位置。改任一项都要重出。"""
    ov = item.get("overlay") or {}
    plat = item["platform"]
    payload = "|".join([
        str(ov.get("text") or ""),
        plat,
        str(ov.get("font_size") or PLATFORMS[plat]["font_size"]),
        str(ov.get("stroke") or PLATFORMS[plat]["stroke"]),
        str(ov.get("pos") or ""),
        str(font_path or ""),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def img_state_key(item, font_path=None):
    """出图断点 key：提示词摘要 + 比例 + 分辨率 + 模型 + 叠字内容与样式。"""
    return "img:%s:%s:%s:%s:%s" % (
        item["id"], item["gen_ratio"], item.get("resolution") or "1K",
        item.get("model") or "nano-banana",
        overlay_style_sig(item, font_path))


def overlay_state_key(img_path, item, font_path=None, text_color=None,
                      stroke_color=None, shadow=True):
    """叠字断点 key：底图路径 + 叠字内容与样式 + 颜色 + 阴影。

    ⚠️ 底图进了 key：换了底图就必须重新叠字（否则新底图上是旧字）。
    """
    payload = "|".join([
        str(img_path), overlay_style_sig(item, font_path),
        str(text_color or ""), str(stroke_color or ""), "1" if shadow else "0",
    ])
    return "ov:%s:%s" % (item["id"], hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16])


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


# ===========================================================================
# JSON 契约（--json）
# ===========================================================================

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None,
         # `trace` = 本次退出码非 0 时，命令自己**已经**吐过一个完整 JSON 了
         # （典型的：命令跑完了、产出也给了，只是闸门判定不合格 → 结果里 ok=false）。
         # ⚠️ 实测踩过：报价阶段（exit=4）曾经"先吐报价 JSON、再补失败信封"，
         #    于是 stdout 上出现**两个 JSON 文档**，`json.loads` 直接
         #    `Extra data: line N column 1` —— 把「stdout 只有一个 JSON」这条不变量打破了。
         # 退出码语义一个字不变，只是不再画蛇添足补信封。
         "trace": False}

# 退出码 → 失败类别（与 SKILL.md 里公示的退出码表一致）
_KIND_BY_EXIT = {2: "usage", 3: "gate", 4: "call", 5: "interrupt", 130: "interrupt"}


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
    """把 JSON 文本写到**真 stdout** 并记账（绕开可能的 stdout 重定向）。"""
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
    _JSON["trace"] = True
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

    只写 stdout（真 stdout）；完整 traceback 由 main() 的兜底层原样打到 stderr。
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
    """让 `--json` 写在子命令**前后都能用**（与同族模板同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py plan --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


# ===========================================================================
# 通用工具
# ===========================================================================

def _red(s, force_plain=False):
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "!! " + s
    return "\033[31m" + s + "\033[0m"


def ensure_outside_pkg(outdir):
    """`--outdir` 在包内 → 抛 UsageError（exit=2）。

    包内不许有任何图片：SkillHub 的上传白名单只收
    `.md .py .txt .json .sh .js .yaml .yml .csv`，图片会让上传 400。
    """
    pkg_dir = Path(__file__).resolve().parent.parent
    try:
        Path(outdir).resolve().relative_to(pkg_dir)
    except ValueError:
        return
    raise UsageError(
        "输出目录 %s 在 Skill 包内（%s）。包内不许有任何图片——上传白名单只收文本，"
        "请换到包外，例如 %s"
        % (Path(outdir).resolve(), pkg_dir,
           Path(os.environ.get("TEMP") or ".") / "cover-factory-out"))


class UsageError(a7w.A7wError):
    """用法错误（退出码 2）。"""


class GateError(a7w.A7wError):
    """硬闸门命中（退出码 3）。"""


def _load_titles(a):
    """标题清单来源：`--file` 一份文本（每行一个标题）/ `--text` 逗号分隔 / 位置参数。"""
    titles = []
    for f in (getattr(a, "files", None) or []):
        p = Path(f)
        if not p.is_file():
            raise UsageError("找不到标题清单文件：%s" % f)
        titles.extend(_split_lines(p.read_text(encoding="utf-8-sig", errors="replace")))
    if getattr(a, "file", None):
        p = Path(a.file)
        if not p.is_file():
            raise UsageError("找不到标题清单文件：%s" % a.file)
        titles.extend(_split_lines(p.read_text(encoding="utf-8-sig", errors="replace")))
    if getattr(a, "text", None):
        titles.extend(_split_lines(a.text.replace("，", "\n").replace(",", "\n")))
    out, seen = [], set()
    for t in titles:
        t = t.strip().lstrip("-*0123456789.、) ").strip()
        if not t or t.startswith("#"):
            continue
        k = norm_title(t)
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _split_lines(text):
    return [ln for ln in (text or "").splitlines()]


def _resolve_platforms(names):
    out = []
    for n in (names or DEFAULT_PLATFORMS):
        key = str(n).strip()
        if key not in PLATFORMS:
            raise UsageError("未知平台 %r；可选：%s" % (key, " / ".join(PLATFORM_CHOICES)))
        if key not in out:
            out.append(key)
    return out


def _require_plan(a):
    p = Path(a.plan)
    if not p.is_file():
        raise UsageError("找不到方案文件：%s（先用 `plan` 生成）" % a.plan)
    try:
        obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise UsageError("方案文件不是合法 JSON：%s（%s）" % (a.plan, exc))
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list) or not items:
        raise UsageError("方案文件里没有 items：%s（先用 `plan` 生成）" % a.plan)
    return obj, items


# ===========================================================================
# 子命令：specs
# ===========================================================================

def cmd_specs(a):
    rows = []
    for key in _resolve_platforms(a.platform or PLATFORM_CHOICES):
        s = PLATFORMS[key]
        w, h = target_size(key)
        safe = safe_rect(key, w, h)
        avw = safe["right"] - safe["left"]
        avail_chars = avw // s["font_size"]
        font, cands = find_font(a.font)
        fit_ok = None
        if font:
            try:
                from PIL import ImageFont
                f = ImageFont.truetype(font, s["font_size"])
                probe = "字" * s["max_chars"]
                lines = wrap_text(probe, f, avw - 2 * s["stroke"])
                bw, bh = measure_lines(lines, f, s["stroke"])
                fit_ok = (len(lines) <= 3 and bw <= avw
                          and bh <= (safe["bottom"] - safe["top"]))
            except Exception:
                fit_ok = None
        rows.append({
            "key": key, "name": s["name"],
            "design_ratio": s["design_ratio"], "gen_ratio": s["gen_ratio"],
            "target_px": s["target_px"], "gen_ratio_note": s["gen_ratio_note"],
            "safe": s["safe"], "safe_px": [safe["left"], safe["top"],
                                           safe["right"], safe["bottom"]],
            "font_size": s["font_size"], "stroke": s["stroke"],
            "max_chars": s["max_chars"],
            "avail_width_px": avw,
            "avail_chars_at_font_size": avail_chars,
            "max_chars_selfcheck_ok": fit_ok,
            "text_pos": s["text_pos"], "note": s["note"],
        })
    bad_fit = [r for r in rows if r["max_chars_selfcheck_ok"] is False]
    font, cands = find_font(a.font)
    if a.json:
        _json_out({"version": VERSION, "font": font, "font_candidates": cands,
                   "platforms": rows,
                   "max_chars_selfcheck_bad": [r["key"] for r in bad_fit]},
                  a, indent=1, ok=not bad_fit)
        return 0 if not bad_fit else _fail(
            3, "gate", "口径自检未通过：%s 的 max_chars 在该字号下放不进安全区"
            % " / ".join(r["key"] for r in bad_fit))
    print("三剪客 · 封面图批量生成 —— 各平台封面规格（v%s）" % VERSION)
    print("零网络、零成本；口径与 scripts/run.py 的 PLATFORMS 表一致。\n")
    for r in rows:
        print("【%s】%s" % (r["name"], r["key"]))
        print("  比例        %s（生成用 aspect_ratio=%s）%s"
              % (r["design_ratio"], r["gen_ratio"],
                 "  ← " + r["gen_ratio_note"] if r["gen_ratio_note"] else ""))
        print("  目标像素    %s" % r["target_px"])
        print("  叠字安全区  px[%d,%d,%d,%d]  比例 tof%.2f bot%.2f l%.2f r%.2f"
              % (r["safe_px"][0], r["safe_px"][1], r["safe_px"][2], r["safe_px"][3],
                 r["safe"]["top"], r["safe"]["bottom"], r["safe"]["left"], r["safe"]["right"]))
        print("  大字        %dpx 字号 / 描边 %dpx / **上限 %d 字**（超了拦截，不截断）"
              % (r["font_size"], r["stroke"], r["max_chars"]))
        print("  可用宽度    %dpx（这个字号一行放得下约 %d 个汉字；%d 字上限会折成 %s 行）"
              % (r["avail_width_px"], r["avail_chars_at_font_size"], r["max_chars"],
                 "2" if r["max_chars"] > r["avail_chars_at_font_size"] else "1"))
        print("  大字位置    %s" % r["text_pos"])
        print("  要点        %s" % r["note"])
        print()
    print("字体：%s" % (font or "**没有找到可用的中文字体** —— overlay 会报降级（exit=2）"))
    if font:
        print("  （可用 --font 指定其他字体文件）")
    if bad_fit:
        print()
        print(_red("口径自检未通过：%s 的 max_chars 在该字号下放不进安全区"
                   % " / ".join(r["key"] for r in bad_fit)))
        return _fail(3, "gate", "口径自检未通过：%s"
                     % " / ".join(r["key"] for r in bad_fit))
    return 0


# ===========================================================================
# 子命令：plan
# ===========================================================================

def cmd_plan(a):
    platforms = _resolve_platforms(a.platform)
    titles = _load_titles(a)
    if not titles:
        raise UsageError('请给标题清单：--file 标题.md（每行一个）或 --text "标题1，标题2"')
    titles = titles[:max(1, a.titles)]
    prompt = build_plan_prompt(titles, platforms, a.style, a.brief)
    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "system": SYSTEM_PROMPT, "user": prompt,
                       "titles": titles, "platforms": platforms}, a, indent=1)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (SYSTEM_PROMPT, prompt))
        return 0
    sys.stderr.write("正在用 `%s` 出封面方案（%d 个标题 × %d 个平台 = %d 张）…\n"
                     % (a.model, len(titles), len(platforms),
                        len(titles) * len(platforms)))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    items, notes = normalize_plan(parse_first_json(content), titles, platforms, a.style)
    if not items:
        raise a7w.A7wError("模型没产出任何封面条目")
    plan = {"version": VERSION, "titles": titles, "platforms": platforms,
            "style": a.style, "model": a.model, "usage": usage,
            "elapsed_sec": round(elapsed, 1), "count": len(items),
            "items": items, "notes": notes}
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(plan, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    bad = [it for it in items if it["leaks"]]
    if a.json:
        _json_out(plan, a, indent=1, ok=not bad)
    else:
        _render_plan(plan)
    cost = estimate_cost(len(items), "1K", a.points_per_image)
    tail = "\n预估出图成本（这一步还没出图，只花了文本钱）：\n  %s\n" % fmt_cost(cost)
    if a.json:
        sys.stderr.write(tail)
    else:
        print(tail.rstrip())
    if a.out and not a.json:
        sys.stderr.write("方案已写入 %s\n" % a.out)
    if notes:
        for n in notes:
            sys.stderr.write("  · %s\n" % n)
    if bad:
        _report_leaks(bad)
        return _fail(3, "gate", "闸门：有 %d 条封面方案命中（见 stderr）" % len(bad))
    sys.stderr.write("usage: %s\n" % json.dumps(usage, ensure_ascii=False))
    return 0


def _report_leaks(bad):
    """标红 + stderr 汇总（硬闸门的统一出口）。"""
    sys.stderr.write("\n")
    for it in bad:
        for kind, why in it["leaks"]:
            sys.stderr.write("   %s %s\n" % (_red("[%s]" % kind), why))
    sys.stderr.write("\n%s\n" % _red(
        "共 %d 条封面方案命中硬闸门，**已拦截，未提交任何任务（不花一分钱）**。\n"
        "改标题 / 改画面描述后重跑；叠字超长请把超出的字移到正文或拆成两张。"
        % len(bad)))


def _render_plan(plan):
    print("封面方案：%d 个标题 × %d 个平台 = %d 张"
          % (len(plan["titles"]), len(plan["platforms"]), plan["count"]))
    print("标题：" + "；".join(plan["titles"]))
    print("平台：" + "、".join(PLATFORMS[p]["name"] for p in plan["platforms"]))
    print("模型：%s   耗时：%.1fs" % (plan["model"], plan["elapsed_sec"]))
    print()
    for it in plan["items"]:
        print("#%-4s %-8s %-6s %s  → %s"
              % (it["id"], it["platform_name"], it["gen_ratio"],
                 it["target_px"], it["overlay"]["text"]))
        print("      画什么：%s" % it["desc"])
        if it["keywords"]:
            print("      关键词：%s" % "、".join(it["keywords"]))
        if it["colors"]:
            print("      色板：%s" % " ".join(it["colors"]))
        print("      大字写什么：%s" % it["overlay"]["text"])
        print("      大字放哪：%s（%dpx 字号 / 描边 %dpx / 上限 %d 字）"
              % (it["overlay"]["pos"], it["overlay"]["font_size"],
                 it["overlay"]["stroke"], it["overlay"]["max_chars"]))
        print("      出图提示词：%s" % it["prompt"])
        for kind, why in it["leaks"]:
            print("      " + _red("[%s] %s" % (kind, why)))
        print()


# ===========================================================================
# 子命令：cost
# ===========================================================================

def cmd_cost(a):
    if a.titles and a.platform:
        n = a.titles * len(_resolve_platforms(a.platform))
    elif a.count:
        n = a.count
    else:
        raise UsageError("请给 --count（几张），或同时给 --titles N --platform p1 --platform p2")
    rec = estimate_cost(n, a.resolution, a.points_per_image)
    over = None
    if rec["total_points"] is None:
        exit_code = 3
        msg = fmt_cost(rec)
    elif a.budget is not None and rec["total_points"] > a.budget:
        exit_code = 3
        msg = "%s，**超过 --budget %g 点**：images / all 会在提交前被拦下" % (
            fmt_cost(rec), a.budget)
        over = True
    else:
        exit_code = 0
        msg = fmt_cost(rec)
    if a.json:
        _json_out({"cost": rec, "budget": a.budget, "over_budget": over}, a,
                  indent=1, ok=(exit_code == 0))
    else:
        print(msg)
        if a.budget is not None and not over and rec["total_points"] is not None:
            print("预算 %g 点：在预算内" % a.budget)
    if exit_code:
        return _fail(exit_code, "gate" if over else "budget", msg)
    return 0


# ===========================================================================
# 子命令：models
# ===========================================================================

def cmd_models(a):
    apps = a7w._unwrap(a7w._request("GET", a7w.HOST + "/api/v1/apps",
                                    a7w.load_key(a.key))) or {}
    models = a7w._unwrap(a7w._request("GET", a7w.HOST + "/api/v1/models",
                                      a7w.load_key(a.key))) or {}
    app_list = apps if isinstance(apps, list) else (apps.get("data") or apps.get("list") or [])
    out = {"host": a7w.HOST, "apps_count": len(app_list), "apps": [], "models": models}
    for it in app_list:
        if not isinstance(it, dict):
            continue
        out["apps"].append({"code": it.get("code") or it.get("app") or it.get("slug"),
                            "name": it.get("name") or it.get("title")})
    if a.json:
        _json_out(out, a, indent=1)
        return 0
    print("在架应用 %d 个：" % out["apps_count"])
    for it in out["apps"][:30]:
        print("  %-24s %s%s" % (it["code"], it["name"],
                                "   ← 本包用这个" if it["code"] == APP_IMAGE else ""))
    print()
    print("出图模型（`nano_banana` 的 model 参数可选值，实测）：")
    for m in ("nano-banana", "nano-banana-2:official", "nano-banana-2-lite:official",
              "nano-banana-pro:official"):
        print("  %s" % m)
    print()
    print("注意：平台文档里的价格字段（pricing_matrix / tenant_*）我们验证过半数不可信，")
    print("     结算价只认任务返回的 usage.points_cost。")
    return 0


# ===========================================================================
# 子命令：images
# ===========================================================================

def _iter_selected(items, a):
    """按 --platform / --count / --only 过滤（顺序保持方案里的顺序）。"""
    sel = items
    if a.platform:
        plats = _resolve_platforms(a.platform)
        sel = [it for it in sel if it["platform"] in plats]
    if a.only:
        ids = {s.strip() for s in a.only.split(",") if s.strip()}
        sel = [it for it in sel if it["id"] in ids or it["title"] in ids]
    if a.count:
        sel = sel[:a.count]
    return sel


def _quote_lines(sel, cost, a, outdir):
    """报价文案（人读）。返回行列表，由调用方决定写 stdout 还是 stderr。

    ⚠️ `--json` 下**必须写 stderr**：stdout 上只允许有一个 JSON 文档。
    实测踩过：`all --json` 在报价阶段把这份人读文案打到了 stdout，
    于是 `json.loads` 报 `Extra data: line 40 column 1` —— 契约被破坏。
    """
    lines = ["本次要出 %d 张背景图 → %s" % (len(sel), outdir),
             "  " + fmt_cost(cost)]
    for it in sel:
        lines.append("  #%-5s %-8s %-6s %s" % (it["id"], it["platform_name"],
                                               it["gen_ratio"], it["title"]))
    if a.budget is not None:
        ok = (cost["total_points"] is not None and cost["total_points"] <= a.budget)
        lines.append("  预算 %g 点：%s" % (a.budget, "在预算内" if ok else "超了，会被拦下"))
    return lines


def _print_quote(sel, cost, a, outdir, to_stderr=False):
    out = sys.stderr if to_stderr else sys.stdout
    for ln in _quote_lines(sel, cost, a, outdir):
        out.write(ln + "\n")


def _gates_for_images(a, sel, font_path=None):
    """闸门五：叠字可读性（**在花钱之前**判）+ 每张的提示词闸门。

    ⚠️ 这里也走 `overlay_text_of()`：实测 `plan_overlay` 曾经读错字段，
    闸门读到空串 → 长度 0 → 全绿 → 静默出一张没字的封面。取文本只能有一个入口。
    """
    bad = []
    for it in sel:
        leaks = list(it.get("leaks") or [])
        text = overlay_text_of(it)
        if not text.strip():
            leaks.append(("empty_text",
                          "没有大字标题：**拒绝在花钱之前放过**（否则会出一张没字的封面）"))
        fit = text_fits(text, it["platform"])
        if not fit["ok"]:
            leaks.append(("text_too_long", fit["why"]))
        if leaks:
            bad.append({"id": it["id"], "platform_name": it["platform_name"],
                        "title": it.get("title"), "leaks": leaks})
    return bad


def cmd_images(a):
    plan_obj, items = _require_plan(a)
    sel = _iter_selected(items, a)
    if not sel:
        raise UsageError("按 --platform/--count/--only 过滤后没有可出的条目")
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    resolution = a.resolution or "1K"
    for it in sel:
        it["resolution"] = resolution
    cost = estimate_cost(len(sel), resolution, a.points_per_image)

    # ---- 闸门五：叠字可读性（**在花钱之前**）----
    bad = _gates_for_images(a, sel, a.font)
    if bad and not a.allow_prompt_hits:
        if a.json:
            _json_out({"stage": "gate", "count": len(bad), "blocked": bad}, a,
                      indent=1, ok=False)
        sys.stderr.write("\n")
        for b in bad:
            for kind, why in b["leaks"]:
                if kind == "text_too_long":
                    sys.stderr.write("   %s #%s %s\n" % (_red("[%s]" % kind),
                                                         b["id"], why))
        sys.stderr.write("\n%s\n" % _red(
            "共 %d 张的叠字标题超过平台上限，**已拦截，未提交任何任务（不花一分钱）**。\n"
            "上限按平台给（见 `specs`）；**不接受 --allow-prompt-hits 放行超长大字**——\n"
            "放行等于回到静默截断，你会以为改了、其实图上的字是残的。"
            % len([b for b in bad
                   if any(k == "text_too_long" for k, _ in b["leaks"])])))
        return _fail(3, "gate", "闸门五：有 %d 张的叠字标题超长，未提交任何任务" % len(bad))

    # ---- 闸门六：成本上限（**在提交任何任务之前**）----
    if cost["total_points"] is None:
        msg = ("%s 档没有实测单价，**拒绝凭猜估算**（只有 1K 有实测价 24 点/张）。"
               "给 --points-per-image 指定单价，或先用 1K 出。" % resolution)
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(3, "budget", msg)
    if a.budget is not None and cost["total_points"] > a.budget:
        msg = ("预估 %g 点超过预算上限 %g 点，**已中断，未提交任何任务**"
               % (cost["total_points"], a.budget))
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(3, "budget", msg)

    need_yes = not a.yes and a.budget is None
    if need_yes or a.dry_run:
        if a.dry_run and not a.json:
            _print_quote(sel, cost, a, outdir)
        if a.json:
            # 报价文案一律走 stderr，stdout 只留那一个 JSON
            for ln in _quote_lines(sel, cost, a, outdir):
                sys.stderr.write(ln + "\n")
            _json_out({"stage": "quote", "outdir": str(outdir), "cost": cost,
                       "items": [{"id": it["id"], "platform": it["platform"],
                                  "gen_ratio": it["gen_ratio"],
                                  "title": it["title"]} for it in sel]},
                      a, indent=1, ok=not need_yes)
        if a.dry_run:
            return 0
        sys.stderr.write("\n**这是一次真花钱的操作。**\n\n")
        if not a.json:
            _print_quote(sel, cost, a, outdir)
        sys.stderr.write("\n确认后加 --yes 重跑（或用 --budget 设上限）。\n")
        return _fail(4, "call", "需要 --yes 确认（还没花钱，也没提交）")

    if not a.json:
        _print_quote(sel, cost, a, outdir)
    else:
        for ln in _quote_lines(sel, cost, a, outdir):
            sys.stderr.write(ln + "\n")
    sys.stderr.write("\n开始出图…\n")
    return _run_images(a, sel, plan_obj, outdir, cost, resolution)


def _finish_item(it, url, pts, path, nbytes):
    """把一条出图结果落到条目上（正常路径与「补下载」路径共用）。"""
    it["bg_path"] = str(path)
    it["points_cost"] = pts
    it["bg_url"] = url
    it["bg_bytes"] = nbytes


def _recover_unfinished(a, it, prev, outfile, key, state, spath):
    """断点里是 `submitted`（已提交、已预冻结）→ **续查 task_id，绝不重新提交**。

    这条路以前只有「轮询超时 / 任务还在跑」会走。实测又补了一种：
    **任务已经 completed，但下载那一步崩了**（`download` 传了 None 当 key）——
    断点里只有 task_id、没有 image_url，重跑如果直接重提交就是**白扣一次费**。
    所以这里先按 task_id 续查：completed 就直接下载入库（0 点），
    还像上次是因为 task_id 已经查不到（平台清理了任务）才回落到重新提交。
    """
    if not (prev and prev.get("status") == "submitted" and not a.force):
        return None, False
    tid = prev.get("task_id")
    if not tid:
        return None, False
    sys.stderr.write("  #%s 断点里已有 task_id=%s（已提交，不重复提交），续查结果…\n"
                     % (it["id"], tid))
    try:
        status, tdata, _payload, _ticks = poll_task(tid, a.key, 5)
    except a7w.A7wError as exc:
        sys.stderr.write("    #%s 续查失败（%s）—— 任务可能已被平台清理，重新提交\n"
                         % (it["id"], exc))
        return None, False
    if status != "completed":
        sys.stderr.write("    #%s 任务状态 %s，未完成；重新提交\n" % (it["id"], status))
        return None, False
    urls = find_image_urls(tdata)
    if not urls:
        sys.stderr.write("    #%s 任务已完成但没有图片地址；重新提交\n" % it["id"])
        return None, False
    nbytes = download(urls[0], outfile, timeout=180, key=a.key)
    pts = points_cost(tdata)
    state["items"][key].update({"status": "completed", "path": str(outfile),
                                "image_url": urls[0], "points_cost": pts,
                                "bytes": nbytes, "completed_at": time.time()})
    save_state(spath, state)
    sys.stderr.write("    #%s 补下载成功（%s 点，%d 字节，**没有再提交、没有重复扣费**）\n"
                     % (it["id"], pts, nbytes))
    return pts, True


def _finalize_image(it, outdir, a, nbytes):
    """真正的收尾：读真实像素 → `--snap` 裁到平台设计比例 → 复核。

    返回 (rec, final_rec)。`rec["ok"]` 就是闸门四的结论。
    """
    outfile = outdir / ("%s_%s%s" % (it["id"], it["platform"], OUT_EXT))
    raw_rec = check_ratio(outfile, it["gen_ratio"], a.ratio_tolerance)
    design_rec = None
    snapped = None
    if it["design_ratio"] != it["gen_ratio"]:
        design_rec = check_ratio(outfile, it["design_ratio"], a.ratio_tolerance)
    if a.snap:
        snapped_to = outfile.with_name(outfile.stem + "_snap" + outfile.suffix)
        got = snap_to_ratio(outfile, snapped_to, it["design_ratio"])
        if got:
            how, cbox = got
            recheck = check_ratio(snapped_to, it["design_ratio"], a.ratio_tolerance)
            snapped = {"how": how, "box": list(cbox), "recheck": recheck}
            if recheck["ok"]:
                try:
                    os.replace(str(snapped_to), str(outfile))
                    snapped["applied"] = True
                except OSError as exc:
                    snapped["applied"] = False
                    snapped["why"] = "裁好了但替换原文件失败：%s" % exc
            else:
                snapped["applied"] = False
                snapped["why"] = "裁完复核仍不合格：%s" % recheck["why"]
        else:
            snapped = {"how": None, "recheck": None, "applied": False,
                       "why": "没有 PIL，内置裁剪器也不支持这张图 —— 如实报告「没能裁」"}
    final_rec = check_ratio(outfile, it["design_ratio"]
                            if (snapped and snapped.get("applied")) else it["gen_ratio"],
                            a.ratio_tolerance)
    rec = {"real_px": final_rec["real_px"], "real_label": final_rec["real_label"],
           "deviation": final_rec["deviation"], "ok": final_rec["ok"],
           "why": final_rec["why"], "gen_ratio": it["gen_ratio"],
           "request_ratio": (it["design_ratio"] if (snapped and snapped.get("applied"))
                             else it["gen_ratio"]),
           "design_ratio": it["design_ratio"],
           "gen_check": raw_rec, "design_check_before_snap": design_rec,
           "snap": snapped, "bytes": nbytes, "file": str(outfile)}
    return rec, final_rec


def _run_images(a, sel, plan_obj, outdir, cost, resolution):
    spath = Path(a.state) if a.state else (outdir / STATE_NAME)
    state = load_state(spath)
    state.setdefault("items", {})
    spent = 0.0
    recovered_points = 0.0
    done, skipped, failed, ratio_bad, ratio_ok = [], [], [], [], []
    t_start = time.time()
    n = len(sel)
    for idx, it in enumerate(sel, 1):
        key = img_state_key(it, a.font)
        prev = state["items"].get(key)
        # 逐维复核（同族口径）：记录里的值与本次不一致就重出，绝不静默复用旧图
        if prev:
            same_prompt = (prev.get("prompt_digest") == prompt_digest(it["prompt"]))
            same_style = (prev.get("overlay_sig") == overlay_style_sig(it, a.font))
            same_res = (str(prev.get("resolution") or "").upper() == resolution.upper())
            if not (same_prompt and same_style and same_res):
                sys.stderr.write("    #%s 断点记录与本次不一致（提示词/叠字样式/分辨率）"
                                 "→ **不复用旧图**，重新出图\n" % it["id"])
                prev = None
        if prev and prev.get("status") == "completed" and not a.force:
            pts = prev.get("points_cost")
            if isinstance(pts, (int, float)):
                # 跳过的那张上一次已经真扣过费 —— 记进"来自断点"的账，**不算本次花费**
                recovered_points += float(pts)
            skipped.append(it)
            sys.stderr.write("  [%d/%d] #%s 已完成，跳过（上次扣费 %s 点，不再重复扣）\n"
                             % (idx, n, it["id"], pts))
            _finish_item(it, prev.get("image_url"), pts, prev.get("path") or "",
                         prev.get("bytes"))
            it["task_id"] = prev.get("task_id")
            # ⚠️ 跳过也要**重新读一遍真实像素**，不能直接沿用断点里存的复核结论：
            #    断点文件可能是手工改过的、图也可能被外部替换过 —— 那就成了"假绿"。
            if Path(it["bg_path"]).is_file():
                rec, _final = _finalize_image(it, outdir, a, prev.get("bytes") or 0)
            else:
                rec = {"ok": False, "why": "断点里的文件不存在：%s" % it["bg_path"],
                       "real_px": None, "deviation": None}
            it["ratio"] = rec
            if rec.get("ok"):
                ratio_ok.append(rec)
            else:
                ratio_bad.append((it, rec))
            done.append(it)
            continue
        if a.max_seconds and (time.time() - t_start) > a.max_seconds:
            msg = "达到 --max-seconds %g 上限，已中断；已完成的都在断点文件里，重跑可续" \
                  % a.max_seconds
            sys.stderr.write("\n%s\n" % _red(msg))
            save_state(spath, state)
            return _fail(5, "interrupt", msg)

        outfile = outdir / ("%s_%s%s" % (it["id"], it["platform"], OUT_EXT))

        # 断点里是 submitted（已提交、已预冻结）→ **续查 task_id，绝不重新提交**
        pts, recovered = _recover_unfinished(a, it, prev, outfile, key, state, spath)
        if recovered:
            rec, final_rec = _finalize_image(it, outdir, a, Path(outfile).stat().st_size)
            it["ratio"] = rec
            # ⚠️ 补下载的那张钱是**上一轮**扣的，不能算进"本次花了多少"，
            #    否则用户会以为重跑又扣了一次（实测第一次跑就踩在这一点上）。
            if isinstance(pts, (int, float)):
                recovered_points += float(pts)
            _finish_item(it, prev.get("image_url"), pts, outfile,
                         Path(outfile).stat().st_size)
            done.append(it)
            if rec["ok"]:
                ratio_ok.append(rec)
            else:
                ratio_bad.append((it, rec))
            continue

        # 每张提交前**再核一次**预算（真实扣费可能比预估高）
        if a.budget is not None and spent + (cost["points_per_image"] or 0) > a.budget:
            msg = ("已花 %g 点，再出下一张会超过 --budget %g 点，**就地停止**"
                   % (spent, a.budget))
            sys.stderr.write("\n%s\n" % _red(msg))
            save_state(spath, state)
            return _fail(3, "budget", msg)

        try:
            data = submit_image(it["prompt"], aspect_ratio=it["gen_ratio"],
                                resolution=resolution, model=it["model"], key=a.key)
            task_id = (data or {}).get("task_id")
            if not task_id:
                raise a7w.A7wError("提交后没有拿到 task_id：%s"
                                   % json.dumps(data, ensure_ascii=False)[:200])
            state["items"][key] = {
                "status": "submitted", "task_id": task_id,
                "prompt_digest": prompt_digest(it["prompt"]),
                "overlay_sig": overlay_style_sig(it, a.font),
                "resolution": resolution, "gen_ratio": it["gen_ratio"],
                "model": it["model"], "id": it["id"], "title": it["title"],
                "platform": it["platform"], "frozen_points": (data or {}).get("frozen_points"),
                "submitted_at": time.time(),
            }
            save_state(spath, state)
        except a7w.A7wError as exc:
            failed.append((it, str(exc)))
            sys.stderr.write("  [%d/%d] #%s 提交失败：%s\n" % (idx, n, it["id"], exc))
            if a.stop_on_error:
                save_state(spath, state)
                return _fail(4, "call", "提交失败且指定了 --stop-on-error：%s" % exc)
            continue

        if a.no_wait:
            sys.stderr.write("  [%d/%d] #%s 已提交，不等待：task_id=%s\n"
                             % (idx, n, it["id"], task_id))
            continue
        status, tdata, _payload, ticks = poll_task(task_id, a.key, a.poll_timeout)
        if status == "timeout":
            sys.stderr.write("  [%d/%d] #%s 轮询超时（task_id=%s 已记进断点，重跑可续查）\n"
                             % (idx, n, it["id"], task_id))
            failed.append((it, "轮询超时"))
            continue
        if status != "completed":
            failed.append((it, "任务终态 %s" % status))
            sys.stderr.write("  [%d/%d] #%s 任务失败：%s\n" % (idx, n, it["id"], status))
            continue
        urls = find_image_urls(tdata)
        if not urls:
            failed.append((it, "任务完成但没有图片地址"))
            sys.stderr.write("  [%d/%d] #%s 没有图片地址\n" % (idx, n, it["id"]))
            continue
        pts = points_cost(tdata)
        # ⚠️ 先把 task_id / image_url 落盘**再**下载：下载失败也能靠断点续查补图，
        #    不会因为"崩在最后一步"而白扣一次费（实测踩过这个坑）。
        state["items"][key].update({"status": "submitted", "task_id": task_id,
                                    "image_url": urls[0], "points_cost": pts})
        save_state(spath, state)
        try:
            nbytes = download(urls[0], outfile, timeout=180, key=a.key)
        except a7w.A7wError as exc:
            failed.append((it, "下载失败：%s" % exc))
            sys.stderr.write("  [%d/%d] #%s 下载失败：%s（task_id 与 image_url 已记进断点，"
                             "重跑会**补下载**而不是重新提交）\n"
                             % (idx, n, it["id"], exc))
            continue

        rec, final_rec = _finalize_image(it, outdir, a, nbytes)
        if rec["ok"]:
            ratio_ok.append(rec)
        else:
            ratio_bad.append((it, rec))
            sys.stderr.write("  %s #%s 比例不合格：%s\n"
                             % (_red("[比例]"), it["id"], rec["why"]))

        state["items"][key].update({
            "status": "completed", "path": str(outfile), "image_url": urls[0],
            "points_cost": pts, "bytes": nbytes, "ratio": rec,
            "completed_at": time.time(),
        })
        save_state(spath, state)
        if isinstance(pts, (int, float)):
            spent += float(pts)
        _finish_item(it, urls[0], pts, outfile, nbytes)
        it["bg_bytes"] = nbytes
        it["task_id"] = task_id
        it["ratio"] = rec
        done.append(it)
        sys.stderr.write(
            "  [%d/%d] #%s 完成 %s（%s 点，%d 字节，轮询 %d 次）\n"
            % (idx, n, it["id"], final_rec["real_label"], pts, nbytes, ticks))
        if not rec["ok"] and a.stop_on_error:
            save_state(spath, state)
            return _fail(3, "gate", "比例不合格且指定了 --stop-on-error")

    save_state(spath, state)
    summary = {"outdir": str(outdir), "state": str(spath),
               "requested": len(sel), "completed": len(done),
               "skipped": len(skipped), "failed": len(failed),
               "ratio_ok": len(ratio_ok), "ratio_bad": len(ratio_bad),
               "points_spent_this_run": round(spent, 2),
               "yuan_spent_this_run": round(spent / float(POINTS_PER_YUAN), 2),
               "points_recovered_from_breakpoint": round(recovered_points, 2),
               "points_total_of_outputs": round(spent + recovered_points, 2),
               "items": [{"id": it["id"], "platform": it["platform"],
                          "title": it["title"], "file": it.get("bg_path"),
                          "points_cost": it.get("points_cost"),
                          "ratio": it.get("ratio")} for it in done],
               "failures": [{"id": it["id"], "why": why} for it, why in failed]}
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    if a.json:
        _json_out(summary, a, indent=1, ok=(not failed and not ratio_bad))
    else:
        print("\n出图完成：交付 %d 张（断点跳过 %d 张，失败 %d 张）"
              % (len(done), len(skipped), len(failed)))
        print("本次共扣 **%g 点 = %.2f 元**；另有 %g 点来自断点里上一轮已扣的图（未重复扣费）"
              % (spent, spent / float(POINTS_PER_YUAN), recovered_points))
        print("断点文件：%s（重跑同一条命令不会重复扣费）" % spath)
    if ratio_bad:
        sys.stderr.write("\n")
        for it, rec in ratio_bad:
            sys.stderr.write("   %s #%s %s\n" % (_red("[比例]"), it["id"], rec["why"]))
        sys.stderr.write("\n%s\n" % _red(
            "闸门四：有 %d 张的真实像素比例超容差（%.1f%%），加 --snap 可裁到平台设计比例"
            % (len(ratio_bad), RATIO_TOLERANCE * 100)))
        return _fail(3, "gate", "闸门四：%d 张比例不合格" % len(ratio_bad))
    if failed:
        return _fail(4, "call", "有 %d 张出图失败（重跑可用断点续查）" % len(failed))
    return 0


# ===========================================================================
# 子命令：overlay
# ===========================================================================

def _iter_bg(items, outdir, only=None):
    """找出已经出好的底图（断点记录里的 path 存在才算）。"""
    out = []
    for it in items:
        if only and it["id"] not in only and it["title"] not in only:
            continue
        for cand in (it.get("bg_path"), str(Path(outdir) / ("%s_%s%s"
                                                            % (it["id"], it["platform"], OUT_EXT)))):
            if cand and Path(cand).is_file():
                out.append((it, str(cand)))
                break
    return out


def cmd_overlay(a):
    plan_obj, items = _require_plan(a)
    sel = _iter_selected(items, a)
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ---- 没有 PIL：**明确降级**（exit=2），绝不静默出一张没有字的图 ----
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa
    except ImportError:
        msg = ("本地叠字需要 PIL（`pip install pillow`）。**没有 PIL 就没有降级渲染路径** —— "
               "纯标准库渲染不了中文大字（没有点阵字库、也没法把 TTF 字形栅格化）。\n"
               "本包**拒绝静默产出一张没有字的图**：那会让你以为叠字成功了。\n"
               "两条出路：① 装上 PIL 后原样重跑（底下背景图不用重出，不重复扣费）；"
               "② 用 `images` 只出无字背景图，把大字标题交给你的设计工具。")
        if a.json:
            _json_out({"stage": "overlay", "degraded": True, "reason": "no_pil",
                       "message": msg}, a, indent=1, ok=False)
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(2, "usage", msg)

    bgs = _iter_bg(sel, outdir, {s.strip() for s in (a.only or "").split(",") if s.strip()} or None)
    if not bgs:
        raise UsageError("在 %s 里没找到可叠字的底图；先跑 `images` 出图（或用 --outdir 指对目录）"
                         % outdir)

    font_path, _ = find_font(a.font)
    spath = Path(a.state) if a.state else (outdir / STATE_NAME)
    state = load_state(spath)
    state.setdefault("items", {})

    results, bad_fit, bad_safe, missing_fonts = [], [], [], []
    for n, (it, bg) in enumerate(bgs, 1):
        spec_rec = plan_overlay(it, a.font)
        if not spec_rec["ok"]:
            if spec_rec["kind"] == "no_font":
                missing_fonts.append(spec_rec)
            else:
                bad_fit.append(spec_rec)
            sys.stderr.write("  %s #%s %s\n" % (_red("[叠字]"), it["id"], spec_rec["why"]))
            continue
        key = overlay_state_key(bg, it, a.font, a.text_color, a.stroke_color,
                               not a.no_shadow)
        prev = state["items"].get(key)
        if prev and prev.get("status") == "done" and not a.force and Path(prev.get("path", "")).is_file():
            results.append({"id": it["id"], "platform": it["platform"],
                            "title": it["title"], "file": prev["path"],
                            "skipped": True, "render": prev.get("render")})
            sys.stderr.write("  [%d/%d] #%s 已叠过字（大字与样式都没变），跳过\n"
                             % (n, len(bgs), it["id"]))
            continue
        if a.dry_run:
            results.append({"id": it["id"], "platform": it["platform"], "dry_run": True,
                            "plan": spec_rec})
            if not a.json:
                print("#%s %s → %s" % (it["id"], spec_rec["platform_name"],
                                       spec_rec["text"]))
                print("   底图 %s" % bg)
                print("   字号 %dpx 描边 %dpx / %d 行 / 渲染框 %s / 安全区 %s"
                      % (spec_rec["font_size"], spec_rec["stroke_width"],
                         len(spec_rec["lines"]), spec_rec["box"], spec_rec["safe_rect"]))
                print("   字体 %s" % spec_rec["font"])
            continue
        suffix = "_cover" + (Path(bg).suffix or OUT_EXT)
        dst = outdir / (Path(bg).stem + suffix)
        if a.outdir_name:
            dst = Path(a.outdir_name) / (Path(bg).stem + (Path(bg).suffix or OUT_EXT))
        r = render_overlay(bg, dst, spec_rec, a.text_color, a.stroke_color,
                           not a.no_shadow, a.font)
        if not r.get("ok"):
            bad_fit.append(dict(spec_rec, why=r.get("why"), kind=r.get("kind")))
            sys.stderr.write("  %s #%s %s\n" % (_red("[叠字]"), it["id"], r.get("why")))
            continue
        # ---- 叠字后复核真实像素（产出必须等于平台目标像素）----
        want = target_size(it["platform"])
        px_ok = (tuple(r["out_px"]) == tuple(want))
        rec = {"out_px": r["out_px"], "want_px": list(want), "px_ok": px_ok,
               "box": r["box"], "safe_ok": r["safe_ok"], "font": r["font"],
               "font_size": r["font_size"], "lines": r["lines"],
               "stroke_width": r["stroke_width"], "fill": r["fill"],
               "stroke_fill": r["stroke_fill"],
               "bytes": Path(dst).stat().st_size if Path(dst).is_file() else None}
        if not r["safe_ok"]:
            bad_safe.append({"id": it["id"], "why": "叠字框 %s 越出安全区" % (r["box"],)})
        state["items"][key] = {"status": "done", "path": str(dst), "render": rec,
                               "overlay_sig": overlay_style_sig(it, a.font),
                               "text": (it.get("overlay") or {}).get("text")}
        save_state(spath, state)
        results.append({"id": it["id"], "platform": it["platform"],
                        "title": it["title"], "file": str(dst), "render": rec})
        sys.stderr.write("  [%d/%d] #%s 叠字完成 %dx%d（%d 字节，%d 行，%dpx 字号）\n"
                         % (n, len(bgs), it["id"], r["out_px"][0], r["out_px"][1],
                            rec["bytes"] or 0, len(r["lines"]), r["font_size"]))

    summary = {"outdir": str(outdir), "state": str(spath),
               "requested": len(bgs), "rendered": len([r for r in results if not r.get("skipped")]),
               "skipped": len([r for r in results if r.get("skipped")]),
               "blocked_too_long": bad_fit, "blocked_outside_safe": bad_safe,
               "missing_font": missing_fonts,
               "font": font_path,
               "items": [{k: v for k, v in r.items() if k != "plan"} for r in results]}
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    if a.json:
        _json_out(summary, a, indent=1, ok=not (bad_fit or bad_safe or missing_fonts))
    else:
        print("\n叠字完成：%d 张（跳过 %d 张）" % (summary["rendered"], summary["skipped"]))
    if missing_fonts:
        sys.stderr.write("\n%s\n" % _red("没有可用的中文字体：%s" % missing_fonts[0]["why"]))
        return _fail(2, "usage", "没有可用的中文字体（用 --font 指定）")
    if bad_fit:
        sys.stderr.write("\n")
        for b in bad_fit:
            sys.stderr.write("   %s #%s %s\n" % (_red("[叠字]"), b.get("id"), b.get("why")))
        sys.stderr.write("\n%s\n" % _red(
            "闸门五：有 %d 张的叠字放不下（超长 / 缩小到地板仍溢出），**已拦截，未渲染**。"
            % len(bad_fit)))
        return _fail(3, "gate", "闸门五：%d 张叠字放不下" % len(bad_fit))
    if bad_safe:
        sys.stderr.write("\n")
        for b in bad_safe:
            sys.stderr.write("   %s #%s %s\n" % (_red("[叠字安全区]"), b["id"], b["why"]))
        sys.stderr.write("\n%s\n" % _red(
            "闸门五：有 %d 张的叠字越出安全区（可能被平台角标/互动条盖住）。" % len(bad_safe)))
        return _fail(3, "gate", "闸门五：%d 张叠字越出安全区" % len(bad_safe))
    return 0


# ===========================================================================
# 子命令：all
# ===========================================================================

def cmd_all(a):
    """串起 plan → images → overlay，**断点续跑**。

    ⚠️ 这里**不是**把 `a` 复制成 Namespace 再调 `cmd_plan(a)` —— 实测那样会炸：
    `all` 的参数集与其他子命令并不相同（`cmd_plan` 要 `a.dry_run`、`cmd_images` 要
    `a.snap`…），靠 `argparse.Namespace(**vars(a))` 拼出来的对象必然缺字段，
    运行到一半抛 `AttributeError: 'Namespace' object has no attribute 'dry_run'`。
    所以 `all` 自己按顺序走三步，每一步需要的字段从 `a` 里就地取默认值。
    """
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plan_out = Path(a.out) if a.out else (outdir / "cover-plan.json")

    # ---- 1) plan（只花文本钱；已有方案文件就跳过 —— 断点续跑）----
    if plan_out.is_file() and not a.force:
        obj = json.loads(plan_out.read_text(encoding="utf-8", errors="replace"))
        if isinstance(obj, dict) and obj.get("items"):
            sys.stderr.write("[1/3] 已有方案 %s（%d 条），跳过 plan 阶段（重跑不重复花文本钱）\n"
                             % (plan_out, len(obj["items"])))
        else:
            sys.stderr.write("[1/3] 方案文件里没有 items，重新出方案\n")
            plan_out.unlink()
    if not plan_out.is_file():
        platforms = _resolve_platforms(a.platform)
        titles = _load_titles(a)
        if not titles:
            raise UsageError('请给标题清单：--file 标题.md（每行一个）或 --text "标题1，标题2"')
        titles = titles[:max(1, a.titles)]
        prompt = build_plan_prompt(titles, platforms, a.style, a.brief)
        sys.stderr.write("[1/3] 正在用 `%s` 出封面方案（%d 个标题 × %d 个平台 = %d 张）…\n"
                         % (a.model, len(titles), len(platforms),
                            len(titles) * len(platforms)))
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                              temperature=a.temperature, max_tokens=a.max_tokens,
                              key=a.key, json_mode=not a.no_json_mode)
        items, notes = normalize_plan(parse_first_json(content), titles, platforms, a.style)
        if not items:
            raise a7w.A7wError("模型没产出任何封面条目")
        plan = {"version": VERSION, "titles": titles, "platforms": platforms,
                "style": a.style, "model": a.model, "usage": usage,
                "elapsed_sec": round(time.time() - t0, 1), "count": len(items),
                "items": items, "notes": notes}
        plan_out.parent.mkdir(parents=True, exist_ok=True)
        plan_out.write_text(json.dumps(plan, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        bad = [it for it in items if it["leaks"]]
        for n in notes:
            sys.stderr.write("  · %s\n" % n)
        if bad:
            _report_leaks(bad)
            return _fail(3, "gate",
                         "[1/3] 方案阶段：%d 条命中硬闸门（未出图、未花钱）" % len(bad))

    # ---- 2) images ----
    ns = argparse.Namespace(
        key=a.key, json=a.json, plan=str(plan_out), outdir=str(outdir),
        platform=a.platform, count=a.count, only=getattr(a, "only", None),
        resolution=getattr(a, "resolution", None),
        points_per_image=a.points_per_image, budget=a.budget, yes=a.yes,
        snap=a.snap, ratio_tolerance=a.ratio_tolerance, poll_timeout=a.poll_timeout,
        max_seconds=getattr(a, "max_seconds", None), force=a.force,
        no_wait=a.no_wait, stop_on_error=a.stop_on_error, dry_run=False,
        allow_prompt_hits=a.allow_prompt_hits, report=None, state=getattr(a, "state", None),
        font=a.font)
    rc = cmd_images(ns)
    if rc:
        return rc

    # ---- 3) overlay ----
    ns3 = argparse.Namespace(
        key=a.key, json=a.json, plan=str(plan_out), outdir=str(outdir),
        platform=a.platform, count=a.count, only=getattr(a, "only", None),
        resolution=getattr(a, "resolution", None),
        points_per_image=a.points_per_image, force=a.force,
        outdir_name=getattr(a, "outdir_name", None), text_color=a.text_color,
        stroke_color=a.stroke_color, no_shadow=a.no_shadow, font=a.font,
        state=getattr(a, "state", None), report=None, dry_run=False,
        allow_prompt_hits=a.allow_prompt_hits)
    return cmd_overlay(ns3)


# ===========================================================================
# CLI
# ===========================================================================

def _add_titles_opts(p):
    p.add_argument("files", nargs="*", help="标题清单文件（每行一个标题）")
    p.add_argument("--file", help="标题清单文件（每行一个标题，`#` 开头算注释）")
    p.add_argument("--text", help="直接给标题，逗号或换行分隔")
    p.add_argument("--titles", type=int, default=200,
                   help="最多取前 N 个标题，默认 200")


def _add_model_opts(p):
    p.add_argument("--model", default=DEFAULT_MODEL, help="文本模型，默认 %s" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--no-json-mode", action="store_true",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_platform_opt(p):
    """`--platform` 每个子命令只定义**一处**（argparse 同参数重复定义会直接报错）。"""
    p.add_argument("--platform", action="append", choices=PLATFORM_CHOICES,
                   help="只处理指定平台，可重复；默认 5 个平台全出")


def _add_image_opts(p, with_outdir=True):
    if with_outdir:
        p.add_argument("--outdir",
                       default=str(Path(os.environ.get("TEMP") or ".") / "cover-factory-out"),
                       help="产出目录（**必须在 Skill 包外**）")
    p.add_argument("--count", type=int, help="最多处理前 N 条")
    p.add_argument("--only", help="只处理指定 id（逗号分隔）")
    p.add_argument("--resolution", default=None, choices=list(RESOLUTIONS),
                   help="出图分辨率，默认 1K（只有 1K 有实测价 24 点/张）")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--font", help="指定中文字体文件（.ttf/.ttc/.otf）")
    p.add_argument("--state", help="断点文件路径，默认 <outdir>/%s" % STATE_NAME)
    p.add_argument("--force", action="store_true", help="忽略断点重出（**会重复扣费**）")
    p.add_argument("--report", help="把本次证据写成 JSON")
    p.add_argument("--allow-prompt-hits", action="store_true",
                   help="提示词命中闸门也照出（默认拦截；**超长大字不放行**）")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 封面图批量生成：一批标题 → 各平台封面（背景图 + 本地叠字）")
    ap.add_argument("--key", help="临时指定 api.a7w.cn 的 Key（别写进脚本或文档）")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    ap.add_argument("--version", action="version", version="sanjianke-cover-factory %s" % VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --- specs ---
    p = sub.add_parser("specs", help="各平台封面规格（零网络、零成本）")
    _add_json(p)
    p.add_argument("--platform", action="append", choices=PLATFORM_CHOICES,
                   help="只看指定平台，可重复；默认全部")
    p.add_argument("--font", help="指定中文字体文件（用于自检字号口径）")
    p.set_defaults(func=cmd_specs)

    # --- plan ---
    p = sub.add_parser("plan", help="按标题清单出封面方案（只花文本钱）")
    _add_json(p)
    _add_titles_opts(p)
    _add_model_opts(p)
    _add_platform_opt(p)
    p.add_argument("--style", help="统一视觉风格口径（会给到模型）")
    p.add_argument("--brief", help="作者补充要求")
    p.add_argument("--out", help="把方案写成 JSON（images / overlay 要用它）")
    p.add_argument("--dry-run", action="store_true", help="只打印提示词，不调模型、不花钱")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.set_defaults(func=cmd_plan)

    # --- images ---
    p = sub.add_parser("images", help="按方案批量出背景图（真花钱，先报价再确认）")
    _add_json(p)
    p.add_argument("--plan", required=True, help="plan 产出的方案 JSON")
    _add_image_opts(p)
    _add_platform_opt(p)
    p.add_argument("--budget", type=float, help="成本上限（点）：超了直接停，不提交")
    p.add_argument("--yes", action="store_true", help="确认真的花钱（不加就只报价）")
    p.add_argument("--snap", action="store_true",
                   help="出图后按**平台设计比例**精确裁剪（并复核，裁准了才换）")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   help="比例容差，默认 %.3f（实测最大偏差 2.9 个百分点）" % RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT,
                   help="单张轮询超时秒数，默认 %g" % POLL_TIMEOUT_DEFAULT)
    p.add_argument("--max-seconds", type=float, help="整批最长耗时（秒），到点中断可续跑")
    p.add_argument("--no-wait", action="store_true", help="只提交不等结果（稍后用任务续查）")
    p.add_argument("--stop-on-error", action="store_true", help="一张失败就整体停")
    p.add_argument("--dry-run", action="store_true", help="只报价，一个任务都不提交")
    p.set_defaults(func=cmd_images)

    # --- overlay ---
    p = sub.add_parser("overlay", help="把大字标题本地渲染到图上（零成本、零网络）")
    _add_json(p)
    p.add_argument("--plan", required=True, help="plan 产出的方案 JSON")
    _add_image_opts(p)
    _add_platform_opt(p)
    p.add_argument("--outdir-name", help="另存到一个目录（默认就地写在 --outdir 里）")
    p.add_argument("--text-color", help="大字颜色，如 #FFFFFF")
    p.add_argument("--stroke-color", help="描边颜色，如 #101010")
    p.add_argument("--no-shadow", action="store_true", help="不画阴影层（亮底图上可读性会下降）")
    p.add_argument("--dry-run", action="store_true", help="只算排版，不渲染、不写文件")
    p.set_defaults(func=cmd_overlay)

    # --- all ---
    p = sub.add_parser("all", help="串起 plan → images → overlay（断点续跑）")
    _add_json(p)
    _add_titles_opts(p)
    _add_model_opts(p)
    _add_platform_opt(p)
    p.add_argument("--style", help="统一视觉风格口径")
    p.add_argument("--brief", help="作者补充要求")
    p.add_argument("--out", help="方案 JSON 路径，默认 <outdir>/cover-plan.json")
    _add_image_opts(p)
    p.add_argument("--budget", type=float, help="成本上限（点）")
    p.add_argument("--yes", action="store_true", help="确认真的花钱")
    p.add_argument("--snap", action="store_true", help="出图后裁到平台设计比例")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT)
    p.add_argument("--max-seconds", type=float)
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--stop-on-error", action="store_true")
    p.add_argument("--text-color", help="大字颜色")
    p.add_argument("--stroke-color", help="描边颜色")
    p.add_argument("--no-shadow", action="store_true")
    p.add_argument("--outdir-name", help="叠字另存目录")
    p.set_defaults(func=cmd_all)

    # --- cost ---
    p = sub.add_parser("cost", help="只算钱不出图")
    _add_json(p)
    p.add_argument("--count", type=int, help="要出几张")
    p.add_argument("--titles", type=int, help="标题个数（配合 --platform 算总数）")
    p.add_argument("--platform", action="append", choices=PLATFORM_CHOICES)
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--budget", type=float, help="预算上限（点），超了退出码 3")
    p.set_defaults(func=cmd_cost)

    # --- models ---
    p = sub.add_parser("models", help="列出在架应用与模型（零成本）")
    _add_json(p)
    p.set_defaults(func=cmd_models)
    return ap


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与普通 CLI 一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout          # 记住真 stdout（信封不许被重定向吞掉）
    _JSON["want"] = "--json" in argv_eff  # argparse 失败时还没有 a，先按命令行判断
    _JSON["emitted"] = False
    _JSON["reason"] = None
    _JSON["trace"] = False
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
        # argparse 的参数错（退出码 2）也要给信封；--help / --version（0）不算失败
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    kind, msg = None, None
    try:
        rc = a.func(a)
    except UsageError as exc:
        sys.stderr.write("\n错误：%s\n" % exc)
        rc, kind, msg = 2, "usage", str(exc)
    except a7w.A7wError as exc:
        sys.stderr.write("\n错误：%s\n" % exc)
        rc, kind, msg = 4, "call", str(exc)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（已提交的任务记在断点文件里，重跑可续查）\n")
        rc, kind, msg = 130, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        if _JSON["trace"]:
            # 命令自己已经吐过完整 JSON（结果里 ok=false）→ **绝不再补信封**，
            # 否则 stdout 上会有两个 JSON 文档，消费方 `json.loads` 直接失败。
            sys.stderr.write("\n%s\n" % _red(
                "本次以退出码 %d 结束；结果 JSON 已经在上面的 stdout 里（ok=false）。"
                % rc))
            return rc
        _json_fail(rc, reason.get("kind") or kind,
                   reason.get("message") or msg, reason.get("detail"), a)
    return rc


if __name__ == "__main__":
    sys.exit(main())
