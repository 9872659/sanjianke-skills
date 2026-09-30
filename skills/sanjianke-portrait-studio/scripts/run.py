#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 头像写真工坊（sanjianke-portrait-studio）。

给一张人像照（或一段人设描述）+ 一个风格包，批量产出**成套的头像与写真**：
头像 1:1、社交封面 3:4、横版 16:9，可按「风格包 × 比例 × 变体」展开成矩阵。

子命令
    styles  列出内置风格包（**零网络、零成本**）
    plan    出拍摄方案（**零网络、零成本**，本地确定性矩阵展开）
    gen     批量出图（真花钱，跑之前先报价并要求 --yes）
    cost    只算钱不出图
    models  列出在架应用与模型
    verify  复核已有图片的比例真伪（拿回真实像素，跑比例闸门）

六条硬约束（都不是「警告」，是拦截，退出码非 0）
    1. 比例真伪：读**真实像素**再算比例，不信接口自报字段；容差内也打印偏差；
       `--snap` 本地裁准（上游按 32 对齐，3:4 与 16:9 天然给不出精确比例）
    2. 人物合规：公众人物 / 政治人物 / 明星的**姓名或特征词**命中即拦；
       未成年人相关内容**一律不做**（本包不出未成年写真）
    3. 恶俗 / 违背物理：低俗、暴力违禁、解剖与物理不可能的表述命中即拦
    4. 成本上限：超 --budget 直接停，不提交任何任务
    5. prompt_echo：出图提示词与提示词里的示例「去标点后相等」、二元组 Jaccard ≥ 0.75、
       或示例二元组覆盖度 ≥ 0.60 即拦
    6. --outdir 指到 Skill 包内 → 退出码 2（包内不许有任何图片）

零第三方依赖：只用标准库。图片裁剪（--snap）优先用 PIL，没有 PIL 时回落到内置的
8 位 PNG 裁剪器（只用 zlib + struct），两条路都走不通时**如实报告「没能裁」**，不假装成功。
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

try:                                    # Windows 控制台默认不是 UTF-8，先掰正，避免中文乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:                       # 老版本 Python 没有 reconfigure，忽略即可
    pass

STATE_NAME = "portrait-studio-state.json"

# ---------------------------------------------------------------------------
# nano_banana 出图应用相关（本包业务，**放这里而不是 a7w.py**）
#
# 【约定】`scripts/a7w.py` 是所有 Skill 包共用的零依赖客户端，靠
# 「包内副本 SHA256 == 规范版」批量校验各包有没有被改坏。
# 所以**任何包都不许为了自己的业务往 a7w.py 里加东西**：
#   · 需要读图片像素     → 独立模块 `imgprobe.py`
#   · 需要应用专属的接口 → 就写在下面这一段里
# ---------------------------------------------------------------------------

APP_IMAGE = "nano_banana"                     # 出图应用编码
API_SUBMIT = "submit"                         # POST /api/v1/apps/nano_banana/submit
API_QUERY = "query"                           # POST /api/v1/apps/nano_banana/query（备用）
TASK_URL = a7w.HOST + "/api/v1/tasks/{}"      # GET  /api/v1/tasks/<task_id>（统一任务查询，实际用它）

# 参数可选值。用 `python scripts/a7w.py schema nano_banana` 可现查核对（写代码前先跑这个，别猜）。
RESOLUTIONS = ("1K", "2K", "4K")
ASPECT_RATIOS = ("auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
                 "5:4", "4:5", "21:9")
ACTIONS = ("generate", "edit")
IMAGE_MODELS = ("nano-banana", "nano-banana-2", "nano-banana-2-lite",
                "nano-banana-pro", "nano-banana:official",
                "nano-banana-2-lite:official", "nano-banana-2:official",
                "nano-banana-pro:official")
DEFAULT_IMAGE_MODEL = "nano-banana"

# 单张轮询上限（秒）。**本包自己的口径，不改 a7w.py 里那个 1800**——
# 那里是给视频任务调的；出图实测 5~60 秒完成，600 秒足够且能更快暴露卡死。
POLL_TIMEOUT_DEFAULT = 600

# 实测单价：nano_banana 1K 出图 24 点/张（= 0.24 元，1 元 = 100 点）。
# 只有 1K 是我们真金白银打出来的数，2K/4K 没实测过，所以不给默认价——
# 想估算 2K/4K 必须自己传 --points-per-image，宁可拒绝估算也不编一个数。
POINTS_PER_IMAGE_1K = 24
POINTS_PER_YUAN = 100
UNTESTED_RESOLUTIONS = ("2K", "4K")

OUT_EXT = ".png"

# ---------------------------------------------------------------------------
# 风格包（styles）
#
# 为什么内置而不是让模型现编：出「成套」头像写真时，最怕的是 5 张图来自 5 个世界。
# 风格包把「光线方向、背景材质、服装质地、后期调性」四件事钉死，
# 于是同一套里的每张图共享同一套视觉语汇，拼在一起才像一组作品。
#
# 字段全部是**可直接入提示词的中文短语**，不含任何违禁词与真人指代
# （prompt_gate 会在 plan 阶段对每一条合成后的提示词再扫一遍兜底）。
# ---------------------------------------------------------------------------

STYLE_PACKS = {
    "business": {
        "name": "商务精英",
        "scene": "个人 IP 主页、名片、简历、团队介绍页",
        "light": "影棚三点布光，主光在四十五度侧前方，辅光提亮暗部，背景留一道轮廓光，面部立体但反差克制",
        "bg": "深灰或藏青纯色背景，干净无杂物，与服装拉开层次",
        "wardrobe": "合身深色西装外套配浅色衬衫，面料哑光、无图案无标识",
        "grade": "低饱和、肤色准确、质感干净的商业修图调性",
        "tail": "构图端正，眼神看向镜头，神态自信克制，无文字、无水印、无标识",
    },
    "literary": {
        "name": "文艺清新",
        "scene": "生活方式账号、书评影评、独立创作者主页",
        "light": "窗边自然散射光，光从侧后方来，面部保留柔和过渡，不压暗",
        "bg": "米白墙面配一株绿植与木质家具，背景轻微虚化，环境有生活气息",
        "wardrobe": "亚麻或纯棉浅色上衣，质地柔软、无图案",
        "grade": "暖调低对比，轻微胶片颗粒，肤色通透",
        "tail": "姿态松弛，视线可以略偏镜头，无文字、无水印、无标识",
    },
    "studiobw": {
        "name": "黑白棚拍",
        "scene": "设计师、摄影师、品牌主理人的高级感形象",
        "light": "单灯硬光加柔光罩，明暗交界清楚，暗部保留细节不糊死",
        "bg": "纯黑或中灰无缝背景纸，无接缝可见",
        "wardrobe": "黑色高领或简洁白衬衫，去掉一切装饰与配饰",
        "grade": "纯黑白摄影质感，层次细腻、颗粒均匀",
        "tail": "表情平静，构图中留出大面积负空间，无文字、无水印、无标识",
    },
    "neon": {
        "name": "赛博霓虹",
        "scene": "科技类账号、游戏与音乐人主页、潮流品牌形象",
        "light": "青蓝与品红双色霓虹侧逆光，面部一侧有清晰的高光边缘",
        "bg": "夜晚城市街景或金属墙面，背景灯光虚化成光斑",
        "wardrobe": "修身深色机能外套，哑光面料",
        "grade": "高对比冷调，青蓝与品红对撞，画面干净不脏",
        "tail": "神态冷静，构图略带电影感，无文字、无水印、无标识",
    },
    "film": {
        "name": "复古胶片",
        "scene": "怀旧叙事内容、播客封面、独立杂志与访谈栏目",
        "light": "午后侧逆光带光斑，允许轻微眩光",
        "bg": "老式室内或街角，木质与砖墙质感，背景虚化",
        "wardrobe": "复古针织或卡其外套，颜色偏暖旧",
        "grade": "经典胶片色调，暖黄高光配偏青阴影，颗粒与轻微暗角",
        "tail": "神情自然，像被随手拍到的一瞬间，无文字、无水印、无标识",
    },
    "guofeng": {
        "name": "国风雅致",
        "scene": "传统文化内容、茶与香道、文博与文旅账号",
        "light": "柔和侧光结合窗格投影，光影有层次、不过曝",
        "bg": "素色墙面配竹帘或屏风，陈设克制",
        "wardrobe": "立领中式上衣，素色棉麻或丝绸，纹样淡雅",
        "grade": "低饱和青绿与米色调，质感温润",
        "tail": "姿态端方，视线平视或略低，无文字、无水印、无标识",
    },
}

# 姿态变体：同一风格包同一比例出多张时，靠它避免「同一张图刷 N 遍」
POSES = (
    "正面平视构图，肩线水平，双手收在画面下缘之外",
    "四分之三侧身，面部转向镜头，下颌微收，肩线略斜",
    "微微侧脸平视，一侧肩膀靠近镜头，营造纵深与层次",
    "身体正对镜头，头部轻微侧转，视线越过镜头一点，神态松弛",
)

# ---------------------------------------------------------------------------
# 比例预设（preset）
#
# 三个比例就是本包的全部交付形态：头像 1:1、社交封面 3:4、横版 16:9。
# gen_ratio 是**发给上游的 aspect_ratio**，design_ratio 是**交付口径**。
# 两者在本包里恰好相同，但字段分开留着：将来某个平台要求 2.35:1 这类
# 上游给不出的比例时，只需要改 design_ratio 并让 --snap 裁准，不用改逻辑。
# ---------------------------------------------------------------------------

PRESETS = {
    "avatar": {
        "name": "头像 1:1",
        "design_ratio": "1:1",
        "gen_ratio": "1:1",
        "pixel_hint": "1024x1024",
        "frame": "胸部以上近景，头顶留出约百分之八的余量，人物居中",
        "use_for": "站内头像、社群形象、企业通讯录。多数平台对头像做圆形或圆角裁切，"
                   "脸部不要贴边，左右各留约百分之十的安全区。",
    },
    "cover34": {
        "name": "社交封面 3:4",
        "design_ratio": "3:4",
        "gen_ratio": "3:4",
        "pixel_hint": "1080x1440",
        "frame": "腰部以上至大腿中段构图，眼睛落在画面上方三分之一处，上下各留约百分之八安全区",
        "use_for": "竖版主页封面、笔记与图文首图。3:4 在信息流里占位较高，"
                   "主体不要压在左上角（会被平台角标盖住）。",
    },
    "wide": {
        "name": "横版 16:9",
        "design_ratio": "16:9",
        "gen_ratio": "16:9",
        "pixel_hint": "1280x720",
        "frame": "半身横构，主体略偏画面右侧，左侧留出标题压字区，人物占画面高度约七成",
        "use_for": "横版封面、团队页横幅、直播与课程头图。左侧压字区可以叠标题。",
    },
}

# 上游 1K 档实际能给的像素（**本包真机实测，三个预设全覆盖**）。
# 留作文档与排错依据：3:4 与 16:9 天然拿不到精确比例，这决定了容差怎么定、
# 以及为什么需要 --snap。实测原始记录见 --report 产出的证据 JSON。
MEASURED_1K_PIXELS = {
    "1:1": [1024, 1024],
    "3:4": [864, 1184],
    "16:9": [1344, 768],
}

DEFAULT_SUBJECT = ("一位成年人物（二十五至四十岁），东亚面孔，五官自然、"
                   "肤色真实、发质健康")

# ---------------------------------------------------------------------------
# nano_banana 接口封装
#
# 为什么要单独这一段：这些是**出图应用专属**的东西，而 `a7w.py` 是几十个包
# 共用的客户端（靠 SHA256 校验一致性），不许往里加业务代码。
# 通用能力（_request / _unwrap / load_key / save / A7wError / HOST）继续用 a7w 的。
#
# ⚠️ 平台文档写的是 `data.result.status`，**实测不对**：`status` 在 `data` 顶层。
# 照文档写会永远读不到状态、一路轮询到超时（这是别人踩过的坑，本包按实测结构取）。
# ⚠️ **`code == 1` 才是成功，不是 0**；HTTP 200 也不等于业务成功。
# ---------------------------------------------------------------------------


def submit_image(prompt, aspect_ratio="1:1", resolution="1K",
                 model=DEFAULT_IMAGE_MODEL, action="generate", image_urls=None,
                 callback_url=None, key=None, timeout=180):
    """提交一个出图任务，返回网关 data（含 task_id 与预冻结点数）。

    请求体字段用 `python scripts/a7w.py schema nano_banana` 实查过，不要凭记忆加字段：
        prompt / action / model / image_urls / resolution / aspect_ratio / callback_url
    """
    if action not in ACTIONS:
        raise a7w.A7wError("action 只能是 %s，收到 %r" % (" / ".join(ACTIONS), action))
    if resolution not in RESOLUTIONS:
        raise a7w.A7wError("resolution 只能是 %s，收到 %r" % (" / ".join(RESOLUTIONS), resolution))
    if aspect_ratio not in ASPECT_RATIOS:
        raise a7w.A7wError("aspect_ratio 只能是 %s，收到 %r" % (" / ".join(ASPECT_RATIOS), aspect_ratio))
    if action == "edit" and not image_urls:
        raise a7w.A7wError("action=edit 时必须提供 image_urls（即 --photo-url）")
    body = {"prompt": prompt, "action": action, "model": model,
            "resolution": resolution, "aspect_ratio": aspect_ratio}
    if image_urls:
        body["image_urls"] = list(image_urls)
    if callback_url:
        body["callback_url"] = callback_url
    url = "%s/api/v1/apps/%s/%s" % (a7w.HOST, APP_IMAGE, API_SUBMIT)
    return a7w._unwrap(a7w._request("POST", url, a7w.load_key(key), body=body, timeout=timeout))


def task_state(task_id, key=None):
    """查一次任务，返回 (状态, 归一化 data, 原始信封)。

    ⚠️ `status` 在 `data` 顶层（实测），不在 `data.result` 里。
    """
    payload = a7w._request("GET", TASK_URL.format(task_id), a7w.load_key(key))
    data = a7w._unwrap(payload) or {}
    return data.get("status"), data, payload


def poll_task(task_id, key=None, timeout=POLL_TIMEOUT_DEFAULT,
              interval=a7w.POLL_INTERVAL, on_tick=None):
    """轮询任务到终态。

    **必须有超时上限**：出图会卡在 processing，无限等会把整批挂死。
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
# 同一个错误在出图场景的形态是：接口自报 `aspect_ratio=3:4`，
# 但真实像素是 1024x1024。只信自报值 → 用户拿去排版才发现全错了。
#
# 所以这里**只认文件头里的宽高**。
#
# ⚠️ 实测到的上游特性（必须写进文档，否则闸门天天误报）：
#   上游不是按比例给像素，而是先定总像素、再把每边向下对齐到 32 的倍数。
#   所以 10 种比例里有 5 种给不出像素级精确比例，本包用到的三种里占两种：
#       请求 3:4  → 864x1184   = 0.7297（3:4 = 0.75）   偏差 2.70%
#       请求 16:9 → 1344x768   = 1.7500（16:9 = 1.7778）偏差 1.56%
#       请求 1:1  → 1024x1024  = 1.0000                 偏差 0%
#   这**不是**网关 bug，是扩散模型按 32 对齐的常规做法。但它意味着
#   「请求比例 == 产出比例」这个断言对三分之二的比例天然不成立。
#
# 处理方式（三条一起用，缺一条闸门就会变成天天误报的噪音）：
#   a) 默认容差 3%：容差内不算「假」，但会**明确打印真实像素与偏差**，不藏
#   b) 超过容差 → 标红 + 计入闸门失败 + 退出码 3
#   c) `--snap`：出图后按请求比例精确裁掉多余像素，让产出真的等于请求比例；
#      裁剪结果再次读文件头复核，裁成功才记 exact
# ---------------------------------------------------------------------------

RATIO_TOLERANCE = 0.03        # 默认 3%（实测最大偏差 2.70%，留一点余量）

# 容差地板：**像素只能是整数**，所以「裁到精确比例」本身就有量化误差。
# 实测（--snap 之后复核）：3:4 裁到 864x1152 → 0.75 精确；16:9 裁到 1344x756 → 0.75…，
# 相邻整数像素间隔约 0.1%。所以用户把 --ratio-tolerance 调到比这还小时，
# 会把「本来就必须存在」的舍入误差判成不合格。0.0025 是保守地板，仍能抓住真错：
# 请求 3:4 却给 1:1 的偏差是 33%，比地板大 130 倍。
RATIO_TOLERANCE_FLOOR = 0.0025

# 提示词里出现过的示例文本。**新增示例必须登记到这里。**
# 这些是「跨主题」的假例子（音箱、图标），与真实人像业务明显不搭，
# 正常不该出现在真实产出里——真实人像提示词与它们的相似度都远低于 0.1。
PROMPT_SAMPLES = [
    "一只黄色香蕉形状的蓝牙音箱，纯白背景，柔光棚拍，主体居中",
    "a yellow banana-shaped bluetooth speaker on a pure white background, soft studio light",
    "橙色渐变背景上一个白色圆形图标，极简扁平插画风，无文字",
]

# 比例换算（parse_ratio / ratio_label / image_size）都在 `imgprobe.py`：
# 那是本包自己的图片探针模块，a7w.py 保持逐字节等于规范版。
parse_ratio = imgprobe.parse_ratio
ratio_label = imgprobe.ratio_label


def check_ratio(path, want_ratio, tolerance=None):
    """闸门一：读真实像素，判是否等于请求比例。

    返回 dict（`ok` 为闸门结论）：
        real_px / real_label / real_ratio / want_ratio / deviation / ok / why
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
# 为什么值得做：上游按 32 对齐，3:4 实测给 864x1184（偏差 2.70%）。
# 自媒体平台对封面比例是有像素级要求的，3:4 上差 2.70% 就是 32 像素，
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
# 闸门三：恶俗 / 违背物理（低俗、暴力违禁、解剖与物理不可能）
#
# 为什么单列一条而不是并进广告法词表：这两类命中的**性质不同**。
# 广告法违禁词是「文案不能这么说」，恶俗与违背物理是「这张图不该被生成」——
# 前者会让物料被投诉，后者会让账号被处置。分级处理，但都是硬拦。
#
# ⚠️ 这是**启发式自检**，不是内容安全网关。它抓的是「使用者自己把违规要求写进了提示词」
# 这一种最可控的情形；真实风险面远比正则表大，见 SKILL.md 免责声明。
# ---------------------------------------------------------------------------

VULGAR_PATTERNS = [
    (r"色情|情色|裸露|半裸|全裸|裸体|露点|走光|情趣(内衣|装)|内衣写真|泳装湿身|湿身|"
     r"艳照|挑逗|撩人|擦边球|擦边|大尺度|比基尼写真|制服诱惑", "恶俗/低俗内容"),
    (r"血腥|暴力|尸体|自杀|自残|枪械|枪支|弹药|毒品|违禁品|管制刀具|恐怖袭击", "暴力/违禁内容"),
    (r"(三|四|五|六|七|八)只(手|胳膊|手臂|腿|眼睛)|双头|两张脸|多张脸|多头|多臂|多指|六指|"
     r"断肢|断头|穿模|身体(穿|融)过|关节反向|反关节|脖子?旋转\s*360|不可能(的)?(姿态|解剖)|"
     r"畸形(肢体|手指)", "违背物理/解剖"),
    (r"水往高处流|反重力|影子(方向|朝向)不一致|无视透视|透视错误", "违背物理"),
]
VULGAR_RE = [(re.compile(p), why) for p, why in VULGAR_PATTERNS]

# 广告法 / 平台高压线（与配图工厂同口径，出图提示词同样适用）
BANNED_PATTERNS = [
    (r"国家级|世界级|最高级|最佳|最优|最强|第一品牌|全国第一|排名第一|销量第一", "高",
     "广告法第九条绝对化用语，出图文字与提示词都不许带"),
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


def compliance_scan(text):
    """扫广告法违禁词，返回命中列表。"""
    hits = []
    for rx, lvl, why in BANNED_RE:
        m = rx.search(text or "")
        if m:
            hits.append({"word": m.group(0), "level": lvl, "why": why})
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits


def vulgar_scan(text):
    """扫恶俗 / 违背物理表述，返回命中列表。"""
    hits = []
    for rx, why in VULGAR_RE:
        m = rx.search(text or "")
        if m:
            hits.append({"word": m.group(0), "why": why})
    return hits


# ---------------------------------------------------------------------------
# 闸门二：人物合规（本包特有）
#
# 头像写真这个场景的特殊风险只有一个，但很硬：**别人的脸**。
#   · 拿公众人物 / 政治人物 / 明星的脸做头像与写真，涉及肖像权，且平台处置很重
#   · 未成年人写真，本包**一律不做**（不做未成年写真类生成），命中即拦、不留后门
#
# 【刻意的取舍，必须如实说明】
# 本包**不内嵌任何在世真实个体的姓名**。把真人姓名写进一个公开分发的包里，
# 本身就是隐私风险，也会让名单迅速过期。所以姓名拦截走三条路：
#   A. 类别词与称谓词（明确特征词）：明星 / 总统 / 主席 / 领导人 / 议员 …
#   B. 指代结构：X的脸 / 像 X 那样 / X 同款脸 / 撞脸 / 换脸 / 面部替换 …
#   C. **外挂名单** `--person-blocklist <文件>`：一行一个名字，命中即拦。
#     需要按具体姓名拦截时用这一条（也可直接加进计划里的提示词再过一遍闸门）。
# 这一点在 SKILL.md 与交付报告里都写明了，不含糊。
# ---------------------------------------------------------------------------

# A. 政治人物：职衔与称谓（特征词）
POLITICAL_TERMS = [
    r"主席", r"总统(?!套房)", r"总理", r"首相", r"总书记", r"国家元首",
    r"国家领导人", r"领导人", r"政治局", r"国务委员", r"中央委员",
    r"人大代表", r"政协委员", r"部长", r"副部长", r"省长", r"副省长",
    r"市长", r"副市长", r"州长", r"县长", r"区长", r"议员", r"参议员",
    r"众议员", r"州议员", r"大使", r"教皇", r"国王", r"女王", r"亲王",
    r"王储", r"第一夫人", r"政要", r"政治人物", r"政界人物", r"政客",
    r"president", r"prime\s+minister",
    r"premier", r"politician", r"senator", r"governor", r"monarch",
]

# A. 公众人物 / 明星：类别特征词
CELEB_TERMS = [
    r"明星", r"名人", r"公众人物", r"知名人士", r"知名人物", r"社会名流", r"艺人",
    r"演员", r"女演员", r"歌手", r"影帝", r"影后", r"视帝", r"视后",
    r"球星", r"球员", r"运动员", r"网红", r"大V", r"大v", r"主播",
    r"博主", r"爱豆", r"偶像(?!剧)", r"idol", r"celebrity", r"public\s+figure",
    r"famous\s+person", r"superstar", r"influencer", r"singer", r"actress",
]

# B. 指代结构：不点名也能识别「照着某个具体真人做」
IDENTITY_PATTERNS = [
    (r"(像|模仿|复刻|还原|神似|酷似|照着|参考)\s*[\u4e00-\u9fff]{2,4}"
     r"(的脸|脸型|脸庞|长相|样子|形象|造型|神态)", "把某个具体真人的脸当成了参照对象"),
    (r"[\u4e00-\u9fff]{2,4}(同款脸|同款长相|撞脸)", "同款脸/撞脸＝指向某个具体真人"),
    (r"(明星|名人|政要|领导人|艺人|网红|公众人物|真人)的(脸|长相|肖像|形象|造型)",
     "明星/名人的脸或形象"),
    (r"(换脸|AI换脸|ai换脸|人脸替换|人脸融合|人脸克隆|脸部替换|面部替换|五官替换|"
     r"deepfake|deep\s*fake|faceswap|face\s*swap)", "换脸/人脸替换"),
    (r"(领导人|政要|官员)(形象|头像|写真|照片|肖像)", "领导人的形象/头像"),
    (r"[\u4e00-\u9fff]{2,4}(主席|总统(?!套房)|总理|首相|总书记)", "「姓名＋职衔」形式的指名道姓"),
]
IDENTITY_RE = [(re.compile(p), why) for p, why in IDENTITY_PATTERNS]

# B. 未成年人：本包一律不做，命中即拦（刻意偏严，宁可误伤）
MINOR_PATTERNS = [
    (r"未成年|儿童|孩童|幼儿|幼童|宝宝|婴儿|婴孩|小孩|小孩子|孩子|小朋友|少儿|"
     r"少男|少女|少年|青少年|学龄前|幼儿园|小学生|中学生|初中生|高中生|"
     r"校服|校园风|童装|童星|萌娃|萝莉|正太|亲子照|母子|母女|父子|父女|"
     r"男童|女童|襁褓|child|children|kid|teen|teenager|schoolboy|schoolgirl",
     "未成年人相关内容（本包不做未成年写真类生成）"),
]
MINOR_RE = [(re.compile(p), why) for p, why in MINOR_PATTERNS]

# 年龄声明：**任何小于 18 的年龄数字**都按未成年处理（「12 岁」「15周岁」「16 years old」）
MINOR_AGE_RE = re.compile(r"(\d{1,3})\s*(?:周\s*岁|岁|years?\s*old)", re.IGNORECASE)
ADULT_AGE = 18


def minor_scan(text):
    """扫未成年人相关内容，返回命中列表。年龄数字 < 18 也算。"""
    hits = []
    for rx, why in MINOR_RE:
        m = rx.search(text or "")
        if m:
            hits.append({"word": m.group(0), "why": why})
    for m in MINOR_AGE_RE.finditer(text or ""):
        try:
            age = int(m.group(1))
        except ValueError:
            continue
        if 0 < age < ADULT_AGE:
            hits.append({"word": m.group(0),
                         "why": "年龄声明 %d 岁 < %d，按未成年人处理" % (age, ADULT_AGE)})
    return hits


def person_scan(text, blocklist=None):
    """闸门二：扫公众人物 / 政治人物 / 明星 / 未成年人，返回命中列表。"""
    hits = []
    for pat in POLITICAL_TERMS:
        m = re.search(pat, text or "", re.IGNORECASE)
        if m:
            hits.append({"kind": "political", "word": m.group(0),
                         "why": "政治人物特征词「%s」：不做任何政治人物的形象生成"
                                % m.group(0)})
    for pat in CELEB_TERMS:
        m = re.search(pat, text or "", re.IGNORECASE)
        if m:
            hits.append({"kind": "celebrity", "word": m.group(0),
                         "why": "公众人物/明星特征词「%s」：涉及肖像权，不做"
                                % m.group(0)})
    for rx, why in IDENTITY_RE:
        m = rx.search(text or "")
        if m:
            hits.append({"kind": "identity", "word": m.group(0), "why": why})
    for name in (blocklist or []):
        n = (name or "").strip()
        if n and n in (text or ""):
            hits.append({"kind": "blocklist", "word": n,
                         "why": "命中外挂人物名单（--person-blocklist）"})
    hits.extend(minor_scan(text))
    for h in hits:
        h.setdefault("kind", "minor")
    return hits


def load_person_blocklist(path):
    """读外挂人物名单：一行一个名字，`#` 开头跳过。"""
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        raise a7w.A7wError("找不到外挂人物名单文件：%s" % path)
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


# ---------------------------------------------------------------------------
# 闸门五：prompt_echo（照抄提示词示例）
#
# 事故复盘（来自标题工坊的实测）：提示词里写过的示例，
# 哪怕明确标着「这是错的写法」，模型照样照抄——公众号那一轮最高分 89.0 的标题
# **一字不差就是提示词里的示例**。最高分变成「抄标准答案」，排序就废了。
#
# 出图场景下这条更隐蔽：你不会一眼看出这张图和测试用例长得一样，
# 而是「看起来挺正常」，直到发现整套写真其实是同一个模子。
# 本包的方案由本地矩阵生成、不经过大模型，所以照抄风险主要来自
# **手改 plan.json** 或 **直接喂 --prompt** —— 闸门照样跑在前头。
#
# 判定：去标点后相等 → 命中；字符二元组 Jaccard ≥ 0.75 → 命中；
#       示例的二元组覆盖度 ≥ ECHO_CONTAIN → 命中（第三条，见下）。
# 阈值标定依据：标题工坊实测 196 条正常产出与跨主题示例的最高相似度只有 0.174，
# 而「少两个字的同构照抄」是 0.765。0.75 既能兜住轻改写，离正常上限还有 4 倍余量。
# 这里额外加一条**相对**长度守卫：目标归一化长度 < max(ECHO_MIN_LEN_FLOOR, len(示例)//2)
# 就不比相似度与覆盖度，因为短串的二元组集合太小、指标会虚高。
#
# 【为什么还要第三条】真人写真提示词动辄 60~150 字，示例只有 25 字，Jaccard 的分母是
# 两份二元组的**并集**，示例那一侧被长提示词摊薄得极狠 —— 示例原样塞进去也照样放行。
# 本包 PROMPT_SAMPLES 与 `sanjianke-image-factory` 逐字相同，所以那边实测的窗口原样适用：
#   · 示例原样嵌入 + 补 9 个字（34 字）→ Jaccard 24/33 = 0.727（旧判据放行 ❌）
#                                        覆盖度 24/24 = 1.000（新判据拦下 ✓）
#   · 示例原样嵌进一条 102 字的六段结构提示词 → Jaccard 0.245（漏）、覆盖度 1.000（抓住）
# 覆盖度只看"示例被抄了多少"，不看提示词有多长，摊薄对它无效。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6


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


def prompt_gate(prompt, blocklist=None):
    """对一个出图提示词跑**全部本地内容闸门**，返回命中列表 [(kind, why), …]。

    顺序刻意如此：人物合规（本包特有、后果最重）→ 恶俗/违背物理 → 广告法 → 照抄。
    """
    leaks = []
    for h in person_scan(prompt, blocklist):
        leaks.append((h.get("kind") or "person", h["why"]))
    for h in vulgar_scan(prompt):
        leaks.append(("vulgar", "命中「%s」（%s）" % (h["word"], h["why"])))
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
    rec["notes"].append("提交时会先冻结（实测 frozen_points 高于实扣，如 31.2 vs 24），"
                        "完成后按实测价结算，失败全额退回；只信 usage.points_cost")
    return rec


def fmt_cost(rec):
    if rec.get("total_points") is None:
        return "无法估算（%s）" % "；".join(rec.get("notes") or [])
    return "%d 张 × %g 点 = %g 点 = %.2f 元" % (
        rec["count"], rec["points_per_image"], rec["total_points"], rec["total_yuan"])


# ---------------------------------------------------------------------------
# 拍摄方案（plan）—— 本地确定性矩阵展开
#
# 为什么不调用大模型：本包的方案是**矩阵式**的（风格包 × 比例 × 变体），
# 每一格的机位/光线/背景/服装/姿态/后期都由风格包与预设决定，语义上不需要模型补全。
# 走本地意味着 plan 与 styles 一样**零网络、零成本、可复现**，
# 于是「真花钱」的操作只剩 gen 一个，成本前置反而更干净。
#
# 【铁律】方案里的提示词**不许出现任何一条可直接复制的示例**；
# PROMPT_SAMPLES 登记的是跨主题的假例子（音箱/图标），与真实人像业务明显不搭。
# ---------------------------------------------------------------------------

def compose_prompt(subject, style, preset, variant):
    """把「人设 + 风格包 + 比例预设 + 姿态变体」拼成一条出图提示词。"""
    pose = POSES[variant % len(POSES)]
    return ("%s，%s。光线：%s；背景：%s；着装：%s；后期：%s；姿态：%s。%s"
            % (subject, preset["frame"], style["light"], style["bg"],
               style["wardrobe"], style["grade"], pose, style["tail"]))


def build_items(style_keys, preset_keys, variants, subject, blocklist=None):
    """展开成拍摄方案条目列表（确定性，同一入参永远同一结果）。"""
    items = []
    n = 0
    for sk in style_keys:
        st = STYLE_PACKS[sk]
        for pk in preset_keys:
            ps = PRESETS[pk]
            for v in range(max(1, int(variants))):
                n += 1
                prompt = compose_prompt(subject, st, ps, v)
                items.append({
                    "id": n,
                    "style": sk, "style_name": st["name"], "style_scene": st["scene"],
                    "preset": pk, "preset_name": ps["name"], "variant": v + 1,
                    "aspect_ratio": ps["gen_ratio"],
                    "design_ratio": ps["design_ratio"],
                    "pixel_hint": ps["pixel_hint"],
                    "resolution": "1K", "model": DEFAULT_IMAGE_MODEL,
                    "prompt": prompt,
                    "shot": {"机位": ps["frame"], "光线": st["light"], "背景": st["bg"],
                             "服装": st["wardrobe"], "姿态": POSES[v % len(POSES)],
                             "后期": st["grade"]},
                    "use_for": ps["use_for"],
                    "alt": "%s-%s-%d" % (ps["name"], st["name"], v + 1),
                    "leaks": prompt_gate(prompt, blocklist),
                })
    return items


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
#   · key = 提示词 + 生成比例 + 分辨率 + 模型 + action + 参考图的哈希，改了就是新的一项
# ---------------------------------------------------------------------------

def state_key(item):
    payload = "|".join([item["prompt"], item["aspect_ratio"], item["resolution"],
                        item.get("model") or DEFAULT_IMAGE_MODEL,
                        item.get("action") or "generate",
                        ",".join(item.get("image_urls") or [])])
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


def _pick(keys, table, what, default=None):
    out = []
    for k in (keys if keys else ([] if default is None else [default])):
        k = str(k).strip()
        if k not in table:
            raise a7w.A7wError("未知%s %r；可选：%s" % (what, k, " / ".join(table)))
        if k not in out:
            out.append(k)
    if not out:
        raise a7w.A7wError("至少要指定一个%s；可选：%s" % (what, " / ".join(table)))
    return out


def cmd_styles(a):
    """列出内置风格包——零网络、零成本。"""
    out = []
    for k, st in STYLE_PACKS.items():
        out.append({"style": k, "name": st["name"], "scene": st["scene"],
                    "light": st["light"], "bg": st["bg"], "wardrobe": st["wardrobe"],
                    "grade": st["grade"], "tail": st["tail"]})
    if a.json:
        _json_out({"styles": out, "presets": PRESETS, "poses": list(POSES),
                   "measured_1k_pixels": MEASURED_1K_PIXELS}, a, indent=1)
        return 0
    print("内置风格包 %d 个（零网络、零成本，直接可用来出方案）：\n" % len(out))
    for x in out:
        print("  %-10s %-8s  %s" % (x["style"], x["name"], x["scene"]))
        print("      光线：%s" % x["light"])
        print("      背景：%s" % x["bg"])
        print("      着装：%s" % x["wardrobe"])
        print("      后期：%s" % x["grade"])
        print()
    print("比例预设 %d 个（上游 1K 实测像素见下——3:4 与 16:9 天然不是精确比例）：" % len(PRESETS))
    for k, ps in PRESETS.items():
        px = MEASURED_1K_PIXELS.get(ps["gen_ratio"])
        hint = "%dx%d" % (px[0], px[1]) if px else "未实测"
        dev = ""
        if px:
            want = parse_ratio(ps["gen_ratio"])
            if want:
                dev = "（偏差 %.2f%%）" % (abs(px[0] / float(px[1]) - want) / want * 100)
        print("  %-10s %-10s 设计比例 %-6s 生成用 %-6s 排版目标 %-10s 上游实测 %s%s"
              % (k, ps["name"], ps["design_ratio"], ps["gen_ratio"],
                 ps["pixel_hint"], hint, dev))
        print("      用途：%s" % ps["use_for"])
    print("\n姿态变体 %d 个（--variants N 会在同一风格同一比例下轮换）：" % len(POSES))
    for i, p in enumerate(POSES, 1):
        print("  v%d  %s" % (i, p))
    print("\n下一步：python scripts/run.py plan --style business --preset avatar --preset cover34 --out plan.json")
    return 0


def create_plan(a):
    """按参数展开方案（plan 与 gen --prompt 之外的路径共用）。"""
    styles = _pick(a.style, STYLE_PACKS, "风格包", default="business")
    presets = _pick(a.preset, PRESETS, "比例预设", default=None) if a.preset \
        else list(PRESETS)
    subject = (a.subject or DEFAULT_SUBJECT).strip()
    blocklist = load_person_blocklist(getattr(a, "person_blocklist", None))
    items = build_items(styles, presets, a.variants, subject, blocklist)
    if getattr(a, "count", None):
        items = items[:a.count]
    return styles, presets, subject, items


def cmd_plan(a):
    styles, presets, subject, items = create_plan(a)
    if not items:
        raise a7w.A7wError("方案展开后是空的，检查 --style / --preset / --variants")
    plan = {"version": 1, "kind": "portrait-studio-plan",
            "subject": subject, "styles": styles, "presets": presets,
            "variants": max(1, int(a.variants)), "count": len(items),
            "items": items}
    cost = estimate_cost(len(items), "1K", a.points_per_image)
    if a.out:                       # 两种模式都要落盘：gen 要用这个文件
        Path(a.out).write_text(json.dumps(plan, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    if a.json:
        # JSON 模式只吐一个完整 JSON：把报价塞进同一个对象，
        # 不再往 stdout 追加人读的说明行，否则管道里 `json.loads` 会炸。
        plan["estimate"] = cost
        _json_out(plan, a, indent=1)
        if a.out:
            sys.stderr.write("方案已写入 %s\n" % a.out)
        return 3 if any(it["leaks"] for it in items) else 0
    _render_plan(plan)
    print("\n预估出图成本（**这一步没花任何钱**：plan 是本地展开，不联网）：")
    print("  " + fmt_cost(cost))
    if a.out:
        sys.stderr.write("方案已写入 %s\n" % a.out)
    return 3 if any(it["leaks"] for it in items) else 0


def _render_plan(plan):
    print("拍摄方案：%s" % plan["subject"])
    print("风格包：%s   比例：%s   共 %d 张   变体 %d 个/格"
          % ("、".join(STYLE_PACKS[s]["name"] for s in plan["styles"]),
             "、".join(PRESETS[p]["name"] for p in plan["presets"]),
             plan["count"], plan["variants"]))
    print()
    for it in plan["items"]:
        print("#%-3d %-10s %-10s %-6s %-5s"
              % (it["id"], it["style_name"], it["preset_name"],
                 it["aspect_ratio"], it["resolution"]))
        print("     拍摄要点：%s" % it["shot"]["机位"])
        print("     光线/背景：%s ｜ %s" % (it["shot"]["光线"], it["shot"]["背景"]))
        print("     着装/姿态：%s ｜ %s" % (it["shot"]["服装"], it["shot"]["姿态"]))
        print("     后期：%s" % it["shot"]["后期"])
        print("     出图提示词：%s" % it["prompt"])
        print("     用途：%s" % it["use_for"])
        for kind, why in it["leaks"]:
            print("     " + _red("✗ %s：%s" % (kind, why)))
    hits = [it for it in plan["items"] if it["leaks"]]
    if hits:
        sys.stderr.write("\n!! %d 条提示词命中本地闸门（人物合规 / 恶俗 / 违禁词 / 照抄 / 占位符），"
                         "改掉后再出图\n" % len(hits))


def cmd_cost(a):
    rec = estimate_cost(a.count, a.resolution, a.points_per_image)
    # 先定结论：估不出价、超预算都算「不放行」。发出的 JSON 里的 ok 必须与退出码一致。
    no_price = rec.get("total_points") is None
    over = (a.budget is not None and rec.get("total_points") is not None
            and rec["total_points"] > a.budget)
    if no_price:
        rec_rc = _fail(3, "budget", "拿不到该档的可信单价，拒绝凭猜估算")
    elif over:
        rec_rc = _fail(3, "budget", "预估成本 %g 点超过 --budget 上限 %g 点"
                       % (rec["total_points"], a.budget))
    else:
        rec_rc = 0
    if a.json:
        _json_out(rec, a, indent=1, ok=not rec_rc)
    else:
        print("预估成本：%s" % fmt_cost(rec))
        for n in rec.get("notes") or []:
            print("  · %s" % n)
        if a.budget is not None and rec.get("total_points") is not None:
            print("  · 预算 %g 点：%s" % (a.budget, "超了，gen 会被拦下" if over else "在预算内"))
    # 估不出价也是「闸门不放行」：拿不到可信单价就往流水线里放行，等于没有成本前置。
    if no_price:
        sys.stderr.write("!! 拿不到该档的可信单价，无法完成成本前置检查\n")
    return rec_rc


def cmd_models(a):
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
    print("     结算价只认任务返回的 usage.points_cost。")
    return 0


def cmd_verify(a):
    """复核已有图片的比例真伪：跑闸门一，不合格退出码 3。"""
    results = []
    bad = 0
    for f in a.files:
        if not Path(f).is_file():
            raise a7w.A7wError("找不到图片文件：%s" % f)
        rec = check_ratio(f, a.ratio, a.ratio_tolerance)
        results.append(rec)
        if not rec["ok"]:
            bad += 1
    if a.json:
        # ok 如实反映「这批图的比例是否全部合格」，退出码仍是 3
        _json_out({"ratio": a.ratio, "tolerance": results[0]["tolerance"],
                   "results": results, "failed": bad}, a, indent=1, ok=not bad)
    else:
        print("比例复核：请求 %s，容差 %.2f%%（真实像素来自文件头，不信任何自报字段）"
              % (a.ratio, results[0]["tolerance"] * 100))
        for r in results:
            flag = "合格" if r["ok"] else "不合格"
            dev = "—" if r["deviation"] is None else "%.2f%%" % (r["deviation"] * 100)
            print("  [%s] %s  真实像素 %sx%s (%s)  偏差 %s  %s"
                  % (flag, r["file"], r["real_px"][0], r["real_px"][1],
                     r["real_label"], dev, r["format"]))
            print("        %s" % r["why"])
        print("\n共 %d 张，%d 张不合格。" % (len(results), bad))
    return 3 if bad else 0


def _print_gen_plan(items, outdir, resolution, override, action):
    print("将要出图：%d 张（action=%s）" % (len(items), action))
    for it in items:
        print("  #%-3d %-10s %-10s %-6s %-5s %s" % (
            it["id"], it.get("style_name") or it.get("style") or "-",
            it.get("preset_name") or it.get("preset") or "-",
            it["aspect_ratio"], it["resolution"],
            it["prompt"][:40] + ("…" if len(it["prompt"]) > 40 else "")))
    print("  输出目录：%s  （**必须不在 Skill 包内**）" % outdir)
    u = unit_points(resolution, override)
    print("  单张成本：%s" % ("%g 点" % u if u is not None
                             else "未知（%s 档无实测价）" % resolution))


def _items_from_prompt(a):
    """`gen --prompt "…"` 的直接出图路径：单条，提示词原样使用（不被模板改写）。"""
    preset = (a.preset or ["avatar"])[0]
    if preset not in PRESETS:
        raise a7w.A7wError("未知比例预设 %r；可选：%s" % (preset, " / ".join(PRESETS)))
    ps = PRESETS[preset]
    ratio = (a.ratio or ps["gen_ratio"]).strip()
    if ratio not in ASPECT_RATIOS:
        raise a7w.A7wError("未知比例 %r；可选：%s" % (ratio, " / ".join(ASPECT_RATIOS)))
    return [{
        "id": 1, "style": (a.style or ["custom"])[0], "style_name": "自定义提示词",
        "preset": preset, "preset_name": ps["name"], "variant": 1,
        "aspect_ratio": ratio, "design_ratio": ratio,
        "resolution": (a.resolution or "1K").upper(),
        "model": a.model, "prompt": a.prompt, "shot": {}, "use_for": ps["use_for"],
        "alt": "自定义-%s" % ps["name"], "leaks": [],
    }]


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
    # ---- 载入条目 ------------------------------------------------------
    if a.prompt and a.plan:
        raise a7w.A7wError("--prompt 与 --plan 只能二选一")
    if a.prompt:
        items = _items_from_prompt(a)
    elif a.plan:
        plan_path = Path(a.plan)
        if not plan_path.is_file():
            raise a7w.A7wError("找不到方案文件：%s（先用 `plan` 生成）" % a.plan)
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # 手改坏了 / 不是本包产出的文件：这是输入错，不该崩成 exit 1 + stdout 空
            raise a7w.A7wError("方案文件读不动或不是合法 JSON：%s（%s）" % (a.plan, exc))
        items = plan.get("items") or []
        if not items:
            raise a7w.A7wError("方案文件里没有 items：%s" % a.plan)
        if a.preset:
            items = [it for it in items if it.get("preset") in a.preset]
            if not items:
                raise a7w.A7wError("按 --preset %s 过滤后没有条目" % "、".join(a.preset))
        if a.style:
            items = [it for it in items if it.get("style") in a.style]
            if not items:
                raise a7w.A7wError("按 --style %s 过滤后没有条目" % "、".join(a.style))
        if a.count:
            items = items[:a.count]
        if a.resolution:
            for it in items:
                it["resolution"] = a.resolution.upper()
        for it in items:
            it.setdefault("resolution", "1K")
            it.setdefault("model", a.model)
            it.setdefault("preset_name", it.get("preset") or "-")
            it.setdefault("style_name", it.get("style") or "-")
    else:
        raise a7w.A7wError("要么给 --plan <方案 JSON>，要么给 --prompt \"一条出图提示词\"")

    # ---- 参考图 / action ----------------------------------------------
    action = a.action or ("edit" if a.photo_url else "generate")
    if action == "edit" and not a.photo_url:
        raise a7w.A7wError(
            "action=edit 需要参考图 URL（--photo-url）。"
            "注意：上游只接受**公网可访问的 HTTP/HTTPS 图片地址**，"
            "平台没有提供本地文件上传接口，所以本地照片必须先自己放到可访问的位置。")
    if action == "generate" and a.photo_url:
        raise a7w.A7wError("给了 --photo-url 就是图生图；请同时加 --action edit（或干脆不写 action）")
    for it in items:
        it["action"] = action
        it["image_urls"] = list(a.photo_url or [])

    # ---- 闸门六（配置前置）：--outdir 不许指到包内 ----------------------
    outdir = Path(a.outdir).resolve()
    pkg_dir = Path(__file__).resolve().parent.parent
    try:
        outdir.relative_to(pkg_dir)
        raise a7w.A7wError(
            "输出目录 %s 在 Skill 包内（退出码 2）。包内不许有任何图片——"
            "上传白名单只收文本文件，图片会让上传失败。请换到包外，例如 %s"
            % (outdir, Path(os.environ.get("TEMP") or ".") / "portrait-studio-out"))
    except ValueError:
        pass                                    # 在包外，正常

    # ---- 闸门二/三/五：出图前把提示词扫一遍（方案文件可能是手改过的）----
    blocklist = load_person_blocklist(a.person_blocklist)
    blocked = []
    for it in items:
        it["leaks"] = it.get("leaks") or prompt_gate(it["prompt"], blocklist)
        if it["leaks"]:
            blocked.append(it)
    if blocked and not a.allow_prompt_hits:
        for it in blocked:
            sys.stderr.write("!! #%s 出图提示词命中闸门：\n" % it["id"])
            for kind, why in it["leaks"]:
                sys.stderr.write("     %s\n" % _red("%s：%s" % (kind, why)))
        sys.stderr.write(
            "\n共 %d 张被判不合格，**已拦截，未提交任何任务**（不花一分钱）。\n"
            "改掉提示词后重跑；确实要带违禁词出图才加 --allow-prompt-hits"
            "（人物合规与未成年人不建议绕过）。\n" % len(blocked))
        return _fail(3, "gate", "有出图提示词命中本地闸门，已拦截、未提交任何任务")

    outdir.mkdir(parents=True, exist_ok=True)
    state_path = a.state or str(outdir / STATE_NAME)
    state = load_state(state_path)

    resolution = items[0]["resolution"]
    cost = estimate_cost(len(items), resolution, a.points_per_image)
    _print_gen_plan(items, outdir, resolution, a.points_per_image, action)
    print("\n预估成本：%s" % fmt_cost(cost))
    for n in cost.get("notes") or []:
        print("  · %s" % n)

    # ---- 闸门四：成本上限。**在提交任何任务之前**判，超了直接停。-------
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
            sys.stderr.write("[%d/%d] #%s 提交：action=%s aspect_ratio=%s resolution=%s model=%s\n"
                             % (n, len(items), it["id"], action, it["aspect_ratio"],
                                it["resolution"], it.get("model") or DEFAULT_IMAGE_MODEL))
            try:
                data = submit_image(it["prompt"], aspect_ratio=it["aspect_ratio"],
                                    resolution=it["resolution"],
                                    model=it.get("model") or DEFAULT_IMAGE_MODEL,
                                    action=action, image_urls=it.get("image_urls"),
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
                "id": it["id"], "style": it.get("style"), "preset": it.get("preset"),
                "prompt": it["prompt"], "aspect_ratio": it["aspect_ratio"],
                "resolution": it["resolution"], "model": it.get("model"),
                "action": action, "image_urls": it.get("image_urls") or [],
                "task_id": task_id, "status": "pending",
                "frozen_points": data.get("frozen_points"),
                "request": {"prompt": it["prompt"], "action": action,
                            "resolution": it["resolution"],
                            "aspect_ratio": it["aspect_ratio"],
                            "model": it.get("model"),
                            "image_urls": it.get("image_urls") or None},
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
        dest = outdir / ("%s-%s-%s-%s%s" % (it["id"], it.get("preset") or "img",
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

        want = it.get("design_ratio") or it["aspect_ratio"] if a.snap_on_design \
            else it["aspect_ratio"]
        check = check_ratio(str(dest), want, a.ratio_tolerance)
        # 保留**裁剪前**的原始判定。这份证据很重要：它记录了上游真实给了什么像素，
        # 裁过之后就不该再拿裁后结果冒充「上游原始产出」。
        first_check = dict(check)
        rec["image_url"] = url
        rec["file"] = str(dest)
        rec["first_check"] = first_check
        rec["real_px"] = check["real_px"]
        rec["real_ratio"] = check.get("real_ratio")
        rec["want_ratio"] = want
        rec["ratio_deviation"] = check["deviation"]

        # --snap 的默认口径：**偏差 > 0 就裁准**（上游按 32 对齐，3:4 与 16:9
        # 天然不是精确比例；用户加 --snap 的意图就是要像素级精确）。
        # 想回到「只在超容差时裁」的保守口径，用 --snap-when overtolerance。
        need_snap = bool(a.snap) and (
            (not check["ok"]) if a.snap_when == "overtolerance"
            else bool(check.get("deviation")))
        if need_snap:
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
                               "why": "没有 PIL，内置裁剪器也不支持这个 PNG"
                                      "（需 8 位真彩/真彩+alpha）；**没能裁，未假装成功**"}
        rec["raw_ratio_check"] = check

        rec["ratio_ok"] = bool(check["ok"])
        rec["status"] = "completed"
        save_state(state_path, state)
        if check["ok"]:
            done.append((it, rec))
            print("    完成 真实像素 %sx%s  比例 %s  偏差 %s  扣费 %s 点  → %s"
                  % (check["real_px"][0], check["real_px"][1],
                     check.get("real_label"),
                     "—" if check["deviation"] is None else "%.2f%%" % (check["deviation"] * 100),
                     pts, rec["file"]))
        else:
            ratio_bad.append((it, rec))
            print("    " + _red("完成但比例不合格：%s" % check.get("why")))
            print("    " + _red("  → %s" % rec["file"]))

    # ------------------------------------------------------------------
    # 收尾
    # ------------------------------------------------------------------
    summary = {
        "plan": str(a.plan) if a.plan else None, "outdir": str(outdir),
        "state": state_path, "action": action,
        "planned_images": len(items),
        "completed": [{"id": it["id"], "style": it.get("style"),
                       "preset": it.get("preset"),
                       "task_id": r.get("task_id"),
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
            print("  " + _red("✗ #%s %s 失败：%s" % (f["id"], f["stage"], f.get("error"))))
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
    """让 `--json` 写在子命令**前后都能用**。

    只用父级的 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py styles --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 头像写真工坊：一张人像照 + 一个风格包，批量出头像与写真",
        allow_abbrev=False)
    ap.add_argument("--key", help="临时指定 api.a7w.cn 的 Key（别写进脚本或文档）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --- styles ---
    p = sub.add_parser("styles", help="列出内置风格包（零网络、零成本）", allow_abbrev=False)
    _add_json(p)
    p.set_defaults(func=cmd_styles)

    # --- plan ---
    p = sub.add_parser("plan", help="出拍摄方案（零网络、零成本，本地矩阵展开）", allow_abbrev=False)
    _add_json(p)
    p.add_argument("--style", action="append", choices=list(STYLE_PACKS),
                   help="风格包，可重复；默认 business")
    p.add_argument("--preset", action="append", choices=list(PRESETS),
                   help="比例预设，可重复；默认三个全出（avatar / cover34 / wide）")
    p.add_argument("--variants", type=int, default=1,
                   help="每个「风格×比例」出几个姿态变体，默认 1")
    p.add_argument("--subject", help="人设描述（年龄、性别、发型、气质等），会织进每条提示词")
    p.add_argument("--count", type=int, help="最多保留几条（截断矩阵）")
    p.add_argument("--person-blocklist", help="外挂人物名单文件（一行一个名字，命中即拦）")
    p.add_argument("--out", help="把方案写到这个 JSON 文件（gen 要用它）")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点），只用于报价")
    p.set_defaults(func=cmd_plan)

    # --- cost ---
    p = sub.add_parser("cost", help="只算钱不出图", allow_abbrev=False)
    _add_json(p)
    p.add_argument("--count", type=int, required=True, help="要出几张")
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--budget", type=float, help="预算上限（点），超了退出码 3")
    p.set_defaults(func=cmd_cost)

    # --- models ---
    p = sub.add_parser("models", help="列出在架应用与模型", allow_abbrev=False)
    _add_json(p)
    p.set_defaults(func=cmd_models)

    # --- verify ---
    p = sub.add_parser("verify", help="复核已有图片的比例真伪（闸门一）", allow_abbrev=False)
    _add_json(p)
    p.add_argument("files", nargs="+", help="要复核的图片文件")
    p.add_argument("--ratio", required=True, help="请求比例，如 1:1 / 3:4 / 16:9")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   help="比例容差，默认 %.3f（实测最大偏差 2.70%%）" % RATIO_TOLERANCE)
    p.set_defaults(func=cmd_verify)

    # --- gen ---
    p = sub.add_parser("gen", help="批量出图（真花钱，先报价再确认）", allow_abbrev=False)
    _add_json(p)
    p.add_argument("--plan", help="plan 产出的方案 JSON")
    p.add_argument("--prompt", help="直接给一条出图提示词（与 --plan 二选一）")
    p.add_argument("--style", action="append", choices=list(STYLE_PACKS),
                   help="按风格包过滤方案，可重复")
    p.add_argument("--preset", action="append", choices=list(PRESETS),
                   help="按比例预设过滤方案，可重复")
    p.add_argument("--ratio", help="只配 --prompt 用：覆盖生成比例，如 3:4")
    p.add_argument("--photo-url", action="append",
                   help="参考图公网 URL（**上游只接受 HTTP/HTTPS 地址，无本地上传接口**）；"
                        "给了就是 action=edit 的图生图")
    p.add_argument("--action", choices=list(ACTIONS), help="generate 或 edit；默认按是否有 --photo-url 推断")
    p.add_argument("--model", default=DEFAULT_IMAGE_MODEL,
                   help="出图模型，默认 %s" % DEFAULT_IMAGE_MODEL)
    p.add_argument("--resolution", choices=list(RESOLUTIONS), help="覆盖分辨率")
    p.add_argument("--count", type=int, help="最多出几张（截断方案）")
    p.add_argument("--outdir",
                   default=str(Path(os.environ.get("TEMP") or ".") / "portrait-studio-out"),
                   help="图片输出目录（**必须在 Skill 包外**，否则退出码 2）")
    p.add_argument("--state", help="断点文件路径，默认 <outdir>/%s" % STATE_NAME)
    p.add_argument("--budget", type=float, help="成本上限（点）：超了直接停，不提交")
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--yes", action="store_true", help="确认真的花钱（不加就只报价）")
    p.add_argument("--snap", action="store_true",
                   help="出图后按请求比例精确裁剪（上游按 32 对齐，3:4 与 16:9 拿不到精确比例）")
    p.add_argument("--snap-when", choices=("nonzero", "overtolerance"), default="nonzero",
                   help="nonzero=只要偏差>0 就裁准（默认）；overtolerance=只在超容差时裁")
    p.add_argument("--snap-on-design", action="store_true",
                   help="按设计比例（design_ratio）裁，而不是按生成比例")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   help="比例容差，默认 %.3f（实测最大偏差 2.70%%）" % RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT,
                   help="单张轮询超时秒数，默认 %g（上限，不是期望时长）" % POLL_TIMEOUT_DEFAULT)
    p.add_argument("--poll-interval", type=float, default=a7w.POLL_INTERVAL,
                   help="轮询间隔秒数，默认 %g" % a7w.POLL_INTERVAL)
    p.add_argument("--max-seconds", type=float, help="整批最长耗时（秒），到点中断（退出码 5），可续跑")
    p.add_argument("--force", action="store_true", help="忽略断点，全部重出（**会重复扣费**）")
    p.add_argument("--no-wait", action="store_true", help="只提交不等结果（稍后用 task 续查）")
    p.add_argument("--stop-on-error", action="store_true", help="一张失败就整体停")
    p.add_argument("--person-blocklist", help="外挂人物名单文件（一行一个名字，命中即拦）")
    p.add_argument("--allow-prompt-hits", action="store_true",
                   help="即使提示词命中闸门也出图（默认拦截；人物合规与未成年人不建议绕过）")
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
