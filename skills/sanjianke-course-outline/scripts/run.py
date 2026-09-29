#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 课程生产线（sanjianke-course-outline）。

给一个主题和受众水平 → 大纲 → 逐节讲义 → 习题与解析。

子命令
    plan    出课程大纲（章节 / 小节 / 学习目标 / 时长）
    lesson  按大纲逐节写讲义（每节 1500~3000 字）
    quiz    按大纲逐节出习题 + 答案 + 解析（难度分层）
    all     跑完整套（大纲 → 讲义 → 习题），**断点续跑**
    cost    只算钱，一次调用都不发
    models  列出 api.a7w.cn 当前在架的模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）
    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py plan --topic "零基础短视频剪辑" --key sk-xxxx
    export A7W_API_KEY=sk-xxxx      # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

五道本地硬闸门（都是**拦截**：标红 + stderr 汇总 + 退出码非 0，不是"提示一下"）
    1. 合规         广告法违禁词；教育类另有「保过 / 包学会 / 提分保证 / 最」等
    2. 占位符残留   产出里不许有 `{}`、`[填空]`、`XXX`、`待补充`
    3. prompt_echo  提示词里的示例登记在 PROMPT_SAMPLES，产出若与之去标点后相等、
                    或字符二元组 Jaccard ≥ 0.75 → 拦截。**模型会照抄示例，哪怕标着"这是错的"**
    4. 结构校验     plan 必须真有大纲结构（章节数、每节有学习目标），缺项标红
    5. 成本上限     `--budget` 超了停

设计取舍
    · 闸门判定全部在本地做确定性判定，不采信模型自评（"我检查过了"不算数）。
    · 讲义字数、习题分层都是**产出侧**约束：模型少给还是多给都会被如实报出来，
      超出的部分不偷偷截断，让用户自己决定删哪句。
    · 成本是**估算**：网关不公布逐模型单价，默认按 0.02 元/千 token 折算，
      可用 --yuan-per-ktok 覆盖。文档里明确写了这是估算口径，不是账单。
"""

import argparse
import io
import json
import os
import re
import sys
import traceback
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402  ← 共用零依赖客户端；**逐字节等于规范版，本包不改它**

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

STATE_NAME = "course-outline-state.json"
LESSON_EXT = ".md"

# ---------------------------------------------------------------------------
# 受众水平口径（决定讲义的深度与前置假设）
# ---------------------------------------------------------------------------

LEVELS = {
    "zero": {
        "name": "零基础",
        "tone": "读者完全没接触过这个领域。每个术语第一次出现必须用一句大白话解释；"
                "多用生活化类比；不假设任何工具或背景知识；步骤要能照着做",
        "ratio": "概念 40% / 演示 45% / 练习 15%",
    },
    "basic": {
        "name": "入门",
        "tone": "读者懂最基础的概念、动手做过一两次但不成体系。可以跳过名词解释，"
                "重点讲清「为什么这么做」和常见错误",
        "ratio": "概念 25% / 演示 50% / 练习 25%",
    },
    "advanced": {
        "name": "进阶",
        "tone": "读者已经能独立完成常规任务。不解释基础概念，直接讲原理、边界条件、"
                "性能与成本取舍、以及别人踩过的坑",
        "ratio": "概念 20% / 演示 40% / 练习 40%",
    },
}
LEVEL_CHOICES = list(LEVELS.keys())

# 习题难度分层：三档固定，每档都有明确的能力指向
QUIZ_TIERS = (
    ("basic", "基础", "能复述、能识别、能照着做"),
    ("applied", "应用", "能在新场景里用出来、能改参数"),
    ("advanced", "进阶", "能判断取舍、能排错、能迁移到没讲过的情形"),
)
TIER_KEYS = [t[0] for t in QUIZ_TIERS]
QUESTION_TYPES = ("choice", "judge", "short", "case")
QUESTION_TYPE_LABEL = {
    "choice": "单选题",
    "judge": "判断题",
    "short": "简答题",
    "case": "案例分析题",
}


# ---------------------------------------------------------------------------
# 闸门一：合规自检（广告法违禁词 + 教育类敏感表述）
#
# 每一行：正则 → 风险等级 → 人话解释。这是**粗筛**，宁可多报也别漏报；
# 最终判断仍要人工复核，也不等于平台的官方审核结论。
#
# 教育类为什么单列：知识付费与企业内训最常见的违规不是"最"字，
# 是**效果承诺**——「保过」「包学会」「提分保证」这类把结果写死的说法。
# 广告法第二十四条本来就禁止教育、培训广告对升学、通过考试、获得学位学历
# 或者合格证书作保证性承诺，所以这一档按**高风险**处理。
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
    # —— 教育 / 培训类效果承诺（本包的主战场）——
    (r"保过|包过|保过关|包过关|包拿证|保拿证|不过退款|考不过退", "高",
     "教育类效果承诺；广告法禁止对通过考试作保证性承诺"),
    (r"包学会|保证学会|学不会退|包教包会|学会为止|一定学会", "高",
     "教育类效果承诺；「包学会」属保证性承诺"),
    (r"提分保证|保证提分|必提分|分数保证|稳提\s*\d+\s*分|保底\s*\d+\s*分", "高",
     "教育类提分承诺"),
    (r"(保|包)(就业|offer|录用|录取)|包分配|推荐就业保证", "高",
     "教育类就业承诺"),
    (r"零基础也能(月入|年薪|赚)|学完(就)?能(月入|年薪|赚)", "高",
     "收益承诺，且与培训效果绑定"),
    (r"治愈|根治|痊愈|药到病除|包治|疗效|无副作用|零副作用", "高",
     "医疗功效宣称，非药品/医疗器械不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报|内部渠道|"
     r"跟着买就(赚|涨)", "高", "投资类收益承诺与荐股话术"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方(推荐|认证|指定)|"
     r"教育部(认证|指定)|人社部(认证|指定)", "高", "不得虚构权威背书"),
    # 【实测修正】「唯一（品牌/技术/认证/选择…）」才拦；裸的「唯一」不拦。
    # 依据：真机跑习题时，模型在题干里写了「判断一段画面是不是废片，**唯一标准**是
    # 画面够不够清晰稳定」——这是把"唯一标准"当普通词在用，不是排他性广告宣称，
    # 属于必然误伤。同理放过「首个」这类中性量词，只留真正在给自己贴排他性标签的形态。
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
# 【实测依据】真机连跑 4 次讲义，1 次被拦，拦下的是
#   「做菜和剪辑**最大**的共同点是：先做减法，再做加法」
# 这是讲义里在讲一件常识，不是给商品贴"最大"的标签。学员要花钱买的课程内容
# 被这条规则拦下，会比漏报更糟——所以加一层上下文豁免，但**豁免范围写死在代码里、
# 可枚举、可复核**，不是一句"人工判断"了事。
#
# 反过来说，`最好的课程` / `最强的` / `最高级` / `最大优惠` 这类仍然照拦：
# 它们的后文不在豁免表里。
SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥",
)
# 一个可选的「的」：「最大的共同点」「最大的区别」都是讲义里常见的说法。
SUPERLATIVE_OK_RE = re.compile(
    r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")


def _superlative_is_normal_usage(text, m):
    """「最大/最好/最常见…」后面接的是比较或程度词 → 判为普通用法，不拦。"""
    if not m.group(0).startswith("最"):
        return False
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
# 讲义和习题是大模型一次吐几千字，模板没替换干净的形态比标题场景多得多：
#   · `{}` / `{{标题}}`      JSON 骨架被当正文写进去了
#   · `[填空]` / `[待补充]`  模型给自己留的空档
#   · `XXX` / `xxx`          忘了替换的占位
#   · `待补充` / `待定`      同上
#
# `[填空]` 这类**必须做长度约束**：讲义里出现 `[1]`（引用序号）、`[图 1]`（配图位）
# 是完全正常的写法，一刀切按括号内容判会把好讲义全拦下。所以只在"括号里是个占位词"
# 或"括号里少于 6 个字且带占位含义"时才判命中。
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    (re.compile(r"\{\{?\s*[\u4e00-\u9fffA-Za-z0-9_]*\s*\}?\}"), "{}",
     "残留了模板占位符 `{}`，模板没被替换干净"),
    (re.compile(r"[\[【](填空|待补充|待填|待定|待完善|略|此处省略|XXX|xx|XX)[\]】]"), "[]",
     "残留了占位符 `[...]`，模型给自己留的空档没补"),
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


def _placeholder_marker(text, patterns=None):
    """只用**短标记**判占位符（`{}` / `XXX` / `待补充`），不看 `[填空]` 那种长括号。

    用途：需要在一段文字里快速找一个"明显是没写完"的标记时（而不是长括号，
    因为 `[1]`、`[图 2]` 这类引用序号是正常写法）。返回标记字符串或 ""。
    """
    t = text or ""
    for rx, label, _why in (patterns or PLACEHOLDER_PATTERNS):
        if label == "[]":
            continue
        m = rx.search(t)
        if m:
            return m.group(0)[:40]
    return ""


# ---------------------------------------------------------------------------
# 闸门三：prompt_echo（照抄提示词示例）
#
# 事故复盘（来自爆款标题工坊的实测，两次都真被抓到）：
#   1. 提示词里写过正例 `结论先说：便携榨汁杯不适合三类人` → 模型直接产出近似句
#   2. 提示词里留过 `便携榨汁杯不适合这三类人，理由有三个` → 公众号那一轮**最高分 89.0 的
#      标题一字不差就是它**
# 第 2 例性质更重：最高分那条是"抄了标准答案"，不是"真的最好"，而排序是那个包的核心产出。
#
# 在本包里形态不同但同样致命：课程大纲的示例章节名如果被照抄，整份大纲会变成
# "把示例换个主题词"，章节顺序、学习目标的写法全部雷同——看起来完全正常，
# 直到你发现它是模板填空题。
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
# 侥幸放行），因为分母是两份二元组的并集，讲义那一侧的体量把相似度摊薄了。
# 覆盖度只看"示例被抄了多少"，不看产出有多长：同一次照抄的覆盖度是 **1.00**。
# 实测真讲义对这条示例的覆盖度是 0.05。
ECHO_CONTAIN = 0.60
# 长度守卫（**相对阈值**，与同族另外四个包统一）：目标归一化长度 < max(6, len(示例)//2)
# 时就不比相似度与覆盖度 —— 短串的二元组太少，指标会虚高。
# 用绝对阈值 12 会让短示例的包漏掉「≤11 字的截断照抄」；本包示例 18~40 字 → 门槛 9~20。
# 四个包逐档实测（对每条示例做逐字截断，共 321 档）：相对阈值比绝对 12 多抓 5 档、少抓 0 档。
ECHO_MIN_LEN_FLOOR = 6


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)

# 提示词里出现过的示例文本（跨主题，正常不该被抄）。新增示例必须登记到这里。
PROMPT_SAMPLES = [
    # 大纲示例：故意用了与本包业务不搭的领域（社区团购 / 机械制图 / 架子鼓），
    # 模型不会把"橙子分拣"这种章节名搬进短视频剪辑课。
    "第一章 社区团购的选品逻辑",
    "橙子分拣线上的三个常见停机点",
    "架子鼓初学者最容易忽略的坐姿问题",
    # 讲义示例：同样用不搭界的领域，且刻意写得"不像正常会写的句子"，
    # 免得真实产出与它撞相似度（实测正常讲义正文与这条只有 0.19~0.29）。
    "本章用一句话给出结论，然后分三步演示，最后指出一个常见错误",
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
# 闸门四：结构校验（大纲必须真是大纲）
#
# 教训来自爆款标题工坊：那里只信模型自报的 `formula` 字段，结果真该被判命的那条
# 恰好漏判——**闸门是假绿的**。在本包里对应的形态是：模型返回一个
# `{"chapters": []}` 或者章节里没有 sections，脚本照样打印"大纲已生成"，
# 用户拿着空大纲去生成讲义才发现。
#
# 所以大纲必须**逐层校验**，缺项标红：
#   · 章节数 ≥ 1（--chapters 指定了就按指定数校验）
#   · 每章至少 1 个小节
#   · **每个小节必须有学习目标**（--strict 时要求 ≥ 2 条）
#   · 学习目标不许是"了解 / 熟悉 / 掌握 XX"这种三字空话（无信息量的目标等于没有目标）
#   · 时长必须能算出正数
# ---------------------------------------------------------------------------

EMPTY_OBJECTIVE_RE = re.compile(
    r"^(了解|熟悉|掌握|学习|认识|理解|知道|明白)\s*[\u4e00-\u9fff]{0,6}$")
MIN_OBJECTIVE_LEN = 6


def _clean_list(v, limit=None):
    """把模型给的"列表"归一成字符串列表。

    模型会返回 ["a","b"] / "a；b" / [{"text":"a"}] 三种形态，
    最后一种在实测里最常见（它想补充说明）。三种都认。
    """
    out = []
    if v is None:
        return out
    items = v if isinstance(v, list) else re.split(r"[\n；;]+", str(v))
    for it in items:
        if isinstance(it, dict):
            it = it.get("text") or it.get("objective") or it.get("goal") or ""
        s = re.sub(r"\s+", " ", str(it or "")).strip().strip("-·*").strip()
        if s:
            out.append(s)
    if limit:
        out = out[:limit]
    return out


def normalize_outline(obj, subject, level, chapters_wanted=None):
    """把模型返回的大纲收拾成内部结构，并附上本地结构校验结果。"""
    raw_chapters = []
    if isinstance(obj, dict):
        raw_chapters = obj.get("chapters") or obj.get("outline") or obj.get("items") or []
    elif isinstance(obj, list):
        raw_chapters = obj
    chapters = []
    for ci, rc in enumerate(raw_chapters, 1):
        if not isinstance(rc, dict):
            continue
        title = re.sub(r"\s+", " ", str(rc.get("title") or rc.get("name") or "")).strip()
        goal = re.sub(r"\s+", " ", str(rc.get("goal") or rc.get("chapter_goal") or "")).strip()
        raw_sections = rc.get("sections") or rc.get("lessons") or []
        sections = []
        for si, rs in enumerate(raw_sections, 1):
            if isinstance(rs, str):
                rs = {"title": rs}
            if not isinstance(rs, dict):
                continue
            stitle = re.sub(r"\s+", " ", str(rs.get("title") or rs.get("name") or "")).strip()
            objectives = _clean_list(rs.get("objectives") or rs.get("goals")
                                     or rs.get("learning_objectives"))
            minutes = rs.get("minutes") or rs.get("duration") or rs.get("duration_min")
            try:
                minutes = int(round(float(re.sub(r"[^\d.]", "", str(minutes)) or 0)))
            except (TypeError, ValueError):
                minutes = 0
            sections.append({
                "no": "%d-%d" % (ci, si),
                "chapter_index": ci,
                "title": stitle,
                "objectives": objectives,
                "minutes": minutes,
                "points": _clean_list(rs.get("points") or rs.get("outline")),
            })
        chapters.append({"index": ci, "title": title, "goal": goal, "sections": sections})

    plan = {
        "subject": subject,
        "level": level,
        "level_name": LEVELS[level]["name"],
        "chapters": chapters,
        "chapter_count": len(chapters),
        "section_count": sum(len(c["sections"]) for c in chapters),
        "total_minutes": sum(s["minutes"] for c in chapters for s in c["sections"]),
    }
    checks = structure_checks(plan, chapters_wanted)
    plan["structure_ok"] = all(c["ok"] for c in checks)
    plan["structure_checks"] = checks
    plan["total_hours"] = round(plan["total_minutes"] / 60.0, 1)
    return plan


def structure_checks(plan, chapters_wanted=None):
    """闸门四的实现：逐层校验大纲结构，返回 [{'check','ok','detail'}]。"""
    checks = []
    chs = plan.get("chapters") or []

    def add(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    add("章节数", plan.get("chapter_count", 0) >= 1,
        "解析出 %d 章" % plan.get("chapter_count", 0)
        + ("，期望 %d 章" % chapters_wanted if chapters_wanted else ""))
    if chapters_wanted:
        add("章节数符合 --chapters", plan.get("chapter_count") == chapters_wanted,
            "实际 %d 章 / 期望 %d 章" % (plan.get("chapter_count"), chapters_wanted))

    no_sections = [c["index"] for c in chs if not c["sections"]]
    add("每章都有小节", not no_sections,
        "没有章节缺小节" if not no_sections
        else "第 %s 章一个小节都没解析出来" % "、".join(map(str, no_sections)))

    missing_obj, empty_obj, short_obj, no_time = [], [], [], []
    for c in chs:
        for s in c["sections"]:
            tag = "%s %s" % (s["no"], s["title"] or "(无标题)")
            if not s["objectives"]:
                missing_obj.append(tag)
            else:
                for o in s["objectives"]:
                    if EMPTY_OBJECTIVE_RE.match(o) or len(o) < MIN_OBJECTIVE_LEN:
                        empty_obj.append("%s → 「%s」" % (tag, o))
            if not s["title"]:
                short_obj.append(tag)
            if s["minutes"] <= 0:
                no_time.append(tag)
    add("每节都有学习目标", not missing_obj,
        "全部小节都有学习目标" if not missing_obj
        else "%d 个小节没有学习目标：%s" % (len(missing_obj), "；".join(missing_obj[:6])))
    add("学习目标不是空话", not empty_obj,
        "学习目标都有具体落点" if not empty_obj
        else "%d 条目标是无信息量的套话：%s" % (len(empty_obj), "；".join(empty_obj[:6])))
    add("小节都有标题", not short_obj,
        "全部小节都有标题" if not short_obj else "缺标题：%s" % "；".join(short_obj[:6]))
    add("每节都有正数时长", not no_time,
        "总时长 %d 分钟" % plan.get("total_minutes", 0) if not no_time
        else "%d 个小节时长为 0 或无法解析：%s" % (len(no_time), "；".join(no_time[:6])))
    return checks


# ---------------------------------------------------------------------------
# 闸门五：成本
#
# 网关不公布逐模型的逐 token 单价，所以我们**不编单价**：
# 默认口径写成一个可覆盖的常量，并且在文档与输出里都标成"估算"。
# 真实账单以 api.a7w.cn 控制台为准——`all` 跑完会把真实 usage 逐次打出来，
# 方便用户自己拿 token 数去核对。
# ---------------------------------------------------------------------------

YUAN_PER_KTOK_DEFAULT = 0.02     # 元 / 千 token，**估算口径**，不是账单
POINTS_PER_YUAN = 100            # 算力集市的充值比例：1 元 = 100 点

# 一次调用的 token 用量预估（用于 cost 子命令与 --budget 前置检查）
EST_TOKENS = {
    "plan": {"prompt": 900, "completion": 2600},
    "lesson": {"prompt": 1500, "completion": 4200},
    "quiz": {"prompt": 1400, "completion": 2600},
}


def estimate_tokens(lessons, quizzes):
    """估 token 用量。lessons / quizzes 是要生成的小节数（首次调用另加一次大纲）。"""
    plan = EST_TOKENS["plan"]
    lesson = EST_TOKENS["lesson"]
    quiz = EST_TOKENS["quiz"]
    prompt = plan["prompt"] + lesson["prompt"] * lessons + quiz["prompt"] * quizzes
    completion = plan["completion"] + lesson["completion"] * lessons + quiz["completion"] * quizzes
    calls = 1 + lessons + quizzes
    return {"calls": calls, "prompt_tokens": prompt, "completion_tokens": completion,
            "total_tokens": prompt + completion}


def yuan_from_tokens(tokens, yuan_per_ktok=None):
    rate = YUAN_PER_KTOK_DEFAULT if yuan_per_ktok is None else float(yuan_per_ktok)
    return round(tokens / 1000.0 * rate, 4)


class CostTracker:
    """累计真实 usage，实时核预算。超了就地停（闸门五）。"""

    def __init__(self, budget=None, yuan_per_ktok=None):
        self.budget = budget
        self.rate = YUAN_PER_KTOK_DEFAULT if yuan_per_ktok is None else float(yuan_per_ktok)
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
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

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    @property
    def yuan(self):
        return yuan_from_tokens(self.total_tokens, self.rate)

    @property
    def points(self):
        return round(self.yuan * POINTS_PER_YUAN, 1)

    def over_budget(self, extra_tokens=0):
        if self.budget is None:
            return False
        return yuan_from_tokens(self.total_tokens + extra_tokens, self.rate) > self.budget

    def line(self):
        return ("已用 %d 次调用 · token prompt=%d completion=%d total=%d · "
                "估算 %.3f 元（%g 元/千 token%s）" % (
                    self.calls, self.prompt_tokens, self.completion_tokens, self.total_tokens,
                    self.yuan, self.rate,
                    "，含 %d 次估值非真实 usage" % self.estimated_flags
                    if self.estimated_flags else ""))


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class CourseError(a7w.A7wError):
    """课程生产线失败。"""


class CourseGate(CourseError):
    """被本地硬闸门拦下（与"调用失败"分开，退出码也不同：闸门 3 / 失败 4）。"""


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, timeout=300, json_mode=True,
         tracker=None, tracker_label=""):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么必须带退避重试：网关的 upstream timeout / HTTP 502 实测很常见，
    一节讲义就是几千 token，被一次抖动打断要重跑整节，很亏。
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
                raise CourseError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise CourseError("点数不足（402）：%s  到 https://api.a7w.cn/ 充值后重试。" % msg)
            if exc.code == 404:
                raise CourseError("模型不存在（404）：%s  用 `run.py models` 现查在架模型。" % msg)
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 %s，%ss 后重试…\n" % (exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise CourseError("调用失败（HTTP %s）：%s" % (exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（%s），%ss 后重试 %d/%d…\n" % (
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    if payload is None:
        raise CourseError("网络错误：%s（已重试 %d 次；确认能访问 %s）" % (
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 网关对生成应用那条链路会把结果包一层 {"code":1,"data":{...}}，两种形态都认。
    # 注意：走 /chat/completions 的**成功响应不带 code 字段**，所以不能拿 code 判成功。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise CourseError("模型没返回 choices：%s" % json.dumps(payload, ensure_ascii=False)[:300])
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
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
        raise CourseError("模型返回空内容")
    dec = json.JSONDecoder()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = [fenced.group(1).strip()] if fenced else []
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
    raise CourseError("模型返回的不是合法 JSON：%s" % text[:300].replace("\n", " "))


# ---------------------------------------------------------------------------
# 提示词
#
# 【铁律】提示词里不许出现任何一份可直接复制的完整产出。
# 讲形态只用描述性语言，举例一律用登记在 PROMPT_SAMPLES 里的**跨主题**示例
# （社区团购选品 / 机械制图 / 架子鼓），与真实业务主题明显不搭。
# 万一以后有人把真实示例加回提示词，PROMPT_SAMPLES + echo 闸门会兜住。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是三剪客团队的课程设计编辑，服务知识付费、企业内训与录课老师。\n"
    "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
    "你有两条不可越过的底线：\n"
    "  1. 不写任何效果承诺——「保过」「包学会」「提分保证」「保证就业」这类说法一律不许出现，"
    "广告法也禁止「最/第一/国家级/100%/根治/绝对」等用语；\n"
    "  2. 不编造数据、人名、机构名、检测结论与权威背书；没有依据就写定性描述。\n"
    "你写的课程必须能真的被讲出来：学习目标要可检验，练习要能动手做完。"
)


def _level_block(level):
    lv = LEVELS[level]
    return "- 受众水平：%s。%s\n- 讲练配比参考：%s" % (lv["name"], lv["tone"], lv["ratio"])


def build_plan_prompt(subject, level, chapters, sections_per_chapter,
                      total_minutes=None, audience=None, requirements=None):
    """大纲提示词。所有示例一律跨主题，且登记在 PROMPT_SAMPLES。"""
    extra = []
    if audience:
        extra.append("受众补充说明：%s" % audience)
    if requirements:
        extra.append("必须有把握覆盖的硬性要求（来自用户，不要漏）：%s" % requirements)
    return """请为下面这门课出一份**可执行的课程大纲**。

课程主题：{subject}

{level}

结构要求：
- 一共 {chapters} 章，每章 {spc} 个小节（共 {total} 节）
- 每章要有 `goal`：这一章学完，学员能做到什么（一句话，要有具体落点）
- **每个小节都必须有 `objectives`**：2~3 条学习目标，每条都要**可检验**
  - 合格的写法：写出「能判断…」「能独立完成…」「能说出 A 与 B 的区别」这种
    带动作和对象的目标
  - 不合格的写法：只写「了解 XX」「熟悉 XX」「掌握 XX」——这类三字套话不算学习目标，
    脚本会判为结构不合格并拦下
- 每个小节要有 `minutes`：实际讲这一节需要的分钟数（整数，按受众水平给，
  {tone_hint}）
- 每个小节要有 `points`：2~4 条这一节要讲到的知识点关键字（不是整句话）
- 章节顺序要符合学习路径：后一节必须能用上前一节学到的东西，不许跳步
- 时长合计尽量落在 {budget_hint} 左右

{extra}
主题词的使用：
- 不要让每章标题都以完整主题词「{subject}」开头，**以它开头的章节不要超过一半**，
  其余用具体做法、场景或对象命名，避免整份大纲看起来像同一个模板

讲形态（只体会结构，**不要照抄任何示例内容，也不要改主题**）：
- 章节标题写的是"这件事叫什么 + 为什么值得学"，不是"第 X 讲"
- 学习目标写的是学员能做到什么，不是讲师要讲什么

只输出一个 JSON 对象，不要输出别的任何东西：
{{"subject":"{subject}","chapters":[{{"title":"章节标题","goal":"这一章学完能做到什么",
"sections":[{{"title":"小节标题","objectives":["可检验的目标一","可检验的目标二"],
"minutes":45,"points":["知识点1","知识点2"]}}]}}]}}""".format(
        subject=subject, level=_level_block(level), chapters=chapters,
        spc=sections_per_chapter, total=chapters * sections_per_chapter,
        tone_hint="零基础把单节控制在 30~45 分钟，进阶可以 45~60 分钟"
                  if level == "zero" else "单节 30~60 分钟",
        budget_hint=("%d 分钟" % total_minutes) if total_minutes else "总量的自然长度",
        extra=("\n".join(extra) + "\n") if extra else "")


def build_lesson_prompt(subject, level, chapter, section):
    obj = "\n".join("- %s" % o for o in section["objectives"]) or "- （大纲没给目标，请自行补上并写清楚）"
    pts = "、".join(section["points"]) or "（大纲没给，按小节标题自行判断）"
    return """请写第 {no} 节的**讲义正文**，学员是要拿它自学的。

课程主题：{subject}
所属章节：第 {ci} 章《{ctitle}》
本节标题：《{stitle}》
本节学习目标（讲义必须覆盖每一条，写完要能对照检查）：
{obj}
本节知识点：{pts}
本节篇幅：{minutes} 分钟能讲完

{level}

讲义写法：
- 用 Markdown，从 `## {stitle}` 开始，小节内部用 `###` 分块
- 字数 **1500~3000 个中文字符**（不含 Markdown 符号）。这是硬要求：
  少于 1500 字讲不透，多于 3000 字单节就听不完了
- 必须包含这四块，顺序不要变：
  1. 本节要解决的问题（为什么学它，不学会在哪里卡住）
  2. 核心内容（概念 + 步骤 + 至少一个具体例子，例子要能跟着做）
  3. 常见错误（至少 2 条，写清"错在哪、为什么错、怎么改"）
  4. 本节小结（3~5 条要点）+ 一句承上启下的话，引出下一节
- **只把内容写出来，不要写"以下是我的回答""作为 AI"这类话，不要写给自己看的注释**
- 不要留任何待补的空档：不许出现 `{{}}`、`[填空]`、`XXX`、`待补充` 这类占位符
- 不许有任何效果承诺（保过 / 包学会 / 提分保证），不许编数据、人名、机构与背书
- 专业术语第一次出现要用一句大白话解释（按上面的受众水平决定解释多少）

只输出一个 JSON 对象，不要输出别的任何东西：
{{"title":"{stitle}","content":"讲义正文（Markdown，从 ## 标题开始）"}}""".format(
        no=section["no"], subject=subject, ci=chapter["index"], ctitle=chapter["title"],
        stitle=section["title"], obj=obj, pts=pts,
        minutes=section["minutes"] or 45, level=_level_block(level))


def build_quiz_prompt(subject, level, chapter, section, per_tier, lesson_text=None):
    tiers = "\n".join("- %s（%s）：%s" % (k, name, cap) for k, name, cap in QUIZ_TIERS)
    types = " / ".join("%s=%s" % (k, v) for k, v in QUESTION_TYPE_LABEL.items())
    ctx = ""
    if lesson_text:
        body = lesson_text.strip()
        if len(body) > 4000:
            body = body[:4000] + "\n…（讲义过长，已截断到前 4000 字）"
        ctx = "\n本节讲义（题目必须严格出自这份讲义，不要考讲义里没有的东西）：\n" + body + "\n"
    return """请为第 {no} 节《{stitle}》出**分层习题**，并给出答案与解析。

课程主题：{subject}
所属章节：第 {ci} 章《{ctitle}》
本节学习目标：
{obj}
{ctx}
{level}

难度分层（每层恰好 {per} 道题）：
{tiers}

题目要求：
- `type` 只能用这几个值：{types}
- 单选题必须给 `options`：**恰好 4 个选项**，写成 "A. …" "B. …" "C. …" "D. …" 的形式，
  `answer` 只写选项字母（如 "B"）；干扰项要像真的，不要凑数
- 判断题 `answer` 只写 "对" 或 "错"
- 简答题 `answer` 写 3~5 句参考答案
- 案例分析题 `answer` 写完整的分析思路（先给判断，再给依据，最后给做法）
- **每道题都必须有 `explain`（解析）**，解析要说清三件事：为什么这个答案对、
  其他选项/其他做法错在哪、这题考的是哪个知识点。解析不许写"见讲义"这种废话
- 题目不要出现"以上都对""以上都不对"这种凑数选项
- 不许编造讲义与目标里没有的数据、人名、机构
- **不许有任何效果承诺**（保过 / 包学会 / 提分保证），题干与选项里也不要出现
  「最好」「第一」「唯一」「100%」「绝对」这类绝对化说法
  （想表达"判断依据不止一个"就直接写"不能只看这一个"）

只输出一个 JSON 对象，不要输出别的任何东西：
{{"section":"{stitle}","questions":[{{"tier":"basic","type":"choice",
"question":"题干","options":["A. …","B. …","C. …","D. …"],"answer":"B",
"explain":"解析"}}]}}""".format(
        no=section["no"], subject=subject, ci=chapter["index"], ctitle=chapter["title"],
        stitle=section["title"],
        obj="\n".join("- %s" % o for o in section["objectives"]) or "- （大纲没给）",
        ctx=ctx, level=_level_block(level), per=per_tier, tiers=tiers, types=types)


# ---------------------------------------------------------------------------
# 产出归一化 + 闸门执行
# ---------------------------------------------------------------------------

def normalize_lesson(obj, section):
    """收拾讲义返回，跑闸门，返回内部结构。"""
    if isinstance(obj, str):
        obj = {"content": obj}
    obj = obj if isinstance(obj, dict) else {}
    title = re.sub(r"\s+", " ", str(obj.get("title") or section["title"])).strip()
    content = str(obj.get("content") or obj.get("text") or obj.get("body") or "").strip()
    leaks = []
    if not content:
        leaks.append({"kind": "empty", "why": "模型没返回讲义正文（content 为空）"})
    for h in compliance_scan(content):
        leaks.append({"kind": "banned_word",
                      "why": "命中违禁词「%s」（%s风险）：%s" % (h["word"], h["level"], h["why"])})
    for h in placeholder_hits(content):
        leaks.append({"kind": "placeholder", "why": h["why"]})
    leaks.extend(echo_hits(content, "讲义"))
    chars = len(re.sub(r"[#*>`\-\s\[\]()]", "", content))
    ok_len = 1500 <= chars <= 3000
    if content and not ok_len:
        leaks.append({"kind": "length",
                      "why": "讲义正文 %d 字，不在要求的 1500~3000 字区间（%s）"
                             % (chars, "偏短，讲不透" if chars < 1500 else "偏长，单节讲不完")})
    return {"no": section["no"], "title": title, "content": content,
            "chars": chars, "length_ok": ok_len, "leaks": leaks,
            "ok": not leaks}


def normalize_quiz(obj, section, per_tier):
    """收拾习题返回，跑闸门，返回内部结构。"""
    raw = []
    if isinstance(obj, dict):
        raw = obj.get("questions") or obj.get("items") or []
    elif isinstance(obj, list):
        raw = obj
    questions, leaks = [], []
    for qi, rq in enumerate(raw, 1):
        if not isinstance(rq, dict):
            continue
        tier = str(rq.get("tier") or rq.get("level") or "").strip().lower()
        if tier not in TIER_KEYS:
            tier = "basic"
        qtype = str(rq.get("type") or rq.get("question_type") or "").strip().lower()
        alias = {"single": "choice", "single_choice": "choice", "选择题": "choice",
                 "singlechoice": "choice", "tf": "judge", "truefalse": "judge",
                 "判断题": "judge", "简答": "short", "essay": "short",
                 "案例": "case", "analysis": "case"}
        qtype = alias.get(qtype, qtype if qtype in QUESTION_TYPES else "short")
        options = _clean_list(rq.get("options"))
        if qtype == "choice" and options and len(options) != 4:
            leaks.append({"kind": "quiz_options",
                          "why": "第 %d 题是单选题，但有 %d 个选项（要求恰好 4 个）"
                                 % (qi, len(options))})
        answer = str(rq.get("answer") or "").strip()
        explain = str(rq.get("explain") or rq.get("explanation")
                      or rq.get("analysis") or "").strip()
        qtext = str(rq.get("question") or rq.get("stem") or "").strip()
        if not qtext:
            leaks.append({"kind": "quiz_empty", "why": "第 %d 题没有题干" % qi})
        if not answer:
            leaks.append({"kind": "quiz_no_answer", "why": "第 %d 题没有答案" % qi})
        if not explain:
            leaks.append({"kind": "quiz_no_explain", "why": "第 %d 题没有解析" % qi})
        blob = "\n".join([qtext, " ".join(options), answer, explain])
        for h in compliance_scan(blob):
            leaks.append({"kind": "banned_word",
                          "why": "第 %d 题命中违禁词「%s」（%s风险）：%s"
                                 % (qi, h["word"], h["level"], h["why"])})
        for h in placeholder_hits(blob):
            leaks.append({"kind": "placeholder", "why": "第 %d 题%s" % (qi, h["why"])})
        for x in echo_hits(qtext, "第 %d 题题干" % qi):
            leaks.append({"kind": x["kind"], "why": x["why"]})
        questions.append({"tier": tier, "tier_name": dict(
            (k, n) for k, n, _ in QUIZ_TIERS)[tier], "type": qtype,
            "type_name": QUESTION_TYPE_LABEL[qtype], "question": qtext,
            "options": options, "answer": answer, "explain": explain})
    counts = {}
    for q in questions:
        counts[q["tier"]] = counts.get(q["tier"], 0) + 1
    for key, name, _cap in QUIZ_TIERS:
        if counts.get(key, 0) != per_tier:
            leaks.append({"kind": "quiz_tier_count",
                          "why": "%s档应有 %d 道题，实际 %d 道（难度分层不完整）"
                                 % (name, per_tier, counts.get(key, 0))})
    if not questions:
        leaks.append({"kind": "empty", "why": "模型没返回任何题目"})
    return {"no": section["no"], "title": section["title"], "questions": questions,
            "tier_counts": counts, "leaks": leaks, "ok": not leaks}


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


def state_key(section_no, stage):
    return "%s:%s" % (stage, section_no)


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "✗ " + s
    return "\x1b[31m%s\x1b[0m" % s


def fmt_minutes(m):
    if m <= 0:
        return "未知"
    if m < 60:
        return "%d 分钟" % m
    return "%d 小时 %d 分" % (m // 60, m % 60)


def render_outline_md(plan, model=None, usage=None, elapsed=None):
    out = ["# 课程大纲 · %s" % plan["subject"], ""]
    out.append("- 受众水平：%s" % plan["level_name"])
    out.append("- 规模：%d 章 / %d 节 / 合计 %s" % (
        plan["chapter_count"], plan["section_count"], fmt_minutes(plan["total_minutes"])))
    if model:
        out.append("- 模型：`%s`　命令端点：`POST /api/v1/chat/completions`" % model)
    if usage:
        out.append("- token 用量：prompt=%s completion=%s total=%s" % (
            usage.get("prompt_tokens", "-"), usage.get("completion_tokens", "-"),
            usage.get("total_tokens", "-")))
    if elapsed is not None:
        out.append("- 耗时：%.1fs" % elapsed)
    out.append("")
    for c in plan["chapters"]:
        out.append("## 第 %d 章　%s" % (c["index"], c["title"]))
        out.append("")
        if c["goal"]:
            out.append("> 本章目标：%s" % c["goal"])
            out.append("")
        out.append("| 小节 | 标题 | 时长 | 学习目标 |")
        out.append("|---|---|---|---|")
        for s in c["sections"]:
            objs = "<br>".join("· " + o for o in s["objectives"]) or "（缺）"
            out.append("| %s | %s | %s | %s |" % (
                s["no"], s["title"] or "（缺标题）", fmt_minutes(s["minutes"]), objs))
        out.append("")
    return "\n".join(out)


def render_audit_md(audit):
    out = ["# 质量与合规自检报告", ""]
    out.append("> 本地确定性判定（模型自评不参与）。命中项一律拦截，退出码非 0。")
    out.append("")
    if audit["ok"]:
        out.append("✅ 全部 **%d** 个受检对象通过五道闸门。" % audit["checked"])
    else:
        out.append("⚠️ %d 个受检对象中 **%d** 个命中闸门，必须人工复核后才能使用。"
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
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def _load_json_file(path, what):
    p = Path(path)
    if not p.is_file():
        raise CourseError("找不到%s文件：%s" % (what, path))
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))


def _require_plan(a):
    obj = _load_json_file(a.plan, "大纲")
    plan = obj.get("plan") if isinstance(obj, dict) and "plan" in obj else obj
    if not isinstance(plan, dict) or not plan.get("chapters"):
        raise CourseError("大纲文件里没有 chapters：%s（先用 `plan` 生成）" % a.plan)
    for c in plan["chapters"]:
        c.setdefault("sections", [])
        for s in c["sections"]:
            s.setdefault("objectives", [])
            s.setdefault("minutes", 0)
            s.setdefault("points", [])
            s.setdefault("no", "%s-%s" % (c.get("index"), s.get("no", "?")))
            s.setdefault("chapter_index", c.get("index"))
    # 闸门四在讲义/习题阶段**再跑一遍**：大纲是可能被手工改坏的，
    # 拿一份结构残缺的大纲去写讲义，等于把错误放大到几十节。
    plan["chapter_count"] = len(plan["chapters"])
    plan["section_count"] = sum(len(c["sections"]) for c in plan["chapters"])
    plan["total_minutes"] = sum(s["minutes"] for c in plan["chapters"] for s in c["sections"])
    checks = structure_checks(plan)
    bad = [c for c in checks if not c["ok"]]
    if bad:
        for c in bad:
            sys.stderr.write("   %s ✗ %s\n" % (c["check"], c["detail"]))
        raise CourseGate(
            "闸门四：%s 的结构校验未通过（%d 项），先修大纲再生成讲义/习题"
            % (a.plan, len(bad)))
    return plan


def _plan_level(plan, a):
    """讲义/习题的受众水平优先跟大纲走（大纲里已经定死了讲练深度）。"""
    return plan.get("level") or getattr(a, "level", None) or "zero"


def _iter_sections(plan):
    for c in plan["chapters"]:
        for s in c["sections"]:
            yield c, s


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

# 退出码 → 失败类别（与 SKILL.md 里公示的退出码表一致）
_KIND_BY_EXIT = {2: "usage", 3: "gate", 4: "call", 130: "interrupt"}


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


def _emit(a, text, json_obj=None, ok=True):
    """统一出口。

    `--json` 且给了 `json_obj` 时：补 ok 后序列化，同时落 `--out`；
    否则原样输出 text（非 JSON 模式的输出与改动前逐字节一致）。
    """
    if json_obj is not None and getattr(a, "json", False):
        body = _json_text(json_obj, indent=1, ok=ok)
        if getattr(a, "out", None):
            p = Path(a.out)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 %s\n" % a.out)
        _json_write(body)
        return
    if getattr(a, "out", None):
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 %s\n" % a.out)
    print(text)


def cmd_plan(a):
    if not (a.topic or "").strip():
        raise CourseError('请用 --topic 给一个主题，例如 --topic "零基础短视频剪辑"')
    prompt = build_plan_prompt(a.topic, a.level, a.chapters, a.sections_per_chapter,
                               a.total_minutes, a.audience, a.requirements)
    if a.dry_run:
        _dry_run_json(a, topic=a.topic, level=a.level, user=prompt)
        return 0
    sys.stderr.write("正在用 `%s` 出 %d 章 × %d 节的课程大纲…\n"
                     % (a.model, a.chapters, a.sections_per_chapter))
    tracker = CostTracker(a.budget, a.yuan_per_ktok)
    if tracker.over_budget(EST_TOKENS["plan"]["prompt"] + EST_TOKENS["plan"]["completion"]):
        sys.stderr.write("\n%s\n" % _red(
            "预估成本已超 --budget %g 元，未发起任何调用" % a.budget))
        return _fail(3, "budget", "预估成本已超 --budget %g 元，未发起任何调用" % a.budget)
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                          max_tokens=a.max_tokens, key=a.key,
                          json_mode=not a.no_json_mode,
                          tracker=tracker, tracker_label="plan")
    elapsed = time.time() - t0
    plan = normalize_outline(parse_first_json(content), a.topic, a.level, a.chapters)
    if not plan["chapters"]:
        raise CourseError("模型返回里没有 chapters，大纲是空的（可加大 --max-tokens 或换模型）")
    result = {"plan": plan, "model": a.model, "usage": usage,
              "elapsed_sec": round(elapsed, 1), "cost": {
                  "total_tokens": tracker.total_tokens, "yuan": tracker.yuan}}
    _emit(a, render_outline_md(plan, a.model, usage, elapsed), json_obj=result)
    sys.stderr.write("usage: %s\n" % json.dumps(usage, ensure_ascii=False))
    sys.stderr.write("%s\n" % tracker.line())
    return _report_gates(plan["structure_checks"], plan["structure_ok"],
                         "大纲结构校验未通过（缺章节 / 缺小节 / 缺学习目标），已标红")


def _report_gates(checks, ok, msg):
    """把结构校验结果打到 stderr 并在失败时返回退出码 3。"""
    bad = [c for c in checks if not c["ok"]]
    for c in bad:
        sys.stderr.write("   %s %s：%s\n" % (c["check"], "✗", c["detail"]))
    if bad and not ok:
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(3, "gate", "闸门：大纲结构校验未通过（%d 项）" % len(bad))
    return 0


def cmd_lesson(a):
    plan = _require_plan(a)
    sections = list(_iter_sections(plan))
    if a.count:
        sections = sections[:a.count]
    if not sections:
        raise CourseError("大纲里一个小节都没有")
    if a.from_file:
        text = Path(a.from_file).read_text(encoding="utf-8", errors="replace")
        obj = parse_first_json(text)
        item = normalize_lesson(obj, sections[0][1])
        return _emit_lessons(a, plan, [(sections[0][0], sections[0][1], item)], None, None)
    tracker = CostTracker(a.budget, a.yuan_per_ktok)
    per = EST_TOKENS["lesson"]["prompt"] + EST_TOKENS["lesson"]["completion"]
    if tracker.over_budget(per * len(sections)):
        sys.stderr.write("\n%s\n" % _red(
            "预估成本已超 --budget %g 元，一条讲义都没生成" % a.budget))
        return _fail(3, "budget", "预估成本已超 --budget %g 元，一条讲义都没生成" % a.budget)
    results, model, usage0 = [], a.model, None
    dry = []
    for i, (c, s) in enumerate(sections, 1):
        prompt = build_lesson_prompt(plan["subject"], _plan_level(plan, a), c, s)
        if a.dry_run:
            if getattr(a, "json", False):
                # 逐节的提示词先攒起来，最后**一次性**吐一个 JSON（不能吐多个 JSON 文档）
                dry.append({"section": s["no"], "index": i, "total": len(sections),
                            "user": prompt})
            else:
                print("=== [%d/%d] %s ===\n%s" % (i, len(sections), s["no"], prompt))
            continue
        sys.stderr.write("[%d/%d] 正在写 %s《%s》…\n" % (i, len(sections), s["no"], s["title"]))
        if tracker.over_budget(per):
            sys.stderr.write("\n%s\n" % _red("成本已达 --budget %g 元，就地停止（%s）"
                                            % (a.budget, tracker.line())))
            break
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                              max_tokens=a.max_tokens, key=a.key,
                              json_mode=not a.no_json_mode,
                              tracker=tracker, tracker_label="lesson")
        item = normalize_lesson(parse_first_json(content), s)
        item["elapsed_sec"] = round(time.time() - t0, 1)
        item["usage"] = usage
        sys.stderr.write("      %.0f 字 · %.1fs · usage %s\n" % (
            item["chars"], item["elapsed_sec"], json.dumps(usage, ensure_ascii=False)))
        results.append((c, s, item))
        usage0 = usage
    if a.dry_run:
        if getattr(a, "json", False):
            _dry_run_json(a, sections=dry)
        return 0
    if not results:
        raise CourseError("没有生成任何讲义")
    return _emit_lessons(a, plan, results, model, tracker)


def _emit_lessons(a, plan, results, model, tracker):
    out = ["# 课程讲义 · %s" % plan["subject"], "",
           "- 受众水平：%s" % plan.get("level_name", ""),
           "- 本次生成：%d 节" % len(results), ""]
    for c, s, it in results:
        out.append("---")
        out.append("")
        out.append("## 第 %d 章　%s" % (c.get("index", 0), c.get("title", "")))
        out.append("")
        out.append("**%s　%s**" % (it["no"], it["title"]))
        out.append("")
        out.append(it["content"] or "（正文为空）")
        out.append("")
        if it["leaks"]:
            out.append("### 本地自检命中")
            out.append("")
            for lk in it["leaks"]:
                out.append("- %s：%s" % (lk["kind"], lk["why"]))
            out.append("")
    md = "\n".join(out)
    bad = [it for _c, _s, it in results if not it["ok"]]
    _emit(a, md, json_obj={"subject": plan["subject"], "model": model,
                           "lessons": [it for _c, _s, it in results]}, ok=not bad)
    if bad:
        sys.stderr.write("\n%s\n" % _red("闸门：%d 节讲义命中（违禁词 / 占位符 / 照抄示例 / "
                                        "字数越界），不可直接录课：" % len(bad)))
        for it in bad:
            for lk in it["leaks"]:
                sys.stderr.write("   %s  ← %s\n" % (it["no"], lk["why"]))
        if tracker:
            sys.stderr.write("%s\n" % tracker.line())
        return _fail(3, "gate", "闸门：%d 节讲义命中（违禁词/占位符/照抄示例/字数越界）" % len(bad))
    if tracker:
        sys.stderr.write("%s\n" % tracker.line())
    return 0


def cmd_quiz(a):
    plan = _require_plan(a)
    sections = list(_iter_sections(plan))
    if a.count:
        sections = sections[:a.count]
    if not sections:
        raise CourseError("大纲里一个小节都没有")
    if a.from_file:
        text = Path(a.from_file).read_text(encoding="utf-8", errors="replace")
        obj = parse_first_json(text)
        item = normalize_quiz(obj, sections[0][1], a.per_tier)
        return _emit_quizzes(a, plan, [(sections[0][0], sections[0][1], item)], None, None)
    tracker = CostTracker(a.budget, a.yuan_per_ktok)
    per = EST_TOKENS["quiz"]["prompt"] + EST_TOKENS["quiz"]["completion"]
    if tracker.over_budget(per * len(sections)):
        sys.stderr.write("\n%s\n" % _red(
            "预估成本已超 --budget %g 元，一道题都没生成" % a.budget))
        return _fail(3, "budget", "预估成本已超 --budget %g 元，一道题都没生成" % a.budget)
    lessons = {}
    if a.lessons_file:
        lessons = _load_json_file(a.lessons_file, "讲义").get("lessons") or []
        lessons = dict((x.get("no"), x.get("content")) for x in lessons
                       if isinstance(x, dict))
    results, model = [], a.model
    dry = []
    for i, (c, s) in enumerate(sections, 1):
        prompt = build_quiz_prompt(plan["subject"], _plan_level(plan, a), c, s,
                                   a.per_tier, lessons.get(s["no"]))
        if a.dry_run:
            if getattr(a, "json", False):
                dry.append({"section": s["no"], "index": i, "total": len(sections),
                            "user": prompt})
            else:
                print("=== [%d/%d] %s ===\n%s" % (i, len(sections), s["no"], prompt))
            continue
        sys.stderr.write("[%d/%d] 正在出 %s《%s》的习题…\n"
                         % (i, len(sections), s["no"], s["title"]))
        if tracker.over_budget(per):
            sys.stderr.write("\n%s\n" % _red("成本已达 --budget %g 元，就地停止（%s）"
                                            % (a.budget, tracker.line())))
            break
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                              max_tokens=a.max_tokens, key=a.key,
                              json_mode=not a.no_json_mode,
                              tracker=tracker, tracker_label="quiz")
        item = normalize_quiz(parse_first_json(content), s, a.per_tier)
        item["elapsed_sec"] = round(time.time() - t0, 1)
        item["usage"] = usage
        sys.stderr.write("      %d 题 · %.1fs · usage %s\n" % (
            len(item["questions"]), item["elapsed_sec"], json.dumps(usage, ensure_ascii=False)))
        results.append((c, s, item))
    if a.dry_run:
        if getattr(a, "json", False):
            _dry_run_json(a, sections=dry)
        return 0
    if not results:
        raise CourseError("没有生成任何习题")
    return _emit_quizzes(a, plan, results, model, tracker)


def _emit_quizzes(a, plan, results, model, tracker):
    out = ["# 课程习题与解析 · %s" % plan["subject"], "",
           "- 受众水平：%s" % plan.get("level_name", ""),
           "- 本次生成：%d 节" % len(results), ""]
    for c, s, it in results:
        out.append("---")
        out.append("")
        out.append("## %s　%s" % (it["no"], it["title"]))
        out.append("")
        for qi, q in enumerate(it["questions"], 1):
            out.append("**%d. [%s / %s]** %s" % (qi, q["tier_name"], q["type_name"], q["question"]))
            if q["options"]:
                out.append("")
                for o in q["options"]:
                    out.append("- %s" % o)
            out.append("")
            out.append("- 答案：%s" % q["answer"])
            out.append("- 解析：%s" % q["explain"])
            out.append("")
        if it["leaks"]:
            out.append("### 本地自检命中")
            out.append("")
            for lk in it["leaks"]:
                out.append("- %s：%s" % (lk["kind"], lk["why"]))
            out.append("")
    bad = [it for _c, _s, it in results if not it["ok"]]
    _emit(a, "\n".join(out), json_obj={"subject": plan["subject"], "model": model,
                                       "quizzes": [it for _c, _s, it in results]},
          ok=not bad)
    if bad:
        sys.stderr.write("\n%s\n" % _red("闸门：%d 节习题命中（缺答案 / 缺解析 / 分层不全 / "
                                        "违禁词 / 占位符 / 照抄示例）：" % len(bad)))
        for it in bad:
            for lk in it["leaks"]:
                sys.stderr.write("   %s  ← %s\n" % (it["no"], lk["why"]))
        if tracker:
            sys.stderr.write("%s\n" % tracker.line())
        return _fail(3, "gate", "闸门：%d 节习题命中（缺答案/解析或分层不全）" % len(bad))
    if tracker:
        sys.stderr.write("%s\n" % tracker.line())
    return 0


def cmd_cost(a):
    sections = a.chapters * a.sections_per_chapter
    n_lessons = sections if a.lessons is None else a.lessons
    n_quizzes = 0 if a.quiz_off else (sections if a.quizzes is None else a.quizzes)
    est = estimate_tokens(n_lessons, n_quizzes)
    yuan = yuan_from_tokens(est["total_tokens"], a.yuan_per_ktok)
    rec = {
        "chapters": a.chapters, "sections_per_chapter": a.sections_per_chapter,
        "sections": sections, "lesson_calls": n_lessons, "quiz_calls": n_quizzes,
        "calls": est["calls"],
        "est_prompt_tokens": est["prompt_tokens"],
        "est_completion_tokens": est["completion_tokens"],
        "est_total_tokens": est["total_tokens"],
        "yuan_per_ktok": YUAN_PER_KTOK_DEFAULT if a.yuan_per_ktok is None else a.yuan_per_ktok,
        "est_yuan": yuan, "est_points": round(yuan * POINTS_PER_YUAN, 1),
        "budget": a.budget, "model": a.model,
        "notes": [
            "**这是估算，不是账单**：网关不公布逐模型单价，默认按 %g 元/千 token 折算，"
            "可用 --yuan-per-ktok 覆盖。" % (YUAN_PER_KTOK_DEFAULT if a.yuan_per_ktok is None
                                             else a.yuan_per_ktok),
            "单价口径待核：本包没有用真金白银跑出逐模型单价，所以不写死某个模型的价。",
            "真实用量看每次调用返回的 usage（prompt_tokens / completion_tokens），"
            "账单以 api.a7w.cn 控制台为准。",
            "1 元 = %d 点。" % POINTS_PER_YUAN,
        ],
    }
    # 先定结论：超预算就是「不放行」，发出的 JSON 里 ok 要与退出码一致
    over_budget = a.budget is not None and yuan > a.budget
    rec_rc = (_fail(3, "budget", "预估 %.2f 元超过 --budget %g 元，未发起任何调用"
                    % (yuan, a.budget)) if over_budget else 0)
    if a.json:
        _json_out(rec, a, indent=1, ok=not rec_rc)
    else:
        print("预估成本（一次调用都不发）")
        print("  规模：%d 章 × %d 节 = %d 节" % (a.chapters, a.sections_per_chapter, sections))
        print("  调用次数：%d 次（1 次大纲 + %d 次讲义 + %d 次习题）"
              % (est["calls"], n_lessons, n_quizzes))
        print("  预估 token：prompt %d + completion %d = %d"
              % (est["prompt_tokens"], est["completion_tokens"], est["total_tokens"]))
        print("  预估花费：%.2f 元（≈ %g 点，按 %g 元/千 token）"
              % (yuan, rec["est_points"], rec["yuan_per_ktok"]))
        for n in rec["notes"]:
            print("  · %s" % n)
        if a.budget is not None:
            over = yuan > a.budget
            print("  · 预算 %g 元：%s" % (a.budget, "超了，all 会被拦下" if over else "在预算内"))
    if over_budget:
        sys.stderr.write("\n%s\n" % _red(
            "闸门五：预估 %.2f 元超过 --budget %g 元，all 会在发起调用前停在这里"
            % (yuan, a.budget)))
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
        _json_out(lst, a, indent=1)
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
    print("      课程生产线是纯文本任务，只能选 type_code=text 的模型：`models --type text`。")
    print("用法：run.py plan --topic \"...\" --model <model_code>")
    return 0


# ---------------------------------------------------------------------------
# all：跑完整套（断点续跑）
# ---------------------------------------------------------------------------

def cmd_all(a):
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state = {} if a.force else load_state(outdir)
    tracker = CostTracker(a.budget, a.yuan_per_ktok)

    # ---- 第 1 步：大纲 ----
    plan_file = outdir / "outline.json"
    plan = None
    if not a.force and state.get("outline", {}).get("ok") and plan_file.is_file():
        plan = (json.loads(plan_file.read_text(encoding="utf-8")) or {}).get("plan")
        if plan:
            sys.stderr.write("[1/3] 大纲已完成，跳过（断点续跑，不再重复扣费）\n")
    if plan is None:
        prompt = build_plan_prompt(a.topic, a.level, a.chapters, a.sections_per_chapter,
                                   a.total_minutes, a.audience, a.requirements)
        est = EST_TOKENS["plan"]
        if tracker.over_budget(est["prompt"] + est["completion"]):
            sys.stderr.write("\n%s\n" % _red(
                "闸门五：预估成本已超 --budget %g 元，未发起任何调用" % a.budget))
            return _fail(3, "budget", "预估成本已超 --budget %g 元，未发起任何调用" % a.budget)
        sys.stderr.write("[1/3] 正在用 `%s` 出大纲：%d 章 × %d 节…\n"
                         % (a.model, a.chapters, a.sections_per_chapter))
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                              max_tokens=a.max_tokens, key=a.key,
                              json_mode=not a.no_json_mode,
                              tracker=tracker, tracker_label="plan")
        el = round(time.time() - t0, 1)
        plan = normalize_outline(parse_first_json(content), a.topic, a.level, a.chapters)
        if not plan["chapters"]:
            raise CourseError("模型返回里没有 chapters，大纲是空的（可加大 --max-tokens 或换模型）")
        plan_file.write_text(json.dumps({"plan": plan, "model": a.model, "usage": usage,
                                         "elapsed_sec": el}, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        sys.stderr.write("      %d 章 / %d 节 / %s · %.1fs · usage %s\n" % (
            plan["chapter_count"], plan["section_count"], fmt_minutes(plan["total_minutes"]),
            el, json.dumps(usage, ensure_ascii=False)))
        if not plan["structure_ok"]:
            state["outline"] = {"ok": False}
            save_state(outdir, state)
            for c in plan["structure_checks"]:
                if not c["ok"]:
                    sys.stderr.write("   %s ✗ %s\n" % (c["check"], c["detail"]))
            sys.stderr.write("\n%s\n" % _red(
                "闸门四：大纲结构校验未通过（缺章节 / 缺小节 / 缺学习目标），"
                "后续讲义不会基于这份大纲生成"))
            sys.stderr.write("%s\n" % tracker.line())
            return _fail(3, "gate", "闸门四：大纲结构校验未通过，后续讲义不会基于它生成")
        state["outline"] = {"ok": True}
        save_state(outdir, state)

    (outdir / "outline.md").write_text(
        render_outline_md(plan, a.model) + "\n", encoding="utf-8")

    sections = list(_iter_sections(plan))
    if a.count:
        sections = sections[:a.count]
    lesson_dir = outdir / "lessons"
    quiz_dir = outdir / "quiz"
    lesson_dir.mkdir(exist_ok=True)
    quiz_dir.mkdir(exist_ok=True)

    # ---- 第 2 步：讲义 ----
    per_lesson = EST_TOKENS["lesson"]["prompt"] + EST_TOKENS["lesson"]["completion"]
    for i, (c, s) in enumerate(sections, 1):
        key = state_key(s["no"], "lesson")
        f = lesson_dir / ("%s.md" % s["no"])
        if not a.force and state.get(key, {}).get("ok") and f.is_file():
            sys.stderr.write("[2/3] 讲义 %s 已完成，跳过\n" % s["no"])
            continue
        if tracker.over_budget(per_lesson):
            sys.stderr.write("\n%s\n" % _red("闸门五：成本已达 --budget %g 元，就地停止（%s）"
                                            % (a.budget, tracker.line())))
            save_state(outdir, state)
            return _fail(3, "budget", "成本已达 --budget %g 元，就地停止" % a.budget)
        sys.stderr.write("[2/3] (%d/%d) 正在写讲义 %s《%s》…\n"
                         % (i, len(sections), s["no"], s["title"]))
        prompt = build_lesson_prompt(plan["subject"], _plan_level(plan, a), c, s)
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                              max_tokens=a.max_tokens, key=a.key,
                              json_mode=not a.no_json_mode,
                              tracker=tracker, tracker_label="lesson")
        item = normalize_lesson(parse_first_json(content), s)
        item["elapsed_sec"] = round(time.time() - t0, 1)
        item["usage"] = usage
        f.write_text(item["content"] or "", encoding="utf-8")
        state[key] = {"ok": item["ok"], "chars": item["chars"],
                      "leaks": item["leaks"], "file": str(f)}
        save_state(outdir, state)
        sys.stderr.write("      %d 字 · %.1fs · usage %s\n"
                         % (item["chars"], item["elapsed_sec"],
                            json.dumps(usage, ensure_ascii=False)))

    # ---- 第 3 步：习题 ----
    per_quiz = EST_TOKENS["quiz"]["prompt"] + EST_TOKENS["quiz"]["completion"]
    lesson_files = dict((s["no"], lesson_dir / ("%s.md" % s["no"])) for _c, s in sections)
    for i, (c, s) in enumerate(sections, 1):
        key = state_key(s["no"], "quiz")
        f = quiz_dir / ("%s.json" % s["no"])
        if not a.force and state.get(key, {}).get("ok") and f.is_file():
            sys.stderr.write("[3/3] 习题 %s 已完成，跳过\n" % s["no"])
            continue
        if tracker.over_budget(per_quiz):
            sys.stderr.write("\n%s\n" % _red("闸门五：成本已达 --budget %g 元，就地停止（%s）"
                                            % (a.budget, tracker.line())))
            save_state(outdir, state)
            return _fail(3, "budget", "成本已达 --budget %g 元，就地停止" % a.budget)
        sys.stderr.write("[3/3] (%d/%d) 正在出习题 %s《%s》…\n"
                         % (i, len(sections), s["no"], s["title"]))
        lf = lesson_files.get(s["no"])
        lesson_text = lf.read_text(encoding="utf-8", errors="replace") if (
            lf and lf.is_file()) else None
        prompt = build_quiz_prompt(plan["subject"], _plan_level(plan, a), c, s,
                                   a.per_tier, lesson_text)
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model, temperature=a.temperature,
                              max_tokens=a.max_tokens, key=a.key,
                              json_mode=not a.no_json_mode,
                              tracker=tracker, tracker_label="quiz")
        item = normalize_quiz(parse_first_json(content), s, a.per_tier)
        item["elapsed_sec"] = round(time.time() - t0, 1)
        item["usage"] = usage
        f.write_text(json.dumps(item, ensure_ascii=False, indent=1), encoding="utf-8")
        state[key] = {"ok": item["ok"], "leaks": item["leaks"], "file": str(f)}
        save_state(outdir, state)
        sys.stderr.write("      %d 题 · %.1fs · usage %s\n"
                         % (len(item["questions"]), item["elapsed_sec"],
                            json.dumps(usage, ensure_ascii=False)))

    return _finalize_all(a, outdir, plan, state, tracker, sections, lesson_dir, quiz_dir)


def _finalize_all(a, outdir, plan, state, tracker, sections, lesson_dir, quiz_dir):
    """汇总：合成讲稿、质量报告、闸门汇总、退出码。"""
    failures, checked, lessons, quizzes = [], 0, [], []
    for _c, s in sections:
        ls = state.get(state_key(s["no"], "lesson")) or {}
        qs = state.get(state_key(s["no"], "quiz")) or {}
        checked += (1 if ls else 0) + (1 if qs else 0)
        if ls and not ls.get("ok"):
            failures.append({"no": "讲义 %s" % s["no"], "leaks": ls.get("leaks") or []})
        if qs and not qs.get("ok"):
            failures.append({"no": "习题 %s" % s["no"], "leaks": qs.get("leaks") or []})
        lf = lesson_dir / ("%s.md" % s["no"])
        if lf.is_file():
            lessons.append({"no": s["no"], "title": s["title"],
                            "content": lf.read_text(encoding="utf-8", errors="replace")})
        qf = quiz_dir / ("%s.json" % s["no"])
        if qf.is_file():
            quizzes.append(json.loads(qf.read_text(encoding="utf-8", errors="replace")))

    audit = {"ok": not failures and plan["structure_ok"], "checked": checked,
             "failures": failures, "structure_checks": plan["structure_checks"],
             "structure_ok": plan["structure_ok"],
             "cost": {"calls": tracker.calls, "prompt_tokens": tracker.prompt_tokens,
                      "completion_tokens": tracker.completion_tokens,
                      "total_tokens": tracker.total_tokens, "yuan": tracker.yuan,
                      "yuan_per_ktok": tracker.rate,
                      "estimated_calls": tracker.estimated_flags},
             "model": a.model, "subject": plan["subject"], "level": plan["level_name"]}
    (outdir / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    (outdir / "AUDIT.md").write_text(render_audit_md(audit) + "\n", encoding="utf-8")

    # 合成一份可直接发出去的讲稿
    book = [render_outline_md(plan, a.model), "", "---", ""]
    for ls in lessons:
        book.append("## %s　%s" % (ls["no"], ls["title"]))
        book.append("")
        book.append(re.sub(r"^##\s+.*$", "", ls["content"], count=1, flags=re.M).strip())
        book.append("")
        qz = next((q for q in quizzes if q.get("no") == ls["no"]), None)
        if qz:
            book.append("### 本节习题")
            book.append("")
            for qi, q in enumerate(qz.get("questions") or [], 1):
                book.append("**%d. [%s / %s]** %s" % (qi, q.get("tier_name", ""),
                                                      q.get("type_name", ""), q.get("question", "")))
                for o in q.get("options") or []:
                    book.append("- %s" % o)
                book.append("")
                book.append("- 答案：%s" % q.get("answer", ""))
                book.append("- 解析：%s" % q.get("explain", ""))
                book.append("")
        book.append("")
    (outdir / "course.md").write_text("\n".join(book) + "\n", encoding="utf-8")

    tiers = "/".join("%s×%d" % (n, a.per_tier) for _k, n, _c in QUIZ_TIERS)
    gate_ok = not failures and bool(plan["structure_ok"])
    if a.json:
        # --json 时 stdout 只允许一个完整 JSON（人读小结改由下面 else 分支负责）；
        # ok 如实反映闸门结论，退出码仍是 3
        _json_out({
            "subject": plan["subject"],
            "outdir": str(outdir),
            "outline": ["outline.md", "outline.json"],
            "lessons": len(lessons),
            "quizzes": len(quizzes),
            "quiz_tiers": tiers,
            "course": "course.md",
            "audit": ["AUDIT.md", "audit.json"],
            "cost": tracker.line(),
            "yuan_per_ktok": tracker.rate,
            "gate_failures": [f["no"] for f in failures],
            "structure_ok": plan["structure_ok"],
        }, a, indent=2, ok=gate_ok)
    else:
        print("课程生产线跑完：%s" % plan["subject"])
        print("  输出目录：%s" % outdir)
        print("  大纲：outline.md / outline.json")
        print("  讲义：%d 节（lessons/*.md）" % len(lessons))
        print("  习题：%d 节（quiz/*.json），分层 %s" % (len(quizzes), tiers))
        print("  合计讲稿：course.md")
        print("  质量报告：AUDIT.md / audit.json")
        print("  %s" % tracker.line())
        print("  单价口径是**估算**（%g 元/千 token，可用 --yuan-per-ktok 覆盖），"
              "账单以 api.a7w.cn 控制台为准。" % tracker.rate)
    if a.outdir:
        sys.stderr.write("断点文件：%s（原样重跑即可续跑，已完成的不会重复扣费）\n"
                         % state_path(a.outdir))

    if failures:
        sys.stderr.write("\n%s\n" % _red(
            "闸门：%d 个受检对象命中（违禁词 / 占位符 / 照抄示例 / 缺答案解析 / 分层不全），"
            "详见 %s" % (len(failures), outdir / "AUDIT.md")))
        for f in failures:
            for lk in f["leaks"][:4]:
                sys.stderr.write("   %s  ← %s：%s\n" % (f["no"], lk.get("kind"), lk.get("why")))
        return _fail(3, "gate", "%d 个受检对象命中本地闸门" % len(failures))
    if not plan["structure_ok"]:
        sys.stderr.write("\n%s\n" % _red("闸门四：大纲结构校验未通过"))
        return _fail(3, "gate", "闸门四：大纲结构校验未通过")
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与 sanjianke-portrait-studio 同口径）。

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
                   help="最大输出 token，默认 8192（讲义建议不低于 8192）")
    p.add_argument("--key", help="临时指定 A7W API Key（别写进脚本或文档）")
    p.add_argument("--budget", type=float, default=None,
                   help="成本上限（元，估算口径）。超了就地停，退出码 3")
    p.add_argument("--yuan-per-ktok", type=float, default=None, dest="yuan_per_ktok",
                   help="单价（元/千 token），默认 %g；这只是估算口径" % YUAN_PER_KTOK_DEFAULT)
    _add_json(p)
    if with_out:
        p.add_argument("--out", help="把结果写到这个文件（目录必须存在）")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_level_opts(p, level_only=False):
    p.add_argument("--level", default="zero", choices=LEVEL_CHOICES,
                   help="受众水平：zero(零基础，默认) / basic(入门) / advanced(进阶)"
                        + ("；给了 --plan 时会被大纲里的 level 覆盖" if level_only else ""))
    if level_only:
        return
    p.add_argument("--audience", help="受众补充说明（谁在学、用在什么场景）")
    p.add_argument("--requirements", help="必须覆盖的硬性要求，会原样给到模型")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 课程生产线（走 api.a7w.cn 的 OpenAI 兼容大模型端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="出课程大纲（章节 / 小节 / 学习目标 / 时长）")
    p.add_argument("--topic", required=True, help="课程主题")
    p.add_argument("--chapters", type=int, default=4, help="章数，默认 4")
    p.add_argument("--sections-per-chapter", type=int, default=2,
                   dest="sections_per_chapter", help="每章小节数，默认 2")
    p.add_argument("--total-minutes", type=int, default=None, dest="total_minutes",
                   help="全课时长目标（分钟），默认不约束")
    _add_level_opts(p)
    _add_model_opts(p)
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("lesson", help="按大纲逐节写讲义（每节 1500~3000 字）")
    p.add_argument("--plan", required=True, help="`plan --json --out` 产出的文件")
    p.add_argument("--count", type=int, default=None, help="最多写几节，默认全部")
    p.add_argument("--from-file", dest="from_file",
                   help="**闸门复检用**：不调模型，直接拿一份返回 JSON 过闸门")
    p.add_argument("--level", default="zero", choices=LEVEL_CHOICES, help="受众水平，默认 zero")
    _add_model_opts(p)
    p.set_defaults(func=cmd_lesson)

    p = sub.add_parser("quiz", help="按大纲逐节出习题 + 答案 + 解析（难度分层）")
    p.add_argument("--plan", required=True, help="`plan --json --out` 产出的文件")
    p.add_argument("--count", type=int, default=None, help="最多出几节，默认全部")
    p.add_argument("--per-tier", type=int, default=2, dest="per_tier",
                   help="每档难度出几道题，默认 2（三档共 6 道）")
    p.add_argument("--lessons-file", dest="lessons_file",
                   help="`lesson --json --out` 的结果，给了就让题目严格出自讲义")
    p.add_argument("--from-file", dest="from_file",
                   help="**闸门复检用**：不调模型，直接拿一份返回 JSON 过闸门")
    _add_level_opts(p, level_only=True)
    _add_model_opts(p)
    p.set_defaults(func=cmd_quiz)

    p = sub.add_parser("all", help="跑完整套（大纲 → 讲义 → 习题），断点续跑")
    p.add_argument("--topic", required=True, help="课程主题")
    p.add_argument("--outdir", default="course-out",
                   help="输出目录，默认 course-out；建议指到包外")
    p.add_argument("--chapters", type=int, default=4, help="章数，默认 4")
    p.add_argument("--sections-per-chapter", type=int, default=2,
                   dest="sections_per_chapter", help="每章小节数，默认 2")
    p.add_argument("--total-minutes", type=int, default=None, dest="total_minutes")
    p.add_argument("--count", type=int, default=None, help="最多处理几节，默认全部")
    p.add_argument("--per-tier", type=int, default=2, dest="per_tier",
                   help="每档难度几道题，默认 2")
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑（**会重复扣费**）")
    _add_level_opts(p)
    _add_model_opts(p, with_out=False)
    p.set_defaults(func=cmd_all)

    p = sub.add_parser("cost", help="只算钱，一次调用都不发")
    p.add_argument("--chapters", type=int, default=4, help="章数，默认 4")
    p.add_argument("--sections-per-chapter", type=int, default=2,
                   dest="sections_per_chapter", help="每章小节数，默认 2")
    p.add_argument("--lessons", type=int, default=None, help="实际要写几节讲义，默认全部")
    p.add_argument("--quizzes", type=int, default=None, help="实际要出几节习题，默认全部")
    p.add_argument("--quiz-off", action="store_true", dest="quiz_off", help="不算习题的钱")
    p.add_argument("--budget", type=float, default=None, help="预算上限（元），超了退出码 3")
    p.add_argument("--yuan-per-ktok", type=float, default=None, dest="yuan_per_ktok",
                   help="单价（元/千 token），默认 %g" % YUAN_PER_KTOK_DEFAULT)
    p.add_argument("--model", default=DEFAULT_MODEL, help="只是回显，不影响估算")
    _add_json(p)
    p.set_defaults(func=cmd_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）")
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
    except CourseGate as exc:
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
        _json_fail(rc, reason.get("kind") or kind,
                   reason.get("message") or msg, reason.get("detail"), a)
    return rc


if __name__ == "__main__":
    sys.exit(main())
