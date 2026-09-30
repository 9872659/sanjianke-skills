#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 评审委员会 —— 真正干活的脚本（零第三方依赖）。

**产品线 L3（多智能体协作型）· 对抗式**：不是"一个声音自我迭代"，也不是
"角色按顺序接力"，而是**四个立场各自独立评审 → 当面对质 → 出裁决书**。

八个子命令：

    seats    列出四个席位的立场与目标函数（纯本地，零成本）
    brief    把待评方案整理成评审材料（纯本地，零成本：大纲 / 主张 / 数字 / 本地预扫）
    panel    四席**独立评审**（信息隔离：四席互相看不到对方的意见）
    clash    对质：把四份意见放一起，找出**真实分歧**并逐点辩
    verdict  裁决书：结论（通过/有条件通过/否决）+ 条件清单 + **少数派意见保留在案**
    run      一条命令跑完整评审（brief → panel → clash → verdict），带断点续跑
    cost     报价：这次评审大概花多少 token（金额要你自己填单价）
    models   列出 api.a7w.cn 当前在架的文本模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py seats
    python3 run.py brief   --file 方案.md --json --out brief.json
    python3 run.py panel   --file 方案.md --outdir D:/board --json
    python3 run.py clash   --file 方案.md --panel D:/board/panel.json --json
    python3 run.py verdict --file 方案.md --panel D:/board/panel.json \
                           --clash D:/board/clash.json --json
    python3 run.py run     --file 方案.md --outdir D:/board --budget 200 \
                           --price-in 1000 --price-out 2000 --json
    python3 run.py cost    --file 方案.md --rounds 6
    python3 run.py panel   --file 方案.md --dry-run        # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py panel --file 方案.md --key sk-xxxx
    export A7W_API_KEY=sk-xxxx     # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍（这一节是本包与同族其它包的**分界线**）
    · 与 L2 闭环（sanjianke-content-qc）的差别不是"多几个评分维度"。L2 是一个声音
      拿一张加权评分表自我迭代到收敛；本包**不追求收敛**，它要把分歧**摊开**：
      谁支持、谁反对、争点是什么、怎么裁。产出是一份裁决书，不是一份更高的分数。
    · 与流水线式 L3（sanjianke-content-team）的差别是**方向**。流水线是角色按顺序
      接力，后一个审前一个；本包是四个立场**同时**独立评审（互相看不到），
      然后在 clash 里正面对质。上游是"一份已有方案"，不是"一个选题"。
    · **信息隔离是机制，不是修辞**：panel 阶段是四次独立调用，每次的提示词里
      只有本席位的立场块，没有其它席位的任何文字（见 isolation 证据）。
      这样才能保证四个结论是四个立场各自算出来的，而不是一次回答的四种复述。
    · **不采信模型自报的立场差异**：本地算四席意见的**重叠度**（二元组覆盖），
      高度重合就判「立场失效」（闸门五）——四个角色说同样的话不算协作，
      也不算"一致通过"。这一条是本包最值钱的闸门。
    · 「引用原文」不靠提示词求模型配合，而是**本地校验引文**（见 verify_anchor）：
      意见必须锚定到材料原文的某一句，对质必须锚定到某个席位自己说过的话。
      编造的引文会被剔出并计入未锚定率，超阈值判「定位失败」。
"""

import argparse
import hashlib
import json
import os
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

# 退出码。数值与全族对齐：
EXIT_OK = 0            # 裁决出来了，且没有任何硬闸门命中
EXIT_USAGE = 2         # 参数/配置错（文件不存在、席位名错、--outdir 在包内、--budget 没配单价）
EXIT_GATE = 3          # 硬闸门命中（合规/占位符/照抄示例/评审锚点/立场失效/裁决不完整）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。
# 事故复盘（同族踩过）：改了席位立场或闸门口径却不改 key，续跑会把上一版口径的旧产物
# 当成"已完成"直接复用，产出对不上文档。加版本号是最省事的根治办法。
RUBRIC_VERSION = "board-rubric-1.0.0"
PROMPT_VERSION = "board-prompt-1.0.0"
SEATS_VERSION = "board-seats-1.0.0"


# ---------------------------------------------------------------------------
# 四个席位：每个席位一个**独立目标函数**与一组**天然倾向**
#
# 设计要点（这是本包能成立的前提）：四个目标函数必须**真的会互相否掉对方**，
# 不能是同一件事的四个措辞。所以每个席位都带一句 `must_have`（最不能让步的一点）
# 和一句 `kill_switch`（什么情况下主张否决）——这两个字段结构性地逼出分歧：
# 业务负责人要加 CTA 的时候，合规官正好在拦那句承诺；用户代言人嫌术语多的时候，
# 竞品分析师正好觉得那些术语就是差异化。
#
# 注意：席位只有立场，没有"最终决定权"。裁决由 verdict 阶段（主席视角）出，
# 且必须把少数派意见原样留给用户看 —— 抹平分歧是本包明令禁止的。
# ---------------------------------------------------------------------------

SEATS = [
    {
        "id": "user_advocate",
        "name": "用户代言人",
        "icon": "用户",
        "goal": "用户看完会不会觉得有用、会不会觉得被骗",
        "bias": "挑自嗨、术语堆砌、承诺不清、把内部视角当成用户视角",
        "question": "站在一个**普通用户**的位置上：这段话对他有什么用？他凭什么信？他会不会觉得被绕了？",
        "focus": [
            "这份东西是给谁看的，那个人凭什么在 30 秒内相信它",
            "承诺能不能兑现，兑现之后用户具体得到什么",
            "有没有术语/黑话/内部代号把普通人挡在门外",
            "有没有把「我们做了什么」当成「用户得到什么」",
        ],
    },
    {
        "id": "competitor_analyst",
        "name": "竞品分析师",
        "icon": "竞品",
        "goal": "这东西和市面上已有的比，有没有可被指认的差异",
        "bias": "挑同质化、没有声称、随时可被替代、把通用能力当独家卖点",
        "question": "把它和市面上已有的同类东西放在一起：哪一句话是别人说不出、或说不动的？",
        "focus": [
            "一句话能不能说清「我和别人有什么不同」",
            "这个差异能不能被验证、被感知、被复现",
            "别人照抄这套东西的成本高不高",
            "有没有把行业通用能力当成自家独家卖点",
        ],
    },
    {
        "id": "compliance_officer",
        "name": "合规官",
        "icon": "合规",
        "goal": "法律与平台风险：这份东西发出去会不会出事",
        "bias": "挑违禁词、绝对化用语、无依据承诺、资质缺失、刷单与导流话术",
        "question": "把这份材料当成即将公开发布的东西来审：哪一句会被平台或监管盯上？",
        "focus": [
            "有没有「最/第一/国家级/100%/保过」这类绝对化或明令禁止的表述",
            "承诺有没有依据、能不能举证、举证责任在谁",
            "有没有站外导流、诱导分享、刷量/刷单话术",
            "有没有拿资质、认证、权威背书说事却拿不出证据",
        ],
    },
    {
        "id": "business_owner",
        "name": "业务负责人",
        "icon": "业务",
        "goal": "投进去的人力和钱，能不能换回可衡量的结果",
        "bias": "挑成本过高、链路太长、没有 CTA、没有验收口径、失败没有止损",
        "question": "如果这条链路明天就要开工：要几个人、几天、多少钱，什么算成功，什么算止损？",
        "focus": [
            "要几个人、几天、多少钱，钱花在哪一步",
            "链路能不能再短一步，哪一步是纯消耗",
            "有没有明确的转化动作（CTA）与验收口径",
            "失败时的止损点在哪，什么时候该停",
        ],
    },
]

SEAT_IDS = [s["id"] for s in SEATS]
SEAT_BY_ID = {s["id"]: s for s in SEATS}
SEAT_NAME = {s["id"]: s["name"] for s in SEATS}


def as_seat_id(value):
    """把模型给的席位标识归一到席位 id。

    真机实测踩到的：主席在 `minority[].seat` 里填的是**显示名**（「合规官」）而不是 id
    （`compliance_officer`），于是"少数派里出现了不存在的席位"这条闸门误报，
    把一份合格的裁决判成不完整。字面看命令行是对的，错在最难查的地方。
    所以这里两种写法都认：id 原样，显示名映射成 id，其它一律 None（那才是真的不认识）。
    """
    if not isinstance(value, str):
        return None
    v = value.strip()
    if v in SEAT_BY_ID:
        return v
    for sid, name in SEAT_NAME.items():
        if v == name or v == "{}（{}）".format(name, sid) or v == "{} {}".format(name, sid):
            return sid
    for sid in SEAT_IDS:
        if v.startswith(sid):
            return sid
    return None

# 席位结论三档（+ 未表态兜底）。注意「有条件支持」**不等于**「支持」：
# 只要有一席是有条件的，"无条件通过"这个裁决就是错的（见 verdict_gate）。
SEAT_VERDICT_POS = ("支持", "有条件支持")
SEAT_VERDICT_STRICT_POS = "支持"
SEAT_VERDICT_NEG = "反对"
SEAT_VERDICT_ANY = ("支持", "有条件支持", "反对", "未表态")

# 最高裁决三档
DECISION_PASS = "通过"
DECISION_COND = "有条件通过"
DECISION_REJECT = "否决"
DECISION_ANY = (DECISION_PASS, DECISION_COND, DECISION_REJECT)


# ---------------------------------------------------------------------------
# 闸门一：合规（广告法违禁词）
#
# 每项：正则 → 风险等级 → 人话解释。这是一道**粗筛**，宁可多报也别漏报，
# 最终判断仍要人工复核，且不等于平台官方审核结论。
# 本包的合规官席位会独立再挑一遍，但**本地这道是确定性的**——
# 模型说"没问题"骗不过它。材料命中就拦，裁决书自己写出违禁词也拦。
# ---------------------------------------------------------------------------

# 「第一」的可枚举上下文豁免（照抄同族，理由见 references/成本与排错.md）：
# 长文里「第一年」「第一步」「第一件事」是**序数**，不是最高级宣称。
# 一刀切拦下的后果很实在：用户会把整个合规闸门关掉，那比漏报更糟。
FIRST_ORDINAL_AFTER = (
    "次|年|天|步|个|条|款|批|周|月|季|轮|种|点|部|遍|章|节|课|集|届|期|流|层|类"
    "|句|段|行|件|桶|手|版|稿|封|笔|单|场|局|盘|组|队|线|环|圈|代|世|阶|时|印|梯"
    # 本包新增：`第一` 后面接这些词的也是**序数/惯用语**，不是排他性宣称。
    # 真机实测踩到的误报：席位写「普通用户读到这组数字的第一反应不是『厉害』」，
    # 「第一反应」被当成「第一」类排他性表述拦下。同类还有第一印象 / 第一时间 / 第一眼。
    "|反应|印象|时间|感觉|直觉|现场|眼"
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
    (r"保过|包过|保过审|保证过审", "高",
     "「保过」类承诺，属明令禁止的效果担保"),
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
    (r"刷单|刷量|刷好评|虚假交易|shua单", "高",
     "虚假交易类话术，平台零容忍"),
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

# 「最X」的可枚举上下文豁免表。同时加一条**句首不豁免**：
# 句首的「最大区别是…」是标题式宣称，照拦；句中的「最大的区别是…」是普通中文用法。
SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥", "低", "高", "多", "少", "大", "小", "早", "晚",
    # 本包新增的一档：**商业测算用语**。真机实测踩到的误报——
    # 席位写的「可承受的最高获客成本」「最高出价」被当成最高级商品宣称拦下。
    # 这类词是内部测算口径，不是对外广告语；一刀切拦下会让用户关掉整个合规闸门。
    # 仍然遵守同一条边界：**句首不豁免**（句首的「最高获客成本是 80 元」是标题式宣称，照拦）。
    "获客", "出价", "预算", "上限", "限价", "限额", "成本", "收益", "性价比", "增速",
)
SUPERLATIVE_OK_RE = re.compile(r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")


def _superlative_is_normal_usage(text, m):
    """「最X」后面接的是比较或程度词，**且不在句首** → 判为普通用法，不拦。"""
    if not m.group(0).startswith("最"):
        return False
    before = (text or "")[:m.start()]
    if not before.strip() or _SENT_END_RE.search(before):
        return False                       # 句首 → 不豁免
    return bool(SUPERLATIVE_OK_RE.match((text or "")[m.end():]))


def compliance_scan(text, levels=None):
    """扫一遍违禁词，返回 (命中列表, 豁免列表)。被豁免的疑似命中**不静默放过**。

    `levels` 可以只扫某一档风险：材料侧全扫（高/中/低），产出侧只扫高风险
    （理由见 compliance_scan_output）。
    """
    hits, exempted, seen = [], [], set()
    t = text or ""
    for rx, lvl, why in BANNED_RE:
        if levels is not None and lvl not in levels:
            continue
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


# 产出侧**不查**的条目：`最X` 是本表里上下文依赖最强的一条。
# 真机实测（第一轮就踩到）：席位写「人力成本是这笔账里最大的一块」「可承受的最高获客成本」，
# 这是普通中文程度用法与内部测算口径，不是商品宣称；而这类误报会让人把整个合规闸门关掉。
# 材料侧**照查**（那里才是会被公开发布的东西）。
# 被排除的条目**不静默丢弃**：它们照样进 `contextual_only`，附 `not_counted_reason`。
OUTPUT_EXCLUDED_WHY = ("广告法第九条禁止「最高级」用语",)

# 「提到」而不是「主张」的上下文标记。
# 真机实测（第二轮踩到的）：合规官写「无法举证为 100% 成立」「明确禁止代发、代拍、刷量」，
# 这是**在禁止/在指出风险**，不是自己在做违规宣称；而 100% 与 刷量 都被当成命中拦下了。
# 判定方式很朴素：看命中所在的那**一整个小句**里有没有这些词——有就是"提到/在拦它"，
# 没有才是"自己在主张"。这一条也保证了闸门还有牙：
# 「本方案必须保证过审」这种小句里没有任何标记词，照样拦。
META_CONTEXT_RE = re.compile(
    "禁止|严禁|不得|不许|不能|不可|避免|杜绝|防范|防止|违规|风险|涉嫌|属于|构成|"
    "无出处|无法举证|不可举证|举证|撤回|删除|删掉|去掉|不实|虚假|夸大|诱导|"
    "不构成|不算|不是|未|没|缺|整改|改为|改成|替换|风险点|红线|合规问题")
_SENT_BOUND = re.compile(r"[。！？!?；;\n]")


def _ctx_window(text, pos, width=24):
    """命中位置前后各 width 个字符（**不跨句末标点**）。

    为什么用"窗口"而不是"整句"：中文评审句子里逗号、顿号极多，
    按标点切成小句会把「明确禁止代发、代拍、刷量」切碎成「刷量」，
    标记词正好被切掉 —— 这是本包自测时真踩到的一次。
    也不跨句末标点：跨句取词会把上一句的"禁止"借给下一句的违规宣称。
    """
    start = 0
    for m in _SENT_BOUND.finditer(text):
        if m.end() <= pos:
            start = m.end()
        else:
            break
    m = _SENT_BOUND.search(text, pos)
    end = m.start() if m else len(text)
    return text[max(start, pos - width):min(end, pos + width)]


def compliance_scan_output(prose, material):
    """产出侧合规（**与材料侧口径不同，这是踩过一次误报之后定的**）。

    真机实测踩到的两类问题（都是评审文书的正常写法，却被当成违规宣称）：
      1. **引用**：四席会引材料里的问题表述（「『30 分钟出片』是效果承诺」）
      2. **提到**：合规官会写「无法举证为 100% 成立」「明确禁止刷量」「第一反应不是厉害」
         —— 这是在禁止、在指出风险，不是自己在做违规宣称

    所以产出侧收紧成三条**能解释的**规则：
      1. 只查**高风险**（广告法明令禁止的那一类）；中低风险项与 `最X`
         在评审文书里多半是描述性用语，列进 `contextual_only` 提示人工看，不拦。
      2. 材料里已经出现过的词判为**引用**，不计命中。
      3. 命中所在的**小句**里有禁止/举证/风险类标记词的判为**提到**，不计命中；
         小句里没有任何标记词的才是**自己在主张** → 拦
         （「本方案必须保证过审」照样拦得住）。
    被排除的条目**全部保留在案**（带 `not_counted_reason`），不静默丢弃。
    """
    hi_all, exempted = compliance_scan(prose, levels=("高",))
    hi, soft = [], []
    for h in hi_all:
        if h["why"] in OUTPUT_EXCLUDED_WHY:
            h = dict(h)
            h["not_counted_reason"] = ("`最X` 在评审文书里多为普通中文程度用法或内部测算口径"
                                       "（如「最大的一块」「最高获客成本」），"
                                       "产出侧不拦；材料侧照查")
            soft.append(h)
        else:
            hi.append(h)
    mat_words = {h["word"] for h in compliance_scan(material)[0]}
    fresh, quoted, mentioned = [], [], []
    for h in hi:
        if h["word"] in mat_words:
            quoted.append(h)
            continue
        pos = prose.find(h["word"])
        ctx = _ctx_window(prose, pos) if pos >= 0 else ""
        m = META_CONTEXT_RE.search(ctx)
        if m:
            h = dict(h)
            h["not_counted_reason"] = (
                "命中前后 24 字里有「{}」这类标记词——判为**提到/在禁止**，"
                "不是评审自己在做违规宣称".format(m.group(0)))
            h["context_window"] = ctx[:60]
            mentioned.append(h)
        else:
            fresh.append(h)
    contextual, _ = compliance_scan(prose, levels=("中", "低"))
    return fresh, quoted, mentioned, contextual + soft, exempted


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
#
# 评审材料与裁决书都是给人看的，模板没替换干净是最典型的"没交付"形态：
#   · `{}` / `{{标题}}`       骨架被当正文写进去了
#   · `[待填]` / `[待补充]`    模型给自己留的空档
#   · `XXX` / `xxx`            忘了替换的占位
#   · `（此处省略）`           模型懒得写，直接省略
# `[1]`（引用序号）、`[图 2]`（配图位）是**正常写法**，不按括号内容一刀切。
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    (re.compile(r"\{\{?\s*[\u4e00-\u9fffA-Za-z0-9_]*\s*\}?\}"), "{}",
     "残留了模板占位符 `{}`，模板没被替换干净"),
    (re.compile(r"[\[【（(]\s*(待填|填空|待补充|待完善|待定)\s*[\]】）)]"), "[]",
     "残留了占位符 `[待填]`，模型给自己留的空档没补"),
    (re.compile(r"[\[【]\s*(略|此处省略)\s*[\]】]"), "[]",
     "残留了「此处省略」类占位"),
    (re.compile(r"[(（]\s*此处省略[^)）]{0,12}[)）]"), "（此处省略）",
     "残留了「（此处省略）」——该写的内容被省略了"),
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
#   2. 提示词里留过一整句示例 → 那一轮**最高分**的产出一字不差就是它
# 四席评审同样会踩：提示词里写了「怎么算一条好意见」，模型就把那句原样填进 `why`。
#
# 三条命中判据（任一即命中）：
#   exact    去掉标点后完全相同
#   jaccard  字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
#   contain  示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（示例被夹带进更长的句子里）
#
# 【为什么必须有第三条】Jaccard 的分母是两份二元组的**并集**，产出越长，
# 示例那一侧被摊薄得越狠 —— 示例原样嵌进去也会掉到 0.75 以下侥幸放行。
#
# 【为什么第三条必须有**适用窗口**】覆盖度只看"示例被抄了多少"，不看产出有多长，
# 所以它对**短示例**会饱和：示例归一后只有 3~5 字（2~4 个二元组）时，
# 长文本里被动凑齐两个二元组就有 0.5 的覆盖度 —— 离 0.60 的阈值只差 0.10。
# 本包在真实语料上量过（105,863 字符 / 3,253 句，见 references/成本与排错.md）：
#   · 13~20 字的跨主题示例：各长度比档位覆盖度上限 0.125~0.333，≥0.60 命中 0 条
#   · 2~5 字的短示例：长度比 ≥2 的档位覆盖度上限直接到 0.500 —— 余量只剩 0.10
# 所以 contain 只在**两个条件都满足**时适用：
#   1. 目标片段长度 ≤ 示例长度 × ECHO_CONTAIN_MAX_RATIO（长度比窗口）
#   2. 示例归一后长度 ≥ ECHO_CONTAIN_MIN_SAMPLE（二元组数量够用）
# 不适用的地方会记进 `contain_skipped`，**不静默略过**。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6          # 长度守卫的绝对下限，防极短串的二元组噪声
ECHO_CONTAIN_MAX_RATIO = 3.0    # contain 适用窗口：目标长度 ≤ 示例长度 × 该系数
ECHO_CONTAIN_MIN_SAMPLE = 8     # contain 适用窗口：示例归一后至少这么长

# 提示词里出现过的**跨主题**示例（正常不该被抄）。新增示例必须登记到这里。
# 跨主题 = 与任何真实选题都不搭（电动车充电桩），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
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


def _overlap(a, b):
    """较短一侧被另一侧覆盖的比例（**不对称度量的对称化**）。

    为什么立场重叠度不能直接用 Jaccard：两席的意见篇幅天然不同
    （合规官可能有 8 条、竞品分析师只有 2 条），Jaccard 的分母是并集，
    篇幅差一大就被摊薄，"说了同样的话"反而测不出来。
    用 min 归一后，「短的那份有多少比例的内容出现在长的那份里」才是我们要问的问题。
    """
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(min(len(ba), len(bb)))


def prompt_echo(text, samples=None):
    """文本是否与提示词里的示例"抄得太近"。

    返回 (是否命中, 分数, 撞上的示例, 判据, 被跳过的判据列表)；
    判据是 "exact" / "jaccard" / "contain"，没命中时后三项为 (0.0, "", "")。
    """
    target = _norm_anchor(text)
    if not target:
        return False, 0.0, "", "", []
    best_score, best_sample, best_rule = 0.0, "", ""
    skipped = []
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        ns = _norm_anchor(s)
        if target == ns:
            return True, 1.0, s, "exact", skipped
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(text, s)
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        base = _bigrams(s)
        # contain 的适用窗口：长度比 + 示例长度，两个都满足才用它
        if len(target) > ECHO_CONTAIN_MAX_RATIO * max(1, len(ns)):
            skipped.append({"rule": "contain", "why": "目标长度 {} > 示例长度 {} × {}"
                            .format(len(target), len(ns), ECHO_CONTAIN_MAX_RATIO)})
            continue
        if len(ns) < ECHO_CONTAIN_MIN_SAMPLE:
            skipped.append({"rule": "contain", "why": "示例归一后仅 {} 字 < {}，"
                            "二元组太少、覆盖度会饱和".format(len(ns), ECHO_CONTAIN_MIN_SAMPLE)})
            continue
        contain = (len(_bigrams(text) & base) / float(len(base))) if base else 0.0
        if contain >= ECHO_CONTAIN and contain >= best_score:
            best_score, best_sample, best_rule = contain, s, "contain"
    if best_rule:
        return True, best_score, best_sample, best_rule, skipped
    return False, best_score, best_sample, "", skipped


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


def _dedupe_skips(skips):
    """把「contain 判据被适用窗口跳过」的记录按原因合并（真机上一条产出会有上百次）。"""
    agg = {}
    for s in skips or []:
        key = s.get("why") or s.get("rule")
        agg[key] = agg.get(key, 0) + 1
    return [{"why": k, "times": v} for k, v in sorted(agg.items(), key=lambda x: -x[1])]


def prompt_echo_scan(text, samples=None, label="产出"):
    """在长文本里逐句找「照抄提示词示例」的地方，返回 (命中列表, 被跳过的窗口记录)。

    两层：整段先比一次（只认 exact / jaccard，兜整篇照抄的极端情况），
    再**逐句**比一次（含覆盖度判据，兜「某一句是抄的」这个真实形态）。
    """
    hits, skips = [], []
    whole_hit, score, sample, rule, sk = prompt_echo(text, samples)
    skips.extend(sk)
    if whole_hit and rule != "contain":
        hits.append({"segment": (text or "")[:40], "rule": rule, "sim": round(score, 3),
                     "sample": sample,
                     "why": ("与提示词示例去掉标点后完全相同（照抄示例）" if rule == "exact"
                             else "与提示词示例相似度 {:.2f}，属同构照抄".format(score))})
        return hits, skips
    for seg in split_sentences(text):
        hit, score, sample, rule, sk = prompt_echo(seg, samples)
        skips.extend(sk)
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
    return hits, skips


# ---------------------------------------------------------------------------
# 闸门四：评审锚点（意见必须引用原文真实句子）
#
# 一份四席评审最没用的形态，是四条"泛泛而谈"：都说"建议加强逻辑、注意合规"，
# 谁也不说清是哪一句。所以本包不采信模型的引文，而是**本地校验**：
# 它引的那句话在不在**对应的文本**里？
#
# 注意本包有三层锚点，各自锚到不同的文本（这是与同族最不一样的地方）：
#   · 席位意见的 quote      → 锚到**待评材料**的句子（意见必须对着材料说）
#   · 对质的 side.quote     → 锚到**那个席位自己说过的话**（不许替别人发言）
#   · 裁决条件的 quote      → 锚到**它标注的那个席位**说过的话（不许移花接木）
# 三层共用 verify_anchor，四条判据递进：
#   exact      归一化后与某一整句完全相同
#   substring  归一化后是某一整句的一部分（模型只引了半句，最常见）
#   fuzzy      与最像的那一句 Jaccard ≥ ANCHOR_SIM 且引文够长（轻改写式引用）
#   unverified 以上都不成立 → **判为锚点幻觉**，剔出并计入未锚定率
#
# 未锚定率超过 ANCHOR_MAX_MISS → 判「定位失败」，压分 + 标红 + stderr 汇总 + 退出码 3。
# ---------------------------------------------------------------------------

ANCHOR_MIN_SUBSTR = 4     # 精确子串匹配的最低长度（低风险判据，门槛可以矮）
ANCHOR_MIN_CHARS = 8      # 模糊匹配的最低长度（二元组太少会虚高，门槛必须高）
ANCHOR_SIM = 0.55         # 模糊匹配阈值
ANCHOR_MAX_MISS = 0.40    # 未锚定率超过它就判「定位失败」


def verify_anchor(quote, sentences, norms=None):
    """把引文锚定到某一句话上。返回 (ok, rule, index)；index 是句序号（0 基）。"""
    q = _norm_anchor(quote)
    if not q:
        return False, "unverified", -1
    if norms is None:
        norms = [_norm_anchor(s) for s in sentences]
    for i, n in enumerate(norms):
        if n and n == q:
            return True, "exact", i
    if len(q) >= ANCHOR_MIN_SUBSTR:
        for i, n in enumerate(norms):
            if n and (q in n or n in q) and min(len(q), len(n)) >= ANCHOR_MIN_SUBSTR:
                return True, "substring", i
    best_i, best = -1, 0.0
    if len(q) >= ANCHOR_MIN_CHARS:
        for i, s in enumerate(sentences):
            sim = _similarity(quote, s)
            if sim > best:
                best_i, best = i, sim
        if best >= ANCHOR_SIM:
            return True, "fuzzy", best_i
    return False, "unverified", -1


class AnchorTarget:
    """一个可被引用的文本（材料 / 某席位的话），带句子切分缓存。"""

    def __init__(self, key, label, text):
        self.key = key
        self.label = label
        self.text = text or ""
        self.sentences = split_sentences(self.text)
        self.norms = [_norm_anchor(s) for s in self.sentences]

    def check(self, quote):
        """返回 (是否锚定, 判据, 句序号, 真实原句)。"""
        ok, rule, idx = verify_anchor(quote, self.sentences, self.norms)
        sent = self.sentences[idx] if ok and idx >= 0 else ""
        return ok, rule, (idx + 1 if ok and idx >= 0 else None), sent


# ---------------------------------------------------------------------------
# 闸门五：立场有效性（**本包的核心闸门**）
#
# 四席评审最容易变成的一场表演：四个角色说了同样的话，然后宣布"一致通过"。
# 那不是协作，是**同一份意见换了四个抬头**。这一条不靠提示词，本地算：
#
#   判据 A（硬）：任一对席位的**意见重叠度** ≥ STANCE_OVERLAP
#                重叠度 = 较短那份有多少比例的内容出现在较长那份里（min 归一），
#                且两份中较短的那份二元组不少于 STANCE_MIN_GRAMS（防短文本虚高）
#   判据 B（硬）：对质阶段找不到**任何**真实分歧，且四席结论完全相同
#                → 判「立场失效」：四个立场不同的角色对同一份方案零分歧，
#                  基本只能说明立场没起作用（材料确实无争议时用 --unanimous-ok 降级）
#
# 判据 A 用 min 归一而不是 Jaccard 的理由见 _overlap()。
# 判据 B 之所以是硬闸门而不是提示：本包的交付物就是"分歧 + 裁决"，
# 没有分歧就没有交付物；把"零分歧"当"一致通过"正是本包要防的那个假象。
# ---------------------------------------------------------------------------

STANCE_OVERLAP = 0.75      # 判据 A：意见重叠度阈值
STANCE_MIN_GRAMS = 30      # 判据 A：短的那份至少这么多二元组（约 30 字内容）
# 这个门槛怎么定的（**改过一次，原因是它把真问题放过了**）：
# 一开始写 60，理由是"防短文本虚高"。自测时发现四席写**一模一样的 95 个字**
# （45 个二元组）时重叠度算出来是 1.00，却因为没到 60 被判为"不拦" —— 而这正是本包要抓的形态。
# 参考量级：真机实测四席各自的"自己的话"是 986~1008 个二元组（约 1000 字），
# 门槛 30 只是这个量级的 3%，只能挡住"两席各用十几个通用词"这种真正无信息的噪声。
# 另有独立的红线 STANCE_MIN_OWN_GRAMS（少于 40 个二元组单独标红"只有引用没有观点"）。
STANCE_RED_OVERLAP = 0.55  # 标红（不单独拦）：超过它就在报告里提示"两边说得太像"
STANCE_MIN_OWN_GRAMS = 40  # 标红：一个席位自己的话少于这个量（约 40 字）就提示"只有引用没有观点"
STANCE_SENT_MIN = 16       # 句子级相似度只对够长的句子算（短句雷同没有信息量）


def seat_anchor_text(seat):
    """席位意见的**可被引用文本**（对质/裁决的引文要锚到这里）。

    必须包含 `quote`：席位"说过的话"里，引用材料原文的那部分也算它说的话。
    """
    parts = [seat.get("verdict") or "", seat.get("must_have") or "",
             seat.get("kill_switch") or "", seat.get("summary") or ""]
    for p in seat.get("points") or []:
        parts.extend([p.get("quote") or "", p.get("why") or "", p.get("ask") or ""])
    return "\n".join(x for x in parts if x)


def seat_own_words(seat):
    """席位**自己的话**（不含它引用的材料原文）。

    ⚠️ 闸门五必须用这一份，不能用 seat_anchor_text。原因：四席经常引用**同一句材料原文**
    （这是好事，说明大家都看到了同一处问题），引用部分逐字相同会把重叠度抬上去 ——
    拿它判"四个角色说了同样的话"会误伤。要问的是"他们自己的判断是不是一套话"。
    """
    parts = [seat.get("verdict") or "", seat.get("must_have") or "",
             seat.get("kill_switch") or "", seat.get("summary") or ""]
    for p in seat.get("points") or []:
        parts.extend([p.get("why") or "", p.get("ask") or ""])
    return "\n".join(x for x in parts if x)


def stance_check(seats):
    """算四席意见的重叠度，返回结构化结论（含每一对的数字，便于人工复核）。

    两份文本都用 `seat_own_words`（见那里的理由）。
    """
    res = {"pairs": [], "max_overlap": 0.0, "overlap_pairs": [], "red_pairs": [],
           "thin_own_words": [],
           "verdicts": {}, "distinct_verdicts": 0, "all_same_verdict": False,
           "distinct_verdict_seats": [],
           "text_basis": ("重叠度与句子级相似度都只算各席位**自己的话**"
                          "（verdict / must_have / kill_switch / summary / why / ask），"
                          "不含各席位引用的材料原文——引用同一句原文是正常的，"
                          "拿它算重叠会误判。")}
    bodies = {s["id"]: seat_own_words(s) for s in seats}
    ids = [s["id"] for s in seats]
    for s in seats:
        g = len(_bigrams(seat_own_words(s)))
        if len(s.get("points") or []) >= 2 and g < STANCE_MIN_OWN_GRAMS:
            res["thin_own_words"].append({"seat": s["id"], "own_grams": g})
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            ov = _overlap(bodies[a], bodies[b])
            grams = min(len(_bigrams(bodies[a])), len(_bigrams(bodies[b])))
            sent_max, sent_pair = 0.0, ""
            sa, sb = split_sentences(bodies[a]), split_sentences(bodies[b])
            for x in sa:
                for y in sb:
                    if len(_norm_anchor(x)) < STANCE_SENT_MIN or len(_norm_anchor(y)) < STANCE_SENT_MIN:
                        continue
                    sim = _similarity(x, y)
                    if sim > sent_max:
                        sent_max, sent_pair = sim, x[:40]
            rec = {"a": a, "b": b, "overlap": round(ov, 3), "min_grams": grams,
                   "max_sentence_sim": round(sent_max, 3), "sentence": sent_pair,
                   "note": "重叠度按较短一侧归一（min 归一），只算各自的话，"
                           "避免篇幅差与共同引用把相似度算歪"}
            res["pairs"].append(rec)
            res["max_overlap"] = max(res["max_overlap"], round(ov, 3))
            if ov >= STANCE_OVERLAP and grams >= STANCE_MIN_GRAMS:
                res["overlap_pairs"].append(rec)
            elif ov >= STANCE_RED_OVERLAP:
                res["red_pairs"].append(rec)
    for s in seats:
        res["verdicts"][s["id"]] = s.get("verdict") or "未表态"
    res["distinct_verdicts"] = len(set(res["verdicts"].values()))
    res["all_same_verdict"] = res["distinct_verdicts"] == 1
    res["distinct_verdict_seats"] = sorted(set(res["verdicts"].values()))
    return res


# ---------------------------------------------------------------------------
# 闸门六：裁决完整性
#
# 裁决书是本包的**最终交付物**，它有三种常见的废掉方式：
#   1. 明明有席位反对，主席判「通过」——把反对意见吞了
#   2. 判「有条件通过」却给不出条件清单——等于没判
#   3. 少数派意见不见了——等于把中间的争论抹平，用户只看到一个结论
# 这三条都在本地判，不采信模型的自我声明。
# ---------------------------------------------------------------------------

def verdict_gate(decision, conditions, minority, seats, real_divergences):
    """裁决完整性闸门。返回 (ok, problems, required_minority, listed_minority)。

    三条纪律（都在本地判，不采信模型的自我声明）：
      1. 有席位反对（或有条件支持）却判「通过」→ 拦
      2. **条件清单不能空**：判「有条件通过」或「否决」都必须给出可验证的条件清单
         （否决时的条件是"要翻案必须做到什么"，没有它这份裁决无法执行）
      3. **少数派意见必须在案**：与最终裁决方向不一致的席位要逐条保留；
         反过来，判「通过」时也不该带一堆条件（那应该判「有条件通过」）
    """
    problems = []
    dissent = [s["id"] for s in seats if (s.get("verdict") or "") == SEAT_VERDICT_NEG]
    conditional = [s["id"] for s in seats if (s.get("verdict") or "") == "有条件支持"]
    if decision not in DECISION_ANY:
        problems.append("裁决结论「{}」不是三档之一（{}）".format(
            decision, " / ".join(DECISION_ANY)))
    if decision == DECISION_PASS:
        if dissent:
            problems.append("有 {} 席意见是「反对」（{}），却判「通过」——"
                            "反对意见被吞了".format(
                                len(dissent), "、".join(SEAT_NAME.get(x, x) for x in dissent)))
        if conditional:
            problems.append("有 {} 席是「有条件支持」（{}），却判「通过」——"
                            "没有任何条件就不该无条件通过".format(
                                len(conditional),
                                "、".join(SEAT_NAME.get(x, x) for x in conditional)))
        if real_divergences:
            problems.append("对质里还有 {} 个未解决的真实分歧，却判「通过」".format(
                len(real_divergences)))
        if conditions:
            problems.append("判「通过」却带 {} 条条件——这应当判「有条件通过」".format(
                len(conditions)))
    if decision in (DECISION_COND, DECISION_REJECT) and not conditions:
        extra = ("（否决时的条件是「要翻案必须做到什么」，同样是可执行的交付物）"
                 if decision == DECISION_REJECT else "（等于没判）")
        problems.append("判「{}」但条件清单为空——裁决必须带条件清单{}".format(decision, extra))
    # 少数派保留：与最终裁决方向不一致的席位，必须逐条出现在 minority 里
    if decision == DECISION_REJECT:
        required = [s["id"] for s in seats if (s.get("verdict") or "") in SEAT_VERDICT_POS]
    else:
        required = list(dissent)
    listed, unknown = [], []
    for m in (minority or []):
        if not isinstance(m, dict):
            continue
        raw = m.get("seat")
        sid = as_seat_id(raw)
        if sid:
            listed.append(sid)
        else:
            unknown.append(str(raw))
    if unknown:
        problems.append("少数派意见里出现了不存在的席位：{}".format("、".join(unknown)))
    missing = [x for x in required if x not in listed]
    if missing:
        problems.append("{} 与最终裁决方向不一致，却没有出现在少数派意见里（少数派被抹平）"
                        .format("、".join(SEAT_NAME.get(x, x) for x in missing)))
    return (not problems), problems, required, listed


# ---------------------------------------------------------------------------
# 提示词
#
# 【铁律】提示词里**不许出现任何一条可直接复制的完整中文范文句**。
# 事故复盘（同族，实测抓到两例）：提示词里写过正例，模型直接产出同构句；
# 尤其严重的一例，全批最高分的那条一字不差就是提示词里的示例 ——
# "抄了标准答案"被当成"真的最好"，排序/评分就废了。
# 本包的对策一样：讲形态只用**描述性语言**；确实要举例时用**跨主题示例**
# （登记进 PROMPT_SAMPLES，由 prompt_echo 闸门兜底）。
#
# 【信息隔离】panel 阶段的提示词里**只有本席位的立场块**，没有其它席位的
# 任何文字，也没有席位花名册。这是本包最关键的机制约束：
# 四席必须是四次独立调用算出来的，不能是一次回答的四种复述。
# ---------------------------------------------------------------------------

CHAT_RETRY_NOTE = "上游 5xx 与网络抖动退避重试；4xx 直接报错，不浪费额度。"

SEAT_SYSTEM = (
    "你是「三剪客 · 评审委员会」的**{name}**。\n"
    "你只代表你这一席的立场，不为别的立场着想，也不负责调和折中——"
    "把话说到本席位该说的位置上，是你的职责。\n"
    "你的目标函数：{goal}\n"
    "你的天然倾向（这是职责，不是偏见）：{bias}\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 每条意见必须**原样引用**材料里真实存在的一句话（或句中连续的一小段），"
    "不得改写、不得概括、不得凭空编造引文。引不出来的意见一律不要写。\n"
    "  2. 不许写「整体不错」「建议加强」「注意合规」这类无法执行的泛泛之谈；"
    "每条意见的 `ask` 必须是**可以直接落到纸面上的改法**，不是方向。\n"
    "  3. 不许编造材料里没有的数据、案例、机构名、人名。\n"
    "  4. 不许替其它立场打分，也不许因为怕得罪人而降低风险等级。\n"
    "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

# 跨主题示例：只用来讲"什么样的一条意见算无法执行"，不是范文。
# 跨主题 = 与任何真实选题都不搭（电动车充电桩），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
_PROMPT_SAMPLE_BLOCK = (
    "跨主题示例（**仅供理解「什么算无法执行」，禁止把示例原句写进任何字段**）：\n"
    "  · 反面（无法执行）：把「{}」这类**没有出处的判断**当成意见，只说要更好，不说改哪句。\n"
    "  · 正面（可执行）：引出一句原文，说明它缺什么，再给出你要求的改法。\n"
).format(PROMPT_SAMPLES[0])

_SEAT_SCHEMA = {
    "verdict": "支持|有条件支持|反对",
    "acceptability": 0,
    "must_have": "从你这一席出发，最不能让步的一点（一句话）",
    "kill_switch": "出现什么情况你会主张否决这份材料（一句话）",
    "points": [
        {
            "quote": "材料里**原样**的一句话（或句中连续一小段）",
            "severity": "高|中|低",
            "why": "这句话从你这一席看为什么是问题",
            "ask": "你要求改成什么样（具体到能落纸）",
        }
    ],
    "summary": "两三句总评",
}


def build_seat_prompt(seat, material, material_meta=None):
    """单席评审提示词。**只含本席位立场**（信息隔离的实现处）。"""
    meta = material_meta or {}
    head = ("下面是**待评审的一份方案/稿件**。请以「{name}」的身份，"
            "只从本席位的视角做一次评审。\n").format(name=seat["name"])
    lines = [
        "你的评审视角（只从这一条出发）：" + seat["question"],
        "",
        "本席位盯的点（这是你的清单，不是全部）：",
    ]
    lines += ["  · " + x for x in seat["focus"]]
    lines += [
        "",
        "评审要求：",
        "  · verdict 是本席位的结论：支持 / 有条件支持 / 反对。只有你能代表本席说话。",
        "  · acceptability 是本席位视角下的可接受度（0~10 的整数；10 = 本席位毫无异议）。",
        "  · must_have 与 kill_switch 必须写，它们是你这一席的底线，不许写成套话。",
        "  · points 最多 8 条，按 severity 从高到低；每条 quote 必须是材料原文原样的一句话。",
        "  · 从你的立场看确实挑不出问题时，points 给空数组、verdict 给「支持」，"
        "并在 summary 里说明你为什么挑不出。",
        "",
        _PROMPT_SAMPLE_BLOCK,
    ]
    if meta.get("chars"):
        lines += ["", "  · 待评材料 {} 字符 / {} 句".format(
            meta.get("chars"), meta.get("sentences"))]
    return (
        head
        + "\n".join(lines)
        + "\n\n按要求只输出这个 JSON 对象：\n"
        + json.dumps(_SEAT_SCHEMA, ensure_ascii=False, indent=1)
        + "\n\n===== 待评材料开始 =====\n" + (material or "")
        + "\n===== 待评材料结束 =====\n"
    )


_CLASH_SCHEMA = {
    "divergences": [
        {
            "topic": "争点的一句话概括",
            "crux": "争的到底是哪一点（不可再分的那一点）",
            "sides": [
                {"stance": "支持|反对", "seats": ["席位id"], "quote": "该席位**原话**"},
                {"stance": "反对|支持", "seats": ["席位id"], "quote": "该席位**原话**"},
            ],
            "why_real": "为什么这是真分歧，而不是措辞差异",
            "cost_of_each_side": "各让一步分别要付出什么代价",
            "tie_break": "如果只能选一边，按什么证据或规则裁",
        }
    ],
    "shared_ground": ["四席其实都同意的点"],
    "no_divergence_reason": "divergences 为空时说明为什么真的没有分歧",
    "summary": "两三句总评",
}


def build_clash_prompt(material, seats):
    """对质提示词：把四份独立意见放在一起，找**真实分歧**。

    对质阶段必须看到全部四份意见（这是设计上的破隔离点）：
    信息隔离只发生在 panel 阶段，对质的目的就是把隔离出来的差异摆到同一张桌上。
    """
    blocks = []
    for s in seats:
        pts = []
        for p in s.get("points") or []:
            pts.append("      · [{}] 原句：{}\n        问题：{}\n        要求：{}".format(
                p.get("severity") or "中", p.get("quote") or "",
                p.get("why") or "-", p.get("ask") or "-"))
        blocks.append(
            "【{}（{}）】结论：{}；可接受度 {}；底线：{}；否决条件：{}\n"
            "   意见：\n{}\n   总评：{}".format(
                SEAT_NAME.get(s["id"], s["id"]), s["id"], s.get("verdict") or "未表态",
                s.get("acceptability"), s.get("must_have") or "-",
                s.get("kill_switch") or "-",
                "\n".join(pts) if pts else "    （该席位未提出问题）",
                s.get("summary") or "-"))
    return (
        "下面是同一份材料的**四份独立评审意见**。四席此前**互相看不到对方的意见**，"
        "各自只代表自己的立场。\n"
        "你的任务是**对质**：把真实分歧找出来、摊开、辩清楚。\n\n"
        "判定纪律（违反就整份作废）：\n"
        "  1. 真实分歧 = 同一件事上**有人支持、有人反对**，且换一边会让结论不同。\n"
        "     只是措辞不同、或者结论一致的，**不算分歧**，不要写进 divergences。\n"
        "  2. 每条分歧必须有两个 side：一边 stance 写「支持」、另一边写「反对」"
        "（或反向），两侧的 `seats` 必须是真实存在的席位 id。\n"
        "  3. 每个 side 的 `quote` 必须是**那个席位自己说过的话**（原样摘引，"
        "不得改写、不得替别的席位发言、不得编造）。摘不出来就不要写这条分歧。\n"
        "  4. 不许为了凑数把共识包装成分歧；也不许把真分歧和稀泥成「建议兼顾」。\n"
        "  5. 四份意见确实没有分歧时，divergences 给空数组，"
        "并在 no_divergence_reason 里写清为什么——这一栏会被本地闸门复核。\n"
        "  6. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n\n"
        + _PROMPT_SAMPLE_BLOCK
        + "\n\n===== 四份独立意见开始 =====\n"
        + "\n\n".join(blocks)
        + "\n===== 四份独立意见结束 =====\n\n"
        + "===== 待评材料（供你核对引文）开始 =====\n" + (material or "")
        + "\n===== 待评材料结束 =====\n\n"
        + "按要求只输出这个 JSON 对象：\n"
        + json.dumps(_CLASH_SCHEMA, ensure_ascii=False, indent=1)
        + "\n"
    )


_VERDICT_SCHEMA = {
    "decision": "通过|有条件通过|否决",
    "vote_table": [{"seat": "席位id", "verdict": "该席位的结论", "one_line": "一句话"}],
    "conditions": [
        {
            "id": 1,
            "what": "必须满足什么（可验证）",
            "from_seats": ["席位id"],
            "quote": "提出这条的席位**原话**",
            "how_to_verify": "怎么算满足了",
        }
    ],
    "minority": [
        {"seat": "席位id", "position": "该席位的立场（原话或紧贴原话）",
         "why_kept": "为什么保留在案"}
    ],
    "dissenting_seats": ["与最终裁决方向不一致的席位id"],
    "rationale": "裁决理由：要正面回应每一个争点，不要绕开",
    "summary": "两三句",
}


def build_verdict_prompt(material, seats, clash):
    """裁决提示词：材料 + 四席意见 + 对质结果 → 裁决书。"""
    votes = "；".join("{}={}".format(SEAT_NAME.get(s["id"], s["id"]),
                                   s.get("verdict") or "未表态") for s in seats)
    divs = []
    for i, d in enumerate(clash.get("real_divergences") or [], 1):
        sides = "；".join("{}：{}（{}）".format(
            x.get("stance"), "、".join(SEAT_NAME.get(k, k) for k in x.get("seats") or []),
            (x.get("quote") or "")[:60]) for x in d.get("sides") or [])
        divs.append("  {}. 争点：{}\n     争的到底是：{}\n     双方立场：{}".format(
            i, d.get("topic") or "-", d.get("crux") or "-", sides))
    div_block = "\n".join(divs) if divs else "  （对质未找到真实分歧）"
    return (
        "下面是待评材料、四席独立评审意见、以及对质结果。"
        "请以「评审委员会主席」的身份出一份**裁决书**。\n\n"
        "裁决纪律（违反就整份作废）：\n"
        "  1. decision 只能三选一：通过 / 有条件通过 / 否决。\n"
        "  2. 只要有任何一席的结论是「反对」，就**不许**判「通过」（无条件通过）；"
        "有「有条件支持」的席位同样不许判「通过」。\n"
        "  3. 判「有条件通过」或「否决」都必须给出**条件清单**，每条都要可验证"
        "（满足什么、怎么算满足）；条件不许写成「注意合规」这类空话。"
        "判「否决」时，条件清单写的是**要翻案必须做到什么**——没有它这份裁决没法执行。\n"
        "  4. **少数派意见必须保留在案**：与最终裁决方向不一致的席位（例如你要判"
        "「有条件通过」，而某席位是「反对」），必须逐条出现在 minority 里，"
        "原样保留它的立场，不许抹平、不许改写成你的话。"
        "判「通过」时条件是空的（带条件就该判「有条件通过」）。\n"
        "  5. 每条 condition 的 from_seats 必须是真实存在的席位 id（" + "、".join(SEAT_IDS)
        + "），quote 必须是该席位自己说过的话（原样）。\n"
        "  6. rationale 要正面回应每一个争点，说明你为什么这么裁。\n"
        "  7. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n\n"
        + _PROMPT_SAMPLE_BLOCK
        + "\n\n席位结论一览（本地从四份意见里读出来的，与你看到的应该一致）：\n  "
        + votes + "\n"
        + "\n===== 对质找到的真实分歧 =====\n" + div_block + "\n"
        + "\n===== 四份独立意见（完整）开始 =====\n"
        + "\n\n".join(
            "【{}】结论 {} / 可接受度 {} / 底线：{} / 否决条件：{}\n{}".format(
                SEAT_NAME.get(s["id"], s["id"]), s.get("verdict") or "未表态",
                s.get("acceptability"), s.get("must_have") or "-",
                s.get("kill_switch") or "-",
                "\n".join("    · [{}] {} → 要求：{}".format(
                    p.get("severity") or "中", p.get("quote") or "", p.get("ask") or "-")
                    for p in (s.get("points") or [])) or "    （未提出问题）")
            for s in seats)
        + "\n===== 四份独立意见结束 =====\n\n"
        + "===== 待评材料开始 =====\n" + (material or "") + "\n===== 待评材料结束 =====\n\n"
        + "按要求只输出这个 JSON 对象：\n"
        + json.dumps(_VERDICT_SCHEMA, ensure_ascii=False, indent=1)
        + "\n"
    )


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class BoardError(a7w.A7wError):
    """评审流程里的所有可预期失败。子类各自带退出码。"""
    exit_code = EXIT_CALL


class UsageError(BoardError):
    """参数/配置用错了（文件不存在、席位名错、给了 --budget 没给单价…）。→ 退出码 2"""
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """产出路径落在 Skill 包内（退出码 2）。"""


class GateFail(BoardError):
    """硬闸门命中（退出码 3）。"""
    exit_code = EXIT_GATE


class BudgetStop(BoardError):
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
    一次评审要跑六次调用，被一次抖动打断要重跑整轮，很亏。
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
                raise BoardError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise BoardError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise BoardError("模型不存在（404）：{}  "
                                 "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise BoardError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise BoardError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 网关把 OpenAI 的返回包了一层 {"code":1,"data":{...}}，两种形态都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise BoardError("模型没返回 choices：{}".format(
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
        raise BoardError("模型返回空内容")
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
    raise BoardError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


# ---------------------------------------------------------------------------
# 成本：token 标定 + 预算闸门
#
# 只出 token，**不编金额**：文本模型网关不公布单价（/api/v1/models 里也没有价格字段）。
# 字符 → token 的标定比例（**是全族实测值**，不是厂商文档）：
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN_IN = 1.61     # 输入侧：拿真实调用标定，实测均值 1.612
TOKENS_PER_CHAR_OUT = 1.11    # 输出侧：1 个原始字符 ≈ 多少 token，实测均值 1.109
POINTS_PER_YUAN = 100.0       # 平台口径：1 元 = 100 点

SEAT_OUT_TOKENS = 700         # 单席意见的 JSON 输出经验值（含最多 8 条意见）
CLASH_OUT_TOKENS = 1400       # 对质的输出经验值（含逐点辩）
VERDICT_OUT_TOKENS = 1200     # 裁决书的输出经验值（含条件清单与少数派）


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(text, seat_count=4):
    """一次完整评审的调用清单（用于报价，越清楚越好）。"""
    src_in = estimate_tokens_in(text)
    seat_calls = [{
        "stage": "四席独立评审（每席 1 次调用）", "calls": seat_count,
        "tokens_in": (src_in + 700) * seat_count,
        "tokens_out": SEAT_OUT_TOKENS * seat_count,
        "note": "每次调用只带本席位的立场块（信息隔离），四席互相看不到对方",
    }]
    # 对质与裁决的输入随席位意见规模增长，按实测口径估
    clash_in = src_in + int(SEAT_OUT_TOKENS * seat_count / TOKENS_PER_CHAR_OUT) + 600
    seat_in = src_in + int(SEAT_OUT_TOKENS * seat_count / TOKENS_PER_CHAR_OUT)
    seat_calls.append({
        "stage": "对质（1 次调用）", "calls": 1,
        "tokens_in": clash_in, "tokens_out": CLASH_OUT_TOKENS,
        "note": "输入 = 材料 + 四份意见；这一步**故意打破隔离**，把差异摆到一张桌上",
    })
    seat_calls.append({
        "stage": "裁决书（1 次调用）", "calls": 1,
        "tokens_in": seat_in + clash_in + 400, "tokens_out": VERDICT_OUT_TOKENS,
        "note": "输入 = 材料 + 四份意见 + 对质结果；产出条件清单与少数派意见",
    })
    return seat_calls


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
        self.log = []

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
        self.log.append({"label": label, "usage": dict(u) if isinstance(u, dict) else {},
                         "prompt_tokens": p, "completion_tokens": c})

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    @property
    def points(self):
        if not self.has_price:
            return None
        return ((self.prompt_tokens / 1e6) * float(self.price_in)
                + (self.completion_tokens / 1e6) * float(self.price_out))

    def preview(self, extra_in=0, extra_out=0):
        """这一次调用之后预计的点数（没单价时为 None）。"""
        if not self.has_price:
            return None
        return (((self.prompt_tokens + extra_in) / 1e6) * float(self.price_in)
                + ((self.completion_tokens + extra_out) / 1e6) * float(self.price_out))

    def would_exceed(self, extra_in=0, extra_out=0):
        if self.budget is None:
            return False
        pts = self.preview(extra_in, extra_out)
        return pts is not None and pts > self.budget

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

    def as_dict(self):
        d = {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "calls_without_usage": self.estimated_flags,
            "budget_points": self.budget,
            "has_price": self.has_price,
            "price_in": self.price_in,
            "price_out": self.price_out,
            "usage_log": self.log,
            "note": "token 是网关返回的真实 usage；金额只有在你给了单价时才折算，本包不编单价。",
        }
        if self.has_price:
            d["points"] = round(self.points or 0, 4)
            d["yuan"] = round((self.points or 0) / POINTS_PER_YUAN, 4)
        else:
            d["points"] = None
            d["yuan"] = None
        return d


def guarded_chat(prompt, tracker, label, system=None, model=DEFAULT_MODEL,
                 temperature=0.7, max_tokens=8192, key=None, json_mode=True):
    """带**预算预检**的一次调用：预估会超预算就地中止（退出码 5），一次调用都不发。"""
    est_in = estimate_tokens_in(prompt) + estimate_tokens_in(system or "")
    if tracker.would_exceed(est_in, max_tokens):
        raise BudgetStop(
            "预算超限，已就地中止（未发起本次调用）。已用 {} 点，预算 {} 点，"
            "本次预计还要约 {} 点。调大 --budget，或减少席位数量，或换更短的模型。".format(
                round(tracker.points or 0, 4), tracker.budget,
                round((tracker.preview(est_in, max_tokens) or 0) - (tracker.points or 0), 4)))
    t0 = time.time()
    content, usage = chat(prompt, system=system, model=model, temperature=temperature,
                          max_tokens=max_tokens, key=key, json_mode=json_mode)
    tracker.add(usage, label)
    tracker.log[-1]["elapsed"] = round(time.time() - t0, 1)
    return content, usage


# ---------------------------------------------------------------------------
# 断点续跑
#
# 事故复盘（同族踩过三次，本包一次都不许再踩）：
#   · 内容截断没进 key   → 把 8000 字截成 4000 字重跑，key 没变，静默复用了旧产物
#   · 口径没进 key       → 换了闸门口径重跑，命中的还是上一版产物
#   · 席位数量没进 key   → 参数调了但没生效，用户以为改过了
# 结论：**断点 key 必须含全部影响产出的维度**。
# ---------------------------------------------------------------------------

STATE_NAME = "state.json"
STATE_VERSION = 1


def state_key(stage, source_sha=None, source_chars=None, prompt_chars=None,
              model=None, temperature=None, seats=None, seat_count=None,
              panel_sha=None, clash_sha=None,
              rubric=RUBRIC_VERSION, prompt=PROMPT_VERSION, seatsv=SEATS_VERSION):
    """算一个断点 key：**所有影响产出的维度都在里面**。

    参数逐个都有关联的事故：
      source_sha / source_chars  材料内容变了必须重跑（摘要防"改了一个字却复用"）
      prompt_chars               实际喂给模型的字符数；截断上限变了必须重跑
      model / temperature        换模型或换温度就是换产出
      seats / seat_count         换席位组合 = 换立场组合，四席与两席的产出不是一回事
      panel_sha                  复用哪一份席位意见；那份文件变了必须重跑
      clash_sha                  复用哪一份对质结果
      rubric / prompt / seatsv   口径版本、提示词版本、席位定义版本
    """
    payload = {
        "v": STATE_VERSION,
        "stage": stage,
        "source_sha": source_sha,
        "source_chars": source_chars,
        "prompt_chars": prompt_chars,
        "model": model,
        "temperature": temperature,
        "seats": list(seats or []),
        "seat_count": seat_count,
        "panel_sha": panel_sha,
        "clash_sha": clash_sha,
        "rubric": rubric,
        "prompt": prompt,
        "seats_version": seatsv,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "{}:{}".format(stage, hashlib.sha256(blob).hexdigest()[:20])


def text_sha(text):
    """材料内容摘要（先做换行/空白归一，避免"只改了行尾空白"导致无谓重跑）。"""
    norm = re.sub(r"[ \t\r]+", " ", (text or "")).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def file_sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def json_sha(obj):
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


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
# 闸门：产出不许落在包内
#
# 为什么单独做一道闸门而不是"提示一下"：Skill 包的上传白名单只收
# `.md .py .txt .json .sh .js .yaml .yml .csv`，包内塞一张 png 会让上传直接 400。
# 写文件是**写操作**，写进去之前就要拦住，不能等用户打完卡再回滚。
# 退出码 2（usage）：这是用法错误，不是闸门判定，也不是上游失败。
# ---------------------------------------------------------------------------

def pkg_dir():
    return Path(__file__).resolve().parent.parent


def ensure_outside_pkg(path, what="输出目录", example="review-board-out"):
    """产出路径在包内 → 抛 PackagePathError（退出码 2）。"""
    root = pkg_dir()
    target = Path(path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return
    raise PackagePathError(
        "{} {} 在 Skill 包内（{}）。包内只允许白名单文本后缀，产出不许进包，"
        "请换到包外，例如 {}".format(
            what, target, root, Path(os.environ.get("TEMP") or ".") / example))


# ---------------------------------------------------------------------------
# 评审材料整理（`brief`，**纯本地零成本**）
#
# 为什么不调模型：评审材料只是把"大家要看同一份东西"这件事固定下来。
# 摘要、大纲、主张、数字都能确定性抽出来；多花一次调用不会让它更准，
# 只会让"先看看材料"这个动作开始花钱。所以这一步一次调用都不发。
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$", re.M)
NUM_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|％|万|亿|千|百|元|块|天|小时|分钟|人|个|条|次|篇|台|单)?")


def extract_numbers(text):
    """抽材料里的数字（含单位）：评审里最常被"记错"的就是这类硬信息。"""
    out, seen = [], set()
    for m in NUM_TOKEN_RE.finditer(text or ""):
        raw = m.group(0).strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        out.append({"raw": raw, "context": _ctx(text, m.start(), m.end())})
    return out[:60]


def _ctx(text, start, end, pad=16):
    return (text or "")[max(0, start - pad):min(len(text or ""), end + pad)].replace("\n", " ")


PROPER_PATTERNS = [
    (re.compile(r"《([^》]{1,30})》"), "书名"),
    (re.compile(r"[「“]([^」”]{2,20})[」”]"), "引号"),
    (re.compile(r"\b([A-Z][A-Za-z0-9\-]{1,20}(?:\s[A-Z][A-Za-z0-9\-]{1,20})?)\b"), "英文"),
    (re.compile(r"([\u4e00-\u9fff]{2,12}(?:公司|团队|平台|客户端|工具|软件|服务))"), "机构/产品"),
]
PROPER_STOP = {"ok", "vs", "etc", "eg", "ie", "nb", "json", "api", "cta", "url"}


def extract_proper(text):
    """抽专有名词（粗筛，抓不全也可能多报；只作材料索引，不作闸门）。"""
    out, seen = [], set()
    for rx, label in PROPER_PATTERNS:
        for m in rx.finditer(text or ""):
            raw = (m.group(1) or "").strip()
            if not raw or raw.lower() in PROPER_STOP or raw in seen:
                continue
            seen.add(raw)
            out.append({"kind": label, "raw": raw, "context": _ctx(text, m.start(), m.end())})
    return out[:50]


REVIEW_QUESTIONS = [
    "这份材料在什么条件下值得通过？",
    "什么情况下必须否决它？",
    "你最不能让步的一点是什么？",
]


def build_brief(text, source_path=None):
    """把待评材料整理成结构化评审材料（纯本地）。"""
    heads = [{"level": len(m.group(1)), "text": m.group(2)} for m in HEADING_RE.finditer(text or "")]
    hits_c, exempted = compliance_scan(text)
    ph = placeholder_hits(text)
    echo, echo_skips = prompt_echo_scan(text, label="材料")
    return {
        "source": str(source_path) if source_path else None,
        "sha": text_sha(text),
        "chars": char_count(text),
        "sentences": len(split_sentences(text)),
        "paragraphs": len(split_paras(text)),
        "headings": heads,
        "numbers": extract_numbers(text),
        "proper_nouns": extract_proper(text),
        "review_questions": list(REVIEW_QUESTIONS),
        "local_prescan": {
            "compliance": {"ok": not hits_c, "hits": hits_c, "exempted": exempted},
            "placeholder": {"ok": not ph, "hits": ph},
            "prompt_echo": {"ok": not echo, "hits": echo, "contain_skipped": echo_skips},
        },
        "note": ("本材料由本地整理（零调用）：大纲、数字、专有名词、本地预扫结果。"
                 "四席评审时会把材料全文原样发给每个席位。"),
    }


def char_count(text):
    """正文字符数（**不含空白**）——中英混排时这个数比 len() 更贴近"篇幅"。"""
    return len(re.sub(r"\s+", "", text or ""))


# ---------------------------------------------------------------------------
# 归一化与本地校验
# ---------------------------------------------------------------------------

def _clamp(v, lo=0, hi=10):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, v))


def normalize_seat(raw, seat, material_target):
    """把一席的模型返回归一化，并做**本地锚点校验**。

    锚定成功的那条会把 `quote` 就地修正成材料里的真实句子（`sentence` 字段）——
    模型引半句、连引两句都对不上时，报告里要显示的是材料原文，不是模型的转述。
    锚不上的记进 `unanchored_points`，**不进对质输入**。
    """
    raw = raw if isinstance(raw, dict) else {}
    verdict = (raw.get("verdict") or "").strip()
    if verdict not in SEAT_VERDICT_ANY:
        m = re.search(r"支持|有条件支持|反对", verdict)
        verdict = m.group(0) if m else "未表态"
    points_raw = raw.get("points") if isinstance(raw.get("points"), list) else []
    points_raw = [p for p in points_raw if isinstance(p, dict)][:8]
    ok_pts, bad_pts = [], []
    for p in points_raw:
        quote = (p.get("quote") or "").strip()
        good, rule, sent_no, sent = material_target.check(quote)
        item = {
            "quote": quote,
            "severity": (p.get("severity") or "中").strip() or "中",
            "why": (p.get("why") or "").strip(),
            "ask": (p.get("ask") or "").strip(),
            "anchor_rule": rule,
        }
        if good:
            item["sentence"] = sent
            item["sent_no"] = sent_no
            ok_pts.append(item)
        else:
            item["why_unverified"] = (
                "引文在材料里找不到（归一化后也不匹配任一整句，模糊相似度 < {:.2f}）"
                "——判为锚点幻觉，不进对质输入".format(ANCHOR_SIM))
            bad_pts.append(item)
    return {
        "id": seat["id"],
        "name": seat["name"],
        "goal": seat["goal"],
        "bias": seat["bias"],
        "verdict": verdict,
        "acceptability": _clamp(raw.get("acceptability", 5)),
        "must_have": (raw.get("must_have") or "").strip(),
        "kill_switch": (raw.get("kill_switch") or "").strip(),
        "points": ok_pts,
        "unanchored_points": bad_pts,
        "summary": (raw.get("summary") or "").strip(),
        "raw": raw,
    }


def anchor_stat_for(records, total_key="total"):
    """把一批 (ok, bad) 统计成锚点结论。"""
    verified = sum(1 for r in records if r)
    unanchored = len(records) - verified
    total = len(records)
    miss = (unanchored / float(total)) if total else 0.0
    return {
        "total": total, "verified": verified, "unanchored": unanchored,
        "miss_rate": round(miss, 3),
        "ok": not (total and miss > ANCHOR_MAX_MISS),
        "threshold": ANCHOR_MAX_MISS,
    }


def collect_seat_anchors(seats):
    """四席意见 + 对质 + 裁决条件三层锚点合并统计。"""
    recs = []
    rules = {}
    for s in seats:
        for p in s.get("points") or []:
            recs.append(True)
            rules[p.get("anchor_rule") or "-"] = rules.get(p.get("anchor_rule") or "-", 0) + 1
        for p in s.get("unanchored_points") or []:
            recs.append(False)
    return recs, rules


# ---------------------------------------------------------------------------
# 对质结果的本地校验
#
# 对质最容易注水的地方：把"其实两边都同意"的东西写成分歧，或者**替别的席位发言**。
# 所以每条分歧要过两道本地校验：
#   1. 两侧立场必须真的对立（支持 vs 反对），只有一边或两边同向 → 不算真分歧
#   2. 每个 side 的 quote 必须锚定到**那个席位自己说过的话**（锚不上 → 这一侧作废）
# 两侧都锚上、且立场对立 → 才进 `real_divergences`。
# ---------------------------------------------------------------------------

def validate_clash(raw, seats, material):
    """校验对质结果。返回结构化 dict（含 real_divergences / rejected_divergences）。"""
    raw = raw if isinstance(raw, dict) else {}
    divs_raw = raw.get("divergences") if isinstance(raw.get("divergences"), list) else []
    targets = {s["id"]: AnchorTarget(s["id"], SEAT_NAME.get(s["id"], s["id"]),
                                     seat_anchor_text(s)) for s in seats}
    real, rejected = [], []
    for d in divs_raw:
        if not isinstance(d, dict):
            continue
        topic = (d.get("topic") or "").strip()
        sides_raw = d.get("sides") if isinstance(d.get("sides"), list) else []
        rec = {
            "topic": topic,
            "crux": (d.get("crux") or "").strip(),
            "why_real": (d.get("why_real") or "").strip(),
            "cost_of_each_side": (d.get("cost_of_each_side") or "").strip(),
            "tie_break": (d.get("tie_break") or "").strip(),
            "sides": [], "problems": [],
        }
        if len(sides_raw) < 2:
            rec["problems"].append("只有 {} 侧，构不成对质".format(len(sides_raw)))
            rejected.append(rec)
            continue
        for sd in sides_raw:
            if not isinstance(sd, dict):
                continue
            stance = (sd.get("stance") or "").strip()
            ids = [as_seat_id(x) for x in (sd.get("seats") or [])]
            ids = [x for x in ids if x]
            quote = (sd.get("quote") or "").strip()
            side = {"stance": stance, "seats": ids, "quote": quote, "anchor": {}}
            if not ids:
                rec["problems"].append("有一侧的 seats 不是有效席位 id：{}".format(sd.get("seats")))
                continue
            anchored = {}
            for sid in ids:
                ok, rule, sent_no, sent = targets[sid].check(quote)
                anchored[sid] = {"ok": ok, "rule": rule, "sent_no": sent_no, "sentence": sent}
            side["anchor"] = anchored
            # 至少要锚定到该侧**其中一个**席位说过的话，否则这一侧是替别人发言
            if not any(v["ok"] for v in anchored.values()):
                side["why_unverified"] = (
                    "这一侧的引文在它标注的席位意见里找不到——疑似替别的席位发言或编造引文，"
                    "该侧作废")
            rec["sides"].append(side)
        good_sides = [x for x in rec["sides"]
                      if not x.get("why_unverified") and x.get("seats")]
        pos = [x for x in good_sides if x["stance"] in ("支持", "有条件支持")]
        neg = [x for x in good_sides if x["stance"] == "反对"]
        if not (pos and neg):
            rec["problems"].append(
                "两侧立场没有真的对立（有效侧立场：{}）——"
                "结论一致的不能算分歧".format(
                    "、".join(x["stance"] or "空" for x in good_sides) or "无"))
            rejected.append(rec)
            continue
        if len(good_sides) != len(rec["sides"]):
            rec["problems"].append("有 {} 侧引文未锚定，已作废该侧".format(
                len(rec["sides"]) - len(good_sides)))
        # 同一席位同时出现在两侧 = 标注自相矛盾。
        # 真机实测出现过（业务负责人被同时放进「支持」与「反对」两侧）。
        # **不因此作废这条分歧**：争点本身可能是真的，作废会把真内容丢掉；
        # 但也**不装作没看见**——标出来让人自己判断该信哪一边。
        pos_ids = {sid for x in pos for sid in x["seats"]}
        neg_ids = {sid for x in neg for sid in x["seats"]}
        both = sorted(pos_ids & neg_ids)
        if both:
            rec["seat_on_both_sides"] = both
            rec["problems"].append(
                "同一席位同时出现在两侧（{}）——标注自相矛盾，已标出但不作废该条".format(
                    "、".join(SEAT_NAME.get(x, x) for x in both)))
        rec["seat_ids"] = sorted({sid for x in good_sides for sid in x["seats"]})
        real.append(rec)
    shared = raw.get("shared_ground") if isinstance(raw.get("shared_ground"), list) else []
    return {
        "real_divergences": real,
        "rejected_divergences": rejected,
        "shared_ground": [str(x) for x in shared][:10],
        "no_divergence_reason": (raw.get("no_divergence_reason") or "").strip(),
        "summary": (raw.get("summary") or "").strip(),
        "raw": raw,
    }


def validate_verdict(raw, seats, clash):
    """校验裁决书。条件与少数派都要过锚点与席位校验（不采信自报）。"""
    raw = raw if isinstance(raw, dict) else {}
    targets = {s["id"]: AnchorTarget(s["id"], SEAT_NAME.get(s["id"], s["id"]),
                                     seat_anchor_text(s)) for s in seats}
    decision = (raw.get("decision") or "").strip()
    if decision not in DECISION_ANY:
        m = re.search(r"有条件通过|通过|否决", decision)
        decision = m.group(0) if m else decision
    conds = []
    for i, c in enumerate(raw.get("conditions") or [], 1):
        if not isinstance(c, dict):
            continue
        ids = [as_seat_id(x) for x in (c.get("from_seats") or [])]
        ids = [x for x in ids if x]
        quote = (c.get("quote") or "").strip()
        anchor = {}
        for sid in ids:
            ok, rule, sent_no, sent = targets[sid].check(quote)
            anchor[sid] = {"ok": ok, "rule": rule, "sent_no": sent_no, "sentence": sent}
        cond = {
            "id": c.get("id") if isinstance(c.get("id"), int) else i,
            "what": (c.get("what") or "").strip(),
            "from_seats": ids,
            "quote": quote,
            "how_to_verify": (c.get("how_to_verify") or "").strip(),
            "anchor": anchor,
        }
        if not ids:
            cond["problem"] = "from_seats 不是有效席位 id：{}".format(c.get("from_seats"))
        elif quote and not any(v["ok"] for v in anchor.values()):
            cond["problem"] = ("这条条件的引文在它标注的席位意见里找不到"
                               "——不采信自报，请人工复核")
        conds.append(cond)
    minority = []
    for m in raw.get("minority") or []:
        if not isinstance(m, dict):
            continue
        sid = as_seat_id(m.get("seat"))
        minority.append({
            "seat": sid or str(m.get("seat")),
            "seat_name": SEAT_NAME.get(sid) or str(m.get("seat")),
            "position": (m.get("position") or "").strip(),
            "why_kept": (m.get("why_kept") or "").strip(),
        })
    votes = []
    for v in raw.get("vote_table") or []:
        if not isinstance(v, dict):
            continue
        sid = as_seat_id(v.get("seat"))
        votes.append({"seat": sid or str(v.get("seat")),
                      "seat_name": SEAT_NAME.get(sid) or str(v.get("seat")),
                      "verdict": (v.get("verdict") or "").strip(),
                      "one_line": (v.get("one_line") or "").strip()})
    return {
        "decision": decision,
        "conditions": conds,
        "minority": minority,
        "model_vote_table": votes,
        "declared_dissent": [x for x in (raw.get("dissenting_seats") or []) if isinstance(x, str)],
        "rationale": (raw.get("rationale") or "").strip(),
        "summary": (raw.get("summary") or "").strip(),
        "raw": raw,
    }


def local_vote_table(seats):
    """本地按四席结论拼的票表（**不采信模型自报**），并对自报票表做交叉核对。"""
    return [{"seat": s["id"], "seat_name": s["name"], "verdict": s.get("verdict") or "未表态",
             "acceptability": s.get("acceptability")} for s in seats]


def vote_mismatch(seats, verdict):
    """本地票表 vs 模型自报票表：对不上的逐条列出。"""
    local = {s["id"]: (s.get("verdict") or "未表态") for s in seats}
    out = []
    for v in verdict.get("model_vote_table") or []:
        sid = v.get("seat")
        if sid in local and v.get("verdict") and v["verdict"] != local[sid]:
            out.append({"seat": sid, "seat_name": SEAT_NAME.get(sid, str(sid)),
                        "local": local[sid], "declared": v["verdict"]})
    missing = [sid for sid in local if sid not in {v.get("seat") for v in
                                                   (verdict.get("model_vote_table") or [])}]
    return {"mismatches": out, "missing_from_table": missing,
            "note": ("票表以本地从四份意见里读出的结论为准；这一栏只用来暴露"
                     "裁决书自报票表与四席实际结论不一致的地方。")}


# ---------------------------------------------------------------------------
# 产出文本（供闸门二 / 三扫描）
#
# ⚠️ 只拼**人读的散文字段**，绝不拼 JSON 序列化 —— 序列化里全是 `{}`，
# 拿它扫占位符会 100% 误报。这条边界踩过一次就够。
# ---------------------------------------------------------------------------

def output_prose(seats, clash, verdict):
    parts = []
    for s in seats:
        parts.extend([s.get("must_have") or "", s.get("kill_switch") or "",
                      s.get("summary") or ""])
        for p in s.get("points") or []:
            parts.extend([p.get("why") or "", p.get("ask") or ""])
        for p in s.get("unanchored_points") or []:
            parts.extend([p.get("why") or "", p.get("ask") or ""])
    for d in (clash or {}).get("real_divergences") or []:
        parts.extend([d.get("topic") or "", d.get("crux") or "", d.get("why_real") or "",
                      d.get("cost_of_each_side") or "", d.get("tie_break") or ""])
    for d in (clash or {}).get("rejected_divergences") or []:
        parts.extend([d.get("topic") or "", d.get("crux") or ""])
    for x in (clash or {}).get("shared_ground") or []:
        parts.append(str(x))
    parts.append((clash or {}).get("summary") or "")
    v = verdict or {}
    parts.extend([v.get("rationale") or "", v.get("summary") or ""])
    for c in v.get("conditions") or []:
        parts.extend([c.get("what") or "", c.get("how_to_verify") or ""])
    for m in v.get("minority") or []:
        parts.extend([m.get("position") or "", m.get("why_kept") or ""])
    return "\n".join(x for x in parts if x)


# ---------------------------------------------------------------------------
# 闸门总评估
# ---------------------------------------------------------------------------

def evaluate_gates(material, seats, clash, verdict, material_meta=None,
                   unanimous_ok=False):
    """跑全部**本地**闸门，返回结构化结论。

    硬闸门 = compliance / placeholder / output_* / prompt_echo / anchor / stance / verdict
    八项；材料侧与产出侧分开记，因为它们指向的处置完全不同
    （材料踩线 → 别评了；产出踩线 → 主席没按纪律写）。

    `unanimous_ok=True` 时，「四席结论全同且零分歧」从硬闸门降级为标红提示
    （对应 `run --unanimous-ok`：确认材料本身无争议时才用）。
    """
    hits_c, exempted = compliance_scan(material)
    mat_ph = placeholder_hits(material)
    prose = output_prose(seats, clash, verdict)
    out_ph = placeholder_hits(prose)
    out_fresh, out_quoted, out_mentioned, out_contextual, out_exempted = \
        compliance_scan_output(prose, material)
    out_echo, out_echo_skips = prompt_echo_scan(prose, label="产出")
    out_echo_skips = _dedupe_skips(out_echo_skips)

    # 锚点：四席意见 + 对质两侧 + 裁决条件，三层合并
    recs, rules = collect_seat_anchors(seats)
    for d in (clash or {}).get("real_divergences") or []:
        for sd in d.get("sides") or []:
            for _sid, a in (sd.get("anchor") or {}).items():
                recs.append(bool(a.get("ok")))
                if a.get("ok"):
                    rules[a.get("rule") or "-"] = rules.get(a.get("rule") or "-", 0) + 1
    for d in (clash or {}).get("rejected_divergences") or []:
        for sd in d.get("sides") or []:
            for _sid, a in (sd.get("anchor") or {}).items():
                recs.append(bool(a.get("ok")))
    for c in (verdict or {}).get("conditions") or []:
        for _sid, a in (c.get("anchor") or {}).items():
            recs.append(bool(a.get("ok")))
            if a.get("ok"):
                rules[a.get("rule") or "-"] = rules.get(a.get("rule") or "-", 0) + 1
    anchor = anchor_stat_for(recs)
    anchor["rules"] = rules
    if not anchor["ok"]:
        anchor["why"] = ("{} 条引文里 {} 条在对应文本里找不到（未锚定率 {:.0%} > {:.0%}）"
                         "——意见没有落到原文上，这份评审不可执行".format(
                             anchor["total"], anchor["unanchored"],
                             anchor["miss_rate"], ANCHOR_MAX_MISS))

    stance = stance_check(seats) if seats else {}
    real_divs = (clash or {}).get("real_divergences") or []
    stance_problems, stance_red = [], []
    if stance:
        if stance.get("overlap_pairs"):
            for p in stance["overlap_pairs"]:
                stance_problems.append(
                    "「{}」与「{}」的意见重叠度 {:.2f} ≥ {:.2f}（短的一份 {} 个二元组）——"
                    "两席说的是同一套话，立场没起作用".format(
                        SEAT_NAME.get(p["a"], p["a"]), SEAT_NAME.get(p["b"], p["b"]),
                        p["overlap"], STANCE_OVERLAP, p["min_grams"]))
        if stance.get("red_pairs"):
            for p in stance["red_pairs"]:
                stance_red.append(
                    "「{}」与「{}」的意见重叠度 {:.2f}（阈值 {:.2f}）——"
                    "两边说得太像，建议人工看一眼".format(
                        SEAT_NAME.get(p["a"], p["a"]), SEAT_NAME.get(p["b"], p["b"]),
                        p["overlap"], STANCE_OVERLAP))
        for t in stance.get("thin_own_words") or []:
            stance_red.append(
                "「{}」自己的话太少（{} 个二元组 < {}）——它可能只在转述材料原文，"
                "没给出本席位的判断".format(SEAT_NAME.get(t["seat"], t["seat"]),
                                        t["own_grams"], STANCE_MIN_OWN_GRAMS))
        if not real_divs and stance.get("all_same_verdict") and len(seats) >= 2:
            why = ("对质没找到任何真实分歧，且 {} 席结论完全相同（{}）——"
                   "本包不把它当成「一致通过」：立场不同的角色对同一份材料零分歧，"
                   "基本只能说明立场没起作用").format(
                       len(seats), "、".join(stance.get("distinct_verdict_seats") or []))
            if unanimous_ok:
                stance_red.append(why + "（已用 --unanimous-ok 降级为提示）")
            else:
                stance_problems.append(why + "。材料确实无争议时用 --unanimous-ok 降级")
    stance_gate = {
        "ok": not stance_problems,
        "problems": stance_problems,
        "red_hints": stance_red,
        "red": bool(stance_problems) or bool(stance_red) or bool(stance.get("red_pairs")),
        "overlap_threshold": STANCE_OVERLAP,
        "min_grams": STANCE_MIN_GRAMS,
        "max_overlap": (stance or {}).get("max_overlap"),
        "pairs": (stance or {}).get("pairs"),
    }

    vg_ok, vg_problems, required, listed = verdict_gate(
        (verdict or {}).get("decision"), (verdict or {}).get("conditions"),
        (verdict or {}).get("minority"), seats, real_divs)

    gates = {
        "compliance": {"ok": not hits_c, "target": "待评材料", "hits": hits_c,
                       "exempted": exempted},
        "placeholder": {"ok": not mat_ph, "target": "待评材料", "hits": mat_ph},
        "output_compliance": {"ok": not out_fresh, "target": "四席意见 / 对质 / 裁决书",
                              "hits": out_fresh, "quoted_from_material": out_quoted,
                              "mentioned_as_warning": out_mentioned,
                              "contextual_only": out_contextual, "exempted": out_exempted,
                              "rule": ("产出侧只查高风险条目，并排除两类正常写法："
                                       "材料里已有的词（引用被审对象）与"
                                       "小句里带禁止/举证/风险标记词的（提到而非主张）；"
                                       "中低风险项列在 contextual_only 里提示人工看，不拦")},
        "output_placeholder": {"ok": not out_ph, "target": "四席意见 / 对质 / 裁决书",
                               "hits": out_ph},
        "prompt_echo": {"ok": not out_echo, "target": "四席意见 / 对质 / 裁决书",
                        "hits": out_echo, "contain_skipped": out_echo_skips,
                        "window": {"max_ratio": ECHO_CONTAIN_MAX_RATIO,
                                   "min_sample": ECHO_CONTAIN_MIN_SAMPLE,
                                   "floor": ECHO_MIN_LEN_FLOOR}},
        "anchor": anchor,
        "stance": stance_gate,
        "verdict": {"ok": vg_ok, "problems": vg_problems,
                    "required_minority": required, "listed_minority": listed,
                    "decision": (verdict or {}).get("decision"),
                    "conditions": len((verdict or {}).get("conditions") or [])},
    }
    return gates


HARD_GATE_KEYS = ("compliance", "placeholder", "output_compliance", "output_placeholder",
                  "prompt_echo", "anchor", "stance", "verdict")


def gate_failed(gates):
    for k in HARD_GATE_KEYS:
        v = gates.get(k)
        if v and not v.get("ok", True):
            return True
    return False


def gate_summary_lines(gates):
    """给 stderr 的汇总行（闸门命中一律汇总，别让人去翻 JSON）。"""
    lines = []
    for k in HARD_GATE_KEYS:
        v = gates.get(k) or {}
        if v.get("ok", True):
            continue
        if k in ("compliance", "output_compliance"):
            for h in (v.get("hits") or [])[:5]:
                lines.append("[{}] {} 风险：命中「{}」——{}（{}）".format(
                    k, h.get("level"), h.get("word"), h.get("why"), h.get("context")))
        elif k in ("placeholder", "output_placeholder"):
            for h in (v.get("hits") or [])[:5]:
                lines.append("[{}] {}".format(k, h.get("why")))
        elif k == "prompt_echo":
            for h in (v.get("hits") or [])[:3]:
                lines.append("[{}] {}".format(k, h.get("why")))
        elif k == "anchor":
            lines.append("[anchor] {}".format(v.get("why") or "引文未锚定率过高"))
        elif k == "stance":
            for p in (v.get("problems") or [])[:4]:
                lines.append("[stance] " + p)
        elif k == "verdict":
            for p in (v.get("problems") or [])[:4]:
                lines.append("[verdict] " + p)
    return lines


# ---------------------------------------------------------------------------
# 渲染（人读文本）
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "✗ " + s
    return "\x1b[31m{}\x1b[0m".format(s)


def render_seats_md():
    out = ["# 三剪客 · 评审委员会：四个席位", "",
           "> 每个席位有**自己独立的目标函数**与天然倾向。四个目标函数必须真的会互相否掉对方，",
           "> 否则就不是四个立场，而是同一份意见的四种措辞（本地闸门五会拦）。", ""]
    for i, s in enumerate(SEATS, 1):
        out.append("## 第 {} 席 · {}（`{}`）".format(i, s["name"], s["id"]))
        out.append("")
        out.append("- **目标函数**：{}".format(s["goal"]))
        out.append("- **天然倾向**：{}".format(s["bias"]))
        out.append("- **评审视角**：{}".format(s["question"]))
        out.append("- **盯的点**：")
        for x in s["focus"]:
            out.append("  - {}".format(x))
        out.append("")
    out.append("## 四个立场为什么会互相否掉")
    out.append("")
    out.append("| 场景 | 一个席位要 | 另一个席位正好在拦 |")
    out.append("|---|---|---|")
    out.append("| 加转化 | 业务负责人要补 CTA 与验收口径 | 合规官在拦那句承诺（无依据） |")
    out.append("| 说人话 | 用户代言人嫌术语堆砌 | 竞品分析师觉得那些术语正是差异化 |")
    out.append("| 讲差异 | 竞品分析师要独家声称 | 合规官不许「独家/唯一」无依据 |")
    out.append("| 砍链路 | 业务负责人要砍掉一步 | 用户代言人说那一步正是信任来源 |")
    out.append("")
    out.append("零成本命令：`run.py seats`")
    return "\n".join(out)


def render_brief_md(brief, text):
    out = ["# 评审材料（本地整理，零调用）", ""]
    out.append("- 来源：{}".format(brief.get("source") or "（--file）"))
    out.append("- 篇幅：{} 字符（不含空白）· {} 句 · {} 段".format(
        brief["chars"], brief["sentences"], brief["paragraphs"]))
    out.append("- 内容摘要：`{}`".format((brief.get("sha") or "")[:16]))
    out.append("")
    if brief["headings"]:
        out.append("## 大纲")
        out.append("")
        for h in brief["headings"]:
            out.append("{} {}".format("  " * (h["level"] - 1), h["text"]))
        out.append("")
    if brief["numbers"]:
        out.append("## 材料里的数字（{} 条，评审时最容易被记错的就是这类硬信息）".format(
            len(brief["numbers"])))
        out.append("")
        for n in brief["numbers"][:30]:
            out.append("- `{}` —— {}".format(n["raw"], n["context"]))
        out.append("")
    if brief["proper_nouns"]:
        out.append("## 专有名词（{} 条，粗筛）".format(len(brief["proper_nouns"])))
        out.append("")
        out.append("、".join("{}「{}」".format(p["kind"], p["raw"]) for p in brief["proper_nouns"][:30]))
        out.append("")
    pre = brief["local_prescan"]
    out.append("## 本地预扫（四席评审前先看这一栏）")
    out.append("")
    for key, label in (("compliance", "合规（违禁词）"), ("placeholder", "占位符残留"),
                       ("prompt_echo", "照抄提示词示例")):
        v = pre[key]
        if v["ok"]:
            out.append("- ✅ {}：未命中".format(label))
        else:
            out.append("- ✗ **{}：命中** —— {}".format(
                label, "；".join(h.get("why") or "" for h in v["hits"][:3])))
    if pre["compliance"].get("exempted"):
        out.append("- （合规豁免 {} 处：「最X」后接程度/比较词且不在句首，按普通中文用法放行）"
                   .format(len(pre["compliance"]["exempted"])))
    out.append("")
    out.append("## 每个席位都要回答的三个问题")
    out.append("")
    for q in brief["review_questions"]:
        out.append("- {}".format(q))
    out.append("")
    out.append("## 待评材料全文")
    out.append("")
    out.append(text or "")
    out.append("")
    return "\n".join(out)


def render_panel_md(seats, isolation):
    out = ["# 四席独立评审（信息隔离）", ""]
    out.append("> 四席各是一次**独立调用**：每席的提示词里只有本席位的立场块，"
               "没有任何其它席位的文字。对质在下一阶段才发生。")
    out.append("")
    out.append("| 席位 | 结论 | 可接受度 | 锚定意见 | 未锚定 |")
    out.append("|---|---|---|---|---|")
    for s in seats:
        out.append("| {} | {} | {}/10 | {} | {} |".format(
            s["name"], s["verdict"], s.get("acceptability"),
            len(s.get("points") or []), len(s.get("unanchored_points") or [])))
    out.append("")
    for s in seats:
        out.append("## {}（`{}`）".format(s["name"], s["id"]))
        out.append("")
        out.append("- 目标函数：{}".format(s["goal"]))
        out.append("- 结论：**{}**（可接受度 {}/10）".format(s["verdict"], s.get("acceptability")))
        out.append("- 最不能让步：{}".format(s.get("must_have") or "（未给出）"))
        out.append("- 主张否决的条件：{}".format(s.get("kill_switch") or "（未给出）"))
        out.append("")
        if s.get("points"):
            for i, p in enumerate(s["points"], 1):
                line = "{}. [{}] 第 {} 句（锚点 {}）：{}".format(
                    i, p.get("severity"), p.get("sent_no"), p.get("anchor_rule"),
                    p.get("sentence") or p.get("quote"))
                if (p.get("severity") or "") == "高":
                    line = _red(line)
                out.append(line)
                out.append("   - 问题：{}".format(p.get("why") or "-"))
                out.append("   - 要求：{}".format(p.get("ask") or "-"))
        else:
            out.append("（本席位未提出问题）")
        out.append("")
        if s.get("summary"):
            out.append("总评：{}".format(s["summary"]))
            out.append("")
        if s.get("unanchored_points"):
            out.append("### 未通过锚点校验的意见（{} 条，**不进对质输入**）".format(
                len(s["unanchored_points"])))
            out.append("")
            for p in s["unanchored_points"]:
                out.append("- 引文「{}」——{}".format((p.get("quote") or "")[:60],
                                                  p.get("why_unverified") or ""))
            out.append("")
    out.append("## 信息隔离证据")
    out.append("")
    out.append("| 席位 | 提示词字符 | 提示词 SHA256(前 16) | 提示词里出现的其它席位名 |")
    out.append("|---|---|---|---|")
    for sid, rec in (isolation.get("seats") or {}).items():
        out.append("| {} | {} | {} | {} |".format(
            SEAT_NAME.get(sid, sid), rec.get("prompt_chars"), (rec.get("prompt_sha") or "")[:16],
            "、".join(rec.get("other_seat_names_found") or []) or "无"))
    out.append("")
    out.append("隔离说明：{}".format(isolation.get("note") or ""))
    return "\n".join(out)


def render_clash_md(clash):
    out = ["# 对质：真实分歧", ""]
    out.append("> 这一步**故意打破隔离**：把四份此前互相看不到的意见摆到同一张桌上，"
               "找出真的会让结论不同的分歧。只是措辞不同、结论一致的，不算分歧。")
    out.append("")
    real = clash.get("real_divergences") or []
    rejected = clash.get("rejected_divergences") or []
    if not real:
        out.append("## 没有找到真实分歧")
        out.append("")
        out.append("理由（模型自述）：{}".format(clash.get("no_divergence_reason") or "（未说明）"))
        out.append("")
        out.append("> ⚠️ 本地闸门五会复核这一结论：四席结论全同且零分歧时，"
                   "本包**不把它当成「一致通过」**，而是判「立场失效」（退出码 3）。")
        out.append("")
    for i, d in enumerate(real, 1):
        out.append("## 争点 {} · {}".format(i, d.get("topic") or "（无标题）"))
        out.append("")
        out.append("- **争的到底是**：{}".format(d.get("crux") or "-"))
        out.append("- **涉及席位**：{}".format(
            "、".join(SEAT_NAME.get(x, x) for x in (d.get("seat_ids") or []))))
        out.append("- **为什么是真分歧**：{}".format(d.get("why_real") or "-"))
        out.append("- **各让一步的代价**：{}".format(d.get("cost_of_each_side") or "-"))
        out.append("- **要选一边的话**：{}".format(d.get("tie_break") or "-"))
        if d.get("seat_on_both_sides"):
            out.append("- ⚠️ **同一席位被同时放到了两侧**（{}）——标注自相矛盾，"
                       "本地没有作废这条分歧（争点本身可能是真的），请人工判断该信哪一边"
                       .format("、".join(SEAT_NAME.get(x, x)
                                       for x in d["seat_on_both_sides"])))
        out.append("")
        out.append("| 一方立场 | 席位 | 该席位原话（本地已锚定） |")
        out.append("|---|---|---|")
        for sd in d.get("sides") or []:
            sent = ""
            for _sid, a in (sd.get("anchor") or {}).items():
                if a.get("ok"):
                    sent = a.get("sentence") or ""
                    break
            out.append("| {} | {} | {} |".format(
                sd.get("stance") or "-",
                "、".join(SEAT_NAME.get(x, x) for x in (sd.get("seats") or [])),
                (sent or sd.get("quote") or "")[:80]))
        out.append("")
    if rejected:
        out.append("## 被判为「伪分歧」的条目（{} 条，本地剔出）".format(len(rejected)))
        out.append("")
        out.append("这一栏是**防注水**用的：两侧立场没有真的对立、或引文锚不到说话人，"
                   "都不算分歧。登在这里是为了让你看到模型试图把什么当成分歧。")
        out.append("")
        for i, d in enumerate(rejected, 1):
            out.append("- {}. 「{}」——{}".format(
                i, (d.get("topic") or "")[:40], "；".join(d.get("problems") or []) or "未通过校验"))
        out.append("")
    if clash.get("shared_ground"):
        out.append("## 四席其实都同意的点（背景共识，不是分歧）")
        out.append("")
        for x in clash["shared_ground"]:
            out.append("- {}".format(x))
        out.append("")
    if clash.get("summary"):
        out.append("## 总评")
        out.append("")
        out.append(clash["summary"])
        out.append("")
    return "\n".join(out)


def render_verdict_md(verdict, seats, vote_audit):
    v = verdict
    out = ["# 裁决书", ""]
    out.append("> 裁决 = 结论 + **条件清单** + **少数派意见保留在案**。"
               "三者缺一，本地闸门六就会拦下这份裁决。")
    out.append("")
    out.append("## 结论：{}".format(v.get("decision") or "（未给出）"))
    out.append("")
    if v.get("summary"):
        out.append(v["summary"])
        out.append("")
    out.append("## 票表（本地从四份意见读出，**不采信自报**）")
    out.append("")
    out.append("| 席位 | 结论 | 可接受度 |")
    out.append("|---|---|---|")
    for r in local_vote_table(seats):
        out.append("| {} | {} | {}/10 |".format(r["seat_name"], r["verdict"], r["acceptability"]))
    out.append("")
    if vote_audit.get("mismatches"):
        out.append("> ⚠️ 裁决书自报的票表与四席实际结论不一致的地方：")
        for m in vote_audit["mismatches"]:
            out.append("> - {}：本地读到「{}」，自报「{}」".format(
                m["seat_name"], m["local"], m["declared"]))
        out.append("")
    out.append("## 必须满足的条件（{} 条）".format(len(v.get("conditions") or [])))
    out.append("")
    if not v.get("conditions"):
        out.append("（没有条件清单。若结论是「有条件通过」，本地闸门六会直接拦下。）")
        out.append("")
    for c in v.get("conditions") or []:
        out.append("{}. **{}**".format(c.get("id"), c.get("what") or "-"))
        out.append("   - 来自：{}".format("、".join(
            SEAT_NAME.get(x, x) for x in (c.get("from_seats") or [])) or "（未标注席位）"))
        sent = ""
        for _sid, a in (c.get("anchor") or {}).items():
            if a.get("ok"):
                sent = a.get("sentence") or ""
                break
        out.append("   - 该席位原话：{}".format((sent or c.get("quote") or "-")[:100]))
        out.append("   - 怎么算满足：{}".format(c.get("how_to_verify") or "-"))
        if c.get("problem"):
            out.append("   - ⚠️ {}".format(c["problem"]))
        out.append("")
    out.append("## 少数派意见（保留在案，不许抹平）")
    out.append("")
    if not v.get("minority"):
        out.append("（无。若与最终裁决方向不一致的席位没有出现在这里，本地闸门六会拦下。）")
        out.append("")
    for m in v.get("minority") or []:
        out.append("- **{}**：{}".format(m.get("seat_name") or m.get("seat"), m.get("position") or "-"))
        if m.get("why_kept"):
            out.append("  - 为什么保留：{}".format(m["why_kept"]))
    out.append("")
    if v.get("rationale"):
        out.append("## 裁决理由（要正面回应每个争点）")
        out.append("")
        out.append(v["rationale"])
        out.append("")
    return "\n".join(out)


def render_report_md(brief, seats, clash, verdict, gates, vote_audit, usage_dict,
                     model, source_path, state_info=None):
    out = ["# 评审委员会 · 总报告", ""]
    out.append("- 待评材料：{}".format(source_path or "（--file）"))
    out.append("- 材料篇幅：{} 字符（不含空白）· {} 句".format(brief["chars"], brief["sentences"]))
    out.append("- 材料摘要：`{}`".format((brief.get("sha") or "")[:16]))
    out.append("- 模型：`{}`　端点：`POST /api/v1/chat/completions`".format(model))
    out.append("- 调用：{} 次 · token prompt={} completion={} total={}".format(
        usage_dict.get("calls"), usage_dict.get("prompt_tokens"),
        usage_dict.get("completion_tokens"), usage_dict.get("total_tokens")))
    if usage_dict.get("has_price"):
        out.append("- 估算：{:g} 点 ≈ ¥{:g}（按你填的单价，真实扣费以账户流水为准）".format(
            usage_dict.get("points") or 0, usage_dict.get("yuan") or 0))
    else:
        out.append("- 金额：文本模型网关不公布单价，**未折算**（要折算请传 --price-in / --price-out）")
    out.append("")
    out.append("## 1. 四席独立评审（信息隔离）")
    out.append("")
    out.append("| 席位 | 结论 | 可接受度 | 意见数 | 未锚定 | 底线 |")
    out.append("|---|---|---|---|---|---|")
    for s in seats:
        out.append("| {} | {} | {}/10 | {} | {} | {} |".format(
            s["name"], s["verdict"], s.get("acceptability"),
            len(s.get("points") or []), len(s.get("unanchored_points") or []),
            (s.get("must_have") or "-")[:40]))
    out.append("")
    for s in seats:
        out.append("### {} —— {}".format(s["name"], s["verdict"]))
        out.append("")
        for i, p in enumerate(s.get("points") or [], 1):
            out.append("{}. [{}] {}".format(i, p.get("severity"), p.get("sentence") or p.get("quote")))
            out.append("   - 问题：{}".format(p.get("why") or "-"))
            out.append("   - 要求：{}".format(p.get("ask") or "-"))
        if not s.get("points"):
            out.append("（未提出问题）")
        out.append("")
    out.append("## 2. 对质：真实分歧 {} 个（伪分歧剔出 {} 个）".format(
        len(clash.get("real_divergences") or []), len(clash.get("rejected_divergences") or [])))
    out.append("")
    for i, d in enumerate(clash.get("real_divergences") or [], 1):
        out.append("{}. **{}**".format(i, d.get("topic") or "-"))
        out.append("   - 争点：{}".format(d.get("crux") or "-"))
        out.append("   - 涉及：{}".format("、".join(
            SEAT_NAME.get(x, x) for x in (d.get("seat_ids") or []))))
        out.append("   - 为什么是真分歧：{}".format(d.get("why_real") or "-"))
        out.append("   - 各让一步的代价：{}".format(d.get("cost_of_each_side") or "-"))
        out.append("   - 要选一边：{}".format(d.get("tie_break") or "-"))
        out.append("")
    if not (clash.get("real_divergences") or []):
        out.append("（没有真实分歧。模型自述理由：{}）".format(
            clash.get("no_divergence_reason") or "（未说明）"))
        out.append("")
    out.append("## 3. 裁决书")
    out.append("")
    out.append("### 结论：{}".format(verdict.get("decision") or "（未给出）"))
    out.append("")
    out.append("### 条件清单（{} 条）".format(len(verdict.get("conditions") or [])))
    out.append("")
    for c in verdict.get("conditions") or []:
        out.append("- **{}**（来自 {}）｜怎么算满足：{}".format(
            c.get("what") or "-",
            "、".join(SEAT_NAME.get(x, x) for x in (c.get("from_seats") or [])) or "-",
            c.get("how_to_verify") or "-"))
    if not (verdict.get("conditions") or []):
        out.append("- （无）")
    out.append("")
    out.append("### 少数派意见（保留在案）")
    out.append("")
    for m in verdict.get("minority") or []:
        out.append("- **{}**：{}".format(m.get("seat_name") or m.get("seat"),
                                        m.get("position") or "-"))
    if not (verdict.get("minority") or []):
        out.append("- （无）")
    out.append("")
    if verdict.get("rationale"):
        out.append("### 裁决理由")
        out.append("")
        out.append(verdict["rationale"])
        out.append("")
    out.append("## 4. 本地闸门")
    out.append("")
    out.append("| 闸门 | 结果 | 说明 |")
    out.append("|---|---|---|")
    label = {"compliance": "合规（材料）", "placeholder": "占位符（材料）",
             "output_compliance": "合规（产出）", "output_placeholder": "占位符（产出）",
             "prompt_echo": "照抄提示词示例", "anchor": "评审锚点（三层引文）",
             "stance": "立场有效性", "verdict": "裁决完整性"}
    for k in HARD_GATE_KEYS:
        v = gates.get(k) or {}
        ok = v.get("ok", True)
        note = ""
        if k == "compliance" and not ok:
            note = "命中：" + "、".join(h["word"] for h in v["hits"][:4])
        elif k == "output_compliance":
            note = ("命中（新增宣称）：" + "、".join(h["word"] for h in (v.get("hits") or [])[:4])
                    if not ok else "")
            if v.get("quoted_from_material"):
                note += "（另有 {} 处是引用材料原文，不计命中）".format(
                    len(v["quoted_from_material"]))
            if v.get("contextual_only"):
                note += "；中低风险描述性用语 {} 处（不拦，见 JSON）".format(
                    len(v["contextual_only"]))
        elif k in ("placeholder", "output_placeholder") and not ok:
            note = "命中：" + "、".join(h["kind"] for h in v["hits"][:4])
        elif k == "prompt_echo":
            note = "命中 {} 处".format(len(v.get("hits") or []))
            if v.get("contain_skipped"):
                note += "；contain 判据因适用窗口跳过 {} 处".format(
                    sum(x.get("times", 1) for x in v["contain_skipped"]))
        elif k == "anchor":
            note = "{} 条引文 / 未锚定 {} 条（{:.0%}）".format(
                v.get("total"), v.get("unanchored"), v.get("miss_rate") or 0)
            if not ok:
                note = _red(note)
        elif k == "stance":
            note = "任一对席位最大重叠度 {}".format(v.get("max_overlap"))
            if not ok:
                note = _red(note)
        elif k == "verdict":
            note = "结论 {} / 条件 {} 条 / 少数派 {} 条".format(
                v.get("decision"), v.get("conditions"), len(v.get("listed_minority") or []))
        out.append("| {} | {} | {} |".format(label.get(k, k), "✅" if ok else "✗ 命中", note))
    out.append("")
    bad = [k for k in HARD_GATE_KEYS if not (gates.get(k) or {}).get("ok", True)]
    if bad:
        out.append("> ⚠️ 命中 {} 项硬闸门：{}。命中项已标红，处置方式见 references/成本与排错.md。".format(
            len(bad), "、".join(label.get(k, k) for k in bad)))
    else:
        out.append("> ✅ 八道本地闸门全部通过。")
    out.append("")
    if vote_audit.get("mismatches"):
        out.append("## 5. 自报票表核对")
        out.append("")
        for m in vote_audit["mismatches"]:
            out.append("- {}：本地「{}」 vs 自报「{}」".format(
                m["seat_name"], m["local"], m["declared"]))
        out.append("")
    if state_info:
        out.append("## 断点续跑")
        out.append("")
        out.append("- 断点 key（含材料摘要 / 模型 / 温度 / 席位组合 / 口径版本）：")
        for k, v in state_info.items():
            out.append("  - `{}` = `{}`".format(k, v))
        out.append("")
        out.append("同一个 `--outdir` 重跑：key 没命中就跳过并打印「已完成」，**0 次调用**。"
                   "要强跑用 `--force`。")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#
# 信封必须落在**真 stdout**：所有 JSON 文本都经 `_json_write` 写，绕开任何临时的 stdout 重定向。
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

    只写 stdout（真 stdout）；完整 traceback 由 main() 的兜底层原样打到 stderr。
    `detail.where` 只取**最后一帧**的文件名:行号，整条栈不进 JSON。
    如果本次已经吐过结果，就**不再补信封**（守住"stdout 永远只有一个 JSON"）。
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
# 文件与产物
# ---------------------------------------------------------------------------

def read_text(path):
    p = Path(path)
    if not p.is_file():
        raise UsageError("找不到文件：{}".format(p))
    try:
        data = p.read_bytes()
    except OSError as exc:
        raise UsageError("读不动文件 {}：{}".format(p, exc))
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", "replace")


def write_text(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def write_json(path, obj):
    return write_text(path, json.dumps(obj, ensure_ascii=False, indent=1))


def load_json(path, what="文件"):
    p = Path(path)
    if not p.is_file():
        raise UsageError("找不到{}：{}".format(what, p))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("{} 不是合法 JSON（{}）：{}".format(what, exc, p))


def resolve_seats(spec):
    """把 `--seats a,b` 解析成席位定义列表；没给就用全部四席。"""
    if not spec:
        return list(SEATS)
    ids = [x.strip() for x in str(spec).split(",") if x.strip()]
    bad = [x for x in ids if x not in SEAT_BY_ID]
    if bad:
        raise UsageError("席位名不认识：{}。可用席位：{}".format(
            "、".join(bad), "、".join(SEAT_IDS)))
    if len(ids) < 2:
        raise UsageError("至少要两个席位才能对质（现在只给了 {} 个）".format(len(ids)))
    seen, out = set(), []
    for x in ids:
        if x not in seen:
            seen.add(x)
            out.append(SEAT_BY_ID[x])
    return out


def seats_spec(seats):
    return ",".join(s["id"] for s in seats)


def material_meta(text):
    return {"chars": char_count(text), "sentences": len(split_sentences(text)),
            "sha": text_sha(text)}


def isolation_evidence(seat_prompts, seats):
    """信息隔离证据：每席提示词里有没有出现**别的席位**的名字。"""
    recs = {}
    for s in seats:
        p = seat_prompts[s["id"]]
        found = []
        for other in seats:
            if other["id"] == s["id"]:
                continue
            if other["name"] in p:
                found.append(other["name"])
        recs[s["id"]] = {
            "prompt_chars": len(p),
            "prompt_sha": hashlib.sha256(p.encode("utf-8")).hexdigest(),
            "other_seat_names_found": found,
            "stance_block_ids": [s["id"]],
        }
    return {
        "seats": recs,
        "note": ("panel 是 N 次**独立调用**，每次只带本席位的立场块，"
                 "不带其它席位的意见，也不带席位花名册；"
                 "「提示词里出现的其它席位名」应为空（材料正文自己提到某个角色名除外）。"
                 "隔离只发生在 panel 阶段——clash 阶段**故意**把四份意见放到一起。"),
        "stage_inputs": {"panel": ["material"], "clash": ["material", "panel"],
                         "verdict": ["material", "panel", "clash"]},
    }


# ---------------------------------------------------------------------------
# 子命令：seats（零成本）
# ---------------------------------------------------------------------------

def run_seats(a):
    md = render_seats_md()
    body = {"command": "seats", "seats": SEATS,
            "seat_ids": SEAT_IDS,
            "why_adversarial": [
                "席位只有立场，没有最终决定权：裁决由 verdict 出，且必须保留少数派",
                "panel 阶段四次独立调用、信息隔离，四席互相看不到对方的意见",
                "本地不采信自报：立场重叠度过高即判「立场失效」（闸门五）",
            ],
            "markdown": md}
    if _json_out(body, a):
        return _after_out(a, md, "seats", obj=body)
    print(md)
    return _after_out(a, md, "seats", printed=True, obj=body)


# ---------------------------------------------------------------------------
# 子命令：brief（零成本）
# ---------------------------------------------------------------------------

def run_brief(a):
    text = read_text(a.file)
    brief = build_brief(text, a.file)
    if a.outdir:
        ensure_outside_pkg(a.outdir, "输出目录", "review-board-out")
        write_json(Path(a.outdir) / "brief.json", brief)
        write_text(Path(a.outdir) / "brief.md", render_brief_md(brief, text))
    md = render_brief_md(brief, text)
    body = {"command": "brief", "brief": brief, "markdown": md}
    if _json_out(body, a):
        return _after_out(a, md, "brief", obj=body)
    print(md)
    return _after_out(a, md, "brief", printed=True, obj=body)


def _after_out(a, md, name, printed=False, obj=None):
    """统一的 `--out` 落盘。

    **契约**：带 `--json` 时 `--out` 写的是**结果 JSON**（可以原样喂给下一个子命令，
    例如 `panel --json --out panel.json` 之后 `clash --panel panel.json`）；
    不带 `--json` 时写的是人读的 Markdown。两者都不是"随手打一份 log"。
    """
    if getattr(a, "out", None):
        ensure_outside_pkg(a.out, "输出文件", "{}-out".format(name))
        if _json_want(a) and obj is not None:
            write_json(a.out, _json_payload(obj, True))
        else:
            write_text(a.out, md)
        if not printed and not _json_want(a):
            print("已写出：{}".format(a.out))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：panel（四席独立评审）
# ---------------------------------------------------------------------------

def run_panel(a):
    check_cost_opts(a)
    text = read_text(a.file)
    seats = resolve_seats(getattr(a, "seats", None))
    meta = material_meta(text)
    target = AnchorTarget("material", "待评材料", text)

    if a.replay:
        raw = load_json(a.replay, "回放文件（panel 结果）")
        raw_seats = raw.get("seats") if isinstance(raw, dict) else None
        if not isinstance(raw_seats, list):
            raise UsageError("回放文件里没有 seats 数组：{}".format(a.replay))
        by_id = {x.get("id"): x for x in raw_seats if isinstance(x, dict)}
        seats_out = []
        for s in seats:
            src = by_id.get(s["id"])
            if src is None:
                raise UsageError("回放文件缺少席位 {}：{}".format(s["id"], a.replay))
            seats_out.append(normalize_seat(src.get("raw") or src, s, target))
        isolation = {
            "seats": {s["id"]: {"prompt_chars": None, "prompt_sha": None,
                                "other_seat_names_found": [], "stance_block_ids": [s["id"]]}
                      for s in seats},
            "note": "本次是 --replay：没有真实发过提示词，隔离证据无从取，"
                    "只做了本地归一化与锚点校验。",
            "stage_inputs": {"panel": ["material"]},
        }
        tracker = CostTracker()
        note = "本次是 --replay：一次调用都没发，只做了本地归一化与锚点校验。"
    else:
        prompts = {s["id"]: build_seat_prompt(s, text, meta) for s in seats}
        if a.dry_run:
            for s in seats:
                print("===== 席位 {}（{}）的完整提示词开始 =====".format(s["id"], s["name"]))
                print(prompts[s["id"]])
                print("===== 席位 {} 的完整提示词结束 =====\n".format(s["id"]))
            print("--dry-run：以上 {} 次调用**没有发出**，没有花任何点数。".format(len(seats)))
            return EXIT_OK
        tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
        seats_out = []
        for s in seats:
            sys.stderr.write("四席评审：{}…\n".format(s["name"]))
            content, _usage = guarded_chat(
                prompts[s["id"]], tracker, "panel:{}".format(s["id"]),
                system=SEAT_SYSTEM.format(name=s["name"], goal=s["goal"], bias=s["bias"]),
                model=a.model, temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
                json_mode=not a.no_json_mode)
            raw = parse_first_json(content)
            if isinstance(raw, dict) and "seat" in raw:
                raw["seat"] = s["id"]
            seats_out.append(normalize_seat(raw, s, target))
        isolation = isolation_evidence(prompts, seats)
        note = None

    recs = []
    for s in seats_out:
        recs.extend([True] * len(s.get("points") or []))
        recs.extend([False] * len(s.get("unanchored_points") or []))
    anchor = anchor_stat_for(recs)
    anchor["rules"] = {}
    for s in seats_out:
        for p in s.get("points") or []:
            r = p.get("anchor_rule") or "-"
            anchor["rules"][r] = anchor["rules"].get(r, 0) + 1
    stance = stance_check(seats_out)
    body = {
        "command": "panel",
        "material": meta,
        "seats": seats_out,
        "anchor": anchor,
        "stance": stance,
        "isolation": isolation,
        "usage": tracker.as_dict(),
        "note": note or "四席各一次独立调用，信息隔离（详见 isolation 字段）。",
    }
    md = render_panel_md(seats_out, isolation)
    if a.outdir:
        ensure_outside_pkg(a.outdir, "输出目录", "review-board-out")
        write_json(Path(a.outdir) / "panel.json", body)
        write_text(Path(a.outdir) / "panel.md", md)
    _add_isolation_stderr(isolation)
    sys.stderr.write(tracker.line() + "\n")
    if _json_out(body, a):
        return _after_out(a, md, "panel", obj=body)
    print(md)
    return _after_out(a, md, "panel", printed=True, obj=body)


def _add_isolation_stderr(isolation):
    bad = [(k, v) for k, v in (isolation.get("seats") or {}).items()
           if v.get("other_seat_names_found")]
    if bad:
        sys.stderr.write("提示：有席位的提示词里出现了其它席位名（可能来自材料正文）：{}\n".format(
            "、".join(k for k, _ in bad)))


# ---------------------------------------------------------------------------
# 子命令：clash（对质）
# ---------------------------------------------------------------------------

def _seats_from_panel(panel_obj, seats):
    """从 panel.json 里按席位 id 取回四席意见（缺失即用法错误）。"""
    raw_seats = panel_obj.get("seats") if isinstance(panel_obj, dict) else None
    if not isinstance(raw_seats, list):
        raise UsageError("panel 结果里没有 seats 数组")
    by_id = {x.get("id"): x for x in raw_seats if isinstance(x, dict)}
    out = []
    for s in seats:
        if s["id"] not in by_id:
            raise UsageError("panel 结果里缺少席位 {}（该文件是用别的 --seats 跑的吗？）".format(
                s["id"]))
        out.append(by_id[s["id"]])
    return out


def run_clash(a):
    check_cost_opts(a)
    text = read_text(a.file)
    seats = resolve_seats(getattr(a, "seats", None))
    panel_obj = load_json(a.panel, "panel 结果")
    seats_in = _seats_from_panel(panel_obj, seats)

    if a.replay:
        raw = load_json(a.replay, "回放文件（clash 结果）")
        tracker = CostTracker()
        prompt_sha = None
    else:
        prompt = build_clash_prompt(text, seats_in)
        prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if a.dry_run:
            print(prompt)
            print("--dry-run：这一次调用**没有发出**，没有花任何点数。")
            return EXIT_OK
        tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
        sys.stderr.write("对质：把 {} 份独立意见放到一张桌上…\n".format(len(seats_in)))
        content, _usage = guarded_chat(
            prompt, tracker, "clash", model=a.model, temperature=a.temperature,
            max_tokens=a.max_tokens, key=a.key, json_mode=not a.no_json_mode)
        raw = parse_first_json(content)

    clash = validate_clash(raw, seats_in, text)
    clash.update({
        "command": "clash",
        "material": material_meta(text),
        "panel_sha": json_sha(panel_obj),
        "usage": tracker.as_dict(),
        "prompt_sha": prompt_sha,
    })
    md = render_clash_md(clash)
    if a.outdir:
        ensure_outside_pkg(a.outdir, "输出目录", "review-board-out")
        write_json(Path(a.outdir) / "clash.json", clash)
        write_text(Path(a.outdir) / "clash.md", md)
    sys.stderr.write("对质结果：真实分歧 {} 个，伪分歧剔出 {} 个。\n".format(
        len(clash["real_divergences"]), len(clash["rejected_divergences"])))
    sys.stderr.write(tracker.line() + "\n")
    if _json_out(clash, a):
        return _after_out(a, md, "clash", obj=clash)
    print(md)
    return _after_out(a, md, "clash", printed=True, obj=clash)


# ---------------------------------------------------------------------------
# 子命令：verdict（裁决书）
# ---------------------------------------------------------------------------

def run_verdict(a):
    check_cost_opts(a)
    text = read_text(a.file)
    seats = resolve_seats(getattr(a, "seats", None))
    panel_obj = load_json(a.panel, "panel 结果")
    seats_in = _seats_from_panel(panel_obj, seats)
    clash_obj = load_json(a.clash, "clash 结果") if getattr(a, "clash", None) else {"real_divergences": []}

    if a.replay:
        raw = load_json(a.replay, "回放文件（verdict 结果）")
        tracker = CostTracker()
        prompt_sha = None
    else:
        prompt = build_verdict_prompt(text, seats_in, clash_obj)
        prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if a.dry_run:
            print(prompt)
            print("--dry-run：这一次调用**没有发出**，没有花任何点数。")
            return EXIT_OK
        tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
        sys.stderr.write("裁决：出裁决书（结论 + 条件清单 + 少数派意见）…\n")
        content, _usage = guarded_chat(
            prompt, tracker, "verdict", model=a.model, temperature=a.temperature,
            max_tokens=a.max_tokens, key=a.key, json_mode=not a.no_json_mode)
        raw = parse_first_json(content)

    verdict = validate_verdict(raw, seats_in, clash_obj)
    audit = vote_mismatch(seats_in, verdict)
    vg_ok, vg_problems, required, listed = verdict_gate(
        verdict.get("decision"), verdict.get("conditions"), verdict.get("minority"),
        seats_in, clash_obj.get("real_divergences") or [])
    verdict.update({
        "command": "verdict",
        "material": material_meta(text),
        "panel_sha": json_sha(panel_obj),
        "clash_sha": json_sha(clash_obj),
        "local_vote_table": local_vote_table(seats_in),
        "vote_audit": audit,
        "completeness": {"ok": vg_ok, "problems": vg_problems,
                         "required_minority": required, "listed_minority": listed},
        "usage": tracker.as_dict(),
        "prompt_sha": prompt_sha,
    })
    md = render_verdict_md(verdict, seats_in, audit)
    verdict["exit"] = EXIT_OK if vg_ok else EXIT_GATE
    if not vg_ok:
        for p in vg_problems:
            sys.stderr.write("裁决完整性闸门：" + p + "\n")
    if a.outdir:
        ensure_outside_pkg(a.outdir, "输出目录", "review-board-out")
        write_json(Path(a.outdir) / "verdict.json", verdict)
        write_text(Path(a.outdir) / "verdict.md", md)
    sys.stderr.write(tracker.line() + "\n")
    # 闸门命中时结果本身就是失败报告（ok=false + exit=3），不另补信封
    if _json_out(verdict, a, ok=vg_ok):
        _after_out(a, md, "verdict", obj=verdict)
    else:
        print(md)
        _after_out(a, md, "verdict", printed=True, obj=verdict)
    if not vg_ok:
        raise GateFail("裁决不完整：{}".format("；".join(vg_problems)))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：run（一条命令跑完整评审，带断点续跑）
# ---------------------------------------------------------------------------

def run_run(a):
    check_cost_opts(a)
    text = read_text(a.file)
    seats = resolve_seats(getattr(a, "seats", None))
    meta = material_meta(text)
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir, "输出目录", "review-board-out")
    outdir.mkdir(parents=True, exist_ok=True)
    if a.out:
        ensure_outside_pkg(a.out, "输出文件", "run-out.json")

    brief = build_brief(text, a.file)
    write_json(outdir / "brief.json", brief)
    write_text(outdir / "brief.md", render_brief_md(brief, text))

    tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
    state = load_state(outdir)
    prompt_chars = meta["chars"]
    sspec = seats_spec(seats)
    state_info = {}
    target = AnchorTarget("material", "待评材料", text)
    calls = []

    # ---- panel ----
    k_panel = state_key("panel", meta["sha"], meta["chars"], prompt_chars, a.model,
                        a.temperature, sspec, len(seats))
    state_info["panel"] = k_panel
    panel_path = outdir / "panel.json"
    panel_obj = None
    if panel_path.is_file() and state["entries"].get(k_panel) == "done" and not a.force:
        panel_obj = load_json(panel_path, "panel 结果")
        sys.stderr.write("panel：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        panel_obj = load_json(Path(a.replay) / "panel.json", "回放目录里的 panel 结果")
        # 回放要**重做一遍锚点校验**，不能直接信文件里存好的 points/unanchored_points：
        # 否则一份被手工改过的 panel.json 就能绕过锚点闸门（本包自测时真踩到了）。
        panel_obj = dict(panel_obj)
        panel_obj["seats"] = _renormalize_panel(panel_obj, seats, target)
        sys.stderr.write("panel：--replay 命中，跳过模型调用（锚点已本地重算）。\n")
        write_json(panel_path, panel_obj)
    else:
        prompts = {s["id"]: build_seat_prompt(s, text, meta) for s in seats}
        if a.dry_run:
            for s in seats:
                print("===== 席位 {}（{}）的提示词开始 =====".format(s["id"], s["name"]))
                print(prompts[s["id"]])
                print("===== 席位 {} 的提示词结束 =====\n".format(s["id"]))
            print("--dry-run：本次 run 的 {} 次席位调用**没有发出**。"
                  "对质与裁决的提示词依赖四席产出，无法在 dry-run 里预演。".format(len(seats)))
            return EXIT_OK
        seats_out = []
        mark = len(tracker.log)
        for s in seats:
            sys.stderr.write("四席评审：{}…\n".format(s["name"]))
            content, usage = guarded_chat(
                prompts[s["id"]], tracker, "panel:{}".format(s["id"]),
                system=SEAT_SYSTEM.format(name=s["name"], goal=s["goal"], bias=s["bias"]),
                model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
                key=a.key, json_mode=not a.no_json_mode)
            calls.append({"stage": "panel:{}".format(s["id"]), "usage": usage})
            seats_out.append(normalize_seat(parse_first_json(content), s, target))
        recs = []
        for s in seats_out:
            recs.extend([True] * len(s.get("points") or []))
            recs.extend([False] * len(s.get("unanchored_points") or []))
        anchor = anchor_stat_for(recs)
        anchor["rules"] = {}
        for s in seats_out:
            for p in s.get("points") or []:
                r = p.get("anchor_rule") or "-"
                anchor["rules"][r] = anchor["rules"].get(r, 0) + 1
        panel_obj = {
            "command": "panel", "material": meta, "seats": seats_out, "anchor": anchor,
            "stance": stance_check(seats_out),
            "isolation": isolation_evidence(prompts, seats),
            "usage": _stage_usage(tracker, mark),
            "note": "四席各一次独立调用，信息隔离（详见 isolation 字段）。",
        }
        write_json(panel_path, panel_obj)
        write_text(outdir / "panel.md", render_panel_md(seats_out, panel_obj["isolation"]))
        state["entries"][k_panel] = "done"
        save_state(outdir, state)

    seats_in = _seats_from_panel(panel_obj, seats)
    _add_isolation_stderr(panel_obj.get("isolation") or {})

    # ---- clash ----
    k_clash = state_key("clash", meta["sha"], meta["chars"], prompt_chars, a.model,
                        a.temperature, sspec, len(seats),
                        panel_sha=json_sha(panel_obj))
    state_info["clash"] = k_clash
    clash_path = outdir / "clash.json"
    clash_obj = None
    if clash_path.is_file() and state["entries"].get(k_clash) == "done" and not a.force:
        clash_obj = load_json(clash_path, "clash 结果")
        sys.stderr.write("clash：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        clash_obj = load_json(Path(a.replay) / "clash.json", "回放目录里的 clash 结果")
        # 与 panel 同理：回放要**重跑本地校验**（真分歧判定、引文锚点、两侧矛盾），
        # 不能直接信文件里存好的 real_divergences —— 否则改过判定口径也看不出差别。
        raw_c = clash_obj.get("raw") if isinstance(clash_obj, dict) else None
        if isinstance(raw_c, dict):
            keep = {k: clash_obj.get(k) for k in ("command", "material", "panel_sha",
                                                  "usage", "prompt_sha") if k in clash_obj}
            clash_obj = validate_clash(raw_c, seats_in, text)
            clash_obj.update({k: v for k, v in keep.items() if v is not None})
        sys.stderr.write("clash：--replay 命中，跳过模型调用（本地校验已重算）。\n")
        write_json(clash_path, clash_obj)
        write_text(outdir / "clash.md", render_clash_md(clash_obj))
    else:
        prompt = build_clash_prompt(text, seats_in)
        mark = len(tracker.log)
        sys.stderr.write("对质：把 {} 份独立意见放到一张桌上…\n".format(len(seats_in)))
        content, usage = guarded_chat(
            prompt, tracker, "clash", model=a.model, temperature=a.temperature,
            max_tokens=a.max_tokens, key=a.key, json_mode=not a.no_json_mode)
        calls.append({"stage": "clash", "usage": usage})
        clash_obj = validate_clash(parse_first_json(content), seats_in, text)
        clash_obj.update({"command": "clash", "material": meta,
                          "panel_sha": json_sha(panel_obj),
                          "usage": _stage_usage(tracker, mark),
                          "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()})
        write_json(clash_path, clash_obj)
        write_text(outdir / "clash.md", render_clash_md(clash_obj))
        state["entries"][k_clash] = "done"
        save_state(outdir, state)
        sys.stderr.write("对质结果：真实分歧 {} 个，伪分歧剔出 {} 个。\n".format(
            len(clash_obj.get("real_divergences") or []),
            len(clash_obj.get("rejected_divergences") or [])))

    # ---- verdict ----
    k_verdict = state_key("verdict", meta["sha"], meta["chars"], prompt_chars, a.model,
                          a.temperature, sspec, len(seats),
                          panel_sha=json_sha(panel_obj), clash_sha=json_sha(clash_obj))
    state_info["verdict"] = k_verdict
    verdict_path = outdir / "verdict.json"
    verdict_obj = None
    if verdict_path.is_file() and state["entries"].get(k_verdict) == "done" and not a.force:
        verdict_obj = load_json(verdict_path, "verdict 结果")
        sys.stderr.write("verdict：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        verdict_obj = load_json(Path(a.replay) / "verdict.json", "回放目录里的 verdict 结果")
        # 同样重跑本地校验：条件与少数派的席位归一会重做，显示名 → id 的映射也会重做
        raw_v = verdict_obj.get("raw") if isinstance(verdict_obj, dict) else None
        if isinstance(raw_v, dict):
            keep = {k: verdict_obj.get(k) for k in
                    ("command", "material", "panel_sha", "clash_sha", "usage",
                     "prompt_sha") if k in verdict_obj}
            verdict_obj = validate_verdict(raw_v, seats_in, clash_obj)
            verdict_obj["local_vote_table"] = local_vote_table(seats_in)
            verdict_obj["vote_audit"] = vote_mismatch(seats_in, verdict_obj)
            verdict_obj.update({k: v for k, v in keep.items() if v is not None})
        sys.stderr.write("verdict：--replay 命中，跳过模型调用（本地校验已重算）。\n")
        write_json(verdict_path, verdict_obj)
        write_text(outdir / "verdict.md", render_verdict_md(
            verdict_obj, seats_in, verdict_obj.get("vote_audit") or
            vote_mismatch(seats_in, verdict_obj)))
    else:
        prompt = build_verdict_prompt(text, seats_in, clash_obj)
        mark = len(tracker.log)
        sys.stderr.write("裁决：出裁决书（结论 + 条件清单 + 少数派意见）…\n")
        content, usage = guarded_chat(
            prompt, tracker, "verdict", model=a.model, temperature=a.temperature,
            max_tokens=a.max_tokens, key=a.key, json_mode=not a.no_json_mode)
        calls.append({"stage": "verdict", "usage": usage})
        verdict_obj = validate_verdict(parse_first_json(content), seats_in, clash_obj)
        verdict_obj.update({
            "command": "verdict", "material": meta,
            "panel_sha": json_sha(panel_obj), "clash_sha": json_sha(clash_obj),
            "local_vote_table": local_vote_table(seats_in),
            "vote_audit": vote_mismatch(seats_in, verdict_obj),
            "usage": _stage_usage(tracker, mark),
            "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        })
        write_json(verdict_path, verdict_obj)
        write_text(outdir / "verdict.md", render_verdict_md(
            verdict_obj, seats_in, verdict_obj["vote_audit"]))
        state["entries"][k_verdict] = "done"
        save_state(outdir, state)

    # ---- 闸门 + 报告 ----
    gates = evaluate_gates(text, seats_in, clash_obj, verdict_obj, meta,
                           unanimous_ok=bool(getattr(a, "unanimous_ok", False)))
    audit = vote_mismatch(seats_in, verdict_obj)
    if tracker.calls:
        usage_dict = tracker.as_dict()
    else:
        # 断点续跑 / 回放路径下 tracker 里没有真实 usage：把各阶段自己记的 usage 搬运汇总
        usage_dict = _merge_stage_usage([panel_obj, clash_obj, verdict_obj], tracker)
    report = render_report_md(brief, seats_in, clash_obj, verdict_obj, gates, audit,
                              usage_dict, a.model, a.file, state_info)
    write_text(outdir / "REPORT.md", report)
    for p in gate_summary_lines(gates):
        sys.stderr.write("闸门命中：" + p + "\n")
    bad = [k for k in HARD_GATE_KEYS if not (gates.get(k) or {}).get("ok", True)]
    if bad:
        sys.stderr.write("本地闸门命中 {} 项：{}（详见 {}/REPORT.md）\n".format(
            len(bad), "、".join(bad), outdir))
    else:
        sys.stderr.write("本地闸门：八项全部通过。\n")
    sys.stderr.write(tracker.line() + "\n" if tracker.calls else
                     "本次是断点续跑 / 回放：{} 次调用。\n".format(tracker.calls))

    body = {
        "command": "run",
        "material": meta,
        "brief": {"sha": brief["sha"], "chars": brief["chars"],
                  "headings": len(brief["headings"]), "numbers": len(brief["numbers"])},
        "seats": seats_in,
        "clash": clash_obj,
        "verdict": verdict_obj,
        "gates": gates,
        "gate_failed": gate_failed(gates),
        "exit": (EXIT_GATE if bad else EXIT_OK),
        "vote_audit": audit,
        "usage": usage_dict,
        "state_key": state_info,
        "outdir": str(outdir),
        "files": ["brief.json", "brief.md", "panel.json", "panel.md", "clash.json",
                  "clash.md", "verdict.json", "verdict.md", "REPORT.md", "state.json"],
        "report_md": report,
    }
    if a.out:
        if _json_want(a):
            write_json(a.out, _json_payload(body, not bad))
        else:
            write_text(a.out, report)
    # ⚠️ 契约细节：闸门命中时，**结果本身**就是那份失败报告（`ok: false` + `exit` + `gates`），
    # 不再另补一个错误信封 —— 守住"stdout 永远只有一个 JSON"这条不变量。
    # 只有"连结果都没产出"的失败（参数错、调用失败、预算超限、未捕获异常）才给错误信封。
    if _json_out(body, a, ok=not bad):
        pass
    else:
        print(report)
        print("\n产出目录：{}".format(outdir))
    if bad:
        raise GateFail("本地闸门命中 {} 项：{}".format(
            len(bad), "、".join(bad)))
    return EXIT_OK


def _stage_usage(tracker, start):
    """把 tracker.log[start:] 这一段调用整理成一个阶段 usage 记录。

    为什么要按阶段切：`run` 一共三个阶段，断点续跑时可能只有一部分真的调用了模型。
    阶段各自的 usage 记在各自产物里，汇总时相加不会重复计数。
    token 全部来自网关返回的真实 usage，没有任何估算值混在里面。
    """
    log = tracker.log[start:]
    p = sum(x.get("prompt_tokens") or 0 for x in log)
    c = sum(x.get("completion_tokens") or 0 for x in log)
    return {"calls": len(log), "prompt_tokens": p, "completion_tokens": c,
            "total_tokens": p + c, "usage_log": log}


def _merge_stage_usage(objs, tracker):
    """断点/回放路径下把各阶段 json 里记的 usage 汇总（token 是真实 usage 的搬运）。"""
    out = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
           "calls_without_usage": 0, "replayed_or_resumed": True,
           "budget_points": tracker.budget, "has_price": tracker.has_price,
           "points": None, "yuan": None, "usage_log": [],
           "note": ("本次有阶段来自断点或 --replay：token 数是从各阶段产物里读回来的"
                    "真实 usage，不是重新调用产生的。")}
    for o in objs:
        u = (o or {}).get("usage") or {}
        if u.get("replayed"):
            continue
        log = u.get("usage_log")
        if isinstance(log, list) and log:
            for rec in log:
                out["usage_log"].append(rec)
                out["calls"] += 1
                out["prompt_tokens"] += rec.get("prompt_tokens") or 0
                out["completion_tokens"] += rec.get("completion_tokens") or 0
            continue
        out["calls"] += u.get("calls") or 0
        out["prompt_tokens"] += u.get("prompt_tokens") or 0
        out["completion_tokens"] += u.get("completion_tokens") or 0
        for rec in (u.get("usage_log") or []):
            out["usage_log"].append(rec)
    out["total_tokens"] = out["prompt_tokens"] + out["completion_tokens"]
    return out


# ---------------------------------------------------------------------------
# 子命令：cost / models
# ---------------------------------------------------------------------------

def run_cost(a):
    check_cost_opts(a)
    text = a.text if a.text else (read_text(a.file) if a.file else "")
    if not text:
        raise UsageError("要报价请给 --file 或 --text")
    seats = resolve_seats(getattr(a, "seats", None))
    calls = estimate_calls(text, len(seats))
    t_in = sum(c["tokens_in"] for c in calls)
    t_out = sum(c["tokens_out"] for c in calls)
    rec = compute_cost(t_in, t_out, a.price_in, a.price_out)
    body = {
        "command": "cost",
        "chars": char_count(text),
        "seats": [s["id"] for s in seats],
        "calls": calls,
        "total_calls": sum(c["calls"] for c in calls),
        "tokens_in": t_in,
        "tokens_out": t_out,
        "tokens_total": t_in + t_out,
        "cost": rec,
        "calibration": {"chars_per_token_in": CHARS_PER_TOKEN_IN,
                        "tokens_per_char_out": TOKENS_PER_CHAR_OUT,
                        "note": "字符→token 的比例是全族真机实测值，是估算不是账单。"},
        "budget": a.budget,
    }
    md = ["# 这次评审大概花多少", "",
          "- 材料：{} 字符".format(char_count(text)),
          "- 席位：{} 个（{}）".format(len(seats), "、".join(SEAT_NAME[s["id"]] for s in seats)),
          "- 调用：{} 次".format(sum(c["calls"] for c in calls)),
          "",
          "| 阶段 | 次数 | 输入 token | 输出 token | 说明 |",
          "|---|---|---|---|---|"]
    for c in calls:
        md.append("| {} | {} | {} | {} | {} |".format(
            c["stage"], c["calls"], c["tokens_in"], c["tokens_out"], c["note"]))
    md.append("| **合计** | **{}** | **{}** | **{}** |  |".format(
        sum(c["calls"] for c in calls), t_in, t_out))
    md.append("")
    md.append("- 金额：{}".format(fmt_cost(rec)))
    md.append("- 标定：输入 1 token ≈ {} 字符；输出 1 字符 ≈ {} token（全族实测值，估算非账单）"
              .format(CHARS_PER_TOKEN_IN, TOKENS_PER_CHAR_OUT))
    md = "\n".join(md)
    if _json_out(body, a):
        return _after_out(a, md, "cost", obj=body)
    print(md)
    return _after_out(a, md, "cost", printed=True, obj=body)


def run_models(a):
    key = a7w.load_key(a.key)
    payload = a7w._request("GET", MODELS_URL, key)
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
        print("  {:<28} {:<8} call_type={}  {:<28} {}".format(
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            m.get("call_type"), str(m.get("vendor_name") or "-"),
            str(m.get("model_name") or "")[:24]))
    print("")
    print("提示：模型名会变，以本命令现查为准，别写死在脚本里。")
    print("      `{}` 实测可用（路由到 deepseek-flash），但它**不在**上面这份列表里，"
          .format(DEFAULT_MODEL))
    print("      所以「列表里没有」不等于「不能用」。")
    print("用法：run.py panel --file 方案.md --model <model_code>")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def check_cost_opts(a):
    """`--budget` 必须配单价 —— 在**任何调用发生之前**检查。

    事故复盘（本包自测时踩到的真实坑，不是理论问题）：这道校验原先只写在 `cost` 里，
    于是 `panel --file x --budget 50`（没给单价）一路跑完 4 次真实调用才返回 ——
    用户以为设了预算上限，实际一分钱都没被拦住。预算这道闸门**在别的子命令上漏了**，
    而漏的方式是"看起来生效了"。所以它必须是所有会花钱的子命令的第一步。
    """
    if getattr(a, "budget", None) is None:
        return
    if getattr(a, "price_in", None) is None or getattr(a, "price_out", None) is None:
        raise UsageError(
            "用了 --budget 就必须给 --price-in 与 --price-out：文本模型网关不公布单价，"
            "没有单价就没法把 token 折成点数、预算无从判定。"
            "（本次**不会发起任何调用**，不花一分钱。）")
    if float(a.budget) <= 0:
        raise UsageError("--budget 必须大于 0")


def _renormalize_panel(panel_obj, seats, target):
    """回放时**重新做一遍本地归一化与锚点校验**，不直接信文件里存好的结论。

    为什么要重做：`--replay` 的目的是"用存下来的四席产出重跑闸门"。
    如果直接信任文件里的 `points` / `unanchored_points`，那么一份被手工改过的
    panel.json 就能绕过锚点闸门（本包自测时正是这样让闸门四看起来通过了）。
    `raw` 字段在真实产物里是留着的，所以重做是可能的。
    """
    raw_seats = panel_obj.get("seats") if isinstance(panel_obj, dict) else None
    if not isinstance(raw_seats, list):
        raise UsageError("panel 结果里没有 seats 数组")
    by_id = {x.get("id"): x for x in raw_seats if isinstance(x, dict)}
    out = []
    for s in seats:
        src = by_id.get(s["id"])
        if src is None:
            raise UsageError("panel 结果里缺少席位 {}（该文件是用别的 --seats 跑的吗？）".format(
                s["id"]))
        out.append(normalize_seat(src.get("raw") or src, s, target))
    return out


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与全族同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py panel --file x --json` 会报 `unrecognized arguments` 并退出 2。
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
                   help="最大输出 token，默认 8192（一次评审多次调用，别调太小）")
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
    p.add_argument("--file", required=True, help="待评方案/稿件（.md / .txt，UTF-8）")
    p.add_argument("--seats", help="只跑指定的席位（逗号分隔，默认全部四席）：{}".format(
        "、".join(SEAT_IDS)))
    p.add_argument("--outdir", help="把这一阶段的产物落这个目录（**必须在包外**）")
    p.add_argument("--replay", help="回放一份已保存的阶段产物：只跑本地校验与渲染，"
                                    "**零调用**（闸门自测用）")


def _parser(**kw):
    """统一构造 ArgumentParser，**关掉长选项前缀缩写**（`allow_abbrev=False`）。

    事故复盘（同族自测时踩到的真实坑，不是理论问题）：
    `run` 上同时有 `--outdir`，用户写 `--out report.json` 想输出结果文件，
    argparse 默认允许**前缀缩写**，于是 `--out` 被当成 `--outdir` 的缩写匹配上了 ——
    结果：产出目录变成了一个叫 `report.json` 的目录，而且**不报任何错**。
    这类"参数被静默吃成另一个参数"的错误最难查，因为命令行看起来是对的。
    """
    kw.setdefault("allow_abbrev", False)
    return argparse.ArgumentParser(**kw)


def _main(argv_eff):
    ap = _parser(
        prog="run.py",
        description="三剪客 · 评审委员会（L3 对抗式多智能体评审；走 api.a7w.cn 的 OpenAI 兼容端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    # 每个子命令的 parser 也必须关掉缩写：argparse 的缩写开关是**每个 parser 各自**的属性，
    # 只在父级设一遍不够（子 parser 是另造的实例，默认仍然是允许缩写）。
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("seats", help="列出四个席位的立场与目标函数（零成本）")
    _add_json(p)
    p.add_argument("--out", help="把席位表写到这个文件")
    p.set_defaults(func=run_seats)

    p = sub.add_parser("brief", help="把待评方案整理成评审材料（纯本地零成本）")
    p.add_argument("--file", required=True, help="待评方案/稿件（.md / .txt，UTF-8）")
    _add_json(p)
    p.add_argument("--out", help="把材料写到这个文件")
    p.add_argument("--outdir", help="把 brief.json / brief.md 落这个目录（必须在包外）")
    p.set_defaults(func=run_brief)

    p = sub.add_parser("panel", help="四席独立评审（信息隔离，每席一次调用）")
    _add_source_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_panel)

    p = sub.add_parser("clash", help="对质：找真实分歧并逐点辩（一次调用）")
    p.add_argument("--file", required=True, help="待评方案/稿件")
    p.add_argument("--panel", required=True, help="panel 产出的 panel.json")
    p.add_argument("--seats", help="只跑指定的席位（默认全部四席）")
    p.add_argument("--outdir", help="把这一阶段的产物落这个目录（必须在包外）")
    p.add_argument("--replay", help="回放一份已保存的 clash 产物：零调用")
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_clash)

    p = sub.add_parser("verdict", help="裁决书：结论 + 条件清单 + 少数派意见（一次调用）")
    p.add_argument("--file", required=True, help="待评方案/稿件")
    p.add_argument("--panel", required=True, help="panel 产出的 panel.json")
    p.add_argument("--clash", help="clash 产出的 clash.json（没有就按无分歧处理）")
    p.add_argument("--seats", help="只跑指定的席位（默认全部四席）")
    p.add_argument("--outdir", help="把这一阶段的产物落这个目录（必须在包外）")
    p.add_argument("--replay", help="回放一份已保存的 verdict 产物：零调用")
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_verdict)

    p = sub.add_parser("run", help="一条命令跑完整评审（brief→panel→clash→verdict），断点续跑")
    p.add_argument("--file", required=True, help="待评方案/稿件（.md / .txt，UTF-8）")
    p.add_argument("--seats", help="只跑指定的席位（逗号分隔，默认全部四席）：{}".format(
        "、".join(SEAT_IDS)))
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".") / "review-board-out"),
                   help="目录产物落这里（**必须在包外**）：brief、panel、clash、verdict、"
                        "REPORT.md、state.json")
    p.add_argument("--replay", help="从一个已有产物目录回放：读取该目录里的 "
                                    "panel.json / clash.json / verdict.json，"
                                    "**零调用**只跑本地闸门与报告（闸门自测用）")
    p.add_argument("--force", action="store_true",
                   help="忽略断点文件，从头重跑（key 没命中就会重新花钱）")
    p.add_argument("--unanimous-ok", action="store_true", dest="unanimous_ok",
                   help="允许「四席结论全同且零分歧」不判立场失效"
                        "（只在确认材料本身无争议时用；默认是硬闸门）")
    p.set_defaults(func=run_run)

    p = sub.add_parser("cost", help="报价：这次评审大概花多少 token（金额要你填单价）")
    p.add_argument("--file", help="按这份材料估")
    p.add_argument("--text", help="或直接给文本")
    p.add_argument("--seats", help="按几个席位估（默认四席）")
    _add_cost_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把报价写到这个文件")
    p.set_defaults(func=run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的文本模型（免费）")
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
    for k, v in (("json", False), ("out", None), ("dry_run", False), ("no_json_mode", False),
                 ("budget", None), ("price_in", None), ("price_out", None), ("replay", None),
                 ("force", False), ("unanimous_ok", False), ("seats", None), ("outdir", None),
                 ("clash", None), ("type", "text")):
        if not hasattr(a, k):
            setattr(a, k, v)
    kind, msg, detail = None, None, None
    try:
        rc = a.func(a)
    except BoardError as exc:
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
