#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 风格克隆体 —— 真正的干活的脚本（零第三方依赖）。

把"一个账号的调性"变成**一组可测量的指标**，然后按指标写、按指标验。

子命令：

    profile   读 3~20 篇样本 → 抽风格档案（纯本地统计，零成本、不调模型）
    write     按风格档案写一篇新稿（要花 token）
    verify    新稿逐指标 vs 档案，给偏差表与通过与否（纯本地，零成本）
    diff      档案 vs 新稿的指标对照表（纯本地，零成本）
    baseline  用样本自身跑一遍指标，给出「自相似阈值」（纯本地，零成本）
    all       抽档 → 写 → 自检 → 迭代（要花 token）
    cost      只算钱（不给单价就只报 token，不编价）
    models    列出当前在架模型

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py profile --samples ./samples --json --out profile.json
    python3 run.py write --profile profile.json --topic "选题" --json --out draft.json
    python3 run.py verify --profile profile.json --result draft.json
    python3 run.py verify --profile profile.json --file 别人的稿子.md   # 反例测试
    python3 run.py diff --profile profile.json --result draft.json
    python3 run.py baseline --samples ./samples
    python3 run.py all --samples ./samples --topic "选题" --outdir D:/out --budget 1
    python3 run.py profile --samples ./samples --dry-run     # 不存在的参数会报错，见文档

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py write ... --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍
    · **风格必须可测量**。档案里没有一项是模型的形容词（"幽默风趣"这种），
      全是能在新稿上重新数一遍的数字：句长均值/标准差、人称占比、标点密度、
      段长、口头禅 n-gram 频次、开场与结尾的句式类别、禁用词表。
      "读起来像"不能当验收标准，因为它不可反驳。
    · **闸门比产出重要**。合规 / 占位符 / 照抄提示词示例 / 风格偏离 / 样本量不足
      都是硬闸门：命中即标红 + stderr 汇总 + 退出码非 0。
    · **反例必须能失败**。verify 对"别的风格"的稿子必须判不通过，
      否则这个包卖的就是"读起来像"。所以基线是**样本自身**的指标分布，
      不是拍脑袋的绝对阈值——见 references/metrics-and-tolerance.md。
    · 违禁词表是**启发式自检**，来自公开经验整理，不构成法律意见。
"""

import argparse
import json
import math
import os
import re
import sys
import traceback
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 不写 __pycache__：SkillHub 的扩展名白名单只放
# .md .py .txt .json .sh .js .yaml .yml .csv，`.pyc` 不在里面。
# 本包目录是"只放文档与脚本"的交付物，跑一次就在里面留两个 .pyc 不合适。
sys.dont_write_bytecode = True
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

EXIT_OK = 0            # 全部干净
EXIT_USAGE = 2         # 参数/配置错误（样本不足 3 篇 / outdir 指到包内 / 文件不存在）
EXIT_GATE = 3          # 有硬闸门命中（合规 / 占位符 / 照抄示例 / 风格偏离 / 结构缺项）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

MIN_SAMPLES = 3        # 样本门槛：少于 3 篇指标不可信，拒绝抽档
MAX_SAMPLES = 20       # 上限：样本太多会让"档案"变成平均值，反而没有调性

SAMPLE_SUFFIXES = (".md", ".txt", ".markdown")

PACKAGE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 风格指标：容差与口径
#
# 这些数字不是审美偏好，是**分布参数**。标定依据见
# references/metrics-and-tolerance.md，简单说：
#   · 句长这类"有自然波动"的指标，用**样本自身的标准差**定带宽，不用绝对百分比
#   · 标点密度 / 口头禅这类"可以为零"的指标，用**感知下限**兜底
#     （因为 0 → 0.3/百字 在相对百分比里是无穷大偏离，但那点差别没人读得出来）
#   · 开场 / 结尾 / 口头禅这类**类别型**指标，只判"类别对不对"，不判程度
# ---------------------------------------------------------------------------

# 句长：用**中位数 + 四分位距**定带宽（抗极值），再取样本内/篇间离散里较小的那一项兜底。
#
# 【为什么不用「均值 ± 2×标准差」】第一版就是这么写的，实测踩坑：
# 样本里有对话体（一句一行、7 个字）也有长段落（40+ 字），句长标准差被拉到 12.5，
# 带宽 ±25.2，下限算出来是 **-1.4 汉字**——这个带宽等于没有：任何句长都通过。
# 中位数与 IQR 对"一句话成段"这种极化分布不敏感，带宽才有判别力。
# 上限 CAPPED 是为了防"样本句长极其整齐 → 带宽趋近 0 → 正常波动全判偏离"。
SENT_BAND_IQR_K = 1.0        # 带宽 = k × IQR
SENT_BAND_CAP = 15.0         # 带宽上限（汉字）
SENT_BAND_FLOOR = 5.0        # 带宽下限
SENT_LO_FLOOR = 4.0          # 允许区间下限不小于这个值（句长不可能 ≤ 0）
# 句长分布形状：短句（≤12）与长句（≥30）占比的**绝对**容差
SHORT_SENT_BAND = 0.15
LONG_SENT_BAND = 0.15
# 标点密度（每百字）：绝对容差 + 相对容差取大者
PUNCT_BAND_ABS = 0.6
PUNCT_BAND_REL = 0.5
# 段落平均长度：相对容差
PARA_BAND_REL = 0.35
PARA_BAND_FLOOR = 8.0        # 汉字
# 人称占比：绝对容差（占比是 0~1 的数，绝对差更好解释）
PERSON_BAND_ABS = 0.20
# 动词/程度/逻辑词 每百字
LEX_BAND_ABS = 0.8
LEX_BAND_REL = 0.5
# 口头禅：档案 top-N 里至少命中这么多个，才算"口头禅对上了"
CATCHPHRASE_MIN_HIT = 2

# --- 容差自标定（见 calibrate()）-------------------------------------------------
# 每个指标的容许偏差 = band × dev_limit，dev_limit 由**样本自身**的偏差分布定。
DEFAULT_DEV_LIMIT = 1.0    # 下限：至少 1 倍带宽，不能比"贴着档案算"更严
MAX_DEV_LIMIT = 2.0        # 上限：自标定最多把带宽放宽到 2 倍
SAFETY = 1.5               # 样本观测到的最大相对偏差 × 这个系数（留出未见样本的余量）
DEFAULT_DEV_LIMIT_FALLBACK = DEFAULT_DEV_LIMIT
# 口头禅提取的 n-gram 长度
NGRAM_SIZES = (3, 4, 5, 6)
# 口头禅的虚词黑名单：这些 ng 到处都是，不构成"调性"
NGRAM_STOP = set("的了是在和与也就都还很更要会能可以把被从对为以及这个那个我们你们他们一个"
                 "什么怎么因为所以但是而且如果就是不是没有可以自己这样那样时候问题东西"
                 "知道觉得可能应该需要直接其实真的已经一直一样比如例如另外此外因此于是"
                 "一二三四五六七八九十")
# 汉字的区间（用来数"汉字数"，标点与英文不算）
HAN_RE = re.compile(r"[\u4e00-\u9fff]")

# 人称词表
PERSON_WORDS = {
    "first": ("我们", "我", "咱", "俺"),
    "second": ("你们", "你", "您"),
    "third": ("他们", "她们", "他", "她", "它"),
}
# 典型词汇组：每组是"一眼能看出调性"的词
LEX_GROUPS = {
    "hedge": ("其实", "大概", "差不多", "应该是", "可能", "也许", "说白了"),
    "contrast": ("但", "但是", "不过", "然而", "其实"),
    "enumeration": ("第一", "第二", "第三", "首先", "其次", "最后"),
    "transition": ("于是", "然后", "接着", "所以", "因此", "结果"),
    "metaphor": ("像", "似的", "仿佛", "好比"),
}
# 标点密度统计哪些
PUNCT_KINDS = {
    "exclaim": ("！", "!"),
    "question": ("？", "?"),
    "ellipsis": ("……", "…", "..."),
    "dash": ("——", "—"),
    "colon": ("：", ":"),
    "quote": ("“", "”", "\""),
    "comma": ("，", ","),
    "enum_comma": ("、",),
}
# 段落开头序数词（"一、" / "1." / "第一，"）
ORDINAL_HEAD_RE = re.compile(r"^\s*(?:[一二三四五六七八九十]+[、.．]|[0-9]{1,2}[、.．]|第[一二三四五六七八九十0-9]+(?:点|条|步|章|节|部分)?[，,、.．])")

# 开场句式类别（只判类别，不判具体句子）——正则顺序即优先级。
# 判的是**开场段**（第一个正文段落），不是切出来的第一句：本族样本里
# 「上周三下午，一个开火锅店的老板把我叫到店里…」是场景类，但如果只取第一句
# 且它前面挂着标题，就会全落到"陈述式"。实测 6/6 篇误判，所以改成判开场段。
OPENING_PATTERNS = [
    ("疑问式", r"[？?]|^\s*(?:为什么|怎么|如何|是不是|有没有)"),
    ("场景对白", r"^[“\"「]|(?:说|问|喊|告诉我|打电话|发消息|在群里)[：:，,]|"
                 r"把我叫到|找到我|问我"),
    ("时间切入", r"^\s*(?:昨天|今天|前天|上周|上个月|去年|今年|那天|前几天|有一次|"
                 r"上上?周[一二三四五六日天]|周[一二三四五六日天]|"
                 r"[0-9]{4}\s*年|[0-9]{1,2}\s*月|[0-9]{1,2}\s*点)"),
    ("第一人称叙事", r"^\s*(?:我|咱|我们|俺)"),
    ("共鸣现象式", r"^\s*(?:很多人|大家|大多数人|不少人|你是不是|有没有人)"),
    ("数据切入", r"^\s*(?:[0-9]{1,4}|百分之|超过|近|约)[^，。]{0,20}[%％个条次倍元万字]"),
    ("结论前置", r"^\s*(?:先说|结论|答案|一句话|说白了|直接说)"),
    ("定义陈述", r"^[^。！？]{4,30}(?:是|属于|指|是一种|的本质|的问题)"),
]
OPENING_TYPES = [n for n, _ in OPENING_PATTERNS]
OPENING_RE = [(n, re.compile(p)) for n, p in OPENING_PATTERNS]
# 结尾句式类别
ENDING_PATTERNS = [
    ("行动召唤", r"(?:关注|点赞|收藏|评论|留言|转发|私信|加我|扣\s*1|说说|聊聊|告诉我|你怎么看|欢迎补充|在看|分享)"),
    ("鼓励收束", r"(?:也可以|都能|就够了|来得及|不用怕|值得|试试|慢慢来|别急|没关系)"),
    ("价值升华", r"(?:本质上|归根到底|说到底|真正|重要的不是|比起|与其)"),
    ("留白/反问", r"[？?]\s*$"),
    ("总结归纳", r"(?:所以|因此|总之|一句话|归根到底|总结)"),
    ("回扣开头", r"(?:回到开头|还记得|就像开头|开头那句)"),
]
ENDING_TYPES = [n for n, _ in ENDING_PATTERNS]
ENDING_RE = [(n, re.compile(p)) for n, p in ENDING_PATTERNS]


# ---------------------------------------------------------------------------
# 合规自检：广告法违禁词表（确定性，零成本，不依赖模型）
#
# 与全族同一张表、同一口径。ctx 字段标记是否需要走「数据极值」语境豁免。
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎)", "高",
     "广告法第九条禁止「最高级」用语", "superlative"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证", None),
    # 「第一」加了两组排除：`第一次` 是时间序数，`第一步` 是步骤序数，两者都不是
    # 排他性宣称。第一版只有 `(?!次)`，实测把「我见过太多同行栽在第一步」判成
    # 高风险广告法命中，整篇被拦 —— 是**在真机跑出来的误伤**，不是想出来的。
    (r"排名第一|销量第一|口碑第一|行业第一|全国第一|全网第一|全球第一|世界第一|第一品牌|第一选择", "高", "「第一」类排他性表述", None),
    (r"国家级|世界级|全球级|国际级|国家级产品", "高",
     "「国家级」等权威性词汇属明令禁止", None),
    (r"100\s*%|百分之百|百分百", "高",
     "绝对化效果承诺", None),
    (r"绝对(有效|安全|放心|不会|能|可以)|保证(有效|成功|瘦|赚)|无效退款", "高",
     "绝对化保证与效果担保", None),
    (r"根治|治愈|痊愈|药到病除|包治|治疗(好|效果)|疗效|无副作用|零副作用", "高",
     "医疗功效宣称，非药品/医疗器械不得使用", None),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报", "高",
     "投资类收益承诺", None),
    (r"免费领|免费送|0\s*元购|白送", "中",
     "可能构成虚假优惠或诱导分享", None),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天", "中",
     "促销时限表述需与实际活动一致", None),
    (r"独家|唯一|首个|首创|填补空白|领先(品牌|技术)", "中",
     "排他性表述需有可举证依据", None),
    (r"纯天然|无添加|零添加|无毒无害", "中",
     "成分宣称需与检测报告一致", None),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐", "高",
     "不得虚构权威背书", None),
    (r"催情|壮阳|丰胸|减肥(药|神器)|美白针|生发(神器)", "高",
     "特殊功效与特殊品类敏感词", None),
    (r"点击链接|加微信|私信我|扫码(加|进)|vx|VX|微信号", "中",
     "站外导流，平台普遍限制", None),
    (r"[！!]{2,}|[?？]{3,}", "低",
     "标点堆砌，易被判标题党/低质", None),
    (r"(震惊|惊呆|不看后悔|错过再等一年|速看|删前必看)", "中",
     "标题党式诱导", None),
]
BANNED_RE = [(re.compile(p), lvl, why, ctx) for p, lvl, why, ctx in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}

# ---------------------------------------------------------------------------
# 「最高级」用语的语境豁免（照抄同族口径，**这是被实测误伤逼出来的**）
#
# 事故复盘（全族共用）：真实原稿里写「回头翻一条自己播放量最低的视频」，
# 被本地闸门判成高风险「广告法第九条禁止最高级用语」并整篇拦截。
# 这个诊断是**错的**——那是在描述自己的数据，不是商品/服务宣称。
# 一个正确写法的稿子被判违规，使用者就会开始无视闸门，闸门等于废了。
#
# 豁免条件刻意做得**很窄**：
#   · `最X` 前一个字是计量类名词（量/率/数/分/位/条/次/段/部/集/页/个/天/月/年）
#   · 且 `最X` 后面紧跟「的」或「之」
#   · **句首（前面没有字符）一律不豁免** —— `最好的产品` 出现在句首时必须照拦
# 命中豁免时整处放过，但在报告里登记（`gates.compliance.exempted`），**不静默放过**。
# 豁免词表刻意不含 `时`/`款`/`种`/`家`/`价`：「课时最低」「单价最低」必须照拦。
# ---------------------------------------------------------------------------

MEASURE_PREFIX = "量率数分位条次段部集页个天月年"


def _is_data_extreme(text, m):
    """`最X` 是不是在描述数据极值（而不是商品宣称）？"""
    start, end = m.start(), m.end()
    before = text[start - 1] if start > 0 else ""
    after = text[end:end + 1]
    # 注意 `before and`：空字符串在 Python 里 `"" in "量率数…"` 是 True，
    # 漏了这一步，**句首的「最好/最低」会被全部误豁免**。
    return bool(before) and before in MEASURE_PREFIX and after in ("的", "之")


# ---------------------------------------------------------------------------
# 占位符残留
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    (r"\{\s*[^{}\n]{0,40}\s*\}", "残留了 `{}` 占位符，模板没被替换干净"),
    (r"\[\s*(?:待填|待补|填写|请填|待定|TODO|TBD)[^\]]{0,40}\]", "残留了 `[待填]` 一类占位符"),
    (r"XXX+|xxx+", "残留了 `XXX` 占位符"),
    (r"（\s*此处省略[^）]*）|\(\s*此处省略[^)]*\)", "残留了「（此处省略）」占位符"),
    (r"待补充|待补齐|此处待补", "残留了「待补充」占位符"),
    (r"\bTODO\b|\bTBD\b", "残留了 TODO/TBD 标记"),
    (r"【[^】]{0,20}(?:待|请)[^】]{0,20}】", "残留了【待填】一类占位符"),
]
PLACEHOLDER_RE = [(re.compile(p), why) for p, why in PLACEHOLDER_PATTERNS]


# ---------------------------------------------------------------------------
# prompt_echo：照抄提示词示例
#
# 三条判据（全族统一口径，别自创）：
#   · exact   —— 去掉标点后完全相同
#   · jaccard —— 字符二元组 Jaccard ≥ ECHO_SIM
#   · contain —— 示例的二元组**覆盖度** ≥ ECHO_CONTAIN
#
# 【为什么必须有第三条】Jaccard 的分母是并集，产出越长示例被摊得越狠。
# 实测（同族）：示例原样嵌进 24 字标题里只有 0.696（旧判据放行），覆盖度却是 1.000。
# 【为什么长度门槛是相对值】绝对阈值会随示例长度变化而失效，
# 所以用 `max(6, len(示例)//2)`。
#
# 本包的特殊之处：**提示词里确实会放样本**（每个样本的开场句与结尾句，最多 2N 句），
# 所以这道闸门在本包里不是"防意外"，是"防必然"——不设它，模型把样本原句抄进新稿
# 是最省力的写法，而那样产出的东西恰恰是这个包最该拦下的东西。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6
# 长度守卫（**相对阈值**）+ 覆盖度适用窗口。两条都是实测标定出来的。
#
# ① 目标长度门槛 = max(6, 示例长度 // 2)。短串的二元组太少，指标会虚高。
#
# ② 覆盖度只在**目标长度 ≤ 1.5 × 示例长度**（ECHO_CONTAIN_MAX_RATIO）时参与判定。
#
# 【这是本包真机跑出来的坑，必须写下来】第一版没有这条限制，结果是：
# 正文全篇（1796 字）与示例（16 字）比，覆盖度算出 **0.60**，闸门报
# 「正文有 60% 的内容来自提示词示例「没关系，第一步本来就是这样走出来的。」」
# —— 而正文里与那句示例唯一的重合只有「第一步」三个字。
# 根因：二元组集合的**并集**随文本变长迅速饱和。只要目标足够长，示例那 16 个
# 二元组几乎总会被"顺带覆盖"到，覆盖度趋近 1 是**必然**，不是抄袭。
# 标定数据（`_styleclone_test/echo_calib.py`，817 组真实非照抄比对）：
#   · 逐句比：contain 最大 **0.200**（p99 0.133、中位 0.000）—— 与 0.60 有 3 倍余量
#   · 整篇比：contain 中位 **0.302**、最大 0.600 —— 与阈值零余量，必然误报
# 所以覆盖度的适用单位是「句 / 段」级别的可比长度，不是整篇。
# 加窗口后逐句判据的余量一点没变（样本原句照抄仍是 1.000），
# 而"整篇 vs 短示例"这种必然误报被关掉。
ECHO_CONTAIN_MAX_RATIO = 1.5
# 片段级判据阈值（`_ordered_coverage`：等长窗口 + 顺序匹配）。
# 单独标定：非照抄的 817 组比对里该项最大 **0.286**，而"原句 + 补几个字"是 **1.000**。
# 定 0.75，两侧余量都在 2.6 倍以上。
ECHO_FRAGMENT = 0.75
# 样本自相似阈值的取法：阈值 = 两两相似度的最小值 × 这个比例。
# 0.5 的依据见 style_distance() 的实测标定（同风格 min 0.096 · 混样本 min 0.0067）。
SELF_SIM_MIN_RATIO = 0.5
# 本包**不**把样本正文放进提示词，只放开场/结尾句，所以比对单位是"句"。
# 正文整体相似度另有一条独立的防抄袭闸门（见 SAMPLE_OVERLAP_*）。
SAMPLE_OVERLAP_WARN = 0.35   # 新稿与**样本全文**的二元组 Jaccard 警告线
SAMPLE_OVERLAP_FAIL = 0.50   # 超过这条线 = 换皮样本，直接拦

_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的产出往往只改标点（`，`↔`、`↔空格`），所以必须先抹平标点再看。
    """
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


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


def _bigram_seq(s):
    """按出现顺序的二元组序列（**元素是二元组本身的字符串**，不是编号）。

    为什么不能编号：第一版给每个二元组分配一个递增整数 id，结果
    「示例的 16 个二元组」变成「16 个整数 0..15」，而**任何**长度 ≥ 16 的目标里
    都必然能找到一串"相似"的整数序列，LCS 直接算成 1.000 —— 非照抄语句
    100% 判为照抄，判据完全失效。这是自测时用 133 条非照抄语句量出来的
    （975 条组合里 cov≥0.5，且大量 1.000），不是看代码看出来的。
    用二元组字符串本身，匹配才是真的匹配。
    """
    s = _norm_for_echo(s)
    if len(s) < 2:
        return []
    return [s[i:i + 2] for i in range(len(s) - 1)]


def _lcs_len(a, b):
    """最长公共子序列长度（滚动数组 DP）。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            cur[j] = prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def _ordered_coverage(target, sample):
    """把示例（归一化后）当模板，在目标上滑一个**等长**窗口，
    返回窗口与示例的**最长公共子序列**占示例长度的比例，取各窗口最大值（0~1）。

    这是覆盖度的**有序版**，本包用它抓「整句被搬进更长的句子里」这个真实抄法。

    **为什么不用集合版覆盖度**：集合的并集随目标变长迅速饱和，整篇 vs 短示例
    必然报 0.6+（见 ECHO_CONTAIN_MAX_RATIO 上方的事故复盘）。

    **为什么用 LCS 而不是贪心顺序匹配**：第一版用 `list.index(...)` 贪心不回退，
    方向是对的（不回退保证了顺序），但实测在长句上**直接爆成 1.000**——
    非照抄语句无论怎么测都是满分，判据等于没有。LCS 是贪心的正确版本：
    它保证"顺序 + 最大匹配数"，不会把零散单字凑成一整句。
    """
    t = _norm_for_echo(target)
    s = _norm_for_echo(sample)
    if len(s) < 2 or len(t) < len(s):
        return 0.0
    sseq = _bigram_seq(sample)
    if not sseq:
        return 0.0
    width = len(s)
    need = float(len(sseq))
    best = 0.0
    for start in range(0, len(t) - width + 1):
        wseq = _bigram_seq(t[start:start + width])
        cov = _lcs_len(sseq, wseq) / need
        if cov > best:
            best = cov
            if best >= 0.999:
                break
    return best


def prompt_echo(text, samples, use_contain=True):
    """文本是否与提示词里的示例"抄得太近"。

    判据（任一命中）：
      · 去掉标点后**完全相同**（最直接的照抄）
      · 字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
      · 示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（把示例夹带进更长的句子里；
        Jaccard 会被长度摊薄，只有覆盖度抓得住）

    `use_contain=False` 时**关掉覆盖度**（只留 exact / jaccard）。
    整篇级别的比对必须关掉它 —— 理由见 ECHO_CONTAIN_MAX_RATIO 上方那段事故复盘。
    """
    target = _norm_for_echo(text)
    if not target:
        return False, 0.0, "", ""
    best_score, best_sample, best_rule = 0.0, "", ""
    for s in samples or ():
        if not s:
            continue
        ns = _norm_for_echo(s)
        if target == ns:
            return True, 1.0, s, "exact"
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(text, s)
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        if not use_contain:
            continue
        # 覆盖度适用窗口：目标长度不超过示例的 ECHO_CONTAIN_MAX_RATIO 倍
        if len(target) > ECHO_CONTAIN_MAX_RATIO * len(ns):
            continue
        base = _bigrams(s)
        contain = (len(_bigrams(text) & base) / float(len(base))) if base else 0.0
        if contain >= ECHO_CONTAIN and contain >= best_score:
            best_score, best_sample, best_rule = contain, s, "contain"
    if best_rule:
        return True, best_score, best_sample, best_rule
    return False, best_score, best_sample, ""


def fragment_echo(text, samples, label="正文（片段级）"):
    """**片段级**照抄检查：示例被整段搬进一个更长的句子里。

    为什么单列一条（真机上踩出来的漏洞）：
    把示例原句后面接几个字，例如
        `…就是没关系，第一步本来就是这样走出来的这个道理。`
    这时
      · exact   —— 不成立（不是完全相同）
      · jaccard —— 0.53（长度差把并集撑大，够不到 0.75）
      · contain —— 被 ECHO_CONTAIN_MAX_RATIO 窗口挡住（目标 37 字 > 示例 16×1.5=24）
    三条判据全漏，而人眼一看就知道是抄的。
    判据换成 `_ordered_coverage`（等长窗口 + 顺序匹配）后这一例是 1.000。
    """
    hits = []
    t = _norm_for_echo(text)
    if len(t) < 8:
        return hits
    for s in samples or ():
        if not s:
            continue
        ns = _norm_for_echo(s)
        if len(ns) < 8 or len(t) < len(ns):
            continue
        cov = _ordered_coverage(text, s)
        if cov >= ECHO_FRAGMENT:
            hits.append({
                "rule": "fragment", "score": round(cov, 3), "sample": s,
                "why": "{}里有 {:.0f}% 的「{}」被**按原顺序**搬了过来"
                       "（等长窗口 + 顺序匹配 ≥ {:.2f} 即判片段照抄）".format(
                           label, cov * 100, s, ECHO_FRAGMENT),
            })
            break
    return hits


def prompt_echo_scan(text, samples, label="正文"):
    """两层都查：**整段一次（只比 exact/jaccard）+ 逐句一次（三条判据全上）**。

    事故复盘（同族）：只比"整段正文"是不够的——正文 1000 字、示例二三十字时
    Jaccard 的分母被撑到 1000 多，**模型把示例原样抄进正文的某一段时这道闸门完全看不见**。
    而长文场景下"抄示例"恰恰就是"有一段是抄的"。所以整段比一次、逐句再比一次。

    本包又补了一层：**整段那一次必须关掉覆盖度**。
    覆盖度在"整篇 vs 短示例"上会必然误报（见 ECHO_CONTAIN_MAX_RATIO 上方）。
    """
    hits = []
    ok, score, sample, rule = prompt_echo(text, samples, use_contain=False)
    if ok:
        hits.append(_echo_hit(label, score, sample, rule))
    for sent in split_sentences(text):
        if len(_norm_for_echo(sent)) < 8:
            continue
        ok, score, sample, rule = prompt_echo(sent, samples)
        if ok:
            h = _echo_hit(label + "（逐句）", score, sample, rule)
            if h["why"] not in [x["why"] for x in hits]:
                hits.append(h)
            continue
        # 三条判据都没抓住时，再上片段级判据（整句被搬进更长的句子里）
        for h in fragment_echo(sent, samples, label + "（片段级）"):
            if h["why"] not in [x["why"] for x in hits]:
                hits.append(h)
    return hits


def _echo_hit(label, score, sample, rule):
    if rule == "exact":
        why = "{}与提示词示例「{}」去掉标点后完全相同（照抄示例）".format(label, sample)
    elif rule == "contain":
        why = ("{}有 {:.0f}% 的内容来自提示词示例「{}」（覆盖度 ≥ {:.2f} 即判照抄；"
               "Jaccard 会随产出变长被摊薄）").format(label, score * 100, sample, ECHO_CONTAIN)
    else:
        why = "{}与提示词示例「{}」相似度 {:.2f}，属同构照抄".format(label, sample, score)
    return {"rule": rule, "score": round(score, 3), "sample": sample, "why": why}


def sample_overlap(text, sample_texts):
    """新稿与**样本全文**的相似度最高值（防"换皮样本"）。

    与 prompt_echo 的区别：prompt_echo 比的是"提示词里放过的示例句"，
    这里比的是"样本全文"。模型没看到全文也可能撞上，所以这是一道独立闸门。
    """
    best = 0.0
    who = ""
    for i, s in enumerate(sample_texts or (), 1):
        sim = _similarity(text, s)
        if sim > best:
            best, who = sim, "样本 {}".format(i)
    return best, who


# ---------------------------------------------------------------------------
# 合规 / 占位符 / 结构 闸门
# ---------------------------------------------------------------------------

def compliance_scan(text):
    """扫违禁词。返回 {"hits": [...], "exempted": [...]}。

    hits 是硬闸门拦截项；exempted 是语境判断为"在说数据极值"的疑似项，
    放过但登记，**不静默放过**。
    """
    text = text or ""
    hits, exempted = [], []
    for rx, lvl, why, ctx in BANNED_RE:
        m = rx.search(text)
        if not m:
            continue
        if ctx == "superlative" and _is_data_extreme(text, m):
            exempted.append({
                "word": m.group(0),
                "why": "疑似绝对化用语，但前一个字是计量类名词、后面紧跟「的/之」，"
                       "判断为在描述数据极值（不是商品/服务宣称）——本地放过，请人工确认",
                "context": text[max(0, m.start() - 10):m.end() + 10],
            })
            continue
        hits.append({"word": m.group(0), "level": lvl, "why": why})
    seen, out = set(), []
    for h in hits:
        if h["word"] in seen:
            continue
        seen.add(h["word"])
        out.append(h)
    out.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return {"hits": out, "exempted": exempted}


def placeholder_scan(text):
    hits = []
    for rx, why in PLACEHOLDER_RE:
        m = rx.search(text or "")
        if m:
            hits.append({"found": m.group(0)[:30], "why": why})
    return hits


def structure_gate(title, body):
    """结构闸门：必须有标题 + 正文，正文至少 2 段、至少 200 汉字。

    为什么 200 字是硬线：样本量指标全部建立在"有足够句子"之上。
    一段 80 字的产出算不出句长分布，硬留在"通过"里只会让报告骗人。
    """
    missing = []
    t = (title or "").strip()
    b = (body or "").strip()
    if not t:
        missing.append("标题")
    paras = split_paragraphs(b)
    if len(paras) < 2:
        missing.append("正文至少 2 段")
    if han_len(b) < 200:
        missing.append("正文至少 200 汉字（当前 {}）".format(han_len(b)))
    return len(missing) == 0, {"missing": missing, "paras": len(paras), "han": han_len(b)}


# ---------------------------------------------------------------------------
# 文本切分与基础计数
# ---------------------------------------------------------------------------

_MD_NOISE_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)]|>|#{1,6})\s*", re.M)


def _strip_md(text):
    """抹掉 Markdown 结构噪声：标题井号、引用符、列表符、行内强调符、链接地址、表格线。

    为什么要抹：`### 一、xxx` 里的 `###` 会把"段落第一个字"算成 `#`，
    开场句式判定就会全部落到"定义陈述"上。**这是数出来的坑，不是想出来的**。
    """
    t = text or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^\s*\|.*\|\s*$", " ", t, flags=re.M)
    t = re.sub(r"^\s*[-*_=]{3,}\s*$", " ", t, flags=re.M)
    t = _MD_NOISE_RE.sub("", t)
    t = t.replace("**", "").replace("__", "").replace("`", "")
    t = re.sub(r"[ \t\u3000]+", " ", t)
    return t


def split_paragraphs(text):
    """按空行切段；单换行不切段（本族样本里单换行大量用于短句成行）。"""
    t = _strip_md(text)
    raw = re.split(r"\n\s*\n+", t)
    out = []
    for p in raw:
        p = " ".join(p.split())
        if han_len(p) >= 4:
            out.append(p)
    return out


def split_sentences(text):
    """切句：在 。！？； 与换行处切，**不在逗号处切**（与全族口径一致）。

    **标题行（`## 第 1 篇｜…`）不算句子**。第一版没排除，结果标题被并进开场句，
    开场句式判定全部落到"陈述式"（实测 6/6 篇），而且标题里的 `30秒`／`vr`
    被当成口头禅混进 top-5 —— 这是数出来的坑。
    """
    t = _strip_md(text)
    out = []
    for line in t.splitlines():
        c0 = line.strip()
        if not c0:
            continue
        if _looks_like_title(c0):
            continue
        for chunk in _SENT_SPLIT.split(c0):
            if chunk is None:
                continue
            c = " ".join(chunk.split())
            if han_len(c) >= 2:
                out.append(c)
    return out


def _looks_like_title(line):
    """这一行是不是"文章标题"而不是正文？

    本族样本的形态：`## 第 N 篇｜xxx`、`# xxx`、`## xxx`，或第一行没有句末标点
    且很短（≤ 40 汉字）。判据刻意保守：宁可把一段短正文当标题丢掉一句，
    也不要把标题混进正文指标里 —— 标题的句长/人称与正文完全是两种分布。
    """
    if re.match(r"^\s*#{1,6}\s", line):
        return True
    if re.match(r"^\s*第\s*\d+\s*篇", line):
        return True
    if han_len(line) <= 40 and not re.search(r"[。！？；，]", line):
        return True
    return False


def first_paragraph(text):
    """真正的开场段：第一个被 `_looks_like_title` 之外、汉字 ≥ 8 的段落。"""
    for p in split_paragraphs(text):
        if _looks_like_title(p):
            continue
        if han_len(p) >= 8:
            return p
    return ""


def han_len(s):
    """汉字数（标点、空格、英文、数字都不算）。风格指标全部以汉字数为口径。"""
    return len(HAN_RE.findall(s or ""))


def count_chars(s):
    """原始字符数（含标点换行）——算 token 与字数上限时用这个。"""
    return len(s or "")


def _sent_lens(sentences):
    out = []
    for s in sentences:
        n = han_len(re.sub(r"^[^，。！？]{0,6}(?=[，。！？])", "", s)) or han_len(s)
        if n >= 2:
            out.append(n)
    return out


def mean(xs):
    return sum(xs) / float(len(xs)) if xs else 0.0


def stdev(xs):
    """样本标准差。样本 < 2 时返回 0。"""
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / float(len(xs) - 1))


def median(xs):
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    return float(s[n // 2]) if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def percentile(xs, q):
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


# ---------------------------------------------------------------------------
# 指标计算：把一篇（或一组）文本变成一组数字
# ---------------------------------------------------------------------------

def _punct_rates(text):
    """每百字标点密度。**先剔除标点堆砌类重复**再算，避免 `！！！` 把密度拉爆。"""
    n = max(1, han_len(text))
    rates = {}
    for kind, marks in PUNCT_KINDS.items():
        c = 0
        for mk in marks:
            c += text.count(mk)
        rates[kind] = round(c * 100.0 / n, 3)
    # 总标点密度（中文标点全集）
    total = len(re.findall(r"[，。！？；：、“”‘’（）《》〈〉【】…—·、]", text))
    rates["total"] = round(total * 100.0 / n, 3)
    return rates


def _person_stats(text):
    """人称占比。占比的分母是"人称词总出现次数"，不是字数——
    所以它是"这篇稿子里说话的方式"，与长短无关。"""
    counts = {}
    total = 0
    for key, words in PERSON_WORDS.items():
        c = 0
        for w in words:
            c += len(re.findall(re.escape(w), text))
        counts[key] = c
        total += c
    frac = {}
    for key in PERSON_WORDS:
        frac[key] = round(counts[key] / float(total), 4) if total else 0.0
    dom = max(frac, key=lambda k: frac[k]) if total else "none"
    # 第一人称压倒性时（≥0.6）单列，因为那是"自述体"最明显的标志
    return {"counts": counts, "total": total, "frac": frac, "dominant": dom}


def _lex_rates(text):
    """典型词组的每百字密度 + 高频词表（用于"禁用词"反查）。"""
    n = max(1, han_len(text))
    out = {}
    for group, words in LEX_GROUPS.items():
        c = 0
        for w in words:
            c += len(re.findall(re.escape(w), text))
        out[group] = round(c * 100.0 / n, 3)
    return out


def _ngram_counts(texts, sizes=NGRAM_SIZES):
    """跨全部文本统计 n-gram 频次。**只在句子内统计**，跨句的 n-gram 不是口头禅。"""
    cnt = {}
    for t in texts:
        for sent in split_sentences(t):
            s = _norm_for_echo(sent)
            for k in sizes:
                for i in range(len(s) - k + 1):
                    g = s[i:i + k]
                    if _ngram_stop(g):
                        continue
                    cnt[g] = cnt.get(g, 0) + 1
        # 段落开头也统计（"一、" 这类分段习惯）
        for p in split_paragraphs(t):
            m = ORDINAL_HEAD_RE.match(p)
            if m:
                cnt[m.group(0).strip()] = cnt.get(m.group(0).strip(), 0) + 1
    return cnt


def _ngram_stop(g):
    if g in NGRAM_STOP:
        return True
    # **必须是纯汉字**。第一版只要求"含汉字"，结果 `30秒`、`视频超清vr` 这类
    # 半截词混进了 top-5 口头禅——数字与拉丁字母夹在中文里，几乎必然是
    # 拉丁/数字被切开的产物，不是口头禅。
    if not all("\u4e00" <= ch <= "\u9fff" for ch in g):
        return True
    # 全是虚词/标点的组合也丢掉
    if all(ch in NGRAM_STOP for ch in g):
        return True
    return False


def pick_catchphrases(cnt, sample_count, top=5, min_df=2):
    """选口头禅：优先**跨篇复现**的（文档频率高），其次看总频次。

    为什么要文档频率优先：只在某一篇里重复 8 次的词组，是那篇的内容词；
    出现在 4 篇里的词组，才是这个作者的口头禅。**这是"调性"与"选题"的分界**。
    """
    # 文档频率：重新统计每个 ng 出现在几篇里
    df = cnt.get("__df__") if isinstance(cnt, dict) else None
    items = []
    for g, c in cnt.items():
        if g.startswith("__"):
            continue
        d = (df or {}).get(g, 0)
        # 被更长的高频 ng 完全包含的短 ng，降权（否则 3-gram 会把 5-gram 的口头禅挤掉）
        items.append({"ng": g, "count": c, "df": d,
                      "score": d * 2.0 + min(c, 10) * 0.5 + len(g) * 0.1})
    items.sort(key=lambda x: (-x["score"], -x["count"], -len(x["ng"])))
    chosen = []
    for it in items:
        if it["df"] < min_df and sample_count >= min_df:
            continue
        g = it["ng"]
        # 双向去重：`视频超清` 与 `频超清x` 这种"同一处的两个窗口"要只留一个。
        # 只做单向（新的是旧的子串）会漏掉反向包含，实测就漏过一对。
        if any(g in c["ng"] or c["ng"] in g for c in chosen):
            continue
        chosen.append(it)
        if len(chosen) >= top:
            break
    return chosen


def _ngram_df(texts, sizes=NGRAM_SIZES):
    df = {}
    cnt = {}
    for t in texts:
        seen = set()
        for sent in split_sentences(t):
            s = _norm_for_echo(sent)
            for k in sizes:
                for i in range(len(s) - k + 1):
                    g = s[i:i + k]
                    if _ngram_stop(g):
                        continue
                    cnt[g] = cnt.get(g, 0) + 1
                    seen.add(g)
        for g in seen:
            df[g] = df.get(g, 0) + 1
    cnt["__df__"] = df
    return cnt


def classify_opening(text):
    t = (text or "").strip().lstrip("“\"'「『")
    for name, rx in OPENING_RE:
        if rx.search(t):
            return name
    return "陈述式"


def classify_ending(text):
    t = (text or "").strip()
    for name, rx in ENDING_RE:
        if rx.search(t):
            return name
    return "平铺收束"


def style_markers(text):
    """风格指纹：只留**风格性**二字组。

    做法：切句 → 抹标点 → 逐句抽二元组 → 丢掉跨句重复（那是内容词，不是调性）
    → 丢掉含虚词黑名单字符的组合。剩下的是"这个作者说话的习惯"。
    **不用它做绝对判断，只用来算样本之间的两两相似度**，得出"自相似基线"。
    """
    per_sent = []
    for sent in split_sentences(text):
        s = _norm_for_echo(sent)
        per_sent.append({s[i:i + 2] for i in range(len(s) - 1)})
    cnt = {}
    for bg in per_sent:
        for g in bg:
            cnt[g] = cnt.get(g, 0) + 1
    markers = set()
    for g, c in cnt.items():
        if c > 1:
            continue                      # 同句重复 = 内容词
        if any(ch in NGRAM_STOP for ch in g):
            continue
        markers.add(g)
    return markers


def style_distance(texts):
    """两两相似度矩阵的统计量（样本自相似基线）。

    returns：pairwise / mean / min / max / **threshold** / mix_flag / floor。

    `threshold` = 两两相似度的最小值 × SELF_SIM_MIN_RATIO（本包取 0.5）。
    **这是"算不算同一个账号"的经验下界，由样本自身算出来，不是拍脑袋定的绝对值。**

    标定依据（`_styleclone_test/marker_calib.py`，实测）：
      · 同风格 6 篇：mean 0.127、**min 0.096**
      · 跨风格两两：mean 0.010、max 0.019（与同风格最近的一对差 5 倍以上）
      · 5 篇同风格 + 混进 1 篇异风格：mean 0.088、**min 0.0067** → 触发混样本提示
    """
    sets = [style_markers(t) for t in texts]
    pairs = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            a, b = sets[i], sets[j]
            if not a or not b:
                continue
            jac = len(a & b) / float(len(a | b))
            pairs.append({"a": i + 1, "b": j + 1, "sim": round(jac, 4)})
    sims = [p["sim"] for p in pairs]
    mn = min(sims) if sims else 0.0
    me = mean(sims) if sims else 0.0
    mix = bool(sims) and mn < SELF_SIM_MIN_RATIO * me
    return {
        "pairwise": pairs,
        "pairs": len(pairs),
        "mean": round(me, 4),
        "min": round(mn, 4),
        "max": round(max(sims), 4) if sims else 0.0,
        "threshold": round(mn * SELF_SIM_MIN_RATIO, 4),
        "min_ratio": SELF_SIM_MIN_RATIO,
        "mix_flagged": mix,
        "mix_pair": next((p for p in pairs if p["sim"] == mn), None),
    }


def analyze_text(text):
    """把一篇文本变成一组**可再次测量**的指标。"""
    text = text or ""
    sents = split_sentences(text)
    lens = _sent_lens(sents)
    paras = split_paragraphs(text)
    para_lens = [han_len(p) for p in paras]
    n = max(1, han_len(text))
    open_para = first_paragraph(text)
    open_sent = ""
    for chunk in _SENT_SPLIT.split(open_para):
        if han_len(chunk) >= 2:
            open_sent = chunk.strip()
            break
    return {
        "han": han_len(text),
        "chars": count_chars(text),
        "sentences": len(sents),
        "paragraphs": len(paras),
        "sent_len": {
            "mean": round(mean(lens), 2),
            "stdev": round(stdev(lens), 2),
            "median": round(median(lens), 2),
            "p10": round(percentile(lens, 0.10), 1),
            "p90": round(percentile(lens, 0.90), 1),
            "max": max(lens) if lens else 0,
            "short_frac": round(sum(1 for x in lens if x <= 12) / float(len(lens) or 1), 4),
            "long_frac": round(sum(1 for x in lens if x >= 30) / float(len(lens) or 1), 4),
        },
        "para_len": {
            "mean": round(mean(para_lens), 2),
            "stdev": round(stdev(para_lens), 2),
            "max": max(para_lens) if para_lens else 0,
        },
        "punct": _punct_rates(text),
        "person": _person_stats(text),
        "lex": _lex_rates(text),
        "questions": round(len(re.findall(r"[？?]", text)) * 100.0 / n, 3),
        "exclaims": round(len(re.findall(r"[！!]", text)) * 100.0 / n, 3),
        "opening": open_sent or (sents[0] if sents else ""),
        "opening_type": classify_opening(open_para),
        "ending": sents[-1] if sents else "",
        "ending_type": classify_ending(sents[-1]) if sents else "",
        "ordinal_para_frac": round(
            sum(1 for p in paras if ORDINAL_HEAD_RE.match(p)) / float(len(paras) or 1), 4),
    }


def build_profile(sample_texts, names=None):
    """从样本集抽风格档案。

    档案里每一项都是**数字或可枚举的类别**，没有一项是模型的形容词。
    这样 verify 才能在新稿上把每一项重新数一遍并比对——"可测量"的判据就在这里。
    """
    names = names or ["样本{}".format(i + 1) for i in range(len(sample_texts))]
    per = [analyze_text(t) for t in sample_texts]
    n = len(per)
    sent_means = [p["sent_len"]["mean"] for p in per]
    sent_medians = [p["sent_len"]["median"] for p in per]
    sent_stdevs = [p["sent_len"]["stdev"] for p in per]
    para_means = [p["para_len"]["mean"] for p in per]

    # 句长带宽：IQR 主导（抗极值），并**不比样本自身的标准差更大**——
    # 带宽比稿子里的自然波动还宽，就等于没有判别力。这是第一版踩出来的。
    all_lens = []
    for t in sample_texts:
        all_lens.extend(_sent_lens(split_sentences(t)))
    iqr = percentile(all_lens, 0.75) - percentile(all_lens, 0.25)
    inside = mean(sent_stdevs)
    outside = stdev(sent_medians)
    sent_band = min(SENT_BAND_CAP,
                    max(SENT_BAND_FLOOR,
                        min(SENT_BAND_IQR_K * iqr, inside + outside)))
    sent_center = median(sent_medians)
    sent_lo = max(SENT_LO_FLOOR, sent_center - sent_band)
    para_band = max(PARA_BAND_FLOOR, PARA_BAND_REL * mean(para_means))

    punct_keys = sorted(PUNCT_KINDS.keys()) + ["total"]
    punct_mean = {k: round(mean([p["punct"][k] for p in per]), 3) for k in punct_keys}
    # 标点带宽：取「相对容差」与「逐篇离散度」里更宽的那个。
    #
    # 【为什么必须看逐篇离散】第一版只用 `max(0.6, 0.5×均值)`。破折号均值 1.03，
    # 带宽 0.6，允许区间 0.43~1.63 —— 一篇**一个破折号都不用**的同风格稿子
    # 直接被判偏离（实测：自写对照稿就栽在这一项）。
    # 但样本里破折号本来就是"有的篇很多、有的篇一个没有"，这种波动是**调性的一部分**，
    # 不该判违规。所以带宽改为 max(相对容差, 逐篇标准差)，把样本自己的波动吃进去。
    punct_band = {}
    for k in punct_keys:
        vals = [p["punct"][k] for p in per]
        sd_k = stdev(vals)
        punct_band[k] = round(max(PUNCT_BAND_ABS, PUNCT_BAND_REL * punct_mean[k], sd_k), 3)

    fracs = {k: [p["person"]["frac"][k] for p in per] for k in PERSON_WORDS}
    person_mean = {k: round(mean(v), 4) for k, v in fracs.items()}
    dom_counts = {}
    for p in per:
        dom_counts[p["person"]["dominant"]] = dom_counts.get(p["person"]["dominant"], 0) + 1

    lex_keys = sorted(LEX_GROUPS.keys())
    lex_mean = {k: round(mean([p["lex"][k] for p in per]), 3) for k in lex_keys}
    lex_band = {k: round(max(LEX_BAND_ABS, LEX_BAND_REL * lex_mean[k]), 3) for k in lex_keys}

    opening_types = [p["opening_type"] for p in per]
    ending_types = [p["ending_type"] for p in per]
    open_votes = {}
    for t in opening_types:
        open_votes[t] = open_votes.get(t, 0) + 1
    end_votes = {}
    for t in ending_types:
        end_votes[t] = end_votes.get(t, 0) + 1

    cnt = _ngram_df(sample_texts)
    catch = pick_catchphrases(cnt, n, top=5)

    sd = style_distance(sample_texts)

    banned = {}
    for p in per:
        for k, v in p["lex"].items():
            banned.setdefault(k, [])

    profile = {
        "profile_version": "1.0",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "samples": {
            "count": n,
            "names": list(names),
            "han": [p["han"] for p in per],
            "han_total": sum(p["han"] for p in per),
            "han_mean": round(mean([p["han"] for p in per]), 1),
        },
        "sent_len": {
            "mean": round(sent_center, 2),
            "mean_of_means": round(mean(sent_means), 2),
            "stdev_mean": round(inside, 2),
            "between_stdev": round(outside, 2),
            "iqr": round(iqr, 2),
            "band": round(sent_band, 2),
            "lo": round(sent_lo, 2),
            "hi": round(sent_center + sent_band, 2),
            "median": round(sent_center, 2),
            "p10": round(percentile(all_lens, 0.10), 1),
            "p90": round(percentile(all_lens, 0.90), 1),
            "short_frac": round(mean([p["sent_len"]["short_frac"] for p in per]), 4),
            "long_frac": round(mean([p["sent_len"]["long_frac"] for p in per]), 4),
            "per_sample_mean": sent_means,
            "per_sample_median": sent_medians,
        },
        "para_len": {
            "mean": round(mean(para_means), 2),
            "band": round(para_band, 2),
            "lo": round(max(1.0, mean(para_means) - para_band), 2),
            "hi": round(mean(para_means) + para_band, 2),
            "max": max(p["para_len"]["max"] for p in per),
            "per_sample_mean": para_means,
            "ordinal_para_frac": round(mean([p["ordinal_para_frac"] for p in per]), 4),
        },
        "punct": {"mean": punct_mean, "band": punct_band},
        "person": {"mean_frac": person_mean, "band": PERSON_BAND_ABS,
                   "dominant": max(dom_counts, key=lambda k: dom_counts[k]) if dom_counts else "none",
                   "dominant_votes": dom_counts,
                   "total_per_sample": [p["person"]["total"] for p in per]},
        "lex": {"mean": lex_mean, "band": lex_band},
        "catchphrases": catch,
        "openings": {"types": opening_types, "votes": open_votes,
                     "sentences": [p["opening"] for p in per]},
        "endings": {"types": ending_types, "votes": end_votes,
                    "sentences": [p["ending"] for p in per]},
        "self_similarity": sd,
        "per_sample": per,
    }
    # 容差自标定：拿样本自己跑一遍对照表，得到每个指标的容许偏差倍数。
    # **必须在 profile 主体建好之后**（calibrate 要读 punct.mean / catchphrases 等）。
    profile["tolerance"] = calibrate(profile, sample_texts)
    profile["self_check"] = verify_self(profile, sample_texts)
    return profile


# ---------------------------------------------------------------------------
# 指标比对：新稿 vs 档案（**这一节是本包的核心**）
#
# 每个指标给出：档案值、带宽、新稿值、带符号偏差、相对偏差、是否在带内。
# 不允许只给"很像"这种结论——**每一项都要有一个能反驳的数**。
# ---------------------------------------------------------------------------

def _cmp(name, label, prof, band, got, unit="", kind="range", note=""):
    """比一项。kind=range 用带宽；kind=class 判类别是否一致。"""
    dev = abs(float(got) - float(prof))
    rel = dev / band if band else (0.0 if dev == 0 else 1.0)
    ok = dev <= band + 1e-9
    return {
        "metric": name, "label": label, "profile": prof, "band": band,
        "got": got, "dev": round(dev, 4), "rel": round(rel, 4),
        "ok": bool(ok), "unit": unit, "kind": kind, "note": note,
        "lo": round(float(prof) - band, 4), "hi": round(float(prof) + band, 4),
    }


def compare(profile, text):
    """把一篇新稿逐指标与档案比对，返回对照表 + 汇总。

    `ok` 的判据是 `dev <= band × dev_limit`，`dev_limit` **来自样本自身**
    （见 calibrate()）—— 同账号的样本必须先过得去，闸门才有资格拦别人。
    """
    rows = build_rows(profile, text)
    limits = profile.get("tolerance") or {}
    for r in rows:
        dl = limits.get(r["metric"], {}).get("dev_limit", DEFAULT_DEV_LIMIT)
        r["dev_limit"] = round(dl, 3)
        r["limit_kind"] = "class" if r["kind"] == "class" else (
            "band" if r["kind"] == "range" else "count")
        if r["band"] is not None:
            r["limit_abs"] = round(r["band"] * dl, 4)
        if r["kind"] == "class" and limits.get(r["metric"], {}).get("open"):
            r["profile"] = "（任意类别）"
    for r in rows:
        apply_tolerance(r)
    fails = [r for r in rows if not r["ok"]]
    devs = [r["rel"] for r in rows]
    score = max(0.0, 100.0 * (1.0 - (mean(devs) if devs else 0.0)))
    return {
        "current": analyze_text(text),
        "rows": rows,
        "fails": fails,
        "fail_count": len(fails),
        "metric_count": len(rows),
        "mean_dev": round(mean(devs) if devs else 0.0, 4),
        "max_dev": round(max(devs) if devs else 0.0, 4),
        "style_score": round(score, 1),
        "ok": not fails,
    }


def apply_tolerance(r):
    """按自标定容差（dev_limit）判定通过与否。就地改 `r["ok"]`。"""
    if r["kind"] == "class":
        if r["profile"] == "（任意类别）":
            r["ok"] = True
            r["note"] = (r["note"] or "") + "；样本里开场类别不统一 → 这一项放开"
        return
    dl = r.get("dev_limit", DEFAULT_DEV_LIMIT)
    if r["hi"] is not None and r["band"] is not None:
        lo_eff = float(r["profile"]) - float(r["band"]) * dl
        hi_eff = float(r["profile"]) + float(r["band"]) * dl
        # 区间下限不小于 0（句长/密度不可能为负）
        r["lo_eff"] = round(max(0.0, lo_eff), 4)
        r["hi_eff"] = round(hi_eff, 4)
        r["ok"] = r["lo_eff"] - 1e-9 <= float(r["got"]) <= r["hi_eff"] + 1e-9
    elif r["band"] is not None:
        r["dev_eff"] = round(float(r["band"]) * dl, 4)
        r["ok"] = r["got"] >= r["dev_eff"] - 1e-9
    else:
        r["ok"] = True


def build_rows(profile, text):
    """把档案与新稿的指标一一配对，产出对照行（**不做通过判定**）。"""
    cur = analyze_text(text)
    rows = []
    sl = profile["sent_len"]
    pl = profile["para_len"]

    rows.append(_cmp("sent_len_mean", "平均句长", sl["mean"], sl["band"],
                     cur["sent_len"]["mean"], "汉字"))
    rows.append(_cmp("para_len_mean", "平均段长", pl["mean"], pl["band"],
                     cur["para_len"]["mean"], "汉字"))
    rows.append(_cmp("sent_short_frac", "短句占比(≤12字)", sl["short_frac"], SHORT_SENT_BAND,
                     cur["sent_len"]["short_frac"], ""))
    rows.append(_cmp("sent_long_frac", "长句占比(≥30字)", sl["long_frac"], LONG_SENT_BAND,
                     cur["sent_len"]["long_frac"], ""))
    for k in sorted(profile["punct"]["mean"].keys()):
        rows.append(_cmp("punct_" + k, "标点密度·" + _punct_label(k),
                         profile["punct"]["mean"][k], profile["punct"]["band"][k],
                         cur["punct"][k], "/百字"))
    for k in ("first", "second", "third"):
        rows.append(_cmp("person_" + k, "人称占比·" + _person_label(k),
                         profile["person"]["mean_frac"][k], profile["person"]["band"],
                         cur["person"]["frac"][k], ""))
    for k in sorted(profile["lex"]["mean"].keys()):
        rows.append(_cmp("lex_" + k, "词组密度·" + _lex_label(k),
                         profile["lex"]["mean"][k], profile["lex"]["band"][k],
                         cur["lex"][k], "/百字"))
    rows.append(_cmp("ordinal_para_frac", "序数开头段占比",
                     pl["ordinal_para_frac"], 0.30, cur["ordinal_para_frac"], ""))

    # 口头禅：命中几个档案里的 top-N（类别型：只数命中数）
    hit, missed = [], []
    for it in profile["catchphrases"]:
        g = it["ng"]
        c = len(re.findall(re.escape(g), _norm_for_echo(text)))
        if c > 0:
            hit.append({"ng": g, "count_in_draft": c,
                        "count_in_samples": it["count"], "df": it["df"]})
        else:
            missed.append({"ng": g, "count_in_samples": it["count"], "df": it["df"]})
    need = min(CATCHPHRASE_MIN_HIT, len(profile["catchphrases"]))
    rows.append({
        "metric": "catchphrase_hit", "label": "口头禅命中", "profile": len(profile["catchphrases"]),
        "band": need, "got": len(hit),
        "dev": max(0, need - len(hit)), "rel": 0.0 if len(hit) >= need else 1.0,
        "ok": len(hit) >= need, "unit": "个", "kind": "count",
        "note": "命中：" + ("、".join(h["ng"] for h in hit) or "无") +
                ("；未命中：" + "、".join(m["ng"] for m in missed) if missed else ""),
        "lo": need, "hi": None,
    })

    # 开场 / 结尾类别。**样本里类别不统一时，这一项放开**——
    # 样本自己都用好几种开场，却要求新稿必须用其中一种，是双重标准。
    otypes = set(profile["openings"]["types"])
    etypes = set(profile["endings"]["types"])
    o_all_open = len(otypes) > max(1, profile["samples"]["count"] // 3)
    e_all_open = len(etypes) > max(1, profile["samples"]["count"] // 3)
    rows.append({
        "metric": "opening_type", "label": "开场句式",
        "profile": "（任意类别）" if o_all_open else "/".join(sorted(otypes)),
        "band": None, "got": cur["opening_type"],
        "dev": 0 if (o_all_open or cur["opening_type"] in otypes) else 1,
        "rel": 0.0 if (o_all_open or cur["opening_type"] in otypes) else 1.0,
        "ok": bool(o_all_open or cur["opening_type"] in otypes), "unit": "", "kind": "class",
        "note": "样本用过的类别：" + "、".join(sorted(otypes)), "lo": None, "hi": None,
    })
    rows.append({
        "metric": "ending_type", "label": "结尾句式",
        "profile": "（任意类别）" if e_all_open else "/".join(sorted(etypes)),
        "band": None, "got": cur["ending_type"],
        "dev": 0 if (e_all_open or cur["ending_type"] in etypes) else 1,
        "rel": 0.0 if (e_all_open or cur["ending_type"] in etypes) else 1.0,
        "ok": bool(e_all_open or cur["ending_type"] in etypes), "unit": "", "kind": "class",
        "note": "样本用过的类别：" + "、".join(sorted(etypes)), "lo": None, "hi": None,
    })

    # 人称主导是否变了
    pdom = profile["person"]["dominant"]
    cdom = cur["person"]["dominant"]
    rows.append({
        "metric": "person_dominant", "label": "主导人称", "profile": _person_label(pdom),
        "band": None, "got": _person_label(cdom), "dev": 0 if pdom == cdom else 1,
        "rel": 0.0 if pdom == cdom else 1.0, "ok": pdom == cdom, "unit": "", "kind": "class",
        "note": "主导人称变了就等于换了叙述视角", "lo": None, "hi": None,
    })
    return rows


def calibrate(profile, sample_texts):
    """**自标定**：拿样本自己跑一遍对照表，得出每个指标的容差倍数。

    为什么必须这么做：容差写死就会出现两种坏结果之一 ——
    要么严到"同账号的样本自己都过不去"（闸门在正常使用中一直响，最后没人看），
    要么松到"什么稿子都能过"（那就是假绿，比闸门失效更糟）。
    样本自己产出的偏差分布，是唯一能同时避开这两者的依据。

    每个指标取「样本观测到的最大相对偏差 × SAFETY」，落到 [1.0, MAX] 区间。
    再加一层**硬上限**：任何指标的容许绝对偏差不得超过 band × HARD_CAP，
    免得自标定把闸门放松到无边。class 类指标：样本里类别不统一 → 标 open。
    """
    raw = [build_rows(profile, t) for t in sample_texts]
    limits = {}
    for i, r in enumerate(raw[0]):
        key = r["metric"]
        if r["kind"] == "class":
            open_flag = any(rows[i]["ok"] is False for rows in raw)
            limits[key] = {"kind": "class", "dev_limit": 1.0,
                           "open": bool(open_flag),
                           "note": "样本内部类别不统一" if open_flag else "样本内部类别一致"}
            continue
        rels = [rows[i]["rel"] for rows in raw if rows[i].get("band")]
        mx = max(rels) if rels else 0.0
        dl = max(DEFAULT_DEV_LIMIT, min(MAX_DEV_LIMIT, mx * SAFETY))
        limits[key] = {"kind": "band", "dev_limit": round(dl, 3),
                       "sample_max_rel": round(mx, 3)}
    return limits


def verify_self(profile, sample_texts):
    """自证：把档案套回样本自身，统计通过率。

    这是"可测量还是读起来像"那一条的**内建证据**：
    profile / verify 都会打印它。如果同账号样本自己通过率不是 100%，
    说明这份档案的容差定错了，使用者应该先改口径而不是相信后面的结论。
    """
    rows = []
    for i, t in enumerate(sample_texts):
        c = compare(profile, t)
        rows.append({"sample": profile["samples"]["names"][i] if i < len(
            profile["samples"]["names"]) else "样本{}".format(i + 1),
            "style_score": c["style_score"], "fail_count": c["fail_count"],
            "fails": [r["label"] for r in c["fails"]]})
    passed = sum(1 for r in rows if r["fail_count"] == 0)
    return {"total": len(rows), "passed": passed,
            "pass_rate": round(passed / float(len(rows) or 1), 4), "per_sample": rows}


def _punct_label(k):
    return {"exclaim": "叹号", "question": "问号", "ellipsis": "省略号", "dash": "破折号",
            "colon": "冒号", "quote": "引号", "comma": "逗号", "enum_comma": "顿号",
            "total": "全部"}.get(k, k)


def _person_label(k):
    return {"first": "我/我们", "second": "你/你们", "third": "他/她/他们",
            "none": "（无）"}.get(k, k)


def _lex_label(k):
    return {"hedge": "缓和词(其实/大概)", "contrast": "转折词(但/不过)",
            "enumeration": "序数词(第一/首先)", "transition": "顺承词(于是/然后/所以)",
            "metaphor": "比喻词(像/似的/仿佛)"}.get(k, k)


# ---------------------------------------------------------------------------
# 成本模型
#
# 现实情况（实测，别猜）：
#   · `POST /api/v1/chat/completions` 的成功响应**不带 `code` 字段**；
#     usage 里只有 prompt_tokens / completion_tokens / total_tokens。
#   · `GET /api/v1/models` 的记录里**没有价格字段**；
#     `GET /api/v1/pricing` 实测只有生成应用的规则，**不含文本大模型**。
# 结论：**拿不到可信的文本模型单价，本包拒绝凭空编一个。**
#   token 数我们估（实测标定），金额必须由你给单价。
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN_IN = 1.61    # 实测标定：1 token ≈ 1.61 原始字符（含换行）
TOKENS_PER_CHAR_OUT = 1.11   # 实测标定：1 原始字符 ≈ 1.11 token
POINTS_PER_YUAN = 100.0      # 平台口径：1 元 = 100 点


def estimate_tokens_in(text):
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_tokens_out(chars):
    return max(1, int(round((chars or 0) * TOKENS_PER_CHAR_OUT)))


def compute_cost(tokens_in, tokens_out, price_in=None, price_out=None):
    rec = {"tokens_in": int(tokens_in or 0), "tokens_out": int(tokens_out or 0),
           "price_in": price_in, "price_out": price_out, "unit": "点/百万 token",
           "points": None, "yuan": None, "notes": []}
    if price_in is None or price_out is None:
        rec["notes"].append(
            "没给单价，无法给出金额：接口的 pricing 表实测不含文本大模型，"
            "models 列表实测也没有价格字段。用 --price-in / --price-out 指定你账号的"
            "单价（点/百万 token）即可算出点数与金额。")
        return rec
    pts = (rec["tokens_in"] / 1e6) * float(price_in) + \
          (rec["tokens_out"] / 1e6) * float(price_out)
    rec["points"] = round(pts, 4)
    rec["yuan"] = round(pts / POINTS_PER_YUAN, 4)
    rec["notes"].append("按你给的单价线性折算；真实扣费以账户流水为准。")
    return rec


def fmt_cost(rec):
    if rec.get("points") is None:
        return "token {} in + {} out（金额无法估算：{}）".format(
            rec["tokens_in"], rec["tokens_out"], "；".join(rec.get("notes") or []))
    return "%d in + %d out tokens = %g 点 = ¥%g" % (
        rec["tokens_in"], rec["tokens_out"], rec["points"], rec["yuan"])


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class StyleError(a7w.A7wError):
    """调用失败（网络、鉴权、点数、模型名）。→ 退出码 4"""


class UsageError(StyleError):
    """参数/配置用错了（样本不足、文件不存在、outdir 指到包内）。→ 退出码 2

    为什么要跟 StyleError 分开：这两类错误的处理方式完全不同。
    参数错了要改命令重跑，不花一分钱；调用失败要查 Key / 点数 / 模型名。
    混成一个退出码，CI 里就没法区分「我命令写错了」和「网关挂了」。
    """


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
         max_tokens=4096, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    **为什么必须带退避重试**：网关的 upstream timeout / HTTP 502 实测很常见。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。

    成功响应**不带 `code` 字段**（实测），所以这里不判 code；只判 choices 在不在。
    `code==1` 那套信封是生成应用的，不适用于本端点。
    """
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
               "Content-Type": "application/json",
               "Accept": "application/json"}

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
            msg = None
            if isinstance(err.get("error"), dict):
                msg = err["error"].get("message")
            msg = msg or err.get("msg") or text[:200]
            if exc.code == 401:
                raise StyleError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise StyleError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise StyleError(
                    "模型不存在（404）：{}  用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 429，{}s 后重试…\n".format(3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise StyleError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise StyleError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    if payload is None:
        raise StyleError("网络错误：{}".format(last_exc))

    # 兜底：万一网关换了形态包了一层 {"code":1,"data":{...}}，两种都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise StyleError("模型没返回 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    finish_reason = (choices[0] or {}).get("finish_reason")
    _LAST_FINISH["reason"] = finish_reason
    _LAST_FINISH["chars"] = len(content)
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    return content, usage


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    模型经常在合法 JSON 后面多吐几个字符（```、解释、第二个对象、重复的 }），
    直接 json.loads 会炸。这里用 json.JSONDecoder().raw_decode()，
    从一个 { 或 [ 开始试解码，成功就返回，失败就往后挪一个字符接着试。
    """
    if not text:
        raise StyleError("模型返回空内容")
    dec = json.JSONDecoder()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1).strip())
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
    raise StyleError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


# ---------------------------------------------------------------------------
# 样本读取与产出位置闸门
# ---------------------------------------------------------------------------

def _strip_bom(s):
    return s[1:] if s and s[0] == "\ufeff" else s


def _read_text(p):
    return _strip_bom(Path(p).read_text(encoding="utf-8", errors="replace"))


def read_samples(a):
    """读样本集：`--samples` 可以给目录、单个文件，或重复多次。"""
    paths = []
    for s in (a.samples or []):
        p = Path(s)
        if p.is_dir():
            found = sorted([f for f in p.rglob("*")
                            if f.is_file() and f.suffix.lower() in SAMPLE_SUFFIXES])
            if not found:
                raise UsageError("样本目录里没有 {} 结尾的文件：{}".format(
                    "/".join(SAMPLE_SUFFIXES), p))
            paths.extend(found)
        elif p.is_file():
            paths.append(p)
        else:
            raise UsageError("找不到样本：{}".format(s))
    for s in (a.sample_files or []):
        p = Path(s)
        if not p.is_file():
            raise UsageError("找不到样本文件：{}".format(s))
        paths.append(p)
    if not paths:
        raise UsageError("没给样本。用 --samples <目录或文件>，可重复多次")
    # 去重保序
    seen, uniq = set(), []
    for p in paths:
        rp = str(p.resolve())
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    texts, names = [], []
    for p in uniq:
        t = _read_text(p)
        if han_len(t) < 80:
            sys.stderr.write("跳过过短的样本（汉字 < 80）：{}\n".format(p))
            continue
        texts.append(t)
        names.append(p.name)
    if len(texts) < MIN_SAMPLES:
        raise UsageError(
            "样本不足 {} 篇（有效样本 {} 篇）：样本太少，句长分布、人称占比、"
            "口头禅频次这些指标会被单篇的偶然写法支配，抽出来的不是调性。\n"
            "  请再补样本，或用 --samples 多指一个目录。\n"
            "  （这是硬闸门，不是警告：宁可拒绝抽档，也不给一份不可信的档案。）".format(
                MIN_SAMPLES, len(texts)))
    if len(texts) > MAX_SAMPLES:
        sys.stderr.write(
            "提示：样本 {} 篇超过上限 {}，只取前 {} 篇。\n"
            "  理由：样本越多，档案越像'平均值'——跨作者的平均值没有调性。\n".format(
                len(texts), MAX_SAMPLES, MAX_SAMPLES))
        texts, names = texts[:MAX_SAMPLES], names[:MAX_SAMPLES]
    return texts, names


def _is_inside_package(path):
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    try:
        p.relative_to(PACKAGE_DIR)
        return True
    except ValueError:
        return False


def guard_outdir(path, what="--outdir"):
    """产出位置闸门：`--outdir`/`--out` 指到包内 → exit=2。

    为什么是硬闸门而不是提示：SkillHub 的扩展名白名单只放
    `.md .py .txt .json .sh .js .yaml .yml .csv`，包内不许出现图片或其他二进制。
    产出写进包里，一旦格式越界就是整包被拒。
    """
    if not path:
        return
    if _is_inside_package(path):
        sys.stderr.write(
            "配置错误：{} 指到了技能包内部（{}）。\n"
            "  产出必须落在包外：包内只放文档与脚本，扩展名白名单只允许 "
            ".md .py .txt .json .sh .js .yaml .yml .csv，图片一律不许进包。\n"
            "  换一个包外目录（例如 D:/styleclone/out）再跑。\n".format(what, PACKAGE_DIR))
        raise UsageError("{} 指到了技能包内部，产出必须落在包外".format(what))


# ---------------------------------------------------------------------------
# 提示词
#
# 【本包最重要的一条纪律】提示词里**不放样本正文**，只放：
#   · 量化指标（数字，抄不走）
#   · 每个样本的开场句与结尾句（最多 2N 句，短句）
# 这两类会被登记为 PROMPT_SAMPLES，产出里抄到就触发 prompt_echo 闸门。
#
# 为什么不放全文：放了全文，最优策略就是"把样本改几个词"，闸门会一直响，
# 而模型也确实没有任何别的办法可用。放指标 + 首尾句，模型必须自己造正文，
# 这才是"学调性"与"抄样本"的分界。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是「三剪客 · 风格克隆体」的写手。你的任务不是写得好，是**写得像**：\n"
    "给定一份量化的风格档案（平均句长、句长带宽、人称占比、标点密度、段长、"
    "口头禅、开场与结尾句式），你要写出一篇符合这些数字的新稿。\n"
    "硬性纪律：\n"
    "1. 只输出一个 JSON 对象，不要任何解释文字、不要 Markdown 代码围栏。\n"
    "2. **禁止照抄参考句**。参考句只用来让你看清句式类别，抄一句就作废。\n"
    "3. **禁止编造数据**。没有给 --evidence 就不许出现具体数字、金额、比例、实测结论。\n"
    "4. 平均句长是硬指标：写完请自己数一遍，别交一篇句长偏离档案 10 字以上的稿子。\n"
    "5. 输出必须是一个完整可发布的稿子，不是提纲、不是片段。"
)


def _fmt_num(x):
    if x is None:
        return "-"
    if isinstance(x, float):
        return ("%.2f" % x).rstrip("0").rstrip(".") if abs(x) < 1000 else "%.0f" % x
    return str(x)


def build_profile_block(profile):
    """把档案渲染成提示词里的"指标卡"。**只有数字与类别，没有样本正文。**"""
    sl, pl, pu = profile["sent_len"], profile["para_len"], profile["punct"]
    pe, lx = profile["person"], profile["lex"]
    out = []
    out.append("[指标卡 | 从 {} 篇样本抽出，合计 {} 汉字]".format(
        profile["samples"]["count"], profile["samples"]["han_total"]))
    out.append("· 平均句长 {:.1f} 汉字（允许 {:.1f}~{}，带宽 ±{:.1f}）".format(
        sl["mean"], sl["lo"], sl["hi"], sl["band"]))
    out.append("· 句长中位数 {:.1f}｜p10 {:.1f}｜p90 {:.1f}｜"
               "短句(≤12)占比 {:.0%}｜长句(≥30)占比 {:.0%}".format(
                   sl["median"], sl["p10"], sl["p90"], sl["short_frac"], sl["long_frac"]))
    out.append("· 平均段长 {:.1f} 汉字（允许 {:.1f}~{}）｜序数开头段占比 {:.0%}".format(
        pl["mean"], pl["lo"], pl["hi"], pl["ordinal_para_frac"]))
    out.append("· 人称占比：我/我们 {:.0%}｜你/你们 {:.0%}｜他/她 {:.0%}｜主导人称：{}".format(
        pe["mean_frac"]["first"], pe["mean_frac"]["second"], pe["mean_frac"]["third"],
        _person_label(pe["dominant"])))
    out.append("· 标点密度（每百字）：叹号 {:.2f}｜问号 {:.2f}｜省略号 {:.2f}｜破折号 {:.2f}"
               "｜逗号 {:.2f}｜顿号 {:.2f}｜引号 {:.2f}".format(
                   pu["mean"]["exclaim"], pu["mean"]["question"], pu["mean"]["ellipsis"],
                   pu["mean"]["dash"], pu["mean"]["comma"], pu["mean"]["enum_comma"],
                   pu["mean"]["quote"]))
    out.append("· 词组密度（每百字）：缓和词 {:.2f}｜转折词 {:.2f}｜序数词 {:.2f}｜"
               "顺承词 {:.2f}｜比喻词 {:.2f}".format(
                   lx["mean"]["hedge"], lx["mean"]["contrast"], lx["mean"]["enumeration"],
                   lx["mean"]["transition"], lx["mean"]["metaphor"]))
    if profile["catchphrases"]:
        out.append("· 口头禅（必须自然用上至少 {} 个，别硬塞）：{}".format(
            min(CATCHPHRASE_MIN_HIT, len(profile["catchphrases"])),
            "、".join("「{}」(样本里出现 {} 次/{} 篇)".format(
                c["ng"], c["count"], c["df"]) for c in profile["catchphrases"])))
    out.append("· 开场句式（样本用过的类别）：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in sorted(
            profile["openings"]["votes"].items(), key=lambda kv: -kv[1]))))
    out.append("· 结尾句式（样本用过的类别）：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in sorted(
            profile["endings"]["votes"].items(), key=lambda kv: -kv[1]))))
    return "\n".join(out)


def profile_samples_for_echo(profile):
    """登记进提示词的示例句 = 每个样本的开场句与结尾句。

    与 build_write_prompt 里真正写进提示词的句子**必须完全一致**，
    否则闸门守的不是提示词里实际放过的东西。
    """
    out = []
    for s in profile["openings"]["sentences"]:
        if s:
            out.append(s)
    for s in profile["endings"]["sentences"]:
        if s:
            out.append(s)
    return out


def build_write_prompt(profile, topic, evidence=None, brief=None, feedback=None):
    # 目标字数：样本汉字中位数（写一篇与样本同量级的稿子）。
    # 用中位数而不是均值：样本里偶尔有一篇特别长的，均值会把它拽偏。
    target = int(round(median([p["han"] for p in profile["per_sample"]]))) or \
        int(round(profile["samples"]["han_mean"]))
    ref_open = profile["openings"]["sentences"]
    ref_end = profile["endings"]["sentences"]
    out = []
    out.append(build_profile_block(profile))
    out.append("")
    out.append("[句式参考 | 只准看句式，**严禁照抄原句**]")
    for i, s in enumerate(ref_open, 1):
        out.append("· 样本{}开场（{}）：{}".format(i, profile["openings"]["types"][i - 1] if
                                                  i - 1 < len(profile["openings"]["types"]) else "-", s))
    for i, s in enumerate(ref_end, 1):
        out.append("· 样本{}结尾（{}）：{}".format(i, profile["endings"]["types"][i - 1] if
                                                  i - 1 < len(profile["endings"]["types"]) else "-", s))
    out.append("")
    out.append("[本次任务]")
    out.append("· 主题/选题：{}".format(topic))
    if brief:
        out.append("· 额外要求：{}".format(brief))
    if evidence:
        out.append("· 可以使用的真实素材（只有这些数字能用）：{}".format(evidence))
    else:
        out.append("· 没有提供任何真实素材，所以**全文不许出现具体数字、金额、比例、"
                   "排名、实测结论**——需要举例时用定性描述。")
    out.append("· 目标篇幅：约 {} 汉字（不低于 {} 汉字——素材不够宁可把论点写透，"
               "也别提前收尾；样本就是这个量级）".format(target, int(target * 0.85)))
    out.append("")
    if feedback:
        out.append("[上一轮的风格偏离反馈 | 逐条修掉]")
        for f in feedback:
            out.append("· {}".format(f))
        out.append("")
    out.append("[输出格式] 只输出这个 JSON：")
    out.append('{"title": "标题（一句话，与样本标题同一口气）",')
    out.append(' "body": "正文（用 \\n\\n 分段，段内不要换行）",')
    out.append(' "style_notes": "你为了贴合指标做的三个具体动作（各一句）"}')
    out.append("")
    out.append("自检清单（交稿前逐条过）：平均句长落在 {}~{}；段长落在 {}~{}；"
               "口头禅用上至少 {} 个；开场用「{}」类；结尾用「{}」类；"
               "没有照抄参考句；没有编造数字。".format(
                   _fmt_num(profile["sent_len"]["lo"]), _fmt_num(profile["sent_len"]["hi"]),
                   _fmt_num(profile["para_len"]["lo"]), _fmt_num(profile["para_len"]["hi"]),
                   min(CATCHPHRASE_MIN_HIT, len(profile["catchphrases"])),
                   "、".join(sorted(set(profile["openings"]["types"]))),
                   "、".join(sorted(set(profile["endings"]["types"])))))
    return "\n".join(out)


def build_repair_prompt(profile, topic, draft, cmp_result, evidence=None):
    """迭代轮：把**偏差项**给模型看，让它定点修，而不是重写。"""
    out = []
    out.append(build_profile_block(profile))
    out.append("")
    out.append("[上一版新稿]")
    out.append(draft)
    out.append("")
    out.append("[逐指标实测 vs 档案 | 只列偏离项]")
    for r in cmp_result["fails"]:
        if r["kind"] == "class":
            out.append("· {}：档案是「{}」，你这版是「{}」——换成档案里的类别".format(
                r["label"], r["profile"], r["got"]))
        else:
            direction = "偏长" if (r["hi"] is not None and isinstance(r["got"], (int, float))
                                 and r["got"] > r["hi"]) else "偏短"
            out.append("· {}：档案 {}（允许 {}~{}），你这版 {} —— {} {:.2f}{}".format(
                r["label"], _fmt_num(r["profile"]), _fmt_num(r["lo"]), _fmt_num(r["hi"]),
                _fmt_num(r["got"]), direction, r["dev"], r["unit"]))
    out.append("")
    out.append("[任务] 在**保持内容与主题不变**的前提下定点修掉上面每一项偏离。"
               "不要重写成另一篇；不要新增编造的数据。")
    if evidence:
        out.append("可用的真实素材：{}".format(evidence))
    out.append("主题：{}".format(topic))
    out.append("")
    out.append("[输出格式] 与上一版相同的 JSON（title / body / style_notes）。")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """偏离/命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "⚠️ " + s
    return "\x1b[31m{}\x1b[0m".format(s)


def render_profile_md(profile):
    sl, pl, pu = profile["sent_len"], profile["para_len"], profile["punct"]
    pe, lx = profile["person"], profile["lex"]
    out = []
    out.append("# 风格档案｜{} 篇样本".format(profile["samples"]["count"]))
    out.append("")
    out.append("- 样本：{}".format("、".join(profile["samples"]["names"])))
    out.append("- 样本量：{} 篇，合计 {} 汉字（均 {:.0f} 汉字/篇）".format(
        profile["samples"]["count"], profile["samples"]["han_total"], profile["samples"]["han_mean"]))
    out.append("- 生成时间：{}".format(profile["generated_at"]))
    sc = profile.get("self_check")
    if sc:
        out.append("- **自证**：{} 篇样本套这份档案，通过 **{}/{} = {:.0%}**"
                   "（容差就是按这个标定的）".format(
                       sc["total"], sc["passed"], sc["total"], sc["pass_rate"]))
    out.append("")
    out.append("## 一、句长分布")
    out.append("")
    out.append("| 指标 | 值 | 说明 |")
    out.append("|---|---|---|")
    out.append("| 平均句长 | **{:.1f}** 汉字 | 允许区间 {:.1f}~{:.1f}（带宽 ±{:.1f}，"
               "由样本内标准差与篇间离散合成） |".format(sl["mean"], sl["lo"], sl["hi"], sl["band"]))
    out.append("| 句长标准差（样本内均值） | {:.1f} | 越大越忽长忽短 |".format(sl["stdev_mean"]))
    out.append("| 篇间句长离散 | {:.1f} | 说明这个账号每篇之间本来就有波动 |".format(sl["between_stdev"]))
    out.append("| 句长中位数 | {:.1f} | 比均值抗极值 |".format(sl["median"]))
    out.append("| p10 / p90 | {:.1f} / {:.1f} | 句长的两端 |".format(sl["p10"], sl["p90"]))
    out.append("| 短句占比（≤12 汉字） | {:.0%} | 调性的一半在这里 |".format(sl["short_frac"]))
    out.append("| 长句占比（≥30 汉字） | {:.0%} | 另一半 |".format(sl["long_frac"]))
    out.append("")
    out.append("按样本逐篇：{}".format(
        "、".join("{:.1f}".format(x) for x in sl["per_sample_mean"])))
    out.append("")
    out.append("## 二、段落节奏")
    out.append("")
    out.append("| 指标 | 值 |")
    out.append("|---|---|")
    out.append("| 平均段长 | **{:.1f}** 汉字（允许 {:.1f}~{}） |".format(
        pl["mean"], pl["lo"], pl["hi"]))
    out.append("| 最长段（样本里出现过） | {} 汉字 |".format(pl["max"]))
    out.append("| 序数开头段占比（一、/ 1. / 第一，） | {:.0%} |".format(pl["ordinal_para_frac"]))
    out.append("")
    out.append("## 三、人称分布")
    out.append("")
    out.append("| 人称 | 平均占比 | 逐篇占比 |")
    out.append("|---|---|---|")
    for k in ("first", "second", "third"):
        out.append("| {} | **{:.1%}** | {} |".format(
            _person_label(k), pe["mean_frac"][k],
            "、".join("{:.0%}".format(p["person"]["frac"][k]) for p in profile["per_sample"])))
    out.append("")
    out.append("- 主导人称：**{}**（各篇投票：{}）".format(
        _person_label(pe["dominant"]),
        "、".join("{}×{}".format(_person_label(k), v) for k, v in pe["dominant_votes"].items())))
    out.append("")
    out.append("## 四、标点密度（每百字）")
    out.append("")
    out.append("| 标点 | 密度 | 允许区间 |")
    out.append("|---|---|---|")
    for k in ["exclaim", "question", "ellipsis", "dash", "colon", "quote", "comma",
              "enum_comma", "total"]:
        out.append("| {} | {:.2f} | {:.2f}~{:.2f} |".format(
            _punct_label(k), pu["mean"][k], pu["mean"][k] - pu["band"][k],
            pu["mean"][k] + pu["band"][k]))
    out.append("")
    out.append("## 五、词组密度（每百字）")
    out.append("")
    out.append("| 词组 | 密度 | 允许区间 |")
    out.append("|---|---|---|")
    for k in sorted(lx["mean"].keys()):
        out.append("| {} | {:.2f} | {:.2f}~{:.2f} |".format(
            _lex_label(k), lx["mean"][k], lx["mean"][k] - lx["band"][k],
            lx["mean"][k] + lx["band"][k]))
    out.append("")
    out.append("## 六、口头禅 top-{}".format(len(profile["catchphrases"])))
    out.append("")
    if profile["catchphrases"]:
        out.append("| 口头禅 | 样本内次数 | 出现在几篇 |")
        out.append("|---|---|---|")
        for c in profile["catchphrases"]:
            out.append("| {} | {} | {}/{} |".format(
                c["ng"], c["count"], c["df"], profile["samples"]["count"]))
        out.append("")
        out.append("选取口径：**先看跨篇复现（出现在几篇），再看总频次**。"
                   "只在某一篇里反复出现的词组是那篇的内容词，不是这个作者的调性。")
    else:
        out.append("样本里没有达到复现门槛（≥2 篇）的词组——这本身也是一条信息："
                   "这个作者的调性不靠固定口头禅，靠句式和节奏。")
    out.append("")
    out.append("## 七、开场与结尾套路")
    out.append("")
    out.append("| 位置 | 逐篇类别 |")
    out.append("|---|---|")
    out.append("| 开场 | {} |".format("、".join(profile["openings"]["types"])))
    out.append("| 结尾 | {} |".format("、".join(profile["endings"]["types"])))
    out.append("")
    out.append("类别票数——开场：{}｜结尾：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in sorted(
            profile["openings"]["votes"].items(), key=lambda kv: -kv[1])),
        "、".join("{}×{}".format(k, v) for k, v in sorted(
            profile["endings"]["votes"].items(), key=lambda kv: -kv[1]))))
    out.append("")
    out.append("## 八、样本自相似基线（**反例判据**）")
    out.append("")
    sd = profile["self_similarity"]
    out.append("把每篇样本的风格指纹（只留风格性二字组，丢掉跨句重复的内容词）"
               "两两比一遍：")
    out.append("")
    out.append("| 组合 | 相似度 |")
    out.append("|---|---|")
    for p in sd["pairwise"][:15]:
        out.append("| 样本{} ↔ 样本{} | {:.3f} |".format(p["a"], p["b"], p["sim"]))
    if len(sd["pairwise"]) > 15:
        out.append("| …（共 {} 对） | |".format(sd["pairs"]))
    out.append("")
    out.append("- 均值 **{:.3f}**｜最低 **{:.3f}**｜最高 **{:.3f}**".format(
        sd["mean"], sd["min"], sd["max"]))
    out.append("- **自相似阈值 = {:.3f}**（两两相似度的最低值）。"
               "这个阈值不是拍脑袋定的：它是**同一个人写的稿子之间最低的相似度**。"
               "任何稿子与样本集的风格相似度低于它，就不比样本之间更像，"
               "也就不该判为'同一个账号'。".format(sd["threshold"]))
    out.append("")
    out.append("下一步：`python3 run.py write --profile <本档案.json> --topic \"选题\"`")
    return "\n".join(out)


def render_verify_md(cmp_result, profile, draft_meta=None, title=""):
    """逐指标对照表。**不许只给一个"很像"的结论。**"""
    out = []
    out.append("# 风格一致性自检")
    out.append("")
    if title:
        out.append("- 新稿：{}".format(title))
    if draft_meta:
        out.append("- 稿子 {} 汉字 / {} 句 / {} 段".format(
            draft_meta["han"], draft_meta["sentences"], draft_meta["paragraphs"]))
    out.append("- 档案：{} 篇样本，平均句长 {:.1f}、平均段长 {:.1f}".format(
        profile["samples"]["count"], profile["sent_len"]["mean"], profile["para_len"]["mean"]))
    out.append("- 风格一致度：**{}/100**（= 100×(1−平均相对偏差)；只用来横向比较，"
               "不是概率）".format(cmp_result["style_score"]))
    out.append("")
    verdict = "✅ 全部 {} 项指标落在容差内".format(cmp_result["metric_count"]) if cmp_result["ok"] \
        else "❌ {} / {} 项指标超出容差".format(cmp_result["fail_count"], cmp_result["metric_count"])
    if cmp_result["ok"]:
        out.append("> {}".format(verdict))
    else:
        out.append("> {}".format(_red(verdict)))
    out.append("")
    out.append("## 逐指标对照表")
    out.append("")
    out.append("| 指标 | 档案值 | 允许区间 | 新稿 | 偏差 | 相对偏差 | 结论 |")
    out.append("|---|---|---|---|---|---|---|")
    for r in cmp_result["rows"]:
        if r["kind"] == "class":
            band = "—"
            prof = r["profile"]
            got = r["got"]
            dev = "类别不同" if not r["ok"] else "同类"
            rel = "—"
        elif r["kind"] == "count":
            band = "≥{}".format(r["band"])
            prof = r["profile"]
            got = r["got"]
            dev = "{:+}".format(r["got"] - r["band"]) if r["got"] < r["band"] else "达标"
            rel = "{:.2f}".format(r["rel"])
        else:
            band = "{}~{}".format(_fmt_num(r["lo"]), _fmt_num(r["hi"]))
            prof = _fmt_num(r["profile"]) + (" " + r["unit"] if r["unit"] else "")
            got = _fmt_num(r["got"]) + (" " + r["unit"] if r["unit"] else "")
            dev = "{:+.2f}".format(r["got"] - r["profile"])
            rel = "{:.2f}".format(r["rel"])
        mark = "✅" if r["ok"] else "❌ **偏离**"
        line = "| {} | {} | {} | {} | {} | {} | {} |".format(
            r["label"], prof, band, got, dev, rel, mark)
        if not r["ok"]:
            line = _red(line)
        out.append(line)
    out.append("")
    if not cmp_result["ok"]:
        out.append("## 偏离明细（**这些就是要改的地方**）")
        out.append("")
        for r in cmp_result["fails"]:
            if r["kind"] == "class":
                out.append("- **{}**：档案是「{}」，新稿是「{}」。{}".format(
                    r["label"], r["profile"], r["got"], r["note"]))
            elif r["kind"] == "count":
                out.append("- **{}**：档案要求命中 ≥{} 个，新稿只命中 {} 个。{}".format(
                    r["label"], r["band"], r["got"], r["note"]))
            else:
                d = r["got"] - r["profile"]
                out.append("- **{}**：档案 {} {}，新稿 {} {}，偏差 {:+.2f}（超出带宽 {} 的 {:.2f} 倍）。".format(
                    r["label"], _fmt_num(r["profile"]), r["unit"], _fmt_num(r["got"]), r["unit"],
                    d, _fmt_num(r["band"]), r["rel"]))
        out.append("")
        out.append("> 想让它自己修：`python3 run.py all --samples <样本目录> "
                   "--topic \"...\" --iterations 2`，脚本会把上面这些偏离项喂回模型。")
    out.append("")
    out.append("## 口头禅核验")
    out.append("")
    cp = [r for r in cmp_result["rows"] if r["metric"] == "catchphrase_hit"][0]
    out.append("- {}".format(cp["note"]))
    return "\n".join(out)


def render_diff_md(cmp_result, profile, source_label="新稿"):
    """档案 vs 新稿的并排指标对照（比 verify 更简短，只列关键项）。"""
    out = []
    out.append("# 指标对照｜档案 vs {}".format(source_label))
    out.append("")
    out.append("| 指标 | 档案 | {}".format(source_label))
    out.append("|---|---|---|")
    for r in cmp_result["rows"]:
        if r["kind"] == "class":
            out.append("| {} | {} | {} {} |".format(
                r["label"], r["profile"], r["got"], "" if r["ok"] else "❌"))
        else:
            out.append("| {} | {} {} | {} {} {} |".format(
                r["label"], _fmt_num(r["profile"]), r["unit"], _fmt_num(r["got"]), r["unit"],
                "" if r["ok"] else "❌"))
    out.append("")
    out.append("风格一致度 **{}/100**；偏离 {}/{} 项。".format(
        cmp_result["style_score"], cmp_result["fail_count"], cmp_result["metric_count"]))
    return "\n".join(out)


def render_baseline_md(profile):
    """baseline：把样本自身逐篇跑一遍比对，给出"同风格"的经验分布。

    这是本包"可测量还是读起来像"那一条的**自证材料**：
    如果同账号的样本自己对不上档案，那这个档案就是假的。
    """
    out = []
    out.append("# 样本自身一致性（自证：档案是否真的描述了这个账号）")
    out.append("")
    out.append("把 {} 篇样本**逐篇**与（含它自己在内的）档案比对。"
               "同一作者的稿子不应该大幅偏离自己的档案。".format(
                   profile["samples"]["count"]))
    out.append("")
    out.append("| 样本 | 汉字 | 平均句长 | 一致度 | 偏离项 |")
    out.append("|---|---|---|---|---|")
    for i, p in enumerate(profile["per_sample"], 1):
        out.append("| {} | {} | {:.1f} | — | — |".format(
            profile["samples"]["names"][i - 1], p["han"], p["sent_len"]["mean"]))
    out.append("")
    sd = profile["self_similarity"]
    out.append("- 样本两两风格指纹相似度：均值 {:.3f}、最低 {:.3f}、最高 {:.3f}".format(
        sd["mean"], sd["min"], sd["max"]))
    out.append("- **自相似阈值 {:.3f}**：低于它的稿子不算这个账号的风格".format(sd["threshold"]))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def _load_profile(p):
    path = Path(p)
    if not path.is_file():
        raise UsageError("找不到风格档案文件：{}（先用 `run.py profile --out` 生成）".format(p))
    try:
        obj = json.loads(_strip_bom(path.read_text(encoding="utf-8", errors="replace")))
    except ValueError as exc:
        raise UsageError("风格档案不是合法 JSON：{}（{}）".format(p, exc))
    if not isinstance(obj, dict) or "sent_len" not in obj or "samples" not in obj:
        raise UsageError("{} 不是本包生成的风格档案（缺 sent_len / samples 字段）".format(p))
    return obj


def _write_text(path, text):
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def _emit(a, result, md_text, ok=True):
    """统一出口：`--json` 时补 ok 写**真 stdout**（同时落 `--out`），否则打人读文本。"""
    if a.json:
        body = _json_text(result, indent=2, ok=ok)
        if a.out:
            guard_outdir(a.out, "--out")
            _write_text(a.out, body)
            sys.stderr.write("已写入 {}\n".format(a.out))
        _json_write(body)
        return
    if a.out:
        guard_outdir(a.out, "--out")
        _write_text(a.out, md_text)
        sys.stderr.write("已写入 {}\n".format(a.out))
    print(md_text)


def _profile_for_echo(profile):
    return profile_samples_for_echo(profile)


def gate_draft(text_title, body, profile, sample_texts=None, is_draft=True):
    """对一篇稿子跑全部本地闸门，返回 gates 字典。

    五项硬闸门（`ok=False` 即拦截）：
      1. 合规       广告法违禁词；「最X」按可枚举语境豁免、句首不豁免
      2. 占位符残留 {} / [待填] / XXX / TODO
      3. prompt_echo 与提示词示例（样本首尾句）三条判据
      4. 风格偏离   逐指标 vs 档案
      5. 结构缺项   标题 + ≥2 段 + ≥200 汉字
    另有一项防换皮：新稿与样本**全文**的相似度（模型没看到全文也可能撞上）。
    """
    full = (text_title or "") + "\n" + (body or "")
    comp = compliance_scan(full)
    ph = placeholder_scan(full)
    echo = prompt_echo_scan(body or "", _profile_for_echo(profile))
    echo += prompt_echo_scan(text_title or "", _profile_for_echo(profile), label="标题")
    st_ok, st = structure_gate(text_title, body)
    cmp_result = compare(profile, body or "")
    gates = {
        "compliance": {"ok": not comp["hits"], "hits": comp["hits"],
                       "exempted": comp["exempted"]},
        "placeholder": {"ok": not ph, "hits": ph},
        "prompt_echo": {"ok": not echo, "hits": echo},
        "structure": {"ok": st_ok, "missing": st["missing"], "detail": st},
        "style": {"ok": cmp_result["ok"], "fail_count": cmp_result["fail_count"],
                  "metric_count": cmp_result["metric_count"],
                  "style_score": cmp_result["style_score"],
                  "fails": cmp_result["fails"]},
    }
    if sample_texts:
        sim, who = sample_overlap(body or "", sample_texts)
        gates["sample_overlap"] = {
            "ok": sim < SAMPLE_OVERLAP_FAIL,
            "sim": round(sim, 4), "who": who,
            "threshold": SAMPLE_OVERLAP_FAIL,
            "warn": sim >= SAMPLE_OVERLAP_WARN,
        }
    gates["ok"] = all(g.get("ok", True) for k, g in gates.items() if k != "sample_overlap") \
        and gates.get("sample_overlap", {"ok": True})["ok"]
    return gates, cmp_result


def gate_report(name, gates):
    """把命中汇总到 stderr。返回该稿是否被拦。"""
    reasons = []
    g = gates
    if not g["compliance"]["ok"]:
        reasons.append("合规：命中 " + "、".join(
            "「{}」({})".format(h["word"], h["level"]) for h in g["compliance"]["hits"]))
    if not g["placeholder"]["ok"]:
        reasons.append("占位符：" + "；".join(h["why"] for h in g["placeholder"]["hits"]))
    if not g["prompt_echo"]["ok"]:
        reasons.append("照抄示例：" + "；".join(h["why"] for h in g["prompt_echo"]["hits"]))
    if not g["structure"]["ok"]:
        reasons.append("结构缺项：" + "、".join(g["structure"]["missing"]))
    if not g["style"]["ok"]:
        detail = "、".join(
            "{} 档案 {} 实测 {}{}".format(
                r["label"], _fmt_num(r["profile"]), _fmt_num(r["got"]),
                "（{}）".format(r["got"]) if r["kind"] == "class" else "")
            for r in g["style"]["fails"][:6])
        reasons.append("风格偏离 {} 项：{}".format(g["style"]["fail_count"], detail))
    so = g.get("sample_overlap")
    if so and not so["ok"]:
        reasons.append("疑似照搬样本：与{}的相似度 {:.3f} ≥ {:.2f}".format(
            so["who"], so["sim"], so["threshold"]))
    if reasons:
        sys.stderr.write("\n!! [{}] 被硬闸门拦下，不可直接发布：\n".format(name))
        for r in reasons:
            sys.stderr.write("   - {}\n".format(r))
        return True
    # 被豁免的疑似命中也要说一声，**不静默放过**
    ex = g["compliance"].get("exempted") or []
    if ex:
        sys.stderr.write("\n提示：[{}] 本地放过 {} 处疑似绝对化用语"
                         "（判定为「在说数据极值」而不是商品宣称）。这是启发式判断，"
                         "请人工确认：\n".format(name, len(ex)))
        for e in ex:
            sys.stderr.write("   「{}」：…{}…\n".format(e["word"], e["context"]))
    if so and so.get("warn"):
        sys.stderr.write("提示：[{}] 与{}的相似度 {:.3f} 已接近换皮线 {:.2f}。\n".format(
            name, so["who"], so["sim"], so["threshold"]))
    return False


def _run_profile(a):
    """抽风格档案。

    **`--out` 在 `--json` 下写 JSON、在非 `--json` 下写 Markdown**，与全族口径一致
    （同 `_emit`）。第一版这里两种模式都写 JSON，结果文档里教的
    `profile --out profile.json`（不带 --json）写出来的是一个 Markdown 文件，
    下一步 `write --profile` 直接报"不是合法 JSON"。**这是自测时踩出来的**：
    能用不起来的命令写进文档，比不写更糟。
    """
    texts, names = read_samples(a)
    profile = build_profile(texts, names)
    guard_outdir(a.outdir, "--outdir")
    md = render_profile_md(profile)
    if a.json:
        result = dict(profile)
        if a.out:
            guard_outdir(a.out, "--out")
            _write_text(a.out, _json_text(result, indent=2))
            sys.stderr.write("已写入 {}（JSON 格式）\n".format(a.out))
        _json_write(_json_text(result, indent=2))
        if a.outdir:
            base = Path(a.outdir)
            base.mkdir(parents=True, exist_ok=True)
            _write_text(base / "style-profile.json", _json_text(profile, indent=2))
            _write_text(base / "style-profile.md", md)
            sys.stderr.write("风格档案已落盘：{}/style-profile.json\n".format(base))
        return EXIT_OK
    if a.out:
        guard_outdir(a.out, "--out")
        _write_text(a.out, md)
        sys.stderr.write("已写入 {}（Markdown 格式；要 JSON 请加 --json）\n".format(a.out))
    if a.outdir:
        base = Path(a.outdir)
        base.mkdir(parents=True, exist_ok=True)
        _write_text(base / "style-profile.json", _json_text(profile, indent=2))
        _write_text(base / "style-profile.md", md)
        sys.stderr.write("风格档案已落盘：{}/style-profile.json（JSON）+ style-profile.md\n".format(base))
    print(md)
    return EXIT_OK


def _run_baseline(a):
    """自证：样本自身对档案的通过率 + 自相似阈值。

    **这是本包"可测量还是读起来像"那一条的内建证据。**
    如果同账号的样本自己对不上自己的档案，那这份档案就是假的，
    后面所有"通过 / 不通过"都没有意义。
    """
    texts, names = read_samples(a)
    profile = build_profile(texts, names)
    rows = []
    for i, t in enumerate(texts):
        c = compare(profile, t)
        rows.append({"sample": names[i], "han": han_len(t),
                     "sent_len_mean": c["current"]["sent_len"]["mean"],
                     "style_score": c["style_score"], "fail_count": c["fail_count"],
                     "fails": [r["label"] for r in c["fails"]]})
    sd = profile["self_similarity"]
    sc = profile["self_check"]
    result = {
        "samples": profile["samples"],
        "self_similarity": sd,
        "threshold": sd["threshold"],
        "tolerance": profile["tolerance"],
        "self_check": sc,
        "per_sample": rows,
        "note": "自相似阈值 = 样本两两风格指纹相似度的最低值。它是本包判'像不像'的"
                "经验下界：低于它，就不比同一个人的稿子之间更像。"
                "自证通过率 = 样本自己套档案的通过率，必须是 100%（容差就是按它标定的）。",
    }
    if a.json:
        if a.out:
            guard_outdir(a.out, "--out")
            _write_text(a.out, _json_text(result, indent=2))
            sys.stderr.write("已写入 {}（JSON）\n".format(a.out))
        _json_write(_json_text(result, indent=2))
        return EXIT_OK
    out = []
    out.append("# 样本自身一致性基线（自证）")
    out.append("")
    out.append("**样本自己套自己的档案，通过率 {}/{} = {:.0%}**。"
               "容差（dev_limit）就是按这个标定的：同一个人写的稿子必须先过得去，"
               "闸门才有资格拦别人。".format(sc["passed"], sc["total"], sc["pass_rate"]))
    out.append("")
    out.append("| 样本 | 汉字 | 平均句长 | 一致度 | 偏离项 |")
    out.append("|---|---|---|---|---|")
    for r in rows:
        out.append("| {} | {} | {:.1f} | {}/100 | {} |".format(
            r["sample"], r["han"], r["sent_len_mean"], r["style_score"],
            "、".join(r["fails"]) if r["fails"] else "无"))
    out.append("")
    out.append("## 风格指纹：样本两两相似度（**反例判据**）")
    out.append("")
    out.append("| 组合 | 相似度 |")
    out.append("|---|---|")
    for p in sd["pairwise"][:20]:
        out.append("| 样本{} ↔ 样本{} | {:.3f} |".format(p["a"], p["b"], p["sim"]))
    if len(sd["pairwise"]) > 20:
        out.append("| …（共 {} 对） | |".format(sd["pairs"]))
    out.append("")
    out.append("- 均值 **{:.3f}**｜最低 **{:.3f}**｜最高 **{:.3f}**".format(
        sd["mean"], sd["min"], sd["max"]))
    out.append("- **自相似阈值 {:.3f}**：这是同一个人写的稿子之间**最低**的相似度。"
               "任何稿子与样本集的风格指纹相似度低于它，就不比样本之间更像，"
               "也就不该判为'同一个账号'。".format(sd["threshold"]))
    out.append("")
    out.append("## 自标定出的容差（dev_limit = 容许偏差 ÷ 带宽）")
    out.append("")
    out.append("| 指标 | dev_limit | 样本观测到的最大相对偏差 |")
    out.append("|---|---|---|")
    for k in sorted(profile["tolerance"]):
        v = profile["tolerance"][k]
        if v.get("kind") == "class":
            out.append("| {} | 类别判据 | {} |".format(k, v.get("note", "")))
        else:
            out.append("| {} | {:.2f} | {} |".format(
                k, v.get("dev_limit", 1.0), v.get("sample_max_rel", "-")))
    text = "\n".join(out)
    if a.out:
        guard_outdir(a.out, "--out")
        _write_text(a.out, text)
        sys.stderr.write("已写入 {}（Markdown；要 JSON 请加 --json）\n".format(a.out))
    print(text)
    return EXIT_OK


def _draft_from_args(a):
    """verify / diff 的稿子输入：`--result` 读 write 的 JSON，`--file`/`--text` 读纯文本。"""
    if a.result:
        p = Path(a.result)
        if not p.is_file():
            raise UsageError("找不到结果文件：{}".format(a.result))
        try:
            obj = json.loads(_strip_bom(p.read_text(encoding="utf-8", errors="replace")))
        except ValueError as exc:
            raise UsageError("{} 不是合法 JSON：{}".format(a.result, exc))
        draft = obj.get("draft") if isinstance(obj, dict) else None
        if not isinstance(draft, dict):
            draft = obj if isinstance(obj, dict) else {}
        title = draft.get("title") or ""
        body = draft.get("body") or ""
        if not body:
            raise UsageError("{} 里没有 draft.body 字段（不是 `write --json --out` 的结果文件？）".format(
                a.result))
        return title, body, {"source": a.result, "meta": obj}
    if a.text:
        t = _strip_bom(a.text)
        lines = [l for l in t.splitlines() if l.strip()]
        title = lines[0].lstrip("# ").strip() if lines else ""
        return title, t, {"source": "命令行 --text", "meta": {}}
    if a.file:
        p = Path(a.file)
        if not p.is_file():
            raise UsageError("找不到稿子文件：{}".format(a.file))
        t = _read_text(p)
        lines = [l for l in t.splitlines() if l.strip()]
        title = lines[0].lstrip("# ").strip() if lines else ""
        return title, t, {"source": a.file, "meta": {}}
    raise UsageError("没给稿子。用 --result <write 的结果.json> 或 --file <稿子.md> 或 --text \"...\"")


def _run_verify(a):
    profile = _load_profile(a.profile)
    title, body, meta = _draft_from_args(a)
    sample_texts = None
    if a.samples or a.sample_files:
        sample_texts, _names = read_samples(a)
    gates, cmp_result = gate_draft(title, body, profile, sample_texts)
    result = {
        "profile_samples": profile["samples"]["count"],
        "draft": {"title": title, "han": han_len(body),
                  "sentences": cmp_result["current"]["sentences"],
                  "paragraphs": cmp_result["current"]["paragraphs"]},
        "style_score": cmp_result["style_score"],
        "metric_count": cmp_result["metric_count"],
        "fail_count": cmp_result["fail_count"],
        "mean_dev": cmp_result["mean_dev"],
        "max_dev": cmp_result["max_dev"],
        "metrics": cmp_result["rows"],
        "gates": gates,
        "source": meta["source"],
    }
    blocked = gate_report("verify " + (meta["source"] or ""), gates)
    if a.json:
        body_json = _json_text(result, indent=2, ok=not blocked)
        if a.out:
            guard_outdir(a.out, "--out")
            _write_text(a.out, body_json)
            sys.stderr.write("已写入 {}\n".format(a.out))
        _json_write(body_json)
        return EXIT_GATE if blocked else EXIT_OK
    md = render_verify_md(cmp_result, profile, cmp_result["current"], title)
    if a.out:
        guard_outdir(a.out, "--out")
        _write_text(a.out, md)
        sys.stderr.write("已写入 {}\n".format(a.out))
    print(md)
    return EXIT_GATE if blocked else EXIT_OK


def _run_diff(a):
    profile = _load_profile(a.profile)
    title, body, meta = _draft_from_args(a)
    cmp_result = compare(profile, body)
    label = a.label or Path(meta["source"]).name if meta["source"] else "新稿"
    result = {
        "profile_samples": profile["samples"]["count"],
        "style_score": cmp_result["style_score"],
        "fail_count": cmp_result["fail_count"],
        "metric_count": cmp_result["metric_count"],
        "rows": cmp_result["rows"],
    }
    if a.json:
        _json_out(result, a, indent=2)
        if a.out:
            guard_outdir(a.out, "--out")
            _write_text(a.out, _json_text(result, indent=2))
            sys.stderr.write("已写入 {}\n".format(a.out))
        return EXIT_OK
    md = render_diff_md(cmp_result, profile, label)
    if a.out:
        guard_outdir(a.out, "--out")
        _write_text(a.out, md)
        sys.stderr.write("已写入 {}\n".format(a.out))
    print(md)
    return EXIT_OK


def _state_key(a, profile, texts):
    """断点 key：**含全部影响产出的维度**。

    同族踩过的坑：内容截断 / `resolution` 不入 key / 死参数 → 静默复用旧产物。
    所以这里把「样本集摘要 + 档案摘要 + 题目 + 模型 + 温度 + max_tokens + 迭代轮」
    全部塞进 key。任何一项变了，key 就变，就不会复用旧稿。
    """
    import hashlib
    h = hashlib.sha256()
    h.update(json.dumps({
        "samples": [
            {"name": n, "han": han_len(t), "sha": hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]}
            for n, t in zip(profile["samples"]["names"], texts)
        ],
        "profile": {
            "count": profile["samples"]["count"],
            "sent_mean": profile["sent_len"]["mean"],
            "para_mean": profile["para_len"]["mean"],
            "person": profile["person"]["mean_frac"],
            "threshold": profile["self_similarity"]["threshold"],
            "catch": [c["ng"] for c in profile["catchphrases"]],
        },
        "topic": a.topic, "brief": a.brief, "evidence": a.evidence,
        "model": a.model, "temperature": a.temperature, "max_tokens": a.max_tokens,
        "iterations": a.iterations,
    }, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return h.hexdigest()[:16]


def _run_write(a):
    profile = _load_profile(a.profile)
    guard_outdir(a.outdir, "--outdir")
    prompt = build_write_prompt(profile, a.topic, a.evidence, a.brief)
    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "system": SYSTEM_PROMPT, "user": prompt}, a, indent=2)
        else:
            print("=== system ===\n{}\n\n=== user ===\n{}".format(SYSTEM_PROMPT, prompt))
        return EXIT_OK

    est_in = estimate_tokens_in(SYSTEM_PROMPT + prompt)
    est_out = estimate_tokens_out(int(round(profile["samples"]["han_mean"] * 1.15)))
    est = compute_cost(est_in, est_out, a.price_in, a.price_out)
    if a.price_in is not None:
        sys.stderr.write("预估：{}\n".format(fmt_cost(est)))
    if a.budget is not None and est["points"] is not None and est["points"] > a.budget:
        sys.stderr.write("!! 预估成本 {} 点已超过 --budget {} 点，就地中止（还没花钱）。\n".format(
            est["points"], a.budget))
        return _fail(EXIT_BUDGET, "budget",
                     "预估成本 %s 点已超过 --budget %s 点" % (est["points"], a.budget))

    sys.stderr.write("正在用 `{}` 按档案写稿（目标 {} 汉字）…\n".format(
        a.model, int(round(profile["samples"]["han_mean"]))))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                          max_tokens=a.max_tokens, key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    obj = parse_first_json(content)
    if not isinstance(obj, dict):
        raise StyleError("模型返回的不是 JSON 对象")
    title = (obj.get("title") or "").strip()
    body = (obj.get("body") or "").strip()
    if not body:
        raise StyleError("模型没产出正文（检查 --max-tokens 与模型名）")
    gates, cmp_result = gate_draft(title, body, profile)
    result = {
        "model": a.model,
        "chat_endpoint": CHAT_URL,
        "usage": usage,
        "elapsed": round(elapsed, 1),
        "profile_summary": {
            "samples": profile["samples"]["count"],
            "sent_len_mean": profile["sent_len"]["mean"],
            "sent_len_band": profile["sent_len"]["band"],
            "para_len_mean": profile["para_len"]["mean"],
            "dominant_person": profile["person"]["dominant"],
            "self_similarity_threshold": profile["self_similarity"]["threshold"],
        },
        "draft": {"title": title, "body": body,
                  "style_notes": obj.get("style_notes") or ""},
        "style_score": cmp_result["style_score"],
        "fail_count": cmp_result["fail_count"],
        "metric_count": cmp_result["metric_count"],
        "metrics": cmp_result["rows"],
        "gates": gates,
        "cost_estimate": est,
    }
    blocked = gate_report("write", gates)
    md = ["# 新稿｜按风格档案写", ""]
    md.append("- 模型：`{}`　端点：`POST /api/v1/chat/completions`".format(a.model))
    md.append("- token：prompt={} completion={} total={}".format(
        usage.get("prompt_tokens", "-"), usage.get("completion_tokens", "-"),
        usage.get("total_tokens", "-")))
    md.append("- 耗时：{:.1f}s".format(elapsed))
    md.append("- 风格一致度：**{}/100**（偏离 {}/{} 项）".format(
        cmp_result["style_score"], cmp_result["fail_count"], cmp_result["metric_count"]))
    md.append("")
    md.append("## {}".format(title))
    md.append("")
    md.append(body)
    if obj.get("style_notes"):
        md.append("")
        md.append("> 模型自述的贴合动作：{}".format(obj.get("style_notes")))
    md.append("")
    md.append(render_verify_md(cmp_result, profile, cmp_result["current"], title))
    _emit(a, result, "\n".join(md), ok=not blocked)
    return EXIT_GATE if blocked else EXIT_OK


def _run_all(a):
    texts, names = read_samples(a)
    profile = build_profile(texts, names)
    guard_outdir(a.outdir, "--outdir")
    if a.outdir:
        base = Path(a.outdir)
        base.mkdir(parents=True, exist_ok=True)
        _write_text(base / "style-profile.json", _json_text(profile, indent=2))
        _write_text(base / "style-profile.md", render_profile_md(profile))
        sys.stderr.write("风格档案已落盘：{}/style-profile.json\n".format(base))

    if a.dry_run:
        prompt = build_write_prompt(profile, a.topic, a.evidence, a.brief)
        if a.json:
            _json_out({"dry_run": True, "system": SYSTEM_PROMPT, "user": prompt,
                       "profile": profile}, a, indent=2)
        else:
            print("=== system ===\n{}\n\n=== user ===\n{}".format(SYSTEM_PROMPT, prompt))
        return EXIT_OK

    # 预检：样本之间像不像同一个账号。
    # 判据用**自标定阈值**（两两相似度最小值的一半），不是拍脑袋的绝对值——
    # 第一版写的是硬编码 `< 0.10`，实测把同一批 6 篇同风格样本（min 0.096）
    # 判成了"不像同一个账号"并拒绝往下跑。**阈值写死就会犯这种错**：
    # 一个数不可能同时适配"公众号长文"和"短句口语"两种稿子的指纹尺度。
    sd = profile["self_similarity"]
    if sd["mix_flagged"]:
        mp = sd["mix_pair"] or {}
        sys.stderr.write(
            "!! 样本自相似阈值 {:.4f}：样本 {} 与样本 {} 的相似度只有 {:.4f}，"
            "低于全体均值 {:.4f} 的 {:.0%}。\n"
            "   这通常意味着**样本里混了别的作者的稿子**。抽出来的档案会是几篇的\n"
            "   平均值，而不是任何一篇的调性。建议先剔掉不像的那篇再跑。\n".format(
                sd["threshold"], mp.get("a", "?"), mp.get("b", "?"), mp.get("sim", 0.0),
                sd["mean"], sd["min_ratio"]))
        if not a.force:
            return _fail(EXIT_USAGE, "usage",
                         "样本相似度最低的一对只有 %.4f（全体均值 %.4f 的 %.0f%%），"
                         "疑似混了别的作者；加 --force 可强行继续"
                         % (mp.get("sim", 0.0), sd["mean"], sd["min_ratio"] * 100))
    elif sd["pairs"] and sd["threshold"] < 0.01:
        sys.stderr.write(
            "!! 样本自相似阈值只有 {:.4f}（< 0.01）：整批样本彼此的风格指纹几乎不重叠，\n"
            "   这不是'一个账号的调性'，硬写出来的稿子会是几篇的平均值。\n".format(
                sd["threshold"]))
        if not a.force:
            return _fail(EXIT_USAGE, "usage",
                         "样本自相似阈值 %.4f < 0.01，样本之间不像同一个账号"
                         "（加 --force 可强行继续）" % sd["threshold"])

    iterations = max(1, int(a.iterations or 1))
    price_in, price_out = a.price_in, a.price_out
    if a.budget is not None and (price_in is None or price_out is None):
        sys.stderr.write(
            "配置错误：给了 --budget 就必须给单价，否则预算没有任何意义。\n"
            "  接口的 pricing 表实测不含文本大模型、models 列表也没有价格字段，\n"
            "  所以本包拒绝凭空编一个单价。请补 --price-in / --price-out"
            "（单位：点/百万 token）。\n")
        return _fail(EXIT_USAGE, "usage", "给了 --budget 就必须给单价（本包拒绝编造单价）")

    history = []
    spents = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    spent_pts = 0.0
    draft = None
    cmp_result = None
    gates = None
    demo = build_write_prompt(profile, a.topic, a.evidence, a.brief)
    est_in = estimate_tokens_in(SYSTEM_PROMPT + demo)
    est_out = estimate_tokens_out(int(round(profile["samples"]["han_mean"] * 1.15)))
    est = compute_cost(est_in * iterations, est_out * iterations, price_in, price_out)
    if price_in is not None:
        sys.stderr.write("预估（{} 轮上限）：{}\n".format(iterations, fmt_cost(est)))
    if a.budget is not None and est["points"] is not None and est["points"] > a.budget:
        sys.stderr.write(
            "!! 预估成本 {} 点已超过 --budget {} 点（{} 轮上限），就地中止（还没花钱）。\n".format(
                est["points"], a.budget, iterations))
        return _fail(EXIT_BUDGET, "budget",
                     "预估成本 %s 点已超过 --budget %s 点（%d 轮上限），就地中止（还没花钱）"
                     % (est["points"], a.budget, iterations))

    feedback = None
    t_all = time.time()
    best = None      # 保留**最好的一轮**，不是最后一轮
    for rnd in range(1, iterations + 1):
        if rnd == 1:
            prompt = build_write_prompt(profile, a.topic, a.evidence, a.brief)
        else:
            if cmp_result is None or not cmp_result["fails"]:
                break
            prompt = build_repair_prompt(profile, a.topic, draft["body"], cmp_result, a.evidence)
        sys.stderr.write("[第 {}/{} 轮] 调 `{}` 写稿…\n".format(rnd, iterations, a.model))
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                              max_tokens=a.max_tokens, key=a.key, json_mode=not a.no_json_mode)
        el = time.time() - t0
        obj = parse_first_json(content)
        if not isinstance(obj, dict) or not (obj.get("body") or "").strip():
            raise StyleError("第 {} 轮模型没产出正文".format(rnd))
        draft = {"title": (obj.get("title") or "").strip(),
                 "body": (obj.get("body") or "").strip(),
                 "style_notes": obj.get("style_notes") or ""}
        gates, cmp_result = gate_draft(draft["title"], draft["body"], profile, texts)
        history.append({
            "round": rnd, "usage": usage, "elapsed": round(el, 1),
            "style_score": cmp_result["style_score"],
            "fail_count": cmp_result["fail_count"],
            "han": han_len(draft["body"]),
            "fails": [r["label"] for r in cmp_result["fails"]],
        })
        # 【为什么必须记最好的一轮】实测：第 2 轮把偏离从 7 项压到 4 项，
        # 第 3 轮**又退回到同样的 4 项、分数一模一样**——定点修到了天花板之后
        # 还会来回摆。如果最后吐的是"最后一轮"，产出质量就取决于轮数奇偶，这说不通。
        # 记分规则：偏离项少者优先，同分看一致度，再同分保留更早的那一轮（少花钱）。
        key = (cmp_result["fail_count"], -cmp_result["style_score"])
        if best is None or key < best["key"]:
            best = {"key": key, "round": rnd, "draft": dict(draft),
                    "cmp": cmp_result, "gates": gates}
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if isinstance(usage.get(k), int):
                spents[k] += usage[k]
        spent_pts = compute_cost(spents["prompt_tokens"], spents["completion_tokens"],
                                 price_in, price_out)["points"] or 0.0
        sys.stderr.write("   一致度 {}/100，偏离 {} 项，正文 {} 汉字{}\n".format(
            cmp_result["style_score"], cmp_result["fail_count"], han_len(draft["body"]),
            "" if cmp_result["ok"] else "（" + "、".join(r["label"] for r in cmp_result["fails"][:5]) + "）"))
        if a.budget is not None and price_in is not None and spent_pts > a.budget:
            sys.stderr.write("!! 已花 {} 点，超过 --budget {} 点，就地中止。\n".format(
                spent_pts, a.budget))
            _emit_all_result(a, profile, draft, cmp_result, gates, history, spents, texts,
                             time.time() - t_all, ok=False)
            return _fail(EXIT_BUDGET, "budget",
                         "已花 %s 点超过 --budget %s 点，就地中止（已完成 %d 轮）"
                         % (spent_pts, a.budget, rnd))
        if cmp_result["ok"]:
            sys.stderr.write("   ✅ 全部指标落在容差内，停止迭代。\n")
            break

    if best and best["round"] != (history[-1]["round"] if history else 0):
        sys.stderr.write(
            "提示：共 {} 轮，最终采用**第 {} 轮**（偏离 {} 项）；最后一轮偏离 {} 项、更差，已丢弃。"
            "迭代不是单调变好，所以本包保留最好的一轮。\n".format(
                len(history), best["round"], best["cmp"]["fail_count"],
                history[-1]["fail_count"]))
    if best:
        draft, cmp_result, gates = best["draft"], best["cmp"], best["gates"]
    blocked = _emit_all_result(a, profile, draft, cmp_result, gates, history, spents, texts,
                               time.time() - t_all, ok=not (gates and not gates["ok"]),
                               best_round=(best or {}).get("round"))
    return EXIT_GATE if blocked else EXIT_OK


def _emit_all_result(a, profile, draft, cmp_result, gates, history, spents, texts, elapsed,
                     ok=True, best_round=None):
    actual = compute_cost(spents.get("prompt_tokens"), spents.get("completion_tokens"),
                          a.price_in, a.price_out)
    result = {
        "model": a.model,
        "chat_endpoint": CHAT_URL,
        "profile": profile,
        "profile_summary": {
            "samples": profile["samples"]["count"],
            "sent_len_mean": profile["sent_len"]["mean"],
            "sent_len_band": profile["sent_len"]["band"],
            "para_len_mean": profile["para_len"]["mean"],
            "self_similarity_threshold": profile["self_similarity"]["threshold"],
        },
        "topic": a.topic,
        "draft": draft,
        "style_score": cmp_result["style_score"] if cmp_result else None,
        "fail_count": cmp_result["fail_count"] if cmp_result else None,
        "metric_count": cmp_result["metric_count"] if cmp_result else None,
        "metrics": cmp_result["rows"] if cmp_result else [],
        "gates": gates,
        "iterations": history,
        "best_round": best_round,
        "usage_totals": spents,
        "cost_actual_tokens": actual,
        "elapsed": round(elapsed, 1),
    }
    blocked = False
    if gates:
        blocked = gate_report("all", gates)
    overall_ok = bool(ok and gates and gates.get("ok")) if gates else bool(ok)
    md = ["# 风格克隆｜抽档 → 写 → 自检"]
    md.append("")
    md.append("- 样本 {} 篇｜平均句长 {:.1f}（±{:.1f}）｜平均段长 {:.1f}｜自相似阈值 {:.3f}".format(
        profile["samples"]["count"], profile["sent_len"]["mean"], profile["sent_len"]["band"],
        profile["para_len"]["mean"], profile["self_similarity"]["threshold"]))
    md.append("- 迭代：{} 轮｜token 合计 prompt={} completion={}".format(
        len(history), spents["prompt_tokens"], spents["completion_tokens"]))
    if best_round:
        md.append("- **采用第 {} 轮**（迭代不单调变好，本包保留偏离最少的那一轮）".format(best_round))
    md.append("")
    for h in history:
        star = " ←采用" if best_round == h["round"] else ""
        md.append("- 第 {} 轮：一致度 {}/100，偏离 {} 项，正文 {} 汉字{}{}".format(
            h["round"], h["style_score"], h["fail_count"], h.get("han", "-"),
            "" if not h["fails"] else "（" + "、".join(h["fails"]) + "）", star))
    md.append("")
    if draft:
        md.append("## {}".format(draft["title"]))
        md.append("")
        md.append(draft["body"])
        md.append("")
    if cmp_result:
        md.append(render_verify_md(cmp_result, profile, cmp_result["current"], draft["title"]))
    text = "\n".join(md)
    if a.json:
        body = _json_text(result, indent=2, ok=overall_ok)
        if a.out:
            guard_outdir(a.out, "--out")
            _write_text(a.out, body)
            sys.stderr.write("已写入 {}\n".format(a.out))
        _json_write(body)
    else:
        if a.out:
            guard_outdir(a.out, "--out")
            _write_text(a.out, text)
            sys.stderr.write("已写入 {}\n".format(a.out))
        print(text)
    if a.outdir and draft:
        base = Path(a.outdir)
        _write_text(base / "draft.md", text)
        _write_text(base / "draft.json", _json_text(result, indent=2, ok=overall_ok))
        sys.stderr.write("新稿已落盘：{}/draft.md、{}/draft.json\n".format(base, base))
    return blocked


def _run_cost(a):
    # 两种口径：按样本目录估算，或按 write/all 的结果文件读真实 usage
    if a.from_result:
        p = Path(a.from_result)
        if not p.is_file():
            raise UsageError("找不到结果文件：{}".format(a.from_result))
        try:
            obj = json.loads(_strip_bom(p.read_text(encoding="utf-8", errors="replace")))
        except ValueError as exc:
            raise UsageError("{} 不是合法 JSON：{}".format(a.from_result, exc))
        u = obj.get("usage_totals") or obj.get("usage") or {}
        rec = compute_cost(u.get("prompt_tokens"), u.get("completion_tokens"),
                           a.price_in, a.price_out)
        rec["source"] = str(p)
        rec["usage"] = u
        if a.json:
            _json_out(rec, a, indent=2)
            return EXIT_OK
        print("真实 token（读自 {}）：".format(p))
        print("  prompt={} completion={} total={}".format(
            u.get("prompt_tokens", "-"), u.get("completion_tokens", "-"),
            u.get("total_tokens", "-")))
        print("  {}".format(fmt_cost(rec)))
        print("  单位：{}".format(rec["unit"]))
        for n in rec["notes"]:
            print("  注：{}".format(n))
        return EXIT_OK

    texts, names = read_samples(a)
    profile = build_profile(texts, names)
    prompt = build_write_prompt(profile, a.topic or "（未给主题）", a.evidence, a.brief)
    tin = estimate_tokens_in(SYSTEM_PROMPT + prompt)
    tout = estimate_tokens_out(int(round(profile["samples"]["han_mean"] * 1.15)))
    rec = compute_cost(tin, tout, a.price_in, a.price_out)
    rec["iterations"] = max(1, int(a.iterations or 1))
    rec["samples"] = {"count": profile["samples"]["count"],
                      "han_mean": profile["samples"]["han_mean"]}
    if a.budget is not None:
        if a.price_in is None or a.price_out is None:
            return _fail(EXIT_USAGE, "usage", "给了 --budget 就必须给单价（本包拒绝编造单价）")
        tot = compute_cost(tin * rec["iterations"], tout * rec["iterations"],
                           a.price_in, a.price_out)
        over = (tot["points"] or 0) > a.budget
        rec["budget_check"] = {"budget": a.budget, "est_points": tot["points"],
                               "ok": not over, "iters": rec["iterations"]}
        if over:
            # **超预算是一道硬闸门（退出码 5），不是提示。**
            # 与 write / all 的预检同一口径：还没花钱就中止，退出码必须能让 CI 看见。
            sys.stderr.write(
                "!! 预估成本 {} 点已超过 --budget {} 点：{} 轮 × 每轮约 {} token，"
                "还没花钱，就地中止。\n"
                "   想跑就提高 --budget、减少 --iterations，或换更短的样本集。\n".format(
                    tot["points"], a.budget, rec["iterations"], tin + tout))
            _fail(EXIT_BUDGET, "budget",
                  "预估成本 %s 点已超过 --budget %s 点，就地中止（还没花钱）"
                  % (tot["points"], a.budget))
    if a.json:
        over = (rec.get("budget_check") or {}).get("ok") is False
        # 结果已经吐出来了，`ok` 就要如实写 false（契约：已经吐过结果时不再补信封）
        _json_out(rec, a, indent=2, ok=not over)
        return EXIT_BUDGET if over else EXIT_OK
    print("估算口径（不是账单）：")
    print("  样本 {} 篇，均 {} 汉字".format(
        profile["samples"]["count"], profile["samples"]["han_mean"]))
    print("  输入约 {} token（提示词 {} 字符 ÷ 1.61）".format(tin, len(SYSTEM_PROMPT + prompt)))
    print("  输出约 {} token（目标 {} 汉字 × 1.11）".format(
        tout, int(round(profile["samples"]["han_mean"] * 1.15))))
    print("  {}".format(fmt_cost(rec)))
    print("  单位：点/百万 token")
    for n in rec["notes"]:
        print("  注：{}".format(n))
    if "budget_check" in rec:
        bc = rec["budget_check"]
        print("  预算：预估 {} 点 vs 上限 {} 点 → {}".format(
            bc["est_points"], bc["budget"], "通过" if bc["ok"] else "超限"))
    if "budget_check" in rec and rec["budget_check"]["ok"] is False:
        return _fail(EXIT_BUDGET, "budget",
                     "预估成本 %s 点已超过 --budget %s 点，就地中止（还没花钱）"
                     % (rec["budget_check"]["est_points"], rec["budget_check"]["budget"]))
    return EXIT_OK


def _run_models(a):
    key = a7w.load_key(a.key)
    try:
        payload = a7w._request("GET", MODELS_URL, key, timeout=60)
    except a7w.A7wError as exc:
        raise StyleError(str(exc))
    rows = []
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        rows = data
    elif isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        for v in payload["data"].values():
            if isinstance(v, list):
                rows.extend(v)
    sel = []
    for m in rows:
        if not isinstance(m, dict):
            continue
        t = m.get("type") or m.get("model_type") or ""
        if a.type != "all" and t and t != a.type:
            continue
        sel.append(m)
    if a.json:
        _json_out({"type": a.type, "count": len(sel), "models": sel}, a, indent=2)
        return EXIT_OK
    print("在架模型 {} 个（https://api.a7w.cn/api/v1/models）".format(len(sel)))
    print("")
    for m in sel:
        name = m.get("model") or m.get("name") or m.get("model_name") or "?"
        t = m.get("type") or m.get("model_type") or ""
        print("  {:<28} {:<8} {}".format(str(name), str(t), m.get("title") or ""))
    print("")
    print("提示：`deepseek-chat` 这个别名实测可用（路由到 deepseek-flash），"
          "但它**不在**上面这个列表里 —— 「列表里没有」不等于「不能用」。")
    return EXIT_OK


# ---------------------------------------------------------------------------
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封（已经吐过结果的，ok 写在那个结果里）
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#
# 信封必须落在**真 stdout**：JSON 文本统一经 `_json_write` 写。
# ---------------------------------------------------------------------------

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}

_KIND_BY_EXIT = {2: "usage", 3: "gate", 4: "call", 5: "budget", 130: "interrupt"}


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
    if _JSON["reason"] is None:
        _JSON["reason"] = {"kind": kind, "message": message, "detail": detail}
    return rc


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（同族口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py verify --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_sample_opts(p):
    p.add_argument("--samples", action="append",
                   help="样本：目录或文件，可重复多次（目录会递归找 .md/.txt/.markdown）")
    p.add_argument("--sample-files", action="append", dest="sample_files",
                   help="单个样本文件，可重复多次（与 --samples 等价，写起来更明确）")


def _add_model_opts(p, with_cost=False):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 {}（实测可用；用 `run.py models` 现查在架模型）".format(
                       DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens",
                   help="最大输出 token，默认 4096")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--out", help="把结果写到这个文件（必须在包外）")
    p.add_argument("--outdir", help="产出目录（必须在包外）")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")
    if with_cost:
        _add_cost_opts(p)


def _add_cost_opts(p):
    p.add_argument("--price-in", type=float, dest="price_in",
                   help="输入单价，单位「点/百万 token」。不给我就不给金额（不编价）")
    p.add_argument("--price-out", type=float, dest="price_out",
                   help="输出单价，单位「点/百万 token」")
    p.add_argument("--budget", type=float,
                   help="预算上限（点）。超了就地中止，退出码 5；用 --budget 必须给单价")


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与以前完全一致。
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
            raise                                 # 非 --json：原样冒泡
        traceback.print_exc()                     # 完整栈 → stderr（不吞、不截断）
        _json_internal(exc)
        return 1


def _main(argv_eff):
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 风格克隆体（走 api.a7w.cn 的 OpenAI 兼容大模型端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models",
        allow_abbrev=False)
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("profile", help="从样本抽风格档案（纯本地统计，零成本不调模型）", allow_abbrev=False)
    _add_sample_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把档案写到这个文件（必须在包外）")
    p.add_argument("--outdir", help="产出目录（必须在包外）")
    p.set_defaults(func=_run_profile)

    p = sub.add_parser("baseline", help="样本自身的自相似基线（反例判据，零成本）", allow_abbrev=False)
    _add_sample_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件（必须在包外）")
    p.add_argument("--outdir", help="产出目录（必须在包外）")
    p.set_defaults(func=_run_baseline)

    p = sub.add_parser("write", help="按风格档案写一篇新稿（要花 token）", allow_abbrev=False)
    p.add_argument("--profile", required=True, help="风格档案 JSON（profile --out 生成）")
    p.add_argument("--topic", required=True, help="主题 / 选题")
    p.add_argument("--brief", help="额外要求")
    p.add_argument("--evidence", help="可以使用的真实素材（没写就不许编数字）")
    _add_model_opts(p, with_cost=True)
    p.set_defaults(func=_run_write)

    p = sub.add_parser("verify", help="风格一致性自检：新稿逐指标 vs 档案（纯本地，零成本）", allow_abbrev=False)
    p.add_argument("--profile", required=True, help="风格档案 JSON")
    p.add_argument("--result", help="write/all 的结果 JSON")
    p.add_argument("--file", help="稿子文件（.md/.txt）——拿别的风格的稿子跑就是反例测试")
    p.add_argument("--text", help="直接给稿子正文")
    _add_sample_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件（必须在包外）")
    p.add_argument("--outdir", help="产出目录（必须在包外）")
    p.set_defaults(func=_run_verify)

    p = sub.add_parser("diff", help="档案 vs 新稿的指标对照表（纯本地，零成本）", allow_abbrev=False)
    p.add_argument("--profile", required=True, help="风格档案 JSON")
    p.add_argument("--result", help="write/all 的结果 JSON")
    p.add_argument("--file", help="稿子文件（.md/.txt）")
    p.add_argument("--text", help="直接给稿子正文")
    p.add_argument("--label", help="对照表里右侧那一列的名字")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件（必须在包外）")
    p.add_argument("--outdir", help="产出目录（必须在包外）")
    p.set_defaults(func=_run_diff)

    p = sub.add_parser("all", help="抽档 → 写 → 自检 → 迭代（要花 token）", allow_abbrev=False)
    _add_sample_opts(p)
    p.add_argument("--topic", required=True, help="主题 / 选题")
    p.add_argument("--brief", help="额外要求")
    p.add_argument("--evidence", help="可以使用的真实素材（没写就不许编数字）")
    p.add_argument("--iterations", type=int, default=2,
                   help="最多迭代几轮（默认 2；指标全过就提前停）")
    p.add_argument("--force", action="store_true",
                   help="样本自相似阈值过低时强行继续（默认拒绝，退出码 2）")
    _add_model_opts(p, with_cost=True)
    p.set_defaults(func=_run_all)

    p = sub.add_parser("cost", help="只算钱（不给单价就只报 token，不编价）", allow_abbrev=False)
    _add_sample_opts(p)
    p.add_argument("--from-result", dest="from_result",
                   help="读 write/all 的结果文件，用**真实 token 数**算钱")
    p.add_argument("--topic", help="主题（只影响提示词长度估算）")
    p.add_argument("--brief", help="额外要求")
    p.add_argument("--evidence", help="真实素材")
    p.add_argument("--iterations", type=int, default=2, help="按几轮估算，默认 2")
    _add_cost_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件（必须在包外）")
    p.set_defaults(func=_run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）", allow_abbrev=False)
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=_run_models)

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
    except UsageError as exc:
        sys.stderr.write("参数错误：{}\n".format(exc))
        rc, kind, msg = EXIT_USAGE, "usage", str(exc)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc, kind, msg = EXIT_CALL, "call", str(exc)
    except KeyboardInterrupt:
        sys.stderr.write("已中断\n")
        rc, kind, msg = EXIT_INTERRUPT, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        _json_fail(rc, reason.get("kind") or kind,
                   reason.get("message") or msg, reason.get("detail"), a)
    return rc


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    sys.exit(main())
