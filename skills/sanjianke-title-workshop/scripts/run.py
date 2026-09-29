#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 爆款标题工坊 —— 真正的干活的脚本（零第三方依赖）。

四个子命令：

    gen     给一个主题/产品，生成 N 个标题（默认 30）并四维打分降序输出
    score   给已有的标题清单打分（从参数或文件读）
    ab      基于打分结果给 A/B 测试配对建议（哪两个配对、测哪个变量）
    models  列出 api.a7w.cn 当前在架的模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py models
    python3 run.py gen --topic "便携榨汁杯" --platform xiaohongshu --count 12
    python3 run.py gen --topic "便携榨汁杯" --platform douyin --count 30 --json --out titles.json
    python3 run.py score --file titles.txt --platform wechat
    python3 run.py score --titles "通勤带它出门，我再也没买过奶茶" "这个杯子凭什么卖爆"
    python3 run.py ab --file titles.json
    python3 run.py gen --topic "便携榨汁杯" --dry-run      # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py gen ... --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍
    · 打分是**大模型给语义分 + 本地做确定性扣分**的混合口径：广告法违禁词命中一律压合规分，
      平台的硬性字数上限超了就压平台适配分。这样"模型瞎给高分"骗不过本地闸门。
    · 违禁词表是**启发式自检**，来自公开经验整理，不构成法律意见，也不等于平台官方审核规则。
    · 标题是给人做决策的原料，不是发出去就完事：A/B 一次只改一个变量，这条纪律由人来守。
"""

import argparse
import json
import os
import re
import sys
import traceback
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4
DIM_KEYS = ("click", "info", "platform_fit", "compliance")
DIM_LABEL = {
    "click": "点击欲望",
    "info": "信息量",
    "platform_fit": "平台适配",
    "compliance": "合规",
}
# 四维加权总分（满分 100）：点击欲望是标题的第一职责，给最高权重；
# 合规是底线，权重最低但一票否决（命中违禁词直接压到 1~2 分）。
DIM_WEIGHT = {"click": 0.35, "info": 0.25, "platform_fit": 0.25, "compliance": 0.15}


# ---------------------------------------------------------------------------
# 平台口径：标题公式、字数上限、禁忌
# ---------------------------------------------------------------------------

PLATFORMS = {
    "xiaohongshu": {
        "name": "小红书",
        "limit": 20,
        "tone": "口语、真诚、像朋友安利，不用夸张绝对化词，可以适度用 1~2 个 emoji，标题别写太长",
        "formulas": [
            ("痛点直击", "{人群}总被{痛点}劝退？我找到{解法}了"),
            ("数字清单", "{数字}个{品类}选购要点，第{n}条最容易踩坑"),
            ("身份代入", "月薪{数字}k 也能{结果}，全靠{方法}"),
            ("对比反差", "{a}和{b}我都试过，差别真的大"),
            ("时间承诺", "坚持{d}天{行为}，我的{指标}变了"),
        ],
    },
    "douyin": {
        "name": "抖音",
        "limit": 15,
        "tone": "前 3 个字就要出冲突或悬念，口语到能直接念出来，别用书面语和长定语",
        "formulas": [
            ("悬念钩子", "别急着买{品类}，先看这条"),
            ("反常识", "{常识}其实是错的，{反转}"),
            ("身份冲突", "干了{n}年{职业}，我劝你{建议}"),
            ("结果前置", "{结果}，就靠这一步"),
            ("警告式", "这{数量}种{品类}，千万别买"),
        ],
    },
    "wechat": {
        "name": "公众号",
        "limit": 25,
        "tone": "双段式（主标题+悬念副标题）或完整句，偏理性克制，可以有一点信息势能",
        "formulas": [
            ("双段式", "{主标题}｜{副标题悬念}"),
            ("深度感", "关于{话题}，我研究了{n}份资料后想说几句"),
            ("清单式", "{数字}个{品类}真相，第{n}个很少有人提"),
            ("观点式", "{现象}的背后，是{判断}"),
            ("人物故事", "{人物}用{d}年只做成了一件事，{启示}"),
        ],
    },
    "zhihu": {
        "name": "知乎",
        "limit": 25,
        "tone": "专业、有信息密度，用提问或结论前置，避免情绪化感叹号",
        "formulas": [
            ("提问式", "为什么{现象}？{专业解释}"),
            ("结论前置", "{结论要点}，三个理由"),
            ("经验式", "身为{身份}，{品类}到底该怎么选"),
            ("反直觉", "都说{观点}，但{反例}说明{判断}"),
            ("拆解式", "{品类}的{数量}个关键参数，一次讲清"),
        ],
    },
}
PLATFORM_CHOICES = list(PLATFORMS.keys())


# ---------------------------------------------------------------------------
# 合规自检：广告法违禁词表（确定性，零成本，不依赖模型）
# ---------------------------------------------------------------------------

# 每项：正则 → 风险等级 → 人话解释。这是一道**粗筛**，宁可多报也别漏报，
# 最终判断仍要人工复核，且不等于平台官方审核结论。
BANNED_PATTERNS = [
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎)", "高",
     "广告法第九条禁止「最高级」用语"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    (r"第一(名|品牌|选择|名)?(?!次)|No\.?\s*1|TOP\s*1|排名第一|销量第一", "高",
     "「第一」类排他性表述"),
    (r"国家级|世界级|全球级|国际级|国家级产品", "高",
     "「国家级」等权威性词汇属明令禁止"),
    (r"100\s*%|百分之百|百分百", "高",
     "绝对化效果承诺"),
    (r"绝对(有效|安全|放心|不会|能|可以)|保证(有效|成功|瘦|赚)|无效退款", "高",
     "绝对化保证与效果担保"),
    (r"根治|治愈|痊愈|药到病除|包治|治疗(好|效果)|疗效|无副作用|零副作用", "高",
     "医疗功效宣称，非药品/医疗器械不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报", "高",
     "投资类收益承诺"),
    (r"免费领|免费送|0\s*元购|白送", "中",
     "可能构成虚假优惠或诱导分享"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天", "中",
     "促销时限表述需与实际活动一致"),
    (r"独家|唯一|首个|首创|填补空白|领先(品牌|技术)", "中",
     "排他性表述需有可举证依据"),
    (r"纯天然|无添加|零添加|无毒无害", "中",
     "成分宣称需与检测报告一致"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐", "高",
     "不得虚构权威背书"),
    (r"催情|壮阳|丰胸|减肥(药|神器)|美白针|生发(神器)", "高",
     "特殊功效与特殊品类敏感词"),
    (r"点击链接|加微信|私信我|扫码(加|进)|vx|VX|微信号", "中",
     "站外导流，平台普遍限制"),
    (r"[！!]{2,}|[?？]{3,}", "低",
     "标点堆砌，易被判标题党/低质"),
    (r"(震惊|惊呆|不看后悔|错过再等一年|速看|删前必看)", "中",
     "标题党式诱导"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}
# 合规分压制：命中高/中/低风险时，合规维度的最高分（大模型给几分都压到这以下）
COMPLIANCE_CAP = {"高": 1, "中": 4, "低": 7}


# ---------------------------------------------------------------------------
# 模板污染闸门（跨平台，防复发）
#
# 事故复盘：知乎「结论前置」的模板 `{结论}，三个理由` 让模型把公式名当成了标题前缀，
# 产出 `结论前置：便携榨汁杯不适合三类人`，而且拿了 89.0 分——**全批最高分**。
# 一个带缺陷的标题排到第一，比排到末位糟糕得多：用户只看前三条，第一条就是废的。
# 所以这类检查必须和违禁词一样是**硬闸门**（压分 + 标红 + 汇总），不能只是提示。
#
# 四小类（前三类是本闸门原生形态，第四类 prompt_echo 见下方常量区）：
#   placeholder  标题里残留 `{` 或 `}`（占位符没被替换）
#   formula_name 标题里出现 formula 字段自己报的公式名（公式名被当文案写进去）
#   name_prefix  标题以公式名 + 冒号/顿号/破折号起头（本次事故的具体形态）
#   prompt_echo  标题与提示词里登记过的示例抄得太近（exact / jaccard / contain 三条判据）
# ---------------------------------------------------------------------------

TEMPLATE_CAP = 3.0          # 命中即把合规维封顶到这个分（低于中风险违禁词的 4 分）
# 公式名后紧跟这些分隔符，说明模型把公式名当成了"标签：内容"结构在写。
# 含全角竖线 `｜`：那是公众号「双段式」模板自己的分隔符，同样会带出 `双段式｜xxx` 这种污染。
NAME_SEP = "：:、—－-｜|"
# 与提示词示例的相似度阈值（字符二元组 Jaccard）。
# 实测标定：196 条正常标题与跨主题示例的最高相似度只有 0.174（余量极大），
# 而"少两个字的同构照抄"相似度 0.765。所以 0.75 既能兜住轻改写，
# 又离正常标题的实测上限有 4 倍以上的安全距离。
ECHO_SIM = 0.75

# 覆盖度阈值（第三条判据）：示例的字符二元组里有多大比例出现在产出中。
#
# 【为什么必须有这一条】Jaccard 的分母是两份二元组的**并集**，产出越长，
# 示例那一侧被摊薄得越狠 —— 示例原样嵌进去也会掉到 0.75 以下侥幸放行。
# 本包实测（`_test_echo_contain.py`，示例1「电动车充电桩到底值不值得装，三个理由」，
# 去标点后 17 字 / 16 个二元组）：
#   · 示例原样嵌入 + 补 7 个字 = 24 字（正好在公众号/知乎 25 字上限内）
#     → Jaccard 16/23 = 0.696（旧判据放行 ❌）  覆盖度 16/16 = 1.000（新判据拦下 ✓）
#   · 同一条示例原样嵌进 52 字的产出
#     → Jaccard 0.314（漏）                     覆盖度 1.000（抓住）
# 覆盖度只看"示例被抄了多少"，不看产出有多长，摊薄对它无效。
# 阈值 0.60 的余量实测：34 条真实历史标题 + 同主题对抗样本（充电桩主题 15 条）里，
# 覆盖度最大只有 0.500（余量 1.2 倍），误伤 0 条。
ECHO_CONTAIN = 0.60
# 长度守卫（**相对阈值**）：目标归一化长度 < max(ECHO_MIN_LEN_FLOOR, len(示例)//2) 时，
# 就不比相似度与覆盖度 —— 短串的二元组太少，指标会虚高。
#
# 为什么不用绝对阈值 12：本包的示例只有 15~17 字，12 的绝对门槛占了示例长度的七成以上，
# 会把「≤11 字的截断照抄」整档放过。实测（`_test_echo_contain.py`）：
#   · 「小区充电桩的安装条件别」11 字，对示例2 覆盖度 0.714 → 绝对阈值 12 下**漏掉**
#   · 「电动车充电桩到底值不值得」12 字，覆盖度 0.688 → 本来就拦得住
# 换成相对阈值后：示例 15~17 字 → 门槛 7~8，那一档收回来；同时保留 6 的绝对下限，
# 防止极短串的二元组噪声。旧判据（只有 Jaccard）对这些 ≤11 字的用例本来也是放行，
# 所以这次改动是**净增检测**，不是放宽。
ECHO_MIN_LEN_FLOOR = 6


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


def _has_sep_after(text, pos):
    """pos 位置之后紧跟的是分隔符或串尾吗？"""
    return pos >= len(text) or text[pos] in NAME_SEP


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的标题往往只改标点（`，`↔`、`↔空格），所以必须先抹平标点再看。
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


def prompt_echo(title, samples=None):
    """标题是否与提示词里的示例"抄得太近"。

    三条命中路径（任一即命中）：
      · 去掉标点后**完全相同**（最直接的照抄）
      · 字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
      · 示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（把示例夹带进更长的标题里；
        Jaccard 会被长度摊薄，只有覆盖度抓得住，依据见 ECHO_CONTAIN 上方）

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"，
    没命中时后两项为 (0.0, "", "")。
    """
    target = _norm_for_echo(title)
    if not target:
        return False, 0.0, "", ""
    best_score, best_sample, best_rule = 0.0, "", ""
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        if target == _norm_for_echo(s):
            return True, 1.0, s, "exact"
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(title, s)
        base = _bigrams(s)
        contain = (len(_bigrams(title) & base) / float(len(base))) if base else 0.0
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        if contain >= ECHO_CONTAIN and contain >= best_score:
            best_score, best_sample, best_rule = contain, s, "contain"
    if best_rule:
        return True, best_score, best_sample, best_rule
    return False, best_score, best_sample, ""


def known_formula_names(platform):
    """该平台所有公式名（运行时从 PLATFORMS 取，改了公式这里自动跟着变）。"""
    return [n for n, _tpl in PLATFORMS[platform]["formulas"]]


def _template_leaks(title, formula, platform):
    """扫标题里的模板污染，返回命中列表（可能为空）。

    **为什么不能只信 formula 字段**（踩过坑）：模型在 `formula` 里经常自己发挥，
    实测把 `结论前置` 写成了 `结论前置+人群排除`。如果只拿 formula 的值去标题里找，
    恰好是本次事故那个标题会漏判——闸门就白加了。
    所以判定用两路取并集：
      1. 模型自报的 formula（归一化后）
      2. 该平台**已知的公式名全集**（来自 PLATFORMS，不依赖模型）
    只要标题里出现其中任何一个，就算公式名泄漏。
    """
    leaks = []
    for ch in "{}":
        if ch in title:
            leaks.append(("placeholder", "标题里残留了占位符符号 `{}`，模板没被替换干净".format(ch)))
            break

    names = []
    reported = (formula or "").strip()
    if reported and reported != "-":
        # 归一化：模型爱写 `结论前置+人群排除` / `结论前置/xxx`，切成候选名
        names.extend(p for p in re.split(r"[+＋/、,，\s]+", reported) if len(p) >= 2)
    names.extend(known_formula_names(platform))
    names = list(dict.fromkeys(names))     # 去重保序

    for name in names:
        # 判定收紧的依据（196 条正常标题实测）：
        # 原来的「公式名出现在标题任意位置」误伤 4 条，全部是公式名当成了正常词的一部分——
        # `结论前置条件很重要`（"结论前置条件"）、`清单式写作的三个误区`（讲"清单式"这件事）、
        # `提问式标题的搜索价值`。公式名都是自然中文词组，做无差别子串匹配必然误伤。
        #
        # 所以只在**公式名后面紧跟分隔符或串尾**时才判命中。这样：
        #   命中 `结论前置：便携榨汁杯…` / `双段式｜便携榨汁杯…`（事故形态 + 90 分那条）
        #   放过 `结论前置条件很重要`、`清单式写作的三个误区`
        # 代价：`关于 X，结论前置：xxx` 这种句中形态不判了——但提示词明确禁止公式名入库，
        # 实测两轮 96 条里这种形态 0 条，不值得为它承担误伤。
        pos = title.find(name)
        if pos < 0:
            continue
        end = pos + len(name)
        if not _has_sep_after(title, end):
            continue
        leaks.append(("formula_name", "标题里出现了公式名「{}」，公式名不是文案".format(name)))
        if pos == 0:
            leaks.append(("name_prefix",
                          "标题以「{}{}」起头，把公式名当成了标签前缀".format(
                              name, title[end] if end < len(title) else ""))) 
        break

    # 抄提示词示例：最高分那条如果是"抄标准答案"，排序就废了，所以与模板污染同档处理
    # （压合规分到 TEMPLATE_CAP、标红、stderr 汇总、退出码 3）。
    echoed, score, sample, rule = prompt_echo(title)
    if echoed:
        if rule == "exact":
            leaks.append(("prompt_echo",
                          "标题与提示词示例「{}」去掉标点后完全相同（照抄示例）".format(sample)))
        elif rule == "contain":
            leaks.append(("prompt_echo",
                          "标题有 {:.0f}% 的内容来自提示词示例「{}」"
                          "（覆盖度 ≥ {:.2f} 即判照抄；Jaccard 会随产出变长被摊薄）".format(
                              score * 100, sample, ECHO_CONTAIN)))
        else:
            leaks.append(("prompt_echo",
                          "标题与提示词示例「{}」相似度 {:.2f}，属同构照抄".format(sample, score)))
    return leaks


def compliance_scan(text):
    """扫一遍违禁词，返回命中列表（可能为空）。"""
    hits = []
    for rx, lvl, why in BANNED_RE:
        m = rx.search(text)
        if m:
            hits.append({"word": m.group(0), "level": lvl, "why": why})
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class TitleError(a7w.A7wError):
    """标题生成/打分失败。"""


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.8,
         max_tokens=4096, key=None, timeout=240, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么必须带退避重试：网关的 upstream timeout / HTTP 502 实测很常见，
    标题生成一次就是几十个标题，被一次抖动打断要重跑整批，很亏。
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
                raise TitleError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise TitleError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise TitleError("模型不存在（404）：{}  "
                                 "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise TitleError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise TitleError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 网关把 OpenAI 的返回包了一层 {"code":1,"data":{...}}，两种形态都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise TitleError("模型没返回 choices：{}".format(json.dumps(payload, ensure_ascii=False)[:300]))
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    return content, usage


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    为什么要这么写：模型经常在合法 JSON 后面多吐几个字符（```、解释、第二个对象、
    重复的 } ），直接 json.loads 会炸。这里用 json.JSONDecoder().raw_decode()，
    从一个 { 或 [ 开始试解码，成功就返回，失败就往后挪一个字符接着试。
    """
    if not text:
        raise TitleError("模型返回空内容")
    dec = json.JSONDecoder()
    # 优先剥掉 ```json 围栏，成功率高且快
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
    raise TitleError("模型返回的不是合法 JSON：{}".format(text[:300].replace("\n", " ")))


# ---------------------------------------------------------------------------
# 打分：大模型给语义分 + 本地确定性扣分
# ---------------------------------------------------------------------------

def _clamp(v, lo=1, hi=10):
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def char_len(s):
    """按字符数算长度（中文一个字算一个字符，emoji 一个算一个）。"""
    return len(s or "")


def normalize_item(raw, platform):
    """把模型返回的一条标题收拾成内部结构，并补上本地判定。"""
    pf = PLATFORMS[platform]
    title = str((raw or {}).get("title") or "").strip().strip('"').strip()
    title = re.sub(r"\s+", " ", title)
    scores = {}
    raw_scores = (raw or {}).get("scores") or {}
    for k in DIM_KEYS:
        scores[k] = _clamp(raw_scores.get(k, 5))
    hits = compliance_scan(title)
    # 本地闸门一：违禁词命中 → 压合规分
    if hits:
        cap = min(COMPLIANCE_CAP.get(h["level"], 5) for h in hits)
        scores["compliance"] = min(scores["compliance"], cap)
    # 本地闸门二：模板污染（占位符残留 / 公式名被当文案）→ 压合规分。
    # 跟违禁词同一档处理，因为这两种缺陷在"不可直接发布"这一点上等价。
    formula = str((raw or {}).get("formula") or "").strip() or "-"
    leaks = _template_leaks(title, formula, platform)
    if leaks:
        scores["compliance"] = min(scores["compliance"], TEMPLATE_CAP)
    # 本地闸门三：超平台字数上限 → 压平台适配分
    length = char_len(title)
    over = length - pf["limit"]
    length_ok = over <= 0
    if not length_ok:
        scores["platform_fit"] = min(scores["platform_fit"], 5 if over <= 5 else 3)
    total = sum(scores[k] * DIM_WEIGHT[k] for k in DIM_KEYS) * 10
    return {
        "title": title,
        "formula": formula,
        "hook": str((raw or {}).get("hook") or "").strip(),
        "scores": scores,
        "total": round(total, 1),
        "length": length,
        "length_limit": pf["limit"],
        "length_ok": length_ok,
        "compliance": hits,
        "compliant": not hits,
        "risk": hits[0]["level"] if hits else "",
        "template_leaks": [{"kind": k, "why": w} for k, w in leaks],
        "template_ok": not leaks,
        "why": str((raw or {}).get("why") or "").strip(),
    }


def rank_items(raw_list, platform, count=None):
    items = []
    seen = set()
    for raw in (raw_list or []):
        if not isinstance(raw, dict):
            continue
        it = normalize_item(raw, platform)
        if not it["title"]:
            continue
        key = it["title"]
        if key in seen:          # 标题去重，重复的不占名额
            continue
        seen.add(key)
        items.append(it)
    items.sort(key=lambda x: (-x["total"], x["length"]))
    if count:
        items = items[:count]
    return items


# ---------------------------------------------------------------------------
# 提示词
#
# 【铁律】提示词里**不许出现任何一条可直接复制的完整中文标题**。
#
# 事故复盘（两例，都是实测抓到的「模型锚定示例」）：
#   1. 提示词里写过正例 `结论先说：便携榨汁杯不适合三类人` → 模型直接产出
#      `结论先说：这类产品不适合三类人`
#   2. 提示词里留过 `便携榨汁杯不适合这三类人，理由有三个` → 公众号那一轮最高分
#      89.0 的标题**一字不差就是它**
# 第 2 例性质更重：最高分那条是"抄了标准答案"，不是"真的最好"，而排序是本包的核心产出。
#
# 所以：讲形态只用**描述性语言**或**跨主题示例**（示例主题用电动车充电桩，
# 与榨汁杯这类真实主题明显不搭，模型不会抄过去）。
# 万一以后有人又把示例加回提示词，PROMPT_SAMPLES + prompt_echo 闸门会兜住。
# ---------------------------------------------------------------------------

# 提示词里出现过的示例文本（跨主题，正常不该被抄）。新增示例必须登记到这里。
PROMPT_SAMPLES = [
    "电动车充电桩到底值不值得装，三个理由",
    "小区充电桩的安装条件，别只看价格",
]


def _formula_block(platform):
    pf = PLATFORMS[platform]
    lines = []
    for i, (name, tpl) in enumerate(pf["formulas"], 1):
        lines.append("{}. {}：{}".format(i, name, tpl))
    return "\n".join(lines)


def build_system_prompt(platform):
    pf = PLATFORMS[platform]
    return (
        "你是三剪客团队的新媒体标题编辑，服务小红书 / 抖音 / 公众号 / 知乎四个平台。\n"
        "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
        "你写的标题必须能被真实发布：不编造数据、不虚构权威背书、不使用广告法违禁词"
        "（最/第一/国家级/100%/根治/绝对 等一律不许出现）。"
    )


def build_gen_prompt(topic, platform, count, product=None, audience=None,
                     evidence=None, temperature_note=True):
    pf = PLATFORMS[platform]
    extra = []
    if product:
        extra.append("产品/服务名：{}".format(product))
    if audience:
        extra.append("目标人群：{}".format(audience))
    if evidence:
        extra.append("可用且**必须真实**的证据（只能用这些，不许自己编数字）：{}".format(evidence))
    else:
        extra.append("没有提供任何真实数据，因此**不许编造**具体数字、销量、检测结论、专家背书；"
                     "只能做不依赖数据的表达")
    return """请为下面的主题写 {count} 个**{pname}**风格的标题，并逐个打分。

主题：{topic}
{extra}

{pname}的硬性口径：
- 字数上限：{limit} 个字符（含标点与 emoji，一个 emoji 算 1 个字符），超了就不合格
- 语感要求：{tone}

本平台的标题公式，请覆盖尽量多的公式，同一条公式不要用超过 4 次：
{formulas}

公式的读法（很重要，踩过坑）：
- `{{}}` 里的文字是**待替换的占位符说明**，必须换成与主题贴合的**真实内容**
- **绝不能原样输出 `{{}}` 或里面的占位符名**，也**绝不能把公式名本身当文案写进标题**
- 判断标准：标题的第一个词必须就是**内容**（比如"为什么…""三个理由…""这类产品…"），
  绝不能是"结论前置""数字清单""双段式"这种**套路口径的名字**
- 下面用**另一个主题**演示形态上的对错，请只体会结构，不要照抄内容、也不要改主题：
  - 错的写法：先写套路名，再用冒号接一句内容
  - 对的写法：先给出判断或疑问，紧接着给理由或结论，全程不带任何前缀

主题词的使用：
- 不要让每条标题都以完整主题词「{topic}」开头，**以它开头的标题不要超过一半**，
  其余用"它/这杯子/这类产品"等代词或场景词替换，避免整批标题看起来像同一个模板
- 但不要为了凑这个比例把每条的第一个词都换掉：留出自然分布即可

打分口径（每项 1~10 的整数，别都给高分，要拉开差距）：
- click（点击欲望）：陌生人刷到会不会停一下。平铺直叙给 3~5，有真钩子才给 8 以上
- info（信息量）：看完标题是否已经知道"能得到什么"。空喊情绪给 2~4
- platform_fit（平台适配）：是否符合上面的字数和语感口径
- compliance（合规）：是否有绝对化用语、虚假承诺、医疗/投资功效、站外导流。干净给 9~10

只输出一个 JSON 对象，结构如下（不要输出别的任何东西）：
{{"titles":[{{"title":"标题原文","formula":"用的公式名","hook":"一句话说钩子在哪","scores":{{"click":8,"info":7,"platform_fit":9,"compliance":10}},"why":"一句话说这条为什么可能爆"}}]}}

{tnote}""".format(
        count=count, pname=pf["name"], topic=topic,
        extra="\n".join(extra) + "\n", limit=pf["limit"], tone=pf["tone"],
        formulas=_formula_block(platform),
        tnote=("尽量让 {0} 条标题的钩子类型分散开，方便后续做 A/B 测试。".format(count)
               if temperature_note else ""),
    )


def build_score_prompt(titles, platform):
    pf = PLATFORMS[platform]
    lst = "\n".join("{}. {}".format(i, t) for i, t in enumerate(titles, 1))
    return """给下面已有的标题逐个打分，并各写一句改进建议。不要改写标题原文。

平台：{pname}（字数上限 {limit} 字符；语感：{tone}）

标题清单：
{titles}

打分口径（每项 1~10 的整数，要拉开差距，别一律给高分）：
- click（点击欲望）：陌生人刷到会不会停一下
- info（信息量）：看完是否知道能得到什么
- platform_fit（平台适配）：字数与语感是否符合 {pname}
- compliance（合规）：绝对化用语 / 虚假承诺 / 医疗投资功效 / 站外导流。干净给 9~10

只输出一个 JSON 对象，不要输出别的：
{{"titles":[{{"title":"标题原文（逐字照抄，不要改）","formula":"可归到哪类钩子","hook":"钩子在哪","scores":{{"click":8,"info":7,"platform_fit":9,"compliance":10}},"why":"一句话说这条的优劣"}}]}}""".format(
        pname=pf["name"], limit=pf["limit"], tone=pf["tone"], titles=lst)


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """合规命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "⚠️ " + s
    return "\x1b[31m{}\x1b[0m".format(s)


def render_md(items, topic, platform, model, usage, elapsed, mode="gen"):
    pf = PLATFORMS[platform]
    out = []
    out.append("# 标题工坊 · {}｜{}".format(mode == "gen" and "生成" or "打分", pf["name"]))
    out.append("")
    out.append("- 主题/输入：{}".format(topic or "（打分已有标题）"))
    out.append("- 平台口径：{}，字数上限 {} 字符".format(pf["name"], pf["limit"]))
    out.append("- 模型：`{}`　命令端点：`POST /api/v1/chat/completions`".format(model))
    out.append("- 产出：{} 条（按加权总分降序）".format(len(items)))
    if usage:
        out.append("- token 用量：prompt={} completion={} total={}".format(
            usage.get("prompt_tokens", "-"), usage.get("completion_tokens", "-"),
            usage.get("total_tokens", "-")))
    if elapsed:
        out.append("- 耗时：{:.1f}s".format(elapsed))
    out.append("")

    bad = [i for i in items if not i["compliant"]]
    over = [i for i in items if not i["length_ok"]]
    tpl = [i for i in items if not i["template_ok"]]
    if bad or over or tpl:
        out.append("> ⚠️ 本地自检：{} 条命中违禁词、{} 条模板污染（公式名/占位符泄漏）、"
                   "{} 条超字数上限。命中项已压分并标红，发布前必须人工复核。".format(
                       len(bad), len(tpl), len(over)))
    else:
        out.append("> ✅ 本地自检：{} 条全部未命中内置违禁词表、无模板污染，且字数全部达标。".format(
            len(items)))
    out.append("")

    out.append("## 排行")
    out.append("")
    out.append("| # | 标题 | 点击欲望 | 信息量 | 平台适配 | 合规 | 总分 | 字数 | 公式 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for i, it in enumerate(items, 1):
        s = it["scores"]
        title = it["title"]
        flag = ""
        if not it["compliant"]:
            flag += " ⚠️" + "".join("[{}]".format(h["word"]) for h in it["compliance"])
        if not it["template_ok"]:
            flag += " ⚠️模板污染"
        if not it["length_ok"]:
            flag += " ⚠️超{}字".format(it["length"] - it["length_limit"])
        out.append("| {} | {}{} | {} | {} | {} | {} | **{}** | {}/{} | {} |".format(
            i, title, flag, s["click"], s["info"], s["platform_fit"], s["compliance"],
            it["total"], it["length"], it["length_limit"], it["formula"]))
    out.append("")

    out.append("## 逐条说明")
    out.append("")
    for i, it in enumerate(items, 1):
        head = "{}. **{}**（{} 分）".format(i, it["title"], it["total"])
        if not it["compliant"] or not it["template_ok"]:
            head = _red(head)
        out.append(head)
        if it["hook"]:
            out.append("   - 钩子：{}".format(it["hook"]))
        if it["why"]:
            out.append("   - 判断：{}".format(it["why"]))
        if not it["template_ok"]:
            for lk in it["template_leaks"]:
                out.append("   - 🧩 模板污染（{}）：{}".format(lk["kind"], lk["why"]))
        if not it["compliant"]:
            for h in it["compliance"]:
                out.append("   - 🚫 合规：命中「{}」（{}风险）——{}".format(
                    h["word"], h["level"], h["why"]))
        if not it["length_ok"]:
            out.append("   - ✂️ 字数：{} 字符，超 {} 字符上限 {} 字，需删减".format(
                it["length"], pf["name"], it["length"] - it["length_limit"]))
    out.append("")
    out.append("下一步：`python3 run.py ab --file <上面的 JSON 结果>` 拿 A/B 配对建议。")
    return "\n".join(out)


def render_ab_md(items, platform, pairs):
    pf = PLATFORMS[platform]
    out = []
    out.append("# A/B 测试配对建议 · {}".format(pf["name"]))
    out.append("")
    out.append("> 纪律：**一次只改一个变量**。两个标题如果在钩子、句式、信息结构上全都不一样，"
               "就算跑出胜负你也学不到东西。下面每一对都只在标注的那**一个变量**上不同。")
    out.append("")
    out.append("## 执行前提")
    out.append("")
    out.append("- 指标口径统一：曝光量、点击率（CTR）、完播/阅读时长；主指标只看 **CTR**")
    out.append("- 每对至少各 2000 次曝光再看结果，低于这个量级不要下结论")
    out.append("- 同一对的两个标题必须**同时段、同素材、同人群**跑，别一个发早上一个发晚上")
    out.append("- 只把**合规**的标题拿去测；命中违禁词的先改完再说")
    out.append("")
    out.append("## 配对清单")
    out.append("")
    out.append("| 组 | A（分数） | B（分数） | 测试变量 | 归因说明 |")
    out.append("|---|---|---|---|---|")
    for i, p in enumerate(pairs, 1):
        a, b = p["a"], p["b"]
        out.append("| {} | {}（{}） | {}（{}） | {} | {} |".format(
            i, a["title"], a["total"], b["title"], b["total"], p["variable"], p["hypothesis"]))
    out.append("")
    out.append("## 变量定义与判读")
    out.append("")
    out.append("| 变量 | 说明 | 谁赢说明什么 |")
    out.append("|---|---|---|")
    out.append("| 钩子类型 | 只换钩子，后半句保留 | 你的受众吃哪一类开头，后续批量套用赢家 |")
    out.append("| 句式结构 | 陈述句 / 疑问句 / 祈使句互换 | 疑问句赢 = 受众有未解问题；祈使句赢 = 指令更有效 |")
    out.append("| 信息密度 | 只加/只减一个具体信息点 | 加信息赢 = 受众要决策依据；减信息赢 = 钩子本身够强 |")
    out.append("| 人称视角 | 第一人称「我」/ 第二人称「你」/ 第三人称 | 决定标题的代入感强弱 |")
    out.append("| 数字 vs 文字 | 只把「三个」换成「3 个」 | 影响扫读速度，最容易出显著差异也最容易是噪声 |")
    out.append("| 字数长短 | 只增删限定词 | 短视频平台通常短优，图文平台未必 |")
    out.append("")
    if len(items) < 4:
        out.append("> 提示：可配对的标题少于 4 条，建议先用 `gen --count 20` 多生成一些再配对。")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# A/B 配对（纯本地确定性逻辑，不再花 token）
# ---------------------------------------------------------------------------

def _kw(t):
    return set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}|\d+", t or ""))


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def _classify_variable(a, b):
    """判断这一对标题的差异主要落在哪个变量上。

    同公式的一对骨架一样，差异只可能来自这几处。判定顺序按"可归因性"排：
    数字 → 人称 → 字数 → 句式 → 信息密度（默认兜底）。

    注意这里的每一条都必须**站得住**才算——判错变量比不判还糟，
    因为它会让你按错误的结论去调整下一批标题。
    """
    ta, tb = a["title"], b["title"]

    def arabic(t):
        """只认阿拉伯数字。中文数字（"三个"）不是数字形式差异，是措辞差异。"""
        return set(re.findall(r"\d+", t))

    zh_num = re.compile(r"[一二三四五六七八九十]+")
    za, zb = arabic(ta), arabic(tb)
    zh_a, zh_b = zh_num.findall(ta), zh_num.findall(tb)

    # 1) 数字 vs 文字：一边阿拉伯数字、一边中文数字，且数量对得上
    if za and zh_b and len(za) == len(zh_b):
        return "数字 vs 文字", "只把中文数字换成了阿拉伯数字，是最干净也最容易出显著性的一类差异"
    if zb and zh_a and len(zb) == len(zh_a):
        return "数字 vs 文字", "只把中文数字换成了阿拉伯数字，是最干净也最容易出显著性的一类差异"
    # 1b) 两边都是阿拉伯数字但数值不同（"4 个" vs "3 个"）：数字本身是变量
    if za and zb and za != zb:
        return "数字 vs 文字", "只换了具体数字（{}→{}），测的是数量对点击的影响".format(
            "/".join(sorted(za)), "/".join(sorted(zb)))

    # 2) 人称视角：叙述人称不同
    pronoun = {"我": "第一人称", "你": "第二人称", "他": "第三人称", "她": "第三人称"}
    pa = {v for k, v in pronoun.items() if k in ta}
    pb = {v for k, v in pronoun.items() if k in tb}
    if pa != pb:
        return "人称视角", "两边的叙述人称不同，测的是代入感强弱"

    # 3) 字数长短：骨架相同，但一边明显更长/更短
    if abs(a["length"] - b["length"]) >= 5:
        return "字数长短", "骨架相同但长度差 {} 字，测的是扫读成本".format(
            abs(a["length"] - b["length"]))

    # 4) 句式结构：疑问句 ↔ 陈述句
    q = lambda t: t.endswith("？") or t.endswith("?")
    if q(ta) != q(tb):
        return "句式结构", "一边是疑问句一边是陈述句，测的是受众有没有未解问题"

    # 5) 兜底：信息密度。再看差异究竟落在前半句还是后半句，好写假设
    head_a, _, tail_a = ta.partition("，")
    head_b, _, tail_b = tb.partition("，")
    if head_a == head_b and tail_a != tail_b:
        return "信息密度", "前半句完全相同，只换了后半句给出的信息量"
    if tail_a == tail_b and head_a != head_b:
        return "信息密度", "后半句完全相同，只换了前半句的切入角度"
    return "信息密度", "字数与句式都接近，差异在具体信息点的增删"


def pick_pairs(items, limit=5):
    """挑「只差一个变量」的标题对。

    做法：先按公式名分组（同公式 = 钩子相同，差异来自句式/数字/人称），
    同组内取相似度最高的一对——相似度高说明句子骨架一样，差异真的只在细处，
    这样跑出来的胜负才可归因。组内不够就从全量里按相似度补。
    """
    ok = [i for i in items if i["compliant"] and i["length_ok"]] or list(items)
    by_formula = {}
    for it in ok:
        by_formula.setdefault(it["formula"], []).append(it)

    pairs, used = [], set()

    def add(a, b, variable, hypothesis):
        key = tuple(sorted((a["title"], b["title"])))
        if key in used:
            return False
        used.add(key)
        pairs.append({"a": a, "b": b, "variable": variable, "hypothesis": hypothesis})
        return True

    # 第一轮：同公式内配对（最干净的归因）
    for formula, group in by_formula.items():
        if len(group) < 2 or len(pairs) >= limit:
            continue
        best, best_sim = None, -1.0
        for x in range(len(group)):
            for y in range(x + 1, len(group)):
                a, b = group[x], group[y]
                sim = _jaccard(_kw(a["title"]), _kw(b["title"]))
                if sim > best_sim:
                    best, best_sim = (a, b), sim
        if best:
            a, b = best
            variable, why = _classify_variable(a, b)
            add(a, b, variable, "同一钩子下{}——{}".format(variable, why))

    # 第二轮：跨公式按相似度补（骨架近似但钩子不同 → 测钩子）
    if len(pairs) < limit:
        cand = []
        for x in range(len(ok)):
            for y in range(x + 1, len(ok)):
                a, b = ok[x], ok[y]
                cand.append((_jaccard(_kw(a["title"]), _kw(b["title"])), a, b))
        cand.sort(key=lambda c: -c[0])
        for sim, a, b in cand:
            if len(pairs) >= limit:
                break
            if sim <= 0:
                continue
            shared = "、".join(list(_kw(a["title"]) & _kw(b["title"]))[:3]) or "无"
            if add(a, b, "钩子类型",
                   "共有词是「{}」，钩子不同，对比哪类开头更抓人".format(shared)):
                continue
    return pairs[:limit]


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def _read_titles(a):
    """收集标题：位置参数 + --titles + --file 三处都收，去空去重。

    位置参数与 --titles 是两个不同的 dest（title_args / titles）：
    argparse 里同名会让 `run.py score --titles A B` 被位置参数先吃掉一条，
    这是踩过的坑，别改回去。
    """
    titles = []
    titles.extend(getattr(a, "title_args", None) or [])
    if getattr(a, "titles", None):
        titles.extend(a.titles)
    if getattr(a, "file", None):
        p = Path(a.file)
        if not p.is_file():
            raise TitleError("找不到文件：{}".format(p))
        raw = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix.lower() == ".json":
            obj = parse_first_json(raw)
            if isinstance(obj, dict):
                for it in (obj.get("titles") or obj.get("items") or []):
                    if isinstance(it, dict):
                        titles.append(str(it.get("title") or ""))
                    elif isinstance(it, str):
                        titles.append(it)
            elif isinstance(obj, list):
                for it in obj:
                    titles.append(it if isinstance(it, str) else str((it or {}).get("title") or ""))
        else:
            for line in raw.splitlines():
                line = line.strip()
                line = re.sub(r"^\s*(?:[-*]|\d+[.、)])\s*", "", line)
                if line and not line.startswith("#"):
                    titles.append(line)
    seen, out = set(), []
    for t in (t.strip() for t in titles):
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _run_gen(a):
    pf = PLATFORMS[a.platform]
    if not (a.topic or "").strip():
        raise TitleError("请用 --topic 给一个主题，例如 --topic \"便携榨汁杯\"")
    prompt = build_gen_prompt(a.topic, a.platform, a.count, a.product,
                              a.audience, a.evidence)
    if a.dry_run:
        # --json 时 stdout 必须是**单个完整 JSON**，所以 dry-run 也包成 JSON
        if a.json:
            _json_out({"dry_run": True, "platform": a.platform,
                       "system": build_system_prompt(a.platform), "user": prompt},
                      a, indent=2)
        else:
            print("=== system ===\n{}\n\n=== user ===\n{}".format(
                build_system_prompt(a.platform), prompt))
        return 0
    sys.stderr.write("正在用 `{}` 生成 {} 个{}标题…\n".format(
        a.model, a.count, pf["name"]))
    t0 = time.time()
    content, usage = chat(prompt, build_system_prompt(a.platform), model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    obj = parse_first_json(content)
    raw_list = obj.get("titles") if isinstance(obj, dict) else obj
    if not isinstance(raw_list, list):
        raise TitleError("模型返回里没有 titles 数组")
    items = rank_items(raw_list, a.platform, a.count)
    if not items:
        raise TitleError("模型没产出任何可用标题，可加大 --max-tokens 或换模型重试")
    result = {"topic": a.topic, "platform": a.platform, "model": a.model,
              "usage": usage, "elapsed": round(elapsed, 1), "titles": items}
    return _emit(a, result, render_md(items, a.topic, a.platform, a.model, usage, elapsed, "gen"))


def _run_score(a):
    titles = _read_titles(a)
    if not titles:
        raise TitleError("没读到标题。用 --titles \"标题1\" \"标题2\" 或 --file 标题.txt/.json")
    prompt = build_score_prompt(titles, a.platform)
    if a.dry_run:
        # 同上：--json 时只吐一个 JSON
        if a.json:
            _json_out({"dry_run": True, "platform": a.platform,
                       "titles": titles, "prompt": prompt}, a, indent=2)
        else:
            print(prompt)
        return 0
    sys.stderr.write("正在用 `{}` 给 {} 条标题打分…\n".format(a.model, len(titles)))
    t0 = time.time()
    content, usage = chat(prompt, build_system_prompt(a.platform), model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    obj = parse_first_json(content)
    raw_list = obj.get("titles") if isinstance(obj, dict) else obj
    if not isinstance(raw_list, list):
        raise TitleError("模型返回里没有 titles 数组")
    # 打分场景：模型偶尔漏几条，用原文兜底，保证一条不丢
    got = {str((r or {}).get("title") or "").strip() for r in raw_list if isinstance(r, dict)}
    for t in titles:
        if t not in got:
            raw_list.append({"title": t, "formula": "-", "hook": "",
                             "scores": {}, "why": "模型未打分，本地按默认分兜底"})
    items = rank_items(raw_list, a.platform, None)
    result = {"platform": a.platform, "model": a.model, "usage": usage,
              "elapsed": round(elapsed, 1), "titles": items}
    return _emit(a, result, render_md(items, None, a.platform, a.model, usage, elapsed, "score"))


def _emit(a, result, md):
    # 先把闸门结论算出来：`ok` 要如实反映"这批能不能直接用"（命中闸门 → ok=false），
    # 而退出码仍是 3，语义不变。
    bad = [i for i in result["titles"] if not i["compliant"]]
    tpl = [i for i in result["titles"] if not i.get("template_ok", True)]
    rc = 0
    if bad or tpl:
        rc = 3
    text = _json_text(result, indent=2, ok=not rc) if a.json else md
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    if a.json:
        _json_write(text)
    else:
        print(text)
    if bad:
        sys.stderr.write("\n⚠️ {} 条标题命中内置违禁词表，发布前必须人工复核：\n".format(len(bad)))
        for it in bad:
            sys.stderr.write("   {}  ← 命中 {}\n".format(
                it["title"], "、".join(h["word"] for h in it["compliance"])))
        rc = 3
    if tpl:
        sys.stderr.write("\n🧩 {} 条标题存在模板污染（公式名/占位符泄漏，或抄了提示词示例），"
                         "不可直接发布：\n".format(len(tpl)))
        for it in tpl:
            sys.stderr.write("   {}  ← {}\n".format(
                it["title"], "；".join(lk["why"] for lk in it["template_leaks"])))
        rc = 3
    return rc


def _run_ab(a):
    if a.file:
        p = Path(a.file)
        if not p.is_file():
            raise TitleError("找不到文件：{}".format(p))
        obj = parse_first_json(p.read_text(encoding="utf-8", errors="replace"))
        raw_list = obj.get("titles") if isinstance(obj, dict) else obj
        platform = a.platform or (obj.get("platform") if isinstance(obj, dict) else None) or "xiaohongshu"
        items = rank_items(raw_list, platform, None)
    else:
        titles = _read_titles(a)
        if not titles:
            raise TitleError("没读到标题。用 --file <gen --json 的结果> 或 --titles ...")
        platform = a.platform or "xiaohongshu"
        items = rank_items([{"title": t} for t in titles], platform, None)
    if not items:
        raise TitleError("没有可用于配对的标题")
    pairs = pick_pairs(items, a.pairs)
    md = render_ab_md(items, platform, pairs)
    if a.json:
        _json_out({"platform": platform, "pairs": pairs, "titles": items}, a, indent=2)
    else:
        print(md)
    if a.out:
        Path(a.out).write_text((_json_text({"platform": platform, "pairs": pairs,
                                            "titles": items}, indent=2)
                                if a.json else md) + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    return 0


def _run_models(a):
    key = a7w.load_key(a.key)
    try:
        payload = a7w._request("GET", MODELS_URL, key, timeout=60)
    except a7w.A7wError as exc:
        sys.stderr.write("拉模型清单失败：{}\n".format(exc))
        return _fail(4, "call", "拉取模型清单失败（网络 / 鉴权 / Key）")
    lst = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(lst, dict):
        lst = lst.get("data") or lst.get("list") or []
    lst = [m for m in (lst or []) if isinstance(m, dict)]
    if a.type and a.type != "all":
        lst = [m for m in lst if str(m.get("type_code")) == a.type]
    if a.json:
        _json_out(lst, a, indent=1)
        return 0
    print("在架模型 {} 个（{}）\n".format(len(lst), MODELS_URL))
    for m in lst:
        print("  {:<26} {:<8} call_type={}  {:<28} {}".format(
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            m.get("call_type"), str(m.get("vendor_name") or "-"),
            str(m.get("model_name") or "")[:24]))
    print("")
    print("提示：模型名会变，以本命令现查为准，别写死在脚本里。")
    print("      `{}` 实测可用（路由到 deepseek-flash），但它**不在**上面这份列表里，".format(DEFAULT_MODEL))
    print("      所以「列表里没有」不等于「不能用」。")
    print("用法：run.py gen --topic \"...\" --model <model_code>")
    return 0


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
# 信封必须落在**真 stdout**：所有 JSON 文本都经 `_json_write` 写，绕开任何临时的 stdout 重定向。
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


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与 sanjianke-portrait-studio 同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py gen ... --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_model_opts(p, platform_default="xiaohongshu"):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 {}（实测可用；用 `run.py models` 现查在架模型）".format(DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.8, help="采样温度，默认 0.8")
    p.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens",
                   help="最大输出 token，默认 4096（30 条标题建议不低于 4096）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--out", help="把结果写到这个文件")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


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
        description="三剪客 · 爆款标题工坊（走 api.a7w.cn 的 OpenAI 兼容大模型端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("gen", help="生成 N 个标题并四维打分降序输出")
    p.add_argument("--topic", required=True, help="主题 / 产品 / 选题")
    p.add_argument("--platform", default="xiaohongshu", choices=PLATFORM_CHOICES,
                   help="平台风格，默认 xiaohongshu")
    p.add_argument("--count", type=int, default=30, help="要几条标题，默认 30")
    p.add_argument("--product", help="产品名（可与 topic 不同）")
    p.add_argument("--audience", help="目标人群")
    p.add_argument("--evidence", help="可用的真实证据（实测数据/检测报告），没写就不许编数字")
    _add_model_opts(p)
    p.set_defaults(func=_run_gen)

    p = sub.add_parser("score", help="给已有标题清单打分（参数或文件）")
    p.add_argument("title_args", nargs="*", help="直接跟在命令后的标题，可写多条")
    p.add_argument("--titles", nargs="+", help="与位置参数等价，便于脚本里书写")
    p.add_argument("--file", help="从文件读标题（.txt 一行一条；.json 读 gen --json 的结果）")
    p.add_argument("--platform", default="xiaohongshu", choices=PLATFORM_CHOICES,
                   help="按哪个平台的口径打分，默认 xiaohongshu")
    _add_model_opts(p)
    p.set_defaults(func=_run_score)

    p = sub.add_parser("ab", help="给 A/B 测试配对建议（哪两个配对、测什么变量）")
    p.add_argument("--file", help="gen --json --out 的结果文件（推荐）")
    p.add_argument("title_args", nargs="*", help="也可直接给标题")
    p.add_argument("--titles", nargs="+", help="与位置参数等价")
    p.add_argument("--platform", choices=PLATFORM_CHOICES, help="平台口径，默认跟随结果文件")
    p.add_argument("--pairs", type=int, default=5, help="最多给几对，默认 5")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_ab)
    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）")
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部 75 个")
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
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
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
