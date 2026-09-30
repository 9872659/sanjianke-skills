#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 内容团队 —— 多智能体协作出稿（零第三方依赖）。

**产品线 L3（多智能体协作型）的第一个包。** 与 L2（单角色自我迭代，如
sanjianke-content-qc 的「打分 → 重写 → 复评」）的分界不是"调了几次模型"，而是：

  1. 四个角色**各有各的目标函数与产出物**（选题卡 / 初稿 / 问题清单 / 风险裁决）
  2. 角色之间**互相否掉东西**（审稿打回写手、合规一票否决、策划重开选题）
  3. 有**明确的裁决机制**（谁能否谁、最多几轮、谈不拢走哪个出口）
  4. 一条命令出成品：**定稿 + 全过程记录**

**信息不对称**（本包是 L3 而不是"一个模型演四个角色"的关键，且是结构性保证）：

  · 写手的 `self_check`（自评）**不进审稿的上下文** —— 审稿只看到规划卡与初稿正文
  · 审稿的 `issues`（偏好）**不进合规的上下文** —— 合规只看到规划卡要点与稿件正文，
    提示词里明说"本团队内部没有给出任何风险结论，你不得假设前道已放行"
  · 两条禁令由 `assert_isolation()` 在**每次调用前**用文本级检查验证，
    判定结果逐条写进产出与流程日志（`isolation` 字段），可复核

八个子命令：

    roles       列出四个角色的职权、产出物与否决权（纯本地，零成本）
    plan        策划出选题卡
    draft       写手按选题卡出初稿（附自评；自评不进审稿上下文）
    review      审稿出逐条问题清单，**可打回写手**
    compliance  合规风险裁决，**有一票否决权**
    run         一条命令跑完整协作：带裁决、轮次上限与明确出口
    log         读回全过程记录：谁在第几轮改了什么、谁否决了什么、引用原句
    cost / models

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py roles
    python3 run.py plan       --brief brief.md --outdir /tmp/ct
    python3 run.py draft      --brief brief.md --card /tmp/ct/plan.json --outdir /tmp/ct
    python3 run.py review     --brief brief.md --card /tmp/ct/plan.json --draft /tmp/ct/rounds/r1/draft.md
    python3 run.py compliance --brief brief.md --card /tmp/ct/plan.json --draft /tmp/ct/rounds/r1/draft.md
    python3 run.py run        --brief brief.md --rounds 2 --outdir /tmp/ct
    python3 run.py log        --outdir /tmp/ct
    python3 run.py plan       --brief brief.md --dry-run     # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py run --brief brief.md --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍
    · **为什么不是"一个模型分四次扮演不同角色"**：那样每个角色看到的上下文是一样的，
      不会有真正的对抗，评估者与被执行者是同一个声音。本包把"看不到什么"写死成
      提示词模板的结构（`ROLE_INPUTS`），再用 `assert_isolation()` 在调用前验证。
    · **谈不拢不许装作谈拢**：轮次用尽、合规打回次数用尽、连续两轮没有实质改动、
      审稿连续两轮指向同一批被拒条目的同一段文字 —— 这四种情况都走**显式出口**
      （升级给人看 / 产出带未决项），退出码 3，并在 `escalation` 里写明原因。
    · **合规一票否决**：合规判 `veto` 直接终止，产出就是"带未决项"，不换词硬发。
      只有"替换表里明确登记过安全替代词"的违禁词才允许**本地**自动替换，
      替换后必须本地复扫确认干净（`auto_fixed_verified`）；复扫不干净按否决处理。
    · 违禁词表是**启发式自检**，来自公开经验整理，不构成法律意见，
      也不等于平台官方审核规则。
"""

import argparse
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
# 关掉字节码写入，**必须在 import a7w 之前**。
#
# 【实测记录 —— 这里曾经写错过，把推测当成了结论，以下是复核过的】
# 干净临时目录里逐格对照（CPython 3.11.9）：
#
#   1  python run.py            （正常直跑）           → 一个 .pyc 都不生成
#   2  import run（**先**设 flag）                      → 一个 .pyc 都不生成
#   3  import run（**没设** flag）                      → __pycache__/run.cpython-311.pyc
#   4  python -m py_compile run.py                     → __pycache__/run.cpython-311.pyc
#
# 三条由此确定的结论：
#   a. **`sys.dont_write_bytecode = True` 是有效的**，只要它设在被 import 的那个
#      模块**之前**。迟一行，那个模块就已经落盘了（所以第 2 格才干净、第 3 格才有）。
#   b. **入口脚本作为 `__main__` 永远不会被字节码缓存** —— 第 1 格可以证明。
#      （早先这里写着"入口脚本自己也逃不掉"，那是没验证过的推测，是错的。）
#   c. **会生成 `run.pyc` 的情形只有两种**：有工具把入口 `import` 当模块用了
#      （零成本自检脚本 / 测试框架最常见），或者跑了 `py_compile`。
#      本项目就踩过第 1 种：一份自检脚本 `import run as R`，于是多了 run.pyc。
#
# 另外，`.pyc` **不会**导致上传被拒 —— `__pycache__` 与 `*.pyc` 在 CLI 的排除清单里，
# 本来就不会被打包。所以这一行是"让包保持干净"的锦上添花，不是上传的硬前提。
# 真正该做的两件事：自检脚本别 import 入口（import 之前先设这个 flag），
# 以及跑完 `py_compile` 之后清掉 `__pycache__`。
sys.dont_write_bytecode = True
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

# 退出码。数值与同族对齐：
EXIT_OK = 0            # 定稿：全流程走通、合规放行、无硬闸门命中
EXIT_USAGE = 2         # 参数/配置错（文件不存在、--outdir 在包内、给 --budget 没给单价）
EXIT_GATE = 3          # 硬闸门命中（合规/占位符/照抄示例/锚点/丢事实/**未收敛**）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。改了角色提示词/裁决规则却不改 key，
# 续跑会把上一版口径的旧产物当成"已完成"直接复用，产出对不上文档。
ROLE_VERSION = "ct-roles-1.0.0"
PROMPT_VERSION = "ct-prompt-1.0.0"
RULING_VERSION = "ct-ruling-1.0.0"

# 默认目标篇幅。**为什么给目标而不是上限**：实测模型会贴着你给的数字写，
# 给上限就一定顶到上限（然后超）。600 字也是"两三轮协作能收住"的区间。
DEFAULT_TARGET_CHARS = 600
TARGET_CHARS_MIN = 200
TARGET_CHARS_MAX = 4000


# ===========================================================================
# 角色表：L3 的地基
#
# 每个角色有自己的**目标函数**（想要什么）、**产出物**（交什么）与**否决权**（能否谁）。
# `inputs` 是**允许进入该角色上下文的字段白名单**，`forbidden` 是被显式排除的字段。
# 这两栏不是文档，是 build_*_prompt() 真实读的那份数据 —— 提示词模板按它拼装，
# assert_isolation() 按它验证。改这里就同时改了行为与判定，不会文档与实现两张皮。
# ===========================================================================

ROLE_ORDER = ("planner", "writer", "reviewer", "compliance")

ROLES = {
    "planner": {
        "name": "策划",
        "goal": "选题够不够打、角度有没有新意 —— 交不出一张有差异化的选题卡就是失职",
        "deliverable": "选题卡（受众 / 痛点 / 拟定标题 / 角度 / 差异化 / 3 条论据支柱）",
        "veto": "能否掉平庸的选题并重开，重开上限由 --plan-retries 控制",
        "inputs": ["brief", "target_chars"],
        "forbidden": [],
        "exit_on_fail": "选题卡不达标 → 重开；上限用尽 → 升级给人看（退出码 3）",
    },
    "writer": {
        "name": "写手",
        "goal": "严格按选题卡把稿子写出来，字数落区间，不动选题卡定的角度",
        "deliverable": "初稿正文 + 自评（self_check，**审稿看不到这一栏**）",
        "veto": "无 —— 写手只能改，不能否掉审稿或合规的结论",
        "inputs": ["brief", "card", "target_chars"],
        "forbidden": [],
        "exit_on_fail": "不适用（写手没有否决权）",
    },
    "reviewer": {
        "name": "审稿",
        "goal": "结构 / 逻辑 / 可读性 / 信息密度 —— 挑不出具体问题就是没干活",
        "deliverable": "逐条问题清单，每条**必须原样引用初稿里真实存在的一句话**",
        "veto": "能打回写手（pass/send_back），打回必须附「必须修」的问题清单",
        # ⚠️ 关键：写手的 self_check 被显式排除在审稿上下文之外。
        "inputs": ["brief", "card", "draft"],
        "forbidden": ["self_check", "writer_self_check"],
        "exit_on_fail": "连续两轮指向同一段文字仍然被拒 → 判定写手改不动 → 升级给人看",
    },
    "compliance": {
        "name": "合规",
        "goal": "广告法 / 事实 / 平台规则 —— 只看这一稿能不能发，不看它写得好不好",
        "deliverable": "风险裁决：pass（放行）/ fix（可安全替换）/ send_back（打回）/ veto（一票否决）",
        "veto": "**一票否决权**：判 veto 直接终止，产出就是带未决项的稿件，不换词硬发",
        # ⚠️ 关键：审稿的 issues 被显式排除在合规上下文之外。
        # 合规不许假设"前面已经审过了所以没问题"。
        "inputs": ["brief", "card_meta", "draft"],
        "forbidden": ["self_check", "issues", "review_verdict"],
        "exit_on_fail": "打回次数用尽仍不放行 → 带未决项产出（退出码 3）",
    },
}

# 每个角色调用的提示词里**禁止出现的标记词**。assert_isolation 用它做文本级检查：
# 排除一个字段，靠的不是"我模板里没写"，而是"调用前真的扫过一遍"。
ISOLATION_MARKERS = {
    "self_check": ["自评", "self_check", "我认为写得好的地方", "我自己的评价"],
    "issues": ["问题清单", "审稿意见", "审稿的", "issues"],
    "review_verdict": ["审稿结论", "review_verdict", "上道已经放行", "审稿已通过"],
}

# 合规的「安全替代词」表。**只有登记在这里的词才允许本地自动替换**，
# 替换后必须本地复扫确认干净（auto_fixed_verified）——否则按否决处理。
# 表里空着的（比如"国家级"）说明本地没有可靠的安全替代，必须走 veto 给人看。
SAFE_REPLACEMENTS = {
    "最好": "", "最佳": "较合适", "最优": "较合适", "最低": "较低", "最便宜": "价格较低",
    "最快": "较快", "最强": "较强", "最大": "较大", "最高": "较高", "最先进": "较先进",
    "最新": "较新", "最流行": "较流行", "最受欢迎": "较受欢迎",
    "百分之百": "基本", "百分百": "基本",
    "100%": "", "No.1": "靠前", "no.1": "靠前", "TOP1": "靠前", "top1": "靠前",
    "绝对有效": "通常有效", "保证有效": "有助于", "无效退款": "可按规则申请售后",
    "零风险": "风险较低", "稳赚": "有机会", "躺赚": "有机会", "包赚": "有机会",
    "稳赚不赔": "有机会", "一本万利": "有机会", "高回报": "有机会",
    "独家": "特色", "唯一": "少见的", "首个": "较早的", "首创": "较早采用",
    "领先品牌": "较早采用该做法的品牌", "领先技术": "较早采用的技术",
    "纯天然": "以天然成分为主", "无添加": "配方简单", "零添加": "配方简单",
    "无毒无害": "按说明使用较安心",
    "点击链接": "查看详情", "加微信": "联系客服", "私信我": "联系客服",
    "震惊": "值得注意", "惊呆": "值得注意", "速看": "可以一看",
}

# 提示词里出现过的**跨主题**示例（正常不该被抄）。新增示例必须登记到这里。
# 跨主题 = 与任何真实选题都不搭（电动车充电桩），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
PROMPT_SAMPLES = [
    "电动车充电桩到底值不值得装，三个理由",
    "小区充电桩的安装条件别只看价格",
]

CONVERGE_NOTE = (
    "裁决不是投票：审稿有权打回，合规有权否决，两者是**串行**关系 —— "
    "审稿不过就轮不到合规；审稿过了合规仍可独立否决。"
    "轮次用尽、连续两轮无实质改动、审稿持续指向同一段文字 —— 都走**显式出口**。"
)

MAX_NO_CHANGE_STRIKES = 1     # 连续两轮"没有实质改动"就升级（0 次改动即算一次）
BODY_MIN_SIM = 0.86           # 新稿与上一稿的正文相似度 ≥ 此值即判「没有实质改动」
FIX_RATIO_MIN = 0.5           # 打回时说"已修"的问题条数 / 被点名条数，低于它就判没修够


# ===========================================================================
# 闸门一：合规（广告法违禁词）
#
# 每项：正则 → 风险等级 → 人话解释。这是一道**粗筛**，宁可多报也别漏报，
# 最终判断仍要人工复核，且不等于平台官方审核结论。
# ===========================================================================

# 「第一」的可枚举上下文豁免（同族踩过：长文里「第一年」「第一步」是**序数**，
# 不是最高级宣称；一刀切拦下的后果是用户干脆把整个合规闸门关掉，那比漏报更糟）。
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
# 事故复盘：`最大区别` / `最主要的是` 这类是**普通中文用法**，不是最高级商品宣称。
# 开了豁免口子，但同时加一条**句首不豁免**：句首的「最大区别是…」是标题式宣称，照拦。
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


def check_ordinal_exemption(text, m):
    """「第一」是不是**序数**（不是排他性宣称）？是则豁免。

    两条判据，命中其一即豁免：

      1. 后接序数量词 —— 「第一年」「第一步」「第一件事」「第一批」这类。
         事故复盘（同族）：原来那条只排除了「第一次」，实测第一篇真实稿就被误判
         （「第一年上了 3 部剧」）。一刀切拦下的后果很实在：用户会把整个合规闸门关掉，
         那比漏报更糟。
      2. 后接**计量词 + 普通名词** —— 「第一台半自动」「第一款胶囊机」「第一个月」。
         本包实测踩到两次：`买入第一台半自动` 与 `想买第一台家用咖啡机的人`
         都被当成「第一」类排他性表述。这是**序数**用法（第一台 = 首台），
         与「销量第一 / 排名第一」毫无关系，却让定稿连带罚分。
         判据取「后接量词」而不是「后接任意名词」，是为了**不放过**
         「第一品牌」「第一选择」这类真正的排他性表述 —— 那两个词后面不是量词。

    没有命中豁免的（「第一名」「第一品牌」「销量第一。」）照拦，且豁免项会记进
    `exempted`，**不静默放过**。
    """
    if m.group(0) != "第一":
        return False
    after = (text or "")[m.end():]
    if re.match(r"^(?:" + FIRST_ORDINAL_AFTER + r")", after):
        return True
    return re.match(r"^[台款个只把种条部支瓶盒套间场次]", after) is not None


def compliance_scan(text):
    """扫一遍违禁词，返回 (命中列表, 被豁免列表)，命中按风险等级排序。

    同一处文字可能在文中出现多次（一次是广告语、一次是普通用法），
    所以判定按**每一处出现**做，任一处未被豁免就算命中。
    被豁免的疑似命中会记进 `exempted`，**不静默放过**。
    """
    hits, exempted, seen = [], [], set()
    t = text or ""
    for rx, lvl, why in BANNED_RE:
        for m in rx.finditer(t):
            if _superlative_is_normal_usage(t, m) or check_ordinal_exemption(t, m):
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


def apply_safe_replacements(text):
    """把**登记在 SAFE_REPLACEMENTS 里**的违禁词替换成安全替代词（纯本地）。

    只在合规判 `fix` 时用。替换完必须本地复扫确认干净，否则按否决处理。
    返回 (新文本, 改了什么)。
    """
    out = text or ""
    changes, seen = [], set()
    for rx, lvl, why in BANNED_RE:
        # 从长到短替换，避免"最便宜"被"最低"的规则先切碎
        for m in sorted(rx.finditer(out), key=lambda x: -len(x.group(0))):
            if _superlative_is_normal_usage(out, m) or check_ordinal_exemption(out, m):
                continue
            word = m.group(0)
            if word in seen or word not in SAFE_REPLACEMENTS:
                continue
            seen.add(word)
            rep = SAFE_REPLACEMENTS[word]
            changes.append({"word": word, "level": lvl, "replaced_with": rep, "why": why})
    for c in changes:
        out = out.replace(c["word"], c["replaced_with"])
    if changes:
        # 替换后清理可能出现的空括号/双空格
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r"（\s*）|\(\s*\)", "", out)
    return out, changes


# ===========================================================================
# 闸门二：占位符残留
#
# 长文是大模型一次吐几百上千字，模板没替换干净的形态比标题场景多得多：
# `{}` / `[待填]` / `XXX` / `（此处省略）` / `待补充`。
# `[1]`（引用序号）、`[图 2]`（配图位）是**正常写法**，所以括号那条只认枚举表。
# ===========================================================================

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


# ===========================================================================
# 闸门三：照抄提示词示例（prompt_echo）
#
# 事故复盘：提示词里写过正例 → 模型直接产出同构句；提示词里留过整句示例 →
# 那一轮**最高分**的产出一字不差就是它。"抄了标准答案"被当成"真的最好"。
#
# 本包是长文场景，所以判定分两层：整段比一次 + **逐句**比一次。
# 正文有几百上千字，把整段拿去和示例算 Jaccard，分母被撑大，相似度永远接近 0 ——
# 模型把示例原样抄进某一句，整段判据完全看不见。
#
# 三条命中判据（任一即命中）：
#   exact    去掉标点后完全相同
#   jaccard  字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
#   contain  示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（示例被夹带进更长的句子里）
#
# 【为什么必须有第三条】Jaccard 的分母是两份二元组的**并集**，产出越长，
# 示例那一侧被摊薄得越狠 —— 示例原样嵌进去也会掉到 0.75 以下侥幸放行。
# 覆盖度只看"示例被抄了多少"，不看产出有多长，摊薄对它无效。
# ===========================================================================

ECHO_SIM = 0.75          # 同族实测标定：196 条正常产出与跨主题示例最高只 0.174
ECHO_CONTAIN = 0.60      # 同族实测：真实历史产出里覆盖度最大 0.500，余量 1.2 倍、误伤 0
ECHO_MIN_LEN_FLOOR = 6   # 长度守卫的绝对下限，防极短串的二元组噪声


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


ECHO_APPLY_MIN = 24      # contain 判据的**适用窗口**：只对 ≥ 24 字的产出片段判


def prompt_echo(text, samples=None, rule_contain=True):
    """文本是否与提示词里的示例"抄得太近"。

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"。

    【contain 的适用窗口】覆盖度判据的分母是**示例的二元组全集**。当产出比示例短、
    或两者都只有几个字时，几个巧合的二元组就能把覆盖度顶到 0.6 以上 —— 实测
    「三个理由」这种 4 字短语与示例共 3 个二元组就能到 0.75。所以 contain 只在
    产出片段 ≥ ECHO_APPLY_MIN 字时启用；更短的片段由 exact / jaccard 负责
    （jaccard 是并集分母，短串时不会虚高）。
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
        if rule_contain and len(target) >= ECHO_APPLY_MIN and contain >= ECHO_CONTAIN \
                and contain >= best_score:
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


def prompt_echo_scan(text, samples=None, label="稿件"):
    """在长文本里逐句找「照抄提示词示例」的地方，返回命中列表（可能为空）。

    两层：整段先比一次（只认 exact / jaccard，兜整篇照抄的极端情况），
    再**逐句**比一次（含覆盖度判据，兜「某一句是抄的」这个真实形态）。
    """
    hits = []
    whole_hit, score, sample, rule = prompt_echo(text, samples, rule_contain=False)
    if whole_hit:
        hits.append({"segment": (text or "")[:40], "rule": rule, "sim": round(score, 3),
                     "sample": sample,
                     "why": ("与提示词示例去掉标点后完全相同（照抄示例）" if rule == "exact"
                             else "与提示词示例相似度 {:.2f}，属同构照抄".format(score))})
        return hits
    for para in split_paras(text):
        for seg in split_sentences(para) + [para]:
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
            return hits              # 一处命中足够拦截，不用把整篇列完
    return hits


# ===========================================================================
# 闸门四：重写不许丢事实（数字 / 专有名词）
#
# 这是"AI 改稿"最隐蔽的一种损失：语句更顺了、评分更高了，但**原稿里的一个数字没了**。
# 人眼几乎发现不了（尤其改的是几千字的长文），但业务上它可能是致命的。
#
# 【诚实说明这是启发式】数字这一条是确定性的；专有名词靠四类模式抓，抓不全，
# 也可能多报。所以：多报会拦下正常产出 → 提供 `--facts-warn-only` 降级为提示。
#
# 【本包的额外一条，比同族更严】第一稿的"事实"不只来自上一稿，也来自**策划的选题卡**：
# 策划在论据支柱里许下的数字与专名，定稿里必须兑现（否则读者看到的是"标题许诺了
# 三个数据、正文一个都没有"）。这条判据叫 coverage。
# ===========================================================================

NUM_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")
FACT_PROPER_PATTERNS = [
    (re.compile(r"《([^》\n]{2,24})》"), "书名/作品名"),
    (re.compile(r"[「“]([^」”\n]{2,20})[」”]"), "引号内短语"),
    (re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9.+#\-]{1,19})(?![A-Za-z0-9])"), "英文专名"),
    # 机构后缀这一条**实测踩过坑**：原来的枚举表里有「平台 / 系统 / 模型 / 算法」，
    # 第一次真机跑就把「我们也试过让模型」整段抓成了专名 —— 这四个词在中文技术写作里
    # 太通用。假事实的危害不只是多一条：改稿把「模型」换成「大模型」就会被判成"丢了专名"，
    # 台账一多报，人就不看台账了。所以只留真正指向具体实体的后缀。
    (re.compile(r"([\u4e00-\u9fff]{2,8}(?:公司|集团|大学|学院|研究院|实验室"
                r"|基金|银行|医院|工作室|协会|出版社|电视台))"), "机构/产品名"),
]
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
    """抽出文本里的事实清单（数字 + 启发式专有名词），去重保序。"""
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


def _fact_present_in(final_text, f):
    """单个事实在不在文本里（与 fact_loss_report 同一套判据，含数字换中文写法）。"""
    norm_final = _norm_text(final_text)
    if f["kind"] == "num":
        if _num_present(norm_final, f["norm"]):
            return True
        if "." not in f["norm"]:
            cn = int_to_cn(int(f["norm"]))
            return bool(cn) and cn != "零" and cn in _norm_anchor(final_text)
        return False
    return f["norm"].lower() in norm_final.lower()


def fact_loss_report(orig_text, final_text, warn_only=False):
    """逐条核对上一稿事实在新稿里还在不在。

    返回 {"total","kept","lost","renumbered","kept_rate","ok","warn_only","facts"}
      kept        —— 仍在的
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


# ===========================================================================
# 闸门五：审稿锚点校验（审稿的引文必须在稿子里真实存在）
#
# 只是"在提示词里写一句请引用原句"，模型经常给你泛泛而谈
# （「建议加强逻辑衔接」「整体信息量可以更足」）—— 这种意见**没法执行**：
# 改哪个句子？改成什么？写手拿到它只能重写一遍。
#
# 所以本包不采信审稿的引文，而是**本地校验**：它引的那句话在不在稿子里？
#   exact      归一化后与某一整句完全相同
#   substring  归一化后是某一整句的一部分（只引半句，最常见）
#   fuzzy      与最像的那一句 Jaccard ≥ ANCHOR_SIM 且引文够长（轻改写式引用）
#   unverified 以上都不成立 → **判为锚点幻觉**，不进写手的修订输入，并计入未锚定率
#
# 未锚定率超过 ANCHOR_MAX_MISS → 判「审稿不达标」，压分 + 标红 + stderr 汇总 + 退出码 3。
# ===========================================================================

ANCHOR_MIN_SUBSTR = 4     # 精确子串匹配的最低长度
ANCHOR_MIN_CHARS = 8      # 模糊匹配的最低长度（二元组太少会虚高，门槛必须高）
ANCHOR_SIM = 0.55         # 模糊匹配阈值
ANCHOR_MAX_MISS = 0.40    # 未锚定率超过它就判「锚点失败」

# 为什么两种匹配用**两个不同的长度门槛**（相对阈值的思路，与 prompt_echo 的长度守卫同源）：
# 「引文恰好是某句的连续片段」是**精确**判断（去标点后逐字命中），短一点也几乎不会误伤；
# 而「最像的那一句」是**统计**判断，短串的字符二元组集合太小，相似度会虚高，所以必须卡长度。


def verify_anchor(quote, sentences, norms=None):
    """把审稿的引文锚定到稿子的某一句话上。

    返回 (ok, rule, index)；index 是句序号（0 基），未锚定时为 -1。
    """
    q = _norm_anchor(quote)
    if not q:
        return False, "unverified", -1
    if norms is None:
        norms = [_norm_anchor(s) for s in sentences]
    for i, n in enumerate(norms):                     # 1) 完全相同
        if n and n == q:
            return True, "exact", i
    if len(q) >= ANCHOR_MIN_SUBSTR:                   # 2) 精确子串（双向）
        for i, n in enumerate(norms):
            if n and (q in n or n in q) and min(len(q), len(n)) >= ANCHOR_MIN_SUBSTR:
                return True, "substring", i
    best_i, best = -1, 0.0                            # 3) 模糊：找最像的一句
    if len(q) >= ANCHOR_MIN_CHARS:
        for i, s in enumerate(sentences):
            sim = _similarity(quote, s)
            if sim > best:
                best_i, best = i, sim
        if best >= ANCHOR_SIM:
            return True, "fuzzy", best_i
    return False, "unverified", -1


def anchor_issues(issues, text):
    """给审稿的每条问题做锚点校验，返回 (锚定成功的, 未锚定的)。

    锚定成功的那条会把 `quote` **就地修正成稿子里的真实句子**（`sentence` 字段）——
    审稿引半句、连引两句都对不上时，日志里要显示的是稿件原文，不是它的转述。
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
            item["why_unverified"] = ("引文在稿子里找不到（归一化后也不匹配任一整句，"
                                      "模糊相似度 < {:.2f}）——判为锚点幻觉，不进写手的修订输入"
                                      .format(ANCHOR_SIM))
            bad_list.append(item)
    return ok_list, bad_list


# ===========================================================================
# 信息不对称：结构性保证 + 调用前验证
#
# L3 与"一个模型演四个角色"的真正分界在这里。演出来的四个角色共享同一份上下文，
# 于是"审稿"永远看不到一个它不知道的自评、"合规"永远顺着审稿的结论走 —— 对抗是假的。
#
# 本包把"看不到什么"做成两个机制：
#   1. ROLE_INPUTS（即 ROLES[*]["inputs"]）是**字段白名单**，提示词模板按它拼装，
#      被排除的字段在物理上就没有进入 prompt 的路径；
#   2. assert_isolation() 在**每次调用前**扫一遍真实 prompt 文本，逐条验证被禁字段
#      的标记词一个都不出现。判定结果写进产出与流程日志，外部可复核。
# ===========================================================================

def check_isolation(stage, prompt_text, excluded_fields=None):
    """纯函数：检查一次调用的 prompt 里有没有混进被排除的字段。

    参数
      stage           角色名（ROLES 的键）
      prompt_text     **真实**拼好的提示词全文
      excluded_fields 覆盖 ROLES[stage]["forbidden"]（一般不用传）

    返回 {"stage","excluded","markers_checked","leaked","ok"}
      leaked 每项：{"field": 被禁字段, "marker": 命中的标记词, "at": 命中位置附近片段}
    """
    spec = ROLES.get(stage) or {}
    excluded = list(excluded_fields if excluded_fields is not None
                    else spec.get("forbidden") or [])
    hay = _norm_anchor(prompt_text)
    leaked, checked = [], 0
    for field in excluded:
        for marker in ISOLATION_MARKERS.get(field, []):
            checked += 1
            if _norm_anchor(marker) and _norm_anchor(marker) in hay:
                leaked.append({"field": field, "marker": marker,
                               "at": (prompt_text or "")[:0] + _marker_context(prompt_text, marker)})
    return {"stage": stage, "excluded": excluded, "markers_checked": checked,
            "leaked": leaked, "ok": not leaked}


def _marker_context(text, marker):
    """命中标记词的位置附近取一小段，便于人眼核对（不是整篇）。"""
    i = (text or "").find(marker)
    if i < 0:
        return ""
    return (text or "")[max(0, i - 24):i + len(marker) + 24].replace("\n", " ")


def assert_isolation(stage, prompt_text, excluded_fields=None):
    """调用前断言：不对称被破坏了就**不许发这次调用**（抛 IsolationBreach）。

    为什么是硬失败而不是打个 warning：如果审稿真的看到了写手的自评，这一轮
    产出的"独立判断"就是假的，整条链的结论都不能用 —— 宁可停下报错，
    也不要产出一份看起来完整、实际是同一个人自说自话的报告。
    """
    rep = check_isolation(stage, prompt_text, excluded_fields)
    if not rep["ok"]:
        detail = "；".join("{} 的标记词「{}」出现在 prompt 里".format(
            l["field"], l["marker"]) for l in rep["leaked"])
        raise IsolationBreach(
            "信息不对称被破坏，已中止本次调用：{}。这是本包的硬性机制（L3 的立身之本），"
            "不是可以放宽的告警。".format(detail))
    return rep


class IsolationBreach(RuntimeError):
    """信息不对称被破坏（L3 的硬性机制）。"""


# ===========================================================================
# 闸门六：裁决与终止条件
#
# 四个出口，都是**显式**的，不许假装谈拢：
#   rounds_exhausted       轮次上限用尽仍未放行
#   plan_retries_exhausted 策划重开上限用尽仍交不出达标选题卡
#   no_effective_change    连续两轮改动过小（写手在原地打转）
#   stalled_same_quote     审稿连续两轮指向同一段被拒文字（写手改不动那一句）
#   compliance_send_back_exhausted 合规打回次数用尽仍不放行
# 出口 1/2/3/4 → 升级给人看；出口 5 与合规 veto → 带未决项产出。
# ===========================================================================

EXIT_KIND = {
    "rounds_exhausted": "升级给人看：轮次用尽，附全部未决项",
    "plan_retries_exhausted": "升级给人看：策划交不出达标选题卡",
    "no_effective_change": "升级给人看：写手在原地打转，继续跑只是烧钱",
    "stalled_same_quote": "升级给人看：审稿两次指向同一段文字，写手改不动它",
    "compliance_send_back_exhausted": "带未决项产出：合规打回次数用尽仍不放行",
}


def body_similarity(a, b):
    """两稿正文的相似度（字符二元组 Jaccard，去标点空白）。"""
    return round(_similarity(a or "", b or ""), 3)


def revision_effective(old_text, new_text, fixes_requested, fixes_reported):
    """判断这一轮修改是不是**实质改动**。

    两个都要看：
      · 正文相似度 —— 只动几个标点/换个词就等于没改
      · 自报已修的条数占被点名条数的比例 —— 说"已修"但正文没变的，不算
    返回 {"effective","body_sim","fix_ratio","why"}
    """
    sim = body_similarity(old_text, new_text)
    req = max(0, int(fixes_requested or 0))
    rep = max(0, int(fixes_reported or 0))
    ratio = (rep / float(req)) if req else 1.0
    why = []
    if sim >= BODY_MIN_SIM:
        why.append("新稿与上一稿的正文相似度 {:.2f} ≥ {:.2f}，等于没改".format(sim, BODY_MIN_SIM))
    if req and ratio < FIX_RATIO_MIN:
        why.append("被点名 {} 条只自报修了 {} 条（{:.0%} < {:.0%}）".format(req, rep, ratio, FIX_RATIO_MIN))
    return {"effective": not why, "body_sim": sim, "fix_ratio": round(ratio, 3),
            "why": "；".join(why) or "有实质改动"}


def check_escalation(rounds_run, rounds_max, plan_retries_used, plan_retries_max,
                     strikes, comp_send_back_used, comp_send_back_max,
                     stalled_quote=None):
    """算出"现在该不该走显式出口"。返回出口名或 None。

    这个函数是纯函数、只读参数，**故意**不掺任何"也许还能再跑一轮"的模糊判断 ——
    模糊判断正是"假装谈拢"的来源。
    """
    if stalled_quote:
        return "stalled_same_quote"
    if strikes > MAX_NO_CHANGE_STRIKES:
        return "no_effective_change"
    if plan_retries_used > plan_retries_max:
        return "plan_retries_exhausted"
    if comp_send_back_used > comp_send_back_max:
        return "compliance_send_back_exhausted"
    if rounds_run >= rounds_max:
        return "rounds_exhausted"
    return None


# ===========================================================================
# 提示词
#
# 【铁律】提示词里**不许出现任何一条可直接复制的完整中文范文句**。
# 事故复盘（同族，实测抓到两例）：提示词里写过正例，模型直接产出同构句；
# 尤其严重的一例，那一批最高分的产出**一字不差**就是提示词里的示例。
# 所以：讲形态只用**描述性语言**；确实需要举例时用**跨主题示例**
# （登记进 PROMPT_SAMPLES，由 prompt_echo 闸门兜底）。
# ===========================================================================

CHAT_RETRY_NOTE = "上游 5xx 与网络抖动退避重试；4xx 直接报错，不浪费额度。"

SYSTEM_PROMPTS = {
    "planner": (
        "你是内容团队的**策划**。团队接下来要写的东西全看你这张选题卡。\n"
        "你的目标函数：**选题够不够打、角度有没有新意**。交出一张换谁都能写的通用选题卡，"
        "就是你的失职 —— 审稿和合规不会替你把关选题质量，这一关只有你。\n"
        "硬性纪律（违反就整份作废）：\n"
        "  1. 不许编造任何数据、机构名、人名、案例。没有出处的数字一个都不要写。\n"
        "  2. `angle` 必须是**一个具体可执行的角度**，不是'从多个维度分析'这类空话。\n"
        "  3. `pillars` 恰好 3 条，每条一句话，彼此不能是同义改写。\n"
        "  4. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。"
    ),
    "writer": (
        "你是内容团队的**写手**。你只对一件事负责：**严格按策划的选题卡把稿子写出来**。\n"
        "硬性纪律（违反就整份作废）：\n"
        "  1. 不许改选题卡定的角度、受众、论据支柱。写得再顺，偏离选题卡就是不合格。\n"
        "  2. 不许编造数据、机构名、人名、案例。数字只能用给你的材料里出现过的。\n"
        "  3. 正文里不许出现绝对化用语（最高级、「第一」、100%、国家级这类）。\n"
        "  4. 不许输出 Markdown 代码围栏，不许输出 `{}` / `[待填]` 这类占位符。\n"
        "  5. 只输出 JSON，不要输出解释文字。"
    ),
    "reviewer": (
        "你是内容团队的**审稿**。你审的是结构 / 逻辑 / 可读性 / 信息密度。\n"
        "你的目标函数：**挑出具体到句子的真问题**。一条问题都挑不出来，说明你没干活；"
        "挑出十条泛泛之谈，同样说明你没干活。\n"
        "硬性纪律（违反就整份作废）：\n"
        "  1. 每条问题必须**原样引用**稿子里真实存在的一句话（或句中连续的一小段），"
        "不得改写、不得概括、不得凭空编造引文。引不出来的问题一律不要写。\n"
        "  2. 不许写「整体不错」「建议加强逻辑」这类无法执行的泛泛之谈。"
        "每条问题的 `fix` 必须是**改写后的具体句子**，不是方向。\n"
        "  3. 你**只依据稿件正文与选题卡**判断。任何「作者自己的评价」都不该影响你；"
        "如果它出现在你看到的内容里，忽略它并照常独立判断。\n"
        "  4. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。"
    ),
    "compliance": (
        "你是内容团队的**合规**。你审的是广告法 / 事实 / 平台规则。\n"
        "你的目标函数：**这一稿能不能发**。写得再好，不能发就是不能发。"
        "你**不评估**它写得好不好，那不是你的职权。\n"
        "硬性纪律（违反就整份作废）：\n"
        "  1. **本团队内部没有向你提供任何风险结论**，也不提供上一道工序的意见。"
        "你不得假设「前面已经审过了所以没问题」，一切风险由你从稿件正文独立判断。\n"
        "  2. 每条发现必须**原样引用**稿件里真实存在的文字。引不出来的不要写。\n"
        "  3. `risk_level` 与 `verdict` 必须与你的发现一致：有高风险发现却判 pass，"
        "属于失职。\n"
        "  4. 事实问题（无出处的数据、无法举证的承诺）比措辞问题严重。\n"
        "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。"
    ),
}

# 跨主题示例：只用来讲"什么样的问题算无法执行"，不是范文。
# 跨主题 = 与任何真实选题都不搭（电动车充电桩），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
_PROMPT_SAMPLE_BLOCK = (
    "跨主题示例（**仅供理解「什么算无法执行」，禁止把示例原句写进任何字段**）：\n"
    "  · 反面（无法执行）：把「{}」这类**没有出处的判断**当成建议，只说要更好，不说改哪句。\n"
    "  · 正面（可执行）：引出一句原文，说明它缺什么，再给出改写后的那句话。\n"
).format(PROMPT_SAMPLES[0])


def _json_req(obj):
    return ("\n按要求只输出这个 JSON 对象：\n"
            + json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def build_plan_prompt(brief, target_chars, attempt_note=None):
    """策划：从用户材料出选题卡。**输入只有用户的材料**（+ 目标字数）。

    策划看不到任何其他角色的东西 —— 它是链条的第一环，没有上游。
    """
    return (
        "下面是用户给的原始材料（可能很短，也可能只是一句话）。\n"
        + (attempt_note + "\n" if attempt_note else "")
        + "\n请据此出一张**选题卡**。\n"
        + "要求：\n"
          "  · `angle` 要具体到一个可执行的角度，能让写手立刻动笔；不许写成'全面分析'。\n"
          "  · `differentiation` 要说清这篇稿子**跟同题材的常见稿子比不一样在哪**。\n"
          "  · `pillars` 恰好 3 条论据支柱，每条一句话，彼此不能是同义改写。\n"
          "  · `must_keep` 列出写手**必须写进正文**的硬信息（数字、条件、专有名词）。"
          "只能从下面的材料里抄，材料里没有的就别写；材料里确实没有硬信息就给空数组。\n"
          "  · 目标篇幅约 {n} 字符（写手会照这个数写）。\n".format(n=target_chars)
        + _json_req({
            "title": "拟定标题（不超过 30 字）",
            "audience": "写给谁看（具体到一类人，不要写'所有人'）",
            "pain": "这群人当下最具体的那个痛点",
            "angle": "从哪个具体角度切入",
            "differentiation": "与同题材常见稿子比，差异化在哪",
            "pillars": ["论据支柱 1", "论据支柱 2", "论据支柱 3"],
            "must_keep": ["写手必须写进正文的硬信息（数字/条件/专名），没有就给空数组"],
            "risk_note": "这个角度最可能踩的合规风险（给合规角色看的提示，不是结论）",
        })
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def _card_block(card, with_meta_only=False):
    """把选题卡渲染成提示词块。

    `with_meta_only=True` 时**只给标题与风险提示**（合规用）—— 合规不需要看
    受众/痛点/差异化，它要审的是稿件正文本身。给得越少，它越不得不独立判断。
    """
    if not isinstance(card, dict):
        return "  （策划没有交出可用的选题卡）\n"
    if with_meta_only:
        return ("  · 拟定标题：{}\n  · 策划提示的风险点：{}\n".format(
            card.get("title") or "-", card.get("risk_note") or "-"))
    lines = ["  · 拟定标题：{}".format(card.get("title") or "-"),
             "  · 受众：{}".format(card.get("audience") or "-"),
             "  · 痛点：{}".format(card.get("pain") or "-"),
             "  · 角度：{}".format(card.get("angle") or "-"),
             "  · 差异化：{}".format(card.get("differentiation") or "-")]
    for i, p in enumerate(card.get("pillars") or [], 1):
        lines.append("  · 论据支柱 {}：{}".format(i, p))
    mk = card.get("must_keep") or []
    lines.append("  · 必须写进正文的硬信息：{}".format(
        "、".join(str(x) for x in mk) if mk else "（无）"))
    lines.append("  · 策划提示的风险点：{}".format(card.get("risk_note") or "-"))
    return "\n".join(lines) + "\n"


def build_draft_prompt(brief, card, target_chars):
    """写手：按选题卡出初稿。**输入 = 用户材料 + 选题卡 + 目标字数**。

    写手看不到审稿、看不到合规 —— 它是被审的对象，事前不该知道审查口径。
    """
    return (
        "请按下面这张选题卡写出**初稿**。\n"
        + "选题卡：\n" + _card_block(card)
        + "\n写作要求：\n"
          "  · 篇幅约 {n} 字符（不含空白的正文字符数，上下浮动不超过 15%）。\n".format(n=target_chars)
        + "  · 三个论据支柱都要在正文里落到实处，不能只在标题里提。\n"
          "  · `must_keep` 里的每一项都必须原样出现在正文里。\n"
          "  · 正文用连续段落写，不要小标题清单，不要 Markdown 记号。\n"
          "  · 事实只能用材料与选题卡里有的；需要的数字材料里没有，就用定性描述，"
          "**不许自己造一个数**。\n"
        + _json_req({
            "draft": "初稿正文（只放正文，不要加任何说明、标题、围栏）",
            "self_check": {
                "good": ["你自己认为写得好的地方（1~3 条）"],
                "weak": ["你自己知道还不行的地方（1~3 条）"],
            },
            "must_keep_used": ["你确实写进正文的硬信息"],
        })
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def build_review_prompt(brief, card, draft):
    """审稿：出问题清单，可打回。**输入 = 用户材料 + 选题卡 + 稿件正文**。

    ⚠️ 这里**没有**写手的 `self_check`、也没有写手的 `must_keep_used` 自报。
    这是本包信息不对称的第一条，由 assert_isolation() 在调用前验证。
    """
    return (
        "请审下面这篇稿子。\n"
        + "\n选题卡（判断稿子有没有偏离它）：\n" + _card_block(card)
        + "\n\n审稿口径：\n"
          "  · 结构：能不能一眼看出「开头给处境 → 中间拆解 → 结尾给结论/行动」的推进。\n"
          "  · 逻辑：论据有没有支撑它自己的结论，有没有前后矛盾。\n"
          "  · 可读性：句子长度、指代是否明确、有没有读两遍才懂的句子。\n"
          "  · 信息密度：单位字数里有多少可验证的具体信息（数字、条件、步骤、边界）。\n"
          "  · 偏离选题卡（角度跑偏、论据支柱没落实）算**高**严重度。\n"
        + "\n" + _PROMPT_SAMPLE_BLOCK
        + "\n裁决口径：\n"
          "  · 只要有**任何一条** 高 严重度的问题，`verdict` 必须是 `send_back`。\n"
          "  · `send_back` 时 `must_fix` 列出**必须修**的问题（引用它们的 id），"
          "写手会照着这份清单改。\n"
          "  · 挑不出问题就给 `pass` 与空 issues —— 但请确认你真的逐句看过了。\n"
        + _json_req({
            "verdict": "pass | send_back",
            "issues": [{
                "id": 1,
                "quote": "稿子里**原样**的一句话（或句中连续一小段）",
                "dims": ["structure|logic|readability|info_density|off_card"],
                "severity": "高|中|低",
                "why": "这句话为什么是问题",
                "fix": "改写后的具体句子",
            }],
            "must_fix": [1],
            "summary": "两三句总评",
        })
        + "\n补充要求：issues 最多 10 条，按 severity 从高到低排序，id 从 1 连续编号。"
          "**任何一条 高 严重度的问题都必须同时出现在 must_fix 里。**\n"
        + "\n===== 稿件全文开始 =====\n" + (draft or "") + "\n===== 稿件全文结束 =====\n"
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def build_revise_prompt(brief, card, draft, issues, facts, round_no):
    """写手修订：**输入 = 用户材料 + 选题卡 + 当前稿 + 必须修的问题清单**。

    ⚠️ 这是**审稿意见单向下行**：给的是"必须修什么"，不是审稿的系统提示词、
    不是审稿的偏好描述。写手看不到审稿角色的目标函数与裁决口径全文 ——
    它只拿到被锚定过的、可执行的那几条。
    """
    lines = []
    for it in issues:
        lines.append("  {}. [{}/{}] 原句：{}\n     问题：{}\n     建议改法：{}".format(
            it.get("id") or "-",
            "/".join(it.get("dims") or ["-"]),
            it.get("severity") or "-",
            it.get("sentence") or it.get("quote") or "",
            it.get("why") or "-", it.get("fix") or "-"))
    issue_block = "\n".join(lines) if lines else "  （无：本轮没有被点名的问题）"
    fact_lines = []
    for f in facts:
        if f["kind"] == "num":
            fact_lines.append("  · 数字 {}（原句：{}）".format(f["raw"], f["context"]))
        else:
            fact_lines.append("  · {}「{}」（原句：{}）".format(
                f.get("label") or "专名", f["raw"], f["context"]))
    fact_block = "\n".join(fact_lines) if fact_lines else "  （无）"
    return (
        "这是第 {} 轮修订。下面是当前稿子与审稿的**必须修清单**，请照单修改。\n".format(round_no)
        + "\n选题卡（不许改它定的角度）：\n" + _card_block(card)
        + "\n修改纪律（违反就整份作废）：\n"
          "  1. **只改清单点到的地方**。清单没点到的句子，除非与改动直接相邻，一个字都别动。\n"
          "  2. **事实清单里的每一项都必须原样保留**（数字、单位、专有名词一个都不能少、"
          "不能改口）。清单之外不许新增任何数字、机构名、人名。\n"
          "  3. 不许改变题材、不许改选题卡定的角度与论据支柱。\n"
          "  4. 不许把清单里的编号、字段名、本提示词的词句写进正文；"
          "不许输出 Markdown 代码围栏或占位符。\n"
          "  5. 如果某条 fix 会让句子明显变长，**先拆成两句**，不要把三层意思塞进一句。\n"
        + "\n===== 必须修清单（本地已逐条锚定到稿子里的句子）=====\n" + issue_block
        + "\n\n===== 必须原样保留的事实清单 =====\n" + fact_block
        + _json_req({
            "draft": "修订后的完整正文（只放正文，不要加任何说明、标题、围栏）",
            "fixes": [{
                "issue_id": 1,
                "before": "被改掉的那句原话",
                "after": "改成了什么",
                "why": "为什么这么改",
            }],
            "self_check": {
                "good": ["你自己认为这轮改得好的地方（1~3 条）"],
                "weak": ["你自己知道还不行的地方（1~3 条）"],
            },
        })
        + "\n补充要求：`fixes` 覆盖你**实际做过**的每一处修改，一处一条，"
          "`issue_id` 填你对应的是清单第几条；没被点名但顺手改了的地方 issue_id 填 0。"
          "**不要为了凑数编改动。**\n"
        + "\n===== 当前稿子开始 =====\n" + (draft or "") + "\n===== 当前稿子结束 =====\n"
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def build_compliance_prompt(brief, card, draft, stage_note=None):
    """合规：风险裁决。**输入 = 用户材料 + 选题卡元信息 + 稿件正文**。

    ⚠️ 这里**没有**审稿的 `issues`、**没有**审稿的 `verdict`、**没有**写手的 `self_check`。
    合规的提示词里还明写了一句"本团队内部没有向你提供任何风险结论"——
    这是本包信息不对称的第二条，由 assert_isolation() 在调用前验证。

    只给合规「标题 + 策划提示的风险点」，不给受众/痛点/差异化：给得越少，
    它越不得不从稿件正文本身独立判断，而不是顺着策划的框架走。
    """
    return (
        "请对下面这篇稿子做**发布前合规裁决**。\n"
        + (stage_note + "\n" if stage_note else "")
        + "\n选题卡元信息（**仅供你了解这篇稿子在讲什么，不构成任何风险结论**）：\n"
        + _card_block(card, with_meta_only=True)
        + "\n裁决口径：\n"
          "  · 广告法：绝对化用语（最高级、「第一」、100%、国家级）、无法举证的承诺、"
          "虚构权威背书。\n"
          "  · 事实：无出处的数字、把推测写成结论、自相矛盾的数据。\n"
          "  · 平台规则：站外导流、诱导分享、标题党、特殊品类敏感宣称。\n"
          "  · `verdict` 四选一：\n"
          "      pass      没有风险发现，可以发\n"
          "      fix       只有**个别可安全替换的措辞**问题（例如一个绝对化形容词），"
          "换掉即可，不影响结论\n"
          "      send_back 需要写手改结构或改写整段才能合规\n"
          "      veto      **一票否决**：事实造假、虚假承诺、违法违规品类，"
          "换词也救不回来\n"
          "  · 有 高 风险发现却判 pass 属于失职。\n"
        + _json_req({
            "verdict": "pass | fix | send_back | veto",
            "risk_level": "无 | 低 | 中 | 高",
            "findings": [{
                "quote": "稿子里**原样**的一段文字",
                "rule": "违反的是哪条规则（广告法第X条 / 平台规则X / 事实性）",
                "level": "高|中|低",
                "why": "为什么这是风险",
                "safe_replacement": "可安全替换的措辞（只在 verdict=fix 时给，其余给空字符串）",
            }],
            "reason": "裁决理由（必须写清：凭什么放行，或凭什么否决）",
        })
        + "\n补充要求：findings 最多 10 条，按 level 从高到低。"
          "判 `fix` 时 findings 必须**都**给了 `safe_replacement`；"
          "只要有 高 风险就必须是 `veto` 或 `send_back`，不许是 `fix` 或 `pass`。\n"
        + "\n===== 稿件全文开始 =====\n" + (draft or "") + "\n===== 稿件全文结束 =====\n"
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


# ===========================================================================
# 底层：OpenAI 兼容调用 + 健壮 JSON 解析
# ===========================================================================

class CtError(a7w.A7wError):
    """本流程里的所有可预期失败。子类各自带退出码。"""
    exit_code = EXIT_CALL


class UsageError(CtError):
    """参数/配置用错了（文件不存在、--outdir 在包内、给了 --budget 没给单价）。→ 2

    为什么要跟调用失败分开：这两类错误的**处理方式完全不同**。
    参数错了改命令重跑，不花一分钱；调用失败要查 Key / 点数 / 模型名。
    混成一个退出码，CI 里就没法区分「我命令写错了」和「网关挂了」。
    """
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """产出路径落在 Skill 包内（退出码 2）。"""


class GateFail(CtError):
    """硬闸门命中（退出码 3）。"""
    exit_code = EXIT_GATE


class BudgetStop(CtError):
    """预算超限，已就地中止（退出码 5）。"""
    exit_code = EXIT_BUDGET


class DryRunStop(CtError):
    """`--dry-run`：把这次调用**将要发出去的提示词**带出来，然后中止本次流程。

    为什么用异常而不是返回值：L3 一条链上有四五个角色、每轮好几次调用，
    返回值全靠位置约定，很容易取错字段（本包就踩过一次，`--dry-run` 打出了 null）。
    异常只有一条携带路径，调用方取不出别的东西，语义唯一。
    """
    exit_code = EXIT_OK

    def __init__(self, stage, prompt):
        super().__init__("dry-run：只打印提示词，不调用模型")
        self.stage = stage
        self.prompt = prompt


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
    结果崩在**钱已经扣之后**。本包一律自己发 urllib 请求，语义只有一种，
    不给误用的机会。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见，
    一次改写是一整篇稿子，被一次抖动打断要重跑整轮，很亏。
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
                raise CtError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise CtError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise CtError("模型不存在（404）：{}  "
                              "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise CtError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise CtError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 网关把 OpenAI 的返回包了一层 {"code":1,"data":{...}}，两种形态都认。
    # 实测成功响应**不带 code**，但兜底不能省。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise CtError("模型没返回 choices：{}".format(
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
        raise CtError("模型返回空内容")
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
    raise CtError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


# ===========================================================================
# 成本：token 标定 + 预算闸门
# ===========================================================================

# 字符 → token 的标定比例（**是同族实测值**，不是厂商文档）：
CHARS_PER_TOKEN_IN = 1.61
TOKENS_PER_CHAR_OUT = 1.11
POINTS_PER_YUAN = 100.0

# 各角色一次调用的输出 token 经验值（用于 cost 报价）
PLAN_OUT_TOKENS = 500
REVIEW_OUT_TOKENS = 700
COMPLIANCE_OUT_TOKENS = 400


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(brief_chars, target_chars, rounds, plan_retries=1, comp_send_back=1):
    """一次协作的调用清单（用于报价，越清楚越好）。**按最坏情况估**。

    轮次是"最多几轮"，报价要按上限估，否则用户会低估预算。
    额外把 1 次策划重开与 1 次合规打回算进去（都是常见路径）。
    """
    brief_in = int(round(brief_chars / CHARS_PER_TOKEN_IN))
    draft_out = int(round(target_chars * TOKENS_PER_CHAR_OUT))
    draft_in = int(round(target_chars / CHARS_PER_TOKEN_IN))
    calls = []
    n_plan = 1 + max(0, plan_retries)
    calls.append({"stage": "策划 · 选题卡", "calls": n_plan,
                  "tokens_in": (brief_in + 200) * n_plan,
                  "tokens_out": PLAN_OUT_TOKENS * n_plan,
                  "note": "输入只有用户材料；重开选题会再花一次（上界 {} 次）".format(n_plan)})
    calls.append({"stage": "写手 · 初稿", "calls": 1,
                  "tokens_in": brief_in + 500 + draft_in // 2,
                  "tokens_out": draft_out,
                  "note": "输入 = 用户材料 + 选题卡；出稿并附自评（自评不进审稿）"})
    n_rev = max(0, rounds)
    calls.append({"stage": "审稿 · 问题清单（每轮 1 次）", "calls": n_rev,
                  "tokens_in": (brief_in + 400 + draft_in) * n_rev,
                  "tokens_out": REVIEW_OUT_TOKENS * n_rev,
                  "note": "输入 = 用户材料 + 选题卡 + 稿件；**写手自评被排除**"})
    calls.append({"stage": "写手 · 修订（每轮 1 次）", "calls": n_rev,
                  "tokens_in": (brief_in + 900 + draft_in) * n_rev,
                  "tokens_out": draft_out * n_rev,
                  "note": "输入 = 当前稿 + 锚定过的必须修清单 + 事实清单"})
    n_comp = 1 + max(0, comp_send_back)
    calls.append({"stage": "合规 · 风险裁决", "calls": n_comp,
                  "tokens_in": (brief_in + 200 + draft_in) * n_comp,
                  "tokens_out": COMPLIANCE_OUT_TOKENS * n_comp,
                  "note": "输入 = 用户材料 + 选题卡元信息 + 稿件；**审稿意见被排除**；"
                          "上界 {} 次".format(n_comp)})
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
        if self.budget is None or not self.has_price:
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


# ===========================================================================
# 本地确定性闸门与评估
# ===========================================================================

def _clamp(v, lo=1, hi=10):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, v))


def char_count(text):
    """正文字符数（**不含空白**）——中英混排时这个数比 len() 更贴近"篇幅"。"""
    return len(re.sub(r"\s+", "", text or ""))


def length_band(target_chars):
    """目标篇幅的**可接受区间**：名义 ±15%，再叠加一个绝对容差。

    事故复盘（本包真机实测抓到的，不是推演）：只用 ±15% 时，目标 600 字的区间是
    510~690，而模型产出 **693 字** —— 超 3 个字判硬闸门命中、退出码 3、整轮产出作废。
    3 个字（0.5%）当成硬失败，是把闸门变成了噪声源：用户遇到几次就会把整道闸门关掉，
    而闸门关掉之后真正该拦的（丢事实、违禁词）也一起失效了。
    所以再叠一个 `max(15, 目标×2%)` 的绝对容差：600 字时上下各放宽 15 字 → 495~705，
    仍然拦得住"写了 900 字"或"只写了 200 字"这种真的跑偏。
    """
    slack = max(15, int(round(target_chars * 0.02)))
    return (int(round(target_chars * 0.85)) - slack,
            int(round(target_chars * 1.15)) + slack,
            slack)


def evaluate_gates(text, target_chars=None, anchor_stat=None, facts=None):
    """跑全部**本地**闸门，返回结构化结论。

    硬闸门 = compliance / placeholder / prompt_echo / length / anchor / facts 六项。
    """
    hits_c, exempted = compliance_scan(text)
    ph = placeholder_hits(text)
    echo = prompt_echo_scan(text)
    g = {
        "compliance": {
            "ok": not hits_c, "hits": hits_c, "exempted": exempted,
            "cap": (COMPLIANCE_CAP.get(hits_c[0]["level"]) if hits_c else None),
        },
        "placeholder": {"ok": not ph, "hits": ph},
        "prompt_echo": {"ok": not echo, "hits": echo},
    }
    if target_chars:
        lo, hi, slack = length_band(target_chars)
        n = char_count(text)
        g["length"] = {"ok": lo <= n <= hi, "chars": n, "lo": lo, "hi": hi,
                       "target": target_chars, "slack": slack,
                       "delta": (0 if lo <= n <= hi else (n - hi if n > hi else n - lo))}
    if anchor_stat is not None:
        g["anchor"] = anchor_stat
    if facts is not None:
        g["facts"] = facts
    return g


# 硬闸门清单（顺序即 stderr 汇总的显示顺序）
HARD_GATE_KEYS = ("compliance", "placeholder", "prompt_echo", "length", "anchor", "facts")


def gate_failed(gates):
    """硬闸门是否命中。"""
    for k in HARD_GATE_KEYS:
        v = gates.get(k)
        if isinstance(v, dict) and not v.get("ok", True):
            return True
    return False


def gate_failed_keys(gates):
    return [k for k in HARD_GATE_KEYS
            if isinstance(gates.get(k), dict) and not gates[k].get("ok", True)]


def apply_local_caps(dims, gates):
    """本地确定性扣分：违禁词压合规分、字数跑出区间压篇幅分。

    返回 (修正后的 dims, 扣分记录)。**关键**：峰值由本地定，模型给多高都压下来。
    """
    dims = dict(dims)
    ded = []
    c = gates.get("compliance") or {}
    if c and not c.get("ok") and c.get("cap") is not None:
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
        if dims.get("length_fit", 10) > cap:
            ded.append({"kind": "length", "dim": "length_fit",
                        "from": dims.get("length_fit"), "to": cap,
                        "why": "字数 {} 不在 {}~{} 区间（偏离 {} 字），篇幅分封顶 {}".format(
                            n, lo, hi, abs(off), cap)})
            dims["length_fit"] = cap
    a = gates.get("anchor") or {}
    if a and not a.get("ok", True):
        if dims.get("info_density", 10) > 5:
            ded.append({"kind": "anchor", "dim": "info_density",
                        "from": dims.get("info_density"), "to": 5,
                        "why": "问题清单未锚定率 {:.0%}，定位不可信 → 信息密度分封顶 5".format(
                            a.get("miss_rate", 0))})
            dims["info_density"] = 5
    return dims, ded


# ===========================================================================
# 断点续跑（`run` 用）
#
# 事故复盘（同族踩过三次）：
#   · 内容截断没进 key   → 把 8000 字截成 4000 字重跑，key 没变，静默复用了旧产物
#   · 口径改了没进 key   → 改了评分维度权重却不改 key，续跑复用了上一版口径的旧产物
#   · 死参数没进 key     → 参数调了但没生效，用户以为改过了
#
# 结论：**断点 key 必须含全部影响产出的维度**。L3 比 L2 多出来的维度是
# **各角色提示词版本**与**裁决口径版本** —— 它们变了产出就变，必须进 key。
# ===========================================================================

STATE_NAME = "state.json"
STATE_VERSION = 1


def state_key(stage, brief_sha=None, brief_chars=None, draft_sha=None, card_sha=None,
              model=None, temperature=None, round_no=None, target_chars=None,
              rounds=None, roles=ROLE_VERSION, prompt=PROMPT_VERSION,
              ruling=RULING_VERSION):
    """算一个断点 key：**所有影响产出的维度都在里面**。

      brief_sha / brief_chars   用户材料变了必须重跑（摘要防"改了一个字却复用"）
      draft_sha                 当前稿变了，这一轮的产出必然不同
      card_sha                  选题卡变了（策划重开过）必须重跑
      model / temperature       换模型或换温度就是换产出
      round_no                  第几轮；轮次不同产物不同
      target_chars              目标篇幅影响写手怎么写
      rounds                    总轮次变了，"是否已跑完"的判定就变了
      roles / prompt / ruling   角色提示词版本、提示词版本、裁决口径版本
    """
    payload = {
        "v": STATE_VERSION, "stage": stage,
        "brief_sha": brief_sha, "brief_chars": brief_chars,
        "draft_sha": draft_sha, "card_sha": card_sha,
        "model": model, "temperature": temperature, "round_no": round_no,
        "target_chars": target_chars, "rounds": rounds,
        "roles": roles, "prompt": prompt, "ruling": ruling,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "{}:{}".format(stage, hashlib.sha256(blob).hexdigest()[:20])


def text_sha(text):
    """内容摘要（先做换行/空白归一，避免"只改了行尾空白"导致无谓重跑）。"""
    norm = re.sub(r"[ \t\r]+", " ", (text or "")).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def file_sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def load_state(outdir):
    p = Path(outdir) / STATE_NAME
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
    p = Path(outdir) / STATE_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


# ===========================================================================
# 闸门：`--outdir` 不许落在包内
#
# 为什么单独做一道闸门而不是"提示一下"：Skill 包的上传白名单只收
# `.md .py .txt .json .sh .js .yaml .yml .csv`，包内塞一张 png 会让上传直接 400。
# 写文件是**写操作**，写进去之前就要拦住。退出码 2（usage）：这是用法错误。
# ===========================================================================

def pkg_dir():
    return Path(__file__).resolve().parent.parent


def ensure_outside_pkg(outdir):
    """`--outdir` 在包内 → 抛 PackagePathError（退出码 2）。"""
    root = pkg_dir()
    try:
        target = Path(outdir).resolve()
    except OSError as exc:
        raise UsageError("产出目录不可用：{}（{}）".format(outdir, exc))
    if target == root or root in target.parents:
        raise PackagePathError(
            "产出目录不能落在 Skill 包内：{}（包根 {}）。\n"
            "原因：包里只应该有待发布的白名单文件（.md/.py/.txt/.json/.sh/.js/.yaml/.yml/.csv）。"
            "把产出（稿件、台账、REPORT、state.json）写进包里会污染交付物。"
            "请把 --outdir 指到包外（例如 %TEMP% 下）。"
            .format(target, root))
    return target


def ensure_outside_pkg_file(path):
    """单个产出文件同样不许落在包内。"""
    root = pkg_dir()
    target = Path(path).resolve()
    if root in target.parents:
        raise PackagePathError(
            "产出文件不能落在 Skill 包内：{}（包根 {}）。".format(target, root))
    return target


# ===========================================================================
# 角色调用（每个函数都先 assert_isolation，再花钱）
# ===========================================================================

def _role_call(stage, prompt, model, key, tracker, a, label, out_tokens,
               excluded_fields=None):
    """四个角色共用的调用外壳：**先验信息不对称 → 再核预算 → 才发请求**。

    顺序不能倒：如果隔离检查失败，这次调用**一个字都不该发出去**（省钱且不留假证据）。

    `--dry-run` 在这里抛 DryRunStop（携带提示词），不返回任何业务对象 ——
    这样调用方**不可能**把一个 None 当成产出继续往下走。
    返回 (obj, usage, elapsed, isolation_report, prompt_chars)
    """
    iso = assert_isolation(stage, prompt, excluded_fields)
    if a.dry_run:
        raise DryRunStop(stage, prompt)
    est_in = estimate_tokens_in(prompt)
    if tracker.over_budget(est_in, out_tokens):
        raise BudgetStop("预估成本已超预算，**未发起这次「{}」调用**（{}）".format(
            label, tracker.line()))
    sys.stderr.write("正在让 `{}` 出「{}」…\n".format(model, label))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPTS[stage], model=model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    tracker.add(usage, stage)
    obj = parse_first_json(content)
    return obj, usage, elapsed, iso, len(prompt)


def normalize_card(raw, attempt=1):
    """把策划的返回归一化 + 本地判"这张卡够不够打"。

    策划的否决权体现在这里：`angle` 太短、太泛（含"多维度/全面/综合"这类词）、
    三条支柱不足或互为同义改写 —— 都判 `ok=False`，触发重开。
    """
    raw = raw if isinstance(raw, dict) else {}
    pillars = [str(p).strip() for p in (raw.get("pillars") or []) if str(p or "").strip()]
    card = {
        "attempt": attempt,
        "title": (raw.get("title") or "").strip(),
        "audience": (raw.get("audience") or "").strip(),
        "pain": (raw.get("pain") or "").strip(),
        "angle": (raw.get("angle") or "").strip(),
        "differentiation": (raw.get("differentiation") or "").strip(),
        "pillars": pillars[:3],
        "must_keep": [str(x).strip() for x in (raw.get("must_keep") or []) if str(x or "").strip()],
        "risk_note": (raw.get("risk_note") or "").strip(),
    }
    problems = []
    if len(card["title"]) < 6:
        problems.append("标题太短（{} 字），看不出这篇在讲什么".format(len(card["title"])))
    if len(card["angle"]) < 10:
        problems.append("角度只有 {} 字，写手无法据此动笔".format(len(card["angle"])))
    vague = re.findall(r"多(?:个)?维度|全面(?:分析|覆盖)|综合(?:分析|来看)|深入探讨|浅谈",
                       card["angle"] + card["differentiation"])
    if vague:
        problems.append("角度/差异化里出现空话「{}」，这不是一个可执行的角度".format("、".join(set(vague))))
    if len(card["pillars"]) < 3:
        problems.append("论据支柱只有 {} 条，要求恰好 3 条".format(len(card["pillars"])))
    else:
        for i in range(len(card["pillars"])):
            for j in range(i + 1, len(card["pillars"])):
                if _similarity(card["pillars"][i], card["pillars"][j]) >= 0.55:
                    problems.append("论据支柱 {} 与 {} 是同一个意思（相似度 {:.2f}）".format(
                        i + 1, j + 1, _similarity(card["pillars"][i], card["pillars"][j])))
    if len(card["audience"]) < 4:
        problems.append("受众描述太泛（{}），要求具体到一类人".format(card["audience"] or "空"))
    card["problems"] = problems
    card["ok"] = not problems
    card["card_sha"] = text_sha(json.dumps(card, ensure_ascii=False, sort_keys=True))
    return card


def card_digest_for_compliance(card):
    """合规只拿到选题卡的**元信息**（标题 + 策划提示的风险点）。

    这个函数是"合规看不到什么"的第二层保证：即便 ROLES 配置被人改宽，
    送进合规提示词的仍然只有这一个窄字典。
    """
    card = card if isinstance(card, dict) else {}
    return {"title": card.get("title") or "", "risk_note": card.get("risk_note") or ""}


def normalize_review(raw, draft):
    """把审稿的返回归一化 + **本地锚点校验**。

    锚点失败（未锚定率 > ANCHOR_MAX_MISS）→ `anchor.ok=False`，
    未锚定的引文**不进写手的修订输入**（它本来就不可执行）。
    """
    raw = raw if isinstance(raw, dict) else {}
    issues_raw = [i for i in (raw.get("issues") or []) if isinstance(i, dict)][:10]
    # 锚点校验前先把作者/角色的自我评价类字段剔掉（审稿本就不该看到它们）
    ok_issues, bad_issues = anchor_issues(issues_raw, draft)
    for n, it in enumerate(ok_issues, 1):
        it["id"] = n
    total = len(ok_issues) + len(bad_issues)
    anchor_stat = {
        "ok": True, "total": total, "verified": len(ok_issues),
        "unanchored": len(bad_issues),
        "miss_rate": round(len(bad_issues) / float(total), 3) if total else 0.0,
        "rules": {}, "no_actionable": False,
    }
    for it in ok_issues:
        r = it.get("anchor_rule") or "-"
        anchor_stat["rules"][r] = anchor_stat["rules"].get(r, 0) + 1
    if total and anchor_stat["miss_rate"] > ANCHOR_MAX_MISS:
        anchor_stat["ok"] = False
        anchor_stat["why"] = ("{} 条问题里 {} 条的引文在稿子里找不到（未锚定率 {:.0%} > {:.0%}）"
                              "——审稿在编引文，这份清单不可执行".format(
                                  total, len(bad_issues), anchor_stat["miss_rate"], ANCHOR_MAX_MISS))

    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in ("pass", "send_back"):
        verdict = "send_back" if ok_issues else "pass"
    # 高严重度必须在 must_fix 里（提示词里要求过，本地兜底：漏了也补进去）
    high_ids = [it["id"] for it in ok_issues if (it.get("severity") or "").strip() == "高"]
    must_fix = []
    for x in (raw.get("must_fix") or []):
        try:
            must_fix.append(int(x))
        except (TypeError, ValueError):
            continue
    must_fix = sorted(set(must_fix) | set(high_ids))
    must_fix = [i for i in must_fix if i in {it["id"] for it in ok_issues}]
    # 本地裁决兜底：有 高 严重度问题却判 pass → 强制改判 send_back（不许自己给自己放行）
    forced = None
    if high_ids and verdict == "pass":
        verdict = "send_back"
        forced = ("审稿判了 pass，但清单里有 {} 条 高 严重度问题 —— "
                  "按裁决口径强制改判 send_back（本地兜底，不放行）".format(len(high_ids)))
    return {
        "verdict": verdict, "verdict_forced_reason": forced,
        "issues": ok_issues, "unanchored_issues": bad_issues, "must_fix": must_fix,
        "anchor": anchor_stat,
        "summary": (raw.get("summary") or "").strip(),
        "gate_failed": not anchor_stat["ok"],
    }


def normalize_compliance(raw, draft):
    """把合规的返回归一化 + **本地一致性兜底**。

    两条本地兜底（模型说了不算）：
      · 有 高 风险发现却判 pass/fix → 强制改判 veto（合规的否决权不能被模型自己放弃）
      · 判 fix 但没给 safe_replacement → 降级为 send_back（本地无法安全替换就不能自动改）
    """
    raw = raw if isinstance(raw, dict) else {}
    findings = []
    for i, f in enumerate([x for x in (raw.get("findings") or []) if isinstance(x, dict)][:10]):
        findings.append({
            "id": i + 1,
            "quote": (f.get("quote") or "").strip(),
            "rule": (f.get("rule") or "").strip(),
            "level": (f.get("level") or "").strip() or "中",
            "why": (f.get("why") or "").strip(),
            "safe_replacement": (f.get("safe_replacement") or "").strip(),
        })
    findings.sort(key=lambda x: LEVEL_ORDER.get(x["level"], 9))
    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in ("pass", "fix", "send_back", "veto"):
        verdict = "send_back"
    high = [f for f in findings if f["level"] == "高"]
    notes = []
    if high and verdict in ("pass", "fix"):
        notes.append("合规判了 {}，但有 {} 条 高 风险发现 —— 本地强制改判 veto"
                     "（一票否决权不许被模型自己放弃）".format(verdict, len(high)))
        verdict = "veto"
    if verdict == "fix" and not all(f["safe_replacement"] for f in findings):
        notes.append("合规判了 fix，但至少一条发现没给 safe_replacement —— "
                     "本地无法安全替换，降级为 send_back")
        verdict = "send_back"
    # 本地闸门与合规裁决必须互相印证：本地扫到高风险词而合规说 pass，也不放行
    hits, _ex = compliance_scan(draft)
    if hits and verdict == "pass":
        notes.append("本地违禁词扫描命中「{}」（{}风险），合规却判 pass —— "
                     "本地不放行，降级为 fix/send_back".format(hits[0]["word"], hits[0]["level"]))
        verdict = "fix" if all(h["word"] in SAFE_REPLACEMENTS for h in hits) else "send_back"
    return {
        "verdict": verdict, "risk_level": (raw.get("risk_level") or "").strip() or "未知",
        "findings": findings, "reason": (raw.get("reason") or "").strip(),
        "local_notes": notes,
        "local_hits": hits,
        "gate_failed": verdict == "veto",
    }


# ===========================================================================
# 全过程记录（谁在哪个阶段改了什么 / 谁否决了什么 / 引用原句）
#
# L3 的核心交付不是"一篇稿子"，而是"一篇稿子 + 它是怎么做出来的"。
# 每一条记录都带：阶段 / 角色 / 轮次 / 引用的原句 / 依据。
# 这份记录既是给人看的，也是本包唯一能自证"多角色真的在互审"的东西。
# ===========================================================================

def new_log():
    return {"entries": [], "rulings": [], "isolation": [], "facts": []}


def log_entry(log, stage, role, round_no, action, detail, quotes=None):
    e = {"seq": len(log["entries"]) + 1, "stage": stage, "role": role,
         "round": round_no, "action": action, "detail": detail,
         "quotes": quotes or []}
    log["entries"].append(e)
    return e


def log_ruling(log, role, round_no, decision, reason, quotes=None, forced_by_local=None):
    r = {"seq": len(log["rulings"]) + 1, "role": role, "round": round_no,
         "decision": decision, "reason": reason, "quotes": quotes or [],
         "forced_by_local": forced_by_local}
    log["rulings"].append(r)
    return r


def log_isolation(log, stage, iso_report, prompt_chars, round_no):
    log["isolation"].append({
        "stage": stage, "role": (ROLES.get(stage) or {}).get("name") or stage,
        "round": round_no, "prompt_chars": prompt_chars,
        "excluded_fields": iso_report["excluded"],
        "markers_checked": iso_report["markers_checked"],
        "leaked": iso_report["leaked"], "ok": iso_report["ok"],
    })


# ===========================================================================
# 渲染（人读的 Markdown）
# ===========================================================================

def _red(s, force_plain=False):
    if force_plain or not sys.stderr.isatty():
        return s
    return "\033[31m{}\033[0m".format(s)


def render_card_md(card, model, usage, elapsed):
    out = ["# 策划 · 选题卡", ""]
    if not card:
        out.append("（没有拿到选题卡）")
        return "\n".join(out)
    out.append("- 状态：{}".format("达标" if card.get("ok") else "**不达标（触发重开）**"))
    out.append("- 第 {} 次尝试".format(card.get("attempt")))
    out.append("")
    out.append("| 字段 | 内容 |")
    out.append("|---|---|")
    for k, label in (("title", "拟定标题"), ("audience", "受众"), ("pain", "痛点"),
                     ("angle", "角度"), ("differentiation", "差异化"),
                     ("risk_note", "策划提示的风险点")):
        out.append("| {} | {} |".format(label, card.get(k) or "-"))
    out.append("")
    out.append("## 论据支柱")
    out.append("")
    for i, p in enumerate(card.get("pillars") or [], 1):
        out.append("{}. {}".format(i, p))
    if not card.get("pillars"):
        out.append("（无）")
    out.append("")
    mk = card.get("must_keep") or []
    out.append("## 必须写进正文的硬信息")
    out.append("")
    for x in mk:
        out.append("- {}".format(x))
    if not mk:
        out.append("（无 —— 材料里没有硬信息，写手不许自己造数）")
    out.append("")
    if card.get("problems"):
        out.append("## 策划自评不达标的原因（本地判定）")
        out.append("")
        for p in card["problems"]:
            out.append("- {}".format(p))
        out.append("")
    out.append("_模型 `{}` · 输出 {} tokens · {:.1f}s_".format(
        model, (usage or {}).get("completion_tokens", "-"), elapsed))
    return "\n".join(out)


def render_draft_md(draft_text, self_check, model, usage, elapsed, round_no, label="初稿"):
    out = ["# 写手 · {}".format(label), ""]
    out.append("- 轮次：第 {} 轮".format(round_no))
    out.append("- 正文字符数（不含空白）：{}".format(char_count(draft_text)))
    out.append("")
    out.append("## 正文")
    out.append("")
    out.append(draft_text or "（空）")
    out.append("")
    out.append("## 写手自评（⚠️ 这一栏**不进审稿的上下文**）")
    out.append("")
    sc = self_check if isinstance(self_check, dict) else {}
    for key, title in (("good", "自己认为写得好的地方"), ("weak", "自己知道还不行的地方")):
        out.append("**{}**".format(title))
        out.append("")
        vals = sc.get(key) or []
        for v in vals:
            out.append("- {}".format(v))
        if not vals:
            out.append("（未提供）")
        out.append("")
    out.append("_模型 `{}` · 输出 {} tokens · {:.1f}s_".format(
        model, (usage or {}).get("completion_tokens", "-"), elapsed))
    return "\n".join(out)


def render_review_md(rev, model, usage, elapsed, round_no):
    out = ["# 审稿 · 问题清单（第 {} 轮）".format(round_no), ""]
    out.append("- 裁决：**{}**".format(
        "打回写手（send_back）" if rev["verdict"] == "send_back" else "放行（pass）"))
    out.append("- 问题条数：锚定成功 {} / 未锚定 {}（未锚定率 {:.0%}）".format(
        rev["anchor"]["verified"], rev["anchor"]["unanchored"], rev["anchor"]["miss_rate"]))
    out.append("- 必须修：{}".format(
        "、".join("#{}".format(i) for i in rev["must_fix"]) or "（无）"))
    if rev.get("verdict_forced_reason"):
        out.append("- ⚠️ 本地兜底：{}".format(rev["verdict_forced_reason"]))
    if not rev["anchor"]["ok"]:
        out.append("- ⚠️ **锚点闸门命中**：{}".format(rev["anchor"].get("why") or ""))
    out.append("")
    out.append("## 问题清单（逐条引用原句）")
    out.append("")
    for it in rev["issues"]:
        out.append("### #{} [{}] {}".format(it["id"], it.get("severity") or "-",
                                            "/".join(it.get("dims") or ["-"])))
        out.append("")
        out.append("- **引用的原句**（第 {} 句，锚定判据 `{}`）：{}".format(
            it.get("sent_no"), it.get("anchor_rule"), it.get("sentence") or it.get("quote")))
        out.append("- 问题：{}".format(it.get("why") or "-"))
        out.append("- 建议改法：{}".format(it.get("fix") or "-"))
        out.append("")
    if not rev["issues"]:
        out.append("（没有锚定成功的问题）")
        out.append("")
    if rev["unanchored_issues"]:
        out.append("## 被剔出的问题（引文在稿子里找不到）")
        out.append("")
        for it in rev["unanchored_issues"]:
            out.append("- 引文「{}」—— {}".format(
                (it.get("quote") or "")[:40], it.get("why_unverified") or ""))
        out.append("")
    out.append("## 总评")
    out.append("")
    out.append(rev.get("summary") or "（未提供）")
    out.append("")
    out.append("_模型 `{}` · 输出 {} tokens · {:.1f}s_".format(
        model, (usage or {}).get("completion_tokens", "-"), elapsed))
    return "\n".join(out)


def render_compliance_md(comp, model, usage, elapsed, round_no):
    label = {"pass": "放行（pass）", "fix": "可安全替换（fix）",
             "send_back": "打回写手（send_back）", "veto": "一票否决（veto）"}
    out = ["# 合规 · 风险裁决（第 {} 轮）".format(round_no), ""]
    out.append("- 裁决：**{}**".format(label.get(comp["verdict"], comp["verdict"])))
    out.append("- 自报风险等级：{}".format(comp.get("risk_level") or "-"))
    out.append("")
    out.append("## 裁决理由")
    out.append("")
    out.append(comp.get("reason") or "（未提供理由 —— 这一条本身不合格）")
    out.append("")
    if comp.get("local_notes"):
        out.append("## 本地兜底（模型说了不算）")
        out.append("")
        for n in comp["local_notes"]:
            out.append("- {}".format(n))
        out.append("")
    if comp.get("local_hits"):
        out.append("## 本地违禁词扫描")
        out.append("")
        for h in comp["local_hits"]:
            out.append("- 「{}」（{}风险）：{}　上下文：{}".format(
                h["word"], h["level"], h["why"], h["context"]))
        out.append("")
    out.append("## 风险发现")
    out.append("")
    for f in comp["findings"]:
        out.append("- **#{} [{}风险]** 引用：{}".format(f["id"], f["level"], f["quote"]))
        out.append("  - 规则：{}".format(f["rule"] or "-"))
        out.append("  - 为什么是风险：{}".format(f["why"] or "-"))
        if f["safe_replacement"]:
            out.append("  - 安全替代：{}".format(f["safe_replacement"]))
        out.append("")
    if not comp["findings"]:
        out.append("（没有风险发现）")
        out.append("")
    out.append("_模型 `{}` · 输出 {} tokens · {:.1f}s_".format(
        model, (usage or {}).get("completion_tokens", "-"), elapsed))
    return "\n".join(out)


def render_log_md(log, escalation, convergence, final_text, gates, cost_rec):
    out = ["# 全过程记录", ""]
    out.append("这份记录回答三个问题：**每个角色交了什么**、**谁否掉了什么**、**为什么**。")
    out.append("")
    out.append("## 角色与职权")
    out.append("")
    out.append("| 角色 | 目标函数 | 产出物 | 否决权 |")
    out.append("|---|---|---|---|")
    for k in ROLE_ORDER:
        r = ROLES[k]
        out.append("| **{}** | {} | {} | {} |".format(
            r["name"], r["goal"], r["deliverable"], r["veto"]))
    out.append("")
    out.append("## 裁决记录（谁否掉了什么）")
    out.append("")
    if log["rulings"]:
        out.append("| # | 角色 | 轮次 | 裁决 | 理由 | 引用原句 | 本地兜底 |")
        out.append("|---|---|---|---|---|---|---|")
        for r in log["rulings"]:
            q = "；".join("「{}」".format(x[:24]) for x in (r["quotes"] or [])[:2]) or "-"
            out.append("| {} | {} | {} | **{}** | {} | {} | {} |".format(
                r["seq"], r["role"], r["round"], r["decision"],
                (r["reason"] or "-")[:70], q, r.get("forced_by_local") or "-"))
    else:
        out.append("（没有裁决记录）")
    out.append("")
    out.append("## 动作流水（谁在第几轮改了什么）")
    out.append("")
    out.append("| # | 阶段 | 角色 | 轮次 | 动作 | 说明 |")
    out.append("|---|---|---|---|---|---|")
    for e in log["entries"]:
        out.append("| {} | {} | {} | {} | {} | {} |".format(
            e["seq"], e["stage"], e["role"], e["round"], e["action"],
            (e["detail"] or "").replace("|", "／")[:110]))
    out.append("")
    out.append("## 信息不对称验证（每次调用前本地实检）")
    out.append("")
    out.append("被排除的字段**不允许出现在该角色的提示词文本里**，每次调用前扫一遍标记词。")
    out.append("")
    out.append("| 阶段 | 角色 | 轮次 | 提示词字符数 | 被排除的字段 | 检查的标记词数 | 泄漏 | 结论 |")
    out.append("|---|---|---|---|---|---|---|---|")
    for r in log["isolation"]:
        out.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["stage"], r["role"], r["round"], r["prompt_chars"],
            "、".join(r["excluded_fields"]) or "（无）", r["markers_checked"],
            "、".join("{}/{}".format(l["field"], l["marker"]) for l in r["leaked"]) or "无",
            "通过" if r["ok"] else "**不通过（已中止）**"))
    out.append("")
    out.append("## 终止判定")
    out.append("")
    out.append("- 收敛：{}".format("是" if convergence.get("converged") else "**否**"))
    out.append("- 原因：{}".format(convergence.get("why") or "-"))
    if escalation:
        out.append("- 出口：**{}** —— {}".format(
            escalation["kind"], EXIT_KIND.get(escalation["kind"], "")))
        out.append("- 未决项：")
        for u in escalation.get("unresolved") or ["（无）"]:
            out.append("  - {}".format(u))
    else:
        out.append("- 出口：无（全流程走通，合规放行）")
    out.append("")
    out.append("## 定稿硬闸门")
    out.append("")
    hit = gate_failed_keys(gates)
    if hit:
        for k in hit:
            out.append("- **{}**：{}".format(k, json.dumps(
                gates[k], ensure_ascii=False)[:300]))
    else:
        out.append("- 全部通过")
    out.append("")
    out.append("## 定稿正文（{} 字符）".format(char_count(final_text)))
    out.append("")
    out.append(final_text or "（空）")
    out.append("")
    if cost_rec:
        out.append("## 成本")
        out.append("")
        out.append("- 调用 {} 次 · prompt {} + completion {} = {} tokens".format(
            cost_rec["calls"], cost_rec["prompt_tokens"],
            cost_rec["completion_tokens"], cost_rec["total_tokens"]))
        if cost_rec.get("points") is None:
            out.append("- 金额：**网关不公布文本单价，未折算**"
                       "（要折算请传 --price-in / --price-out）")
        else:
            out.append("- 估算 {:g} 点 ≈ ¥{:g}（按你填的单价）".format(
                cost_rec["points"], cost_rec["yuan"]))
    return "\n".join(out)


def render_roles_md():
    out = ["# 三剪客 · 内容团队 —— 四个角色与职权", ""]
    out.append("**产品线 L3（多智能体协作型）。** 与 L2（单角色自我迭代）的分界：")
    out.append("角色各有目标函数与产出物、**角色之间能否掉彼此**、有明确裁决与出口。")
    out.append("")
    out.append("## 职权表")
    out.append("")
    out.append("| 角色 | 目标函数 | 产出物 | 否决权 | 谈不拢时的出口 |")
    out.append("|---|---|---|---|---|")
    for k in ROLE_ORDER:
        r = ROLES[k]
        out.append("| **{}** (`{}`) | {} | {} | {} | {} |".format(
            r["name"], k, r["goal"], r["deliverable"], r["veto"], r["exit_on_fail"]))
    out.append("")
    out.append("## 信息不对称（L3 的立身之本）")
    out.append("")
    out.append("「一个模型演四个角色」的致命之处：四个角色共享同一份上下文，")
    out.append("于是审稿永远看不到一个它不知道的自评、合规永远顺着审稿的结论走 —— **对抗是假的**。")
    out.append("本包把「看不到什么」写成字段白名单，并在**每次调用前**用文本级检查验证。")
    out.append("")
    out.append("| 角色 | 允许进入上下文 | **被显式排除** |")
    out.append("|---|---|---|")
    for k in ROLE_ORDER:
        r = ROLES[k]
        out.append("| {} | {} | {} |".format(
            r["name"], "、".join(r["inputs"]),
            "、".join(r["forbidden"]) or "（无）"))
    out.append("")
    out.append("两条最关键的排除：")
    out.append("")
    out.append("1. **写手的自评（`self_check`）不进审稿的上下文** —— "
               "审稿只看到选题卡与正文，不知道作者自己觉得哪里好、哪里弱。")
    out.append("2. **审稿的问题清单（`issues`）不进合规的上下文** —— "
               "合规只看到选题卡元信息与正文，提示词里明说"
               "「本团队内部没有向你提供任何风险结论」。")
    out.append("")
    out.append("## 裁决与终止条件")
    out.append("")
    out.append("| 出口 | 含义 |")
    out.append("|---|---|")
    for k, v in EXIT_KIND.items():
        out.append("| `{}` | {} |".format(k, v))
    out.append("")
    out.append("## 一次协作的调用顺序")
    out.append("")
    out.append("```")
    out.append("策划 plan ──▶ 写手 draft ──▶ 审稿 review ──┬─ pass ──▶ 合规 compliance ──┬─ pass/fix ──▶ 定稿")
    out.append("   ▲                ▲                        │                            ├─ send_back ─┐")
    out.append("   │                └──── 必须修清单 ──────────┘ send_back                   └─ veto ──────┼─▶ 带未决项产出")
    out.append("   └── 选题卡不达标 / 重开（上限 --plan-retries）        └────── 修订（上限 --rounds）───┘")
    out.append("```")
    out.append("")
    out.append("**审稿与合规是串行关系，不是投票**：审稿不过就轮不到合规；"
               "审稿过了合规仍可独立否决。")
    return "\n".join(out)


# ===========================================================================
# 读取与校验
# ===========================================================================

def read_text(path, what="文件"):
    if not path:
        raise UsageError("{}的路径是空的（命令里少了这个参数？）".format(what))
    p = Path(path)
    if not p.is_file():
        raise UsageError("{}不存在：{}".format(what, path))
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise UsageError("读不了{}：{}（{}）".format(what, path, exc))
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UsageError("{}不是 UTF-8/GB18030 文本：{}".format(what, path))


def check_budget(a):
    if a.budget is not None and (a.price_in is None or a.price_out is None):
        raise UsageError("用了 --budget 就必须给 --price-in / --price-out —— "
                         "不给单价无法核预算，本包**不会**替你编一个单价。")


def check_target_chars(n):
    if n < TARGET_CHARS_MIN or n > TARGET_CHARS_MAX:
        raise UsageError("--target-chars {} 超出可用区间 {}~{}。".format(
            n, TARGET_CHARS_MIN, TARGET_CHARS_MAX))
    return int(n)


def check_positive(name, v, allow_zero=True):
    lo = 0 if allow_zero else 1
    if v is None or int(v) < lo:
        raise UsageError("{} 必须 ≥ {}（给的是 {}）".format(name, lo, v))
    return int(v)


def card_from_file(path):
    """读一份 `plan --json --out` 的结果当选题卡（零成本复用）。"""
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        raise UsageError("选题卡文件不存在：{}".format(path))
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("选题卡文件不是合法 JSON：{}（{}）".format(path, exc))
    card = obj.get("card") if isinstance(obj, dict) and isinstance(obj.get("card"), dict) else obj
    if not isinstance(card, dict) or not card.get("angle"):
        raise UsageError("选题卡文件里没有可用的 card.angle：{}".format(path))
    if "ok" not in card:
        card = normalize_card(card, attempt=int(card.get("attempt") or 1))
    return card


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


def fmt_cost_dict(tracker):
    pts = tracker.points
    return {"calls": tracker.calls,
            "prompt_tokens": tracker.prompt_tokens,
            "completion_tokens": tracker.completion_tokens,
            "total_tokens": tracker.total_tokens,
            "points": None if pts is None else round(pts, 4),
            "yuan": None if pts is None else round(pts / POINTS_PER_YUAN, 4),
            "priced": tracker.has_price}


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


def _gate_stderr(label, gates):
    """把硬闸门命中汇总到 stderr（标红 + 逐条原因），返回是否命中。"""
    hit = [(k, gates[k]) for k in HARD_GATE_KEYS
           if isinstance(gates.get(k), dict) and not gates[k].get("ok", True)]
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
            sys.stderr.write("   [篇幅] {} 不在 {}~{} 区间（偏离 {} 字）\n".format(
                v["chars"], v["lo"], v["hi"], abs(v["delta"])))
        elif k == "anchor":
            sys.stderr.write("   [审稿锚点] {}（已锚定 {} / {} 条）\n".format(
                v.get("why") or "未锚定率过高", v.get("verified"), v.get("total")))
        elif k == "facts":
            sys.stderr.write("   [事实保全] 丢了 {} 条：{}\n".format(
                len(v.get("lost") or []),
                "、".join("「{}」".format(f["raw"]) for f in (v.get("lost") or [])[:8])))
    ex = (gates.get("compliance") or {}).get("exempted") or []
    if ex:
        sys.stderr.write("   提示：本地放过 {} 处疑似绝对化用语（判为普通用法），请人工确认："
                         "{}\n".format(len(ex), "、".join("「{}」".format(e["word"]) for e in ex)))
    return True


# ===========================================================================
# 子命令：roles（零成本）
# ===========================================================================

def run_roles(a):
    result = {
        "mode": "roles", "role_version": ROLE_VERSION,
        "roles": [{
            "key": k, "name": ROLES[k]["name"], "goal": ROLES[k]["goal"],
            "deliverable": ROLES[k]["deliverable"], "veto": ROLES[k]["veto"],
            "inputs": ROLES[k]["inputs"], "forbidden": ROLES[k]["forbidden"],
            "exit_on_fail": ROLES[k]["exit_on_fail"],
        } for k in ROLE_ORDER],
        "exits": EXIT_KIND,
        "isolation": {
            "self_check_not_in_reviewer": (
                "写手的 self_check 被显式排除在审稿上下文之外（ROLES.reviewer.forbidden），"
                "每次调用前由 assert_isolation 做文本级检查，泄漏则中止调用并退出码 3"),
            "issues_not_in_compliance": (
                "审稿的 issues 被显式排除在合规上下文之外（ROLES.compliance.forbidden），"
                "合规提示词里明写「本团队内部没有向你提供任何风险结论」"),
            "markers": ISOLATION_MARKERS,
        },
        "note": "本包是 L3：角色各有目标函数与产出物，且**能否掉彼此**。"
                "若审稿逐条放行、合规永不出问题，那就是假协作 —— 看 log 的裁决记录。",
    }
    _emit(a, result, render_roles_md(), ok=True)
    return EXIT_OK


# ===========================================================================
# 子命令：plan
# ===========================================================================

def plan_once(a, brief, target_chars, model, key, tracker, attempt, attempt_note, outdir,
              state=None, brief_sha=None):
    """跑一次策划。返回 (card, usage, elapsed, iso, prompt_chars)。

    ⚠️ `--dry-run` 下**抛 DryRunStop 把提示词带出来**，而不是返回一个"假的 card"。
    事故复盘（本包自测时踩到的）：早先的版本返回 `(None, prompt, ...)`，
    调用方把第一个返回值当 card 去 print，于是 `--dry-run` 只打出一个 `None` ——
    dry-run 的全部价值就是让你看清将要发出去的提示词，打 null 等于这个开关废了。
    改成异常传递后，"提示词"只能从异常对象里取，调用方不可能再取错字段。
    """
    skey = state_key("plan", brief_sha=brief_sha, brief_chars=char_count(brief),
                     model=model, temperature=a.temperature, round_no=attempt,
                     target_chars=target_chars, rounds=0)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("策划（第 {} 次尝试）已在断点里，跳过（零成本）。\n".format(attempt))
            return normalize_card(hit["raw"], attempt), hit.get("usage") or {}, 0.0, \
                hit.get("iso") or {"excluded": [], "markers_checked": 0, "leaked": [], "ok": True}, \
                hit.get("prompt_chars") or 0
    prompt = build_plan_prompt(brief, target_chars, attempt_note)
    obj, usage, elapsed, iso, pchars = _role_call(
        "planner", prompt, model, key, tracker, a, "选题卡", PLAN_OUT_TOKENS)
    card = normalize_card(obj, attempt)
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "raw": {k: card.get(k) for k in
                    ("title", "audience", "pain", "angle", "differentiation",
                     "pillars", "must_keep", "risk_note")},
            "usage": usage, "iso": iso, "prompt_chars": pchars}
        if outdir:
            save_state(outdir, state)
    return card, usage, elapsed, iso, pchars


def run_plan(a):
    brief = read_text(a.brief, "用户材料")
    if not brief.strip():
        raise UsageError("用户材料是空的：{}".format(a.brief))
    target_chars = check_target_chars(a.target_chars)
    check_budget(a)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = state = None
    if a.outdir:
        outdir = ensure_outside_pkg(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    retries = check_positive("--plan-retries", a.plan_retries)
    log = new_log()
    tried, card, usage, elapsed, iso, pchars = [], None, {}, 0.0, None, 0
    for attempt in range(1, retries + 2):
        note = None
        if tried:
            note = ("上一次的选题卡被本地判为不达标，原因：\n"
                    + "\n".join("  · " + p for p in tried[-1]["problems"])
                    + "\n请换一个角度重出，**不要只是把上一版换几个词**。")
        card, usage, elapsed, iso, pchars = plan_once(
            a, brief, target_chars, a.model, a.key, tracker, attempt, note, outdir,
            state, text_sha(brief))
        log_isolation(log, "planner", iso, pchars, attempt)
        tried.append(card)
        log_entry(log, "plan", "策划", attempt,
                  "交选题卡", "标题「{}」；角度：{}；{}".format(
                      card["title"], card["angle"],
                      "达标" if card["ok"] else "**不达标**：" + "；".join(card["problems"])))
        if card["ok"]:
            log_ruling(log, "策划", attempt, "accepted",
                       "选题卡达标：角度具体、三条支柱互不重义", [card.get("angle") or ""])
            break
        log_ruling(log, "策划", attempt, "rejected",
                   "选题卡不达标（重开）", card["problems"])
    rc = EXIT_OK
    escalation = None
    if card and not card["ok"]:
        escalation = {"kind": "plan_retries_exhausted", "rounds_run": len(tried),
                      "unresolved": card["problems"]}
        rc = EXIT_GATE
        sys.stderr.write("\n{}\n".format(_red(
            "策划重开上限（--plan-retries {}）用尽，选题卡仍不达标 —— "
            "升级给人看，不硬着头皮往下写。".format(retries))))
    result = {
        "mode": "plan", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model, "target_chars": target_chars,
        "brief": {"path": str(a.brief), "sha": text_sha(brief), "chars": char_count(brief)},
        "attempts": len(tried), "card": card, "escalation": escalation,
        "log": log, "usage": usage, "elapsed": elapsed,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
    }
    if outdir is not None:
        (outdir / "plan.json").write_text(
            json.dumps({"card": card, "attempts": tried, "escalation": escalation},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "plan.md").write_text(
            render_card_md(card, a.model, usage, elapsed) + "\n", encoding="utf-8")
        sys.stderr.write("目录产物：{}（plan.json / plan.md）\n".format(outdir))
    _emit(a, result, render_card_md(card, a.model, usage, elapsed), ok=not rc)
    return rc


# ===========================================================================
# 子命令：draft
# ===========================================================================

def normalize_draft_output(obj, what="draft"):
    """把写手的返回归一化。返回 (正文, 自评, fixes, must_keep_used)。"""
    obj = obj if isinstance(obj, dict) else {}
    text = obj.get(what)
    if not isinstance(text, str) or not text.strip():
        raise CtError("写手返回里没有可用的 `{}` 正文".format(what))
    sc = obj.get("self_check") if isinstance(obj.get("self_check"), dict) else {}
    fixes = [f for f in (obj.get("fixes") or []) if isinstance(f, dict)]
    return text.strip(), sc, fixes, [str(x) for x in (obj.get("must_keep_used") or [])]


def draft_once(a, brief, card, target_chars, model, key, tracker, outdir, state=None,
               brief_sha=None):
    skey = state_key("draft", brief_sha=brief_sha, brief_chars=char_count(brief),
                     card_sha=card.get("card_sha"), model=model,
                     temperature=a.temperature, target_chars=target_chars, rounds=0)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("初稿已在断点里，跳过（零成本）。\n")
            return (hit["draft"], hit.get("self_check") or {}, [], hit.get("must_keep_used") or [],
                    hit.get("usage") or {}, 0.0,
                    hit.get("iso") or {"excluded": [], "markers_checked": 0, "leaked": [], "ok": True},
                    hit.get("prompt_chars") or 0)
    prompt = build_draft_prompt(brief, card, target_chars)
    obj, usage, elapsed, iso, pchars = _role_call(
        "writer", prompt, model, key, tracker, a, "初稿", int(
            target_chars * TOKENS_PER_CHAR_OUT))
    text, sc, fixes, used = normalize_draft_output(obj, "draft")
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "draft": text, "self_check": sc, "must_keep_used": used,
            "usage": usage, "iso": iso, "prompt_chars": pchars}
        if outdir:
            save_state(outdir, state)
    return text, sc, fixes, used, usage, elapsed, iso, pchars


def _write_round_dir(outdir, round_no, payloads):
    d = Path(outdir) / "rounds" / "r{}".format(round_no)
    d.mkdir(parents=True, exist_ok=True)
    for name, body in payloads.items():
        (d / name).write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    return d


def run_draft(a):
    brief = read_text(a.brief, "用户材料")
    target_chars = check_target_chars(a.target_chars)
    card = card_from_file(a.card)
    if card is None:
        raise UsageError("draft 需要 --card 指一份 plan 交出的选题卡"
                         "（`run.py plan --brief ... --json --out plan.json`）")
    check_budget(a)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = state = None
    if a.outdir:
        outdir = ensure_outside_pkg(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    log = new_log()
    res = draft_once(a, brief, card, target_chars, a.model, a.key, tracker, outdir, state,
                     text_sha(brief))
    text, sc, fixes, used, usage, elapsed, iso, pchars = res
    log_isolation(log, "writer", iso, pchars, 1)
    log_entry(log, "draft", "写手", 1, "交初稿",
              "{} 字符；自评 {} 条（自评不进审稿上下文）".format(
                  char_count(text), len((sc or {}).get("good") or []) + len((sc or {}).get("weak") or [])))
    gates = evaluate_gates(text, target_chars)
    rc = EXIT_GATE if gate_failed(gates) else EXIT_OK
    if rc == EXIT_GATE:
        _gate_stderr("初稿", gates)
    result = {
        "mode": "draft", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model, "target_chars": target_chars,
        "brief": {"path": str(a.brief), "sha": text_sha(brief)},
        "card": card, "draft": text, "chars": char_count(text),
        "self_check": sc, "self_check_excluded_from": ["reviewer", "compliance"],
        "must_keep_used": used, "gates": gates, "gate_failed": gate_failed(gates),
        "log": log, "usage": usage, "elapsed": elapsed,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
    }
    if outdir is not None:
        _write_round_dir(outdir, 1, {
            "draft.md": render_draft_md(text, sc, a.model, usage, elapsed, 1),
            "draft.txt": text,
        })
        (outdir / "draft.json").write_text(
            json.dumps({"draft": text, "self_check": sc, "must_keep_used": used},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        sys.stderr.write("目录产物：{}（draft.json / rounds/r1/draft.md|txt）\n".format(outdir))
    _emit(a, result, render_draft_md(text, sc, a.model, usage, elapsed, 1), ok=not rc)
    return rc


# ===========================================================================
# 子命令：review
# ===========================================================================

def review_once(a, brief, card, draft, model, key, tracker, outdir, state=None,
                brief_sha=None, round_no=1):
    draft_sha = text_sha(draft)
    skey = state_key("review", brief_sha=brief_sha, brief_chars=char_count(brief),
                     draft_sha=draft_sha, card_sha=card.get("card_sha"), model=model,
                     temperature=a.temperature, round_no=round_no, rounds=a.rounds)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("第 {} 轮审稿已在断点里，跳过（零成本）。\n".format(round_no))
            return normalize_review(hit["raw"], draft), hit.get("usage") or {}, 0.0, \
                hit.get("iso") or {"excluded": [], "markers_checked": 0, "leaked": [], "ok": True}, \
                hit.get("prompt_chars") or 0
    prompt = build_review_prompt(brief, card, draft)
    obj, usage, elapsed, iso, pchars = _role_call(
        "reviewer", prompt, model, key, tracker, a, "问题清单", REVIEW_OUT_TOKENS)
    rev = normalize_review(obj, draft)
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "raw": {"verdict": obj.get("verdict") if isinstance(obj, dict) else None,
                    "issues": [{"quote": i.get("quote"), "dims": i.get("dims"),
                                "severity": i.get("severity"), "why": i.get("why"),
                                "fix": i.get("fix")} for i in
                               ((obj.get("issues") or []) if isinstance(obj, dict) else [])
                               if isinstance(i, dict)],
                    "must_fix": obj.get("must_fix") if isinstance(obj, dict) else [],
                    "summary": (obj.get("summary") if isinstance(obj, dict) else "") or ""},
            "usage": usage, "iso": iso, "prompt_chars": pchars}
        if outdir:
            save_state(outdir, state)
    return rev, usage, elapsed, iso, pchars


def run_review(a):
    brief = read_text(a.brief, "用户材料")
    draft = read_text(a.draft, "待审稿件")
    if not draft.strip():
        raise UsageError("待审稿件是空的：{}".format(a.draft))
    card = card_from_file(a.card)
    if card is None:
        raise UsageError("review 需要 --card 指一份选题卡（审稿要据此判断有没有偏离）")
    check_budget(a)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = state = None
    if a.outdir:
        outdir = ensure_outside_pkg(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    log = new_log()
    rev, usage, elapsed, iso, pchars = review_once(
        a, brief, card, draft, a.model, a.key, tracker, outdir, state, text_sha(brief),
        round_no=1)
    log_isolation(log, "reviewer", iso, pchars, 1)
    log_entry(log, "review", "审稿", 1, "出问题清单",
              "锚定 {} 条 / 未锚定 {} 条；裁决 {}".format(
                  rev["anchor"]["verified"], rev["anchor"]["unanchored"], rev["verdict"]),
              [it.get("sentence") or it.get("quote") for it in rev["issues"][:3]])
    if rev["verdict"] == "send_back":
        log_ruling(log, "审稿", 1, "send_back",
                   "{} 条问题必须在写手修订中处理（必须修 #{}）".format(
                       len(rev["issues"]), "、#".join(str(i) for i in rev["must_fix"])),
                   [it.get("sentence") or it.get("quote") for it in rev["issues"]
                    if it["id"] in rev["must_fix"]][:3],
                   forced_by_local=rev.get("verdict_forced_reason"))
    else:
        log_ruling(log, "审稿", 1, "pass", rev.get("summary") or "未发现问题")
    gates = evaluate_gates(draft, None, rev["anchor"])
    rc = EXIT_GATE if gate_failed(gates) else EXIT_OK
    if rc == EXIT_GATE:
        _gate_stderr("审稿", gates)
    result = {
        "mode": "review", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model, "brief": {"path": str(a.brief), "sha": text_sha(brief)},
        "draft": {"path": str(a.draft), "sha": text_sha(draft), "chars": char_count(draft)},
        "card": card, "verdict": rev["verdict"],
        "verdict_forced_reason": rev.get("verdict_forced_reason"),
        "issues": rev["issues"], "unanchored_issues": rev["unanchored_issues"],
        "must_fix": rev["must_fix"], "anchor": rev["anchor"],
        "summary": rev["summary"], "gatges_note": None, "gates": gates,
        "gate_failed": gate_failed(gates), "log": log,
        "usage": usage, "elapsed": elapsed,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
    }
    if outdir is not None:
        (outdir / "review.json").write_text(
            json.dumps({"verdict": rev["verdict"], "issues": rev["issues"],
                        "unanchored_issues": rev["unanchored_issues"],
                        "must_fix": rev["must_fix"], "anchor": rev["anchor"]},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "review.md").write_text(
            render_review_md(rev, a.model, usage, elapsed, 1) + "\n", encoding="utf-8")
        sys.stderr.write("目录产物：{}（review.json / review.md）\n".format(outdir))
    _emit(a, result, render_review_md(rev, a.model, usage, elapsed, 1), ok=not rc)
    return rc


# ===========================================================================
# 子命令：compliance
# ===========================================================================

def compliance_once(a, brief, card, draft, model, key, tracker, outdir, state=None,
                    brief_sha=None, round_no=1):
    draft_sha = text_sha(draft)
    skey = state_key("compliance", brief_sha=brief_sha, brief_chars=char_count(brief),
                     draft_sha=draft_sha, model=model, temperature=a.temperature,
                     round_no=round_no, rounds=a.rounds)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("第 {} 轮合规裁决已在断点里，跳过（零成本）。\n".format(round_no))
            return normalize_compliance(hit["raw"], draft), hit.get("usage") or {}, 0.0, \
                hit.get("iso") or {"excluded": [], "markers_checked": 0, "leaked": [], "ok": True}, \
                hit.get("prompt_chars") or 0
    meta = card_digest_for_compliance(card)
    stage_note = None
    if round_no > 1:
        stage_note = ("这是第 {} 轮的合规复核。**上一轮合规的意见没有随本次调用附上**，"
                      "请只依据下面这份正文独立裁决。".format(round_no))
    prompt = build_compliance_prompt(brief, meta, draft, stage_note)
    obj, usage, elapsed, iso, pchars = _role_call(
        "compliance", prompt, model, key, tracker, a, "风险裁决", COMPLIANCE_OUT_TOKENS)
    comp = normalize_compliance(obj, draft)
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "raw": {"verdict": obj.get("verdict") if isinstance(obj, dict) else None,
                    "risk_level": obj.get("risk_level") if isinstance(obj, dict) else None,
                    "findings": obj.get("findings") if isinstance(obj, dict) else [],
                    "reason": (obj.get("reason") if isinstance(obj, dict) else "") or ""},
            "usage": usage, "iso": iso, "prompt_chars": pchars}
        if outdir:
            save_state(outdir, state)
    return comp, usage, elapsed, iso, pchars


def run_compliance(a):
    # ⚠️ `--brief` 在本子命令里是**可选**的，不给时默认是 None。
    # 事故复盘（本包自测抓到）：早先直接把它传给 read_text()，于是
    # `compliance --draft x.md`（不给 --brief，完全合法的用法）崩在
    # `TypeError: expected str, bytes or os.PathLike object, not NoneType` —
    # 一个**用法问题**被报成了 kind=internal（退出码 1）。internal 是留给
    # 真 bug 的，把它用来兜"用户少给一个可选参数"，等于把契约里的
    # 「internal = 我没预料到」这条语义废掉。所以这里显式降级成空材料。
    brief = read_text(a.brief, "用户材料") if a.brief else ""
    draft = read_text(a.draft, "待裁稿件")
    if not draft.strip():
        raise UsageError("待裁稿件是空的：{}".format(a.draft))
    card = card_from_file(a.card) or {}
    check_budget(a)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = state = None
    if a.outdir:
        outdir = ensure_outside_pkg(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    log = new_log()
    comp, usage, elapsed, iso, pchars = compliance_once(
        a, brief, card, draft, a.model, a.key, tracker, outdir, state, text_sha(brief), 1)
    log_isolation(log, "compliance", iso, pchars, 1)
    log_entry(log, "compliance", "合规", 1, "风险裁决",
              "{}；{} 条发现；本地扫描命中 {} 处".format(
                  comp["verdict"], len(comp["findings"]), len(comp["local_hits"])))
    log_ruling(log, "合规", 1, comp["verdict"], comp.get("reason") or "（未给理由）",
               [f["quote"] for f in comp["findings"][:3]],
               forced_by_local="；".join(comp["local_notes"]) or None)
    rc = EXIT_GATE if comp["verdict"] == "veto" else EXIT_OK
    if comp["verdict"] == "veto":
        sys.stderr.write("\n{}\n".format(_red(
            "合规一票否决：{}".format(comp.get("reason") or "未给理由"))))
    result = {
        "mode": "compliance", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model, "brief": {"path": str(a.brief), "sha": text_sha(brief)},
        "draft": {"path": str(a.draft), "sha": text_sha(draft), "chars": char_count(draft)},
        "card_meta_given_to_compliance": card_digest_for_compliance(card),
        "verdict": comp["verdict"], "risk_level": comp["risk_level"],
        "findings": comp["findings"], "reason": comp["reason"],
        "local_notes": comp["local_notes"], "local_hits": comp["local_hits"],
        "log": log, "usage": usage, "elapsed": elapsed,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
    }
    if outdir is not None:
        (outdir / "compliance.json").write_text(
            json.dumps({k: result[k] for k in
                        ("verdict", "risk_level", "findings", "reason",
                         "local_notes", "local_hits")}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        (outdir / "compliance.md").write_text(
            render_compliance_md(comp, a.model, usage, elapsed, 1) + "\n", encoding="utf-8")
        sys.stderr.write("目录产物：{}（compliance.json / compliance.md）\n".format(outdir))
    _emit(a, result, render_compliance_md(comp, a.model, usage, elapsed, 1), ok=not rc)
    return rc


# ===========================================================================
# 子命令：run —— 一条命令跑完整协作
# ===========================================================================

def revise_once(a, brief, card, draft, issues, facts, model, key, tracker, round_no,
                outdir, state=None, brief_sha=None):
    draft_sha = text_sha(draft)
    skey = state_key("revise", brief_sha=brief_sha, brief_chars=char_count(brief),
                     draft_sha=draft_sha, card_sha=card.get("card_sha"), model=model,
                     temperature=a.temperature, round_no=round_no, rounds=a.rounds)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("第 {} 轮修订已在断点里，跳过（零成本）。\n".format(round_no))
            return (hit["draft"], hit.get("self_check") or {}, hit.get("fixes") or [],
                    hit.get("usage") or {}, 0.0,
                    hit.get("iso") or {"excluded": [], "markers_checked": 0, "leaked": [], "ok": True},
                    hit.get("prompt_chars") or 0)
    prompt = build_revise_prompt(brief, card, draft, issues, facts, round_no)
    obj, usage, elapsed, iso, pchars = _role_call(
        "writer", prompt, model, key, tracker, a, "第 {} 轮修订".format(round_no),
        int(char_count(draft) * TOKENS_PER_CHAR_OUT))
    text, sc, fixes, _used = normalize_draft_output(obj, "draft")
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "draft": text, "self_check": sc, "fixes": fixes,
            "usage": usage, "iso": iso, "prompt_chars": pchars}
        if outdir:
            save_state(outdir, state)
    return text, sc, fixes, usage, elapsed, iso, pchars


def run_run(a):
    """一条命令走完：策划 → 写手 → 审稿 → 写手修订 → 合规，带裁决、轮次上限与出口。"""
    if getattr(a, "out", None):
        # `run` 的产物是一个**目录**（final.md / REPORT.md / log.json / rounds/ …），
        # 不是单个文件。同族踩过 "--out 被静默当成 --outdir 的缩写"，
        # 本包不允许长选项缩写，但 `run` 子命令又确实注册了 --out（共用模型选项组），
        # 于是 `run --out x.json` 会被**收下却完全没用** —— 用户以为写盘了。
        # 与其留一个静默无效的参数，不如直接报用法错。
        raise UsageError(
            "`run` 没有单文件产出，请用 --outdir 指定产出目录"
            "（final.md / final.json / REPORT.md / log.json / plan.json / rounds/）。"
            "要单文件结果请用 plan / draft / review / compliance 的 --out。")
    brief = read_text(a.brief, "用户材料")
    if not brief.strip():
        raise UsageError("用户材料是空的：{}".format(a.brief))
    target_chars = check_target_chars(a.target_chars)
    rounds = check_positive("--rounds", a.rounds)
    plan_retries = check_positive("--plan-retries", a.plan_retries)
    comp_max = check_positive("--compliance-sendback", a.compliance_sendback)
    check_budget(a)
    if rounds < 1:
        raise UsageError("--rounds 至少为 1 —— 本包的语义是"
                         "「策划 → 写手 → 审稿 → 修订」，0 轮没有协作可谈"
                         "（只要质检不要协作请用 L2 的内容质量闭环）。")

    outdir = ensure_outside_pkg(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)

    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    log = new_log()
    usages = []
    rulings_summary = {"reviewer_send_back": 0, "compliance_veto": 0,
                       "compliance_send_back": 0, "planner_reject": 0}

    # ---------------- 1) 策划 ----------------
    card, tried, plan_iso = None, [], []
    for attempt in range(1, plan_retries + 2):
        note = None
        if tried:
            note = ("上一次的选题卡被本地判为不达标，原因：\n"
                    + "\n".join("  · " + p for p in tried[-1]["problems"])
                    + "\n请换一个角度重出，**不要只是把上一版换几个词**。")
        card, usage, elapsed, iso, pchars = plan_once(
            a, brief, target_chars, a.model, a.key, tracker, attempt, note, outdir,
            state, text_sha(brief))
        usages.append(usage)
        log_isolation(log, "planner", iso, pchars, attempt)
        tried.append(card)
        log_entry(log, "plan", "策划", attempt, "交选题卡",
                  "标题「{}」；{}".format(
                      card["title"], "达标" if card["ok"] else "不达标：" + "；".join(card["problems"])))
        if card["ok"]:
            log_ruling(log, "策划", attempt, "accepted",
                       "选题卡达标：角度具体、三条支柱互不重义", [card.get("angle") or ""])
            break
        rulings_summary["planner_reject"] += 1
        log_ruling(log, "策划", attempt, "rejected", "选题卡不达标（重开）", card["problems"])

    escalation = None
    if card is None or not card["ok"]:
        escalation = {"kind": "plan_retries_exhausted", "rounds_run": len(tried),
                      "unresolved": (card or {}).get("problems") or ["策划没有交出可用选题卡"]}
        return _finish_run(a, outdir, log, escalation, None, brief, target_chars, rounds,
                           usages, tracker, rulings_summary, card, None, None, None, [])

    # ---------------- 2) 写手初稿 ----------------
    res = draft_once(a, brief, card, target_chars, a.model, a.key, tracker, outdir, state,
                     text_sha(brief))
    draft_text, self_check, _fx, _used, usage, elapsed, iso, pchars = res
    usages.append(usage)
    log_isolation(log, "writer", iso, pchars, 1)
    log_entry(log, "draft", "写手", 1, "交初稿",
              "{} 字符；自评 {} 条（**审稿看不到这一栏**）".format(
                  char_count(draft_text),
                  len((self_check or {}).get("good") or []) + len((self_check or {}).get("weak") or [])))
    _write_round_dir(outdir, 0, {
        "draft.md": render_draft_md(draft_text, self_check, a.model, usage, elapsed, 0, "初稿"),
        "draft.txt": draft_text})

    # ---------------- 3) 审稿 ↔ 写手修订 循环 ----------------
    cur_text = draft_text
    strikes = 0
    prev_rejected_quotes = set()
    stalled_quote = None
    round_runs = []
    for r in range(1, rounds + 1):
        rev, usage, elapsed, iso, pchars = review_once(
            a, brief, card, cur_text, a.model, a.key, tracker, outdir, state,
            text_sha(brief), round_no=r)
        usages.append(usage)
        log_isolation(log, "reviewer", iso, pchars, r)
        log_entry(log, "review", "审稿", r, "出问题清单",
                  "锚定 {} 条 / 未锚定 {} 条（未锚定率 {:.0%}）；裁决 {}".format(
                      rev["anchor"]["verified"], rev["anchor"]["unanchored"],
                      rev["anchor"]["miss_rate"], rev["verdict"]),
                  [it.get("sentence") or it.get("quote") for it in rev["issues"][:3]])
        # 审稿锚点闸门：不可执行的清单不许往下走
        if not rev["anchor"]["ok"]:
            escalation = {"kind": "rounds_exhausted",
                          "rounds_run": r,
                          "unresolved": ["审稿锚点闸门命中：" + (rev["anchor"].get("why") or "")]}
            _write_round_dir(outdir, r, {
                "review.md": render_review_md(rev, a.model, usage, elapsed, r)})
            return _finish_run(a, outdir, log, escalation, rev, brief, target_chars, rounds,
                               usages, tracker, rulings_summary, card, cur_text, self_check,
                               None, round_runs)

        if rev["verdict"] == "pass":
            log_ruling(log, "审稿", r, "pass",
                       rev.get("summary") or "未发现问题（逐句看过）")
        else:
            rulings_summary["reviewer_send_back"] += 1
            log_ruling(log, "审稿", r, "send_back",
                       "{} 条问题必须在写手修订中处理（必须修 #{}）".format(
                           len(rev["issues"]), "、#".join(str(i) for i in rev["must_fix"])),
                       [it.get("sentence") or it.get("quote") for it in rev["issues"]
                        if it["id"] in rev["must_fix"]][:3],
                       forced_by_local=rev.get("verdict_forced_reason"))

        _write_round_dir(outdir, r, {
            "draft.md": render_draft_md(cur_text, self_check, a.model, {}, 0, r, "送审稿"),
            "draft.txt": cur_text,
            "review.md": render_review_md(rev, a.model, usage, elapsed, r)})

        if rev["verdict"] == "pass":
            round_runs.append({"round": r, "review_verdict": "pass",
                               "compliance_verdict": None})
            break

        # 审稿打回 → 检查是不是"写手改不动"（连续两轮指向同一批文字）
        cur_quotes = set(_norm_anchor(it.get("sentence") or it.get("quote") or "")
                         for it in rev["issues"] if it["id"] in rev["must_fix"])
        if prev_rejected_quotes and cur_quotes and \
                len(cur_quotes & prev_rejected_quotes) >= max(1, len(cur_quotes) // 2):
            stalled_quote = sorted(cur_quotes & prev_rejected_quotes)[0][:40]
        prev_rejected_quotes = cur_quotes

        if r >= rounds:
            escalation = {"kind": "rounds_exhausted", "rounds_run": r,
                          "unresolved": ["审稿仍判打回：{}".format(
                              "；".join("#{}({})".format(it["id"], (it.get("sentence") or "")[:36])
                                        for it in rev["issues"] if it["id"] in rev["must_fix"]))
                              or "审稿打回但没有锚定成功的问题"]}
            round_runs.append({"round": r, "review_verdict": "send_back",
                               "compliance_verdict": None})
            break

        # 写手修订（**只拿到锚定过的必须修清单**）
        issues_for_writer = [it for it in rev["issues"] if it["id"] in rev["must_fix"]] \
            or rev["issues"]
        facts = extract_facts(cur_text)
        old_text = cur_text
        new_text, new_sc, fixes, usage2, elapsed2, iso2, pchars2 = revise_once(
            a, brief, card, cur_text, issues_for_writer, facts, a.model, a.key, tracker,
            r, outdir, state, text_sha(brief))
        usages.append(usage2)
        log_isolation(log, "writer", iso2, pchars2, r)
        eff = revision_effective(old_text, new_text, len(issues_for_writer), len(fixes))
        fl = fact_loss_report(old_text, new_text, warn_only=a.facts_warn_only)
        log_entry(log, "revise", "写手", r, "按必须修清单修订",
                  "{} → {} 字符；自报修 {} 条（点名 {} 条）；正文相似度 {:.2f}；{}".format(
                      char_count(old_text), char_count(new_text), len(fixes),
                      len(issues_for_writer), eff["body_sim"],
                      "**判为没有实质改动**：" + eff["why"] if not eff["effective"] else "有实质改动"),
                  [f.get("before") for f in fixes[:3] if f.get("before")])
        if not eff["effective"]:
            strikes += 1
            log_ruling(log, "写手", r, "ineffective",
                       "本轮修订被本地判为没有实质改动：{}".format(eff["why"]),
                       [f.get("before") for f in fixes[:2] if f.get("before")])
        else:
            strikes = 0
        log["facts"].append({"round": r, "stage": "revise", **{k: v for k, v in fl.items()
                                                               if k != "facts"}})
        _write_round_dir(outdir, r, {
            "revise.md": render_draft_md(new_text, new_sc, a.model, usage2, elapsed2, r,
                                         "第 {} 轮修订稿".format(r)),
            "revise.txt": new_text,
            "facts.json": json.dumps(fl, ensure_ascii=False, indent=1)})
        cur_text, self_check = new_text, new_sc
        if strikes > MAX_NO_CHANGE_STRIKES:
            escalation = {"kind": "no_effective_change", "rounds_run": r,
                          "unresolved": ["写手连续 {} 轮修订没有实质改动：{}".format(
                              strikes, eff["why"])]}
            round_runs.append({"round": r, "review_verdict": "send_back",
                               "compliance_verdict": None,
                               "writer_effective": False})
            break
        round_runs.append({"round": r, "review_verdict": "send_back",
                           "compliance_verdict": None, "writer_effective": True})
        if stalled_quote:
            escalation = {"kind": "stalled_same_quote", "rounds_run": r,
                          "unresolved": ["审稿连续两轮指向同一段文字仍然被拒：{}".format(
                              stalled_quote)]}
            break

    # ---------------- 4) 合规 ----------------
    comp = None
    comp_used = 0
    if escalation is None:
        while True:
            comp_used += 1
            comp, usage, elapsed, iso, pchars = compliance_once(
                a, brief, card, cur_text, a.model, a.key, tracker, outdir, state,
                text_sha(brief), round_no=comp_used)
            usages.append(usage)
            log_isolation(log, "compliance", iso, pchars, comp_used)
            log_entry(log, "compliance", "合规", comp_used, "风险裁决",
                      "{}；{} 条发现；本地扫描命中 {} 处".format(
                          comp["verdict"], len(comp["findings"]), len(comp["local_hits"])),
                      [f["quote"] for f in comp["findings"][:3]])
            log_ruling(log, "合规", comp_used, comp["verdict"],
                       comp.get("reason") or "（未给理由）",
                       [f["quote"] for f in comp["findings"][:3]],
                       forced_by_local="；".join(comp["local_notes"]) or None)
            _write_round_dir(outdir, "c{}".format(comp_used), {
                "compliance.md": render_compliance_md(comp, a.model, usage, elapsed, comp_used),
                "draft.txt": cur_text})

            if comp["verdict"] == "pass":
                break
            if comp["verdict"] == "fix":
                new_text, repl = apply_safe_replacements(cur_text)
                if repl:
                    fixed, fresh = _verify_fix(a, cur_text, new_text, repl, cur_text, comp)
                    log_entry(log, "compliance", "合规", comp_used, "本地安全替换",
                              "替换 {} 处：{}；复扫 {}".format(
                                  len(repl),
                                  "、".join("「{}」→「{}」".format(c["word"], c["replaced_with"])
                                            for c in repl),
                                  "干净" if fixed else "**仍不干净**"))
                    log_ruling(log, "合规", comp_used, "auto_fixed_verified" if fixed
                               else "auto_fix_failed",
                               "本地按登记过的安全替代词替换后复扫：{}".format(
                                   "干净，放行" if fixed else "仍有命中，按否决处理"),
                               [c["word"] for c in repl])
                    cur_text = new_text
                    if fixed:
                        comp = dict(comp)
                        comp["verdict"] = "auto_fixed_verified"
                        comp["applied_replacements"] = repl
                        break
                    comp = dict(comp)
                    comp["verdict"] = "veto"
                    comp["reason"] = ((comp.get("reason") or "")
                                      + "；本地替换后复扫仍不干净，按否决处理")
                    escalation = {"kind": "compliance_send_back_exhausted",
                                  "rounds_run": comp_used,
                                  "unresolved": ["本地安全替换后仍命中违禁词，无法自动放行"]}
                    break
                escalation = {"kind": "compliance_send_back_exhausted",
                              "rounds_run": comp_used,
                              "unresolved": ["合规判 fix，但本地登记表里没有可用的安全替代词"]}
                break
            if comp["verdict"] == "veto":
                rulings_summary["compliance_veto"] += 1
                escalation = {"kind": "compliance_send_back_exhausted",
                              "rounds_run": comp_used,
                              "unresolved": ["合规一票否决：{}".format(comp.get("reason") or "未给理由")]
                              + ["[{}风险] {}".format(f["level"], f["quote"][:60])
                                 for f in comp["findings"][:5]]}
                break
            # send_back：还有额度就让写手再改一轮（**不把上一轮合规意见带过去**）
            rulings_summary["compliance_send_back"] += 1
            if comp_used > comp_max:
                escalation = {"kind": "compliance_send_back_exhausted",
                              "rounds_run": comp_used,
                              "unresolved": ["合规打回 {} 次仍不放行：{}".format(
                                  comp_used, comp.get("reason") or "未给理由")]}
                break
            findings = comp["findings"] or [{"id": 1, "quote": "", "level": "中",
                                             "why": comp.get("reason") or "合规要求修改",
                                             "dims": ["compliance"], "fix": "", "severity": "高"}]
            issues_for_writer = []
            for f in findings:
                issues_for_writer.append({
                    "id": f.get("id") or len(issues_for_writer) + 1,
                    "quote": f.get("quote") or "", "sentence": f.get("quote") or "",
                    "dims": ["compliance"], "severity": "高" if f.get("level") == "高" else "中",
                    "why": "合规判定为风险：{}（{}）".format(f.get("why") or "", f.get("rule") or ""),
                    "fix": f.get("safe_replacement") or "改写这一段以消除该风险",
                })
            facts = extract_facts(cur_text)
            old_text = cur_text
            new_text, new_sc, fixes, usage2, elapsed2, iso2, pchars2 = revise_once(
                a, brief, card, cur_text, issues_for_writer, facts, a.model, a.key, tracker,
                "c{}".format(comp_used), outdir, state, text_sha(brief))
            usages.append(usage2)
            log_isolation(log, "writer", iso2, pchars2, comp_used)
            eff = revision_effective(old_text, new_text, len(issues_for_writer), len(fixes))
            log_entry(log, "revise", "写手", comp_used, "按合规要求修订",
                      "{} → {} 字符；自报修 {} 条；正文相似度 {:.2f}".format(
                          char_count(old_text), char_count(new_text), len(fixes), eff["body_sim"]))
            _write_round_dir(outdir, "c{}".format(comp_used), {
                "compliance.md": render_compliance_md(comp, a.model, usage, elapsed, comp_used),
                "revise.md": render_draft_md(new_text, new_sc, a.model, usage2, elapsed2,
                                             comp_used, "合规修订稿"),
                "revise.txt": new_text})
            cur_text, self_check = new_text, new_sc
            if not eff["effective"]:
                escalation = {"kind": "no_effective_change", "rounds_run": comp_used,
                              "unresolved": ["合规打回后写手修订没有实质改动：{}".format(eff["why"])]}
                break

    return _finish_run(a, outdir, log, escalation, comp, brief, target_chars, rounds,
                       usages, tracker, rulings_summary, card, cur_text, self_check,
                       round_runs, [])


def _verify_fix(a, old_text, new_text, repl, draft, comp):
    """本地替换后**必须复扫确认干净**。返回 (是否干净, 复扫结果)。"""
    hits, _ex = compliance_scan(new_text)
    return (not hits), hits


def _emit_dry(a, stage, payload):
    if a.json:
        _json_out({"dry_run": True, "stage": stage, "prompt": payload}, a, indent=2)
    else:
        print(payload)

def _finish_run(a, outdir, log, escalation, comp, brief, target_chars, rounds, usages,
                tracker, rulings_summary, card, final_text, self_check, round_runs,
                _extra):
    """收口：跑定稿的硬闸门、写全部产物、决定退出码。"""
    final_text = final_text or ""
    # ---- 事实基准：以**策划的 must_keep** 为准，不是整份用户材料 ----
    #
    # 事故复盘（本包真机实测抓到的，不是推演）：最初把整份 `brief` 当基准，
    # 材料里那句「看到一个说法：90% 的人买完咖啡机都没认真清洗过」被抽成了一条
    # 必须保全的事实。写手按选题卡的 risk_note 把它**正确地**处理成
    # 「这个说法没有出处，只能当作未经验证的说法，不能当成结论」——
    # 结果它被闸门判为"丢了事实 90"。这是把**无出处的说法**当成了必须复读的事实，
    # 逼写手去复述一条未经验证的数据，方向正好反了。
    #
    # 正确的基准是策划写进 `must_keep` 的那几条（策划只有在材料里确实有出处时才登记）。
    # 用户材料里那些**没被写进 must_keep** 的数字（例如上面那个 90%）进 `untrusted_brief`，
    # 照样列出来给人看，但**不参与判定**、不压退出码。
    keep_text = "\n".join(str(x) for x in ((card or {}).get("must_keep") or []))
    baseline_facts = extract_facts(keep_text)
    coverage = (fact_loss_report(keep_text, final_text, warn_only=a.facts_warn_only)
                if baseline_facts else
                {"total": 0, "kept": 0, "lost": [], "renumbered": [], "kept_rate": 1.0,
                 "ok": True, "warn_only": bool(a.facts_warn_only), "facts": []})
    coverage["kind"] = "card_must_keep"
    coverage["note"] = ("基准 = 策划选题卡里的 must_keep（策划只在用户材料里确实有出处时"
                        "才登记）。策划许下的硬信息必须在定稿里兑现，否则就是"
                        "「标题许诺了数据、正文一个都没有」。")
    # 材料里有、但没进 must_keep 的数字：**列出来但不拦**
    keep_norms = {(f["kind"], f["norm"]) for f in baseline_facts}
    untrusted = [f for f in extract_facts(brief)
                 if (f["kind"], f["norm"]) not in keep_norms]
    lost_untrusted = [f for f in untrusted
                      if not _fact_present_in(final_text, f)] if untrusted else []
    coverage["untrusted_brief"] = {
        "note": "用户材料里出现、但**没有被策划登记进 must_keep** 的硬信息。"
                "它们不参与判定（未经验证的说法不该被逼着复读），列出来供人工核对。",
        "total": len(untrusted),
        "not_in_final": [{"kind": f["kind"], "raw": f["raw"],
                          "context": f.get("context") or ""} for f in lost_untrusted],
    }

    # 逐轮事实保全（打回重写后，上一版的数字/专名必须仍在）
    per_round_loss = [x for x in (log.get("facts") or []) if not x.get("ok")]

    gates = evaluate_gates(final_text, target_chars, None, coverage)
    review_anchor_ok = True
    if isinstance(comp, dict):
        pass
    converged = bool(escalation is None and isinstance(comp, dict)
                     and comp.get("verdict") in ("pass", "auto_fixed_verified")
                     and not gate_failed(gates))
    if escalation is None and not converged:
        escalation = {"kind": "rounds_exhausted", "rounds_run": len(round_runs),
                      "unresolved": ["合规未放行（{}）".format(
                          (comp or {}).get("verdict") or "无裁决")]}
    why = ("全流程走通：审稿放行，合规 {}，定稿硬闸门全过。".format(
        (comp or {}).get("verdict"))
        if converged else
        "**未收敛**（出口：{}）。{}".format(
            (escalation or {}).get("kind"),
            EXIT_KIND.get((escalation or {}).get("kind"), "")))
    convergence = {"converged": converged, "why": why,
                   "exit_kind": (escalation or {}).get("kind"),
                   "unresolved": (escalation or {}).get("unresolved") or []}

    # 信息不对称汇总（可复核）
    iso_all = log["isolation"]
    iso_ok = all(x["ok"] for x in iso_all)
    asym = {
        "verified_calls": len(iso_all),
        "all_ok": iso_ok,
        "self_check_excluded_from_reviewer": all(
            "self_check" in x["excluded_fields"]
            for x in iso_all if x["stage"] == "reviewer") if any(
            x["stage"] == "reviewer" for x in iso_all) else None,
        "issues_excluded_from_compliance": all(
            "issues" in x["excluded_fields"]
            for x in iso_all if x["stage"] == "compliance") if any(
            x["stage"] == "compliance" for x in iso_all) else None,
        "note": "每次调用前对**真实提示词文本**扫标记词；泄漏会当场中止调用（退出码 3），"
                "所以 all_ok 为真意味着这些调用确实在信息不对称下发生。",
    }

    n_entries = len(log["entries"])
    result = {
        "mode": "run", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "ruling_version": RULING_VERSION,
        "model": a.model, "target_chars": target_chars,
        "rounds": rounds, "rounds_run": len(round_runs),
        "plan_retries": a.plan_retries, "compliance_sendback": a.compliance_sendback,
        "brief": {"path": str(a.brief), "sha": text_sha(brief), "chars": char_count(brief)},
        "card": card, "card_attempts": len(card and [card] or []),
        "roles": {k: {"name": ROLES[k]["name"], "veto": ROLES[k]["veto"],
                      "forbidden": ROLES[k]["forbidden"]} for k in ROLE_ORDER},
        "final": final_text, "chars": char_count(final_text),
        "compliance": comp, "convergence": convergence, "escalation": escalation,
        "rulings_summary": rulings_summary,
        "gates": gates, "gate_failed": gate_failed(gates),
        "fact_coverage": coverage, "fact_loss_per_round": per_round_loss,
        "information_asymmetry": asym,
        "log": log, "log_entries": n_entries,
        "rounds_detail": round_runs,
        "usage": _sum_usage(usages),
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
        "ok_bool": converged,
    }

    # ---------------- 写产物 ----------------
    (outdir / "final.md").write_text(final_text + "\n", encoding="utf-8")
    (outdir / "final.json").write_text(json.dumps({
        "brief": result["brief"], "card": card, "final": final_text,
        "compliance": comp, "convergence": convergence,
        "fact_coverage": coverage,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    (outdir / "REPORT.md").write_text(
        render_log_md(log, escalation, convergence, final_text, gates,
                      result["cost"]) + "\n", encoding="utf-8")
    if card:
        (outdir / "plan.json").write_text(
            json.dumps({"card": card}, ensure_ascii=False, indent=1), encoding="utf-8")

    sys.stderr.write("\n{}\n".format(tracker.line()))
    _gate_stderr("定稿", gates)
    if not coverage["ok"]:
        sys.stderr.write("\n{}\n".format(_red(
            "事实覆盖：用户材料/选题卡里的 {} 条硬信息没有落到定稿里".format(
                len(coverage["lost"])))))
        for f in coverage["lost"]:
            sys.stderr.write("   [{}] `{}` —— 出处：{}\n".format(
                f.get("label") or f["kind"], f["raw"], f.get("context") or ""))
    for x in per_round_loss:
        sys.stderr.write("   第 {} 轮修订丢了 {} 条上一稿事实：{}\n".format(
            x.get("round"), len(x.get("lost") or []),
            "、".join("「{}」".format(f["raw"]) for f in (x.get("lost") or [])[:6])))
    if escalation:
        sys.stderr.write("\n{}\n".format(_red(
            "未收敛，出口 = {}：{}".format(
                escalation["kind"], EXIT_KIND.get(escalation["kind"], "")))))
        for u in escalation.get("unresolved") or []:
            sys.stderr.write("   · {}\n".format(u))
    else:
        sys.stderr.write("收敛：审稿放行 + 合规 {} + 硬闸门全过。\n".format(
            (comp or {}).get("verdict")))
    sys.stderr.write("目录产物：{}（final.md / final.json / REPORT.md / log.json / "
                     "plan.json / rounds/ / state.json）\n".format(outdir))

    md = render_log_md(log, escalation, convergence, final_text, gates, result["cost"])
    _emit(a, result, md, ok=converged)
    return EXIT_OK if converged else EXIT_GATE


# ===========================================================================
# 子命令：log —— 读回全过程记录
# ===========================================================================

def run_log(a):
    outdir = Path(a.outdir)
    logf = outdir / "log.json"
    repf = outdir / "REPORT.md"
    if not logf.is_file():
        raise UsageError("这个目录里没有 log.json（不是本包的 --outdir？）：{}".format(outdir))
    try:
        # BOM 容忍：Windows 上 `Out-File -Encoding utf8`（PowerShell 5.1）会写 BOM，
        # 用 json.loads 严格解 utf-8 会炸成 JSONDecodeError。本包的 log.json 是
        # 自己写的（无 BOM），但用户可能手工编辑过 —— 这属于"文件内容问题"，
        # 要报成用法错（退出码 2），不能让它变成 internal 噪声。
        log = json.loads(logf.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise UsageError("读不了 log.json：{}（{}）".format(logf, exc))
    if not isinstance(log, dict) or not isinstance(log.get("entries", []), list) \
            or not isinstance(log.get("rulings", []), list):
        raise UsageError("log.json 结构不对（缺 entries/rulings 列表）：{}".format(logf))
    fin = outdir / "final.md"
    final_text = fin.read_text(encoding="utf-8") if fin.is_file() else ""
    comp = None
    cf = outdir / "compliance.json"
    if cf.is_file():
        try:
            comp = json.loads(cf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            comp = None
    rulings = log.get("rulings") or []
    vetoes = [r for r in rulings if r["decision"] in ("veto", "rejected", "send_back",
                                                      "ineffective", "auto_fix_failed")]
    result = {
        "mode": "log", "outdir": str(outdir),
        "entries": len(log.get("entries") or []), "rulings": len(rulings),
        "vetoes_or_rejections": len(vetoes),
        "by_decision": _count_by(rulings, "decision"),
        "by_role": _count_by(rulings, "role"),
        "isolation": log.get("isolation") or [],
        "final_chars": char_count(final_text),
        "final_preview": final_text[:400],
        "compliance": comp,
        "log": log,
        "report_path": str(repf) if repf.is_file() else None,
        "answer": ("这份记录里 {} 条裁决中有 {} 条是否决/打回类决定 —— "
                   "如果这个数是 0，说明多角色互审没有真的发生。".format(
                       len(rulings), len(vetoes))),
    }
    if a.json:
        _json_out(result, a, indent=2)
        return EXIT_OK
    out = ["# 全过程记录：{}".format(outdir), ""]
    out.append("- 动作流水 {} 条 · 裁决 {} 条 · 其中否决/打回 {} 条".format(
        result["entries"], result["rulings"], result["vetoes_or_rejections"]))
    out.append("- 裁决分布：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in result["by_decision"].items()) or "（无）"))
    out.append("- 按角色：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in result["by_role"].items()) or "（无）"))
    out.append("- 信息不对称实检：{} 次调用，全部通过 = {}".format(
        len(result["isolation"]), all(x["ok"] for x in result["isolation"])))
    out.append("- {}".format(result["answer"]))
    out.append("")
    out.append("完整报告见 `{}`。".format(repf.name))
    print("\n".join(out))
    return EXIT_OK


def _count_by(rows, key):
    out = {}
    for r in rows or []:
        k = str(r.get(key) or "-")
        out[k] = out.get(k, 0) + 1
    return out


# ===========================================================================
# 子命令：cost
# ===========================================================================

def run_cost(a):
    if a.file:
        text = read_text(a.file, "材料")
    elif a.text:
        text = a.text
    else:
        raise UsageError("要么给 --file，要么给 --text")
    check_budget(a)
    target_chars = check_target_chars(a.target_chars)
    rounds = check_positive("--rounds", a.rounds)
    plan_retries = check_positive("--plan-retries", a.plan_retries)
    comp_sb = check_positive("--compliance-sendback", a.compliance_sendback)
    calls = estimate_calls(len(text), target_chars, rounds, plan_retries, comp_sb)
    tin = sum(c["tokens_in"] for c in calls)
    tout = sum(c["tokens_out"] for c in calls)
    total_calls = sum(c["calls"] for c in calls)
    rec = compute_cost(tin, tout, a.price_in, a.price_out)
    rep = {
        "mode": "cost", "target_chars": target_chars, "rounds": rounds,
        "plan_retries": plan_retries, "compliance_sendback": comp_sb,
        "brief_chars": len(text or ""), "total_calls": total_calls,
        "calls": calls,
        "tokens_in": tin, "tokens_out": tout,
        "chars_per_token_in": CHARS_PER_TOKEN_IN,
        "tokens_per_char_out": TOKENS_PER_CHAR_OUT,
        "points_per_yuan": POINTS_PER_YUAN,
        "cost": rec,
        "roles": [{"key": k, "name": ROLES[k]["name"],
                   "model_calls": (1 if k == "writer" else 0) + 1} for k in ROLE_ORDER],
        "note": "这是**估算，不是账单**：字符→token 的比值来自同族实测标定，"
                "不是厂商文档。真实扣费以账户流水为准。按**最坏情况**估"
                "（含策划重开与合规打回各一次的上界）。",
    }
    out = ["# 协作成本估算", ""]
    out.append("- 材料：{} 字符　目标篇幅：{} 字符　轮次：{}".format(
        len(text or ""), target_chars, rounds))
    out.append("- 调用次数合计：{}".format(total_calls))
    out.append("")
    out.append("| 阶段 | 次数 | 输入 token | 输出 token | 说明 |")
    out.append("|---|---|---|---|---|")
    for c in calls:
        out.append("| {} | {} | {} | {} | {} |".format(
            c["stage"], c["calls"], c["tokens_in"], c["tokens_out"], c["note"]))
    out.append("| **合计** | {} | {} | {} |".format(total_calls, tin, tout))
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
    out.append("标定口径：1 token ≈ {} 输入字符；1 输出字符 ≈ {} token。{}".format(
        CHARS_PER_TOKEN_IN, TOKENS_PER_CHAR_OUT, rep["note"]))
    rc = EXIT_OK
    if a.budget is not None and rec["points"] is not None:
        if rec["points"] > a.budget:
            rc = EXIT_BUDGET
            sys.stderr.write("\n{}\n".format(_red(
                "预算闸门：预估 {:g} 点超过 --budget {:g} 点，run 会在发起调用前停下"
                .format(rec["points"], a.budget))))
    _emit(a, rep, "\n".join(out), ok=not rc)
    return rc


# ===========================================================================
# 子命令：models
# ===========================================================================

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
    print("用法：run.py run --brief 材料.md --model <model_code>")
    return EXIT_OK


# ===========================================================================
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#
# 信封必须落在**真 stdout**：所有 JSON 文本都经 `_json_write` 写，绕开任何临时的 stdout 重定向。
# ===========================================================================

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}

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


# ===========================================================================
# 入口
# ===========================================================================

def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py roles --json` 会报 `unrecognized arguments` 并退出 2。
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


def _add_brief_opts(p, required=True):
    p.add_argument("--brief", required=required,
                   help="用户材料（.md / .txt，UTF-8）：选题来源 + 事实基准")
    p.add_argument("--target-chars", type=int, default=DEFAULT_TARGET_CHARS,
                   dest="target_chars",
                   help="目标篇幅（不含空白的字符数），默认 {}".format(DEFAULT_TARGET_CHARS))


def _add_facts_opt(p):
    p.add_argument("--facts-warn-only", action="store_true", dest="facts_warn_only",
                   help="把「丢事实 / 硬信息没兑现」从硬闸门降级为提示"
                        "（**已知会误报**：把「87%」合法改写成「接近九成」这类。"
                        "默认仍然是硬闸门）")


def _parser(**kw):
    """统一构造 ArgumentParser，**关掉长选项前缀缩写**（`allow_abbrev=False`）。

    事故复盘（同族自测时踩到的真实坑）：子命令上同时有 `--outdir` 时，
    用户写 `--out report.json` 想输出结果文件，argparse 默认允许**前缀缩写**，
    于是 `--out` 被当成 `--outdir` 的缩写匹配上了 —— 结果：产出目录变成了一个叫
    `report.json` 的目录，而且**不报任何错**。这类"参数被静默吃成另一个参数"的错误
    最难查，因为命令行看起来是对的。关掉缩写后，`--out` 直接报 unrecognized
    arguments（退出码 2），一眼就能看出问题。
    """
    kw.setdefault("allow_abbrev", False)
    return argparse.ArgumentParser(**kw)


def _main(argv_eff):
    ap = _parser(
        prog="run.py",
        description="三剪客 · 内容团队 —— L3 多智能体协作出稿"
                    "（策划 / 写手 / 审稿 / 合规，走 api.a7w.cn 的 OpenAI 兼容端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    # 每个子命令的 parser 也必须关掉缩写：argparse 的缩写开关是**每个 parser 各自**的
    # 属性，只在父级设一遍不够（子 parser 是另造的实例，默认仍然允许缩写）。
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("roles", help="列出四个角色的职权、产出物与否决权（零成本）")
    _add_json(p)
    p.add_argument("--out", help="把职权表写到这个文件")
    p.set_defaults(func=run_roles)

    p = sub.add_parser("plan", help="策划出选题卡（不达标会自动重开）")
    _add_brief_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--plan-retries", type=int, default=1, dest="plan_retries",
                   help="选题卡不达标时最多重开几次，默认 1（合计最多试 2 次）")
    p.add_argument("--outdir", help="目录产物落这里（**必须在包外**）：plan.json / plan.md")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")
    p.set_defaults(func=run_plan)

    p = sub.add_parser("draft", help="写手按选题卡出初稿（附自评；自评不进审稿）")
    _add_brief_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--card", required=True, help="选题卡 JSON（plan --json --out 的产物）")
    p.add_argument("--outdir", help="目录产物落这里（**必须在包外**）")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")
    p.set_defaults(func=run_draft)

    p = sub.add_parser("review", help="审稿出问题清单，**可打回写手**")
    _add_brief_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--card", required=True, help="选题卡 JSON")
    p.add_argument("--draft", required=True, help="待审稿件（.md/.txt）")
    p.add_argument("--outdir", help="目录产物落这里（**必须在包外**）")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")
    p.set_defaults(func=run_review)

    p = sub.add_parser("compliance", help="合规风险裁决，**有一票否决权**")
    _add_brief_opts(p, required=False)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--card", help="选题卡 JSON（可选；只取标题与风险提示给合规）")
    p.add_argument("--draft", required=True, help="待裁稿件（.md/.txt）")
    p.add_argument("--outdir", help="目录产物落这里（**必须在包外**）")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")
    p.set_defaults(func=run_compliance)

    p = sub.add_parser("run", help="一条命令跑完整协作：带裁决、轮次上限与明确出口")
    _add_brief_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--rounds", type=int, default=2,
                   help="审稿↔写手修订最多几轮，默认 2（至少 1）")
    p.add_argument("--plan-retries", type=int, default=1, dest="plan_retries",
                   help="选题卡不达标时最多重开几次，默认 1")
    p.add_argument("--compliance-sendback", type=int, default=1,
                   dest="compliance_sendback",
                   help="合规打回后最多再让写手改几轮，默认 1")
    _add_facts_opt(p)
    p.add_argument("--outdir",
                   default=str(Path(os.environ.get("TEMP") or ".") / "content-team-out"),
                   help="目录产物落这里（**必须在包外**）：final.md / final.json / "
                        "REPORT.md / log.json / plan.json / rounds/ / state.json")
    p.add_argument("--force", action="store_true",
                   help="忽略断点文件，从头重跑（key 没命中就会重新花钱）")
    p.set_defaults(func=run_run)

    p = sub.add_parser("log", help="读回全过程记录：谁改了什么、谁否决了什么")
    p.add_argument("--outdir", required=True, help="run 的 --outdir")
    _add_json(p)
    p.set_defaults(func=run_log)

    p = sub.add_parser("cost", help="报价：一次协作大概花多少 token（金额要你填单价）")
    p.add_argument("--file", help="按这份材料估")
    p.add_argument("--text", help="或直接给文本")
    p.add_argument("--target-chars", type=int, default=DEFAULT_TARGET_CHARS,
                   dest="target_chars", help="目标篇幅，默认 {}".format(DEFAULT_TARGET_CHARS))
    p.add_argument("--rounds", type=int, default=2, help="按几轮估，默认 2")
    p.add_argument("--plan-retries", type=int, default=1, dest="plan_retries",
                   help="按最多重开几次估，默认 1")
    p.add_argument("--compliance-sendback", type=int, default=1,
                   dest="compliance_sendback", help="按最多打回几次估，默认 1")
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
                 ("price_out", None), ("force", False),
                 ("target_chars", DEFAULT_TARGET_CHARS), ("rounds", 0),
                 ("plan_retries", 1), ("compliance_sendback", 1),
                 ("facts_warn_only", False), ("brief", None), ("card", None),
                 ("draft", None), ("outdir", None), ("file", None), ("text", None),
                 ("type", "text")):
        if not hasattr(a, k):
            setattr(a, k, v)
    kind, msg, detail = None, None, None
    try:
        rc = a.func(a)
    except DryRunStop as exc:
        # `--dry-run`：把这次调用**将要发出去的提示词**打出来，退出码 0（没花钱）
        _emit_dry(a, exc.stage, exc.prompt)
        return EXIT_OK
    except IsolationBreach as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc, kind, msg = EXIT_GATE, "gate", str(exc)
    except CtError as exc:
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


def cli():
    """stdout/stderr 的编码收口。"""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    return main()


if __name__ == "__main__":
    sys.exit(cli())
