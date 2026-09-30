#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 长文自动生产线（sanjianke-longform-factory）。

给一个主题，一条链路产出**可发布的长文**：
    选题角度 → 大纲 → 正文（3000 字级）→ 配图（自动决定画什么、几张）→ 平台适配。

子命令
    outline  出选题角度 + 大纲（角度 / 钩子 / 分节小标题 / 每节字数与要点）
    write    按大纲写正文（长文 3000 字级：标题 + 正文 + 结尾引导）
    images   按正文出配图方案（自动决定画什么、几张、什么比例），**先报价再出图**
    adapt    把长文改写成平台版（公众号 / 头条 / 知乎）
    all      跑完整条链路（大纲 → 正文 → 配图 → 适配），**断点续跑**
    cost     只算钱，一次调用都不发
    models   列出 api.a7w.cn 当前在架的模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）
    大模型       POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单     GET  https://api.a7w.cn/api/v1/models
    出图（异步） POST https://api.a7w.cn/api/v1/apps/nano_banana/submit
    任务轮询     GET  https://api.a7w.cn/api/v1/tasks/<task_id>

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py outline --topic "短视频批量出片" --key sk-xxxx
    export A7W_API_KEY=sk-xxxx      # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

八道本地硬闸门（都是**拦截**：标红 + stderr 汇总 + 退出码非 0，不是"提示一下"）
    1. 合规          广告法违禁词；「最X」有可枚举的上下文豁免，句首不许误豁免
    2. 占位符残留    `{}`、`[待填]`、`XXX`、`（此处省略）`
    3. prompt_echo   去标点相等 / 二元组 Jaccard ≥ 0.75 / 示例覆盖度 ≥ 0.60
    4. 字数区间      长文按平台区间校验（公众号 / 头条 / 知乎各自口径）
    5. 结构完整性    标题 + 正文 + 结尾引导，缺一项标红
    6. 出图比例真伪  读**真实像素**，不许信接口自报；容差 3%，容差内也打印偏差
    7. 成本上限      `images` / `all` 发起出图前必须先报价，超 `--budget` 停
    8. `--outdir`    落在包内 → exit=2（产出图不许进包，包内白名单只收文本）

设计取舍
    · 闸门判定全部在本地做确定性判定，不采信模型自评（"我检查过了"不算数）。
    · 字数、配图张数都是**产出侧**约束：模型少给还是多给都会被如实报出来，
      超出的部分不偷偷截断，让用户自己决定删哪句。
    · 文本成本只出 **token**：网关不公布文本模型单价（pricing 表不含文本模型、
      models 无价格字段、usage 无 points_cost），所以**金额必须用户自填单价**，
      默认只渲染 token；给了 --yuan-per-ktok 才渲染金额，并明确标成估算。
    · 出图成本用**实测价**：nano_banana 1K = 24 点/张。2K/4K 没实测过，不给默认价。
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
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402  ← 共用零依赖客户端；**逐字节等于规范版，本包不改它**
import imgprobe  # noqa: E402  ← 本包自己的图片头探针（读真实像素），独立模块

# 控制台统一按 UTF-8 输出，避免 Windows 代码页把中文和 emoji 打成乱码
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

STATE_NAME = "longform-state.json"

# ---------------------------------------------------------------------------
# nano_banana 出图应用相关（本包业务，**放在这里而不是 a7w.py**）
#
# 【约定】`scripts/a7w.py` 是所有 Skill 包共用的零依赖客户端，我们靠
# 「包内副本 SHA256 == 规范版」批量校验 60+ 个包有没有被改坏。
# 所以**任何包都不许为了自己的业务往 a7w.py 里加东西**：
#   · 需要读图片像素     → 独立模块 `imgprobe.py`
#   · 需要应用专属的接口 → 就写在下面这一段里
# ---------------------------------------------------------------------------

APP_IMAGE = "nano_banana"                   # 出图应用编码
API_SUBMIT = "submit"                       # POST /api/v1/apps/nano_banana/submit
TASK_URL = a7w.HOST + "/api/v1/tasks/{}"    # GET  /api/v1/tasks/<task_id>（实际用它）

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
# 只有 1K 是真金白银打出来的数；2K/4K 没实测过 → 不给默认价，
# 想估算必须自己传 --points-per-image，宁可拒绝估算也不编一个数。
POINTS_PER_IMAGE_1K = 24
POINTS_PER_YUAN = 100
UNTESTED_RESOLUTIONS = ("2K", "4K")

OUT_EXT = ".png"

# ---------------------------------------------------------------------------
# 平台规格：字数区间 / 结构要求 / 配图张数与比例
#
# 字数区间是**硬区间**（闸门四按它判）：长文写不到下限读者觉得水，
# 超过上限平台会折叠或截断。三种平台的区间不一样，所以做成表，不写死在函数里。
#
# 配图张数是**建议档**，不是硬闸门：模型给多给少都会如实报出来并提示，
# 但不会因为"多画了一张"就判不合格（那属于创作自由，不是缺陷）。
# ---------------------------------------------------------------------------

PLATFORMS = {
    "wechat": {
        "name": "公众号",
        "chars": (2500, 4500),
        "images": (2, 5),
        "ratio": "16:9",
        "note": "长图文。开头 3 行内必须给出「读完能拿到什么」；"
                "小标题要能单独被截图传播；结尾引导偏「在看 / 转发 / 关注」。",
        "structure": "开头钩子 + 3~6 个小标题分节 + 结尾引导",
    },
    "toutiao": {
        "name": "头条",
        "chars": (1800, 3500),
        "images": (3, 6),
        "ratio": "16:9",
        "note": "信息流。第一段就要给结论（信息流的读者只看前两屏）；"
                "段落短、每段不超过 4 行；结尾引导偏「关注看后续」。",
        "structure": "结论前置 + 分点展开 + 结尾引导",
    },
    "zhihu": {
        "name": "知乎",
        "chars": (2500, 6000),
        "images": (1, 4),
        "ratio": "4:3",
        "note": "问答体。开头必须先给判断（赞同/反对/分情况），再给依据与边界条件；"
                "允许更长的推理链；结尾引导偏「收藏 / 追更 / 评论区补充」。",
        "structure": "先给判断 + 依据与边界 + 结尾引导",
    },
}
PLATFORM_CHOICES = list(PLATFORMS.keys())

# 长文正文（write 子命令）的默认区间：取公众号口径，因为"长文"的默认场景就是公众号长图文。
LONGFORM_CHARS = PLATFORMS["wechat"]["chars"]
# 结束语/结尾引导的识别口径（闸门五用）：段末出现这些词之一，就算有引导。
ENDING_MARKERS = ("关注", "在看", "转发", "收藏", "点赞", "留言", "评论", "订阅",
                  "追更", "分享", "点个", "加个星标", "下篇", "下一篇")

# 配图角色：决定"这张图画什么"
IMAGE_ROLES = {
    "cover": "封面：第一眼要能读懂这篇文章讲什么，主体大、留白够、不堆字",
    "flow": "流程图：把文里的步骤画成一条链，箭头清晰，不要花哨装饰",
    "compare": "对比图：左右分栏呈现两个状态的差别，两栏信息量对等",
    "data": "数据图：把一组数字视觉化（**只画文稿里真实出现过的数字**）",
    "scene": "场景图：一个人正在做这件事的画面，用于把抽象内容变具体",
    "quote": "金句图：一句核心判断 + 大量留白，文字要少",
    "ending": "结尾图：引导关注/收藏，克制不吆喝",
}
ROLE_CHOICES = list(IMAGE_ROLES.keys())

# 上游实际能给的像素（1K 档，实测 10 种比例）。留作文档与排错依据。
MEASURED_1K_PIXELS = {
    "1:1": [1024, 1024], "3:4": [864, 1184], "4:3": [1184, 864],
    "16:9": [1344, 768], "9:16": [768, 1344], "21:9": [1536, 672],
    "2:3": [832, 1248], "3:2": [1248, 832], "4:5": [896, 1152],
    "5:4": [1152, 896],
}

# ---------------------------------------------------------------------------
# 闸门一：合规自检（广告法违禁词 + 新媒体专属条目）
#
# 每一行：正则 → 风险等级 → 人话解释。这是**粗筛**，宁可多报也别漏报；
# 最终判断仍要人工复核，也不等于平台的官方审核结论。
#
# 新媒体长文为什么单列"站外导流 / 标题党"两档：这两类不是广告法问题，
# 是平台审核问题——公众号文章里放微信号、用「震惊体」，是限流与被删的直接原因。
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    # —— 广告法绝对化用语 ——
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎|顶尖|厉害)", "高",
     "广告法第九条禁止「最高级」用语"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    (r"(全国|全球|全网|行业|销量|口碑|人气)第一|第一品牌|排名第一|"
     r"No\.?\s*1|TOP\s*1", "高", "「第一」类排他性表述"),
    (r"国家级|世界级|全球级|国际级|国家级产品", "高",
     "「国家级」等权威性词汇属明令禁止"),
    (r"100\s*%|百分之百|百分百", "高", "绝对化效果承诺"),
    (r"绝对(有效|安全|放心|不会|能|可以|正确|专业)|"
     r"保证(有效|成功|学会|通过|就业|录用)|无效退款", "高", "绝对化保证与效果担保"),
    # —— 新媒体场景最常见的两类（不是广告法，是平台审核）——
    (r"治愈|根治|痊愈|药到病除|包治|疗效|无副作用|零副作用", "高",
     "医疗功效宣称，非药品/医疗器械不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报|内部渠道|"
     r"跟着买就(赚|涨)", "高", "投资类收益承诺与荐股话术"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方(推荐|认证|指定)|"
     r"教育部(认证|指定)|人社部(认证|指定)", "高", "不得虚构权威背书"),
    # 【实测修正】「唯一（品牌/技术/认证/选择…）」才拦；裸的「唯一」不拦。
    # 依据（继承课程生产线的真机结论）：模型会把"唯一标准"当普通词用
    # （"判断一段画面是不是废片，唯一标准是够不够清晰稳定"），
    # 那不是排他性广告宣称，一刀切属于必然误伤。所以只留真正在贴排他性标签的形态。
    (r"独家|首创|填补空白|行业领先|领先品牌|领先技术|"
     r"唯一(选择|指定|授权|官方|认证|品牌|推荐|渠道|合作)", "中",
     "排他性表述需有可举证依据"),
    (r"免费领|免费送|0\s*元购|白送", "中", "可能构成虚假优惠或诱导分享"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天|名额有限先到先得", "中",
     "促销时限表述需与实际活动一致"),
    (r"纯天然|无添加|零添加|无毒无害", "中", "成分宣称需与检测报告一致"),
    (r"催情|壮阳|丰胸|减肥(药|神器)|美白针|生发(神器)", "高",
     "特殊功效与特殊品类敏感词"),
    (r"点击链接|加微信|私信我|扫码(加|进)|vx|VX|微信号|加我好友", "中",
     "站外导流，平台普遍限制"),
    (r"(震惊|惊呆|不看后悔|错过再等一年|速看|删前必看|最后一天)", "中",
     "标题党式诱导"),
    (r"[！!]{2,}|[?？]{3,}", "低", "标点堆砌，易被判标题党/低质"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}

# 命中之后再看一眼**后续几个字**：如果接的是比较 / 程度 / 常见这类用法，
# 那它是"普通中文词"而不是"最高级广告语"，放行。
#
# 【实测依据 · 继承课程生产线】真机连跑 4 次讲义，1 次被拦，拦下的是
#   「做菜和剪辑**最大**的共同点是：先做减法，再做加法」
# 这是讲义里在讲一件常识，不是给商品贴"最大"的标签。长文里的形态更常见：
#   「长文和短视频**最大**的区别是……」「新手**最**容易踩的坑是……」
# 这些是文章的正文骨架，拦下来的代价比漏报更大。所以加一层上下文豁免，
# 但**豁免范围写死在代码里、可枚举、可复核**，不是一句"人工判断"了事。
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
# 上面那句会在闸门里被拦下，属**已知的保守行为**，靠改文案解决（把「最高」换成「比较大」），
# 不靠放松规则解决。这一条写在报告里，不藏着。
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
# 长文是大模型一次吐几千字，模板没替换干净的形态比标题场景多得多：
#   · `{}` / `{{标题}}`        JSON 骨架被当正文写进去了
#   · `[待填]` / `[待补充]`    模型给自己留的空档
#   · `XXX` / `xxx`            忘了替换的占位
#   · `（此处省略）`           最常见的一种：模型懒得写，直接省略
#
# `[1]`（引用序号）、`[图 2]`（配图位）是**正常写法**，一刀切按括号内容判会把好文章全拦下。
# 注意本包的显式要求里点名了 `[待填]`，所以括号那条的枚举表里必须有它。
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
# 事故复盘（来自爆款标题工坊的实测，两次都真被抓到）：
#   1. 提示词里写过正例 `结论先说：便携榨汁杯不适合三类人` → 模型直接产出近似句
#   2. 提示词里留过 `便携榨汁杯不适合这三类人，理由有三个` → 公众号那一轮**最高分 89.0 的
#      标题一字不差就是它**
# 第 2 例性质更重：最高分那条是"抄了标准答案"，不是"真的最好"，而排序是那个包的核心产出。
#
# 在本包里形态是：示例小标题 / 示例开头句被照抄 → 整篇文章变成"把示例换个主题词"，
# 段落顺序、句式全部雷同——看起来完全正常，直到你发现它是模板填空题。
#
# 判定：与示例去标点后**相等** → 命中；字符二元组 Jaccard ≥ 0.75 → 命中。
# 阈值标定依据：标题工坊实测 196 条正常产出与跨主题示例的最高相似度只有 0.174，
# 而"少两个字的同构照抄"是 0.765。0.75 既能兜住轻改写，离正常上限还有 4 倍余量。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
# 覆盖度阈值：示例的字符二元组里有多大比例出现在产出中。
#
# 【为什么必须再加这一条】Jaccard 在两个长度差几十倍的对象之间会被**稀释**：
# 实测把一条 40 字的示例原样塞进一份 2400 字的讲义，Jaccard 只有 **0.17**（远低于 0.75，
# 侥幸放行），因为分母是两份二元组的并集，产出那一侧的体量把相似度摊薄了。
# 覆盖度只看"示例被抄了多少"，不看产出有多长：同一次照抄的覆盖度是 **1.00**。
# 长文比讲义更长（3000~4500 字），稀释只会更严重，所以这条对本包是必需的。
ECHO_CONTAIN = 0.60
# 长度守卫（**相对阈值**，与同族另外四个包统一）：目标归一化长度 < max(6, len(示例)//2)
# 时就不比相似度与覆盖度 —— 短串的二元组太少，指标会虚高。
# 用绝对阈值 12 会让短示例的包漏掉「≤11 字的截断照抄」；本包示例 18~40 字 → 门槛 9~20。
ECHO_MIN_LEN_FLOOR = 6


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


# 提示词里出现过的示例文本（跨主题，正常不该被抄）。新增示例必须登记到这里。
PROMPT_SAMPLES = [
    # 角度示例：故意用了与本包业务不搭的领域（水产养殖 / 木工 / 天文观测），
    # 模型不会把"蚝苗"这种词搬进短视频批量出片的文章里。
    "为什么养殖户开始用无人机看蚝排",
    "手工木工为什么先学磨刀而不是学开料",
    "业余天文爱好者第一次买赤道仪会后悔的三件事",
    # 正文结构示例：同样用不搭界的领域，且刻意写得"不像正常会写的句子"，
    # 免得真实产出与它撞相似度。
    "先把结论放在第一段，再用三个要点展开，最后给一句能带走的话",
]


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的产出往往只改标点（`，`↔`、`↔空格），所以必须先抹平标点再看。
    """
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _bigrams(s):
    s = _norm_for_echo(s)
    if len(s) < 2:
        return set(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _similarity(a, b):
    """字符二元组 Jaccard 相似度，0~1。"""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(len(ba | bb))


def prompt_echo(text, samples=None):
    """文本是否与登记过的示例"抄得太近"。返回 (是否命中, 得分, 撞上的示例, 判定依据)。

    三条命中路径（任一即命中）：
      1. 去标点后**完全相同** —— 最直接的照抄
      2. 字符二元组 **Jaccard ≥ ECHO_SIM** —— 长度相当的同构改写
      3. 示例的二元组**覆盖度 ≥ ECHO_CONTAIN** —— 长文里夹带示例（Jaccard 会被摊薄，
         只有覆盖度能抓住；见上面 ECHO_CONTAIN 的标定依据）
    """
    target = _norm_for_echo(text)
    if not target:
        return False, 0.0, "", ""
    best_score, best_sample, best_rule = 0.0, "", ""
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        if target == _norm_for_echo(s):
            return True, 1.0, s, "exact"
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(text, s)
        base = _bigrams(s)
        contain = (len(_bigrams(text) & base) / float(len(base))) if base else 0.0
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        if contain >= ECHO_CONTAIN and contain >= best_score:
            best_score, best_sample, best_rule = contain, s, "contain"
    if best_rule:
        return True, best_score, best_sample, best_rule
    return False, best_score, best_sample, ""


def echo_hits(text, where="产出"):
    """对一个产出片段跑 prompt_echo，返回命中列表。"""
    echoed, score, sample, rule = prompt_echo(text)
    if not echoed:
        return []
    if rule == "exact":
        return [{"kind": "prompt_echo",
                 "why": "%s与提示词示例「%s」去掉标点后完全相同（照抄示例）" % (where, sample[:32])}]
    if rule == "contain":
        return [{"kind": "prompt_echo",
                 "why": "%s里有 %.0f%% 的内容来自提示词示例「%s」（长文夹带照抄，"
                        "Jaccard 会被摊薄，靠覆盖度抓到）"
                        % (where, score * 100, sample[:32])}]
    return [{"kind": "prompt_echo",
             "why": "%s与提示词示例「%s」相似度 %.2f，属同构照抄" % (where, sample[:32], score)}]


# ---------------------------------------------------------------------------
# 闸门四：字数区间（长文按平台区间校验）
#
# 「3000 字级」不是一个精确数字，是**区间**：公众号 2500~4500 / 头条 1800~3500 /
# 知乎 2500~6000。低于下限读者觉得水，高于上限平台折叠或截断。
#
# 计数口径：去掉 Markdown 符号与空白后的字符数（中英文都按字符算）。
# 为什么不按"汉字数"算：一篇长文里中英混排、数字与代码都很常见，
# 只数汉字会把 400 字的英文段落当 0 字，判定会比实际情况宽松得多。
# ---------------------------------------------------------------------------

MARKUP_NOISE_RE = re.compile(r"[#*>`\-\s\[\]()|~]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def count_chars(text):
    """正文字数：去掉 Markdown 符号与空白后的字符数。"""
    return len(MARKUP_NOISE_RE.sub("", text or ""))


def count_cjk(text):
    """顺手给一个汉字数（仅供参考，不参与闸门判定）。"""
    return len(CJK_RE.findall(text or ""))


def length_verdict(text, platform=None, chars_range=None):
    """闸门四：字数是否落在区间内。返回 (ok, chars, lo, hi, why)。"""
    lo, hi = chars_range or PLATFORMS.get(platform or "wechat", PLATFORMS["wechat"])["chars"]
    n = count_chars(text)
    if n < lo:
        return False, n, lo, hi, ("正文 %d 字，低于%s区间下限 %d 字（偏短，内容撑不起来）"
                                  % (n, _plat_name(platform), lo))
    if n > hi:
        return False, n, lo, hi, ("正文 %d 字，超过%s区间上限 %d 字（平台会折叠或截断；"
                                  "脚本不会替你截断，请自己删）"
                                  % (n, _plat_name(platform), hi))
    return True, n, lo, hi, "正文 %d 字，落在%s区间 %d~%d 字内" % (n, _plat_name(platform), lo, hi)


def _plat_name(platform):
    p = PLATFORMS.get(platform or "")
    return ("%s" % p["name"]) if p else "长文"


# ---------------------------------------------------------------------------
# 闸门五：结构完整性（标题 + 正文 + 结尾引导）
#
# 教训来自爆款标题工坊：那里只信模型自报的 `formula` 字段，结果真该被判命的那条
# 恰好漏判——**闸门是假绿的**。在本包里对应的形态是：模型返回一个
# `{"title": "...", "content": "..."}` 而 content 里既没有小标题、也没有结尾引导，
# 脚本照样打印"正文已生成"，用户发出去才发现文章是"半截"的。
#
# 所以结构必须**逐项校验**，缺项标红：
#   · 标题非空，且不是"关于XX的思考"这种无信息量的泛题
#   · 正文非空，且有分节（至少 3 个 Markdown 小标题或 numbered 小节）
#   · 结尾有引导（结尾两段内出现关注/在看/收藏/评论这类词）
# ---------------------------------------------------------------------------

GENERIC_TITLE_RE = re.compile(
    r"^(关于.{2,12}的(一些)?(思考|想法|看法|总结)|浅谈.{2,12}|随便聊聊|杂谈)$")
MIN_SECTIONS = 3


def structure_checks(article, title=None, content=None, platform=None, ending=None):
    """闸门五的实现：逐项校验长文结构，返回 [{'check','ok','detail'}]。"""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    t = (title if title is not None else (article or {}).get("title") or "").strip()
    body = (content if content is not None
            else (article or {}).get("content") or (article or {}).get("text") or "").strip()
    ending_text = ((ending if ending is not None else (article or {}).get("ending") or "")
                   or "").strip()

    add("有标题", bool(t), "标题：%s" % t[:40] if t else "标题为空")
    if t:
        add("标题不是泛题", not GENERIC_TITLE_RE.match(t),
            "标题具体" if not GENERIC_TITLE_RE.match(t)
            else "「%s」是无信息量的泛题（读者看不出文章讲什么、凭什么点开）" % t[:40])

    n_chars = count_chars(body)
    add("有正文", n_chars > 0, "正文 %d 字" % n_chars if n_chars else "正文为空")

    heads = re.findall(r"^#{2,4}\s+\S", body, re.M)
    numbered = re.findall(r"^\s*(?:\d{1,2}[.、)]|第[一二三四五六七八九十]{1,3}[节部分])", body, re.M)
    n_sec = max(len(heads), len(numbered))
    add("正文有分节", n_sec >= MIN_SECTIONS,
        "解析到 %d 个小节（≥ %d 合格）" % (n_sec, MIN_SECTIONS) if n_sec >= MIN_SECTIONS
        else "只解析到 %d 个小节（要求 ≥ %d）：没有分节的长文没法读，也没法被转发" % (n_sec, MIN_SECTIONS))

    tail = "\n".join([x.strip() for x in body.split("\n") if x.strip()][-5:])
    marker = next((w for w in ENDING_MARKERS if w in tail), "") \
        or next((w for w in ENDING_MARKERS if w in ending_text), "")
    add("有结尾引导", bool(marker),
        "结尾出现引导词「%s」" % marker if marker
        else "结尾五段与 ending 字段里都没有关注/在看/收藏/评论这类引导"
             "（文章发出去等于没结尾）")
    return checks


# ---------------------------------------------------------------------------
# 闸门六：出图比例真伪（读真实像素，不信自报值）
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
#   c) `--snap`：出图后按请求比例精确裁掉多余像素，让产出真的等于请求比例；
#      裁剪结果再次读文件头复核，裁成功才记 exact
# ---------------------------------------------------------------------------

RATIO_TOLERANCE = 0.03        # 默认 3%（实测最大偏差 2.86%，留一点余量）

# 容差地板：**像素只能是整数**，所以「裁到精确比例」本身就有量化误差。
# 实测（--snap 之后复核）：2.35:1 @宽 864 → 高 368，偏差 0.0925%；
# 相邻整数像素间隔约 0.27%。所以用户把 --ratio-tolerance 调到比这还小时，
# 会把「本来就必须存在」的舍入误差判成不合格。0.0025 是保守地板，仍能抓住真错：
# 请求 3:4 却给 2:3 的偏差是 11%，比地板大 40 倍。
RATIO_TOLERANCE_FLOOR = 0.0025

parse_ratio = imgprobe.parse_ratio
ratio_label = imgprobe.ratio_label


def check_ratio(path, want_ratio, tolerance=None):
    """闸门六：读真实像素，判是否等于请求比例。

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
# 为什么值得做：上游按 32 对齐，3:4 实测给 864x1184（偏差 2.70%）。
# 自媒体平台对封面比例是有像素级要求的，差 2% 在 3:4 上就是 24 像素，
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
        ihdr, idat = None, []
        for typ, data in _png_chunks(blob):
            if typ == b"IHDR":
                ihdr = data
            elif typ == b"IDAT":
                idat.append(data)
            elif typ == b"IEND":
                break
        if not ihdr or not idat:
            return None
        w, h, depth, ctype = struct.unpack(">IIBB", ihdr[:10])
        if depth != 8 or ctype not in (2, 6):
            return None
        bpp = 4 if ctype == 6 else 3
        stride = w * bpp
        raw = zlib.decompress(b"".join(idat))
        if len(raw) < (stride + 1) * h:
            return None
        pixels = _unfilter(raw, stride, h, bpp)
        want = parse_ratio(want_ratio)
        if w / float(h) > want:
            nw, nh = max(1, int(round(h * want))), h
        else:
            nw, nh = w, max(1, int(round(w / want)))
        left, top = (w - nw) // 2, (h - nh) // 2
        rows = []
        for y in range(top, top + nh):
            rows.append(pixels[(y * stride + left * bpp):(y * stride + (left + nw) * bpp)])
        _png_write(dst, nw, nh, bpp, rows)
        return "stdlib-png", (left, top, nw, nh)
    except Exception:
        return None


def snap_to_ratio(src, dst, want_ratio):
    """把图精确裁到 want_ratio。返回 (方式, 裁剪框) 或 None。"""
    got = _try_pil_crop(src, dst, want_ratio)
    if got:
        return got
    return _try_stdlib_png_crop(src, dst, want_ratio)


# ---------------------------------------------------------------------------
# 闸门七（成本）口径
#
# 【与课程生产线不同的地方，必须说清】
#   · 文本：网关**不公布文本模型单价**（pricing 表不含文本模型、models 无价格字段、
#     usage 无 points_cost）。所以本包**默认只出 token，不出金额**；
#     要金额必须用户自己传 --yuan-per-ktok，传了就明确标成"用户自填单价的估算"。
#     —— 我们不编一个"看起来合理"的价，因为编出来的数字会被当成账单。
#   · 出图：有实测价（nano_banana 1K = 24 点/张），按实测价报价；
#     2K/4K 没实测过 → 不给默认价，拒绝凭猜估算。
# ---------------------------------------------------------------------------

POINTS_PER_YUAN = 100            # 算力集市的充值比例：1 元 = 100 点

# 一次调用的 token 用量预估（用于 cost 子命令与 --budget 前置检查）
EST_TOKENS = {
    "outline": {"prompt": 1100, "completion": 2600},
    "write": {"prompt": 1800, "completion": 7000},
    "adapt": {"prompt": 2600, "completion": 5200},
    "images": {"prompt": 1400, "completion": 1800},
}


def unit_points(resolution, override=None):
    """单张出图成本（点）。只有 1K 有实测价；2K/4K 不给默认值。"""
    if override is not None:
        return float(override)
    if (resolution or "1K").upper() == "1K":
        return float(POINTS_PER_IMAGE_1K)
    return None


def image_cost(count, resolution="1K", override=None):
    """出图成本预估 dict。拿不到可信单价时**诚实返回 None**，不编价。"""
    pts = unit_points(resolution, override)
    rec = {"count": int(count), "resolution": (resolution or "1K").upper(),
           "points_per_image": pts,
           "source": "override(--points-per-image)" if override is not None else "实测",
           "points_per_yuan": POINTS_PER_YUAN, "notes": []}
    if pts is None:
        rec["total_points"] = None
        rec["total_yuan"] = None
        rec["notes"].append(
            "%s 档没有实测单价，拒绝凭猜估算：请用 --points-per-image 指定单价后重算"
            % rec["resolution"])
        return rec
    if override is not None:
        rec["notes"].append("单价来自 --points-per-image，不是我们实测的数")
    rec["total_points"] = pts * rec["count"]
    rec["total_yuan"] = rec["total_points"] / float(POINTS_PER_YUAN)
    rec["notes"].append("按实测价 %g 点/张（1K）计算；实际扣费以任务返回的 usage.points_cost 为准"
                        % POINTS_PER_IMAGE_1K)
    rec["notes"].append("提交时会先冻结（实测 frozen_points 比结算值略高），完成后按实测结算，"
                        "失败全额退回；只信 usage.points_cost")
    return rec


def fmt_image_cost(rec):
    if rec.get("total_points") is None:
        return "无法估算（%s）" % "；".join(rec.get("notes") or [])
    return "%d 张 × %g 点 = %g 点 = %.2f 元" % (
        rec["count"], rec["points_per_image"], rec["total_points"], rec["total_yuan"])


def text_cost_record(calls, prompt_tokens, completion_tokens, yuan_per_ktok=None,
                     estimated_calls=0):
    """文本成本记录。**默认只出 token**；给了单价才出金额并标成自填口径。"""
    total = prompt_tokens + completion_tokens
    rec = {"calls": calls, "prompt_tokens": prompt_tokens,
           "completion_tokens": completion_tokens, "total_tokens": total,
           "estimated_calls": estimated_calls,
           "yuan_per_ktok": yuan_per_ktok, "yuan": None, "points": None,
           "price_source": "user-supplied" if yuan_per_ktok is not None else "unknown",
           "notes": [
               "网关不公布文本模型单价（pricing 表不含文本模型、models 无价格字段、"
               "usage 无 points_cost），所以这里**只出 token**。",
           ]}
    if yuan_per_ktok is not None:
        rec["yuan"] = round(total / 1000.0 * float(yuan_per_ktok), 4)
        rec["points"] = round(rec["yuan"] * POINTS_PER_YUAN, 1)
        rec["notes"].append(
            "金额按**你自己填的** %g 元/千 token 折算，是估算不是账单；"
            "真实账单以 api.a7w.cn 控制台为准。" % float(yuan_per_ktok))
    else:
        rec["notes"].append(
            "要出金额请自己传 --yuan-per-ktok <元/千token>（我们不会替你编一个单价）。")
    if estimated_calls:
        rec["notes"].append("其中 %d 次调用没拿到真实 usage，按估值记账。" % estimated_calls)
    return rec


class CostTracker:
    """累计真实 usage（token）、出图点数，实时核预算。超了就地停（闸门七）。"""

    def __init__(self, budget=None, yuan_per_ktok=None):
        self.budget = budget
        self.rate = None if yuan_per_ktok is None else float(yuan_per_ktok)
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.image_points = 0.0
        self.estimated_flags = 0

    def add(self, usage, label=""):
        """记一次真实 usage；usage 缺失时按估值记并如实标注。"""
        u = usage or {}
        p, c = u.get("prompt_tokens"), u.get("completion_tokens")
        if not isinstance(p, int) or not isinstance(c, int):
            est = EST_TOKENS.get(label) or {"prompt": 0, "completion": 0}
            p, c = est["prompt"], est["completion"]
            self.estimated_flags += 1
        self.calls += 1
        self.prompt_tokens += p
        self.completion_tokens += c

    def add_points(self, points):
        if points:
            self.image_points += float(points)

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    @property
    def yuan(self):
        if self.rate is None:
            return None
        return round(self.total_tokens / 1000.0 * self.rate, 4)

    def over_budget(self, extra_tokens=0, extra_points=0.0):
        """预算核验。给了单价才可能超（没单价时金额未知 → 只报 token，不假装在预算内）。"""
        if self.budget is None:
            return False
        if self.rate is None and not extra_points:
            return False
        cost = 0.0
        if self.rate is not None:
            cost += (self.total_tokens + extra_tokens) / 1000.0 * self.rate
        cost += (self.image_points + extra_points) / float(POINTS_PER_YUAN)
        return cost > self.budget

    def line(self):
        s = ("已用 %d 次文本调用 · token prompt=%d completion=%d total=%d"
             % (self.calls, self.prompt_tokens, self.completion_tokens, self.total_tokens))
        if self.estimated_flags:
            s += "（含 %d 次估值非真实 usage）" % self.estimated_flags
        if self.image_points:
            s += " · 出图已扣 %g 点" % self.image_points
        if self.rate is None:
            s += " · 金额：网关不公布文本单价，**未折算**（要折算就传 --yuan-per-ktok）"
        else:
            s += " · 估算 %.3f 元（按你填的 %g 元/千 token）" % (self.yuan, self.rate)
        return s


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class LongformError(a7w.A7wError):
    """长文生产线失败。"""


class LongformGate(LongformError):
    """被本地硬闸门拦下（与"调用失败"分开，退出码也不同：闸门 3 / 失败 4）。"""


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
         max_tokens=8192, key=None, timeout=300, json_mode=True,
         tracker=None, tracker_label=""):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么必须带退避重试：网关的 upstream timeout / HTTP 502 实测很常见，
    一次长文就是几千 token，被一次抖动打断要整篇重写，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。
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
                sys.stderr.write("上游 %s，%ss 后重试 %d/%d…\n" % (
                    exc.code, 3 * (attempt + 1), attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
            try:
                err = json.loads(text)
            except ValueError:
                err = {}
            msg = err.get("msg")
            if not msg and isinstance(err.get("error"), dict):
                msg = err["error"].get("message")
            if not msg and isinstance(err.get("data"), dict):
                msg = err["data"].get("msg")
            msg = msg or text[:200]
            if exc.code == 401:
                raise LongformError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise LongformError("点数不足（402）：%s  到 https://api.a7w.cn/ 充值后重试。" % msg)
            if exc.code == 404:
                raise LongformError("模型不存在（404）：%s  用 `run.py models` 现查在架模型。" % msg)
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 %s，%ss 后重试…\n" % (exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise LongformError("调用失败（HTTP %s）：%s" % (exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（%s），%ss 后重试 %d/%d…\n" % (
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    if payload is None:
        raise LongformError("网络错误：%s（已重试 %d 次；确认能访问 %s）" % (
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 网关对生成应用那条链路会把结果包一层 {"code":1,"data":{...}}，两种形态都认。
    # 注意：走 /chat/completions 的**成功响应不带 code 字段**，所以不能拿 code 判成功。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise LongformError("模型没返回 choices：%s" % json.dumps(payload, ensure_ascii=False)[:300])
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    finish_reason = (choices[0] or {}).get("finish_reason")
    _LAST_FINISH["reason"] = finish_reason
    _LAST_FINISH["chars"] = len(content)
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    if tracker is not None:
        tracker.add(usage, tracker_label)
    return content, usage


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    为什么要这么写：模型经常在合法 JSON 后面多吐字符（```、解释、第二个对象、
    重复的 }），直接 json.loads 会炸。用 json.JSONDecoder().raw_decode()
    从一个 { 或 [ 开始试解码，成功就返回，失败就往后挪一个字符接着试。
    """
    if not text:
        raise LongformError("模型返回空内容")
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
                obj, _end = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    raise LongformError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


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
        raise LongformError("action 只能是 {}，收到 {!r}".format(" / ".join(ACTIONS), action))
    if resolution not in RESOLUTIONS:
        raise LongformError("resolution 只能是 {}，收到 {!r}".format(" / ".join(RESOLUTIONS), resolution))
    if aspect_ratio not in ASPECT_RATIOS:
        raise LongformError("aspect_ratio 只能是 {}，收到 {!r}".format(
            " / ".join(ASPECT_RATIOS), aspect_ratio))
    body = {"prompt": prompt, "action": action, "model": model,
            "resolution": resolution, "aspect_ratio": aspect_ratio}
    if image_urls:
        body["image_urls"] = list(image_urls)
    if callback_url:
        body["callback_url"] = callback_url
    url = "{}/api/v1/apps/{}/{}".format(a7w.HOST, APP_IMAGE, API_SUBMIT)
    return a7w._unwrap(a7w._request("POST", url, a7w.load_key(key), body=body, timeout=timeout))


def task_state(task_id, key=None):
    """查一次任务，返回 (状态, 归一化 data, 原始信封)。

    ⚠️ 平台文档写 `data.result.status`，**实测 status 在 data 顶层**。按文档写会读到 None。
    """
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
    提交响应里的 frozen_points 也只是**预冻结**，失败全额退回，不是最终扣费。
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
# 提示词
#
# 【铁律】提示词里不许出现任何一份可直接复制的完整产出。
# 讲形态只用描述性语言，举例一律用登记在 PROMPT_SAMPLES 里的**跨主题**示例
# （水产养殖 / 手工木工 / 天文观测），与真实业务主题明显不搭。
# 万一以后有人把真实示例加回提示词，PROMPT_SAMPLES + echo 闸门会兜住。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是三剪客团队的新媒体主编，负责把选题写成能直接发布的长文。\n"
    "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
    "你有三条不可越过的底线：\n"
    "  1. 不写任何效果承诺与绝对化说法——「最好」「第一」「国家级」「100%」"
    "「保证有效」「根治」这类一律不许出现；\n"
    "  2. 不编造数据、人名、机构名、检测结论与权威背书；没有依据就写定性描述；\n"
    "  3. 不留任何待补的空档——不许出现 `{}`、`[待填]`、`XXX`、`（此处省略）`。\n"
    "你写的长文必须能被读完：开头三行给出读者能拿走的东西，中间分节推进，"
    "结尾给一句能带走的话或一个动作。"
)


def build_outline_prompt(topic, platform, angles_wanted, sections_wanted,
                         audience=None, requirements=None, tone=None):
    """选题角度 + 大纲提示词。所有示例一律跨主题，且登记在 PROMPT_SAMPLES。"""
    p = PLATFORMS.get(platform) or PLATFORMS["wechat"]
    extra = []
    if audience:
        extra.append("受众补充说明：%s" % audience)
    if requirements:
        extra.append("必须有把握覆盖的硬性要求（来自用户，不要漏）：%s" % requirements)
    if tone:
        extra.append("语气/调性：%s" % tone)
    return """请为下面这个主题出一份**可执行的长文大纲**。

主题：{topic}
目标平台：{pname}（{pnote}）

结构要求：
- 先给 {angles} 个**互相不重叠**的选题角度。每个角度要有：
  - `angle`：一句话说清"从哪个切面写"
  - `audience`：这个角度是写给谁的
  - `hook`：读者为什么会点开（要具体，不要"很有价值"这种空话）
  - `why_me`：凭什么这篇文章讲这个角度是站得住的（经验/踩坑/反常识）
- 再从这些角度里选**最值得写的 1 个**，在 `chosen` 字段里原样写上它的 `angle` 文本
- 然后给出 `sections`：{sections} 个分节，每节要有：
  - `title`：小标题（要能单独被截图传播，不要"第一部分"这种）
  - `chars`：这一节计划多少字（整数，合计要接近 {total_chars} 字）
  - `points`：2~4 条这一节要讲到的要点（不是整句话）
- `structure` 字段：用一句话描述整篇的行文骨架（{pstructure}）
- 章节顺序要能一路读下来：后一节要用上前一节建立的概念，不许跳步

{extra}
写法约束：
- 小标题不要都用「{topic}」开头，**以它开头的分节不要超过一半**
- 不要写成"是什么 / 为什么 / 怎么办"这种万能三段式，要让读者看出这篇是**具体**讲什么的

讲形态（只体会结构，**不要照抄任何示例内容，也不要改主题**）：
- 好的角度是从一个具体的操作现场切进去的，不是从概念定义切进去的

只输出一个 JSON 对象，不要输出别的任何东西：
{{"topic":"{topic}","platform":"{platform}","angles":[{{"angle":"角度一句话",
"audience":"写给谁","hook":"为什么会点开","why_me":"凭什么站得住"}}],
"chosen":"被选中的那个角度原文","structure":"行文骨架一句话",
"sections":[{{"title":"小标题","chars":600,"points":["要点1","要点2"]}}]}}""".format(
        topic=topic, pname=p["name"], pnote=p["note"], angles=angles_wanted,
        sections=sections_wanted,
        total_chars=int((p["chars"][0] + p["chars"][1]) / 2),
        pstructure=p["structure"], extra=("\n".join(extra) + "\n") if extra else "",
        platform=platform)


def build_write_prompt(topic, platform, outline, chars_range=None, model_note=None):
    """正文提示词。"""
    p = PLATFORMS.get(platform) or PLATFORMS["wechat"]
    lo, hi = chars_range or p["chars"]
    secs = outline.get("sections") or []
    plan_txt = "\n".join(
        "- %s（约 %s 字）：%s" % (s.get("title") or "（未命名）", s.get("chars") or "?",
                                 "、".join(s.get("points") or []) or "（大纲未给要点）")
        for s in secs) or "（大纲没给分节，请自行分成 3~6 节）"
    return """请按下面这份大纲，写出**可直接发布的{pname}长文**。

主题：{topic}
选中的角度：{chosen}
行文骨架：{structure}

分节计划（**顺序与标题都要用上**）：
{plan}

篇幅要求（**最容易翻车的一条，请认真对待**）：
- 正文 **{lo}~{hi} 个字符**（不含 Markdown 符号与空白），这是**硬区间**，脚本会按真实字符数核对
- **目标：{target} 个字符左右**。实测教训：只写"落在区间内"时，模型会习惯性写下限少 4%~20%
  （实测 7 次里有 5 次偏短，最差一次只有下限的 79%），然后被闸门拦下，整篇要重写一遍
- 所以下面这条是**硬结构要求**，请按它来凑够字数：
  **每个 `##` 小标题下面至少写 3 个段落**，每段 2~5 句，不要用一个大段糊过去。
  {sections} 个小节 × 每节 3 段，是达到 {target} 字的基本盘
- 写了具体例子、常见误区、判断标准的地方要展开说清，不要一句带过
- 高于 {hi} 字平台会折叠或截断（脚本**不会**替你截断）

结构要求（缺一项就会被脚本标红）：
- `title`：文章标题（要具体，不要「关于XX的思考」这种泛题）
- `summary`：一句话摘要（30~70 字，用于平台摘要位）
- `content`：正文，Markdown 格式，从 `## 第一个小标题` 开始：
  - **开头三行内**必须让读者知道"读完能拿到什么"
  - 用 `##` 小标题把正文分成 {sections} 节左右，小标题就用上面的计划标题
  - 每节内部可以用 `###` 再分块、用短列表代替长段落
  - **至少一处具体例子**（能跟着复述/照做的，不是"比如可以提高效率"这种空话）
  - **至少一处常见误区**：写清"错在哪、为什么错、怎么改"
  - **结尾必须有引导**：最后两段里要出现关注 / 在看 / 收藏 / 评论 / 转发
    这类词之一，并且是**具体**的一句话（不要"感谢阅读"这种）
- `ending`：把结尾那句引导原样再放一份（方便单独取用）

风格：
- 长短句交替，不要通篇排比
- 不许写"作为 AI""以下是我的回答"这类话，也不要写给自己看的注释
- 术语第一次出现用一句大白话解释
- 不编数据、不编人名机构、不做效果承诺
- 不许留待补空档：`{{}}`、`[待填]`、`XXX`、`（此处省略）` 都不许出现

只输出一个 JSON 对象，不要输出别的任何东西：
{{"title":"文章标题","summary":"一句话摘要","content":"正文（Markdown）",
"ending":"结尾引导那一句","key_points":["全文要点1","全文要点2","全文要点3"]}}""".format(
        pname=p["name"], topic=topic, chosen=outline.get("chosen") or "（大纲未给，按主题自行判断）",
        structure=outline.get("structure") or p["structure"], plan=plan_txt,
        lo=lo, hi=hi, target=int((lo + hi) / 2), sections=max(3, len(secs) or 4))


def build_images_prompt(topic, platform, article, min_n, max_n, ratio):
    """配图方案提示词：自动决定画什么、几张。"""
    p = PLATFORMS.get(platform) or PLATFORMS["wechat"]
    body = (article.get("content") or "").strip()
    if len(body) > 6000:
        body = body[:6000] + "\n…（正文过长，已截断到前 6000 字）"
    titles = re.findall(r"^#{2,4}\s+(.+)$", body, re.M)
    return """请给下面这篇长文出一份**配图方案**，并给每张图写出**可直接提交给文生图模型**的提示词。

文章标题：{title}
目标平台：{pname}（配图比例统一用 {ratio}）
平台建议张数：{min_n}~{max_n} 张（**你按正文实际需要决定**，可以少给；多给的建议不会被采纳）

正文小标题清单：
{titles}

正文（节选）：
{body}

方案要求：
- 每张图要有 `role`，只能是这几个值：{roles}
- 每张图要有 `why`：**这一张解决正文的哪个问题**（写清对应哪一节/哪一句）
- 每张图要有 `prompt`：中文，给文生图模型用。要求：
  - 写清主体、场景、光线、构图、风格；**不要写尺寸数字**（尺寸由 aspect_ratio 参数控制）
  - **不许出现任何文字、字幕、水印、logo 的描述**（文生图模型会把中文字画成乱码）
  - 数据图只许画正文里**真实出现过**的数字，不许自己造数
- `ratio` 一律用 {ratio}
- `count` 字段：你实际给了几张（整数）

只输出一个 JSON 对象，不要输出别的任何东西：
{{"count":3,"images":[{{"role":"cover","why":"对应开头，让读者一眼知道讲什么",
"prompt":"中文出图提示词","ratio":"{ratio}"}}]}}""".format(
        title=article.get("title") or topic, pname=p["name"], ratio=ratio,
        min_n=min_n, max_n=max_n,
        titles="\n".join("- %s" % t for t in titles[:12]) or "（正文里没解析到小标题）",
        body=body, roles=" / ".join(ROLE_CHOICES))


def build_adapt_prompt(topic, platform, article, chars_range):
    """平台适配提示词：把长文改写成指定平台版。"""
    p = PLATFORMS.get(platform) or PLATFORMS["wechat"]
    lo, hi = chars_range
    return """请把下面这篇长文**改写成{pname}版本**（不是复制，是按这个平台的重写）。

原文标题：{title}
原文摘要：{summary}

目标平台规格：
- 篇幅：**{lo}~{hi} 个字符**（不含 Markdown 符号与空白），硬要求
- 结构：{pstructure}
- 平台特性：{pnote}

改写要求：
- 保留原文的**核心观点与事实**，不许新增原文没有的数据、案例与结论
- `title` 按目标平台重写（{pname}的标题要在信息流里 3 秒读懂）
- `content` 是完整的平台版正文，Markdown 格式，从 `## 小标题` 开始
- 结尾必须有引导（关注 / 在看 / 收藏 / 评论 / 转发 之一），且要合这个平台的调性
- 遵守同样的底线：不编数据、不编人名机构、不做效果承诺、不留待补空档
  （`{{}}`、`[待填]`、`XXX`、`（此处省略）` 都不许出现）

原文正文：
{body}

只输出一个 JSON 对象，不要输出别的任何东西：
{{"platform":"{platform}","title":"平台版标题","summary":"平台版摘要",
"content":"平台版正文（Markdown）","ending":"结尾引导那一句",
"changed":["改了什么1","改了什么2"]}}""".format(
        pname=p["name"], title=article.get("title") or topic,
        summary=article.get("summary") or "（原文没给摘要）",
        lo=lo, hi=hi, pstructure=p["structure"], pnote=p["note"],
        platform=platform, body=(article.get("content") or "")[:8000])


# ---------------------------------------------------------------------------
# 产出归一化 + 闸门执行
# ---------------------------------------------------------------------------

def _clean_list(v, limit=None):
    """把模型给的"列表"归一成字符串列表（三种形态都认）。"""
    out = []
    if v is None:
        return out
    items = v if isinstance(v, list) else re.split(r"[\n；;]+", str(v))
    for it in items:
        if isinstance(it, dict):
            it = it.get("text") or it.get("point") or it.get("title") or ""
        s = re.sub(r"\s+", " ", str(it or "")).strip().strip("-·*").strip()
        if s:
            out.append(s)
    if limit:
        out = out[:limit]
    return out


def normalize_outline(obj, topic, platform, angles_wanted=None, sections_wanted=None):
    """把模型返回的大纲收拾成内部结构，并附上本地结构校验结果。"""
    obj = obj if isinstance(obj, dict) else {}
    angles = []
    for ra in (obj.get("angles") or []):
        if isinstance(ra, str):
            ra = {"angle": ra}
        if not isinstance(ra, dict):
            continue
        angles.append({
            "angle": re.sub(r"\s+", " ", str(ra.get("angle") or ra.get("title") or "")).strip(),
            "audience": re.sub(r"\s+", " ", str(ra.get("audience") or "")).strip(),
            "hook": re.sub(r"\s+", " ", str(ra.get("hook") or "")).strip(),
            "why_me": re.sub(r"\s+", " ", str(ra.get("why_me") or ra.get("why") or "")).strip(),
        })
    sections = []
    for si, rs in enumerate((obj.get("sections") or []), 1):
        if isinstance(rs, str):
            rs = {"title": rs}
        if not isinstance(rs, dict):
            continue
        try:
            chars = int(round(float(re.sub(r"[^\d.]", "", str(rs.get("chars") or 0)) or 0)))
        except (TypeError, ValueError):
            chars = 0
        sections.append({
            "no": si,
            "title": re.sub(r"\s+", " ", str(rs.get("title") or rs.get("name") or "")).strip(),
            "chars": chars,
            "points": _clean_list(rs.get("points") or rs.get("outline")),
        })
    p = PLATFORMS.get(platform) or PLATFORMS["wechat"]
    plan = {
        "topic": topic, "platform": platform, "platform_name": p["name"],
        "angles": angles, "angle_count": len(angles),
        "chosen": re.sub(r"\s+", " ", str(obj.get("chosen") or "")).strip(),
        "structure": re.sub(r"\s+", " ", str(obj.get("structure") or "")).strip(),
        "sections": sections, "section_count": len(sections),
        "planned_chars": sum(s["chars"] for s in sections),
        "chars_range": list(p["chars"]),
    }
    checks = outline_checks(plan, angles_wanted, sections_wanted)
    plan["structure_ok"] = all(c["ok"] for c in checks)
    plan["structure_checks"] = checks
    return plan


def outline_checks(plan, angles_wanted=None, sections_wanted=None):
    """闸门五的前半段：大纲结构校验，返回 [{'check','ok','detail'}]。"""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    angles = plan.get("angles") or []
    secs = plan.get("sections") or []
    lo, hi = plan.get("chars_range") or LONGFORM_CHARS

    add("有选题角度", len(angles) >= 2,
        "解析出 %d 个角度" % len(angles) if len(angles) >= 2
        else "只解析出 %d 个角度（至少要有 2 个才叫选题）" % len(angles))
    if angles_wanted:
        add("角度数符合 --angles", len(angles) == angles_wanted,
            "实际 %d 个 / 期望 %d 个" % (len(angles), angles_wanted))
    empty_angle = ["#%d" % (i + 1) for i, a in enumerate(angles)
                   if not a["angle"] or len(a["angle"]) < 6]
    add("角度不是空话", not empty_angle,
        "每个角度都写了切面" if not empty_angle
        else "第 %s 个角度没写清切面（少于 6 个字等于没说）" % "、".join(empty_angle))
    no_hook = ["#%d" % (i + 1) for i, a in enumerate(angles) if not a["hook"]]
    add("每个角度有钩子", not no_hook,
        "每个角度都写了为什么点开" if not no_hook
        else "第 %s 个角度没写 hook（读者凭什么点开）" % "、".join(no_hook))

    add("选定了唯一角度", bool(plan.get("chosen")),
        "选中：%s" % plan["chosen"][:40] if plan.get("chosen")
        else "没给 chosen 字段（模型没说最后要写哪个角度）")

    add("有分节", len(secs) >= 3,
        "解析出 %d 个分节" % len(secs) if len(secs) >= 3
        else "只解析出 %d 个分节（长文至少要 3 节）" % len(secs))
    if sections_wanted:
        add("分节数符合 --sections", len(secs) == sections_wanted,
            "实际 %d 节 / 期望 %d 节" % (len(secs), sections_wanted))
    no_title = ["#%d" % s["no"] for s in secs if not s["title"]]
    add("每节都有小标题", not no_title,
        "全部小节都有小标题" if not no_title else "缺标题：%s" % "、".join(no_title))
    no_points = ["#%d" % s["no"] for s in secs if not s["points"]]
    add("每节都有要点", not no_points,
        "全部小节都有要点" if not no_points
        else "第 %s 节没给 points（这一节要讲什么没定下来）" % "、".join(no_points))
    zero_chars = ["#%d" % s["no"] for s in secs if s["chars"] <= 0]
    add("每节都有正数计划字数", not zero_chars,
        "计划合计 %d 字" % plan.get("planned_chars", 0) if not zero_chars
        else "第 %s 节计划字数为 0" % "、".join(zero_chars))
    total = plan.get("planned_chars", 0)
    add("计划字数落在平台区间", lo <= total <= hi,
        "合计 %d 字，落在区间 %d~%d 内" % (total, lo, hi) if lo <= total <= hi
        else "合计 %d 字，不在%s区间 %d~%d 内" % (total, plan.get("platform_name", ""), lo, hi))
    return checks


def normalize_article(obj, platform="wechat", chars_range=None, trust_chars=None,
                      where="正文"):
    """收拾正文返回，跑闸门，返回内部结构。

    两种输入形态都认（**实测踩过这个坑**）：
      · 模型原始返回 `{"title":…,"content":…}`
      · 本包 `write --json --out` 存下来的信封 `{"ok":…,"article":{…}}`
    一开始只认第一种，结果 `write --from-file <自己 --out 的文件>` 解析出 0 字，
    闸门报「正文为空」——**自己产出的文件自己读不了**。所以这里先拆一层信封。
    """
    obj = unwrap_model_output(obj)
    if isinstance(obj, str):
        obj = {"content": obj}
    obj = obj if isinstance(obj, dict) else {}
    title = re.sub(r"\s+", " ", str(obj.get("title") or "")).strip()
    summary = re.sub(r"\s+", " ", str(obj.get("summary") or "")).strip()
    content = str(obj.get("content") or obj.get("text") or obj.get("body") or "").strip()
    ending = re.sub(r"\s+", " ", str(obj.get("ending") or "")).strip()
    leaks = []
    if not content:
        leaks.append({"kind": "empty", "why": "模型没返回正文（content 为空）"})
    for h in compliance_scan("\n".join([title, summary, content, ending])):
        leaks.append({"kind": "banned_word",
                      "why": "命中违禁词「%s」（%s风险）：%s" % (h["word"], h["level"], h["why"])})
    for h in placeholder_hits("\n".join([title, summary, content, ending])):
        leaks.append({"kind": "placeholder", "why": h["why"]})
    leaks.extend(echo_hits(title, "标题"))
    leaks.extend(echo_hits(content[:1200], "正文开头"))
    checks = structure_checks(None, title=title, content=content,
                              platform=platform, ending=ending)
    for c in checks:
        if not c["ok"]:
            leaks.append({"kind": "structure", "why": "%s：%s" % (c["check"], c["detail"])})
    lo, hi = chars_range or PLATFORMS.get(platform or "wechat", PLATFORMS["wechat"])["chars"]
    n = count_chars(content) if trust_chars is None else int(trust_chars)
    length_ok = lo <= n <= hi
    if content and not length_ok:
        leaks.append({"kind": "length",
                      "why": "正文 %d 字，不在要求的 %d~%d 字区间（%s）"
                             % (n, lo, hi, "偏短，内容撑不起来" if n < lo else
                                "偏长，平台会折叠或截断；脚本不会替你截断")})
    return {"platform": platform, "platform_name": _plat_name(platform),
            "title": title, "summary": summary, "content": content, "ending": ending,
            "key_points": _clean_list(obj.get("key_points")),
            "changed": _clean_list(obj.get("changed")),
            "chars": n, "cjk": count_cjk(content), "chars_range": [lo, hi],
            "length_ok": length_ok, "structure_checks": checks,
            "leaks": leaks, "ok": not leaks}


def prompt_gate(prompt):
    """出图提示词过闸门二/三（占位符 + 照抄示例）。返回 [(kind, why)]。"""
    leaks = []
    for h in placeholder_hits(prompt or ""):
        leaks.append((h["kind"], h["why"]))
    for h in compliance_scan(prompt or ""):
        leaks.append(("banned_word", "出图提示词命中违禁词「%s」：%s" % (h["word"], h["why"])))
    echoed, score, sample, rule = prompt_echo(prompt or "")
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


def normalize_image_plan(obj, platform, min_n, max_n, ratio, warning_only=True,
                         resolution="1K"):
    """收拾配图方案，跑闸门，返回内部结构。

    张数是**建议档**：多了少了都给 notice（不判失败），因为"多画一张"属创作自由。
    但如果一张都没有，那就是硬失败。

    `resolution` 从 `--resolution` 传进来落到每个 item 上（**不要再写死 "1K"**）：
    写死会让 `--resolution 4K` 静默变成 1K —— 参数被解析了却从不生效，
    用户以为自己拿了 4K。`submit_image()` 只吃 item 上的这个值，
    所以它也是出图断点 key 里 `resolution` 那一维的来源，两处必须同一个数。
    """
    obj = obj if isinstance(obj, dict) else {}
    raw = obj.get("images") or obj.get("items") or []
    items, leaks, notices = [], [], []
    for i, ri in enumerate(raw, 1):
        if isinstance(ri, str):
            ri = {"prompt": ri}
        if not isinstance(ri, dict):
            continue
        role = str(ri.get("role") or "scene").strip().lower()
        if role not in ROLE_CHOICES:
            role = "scene"
        pr = str(ri.get("prompt") or "").strip()
        it = {"id": i, "role": role, "role_note": IMAGE_ROLES[role],
              "why": re.sub(r"\s+", " ", str(ri.get("why") or "")).strip(),
              "prompt": pr, "aspect_ratio": ratio, "resolution": resolution,
              "platform": platform}
        it["leaks"] = [(k, w) for k, w in prompt_gate(pr)]
        if not pr:
            it["leaks"].append(("empty", "第 %d 张图没有出图提示词" % i))
        leaks.extend([{"kind": k, "why": "第 %d 张（%s）：%s" % (i, role, w)}
                      for k, w in it["leaks"]])
        items.append(it)
    if not items:
        leaks.append({"kind": "empty", "why": "模型没返回任何配图条目"})
    n = len(items)
    if n and n < min_n:
        notices.append("只给了 %d 张，低于平台建议下限 %d 张（不判失败，但正文可能缺图）"
                       % (n, min_n))
    if n > max_n:
        notices.append("给了 %d 张，超过平台建议上限 %d 张（脚本只按实际张数计费，"
                       "多出来的自己决定要不要" % (n, max_n))
    return {"platform": platform, "platform_name": _plat_name(platform),
            "count": n, "suggested": [min_n, max_n], "ratio": ratio,
            "items": items, "notices": notices,
            "leaks": leaks, "ok": not leaks}


# ---------------------------------------------------------------------------
# 断点续跑（`all` 用）
# ---------------------------------------------------------------------------

def state_path(outdir):
    return Path(outdir) / STATE_NAME


def load_state(outdir):
    p = state_path(outdir)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            sys.stderr.write("断点文件损坏，按空状态重跑：%s\n" % p)
    return {}


def save_state(outdir, state):
    p = state_path(outdir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def state_key(stage, name=""):
    return "%s:%s" % (stage, name) if name else stage


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "✗ " + s
    return "\x1b[31m%s\x1b[0m" % s


def render_outline_md(plan, model=None, usage=None, elapsed=None):
    out = ["# 长文大纲 · %s" % plan["topic"], ""]
    out.append("- 目标平台：%s（正文区间 %d~%d 字）"
               % (plan["platform_name"], plan["chars_range"][0], plan["chars_range"][1]))
    out.append("- 分节：%d 节 / 计划合计 %d 字" % (plan["section_count"], plan["planned_chars"]))
    if model:
        out.append("- 模型：`%s`　命令端点：`POST /api/v1/chat/completions`" % model)
    if usage:
        out.append("- token 用量：prompt=%s completion=%s total=%s" % (
            usage.get("prompt_tokens", "-"), usage.get("completion_tokens", "-"),
            usage.get("total_tokens", "-")))
    if elapsed is not None:
        out.append("- 耗时：%.1fs" % elapsed)
    out.append("")
    out.append("## 选题角度（%d 个）" % plan["angle_count"])
    out.append("")
    out.append("| # | 角度 | 写给谁 | 为什么点开 | 凭什么站得住 |")
    out.append("|---|---|---|---|---|")
    for i, a in enumerate(plan["angles"], 1):
        out.append("| %d | %s | %s | %s | %s |" % (
            i, a["angle"] or "（缺）", a["audience"] or "（缺）",
            a["hook"] or "（缺）", a["why_me"] or "（缺）"))
    out.append("")
    if plan.get("chosen"):
        out.append("> **选定角度**：%s" % plan["chosen"])
        out.append("")
    if plan.get("structure"):
        out.append("> **行文骨架**：%s" % plan["structure"])
        out.append("")
    out.append("## 分节大纲")
    out.append("")
    out.append("| 节 | 小标题 | 计划字数 | 要点 |")
    out.append("|---|---|---|---|")
    for s in plan["sections"]:
        pts = "<br>".join("· " + x for x in s["points"]) or "（缺）"
        out.append("| %d | %s | %s | %s |" % (s["no"], s["title"] or "（缺标题）",
                                              s["chars"], pts))
    out.append("")
    return "\n".join(out)


def render_article_md(art):
    out = ["# %s" % (art["title"] or "（无标题）"), ""]
    if art.get("summary"):
        out.append("> %s" % art["summary"])
        out.append("")
    out.append(art["content"] or "（正文为空）")
    out.append("")
    if art["leaks"]:
        out.append("### 本地自检命中")
        out.append("")
        for lk in art["leaks"]:
            out.append("- %s：%s" % (lk["kind"], lk["why"]))
        out.append("")
    return "\n".join(out)


def render_audit_md(audit):
    out = ["# 长文生产质检报告", ""]
    out.append("> 本地确定性判定（模型自评不参与）。命中项一律拦截，退出码非 0。")
    out.append("")
    if audit["ok"]:
        out.append("✅ 全部 **%d** 个受检对象通过八道闸门。" % audit["checked"])
    else:
        out.append("⚠️ %d 个受检对象中 **%d** 个命中闸门，必须人工复核后才能发布。"
                   % (audit["checked"], len(audit["failures"])))
    out.append("")
    if audit["failures"]:
        out.append("| 对象 | 命中类型 | 说明 |")
        out.append("|---|---|---|")
        for f in audit["failures"]:
            for lk in f["leaks"]:
                out.append("| %s | %s | %s |" % (f["no"], lk["kind"], lk["why"]))
        out.append("")
    if audit.get("structure_checks"):
        out.append("## 大纲结构校验")
        out.append("")
        out.append("| 检查项 | 结果 | 详情 |")
        out.append("|---|---|---|")
        for c in audit["structure_checks"]:
            out.append("| %s | %s | %s |" % (c["check"], "✅" if c["ok"] else "❌", c["detail"]))
        out.append("")
    if audit.get("images"):
        out.append("## 配图（真实像素 vs 请求比例）")
        out.append("")
        out.append("| # | 角色 | 请求比例 | 真实像素 | 实得比例 | 偏差 | 结论 |")
        out.append("|---|---|---|---|---|---|---|")
        for im in audit["images"]:
            out.append("| %s | %s | %s | %sx%s | %s | %s | %s |" % (
                im.get("id"), im.get("role"), im.get("want_ratio"),
                (im.get("real_px") or ["?", "?"])[0], (im.get("real_px") or ["?", "?"])[1],
                im.get("real_label"),
                ("%.2f%%" % (im["deviation"] * 100)) if im.get("deviation") is not None else "-",
                "✅" if im.get("ratio_ok") else "❌"))
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封（已经吐过结果的，ok 写在那个结果里）
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
# ---------------------------------------------------------------------------

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None,
         "pending": None}

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


def _json_stdout():
    return _JSON["stdout"] or sys.stdout


def _json_write(text):
    """把 JSON 文本写到**真 stdout** 并记账。**只允许被调用一次。**"""
    _json_stdout().write(text + "\n")
    _JSON["emitted"] = True


def _json_want(a=None):
    if a is not None:
        return bool(getattr(a, "json", False))
    return bool(_JSON["want"])


def _stage_json(obj, out=None, indent=1, ok=True):
    """**暂存**一份要写的 JSON，不落盘、不写 stdout。

    为什么要暂存而不是立刻写：`_emit` / `_json_out` 在命令函数里被调用时只能给出
    `ok=not bad`，**还不知道最终退出码**（退出码是 `_main` 兜住异常之后才定下来的）。
    如果这里就写出去，`_main` 发现 rc != 0 再想补 `error` 字段，就只能**在同一个
    stdout 上再写一份**——实测立刻变成两个 JSON 文档，`json.loads` 直接失败。
    所以真正的写出统一推迟到 `_flush_json()`，由 `_main` 在 rc 定下来之后调一次。
    """
    _JSON["pending"] = {"obj": obj, "out": out, "indent": indent, "ok": bool(ok)}
    return True


def _flush_json(rc=0, kind=None, message=None, detail=None):
    """把暂存的 JSON 写到真 stdout（顺带落 `--out`）。**全程只写一次。**

    最终 ok = (rc == 0)；rc != 0 时并入 `exit` 与 `error` 信封字段，
    这样「结果主体」与「错误信封」两种消费姿势用同一份输出都能判失败。
    """
    pending = _JSON["pending"]
    if not pending:
        return False
    obj, out = pending["obj"], pending["out"]
    indent = pending["indent"]
    if rc:
        k = kind or _KIND_BY_EXIT.get(rc, "gate")
        m = message or "命令以退出码 %s 结束（人读原因见 stderr）" % rc
        body = _result_with_error(obj, k, m, detail, indent, rc=rc)
    else:
        ok = pending["ok"]
        body = _json_text(obj, indent=indent, ok=ok)
    _JSON["pending"] = None
    if out:
        try:
            p = Path(out)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 %s\n" % out)
        except OSError as exc:
            sys.stderr.write("写 --out 失败：%s\n" % exc)
    _json_write(body)
    return True


def _json_out(obj, a=None, indent=1, ok=True):
    """`--json` 模式的结果出口（`cost` / `all` / `images` 收尾用）。返回是否已暂存。

    ⚠️ 走的是**暂存**（见 `_stage_json` 的说明），不是立刻写 stdout；
    真正写出在 `_main` 的 `_flush_json()`。`--out` 也由那里统一落盘，
    所以不会再出现「`images --json --out x.json` 跑完 x.json 是空的」那种事
    （一开始 `_json_out` 这条路径漏了 `--out`，实测踩到）。
    """
    if not _json_want(a):
        return False
    if _JSON["pending"] is not None:
        # 同一进程里第二次暂存 = 代码 bug（会覆盖前一份、丢产出），**如实报出来**
        sys.stderr.write("内部错误：一次运行里暂存了两份 JSON 结果（后一份覆盖前一份），"
                         "这是脚本 bug，请连同命令一起反馈。\n")
    return _stage_json(obj, getattr(a, "out", None) if a is not None else None,
                       indent=indent, ok=ok)


def _json_fail(rc, kind=None, message=None, detail=None, a=None):
    """`--json` 模式的失败出口：**只在本次没有任何结果要写时**才发独立信封。"""
    if _JSON["emitted"] or _JSON["pending"] is not None or not _json_want(a):
        return
    err = {"kind": kind or _KIND_BY_EXIT.get(rc, "call"),
           "message": message or "命令以退出码 %s 结束（人读原因见 stderr）" % rc}
    if detail is not None:
        err["detail"] = detail
    _json_write(json.dumps({"ok": False, "exit": rc, "error": err},
                           ensure_ascii=False, indent=1))


def _json_internal(exc):
    """未预料异常的兜底信封 —— **报 bug，不藏 bug**。"""
    if _JSON["emitted"]:
        return
    _JSON["pending"] = None          # 未预料异常：丢掉半成品结果，只发兜底信封
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


def _emit(a, text, json_obj=None, ok=True):
    """统一出口。

    `--json` 且给了 `json_obj` 时：**暂存**（补 ok 后序列化，最终由 `_main` 落
    stdout 与 `--out`）；否则原样输出 text（非 JSON 模式的输出与改动前逐字节一致）。
    """
    if json_obj is not None and getattr(a, "json", False):
        _json_out(json_obj, a, indent=1, ok=ok)
        return
    if getattr(a, "out", None):
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 %s\n" % a.out)
    print(text)


def _result_with_error(json_obj, kind, message, detail=None, indent=1, rc=None):
    """结果主体 + `error` / `exit` 信封字段，`ok` 如实为 false。

    **为什么不是另发一个信封文档**：stdout 只许有一个 JSON 文档，而结果主体
    （正文、逐条闸门命中原因、配图真实像素）恰恰是失败时最需要机读的东西。
    所以不再多发一个文档，而是把错误**并入**结果主体；`_json_fail` 只在
    「本次没有任何结果」时才发那个独立信封。

    并入时补齐 `exit`，让「结果主体」与「错误信封」两套消费姿势都能只靠
    `ok` / `exit` / `error` 三个字段判失败，不必先猜这次是哪一种输出。
    """
    obj = dict(json_obj) if isinstance(json_obj, dict) else {"data": json_obj}
    obj["error"] = {"kind": kind, "message": message}
    if detail is not None:
        obj["error"]["detail"] = detail
    if rc is not None:
        obj["exit"] = rc
    return json.dumps(_json_payload(obj, False), ensure_ascii=False, indent=indent)


# ---------------------------------------------------------------------------
# 闸门八：`--outdir` 不许落在包内
#
# 为什么单独做一道闸门而不是"提示一下"：Skill 包的上传白名单只收
# `.md .py .txt .json .sh .js .yaml .yml .csv`，包内塞一张 png 会让上传直接 400。
# 出图是**写操作**，写进去之前就要拦住，不能等用户打完卡再回滚。
# 退出码 2（usage）：这是用法错误，不是闸门判定，也不是上游失败。
# ---------------------------------------------------------------------------

def ensure_outside_pkg(outdir):
    """`--outdir` 在包内 → 抛 LongformGate(exit=2 由调用方转)。"""
    pkg_dir = Path(__file__).resolve().parent.parent
    try:
        Path(outdir).resolve().relative_to(pkg_dir)
    except ValueError:
        return
    raise PackagePathError(
        "输出目录 %s 在 Skill 包内（%s）。包内不许有任何图片——上传白名单只收文本，"
        "请换到包外，例如 %s"
        % (Path(outdir).resolve(), pkg_dir,
           Path(os.environ.get("TEMP") or ".") / "longform-out"))


class PackagePathError(LongformError):
    """用法错误：产出路径落在包内（退出码 2）。"""


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def _load_json_file(path, what):
    p = Path(path)
    if not p.is_file():
        raise LongformError("找不到%s文件：%s" % (what, path))
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))


def unwrap_model_output(obj):
    """把「模型原始返回」与「本包 `--json --out` 存下来的信封」统一成模型原始返回。

    **这个函数存在的原因是实测踩过三次同一个坑**：`write --from-file`、
    `adapt --from-file`、`normalize_article` 一开始都只认模型原始返回
    `{"title":…,"content":…}`，于是「拿本包自己 `--out` 出来的文件做闸门复检」
    会解析出 0 字、闸门报「正文为空」——**自己产出的文件自己读不了**。
    三种信封形态都在这一个地方拆：`{"article":…}` / `{"articles":[…][0]}` / 裸对象。
    """
    if not isinstance(obj, dict):
        return obj
    if obj.get("content") or obj.get("text") or obj.get("body"):
        return obj
    if isinstance(obj.get("article"), dict):
        return obj["article"]
    arts = obj.get("articles")
    if isinstance(arts, list) and arts and isinstance(arts[0], dict):
        return arts[0]
    return obj


def declared_chars(obj):
    """读**产出侧**声明的字数（`article.chars`）。

    ⚠️ 只用于**故意喂坏数据**的闸门自检：正常路径下 `trust_chars=None`，
    字数一律由本脚本数 Markdown 符号与空白（`count_chars`），这是唯一可信口径。
    传 `--trust-chars` 时本脚本采信产出侧声明值 —— 这正好是「闸门假绿」的反例，
    用它就能演示「声明 4000 字、真实只有几十字」会被抓出来。
    """
    if not isinstance(obj, dict):
        return None
    for k in ("chars", "char_count", "word_count"):
        v = obj.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    a = obj.get("article")
    if isinstance(a, dict):
        return declared_chars(a)
    return None


def _require_outline(a):
    obj = _load_json_file(a.outline, "大纲")
    plan = obj.get("outline") if isinstance(obj, dict) and "outline" in obj else obj
    if not isinstance(plan, dict) or not plan.get("sections"):
        raise LongformError("大纲文件里没有 sections：%s（先用 `outline` 生成）" % a.outline)
    return _revalidate_outline(plan, a.outline)


def _revalidate_outline(plan, where):
    """大纲是 JSON 文件，**手工改坏它是最容易被忽略的失败入口**。

    拿一份结构残缺的大纲去写正文，等于把错误放大到几千字。所以 write / images /
    adapt 在载入大纲时会重新跑一遍结构校验，不合格直接返回退出码 3。
    """
    for s in plan.get("sections") or []:
        s.setdefault("points", [])
        s.setdefault("chars", 0)
        s.setdefault("no", 0)
    plan["section_count"] = len(plan.get("sections") or [])
    plan["planned_chars"] = sum(s.get("chars") or 0 for s in plan["sections"])
    plan.setdefault("chars_range", list(
        PLATFORMS.get(plan.get("platform") or "wechat", PLATFORMS["wechat"])["chars"]))
    checks = outline_checks(plan)
    bad = [c for c in checks if not c["ok"]]
    if bad:
        for c in bad:
            sys.stderr.write("   %s ✗ %s\n" % (c["check"], c["detail"]))
        raise LongformGate(
            "闸门五：%s 的大纲结构校验未通过（%d 项），先修大纲再写正文" % (where, len(bad)))
    plan["structure_checks"] = checks
    plan["structure_ok"] = True
    return plan


def _require_article(a):
    obj = _load_json_file(a.article, "正文")
    art = obj.get("article") if isinstance(obj, dict) and "article" in obj else obj
    if not isinstance(art, dict) or not (art.get("content") or "").strip():
        raise LongformError("正文文件里没有 content：%s（先用 `write` 生成）" % a.article)
    return art


def cmd_outline(a):
    if not (a.topic or "").strip():
        raise LongformError('请用 --topic 给一个主题，例如 --topic "短视频批量出片"')
    prompt = build_outline_prompt(a.topic, a.platform, a.angles, a.sections,
                                 a.audience, a.requirements, a.tone)
    if a.dry_run:
        _dry_run_json(a, topic=a.topic, platform=a.platform, user=prompt)
        return 0
    sys.stderr.write("正在用 `%s` 出选题角度 + 大纲（%s / %d 节）…\n"
                     % (a.model, PLATFORMS[a.platform]["name"], a.sections))
    tracker = CostTracker(a.budget, a.yuan_per_ktok)
    if tracker.over_budget(EST_TOKENS["outline"]["prompt"] + EST_TOKENS["outline"]["completion"]):
        sys.stderr.write("\n%s\n" % _red(
            "预估成本已超 --budget %g 元，未发起任何调用" % a.budget))
        return _fail(3, "budget", "预估成本已超 --budget %g 元，未发起任何调用" % a.budget)
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                          max_tokens=a.max_tokens, key=a.key,
                          json_mode=not a.no_json_mode,
                          tracker=tracker, tracker_label="outline")
    elapsed = time.time() - t0
    plan = normalize_outline(parse_first_json(content), a.topic, a.platform, a.angles, a.sections)
    if not plan["sections"]:
        raise LongformError("模型返回里没有 sections，大纲是空的（可加大 --max-tokens 或换模型）")
    result = {"outline": plan, "model": a.model, "usage": usage,
              "elapsed_sec": round(elapsed, 1),
              "cost": text_cost_record(tracker.calls, tracker.prompt_tokens,
                                       tracker.completion_tokens, a.yuan_per_ktok,
                                       tracker.estimated_flags)}
    _emit(a, render_outline_md(plan, a.model, usage, elapsed), json_obj=result,
          ok=plan["structure_ok"])
    sys.stderr.write("usage: %s\n" % json.dumps(usage, ensure_ascii=False))
    sys.stderr.write("%s\n" % tracker.line())
    return _report_gates(plan["structure_checks"], plan["structure_ok"],
                         "闸门五：大纲结构校验未通过（缺角度 / 缺钩子 / 缺分节 / 计划字数越界），已标红")


def _report_gates(checks, ok, msg):
    """把结构校验结果打到 stderr 并在失败时返回退出码 3。"""
    bad = [c for c in checks if not c["ok"]]
    for c in bad:
        sys.stderr.write("   %s %s：%s\n" % (c["check"], "✗", c["detail"]))
    if bad and not ok:
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(3, "gate", "闸门五：结构校验未通过（%d 项）" % len(bad))
    return 0


def cmd_write(a):
    plan = _require_outline(a)
    platform = plan.get("platform") or a.platform
    chars_range = plan.get("chars_range")
    if a.from_file:
        raw = Path(a.from_file).read_text(encoding="utf-8", errors="replace")
        obj = unwrap_model_output(parse_first_json(raw))
        trust = declared_chars(parse_first_json(raw)) if getattr(a, "trust_chars", False) else None
        art = normalize_article(obj, platform, chars_range, trust_chars=trust)
        _emit_article(a, plan, art, None, None)
        return 0 if art["ok"] else _fail(3, "gate", "闸门：正文命中（%d 项）" % len(art["leaks"]))
    prompt = build_write_prompt(plan.get("topic") or a.topic or "", platform, plan, chars_range)
    if a.dry_run:
        _dry_run_json(a, topic=plan.get("topic"), platform=platform, user=prompt)
        return 0
    tracker = CostTracker(a.budget, a.yuan_per_ktok)
    est = EST_TOKENS["write"]
    if tracker.over_budget(est["prompt"] + est["completion"]):
        sys.stderr.write("\n%s\n" % _red(
            "预估成本已超 --budget %g 元，一个字都没写" % a.budget))
        return _fail(3, "budget", "预估成本已超 --budget %g 元，一个字都没写" % a.budget)
    sys.stderr.write("正在用 `%s` 写正文（%s，目标 %d~%d 字）…\n"
                     % (a.model, _plat_name(platform),
                        (chars_range or LONGFORM_CHARS)[0], (chars_range or LONGFORM_CHARS)[1]))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                          max_tokens=a.max_tokens, key=a.key,
                          json_mode=not a.no_json_mode,
                          tracker=tracker, tracker_label="write")
    elapsed = time.time() - t0
    art = normalize_article(parse_first_json(content), platform, chars_range)
    art["elapsed_sec"] = round(elapsed, 1)
    art["usage"] = usage
    art["topic"] = plan.get("topic") or a.topic
    art["chosen"] = plan.get("chosen")
    sys.stderr.write("      %d 字 · %.1fs · usage %s\n"
                     % (art["chars"], elapsed, json.dumps(usage, ensure_ascii=False)))
    return _emit_article(a, plan, art, tracker, usage)


def _emit_article(a, plan, art, tracker, usage):
    bad = not art["ok"]
    result = {"topic": plan.get("topic"), "platform": art["platform"],
              "model": a.model, "article": art, "usage": usage,
              "gate_failures": [lk["why"] for lk in art["leaks"]]}
    if tracker is not None:
        result["cost"] = text_cost_record(tracker.calls, tracker.prompt_tokens,
                                          tracker.completion_tokens,
                                          tracker.rate, tracker.estimated_flags)
    _emit(a, render_article_md(art), json_obj=result, ok=not bad)
    if bad:
        sys.stderr.write("\n%s\n" % _red(
            "闸门：正文命中（违禁词 / 占位符 / 照抄示例 / 字数越界 / 结构残缺），"
            "不可直接发布：" % ()))
        for lk in art["leaks"]:
            sys.stderr.write("   %s ← %s\n" % (lk["kind"], lk["why"]))
        if tracker:
            sys.stderr.write("%s\n" % tracker.line())
        return _fail(3, "gate", "闸门：正文命中（违禁词/占位符/照抄示例/字数越界/结构残缺）")
    if tracker:
        sys.stderr.write("%s\n" % tracker.line())
    return 0


def cmd_images(a):
    platform = a.platform
    ratio = a.ratio or PLATFORMS[platform]["ratio"]
    min_n, max_n = PLATFORMS[platform]["images"]
    if a.count:
        max_n = a.count

    # ---- 报价阶段：先把方案拿到（文本调用，便宜），再报价，再出图 ----
    plan_obj = None
    if a.from_file:
        plan_obj = normalize_image_plan(parse_first_json(
            Path(a.from_file).read_text(encoding="utf-8", errors="replace")),
            platform, min_n, max_n, ratio, resolution=a.resolution)
    else:
        if not getattr(a, "article", None):
            raise LongformError("请用 --article 给正文文件（`write --json --out` 的产出），"
                                "或用 --from-file 直接过闸门")
        art = _require_article(a)
        content = art.get("content") or ""
        # 闸门一/二/三：正文先扫一遍，正文不合格就别基于它配图
        pre = []
        for h in compliance_scan("\n".join([art.get("title") or "", content])):
            pre.append({"kind": "banned_word",
                        "why": "正文命中违禁词「%s」：%s" % (h["word"], h["why"])})
        for h in placeholder_hits(content):
            pre.append({"kind": "placeholder", "why": "正文%s" % h["why"]})
        if pre and not a.allow_article_hits:
            for lk in pre:
                sys.stderr.write("   %s\n" % _red("%s：%s" % (lk["kind"], lk["why"])))
            sys.stderr.write("\n%s\n" % _red(
                "正文自身命中闸门，**已拦截，未提交任何出图任务**（不花一分钱）。"
                "先修正文，或加 --allow-article-hits 强行继续。"))
            return _fail(3, "gate", "正文命中本地闸门，已拦截、未提交任何任务")
        prompt = build_images_prompt(plan_obj.get("topic") if plan_obj else (a.topic or ""),
                                     platform, art, min_n, max_n, ratio)
        if a.dry_run:
            _dry_run_json(a, platform=platform, ratio=ratio, user=prompt)
            return 0
        tracker = CostTracker(a.budget, a.yuan_per_ktok)
        if tracker.over_budget(EST_TOKENS["images"]["prompt"] + EST_TOKENS["images"]["completion"]):
            sys.stderr.write("\n%s\n" % _red(
                "预估成本已超 --budget %g 元，未发起任何调用" % a.budget))
            return _fail(3, "budget", "预估成本已超 --budget %g 元，未发起任何调用" % a.budget)
        sys.stderr.write("正在用 `%s` 出配图方案（%s，建议 %d~%d 张）…\n"
                         % (a.model, _plat_name(platform), min_n, max_n))
        content_json, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                                   temperature=a.temperature, max_tokens=a.max_tokens,
                                   key=a.key, json_mode=not a.no_json_mode,
                                   tracker=tracker, tracker_label="images")
        plan_obj = normalize_image_plan(parse_first_json(content_json),
                                        platform, min_n, max_n, ratio,
                                        resolution=a.resolution)
        plan_obj["usage"] = usage
        plan_obj["cost_text"] = text_cost_record(tracker.calls, tracker.prompt_tokens,
                                                 tracker.completion_tokens, tracker.rate,
                                                 tracker.estimated_flags)
        sys.stderr.write("      %d 张 · usage %s\n"
                         % (plan_obj["count"], json.dumps(usage, ensure_ascii=False)))

    if not plan_obj["items"]:
        raise LongformError("配图方案是空的（可加大 --max-tokens 或换模型）")

    # ---- 张数收口：--count 是真闸门（少花钱），平台建议档只是建议 ----
    if a.count and len(plan_obj["items"]) > a.count:
        plan_obj["items"] = plan_obj["items"][:a.count]
        plan_obj["count"] = len(plan_obj["items"])
        plan_obj["notices"].append("按 --count %d 截断到前 %d 张" % (a.count, a.count))

    # ---- 出图前的闸门：提示词自检 ----
    blocked = [it for it in plan_obj["items"] if it["leaks"]]
    if blocked and not a.allow_prompt_hits:
        for it in blocked:
            sys.stderr.write("!! #%s（%s）出图提示词命中闸门：\n" % (it["id"], it["role"]))
            for kind, why in it["leaks"]:
                sys.stderr.write("     %s\n" % _red("%s：%s" % (kind, why)))
        sys.stderr.write(
            "\n共 %d 张被判不合格，**已拦截，未提交任何任务**（不花一分钱）。\n"
            "改掉提示词后重跑；确实要带这些词出图才加 --allow-prompt-hits。\n" % len(blocked))
        return _fail(3, "gate", "有出图提示词命中本地闸门，已拦截、未提交任何任务")

    # ---- 闸门八：输出目录不许在包内 ----
    try:
        ensure_outside_pkg(a.outdir)
    except PackagePathError as exc:
        sys.stderr.write("\n%s\n" % _red(str(exc)))
        return _fail(2, "usage", str(exc))

    outdir = Path(a.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    spath = a.state or str(outdir / STATE_NAME)

    # ---- 闸门七：先报价，再要 --yes ----
    cost = image_cost(len(plan_obj["items"]), a.resolution, a.points_per_image)
    _print_image_plan(plan_obj, outdir, a.points_per_image)
    _print_quote(plan_obj, cost, a)
    # `--local-image`：用一张本地图代替真实出图。
    # **为什么不给生产路径留这个开关**：它不出网、不花钱，只做**比例闸门自检**——
    # 需要演示「接口自报 16:9、真实像素却不是」这种假绿时，拿任意一张已知像素的图
    # 走完整的「读文件头 → 算偏差 → 判容差」链路即可，不必真花钱造一张错图。
    if getattr(a, "local_image", None):
        src = Path(a.local_image)
        if not src.is_file():
            raise LongformError("--local-image 找不到文件：%s" % src)
        dest = outdir / ("local-%s%s" % (src.stem, src.suffix or OUT_EXT))
        dest.write_bytes(src.read_bytes())
        it = plan_obj["items"][0]
        chk = check_ratio(str(dest), it["aspect_ratio"], a.ratio_tolerance)
        payload = {"ok": bool(chk["ok"]), "local_image": True, "file": str(dest),
                   "id": it["id"], "want_ratio": it["aspect_ratio"],
                   "role": it["role"], "first_check": chk,
                   "real_px": chk["real_px"], "real_ratio": chk.get("real_ratio"),
                   "real_label": chk.get("real_label"), "deviation": chk.get("deviation"),
                   "points_cost": 0, "note": "--local-image：本地复检，未提交任务、未扣费"}
        _stage_json(payload, getattr(a, "out", None), indent=1, ok=bool(chk["ok"]))
        if not a.json:
            print("本地复检（未提交任务、未扣费）：%s" % dest)
            print("  " + (chk["why"] if chk["ok"] else _red(chk["why"])))
        if not chk["ok"]:
            return _fail(3, "gate", chk.get("why") or "真实像素与请求比例不符")
        return 0
    if cost.get("total_points") is None:
        sys.stderr.write("\n%s\n" % _red(
            "没有可信单价（只有 1K 有实测价），拒绝盲跑。"
            "用 --points-per-image <点数> 指定单价后重试。"))
        return _fail(3, "budget", "没有实测单价，拒绝凭猜估算")
    if a.budget is not None and cost["total_points"] > a.budget:
        sys.stderr.write("\n%s\n" % _red(
            "预估 %g 点超过预算上限 %g 点，**已中断，未提交任何任务**。"
            % (cost["total_points"], a.budget)))
        return _fail(3, "budget", "预估 %g 点超过 --budget 上限 %g 点，未提交任何任务"
                     % (cost["total_points"], a.budget))
    if not a.yes:
        sys.stderr.write("\n这是一次**真花钱**的操作（约 %.2f 元 / %g 点）。"
                         "确认后加 --yes 重跑。\n"
                         % (cost["total_yuan"] or 0, cost["total_points"] or 0))
        return _fail(4, "usage", "这是一次真花钱的操作，确认后加 --yes 重跑")

    return _run_images(a, plan_obj, outdir, spath, cost)


def _print_image_plan(plan_obj, outdir, override):
    print("配图方案（%s，比例 %s）" % (plan_obj["platform_name"], plan_obj["ratio"]))
    print("  输出目录：%s  （**必须不在 Skill 包内**）" % outdir)
    for it in plan_obj["items"]:
        print("  #%s [%s] %s" % (it["id"], it["role"], it["why"] or "（没写对应哪一节）"))
        print("      %s" % it["prompt"])
    for n in plan_obj["notices"]:
        print("  注意：%s" % n)
    print("")


def _print_quote(plan_obj, cost, a):
    print("预估出图成本：%s" % fmt_image_cost(cost))
    for n in cost.get("notes") or []:
        print("  · %s" % n)
    if plan_obj.get("cost_text"):
        ct = plan_obj["cost_text"]
        print("  配图方案那一次文本调用：token prompt=%d completion=%d total=%d"
              % (ct["prompt_tokens"], ct["completion_tokens"], ct["total_tokens"]))
        print("  · %s" % ct["notes"][0])
    if a.budget is not None:
        print("  预算 %g 点：%s" % (a.budget, "超了，会被拦下"
                                   if (cost.get("total_points") or 0) > a.budget else "在预算内"))


def _img_state_key(item):
    """出图断点 key：`img:<id>:<分辨率>:<归一化提示词的摘要>`。

    ⚠️ 这里**必须对完整提示词取摘要**，绝不能截断提示词前 N 个字符。
    曾经的写法是 `_norm_for_echo(prompt)[:24]`：提示词**只改第 25 字之后**的内容时
    key 不变 → 断点命中 → **静默复用旧图**，用户以为重出了、其实拿到的是旧图，
    连一句提示都没有。这是「静默复用过期产物」，比多扣一次费危险得多
    （多扣费用户立刻会发现，复用旧图不会）。

    ⚠️ 这里**必须把 `resolution` 算进 key**（1.0.4 补的第 3 维）。
    1.0.3 的 key 只有「id + 提示词摘要」：先跑 1K 出了图，再改成 `--resolution 4K`
    重跑 → key 不变 → 断点命中 → **复用 1K 的图，用户以为自己拿到了 4K**。
    同样是静默复用过期产物，而且这次提示词一个字没变，
    任何基于提示词的兜底都发现不了。`resolution` 直接进 key（纯文本，不必哈希）：
    取值只有 1K/2K/4K 三个，长度可控且比摘要更好读。

    摘要取 16 位十六进制（64 bit）：key 长度可控、可读，且碰撞概率对本场景可忽略；
    提示词变一个字，key 必变 → 重新出图并重新扣费（这是设计如此）。
    """
    digest = hashlib.sha1(_norm_for_echo(item.get("prompt")).encode("utf-8")).hexdigest()
    return "img:%s:%s:%s" % (item["id"], item.get("resolution") or "1K", digest[:16])


def _run_images(a, plan_obj, outdir, spath, cost):
    state = json.loads(Path(spath).read_text(encoding="utf-8")) if Path(spath).is_file() else {}
    state.setdefault("items", {})
    total_points, spent_this_run = 0.0, 0.0
    done, skipped, failed, ratio_bad = [], [], [], []
    for n, it in enumerate(plan_obj["items"], 1):
        key = _img_state_key(it)
        prev = state["items"].get(key)
        # 二次兜底：key 只认「id + 分辨率 + 提示词摘要」，正常不会出现
        # 「key 相同但提示词不同」。但断点文件可能是手工改过的、或由旧版本生成的，
        # 一旦真出现就必须**重出**，绝不能静默复用旧图（本包的原则：断点命中不能只看状态标记）。
        cur_norm = _norm_for_echo(it["prompt"])
        if prev and _norm_for_echo(prev.get("prompt")) != cur_norm:
            sys.stderr.write("    #%s 断点记录里的提示词与本次不一致 → **不复用旧图**，重新出图\n"
                             % it["id"])
            prev = None
        # 分辨率兜底：与提示词兜底同一口径。key 里已经带了 resolution，
        # 但断点文件是旧版生成的（那时 key 不含分辨率）或手改过时，
        # 记录里的 `resolution` 可能与本次对不上；对不上就重出。
        # 记录里**没存** `resolution`（旧断点）同样按「不一致」处理：
        # 说不出上次是什么档，就没有复用那张图的依据。
        prev_res = prev.get("resolution") if prev else None
        want_res = it.get("resolution") or "1K"
        if prev and (not isinstance(prev_res, str)
                     or prev_res.upper() != want_res.upper()):
            sys.stderr.write("    #%s 断点记录里的分辨率（%s）与本次（%s）不一致 → "
                             "**不复用旧图**，重新出图\n"
                             % (it["id"], prev_res or "没存", want_res))
            prev = None
        if prev and prev.get("status") == "completed" and not a.force:
            pts = prev.get("points_cost")
            # ⚠️ 跳过的那张，它**上次已经真扣过费**，必须计入 total_points，
            # 否则断点续跑跑完，汇总里的「累计扣费」会比真实花的少——
            # 实测踩到：续跑后 image_points=0，而实际已经花了 48 点。
            # `spent_this_run` 不加（那次不是本次花的），两个数分开报。
            total_points += float(pts or 0)
            skipped.append((it, prev))
            print("[%d/%d] #%s 已完成，跳过（上次扣费 %s 点，不再重复扣）"
                  % (n, len(plan_obj["items"]), it["id"], pts))
            continue
        if a.budget is not None:
            spend = total_points + (cost["points_per_image"] or 0)
            if spend > a.budget:
                sys.stderr.write(
                    "\n%s\n" % _red("已花/待花 %g 点将超过预算 %g 点，**就此停下**"
                                    "（不再提交新任务）。已完成的图与断点都在 %s。"
                                    % (spend, a.budget, spath)))
                _save_img_state(spath, state)
                return _fail(3, "budget", "已花/待花 %g 点将超过 --budget %g 点，就此停下"
                             % (spend, a.budget), detail={"outdir": str(outdir)})
        sys.stderr.write("[%d/%d] #%s 提交：aspect_ratio=%s resolution=%s model=%s\n"
                         % (n, len(plan_obj["items"]), it["id"], it["aspect_ratio"],
                            it["resolution"], a.image_model))
        try:
            data = submit_image(it["prompt"], aspect_ratio=it["aspect_ratio"],
                                resolution=it["resolution"], model=a.image_model,
                                key=a.key, timeout=a.submit_timeout)
        except a7w.A7wError as exc:
            sys.stderr.write("    提交失败：%s\n" % exc)
            failed.append({"id": it["id"], "stage": "submit", "error": str(exc)})
            if a.stop_on_error:
                _save_img_state(spath, state)
                return _fail(4, "call", "一张失败就整体停（--stop-on-error）")
            continue
        task_id = data.get("task_id")
        state["items"][key] = {
            "id": it["id"], "role": it["role"], "prompt": it["prompt"],
            "aspect_ratio": it["aspect_ratio"], "resolution": it["resolution"],
            "model": a.image_model, "task_id": task_id, "status": "pending",
            "frozen_points": data.get("frozen_points"),
            "submit_response": data,
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        _save_img_state(spath, state)

        def on_tick(status, data, _key=key):
            state["items"][_key]["last_status"] = status
            _save_img_state(spath, state)

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
                _save_img_state(spath, state)
                return _fail(4, "call", "一张失败就整体停（--stop-on-error）")
            continue

        rec = state["items"][key]
        rec["last_status"] = status
        rec["raw_task"] = payload
        if status != "completed":
            err = data.get("error") or (data.get("result") or {}).get("error") or ""
            sys.stderr.write("    任务未成功：%s  %s\n" % (status, err))
            rec["status"] = "failed"
            rec["error"] = "%s %s" % (status, err)
            _save_img_state(spath, state)
            failed.append({"id": it["id"], "stage": "task", "task_id": task_id,
                           "error": rec["error"], "raw_task": payload})
            if a.stop_on_error:
                return _fail(4, "call", "一张失败就整体停（--stop-on-error）")
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
            _save_img_state(spath, state)
            failed.append({"id": it["id"], "stage": "no_url", "task_id": task_id,
                           "raw_task": payload})
            continue

        url = urls[0]
        # 文件名里带上分辨率：摘要只对**提示词**取，同一提示词换档（1K→4K）时
        # `key.split(":")[-1]` 是**同一个**摘要，不带分辨率就会把 4K 的图
        # 覆盖到 1K 的文件名上。带上它，两档各自的产出都留着。
        dest = outdir / ("%s-%s-%s-%s-%s%s" % (it["id"], it["role"],
                                               it["aspect_ratio"].replace(":", "x"),
                                               it.get("resolution") or "1K",
                                               key.split(":")[-1][:12], OUT_EXT))
        try:
            a7w.save(url, str(dest))
        except a7w.A7wError as exc:
            rec["status"] = "failed"
            rec["error"] = "下载失败：%s" % exc
            rec["image_url"] = url
            _save_img_state(spath, state)
            failed.append({"id": it["id"], "stage": "download", "task_id": task_id,
                           "error": str(exc), "image_url": url})
            continue

        # 闸门六：**只认文件头里的宽高**，不采信任何接口自报的 aspect_ratio
        check = check_ratio(str(dest), it["aspect_ratio"], a.ratio_tolerance)
        first_check = dict(check)
        rec["image_url"] = url
        rec["file"] = str(dest)
        rec["first_check"] = first_check
        rec["real_px"] = check["real_px"]
        rec["real_ratio"] = check.get("real_ratio")
        rec["real_label"] = check.get("real_label")
        rec["want_ratio"] = it["aspect_ratio"]
        rec["ratio_deviation"] = check["deviation"]

        if a.snap and not check["ok"]:
            snapped = str(dest.with_name(dest.stem + "-snapped" + dest.suffix))
            got = snap_to_ratio(str(dest), snapped, it["aspect_ratio"])
            if got:
                way, box = got
                after = check_ratio(snapped, it["aspect_ratio"], a.ratio_tolerance)
                rec["snap"] = {"method": way, "box": box, "file": snapped, "after": after}
                if after["ok"]:
                    dest = Path(snapped)
                    check = after
                    rec["real_px"] = after["real_px"]
                    rec["real_ratio"] = after.get("real_ratio")
                    rec["real_label"] = after.get("real_label")
                    rec["ratio_deviation"] = after["deviation"]
                    rec["file"] = str(snapped)
            else:
                rec["snap"] = {"method": None,
                               "why": "没有 PIL，内置裁剪器也不支持这个 PNG（需 8 位真彩/真彩+alpha）"}
        rec["raw_ratio_check"] = check
        rec["ratio_ok"] = bool(check["ok"])
        rec["status"] = "completed"
        _save_img_state(spath, state)
        if check["ok"]:
            done.append((it, rec))
            print("    完成 真实像素 %sx%s  %s  偏差 %.2f%%  扣费 %s 点  → %s"
                  % (check["real_px"][0], check["real_px"][1], check.get("real_label"),
                     (check["deviation"] or 0) * 100, pts, rec["file"]))
        else:
            ratio_bad.append((it, rec))
            print("    " + _red("完成但比例不合格：%s" % check.get("why")))
            print("    " + _red("  → %s" % rec["file"]))

    return _finalize_images(a, plan_obj, outdir, spath, cost, done, skipped,
                            failed, ratio_bad, total_points, spent_this_run)


def _save_img_state(spath, state):
    p = Path(spath)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _finalize_images(a, plan_obj, outdir, spath, cost, done, skipped, failed,
                     ratio_bad, total_points, spent_this_run):
    summary = {
        "platform": plan_obj["platform"], "outdir": str(outdir), "state": spath,
        "planned_images": plan_obj["count"],
        "ratio_requested": plan_obj["ratio"],
        "completed": [{"id": it["id"], "role": it["role"], "task_id": r.get("task_id"),
                       "file": r.get("file"), "real_px": r.get("real_px"),
                       "real_label": r.get("real_label"),
                       "want_ratio": it["aspect_ratio"], "real_ratio": r.get("real_ratio"),
                       "deviation": r.get("ratio_deviation"),
                       "points_cost": r.get("points_cost"),
                       "image_url": r.get("image_url"),
                       "first_check": r.get("first_check"),
                       "snap": r.get("snap"),
                       "raw_task": r.get("raw_task")}
                      for it, r in done],
        "skipped_already_done": [{"id": it["id"], "task_id": r.get("task_id"),
                                  "file": r.get("file"), "points_cost": r.get("points_cost"),
                                  "real_px": r.get("real_px")} for it, r in skipped],
        "ratio_failed": [{"id": it["id"], "file": r.get("file"), "real_px": r.get("real_px"),
                          "want_ratio": it["aspect_ratio"],
                          "why": (r.get("raw_ratio_check") or {}).get("why")}
                         for it, r in ratio_bad],
        "failed": failed,
        "points_cost_total": total_points,
        "points_cost_this_run": spent_this_run,
        "points_per_yuan": POINTS_PER_YUAN,
        "yuan_total": round(total_points / float(POINTS_PER_YUAN), 4),
        "cost_quote": cost,
        "notices": plan_obj["notices"],
    }
    gate_bad = bool(ratio_bad or failed)
    # 先把这份摘要落盘：断点续跑与后续脚本都要读它（`--json` 时它也是 stdout 的那份 JSON）。
    # ⚠️ 但 `all` 调进来时**不发 stdout、也不占 pending**：`all` 自己会在第 4 步之后
    # 发一份含正文/适配/配图的总摘要。两边都发就会出现「一次运行里暂存了两份 JSON」
    # （实测报出来的就是这条内部错误）。所以由 `all` 用 `_suppress_json_out` 标记收口。
    if not getattr(a, "_suppress_json_out", False):
        _stage_json(summary, getattr(a, "out", None), indent=1, ok=not gate_bad)
    try:
        Path(outdir / "images-summary.json").write_text(
            json.dumps(_json_payload(summary, not gate_bad), ensure_ascii=False, indent=1),
            encoding="utf-8")
    except OSError as exc:
        sys.stderr.write("写 images-summary.json 失败：%s\n" % exc)
    if not a.json and not getattr(a, "_suppress_json_out", False):
        print("")
        print("配图跑完：%s（%s）" % (plan_obj["platform_name"], outdir))
        print("  完成：%d 张" % len(done))
        for it, r in done:
            print("    #%s %s  %sx%s  %s  真实偏差 %.2f%%  %s 点"
                  % (it["id"], it["role"], (r.get("real_px") or [0, 0])[0],
                     (r.get("real_px") or [0, 0])[1], r.get("real_label"),
                     (r.get("ratio_deviation") or 0) * 100, r.get("points_cost")))
        if skipped:
            print("  跳过（已完成，不重复扣费）：%d 张" % len(skipped))
        if ratio_bad:
            print("  " + _red("比例不合格：%d 张" % len(ratio_bad)))
        if failed:
            print("  " + _red("失败：%d 张" % len(failed)))
        print("  本次实际扣费：%g 点 = %.2f 元（累计 %g 点）"
              % (spent_this_run, spent_this_run / float(POINTS_PER_YUAN),
                 total_points))
        print("  结算口径：只信任务返回的 usage.points_cost，不信 pricing_matrix。")
        print("  断点文件：%s（原样重跑即可续跑，已完成的不会重复扣费）" % spath)
    if ratio_bad:
        for it, r in ratio_bad:
            sys.stderr.write("   " + _red("#%s %s" % (it["id"], (r.get("raw_ratio_check") or {}).get("why")))
                             + "\n")
    if failed:
        sys.stderr.write("\n%s\n" % _red("闸门：%d 张失败" % len(failed)))
        for f in failed:
            sys.stderr.write("   #%s %s：%s\n" % (f["id"], f["stage"], f["error"]))
        return _fail(4, "call", "%d 张出图失败" % len(failed))
    if ratio_bad:
        return _fail(3, "gate", "%d 张真实像素与请求比例偏差超过容差" % len(ratio_bad))
    return 0


def cmd_adapt(a):
    art = _require_article(a)
    target = a.platform
    p = PLATFORMS[target]
    chars_range = (a.chars_min, a.chars_max) if (a.chars_min or a.chars_max) else p["chars"]
    topic = art.get("title") or a.topic or ""
    prompt = build_adapt_prompt(topic, target, art, chars_range)
    if a.dry_run:
        _dry_run_json(a, platform=target, user=prompt)
        return 0
    if a.from_file:
        obj = unwrap_model_output(parse_first_json(
            Path(a.from_file).read_text(encoding="utf-8", errors="replace")))
        item = normalize_article(obj, target, chars_range)
        return _emit_adapt(a, art, [item], None, None)
    platforms = [target] if not a.all_platforms else PLATFORM_CHOICES
    tracker = CostTracker(a.budget, a.yuan_per_ktok)
    per = EST_TOKENS["adapt"]["prompt"] + EST_TOKENS["adapt"]["completion"]
    if tracker.over_budget(per * len(platforms)):
        sys.stderr.write("\n%s\n" % _red(
            "预估成本已超 --budget %g 元，一个平台版都没改" % a.budget))
        return _fail(3, "budget", "预估成本已超 --budget %g 元，一个平台版都没改" % a.budget)
    results, usages = [], []
    for i, pl in enumerate(platforms, 1):
        cr = (a.chars_min, a.chars_max) if (a.chars_min or a.chars_max) else PLATFORMS[pl]["chars"]
        pr = build_adapt_prompt(topic, pl, art, cr)
        if tracker.over_budget(per):
            sys.stderr.write("\n%s\n" % _red("成本已达 --budget %g 元，就地停止（%s）"
                                            % (a.budget, tracker.line())))
            break
        sys.stderr.write("[%d/%d] 正在改写成%s版（目标 %d~%d 字）…\n"
                         % (i, len(platforms), PLATFORMS[pl]["name"], cr[0], cr[1]))
        t0 = time.time()
        content, usage = chat(pr, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                              max_tokens=a.max_tokens, key=a.key,
                              json_mode=not a.no_json_mode,
                              tracker=tracker, tracker_label="adapt")
        item = normalize_article(parse_first_json(content), pl, cr)
        item["elapsed_sec"] = round(time.time() - t0, 1)
        item["usage"] = usage
        usages.append(usage)
        sys.stderr.write("      %d 字 · %.1fs · usage %s\n"
                         % (item["chars"], item["elapsed_sec"],
                            json.dumps(usage, ensure_ascii=False)))
        results.append(item)
    if not results:
        raise LongformError("没有生成任何平台版")
    return _emit_adapt(a, art, results, tracker, usages)


def _emit_adapt(a, art, results, tracker, usages):
    out = ["# 平台适配版 · %s" % (art.get("title") or ""), ""]
    bad = []
    for r in results:
        out.append("---")
        out.append("")
        out.append("## %s" % r["platform_name"])
        out.append("")
        out.append("**%s**" % (r["title"] or "（无标题）"))
        out.append("")
        if r["changed"]:
            out.append("> 相比原文的改动：%s" % "；".join(r["changed"]))
            out.append("")
        out.append("- 字数：%d 字（区间 %d~%d）%s" % (
            r["chars"], r["chars_range"][0], r["chars_range"][1],
            "" if r["length_ok"] else "  ← 越界"))
        out.append("")
        out.append(r["content"] or "（正文为空）")
        out.append("")
        if r["leaks"]:
            out.append("### 本地自检命中")
            out.append("")
            for lk in r["leaks"]:
                out.append("- %s：%s" % (lk["kind"], lk["why"]))
            out.append("")
        if not r["ok"]:
            bad.append(r)
    result = {"platforms": [r["platform"] for r in results],
              "model": a.model, "articles": results,
              "usages": usages,
              "gate_failures": [{"platform": r["platform"],
                                 "why": [lk["why"] for lk in r["leaks"]]} for r in bad]}
    if tracker is not None:
        result["cost"] = text_cost_record(tracker.calls, tracker.prompt_tokens,
                                          tracker.completion_tokens, tracker.rate,
                                          tracker.estimated_flags)
    _emit(a, "\n".join(out), json_obj=result, ok=not bad)
    if bad:
        sys.stderr.write("\n%s\n" % _red(
            "闸门：%d 个平台版命中（违禁词 / 占位符 / 照抄示例 / 字数越界 / 结构残缺）："
            % len(bad)))
        for r in bad:
            for lk in r["leaks"]:
                sys.stderr.write("   %s ← %s：%s\n" % (r["platform_name"], lk["kind"], lk["why"]))
        if tracker:
            sys.stderr.write("%s\n" % tracker.line())
        return _fail(3, "gate", "闸门：%d 个平台版命中本地闸门" % len(bad))
    if tracker:
        sys.stderr.write("%s\n" % tracker.line())
    return 0


def cmd_cost(a):
    platform = a.platform
    p = PLATFORMS[platform]
    lo, hi = (a.chars_min, a.chars_max) if (a.chars_min or a.chars_max) else p["chars"]
    sections = a.sections
    images = a.images if a.images is not None else \
        int((p["images"][0] + p["images"][1]) / 2)
    quote = {
        "platform": platform, "platform_name": p["name"], "chars_range": [lo, hi],
        "sections": sections, "images": images,
        "text_calls": {"outline": 1, "write": 1, "adapt": 0 if a.adapt_off else
                       (len(PLATFORM_CHOICES) if a.all_platforms else 1),
                       "image_plan": 0 if a.images == 0 else 1},
        "tokens": {}, "image_cost": None, "notes": [],
    }
    tok = {"outline": EST_TOKENS["outline"], "write": EST_TOKENS["write"],
           "image_plan": EST_TOKENS["images"], "adapt": EST_TOKENS["adapt"]}
    calls = quote["text_calls"]
    prompt_t = tok["outline"]["prompt"] + tok["write"]["prompt"]
    completion_t = tok["outline"]["completion"] + tok["write"]["completion"]
    n_calls = 2
    if calls["image_plan"]:
        prompt_t += tok["image_plan"]["prompt"]
        completion_t += tok["image_plan"]["completion"]
        n_calls += 1
    for _ in range(calls["adapt"]):
        prompt_t += tok["adapt"]["prompt"]
        completion_t += tok["adapt"]["completion"]
        n_calls += 1
    quote["tokens"] = {"prompt_tokens": prompt_t, "completion_tokens": completion_t,
                       "total_tokens": prompt_t + completion_t, "calls": n_calls}
    # 写正文的 max_tokens 要够 4500 字，这里如实提示
    quote["write_max_tokens_hint"] = 8192
    # `cost` 子命令**没有** `--resolution`（它是纯估算、不出图），所以这里用
    # getattr 兜底 1K：写死 `a.resolution` 会让 `cost` 直接 AttributeError 崩掉
    # （改这一版时实测踩到）。出图那条链路（`images` / `all`）永远有 a.resolution。
    icost = image_cost(images, getattr(a, "resolution", "1K"), a.points_per_image)
    quote["image_cost"] = icost
    quote["notes"] = [
        "**文本只出 token，不出金额**：网关不公布文本模型单价（pricing 表不含文本模型、"
        "models 无价格字段、usage 无 points_cost），所以我们不编单价。",
        "要文本金额请自己传 --yuan-per-ktok <元/千token>，传了才算，并标成估算。",
        "出图按**实测价** %g 点/张（1K，= %.2f 元）计；2K/4K 没有实测价，"
        "必须用 --points-per-image 指定，我们不猜。" % (POINTS_PER_IMAGE_1K,
                                                POINTS_PER_IMAGE_1K / float(POINTS_PER_YUAN)),
        "真实用量看每次调用返回的 usage 与出图任务的 usage.points_cost；账单以 api.a7w.cn 控制台为准。",
        "1 元 = %d 点。" % POINTS_PER_YUAN,
    ]
    # 先定结论：超预算就是「不放行」，发出的 JSON 里 ok 要与退出码一致
    over_budget = a.budget is not None and (icost.get("total_points") or 0) > a.budget
    rec_rc = (_fail(3, "budget", "预估 %g 点超过 --budget %g 点，未发起任何调用"
                    % (icost.get("total_points") or 0, a.budget)) if over_budget else 0)
    if a.json:
        _stage_json(quote, getattr(a, "out", None), indent=1, ok=not rec_rc)
    else:
        print("预估成本（一次调用都不发）")
        print("  平台：%s（正文区间 %d~%d 字 / 建议配图 %d~%d 张）"
              % (p["name"], lo, hi, p["images"][0], p["images"][1]))
        print("  分节：%d 节　配图：%d 张" % (sections, images))
        print("  文本调用：%d 次（outline %d / write %d / images %d / adapt %d）"
              % (n_calls, calls["outline"], calls["write"], calls["image_plan"],
                 calls["adapt"]))
        print("  预估 token：prompt %d + completion %d = %d"
              % (prompt_t, completion_t, prompt_t + completion_t))
        print("  预估出图：%s" % fmt_image_cost(icost))
        if a.yuan_per_ktok is not None:
            yuan = (prompt_t + completion_t) / 1000.0 * a.yuan_per_ktok
            print("  文本金额估算：%.2f 元（按**你填的** %g 元/千 token）"
                  % (yuan, a.yuan_per_ktok))
        for n in quote["notes"]:
            print("  · %s" % n)
        if a.budget is not None:
            print("  预算 %g 点：%s" % (a.budget, "超了，images/all 会被拦下"
                                       if over_budget else "在预算内"))
    if over_budget:
        sys.stderr.write("\n%s\n" % _red(
            "闸门七：预估 %g 点超过 --budget %g 点，images / all 会在发起调用前停在这里"
            % (icost.get("total_points") or 0, a.budget)))
        return rec_rc
    return 0


def cmd_models(a):
    key = a7w.load_key(a.key)
    try:
        payload = a7w._request("GET", MODELS_URL, key, timeout=60)
    except a7w.A7wError as exc:
        sys.stderr.write("拉模型清单失败：%s\n" % exc)
        return _fail(4, "call", "拉取模型清单失败（网络 / 鉴权 / Key）")
    data = a7w._unwrap(payload)
    lst = data.get("list") if isinstance(data, dict) and "list" in data else data
    lst = [m for m in (lst or []) if isinstance(m, dict)]
    if a.type and a.type != "all":
        lst = [m for m in lst if str(m.get("type_code")) == a.type]
    if a.json:
        _stage_json(lst, getattr(a, "out", None), indent=1)
        return 0
    print("在架模型 %d 个（%s）\n" % (len(lst), MODELS_URL))
    for m in lst:
        print("  %-26s %-8s call_type=%s  %-28s %s" % (
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            m.get("call_type"), str(m.get("vendor_name") or "-"),
            str(m.get("model_name") or "")[:24]))
    print("")
    print("提示：模型名会变，以本命令现查为准，别写死在脚本里。")
    print("      `%s` 实测可用（路由到 deepseek-flash），但它**不在**上面这份列表里，" % DEFAULT_MODEL)
    print("      所以「列表里没有」不等于「不能用」。")
    print("      长文生产线是纯文本任务，只能选 type_code=text 的模型：`models --type text`。")
    print("用法：run.py outline --topic \"...\" --model <model_code>")
    return 0


# ---------------------------------------------------------------------------
# all：跑完整条链路（断点续跑）
# ---------------------------------------------------------------------------

def cmd_all(a):
    try:
        ensure_outside_pkg(a.outdir)
    except PackagePathError as exc:
        sys.stderr.write("\n%s\n" % _red(str(exc)))
        return _fail(2, "usage", str(exc))
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state = {} if a.force else load_state(outdir)
    tracker = CostTracker(a.budget, a.yuan_per_ktok)
    platform = a.platform
    p = PLATFORMS[platform]
    chars_range = (a.chars_min, a.chars_max) if (a.chars_min or a.chars_max) else p["chars"]

    # ---- 第 1 步：大纲 ----
    outline_file = outdir / "outline.json"
    plan = None
    if not a.force and (state.get("outline") or {}).get("ok") and outline_file.is_file():
        plan = (json.loads(outline_file.read_text(encoding="utf-8")) or {}).get("outline")
        if plan:
            sys.stderr.write("[1/4] 大纲已完成，跳过（断点续跑，不再重复扣费）\n")
    if plan is None:
        est = EST_TOKENS["outline"]
        if tracker.over_budget(est["prompt"] + est["completion"]):
            sys.stderr.write("\n%s\n" % _red(
                "闸门七：预估成本已超 --budget %g 元，未发起任何调用" % a.budget))
            return _fail(3, "budget", "预估成本已超 --budget %g 元，未发起任何调用" % a.budget)
        sys.stderr.write("[1/4] 正在用 `%s` 出选题角度 + 大纲（%s）…\n" % (a.model, p["name"]))
        ocontent, ousage = chat(build_outline_prompt(a.topic, platform, a.angles, a.sections,
                                                     a.audience, a.requirements, a.tone),
                                SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                                max_tokens=a.max_tokens, key=a.key,
                                json_mode=not a.no_json_mode,
                                tracker=tracker, tracker_label="outline")
        plan = normalize_outline(parse_first_json(ocontent), a.topic, platform,
                                 a.angles, a.sections)
        if not plan["sections"]:
            raise LongformError("模型返回里没有 sections，大纲是空的（可加大 --max-tokens 或换模型）")
        outline_file.write_text(json.dumps({"outline": plan, "model": a.model,
                                            "usage": ousage},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
        sys.stderr.write("      %d 个角度 / %d 节 / 计划 %d 字 · usage %s\n"
                         % (plan["angle_count"], plan["section_count"],
                            plan["planned_chars"], json.dumps(ousage, ensure_ascii=False)))
        if not plan["structure_ok"]:
            state["outline"] = {"ok": False,
                               "checks": plan["structure_checks"]}
            save_state(outdir, state)
            for c in plan["structure_checks"]:
                if not c["ok"]:
                    sys.stderr.write("   %s ✗ %s\n" % (c["check"], c["detail"]))
            sys.stderr.write("\n%s\n" % _red(
                "闸门五：大纲结构校验未通过，后续正文不会基于这份大纲生成"))
            sys.stderr.write("%s\n" % tracker.line())
            return _fail(3, "gate", "闸门五：大纲结构校验未通过，后续正文不会基于它生成")
        state["outline"] = {"ok": True, "checks": plan["structure_checks"]}
        save_state(outdir, state)

    (outdir / "outline.md").write_text(
        render_outline_md(plan, a.model) + "\n", encoding="utf-8")

    # ---- 第 2 步：正文 ----
    article_file = outdir / "article.json"
    art = None
    # ⚠️ 断点命中要同时满足「状态 ok」与「**产出文件本身**也是合格的」。
    # 只看状态、不看文件内容的话，手工改坏 `article.json`（或改掉正文里的违禁词）
    # 之后重跑会被当成「已完成」直接跳过，**闸门变成假绿**——这正是模板里
    # 反复出现的那类事故（标题工坊只信模型自报字段）。所以这里两个条件都要。
    if not a.force and (state.get("write") or {}).get("ok") and article_file.is_file():
        art = (json.loads(article_file.read_text(encoding="utf-8")) or {}).get("article")
        if art and art.get("ok"):
            sys.stderr.write("[2/4] 正文已完成，跳过（%d 字，已复检 ok）\n" % art.get("chars", 0))
        else:
            sys.stderr.write("[2/4] 断点说正文已完成，但文件里的正文不合格 → **不跳过**，重新生成\n")
            art = None
    if art is None:
        est = EST_TOKENS["write"]
        if tracker.over_budget(est["prompt"] + est["completion"]):
            sys.stderr.write("\n%s\n" % _red("闸门七：成本已达 --budget %g 元，就地停止" % a.budget))
            save_state(outdir, state)
            return _fail(3, "budget", "成本已达 --budget %g 元，就地停止")
        sys.stderr.write("[2/4] 正在写正文（目标 %d~%d 字）…\n" % (chars_range[0], chars_range[1]))
        wcontent, wusage = chat(build_write_prompt(a.topic, platform, plan, chars_range),
                                SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                                max_tokens=a.max_tokens, key=a.key,
                                json_mode=not a.no_json_mode,
                                tracker=tracker, tracker_label="write")
        art = normalize_article(parse_first_json(wcontent), platform, chars_range)
        art["topic"] = a.topic
        art["chosen"] = plan.get("chosen")
        art["usage"] = wusage
        article_file.write_text(json.dumps({"article": art, "model": a.model},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
        sys.stderr.write("      %d 字 · usage %s\n"
                         % (art["chars"], json.dumps(wusage, ensure_ascii=False)))
        state["write"] = {"ok": art["ok"], "chars": art["chars"], "leaks": art["leaks"]}
        save_state(outdir, state)
        if not art["ok"]:
            for lk in art["leaks"]:
                sys.stderr.write("   %s ← %s\n" % (lk["kind"], lk["why"]))
            sys.stderr.write("\n%s\n" % _red(
                "闸门：正文命中，**后续配图不会基于这份正文生成**（先把正文改干净）"))
            sys.stderr.write("%s\n" % tracker.line())
            return _fail(3, "gate", "闸门：正文命中本地闸门，链路已停在这里")
    (outdir / "article.md").write_text(render_article_md(art) + "\n", encoding="utf-8")

    # ---- 第 3 步：配图 ----
    image_summary = None
    if a.images == 0:
        sys.stderr.write("[3/4] --images 0：跳过配图\n")
    else:
        want = a.images if a.images is not None else int((p["images"][0] + p["images"][1]) / 2)
        ratio = a.ratio or p["ratio"]
        # 报价先行：闸门七在提交**任何**任务之前判
        icost = image_cost(want, a.resolution, a.points_per_image)
        print("")
        _print_quote({}, icost, a)
        if icost.get("total_points") is None:
            sys.stderr.write("\n%s\n" % _red(
                "闸门七：没有可信单价（1K 有实测价，2K/4K 没有），拒绝盲跑。"
                "用 --points-per-image 指定单价后重试。"))
            save_state(outdir, state)
            return _fail(3, "budget", "没有可信单价，拒绝凭猜估算")
        if a.budget is not None and icost["total_points"] > a.budget:
            sys.stderr.write("\n%s\n" % _red(
                "闸门七：预估 %g 点超过 --budget %g 点，**已中断，未提交任何出图任务**。"
                % (icost["total_points"], a.budget)))
            save_state(outdir, state)
            return _fail(3, "budget", "预估 %g 点超过 --budget %g 点，未提交任何出图任务"
                         % (icost["total_points"], a.budget))
        if not a.yes:
            sys.stderr.write("\n%s\n" % _red(
                "配图是**真花钱**的操作（约 %.2f 元 / %g 点）。"
                "确认后加 --yes 重跑；只想先看正文就加 --images 0。"
                % (icost["total_yuan"] or 0, icost["total_points"] or 0)))
            save_state(outdir, state)
            return _fail(4, "usage", "配图要花钱，确认后加 --yes 重跑（或 --images 0 跳过）")

        sys.stderr.write("[3/4] 正在出配图方案…\n")
        iprompt = build_images_prompt(a.topic, platform, art, p["images"][0], p["images"][1], ratio)
        icontent, iusage = chat(iprompt, SYSTEM_PROMPT, model=a.model,
                                temperature=a.temperature, max_tokens=a.max_tokens,
                                key=a.key, json_mode=not a.no_json_mode,
                                tracker=tracker, tracker_label="images")
        iplan = normalize_image_plan(parse_first_json(icontent), platform,
                                     p["images"][0], p["images"][1], ratio,
                                     resolution=a.resolution)
        if a.images and len(iplan["items"]) > a.images:
            iplan["items"] = iplan["items"][:a.images]
            iplan["count"] = len(iplan["items"])
            iplan["notices"].append("按 --images %d 截断到前 %d 张" % (a.images, a.images))
        blocked = [it for it in iplan["items"] if it["leaks"]]
        if blocked and not a.allow_prompt_hits:
            for it in blocked:
                for kind, why in it["leaks"]:
                    sys.stderr.write("   #%s %s ← %s\n" % (it["id"], kind, why))
            sys.stderr.write("\n%s\n" % _red(
                "闸门二/三：%d 张出图提示词命中，**未提交任何任务**（不花一分钱）"
                % len(blocked)))
            save_state(outdir, state)
            return _fail(3, "gate", "有出图提示词命中本地闸门，未提交任何任务")
        # 方案张数可能与报价张数不同 → 按方案实际张数重新报价并再核一次预算
        icost = image_cost(len(iplan["items"]), a.resolution, a.points_per_image)
        if a.budget is not None and (icost.get("total_points") or 0) > a.budget:
            sys.stderr.write("\n%s\n" % _red(
                "闸门七：方案实际 %d 张 = %g 点，超过 --budget %g 点，未提交任何任务"
                % (len(iplan["items"]), icost.get("total_points") or 0, a.budget)))
            save_state(outdir, state)
            return _fail(3, "budget", "方案实际张数超预算，未提交任何任务")
        (outdir / "images-plan.json").write_text(
            json.dumps({"plan": iplan, "usage": iusage, "quote": icost},
                       ensure_ascii=False, indent=1), encoding="utf-8")

        img_out = Path(a.img_outdir) if a.img_outdir else (outdir / "images")
        try:
            ensure_outside_pkg(img_out)
        except PackagePathError as exc:
            sys.stderr.write("\n%s\n" % _red(str(exc)))
            save_state(outdir, state)
            return _fail(2, "usage", str(exc))
        img_out.mkdir(parents=True, exist_ok=True)
        img_state = str(img_out / STATE_NAME)
        # 第 3 步由 `all` 自己收口 stdout（第 4 步后发总摘要），所以让 `_run_images`
        # 不要占 pending —— 见 `_finalize_images` 里 `_suppress_json_out` 的说明。
        a._suppress_json_out = True
        img_rc = _run_images(a, iplan, img_out, img_state, icost)
        a._suppress_json_out = False
        isum = img_out / "images-summary.json"
        image_summary = (json.loads(isum.read_text(encoding="utf-8"))
                         if isum.is_file() else None)
        # 把出图扣费记进总账。**用 images-summary 里的累计值，不重新加一遍**：
        # 那个值已经把「本次新扣的」与「断点跳过但上次已扣的」都算进去了
        # （见 `_run_images` 里跳过分支的注释），在这里再加一次就是重复计费。
        if image_summary:
            tracker.add_points(image_summary.get("points_cost_total") or 0)
        if img_rc:
            save_state(outdir, state)
            return img_rc

    # ---- 第 4 步：平台适配 ----
    adapts = []
    targets = PLATFORM_CHOICES if a.adapt_all else []
    if not targets:
        sys.stderr.write("[4/4] 未指定 --adapt-all，跳过平台适配\n")
    for i, pl in enumerate(targets, 1):
        f = outdir / ("adapt-%s.json" % pl)
        k = state_key("adapt", pl)
        if not a.force and (state.get(k) or {}).get("ok") and f.is_file():
            adapts.append(json.loads(f.read_text(encoding="utf-8"))["article"])
            sys.stderr.write("[4/4] %s 版已完成，跳过\n" % PLATFORMS[pl]["name"])
            continue
        cr = PLATFORMS[pl]["chars"]
        est = EST_TOKENS["adapt"]
        if tracker.over_budget(est["prompt"] + est["completion"]):
            sys.stderr.write("\n%s\n" % _red(
                "闸门七：成本已达 --budget %g 元，就地停止" % a.budget))
            break
        sys.stderr.write("[4/4] (%d/%d) 正在改写成%s版…\n"
                         % (i, len(targets), PLATFORMS[pl]["name"]))
        acontent, ausage = chat(build_adapt_prompt(a.topic, pl, art, cr), SYSTEM_PROMPT,
                                model=a.model, temperature=a.temperature,
                                max_tokens=a.max_tokens, key=a.key,
                                json_mode=not a.no_json_mode,
                                tracker=tracker, tracker_label="adapt")
        item = normalize_article(parse_first_json(acontent), pl, cr)
        item["usage"] = ausage
        f.write_text(json.dumps({"article": item, "model": a.model},
                                ensure_ascii=False, indent=1), encoding="utf-8")
        state[k] = {"ok": item["ok"], "chars": item["chars"], "leaks": item["leaks"],
                    "file": str(f)}
        save_state(outdir, state)
        sys.stderr.write("      %d 字 · usage %s\n"
                         % (item["chars"], json.dumps(ausage, ensure_ascii=False)))
        adapts.append(item)

    return _finalize_all(a, outdir, plan, art, adapts, image_summary, state, tracker)


def _finalize_all(a, outdir, plan, art, adapts, image_summary, state, tracker):
    """汇总：合并稿、质量报告、闸门汇总、退出码。"""
    failures, checked = [], 0
    if plan and not plan.get("structure_ok", True):
        failures.append({"no": "大纲", "leaks": [
            {"kind": "structure", "why": "%s：%s" % (c["check"], c["detail"])}
            for c in (plan.get("structure_checks") or []) if not c["ok"]]})
    checked += 1
    if art:
        checked += 1
        if not art.get("ok", True):
            failures.append({"no": "正文", "leaks": art.get("leaks") or []})
    for it in adapts:
        checked += 1
        if not it.get("ok", True):
            failures.append({"no": "%s 版" % it.get("platform_name"),
                             "leaks": it.get("leaks") or []})
    img_imgs = ((image_summary or {}).get("completed") or [])
    if image_summary:
        checked += 1
        if image_summary.get("ratio_failed") or image_summary.get("failed"):
            failures.append({"no": "配图", "leaks": [
                {"kind": "ratio", "why": x.get("why") or ""}
                for x in (image_summary.get("ratio_failed") or [])] + [
                {"kind": "image_failed", "why": "%s：%s" % (x.get("stage"), x.get("error"))}
                for x in (image_summary.get("failed") or [])]})

    audit = {"ok": not failures, "checked": checked, "failures": failures,
             "structure_checks": (plan or {}).get("structure_checks"),
             "structure_ok": (plan or {}).get("structure_ok", True),
             "images": [{"id": x.get("id"), "role": x.get("role"),
                         "want_ratio": x.get("want_ratio"),
                         "real_px": x.get("real_px"), "real_label": x.get("real_label"),
                         "deviation": x.get("deviation"),
                         "ratio_ok": (x.get("first_check") or {}).get("ok"),
                         "points_cost": x.get("points_cost")} for x in img_imgs],
             "cost": {"text": text_cost_record(tracker.calls, tracker.prompt_tokens,
                                               tracker.completion_tokens, tracker.rate,
                                               tracker.estimated_flags),
                      "image_points": tracker.image_points,
                      "image_yuan": round(tracker.image_points / float(POINTS_PER_YUAN), 4)},
             "model": a.model, "topic": plan.get("topic") if plan else a.topic,
             "platform": a.platform, "platform_name": PLATFORMS[a.platform]["name"]}
    (outdir / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    (outdir / "AUDIT.md").write_text(render_audit_md(audit) + "\n", encoding="utf-8")

    # 合成一份可直接发布的稿子
    book = []
    if plan:
        book += [render_outline_md(plan, a.model), "", "---", ""]
    if art:
        book += [render_article_md(art), ""]
    for it in adapts:
        book += ["---", "", "## %s 版" % it["platform_name"], "",
                 "**%s**" % (it.get("title") or ""), "", it.get("content") or "", ""]
    if img_imgs:
        book += ["---", "", "## 配图清单（真实像素 vs 请求比例）", "",
                 "| # | 角色 | 请求比例 | 真实像素 | 实得比例 | 偏差 | 文件 |",
                 "|---|---|---|---|---|---|---|"]
        for x in img_imgs:
            book.append("| %s | %s | %s | %sx%s | %s | %.2f%% | %s |" % (
                x.get("id"), x.get("role"), x.get("want_ratio"),
                (x.get("real_px") or ["?", "?"])[0], (x.get("real_px") or ["?", "?"])[1],
                x.get("real_label"), (x.get("deviation") or 0) * 100, x.get("file")))
        book.append("")
    (outdir / "longform.md").write_text("\n".join(book) + "\n", encoding="utf-8")

    gate_ok = not failures
    if a.json:
        _json_out({
            "topic": plan.get("topic") if plan else a.topic,
            "platform": a.platform, "platform_name": PLATFORMS[a.platform]["name"],
            "outdir": str(outdir),
            "outline": ["outline.md", "outline.json"],
            "article": "article.md",
            "article_chars": (art or {}).get("chars"),
            "adapts": [it.get("platform") for it in adapts],
            "images": len(img_imgs),
            "images_pixels": [{"id": x.get("id"), "want_ratio": x.get("want_ratio"),
                               "real_px": x.get("real_px"),
                               "deviation": x.get("deviation")} for x in img_imgs],
            "image_points": tracker.image_points,
            "longform": "longform.md",
            "audit": ["AUDIT.md", "audit.json"],
            "cost": tracker.line(),
            "gate_failures": [f["no"] for f in failures],
        }, a, indent=2, ok=gate_ok)
    else:
        print("")
        print("长文生产线跑完：%s" % (plan.get("topic") if plan else a.topic))
        print("  输出目录：%s" % outdir)
        print("  大纲：outline.md / outline.json（%d 个角度 / %d 节）"
              % (plan.get("angle_count", 0), plan.get("section_count", 0)))
        print("  正文：article.md（%s 字）" % (art or {}).get("chars", "-"))
        print("  配图：%d 张（真实像素见 AUDIT.md）" % len(img_imgs))
        print("  平台版：%s" % ("、".join(it["platform_name"] for it in adapts) or "（未做）"))
        print("  合并稿：longform.md")
        print("  质量报告：AUDIT.md / audit.json")
        print("  %s" % tracker.line())
        print("  断点文件：%s（原样重跑即可续跑，已完成的不会重复扣费）"
              % state_path(a.outdir))
    if failures:
        sys.stderr.write("\n%s\n" % _red(
            "闸门：%d 个受检对象命中，详见 %s" % (len(failures), outdir / "AUDIT.md")))
        for f in failures:
            for lk in (f["leaks"] or [])[:4]:
                sys.stderr.write("   %s ← %s：%s\n" % (f["no"], lk.get("kind"), lk.get("why")))
        return _fail(3, "gate", "%d 个受检对象命中本地闸门" % len(failures))
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与同族四个包同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py cost --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _dry_run_json(a, **extra):
    """`--dry-run` 的提示词回显：`--json` 时必须包成单个 JSON，否则 stdout 不是 JSON。"""
    if getattr(a, "json", False):
        obj = {"dry_run": True}
        obj.update(extra)
        _json_out(obj, a, indent=2)
    else:
        print("=== system ===\n%s\n\n=== user ===\n%s" % (SYSTEM_PROMPT, extra.get("user", "")))


def _add_model_opts(p, with_out=True):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 %s（实测可用；用 `run.py models` 现查在架模型）" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens",
                   help="最大输出 token，默认 8192（长文正文建议不低于 8192）")
    p.add_argument("--key", help="临时指定 A7W API Key（别写进脚本或文档）")
    p.add_argument("--budget", type=float, default=None,
                   help="成本上限。文本按 --yuan-per-ktok 折算成元；出图按**点**。超了就地停，退出码 3")
    p.add_argument("--yuan-per-ktok", type=float, default=None, dest="yuan_per_ktok",
                   help="文本单价（元/千 token）。**网关不公布文本单价，默认不折算金额**；"
                        "填了才出金额，且只是估算")
    _add_json(p)
    if with_out:
        p.add_argument("--out", help="把结果写到这个文件（目录必须存在）")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_chars_opts(p, default_note=True):
    p.add_argument("--chars-min", type=int, default=None, dest="chars_min",
                   help="覆盖字数下限（默认按平台口径%s）" % ("：公众号 2500 / 头条 1800 / 知乎 2500"
                                                              if default_note else ""))
    p.add_argument("--chars-max", type=int, default=None, dest="chars_max",
                   help="覆盖字数上限（默认按平台口径：公众号 4500 / 头条 3500 / 知乎 6000）")


def _add_image_opts(p, with_outdir=True):
    p.add_argument("--image-model", default="nano-banana", dest="image_model",
                   choices=IMAGE_MODELS, help="出图模型，默认 nano-banana")
    p.add_argument("--resolution", default="1K", choices=RESOLUTIONS,
                   help="出图分辨率档，默认 1K（只有 1K 有实测价 24 点/张）")
    p.add_argument("--ratio", default=None,
                   help="出图比例，默认按平台（公众号/头条 16:9、知乎 4:3）；"
                        "可选 %s" % " / ".join(ASPECT_RATIOS))
    p.add_argument("--points-per-image", type=float, default=None, dest="points_per_image",
                   help="单张出图点数（覆盖实测价）。2K/4K 没有实测价，必须传它才给估算")
    p.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_DEFAULT,
                   dest="poll_timeout", help="单张轮询上限（秒），默认 %g" % POLL_TIMEOUT_DEFAULT)
    p.add_argument("--poll-interval", type=float, default=a7w.POLL_INTERVAL,
                   dest="poll_interval", help="轮询间隔（秒），默认 %g" % a7w.POLL_INTERVAL)
    p.add_argument("--submit-timeout", type=float, default=180, dest="submit_timeout",
                   help="提交请求超时（秒），默认 180")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   dest="ratio_tolerance",
                   # 这里要**两层**格式化，所以百分号得写四个：
                   # `... % RATIO_TOLERANCE` 先把 `%g` 填成 0.03，
                   # 之后 argparse 的 HelpFormatter 还会再 `%` 一次 ——
                   # 只写一个 `%` 时第二次会撞上 `%）`，抛
                   # `ValueError: unsupported format character`，
                   # 于是 `images --help` / `all --help` 整条命令崩掉（实测踩到）。
                   help="比例容差，默认 %g（实测上游按 32 对齐，最大偏差 2.86%%%%）"
                        % RATIO_TOLERANCE)
    p.add_argument("--snap", action="store_true",
                   help="出图后按请求比例精确裁剪（本地裁，读文件头复核）")
    p.add_argument("--yes", action="store_true", help="确认真的花钱（不加就只报价）")
    p.add_argument("--state", help="出图断点文件路径，默认 <outdir>/%s" % STATE_NAME)
    p.add_argument("--stop-on-error", action="store_true", dest="stop_on_error",
                   help="一张失败就整体停")
    p.add_argument("--allow-prompt-hits", action="store_true", dest="allow_prompt_hits",
                   help="允许带违禁词/占位符的出图提示词（默认拦截）")
    if with_outdir:
        p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".")
                                               / "longform-images"),
                       help="出图输出目录，默认 %%TEMP%%\\longform-images；**必须不在 Skill 包内**")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 长文自动生产线（api.a7w.cn 的 OpenAI 兼容端点 + nano_banana 出图）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models · "
               "POST https://api.a7w.cn/api/v1/apps/nano_banana/submit · "
               "GET https://api.a7w.cn/api/v1/tasks/<task_id>",
        allow_abbrev=False)
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("outline", help="出选题角度 + 大纲（角度 / 钩子 / 分节 / 计划字数）", allow_abbrev=False)
    p.add_argument("--topic", required=True, help="文章主题")
    p.add_argument("--platform", default="wechat", choices=PLATFORM_CHOICES,
                   help="目标平台：wechat(公众号，默认) / toutiao(头条) / zhihu(知乎)")
    p.add_argument("--angles", type=int, default=4, help="要几个选题角度，默认 4")
    p.add_argument("--sections", type=int, default=5, help="正文分几节，默认 5")
    p.add_argument("--audience", help="受众补充说明（写给谁、什么场景）")
    p.add_argument("--requirements", help="必须覆盖的硬性要求，会原样给到模型")
    p.add_argument("--tone", help="语气/调性，例如「克制、少形容词」")
    _add_model_opts(p)
    p.set_defaults(func=cmd_outline)

    p = sub.add_parser("write", help="按大纲写正文（长文 3000 字级）", allow_abbrev=False)
    p.add_argument("--outline", required=True, help="`outline --json --out` 产出的文件")
    p.add_argument("--topic", help="覆盖大纲里的主题（一般不用传）")
    p.add_argument("--platform", default="wechat", choices=PLATFORM_CHOICES,
                   help="目标平台；给了 --outline 时以大纲里的 platform 为准")
    p.add_argument("--from-file", dest="from_file",
                   help="**闸门复检用**：不调模型，直接拿一份返回 JSON 过闸门")
    p.add_argument("--trust-chars", action="store_true", dest="trust_chars",
                   help="**闸门自检用**：采信产出侧声明的 chars 字段而不是本地数字数"
                        "（用来演示「声明 4000 字、真实几十字」会被抓出来）")
    _add_model_opts(p)
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("images", help="按正文出配图方案 + 出图（先报价，要 --yes）", allow_abbrev=False)
    p.add_argument("--article", help="`write --json --out` 产出的文件")
    p.add_argument("--from-file", dest="from_file",
                   help="**闸门复检用**：直接拿一份配图方案 JSON 过闸门（不调模型）")
    p.add_argument("--topic", help="主题（给配图方案提示词用，可省）")
    p.add_argument("--platform", default="wechat", choices=PLATFORM_CHOICES,
                   help="目标平台，默认 wechat")
    p.add_argument("--count", type=int, default=None,
                   help="最多出几张（**真闸门**，少花钱）。不传就是方案里的实际张数")
    p.add_argument("--allow-article-hits", action="store_true", dest="allow_article_hits",
                   help="正文命中闸门也继续（默认拦截）")
    _add_image_opts(p)
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="出配图方案用的文本模型，默认 %s" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--budget", type=float, default=None,
                   help="出图成本上限（**点**）。超了不提交任何任务，退出码 3")
    p.add_argument("--yuan-per-ktok", type=float, default=None, dest="yuan_per_ktok")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode")
    p.add_argument("--force", action="store_true", help="忽略出图断点重出（**会重复扣费**）")
    p.add_argument("--local-image", dest="local_image", default=None,
                   help="**比例闸门自检用**：拿一张本地图代替出图，只跑「真实像素 vs 请求比例」"
                        "判定（不出网、不花钱、不提交任务）")
    p.add_argument("--out", help="把本次出图摘要写成 JSON 文件（与 stdout 的 JSON 一致）")
    _add_json(p)
    p.set_defaults(func=cmd_images)

    p = sub.add_parser("adapt", help="把长文改写成平台版（公众号 / 头条 / 知乎）", allow_abbrev=False)
    p.add_argument("--article", required=True, help="`write --json --out` 产出的文件")
    p.add_argument("--topic", help="主题（覆盖用）")
    p.add_argument("--platform", default="wechat", choices=PLATFORM_CHOICES,
                   help="目标平台，默认 wechat")
    p.add_argument("--all-platforms", action="store_true", dest="all_platforms",
                   help="三个平台版都出")
    p.add_argument("--from-file", dest="from_file",
                   help="**闸门复检用**：不调模型，直接拿一份返回 JSON 过闸门")
    _add_chars_opts(p)
    _add_model_opts(p)
    p.set_defaults(func=cmd_adapt)

    p = sub.add_parser("all", help="跑完整条链路（大纲 → 正文 → 配图 → 适配），断点续跑", allow_abbrev=False)
    p.add_argument("--topic", required=True, help="文章主题")
    p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".")
                                           / "longform-out"),
                   help="输出目录，默认 %%TEMP%%\\longform-out；**必须在包外**（包内 exit=2）")
    p.add_argument("--img-outdir", dest="img_outdir", default=None,
                   help="配图输出目录，默认 <outdir>/images；**必须在包外**")
    p.add_argument("--platform", default="wechat", choices=PLATFORM_CHOICES,
                   help="目标平台，默认 wechat")
    p.add_argument("--angles", type=int, default=4, help="选题角度数，默认 4")
    p.add_argument("--sections", type=int, default=5, help="正文分节数，默认 5")
    p.add_argument("--audience", help="受众补充说明")
    p.add_argument("--requirements", help="必须覆盖的硬性要求")
    p.add_argument("--tone", help="语气/调性")
    p.add_argument("--images", type=int, default=None, dest="images",
                   help="出几张图；传 0 表示完全跳过配图（不出网、不花钱）")
    p.add_argument("--adapt-all", action="store_true", dest="adapt_all",
                   help="末端把三个平台版都出一遍")
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑（**会重复扣费**）")
    _add_chars_opts(p)
    _add_image_opts(p, with_outdir=False)
    p.add_argument("--model", default=DEFAULT_MODEL, help="文本模型，默认 %s" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--budget", type=float, default=None,
                   help="成本上限。文本按 --yuan-per-ktok 折算成元；出图按**点**。超了就地停")
    p.add_argument("--yuan-per-ktok", type=float, default=None, dest="yuan_per_ktok")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    _add_json(p)
    p.set_defaults(func=cmd_all)

    p = sub.add_parser("cost", help="只算钱，一次调用都不发", allow_abbrev=False)
    p.add_argument("--platform", default="wechat", choices=PLATFORM_CHOICES,
                   help="目标平台，默认 wechat")
    p.add_argument("--sections", type=int, default=5, help="分节数，默认 5")
    p.add_argument("--images", type=int, default=None,
                   help="配图张数，默认取平台建议中值；0 表示不算配图")
    p.add_argument("--all-platforms", action="store_true", dest="all_platforms",
                   help="算三个平台版都出的钱")
    p.add_argument("--adapt-off", action="store_true", dest="adapt_off",
                   help="不算平台适配的钱")
    p.add_argument("--points-per-image", type=float, default=None, dest="points_per_image",
                   help="单张出图点数（覆盖实测价 24 点/张）")
    p.add_argument("--budget", type=float, default=None, help="出图预算上限（**点**），超了退出码 3")
    p.add_argument("--yuan-per-ktok", type=float, default=None, dest="yuan_per_ktok",
                   help="文本单价（元/千 token）。不填就**只出 token 不出金额**")
    p.add_argument("--model", default=DEFAULT_MODEL, help="只是回显，不影响估算")
    _add_chars_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把估算结果写成 JSON 文件（与 stdout 的 JSON 一致）")
    p.set_defaults(func=cmd_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）", allow_abbrev=False)
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
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
    _JSON["pending"] = None
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
    except PackagePathError as exc:
        sys.stderr.write("\n%s\n" % _red(str(exc)))
        rc, kind, msg = 2, "usage", str(exc)
    except LongformGate as exc:
        sys.stderr.write("\n%s\n" % _red(str(exc)))
        rc, kind, msg = 3, "gate", str(exc)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：%s\n" % exc)
        rc, kind, msg = 4, "call", str(exc)
    except KeyboardInterrupt:
        sys.stderr.write("已中断\n")
        rc, kind, msg = 130, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        k = reason.get("kind") or kind or _KIND_BY_EXIT.get(rc, "gate")
        m = reason.get("message") or msg or "命令以退出码 %s 结束（人读原因见 stderr）" % rc
        det = reason.get("detail")
        # 有暂存结果 → 并入 error/exit 一起写（stdout 只有一个 JSON 文档）；
        # 没有暂存结果 → 发独立错误信封。两条路都只调用一次 `_json_write`。
        if _JSON["pending"] is not None and _json_want(a):
            _flush_json(rc, k, m, det)
        else:
            _json_fail(rc, k, m, det, a)
    else:
        _flush_json(0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
