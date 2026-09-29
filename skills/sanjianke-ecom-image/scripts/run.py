#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 电商主图工厂（sanjianke-ecom-image）。

给商品信息（标题/类目/卖点/参数/实物图 URL），批量产出**电商平台规格**的主图与详情图：
白底主图 / 场景图 / 卖点图 / 细节图 / 资质图，按平台规格（淘宝 800x800 / 1688 / 拼多多 /
抖音商城 3:4）出图，卖点文案按**主图位**分配，并做电商合规自检。

子命令
    specs       列出各平台主图规格（零网络、零成本）
    sellpoints  从商品信息提炼卖点并分配到主图位（文本，花文本钱）
    images      批量出图（真花钱：先报价、要 --yes，断点续跑）
    compliance  卖点文案合规自检（零成本、纯本地）
    all         sellpoints → images 一条龙
    cost        只算钱不出图
    models      列出在架应用与模型

与同族的区别（**不是「换个比例 + 换个提示词」**，四条都是结构性的）
    1. 商品图驱动：输入是**商品实物图 URL**。场景图用 action=generate（不提 URL），
       图生图改造与资质位用 action=edit + image_urls。不要求用户先把商品图改词描述一遍。
       本包**不自造商品图**（白底原始图要实拍，见 references/ecom-image-method.md）。
    2. 主图位驱动：卖点不是「随便分配给几张图」，而是按平台固定的**主图位**分配
       （第 1 张利益点 / 第 2 张规格与适用 / 第 3 张细节工艺 / 第 4 张场景人群 /
       第 5 张资质售后），并对第 5 位缺失做**主图位完整性**闸门。
    3. 电商合规独立成闸：「最X」有**可枚举的上下文豁免 + 句首不豁免**，
       另加「不伪造销量 / 评价 / 资质 / 检测报告」的独立判据。
    4. 平台规格闸门：淘宝白底主图 800x800（可 800 以上，必须正方）、抖音商城 3:4。

设计上的六条硬约束（都不是「警告」而是「拦截 + 标红 + stderr 汇总 + 非 0 退出码」）
    1. 电商合规：广告法违禁词（最/第一/国家级/100%）+ 伪造销量/评价/资质/检测报告
    2. 占位符残留：`{}` / `[待填]` / `XXX`
    3. prompt_echo：三条判据（去标点相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60）+ 相对长度守卫
    4. 出图比例真伪：**读真实像素**，不信自报字段；容差 3%，容差内也打印偏差；--snap 裁准
    5. 主图位完整性：五张位缺位 → 标红
    6. 成本上限；产出图不许进包（--outdir 在包内 → exit=2）

零第三方依赖：只用标准库。裁剪（--snap）在有 PIL 时用 PIL，
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
import imgprobe   # noqa: E402  ← 图片头探针（读真实像素），独立模块，只读

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"       # 实测可用（会路由到 deepseek-flash）
CHAT_RETRIES = 4
STATE_NAME = "ecom-image-state.json"

# ---------------------------------------------------------------------------
# nano_banana 出图应用相关（本包业务，**放在这里而不是 a7w.py**）
#
# 【约定】`scripts/a7w.py` 是所有 Skill 包共用的零依赖客户端，我们靠
# 「包内副本 SHA256 == 规范版」（16797 B / EACD2E4F…B465）批量校验各包有没有被改坏。
# 所以**任何包都不许为了自己的业务往 a7w.py 里加东西**：
#   · 需要读图片像素     → 独立模块 `imgprobe.py`
#   · 需要应用专属的接口 → 就写在这一段里
#
# schema 现查（`python scripts/a7w.py schema nano_banana`，写代码前实跑过一次）：
#   submit  POST /api/v1/apps/nano_banana/submit   异步
#         model / action / prompt / image_urls / resolution / aspect_ratio / callback_url
#   query   POST /api/v1/apps/nano_banana/query    同步，参数 task_id
# 注意：**没有 /generate 这个端点**，「文生图」是 submit 的 action=generate 参数。
# ---------------------------------------------------------------------------

APP_IMAGE = "nano_banana"
API_SUBMIT = "submit"
API_QUERY = "query"
TASK_URL = a7w.HOST + "/api/v1/tasks/{}"

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

OUT_EXT = ".png"

# ---------------------------------------------------------------------------
# 平台规格：**电商平台**主图规格（与新媒体配图工厂的「小红书 3:4 / 公众号 2.35:1」
# 是完全不同的一张表——那里是内容平台的封面比例，这里是电商平台的商品图规格）
#
# design_px 是**平台要求的目标像素**，gen_ratio 是喂给上游 nano_banana 的 aspect_ratio。
# 两者可能不同（例如抖音商城要 3:4 而不是上游能给的精确像素）。
# ---------------------------------------------------------------------------

PLATFORMS = {
    "taobao": {
        "name": "淘宝 / 天猫",
        "main_px": "800x800",
        "design_ratio": "1:1",
        "gen_ratio": "1:1",
        "slot1_white_bg": True,
        "note": "主图必须正方形，最小 800x800（可更大，比例仍须 1:1）；第 1 张是白底主图，"
                "**背景必须是纯白**，主体占比约 70%~85%，四周留白、不要贴边、不要水印。"
                "白底主图是搜索与猜你喜欢的入池基础，做不好后面几张都没机会被看到。",
    },
    "taobao34": {
        "name": "淘宝 / 天猫 3:4 竖版主图",
        "main_px": "750x1000",
        "design_ratio": "3:4",
        "gen_ratio": "3:4",
        "slot1_white_bg": False,
        "note": "竖版主图位（部分类目与投放位使用）。上游按 32 对齐，3:4 实得 864x1184 "
                "（偏差 2.70%），要像素级精确比例就加 --snap。",
    },
    "1688": {
        "name": "1688 主图",
        "main_px": "800x800",
        "design_ratio": "1:1",
        "gen_ratio": "1:1",
        "slot1_white_bg": True,
        "note": "面向批发采购，第 1 张白底主图同样要纯白背景；后续图位重点讲**规格、"
                "起订量、材质、供货能力**，不要写成零售口吻的促销。",
    },
    "pinduoduo": {
        "name": "拼多多主图",
        "main_px": "800x800",
        "design_ratio": "1:1",
        "gen_ratio": "1:1",
        "slot1_white_bg": True,
        "note": "主图正方形，白底优先。价格与规格信息密度高，但**不许在图上写「最低价」"
                "「全网最低」这类绝对化用语**——这是本包合规闸门的高危词。",
    },
    "douyin": {
        "name": "抖音商城 3:4",
        "main_px": "1200x1600",
        "design_ratio": "3:4",
        "gen_ratio": "3:4",
        "slot1_white_bg": False,
        "note": "抖音商城商品图 3:4 竖版，信息流里占位最高。上下各留约 8% 安全区，"
                "主体不要压到边角（会被角标与商品卡遮住）。",
    },
    "detail": {
        "name": "详情页长图",
        "main_px": "750x不限",
        "design_ratio": "1:3",
        "gen_ratio": "3:4",
        "slot1_white_bg": False,
        "note": "详情页是**长图**：宽度固定 750，高度按内容分屏累加。上游单张出不了长图，"
                "所以本包按屏出图（单屏 3:4），**拼接在本地做**（见 references/platform-specs.md "
                "的拼接一节）。design_ratio 1:3 是「单屏占长图的三分之一」的记录口径，"
                "生成仍用 3:4。",
    },
}

# 五张主图位。**顺序即平台语义**：第 1 张利益点、第 2 张规格与适用、
# 第 3 张细节工艺、第 4 张场景人群、第 5 张资质售后。
#
# 为什么卖点要「按位分配」而不是「平均分配给 N 张图」：
# 电商主图位是**平台固定的语义槽**，不是一篇文章里的插图位置。用户划到第 2 张
# 想看的是「这东西多大、我能不能用」，不是又一句利益点。把卖点乱塞进图位，
# 五张图会变成五张重复的主图——这是我们与「新媒体配图工厂」最本质的区别。
SLOTS = [
    {"slot": "main", "cn": "主图", "index": 1,
     "mission": "利益点：一句话说清「买它解决什么问题」，主体大、留白够",
     "rule": "第 1 张主图承担点击率，只放**一个**核心利益点；白底平台必须纯白背景",
     "required": True},
    {"slot": "spec", "cn": "规格图", "index": 2,
     "mission": "规格与适用：尺寸/容量/材质/型号 + 适用人群或不适用人群",
     "rule": "把参数讲清，不吹；写「不适合谁」比写「人人适合」更让人信",
     "required": True},
    {"slot": "selling", "cn": "卖点图", "index": 3,
     "mission": "细节与工艺：放大一个可验证的做工细节，配一句证据型文案",
     "rule": "细节要能被买家在实拍里对上；**不许把「检测报告」写成不存在的结论**",
     "required": True},
    {"slot": "scene", "cn": "场景图", "index": 4,
     "mission": "场景与人群：商品在真实使用场景里，让买家代入",
     "rule": "场景图用 generate（商品图作风格与主体参考）；不摆拍出不存在的使用效果",
     "required": True},
    {"slot": "qualification", "cn": "资质图", "index": 5,
     "mission": "资质与售后：可查验的资质/参数/售后承诺（**用你真实持有的材料**）",
     "rule": "**本包不生成资质**。这一位走 action=edit，把你真实持有的资质图拿来改版式；"
             "没有资质就**如实缺位**，闸门会标红——比伪造一张图安全得多",
     "required": True},
]

SLOT_KEYS = [s["slot"] for s in SLOTS]

# 上游实际能给的像素（1K 档，实测 10 种比例）。留作文档与排错依据。
MEASURED_1K_PIXELS = {
    "1:1": [1024, 1024], "3:4": [864, 1184], "4:3": [1184, 864],
    "16:9": [1344, 768], "9:16": [768, 1344], "21:9": [1536, 672],
    "2:3": [832, 1248], "3:2": [1248, 832], "4:5": [896, 1152],
    "5:4": [1152, 896],
}

# 详情页长图的单屏口径（本地拼接用）
DETAIL_SCREEN_PX = (750, 1000)


# ---------------------------------------------------------------------------
# nano_banana 接口封装
#
# 平台文档写的是 `data.result.status`，**实测不对**：status 在 `data` 顶层。
# 照文档写会永远读不到状态、一路轮询到超时，所以这里按实测结构取。
# ---------------------------------------------------------------------------

def submit_image(prompt, aspect_ratio="1:1", resolution="1K",
                 model="nano-banana", action="generate", image_urls=None,
                 callback_url=None, key=None, timeout=180):
    """提交一个出图任务，返回网关 data（含 task_id 与预冻结点数）。

    请求体字段用 `python scripts/a7w.py schema nano_banana` 实查过，不凭记忆加字段：
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
        raise a7w.A7wError("action=edit 时必须提供 image_urls（商品实物图/资质图的公网直链）")
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
# 闸门四：出图比例真伪（读真实像素，不信自报值）
#
# 事故来源：标题工坊上一版只信模型自报的 `formula` 字段做模板污染判定，
# 结果那个真该被判命的标题恰好漏判——闸门是**假绿**的。
# 同一个错误在出图场景的形态是：接口/模型自报 `aspect_ratio=3:4`，
# 但真实像素是 1024x1024。只信自报值 → 用户拿去上架才发现五张主图尺寸不齐。
#
# ⚠️ 实测到的上游特性（必须写进文档，否则闸门天天误报）：
#   上游不是按比例给像素，而是先定总像素、再把每边向下取整到 32 的倍数。
#       请求 3:4  → 864x1184   = 0.7297（3:4 = 0.75）  偏差 2.70%
#       请求 16:9 → 1344x768   = 1.7500（16:9 = 1.778）偏差 1.56%
#       请求 9:16 → 768x1344   = 0.5714（9:16 = 0.5625）偏差 1.56%
#       请求 4:5  → 896x1152   = 0.7778（4:5 = 0.8）    偏差 2.78%
#       请求 5:4  → 1152x896   = 1.2857（5:4 = 1.25）   偏差 2.86%
#   精确的 5 种：1:1 / 4:3 / 21:9 / 2:3 / 3:2
#   这**不是**网关 bug，是扩散模型按 32 对齐的常规做法。但它意味着
#   「请求比例 == 产出比例」这个断言对一半的比例天然不成立。
#
# 处理方式（三条一起用，缺一条闸门就会变成天天误报的噪音）：
#   a) 默认容差 3%：容差内不算「假」，但会**明确打印真实像素与偏差**，不藏
#   b) 超过容差 → 标红 + 计入闸门失败 + 退出码 3
#   c) `--snap`：出图后按请求比例精确裁掉多余像素；裁剪结果再次读文件头复核
# ---------------------------------------------------------------------------

RATIO_TOLERANCE = 0.03

# 容差地板：**像素只能是整数**，所以「裁到精确比例」本身就有量化误差。
# 实测（--snap 之后复核）：相邻整数像素间隔约 0.27%，所以用户把
# --ratio-tolerance 调到比这还小时，会把「本来就必须存在」的舍入误差判成不合格。
RATIO_TOLERANCE_FLOOR = 0.0025

# ---------------------------------------------------------------------------
# 提示词里出现过的示例文本。**新增示例必须登记到这里。**
#
# 下面是「跨类目」的假例子：黄色香蕉造型蓝牙音箱（3C 类目）与橙色圆形图标。
# 真实商品不会是这两个，所以正常出图提示词与它们不该有高相似度。
# 但凡在提示词里给模型看过一条**完整可直接复制的**出图提示词，模型就会照抄——
# 标题工坊实测过：公众号那一轮最高分 89.0 的标题**一字不差就是提示词里的示例**。
# ---------------------------------------------------------------------------
PROMPT_SAMPLES = [
    "一只黄色香蕉形状的蓝牙音箱，纯白背景，柔光棚拍，主体居中",
    "a yellow banana-shaped bluetooth speaker on a pure white background, soft studio light",
    "橙色渐变背景上一个白色圆形图标，极简扁平插画风，无文字",
]

parse_ratio = imgprobe.parse_ratio
ratio_label = imgprobe.ratio_label


def check_ratio(path, want_ratio, tolerance=None):
    """闸门四：读真实像素，判是否等于请求比例。"""
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
# 电商平台对主图比例有硬要求（淘宝主图必须正方、抖音商城 3:4），
# 差 2% 在 3:4 上就是 27 像素，上传后会被平台二次裁切、位置不可控。
# 与其让平台裁，不如本地裁准。
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
# 闸门一：电商合规（广告法违禁词 + 不伪造销量/评价/资质/检测报告）
#
# 【为什么「最X」要开上下文豁免，而不是一刀切】
# 电商文案里「最好」「最强」是绝对化用语，照拦没错；但中文里「最大」也大量出现在
# **普通比较句**里：「和同类产品最大的区别是……」「这个价位里最省事的做法是……」。
# 一刀切拦下来，运营会成天在改根本不违规的句子，闸门变成噪音——闸门一旦变成噪音，
# 人就会加 --allow-prompt-hits 把它关掉，那时真正该拦的也拦不住了。
#
# 所以加一层**上下文豁免**：
#   命中「最…」之后再看一眼后续几个字，若接的是比较/程度类词，判为普通中文用法。
#   豁免范围**写死在代码里、可枚举、可复核**，不是一句「人工判断」了事。
# ⚠️ 句首不许误豁免：「最大区别是……」这种**句首**写法经常正是标题式的最高级宣称。
# ⚠️ 豁免只允许一个「的」/「了」：
#   实测踩到过「找出占比最高、且最容易改的那一个环节」被拦。想放开它只有两条路，
#   两条都不该走：往豁免表里加「且」＝自行扩张口径，越走越松；让标点豁免生效＝
#   「最好的工具，值得买」也会被放行，等于给最高级广告语开后门。
#   所以上面那句会在闸门里被拦下，属**已知的保守行为**，靠改文案解决，不靠放松规则解决。
# ---------------------------------------------------------------------------

ECO_SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥", "多", "少", "大", "小", "好", "差",
    "近", "远", "快", "慢", "重", "轻", "薄", "厚", "长", "短", "宽", "窄",
    "高", "低", "贵", "便宜",
)
ECO_SUPERLATIVE_OK_RE = re.compile(
    r"^\s*[的了]?\s*(?:" + "|".join(ECO_SUPERLATIVE_OK_AFTER) + r")")

# 句首判定：命中处前面只有空白，或前一个非空白字符是句末标点/换行 → 视为句首。
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")


def _superlative_is_normal_usage(text, m):
    """「最X」后接比较/程度词，**且不在句首** → 判为普通中文用法，不拦。

    两个条件缺一不可：
      1. 后文落在可枚举的豁免表里（ECO_SUPERLATIVE_OK_AFTER）
      2. 命中处不在句首（句首的「最大区别是…」是标题式最高级宣称，照拦）
    """
    if not m.group(0).startswith("最"):
        return False
    before = (text or "")[:m.start()]
    if not before.strip() or _SENT_END_RE.search(before):
        return False                       # 句首 → 不豁免
    return bool(ECO_SUPERLATIVE_OK_RE.match((text or "")[m.end():]))


BANNED_PATTERNS = [
    (r"国家级|世界级|最高级|最佳|最优|最强|最好|最棒|最先进|最领先|第一品牌|全国第一|排名第一|销量第一|行业第一|同类第一", "高",
     "广告法第九条绝对化用语，商品主图与卖点文案都不许带"),
    # ⚠️ `最[\u4e00-\u9fff]` 单独成条，是为了让**每一处「最X」都过一遍
    # `_superlative_is_normal_usage` 的豁免判定**。上一版把「最大」漏在模式之外，
    # 结果是：「最大的区别是它更耐用」这种**句首**最高级宣称**根本没被命中**，
    # 「句首不豁免」这条规则等于没被测到——闸门是假绿的（实测踩到，已修）。
    (r"最[\u4e00-\u9fff]|全网最低|史上最低|顶级|极品|绝无仅有|独一无二|仅此一家|遥遥领先", "高",
     "绝对化用语，无法举证；普通中文比较用法（如「最大的区别是…」）由上下文豁免放行，"
     "但**句首**的「最X」一律照拦"),
    (r"100%|百分之百|百分百|绝对(有效|安全|可靠|不会|正品)|保证(有效|见效|正品|最低)", "高",
     "绝对化承诺，属虚假宣传高风险表述"),
    (r"国家(认证|认可|免检|级)|央视(推荐|上榜)|官方(推荐|指定|认证)|权威认证|国际认证|免检产品", "高",
     "虚构权威背书；认证必须能出示证书编号与颁发机构"),
    (r"根治|治愈|药到病除|包治|特效|无副作用|抗癌|降(血压|血糖|血脂)|医用级|械字号功效", "高",
     "医疗功效宣称，普通商品不得使用"),
    (r"稳赚|保本|保收益|零风险|躺赚|日入过万|月入百万|包过|投资回报率", "高",
     "投资/收益承诺，金融敏感表述"),
    # --- 电商专属：不伪造销量 / 评价 / 资质 / 检测报告 ---
    (r"(销量|累计销量|月销|已售|售出|成交)\s*(第|No\.?1|第一|冠军|领先|破\s*\d)|"
     r"\d+\s*万?\s*\+?\s*(人|用户|买家|家庭)\s*(已购|在用|选择|复购)", "高",
     "销量/购买人数必须来自平台后台真实数据；主图与文案不得自造销量"),
    (r"(好评|评价|口碑)\s*(率)?\s*(100%|百分百|零差评|无一差评|0\s*差评)|"
     r"好评如潮|全部五星|清一色好评|真实评价\s*\d+\s*条", "高",
     "不得伪造评价或评价率；平台规则与广告法都禁止"),
    (r"(权威|国家级|官方|国际)?检测(报告|机构)?\s*(认证|通过|合格)|"
     r"检测报告\s*(编号|号)?\s*[:：]?|质检(合格|报告)|SGS|CMA|CNAS", "高",
     "检测报告/认证必须真实存在且能出示；**本包不生成资质，也不替你编结论**"),
    (r"专利(技术|产品|认证)|独家(配方|技术|专利)|(祖传|宫廷|特供|专供|内供)", "高",
     "专利与专供特权类表述必须有可查验依据，否则属虚假宣传"),
    (r"包邮|假一赔十|七天无理由|正品保障|假一赔万", "中",
     "售后承诺必须与店铺实际规则一致，写错要担责"),
    (r"首[个创]|独家|唯一|填补空白|销量冠军", "中",
     "排他性表述，需有可举证依据"),
    (r"免费领|免费送|0\s*元购|白送|扫码(加|进|领)|加微信|私信我|vx|VX", "中",
     "诱导分享或站外导流，电商平台普遍限制"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天|错过再等一年", "中",
     "促销时限表述需与真实活动一致"),
    (r"纯天然|无添加|零添加|无毒无害|食品级|婴儿级", "中",
     "成分/材质宣称需与检测报告一致"),
    (r"震惊|惊呆|不看后悔|速看|删前必看", "低",
     "标题党式诱导"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}
VERDICT_BY_LEVEL = {"高": "blocked", "中": "review", "低": "check"}


def compliance_scan(text):
    """扫一遍违禁词，返回命中列表（可能为空），按风险等级排序。

    同一个词可能在文案里出现多次（一次是广告语、一次是普通用法），
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
# 卖点是从商品信息里提炼的，商品信息常常本身就是运营从别处粘来的半成品：
# 模板没替换干净就会留下 `{}` / `[待填]` / `XXX`，这些字符串**会进提示词**，
# 然后被画到图上（AI 出图的文字基本是错的，画出来就是一堆乱码）。
#
# `[1]`（引用序号）、`[图 2]`（配图位）是正常写法，一刀切按括号内容判会把好文案全拦下。
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    (re.compile(r"\{\{?\s*[\u4e00-\u9fffA-Za-z0-9_]*\s*\}?\}"), "{}",
     "残留了模板占位符 `{}`，模板没被替换干净"),
    (re.compile(r"[\[【(（]\s*(待填|填空|待补充|待完善|待定|待核实)\s*[\]】)）]"), "[]",
     "残留了占位符 `[待填]`，模型给自己留的空档没补"),
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
# 出图场景下这条更隐蔽：你不会一眼看出这张主图和示例长得一样，
# 而是「看起来挺正常」，直到发现五张主图是同一个模子、甚至跟示例图片类似。
#
# 判定：去标点后相等 → 命中；字符二元组 Jaccard ≥ 0.75 → 命中；
#       示例的二元组覆盖度 ≥ 0.60 → 命中。
#
# 【为什么还要第三条】出图提示词动辄 60~120 字，示例只有 25 字，Jaccard 的分母是
# 两份二元组的**并集**，示例那一侧被长提示词摊薄得极狠——示例原样塞进去也照样放行。
# 本族实测：
#   · 示例原样嵌入 + 补 9 个字（34 字）→ Jaccard 0.727（旧判据放行 ❌）覆盖度 1.000（拦 ✓）
#   · 示例原样嵌进一条 102 字的提示词 → Jaccard 0.245（漏）            覆盖度 1.000（抓住）
# 覆盖度只看「示例被抄了多少」，不看提示词有多长，摊薄对它无效。
# 阈值 0.60 的余量实测：17 条真实历史提示词里覆盖度最大只有 0.547，误伤 0 条。
#
# 【本包的长度守卫为什么与同族不同（主动偏离，已记在报告里）】
# 同族的守卫是 max(6, len(示例)//2)（示例 25 字 → 门槛 12），因为**内容平台的**
# 出图提示词本来就是 60~120 字。但**电商主图的**出图提示词惯常只有 30~50 字
# （「纯白背景，一双白色运动鞋，主体居中，柔光棚拍」＝22 字），
# 沿用 max(6, //2)=12 门槛会漏掉「示例原样当作整条提示词」这一最直接的照抄。
# 所以本包的守卫收紧成 min(20, max(6, len(示例)//4))：示例 25 字 → 门槛 6。
# ⚠️ 只改**门槛**，三条判据的**阈值一个都没动**（去标点相等 / 0.75 / 0.60）。
# 另外「去标点后完全相同」这条**不受长度门槛约束**（与同族一致），
# 所以门槛放宽到 6 不会让「整条照抄」漏网。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6
ECHO_MIN_LEN_CAP = 20


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：min(20, max(6, len(示例)//4))。"""
    return min(ECHO_MIN_LEN_CAP,
               max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 4))


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
      · 去标点后**完全相同**（最直接的照抄，不受长度门槛约束）
      · 字符二元组 Jaccard ≥ 0.75（长度相当的同构改写）
      · 示例的二元组**覆盖度 ≥ 0.60**（把示例夹带进更长的提示词里）

    返回 (是否命中, 分数, 撞上的示例, 判据)。
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


def prompt_gate(text):
    """对一段文本（出图提示词 / 卖点文案）跑三道本地闸门，返回命中列表。"""
    leaks = []
    for h in compliance_scan(text):
        leaks.append(("banned_word", "命中违禁词「%s」（%s 风险）：%s"
                      % (h["word"], h["level"], h["why"])))
    for h in placeholder_hits(text):
        leaks.append(("placeholder", "%s（命中 `%s`）" % (h["why"], h["word"])))
    echoed, score, sample, rule = prompt_echo(text)
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
    rec["notes"].append("提交时会先冻结（实测 frozen_points=31.2，**预冻结≠结算**），"
                        "完成后按 24 点结算，失败全额退回；只信 usage.points_cost")
    return rec


def fmt_cost(rec):
    if rec.get("total_points") is None:
        return "无法估算（%s）" % "；".join(rec.get("notes") or [])
    return "%d 张 × %g 点 = %g 点 = %.2f 元" % (
        rec["count"], rec["points_per_image"], rec["total_points"], rec["total_yuan"])


# ---------------------------------------------------------------------------
# 主图位完整性（闸门五）
#
# 电商主图位是**平台语义槽**：买家划到第 2 张想看规格，第 5 张找资质与售后。
# 缺位不是「少一张图」这么轻——缺第 5 位意味着买家在决策最后一刻找不到
# 资质与售后依据，直接影响转化；缺第 1 位则连入池机会都没有。
# 所以缺位要**标红并计入闸门失败**，而不是「提示一下」。
# ---------------------------------------------------------------------------

def slot_coverage(items, platforms=None):
    """检查五张主图位的覆盖情况，返回 (是否完整, 覆盖报告)。"""
    have = []
    for it in items or []:
        s = it.get("slot")
        if s and s not in have:
            have.append(s)
    missing = [s for s in SLOTS if s["slot"] not in have]
    unknown = [it.get("slot") for it in (items or [])
               if it.get("slot") and it.get("slot") not in SLOT_KEYS]
    required_missing = [s for s in missing if s["required"]]
    return (not required_missing), {
        "have": have,
        "missing": [{"slot": s["slot"], "cn": s["cn"], "index": s["index"],
                     "mission": s["mission"]} for s in missing],
        "required_missing": [s["slot"] for s in required_missing],
        "unknown_slots": [u for u in unknown if u],
        "complete": not required_missing,
    }


# ---------------------------------------------------------------------------
# 提示词：提炼卖点并按主图位分配
#
# 【铁律】提示词里不许出现任何一条可直接复制的完整出图提示词。
# 举例只用**登记在 PROMPT_SAMPLES 里的跨类目示例**（香蕉造型音箱、橙色圆形图标）。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是三剪客团队的电商视觉策划，负责把商品信息变成电商平台的主图与详情图方案。\n"
    "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
    "纪律（违反即返工）：\n"
    "1. 不编造商品信息里没有的数字、材质、认证、检测结论、销量、评价。\n"
    "2. 不使用广告法违禁词：最/第一/国家级/100%/绝对/根治/包治 等一律不许出现。\n"
    "3. 不伪造销量、评价、资质、检测报告；没有依据的卖点宁可不写。\n"
    "4. 不要在图上要求生成文字（AI 出图的文字基本都是错的，文字后期自己压）。"
)


def slot_block():
    lines = []
    for s in SLOTS:
        lines.append("- slot={slot}（第 {index} 张 · {cn}）：{mission}。{rule}".format(**s))
    return "\n".join(lines)


def platform_block(keys):
    lines = []
    for k in keys:
        pf = PLATFORMS[k]
        lines.append("- {key}（{name}）：主图像素 {px}，设计比例 {dr}，实际生成比例 {gr}。{note}".format(
            key=k, name=pf["name"], px=pf["main_px"], dr=pf["design_ratio"],
            gr=pf["gen_ratio"], note=pf["note"]))
    return "\n".join(lines)


def build_sellpoints_prompt(product, platforms, specs=None, usp=None,
                            audience=None, evidence=None, price=None):
    body = ["商品标题：%s" % product]
    if price:
        body.append("售价：%s" % price)
    if specs:
        body.append("规格参数：%s" % specs)
    if usp:
        body.append("已知卖点（运营提供）：%s" % usp)
    if audience:
        body.append("目标人群：%s" % audience)
    if evidence:
        body.append("**可出示的证据**（只有这些可以写成证据型文案）：%s" % evidence)
    else:
        body.append("**可出示的证据：无**。没有任何证据时，卖点只能写"
                    "「看得见的外观与规格」，**不许**写检测、认证、销量、评价、疗效。")
    src = "\n".join(body)
    return """给下面这个商品出一份**电商主图方案**：提炼卖点，并按主图位分配到 5 张图。

{src}

要覆盖的平台：
{platforms}

主图位（slot）的含义与要求，**逐条照做**：
{slots}

出方案的纪律：
- 一共 5 个 slot，每个 slot 恰好一条，顺序按第 1~5 张
- 每个 slot 的 `headline` 是**压在图上的短文案**，≤ 14 字，具体、可验证、不喊口号
- 每个 slot 的 `prompt` 是**直接发给文生图模型的出图提示词**，中文，30~60 字，
  要写清：主体、构图与视角、背景（白底位必须写「纯白背景」）、光线、色调、画风
- **不要在 prompt 里要求生成任何文字**（文字后期自己压）
- `evidence` 字段写这条卖点的**依据**；没有依据的卖点，evidence 必须写 "无依据-不建议投放"
- 不要编造商品信息里没有的数字、材质、认证、检测结论、销量、评价
- 不许出现绝对化用语（最/第一/国家级/100%/绝对 等）

只输出一个 JSON 对象，结构如下（不要输出别的任何东西）：
{{"items":[{{"slot":"main","headline":"压在图上的短文案","prompt":"出图提示词原文",
"evidence":"这条卖点的依据","why":"为什么把它放在这一位"}}]}}""".format(
        src=src, platforms=platform_block(platforms), slots=slot_block())


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


_ROLE_TO_SLOT = {"cover": "main"}          # 兼容外部喂进来的旧结构


def normalize_sellpoints(obj, platforms, product_image=None, allow_edit=True):
    """把模型产出收拾成内部结构：补平台/比例、按 slot 排序、跑本地闸门。

    **商品图驱动的落点就在这个函数里**：
      · 第 1~4 位（主图/规格/卖点/场景）用 action=generate —— 商品实物图在这几位是
        **风格与主体参考**，不作为 edit 的输入图（把商品硬贴进生成图容易出现变形与错位）；
      · 第 5 位（资质/售后）用 action=edit + image_urls —— 资质必须来自用户**真实持有**的材料，
        本包只改版式、不生成内容。没有资质图 URL 时如实缺位，交给主图位完整性闸门标红。
    """
    items_raw = obj.get("items") if isinstance(obj, dict) else obj
    if not isinstance(items_raw, list):
        raise a7w.A7wError("方案里没有 items 列表：%s" % json.dumps(obj, ensure_ascii=False)[:200])
    by_slot = {}
    for i, raw in enumerate(items_raw, 1):
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("slot") or "").strip()
        key = _ROLE_TO_SLOT.get(key, key)
        if key not in SLOT_KEYS:
            key = SLOT_KEYS[min(i - 1, len(SLOT_KEYS) - 1)]
        if key in by_slot:
            continue                       # 一个 slot 只收第一条（提示词里已要求恰好一条）
        by_slot[key] = raw
    out = []
    for s in SLOTS:
        raw = by_slot.get(s["slot"])
        if raw is None:
            continue                       # 缺位**不补**：缺位本身要如实报出来
        platform = str(raw.get("platform") or platforms[0]).strip()
        if platform not in PLATFORMS:
            platform = platforms[0]
        pf = PLATFORMS[platform]
        ar = str(raw.get("aspect_ratio") or pf["gen_ratio"]).strip()
        if ar not in ASPECT_RATIOS:
            ar = pf["gen_ratio"]
        prompt = re.sub(r"\s+", " ", str(raw.get("prompt") or "")).strip()
        headline = re.sub(r"\s+", " ", str(raw.get("headline") or "")).strip()
        # 白底位：平台要求第 1 张纯白背景，提示词里没写就**补上**并标注
        added_white = False
        if pf.get("slot1_white_bg") and s["slot"] == "main" and "纯白" not in prompt:
            prompt = ("纯白背景，" + prompt) if prompt else "纯白背景，商品主体居中"
            added_white = True
        action = "edit" if (s["slot"] == "qualification" and platform_image_ok(product_image)) \
            else "generate"
        if action == "edit" and not allow_edit:
            action = "generate"
        item = {
            "id": s["index"], "slot": s["slot"], "slot_cn": s["cn"],
            "platform": platform, "platform_name": pf["name"],
            "design_ratio": pf["design_ratio"], "main_px": pf["main_px"],
            "aspect_ratio": ar, "resolution": "1K",
            "headline": headline, "prompt": prompt,
            "evidence": str(raw.get("evidence") or "").strip(),
            "why": str(raw.get("why") or "").strip(),
            "action": action,
            "image_urls": [product_image] if action == "edit" else None,
            "white_bg_filled": added_white,
        }
        item["leaks"] = prompt_gate(item["headline"]) + prompt_gate(item["prompt"])
        item["leaks"] = _dedup_leaks(item["leaks"])
        item["evidence_unfounded"] = bool(
            item["evidence"] and re.search(r"无依据|不建议投放|待核实", item["evidence"]))
        # ⚠️ 资质位没有**真实持有的资质图**时，必须显式提醒。
        # 真机实测踩到：模型会给第 5 位写一条「自有实拍图与拆解视频」当依据，
        # 然后照样生成一张**它自己画出来的「资质图」**——用户很可能直接拿去上架，
        # 那图上的「资质」是编的。本包的立场是：**不生成资质**，只改真实材料的版式。
        item["qualification_missing"] = (s["slot"] == "qualification"
                                         and not platform_image_ok(product_image))
        if item["qualification_missing"]:
            item["evidence_note"] = (
                "未提供真实资质图（--product-image 不是可访问的 URL）："
                "这一位若照常出图，产出的是**模型画的示意版式**，不是资质本身，"
                "**不许当作资质材料上架**。请提供你真实持有的资质图后重跑。")
        else:
            item["evidence_note"] = ""
        out.append(item)
    return out


def platform_image_ok(url):
    return bool(url and str(url).startswith("http"))


def _dedup_leaks(leaks):
    seen, out = set(), []
    for kind, why in leaks:
        k = (kind, why)
        if k not in seen:
            seen.add(k)
            out.append((kind, why))
    return out


# ---------------------------------------------------------------------------
# 断点续跑
#
# 出图是**异步 + 按次扣费**的：一次抖动、一次 Ctrl+C，都会让「已经提交并冻结了点数」
# 的任务悬在那里。如果没有断点记录，重跑会把同一张图再买一遍。
#
# ⚠️ 本族的断点 key 事故（**全部实测踩过，一条都不能省**）：
#   · 内容截断：曾用 `_norm(prompt)[:24]` 当 key → 提示词**只改第 25 字之后**的内容时
#     key 不变 → 静默复用旧图。用户以为重出了，其实拿到的是旧图，而且**一句提示都没有**。
#     所以这里对**完整提示词**取摘要，绝不截断。
#   · resolution 不入 key：曾用「id + 提示词摘要」→ 先跑 1K 再改 `--resolution 4K` 重跑，
#     key 不变 → 复用了 1K 的图，用户以为拿到 4K。所以 resolution 直接进 key。
#   · 死参数：`resolution` 被解析了却从不生效（写死 "1K"）→ `--resolution 4K` 静默变 1K，
#     且因为 resolution 没进 key，两处都发现不了。所以建 item 时就用传入的 resolution。
#
# key 必须含**全部影响产出的维度**：
#     id + slot + 提示词全文摘要 + 比例 + resolution + 模型 + action（+ edit 的参考图）
# 少任何一维 = 静默复用过期产物。多扣一次费用户立刻会发现；复用旧图不会。
# 「静默复用过期产物」比多扣一次费危险得多，这是本族用真钱换来的结论。
# ---------------------------------------------------------------------------

def state_key(item):
    payload = "|".join([
        item["prompt"],
        item.get("aspect_ratio") or "",
        (item.get("resolution") or "1K").upper(),
        item.get("model") or "nano-banana",
        item.get("action") or "generate",
        "|".join(item.get("image_urls") or []),
    ])
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return "img:%s:%s:%s:%s:%s:%s" % (
        item.get("id"), item.get("slot") or "-",
        (item.get("resolution") or "1K").upper(),
        item.get("aspect_ratio") or "-",
        item.get("action") or "generate", digest)


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


def _prev_consistent(prev, item):
    """断点命中的**二次兜底**：key 相同不代表记录可信（旧版断点 / 手工改过）。

    说不出上次是什么档（没存 resolution）、或记录里的提示词与本轮不一致，一律**不复用**。
    """
    if not prev:
        return True, None
    prev_res = prev.get("resolution")
    want_res = (item.get("resolution") or "1K").upper()
    if not isinstance(prev_res, str) or prev_res.upper() != want_res:
        return False, ("断点记录里的分辨率（%s）与本次（%s）不一致"
                       % (prev_res or "没存", want_res))
    if _norm_for_echo(prev.get("prompt")) != _norm_for_echo(item.get("prompt")):
        return False, "断点记录里的提示词与本次不一致"
    if (prev.get("action") or "generate") != (item.get("action") or "generate"):
        return False, ("断点记录里的 action（%s）与本次（%s）不一致"
                       % (prev.get("action") or "generate", item.get("action")))
    return True, None


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "!! " + s
    return "\033[31m" + s + "\033[0m"


def _resolve_platforms(names):
    out = []
    for n in names or ["taobao"]:
        key = str(n).strip()
        if key not in PLATFORMS:
            raise a7w.A7wError("未知平台 %r；可选：%s" % (key, " / ".join(PLATFORMS)))
        if key not in out:
            out.append(key)
    return out


def _pkg_dir():
    return Path(__file__).resolve().parent.parent


def _check_outdir(outdir):
    """产出图不许进包：--outdir 在包内 → 抛错（调用方转成 exit 2）。"""
    p = Path(outdir).resolve()
    pkg = _pkg_dir()
    try:
        p.relative_to(pkg)
    except ValueError:
        return p
    raise a7w.A7wError(
        "输出目录 %s 在 Skill 包内。包内不许有任何图片（上传白名单只收文本文件），"
        "请换到包外，例如 %s" % (p, Path(os.environ.get("TEMP") or ".") / "ecom-image-out"))


# --- specs（零网络、零成本）---

def cmd_specs(a):
    keys = _resolve_platforms(a.platform) if a.platform else list(PLATFORMS)
    data = {"platforms": [{"key": k, **PLATFORMS[k]} for k in keys],
            "slots": SLOTS,
            "measured_1k_pixels": MEASURED_1K_PIXELS,
            "ratio_tolerance": RATIO_TOLERANCE,
            "detail_screen_px": list(DETAIL_SCREEN_PX),
            "note": ("design_ratio 是平台要求的比例；gen_ratio 是喂给上游 nano_banana 的 "
                     "aspect_ratio。上游按 32 对齐（3:4 实得 864x1184，偏差 2.70%），"
                     "要像素级精确比例加 --snap。")}
    if a.json:
        _json_out(data, a, indent=1)
        return 0
    print("电商主图规格（零网络、零成本）\n")
    print("%-12s %-22s %-10s %-9s %-9s %s" % ("key", "平台", "主图像素", "设计比例", "生成比例", "白底首图"))
    for k in keys:
        pf = PLATFORMS[k]
        print("%-12s %-22s %-10s %-9s %-9s %s" % (
            k, pf["name"], pf["main_px"], pf["design_ratio"], pf["gen_ratio"],
            "是" if pf.get("slot1_white_bg") else "否"))
    print("\n五张主图位（顺序即平台语义）：")
    for s in SLOTS:
        print("  第 %d 张  %-6s %-6s %s" % (s["index"], s["slot"], s["cn"], s["mission"]))
    print("\n上游 1K 档实测像素（按 32 对齐，10 种比例里 5 种拿不到精确比例）：")
    for ar, px in MEASURED_1K_PIXELS.items():
        want = parse_ratio(ar)
        real = px[0] / float(px[1])
        dev = abs(real - want) / want * 100 if want else 0.0
        print("  %-6s → %dx%d  实际 %.4f  偏差 %.2f%%" % (ar, px[0], px[1], real, dev))
    print("\n详情页：宽度固定 750，按屏出图（单屏 3:4），**拼接在本地做**。")
    print("比例容差默认 %.0f%%，容差内也照打真实像素与偏差；要裁准加 --snap。" % (RATIO_TOLERANCE * 100))
    return 0


# --- sellpoints ---

def cmd_sellpoints(a):
    platforms = _resolve_platforms(a.platform)
    product = (a.product or "").strip()
    if not product:
        raise a7w.A7wError("请用 --product 给商品标题")
    prompt = build_sellpoints_prompt(product, platforms, a.specs, a.usp,
                                     a.audience, a.evidence, a.price)
    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "system": SYSTEM_PROMPT, "user": prompt}, a, indent=1)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (SYSTEM_PROMPT, prompt))
        return 0
    sys.stderr.write("正在用 `%s` 提炼卖点并分配到主图位…\n" % a.model)
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    items = normalize_sellpoints(parse_first_json(content), platforms,
                                 a.product_image, allow_edit=not a.no_edit)
    if not items:
        raise a7w.A7wError("模型没产出任何主图位")
    for it in items:
        it["resolution"] = (a.resolution or "1K").upper()
    ok, cov = slot_coverage(items)
    plan = {"product": product, "platforms": platforms, "count": len(items),
            "model": a.model, "usage": usage, "elapsed_sec": round(elapsed, 1),
            "product_image": a.product_image, "slots_covered": cov,
            "items": items}
    if a.out:
        Path(a.out).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        _json_out(plan, a, indent=1, ok=ok and not any(it["leaks"] for it in items))
    else:
        _render_sellpoints(plan)
    cost = estimate_cost(len(items), items[0]["resolution"], a.points_per_image)
    if a.json:
        sys.stderr.write("\n预估出图成本（这一步还没出图，只花了文本钱）：\n  %s\n" % fmt_cost(cost))
    else:
        print("\n预估出图成本（这一步还没出图，只花了文本钱）：")
        print("  " + fmt_cost(cost))
    if a.out and not a.json:
        sys.stderr.write("方案已写入 %s\n" % a.out)
    rc = 0
    if not ok or any(it["leaks"] for it in items):
        rc = _fail(3, "gate", "卖点方案命中闸门（违禁词/占位符/照抄示例）或主图位缺位")
        rc = 3
    return rc


def _render_sellpoints(plan):
    print("电商主图方案：%s" % plan["product"])
    print("平台：%s   共 %d 个图位   模型：%s   耗时 %.1fs"
          % ("、".join(PLATFORMS[p]["name"] for p in plan["platforms"]),
             plan["count"], plan["model"], plan["elapsed_sec"]))
    print()
    for it in plan["items"]:
        print("#%d  第 %d 张  %-6s %-6s  %-9s %-5s action=%s" % (
            it["id"], it["id"], it["slot"], it["slot_cn"], it["aspect_ratio"],
            it["resolution"], it["action"]))
        print("     压图文案：%s" % (it["headline"] or "（空）"))
        print("     出图提示词：%s" % it["prompt"])
        if it["evidence"]:
            print("     卖点依据：%s" % it["evidence"])
        if it["evidence_unfounded"]:
            print("     " + _red("✗ 这条卖点自报无依据，不建议投放"))
        if it.get("qualification_missing"):
            print("     " + _red("✗ 资质位没有真实资质图：%s" % it["evidence_note"]))
        if it["white_bg_filled"]:
            print("     · 白底首图：提示词里没写纯白背景，已自动补上")
        if it.get("image_urls"):
            print("     参考图（action=edit）：%s" % ", ".join(it["image_urls"]))
        for kind, why in it["leaks"]:
            print("     " + _red("✗ %s：%s" % (kind, why)))
    cov = plan["slots_covered"]
    print()
    if cov["complete"]:
        print("主图位完整性：完整（5/5）")
    else:
        print(_red("主图位完整性：缺 %d 位 → %s"
                   % (len(cov["required_missing"]),
                      "、".join("%s（第 %d 张）" % (m["cn"], m["index"])
                                for m in cov["missing"]))))
        print(_red("  缺第 5 张资质位意味着买家在决策最后一刻找不到资质与售后依据；"
                   "本包**不生成资质**，请提供你真实持有的资质图 URL。"))
    hits = [it for it in plan["items"] if it["leaks"]]
    if hits:
        sys.stderr.write("\n!! %d 个图位的文案命中本地闸门（违禁词 / 占位符 / prompt_echo），"
                         "改掉后再出图\n" % len(hits))
    if not cov["complete"]:
        sys.stderr.write("\n!! 主图位缺位 %s，补位后再出图（或用 --allow-missing-slots 只出已有的）\n"
                         % "、".join(cov["required_missing"]))


# --- compliance（零成本）---

def cmd_compliance(a):
    parts = []
    if a.file:
        p = Path(a.file)
        if not p.is_file():
            raise a7w.A7wError("找不到文件：%s" % a.file)
        parts.append(p.read_text(encoding="utf-8", errors="replace"))
    for t in (a.text or []):
        parts.append(t)
    if not parts:
        raise a7w.A7wError("请用 --text 给文案，或用 --file 给文案文件")
    text = "\n".join(parts)
    hits = compliance_scan(text)
    phs = placeholder_hits(text)
    echoed, score, sample, rule = prompt_echo(text)
    verdict = "pass"
    for h in hits:
        v = VERDICT_BY_LEVEL.get(h["level"], "check")
        if v == "blocked":
            verdict = "blocked"
            break
        if v == "review" and verdict in ("pass", "check"):
            verdict = "review"
        elif v == "check" and verdict == "pass":
            verdict = "check"
    if phs and verdict == "pass":
        verdict = "check"
    if echoed and verdict in ("pass", "check"):
        verdict = "review"
    rec = {"verdict": verdict, "hits": hits, "placeholders": phs,
           "prompt_echo": {"hit": echoed, "score": round(score, 4),
                           "sample": sample[:28], "rule": rule},
           "note": ("这是**启发式自检工具**，按子串/正则匹配，不理解语义、不看图片、"
                    "不做谐音识别；不构成法律意见，也不代表任何平台的官方审核标准。"
                    "高风险类目（食品/保健/医疗/母婴/化妆品/3C 认证）必须人工复核。")}
    if a.json:
        _json_out(rec, a, indent=1, ok=(verdict == "pass"))
    else:
        print("合规自检结论：**%s**" % verdict)
        if hits:
            print("命中违禁词 %d 条：" % len(hits))
            for h in hits:
                print("  " + _red("[%s] %s —— %s" % (h["level"], h["word"], h["why"])))
        else:
            print("违禁词：无命中")
        if phs:
            print("占位符残留 %d 条：" % len(phs))
            for h in phs:
                print("  " + _red("%s（%s）" % (h["why"], h["kind"])))
        if echoed:
            print("  " + _red("prompt_echo：与示例「%s」相似度 %.2f（%s）" % (sample[:28], score, rule)))
        print("\n口径：%s" % rec["note"])
    rc = 0
    if verdict == "blocked":
        _fail(1, "gate", "合规自检未通过：命中高风险违禁词")
        rc = 1
    elif a.strict and verdict != "pass":
        _fail(1, "gate", "合规自检未通过（--strict）：结论 %s" % verdict)
        rc = 1
    return rc


# --- cost ---

def cmd_cost(a):
    rec = estimate_cost(a.count, a.resolution, a.points_per_image)
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
            print("  · 预算 %g 点：%s" % (a.budget, "超了，images 会被拦下" if over else "在预算内"))
    if no_price:
        sys.stderr.write("!! 拿不到该档的可信单价，无法完成成本前置检查\n")
    return rc


# --- models ---

def cmd_models(a):
    import urllib.request
    import urllib.error
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
    print("\n注意：平台文档里的价格字段（pricing_matrix / tenant_*）我们验证过半数不可信，")
    print("     结算价只认任务返回的 usage.points_cost；frozen_points 是预冻结不是结算。")
    return 0


# --- images ---

def _print_images_plan(items, outdir, resolution, override):
    print("将要出图：%d 张" % len(items))
    for it in items:
        print("  #%-3d %-6s %-6s %-12s %-6s %-5s action=%-8s %s" % (
            it["id"], it.get("slot") or "-", it.get("slot_cn") or "-",
            PLATFORMS[it["platform"]]["name"], it["aspect_ratio"], it["resolution"],
            it.get("action") or "generate",
            it["prompt"][:44] + ("…" if len(it["prompt"]) > 44 else "")))
    print("  输出目录：%s  （**必须不在 Skill 包内**）" % outdir)
    print("  单张成本：%s" % ("%g 点" % unit_points(resolution, override)
                              if unit_points(resolution, override) is not None
                              else "未知（%s 档无实测价）" % resolution))


def cmd_images(a):
    """入口：`--json` 时把人读输出（报价、进度、逐张结果）整体导向 stderr。

    这样 stdout 里只剩一个完整 JSON，`json.loads` 才能直接用。
    """
    out_raw = sys.stdout
    if getattr(a, "json", False):
        sys.stdout = sys.stderr
    try:
        return _cmd_images_impl(a, out_raw)
    finally:
        sys.stdout = out_raw


def _load_items(a):
    """方案来源：`--plan` JSON，或 `--product` 现出（走 sellpoints）。

    两条路都做同一件事：拿到一份 items（带 slot / prompt / aspect_ratio / action）。
    """
    if a.plan:
        plan_path = Path(a.plan)
        if not plan_path.is_file():
            raise a7w.A7wError("找不到方案文件：%s（先用 `sellpoints` 生成）" % a.plan)
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise a7w.A7wError("方案文件读不动或不是合法 JSON：%s（%s）" % (a.plan, exc))
        items = plan.get("items") or []
        if not items:
            raise a7w.A7wError("方案文件里没有 items：%s" % a.plan)
        for it in items:
            if "slot" not in it and it.get("role"):
                it["slot"] = _ROLE_TO_SLOT.get(it["role"], it["role"])
        return items, plan
    if not a.product:
        raise a7w.A7wError("请用 --plan 给方案文件，或用 --product 现出方案")
    platforms = _resolve_platforms(a.platform)
    prompt = build_sellpoints_prompt(a.product, platforms, a.specs, a.usp,
                                     a.audience, a.evidence, a.price)
    sys.stderr.write("正在用 `%s` 现出主图方案（花文本钱）…\n" % a.model)
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    items = normalize_sellpoints(parse_first_json(content), platforms,
                                 a.product_image, allow_edit=not a.no_edit)
    return items, {"product": a.product, "platforms": platforms,
                   "usage": usage, "source": "inline"}


def _cmd_images_impl(a, out_raw):
    items, plan = _load_items(a)
    if not items:
        raise a7w.A7wError("方案里没有任何图位")

    platforms = [str(x) for x in (a.platform or [])]
    if platforms:
        items = [it for it in items if it.get("platform") in platforms]
        if not items:
            raise a7w.A7wError("按 --platform %s 过滤后没有条目" % "、".join(platforms))
    if a.slot:
        items = [it for it in items if it.get("slot") in a.slot]
        if not items:
            raise a7w.A7wError("按 --slot %s 过滤后没有条目" % "、".join(a.slot))
    if a.count:
        items = items[:a.count]
    for it in items:
        if a.resolution:
            it["resolution"] = a.resolution.upper()
        it.setdefault("resolution", "1K")
        it.setdefault("model", a.image_model or "nano-banana")
        it.setdefault("action", "generate")
        if a.model_image_override:
            it["model"] = a.model_image_override
        if it["action"] == "edit" and not (it.get("image_urls")):
            if a.product_image:
                it["image_urls"] = [a.product_image]
            else:
                it["action"] = "generate"
                sys.stderr.write("⚠ #%s 资质位没有可用的参考图 URL（--product-image），"
                                 "改为 generate。本包**不生成资质内容**，"
                                 "请提供你真实持有的资质图。\n" % it.get("id"))
    # 资质位没有真实材料时，再明确提醒一次（真机实测：模型会照样画一张「资质图」出来）
    for it in items:
        if it.get("slot") == "qualification" and not it.get("image_urls"):
            sys.stderr.write(
                "⚠ 第 %s 张资质位没有真实资质图：这次产出的是**示意版式**，不是资质本身，"
                "**不许当作资质材料上架**。\n" % it.get("id"))
    # 主图位完整性（闸门五）
    ok, cov = slot_coverage(items)
    if not ok and not a.allow_missing_slots:
        for m in cov["missing"]:
            sys.stderr.write("!! 主图位缺位：第 %d 张 %s（%s）——%s\n"
                             % (m["index"], m["cn"], m["slot"], m["mission"]))
        sys.stderr.write(
            "\n共缺 %d 个必填图位，**已拦截，未提交任何任务**（不花一分钱）。\n"
            "补位后重跑；只想出已有图位就加 --allow-missing-slots。\n"
            % len(cov["required_missing"]))
        return _fail(3, "gate", "主图位缺位 %s，已拦截、未提交任何任务"
                     % "、".join(cov["required_missing"]))

    # 闸门一/二/三：出图前把文案再扫一遍（方案文件可能是手改过的）
    blocked = []
    for it in items:
        text = "%s\n%s" % (it.get("headline") or "", it.get("prompt") or "")
        it["leaks"] = it.get("leaks") or prompt_gate(text)
        if it["leaks"]:
            blocked.append(it)
    if blocked and not a.allow_prompt_hits:
        for it in blocked:
            sys.stderr.write("!! #%s（第 %s 张 %s）文案命中闸门：\n"
                             % (it.get("id"), it.get("id"), it.get("slot_cn") or "-"))
            for kind, why in it["leaks"]:
                sys.stderr.write("     %s\n" % _red("%s：%s" % (kind, why)))
        sys.stderr.write(
            "\n共 %d 张被判不合格，**已拦截，未提交任何任务**（不花一分钱）。\n"
            "改掉文案后重跑；确实要带违禁词出图才加 --allow-prompt-hits。\n" % len(blocked))
        return _fail(3, "gate", "有图位文案命中本地闸门，已拦截、未提交任何任务")

    # 闸门六：产出图不许进包
    outdir = _check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state_path = a.state or str(outdir / STATE_NAME)
    state = load_state(state_path)

    resolution = items[0]["resolution"]
    cost = estimate_cost(len(items), resolution, a.points_per_image)
    _print_images_plan(items, outdir, resolution, a.points_per_image)
    print("\n预估成本：%s" % fmt_cost(cost))
    for n in cost.get("notes") or []:
        print("  · %s" % n)

    # 闸门：成本上限。**在提交任何任务之前**判，超了直接停。
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
        it["model"] = it.get("model") or "nano-banana"
        key = state_key(it)
        prev = state["items"].get(key)
        consistent, why = _prev_consistent(prev, it)
        if not consistent:
            sys.stderr.write("    #%s %s → **不复用旧图**，重新出图\n" % (it.get("id"), why))
            prev = None
        if prev and prev.get("status") == "completed" and not a.force:
            pts = prev.get("points_cost")
            # ⚠️ 跳过的那张**上次已经真扣过费**，必须计入 total_points，
            # 否则续跑跑完，汇总里的「累计扣费」会比真实花的少。
            # spent_this_run 不加（那次不是本次花的），两个数分开报。
            total_points += float(pts or 0)
            skipped.append((it, prev))
            print("[%d/%d] #%s 已完成，跳过（上次扣费 %s 点，不再重复扣）"
                  % (n, len(items), it.get("id"), pts))
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
                  % (n, len(items), it.get("id"), task_id))
        else:
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
            sys.stderr.write("[%d/%d] #%s 提交：slot=%s action=%s aspect_ratio=%s "
                             "resolution=%s model=%s\n"
                             % (n, len(items), it.get("id"), it.get("slot"),
                                it.get("action"), it["aspect_ratio"],
                                it["resolution"], it.get("model")))
            try:
                data = submit_image(it["prompt"], aspect_ratio=it["aspect_ratio"],
                                    resolution=it["resolution"], model=it.get("model"),
                                    action=it.get("action") or "generate",
                                    image_urls=it.get("image_urls"), key=a.key)
            except a7w.A7wError as exc:
                sys.stderr.write("    提交失败：%s\n" % exc)
                failed.append({"id": it.get("id"), "stage": "submit", "error": str(exc)})
                if a.stop_on_error:
                    save_state(state_path, state)
                    return _fail(2, "call", "一张失败就整体停（--stop-on-error）")
                continue
            task_id = data.get("task_id")
            state["items"][key] = {
                "id": it.get("id"), "slot": it.get("slot"),
                "platform": it.get("platform"), "headline": it.get("headline"),
                "prompt": it["prompt"], "aspect_ratio": it["aspect_ratio"],
                "resolution": it["resolution"], "model": it.get("model"),
                "action": it.get("action"), "image_urls": it.get("image_urls"),
                "task_id": task_id, "status": "pending",
                # frozen_points 是**预冻结**（实测 31.2），不是结算价，只作记录
                "frozen_points": data.get("frozen_points"),
                "request": {"prompt": it["prompt"], "action": it.get("action"),
                            "resolution": it["resolution"],
                            "aspect_ratio": it["aspect_ratio"],
                            "model": it.get("model"),
                            "image_urls": it.get("image_urls")},
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
            failed.append({"id": it.get("id"), "stage": "poll", "task_id": task_id,
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
            failed.append({"id": it.get("id"), "stage": "task", "task_id": task_id,
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
            failed.append({"id": it.get("id"), "stage": "no_url", "task_id": task_id,
                           "raw_task": payload})
            continue

        url = urls[0]
        dest = outdir / ("%s-%s-%s-%s%s" % (
            it.get("id"), it.get("slot") or "-",
            it["aspect_ratio"].replace(":", "x"),
            key.split(":")[-1], OUT_EXT))
        try:
            a7w.save(url, str(dest))
        except a7w.A7wError as exc:
            rec["status"] = "failed"
            rec["error"] = "下载失败：%s" % exc
            rec["image_url"] = url
            save_state(state_path, state)
            failed.append({"id": it.get("id"), "stage": "download", "task_id": task_id,
                           "error": str(exc), "image_url": url})
            continue

        # 闸门四：比例真伪。want 用**平台设计比例**优先（电商要的是平台比例，
        # 不是上游能给的最近比例），所以电商场景默认就该按设计比例裁。
        want = PLATFORMS[it["platform"]]["design_ratio"] if (a.snap_on_design or a.snap) \
            else it["aspect_ratio"]
        if it["platform"] == "detail":
            want = it["aspect_ratio"]        # 详情页单屏按生成比例，设计口径是长图拼接
        check = check_ratio(str(dest), want, a.ratio_tolerance)
        first_check = dict(check)            # 保留裁剪前的原始判定（上游到底给了什么）
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
                rec["snap"] = {"method": way, "box": box, "file": snapped, "after": after}
                if after["ok"]:
                    dest = Path(snapped)
                    check = after
                    rec["real_px"] = after["real_px"]
                    rec["real_ratio"] = after.get("real_ratio")
                    rec["ratio_deviation"] = after["deviation"]
                    rec["file"] = str(snapped)
            else:
                rec["snap"] = {"method": None,
                               "why": "没有 PIL，内置裁剪器也不支持这个 PNG"
                                      "（需 8 位真彩/真彩+alpha）"}
        rec["raw_ratio_check"] = check

        rec["ratio_ok"] = bool(check["ok"])
        rec["status"] = "completed"
        save_state(state_path, state)
        if check["ok"]:
            done.append((it, rec))
            print("    完成 真实像素 %sx%s  比例 %s  偏差 %.2f%%  扣费 %s 点  → %s"
                  % (check["real_px"][0], check["real_px"][1], check.get("real_label"),
                     (check.get("deviation") or 0) * 100, pts, rec["file"]))
        else:
            ratio_bad.append((it, rec))
            print("    " + _red("完成但比例不合格：%s" % check.get("why")))
            print("    " + _red("  → %s" % rec["file"]))

    # ------------------------------------------------------------------
    # 收尾
    # ------------------------------------------------------------------
    summary = {
        "plan": a.plan, "product": plan.get("product"), "outdir": str(outdir),
        "state": state_path, "platforms": plan.get("platforms"),
        "planned_images": len(items),
        "slots_covered": slot_coverage(items)[1],
        "completed": [{"id": it.get("id"), "slot": it.get("slot"),
                       "headline": it.get("headline"), "action": it.get("action"),
                       "task_id": r.get("task_id"), "file": r.get("file"),
                       "real_px": r.get("real_px"), "want_ratio": r.get("want_ratio"),
                       "real_ratio": r.get("real_ratio"),
                       "deviation": r.get("ratio_deviation"),
                       "points_cost": r.get("points_cost"),
                       "frozen_points": r.get("frozen_points"),
                       "image_url": r.get("image_url"), "request": r.get("request"),
                       "first_check": r.get("first_check"), "snap": r.get("snap"),
                       "raw_task": r.get("raw_task")}
                      for it, r in done],
        "skipped_already_done": [{"id": it.get("id"), "task_id": r.get("task_id"),
                                  "file": r.get("file"), "points_cost": r.get("points_cost"),
                                  "real_px": r.get("real_px")}
                                 for it, r in skipped],
        "ratio_failed": [{"id": it.get("id"), "slot": it.get("slot"), "file": r.get("file"),
                          "real_px": r.get("real_px"), "want_ratio": r.get("want_ratio"),
                          "why": (r.get("raw_ratio_check") or {}).get("why")}
                         for it, r in ratio_bad],
        "failed": failed,
        "points_cost_total": total_points,
        "points_cost_this_run": spent_this_run,
        "yuan_this_run": round(spent_this_run / float(POINTS_PER_YUAN), 3),
        "estimate": cost,
    }
    if a.json:
        (_JSON["stdout"] or out_raw).write(
            _json_text(summary, indent=1, ok=not (failed or ratio_bad)) + "\n")
        _JSON["emitted"] = True
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
                              % (it.get("id"), r["real_px"][0], r["real_px"][1],
                                 r.get("want_ratio"))))
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


# --- all ---

def cmd_all(a):
    """sellpoints → images 一条龙。花钱的那一段仍然要 --yes。"""
    # 与 cmd_images 同口径：记下**真 stdout** 后再换，避免两处重定向互相踩。
    out_raw = _JSON["stdout"] or sys.stdout
    if getattr(a, "json", False):
        sys.stdout = sys.stderr
    try:
        if a.dry_run:
            return cmd_sellpoints(a)
        rc1 = cmd_sellpoints(a)
        if rc1 and not a.allow_prompt_hits:
            return rc1
        plan_out = a.plan_out or a.out
        if not plan_out:
            raise a7w.A7wError("`all` 需要 --plan-out 指定方案文件路径（供 images 复用）")
        a.plan = plan_out
        return _cmd_images_impl(a, out_raw)
    finally:
        sys.stdout = out_raw


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封（已经吐过结果的，ok 写在那个结果里）
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**
#   · 未捕获异常 → `kind: "internal"` + **完整 traceback 原样打到 stderr**，退出码固定 1
#   · `--json` 写在子命令**前面或后面**都可以（见 `_add_json`）
#
# 信封必须落在**真 stdout**：cmd_images / cmd_all 会在执行期间把 sys.stdout 临时换成
# stderr，所以 JSON 文本统一经 `_json_write` 写到进 main() 时记住的那份真 stdout。
# ---------------------------------------------------------------------------

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}

_KIND_BY_EXIT = {1: "gate", 2: "call", 3: "gate", 4: "usage", 5: "interrupt", 130: "interrupt"}


def _json_payload(obj, ok=True):
    if isinstance(obj, dict):
        out = {"ok": bool(ok)}
        out.update(obj)
        return out
    return {"ok": bool(ok), "data": obj}


def _json_text(obj, indent=1, ok=True):
    return json.dumps(_json_payload(obj, ok), ensure_ascii=False, indent=indent)


def _json_write(text):
    (_JSON["stdout"] or sys.stdout).write(text + "\n")
    _JSON["emitted"] = True


def _json_want(a=None):
    if a is not None:
        return bool(getattr(a, "json", False))
    return bool(_JSON["want"])


def _json_out(obj, a=None, indent=1, ok=True):
    if not _json_want(a):
        return False
    _json_write(_json_text(obj, indent=indent, ok=ok))
    return True


def _json_fail(rc, kind=None, message=None, detail=None, a=None):
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
    如果本次已经吐过结果，就**不再补信封**（守住「stdout 永远只有一个 JSON」这条不变量）。
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
    """让 `--json` 写在子命令**前后都能用**（与同族同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py specs --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_product_args(p, with_resolution=True):
    p.add_argument("--product", help="商品标题（出方案的输入）")
    p.add_argument("--platform", action="append", choices=list(PLATFORMS),
                   help="目标平台，可重复；默认 taobao")
    p.add_argument("--specs", help="规格参数（尺寸/容量/材质/型号）")
    p.add_argument("--usp", help="运营提供的已知卖点")
    p.add_argument("--audience", help="目标人群")
    p.add_argument("--evidence", help="**可出示的证据**（检测报告/资质/专利）；没有就别填")
    p.add_argument("--price", help="售价（写进方案上下文，不上图）")
    p.add_argument("--product-image", help="商品实物图 URL（公网可访问；资质位走 action=edit 时用）")
    p.add_argument("--no-edit", action="store_true",
                   help="禁止 action=edit，全部用 generate（默认资质位允许 edit）")
    p.add_argument("--model", default=DEFAULT_MODEL, help="文本模型，默认 %s" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--no-json-mode", action="store_true", help="不要求上游返回 JSON 对象")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    if with_resolution:
        p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS),
                       help="出图分辨率，默认 1K")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 电商主图工厂：给商品信息，按平台规格批量产出主图与详情图")
    ap.add_argument("--key", help="临时指定 api.a7w.cn 的 Key（别写进脚本或文档）")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --- specs ---
    p = sub.add_parser("specs", help="列出各平台主图规格（零网络、零成本）")
    _add_json(p)
    p.add_argument("--platform", action="append", choices=list(PLATFORMS),
                   help="只看某平台，可重复")
    p.set_defaults(func=cmd_specs)

    # --- sellpoints ---
    p = sub.add_parser("sellpoints", help="提炼卖点并分配到主图位（文本）")
    _add_json(p)
    _add_product_args(p)
    p.add_argument("--out", help="把方案写成 JSON（images 要用它）")
    p.add_argument("--dry-run", action="store_true", help="只打印提示词，不调模型、不花钱")
    p.set_defaults(func=cmd_sellpoints)

    # --- compliance ---
    p = sub.add_parser("compliance", help="卖点文案合规自检（零成本、纯本地）")
    _add_json(p)
    p.add_argument("--text", action="append", help="待检文案，可重复")
    p.add_argument("--file", help="待检文案文件")
    p.add_argument("--strict", action="store_true",
                   help="非 pass 结论一律退出码 1（CI 卡门禁）")
    p.set_defaults(func=cmd_compliance)

    # --- cost ---
    p = sub.add_parser("cost", help="只算钱不出图")
    _add_json(p)
    p.add_argument("--count", type=int, required=True, help="要出几张")
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--budget", type=float, help="预算上限（点），超了退出码非 0")
    p.set_defaults(func=cmd_cost)

    # --- models ---
    p = sub.add_parser("models", help="列出在架应用与模型")
    _add_json(p)
    p.set_defaults(func=cmd_models)

    # --- images ---
    p = sub.add_parser("images", help="批量出图（真花钱：先报价、要 --yes）")
    _add_json(p)
    _add_product_args(p)
    p.add_argument("--plan", help="sellpoints 产出的方案 JSON（给这个就不用 --product）")
    p.add_argument("--slot", action="append", choices=SLOT_KEYS,
                   help="只出某几个图位，可重复")
    p.add_argument("--count", type=int, help="最多出几张（截断方案）")
    p.add_argument("--image-model", default="nano-banana",
                   help="出图模型，默认 nano-banana")
    p.add_argument("--model-image", dest="model_image_override",
                   help="（同 --image-model，覆盖方案里每条的 model）")
    p.add_argument("--outdir",
                   default=str(Path(os.environ.get("TEMP") or ".") / "ecom-image-out"),
                   help="图片输出目录（**必须在 Skill 包外**）")
    p.add_argument("--state", help="断点文件路径，默认 <outdir>/%s" % STATE_NAME)
    p.add_argument("--budget", type=float, help="成本上限（点）：超了直接停，不提交")
    p.add_argument("--yes", action="store_true", help="确认真的花钱（不加就只报价）")
    p.add_argument("--snap", action="store_true",
                   help="出图后按比例精确裁剪（上游按 32 对齐，3:4 实得 864x1184，偏差 2.70%%）")
    p.add_argument("--snap-on-design", action="store_true",
                   help="按平台设计比例裁（默认 --snap 时即按设计比例裁）")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   help="比例容差，默认 %.3f（实测最大偏差 2.70 个百分点）" % RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT,
                   help="单张轮询超时秒数，默认 %g" % POLL_TIMEOUT_DEFAULT)
    p.add_argument("--poll-interval", type=float, default=a7w.POLL_INTERVAL,
                   help="轮询间隔秒数，默认 %g" % a7w.POLL_INTERVAL)
    p.add_argument("--max-seconds", type=float, help="整批最长耗时（秒），到点中断可续跑")
    p.add_argument("--force", action="store_true", help="忽略断点，全部重出（会重复扣费）")
    p.add_argument("--no-wait", action="store_true", help="只提交不等结果（稍后用 task 续查）")
    p.add_argument("--stop-on-error", action="store_true", help="一张失败就整体停")
    p.add_argument("--allow-prompt-hits", action="store_true",
                   help="即使文案命中闸门也出图（默认拦截）")
    p.add_argument("--allow-missing-slots", action="store_true",
                   help="主图位不齐也照出（默认拦截）")
    p.add_argument("--report", help="把本次证据（请求参数/任务原文/真实像素）写成 JSON")
    p.set_defaults(func=cmd_images)

    # --- all ---
    p = sub.add_parser("all", help="sellpoints → images 一条龙")
    _add_json(p)
    _add_product_args(p)
    p.add_argument("--plan-out", help="中间方案文件的路径（**必填**）")
    p.add_argument("--out", help="同 --plan-out（别名）")
    p.add_argument("--images-outdir", dest="outdir",
                   default=str(Path(os.environ.get("TEMP") or ".") / "ecom-image-out"),
                   help="图片输出目录（**必须在 Skill 包外**）")
    p.add_argument("--state", help="断点文件路径")
    p.add_argument("--budget", type=float, help="成本上限（点）")
    p.add_argument("--yes", action="store_true", help="确认真的花钱（不加就只报价）")
    p.add_argument("--snap", action="store_true", help="出图后按比例精确裁剪")
    p.add_argument("--snap-on-design", action="store_true", help="按平台设计比例裁")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT)
    p.add_argument("--poll-interval", type=float, default=a7w.POLL_INTERVAL)
    p.add_argument("--max-seconds", type=float)
    p.add_argument("--count", type=int)
    p.add_argument("--slot", action="append", choices=SLOT_KEYS)
    p.add_argument("--image-model", default="nano-banana")
    p.add_argument("--model-image", dest="model_image_override")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--stop-on-error", action="store_true")
    p.add_argument("--allow-prompt-hits", action="store_true")
    p.add_argument("--allow-missing-slots", action="store_true")
    p.add_argument("--report")
    p.add_argument("--dry-run", action="store_true", help="只打印提示词，不调模型、不花钱")
    p.set_defaults(func=cmd_all)
    return ap


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与同族一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout
    _JSON["want"] = "--json" in argv_eff
    _JSON["emitted"] = False
    _JSON["reason"] = None
    try:
        return _main(argv_eff)
    except Exception as exc:                      # noqa: BLE001 —— 故意的：契约要求给信封
        if not _JSON["want"]:
            raise
        traceback.print_exc()                     # 完整栈 → stderr（不吞、不截断）
        _json_internal(exc)
        return 1


def _main(argv_eff):
    ap = build_parser()
    try:
        a = ap.parse_args(argv_eff)
    except SystemExit as exc:
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    kind, msg = None, None
    # ⚠️ `a.func(a)` 必须在 sys.stdout 已经是**真 stdout** 的状态下调用，
    # 否则 cmd_images / cmd_all 里那套「临时把 sys.stdout 换成 stderr」会互相踩：
    # 第一处换成 stderr 后，第二次进来时 `out_raw = sys.stdout` 记下的已经是 stderr，
    # `finally` 又把它（错的那份）恢复回去 → 之后所有 print 都进了 stdout。
    # 实测踩到：「拿着目录当 --plan」这种输入错，stdout 里吐的是一行中文错误而不是
    # JSON 信封，`json.loads` 直接炸，**也不满足「stdout 只有一个 JSON」这条契约**。
    try:
        rc = a.func(a)
    except a7w.A7wError as exc:
        sys.stdout = _JSON["stdout"] or sys.stdout   # 出口前先修好 stdout
        sys.stderr.write("\n错误：%s\n" % exc)
        rc, kind, msg = 2, "call", str(exc)
    except KeyboardInterrupt:
        sys.stdout = _JSON["stdout"] or sys.stdout
        sys.stderr.write("\n已中断（已提交的任务记在断点文件里，重跑可续查）\n")
        rc, kind, msg = 130, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        _json_fail(rc, reason.get("kind") or kind,
                   reason.get("message") or msg, reason.get("detail"), a)
    return rc


if __name__ == "__main__":
    sys.exit(main())
