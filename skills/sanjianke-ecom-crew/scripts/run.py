#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 电商上新小组 —— 四个角色的协作流水线（零第三方依赖）。

这是 **L3 多智能体协作型**：四个角色各有自己的目标函数与产出物，
互相能否掉对方的东西，一条命令出整套上新物料 + 一份可读的裁决记录。

九个（含 log）子命令：

    roles        列出四个角色的职权、产出契约与否决权（零成本、不联网）
    pick         选品：出选品卡（卖点/成本/毛利/资质/风险）；**自己能否掉这个品**
    copy         文案：主图五个位 + 详情页文案
    visual       视觉：每个主图位画什么、文字压哪；**能说「这张做不出来」**
    compliance   合规：按广告法与平台规则裁决（放行 / 打回 / **一票否决**）
    run          完整协作：选品 → 文案 ⇄ 视觉 → 合规，打回就重开，谈不拢就说谈不拢
    log          把 `run --outdir` 落下的裁决记录读出来（零成本）
    cost         报价：这次协作大概花多少 token（金额要你自己填单价）
    models       列出 api.a7w.cn 当前在架的模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py roles
    python3 run.py pick --file 商品资料.md
    python3 run.py copy --file 商品资料.md --pick 选品卡.json --out 文案.json
    python3 run.py visual --file 商品资料.md --copy 文案.json
    python3 run.py compliance --file 商品资料.md --bundle 物料.json
    python3 run.py run --file 商品资料.md --rounds 2 --outdir 输出目录
    python3 run.py cost --file 商品资料.md --rounds 2
    python3 run.py pick --file 商品资料.md --dry-run      # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py run --file 商品资料.md --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍（为什么是 L3，而不是「单包多跑几个角色」）
    · 四个角色**各有独立目标函数**：选品看「能不能卖、毛利与资质」，文案看「能不能转化」，
      视觉看「图能不能产出、版式是否合规」，合规看「广告法与平台规则」。
      目标函数不同，才会得出不同结论 —— 这是"互否"能真实发生的前提。
    · **信息不对称是本地强制的**：喂给某个角色的上文只挑它该看到的字段。
      文案看不到视觉的可产性判断；视觉看不到合规的口径；合规看不到任何一方的自评。
      每次协作都会把「各角色实际收到了什么」打进 stderr，可以逐条核对。
    · **否决权是真的**：选品能自己否掉这个品（标 `venv_veto`，不会再往下跑）；
      视觉能标注某个主图位「做不出来」并要求改；合规能一票否决整包。
      本地闸门会**真的截住**（打回→重开；否决→不许放行），不是提示一句了事。
    · **不许假装谈拢**：轮次用尽仍在否决 → 明确报「未收敛」（退出码 3），
      裁决记录里留下每一轮的否决理由与未解决问题，绝不输出一份"看起来通过了"的物料。
    · **本包不出图**。视觉角色只产出**文本方案**（每张图画什么、文字压哪、素材从哪来）；
      真出图交给已有的电商主图包。包内不允许出现任何图片文件。
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
# 不许往包里写 .pyc。跑一次就会在 scripts/__pycache__/ 留下 .pyc，而 Skill 包的上传
# 白名单里没有它（CLI 的排除清单里就有 .pyc，**不会导致上传被拒**，
# 但包内多出一堆二进制垃圾没意义）。在 import a7w **之前**关掉字节码写入。
sys.dont_write_bytecode = True
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

# 退出码（与同族对齐）：
EXIT_OK = 0            # 跑完且没有任何硬闸门命中
EXIT_USAGE = 2         # 参数/配置错（文件不存在、--outdir 在包内、给了 --budget 没给单价）
EXIT_GATE = 3          # 硬闸门命中（合规/占位符/照抄示例/锚点/主图位/裁决完整性/未收敛）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止（**未发起那次调用**）
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。
# 事故复盘（同族踩过）：改了提示词或某个闸门口径却不改 key，续跑会把上一版口径的旧产物
# 当成"已完成"直接复用，产出对不上文档。加版本号是最省事的根治办法。
CREW_VERSION = "ecom-crew-1.0.0"
PROMPT_VERSION = "ecom-prompt-1.0.0"
GATE_VERSION = "ecom-gate-1.0.0"

ROLE_ORDER = ("pick", "copy", "visual", "compliance")


# ---------------------------------------------------------------------------
# 五个主图位（闸门五的口径来源）
#
# 电商主图的"位"不是排版偏好，是**平台约定**：每一张承担一个不同的说服任务。
# 所以缺位不是"少一张图"，是"少一个说服环节"。缺位一律标红（退出码 3）。
# ---------------------------------------------------------------------------

SLOT_KEYS = ("s1_benefit", "s2_spec", "s3_detail", "s4_scene", "s5_trust")
SLOT_LABEL = {
    "s1_benefit": "第 1 位 · 利益点",
    "s2_spec": "第 2 位 · 规格与适用",
    "s3_detail": "第 3 位 · 细节工艺",
    "s4_scene": "第 4 位 · 场景人群",
    "s5_trust": "第 5 位 · 资质售后",
}
SLOT_ASK = {
    "s1_benefit": "一张图说清「买它我能得到什么」——最想让人在 0.5 秒内读到的那一句",
    "s2_spec": "规格、型号、容量、适用人群与不适用人群，一目了然",
    "s3_detail": "材质、工艺、做工细节的可验证呈现（能做微距就做微距）",
    "s4_scene": "真实使用场景与目标人群，让人对号入座",
    "s5_trust": "售后承诺与**真实持有**的资质（没有真实资质就如实缺位，不许伪造）",
}
SLOT_CHOICES = list(SLOT_KEYS)

# 视觉角色的「做不出来」理由码。**枚举是刻意的**：自由文本没法做闸门，
# 也说不清"到底缺什么"。每一个码都对应一句"要谁能解决"。
VISUAL_REASON_CODES = {
    "missing_asset": "缺真实素材（实物图 / 实拍图 / 包装图），且用户没有提供可用的替代",
    "unverifiable_claim": "画面要呈现的效果无法用现有素材验证（可能变成伪造演示）",
    "no_real_cert": "该位要求资质，但用户没有提供真实持有的资质文件",
    "text_overflow": "文案字数超出该位的可读上限，硬排会糊成一团",
    "platform_rule": "该位形态与目标平台的主图规则冲突（如白底位放场景）",
}
REASON_CHOICES = list(VISUAL_REASON_CODES.keys())

PRODUCTIVITY_CHOICES = ("producible", "producible_with_placeholder", "not_producible")

# 素材可信度：证据优先级（实拍 > 检测报告 > 参数 > 形容词）。
# 视觉角色拿它判断"这张图有没有料"。形容词不是素材。
EVIDENCE_CHOICES = ("实拍图", "实物图", "检测报告", "资质证书", "包装图", "参数表", "仅形容词")

VERDICT_CHOICES = ("放行", "打回", "一票否决")
SEVERITY_CHOICES = ("高", "中", "低")

PICK_VERDICT_CHOICES = ("可主推", "可测试", "放弃")

# 默认目标平台白底位口径：淘宝/天猫首图白底。本包不改变出图，只影响视觉方案里的
# 版式与背景描述，以及合规角色的平台规则口径。
PLATFORM_CHOICES = ("taobao", "tmall", "1688", "pdd", "douyin")
PLATFORM_LABEL = {
    "taobao": "淘宝",
    "tmall": "天猫",
    "1688": "1688",
    "pdd": "拼多多",
    "douyin": "抖音商城",
}
DEFAULT_PLATFORM = "taobao"


# ---------------------------------------------------------------------------
# 四个角色（本包的骨架）
#
# 【为什么这四个】电商上新是一条**立场天然冲突**的链：
#   选品想让品能卖（乐观）；视觉要保证图真能做出来（悲观）；合规要保证发得出去（保守）；
#   文案夹在中间，既要转化又要过审。四者目标函数不同 → 必然互相否。
#
# 【为什么信息要隔离】如果每个角色都能看到上游的自我评价（"我觉得这个方案没问题"），
# 后面的人就会顺着前一个人的结论走 —— 那只是一个人写了四遍，不是四个立场在互审。
# 本包的做法：喂给角色的上文**只挑它该看到的字段**（见 ROLE_SEES / role_input）。
# ---------------------------------------------------------------------------

ROLE_INFO = [
    {
        "key": "pick",
        "name": "选品",
        "objective": "这个品能不能卖、毛利够不够、资质与合规风险能不能兜住",
        "deliverable": "选品卡：类目 / 售价 / 成本拆解 / 退货后毛利 / 保本 CPA / "
                       "卖点与证据 / 资质状态 / 风险清单 / 自己的结论",
        "veto": "能。`venv_veto=true` 时**整条流水线就地停下**，不会进入文案与视觉；"
                "也可以 `重开`（要用户补一项真实材料后重跑）",
        "sees": "商品资料（用户给的原始材料）",
        "cannot_see": "（它是第一个角色，没有上游）",
    },
    {
        "key": "copy",
        "name": "文案",
        "objective": "主图与详情页的文字能不能转化，以及能不能被图和平台容下",
        "deliverable": "主图五位的文案（每行不超过该位上限）+ 详情页文案 + 依据",
        "veto": "无。文案不能否决任何角色；它只能被否（被视觉要求改、被合规打回）",
        "sees": "商品资料 + 选品卡的**卖点与证据、风险提示** + 上一轮的否决意见（若有）",
        "cannot_see": "选品角色的自评与结论细节（只给结构化字段，不给它的长篇论述）",
    },
    {
        "key": "visual",
        "name": "视觉",
        "objective": "每张图到底画什么、文字压哪、素材从哪来、能不能真的做出来",
        "deliverable": "五位的视觉方案（画面 / 素材来源 / 可产性 / 文字位置与字数 / 版式）"
                       "+ 做不出来的位与理由码",
        "veto": "能。对任一位标 `not_producible` 即**打回文案**：必须改到能产出，"
                "或由用户补齐真实素材；改不动就在轮次用尽时报未收敛",
        "sees": "商品资料 + 主图位的**文案**（只给文字）+ 素材清单",
        "cannot_see": "选品卡的风险清单细节、合规的任何结论、各角色的自评",
    },
    {
        "key": "compliance",
        "name": "合规",
        "objective": "广告法与平台规则：这套物料能不能发出去",
        "deliverable": "风险裁决：逐条违规项（含原文引文）/ 需补材料 / 整改要求 / "
                       "结论（放行 / 打回 / 一票否决）",
        "veto": "**一票否决**。`一票否决` 时整包不许放行：要重开就按整改要求重开，"
                "轮次用尽仍在否决就如实报未收敛（退出码 3）",
        "sees": "商品资料 + 最终物料（选品卡要点 / 五位文案 / 五位视觉方案）",
        "cannot_see": "任何角色的自我评价与内部打分（只给产出物本身）",
    },
]
ROLE_BY_KEY = {r["key"]: r for r in ROLE_INFO}


def role_label(key):
    return (ROLE_BY_KEY.get(key) or {}).get("name") or key


# ---------------------------------------------------------------------------
# 闸门一：_superlative_is_normal_usage 的豁免口径
# 「最X」的可枚举上下文豁免表 + 一条**句首不豁免**。
# 事故复盘（同族实测）：`最大区别` / `最主要的是` / 「可承受的最高获客成本」这类是
# **普通中文程度用法与内部测算口径**，不是最高级商品宣称。一刀切拦下会把正常文案整篇
# 判死，用户就会干脆关掉整个合规闸门 —— 那比漏报更糟。
# 但句首的「最大区别是…」是标题式宣称，**照拦**。
#
# ⚠️ 诚实说明一处死代码：下面表里的「获客 / 出价 / 预算 / 成本…」这一档，
# 上游的正则只把「最 + 好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎」送进来，
# 所以「最获客」这种组合永远不会命中 —— 也就是说这一档**当前不会被触发**。
# 保留它是因为：它把"内部测算口径不算宣称"这条口径写在了代码里，
# 一旦上游的正则扩宽（比如加一条 `最(低价|划算)`），这一档立刻生效。
# 这是**主动偏离**同族写法的地方，记在这里，不假装它在起作用。
# ---------------------------------------------------------------------------

SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥", "低", "高", "多", "少", "大", "小", "早", "晚",
    # 内部测算口径（当前不会被触发，理由见上）
    "获客", "出价", "预算", "上限", "限价", "限额", "成本", "收益", "性价比", "增速",
)
SUPERLATIVE_OK_RE = re.compile(r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")

# 「第一」的可枚举上下文豁免：长文里「第一年」「第一步」是**序数**，不是排他性宣称。
# 同族原来那条只排除了「第一次」，实测真实稿就被误判（「第一年上了 3 部剧」）。
# 本包新增「眼」：真机实测里视觉角色写「主次关系为主标题第一眼、包装第二眼」——
# 这是**阅读顺序**，不是"第一名"。豁免仍然只认这些枚举后缀，
# 「行业第一的康复效率」这种排他性宣称照拦（后缀是「的」，不在表里）。
FIRST_ORDINAL_AFTER = (
    "次|年|天|步|个|条|款|批|周|月|季|轮|种|点|部|遍|章|节|课|集|届|期|流|层|类"
    "|句|段|行|件|桶|手|版|稿|封|笔|单|场|局|盘|组|队|线|环|圈|代|世|阶|时|印|梯|眼"
)


def _superlative_is_normal_usage(text, m):
    """「最X」后面接的是比较或程度词，**且不在句首** → 判为普通用法，不拦。

    两个条件缺一不可：后文落在豁免表里；命中处不在句首。
    """
    if not m.group(0).startswith("最"):
        return False
    before = (text or "")[:m.start()]
    if not before.strip() or _SENT_END_RE.search(before):
        return False                       # 句首 → 不豁免
    return bool(SUPERLATIVE_OK_RE.match((text or "")[m.end():]))


# 违禁词表（词表思路沿用 xhs-daihuo-live-kit 的 scripts/compliance_check.py：
# 公开经验整理的高/中/低三档 + 类目规则；**不重写第二套**，只按电商上新场景增补）。
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
    (r"绝对(有效|安全|放心|不会|能|可以)|保证(有效|成功|过审|达标|上架)|无效退款|保过",
     "高", "绝对化保证与效果担保"),
    (r"无法举证|不可举证|无从考证|没有依据的?宣称", "中",
     "无法举证的宣称，平台会要求提供依据"),
    (r"根治|治愈|痊愈|药到病除|包治|治疗(好|效果)|疗效|无副作用|零副作用", "高",
     "医疗功效宣称，非药品/医疗器械不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报", "高",
     "投资类收益承诺"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐|官方认证", "高",
     "不得虚构权威背书"),
    (r"催情|壮阳|丰胸|减肥(药|神器)|美白针|生发(神器)", "高",
     "特殊功效与特殊品类敏感词"),
    # —— 以下中风险：不是明令禁止，但需要可举证的依据 ——
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
    # —— 本包增补（电商上新场景特有：伪造社会证明） ——
    (r"刷单|刷量|刷评|好评返现|代发好评|虚假评价", "高",
     "伪造销量/评价属明令禁止"),
    (r"爆卖\s*\d+\s*(万|千|件)|月销\s*\d+\s*万", "中",
     "销量类表述需与后台真实数据一致"),
    (r"包过|必过|保证过审|保证上架|关系过硬", "高",
     "对平台审核结果做承诺，属虚假承诺"),
    (r"[！!]{2,}|[?？]{3,}", "低",
     "标点堆砌，易被判标题党/低质"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}


def compliance_scan(text, levels=None):
    """扫一遍违禁词，返回 (命中列表, 豁免列表)。被豁免的疑似命中**不静默放过**。

    `levels` 可以只扫某一档风险：材料侧与创作者产出侧全扫，评审文书侧只扫高风险。

    去重按**位置**做，不按词做：`我们是销量第一。` 会同时被
    「第一」与「排名第一|销量第一|…」两条模式命中（重叠覆盖同一处文字）。
    同一次出现只该报一条，否则 `_gate_stderr` 里会出现两条长得一样的命中，
    读的人会以为有两处问题。
    """
    hits, exempted, seen = [], [], set()
    spans = []                       # 已报过的 (start, end)，用于跨模式去重
    t = text or ""
    for rx, lvl, why in BANNED_RE:
        if levels is not None and lvl not in levels:
            continue
        for m in rx.finditer(t):
            if _superlative_is_normal_usage(t, m):
                exempted.append({"word": m.group(0), "level": lvl,
                                 "why_exempt": "「最X」后接可枚举的程度/比较词，且不在句首 "
                                               "→ 判为普通中文用法，不是最高级商品宣称",
                                 "context": t[max(0, m.start() - 12):m.end() + 12]})
                continue
            word = m.group(0)
            key = (word, lvl)
            if key in seen:
                continue
            if any(m.start() < e and s < m.end() for s, e in spans):
                continue             # 与已报过的命中重叠 → 同一次出现，不重复报
            seen.add(key)
            spans.append((m.start(), m.end()))
            hits.append({"word": word, "level": lvl, "why": why,
                         "context": t[max(0, m.start() - 12):m.end() + 12]})
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits, exempted


# ---------------------------------------------------------------------------
# 「提到/引用」的语境排除（**只在评审文书侧用**）
#
# 事故复盘（同族 review-board 踩过两轮，本包直接沿用结论，不再踩一次）：
#   1. **引用**：评审会引材料里的问题表述（「『30 天见效』是效果承诺」）
#   2. **提到**：评审会写「明确禁止代发、代拍、刷量」「无法举证为 100% 成立」
#      —— 这是**在禁止它、在指出风险**，不是自己在做违规宣称
# 拿材料侧那把尺子去量评审文书，一天能误报十次，而误报会让人把整个闸门关掉。
#
# ⚠️ **产出侧与材料侧口径分开，是本包与 ecom-image 的重要区别**：
# ecom-image 扫的是**要发布的商品文案**，那里没有任何"引用/提到"的存在理由 ——
# 所以本包对**要发布的创作者产出（选品卡/主图文案/详情页/视觉方案）全档照查**，
# 一个豁免口子都不开。「保证过审、100% 达标」照样拦（自测用例覆盖）。
# 而**评审文书（合规裁决、打回意见）**才走下面这套排除；被排除的**必须留下原因**。
# ---------------------------------------------------------------------------

META_CONTEXT_RE = re.compile(
    "禁止|严禁|不得|不许|不能|不可|避免|杜绝|防范|防止|违规|风险|涉嫌|属于|构成|"
    "无出处|无法举证|不可举证|举证|撤回|删除|删掉|去掉|不实|虚假|夸大|诱导|"
    "不构成|不算|不是|未|没|缺|整改|改为|改成|替换|风险点|红线|合规问题")
_SENT_BOUND = re.compile(r"[。！？!?；;\n]")
META_WINDOW = 24        # 「提到」判定窗口：命中前后各 24 字（不跨句末标点）


def _ctx_window(text, pos, width=META_WINDOW):
    """命中位置前后各 width 个字符（**不跨句末标点**）。

    为什么用"窗口"而不是"整句"：中文里逗号顿号极多，按标点切成小句会把
    「明确禁止代发、代拍、刷量」切碎成「刷量」，标记词正好被切掉 —— 同族实测踩过。
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


def _scan_prose_with_context(prose, material, label=""):
    """评审文书侧扫描：高风险命中再做「引用 / 提到」两道排除，**被排除的留下原因**。

    返回 (fresh, quoted, mentioned, soft, exempted)：
      fresh      真正的命中（闸门拦它）
      quoted     与材料里同词 → 判为引用材料，不计命中（带 not_counted_reason）
      mentioned  窗口内有「禁止/不得/违规…」标记词 → 判为提到/在禁它，不计命中
      soft       中低风险项（评审文书里多为描述性用语，列出来提示人工看，不拦）
      exempted   「最X」普通用法豁免项（同样不静默丢弃）
    """
    hi_all, exempted = compliance_scan(prose, levels=("高",))
    mat_words = {h["word"] for h in compliance_scan(material or "")[0]}
    fresh, quoted, mentioned = [], [], []
    for h in hi_all:
        if h["word"] in mat_words:
            h = dict(h)
            h["not_counted_reason"] = ("该词在**用户给的材料**里已出现 → 判为引用材料，"
                                       "不是评审自己新做的宣称")
            quoted.append(h)
            continue
        pos = prose.find(h["word"])
        if pos < 0:
            fresh.append(h)
            continue
        ctx = _ctx_window(prose, pos)
        m = META_CONTEXT_RE.search(ctx)
        if m:
            h = dict(h)
            h["not_counted_reason"] = (
                "命中前后 {} 字内有「{}」这类标记词 → 判为**提到/在禁止**它，"
                "不是评审自己在做违规宣称".format(META_WINDOW, m.group(0)))
            h["context_window"] = ctx[:60]
            mentioned.append(h)
        else:
            fresh.append(h)
    soft, _ = compliance_scan(prose, levels=("中", "低"))
    if label:
        for h in fresh:
            h["in"] = label
    return fresh, quoted, mentioned, soft, exempted


def compliance_scan_material(text):
    """**材料侧**：用户给的原始资料。全档（高/中/低）全查，不做任何语境排除。

    材料是会被拿去做宣传的源头，宁可多报。
    """
    hits, exempted = compliance_scan(text)
    return {"side": "material", "hits": hits, "exempted": exempted,
            "ok": not hits,
            "why": ("材料里命中 {} 处违禁/高风险表述".format(len(hits)) if hits else "")}


def compliance_scan_creator(text, label):
    """**创作者产出侧**（主图文案 / 详情页）：全档全查，**一个豁免口子都不开**。

    这些文字就是准备发出去的商品文案本身，没有"引用"或"提到"的存在理由。
    """
    hits, exempted = compliance_scan(text)
    return {"side": "creator", "label": label, "hits": hits, "exempted": exempted,
            "ok": not hits,
            "why": ("{} 命中 {} 处违禁/高风险表述".format(label, len(hits)) if hits else "")}


# ---------------------------------------------------------------------------
# 创作者产出里的「**职责是审**」的那些字段
#
# 事故复盘（本包真机第一次跑就抓到的，不是假想）：选品卡的风险清单里写着
# 「功效宣称「100% 有效改善颈椎、行业第一的康复效率」没有检测报告支撑，
#  且含绝对化用语与最高级表述」—— 这是**在指出风险**，不是在宣称效果。
# 但拿发布口径去量它，12 处命中全是这一类，整份产出被判违规、流水线被拦，
# 而它恰恰是**唯一把问题说清楚的那份东西**。误报会让人把整个闸门关掉。
#
# 所以创作者产出**按字段分两类**，这是本包与 ecom-image 的又一处口径差别：
#   · **面客字段**（主图文案 / 详情页 / 选品卡卖点）→ 零豁免，照发布口径查
#   · **审类字段**（风险评估 / 依据 / 缺口 / 待补材料）→ 允许「引用材料」与
#     「提到/在禁止」两类排除，**被排除的必须留下原因**，照样列在案上可复查
# 闸门还有牙：「保证过审，效果 100% 达标」这种没有任何标记词的小句照样拦。
# ---------------------------------------------------------------------------

REVIEW_FIELD_LABELS = ("风险", "依据", "缺口", "待补材料", "否决理由", "总结",
                       "复核", "who_can_fix", "ask_user",
                       # 视觉方案里**不上画面**的字段（真机实测踩出来的）：
                       # 视觉写「主次关系为主标题第一眼、包装第二眼」，这是**内部的版式说明**，
                       # 不是图上的字。拿面客口径量它 → 4 处「第一」误报、闸门被假警报拦下。
                       "版式说明", "平台适配", "可产性说明")


def _label_is_review(label):
    """这个字段是不是「审类字段」（职责是审/是内部说明，不是面客文案）？"""
    return any(x in (label or "") for x in REVIEW_FIELD_LABELS)


def scan_creator_field(label, text, material):
    """扫一个创作者产出字段：面客字段零豁免，审类字段开引用/提到排除。

    命中一律带上 `in`（字段名）与 `field_kind`：出问题时必须一眼看出**是哪一处的字**，
    不然读报告的人只看到「命中 4 处」却不知道去哪改（真机实测踩过）。
    """
    if not _label_is_review(label):
        r = compliance_scan_creator(text, label)
        for h in r["hits"]:
            h["in"] = label
            h["field_kind"] = "面客字段（零豁免）"
        return r["hits"], [], [], r["exempted"]
    fresh, quoted, mentioned, _soft, exempted = _scan_prose_with_context(
        text, material, label)
    for h in fresh:
        h["in"] = label
        h["field_kind"] = "审类字段（已开引用/提到排除后仍然命中）"
    for h in quoted + mentioned:
        h["in"] = label
    return fresh, quoted, mentioned, exempted


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
# 模板没替换干净的典型形态：`{}` / `[待填]` / `XXX` / `（此处省略）` / `TODO`。
# `[1]`（引用序号）、`[图 2]`（配图位）是**正常写法**，不按括号内容一刀切。
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    # ⚠️ 这条的口径是本包自测时专门收紧的，理由只有一条：**别误报**。
    #   · 双层必须**里面有内容**（`{{标题}}`）—— 骨架被当正文写进去了，这才是残留。
    #   · 单层必须**里面有内容**（`{标题}`）—— 同上。
    #   · **空的 `{}` / `{ }` 一律放过**：它是 `json.dumps({})` 的正常产物，
    #     在正常提示词里到处都是；把它判成"模板没替换干净"就是假警报。
    # 代价（诚实说明）：`{{}}` / `{ }` 这种**没有内容的**占位符抓不到。
    # 但那种空占位在电商文案里没有意义，而误报会让用户把整个闸门关掉 —— 那更糟。
    (re.compile(r"\{\{\s*[\u4e00-\u9fffA-Za-z0-9_]+\s*\}\}"
                r"|\{\s*[\u4e00-\u9fffA-Za-z0-9_]+\s*\}"), "{}",
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
# 事故复盘（同族，两例）：提示词里写过正例 → 模型直接产出同构句；其中一例
# 全批**最高分**的那条一字不差就是提示词里的示例 —— "抄了标准答案"被当成"真的最好"。
# 四角色协作同样会踩：提示词里写了"一条好的视觉方案长什么样"，模型就把那句填进字段。
#
# 三条命中判据（任一即命中）：
#   exact    去掉标点后完全相同
#   jaccard  字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
#   contain  示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（示例被夹带进更长的句子里）
#
# 【为什么必须有第三条】Jaccard 的分母是两份二元组的**并集**，产出越长，
# 示例那一侧被摊薄得越狠 —— 示例原样嵌进去也会掉到 0.75 以下侥幸放行。
#
# 【为什么第三条必须有适用窗口】覆盖度只看"示例被抄了多少"，不看产出有多长，
# 所以对**短示例**会饱和：示例归一后只有 3~5 字时，长文本被动凑齐两个二元组
# 就有 0.5 的覆盖度 —— 离 0.60 只剩 0.10 余量。
# 同族在真实语料上量过（105,863 字符 / 3,253 句）：13~20 字示例各长度比档位
# 覆盖度上限 0.125~0.333、≥0.60 命中 0 条；2~5 字短示例长度比 ≥2 时上限 0.500。
# 所以 contain 只在**两个条件都满足**时适用：
#   1. 目标片段长度 ≤ 示例长度 × ECHO_CONTAIN_MAX_RATIO（长度比窗口）
#   2. 示例归一后长度 ≥ ECHO_CONTAIN_MIN_SAMPLE（二元组数量够用）
# 不适用的地方记进 `contain_skipped`，**不静默略过**。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6          # 长度守卫的绝对下限，防极短串的二元组噪声
ECHO_CONTAIN_MAX_RATIO = 3.0    # contain 适用窗口：目标长度 ≤ 示例长度 × 该系数
ECHO_CONTAIN_MIN_SAMPLE = 8     # contain 适用窗口：示例归一后至少这么长

# 提示词里出现过的**跨主题**示例（正常不该被抄）。新增提示词示例必须登记到这里。
# 跨主题 = 与任何真实电商选题都不搭（电动车充电桩），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
PROMPT_SAMPLES = [
    "电动车充电桩到底值不值得装，三个理由",
    "小区充电桩的安装条件别只看价格",
    "先看安装条件，再谈价格",
]

# 这三个示例里，第 3 条只有 9 字（归一后 9 字），**大于** ECHO_CONTAIN_MIN_SAMPLE=8，
# 所以它仍然走 contain 判据；长度比窗口是 3.0，即只有 ≤27 字的片段才会被 contain 判据审。
# 这不是拍脑袋：短示例正是会饱和的那一类，窗口收窄后 9 字示例只对"短片段"生效，
# 对长句不再产生虚假命中。


def _norm_anchor(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的文本往往只改标点（`，`↔`、`↔空格），所以必须先抹平标点再看。
    """
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。**相对阈值**。

    绝对阈值（比如 12）在示例只有 15~17 字时占了示例长度的七成以上，
    会把「≤11 字的截断照抄」整档放过。
    """
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_anchor(sample)) // 2)


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

    为什么立场重叠度不能直接用 Jaccard：两席意见的篇幅天然不同，
    Jaccard 的分母是并集，篇幅差一大就被摊薄，"说了同样的话"反而测不出来。
    用 min 归一后，「短的那份有多少内容出现在长的那份里」才是要问的问题。
    """
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(min(len(ba), len(bb)))


def prompt_echo(text, samples=None):
    """文本是否与提示词里的示例"抄得太近"。

    返回 (是否命中, 分数, 撞上的示例, 判据, 被窗口跳过的判据列表)。
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
        # contain 的适用窗口：长度比 + 示例长度，两个都满足才用它
        if len(target) > ECHO_CONTAIN_MAX_RATIO * max(1, len(ns)):
            skipped.append({"rule": "contain",
                            "why": "目标长度 {} > 示例长度 {} × {}".format(
                                len(target), len(ns), ECHO_CONTAIN_MAX_RATIO)})
            continue
        if len(ns) < ECHO_CONTAIN_MIN_SAMPLE:
            skipped.append({"rule": "contain",
                            "why": "示例归一后仅 {} 字 < {}，二元组太少、覆盖度会饱和"
                                   .format(len(ns), ECHO_CONTAIN_MIN_SAMPLE)})
            continue
        base = _bigrams(s)
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
    """把「contain 判据被适用窗口跳过」的记录按原因合并（一条产出会有上百次）。"""
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
# 闸门四：锚点校验（每条意见必须引用**真实原文**，编造引文剔出）
#
# 一份四角色协作最没用的形态，是所有人都在说"建议优化、注意合规"：
# 谁也不说清是哪一句。所以本包不采信模型的引文，而是**本地校验**：
# 它引的那句话在不在**它自己那份材料**里？
#
# 四个角色各锚各的：
#   pick       → 商品资料原文
#   copy       → 商品资料原文（文案的依据必须能在资料里找到）
#   visual     → 商品资料 + 该位文案（视觉引的可能是文案那一行）
#   compliance → 最终物料全文（它审的是物料，引的必须是物料里真实存在的字）
#
# 三级递进：exact / substring（精确子串，低门槛）/ fuzzy（统计判据，高门槛）。
# 未锚定率 > ANCHOR_MAX_MISS → 判「定位失败」，压分 + 标红 + stderr 汇总 + 退出码 3。
# ---------------------------------------------------------------------------

ANCHOR_MIN_SUBSTR = 4     # 精确子串匹配的最低长度（低风险判据，门槛可以矮）
ANCHOR_MIN_CHARS = 8      # 模糊匹配的最低长度（二元组太少会虚高，门槛必须高）
ANCHOR_SIM = 0.55         # 模糊匹配阈值
ANCHOR_MAX_MISS = 0.40    # 未锚定率超过它就判「定位失败」

# 为什么两种匹配用**两个不同的长度门槛**：「引文恰好是某句的连续片段」是**精确**判断，
# 短一点也几乎不会误伤；而「最像的那一句」是**统计**判断，短串的二元组集合太小，
# 相似度会虚高。一个门槛管两件事，就会出现"6 个字的真实引文被判成幻觉"这种
# 把真问题算成假问题的情况 —— 它会直接污染未锚定率。


def verify_anchor(quote, sentences, norms=None):
    """把引文锚定到目标文本的某一句话上。返回 (ok, rule, index)。"""
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


def anchor_records(records, text, quote_field="quote", label=""):
    """给一批记录的引文做锚点校验，返回 (锚定成功的, 未锚定的, 统计)。

    锚定成功的那条会把引文**就地修正成目标文本里的真实句子**（`sentence` 字段）——
    模型引半句、连引两句时，台账里要显示原文本原文，不是模型的转述。
    """
    sents = split_sentences(text)
    norms = [_norm_anchor(s) for s in sents]
    ok_list, bad_list = [], []
    for it in records or []:
        if not isinstance(it, dict):
            continue
        quote = str(it.get(quote_field) or "").strip()
        good, rule, idx = verify_anchor(quote, sents, norms)
        item = dict(it)
        item["anchor_rule"] = rule
        if label:
            item.setdefault("in", label)
        if good:
            item["sentence"] = sents[idx]
            item["sent_no"] = idx + 1
            ok_list.append(item)
        else:
            item["why_unverified"] = ("引文在目标文本里找不到（归一化后不匹配任一整句，"
                                      "模糊相似度 < {:.2f}）——判为锚点幻觉，不作为交付内容"
                                      .format(ANCHOR_SIM))
            bad_list.append(item)
    total = len(ok_list) + len(bad_list)
    stat = {
        "ok": True, "total": total, "verified": len(ok_list), "unanchored": len(bad_list),
        "miss_rate": round(len(bad_list) / float(total), 3) if total else 0.0,
        "rules": {},
    }
    for it in ok_list:
        r = it.get("anchor_rule") or "-"
        stat["rules"][r] = stat["rules"].get(r, 0) + 1
    if total and stat["miss_rate"] > ANCHOR_MAX_MISS:
        stat["ok"] = False
        stat["why"] = ("{} 条意见里 {} 条的引文在目标文本里找不到（未锚定率 {:.0%} > {:.0%}）"
                       "——模型在编引文，这份产出不可执行".format(
                           total, len(bad_list), stat["miss_rate"], ANCHOR_MAX_MISS))
    return ok_list, bad_list, stat


# ---------------------------------------------------------------------------
# 闸门五 / 六 / 七：主图位完整性、裁决完整性、成本上限
# （实现分别在 validate_visual / validate_ruling / CostTracker）
# ---------------------------------------------------------------------------

# 每个位的文案字数上限（超了就是排版事故：主图上没人会读第 12 个字）。
SLOT_MAX_CHARS = {
    "s1_benefit": 14,
    "s2_spec": 40,
    "s3_detail": 24,
    "s4_scene": 20,
    "s5_trust": 30,
}

# 选品角色的本地一票否决线（不依赖模型的措辞，模型给"可主推"也拦得住）：
PICK_MARGIN_FLOOR = 0.20        # 退货后毛利 / 售价 < 20% → 本地判「放弃」
PICK_RETURN_RATE_CEIL = 0.40    # 退货率 > 40% → 本地判「放弃」
PICK_REQUIRED_CERT = ("食品", "保健", "化妆品", "医疗器械", "儿童", "3C", "电器")


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

_ECHO_WARNING = (
    "跨主题示例（**仅供理解「什么算不合格的写法」，禁止把示例原句抄进任何字段**；"
    "抄了会被本地闸门拦下并让整份产出作废）：\n"
    + "".join("  · {}\n".format(s) for s in PROMPT_SAMPLES)
)

SYSTEM_BASE = (
    "你是一个电商上新小组里的一个角色，只对自己的目标函数负责。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 不许编造用户材料里没有的数字、材质、认证、检测结论、销量、评价、资质。\n"
    "  2. 每条判断要能指回材料里的**原话**（`quote` 必须原样摘录材料里的连续一小段，"
    "不得改写、不得概括、不得凭空编造）。引不出来就别写。\n"
    "  3. 不许写「整体不错」「建议加强」这类无法执行的泛泛之谈。\n"
    "  4. 明确禁止：绝对化用语（最高级、「第一」、100%、国家级），"
    "以及任何形式的伪造销量/评价/资质/检测报告。\n"
    "  5. 只输出 JSON，不要解释文字、不要 Markdown 代码围栏。\n"
)

PICK_SYSTEM = (SYSTEM_BASE
               + "你现在的角色是【选品】：只关心「这个品能不能卖、毛利与资质能不能兜住」。\n"
                 "你的结论可以是负面的 —— 该放弃就放弃，该否决就否决。\n"
                 "**不要**为了让人高兴而给出乐观结论。\n")

COPY_SYSTEM = (SYSTEM_BASE
               + "你现在的角色是【文案】：只关心「主图与详情页的文字能不能转化」。\n"
                 "你看不到视觉与合规的结论，也不需要猜他们的意见。\n"
                 "**不要**为了转化而写违规词；被上游打回时按打回意见逐条改。\n")

VISUAL_SYSTEM = (SYSTEM_BASE
                 + "你现在的角色是【视觉】：只关心「每张图到底画什么、能不能真的做出来」。\n"
                   "你必须**诚实**判断可产性：素材不够就说做不出来，并给出理由码。\n"
                   "**不要**为了让流程跑通而把没有素材的图标的 `producible`。\n")

COMPLIANCE_SYSTEM = (SYSTEM_BASE
                     + "你现在的角色是【合规】：只关心「广告法与平台规则，这套物料能不能发」。\n"
                       "你可以放行、可以打回、也可以**一票否决**。\n"
                       "**不要**因为别人已经做了很多轮就放行；也不要在有依据时假装没问题。\n")


# ---------------------------------------------------------------------------
# 商品资料的解析（零成本、纯本地）
#
# 资料格式就一种：`键：值` 一行一条（也认 `键: 值`）。这不是要发明格式 ——
# 是为了让**成本参数**能被本地确定性地算出来（毛利、保本 CPA）。
# 只有模型算的账不可能进闸门：模型会把 39.9 写成 39、把退货率算错，
# 而「这个品能不能卖」正是本包第一个角色要拍的板。
#
# 认不出来的行一律当"自由文本材料"，照样喂给角色 **且照样扫合规**。
# ---------------------------------------------------------------------------

MATERIAL_TEMPLATE = """商品名：便携榨汁杯 600ml
类目：小家电 / 厨房电器
平台：taobao
售价：99
成本：42
物流：6
包材：2
佣金率：0.05
退货率：0.12
资质：3C 认证（证书编号可查）、食品接触材料检测报告
素材：实拍图 6 张、包装图 2 张、参数表 1 份
卖点：一杯一袋、单手开盖、可整杯冲洗
详情：杯身 Tritan，刀头 304 不锈钢可拆洗，USB-C 充电，容量 600ml
"""

# 成本参数字段（本地确定性计算用）
COST_FIELDS = {
    "售价": "price", "价格": "price",
    "成本": "cost", "进货价": "cost", "拿货价": "cost",
    "物流": "shipping", "运费": "shipping",
    "包材": "packing", "包装费": "packing",
    "佣金率": "commission_rate", "佣金": "commission_rate",
    "退货率": "return_rate",
}
MATERIAL_ALIASES = {
    "商品": "商品名", "商品名称": "商品名", "品名": "商品名", "产品": "商品名",
    "品类": "类目", "分类": "类目",
    "目标平台": "平台",
    "资质证书": "资质", "认证": "资质",
    "素材清单": "素材", "图片素材": "素材",
    "核心卖点": "卖点", "产品卖点": "卖点",
    "详情页资料": "详情", "产品参数": "详情", "规格": "详情",
}
MATERIAL_KEYS = ("商品名", "类目", "平台", "资质", "素材", "卖点", "详情",
                 "目标人群", "风险提示", "备注")
_LINE_KV = re.compile(r"^\s*([^：:\s][^：:]{0,15})\s*[：:]\s*(.*)$")


def _to_float(raw):
    """把「39.9」「39.9 元」「5%」「0.05」都读成一个数。读不出返回 None。"""
    s = str(raw or "").strip()
    if not s:
        return None
    pct = "%" in s or "％" in s
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    if not m:
        return None
    v = float(m.group(0))
    if pct:
        v = v / 100.0
    return v


def parse_material(text):
    """把 `键：值` 形式的商品资料解析成结构化字段。

    返回 {"fields": {...}, "free_lines": [...], "raw": 原文}。
    解析不出来的行**不丢**：它们进 free_lines，照样喂给角色、照样扫合规。
    """
    fields, free_lines = {}, []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        m = _LINE_KV.match(line)
        if not m:
            free_lines.append(line)
            continue
        key = m.group(1).strip()
        val = m.group(2).strip()
        key = MATERIAL_ALIASES.get(key, key)
        if key in COST_FIELDS or key in MATERIAL_KEYS:
            if key in fields:
                fields[key] = fields[key] + "；" + val      # 同键多行 → 合并
            else:
                fields[key] = val
        else:
            free_lines.append(line)
    return {"fields": fields, "free_lines": free_lines, "raw": text or ""}


def material_numbers(mat):
    """从资料里读出成本参数（本地确定性）。缺的字段是 None，**不猜**。"""
    f = mat.get("fields") or {}
    out = {}
    for key, name in COST_FIELDS.items():
        if key in f:
            v = _to_float(f[key])
            if v is not None and name not in out:
                out[name] = v
            continue
    # `佣金` 这种键可能是「0.05」也可能是「5 元」——按 <1 当比率、>=1 当金额处理并如实记录
    if "commission_rate" in out and out["commission_rate"] >= 1.0:
        out["commission_note"] = ("资料里的佣金值是 {}，按**比率 <1 / 金额 >=1** 的口径"
                                  "无法判定，本地未把它折进毛利".format(out["commission_rate"]))
        out["commission_rate"] = None
    if "return_rate" in out and out["return_rate"] > 1.0:
        out["return_rate"] = out["return_rate"] / 100.0    # 「12」这种写法按百分数读
    return out


def margin_calc(mat):
    """本地确定性毛利测算 —— 沿用「小红书带货作战包」的公式口径（不另立一套）：

        单件毛利   = 售价 - 成本 - 物流 - 包材
        佣金后毛利 = 单件毛利 - 售价 × 佣金率
        退货后毛利 = 佣金后毛利 × (1 - 退货率)
        保本 CPA   = 退货后毛利（投放超过就是纯亏）
        建议 CPA 上限 = 退货后毛利 × 0.5

    缺参数时返回 `missing` 列表并**不给数字**（不猜、不编）。
    """
    n = material_numbers(mat)
    need = ("price", "cost")
    missing = [k for k in ("price", "cost", "shipping", "packing",
                           "commission_rate", "return_rate") if n.get(k) is None]
    rec = {"inputs": {k: n.get(k) for k in
                      ("price", "cost", "shipping", "packing",
                       "commission_rate", "return_rate")},
           "missing": missing, "unit_note": n.get("commission_note")}
    if any(n.get(k) is None for k in need):
        rec["ok"] = False
        rec["why"] = ("算不出账：资料里缺 {}".format(
            "、".join(k for k in missing if k in ("price", "cost"))))
        return rec
    price, cost = n["price"], n["cost"]
    ship = n.get("shipping") or 0.0
    pack = n.get("packing") or 0.0
    comm = n.get("commission_rate") or 0.0
    ret = n.get("return_rate") or 0.0
    gross = price - cost - ship - pack
    after_comm = gross - price * comm
    after_ret = after_comm * (1.0 - ret)
    rec.update({
        "ok": True,
        "gross": round(gross, 2),
        "after_commission": round(after_comm, 2),
        "after_return": round(after_ret, 2),
        "margin_rate_on_price": round(after_ret / price, 4) if price else None,
        "breakeven_cpa": round(after_ret, 2),
        "suggested_cpa_cap": round(after_ret * 0.5, 2),
        "formula": "退货后毛利 = (售价-成本-物流-包材-售价×佣金率)×(1-退货率)",
    })
    return rec


def required_certs(mat):
    """这个类目按常规需要哪些资质（本地启发式，只为在选品卡里提示缺口）。"""
    cat = str((mat.get("fields") or {}).get("类目") or "")
    hit = [k for k in PICK_REQUIRED_CERT if k in cat]
    return hit


# ---------------------------------------------------------------------------
# 信息隔离：每个角色**实际收到什么**
#
# 这是本包区别于"多跑几个角色"的核心机制，所以它不算提示词工程，算**代码**：
# 喂给某个角色的上文只挑它该看到的字段（见 ROLE_INFO 的 sees / cannot_see）。
# `role_input` 是唯一的入口 —— 想偷偷塞点上游自评进去，必须在函数体里写出来，
# 而 role_input 的输出会原样打进 stderr（`--show-inputs`，默认开），当场就能核对。
# ---------------------------------------------------------------------------

def _slim_pick_for_downstream(pick_card):
    """选品卡 → 下游角色看得到的**结构化字段**（丢掉它的长篇论述与自评）。

    事故复盘（同族内容团队踩过）：把上游的完整结论原文传下去，下游会顺着它的措辞
    复述一遍 —— 四份产出读起来像一个声音。所以只传"事实"，不传"态度"。
    """
    pc = pick_card if isinstance(pick_card, dict) else {}
    return {
        "product": pc.get("product") or pc.get("商品名") or "",
        "sellpoints": [s for s in (pc.get("sellpoints") or []) if isinstance(s, dict)],
        "margin": pc.get("margin") or {},
        "certs": pc.get("certs") or {},
        "risks": [r for r in (pc.get("risks") or []) if isinstance(r, dict)],
    }


def slim_copy_for_review(copy_obj):
    """文案 → 合规看得到的部分：**只给版面文字**。

    合规审的是"发出去长什么样"，不是文案的内部工作状态；依据、自评这类字段一律不带。
    """
    c = copy_obj if isinstance(copy_obj, dict) else {}
    slots = c.get("slots") if isinstance(c.get("slots"), dict) else {}
    return {
        "slots": {k: str(slots.get(k) or "") for k in SLOT_KEYS},
        "detail": (c.get("detail") if isinstance(c.get("detail"), dict) else {}),
    }


def slim_visual_for_review(visual_obj):
    """视觉方案 → 合规看得到的部分（**白名单**）。

    事故复盘（本包自测真机抓到的，不是假想）：合规角色原本拿的是视觉对象**整体**，
    于是 `.self_score`（视觉对自己的 8.8 分）被一起喂了进去 —— 这就破坏了
    "合规看不到任何角色的自评"这条隔离。所以改成**白名单**：
    只放版式与文字相关的字段，任何自评/打分字段都不可能漏出去。
    """
    v = visual_obj if isinstance(visual_obj, dict) else {}
    out = []
    for s in (v.get("slots") or []):
        if not isinstance(s, dict):
            continue
        t = s.get("text") if isinstance(s.get("text"), dict) else {}
        out.append({
            "slot": s.get("slot"), "scene": s.get("scene"), "layout": s.get("layout"),
            "productivity": s.get("productivity"), "reason_code": s.get("reason_code"),
            "why": s.get("why"), "platform_note": s.get("platform_note"),
            "text": {"position": t.get("position"), "chars": t.get("chars"),
                     "max_chars": t.get("max_chars"), "style": t.get("style")},
        })
    return {"slots": out}


def role_input(role, mat, *, pick_card=None, copy_obj=None, visual=None,
               rejects=None, ruling=None, material_text=None):
    """算出**该角色这一轮实际收到的输入**（本地强制隔离）。

    返回一个 dict，同时用于两件事：拼提示词、打隔离证据到 stderr。
    """
    base = {"商品资料": (material_text if material_text is not None
                     else (mat.get("raw") if isinstance(mat, dict) else "") or "")}
    if role == "pick":
        return dict(base)
    if role == "copy":
        slim = _slim_pick_for_downstream(pick_card)
        out = dict(base)
        out["选品卡的卖点与证据"] = slim["sellpoints"]
        out["本地毛利测算"] = slim["margin"]
        out["选品的风险提示"] = slim["risks"]
        if rejects:
            # 打回意见**要传**（不然文案没法改），但只传"要求"，不传上一轮的自评
            out["被视觉打回的意见"] = rejects
        return out
    if role == "visual":
        out = dict(base)
        c = copy_obj if isinstance(copy_obj, dict) else {}
        out["主图五位的文案（只给文字）"] = {
            k: (c.get("slots") or {}).get(k) for k in SLOT_KEYS}
        out["详情页文案"] = c.get("detail") or ""
        out["素材清单（来自用户资料）"] = (mat.get("fields") or {}).get("素材") or ""
        if rejects:
            out["上一轮被你自己打回的位（本轮重点看这些）"] = rejects
        return out
    if role == "compliance":
        out = dict(base)
        out["最终物料"] = {
            "选品卡要点": _slim_pick_for_downstream(pick_card),
            "主图五位文案": slim_copy_for_review(copy_obj)["slots"],
            "详情页文案": slim_copy_for_review(copy_obj)["detail"],
            "五位视觉方案": slim_visual_for_review(visual),
        }
        if ruling:
            out["上一轮你自己的裁决（本轮复裁）"] = {
                "verdict": ruling.get("verdict"),
                "violations": ruling.get("violations"),
                "required_fixes": ruling.get("required_fixes"),
            }
        return out
    return base


def isolation_note(role, payload):
    """把「这个角色收到了什么」压成一行可核对的证据。"""
    keys = [k for k in payload.keys() if k != "商品资料"]
    parts = []
    for k in keys:
        v = payload[k]
        if isinstance(v, str):
            parts.append("{}={} 字".format(k, len(v)))
        elif isinstance(v, list):
            parts.append("{}={} 条".format(k, len(v)))
        elif isinstance(v, dict):
            parts.append("{}={} 项".format(k, len(v)))
        else:
            parts.append("{}={}".format(k, bool(v)))
    return "角色[{}] 输入 = 商品资料 {} 字{}".format(
        role_label(role), len(payload.get("商品资料") or ""),
        ("；另有 " + "、".join(parts)) if parts else "（**只有商品资料**）")


def _dump_role_input(role, payload, enabled=True, stream=None):
    """把角色实际收到的输入摘要打进 stderr（默认开，可 `--hide-inputs` 关掉）。"""
    if not enabled:
        return
    stream = stream or sys.stderr
    stream.write("  · " + isolation_note(role, payload) + "\n")
    blocked = {
        "pick": "（第一个角色，无上游）",
        "copy": "看不到视觉的可产性结论、看不到合规口径、看不到任何角色的自评",
        "visual": "看不到选品卡的风险清单细节、看不到合规结论、看不到文案的自评",
        "compliance": "看不到任何角色的自我评价与内部打分，只拿到产出物本身",
    }.get(role, "")
    if blocked:
        stream.write("    └ 隔离：{}\n".format(blocked))


# ---------------------------------------------------------------------------
# 提示词构造
# ---------------------------------------------------------------------------

def _product_block(mat):
    """商品资料原样贴回去，并标注哪些字段是**本地解析出来的**（可核对）。"""
    f = mat.get("fields") or {}
    lines = []
    for k in MATERIAL_KEYS + ("目标人群", "风险提示", "备注"):
        if f.get(k):
            lines.append("  · {}：{}".format(k, f[k]))
    free = mat.get("free_lines") or []
    if free:
        lines.append("  · 其他材料：")
        lines.extend("      " + x for x in free)
    if not lines:
        lines.append("  （用户只给了自由文本，见下方原文）")
    return "商品资料（用户给的原始材料，**事实只能来自这里**）：\n" + "\n".join(lines)


def build_pick_prompt(mat, target_platform, fixes=None):
    n = material_numbers(mat)
    mg = margin_calc(mat)
    certs = required_certs(mat)
    mg_lines = []
    if mg.get("ok"):
        mg_lines.append("  · 本地已按公式算出（口径：单件毛利 = 售价-成本-物流-包材；"
                        "佣金后毛利 = 单件毛利 - 售价×佣金率；退货后毛利 = 佣金后毛利×(1-退货率)）：")
        mg_lines.append("      售价 {price} / 成本 {cost} / 物流 {shipping} / 包材 {packing} / "
                        "佣金率 {commission_rate} / 退货率 {return_rate}".format(
                            **{k: ("缺" if v is None else v) for k, v in mg["inputs"].items()}))
        mg_lines.append("      单件毛利 {} · 佣金后毛利 {} · **退货后毛利 {}** · 保本 CPA {} · "
                        "建议 CPA 上限 {}".format(
                            mg["gross"], mg["after_commission"], mg["after_return"],
                            mg["breakeven_cpa"], mg["suggested_cpa_cap"]))
        mg_lines.append("      退货后毛利 / 售价 = {:.1%}".format(mg["margin_rate_on_price"] or 0))
        mg_lines.append("  本地判定线（**不因你的措辞而改变**）：退货后毛利占售价 < 20% 判「放弃」；"
                        "退货率 > 40% 判「放弃」；命中则整条流水线不会往下走。")
    else:
        mg_lines.append("  · " + (mg.get("why") or "本地算不出账"))
        mg_lines.append("  · 缺的参数：{} —— **不要在选品卡里编出这些数字**，"
                        "把 `need_materials` 列清楚。".format("、".join(mg.get("missing") or [])))
    if mg.get("unit_note"):
        mg_lines.append("  · " + mg["unit_note"])
    cert_line = ("  · 该品类的常规资质要求（本地启发式，仅供参考）：{}".format("、".join(certs))
                 if certs else "  · 本地未从类目里认出必配资质（**不代表不需要**）")
    pricing = ("  · 目标平台：{}（{}）".format(PLATFORM_LABEL[target_platform], target_platform))
    fix_block = ""
    if fixes:
        fix_block = (
            "\n⚠️ 这是**重开**：合规角色上一轮打回了这套物料，其中有 {} 条整改要求"
            "**只有你能执行**（文案改不了商品名与卖点体系）。本轮必须逐条落到选品卡上；"
            "做不到的，就在 `need_materials` 里说清要用户补什么：\n".format(len(fixes))
            + "".join("  · {}\n".format(x) for x in fixes)
            + "  你**看不到**合规的完整裁决书，只有这些要求 —— 这是刻意的信息隔离。\n")
    return (
        "请以【选品】的角色，对这个品做一次能不能卖的判断。\n"
        "\n" + _product_block(mat) + "\n"
        "\n下面是本地算好的账，你可以质疑它，但**不许改它的数字**：\n"
        + "\n".join(mg_lines) + "\n"
        + cert_line + "\n" + pricing + "\n"
        + fix_block
        + "\n" + _ECHO_WARNING
        + "\n你只对自己的目标函数负责：这个品**能不能卖**、毛利够不够、资质与合规风险兜不兜得住。\n"
          "结论可以是负面的。如果你认为不该做，就把 `venv_veto` 设为 true 并说清依据。\n"
        + "\n按要求只输出这个 JSON 对象：\n"
        + json.dumps({
            "product": "商品名",
            "category": "类目",
            "target_platform": target_platform,
            "sellpoints": [{
                "point": "一条卖点（一句话）",
                "evidence": "这条卖点的依据：材料里的哪个字段/哪句话",
                "quote": "材料里**原样**的连续一小段（必须能逐字找到）",
            }],
            "margin": {
                "price": 0, "cost": 0, "shipping": 0, "packing": 0,
                "commission_rate": 0, "return_rate": 0,
                "after_return_margin": 0, "breakeven_cpa": 0, "note": "对本地测算的复核意见",
            },
            "certs": {
                "held": ["材料里明确写了的资质"],
                "required_for_category": ["该品类按常规需要的资质"],
                "missing": ["材料里**没有**的资质（不许编）"],
            },
            "risks": [{
                "risk": "风险是什么",
                "level": "高|中|低",
                "quote": "材料里原样的一小段（必须是真实的）",
                "why": "为什么这是风险",
                "who_can_fix": "要谁能解决（用户补材料 / 换规格 / 换品）",
            }],
            "conclusion": "可主推|可测试|放弃",
            "venv_veto": False,
            "veto_reason": "若 venv_veto 为 true，这里写清否决理由；否则空字符串",
            "need_materials": ["要用户补的真实材料（没有就空数组）"],
        }, ensure_ascii=False, indent=1)
        + "\n补充要求：sellpoints 3~6 条，每条都必须能在材料里找到原话依据；"
          "缺依据的卖点**不要写**。risks 最多 8 条，按 level 从高到低。"
          "`venv_veto` 只有在你认为这个品**根本不该做**时才设 true。\n"
        + "\n===== 商品资料原文开始 =====\n" + (mat.get("raw") or "")
        + "\n===== 商品资料原文结束 =====\n"
    )


def build_copy_prompt(mat, target_platform, slim_pick=None, rejects=None):
    pick_block = []
    if slim_pick:
        pick_block.append("选品角色的结构化输出（**只有事实字段，没有它的论述与自评**）：")
        for s in slim_pick.get("sellpoints") or []:
            pick_block.append("  · 卖点：{}（依据：{}）".format(
                s.get("point") or s.get("sellpoint") or "-", s.get("evidence") or "-"))
        mg = slim_pick.get("margin") or {}
        if mg:
            pick_block.append("  · 本地毛利测算：退货后毛利 {}，保本 CPA {}".format(
                mg.get("after_return"), mg.get("breakeven_cpa")))
        risks = slim_pick.get("risks") or []
        if risks:
            pick_block.append("  · 选品标出的风险（**文案里不许弱化它**）：" + "；".join(
                "{}（{}）".format(r.get("risk") or "-", r.get("level") or "-")
                for r in risks))
    reject_block = []
    if rejects:
        reject_block.append("视觉角色**已经明确说做不出来**的位，本轮必须改到能产出，"
                            "或明确换成能在现有素材下做出的方案：")
        for r in rejects:
            reject_block.append("  · {}：理由码 {} —— {}".format(
                SLOT_LABEL.get(r.get("slot"), r.get("slot")),
                r.get("reason_code") or "-", r.get("why") or "-"))
        reject_block.append("  ⚠️ 你**看不到**视觉角色的内部打分与完整方案，只有这些要求 —— "
                            "这是刻意的信息隔离，不要试图猜测它的其他意见。")
    slot_lines = []
    for k in SLOT_KEYS:
        slot_lines.append("  · {}（{}）：一行不超过 {} 个字".format(
            SLOT_LABEL[k], SLOT_ASK[k], SLOT_MAX_CHARS[k]))
    return (
        "请以【文案】的角色，写这套上新物料里的**文字**部分。\n"
        "\n" + _product_block(mat) + "\n"
        + ("\n" + "\n".join(pick_block) + "\n" if pick_block else "")
        + ("\n" + "\n".join(reject_block) + "\n" if reject_block else "")
        + "\n主图五个位（**每一位的文案独立写，缺一个位就是交付不完整**）：\n"
        + "\n".join(slot_lines) + "\n"
        "\n" + _ECHO_WARNING
        + "\n纪律：\n"
          "  1. 五位的文案**字数上限是硬约束**（主图上没人会读第 12 个字），超了会被本地闸门拦下。\n"
          "  2. 不许编造材料里没有的数字、认证、检测结论、销量、评价。\n"
          "  3. 不许用绝对化用语（最高级、「第一」、100%、国家级）。\n"
          "  4. 第 5 位（资质售后）只写**材料里真实持有**的资质；没有就写售后承诺，"
          "并在 `slot_evidence` 里注明「该位无真实资质」。\n"
          "  5. 详情页文案要按材料里的事实写，每条都要能指回材料。\n"
          "  6. **主图上不许出现任何「内部状态」的字**（真机实测踩过：模型把"
          "「无真实资质图」「缺资质图」这类内部说明写进了第 5 位文案）。"
          "第 5 位没有资质可展示时，就写售后口径（例如退换规则），"
          "**不要在主图上解释自己缺什么** —— 那是给运营看的，不是给消费者看的。\n"
        + "\n⚠️ **交之前先数字数**（真机实测踩过：第 1 位写了 17 字、上限 14 字，"
          "被本地闸门拦下，整包返工）。上面每一位的上限是**硬约束**，"
          "中文按字符算（标点也算一个）。写完每一位自己数一遍，超了就删到不超。\n"
        + "\n按要求只输出这个 JSON 对象：\n"
        + json.dumps({
            "slots": {k: "该位的文案" for k in SLOT_KEYS},
            "slot_evidence": {k: "该位文案的依据（材料里的哪个字段/哪句话）" for k in SLOT_KEYS},
            "detail": {
                "opening": "详情页开头（2~3 句）",
                "sections": [{"title": "小标题", "body": "正文（3~6 句）",
                              "quote": "材料里原样的一小段作为依据"}],
                "closing": "结尾（售后与行动指引）",
            },
            "banned_avoided": ["你主动避开的违规表述"],
        }, ensure_ascii=False, indent=1)
        + "\n补充要求：detail.sections 3~5 段。`banned_avoided` 不是免责声明，"
          "本地闸门扫的是你**实际写出来的字**，不是这份清单。\n"
        + "\n===== 商品资料原文开始 =====\n" + (mat.get("raw") or "")
        + "\n===== 商品资料原文结束 =====\n"
    )


def build_visual_prompt(mat, target_platform, copy_obj, rejects=None):
    c = copy_obj if isinstance(copy_obj, dict) else {}
    slots = c.get("slots") or {}
    slot_lines = []
    for k in SLOT_KEYS:
        txt = slots.get(k) or "（该位没有文案）"
        slot_lines.append("  · {}（{}）\n      文案：{}\n      该位要解决的事：{}".format(
            SLOT_LABEL[k], k, txt, SLOT_ASK[k]))
    reject_block = ""
    if rejects:
        reject_block = ("\n上一轮你标了「做不出来」的位（本轮要重新判：文案改了，是不是能做了；"
                        "素材没变则仍然做不出来）：\n"
                        + "\n".join("  · {}：{}".format(
                            SLOT_LABEL.get(r.get("slot"), r.get("slot")),
                            r.get("reason_code") or "-") for r in rejects) + "\n")
    assets = (mat.get("fields") or {}).get("素材") or "（材料里没有写素材清单）"
    return (
        "请以【视觉】的角色，对这五个主图位出**文本方案**（本包不出图，只出方案）。\n"
        "\n" + _product_block(mat) + "\n"
        "\n素材清单：{}\n".format(assets)
        + reject_block
        + "\n五位各自拿到的文案（**你只拿到文字，看不到文案角色的自评与依据**）：\n"
        + "\n".join(slot_lines) + "\n"
        "\n" + _ECHO_WARNING
        + "\n纪律：\n"
          "  1. 每一位都要给 `productivity`：`producible` / `producible_with_placeholder` / "
          "`not_producible`。\n"
          "  2. 素材清单里没有的东西**不许当素材用**。要做实拍、要资质、要使用场景但没有对应素材，"
          "就诚实标 `not_producible`，并给 `reason_code`。\n"
          "  3. `reason_code` 只能是这几个之一：" + "、".join(
              "{}（{}）".format(k, v) for k, v in VISUAL_REASON_CODES.items()) + "。\n"
          "  4. `not_producible` 时 `why` 要说清「缺什么、谁能补」，"
          "`ask_user` 写要用户补的具体材料（写给用户看的，不是写给文案看的）。\n"
          "  5. 文字位置要给**具体位置与字数**（主图上文字是版式的一部分）。\n"
          "  6. 画面描述里不许出现材料里没有的认证、检测、销量、评价元素。\n"
        + "\n按要求只输出这个 JSON 对象：\n"
        + json.dumps({
            "slots": [{
                "slot": "s1_benefit|s2_spec|s3_detail|s4_scene|s5_trust",
                "scene": "画面画什么（具体到构图与主体）",
                "assets": ["用到的素材，必须来自素材清单"],
                "asset_gap": "缺什么素材（没有缺口就空字符串）",
                "productivity": "producible|producible_with_placeholder|not_producible",
                "reason_code": "not_producible 时必填，取值为理由码之一；否则空字符串",
                "why": "为什么做不出来 / 为什么能做出来",
                "ask_user": "not_producible 时要用户补什么（写给用户，没有就空字符串）",
                "text": {"position": "文字压在画面哪个位置", "chars": 0,
                         "max_chars": 0, "style": "字号/颜色/描边的文字描述"},
                "layout": "版式与背景（比例、留白、主次关系）",
                "platform_note": "与目标平台主图规则的适配说明",
            } for _ in SLOT_KEYS],
            "rejected_slots": ["你标为 not_producible 的 slot 名"],
            "producible_count": 0,
            "summary": "两三句总结：这套图能不能真的做出来",
        }, ensure_ascii=False, indent=1)
        + "\n补充要求：`slots` 必须**正好五条**，slot 名用上面给的五个（缺位会被本地闸门拦下）。"
          "`chars` 填该位文案的字符数，`max_chars` 填 {0}。"
          "`rejected_slots` 与 `slots` 里标了 not_producible 的必须一致。\n".format(
              json.dumps(SLOT_MAX_CHARS, ensure_ascii=False))
        + "\n===== 商品资料原文开始 =====\n" + (mat.get("raw") or "")
        + "\n===== 商品资料原文结束 =====\n"
    )


def json_block(obj):
    """把对象渲染成提示词里用的 JSON 文本。

    空的字典会渲染成 `{ }`（而不是 `{}`）：`{}` 与**模板占位符**长得一模一样，
    留在提示词里会给占位符闸门制造假警报。同时闸门那边也收紧了 —— 只认两侧紧贴的
    `{}`，不再把空 JSON 对象当成"模板没替换干净"。
    """
    s = json.dumps(obj, ensure_ascii=False, indent=1)
    return "{ }" if s.strip() == "{}" else s


def build_compliance_prompt(mat, target_platform, bundle, ruling=None):
    b = bundle if isinstance(bundle, dict) else {}
    # 提示词里给合规看的东西，必须与 role_input 走的**同一套白名单**，
    # 否则它引的原文在本地锚不上（污染未锚定率），或者自评字段从提示词这边漏出去。
    seen_copy = slim_copy_for_review({"slots": b.get("主图五位文案"),
                                      "detail": b.get("详情页文案")})
    seen_visual = slim_visual_for_review(b.get("五位视觉方案") or {})
    prev = ""
    if ruling:
        prev = ("\n上一轮**你自己**的裁决（本轮是复裁，物料已经改过）：\n"
                "  结论：{}\n".format(ruling.get("verdict") or "-")
                + "  上次的整改要求：\n"
                + "\n".join("    · {}".format(x) for x in (ruling.get("required_fixes") or []))
                + "\n  判断规则：如果整改要求**真的做到了**，就不该继续否决；"
                  "如果没做到，继续否决并说清哪一条没做到。\n")
    material_block = (
        "\n待裁决的最终物料（**你只看产出物本身，看不到任何角色的自我评价与内部打分**）：\n"
        "① 选品卡要点：\n{}\n"
        "② 主图五位文案：\n{}\n"
        "③ 详情页文案：\n{}\n"
        "④ 五位视觉方案：\n{}\n").format(
            json_block(b.get("选品卡要点") or {}),
            json_block(seen_copy["slots"]),
            json_block(seen_copy["detail"]),
            json_block(seen_visual))
    return (
        "请以【合规】的角色，对这套上新物料做发布前裁决。\n"
        "\n" + _product_block(mat) + "\n"
        "\n目标平台：{}（{}）\n".format(PLATFORM_LABEL[target_platform], target_platform)
        + prev
        + material_block
        + "\n" + _ECHO_WARNING
        + "\n纪律（这是裁决，不是建议）：\n"
          "  1. 逐条违规项都要给 `quote`：**原样**摘录上面物料或商品资料里的"
          "**实际内容**（商品名、卖点、某一行的文案、画面描述、整改要求原文），"
          "引不出来的一律不要写。\n"
          "     ⚠️ **不许把 JSON 的字段名或结构当引文**（真机实测踩过：合规写成"
          " `\"product\": \"麦香低糖代餐奶昔 30 条装\"`，这是结构不是内容，本地锚点校验"
          "找不到它，会被判成锚点幻觉）。要引就引内容本身，例如"
          " `麦香低糖代餐奶昔 30 条装`。\n"
          "  2. 明确禁止的表述（最高级、「第一」、100%、国家级、绝对化承诺）"
          "与**伪造销量/评价/资质/检测报告**一律判高。\n"
          "  3. 结论三选一：`放行` / `打回` / `一票否决`。\n"
          "     · `打回`：物料能用，但有必改项 → `required_fixes` 要写清改哪一处、改成什么方向。\n"
          "     · `一票否决`：这套物料**不能以任何形式发布**（例如核心卖点无法举证、"
          "或无真实资质却要做资质宣称）→ 必须写 `veto_reason` 与 `required_fixes`。\n"
          "  4. **不许假装谈拢**：如果你认为有问题，就不要写「基本合规」「总体没问题」。\n"
          "     有反对意见就写进 `pending`（未解决的问题），不要抹平。\n"
          "  5. 打回或否决时，`required_fixes` 不能为空，每条要指明改哪一处、要补什么材料。\n"
        + "\n按要求只输出这个 JSON 对象：\n"
        + json.dumps({
            "verdict": "放行|打回|一票否决",
            "violations": [{
                "quote": "原样摘录的一小段",
                "rule": "违反的是哪条（广告法第几条 / 平台规则名称）",
                "level": "高|中|低",
                "what": "这一处为什么违规",
                "fix": "怎么改（给到可执行的程度）",
            }],
            "risk_claims": ["无法举证的效果或数据宣称（原样摘录）"],
            "forged_evidence": ["疑似伪造的销量/评价/资质/检测报告（原样摘录；没有就空数组）"],
            "required_fixes": ["必改项：改哪一处、改成什么方向"],
            "need_materials": ["要用户补的真实材料"],
            "veto_reason": "一票否决时必填；否则空字符串",
            "pending": ["你认为仍未解决的问题（不许抹平）"],
            "conclusion_note": "两三句结论说明",
        }, ensure_ascii=False, indent=1)
        + "\n补充要求：violations 最多 12 条，按 level 从高到低。没有违规就给空数组，"
          "但**不要**为了显得认真而编违规。\n"
        + "\n===== 商品资料原文开始 =====\n" + (mat.get("raw") or "")
        + "\n===== 商品资料原文结束 =====\n"
    )


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class CrewError(a7w.A7wError):
    """协作流程里的所有可预期失败。子类各自带退出码。"""
    exit_code = EXIT_CALL


class UsageError(CrewError):
    """参数/配置用错了（文件不存在、平台名错、给了 --budget 没给单价…）。→ 退出码 2"""
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """产出路径落在 Skill 包内（退出码 2）。"""
    exit_code = EXIT_USAGE


class GateFail(CrewError):
    """硬闸门命中（退出码 3）。"""
    exit_code = EXIT_GATE


class BudgetStop(CrewError):
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
    一次协作是四五个角色的连续调用，被一次抖动打断要重跑整轮，很亏。
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
            msg = ((err.get("error") or {}).get("message")
                   if isinstance(err.get("error"), dict) else None)
            msg = msg or err.get("msg") or text[:200]
            if exc.code == 401:
                raise CrewError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise CrewError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise CrewError("模型不存在（404）：{}  "
                                "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 {}，{}s 后重试…\n".format(
                    exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise CrewError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise CrewError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 成功响应**不带** `code` 字段；网关有时把它包一层 {"code":1,"data":{...}}，两种形态都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise CrewError("模型没返回 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    finish_reason = (choices[0] or {}).get("finish_reason")
    _LAST_FINISH["reason"] = finish_reason
    _LAST_FINISH["chars"] = len(content)
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    return content, usage


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值（`raw_decode()` 逐个 `{` / `[` 试）。

    为什么要这么写：模型经常在合法 JSON 后面多吐几个字符（```、解释、第二个对象、
    重复的 }），直接 json.loads 会炸。
    """
    if not text:
        raise CrewError("模型返回空内容")
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
    raise CrewError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


# ---------------------------------------------------------------------------
# 成本：token 标定 + 预算闸门
#
# 字符 → token 的标定比例（**是同族实测值**，不是厂商文档）：
# 输入侧沿用同族实测均值 1.612：
CHARS_PER_TOKEN_IN = 1.61
# 输出侧按「1 个原始字符 ≈ 多少 token」算，同族实测均值 1.109：
TOKENS_PER_CHAR_OUT = 1.11
# 平台口径：1 元 = 100 点。
POINTS_PER_YUAN = 100.0

# 各角色一次调用的输出 token 经验值（用于报价）。
ROLE_OUT_TOKENS = {"pick": 1100, "copy": 1500, "visual": 1800, "compliance": 1300}
ROLE_SYSTEM_TOKENS = 260        # system + 提示词骨架的固定开销（粗略）


def estimate_tokens_in(text):
    """估输入 token（用**原始字符数**，含换行——换行也要花 token）。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(mat, rounds):
    """一次协作的调用清单（用于报价，越清楚越好）。

    协作的调用构成：1 次选品 + 每轮（1 次文案 + 1 次视觉 + 1 次合规）。
    轮次是**上限**：真实跑起来可能第 1 轮就放行、也可能轮次用尽仍在否决。
    """
    src = estimate_tokens_in(mat.get("raw") or "")
    rounds = max(1, int(rounds or 1))
    calls = [{"stage": "选品（1 次）", "calls": 1,
              "tokens_in": src + ROLE_SYSTEM_TOKENS,
              "tokens_out": ROLE_OUT_TOKENS["pick"],
              "note": "出选品卡；本地毛利/资质判定线独立于它的结论"}]
    for name, note in (("copy", "写主图五位 + 详情页；被打回时按打回意见重写"),
                       ("visual", "出五位视觉方案；可能标某位做不出来"),
                       ("compliance", "裁决放行/打回/一票否决")):
        calls.append({"stage": "{}（每轮 1 次）".format(role_label(name)),
                      "calls": rounds,
                      "tokens_in": (src + ROLE_SYSTEM_TOKENS
                                    + sum(ROLE_OUT_TOKENS[k]
                                          for k in ("pick", "copy", "visual"))) * rounds,
                      "tokens_out": ROLE_OUT_TOKENS[name] * rounds,
                      "note": note})
    return calls


def compute_cost(tokens_in, tokens_out, price_in=None, price_out=None):
    """算钱。单价单位：点 / 百万 token。缺单价时诚实返回 None，**不编价**。"""
    rec = {
        "tokens_in": int(tokens_in or 0),
        "tokens_out": int(tokens_out or 0),
        "price_in": price_in, "price_out": price_out,
        "unit": "点/百万 token",
        "points": None, "yuan": None, "notes": [],
    }
    if price_in is None or price_out is None:
        rec["notes"].append(
            "没给单价，无法给出金额：文本模型网关**不公布单价**（models 列表里也没有价格字段）。"
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
        self.stages = []          # 每次调用一行：[阶段, prompt_tokens, completion_tokens]

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
        self.stages.append({"stage": label, "prompt_tokens": p, "completion_tokens": c,
                            "usage_present": bool(u)})

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

    def line(self, prefix="已用"):
        s = "{} {} 次文本调用 · token prompt={} completion={} total={}".format(
            prefix, self.calls, self.prompt_tokens, self.completion_tokens,
            self.total_tokens)
        if self.estimated_flags:
            s += "（含 {} 次没有真实 usage 的调用）".format(self.estimated_flags)
        if not self.has_price:
            s += " · 金额：网关不公布文本单价，**未折算**（要折算请传 --price-in / --price-out）"
        else:
            s += " · 估算 {:g} 点 ≈ ¥{:g}（按你填的单价）".format(
                self.points or 0, (self.points or 0) / POINTS_PER_YUAN)
        return s


def usage_dict(tracker, raw_usages=None):
    """把整轮的真实 usage 汇总成可展示的 dict（**只报 token，不编金额**）。"""
    d = {
        "calls": tracker.calls,
        "prompt_tokens": tracker.prompt_tokens,
        "completion_tokens": tracker.completion_tokens,
        "total_tokens": tracker.total_tokens,
        "estimated_flags": tracker.estimated_flags,
        "per_call": list(tracker.stages),
        "priced": tracker.has_price,
        "points": (None if tracker.points is None else round(tracker.points, 4)),
        "yuan": (None if tracker.points is None
                 else round(tracker.points / POINTS_PER_YUAN, 4)),
        "gateway_note": ("文本模型网关不公布单价，本包只报 token；"
                         "要折算金额请传 --price-in / --price-out。"),
    }
    if raw_usages:
        d["raw_usage"] = raw_usages
    return d


# ---------------------------------------------------------------------------
# 断点续跑
#
# 事故复盘（同族踩过三次，本包一次都不许再踩）：
#   · 内容截断没进 key   → 把 8000 字截成 4000 字重跑，key 没变，静默复用了旧产物
#   · 分辨率没进 key     → 换了档位重跑，命中的还是上一档的产物
#   · 死参数没进 key     → 参数调了但没生效，用户以为改过了
# 结论：**断点 key 必须含全部影响产出的维度**。
# 本包的做法更彻底：不看参数名，而是把「这一阶段的**全部输入**」序列化后取摘要 ——
# 输入变了 key 必变，不存在"忘了把某个维度写进 key"这种事。
# ---------------------------------------------------------------------------

STATE_NAME = "state.json"
STATE_VERSION = 1


def json_sha(obj):
    """任意可序列化对象的稳定摘要（sort_keys，保证与字典顺序无关）。"""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def state_key(stage, payload):
    """断点 key = 阶段名 + **该阶段全部输入的摘要**（含口径版本号）。

    payload 里必须放影响产出的每一样东西：角色、模型、温度、max_tokens、轮次、
    目标平台、各上游产物的内容摘要、口径版本。少一个就会出现"改了参数却复用旧产物"。
    """
    return "{}:{}".format(stage, json_sha(payload)[:20])


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
# 闸门：`--outdir` / `--out` 不许落在包内
#
# 为什么单独做一道闸门而不是"提示一下"：Skill 包的上传白名单只收
# `.md .py .txt .json .sh .js .yaml .yml .csv`，包内塞一张 png 会让上传直接 400。
# （`scripts/__pycache__/*.pyc` 在 CLI 的排除清单里，**不会**导致上传被拒 ——
#  所以本包只在 `sys.dont_write_bytecode` 上做干净，不拿 .pyc 当理由吓人。）
# 写文件是**写操作**，写进去之前就要拦住。退出码 2（usage）。
# ---------------------------------------------------------------------------

def pkg_dir():
    return Path(__file__).resolve().parent.parent


def ensure_outside_pkg(target, what="输出路径", example="ecom-crew-out"):
    """路径在包内 → 抛 PackagePathError（退出码 2）。"""
    root = pkg_dir()
    t = Path(target).resolve()
    try:
        t.relative_to(root)
    except ValueError:
        return
    raise PackagePathError(
        "{} {} 在 Skill 包内（{}）。包内只允许白名单文本后缀，**产出不许进包**"
        "（也不许有任何图片），请换到包外，例如 {}".format(
            what, t, root, Path(os.environ.get("TEMP") or ".") / example))


# ---------------------------------------------------------------------------
# `--budget` 的前置校验：**每个会花钱的子命令第一步都要跑**
#
# 事故复盘（同族踩过）：校验只写在 `cost` 子命令里，于是 `run --budget 0.5`
# 一路跑到报价之后才拦 —— 自测就真花了钱。
# 所以抽成 check_cost_opts()，由每个会调模型的子命令在**任何网络请求之前**调用。
# ---------------------------------------------------------------------------

def check_cost_opts(a):
    """预算参数的合法性前置校验（零成本，不联网）。"""
    budget = getattr(a, "budget", None)
    pin, pout = getattr(a, "price_in", None), getattr(a, "price_out", None)
    if budget is not None and budget <= 0:
        raise UsageError("--budget 必须大于 0（给的是 {}）".format(budget))
    if (pin is None) != (pout is None):
        raise UsageError("--price-in 与 --price-out 要么都给、要么都不给：只给一个算不出金额。")
    if budget is not None and pin is None:
        # 没单价就没有"点数"，预算无法核验 → 报出来，但不拦（金额本来就不可知）
        sys.stderr.write(
            "提示：你给了 --budget {}（点）但没给单价。文本模型网关**不公布单价**，"
            "因此这次协作的金额无法折算、预算也无法核验；本包只报真实 token，"
            "不会编一个金额出来。要真正核预算请同时给 --price-in / --price-out。\n".format(budget))


def read_text(path, what="文件"):
    p = Path(path)
    if not p.is_file():
        raise UsageError("{}不存在：{}".format(what, path))
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise UsageError("{}不是 UTF-8 文本（{}）。请另存为 UTF-8。".format(what, exc))


def read_json(path, what="文件"):
    p = Path(path)
    if not p.is_file():
        raise UsageError("{}不存在：{}".format(what, path))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("{}不是合法 JSON（{}）：{}".format(what, exc, path))


def load_artifact(path, key, what="产物"):
    """读一份别的子命令落下的 JSON 产物，并把信封脱掉。

    `--json` 的输出外面包了 `{"ok": true, ...}`；顶层是数组时包成
    `{"ok": true, "data": [...]}`。下游子命令要的是**里面的那份产物**，
    所以这里统一拆信封：有 `key` 就取 `key`，否则若是纯信封且带 `data` 就取 `data`。
    """
    if not path:
        return None
    obj = read_json(path, what)
    if isinstance(obj, dict) and key in obj and isinstance(obj.get(key), (dict, list)):
        return obj[key]
    if isinstance(obj, dict) and set(obj.keys()) <= {"ok", "data"} and "data" in obj:
        return obj["data"]
    return obj


def write_text(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def write_json(path, obj):
    """JSON 产物一律不写 `ensure_ascii`（中文要能直接读），缩进 1。"""
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


# ---------------------------------------------------------------------------
# 六道硬闸门的清单（给文档、给人读、也给 `--json` 的 gates 段用同一份口径）
#
# 与同族一致：命中一律 **压分/拦截 + 标红 + stderr 汇总 + 非 0 退出码**。
# ---------------------------------------------------------------------------

GATE_CATALOG = [
    ("compliance", "电商合规", "广告法违禁词（最/第一/国家级/100%/保过…）；"
                               "不伪造销量/评价/资质/检测报告。材料侧与产出侧同口径（全档全查，"
                               "产出侧零豁免）；**评审文书侧**另开引用/提到排除，被排除的留下原因"),
    ("placeholder", "占位符残留", "`{}` / `[待填]` / `XXX` / `（此处省略）` / `TODO`"),
    ("prompt_echo", "照抄提示词示例", "去标点相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60（含适用窗口）"),
    ("anchor", "锚点到句子", "每条意见必须引用真实原文；未锚定率 > 0.40 判定位失败，"
                             "编造引文剔出"),
    ("slot_complete", "主图位完整性", "五个主图位缺位即标红（视觉方案必须正好五位）"),
    ("ruling", "裁决完整性", "打回/否决必须留理由与整改项；有反对却判放行 = 假装谈拢"),
]

GATE_KEYS = tuple(g[0] for g in GATE_CATALOG)


# ---------------------------------------------------------------------------
# 闸门五：主图位完整性（本包特有）
# ---------------------------------------------------------------------------

def check_slots(copy_obj, visual_obj):
    """检查五个主图位是否齐、视觉方案是否正好五位。返回 (ok, issues, detail)。"""
    issues, detail = [], {}
    c = copy_obj if isinstance(copy_obj, dict) else None
    v = visual_obj if isinstance(visual_obj, dict) else None
    c_slots = (c or {}).get("slots") if isinstance((c or {}).get("slots"), dict) else {}
    missing_copy = [k for k in SLOT_KEYS if not str(c_slots.get(k) or "").strip()]
    detail["copy_slots"] = len([k for k in SLOT_KEYS if str(c_slots.get(k) or "").strip()])
    if c is not None and missing_copy:
        issues.append({
            "kind": "copy_missing_slots",
            "slots": missing_copy,
            "why": "主图文案缺位：" + "、".join(SLOT_LABEL[k] for k in missing_copy),
        })
    over = []
    for k in SLOT_KEYS:
        txt = str(c_slots.get(k) or "")
        n = len(re.sub(r"\s+", "", txt))
        if n > SLOT_MAX_CHARS[k]:
            over.append({"slot": k, "chars": n, "max": SLOT_MAX_CHARS[k],
                         "text": txt[:40]})
    detail["copy_over_limit"] = over
    if over:
        issues.append({
            "kind": "copy_over_limit",
            "items": over,
            "why": "主图文案超字数上限：" + "、".join(
                "{} {} 字 > {}".format(SLOT_LABEL[o["slot"]], o["chars"], o["max"])
                for o in over),
        })
    if v is not None:
        vs = v.get("slots") if isinstance(v.get("slots"), list) else []
        named = [str((s or {}).get("slot") or "").strip() for s in vs if isinstance(s, dict)]
        detail["visual_slots"] = named
        miss_v = [k for k in SLOT_KEYS if k not in named]
        dup = sorted({x for x in named if named.count(x) > 1 and x})
        extra = [x for x in named if x and x not in SLOT_KEYS]
        if miss_v or dup or extra or len(vs) != len(SLOT_KEYS):
            issues.append({
                "kind": "visual_slots",
                "missing": miss_v, "duplicated": dup, "unknown": extra,
                "count": len(vs),
                "why": "视觉方案的五位不齐（收到 {} 条；缺 {}；重复 {}；不认识的位 {})".format(
                    len(vs), "、".join(miss_v) or "无", "、".join(dup) or "无",
                    "、".join(extra) or "无"),
            })
    ok = not issues
    return ok, issues, detail


# ---------------------------------------------------------------------------
# 闸门六：裁决完整性（**不许假装谈拢**）
#
# 一道"看起来通过了"的裁决，比一道明确的否决危险得多。所以本地不采信结论，
# 而是检查结论与事实是否自洽：
#   · 打回/否决却没有整改要求（required_fixes 空）→ 拦
#   · 一票否决却没有否决理由 → 拦
#   · 有高等级违规（violations 有 level=高 / forged_evidence 非空 / risk_claims 非空）
#     却判「放行」→ 拦，这就是假装谈拢
#   · pending 非空却判「放行」→ 拦（自己都写了还有未解决问题）
#   · 违规项没有引文 → 拦（说不清是哪里）
# ---------------------------------------------------------------------------

def check_ruling(ruling, bundle_text=""):
    """裁决完整性校验。返回 (ok, issues, detail)。"""
    r = ruling if isinstance(ruling, dict) else {}
    issues = []
    verdict = str(r.get("verdict") or "").strip()
    if verdict not in VERDICT_CHOICES:
        issues.append({"kind": "bad_verdict",
                       "why": "裁决结论不是 放行/打回/一票否决 之一：{}".format(verdict or "（空）")})
    viol = [v for v in (r.get("violations") or []) if isinstance(v, dict)]
    risks = [x for x in (r.get("risk_claims") or []) if str(x or "").strip()]
    forged = [x for x in (r.get("forged_evidence") or []) if str(x or "").strip()]
    fixes = [x for x in (r.get("required_fixes") or []) if str(x or "").strip()]
    pending = [x for x in (r.get("pending") or []) if str(x or "").strip()]
    hi = [v for v in viol if str(v.get("level") or "").strip() == "高"]
    detail = {"verdict": verdict, "violations": len(viol), "high": len(hi),
              "risk_claims": len(risks), "forged_evidence": len(forged),
              "required_fixes": len(fixes), "pending": len(pending)}
    if verdict in ("打回", "一票否决") and not fixes:
        issues.append({"kind": "no_fixes",
                       "why": "结论是「{}」却没有任何整改要求（required_fixes 为空）——"
                              "打回/否决必须说清改什么".format(verdict)})
    if verdict == "一票否决" and not str(r.get("veto_reason") or "").strip():
        issues.append({"kind": "no_veto_reason",
                       "why": "结论是「一票否决」却没有 veto_reason —— 否决必须留可读理由"})
    hard = bool(hi) or bool(forged) or bool(risks)
    if verdict == "放行" and hard:
        issues.append({"kind": "fake_pass",
                       "why": "判「放行」但裁决里存在高等级违规 {} 条 / 无法举证宣称 {} 条 / "
                              "疑似伪造证据 {} 条 —— 这就是**假装谈拢**".format(
                                  len(hi), len(risks), len(forged))})
    if verdict == "放行" and pending:
        issues.append({"kind": "fake_pass",
                       "why": "判「放行」但 pending 里还列着 {} 条未解决问题 —— 不许假装谈拢"
                              .format(len(pending))})
    for v in viol:
        if not str(v.get("quote") or "").strip():
            issues.append({"kind": "no_quote",
                           "why": "有一条违规项没有引文（quote 为空），说不清是物料里的哪一处"})
            break
    return (not issues), issues, detail


def check_visual_feasibility(visual_obj):
    """视觉可产性校验。

    这一条不是"闸门"而是**协作回授信号的来源**：视觉说某位做不出来，
    就把该位送回文案重写。但要检查它说得清不清楚：
      · `productivity` 必须是三个取值之一
      · `not_producible` 必须有 `reason_code`（枚举内）与 `why`
      · `reason_code=missing_asset` 时 `asset_gap` 不能为空
    """
    v = visual_obj if isinstance(visual_obj, dict) else {}
    issues, rejects = [], []
    for s in (v.get("slots") or []):
        if not isinstance(s, dict):
            continue
        slot = str(s.get("slot") or "").strip()
        prod = str(s.get("productivity") or "").strip()
        if prod not in PRODUCTIVITY_CHOICES:
            issues.append({"kind": "bad_productivity", "slot": slot,
                           "why": "{} 的可产性取值不合法：{}（只能是 {}）".format(
                               slot or "（无名位）", prod or "（空）",
                               " / ".join(PRODUCTIVITY_CHOICES))})
            continue
        if prod != "not_producible":
            continue
        rc = str(s.get("reason_code") or "").strip()
        why = str(s.get("why") or "").strip()
        if rc not in REASON_CHOICES:
            issues.append({"kind": "bad_reason_code", "slot": slot,
                           "why": "{} 标了做不出来，但理由码不在枚举内：{}".format(
                               SLOT_LABEL.get(slot, slot), rc or "（空）")})
        if not why:
            issues.append({"kind": "no_why", "slot": slot,
                           "why": "{} 标了做不出来，但没写 why".format(SLOT_LABEL.get(slot, slot))})
        if rc == "missing_asset" and not str(s.get("asset_gap") or "").strip():
            issues.append({"kind": "no_asset_gap", "slot": slot,
                           "why": "{} 的理由码是 missing_asset，但 asset_gap 是空的 —— "
                                  "说不清缺什么素材".format(SLOT_LABEL.get(slot, slot))})
        rejects.append({"slot": slot, "reason_code": rc, "why": why,
                        "asset_gap": s.get("asset_gap") or "",
                        "ask_user": s.get("ask_user") or "",
                        "text": (s.get("text") or {}).get("chars")
                        if isinstance(s.get("text"), dict) else None})
    declared = [x for x in (v.get("rejected_slots") or []) if str(x or "").strip()]
    from_slots = [r["slot"] for r in rejects if r["slot"]]
    detail = {"rejects": rejects, "declared": declared, "from_slots": from_slots}
    if sorted(set(declared)) != sorted(set(from_slots)):
        issues.append({"kind": "reject_mismatch",
                       "why": "rejected_slots（{}）与各 slot 的 not_producible（{}）对不上".format(
                           "、".join(declared) or "空", "、".join(from_slots) or "空")})
    return (not issues), issues, detail


# ---------------------------------------------------------------------------
# 选品角色的本地判定线（**不因模型措辞而改变**）
#
# 为什么必须有：本包第一个角色就能否掉这个品，而"能不能卖"最容易被模型说得乐观。
# 所以本地拿**自己算出来的账**再判一次，模型写「可主推」也拦得住。
# 这一条同时也是 L3 里"角色有独立目标函数 + 有人能否决"的最硬证据：
# 选品的否决权不取决于它乐不乐意说，而取决于账。
# ---------------------------------------------------------------------------

def check_pick(pick_card, mat):
    """选品卡的本地校验。返回 (ok, issues, detail)。

    `ok=False` 有两种含义，用 detail["veto"] 区分：
      · 本地判定线与模型结论冲突 / 账算不过来 → veto=True，整条流水线停
      · 卡面不完整（引文编的、缺项）→ veto=False，重开该角色
    """
    pc = pick_card if isinstance(pick_card, dict) else {}
    issues = []
    mg = margin_calc(mat)
    sellpoints = [s for s in (pc.get("sellpoints") or []) if isinstance(s, dict)]
    risks = [r for r in (pc.get("risks") or []) if isinstance(r, dict)]
    conclusion = str(pc.get("conclusion") or "").strip()
    veto_by_model = bool(pc.get("venv_veto"))
    local_veto, local_why = False, []

    if conclusion not in PICK_VERDICT_CHOICES and not veto_by_model:
        issues.append({"kind": "bad_conclusion",
                       "why": "结论不是 可主推/可测试/放弃 之一：{}".format(conclusion or "（空）")})
    if not sellpoints:
        issues.append({"kind": "no_sellpoints",
                       "why": "选品卡没有一条卖点（sellpoints 为空）——下游角色没有可用的输入"})
    # 本地判定线一：毛利
    if mg.get("ok"):
        rate = mg.get("margin_rate_on_price") or 0.0
        ret = (mg.get("inputs") or {}).get("return_rate")
        if rate < PICK_MARGIN_FLOOR:
            local_veto = True
            local_why.append("退货后毛利占售价 {:.1%} < {:.0%}（本地线）".format(
                rate, PICK_MARGIN_FLOOR))
        if ret is not None and ret > PICK_RETURN_RATE_CEIL:
            local_veto = True
            local_why.append("退货率 {:.0%} > {:.0%}（本地线）".format(ret, PICK_RETURN_RATE_CEIL))
    else:
        # 账算不出来：不拦（缺材料本来就是要求用户补），但要如实记
        local_why.append("本地算不出账（{}）→ 未做本地线判定".format(
            mg.get("why") or "缺参数"))
    # 本地判定线二：模型说放弃/否决，但账目字段是空话
    if veto_by_model and not str(pc.get("veto_reason") or "").strip():
        issues.append({"kind": "no_veto_reason",
                       "why": "选品卡设了 venv_veto=true 但没写 veto_reason —— 否决必须留理由"})
    # 方向冲突：模型说可主推，本地线判放弃
    if local_veto and conclusion == "可主推" and not veto_by_model:
        issues.append({"kind": "local_conflict",
                       "why": "模型结论是「可主推」，但本地判定线判「放弃」：{}".format(
                           "；".join(local_why))})
    detail = {
        "conclusion": conclusion,
        "model_veto": veto_by_model,
        "veto": bool(veto_by_model or (local_veto and conclusion != "可测试")),
        "local_veto": local_veto,
        "local_why": local_why,
        "margin": mg,
        "sellpoints": len(sellpoints),
        "risks": len(risks),
    }
    if detail["veto"] and not detail["model_veto"]:
        detail["veto_reason"] = "本地判定线否决：{}".format("；".join(local_why))
    else:
        detail["veto_reason"] = str(pc.get("veto_reason") or "").strip()
    return (not issues), issues, detail


# ---------------------------------------------------------------------------
# 产出的可扫描文本：把每个角色的产出拆成"要扫的字段"
# ---------------------------------------------------------------------------

def _pick_texts(pc):
    pc = pc if isinstance(pc, dict) else {}
    out = []
    for i, s in enumerate(pc.get("sellpoints") or [], 1):
        if isinstance(s, dict):
            out.append(("选品卡·卖点{}".format(i), str(s.get("point") or "")))
    for i, r in enumerate(pc.get("risks") or [], 1):
        if isinstance(r, dict):
            out.append(("选品卡·风险{}".format(i),
                        "{} {}".format(r.get("risk") or "", r.get("why") or "")))
    out.append(("选品卡·结论", str(pc.get("conclusion") or "")))
    if pc.get("veto_reason"):
        out.append(("选品卡·否决理由", str(pc["veto_reason"])))
    for i, x in enumerate(pc.get("need_materials") or [], 1):
        out.append(("选品卡·待补材料{}".format(i), str(x or "")))
    return [(k, v) for k, v in out if v.strip()]


def _copy_texts(cp):
    cp = cp if isinstance(cp, dict) else {}
    out = []
    slots = cp.get("slots") if isinstance(cp.get("slots"), dict) else {}
    for k in SLOT_KEYS:
        if str(slots.get(k) or "").strip():
            out.append(("主图文案·{}".format(SLOT_LABEL[k]), str(slots[k])))
    d = cp.get("detail") if isinstance(cp.get("detail"), dict) else {}
    if str(d.get("opening") or "").strip():
        out.append(("详情页·开头", str(d["opening"])))
    for i, s in enumerate(d.get("sections") or [], 1):
        if isinstance(s, dict):
            out.append(("详情页·第{}段标题".format(i), str(s.get("title") or "")))
            out.append(("详情页·第{}段正文".format(i), str(s.get("body") or "")))
            out.append(("详情页·第{}段依据".format(i), str(s.get("quote") or "")))
    if str(d.get("closing") or "").strip():
        out.append(("详情页·结尾", str(d["closing"])))
    return out


def _visual_texts(v):
    """视觉方案的字段**分成两类**（真机实测踩过：内部的版式说明被当成面客文案）。

    · 「画面」与「文字说明」是**要落到图上的东西** → 面客口径，零豁免
    · 「版式说明 / 可产性说明 / 平台适配」是内部工作说明，**不会出现在图上**
      → 审类口径（「主标题第一眼」这种主次描述不该被当成最高级宣称）
    """
    v = v if isinstance(v, dict) else {}
    out = []
    for s in (v.get("slots") or []):
        if not isinstance(s, dict):
            continue
        label = SLOT_LABEL.get(str(s.get("slot") or "").strip(), str(s.get("slot") or "?"))
        t = s.get("text") if isinstance(s.get("text"), dict) else {}
        out.append(("视觉方案·{}·画面".format(label),
                    "{} {}".format(s.get("scene") or "", t.get("style") or "")))
        out.append(("视觉方案·{}·版式说明".format(label),
                    "{} {} {}".format(s.get("layout") or "", s.get("why") or "",
                                      s.get("platform_note") or "")))
    if str(v.get("summary") or "").strip():
        out.append(("视觉方案·总结", str(v["summary"])))
    return [(k, x) for k, x in out if x.strip()]


def bundle_text_for_ruling(mat, pick_card=None, copy_obj=None, visual_obj=None):
    """把「合规角色审的那份物料」拼成一段纯文本，用于锚点与引用排除。

    必须和提示词里给它看的东西一致 —— 否则它引的原文在本地找不到，会污染未锚定率。
    """
    parts = [mat.get("raw") or ""]
    if isinstance(pick_card, dict):
        for s in (pick_card.get("sellpoints") or []):
            if isinstance(s, dict):
                parts.append(str(s.get("point") or ""))
        for r in (pick_card.get("risks") or []):
            if isinstance(r, dict):
                parts.append("{} {}".format(r.get("risk") or "", r.get("why") or ""))
    if isinstance(copy_obj, dict):
        slots = copy_obj.get("slots") if isinstance(copy_obj.get("slots"), dict) else {}
        for k in SLOT_KEYS:
            parts.append(str(slots.get(k) or ""))
        d = copy_obj.get("detail") if isinstance(copy_obj.get("detail"), dict) else {}
        parts.append(str(d.get("opening") or ""))
        for s in (d.get("sections") or []):
            if isinstance(s, dict):
                parts.append("{} {}".format(s.get("title") or "", s.get("body") or ""))
        parts.append(str(d.get("closing") or ""))
    if isinstance(visual_obj, dict):
        for s in (visual_obj.get("slots") or []):
            if isinstance(s, dict):
                parts.append("{} {}".format(s.get("scene") or "", s.get("why") or ""))
    return "\n".join(x for x in parts if str(x).strip())


# ---------------------------------------------------------------------------
# 六道闸门的统一评估（本地、确定性）
# ---------------------------------------------------------------------------

def _compliance_gate(specs, material_text):
    """`specs` = [(side, label, text)]；side 取 material / creator / review。

    · **material**（用户给的原始资料）：全档全查；命中**只报不拦**（见下）。
    · **creator**（我们产出的物料）：面客字段零豁免、审类字段开引用/提到排除。
    · **review**（合规裁决文书）：高风险 + 引用/提到排除。

    【材料侧为什么不拦】（真机实测定的口径，不是想当然）：材料是**用户给的商品事实**
    （常常是把违规卖点原样贴进来的草稿）。如果我们产出的主图文案一个字没错、
    只因为用户材料里那句"100% 有效"就整包判死，那这道闸门就永远过不去，
    用户只会把它关掉。所以：
      · 材料侧命中 → 进 `material_hits`，**标红提示、写进报告，但不改退出码**
      · 真正的拦截对象是**我们产出的字**（creator / review 两侧）
    这也是本包与 ecom-image 的一处差别：那边材料就是出图提示词的来源，必须一起拦；
    这边材料只是事实来源，面客文案是独立产出物，拦错了地方就等于没拦。
    """
    fresh, quoted, mentioned, soft, exempted = [], [], [], [], []
    material_hits = []
    for side, label, text in specs:
        if not str(text or "").strip():
            continue
        if side == "material":
            r = compliance_scan_material(text)
            material_hits.extend([dict(h, side="material", in_field=label)
                                  for h in r["hits"]])
            exempted.extend(r["exempted"])
        elif side == "review":
            f, q, m, s, ex = _scan_prose_with_context(text, material_text, label)
            for h in f:
                h["field_kind"] = "裁决文书（已开引用/提到排除后仍然命中）"
            fresh.extend(f)
            quoted.extend(q)
            mentioned.extend(m)
            soft.extend(s)
            exempted.extend(ex)
        else:
            f, q, m, ex = scan_creator_field(label, text, material_text)
            fresh.extend(f)
            quoted.extend(q)
            mentioned.extend(m)
            exempted.extend(ex)
    out = {
        "ok": not fresh,
        "hits": fresh,
        "material_hits": material_hits,
        "material_note": ("材料侧命中 {} 处：**只报不拦**（材料是用户给的事实来源，"
                          "不是我们要发布的字）；要发布的是产出物，拦的是产出物。"
                          .format(len(material_hits)) if material_hits else ""),
        "quoted_from_material": quoted,
        "mentioned_as_warning": mentioned,
        "contextual_only": soft,
        "exempted": exempted,
        "why": ("产出侧命中 {} 处违禁/高风险表述".format(len(fresh)) if fresh else ""),
    }
    return out


def evaluate_gates(*, material_text, pick_card=None, copy_obj=None, visual_obj=None,
                   ruling=None, rulings=None, pick=None, slots_ok=None,
                   slot_issues=None, slot_detail=None, anchors=None):
    """跑全部**本地**闸门，返回结构化 gates dict。

    每一项的形态都是 `{"ok": bool, ...}`，与同族一致；除此之外还带
    `excluded_kept`（被语境排除但留在案上的条目）与 `skipped_windows`
    （contain 判据被适用窗口跳过的记录）—— **被排除的不静默丢弃**。
    """
    specs = [("material", "商品资料", material_text)]
    for label, text in _pick_texts(pick_card):
        specs.append(("creator", label, text))
    for label, text in _copy_texts(copy_obj):
        specs.append(("creator", label, text))
    for label, text in _visual_texts(visual_obj):
        specs.append(("creator", label, text))
    rl = ruling if isinstance(ruling, dict) else {}
    review_texts = [("合规裁决·结论", str(rl.get("conclusion_note") or "")),
                    ("合规裁决·否决理由", str(rl.get("veto_reason") or ""))]
    for i, v in enumerate(rl.get("violations") or [], 1):
        if isinstance(v, dict):
            review_texts.append(("合规裁决·违规{}".format(i),
                                 "{} {}".format(v.get("what") or "", v.get("fix") or "")))
    for i, x in enumerate(rl.get("required_fixes") or [], 1):
        review_texts.append(("合规裁决·整改{}".format(i), str(x or "")))
    for x in (rl.get("risk_claims") or []):
        review_texts.append(("合规裁决·风险宣称", str(x or "")))
    for x in (rl.get("forged_evidence") or []):
        review_texts.append(("合规裁决·疑似伪造", str(x or "")))
    for x in (rl.get("pending") or []):
        review_texts.append(("合规裁决·未解决", str(x or "")))
    for label, text in review_texts:
        specs.append(("review", label, text))

    g = {}
    g["compliance"] = _compliance_gate(specs, material_text)

    # 占位符：扫**全部产出**（材料侧也扫：模板没填干净的材料会一路污染到成品）
    ph = []
    for side, label, text in specs:
        for h in placeholder_hits(text):
            ph.append(dict(h, in_=label, side=side))
    for h in ph:
        h.pop("in_", None)
        h.setdefault("in", "")
    g["placeholder"] = {"ok": not ph, "hits": ph,
                        "why": ("残留 {} 处占位符".format(len(ph)) if ph else "")}

    # 照抄示例：只扫**产出**（材料是用户给的，不是模型产出）
    echo, skips = [], []
    for side, label, text in specs:
        if side == "material":
            continue
        hits, sk = prompt_echo_scan(text, label=label)
        skips.extend(sk)
        echo.extend(hits)
    g["prompt_echo"] = {"ok": not echo, "hits": echo, "samples": list(PROMPT_SAMPLES),
                        "contain_window": {"max_ratio": ECHO_CONTAIN_MAX_RATIO,
                                           "min_sample_chars": ECHO_CONTAIN_MIN_SAMPLE},
                        "skipped_windows": _dedupe_skips(skips),
                        "why": ("命中 {} 处照抄提示词示例".format(len(echo)) if echo else "")}

    if anchors is not None:
        g["anchor"] = anchors
    if slots_ok is not None:
        g["slot_complete"] = {"ok": bool(slots_ok), "issues": slot_issues or [],
                              "detail": slot_detail or {},
                              "why": ("；".join(i.get("why") or "" for i in (slot_issues or []))
                                      if slot_issues else "")}
    if ruling is not None:
        ok, issues, detail = check_ruling(ruling, bundle_text_for_ruling(
            {"raw": material_text}, pick_card, copy_obj, visual_obj))
        g["ruling"] = {"ok": ok, "issues": issues, "detail": detail,
                       "why": "；".join(i.get("why") or "" for i in issues)}
    if pick is not None:
        g["pick"] = pick
    return g


def gate_hits(gates):
    """列出没过的闸门（按 GATE_KEYS 的顺序），返回 [(key, obj)]。"""
    out = []
    for k in GATE_KEYS:
        v = gates.get(k)
        if v and not v.get("ok", True):
            out.append((k, v))
    return out


def gate_failed(gates):
    return bool(gate_hits(gates))


def apply_local_caps(dims, gates):
    """本地确定性压分：违禁词压合规分、缺位压交付分、裁决不完整压裁决分。

    **关键**：峰值由本地定，模型给多高都压下来（"模型瞎给高分骗不过本地闸门"）。
    """
    dims = dict(dims)
    ded = []
    c = gates.get("compliance") or {}
    if not c.get("ok"):
        hi = [h for h in c["hits"] if h.get("level") == "高"]
        cap = 1 if hi else 4
        if dims.get("compliance", 10) > cap:
            ded.append({"kind": "compliance", "dim": "compliance",
                        "from": dims.get("compliance"), "to": cap,
                        "why": "命中违禁表述「{}」→ 合规分封顶 {}".format(
                            (c["hits"][0] if c.get("hits") else {}).get("word", "?"), cap)})
            dims["compliance"] = cap
    s = gates.get("slot_complete") or {}
    if s and not s.get("ok", True):
        if dims.get("deliverable", 10) > 4:
            ded.append({"kind": "slot_complete", "dim": "deliverable",
                        "from": dims.get("deliverable"), "to": 4,
                        "why": "主图位不齐 / 文案超限 → 交付分封顶 4"})
            dims["deliverable"] = 4
    r = gates.get("ruling") or {}
    if r and not r.get("ok", True):
        if dims.get("ruling", 10) > 3:
            ded.append({"kind": "ruling", "dim": "ruling",
                        "from": dims.get("ruling"), "to": 3,
                        "why": "裁决不自洽（{}）→ 裁决分封顶 3".format(
                            (r.get("issues") or [{}])[0].get("why", ""))})
            dims["ruling"] = 3
    a = gates.get("anchor") or {}
    if a and not a.get("ok", True):
        if dims.get("evidence", 10) > 4:
            ded.append({"kind": "anchor", "dim": "evidence",
                        "from": dims.get("evidence"), "to": 4,
                        "why": "未锚定率 {:.0%} > {:.0%} → 依据分封顶 4".format(
                            a.get("miss_rate", 0), ANCHOR_MAX_MISS)})
            dims["evidence"] = 4
    return dims, ded


# ---------------------------------------------------------------------------
# 人读渲染（Markdown）
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """标红：终端里加 ANSI，重定向到文件时不加（免得文件里全是转义符）。"""
    if force_plain or not sys.stderr.isatty():
        return s
    return "\033[31m{}\033[0m".format(s)


def render_roles_md():
    lines = ["# 三剪客 · 电商上新小组：四个角色", "",
             "L3 多智能体协作型：**四个角色各有目标函数、各有产出物、互相能否掉对方的东西**。",
             "", "| 角色 | 目标函数 | 产出物 | 否决权 |", "|---|---|---|---|"]
    for r in ROLE_INFO:
        lines.append("| **{}** | {} | {} | {} |".format(
            r["name"], r["objective"], r["deliverable"], r["veto"]))
    lines += ["", "## 信息隔离（本地强制，不是提示词礼貌请求）", "",
              "| 角色 | 看得到 | 看不到 |", "|---|---|---|"]
    for r in ROLE_INFO:
        lines.append("| {} | {} | {} |".format(r["name"], r["sees"], r["cannot_see"]))
    lines += ["", "## 五个主图位（闸门五的口径）", ""]
    for k in SLOT_KEYS:
        lines.append("- **{}**（`{}`）：{}；文案上限 {} 字".format(
            SLOT_LABEL[k], k, SLOT_ASK[k], SLOT_MAX_CHARS[k]))
    lines += ["", "## 视觉的「做不出来」理由码（枚举，不允许自由发挥）", ""]
    for k, v in VISUAL_REASON_CODES.items():
        lines.append("- `{}`：{}".format(k, v))
    lines += ["", "## 六道硬闸门", "", "| 闸门 | 判据 |", "|---|---|"]
    for key, name, why in GATE_CATALOG:
        lines.append("| **{}**（`{}`） | {} |".format(name, key, why))
    lines += ["", "> 本包**不出图**。视觉角色只出**文本方案**，真出图交给已有的电商主图包。",
              "> 包内不允许出现任何图片文件。", ""]
    return "\n".join(lines)


def render_pick_md(pc, chk, mat, model=None, usage_note=""):
    pc = pc if isinstance(pc, dict) else {}
    mg = chk.get("margin") or {}
    lines = ["# 选品卡 · {}".format(pc.get("product") or (mat.get("fields") or {}).get("商品名") or "-"),
             ""]
    if chk.get("veto"):
        lines += ["> **本角色已否决这个品**：{}".format(chk.get("veto_reason") or "-"),
                  "> 整条流水线停在这里，不会进入文案与视觉。", ""]
    lines += ["- 类目：{}".format(pc.get("category") or "-"),
              "- 目标平台：{}".format(pc.get("target_platform") or "-"),
              "- 结论：**{}**".format(chk.get("conclusion") or "-"),
              "- 是否否决：{}".format("是" if chk.get("veto") else "否"),
              ""]
    lines += ["## 账（本地算的，可复核）", ""]
    if mg.get("ok"):
        inp = mg.get("inputs") or {}
        lines += ["| 项 | 值 |", "|---|---|",
                  "| 售价 | {} |".format(inp.get("price")),
                  "| 成本 | {} |".format(inp.get("cost")),
                  "| 物流 / 包材 | {} / {} |".format(inp.get("shipping"), inp.get("packing")),
                  "| 佣金率 / 退货率 | {} / {} |".format(
                      inp.get("commission_rate"), inp.get("return_rate")),
                  "| 单件毛利 | {} |".format(mg.get("gross")),
                  "| 佣金后毛利 | {} |".format(mg.get("after_commission")),
                  "| **退货后毛利** | **{}** |".format(mg.get("after_return")),
                  "| 退货后毛利 / 售价 | {:.1%} |".format(mg.get("margin_rate_on_price") or 0),
                  "| 保本 CPA | {} |".format(mg.get("breakeven_cpa")),
                  "| 建议 CPA 上限 | {} |".format(mg.get("suggested_cpa_cap")), ""]
        lines += ["公式：`{}`".format(mg.get("formula")), ""]
    else:
        lines += ["- {}（缺：{}）".format(mg.get("why") or "算不出账",
                                        "、".join(mg.get("missing") or [])), ""]
    if chk.get("local_why"):
        lines += ["本地判定线备注：", ""] + ["- {}".format(x) for x in chk["local_why"]] + [""]
    lines += ["## 卖点与依据", ""]
    sp = [s for s in (pc.get("sellpoints") or []) if isinstance(s, dict)]
    if sp:
        lines += ["| # | 卖点 | 依据 | 原文 |", "|---|---|---|---|"]
        for i, s in enumerate(sp, 1):
            lines.append("| {} | {} | {} | {} |".format(
                i, s.get("point") or "-", s.get("evidence") or "-",
                (s.get("sentence") or s.get("quote") or "-")[:40]))
    else:
        lines.append("- （没有卖点）")
    lines += ["", "## 资质", ""]
    certs = pc.get("certs") if isinstance(pc.get("certs"), dict) else {}
    lines += ["- 已持有：{}".format("、".join(certs.get("held") or []) or "（材料里没写）"),
              "- 类目按常规需要：{}".format(
                  "、".join(certs.get("required_for_category") or []) or "-"),
              "- **缺口**：{}".format("、".join(certs.get("missing") or []) or "无")]
    lines += ["", "## 风险清单", ""]
    risks = [r for r in (pc.get("risks") or []) if isinstance(r, dict)]
    if risks:
        lines += ["| 等级 | 风险 | 原文 | 谁能解决 |", "|---|---|---|---|"]
        for r in risks:
            lines.append("| {} | {} | {} | {} |".format(
                r.get("level") or "-", r.get("risk") or "-",
                (r.get("sentence") or r.get("quote") or "-")[:36], r.get("who_can_fix") or "-"))
    else:
        lines.append("- （没有列风险）")
    need = [x for x in (pc.get("need_materials") or []) if str(x or "").strip()]
    if need:
        lines += ["", "## 要用户补的真实材料", ""] + ["- {}".format(x) for x in need]
    if usage_note:
        lines += ["", "---", "", usage_note]
    return "\n".join(lines) + "\n"


def render_copy_md(cp, model=None, usage_note=""):
    cp = cp if isinstance(cp, dict) else {}
    slots = cp.get("slots") if isinstance(cp.get("slots"), dict) else {}
    ev = cp.get("slot_evidence") if isinstance(cp.get("slot_evidence"), dict) else {}
    lines = ["# 主图文案 · 五个位", "",
             "| 位 | 文案 | 字数 / 上限 | 依据 |", "|---|---|---|---|"]
    for k in SLOT_KEYS:
        txt = str(slots.get(k) or "**（缺位）**")
        n = len(re.sub(r"\s+", "", str(slots.get(k) or "")))
        flag = " ⚠️" if n > SLOT_MAX_CHARS[k] else ""
        lines.append("| {} | {} | {} / {}{} | {} |".format(
            SLOT_LABEL[k], txt, n, SLOT_MAX_CHARS[k], flag, (ev.get(k) or "-")[:40]))
    lines += ["", "## 详情页文案", ""]
    d = cp.get("detail") if isinstance(cp.get("detail"), dict) else {}
    if d.get("opening"):
        lines += ["**开头**", "", str(d["opening"]), ""]
    for i, s in enumerate(d.get("sections") or [], 1):
        if isinstance(s, dict):
            lines += ["**{}**".format(s.get("title") or "第 {} 段".format(i)), "",
                      str(s.get("body") or ""), ""]
            if s.get("sentence") or s.get("quote"):
                lines += ["> 依据：{}".format((s.get("sentence") or s.get("quote"))[:60]), ""]
    if d.get("closing"):
        lines += ["**结尾**", "", str(d["closing"]), ""]
    av = [x for x in (cp.get("banned_avoided") or []) if str(x or "").strip()]
    if av:
        lines += ["## 文案自称避开的表述", ""] + ["- {}".format(x) for x in av] + [
            "", "> 注意：本地闸门扫的是**你实际写出来的字**，不是这份清单。", ""]
    if usage_note:
        lines += ["---", "", usage_note]
    return "\n".join(lines) + "\n"


def render_visual_md(v, chk, model=None, usage_note=""):
    v = v if isinstance(v, dict) else {}
    rejects = {r["slot"]: r for r in (chk.get("rejects") or [])}
    lines = ["# 视觉方案 · 五个位（**本包不出图，只出方案**）", ""]
    if rejects:
        lines += ["> **视觉角色说这些位做不出来**：" + "、".join(
            SLOT_LABEL.get(k, k) for k in rejects), ""]
    for s in (v.get("slots") or []):
        if not isinstance(s, dict):
            continue
        slot = str(s.get("slot") or "").strip()
        prod = str(s.get("productivity") or "-")
        lines += ["## {}".format(SLOT_LABEL.get(slot, slot)), "",
                  "- 画面：{}".format(s.get("scene") or "-"),
                  "- 素材：{}".format("、".join(s.get("assets") or []) or "（无）"),
                  "- 素材缺口：{}".format(s.get("asset_gap") or "无"),
                  "- 可产性：**{}**{}".format(
                      prod, "（理由码 `{}`）".format(s.get("reason_code"))
                      if s.get("reason_code") else ""),
                  "- 为什么：{}".format(s.get("why") or "-")]
        if s.get("ask_user"):
            lines.append("- **要用户补**：{}".format(s["ask_user"]))
        t = s.get("text") if isinstance(s.get("text"), dict) else {}
        lines += ["- 文字：位置 {} · {} 字 / 上限 {} · {}".format(
            t.get("position") or "-", t.get("chars"), t.get("max_chars"), t.get("style") or "-"),
            "- 版式：{}".format(s.get("layout") or "-"),
            "- 平台适配：{}".format(s.get("platform_note") or "-"), ""]
    if v.get("summary"):
        lines += ["## 总结", "", str(v["summary"]), ""]
    if usage_note:
        lines += ["---", "", usage_note]
    return "\n".join(lines) + "\n"


def render_ruling_md(r, model=None, usage_note=""):
    r = r if isinstance(r, dict) else {}
    verdict = str(r.get("verdict") or "-")
    mark = {"放行": "✅", "打回": "↩️", "一票否决": "⛔"}.get(verdict, "?")
    lines = ["# 合规裁决 · {} {}".format(mark, verdict), ""]
    if verdict == "一票否决":
        lines += ["> **一票否决**：这套物料不能以任何形式发布。", "",
                  "> 理由：{}".format(r.get("veto_reason") or "-"), ""]
    lines += ["## 违规项", ""]
    viol = [v for v in (r.get("violations") or []) if isinstance(v, dict)]
    if viol:
        lines += ["| 等级 | 原文 | 违反 | 为什么 | 怎么改 |", "|---|---|---|---|---|"]
        for v in viol:
            lines.append("| {} | {} | {} | {} | {} |".format(
                v.get("level") or "-", (v.get("sentence") or v.get("quote") or "-")[:36],
                v.get("rule") or "-", v.get("what") or "-", v.get("fix") or "-"))
    else:
        lines.append("- （没有违规项）")
    for title, key in (("无法举证的效果/数据宣称", "risk_claims"),
                       ("疑似伪造的销量/评价/资质/检测报告", "forged_evidence"),
                       ("必改项", "required_fixes"),
                       ("要用户补的真实材料", "need_materials"),
                       ("仍未解决的问题（**不许抹平**）", "pending")):
        xs = [str(x) for x in (r.get(key) or []) if str(x or "").strip()]
        if xs:
            lines += ["", "## {}".format(title), ""] + ["- {}".format(x) for x in xs]
    if r.get("conclusion_note"):
        lines += ["", "## 结论说明", "", str(r["conclusion_note"])]
    if usage_note:
        lines += ["", "---", "", usage_note]
    return "\n".join(lines) + "\n"


def render_report_md(result):
    """`run` 的主交付物：整套物料 + **裁决记录**（谁否了谁、几轮、为什么）。"""
    mat = result.get("material") or {}
    r = result
    lines = ["# 上新物料与裁决记录 · {}".format(r.get("product") or "-"), "",
             "| 项 | 值 |", "|---|---|",
             "| 目标平台 | {} |".format(PLATFORM_LABEL.get(r.get("platform"), r.get("platform"))),
             "| 模型 | `{}` |".format(r.get("model")),
             "| 口径版本 | crew {} / prompt {} / gate {} |".format(
                 CREW_VERSION, PROMPT_VERSION, GATE_VERSION),
             "| 轮次上限 / 实际用了 | {} / {} |".format(
                 r.get("rounds_planned"), r.get("rounds_used")),
             "| 最终状态 | {} |".format(r.get("final_status")),
             "| 是否收敛 | {} |".format("是" if r.get("converged") else "**否（如实报未收敛）**"),
             ""]
    if r.get("not_converged_why"):
        lines += ["> {}".format(r["not_converged_why"]), ""]

    lines += ["## 一、协作过程：谁否了谁", ""]
    log = r.get("interaction_log") or []
    if log:
        lines += ["| # | 轮 | 谁 | 动作 | 对象 | 理由 |", "|---|---|---|---|---|---|"]
        for i, e in enumerate(log, 1):
            lines.append("| {} | {} | {} | {} | {} | {} |".format(
                i, e.get("round", "-"), e.get("role", "-"), e.get("action", "-"),
                e.get("target", "-"), (e.get("reason") or "")[:60]))
    else:
        lines.append("- （没有发生任何打回或否决：四个角色各写各的，**这属于假协作**）")
    lines += ["", "### 信息隔离证据（各角色实际收到了什么）", ""]
    for x in (r.get("isolation") or []):
        lines.append("- {}".format(x))
    lines += ["", "## 二、选品卡", ""]
    pc = r.get("pick") or {}
    pchk = (r.get("checks") or {}).get("pick") or {}
    lines += [render_pick_md(pc, pchk, mat).split("\n", 1)[1].strip(), ""]
    if r.get("copy"):
        lines += ["## 三、主图文案与详情页", "",
                  render_copy_md(r["copy"], r.get("model")).split("\n", 1)[1].strip(), ""]
    if r.get("visual"):
        vchk = (r.get("checks") or {}).get("visual") or {}
        lines += ["## 四、视觉方案", "",
                  render_visual_md(r["visual"], vchk, r.get("model")).split("\n", 1)[1].strip(), ""]
    rulings = r.get("rulings") or []
    if rulings:
        lines += ["## 五、合规裁决（逐轮留档）", ""]
        for i, x in enumerate(rulings, 1):
            rl = x.get("ruling") or {}
            lines += ["### 第 {} 轮裁决".format(x.get("round", i)), "",
                      render_ruling_md(rl, r.get("model")).split("\n", 1)[1].strip(), ""]
    lines += ["## 六、闸门自检", "", "| 闸门 | 结果 | 说明 |", "|---|---|---|"]
    gates = r.get("gates") or {}
    for key, name, _why in GATE_CATALOG:
        g = gates.get(key)
        if g is None:
            lines.append("| {} | — | 本次未评估 |".format(name))
        else:
            lines.append("| {} | {} | {} |".format(
                name, "✅ 通过" if g.get("ok") else "❌ 命中", (g.get("why") or "")[:70]))
    ex = (gates.get("compliance") or {}).get("quoted_from_material") or []
    mn = (gates.get("compliance") or {}).get("mentioned_as_warning") or []
    ct = (gates.get("compliance") or {}).get("contextual_only") or []
    mh = (gates.get("compliance") or {}).get("material_hits") or []
    if mh:
        lines += ["", "### 商品资料侧的违禁表述（**只报不拦**）", "",
                  "> 材料是用户给的事实来源，不是我们要发布的字；要发布的是产出物，"
                  "拦的是产出物。但下面这些说法必须改掉或补依据。", ""]
        for h in mh[:12]:
            lines.append("- 「{}」（{}）—— {}".format(
                h.get("word"), h.get("level"), h.get("why") or ""))
    if ex or mn or ct:
        lines += ["", "### 产出侧被语境排除的条目（**留在案上，不静默丢弃**）", ""]
        for title, xs in (("引用材料（材料里已有同词）", ex),
                          ("提到/在禁止（前后 24 字内有标记词）", mn),
                          ("中低风险（审类字段里多为描述性用语）", ct)):
            if xs:
                lines += ["**{}**：".format(title), ""]
                for h in xs[:8]:
                    lines.append("- 「{}」（{}）—— {}".format(
                        h.get("word"), h.get("in") or h.get("in_field") or "-",
                        h.get("not_counted_reason") or ""))
                lines.append("")
    tail = render_usage_section(r)
    if tail:
        lines += [tail]
    return "\n".join(lines) + "\n"


def render_usage_section(r):
    u = r.get("usage") or {}
    if not u:
        return ""
    lines = ["## 七、成本（真实 usage，**不编金额**）", "",
             "| 项 | 值 |", "|---|---|",
             "| 调用次数 | {} |".format(u.get("calls")),
             "| prompt tokens | {} |".format(u.get("prompt_tokens")),
             "| completion tokens | {} |".format(u.get("completion_tokens")),
             "| **总 token** | **{}** |".format(u.get("total_tokens")),
             ""]
    if u.get("price_note") or u.get("gateway_note"):
        lines += ["> {}".format(u.get("price_note") or u.get("gateway_note")), ""]
    per = u.get("per_call") or []
    if per:
        lines += ["| # | 阶段 | prompt | completion |", "|---|---|---|---|"]
        for i, x in enumerate(per, 1):
            lines.append("| {} | {} | {} | {} |".format(
                i, x.get("stage"), x.get("prompt_tokens"), x.get("completion_tokens")))
    return "\n".join(lines) + "\n"


def render_cost_md(rec):
    lines = ["# 报价 · 三剪客电商上新小组", "",
             "| 项 | 值 |", "|---|---|"]
    for c in rec.get("calls") or []:
        lines.append("| {} | {} 次，in {} + out {} tokens |".format(
            c.get("stage"), c.get("calls"), c.get("tokens_in"), c.get("tokens_out")))
    lines += ["| **合计** | **{} 次调用 · in {} + out {} tokens** |".format(
        rec.get("total_calls"), rec.get("tokens_in"), rec.get("tokens_out")), ""]
    lines += ["- 金额：{}".format(fmt_cost(rec)), ""]
    for n in rec.get("notes") or []:
        lines.append("> {}".format(n))
    lines += ["", "## 各角色的调用与说明", ""]
    for c in rec.get("calls") or []:
        lines.append("- **{}**：{}".format(c.get("stage"), c.get("note") or ""))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 角色调用（唯一的出口）
# ---------------------------------------------------------------------------

def _tracker(a):
    return CostTracker(getattr(a, "budget", None),
                       getattr(a, "price_in", None),
                       getattr(a, "price_out", None))


def invoke_role(role, prompt, system, a, tracker, key, label=None, out_tokens=1200):
    """调一次模型代表某个角色说话（**会花钱**）。

    顺序很要紧：**先预算核验、再发请求**。超预算时**一次调用都不发**（退出码 5）。
    """
    label = label or role_label(role)
    if getattr(a, "dry_run", False):
        return None, None, 0.0, None
    est_in = estimate_tokens_in(prompt)
    if tracker.over_budget(est_in, out_tokens):
        raise BudgetStop("预估成本已超预算，**未发起「{}」这次调用**（{}）".format(
            label, tracker.line()))
    sys.stderr.write("正在让【{}】说话（{}）…\n".format(label, getattr(a, "model", DEFAULT_MODEL)))
    t0 = time.time()
    content, usage = chat(
        prompt, system, model=getattr(a, "model", DEFAULT_MODEL),
        temperature=getattr(a, "temperature", 0.7),
        max_tokens=getattr(a, "max_tokens", 8192), key=key,
        json_mode=not getattr(a, "no_json_mode", False))
    elapsed = time.time() - t0
    tracker.add(usage, label)
    obj = parse_first_json(content)
    return obj, usage, elapsed, content


def stage_payload(stage, a, **extra):
    """断点 key 的输入载荷：**放全所有影响产出的维度**。"""
    p = {
        "stage": stage,
        "model": getattr(a, "model", DEFAULT_MODEL),
        "temperature": getattr(a, "temperature", 0.7),
        "max_tokens": getattr(a, "max_tokens", 8192),
        "json_mode": not getattr(a, "no_json_mode", False),
        "crew": CREW_VERSION, "prompt": PROMPT_VERSION, "gate": GATE_VERSION,
        "gate_keys": list(GATE_KEYS),
        "echo": {"sim": ECHO_SIM, "contain": ECHO_CONTAIN,
                 "max_ratio": ECHO_CONTAIN_MAX_RATIO,
                 "min_sample": ECHO_CONTAIN_MIN_SAMPLE,
                 "floor": ECHO_MIN_LEN_FLOOR},
        "anchor": {"sim": ANCHOR_SIM, "max_miss": ANCHOR_MAX_MISS,
                   "min_substr": ANCHOR_MIN_SUBSTR, "min_chars": ANCHOR_MIN_CHARS},
        "slot_max_chars": dict(SLOT_MAX_CHARS),
        "samples": list(PROMPT_SAMPLES),
        "pick_lines": {"margin_floor": PICK_MARGIN_FLOOR,
                       "return_rate_ceil": PICK_RETURN_RATE_CEIL},
    }
    p.update(extra)
    return p


def _cached(state, key):
    return (state.get("entries") or {}).get(key) if state is not None else None


def _put(state, key, payload, outdir):
    if state is None:
        return
    state.setdefault("entries", {})[key] = payload
    if outdir:
        save_state(outdir, state)


def _cost_line(a, tracker):
    if getattr(a, "json", False):
        return ""
    return tracker.line()


# ---------------------------------------------------------------------------
# 子命令：roles（零成本）
# ---------------------------------------------------------------------------

def run_roles(a):
    md = render_roles_md()
    obj = {
        "crew_version": CREW_VERSION,
        "roles": [{k: v for k, v in r.items()} for r in ROLE_INFO],
        "slots": {k: {"label": SLOT_LABEL[k], "ask": SLOT_ASK[k],
                      "max_chars": SLOT_MAX_CHARS[k]} for k in SLOT_KEYS},
        "visual_reason_codes": VISUAL_REASON_CODES,
        "gates": [{"key": k, "name": n, "why": w} for k, n, w in GATE_CATALOG],
        "echo_samples": list(PROMPT_SAMPLES),
    }
    if _json_out(obj, a, indent=2):
        return EXIT_OK
    print(md)
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：pick / copy / visual / compliance
# ---------------------------------------------------------------------------

def _load_material(a):
    if getattr(a, "text", None):
        raw = a.text
        path = None
    else:
        path = a.file
        raw = read_text(path, "商品资料")
    if not raw.strip():
        raise UsageError("商品资料是空的：{}".format(path or "--text"))
    return parse_material(raw), path


def run_pick(a):
    check_cost_opts(a)          # ← 会花钱的子命令第一步
    mat, path = _load_material(a)
    platform = a.platform
    if a.dry_run:
        # **在创建产物目录、建断点、发任何请求之前**退出：dry-run 一个字节都不落盘。
        prompt = build_pick_prompt(mat, platform)
        if _json_out({"dry_run": True, "role": "pick", "prompt": prompt}, a, indent=2):
            return EXIT_OK
        print(prompt)
        return EXIT_OK
    payload = role_input("pick", mat)
    _dump_role_input("pick", payload, enabled=not getattr(a, "hide_inputs", False))
    prompt = build_pick_prompt(mat, platform)
    tracker = _tracker(a)
    key, state, outdir = a.key, None, None
    if getattr(a, "outdir", None):
        ensure_outside_pkg(a.outdir, "--outdir")
        outdir = a.outdir
        state = load_state(outdir)
    skey = state_key("pick", stage_payload("pick", a,
                                           material=json_sha(mat.get("raw") or ""),
                                           platform=platform))
    hit = _cached(state, skey)
    if hit and not getattr(a, "force", False):
        pc, usage = hit["card"], hit.get("usage") or {}
        sys.stderr.write("选品卡已在断点里，跳过（零成本）。\n")
    else:
        obj, usage, _el, _raw = invoke_role(
            "pick", prompt, PICK_SYSTEM, a, tracker, key,
            out_tokens=ROLE_OUT_TOKENS["pick"])
        pc = obj if isinstance(obj, dict) else {}
        _put(state, skey, {"card": pc, "usage": usage}, outdir)
    ok_sp, bad_sp, sp_stat = anchor_records(pc.get("sellpoints"), mat.get("raw") or "",
                                            label="卖点")
    ok_rk, bad_rk, rk_stat = anchor_records(pc.get("risks"), mat.get("raw") or "",
                                            label="风险")
    pc["sellpoints"] = ok_sp
    pc["risks"] = ok_rk
    pc["unanchored"] = bad_sp + bad_rk
    anchor_stat = {**sp_stat, "total": sp_stat["total"] + rk_stat["total"],
                   "verified": sp_stat["verified"] + rk_stat["verified"],
                   "unanchored": sp_stat["unanchored"] + rk_stat["unanchored"]}
    anchor_stat["miss_rate"] = (round(anchor_stat["unanchored"] / float(anchor_stat["total"]), 3)
                                if anchor_stat["total"] else 0.0)
    anchor_stat["ok"] = (not anchor_stat["unanchored"]
                         or anchor_stat["miss_rate"] <= ANCHOR_MAX_MISS)
    if not anchor_stat["ok"]:
        anchor_stat["why"] = ("{} 条里有 {} 条引文在商品资料里找不到"
                              "（未锚定率 {:.0%} > {:.0%}）".format(
                                  anchor_stat["total"], anchor_stat["unanchored"],
                                  anchor_stat["miss_rate"], ANCHOR_MAX_MISS))
    ok, issues, chk = check_pick(pc, mat)
    gates = evaluate_gates(material_text=mat.get("raw") or "", pick_card=pc,
                           pick={"ok": ok, "issues": issues, "detail": chk},
                           anchors=anchor_stat)
    failed = gate_failed(gates)
    rc = EXIT_GATE if failed else EXIT_OK
    result = {
        "mode": "pick", "role": "pick",
        "model": a.model, "platform": platform,
        "crew_version": CREW_VERSION, "prompt_version": PROMPT_VERSION,
        "gate_version": GATE_VERSION,
        "source": {"path": path, "chars": len(mat.get("raw") or "")},
        "card": pc, "check": chk, "anchors": anchor_stat,
        "gates": gates, "veto": bool(chk.get("veto")),
        "usage": usage_dict(tracker, [usage]),
    }
    if failed:
        _gate_stderr("选品", gates)
    if chk.get("veto"):
        sys.stderr.write(_red("\n选品角色**否决**了这个品：{}\n".format(
            chk.get("veto_reason") or "-")) + "整条流水线到此为止。\n")
    _emit(a, result, render_pick_md(pc, chk, mat), ok=not failed)
    return rc


def run_copy(a):
    check_cost_opts(a)
    mat, path = _load_material(a)
    pick_card = load_artifact(getattr(a, "pick", None), "card", "选品卡") if getattr(a, "pick", None) else None
    slim = _slim_pick_for_downstream(pick_card)
    rejects = load_artifact(getattr(a, "rejects", None), "rejected_slots", "打回意见") \
        if getattr(a, "rejects", None) else None
    if isinstance(rejects, dict):        # 吃 `visual --json` 的完整结果时，取它里面的打回清单
        rejects = rejects.get("feasibility", {}).get("rejects") or rejects.get("rejects") or []
    if a.dry_run:
        prompt = build_copy_prompt(mat, a.platform, slim, rejects)
        if _json_out({"dry_run": True, "role": "copy", "prompt": prompt}, a, indent=2):
            return EXIT_OK
        print(prompt)
        return EXIT_OK
    payload = role_input("copy", mat, pick_card=pick_card, rejects=rejects)
    _dump_role_input("copy", payload, enabled=not getattr(a, "hide_inputs", False))
    prompt = build_copy_prompt(mat, a.platform, slim, rejects)
    tracker = _tracker(a)
    key, state, outdir = a.key, None, None
    if getattr(a, "outdir", None):
        ensure_outside_pkg(a.outdir, "--outdir")
        outdir = a.outdir
        state = load_state(outdir)
    skey = state_key("copy", stage_payload(
        "copy", a, material=json_sha(mat.get("raw") or ""), platform=a.platform,
        pick=json_sha(slim), rejects=json_sha(rejects or [])))
    hit = _cached(state, skey)
    if hit and not getattr(a, "force", False):
        cp, usage = hit["copy"], hit.get("usage") or {}
        sys.stderr.write("文案已在断点里，跳过（零成本）。\n")
    else:
        obj, usage, _el, _raw = invoke_role(
            "copy", prompt, COPY_SYSTEM, a, tracker, key,
            out_tokens=ROLE_OUT_TOKENS["copy"])
        cp = obj if isinstance(obj, dict) else {}
        _put(state, skey, {"copy": cp, "usage": usage}, outdir)
    ok_ev, bad_ev, ev_stat = anchor_records(
        [{"quote": (cp.get("slot_evidence") or {}).get(k), "slot": k} for k in SLOT_KEYS
         if str((cp.get("slot_evidence") or {}).get(k) or "").strip()],
        mat.get("raw") or "", label="主图位依据")
    d = cp.get("detail") if isinstance(cp.get("detail"), dict) else {}
    ok_ds, bad_ds, ds_stat = anchor_records(d.get("sections"), mat.get("raw") or "",
                                           label="详情页依据")
    if isinstance(d, dict):
        d["sections"] = ok_ds
    anchor_stat = {"ok": True,
                   "total": ev_stat["total"] + ds_stat["total"],
                   "verified": ev_stat["verified"] + ds_stat["verified"],
                   "unanchored": ev_stat["unanchored"] + ds_stat["unanchored"],
                   "rules": {}, "unanchored_items": bad_ev + bad_ds}
    anchor_stat["miss_rate"] = (round(anchor_stat["unanchored"] / float(anchor_stat["total"]), 3)
                                if anchor_stat["total"] else 0.0)
    if anchor_stat["unanchored"] and anchor_stat["miss_rate"] > ANCHOR_MAX_MISS:
        anchor_stat["ok"] = False
        anchor_stat["why"] = ("{} 条依据里 {} 条引文在商品资料里找不到（未锚定率 {:.0%}）"
                              .format(anchor_stat["total"], anchor_stat["unanchored"],
                                      anchor_stat["miss_rate"]))
    slots_ok, slot_issues, slot_detail = check_slots(cp, None)
    gates = evaluate_gates(material_text=mat.get("raw") or "", copy_obj=cp,
                           slots_ok=slots_ok, slot_issues=slot_issues,
                           slot_detail=slot_detail, anchors=anchor_stat)
    failed = gate_failed(gates)
    rc = EXIT_GATE if failed else EXIT_OK
    result = {"mode": "copy", "role": "copy", "model": a.model, "platform": a.platform,
              "crew_version": CREW_VERSION, "prompt_version": PROMPT_VERSION,
              "gate_version": GATE_VERSION,
              "source": {"path": path, "chars": len(mat.get("raw") or "")},
              "copy": cp, "anchors": anchor_stat, "slots": slot_detail,
              "gates": gates, "usage": usage_dict(tracker, [usage])}
    if failed:
        _gate_stderr("文案", gates)
    _emit(a, result, render_copy_md(cp, a.model), ok=not failed)
    return rc


def run_visual(a):
    check_cost_opts(a)
    mat, path = _load_material(a)
    copy_obj = load_artifact(getattr(a, "copy", None), "copy", "文案") \
        if getattr(a, "copy", None) else None
    if isinstance(copy_obj, dict) and "copy" in copy_obj and "slots" not in copy_obj:
        copy_obj = copy_obj.get("copy") or copy_obj     # 直接吃 `copy` 子命令的 --json 产物
    rejects = load_artifact(getattr(a, "rejects", None), "rejected_slots", "打回意见") \
        if getattr(a, "rejects", None) else None
    if isinstance(rejects, dict):
        rejects = rejects.get("feasibility", {}).get("rejects") or rejects.get("rejects") or []
    if a.dry_run:
        prompt = build_visual_prompt(mat, a.platform, copy_obj, rejects)
        if _json_out({"dry_run": True, "role": "visual", "prompt": prompt}, a, indent=2):
            return EXIT_OK
        print(prompt)
        return EXIT_OK
    payload = role_input("visual", mat, copy_obj=copy_obj, rejects=rejects)
    _dump_role_input("visual", payload, enabled=not getattr(a, "hide_inputs", False))
    prompt = build_visual_prompt(mat, a.platform, copy_obj, rejects)
    tracker = _tracker(a)
    key, state, outdir = a.key, None, None
    if getattr(a, "outdir", None):
        ensure_outside_pkg(a.outdir, "--outdir")
        outdir = a.outdir
        state = load_state(outdir)
    skey = state_key("visual", stage_payload(
        "visual", a, material=json_sha(mat.get("raw") or ""), platform=a.platform,
        copy=json_sha(copy_obj or {}), rejects=json_sha(rejects or [])))
    hit = _cached(state, skey)
    if hit and not getattr(a, "force", False):
        vo, usage = hit["visual"], hit.get("usage") or {}
        sys.stderr.write("视觉方案已在断点里，跳过（零成本）。\n")
    else:
        obj, usage, _el, _raw = invoke_role(
            "visual", prompt, VISUAL_SYSTEM, a, tracker, key,
            out_tokens=ROLE_OUT_TOKENS["visual"])
        vo = obj if isinstance(obj, dict) else {}
        _put(state, skey, {"visual": vo, "usage": usage}, outdir)
    feas_ok, feas_issues, feas_detail = check_visual_feasibility(vo)
    slots_ok, slot_issues, slot_detail = check_slots(copy_obj, vo)
    gates = evaluate_gates(material_text=mat.get("raw") or "", copy_obj=copy_obj,
                           visual_obj=vo, slots_ok=slots_ok, slot_issues=slot_issues,
                           slot_detail=slot_detail)
    gates["visual_feasibility"] = {"ok": feas_ok, "issues": feas_issues,
                                   "detail": feas_detail,
                                   "why": "；".join(i.get("why") or "" for i in feas_issues)}
    failed = gate_failed(gates) or not feas_ok
    rc = EXIT_GATE if failed else EXIT_OK
    rejects_out = feas_detail.get("rejects") or []
    if rejects_out:
        sys.stderr.write(_red("\n视觉角色打回了 {} 个位：{}\n".format(
            len(rejects_out),
            "、".join(SLOT_LABEL.get(x["slot"], x["slot"]) for x in rejects_out)))
            + "这几个位必须改到能产出，或由用户补齐素材。\n")
    result = {"mode": "visual", "role": "visual", "model": a.model, "platform": a.platform,
              "crew_version": CREW_VERSION,
              "source": {"path": path, "chars": len(mat.get("raw") or "")},
              "visual": vo, "feasibility": feas_detail,
              "rejected_slots": rejects_out, "slots": slot_detail,
              "gates": gates, "usage": usage_dict(tracker, [usage])}
    if failed:
        _gate_stderr("视觉", gates)
    _emit(a, result, render_visual_md(vo, feas_detail, a.model), ok=not failed)
    return rc


def _ruling_anchors(ruling, bundle_text):
    """合规裁决里的引文锚点到**它自己审的那份物料**上。"""
    ok_v, bad_v, v_stat = anchor_records(ruling.get("violations"), bundle_text,
                                         label="违规项引文")
    ruling["violations"] = ok_v
    ruling["unanchored_quotes"] = bad_v
    extra_total = len([x for x in (ruling.get("risk_claims") or []) if str(x or "").strip()])
    stat = {"ok": True, "total": v_stat["total"] + extra_total,
            "verified": v_stat["verified"] + extra_total,
            "unanchored": v_stat["unanchored"], "rules": v_stat["rules"],
            "unanchored_items": bad_v}
    stat["miss_rate"] = (round(stat["unanchored"] / float(stat["total"]), 3)
                         if stat["total"] else 0.0)
    if stat["unanchored"] and stat["miss_rate"] > ANCHOR_MAX_MISS:
        stat["ok"] = False
        stat["why"] = ("{} 条引文里 {} 条在物料里找不到（未锚定率 {:.0%} > {:.0%}）"
                       .format(stat["total"], stat["unanchored"], stat["miss_rate"],
                               ANCHOR_MAX_MISS))
    return stat


def run_compliance(a):
    check_cost_opts(a)
    mat, path = _load_material(a)
    bundle = load_artifact(getattr(a, "bundle", None), "bundle", "物料") \
        if getattr(a, "bundle", None) else None
    ruling_prev = load_artifact(getattr(a, "prev", None), "ruling", "上一轮裁决") \
        if getattr(a, "prev", None) else None
    if a.dry_run:
        prompt = build_compliance_prompt(mat, a.platform, bundle or {}, ruling_prev)
        if _json_out({"dry_run": True, "role": "compliance", "prompt": prompt}, a, indent=2):
            return EXIT_OK
        print(prompt)
        return EXIT_OK
    payload = role_input("compliance", mat, pick_card=(bundle or {}).get("选品卡要点"),
                         copy_obj={"slots": (bundle or {}).get("主图五位文案"),
                                   "detail": (bundle or {}).get("详情页文案")},
                         visual=(bundle or {}).get("五位视觉方案"), ruling=ruling_prev)
    _dump_role_input("compliance", payload, enabled=not getattr(a, "hide_inputs", False))
    prompt = build_compliance_prompt(mat, a.platform, bundle or {}, ruling_prev)
    tracker = _tracker(a)
    key, state, outdir = a.key, None, None
    if getattr(a, "outdir", None):
        ensure_outside_pkg(a.outdir, "--outdir")
        outdir = a.outdir
        state = load_state(outdir)
    skey = state_key("compliance", stage_payload(
        "compliance", a, material=json_sha(mat.get("raw") or ""), platform=a.platform,
        bundle=json_sha(bundle or {}), prev=json_sha(ruling_prev or {})))
    hit = _cached(state, skey)
    if hit and not getattr(a, "force", False):
        ruling, usage = hit["ruling"], hit.get("usage") or {}
        sys.stderr.write("裁决已在断点里，跳过（零成本）。\n")
    else:
        obj, usage, _el, _raw = invoke_role(
            "compliance", prompt, COMPLIANCE_SYSTEM, a, tracker, key,
            out_tokens=ROLE_OUT_TOKENS["compliance"])
        ruling = obj if isinstance(obj, dict) else {}
        _put(state, skey, {"ruling": ruling, "usage": usage}, outdir)
    btext = bundle_text_for_ruling(
        mat, (bundle or {}).get("选品卡要点"),
        {"slots": (bundle or {}).get("主图五位文案"),
         "detail": (bundle or {}).get("详情页文案")},
        (bundle or {}).get("五位视觉方案"))
    anchor_stat = _ruling_anchors(ruling, btext)
    gates = evaluate_gates(material_text=mat.get("raw") or "", ruling=ruling,
                           anchors=anchor_stat)
    failed = gate_failed(gates)
    rc = EXIT_GATE if failed else EXIT_OK
    verdict = str(ruling.get("verdict") or "-")
    if verdict == "一票否决":
        sys.stderr.write(_red("\n合规角色**一票否决**：{}\n".format(
            ruling.get("veto_reason") or "-")) + "这套物料不许放行。\n")
    elif verdict == "打回":
        sys.stderr.write(_red("\n合规角色打回：{} 条整改要求\n".format(
            len(ruling.get("required_fixes") or []))))
    result = {"mode": "compliance", "role": "compliance", "model": a.model,
              "platform": a.platform, "crew_version": CREW_VERSION,
              "source": {"path": path, "chars": len(mat.get("raw") or "")},
              "ruling": ruling, "verdict": verdict, "anchors": anchor_stat,
              "gates": gates, "usage": usage_dict(tracker, [usage])}
    if failed:
        _gate_stderr("裁决", gates)
    _emit(a, result, render_ruling_md(ruling, a.model), ok=not failed)
    return rc


# ---------------------------------------------------------------------------
# 子命令：run（一条命令出整套物料 + 裁决记录）
#
# 轮次语义（**必须一眼看懂，否则"几轮"就会被误解**）：
#   一轮 = ①文案写 → ②视觉判可产性 → ③合规裁决
#   视觉打回 → 该轮的文案按打回意见重写（内部重试，最多 COPY_RETRY 次）
#   合规打回/否决 → 进入下一轮（文案带着合规的整改要求重写）
#   轮次用尽仍在否决 → **如实报未收敛**，退出码 3（绝不输出一份"看起来通过了"的物料）
# ---------------------------------------------------------------------------

COPY_RETRY = 2      # 一轮内文案被视觉打回后的最多重写次数

# 打回意见指向**上游**（选品卡）的标记词。
# 事故复盘（本包真机第三次跑抓到的，两轮都是**误判**）：
# 原本的标记表里有「资质」，于是
# 「必改项：主图 s5 删除「食品生产许可证SC…」，改为不含**资质**的信任表述」
# 被当成"只有选品能执行"的要求回传给了选品 —— 而这条明明是文案的活。
# 后果是：多花一次选品调用、选品卡一字没变、真正该改的文案没被这条驱动。
# 「资质」「卖点」这类词**在整改要求里到处都是**，不能当标记词。
# 现在只认**明确指向选品卡结构**的说法：说得清是选品卡/商品名/类目的才回传，
# 说不清就不回传（宁可漏回传，也不要瞎回传 —— 瞎回传会白花钱还让日志说不清）。
UPSTREAM_FIX_MARKERS = ("选品卡", "商品名", "品名", "类目", "标题里的", "product")

# 否定语境：出现这些词的条目**不判为上游项**（「商品名不用改」不该触发重开）
UPSTREAM_NEGATIONS = ("不用改", "无需改", "不必改", "不需要改", "保留", "不属于选品",
                      "文案改", "文案侧")


def upstream_fix_items(ruling):
    """从合规的整改要求里挑出**必须由选品角色处理**的条目（没有就返回空）。

    判据（必须同时满足）：提到 `UPSTREAM_FIX_MARKERS` 里的词，且不含否定语境。
    """
    out = []
    for x in (ruling or {}).get("required_fixes") or []:
        s = str(x or "")
        if not any(m in s for m in UPSTREAM_FIX_MARKERS):
            continue
        if any(neg in s for neg in UPSTREAM_NEGATIONS):
            continue
        out.append(s)
    return out


def _dump_inputs(a, role, payload, isolation):
    isolation.append(isolation_note(role, payload))
    _dump_role_input(role, payload, enabled=not getattr(a, "hide_inputs", False))


def _stage_call(a, stage, payload, prompt, system, tracker, key, out_tokens, label,
                state, outdir):
    """一次带断点的角色调用。返回 (obj, usage, from_cache)。"""
    skey = state_key(stage, payload)
    hit = _cached(state, skey)
    if hit and not getattr(a, "force", False):
        sys.stderr.write("{} 已在断点里，跳过（零成本）。\n".format(label))
        return hit.get("obj"), hit.get("usage") or {}, True
    obj, usage, _el, _raw = invoke_role(stage if stage in ROLE_BY_KEY else "copy",
                                        prompt, system, a, tracker, key,
                                        label=label, out_tokens=out_tokens)
    obj = obj if isinstance(obj, dict) else {}
    _put(state, skey, {"obj": obj, "usage": usage}, outdir)
    return obj, usage, False


def run_run(a):
    check_cost_opts(a)                          # ← 第一个会被花钱的子命令：先校验
    mat, path = _load_material(a)
    platform = a.platform
    rounds_planned = max(1, int(getattr(a, "rounds", 2) or 2))
    outdir = a.outdir
    # 闸门八先跑：`--outdir` 指到包内是**用法错误**，与 dry-run 与否无关（退出码 2）
    ensure_outside_pkg(outdir, "--outdir")
    if a.dry_run:
        # dry-run：只把「第一个角色会看到什么」打出来，**不建目录、不写文件、不发请求**。
        prompt = build_pick_prompt(mat, platform)
        if _json_out({"dry_run": True, "role": "pick", "prompt": prompt}, a, indent=2):
            return EXIT_OK
        print(prompt)
        return EXIT_OK
    state = load_state(outdir)
    tracker = _tracker(a)
    key = a.key
    isolation, interaction, usages, rulings_log = [], [], [], []
    base = {"material": json_sha(mat.get("raw") or ""), "platform": platform}
    sys.stderr.write("\n=== 三剪客 · 电商上新小组开始协作（平台 {}，轮次上限 {}）===\n\n".format(
        PLATFORM_LABEL[platform], rounds_planned))

    # ---- ① 选品（第一个角色，也是第一个能否决的角色）----
    payload = role_input("pick", mat)
    _dump_inputs(a, "pick", payload, isolation)
    prompt = build_pick_prompt(mat, platform)
    pc, usage, _cached_hit = _stage_call(
        a, "pick", stage_payload("pick", a, **base), prompt, PICK_SYSTEM, tracker, key,
        ROLE_OUT_TOKENS["pick"], role_label("pick"), state, outdir)
    usages.append(usage)
    ok_sp, bad_sp, sp_stat = anchor_records(pc.get("sellpoints"), mat.get("raw") or "",
                                            label="卖点")
    ok_rk, bad_rk, rk_stat = anchor_records(pc.get("risks"), mat.get("raw") or "", label="风险")
    pc["sellpoints"] = ok_sp
    pc["risks"] = ok_rk
    pc["unanchored"] = bad_sp + bad_rk
    pick_anchors = {"ok": True,
                    "total": sp_stat["total"] + rk_stat["total"],
                    "verified": sp_stat["verified"] + rk_stat["verified"],
                    "unanchored": sp_stat["unanchored"] + rk_stat["unanchored"],
                    "rules": {}, "unanchored_items": bad_sp + bad_rk}
    pick_anchors["miss_rate"] = (round(pick_anchors["unanchored"]
                                       / float(pick_anchors["total"]), 3)
                                 if pick_anchors["total"] else 0.0)
    if pick_anchors["unanchored"] and pick_anchors["miss_rate"] > ANCHOR_MAX_MISS:
        pick_anchors["ok"] = False
        pick_anchors["why"] = ("{} 条引文里 {} 条在商品资料里找不到（未锚定率 {:.0%}）"
                               .format(pick_anchors["total"], pick_anchors["unanchored"],
                                       pick_anchors["miss_rate"]))
    pick_ok, pick_issues, pick_chk = check_pick(pc, mat)
    interaction.append({"round": 0, "role": role_label("pick"), "action": "出选品卡",
                        "target": pc.get("product") or "-",
                        "reason": "结论 {}".format(pick_chk.get("conclusion") or "-")})
    if pick_chk.get("veto"):
        interaction.append({"round": 0, "role": role_label("pick"), "action": "否决",
                            "target": "这个品", "reason": pick_chk.get("veto_reason") or "-"})
    sys.stderr.write("\n【{}】结论：{}（否决={}）\n".format(
        role_label("pick"), pick_chk.get("conclusion") or "-",
        "是" if pick_chk.get("veto") else "否"))
    if pick_chk.get("veto"):
        gates = evaluate_gates(material_text=mat.get("raw") or "", pick_card=pc,
                               pick={"ok": pick_ok, "issues": pick_issues,
                                     "detail": pick_chk},
                               anchors=pick_anchors)
        result = _run_result(a, mat, path, platform, rounds_planned, 0, pc, None, None,
                             None, pick_chk, {}, [], gates, interaction, isolation,
                             usages, tracker, rulings_log,
                             converged=False, final_status="选品否决（未进入后续角色）",
                             not_converged_why="选品角色否决了这个品，整条流水线停在第 0 轮。")
        if gate_failed(gates):
            _gate_stderr("协作", gates)
        _emit(a, result, render_report_md(result), ok=not gate_failed(gates))
        return EXIT_GATE if gate_failed(gates) else EXIT_OK

    slim = _slim_pick_for_downstream(pc)
    copy_obj = visual_obj = ruling = None
    rejects = None
    pending_fixes = None
    pick_fixes = None            # 合规打回里**只有选品能执行**的条目（上游回传）
    rounds_used = 0
    final_status = "未收敛"
    converged = False
    not_converged_why = ""
    gates = {}
    checks = {}

    for rnd in range(1, rounds_planned + 1):
        rounds_used = rnd
        sys.stderr.write("\n--- 第 {} 轮 ---\n".format(rnd))
        # ---- ⓪ 上游回传：合规上一轮点名要改选品卡，就先把选品卡重开 ----
        if pick_fixes:
            sys.stderr.write("合规上一轮点名要改选品卡，把 {} 条要求回传给【{}】重开…\n".format(
                len(pick_fixes), role_label("pick")))
            ppayload = role_input("pick", mat)
            _dump_inputs(a, "pick", ppayload, isolation)
            pprompt = build_pick_prompt(mat, platform, fixes=pick_fixes)
            pc, pusage, _hit = _stage_call(
                a, "pick", stage_payload("pick", a, round_no=rnd, rework=True, **base,
                                         fixes=json_sha(pick_fixes)),
                pprompt, PICK_SYSTEM, tracker, key, ROLE_OUT_TOKENS["pick"],
                "{}（第 {} 轮重开）".format(role_label("pick"), rnd), state, outdir)
            usages.append(pusage)
            ok_sp, bad_sp, sp_stat = anchor_records(pc.get("sellpoints"),
                                                    mat.get("raw") or "", label="卖点")
            ok_rk, bad_rk, rk_stat = anchor_records(pc.get("risks"),
                                                    mat.get("raw") or "", label="风险")
            pc["sellpoints"], pc["risks"] = ok_sp, ok_rk
            pc["unanchored"] = bad_sp + bad_rk
            pick_anchors = {**pick_anchors,
                            "total": sp_stat["total"] + rk_stat["total"],
                            "verified": sp_stat["verified"] + rk_stat["verified"],
                            "unanchored": sp_stat["unanchored"] + rk_stat["unanchored"]}
            pick_anchors["miss_rate"] = (round(pick_anchors["unanchored"]
                                               / float(pick_anchors["total"]), 3)
                                         if pick_anchors["total"] else 0.0)
            pick_anchors["ok"] = (not pick_anchors["unanchored"]
                                  or pick_anchors["miss_rate"] <= ANCHOR_MAX_MISS)
            pick_ok, pick_issues, pick_chk = check_pick(pc, mat)
            slim = _slim_pick_for_downstream(pc)
            interaction.append({
                "round": rnd, "role": role_label("compliance"), "action": "打回上游",
                "target": role_label("pick"),
                "reason": "；".join(str(x) for x in pick_fixes)[:160]})
            interaction.append({"round": rnd, "role": role_label("pick"), "action": "按合规要求重开",
                                "target": pc.get("product") or "-",
                                "reason": "结论 {}".format(pick_chk.get("conclusion") or "-")})
            if pick_chk.get("veto"):
                interaction.append({"round": rnd, "role": role_label("pick"), "action": "否决",
                                    "target": "这个品",
                                    "reason": pick_chk.get("veto_reason") or "-"})
                sys.stderr.write(_red("重开后选品角色**否决**了这个品：{}\n".format(
                    pick_chk.get("veto_reason") or "-")))
                break
            pick_fixes = None
        # ---- ② 文案（可能被视觉连续打回）----
        attempt, copy_obj, cp_rejects = 0, None, rejects
        while True:
            cpayload = role_input("copy", mat, pick_card=pc, rejects=cp_rejects)
            _dump_inputs(a, "copy", cpayload, isolation)
            cprompt = build_copy_prompt(mat, platform, slim, cp_rejects)
            copy_obj, cusage, _hit = _stage_call(
                a, "copy", stage_payload("copy", a, round_no=rnd, attempt=attempt,
                                         **base, pick=json_sha(slim),
                                         rejects=json_sha(cp_rejects or [])),
                cprompt, COPY_SYSTEM, tracker, key, ROLE_OUT_TOKENS["copy"],
                "{}（第 {} 轮/第 {} 次）".format(role_label("copy"), rnd, attempt + 1),
                state, outdir)
            usages.append(cusage)
            # ---- ③ 视觉：判可产性，可以打回 ----
            vpayload = role_input("visual", mat, copy_obj=copy_obj, rejects=cp_rejects)
            _dump_inputs(a, "visual", vpayload, isolation)
            vprompt = build_visual_prompt(mat, platform, copy_obj, cp_rejects)
            visual_obj, vusage, _hit = _stage_call(
                a, "visual", stage_payload("visual", a, round_no=rnd, attempt=attempt,
                                           **base, copy=json_sha(copy_obj),
                                           rejects=json_sha(cp_rejects or [])),
                vprompt, VISUAL_SYSTEM, tracker, key, ROLE_OUT_TOKENS["visual"],
                "{}（第 {} 轮/第 {} 次）".format(role_label("visual"), rnd, attempt + 1),
                state, outdir)
            usages.append(vusage)
            feas_ok, feas_issues, feas_detail = check_visual_feasibility(visual_obj)
            new_rejects = feas_detail.get("rejects") or []
            if attempt == 0:
                interaction.append({"round": rnd, "role": role_label("copy"),
                                    "action": "出文案", "target": "主图五位 + 详情页",
                                    "reason": "{} 位文案".format(
                                        len([k for k in SLOT_KEYS
                                             if str((copy_obj.get("slots") or {}).get(k)
                                                    or "").strip()]))})
            if feas_detail.get("declared") is not None:
                interaction.append({"round": rnd, "role": role_label("visual"),
                                    "action": "判可产性",
                                    "target": "第 {} 次视觉方案".format(attempt + 1),
                                    "reason": "可产 {} 位，打回 {} 位".format(
                                        5 - len(new_rejects), len(new_rejects))})
            if not new_rejects:
                break
            interaction.append({
                "round": rnd, "role": role_label("visual"), "action": "打回",
                "target": "、".join(SLOT_LABEL.get(x["slot"], x["slot"]) for x in new_rejects),
                "reason": "；".join("{}（{}）".format(
                    SLOT_LABEL.get(x["slot"], x["slot"]), x.get("reason_code") or "-")
                    for x in new_rejects)})
            sys.stderr.write(_red(
                "\n视觉角色打回 {} 个位（{}）\n".format(
                    len(new_rejects),
                    "、".join(SLOT_LABEL.get(x["slot"], x["slot"]) for x in new_rejects))))
            cp_rejects = new_rejects
            rejects = new_rejects
            attempt += 1
            if attempt >= COPY_RETRY:
                sys.stderr.write("文案已重写 {} 次，这些位仍然做不出来 —— "
                                 "按未收敛处理（不假装做出来了）。\n".format(COPY_RETRY))
                break
        slots_ok, slot_issues, slot_detail = check_slots(copy_obj, visual_obj)
        checks["visual"] = feas_detail
        # ---- ④ 合规裁决 ----
        bundle = {"选品卡要点": slim,
                  "主图五位文案": (copy_obj or {}).get("slots"),
                  "详情页文案": (copy_obj or {}).get("detail"),
                  "五位视觉方案": visual_obj}
        bpayload = role_input("compliance", mat, pick_card=slim,
                              copy_obj=copy_obj, visual=visual_obj, ruling=ruling)
        _dump_inputs(a, "compliance", bpayload, isolation)
        if pending_fixes:
            bpayload["上一轮自己的整改要求（本轮复裁）"] = pending_fixes
        bprompt = build_compliance_prompt(mat, platform, bundle, ruling)
        ruling, rusage, _hit = _stage_call(
            a, "compliance", stage_payload("compliance", a, round_no=rnd, **base,
                                           bundle=json_sha(bundle),
                                           prev=json_sha(ruling or {})),
            bprompt, COMPLIANCE_SYSTEM, tracker, key, ROLE_OUT_TOKENS["compliance"],
            "{}（第 {} 轮）".format(role_label("compliance"), rnd), state, outdir)
        usages.append(rusage)
        btext = bundle_text_for_ruling(mat, slim,
                                       {"slots": (copy_obj or {}).get("slots"),
                                        "detail": (copy_obj or {}).get("detail")},
                                       visual_obj)
        ruling_anchors = _ruling_anchors(ruling, btext)
        verdict = str(ruling.get("verdict") or "-")
        rulings_log.append({"round": rnd, "ruling": ruling, "anchors": ruling_anchors})
        pending_fixes = ruling.get("required_fixes") or []
        gates = evaluate_gates(material_text=mat.get("raw") or "", pick_card=pc,
                               copy_obj=copy_obj, visual_obj=visual_obj, ruling=ruling,
                               slots_ok=slots_ok, slot_issues=slot_issues,
                               slot_detail=slot_detail, anchors=ruling_anchors)
        gates["pick"] = {"ok": pick_ok, "issues": pick_issues, "detail": pick_chk}
        failed = gate_failed(gates)
        sys.stderr.write("\n【{}】裁决：{}（闸门{}）\n".format(
            role_label("compliance"), verdict, "命中" if failed else "全过"))
        if verdict == "放行" and not failed:
            interaction.append({"round": rnd, "role": role_label("compliance"),
                                "action": "放行", "target": "整套物料",
                                "reason": ruling.get("conclusion_note") or "-"})
            final_status, converged = "放行", True
            break
        interaction.append({
            "round": rnd, "role": role_label("compliance"),
            "action": ("一票否决" if verdict == "一票否决" else
                       ("打回" if verdict == "打回" else "闸门拦截")),
            "target": "整套物料",
            "reason": (ruling.get("veto_reason") if verdict == "一票否决"
                       else "；".join(str(x) for x in (pending_fixes or []))[:120]
                       or "；".join(i.get("why") or "" for _, i in gate_hits(gates))[:120])})
        if verdict == "一票否决":
            sys.stderr.write(_red("合规角色**一票否决**：{}\n".format(
                ruling.get("veto_reason") or "-")))
        if failed:
            _gate_stderr("第 {} 轮协作".format(rnd), gates)
        if rnd < rounds_planned:
            # 把「只有选品能执行」的整改要求回传给选品，下一轮先重开选品卡。
            # 不这么做的话，商品名/卖点体系一字不变，下一轮只是换个说法再打回一次 ——
            # 那叫"看起来在重开"，不叫协作。
            pick_fixes = upstream_fix_items(ruling) or None
            if pick_fixes:
                sys.stderr.write("其中 {} 条整改要求指向选品卡，下一轮会先回传给【{}】。\n".format(
                    len(pick_fixes), role_label("pick")))
            sys.stderr.write("带着整改要求进入第 {} 轮重开。\n".format(rnd + 1))

    if not converged:
        last = rulings_log[-1] if rulings_log else {}
        last_ruling = last.get("ruling") or {}
        v = str(last_ruling.get("verdict") or "未裁决")
        not_converged_why = (
            "轮次用尽（上限 {}）仍在「{}」。最后一条否决理由：{}；未解决的整改项：{}。"
            "**本包不会为了给出一份好看的物料而假装谈拢** —— 交付物里保留每一轮的裁决与原样引文，"
            "请补齐材料或改品后重跑。".format(
                rounds_planned, v,
                last_ruling.get("veto_reason") or "（无）",
                "；".join(str(x) for x in (last_ruling.get("required_fixes") or [])) or "（无）"))
        final_status = "未收敛（{}）".format(v)
    result = _run_result(a, mat, path, platform, rounds_planned, rounds_used, pc, copy_obj,
                         visual_obj, ruling, pick_chk, checks, rulings_log, gates,
                         interaction, isolation, usages, tracker, rulings_log,
                         converged=converged, final_status=final_status,
                         not_converged_why=not_converged_why)
    rc = EXIT_OK if (converged and not gate_failed(gates)) else EXIT_GATE
    _emit(a, result, render_report_md(result), ok=not rc)
    return rc


def _run_result(a, mat, path, platform, rounds_planned, rounds_used, pick_card, copy_obj,
                visual_obj, ruling, pick_chk, checks, rulings_log, gates, interaction,
                isolation, usages, tracker, _rl, converged, final_status,
                not_converged_why):
    res = {
        "mode": "run",
        "product": pick_card.get("product") or (mat.get("fields") or {}).get("商品名") or "-",
        "platform": platform,
        "platform_name": PLATFORM_LABEL.get(platform, platform),
        "model": a.model,
        "crew_version": CREW_VERSION, "prompt_version": PROMPT_VERSION,
        "gate_version": GATE_VERSION,
        "source": {"path": path, "chars": len(mat.get("raw") or ""),
                   "material_sha": json_sha(mat.get("raw") or "")},
        "rounds_planned": rounds_planned, "rounds_used": rounds_used,
        "converged": bool(converged), "final_status": final_status,
        "not_converged_why": not_converged_why,
        "interaction_log": interaction,
        "isolation": isolation,
        "pick": pick_card, "copy": copy_obj, "visual": visual_obj, "ruling": ruling,
        "rulings": rulings_log,
        "checks": {"pick": pick_chk, "visual": (checks or {}).get("visual") or {}},
        "gates": gates,
        "usage": usage_dict(tracker, usages),
    }
    outdir = getattr(a, "outdir", None)
    if outdir:
        write_json(str(Path(outdir) / "result.json"), res)
        write_text(str(Path(outdir) / "REPORT.md"), render_report_md(res))
        res["outdir"] = str(outdir)
        sys.stderr.write("\n产物已写入 {}（result.json / REPORT.md / state.json）\n".format(outdir))
    return res


# ---------------------------------------------------------------------------
# 子命令：log（把 run 落下的裁决记录读出来，零成本）
# ---------------------------------------------------------------------------

def run_log(a):
    target = a.result
    if not target:
        if not a.outdir:
            raise UsageError("给一个 `--result 结果.json`，或给 `--outdir 目录`（读里面的 result.json）")
        target = str(Path(a.outdir) / "result.json")
    obj = read_json(target, "run 的结果文件")
    if _json_out(obj, a, indent=2):
        return EXIT_OK
    print(render_report_md(obj))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：cost（报价，零成本）
# ---------------------------------------------------------------------------

def run_cost(a):
    check_cost_opts(a)
    if getattr(a, "text", None):
        raw = a.text
        path = None
    elif getattr(a, "file", None):
        raw = read_text(a.file, "商品资料")
        path = a.file
    else:
        raise UsageError("给 `--file 商品资料.md` 或 `--text \"...\"` 才能估算")
    mat = parse_material(raw)
    rounds = max(1, int(getattr(a, "rounds", 2) or 2))
    calls = estimate_calls(mat, rounds)
    tin = sum(int(c["tokens_in"]) for c in calls)
    tout = sum(int(c["tokens_out"]) for c in calls)
    rec = compute_cost(tin, tout, a.price_in, a.price_out)
    rec.update({
        "mode": "cost", "rounds": rounds, "path": path,
        "source_chars": len(raw or ""), "calls": calls,
        "total_calls": sum(int(c["calls"]) for c in calls),
        "crew_version": CREW_VERSION,
        "calibration": {"chars_per_token_in": CHARS_PER_TOKEN_IN,
                        "tokens_per_char_out": TOKENS_PER_CHAR_OUT},
        "call_note": ("调用次数按**轮次上限**估：真实跑起来可能第 1 轮就放行"
                      "（省掉后面所有轮），也可能轮次用尽仍在否决。"),
    })
    rec["notes"].append(rec.pop("call_note"))
    if _json_out(rec, a, indent=2):
        return EXIT_OK
    print(render_cost_md(rec))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：models（免费）
# ---------------------------------------------------------------------------

def run_models(a):
    url = MODELS_URL + ("" if not a.type or a.type == "all" else "?type=" + str(a.type))
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + a7w.load_key(a.key), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except Exception as exc:                       # noqa: BLE001 —— 拉清单失败就是拉清单失败
        return _fail(EXIT_CALL, "call", "拉取模型清单失败（网络 / 鉴权 / Key）：{}".format(exc))
    lst = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(lst, dict):
        lst = lst.get("data") or lst.get("list") or []
    lst = [m for m in (lst or []) if isinstance(m, dict)]
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
    print("      另外：文本模型**没有单价字段**，所以本包只报 token、不报金额。")
    print("用法：run.py run --file 商品资料.md --model <model_code>")
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

_KIND_BY_EXIT = {1: "internal", 2: "usage", 3: "gate", 4: "call", 5: "budget", 130: "interrupt"}


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


def _emit(a, result, md_text, ok=True):
    """统一出口：`--json` 时补 ok 写**真 stdout**（同时落 `--out`），否则原样打人读文本。"""
    if getattr(a, "json", False):
        body = _json_text(result, indent=2, ok=ok)
        if getattr(a, "out", None):
            ensure_outside_pkg(a.out, "--out")
            write_text(a.out, body + "\n")
            sys.stderr.write("已写入 {}\n".format(a.out))
        _json_write(body)
        return
    if getattr(a, "out", None):
        ensure_outside_pkg(a.out, "--out")
        write_text(a.out, md_text + "\n" if not md_text.endswith("\n") else md_text)
        sys.stderr.write("已写入 {}\n".format(a.out))
    print(md_text if md_text.endswith("\n") else md_text + "\n")


def _gate_stderr(label, gates):
    """把硬闸门命中汇总到 stderr（标红 + 逐条原因）。返回是否命中。"""
    hits = gate_hits(gates)
    if not hits:
        return False
    sys.stderr.write("\n{}\n".format(_red(
        "{}：{} 项硬闸门命中".format(label, len(hits)))))
    for k, v in hits:
        name = dict((x[0], x[1]) for x in GATE_CATALOG).get(k, k)
        if k == "compliance":
            sys.stderr.write("   [{}] 产出侧命中 ".format(name) + "、".join(
                "「{}」({}，{})".format(h.get("word"), h.get("level"),
                                       h.get("in_field") or h.get("in") or "-")
                for h in (v.get("hits") or [])[:8]) + "\n")
        elif k == "placeholder":
            sys.stderr.write("   [{}] ".format(name) + "；".join(
                "{}（{}）".format(h.get("why"), h.get("in") or "-")
                for h in (v.get("hits") or [])[:5]) + "\n")
        elif k == "prompt_echo":
            sys.stderr.write("   [{}] ".format(name) + "；".join(
                h.get("why") or "" for h in (v.get("hits") or [])[:3]) + "\n")
        elif k == "anchor":
            sys.stderr.write("   [{}] {}\n".format(
                name, v.get("why") or "未锚定率过高（已锚定 {} / {} 条）".format(
                    v.get("verified"), v.get("total"))))
        elif k == "slot_complete":
            for i in (v.get("issues") or []):
                sys.stderr.write("   [{}] {}\n".format(name, i.get("why")))
        elif k == "ruling":
            for i in (v.get("issues") or []):
                sys.stderr.write("   [{}] {}\n".format(name, i.get("why")))
        else:
            sys.stderr.write("   [{}] {}\n".format(name, v.get("why") or "命中"))
    ex = (gates.get("compliance") or {}).get("exempted") or []
    if ex:
        sys.stderr.write("   提示：本地放过 {} 处疑似绝对化用语（判为普通中文用法，"
                         "**不静默丢弃**，明细在结果的 gates.compliance.exempted）：{}\n".format(
                             len(ex), "、".join("「{}」".format(e.get("word")) for e in ex[:8])))
    mh = (gates.get("compliance") or {}).get("material_hits") or []
    if mh:
        sys.stderr.write("   提示：**你给的商品资料**里有 {} 处违禁/高风险表述（{}）——"
                         "只报不拦，因为要发布的是产出物；但资料是事实来源，"
                         "这些说法必须改掉或补依据，否则合规角色会据此否决。\n".format(
                             len(mh), "、".join("「{}」".format(h.get("word"))
                                              for h in mh[:8])))
    q = (gates.get("compliance") or {}).get("quoted_from_material") or []
    m = (gates.get("compliance") or {}).get("mentioned_as_warning") or []
    if q or m:
        sys.stderr.write("   提示：产出侧另有 {} 处判为**引用材料**、{} 处判为**提到/在禁止**"
                         "（都在结果的 gates 里留了原因，未静默丢弃）。\n".format(len(q), len(m)))
    return True


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py run --file x --json` 会报 `unrecognized arguments` 并退出 2。
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
                   help="最大输出 token，默认 8192")
    p.add_argument("--key", help="临时指定 A7W API Key")
    if out:
        p.add_argument("--out", help="把结果写到这个文件（**必须在包外**）")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")
    p.add_argument("--hide-inputs", action="store_true", dest="hide_inputs",
                   help="不打印「各角色实际收到了什么」的隔离证据（默认打印）")


def _add_cost_opts(p):
    p.add_argument("--price-in", type=float, dest="price_in",
                   help="输入单价，单位「点/百万 token」。不给我就不给金额（不编价）")
    p.add_argument("--price-out", type=float, dest="price_out",
                   help="输出单价，单位「点/百万 token」")
    p.add_argument("--budget", type=float,
                   help="预算上限（点）。超了就地中止且**不发起那次调用**，退出码 5；"
                        "用 --budget 最好同时给单价（网关不公布单价，没单价核不了预算）")


def _add_material_opts(p, required=True):
    p.add_argument("--file", required=required, help="商品资料（.md / .txt，UTF-8，`键：值` 一行一条）")
    p.add_argument("--text", help="或直接给资料文本（与 --file 二选一）")
    p.add_argument("--platform", default=DEFAULT_PLATFORM, choices=list(PLATFORM_CHOICES),
                   help="目标平台，默认 {}（影响主图版式与合规口径）".format(DEFAULT_PLATFORM))


def _add_state_opts(p):
    p.add_argument("--outdir", help="产物目录（**必须在包外**）：state.json 等")
    p.add_argument("--force", action="store_true", help="忽略断点，从头重跑（会重新花钱）")


def _parser(**kw):
    """统一构造 ArgumentParser，**关掉长选项前缀缩写**（`allow_abbrev=False`）。

    事故复盘（同族自测时踩到的真实坑）：`all` 上同时有 `--outdir`，用户写
    `--out report.json` 想输出结果文件，argparse 默认允许**前缀缩写**，于是 `--out`
    被当成 `--outdir` 的缩写匹配上了 —— 结果产出目录变成了一个叫 `report.json` 的目录，
    而且**不报任何错**。这类"参数被静默吃成另一个参数"的错误最难查。
    关掉缩写后 `--out` 直接报 unrecognized arguments（退出码 2），一眼就能看出问题。
    """
    kw.setdefault("allow_abbrev", False)
    return argparse.ArgumentParser(**kw)


def _main(argv_eff):
    ap = _parser(
        prog="run.py",
        description="三剪客 · 电商上新小组（L3 多智能体协作：选品 / 文案 / 视觉 / 合规）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("roles", help="列出四个角色的职权、产出与否决权（零成本、不联网）")
    _add_json(p)
    p.set_defaults(func=run_roles)

    p = sub.add_parser("pick", help="选品：出选品卡；**自己可以否决这个品**")
    _add_material_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_state_opts(p)
    p.set_defaults(func=run_pick)

    p = sub.add_parser("copy", help="文案：主图五个位 + 详情页")
    _add_material_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_state_opts(p)
    p.add_argument("--pick", help="选品卡的 JSON 产物（`pick --json --out`）；只取它的结构化字段")
    p.add_argument("--rejects", help="视觉打回意见的 JSON（`visual --json --out`），用于重写")
    p.set_defaults(func=run_copy)

    p = sub.add_parser("visual", help="视觉：五位方案；**可以说某一位做不出来**")
    _add_material_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_state_opts(p)
    p.add_argument("--copy", help="文案的 JSON 产物（`copy --json --out`）")
    p.add_argument("--rejects", help="上一轮的打回意见 JSON")
    p.set_defaults(func=run_visual)

    p = sub.add_parser("compliance", help="合规：裁决放行 / 打回 / **一票否决**")
    _add_material_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_state_opts(p)
    p.add_argument("--bundle", help="整套物料的 JSON（`run` 结果的 `pick`/`copy`/`visual` 段）")
    p.add_argument("--prev", help="上一轮裁决的 JSON（复裁用）")
    p.set_defaults(func=run_compliance)

    p = sub.add_parser("run", help="完整协作：选品 → 文案 ⇄ 视觉 → 合规（一条命令出整套物料）")
    _add_material_opts(p)
    _add_model_opts(p, out=False)
    _add_cost_opts(p)
    p.add_argument("--rounds", type=int, default=2,
                   help="轮次上限（一轮 = 文案→视觉→合规），默认 2；"
                        "轮次用尽仍在否决会**如实报未收敛**（退出码 3）")
    p.add_argument("--outdir", default=str(Path(os.environ.get("TEMP") or ".") / "ecom-crew-out"),
                   help="产物目录（**必须在包外**）：result.json / REPORT.md / state.json")
    p.add_argument("--force", action="store_true", help="忽略断点，从头重跑（会重新花钱）")
    p.set_defaults(func=run_run)

    p = sub.add_parser("log", help="把 run 落下的裁决记录读出来（零成本）")
    p.add_argument("--result", help="run 的 result.json")
    p.add_argument("--outdir", help="或给 run 的 --outdir（读里面的 result.json）")
    _add_json(p)
    p.add_argument("--out", help="把记录写到这个文件")
    p.set_defaults(func=run_log)

    p = sub.add_parser("cost", help="报价：这次协作大概花多少 token（金额要你填单价）")
    p.add_argument("--file", help="按这份商品资料估")
    p.add_argument("--text", help="或直接给资料文本")
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
                 ("no_json_mode", False), ("hide_inputs", False), ("key", None),
                 ("budget", None), ("price_in", None), ("price_out", None),
                 ("force", False), ("platform", DEFAULT_PLATFORM), ("rounds", 2),
                 ("outdir", None), ("model", DEFAULT_MODEL), ("temperature", 0.7),
                 ("max_tokens", 8192), ("file", None), ("text", None),
                 ("pick", None), ("copy", None), ("bundle", None), ("prev", None),
                 ("rejects", None), ("result", None), ("type", "text")):
        if not hasattr(a, k):
            setattr(a, k, v)
    kind, msg, detail = None, None, None
    rc = EXIT_OK
    try:
        rc = a.func(a)
    except CrewError as exc:
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


