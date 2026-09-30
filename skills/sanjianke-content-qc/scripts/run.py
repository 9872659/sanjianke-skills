#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 内容质量闭环 —— 真正干活的脚本（零第三方依赖）。

七个子命令：

    score   给一篇成稿多维打分，并给出**定位到具体句子**的问题清单
    revise  按问题清单重写；`--rounds` 控制迭代轮数，每轮复评
    diff    原稿 vs 定稿的**逐句改动台账**（纯本地，零成本）
    rules   本地规则自检：违禁词 / 占位符 / 字数 / 结构（纯本地，零成本）
    all     完整闭环：评分 → 重写 → 复评，直到达标或轮次用尽；**断点续跑**
    cost    报价：这次闭环大概要花多少 token（金额要你自己填单价）
    models  列出 api.a7w.cn 当前在架的模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py rules  --file 稿子.md
    python3 run.py score  --file 稿子.md --platform wechat
    python3 run.py revise --file 稿子.md --platform wechat --rounds 2 --out 定稿.json
    python3 run.py diff   --before 稿子.md --after 定稿.md
    python3 run.py all    --file 稿子.md --platform wechat --rounds 3 --target 85
    python3 run.py cost   --file 稿子.md --rounds 3 --price-in 1000 --price-out 2000
    python3 run.py score  --file 稿子.md --dry-run     # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py score --file 稿子.md --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍
    · 本包处理的是**别人已经写完的稿**，不是从主题生成。所以它不改题材、不换平台形态、
      不重排结构骨架，只做「哪里不行 → 怎么改 → 改完真的好了吗」这件事。
    · 打分是**大模型给语义分 + 本地做确定性扣分**的混合口径：违禁词命中压合规分、
      字数跑出平台区间压平台适配分。模型瞎给高分骗不过本地闸门。
    · 「定位到句子」不是靠提示词求模型配合，而是**本地校验引文能不能在原稿里找到**
      （见 verify_anchor）。模型编造引文会被锚点闸门拦下并标红，这一点是实测过的。
    · 复评用**同一次调用里匿名双评**（原稿与新稿一起、乱序、只给编号），
      目的是让「涨了多少分」不受两次调用之间评分漂移的影响。见 build_pair_prompt。
    · 违禁词表是**启发式自检**，来自公开经验整理，不构成法律意见，也不等于平台官方审核规则。
"""

import argparse
import difflib
import hashlib
import json
import os
import random
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 不许往包里写 .pyc。同族的包跑一次就会在 scripts/__pycache__/ 留下几个 .pyc
# （实测 longform-factory 里就有），而 Skill 包的上传白名单里没有 .pyc ——
# 上传时会因为一个后缀被拒。在 import a7w **之前**关掉字节码写入，根治这件事。
sys.dont_write_bytecode = True
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

# 退出码。数值与同族（sanjianke-multiplat-rewrite）对齐：
EXIT_OK = 0            # 达标：评分过了目标线，且没有任何硬闸门命中
EXIT_USAGE = 2         # 参数/配置错（文件不存在、--outdir 在包内、给了 --budget 没给单价）
EXIT_GATE = 3          # 硬闸门命中（合规/占位符/照抄示例/丢事实/定位失败/未收敛）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。
# 事故复盘（同族踩过）：改了评分维度权重却不改 key，续跑会把上一版口径的旧产物
# 当成"已完成"直接复用，产出对不上文档。加版本号是最省事的根治办法。
RUBRIC_VERSION = "qc-rubric-1.0.0"
PROMPT_VERSION = "qc-prompt-1.0.0"


# ---------------------------------------------------------------------------
# 五个评分维度
#
# 权重口径：信息密度与结构决定"这篇能不能解决读者的问题"，给最高权重；
# 合规权重最低但**一票否决**（命中违禁词直接压到 1~4 分），
# 因为合规不是"写得好不好"，是"能不能发"。
# ---------------------------------------------------------------------------

DIM_KEYS = ("info_density", "structure", "readability", "compliance", "platform_fit")
DIM_LABEL = {
    "info_density": "信息密度",
    "structure": "结构",
    "readability": "可读性",
    "compliance": "合规",
    "platform_fit": "平台适配",
}
DIM_WEIGHT = {
    "info_density": 0.25,
    "structure": 0.20,
    "readability": 0.20,
    "compliance": 0.15,
    "platform_fit": 0.20,
}

# 维度权重表必须严丝合缝，否则总分会跑出 0~100。启动时就自检，别等线上才发现。
assert abs(sum(DIM_WEIGHT.values()) - 1.0) < 1e-9, "DIM_WEIGHT 必须归一"

DEFAULT_TARGET = 85.0      # 目标线（0~100）。达标即停。


# ---------------------------------------------------------------------------
# 平台口径：字数区间、段数、结构要求、CTA 词表
#
# 只保留**质检要用得到**的字段。`generic` 是不指定平台时的兜底口径：
# 区间放得很宽，只查"通用发布形态"（分段是否清楚、字数是否合理），
# 免得拿公众号的尺子量小红书稿子，把好稿子误判成不及格。
#
# 目标字数取区间中位偏下：lo + TARGET_POS × (hi - lo)。
# 为什么不给上限：实测模型会贴着你给的数字写，给上限就一定顶到上限（然后超）。
# ---------------------------------------------------------------------------

TARGET_POS = 0.35

PLATFORMS = {
    "generic": {
        "name": "通用（不限平台）",
        "chars": (200, 8000),
        "para_chars": (1, 600),
        "para_count": (2, 300),
        "cta": None,
        "fit_notes": [
            "分段要清楚：一段讲一件事，不要一坨到底",
            "Markdown 记号（**加粗** / ## 标题）在部分平台会原样显示，发布前确认",
        ],
    },
    "wechat": {
        "name": "公众号",
        "chars": (1200, 2200),
        "para_chars": (80, 220),
        "para_count": (6, 12),
        "cta": r"关注|留言|评论|在看|转发|分享|点赞",
        "fit_notes": [
            "段落之间要有递进，不能是并列要点清单",
            "结尾要有可执行的互动引导（关注 / 留言 / 在看这类动作词）",
        ],
    },
    "xiaohongshu": {
        "name": "小红书",
        "chars": (350, 800),
        "para_chars": (10, 60),
        "para_count": (4, 10),
        "cta": r"收藏|评论|点赞|关注|告诉我|教教我|聊聊|说说|还有别的",
        "fit_notes": [
            "每段不超过 3 行，短句为主",
            "口语化，不用书面连接词（因此 / 综上 / 首先其次最后）",
            "正文里不许出现站外联系方式（微信号 / 手机号 / 私信我）",
        ],
    },
    "douyin": {
        "name": "抖音",
        "chars": (300, 600),
        "para_chars": (8, 40),
        "para_count": (6, 14),
        "cta": r"关注|点赞|评论|扣\s*1|私信|转发",
        "fit_notes": [
            "一句一行，每行一口气能念完",
            "不出现括号注释、emoji、Markdown 记号（这是要念出来的稿子）",
        ],
    },
    "zhihu": {
        "name": "知乎",
        "chars": (800, 1500),
        "para_chars": (60, 260),
        "para_count": (5, 12),
        "cta": r"赞同|评论|补充|反例|怎么看|欢迎|说说",
        "fit_notes": [
            "要有依据与边界条件，不能只给结论",
            "不出现「我是专家」「官方认证」这类无依据的权威自称",
        ],
    },
    "toutiao": {
        "name": "头条",
        "chars": (600, 1200),
        "para_chars": (30, 120),
        "para_count": (5, 12),
        "cta": r"评论|说说|怎么看|你身边|卡在哪|聊聊|讨论|留言|你们",
        "fit_notes": [
            "每段只讲一件事，段落短、信息密度高",
            "标题许诺的内容正文必须真的给到（不许标题党）",
        ],
    },
}
PLATFORM_CHOICES = list(PLATFORMS.keys())
DEFAULT_PLATFORM = "generic"


def platform_name(platform):
    return PLATFORMS.get(platform, PLATFORMS[DEFAULT_PLATFORM])["name"]


def target_chars(platform):
    """该平台的目标字数（提示词用这个数，不是上限）。"""
    lo, hi = PLATFORMS[platform]["chars"]
    return int(round(lo + (hi - lo) * TARGET_POS))


# ---------------------------------------------------------------------------
# 闸门一：合规（广告法违禁词）
#
# 每项：正则 → 风险等级 → 人话解释。这是一道**粗筛**，宁可多报也别漏报，
# 最终判断仍要人工复核，且不等于平台官方审核结论。
# ---------------------------------------------------------------------------

# 「第一」的可枚举上下文豁免（本包新增，理由见 reports 与 SKILL.md「主动偏离」）：
# 长文里「第一年」「第一步」「第一件事」是**序数**，不是最高级宣称。
# 同族原来那条 `第一(名|品牌|选择|名)?(?!次)` 只排除了「第一次」，
# 实测第一篇真实稿就被误判（「第一年上了 3 部剧」）。
# 一刀切拦下的后果很实在：用户会把整个合规闸门关掉，那比漏报更糟。
# 所以改成枚举「序数后接词」——后接这些字的就是序数，不拦；其余（第一名 / 第一品牌 /
# 「销量第一。」）照拦。豁免项会记进 exempted，**不静默放过**。
FIRST_ORDINAL_AFTER = (
    "次|年|天|步|个|条|款|批|周|月|季|轮|种|点|部|遍|章|节|课|集|届|期|流|层|类"
    "|句|段|行|件|桶|手|版|稿|封|笔|单|场|局|盘|组|队|线|环|圈|代|世|阶|时|印|梯"
)
BANNED_PATTERNS = [
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎)", "高",
     "广告法第九条禁止「最高级」用语"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    (r"第一(?!" + FIRST_ORDINAL_AFTER + r")", "高",
     "「第一」类排他性表述"),
    (r"排名第一|销量第一|口碑第一|行业第一|全国第一|全网第一|全球第一|世界第一", "高",
     "「第一」类排他性表述"),
    (r"No\.?\s*1|TOP\s*1|top\s*1", "高",
     "「第一」类排他性表述"),
    (r"国家级|世界级|全球级|国际级", "高",
     "「国家级」等权威性词汇属明令禁止"),
    (r"100\s*%|百分之百|百分百", "高",
     "绝对化效果承诺"),
    (r"绝对(有效|安全|放心|不会|能|可以)|保证(有效|成功|瘦|赚)|无效退款", "高",
     "绝对化保证与效果担保"),
    (r"根治|治愈|痊愈|药到病除|包治|治疗(好|效果)|疗效|无副作用|零副作用", "高",
     "医疗功效宣称，非药品/医疗器械不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报", "高",
     "投资类收益承诺"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐", "高",
     "不得虚构权威背书"),
    (r"催情|壮阳|丰胸|减肥(药|神器)|美白针|生发(神器)", "高",
     "特殊功效与特殊品类敏感词"),
    (r"免费领|免费送|0\s*元购|白送", "中",
     "可能构成虚假优惠或诱导分享"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天", "中",
     "促销时限表述需与实际活动一致"),
    (r"独家|唯一|首个|首创|填补空白|领先(品牌|技术)", "中",
     "排他性表述需有可举证依据"),
    (r"纯天然|无添加|零添加|无毒无害", "中",
     "成分宣称需与检测报告一致"),
    (r"点击链接|加微信|私信我|扫码(加|进)|vx|VX|微信号", "中",
     "站外导流，平台普遍限制"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看", "中",
     "标题党式诱导"),
    (r"[！!]{2,}|[?？]{3,}", "低",
     "标点堆砌，易被判标题党/低质"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}
# 合规分压制：命中高/中/低风险时，合规维度的最高分（大模型给几分都压到这以下）
COMPLIANCE_CAP = {"高": 1, "中": 4, "低": 7}

# 「最X」的可枚举上下文豁免表。
# 事故复盘（同族，长文场景踩出来的）：`最大区别` / `最主要的是` 这类是**普通中文用法**，
# 不是最高级商品宣称。一刀切拦下会把正常稿子整篇判死，用户就会干脆关掉闸门 —— 那更糟。
# 所以开了豁免口子，但同时加一条**句首不豁免**：句首的「最大区别是…」是标题式宣称，照拦。
SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥", "低", "高", "多", "少", "大", "小", "早", "晚",
)
SUPERLATIVE_OK_RE = re.compile(r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")
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

    同一处文字可能在文中出现多次（一次是广告语、一次是普通用法），
    所以判定按**每一处出现**做，任一处未被豁免就算命中。
    被豁免的疑似命中会记进 `exempted`，**不静默放过**。
    """
    hits, exempted, seen = [], [], set()
    t = text or ""
    for rx, lvl, why in BANNED_RE:
        for m in rx.finditer(t):
            if _superlative_is_normal_usage(t, m):
                exempted.append({"word": m.group(0), "level": lvl,
                                 "context": t[max(0, m.start() - 12):m.end() + 12]})
                continue
            word = m.group(0)
            key = (word, lvl)
            if key in seen:
                continue
            seen.add(key)
            hits.append({"word": word, "level": lvl, "why": why,
                         "context": t[max(0, m.start() - 12):m.end() + 12]})
            break
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits, exempted


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
#
# 长文是大模型一次吐几千字，模板没替换干净的形态比标题场景多得多：
#   · `{}` / `{{标题}}`       骨架被当正文写进去了
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
    (re.compile(r"[\[【（(]\s*(待填|填空|待补充|待完善|待定)\s*[\]】）)]"), "[]",
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
# 闸门三：照抄提示词示例（prompt_echo）
#
# 事故复盘（同族，两例，都是实测抓到的「模型锚定示例」）：
#   1. 提示词里写过正例 → 模型直接产出同构句
#   2. 提示词里留过一整句示例 → 公众号那一轮**最高分**的标题一字不差就是它
# 第 2 例性质更重：最高分那条是"抄了标准答案"，不是"真的最好"。
#
# 本包是长文场景，所以判定分两层（这条是写完闸门后自测发现的漏洞）：
# 正文有 1000+ 字，把整段拿去和示例算 Jaccard，分母被撑到 1000 多，相似度永远接近 0 ——
# 模型把示例原样抄进某一段，这道闸门完全看不见。所以必须**逐句**比。
#
# 三条命中判据（任一即命中）：
#   exact    去掉标点后完全相同
#   jaccard  字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
#   contain  示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（示例被夹带进更长的句子里）
#
# 【为什么必须有第三条】Jaccard 的分母是两份二元组的**并集**，产出越长，
# 示例那一侧被摊薄得越狠 —— 示例原样嵌进去也会掉到 0.75 以下侥幸放行。
# 覆盖度只看"示例被抄了多少"，不看产出有多长，摊薄对它无效。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75          # 同族实测标定：196 条正常产出与跨主题示例最高只 0.174
ECHO_CONTAIN = 0.60      # 同族实测：真实历史产出里覆盖度最大 0.500，余量 1.2 倍、误伤 0
ECHO_MIN_LEN_FLOOR = 6   # 长度守卫的绝对下限，防极短串的二元组噪声

# 提示词里出现过的**跨主题**示例（正常不该被抄）。新增示例必须登记到这里。
# 跨主题 = 与任何真实选题都不搭（电动车充电桩），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住。
PROMPT_SAMPLES = [
    "电动车充电桩到底值不值得装，三个理由",
    "小区充电桩的安装条件别只看价格",
]


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。

    **相对阈值**，不是绝对值。绝对阈值（比如 12）在示例只有 15~17 字时
    占了示例长度的七成以上，会把「≤11 字的截断照抄」整档放过。
    """
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_anchor(sample)) // 2)


def _norm_anchor(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的文本往往只改标点（`，`↔`、`↔空格），所以必须先抹平标点再看。
    """
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _bigrams(s):
    s = _norm_anchor(s)
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
    """文本是否与提示词里的示例"抄得太近"。

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"，
    没命中时后两项为 (0.0, "", "")。
    """
    target = _norm_anchor(text)
    if not target:
        return False, 0.0, "", ""
    best_score, best_sample, best_rule = 0.0, "", ""
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        if target == _norm_anchor(s):
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


# 拆句：中文句末标点 + 换行。用于**逐句**比对与逐句定位。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def split_sentences(text):
    """把正文拆成句子列表（保序、去空白项）。"""
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def split_paras(text):
    """把正文拆成段落列表。段落 = 一个或连续多个非空行。"""
    paras, cur = [], []
    for line in (text or "").splitlines():
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append("\n".join(cur))
            cur = []
    if cur:
        paras.append("\n".join(cur))
    return paras


def prompt_echo_scan(text, samples=None, label="原稿"):
    """在长文本里逐句找「照抄提示词示例」的地方，返回命中列表（可能为空）。

    两层：整段先比一次（只认 exact / jaccard，兜整篇照抄的极端情况），
    再**逐句**比一次（含覆盖度判据，兜「某一句是抄的」这个真实形态）。
    """
    hits = []
    whole_hit, score, sample, rule = prompt_echo(text, samples)
    if whole_hit and rule != "contain":
        hits.append({"segment": (text or "")[:40], "rule": rule, "sim": round(score, 3),
                     "sample": sample,
                     "why": ("与提示词示例去掉标点后完全相同（照抄示例）" if rule == "exact"
                             else "与提示词示例相似度 {:.2f}，属同构照抄".format(score))})
        return hits
    for seg in split_sentences(text):
        hit, score, sample, rule = prompt_echo(seg, samples)
        if not hit:
            continue
        if rule == "contain":
            why = ("{}里的「{}」有 {:.0f}% 的内容来自提示词示例「{}」"
                   "（覆盖度 ≥ {:.2f} 即判照抄；Jaccard 会随句子变长被摊薄）"
                   .format(label, seg[:20], score * 100, sample[:24], ECHO_CONTAIN))
        elif rule == "exact":
            why = "{}里的「{}」与提示词示例去掉标点后完全相同（照抄示例）".format(label, seg[:20])
        else:
            why = "{}里的「{}」与提示词示例相似度 {:.2f}，属同构照抄".format(label, seg[:20], score)
        hits.append({"segment": seg[:40], "rule": rule, "sim": round(score, 3),
                     "sample": sample, "why": why})
        break                      # 一处命中足够拦截，不用把整篇列完
    return hits


# ---------------------------------------------------------------------------
# 闸门四：改动不许丢事实（数字 / 专有名词）
#
# 这是"AI 改稿"最隐蔽的一种损失：语句更顺了、评分更高了，但**原稿里的一个数字没了**。
# 人眼几乎发现不了（尤其改的是几千字的长文），但业务上它可能是致命的
# （报价、参数、结论数字被改掉）。
#
# 本地把原稿里的事实抽成清单，两件事都用它：
#   1. 喂给改写提示词，要求逐条保留（这是"修复"，不只是"拦下"）
#   2. 改完之后逐条核对定稿里还在不在（这是"闸门"）
#
# 【诚实说明这是启发式】数字这一条是确定性的；专有名词靠四类模式（书名号、引号、
# 英文词、机构后缀）抓，抓不全，也可能多报。所以：多报会拦下正常产出 → 提供
# `--facts-warn-only` 降级为提示（记录在案，不动退出码）。
# ---------------------------------------------------------------------------

NUM_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")
FACT_PROPER_PATTERNS = [
    (re.compile(r"《([^》\n]{2,24})》"), "书名/作品名"),
    (re.compile(r"[「“]([^」”\n]{2,20})[」”]"), "引号内短语"),
    (re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9.+#\-]{1,19})(?![A-Za-z0-9])"), "英文专名"),
    # 机构后缀这一条**实测踩过坑**：原来的枚举表里有「平台 / 系统 / 模型 / 算法」，
    # 第一次真机跑就把「我们也试过让模型」「原因不在模型」整段抓成了专名 ——
    # 这四个词在中文技术写作里太通用，后面跟什么都能组成"XX模型"。
    # 假事实的危害不只是多一条：改稿把「模型」换成「大模型」就会被判成"丢了专名"，
    # 台账一多报，人就不看台账了。所以只留真正指向具体实体的后缀。
    (re.compile(r"([\u4e00-\u9fff]{2,8}(?:公司|集团|大学|学院|研究院|实验室"
                r"|基金|银行|医院|工作室|协会|出版社|电视台))"), "机构/产品名"),
]
# 纯排版词，不算事实（否则改稿把 "OK" 删了也算丢事实，噪声太大）。
PROPER_STOP = {"ok", "vs", "etc", "eg", "ie", "nb"}

_CN_DIGIT = "零一二三四五六七八九"
_CN_UNIT = ("", "十", "百", "千")
_CN_BIG = ("", "万", "亿")


def int_to_cn(n):
    """非负整数 → 中文写法（0~99999999）。只为判断"数字是不是只换了写法"。"""
    n = int(n)
    if n < 0:
        return ""
    if n == 0:
        return "零"
    groups = []
    while n > 0:
        groups.append(n % 10000)
        n //= 10000
    out = []
    for gi in range(len(groups) - 1, -1, -1):
        g = groups[gi]
        if g == 0:
            if out and not out[-1].endswith("零"):
                out.append("零")
            continue
        seg, zero = [], False
        for pos in range(3, -1, -1):
            d = (g // (10 ** pos)) % 10
            if d == 0:
                zero = True
                continue
            if zero and seg:
                seg.append("零")
            zero = False
            seg.append(_CN_DIGIT[d] + _CN_UNIT[pos])
        s = "".join(seg)
        if s.startswith("一十"):
            s = s[1:]
        out.append(s + _CN_BIG[gi])
    return "".join(out).rstrip("零") or "零"


def _norm_num(raw):
    """数字归一：`87.0` → `87`，`007` → `7`，其余保留。"""
    s = (raw or "").strip()
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if f == int(f) else s


def _to_halfwidth(s):
    """全角数字/百分号/点 → 半角。模型很爱把数字换成全角。"""
    out = []
    for ch in s or "":
        o = ord(ch)
        if o == 0x3000:
            out.append(" ")
        elif 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def _norm_text(s):
    """文本归一（用于事实核对）：全角转半角 + 去掉所有空白。"""
    return re.sub(r"\s+", "", _to_halfwidth(s or ""))


def _is_list_marker(text, m):
    """这一处数字是不是行首的列表序号（`1.` / `2、` / `3)`）？

    列表序号不是事实：删掉或重排列表不该被判成丢事实。
    """
    if m.end() >= len(text) or text[m.end()] not in ".、)）":
        return False
    before = text[:m.start()]
    # 注意这里是 `before` 而不是 `before.rstrip()`：把换行 strip 掉之后
    # 「\n1.」就判不出来了（实测踩过，列表序号被当成事实，台账多报一堆"丢了数字"）。
    return (not before.strip()) or re.search(r"(^|\n)[ \t]*$", before) is not None


def _inside_latin_token(text, m):
    """数字是不是夹在拉丁字母 token 里（`A7W` 的 7、`H264` 的 264）？

    实测踩到过：`A7W 商城` 被抽出一个"事实 `7`"，改稿把 A7W 换成"某商城"之后
    台账会多报一条"丢了数字 7"——**假警报会让人不信任整张表**。
    这类数字由「英文专名」那条模式整块负责，这里跳过。
    """
    t = text or ""
    before = t[m.start() - 1] if m.start() > 0 else ""
    after = t[m.end()] if m.end() < len(t) else ""
    return before.isalpha() and before.isascii() or after.isalpha() and after.isascii()


def _ctx(text, start, end, pad=16):
    return (text or "")[max(0, start - pad):end + pad].replace("\n", " ")


def extract_facts(text):
    """抽出稿件里的事实清单（数字 + 启发式专有名词），去重保序。"""
    t = text or ""
    facts, seen = [], set()
    for m in NUM_TOKEN_RE.finditer(t):
        if _is_list_marker(t, m) or _inside_latin_token(t, m):
            continue
        raw = m.group(0)
        f = {"kind": "num", "raw": raw, "norm": _norm_num(raw),
             "context": _ctx(t, m.start(), m.end())}
        key = ("num", f["norm"])
        if key in seen:
            continue
        seen.add(key)
        facts.append(f)
    for rx, label in FACT_PROPER_PATTERNS:
        for m in rx.finditer(t):
            raw = (m.group(1) or "").strip()
            if raw.lower() in PROPER_STOP:
                continue
            norm = _norm_anchor(raw)
            if len(norm) < 2:
                continue
            key = ("proper", norm.lower())
            if key in seen:
                continue
            seen.add(key)
            facts.append({"kind": "proper", "label": label, "raw": raw, "norm": norm,
                          "context": _ctx(t, m.start(), m.end())})
    return facts


def _num_present(norm_final, n):
    """定稿里有没有这个数（按数字边界匹配，避免 87 被 1870 蒙混过关）。"""
    return re.search(r"(?<!\d)" + re.escape(n) + r"(?!\d)", norm_final) is not None


def fact_loss_report(orig_text, final_text, warn_only=False):
    """逐条核对原稿事实在定稿里还在不在。

    返回 {"total","kept","lost","renumbered","kept_rate","ok","warn_only","facts"}
      kept        —— 仍在定稿里的
      renumbered  —— 数字换了写法（`3` → `三`）仍在，**不算丢**
      lost        —— 找不到的，会被列出（含原稿里的上下文，好让人判断）
    """
    facts = extract_facts(orig_text)
    norm_final = _norm_text(final_text)
    norm_cjk = _norm_anchor(final_text)
    kept, lost, renumbered = [], [], []
    for f in facts:
        if f["kind"] == "num":
            if _num_present(norm_final, f["norm"]):
                kept.append(f)
                continue
            if "." not in f["norm"]:
                cn = int_to_cn(int(f["norm"]))
                if cn and cn not in ("零",) and cn in norm_cjk:
                    r = dict(f)
                    r["as"] = cn
                    renumbered.append(r)
                    kept.append(r)
                    continue
        else:
            if f["norm"].lower() in norm_final.lower():
                kept.append(f)
                continue
        lost.append(f)
    return {
        "total": len(facts),
        "kept": len(kept),
        "lost": lost,
        "renumbered": renumbered,
        "kept_rate": round(len(kept) / float(len(facts)), 3) if facts else 1.0,
        "ok": (not lost) or bool(warn_only),
        "warn_only": bool(warn_only),
        "facts": facts,
    }


# ---------------------------------------------------------------------------
# 闸门五：定位锚点校验（本包的核心机制，也是"逐句定位"能不能成立的判据）
#
# 只是"在提示词里写一句请定位到句子"，模型经常给你泛泛而谈
# （「建议加强逻辑衔接」「整体信息量可以更足」）—— 这种建议**没法执行**：
# 改哪个句子？改成什么？审稿的人拿到它只能重写一遍。
#
# 所以本包不采信模型的引文，而是**本地校验**：它引的那句话在不在原稿里？
# 三步递进：
#   exact      归一化后与某一整句完全相同
#   substring  归一化后是某一整句的一部分（模型只引了半句，最常见）
#   contained  某一整句是引文的一部分（模型把两句连起来引了）
#   fuzzy      与最像的那一句 Jaccard ≥ ANCHOR_SIM 且引文够长（轻改写式引用）
#   unverified 以上都不成立 → **判为锚点幻觉**，不进改写输入，并计入未锚定率
#
# 未锚定率超过 ANCHOR_MAX_MISS → 判「定位失败」，压分 + 标红 + stderr 汇总 + 退出码 3。
# 另外：总分没到目标线却一条可用建议都没有 → 也判失败（闭环跑不下去，不能假装能跑）。
# ---------------------------------------------------------------------------

ANCHOR_MIN_SUBSTR = 4     # 精确子串匹配的最低长度（低风险判据，门槛可以矮）
ANCHOR_MIN_CHARS = 8      # 模糊匹配的最低长度（二元组太少会虚高，门槛必须高）
ANCHOR_SIM = 0.55         # 模糊匹配阈值；标定数据见 references/质检维度与评分口径.md
ANCHOR_MAX_MISS = 0.40    # 未锚定率超过它就判「定位失败」

# 为什么两种匹配用**两个不同的长度门槛**（相对阈值的思路，与 prompt_echo 的长度守卫同源）：
# 「引文恰好是某句的连续片段」是**精确**判断（去标点后逐字命中），短一点也几乎不会误伤；
# 而「最像的那一句」是**统计**判断，短串的字符二元组集合太小，相似度会虚高，
# 所以必须卡长度。一个门槛管两件事，就会出现"6 个字的真实引文被判成幻觉"
# 这种把真问题算成假问题的情况 —— 它会直接污染未锚定率。


def verify_anchor(quote, sentences, norms=None):
    """把模型的引文锚定到原稿的某一句话上。

    返回 (ok, rule, index)；index 是句序号（0 基），未锚定时为 -1。
    """
    q = _norm_anchor(quote)
    if not q:
        return False, "unverified", -1
    if norms is None:
        norms = [_norm_anchor(s) for s in sentences]
    # 1) 完全相同
    for i, n in enumerate(norms):
        if n and n == q:
            return True, "exact", i
    # 2) 引文是某句的一部分 / 3) 某句是引文的一部分（精确子串，低门槛）
    if len(q) >= ANCHOR_MIN_SUBSTR:
        for i, n in enumerate(norms):
            if n and (q in n or n in q) and min(len(q), len(n)) >= ANCHOR_MIN_SUBSTR:
                return True, "substring", i
    # 4) 模糊：找最像的一句（统计判据，高门槛）
    best_i, best = -1, 0.0
    if len(q) >= ANCHOR_MIN_CHARS:
        for i, s in enumerate(sentences):
            sim = _similarity(quote, s)
            if sim > best:
                best_i, best = i, sim
        if best >= ANCHOR_SIM:
            return True, "fuzzy", best_i
    return False, "unverified", -1


def anchor_issues(issues, text):
    """给每条问题做锚点校验，返回 (锚定成功的, 未锚定的)。

    锚定成功的那条会把 `quote` **就地修正成原稿里的真实句子**（`sentence` 字段）——
    模型引半句、连引两句都对不上时，台账里要显示的是原稿原文，不是模型的转述。
    """
    sents = split_sentences(text)
    norms = [_norm_anchor(s) for s in sents]
    ok_list, bad_list = [], []
    for it in issues:
        quote = (it.get("quote") or "").strip()
        good, rule, idx = verify_anchor(quote, sents, norms)
        item = dict(it)
        item["quote"] = quote
        item["anchor_rule"] = rule
        if good:
            item["sentence"] = sents[idx]
            item["sent_no"] = idx + 1
            ok_list.append(item)
        else:
            item["why_unverified"] = ("引文在原稿里找不到（归一化后也不匹配任一整句，"
                                      "模糊相似度 < {:.2f}）——判为锚点幻觉，不进改写输入"
                                      .format(ANCHOR_SIM))
            bad_list.append(item)
    return ok_list, bad_list


# ---------------------------------------------------------------------------
# 闸门六：收敛判定
#
# `all` 必须在轮次内收敛，或**明确报「未收敛」**。不得假装收敛 ——
# 具体做法：复评分数用的不是"每轮新调一次分"，而是**同一次调用里匿名双评**
# （原稿与新稿一起、乱序、只给编号），这样"涨了多少"不受两次调用之间的评分漂移影响。
# 即便如此，模型的自评分仍然可能虚高，所以：
#   · 分数轨迹全程记录，涨幅一并展示，**不四舍五入成一个结论**
#   · 还有 diff 的逐句台账作旁证：改了多少句、其中多少只是换词
# ---------------------------------------------------------------------------

CONVERGE_NOTE = ("复评分数来自同一次调用里的匿名双评（原稿与新稿乱序、只给编号），"
                 "目的：让涨幅不受两次调用之间的评分漂移影响。"
                 "但模型自评仍可能偏高，所以本包同时给逐句台账作旁证。")


# ---------------------------------------------------------------------------
# 提示词
#
# 【铁律】提示词里**不许出现任何一条可直接复制的完整中文范文句**。
# 事故复盘（同族，实测抓到两例）：提示词里写过正例，模型直接产出同构句；
# 尤其严重的一例，全批最高分的那条一字不差就是提示词里的示例 ——
# "抄了标准答案"被当成"真的最好"，排序/评分就废了。
#
# 所以：讲形态只用**描述性语言**；确实需要举例时用**跨主题示例**（登记进
# PROMPT_SAMPLES，由 prompt_echo 闸门兜底）。
# ---------------------------------------------------------------------------

CHAT_RETRY_NOTE = "上游 5xx 与网络抖动退避重试；4xx 直接报错，不浪费额度。"

SYSTEM_PROMPT = (
    "你是一位严格的内容质检编辑，替团队做**发布前审稿**。\n"
    "你的职责不是鼓励作者，而是**找出具体到句子的问题**，并给出可以直接执行的改法。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 每条问题必须**原样引用**稿件里真实存在的一句话（或句中连续的一小段），"
    "不得改写、不得概括、不得凭空编造引文。引不出来的问题一律不要写。\n"
    "  2. 不许写「整体不错」「建议加强逻辑」这类无法执行的泛泛之谈。"
    "每条问题的 `fix` 必须是**改写后的具体句子**，不是方向。\n"
    "  3. 不许编造稿件里没有的数据、案例、机构名、人名。\n"
    "  4. 评分只依据你看到的文本，不依据题材好坏、不依据作者是谁。\n"
    "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。"
)

# 评分口径（维度定义 + 分档锚点）。这份文字同时写进 references/ 文档，口径只有一处。
RUBRIC_TEXT = (
    "五个维度各打 1~10 分（整数），分档锚点如下：\n"
    "  · 信息密度：单位字数里有多少**可验证的具体信息**（数字、条件、步骤、边界）。"
    "9~10 = 几乎每段都有硬信息；5~6 = 有观点但缺依据；1~4 = 只有形容词与重复的口号。\n"
    "  · 结构：能否一眼看出「开头给处境 → 中间拆解 → 结尾给结论/行动」的推进关系。"
    "9~10 = 层级清楚、段间有递进；5~6 = 平铺直叙但能读下去；1~4 = 顺序混乱或首尾不接。\n"
    "  · 可读性：句子长度、指代是否明确、有没有读两遍才懂的句子、有没有术语没解释。"
    "9~10 = 一遍读懂；5~6 = 偶有拗口长句；1~4 = 多处需要回读。\n"
    "  · 合规：有无绝对化用语、无法举证的承诺、站外导流、医疗/投资类敏感宣称。"
    "9~10 = 干净；5~6 = 有边缘表述需人工确认；1~4 = 明确踩线。\n"
    "  · 平台适配：字数、分段、语气、结尾引导是否符合目标平台的分发习惯。"
    "9~10 = 与目标平台高度匹配；5~6 = 需要调整分段与语气；1~4 = 明显不是这个平台该有的形态。"
)

# 跨主题示例：只用来讲"什么样的问题算无法执行"，不是范文。
# 跨主题 = 与任何真实选题都不搭（电动车充电桩），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
_PROMPT_SAMPLE_BLOCK = (
    "跨主题示例（**仅供理解「什么算无法执行」，禁止把示例原句写进任何字段**）：\n"
    "  · 反面（无法执行）：把「{}」这类**没有出处的判断**当成建议，只说要更好，不说改哪句。\n"
    "  · 正面（可执行）：引出一句原文，说明它缺什么，再给出改写后的那句话。\n"
).format(PROMPT_SAMPLES[0])


def platform_context_block(platform):
    """平台口径参考块。**单篇打分与匿名双评必须用同一份**。

    事故复盘（第一次真机跑出来的，不是理论问题）：双评提示词一开始漏了这一段，
    结果同一篇原稿在单篇打分里是 81.5 分，在同轮双评里只有 72.5 分 ——
    差了 9 分，几乎全是"这次调用没给它字数口径"造成的。
    两个模式的分不在同一把尺子上，轨迹就没有可比性，整包的核心产出（评分涨幅）直接失真。
    所以这一段抽成一个函数，两边共用，改一处就两边都改。
    """
    pf = PLATFORMS[platform]
    lo, hi = pf["chars"]
    return (
        "平台口径参考（本地闸门也会按它校验，但你要独立判断）：\n"
        "  · 目标平台：{name}；字数区间 {lo}~{hi} 字符，目标约 {t} 字符\n".format(
            name=pf["name"], lo=lo, hi=hi, t=target_chars(platform))
        + "".join("  · {}\n".format(x) for x in pf["fit_notes"])
    )


def build_score_prompt(text, platform, doc_id=None):
    """单篇打分的提示词。"""
    head = "对下面这份稿件做发布前质检。\n"
    if doc_id:
        head = "这是编号 {} 的稿件。对下面这份稿件做发布前质检。\n".format(doc_id)
    return (
        head
        + "\n"
        + RUBRIC_TEXT
        + "\n\n"
        + _PROMPT_SAMPLE_BLOCK
        + "\n"
        + platform_context_block(platform)
        + "  · 当前稿件 {n} 字符\n".format(n=len(text or ""))
        + "\n按要求只输出这个 JSON 对象：\n"
        + json.dumps({
            "dims": {k: 0 for k in DIM_KEYS},
            "dim_notes": {k: "这个分数的一句话依据" for k in DIM_KEYS},
            "issues": [{
                "quote": "原稿里**原样**的一句话（或句中连续一小段）",
                "dims": ["info_density"],
                "severity": "高|中|低",
                "why": "这句话为什么是问题",
                "fix": "改写后的具体句子",
            }],
            "summary": "两三句总评",
        }, ensure_ascii=False, indent=1)
        + "\n补充要求：issues 最多 12 条，按 severity 从高到低。"
          "任何一个维度你给了 8 分以下，就必须至少有一条问题落在那个维度上。"
          "如果整篇确实挑不出问题，issues 给空数组。\n"
        + "\n===== 稿件全文开始 =====\n" + (text or "") + "\n===== 稿件全文结束 =====\n"
    )


def build_pair_prompt(orig, cand, platform, orig_first=True):
    """同一次调用里**匿名双评**原稿与新稿（乱序、只给编号）。

    为什么这么做：如果"第 1 轮 74 分、第 2 轮 81 分"来自两次独立调用，
    那 7 分的涨幅里有多少是稿子真的变好了、有多少只是两次调用之间的评分漂移，
    谁也说不清。放进同一次调用，两篇共享同一套上下文与同一把尺子，
    涨幅才勉强能当证据用。

    **诚实说明边界**：同一调用里模型仍可能认得出哪篇是"改过的"从而给高分
    （自我偏好偏差），匿名与乱序只能削弱、不能消除。所以台账会同时给出
    逐句改动统计，让人能独立判断"是真改好了还是只换了说法"。
    """
    docs = [(("1", orig), ("2", cand)) if orig_first else (("1", cand), ("2", orig))]
    d1, d2 = docs[0]
    return (
        "下面有**两份**稿件，是同一主题的两个版本，编号 {} 与 {}。\n".format(d1[0], d2[0])
        + "请**独立**给每一份做发布前质检：独立打分、独立列问题。\n"
        + "不要比较两份谁更好，不要猜测哪一份是改过的，不要因为编号顺序影响你的评分。\n"
        + "\n"
        + RUBRIC_TEXT
        + "\n\n" + _PROMPT_SAMPLE_BLOCK
        + "\n" + platform_context_block(platform)
        + "  · 当前两份稿件分别 {n1} 字符 / {n2} 字符\n".format(
            n1=len(d1[1] or ""), n2=len(d2[1] or ""))
        + "\n按要求只输出这个 JSON 对象：\n"
        + json.dumps({
            "docs": [{
                "id": "1",
                "dims": {k: 0 for k in DIM_KEYS},
                "dim_notes": {k: "这个分数的一句话依据" for k in DIM_KEYS},
                "issues": [{
                    "quote": "该稿件里**原样**的一句话（或句中连续一小段）",
                    "dims": ["structure"],
                    "severity": "高|中|低",
                    "why": "这句话为什么是问题",
                    "fix": "改写后的具体句子",
                }],
                "summary": "两三句总评",
            }, {
                "id": "2",
                "dims": {k: 0 for k in DIM_KEYS},
                "dim_notes": {k: "这个分数的一句话依据" for k in DIM_KEYS},
                "issues": [],
                "summary": "两三句总评",
            }],
        }, ensure_ascii=False, indent=1)
        + "\n补充要求：每份的 issues 最多 12 条，按 severity 从高到低。"
          "维度低于 8 分就必须有对应问题。id 必须原样回填 \"{}\" 与 \"{}\"。\n".format(
              d1[0], d2[0])
        + "\n===== 编号 {} 的稿件开始 =====\n{}\n===== 编号 {} 的稿件结束 =====\n".format(
            d1[0], d1[1], d1[0])
        + "\n===== 编号 {} 的稿件开始 =====\n{}\n===== 编号 {} 的稿件结束 =====\n".format(
            d2[0], d2[1], d2[0])
    )


def build_revise_prompt(text, platform, issues, facts, length_note=None):
    """按已定位的问题清单重写。

    改写输入里带上三样东西：全文、**锚定过的**问题清单（只给能定位到句子的那些）、
    本地抽出的事实清单。第三样是关键：它把"丢事实"从"改完再拦下"变成"事前就要求保留"。
    """
    pf = PLATFORMS[platform]
    lo, hi = pf["chars"]
    lines = []
    for i, it in enumerate(issues, 1):
        lines.append("  {}. [{}] 原句：{}\n     问题：{}\n     建议改法：{}".format(
            i, "/".join(DIM_LABEL.get(d, d) for d in it.get("dims") or ["-"]),
            it.get("sentence") or it.get("quote") or "",
            it.get("why") or "-", it.get("fix") or "-"))
    issue_block = "\n".join(lines) if lines else "  （本地未定位到问题，请只做保守的通顺化，不要改结构）"
    fact_lines = []
    for f in facts:
        if f["kind"] == "num":
            fact_lines.append("  · 数字 {}（原句：{}）".format(f["raw"], f["context"]))
        else:
            fact_lines.append("  · {}「{}」（原句：{}）".format(
                f.get("label") or "专名", f["raw"], f["context"]))
    fact_block = "\n".join(fact_lines) if fact_lines else "  （本地未抽出事实条目）"
    return (
        "下面是**别人已经写完的一篇成稿**，请按质检清单做一轮修改。\n"
        "目标平台：{}（字数区间 {}~{}，目标约 {} 字符）。\n".format(
            pf["name"], lo, hi, target_chars(platform))
        + (length_note + "\n" if length_note else "")
        + "\n修改纪律（违反就整份作废）：\n"
          "  1. **只改清单点到的地方**。清单没点到的句子，除非它跟改动直接相邻，否则一个字都别动。\n"
          "  2. **事实清单里的每一项都必须原样保留在定稿里**（数字、单位、专有名词一个都不能少、"
          "不能改口、不能换算法）。事实清单之外，不许新增任何数字、案例、机构名、人名。\n"
          "  3. 不许改变题材、不许换平台形态、不许重排整体结构骨架。\n"
          "  4. 不许把清单里的编号、字段名、本提示词的词句写进正文；"
          "不许输出 Markdown 代码围栏，不许输出 `{}` 这类占位符。\n"
          "  5. 正文里不许出现绝对化用语（最高级、「第一」、100%、国家级这类）。\n"
          "  6. 如果某条 fix 会让句子明显变长，**先拆成两句**，不要把三层意思塞进一句。"
          "中文单句尽量控制在 60 字以内。（真机实测踩过：第一轮改写照着 fix 把句子拉长，"
          "可读性分从 9 掉到 7 —— 质量问题修好了，阅读体验反而变差，这不叫改好了。）\n"
          "\n===== 质检清单（本地已逐条锚定到原稿句子）=====\n" + issue_block
        + "\n\n===== 必须保留的事实清单（本地抽取，数字为确定性检查）=====\n" + fact_block
        + "\n\n按要求只输出这个 JSON 对象：\n"
        + json.dumps({
            "final": "修改后的完整正文（只放正文，不要加任何说明、标题、围栏）",
            "changes": [{
                "before": "原稿里被改掉的那句原话",
                "after": "改成了什么",
                "why": "为什么这么改（对应清单第几条）",
                "issue_ids": [1],
            }],
            "kept_facts": ["你确认已原样保留的事实"],
        }, ensure_ascii=False, indent=1)
        + "\n补充要求：changes 覆盖你实际做过的每一处改动，一处一条；"
          "改动很少就少写几条，**不要为了凑数编改动**。\n"
        + "\n===== 原稿开始 =====\n" + (text or "") + "\n===== 原稿结束 =====\n"
    )


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class QcError(a7w.A7wError):
    """质检流程里的所有可预期失败。子类各自带退出码。"""
    exit_code = EXIT_CALL


class UsageError(QcError):
    """参数/配置用错了（文件不存在、平台名错、给了 --budget 没给单价…）。→ 退出码 2

    为什么要跟调用失败分开：这两类错误的**处理方式完全不同**。
    参数错了改命令重跑，不花一分钱；调用失败要查 Key / 点数 / 模型名。
    混成一个退出码，CI 里就没法区分「我命令写错了」和「网关挂了」。
    """
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """产出路径落在 Skill 包内（退出码 2）。"""


class GateFail(QcError):
    """硬闸门命中（退出码 3）。"""
    exit_code = EXIT_GATE


class BudgetStop(QcError):
    """预算超限，已就地中止（退出码 5）。"""
    exit_code = EXIT_BUDGET


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

    ⚠️ 本函数**故意不走** `a7w._request`：那边有个 `raw` 参数，是**原始请求体字节**
    （用于 multipart 上传），**不是**"要原始响应"。同族有人把它当成后者用过，
    结果崩在**钱已经扣之后**。本包一律自己发 urllib 请求，语义只有一种，不给误用的机会。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见，
    一次改写是一篇完整长文，被一次抖动打断要重跑整轮，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。
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
            msg = (err.get("error") or {}).get("message") if isinstance(err.get("error"), dict) else None
            msg = msg or err.get("msg") or text[:200]
            if exc.code == 401:
                raise QcError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise QcError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise QcError("模型不存在（404）：{}  "
                              "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise QcError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise QcError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 网关把 OpenAI 的返回包了一层 {"code":1,"data":{...}}，两种形态都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise QcError("模型没返回 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    finish_reason = (choices[0] or {}).get("finish_reason")
    _LAST_FINISH["reason"] = finish_reason
    _LAST_FINISH["chars"] = len(content)
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    return content, usage


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    为什么要这么写：模型经常在合法 JSON 后面多吐几个字符（```、解释、第二个对象、
    重复的 } ），直接 json.loads 会炸。这里用 json.JSONDecoder().raw_decode()，
    从一个 { 或 [ 开始试解码，成功就返回，失败就往后挪一个字符接着试。
    """
    if not text:
        raise QcError("模型返回空内容")
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
    raise QcError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


# ---------------------------------------------------------------------------
# 成本：token 标定 + 预算闸门
#
# 字符 → token 的标定比例（**是同族实测值**，不是厂商文档）：
# 输入侧拿真实 rewrite --all 的 5 次调用做标定，实测均值 1.612，本包沿用：
CHARS_PER_TOKEN_IN = 1.61
# 输出侧按「1 个原始字符 ≈ 多少 token」算，同族实测均值 1.109（平台间 0.93~1.63，
# 差异几乎全部来自换行数）。这里用均值——这是**估算，不是账单**。
TOKENS_PER_CHAR_OUT = 1.11
# 平台口径：1 元 = 100 点。
POINTS_PER_YUAN = 100.0

# 一次闭环的调用构成（用于 cost 报价）：
#   基线 1 次单篇打分 + 每轮（1 次改写 + 1 次匿名双评）
SCORE_ISSUE_OUT_TOKENS = 700     # 单篇打分的 JSON 输出（含问题清单）经验值
REVISE_OUT_RATIO = 0.95          # 改写输出 ≈ 原稿字数 × 该系数


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(text, platform, rounds):
    """一次闭环的调用清单（用于报价，越清楚越好）。"""
    src_in = estimate_tokens_in(text)
    out_chars = max(len(text or ""), target_chars(platform))
    revise_out = max(1, int(round(out_chars * REVISE_OUT_RATIO * TOKENS_PER_CHAR_OUT)))
    calls = [{"stage": "基线单篇打分", "calls": 1,
              "tokens_in": src_in + 300, "tokens_out": SCORE_ISSUE_OUT_TOKENS,
              "note": "给出五维分与定位到句的问题清单；可用 --baseline 复用已有结果，省掉这一次"}]
    per_in = src_in + 300 + 400        # 原稿 + 清单 + 事实清单
    per_out = revise_out
    calls.append({"stage": "改写（每轮 1 次）", "calls": max(0, rounds),
                  "tokens_in": per_in * max(0, rounds), "tokens_out": per_out * max(0, rounds),
                  "note": "输入含全文 + 锚定过的问题清单 + 事实清单"})
    pair_in = (src_in * 2) + 300
    pair_out = SCORE_ISSUE_OUT_TOKENS * 2
    calls.append({"stage": "匿名双评（每轮 1 次）", "calls": max(0, rounds),
                  "tokens_in": pair_in * max(0, rounds), "tokens_out": pair_out * max(0, rounds),
                  "note": "同一次调用里给原稿与新稿各自打分，用于消除跨调用的评分漂移"})
    return calls


def compute_cost(tokens_in, tokens_out, price_in=None, price_out=None):
    """算钱。单价单位：点 / 百万 token。缺单价时诚实返回 None，不编价。"""
    rec = {
        "tokens_in": int(tokens_in or 0),
        "tokens_out": int(tokens_out or 0),
        "price_in": price_in, "price_out": price_out,
        "unit": "点/百万 token",
        "points": None, "yuan": None, "notes": [],
    }
    if price_in is None or price_out is None:
        rec["notes"].append(
            "没给单价，无法给出金额：文本模型网关不公布单价（models 列表里也没有价格字段）。"
            "用 --price-in / --price-out 指定你账号的单价（点/百万 token）即可算出点数与金额。")
        return rec
    pts = (rec["tokens_in"] / 1e6) * float(price_in) + \
          (rec["tokens_out"] / 1e6) * float(price_out)
    rec["points"] = round(pts, 4)
    rec["yuan"] = round(pts / POINTS_PER_YUAN, 4)
    rec["notes"].append("按你给的单价线性折算；真实扣费以账户流水为准。")
    return rec


def fmt_cost(rec):
    if rec.get("points") is None:
        return "无法估算金额（{}）".format("；".join(rec.get("notes") or []))
    return "{} in + {} out tokens = {:g} 点 = ¥{:g}".format(
        rec["tokens_in"], rec["tokens_out"], rec["points"], rec["yuan"])


class CostTracker:
    """累计真实 usage（token），实时核预算。超了就地停（闸门：成本上限）。"""

    def __init__(self, budget=None, price_in=None, price_out=None):
        self.budget = budget
        self.price_in = price_in
        self.price_out = price_out
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.estimated_flags = 0

    @property
    def has_price(self):
        return self.price_in is not None and self.price_out is not None

    def add(self, usage, label=""):
        """记一次真实 usage；usage 缺失时**如实计数**并标注（不假装精确）。"""
        u = usage or {}
        p, c = u.get("prompt_tokens"), u.get("completion_tokens")
        if not isinstance(p, int) or not isinstance(c, int):
            p, c = 0, 0
            self.estimated_flags += 1
        self.calls += 1
        self.prompt_tokens += p
        self.completion_tokens += c

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    @property
    def points(self):
        if not self.has_price:
            return None
        return ((self.prompt_tokens / 1e6) * float(self.price_in)
                + (self.completion_tokens / 1e6) * float(self.price_out))

    def over_budget(self, extra_in=0, extra_out=0):
        """预算核验。给了单价才可能超（没单价时金额未知 → 只报 token，不假装在预算内）。"""
        if self.budget is None:
            return False
        if not self.has_price:
            return False
        pts = (((self.prompt_tokens + extra_in) / 1e6) * float(self.price_in)
               + ((self.completion_tokens + extra_out) / 1e6) * float(self.price_out))
        return pts > self.budget

    def line(self):
        s = "已用 {} 次文本调用 · token prompt={} completion={} total={}".format(
            self.calls, self.prompt_tokens, self.completion_tokens, self.total_tokens)
        if self.estimated_flags:
            s += "（含 {} 次没有真实 usage 的调用）".format(self.estimated_flags)
        if not self.has_price:
            s += " · 金额：网关不公布文本单价，**未折算**（要折算请传 --price-in / --price-out）"
        else:
            s += " · 估算 {:g} 点 ≈ ¥{:g}（按你填的单价）".format(
                self.points or 0, (self.points or 0) / POINTS_PER_YUAN)
        return s


# ---------------------------------------------------------------------------
# 本地确定性扣分与闸门评估
# ---------------------------------------------------------------------------

def _clamp(v, lo=1, hi=10):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, v))


def char_count(text):
    """正文字符数（**不含空白**）——中英混排时这个数比 len() 更贴近"篇幅"。"""
    return len(re.sub(r"\s+", "", text or ""))


def evaluate_gates(text, platform, issues=None, anchor_stat=None):
    """跑全部**本地**闸门，返回结构化结论。

    硬闸门 = compliance / placeholder / prompt_echo / length / anchor 五项；
    structure 是软提示（**故意不拦**：审的是别人写好的成稿，
    「结尾没有 CTA」这类在不少稿子上是合理选择，当硬闸门会天天误报）。
    """
    hits_c, exempted = compliance_scan(text)
    ph = placeholder_hits(text)
    echo = prompt_echo_scan(text)
    lo, hi = PLATFORMS[platform]["chars"]
    n = char_count(text)
    length_ok = lo <= n <= hi
    g = {
        "compliance": {
            "ok": not hits_c, "hits": hits_c, "exempted": exempted,
            "cap": (COMPLIANCE_CAP.get(hits_c[0]["level"]) if hits_c else None),
        },
        "placeholder": {"ok": not ph, "hits": ph},
        "prompt_echo": {"ok": not echo, "hits": echo},
        "length": {"ok": length_ok, "chars": n, "lo": lo, "hi": hi,
                   "delta": (0 if length_ok else (n - hi if n > hi else n - lo))},
    }
    if anchor_stat is not None:
        g["anchor"] = anchor_stat
    return g


def gate_failed(gates):
    """硬闸门是否命中（structure 不在此列）。"""
    for k in ("compliance", "placeholder", "prompt_echo", "length", "anchor"):
        v = gates.get(k)
        if v and not v.get("ok", True):
            return True
    return False


def apply_local_caps(dims, gates):
    """本地确定性扣分：违禁词压合规分、字数跑出区间压平台适配分。

    返回 (修正后的 dims, 扣分记录)。**关键**：峰值由本地定，模型给多高都压下来。
    """
    dims = dict(dims)
    ded = []
    c = gates.get("compliance") or {}
    if not c.get("ok") and c.get("cap") is not None:
        cap = c["cap"]
        if dims.get("compliance", 10) > cap:
            ded.append({"kind": "compliance", "dim": "compliance",
                        "from": dims.get("compliance"), "to": cap,
                        "why": "命中违禁词「{}」（{}风险），合规分封顶 {}".format(
                            c["hits"][0]["word"], c["hits"][0]["level"], cap)})
            dims["compliance"] = cap
    l = gates.get("length") or {}
    if l and not l.get("ok"):
        n, lo, hi = l["chars"], l["lo"], l["hi"]
        span = max(1, hi - lo)
        off = (n - hi) if n > hi else (lo - n)
        cap = 3 if off > span * 0.3 else 6
        if dims.get("platform_fit", 10) > cap:
            ded.append({"kind": "length", "dim": "platform_fit",
                        "from": dims.get("platform_fit"), "to": cap,
                        "why": "字数 {} 不在 {}~{} 区间（偏离 {} 字），平台适配分封顶 {}".format(
                            n, lo, hi, abs(off), cap)})
            dims["platform_fit"] = cap
    a = gates.get("anchor") or {}
    if a and not a.get("ok", True):
        if dims.get("info_density", 10) > 5:
            ded.append({"kind": "anchor", "dim": "info_density",
                        "from": dims.get("info_density"), "to": 5,
                        "why": "问题清单未锚定率 {:.0%}，定位不可信 → 信息密度分封顶 5".format(
                            a.get("miss_rate", 0))})
            dims["info_density"] = 5
    return dims, ded


def total_score(dims):
    """加权总分，0~100（保留 1 位小数）。"""
    s = 0.0
    for k in DIM_KEYS:
        s += float(dims.get(k, 0)) * DIM_WEIGHT[k]
    return round(s * 10.0, 1)


def normalize_scored_doc(raw, text, platform):
    """把模型返回的一篇打分结果归一化 + 上本地闸门。

    这里的顺序很重要：**先跑本地闸门 → 再校验锚点 → 再把本地上限压上去 → 最后算总分**。
    倒过来做的话，压分之后的总分与展示的维度分会对不上。
    """
    raw = raw if isinstance(raw, dict) else {}
    dims_raw = raw.get("dims") if isinstance(raw.get("dims"), dict) else {}
    dims = {k: _clamp(dims_raw.get(k, 6)) for k in DIM_KEYS}
    issues_raw = raw.get("issues") if isinstance(raw.get("issues"), list) else []
    issues_raw = [i for i in (issues_raw or []) if isinstance(i, dict)][:12]
    ok_issues, bad_issues = anchor_issues(issues_raw, text)
    total_issues = len(ok_issues) + len(bad_issues)
    anchor_stat = {
        "ok": True,
        "total": total_issues,
        "verified": len(ok_issues),
        "unanchored": len(bad_issues),
        "miss_rate": round(len(bad_issues) / float(total_issues), 3) if total_issues else 0.0,
        "rules": {},
        "no_actionable": False,
    }
    for it in ok_issues:
        r = it.get("anchor_rule") or "-"
        anchor_stat["rules"][r] = anchor_stat["rules"].get(r, 0) + 1
    # 定位失败判据一：未锚定率过高
    if total_issues and anchor_stat["miss_rate"] > ANCHOR_MAX_MISS:
        anchor_stat["ok"] = False
        anchor_stat["why"] = ("{} 条问题里 {} 条的引文在原稿里找不到（未锚定率 {:.0%} > {:.0%}）"
                              "——模型在编引文，这份清单不可执行".format(
                                  total_issues, len(bad_issues),
                                  anchor_stat["miss_rate"], ANCHOR_MAX_MISS))
    gates = evaluate_gates(text, platform, ok_issues, anchor_stat)
    dims, ded = apply_local_caps(dims, gates)
    doc = {
        "chars": char_count(text),
        "sentences": len(split_sentences(text)),
        "paragraphs": len(split_paras(text)),
        "dims": dims,
        "dim_notes": (raw.get("dim_notes") if isinstance(raw.get("dim_notes"), dict) else {}),
        "total": total_score(dims),
        "issues": ok_issues,
        "unanchored_issues": bad_issues,
        "summary": (raw.get("summary") or "").strip(),
        "deductions": ded,
        "gates": gates,
    }
    doc["gate_failed"] = gate_failed(gates)
    return doc


# ---------------------------------------------------------------------------
# 断点续跑（`all` 用）
#
# 事故复盘（同族踩过三次，本包一次都不许再踩）：
#   · 内容截断没进 key   → 把 8000 字截成 4000 字重跑，key 没变，静默复用了旧产物
#   · resolution 没进 key → 换了档位重跑，命中的还是上一档的产物
#   · 死参数没进 key     → 参数调了但没生效，用户以为改过了
# 结论：**断点 key 必须含全部影响产出的维度**。本包的产出由下面这些量共同决定，
# 少一个就会出现"改了参数却复用旧产物"。
# ---------------------------------------------------------------------------

STATE_NAME = "state.json"
STATE_VERSION = 1


def state_key(stage, source_sha=None, source_chars=None, prompt_chars=None,
              model=None, platform=None, temperature=None, round_no=None,
              target=None, baseline_sha=None, rounds=None,
              rubric=RUBRIC_VERSION, prompt=PROMPT_VERSION):
    """算一个断点 key：**所有影响产出的维度都在里面**。

    参数逐个都有关联的事故：
      source_sha / source_chars  稿件内容变了必须重跑（摘要防"改了一个字却复用"）
      prompt_chars               实际喂给模型的字符数；截断上限变了必须重跑
      model / temperature        换模型或换温度就是换产出
      platform                   换平台口径 = 换字数区间与评分尺子
      round_no                   第几轮；轮次不同产物不同
      target                     目标线影响"第几轮停"
      baseline_sha               复用了哪份评分结果；那份文件变了必须重跑
      rounds                     总轮次变了，"是否已跑完"的判定就变了
      rubric / prompt            口径版本与提示词版本
    """
    payload = {
        "v": STATE_VERSION,
        "stage": stage,
        "source_sha": source_sha,
        "source_chars": source_chars,
        "prompt_chars": prompt_chars,
        "model": model,
        "platform": platform,
        "temperature": temperature,
        "round_no": round_no,
        "target": target,
        "baseline_sha": baseline_sha,
        "rounds": rounds,
        "rubric": rubric,
        "prompt": prompt,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "{}:{}".format(stage, hashlib.sha256(blob).hexdigest()[:20])


def text_sha(text):
    """稿件内容摘要（先做换行/空白归一，避免"只改了行尾空白"导致无谓重跑）。"""
    norm = re.sub(r"[ \t\r]+", " ", (text or "")).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def file_sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def state_path(outdir):
    return Path(outdir) / STATE_NAME


def load_state(outdir):
    p = state_path(outdir)
    if p.is_file():
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict) and obj.get("version") == STATE_VERSION:
                return obj
            sys.stderr.write("断点文件版本不符，按空状态重跑：{}\n".format(p))
        except (OSError, ValueError):
            sys.stderr.write("断点文件损坏，按空状态重跑：{}\n".format(p))
    return {"version": STATE_VERSION, "entries": {}}


def save_state(outdir, state):
    p = state_path(outdir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


# ---------------------------------------------------------------------------
# 闸门：`--outdir` 不许落在包内
#
# 为什么单独做一道闸门而不是"提示一下"：Skill 包的上传白名单只收
# `.md .py .txt .json .sh .js .yaml .yml .csv`，包内塞一张 png 会让上传直接 400。
# 写文件是**写操作**，写进去之前就要拦住，不能等用户打完卡再回滚。
# 退出码 2（usage）：这是用法错误，不是闸门判定，也不是上游失败。
# ---------------------------------------------------------------------------

def pkg_dir():
    return Path(__file__).resolve().parent.parent


def ensure_outside_pkg(outdir):
    """`--outdir` 在包内 → 抛 PackagePathError（退出码 2）。"""
    root = pkg_dir()
    target = Path(outdir).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return
    raise PackagePathError(
        "输出目录 {} 在 Skill 包内（{}）。包内只允许白名单文本后缀，产出不许进包，"
        "请换到包外，例如 {}".format(target, root,
                                 Path(os.environ.get("TEMP") or ".") / "content-qc-out"))


# ---------------------------------------------------------------------------
# 逐句改动台账（纯本地，零成本）
#
# 为什么台账必须**本地算**，不能只信模型自报的 changes：
# 模型经常漏报自己改过的句子（有时是忘了，有时是它觉得自己没改）。
# 只信自报的台账 = 一份"声称改了什么"的清单，不是"实际改了什么"的清单。
# 这里的做法是：本地 difflib 对齐句子 → 得到**实际**改动；
# 再把模型自报的 changes 按锚点挂上去，只补充"为什么"。
# 挂不上的自报改动记进 phantom（声称改了但实际没改）；
# 本地改了但模型没说的记进 unexplained（改了但没说为什么）。
# ---------------------------------------------------------------------------

def _pair_replace_block(ai, bj, a_sents, b_sents):
    """在一个 replace 块里按**相似度贪心配对**，返回 (pairs, left_a, left_b)。

    事故复盘（本包自测真机上看到的，不是假设）：第一版按下标硬配，
    模型把一句话拆成两句之后，台账里出现
    「还有一个坑是素材授权。」→「因为在每个环节省下来的时间，最后都会在返工里加倍还回去…」
    这种完全不相干的一对 —— 读台账的人会以为模型在乱改，其实是**配对配错了**。
    按相似度贪心配对之后，拆句会如实显示成「替换 + 新增」，一眼就懂。
    """
    cand = []
    for x in ai:
        for y in bj:
            cand.append((_similarity(a_sents[x], b_sents[y]), x, y))
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))
    used_a, used_b, pairs = set(), set(), []
    for sim, x, y in cand:
        if x in used_a or y in used_b:
            continue
        used_a.add(x)
        used_b.add(y)
        pairs.append((sim, x, y))
    pairs.sort(key=lambda t: t[1])
    left_a = [x for x in ai if x not in used_a]
    left_b = [y for y in bj if y not in used_b]
    return pairs, left_a, left_b


def sentence_align(before_text, after_text):
    """原稿 vs 定稿的逐句对齐，返回 rows（每一处改动/未改都有一行）。"""
    a_sents = split_sentences(before_text)
    b_sents = split_sentences(after_text)
    a_norm = [_norm_anchor(s) for s in a_sents]
    b_norm = [_norm_anchor(s) for s in b_sents]
    sm = difflib.SequenceMatcher(None, a_norm, b_norm, autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                rows.append({"op": "keep", "a_index": i1 + k + 1, "b_index": j1 + k + 1,
                             "before": a_sents[i1 + k], "after": b_sents[j1 + k],
                             "sim": 1.0, "verdict": "未改"})
        elif tag == "replace":
            pairs, left_a, left_b = _pair_replace_block(
                list(range(i1, i2)), list(range(j1, j2)), a_sents, b_sents)
            for sim, x, y in pairs:
                rows.append({
                    "op": "replace", "a_index": x + 1, "b_index": y + 1,
                    "before": a_sents[x], "after": b_sents[y], "sim": round(sim, 3),
                    # 相似度 ≥ PARAPHRASE_SIM 的"替换"其实只是换了说法：
                    # 字数、信息点都没变，读起来不一样而已。
                    "verdict": "疑似仅换词" if sim >= PARAPHRASE_SIM else "实质改写",
                })
            for x in left_a:
                rows.append({"op": "delete", "a_index": x + 1, "b_index": None,
                             "before": a_sents[x], "after": "", "sim": 0.0,
                             "verdict": "删除"})
            for y in left_b:
                rows.append({"op": "insert", "a_index": None, "b_index": y + 1,
                             "before": "", "after": b_sents[y], "sim": 0.0,
                             "verdict": "新增"})
        elif tag == "delete":
            for k in range(i2 - i1):
                rows.append({"op": "delete", "a_index": i1 + k + 1, "b_index": None,
                             "before": a_sents[i1 + k], "after": "",
                             "sim": 0.0, "verdict": "删除"})
        else:                                   # insert
            for k in range(j2 - j1):
                rows.append({"op": "insert", "a_index": None, "b_index": j1 + k + 1,
                             "before": "", "after": b_sents[j1 + k],
                             "sim": 0.0, "verdict": "新增"})
    rows.sort(key=lambda r: (r["a_index"] is None, r["a_index"] or 0,
                             r["b_index"] is None, r["b_index"] or 0))
    return rows


PARAPHRASE_SIM = 0.90     # "替换"但相似度 ≥ 它就判「疑似仅换词」


def merge_ledger(rows, model_changes, before_text, same_base=True):
    """把模型自报的 changes 挂到本地台账上，补出"为什么"。

    返回 (rows, phantom, unexplained)。

    `same_base=False` 表示这份自报清单**不是针对 `before_text` 的**（比如 `all` 跑了两轮，
    自报的是第 2 轮相对第 1 轮版本的改动，而 `--before` 给的是最初的原稿）。
    这时候挂不上是**正常的**，不能算"虚报"，所以单独走 foreign 一栏如实说明 ——
    事故复盘：第一版不管这条，把 4 条针对中间版本的真实改动全打成了「模型声称改了、
    本地却没有」，等于给模型扣了一顶莫须有的帽子，读的人会不信任整张表。
    """
    sents = split_sentences(before_text)
    norms = [_norm_anchor(s) for s in sents]
    by_index = {}
    for r in rows:
        if r.get("a_index") is not None and r["op"] in ("replace", "delete"):
            by_index.setdefault(r["a_index"], r)
    phantom, foreign = [], []
    bucket = phantom if same_base else foreign
    for ch in (model_changes or []):
        if not isinstance(ch, dict):
            continue
        before = (ch.get("before") or "").strip()
        good, rule, idx = verify_anchor(before, sents, norms)
        if not good:
            bucket.append({"before": before, "after": (ch.get("after") or "").strip(),
                           "why": (ch.get("why") or "").strip(),
                           "reason": ("自报改动引文在原稿里找不到（锚点未通过）" if same_base
                                      else "自报改动针对的是中间版本，与 --before 不是同一稿")})
            continue
        row = by_index.get(idx + 1)
        if row is None:
            bucket.append({"before": before, "after": (ch.get("after") or "").strip(),
                           "why": (ch.get("why") or "").strip(),
                           "reason": ("自报改动的那一句在本地逐句对齐里没有被改动"
                                      if same_base else
                                      "自报改动的那一句在这一版里没有被改动（针对中间版本）")})
            continue
        if not row.get("why"):
            row["why"] = (ch.get("why") or "").strip()
            row["issue_ids"] = ch.get("issue_ids") or []
            row["why_source"] = "模型自报"
    unexplained = [r for r in rows
                   if r["op"] in ("replace", "delete", "insert") and not r.get("why")]
    return rows, phantom, unexplained, foreign


def ledger_stats(rows):
    """台账统计：改了多少句、其中多少只是换词、整体相似度。"""
    changed = [r for r in rows if r["op"] != "keep"]
    repl = [r for r in rows if r["op"] == "replace"]
    para = [r for r in repl if r["verdict"] == "疑似仅换词"]
    return {
        "sentences_before": len([r for r in rows if r["a_index"] is not None]),
        "sentences_after": len([r for r in rows if r["b_index"] is not None]),
        "changed": len(changed),
        "kept": len(rows) - len(changed),
        "replaced": len(repl),
        "inserted": len([r for r in rows if r["op"] == "insert"]),
        "deleted": len([r for r in rows if r["op"] == "delete"]),
        "paraphrase_only": len(para),
        "paraphrase_ratio": (round(len(para) / float(len(repl)), 3) if repl else 0.0),
        "changed_ratio": (round(len(changed) / float(len(rows)), 3) if rows else 0.0),
    }


def body_similarity(before_text, after_text):
    """整体相似度（字符二元组 Jaccard）。越低说明改得越透。"""
    return round(_similarity(before_text, after_text), 3)


# ---------------------------------------------------------------------------
# 渲染（人读文本）
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "✗ " + s
    return "\x1b[31m{}\x1b[0m".format(s)


def render_score_md(doc, platform, model, usage, elapsed, source_path=None):
    pf = PLATFORMS[platform]
    out = ["# 内容质检 · {}".format(pf["name"]), ""]
    out.append("- 稿件：{}".format(source_path or "（--file）"))
    out.append("- 篇幅：{} 字符（不含空白）· {} 句 · {} 段".format(
        doc["chars"], doc["sentences"], doc["paragraphs"]))
    out.append("- 平台字数口径：{}~{} 字符".format(pf["chars"][0], pf["chars"][1]))
    out.append("- 模型：`{}`　命令端点：`POST /api/v1/chat/completions`".format(model))
    if usage:
        out.append("- token 用量：prompt={} completion={} total={}".format(
            usage.get("prompt_tokens", "-"), usage.get("completion_tokens", "-"),
            usage.get("total_tokens", "-")))
    if elapsed:
        out.append("- 耗时：{:.1f}s".format(elapsed))
    out.append("")
    out.append("## 各维评分")
    out.append("")
    out.append("| 维度 | 得分 | 权重 | 加权 |")
    out.append("|---|---|---|---|")
    for k in DIM_KEYS:
        s = doc["dims"][k]
        mark = " ⚠️" if s <= 4 else ""
        out.append("| {}{} | {} | {} | {:.2f} |".format(
            DIM_LABEL[k], mark, s, DIM_WEIGHT[k], s * DIM_WEIGHT[k]))
    out.append("| **加权总分** |  |  | **{}** |".format(doc["total"]))
    out.append("")
    if doc["dim_notes"]:
        out.append("### 各维依据")
        out.append("")
        for k in DIM_KEYS:
            n = doc["dim_notes"].get(k)
            if n:
                out.append("- **{}**：{}".format(DIM_LABEL[k], n))
        out.append("")
    if doc["deductions"]:
        out.append("### 本地确定性扣分（模型给多高都会被压下来）")
        out.append("")
        for d in doc["deductions"]:
            out.append("- {}：{} → {} —— {}".format(
                DIM_LABEL.get(d["dim"], d["dim"]), d["from"], d["to"], d["why"]))
        out.append("")
    g = doc["gates"]
    bad = [k for k in ("compliance", "placeholder", "prompt_echo", "length", "anchor")
           if g.get(k) and not g[k].get("ok", True)]
    if bad:
        out.append("> ⚠️ 本地闸门：{} 项命中 —— {}。命中项已压分并标红，定稿前必须处理。".format(
            len(bad), "、".join(bad)))
    else:
        out.append("> ✅ 本地闸门：合规 / 占位符 / 照抄示例 / 字数 / 定位锚点 五项全部通过。")
    out.append("")

    a = g.get("anchor") or {}
    out.append("## 定位到句子的问题清单（{} 条）".format(len(doc["issues"])))
    out.append("")
    if a:
        out.append("锚点校验：{} 条引文，{} 条在原稿里找到（{}），{} 条找不到{}。".format(
            a.get("total", 0), a.get("verified", 0),
            "、".join("{}×{}".format(v, k) for k, v in sorted((a.get("rules") or {}).items())) or "-",
            a.get("unanchored", 0),
            "（未锚定率 {:.0%}）".format(a.get("miss_rate", 0)) if a.get("total") else ""))
        out.append("")
    if not doc["issues"]:
        out.append("（模型没有给出可定位到句子的问题。若总分低于目标线，这一点本身就是"
                   "「定位失败」，会被闸门拦下。）")
        out.append("")
    for i, it in enumerate(doc["issues"], 1):
        head = "{}. 第 {} 句 · {} 风险 · {}".format(
            i, it.get("sent_no") or "?", it.get("severity") or "中",
            "/".join(DIM_LABEL.get(d, d) for d in (it.get("dims") or ["-"])))
        if (it.get("severity") or "") == "高":
            head = _red(head)
        out.append(head)
        out.append("   - 原句（锚点 {}）：{}".format(it.get("anchor_rule") or "-",
                                              it.get("sentence") or it.get("quote")))
        out.append("   - 问题：{}".format(it.get("why") or "-"))
        out.append("   - 改法：{}".format(it.get("fix") or "-"))
    out.append("")
    if doc["unanchored_issues"]:
        out.append("## 未通过锚点校验的问题（{} 条，**不进改写输入**）".format(
            len(doc["unanchored_issues"])))
        out.append("")
        for i, it in enumerate(doc["unanchored_issues"], 1):
            out.append("- {} 引文「{}」——{}".format(
                i, (it.get("quote") or "")[:60], it.get("why_unverified") or ""))
        out.append("")
    if doc["summary"]:
        out.append("## 总评")
        out.append("")
        out.append(doc["summary"])
        out.append("")
    out.append("下一步：`python3 run.py revise --file <原稿> --platform {} "
               "--rounds 2 --out 定稿.json`".format(platform))
    return "\n".join(out)


def render_ledger_md(rows, stats, before_text, after_text, facts, phantom, unexplained,
                     foreign=None):
    out = ["# 改动台账（逐句）", ""]
    out.append("> 台账由**本地 difflib 逐句对齐**算出，不是模型自报的清单。"
               "模型自报的改动只在「为什么」那一栏补充说明，挂不上的会单独列出。")
    out.append("")
    out.append("- 原稿 {} 句 → 定稿 {} 句；改动 {} 句，未改 {} 句".format(
        stats["sentences_before"], stats["sentences_after"], stats["changed"], stats["kept"]))
    out.append("- 替换 {} · 新增 {} · 删除 {}".format(
        stats["replaced"], stats["inserted"], stats["deleted"]))
    out.append("- 其中**疑似仅换词**（相似度 ≥ {}）{} 处，占替换的 {:.0%}".format(
        PARAPHRASE_SIM, stats["paraphrase_only"], stats["paraphrase_ratio"]))
    out.append("- 整体相似度（字符二元组 Jaccard）：{}（越低说明改得越透）".format(
        body_similarity(before_text, after_text)))
    out.append("")
    if unexplained:
        out.append("- ⚠️ 有 {} 处改动模型**没说为什么**（台账里标为「未说明」）".format(
            len(unexplained)))
        out.append("")
    if foreign:
        out.append("## 自报清单是相对**中间版本**的改动（{} 处，无法与 `--before` 对齐）".format(
            len(foreign)))
        out.append("")
        out.append("这不是虚报：多轮闭环里，最后一轮的自报改动是相对**上一轮版本**的，"
                   "而这里的 `--before` 给的是最初原稿。想逐轮对齐请直接看 "
                   "`REPORT.md` 与 `ledger.json`。")
        out.append("")
        for i, p in enumerate(foreign, 1):
            out.append("- {}. 「{}」→「{}」".format(
                i, p["before"][:50], p["after"][:50]))
        out.append("")
    if phantom:
        out.append("## 模型声称改了、本地对齐里却没有的改动（{} 处）".format(len(phantom)))
        out.append("")
        out.append("这一栏是**防自报失真**用的：模型有时会漏报，有时会虚报。"
                   "以本页表格（本地算的）为准。")
        out.append("")
        for i, p in enumerate(phantom, 1):
            out.append("- {}. 「{}」→「{}」（{}）".format(
                i, p["before"][:50], p["after"][:50], p.get("reason") or ""))
        out.append("")
    out.append("## 逐句对照")
    out.append("")
    out.append("| 句 | 判定 | 相似度 | 原句 | 定稿 | 为什么 |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        if r["op"] == "keep":
            continue
        out.append("| {}→{} | {} | {} | {} | {} | {} |".format(
            r.get("a_index") or "-", r.get("b_index") or "-", r["verdict"], r["sim"],
            (r["before"] or "")[:40].replace("|", "／"),
            (r["after"] or "")[:40].replace("|", "／"),
            (r.get("why") or "未说明").replace("|", "／")[:60]))
    out.append("")
    out.append("## 事实保全（原稿里的数字与专有名词）")
    out.append("")
    out.append("- 抽出事实 {} 条，定稿里仍在 {} 条，保全率 {:.0%}".format(
        facts["total"], facts["kept"], facts["kept_rate"]))
    if facts["renumbered"]:
        out.append("- 换了写法但仍在 {} 条：{}".format(
            len(facts["renumbered"]),
            "、".join("{} → {}".format(f["raw"], f.get("as")) for f in facts["renumbered"])))
    if facts["lost"]:
        out.append("")
        out.append("**丢了 {} 条（必须人工确认是不是有意去掉的）**：".format(len(facts["lost"])))
        out.append("")
        for f in facts["lost"]:
            kind = "数字" if f["kind"] == "num" else (f.get("label") or "专名")
            out.append("- [{}] `{}` —— 原句：{}".format(kind, f["raw"], f["context"]))
    else:
        out.append("- ✅ 一条都没丢。")
    out.append("")
    return "\n".join(out)


def render_report_md(result):
    """`all` / `revise` 的总报告：评分轨迹 + 台账摘要 + 闸门 + 事实。"""
    out = ["# 内容质量闭环 · 总报告", ""]
    out.append("- 稿件：{}".format(result.get("source_path") or "-"))
    out.append("- 平台口径：{}".format(platform_name(result["platform"])))
    out.append("- 模型：`{}`".format(result.get("model")))
    out.append("- 目标线：{} 分（加权总分 0~100）".format(result.get("target")))
    out.append("- 轮次：{}".format(result.get("rounds")))
    out.append("")
    out.append("## 评分轨迹")
    out.append("")
    out.append("> " + CONVERGE_NOTE)
    out.append("")
    out.append("| 阶段 | 加权总分 | 信息密度 | 结构 | 可读性 | 合规 | 平台适配 | 说明 |")
    out.append("|---|---|---|---|---|---|---|---|")
    for t in result.get("trajectory") or []:
        d = t.get("dims") or {}
        out.append("| {} | **{}** | {} | {} | {} | {} | {} | {} |".format(
            t.get("label"), t.get("total"), d.get("info_density", "-"), d.get("structure", "-"),
            d.get("readability", "-"), d.get("compliance", "-"), d.get("platform_fit", "-"),
            t.get("note") or ""))
    out.append("")
    conv = result.get("convergence") or {}
    if conv.get("converged"):
        out.append("**结论：已收敛。** {}".format(conv.get("why") or ""))
    else:
        out.append(_red("**结论：未收敛。** {}".format(conv.get("why") or "")))
    out.append("")
    sc = result.get("scoring_scale") or {}
    if sc:
        out.append("## 评分口径（**这条必须看，否则会得出错误结论**）")
        out.append("")
        out.append("- 第 0 轮 = **单篇口径**（一次调用只给它一篇）：{} 分".format(
            sc.get("baseline_total")))
        if sc.get("pair_original_totals"):
            out.append("- 第 1 轮起 = **同轮匿名双评口径**（一次调用里给原稿与新稿各打一次）："
                       "原稿在双评口径下 {} 分".format(sc.get("pair_original_totals")))
            out.append("- **两种口径的分不在同一把尺子上**：本次实测差 {} 分"
                       "（单篇 − 双评）。`--target` 按 **{}** 口径判定。".format(
                           sc.get("mode_gap"), sc.get("target_mode")))
            out.append("- 所以：拿 `score` 的单篇分去跟这里的双评分比，一定会得出"
                       "「改了也没变好」的错误结论。想只看单篇口径就 `--rounds 0`。")
        out.append("")
        out.append("> {}".format(sc.get("note")))
        out.append("")
    led = result.get("ledger") or {}
    if led.get("stats"):
        s = led["stats"]
        out.append("## 改动规模")
        out.append("")
        out.append("- 改动 {} 句 / 共 {} 句（{:.0%}）；整体相似度 {}".format(
            s["changed"], s["sentences_before"], s["changed_ratio"], led.get("body_sim")))
        out.append("- 替换 {} 处，其中**疑似仅换词** {} 处（占 {:.0%}）".format(
            s["replaced"], s["paraphrase_only"], s["paraphrase_ratio"]))
        out.append("- 模型没说为什么的改动：{} 处".format(len(led.get("unexplained") or [])))
        out.append("- 模型声称改了、本地对齐里却没有的：{} 处".format(
            len(led.get("phantom") or [])))
        out.append("")
    fl = result.get("fact_loss") or {}
    if fl:
        out.append("## 事实保全")
        out.append("")
        out.append("- 抽出 {} 条，仍在 {} 条，保全率 {:.0%}{}".format(
            fl.get("total", 0), fl.get("kept", 0), fl.get("kept_rate", 1.0),
            "" if fl.get("ok") else "  ← **有丢失，闸门命中**"))
        for f in fl.get("lost") or []:
            out.append("- 丢了 [{}] `{}` —— 原句：{}".format(
                "数字" if f["kind"] == "num" else (f.get("label") or "专名"),
                f["raw"], f["context"]))
        out.append("")
    g = result.get("gates") or {}
    out.append("## 闸门结论（对定稿）")
    out.append("")
    for k in ("compliance", "placeholder", "prompt_echo", "length", "anchor"):
        v = g.get(k) or {}
        out.append("- {}：{}".format(
            k, "通过" if v.get("ok", True) else "**命中**"))
    out.append("")
    out.append("## 定稿")
    out.append("")
    out.append(result.get("final") or "")
    out.append("")
    return "\n".join(out)


def render_rules_md(rep, platform):
    out = ["# 本地规则自检（零成本）", ""]
    out.append("- 稿件：{}".format(rep["source_path"] or "-"))
    out.append("- 平台口径：{}".format(platform_name(platform)))
    out.append("- 篇幅：{} 字符（不含空白）· {} 句 · {} 段".format(
        rep["chars"], rep["sentences"], rep["paragraphs"]))
    out.append("")
    for key, label in (("compliance", "合规（广告法违禁词，硬闸门）"),
                       ("placeholder", "占位符残留（硬闸门）"),
                       ("prompt_echo", "照抄提示词示例（硬闸门）"),
                       ("length", "字数区间（硬闸门）"),
                       ("structure", "结构（软提示，不拦）")):
        v = rep["checks"].get(key) or {}
        out.append("## {}：{}".format(label, "通过" if v.get("ok") else "命中"))
        out.append("")
        if key == "compliance":
            for h in v.get("hits") or []:
                out.append("   - 🚫 「{}」（{}风险）—— {}｜上下文：…{}…".format(
                    h["word"], h["level"], h["why"], h["context"]))
            for e in v.get("exempted") or []:
                out.append("   - （已放过，人工确认）「{}」—— 判定为普通用法：…{}…".format(
                    e["word"], e["context"]))
        elif key in ("placeholder", "prompt_echo"):
            for h in v.get("hits") or []:
                out.append("   - " + (h.get("why") or ""))
        elif key == "length":
            out.append("   - 字数 {}，区间 {}~{}，偏离 {} 字".format(
                v.get("chars"), v.get("lo"), v.get("hi"), v.get("delta")))
        else:
            for m in v.get("missing") or []:
                out.append("   - " + m)
        if not (v.get("hits") or v.get("missing") or key == "length"):
            out.append("   - 无")
        out.append("")
    out.append("## 事实清单（会被改写提示词带去，并逐条核对）")
    out.append("")
    out.append("- 抽出 {} 条（数字 + 启发式专有名词）".format(len(rep["facts"])))
    out.append("")
    for f in rep["facts"][:40]:
        kind = "数字" if f["kind"] == "num" else (f.get("label") or "专名")
        out.append("- [{}] `{}`".format(kind, f["raw"]))
    if len(rep["facts"]) > 40:
        out.append("- …（还有 {} 条）".format(len(rep["facts"]) - 40))
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 本地结构自检（软提示）
# ---------------------------------------------------------------------------

def structure_checks(text, platform):
    """结构软提示。**故意不拦**：审的是别人写好的成稿，缺 CTA 常常是合理选择。"""
    pf = PLATFORMS[platform]
    paras = split_paras(text)
    sents = split_sentences(text)
    missing = []
    pc_lo, pc_hi = pf["para_count"]
    if len(paras) < pc_lo:
        missing.append("段落数只有 {}，低于该平台常见区间 {~{}（可能是一坨到底）".format(
            len(paras), pc_lo, pc_hi))
    if len(paras) > pc_hi:
        missing.append("段落数 {}，高于该平台常见区间 {~{}（可能太碎）".format(
            len(paras), pc_lo, pc_hi))
    pch_lo, pch_hi = pf["para_chars"]
    long_paras = [i + 1 for i, p in enumerate(paras) if char_count(p) > pch_hi]
    if long_paras:
        missing.append("第 {} 段超过 {} 字符，建议拆段".format(
            "、".join(str(i) for i in long_paras[:6]), pch_hi))
    long_sents = [s for s in sents if char_count(s) > 70]
    if long_sents:
        missing.append("有 {} 句超过 70 字符（中文长句是「读两遍才懂」的主因），"
                       "例：{}".format(len(long_sents), long_sents[0][:30] + "…"))
    if pf.get("cta"):
        tail = "".join(sents[-3:]) if sents else ""
        if not re.search(pf["cta"], tail):
            missing.append("结尾 3 句里没有该平台的动作引导词（{}）".format(pf["cta"]))
    return {"ok": not missing, "missing": missing,
            "paragraphs": len(paras), "sentences": len(sents)}


# ---------------------------------------------------------------------------
# 子命令：读取与校验
# ---------------------------------------------------------------------------

def read_text(path, what="稿件"):
    p = Path(path)
    if not p.is_file():
        raise UsageError("找不到{}文件：{}".format(what, path))
    raw = p.read_bytes()
    # BOM 会让第一个字变成不可见字符，字数统计与逐句定位都会偏。
    for bom in (b"\xef\xbb\xbf",):
        if raw.startswith(bom):
            raw = raw[len(bom):]
            break
    return raw.decode("utf-8", "replace")


def check_platform(platform):
    if platform not in PLATFORMS:
        raise UsageError("平台名 `{}` 不认识；可选：{}".format(platform, "、".join(PLATFORM_CHOICES)))
    return platform


def check_budget(a):
    """`--budget` 必须配单价，否则无法核价 → 退出码 2（不假装在预算内）。"""
    if getattr(a, "budget", None) is not None:
        pi = getattr(a, "price_in", None)
        po = getattr(a, "price_out", None)
        if pi is None or po is None:
            raise UsageError(
                "--budget 必须同时给 --price-in 与 --price-out（点/百万 token）。"
                "文本模型网关不公布单价，没单价就没法核预算——不假装在预算内。"
                "只想看 token 就别传 --budget。")


def load_baseline(path, text, platform):
    """复用一份已有的 `score --json --out` 结果，省掉基线那次调用。

    **必须核对稿件一致性**：baseline 里的 source_sha 与当前稿件不一致时直接拒用（退出码 2），
    不许"拿 A 稿的分数给 B 稿用"。这也是同族"静默复用旧产物"事故的同一类防护。
    """
    p = Path(path)
    if not p.is_file():
        raise UsageError("找不到 baseline 文件：{}".format(path))
    try:
        obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise UsageError("baseline 不是合法 JSON：{}（{}）".format(path, exc))
    if not isinstance(obj, dict) or "docs" not in obj and "doc" not in obj:
        raise UsageError("baseline 结构不对：既没有 doc 也没有 docs 字段。"
                         "应当是本包 `score --json --out` 的产物。")
    base = obj.get("doc") or (obj.get("docs") or {}).get("source")
    if not isinstance(base, dict):
        raise UsageError("baseline 里找不到可用的原始打分对象。")
    src = obj.get("source") or {}
    if src.get("platform") and src["platform"] != platform:
        raise UsageError("baseline 是 {} 口径，本次是 {} —— 尺子不同不许复用。".format(
            src["platform"], platform))
    if src.get("sha") and src["sha"] != text_sha(text):
        raise UsageError(
            "baseline 与本次稿件内容不一致（摘要不同），拒绝复用："
            "baseline={} 本次={}。换稿件请重新打分，或去掉 --baseline。".format(
                str(src.get("sha"))[:12], text_sha(text)[:12]))
    return obj, base


def _sum_usage(usages):
    out = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    has = False
    for u in usages or []:
        if not isinstance(u, dict):
            continue
        for k in out:
            v = u.get(k)
            if isinstance(v, int):
                out[k] += v
                has = True
    return out if has else {}


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------

def _emit(a, result, md_text, ok=True):
    """统一出口：`--json` 时补 ok 写**真 stdout**（同时落 `--out`），否则原样打人读文本。"""
    if a.json:
        body = _json_text(result, indent=2, ok=ok)
        if getattr(a, "out", None):
            Path(a.out).write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 {}\n".format(a.out))
        _json_write(body)
        return
    if getattr(a, "out", None):
        Path(a.out).write_text(md_text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    print(md_text)


def _gate_stderr(label, doc):
    """把硬闸门命中汇总到 stderr（标红 + 逐条原因），返回是否命中。"""
    g = doc.get("gates") or {}
    hit = [(k, g[k]) for k in ("compliance", "placeholder", "prompt_echo", "length", "anchor")
           if g.get(k) and not g[k].get("ok", True)]
    if not hit:
        return False
    sys.stderr.write("\n{}\n".format(_red(
        "{}：{} 项硬闸门命中，定稿前必须处理".format(label, len(hit)))))
    for k, v in hit:
        if k == "compliance":
            sys.stderr.write("   [合规] 命中 " + "、".join(
                "「{}」({})".format(h["word"], h["level"]) for h in v["hits"]) + "\n")
        elif k == "placeholder":
            sys.stderr.write("   [占位符] " + "；".join(h["why"] for h in v["hits"]) + "\n")
        elif k == "prompt_echo":
            sys.stderr.write("   [照抄示例] " + "；".join(h["why"] for h in v["hits"]) + "\n")
        elif k == "length":
            sys.stderr.write("   [字数] {} 不在 {}~{} 区间（偏离 {} 字）\n".format(
                v["chars"], v["lo"], v["hi"], abs(v["delta"])))
        elif k == "anchor":
            sys.stderr.write("   [定位锚点] {}（已锚定 {} / {} 条）\n".format(
                v.get("why") or "未锚定率过高", v.get("verified"), v.get("total")))
    ex = (g.get("compliance") or {}).get("exempted") or []
    if ex:
        sys.stderr.write("   提示：本地放过 {} 处疑似绝对化用语（判为普通用法），请人工确认："
                         "{}\n".format(len(ex), "、".join("「{}」".format(e["word"]) for e in ex)))
    return True


def score_one(a, text, platform, model, key, tracker, baseline_sha=None):
    """一次单篇打分（会花钱）。返回 (doc, usage, elapsed)。"""
    prompt = build_score_prompt(text, platform)
    if a.dry_run:
        return None, prompt, 0.0
    est_in = estimate_tokens_in(prompt)
    if tracker.over_budget(est_in, SCORE_ISSUE_OUT_TOKENS):
        raise BudgetStop("预估成本已超预算，**未发起这次打分调用**（{}）".format(tracker.line()))
    sys.stderr.write("正在用 `{}` 做单篇质检打分…\n".format(model))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=model, temperature=a.temperature,
                          max_tokens=a.max_tokens, key=key,
                          json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    tracker.add(usage, "score")
    obj = parse_first_json(content)
    return obj, usage, elapsed


def run_score(a):
    platform = check_platform(a.platform)
    text = read_text(a.file)
    if not text.strip():
        raise UsageError("稿件是空的：{}".format(a.file))
    check_budget(a)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    if getattr(a, "baseline", None):
        _base_obj, doc = load_baseline(a.baseline, text, platform)
        usage, elapsed = {}, 0.0
        sys.stderr.write("已复用 baseline 的打分（零成本）：{}\n".format(a.baseline))
    else:
        obj, usage, elapsed = score_one(a, text, platform, a.model, a.key, tracker)
        if a.dry_run:
            if a.json:
                _json_out({"dry_run": True, "platform": platform, "prompt": obj}, a, indent=2)
            else:
                print(obj)
            return EXIT_OK
        if not (isinstance(obj, dict) and isinstance(obj.get("dims"), dict)):
            raise QcError("模型返回里没有 dims 对象：{}".format(
                json.dumps(obj, ensure_ascii=False)[:200]))
        doc = normalize_scored_doc(obj, text, platform)
    result = {
        "mode": "score",
        "platform": platform,
        "platform_name": PLATFORMS[platform]["name"],
        "model": a.model,
        "rubric_version": RUBRIC_VERSION,
        "prompt_version": PROMPT_VERSION,
        "source": {"path": str(a.file), "sha": text_sha(text),
                   "chars": char_count(text), "platform": platform},
        "doc": doc,
        "usage": usage,
        "elapsed": elapsed,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
    }
    rc = EXIT_GATE if doc["gate_failed"] else EXIT_OK
    if rc == EXIT_GATE:
        _gate_stderr("打分", doc)
    md = render_score_md(doc, platform, a.model, usage, elapsed, a.file)
    _emit(a, result, md, ok=not rc)
    return rc


def fmt_cost_dict(tracker):
    pts = tracker.points
    return {"calls": tracker.calls,
            "prompt_tokens": tracker.prompt_tokens,
            "completion_tokens": tracker.completion_tokens,
            "total_tokens": tracker.total_tokens,
            "points": None if pts is None else round(pts, 4),
            "yuan": None if pts is None else round(pts / POINTS_PER_YUAN, 4),
            "priced": tracker.has_price}


def pair_score(a, orig, cand, platform, model, key, tracker, seed, round_no):
    """同一次调用里匿名双评（会花钱）。返回 (orig_doc, cand_doc, usage, order)。"""
    orig_first = _pair_order(seed)
    prompt = build_pair_prompt(orig, cand, platform, orig_first)
    if a.dry_run:
        return None, None, prompt, {"orig_is": "1" if orig_first else "2"}
    if tracker.over_budget(estimate_tokens_in(prompt), SCORE_ISSUE_OUT_TOKENS * 2):
        raise BudgetStop("预估成本已超预算，**未发起第 {} 轮复评**（{}）".format(
            round_no, tracker.line()))
    sys.stderr.write("第 {} 轮复评：同一次调用里匿名双评原稿与新稿（原稿是 {} 号）…\n".format(
        round_no, "1" if orig_first else "2"))
    content, usage = chat(prompt, SYSTEM_PROMPT, model=model, temperature=a.temperature,
                          max_tokens=a.max_tokens, key=key,
                          json_mode=not a.no_json_mode)
    tracker.add(usage, "pair")
    obj = parse_first_json(content)
    docs = obj.get("docs") if isinstance(obj, dict) else None
    if not isinstance(docs, list) or len(docs) < 2:
        raise QcError("模型没有按编号返回两份打分（docs 少于 2 条）")
    by_id = {}
    for d in docs:
        if isinstance(d, dict) and str(d.get("id") or "").strip() in ("1", "2"):
            by_id.setdefault(str(d["id"]).strip(), d)
    if "1" not in by_id or "2" not in by_id:
        # 编号被模型改写时，按返回顺序兜底（**并如实记录**，不假装编号是对的）
        ordered = [d for d in docs if isinstance(d, dict)]
        by_id.setdefault("1", ordered[0])
        by_id.setdefault("2", ordered[1])
        sys.stderr.write("提示：模型没有原样回填编号，已按返回顺序对齐（有对错风险）。\n")
    d_orig = normalize_scored_doc(by_id["1" if orig_first else "2"], orig, platform)
    d_cand = normalize_scored_doc(by_id["2" if orig_first else "1"], cand, platform)
    return d_orig, d_cand, usage, {"orig_is": "1" if orig_first else "2"}


def _pair_order(seed_material):
    """乱序：原稿放 1 号位还是 2 号位。**用摘要派生，保证断点续跑可复现。**"""
    h = hashlib.sha256(str(seed_material).encode("utf-8")).digest()
    return random.Random(int.from_bytes(h[:8], "big")).random() < 0.5


def revise_once(a, text, platform, model, key, tracker, issues, facts, length_note):
    """一次改写（会花钱）。返回 (final_text, model_changes, usage)。"""
    prompt = build_revise_prompt(text, platform, issues, facts, length_note)
    if a.dry_run:
        return None, None, prompt
    if tracker.over_budget(estimate_tokens_in(prompt),
                           int(len(text) * REVISE_OUT_RATIO * TOKENS_PER_CHAR_OUT)):
        raise BudgetStop("预估成本已超预算，**未发起这次改写**（{}）".format(tracker.line()))
    sys.stderr.write("正在用 `{}` 按清单重写…\n".format(model))
    content, usage = chat(prompt, SYSTEM_PROMPT, model=model, temperature=a.temperature,
                          max_tokens=a.max_tokens, key=key,
                          json_mode=not a.no_json_mode)
    tracker.add(usage, "revise")
    obj = parse_first_json(content)
    final = obj.get("final") if isinstance(obj, dict) else None
    if not isinstance(final, str) or not final.strip():
        raise QcError("模型返回里没有可用的 final 正文")
    changes = obj.get("changes") if isinstance(obj.get("changes"), list) else []
    return final.strip(), changes, usage


def _loops(a, text, platform):
    """把 --rounds / --target 收敛成一套统一的循环参数。"""
    rounds = max(0, int(a.rounds))
    target = float(a.target) if a.target is not None else DEFAULT_TARGET
    if target > 100.0:
        raise UsageError("--target {} 不可能达到：加权总分上限是 100.0。"
                         "本包不会为了「看起来很努力」去跑一个必然不收敛的循环。".format(target))
    return rounds, target


def loop_run(a, text, platform, model, key, tracker, outdir=None, state=None,
             source_sha=None, baseline=None):
    """评分 → 改写 → 复评的闭环主体。`revise` 与 `all` 共用。

    outdir/state 不为 None 时启用**断点续跑**：每个阶段的 key 都算进 state，
    命中就跳过（并打印"已完成，跳过"），不重复花钱。

    返回 result dict。
    """
    rounds, target = _loops(a, text, platform)
    base_sha = file_sha(a.baseline) if getattr(a, "baseline", None) else None
    src_sha = source_sha or text_sha(text)
    src_chars = char_count(text)

    def skey(stage, round_no=None):
        return state_key(stage, source_sha=src_sha, source_chars=src_chars,
                         prompt_chars=max(len(text), 1), model=model, platform=platform,
                         temperature=a.temperature, round_no=round_no, target=target,
                         baseline_sha=base_sha, rounds=rounds)

    def cached(stage, round_no=None):
        if state is None:
            return None
        return (state.get("entries") or {}).get(skey(stage, round_no))

    def put(stage, payload, round_no=None):
        if state is not None:
            state.setdefault("entries", {})[skey(stage, round_no)] = payload
            if outdir:
                save_state(outdir, state)

    usages = []
    trajectory = []

    # ---- 基线：单篇打分（可复用 --baseline） ----
    if baseline is not None:
        doc0 = baseline
        sys.stderr.write("基线打分来自 --baseline（零成本）。\n")
    else:
        hit = cached("score_base")
        if hit:
            doc0 = hit["doc"]
            sys.stderr.write("基线打分已在断点里，跳过（零成本）。\n")
        else:
            obj, usage, _ = score_one(a, text, platform, model, key, tracker)
            if a.dry_run:
                return {"dry_run": True, "prompt": obj}
            doc0 = normalize_scored_doc(obj, text, platform)
            usages.append(usage)
            put("score_base", {"doc": doc0, "usage": usage})
    trajectory.append({"label": "第 0 轮（原稿）", "total": doc0["total"],
                       "dims": doc0["dims"], "note": "基线单篇打分"})
    sys.stderr.write("基线总分：{}（目标 {}）\n".format(doc0["total"], target))

    cur_text, cur_doc = text, doc0
    ledger = None
    fact_loss = None
    phantom, unexplained = [], []
    pair_orig_totals = []          # 每一轮"同轮原稿"的分（双评口径），用来量口径差
    last_changes = []              # 最后一轮模型自报的改动清单（给 `diff --from` 补"为什么"）
    changes_base_sha = None        # 那份自报清单是相对哪一版稿子的（摘要）
    foreign = []
    rounds_planned = rounds
    converged = cur_doc["total"] >= target
    why = ""
    if converged and rounds > 0:
        # 已经达标就不花钱改了。**如实说明**，不要假装跑过。
        why = "原稿已达目标线 {}（{} 分），未发起任何改写调用。".format(target, cur_doc["total"])
        rounds = 0

    for r in range(1, rounds + 1):
        issues = cur_doc["issues"]
        facts = extract_facts(text)                 # 事实以**原稿**为准，逐轮都核原稿
        length_note = None
        lg = (cur_doc.get("gates") or {}).get("length") or {}
        if lg and not lg.get("ok"):
            length_note = ("注意：当前版本字数 {} 不在 {}~{} 区间，本轮请把字数带回区间内。"
                           .format(lg["chars"], lg["lo"], lg["hi"]))
        hit = cached("revise", r)
        if hit:
            cand_text, changes = hit["final"], hit["changes"]
            sys.stderr.write("第 {} 轮改写已在断点里，跳过（零成本）。\n".format(r))
        else:
            cand_text, changes, usage = revise_once(
                a, cur_text, platform, model, key, tracker, issues, facts, length_note)
            if a.dry_run:
                return {"dry_run": True, "prompt": usage}
            usages.append(usage)
            put("revise", {"final": cand_text, "changes": changes}, r)
        # 逐句台账（纯本地）
        rows = sentence_align(cur_text, cand_text)
        rows, ph, unexp, _fx = merge_ledger(rows, changes, cur_text)
        last_changes = changes
        changes_base_sha = text_sha(cur_text)
        fl = fact_loss_report(text, cand_text, warn_only=a.facts_warn_only)
        # 复评：同一次调用里匿名双评原稿与新稿
        hit = cached("pair", r)
        if hit:
            d_orig = normalize_scored_doc(hit["orig"], text, platform)
            d_cand = normalize_scored_doc(hit["cand"], cand_text, platform)
            usage, order = hit.get("usage") or {}, hit.get("order") or {}
            sys.stderr.write("第 {} 轮复评已在断点里，跳过（零成本）。\n".format(r))
        else:
            d_orig_raw, d_cand_raw, usage, order = pair_score(
                a, text, cand_text, platform, model, key, tracker,
                skey("pair", r), r)
            d_orig = d_orig_raw
            d_cand = d_cand_raw
            usages.append(usage)
            put("pair", {"orig": _raw_of(d_orig), "cand": _raw_of(d_cand),
                         "usage": usage, "order": order}, r)
        delta = round(d_cand["total"] - d_orig["total"], 1)
        trajectory.append({
            "label": "第 {} 轮（新稿）".format(r), "total": d_cand["total"],
            "dims": d_cand["dims"],
            "note": "同轮匿名双评：原稿本轮 {} 分，新稿 {} 分，涨 {} 分；改动 {} 句，其中疑似仅换词 {} 处"
                    .format(d_orig["total"], d_cand["total"], delta,
                            len([x for x in rows if x["op"] != "keep"]), 
                            len([x for x in rows if x.get("verdict") == "疑似仅换词"])),
            "delta_vs_same_round_original": delta,
            "orig_total_same_round": d_orig["total"],
            "order": order,
        })
        sys.stderr.write("第 {} 轮：新稿 {} 分（同轮原稿 {} 分，涨 {} 分）\n".format(
            r, d_cand["total"], d_orig["total"], delta))
        pair_orig_totals.append(d_orig["total"])
        cur_text, cur_doc, ledger, fact_loss = cand_text, d_cand, (rows, ph, unexp), fl
        phantom, unexplained = ph, unexp
        if cur_doc["total"] >= target:
            converged = True
            why = "第 {} 轮达到目标线 {}（{} 分）。".format(r, target, cur_doc["total"])
            break

    # 收敛判定（**必须明确，不许假装收敛**）
    converged = cur_doc["total"] >= target
    if not why:
        if rounds == 0 and rounds_planned > 0:
            why = ("原稿已达目标线 {}（{} 分），未发起改写。".format(target, cur_doc["total"])
                   if converged else
                   "轮次为 0，未做任何改写；原稿 {} 分未达目标线 {} —— 未收敛。".format(
                       cur_doc["total"], target))
        elif converged:
            why = "第 {} 轮达到目标线 {}（{} 分）。".format(rounds, target, cur_doc["total"])
        else:
            why = ("{} 轮用尽仍未达到目标线 {}（当前 {} 分，差 {} 分）。"
                   "**这就是未收敛，不做任何粉饰**：要么继续加轮次，要么人工介入，"
                   "要么把目标线调到这条稿子现实能达到的位置。".format(
                       rounds, target, cur_doc["total"],
                       round(max(0.0, target - cur_doc["total"]), 1)))

    if ledger is None:
        rows = sentence_align(text, cur_text)
        rows, phantom, unexplained, foreign = merge_ledger(rows, [], text)
        ledger = (rows, phantom, unexplained)
    rows, phantom, unexplained = ledger
    if fact_loss is None:
        fact_loss = fact_loss_report(text, cur_text, warn_only=a.facts_warn_only)
    stats = ledger_stats(rows)
    gates = cur_doc["gates"]
    final_gate_failed = gate_failed(gates)
    facts_ok = fact_loss["ok"]
    # 未收敛也算硬闸门命中（退出码 3）：`all` 的语义就是「要么达标、要么明确不达标」。
    ok = bool(converged and not final_gate_failed and facts_ok)
    # 口径差：单篇打分 vs 同轮双评打的是**同一个东西**，但分不在同一把尺子上。
    # 真机实测（同一篇稿、同一模型）：单篇口径 81.5，双评口径 71.5 / 68.5。
    # 这不是 bug 而是两种提示形态的系统性差异，所以**必须显式量出来并公示**，
    # 否则用户会拿 `score` 的单篇分去定 `--target`，然后被双评口径的分"判不达标"。
    mode_gap = None
    if pair_orig_totals:
        mean_pair = sum(pair_orig_totals) / float(len(pair_orig_totals))
        mode_gap = round(doc0["total"] - mean_pair, 1)
    scoring_scale = {
        "baseline_total": doc0["total"],
        "baseline_mode": "single（单篇打分）",
        "round_totals": [t["total"] for t in trajectory[1:]],
        "round_mode": "pair（同一次调用里匿名双评）",
        "pair_original_totals": pair_orig_totals,
        "pair_original_mean": (round(sum(pair_orig_totals) / float(len(pair_orig_totals)), 1)
                               if pair_orig_totals else None),
        "mode_gap": mode_gap,
        "target_mode": "pair" if pair_orig_totals else "single",
        "note": ("第 0 轮是**单篇口径**，第 1 轮起是**同轮匿名双评口径**，两者不在同一把尺子上"
                 "（真机实测差 {} 分）。`--target` 按 {} 口径判定；"
                 "跨口径比分数会得出错误结论。只想用单篇口径就 `--rounds 0`。"
                 .format("未测" if mode_gap is None else mode_gap,
                         "pair" if pair_orig_totals else "single")),
    }
    return {
        "mode": "all" if outdir else "revise",
        "platform": platform,
        "platform_name": PLATFORMS[platform]["name"],
        "model": model,
        "rubric_version": RUBRIC_VERSION,
        "prompt_version": PROMPT_VERSION,
        "target": target,
        "rounds_planned": rounds_planned,
        "rounds_run": max(0, len(trajectory) - 1),     # 轨迹第 0 条是基线，不算一轮
        "rounds": rounds,
        "source": {"path": str(a.file), "sha": src_sha, "chars": src_chars,
                   "platform": platform},
        "baseline": {"path": getattr(a, "baseline", None), "sha": base_sha},
        "trajectory": trajectory,
        "scoring_scale": scoring_scale,
        "convergence": {"converged": converged, "target": target,
                        "final_total": cur_doc["total"], "why": why},
        "doc": cur_doc,
        "gates": gates,
        "fact_loss": fact_loss,
        "ledger": {"stats": stats, "body_sim": body_similarity(text, cur_text),
                   "rows": rows, "phantom": phantom,
                   # `changes` / `changes_base_sha` 放在这里是为了 `diff --from <本文件>`
                   # 能取到模型自报的"为什么"，并**核对它针对的是哪一版稿子**。
                   # 台账的**实际改动**永远以本地对齐为准，这一栏只补理由。
                   "changes": last_changes,
                   "changes_base_sha": changes_base_sha,
                   "unexplained": [{"before": r.get("before"), "after": r.get("after")}
                                   for r in unexplained]},
        "final": cur_text,
        "usage": _sum_usage(usages),
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
        "ok_bool": bool(ok),
    }


def _raw_of(doc):
    """把归一化后的 doc 折回"模型原始返回"的形态，便于断点里复算（归一化是纯函数）。"""
    return {"dims": doc["dims"], "dim_notes": doc.get("dim_notes") or {},
            "issues": [{"quote": i.get("quote"), "dims": i.get("dims"),
                        "severity": i.get("severity"), "why": i.get("why"),
                        "fix": i.get("fix")} for i in doc.get("issues") or []],
            "summary": doc.get("summary") or ""}


def run_revise(a):
    return _run_loop_like(a, with_state=False)


def run_all(a):
    return _run_loop_like(a, with_state=True)


def _run_loop_like(a, with_state):
    platform = check_platform(a.platform)
    text = read_text(a.file)
    if not text.strip():
        raise UsageError("稿件是空的：{}".format(a.file))
    check_budget(a)
    outdir = None
    state = None
    if with_state:
        outdir = Path(a.outdir).resolve()
        ensure_outside_pkg(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    else:
        if getattr(a, "outdir", None):
            raise UsageError("revise 没有 --outdir（它不带断点续跑）；要目录产物与续跑请用 `all`。")
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    baseline = None
    if getattr(a, "baseline", None):
        _obj, baseline = load_baseline(a.baseline, text, platform)
    res = loop_run(a, text, platform, a.model, a.key, tracker, outdir, state,
                   baseline=baseline)
    if res.get("dry_run"):
        if a.json:
            _json_out({"dry_run": True, "platform": platform, "prompt": res["prompt"]}, a, indent=2)
        else:
            print(res["prompt"])
        return EXIT_OK
    ok = res["ok_bool"]
    if outdir is not None:
        (outdir / "final.md").write_text(res["final"] + "\n", encoding="utf-8")
        (outdir / "final.json").write_text(
            json.dumps({"source": res["source"], "final": res["final"],
                        "trajectory": res["trajectory"]}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        led = dict(res["ledger"])
        (outdir / "ledger.json").write_text(
            json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "REPORT.md").write_text(render_report_md(res) + "\n", encoding="utf-8")
        sys.stderr.write("目录产物：{}（final.md / final.json / ledger.json / REPORT.md / state.json）\n"
                         .format(outdir))
    # 闸门汇总到 stderr
    _gate_stderr("定稿", res["doc"])
    if not res["fact_loss"]["ok"]:
        sys.stderr.write("\n{}\n".format(_red(
            "事实保全：丢了 {} 条原稿事实（数字/专名），必须人工确认".format(
                len(res["fact_loss"]["lost"])))))
        for f in res["fact_loss"]["lost"]:
            sys.stderr.write("   [{}] `{}` —— 原句：{}\n".format(
                "数字" if f["kind"] == "num" else (f.get("label") or "专名"),
                f["raw"], f["context"]))
    if not res["convergence"]["converged"]:
        sys.stderr.write("\n{}\n".format(_red(
            "未收敛：{}".format(res["convergence"]["why"]))))
    sc = res.get("scoring_scale") or {}
    if sc.get("mode_gap") is not None and abs(sc["mode_gap"]) >= 5:
        sys.stderr.write("\n口径提示：单篇口径 {} 分 vs 双评口径 {} 分，**差 {} 分** —— "
                         "两种口径不在同一把尺子上，跨口径比分数会得出错误结论"
                         "（详见报告里的「评分口径」一节）。\n".format(
                             sc.get("baseline_total"), sc.get("pair_original_mean"),
                             sc.get("mode_gap")))
    sys.stderr.write("\n{}\n".format(tracker.line()))
    md = render_report_md(res)
    _emit(a, {k: v for k, v in res.items() if k != "ok_bool"}, md, ok=ok)
    # 退出码：达标 0；未收敛 / 丢事实 / 定稿仍命中硬闸门 → 3（语义与 SKILL.md 的退出码表一致）
    return EXIT_OK if ok else EXIT_GATE


def run_diff(a):
    before = read_text(a.before, "原稿")
    after = read_text(a.after, "定稿")
    if not before.strip():
        raise UsageError("原稿是空的：{}".format(a.before))
    platform = check_platform(a.platform)
    rows = sentence_align(before, after)
    model_changes, source, base_sha = [], None, None
    if getattr(a, "from_file", None):
        try:
            obj = json.loads(Path(a.from_file).read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError) as exc:
            raise UsageError("--from 文件读不了或不是合法 JSON：{}（{}）".format(
                a.from_file, exc))
        if isinstance(obj, dict):
            source = obj.get("source")
            led = obj.get("ledger") or {}
            base_sha = led.get("changes_base_sha")
            # 从 revise / all 的结果里取改动清单（几种可能的位置都认）
            for cand in (led.get("changes"), obj.get("changes"),
                         (obj.get("revise") or {}).get("changes")):
                if isinstance(cand, list) and cand:
                    model_changes = cand
                    break
    # 自报清单是不是针对 --before 这一版的？不是就别把"挂不上"当成"虚报"。
    same_base = (base_sha is None) or (base_sha == text_sha(before))
    if base_sha and not same_base:
        sys.stderr.write("提示：--from 里的自报改动是相对**另一版稿子**的"
                         "（base={} / --before={}），这些改动会列进「中间版本」一栏，"
                         "不计为虚报。\n".format(str(base_sha)[:12], text_sha(before)[:12]))
    rows, phantom, unexplained, foreign = merge_ledger(rows, model_changes, before,
                                                      same_base=same_base)
    stats = ledger_stats(rows)
    facts = fact_loss_report(before, after, warn_only=a.facts_warn_only)
    md = render_ledger_md(rows, stats, before, after, facts, phantom, unexplained, foreign)
    result = {
        "mode": "diff",
        "platform": platform,
        "before": {"path": str(a.before), "sha": text_sha(before),
                   "chars": char_count(before)},
        "after": {"path": str(a.after), "sha": text_sha(after),
                  "chars": char_count(after)},
        "ledger": {"stats": stats, "body_sim": body_similarity(before, after),
                   "rows": rows, "phantom": phantom, "foreign": foreign,
                   "changes_base_sha": base_sha,
                   "unexplained": [{"before": r.get("before"), "after": r.get("after")}
                                   for r in unexplained]},
        "fact_loss": facts,
        "changes_source": source,
    }
    rc = EXIT_OK if facts["ok"] else EXIT_GATE
    if rc == EXIT_GATE:
        sys.stderr.write("\n{}\n".format(_red(
            "事实保全：丢了 {} 条原稿事实（数字/专名）".format(len(facts["lost"])))))
        for f in facts["lost"]:
            sys.stderr.write("   [{}] `{}` —— 原句：{}\n".format(
                "数字" if f["kind"] == "num" else (f.get("label") or "专名"),
                f["raw"], f["context"]))
        sys.stderr.write("   处置：要么改回定稿把事实补上，要么确认这次改稿是有意去掉它"
                         "（真有意就去掉 --facts-warn-only 之外的判断依据，不要靠加参数糊过去）。\n")
    _emit(a, result, md, ok=not rc)
    return rc


def run_rules(a):
    platform = check_platform(a.platform)
    text = read_text(a.file)
    if not text.strip():
        raise UsageError("稿件是空的：{}".format(a.file))
    gates = evaluate_gates(text, platform)
    struct = structure_checks(text, platform)
    checks = {
        "compliance": gates["compliance"],
        "placeholder": gates["placeholder"],
        "prompt_echo": gates["prompt_echo"],
        "length": gates["length"],
        "structure": struct,
    }
    rep = {"source_path": str(a.file), "platform": platform,
           "chars": char_count(text), "sentences": len(split_sentences(text)),
           "paragraphs": len(split_paras(text)),
           "checks": checks, "facts": extract_facts(text)}
    hard = [k for k in ("compliance", "placeholder", "prompt_echo", "length")
            if not checks[k].get("ok", True)]
    rc = EXIT_GATE if hard else EXIT_OK
    if hard:
        sys.stderr.write("\n{}\n".format(_red(
            "本地规则自检：{} 项硬闸门命中（{}）".format(len(hard), "、".join(hard)))))
        for k in hard:
            v = checks[k]
            if k == "length":
                sys.stderr.write("   [{}] 字数 {} 不在 {}~{} 区间\n".format(
                    k, v["chars"], v["lo"], v["hi"]))
            else:
                for h in v.get("hits") or []:
                    sys.stderr.write("   [{}] {}\n".format(k, h.get("why") or h.get("word")))
    if not struct["ok"]:
        sys.stderr.write("\n提示：{} 项结构建议（**不拦截**，审成稿时缺项常常是合理选择）：\n".format(
            len(struct["missing"])))
        for m in struct["missing"]:
            sys.stderr.write("   - {}\n".format(m))
    _emit(a, rep, render_rules_md(rep, platform), ok=not rc)
    return rc


def run_cost(a):
    platform = check_platform(a.platform)
    text = a.text or ""
    if getattr(a, "file", None):
        text = read_text(a.file)
    if not text.strip():
        raise UsageError("要给 --file 或 --text，我才能估 token。")
    check_budget(a)
    rounds = max(0, int(a.rounds))
    calls = estimate_calls(text, platform, rounds)
    tin = sum(c["tokens_in"] for c in calls)
    tout = sum(c["tokens_out"] for c in calls)
    rec = compute_cost(tin, tout, a.price_in, a.price_out)
    rep = {
        "mode": "cost",
        "platform": platform,
        "platform_name": PLATFORMS[platform]["name"],
        "source": {"path": str(getattr(a, "file", None) or "(--text)"),
                   "sha": text_sha(text), "chars": char_count(text)},
        "rounds": rounds,
        "calls": calls,
        "total_calls": sum(c["calls"] for c in calls),
        "chars_per_token_in": CHARS_PER_TOKEN_IN,
        "tokens_per_char_out": TOKENS_PER_CHAR_OUT,
        "points_per_yuan": POINTS_PER_YUAN,
        "cost": rec,
        "note": "这是**估算，不是账单**：字符→token 的比值来自同族实测标定，"
                "不是厂商文档。真实扣费以账户流水为准。",
    }
    out = ["# 闭环成本估算", ""]
    out.append("- 稿件：{} 字符（不含空白）".format(char_count(text)))
    out.append("- 平台：{}　轮次：{}".format(PLATFORMS[platform]["name"], rounds))
    out.append("- 调用次数合计：{}".format(rep["total_calls"]))
    out.append("")
    out.append("| 阶段 | 次数 | 输入 token | 输出 token | 说明 |")
    out.append("|---|---|---|---|---|")
    for c in calls:
        out.append("| {} | {} | {} | {} | {} |".format(
            c["stage"], c["calls"], c["tokens_in"], c["tokens_out"], c["note"]))
    out.append("| **合计** | {} | {} | {} |".format(rep["total_calls"], tin, tout))
    out.append("")
    out.append("## 金额")
    out.append("")
    out.append("- {}".format(fmt_cost(rec)))
    if rec["points"] is None:
        out.append("")
        for n in rec["notes"]:
            out.append("- {}".format(n))
        out.append("")
        out.append("**本包不编价**：文本模型网关不公布单价，所以只出 token。"
                   "你自己知道账号单价（点/百万 token）就传 --price-in / --price-out。")
    out.append("")
    out.append("标定口径：1 token ≈ {} 输入字符；1 输出字符 ≈ {} token。{}"
               .format(CHARS_PER_TOKEN_IN, TOKENS_PER_CHAR_OUT, rep["note"]))
    rc = EXIT_OK
    if a.budget is not None and rec["points"] is not None:
        if rec["points"] > a.budget:
            rc = EXIT_BUDGET
            sys.stderr.write("\n{}\n".format(_red(
                "预算闸门：预估 {:g} 点超过 --budget {:g} 点，revise / all 会在发起调用前停下"
                .format(rec["points"], a.budget))))
    _emit(a, rep, "\n".join(out), ok=not rc)
    return rc


def run_models(a):
    key = a7w.load_key(a.key)
    try:
        payload = a7w._request("GET", MODELS_URL, key, timeout=60)
    except a7w.A7wError as exc:
        sys.stderr.write("拉模型清单失败：{}\n".format(exc))
        return _fail(EXIT_CALL, "call", "拉取模型清单失败（网络 / 鉴权 / Key）")
    lst = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(lst, dict):
        lst = lst.get("data") or lst.get("list") or []
    lst = [m for m in (lst or []) if isinstance(m, dict)]
    if a.type and a.type != "all":
        lst = [m for m in lst if str(m.get("type_code")) == a.type]
    if a.json:
        _json_out(lst, a, indent=1)
        return EXIT_OK
    print("在架模型 {} 个（{}）\n".format(len(lst), MODELS_URL))
    for m in lst:
        print("  {:<26} {:<8} call_type={}  {:<28} {}".format(
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            m.get("call_type"), str(m.get("vendor_name") or "-"),
            str(m.get("model_name") or "")[:24]))
    print("")
    print("提示：模型名会变，以本命令现查为准，别写死在脚本里。")
    print("      `{}` 实测可用（路由到 deepseek-flash），但它**不在**上面这份列表里，"
          .format(DEFAULT_MODEL))
    print("      所以「列表里没有」不等于「不能用」。")
    print("用法：run.py score --file 稿子.md --model <model_code>")
    return EXIT_OK


# ---------------------------------------------------------------------------
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封（已经吐过结果的，ok 写在那个结果里）
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#
# 信封必须落在**真 stdout**：所有 JSON 文本都经 `_json_write` 写，绕开任何临时的 stdout 重定向。
# ---------------------------------------------------------------------------

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}

# 退出码 → 失败类别（与 SKILL.md 里公示的退出码表一致）
_KIND_BY_EXIT = {2: "usage", 3: "gate", 4: "call", 5: "budget", 130: "interrupt"}


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
    """把 JSON 文本写到**真 stdout**并记账。"""
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
           "message": message or "命令以退出码 {} 结束（人读原因见 stderr）".format(rc)}
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
        detail["where"] = "{}:{}".format(os.path.basename(last.filename), last.lineno)
    err = {"kind": "internal",
           "message": "{}: {}".format(type(exc).__name__, exc),
           "detail": detail}
    _json_write(json.dumps({"ok": False, "exit": 1, "error": err},
                           ensure_ascii=False, indent=1))


def _fail(rc, kind, message, detail=None):
    """命令函数决定失败时调它：记下原因，返回原退出码（退出码语义不变）。"""
    if _JSON["reason"] is None:
        _JSON["reason"] = {"kind": kind, "message": message, "detail": detail}
    return rc


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与 sanjianke-portrait-studio 同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py score --file x --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_model_opts(p, out=True):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 {}（实测可用；用 `run.py models` 现查在架模型）".format(
                       DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens",
                   help="最大输出 token，默认 8192（改写长文建议不低于 4096）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    if out:
        p.add_argument("--out", help="把结果写到这个文件")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_cost_opts(p):
    p.add_argument("--price-in", type=float, dest="price_in",
                   help="输入单价，单位「点/百万 token」。不给我就不给金额（不编价）")
    p.add_argument("--price-out", type=float, dest="price_out",
                   help="输出单价，单位「点/百万 token」")
    p.add_argument("--budget", type=float,
                   help="预算上限（点）。超了就地中止，退出码 5；用 --budget 必须给单价")


def _add_source_opts(p):
    p.add_argument("--file", required=True, help="待质检的稿件（.md / .txt，UTF-8）")
    p.add_argument("--platform", default=DEFAULT_PLATFORM, choices=PLATFORM_CHOICES,
                   help="平台口径，默认 {}（不指定平台就只按通用发布形态查）".format(
                       DEFAULT_PLATFORM))


def _add_loop_opts(p):
    p.add_argument("--rounds", type=int, default=2,
                   help="最多迭代几轮（评分→重写→复评算一轮），默认 2")
    p.add_argument("--target", type=float, default=DEFAULT_TARGET,
                   help="目标线（加权总分 0~100），默认 {}".format(DEFAULT_TARGET))
    p.add_argument("--baseline", help="复用一份已有的 `score --json --out` 结果当基线，"
                                      "省掉基线那次调用（会核对稿件摘要，不一致直接拒绝）")
    p.add_argument("--facts-warn-only", action="store_true", dest="facts_warn_only",
                   help="把「丢事实」从硬闸门降级为提示（**已知会误报**："
                        "把「87%」合法改写成「接近九成」这类。默认仍然是硬闸门）")


def _parser(**kw):
    """统一构造 ArgumentParser，**关掉长选项前缀缩写**（`allow_abbrev=False`）。

    事故复盘（本包自测时踩到的真实坑，不是理论问题）：
    `all` 上同时有 `--outdir`，用户写 `--out report.json` 想输出结果文件，
    argparse 默认允许**前缀缩写**，于是 `--out` 被当成 `--outdir` 的缩写匹配上了 ——
    结果：产出目录变成了一个叫 `report.json` 的目录，而且**不报任何错**。
    这类"参数被静默吃成另一个参数"的错误最难查，因为命令行看起来是对的。
    关掉缩写后，`--out` 直接报 unrecognized arguments（退出码 2），一眼就能看出问题。
    """
    kw.setdefault("allow_abbrev", False)
    return argparse.ArgumentParser(**kw)


def _main(argv_eff):
    ap = _parser(
        prog="run.py",
        description="三剪客 · 内容质量闭环（走 api.a7w.cn 的 OpenAI 兼容大模型端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    # 每个子命令的 parser 也必须关掉缩写：argparse 的缩写开关是**每个 parser 各自**的属性，
    # 只在父级设一遍不够（子 parser 是另造的实例，默认仍然是允许缩写）。
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("score", help="多维打分 + 定位到句子的修改建议")
    _add_source_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--baseline", help="复用一份已有的打分结果（零成本；会核对稿件摘要）")
    p.set_defaults(func=run_score, baseline=None, facts_warn_only=False)

    p = sub.add_parser("revise", help="按建议重写；--rounds 控制迭代轮数")
    _add_source_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_loop_opts(p)
    p.add_argument("--outdir", help=argparse.SUPPRESS)      # 只为给出友好报错
    p.set_defaults(func=run_revise)

    p = sub.add_parser("diff", help="原稿 vs 定稿的逐句改动台账（纯本地零成本）")
    p.add_argument("--before", required=True, help="原稿（.md/.txt）")
    p.add_argument("--after", required=True, help="定稿（.md/.txt）")
    p.add_argument("--platform", default=DEFAULT_PLATFORM, choices=PLATFORM_CHOICES,
                   help="平台口径，默认 {}".format(DEFAULT_PLATFORM))
    p.add_argument("--from", dest="from_file",
                   help="可选：revise / all 的 `--json --out` 结果，用来补上每处改动的「为什么」")
    p.add_argument("--facts-warn-only", action="store_true", dest="facts_warn_only",
                   help="把「丢事实」从硬闸门降级为提示（已知会误报）")
    _add_json(p)
    p.add_argument("--out", help="把台账写到这个文件")
    p.set_defaults(func=run_diff)

    p = sub.add_parser("rules", help="本地规则自检：违禁词/占位符/字数/结构（零成本）")
    _add_source_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把自检报告写到这个文件")
    p.set_defaults(func=run_rules)

    p = sub.add_parser("all", help="完整闭环：评分→重写→复评，断点续跑")
    _add_source_opts(p)
    _add_model_opts(p)          # 带 --out：与其它子命令一致（配合 allow_abbrev=False 不会歧义）
    _add_cost_opts(p)
    _add_loop_opts(p)
    p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".") / "content-qc-out"),
                   help="目录产物落这里（**必须在包外**）："
                        "final.md / final.json / ledger.json / REPORT.md / state.json")
    p.add_argument("--force", action="store_true",
                   help="忽略断点文件，从头重跑（key 没命中就会重新花钱）")
    p.set_defaults(func=run_all)

    p = sub.add_parser("cost", help="报价：这次闭环大概花多少 token（金额要你填单价）")
    p.add_argument("--file", help="按这篇稿子估")
    p.add_argument("--text", help="或直接给文本")
    p.add_argument("--platform", default=DEFAULT_PLATFORM, choices=PLATFORM_CHOICES,
                   help="平台口径，默认 {}".format(DEFAULT_PLATFORM))
    p.add_argument("--rounds", type=int, default=2, help="按几轮估，默认 2")
    _add_cost_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把报价写到这个文件")
    p.set_defaults(func=run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）")
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=run_models)

    try:
        a = ap.parse_args(argv_eff)
    except SystemExit as exc:
        # argparse 的参数错（退出码 2）也要给信封；--help（0）不算失败
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    # 补默认值（子命令用 set_defaults 声明过的字段在各命令里都能读到）
    for k, v in (("json", False), ("out", None), ("dry_run", False),
                 ("no_json_mode", False), ("budget", None), ("price_in", None),
                 ("price_out", None), ("baseline", None), ("facts_warn_only", False),
                 ("force", False), ("target", DEFAULT_TARGET), ("rounds", 0),
                 ("platform", DEFAULT_PLATFORM)):
        if not hasattr(a, k):
            setattr(a, k, v)
    kind, msg, detail = None, None, None
    try:
        rc = a.func(a)
    except QcError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc, kind, msg = exc.exit_code, _KIND_BY_EXIT.get(exc.exit_code, "call"), str(exc)
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


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    sys.exit(main())
