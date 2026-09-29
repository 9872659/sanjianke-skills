#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 调研取证小组 —— 真正干活的脚本（零第三方依赖）。

**产品线 L3（多智能体协作型）· 取证式（evidentiary）**：不是"评一篇稿写得好不好"
（那是 L2 的内容质量闭环），也不是"审一份方案该不该过"（那是对抗评审），
而是**对一组事实主张做取证与对抗验证**：

    主张方  提出结论与支撑主张，逐条给证据引用
    质疑方  逐条挑战（**看不到主张方的推理过程，只看得到结论与证据编号**）
    取证方  对每条争议主张给出证据强度评级（强 / 中 / 弱 / 无据）
    裁决方  出结论：哪些主张可采信、哪些必须撤回、**哪些必须降级表述**

八个子命令：

    roles     列出四个角色的职权、产出物与否决权（纯本地，零成本）
    claims    主张方：主张清单 + 证据引用（一次调用）
    challenge 质疑方：逐条挑战书 + **挑战类型**（一次调用，信息隔离）
    evidence  取证方：证据强度评级（一次调用）
    verdict   裁决方：可采信边界 + **降级表述建议**（一次调用）
    run       一条命令跑完（claims → challenge → evidence → verdict），带断点续跑
    log       读回全过程记录：哪些主张被挑战掉、哪些被判必须降级
    cost      报价：这次取证大概花多少 token（零成本，金额要你自己填单价）
    models    列出 api.a7w.cn 当前在架的文本模型（零成本）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

⚠️ **本包不联网检索**。它没有检索端点，也不会去查证外部事实；
它做的是**本地推理与评级**：把"这句话凭什么被信"这件事拆开、摊平、判定强弱。
证据是否真的存在于现实世界，仍然要人来核。

用法
    python3 run.py roles
    python3 run.py claims    --file 材料.md --outdir D:/crew --json
    python3 run.py challenge --file 材料.md --claims D:/crew/claims.json --json
    python3 run.py evidence  --file 材料.md --claims D:/crew/claims.json \
                             --challenge D:/crew/challenge.json --json
    python3 run.py verdict   --file 材料.md --claims D:/crew/claims.json \
                             --challenge D:/crew/challenge.json \
                             --evidence D:/crew/evidence.json --json
    python3 run.py run       --file 材料.md --outdir D:/crew --budget 50 \
                             --price-in 1000 --price-out 2000 --json
    python3 run.py log       --outdir D:/crew
    python3 run.py cost      --file 材料.md
    python3 run.py claims    --file 材料.md --dry-run      # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py claims --file 材料.md --key sk-xxxx
    export A7W_API_KEY=sk-xxxx     # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍（这一节是本包与同族其它包的**分界线**）
    · 与 L2 内容质量闭环的差别：那边评的是**文本质量**（信息密度/结构/可读性…五个刻度
      在同一把尺子上，越迭代越收敛）；本包评的是**事实主张能不能站得住**，产物是
      证据强度评级 + 可采信边界 + 降级表述，**不是分数**。
    · 与对抗评审（review-board）的差别：那边四个席位是四个互相冲突的价值立场
      （用户/竞品/合规/业务），审的是"该不该过"；本包四个角色是**同一件事的四个工序**
      （提主张 → 打漏洞 → 评强度 → 定边界），审的是"这句话凭什么被信"。
      两包的闸门也不同：那边核心闸门是「立场失效」，本包核心闸门是「质疑无效」。
    · **信息隔离是机制，不是修辞**：challenge 阶段的提示词里**只有主张方的结论
      与主张文本 + 证据编号/来源名**，没有主张方的推理过程（`reasoning`），
      也没有证据的具体内容与强度。见 challenge 产物的 `isolation` 证据。
    · **不采信模型自报的挑战是否成立**：本地检查每条 challenge 的 target 主张是否
      真的被判为 `challenged`；一条都没成立就判「质疑无效」（闸门五）。
      **不许把「全部放行」当成"证据充分"**。
    · **降级表述是硬交付物**：判「不能采信」的主张必须给替代表述（闸门六）。
      只删不给替代的裁决会把用户的稿子掏空——那是毁稿，不是裁决。
    · 「引用原文」不靠提示词求模型配合，而是**本地校验引文**（见 AnchorTarget）：
      主张、挑战、裁决依据、降级表述里出现的数字都必须能在材料里找到，
      编造的引文与凭空造的数字会被剔出并计入未锚定率。
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
# ⚠️ 不许往包里写 .pyc。同族的包跑一次就会在 scripts/__pycache__/ 留下几个 .pyc，
# 而 Skill 包的上传白名单里没有 .pyc（`.md .py .txt .json .sh .js .yaml .yml .csv`）。
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
EXIT_OK = 0            # 全流程跑完，且没有任何硬闸门命中
EXIT_USAGE = 2         # 参数/配置错（文件不存在、角色名错、--outdir 在包内、--budget 没配单价）
EXIT_GATE = 3          # 硬闸门命中（合规/占位符/照抄示例/锚点/质疑无效/降级缺失/评级不一致）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。
# 事故复盘（同族踩过）：改了角色定义或闸门口径却不改 key，续跑会把上一版口径的旧产物
# 当成"已完成"直接复用，产出对不上文档。加版本号是最省事的根治办法。
RUBRIC_VERSION = "crew-rubric-1.0.0"
PROMPT_VERSION = "crew-prompt-1.0.0"
ROLES_VERSION = "crew-roles-1.0.0"


# ---------------------------------------------------------------------------
# 四个角色：提主张 → 打漏洞 → 评强度 → 定边界
#
# 与"四个立场"（review-board）的区别：那四席是四个互相冲突的目标函数，
# 审的是"该不该过"；本包这四个是**同一件事的四个工序**，审的是
# "这句话凭什么被信、能被信到什么程度、不能采信的话该怎么说"。
# 所以本包的分歧不靠角色互相否掉对方，而靠**质疑方必须真的挑战掉一些主张**
# （闸门五），以及**裁决必须给出可用的替代表述**（闸门六）。
# ---------------------------------------------------------------------------

ROLES = [
    {
        "id": "claimant",
        "name": "主张方",
        "icon": "主张",
        "goal": "把结论说清楚，并为每一条支撑主张**指名**它凭什么",
        "bias": "把结论写大、把依据写虚、把「我们认为」当成「数据显示」",
        "question": "你这份材料到底想让读者相信什么？这个结论是靠哪几条主张撑起来的？"
                    "每一条主张的依据叫什么、编号是什么？",
        "power": "无（只能提主张，不能给自己的主张评级）",
        "deliverable": "主张清单 + 逐条证据引用（每条主张至少一条证据）",
        "focus": [
            "结论一句话说清：读者被要求相信的到底是什么",
            "支撑主张逐条拆开，一条主张只讲一件事（可被单独挑战）",
            "每条主张必须标出**用了哪几条证据**（引用证据编号，不许含糊说「有数据支持」）",
            "证据要落成编号条目：编号、名称、来源类型、时间——不许只写「业内数据」",
        ],
    },
    {
        "id": "challenger",
        "name": "质疑方",
        "icon": "质疑",
        "goal": "在每条主张上找一个**能站住的**漏洞，并说清是哪一类漏洞",
        "bias": "放过「看起来像常识」的主张、把措辞不合口味当成漏洞、挑不动就全放行",
        "question": "这条主张，如果明天要拿它去对外说，最可能在哪被问倒？"
                    "是样本不够、因果搞反、口径不对、时效过期、来源不硬、范围越界，还是利益相关？",
        "power": "**能要求撤回**（challenge 里 severity=致命 的挑战，裁决方必须正面处置）",
        "deliverable": "逐条挑战书（**必须指出挑战类型**）+ 明确列出「我没能挑战动」的主张",
        "focus": [
            "样本：个案当规律、样本量没说、样本选择有偏",
            "因果：只有相关就断言因果、把先后当因果、把同时发生当导致",
            "口径：数字怎么算的没说、分母是什么没说、换口径结论会不会翻",
            "时效：数据是哪一年的、市场条件变了没有、有没有过期",
            "来源：单一来源、二手转引、来源本身有立场、无法核实",
            "范围：局部结论推全体、单一渠道推全平台、单一品类推全行业",
            "利益：谁说这话谁受益、样本是不是自己筛的、有没有自证",
        ],
    },
    {
        "id": "evidence",
        "name": "取证方",
        "icon": "取证",
        "goal": "给每条（被挑战的）主张一个**能用一句话解释**的强度评级",
        "bias": "把「说得很确定」当成「证据很强」、同类证据在不同主张上给不同评级",
        "question": "这条主张手里的那点东西，能撑到什么程度？强、中、弱，还是根本无据？",
        "power": "无（只评级，不裁决；评级要能解释「为什么不是更高一档」）",
        "deliverable": "逐条证据强度评级（强 / 中 / 弱 / 无据）+ 决定性缺口",
        "focus": [
            "强：来源可核实、样本与口径交代清楚、结论不外推、时效在有效期内",
            "中：方向可信但样本或口径有缺口，只能作**方向性**表述",
            "弱：单一来源 / 单一个案 / 口径不明 / 时效存疑，只能作**假设**表述",
            "无据：找不到实质依据，或依据只覆盖了很小一部分却说成普遍结论",
            "**同一类证据在不同主张上必须用同一把尺子**——本地闸门七会核对",
            "每条评级都要写「为什么不是更高一档」（决定性缺口），否则无法复核",
        ],
    },
    {
        "id": "arbiter",
        "name": "裁决方",
        "icon": "裁决",
        "goal": "定可采信边界：哪些能用、哪些只能降级说、哪些必须撤回",
        "bias": "把「撤回」当成唯一手段（只删不给替代）、替主张方补它没给的依据",
        "question": "这份材料最后发出去，哪几句能原样保留？哪几句必须换个说法？哪几句必须删？",
        "power": "**终裁**（可采信 / 降级表述 / 撤回，且必须给替代表述）",
        "deliverable": "可采信边界 + **降级表述建议**（判「不能采信」的必须给出可用的替代说法）",
        "focus": [
            "裁定三档：可采信（原样可用）/ 降级表述（换个更保守的说法）/ 撤回（不能用）",
            "**判「不能采信」的，必须给出替代表述**——只删不给替代会把稿子掏空",
            "替代表述必须**真的更保守**：去掉绝对化、加上限定范围、交代口径、改方向性表述",
            "替代表述**不许引入原文里没有的新数字**（本地闸门会核对）",
            "每条裁定必须说清依据哪条挑战 / 哪条评级，不许凭印象裁",
        ],
    },
]

ROLE_IDS = [r["id"] for r in ROLES]
ROLE_BY_ID = {r["id"]: r for r in ROLES}
ROLE_NAME = {r["id"]: r["name"] for r in ROLES}


def as_role_id(value):
    """把模型给的角色标识归一到角色 id。

    真机实测踩到的（同族）：模型在引子里填的是**显示名**（「质疑方」）而不是 id
    （`challenger`），于是"引用了不存在的角色"这条闸门误报。
    所以这里两种写法都认：id 原样，显示名映射成 id，其它一律 None（那才是真的不认识）。
    """
    if not isinstance(value, str):
        return None
    v = value.strip()
    if v in ROLE_BY_ID:
        return v
    for rid, name in ROLE_NAME.items():
        if v == name or v == "{}（{}）".format(name, rid) or v == "{} {}".format(name, rid):
            return rid
    for rid in ROLE_IDS:
        if v.startswith(rid):
            return rid
    return None


# 主张类型：决定了"这条主张最怕哪一类质疑"
CLAIM_TYPES = ("事实", "因果", "量化", "预测", "比较", "因果+量化", "规范")
CLAIM_TYPE_ANY = CLAIM_TYPES + ("未标注",)

# 质疑类型（**本包的核心分类**，质疑方必须逐条指出）
CHALLENGE_TYPES = ("样本", "因果", "口径", "时效", "来源", "范围", "利益")
CHALLENGE_TYPE_ANY = CHALLENGE_TYPES + ("其他",)

# 证据强度四档（取证方唯一可用的评级）
STRENGTH_LEVELS = ("强", "中", "弱", "无据")
STRENGTH_VALUE = {"强": 3, "中": 2, "弱": 1, "无据": 0}

# 系统提示里给的"典型证据形态"。**这是强制口径校准**，不是可选提示：
# 不钉死形态，模型会在同一条证据上给"强"、在另一条上给"弱"，
# 闸门七（评级口径一致性）就会一直响，而用户不知道是该信闸门还是信产出。
SOURCE_SHAPES = (
    "单个案例 / 一次经历",
    "单一来源（一个客户、一家供应商、一个渠道）",
    "小样本自采（几十份以内、自己筛的样本）",
    "二手转引（别人说的、没有原始出处）",
    "行业公开报告（可核实到具体报告名与年份）",
    "可核实的内部台账 / 平台后台数据（口径可交代）",
    "多个独立来源互相印证",
)

# 证据强度归一化的兜底映射（模型给了细粒度置信度但没给四档时用）
CONFIDENCE_BUCKETS = (
    (0.75, "强"),
    (0.50, "中"),
    (0.20, "弱"),
)


# ---------------------------------------------------------------------------
# 闸门一：合规（广告法违禁词）
#
# 每项：正则 → 风险等级 → 人话解释。这是一道**粗筛**，宁可多报也别漏报，
# 最终判断仍要人工复核，且不等于平台官方审核结论。
# ⚠️ 本包的材料往往**本身就在讨论**这些词（"竞品说全网最低价"），
# 所以产出侧口径与材料侧**严格分开**，见 compliance_scan_output。
# ---------------------------------------------------------------------------

# 「第一」的可枚举上下文豁免（照抄同族）：长文里「第一年」「第一步」是**序数**，
# 不是最高级宣称。一刀切拦下的后果很实在：用户会把整个合规闸门关掉，那比漏报更糟。
FIRST_ORDINAL_AFTER = (
    "次|年|天|步|个|条|款|批|周|月|季|轮|种|点|部|遍|章|节|课|集|届|期|流|层|类"
    "|句|段|行|件|桶|手|版|稿|封|笔|单|场|局|盘|组|队|线|环|圈|代|世|阶|时|印|梯"
    # 本包新增（真机实测踩到）：调研材料里「第一反应」「第一印象」「第一手」
    # 都是惯用语，不是排他性宣称。
    "|反应|印象|时间|感觉|直觉|现场|眼|手|线|版|"
    # 本包新增：调研文书的正常写法。「第一条主张」「第一个缺口」是在给主张编号。
    "|主张|结论|缺口|问题|依据|证据|层级|档"
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
    # 本包新增的一档：**调研测算用语**。真机实测踩到的误报——
    # 取证方写「可承受的最高获客成本」「样本量的上限」「最强的反向证据」
    # 被当成最高级商品宣称拦下。这类词是内部测算口径，不是对外广告语；
    # 一刀切拦下会让用户关掉整个合规闸门。仍然遵守同一条边界：**句首不豁免**。
    "获客", "出价", "预算", "上限", "限价", "限额", "成本", "收益", "性价比", "增速",
    # 本包新增：调研文书里的程度用法——「最强的证据也就到这一步」「最大的缺口」
    # 「最弱的一环」「最坏的情况」。句子中间接程度/名词，不是排他性宣称。
    "强", "弱", "坏", "好", "新", "旧", "近", "远", "快", "慢", "值得", "能", "会",
    "缺", "问题", "风险", "嫌疑", "大", "小",
)
SUPERLATIVE_OK_RE = re.compile(r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")


# 第二类豁免：**可度量的断言式「最X」**（本包新增，真机实测踩到的误报）。
# 事故复盘：材料里写「华南区订单量最高」「样本量的上限」「最大的缺口」，
# 全部被材料侧合规闸门按「最高级用语」拦下——而这三句都不是商品宣称，
# 是**可度量指标的比较陈述**（订单量最高 = 该区域订单量在三者中最大）。
#
# 判据是**可判定的**，不是感觉：
#   · 「最」前面紧邻一个**度量名词**（量/额/数/率/比/分/度/值/位/阶/档/层/级/占）
#   · 且「最X」后面紧跟标点或行尾（是断言，不是修饰名词的定语）
# 两条都满足才豁免，并且**材料侧与产出侧同口径**：
#   · 「华南区订单量最高」→ 豁免（可度量断言）
#   · 「最好/最优惠/最便宜/最大优惠」→ 不豁免（在给商品/服务下定语，照拦）
#   · 「唯一/第一/国家级/100%」→ 与本豁免无关，照拦
MEASURED_NOUNS = ("量", "额", "数", "率", "比", "分", "度", "值", "位", "阶", "档",
                  "层", "级", "占", "水平", "规模", "成本", "预算", "样本", "口径",
                  "缺口", "风险", "强度", "权重", "优先级", "增速", "涨幅", "跌幅")
MEASURED_NOUN_BEFORE_RE = re.compile("(" + "|".join(MEASURED_NOUNS) + ")$")

# 断言式收尾：**要么直接接标点/行尾，要么接一个「可枚举的继词短语」再接标点**。
# 为什么不能写成「后面只要是中文就算」：那样「合约量最高的用户都跑了」也会被豁免，
# 而它可能真的在做商品宣称。收尾必须可枚举，否则这道闸门就没牙了。
TAIL_BOUNDARY = " \t，。！？!?；;：:、,.)）]】\n"
TAIL_DETERMINERS = ("这个", "那个", "这一", "那一", "这些", "那些", "其中")
TAIL_CONTINUATIONS = ("渠道", "城市", "区域", "品类", "产品", "门店", "品牌", "平台",
                      "环节", "指标", "维度", "来源", "证据", "主张", "样本", "口径",
                      "客群", "时段", "月份", "季度", "团队", "方案", "做法", "路径",
                      "方式", "玩法", "场景", "单品", "单位", "分歧", "争点")
# 「最X」在给下面这些名词下定语时，是在给商品/服务做宣称，不豁免。
PROMO_NOUN_AFTER_RE = re.compile(
    r"^\s*的?\s*(品质|质量|标准|水平|档次|配置|规格|服务|体验|性价比|享受|待遇|"
    r"级别|等级|优惠|价格|折扣|性能|效果)")


def _is_assertion_tail(tail):
    """「最X」后面是不是一个**断言式的收尾**（而不是一个名词短语的开头）。

    三种收尾都算：
      1. 直接就是标点 / 行尾
      2. `的是` / `的` / `了` 之后接标点或接可枚举的继词
      3. 直接接可枚举的指示词 + 继词（`这个渠道` / `其中三城`）
    其它情况一律**不算**（宁可漏豁免也不放过商品宣称）。
    """
    t = (tail or "").lstrip()
    if not t:
        return True
    if t[0] in TAIL_BOUNDARY:
        return True
    for p in ("的是", "的也是", "的为", "的", "了"):
        if t.startswith(p):
            return _is_assertion_tail(t[len(p):])
    for p in TAIL_DETERMINERS + TAIL_CONTINUATIONS:
        if t.startswith(p):
            return _is_assertion_tail(t[len(p):])
    return False


def _superlative_is_measured_claim(text, m):
    """「度量名词 + 最X + 标点/句尾」→ 可度量的断言式用法，豁免。

    这条**不看句首**：句首的「订单量最高，说明…」同样是可度量断言，
    与该区域在句中的位置无关。这是与第一类豁免（`区别/不同` 一类）的差别，
    所以两类分开写、分开记原因。
    """
    if not m.group(0).startswith("最"):
        return False
    tail = (text or "")[m.end():]
    if PROMO_NOUN_AFTER_RE.match(tail):
        return False                       # 在给商品名词下定语 → 商品宣称，照拦
    before = (text or "")[:m.start()]
    if not MEASURED_NOUN_BEFORE_RE.search(before):
        return False
    return _is_assertion_tail(tail)


def _superlative_is_normal_usage(text, m):
    """「最X」的豁免判定。返回 (是否豁免, 原因)；不豁免时原因为 None。

    两类豁免（**分开记原因，便于人工复核**）：
      1. `measured_claim`：度量名词 + 最X + 标点（可度量的断言，不看句首）
      2. `degree_usage`  ：最X 后接程度/比较词，**且不在句首**
    """
    if not m.group(0).startswith("最"):
        return False, None
    if _superlative_is_measured_claim(text, m):
        return True, "measured_claim"
    before = (text or "")[:m.start()]
    if not before.strip() or _SENT_END_RE.search(before):
        return False, None                 # 句首 → 第一类豁免不适用
    if SUPERLATIVE_OK_RE.match((text or "")[m.end():]):
        return True, "degree_usage"
    return False, None


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
            exempt_ok, exempt_why = _superlative_is_normal_usage(t, m)
            if exempt_ok:
                exempted.append({"word": m.group(0), "level": lvl,
                                 "exempt_rule": exempt_why,
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
# 取证方与裁决方会大量写「最强的证据也就到这一步」「最大的缺口是没有口径」，
# 这是普通中文程度用法与内部测算口径，不是商品宣称；而这类误报会让人把整个合规闸门关掉。
# 材料侧**照查**（那里才是会被公开发布的东西）。
OUTPUT_EXCLUDED_WHY = ("广告法第九条禁止「最高级」用语",)

# 「提到」而不是「主张」的上下文标记。
# 调研材料常常**本身就在讨论这些词**（"竞品宣称全网最低价，我方不得跟"），
# 产出侧是在引用/在指出风险，不是自己在做违规宣称。
META_CONTEXT_RE = re.compile(
    "禁止|严禁|不得|不许|不能|不可|避免|杜绝|防范|防止|违规|风险|涉嫌|属于|构成|"
    "无出处|无法举证|不可举证|举证|撤回|删除|删掉|去掉|不实|虚假|夸大|诱导|"
    "不构成|不算|不是|未|没|缺|整改|改为|改成|替换|风险点|红线|合规问题|"
    # 本包新增：裁决/质疑文书的标记词——「这条主张要撤回」「建议换成」
    # 「降级表述」「不得对外宣称」「只能作方向性表述」
    "主张|质疑|挑战|降级|替代表述|口径|样本|时效|来源不明|外推|越界")
_SENT_BOUND = re.compile(r"[。！？!?；;\n]")


def _ctx_window(text, pos, width=24):
    """命中位置前后各 width 个字符（**不跨句末标点**）。

    为什么用「窗口」而不是"整句"：中文调研句子里逗号、顿号极多，
    按标点切成小句会把「建议删除"全网最低价"这类表述」切碎成「全网最低价」，
    标记词正好被切掉。也不跨句末标点：跨句取词会把上一句的"禁止"借给下一句的违规宣称。
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
    """产出侧合规（**与材料侧口径不同，这是本包最容易被误报的一道**）。

    本包的材料本身就是"对一组主张做取证"的场所，所以产出里出现
    「全网最低价」「100%」这类字样的**概率远高于**其它包——但那些字样
    出现在质疑书/裁决里时，语义通常是**在引用、在挑战、在要求撤回**。

    所以产出侧收紧成三条**能解释的**规则：
      1. 只查**高风险**（广告法明令禁止的那一类）；中低风险项与 `最X`
         在取证文书里多半是描述性用语，列进 `contextual_only` 提示人工看，不拦。
      2. 材料里已经出现过的词判为**引用**，不计命中。
      3. 命中所在的**小句**里有禁止/举证/撤回类标记词的判为**提到**，不计命中；
         小句里没有任何标记词的才是**自己在主张** → 拦
         （「本方案必须保证过审」照样拦得住）。
    被排除的条目**全部保留在案**（带 `not_counted_reason`），不静默丢弃。
    """
    hi_all, exempted = compliance_scan(prose, levels=("高",))
    hi, soft = [], []
    for h in hi_all:
        if h["why"] in OUTPUT_EXCLUDED_WHY:
            h = dict(h)
            h["not_counted_reason"] = ("`最X` 在取证文书里多为普通中文程度用法或内部测算口径"
                                       "（如「最大的缺口」「最强的证据」），"
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
                "命中前后 24 字里有「{}」这类标记词——判为**提到/在质疑/在要求撤回**，"
                "不是本包自己在做违规宣称".format(m.group(0)))
            h["context_window"] = ctx[:60]
            mentioned.append(h)
        else:
            fresh.append(h)
    contextual, _ = compliance_scan(prose, levels=("中", "低"))
    return fresh, quoted, mentioned, contextual + soft, exempted


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
#
# 取证文书里的模板没替换干净，是典型的"没交付"形态：
#   · `{}` / `{{主张}}`       骨架被当正文写进去了
#   · `[待填]` / `[待补充]`    模型给自己留的空档
#   · `XXX` / `xxx`            忘了替换的占位
#   · `（此处省略）`           模型懒得写，直接省略
# `[1]`（证据编号）、`[图 2]`（配图位）是**正常写法**，不按括号内容一刀切。
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
    # ⚠️ 「待补充 / 待完善 / TODO」这条**只认"整段就是这个空档"**，不看它出现在句子里。
    # 事故复盘（本包真机实测踩到的误报）：裁决方的替代表述里写了
    # 「统计窗口起止日、是否剔除取消/退款/测试单（均待补充）」——这是在**说明口径缺口**，
    # 是正常交付物；而旧口径按子串命中拦下，等于罚它"把没写完的话写清楚了"。
    # 所以拆成两条：括号包裹的占位（上一条已覆盖）+ **整段就是一个空档**。
    (re.compile(r"^\s*(?:待补充|待完善|待填|待定|后续补充|TODO|TBD|XXX)\s*[。.；;]?\s*$",
                re.M), "待补充",
     "整段就是一个占位空档（这一栏没写内容）"),
]

# ⚠️ 整段判据只对**内容字段**生效，不能拿它去扫整篇「人读散文本」——
# 否则一句话正好叫「待补充。」都会被当占位。所以另给一份 FIELD 级判据。
FIELD_EMPTY_RE = re.compile(
    r"^\s*(?:待补充|待完善|待填|待定|后续补充|TODO|TBD|XXX|无|暂无|N/?A|-|—)\s*$")


def placeholder_hits(text):
    """扫占位符残留，返回命中列表（可能为空）。只用于**段落级/整篇**文本。"""
    hits = []
    t = text or ""
    for rx, label, why in PLACEHOLDER_PATTERNS:
        m = rx.search(t)
        if m:
            hits.append({"kind": label, "word": m.group(0)[:40], "why": why})
    return hits


def field_placeholder_hits(records):
    """扫**单字段级**的占位空档（整段就是一个空档）。

    为什么要单列：`placeholder_hits` 扫的是整篇散文，一句正常的
    「…（均待补充）」会被误判；而单个字段如果只写了「待补充」，那是真的没交付。
    两者判据不同，不能混用一把尺子。
    """
    hits = []
    for where, val in records:
        if isinstance(val, str) and val.strip() and FIELD_EMPTY_RE.match(val):
            hits.append({"kind": "待补充", "field": where, "word": val.strip()[:20],
                         "why": "这一栏整段就是一个占位空档（没写内容）"})
    return hits


# ---------------------------------------------------------------------------
# 闸门三：照抄提示词示例（prompt_echo）
#
# 事故复盘（同族，两例，都是实测抓到的「模型锚定示例」）：
#   1. 提示词里写过正例 → 模型直接产出同构句
#   2. 提示词里留过一整句示例 → 那一轮**最高分**的产出一字不差就是它
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
# 跨主题 = 与任何真实调研选题都不搭（社区团购的团长数），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
PROMPT_SAMPLES = [
    "某社区团购平台的团长数量增长了百分之四十",
    "该功能在三个城市的抽样里被提到过",
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

    为什么降级表述与原主张的"是否同一句话"不能用 Jaccard：原主张与替代表述的
    篇幅天然不同（原主张一句话、替代表述可能要带口径），Jaccard 的分母是并集，
    篇幅差一大就被摊薄，"其实还是同一句话"反而测不出来。
    用 min 归一后，「短的那份有多少比例的内容出现在长的那份里」才是我们要问的问题。
    """
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(min(len(ba), len(bb)))


def prompt_echo(text, samples=None):
    """文本是否与提示词里的示例「抄得太近」。

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
# 闸门四：锚点（主张、挑战、裁决依据、降级表述都必须落到真实原文上）
#
# 一份"取证报告"最没用的形态，是四条泛泛而谈：都说"建议补充数据"、
# "注意样本代表性"，谁也不说清是哪一句。所以本包不采信模型的引文，而是**本地校验**：
#   · 主张的 quote / 挑战的 quote → 锚到**待证材料**的句子
#   · 裁决 carries 的依据 quote  → 同样锚到材料（裁决不能凭空造事实）
#   · 降级表述里出现的**数字**   → 必须能在材料里找到（不许引入新数字）
#
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
    """一个可被引用的文本（材料 / 某角色的产出），带句子切分缓存。"""

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
# 数字锚点：降级表述**不许引入原文里没有的新数字**
#
# 这是本包特有的一道校验。降级表述最容易注水的方式有两种：
#   1. 把「增长 40%」降级成「增长明显」——这是**丢失事实**，不是降级（闸门六会查）
#   2. 把「增长 40%」降级成「增长约 40%，样本 200 份」——凭空多出"200 份"
# 第 2 种必须有本地校验，否则"降级表述"会变成"重新编一遍"。
# ---------------------------------------------------------------------------

NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text):
    """抽出文本里的所有数字字面量（含小数），返回集合。"""
    return set(NUM_RE.findall(text or ""))


def numbers_not_in(needle, haystack):
    """needle 里出现了、但 haystack 里找不到的数字（**保序去重**）。"""
    hay = numbers_in(haystack)
    out, seen = [], set()
    for n in NUM_RE.findall(needle or ""):
        if n in hay or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


# ---------------------------------------------------------------------------
# 闸门五：质疑有效性（**本包的核心闸门**）
#
# 一份"取证报告"最容易变成的一场表演：质疑方客客气气写一句
# 「整体方向可信，建议补充一些数据」，然后裁决方宣布"证据充分，全部可采信"。
# 那不是取证，那是**盖章**。
#
# 这一条不靠提示词，本地算：
#   判据 A（硬）：挑战书里**一条挑战都没成立**
#                （没有任何 target 主张被判为 challenged 且挑战有实质内容）
#                → 判「质疑无效」：质疑没发生。**不许把"全部放行"当"证据充分"**。
#   判据 B（硬）：所有主张的挑战结论都是 passed（全部放行），而主张数 ≥ 2
#                → 同上判「质疑无效」（哪怕它写了几条 acknowledged 的"我挑不动"）。
#   判据 C（红）：挑战书里出现了**类型标注缺失**（challenge_type 为空或不在七类里）
#                → 标红（本包要求"必须指出挑战类型"，缺类型说明挑战是随口说的）。
#
# ⚠️ 为什么判据 B 是硬闸门而不是提示：本包的交付物就是"哪条被挑战掉了"，
# 零挑战就没有交付物；把"全部放行"当"证据充分"正是本包要防的那个假象。
# ---------------------------------------------------------------------------

CHALLENGE_VERDICT_CHALLENGED = "challenged"
CHALLENGE_VERDICT_PASSED = "passed"
CHALLENGE_VERDICT_ANY = (CHALLENGE_VERDICT_CHALLENGED, CHALLENGE_VERDICT_PASSED)

# 挑战严重度三档。「致命」的必须在裁决里被处置（撤回或降级）。
SEVERITY_LEVELS = ("致命", "重要", "次要")
SEVERITY_ANY = SEVERITY_LEVELS + ("未标注",)

# 一条"实质性"挑战的最低门槛：挑战理由 + 要求的补正 都不能是空话
MIN_CHALLENGE_TEXT = 8


def norm_challenge_type(raw):
    """归一化挑战类型。认七类；认不出来时**返回 None**（那才是真的没标类型）。"""
    if not isinstance(raw, str):
        return None
    v = raw.strip()
    if not v:
        return None
    for t in CHALLENGE_TYPES:
        if v == t or v.startswith(t):
            return t
    if "其他" in v or "其它" in v:
        return "其他"
    return None


def norm_severity(raw):
    if not isinstance(raw, str):
        return "未标注"
    v = raw.strip()
    for s in SEVERITY_LEVELS:
        if v == s or v.startswith(s):
            return s
    return "未标注"


def challenge_effective(challenge_obj, claims):
    """闸门五：质疑有效性。返回结构化结论（含每一条的数字，便于人工复核）。"""
    raw_ch = (challenge_obj or {}).get("challenges")
    rows = raw_ch if isinstance(raw_ch, list) else []
    claim_ids = {c.get("id") for c in (claims or {}).get("claims") or []}
    effective, passed, untyped, unknown_target = [], [], [], []
    for r in rows:
        if not isinstance(r, dict):
            continue
        tid = r.get("target")
        if tid not in claim_ids:
            unknown_target.append(str(tid))
        ct = norm_challenge_type(r.get("challenge_type"))
        if not ct:
            untyped.append({"target": tid, "reason": (r.get("reason") or "")[:60]})
        verdict = (r.get("verdict") or "").strip()
        if verdict not in CHALLENGE_VERDICT_ANY:
            m = re.search(r"challenged|passed|挑战成立|放行|未能挑战", verdict)
            if m:
                verdict = (CHALLENGE_VERDICT_CHALLENGED
                           if m.group(0) in ("challenged", "挑战成立")
                           else CHALLENGE_VERDICT_PASSED)
            else:
                verdict = ""
        substantive = (len(_norm_anchor(r.get("reason") or "")) >= MIN_CHALLENGE_TEXT
                       and len(_norm_anchor(r.get("required_fix") or "")) >= MIN_CHALLENGE_TEXT)
        if verdict == CHALLENGE_VERDICT_CHALLENGED and substantive:
            effective.append({"target": tid, "challenge_type": ct,
                              "severity": norm_severity(r.get("severity"))})
        elif verdict == CHALLENGE_VERDICT_PASSED:
            passed.append({"target": tid})
    problems, red = [], []
    n_claims = len(claim_ids)
    if not effective:
        problems.append(
            "挑战书里**一条挑战都没成立**（{} 条主张、{} 条挑战记录、成立 0 条）——"
            "质疑没发生。本包不把「全部放行」当成「证据充分」："
            "零挑战的取证报告与没做过取证没有区别".format(n_claims, len(rows)))
    if rows and len(passed) == len(rows) and n_claims >= 2:
        problems.append(
            "所有 {} 条主张的挑战结论都是「放行」（passed）——"
            "质疑方对每一条都放行，说明这一轮质疑是走过场".format(n_claims))
    if untyped:
        red.append("有 {} 条挑战**没有指出挑战类型**（本包要求必须落在七类里：{}）"
                   .format(len(untyped), "、".join(CHALLENGE_TYPES)))
    if unknown_target:
        red.append("有 {} 条挑战的 target 不是有效主张 id：{}"
                   .format(len(unknown_target), "、".join(unknown_target[:5])))
    return {
        "ok": not problems,
        "problems": problems,
        "red_hints": red,
        "red": bool(problems) or bool(red),
        "total_challenges": len(rows),
        "effective": effective,
        "effective_count": len(effective),
        "passed_count": len(passed),
        "untyped": untyped,
        "unknown_target": unknown_target,
        "types_used": sorted({x["challenge_type"] for x in effective if x.get("challenge_type")}),
        "thresholds": {"min_text": MIN_CHALLENGE_TEXT,
                       "types": list(CHALLENGE_TYPES)},
        "note": ("判「成立」的两条本地条件：verdict=challenged **且** reason 与 required_fix "
                 "都不是空话（归一后各 ≥ {} 字）。只看模型自报的 verdict 不算数。"
                 .format(MIN_CHALLENGE_TEXT)),
    }


# ---------------------------------------------------------------------------
# 闸门六：降级表述完整性（**本包第二个核心闸门**）
#
# 裁决书是本包的最终交付物。它最常见的废掉方式不是"判错"，而是**把稿子掏空**：
# 判了一堆"不能采信"，然后只写一个"删"字。用户拿到裁决书之后不知道那句该怎么说。
#
# 三条纪律（都在本地判，不采信模型的自我声明）：
#   1. 判「降级表述」或「撤回」的主张，`downgraded_wording` **不能为空**
#   2. 替代表述不能**与原主张相同**（同一句话不算替代），min 归一相似度 ≥ 0.90 即判同一
#   3. 替代表述**不许引入材料里没有的新数字**
# 另外，判「可采信」的主张不该带替代表述（那是自相矛盾，标红）。
# ---------------------------------------------------------------------------

DOWNGRADE_SAME_SIM = 0.90   # 替代表述与原文的 min 归一相似度 ≥ 它 → 判"没换说法"
DOWNGRADE_MIN_CHARS = 6     # 替代表述的最低长度（太短等于没给）


def downgrade_gate(verdict_obj, claims_obj, material):
    """闸门六：降级表述完整性。返回 (ok, problems, red_hints, 每条裁定的核对明细)。"""
    claims = (claims_obj or {}).get("claims") or []
    by_id = {c.get("id"): c for c in claims if isinstance(c, dict)}
    rulings = ((verdict_obj or {}).get("rulings") or [])
    problems, red, detail = [], [], []
    judged, need_alt = 0, 0
    for r in rulings:
        if not isinstance(r, dict):
            continue
        cid = r.get("claim_id")
        decision = (r.get("decision") or "").strip()
        alt = (r.get("downgraded_wording") or "").strip()
        src = by_id.get(cid) or {}
        src_text = (src.get("text") or "").strip()
        rec = {"claim_id": cid, "decision": decision,
               "downgraded_wording": alt, "problems": []}
        if decision not in RULING_ANY:
            rec["problems"].append("裁定「{}」不在三档里（{}）".format(
                decision, " / ".join(RULING_ANY)))
        judged += 1
        if decision in (RULING_DOWNGRADE, RULING_RETRACT):
            need_alt += 1
            if not alt:
                rec["problems"].append(
                    "判「{}」却没有给 `downgraded_wording`——只删不给替代会把稿子掏空".format(
                        decision))
            elif len(_norm_anchor(alt)) < DOWNGRADE_MIN_CHARS:
                rec["problems"].append("替代表述太短（归一后 {} 字 < {}），等于没给"
                                       .format(len(_norm_anchor(alt)), DOWNGRADE_MIN_CHARS))
            else:
                sim = _overlap(alt, src_text) if src_text else 0.0
                rec["similarity_to_claim"] = round(sim, 3)
                if src_text and sim >= DOWNGRADE_SAME_SIM:
                    rec["problems"].append(
                        "替代表述与原主张几乎是同一句话（相似度 {:.2f} ≥ {:.2f}）——"
                        "这不算「降级」".format(sim, DOWNGRADE_SAME_SIM))
                new_nums = numbers_not_in(alt, material)
                if new_nums:
                    rec["new_numbers"] = new_nums
                    rec["problems"].append(
                        "替代表述里出现了材料里没有的数字：{}——"
                        "降级表述不许编新数据".format("、".join(new_nums[:6])))
                # 丢失事实：原主张里的数字一个都不剩 → 那是删掉不是降级
                lost = [n for n in NUM_RE.findall(src_text) if n not in numbers_in(alt)]
                if lost:
                    rec["lost_numbers"] = lost
                    red.append("主张 {} 的替代表述丢掉了原主张里的数字：{}——"
                               "降级应当是「换个更保守的说法」，不是把事实删掉"
                               .format(cid, "、".join(lost[:6])))
        elif decision == RULING_ACCEPT:
            if alt:
                red.append("主张 {} 判「可采信」却带了替代表述——判据自相矛盾".format(cid))
            if not (r.get("basis_quote") or "").strip():
                rec["problems"].append("判「可采信」却没给 `basis_quote`（凭什么可采信）")
        if rec["problems"]:
            problems.extend(["主张 {}：{}".format(cid, p) for p in rec["problems"]])
        detail.append(rec)
    if not rulings:
        problems.append("裁决书里没有任何裁定（rulings 为空）——等于没裁")
    return (not problems), problems, red, detail, {"judged": judged, "need_alt": need_alt}


# ---------------------------------------------------------------------------
# 闸门七：评级口径一致性（**本包特有**）
#
# 取证方最容易犯的两个错：
#   1. 同一类证据在不同主张上一个评「强」一个评「弱」——那不是评级，是随手写的
#   2. 凭"主张说得有多确定"给强度，而不是凭"手里那点东西有多硬"
#
# 本地判法（确定性的，不采信自述）：
#   · 归一到四档；归一不了就用 confidence 兜底映射
#   · 按 `source_key`（同一来源类型 / 同一证据编号）分组
#   · 同组内极差 > 1 档 → 判「评级口径不一致」
# 极差 1 档以内放行（同一来源在不同主张上确实可以有差别，例如同一个小样本
# 支撑一条窄结论（中）与一条外推结论（弱）——那是**结论范围**的差别，不是尺子的差别）。
# ---------------------------------------------------------------------------

STRENGTH_MAX_SPREAD = 1


def norm_strength(raw, confidence=None):
    """把取证方给的评级归一到四档。返回 (档位, 归一说明)。

    认四档中文；认不出来时用 confidence（0~1）兜底映射；
    两者都没有 → 「未标注」（闸门会把它算作口径问题，而不是静默当"中"）。
    """
    v = raw.strip() if isinstance(raw, str) else ""
    for lvl in STRENGTH_LEVELS:
        if v == lvl:
            return lvl, "原样"
    if v:
        for lvl in STRENGTH_LEVELS:
            if v.startswith(lvl):
                return lvl, "前缀归一（原写「{}」）".format(v[:12])
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return "未标注", "没给四档评级，也没给 confidence"
    if c >= 1.0:
        c = 1.0
    for th, lvl in CONFIDENCE_BUCKETS:
        if c >= th:
            return lvl, "由 confidence={} 兜底映射".format(c)
    return "无据", "由 confidence={} 兜底映射".format(c)


def strength_consistency(evidence_obj):
    """闸门七：按 source_key 分组核对评级口径。返回结构化结论。"""
    rows = ((evidence_obj or {}).get("ratings") or [])
    groups = {}
    items, unlabeled = [], []
    for r in rows:
        if not isinstance(r, dict):
            continue
        lvl, how = norm_strength(r.get("strength"), r.get("confidence"))
        key = (r.get("source_key") or "").strip()
        rec = {"claim_id": r.get("claim_id"), "source_key": key,
               "strength": lvl, "how": how,
               "raw_strength": r.get("strength"), "confidence": r.get("confidence"),
               "decisive_gap": (r.get("decisive_gap") or "").strip()}
        items.append(rec)
        if not key:
            unlabeled.append(rec)
            continue
        groups.setdefault(key, []).append(rec)
    problems, red = [], []
    for key, members in sorted(groups.items()):
        lv = [STRENGTH_VALUE.get(m["strength"], -1) for m in members]
        known = [x for x in lv if x >= 0]
        if len(known) < 2:
            continue
        spread = max(known) - min(known)
        if spread > STRENGTH_MAX_SPREAD:
            problems.append(
                "同一来源「{}」在 {} 条主张上的评级是 {}——极差 {} 档 > {} 档。"
                "同一类证据必须用同一把尺子（这是评级口径不一致，不是结论范围的差别）"
                .format(key, len(members), "、".join(m["strength"] for m in members),
                        spread, STRENGTH_MAX_SPREAD))
    if unlabeled:
        red.append("有 {} 条评级没给出 source_key（同一来源的评级无法被本地核对）"
                   .format(len(unlabeled)))
    if not items:
        problems.append("取证方没有给出任何评级（ratings 为空）")
    n_un = [m for m in items if m["strength"] == "未标注"]
    if n_un:
        red.append("有 {} 条评级归一不到四档（既不是强/中/弱/无据，也没有 confidence）"
                   .format(len(n_un)))
    return {
        "ok": not problems,
        "problems": problems,
        "red_hints": red,
        "red": bool(problems) or bool(red),
        "groups": {k: [m["strength"] for m in v] for k, v in sorted(groups.items())},
        "items": items,
        "unlabeled": unlabeled,
        "values": STRENGTH_VALUE,
        "max_spread": STRENGTH_MAX_SPREAD,
    }


# ---------------------------------------------------------------------------
# 闸门：追认门（证据强度 → 裁定档位）
#
# 这一条是"取证"这件事的逻辑底线，比闸门七更基本：
#   · 证据强度「弱」或「无据」的主张，**不许判「可采信」**
#   · 证据强度「强」的主张，**不许判「撤回」**（要撤回得说清不是强度的问题）
# 没有它，四大角色就只是四次独立输出，而不是一条链。
# ---------------------------------------------------------------------------

RULING_ACCEPT = "可采信"
RULING_DOWNGRADE = "降级表述"
RULING_RETRACT = "撤回"
RULING_ANY = (RULING_ACCEPT, RULING_DOWNGRADE, RULING_RETRACT)


def evidence_gate(verdict_obj, evidence_obj):
    """追认门：裁决必须与证据强度自洽。返回结构化结论。"""
    levels = {}
    for r in ((evidence_obj or {}).get("ratings") or []):
        if not isinstance(r, dict):
            continue
        lvl, _how = norm_strength(r.get("strength"), r.get("confidence"))
        cid = r.get("claim_id")
        prev = levels.get(cid)
        # 同一主张多条评级时取**最低**那一档（裁决要按最弱的支撑来定）
        if prev is None or STRENGTH_VALUE.get(lvl, -1) < STRENGTH_VALUE.get(prev, 9):
            levels[cid] = lvl
    problems, red = [], []
    for r in (verdict_obj or {}).get("rulings") or []:
        if not isinstance(r, dict):
            continue
        cid = r.get("claim_id")
        decision = (r.get("decision") or "").strip()
        lvl = levels.get(cid)
        if lvl is None:
            red.append("主张 {} 没有任何证据强度评级，裁决却给它定了档".format(cid))
            continue
        if lvl in ("弱", "无据") and decision == RULING_ACCEPT:
            problems.append(
                "主张 {} 的证据强度是「{}」，却被判「可采信」——"
                "强度撑不住的结论不许原样采信（要么给替代表述，要么撤回）".format(cid, lvl))
        if lvl == "强" and decision == RULING_RETRACT:
            problems.append(
                "主张 {} 的证据强度是「强」，却被判「撤回」——"
                "强度不是撤回的理由，要撤回必须另给依据".format(cid))
        if lvl == "无据" and decision != RULING_RETRACT:
            red.append("主张 {} 的证据强度是「无据」，裁定是「{}」——"
                       "无据的主张通常只能撤回，建议人工复核".format(cid, decision))
    # 每条被挑战成立的主张都必须被处置（不许装作没看见）
    return {"ok": not problems, "problems": problems, "red_hints": red,
            "red": bool(problems) or bool(red),
            "levels_by_claim": levels,
            "note": ("同一主张有多条评级时取**最低**那一档：裁决要按最弱的支撑来定，"
                     "不能挑对自己有利的那条。")}


# ---------------------------------------------------------------------------
# 提示词
#
# 【铁律】提示词里**不许出现任何一条可直接复制的完整中文范文句**。
# 事故复盘（同族，实测抓到两例）：提示词里写过正例，模型直接产出同构句；
# 尤其严重的一例，全批最高分的那条一字不差就是提示词里的示例 ——
# "抄了标准答案"被当成"真的最好"。
# 本包的对策一样：讲形态只用**描述性语言**；确实要举例时用**跨主题示例**
# （登记进 PROMPT_SAMPLES，由 prompt_echo 闸门兜底）。
#
# 【信息隔离】challenge 阶段的提示词里**只有主张方的结论与主张文本，加上
# 证据的编号/名称/来源类型**——没有主张方的推理过程（`reasoning`），
# 没有证据的具体断言与强度，也没有其它角色的任何文字。
# 这是本包最关键的机制约束：质疑方看不到主张方"为什么这么想"，
# 只能对着"结论 + 编号"挑漏洞；否则它会顺着别人的论证往下补，
# 挑出来的都是措辞问题，而不是主张本身站不站得住。
# ---------------------------------------------------------------------------

CHAT_RETRY_NOTE = "上游 5xx 与网络抖动退避重试；4xx 直接报错，不浪费额度。"

CLAIM_SYSTEM = (
    "你是「三剪客 · 调研取证小组」的**主张方**。\n"
    "你的职责：把材料里的结论与支撑主张**拆开摊平**，并给每条主张**指名依据**。\n"
    "你的目标：{goal}\n"
    "你的天然倾向（这是职责，不是偏见）：{bias}\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 每条主张的 `quote` 必须**原样引用**材料里真实存在的一句话（或句中连续的一小段），"
    "不得改写、不得概括、不得凭空编造引文。引不出来的主张一律不要写。\n"
    "  2. 一条主张只讲一件事，必须能被单独挑战（不要写成三段话的复合句）。\n"
    "  3. 每条主张至少引用一条证据；证据要落成编号条目（编号 / 名称 / 来源类型 / 时间）。\n"
    "     不许写「有数据支持」「业内普遍认为」这类没有编号的说法。\n"
    "  4. `reasoning` 写你**为什么**把这条主张当成支撑（这是给裁决方看的，"
    "质疑方看不到它）。\n"
    "  5. 不许编造材料里没有的数据、机构名、人名、年份。\n"
    "  6. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

_CHALLENGE_SYSTEM = (
    "你是「三剪客 · 调研取证小组」的**质疑方**。\n"
    "你**看不到**主张方的推理过程，也看不到证据的具体内容——"
    "你只看得到它的**结论**、**主张原句**，以及它引用的**证据编号与来源类型**。\n"
    "这不是信息缺失，这是设计：你要对着「这句话凭什么被信」本身挑漏洞，"
    "而不是顺着别人的论证往下补。\n"
    "你的目标：{goal}\n"
    "你的天然倾向（这是职责，不是偏见）：{bias}\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 每条挑战必须**指出挑战类型**，只能从这七类里选一个：{types}。\n"
    "  2. 每条挑战必须有 `reason`（为什么这是漏洞）与 `required_fix`"
    "（要补成什么样这条主张才站得住）。两者都不许写成「建议补充数据」这类空话。\n"
    "  3. `quote` 必须是**主张原句**（原样摘引，不得改写）。摘不出来就不要写这条。\n"
    "  4. **挑战不动就如实说挑战不动**：`verdict` 写 passed，"
    "并在 `unable_reason` 里说清它为什么挑不动。硬凑挑战比放行更糟。\n"
    "  5. 不许因为措辞不合口味就判挑战成立；也不许对每一条都放行。\n"
    "  6. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

EVIDENCE_SYSTEM = (
    "你是「三剪客 · 调研取证小组」的**取证方**。\n"
    "你的职责只有一件：给每条主张手里的那点东西**评一个强度档位**，并说清**为什么不是更高一档**。\n"
    "你的目标：{goal}\n"
    "你的天然倾向（这是职责，不是偏见）：{bias}\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. `strength` 只能是四档之一：强 / 中 / 弱 / 无据。\n"
    "  2. **必须先按下面这份形态表判断，再给档位**——不许凭「这条主张说得多确定」给分：\n"
    "{shapes}\n"
    "  3. 每一条都要给 `source_key`：**同一类证据必须用同一个 key**，"
    "例如都写「单一来源」或都写「小样本自采」。本地会按这个 key 核对你的尺子有没有歪。\n"
    "  4. 每条都要写 `decisive_gap`（决定性缺口：为什么不是更高一档）。这一栏不许空。\n"
    "  5. `confidence` 给 0~1 的数字，作为 `strength` 的量化备注；两者口径要一致。\n"
    "  6. 你只评级，**不裁决**：不许写「建议撤回」「可以保留」这类结论。\n"
    "  7. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

ARBITER_SYSTEM = (
    "你是「三剪客 · 调研取证小组」的**裁决方**。你有终裁权。\n"
    "你的职责：定**可采信边界**——哪几句能原样保留、哪几句必须换个说法、哪几句必须删。\n"
    "你的目标：{goal}\n"
    "你的天然倾向（这是职责，不是偏见）：{bias}\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. `decision` 只能三选一：可采信 / 降级表述 / 撤回。\n"
    "  2. **判「降级表述」或「撤回」的，必须给 `downgraded_wording`**——"
    "一句真的更保守、能直接替换进稿子的说法。\n"
    "     替代表述要真的换说法（不能把原句抄一遍），也不许引入材料里没有的新数字，"
    "更不许把原文的数字删掉（那是删除，不是降级）。\n"
    "     做法：去掉绝对化、加上限定范围、交代口径、改成方向性表述。\n"
    "  3. 证据强度是「弱」或「无据」的主张，**不许判「可采信」**。\n"
    "  4. 判「可采信」的必须给 `basis_quote`（凭什么可采信），且不许带替代表述。\n"
    "  5. 每条裁定都要说清依据哪条挑战或哪条评级（`basis` 栏）。\n"
    "  6. 对被挑战成立的主张必须正面处置，不许装作没看见。\n"
    "  7. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

# 跨主题示例：只用来讲"什么样的挑战算挑不动"，不是范文。
# 跨主题 = 与任何真实调研选题都不搭（社区团购团长数），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
_PROMPT_SAMPLE_BLOCK = (
    "跨主题示例（**仅供理解「什么算没挑动」，禁止把示例原句写进任何字段**）：\n"
    "  · 没挑动（不算挑战）：只说「这条表述可能不够严谨」，不说哪一类漏洞、要补什么。\n"
    "  · 挑得动（算挑战）：指出具体漏洞类型 + 补成什么样这条主张才站得住。\n"
).format()

_CLAIMS_SCHEMA = {
    "conclusion": "这份材料要读者相信的一句话结论",
    "claims": [
        {
            "id": "C1（依次 C2、C3…）",
            "text": "这条主张的原句（可被单独挑战的一句话）",
            "quote": "材料里**原样**的一句话（主张所依据的原文）",
            "claim_type": "|".join(CLAIM_TYPES),
            "evidence_ids": ["E1"],
            "reasoning": "为什么用这条主张支撑结论（**质疑方看不到这一栏**）",
        }
    ],
    "evidence": [
        {
            "id": "E1（依次 E2、E3…）",
            "name": "这份证据叫什么（一个可指认的名字，不是形容词）",
            "source_type": "|".join(SOURCE_SHAPES),
            "timeframe": "这份证据的时间范围（哪一年 / 哪一段）",
            "coverage": "它覆盖了什么、没覆盖什么",
        }
    ],
    "summary": "两三句总评",
}

_CHALLENGE_SCHEMA = {
    "challenges": [
        {
            "target": "C1（主张 id）",
            "quote": "该主张的原句（原样摘引）",
            "challenge_type": "|".join(CHALLENGE_TYPES),
            "severity": "|".join(SEVERITY_LEVELS),
            "reason": "这条主张在这个类型上的漏洞具体是什么",
            "required_fix": "要补成什么样，这条主张才站得住",
            "verdict": "challenged（挑战成立）|passed（挑不动）",
            "unable_reason": "verdict=passed 时必填：为什么挑不动",
            "demand_retract": True,
        }
    ],
    "acknowledged": ["我逐条看过、确实挑不动的主张 id"],
    "overall": "两三句总评：这份材料整体最容易在哪被问倒",
}

_EVIDENCE_SCHEMA = {
    "ratings": [
        {
            "claim_id": "C1",
            "evidence_ids": ["E1"],
            "source_key": "同一类证据用同一个 key（如「单一来源」「小样本自采」）",
            "strength": "|".join(STRENGTH_LEVELS),
            "confidence": 0.0,
            "shape": "|".join(SOURCE_SHAPES),
            "decisive_gap": "决定性缺口：为什么不是更高一档",
        }
    ],
    "summary": "两三句总评",
}

_VERDICT_SCHEMA = {
    "rulings": [
        {
            "claim_id": "C1",
            "decision": "|".join(RULING_ANY),
            "strength_seen": "|".join(STRENGTH_LEVELS),
            "basis": "依据哪条挑战或哪条评级",
            "basis_quote": "材料里**原样**的一句话（判「可采信」时必填）",
            "downgraded_wording": "判「降级表述」或「撤回」时必填：可直接替换进稿子的更保守说法",
            "how_to_use": "这条替代表述怎么用（放哪一段、要不要配口径说明）",
        }
    ],
    "accepted": ["可原样保留的主张 id"],
    "downgraded": ["必须换说法的主张 id"],
    "retracted": ["必须删掉的主张 id"],
    "rationale": "裁决理由：逐条回应被挑战成立的主张",
    "summary": "两三句",
}


def _fmt_shapes():
    return "\n".join("     - {}".format(s) for s in SOURCE_SHAPES)


def build_claims_prompt(material, material_meta=None):
    """主张方提示词。"""
    meta = material_meta or {}
    lines = [
        "下面是**一份调研材料/稿件**（含它的结论与依据）。请以「主张方」的身份，",
        "把它拆成「一句话结论 + 若干条可被单独挑战的支撑主张 + 一份编号证据清单」。",
        "",
        "拆解要求：",
        "  · 结论写在 conclusion 栏，一句话，不要复述全文。",
        "  · 每条主张只讲一件事；`claim_type` 从这几类里选一个：" + " / ".join(CLAIM_TYPES) + "。",
        "  · `evidence_ids` 必须指向你在 evidence 里列出的编号；没有编号的依据不要写。",
        "  · evidence 里的 `name` 要是一个**可指认的名字**（报告名 / 台账名 / 访谈对象类别），",
        "    不许写「业内数据」「相关研究」这类无法指认的说法。",
        "  · `reasoning` 写你凭什么把这句当选支撑——这一栏**质疑方看不到**，",
        "    所以它不需要防守措辞，把真实想法写清楚。",
        "",
        _PROMPT_SAMPLE_BLOCK,
    ]
    if meta.get("chars"):
        lines += ["", "  · 待证材料 {} 字符 / {} 句".format(meta.get("chars"), meta.get("sentences"))]
    return (
        "请以「主张方」的身份，为下面这份材料建立**主张清单与证据清单**。\n"
        + "\n".join(lines)
        + "\n\n按要求只输出这个 JSON 对象：\n"
        + json.dumps(_CLAIMS_SCHEMA, ensure_ascii=False, indent=1)
        + "\n\n===== 待证材料开始 =====\n" + (material or "")
        + "\n===== 待证材料结束 =====\n"
    )


def build_challenge_prompt(claims_obj):
    """质疑方提示词：**只有结论、主张原句、证据编号/名称/来源类型**。

    这是信息隔离的实现处。三样东西**故意不给**：
      · 主张的 `reasoning`（推理过程）
      · 证据的 `coverage`（它覆盖了什么）——那会泄露主张方的论证边界
      · 其它角色的任何文字
    给的是：结论、主张原句、claim_type、引用的证据编号 + 名称 + 来源类型 + 时间。
    """
    claims = (claims_obj or {}).get("claims") or []
    ev = {e.get("id"): e for e in ((claims_obj or {}).get("evidence") or [])
          if isinstance(e, dict)}
    blocks = []
    for c in claims:
        ids = c.get("evidence_ids") or []
        ev_lines = []
        for eid in ids:
            e = ev.get(eid) or {}
            ev_lines.append("        · [{}] {}（来源类型：{}；时间：{}）".format(
                eid, e.get("name") or "（未命名）",
                e.get("source_type") or "（未标注）",
                e.get("timeframe") or "（未标注）"))
        blocks.append(
            "【{}】类型：{}\n    原句：{}\n    它引用的证据：\n{}".format(
                c.get("id"), c.get("claim_type") or "未标注", c.get("text") or "-",
                "\n".join(ev_lines) if ev_lines else "        （未给出证据编号）"))
    return (
        "下面是**主张方的结论与主张清单**。你**看不到**它的推理过程，"
        "也看不到证据的具体内容——只有编号、名称、来源类型与时间。\n"
        "请以「质疑方」的身份，**逐条**挑战。\n\n"
        "结论（主张方要读者相信的一句话）：\n  " + ((claims_obj or {}).get("conclusion") or "-") + "\n\n"
        "挑战纪律（违反就整份作废）：\n"
        "  1. 每条挑战必须指出 `challenge_type`，只能七选一："
        + " / ".join(CHALLENGE_TYPES) + "。\n"
        "  2. `reason` 与 `required_fix` 都必须写实（本地会按长度与实质判断），"
        "不许写「建议补充数据」「表述需更严谨」这类空话。\n"
        "  3. `quote` 必须是**主张原句**（原样摘引）。\n"
        "  4. **逐条都要有记录**：挑战成立写 challenged，挑战不动写 passed 并在 "
        "`unable_reason` 里说清为什么挑不动。\n"
        "     对每一条都放行、或对每一条都硬判成立，都是错的——本地闸门会拦「一条都没成立」。\n"
        "  5. `demand_retract`：你认为这条主张**必须撤回**（不是补正就能救）时填 true。\n"
        "  6. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n\n"
        + _PROMPT_SAMPLE_BLOCK
        + "\n\n===== 结论与主张清单开始 =====\n"
        + "\n\n".join(blocks) if blocks else "（没有主张）"
    ) + (
        "\n===== 结论与主张清单结束 =====\n\n"
        "按要求只输出这个 JSON 对象：\n"
        + json.dumps(_CHALLENGE_SCHEMA, ensure_ascii=False, indent=1)
        + "\n"
    )


def build_evidence_prompt(claims_obj, challenge_obj):
    """取证方提示词：看到主张、证据条目与挑战记录，逐条评级。"""
    claims = (claims_obj or {}).get("claims") or []
    ev = {e.get("id"): e for e in ((claims_obj or {}).get("evidence") or [])
          if isinstance(e, dict)}
    ch = {}
    for r in ((challenge_obj or {}).get("challenges") or []):
        if isinstance(r, dict) and r.get("target"):
            ch.setdefault(r["target"], []).append(r)
    blocks = []
    for c in claims:
        ev_lines = []
        for eid in c.get("evidence_ids") or []:
            e = ev.get(eid) or {}
            ev_lines.append("      · [{}] {}（来源类型：{}；时间：{}；覆盖：{}）".format(
                eid, e.get("name") or "（未命名）", e.get("source_type") or "（未标注）",
                e.get("timeframe") or "（未标注）", e.get("coverage") or "（未标注）"))
        ch_lines = []
        for r in ch.get(c.get("id")) or []:
            ch_lines.append("      · [{} / {} / {}] {}".format(
                r.get("challenge_type") or "未标注", r.get("severity") or "未标注",
                r.get("verdict") or "未标注", (r.get("reason") or "-")[:160]))
        blocks.append(
            "【{}】类型：{}\n    原句：{}\n    证据：\n{}\n    被挑战：\n{}".format(
                c.get("id"), c.get("claim_type") or "未标注", c.get("text") or "-",
                "\n".join(ev_lines) if ev_lines else "      （无）",
                "\n".join(ch_lines) if ch_lines else "      （本轮没有挑战记录）"))
    return (
        "下面是**待证材料的主张清单、证据条目与挑战记录**。"
        "请以「取证方」的身份，逐条给出**证据强度评级**。\n\n"
        "评级纪律（违反就整份作废）：\n"
        "  1. 四档：强 / 中 / 弱 / 无据。\n"
        "  2. **先按形态表判断，再给档位**——不许凭「这条主张说得多确定」给分：\n"
        + _fmt_shapes() + "\n"
        "  3. `source_key` 是本地核对你尺子的依据：**同一类证据必须用同一个 key**。\n"
        "     本地会按 key 分组比对，同组极差超过一档就判「评级口径不一致」。\n"
        "  4. `decisive_gap` 必填：为什么不是更高一档（决定性缺口）。\n"
        "  5. 你只评级，不裁决：不许写「建议撤回」「可以保留」。\n"
        "  6. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n\n"
        + _PROMPT_SAMPLE_BLOCK
        + "\n\n===== 主张 / 证据 / 挑战开始 =====\n"
        + ("\n\n".join(blocks) if blocks else "（没有主张）")
        + "\n===== 结束 =====\n\n"
        "按要求只输出这个 JSON 对象：\n"
        + json.dumps(_EVIDENCE_SCHEMA, ensure_ascii=False, indent=1)
        + "\n"
    )


def build_verdict_prompt(claims_obj, challenge_obj, evidence_obj):
    """裁决方提示词：看到全部三份产出，出可采信边界 + 降级表述。"""
    claims = (claims_obj or {}).get("claims") or []
    eff = {x.get("target") for x in
           ((challenge_obj or {}).get("effective") or [])}
    ratings = {}
    for r in ((evidence_obj or {}).get("ratings") or []):
        if isinstance(r, dict) and r.get("claim_id"):
            lvl, _how = norm_strength(r.get("strength"), r.get("confidence"))
            prev = ratings.get(r["claim_id"])
            if prev is None or STRENGTH_VALUE.get(lvl, -1) < STRENGTH_VALUE.get(prev, 9):
                ratings[r["claim_id"]] = lvl
    ch_by = {}
    for r in ((challenge_obj or {}).get("challenges") or []):
        if isinstance(r, dict) and r.get("target"):
            ch_by.setdefault(r["target"], []).append(r)
    blocks = []
    for c in claims:
        cid = c.get("id")
        ch_lines = []
        for r in ch_by.get(cid) or []:
            ch_lines.append("    · {}：{}（类型 {} / {}）→ 要求：{}".format(
                "**挑战成立**" if r.get("verdict") == "challenged" else "挑战未成立",
                (r.get("reason") or "-")[:160], r.get("challenge_type") or "未标注",
                r.get("severity") or "未标注", (r.get("required_fix") or "-")[:120]))
        blocks.append(
            "【{}】{}\n    原句：{}\n    证据强度（本地按最低档取）：{}\n"
            "    引用的证据：{}\n    挑战：\n{}".format(
                cid, c.get("claim_type") or "未标注", c.get("text") or "-",
                ratings.get(cid) or "（未评级）",
                "、".join(c.get("evidence_ids") or []) or "（无）",
                "\n".join(ch_lines) if ch_lines else "    （没有挑战记录）"))
    return (
        "下面是待证材料的**主张清单、挑战记录与证据强度评级**。"
        "请以「裁决方」的身份出一份**可采信边界**。\n\n"
        "裁决纪律（违反就整份作废）：\n"
        "  1. `decision` 只能三选一：可采信 / 降级表述 / 撤回。\n"
        "  2. **判「降级表述」或「撤回」的，`downgraded_wording` 必填**："
        "一句真的更保守、**能直接替换进原稿**的说法。\n"
        "     它不能把原句抄一遍（本地算相似度，太像就判「没换说法」）；"
        "     不能引入材料里没有的新数字；也不能把原文的数字丢掉（那是删除，不是降级）。\n"
        "     做法：去掉绝对化 / 加上限定范围 / 交代口径 / 改成方向性表述。\n"
        "  3. 证据强度是「弱」或「无据」的主张，**不许判「可采信」**。\n"
        "  4. 判「可采信」必须给 `basis_quote`（材料里原样的一句），且**不许**带替代表述。\n"
        "  5. 每条裁定都要写清依据（`basis`）。被挑战成立的主张（下面标了"
        "「**挑战成立**」的）必须正面处置，不许绕开。\n"
        "  6. `accepted` / `downgraded` / `retracted` 三个 id 列表要与 rulings 里的 decision 一致。\n"
        "  7. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n\n"
        + _PROMPT_SAMPLE_BLOCK
        + "\n\n===== 主张 / 挑战 / 证据强度开始 =====\n"
        + ("\n\n".join(blocks) if blocks else "（没有主张）")
        + "\n===== 结束 =====\n\n"
        "按要求只输出这个 JSON 对象：\n"
        + json.dumps(_VERDICT_SCHEMA, ensure_ascii=False, indent=1)
        + "\n"
    )


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class CrewError(a7w.A7wError):
    """取证流程里的所有可预期失败。子类各自带退出码。"""
    exit_code = EXIT_CALL


class UsageError(CrewError):
    """参数/配置用错了（文件不存在、角色名错、给了 --budget 没给单价…）。→ 退出码 2"""
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """产出路径落在 Skill 包内（退出码 2）。"""


class GateFail(CrewError):
    """硬闸门命中（退出码 3）。"""
    exit_code = EXIT_GATE


class BudgetStop(CrewError):
    """预算超限，已就地中止（退出码 5）。"""
    exit_code = EXIT_BUDGET


# ⚠️ 上游 `finish_reason` 记录位。解析失败时**按它分叉**：
#   finish_reason == "length" → 是真截断，加大 --max-tokens 有用
#   finish_reason != "length" → **加大 --max-tokens 没用**，要明说
# 事故复盘（同族）：靠"内容长度是不是接近 max_tokens"猜截断，猜错过两次 ——
# 模型的 JSON 本来就可能比上限短得多，长度判断会把"格式错"误报成"截断"，
# 于是用户去调大 max-tokens，白花钱还解决不了问题。
# 所以本包**只认 finish_reason**，不认 content 长度。
_LAST_FINISH = {"finish_reason": None, "model": None, "usage": None}


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    ⚠️ 本函数**故意不走** `a7w._request`：那边的 `raw` 参数是**原始请求体字节**
    （用于 multipart 上传），**不是**"要原始响应"。同族有人把它当成后者用过，
    结果崩在**钱已经扣之后**。本包一律自己发 urllib 请求，语义只有一种，不给误用的机会。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见，
    一次取证要跑四次调用，被一次抖动打断要重跑整轮，很亏。
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
    _LAST_FINISH["finish_reason"] = None
    _LAST_FINISH["model"] = model

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
                raise CrewError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise CrewError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise CrewError("模型不存在（404）：{}  "
                                "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
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

    # 网关把 OpenAI 的返回包了一层 {"code":1,"data":{...}}，两种形态都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise CrewError("模型没返回 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    choice0 = choices[0] or {}
    content = (choice0.get("message") or {}).get("content") or ""
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    # ⚠️ 记录 finish_reason：解析失败时靠它分叉（=length 才是截断）
    _LAST_FINISH["finish_reason"] = choice0.get("finish_reason")
    _LAST_FINISH["model"] = (data_obj or {}).get("model") or model
    _LAST_FINISH["usage"] = usage
    return content, usage


def _outermost_json(text):
    """抠出 text 里**最外层括号配平的**完整 JSON 值（dict 或 list）。

    为什么要配平而不是"从每个 `{` 试着 raw_decode"：
    模型常见输出是「合法 JSON + 后面多吐了几个字符」。逐个 `{` 试的写法在
    遇到 `{"a": {"b": 1}}` 这种嵌套时，会从**内层** `{` 开始解出一个 `{"b": 1}`——
    于是解析"成功"了，拿到的是半个对象，**报错指向错误方向**
    （用户看到的是"字段缺失"，而真正的问题是外层多了一个字符）。
    这里改成：从第一个 `{` / `[` 开始做括号配平（跳过字符串内的括号与转义），
    配到平衡就 raw_decode 那一段；失败才往后挪。
    """
    n = len(text or "")
    i = 0
    while i < n:
        if text[i] not in "{[":
            i += 1
            continue
        depth = 0
        j = i
        in_str = False
        esc = False
        while j < n:
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth == 0 and j < n:
            cand = text[i:j + 1]
            try:
                obj = json.loads(cand)
            except ValueError:
                obj = None
            if isinstance(obj, (dict, list)):
                return obj, cand
        i += 1
    return None, None


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值（**优先取最外层括号配平的完整值**）。

    顺序：先试 ``` 围栏里的内容，再试原文。每一份都走 `_outermost_json`
    （括号配平 → 整段 raw_decode），配平失败才退回逐个起点试解。
    """
    if not text:
        raise CrewError("模型返回空内容")
    dec = json.JSONDecoder()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    cands = []
    if fenced:
        cands.append(fenced.group(1).strip())
    cands.append(text)
    for cand in cands:
        obj, _raw = _outermost_json(cand)
        if isinstance(obj, (dict, list)):
            return obj
        # 退路：配平失败（例如字符串没闭合）时按起点逐个试
        for i, ch in enumerate(cand):
            if ch not in "{[":
                continue
            try:
                obj, _end = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    raise CrewError(_json_parse_error(text))


def _json_parse_error(text):
    """解析失败时**按 finish_reason 分叉**给出可执行的处置建议。

    这是本包最容易骗人的一处：同族早期用 content 长度判断"是不是被截断了"，
    结果把「格式错」误报成"截断"，用户去调大 --max-tokens，白花钱还解决不了问题。
    只认 finish_reason：
      · =length  → 真是被 max_tokens 截断，加大有效
      · ≠length  → **加大 --max-tokens 没用**，得从别处找原因（要明说）
    """
    fr = _LAST_FINISH.get("finish_reason")
    head = "模型返回的不是合法 JSON：{}".format((text or "")[:300].replace("\n", " "))
    if fr == "length":
        return (head + "\n【诊断】finish_reason=length —— 输出**确实**被 max_tokens 截断了。"
                       "加大 --max-tokens 有效（这类产出建议 ≥ 4096）。")
    if fr:
        return (head + "\n【诊断】finish_reason={}（**不是 length**）——"
                       "所以这**不是截断**，加大 --max-tokens 没用。"
                       "多半是模型没按 JSON 输出（换模型或加 --no-json-mode 试试），"
                       "或者它输出了非 JSON 的说明文字。".format(fr))
    return (head + "\n【诊断】上游没有返回 finish_reason（可能被网关吞了）。"
                   "无法判断是不是截断；先把 --max-tokens 调大一次试试，"
                   "若仍同样报错，就不是截断问题。")


# ---------------------------------------------------------------------------
# 成本：token 标定 + 预算闸门
#
# 只出 token，**不编金额**：文本模型网关不公布单价（/api/v1/models 里也没有价格字段）。
# 字符 → token 的标定比例（**是全族实测值**，不是厂商文档）：
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN_IN = 1.61     # 输入侧：拿真实调用标定，实测均值 1.612
TOKENS_PER_CHAR_OUT = 1.11    # 输出侧：1 个原始字符 ≈ 多少 token，实测均值 1.109
POINTS_PER_YUAN = 100.0       # 平台口径：1 元 = 100 点

CLAIMS_OUT_TOKENS = 1300      # 主张清单的输出经验值（结论 + 主张 + 证据清单）
CHALLENGE_OUT_TOKENS = 1300   # 质疑书的输出经验值（逐条挑战 + 类型 + 要求）
EVIDENCE_OUT_TOKENS = 900     # 证据强度评级的输出经验值
VERDICT_OUT_TOKENS = 1300     # 裁决书的输出经验值（裁定 + 降级表述）


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(text, role_count=4):
    """一次完整取证的调用清单（用于报价，越清楚越好）。"""
    src_in = estimate_tokens_in(text)
    calls = [{
        "stage": "主张方：主张清单 + 证据引用", "calls": 1,
        "tokens_in": src_in + 700, "tokens_out": CLAIMS_OUT_TOKENS,
        "note": "输入 = 材料全文 + 拆解要求",
    }]
    claims_out_chars = int(CLAIMS_OUT_TOKENS / TOKENS_PER_CHAR_OUT)
    ch_in = src_in + claims_out_chars + 500
    calls.append({
        "stage": "质疑方：逐条挑战书（信息隔离）", "calls": 1,
        "tokens_in": ch_in, "tokens_out": CHALLENGE_OUT_TOKENS,
        "note": "输入 = 结论 + 主张原句 + 证据编号/名称/来源类型；**不含推理过程**",
    })
    ev_in = ch_in + int(CHALLENGE_OUT_TOKENS / TOKENS_PER_CHAR_OUT) + 400
    calls.append({
        "stage": "取证方：证据强度评级", "calls": 1,
        "tokens_in": ev_in, "tokens_out": EVIDENCE_OUT_TOKENS,
        "note": "输入 = 主张 + 证据条目 + 挑战记录（含形态表口径）",
    })
    verdict_in = ev_in + int(EVIDENCE_OUT_TOKENS / TOKENS_PER_CHAR_OUT) + 400
    calls.append({
        "stage": "裁决方：可采信边界 + 降级表述", "calls": 1,
        "tokens_in": verdict_in, "tokens_out": VERDICT_OUT_TOKENS,
        "note": "输入 = 主张 + 挑战 + 证据强度；产出裁定与替代表述",
    })
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
            "本次预计还要约 {} 点。调大 --budget，或换更短的模型。".format(
                round(tracker.points or 0, 4), tracker.budget,
                round((tracker.preview(est_in, max_tokens) or 0) - (tracker.points or 0), 4)))
    t0 = time.time()
    content, usage = chat(prompt, system=system, model=model, temperature=temperature,
                          max_tokens=max_tokens, key=key, json_mode=json_mode)
    tracker.add(usage, label)
    tracker.log[-1]["elapsed"] = round(time.time() - t0, 1)
    tracker.log[-1]["finish_reason"] = _LAST_FINISH.get("finish_reason")
    tracker.log[-1]["upstream_model"] = _LAST_FINISH.get("model")
    return content, usage


# ---------------------------------------------------------------------------
# 断点续跑
#
# 事故复盘（同族踩过三次，本包一次都不许再踩）：
#   · 内容截断没进 key   → 把 8000 字截成 4000 字重跑，key 没变，静默复用了旧产物
#   · 口径没进 key       → 换了闸门口径重跑，命中的还是上一版产物
#   · 阶段参数没进 key   → 参数调了但没生效，用户以为改过了
# 结论：**断点 key 必须含全部影响产出的维度**。
# ---------------------------------------------------------------------------

STATE_NAME = "state.json"
STATE_VERSION = 1


def state_key(stage, source_sha=None, source_chars=None, prompt_chars=None,
              model=None, temperature=None, roles=None, role_count=None,
              claims_sha=None, challenge_sha=None, evidence_sha=None,
              rubric=RUBRIC_VERSION, prompt=PROMPT_VERSION, rolesv=ROLES_VERSION):
    """算一个断点 key：**所有影响产出的维度都在里面**。

    参数逐个都有关联的事故：
      source_sha / source_chars  材料内容变了必须重跑（摘要防"改了一个字却复用"）
      prompt_chars               实际喂给模型的字符数；截断上限变了必须重跑
      model / temperature        换模型或换温度就是换产出
      roles / role_count         换角色组合 = 换取证链条
      claims_sha                 复用哪一份主张清单；那份文件变了必须重跑
      challenge_sha              复用哪一份质疑书
      evidence_sha               复用哪一份证据强度评级
      rubric / prompt / rolesv   口径版本、提示词版本、角色定义版本
    """
    payload = {
        "v": STATE_VERSION,
        "stage": stage,
        "source_sha": source_sha,
        "source_chars": source_chars,
        "prompt_chars": prompt_chars,
        "model": model,
        "temperature": temperature,
        "roles": list(roles or []),
        "role_count": role_count,
        "claims_sha": claims_sha,
        "challenge_sha": challenge_sha,
        "evidence_sha": evidence_sha,
        "rubric": rubric,
        "prompt": prompt,
        "roles_version": rolesv,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "{}:{}".format(stage, hashlib.sha256(blob).hexdigest()[:20])


def text_sha(text):
    """材料内容摘要（先做换行/空白归一，避免「只改了行尾空白」导致无谓重跑）。"""
    norm = re.sub(r"[ \t\r]+", " ", (text or "")).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


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


def ensure_outside_pkg(path, what="输出目录", example="research-crew-out"):
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
# 材料整理（`claims` 之前先本地扫一遍，**纯本地零成本**）
#
# 为什么不调模型：先把"大家要看同一份东西"固定下来。数字、专名、本地预扫
# 都能确定性抽出来；多花一次调用不会让它更准，只会让"先看看材料"开始花钱。
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$", re.M)
NUM_TOKEN_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|％|万|亿|千|百|元|块|天|小时|分钟|人|个|条|次|篇|台|单|份|家|位)?")


def extract_numbers(text):
    """抽材料里的数字（含单位）：取证里最常被「记错」与「编出来」的就是这类硬信息。"""
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
    (re.compile(r"([\u4e00-\u9fff]{2,12}(?:报告|白皮书|台账|后台|样本|调研|访谈|问卷))"), "资料来源"),
    (re.compile(r"\b([A-Z][A-Za-z0-9\-]{1,20}(?:\s[A-Z][A-Za-z0-9\-]{1,20})?)\b"), "英文"),
]
PROPER_STOP = {"ok", "vs", "etc", "eg", "ie", "nb", "json", "api", "cta", "url", "E1", "C1"}


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


CREW_QUESTIONS = [
    "这份材料要读者相信的**一句话结论**是什么？",
    "支撑这个结论的**主张**有几条？每条凭什么？",
    "这些主张里，哪一条最经不起问？",
    "哪一句必须换个说法才能对外说？",
]


def build_brief(text, source_path=None):
    """把待证材料整理成结构化索引（纯本地）。"""
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
        "crew_questions": list(CREW_QUESTIONS),
        "local_prescan": {
            "compliance": {"ok": not hits_c, "hits": hits_c, "exempted": exempted},
            "placeholder": {"ok": not ph, "hits": ph},
            "prompt_echo": {"ok": not echo, "hits": echo, "contain_skipped": echo_skips},
        },
        "note": ("本索引由本地整理（零调用）：大纲、数字、专有名词、本地预扫结果。"
                 "四个角色都会拿到材料全文。"
                 "⚠️ 本包**不联网检索**：这里只是把材料里的东西摊开，不去外部查证。"),
    }


def char_count(text):
    """正文字符数（**不含空白**）——中英混排时这个数比 len() 更贴近「篇幅」。"""
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


def _clamp01(v, default=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


def _as_id(raw, prefix):
    """把主张/证据 id 归一成 C1 / E1 这种形式（模型会写「C1」「c1」「主张1」）。"""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = re.search(r"[A-Za-z]?\s*(\d+)", s)
    if m:
        return "{}{}".format(prefix, m.group(1))
    return s if s.upper().startswith(prefix) else None


def normalize_claims(raw, material_target):
    """把主张方的模型返回归一化，并做**本地锚点校验**。

    锚定成功的那条会把 `quote` 就地修正成材料里的真实句子（`sentence` 字段）。
    锚不上的记进 `unanchored_claims`，**不进质疑方输入**（否则质疑方在挑战一句
    材料里根本不存在的话）。
    """
    raw = raw if isinstance(raw, dict) else {}
    claims_raw = raw.get("claims") if isinstance(raw.get("claims"), list) else []
    ev_raw = raw.get("evidence") if isinstance(raw.get("evidence"), list) else []
    ev_out, ev_ids = [], []
    for i, e in enumerate(ev_raw, 1):
        if not isinstance(e, dict):
            continue
        eid = _as_id(e.get("id"), "E") or "E{}".format(i)
        if eid in ev_ids:
            eid = "E{}".format(i)
        ev_ids.append(eid)
        ev_out.append({
            "id": eid,
            "name": (e.get("name") or "").strip(),
            "source_type": (e.get("source_type") or "").strip(),
            "timeframe": (e.get("timeframe") or "").strip(),
            "coverage": (e.get("coverage") or "").strip(),
        })
    ok, bad = [], []
    for i, c in enumerate(claims_raw, 1):
        if not isinstance(c, dict):
            continue
        cid = _as_id(c.get("id"), "C") or "C{}".format(i)
        quote = (c.get("quote") or "").strip()
        good, rule, sent_no, sent = material_target.check(quote)
        ct = (c.get("claim_type") or "").strip()
        if ct not in CLAIM_TYPE_ANY:
            ct = "未标注"
        item = {
            "id": cid,
            "text": (c.get("text") or "").strip(),
            "quote": quote,
            "claim_type": ct,
            "evidence_ids": [x for x in (_as_id(v, "E") for v in (c.get("evidence_ids") or []))
                             if x],
            "reasoning": (c.get("reasoning") or "").strip(),
            "anchor_rule": rule,
        }
        if good:
            item["sentence"] = sent
            item["sent_no"] = sent_no
            ok.append(item)
        else:
            item["why_unverified"] = (
                "引文在材料里找不到（归一化后也不匹配任一整句，模糊相似度 < {:.2f}）"
                "——判为锚点幻觉，不进质疑方输入".format(ANCHOR_SIM))
            bad.append(item)
    return {
        "conclusion": (raw.get("conclusion") or "").strip(),
        "claims": ok,
        "unanchored_claims": bad,
        "evidence": ev_out,
        "summary": (raw.get("summary") or "").strip(),
        "raw": raw,
    }


SPLIT_IDS_RE = re.compile(r"[、,，/\s]+")


def _split_ids(seq):
    """id 列表归一。模型有时会把 ["C1、C2"] 塞成一个字符串。"""
    out = []
    for x in seq or []:
        if not isinstance(x, str):
            continue
        for piece in SPLIT_IDS_RE.split(x):
            v = _as_id(piece, "C") or _as_id(piece, "E")
            if v and v not in out:
                out.append(v)
    return out


def normalize_challenge(raw, claims_obj, material_target):
    """把质疑方的返回归一化，并做**本地锚点校验**（引文必须是主张原句）。"""
    raw = raw if isinstance(raw, dict) else {}
    claims = (claims_obj or {}).get("claims") or []
    by_id = {c["id"]: c for c in claims}
    targets = {c["id"]: AnchorTarget(c["id"], "主张 {}".format(c["id"]), c.get("text") or "")
               for c in claims}
    rows, bad = [], []
    for r in (raw.get("challenges") if isinstance(raw.get("challenges"), list) else []):
        if not isinstance(r, dict):
            continue
        tid = _as_id(r.get("target"), "C")
        quote = (r.get("quote") or "").strip()
        ct = norm_challenge_type(r.get("challenge_type"))
        verdict = (r.get("verdict") or "").strip().lower()
        item = {
            "target": tid,
            "quote": quote,
            "challenge_type": ct or "",
            "severity": norm_severity(r.get("severity")),
            "reason": (r.get("reason") or "").strip(),
            "required_fix": (r.get("required_fix") or "").strip(),
            "verdict": (CHALLENGE_VERDICT_CHALLENGED if verdict.startswith("challenged")
                        or verdict == "挑战成立"
                        else CHALLENGE_VERDICT_PASSED if verdict.startswith("passed")
                        or verdict in ("放行", "挑不动", "未能挑战")
                        else ""),
            "unable_reason": (r.get("unable_reason") or "").strip(),
            "demand_retract": bool(r.get("demand_retract")),
            "anchor_rule": "unverified",
        }
        # 引文锚到**主张原句**（不是材料）——质疑方只能对着主张说话
        if tid in targets and quote:
            ok, rule, sent_no, sent = targets[tid].check(quote)
            item["anchor_rule"] = rule
            item["anchor_ok"] = ok
            if not ok:
                item["why_unverified"] = (
                    "引文与主张 {} 的原句对不上——疑似编造或改写了被挑战的主张，"
                    "该条挑战作废".format(tid))
        elif tid not in by_id:
            item["why_unverified"] = "target 不是有效主张 id：{}".format(r.get("target"))
        else:
            item["anchor_ok"] = True
        if item.get("why_unverified"):
            bad.append(item)
        rows.append(item)
    ack = _split_ids([x for x in (raw.get("acknowledged") or []) if isinstance(x, str)])
    return {
        "challenges": rows,
        "rejected_challenges": bad,
        "acknowledged": ack,
        "overall": (raw.get("overall") or "").strip(),
        "raw": raw,
    }


def normalize_evidence(raw, claims_obj):
    """把取证方的返回归一化（评级口径归一到四档并留归一说明）。"""
    raw = raw if isinstance(raw, dict) else {}
    rows = []
    for r in (raw.get("ratings") if isinstance(raw.get("ratings"), list) else []):
        if not isinstance(r, dict):
            continue
        lvl, how = norm_strength(r.get("strength"), r.get("confidence"))
        shape = (r.get("shape") or "").strip()
        if shape not in SOURCE_SHAPES:
            shape = "未标注"
        rows.append({
            "claim_id": _as_id(r.get("claim_id"), "C"),
            "evidence_ids": [x for x in (_as_id(v, "E") for v in (r.get("evidence_ids") or []))
                             if x],
            "source_key": (r.get("source_key") or "").strip(),
            "strength": lvl,
            "strength_how": how,
            "raw_strength": r.get("strength"),
            "confidence": r.get("confidence"),
            "shape": shape,
            "decisive_gap": (r.get("decisive_gap") or "").strip(),
        })
    return {"ratings": rows, "summary": (raw.get("summary") or "").strip(), "raw": raw}


def normalize_verdict(raw, claims_obj, material_target):
    """把裁决方的返回归一化，并做**本地锚点校验**（basis_quote 必须是材料原句）。"""
    raw = raw if isinstance(raw, dict) else {}
    claims = (claims_obj or {}).get("claims") or []
    rows = []
    for r in (raw.get("rulings") if isinstance(raw.get("rulings"), list) else []):
        if not isinstance(r, dict):
            continue
        cid = _as_id(r.get("claim_id"), "C")
        decision = (r.get("decision") or "").strip()
        if decision not in RULING_ANY:
            m = re.search(r"降级表述|可采信|撤回", decision)
            decision = m.group(0) if m else decision
        bq = (r.get("basis_quote") or "").strip()
        ok, rule, sent_no, sent = material_target.check(bq) if bq else (False, "unverified", None, "")
        seen = (r.get("strength_seen") or "").strip()
        rows.append({
            "claim_id": cid,
            "decision": decision,
            "strength_seen": seen,
            "basis": (r.get("basis") or "").strip(),
            "basis_quote": bq,
            "basis_anchor": {"ok": ok, "rule": rule, "sent_no": sent_no, "sentence": sent},
            "downgraded_wording": (r.get("downgraded_wording") or "").strip(),
            "how_to_use": (r.get("how_to_use") or "").strip(),
        })
    claim_ids = {c["id"] for c in claims}
    return {
        "rulings": rows,
        "accepted": [x for x in _split_ids(raw.get("accepted")) if x in claim_ids],
        "downgraded": [x for x in _split_ids(raw.get("downgraded")) if x in claim_ids],
        "retracted": [x for x in _split_ids(raw.get("retracted")) if x in claim_ids],
        "rationale": (raw.get("rationale") or "").strip(),
        "summary": (raw.get("summary") or "").strip(),
        "raw": raw,
    }


def anchor_stat_for(records):
    """把一批 bool 统计成锚点结论。"""
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


def collect_anchors(claims_obj, challenge_obj, verdict_obj):
    """四层锚点合并统计：主张引文 / 挑战引文 / 裁决依据引文。"""
    recs, rules = [], {}

    def push(ok, rule=None):
        recs.append(bool(ok))
        if ok and rule:
            rules[rule] = rules.get(rule, 0) + 1

    for c in (claims_obj or {}).get("claims") or []:
        push(True, c.get("anchor_rule") or "-")
    for c in (claims_obj or {}).get("unanchored_claims") or []:
        push(False)
    for r in (challenge_obj or {}).get("challenges") or []:
        if r.get("anchor_rule") == "unverified" and r.get("why_unverified"):
            push(False)
        else:
            push(True, r.get("anchor_rule") or "-")
    for r in (verdict_obj or {}).get("rulings") or []:
        a = r.get("basis_anchor") or {}
        if r.get("basis_quote"):
            push(bool(a.get("ok")), a.get("rule"))
    return recs, rules


# ---------------------------------------------------------------------------
# 产出文本（供闸门二 / 三扫描）
#
# ⚠️ 只拼**人读的散文字段**，绝不拼 JSON 序列化 —— 序列化里全是 `{}`，
# 拿它扫占位符会 100% 误报。这条边界踩过一次就够。
# ---------------------------------------------------------------------------

def output_prose(claims_obj, challenge_obj, evidence_obj, verdict_obj):
    parts = []
    c = claims_obj or {}
    parts.extend([c.get("conclusion") or "", c.get("summary") or ""])
    for x in c.get("claims") or []:
        parts.extend([x.get("text") or "", x.get("reasoning") or ""])
    for x in c.get("evidence") or []:
        parts.extend([x.get("name") or "", x.get("coverage") or ""])
    ch = challenge_obj or {}
    for r in ch.get("challenges") or []:
        parts.extend([r.get("reason") or "", r.get("required_fix") or "",
                      r.get("unable_reason") or ""])
    parts.append(ch.get("overall") or "")
    ev = evidence_obj or {}
    for r in ev.get("ratings") or []:
        parts.extend([r.get("decisive_gap") or "", r.get("source_key") or ""])
    parts.append(ev.get("summary") or "")
    v = verdict_obj or {}
    for r in v.get("rulings") or []:
        parts.extend([r.get("basis") or "", r.get("downgraded_wording") or "",
                      r.get("how_to_use") or ""])
    parts.extend([v.get("rationale") or "", v.get("summary") or ""])
    return "\n".join(x for x in parts if x)


def output_fields(claims_obj, challenge_obj, evidence_obj, verdict_obj):
    """产出里**逐个字段**的 (字段名, 值) 清单，供字段级占位空档判据使用。

    与 `output_prose` 的区别：散文是拼起来给人读的，字段级判据要的是
    「这一栏本身是不是空的」——两者判据不同，所以各有一份。
    """
    out = []
    c = claims_obj or {}
    out += [("claims.conclusion", c.get("conclusion") or "")]
    for x in c.get("claims") or []:
        out += [("claims.claims[{}].text".format(x.get("id")), x.get("text") or "")]
    for x in c.get("evidence") or []:
        out += [("claims.evidence[{}].name".format(x.get("id")), x.get("name") or "")]
    for r in (challenge_obj or {}).get("challenges") or []:
        out += [("challenge[{}].reason".format(r.get("target")), r.get("reason") or ""),
                ("challenge[{}].required_fix".format(r.get("target")),
                 r.get("required_fix") or "")]
    for r in (evidence_obj or {}).get("ratings") or []:
        out += [("evidence[{}].decisive_gap".format(r.get("claim_id")),
                 r.get("decisive_gap") or "")]
    for r in (verdict_obj or {}).get("rulings") or []:
        out += [("verdict[{}].basis".format(r.get("claim_id")), r.get("basis") or ""),
                ("verdict[{}].downgraded_wording".format(r.get("claim_id")),
                 r.get("downgraded_wording") or "")]
    return out


# ---------------------------------------------------------------------------
# 闸门总评估
# ---------------------------------------------------------------------------

def evaluate_gates(material, claims_obj, challenge_obj, evidence_obj, verdict_obj,
                   material_meta=None, allow_all_passed=False):
    """跑全部**本地**闸门，返回结构化结论。

    硬闸门 = compliance / placeholder / output_compliance / output_placeholder /
    prompt_echo / anchor / challenge（质疑有效性）/ downgrade（降级完整性）/
    strength（评级一致性）/ evidence（追认门）
    十项；材料侧与产出侧分开记，因为它们指向的处置完全不同
    （材料踩线 → 别证了；产出踩线 → 某个角色没按纪律写）。

    `allow_all_passed=True` 时，「质疑全放行」从硬闸门降级为标红
    （对应 `run --all-passed-ok`：确认材料本身无争议时才用；默认是硬闸门）。
    """
    hits_c, exempted = compliance_scan(material)
    mat_ph = placeholder_hits(material)
    prose = output_prose(claims_obj, challenge_obj, evidence_obj, verdict_obj)
    out_ph = placeholder_hits(prose) + field_placeholder_hits(output_fields(
        claims_obj, challenge_obj, evidence_obj, verdict_obj))
    out_fresh, out_quoted, out_mentioned, out_contextual, out_exempted = \
        compliance_scan_output(prose, material)
    out_echo, out_echo_skips = prompt_echo_scan(prose, label="产出")
    out_echo_skips = _dedupe_skips(out_echo_skips)

    recs, rules = collect_anchors(claims_obj, challenge_obj, verdict_obj)
    anchor = anchor_stat_for(recs)
    anchor["rules"] = rules
    if not anchor["ok"]:
        anchor["why"] = ("{} 条引文里 {} 条在对应文本里找不到（未锚定率 {:.0%} > {:.0%}）"
                         "——主张/挑战/裁决没有落到原文上，这份取证不可复核".format(
                             anchor["total"], anchor["unanchored"],
                             anchor["miss_rate"], ANCHOR_MAX_MISS))

    # ---- 闸门五：质疑有效性 ----
    ch = challenge_effective(challenge_obj, claims_obj)
    ch_problems, ch_red = list(ch["problems"]), list(ch["red_hints"])
    if ch_problems and allow_all_passed:
        for p in ch_problems:
            ch_red.append(p + "（已用 --all-passed-ok 降级为提示）")
        ch_problems = []
    ch_gate = {
        "ok": not ch_problems,
        "problems": ch_problems,
        "red_hints": ch_red,
        "red": bool(ch_problems) or bool(ch_red),
        "effective_count": ch["effective_count"],
        "passed_count": ch["passed_count"],
        "total_challenges": ch["total_challenges"],
        "types_used": ch["types_used"],
        "thresholds": ch["thresholds"],
        "note": ch["note"],
    }

    # ---- 闸门六：降级表述完整性 ----
    dg_ok, dg_problems, dg_red, dg_detail, dg_stat = downgrade_gate(
        verdict_obj, claims_obj, material)
    dg_gate = {"ok": dg_ok, "problems": dg_problems, "red_hints": dg_red,
               "red": bool(dg_problems) or bool(dg_red),
               "detail": dg_detail, "stats": dg_stat,
               "same_sim_threshold": DOWNGRADE_SAME_SIM,
               "note": ("判「降级表述」或「撤回」的主张必须给替代表述；"
                        "替代表述不能与原主张几乎同句、不许引入新材料没有的数字。")}

    # ---- 闸门七：评级口径一致性 ----
    st = strength_consistency(evidence_obj)
    st_gate = {"ok": st["ok"], "problems": st["problems"], "red_hints": st["red_hints"],
               "red": st["red"], "groups": st["groups"],
               "max_spread": st["max_spread"], "values": st["values"],
               "note": ("按 `source_key` 分组核对：同一类证据在不同主张上的评级"
                        "极差不得超过 {} 档".format(st["max_spread"]))}

    # ---- 追认门：证据强度 → 裁定档位 ----
    eg = evidence_gate(verdict_obj, evidence_obj)
    ev_gate = {"ok": eg["ok"], "problems": eg["problems"], "red_hints": eg["red_hints"],
               "red": eg["red"], "levels_by_claim": eg["levels_by_claim"],
               "note": eg["note"]}

    # ---- 未处置的被挑战主张（红） ----
    undecided = []
    ruled_ids = {r.get("claim_id") for r in (verdict_obj or {}).get("rulings") or []}
    for x in (challenge_obj or {}).get("challenges") or []:
        if (x.get("verdict") == CHALLENGE_VERDICT_CHALLENGED
                and x.get("target") not in ruled_ids):
            undecided.append(x.get("target"))
    if undecided:
        ch_gate["red_hints"] = list(ch_gate["red_hints"]) + [
            "有 {} 条被挑战成立的主张没有出现在裁决里：{}——不许装作没看见".format(
                len(undecided), "、".join(str(x) for x in undecided[:6]))]
        ch_gate["red"] = True

    gates = {
        "compliance": {"ok": not hits_c, "target": "待证材料", "hits": hits_c,
                       "exempted": exempted},
        "placeholder": {"ok": not mat_ph, "target": "待证材料", "hits": mat_ph},
        "output_compliance": {"ok": not out_fresh, "target": "主张/质疑/评级/裁决",
                              "hits": out_fresh, "quoted_from_material": out_quoted,
                              "mentioned_as_warning": out_mentioned,
                              "contextual_only": out_contextual, "exempted": out_exempted,
                              "rule": ("产出侧只查高风险条目，并排除两类正常写法："
                                       "材料里已有的词（引用被证对象）与"
                                       "小句里带禁止/撤回/举证类标记词的（提到而非主张）；"
                                       "中低风险项列在 contextual_only 里提示人工看，不拦")},
        "output_placeholder": {"ok": not out_ph, "target": "主张/质疑/评级/裁决",
                               "hits": out_ph},
        "prompt_echo": {"ok": not out_echo, "target": "主张/质疑/评级/裁决",
                        "hits": out_echo, "contain_skipped": out_echo_skips,
                        "window": {"max_ratio": ECHO_CONTAIN_MAX_RATIO,
                                   "min_sample": ECHO_CONTAIN_MIN_SAMPLE,
                                   "floor": ECHO_MIN_LEN_FLOOR}},
        "anchor": anchor,
        "challenge": ch_gate,
        "downgrade": dg_gate,
        "strength": st_gate,
        "evidence": ev_gate,
    }
    return gates


HARD_GATE_KEYS = ("compliance", "placeholder", "output_compliance", "output_placeholder",
                  "prompt_echo", "anchor", "challenge", "downgrade", "strength", "evidence")


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
        else:
            for p in (v.get("problems") or [])[:4]:
                lines.append("[{}] {}".format(k, p))
    return lines


# ---------------------------------------------------------------------------
# 渲染（人读文本）
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """命中标红。终端支持 ANSI 就打红色，否则用醒目前的 ✗ 前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "✗ " + s
    return "\x1b[31m{}\x1b[0m".format(s)


def render_roles_md():
    out = ["# 三剪客 · 调研取证小组：四个角色", "",
           "> 这不是四个「立场」，而是**同一件事的四个工序**：",
           "> 提主张 → 打漏洞 → 评强度 → 定边界。",
           "> 分歧不靠角色互相否掉对方，而靠**质疑方必须真的挑战掉一些主张**"
           "（闸门五）与**裁决必须给出可用的替代表述**（闸门六）。", ""]
    for i, r in enumerate(ROLES, 1):
        out.append("## 第 {} 道工序 · {}（`{}`）".format(i, r["name"], r["id"]))
        out.append("")
        out.append("- **目标**：{}".format(r["goal"]))
        out.append("- **天然倾向**：{}".format(r["bias"]))
        out.append("- **视角**：{}".format(r["question"]))
        out.append("- **权限**：{}".format(r["power"]))
        out.append("- **产出物**：{}".format(r["deliverable"]))
        out.append("- **盯的点**：")
        for x in r["focus"]:
            out.append("  - {}".format(x))
        out.append("")
    out.append("## 信息隔离发生在哪一步")
    out.append("")
    out.append("| 阶段 | 拿得到什么 | 拿不到什么 |")
    out.append("|---|---|---|")
    out.append("| `claims` | 材料全文 | — |")
    out.append("| `challenge` | 结论 + 主张原句（type）+ 证据**编号/名称/来源类型/时间** | "
               "主张方的 `reasoning`（推理过程）、证据的 `coverage`、其它角色任何文字 |")
    out.append("| `evidence` | 主张 + 证据条目 + 挑战记录 | 主张方的 `reasoning` |")
    out.append("| `verdict` | 主张 + 挑战 + 证据强度 | —（终裁要看全部） |")
    out.append("")
    out.append("零成本命令：`run.py roles`")
    return "\n".join(out)


def render_brief_md(brief, text):
    out = ["# 待证材料索引（本地整理，零调用）", ""]
    out.append("- 来源：{}".format(brief.get("source") or "（--file）"))
    out.append("- 篇幅：{} 字符（不含空白）· {} 句 · {} 段".format(
        brief["chars"], brief["sentences"], brief["paragraphs"]))
    out.append("- 内容摘要：`{}`".format((brief.get("sha") or "")[:16]))
    out.append("- ⚠️ **本包不联网检索**：下面的索引只是把材料里的东西摊开，不去外部查证。")
    out.append("")
    if brief["headings"]:
        out.append("## 大纲")
        out.append("")
        for h in brief["headings"]:
            out.append("{} {}".format("  " * (h["level"] - 1), h["text"]))
        out.append("")
    if brief["numbers"]:
        out.append("## 材料里的数字（{} 条，取证时最容易被「记错」的就是这类硬信息）".format(
            len(brief["numbers"])))
        out.append("")
        for n in brief["numbers"][:30]:
            out.append("- `{}` —— {}".format(n["raw"], n["context"]))
        out.append("")
    if brief["proper_nouns"]:
        out.append("## 专有名词（{} 条，粗筛）".format(len(brief["proper_nouns"])))
        out.append("")
        out.append("、".join("{}「{}」".format(p["kind"], p["raw"])
                            for p in brief["proper_nouns"][:30]))
        out.append("")
    pre = brief["local_prescan"]
    out.append("## 本地预扫（四个角色上场前先看这一栏）")
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
    out.append("## 四个角色要回答的问题")
    out.append("")
    for q in brief["crew_questions"]:
        out.append("- {}".format(q))
    out.append("")
    out.append("## 待证材料全文")
    out.append("")
    out.append(text or "")
    out.append("")
    return "\n".join(out)


def render_claims_md(claims_obj, anchor):
    out = ["# 主张清单（主张方）", ""]
    out.append("> 结论一句话 + 逐条可被单独挑战的主张 + 编号证据清单。")
    out.append("> `reasoning` 一栏**质疑方看不到**（信息隔离，见 challenge 阶段）。")
    out.append("")
    out.append("- **结论**：{}".format(claims_obj.get("conclusion") or "（未给出）"))
    out.append("- 主张 {} 条 · 已锚定 {} 条 · 未锚定 {} 条 · 证据 {} 条".format(
        len(claims_obj.get("claims") or []) + len(claims_obj.get("unanchored_claims") or []),
        anchor.get("verified"), anchor.get("unanchored"),
        len(claims_obj.get("evidence") or [])))
    out.append("")
    out.append("## 证据清单")
    out.append("")
    if claims_obj.get("evidence"):
        out.append("| 编号 | 名称 | 来源类型 | 时间 | 覆盖 |")
        out.append("|---|---|---|---|---|")
        for e in claims_obj["evidence"]:
            out.append("| {} | {} | {} | {} | {} |".format(
                e["id"], e.get("name") or "-", e.get("source_type") or "-",
                e.get("timeframe") or "-", (e.get("coverage") or "-")[:40]))
    else:
        out.append("（没有证据条目——这本身就是问题）")
    out.append("")
    out.append("## 主张逐条")
    out.append("")
    for c in claims_obj.get("claims") or []:
        line = "- **{}**（{}）{}".format(c["id"], c.get("claim_type") or "未标注",
                                        c.get("text") or "-")
        out.append(line)
        out.append("  - 依据证据：{}".format("、".join(c.get("evidence_ids") or []) or "（无）"))
        out.append("  - 材料原句（第 {} 句 / 锚点 {}）：{}".format(
            c.get("sent_no"), c.get("anchor_rule"), c.get("sentence") or c.get("quote") or "-"))
        if c.get("reasoning"):
            out.append("  - 推理（**质疑方看不到**）：{}".format(c["reasoning"]))
    out.append("")
    if claims_obj.get("unanchored_claims"):
        out.append("## 未通过锚点校验的主张（{} 条，**不进质疑方输入**）".format(
            len(claims_obj["unanchored_claims"])))
        out.append("")
        for c in claims_obj["unanchored_claims"]:
            out.append("- {}「{}」——{}".format(
                c.get("id"), (c.get("quote") or "")[:60], c.get("why_unverified") or ""))
        out.append("")
    if claims_obj.get("summary"):
        out.append("总评：{}".format(claims_obj["summary"]))
    return "\n".join(out)


def render_challenge_md(challenge_obj, gate, isolation):
    out = ["# 质疑书（质疑方）", ""]
    out.append("> 质疑方**看不到**主张方的推理过程，只看得到结论、主张原句与证据编号。")
    out.append("> 每条挑战必须指出**挑战类型**（{}）。".format("、".join(CHALLENGE_TYPES)))
    out.append("")
    out.append("- 挑战记录 {} 条 · **挑战成立 {} 条** · 放行 {} 条".format(
        gate.get("total_challenges"), gate.get("effective_count"),
        gate.get("passed_count")))
    out.append("- 用到的挑战类型：{}".format(
        "、".join(gate.get("types_used") or []) or "（无）"))
    if gate.get("effective_count"):
        out.append("- ✅ **这一轮真的挑战掉了主张**：这{}条成立".format(
            gate.get("effective_count")))
    else:
        out.append("- ✗ {}".format(_red(
            "一条挑战都没成立——**质疑没发生**（本包不把「全部放行」当成「证据充分」）",
            force_plain=True)))
    out.append("")
    out.append("| 主张 | 结论 | 类型 | 严重度 | 要求撤回 |")
    out.append("|---|---|---|---|---|")
    for r in challenge_obj.get("challenges") or []:
        out.append("| {} | {} | {} | {} | {} |".format(
            r.get("target"), r.get("verdict") or "未标注",
            r.get("challenge_type") or "**未标注**", r.get("severity") or "未标注",
            "是" if r.get("demand_retract") else ""))
    out.append("")
    for r in challenge_obj.get("challenges") or []:
        out.append("## 对 {}（{}）".format(r.get("target"),
                                        r.get("challenge_type") or "**未标注类型**"))
        out.append("")
        out.append("- 结论：**{}**（严重度 {}）".format(
            r.get("verdict") or "未标注", r.get("severity") or "未标注"))
        if r.get("quote"):
            out.append("- 被挑战的原句：{}".format(r["quote"]))
        if r.get("reason"):
            out.append("- 漏洞：{}".format(r["reason"]))
        if r.get("required_fix"):
            out.append("- 要求的补正：{}".format(r["required_fix"]))
        if r.get("unable_reason"):
            out.append("- 为什么挑不动：{}".format(r["unable_reason"]))
        if r.get("demand_retract"):
            out.append("- {}：**要求撤回**".format(_red("态度", force_plain=True)))
        out.append("")
    if challenge_obj.get("acknowledged"):
        out.append("## 质疑方明说「我挑不动」的主张")
        out.append("")
        out.append("- {}".format("、".join(challenge_obj["acknowledged"])))
        out.append("")
    if challenge_obj.get("rejected_challenges"):
        out.append("## 被本地校验剔出的挑战（{} 条）".format(
            len(challenge_obj["rejected_challenges"])))
        out.append("")
        for r in challenge_obj["rejected_challenges"]:
            out.append("- 对 {}：「{}」——{}".format(
                r.get("target"), (r.get("quote") or "")[:50], r.get("why_unverified") or ""))
        out.append("")
    if challenge_obj.get("overall"):
        out.append("总评：{}".format(challenge_obj["overall"]))
        out.append("")
    out.append("## 信息隔离证据")
    out.append("")
    out.append("| 项目 | 值 |")
    out.append("|---|---|")
    rec = (isolation or {}).get("challenge") or {}
    out.append("| 质疑方提示词字符数 | {} |".format(rec.get("prompt_chars")))
    out.append("| 提示词 SHA256(前 16) | {} |".format((rec.get("prompt_sha") or "")[:16]))
    out.append("| 提示词里出现的 `reasoning` 片段 | {} |".format(
        "、".join(rec.get("reasoning_fragments_found") or []) or "无"))
    out.append("| 提示词里是否含 `coverage` 栏 | {} |".format(
        "是" if rec.get("coverage_leaked") else "否"))
    out.append("")
    out.append("隔离说明：{}".format((isolation or {}).get("note") or ""))
    return "\n".join(out)


def render_evidence_md(evidence_obj, gate):
    out = ["# 证据强度评级（取证方）", ""]
    out.append("> 四档：强 / 中 / 弱 / 无据。**同一类证据必须用同一把尺子**——")
    out.append("> 本地按 `source_key` 分组核对，同组极差 > {} 档即判口径不一致。".format(
        gate.get("max_spread")))
    out.append("")
    out.append("| 主张 | 评级 | source_key | 形态 | 决定性缺口 |")
    out.append("|---|---|---|---|---|")
    for r in evidence_obj.get("ratings") or []:
        line = "| {} | {} | {} | {} | {} |".format(
            r.get("claim_id"), r.get("strength"),
            r.get("source_key") or "**未标注**", r.get("shape") or "-",
            (r.get("decisive_gap") or "-")[:60])
        out.append(line)
    out.append("")
    if gate.get("groups"):
        out.append("## 本地按 source_key 分组核对")
        out.append("")
        out.append("| 来源 key | 各主张上的评级 | 是否同尺子 |")
        out.append("|---|---|---|")
        bad_keys = set()
        for p in gate.get("problems") or []:
            for k in (gate.get("groups") or {}):
                if "「{}」".format(k) in p:
                    bad_keys.add(k)
        for k, lv in (gate.get("groups") or {}).items():
            out.append("| {} | {} | {} |".format(
                k, "、".join(lv), "✗ 极差超限" if k in bad_keys else "✅"))
        out.append("")
    for r in evidence_obj.get("ratings") or []:
        if r.get("strength_how") and r["strength_how"] != "原样":
            out.append("- {}：评级归一说明 —— {}".format(r.get("claim_id"),
                                                       r["strength_how"]))
    if evidence_obj.get("summary"):
        out.append("")
        out.append("总评：{}".format(evidence_obj["summary"]))
    return "\n".join(out)


def render_verdict_md(verdict_obj, claims_obj, gate, ev_gate):
    out = ["# 裁决：可采信边界（裁决方）", ""]
    out.append("> 裁定三档：可采信 / 降级表述 / 撤回。")
    out.append("> ⚠️ **判「降级表述」或「撤回」的必须给替代表述**——")
    out.append("> 只删不给替代会把稿子掏空，那是毁稿，不是裁决。")
    out.append("")
    counts = {}
    for r in verdict_obj.get("rulings") or []:
        counts[r.get("decision")] = counts.get(r.get("decision"), 0) + 1
    out.append("- 裁定 {} 条：{}".format(
        len(verdict_obj.get("rulings") or []),
        "、".join("{} {} 条".format(k, v) for k, v in counts.items()) or "（无）"))
    out.append("")
    for r in verdict_obj.get("rulings") or []:
        cid = r.get("claim_id")
        lvl = (ev_gate.get("levels_by_claim") or {}).get(cid) or "（无评级）"
        head = "## {} · {}（证据强度：{}）".format(cid, r.get("decision") or "未定档", lvl)
        if r.get("decision") == RULING_RETRACT:
            head = _red(head)
        out.append(head)
        out.append("")
        if r.get("basis"):
            out.append("- 依据：{}".format(r["basis"]))
        if r.get("basis_quote"):
            a = r.get("basis_anchor") or {}
            out.append("- 依据原句（锚点 {}）：{}".format(
                a.get("rule") or "-", a.get("sentence") or r["basis_quote"]))
        if r.get("downgraded_wording"):
            out.append("- **替代表述（可直接替换进稿子）**：{}".format(r["downgraded_wording"]))
        if r.get("how_to_use"):
            out.append("- 怎么用：{}".format(r["how_to_use"]))
        out.append("")
    if verdict_obj.get("rationale"):
        out.append("## 裁决理由")
        out.append("")
        out.append(verdict_obj["rationale"])
        out.append("")
    if verdict_obj.get("summary"):
        out.append("总评：{}".format(verdict_obj["summary"]))
    return "\n".join(out)


GATE_LABELS = {
    "compliance": "闸门一 合规（材料侧）",
    "placeholder": "闸门二 占位符残留（材料侧）",
    "output_compliance": "闸门一 合规（产出侧，口径不同）",
    "output_placeholder": "闸门二 占位符残留（产出侧）",
    "prompt_echo": "闸门三 照抄提示词示例",
    "anchor": "闸门四 锚点（主张/挑战/裁决依据）",
    "challenge": "闸门五 质疑有效性（本包核心）",
    "downgrade": "闸门六 降级表述完整性（本包核心）",
    "strength": "闸门七 评级口径一致性（本包特有）",
    "evidence": "闸门八 追认门（强度 → 裁定）",
}


def render_report_md(brief, claims_obj, challenge_obj, evidence_obj, verdict_obj,
                     gates, usage_dict, model, source, state_info=None):
    out = ["# 三剪客 · 调研取证小组 —— 总报告", ""]
    out.append("- 材料：`{}`（{} 字符 · {} 句）".format(
        source, brief["chars"], brief["sentences"]))
    out.append("- 模型：`{}`".format(model))
    out.append("- 工序：主张 → 质疑 → 取证 → 裁决（4 次调用）")
    out.append("- ⚠️ **本包只做本地推理与评级，不联网检索**："
               "证据在现实世界里是否真的存在，仍然要人来核。")
    out.append("")
    out.append("## 一句话结论")
    out.append("")
    out.append("> {}".format(claims_obj.get("conclusion") or "（主张方未给出结论）"))
    out.append("")
    cg = gates.get("challenge") or {}
    dg = gates.get("downgrade") or {}
    counts = {}
    for r in verdict_obj.get("rulings") or []:
        counts[r.get("decision")] = counts.get(r.get("decision"), 0) + 1
    out.append("## 结果速览")
    out.append("")
    out.append("| 项目 | 值 |")
    out.append("|---|---|")
    out.append("| 主张 | {} 条（另有 {} 条引文未锚定、未进质疑输入） |".format(
        len(claims_obj.get("claims") or []), len(claims_obj.get("unanchored_claims") or [])))
    out.append("| 证据条目 | {} 条 |".format(len(claims_obj.get("evidence") or [])))
    out.append("| 挑战记录 | {} 条，其中**挑战成立 {} 条** |".format(
        cg.get("total_challenges"), cg.get("effective_count")))
    out.append("| 挑战类型 | {} |".format("、".join(cg.get("types_used") or []) or "（无）"))
    out.append("| 裁定 | {} |".format(
        "、".join("{} {} 条".format(k, v) for k, v in counts.items()) or "（无）"))
    out.append("| **降级表述** | {} 条（判「降级表述 / 撤回」的主张里，给了替代表述的） |".format(
        sum(1 for r in (verdict_obj.get("rulings") or [])
            if r.get("downgraded_wording"))))
    out.append("")
    out.append("## 本地硬闸门（十项，确定性，可直接进 CI）")
    out.append("")
    out.append("| # | 闸门 | 结果 |")
    out.append("|---|---|---|")
    for k in HARD_GATE_KEYS:
        v = gates.get(k) or {}
        ok = v.get("ok", True)
        out.append("| {} | {} | {} |".format(
            HARD_GATE_KEYS.index(k) + 1, GATE_LABELS.get(k, k), "✅ 通过" if ok else "✗ **命中**"))
    out.append("")
    for k in HARD_GATE_KEYS:
        v = gates.get(k) or {}
        if v.get("ok", True):
            continue
        out.append("### ✗ {} 命中的原因".format(GATE_LABELS.get(k, k)))
        out.append("")
        for p in (v.get("problems") or [])[:8]:
            out.append("- {}".format(p))
        for h in (v.get("hits") or [])[:8]:
            out.append("- {}".format(h.get("why") or h))
        out.append("")
    reds = [(k, h) for k in HARD_GATE_KEYS for h in ((gates.get(k) or {}).get("red_hints") or [])]
    if reds:
        out.append("### 标红提示（不拦，但要看一眼）")
        out.append("")
        for k, h in reds[:12]:
            out.append("- [{}] {}".format(k, h))
        out.append("")
    out.append("## 主张清单")
    out.append("")
    out.append(render_claims_md(claims_obj, gates.get("anchor") or {}))
    out.append("")
    out.append("## 质疑书")
    out.append("")
    out.append(render_challenge_md(challenge_obj, cg, {}))
    out.append("")
    out.append("## 证据强度评级")
    out.append("")
    out.append(render_evidence_md(evidence_obj, gates.get("strength") or {}))
    out.append("")
    out.append("## 裁决：可采信边界")
    out.append("")
    out.append(render_verdict_md(verdict_obj, claims_obj, dg, gates.get("evidence") or {}))
    out.append("")
    out.append("## 本轮 token")
    out.append("")
    out.append("| 项 | 值 |")
    out.append("|---|---|")
    out.append("| 调用次数 | {} |".format(usage_dict.get("calls")))
    out.append("| prompt tokens | {} |".format(usage_dict.get("prompt_tokens")))
    out.append("| completion tokens | {} |".format(usage_dict.get("completion_tokens")))
    out.append("| **total tokens** | **{}** |".format(usage_dict.get("total_tokens")))
    out.append("")
    out.append("> 网关不公布文本单价，所以本报告**只报 token，不编金额**。")
    if state_info:
        out.append("")
        out.append("## 断点 key")
        out.append("")
        for k, v in state_info.items():
            out.append("- `{}`：`{}`".format(k, v))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# `--json` 契约
#
# 【不变量】stdout 永远只有一个 JSON。
#   · 成功               → 结果对象，含 "ok": true
#   · 闸门命中但结果已产出 → **结果对象本身**带 ok:false / exit:3 / gate_failed:true
#                          （不再另补错误信封，守住"只有一个 JSON"）
#   · 失败且结果未产出   → {"ok": false, "exit": <码>, "error": {"kind": …}}
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
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise UsageError("{} 不是合法 JSON（{}）：{}".format(what, exc, p))


def resolve_roles(spec):
    """把 `--roles a,b` 解析成角色定义列表；没给就用全部四道工序。

    本包的四道工序是**链条**（缺一环就没有下游输入），所以要求给全，
    不提供"只跑两个角色"的玩法——那样跑出来的不是取证。
    """
    if not spec:
        return list(ROLES)
    ids = [x.strip() for x in str(spec).split(",") if x.strip()]
    bad = [x for x in ids if x not in ROLE_BY_ID]
    if bad:
        raise UsageError("角色名不认识：{}。可用角色：{}".format(
            "、".join(bad), "、".join(ROLE_IDS)))
    missing = [x for x in ROLE_IDS if x not in ids]
    if missing:
        raise UsageError(
            "本包的四道工序是一条链（主张 → 质疑 → 取证 → 裁决），缺一环就没有下游输入。"
            "缺的角色：{}。要么全给，要么不给。".format("、".join(missing)))
    return [ROLE_BY_ID[x] for x in ROLE_IDS]


def roles_spec(roles):
    return ",".join(r["id"] for r in roles)


def material_meta(text):
    return {"chars": char_count(text), "sentences": len(split_sentences(text)),
            "sha": text_sha(text)}


def isolation_evidence(challenge_prompt, claims_obj):
    """challenge 阶段的信息隔离证据：**本地校验**推理过程有没有泄漏。

    做法：把主张方每一条 `reasoning` 切成 6 字以上的片段，看它们有没有
    出现在质疑方的提示词里；再看 `coverage` 栏的内容有没有被带进去。
    这比"看一眼提示词模板觉得没问题"可靠得多——模板改一行就可能漏。
    """
    frags_found = []
    for c in (claims_obj or {}).get("claims") or []:
        r = _norm_anchor(c.get("reasoning") or "")
        if len(r) < 6:
            continue
        # 取多段窗口（头、中、尾），单点取词容易漏（模型可能只抄了半句）
        wins = [r[i:i + 8] for i in range(0, max(1, len(r) - 8), 8)][:6]
        for w in wins:
            if len(w) >= 6 and w in _norm_anchor(challenge_prompt):
                frags_found.append({"claim_id": c.get("id"), "fragment": w})
                break
    leaked_cov = []
    for e in (claims_obj or {}).get("evidence") or []:
        cov = _norm_anchor(e.get("coverage") or "")
        if len(cov) >= 8 and cov[:12] in _norm_anchor(challenge_prompt):
            leaked_cov.append(e.get("id"))
    return {
        "challenge": {
            "prompt_chars": len(challenge_prompt),
            "prompt_sha": hashlib.sha256(challenge_prompt.encode("utf-8")).hexdigest(),
            "reasoning_fragments_found": frags_found,
            "coverage_leaked": leaked_cov,
            "reasoning_checked": sum(1 for c in (claims_obj or {}).get("claims") or []
                                     if len(_norm_anchor(c.get("reasoning") or "")) >= 6),
        },
        "note": ("challenge 阶段的提示词里只有：结论、主张原句、claim_type、"
                 "证据编号/名称/来源类型/时间。**不含**主张方的 `reasoning`"
                 "（推理过程），也不含证据的 `coverage`。"
                 "隔离是机制不是修辞：质疑方要对着「这句话凭什么被信」本身挑漏洞，"
                 "而不是顺着别人的论证往下补。"),
        "stage_inputs": {"claims": ["material"],
                         "challenge": ["claims.conclusion", "claims.claims.text",
                                       "claims.claims.claim_type",
                                       "claims.evidence.id/name/source_type/timeframe"],
                         "evidence": ["claims", "challenge"],
                         "verdict": ["claims", "challenge", "evidence"]},
    }


# ---------------------------------------------------------------------------
# 子命令：roles（零成本）
# ---------------------------------------------------------------------------

def run_roles(a):
    md = render_roles_md()
    body = {
        "command": "roles",
        "roles": ROLES,
        "role_ids": ROLE_IDS,
        "challenge_types": list(CHALLENGE_TYPES),
        "strength_levels": list(STRENGTH_LEVELS),
        "ruling_levels": list(RULING_ANY),
        "source_shapes": list(SOURCE_SHAPES),
        "why_evidentiary": [
            "四个角色是同一条链的四道工序，不是四个价值立场——链条缺一环就没有下游输入",
            "质疑方看不到主张方的推理过程（信息隔离），只挑战「这句话凭什么被信」",
            "本地不采信自报的挑战是否成立：一条都没成立就判「质疑无效」（闸门五）",
            "裁决必须给降级表述：只删不给替代会把稿子掏空（闸门六）",
            "⚠️ 本包只做本地推理与评级，**不联网检索**",
        ],
        "markdown": md,
    }
    if _json_out(body, a):
        return _after_out(a, md, "roles", obj=body)
    print(md)
    return _after_out(a, md, "roles", printed=True, obj=body)


# ---------------------------------------------------------------------------
# 子命令：claims（主张方，一次调用）
# ---------------------------------------------------------------------------

def run_claims(a):
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    target = AnchorTarget("material", "待证材料", text)
    brief = build_brief(text, a.file)

    if a.replay:
        raw = load_json(a.replay, "回放文件（claims 结果）")
        claims_obj = normalize_claims(raw.get("raw") or raw, target)
        note = "本次是 --replay：一次调用都没发，只做了本地归一化与锚点校验。"
        tracker = CostTracker()
    else:
        prompt = build_claims_prompt(text, meta)
        if a.dry_run:
            print("===== 主张方完整提示词开始 =====")
            print(prompt)
            print("===== 主张方完整提示词结束 =====")
            print("--dry-run：这一次调用**没有发出**，没有花任何点数。")
            return EXIT_OK
        tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
        sys.stderr.write("主张方：拆结论与支撑主张…\n")
        content, _usage = guarded_chat(
            prompt, tracker, "claims", system=CLAIM_SYSTEM.format(
                goal=ROLE_BY_ID["claimant"]["goal"], bias=ROLE_BY_ID["claimant"]["bias"]),
            model=a.model, temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
            json_mode=not a.no_json_mode)
        claims_obj = normalize_claims(parse_first_json(content), target)
        note = None

    recs = [True] * len(claims_obj.get("claims") or []) + \
           [False] * len(claims_obj.get("unanchored_claims") or [])
    anchor = anchor_stat_for(recs)
    anchor["rules"] = {}
    for c in claims_obj.get("claims") or []:
        r = c.get("anchor_rule") or "-"
        anchor["rules"][r] = anchor["rules"].get(r, 0) + 1
    body = {
        "command": "claims",
        "material": meta,
        "brief": {k: brief[k] for k in ("sha", "chars", "sentences", "numbers",
                                        "proper_nouns", "local_prescan")},
        "conclusion": claims_obj.get("conclusion"),
        "claims": claims_obj.get("claims"),
        "unanchored_claims": claims_obj.get("unanchored_claims"),
        "evidence": claims_obj.get("evidence"),
        "anchor": anchor,
        "summary": claims_obj.get("summary"),
        "raw": claims_obj.get("raw"),
        "usage": tracker.as_dict(),
        "note": note or ("主张方的 `reasoning` 会在下一阶段被**剔除**"
                         "（质疑方看不到推理过程）。"),
    }
    md = render_claims_md(claims_obj, anchor)
    if a.outdir:
        ensure_outside_pkg(a.outdir, "输出目录", "research-crew-out")
        write_json(Path(a.outdir) / "claims.json", body)
        write_text(Path(a.outdir) / "claims.md", md)
    sys.stderr.write(tracker.line() + "\n")
    if _json_out(body, a):
        return _after_out(a, md, "claims", obj=body)
    print(md)
    return _after_out(a, md, "claims", printed=True, obj=body)


def _after_out(a, md, name, printed=False, obj=None):
    """统一的 `--out` 落盘。

    **契约**：带 `--json` 时 `--out` 写的是**结果 JSON**（可以原样喂给下一个子命令，
    例如 `claims --json --out claims.json` 之后 `challenge --claims claims.json`）；
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


def _claims_from_file(obj):
    """从 claims.json 里取回主张清单（兼容 --out 写的完整结果对象）。"""
    if not isinstance(obj, dict):
        raise UsageError("claims 结果不是对象")
    if not isinstance(obj.get("claims"), list):
        raise UsageError("claims 结果里没有 claims 数组")
    return {"conclusion": obj.get("conclusion"), "claims": obj.get("claims"),
            "evidence": obj.get("evidence") or [],
            "unanchored_claims": obj.get("unanchored_claims") or [],
            "summary": obj.get("summary")}


# ---------------------------------------------------------------------------
# 子命令：challenge（质疑方，一次调用，信息隔离）
# ---------------------------------------------------------------------------

def run_challenge(a):
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    claims_obj = _claims_from_file(load_json(a.claims, "claims 结果"))

    if a.replay:
        raw = load_json(a.replay, "回放文件（challenge 结果）")
        prompt = build_challenge_prompt(claims_obj)
        challenge_obj = normalize_challenge(raw.get("raw") or raw, claims_obj,
                                           AnchorTarget("m", "材料", text))
        note = "本次是 --replay：一次调用都没发，只做了本地校验。"
        tracker = CostTracker()
    else:
        prompt = build_challenge_prompt(claims_obj)
        if a.dry_run:
            print("===== 质疑方完整提示词开始 =====")
            print(prompt)
            print("===== 质疑方完整提示词结束 =====")
            print("--dry-run：这一次调用**没有发出**，没有花任何点数。")
            return EXIT_OK
        tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
        sys.stderr.write("质疑方：逐条挑战（看不到主张方的推理过程）…\n")
        content, _usage = guarded_chat(
            prompt, tracker, "challenge", system=_CHALLENGE_SYSTEM.format(
                goal=ROLE_BY_ID["challenger"]["goal"],
                bias=ROLE_BY_ID["challenger"]["bias"],
                types=" / ".join(CHALLENGE_TYPES)),
            model=a.model, temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
            json_mode=not a.no_json_mode)
        challenge_obj = normalize_challenge(parse_first_json(content), claims_obj,
                                            AnchorTarget("m", "材料", text))
        note = None

    isolation = isolation_evidence(prompt, claims_obj)
    gate = challenge_effective(challenge_obj, {"claims": claims_obj.get("claims")})
    body = {
        "command": "challenge",
        "material": meta,
        "challenges": challenge_obj.get("challenges"),
        "rejected_challenges": challenge_obj.get("rejected_challenges"),
        "acknowledged": challenge_obj.get("acknowledged"),
        "overall": challenge_obj.get("overall"),
        "effective": gate["effective"],
        "effective_count": gate["effective_count"],
        "passed_count": gate["passed_count"],
        "types_used": gate["types_used"],
        "isolation": isolation,
        "gate_preview": {"ok": gate["ok"], "problems": gate["problems"],
                         "red_hints": gate["red_hints"]},
        "raw": challenge_obj.get("raw"),
        "usage": tracker.as_dict(),
        "note": note or ("质疑方只拿得到结论、主张原句与证据编号/名称/来源类型；"
                         "`reasoning` 与 `coverage` 都被剔除（见 isolation 证据）。"),
    }
    md = render_challenge_md(challenge_obj, gate, isolation)
    if a.outdir:
        ensure_outside_pkg(a.outdir, "输出目录", "research-crew-out")
        write_json(Path(a.outdir) / "challenge.json", body)
        write_text(Path(a.outdir) / "challenge.md", md)
    rec = isolation.get("challenge") or {}
    if rec.get("reasoning_fragments_found"):
        sys.stderr.write("⚠️ 隔离检查：质疑方提示词里出现了 {} 段 `reasoning` 片段\n".format(
            len(rec["reasoning_fragments_found"])))
    else:
        sys.stderr.write("隔离检查：质疑方提示词里没有任何 `reasoning` 片段（已核对 {} 条推理）。\n"
                         .format(rec.get("reasoning_checked")))
    sys.stderr.write("挑战成立 {} 条 / 记录 {} 条。\n".format(
        gate["effective_count"], gate["total_challenges"]))
    sys.stderr.write(tracker.line() + "\n")
    if _json_out(body, a):
        return _after_out(a, md, "challenge", obj=body)
    print(md)
    return _after_out(a, md, "challenge", printed=True, obj=body)


# ---------------------------------------------------------------------------
# 子命令：evidence（取证方，一次调用）
# ---------------------------------------------------------------------------

def _challenge_from_file(obj):
    if not isinstance(obj, dict):
        raise UsageError("challenge 结果不是对象")
    if not isinstance(obj.get("challenges"), list):
        raise UsageError("challenge 结果里没有 challenges 数组")
    return {"challenges": obj.get("challenges"),
            "acknowledged": obj.get("acknowledged") or [],
            "overall": obj.get("overall")}


def run_evidence(a):
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    claims_obj = _claims_from_file(load_json(a.claims, "claims 结果"))
    challenge_obj = _challenge_from_file(load_json(a.challenge, "challenge 结果"))

    if a.replay:
        raw = load_json(a.replay, "回放文件（evidence 结果）")
        evidence_obj = normalize_evidence(raw.get("raw") or raw, claims_obj)
        note = "本次是 --replay：一次调用都没发，只做了本地归一化。"
        tracker = CostTracker()
    else:
        prompt = build_evidence_prompt(claims_obj, challenge_obj)
        if a.dry_run:
            print("===== 取证方完整提示词开始 =====")
            print(prompt)
            print("===== 取证方完整提示词结束 =====")
            print("--dry-run：这一次调用**没有发出**，没有花任何点数。")
            return EXIT_OK
        tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
        sys.stderr.write("取证方：给每条主张评证据强度…\n")
        content, _usage = guarded_chat(
            prompt, tracker, "evidence", system=EVIDENCE_SYSTEM.format(
                goal=ROLE_BY_ID["evidence"]["goal"],
                bias=ROLE_BY_ID["evidence"]["bias"],
                shapes=_fmt_shapes()),
            model=a.model, temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
            json_mode=not a.no_json_mode)
        evidence_obj = normalize_evidence(parse_first_json(content), claims_obj)
        note = None

    gate = strength_consistency(evidence_obj)
    body = {
        "command": "evidence",
        "material": meta,
        "ratings": evidence_obj.get("ratings"),
        "summary": evidence_obj.get("summary"),
        "groups": gate["groups"],
        "gate_preview": {"ok": gate["ok"], "problems": gate["problems"],
                         "red_hints": gate["red_hints"]},
        "raw": evidence_obj.get("raw"),
        "usage": tracker.as_dict(),
        "note": note or ("同一类证据在不同主张上必须用同一把尺子："
                         "本地按 source_key 分组，同组极差 > {} 档即判口径不一致。"
                         .format(STRENGTH_MAX_SPREAD)),
    }
    md = render_evidence_md(evidence_obj, gate)
    if a.outdir:
        ensure_outside_pkg(a.outdir, "输出目录", "research-crew-out")
        write_json(Path(a.outdir) / "evidence.json", body)
        write_text(Path(a.outdir) / "evidence.md", md)
    sys.stderr.write("评级口径：{} 组，{}。\n".format(
        len(gate["groups"]), "一致" if gate["ok"] else "**不一致**"))
    sys.stderr.write(tracker.line() + "\n")
    if _json_out(body, a):
        return _after_out(a, md, "evidence", obj=body)
    print(md)
    return _after_out(a, md, "evidence", printed=True, obj=body)


# ---------------------------------------------------------------------------
# 子命令：verdict（裁决方，一次调用）
# ---------------------------------------------------------------------------

def _evidence_from_file(obj):
    if not isinstance(obj, dict):
        raise UsageError("evidence 结果不是对象")
    if not isinstance(obj.get("ratings"), list):
        raise UsageError("evidence 结果里没有 ratings 数组")
    return {"ratings": obj.get("ratings"), "summary": obj.get("summary")}


def run_verdict(a):
    check_cost_opts(a)
    text = read_text(a.file)
    meta = material_meta(text)
    target = AnchorTarget("material", "待证材料", text)
    claims_obj = _claims_from_file(load_json(a.claims, "claims 结果"))
    challenge_obj = _challenge_from_file(load_json(a.challenge, "challenge 结果"))
    evidence_obj = _evidence_from_file(load_json(a.evidence, "evidence 结果"))

    if a.replay:
        raw = load_json(a.replay, "回放文件（verdict 结果）")
        verdict_obj = normalize_verdict(raw.get("raw") or raw, claims_obj, target)
        note = "本次是 --replay：一次调用都没发，只做了本地归一化与锚点校验。"
        tracker = CostTracker()
    else:
        prompt = build_verdict_prompt(claims_obj, challenge_obj, evidence_obj)
        if a.dry_run:
            print("===== 裁决方完整提示词开始 =====")
            print(prompt)
            print("===== 裁决方完整提示词结束 =====")
            print("--dry-run：这一次调用**没有发出**，没有花任何点数。")
            return EXIT_OK
        tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
        sys.stderr.write("裁决方：定可采信边界与降级表述…\n")
        content, _usage = guarded_chat(
            prompt, tracker, "verdict", system=ARBITER_SYSTEM.format(
                goal=ROLE_BY_ID["arbiter"]["goal"], bias=ROLE_BY_ID["arbiter"]["bias"]),
            model=a.model, temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
            json_mode=not a.no_json_mode)
        verdict_obj = normalize_verdict(parse_first_json(content), claims_obj, target)
        note = None

    dg_ok, dg_problems, dg_red, dg_detail, dg_stat = downgrade_gate(
        verdict_obj, {"claims": claims_obj.get("claims")}, text)
    ev_gate = evidence_gate(verdict_obj, {"ratings": evidence_obj.get("ratings")})
    body = {
        "command": "verdict",
        "material": meta,
        "rulings": verdict_obj.get("rulings"),
        "accepted": verdict_obj.get("accepted"),
        "downgraded": verdict_obj.get("downgraded"),
        "retracted": verdict_obj.get("retracted"),
        "rationale": verdict_obj.get("rationale"),
        "summary": verdict_obj.get("summary"),
        "downgrade": {"ok": dg_ok, "problems": dg_problems, "red_hints": dg_red,
                      "detail": dg_detail, "stats": dg_stat},
        "evidence_consistency": {"ok": ev_gate["ok"], "problems": ev_gate["problems"],
                                 "levels_by_claim": ev_gate["levels_by_claim"]},
        "raw": verdict_obj.get("raw"),
        "usage": tracker.as_dict(),
        "note": note or ("判「降级表述」或「撤回」的主张必须给替代表述；"
                         "本地会核对替代表述是否与原句几乎同句、"
                         "是否引入了材料里没有的新数字。"),
    }
    md = render_verdict_md(verdict_obj, claims_obj, {"detail": dg_detail}, ev_gate)
    if a.outdir:
        ensure_outside_pkg(a.outdir, "输出目录", "research-crew-out")
        write_json(Path(a.outdir) / "verdict.json", body)
        write_text(Path(a.outdir) / "verdict.md", md)
    n_alt = sum(1 for r in verdict_obj.get("rulings") or [] if r.get("downgraded_wording"))
    n_need = dg_stat.get("need_alt") or 0
    sys.stderr.write("裁定 {} 条 · 判「不能采信」{} 条 · 给了替代表述 {} 条。\n".format(
        len(verdict_obj.get("rulings") or []), n_need, n_alt))
    sys.stderr.write(tracker.line() + "\n")
    if _json_out(body, a):
        return _after_out(a, md, "verdict", obj=body)
    print(md)
    return _after_out(a, md, "verdict", printed=True, obj=body)


# ---------------------------------------------------------------------------
# 子命令：run（一条命令跑完，断点续跑）
# ---------------------------------------------------------------------------

def run_run(a):
    check_cost_opts(a)
    text = read_text(a.file)
    roles = resolve_roles(getattr(a, "roles", None))
    meta = material_meta(text)
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir, "输出目录", "research-crew-out")
    outdir.mkdir(parents=True, exist_ok=True)
    if a.out:
        ensure_outside_pkg(a.out, "输出文件", "run-out.json")

    brief = build_brief(text, a.file)
    write_json(outdir / "brief.json", brief)
    write_text(outdir / "brief.md", render_brief_md(brief, text))

    tracker = CostTracker(budget=a.budget, price_in=a.price_in, price_out=a.price_out)
    state = load_state(outdir)
    prompt_chars = meta["chars"]
    rspec = roles_spec(roles)
    state_info = {}
    target = AnchorTarget("material", "待证材料", text)
    calls = []

    # ---- claims ----
    base_claims = dict(source_sha=meta["sha"], source_chars=meta["chars"],
                       prompt_chars=prompt_chars, model=a.model, temperature=a.temperature,
                       roles=rspec, role_count=len(roles))
    k_claims, k_claims_all = _resume_key("claims", state, base_claims)
    state_info["claims"] = k_claims
    state_info["claims_candidates"] = k_claims_all
    claims_path = outdir / "claims.json"
    claims_body = None
    # 断点判定：文件在 + 这个 key 记过 done。回放与正常跑共用同一套 key（见 _resume_key）。
    if claims_path.is_file() and state["entries"].get(k_claims) == "done" and not a.force:
        claims_body = load_json(claims_path, "claims 结果")
        sys.stderr.write("claims：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        rb = load_json(Path(a.replay) / "claims.json", "回放目录里的 claims 结果")
        claims_obj = normalize_claims(rb.get("raw") or rb, target)
        claims_body = _pack_claims(claims_obj, meta, brief, CostTracker(), None)
        sys.stderr.write("claims：--replay 命中，跳过模型调用（锚点已本地重算）。\n")
        # ⚠️ **必须回写规范产物**（只在内存里重建不够）：正常跑时"上一阶段产物摘要"
        # 读的是 outdir 里这份文件；回放若不留下来，下次正常跑算出的 `claims_sha`
        # 就与回放那次对不上 —— 断点不命中，用户又付一次钱。
        # 这里与正常跑写的是同一份 `_pack_*` 结构，序列化一致；
        # `_resume_key` 的双算兜底只作为额外保险。
        write_json(claims_path, claims_body)
        write_text(outdir / "claims.md",
                   render_claims_md(claims_obj, claims_body["anchor"]))
        # ⚠️ 回放也必须记断点。事故复盘（本包自测时真踩到）：第一版没记，
        # 于是「--replay 用真实产物重跑一遍闸门」之后再正常跑一次，
        # 断点不命中，**又付了 4 次调用的钱** —— 用户以为回放过的阶段不用再花钱。
        state["entries"][k_claims] = "done"
        save_state(outdir, state)
    else:
        prompt = build_claims_prompt(text, meta)
        if a.dry_run:
            print("===== 主张方提示词开始 =====")
            print(prompt)
            print("===== 主张方提示词结束 =====")
            print("--dry-run：本次 run 的主张方调用**没有发出**。"
                  "下游提示词依赖上一阶段产出，无法在 dry-run 里预演。")
            return EXIT_OK
        mark = len(tracker.log)
        sys.stderr.write("主张方：拆结论与支撑主张…\n")
        content, usage = guarded_chat(
            prompt, tracker, "claims", system=CLAIM_SYSTEM.format(
                goal=ROLE_BY_ID["claimant"]["goal"], bias=ROLE_BY_ID["claimant"]["bias"]),
            model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
            key=a.key, json_mode=not a.no_json_mode)
        calls.append({"stage": "claims", "usage": usage})
        claims_obj = normalize_claims(parse_first_json(content), target)
        claims_body = _pack_claims(claims_obj, meta, brief, tracker, mark)
        write_json(claims_path, claims_body)
        write_text(outdir / "claims.md", render_claims_md(claims_obj, claims_body["anchor"]))
        state["entries"][k_claims] = "done"
        save_state(outdir, state)

    claims_obj = _claims_from_file(claims_body)

    # ---- challenge ----
    k_challenge, k_ch_all = _resume_key(
        "challenge", state, dict(base_claims, claims_sha=json_sha(claims_body)),
        falls=[dict(claims_sha=json_sha(_read_json_or_none(claims_path)))]
        if claims_path.is_file() else [])
    state_info["challenge"] = k_challenge
    state_info["challenge_candidates"] = k_ch_all
    ch_path = outdir / "challenge.json"
    challenge_body = None
    if ch_path.is_file() and state["entries"].get(k_challenge) == "done" and not a.force:
        challenge_body = load_json(ch_path, "challenge 结果")
        sys.stderr.write("challenge：断点命中，跳过（0 次调用）。\n")
    else:
        prompt = build_challenge_prompt(claims_obj)
        isolation = isolation_evidence(prompt, claims_obj)
        if a.replay:
            rb = load_json(Path(a.replay) / "challenge.json", "回放目录里的 challenge 结果")
            challenge_obj = normalize_challenge(rb.get("raw") or rb, claims_obj, target)
            challenge_body = _pack_challenge(challenge_obj, claims_obj, meta, isolation,
                                             CostTracker(), None)
            sys.stderr.write("challenge：--replay 命中，跳过模型调用（本地校验已重算）。\n")
        else:
            mark = len(tracker.log)
            sys.stderr.write("质疑方：逐条挑战（看不到主张方的推理过程）…\n")
            content, usage = guarded_chat(
                prompt, tracker, "challenge", system=_CHALLENGE_SYSTEM.format(
                    goal=ROLE_BY_ID["challenger"]["goal"],
                    bias=ROLE_BY_ID["challenger"]["bias"],
                    types=" / ".join(CHALLENGE_TYPES)),
                model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
                key=a.key, json_mode=not a.no_json_mode)
            calls.append({"stage": "challenge", "usage": usage})
            challenge_obj = normalize_challenge(parse_first_json(content), claims_obj, target)
            challenge_body = _pack_challenge(challenge_obj, claims_obj, meta, isolation,
                                             tracker, mark)
        write_json(ch_path, challenge_body)
        write_text(outdir / "challenge.md", render_challenge_md(
            challenge_obj, challenge_effective(challenge_obj, claims_obj), isolation))
        state["entries"][k_challenge] = "done"
        save_state(outdir, state)
        sys.stderr.write("挑战成立 {} 条 / 记录 {} 条。\n".format(
            challenge_body.get("effective_count"),
            len(challenge_body.get("challenges") or [])))

    challenge_obj = _challenge_from_file(challenge_body)

    # ---- evidence ----
    k_evidence, k_ev_all = _resume_key(
        "evidence", state,
        dict(base_claims, claims_sha=json_sha(claims_body),
             challenge_sha=json_sha(challenge_body)),
        falls=[dict(claims_sha=json_sha(claims_body),
                    challenge_sha=json_sha(_read_json_or_none(ch_path)))]
        if ch_path.is_file() else [])
    state_info["evidence"] = k_evidence
    state_info["evidence_candidates"] = k_ev_all

    ev_path = outdir / "evidence.json"
    evidence_body = None
    if ev_path.is_file() and state["entries"].get(k_evidence) == "done" and not a.force:
        evidence_body = load_json(ev_path, "evidence 结果")
        sys.stderr.write("evidence：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        rb = load_json(Path(a.replay) / "evidence.json", "回放目录里的 evidence 结果")
        evidence_obj = normalize_evidence(rb.get("raw") or rb, claims_obj)
        evidence_body = _pack_evidence(evidence_obj, meta, CostTracker(), None)
        sys.stderr.write("evidence：--replay 命中，跳过模型调用（本地归一化已重做）。\n")
        write_json(ev_path, evidence_body)
        write_text(outdir / "evidence.md", render_evidence_md(
            evidence_obj, strength_consistency(evidence_obj)))
        state["entries"][k_evidence] = "done"
        save_state(outdir, state)
    else:
        prompt = build_evidence_prompt(claims_obj, challenge_obj)
        mark = len(tracker.log)
        sys.stderr.write("取证方：给每条主张评证据强度…\n")
        content, usage = guarded_chat(
            prompt, tracker, "evidence", system=EVIDENCE_SYSTEM.format(
                goal=ROLE_BY_ID["evidence"]["goal"],
                bias=ROLE_BY_ID["evidence"]["bias"], shapes=_fmt_shapes()),
            model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
            key=a.key, json_mode=not a.no_json_mode)
        calls.append({"stage": "evidence", "usage": usage})
        evidence_obj = normalize_evidence(parse_first_json(content), claims_obj)
        evidence_body = _pack_evidence(evidence_obj, meta, tracker, mark)
        write_json(ev_path, evidence_body)
        write_text(outdir / "evidence.md", render_evidence_md(
            evidence_obj, strength_consistency(evidence_obj)))
        state["entries"][k_evidence] = "done"
        save_state(outdir, state)

    evidence_obj = _evidence_from_file(evidence_body)

    # ---- verdict ----
    k_verdict, k_vd_all = _resume_key(
        "verdict", state,
        dict(base_claims, claims_sha=json_sha(claims_body),
             challenge_sha=json_sha(challenge_body),
             evidence_sha=json_sha(evidence_body)),
        falls=[dict(claims_sha=json_sha(claims_body),
                    challenge_sha=json_sha(challenge_body),
                    evidence_sha=json_sha(_read_json_or_none(ev_path)))]
        if ev_path.is_file() else [])
    state_info["verdict"] = k_verdict
    state_info["verdict_candidates"] = k_vd_all
    v_path = outdir / "verdict.json"
    verdict_body = None
    if v_path.is_file() and state["entries"].get(k_verdict) == "done" and not a.force:
        verdict_body = load_json(v_path, "verdict 结果")
        sys.stderr.write("verdict：断点命中，跳过（0 次调用）。\n")
    elif a.replay:
        rb = load_json(Path(a.replay) / "verdict.json", "回放目录里的 verdict 结果")
        verdict_obj = normalize_verdict(rb.get("raw") or rb, claims_obj, target)
        verdict_body = _pack_verdict(verdict_obj, meta, CostTracker(), None)
        sys.stderr.write("verdict：--replay 命中，跳过模型调用（本地校验已重算）。\n")
        write_json(v_path, verdict_body)
        write_text(outdir / "verdict.md", render_verdict_md(
            verdict_obj, claims_obj, {},
            evidence_gate(verdict_obj, {"ratings": evidence_obj.get("ratings")})))
        state["entries"][k_verdict] = "done"
        save_state(outdir, state)
    else:
        prompt = build_verdict_prompt(claims_obj, challenge_obj, evidence_obj)
        mark = len(tracker.log)
        sys.stderr.write("裁决方：定可采信边界与降级表述…\n")
        content, usage = guarded_chat(
            prompt, tracker, "verdict", system=ARBITER_SYSTEM.format(
                goal=ROLE_BY_ID["arbiter"]["goal"], bias=ROLE_BY_ID["arbiter"]["bias"]),
            model=a.model, temperature=a.temperature, max_tokens=a.max_tokens,
            key=a.key, json_mode=not a.no_json_mode)
        calls.append({"stage": "verdict", "usage": usage})
        verdict_obj = normalize_verdict(parse_first_json(content), claims_obj, target)
        verdict_body = _pack_verdict(verdict_obj, meta, tracker, mark)
        write_json(v_path, verdict_body)
        write_text(outdir / "verdict.md", render_verdict_md(
            verdict_obj, claims_obj, {},
            evidence_gate(verdict_obj, {"ratings": evidence_obj.get("ratings")})))
        state["entries"][k_verdict] = "done"
        save_state(outdir, state)

    verdict_obj = {"rulings": verdict_body.get("rulings"),
                   "accepted": verdict_body.get("accepted"),
                   "downgraded": verdict_body.get("downgraded"),
                   "retracted": verdict_body.get("retracted"),
                   "rationale": verdict_body.get("rationale"),
                   "summary": verdict_body.get("summary")}

    # ---- 闸门 + 报告 ----
    gates = evaluate_gates(text, claims_obj, challenge_obj, evidence_obj, verdict_obj, meta,
                           allow_all_passed=bool(getattr(a, "all_passed_ok", False)))
    if tracker.calls:
        usage_dict = tracker.as_dict()
    else:
        usage_dict = _merge_stage_usage([claims_body, challenge_body, evidence_body,
                                         verdict_body], tracker)
    report = render_report_md(brief, claims_obj, challenge_obj, evidence_obj, verdict_obj,
                              gates, usage_dict, a.model, a.file, state_info)
    write_text(outdir / "REPORT.md", report)
    log_obj = _build_log(claims_obj, challenge_obj, evidence_obj, verdict_obj, gates,
                         usage_dict, a.file, str(outdir))
    write_json(outdir / "log.json", log_obj)

    for p in gate_summary_lines(gates):
        sys.stderr.write("闸门命中：" + p + "\n")
    bad = [k for k in HARD_GATE_KEYS if not (gates.get(k) or {}).get("ok", True)]
    if bad:
        sys.stderr.write("本地闸门命中 {} 项：{}（详见 {}/REPORT.md）\n".format(
            len(bad), "、".join(GATE_LABELS.get(k, k) for k in bad), outdir))
    else:
        sys.stderr.write("本地闸门：十项全部通过。\n")
    sys.stderr.write(tracker.line() + "\n" if tracker.calls else
                     "本次是断点续跑 / 回放：{} 次调用。\n".format(tracker.calls))
    cg = gates.get("challenge") or {}
    sys.stderr.write("本包核心：挑战成立 {} 条 / 记录 {} 条 · 降级表述 {} 条。\n".format(
        cg.get("effective_count"), cg.get("total_challenges"),
        sum(1 for r in verdict_obj.get("rulings") or [] if r.get("downgraded_wording"))))

    body = {
        "command": "run",
        "material": meta,
        "brief": {"sha": brief["sha"], "chars": brief["chars"],
                  "headings": len(brief["headings"]), "numbers": len(brief["numbers"])},
        "conclusion": claims_obj.get("conclusion"),
        "claims": claims_obj.get("claims"),
        "evidence_items": claims_obj.get("evidence"),
        "challenges": challenge_obj.get("challenges"),
        "challenge_effective_count": cg.get("effective_count"),
        "challenge_types_used": cg.get("types_used"),
        "ratings": evidence_obj.get("ratings"),
        "rulings": verdict_obj.get("rulings"),
        "accepted": verdict_obj.get("accepted"),
        "downgraded": verdict_obj.get("downgraded"),
        "retracted": verdict_obj.get("retracted"),
        "rationale": verdict_obj.get("rationale"),
        "isolation": challenge_body.get("isolation"),
        "gates": gates,
        "gate_failed": gate_failed(gates),
        "exit": (EXIT_GATE if bad else EXIT_OK),
        "usage": usage_dict,
        "state_key": state_info,
        "outdir": str(outdir),
        "files": ["brief.json", "brief.md", "claims.json", "claims.md",
                  "challenge.json", "challenge.md", "evidence.json", "evidence.md",
                  "verdict.json", "verdict.md", "REPORT.md", "log.json", "state.json"],
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
            len(bad), "、".join(GATE_LABELS.get(k, k) for k in bad)))
    return EXIT_OK


def _pack_claims(claims_obj, meta, brief, tracker, mark):
    anchor = anchor_stat_for(
        [True] * len(claims_obj.get("claims") or [])
        + [False] * len(claims_obj.get("unanchored_claims") or []))
    anchor["rules"] = {}
    for c in claims_obj.get("claims") or []:
        r = c.get("anchor_rule") or "-"
        anchor["rules"][r] = anchor["rules"].get(r, 0) + 1
    return {
        "command": "claims",
        "material": meta,
        "brief": {k: brief[k] for k in ("sha", "chars", "sentences", "numbers",
                                        "proper_nouns", "local_prescan")},
        "conclusion": claims_obj.get("conclusion"),
        "claims": claims_obj.get("claims"),
        "unanchored_claims": claims_obj.get("unanchored_claims"),
        "evidence": claims_obj.get("evidence"),
        "anchor": anchor,
        "summary": claims_obj.get("summary"),
        "raw": claims_obj.get("raw"),
        "usage": (_stage_usage(tracker, mark) if mark is not None
                  else {"replayed": True, "calls": 0, "prompt_tokens": 0,
                        "completion_tokens": 0, "total_tokens": 0, "usage_log": []}),
        "note": "主张方的 `reasoning` 会在下一阶段被剔除（质疑方看不到推理过程）。",
    }


def _pack_challenge(challenge_obj, claims_obj, meta, isolation, tracker, mark):
    gate = challenge_effective(challenge_obj, claims_obj)
    return {
        "command": "challenge",
        "material": meta,
        "challenges": challenge_obj.get("challenges"),
        "rejected_challenges": challenge_obj.get("rejected_challenges"),
        "acknowledged": challenge_obj.get("acknowledged"),
        "overall": challenge_obj.get("overall"),
        "effective": gate["effective"],
        "effective_count": gate["effective_count"],
        "passed_count": gate["passed_count"],
        "types_used": gate["types_used"],
        "isolation": isolation,
        "raw": challenge_obj.get("raw"),
        "usage": (_stage_usage(tracker, mark) if mark is not None
                  else {"replayed": True, "calls": 0, "prompt_tokens": 0,
                        "completion_tokens": 0, "total_tokens": 0, "usage_log": []}),
        "note": "质疑方只拿得到结论、主张原句与证据编号/名称/来源类型（见 isolation 证据）。",
    }


def _pack_evidence(evidence_obj, meta, tracker, mark):
    gate = strength_consistency(evidence_obj)
    return {
        "command": "evidence",
        "material": meta,
        "ratings": evidence_obj.get("ratings"),
        "summary": evidence_obj.get("summary"),
        "groups": gate["groups"],
        "raw": evidence_obj.get("raw"),
        "usage": (_stage_usage(tracker, mark) if mark is not None
                  else {"replayed": True, "calls": 0, "prompt_tokens": 0,
                        "completion_tokens": 0, "total_tokens": 0, "usage_log": []}),
        "note": "同一类证据必须用同一把尺子（按 source_key 分组核对）。",
    }


def _pack_verdict(verdict_obj, meta, tracker, mark):
    return {
        "command": "verdict",
        "material": meta,
        "rulings": verdict_obj.get("rulings"),
        "accepted": verdict_obj.get("accepted"),
        "downgraded": verdict_obj.get("downgraded"),
        "retracted": verdict_obj.get("retracted"),
        "rationale": verdict_obj.get("rationale"),
        "summary": verdict_obj.get("summary"),
        "raw": verdict_obj.get("raw"),
        "usage": (_stage_usage(tracker, mark) if mark is not None
                  else {"replayed": True, "calls": 0, "prompt_tokens": 0,
                        "completion_tokens": 0, "total_tokens": 0, "usage_log": []}),
        "note": "判「降级表述」或「撤回」的主张必须给替代表述。",
    }


def _stage_usage(tracker, start):
    """把 tracker.log[start:] 这一段调用整理成一个阶段 usage 记录。

    为什么要按阶段切：`run` 一共四道工序，断点续跑时可能只有一部分真的调用了模型。
    阶段各自的 usage 记在各自产物里，汇总时相加不会重复计数。
    token 全部来自网关返回的真实 usage，没有任何估算值混在里面。
    """
    log = tracker.log[start:]
    p = sum(x.get("prompt_tokens") or 0 for x in log)
    c = sum(x.get("completion_tokens") or 0 for x in log)
    return {"calls": len(log), "prompt_tokens": p, "completion_tokens": c,
            "total_tokens": p + c, "usage_log": log,
            "finish_reasons": [x.get("finish_reason") for x in log]}



def _resume_key(stage, state, base_kw, falls=()):
    """断点 key 的**双算兜底**。

    事故复盘（本包自测时真踩到）：`--replay` 会把上一阶段的产物在本地重算一遍
    （这是设计：回放要重跑本地校验），而重算后的序列化与原始产物可能差几个字节 ——
    于是下游的 `json_sha` 变了，**断点不命中，用户又付一次钱**。
    真机实测：同一次运行，回放的 challenge key 与正常跑的 challenge key 不同名。

    处置：先按当下这份产物算 key；**不命中就再按上一份产物摘要算一次**。
    两条都查，命中就用 —— 既保留"产物变了要重跑"的语义（摘要仍在 key 里），
    又不会因为回放导致的序列化漂移而白花钱。
    """
    keys = [state_key(stage, **base_kw)]
    for fb in falls:
        kw = dict(base_kw)
        kw.update(fb)
        keys.append(state_key(stage, **kw))
    for k in keys:
        if state["entries"].get(k) == "done":
            return k, keys
    return keys[0], keys


def _read_json_or_none(path):
    """读 JSON；读不到返回 None（断点兜底用，坏文件不该让整条命令崩掉）。"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None

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
    out["total_tokens"] = out["prompt_tokens"] + out["completion_tokens"]
    return out


# ---------------------------------------------------------------------------
# 子命令：log（读回全过程记录）
# ---------------------------------------------------------------------------

def _build_log(claims_obj, challenge_obj, evidence_obj, verdict_obj, gates, usage, source,
               outdir):
    rulings = verdict_obj.get("rulings") or []
    rows = []
    for r in rulings:
        rows.append({"kind": "ruling", "claim_id": r.get("claim_id"),
                     "decision": r.get("decision"),
                     "has_downgraded_wording": bool(r.get("downgraded_wording")),
                     "basis": (r.get("basis") or "")[:120]})
    for x in challenge_obj.get("challenges") or []:
        rows.append({"kind": "challenge", "claim_id": x.get("target"),
                     "decision": x.get("verdict"),
                     "challenge_type": x.get("challenge_type"),
                     "severity": x.get("severity"),
                     "demand_retract": bool(x.get("demand_retract"))})
    by_decision, by_type = {}, {}
    for r in rows:
        if r["kind"] == "ruling":
            by_decision[r["decision"]] = by_decision.get(r["decision"], 0) + 1
        else:
            by_type[r.get("challenge_type") or "未标注"] = \
                by_type.get(r.get("challenge_type") or "未标注", 0) + 1
    eff = [r for r in rows if r["kind"] == "challenge"
           and r["decision"] == CHALLENGE_VERDICT_CHALLENGED]
    alt = [r for r in rows if r["kind"] == "ruling" and r["has_downgraded_wording"]]
    return {
        "version": STATE_VERSION,
        "source": str(source),
        "outdir": outdir,
        "entries": rows,
        "rulings": rulings,
        "by_decision": by_decision,
        "by_challenge_type": by_type,
        "effective_challenges": len(eff),
        "downgraded_wordings": len(alt),
        "gate_failed": gate_failed(gates),
        "gates_summary": {k: bool((gates.get(k) or {}).get("ok", True))
                          for k in HARD_GATE_KEYS},
        "usage": usage,
        "isolation": None,
        "note": ("`entries` 是动作流水：每条挑战与每条裁定一条记录。"
                 "本包的核心健康指标是 effective_challenges 与 downgraded_wordings ——"
                 "前者为 0 说明质疑没发生，后者为 0 说明裁决没有给出替代方案。"),
    }


def run_log(a):
    outdir = Path(a.outdir)
    logf = outdir / "log.json"
    repf = outdir / "REPORT.md"
    if not logf.is_file():
        raise UsageError("这个目录里没有 log.json（不是本包的 --outdir？）：{}".format(outdir))
    log = load_json(logf, "log.json")
    if not isinstance(log, dict) or not isinstance(log.get("entries"), list):
        raise UsageError("log.json 结构不对（缺 entries 列表）：{}".format(logf))
    vf = outdir / "verdict.json"
    if vf.is_file():
        try:
            v = load_json(vf, "verdict.json")
            for r in v.get("rulings") or []:
                pass
        except UsageError:
            pass
    rows = log.get("entries") or []
    rulings = [r for r in rows if r.get("kind") == "ruling"]
    chs = [r for r in rows if r.get("kind") == "challenge"]
    eff = [r for r in chs if r.get("decision") == CHALLENGE_VERDICT_CHALLENGED]
    alt = [r for r in rulings if r.get("has_downgraded_wording")]
    need_alt = [r for r in rulings
                if r.get("decision") in (RULING_DOWNGRADE, RULING_RETRACT)]
    result = {
        "mode": "log", "outdir": str(outdir),
        "entries": len(rows), "rulings": len(rulings), "challenges": len(chs),
        "effective_challenges": len(eff),
        "downgraded_wordings": len(alt),
        "need_downgraded_wording": len(need_alt),
        "by_decision": log.get("by_decision") or {},
        "by_challenge_type": log.get("by_challenge_type") or {},
        "gate_failed": log.get("gate_failed"),
        "gates_summary": log.get("gates_summary") or {},
        "usage": log.get("usage") or {},
        "source": log.get("source"),
        "report_path": str(repf) if repf.is_file() else None,
        "answer": ("质疑方提了 {} 条挑战，其中 **{} 条真的成立**；"
                   "裁决判了 {} 条「不能采信」，其中 **{} 条给了替代表述**。"
                   "{}".format(
                       len(chs), len(eff), len(need_alt), len(alt),
                       "挑战成立数为 0 → 质疑没发生。" if not eff
                       else "挑战成立数不为 0 → 质疑真的发生了。")),
    }
    md = ["# 全过程记录：{}".format(outdir), ""]
    md.append("- 动作流水 {} 条 · 裁定 {} 条 · 挑战 {} 条".format(
        result["entries"], result["rulings"], result["challenges"]))
    md.append("- **挑战成立 {} 条**（记录 {} 条）".format(len(eff), len(chs)))
    md.append("- **降级表述 {} 条**（判「不能采信」{} 条）".format(len(alt), len(need_alt)))
    md.append("- 裁定分布：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in (result["by_decision"] or {}).items())
        or "（无）"))
    md.append("- 挑战类型分布：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in (result["by_challenge_type"] or {}).items())
        or "（无）"))
    md.append("- {}".format(result["answer"]))
    md.append("")
    md.append("完整报告见 `{}`。".format(repf.name))
    md = "\n".join(md)
    if _json_out(result, a, indent=2):
        return EXIT_OK
    print(md)
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：cost / models
# ---------------------------------------------------------------------------

def run_cost(a):
    check_cost_opts(a)
    text = a.text if a.text else (read_text(a.file) if a.file else "")
    if not text:
        raise UsageError("要报价请给 --file 或 --text")
    roles = resolve_roles(getattr(a, "roles", None))
    calls = estimate_calls(text, len(roles))
    t_in = sum(c["tokens_in"] for c in calls)
    t_out = sum(c["tokens_out"] for c in calls)
    rec = compute_cost(t_in, t_out, a.price_in, a.price_out)
    body = {
        "command": "cost",
        "chars": char_count(text),
        "roles": [r["id"] for r in roles],
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
        "note": "本包不联网检索，只有 4 次文本调用；报价里不含任何检索端点。",
    }
    md = ["# 这次取证大概花多少", "",
          "- 材料：{} 字符".format(char_count(text)),
          "- 工序：{} 道（{}）".format(len(roles), "、".join(ROLE_NAME[r["id"]] for r in roles)),
          "- 调用：{} 次（**本包不联网检索**）".format(sum(c["calls"] for c in calls)),
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
    print("用法：run.py claims --file 材料.md --model <model_code>")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def check_cost_opts(a):
    """`--budget` 必须配单价 —— 在**任何调用发生之前**检查。

    事故复盘（同族自测时踩到的真实坑，不是理论问题）：这道校验原先只写在 `cost` 里，
    于是 `claims --file x --budget 50`（没给单价）一路跑完真实调用才返回 ——
    用户以为设了预算上限，实际一分钱都没被拦住。所以它必须是**每一个会花钱的子命令的第一步**。
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


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与全族同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py claims --file x --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_source_opts(p, stage):
    p.add_argument("--file", required=True, help="待证材料/稿件（.md / .txt，UTF-8）")
    p.add_argument("--outdir", help="把这一阶段的产物落这个目录（**必须在包外**）")
    p.add_argument("--replay", help="回放一份已保存的阶段产物：只跑本地校验与渲染，"
                                    "**零调用**（闸门自测用）")


def _add_model_opts(p, out=True):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 {}（实测可用；用 `run.py models` 现查在架模型）".format(
                       DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens",
                   help="最大输出 token，默认 8192（一次取证多次调用，别调太小）")
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
        description="三剪客 · 调研取证小组（L3 取证式多智能体：主张 → 质疑 → 取证 → 裁决；"
                    "走 api.a7w.cn 的 OpenAI 兼容端点。**本包不联网检索**）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    # 每个子命令的 parser 也必须关掉缩写：argparse 的缩写开关是**每个 parser 各自**的属性，
    # 只在父级设一遍不够（子 parser 是另造的实例，默认仍然是允许缩写）。
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("roles", help="列出四个角色的职权、产出物与否决权（零成本）")
    _add_json(p)
    p.add_argument("--out", help="把角色表写到这个文件")
    p.set_defaults(func=run_roles)

    p = sub.add_parser("claims", help="主张方：主张清单 + 证据引用（一次调用）")
    _add_source_opts(p, "claims")
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_claims)

    p = sub.add_parser("challenge", help="质疑方：逐条挑战书 + 挑战类型（一次调用，信息隔离）")
    _add_source_opts(p, "challenge")
    p.add_argument("--claims", required=True, help="claims 产出的 claims.json")
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_challenge)

    p = sub.add_parser("evidence", help="取证方：证据强度评级（一次调用）")
    _add_source_opts(p, "evidence")
    p.add_argument("--claims", required=True, help="claims 产出的 claims.json")
    p.add_argument("--challenge", required=True, help="challenge 产出的 challenge.json")
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_evidence)

    p = sub.add_parser("verdict", help="裁决方：可采信边界 + 降级表述（一次调用）")
    _add_source_opts(p, "verdict")
    p.add_argument("--claims", required=True, help="claims 产出的 claims.json")
    p.add_argument("--challenge", required=True, help="challenge 产出的 challenge.json")
    p.add_argument("--evidence", required=True, help="evidence 产出的 evidence.json")
    _add_model_opts(p)
    _add_cost_opts(p)
    p.set_defaults(func=run_verdict)

    p = sub.add_parser("run", help="一条命令跑完（claims→challenge→evidence→verdict），断点续跑")
    p.add_argument("--file", required=True, help="待证材料/稿件（.md / .txt，UTF-8）")
    p.add_argument("--roles", help="四道工序（逗号分隔，默认全部）：{}".format(
        "、".join(ROLE_IDS)))
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--outdir",
                   default=str(Path(os.environ.get("TEMP") or ".") / "research-crew-out"),
                   help="目录产物落这里（**必须在包外**）：brief、claims、challenge、"
                        "evidence、verdict、REPORT.md、log.json、state.json")
    p.add_argument("--replay", help="从一个已有产物目录回放：读取该目录里的 "
                                    "claims.json / challenge.json / evidence.json / "
                                    "verdict.json，**零调用**只跑本地闸门与报告（闸门自测用）")
    p.add_argument("--force", action="store_true",
                   help="忽略断点文件，从头重跑（key 没命中就会重新花钱）")
    p.add_argument("--all-passed-ok", action="store_true", dest="all_passed_ok",
                   help="允许「质疑方全部放行」不判「质疑无效」"
                        "（只在确认材料本身无争议时用；默认是硬闸门）")
    p.set_defaults(func=run_run)

    p = sub.add_parser("log", help="读回全过程记录：哪些主张被挑战掉、哪些被判必须降级")
    p.add_argument("--outdir", required=True, help="run 的 --outdir")
    _add_json(p)
    p.set_defaults(func=run_log)

    p = sub.add_parser("cost", help="报价：这次取证大概花多少 token（金额要你填单价，零成本）")
    p.add_argument("--file", help="按这份材料估")
    p.add_argument("--text", help="或直接给文本")
    p.add_argument("--roles", help="按哪几道工序估（默认四道）")
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
                 ("force", False), ("all_passed_ok", False), ("roles", None), ("outdir", None),
                 ("clash", None), ("claims", None), ("challenge", None), ("evidence", None),
                 ("type", "text"), ("file", None), ("text", None)):
        if not hasattr(a, k):
            setattr(a, k, v)
    kind, msg, detail = None, None, None
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
