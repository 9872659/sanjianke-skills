#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 方案竞标小组 —— 真正干活的脚本（零第三方依赖）。

**产品线 L3（多智能体协作型）· 竞争式**：本包**不是**"几个角色互相审一份稿"，
也**不是**"角色按顺序接力做同一件事"。它是一场**有限名额的竞标**：

    三个提案组各自**独立出方案**（互相看不到对方，也看不到评委的偏好）
        ↓
    评委团按**提案前就已公示**的评分维度与权重打分（每条理由必须引用方案原文）
        ↓
    交叉质询：每组必须回答"为什么你的比另外两组好"
              —— 但它**看不到对方的原文**，只能看到对方的**主张摘要**
        ↓
    裁决：出获胜方案 + 落选方案的**可复用部分**（合并建议）+ 打分明细

十个子命令：

    roles     列出三个提案组 / 三名评委 / 质询主持 / 裁决人（纯本地，零成本）
    rubric    公示评分维度与权重（纯本地，零成本，**必须在提案之前跑**）
    propose   某个提案组独立出方案（信息隔离：看不到另外两组，也看不到评委偏好）
    score     评委团按公示维度打分（每名评委一次独立调用；每条理由必须引用方案原文）
    challenge 交叉质询：每组**只对着自己的方案与对方的摘要**回答"我为什么更好"
    award     裁决：获胜方案 + 落选原因 + 合并建议 + 打分明细
    run       一条命令跑完整场竞标（rubric→propose→score→challenge→award），断点续跑
    log       把产出目录里的结果再读一遍（纯本地，零成本）
    cost      报价：这场竞标大概花多少 token（金额要你自己填单价）
    models    列出 api.a7w.cn 当前在架的文本模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py roles
    python3 run.py rubric  --file 任务书.md --outdir D:/bid --json
    python3 run.py propose --file 任务书.md --team a --outdir D:/bid --json
    python3 run.py score   --file 任务书.md --outdir D:/bid --json
    python3 run.py challenge --file 任务书.md --outdir D:/bid --json
    python3 run.py award   --file 任务书.md --outdir D:/bid --json
    python3 run.py run     --file 任务书.md --outdir D:/bid --budget 50 \
                           --price-in 1000 --price-out 2000 --json
    python3 run.py cost    --file 任务书.md --teams 3
    python3 run.py propose --file 任务书.md --team a --dry-run   # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py propose --file 任务书.md --team a --key sk-xxxx
    export A7W_API_KEY=sk-xxxx     # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍（这一节是本包与同族其它包的**分界线**）
    · 与 `sanjianke-review-board`（对抗评审式 L3）的分界：那边审的是**一份已有材料**，
      四个席位对同一份东西各说各话，**没有竞争、没有胜负**，产出是"该不该过"的裁决书；
      本包是**三份各自独立写的方案抢同一个名额**，产出是"谁赢、别人差在哪、
      落选方案的哪些部分还能用"。一句话：那边**裁一份稿**，本包**选一份稿**。
    · 与 `sanjianke-content-team`（流水线式 L3）的分界：那边角色按顺序接力做**同一件事**，
      后一个审前一个，产出是**一个定稿**；本包三组**各做一份**，互不相干，
      谁也不知道别人写了什么 —— 这是**竞争**，不是**协作**。
    · **"竞争"这件事必须能被实测到**，否则就是"三个角色各写一段然后合并"，
      那就退化成了协作式。所以本包有一道专门的闸门（闸门五 · 提案独立性）：
      三组方案两两之间的内容重叠度超阈值 → 判「假竞争」，标红并让整条命令 `exit=3`。
      不采信模型的自我声明，本地算二元组覆盖度。
    · **评分维度必须在提案之前公示**（`rubric` 子命令先跑，写进 `rubric.json`）。
      顺序倒了 → `score` 直接 `exit=2`。理由很实在：维度如果在看到提案之后才定，
      评委就是在**为已经写出来的东西找尺子**，那是"打分"，不是"竞标"。
    · **打分理由必须引用方案原文**，本地校验（见 verify_anchor）：
      引文在方案里锚不上 → 剔出，并计入未锚定率；超阈值判「定位失败」。
      编造引文的评委会被当场抓住，不是靠提示词求它诚实。
    · **信息隔离是机制，不是修辞**：propose 阶段是三次独立调用，每次的提示词里
      只有本组自己的立场与任务书，**没有**另外两组的任何文字，**也没有评分维度**；
      challenge 阶段每组只看得到**对方的主张摘要**，看不到对方的原文。
      隔离证据写进产物（`isolation` 与 `cross_visibility`）。
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
# 不许往包里写 .pyc。同族的包跑一次就会在 scripts/__pycache__/ 留下几个 .pyc，
# 而 Skill 包的上传白名单里没有 .pyc（在 CLI 排除清单里，但包目录里留垃圾没必要）。
# 在 import a7w **之前**关掉字节码写入，根治这件事。
sys.dont_write_bytecode = True
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

# 退出码。数值与全族对齐：
EXIT_OK = 0            # 竞标跑完了，且没有任何硬闸门命中
EXIT_USAGE = 2         # 参数/配置错（文件不存在、组名错、--outdir 在包内、--budget 没配单价、顺序倒置）
EXIT_GATE = 3          # 硬闸门命中（合规/占位符/照抄示例/打分锚点/假竞争/裁决不完整）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。
# 事故复盘（同族踩过）：改了评分维度或闸门口径却不改 key，续跑会把上一版口径的旧产物
# 当成"已完成"直接复用，产出对不上文档。加版本号是最省事的根治办法。
RUBRIC_VERSION = "bid-rubric-1.0.0"
PROMPT_VERSION = "bid-prompt-1.0.0"
CREW_VERSION = "bid-crew-1.0.0"


# ---------------------------------------------------------------------------
# 三个提案组：每组一个**独立的取胜路线**与一组天然倾向
#
# 设计要点（这是本包能成立的前提）：三组的取胜路线必须**真的不一样**，
# 不能是同一份方案的三种措辞。所以每组都带一句 `must_have`（本组最不能让步的一点）
# 与一句 `give_up`（为了赢，本组肯牺牲什么）—— 这两个字段结构性地把三份方案拉开距离：
#   A 组省钱省时间，必然在差异化上吃亏；B 组砸差异化，必然在成本上吃亏；
#   C 组求稳可控，必然在"出彩"上吃亏。三组在同一张评分表上各有长短，
#   这样"竞争"才真实存在，而不是三份都四平八稳。
#
# 三组**互相看不到对方**（信息隔离），也**看不到评分维度**（否则它们会照着尺子
# 优化成三份一样的东西 —— 那正好是本包闸门五要抓的「假竞争」）。
# ---------------------------------------------------------------------------

TEAMS = [
    {
        "id": "team_a",
        "name": "A 组",
        "label": "A 组 · 成本快打",
        "route": "用最少的钱和最短的时间把这件事做成，先跑起来再优化",
        "bias": "抠单价、砍链路、砍到只剩主干；宁可丑、宁可少，也要便宜且三天内能上",
        "question": "如果预算和时间都只有别人一半：这件事最少要花多少钱、几天能把主干跑通？"
                    "哪些环节是纯消耗、可以整个删掉？",
        "focus": [
            "端到端一共要花多少钱，钱花在哪几个环节，哪一环最贵",
            "最少要几个人、几天能跑通第一版（不是最好的一版）",
            "链路里哪一步可以整个删掉而不影响主干达成",
            "交付物长什么样：具体的、能照着做的步骤，不是方向",
        ],
        "must_have": "总成本与工期必须给出可核算的数字（单价 × 用量、人天 × 天数），"
                     "含糊的「视情况而定」不算方案",
        "give_up": "为了把钱和时间压下来，可以牺牲包装、视觉、长尾优化与品牌叙事",
    },
    {
        "id": "team_b",
        "name": "B 组",
        "label": "B 组 · 差异化造势",
        "route": "做一个别人做不出来的东西，靠可指认的差异取胜，不怕贵",
        "bias": "追独特卖点、追记忆点、追传播；宁可贵，也要让人一眼看出和别人不一样",
        "question": "这件事做出来之后，哪一点是**别人说不出、也抄不走**的？"
                    "凭什么让人记住它、讨论它？",
        "focus": [
            "一句话能不能说清「它和别人有什么不同」",
            "这个差异能不能被感知、被验证、被复现，凭什么说它抄不走",
            "有没有记忆点与传播点：用户会主动替它说什么",
            "为了这个差异，愿意多花多少、多等几天（要给出数字）",
        ],
        "must_have": "必须给出可指认的差异化声称，并说明凭什么别人做不到；"
                     "「体验更好」「更用心」这类说法不算差异化",
        "give_up": "为了差异化，可以接受更高成本、更长周期与更难看的毛利",
    },
    {
        "id": "team_c",
        "name": "C 组",
        "label": "C 组 · 稳控兜底",
        "route": "把风险和不确定性压到最低，任何环节都有备份与验收口径，先保证不翻车",
        "bias": "追可控、追可回滚、追可验收；宁可平庸，也不留没兜住的坑",
        "question": "这件事最可能在哪一步翻车？每一步的失败模式是什么、怎么兜、"
                    "验收口径怎么定、多少分算过？",
        "focus": [
            "每个环节的失败模式、触发条件与兜底动作（含回滚）",
            "验收口径：谁在什么时点、看哪几个指标、多少算过、多少算停",
            "外部依赖（人 / 平台 / 供应商 / 资质）断了怎么办，有没有备份路径",
            "合规与资质风险点，哪些动作会踩线、踩线之后怎么收场",
        ],
        "must_have": "必须给出可验收的口径（指标 + 阈值 + 判定时点）与每一步的兜底动作；"
                     "只写「做好监督」「注意风险」不算兜底",
        "give_up": "为了可控，可以接受方案更平庸、更慢、更贵，也不追热点",
    },
]

TEAM_IDS = [t["id"] for t in TEAMS]
TEAM_BY_ID = {t["id"]: t for t in TEAMS}
TEAM_NAME = {t["id"]: t["name"] for t in TEAMS}

TEAM_ALIASES = {
    "a": "team_a", "b": "team_b", "c": "team_c",
    "甲": "team_a", "乙": "team_b", "丙": "team_c",
    "1": "team_a", "2": "team_b", "3": "team_c",
}


def as_team_id(value):
    """把模型给的组标识归一到组 id。

    真机实测踩到的（同族同类问题）：模型在 `winner` / `losers[].team` 里填的是
    **显示名**（「A 组」）而不是 id（`team_a`），于是"获胜组不存在"这条闸门误报，
    把一份合格的裁决判成不完整。字面看命令行是对的，错在最难查的地方。
    所以这里多种写法都认：id 原样、显示名映射、单字母别名（可能是全角）、
    前缀匹配；其它一律 None（那才是真的不认识）。
    """
    if not isinstance(value, str):
        return None
    v = value.strip().replace("（", "(").replace("）", ")")
    if v in TEAM_BY_ID:
        return v
    low = v.lower().replace("  ", " ").strip()
    for sid, name in TEAM_NAME.items():
        if low in (name.lower(), name.replace(" ", "").lower(),
                   "{}（{}）".format(name, sid).lower(), "{} {}".format(name, sid).lower()):
            return sid
    compact = re.sub(r"[\s\-_·:：]", "", low)
    for key, sid in TEAM_ALIASES.items():
        if compact in (key, key + "组", key + "team", "team" + key):
            return sid
    for sid in TEAM_IDS:
        if compact.startswith(sid) or compact.startswith(sid.replace("team_", "")):
            return sid
    m = re.match(r"^[^\u4e00-\u9fffA-Za-z0-9]*([abcABC甲乙丙123])", compact)
    if m:
        return TEAM_ALIASES.get(m.group(1).lower())
    return None


# ---------------------------------------------------------------------------
# 评委团（3 席，不同侧重）+ 质询主持 + 裁决人
#
# **评委能一票否决**：合规官命中硬伤 → 该方案直接出局，不参与分数排序
# （`fellows[].veto`）。这一条保证"打分"不只是打分：有些方案不是"分低"，
# 而是**不能上**。裁决阶段本地会核对：被否决的组不许当获胜组。
#
# 评委只看到**公示的评分维度 + 三份方案**，看不到组名、看不到各组自己的立场、
# 也看不到别的评委打了多少分（三名评委各是一次独立调用）。
# ---------------------------------------------------------------------------

JUDGES = [
    {
        "id": "cost_judge",
        "name": "成本与落地评委",
        "focus": "钱和人天",
        "question": "这份方案的钱和人天算不算得清、值不值：单价 × 用量对得上吗？"
                    "同等结果下能不能更省？说不清成本的部分按最高风险记。",
        "style": "对「说不清」最不宽容；数字对不上账的直接扣到底",
        "veto_power": False,
    },
    {
        "id": "diff_judge",
        "name": "差异与传播评委",
        "focus": "可指认的差异",
        "question": "这份方案里有没有一句是别人说不出、也抄不走的？"
                    "所谓差异能不能被感知、被验证、被复现？同质化的一律给低分。",
        "style": "对「通用能力当独家卖点」最不宽容；没有可验证差异的直接扣到底",
        "veto_power": False,
    },
    {
        "id": "risk_judge",
        "name": "风险与合规评委",
        "focus": "能不能上、兜不兜得住",
        "question": "这份方案发出去会不会出事、翻车了兜不兜得住："
                    "有没有违禁话术与绝对化承诺？有没有验收口径与回滚路径？",
        "style": "别的维度可以给高分，但**合规硬伤一票否决**——有硬伤的方案直接出局",
        "veto_power": True,
    },
]

JUDGE_IDS = [j["id"] for j in JUDGES]
JUDGE_BY_ID = {j["id"]: j for j in JUDGES}
JUDGE_NAME = {j["id"]: j["name"] for j in JUDGES}


def as_judge_id(value):
    """把模型给的评委标识归一到评委 id（认 id、认显示名、认前缀）。"""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if v in JUDGE_BY_ID:
        return v
    for jid, name in JUDGE_NAME.items():
        if v == name or v.startswith(name):
            return jid
    for jid in JUDGE_IDS:
        # 前缀匹配两个方向都认（模型可能写 `cost` 也可能写 `cost_judge`）；
        # ⚠️ 括号不能省：Python 里 `A or B and C` 是 `A or (B and C)`，
        # 少了括号会让很短的串直接命中，归一就形同虚设。
        if v.startswith(jid) or (len(v) >= 5 and jid.startswith(v)):
            return jid
    return None


# ---------------------------------------------------------------------------
# 公示的评分维度与权重 —— **在提案之前就写死在这里，并由 `rubric` 子命令公示**
#
# 为什么维度和权重是**常量**而不是让模型生成：竞标的公正性全押在"尺子先定"这件事上。
# 让模型在看过任务书之后现编一套维度，等于每次竞标换一把尺子，跨场不可比、
# 也无法解释"为什么这条赢了"。所以尺子是**代码里的常量 + 版本号**，
# `rubric` 只负责把它公示出来并存档；改了维度必须改 RUBRIC_VERSION。
#
# 四个维度与题面一致：成本 / 可行性 / 差异化 / 风险。权重合计 1.00。
# ---------------------------------------------------------------------------

DIMENSIONS = [
    {
        "id": "cost",
        "name": "成本",
        "weight": 0.30,
        "what": "端到端总花的钱与人力，能不能核算到单价 × 用量",
        "full": "把总成本拆到环节级，给出单价与用量的算式，并说明同等结果下为何不能再省",
        "zero": "只有「成本可控」「投入不大」这类说法，没有任何可核算的数字",
    },
    {
        "id": "feasibility",
        "name": "可行性",
        "weight": 0.25,
        "what": "以现有的人力、时间与资源，能不能真的按期做出来",
        "full": "给出人天与工期，标出关键路径与依赖，说明凭什么这个工期能兑现",
        "zero": "工期与人力含糊，或所需资源明超任务书给出的条件",
    },
    {
        "id": "differentiation",
        "name": "差异化",
        "weight": 0.25,
        "what": "有没有可指认、可验证、别人抄不走的差异",
        "full": "给出可指认的差异声称，并说明凭什么别人做不到、怎么验证它",
        "zero": "全是行业通用做法，或差异只停留在形容词上",
    },
    {
        "id": "risk",
        "name": "风险",
        "weight": 0.20,
        "what": "合规与执行风险的暴露面，以及翻车之后兜不兜得住",
        "full": "列出各环节失败模式与兜底动作，给可验收口径（指标 + 阈值 + 判定时点）",
        "zero": "无风险清单、无兜底动作，或存在明令禁止的表述与承诺",
    },
]

DIM_IDS = [d["id"] for d in DIMENSIONS]
DIM_BY_ID = {d["id"]: d for d in DIMENSIONS}
DIM_NAME = {d["id"]: d["name"] for d in DIMENSIONS}


def as_dim_id(value):
    """把模型给的维度标识归一到维度 id（认 id、认中文显示名）。"""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if v in DIM_BY_ID:
        return v
    for did, name in DIM_NAME.items():
        if v == name or v.startswith(name) or name in v:
            return did
    low = v.lower()
    for did in DIM_IDS:
        if low.startswith(did[:4]):
            return did
    return None


RUBRIC_TOTAL_WEIGHT = round(sum(d["weight"] for d in DIMENSIONS), 6)

# 名次与总分：总分是**本地按公示权重重算**的，不采信模型自己算的加权分。
# （模型算错乘法是常事，而"打分明细对不上总分"是裁决书最常见的废掉方式。）
SCORE_MIN, SCORE_MAX = 0, 10


def clamp_score(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x < SCORE_MIN:
        x = SCORE_MIN
    if x > SCORE_MAX:
        x = SCORE_MAX
    return x


def weighted_total(dim_scores):
    """按**公示权重**本地重算加权总分（0~10）。缺维度按 0 计并单独标注。"""
    total, missing = 0.0, []
    for d in DIMENSIONS:
        v = (dim_scores or {}).get(d["id"])
        if v is None:
            missing.append(d["id"])
            continue
        total += float(v) * d["weight"]
    return round(total, 3), missing


# ---------------------------------------------------------------------------
# 闸门一：合规（广告法违禁词）
#
# 每项：正则 → 风险等级 → 人话解释。这是一道**粗筛**，宁可多报也别漏报，
# 最终判断仍要人工复核，且不等于平台官方审核结论。
# 本包的合规评委还会独立再挑一遍，但**本地这道是确定性的**——
# 模型说"没问题"骗不过它。任务书命中就拦，竞标文书自己写出违禁词也拦。
# ---------------------------------------------------------------------------

# 「第一」的可枚举上下文豁免（与全族同口径）：
# 长文里「第一年」「第一步」「第一件事」是**序数**，不是最高级宣称。
# 一刀切拦下的后果很实在：用户会把整个合规闸门关掉，那比漏报更糟。
#
# ⚠️ 真机实测（第一轮跑就踩到）：「复用场景：第一，D20 中期核算时用」这种
# **中文列举**（第一，第二，第三…）也是序数用法，但列表里原来只有"词"，没有"标点"，
# 于是「第一，」被当成排他性宣称拦下。这里把逗号/顿号/冒号/右括号这类
# **列举分隔符**补进豁免，同时保持句首与「第一品牌」照拦。
FIRST_ORDINAL_AFTER = (
    "次|年|天|步|个|条|款|批|周|月|季|轮|种|点|部|遍|章|节|课|集|届|期|流|层|类"
    "|句|段|行|件|桶|手|版|稿|封|笔|单|场|局|盘|组|队|线|环|圈|代|世|阶|时|印|梯"
    "|反应|印象|时间|感觉|直觉|现场|眼"
    # 列举分隔符（中文里"第一，"= first, 不是"第一"类宣称）
    "|，|、|：|:|）|\\)|\\）"
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
    # 商业测算用语（竞标文书里极常见）：内部测算口径，不是对外广告语。
    # 边界仍然不变：**句首不豁免**（句首的「最高获客成本是 80 元」照拦）。
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
    """扫一遍违禁词，返回 (命中列表, 豁免列表)。被豁免的疑似命中**不静默放过**。"""
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
# 竞标文书里「成本最大的一块」「最高出价」是普通中文程度用法与内部测算口径，
# 不是对外商品宣称；而这类误报会让人把整个合规闸门关掉。任务书侧**照查**。
# 被排除的条目**不静默丢弃**：它们照样进 `contextual_only`，附 `not_counted_reason`。
OUTPUT_EXCLUDED_WHY = ("广告法第九条禁止「最高级」用语",)

# 「提到」而不是「主张」的上下文标记。
# 实质差异（竞标文书特有）：评委与裁决人**必须**讨论违禁话术（"这段无依据的承诺要删"）、
# 质询主持要指出对方方案里踩线的表述，这些是**在指出风险**，不是自己在做违规宣称。
# 判定方式很朴素：看命中所在的那**一整个小句**里有没有这些标记词——有就是"提到/在拦它"，
# 没有才是"自己在主张"。这一条也保证了闸门还有牙：
# 「本方案必须保证过审」这种小句里没有任何标记词，照样拦。
META_CONTEXT_RE = re.compile(
    "禁止|严禁|不得|不许|不能|不可|避免|杜绝|防范|防止|违规|风险|涉嫌|属于|构成|"
    "无出处|无法举证|不可举证|举证|撤回|删除|删掉|去掉|不实|虚假|夸大|诱导|"
    "不构成|不算|不是|未|没|缺|整改|改为|改成|替换|风险点|红线|合规问题|"
    # 真机实测补进来的四条（都是"在禁止"的写法，第一轮跑就误报了三条）：
    # 「对外话术**不包含**『保证过审』『100%有效』『稳赚』」——这是在禁止，
    # 但原来的窗口只有命中前后各 24 字，而禁止词在引号串的**最后一个**词前面，
    # 第一个词（保证过审）离它就超过了 24 字，于是被当成"自己在主张"。
    "不包含|不含|禁用|勿用|不许用|不得使用|拒绝|杜绝使用")
_SENT_BOUND = re.compile(r"[。！？!?；;\n]")
# 「提到/在禁止」判定的取样窗口：命中前后各 32 字、不跨句末标点。
# 真机实测：24 字太窄（引号串会把标记词推远），32 字刚好包住
# 「不包含「保证过审」「100%有效」「稳赚」等词」这类列举式禁止。
META_CTX_WIDTH = 32


def _ctx_window(text, pos, width=None):
    """命中位置前后各 width 个字符（**不跨句末标点**）。

    为什么用"窗口"而不是"整句"：中文句子里逗号、顿号极多，
    按标点切成小句会把「明确禁止代发、代拍、刷量」切碎成「刷量」，
    标记词正好被切掉 —— 这是同族自测时真踩到的一次。
    也不跨句末标点：跨句取词会把上一句的"禁止"借给下一句的违规宣称。
    """
    if width is None:
        width = META_CTX_WIDTH
    start = 0
    for m in _SENT_BOUND.finditer(text):
        if m.end() <= pos:
            start = m.end()
        else:
            break
    m = _SENT_BOUND.search(text, pos)
    end = m.start() if m else len(text)
    return text[max(start, pos - width):min(end, pos + width)]


def _mentioned_as_warning(prose, word):
    """这个词是不是在**被禁止 / 被指出风险**，而不是"自己主张"。

    真机实测踩到的误报（第一轮跑就中了三条，见 references/成本与排错.md）：
    获胜方案里写着「对外话术不包含「保证过审」「100%有效」「稳赚」等词」——
    这是**条款在禁止这些词**，但：
      · 原来的窗口（前后各 24 字）只覆盖到引号串的末尾，
        第一个词「保证过审」离「不包含」超过了 24 字，于是被判成"自己在主张"；
      · 更关键的是 `prose.find(word)` **只找第一次出现的位置**，
        而同一个词在长文里往往先以别的形态出现过。

    所以这里两处都改：
      1. 窗口放宽到 `META_CTX_WIDTH`（32 字），前后都看；
      2. **遍历这个词的每一次出现**，只要有一次落在"禁止 / 举证 / 风险"语境里，
         就判为「提到」——"列举式禁止"里的词不会同时又在别处被当成主张。
    返回 (是否提到, 证据标记词, 上下文)。
    """
    t = prose or ""
    if not word:
        return False, "", ""
    for m in re.finditer(re.escape(word), t):
        ctx = _ctx_window(t, m.start())
        mark = META_CONTEXT_RE.search(ctx)
        if mark:
            return True, mark.group(0), ctx[:80]
    return False, "", (_ctx_window(t, t.find(word)) if word in t else "")


def compliance_scan_output(prose, material):
    """产出侧合规（**与任务书侧口径不同**）。

    竞标文书的三类正常写法，会被粗筛误判成违规宣称：
      1. **引用**：评委引任务书里的问题表述（「『保证过审』是无依据承诺」）
      2. **提到**：风险评委写「无法举证为 100% 成立」「明确禁止刷量」
         —— 这是在禁止、在指出风险，不是自己在做违规宣称
      3. **讨论**：质询与裁决**必须**复述对方方案里的踩线表述才能裁它

    所以产出侧收紧成三条**能解释的**规则：
      1. 只查**高风险**（广告法明令禁止的那一类）；中低风险项与 `最X`
         在竞标文书里多半是描述性用语，列进 `contextual_only` 提示人工看，不拦。
      2. 任务书里已经出现过的词判为**引用**，不计命中。
      3. 这个词的**每一次出现**都要看一遍上下文（前后各 32 字、不跨句末标点）：
         只要有一次落在"禁止 / 举证 / 风险"语境里就判为**提到**，不计命中
         （见 `_mentioned_as_warning` —— 第一轮真机跑就是被"列举式禁止"误报的）；
         一次都没落进那种语境的才是**自己在主张** → 拦
         （「本方案必须保证过审，效果 100% 达标」照样拦得住）。
    被排除的条目**全部保留在案**（带 `not_counted_reason`），不静默丢弃。
    """
    hi_all, exempted = compliance_scan(prose, levels=("高",))
    hi, soft = [], []
    for h in hi_all:
        if h["why"] in OUTPUT_EXCLUDED_WHY:
            h = dict(h)
            h["not_counted_reason"] = ("`最X` 在竞标文书里多为普通中文程度用法或内部测算口径"
                                       "（如「成本最大的一块」「最高出价」），"
                                       "产出侧不拦；任务书侧照查")
            soft.append(h)
        else:
            hi.append(h)
    mat_words = {h["word"] for h in compliance_scan(material)[0]}
    fresh, quoted, mentioned = [], [], []
    for h in hi:
        if h["word"] in mat_words:
            quoted.append(h)
            continue
        hit, mark, ctx = _mentioned_as_warning(prose, h["word"])
        if hit:
            h = dict(h)
            h["not_counted_reason"] = (
                "命中前后 {} 字里有「{}」这类标记词——判为**提到/在禁止**，"
                "不是竞标方自己在做违规宣称".format(META_CTX_WIDTH, mark))
            h["context_window"] = ctx
            mentioned.append(h)
        else:
            fresh.append(h)
    contextual, _ = compliance_scan(prose, levels=("中", "低"))
    return fresh, quoted, mentioned, contextual + soft, exempted


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
#
# 任务书与竞标文书都是给人看的，模板没替换干净是最典型的"没交付"形态：
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
# 竞标场景更容易踩：提示词里写"什么算一条好意见"，模型就把那句原样填进 `why`。
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
# 跨主题 = 与任何真实任务书都不搭（社区旧衣回收），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
PROMPT_SAMPLES = [
    "社区旧衣回收箱到底该不该撤，先看三个数",
    "小区旧衣回收的运输成本别只看车费",
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

    为什么方案重合度不能直接用 Jaccard：三份方案的篇幅天然不同
    （B 组可能写了 1500 字，A 组只有 700 字），Jaccard 的分母是并集，
    篇幅差一大就被摊薄，"三组交的是同一份东西"反而测不出来。
    用 min 归一后，「短的那份有多少比例出现在长的那份里」才是我们要问的问题。
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
# 闸门四：打分锚点（每条打分理由必须引用方案真实原文）
#
# 一份竞标打分最没用的形态，是"泛泛而谈"：都说"方案不错""成本略高"，
# 谁也不说清是哪一句。而且**本包特有**的风险是：评委很容易把 A 组的原文
# 挂到 B 组头上（三份方案在同一个任务下确实会有些相似表述）。
# 所以本包不采信模型的引文，而是**本地校验**，而且**锚到正确的那个组**：
#   · 打分理由的 quote    → 只能锚到**被评的那一组自己**的方案（anchor 到别的组 = 幻觉）
#   · 获胜理由的 quote    → 锚到获胜组的方案
#   · 落选原因 / 合并建议的 quote → 锚到它标注的那一组
# 四条判据递进：
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

# 交叉可见性核对：对方方案里**够长**的句子（归一后 ≥ 这个字数）如果在提示词里出现，
# 就是"对方原文漏出去了"。摘要里的主张一般较短，所以这个门槛能把"摘要"与"原文"分开。
CROSS_LEAK_MIN = 20


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
    """一个可被引用的文本（任务书 / 某个组的方案），带句子切分缓存。"""

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
# 闸门五：提案独立性（**本包的核心闸门**）
#
# 这是"竞争"与"协作"的分水岭。三组如果交上来的是**同一份东西的三种说法**，
# 那么：
#   · 没有竞争发生 —— 只是把一份稿子抄了三遍，然后假装选了一个赢家；
#   · 打分排序失去意义 —— 三份一样的东西排出来的名次是噪声；
#   · 合并建议也无从谈起 —— 落选方案里没有任何"别处没有的东西"可以合并。
# 一句话：**"三组各写一段然后合并"就是协作，不是竞争，这包就白做了。**
#
# 这一条不靠提示词声明，本地算：
#   判据 A（硬）：任一对方案的**重合度** ≥ INDEP_OVERLAP，且两份中较短的那份
#                二元组不少于 INDEP_MIN_GRAMS（防短文本虚高）→ 判「假竞争」
#   判据 B（标红）：重合度 ≥ INDEP_RED_OVERLAP 但未到硬阈值 → 提示人工看一眼
#   判据 C（标红）：任一方案**自己的话**太少（只写了通用套话）→ 提示"方案没有实质内容"
#
# 重合度用 min 归一（不是 Jaccard）的理由见 _overlap()。
# 阈值 0.75 与同族闸门口径一致；真机实测三份合格方案的两两重合度在 0.1~0.3 量级，
# 余量很大 —— 一旦真的抄成一份，重合度会直接顶到 0.9 以上。
# ---------------------------------------------------------------------------

INDEP_OVERLAP = 0.75       # 判据 A：硬闸门阈值
INDEP_RED_OVERLAP = 0.55   # 判据 B：标红（不单独拦）
INDEP_MIN_GRAMS = 30       # 判据 A：短的那份至少这么多二元组（约 30 字内容）
INDEP_MIN_OWN_GRAMS = 40   # 判据 C：一份方案自己的话少于这个量就提示"只有套话"
INDEP_SENT_MIN = 16        # 句子级相似度只对够长的句子算（短句雷同没有信息量）


def proposal_own_text(p):
    """一个方案的**自己的话**（供重合度判定用）。

    取方案的全部实质内容：一句主张 / 交付物 / 成本工期 / 差异点 / 风险兜底。
    与同族不同，这里不需要剔除"引用"——方案是各写各的，不存在三组共同引用
    同一句任务书原文的情形（任务书原文本来就不在方案里）。
    """
    if not isinstance(p, dict):
        return ""
    parts = [p.get("headline") or "", p.get("approach") or "", p.get("offer") or ""]
    for c in p.get("claims") or []:
        if isinstance(c, dict):
            parts.extend([c.get("text") or "", c.get("evidence") or ""])
    for d in p.get("deliverables") or []:
        parts.append(d if isinstance(d, str) else (d or {}).get("text") or "")
    parts.append(p.get("cost") or "")
    parts.append(p.get("timeline") or "")
    parts.append(p.get("differentiation") or "")
    for r in p.get("risks") or []:
        if isinstance(r, dict):
            parts.extend([r.get("risk") or "", r.get("cover") or ""])
    parts.append(p.get("acceptance") or "")
    return "\n".join(x for x in parts if x)


def independence_check(proposals):
    """算三份方案的重合度，返回结构化结论（含每一对的数字，便于人工复核）。"""
    res = {"pairs": [], "max_overlap": 0.0, "overlap_pairs": [], "red_pairs": [],
           "thin_own_words": [], "lengths": {},
           "text_basis": ("重合度与句子级相似度只算各方案**自己的话**"
                          "（主张 / 交付物 / 成本工期 / 差异点 / 风险兜底 / 验收口径）。"
                          "重合度高说明三组交的是同一份东西的三种说法——那是协作，"
                          "不是竞争。")}
    bodies = {}
    for p in proposals or []:
        if isinstance(p, dict) and p.get("team"):
            bodies[p["team"]] = proposal_own_text(p)
    ids = [t for t in TEAM_IDS if t in bodies]
    for tid in ids:
        res["lengths"][tid] = {"chars": len(bodies[tid]),
                               "bigrams": len(_bigrams(bodies[tid]))}
        if len(_bigrams(bodies[tid])) < INDEP_MIN_OWN_GRAMS:
            res["thin_own_words"].append({"team": tid, "own_grams": len(_bigrams(bodies[tid]))})
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            ov = _overlap(bodies[a], bodies[b])
            grams = min(len(_bigrams(bodies[a])), len(_bigrams(bodies[b])))
            sent_max, sent_pair = 0.0, ""
            for x in split_sentences(bodies[a]):
                for y in split_sentences(bodies[b]):
                    if (len(_norm_anchor(x)) < INDEP_SENT_MIN
                            or len(_norm_anchor(y)) < INDEP_SENT_MIN):
                        continue
                    sim = _similarity(x, y)
                    if sim > sent_max:
                        sent_max, sent_pair = sim, x[:40]
            rec = {"a": a, "b": b, "overlap": round(ov, 3), "min_grams": grams,
                   "max_sentence_sim": round(sent_max, 3), "sentence": sent_pair,
                   "note": "重合度按较短一侧归一（min 归一），避免篇幅差把相似度算歪"}
            res["pairs"].append(rec)
            res["max_overlap"] = max(res["max_overlap"], round(ov, 3))
            if ov >= INDEP_OVERLAP and grams >= INDEP_MIN_GRAMS:
                res["overlap_pairs"].append(rec)
            elif ov >= INDEP_RED_OVERLAP:
                res["red_pairs"].append(rec)
    return res


# ---------------------------------------------------------------------------
# 闸门六：裁决完整性
#
# 裁决是最终交付物。竞标裁决有五种常见的废掉方式：
#   1. 判了获胜组却说不出**凭什么**（没有打分明细）—— 等于假装有竞争
#   2. 落选方案的**落选原因**缺失 —— 用户不知道为什么输了，下一版无从下手
#   3. 落选方案的**可用部分**（合并建议）缺失 —— 竞标最大的浪费：
#      落选稿里明明有好东西，却因为"它输了"被整份丢掉
#   4. 获胜组是一个**被评委一票否决**的组 —— 分再高也不能上
#   5. 有反对方（少数派）意见却不在案 —— 把争论抹平，用户只看到一个结论
# 这五条都在本地判，不采信模型的自我声明。
# ---------------------------------------------------------------------------

def award_gate(award, proposals, panel):
    """裁决完整性闸门。返回 (ok, problems, audit)。"""
    problems = []
    award = award if isinstance(award, dict) else {}
    winner = as_team_id(award.get("winner"))
    audit = {"winner_raw": award.get("winner"), "winner_id": winner}

    # 本地票表：每组的总分与是否被否决（不采信模型自报的"谁分高"）
    totals, vetoed = {}, {}
    for s in (panel or {}).get("judges") or []:
        for sc in s.get("scores") or []:
            tid = sc.get("team")
            if not tid:
                continue
            totals.setdefault(tid, {})
            for d in DIMENSIONS:
                if sc.get("dims", {}).get(d["id"]) is not None:
                    totals[tid][d["id"]] = max(totals[tid].get(d["id"], 0),
                                               sc["dims"][d["id"]])
            for f in sc.get("faults") or []:
                if isinstance(f, dict) and f.get("hit"):
                    pass
    for s in (panel or {}).get("judges") or []:
        for v in s.get("vetoes") or []:
            tid = v.get("team")
            if tid:
                vetoed[tid] = v.get("reason") or "评委一票否决"
    # 总分按"各评委该维度的均值"算，再由**本地公示权重**加权
    judge_totals = {}
    for s in (panel or {}).get("judges") or []:
        for sc in s.get("scores") or []:
            tid = sc.get("team")
            if not tid:
                continue
            judge_totals.setdefault(tid, []).append(sc.get("total"))
    local_totals = {}
    for tid, vals in judge_totals.items():
        nums = [v for v in vals if isinstance(v, (int, float))]
        if nums:
            local_totals[tid] = round(sum(nums) / float(len(nums)), 3)
    audit["local_totals"] = local_totals
    audit["vetoed"] = vetoed
    audit["local_ranking"] = [t for t, _ in sorted(local_totals.items(), key=lambda x: -x[1])]

    if winner is None:
        problems.append("裁决里没有可识别的获胜组（`winner` = {!r}）——"
                        "竞标必须有胜负，判不出赢家等于没裁".format(award.get("winner")))
    elif winner in vetoed:
        problems.append("裁决判「{}」获胜，但它被评委**一票否决**了（{}）——"
                        "被否决的方案不能当获胜方案".format(
                            TEAM_NAME.get(winner, winner), vetoed[winner]))
    elif local_totals and winner != audit["local_ranking"][0]:
        # 不直接拦（评委的定性判断可以压过算术），但必须解释 —— 记成待解释项
        audit["winner_not_top_by_total"] = {
            "winner": winner, "winner_total": local_totals.get(winner),
            "top": audit["local_ranking"][0], "top_total": local_totals.get(audit["local_ranking"][0]),
            "note": "模型判的赢家不是本地总分第一——裁决里必须给出为什么（`why_winner` 是否有实质理由）",
        }
        if not (award.get("why_winner") or "").strip():
            problems.append("裁决判「{}」获胜，但按公示权重重算的总分第一是「{}」"
                            "（{} vs {}），且 `why_winner` 为空 —— 要么给理由，要么改判".format(
                                TEAM_NAME.get(winner, winner),
                                TEAM_NAME.get(audit["local_ranking"][0],
                                              audit["local_ranking"][0]),
                                local_totals.get(winner),
                                local_totals.get(audit["local_ranking"][0])))

    # ⚠️ 这里**只认裁决自己带的打分明细**，不能拿评委团的表来顶。
    # 同族踩过这个坑：本地"好心"补齐之后，这道闸门永远不可能命中 ——
    # 闸门看起来在跑，其实自己把失败圆过去了。评委团的表只能作为**交叉核对**用。
    score_detail = award.get("score_detail") or []
    if not score_detail:
        problems.append("判了获胜组却没有**打分明细**——竞标裁决必须带分，"
                        "否则是「假装有竞争」：看不出赢在哪、输在哪")
    else:
        # 本地交叉核对：裁决自报的分 vs 评委团按公示权重重算的分。
        # 差得太多说明"裁决的分"和"评委打的分"不是一回事，必须让人看见。
        panel_totals = {x.get("team"): x.get("total")
                        for x in (panel or {}).get("score_detail") or []}
        for x in score_detail:
            tid = x.get("team")
            local = x.get("total")
            ref = panel_totals.get(tid)
            if tid and isinstance(local, (int, float)) and isinstance(ref, (int, float)):
                if abs(local - ref) > 1.0:
                    problems.append(
                        "裁决给「{}」的分是 {:.2f}，评委团按公示权重重算的是 {:.2f}，"
                        "差 {:.2f}（> 1.0）——裁决的分与评委打的分对不上，"
                        "这份打分明细不可信".format(
                            TEAM_NAME.get(tid, tid), local, ref, abs(local - ref)))

    by_team = {}
    for p in proposals or []:
        if isinstance(p, dict) and p.get("team"):
            by_team[p["team"]] = p
    losers = award.get("losers") or []
    listed_losers, unknown_losers = [], []
    for x in losers:
        if not isinstance(x, dict):
            continue
        tid = as_team_id(x.get("team"))
        if tid:
            listed_losers.append(tid)
        else:
            unknown_losers.append(str(x.get("team")))
    if unknown_losers:
        problems.append("落选名单里出现了不存在的组：{}".format("、".join(unknown_losers)))
    expected_losers = [t for t in by_team if t != winner]
    missing_losers = [t for t in expected_losers if t not in listed_losers]
    if missing_losers:
        problems.append("{} 落选了却不在落选名单里（落选原因缺失）".format(
            "、".join(TEAM_NAME.get(t, t) for t in missing_losers)))
    for x in losers:
        if not isinstance(x, dict):
            continue
        tid = as_team_id(x.get("team"))
        if tid and not (x.get("why_lost") or "").strip():
            problems.append("「{}」没有给出**落选原因**（`why_lost` 为空）——"
                            "竞标裁决必须说清它输在哪一维度".format(TEAM_NAME.get(tid, tid)))

    merges = award.get("merges") or []
    if not merges:
        problems.append("没有给出**合并建议**（落选方案的可用部分）——"
                        "竞标最大的浪费就是把落选稿整份丢掉："
                        "落选方案的可用部分必须逐条写清「从哪一组拿、补进获胜方案的哪一处」")
    for m in merges:
        if not isinstance(m, dict):
            continue
        tid = as_team_id(m.get("from_team"))
        if tid is None:
            problems.append("合并建议里出现了不存在的来源组：{!r}".format(m.get("from_team")))
        elif tid == winner:
            problems.append("合并建议的来源是获胜组自己（{}）——"
                            "合并建议指的是**从落选方案里拿东西**".format(
                                TEAM_NAME.get(tid, tid)))
        if not (m.get("into") or "").strip():
            problems.append("有一条合并建议没说清补进获胜方案的哪一处（`into` 为空）")

    dissent = award.get("dissent") or []
    if vetoed:
        for tid, why in vetoed.items():
            named = [as_team_id(d.get("team")) for d in dissent if isinstance(d, dict)]
            if tid not in named:
                problems.append("「{}」被评委一票否决（{}），却不在异议记录里 —— "
                                "否决意见被抹平了".format(TEAM_NAME.get(tid, tid), why))
    return (not problems), problems, audit


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
# 【信息隔离】propose 阶段的提示词里**只有本组自己的立场块与任务书**：
#   · 没有另外两组的任何文字（否则就是互相抄，竞争不成立）
#   · 没有评分维度与权重（否则三组会照着同一把尺子把自己优化成同一个形状，
#     那正好落进闸门五要抓的「假竞争」）
# 【交叉可见性】challenge 阶段每组只看得到**对方的主张摘要**（headline + claims），
#   看不到对方的原文与交付细节 —— 这是题面写死的规则，也是本包与
#   "把三份稿子摆一起互评"（那是评审委员会做的事）的分界线。
# ---------------------------------------------------------------------------

CHAT_RETRY_NOTE = "上游 5xx 与网络抖动退避重试；4xx 直接报错，不浪费额度。"

TEAM_SYSTEM = (
    "你是「三剪客 · 方案竞标小组」的**{name}**（{label}）。\n"
    "你代表本组去**赢下这个名额**：这不是写一份四平八稳的方案，"
    "而是把本组的取胜路线打到最锋利的地方。\n"
    "本组的取胜路线：{route}\n"
    "本组的天然倾向（这是本组的打法，不是缺点）：{bias}\n"
    "本组最不能让步的一点：{must_have}\n"
    "为赢下这个名额，本组肯牺牲什么：{give_up}\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 你**不知道**另外几组写了什么，**也不知道**评委按哪些维度打分。"
    "不许猜、不许假设、不许写「相对而言」「比同类方案更好」这类没有对照物的比较。\n"
    "  2. 每一条主张都要给得出依据（算式、口径、可验证的做法）；"
    "编不出依据的主张一律不要写。\n"
    "  3. 不许编造任务书里没有的数据、案例、机构名、人名；"
    "不许写「保证过审」「100% 有效」「稳赚」这类无依据的承诺。\n"
    "  4. 不许写「整体可行」「建议加强执行」这类无法落纸的话；"
    "每条内容都要具体到别人能照着做。\n"
    "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

# 跨主题示例：只用来讲"什么样的一条主张算没有依据"，不是范文。
# 跨主题 = 与任何真实任务书都不搭（社区旧衣回收），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
_PROMPT_SAMPLE_BLOCK = (
    "跨主题示例（**仅供理解「什么算没有依据」，禁止把示例原句写进任何字段**）：\n"
    "  · 反面（没有依据）：把「{}」这类**没有出处的判断**当成主张，只说要更好，不说凭什么。\n"
    "  · 正面（有依据）：给出可核算的算式、可验证的做法或可复现的口径。\n"
).format(PROMPT_SAMPLES[0])

_PROPOSAL_SCHEMA = {
    "headline": "一句话说清本组方案是什么（不超过 40 字）",
    "approach": "本组打算怎么做（这一段是方案主干）",
    "claims": [
        {
            "text": "本组的一条主张",
            "evidence": "这条主张的依据（算式 / 口径 / 可验证的做法）",
        }
    ],
    "deliverables": ["本组最终交付什么（逐条列出，具体到能验收）"],
    "cost": "总花多少钱、钱花在哪（要给算式或明确口径）",
    "timeline": "要几个人、几天，关键路径是什么",
    "differentiation": "本组方案里最不一样的一点，以及凭什么别人做不到",
    "risks": [
        {"risk": "最可能翻车的一步", "cover": "怎么兜、兜不住怎么回滚"},
    ],
    "acceptance": "验收口径：看哪几个指标、多少算过、多少算停",
}


def build_team_prompt(team, task, task_meta=None):
    """单个提案组的提示词。**只含本组立场与任务书**（信息隔离的实现处）。

    刻意**不包含**：另外两组的任何文字、评分维度、评委名单、权重。
    """
    meta = task_meta or {}
    head = ("下面是**这次竞标的任务书**。请以「{name}」（{label}）的身份，"
            "按本组的取胜路线，独立写出一份**能赢的方案**。\n"
            "说明：同一时间还有别的组在写各自的方案，你们互相看不到，"
            "评委也不参与写方案。你只管把本组这条路打到最好。\n").format(
        name=team["name"], label=team["label"])
    lines = [
        "本组的方案视角（只从这一条出发）：" + team["question"],
        "",
        "本组盯的点（这是本组的清单，不是全部）：",
    ]
    lines += ["  · " + x for x in team["focus"]]
    lines += [
        "",
        "写作要求：",
        "  · headline 一句话说清方案是什么；approach 是主干，写清怎么做、分几步。",
        "  · claims 最多 8 条，每条都要带 evidence（算式 / 口径 / 可验证的做法）；"
        "给不出依据的主张直接删掉。",
        "  · deliverables 逐条列清交付物，具体到能验收。",
        "  · cost 与 timeline 要能核算；acceptance 要给指标 + 阈值 + 判定时点。",
        "  · risks 逐条给「最可能翻车的一步 + 怎么兜」。",
        "  · 不要写「相对而言更好」这类没有对照物的比较——你看不到别人写什么。",
        "",
        _PROMPT_SAMPLE_BLOCK,
    ]
    if meta.get("chars"):
        lines += ["", "  · 任务书 {} 字符 / {} 句".format(
            meta.get("chars"), meta.get("sentences"))]
    return (
        head
        + "\n".join(lines)
        + "\n\n按要求只输出这个 JSON 对象：\n"
        + json.dumps(_PROPOSAL_SCHEMA, ensure_ascii=False, indent=1)
        + "\n\n===== 任务书开始 =====\n" + (task or "")
        + "\n===== 任务书结束 =====\n"
    )


JUDGE_SYSTEM = (
    "你是「三剪客 · 方案竞标小组」评委团的**{name}**（侧重：{focus}）。\n"
    "你按**已经公示的评分维度与权重**给每一份方案打分，权重不可改。\n"
    "你的评审重点：{question}\n"
    "你的打分风格：{style}\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 同一次调用里，你**同时**看到全部方案——这是为了横向可比，不是让你折中。"
    "每一份方案都要独立给分，不许为了拉开差距而刻意压分或抬分。\n"
    "  2. 每条打分理由**必须原样引用那组方案里真实存在的一句话**"
    "（或句中连续的一小段），不得改写、不得概括、不得凭空编造引文，"
    "更不许把别组的原话挂到这组头上。引不出来的理由一律不要写。\n"
    "  3. 0~10 分：10 = 这个维度上毫无可挑之处，0 = 这一维度完全没交代。"
    "中间分数请用小数（例如 6.5），别都挤在整数上。\n"
    "  4. 只在你这一席位**有明确否决权**且发现合规硬伤时，才把该组写进 `vetoes`；"
    "没有否决权时 `vetoes` 必须是空数组。否决必须给出理由与原文引文。\n"
    "  5. 不许编造方案里没有的数字、案例、承诺。\n"
    "  6. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

_JUDGE_SCHEMA = {
    "scores": [
        {
            "team": "方案编号（1 / 2 / 3）",
            "dims": {"成本": 0, "可行性": 0, "差异化": 0, "风险": 0},
            "reasons": [
                {
                    "dim": "成本|可行性|差异化|风险",
                    "quote": "该方案里**原样**的一句话",
                    "score": 0,
                    "why": "这个维度上为什么给这个分",
                    "fix": "要做到多少分，它必须补上什么（具体到能落纸）",
                }
            ],
            "conclusion": "两三句总评",
        }
    ],
    "vetoes": [{"team": "方案编号", "reason": "否决理由", "quote": "该方案原样的一句话"}],
    "summary": "两三句总评",
}


def _anon_label(idx):
    return "方案 {}".format(idx + 1)


def build_judge_prompt(judge, task, proposals, rubric):
    """单个评委的提示词。三份方案**匿名**给（不带组名），避免先入为主。

    评委看得到公示的评分维度与权重（那是公开的），看不到各组自己的立场块，
    也看不到别的评委打了多少分（三名评委各是一次独立调用）。
    """
    lines = [
        "本次竞标的**任务书**与**全部 {} 份方案**都在下面。请按公示维度逐份打分。".format(
            len(proposals)),
        "",
        "【公示的评分维度与权重（不可改）】",
    ]
    for d in DIMENSIONS:
        lines.append("  · {}（`{}`，权重 {:.2f}）：{}".format(
            d["name"], d["id"], d["weight"], d["what"]))
        lines.append("      {:.1f} 分的写法：{}".format(10.0, d["full"]))
        lines.append("      {:.1f} 分的写法：{}".format(0.0, d["zero"]))
    lines += [
        "  权重合计 {:.2f}。总分为各维度分数按上述权重加权。".format(RUBRIC_TOTAL_WEIGHT),
        "",
        "【打分要求】",
        "  · `team` 必须填**方案编号**（{}），下面每份方案都标了编号。".format(
            " / ".join(_anon_label(i) for i in range(len(proposals)))),
        "  · `dims` 四个维度都要给 0~10 的分（可用小数）。",
        "  · `reasons` 至少 4 条，**四个维度各覆盖一次**；每条的 `quote` 必须是"
        "**该组方案原文里真实存在的一句话**，不许跨组引用。",
        "  · 每条 `fix` 要具体：要做到更高分必须补上什么。",
        "  · 三个编号的方案都要出现在 `scores` 里，一个都不能漏。",
    ]
    if judge["veto_power"]:
        lines += [
            "  · **你有否决权**：发现合规硬伤（明令禁止的表述、无依据承诺、"
            "资质缺失却拿资质说事、刷量话术等）就把该组写进 `vetoes`。"
            "否决同时要在 reasons 里指出原文。",
        ]
    else:
        lines += ["  · **你没有否决权**：`vetoes` 请给空数组 `[]`。"]
    lines += [
        "",
        _PROMPT_SAMPLE_BLOCK,
        "",
        "===== 任务书开始 =====",
        task or "",
        "===== 任务书结束 =====",
        "",
    ]
    for i, p in enumerate(proposals):
        lines += [
            "===== {} 开始 =====".format(_anon_label(i)),
            json.dumps(p.get("body") or {}, ensure_ascii=False, indent=1),
            "===== {} 结束 =====".format(_anon_label(i)),
            "",
        ]
    lines += [
        "按要求只输出这个 JSON 对象：",
        json.dumps(_JUDGE_SCHEMA, ensure_ascii=False, indent=1),
    ]
    return "\n".join(lines)


CHALLENGE_SYSTEM = (
    "你是「三剪客 · 方案竞标小组」的**质询主持**。\n"
    "你的职责不是评谁好谁坏（那是评委的事），而是**逼出差异**："
    "让每一组把「我为什么比另外两组更该拿到这个名额」说到具体、可核对、"
    "能被对方反驳的位置上。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. **信息隔离**：你手里只有每组提交的**主张摘要**，"
    "没有对方的原文、没有对方的交付细节。绝对不许编造对方的原话，"
    "也不许凭摘要推断对方没写的东西。\n"
    "  2. 问题必须**只针对被质询的那一组自己**："
    "   · 它的方案原文里（你手里有全文）哪一处最经不起追问？\n"
    "   · 评委点出的问题，它打算怎么改？\n"
    "   · 面对另外两组已经亮出来的主张，它的差异化优势到底落在哪一点上？\n"
    "  3. 不许写「整体不错」「建议优化」这类无法执行的空话；每条问题都要能直接回答。\n"
    "  4. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

_CHALLENGE_SCHEMA = {
    "questions": [
        {
            "ask": "向这一组提出的一个问题（只针对它自己）",
            "targets": "这个问题打在它方案的哪一点上",
            "why_hard": "为什么这个问题它必须回答（答不上来会怎样）",
        }
    ],
    "rivals_seen": ["你从摘要里看到的、另外两组各自的核心主张（原样复述摘要，不要扩写）"],
    "must_answer": "这一组在回答里必须交代清楚的一件事（一句话）",
}


def build_challenge_prompt(team, task, own, rival_digests, judge_feedback):
    """质询提示词的构造。

    **交叉可见性（本包的分界线）**：这一组的提示词里
      · 有：它**自己**的全文方案、评委对**它**的打分与批评、另外两组的**主张摘要**
      · 没有：另外两组的**原文**、另外两组收到的批评与分数
    这样它才可能"论证我比它们好"（因为有摘要可对照），
    又不可能"抄它们的方案"（因为看不到原文）。
    """
    lines = [
        "下面要质询的是「{}」（{}）。给它看的材料如下。".format(
            team["name"], team["label"]),
        "",
        "【另外两组已经亮出来的主张摘要（**只有摘要，没有原文**）】",
    ]
    if rival_digests:
        for d in rival_digests:
            lines.append("  · {}：{}".format(d["anon"], d["headline"]))
            for c in d["claims"]:
                lines.append("      - {}".format(c))
    else:
        lines.append("  · （没有可对照的摘要）")
    lines += [
        "",
        "【评委对**这一组**的打分与批评（只给了这一组的，别组的评委意见没有给你）】",
    ]
    if judge_feedback:
        for jf in judge_feedback:
            lines.append("  · {}（{}）给出总分 {}：".format(
                jf["judge_name"], jf["judge_id"], jf["total"]))
            for r in jf["reasons"]:
                lines.append("      - [{}] {} → {}".format(
                    r["dim_name"], r["why"], r["fix"]))
            if jf.get("veto"):
                lines.append("      - !! 该评委行使了**一票否决**：{}".format(jf["veto"]))
            if jf.get("conclusion"):
                lines.append("      - 总评：{}".format(jf["conclusion"]))
    else:
        lines.append("  · （没有评委意见）")
    lines += [
        "",
        "【这一组自己的方案原文】",
        json.dumps(own.get("body") or {}, ensure_ascii=False, indent=1),
        "",
        "质询要求：",
        "  · questions 给 3~6 条，每条都只针对**这一组自己**，且必须能回答。",
        "  · 至少 1 条问题必须打在「它凭什么比另外两组更该拿到名额」这一点上"
        "（它只知道对方的主张摘要，所以问题要落在摘要里已经亮出来的那几点上）。",
        "  · rivals_seen 原样复述你从摘要里看到的对方主张，不要扩写、不要补细节。",
        "  · 不许出现对方方案的原话（你没有对方原文，写了就是编造）。",
        "",
        _PROMPT_SAMPLE_BLOCK,
        "",
        "===== 任务书开始 =====",
        task or "",
        "===== 任务书结束 =====",
        "",
        "按要求只输出这个 JSON 对象：",
        json.dumps(_CHALLENGE_SCHEMA, ensure_ascii=False, indent=1),
    ]
    return "\n".join(lines)


ANSWER_SYSTEM = (
    "你是「三剪客 · 方案竞标小组」的**{name}**（{label}），正在接受交叉质询。\n"
    "你只代表本组作答。你的目标是：把「本组为什么比另外两组更该拿到这个名额」"
    "说到具体、可核对、经得起反驳的位置上。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. **你看不到另外两组的原文**，只能看到它们自己亮出来的**主张摘要**。"
    "不许编造对方的原话、不许假设对方没写的内容、不许说「对方方案里某某处」。\n"
    "  2. 与对方比较时，只能引用**摘要里已经出现的主张**，"
    "并说明本组在哪一点上更强、凭什么。\n"
    "  3. 承认该认的：评委点到的问题，如果确实成立，直接说怎么改、改到什么程度；"
    "不要嘴硬，也不要空口保证。\n"
    "  4. 不许写「整体更优」「综合来看更好」这类没有落点的比较。\n"
    "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

_ANSWER_SCHEMA = {
    "answers": [
        {
            "q": "你回答的是哪一个问题（原样抄问题）",
            "a": "你的回答",
            "evidence": "答案的依据（算式 / 口径 / 可验证的做法）",
            "concede": "该认的就认：这里写你要改什么、改到多少",
        }
    ],
    "why_better": [
        {
            "than": "对方主张摘要里的哪一条",
            "point": "本组在哪一点上更强",
            "why": "凭什么（必须能核对，不许只说「更用心」）",
        }
    ],
    "cannot_beat": "对方哪一条主张是本组确实比不过的（如实说；没有就写「无」）",
}


def build_answer_prompt(team, task, own, rival_digests, judge_feedback, challenge):
    """交叉质询的作答提示词（让这一组**回答**质询主持提出的问题）。

    可见性边界与 build_challenge_prompt 完全一致：自己的全文 + 对方的主张摘要 +
    只属于自己的评委意见。这样"竞争"是真的（有对照物可辩），
    而"抄对方"是不可能的（看不到原文）。
    """
    lines = [
        "质询主持向本组（{}）提出了下面这些问题。请以本组身份逐条作答。".format(team["name"]),
        "",
        "【要回答的问题】",
    ]
    for i, q in enumerate(challenge.get("questions") or [], 1):
        lines.append("  {}. {}（打在：{}）".format(i, q.get("ask"), q.get("targets")))
    if challenge.get("must_answer"):
        lines += ["", "【必须交代清楚的一件事】" + challenge["must_answer"]]
    lines += ["", "【另外两组已经亮出来的主张摘要（**只有摘要，没有原文**）】"]
    if rival_digests:
        for d in rival_digests:
            lines.append("  · {}：{}".format(d["anon"], d["headline"]))
            for c in d["claims"]:
                lines.append("      - {}".format(c))
    else:
        lines.append("  · （没有可对照的摘要）")
    lines += ["", "【评委对**本组**的打分与批评】"]
    for jf in judge_feedback or []:
        lines.append("  · {} 给本组总分 {}：".format(jf["judge_name"], jf["total"]))
        for r in jf["reasons"]:
            lines.append("      - [{}] {} → 要求：{}".format(r["dim_name"], r["why"], r["fix"]))
        if jf.get("veto"):
            lines.append("      - !! 一票否决：{}".format(jf["veto"]))
    lines += [
        "",
        "作答要求：",
        "  · answers 逐条对应上面的问题，`q` 要原样抄问题。",
        "  · why_better 至少 2 条，`than` 必须是上面摘要里**已经出现**的主张；"
        "`why` 要能核对，不许只写「更用心」「更专业」。",
        "  · cannot_beat 要如实说（评委会核对你有没有在硬撑）。",
        "  · 不许出现对方方案的原话（你看不到，写了就是编造）。",
        "",
        _PROMPT_SAMPLE_BLOCK,
        "",
        "===== 任务书开始 =====",
        task or "",
        "===== 任务书结束 =====",
        "",
        "按要求只输出这个 JSON 对象：",
        json.dumps(_ANSWER_SCHEMA, ensure_ascii=False, indent=1),
    ]
    return "\n".join(lines)


AWARD_SYSTEM = (
    "你是「三剪客 · 方案竞标小组」的**裁决人**。\n"
    "你出的是**终裁**：这个名字额只能给一组。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. `winner` 只能填组的 id（{} 之一），不许填显示名。\n"
    "  2. 被评委**一票否决**的组不能判为获胜组。\n"
    "  3. 落选名单必须**逐组**给出 `why_lost`：它输在哪一维度、输在方案的哪一处。"
    "不许写「综合来看稍弱」这类没有落点的话。\n"
    "  4. `merges`（**合并建议**）必须逐条写清：从哪一组拿什么、补进获胜方案的哪一处、"
    "补了之后补上什么缺口。落选方案里有价值的部分不许因为「它输了」就整份丢掉。\n"
    "  5. `score_detail` 必须给出**每个组的每个维度得分**（按公示权重），"
    "不许只给一个总分。\n"
    "  6. 有评委一票否决或持不同意见时，必须逐条写进 `dissent`；"
    "`dissent` 里不许出现不存在的组。\n"
    "  7. 不许写「本方案最好」「效果 100%」这类绝对化表述——"
    "这是内部竞标结论，不是对外广告；用「得分最高」「在该维度上领先」这类可核对的说法。\n"
    "  8. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
).format(" / ".join(TEAM_IDS))

_AWARD_SCHEMA = {
    "winner": "获胜组的 id（{}）".format(" 或 ".join(TEAM_IDS)),
    "why_winner": "它凭什么赢（要落到维度与方案原文上）",
    "winner_quote": "获胜方案里最能说明它该赢的一句话（**原样引用**）",
    "score_detail": [
        {
            "team": "组 id",
            "dims": {"成本": 0, "可行性": 0, "差异化": 0, "风险": 0},
            "total": 0,
            "summary": "这个组在各个维度上的表现（一句话）",
        }
    ],
    "losers": [
        {
            "team": "落选组的 id",
            "why_lost": "它输在哪一维度、输在方案的哪一处（要能核对）",
            "quote": "落选方案里能说明这一点的**原样**一句话",
            "keep": "它方案里仍然值得保留的部分（一句话）",
        }
    ],
    "merges": [
        {
            "from_team": "从哪个落选组拿（组 id）",
            "quote": "那一处**原样**原文",
            "into": "补进获胜方案的哪一处",
            "gain": "补上之后补了什么缺口",
        }
    ],
    "dissent": [{"team": "持不同意见或被否决的组 id", "reason": "原因（原样保留，不许抹平）"}],
    "summary": "两三句总评",
}


def build_award_prompt(task, proposals, panel, answers):
    """裁决提示词：公示维度 + 三份方案 + 评委打分 + 质询与作答，全量摆上桌。"""
    lines = [
        "下面是一场竞标的全部材料：任务书、公示的评分维度与权重、"
        "{} 份方案、评委打分、交叉质询与作答。请出终裁。".format(len(proposals)),
        "",
        "【公示的评分维度与权重（不可改）】",
    ]
    for d in DIMENSIONS:
        lines.append("  · {}（`{}`，权重 {:.2f}）：{}".format(
            d["name"], d["id"], d["weight"], d["what"]))
    lines += [
        "  权重合计 {:.2f}。`score_detail[].total` 必须等于各维度分数按此权重加权的结果。".format(
            RUBRIC_TOTAL_WEIGHT),
        "",
        "【裁决要求】",
        "  · `winner` 填组 id（{}）。".format(" / ".join(TEAM_IDS)),
        "  · 被一票否决的组不能获胜：本次否决情况见下面的评委团结果。",
        "  · 落选组逐个给 `why_lost` + `quote`（原样引文）+ `keep`（仍值得保留的部分）。",
        "  · `merges` 至少 2 条：从落选方案里拿东西补进获胜方案，"
        "写明 `into`（补到哪一处）与 `gain`（补了什么缺口）。",
        "  · `dissent` 必须收录有异议/被否决的组，原样保留理由。",
        "",
        _PROMPT_SAMPLE_BLOCK,
        "",
        "===== 任务书开始 =====",
        task or "",
        "===== 任务书结束 =====",
        "",
    ]
    for t in TEAMS:
        p = next((x for x in proposals if x.get("team") == t["id"]), None)
        if not p:
            continue
        lines += [
            "===== {}（{}）的方案开始 =====".format(t["name"], t["id"]),
            json.dumps(p.get("body") or {}, ensure_ascii=False, indent=1),
            "===== {} 的方案结束 =====".format(t["name"]),
            "",
        ]
    lines += ["===== 评委团结果开始 =====",
              json.dumps(panel.get("judges") or [], ensure_ascii=False, indent=1),
              "===== 评委团结果结束 =====", "",
              "===== 交叉质询与作答开始 =====",
              json.dumps(answers or [], ensure_ascii=False, indent=1),
              "===== 交叉质询与作答结束 =====", "",
              "按要求只输出这个 JSON 对象：",
              json.dumps(_AWARD_SCHEMA, ensure_ascii=False, indent=1)]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class BidError(a7w.A7wError):
    """竞标流程里的所有可预期失败。子类各自带退出码。"""
    exit_code = EXIT_CALL


class UsageError(BidError):
    """参数/配置用错了（文件不存在、组名错、给了 --budget 没给单价、顺序倒置…）。→ 退出码 2"""
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """产出路径落在 Skill 包内（退出码 2）。"""


class OrderError(UsageError):
    """阶段顺序倒了（**未公示评分维度**就打分、没打分就质询…）。退出码 2。

    为什么是 2 而不是 3：顺序倒置是**用法错误**，不是"产出的判定不合格"。
    退出码全族对齐，语义一致，脚本才好分支。
    """


class GateFail(BidError):
    """硬闸门命中（退出码 3）。"""
    exit_code = EXIT_GATE


class BudgetStop(BidError):
    """预算超限，已就地中止（退出码 5）。"""
    exit_code = EXIT_BUDGET


# 最近一次模型调用的 `finish_reason` 与 content 长度。
# **必须记它**：区分"该加大 max_tokens"（`length`）与"模型自己写错了 / 路上断了"
# （`stop` 或 `None`）的**唯一**依据。同族的教训是没记它，于是拿 content 长度去凑解释，
# 把坏 JSON 误归因成"网关在某个固定长度截断"——那个推断是错的（实测 3984 字符
# 也能拿到完整内容，finish_reason='stop'）。
_LAST_FINISH = {"reason": None, "chars": None}


def _json_is_complete(text):
    """文本里有没有一个**括号配平**的 JSON 值（忽略字符串里的括号）。

    只看第一个 `{` / `[` 的配平，且必须配上。用来识别"上游返回的 JSON 坏了"。
    ⚠️ 这是**结构判据**，不是长度判据。配平配上不等于内容对（语法错也可能配上），
    所以它是"便宜的第一道筛"，最终仍要 `json.loads` / `raw_decode` 说了算。
    """
    if not text:
        return False
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    for cand in ([fenced.group(1)] if fenced else []) + [text]:
        start = None
        for i, ch in enumerate(cand):
            if ch in "{[":
                start = i
                break
        if start is None:
            continue
        depth, in_str, esc = 0, False, False
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
                    return True
    return False


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    ⚠️ 本函数**故意不走** `a7w._request`：那边有个 `raw` 参数，是**原始请求体字节**
    （用于 multipart 上传），**不是**"要原始响应"。同族有人把它当成后者用过，
    结果崩在**钱已经扣之后**。本包一律自己发 urllib 请求，语义只有一种，不给误用的机会。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见，
    一次竞标要跑十次调用，被一次抖动打断要重跑整轮，很亏。
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
    attempt = 0
    while attempt < CHAT_RETRIES:
        req = urllib.request.Request(CHAT_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in (502, 503, 504) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("上游 {}，{}s 后重试 {}/{}…\n".format(
                    exc.code, 3 * (attempt + 1), attempt + 1, CHAT_RETRIES - 1))
                attempt += 1
                time.sleep(3 * attempt)
                continue
            try:
                err = json.loads(text)
            except ValueError:
                err = {}
            msg = (err.get("error") or {}).get("message") if isinstance(err.get("error"), dict) else None
            msg = msg or err.get("msg") or text[:200]
            if exc.code == 401:
                raise BidError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise BidError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise BidError("模型不存在（404）：{}  "
                               "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
                attempt += 1
                time.sleep(3 * attempt)
                continue
            raise BidError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                attempt += 1
                time.sleep(3 * attempt)
                continue
            raise BidError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
                getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

        # 网关把 OpenAI 的返回包了一层 {"code":1,"data":{...}}，两种形态都认。
        # ⚠️ 但**成功响应不带 code** —— 别拿 `code` 判成败。
        data_obj = payload
        if (isinstance(payload, dict) and "choices" not in payload
                and isinstance(payload.get("data"), dict)):
            data_obj = payload["data"]
        choices = (data_obj or {}).get("choices") or []
        if not choices:
            raise BidError("模型没返回 choices：{}".format(
                json.dumps(payload, ensure_ascii=False)[:300]))
        content = ((choices[0] or {}).get("message") or {}).get("content") or ""
        finish_reason = (choices[0] or {}).get("finish_reason")
        usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
        _LAST_FINISH["reason"] = finish_reason
        _LAST_FINISH["chars"] = len(content)

        # ⚠️ 上游返回的 JSON **可能是坏的**，而且不只一种坏法：
        #   1. **输出被 max_tokens 截断** —— content 没有正常收尾，`finish_reason == "length"`。
        #   2. **模型偶发吐出语法错的 JSON** —— content 有正常收尾，坏在中间某处；
        #      此时 `finish_reason == "stop"`：上游说它写完了，是它自己写错了。
        #   3. **响应在传输层被切断** —— content 同样没有正常收尾，finish_reason 可能仍是 stop。
        # ❌ **不要用 content 长度判断是哪一种**（实测 3984 字符也能是完整内容）。
        # ✅ 判据是**结构**（能不能按括号配平切出完整顶层值）+ `finish_reason`。
        if json_mode and content and not _json_is_complete(content):
            by_length = (finish_reason == "length")
            hint = ("输出被 max_tokens 截断（finish_reason=length）" if by_length else
                    "上游返回的 JSON 坏了（finish_reason={!r}，**不是长度问题**）"
                    .format(finish_reason))
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("{}（收到 {} 字符），{}s 后重试 {}/{}…\n".format(
                    hint, len(content), 3 * (attempt + 1), attempt + 1, CHAT_RETRIES - 1))
                attempt += 1
                time.sleep(3 * attempt)
                continue
            sys.stderr.write("!! 上游连续 {} 次返回坏 JSON（最后一次 {} 字符，"
                             "finish_reason={!r}）—— {}\n".format(
                                 CHAT_RETRIES, len(content), finish_reason,
                                 "加大 --max-tokens 才管用。" if by_length else
                                 "**加大 --max-tokens 没用**：这是模型写错了或响应在路上"
                                 "断了，换模型重试，或把这一稿拆短分几段跑。"))
        return content, usage
    raise BidError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
        getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    模型经常在合法 JSON 后面多吐几个字符（```、解释、第二个对象、重复的 `}`），
    直接 json.loads 会炸。

    ⚠️ **必须优先返回最外层对象**（同族真机实测踩到的一次，代价是一次调用）：
    外层 JSON **坏掉**时（被截断，或模型吐了语法错），`raw_decode` 在外层的 `{`
    上会抛错，循环继续往后挪，**从 `"claims": [` 里的那个 `{` 解出一条 claim**，
    然后当成"模型的返回"交出去 —— 上层报"返回里没有可用的方案"，
    而真因（外层 JSON 坏了）被这个"成功解出一个对象"盖住了 ——
    **报错指向了错误的方向**，这比坏响应本身更麻烦。
    所以：先按**括号配平**切出第一个完整的顶层值再解；切不出来才退回逐个 `{` 试。
    """
    if not text:
        raise BidError("模型返回空内容")
    dec = json.JSONDecoder()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1).strip())
    candidates.append(text)
    for cand in candidates:
        # 第一优先：括号配平找第一个完整的顶层值（字符串里的括号不计数）
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
        # 兜底：逐个 `{` / `[` 试（处理前后有杂质、括号不配平等形态）
        for i, ch in enumerate(cand):
            if ch not in "{[":
                continue
            try:
                obj, _end = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    # ⚠️ 报错文案**不许**把用户往"加大 max_tokens"上引 —— 那是错的引导。
    fr = _LAST_FINISH.get("reason")
    extra = ("；finish_reason=length（确实被 max_tokens 截断了，加大 --max-tokens 有用）"
             if fr == "length" else
             "；finish_reason={!r} —— **加大 --max-tokens 没用**，"
             "这是模型写错了或响应在路上断了，换模型重试".format(fr))
    raise BidError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), extra))


# ---------------------------------------------------------------------------
# 成本：token 标定 + 预算闸门
#
# 只出 token，**不编金额**：文本模型网关不公布单价（/api/v1/models 里也没有价格字段）。
# 单位统一用「点」（1 元 = 100 点），与全族 16/19 个包一致；
# 帮助串里显式写单位，避免"用户以为单位是元"这类误用。
# 字符 → token 的标定比例（**是全族实测值**，不是厂商文档）：
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN_IN = 1.61     # 输入侧：拿真实调用标定，实测均值 1.612
TOKENS_PER_CHAR_OUT = 1.11    # 输出侧：1 个原始字符 ≈ 多少 token，实测均值 1.109
POINTS_PER_YUAN = 100.0       # 平台口径：1 元 = 100 点

PROPOSE_OUT_TOKENS = 1500     # 单个提案组的 JSON 输出经验值（含主张与风险清单）
JUDGE_OUT_TOKENS = 2400       # 单个评委的输出经验值（三份方案 × 4 个维度 + 理由）
CHALLENGE_OUT_TOKENS = 900    # 质询主持对一组的输出经验值
ANSWER_OUT_TOKENS = 1200      # 一个组的作答经验值
AWARD_OUT_TOKENS = 2000       # 裁决的输出经验值（打分表 + 落选 + 合并建议）


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(text, team_count=3, judge_count=3):
    """一场完整竞标的调用清单（用于报价，越清楚越好）。

    默认规模：3 组提案 + 3 名评委 + 3 次质询 + 3 次作答 + 1 次裁决 = **13 次调用**。
    这不是"多跑几次模型"，而是"三个组各交一份 + 三名评委各打一次 +
    三组各自答辩 + 一次终裁"——少了任何一环，竞争就不成立。
    """
    src_in = estimate_tokens_in(text)
    prop_chars = int(PROPOSE_OUT_TOKENS / TOKENS_PER_CHAR_OUT)
    out = [{
        "stage": "三组独立提案（每组 1 次调用）", "calls": team_count,
        "tokens_in": (src_in + 500) * team_count,
        "tokens_out": PROPOSE_OUT_TOKENS * team_count,
        "note": "每次调用只带本组立场与任务书（信息隔离）：看不到另外两组，也看不到评分维度",
    }]
    judge_in = src_in + prop_chars * team_count + 900
    out.append({
        "stage": "评委团打分（每位评委 1 次调用）", "calls": judge_count,
        "tokens_in": judge_in * judge_count,
        "tokens_out": JUDGE_OUT_TOKENS * judge_count,
        "note": "同一次调用里横向看全部方案（匿名，只有编号），但每份各自独立给分；"
                "每位评委互不可见",
    })
    out.append({
        "stage": "交叉质询（每组 1 次调用，质询主持）", "calls": team_count,
        "tokens_in": (judge_in + prop_chars + 1200) * team_count,
        "tokens_out": CHALLENGE_OUT_TOKENS * team_count,
        "note": "每组只带**自己的全文** + **对方的主张摘要** + **只属于自己的评委意见**",
    })
    out.append({
        "stage": "交叉质询作答（每组 1 次调用）", "calls": team_count,
        "tokens_in": (judge_in + prop_chars + 1500) * team_count,
        "tokens_out": ANSWER_OUT_TOKENS * team_count,
        "note": "每组论证「我为什么比另外两组更该拿到名额」，只能引用对方摘要里的主张",
    })
    out.append({
        "stage": "裁决（1 次调用）", "calls": 1,
        "tokens_in": src_in + judge_in + prop_chars * team_count * 2 + 4000,
        "tokens_out": AWARD_OUT_TOKENS,
        "note": "输入 = 任务书 + 三份方案 + 评委团结果 + 质询与作答；"
                "产出获胜方案 + 落选原因 + 合并建议 + 打分明细",
    })
    return out


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
    """累计真实 usage（token），实时核预算。超了就地停（闸门：成本上限）。

    单位是**点**（1 元 = 100 点），与 --budget 一致。
    """

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
                         "prompt_tokens": p, "completion_tokens": c,
                         "finish_reason": _LAST_FINISH.get("reason"),
                         "content_chars": _LAST_FINISH.get("chars")})

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
            s += " · 金额：网关不公布文本单价，**未折算**（要折算请传 --price-in / --price-out，单位点/百万 token）"
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
            "budget_unit": "点（1 元 = 100 点）",
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
            "本次预计还要约 {} 点。调大 --budget，或减少评委/轮次，或换更短的模型。".format(
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
#   · 组数/评委数没进 key → 参数调了但没生效，用户以为改过了
# 结论：**断点 key 必须含全部影响产出的维度**。
# 本包额外多一个维度：**评分口径版本**（RUBRIC_VERSION）——
# 改了维度或权重，旧产物一律作废，否则会出现"用旧尺子打的分配新尺子的裁决"。
# ---------------------------------------------------------------------------

STATE_NAME = "state.json"
STATE_VERSION = 1

# 自测钩子：任务书里出现这个串就故意抛一个未捕获异常，
# 用来验收「`--json` 下未预料异常 → kind:internal 信封 + 完整 traceback 到 stderr」。
# 放环境变量而不是写死常量：正常运行（没设这个变量）时它是空串，永不可能命中。
_INTERNAL_MARKER = os.environ.get("BIDCREW_INTERNAL_MARKER") or ""


def state_key(stage, source_sha=None, source_chars=None, prompt_chars=None,
              model=None, temperature=None, teams=None, judges=None,
              earlier_sha=None, rubric=RUBRIC_VERSION, prompt=PROMPT_VERSION,
              crew=CREW_VERSION):
    """算一个断点 key：**所有影响产出的维度都在里面**。

    参数逐个都有关联的事故：
      source_sha / source_chars  任务书内容变了必须重跑（摘要防"改了一个字却复用"）
      prompt_chars               实际喂给模型的字符数；截断上限变了必须重跑
      model / temperature        换模型或换温度就是换产出
      teams / judges             换组组合或评委组合 = 换竞争与评判口径
      earlier_sha                复用哪一份上游产物；那份文件变了必须重跑
      rubric / prompt / crew     评分口径版本、提示词版本、班组定义版本
    """
    payload = {
        "v": STATE_VERSION,
        "stage": stage,
        "source_sha": source_sha,
        "source_chars": source_chars,
        "prompt_chars": prompt_chars,
        "model": model,
        "temperature": temperature,
        "teams": list(teams or []),
        "judges": list(judges or []),
        "earlier_sha": earlier_sha,
        "rubric": rubric,
        "prompt": prompt,
        "crew_version": crew,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "{}:{}".format(stage, hashlib.sha256(blob).hexdigest()[:20])


def text_sha(text):
    """任务书内容摘要（先做换行/空白归一，避免"只改了行尾空白"导致无谓重跑）。"""
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
            if isinstance(obj, dict) and isinstance(obj.get("entries"), dict):
                return obj
        except (OSError, ValueError):
            pass
    return {"version": STATE_VERSION, "entries": {}}


def save_state(outdir, state):
    try:
        write_json(state_path(outdir), state)
    except OSError as exc:
        sys.stderr.write("断点文件写不进去（不影响本次产出）：{}\n".format(exc))


def _commit(replay, outdir, state, key, writer):
    """把"写产物 + 标记断点完成"当成一件事提交。

    ⚠️ `--replay` 时**整体跳过**：回放是只读的 —— 不覆盖产物，也不把断点标记成新 key。
    本包真机踩过两次（第二次代价是真金白银），三种坏法都在这里被一次挡住：
      · 只写产物不写 state → 下次续跑 hash 对得上但标记没写，会重跑（花钱）；
      · 只写 state 不写产物 → 下次判定"命中"，读文件却读不到（报错）；
      · 两个都写但 key 变了  → 下次判定不命中，直接去调模型（**真的花了钱**）。
    所以纪律只有一条：**非回放才提交，回放一律不落盘**。
    """
    if replay:
        sys.stderr.write("（回放模式：产物与断点文件都**不写**，本次只读、只算、只打印。）\n")
        return False
    writer()
    if key:
        state.setdefault("entries", {})[key] = "done"
        save_state(outdir, state)
    return True


# ---------------------------------------------------------------------------
# 产出路径：不许进包
#
# 红线：包内只允许 `.md .py .txt .json .sh .js .yaml .yml .csv` 这类文本后缀，
# 包内塞一张 png 会让上传被拒。写文件是**写操作**，写进去之前就要拦住。
# 退出码 2（usage）：这是用法错误，不是闸门判定，也不是上游失败。
# ---------------------------------------------------------------------------

def pkg_dir():
    return Path(__file__).resolve().parent.parent


def ensure_outside_pkg(path, what="输出目录", example="bid-crew-out"):
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
# 任务书整理（**纯本地零成本**）
#
# 为什么不调模型：任务书整理只是把"三组看的是同一份东西"这件事固定下来。
# 大纲、数字、专有名词都能确定性抽出来；多花一次调用不会让它更准，
# 只会让"先看看任务书"这个动作开始花钱。所以这一步一次调用都不发。
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$", re.M)
NUM_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|％|万|亿|千|百|元|块|天|小时|分钟|人|个|条|次|篇|台|单)?")


def _ctx(text, start, end, pad=16):
    return (text or "")[max(0, start - pad):min(len(text or ""), end + pad)].replace("\n", " ")


def extract_numbers(text):
    """抽任务书里的数字（含单位）：竞标里最常被"记错"的就是这类硬信息。"""
    out, seen = [], set()
    for m in NUM_TOKEN_RE.finditer(text or ""):
        raw = m.group(0).strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        out.append({"raw": raw, "context": _ctx(text, m.start(), m.end())})
    return out[:60]


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


TASK_QUESTIONS = [
    "这个名额到底要解决什么问题？",
    "哪些条件是硬约束（预算 / 工期 / 合规），破了就出局？",
    "做成什么样算成功？谁在什么时点判定？",
]


def build_task_brief(text, source_path=None):
    """把任务书整理成结构化材料（纯本地）。"""
    heads = [{"level": len(m.group(1)), "text": m.group(2)} for m in HEADING_RE.finditer(text or "")]
    hits_c, exempted = compliance_scan(text)
    ph = placeholder_hits(text)
    echo, echo_skips = prompt_echo_scan(text, label="任务书")
    return {
        "source": str(source_path) if source_path else None,
        "sha": text_sha(text),
        "chars": char_count(text),
        "sentences": len(split_sentences(text)),
        "paragraphs": len(split_paras(text)),
        "headings": heads,
        "numbers": extract_numbers(text),
        "proper_nouns": extract_proper(text),
        "task_questions": list(TASK_QUESTIONS),
        "local_prescan": {
            "compliance": {"ok": not hits_c, "hits": hits_c, "exempted": exempted},
            "placeholder": {"ok": not ph, "hits": ph},
            "prompt_echo": {"ok": not echo, "hits": echo,
                            "contain_skipped": _dedupe_skips(echo_skips)},
        },
    }


def char_count(text):
    return len(text or "")


def material_meta(text):
    """给提示词用的材料元信息（与 brief 分开，避免每次重算全文）。"""
    t = text or ""
    return {"sha": text_sha(t), "chars": char_count(t),
            "sentences": len(split_sentences(t)), "paragraphs": len(split_paras(t))}


# ---------------------------------------------------------------------------
# 阶段产物归一化与本地校验
# ---------------------------------------------------------------------------

def _clamp(v, lo=0, hi=10):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, x))


def normalize_proposal(raw, team):
    """把一个组的原始返回归一化成方案对象（含锚点准备字段）。

    保留 `raw`：`--replay` 要用它**重跑**本地校验，而不是信任文件里存好的结论
    （否则手工改过的产物就能绕过闸门）。
    """
    raw = raw if isinstance(raw, dict) else {}
    claims = []
    for c in raw.get("claims") or []:
        if isinstance(c, dict):
            text = (c.get("text") or "").strip()
            ev = (c.get("evidence") or "").strip()
        else:
            text, ev = str(c).strip(), ""
        if text:
            claims.append({"text": text, "evidence": ev})
    dels = []
    for d in raw.get("deliverables") or []:
        if isinstance(d, dict):
            s = (d.get("text") or d.get("name") or "").strip()
        else:
            s = str(d).strip()
        if s:
            dels.append(s)
    risks = []
    for r in raw.get("risks") or []:
        if isinstance(r, dict):
            a = (r.get("risk") or "").strip()
            b = (r.get("cover") or "").strip()
            if a or b:
                risks.append({"risk": a, "cover": b})
        else:
            s = str(r).strip()
            if s:
                risks.append({"risk": s, "cover": ""})
    return {
        "team": team["id"],
        "team_name": team["name"],
        "headline": (raw.get("headline") or "").strip(),
        "approach": (raw.get("approach") or "").strip(),
        "claims": claims,
        "deliverables": dels,
        "cost": (raw.get("cost") or "").strip(),
        "timeline": (raw.get("timeline") or "").strip(),
        "differentiation": (raw.get("differentiation") or "").strip(),
        "risks": risks,
        "acceptance": (raw.get("acceptance") or "").strip(),
        "raw": raw,
    }


def normalize_judge(raw, judge, proposals, targets):
    """把一名评委的原始返回归一化：分数夹到 0~10、维度名归一、
    **每条理由的引文锚到被评的那一组自己的方案**（锚不上就剔出并记账）。"""
    raw = raw if isinstance(raw, dict) else {}
    anon_map = {}
    for i, p in enumerate(proposals):
        anon_map[_anon_label(i)] = p["team"]
        anon_map[str(i + 1)] = p["team"]
        anon_map[p["team"]] = p["team"]
        anon_map[p["team_name"]] = p["team"]
        anon_map["方案%s" % (i + 1)] = p["team"]
        anon_map["第%s份" % (i + 1)] = p["team"]
    scores, unanchored, unknown_teams = [], [], []
    seen_teams = set()
    for sc in raw.get("scores") or []:
        if not isinstance(sc, dict):
            continue
        tid = anon_map.get(str(sc.get("team")).strip()) or as_team_id(sc.get("team"))
        if tid is None:
            unknown_teams.append(str(sc.get("team")))
            continue
        seen_teams.add(tid)
        dims_in = sc.get("dims") if isinstance(sc.get("dims"), dict) else {}
        if not dims_in and isinstance(sc.get("dimensions"), dict):
            dims_in = sc["dimensions"]
        dims, dim_missing = {}, []
        for k, v in (dims_in or {}).items():
            did = as_dim_id(k)
            val = _clamp(v)
            if did and val is not None:
                dims[did] = val
        for d in DIMENSIONS:
            if d["id"] not in dims:
                dim_missing.append(d["id"])
        target = targets.get(tid)
        reasons, bad = [], []
        for r in sc.get("reasons") or []:
            if not isinstance(r, dict):
                continue
            did = as_dim_id(r.get("dim"))
            rec = {"dim": did, "raw_dim": r.get("dim"),
                   "quote": (r.get("quote") or "").strip(),
                   "score": _clamp(r.get("score")),
                   "why": (r.get("why") or "").strip(),
                   "fix": (r.get("fix") or "").strip()}
            if target is not None and rec["quote"]:
                ok, rule, no, sent = target.check(rec["quote"])
                rec["anchor"] = {"ok": ok, "rule": rule, "sentence_no": no,
                                 "matched": sent}
                # 关键：引文必须锚到**被评的那一组**。锚到别组 → 记下来。
                other = None
                for oid, ot in targets.items():
                    if oid == tid or ot is None:
                        continue
                    ook, orule, ono, osent = ot.check(rec["quote"])
                    if ook and not ok:
                        other = {"team": oid, "rule": orule, "sentence_no": ono,
                                 "matched": osent}
                        break
                if other:
                    rec["anchor"]["anchored_to_other_team"] = other
            else:
                rec["anchor"] = {"ok": False, "rule": "no_quote", "sentence_no": None,
                                 "matched": ""}
            if not rec["anchor"].get("ok"):
                rec["unanchored_reason"] = (
                    "引文在该组方案里找不到"
                    + ("，但在「{}」的方案里找到了——把别组的原话挂到了这组头上"
                       .format(TEAM_NAME.get((rec["anchor"].get("anchored_to_other_team")
                                              or {}).get("team"), "?"))
                       if rec["anchor"].get("anchored_to_other_team") else ""))
                bad.append(rec)
            reasons.append(rec)
        total, tmissing = weighted_total(dims)
        scores.append({
            "team": tid, "dims": dims, "dims_missing": dim_missing,
            "reasons": reasons, "unanchored_reasons": bad,
            "total": total, "total_missing_dims": tmissing,
            "total_self_reported": _clamp(sc.get("total")),
            "conclusion": (sc.get("conclusion") or "").strip(),
        })
        unanchored.extend(bad)
    missing_teams = [p["team"] for p in proposals if p["team"] not in seen_teams]
    vetoes = []
    for v in raw.get("vetoes") or []:
        if not isinstance(v, dict):
            continue
        tid = anon_map.get(str(v.get("team")).strip()) or as_team_id(v.get("team"))
        if tid is None:
            unknown_teams.append(str(v.get("team")))
            continue
        rec = {"team": tid, "reason": (v.get("reason") or "").strip(),
               "quote": (v.get("quote") or "").strip(),
               "judge_has_veto_power": bool(judge.get("veto_power"))}
        target = targets.get(tid)
        if target is not None and rec["quote"]:
            ok, rule, no, sent = target.check(rec["quote"])
            rec["anchor"] = {"ok": ok, "rule": rule, "sentence_no": no, "matched": sent}
        else:
            rec["anchor"] = {"ok": False, "rule": "no_quote", "sentence_no": None,
                             "matched": ""}
        if not judge.get("veto_power"):
            rec["not_counted_reason"] = ("该评委没有否决权（只有风险与合规评委有），"
                                        "这条 veto 不计入否决名单，但原样保留在案")
        elif not rec["reason"]:
            rec["not_counted_reason"] = "否决没给理由，不计入否决名单"
        elif not rec["anchor"].get("ok"):
            rec["not_counted_reason"] = "否决没锚到该组方案原文，不计入否决名单"
        vetoes.append(rec)
    effective_vetoes = [v for v in vetoes if not v.get("not_counted_reason")]
    return {
        "judge": judge["id"], "judge_name": judge["name"], "focus": judge["focus"],
        "veto_power": bool(judge.get("veto_power")),
        "scores": scores, "vetoes": vetoes, "effective_vetoes": effective_vetoes,
        "missing_teams": missing_teams, "unknown_teams": unknown_teams,
        "unanchored_reasons": unanchored,
        "summary": (raw.get("summary") or "").strip(),
        "raw": raw,
    }


def anchor_stat_for(records, total_key="total"):
    """把一堆 True/False（或带 anchor 的记录）汇总成锚点统计。"""
    vals = []
    for r in records or []:
        if isinstance(r, bool):
            vals.append(r)
        elif isinstance(r, dict):
            vals.append(bool((r.get("anchor") or {}).get("ok")))
    total = len(vals)
    ok = sum(1 for v in vals if v)
    miss = total - ok
    rate = (miss / float(total)) if total else 0.0
    return {"total": total, "anchored": ok, "unanchored": miss,
            "miss_rate": round(rate, 3), "ok": total == 0 or rate <= ANCHOR_MAX_MISS,
            "threshold": ANCHOR_MAX_MISS}


def validate_panel(raw, judges, proposals, targets):
    """归一化评委团结果，并算出**本地票表**（不采信模型自报的加权总分）。"""
    raw = raw if isinstance(raw, dict) else {}
    by_judge = {}
    for j in (raw.get("judges") or []):
        if not isinstance(j, dict):
            continue
        jid = as_judge_id(j.get("judge") or j.get("judge_id") or j.get("id"))
        if jid:
            by_judge[jid] = j
    out_judges, missing_judges = [], []
    for j in judges:
        if j["id"] in by_judge:
            out_judges.append(normalize_judge(by_judge[j["id"]], j, proposals, targets))
        else:
            missing_judges.append(j["id"])
    # 本地票表：按公示权重重算每个评委给每组的总分，再跨评委取均值
    per_team = {}
    for jr in out_judges:
        for sc in jr["scores"]:
            per_team.setdefault(sc["team"], []).append(sc["total"])
    score_detail = []
    for t in TEAM_IDS:
        vals = [v for v in per_team.get(t, []) if isinstance(v, (int, float))]
        avg = round(sum(vals) / float(len(vals)), 3) if vals else None
        dims_avg = {}
        for d in DIMENSIONS:
            ds = []
            for jr in out_judges:
                for sc in jr["scores"]:
                    if sc["team"] == t and sc["dims"].get(d["id"]) is not None:
                        ds.append(sc["dims"][d["id"]])
            dims_avg[d["id"]] = round(sum(ds) / float(len(ds)), 3) if ds else None
        score_detail.append({"team": t, "team_name": TEAM_NAME[t],
                             "dims": dims_avg, "total": avg,
                             "judges_scored": len(vals)})
    vetoed = {}
    for jr in out_judges:
        for v in jr["effective_vetoes"]:
            vetoed.setdefault(v["team"], []).append(
                {"judge": jr["judge"], "judge_name": jr["judge_name"], "reason": v["reason"]})
    ranking = [x["team"] for x in sorted(
        [x for x in score_detail if x["total"] is not None], key=lambda x: -x["total"])]
    unanchored = []
    for jr in out_judges:
        unanchored.extend(jr["unanchored_reasons"])
    return {
        "judges": out_judges, "missing_judges": missing_judges,
        "score_detail": score_detail, "local_ranking": ranking,
        "vetoed": vetoed,
        # ⚠️ 这份清单必须**返回出去**：闸门四要拿它算未锚定率。
        # 同族踩过一次「函数里算了、忘了返回」，结果闸门恒过、看起来还在跑。
        "unanchored_reasons": unanchored,
        "anchor": anchor_stat_for(unanchored),
        "raw": raw,
    }


def validate_award(raw, proposals, panel, targets=None):
    """归一化裁决（组名归一 + 引文锚点 + 本地重算打分明细）。

    ⚠️ `targets` 必须由调用方传进来（或在这里由 proposals 现算）。
    同族踩过一次：函数里写了一个空 dict 当 targets，于是**所有引文都判未锚定**——
    本地校验看起来在跑，实际永远失败。这类"闸门看起来生效了"的错最难查。
    """
    raw = raw if isinstance(raw, dict) else {}
    targets = targets if targets is not None else targets_for(proposals)
    winner = as_team_id(raw.get("winner"))
    detail, unanchored = [], []
    for x in raw.get("score_detail") or []:
        if not isinstance(x, dict):
            continue
        tid = as_team_id(x.get("team"))
        if tid is None:
            continue
        dims_in = x.get("dims") if isinstance(x.get("dims"), dict) else {}
        dims = {}
        for k, v in (dims_in or {}).items():
            did = as_dim_id(k)
            val = _clamp(v)
            if did and val is not None:
                dims[did] = val
        total, tmissing = weighted_total(dims)
        self_total = _clamp(x.get("total"))
        detail.append({"team": tid, "dims": dims, "dims_missing": tmissing,
                       "total": total, "total_self_reported": self_total,
                       "total_mismatch": (
                           None if self_total is None else round(abs((self_total or 0) - total), 3)),
                       "summary": (x.get("summary") or "").strip()})
    losers = []
    for x in raw.get("losers") or []:
        if not isinstance(x, dict):
            continue
        tid = as_team_id(x.get("team"))
        rec = {"team": tid, "raw_team": x.get("team"),
               "why_lost": (x.get("why_lost") or "").strip(),
               "quote": (x.get("quote") or "").strip(),
               "keep": (x.get("keep") or "").strip()}
        t = targets.get(tid) if tid else None
        if t is not None and rec["quote"]:
            ok, rule, no, sent = t.check(rec["quote"])
            rec["anchor"] = {"ok": ok, "rule": rule, "sentence_no": no, "matched": sent}
        else:
            rec["anchor"] = {"ok": False, "rule": "no_quote", "sentence_no": None,
                             "matched": ""}
        if not rec["anchor"]["ok"]:
            rec["unanchored_reason"] = "落选原因引用的句子在该组方案里找不到"
            unanchored.append(rec)
        losers.append(rec)
    merges = []
    for x in raw.get("merges") or []:
        if not isinstance(x, dict):
            continue
        tid = as_team_id(x.get("from_team") or x.get("from"))
        rec = {"from_team": tid, "raw_from": x.get("from_team"),
               "quote": (x.get("quote") or "").strip(),
               "into": (x.get("into") or "").strip(),
               "gain": (x.get("gain") or "").strip()}
        t = targets.get(tid) if tid else None
        if t is not None and rec["quote"]:
            ok, rule, no, sent = t.check(rec["quote"])
            rec["anchor"] = {"ok": ok, "rule": rule, "sentence_no": no, "matched": sent}
        else:
            rec["anchor"] = {"ok": False, "rule": "no_quote", "sentence_no": None,
                             "matched": ""}
        if not rec["anchor"]["ok"]:
            rec["unanchored_reason"] = "合并建议引用的句子在来源组方案里找不到"
            unanchored.append(rec)
        merges.append(rec)
    dissent = []
    for x in raw.get("dissent") or []:
        if not isinstance(x, dict):
            continue
        dissent.append({"team": as_team_id(x.get("team")), "raw_team": x.get("team"),
                        "reason": (x.get("reason") or "").strip()})
    out = {
        "winner": winner, "winner_display": TEAM_NAME.get(winner) if winner else None,
        "why_winner": (raw.get("why_winner") or "").strip(),
        "winner_quote": (raw.get("winner_quote") or "").strip(),
        "score_detail": detail, "losers": losers, "merges": merges,
        "dissent": dissent, "summary": (raw.get("summary") or "").strip(),
        "raw": raw,
    }
    if winner and out["winner_quote"]:
        ok, rule, no, sent = targets[winner].check(out["winner_quote"])
        out["winner_anchor"] = {"ok": ok, "rule": rule, "sentence_no": no, "matched": sent}
        if not ok:
            out["winner_anchor"]["unanchored_reason"] = "获胜理由引用的句子在获胜方案里找不到"
            unanchored.append(out)
    else:
        out["winner_anchor"] = {"ok": False, "rule": "no_quote", "sentence_no": None,
                                "matched": ""}
        if winner:
            unanchored.append(out)
    merge_detail = {}
    for x in detail:
        merge_detail[x["team"]] = x["total"]
    # ⚠️ 这里**不许**把评委团的打分表搬过来冒充"裁决自带的打分明细"。
    # 题面把「判了获胜却没有打分明细」列为硬闸门，如果本地拿评委表补齐，
    # 那道闸门就永远不可能命中——闸门看起来在跑，实际被自己圆过去了。
    out["anchor"] = anchor_stat_for(unanchored)
    out["total_by_team_local_award"] = merge_detail
    return out


def targets_for(proposals):
    """为每个组建一个 AnchorTarget（引文只能锚到对应那一组的方案，不许跨组）。"""
    targets = {}
    for p in proposals or []:
        if isinstance(p, dict) and p.get("team"):
            targets[p["team"]] = AnchorTarget(p["team"], TEAM_NAME.get(p["team"], p["team"]),
                                              proposal_own_text(p))
    return targets


def proposal_digest(p):
    """一个组的**主张摘要**（交叉质询时给对方看的唯一东西）。

    只含 headline + claims[].text —— **不含原文、不含交付细节、不含成本工期**。
    这是题面写死的规则：质询时"看不到对方的原文，只能看到对方的主张摘要"。
    """
    return {
        "team": p.get("team"),
        "headline": (p.get("headline") or "").strip(),
        "claims": [(c.get("text") or "").strip() for c in (p.get("claims") or [])][:8],
    }


def output_prose(proposals, panel, challenges, award):
    """把全部竞标文书拼成一段话，供产出侧闸门扫（合规 / 占位符 / 照抄示例）。"""
    parts = []
    for p in proposals or []:
        parts.append(proposal_own_text(p))
        parts.append(json.dumps(p.get("body") or p.get("raw") or {}, ensure_ascii=False))
    for jr in (panel or {}).get("judges") or []:
        parts.append(jr.get("summary") or "")
        for sc in jr.get("scores") or []:
            parts.append(sc.get("conclusion") or "")
            for r in sc.get("reasons") or []:
                parts.extend([r.get("why") or "", r.get("fix") or ""])
        for v in jr.get("vetoes") or []:
            parts.append(v.get("reason") or "")
    for c in challenges or []:
        parts.append(json.dumps(c.get("digests") or [], ensure_ascii=False))
        for q in (c.get("challenge") or {}).get("questions") or []:
            parts.extend([q.get("ask") or "", q.get("targets") or "", q.get("why_hard") or ""])
        for a in (c.get("answer") or {}).get("answers") or []:
            parts.extend([a.get("a") or "", a.get("evidence") or "", a.get("concede") or ""])
        for w in (c.get("answer") or {}).get("why_better") or []:
            parts.extend([w.get("point") or "", w.get("why") or ""])
    aw = award or {}
    parts.extend([aw.get("why_winner") or "", aw.get("summary") or ""])
    for x in aw.get("score_detail") or []:
        parts.append(x.get("summary") or "")
    for x in aw.get("losers") or []:
        parts.extend([x.get("why_lost") or "", x.get("keep") or ""])
    for x in aw.get("merges") or []:
        parts.extend([x.get("into") or "", x.get("gain") or ""])
    for x in aw.get("dissent") or []:
        parts.append(x.get("reason") or "")
    return "\n".join(x for x in parts if x)


# ---------------------------------------------------------------------------
# 闸门汇总（八道本地硬闸门）
#
#   1 合规（任务书侧 + 产出侧分开口径）      5 提案独立性（本包核心）
#   2 占位符残留                              6 裁决完整性
#   3 prompt_echo                             7 成本上限
#   4 打分锚点                                8 产出不许进包
# 命中一律：**标红 + stderr 汇总 + 非 0 退出码**，全部确定性，跑两次结果一样，可直接进 CI。
# ---------------------------------------------------------------------------

def evaluate_gates(task, proposals, panel, challenges, award, need):
    """跑全部本地闸门，返回结构化结论。

    `need` 说明本次跑的阶段需要哪些产物（子命令不同，闸门的适用面不同）：
    propose 阶段还没有评委结果，就不该拿"裁决完整性"去拦它。
    """
    hits_c, exempted = compliance_scan(task)
    task_ph = placeholder_hits(task)
    prose = output_prose(proposals, panel, challenges, award)
    out_ph = placeholder_hits(prose)
    out_fresh, out_quoted, out_mentioned, out_contextual, out_exempted = \
        compliance_scan_output(prose, task)
    out_echo, out_echo_skips = prompt_echo_scan(prose, label="产出")
    out_echo_skips = _dedupe_skips(out_echo_skips)

    gates = {
        "compliance": {"ok": not hits_c, "target": "任务书", "hits": hits_c,
                       "exempted": exempted},
        "placeholder": {"ok": not task_ph, "target": "任务书", "hits": task_ph},
        "output_compliance": {"ok": not out_fresh, "target": "方案 / 打分理由 / 质询 / 裁决",
                              "hits": out_fresh, "quoted_from_task": out_quoted,
                              "mentioned_as_warning": out_mentioned,
                              "contextual_only": out_contextual, "exempted": out_exempted,
                              "rule": ("产出侧只查高风险条目，并排除两类正常写法："
                                       "任务书里已有的词（引用被竞标对象）与"
                                       "小句里带禁止/举证/风险标记词的（提到而非主张）；"
                                       "中低风险项列在 contextual_only 里提示人工看，不拦")},
        "output_placeholder": {"ok": not out_ph, "target": "方案 / 打分理由 / 质询 / 裁决",
                               "hits": out_ph},
        "prompt_echo": {"ok": not out_echo, "target": "方案 / 打分理由 / 质询 / 裁决",
                        "hits": out_echo, "contain_skipped": out_echo_skips,
                        "window": {"max_ratio": ECHO_CONTAIN_MAX_RATIO,
                                   "min_sample": ECHO_CONTAIN_MIN_SAMPLE,
                                   "floor": ECHO_MIN_LEN_FLOOR}},
    }

    # ---- 闸门四：打分锚点（只在有评委结果时判）----
    if need.get("panel"):
        anchor = (panel or {}).get("anchor") or anchor_stat_for([])
        # ⚠️ 变量名不能叫 `recs`：上面闸门二/三已经用过 `recs` 记账，重名会把这份清单覆盖掉，
        # 结果就是"未锚定 0 条、闸门恒过"——闸门看起来在跑，实际失效。同族踩过同类坑。
        unanchored_reasons = list((panel or {}).get("unanchored_reasons") or [])
        # 每个评委的每条理由都算一条样本：**已锚定的也要计入**，否则未锚定率的分母就错了。
        total = 0
        for jr in (panel or {}).get("judges") or []:
            for sc in jr.get("scores") or []:
                total += len(sc.get("reasons") or [])
        anchor = dict(anchor)
        miss = len(unanchored_reasons)
        anchor["ok"] = (total == 0) or (miss / float(total) <= ANCHOR_MAX_MISS)
        anchor["unanchored"] = miss
        anchor["total"] = total
        anchor["anchored"] = max(0, total - miss)
        anchor["miss_rate"] = round(miss / float(total), 3) if total else 0.0
        if not anchor["ok"]:
            anchor["why"] = ("{} 条打分理由里 {} 条在对应组的方案里找不到"
                             "（未锚定率 {:.0%} > {:.0%}）——"
                             "理由没有落到方案原文上，这份打分不可复核".format(
                                 anchor["total"], anchor["unanchored"],
                                 anchor["miss_rate"], ANCHOR_MAX_MISS))
        gates["anchor"] = anchor

    # ---- 闸门五：提案独立性（本包核心；有 >=2 份方案就判）----
    if len(proposals or []) >= 2:
        indep = independence_check(proposals)
        problems, red = [], []
        for p in indep["overlap_pairs"]:
            problems.append(
                "「{}」与「{}」的方案重合度 {:.2f} ≥ {:.2f}（短的一份 {} 个二元组）——"
                "**假竞争**：三组交的是同一份东西的三种说法，"
                "竞争没有发生，打分排序与合并建议都失去意义".format(
                    p["a"], p["b"], p["overlap"], INDEP_OVERLAP, p["min_grams"]))
        for p in indep["red_pairs"]:
            red.append("「{}」与「{}」的方案重合度 {:.2f}（阈值 {:.2f}）——"
                       "两边写得太像，建议人工看一眼".format(
                           p["a"], p["b"], p["overlap"], INDEP_OVERLAP))
        for t in indep["thin_own_words"]:
            red.append("「{}」自己的话太少（{} 个二元组 < {}）——"
                       "方案可能只有通用套话，没有本组立场".format(
                           t["team"], t["own_grams"], INDEP_MIN_OWN_GRAMS))
        gates["independence"] = {
            "ok": not problems, "problems": problems, "red_hints": red,
            "red": bool(problems) or bool(red),
            "overlap_threshold": INDEP_OVERLAP, "min_grams": INDEP_MIN_GRAMS,
            "max_overlap": indep["max_overlap"], "pairs": indep["pairs"],
            "lengths": indep["lengths"], "text_basis": indep["text_basis"],
        }

    # ---- 闸门六：裁决完整性（只在有裁决时判）----
    if need.get("award"):
        ok, problems, audit = award_gate(award, proposals, panel)
        gates["award"] = {"ok": ok, "problems": problems,
                          "winner": (award or {}).get("winner"),
                          "losers": len((award or {}).get("losers") or []),
                          "merges": len((award or {}).get("merges") or []),
                          "score_detail": len((award or {}).get("score_detail") or []),
                          "audit": audit}
        # 裁决引文也计入锚点闸门
        aw_anchor = (award or {}).get("anchor") or {}
        if gates.get("anchor") and aw_anchor.get("total"):
            extra_total = aw_anchor.get("total") or 0
            extra_miss = aw_anchor.get("unanchored") or 0
            tot = gates["anchor"]["total"] + extra_total
            miss = gates["anchor"]["unanchored"] + extra_miss
            gates["anchor"]["total"] = tot
            gates["anchor"]["unanchored"] = miss
            gates["anchor"]["miss_rate"] = round(miss / float(tot), 3) if tot else 0.0
            gates["anchor"]["award_quotes"] = {"total": extra_total, "unanchored": extra_miss}
            if tot and gates["anchor"]["miss_rate"] > ANCHOR_MAX_MISS:
                gates["anchor"]["ok"] = False
                gates["anchor"]["why"] = (
                    "{} 条引文（含裁决）里 {} 条在对应方案里找不到（未锚定率 {:.0%} > {:.0%}）——"
                    "结论没有落到方案原文上".format(tot, miss, gates["anchor"]["miss_rate"],
                                                    ANCHOR_MAX_MISS))
    return gates


HARD_GATE_KEYS = ("compliance", "placeholder", "output_compliance", "output_placeholder",
                  "prompt_echo", "anchor", "independence", "award")


def gate_failed(gates):
    for k in HARD_GATE_KEYS:
        v = gates.get(k)
        if v and not v.get("ok", True):
            return True
    return False


def gate_summary_lines(gates, panel=None):
    """给 stderr 的汇总行（闸门命中一律汇总，别让人去翻 JSON）。

    `panel` 是为了**点名跨组引用**（分数没到硬阈值时也要提示的那一类）。
    ⚠️ 别在这里引用外层的同名变量：这个函数只认参数，不认闭包。
    """
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
        elif k == "independence":
            for p in (v.get("problems") or [])[:4]:
                lines.append("[independence] " + p)
        elif k == "award":
            for p in (v.get("problems") or [])[:6]:
                lines.append("[award] " + p)
    # 跨组引用**单独汇总**，不受锚点闸门过没过的影响：
    # 这是评委最容易犯、也最容易蒙混过去的错（把别组的原话挂到这组头上），
    # 未锚定率没到硬阈值时也要点名出来让人看见。
    for jr in (panel or {}).get("judges") or []:
        flagged = {}
        for sc in jr.get("scores") or []:
            for r in (sc.get("reasons") or []):
                if (r.get("anchor") or {}).get("anchored_to_other_team"):
                    tid = sc.get("team")
                    flagged[tid] = flagged.get(tid, 0) + 1
        for tid, cnt in sorted(flagged.items()):
            lines.append("[anchor·跨组] {} 有 {} 条打分理由引了别组的原话"
                         "（已剔出并计入未锚定率；未到硬阈值时只提示不拦）".format(tid, cnt))
    return lines


# ---------------------------------------------------------------------------
# 渲染（人读文本）
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "✗ " + s
    return "\x1b[31m{}\x1b[0m".format(s)


def render_roles_md():
    out = ["# 三剪客 · 方案竞标小组：四个参与者",
           "",
           "> 本包是 **L3（多智能体协作型）· 竞争式**：三个提案组抢同一个名额，",
           "> 评委团按**提案前已公示**的维度打分，质询主持逼出差异，裁决人出终裁。",
           "> 与「对抗评审式」的区别：那边**审一份已有材料**（没有胜负），"
           "本包**选一份方案**（有胜负、有落选原因、有合并建议）。",
           ""]
    out.append("## 提案组（{} 个，**信息互相隔离**）".format(len(TEAMS)))
    out.append("")
    for t in TEAMS:
        out.append("### {}（`{}`）".format(t["label"], t["id"]))
        out.append("")
        out.append("- **取胜路线**：{}".format(t["route"]))
        out.append("- **打法（天然倾向）**：{}".format(t["bias"]))
        out.append("- **方案视角**：{}".format(t["question"]))
        out.append("- **最不能让步的一点**：{}".format(t["must_have"]))
        out.append("- **为了赢肯牺牲**：{}".format(t["give_up"]))
        out.append("- **盯的点**：")
        for x in t["focus"]:
            out.append("  - {}".format(x))
        out.append("")
    out.append("## 评委团（{} 席，不同侧重）".format(len(JUDGES)))
    out.append("")
    out.append("| 评委 | 侧重 | 否决权 |")
    out.append("|---|---|---|")
    for j in JUDGES:
        out.append("| **{}**（`{}`） | {} | {} |".format(
            j["name"], j["id"], j["focus"], "**有一票否决**" if j["veto_power"] else "无"))
    out.append("")
    for j in JUDGES:
        out.append("- **{}**：{}".format(j["name"], j["question"]))
        out.append("  - 风格：{}".format(j["style"]))
    out.append("")
    out.append("## 质询主持 / 裁决人")
    out.append("")
    out.append("- **质询主持**：手里只有每组提交的**主张摘要**（没有对方原文），"
               "逐组问出「你凭什么比另外两组更该拿到名额」。产出质询记录。")
    out.append("- **裁决人**：出终裁——获胜组 + 落选原因 + **合并建议**（落选方案的可用部分）"
               "+ 打分明细。产出裁决书。")
    out.append("")
    out.append("## 三组为什么会真的争起来")
    out.append("")
    out.append("| 场景 | 一组要 | 另一组正好在争 |")
    out.append("|---|---|---|")
    out.append("| 压成本 | A 组把链路砍到只剩主干 | B 组说砍掉的那一环正是差异化的来源 |")
    out.append("| 造差异 | B 组砸钱做别人抄不走的东西 | C 组说这条链路没有兜底、翻车就全废 |")
    out.append("| 求稳妥 | C 组给每一步加兜底与验收口径 | A 组说这些兜底就是纯消耗，预算翻倍 |")
    out.append("| 抢工期 | A 组报三天跑通主干 | C 组说三天跑通的版本没有验收口径，等于没交付 |")
    out.append("")
    out.append("零成本命令：`run.py roles`")
    return "\n".join(out)


def render_rubric_md(rubric):
    out = ["# 公示：评分维度与权重（**提案之前就已定死**）",
           "",
           "> 本表由 `rubric` 子命令公示并存档。**顺序不能倒**：",
           "> 没跑过 `rubric` 就 `score` → 退出码 2。",
           "> 理由：维度若在看到方案之后才定，评委就是在**为已经写出来的东西找尺子**——",
           "> 那是「打分」，不是「竞标」。",
           "",
           "| 维度 | id | 权重 |"]
    out.append("|---|---|---|")
    for d in DIMENSIONS:
        out.append("| **{}** | `{}` | {:.2f} |".format(d["name"], d["id"], d["weight"]))
    out.append("")
    out.append("权重合计 **{:.2f}**。总分 = 各维度分数 × 上述权重，逐项相加（0~10）。".format(
        RUBRIC_TOTAL_WEIGHT))
    out.append("")
    for d in DIMENSIONS:
        out.append("## {}（权重 {:.2f}）".format(d["name"], d["weight"]))
        out.append("")
        out.append("- **评什么**：{}".format(d["what"]))
        out.append("- **10 分的样子**：{}".format(d["full"]))
        out.append("- **0 分的样子**：{}".format(d["zero"]))
        out.append("")
    out.append("## 口径版本")
    out.append("")
    out.append("- 评分口径：`{}`".format(RUBRIC_VERSION))
    out.append("- 提示词版本：`{}`".format(PROMPT_VERSION))
    out.append("- 班组定义版本：`{}`".format(CREW_VERSION))
    out.append("")
    out.append("> 维度与权重是**代码里的常量**，不是让模型现编的："
               "竞标的公正性全押在「尺子先定」上。改了维度必须同时改口径版本号，"
               "否则断点续跑会把旧尺子打的分配上新尺子的裁决。")
    out.append("")
    out.append("零成本命令：`run.py rubric --file 任务书.md --outdir <包外目录>`")
    return "\n".join(out)


def render_proposals_md(proposals, isolation=None):
    out = ["# 三组提案（**互相隔离**：每组只看到任务书与本组立场）", ""]
    for p in proposals:
        t = TEAM_BY_ID.get(p.get("team")) or {}
        out.append("## {}（`{}`）".format(p.get("team_name") or p.get("team"), p.get("team")))
        out.append("")
        out.append("- **一句话**：{}".format(p.get("headline") or "（空）"))
        out.append("- **做法**：{}".format(p.get("approach") or "（空）"))
        if p.get("claims"):
            out.append("- **主张与依据**：")
            for c in p["claims"]:
                out.append("  - {}（依据：{}）".format(
                    c.get("text"), c.get("evidence") or "未给"))
        if p.get("deliverables"):
            out.append("- **交付物**：")
            for d in p["deliverables"]:
                out.append("  - {}".format(d))
        out.append("- **成本**：{}".format(p.get("cost") or "（空）"))
        out.append("- **工期与人天**：{}".format(p.get("timeline") or "（空）"))
        out.append("- **差异化**：{}".format(p.get("differentiation") or "（空）"))
        if p.get("risks"):
            out.append("- **风险与兜底**：")
            for r in p["risks"]:
                out.append("  - {} → {}".format(r.get("risk"), r.get("cover") or "未给兜底"))
        out.append("- **验收口径**：{}".format(p.get("acceptance") or "（空）"))
        if t.get("must_have"):
            out.append("")
            out.append("  > 本组最不能让步的一点：{}".format(t["must_have"]))
        out.append("")
    if isolation:
        out.append("## 信息隔离证据")
        out.append("")
        out.append("```json")
        out.append(json.dumps(isolation, ensure_ascii=False, indent=1)[:4000])
        out.append("```")
    return "\n".join(out)


def render_panel_md(panel):
    out = ["# 评委团打分表", "",
           "> 三名评委各是一次独立调用，按**公示维度与权重**打分。",
           "> 每条理由都锚到被评那一组的方案原文（本地校验）。", ""]
    out.append("| 组 | {}".format(" | ".join(
        "{}（{:.2f}）".format(d["name"], d["weight"]) for d in DIMENSIONS)))
    out.append("|---|" + "---|" * (len(DIMENSIONS) + 1) )
    for x in panel.get("score_detail") or []:
        cells = []
        for d in DIMENSIONS:
            v = (x.get("dims") or {}).get(d["id"])
            cells.append("-" if v is None else "{:g}".format(v))
        out.append("| **{}** | {} | **{:g}** |".format(
            x.get("team_name") or x.get("team"), " | ".join(cells),
            x.get("total") if x.get("total") is not None else 0))
    out.append("")
    out.append("本地排名（按公示权重重算总分）：{}".format(
        " > ".join(panel.get("local_ranking") or []) or "（无）"))
    if panel.get("vetoed"):
        out.append("")
        out.append("## 一票否决")
        out.append("")
        for tid, vs in (panel.get("vetoed") or {}).items():
            for v in vs:
                out.append("- **{}** 被 {} 否决：{}".format(
                    TEAM_NAME.get(tid, tid), v.get("judge_name"), v.get("reason")))
    out.append("")
    for jr in panel.get("judges") or []:
        out.append("## {}（`{}`）".format(jr.get("judge_name"), jr.get("judge")))
        out.append("")
        if jr.get("summary"):
            out.append(jr["summary"])
            out.append("")
        for sc in jr.get("scores") or []:
            out.append("### {} · 总分 {}{}".format(
                TEAM_NAME.get(sc.get("team"), sc.get("team")),
                sc.get("total"), "（缺维度：{}）".format(
                    "、".join(sc.get("dims_missing") or [])) if sc.get("dims_missing") else ""))
            out.append("")
            if sc.get("conclusion"):
                out.append("总评：{}".format(sc["conclusion"]))
                out.append("")
            for r in sc.get("reasons") or []:
                a = r.get("anchor") or {}
                mark = "✓" if a.get("ok") else "✗"
                out.append("- **{}**（{} 分，引文 {} {}）".format(
                    DIM_NAME.get(r.get("dim")) or r.get("raw_dim") or "?",
                    "-" if r.get("score") is None else "{:g}".format(r["score"]),
                    mark, a.get("rule")))
                if r.get("quote"):
                    out.append("  - 引文：{}".format(r["quote"]))
                if a.get("matched") and a.get("matched") != r.get("quote"):
                    out.append("  - 实际锚到：{}".format(a["matched"]))
                out.append("  - 为什么：{}".format(r.get("why") or "（空）"))
                out.append("  - 要做到更高分：{}".format(r.get("fix") or "（空）"))
                if r.get("unanchored_reason"):
                    out.append("  - {}".format(_red(r["unanchored_reason"])))
            out.append("")
        for v in jr.get("vetoes") or []:
            flag = "（生效）" if not v.get("not_counted_reason") else "（不计入：{}）".format(
                v.get("not_counted_reason"))
            out.append("- 否决 {} {}".format(TEAM_NAME.get(v.get("team"), v.get("team")), flag))
            out.append("  - 理由：{}".format(v.get("reason") or "（空）"))
        out.append("")
    out.append("## 锚点统计")
    out.append("")
    a = panel.get("anchor") or {}
    out.append("- 打分理由共 {} 条，未锚定 {} 条（{:.0%}，阈值 {:.0%}）".format(
        a.get("total", 0), a.get("unanchored", 0), a.get("miss_rate", 0.0),
        a.get("threshold", ANCHOR_MAX_MISS)))
    return "\n".join(out)


def render_challenge_md(challenges):
    out = ["# 交叉质询记录", "",
           "> **可见性规则**：每一组只拿到「自己的全文 + 对方的主张摘要 + 只属于自己的评委意见」。",
           "> 对方原文与对方收到的批评一律不给 —— 这是「竞争」与「互相抄」的分界线。", ""]
    for c in challenges or []:
        t = TEAM_BY_ID.get(c.get("team")) or {}
        out.append("## {}（`{}`）".format(t.get("name", c.get("team")), c.get("team")))
        out.append("")
        out.append("### 它从摘要里看到的对方主张")
        out.append("")
        for d in c.get("digests") or []:
            out.append("- **{}**：{}".format(d.get("anon"), d.get("headline") or "（空）"))
            for cl in d.get("claims") or []:
                out.append("  - {}".format(cl))
        out.append("")
        ch = c.get("challenge") or {}
        out.append("### 质询主持提出的问题")
        out.append("")
        for i, q in enumerate(ch.get("questions") or [], 1):
            out.append("{}. **{}**".format(i, q.get("ask")))
            out.append("   - 打在哪一点：{}".format(q.get("targets") or "（空）"))
            out.append("   - 为什么必须回答：{}".format(q.get("why_hard") or "（空）"))
        if ch.get("must_answer"):
            out.append("")
            out.append("必须交代清楚的一件事：{}".format(ch["must_answer"]))
        out.append("")
        an = c.get("answer") or {}
        out.append("### 本组作答")
        out.append("")
        for a in an.get("answers") or []:
            out.append("- **问**：{}".format(a.get("q") or "（空）"))
            out.append("  - **答**：{}".format(a.get("a") or "（空）"))
            out.append("  - 依据：{}".format(a.get("evidence") or "（空）"))
            if a.get("concede"):
                out.append("  - 该认的：{}".format(a["concede"]))
        out.append("")
        out.append("### 我为什么比它们更该拿到名额")
        out.append("")
        for w in an.get("why_better") or []:
            out.append("- 对方主张：{}".format(w.get("than") or "（空）"))
            out.append("  - 本组更强在哪：{}".format(w.get("point") or "（空）"))
            out.append("  - 凭什么：{}".format(w.get("why") or "（空）"))
        if an.get("cannot_beat"):
            out.append("")
            out.append("如实承认比不过的：{}".format(an["cannot_beat"]))
        out.append("")
    return "\n".join(out)


def render_award_md(award):
    out = ["# 裁决书", "",
           "> 获胜方案 + 落选原因 + **合并建议**（落选方案的可用部分）+ 打分明细。",
           "> 被判获胜的方案被一票否决、或落选原因缺失、或没有合并建议 → 本地闸门拦下。", ""]
    out.append("## 获胜：{}（`{}`）".format(
        award.get("winner_display") or "（判不出来）", award.get("winner") or "-"))
    out.append("")
    if award.get("why_winner"):
        out.append(award["why_winner"])
        out.append("")
    a = award.get("winner_anchor") or {}
    if award.get("winner_quote"):
        out.append("- 定音引文（{}）：{}".format(
            "已锚定到获胜方案" if a.get("ok") else _red("未锚定，见闸门"), award["winner_quote"]))
        if a.get("matched") and a.get("matched") != award.get("winner_quote"):
            out.append("  - 实际锚到：{}".format(a["matched"]))
        out.append("")
    out.append("## 打分明细（按公示权重）")
    out.append("")
    out.append("| 组 | {} | 总分 |".format(" | ".join(d["name"] for d in DIMENSIONS)))
    out.append("|---|" + "---|" * (len(DIMENSIONS) + 1))
    for x in award.get("score_detail") or []:
        cells = []
        for d in DIMENSIONS:
            v = (x.get("dims") or {}).get(d["id"])
            cells.append("-" if v is None else "{:g}".format(v))
        out.append("| **{}** | {} | **{:g}** |".format(
            TEAM_NAME.get(x.get("team"), x.get("team")), " | ".join(cells),
            x.get("total") if x.get("total") is not None else 0))
    out.append("")
    out.append("## 落选原因")
    out.append("")
    for x in award.get("losers") or []:
        out.append("### {}（`{}`）".format(
            TEAM_NAME.get(x.get("team"), x.get("raw_team")), x.get("team")))
        out.append("")
        out.append("- **输在哪**：{}".format(x.get("why_lost") or _red("（缺失）")))
        if x.get("quote"):
            aa = x.get("anchor") or {}
            out.append("- 引文（{}）：{}".format("已锚定" if aa.get("ok") else _red("未锚定"),
                                            x["quote"]))
        if x.get("keep"):
            out.append("- **仍值得保留**：{}".format(x["keep"]))
        out.append("")
    out.append("## 合并建议（落选方案的可用部分）")
    out.append("")
    if not award.get("merges"):
        out.append(_red("（没有合并建议——本地闸门会拦）"))
    for m in award.get("merges") or []:
        aa = m.get("anchor") or {}
        out.append("- 从 **{}** 拿：{}".format(
            TEAM_NAME.get(m.get("from_team"), m.get("raw_from")), m.get("quote") or "（空）"))
        out.append("  - 补进获胜方案的：{}".format(m.get("into") or _red("（空）")))
        out.append("  - 补上什么缺口：{}".format(m.get("gain") or "（空）"))
        out.append("  - 引文锚点：{}".format("已锚定" if aa.get("ok") else _red("未锚定")))
    out.append("")
    out.append("## 异议与否决（原样保留）")
    out.append("")
    if not award.get("dissent"):
        out.append("（无）")
    for d in award.get("dissent") or []:
        out.append("- **{}**：{}".format(
            TEAM_NAME.get(d.get("team"), d.get("raw_team")), d.get("reason") or "（空）"))
    out.append("")
    if award.get("summary"):
        out.append("## 总评")
        out.append("")
        out.append(award["summary"])
    return "\n".join(out)


def render_report_md(task, brief, proposals, panel, challenges, award, gates,
                     usage_dict, model, source, state_info, isolation):
    out = ["# 三剪客 · 方案竞标小组 · 总报告", "",
           "> **L3 · 竞争式**：三组独立提案 → 评委按公示维度打分 → 交叉质询 → 裁决。",
           "> 与「对抗评审式」的分界：那边审**一份已有材料**（没有胜负）；",
           "> 本包**选一份方案**（有胜负、有落选原因、有合并建议）。", ""]
    out.append("## 本次竞标")
    out.append("")
    out.append("- 任务书：`{}`（{} 字符 / {} 句）".format(
        source, brief.get("chars"), brief.get("sentences")))
    out.append("- 模型：`{}`".format(model))
    out.append("- 评分口径：`{}`（提案之前已公示）".format(RUBRIC_VERSION))
    out.append("- 参赛：{}".format("、".join(
        "{}（`{}`）".format(t["label"], t["id"]) for t in TEAMS)))
    out.append("- 评委：{}".format("、".join(
        "{}（{}）".format(j["name"], "有一票否决" if j["veto_power"] else "无否决权")
        for j in JUDGES)))
    out.append("")
    if award and award.get("winner"):
        out.append("**裁决结果：{} 获胜。**".format(
            award.get("winner_display") or award.get("winner")))
        out.append("")
    out.append("## 一、公示的评分维度（提案之前定死）")
    out.append("")
    out.append("| 维度 | 权重 | 评什么 |")
    out.append("|---|---|---|")
    for d in DIMENSIONS:
        out.append("| {} | {:.2f} | {} |".format(d["name"], d["weight"], d["what"]))
    out.append("")
    out.append("## 二、三组提案（互相隔离）")
    out.append("")
    out.append(render_proposals_md(proposals, isolation))
    out.append("")
    out.append("## 三、评委团打分")
    out.append("")
    out.append(render_panel_md(panel))
    out.append("")
    out.append("## 四、交叉质询")
    out.append("")
    out.append(render_challenge_md(challenges))
    out.append("")
    out.append("## 五、裁决")
    out.append("")
    out.append(render_award_md(award))
    out.append("")
    out.append("## 六、八道本地硬闸门")
    out.append("")
    out.append("| # | 闸门 | 结果 |")
    out.append("|---|---|---|")
    names = [("compliance", "合规（任务书侧）"), ("placeholder", "占位符（任务书侧）"),
             ("output_compliance", "合规（产出侧，口径分开）"),
             ("output_placeholder", "占位符（产出侧）"), ("prompt_echo", "照抄提示词示例"),
             ("anchor", "打分锚点（理由必须引用方案原文）"),
             ("independence", "提案独立性（**假竞争**）"), ("award", "裁决完整性")]
    for key, label in names:
        v = gates.get(key)
        if v is None:
            out.append("| - | {} | 本阶段不适用 |".format(label))
            continue
        out.append("| - | {} | {} |".format(label, "通过" if v.get("ok") else _red("命中")))
    out.append("")
    for key, label in names:
        v = gates.get(key) or {}
        for p in (v.get("problems") or [])[:8]:
            out.append("- [{}] {}".format(key, p))
        for p in (v.get("red_hints") or [])[:8]:
            out.append("- [{}·提示] {}".format(key, p))
        if v.get("why"):
            out.append("- [{}] {}".format(key, v["why"]))
    out.append("")
    ind = gates.get("independence") or {}
    if ind:
        out.append("### 提案独立性明细（本包核心闸门）")
        out.append("")
        out.append("- 两两重合度：{}".format("；".join(
            "{}↔{} = {:.3f}".format(p["a"], p["b"], p["overlap"])
            for p in ind.get("pairs") or []) or "（不足两组）"))
        out.append("- 最大重合度 **{:.3f}**（硬阈值 {:.2f}，标红阈值 {:.2f}）".format(
            ind.get("max_overlap") or 0.0, INDEP_OVERLAP, INDEP_RED_OVERLAP))
        out.append("- 各组方案字数：{}".format("；".join(
            "{} = {} 字".format(k, v.get("chars"))
            for k, v in (ind.get("lengths") or {}).items())))
        out.append("- 判定基准：{}".format(ind.get("text_basis")))
        out.append("")
    out.append("## 七、token 与成本")
    out.append("")
    if usage_dict:
        out.append("- 调用 {} 次，prompt {} + completion {} = **{} token**".format(
            usage_dict.get("calls"), usage_dict.get("prompt_tokens"),
            usage_dict.get("completion_tokens"), usage_dict.get("total_tokens")))
        if usage_dict.get("has_price"):
            out.append("- 估算 {:g} 点 ≈ ¥{:g}（按你填的单价）".format(
                usage_dict.get("points") or 0, usage_dict.get("yuan") or 0))
        else:
            out.append("- 金额：网关不公布文本单价，**未折算**（要折算请传 "
                       "--price-in / --price-out，单位点/百万 token）")
        out.append("")
        out.append("| 调用 | prompt | completion | finish_reason | 内容字符 | 耗时(s) |")
        out.append("|---|---|---|---|---|---|")
        for c in usage_dict.get("usage_log") or []:
            out.append("| {} | {} | {} | {} | {} | {} |".format(
                c.get("label"), c.get("prompt_tokens"), c.get("completion_tokens"),
                c.get("finish_reason"), c.get("content_chars"), c.get("elapsed")))
        out.append("")
        out.append("> `finish_reason` 记在这里是有用的：`length` 才表示被 max_tokens 截断"
                   "（加大 `--max-tokens` 有用）；其它值（含 `stop`/`null`）表示"
                   "**不是长度问题**，加大没用。**不要用内容长度判断**。")
    else:
        out.append("（本次没有真实调用：断点续跑或纯本地路径）")
    out.append("")
    out.append("## 八、断点 key")
    out.append("")
    out.append("```json")
    out.append(json.dumps(state_info or {}, ensure_ascii=False, indent=1))
    out.append("```")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# `--json` 契约
#
#   · 成功：stdout 输出**一个** JSON 对象，第一层一定有 `ok`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#   · `--json` 写在子命令**前后都能用**
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
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", "replace")
    # 自测钩子：闸门自测要能验收「未捕获异常 → kind:internal 信封 + 完整 traceback」，
    # 而这条路径**必须真的抛一个没预料到的异常**，不能靠 mock。
    # 只在显式传了标记串时触发，正常运行永远不会命中（一个字都不多花）。
    if _INTERNAL_MARKER and _INTERNAL_MARKER in text:
        raise RuntimeError("自测用的未捕获异常（internal 信封用例）")
    return text


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


def resolve_teams(spec):
    """把 `--teams a,b` 解析成组定义列表；没给就用全部三组。"""
    if not spec:
        return list(TEAMS)
    ids = [x.strip() for x in str(spec).replace("，", ",").split(",") if x.strip()]
    out = []
    from_ = [x.strip() for x in str(spec).split(",")]
    for i, x in enumerate(ids):
        tid = as_team_id(x)
        if tid is None:
            raise UsageError("不认识这个组：{!r}。可选：{}（或写 a/b/c）".format(
                x, "、".join(TEAM_IDS)))
        out.append(TEAM_BY_ID[tid])
    # 去重保持顺序
    ded, seen = [], set()
    for t in out:
        if t["id"] not in seen:
            seen.add(t["id"])
            ded.append(t)
    del from_
    return ded


def teams_spec(teams):
    return [t["id"] for t in teams]


def judges_spec(judges):
    return [j["id"] for j in judges]


def isolation_evidence(team_prompts, teams, other_team_names):
    """信息隔离证据：每个组的提示词里**有没有混进别的组**。

    这不是"声明我们隔离了"，而是**本地核对**：把那两组的一切可识别文字
    （id / 显示名 / label）在提示词里搜一遍，命中的原样列出来。
    """
    ev = {"teams": {}, "stage_inputs": {
        "propose": ["task", "own_stance"],
        "score": ["task", "all_proposals_anonymous"],
        "challenge": ["task", "own_proposal", "own_judge_feedback", "rival_digests_only"],
        "award": ["task", "all_proposals", "panel", "challenges_answers"],
    }}
    for t in teams:
        prompt = team_prompts.get(t["id"]) or ""
        found = []
        for other in other_team_names:
            if other == t["id"]:
                continue
            for token in {other, TEAM_NAME.get(other, other),
                          (TEAM_BY_ID.get(other) or {}).get("label") or ""}:
                if token and token in prompt:
                    found.append({"other": other, "token": token})
        ev["teams"][t["id"]] = {
            "prompt_chars": len(prompt),
            "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            "other_teams_in_prompt": found,
            "rubric_in_prompt": any(d["name"] in prompt for d in DIMENSIONS),
            "note": ("提示词里只有任务书与本组立场；"
                     "不含另外两组的任何文字，也不含评分维度与权重"),
        }
    return ev


def cross_visibility_evidence(team, prompt, rival_digests, rival_texts=None,
                              own_full_proposal=True, judge_feedback=None):
    """交叉质询阶段的可视性证据：它看到了对方的什么、**没**看到什么。

    本地核对（不是声明）：把对方方案里的句子拿去提示词里搜一遍，命中就算泄漏。

    ⚠️ 两处必须**排除**，否则会误报（真机实测第一轮就踩到了）：
      1. **摘要本身**：摘要（headline + claims）是**有意给出**的，它当然在提示词里；
      2. **别组的 headline / claims 与 judge_feedback 里引用的句子**：
         评委的打分理由是**带引文**的，而评委看的是全部三份方案——
         所以"只属于本组的评委意见"里可能夹着别组的原话引用。
         那不是本题的泄漏（评委引用别组原文是评分的正常动作），
         但要在产物里**如实标注**，不能假装不存在。
    """
    def _is_given(sent):
        """这句话是不是"本来就要给它"的内容（摘要 / 评委引文）。

        ⚠️ 判定要**双向包含**（这一段是真机实测抓出来的）：
        摘要里的 headline 就是方案原文的一句话，而方案提示词按句子切分后
        也正好得到同一句 —— 只判 `sent in piece` 会漏掉
        `piece in sent` 的情形（两边都归一化过标点），于是把"有意给出的摘要"
        误报成"原文泄漏"。两处都判才准。
        """
        s = _norm_anchor(sent)
        for d in rival_digests or []:
            for piece in [d.get("headline") or ""] + list(d.get("claims") or []):
                np = _norm_anchor(piece)
                if np and (s in np or np in s):
                    return True
        for jf in judge_feedback or []:
            for piece in [jf.get("conclusion") or ""]:
                np = _norm_anchor(piece)
                if np and (s in np or np in s):
                    return True
        return False

    leaks, via_digest, via_judge = [], [], []
    for rt in (rival_texts or []):
        tid = rt.get("team")
        for sent in split_sentences(rt.get("text") or ""):
            if sent not in prompt:
                continue
            if _is_given(sent):
                via_digest.append({"team": tid, "sentence": sent[:60]})
                continue
            leaks.append({"team": tid, "sentence": sent[:60], "chars": len(_norm_anchor(sent))})
    # 短句（摘要级别的）不算泄漏；长句命中才算"原文漏出去了"。
    real_leaks = [x for x in leaks if x["chars"] >= CROSS_LEAK_MIN]
    short_hits = [x for x in leaks if x["chars"] < CROSS_LEAK_MIN]
    return {
        "team": team,
        "prompt_chars": len(prompt),
        "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
        "own_full_proposal": bool(own_full_proposal),
        "rival_digest_count": len(rival_digests),
        "rival_digest_fields": ["headline", "claims[].text"],
        "rival_full_text_leaked": real_leaks,
        "rival_sentences_via_digest_or_judge_quote": via_digest[:8],
        "rival_short_sentence_hits": short_hits[:8],
        "leak_rule": ("对方方案里 ≥ {} 字的句子若出现在提示词里且不属于"
                      "「摘要」或「评委引文」，才算原文泄漏；"
                      "短句命中与摘要命中如实列出，但不判为泄漏").format(CROSS_LEAK_MIN),
        "note": ("只给「自己的全文 + 对方的主张摘要 + 只属于自己的评委意见」；"
                 "对方原文与对方收到的批评一律不给"),
    }


def rival_digests_for(team_id, proposals):
    """算出某一组的"对方摘要"（匿名化为 甲/乙 之类的编号，不暴露组名）。"""
    out = []
    idx = 0
    for p in proposals:
        if p.get("team") == team_id:
            continue
        idx += 1
        d = proposal_digest(p)
        out.append({"anon": "对手 {}".format(idx), "team": p.get("team"),
                    "headline": d["headline"], "claims": d["claims"]})
    return out


def judge_feedback_for(team_id, panel, anonymize_rival=False):
    """把**只属于这一组**的评委意见挑出来（别的组的评委意见绝不给）。"""
    out = []
    for jr in (panel or {}).get("judges") or []:
        for sc in jr.get("scores") or []:
            if sc.get("team") != team_id:
                continue
            reasons = []
            for r in sc.get("reasons") or []:
                reasons.append({"dim": r.get("dim"),
                                "dim_name": DIM_NAME.get(r.get("dim")) or r.get("raw_dim"),
                                "why": r.get("why"), "fix": r.get("fix"),
                                "score": r.get("score")})
            veto = None
            for v in jr.get("effective_vetoes") or []:
                if v.get("team") == team_id:
                    veto = v.get("reason")
            out.append({"judge_id": jr.get("judge"), "judge_name": jr.get("judge_name"),
                        "total": sc.get("total"), "reasons": reasons, "veto": veto,
                        "conclusion": sc.get("conclusion")})
    return out


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------

def run_roles(a):
    md = render_roles_md()
    if a.out:
        ensure_outside_pkg(a.out, "输出文件")
        write_text(a.out, md)
    body = {
        "command": "roles",
        "crews": {
            "teams": [{k: t[k] for k in ("id", "name", "label", "route", "bias",
                                         "must_have", "give_up")} for t in TEAMS],
            "judges": [{k: j[k] for k in ("id", "name", "focus", "veto_power")}
                       for j in JUDGES],
            "challenger": {"id": "host", "name": "质询主持",
                           "note": "手里只有主张摘要，没有对方原文"},
            "awarder": {"id": "awarder", "name": "裁决人",
                        "note": "终裁：获胜 + 落选原因 + 合并建议 + 打分明细"},
        },
        "rubric_version": RUBRIC_VERSION,
        "roles_md": md,
    }
    if _json_out(body, a):
        return EXIT_OK
    print(md)
    return EXIT_OK


def run_rubric(a):
    """公示评分维度与权重（**纯本地零成本，必须在提案之前跑**）。"""
    rubric = {
        "command": "rubric",
        "rubric_version": RUBRIC_VERSION,
        "prompt_version": PROMPT_VERSION,
        "crew_version": CREW_VERSION,
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_weight": RUBRIC_TOTAL_WEIGHT,
        "dimensions": [dict(d) for d in DIMENSIONS],
        "order_rule": ("评分维度必须在**提案之前**公示。没跑过 rubric 就 score → 退出码 2。"
                       "理由：维度若在看到方案之后才定，评委就是在为已经写出来的东西找尺子——"
                       "那是「打分」，不是「竞标」。"),
        "weights_are_constants": ("维度与权重是代码里的常量（不是让模型现编的）："
                                  "竞标的公正性全押在「尺子先定」上。改维度必须改口径版本号。"),
    }
    md = render_rubric_md(rubric)
    if a.outdir:
        outdir = Path(a.outdir)
        ensure_outside_pkg(outdir, "输出目录")
        outdir.mkdir(parents=True, exist_ok=True)
        write_json(outdir / "rubric.json", rubric)
        write_text(outdir / "rubric.md", md)
        rubric["written_to"] = str(outdir)
    if a.out:
        ensure_outside_pkg(a.out, "输出文件")
        if _json_want(a):
            write_json(a.out, _json_payload(rubric))
        else:
            write_text(a.out, md)
    if _json_out(rubric, a):
        return EXIT_OK
    print(md)
    if a.outdir:
        print("\n已写入：{}/rubric.json 与 rubric.md".format(a.outdir))
    return EXIT_OK


def require_rubric(outdir, must_exist=True):
    """**顺序闸门**：没公示过评分维度就打分 → OrderError（退出码 2）。

    这条不是形式主义。题面把它列为硬闸门，因为顺序倒了整场竞标的性质就变了：
    先看方案后定尺子 = 为结果找理由。所以它是 `score` 的第一步，
    且**在任何调用之前**判。

    `must_exist=False` 用于 `propose`：单组提案这一步本身不写 rubric，
    但**已经在产出目录里公示过**时，口径版本必须一致（旧尺子打的分配不上新尺子的裁决）。
    """
    p = Path(outdir) / "rubric.json"
    if not p.is_file():
        if not must_exist:
            return None
        raise OrderError(
            "顺序倒了：{} 里没有 rubric.json —— **评分维度必须先公示**。\n"
            "  正确顺序：rubric（公示维度与权重，零成本）→ propose / run\n"
            "  先跑：python3 run.py rubric --file 任务书.md --outdir {}\n"
            "  理由：维度若在看到方案之后才定，就是为已经写出来的东西找尺子——"
            "那是「打分」，不是「竞标」。（本次**不会发起任何调用**。）".format(outdir, outdir))
    obj = load_json(p, "评分口径 rubric.json")
    ver = (obj or {}).get("rubric_version")
    if ver != RUBRIC_VERSION:
        raise OrderError(
            "顺序/口径不一致：{} 里的评分口径是 {!r}，当前代码是 {!r}。\n"
            "  换了维度或权重口径必须重新公示（旧尺子打的分配不上新尺子的裁决）。\n"
            "  重跑：python3 run.py rubric --file 任务书.md --outdir {}".format(
                p, ver, RUBRIC_VERSION, outdir))
    return obj


def require_stage(outdir, name, filename, hint):
    """顺序闸门（阶段前置产物）。缺了就 UsageError（退出码 2），**零调用**。"""
    p = Path(outdir) / filename
    if not p.is_file():
        raise OrderError("顺序倒了：{} 里没有 {}。\n  先跑：{}\n  （本次**不会发起任何调用**）".format(
            outdir, filename, hint))
    return load_json(p, name)


def run_propose(a):
    # ⚠️ 会花钱的子命令，第一步永远是**预算校验**（见 check_cost_opts 的事故复盘）。
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir, "输出目录")
    outdir.mkdir(parents=True, exist_ok=True)
    if a.out:
        ensure_outside_pkg(a.out, "输出文件")
    # 顺序闸门：**尺子先定，再让三组提案**。产出目录里若已公示过口径，
    # 版本必须与当前代码一致（旧尺子打的分配不上新尺子的裁决）；
    # 没有 rubric.json 不算错（`run` 会自己先公示），但 `--require-rubric` 可强制。
    require_rubric(outdir, must_exist=bool(getattr(a, "require_rubric", False)))
    team = TEAM_BY_ID.get(as_team_id(a.team) or "")
    if team is None:
        raise UsageError("不认识这个组：{!r}。可选：{}（或写 a/b/c）".format(
            a.team, "、".join(TEAM_IDS)))

    prompt = build_team_prompt(team, text, meta)
    if a.dry_run:
        print("===== 组 {}（{}）的提示词开始 =====".format(team["id"], team["name"]))
        print(prompt)
        print("===== 组 {} 的提示词结束 =====".format(team["id"]))
        print("--dry-run：本次调用**没有发出**。")
        return EXIT_OK

    tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
    state = load_state(outdir)
    k = state_key("propose:" + team["id"], meta["sha"], meta["chars"], len(prompt),
                  a.model, a.temperature, [team["id"]], judges_spec(JUDGES))
    prop_path = outdir / "proposal_{}.json".format(team["id"])
    if prop_path.is_file() and state["entries"].get(k) == "done" and not a.force:
        obj = load_json(prop_path, "方案结果")
        sys.stderr.write("propose:{}：断点命中，跳过（0 次调用）。\n".format(team["id"]))
        if _json_out(obj, a):
            return EXIT_OK
        print(json.dumps(obj.get("proposal") or {}, ensure_ascii=False, indent=1))
        return EXIT_OK

    sys.stderr.write("提案：{} 独立写方案（看不到另外两组，也看不到评分维度）…\n".format(team["name"]))
    content, usage = guarded_chat(
        prompt, tracker, "propose:{}".format(team["id"]),
        system=TEAM_SYSTEM.format(name=team["name"], label=team["label"],
                                 route=team["route"], bias=team["bias"],
                                 must_have=team["must_have"], give_up=team["give_up"]),
        model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
        key=a.key, json_mode=not a.no_json_mode)
    proposal = normalize_proposal(parse_first_json(content), team)
    proposal["body"] = {k2: v for k2, v in proposal.items() if k2 != "raw"}
    iso = isolation_evidence({team["id"]: prompt}, [team], TEAM_IDS)
    obj = {
        "command": "propose", "team": team["id"], "proposal": proposal,
        "task": meta, "isolation": iso,
        "usage": _stage_usage(tracker, 0),
        "note": "单组提案：提示词里只有任务书与本组立场（见 isolation）。",
    }
    gates = evaluate_gates(text, [proposal], None, None, None, {"panel": False})
    obj["gates"] = gates
    bad = gate_failed(gates)
    obj["gate_failed"] = bad
    obj["exit"] = EXIT_GATE if bad else EXIT_OK
    _commit(bool(getattr(a, "replay", None)), outdir, state, k, lambda: (
        write_json(prop_path, obj),
        write_text(outdir / "proposal_{}.md".format(team["id"]),
                   render_proposals_md([proposal], iso))))
    for line in gate_summary_lines(gates):
        sys.stderr.write("闸门命中：" + line + "\n")
    sys.stderr.write(tracker.line() + "\n")
    if a.out:
        write_json(a.out, _json_payload(obj, not bad))
    if _json_out(obj, a, ok=not bad):
        pass
    else:
        print(render_proposals_md([proposal], iso))
    if bad:
        return _fail(EXIT_GATE, "gate", "组 {} 的提案命中本地闸门".format(team["id"]))
    return EXIT_OK


def collect_proposals(outdir, teams):
    """从产出目录收集全部已完成的方案（缺一组就报错，因为竞争需要三方）。"""
    proposals = []
    missing = []
    for t in teams:
        p = Path(outdir) / "proposal_{}.json".format(t["id"])
        if not p.is_file():
            missing.append(t["id"])
            continue
        obj = load_json(p, "方案结果")
        prop = obj.get("proposal") or {}
        # 回放/续跑时**重做一遍归一化**，不直接信文件里存好的结论
        body = prop.get("raw") or {k: v for k, v in prop.items()
                                   if k not in ("raw", "body", "team", "team_name")}
        proposals.append(normalize_proposal(body, t))
    if missing:
        raise OrderError(
            "顺序倒了：{} 里缺这些组的方案：{}。\n"
            "  先跑：python3 run.py propose --file 任务书.md --team <组> --outdir {}\n"
            "  （三组都写完才谈得上竞争；本次**不会发起任何调用**）".format(
                outdir, "、".join(missing), outdir))
    for p in proposals:
        p["body"] = {k: v for k, v in p.items() if k != "raw"}
    return proposals


def run_score(a):
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir, "输出目录")
    outdir.mkdir(parents=True, exist_ok=True)
    if a.out:
        ensure_outside_pkg(a.out, "输出文件")
    # ⚠️ 顺序闸门（本包特有，硬闸门七）：**必须先公示评分维度**，且在任何调用之前判
    require_rubric(outdir)
    teams = resolve_teams(getattr(a, "teams", None) or None)
    proposals = collect_proposals(outdir, teams)
    targets = targets_for(proposals)

    tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
    state = load_state(outdir)
    judges = JUDGES
    prompt = build_judge_prompt(judges[0], text, proposals, DIMENSIONS)  # 仅用于 key 长度
    k = state_key("score", meta["sha"], meta["chars"], None, a.model, a.temperature,
                  teams_spec(teams), judges_spec(judges),
                  earlier_sha=json_sha([p["raw"] for p in proposals]))
    panel_path = outdir / "panel.json"
    # ⚠️ `--replay` 优先：回放模式下模型路径进不去（缺产物就报错，不"顺手重跑"）。
    if a.replay and not (panel_path.is_file() and state["entries"].get(k) == "done"):
        if not panel_path.is_file():
            raise OrderError(
                "回放模式缺产物：{} 里没有 panel.json。`--replay` **不会**重新生成它"
                "（那要花钱）；请先跑 score，或指向产物完整的目录。"
                "（本次**没有发起任何调用**。）".format(outdir))
        raw_panel = load_json(Path(a.replay) / "panel.json", "回放目录里的评委团结果")
        panel = validate_panel(raw_panel.get("raw") or raw_panel, judges, proposals, targets)
        sys.stderr.write("score：--replay 命中，跳过模型调用（锚点与总分会重算）。\n")
    elif panel_path.is_file() and state["entries"].get(k) == "done" and not a.force:
        panel = load_json(panel_path, "评委团结果")
        panel = validate_panel(panel.get("raw") or {}, judges, proposals, targets)
        sys.stderr.write("score：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        raw_panel = load_json(Path(a.replay) / "panel.json", "回放目录里的评委团结果")
        panel = validate_panel(raw_panel.get("raw") or raw_panel, judges, proposals, targets)
        sys.stderr.write("score：--replay 命中，跳过模型调用（锚点与总分会重算）。\n")
    else:
        out_judges, marks = [], []
        for j in judges:
            sys.stderr.write("打分：{}（{}）按公示维度评三份方案…\n".format(j["name"], j["focus"]))
            p = build_judge_prompt(j, text, proposals, DIMENSIONS)
            mark = len(tracker.log)
            content, usage = guarded_chat(
                p, tracker, "score:{}".format(j["id"]),
                system=JUDGE_SYSTEM.format(name=j["name"], focus=j["focus"],
                                          question=j["question"], style=j["style"]),
                model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
                key=a.key, json_mode=not a.no_json_mode)
            marks.append(mark)
            out_judges.append(parse_first_json(content))
        panel = validate_panel({"judges": _zip_judges(out_judges, judges)},
                               judges, proposals, targets)
        panel["usage"] = _stage_usage(tracker, 0)
        sys.stderr.write("打分完成：本地排名 {}。\n".format(
            " > ".join(panel.get("local_ranking") or []) or "（无）"))
    panel.update({"command": "score", "task": meta,
                  "rubric_version": RUBRIC_VERSION,
                  "rubric": [dict(d) for d in DIMENSIONS],
                  "targets_sha": json_sha({t: k2 for t, k2 in
                                           ((x["team"], x["raw"]) for x in proposals)})})
    gates = evaluate_gates(text, proposals, panel, None, None, {"panel": True})
    bad = gate_failed(gates)
    panel["gates"] = gates
    panel["gate_failed"] = bad
    panel["exit"] = EXIT_GATE if bad else EXIT_OK
    _commit(bool(getattr(a, "replay", None)), outdir, state, k, lambda: (
        write_json(panel_path, panel),
        write_text(outdir / "panel.md", render_panel_md(panel))))
    for line in gate_summary_lines(gates, panel):
        sys.stderr.write("闸门命中：" + line + "\n")
    if tracker.calls:
        sys.stderr.write(tracker.line() + "\n")
    if a.out:
        write_json(a.out, _json_payload(panel, not bad))
    if _json_out(panel, a, ok=not bad):
        pass
    else:
        print(render_panel_md(panel))
    if bad:
        return _fail(EXIT_GATE, "gate", "评委团打分命中本地闸门")
    return EXIT_OK


def _zip_judges(raw_list, judges):
    """把按顺序拿到的评委原始返回，配上对应的评委元信息。"""
    out = []
    for raw, j in zip(raw_list, judges):
        if not isinstance(raw, dict):
            raw = {}
        r = dict(raw)
        r.setdefault("judge", j["id"])
        out.append(r)
    return out


def run_challenge(a):
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir, "输出目录")
    outdir.mkdir(parents=True, exist_ok=True)
    if a.out:
        ensure_outside_pkg(a.out, "输出文件")
    require_rubric(outdir)
    teams = resolve_teams(getattr(a, "teams", None) or None)
    proposals = collect_proposals(outdir, teams)
    panel_obj = require_stage(outdir, "评委团结果", "panel.json",
                              "python3 run.py score --file 任务书.md --outdir {}".format(outdir))
    panel = validate_panel(panel_obj.get("raw") or {}, JUDGES, proposals, targets_for(proposals))

    tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
    state = load_state(outdir)
    ch_path = outdir / "challenge.json"
    k = state_key("challenge", meta["sha"], meta["chars"], None, a.model, a.temperature,
                  teams_spec(teams), judges_spec(JUDGES), earlier_sha=json_sha(panel_obj))
    challenges = None
    # ⚠️ `--replay` 优先（见 run_run 里的事故复盘）。
    if a.replay and not (ch_path.is_file() and state["entries"].get(k) == "done"):
        if not ch_path.is_file():
            raise OrderError(
                "回放模式缺产物：{} 里没有 challenge.json。`--replay` **不会**重新生成它"
                "（那要花钱）；请先跑 challenge，或指向产物完整的目录。"
                "（本次**没有发起任何调用**。）".format(outdir))
        raw_ch = load_json(Path(a.replay) / "challenge.json", "回放目录里的质询结果")
        challenges = _revalidate_challenges(raw_ch.get("challenges") or [], proposals, panel,
                                           text)
        sys.stderr.write("challenge：--replay 命中，跳过模型调用。\n")
    elif ch_path.is_file() and state["entries"].get(k) == "done" and not a.force:
        ch_obj = load_json(ch_path, "质询结果")
        challenges = _revalidate_challenges(ch_obj.get("challenges") or [], proposals, panel,
                                           text)
        sys.stderr.write("challenge：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        raw_ch = load_json(Path(a.replay) / "challenge.json", "回放目录里的质询结果")
        challenges = _revalidate_challenges(raw_ch.get("challenges") or [], proposals, panel,
                                           text)
        sys.stderr.write("challenge：--replay 命中，跳过模型调用。\n")
    else:
        challenges = []
        for t in teams:
            own = next(p for p in proposals if p["team"] == t["id"])
            rivals = rival_digests_for(t["id"], proposals)
            fb = judge_feedback_for(t["id"], panel)
            cp = build_challenge_prompt(t, text, own, rivals, fb)
            sys.stderr.write("质询：向 {} 出题（只给它自己的材料 + 对方摘要）…\n".format(t["name"]))
            mark = len(tracker.log)
            content, usage = guarded_chat(
                cp, tracker, "challenge:{}".format(t["id"]),
                system=CHALLENGE_SYSTEM, model=a.model, temperature=a.temperature,
                max_tokens=a.max_tokens, key=a.key, json_mode=not a.no_json_mode)
            ch_raw = parse_first_json(content)
            challenge = _normalize_challenge(ch_raw)
            ap = build_answer_prompt(t, text, own, rivals, fb, challenge)
            sys.stderr.write("质询：{} 作答（论证我为什么更该拿到名额）…\n".format(t["name"]))
            mark2 = len(tracker.log)
            content2, usage2 = guarded_chat(
                ap, tracker, "answer:{}".format(t["id"]),
                system=ANSWER_SYSTEM.format(name=t["name"], label=t["label"]),
                model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
                key=a.key, json_mode=not a.no_json_mode)
            answer = _normalize_answer(parse_first_json(content2), challenge)
            challenges.append({
                "team": t["id"], "team_name": t["name"],
                "digests": rivals, "challenge": challenge, "answer": answer,
                "judge_feedback_given": [{"judge_id": f["judge_id"], "total": f["total"],
                                          "veto": f.get("veto")} for f in fb],
                "cross_visibility": cross_visibility_evidence(
                    t["id"], cp, rivals,
                    rival_texts=[{"team": x["team"],
                                  "text": proposal_own_text(x)}
                                 for x in proposals if x["team"] != t["id"]],
                    judge_feedback=fb),
                "usage": {"challenge": _stage_usage(tracker, mark),
                          "answer": _stage_usage(tracker, mark2)},
            })
        sys.stderr.write("质询完成：{} 组各自作答。\n".format(len(challenges)))
    gates = evaluate_gates(text, proposals, panel, challenges, None, {"panel": False})
    bad = gate_failed(gates)
    obj = {"command": "challenge", "task": meta, "rubric_version": RUBRIC_VERSION,
           "challenges": challenges, "gates": gates, "gate_failed": bad,
           "exit": EXIT_GATE if bad else EXIT_OK,
           "usage": _stage_usage(tracker, 0) if tracker.calls else _merge_stage_usage(
               [{"usage": c.get("usage", {}).get("challenge")} for c in challenges], tracker),
           "note": ("交叉可见性：每组只拿到自己的全文 + 对方的主张摘要 + "
                    "只属于自己的评委意见（见 cross_visibility）。")}
    _commit(bool(getattr(a, "replay", None)), outdir, state, k, lambda: (
        write_json(ch_path, obj),
        write_text(outdir / "challenge.md", render_challenge_md(challenges))))
    for line in gate_summary_lines(gates, panel):
        sys.stderr.write("闸门命中：" + line + "\n")
    if tracker.calls:
        sys.stderr.write(tracker.line() + "\n")
    if a.out:
        write_json(a.out, _json_payload(obj, not bad))
    if _json_out(obj, a, ok=not bad):
        pass
    else:
        print(render_challenge_md(challenges))
    if bad:
        return _fail(EXIT_GATE, "gate", "交叉质询产出命中本地闸门")
    return EXIT_OK


def _normalize_challenge(raw):
    raw = raw if isinstance(raw, dict) else {}
    qs = []
    for q in raw.get("questions") or []:
        if isinstance(q, dict):
            qs.append({"ask": (q.get("ask") or "").strip(),
                       "targets": (q.get("targets") or "").strip(),
                       "why_hard": (q.get("why_hard") or "").strip()})
        else:
            s = str(q).strip()
            if s:
                qs.append({"ask": s, "targets": "", "why_hard": ""})
    seen = []
    for x in raw.get("rivals_seen") or []:
        s = (x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)).strip()
        if s:
            seen.append(s)
    return {"questions": qs, "rivals_seen": seen,
            "must_answer": (raw.get("must_answer") or "").strip(), "raw": raw}


def _revalidate_challenges(challenges, proposals, panel, text):
    """回放 / 续跑时**重新算一遍交叉可见性证据**，不直接信文件里存好的结论。

    为什么要重做：`cross_visibility`（对方原文有没有漏出去）是**本地算出来的**，
    它的判据会随版本改进。续跑命中时如果原样照抄旧文件，报告里就会出现
    用旧判据算出的数字 —— 真机实测正是这样：修好判据之后，
    报告里还挂着"对方原文泄漏 2 处"（那其实是**有意给出的摘要**）。
    重做的成本是零（纯本地），所以没有理由不重做。
    """
    out = []
    by_team = {p["team"]: p for p in proposals}
    for c in challenges or []:
        if not isinstance(c, dict):
            continue
        tid = c.get("team")
        if tid not in by_team:
            out.append(c)
            continue
        rivals = rival_digests_for(tid, proposals)
        fb = judge_feedback_for(tid, panel)
        cp = build_challenge_prompt(TEAM_BY_ID[tid], text, by_team[tid], rivals, fb)
        c = dict(c)
        c["digests"] = rivals
        c["judge_feedback_given"] = [
            {"judge_id": f["judge_id"], "total": f["total"], "veto": f.get("veto")}
            for f in fb]
        c["cross_visibility"] = cross_visibility_evidence(
            tid, cp, rivals,
            rival_texts=[{"team": x["team"], "text": proposal_own_text(x)}
                         for x in proposals if x["team"] != tid],
            judge_feedback=fb)
        out.append(c)
    return out


def _normalize_answer(raw, challenge):
    raw = raw if isinstance(raw, dict) else {}
    answers = []
    for x in raw.get("answers") or []:
        if not isinstance(x, dict):
            continue
        answers.append({"q": (x.get("q") or "").strip(), "a": (x.get("a") or "").strip(),
                        "evidence": (x.get("evidence") or "").strip(),
                        "concede": (x.get("concede") or "").strip()})
    better = []
    for x in raw.get("why_better") or []:
        if not isinstance(x, dict):
            continue
        better.append({"than": (x.get("than") or "").strip(),
                       "point": (x.get("point") or "").strip(),
                       "why": (x.get("why") or "").strip()})
    return {"answers": answers, "why_better": better,
            "cannot_beat": (raw.get("cannot_beat") or "").strip(), "raw": raw,
            "asked": len(challenge.get("questions") or [])}


def run_award(a):
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir, "输出目录")
    outdir.mkdir(parents=True, exist_ok=True)
    if a.out:
        ensure_outside_pkg(a.out, "输出文件")
    require_rubric(outdir)
    teams = resolve_teams(getattr(a, "teams", None) or None)
    proposals = collect_proposals(outdir, teams)
    targets = targets_for(proposals)
    panel_obj = require_stage(outdir, "评委团结果", "panel.json",
                              "python3 run.py score --file 任务书.md --outdir {}".format(outdir))
    panel = validate_panel(panel_obj.get("raw") or {}, JUDGES, proposals, targets)
    ch_obj = require_stage(outdir, "质询结果", "challenge.json",
                           "python3 run.py challenge --file 任务书.md --outdir {}".format(outdir))
    challenges = ch_obj.get("challenges") or []
    answers = [{"team": c.get("team"), "challenge": c.get("challenge"),
                "answer": c.get("answer")} for c in challenges]

    tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
    state = load_state(outdir)
    aw_path = outdir / "award.json"
    k = state_key("award", meta["sha"], meta["chars"], None, a.model, a.temperature,
                  teams_spec(teams), judges_spec(JUDGES),
                  earlier_sha=json_sha([panel_obj, ch_obj]))
    if a.replay and not (aw_path.is_file() and state["entries"].get(k) == "done"):
        if not aw_path.is_file():
            raise OrderError(
                "回放模式缺产物：{} 里没有 award.json。`--replay` **不会**重新生成它"
                "（那要花钱）；请先跑 award，或指向产物完整的目录。"
                "（本次**没有发起任何调用**。）".format(outdir))
        raw_aw = load_json(Path(a.replay) / "award.json", "回放目录里的裁决结果")
        award = validate_award(raw_aw.get("raw") or raw_aw, proposals, panel, targets)
        sys.stderr.write("award：--replay 命中，跳过模型调用（本地校验已重算）。\n")
    elif aw_path.is_file() and state["entries"].get(k) == "done" and not a.force:
        award = load_json(aw_path, "裁决结果")
        award = validate_award(award.get("raw") or {}, proposals, panel, targets)
        sys.stderr.write("award：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        raw_aw = load_json(Path(a.replay) / "award.json", "回放目录里的裁决结果")
        award = validate_award(raw_aw.get("raw") or raw_aw, proposals, panel, targets)
        sys.stderr.write("award：--replay 命中，跳过模型调用（本地校验已重算）。\n")
    else:
        prompt = build_award_prompt(text, proposals, panel, answers)
        sys.stderr.write("裁决：出终裁（获胜 + 落选原因 + 合并建议 + 打分明细）…\n")
        content, usage = guarded_chat(
            prompt, tracker, "award", system=AWARD_SYSTEM, model=a.model,
            temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
            json_mode=not a.no_json_mode)
        award = validate_award(parse_first_json(content), proposals, panel, targets)
        award["usage"] = _stage_usage(tracker, 0)
    award["rubric_version"] = RUBRIC_VERSION
    award.update({"command": "award", "task": meta})
    # 裁决里没给打分明细 → **不补齐**，留给闸门判（补齐等于把闸门自己废掉）。
    # 这里只把评委团的打分表放在旁边供人对照。
    award["panel_score_detail"] = panel.get("score_detail") or []
    gates = evaluate_gates(text, proposals, panel, challenges, award, {"panel": True, "award": True})
    bad = gate_failed(gates)
    award["gates"] = gates
    award["gate_failed"] = bad
    award["exit"] = EXIT_GATE if bad else EXIT_OK
    _commit(bool(getattr(a, "replay", None)), outdir, state, k, lambda: (
        write_json(aw_path, award),
        write_text(outdir / "award.md", render_award_md(award))))
    for line in gate_summary_lines(gates, panel):
        sys.stderr.write("闸门命中：" + line + "\n")
    if tracker.calls:
        sys.stderr.write(tracker.line() + "\n")
    if a.out:
        write_json(a.out, _json_payload(award, not bad))
    if _json_out(award, a, ok=not bad):
        pass
    else:
        print(render_award_md(award))
    if bad:
        return _fail(EXIT_GATE, "gate", "裁决命中本地闸门")
    return EXIT_OK


def run_log(a):
    """把产出目录里的结果再读一遍（**纯本地零成本**）。"""
    outdir = Path(a.outdir)
    files = ["rubric.json", "proposal_team_a.json", "proposal_team_b.json",
             "proposal_team_c.json", "panel.json", "challenge.json", "award.json",
             "REPORT.md", "state.json"]
    present = [f for f in files if (outdir / f).is_file()]
    if not present:
        raise UsageError("{} 里没有任何本包的产物（找过：{}）".format(
            outdir, "、".join(files)))
    summary = {"command": "log", "outdir": str(outdir), "files": present}
    if (outdir / "award.json").is_file():
        award = load_json(outdir / "award.json", "裁决结果")
        summary["winner"] = award.get("winner")
        summary["losers"] = [x.get("team") for x in (award.get("losers") or [])]
        summary["merges"] = len(award.get("merges") or [])
        summary["gate_failed"] = award.get("gate_failed")
    if (outdir / "panel.json").is_file():
        panel = load_json(outdir / "panel.json", "评委团结果")
        summary["local_ranking"] = panel.get("local_ranking")
        summary["max_overlap"] = ((panel.get("gates") or {}).get("independence") or {}).get(
            "max_overlap")
        summary["vetoed"] = list((panel.get("vetoed") or {}).keys())
    if (outdir / "state.json").is_file():
        summary["state_entries"] = len((load_json(outdir / "state.json", "断点文件")
                                        or {}).get("entries") or {})
    if _json_out(summary, a):
        return EXIT_OK
    print("产出目录：{}".format(outdir))
    print("已有产物：{}".format("、".join(present)))
    if summary.get("winner"):
        print("裁决：{} 获胜；落选 {}；合并建议 {} 条".format(
            TEAM_NAME.get(summary["winner"], summary["winner"]),
            "、".join(TEAM_NAME.get(x, x) for x in summary.get("losers") or []) or "（无）",
            summary.get("merges")))
    if summary.get("local_ranking"):
        print("本地排名：{}".format(" > ".join(summary["local_ranking"])))
    if summary.get("max_overlap") is not None:
        print("最大方案重合度：{:.3f}（阈值 {:.2f}）".format(
            summary["max_overlap"], INDEP_OVERLAP))
    return EXIT_OK


def run_run(a):
    """一条命令跑完整场竞标：rubric → propose×3 → score×3 → challenge×3(+3) → award。"""
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir, "输出目录")
    outdir.mkdir(parents=True, exist_ok=True)
    if a.out:
        ensure_outside_pkg(a.out, "输出文件")
    teams = resolve_teams(getattr(a, "teams", None) or None)
    if len(teams) < 2:
        raise UsageError("竞争至少需要两组（给了 {} 组）——一组不构成竞标".format(len(teams)))

    tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
    state = load_state(outdir)
    state_info, calls = {}, []
    # `--replay` 一开就把话说清楚：**这一跑一次调用都不会发**，缺什么就报错退出。
    # 事故复盘（本包真机踩到，代价是真金白银）：删掉 challenge.json 之后 state 里
    # 还写着 done，续跑判定不成立、又没走 replay 分支，脚本**直接去调模型了** ——
    # 用户以为自己在零成本回放，实际花了钱。所以现在：
    #   1. 每个阶段的判断都是「`--replay` 优先」，模型路径在 replay 下进不去；
    #   2. 缺产物直接 OrderError（退出码 2），不"顺手重新生成"。
    if a.replay:
        sys.stderr.write("== --replay 模式：只重跑本地闸门与渲染，"
                         "**本次一次模型调用都不会发**；缺哪个产物就直接报错。\n")
    rubric_obj = {
        "command": "rubric", "rubric_version": RUBRIC_VERSION,
        "prompt_version": PROMPT_VERSION, "crew_version": CREW_VERSION,
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_weight": RUBRIC_TOTAL_WEIGHT,
        "dimensions": [dict(d) for d in DIMENSIONS],
        "order_rule": ("评分维度必须在**提案之前**公示；顺序倒了 score 会 exit=2"),
        "weights_are_constants": "维度与权重是代码常量，不是模型现编的",
    }
    # ⚠️ 顺序不可倒：**先公示尺子，再让三组提案**。
    # 这不是形式主义：先看方案后定尺子 = 为结果找理由，整场竞标的性质就变了。
    if not a.replay:
        write_json(outdir / "rubric.json", rubric_obj)
        write_text(outdir / "rubric.md", render_rubric_md(rubric_obj))
    sys.stderr.write("步骤 1/5：公示评分维度与权重（纯本地，0 次调用）。\n")

    # ---- 2) 三组独立提案 ----
    proposals, prop_isolation = [], {}
    for t in teams:
        prompt = build_team_prompt(t, text, meta)
        prop_isolation[t["id"]] = prompt
        k = state_key("propose:" + t["id"], meta["sha"], meta["chars"], len(prompt),
                      a.model, a.temperature, [t["id"]], judges_spec(JUDGES))
        state_info["propose:" + t["id"]] = k
        p = outdir / "proposal_{}.json".format(t["id"])
        if p.is_file() and state["entries"].get(k) == "done" and not a.force:
            obj = load_json(p, "方案结果")
            prop = obj.get("proposal") or {}
            body = prop.get("raw") or {kk: vv for kk, vv in prop.items()
                                       if kk not in ("raw", "body", "team", "team_name")}
            proposals.append(normalize_proposal(body, t))
            sys.stderr.write("propose:{}：断点命中，跳过（0 次调用）。\n".format(t["id"]))
            continue
        if a.dry_run:
            print("===== 组 {}（{}）的提示词开始 =====".format(t["id"], t["name"]))
            print(prompt)
            print("===== 组 {} 的提示词结束 =====\n".format(t["id"]))
            continue
        sys.stderr.write("步骤 2/5：{} 独立写方案（看不到另外两组与评分维度）…\n".format(t["name"]))
        mark = len(tracker.log)
        content, usage = guarded_chat(
            prompt, tracker, "propose:{}".format(t["id"]),
            system=TEAM_SYSTEM.format(name=t["name"], label=t["label"], route=t["route"],
                                     bias=t["bias"], must_have=t["must_have"],
                                     give_up=t["give_up"]),
            model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
            key=a.key, json_mode=not a.no_json_mode)
        calls.append({"stage": "propose:{}".format(t["id"]), "usage": usage})
        prop = normalize_proposal(parse_first_json(content), t)
        prop["body"] = {kk: vv for kk, vv in prop.items() if kk != "raw"}
        proposals.append(prop)
        o = {"command": "propose", "team": t["id"], "proposal": prop, "task": meta,
             "usage": _stage_usage(tracker, mark)}
        write_json(p, o)
        state["entries"][k] = "done"
        save_state(outdir, state)
    if a.dry_run:
        print("--dry-run：三组提案的 {} 次调用**没有发出**；打分、质询、裁决依赖方案，"
              "无法在 dry-run 里预演。".format(len(teams)))
        return EXIT_OK

    iso = isolation_evidence(prop_isolation, teams, TEAM_IDS)
    if not a.replay:
        write_text(outdir / "proposals.md", render_proposals_md(proposals, iso))
    for tid, ev in iso["teams"].items():
        leaked = ev.get("other_teams_in_prompt") or []
        sys.stderr.write("隔离核对[{}]：提示词 {} 字符，混进别组文字 {} 处，"
                         "混进评分维度：{}\n".format(
                             tid, ev.get("prompt_chars"), len(leaked),
                             "是" if ev.get("rubric_in_prompt") else "否"))
    targets = targets_for(proposals)

    # ---- 3) 评委团打分 ----
    raw_judges = []
    k_score = state_key("score", meta["sha"], meta["chars"], None, a.model, a.temperature,
                        teams_spec(teams), judges_spec(JUDGES),
                        earlier_sha=json_sha([p["raw"] for p in proposals]))
    state_info["score"] = k_score
    panel_path = outdir / "panel.json"
    if panel_path.is_file() and state["entries"].get(k_score) == "done" and not a.force:
        panel = validate_panel((load_json(panel_path, "评委团结果")).get("raw") or {},
                               JUDGES, proposals, targets)
        sys.stderr.write("score：断点命中，跳过（0 次调用）。\n")
    else:
        for j in JUDGES:
            sys.stderr.write("步骤 3/5：{}（{}）按公示维度评 {} 份方案…\n".format(
                j["name"], j["focus"], len(proposals)))
            p = build_judge_prompt(j, text, proposals, DIMENSIONS)
            mark = len(tracker.log)
            content, usage = guarded_chat(
                p, tracker, "score:{}".format(j["id"]),
                system=JUDGE_SYSTEM.format(name=j["name"], focus=j["focus"],
                                          question=j["question"], style=j["style"]),
                model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
                key=a.key, json_mode=not a.no_json_mode)
            calls.append({"stage": "score:{}".format(j["id"]), "usage": usage})
            raw_judges.append(parse_first_json(content))
        panel = validate_panel({"judges": _zip_judges(raw_judges, JUDGES)},
                               JUDGES, proposals, targets)
        panel["usage"] = _stage_usage(tracker, 0)
        _commit(bool(getattr(a, "replay", None)), outdir, state, k_score,
                lambda: write_json(panel_path, panel))
    panel.update({"command": "score", "task": meta, "rubric_version": RUBRIC_VERSION,
                  "rubric": [dict(d) for d in DIMENSIONS]})
    if not a.replay:
        write_text(outdir / "panel.md", render_panel_md(panel))
    sys.stderr.write("打分完成：本地排名 {}；一票否决 {}。\n".format(
        " > ".join(panel.get("local_ranking") or []) or "（无）",
        "、".join(TEAM_NAME.get(x, x) for x in (panel.get("vetoed") or {})) or "无"))

    # ---- 4) 交叉质询 ----
    ch_path = outdir / "challenge.json"
    k_ch = state_key("challenge", meta["sha"], meta["chars"], None, a.model, a.temperature,
                     teams_spec(teams), judges_spec(JUDGES),
                     earlier_sha=json_sha(load_json(panel_path, "评委团结果")))
    state_info["challenge"] = k_ch
    challenges = []
    if a.replay and not (ch_path.is_file() and state["entries"].get(k_ch) == "done"):
        # ⚠️ `--replay` 必须在**续跑判定之后立刻**接管，顺序不能倒。
        # 真机踩到的坑（代价真金白银）：删掉 challenge.json 之后 state 里还写着 done，
        # 于是续跑判定不成立、又没走 replay 分支，脚本**直接去调模型了** ——
        # 用户以为自己在零成本回放，实际花了钱。所以这里：
        #   `--replay` 一开，模型路径就进不去；缺哪个产物就报错退出（退出码 2），
        #   绝不容许"回放时顺手把该有的东西重新生成一遍"。
        if not ch_path.is_file():
            raise OrderError(
                "回放模式缺产物：{} 里没有 challenge.json。\n"
                "  `--replay` **不会**帮你重新生成（那要花钱）：请把质询那一步跑一次\n"
                "  （python3 run.py challenge --file 任务书.md --outdir {}），"
                "或指向另一个产物完整的目录。\n"
                "  （本次**没有发起任何调用**。）".format(outdir, outdir))
        challenges = _revalidate_challenges(
            load_json(ch_path, "质询结果").get("challenges") or [], proposals, panel, text)
        sys.stderr.write("challenge：--replay 命中（本地校验已重算，0 次调用）。\n")
    elif ch_path.is_file() and state["entries"].get(k_ch) == "done" and not a.force:
        challenges = _revalidate_challenges(
            (load_json(ch_path, "质询结果")).get("challenges") or [], proposals, panel, text)
        sys.stderr.write("challenge：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        challenges = _revalidate_challenges(
            load_json(ch_path, "质询结果").get("challenges") or [], proposals, panel, text)
        sys.stderr.write("challenge：--replay 命中（本地校验已重算，0 次调用）。\n")
    else:
        for t in teams:
            own = next(p for p in proposals if p["team"] == t["id"])
            rivals = rival_digests_for(t["id"], proposals)
            fb = judge_feedback_for(t["id"], panel)
            cp = build_challenge_prompt(t, text, own, rivals, fb)
            sys.stderr.write("步骤 4/5：向 {} 出题（它只看得到对方的主张摘要）…\n".format(t["name"]))
            mark = len(tracker.log)
            content, usage = guarded_chat(
                cp, tracker, "challenge:{}".format(t["id"]), system=CHALLENGE_SYSTEM,
                model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
                key=a.key, json_mode=not a.no_json_mode)
            calls.append({"stage": "challenge:{}".format(t["id"]), "usage": usage})
            challenge = _normalize_challenge(parse_first_json(content))
            ap = build_answer_prompt(t, text, own, rivals, fb, challenge)
            mark2 = len(tracker.log)
            content2, usage2 = guarded_chat(
                ap, tracker, "answer:{}".format(t["id"]),
                system=ANSWER_SYSTEM.format(name=t["name"], label=t["label"]),
                model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
                key=a.key, json_mode=not a.no_json_mode)
            calls.append({"stage": "answer:{}".format(t["id"]), "usage": usage2})
            answer = _normalize_answer(parse_first_json(content2), challenge)
            challenges.append({
                "team": t["id"], "team_name": t["name"], "digests": rivals,
                "challenge": challenge, "answer": answer,
                "judge_feedback_given": [{"judge_id": f["judge_id"], "total": f["total"],
                                          "veto": f.get("veto")} for f in fb],
                "cross_visibility": cross_visibility_evidence(
                    t["id"], cp, rivals,
                    rival_texts=[{"team": x["team"],
                                  "text": proposal_own_text(x)}
                                 for x in proposals if x["team"] != t["id"]],
                    judge_feedback=fb),
                "usage": {"challenge": _stage_usage(tracker, mark),
                          "answer": _stage_usage(tracker, mark2)},
            })
        _commit(bool(getattr(a, "replay", None)), outdir, state, k_ch,
                lambda: write_json(
                    ch_path, {"command": "challenge", "task": meta,
                              "challenges": challenges}))
    if not a.replay:
        write_text(outdir / "challenge.md", render_challenge_md(challenges))
    for c in challenges:
        cv = c.get("cross_visibility") or {}
        sys.stderr.write("交叉可见性[{}]：自己的全文 ✓；对方摘要 {} 条；"
                         "对方原文泄漏 {} 处\n".format(
                             c["team"], cv.get("rival_digest_count"),
                             len(cv.get("rival_full_text_leaked") or [])))

    # ---- 5) 裁决 ----
    answers = [{"team": c.get("team"), "challenge": c.get("challenge"),
                "answer": c.get("answer")} for c in challenges]
    aw_path = outdir / "award.json"
    k_aw = state_key("award", meta["sha"], meta["chars"], None, a.model, a.temperature,
                     teams_spec(teams), judges_spec(JUDGES),
                     earlier_sha=json_sha([load_json(panel_path, "评委团结果"),
                                           load_json(ch_path, "质询结果")]))
    state_info["award"] = k_aw
    if a.replay and not (aw_path.is_file() and state["entries"].get(k_aw) == "done"):
        # 与质询同一处纪律：`--replay` 一开，模型路径就进不去；缺产物就报错。
        if not aw_path.is_file():
            raise OrderError(
                "回放模式缺产物：{} 里没有 award.json。\n"
                "  `--replay` **不会**帮你重新生成（那要花钱）：请把裁决那一步跑一次\n"
                "  （python3 run.py award --file 任务书.md --outdir {}），"
                "或指向另一个产物完整的目录。\n"
                "  （本次**没有发起任何调用**。）".format(outdir, outdir))
        award = validate_award(load_json(aw_path, "裁决结果").get("raw") or {},
                               proposals, panel, targets)
        sys.stderr.write("award：--replay 命中（本地校验已重算，0 次调用）。\n")
    elif aw_path.is_file() and state["entries"].get(k_aw) == "done" and not a.force:
        award = validate_award((load_json(aw_path, "裁决结果")).get("raw") or {},
                               proposals, panel, targets)
        sys.stderr.write("award：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        award = validate_award(load_json(aw_path, "裁决结果").get("raw") or {},
                               proposals, panel, targets)
        sys.stderr.write("award：--replay 命中（本地校验已重算，0 次调用）。\n")
    else:
        prompt = build_award_prompt(text, proposals, panel, answers)
        sys.stderr.write("步骤 5/5：裁决（获胜 + 落选原因 + 合并建议 + 打分明细）…\n")
        mark = len(tracker.log)
        content, usage = guarded_chat(
            prompt, tracker, "award", system=AWARD_SYSTEM, model=a.model,
            temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
            json_mode=not a.no_json_mode)
        calls.append({"stage": "award", "usage": usage})
        award = validate_award(parse_first_json(content), proposals, panel, targets)
        award["usage"] = _stage_usage(tracker, mark)
        _commit(bool(getattr(a, "replay", None)), outdir, state, k_aw,
                lambda: write_json(aw_path, award))
    award.update({"command": "award", "task": meta, "rubric_version": RUBRIC_VERSION})
    # 裁决里没给打分明细 → **不补齐**，留给闸门判（补齐等于把闸门自己废掉）。
    award["panel_score_detail"] = panel.get("score_detail") or []
    if not a.replay:
        write_text(outdir / "award.md", render_award_md(award))

    # ---- 闸门 + 报告 ----
    gates = evaluate_gates(text, proposals, panel, challenges, award,
                           {"panel": True, "award": True})
    if tracker.calls:
        usage_dict = tracker.as_dict()
    else:
        usage_dict = _merge_stage_usage(
            [{"usage": (load_json(panel_path, "p").get("usage") if panel_path.is_file() else None)},
             {"usage": (load_json(ch_path, "c").get("usage") if ch_path.is_file() else None)},
             {"usage": (load_json(aw_path, "a").get("usage") if aw_path.is_file() else None)}],
            tracker)
    brief = build_task_brief(text, a.file)
    if not a.replay:
        write_json(outdir / "task_brief.json", brief)
    if not a.replay:
        write_text(outdir / "task_brief.md", _render_brief_md(brief, text))
    report = render_report_md(text, brief, proposals, panel, challenges, award, gates,
                              usage_dict, a.model, a.file, state_info, iso)
    if not a.replay:
        write_text(outdir / "REPORT.md", report)
    for line in gate_summary_lines(gates, panel):
        sys.stderr.write("闸门命中：" + line + "\n")
    bad = [k for k in HARD_GATE_KEYS if not (gates.get(k) or {}).get("ok", True)]
    if bad:
        sys.stderr.write("本地闸门命中 {} 项：{}（详见 {}/REPORT.md）\n".format(
            len(bad), "、".join(bad), outdir))
    else:
        sys.stderr.write("本地硬闸门：全部通过。\n")
    if tracker.calls:
        sys.stderr.write(tracker.line() + "\n")
    else:
        sys.stderr.write("本次是断点续跑 / 回放：{} 次调用。\n".format(tracker.calls))

    body = {
        "command": "run", "task": meta,
        "rubric": {"rubric_version": RUBRIC_VERSION, "total_weight": RUBRIC_TOTAL_WEIGHT,
                   "dimensions": [dict(d) for d in DIMENSIONS]},
        "proposals": proposals, "isolation": iso,
        "panel": panel, "challenges": challenges, "award": award,
        "gates": gates, "gate_failed": gate_failed(gates),
        "exit": (EXIT_GATE if bad else EXIT_OK),
        "usage": usage_dict, "state_key": state_info, "outdir": str(outdir),
        "files": ["rubric.json", "rubric.md", "proposal_team_a.json", "proposal_team_b.json",
                  "proposal_team_c.json", "proposals.md", "panel.json", "panel.md",
                  "challenge.json", "challenge.md", "award.json", "award.md",
                  "task_brief.json", "task_brief.md", "REPORT.md", "state.json"],
        "report_md": report,
    }
    if a.out:
        if _json_want(a):
            write_json(a.out, _json_payload(body, not bad))
        else:
            write_text(a.out, report)
    # ⚠️ 契约细节：闸门命中时，**结果本身**就是那份失败报告（`ok: false` + `exit` + `gates`），
    # 不再另补一个错误信封 —— 守住"stdout 永远只有一个 JSON"这条不变量。
    if _json_out(body, a, ok=not bad):
        pass
    else:
        print(report)
        print("\n产出目录：{}".format(outdir))
    if bad:
        raise GateFail("本地闸门命中 {} 项：{}".format(len(bad), "、".join(bad)))
    return EXIT_OK


def _render_brief_md(brief, text):
    out = ["# 任务书整理（纯本地，零成本）", "",
           "- 来源：`{}`".format(brief.get("source")),
           "- {} 字符 / {} 句 / {} 段".format(brief.get("chars"), brief.get("sentences"),
                                          brief.get("paragraphs")),
           "- 摘要：`{}`".format(brief.get("sha")), ""]
    if brief.get("headings"):
        out.append("## 大纲")
        out.append("")
        for h in brief["headings"]:
            out.append("{}- {}".format("  " * max(0, h["level"] - 1), h["text"]))
        out.append("")
    if brief.get("numbers"):
        out.append("## 关键数字（三组必须看同一份）")
        out.append("")
        for n in brief["numbers"][:30]:
            out.append("- `{}` … {}".format(n["raw"], n["context"]))
        out.append("")
    if brief.get("proper_nouns"):
        out.append("## 专有名词")
        out.append("")
        for p in brief["proper_nouns"][:30]:
            out.append("- [{}] {}".format(p["kind"], p["raw"]))
        out.append("")
    pre = brief.get("local_prescan") or {}
    out.append("## 本地预扫（任务书侧）")
    out.append("")
    for k, label in (("compliance", "合规"), ("placeholder", "占位符"),
                     ("prompt_echo", "照抄示例")):
        v = pre.get(k) or {}
        out.append("- {}：{}".format(label, "通过" if v.get("ok") else "命中 {} 条".format(
            len(v.get("hits") or []))))
    out.append("")
    out.append("## 三组必须回答的问题")
    out.append("")
    for q in brief.get("task_questions") or []:
        out.append("- {}".format(q))
    return "\n".join(out)


def _stage_usage(tracker, start):
    """把 tracker.log[start:] 这一段调用整理成一个阶段 usage 记录。

    按阶段切：`run` 一共有五个步骤，断点续跑时可能只有一部分真的调用了模型。
    阶段各自的 usage 记在各自产物里，汇总时相加不会重复计数。
    token 全部来自网关返回的真实 usage，没有任何估算值混在里面。
    """
    log = tracker.log[start:]
    p = sum(x.get("prompt_tokens") or 0 for x in log)
    c = sum(x.get("completion_tokens") or 0 for x in log)
    return {"calls": len(log), "prompt_tokens": p, "completion_tokens": c,
            "total_tokens": p + c,
            "log": [{"label": x.get("label"), "prompt_tokens": x.get("prompt_tokens"),
                     "completion_tokens": x.get("completion_tokens"),
                     "finish_reason": x.get("finish_reason"),
                     "content_chars": x.get("content_chars"),
                     "elapsed": x.get("elapsed")} for x in log]}


def _merge_stage_usage(objs, tracker):
    """断点续跑 / 回放时的汇总：把各阶段产物里自己记的 usage 相加。

    为什么要合并而不是重算：续跑的那几步**没有发生调用**，tracker 是空的。
    各阶段产物里存着当时真实的 usage，按阶段相加才不会漏也不会重复。
    """
    calls, p, c, log = 0, 0, 0, []
    for o in objs or []:
        u = (o or {}).get("usage") or {}
        if not u:
            continue
        calls += u.get("calls") or 0
        p += u.get("prompt_tokens") or 0
        c += u.get("completion_tokens") or 0
        for x in u.get("log") or []:
            log.append(x)
    d = tracker.as_dict()
    d.update({"calls": calls, "prompt_tokens": p, "completion_tokens": c,
              "total_tokens": p + c, "usage_log": log,
              "note": "断点续跑 / 回放：token 来自各阶段产物里存下的真实 usage，相加汇总。"})
    if tracker.has_price:
        pts = (p / 1e6) * float(tracker.price_in) + (c / 1e6) * float(tracker.price_out)
        d["points"] = round(pts, 4)
        d["yuan"] = round(pts / POINTS_PER_YUAN, 4)
    return d


def run_cost(a):
    """报价：这场竞标大概花多少 token（金额要你自己填单价）。**零成本**。"""
    text = ""
    if a.file:
        text = read_text(a.file)
    elif a.text:
        text = a.text
    teams = resolve_teams(a.teams or None)
    plan = estimate_calls(text, len(teams), len(JUDGES))
    ti = sum(x["tokens_in"] for x in plan)
    to = sum(x["tokens_out"] for x in plan)
    total_calls = sum(x["calls"] for x in plan)
    rec = compute_cost(ti, to, a.price_in, a.price_out)
    body = {
        "command": "cost",
        "task_chars": char_count(text),
        "team_count": len(teams), "judge_count": len(JUDGES),
        "total_calls": total_calls,
        "plan": plan,
        "tokens_in": ti, "tokens_out": to, "total_tokens": ti + to,
        "cost": rec,
        "note": ("调用次数是**结构性地**定下来的：{} 组各 1 次提案 + {} 名评委各 1 次打分 + "
                 "{} 组各 1 次质询 + {} 组各 1 次作答 + 1 次裁决。"
                 "少了任何一环，「竞争」就不成立。").format(
                     len(teams), len(JUDGES), len(teams), len(teams)),
    }
    if _json_out(body, a):
        return EXIT_OK
    print("这场竞标预计 **{} 次调用**、约 **{} token**（prompt {} + completion {}）".format(
        total_calls, ti + to, ti, to))
    print("")
    print("| 阶段 | 调用 | 估 prompt | 估 completion | 说明 |")
    print("|---|---|---|---|---|")
    for x in plan:
        print("| {} | {} | {} | {} | {} |".format(
            x["stage"], x["calls"], x["tokens_in"], x["tokens_out"], x["note"]))
    print("")
    print(fmt_cost(rec))
    print("")
    print("> 单位说明：`--budget` 的单位是**点**（1 元 = 100 点），"
          "`--price-in / --price-out` 的单位是**点/百万 token**。")
    print("> 文本网关不公布单价，所以本包只报 token、**不编价**。")
    return EXIT_OK


def run_models(a):
    """列出 api.a7w.cn 当前在架的模型（免费，但要 Key 才能调更全的列表）。"""
    key = a7w.load_key(getattr(a, "key", None))
    url = MODELS_URL + ("?type=" + str(a.type) if getattr(a, "type", None) else "")
    try:
        payload = a7w._request("GET", url, key)
    except a7w.A7wError as exc:
        raise BidError("拉模型列表失败：{}".format(exc))
    data = payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        data = payload["data"]
    models = None
    if isinstance(data, dict):
        for k in ("models", "list", "items", "data"):
            if isinstance(data.get(k), list):
                models = data[k]
                break
    elif isinstance(data, list):
        models = data
    if models is None:
        models = []
    if _json_out({"command": "models", "count": len(models), "models": models,
                  "endpoint": MODELS_URL}, a):
        return EXIT_OK
    print("在架模型 {} 个（{}）".format(len(models), MODELS_URL))
    print("")
    for m in models:
        print("  {:<28} {:<8} call_type={}  {:<28} {}".format(
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            m.get("call_type"), str(m.get("vendor_name") or "-"),
            str(m.get("model_name") or "")[:24]))
    print("")
    print("提示：模型名会变，以本命令现查为准，别写死在脚本里。")
    print("      `{}` 实测可用（路由到 deepseek-flash），但它**不在**上面这份列表里，"
          .format(DEFAULT_MODEL))
    print("      所以「列表里没有」不等于「不能用」。")
    print("用法：run.py run --file 任务书.md --outdir <包外目录> --model <model_code>")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def check_cost_opts(a):
    """`--budget` 必须配单价 —— 在**任何调用发生之前**检查。

    事故复盘（同族自测时踩到的真实坑，不是理论问题）：这道校验原先只写在 `cost` 里，
    于是 `run --file x --budget 50`（没给单价）一路跑完十几次真实调用才返回 ——
    用户以为设了预算上限，实际一分钱都没被拦住。所以它必须是
    **每一个会花钱的子命令的第一步**（propose / score / challenge / award / run）。
    """
    if getattr(a, "budget", None) is None:
        return
    if getattr(a, "price_in", None) is None or getattr(a, "price_out", None) is None:
        raise UsageError(
            "用了 --budget 就必须给 --price-in 与 --price-out：文本模型网关不公布单价，"
            "没有单价就没法把 token 折成点数、预算无从判定。"
            "（单位：点/百万 token；本次**不会发起任何调用**，不花一分钱。）")
    if float(a.budget) <= 0:
        raise UsageError("--budget 必须大于 0（单位：点，1 元 = 100 点）")


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与全族同口径）。

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
                   help="最大输出 token，默认 8192（一场竞标十几次调用，别调太小）")
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
                   help="预算上限，单位「点」（1 元 = 100 点）。超了就地中止，退出码 5；"
                        "用 --budget 必须给单价")


def _add_task_opts(p, required=True):
    p.add_argument("--file", required=required, help="竞标任务书（.md / .txt，UTF-8）")
    p.add_argument("--teams", help="只跑指定的组（逗号分隔，默认全部三组）：{}".format(
        "、".join(TEAM_IDS)))
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
        description="三剪客 · 方案竞标小组（L3 竞争式多智能体；走 api.a7w.cn 的 OpenAI 兼容端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    # 每个子命令的 parser 也必须关掉缩写：argparse 的缩写开关是**每个 parser 各自**的属性，
    # 只在父级设一遍不够（子 parser 是另造的实例，默认仍然是允许缩写）。
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("roles", help="列出三组 / 三评委 / 质询主持 / 裁决人（零成本）")
    _add_json(p)
    p.add_argument("--out", help="把角色表写到这个文件")
    p.set_defaults(func=run_roles)

    p = sub.add_parser("rubric", help="公示评分维度与权重（零成本，**必须在提案之前跑**）")
    _add_json(p)
    p.add_argument("--outdir", help="把 rubric.json / rubric.md 落这个目录（必须在包外）")
    p.add_argument("--out", help="把公示结果写到这个文件")
    p.set_defaults(func=run_rubric)

    p = sub.add_parser("propose", help="某个提案组独立出方案（信息隔离，1 次调用）")
    _add_task_opts(p, required=True)
    p.add_argument("--team", required=True, help="哪个组：{}（或写 a/b/c）".format(
        "、".join(TEAM_IDS)))
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--require-rubric", action="store_true", dest="require_rubric",
                   help="要求产出目录里已公示过评分口径（严格顺序；缺了就退出码 2）")
    p.set_defaults(func=run_propose)

    p = sub.add_parser("score", help="评委团按公示维度打分（每名评委 1 次调用）")
    _add_task_opts(p, required=True)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_score)

    p = sub.add_parser("challenge", help="交叉质询：出题 + 每组作答（每组 2 次调用）")
    _add_task_opts(p, required=True)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_challenge)

    p = sub.add_parser("award", help="裁决：获胜 + 落选原因 + 合并建议 + 打分明细（1 次调用）")
    _add_task_opts(p, required=True)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_award)

    p = sub.add_parser("run", help="一条命令跑完整场竞标（rubric→propose→score→"
                                  "challenge→award），断点续跑")
    p.add_argument("--file", required=True, help="竞标任务书（.md / .txt，UTF-8）")
    p.add_argument("--teams", help="只跑指定的组（逗号分隔，默认全部三组）：{}".format(
        "、".join(TEAM_IDS)))
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".") / "bid-crew-out"),
                   help="目录产物落这里（**必须在包外**）：rubric、proposal_*、panel、"
                        "challenge、award、REPORT.md、state.json")
    p.add_argument("--replay", help="从一个已有产物目录回放：读取该目录里的 "
                                    "panel.json / challenge.json / award.json，"
                                    "**零调用**只跑本地闸门与报告（闸门自测用）")
    p.add_argument("--force", action="store_true",
                   help="忽略断点文件，从头重跑（key 没命中就会重新花钱）")
    p.set_defaults(func=run_run)

    p = sub.add_parser("log", help="把产出目录里的结果再读一遍（零成本）")
    p.add_argument("--outdir", required=True, help="产出目录")
    _add_json(p)
    p.set_defaults(func=run_log)

    p = sub.add_parser("cost", help="报价：这场竞标大概花多少 token（金额要你填单价）")
    p.add_argument("--file", help="按这份任务书估")
    p.add_argument("--text", help="或直接给文本")
    p.add_argument("--teams", help="按几组估（默认三组）")
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
    for k, v in (("json", False), ("out", None), ("dry_run", False), ("no_json_mode", False),
                 ("budget", None), ("price_in", None), ("price_out", None), ("replay", None),
                 ("force", False), ("teams", None), ("outdir", None), ("type", "text"),
                 ("team", None), ("text", None), ("file", None), ("key", None),
                 ("require_rubric", False),
                 ("model", DEFAULT_MODEL), ("temperature", 0.7), ("max_tokens", 8192)):
        if not hasattr(a, k):
            setattr(a, k, v)
    kind, msg, detail = None, None, None
    try:
        rc = a.func(a)
    except BidError as exc:
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
