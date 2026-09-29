#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 一稿多平台改写 —— 真正的干活的脚本（零第三方依赖）。

六个子命令：

    platforms  列出支持的平台与规格（**零网络**，不花一分钱）
    plan       读原稿 → 出改写方案（各平台怎么改、保留什么、砍什么）
    rewrite    按平台改写（--platform 单个 / 可重复；--all 全跑）
    diff       原稿与改写的**结构性对比**（字数/段数/开场/结尾）——纯本地，不花钱
    cost       只算钱（token 预估 / 按你给的单价折算点数与金额 / 读实测结果）
    models     列出 api.a7w.cn 当前在架的模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py platforms
    python3 run.py plan --file draft.md
    python3 run.py rewrite --file draft.md --all --json --out out.json
    python3 run.py rewrite --file draft.md --platform xiaohongshu --platform douyin
    python3 run.py diff --file out.json
    python3 run.py cost --file draft.md --all --price-in 1 --price-out 2
    python3 run.py rewrite --file draft.md --all --budget 20 --price-in 1 --price-out 2

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py rewrite ... --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍（三条，都是踩过坑才定下来的）
    1. **平台规格是数据，不是提示词散文。** 字数区间 / 段落长度 / 开场方式 / 结尾引导 /
       话题标签数 / emoji 策略 / 标题风格全部放在 PLATFORMS 这张表里，提示词与本地闸门
       都从表里读。改规格只改表，不改逻辑。
    2. **一个平台一次调用，不让模型一次写完再"调味道"。** 如果一次调用让模型同时产出
       五个平台的稿子，实测结果就是"同一套话换五种皮"——因为模型倾向于先写一份最好写的，
       再把它裁剪成另外四份。分开调用 + 本地跨平台换皮检测（cross_platform）一起上。
    3. **闸门是硬闸门。** 命中即标红 + stderr 汇总 + 退出码非 0，不许只警告。
       退出码可直接进 CI。
"""

import argparse
import json
import os
import re
import sys
import traceback
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash / DeepSeek-V4-Flash 一线。
# 注意它**不在** /api/v1/models 的返回列表里（实测该列表给的是 DeepSeek-V4-Pro /
# DeepSeek-V4-Flash / DeepSeek-V3.2 / DeepSeek-R1-Distill-Qwen-32B 这些 **版本号名**），
# 所以别拿「列表里没有」当「不能用」。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

# 退出码（可直接用于 CI）
EXIT_OK = 0            # 全部干净
EXIT_USAGE = 2         # 参数/配置错误（例如给了 --budget 却没给单价）
EXIT_GATE = 3          # 有硬闸门命中（合规/占位符/照抄示例/字数区间/结构/跨平台换皮）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断


# ---------------------------------------------------------------------------
# 平台规格表（唯一事实来源）
#
# 【铁律】这里的每个字段都是「数据」，提示词与闸门都从这里读。
# 想改某个平台的字数区间、段落长度、标签数量，**只改这张表**，不要去改逻辑。
#
# 字段含义
#   chars         正文字数目标区间（非空白字符数，含中文标点；不含标题/结尾引导/标签）
#   para_chars    单段字数区间
#   para_count    正文段数区间
#   opening       开场方式（怎么起头）
#   ending        结尾引导（怎么收尾 + 引导什么动作）
#   hashtags      话题标签数量区间
#   emoji         emoji 策略
#   cta           结尾引导的「行动指令」识别正则（本地闸门用它判断结尾是不是真的在引导）
#   title_style   标题风格
#   tone          语感口径
#   must          这个平台的硬性要求（会进提示词，也会被本地闸门按需检查）
#
# 口径来源：各平台公开的创作规范 + 三剪客团队自己的投放经验整理，属于**经验口径**，
# 不是平台官方审核标准（官方标准不公开且会变）。区间取值偏保守，宁窄不宽。
# ---------------------------------------------------------------------------

# 目标字数取区间的中位偏下：lo + TARGET_POS × (hi - lo)。
# 为什么不直接给上限：实测模型会贴着你给的数字写，给上限就一定顶到上限（然后超）。
# 为什么不用 0.5：实测给中位数时超上限的比例明显上升。0.35 是实测下来
# 「既不会低于下限、也很少超上限」的位置（见 SKILL.md「字数区间」一节）。
TARGET_POS = 0.35


def target_chars(platform):
    """该平台的目标字数（提示词用这个数，不是上限）。"""
    lo, hi = PLATFORMS[platform]["chars"]
    return int(round(lo + (hi - lo) * TARGET_POS))


PLATFORMS = {
    "wechat": {
        "name": "公众号",
        "label": "公众号长文",
        "chars": (1200, 2200),
        "para_chars": (80, 220),
        "para_count": (6, 12),
        "opening": "现象 / 数据 / 一个具体场景切入，**前两段不出现结论**，先把读者的处境说出来",
        "ending": "把全文结论收成一句能被直接转述的话，再补一句关注或留言引导（问一个具体问题）",
        "hashtags": (0, 0),
        "emoji": "不用 emoji（正文里最多出现 0 个）",
        # 结尾引导必须出现其中至少一个动作词（本地闸门查这个）
        "cta": r"关注|留言|评论|在看|转发|分享|点赞",
        "title_style": "双段式或完整陈述句，14~24 字，偏理性克制，有信息势能；可以用 ｜ 分隔主副题",
        "tone": "书面但不端着，讲道理不讲情绪，允许长句与转折，段落之间要有递进关系",
        "must": [
            "全文要有清晰的递进结构：现象 → 拆解 → 结论，不能是并列的要点清单",
            "至少有 2 处具体的、来自原稿的事实或例子，不许自己编数字",
        ],
    },
    "xiaohongshu": {
        "name": "小红书",
        "label": "小红书笔记",
        "chars": (350, 800),
        "para_chars": (10, 60),
        "para_count": (4, 10),
        "opening": "第一人称身份 + 一个具体痛点（「我是XX，之前一直…」），第一句就要说人话",
        "ending": "口语化互动引导：收藏 / 评论 / 「你们还有别的办法吗」，结尾不要总结陈词",
        "hashtags": (5, 8),
        "emoji": "可以用 2~6 个 emoji 点缀，别每句都挂",
        "cta": r"收藏|评论|点赞|关注|告诉我|教教我|聊聊|说说|还有别的",
        "title_style": "口语短标题，10~20 字，像朋友在说话；可用 1 个 emoji 开头，不要书名号与书面语",
        "tone": "像朋友发消息，短句、多分段、允许语气词（真的 / 反正 / 亲测），不用书面连接词",
        "must": [
            "每段不超过 3 行，段与段之间空行",
            "必须有 5~8 个话题标签，放在正文最后",
            "不许出现站外联系方式（微信号 / 手机号 / 私信我 / 加V）",
        ],
    },
    "douyin": {
        "name": "抖音",
        "label": "抖音口播稿",
        "chars": (300, 600),
        "para_chars": (8, 40),
        "para_count": (6, 14),
        "opening": "前 3 秒必须出钩子：一个反常识结论、一个直接的问题、或一句「先别急着…」",
        "ending": "口播式引导：一句关注理由 + 一句评论区互动（「评论区扣 1」这类）",
        "hashtags": (3, 5),
        "emoji": "不用 emoji（这是要念出来的稿子）",
        "cta": r"关注|点赞|评论|扣\s*1|私信|转发|扣1",
        "title_style": "口语钩子，12~20 字，能直接念出来，不要书面定语和书名号",
        "tone": "纯口语，一句一行（一行就是一个气口），短句为主，允许「你」「我」对说",
        "must": [
            "一句一行，每行都是一口气能念完的短句",
            "全篇不许出现书面连接词（因此 / 综上 / 首先其次最后）",
            "必须能直接念：不出现括号注释、不出现 emoji、不出现 Markdown 记号",
        ],
    },
    "zhihu": {
        "name": "知乎",
        "label": "知乎回答",
        "chars": (800, 1500),
        "para_chars": (60, 260),
        "para_count": (5, 12),
        "opening": "结论前置或反直觉判断切入（「先说结论：…」/「这个问题下的多数回答都漏了一点」）",
        "ending": "收在一条可操作的判断或一句克制的求赞同（「以上，欢迎在评论区补充反例」）",
        "hashtags": (0, 3),
        "emoji": "不用 emoji",
        "cta": r"赞同|评论|补充|反例|怎么看|欢迎|说说",
        "title_style": "提问式或结论前置，14~26 字，专业、有信息密度；不要情绪化感叹号",
        "tone": "克制、给依据，像业内人士在答一个真问题；允许分点，但每点要有一句展开",
        "must": [
            "至少有一处明确给出「什么情况下这个结论不成立」的边界条件",
            "不许出现「我是专家」「官方认证」这类无依据的权威自称",
        ],
    },
    "toutiao": {
        "name": "头条",
        "label": "头条短文",
        "chars": (600, 1200),
        "para_chars": (30, 120),
        "para_count": (5, 12),
        "opening": "悬念或数字切入（「很多人不知道，…」/「三组数据说明…」），第一段就给信息增量",
        "ending": "一句总结 + 一句泛化的讨论引导（「你身边有这种情况吗」），不要硬求关注",
        "hashtags": (0, 3),
        "emoji": "不用 emoji",
        # 头条的结尾是**泛化讨论引导**（不是求关注），所以动作词表里包含「你身边」「卡在哪」这类问法。
        # 这一条是实测踩出来的：原来的通用词表只有「关注/收藏/评论」，把模型按规格写的
        # 「你身边有做二创的朋友吗，他们卡在哪一步？」误判成「结尾没有行动指令」——
        # 闸门与规格自相矛盾。所以 CTA 判定必须跟着平台规格走，不能一把尺子量五个平台。
        "cta": r"评论|说说|怎么看|你身边|卡在哪|聊聊|讨论|留言|你们",
        "title_style": "悬念式或数字式，16~26 字，通俗但不标题党；不要用「震惊」「不看后悔」",
        "tone": "通俗、信息前置、句子偏短，面向泛人群，少用行话，每段只讲一件事",
        "must": [
            "每段只讲一件事，段落短、信息密度高",
            "不许标题党：标题里许诺的内容，正文必须真的给到",
        ],
    },
}
PLATFORM_CHOICES = list(PLATFORMS.keys())
ALL_PLATFORMS = list(PLATFORMS.keys())


# ---------------------------------------------------------------------------
# 合规闸门的数据：广告法违禁词（全平台）+ 平台特有红线
#
# 这是一道**粗筛**：宁可多报也别漏报，最终判断仍要人工复核，
# 且不等于任何平台的官方审核结论（官方标准不公开、会变）。
# ---------------------------------------------------------------------------

# 每项：正则 → 风险等级 → 人话解释 →（可选）语境判定标签
BANNED_PATTERNS = [
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎|顶级|厉害)", "高",
     "广告法第九条禁止「最高级」用语", "superlative"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    (r"第一(名|品牌|选择|名)?(?!次)|No\.?\s*1|TOP\s*1|排名第一|销量第一|行业第一", "高",
     "「第一」类排他性表述"),
    (r"国家级|世界级|全球级|国际级", "高",
     "「国家级」等权威性词汇属明令禁止"),
    (r"100\s*%|百分之百|百分百", "高",
     "绝对化效果承诺"),
    (r"绝对(有效|安全|放心|不会|能|可以)|保证(有效|成功|瘦|赚)|无效退款", "高",
     "绝对化保证与效果担保"),
    (r"根治|治愈|痊愈|药到病除|包治|特效|无副作用|零副作用|抗癌|降(血压|血糖|血脂)", "高",
     "医疗功效宣称，普通内容不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|保本|保收益|日入过万|月入十万|高回报", "高",
     "投资类收益承诺"),
    (r"包过|保过|保录取|保证提分|不过退费|100%\s*就业", "高",
     "教育培训效果承诺，属明令禁止"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐|官方指定", "高",
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
     "成分/材质宣称需与检测报告一致"),
    (r"点击链接|加微信|私信我|扫码(加|进|领)|vx|VX|微信号|加V", "中",
     "站外导流，平台普遍限制"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看|赶紧转发", "中",
     "标题党式诱导"),
    (r"[！!]{2,}|[?？]{3,}", "低",
     "标点堆砌，易被判标题党/低质"),
]
BANNED_RE = []
for _t in BANNED_PATTERNS:
    BANNED_RE.append((re.compile(_t[0]), _t[1], _t[2],
                      _t[3] if len(_t) > 3 else None))
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}
# 合规扣分（按风险等级，取命中里最重的一档，不叠加）：
COMPLIANCE_DEDUCT = {"高": 40, "中": 20, "低": 8}

# ---------------------------------------------------------------------------
# 「最高级」用语的语境豁免（**这是被实测误伤逼出来的**）
#
# 事故复盘：真实原稿改写后，公众号那篇的结尾写「回头翻一条自己播放量最低的视频」，
# 被本地闸门判成「命中高风险（广告法第九条禁止最高级用语）」并整篇拦截。
# 这个诊断是**错的**——「播放量最低的视频」是在描述自己的数据，
# 不是对商品/服务的绝对化宣称。错的不只是等级，是理由本身就不成立。
# 「宁可多报也别漏报」在这里代价过高：一个正确写法的稿子被判违规，
# 使用者就会开始无视闸门，闸门等于废了。
#
# 豁免条件刻意做得**很窄**，只放过明确在说数据极值的形态：
#   · `最X` 前一个字是计量类名词（量/率/数/分/位/条/次/段/部/集/页/款/种/家/个/天/月/年）
#   · 且 `最X` 后面紧跟「的」或「之」
# 命中豁免时**整处放过**，但会在产出里登记下来（`gates.compliance.exempted`），
# 报告里会明说「本地放过了 1 处疑似绝对化用语」——**不静默放过**。
# 为什么不是「降级为低风险」：低风险在本包里同样拦截（与全库口径一致），
# 降级等于没修，误伤依旧会把一篇正确写法的稿子整篇拦下。
#
# 豁免词表刻意**不含** `时`/`款`/`种`/`家`/`价`：
#   「课时最低的课程」「单价最低」都是真实的价格宣称形态，必须照拦。
# ---------------------------------------------------------------------------

MEASURE_PREFIX = "量率数分位条次段部集页个天月年"


def _is_data_extreme(text, m):
    start, end = m.start(), m.end()
    before = text[start - 1] if start > 0 else ""
    after = text[end:end + 1]
    # 注意 `before and`：空字符串在 Python 里 `"" in "量率数…"` 是 True，
    # 漏了这一步句首的「最好/最低」会被全部误豁免（这是写这段时自己踩到的坑）。
    return bool(before) and before in MEASURE_PREFIX and after in ("的", "之")

# 平台特有红线：**同一个表达在不同平台的风险不一样**，所以单列一张表。
# 例：公众号里「加微信」是常规运营话术，小红书里直接判违规导流。
PLATFORM_REDLINES = {
    "wechat": [
        (r"关注(公众号)?(领|送|得)|转发(到)?(朋友圈)?(领|送)|集赞", "中",
         "公众号诱导分享/诱导关注，属违规营销"),
        (r"长按(关注|识别)|点击(阅读原文)?领", "低",
         "引导动作表述需与真实功能一致"),
    ],
    "xiaohongshu": [
        (r"微信|vx|VX|手机号|电话|扣扣|QQ|私信|加我|联系我", "高",
         "小红书对站外导流零容忍，出现联系方式即高危"),
        (r"淘宝|天猫|京东|拼多多|链接在|评论区有链接", "高",
         "引导到站外电商平台，属违规导流"),
        (r"亲测|实测|绝对|闭眼入|人手一个|全网", "中",
         "虚假种草/绝对化体验表述，笔记社区严查"),
        (r"点赞|收藏|关注(我)?(才|才能)看|三连", "中",
         "诱导互动，笔记会被限流"),
    ],
    "douyin": [
        (r"微信|vx|VX|手机号|私信|加我|主页(有)?链接", "高",
         "抖音禁止站外导流，口播稿里出现即高危"),
        (r"点击链接|小黄车|橱窗|购买链接", "中",
         "带货引导需与真实的商品挂载一致"),
    ],
    "zhihu": [
        (r"私信我|加微信|vx|VX|公众号|知识星球|星球", "高",
         "知乎对私域引流审核严格，回答里出现即高危"),
        (r"我是(专家|医生|律师|教授)|官方认证", "中",
         "无依据的权威自称，回答可信度会被质疑"),
        (r"付费咨询|课程|训练营", "中",
         "商业转化表述需与平台规则一致"),
    ],
    "toutiao": [
        (r"微信|vx|VX|私信我|加我", "中",
         "头条限制站外导流"),
        (r"点击(下方|下方链接)|下载APP|关注我领", "中",
         "引导下载/关注类表述需与真实功能一致"),
    ],
}
PLATFORM_REDLINE_RE = {
    k: [(re.compile(p), lvl, why) for p, lvl, why in v]
    for k, v in PLATFORM_REDLINES.items()
}

# 每个平台「结尾引导」的人话说明：只用于报错文案（告诉使用者该补什么动作）。
# 机器判定走 PLATFORMS[k]["cta"] 那张正则，两处必须对应。
CTA_HELP = {
    "wechat": "关注 / 留言 / 在看 / 转发",
    "xiaohongshu": "收藏 / 评论 / 告诉我 / 评论区教教我",
    "douyin": "关注 / 点赞 / 评论区扣 1",
    "zhihu": "赞同 / 评论 / 欢迎补充反例",
    "toutiao": "讨论引导（你身边…吗 / 他们卡在哪一步 / 评论区说说）",
}


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
#
# 为什么单列一道闸门：改写任务的原稿常常是别人给的模板，模型会把 `{产品名}`
# `[待填]` 这类「编稿脚手架」原样留在产出里。这种稿子看起来是完整的，
# 发出去才发现有一半是空白——比明显报错更危险。
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    (r"[{}]", "残留了占位符大括号 `{}`，模板没被替换干净"),
    (r"\[\s*待填\s*\]|【\s*待填\s*】|待填|待补充|待定", "残留「待填/待补充」占位说明"),
    (r"\bXXX+\b|\bxxx+\b|×××|某某某", "残留 `XXX` 占位符"),
    (r"（此处省略[^）]*）|\(此处省略[^)]*\)|此处省略|以下省略|略(去)?若干", "残留「此处省略」说明"),
    (r"\bTODO\b|\bTBD\b|\bFIXME\b", "残留 TODO/TBD 标记"),
    (r"\[[^\]]{0,12}(填写|插入|补充|替换)[^\]]{0,12}\]|【[^】]{0,12}(填写|插入|补充|替换)[^】]{0,12}】",
     "残留「[请填写…]」类提示语"),
]
PLACEHOLDER_RE = [(re.compile(p), why) for p, why in PLACEHOLDER_PATTERNS]


# ---------------------------------------------------------------------------
# 闸门三：prompt_echo（照抄提示词示例）
#
# 事故复盘（来自本库标题工坊的实测，两次）：
#   1. 提示词里写过正例 `结论先说：便携榨汁杯不适合三类人` → 模型直接产出
#      `结论先说：这类产品不适合三类人`
#   2. 提示词里留过 `便携榨汁杯不适合这三类人，理由有三个` → 那一轮**最高分 89.0**
#      的标题**一字不差就是它**
# 第 2 例性质更重：最高分那条是「抄了标准答案」，不是「真的最好」。
#
# 关键结论：**模型会照抄示例，哪怕那个示例标着「这是错的写法」。**
# 所以本包的提示词里不出现任何一句可直接复制的完整中文句子，
# 举例只用**跨主题**的描述性说明 + 登记在 PROMPT_SAMPLES 里的示例；
# 万一以后有人又把真实示例加回提示词，这道闸门会兜住。
#
# 判定：去标点后完全相等 → 命中；字符二元组 Jaccard ≥ ECHO_SIM → 命中；
#       示例的二元组覆盖度 ≥ ECHO_CONTAIN → 命中（第三条，见下）。
# 阈值标定依据（本库实测）：196 条正常产出与跨主题示例的最高相似度只有 0.174，
# 而「少两个字的同构照抄」是 0.765。0.75 既能兜住轻改写，离正常上限还有 4 倍余量。
# 长度守卫是**相对**的：目标归一化长度 < max(ECHO_MIN_LEN_FLOOR, len(示例)//2) 就不比，
# 因为短串的二元组集合太小、指标会虚高。
#
# 【为什么「整段 + 逐句」两层之外还要第三条】逐句比对的**比对单位是一句话**，
# 而拆句只在 。！？； 和换行处切（见 _SENT_SPLIT），**不在逗号处切**。
# 所以当模型把示例揉进自己那句话里（不在示例末尾断句）时，比对单位被撑到
# 30~36 字，Jaccard 照样被摊薄 —— 实测（见 `_eval_multiplat.py` 的结论表）：
#   · 示例1 独立成句 → 逐句 Jaccard 1.000，抓住 ✓
#   · 示例1 揉进长句（36 字）→ 逐句 Jaccard 0.576，**漏**；覆盖度 1.000，抓住 ✓
#   · 示例2 揉进长句（33 字）→ 逐句 Jaccard 0.645，**漏**；覆盖度 1.000，抓住 ✓
#   · 示例3 揉进长句（30 字）→ 逐句 Jaccard 0.517，**漏**；覆盖度 1.000，抓住 ✓
# 五条示例的单句逃逸临界长度是 21~27 字，而中文长文里 27 字以上的句子是常态 ——
# 也就是说逐句层只兜得住「示例自己独立成句」这一种形态，不是冗余而是互补。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)

# 提示词里出现过的示例文本（**跨主题**，正常不该被抄）。新增示例必须登记到这里。
# 主题刻意选「电动车充电桩」，与三剪客真实业务主题（内容创作 / 短剧 / 剪辑）明显不搭。
PROMPT_SAMPLES = [
    "小区里装充电桩到底值不值，我算了三个月的账",
    "先说结论：老小区装充电桩，卡住你的通常不是电表",
    "我住老小区，装充电桩这事踩了三个坑",
    "装充电桩前没人告诉我，物业这一关才是最难过的",
    "三组数据说明，老小区装充电桩比你想的便宜",
]


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的文案往往只改标点（`，`↔`、`↔空格）或换行位置，
    所以必须先抹平标点与空白再看。
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
    """文本是否与提示词里登记过的示例「抄得太近」。

    三条命中路径（任一即命中）：
      · 去标点后**完全相同**（最直接的照抄）
      · 字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
      · 示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（把示例夹带进更长的句子里；
        Jaccard 会被长度摊薄，只有覆盖度抓得住，依据见常量区）

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"，
    没命中时后两项为 (0.0, "", "")。
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


# 拆句：中文句末标点 + 换行。用于**逐句**比对提示词示例。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def split_sentences(text):
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def prompt_echo_scan(text, samples=None, label="正文"):
    """在一段长文本里找「照抄提示词示例」的地方。

    **为什么不能只比整段**（这是写完闸门后自测发现的漏洞）：
    长文的正文有 1000+ 字，而提示词示例只有二三十字。
    把整段正文拿去和示例算 Jaccard，分母被撑到 1000 多，相似度永远接近 0——
    也就是说**模型把示例原样抄进正文的某一段，这道闸门完全看不见**。
    而「抄示例」在长文场景下恰恰就是「有一段是抄的」，不是整篇照抄。

    所以判定分两层：
      1. 整段比一次（兜住整篇照抄的极端情况），这一层**只认 exact / jaccard**：
         整段有 1000+ 字，覆盖度在这里只能告诉你"正文里抄了一句"，指不出是哪一句，
         可操作性差；「夹带照抄」交给第二层去指位置
      2. **逐句比一次**（兜住「某一句是抄的」这个真实形态），含覆盖度判据 ——
         模型把示例揉进自己那句话里时，比对单位被撑长、Jaccard 会漏，只有覆盖度抓得住
    """
    hits = []
    whole_hit, score, sample, rule = prompt_echo(text, samples)
    if whole_hit and rule != "contain":
        hits.append({"part": label, "segment": (text or "")[:40], "sim": round(score, 3),
                     "sample": sample,
                     "why": ("与提示词示例去掉标点后完全相同（照抄示例）" if rule == "exact"
                             else "与提示词示例相似度 {:.2f}，属同构照抄".format(score))})
        return hits
    for seg in split_sentences(text):
        hit, score, sample, rule = prompt_echo(seg, samples)
        if not hit:
            continue
        if rule == "contain":
            why = ("正文里的「{}」有 {:.0f}% 的内容来自提示词示例「{}」"
                   "（覆盖度 ≥ {:.2f} 即判照抄；Jaccard 会随句子变长被摊薄）"
                   .format(seg[:20], score * 100, sample[:24], ECHO_CONTAIN))
        elif rule == "exact":
            why = ("正文里的「{}」与提示词示例去掉标点后完全相同（照抄示例）"
                   .format(seg[:20]))
        else:
            why = ("正文里的「{}」与提示词示例相似度 {:.2f}，属同构照抄"
                   .format(seg[:20], score))
        hits.append({"part": label, "segment": seg[:40], "sim": round(score, 3),
                     "sample": sample, "why": why})
        break                      # 一处命中足够拦截，不用把整篇列完
    return hits


# ---------------------------------------------------------------------------
# 闸门四：跨平台换皮检测（纯本地）
#
# 这是本包**最该有**的一道闸门。多平台改写的失败模式不是"某一篇写坏了"，
# 而是"五篇其实是同一篇换了个开场"——单看每一篇都像样，合起来等于没做改写。
# 人眼很难发现这件事（尤其五篇不并排看），但字符二元组 Jaccard 一眼看穿。
#
# 判定：两两比较正文，只有当**两边都够长**（≥ XPLAT_MIN_CHARS）时才比，
# 因为短正文的二元组集合太小，相似度会虚高。
# 阈值标定见 SKILL.md「跨平台换皮」一节（实测数据）。
# ---------------------------------------------------------------------------

XPLAT_MIN_CHARS = 200
XPLAT_SIM = 0.55        # ≥ 这个值判为「疑似换皮」


def cross_platform_check(items):
    """两两比较各平台正文，返回相似度矩阵与命中列表。"""
    keys = [k for k in items if items[k].get("body")]
    pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            ba, bb = items[a]["body"], items[b]["body"]
            if count_chars(ba) < XPLAT_MIN_CHARS or count_chars(bb) < XPLAT_MIN_CHARS:
                continue
            sim = _similarity(ba, bb)
            pairs.append({
                "a": a, "b": b,
                "a_name": PLATFORMS[a]["name"], "b_name": PLATFORMS[b]["name"],
                "sim": round(sim, 3),
                "flagged": sim >= XPLAT_SIM,
            })
    pairs.sort(key=lambda p: -p["sim"])
    return {
        "threshold": XPLAT_SIM,
        "min_chars": XPLAT_MIN_CHARS,
        "pairs": pairs,
        "flagged": [p for p in pairs if p["flagged"]],
    }


# ---------------------------------------------------------------------------
# 文本工具
# ---------------------------------------------------------------------------

def count_chars(s):
    """正文字数：去掉所有空白字符后的字符数。

    中文一个字算一个，中文标点算一个，emoji 算一个。
    为什么去掉空白：抖音口播稿是一句一行，如果换行算进字数，
    同一个内容「排成一段」和「排成二十行」会差出 20 个字，口径就不一致了。
    """
    return len(re.sub(r"\s+", "", s or ""))


def split_paras(body):
    """拆段：按换行拆，去掉空行。

    口径统一为「一个非空行 = 一段」，五个平台共用同一把尺子。
    抖音口播稿的一行是一个气口，公众号的一行是一个自然段，含义不同但计数一致。
    """
    return [ln.strip() for ln in (body or "").splitlines() if ln.strip()]


def first_sentence(text, limit=40):
    """取文本的第一句（用于开场对比），控制长度。"""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return ""
    m = re.match(r"^(.{6,%d}?[。！？!?；;])" % limit, t)
    head = m.group(1) if m else t[:limit]
    return head.strip()


def last_sentence(text, limit=60):
    """取文本的最后一句（用于结尾对比），控制长度。"""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return ""
    parts = [p for p in re.split(r"(?<=[。！？!?])", t) if p.strip()]
    tail = parts[-1].strip() if parts else t[-limit:]
    if len(tail) > limit:
        tail = tail[-limit:]
    return tail.strip()


# 结尾引导必须真的「引导」：出现这些动作词才算。
#
# 【重要】判定**按平台走**，用 PLATFORMS[platform]["cta"] 那张正则，不是一把通用尺子。
# 实测踩过的坑：头条的结尾规格是「一句总结 + 一句泛化的讨论引导（你身边有这种情况吗）」，
# 模型照着写出来了，但通用词表（只有关注/收藏/评论）判它「没有行动指令」——
# 闸门与规格自相矛盾，等于用闸门去否定自己写的规格。
# 下面这张表只作为**兜底**（平台不在表里时用），正常路径走 PLATFORMS 的 cta 字段。
CTA_FALLBACK = r"关注|收藏|评论|点赞|留言|转发|私信|扣\s*1|说说|聊聊|告诉我|你怎么看|欢迎补充|在看|分享"


def has_cta(text, platform=None):
    """结尾是否真的在引导一个动作。按平台规格判定。"""
    pat = CTA_FALLBACK
    if platform in PLATFORMS:
        pat = PLATFORMS[platform].get("cta") or CTA_FALLBACK
    return bool(re.search(pat, text or ""))


def detect_opening_type(opening, platform):
    """开场方式归类（本地启发式），用于 diff 里判断「开场真的换了没」。"""
    t = opening or ""
    if re.search(r"[？?]", t):
        return "疑问式"
    if re.search(r"^先说结论|^结论", t):
        return "结论前置"
    if re.search(r"^(我|本人|作为一个|身为)", t):
        return "第一人称代入"
    if re.search(r"^别|^先别|^不要|^千万别|^劝你", t):
        return "劝阻/警告式"
    if re.search(r"\d", t):
        return "数字切入"
    if re.search(r"^很多人|^大家|^大多数人|^不少人", t):
        return "共鸣/现象式"
    return "陈述式"


# ---------------------------------------------------------------------------
# 成本模型
#
# 现实情况（实测，别猜）：
#   · `POST /api/v1/chat/completions` 的成功响应**不带 `code` 字段**
#     （`code==1` 那套信封只用于生成应用的响应），也不返回 points_cost；
#     usage 里只有 prompt_tokens / completion_tokens / total_tokens。
#   · `GET /api/v1/models` 的 75 条模型记录里**没有任何价格字段**（实测列出全部键名确认）。
#   · `GET /api/v1/pricing` 实测只有 6 条规则（一条全局 `*` + full_video / asr /
#     flashvsr / action_transfer / person_replacement 等特例），**不含文本大模型**。
#
# 结论：**拿不到可信的文本模型单价，本包拒绝凭空编一个。**
#   · token 数我们估（用实测标定的比例），这是确定可算的；
#   · 金额必须由你给单价：`--price-in` / `--price-out`，单位「点 / 百万 token」；
#   · 单价怎么来：到 https://api.a7w.cn/ 的模型页或你的账单流水上抄，
#     或者跑一轮真实调用后看账户扣费倒推。
#   · 也支持 `cost --from-result out.json`：直接读真实调用记录里的 token 数，
#     那个数不是估算。
# ---------------------------------------------------------------------------

# 字符 → token 的标定比例（**都是实测值**，见 SKILL.md「成本口径」一节）。
#
# 实测方法：拿一次真实 rewrite --all 的 5 次调用，用每个平台的
# `usage.prompt_tokens` / `usage.completion_tokens` 除以我们实际发出去的
# 提示词字符数与收到的正文字符数（**原始字符数，含换行**）。
#
# 输入侧标定极稳（5 个平台 1.609 / 1.611 / 1.612 / 1.614 / 1.615，均值 1.612）：
CHARS_PER_TOKEN_IN = 1.61
# 输出侧按「1 个原始字符 ≈ 多少 token」算，实测均值 1.109，但平台间差别大：
#   知乎 0.93（长段）· 公众号 0.99 · 头条 1.18 · 小红书 1.33 · 抖音 1.63（一句一行，换行也花 token）
# 差异几乎全部来自**换行数**：抖音 18 行，每行一个换行 token，所以最费。
# 这里用均值，并在文档里给出各平台的实测区间——这是估算，不是账单。
TOKENS_PER_CHAR_OUT = 1.11

POINTS_PER_YUAN = 100.0     # 平台口径：1 元 = 100 点


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_tokens_out(platform):
    """估该平台的输出 token。

    按「假设模型写到了目标字数」算——**故意往多了估**：
    预算闸门的用途是「别花超」，宁可高估几分，也不能因为低估而放行。
    抖音这类一句一行的平台实际会更费（换行 token 多），文档里有实测区间。
    """
    return max(1, int(round(target_chars(platform) * TOKENS_PER_CHAR_OUT)))


def compute_cost(tokens_in, tokens_out, price_in=None, price_out=None):
    """算钱。单价单位：点 / 百万 token。缺单价时诚实返回 None。"""
    rec = {
        "tokens_in": int(tokens_in or 0),
        "tokens_out": int(tokens_out or 0),
        "price_in": price_in, "price_out": price_out,
        "unit": "点/百万 token",
        "points": None, "yuan": None, "notes": [],
    }
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
        return "无法估算金额（%s）" % "；".join(rec.get("notes") or [])
    return "%d in + %d out tokens = %g 点 = ¥%g" % (
        rec["tokens_in"], rec["tokens_out"], rec["points"], rec["yuan"])


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class RewriteError(a7w.A7wError):
    """改写 / 方案 / 调用失败（网络、鉴权、点数、模型名）。→ 退出码 4"""


class UsageError(RewriteError):
    """参数/配置用错了（没给原稿、没给平台、文件路径不存在…）。→ 退出码 2

    为什么要跟 RewriteError 分开：这两类错误的**处理方式完全不同**。
    参数错了要改命令重跑，不花一分钱；调用失败要查 Key / 点数 / 模型名。
    混成一个退出码，CI 里就没法区分「我命令写错了」和「网关挂了」。
    退出码表里写的是 2 = 参数/配置错误，所以代码必须真的这么返回。
    """


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=4096, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见。
    改写一次是一个完整平台的长文，被一次抖动打断要重跑整篇，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。

    成功响应**不带 `code` 字段**（实测），所以这里不判 code；
    只判 choices 在不在。`code==1` 那套信封是生成应用的，不适用于本端点。
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
                raise RewriteError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise RewriteError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise RewriteError(
                    "模型不存在（404）：{}  用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 429，{}s 后重试…\n".format(3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise RewriteError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise RewriteError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    if payload is None:
        raise RewriteError("网络错误：{}".format(last_exc))

    # 兜底：万一网关换了形态包了一层 {"code":1,"data":{...}}，两种都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise RewriteError("模型没返回 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    return content, usage


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    为什么要这么写：模型经常在合法 JSON 后面多吐几个字符（```、解释、第二个对象、
    重复的 }），直接 json.loads 会炸。这里用 json.JSONDecoder().raw_decode()，
    从一个 { 或 [ 开始试解码，成功就返回，失败就往后挪一个字符接着试。
    """
    if not text:
        raise RewriteError("模型返回空内容")
    dec = json.JSONDecoder()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1).strip())
    candidates.append(text)
    for cand in candidates:
        for i, ch in enumerate(cand):
            if ch not in "{[":
                continue
            try:
                obj, _end = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    raise RewriteError("模型返回的不是合法 JSON：{}".format(
        text[:300].replace("\n", " ")))


# ---------------------------------------------------------------------------
# 闸门执行：对一份产出跑全部本地检查
# ---------------------------------------------------------------------------

def compliance_scan(text, platform=None):
    """扫违禁词 + 该平台的特定红线。

    返回 {"hits": [...], "exempted": [...]}：
      · hits      —— 判定命中，硬闸门拦截
      · exempted  —— 疑似命中但语境判断为「在说数据极值而不是商品宣称」，放过但登记
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
                "context": text[max(0, m.start() - 8):m.end() + 8],
            })
            continue
        hits.append({"word": m.group(0), "level": lvl, "why": why, "scope": "广告法"})
    for rx, lvl, why in PLATFORM_REDLINE_RE.get(platform or "", []):
        m = rx.search(text)
        if m:
            hits.append({"word": m.group(0), "level": lvl, "why": why,
                         "scope": "{}特有红线".format(PLATFORMS[platform]["name"])})
    # 去重（同一个词可能同时命中广告法和平台红线）
    seen, out = set(), []
    for h in hits:
        key = (h["word"], h["scope"])
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    out.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return {"hits": out, "exempted": exempted}


def placeholder_scan(text):
    """扫占位符残留，返回命中列表。"""
    hits = []
    for rx, why in PLACEHOLDER_RE:
        m = rx.search(text or "")
        if m:
            hits.append({"found": m.group(0)[:30], "why": why})
    return hits


def length_gate(chars, platform):
    """闸门四：字数区间校验。返回 (是否达标, 详情)。"""
    lo, hi = PLATFORMS[platform]["chars"]
    d = {"chars": chars, "lo": lo, "hi": hi, "ok": lo <= chars <= hi, "delta": 0}
    if chars < lo:
        d["delta"] = chars - lo          # 负数 = 不足
    elif chars > hi:
        d["delta"] = chars - hi          # 正数 = 超出
    return d["ok"], d


def length_penalty(d):
    """按偏离程度扣分：偏离该平台区间端点的相对比例 × 100，上限 60 分。"""
    if d["ok"]:
        return 0
    lo, hi, n = d["lo"], d["hi"], d["chars"]
    ratio = (lo - n) / float(lo) if n < lo else (n - hi) / float(hi)
    return min(60, int(round(ratio * 100)))


def structure_gate(title, body, ending, platform=None):
    """闸门五：结构完整性。产出必须有 标题 + 正文 + 结尾引导。"""
    missing = []
    if not (title or "").strip():
        missing.append("标题")
    if not (body or "").strip():
        missing.append("正文")
    if not (ending or "").strip():
        missing.append("结尾引导")
    cta = has_cta(ending, platform)
    if (ending or "").strip() and not cta:
        missing.append("结尾引导里的行动指令（{}）".format(
            CTA_HELP.get(platform, "关注 / 评论 / 收藏 等")))
    return (not missing), missing, cta

def normalize_item(raw, platform):
    """把模型返回的一条产出收拾成内部结构，并跑完全部本地闸门。"""
    pf = PLATFORMS[platform]
    title = str((raw or {}).get("title") or "").strip().strip('"').strip()
    title = re.sub(r"[ \t]+", " ", title)
    body = str((raw or {}).get("body") or "").strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    ending = str((raw or {}).get("ending") or "").strip()
    hashtags = [str(t).strip().lstrip("#") for t in ((raw or {}).get("hashtags") or [])
                if str(t).strip()]
    full = "\n".join([title, body, ending])

    # 闸门一：合规（广告法 + 平台红线）
    scan = compliance_scan(full, platform)
    comp, comp_exempt = scan["hits"], scan["exempted"]
    # 闸门二：占位符残留
    ph = placeholder_scan(full)
    # 闸门三：照抄提示词示例。
    # 标题整条比一次；正文走 prompt_echo_scan（整段 + 逐句两层，见该函数注释）。
    echoes = prompt_echo_scan(title, label="标题") + prompt_echo_scan(body, label="正文")
    # 闸门四：字数区间
    chars = count_chars(body)
    len_ok, len_d = length_gate(chars, platform)
    # 闸门五：结构完整性
    st_ok, st_missing, cta = structure_gate(title, body, ending, platform)
    # 标签数量口径
    tlo, thi = pf["hashtags"]
    tag_ok = tlo <= len(hashtags) <= thi
    # emoji 口径：是否「用」emoji
    emoji_used = any(unicodedata.category(ch) == "So" for ch in full)
    emoji_ok = emoji_used if pf["emoji"].startswith("可以") else (not emoji_used)

    paras = split_paras(body)
    para_lens = [count_chars(p) for p in paras]
    avg_para = round(sum(para_lens) / len(para_lens), 1) if para_lens else 0
    plo, phi = pf["para_chars"]
    cl, ch_ = pf["para_count"]
    para_ok = bool(paras) and all(plo <= n <= phi for n in para_lens)
    pcount_ok = cl <= len(paras) <= ch_

    # 打分：100 起扣，每条扣分都写明理由
    deductions = []
    if comp:
        worst = min(LEVEL_ORDER[h["level"]] for h in comp)
        lvl = [k for k, v in LEVEL_ORDER.items() if v == worst][0]
        deductions.append({"kind": "compliance", "points": COMPLIANCE_DEDUCT[lvl],
                           "why": "命中{}风险表述：{}".format(
                               lvl, "、".join(sorted({h["word"] for h in comp})))}) 
    if ph:
        deductions.append({"kind": "placeholder", "points": 40,
                           "why": "占位符残留：{}".format(ph[0]["why"])})
    if echoes:
        deductions.append({"kind": "prompt_echo", "points": 30,
                           "why": echoes[0]["why"]})
    if not len_ok:
        deductions.append({"kind": "length", "points": length_penalty(len_d),
                           "why": "字数 {} 不在 {}~{} 区间（偏离 {} 字）".format(
                               chars, len_d["lo"], len_d["hi"], abs(len_d["delta"]))})
    if not st_ok:
        deductions.append({"kind": "structure", "points": 25 * len(st_missing),
                           "why": "结构缺项：" + "、".join(st_missing)})
    if not tag_ok:
        deductions.append({"kind": "hashtags", "points": 8,
                           "why": "话题标签 {} 个，不符合 {}~{} 的口径".format(
                               len(hashtags), tlo, thi)})
    if not emoji_ok:
        deductions.append({"kind": "emoji", "points": 5,
                           "why": "emoji 策略不符（该平台：{}）".format(pf["emoji"])})
    score = max(0, 100 - sum(d["points"] for d in deductions))

    return {
        "platform": platform,
        "name": pf["name"],
        "title": title,
        "body": body,
        "ending": ending,
        "hashtags": hashtags,
        "opening_type": detect_opening_type(first_sentence(body), platform),
        "stats": {
            "chars": chars,
            "char_range": [len_d["lo"], len_d["hi"]],
            "paras": len(paras),
            "para_range": [cl, ch_],
            "avg_para": avg_para,
            "para_chars_range": [plo, phi],
            "tags": len(hashtags),
            "tag_range": [tlo, thi],
            "opening": first_sentence(body),
            "ending_sentence": last_sentence(ending or body),
        },
        "spec": {
            "chars": list(pf["chars"]), "para_chars": list(pf["para_chars"]),
            "para_count": [cl, ch_], "opening": pf["opening"], "ending": pf["ending"],
            "hashtags": [tlo, thi], "emoji": pf["emoji"],
            "title_style": pf["title_style"], "tone": pf["tone"],
        },
        "gates": {
            "compliance": {"ok": not comp, "hits": comp, "exempted": comp_exempt},
            "placeholder": {"ok": not ph, "hits": ph},
            "prompt_echo": {"ok": not echoes, "hits": echoes},
            "length": dict(len_d, ok=len_ok),
            "structure": {"ok": st_ok, "missing": st_missing, "has_cta": cta},
            "hashtags": {"ok": tag_ok},
            "emoji": {"ok": emoji_ok, "used": emoji_used},
            "para_style": {"ok": para_ok and pcount_ok,
                           "para_ok": para_ok, "count_ok": pcount_ok},
        },
        "score": score,
        "deductions": deductions,
        "raw_notes": {
            "kept": [str(x) for x in ((raw or {}).get("kept") or [])],
            "cut": [str(x) for x in ((raw or {}).get("cut") or [])],
            "notes": str((raw or {}).get("notes") or "").strip(),
        },
    }


def item_gate_failed(it):
    """这一篇是否被硬闸门拦下（决定退出码）。

    口径：合规 / 占位符 / 照抄示例 / 字数区间 / 结构完整性 —— 五项任一不达标即拦截。
    标签数量、emoji 策略、段落风格只扣分不拦截（它们是风格问题，
    不是「发出去会出事」的问题），但一样会标红显示。
    """
    g = it["gates"]
    return (not g["compliance"]["ok"] or not g["placeholder"]["ok"]
            or not g["prompt_echo"]["ok"] or not g["length"]["ok"]
            or not g["structure"]["ok"])


# ---------------------------------------------------------------------------
# 提示词
#
# 【铁律】提示词里**不许出现任何一句可直接复制的完整中文句子**作为示例。
# 事故复盘见上文「闸门三」注释。举例只用描述性语言 + 登记在 PROMPT_SAMPLES
# 里的跨主题示例（主题是电动车充电桩，与三剪客真实业务明显不搭）。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是三剪客团队的多平台内容编辑，服务公众号 / 小红书 / 抖音 / 知乎 / 头条五个平台。\n"
    "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
    "你写的每一篇都必须能被真实发布：\n"
    "  · 不编造原稿里没有的数据、案例、背书\n"
    "  · 不使用广告法违禁词（最/第一/国家级/100%/根治/绝对/保证 等一律不许出现）\n"
    "  · 不留任何占位符（不许出现 大括号、待填、XXX、此处省略 这类编稿脚手架）\n"
    "  · 同一批改写里，不同平台的开场句与结尾句不许雷同——换皮等于没改写"
)


def _spec_block(platform):
    """把平台规格表里的一行渲染成提示词片段。**改规格只改 PLATFORMS。**"""
    pf = PLATFORMS[platform]
    cl, ch_ = pf["para_count"]
    plo, phi = pf["para_chars"]
    tlo, thi = pf["hashtags"]
    lo, hi = pf["chars"]
    return """平台：{name}（{label}）
- 正文目标字数：**写 {target} 字左右**。合格区间是 {lo}~{hi} 字（按非空白字符算，
  中文标点算一个）。**低于 {lo} 字或高于 {hi} 字都算不合格**——先保证不低于下限。
- 段数：{cl}~{ch} 段；单段字数：{plo}~{phi} 字
- 开场方式：{opening}
- 结尾引导：{ending}
- 结尾必须出现这类动作词（本地会检查）：{cta_help}
- 话题标签：{tlo}~{thi} 个{tag_note}
- emoji 策略：{emoji}
- 标题风格：{title_style}
- 语感口径：{tone}
- 本平台硬性要求：
{must}""".format(
        name=pf["name"], label=pf["label"], lo=lo, hi=hi, target=target_chars(platform),
        cl=cl, ch=ch_, plo=plo, phi=phi, opening=pf["opening"], ending=pf["ending"],
        tlo=tlo, thi=thi, emoji=pf["emoji"], title_style=pf["title_style"],
        tone=pf["tone"], cta_help=CTA_HELP.get(platform, "关注 / 评论"),
        tag_note=("（放在正文最后，每个标签前加 #）" if thi else "（该平台不用话题标签，"
                  "hashtags 返回空数组）"),
        must="\n".join("    {}. {}".format(i, m) for i, m in enumerate(pf["must"], 1)),
    )


def build_rewrite_prompt(source, platform, brief=None, evidence=None, others=None):
    """构造单个平台的改写提示词。

    others：本批还要改的平台名列表 —— 用来说明「你要跟谁拉开差异」。
    把这件事明确写进提示词，是「平台差异真的分出来」的第一道保障；
    第二道保障是本地 cross_platform_check。
    """
    pf = PLATFORMS[platform]
    extra = []
    if brief:
        extra.append("改写要求（来自作者）：{}".format(brief))
    if evidence:
        extra.append("可以使用的真实素材（只能用这些，不许自己编）：{}".format(evidence))
    else:
        extra.append("没有提供额外真实素材：**不许编造**数字、销量、机构名、专家背书，"
                     "需要举例时用原稿里已有的事实")
    other_note = ""
    if others:
        names = "、".join(PLATFORMS[k]["name"] for k in others if k != platform)
        if names:
            other_note = (
                "\n同一批还要改出：{}。三条硬约束：\n"
                "   a) 你的开场句、结尾句必须与它们**明显不同**，不许用通用模板句；\n"
                "   b) **不许整句搬运原稿的措辞**——原稿里的一句话，在你这一篇里要么换一种说法，\n"
                "      要么换一个切入角度，要么删掉。逐句复述原稿是最常见的失败模式；\n"
                "   c) **信息的出场顺序也可以不一样**：原稿从 A 讲到 B 讲到 C，\n"
                "      你可以从 C 起头再回补 A。顺序变了，结构才是真的变了。\n"
                "  （本地会用字符二元组相似度两两比对正文，太像会被判「换皮」并拦下。）\n"
                .format(names))

    sample_note = "\n".join("- {}".format(s) for s in PROMPT_SAMPLES[:3])

    return """把下面这份原稿改写成**{pname}**规格的成品。不是换词，是**按平台重新组织结构**。

=== 原稿开始 ===
{source}
=== 原稿结束 ===

{extra}

{spec}

改写纪律（很重要，逐条照做）：
1. **结构要重来**：按上面的开场方式重新起头，按上面的段落长度重新切段，
   按上面的结尾引导重新收尾。原稿的段落划分基本不能沿用。
2. **不同平台不许雷同**：开场句与结尾句必须是这一篇独有的表达，不要写成通用模板句。
{other_note}
3. **不许留脚手架**：产出里不能出现大括号、待填、XXX、此处省略 这类占位内容。
   所有该具体的地方都要写具体。
4. **不许编事实**：原稿里没有的数字、案例、机构、头衔一个都不许加。
   需要加强说服力时，用原稿已有的事实换一个角度讲。
5. **字数要落在区间里**：这是一个硬指标。写完自己数一遍非空白字符数。
   不够就补充原稿里已有的信息细节（**不是灌水、不是重复表达**），超了就删掉冗余修饰。
   两条红线：**绝不能低于下限**；也不要顶到上限（贴着上限写很容易写超）。
   目标是规格里给的那个「目标字数」。

关于「什么样的产出算好」，只用形态描述，不许照抄任何示例文字：
- 开场要让人有理由继续读下去（疑问 / 结论前置 / 处境共鸣，按上面的开场方式选）
- 正文每一段只承担一个信息点，段与段之间有推进
- 结尾要落到一个具体动作上，不是「以上就是全部内容」这种无信息量收尾
- 下面这几句是**别的主题**（电动车充电桩）的示例，只用来说明形态，**绝对不要照抄**：
{samples}

只输出一个 JSON 对象，结构如下（不要输出别的任何东西）：
{{"title":"{pname}的标题","body":"正文全文，段落之间用 \\n 分隔","ending":"结尾引导原文","hashtags":["标签1","标签2"],"opening_type":"你用的开场方式（一句话）","kept":["保留了原稿的哪些关键信息"],"cut":["砍掉了原稿的哪些内容，为什么"]}}""".format(
        pname=pf["name"], source=(source or "").strip(),
        extra="\n".join(extra) + "\n", spec=_spec_block(platform),
        other_note=other_note, samples=sample_note,
    )


def build_plan_prompt(source, platforms, brief=None):
    """构造改写方案提示词（不改写，只出方案）。"""
    blocks = "\n\n".join(_spec_block(k) for k in platforms)
    extra = "改写要求（来自作者）：{}".format(brief) if brief else ""
    names = "、".join(PLATFORMS[k]["name"] for k in platforms)
    return """先读原稿，然后给出「一稿改成 {names}」的**改写方案**。这一步不要写出成品正文，
只出方案——落笔之前先想清楚每个平台保留什么、砍什么、结构怎么动。

=== 原稿开始 ===
{source}
=== 原稿结束 ===

{extra}

各平台规格如下（方案必须贴着这些规格给）：

{blocks}

输出要求：
1. `keep`：原稿里**必须保留**的信息（具体到信息点，不要写「核心观点」这种空话）
2. `cut`：可以砍掉的内容，并说明为什么在跨平台时它是负担
3. `needs`：原稿缺什么（缺例子 / 缺数据 / 缺一个具体场景），如实说，不要编
4. 每个平台一份：`strategy`（这个平台该怎么改结构，2~3 句）、`keep`、`cut`、
   `opening_plan`（开场从原稿的哪一部分切入）、`ending_plan`（结尾落到什么动作上）、
   `est_chars`（预估字数）
5. `risks`：这次改写最可能踩的坑（比如某平台字数区间很窄、原稿素材不够撑长文）

只输出一个 JSON 对象，结构如下（不要输出别的任何东西）：
{{"source_summary":"原稿一句话概括","keep":["..."],"cut":["..."],"needs":["..."],
"platforms":{{"{first}":{{"strategy":"...","keep":["..."],"cut":["..."],"opening_plan":"...","ending_plan":"...","est_chars":0}}}},"risks":["..."]}}""".format(
        source=(source or "").strip(), extra=extra, blocks=blocks,
        names=names, first=(platforms[0] if platforms else "wechat"),
    )


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "!! " + s
    return "\x1b[31m{}\x1b[0m".format(s)


def render_platforms_md():
    out = ["# 支持的平台与规格", ""]
    out.append("> 这张表就是 `scripts/run.py` 里的 `PLATFORMS` 常量，"
               "命令输出与提示词、闸门用的都是它。**改规格只改表，不改逻辑。**")
    out.append("")
    out.append("| key | 平台 | 正文区间 | 目标字数 | 段数 | 单段字数 | 标签 | emoji | 开场 | 结尾 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for k, pf in PLATFORMS.items():
        out.append("| `{}` | {} | {}~{} | {} | {}~{} | {}~{} | {}~{} | {} | {} | {} |".format(
            k, pf["name"], pf["chars"][0], pf["chars"][1], target_chars(k),
            pf["para_count"][0], pf["para_count"][1],
            pf["para_chars"][0], pf["para_chars"][1],
            pf["hashtags"][0], pf["hashtags"][1],
            "可" if pf["emoji"].startswith("可以") else "否",
            pf["opening"][:26] + "…", pf["ending"][:26] + "…"))
    out.append("")
    out.append("目标字数 = 区间下限 + {:.0%} × 区间长度（提示词里给模型的就是这个数，"
               "不是上限——给上限模型就会顶到上限然后写超）。".format(TARGET_POS))
    out.append("")
    for k, pf in PLATFORMS.items():
        out.append("## {}（`{}`）".format(pf["name"], k))
        out.append("")
        out.append("- **标题风格**：{}".format(pf["title_style"]))
        out.append("- **语感口径**：{}".format(pf["tone"]))
        out.append("- **开场方式**：{}".format(pf["opening"]))
        out.append("- **结尾引导**：{}".format(pf["ending"]))
        out.append("- **emoji 策略**：{}".format(pf["emoji"]))
        out.append("- **本平台硬性要求**：")
        for i, m in enumerate(pf["must"], 1):
            out.append("    {}. {}".format(i, m))
        redlines = PLATFORM_REDLINES.get(k) or []
        if redlines:
            out.append("- **本平台特有红线**（本地闸门会扫）：")
            for rx, lvl, why in redlines:
                out.append("    - [{}风险] {}".format(lvl, why))
        out.append("")
    return "\n".join(out)


def render_plan_md(plan, source, model, usage, elapsed):
    out = ["# 一稿多平台改写方案", ""]
    out.append("- 原稿：{} 字 / {} 段".format(count_chars(source), len(split_paras(source))))
    out.append("- 模型：`{}`　端点：`POST /api/v1/chat/completions`".format(model))
    if usage:
        out.append("- token 用量：prompt={} completion={} total={}".format(
            usage.get("prompt_tokens", "-"), usage.get("completion_tokens", "-"),
            usage.get("total_tokens", "-")))
    out.append("- 耗时：{:.1f}s".format(elapsed))
    out.append("")
    if plan.get("source_summary"):
        out.append("**原稿概括**：{}".format(plan["source_summary"]))
        out.append("")

    def bullets(title, items, empty="（无）"):
        out.append("## {}".format(title))
        out.append("")
        if items:
            for x in items:
                out.append("- {}".format(x))
        else:
            out.append(empty)
        out.append("")

    bullets("必须保留", plan.get("keep"))
    bullets("可以砍掉", plan.get("cut"))
    bullets("原稿缺什么（如实列出，不补编）", plan.get("needs"))

    out.append("## 各平台怎么改")
    out.append("")
    out.append("| 平台 | 预估字数 | 开场切入 | 结尾落点 |")
    out.append("|---|---|---|---|")
    for k, v in (plan.get("platforms") or {}).items():
        if not isinstance(v, dict):
            continue
        name = PLATFORMS.get(k, {}).get("name", k)
        out.append("| {} | {} | {} | {} |".format(
            name, v.get("est_chars", "-"),
            str(v.get("opening_plan") or "")[:30],
            str(v.get("ending_plan") or "")[:30]))
    out.append("")
    for k, v in (plan.get("platforms") or {}).items():
        if not isinstance(v, dict):
            continue
        name = PLATFORMS.get(k, {}).get("name", k)
        out.append("### {}".format(name))
        out.append("")
        if v.get("strategy"):
            out.append("- **改法**：{}".format(v["strategy"]))
        if v.get("opening_plan"):
            out.append("- **开场切入**：{}".format(v["opening_plan"]))
        if v.get("ending_plan"):
            out.append("- **结尾落点**：{}".format(v["ending_plan"]))
        if v.get("keep"):
            out.append("- **保留**：{}".format("；".join(str(x) for x in v["keep"])))
        if v.get("cut"):
            out.append("- **砍掉**：{}".format("；".join(str(x) for x in v["cut"])))
        if v.get("est_chars"):
            out.append("- **预估字数**：{}".format(v["est_chars"]))
        out.append("")
    bullets("这次最可能踩的坑", plan.get("risks"))
    out.append("下一步：`python3 run.py rewrite --file <原稿> --all`")
    return "\n".join(out)


def render_rewrite_md(result):
    src = result["source"]
    out = ["# 一稿多平台改写", ""]
    out.append("- 原稿：{} 字 / {} 段　开场：{}".format(
        src["chars"], src["paras"], src["opening"][:36]))
    out.append("- 模型：`{}`　端点：`POST /api/v1/chat/completions`".format(result["model"]))
    u = result.get("usage_totals") or {}
    if u:
        out.append("- token 合计：prompt={} completion={} total={}（{} 次调用）".format(
            u.get("prompt_tokens", "-"), u.get("completion_tokens", "-"),
            u.get("total_tokens", "-"), u.get("calls", "-")))
    out.append("- 耗时：{:.1f}s".format(result["elapsed"]))
    out.append("")

    items = result["platforms"]
    bad = [k for k, it in items.items() if item_gate_failed(it)]
    xp = result.get("cross_platform") or {}
    if bad or xp.get("flagged"):
        out.append("> !! 本地自检：{} 个平台被硬闸门拦下{}。命中项已标红，"
                   "**不可直接发布**，修完再跑一次。".format(
                       len(bad),
                       "；另有 {} 对平台疑似换皮".format(len(xp["flagged"]))
                       if xp.get("flagged") else ""))
    else:
        out.append("> OK 本地自检：{} 个平台全部通过合规 / 占位符 / 照抄示例 / "
                   "字数区间 / 结构完整性五项硬闸门{}。".format(
                       len(items), "，且平台间差异达标" if xp else ""))
    out.append("")

    out.append("## 结构对比（本地计算，不花 token）")
    out.append("")
    out.append("| 平台 | 字数（区间） | 段数（区间） | 均段长 | 标签 | 开场类型 | 结尾有行动指令 | 得分 |")
    out.append("|---|---|---|---|---|---|---|---|")
    for k, it in items.items():
        s = it["stats"]
        g = it["gates"]
        out.append("| {} | {}{} （{}~{}） | {}{} | {} | {} | {} | {} | **{}** |".format(
            it["name"],
            s["chars"], "" if g["length"]["ok"] else " !!",
            s["char_range"][0], s["char_range"][1],
            s["paras"], "" if g["para_style"]["count_ok"] else " !!",
            s["avg_para"], s["tags"], it["opening_type"],
            "有" if g["structure"]["has_cta"] else "无 !!",
            it["score"]))
    out.append("")

    if xp.get("pairs"):
        out.append("## 跨平台换皮检测（本地，二元组 Jaccard）")
        out.append("")
        out.append("阈值 {}（两篇正文都 ≥ {} 字才比较）。数值越高说明两篇越像。".format(
            xp["threshold"], xp["min_chars"]))
        out.append("")
        out.append("| A | B | 相似度 | 判定 |")
        out.append("|---|---|---|---|")
        for p in xp["pairs"]:
            out.append("| {} | {} | {} | {} |".format(
                p["a_name"], p["b_name"], p["sim"],
                "!! 疑似换皮" if p["flagged"] else "达标"))
        out.append("")

    for k, it in items.items():
        out.append("## {}{}".format(it["name"], "" if not item_gate_failed(it) else "  !!被拦下"))
        out.append("")
        head = "**标题**：{}".format(it["title"])
        if not it["gates"]["compliance"]["ok"] or not it["gates"]["prompt_echo"]["ok"] \
                or not it["gates"]["placeholder"]["ok"]:
            head = _red(head)
        out.append(head)
        out.append("")
        out.append(it["body"])
        out.append("")
        if it["ending"]:
            out.append("**结尾引导**：{}".format(it["ending"]))
            out.append("")
        if it["hashtags"]:
            out.append("**话题标签**（{} 个）：{}".format(
                len(it["hashtags"]), " ".join("#" + t for t in it["hashtags"])))
            out.append("")
        out.append("- 字数 {}（区间 {}~{}）　段数 {}　均段长 {}　开场类型：{}".format(
            it["stats"]["chars"], it["stats"]["char_range"][0], it["stats"]["char_range"][1],
            it["stats"]["paras"], it["stats"]["avg_para"], it["opening_type"]))
        if it["raw_notes"].get("notes"):
            out.append("- 改写说明：{}".format(it["raw_notes"]["notes"]))
        if it["raw_notes"].get("kept"):
            out.append("- 保留：{}".format("；".join(it["raw_notes"]["kept"])))
        if it["raw_notes"].get("cut"):
            out.append("- 砍掉：{}".format("；".join(it["raw_notes"]["cut"])))
        for d in it["deductions"]:
            out.append("   - !! 扣 {} 分（{}）：{}".format(d["points"], d["kind"], d["why"]))
        for ex in it["gates"]["compliance"].get("exempted") or []:
            out.append("   - 本地放过 1 处疑似绝对化用语「{}」（{}）：…{}…".format(
                ex["word"], "说数据极值的语境", ex["context"]))
        out.append("")
    return "\n".join(out)


def render_diff_md(diff):
    src = diff["source"]
    out = ["# 结构性对比（原稿 vs 各平台改写）", ""]
    out.append("> 纯本地计算，**不调模型、不花一分钱**。数据来自 "
               "`rewrite --json --out` 的结果文件。")
    out.append("")
    out.append("原稿：{} 字 / {} 段；开场「{}」；结尾「{}」".format(
        src["chars"], src["paras"], src["opening"][:40], src["ending"][:40]))
    out.append("")
    out.append("| 平台 | 字数 | vs 原稿 | 段数 | vs 原稿 | 均段长 | 开场类型 | 开场真的换了吗 | 结尾引导 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for d in diff["platforms"]:
        out.append("| {} | {} | {:+d} | {} | {:+d} | {} | {} | {} | {} |".format(
            d["name"], d["chars"], d["chars_delta"], d["paras"], d["paras_delta"],
            d["avg_para"], d["opening_type"],
            "OK 换了" if d["opening_changed"] else "!! 与原稿雷同",
            d["ending_sentence"][:24]))
    out.append("")
    out.append("## 逐平台细节")
    out.append("")
    for d in diff["platforms"]:
        out.append("### {}".format(d["name"]))
        out.append("")
        out.append("- 字数：{}（原稿 {}，{:+d}）；目标区间 {}~{} → {}".format(
            d["chars"], src["chars"], d["chars_delta"],
            d["char_range"][0], d["char_range"][1],
            "达标" if d["length_ok"] else "不达标"))
        out.append("- 段数：{}（原稿 {}，{:+d}）；单段字数 {}~{}".format(
            d["paras"], src["paras"], d["paras_delta"], d["min_para"], d["max_para"]))
        out.append("- 开场（{}）：{}".format(d["opening_type"], d["opening"]))
        out.append("- 与原稿开场的相似度：{}".format(d["opening_sim"]))
        out.append("- 结尾引导：{}（行动指令：{}）".format(
            d["ending_sentence"], "有" if d["has_cta"] else "无"))
        out.append("- 与原稿的整体相似度：{}（越低说明改得越透）".format(d["body_sim"]))
        out.append("")
    if diff.get("cross_platform"):
        xp = diff["cross_platform"]
        out.append("## 平台之间像不像")
        out.append("")
        for p in xp["pairs"]:
            out.append("- {} ↔ {}：{} {}".format(
                p["a_name"], p["b_name"], p["sim"],
                "!! 疑似换皮" if p["flagged"] else ""))
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def _strip_bom(s):
    """去掉 UTF-8 BOM。

    Windows 上 `Out-File -Encoding utf8` / 记事本另存为 UTF-8 都会写 BOM（\\ufeff），
    带着它原稿的第一个字会被读成不可见字符，字数统计与相似度都会偏。
    """
    return s.lstrip("\ufeff") if s else s


def _read_source(a):
    """读原稿：--file 或 --text，两者都给时以 --text 为准。"""
    if getattr(a, "text", None):
        return _strip_bom(a.text)
    if getattr(a, "file", None):
        p = Path(a.file)
        if not p.is_file():
            raise UsageError("找不到原稿文件：{}".format(p))
        return _strip_bom(p.read_text(encoding="utf-8", errors="replace"))
    raise UsageError("请给原稿：--file 原稿.md 或 --text \"原稿正文\"")


def _source_meta(source):
    paras = split_paras(source)
    return {
        "chars": count_chars(source),
        "paras": len(paras),
        "opening": first_sentence(source),
        "ending": last_sentence(source),
    }


def _pick_platforms(a):
    """--platform 可重复；--all 全跑。两者都给以 --all 为准。"""
    if getattr(a, "all", False):
        return list(ALL_PLATFORMS)
    picked = getattr(a, "platform", None) or []
    if isinstance(picked, str):
        picked = [picked]
    out = []
    for p in picked:
        if p not in PLATFORMS:
            raise UsageError("不支持的平台：{}（可选：{}）".format(
                p, "、".join(PLATFORM_CHOICES)))
        if p not in out:
            out.append(p)
    if not out:
        raise UsageError(
            "请用 --platform <key> 指定平台（可重复多次），或用 --all 全跑。"
            "可选：{}".format("、".join(PLATFORM_CHOICES)))
    return out


def _sum_usage(usages):
    tot = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    for u in usages:
        if not u:
            continue
        tot["calls"] += 1
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if isinstance(u.get(k), int):
                tot[k] += u[k]
    return tot


def _emit(a, result, md_text, ok=True):
    """统一出口：`--json` 时补 ok 写**真 stdout**（同时落 `--out`），否则原样打人读文本。"""
    if a.json:
        body = _json_text(result, indent=2, ok=ok)
        if a.out:
            Path(a.out).write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 {}\n".format(a.out))
        _json_write(body)
        return
    if a.out:
        Path(a.out).write_text(md_text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    print(md_text)


def _gate_report(items, xplat=None):
    """把命中汇总到 stderr，并返回退出码。"""
    rc = EXIT_OK
    hit = {k: it for k, it in items.items() if item_gate_failed(it)}
    if hit:
        rc = EXIT_GATE
        sys.stderr.write("\n!! 有 {} 个平台被硬闸门拦下，不可直接发布：\n".format(len(hit)))
        for k, it in hit.items():
            g = it["gates"]
            reasons = []
            if not g["compliance"]["ok"]:
                reasons.append("合规：命中 " + "、".join(
                    "「{}」({}/{})".format(h["word"], h["level"], h["scope"])
                    for h in g["compliance"]["hits"]))
            if not g["placeholder"]["ok"]:
                reasons.append("占位符：" + "；".join(
                    h["why"] for h in g["placeholder"]["hits"]))
            if not g["prompt_echo"]["ok"]:
                reasons.append("照抄示例：" + "；".join(
                    h["why"] for h in g["prompt_echo"]["hits"]))
            if not g["length"]["ok"]:
                d = g["length"]
                reasons.append("字数 {} 不在 {}~{} 区间（偏离 {} 字）".format(
                    d["chars"], d["lo"], d["hi"], abs(d["delta"])))
            if not g["structure"]["ok"]:
                reasons.append("结构缺项：" + "、".join(g["structure"]["missing"]))
            sys.stderr.write("   [{}] {} ← {}\n".format(it["name"], it["title"][:30],
                                                        "；".join(reasons)))
    # 只扣分不拦截的项目也报一声，但不动退出码。
    # 硬闸门 = compliance / placeholder / prompt_echo / length / structure 五项；
    # 其余（hashtags / emoji）是风格问题，不构成「发出去会出事」。
    soft = [(it["name"], d) for it in items.values() for d in it["deductions"]
            if d["kind"] in ("hashtags", "emoji")]
    if soft:
        sys.stderr.write("\n提示：{} 项风格扣分（不拦截，但建议改）：\n".format(len(soft)))
        for name, d in soft:
            sys.stderr.write("   [{}] 扣 {} 分：{}\n".format(name, d["points"], d["why"]))
    if xplat and xplat.get("flagged"):
        rc = EXIT_GATE
        sys.stderr.write("\n!! 跨平台换皮：{} 对平台正文相似度 ≥ {}，"
                         "等于同一篇换了个开场：\n".format(
                             len(xplat["flagged"]), xplat["threshold"]))
        for p in xplat["flagged"]:
            sys.stderr.write("   {} ↔ {}：{}\n".format(p["a_name"], p["b_name"], p["sim"]))
    # 被豁免的疑似命中也要说一声，**不静默放过**
    ex = [(it["name"], e) for it in items.values()
          for e in (it["gates"]["compliance"].get("exempted") or [])]
    if ex:
        sys.stderr.write("\n提示：本地放过 {} 处疑似绝对化用语（判定为「在说数据极值」"
                         "而不是商品宣称）。这是启发式判断，请人工确认：\n".format(len(ex)))
        for name, e in ex:
            sys.stderr.write("   [{}]「{}」：…{}…\n".format(name, e["word"], e["context"]))
    return rc


def _run_platforms(a):
    if a.json:
        payload = {
            "chars_per_token_in": CHARS_PER_TOKEN_IN,
            "tokens_per_char_out": TOKENS_PER_CHAR_OUT,
            "target_pos": TARGET_POS,
            "note": "改规格只改 scripts/run.py 里的 PLATFORMS 常量，本命令直接读它",
            "target_chars": {k: target_chars(k) for k in PLATFORMS},
            "platforms": PLATFORMS,
            "redlines": {k: [{"pattern": p, "level": l, "why": w}
                             for p, l, w in v] for k, v in PLATFORM_REDLINES.items()},
        }
        _json_out(payload, a, indent=2)
        return EXIT_OK
    print(render_platforms_md())
    print("")
    print("话题标签 / emoji / 段数口径同样来自这张表；本地闸门按它校验。")
    return EXIT_OK


def _run_plan(a):
    source = _read_source(a)
    platforms = _pick_platforms(a)
    prompt = build_plan_prompt(source, platforms, a.brief)
    if a.dry_run:
        # --json 时 stdout 必须是单个完整 JSON，所以 dry-run 的回显也包成 JSON
        if a.json:
            _json_out({"dry_run": True, "system": SYSTEM_PROMPT,
                       "platforms": platforms, "user": prompt}, a, indent=2)
        else:
            print("=== system ===\n{}\n\n=== user ===\n{}".format(SYSTEM_PROMPT, prompt))
        return EXIT_OK
    sys.stderr.write("正在用 `{}` 出改写方案（{}）…\n".format(
        a.model, "、".join(PLATFORMS[k]["name"] for k in platforms)))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    plan = parse_first_json(content)
    if not isinstance(plan, dict):
        raise RewriteError("模型返回的改写方案不是 JSON 对象")
    result = {"model": a.model, "usage": usage, "elapsed": round(elapsed, 1),
              "source": _source_meta(source), "platforms_requested": platforms,
              "plan": plan}
    _emit(a, result, render_plan_md(plan, source, a.model, usage, elapsed))
    return EXIT_OK


def _run_rewrite(a):
    source = _read_source(a)
    platforms = _pick_platforms(a)
    price_in, price_out = a.price_in, a.price_out
    need_price = a.budget is not None
    if need_price and (price_in is None or price_out is None):
        sys.stderr.write(
            "配置错误：给了 --budget 就必须给单价，否则预算没有任何意义。\n"
            "  接口的 pricing 表实测不含文本大模型、models 列表也没有价格字段，\n"
            "  所以本包拒绝凭空编一个单价。请补 --price-in / --price-out"
            "（单位：点/百万 token）。\n")
        return _fail(EXIT_USAGE, "usage", "给了 --budget 就必须给单价（本包拒绝编造单价）")

    # 预估闸门：先算一遍，开局就知道会不会超预算
    est_in = sum(estimate_tokens_in(SYSTEM_PROMPT +
                                    build_rewrite_prompt(source, k, a.brief, a.evidence, platforms))
                 for k in platforms)
    est_out = sum(estimate_tokens_out(k) for k in platforms)
    est = compute_cost(est_in, est_out, price_in, price_out)
    if price_in is not None:
        sys.stderr.write("预估：约 {} ({} 个平台)\n".format(fmt_cost(est), len(platforms)))
    if a.budget is not None and est["points"] is not None and est["points"] > a.budget:
        sys.stderr.write("!! 预估成本 {} 点已超过 --budget {} 点，就地中止（还没花钱）。\n"
                         "   想继续就跑单平台，或调低 --max-tokens。\n".format(
                             est["points"], a.budget))
        return _fail(EXIT_BUDGET, "budget",
                     "预估成本 %s 点已超过 --budget %s 点，就地中止（还没花钱）"
                     % (est["points"], a.budget))

    items, usages = {}, []
    spent_tokens_in, spent_tokens_out = 0, 0
    dry_prompts = []
    t_all = time.time()
    for idx, k in enumerate(platforms, 1):
        pf = PLATFORMS[k]
        prompt = build_rewrite_prompt(source, k, a.brief, a.evidence, platforms)
        if a.dry_run:
            if a.json:
                # 逐平台的提示词先攒起来，最后一次性吐一个 JSON（不能吐多个 JSON 文档）
                dry_prompts.append({"platform": k, "name": pf["name"], "user": prompt})
            else:
                print("=== [{}] system ===\n{}\n\n=== [{}] user ===\n{}".format(
                    pf["name"], SYSTEM_PROMPT, pf["name"], prompt))
            continue
        sys.stderr.write("[{}/{}] 正在改写成 {}（目标 {}~{} 字）…\n".format(
            idx, len(platforms), pf["name"], pf["chars"][0], pf["chars"][1]))
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                              temperature=a.temperature, max_tokens=a.max_tokens,
                              key=a.key, json_mode=not a.no_json_mode)
        elapsed = time.time() - t0
        obj = parse_first_json(content)
        if not isinstance(obj, dict):
            raise RewriteError("{} 的返回不是 JSON 对象".format(pf["name"]))
        it = normalize_item(obj, k)
        it["usage"] = usage
        it["elapsed"] = round(elapsed, 1)
        it["gate_failed"] = item_gate_failed(it)
        items[k] = it
        usages.append(usage)
        spent_tokens_in += int(usage.get("prompt_tokens") or 0)
        spent_tokens_out += int(usage.get("completion_tokens") or 0)

        # 闸门六：成本上限。用**真实 usage** 累计，超了就停，不再往下买。
        if a.budget is not None and price_in is not None:
            spent = compute_cost(spent_tokens_in, spent_tokens_out, price_in, price_out)
            if spent["points"] is not None and spent["points"] > a.budget:
                sys.stderr.write(
                    "!! 已花 {} 点，超过 --budget {} 点，就地中止（已完成 {} 个平台，"
                    "结果仍会输出到 stderr 之外的标准输出）。\n".format(
                        spent["points"], a.budget, len(items)))
                result = _build_result(a, source, items, usages, time.time() - t_all,
                                       est, price_in, price_out)
                # 结果已经吐出来了，ok 要如实写 false；退出码仍是 5
                _emit(a, result, render_rewrite_md(result), ok=False)
                return _fail(EXIT_BUDGET, "budget",
                             "已花 %s 点超过 --budget %s 点，就地中止（已完成 %d 个平台）"
                             % (spent["points"], a.budget, len(items)))

    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "system": SYSTEM_PROMPT,
                       "prompts": dry_prompts}, a, indent=2)
        return EXIT_OK

    if not items:
        raise RewriteError("没有任何平台产出内容，检查一下模型名与 --max-tokens")

    result = _build_result(a, source, items, usages, time.time() - t_all,
                           est, price_in, price_out)
    _emit(a, result, render_rewrite_md(result))
    return _gate_report(items, result.get("cross_platform"))


def _build_result(a, source, items, usages, elapsed, est, price_in, price_out):
    tot = _sum_usage(usages)
    actual = compute_cost(tot.get("prompt_tokens"), tot.get("completion_tokens"),
                          price_in, price_out)
    return {
        "model": a.model,
        "chat_endpoint": CHAT_URL,
        "usage_totals": tot,
        "usage_per_platform": {k: it.get("usage") for k, it in items.items()},
        "elapsed": round(elapsed, 1),
        "source": _source_meta(source),
        "source_text": source,
        "platforms_requested": list(items.keys()),
        "cost_estimate": est,
        "cost_actual_tokens": actual,
        "cross_platform": cross_platform_check(items),
        "platforms": items,
    }


def read_result_file(p, what="结果文件"):
    """读一个本包生成的 JSON 结果文件。

    为什么要单独包一层：`parse_first_json` 的报错是「模型返回的不是合法 JSON」——
    那句话在**读文件**的场景下是错的（这里根本没有模型参与，是用户给错文件了）。
    报错文案指错方向，用户就会去查模型，白折腾一圈。所以这里换成人话。
    """
    p = Path(p)
    if not p.is_file():
        raise UsageError("找不到{}：{}（先用 rewrite --json --out 生成）".format(what, p))
    try:
        obj = parse_first_json(_strip_bom(p.read_text(encoding="utf-8", errors="replace")))
    except RewriteError:
        raise UsageError(
            "{}不是合法 JSON：{}。本命令要的是 `rewrite --json --out` 生成的结果文件，"
            "不是原稿本身。".format(what, p))
    if not isinstance(obj, dict):
        raise UsageError("{}的顶层不是 JSON 对象：{}".format(what, p))
    return obj


def _run_diff(a):
    """纯本地结构性对比：读 rewrite --json 的结果文件，不再花一分钱。"""
    obj = read_result_file(a.file)
    if not isinstance(obj.get("platforms"), dict):
        raise UsageError(
            "这个文件里没有 platforms 字段，不是 `rewrite --json --out` 的结果文件：{}"
            .format(a.file))
    src_text = obj.get("source_text") or ""
    if not src_text and obj.get("source"):
        src_text = obj["source"].get("text") or ""
    if not src_text:
        raise UsageError("结果文件里没带原稿正文（source_text），无法做对比。"
                           "请用本包 rewrite --json --out 生成的完整结果文件。")
    meta = _source_meta(src_text)
    src_open = first_sentence(src_text)
    src_body = count_chars(src_text)
    rows = []
    for k, it in obj["platforms"].items():
        if k not in PLATFORMS:
            continue
        g = it.get("gates") or {}
        body = it.get("body") or ""
        opening = first_sentence(body)
        paras = split_paras(body)
        lens = [count_chars(x) for x in paras] or [0]
        lg = g.get("length") or {}
        rng = [lg.get("lo"), lg.get("hi")]
        if rng[0] is None or rng[1] is None:
            rng = list(PLATFORMS[k]["chars"])
        rows.append({
            "platform": k, "name": PLATFORMS[k]["name"],
            "chars": count_chars(body),
            "chars_delta": count_chars(body) - src_body,
            "char_range": rng,
            "length_ok": bool(lg.get("ok")),
            "paras": len(paras),
            "paras_delta": len(paras) - meta["paras"],
            "min_para": min(lens), "max_para": max(lens),
            "avg_para": round(sum(lens) / float(len(lens)), 1),
            "opening": opening,
            "opening_type": detect_opening_type(opening, k),
            "opening_sim": round(_similarity(opening, src_open), 3),
            "opening_changed": _similarity(opening, src_open) < 0.6,
            "ending_sentence": last_sentence(it.get("ending") or body),
            "has_cta": has_cta(it.get("ending") or body),
            "body_sim": round(_similarity(body, src_text), 3),
        })
    if not rows:
        raise UsageError("结果文件里没有可识别的平台产出")
    diff = {"source": meta, "source_text": src_text, "platforms": rows,
            "cross_platform": obj.get("cross_platform") or
            cross_platform_check({k: v for k, v in obj["platforms"].items()
                                  if k in PLATFORMS})}
    if a.json:
        _json_out(diff, a, indent=2)
    else:
        print(render_diff_md(diff))
    if a.out:
        Path(a.out).write_text(
            (json.dumps(diff, ensure_ascii=False, indent=2) if a.json
             else render_diff_md(diff)) + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    return EXIT_OK


def _run_cost(a):
    """只算钱。不调模型（除非 --from-result 都没有时用 --models 只做展示）。"""
    if a.from_result:
        p = Path(a.from_result)
        obj = read_result_file(p)
        tot = obj.get("usage_totals") or {}
        rec = compute_cost(tot.get("prompt_tokens") or 0,
                           tot.get("completion_tokens") or 0,
                           a.price_in, a.price_out)
        rec["source"] = "真实调用记录（不是估算）"
        rec["file"] = str(p)
        rec["calls"] = tot.get("calls")
        rec["per_platform"] = {
            k: (v or {}).get("usage") for k, v in (obj.get("platforms") or {}).items()}
        rec_rc = EXIT_OK if rec["points"] is not None or not a.budget else _fail(
            EXIT_USAGE, "usage", "给了 --budget 却没给单价，无法判断是否超预算")
        if a.json:
            _json_out(rec, a, indent=2, ok=not rec_rc)
        else:
            print("# 成本核算（读真实调用记录）\n")
            print("- 文件：{}".format(p))
            print("- 调用次数：{}".format(rec["calls"]))
            print("- token：prompt={} completion={} total={}".format(
                tot.get("prompt_tokens", "-"), tot.get("completion_tokens", "-"),
                tot.get("total_tokens", "-")))
            print("- {}".format(fmt_cost(rec)))
            for k, u in rec["per_platform"].items():
                if u:
                    print("    {}: prompt={} completion={}".format(
                        PLATFORMS.get(k, {}).get("name", k),
                        u.get("prompt_tokens", "-"), u.get("completion_tokens", "-")))
            for n in rec["notes"]:
                print("- 注：{}".format(n))
        return rec_rc

    source = _read_source(a)
    platforms = _pick_platforms(a)
    per_in, per_out, rows = [], [], []
    for k in platforms:
        tin = estimate_tokens_in(SYSTEM_PROMPT + build_rewrite_prompt(source, k))
        tout = estimate_tokens_out(k)
        per_in.append(tin)
        per_out.append(tout)
        rows.append({"platform": k, "name": PLATFORMS[k]["name"],
                     "chars_target": list(PLATFORMS[k]["chars"]),
                     "tokens_in": tin, "tokens_out": tout})
    tot_in, tot_out = sum(per_in), sum(per_out)
    rec = compute_cost(tot_in, tot_out, a.price_in, a.price_out)
    rec["source"] = "本地估算（输入按 %.2f 字/token、输出按 %.3f token/字标定，不是账单）" % (
        CHARS_PER_TOKEN_IN, TOKENS_PER_CHAR_OUT)
    rec["source_chars"] = count_chars(source)
    rec["platforms"] = rows
    if a.budget is not None:
        if rec["points"] is None:
            sys.stderr.write("!! 给了 --budget 但没给单价，无法判断是否超预算。\n")
            usage_rc = _fail(EXIT_USAGE, "usage", "给了 --budget 却没给单价，无法判断是否超预算")
        else:
            usage_rc = 0
        rec["budget"] = a.budget
        rec["over_budget"] = rec["points"] is not None and rec["points"] > a.budget
    else:
        usage_rc = 0
    if a.json:
        _json_out(rec, a, indent=2, ok=not usage_rc)
    else:
        print("# 成本预估\n")
        print("- 原稿：{} 字".format(rec["source_chars"]))
        print("- 平台：{}".format("、".join(r["name"] for r in rows)))
        print("- 标定（实测）：输入 1 个原始字符 ≈ {:.3f} token；输出 1 个原始字符 ≈ {} token".format(
            1.0 / CHARS_PER_TOKEN_IN, TOKENS_PER_CHAR_OUT))
        print("")
        print("| 平台 | 目标字数 | 预估输入 token | 预估输出 token |")
        print("|---|---|---|---|")
        for r in rows:
            print("| {} | {}~{} | {} | {} |".format(
                r["name"], r["chars_target"][0], r["chars_target"][1],
                r["tokens_in"], r["tokens_out"]))
        print("| **合计** |  | **{}** | **{}** |".format(tot_in, tot_out))
        print("")
        print("- {}".format(fmt_cost(rec)))
        for n in rec["notes"]:
            print("- 注：{}".format(n))
        if a.budget is not None:
            print("- 预算 {} 点：{}".format(
                a.budget, "超了" if rec["over_budget"] else "在预算内"))
    return usage_rc


def _run_models(a):
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
        print("  {:<28} {:<8} call_type={}  {:<22} {}".format(
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            m.get("call_type"), str(m.get("vendor_name") or "-"),
            str(m.get("model_name") or "")[:26]))
    print("")
    print("提示：模型名会变，以本命令现查为准，别写死在脚本里。")
    print("      `{}` 实测可用（路由到 deepseek-flash 一线），但它**不在**上面这份列表里，".format(
        DEFAULT_MODEL))
    print("      所以「列表里没有」不等于「不能用」。")
    print("      实测本列表里也没有任何价格字段；算钱请用 cost --price-in/--price-out。")
    print("用法：run.py rewrite --file draft.md --all --model <model_code>")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

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

# 退出码 → 失败类别（与本包 EXIT_* 常量一致）
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
    """把 JSON 文本写到**真 stdout** 并记账。"""
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
    于是文档里常见的 `run.py diff --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_model_opts(p):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 {}（实测可用；用 `run.py models` 现查在架模型）".format(
                       DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens",
                   help="最大输出 token，默认 4096（公众号长文建议不低于 4096）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--out", help="把结果写到这个文件")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_source_opts(p, need_platform=True):
    p.add_argument("--file", help="原稿文件（.md / .txt）")
    p.add_argument("--text", help="直接给原稿正文（与 --file 二选一，同时给以 --text 为准）")
    if need_platform:
        p.add_argument("--platform", action="append", choices=PLATFORM_CHOICES,
                       help="目标平台，可重复多次：--platform wechat --platform douyin")
        p.add_argument("--all", action="store_true", help="全平台都跑（{} 个）".format(
            len(ALL_PLATFORMS)))


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
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 一稿多平台改写（走 api.a7w.cn 的 OpenAI 兼容大模型端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("platforms", help="列出支持的平台与规格（零网络，不花钱）")
    _add_json(p)
    p.set_defaults(func=_run_platforms)

    p = sub.add_parser("plan", help="读原稿 → 出改写方案（各平台怎么改、保留什么、砍什么）")
    _add_source_opts(p)
    p.add_argument("--brief", help="改写要求（作者口述的意图）")
    _add_model_opts(p)
    p.set_defaults(func=_run_plan)

    p = sub.add_parser("rewrite", help="按平台改写（--platform 单个 / --all 全跑）")
    _add_source_opts(p)
    p.add_argument("--brief", help="改写要求（作者口述的意图）")
    p.add_argument("--evidence", help="可以使用的真实素材（没写就不许编数字）")
    _add_cost_opts(p)
    _add_model_opts(p)
    p.set_defaults(func=_run_rewrite)

    p = sub.add_parser("diff", help="结构性对比：原稿 vs 各平台改写（纯本地，不花钱）")
    p.add_argument("--file", required=True, help="rewrite --json --out 的结果文件")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_diff)

    p = sub.add_parser("cost", help="只算钱（token 估算 / 按单价折算 / 读真实调用记录）")
    _add_source_opts(p)
    p.add_argument("--from-result", dest="from_result",
                   help="读 rewrite --json --out 的结果文件，用**真实 token 数**算钱")
    _add_cost_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）")
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
