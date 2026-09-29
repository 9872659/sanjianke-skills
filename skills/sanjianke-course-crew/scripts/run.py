#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 课程教研组 —— 多智能体协作开一门课（零第三方依赖）。

**产品线 L3（多智能体协作型）。** 与 L2（单角色自我迭代，比如
`sanjianke-course-outline` 的「出大纲 → 逐节写 → 校验」）的分界不是"调了几次模型"，
而是四件事：

  1. 四个角色**各有各的目标函数与产出物**：
       教研   → 课程设计卡（目标 / 受众 / 前置 / 考核标准）
       讲师   → 逐节讲义
       课件   → 逐页课件方案（页型 / 标题 / 要点 / 备注）
       质检   → 问题清单（**每条必须引用讲义原句**）+ 风险裁决
  2. 角色之间**互相否掉东西**：
       教研**能否掉自己的设计**（重开到上限，`--design-retries`）
       课件**能说「这页放不下」**并要求讲师拆（`--slide-rework`）
       质检**能否决**（`--inspect-rework`）
  3. 有**明确的裁决机制**：谁能否谁、最多几轮、谈不拢走哪个出口
  4. 一条命令出成品：整门课的**设计卡 + 讲义 + 课件方案 + 质检记录 + 裁决**

**信息不对称**（本包是 L3 而不是"一个模型演四个角色"的关键，且是结构性保证）：

  · 讲师的 `self_check`（自评）**不进课件、不进质检的上下文**
    —— 作者自己说"我觉得这段讲得清楚"会污染下游的独立判断
  · 课件的 `slide_issues`（放不下清单）**不进质检的上下文**
    —— 质检如果知道课件已经逐页验过，就会顺着放行
  · 教研的完整设计卡**不进质检的上下文以外的角色**：
    给课件的只是一份**窄字典**（单元标题 + 逐节标题），讲师拿到的另有其
    `objectives`（他必须照着目标写），但拿不到 `assessment`（考核标准不进讲稿）
  · 三条禁令由 `assert_isolation()` 在**每次调用前**用文本级检查验证，
    判定结果逐条写进产出与流程记录（`isolation` 字段），可复核

九个（含 `all` 的别名 `run`）子命令：

    roles     列出四个角色的职权、产出物与否决权（纯本地，零成本）
    design    教研出课程设计卡（不达标会自动重开）
    lecture   讲师按设计卡写逐节讲义
    slides    课件出逐页方案，**能说「这页放不下」**
    inspect   质检出问题清单（引用讲义原句）+ 风险裁决，**能否决**
    run       一条命令出整门课：带裁决、轮次上限与明确出口
    log       读回全过程记录：谁在第几轮否掉了什么、引用哪句原话
    cost / models

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py roles
    python3 run.py design  --brief brief.md --outdir /tmp/cc --json --out /tmp/cc-design.json
    python3 run.py lecture --brief brief.md --design /tmp/cc/design.json --outdir /tmp/cc
    python3 run.py slides  --brief brief.md --design /tmp/cc/design.json --lectures /tmp/cc/lectures.json
    python3 run.py inspect --brief brief.md --design /tmp/cc/design.json --lectures /tmp/cc/lectures.json
    python3 run.py run     --brief brief.md --chapters 3 --outdir /tmp/cc --json
    python3 run.py log     --outdir /tmp/cc
    python3 run.py run     --brief brief.md --dry-run      # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py run --brief brief.md --key sk-xxxx
    export A7W_API_KEY=sk-xxxx     # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

设计取舍
    · **为什么不是"一个模型分五次扮演不同角色"**：那样每个角色看到的上下文一样，
      不会有真正的对抗，评估者与被执行者是同一个声音。本包把"看不到什么"写死成
      提示词模板的结构（`ROLES[*]["inputs"] / ["forbidden"]`），再用
      `assert_isolation()` 在调用前验证。
    · **本包不出图、不出 PPTX**：`python-pptx` 不是标准库、本包不依赖它；
      课件角色只出**文本方案**（页型 / 标题 / 要点 / 备注），
      真正的版式与逐页 PNG 交给既有的课件排版包去做。
    · **谈不拢不许装作谈拢**：设计重开上限用尽、轮次用尽、连续两轮没有实质改动、
      质检两次指向同一批被拒条目的同一段文字 —— 都走**显式出口**，退出码 3，
      `escalation` 里写明原因与未决项。
    · **合规处置分两个口径**（同族踩过：评审自己写「禁止承诺保过」被自己的闸门拦下）：
      产出侧（讲稿 / 课件方案 / 质检结论）要排除**引用材料**与**警告语境**
      （前后 24 字内有 禁止 / 不得 / 删除 / 违规 等标记词），被排除的每一处都留下原因；
      但闸门仍然有牙 —— 材料侧（用户给的 brief）**照拦不误**，不走豁免。
    · 违禁词表与判定口径是**启发式自检**，来自公开经验整理，不构成法律意见，
      也不等于任何平台的官方审核标准。
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
EXIT_OK = 0            # 收敛：质检放行 + 无硬闸门命中
EXIT_USAGE = 2         # 参数/配置错（文件不存在、--outdir 在包内、给 --budget 没给单价）
EXIT_GATE = 3          # 硬闸门命中（违禁词/占位符/照抄示例/目标不可考核/前置缺失/**未收敛**）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止（**未发起任何调用**）
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。改了角色提示词 / 裁决规则却不改 key，
# 续跑会把上一版口径的旧产物当成"已完成"直接复用，产出对不上文档。
ROLE_VERSION = "cc-roles-1.0.0"
PROMPT_VERSION = "cc-prompt-1.0.0"
RULING_VERSION = "cc-ruling-1.0.0"

# 默认规模与篇幅。**为什么给目标而不是上限**：实测模型会贴着你给的数字写，
# 给上限就一定顶到上限（然后超）。
DEFAULT_CHAPTERS = 3
DEFAULT_SECTIONS_PER_CHAPTER = 1
MAX_SECTIONS = 12                  # 一节讲义一次调用；超过 12 节请分开跑（报价要先看）
DEFAULT_TARGET_CHARS = 800         # 单节讲义的目标字符数（不含空白）
TARGET_CHARS_MIN = 400
TARGET_CHARS_MAX = 3000
DEFAULT_MAX_PAGES = 6              # 逐页课件方案的目标页数


# ===========================================================================
# 角色表：L3 的地基
#
# 每个角色有自己的**目标函数**（想要什么）、**产出物**（交什么）与**否决权**（能否谁）。
# `inputs` 是**允许进入该角色上下文的字段白名单**，`forbidden` 是被显式排除的字段。
# 这两栏不是文档，是 build_*_prompt() 真实读的那份数据 —— 提示词模板按它拼装，
# assert_isolation() 按它验证。改这里就同时改了行为与判定，不会文档与实现两张皮。
# ===========================================================================

ROLE_ORDER = ("designer", "instructor", "slides", "inspector")

ROLES = {
    "designer": {
        "name": "教研",
        "goal": ("这门课值不值得学、给谁学、学完能做到什么、拿什么考核 —— "
                 "交出一张「学完也不知道会了什么」的设计卡就是失职"),
        "deliverable": "课程设计卡（课程目标 / 受众 / 前置知识 / 逐单元学习目标 / 考核标准 / 术语表）",
        "veto": "**能否掉自己的设计并重开**，重开上限由 --design-retries 控制",
        "inputs": ["brief", "chapters", "sections_per_chapter", "target_chars"],
        "forbidden": [],
        "exit_on_fail": "设计卡不达标 → 重开；上限用尽 → 升级给人看（退出码 3）",
    },
    "instructor": {
        "name": "讲师",
        "goal": "每一节都要讲透：目标能落到可观察的行为上，例子能跟着做，过渡能接上下一节",
        "deliverable": "逐节讲义正文 + 自评（self_check，**课件与质检都看不到这一栏**）",
        "veto": "无 —— 讲师只能改，不能否掉课件或质检的结论",
        "inputs": ["brief", "design", "design_digest", "prior_digests", "target_chars",
                   "unit_id", "section_id"],
        "forbidden": [],
        "exit_on_fail": "不适用（讲师没有否决权）",
    },
    "slides": {
        "name": "课件",
        "goal": "每一页放不放得下、版式能不能看 —— 说「放得下」而实际讲不完，就是你的失职",
        "deliverable": "逐页课件方案（页型 / 页标题 / 要点 / 讲稿备注）+ **放不下清单**",
        "veto": "**能说「这页放不下」**并要求讲师拆内容（上限 --slide-rework）",
        # ⚠️ 关键：讲师的 self_check 被显式排除在课件上下文之外。
        "inputs": ["brief", "design_digest", "lectures", "max_pages"],
        "forbidden": ["self_check", "instructor_self_check"],
        "exit_on_fail": "重做上限用尽仍放不下 → 带未决项产出（退出码 3）",
    },
    "inspector": {
        "name": "质检",
        "goal": ("前后一致 + 事实与合规 —— 只看这门课能不能交，不看它写得好不好；"
                 "挑不出具体到句子的真问题就是没干活"),
        "deliverable": "问题清单（**每条必须引用讲义里真实存在的一句话**）+ 风险裁决 + 合规结论",
        "veto": "**能否决**（pass / send_back / veto）：判 veto 直接终止，产出带未决项",
        # ⚠️ 关键：课件的放不下清单与讲师的 self_check 都被显式排除在质检上下文之外。
        "inputs": ["brief", "design", "lectures"],
        "forbidden": ["self_check", "slide_issues", "slides_verdict"],
        "exit_on_fail": "打回次数用尽仍不放行 → 带未决项产出（退出码 3）",
    },
}

# 每个角色调用的提示词里**禁止出现的标记词**。assert_isolation 用它做文本级检查：
# 排除一个字段，靠的不是"我模板里没写"，而是"调用前真的扫过一遍"。
ISOLATION_MARKERS = {
    "self_check": ["自评", "self_check", "我认为讲得好的地方", "我自己的评价"],
    "instructor_self_check": ["讲师自评", "作者自评"],
    "slide_issues": ["放不下清单", "课件的意见", "slide_issues", "页数不够", "这一页放不下"],
    "slides_verdict": ["课件结论", "slides_verdict", "课件已经验过", "课件已通过"],
}

# 合规的「安全替代词」表。**只有登记在这里的词才允许本地自动替换**，
# 替换后必须本地复扫确认干净（auto_fixed_verified）——否则按否决处理。
# 表里空着的说明本地没有可靠的安全替代，必须走 veto 给人看。
SAFE_REPLACEMENTS = {
    "最好": "", "最佳": "较合适", "最优": "较合适", "最便宜": "价格较低",
    "最快": "较快", "最强": "较强", "最先进": "较先进", "最新": "较新",
    "最受欢迎": "较受欢迎",
    "百分之百": "基本", "百分百": "基本", "100%": "", "No.1": "靠前", "no.1": "靠前",
    "TOP1": "靠前", "top1": "靠前",
    "保过": "按课程要求完成学习与练习", "包过": "按课程要求完成学习与练习",
    "包学会": "跟着练完能独立完成练习", "保证学会": "跟着练完能独立完成练习",
    "保证提分": "按进度完成练习", "提分保证": "按进度完成练习",
    "保就业": "课程不含就业承诺", "包就业": "课程不含就业承诺",
    "包分配": "课程不含就业承诺", "一次通过": "按进度完成练习",
    "绝对有效": "通常有效", "保证有效": "有助于", "无效退款": "可按规则申请售后",
    "零风险": "风险较低", "稳赚": "有机会", "躺赚": "有机会", "包赚": "有机会",
    "独家": "特色", "唯一": "少见的", "首个": "较早的", "首创": "较早采用",
    "纯天然": "以天然成分为主", "无添加": "配方简单", "零添加": "配方简单",
    "点击链接": "查看详情", "加微信": "联系客服", "私信我": "联系客服",
}

# 提示词里出现过的**跨主题**示例（正常不该被抄）。新增示例必须登记到这里。
# 跨主题 = 与本包面向的课程主题都不搭（社区团购选品 / 机械制图停机点 / 架子鼓坐姿），
# 模型不会主动抄过去；万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
PROMPT_SAMPLES = [
    "社区团购次日达的丢件率怎么算出来",
    "机械制图里停机点的标注顺序",
    "架子鼓坐姿与手腕角度的关系",
]

CONVERGE_NOTE = (
    "裁决不是投票：教研能否掉自己的设计，课件能说「这页放不下」并要求讲师拆，"
    "质检能否决 —— 三者是**串行**关系。"
    "重开/重做次数用尽、连续两轮无实质改动、质检持续指向同一段文字 —— 都走**显式出口**。"
)

MAX_NO_CHANGE_STRIKES = 1     # 连续两轮"没有实质改动"就升级（0 次改动即算一次）
BODY_MIN_SIM = 0.86           # 新讲义与上一稿的相似度 ≥ 此值即判「没有实质改动」
FIX_RATIO_MIN = 0.5           # 打回时说"已修"的条数 / 被点名条数，低于它就判没修够


# ===========================================================================
# 闸门一：合规（广告法违禁词 + **教育类特有**的效果承诺）
#
# 每项：正则 → 风险等级 → 人话解释。这是一道**粗筛**，宁可多报也别漏报，
# 最终判断仍要人工复核，且不等于平台官方审核结论。
#
# 【教育类特有】广告法禁止教育、培训广告对通过考试、获得学位学历或合格证书
# 作保证性承诺，所以「保过 / 包过 / 包学会 / 保证提分 / 包就业」单列一档高风险。
# 这一档**没有任何豁免**。
# ===========================================================================

# 「第一」的可枚举上下文豁免（同族踩过：长文里「第一年」「第一步」是**序数**，
# 不是最高级宣称；一刀切拦下的后果是用户干脆把整个合规闸门关掉，那比漏报更糟）。
FIRST_ORDINAL_AFTER = (
    "次|年|天|步|个|条|款|批|周|月|季|轮|种|点|部|遍|章|节|课|集|届|期|流|层|类"
    "|句|段|行|件|版|稿|笔|单|场|讲|单元|课时"
)
BANNED_PATTERNS = [
    (r"保过|包过|包学会|保证学会|保证提分|提分保证|保就业|包就业|包分配|一次通过|保上岸",
     "高", "教育、培训广告不得对通过考试 / 获得证书作保证性承诺（广告法明令禁止）"),
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎)", "高",
     "广告法第九条禁止「最高级」用语"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    (r"第一(?!" + FIRST_ORDINAL_AFTER + r")", "高",
     "「第一」类排他性表述"),
    (r"排名第一|销量第一|口碑第一|行业第一|全国第一|全网第一|全球第一|世界第一", "高",
     "「第一」类排他性表述"),
    (r"No\.?\s*1|TOP\s*1|top\s*1", "高", "「第一」类排他性表述"),
    (r"国家级|世界级|全球级|国际级", "高", "「国家级」等权威性词汇属明令禁止"),
    (r"100\s*%|百分之百|百分百", "高", "绝对化效果承诺"),
    (r"绝对(有效|安全|放心|不会|能|可以)|保证(有效|成功|赚钱)|无效退款", "高",
     "绝对化保证与效果担保"),
    (r"包治|根治|治愈|药到病除|无副作用|零副作用", "高",
     "医疗功效宣称，非药品 / 医疗器械不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报", "高",
     "投资类收益承诺"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐", "高",
     "不得虚构权威背书"),
    (r"免费领|免费送|0\s*元购|白送", "中", "可能构成虚假优惠或诱导分享"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天", "中",
     "促销时限表述需与实际活动一致"),
    # 【真机误伤修正】裸的「唯一」被拦下过：讲义里写「组名是你后面排序、复查的
    # **唯一线索**」—— 这是日常中文，不是排他性宣称。处理口径与同族收紧「特效」「唯一」
    # 那次一致：**把裸词收紧成可枚举的排他性搭配**。
    # 「唯一官方授权」「唯一选择」这类照拦，裸的「唯一线索」不再命中。
    (r"独家|唯一(选择|指定|授权|官方|认证|品牌|推荐|渠道|合作|供应商|代理|经销)"
     r"|首个|首创|填补空白|领先(品牌|技术)", "中",
     "排他性表述需有可举证依据"),
    (r"纯天然|无添加|零添加|无毒无害", "中", "成分宣称需与检测报告一致"),
    (r"点击链接|加微信|私信我|扫码(加|进)|vx|VX|微信号", "中",
     "站外导流，平台普遍限制"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看", "中", "标题党式诱导"),
    (r"[！!]{2,}|[?？]{3,}", "低", "标点堆砌，易被判标题党 / 低质"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}
# 合规分压制：命中高/中/低风险时，合规维度的最高分（大模型给几分都压到这以下）
COMPLIANCE_CAP = {"高": 1, "中": 4, "低": 7}

# 「最X」的可枚举上下文豁免表。
# 事故复盘：`最大的区别` / `最主要的是` 这类是**普通中文用法**，不是最高级商品宣称。
# 开了豁免口子，但同时加一条**句首不豁免**：句首的「最大区别是…」是标题式宣称，照拦。
SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥", "低", "高", "多", "少", "大", "小", "早", "晚",
)
SUPERLATIVE_OK_RE = re.compile(r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")
# 句首判定：命中处前面只有空白，或前一个非空白字符是句末标点/换行 → 视为句首。
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")

# 「警告语境」标记词：命中处**前后 24 字**内出现它们，说明这句话在**提到**违禁词
# 而不是在**用**它。
#
# 【事故复盘 —— 同族 review-board 真机踩到过】评审自己写「本文已删除保证提分的表述」
# 这类**提到式**表述，被本地的合规闸门当成违规拦下，整轮产出作废。
# 本包是课程教研场景，这个形态更常见：质检的结论里必然要写
# 「不得出现保过这类承诺」，教研的设计卡里也要写「不做效果承诺」。
#
# 但闸门必须仍然有牙，所以豁免是**双条件**的，且材料侧不走豁免：
#   · 产出侧：前后 24 字内有警告标记词 → 豁免，但**每一处都留原因**（exempted 列表）
#   · 材料侧（用户给的 brief）：**照拦不误**，不豁免（用户材料里写了保过，就是要拦）
WARNING_MARKERS = (
    "禁止", "不得", "不许", "不准", "违规", "违法", "删除", "删掉", "不放", "不能写",
    "避免", "杜绝", "风险", "违规词", "违禁", "检查", "自查", "警示", "反面", "错误示范",
)
WARNING_WINDOW = 24


def _superlative_is_normal_usage(text, m):
    """「最X」后面接的是比较或程度词，**且不在句首** → 判为普通用法，不拦。

    两个条件缺一不可：
      1. 后文落在可枚举的豁免表里（SUPERLATIVE_OK_AFTER）
      2. 命中处不在句首 —— 句首的「最大区别是…」是标题式最高级宣称，照拦
         （课件的**页标题几乎全在句首**，所以这条对本包比对同族更关键）
    """
    if not m.group(0).startswith("最"):
        return False
    before = (text or "")[:m.start()]
    if not before.strip() or _SENT_END_RE.search(before):
        return False                       # 句首 → 不豁免
    return bool(SUPERLATIVE_OK_RE.match((text or "")[m.end():]))


def check_ordinal_exemption(text, m):
    """「第一」是不是**序数 / 枚举标记**（不是排他性宣称）？是则豁免。

    三条判据，命中其一即豁免：

      1. 后接序数量词 —— 「第一年」「第一步」「第一节课」这类。
      2. 后接**计量词 + 普通名词** —— 「第一台」「第一款」「第一个月」。
         判据取「后接量词」而不是「后接任意名词」，是为了**不放过**
         「第一品牌」「第一选择」这类真正的排他性表述 —— 那两个后面不是量词。
      3. **句首 + 顿号/逗号/冒号** —— 「第一，边看边剪。第二，只记内容。」
         真机跑出来的误伤：讲义里分条列举常见错误几乎必然用「第一，… 第二，…」，
         早先没有这一条，整份讲义被合规闸门拦下、判「第一」类排他性表述。
         这是**枚举标记**，与「销量第一」毫无关系。
         限定在句首是为了不放过「他是第一名」这类句中用法。

    没有命中豁免的（「第一名」「第一品牌」「销量第一。」）照拦，且豁免项会记进
    `exempted`，**不静默放过**。
    """
    if m.group(0) != "第一":
        return False
    after = (text or "")[m.end():]
    if re.match(r"^(?:" + FIRST_ORDINAL_AFTER + r")", after):
        return True
    if re.match(r"^[台款个只把种条部支瓶盒套间场次]", after):
        return True
    before = (text or "")[:m.start()]
    if (not before.strip() or _SENT_END_RE.search(before)) \
            and re.match(r"^\s*[，,、：:]", after):
        return True
    return False


def _warning_context(text, m):
    """命中处前后 WARNING_WINDOW 字内有没有警告标记词？返回命中的标记词或 None。

    只在**产出侧**用。材料侧不调用它 —— 用户材料里写了违禁词就是违规，没有豁免。
    """
    t = text or ""
    lo = max(0, m.start() - WARNING_WINDOW)
    hi = min(len(t), m.end() + WARNING_WINDOW)
    win = t[lo:hi]
    for w in WARNING_MARKERS:
        if w in win:
            return w
    return None


def _ordinal_exempt_reason(text, m):
    """「第一」被豁免时到底是哪一种用法？返回原因或 None（给台账用）。

    与 `check_ordinal_exemption` 同一套判据，只是把「哪一种豁免」也说出来 ——
    台账上写「序数用法」而实际是「枚举标记」会让人以为是别的问题。
    """
    if not check_ordinal_exemption(text, m):
        return None
    after = (text or "")[m.end():]
    before = (text or "")[:m.start()]
    if re.match(r"^(?:" + FIRST_ORDINAL_AFTER + r")", after) or \
            re.match(r"^[台款个只把种条部支瓶盒套间场次]", after):
        return "序数用法（后接量词）"
    if (not before.strip() or _SENT_END_RE.search(before)) \
            and re.match(r"^\s*[，,、：:]", after):
        return "枚举标记（句首「第一，…第二，…」）"
    return "序数用法"


def compliance_scan(text, quoted=False, produce_side=True):
    """扫一遍违禁词，返回 (命中列表, 被豁免列表)，命中按风险等级排序。

    `produce_side=True` 时启用双重豁免（普通中文「最X」/「第一」序数 + 警告语境），
    每一处豁免都留下原因；`produce_side=False`（材料侧）**只**保留语言层面的豁免，
    警告语境豁免不生效 —— 材料里写了就是写了。

    同一处文字可能在文中出现多次（一次是警告语、一次是真的承诺），
    所以判定按**每一处出现**做，任一处未被豁免就算命中。
    """
    hits, exempted, seen = [], [], set()
    t = text or ""
    for rx, lvl, why in BANNED_RE:
        for m in rx.finditer(t):
            if _superlative_is_normal_usage(t, m):
                exempted.append({"word": m.group(0), "level": lvl, "reason": "普通中文用法（不在句首）",
                                 "context": t[max(0, m.start() - 12):m.end() + 12]})
                continue
            if check_ordinal_exemption(t, m):
                exempted.append({"word": m.group(0), "level": lvl,
                                 "reason": _ordinal_exempt_reason(t, m) or "序数用法",
                                 "context": t[max(0, m.start() - 12):m.end() + 12]})
                continue
            if produce_side:
                wm = _warning_context(t, m)
                if wm:
                    exempted.append({
                        "word": m.group(0), "level": lvl,
                        "reason": "警告语境（前后 {} 字内有「{}」）—— 在**提到**禁令而不是在承诺".format(
                            WARNING_WINDOW, wm),
                        "context": t[max(0, m.start() - 12):m.end() + 12]})
                    continue
            word = m.group(0)
            key = (word, lvl)
            if key in seen:
                # 同一个词命中多条规则时只记一次，但**不 break** ——
                # break 会让后面的规则（教育类效果承诺那条）整轮被跳过，
                # 实测踩过：一句里同时有「保证提分」和「最好」时，只报出了后者。
                continue
            seen.add(key)
            hits.append({"word": word, "level": lvl, "why": why,
                         "context": t[max(0, m.start() - 12):m.end() + 12]})
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits, exempted


def apply_safe_replacements(text):
    """把**登记在 SAFE_REPLACEMENTS 里**的违禁词替换成安全替代词（纯本地）。

    只在质检判 `fix` 时用。替换完必须本地复扫确认干净，否则按否决处理。
    返回 (新文本, 改了什么)。
    """
    out = text or ""
    changes, seen = [], set()
    for rx, lvl, why in BANNED_RE:
        # 从长到短替换，避免"最便宜"被"最低"的规则先切碎
        for m in sorted(rx.finditer(out), key=lambda x: -len(x.group(0))):
            if _superlative_is_normal_usage(out, m) or check_ordinal_exemption(out, m):
                continue
            if _warning_context(out, m):
                continue
            word = m.group(0)
            if word in seen or word not in SAFE_REPLACEMENTS:
                continue
            seen.add(word)
            changes.append({"word": word, "level": lvl,
                            "replaced_with": SAFE_REPLACEMENTS[word], "why": why})
    for c in changes:
        out = out.replace(c["word"], c["replaced_with"])
    if changes:
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r"（\s*）|\(\s*\)", "", out)
    return out, changes


# ===========================================================================
# 闸门二：占位符残留
#
# 讲义是大模型一次吐上千字，模板没替换干净的形态比标题场景多得多：
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
     "残留了「（此处省略）」—— 模型把该写的内容省略了"),
    (re.compile(r"(?<![A-Za-z0-9])X{3,}(?![A-Za-z0-9])"), "XXX", "残留了占位符 `XXX`，忘了替换"),
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
# 三条命中判据（任一即命中）：
#   exact    去掉标点后完全相同
#   jaccard  字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
#   contain  示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（示例被夹带进更长的句子里）
#
# 【为什么必须有第三条】Jaccard 的分母是两份二元组的**并集**，产出越长，
# 示例那一侧被摊薄得越狠 —— 示例原样嵌进去也会掉到 0.75 以下侥幸放行。
# 覆盖度只看"示例被抄了多少"，不看产出有多长，摊薄对它无效。
# ===========================================================================

ECHO_SIM = 0.75          # 同族实测标定：正常产出与跨主题示例最高只 0.174
ECHO_CONTAIN = 0.60      # 同族实测：真实历史产出里覆盖度最大 0.500，余量 1.2 倍、误伤 0
ECHO_MIN_LEN_FLOOR = 6   # 长度守卫的绝对下限，防极短串的二元组噪声
ECHO_APPLY_MIN = 24      # contain 判据的**适用窗口**：只对 ≥ 24 字的产出片段判


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
    """字符二元组集合。

    【术语一致性必须用得上单字】「完播率」与「完看率」的二元组是
    {完播, 播率} 与 {完看, 看率} —— **交集为空**，纯二元组相似度是 0.0，
    而它们显然是同一个概念的两种叫法。所以这里把**单字**也并进特征集合，
    只差一个字的两种叫法就有了公共特征（完 / 率）。
    对本包其他用途（照抄示例、锚点）没有影响：那两个场景比的是整句，
    单字本来就会被二元组覆盖。
    """
    s = _norm_anchor(s)
    if len(s) < 2:
        return set(s)
    grams = {s[i:i + 2] for i in range(len(s) - 1)}
    grams |= set(s)
    return grams


def _similarity(a, b):
    """字符二元组 Jaccard 相似度，0~1。"""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(len(ba | bb))


def prompt_echo(text, samples=None, rule_contain=True):
    """文本是否与提示词里的示例"抄得太近"。

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"。

    【contain 的适用窗口】覆盖度判据的分母是**示例的二元组全集**。当产出比示例短、
    或两者都只有几个字时，几个巧合的二元组就能把覆盖度顶到 0.6 以上。所以 contain
    只在产出片段 ≥ ECHO_APPLY_MIN 字时启用；更短的片段由 exact / jaccard 负责
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


def prompt_echo_scan(text, samples=None, label="产出"):
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
# 闸门四：学习目标可考核性（**本包特有**）
#
# 学习目标写成「了解 / 熟悉 / 掌握 XX」是课程开发里最常见的偷懒方式：
# 这种目标**无法考核** —— 学员学完说"我了解了"，你也无法说他没了解。
# 可考核的目标必须有**可观察的行为**或**可测的标准**：
#   ✅ 能独立写出一个包含三段的开场脚本
#   ✅ 在 5 分钟内用表格算出本次排期的素材缺口
#   ❌ 了解内容运营的整体思路
#
# 判定：命中不可考核动词（了解/熟悉/掌握/认识/体会/理解…）**或**
# 通篇找不到可考核特征词（能/会/写出/算出/对照/列出/完成/独立/分钟/字/条/%
# 这类）→ 判不可考核。**每一项**都单独判、逐条列出，不是整卡一刀切。
# ===========================================================================

UNASSESSABLE_VERBS = (
    "了解", "熟悉", "认识", "理解", "体会", "感悟", "感知", "领略", "知晓", "知道",
    "掌握", "懂得", "明晰", "明白", "感受", "领会", "领悟", "意识到", "关注",
)
UNASSESSABLE_RE = re.compile("|".join(UNASSESSABLE_VERBS))

# 可考核特征词：**可观察的行为**。这不是"必须出现某个词"，而是
# "找不到任何可观察的行为"就判不可考核。
#
# 【标定过程 —— 这条闸门真机第一次跑就把两份合格的目标判错了】
# 早先的版本要求「有行为**且**有刻度（时长/条数/字数/合格线）」，
# 真机跑出来的两条目标（「能写出 3 个候选开场钩子并挑出 1 个」这类）就被判不可考核 ——
# 那是**误伤**：行为已经可观察，缺刻度不构成"无法考核"。
# 误伤的代价很实在：用户遇到几次就会把整道闸门关掉，而那之后真正该拦的
# （「了解 XX」「熟悉 XX」「掌握 XX」）也一起不拦了。
# 所以标定成：**不可考核动词一票否决 + 必须有"行为动词 + 对象"**，刻度只作为加分项、
# 不再单独构成失败。它仍然拦得住本包真正要拦的那一类（无行为动词的目标）。
OBSERVABLE_RE = re.compile(
    r"写出|画出|算出|列出|说出|讲出|复述|演示|做出|完成|独立(完成|写出|操作)"
    r"|对照|核对|检查|判断|区分|选出|排序|拆解|拆分|重构|修改|改写|搭建|配置|执行|提交"
    r"|能|会|按.{0,6}(步骤|流程|模板|清单|标准)"
)
# 「行为动词 + 对象」：动词后面至少跟两个字的具体对象，才算落到了可检验的东西上
OBSERVABLE_ACTION_RE = re.compile(
    r"(写出|画出|算出|列出|说出|讲出|复述|演示|做出|完成|对照|核对|检查|判断|区分"
    r"|选出|排序|拆解|拆分|重构|修改|改写|搭建|配置|执行|提交)\s*[^，。；、\s]{2,}")
MEASURABLE_RE = re.compile(
    # 「数字 + 量词」是最常见的可测标准形态，量词要列全（类 / 档 / 版 / 门 / 轮 / 阶…）
    r"\d+\s*(分钟|小时|秒|天|周|次|遍|条|个|页|字|句|段|步|项|张|份|人|类|档|版|门|轮|阶|层|组|批|款|种|处|道|%|％)"
    r"|[0-9一二三四五六七八九十两]+\s*(分钟|小时|秒|天|周|次|遍|条|个|页|字|句|段|步|项|张|份|人|类|档|版|门|轮|阶|层|组|批|款|种|处|道)"
    # ⚠️ 中文数词也要算「可测」：模型写「包含三段」「至少五条」时用的是中文数字，
    # 早先只用 `\d+` 会把这类**完全合格**的目标误判成"没刻度"。实测踩到过。
    r"|(包含|涵盖|覆盖|至少|不超过|不少于|多于)\s*[0-9一二三四五六七八九十两]+"
    r"|百分|至少|不(超过|少于|低于)|以内|之内|以上|以下|合格|达标|标准|评分|口径|模板"
)


def objective_assessable(obj):
    """单个学习目标能不能被考核？返回 (是否可考核, 原因)。

    判定顺序：
      1. **不可考核动词一票否决** —— 「了解 / 熟悉 / 掌握 / 理解」这类，
         学员学完说"我了解了"，你无法说他没了解。两头都占的写法（「了解并掌握」）
         照样判不可考核，因为前半截就不可考。
      2. 必须有**可观察的行为** —— 能写出 / 能算出 / 能列出 / 能演示 …
      3. 有刻度（几分钟 / 几条 / 多少字 / 合格线）更好，但**不单独构成失败**：
         把刻度当硬要求会误伤「能写出 3 个候选开场钩子」这种合格目标。
    """
    text = str(obj or "").strip()
    if not text:
        return False, "学习目标是空的"
    bad = UNASSESSABLE_RE.findall(text)
    if bad:
        return False, ("写成「{}」这类**不可考核**的动词：学员学完说'我了解了'，"
                       "你无法说他没了解。要改成可观察的行为或可测的标准".format(
                           "、".join(sorted(set(bad)))))
    if not OBSERVABLE_RE.search(text):
        return False, ("找不到任何**可观察的行为**（写出 / 算出 / 列出 / 演示 / 能…）"
                       "—— 这条目标无法用产出物或动作来检验")
    if not (OBSERVABLE_ACTION_RE.search(text) or MEASURABLE_RE.search(text)):
        return False, ("只有「能 / 会」这类泛泛的表述，**没有落到具体对象或刻度上**"
                       "（写出什么？几分钟内？几条？）—— 仍然考不了")
    return True, ""


def check_objectives(objectives):
    """把一条学习目标列表逐条判可考核性。

    返回 {"ok","total","bad":[...]}；`ok=True` 当且仅当**每一条**都可考核。
    """
    objs = [str(x).strip() for x in (objectives or []) if str(x or "").strip()]
    bad = []
    for i, o in enumerate(objs, 1):
        ok, why = objective_assessable(o)
        if not ok:
            bad.append({"index": i, "objective": o, "why": why})
    return {"ok": not bad and bool(objs), "total": len(objs), "bad": bad,
            "empty": not objs,
            "why": ("没有学习目标" if not objs else
                    ("{} / {} 条学习目标不可考核".format(len(bad), len(objs)) if bad
                     else "{} 条学习目标全部可考核".format(len(objs))))}


# ===========================================================================
# 闸门五：知识点依赖 / 前置缺失（**本包特有**）
#
# 讲义里用到一个术语，但**前面从来没有讲过**，学员就会在这里卡住。
# 这是课程（而不是单篇文章）独有的失败形态：单篇稿子没有"前面"。
#
# 判定是**确定性**的：对每一节的术语候选做两件事 ——
#   1. 在**本节之前**的所有讲义 + 设计卡的「前置知识」里找过没有
#   2. 没找到 → 记为「前置缺失」，逐条列出（术语 + 出现在哪一句）
#
# 【为什么不能只看设计卡的术语表】术语表是教研凭想象写的，讲师临场引入的
# 新术语（比如突然冒出"黄金三秒""完播率") 不会在里面。实测正是靠这一条
# 抓住了设计卡里没有、但讲师在第二节才第一次用到的一个术语。
# ===========================================================================

# 术语候选的抓取规则（五条，都是课程文本里最常见的"新概念"形态）：
#   1. 中文引号 / 书名号里 2~12 字的短语（讲师介绍新概念时最常用引号）
#   2. 「X 叫 Y」「X 称为 Y」「所谓 Y」「Y 是指」这类定义句式里的 Y
#   3. **课程领域里公认的术语**（完播率 / 完看率 / 转化率 …）—— 这一条是必须的：
#      光靠后缀模式会把「我们来看完播率」整段抓成术语（中文没有词边界），
#      有了这一条就能**先**把裸术语本身抓出来。
#   4. 「2~4 字修饰 + 名词后缀」（漏斗指标 / 漏斗模型 / 素材清单 …），
#      前缀限死 2~4 字并过滤掉高频功能词开头，避免把整句吞进来。
#   5. 明显的拉丁字母缩写（2~8 个字母，如 ROI / CTR）
TERM_QUOTE_RE = re.compile(r"[「“《]([^」”》\n]{2,12})[」”》]")
TERM_DEFINE_RE = re.compile(
    r"(?:叫做|称为|称之为|所谓|叫作|又名)\s*[「“]?([\u4e00-\u9fffA-Za-z0-9]{2,10})[」”]?"
    r"|([\u4e00-\u9fff]{2,10})\s*[,，、:：]?\s*(?:指的是|是指|说的是|指的是：)")
# 领域术语表：这些词的"裸形态"本身就是一个知识点，必须能被单独抓出来
TERM_DOMAIN_RE = re.compile(
    r"(?:完播率|完看率|完读率|点击率|转化率|留存率|复购率|打开率|互动率|涨粉率|跳出率"
    r"|漏斗模型|漏斗指标|内容矩阵|账号定位|黄金三秒|封面点击|素材清单|素材库|素材表"
    r"|分镜表|时间轴|时间码|关键帧|转场点|字幕轴|音量包络|拍摄脚本|选题库|选题表"
    r"|目标受众|用户画像|人群标签|投放预算|排期表|验收标准|自查清单|评估口径"
    r"|脚本结构|叙事结构|三段式|四段结构|开场钩子|结尾引导|转化路径|行为漏斗)")
TERM_SUFFIX_RE = re.compile(
    r"([\u4e00-\u9fff]{2,4}(?:率|度|法|模型|矩阵|漏斗|公式|协议|框架|口径|"
    r"流程|模板|清单|标准|效应|定律|原则|定价|折算|链路|画像|权重|指标))")
TERM_LATIN_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,8})(?![A-Za-z0-9])")

# 以这些词开头的候选不算术语（中文没有词边界，抓取先要**切干净**）
TERM_BAD_PREFIX = (
    "我们", "你们", "他们", "这个", "那个", "本节", "这一", "那一", "它的", "他的",
    "这样", "那样", "如果", "因为", "所以", "但是", "而且", "然后", "接着", "下面",
    "上面", "这是", "那是", "有的", "一种", "一个", "就是", "不是", "还有",
    "比如", "例如", "叫做", "称为", "所谓", "指的", "说的", "今天", "明天",
    # 这些是**常用虚词 / 单字动词**开头：中文没有词边界，后缀模式容易把
    # 「节说完播率」「与完看率」「看了完播率」整段抓进来。以它们开头的候选一律丢掉。
    "节", "与", "和", "看", "的", "是", "在", "把", "从", "对", "为", "以", "用",
    "讲", "说", "先", "再", "也", "都", "要", "会", "能", "很", "最", "更", "只",
    "它", "他", "她", "我", "你", "谁", "什", "怎", "如", "若", "则", "并",
    "做", "打开", "切成", "分成", "归成", "起", "给", "拿", "放", "让", "被",
    "未命名",
)
# 术语后面**可以**紧跟的收尾字（这些不算"被切断了"）
TERM_TAIL_OK = set("的是与和也都要会能就再很更最了着呢吗吧的话")


def _is_boundary(text, start, end, strict=False):
    """候选是不是**独立**的术语形态。

    【两个坑，都是真机跑出来的】

    坑一：不能要求"前后都不是汉字"。「我们来看完播率」里「完播率」前面紧挨着「来」，
    早先要求前后都是边界，结果是 `extract_terms("我们来看完播率")` 一个词都抓不出来
    —— **闸门等于没有**。

    坑二：也不能只要求"后面不是汉字"。后缀模式会从任意位置切出 2~4 个汉字，
    真机跑出来的是「老板讲用料」「后厨流程」「完整记完清单」这类**动宾短语**，
    台账里 17 条"前置缺失"有 11 条是这种噪声 —— 台账一多报，人就不看台账了。

    所以分两档：
      · 宽松（默认，用于**领域术语表**这类高置信来源）：只要求后面不是汉字
      · 严格（`strict=True`，用于后缀模式这类低置信来源）：还要求**前面是边界**
        （句首 / 标点 / 空白 / 数字），这样「的」「第」「把」这类词后面的切段会被丢掉
    """
    t = text or ""
    if end < len(t):
        after = t[end]
        if re.match(r"[\u4e00-\u9fff]", after) and after not in TERM_TAIL_OK:
            return False
    if strict and start > 0:
        before = t[start - 1]
        if re.match(r"[\u4e00-\u9fff]", before):
            return False
    return True


def _term_ok(raw):
    """候选是不是一个像样的术语（切干净 + 不在停用表里）。"""
    s = (raw or "").strip()
    if len(s) < TERM_MIN_CHARS or len(s) > 16:
        return False
    if s in TERM_STOP:
        return False
    for p in TERM_BAD_PREFIX:
        if s.startswith(p) and len(s) > len(p):
            return False
    return True


def _trim_term(raw):
    """把一个偏长的候选**收窄**到里面真正的那条领域术语。

    【为什么需要这一步】中文没有词边界，后缀模式会把「我们来看**完播率**」
    「这一**节说完播率**」整段抓进来。早先的做法是丢前缀词，但那只解决了一半
    （「来看完播率」「节说完播率」照样漏）。这里的做法是：如果候选里**含**一条
    领域术语表里的短术语，就取那一条（最长优先）。
    """
    s = (raw or "").strip()
    if not s:
        return s
    best = ""
    for m in TERM_DOMAIN_RE.finditer(s):
        cand = m.group(0)
        if len(cand) > len(best):
            best = cand
    if best and len(best) < len(s):
        return best
    return s


def _ctx(text, start, end, pad=16):
    """取命中位置附近的上下文（给台账看的一句话）。"""
    return (text or "")[max(0, start - pad):end + pad].replace("\n", " ")


def extract_terms(text):
    """抽出一段文本里的术语候选（去重保序，已过滤通用词与切坏的片段）。

    每个来源带自己的 `strict` 档位：领域术语表是**高置信**来源（宽松），
    后缀模式 / 引号 / 定义句式是**低置信**来源（严格，要求前面是边界）。
    """
    t = text or ""
    out, seen = [], set()
    sources = (
        (TERM_DEFINE_RE, True), (TERM_QUOTE_RE, True),
        (TERM_DOMAIN_RE, False), (TERM_SUFFIX_RE, True), (TERM_LATIN_RE, False),
    )
    for rx, strict in sources:
        for m in rx.finditer(t):
            groups = [g for g in m.groups() if g]
            raw = _trim_term((groups[-1] if groups else m.group(0)).strip())
            if not _term_ok(raw):
                continue
            try:
                st, en = m.span(1) if m.lastindex else m.span(0)
            except (IndexError, TypeError):
                st, en = m.span(0)
            if not _is_boundary(t, st, en, strict=strict):
                continue
            norm = _norm_anchor(raw)
            if len(norm) < TERM_MIN_CHARS or norm in TERM_STOP or norm in seen:
                continue
            # **出现次数过滤**：真正的知识点在一节里会被反复使用（拉片 / 时间码 /
            # 分镜清单），而「老板讲用料」「后厨流程」这种**引用一次的例子**只出现一次。
            # 真机台账里剩下的噪声全是这一类，所以只收出现 ≥ TERM_MIN_HITS 次的候选。
            if _norm_anchor(t).count(norm) < TERM_MIN_HITS:
                continue
            seen.add(norm)
            out.append({"term": raw, "norm": norm, "context": _ctx(t, m.start(), m.end())})
    return out

# 通用词停用表：这些不是"知识点"，是日常中文。不做停用会让台账被噪声淹没，
# 而台账一多报，人就不看台账了 —— 那等于没有这个闸门。
TERM_STOP = {
    "内容", "方式", "方法", "问题", "结果", "目标", "标准", "流程", "模板", "清单",
    "时间", "情况", "数据", "信息", "用户", "客户", "公司", "团队", "学习", "课程",
    "讲义", "课件", "作业", "练习", "考试", "阶段", "步骤", "重点", "难点", "基础",
    "能力", "水平", "经验", "效果", "作用", "原因", "特点", "优势", "缺点", "方向",
    "结构", "框架", "模型", "指标", "口径", "链路", "权限", "工具", "平台", "系统",
    "视频", "图片", "文字", "标题", "封面", "账号", "粉丝", "流量", "评论", "直播",
    "什么是", "为什么", "怎么样", "这一节", "下一节", "本节课", "综上所述",
}
TERM_MIN_CHARS = 2
# 一个候选至少要在这一节里出现几次才算"术语"（见 extract_terms 里的说明）
TERM_MIN_HITS = 2
TERM_MAX_PER_SECTION = 12      # 单节最多取这么多个术语候选，超出按出现顺序截取


def _term_sentence(text, term):
    """找到术语所在的整句（引用给读者看的是句子，不是片段）。"""
    for s in split_sentences(text):
        if term and term in s:
            return s
    return _ctx(text or "", 0, 0)


def check_prerequisites(sections, prerequisites=None):
    """逐节检查「用到但前面没讲过」的术语。

    参数
      sections       有序列表：[{"id","title","text","defined_terms"}…]
                     （**必须是课程的讲述顺序**）；`defined_terms` 是这一节
                     **引入了**的术语（讲师自报的 `terms_introduced`，本地会并上
                     正文里的定义句式）
      prerequisites  设计卡里的前置知识（字符串列表）；它们在下游讲义里**不算缺失**

    【一个设计上的坑，说明为什么"引入了"必须单独一栏】早先的版本把**每一节出现的
    术语**都直接记进"已讲过"，于是**这个闸门永远不可能触发**：第 2 节用到的新术语，
    在第 1 节只是被**提到**过（不是被**讲过**），也会被算作"前面讲过了"。
    一个打不响的闸门等于没有闸门，所以"出现过"与"引入过"必须分开：
    只有**引入过**的术语才进入已知集合，纯提及不算。

    返回 {"ok","total_terms","missing":[...],"introduced":{sec_id:[terms]}}
      missing 每项：{"section","term","why","sentence"}
    """
    known = set(_norm_anchor(p) for p in (prerequisites or []) if str(p or "").strip())
    known.discard("")
    introduced, missing, total = {}, [], 0
    reported = set()                  # 同一个术语只报一次，避免台账刷屏
    for sec in sections or []:
        sid = str(sec.get("id") or "")
        text = sec.get("text") or ""
        # 本节"自产自销"：正文里用定义句式当场解释掉的，也算这一节引入了。
        # ⚠️ TERM_DEFINE_RE 有两个分支（A 叫 X / Y 指的是 Z），所以两个捕获组都要取。
        defined_here = set()
        for m in TERM_DEFINE_RE.finditer(text):
            for g in m.groups():
                n = _norm_anchor(g or "")
                if n:
                    defined_here.add(n)
        for t in (sec.get("defined_terms") or []):
            n = _norm_anchor(t)
            if n:
                defined_here.add(n)
        terms = extract_terms(text)[:TERM_MAX_PER_SECTION]
        new_here = []
        for tm in terms:
            total += 1
            norm = tm["norm"]
            if norm in known:
                continue                   # 前面真的讲过 → 放行
            if norm in defined_here:
                new_here.append(tm["term"])   # 本节就地解释了 → 也算这一节引入
                continue
            if norm in reported:
                continue                   # 同一术语只报一条
            missing.append({
                "section": sid, "term": tm["term"],
                "sentence": _term_sentence(text, tm["term"]),
                "why": ("这一节用到「{}」，但它既不在设计卡的「前置知识」里，"
                        "也没有在任何**更早的**一节里被讲过（只是出现过不算讲过）"
                        "—— 学员在这里会卡住").format(tm["term"]),
            })
            reported.add(norm)
        for n in defined_here:
            known.add(n)
        introduced[sid] = new_here
    return {"ok": not missing, "total_terms": total, "missing": missing,
            "introduced": introduced,
            "why": ("发现 {} 处前置缺失（用到但前面没讲过的术语）".format(len(missing))
                    if missing else "没有前置缺失")}


def _near_same_shape(a, b):
    """两个术语是不是「同一个概念的两种叫法」？判据：**同长度、只差一个字**。

    【为什么不用 Jaccard】「完播率」与「完看率」的字符二元组交集为空，
    并上单字之后相似度也只有 0.25 —— 靠相似度阈值判这一条会**永远不触发**。
    差一个字是中文术语改名最典型的形态（完播率/完看率、转化率/转成率、
    素材库/素材表），所以直接用逐字比对，判据确定性、可解释。
    """
    if len(a) != len(b) or len(a) < 3:
        return False
    diff = sum(1 for x, y in zip(a, b) if x != y)
    return diff == 1


def check_terminology(sections):
    """术语一致性：同一个概念在整门课里是不是用了同一个说法。

    【诚实说明这是启发式】「完播率」和「完看率」是不是同一个概念，本质是**语义判断**，
    本地判不了。所以这一条只做两件事：
      · 逐字比对，抓「同长度只差一个字」的两种叫法（确定性判据）
      · 把各节引入的术语并排列出来，让人一眼看到"同一门课里出现了两种叫法"
    真正的一致性判定交给质检角色（它能读语义）。
    """
    suspects = []
    for sec in sections or []:
        terms = extract_terms(sec.get("text") or "")
        for i in range(len(terms)):
            for j in range(i + 1, len(terms)):
                a, b = terms[i]["norm"], terms[j]["norm"]
                if a == b or not _near_same_shape(a, b):
                    continue
                suspects.append({
                    "section": str(sec.get("id") or ""),
                    "a": terms[i]["term"], "b": terms[j]["term"],
                    "why": ("同一节里出现了两种只差一个字的说法（{} / {}），"
                            "疑似同一概念两种叫法").format(terms[i]["term"], terms[j]["term"]),
                })
    return {"ok": not suspects, "suspects": suspects,
            "why": ("{} 处术语一致性疑点".format(len(suspects)) if suspects else "无一致性疑点")}


# ===========================================================================
# 闸门六：质检锚点校验（质检的引文必须在讲义里真实存在）
#
# 只是"在提示词里写一句请引用原句"，模型经常给你泛泛而谈
# （「建议加强前后衔接」「整体信息量可以更足」）—— 这种意见**没法执行**：
# 改哪一句？改成什么？讲师拿到它只能重写一遍。
#
# 所以本包不采信质检的引文，而是**本地校验**：它引的那句话在不在讲义里？
#   exact      归一化后与某一整句完全相同
#   substring  归一化后是某一整句的一部分（只引半句，最常见）
#   fuzzy      与最像的那一句 Jaccard ≥ ANCHOR_SIM 且引文够长（轻改写式引用）
#   unverified 以上都不成立 → **判为锚点幻觉**，不进讲师的修订输入，并计入未锚定率
#
# 未锚定率超过 ANCHOR_MAX_MISS → 判「质检不达标」，压分 + 标红 + stderr 汇总 + 退出码 3。
# ===========================================================================

ANCHOR_MIN_SUBSTR = 4     # 精确子串匹配的最低长度
ANCHOR_MIN_CHARS = 8      # 模糊匹配的最低长度（二元组太少会虚高，门槛必须高）
ANCHOR_SIM = 0.55         # 模糊匹配阈值
ANCHOR_MAX_MISS = 0.40    # 未锚定率超过它就判「锚点失败」


def verify_anchor(quote, sentences, norms=None):
    """把质检的引文锚定到讲义的某一句话上。返回 (ok, rule, index)。"""
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


def anchor_issues(issues, sections):
    """给质检的每条问题做锚点校验，返回 (锚定成功的, 未锚定的)。

    每条问题带 `section`（它说自己引的是哪一节）。锚定在**那一节**里做；
    如果那一节找不到，再退到全课程找一遍（引对了句子但记错了节号，不该判幻觉）。
    锚定成功的那条会把 `quote` **就地修正成讲义里的真实句子**（`sentence` 字段）。
    """
    by_id = {}
    for s in sections or []:
        by_id[str(s.get("id"))] = s
    sent_cache = {k: split_sentences(v.get("text") or "") for k, v in by_id.items()}
    all_sents = []
    for k in by_id:
        all_sents.extend(sent_cache[k])
    all_norms = [_norm_anchor(s) for s in all_sents]
    ok_list, bad_list = [], []
    for it in issues:
        quote = (it.get("quote") or "").strip()
        sid = str(it.get("section") or "")
        sents = sent_cache.get(sid) or []
        good, rule, idx = verify_anchor(quote, sents) if sents else (False, "unverified", -1)
        fixed_sid = sid
        if not good and all_sents:
            good2, rule2, idx2 = verify_anchor(quote, all_sents, all_norms)
            if good2:
                good, rule, idx = good2, rule2, idx2
                fixed_sid = ""
        item = dict(it)
        item["quote"] = quote
        item["anchor_rule"] = rule
        if good:
            if fixed_sid:
                item["section"] = fixed_sid
                item["sentence"] = sents[idx]
            else:
                item["section"] = ""
                item["sentence"] = all_sents[idx]
            item["sent_no"] = idx + 1
            ok_list.append(item)
        else:
            item["why_unverified"] = (
                "引文在讲义里找不到（归一化后不匹配任何整句，模糊相似度 < {:.2f}）"
                "—— 判为锚点幻觉，不进讲师的修订输入".format(ANCHOR_SIM))
            bad_list.append(item)
    return ok_list, bad_list


# ===========================================================================
# 信息不对称：结构性保证 + 调用前验证
#
# L3 与"一个模型演四个角色"的真正分界在这里。演出来的四个角色共享同一份上下文，
# 于是"课件"永远看不到一个它不知道的自评、"质检"永远顺着课件的结论走 —— 对抗是假的。
#
# 本包把"看不到什么"做成两个机制：
#   1. ROLES[*]["inputs"] / ["forbidden"] 是**字段白名单**，提示词模板按它拼装，
#      被排除的字段在物理上就没有进入 prompt 的路径；
#   2. assert_isolation() 在**每次调用前**扫一遍真实 prompt 文本，逐条验证被禁字段
#      的标记词一个都不出现。判定结果写进产出与流程记录，外部可复核。
# ===========================================================================

def check_isolation(stage, prompt_text, excluded_fields=None):
    """纯函数：检查一次调用的 prompt 里有没有混进被排除的字段。

    返回 {"stage","excluded","markers_checked","leaked","ok"}
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
                               "at": _marker_context(prompt_text, marker)})
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

    为什么是硬失败而不是打个 warning：如果课件真的看到了讲师的自我评价，这一轮
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
# 闸门七：裁决与终止条件
#
# 出口都是**显式**的，不许假装谈拢：
#   design_retries_exhausted   教研重开上限用尽仍交不出达标设计卡
#   rounds_exhausted           轮次上限用尽仍不放行
#   no_effective_change        连续两轮改动过小（讲师在原地打转）
#   stalled_same_quote         质检连续两轮指向同一段被拒文字
#   slide_rework_exhausted     课件说「放不下」，重做上限用尽仍放不下
#   inspect_send_back_exhausted 质检打回次数用尽仍不放行
# 出口 1/2/3/4 → 升级给人看；出口 5/6 与质检 veto → 带未决项产出。
# ===========================================================================

EXIT_KIND = {
    "design_retries_exhausted": "升级给人看：教研交不出达标设计卡",
    "rounds_exhausted": "升级给人看：轮次用尽，附全部未决项",
    "no_effective_change": "升级给人看：讲师在原地打转，继续跑只是烧钱",
    "stalled_same_quote": "升级给人看：质检两次指向同一段文字，讲师改不动它",
    "slide_rework_exhausted": "带未决项产出：课件说「这页放不下」，重做上限用尽仍放不下",
    "inspect_send_back_exhausted": "带未决项产出：质检打回次数用尽仍不放行",
}


def body_similarity(a, b):
    """两版讲义的相似度（字符二元组 Jaccard，去标点空白）。"""
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
        why.append("被点名 {} 条只自报修了 {} 条（{:.0%} < {:.0%}）".format(
            req, rep, ratio, FIX_RATIO_MIN))
    return {"effective": not why, "body_sim": sim, "fix_ratio": round(ratio, 3),
            "why": "；".join(why) or "有实质改动"}


def check_escalation(rounds_run, rounds_max, design_retries_used, design_retries_max,
                     strikes, slide_rework_used, slide_rework_max,
                     inspect_used, inspect_max, stalled_quote=None):
    """算出"现在该不该走显式出口"。返回出口名或 None。

    这个函数是纯函数、只读参数，**故意**不掺任何"也许还能再跑一轮"的模糊判断 ——
    模糊判断正是"假装谈拢"的来源。判定顺序 = 严重程度。
    """
    if stalled_quote:
        return "stalled_same_quote"
    if strikes > MAX_NO_CHANGE_STRIKES:
        return "no_effective_change"
    if design_retries_used > design_retries_max:
        return "design_retries_exhausted"
    if slide_rework_used > slide_rework_max:
        return "slide_rework_exhausted"
    if inspect_used > inspect_max:
        return "inspect_send_back_exhausted"
    if rounds_run >= rounds_max:
        return "rounds_exhausted"
    return None


# ===========================================================================
# 闸门八：逐页方案能不能放下（课件角色的否决权）
#
# 课件说「这页放不下」不是主观抱怨，本地给了一条**机械判据**：
#   · 每页要点条数 1~6 条，每条 ≤ 40 字
#   · 页标题 ≤ 30 字
#   · 讲稿备注 40~400 字
#   · 总页数 ≤ --max-pages
# 超了就判「放不下」，并把**实际数字与上限**都打出来（不静默截断、不自动缩字号）。
#
# 同时：课件说「放不下」时**必须**给出要拆哪一页、以及这一页对应讲义里的哪句话 ——
# 引不出讲义原句的诉求一律不算数（这是防"课件随口打回"的机制）。
# ===========================================================================

SLIDE_TITLE_MAX = 30
SLIDE_BULLET_MIN = 1
SLIDE_BULLET_MAX = 6
SLIDE_BULLET_CHARS_MAX = 40
SLIDE_NOTES_MIN = 40
SLIDE_NOTES_MAX = 400
SLIDE_TYPES = ("cover", "section", "content", "summary")


def check_deck(pages, max_pages=DEFAULT_MAX_PAGES):
    """逐页判「放不放得下」。返回 {"ok","problems":[...],"overflow":[...]}"""
    pages = [p for p in (pages or []) if isinstance(p, dict)]
    problems = []
    if not pages:
        problems.append({"kind": "empty_deck", "why": "一页都没有"})
    if len(pages) > max_pages:
        problems.append({"kind": "too_many_pages", "page": "-",
                         "why": "共 {} 页，超过 --max-pages {}".format(len(pages), max_pages)})
    overflow = []
    for i, p in enumerate(pages, 1):
        pid = str(p.get("pid") or "p{:02d}".format(i))
        title = str(p.get("title") or "").strip()
        bullets = [str(b).strip() for b in (p.get("bullets") or []) if str(b or "").strip()]
        notes = str(p.get("notes") or "").strip()
        if not title:
            problems.append({"kind": "no_title", "page": pid, "why": "这一页没有标题"})
        elif len(title) > SLIDE_TITLE_MAX:
            overflow.append({"kind": "title_too_long", "page": pid, "actual": len(title),
                             "limit": SLIDE_TITLE_MAX,
                             "why": "页标题 {} 字 > {} 字，投影上会断成两行以上".format(
                                 len(title), SLIDE_TITLE_MAX)})
        if not (SLIDE_BULLET_MIN <= len(bullets) <= SLIDE_BULLET_MAX):
            overflow.append({"kind": "bullet_count", "page": pid, "actual": len(bullets),
                             "limit": SLIDE_BULLET_MAX,
                             "why": "要点 {} 条，超出 1~{} 条的范围".format(
                                 len(bullets), SLIDE_BULLET_MAX)})
        for b in bullets:
            if len(b) > SLIDE_BULLET_CHARS_MAX:
                overflow.append({"kind": "bullet_too_long", "page": pid, "actual": len(b),
                                 "limit": SLIDE_BULLET_CHARS_MAX,
                                 "why": "单条要点 {} 字 > {} 字：「{}」".format(
                                     len(b), SLIDE_BULLET_CHARS_MAX, b[:24])})
        if notes and not (SLIDE_NOTES_MIN <= len(notes) <= SLIDE_NOTES_MAX):
            overflow.append({"kind": "notes_length", "page": pid, "actual": len(notes),
                             "limit": SLIDE_NOTES_MAX,
                             "why": "讲稿备注 {} 字，不在 {}~{} 字之间".format(
                                 len(notes), SLIDE_NOTES_MIN, SLIDE_NOTES_MAX)})
    return {"ok": not problems and not overflow, "problems": problems,
            "overflow": overflow,
            "pages": len(pages), "max_pages": max_pages,
            "why": ("{} 页里有 {} 处放不下".format(len(pages), len(overflow) + len(problems))
                    if (problems or overflow) else "{} 页全部放得下".format(len(pages)))}


def _unique_quote_match(quote, sections):
    """拿一句引文去各节里找，**只在唯一命中时**返回那节的 id。

    【为什么必须"唯一"】如果一句引文在好几节里都模糊命中（或者只隐约擦到阈值），
    那它到底属于哪一节本身就是不确定的。此时把讲师指到**第一个**命中的节，
    等于让讲师去改一节根本没问题的讲义 —— 比"定位不到"更糟。
    所以：完全相等 / 精确子串命中，且该节是**唯一**命中者 → 返回；
    只有模糊命中 → 也要求唯一，否则返回 ""。
    """
    q = _norm_anchor(quote)
    if not q:
        return ""
    exact_hits, fuzzy_hits = [], []
    for s in sections or []:
        sents = split_sentences(s.get("text") or "")
        good, rule, _idx = verify_anchor(quote, sents)
        if not good:
            continue
        if rule in ("exact", "substring"):
            exact_hits.append(str(s.get("id") or ""))
        else:
            fuzzy_hits.append(str(s.get("id") or ""))
    if len(exact_hits) == 1:
        return exact_hits[0]
    if not exact_hits and len(fuzzy_hits) == 1:
        return fuzzy_hits[0]
    return ""


def resolve_issue_section(issue, sections, pages=None):
    """把一条「放不下」的诉求**定位到具体的节**（三级回退）。

    【为什么必须有这一级】真机第一次跑就死在这里：课件说「这页放不下」，
    但它给出的 `section` 字段是空的、`page` 那一页的 `from_section` 也是空的 ——
    于是编排层「一条都定位不到具体的节」，直接走了 `slide_rework_exhausted` 出口。
    **课件的否决权就废了**：它说放不下，却派不出工。

    三级回退（顺序即为可信度）：
      1. `issue["section"]` 直接就是节 id → 用它
      2. `issue["page"]` 是页 id → 用那一页的 `from_section`
      3. 拿 `quote` 去每一节里锚点匹配，**唯一命中**的那一节就是它
    返回节 id 或 ""。
    """
    ids = {str(s.get("id")) for s in (sections or [])}
    sid = str((issue or {}).get("section") or "").strip()
    if sid and sid in ids:
        return sid
    pid = str((issue or {}).get("page") or "").strip()
    if pid and pages:
        for p in pages:
            if str(p.get("pid")) == pid:
                fs = str(p.get("from_section") or "").strip()
                if fs and fs in ids:
                    return fs
                break
    quote = str((issue or {}).get("quote") or "").strip()
    if quote:
        return _unique_quote_match(quote, sections)
    return ""


def check_slide_issue_anchor(issue, sections):
    """课件说「这页放不下」时，**必须**引得出讲义里真实的一句话。

    返回 (是否锚定成功, 修正后的 issue)。锚定失败的诉求**不算数**（不进讲师的修订输入），
    防止"课件随口打回"。
    """
    item = dict(issue or {})
    quote = str(item.get("quote") or "").strip()
    ok_list, bad_list = anchor_issues([item], sections)
    if ok_list:
        got = ok_list[0]
        got["anchor_ok"] = True
        return True, got
    got = bad_list[0] if bad_list else item
    got["anchor_ok"] = False
    got["why_unverified"] = got.get("why_unverified") or "没有给出讲义引文，诉求不算数"
    return False, got


# ===========================================================================
# 提示词
#
# 【铁律】提示词里**不许出现任何一条可直接复制的完整中文范文句**。
# 事故复盘（同族，实测抓到两例）：提示词里写过正例，模型直接产出同构句；
# 尤其严重的一例，那一批最高分的产出**一字不差**就是提示词里的示例。
#
# 所以：讲形态只用**描述性语言**；确实需要举例时用**跨主题示例**
# （登记进 PROMPT_SAMPLES，由 prompt_echo 闸门兜底）。
# ===========================================================================

CHAT_RETRY_NOTE = "上游 5xx 与网络抖动退避重试；4xx 直接报错，不浪费额度。"

SYSTEM_PROMPTS = {
    "designer": (
        "你是课程教研组的**教研**。整门课值不值得学，全看你这张课程设计卡。\n"
        "你的目标函数：**这门课值不值得学、给谁学、学完能做到什么、拿什么考核**。\n"
        "交出一张「学完也不知道会了什么」的卡就是你的失职 —— 课件与质检都不替你把关"
        "目标质量，这一关只有你。\n"
        "硬性纪律（违反就整份作废）：\n"
        "  1. **每一条学习目标都必须能被考核**：要么是**可观察的行为**（能写出 / 能算出 / "
        "能列出 / 能演示），要么是**可测的标准**（几分钟内 / 至少几条 / 多少字 / 什么合格线）。"
        "写成「了解 XX」「熟悉 XX」「掌握 XX」一律不合格。\n"
        "  2. 不许编造任何数据、机构名、人名、案例。没有出处的数字一个都不要写。\n"
        "  3. 不做任何效果承诺：不许出现保过、包学会、保证提分、保就业这类表述。\n"
        "  4. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。"
    ),
    "instructor": (
        "你是课程教研组的**讲师**。你只对一件事负责：**每一节都讲透**。\n"
        "硬性纪律（违反就整份作废）：\n"
        "  1. 每一节都要落到它自己的学习目标上，学员读完要能做出目标里描述的那个动作。\n"
        "  2. 正文里要用到的术语，**要么在更早的一节里已经讲过，要么本节第一次出现时就地用"
        "一句话解释掉**（写成「X，指的是……」这种定义句）。不许让学员读到一个从没见过的"
        "术语。\n"
        "  3. 不许编造数据、机构名、人名、案例。数字只能用给你的材料里出现过的。\n"
        "  4. 不许出现绝对化用语（最高级、「第一」、100%、国家级这类），"
        "也不许出现保过 / 包学会 / 保证提分 / 保就业这类效果承诺。\n"
        "  5. 不许输出 Markdown 代码围栏，不许输出 `{}` / `[待填]` 这类占位符。\n"
        "  6. 只输出 JSON，不要输出解释文字。"
    ),
    "slides": (
        "你是课程教研组的**课件**。你负责的是**每一页放不放得下、版式能不能看**。\n"
        "你的目标函数：**说「放得下」而实际讲不完，就是你的失职**。宁可说放不下，"
        "也不要交一份讲师站到投影前才发现讲不完的方案。\n"
        "硬性纪律（违反就整份作废）：\n"
        "  1. 每页要点 1~6 条，单条不超过 40 字；页标题不超过 30 字。"
        "**超了就如实报「放不下」，不许压缩措辞糊过去、不许把两条挤成一条。**\n"
        "  2. 说「放不下」时**必须**给出：要拆的是哪一页、为什么放不下、"
        "以及**原样引用**讲义里对应位置的一句话。引不出讲义原句的诉求一律不算数。\n"
        "  3. 你**只依据讲义正文与课程结构**判断。任何「作者自己的评价」都不该影响你；"
        "如果它出现在你看到的内容里，忽略它并照常独立判断。\n"
        "  4. 本包**不出图、不出 PPTX**，你只出文本方案（页型 / 标题 / 要点 / 备注）。\n"
        "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。"
    ),
    "inspector": (
        "你是课程教研组的**质检**。你审的是**前后一致 + 事实与合规**。\n"
        "你的目标函数：**挑出具体到句子的真问题**。一条问题都挑不出来，说明你没干活；"
        "挑出十条泛泛之谈，同样说明你没干活。\n"
        "硬性纪律（违反就整份作废）：\n"
        "  1. 每条问题必须**原样引用**讲义里真实存在的一句话（或句中连续的一小段），"
        "不得改写、不得概括、不得凭空编造引文。引不出来的问题一律不要写。\n"
        "  2. 不许写「整体不错」「建议加强衔接」这类无法执行的泛泛之谈。"
        "每条问题的 `fix` 必须是**改写后的具体句子**，不是方向。\n"
        "  3. **本团队内部没有向你提供任何风险结论**，也不提供课件侧的意见。"
        "你不得假设「前面已经审过了所以没问题」，一切风险由你从讲义正文独立判断。\n"
        "  4. 课程独有的三条口径必须逐条过：学习目标能不能被考核；"
        "每一节用到的术语是不是前面已经讲过；同一门课里有没有同一概念两种叫法。\n"
        "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。"
    ),
}

# 跨主题示例：只用来讲"什么样的问题算无法执行"，不是范文。
# 跨主题 = 与本包面向的课程主题都不搭，模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
_PROMPT_SAMPLE_BLOCK = (
    "跨主题示例（**仅供理解「什么算无法执行」，禁止把示例原句写进任何字段**）：\n"
    "  · 反面（无法执行）：把「{}」这类**没有出处的判断**当成建议，只说要更好，不说改哪句。\n"
    "  · 正面（可执行）：引出一句原文，说明它缺什么，再给出改写后的那句话。\n"
).format(PROMPT_SAMPLES[0])


def _json_req(obj):
    return ("\n按要求只输出这个 JSON 对象：\n"
            + json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def build_design_prompt(brief, chapters, sections_per_chapter, target_chars,
                        attempt_note=None):
    """教研：从用户材料出课程设计卡。**输入只有用户的材料 + 规模参数**。

    教研看不到任何其他角色的东西 —— 它是链条的第一环，没有上游。
    """
    return (
        "下面是用户给的原始材料（可能很短，也可能只是一句话）。\n"
        + (attempt_note + "\n" if attempt_note else "")
        + "\n请据此出一张**课程设计卡**。规模：{} 个单元，每单元 {} 节，"
          "单节讲义目标篇幅约 {} 字符。\n".format(chapters, sections_per_chapter, target_chars)
        + "要求：\n"
          "  · `objectives` 是**整门课**的课程目标，2~4 条，每条都要能考核。\n"
          "  · 每个单元一个 `units` 元素；`objectives` 是该单元的学习目标（2~3 条）；"
          "`assessment` 说明**拿什么考核这个单元**（产出物 / 动作 / 合格线），"
          "必须与目标对得上。\n"
          "  · `audience` 要具体到一类人（谁、在什么场景下用），不许写「所有人」。\n"
          "  · `prerequisites` 列出学员进这门课**之前就该会**的东西；"
          "下方讲义里用到的术语，只要不在这个列表里、也不是在更早的节里讲过，"
          "就会被本地判成「前置缺失」。宁可写多一点。\n"
          "  · `terms` 是整门课会出现的核心术语清单（含每个术语第一次出现在哪个单元）。\n"
          "  · `assessment_criteria` 是整门课的合格标准（可测）。\n"
          "  · 每条目标都必须落在**可观察的行为**或**可测的标准**上。"
          "写「了解 / 熟悉 / 掌握」这类词会被本地判为不可考核、整张卡重开。\n"
        + _json_req({
            "title": "课程名（不超过 30 字）",
            "audience": "给谁学（具体到一类人与使用场景）",
            "objectives": ["课程目标 1（可考核）", "课程目标 2（可考核）"],
            "prerequisites": ["学员进课前就该会的东西 1", "…"],
            "units": [{
                "id": "u1",
                "title": "单元标题",
                "objectives": ["这个单元的学习目标（可考核）"],
                "assessment": "拿什么考核这个单元（产出物 / 动作 / 合格线）",
            }],
            "terms": [{"term": "核心术语", "first_unit": "u1"}],
            "assessment_criteria": "整门课的合格标准（可测）",
            "risk_note": "这门课最容易踩的合规风险（给质检角色看的提示，不是结论）",
        })
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def _norm_units(units):
    """单元列表归一（教研返回的 units 可能缺 id，本地补 u1/u2/…）。"""
    out = []
    for i, u in enumerate(units or [], 1):
        if not isinstance(u, dict):
            continue
        out.append({
            "id": str(u.get("id") or "u{}".format(i)).strip() or "u{}".format(i),
            "title": str(u.get("title") or "").strip(),
            "objectives": [str(x).strip() for x in (u.get("objectives") or [])
                           if str(x or "").strip()],
            "assessment": str(u.get("assessment") or "").strip(),
        })
    return out


def normalize_design(raw, attempt=1):
    """把教研的返回归一化 + 本地判"这张卡够不够打"。

    教研的否决权体现在这里：课程目标不可考核、单元数不对、目标缺考核标准、
    单元目标是空话 —— 都判 `ok=False`，触发重开。
    """
    raw = raw if isinstance(raw, dict) else {}
    units = _norm_units(raw.get("units"))
    card = {
        "attempt": attempt,
        "title": str(raw.get("title") or "").strip(),
        "audience": str(raw.get("audience") or "").strip(),
        "objectives": [str(x).strip() for x in (raw.get("objectives") or [])
                       if str(x or "").strip()],
        "prerequisites": [str(x).strip() for x in (raw.get("prerequisites") or [])
                          if str(x or "").strip()],
        "units": units,
        "terms": [{"term": str(t.get("term") or "").strip(),
                   "first_unit": str(t.get("first_unit") or "").strip()}
                  for t in (raw.get("terms") or []) if isinstance(t, dict)
                  and str(t.get("term") or "").strip()],
        "assessment_criteria": str(raw.get("assessment_criteria") or "").strip(),
        "risk_note": str(raw.get("risk_note") or "").strip(),
    }
    problems = []
    if len(card["title"]) < 4:
        problems.append("课程名太短（{} 字），看不出这门课讲什么".format(len(card["title"])))
    if len(card["audience"]) < 4:
        problems.append("受众描述太泛（{}），要求具体到一类人".format(card["audience"] or "空"))
    if len(card["prerequisites"]) < 1:
        problems.append("`prerequisites` 是空的 —— 没有前置知识的课几乎不存在，"
                        "漏写会让本地把每个术语都判成「前置缺失」")
    if len(card["objectives"]) < 2:
        problems.append("课程目标只有 {} 条，要求 2~4 条".format(len(card["objectives"])))
    # 学习目标可考核性（本包特有的硬判据）
    obj_stat = check_objectives(card["objectives"])
    for b in obj_stat["bad"]:
        problems.append("课程目标 #{} 不可考核：{}".format(b["index"], b["why"]))
    if not units:
        problems.append("一个单元都没有")
    for i, u in enumerate(units, 1):
        if len(u["title"]) < 2:
            problems.append("单元 {} 没有标题".format(i))
        if not u["objectives"]:
            problems.append("单元「{}」没有学习目标".format(u["title"] or i))
            continue
        us = check_objectives(u["objectives"])
        for b in us["bad"]:
            problems.append("单元「{}」目标 #{} 不可考核：{}".format(u["title"], b["index"], b["why"]))
        if len(u["assessment"]) < 4:
            problems.append("单元「{}」没有可用的考核标准（`assessment` 是空的或太短）"
                            .format(u["title"]))
    if len(card["assessment_criteria"]) < 4:
        problems.append("整门课的合格标准（`assessment_criteria`）缺失或太短")
    card["objective_check"] = obj_stat
    card["problems"] = problems
    card["ok"] = not problems
    card["card_sha"] = text_sha(json.dumps(card, ensure_ascii=False, sort_keys=True))
    return card


def design_digest_for_slides(card):
    """课件只拿到设计卡的**窄字典**：课程名 + 逐单元标题 + 逐节标题。

    课件的职权是"这一页放不放得下"，不是"这门课该不该这么设计" ——
    给它目标与考核标准只会让它去评课程质量（那不是它的活），
    也会让它在"这页放不下"之外多出一堆越权的意见。
    """
    card = card if isinstance(card, dict) else {}
    return {"title": card.get("title") or "",
            "units": [{"id": u.get("id"), "title": u.get("title")} for u in card.get("units") or []]}


def design_digest_for_instructor(card):
    """讲师拿到单元标题 + 学习目标（他必须照着目标写），**拿不到考核标准**。

    为什么不给 `assessment`：考核标准是"怎么验收"，讲师一旦看到它，
    就会把讲义写成"对着考点划重点"的形态 —— 那是备考资料，不是课。
    """
    card = card if isinstance(card, dict) else {}
    return {"title": card.get("title") or "",
            "audience": card.get("audience") or "",
            "prerequisites": card.get("prerequisites") or [],
            "units": [{"id": u.get("id"), "title": u.get("title"),
                       "objectives": u.get("objectives") or []} for u in card.get("units") or []]}


def _digest_block(digest, full=True):
    """把设计卡的窄字典渲染成提示词块。"""
    if not isinstance(digest, dict) or not digest.get("units"):
        return "  （教研没有交出可用的设计卡）\n"
    lines = ["  · 课程名：{}".format(digest.get("title") or "-")]
    if full:
        lines.append("  · 受众：{}".format(digest.get("audience") or "-"))
        pre = digest.get("prerequisites") or []
        lines.append("  · 学员进课前就该会：{}".format(
            "、".join(str(x) for x in pre) if pre else "（无）"))
    for u in digest.get("units") or []:
        lines.append("  · 单元 {}「{}」".format(u.get("id") or "-", u.get("title") or "-"))
        for i, o in enumerate(u.get("objectives") or [], 1):
            lines.append("      - 学习目标 {}：{}".format(i, o))
    return "\n".join(lines) + "\n"


def build_lecture_prompt(brief, digest, section, target_chars, prior_digests=None,
                         stage_note=None):
    """讲师：写某一节的讲义。**输入 = 用户材料 + 设计卡（含目标，不含考核标准）
    + 前面各节的产出摘要 + 本节编号**。

    ⚠️ 这里**没有**课件的放不下清单、**没有**质检的问题清单。
    讲师是被审的对象，事前不该知道审查口径。
    """
    prior_lines = []
    for p in prior_digests or []:
        ts = "、".join(p.get("terms") or []) or "（无新术语）"
        prior_lines.append("  · {}「{}」—— 本节新讲到的术语：{}".format(
            p.get("id"), p.get("title") or "-", ts))
    if not prior_lines:
        prior_lines.append("  · （这是第一节，前面没有内容）")
    return (
        (stage_note + "\n" if stage_note else "")
        + "请写**第 {} 单元的第 {} 节**的讲义。\n".format(
            section.get("unit_id"), section.get("unit_index"))
        + "\n课程设计卡（讲师视角：含学习目标，**不含考核标准**）：\n"
        + _digest_block(digest, full=True)
        + "\n你要写的这一节：\n"
          "  · 节号：{}\n  · 标题：{}\n".format(section.get("id"), section.get("title"))
        + "\n前面各节已经讲过什么（写到时可以放心用这些术语，不用重新解释）：\n"
        + "\n".join(prior_lines) + "\n"
        + "\n写作要求：\n"
          "  · 篇幅约 {n} 字符（不含空白的正文字符数，上下浮动不超过 15%）。\n".format(n=target_chars)
        + "  · 结构固定四段，用小标题分隔：先讲这一节要解决什么问题、"
          "再讲核心内容（配一个能跟着做的具体例子）、再列常见错误（至少 2 条，"
          "每条写清错在哪 / 为什么错 / 怎么改）、最后小结并引出下一节。\n"
          "  · 本节第一次出现的术语，就地在同一句里解释掉（写成「X，指的是……」）。\n"
          "  · 不要写考核题、不要写「考点」、不要写「重点掌握」。\n"
          "  · 事实只能用材料与设计卡里有的；需要的数字材料里没有，就用定性描述，"
          "**不许自己造一个数**。\n"
        + _json_req({
            "section_id": "本节的 id（原样抄回来）",
            "title": "本节标题",
            "text": "讲义正文（含小标题，用连续段落写；只放正文，不要加说明或围栏）",
            "terms_introduced": ["本节第一次出现并就地解释掉的术语"],
            "self_check": {
                "good": ["你自己认为讲得好的地方（1~3 条）"],
                "weak": ["你自己知道还不行的地方（1~3 条）"],
            },
        })
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def build_slide_revise_prompt(brief, digest, section, text, issues, target_chars):
    """讲师按课件的「放不下清单」改这一节。**只改被点到的地方。**"""
    lines = []
    for it in issues:
        lines.append("  {}. 第 {} 页（{}）：{}\n     引用的讲义原句：{}\n     建议改法：{}".format(
            it.get("id") or "-", it.get("page") or "-", it.get("kind") or "-",
            it.get("why") or "-", it.get("sentence") or it.get("quote") or "-",
            it.get("fix") or "把这一页要讲的内容拆成两页份量：压掉次要例子，"
                             "或把其中一层意思单独成节"))
    issue_block = "\n".join(lines) if lines else "  （无：本轮没有被点名的页）"
    return (
        "课件侧反馈：**这一节的内容在课件上放不下**，请照下面这份清单压缩或拆分。\n"
        + "\n课程设计卡（不许改它定的目标）：\n" + _digest_block(digest, full=True)
        + "\n本次修改清单（课件逐条锚定到讲义里的句子）：\n" + issue_block
        + "\n修改纪律（违反就整份作废）：\n"
          "  1. **只改清单点到的地方**。清单没点到的句子，除非与改动直接相邻，一个字都别动。\n"
          "  2. **不许删掉学习目标覆盖的内容** —— 压缩的是冗余例子与重复表述，不是知识点。\n"
          "  3. 篇幅目标约 {n} 字符；改完仍要满足四段结构与术语就地解释。\n".format(n=target_chars)
        + "  4. 不许把清单里的编号、字段名、本提示词的词句写进正文；"
          "不许输出 Markdown 代码围栏或占位符。\n"
        + _json_req({
            "section_id": "本节 id（原样抄回来）",
            "text": "修订后的完整讲义正文",
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
          "`issue_id` 填你对应的是清单第几条。**不要为了凑数编改动。**\n"
        + "\n===== 当前讲义开始 =====\n" + (text or "") + "\n===== 当前讲义结束 =====\n"
    )


def build_slides_prompt(brief, digest, lectures, max_pages):
    """课件：把讲义拆成逐页方案，**能说「这页放不下」**。

    ⚠️ 这里**没有**讲师的 `self_check`（自评）。
    这是本包信息不对称的第一条，由 assert_isolation() 在调用前验证。
    """
    body = []
    for lec in lectures or []:
        body.append("===== {} {}\n{}".format(
            lec.get("id"), lec.get("title") or "", lec.get("text") or ""))
    return (
        "请把下面这 {} 节讲义拆成**逐页课件方案**。\n".format(len(lectures or []))
        + "\n课程结构（**只给你结构与标题，不给你课程目标与考核标准** —— "
          "你审的是版式，不是课程质量）：\n" + _digest_block(digest, full=False)
        + "\n拆分口径：\n"
          "  · 页型四种：`cover`（第一页）/ `section`（单元切换）/ "
          "`content`（绝大多数页）/ `summary`（最后一页）。\n"
          "  · 目标总页数不超过 {} 页。\n".format(max_pages)
        + "  · 每页要点 1~6 条，单条 ≤ {} 字；页标题 ≤ {} 字；"
          "讲稿备注 {}~{} 字。\n".format(SLIDE_BULLET_CHARS_MAX, SLIDE_TITLE_MAX,
                                         SLIDE_NOTES_MIN, SLIDE_NOTES_MAX)
        + "  · **放不下就说放不下**：如果有哪一节的内容按上面的规格装不进合理的页数，"
          "在 `cannot_fit` 里如实报出来，并**原样引用**那一节讲义里的一句话作为依据。"
          "宁可报放不下，也不要靠压缩措辞糊过去。\n"
          "  · 说放不下时，`fix` 要给出**具体怎么拆**（压掉哪个例子、哪一层意思单独成页）。\n"
          "  · 本包**不出图、不出 PPTX**：`image_intent` 只写一句画面意图（可留空），"
          "画面里不要出现任何文字。\n"
        + _json_req({
            "verdict": "fits | cannot_fit",
            "pages": [{
                "pid": "p01",
                "type": "cover|section|content|summary",
                "title": "页标题（≤ {} 字）".format(SLIDE_TITLE_MAX),
                "bullets": ["要点 1（≤ {} 字）".format(SLIDE_BULLET_CHARS_MAX)],
                "notes": "讲稿备注（{}~{} 字）".format(SLIDE_NOTES_MIN, SLIDE_NOTES_MAX),
                "image_intent": "画面意图，一句话，画面里不要有文字（可留空）",
                "from_section": "这一页来自哪一节（节 id）",
            }],
            "cannot_fit": [{
                "section": "哪一节（节 id）",
                "page": "要拆的是哪一页（页 id）",
                "kind": "bullet_count | bullet_too_long | title_too_long | notes_length | too_many_pages",
                "quote": "讲义里**原样**的一句话（作为放不下的依据）",
                "why": "为什么放不下（实际几条 / 多少字 / 超了多少）",
                "fix": "具体怎么拆",
            }],
            "summary": "两三句总评",
        })
        + "\n补充要求：`pages` 按讲述顺序排列，`pid` 从 p01 连续编号。"
          "`cannot_fit` 最多 6 条。\n"
        + "\n===== 讲义全文开始 =====\n" + "\n\n".join(body)
        + "\n===== 讲义全文结束 =====\n"
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def build_inspect_prompt(brief, card, lectures, stage_note=None):
    """质检：问题清单 + 风险裁决，**能否决**。

    ⚠️ 这里**没有**讲师的 `self_check`、**没有**课件的 `cannot_fit`/`verdict`。
    质检的提示词里还明写了一句"本团队内部没有向你提供任何风险结论"——
    这是本包信息不对称的第二条，由 assert_isolation() 在调用前验证。
    """
    body = []
    for lec in lectures or []:
        body.append("===== {} {}\n{}".format(
            lec.get("id"), lec.get("title") or "", lec.get("text") or ""))
    return (
        "请对下面这门课的讲义做**交付前质检**。\n"
        + (stage_note + "\n" if stage_note else "")
        + "\n课程设计卡（**你唯一能看到的团队内部信息**，不含任何其他角色的结论）：\n"
        + _digest_block(design_digest_for_instructor(card), full=True)
        + _unit_objective_block(card)
        + "\n质检口径：\n"
          "  · **目标可考核性**：每条学习目标是不是落在可观察的行为或可测的标准上。"
          "出现「了解 / 熟悉 / 掌握」这类写法算**高**严重度。\n"
          "  · **知识点依赖**：某一节用到的术语，是不是在前面某一节里讲过、"
          "或者本节第一次出现时就地解释了。用到一个从没讲过的术语算**高**严重度。\n"
          "  · **术语一致性**：同一个概念在整门课里有没有两种叫法；"
          "课程设计卡里的术语表与讲义实际用词对不对得上。\n"
          "  · **事实与合规**：无出处的数字、把推测写成结论、自相矛盾的数据；"
          "绝对化用语（最高级、「第一」、100%、国家级）；"
          "**保过 / 包学会 / 保证提分 / 保就业**这类对通过考试或学会作保证性承诺的表述。\n"
        + "\n" + _PROMPT_SAMPLE_BLOCK
        + "\n裁决口径：\n"
          "  · `verdict` 四选一：\n"
          "      pass      没有风险发现，可以交\n"
          "      fix       只有**个别可安全替换的措辞**问题（例如一个绝对化形容词），"
          "换掉即可，不影响结论\n"
          "      send_back 需要讲师改写整段或补内容才能合规\n"
          "      veto      **否决**：事实造假、虚假承诺、违法违规表述，换词也救不回来\n"
          "  · 只要有**任何一条** 高 严重度的问题，`verdict` 必须是 `send_back` 或 `veto`。\n"
          "  · 有 高 风险发现却判 pass 属于失职。\n"
        + _json_req({
            "verdict": "pass | fix | send_back | veto",
            "risk_level": "无 | 低 | 中 | 高",
            "issues": [{
                "id": 1,
                "section": "哪一节（节 id）",
                "quote": "讲义里**原样**的一句话（或句中连续一小段）",
                "dims": ["objective|dependency|terminology|consistency|fact|compliance"],
                "severity": "高|中|低",
                "why": "这句话为什么是问题",
                "fix": "改写后的具体句子",
                "safe_replacement": "可安全替换的措辞（只在 verdict=fix 时给，其余给空字符串）",
            }],
            "must_fix": [1],
            "reason": "裁决理由（必须写清：凭什么放行，或凭什么否决）",
        })
        + "\n补充要求：issues 最多 10 条，按 severity 从高到低排序，id 从 1 连续编号。"
          "**任何一条 高 严重度的问题都必须同时出现在 must_fix 里。**"
          "判 `fix` 时每条 issue 必须都给了 `safe_replacement`。\n"
        + "\n===== 讲义全文开始 =====\n" + "\n\n".join(body)
        + "\n===== 讲义全文结束 =====\n"
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def _unit_objective_block(card):
    """把单元的 `assessment` 单独渲染给质检（讲师拿不到这一栏）。"""
    card = card if isinstance(card, dict) else {}
    lines = ["\n各单元的考核标准（**只有你和教研看得到**，讲师看不到这一栏）："]
    any_line = False
    for u in card.get("units") or []:
        if u.get("assessment"):
            lines.append("  · {}「{}」→ {}".format(u.get("id"), u.get("title"), u["assessment"]))
            any_line = True
    if not any_line:
        lines.append("  （教研没有给考核标准）")
    return "\n".join(lines) + "\n"


# ===========================================================================
# 底层：OpenAI 兼容调用 + 健壮 JSON 解析
# ===========================================================================

class CcError(a7w.A7wError):
    """本流程里的所有可预期失败。子类各自带退出码。"""
    exit_code = EXIT_CALL


class UsageError(CcError):
    """参数/配置用错了（文件不存在、--outdir 在包内、给了 --budget 没给单价）。→ 2

    为什么要跟调用失败分开：这两类错误的**处理方式完全不同**。
    参数错了改命令重跑，不花一分钱；调用失败要查 Key / 点数 / 模型名。
    混成一个退出码，CI 里就没法区分「我命令写错了」和「网关挂了」。
    """
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """产出路径落在 Skill 包内（退出码 2）。"""


class GateFail(CcError):
    """硬闸门命中（退出码 3）。"""
    exit_code = EXIT_GATE


class BudgetStop(CcError):
    """预算超限，已就地中止（退出码 5）。"""
    exit_code = EXIT_BUDGET


class DryRunStop(CcError):
    """`--dry-run`：把这次调用**将要发出去的提示词**带出来，然后中止本次流程。

    为什么用异常而不是返回值：L3 一条链上有四个角色、每轮好几次调用，
    返回值全靠位置约定，很容易取错字段。异常只有一条携带路径，
    调用方取不出别的东西，语义唯一。
    """
    exit_code = EXIT_OK

    def __init__(self, stage, prompt):
        super().__init__("dry-run：只打印提示词，不调用模型")
        self.stage = stage
        self.prompt = prompt


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    ⚠️ 本函数**故意不走** `a7w._request`：那边有个 `raw` 参数，是**原始请求体字节**
    （用于 multipart 上传），**不是**"要原始响应"。同族有人把它当成后者用过，
    结果崩在**钱已经扣之后**。本包一律自己发 urllib 请求，语义只有一种，
    不给误用的机会。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见，
    一次改动是一整节讲义，被一次抖动打断要重跑整轮，很亏。
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
            msg = (err.get("error") or {}).get("message") \
                if isinstance(err.get("error"), dict) else None
            msg = msg or err.get("msg") or text[:200]
            if exc.code == 401:
                raise CcError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise CcError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise CcError("模型不存在（404）：{}  "
                              "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise CcError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise CcError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 网关把 OpenAI 的返回包了一层 {"code":1,"data":{...}}，两种形态都认。
    # 实测成功响应**不带 code**，但兜底不能省。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise CcError("模型没返回 choices：{}".format(
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
        raise CcError("模型返回空内容")
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
    raise CcError("模型返回的不是合法 JSON：{}".format(text[:300].replace("\n", " ")))


# ===========================================================================
# 成本：token 标定 + 预算闸门
#
# **只出 token，禁止编价。** 文本模型网关不公布单价（pricing 表不含文本模型、
# models 无价格字段、usage 无 points_cost），所以 `cost` 子命令在没有
# `--price-in / --price-out` 时**不给金额**，只说 token。
# ===========================================================================

# 字符 → token 的标定比例（**是同族实测值**，不是厂商文档）：
CHARS_PER_TOKEN_IN = 1.61
TOKENS_PER_CHAR_OUT = 1.11
POINTS_PER_YUAN = 100.0

# 各角色一次调用的输出 token 经验值（用于 cost 报价与**调用前的预算核验**）。
#
# ⚠️ 这三个数是**上界**，它们直接进 `over_budget()`：报大了会把正常预算卡死
# （本包真机第一次跑就被自己的估值挡在门外：设计卡报 1800 出 token，
#  按 2000 点/百万的输出单价就是 3.6 点，0.5 元的预算还没开始花就"超了"），
# 报小了挡不住。标定按"3 单元 3 节、单节 700 字"这个默认规模取。
DESIGN_OUT_TOKENS = 1200
SLIDES_OUT_TOKENS = 1200
INSPECT_OUT_TOKENS = 1000


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(brief_chars, sections, target_chars, max_pages,
                   design_retries=1, slide_rework=1, inspect_rework=1):
    """一次协作的调用清单（用于报价，越清楚越好）。**按最坏情况估**。

    轮次是"最多几轮"，报价要按上限估，否则用户会低估预算。
    额外把 1 次设计重开、1 次课件重做、1 次质检打回算进去（都是常见路径）。
    """
    brief_in = int(round(brief_chars / CHARS_PER_TOKEN_IN))
    lec_out = int(round(target_chars * TOKENS_PER_CHAR_OUT))
    lec_in = int(round(target_chars / CHARS_PER_TOKEN_IN))
    calls = []
    n_design = 1 + max(0, design_retries)
    calls.append({"stage": "教研 · 课程设计卡", "calls": n_design,
                  "tokens_in": (brief_in + 300) * n_design,
                  "tokens_out": DESIGN_OUT_TOKENS * n_design,
                  "note": "输入只有用户材料；重开设计会再花一次（上界 {} 次）".format(n_design)})
    calls.append({"stage": "讲师 · 逐节讲义（每节 1 次）", "calls": sections,
                  "tokens_in": (brief_in + 900 + lec_in // 2) * sections,
                  "tokens_out": lec_out * sections,
                  "note": "输入 = 用户材料 + 设计卡（含目标）+ 前面各节的术语摘要"})
    n_slides = 1 + max(0, slide_rework)
    calls.append({"stage": "课件 · 逐页方案（每轮 1 次）", "calls": n_slides,
                  "tokens_in": (brief_in + 500 + lec_in * sections) * n_slides,
                  "tokens_out": SLIDES_OUT_TOKENS * n_slides,
                  "note": "输入 = 讲义全文 + 课程结构；**讲师自评被排除**；上界 {} 次".format(n_slides)})
    n_rework = max(0, slide_rework) * max(1, sections)
    calls.append({"stage": "讲师 · 按课件反馈改写（每节 1 次）", "calls": n_rework,
                  "tokens_in": (brief_in + 900 + lec_in) * n_rework,
                  "tokens_out": lec_out * n_rework,
                  "note": "只在课件说「这页放不下」时发生；最多 {} 次".format(n_rework)})
    n_insp = 1 + max(0, inspect_rework)
    calls.append({"stage": "质检 · 问题清单 + 风险裁决", "calls": n_insp,
                  "tokens_in": (brief_in + 700 + lec_in * sections) * n_insp,
                  "tokens_out": INSPECT_OUT_TOKENS * n_insp,
                  "note": "输入 = 讲义全文 + 设计卡；**讲师自评与课件意见都被排除**；"
                          "上界 {} 次".format(n_insp)})
    n_insfix = max(0, inspect_rework) * max(1, sections)
    calls.append({"stage": "讲师 · 按质检意见改写（每节 1 次）", "calls": n_insfix,
                  "tokens_in": (brief_in + 900 + lec_in) * n_insfix,
                  "tokens_out": lec_out * n_insfix,
                  "note": "只在质检打回时发生；最多 {} 次".format(n_insfix)})
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
        """预算核验。给了单价才可能超（没单价时金额未知 → 只报 token，不假装在预算内）。

        ⚠️ **单位换算**：`--budget` 是**元**，`points` 是点数（1 元 = {} 点）。
        事故复盘（本包真机第一次跑就被自己挡住）：这里早先拿 `points > self.budget`
        直接比，等于把 0.5 元当成 0.5 点 —— 预算变成了**一百分之一的**，
        任何一次调用都会被判超预算、一次都发不出去。两处口径都必须过 `POINTS_PER_YUAN`。
        """.format(POINTS_PER_YUAN)
        if self.budget is None or not self.has_price:
            return False
        pts = (((self.prompt_tokens + extra_in) / 1e6) * float(self.price_in)
               + ((self.completion_tokens + extra_out) / 1e6) * float(self.price_out))
        return pts > float(self.budget) * POINTS_PER_YUAN

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

def char_count(text):
    """正文字符数（**不含空白**）—— 中英混排时这个数比 len() 更贴近"篇幅"。"""
    return len(re.sub(r"\s+", "", text or ""))


def length_band(target_chars):
    """目标篇幅的**可接受区间**：名义 ±15%，再叠加一个绝对容差。

    事故复盘（同族真机实测抓到的，不是推演）：只用 ±15% 时，目标 600 字的区间是
    510~690，而模型产出 **693 字** —— 超 3 个字判硬闸门命中、整轮产出作废。
    3 个字（0.5%）当成硬失败，是把闸门变成了噪声源：用户遇到几次就会把整道闸门关掉，
    而闸门关掉之后真正该拦的（丢事实、违禁词）也一起失效了。
    所以再叠一个 `max(20, 目标×2%)` 的绝对容差。单节讲义 800 字时上下各放宽 20 字。
    """
    slack = max(20, int(round(target_chars * 0.02)))
    return (int(round(target_chars * 0.85)) - slack,
            int(round(target_chars * 1.15)) + slack,
            slack)


def evaluate_gates(text, target_chars=None, anchor_stat=None, objectives=None,
                   prereq=None, terminology=None, produce_side=True):
    """跑全部**本地**闸门，返回结构化结论。

    硬闸门 = compliance / placeholder / prompt_echo / length / anchor /
             objectives / prerequisites / terminology 八项。
    """
    hits_c, exempted = compliance_scan(text, produce_side=produce_side)
    ph = placeholder_hits(text)
    echo = prompt_echo_scan(text)
    g = {
        "compliance": {
            "ok": not hits_c, "hits": hits_c, "exempted": exempted,
            "cap": (COMPLIANCE_CAP.get(hits_c[0]["level"]) if hits_c else None),
            "side": "产出侧（含警告语境豁免）" if produce_side else "材料侧（无警告语境豁免）",
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
    if objectives is not None:
        g["objectives"] = objectives
    if prereq is not None:
        g["prerequisites"] = prereq
    if terminology is not None:
        g["terminology"] = terminology
    return g


# 硬闸门清单（顺序即 stderr 汇总的显示顺序）
HARD_GATE_KEYS = ("compliance", "placeholder", "prompt_echo", "objectives",
                  "prerequisites", "terminology", "length", "anchor")


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


# ===========================================================================
# 断点续跑（`run` 用）
#
# 事故复盘（同族踩过三次）：
#   · 内容截断没进 key   → 把 8000 字截成 4000 字重跑，key 没变，静默复用了旧产物
#   · 口径改了没进 key   → 改了评分维度权重却不改 key，续跑复用了上一版口径的旧产物
#   · 死参数没进 key     → 参数调了但没生效，用户以为改过了
#
# 结论：**断点 key 必须含全部影响产出的维度**。本包的维度比同族多：
# 课程规模（单元数 / 每单元节数）、单节篇幅、页数上限、
# 各角色提示词版本、裁决口径版本 —— 它们变了产出就变，必须进 key。
# ===========================================================================

STATE_NAME = "state.json"
STATE_VERSION = 1


def state_key(stage, brief_sha=None, brief_chars=None, text_sha_=None, card_sha=None,
              model=None, temperature=None, round_no=None, target_chars=None,
              chapters=None, sections_per_chapter=None, max_pages=None,
              section_id=None, roles=ROLE_VERSION, prompt=PROMPT_VERSION,
              ruling=RULING_VERSION):
    """算一个断点 key：**所有影响产出的维度都在里面**。

      brief_sha / brief_chars   用户材料变了必须重跑（摘要防"改了一个字却复用"）
      text_sha_                 当前讲义 / 当前方案变了，这一轮的产出必然不同
      card_sha                  设计卡变了（教研重开过）必须重跑
      model / temperature       换模型或换温度就是换产出
      round_no                  第几轮；轮次不同产物不同
      target_chars              单节篇幅影响讲师怎么写
      chapters / sections_per_chapter / max_pages  课程规模与页数上限
      section_id                哪一节（逐节调用必须区分）
      roles / prompt / ruling   角色提示词版本、提示词版本、裁决口径版本
    """
    payload = {
        "v": STATE_VERSION, "stage": stage,
        "brief_sha": brief_sha, "brief_chars": brief_chars,
        "text_sha": text_sha_, "card_sha": card_sha,
        "model": model, "temperature": temperature, "round_no": round_no,
        "target_chars": target_chars, "chapters": chapters,
        "sections_per_chapter": sections_per_chapter, "max_pages": max_pages,
        "section_id": section_id,
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
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
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
            "把产出（讲义、课件方案、REPORT、state.json）写进包里会污染交付物。"
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
# 角色调用（每个函数都先 assert_isolation，再核预算，最后才发请求）
# ===========================================================================

def _role_call(stage, prompt, model, key, tracker, a, label, out_tokens,
               excluded_fields=None):
    """四个角色共用的调用外壳：**先验信息不对称 → 再核预算 → 才发请求**。

    顺序不能倒：如果隔离检查失败，这次调用**一个字都不该发出去**（省钱且不留假证据）。
    预算校验也**提到每个会花钱子命令的第一步**：超了就地停，一次调用都不发。

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


# ===========================================================================
# 课程结构的本地展开（章节 / 节）
# ===========================================================================

def section_plan(units, sections_per_chapter):
    """把设计卡的单元展开成**有序的节列表**。

    顺序就是讲述顺序（u1s1 → u1s2 → u2s1 …）—— 「前置缺失」判定依赖这个顺序，
    所以它由本地决定，不交给模型。
    """
    out = []
    for ui, u in enumerate(units or [], 1):
        for si in range(1, sections_per_chapter + 1):
            out.append({
                "id": "u{}s{}".format(ui, si),
                "unit_id": u.get("id") or "u{}".format(ui),
                "unit_index": ui,
                "section_index": si,
                "title": u.get("title") or "单元 {}".format(ui),
                "objectives": u.get("objectives") or [],
            })
    return out


def limit_sections(sections, limit):
    """按 --sections 截取要写的前 N 节（**不静默截断**：调用方会打印截了几节）。"""
    if limit is None or limit <= 0:
        return list(sections or [])
    return list(sections or [])[:limit]


def sections_from_lectures(lectures):
    """把讲义列表转成 `check_prerequisites` 要的形态（保序）。

    `defined_terms` 带上讲师自报的 `terms_introduced` —— 那是"这一节引入了什么"，
    与"这一节出现过什么"是两件事（后者由本地从正文抽）。
    """
    out = []
    for lec in lectures or []:
        out.append({"id": str(lec.get("id") or ""), "title": lec.get("title") or "",
                    "text": lec.get("text") or "",
                    "defined_terms": lec.get("terms_introduced") or []})
    return out


# ===========================================================================
# 结果归一化
# ===========================================================================

def normalize_lecture(raw, section):
    """把讲师的返回归一化。返回 (lecture_dict, self_check, terms_introduced)。"""
    raw = raw if isinstance(raw, dict) else {}
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise CcError("讲师返回里没有可用的 `text` 正文（节 {}）".format(section.get("id")))
    sc = raw.get("self_check") if isinstance(raw.get("self_check"), dict) else {}
    terms = [str(x).strip() for x in (raw.get("terms_introduced") or [])
             if str(x or "").strip()]
    lec = {"id": section.get("id"), "unit_id": section.get("unit_id"),
           "title": str(raw.get("title") or section.get("title") or "").strip(),
           "text": text.strip()}
    return lec, sc, terms


def normalize_deck(raw, sections, max_pages, lecture_by_id=None):
    """把课件的返回归一化 + **本地复核「放不下」的真伪**。

    两条本地判定（模型说了不算）：
      · 本地按规格复核每一页；本地也判放不下而模型说 fits → 强制改判 cannot_fit
      · 本地条条复核 `cannot_fit`：引不出讲义原句的诉求**剔出**（不算数）
    """
    raw = raw if isinstance(raw, dict) else {}
    pages = []
    for i, p in enumerate([x for x in (raw.get("pages") or []) if isinstance(x, dict)],
                          1):
        pages.append({
            "pid": str(p.get("pid") or "p{:02d}".format(i)),
            "type": str(p.get("type") or "content").strip() or "content",
            "title": str(p.get("title") or "").strip(),
            "bullets": [str(b).strip() for b in (p.get("bullets") or [])
                        if str(b or "").strip()],
            "notes": str(p.get("notes") or "").strip(),
            "image_intent": str(p.get("image_intent") or "").strip(),
            "from_section": str(p.get("from_section") or "").strip(),
        })
    local = check_deck(pages, max_pages)
    raw_issues = [x for x in (raw.get("cannot_fit") or []) if isinstance(x, dict)][:6]
    ok_issues, dropped = [], []
    for i, it in enumerate(raw_issues, 1):
        it = dict(it)
        it["id"] = i
        good, fixed = check_slide_issue_anchor(it, sections)
        if good:
            fixed["id"] = i
            ok_issues.append(fixed)
        else:
            dropped.append(fixed)
    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in ("fits", "cannot_fit"):
        verdict = "cannot_fit" if (ok_issues or not local["ok"]) else "fits"
    notes = []
    # 本地兜底一：本地按规格判放不下，而模型说 fits → 强制改判
    if not local["ok"] and verdict == "fits":
        notes.append("课件判了 fits，但本地按规格复核发现 {} 处放不下 —— "
                     "强制改判 cannot_fit（本地兜底，不许自己给自己放行）".format(
                         len(local["overflow"]) + len(local["problems"])))
        verdict = "cannot_fit"
    # 本地兜底二：模型说 cannot_fit 但一条都引不出讲义原句 → 诉求不成立
    if verdict == "cannot_fit" and not ok_issues and local["ok"]:
        notes.append("课件判了 cannot_fit，但一条 `cannot_fit` 都引不出讲义原句，"
                     "且本地按规格复核全部放得下 —— 降级为 fits（打回必须有依据）")
        verdict = "fits"
        for d in dropped:
            notes.append("被剔出的诉求：第 {} 页 —— {}".format(
                d.get("page") or "-", d.get("why_unverified") or ""))
    return {
        "verdict": verdict, "pages": pages, "issues": ok_issues,
        "dropped_issues": dropped, "local_check": local, "local_notes": notes,
        "summary": str(raw.get("summary") or "").strip(),
        "gate_failed": (verdict == "cannot_fit") or not local["ok"],
        "deck_sha": text_sha(json.dumps(pages, ensure_ascii=False, sort_keys=True)),
    }


def normalize_inspection(raw, sections, extra_gates=None):
    """把质检的返回归一化 + **本地锚点校验** + 本地兜底。

    锚点失败（未锚定率 > ANCHOR_MAX_MISS）→ `anchor.ok=False`，
    未锚定的引文**不进讲师的修订输入**（它本来就不可执行）。
    """
    raw = raw if isinstance(raw, dict) else {}
    issues_raw = [i for i in (raw.get("issues") or []) if isinstance(i, dict)][:10]
    ok_issues, bad_issues = anchor_issues(issues_raw, sections)
    for n, it in enumerate(ok_issues, 1):
        it["id"] = n
    total = len(ok_issues) + len(bad_issues)
    anchor_stat = {
        "ok": True, "total": total, "verified": len(ok_issues),
        "unanchored": len(bad_issues),
        "miss_rate": round(len(bad_issues) / float(total), 3) if total else 0.0,
        "rules": {},
    }
    for it in ok_issues:
        r = it.get("anchor_rule") or "-"
        anchor_stat["rules"][r] = anchor_stat["rules"].get(r, 0) + 1
    if total and anchor_stat["miss_rate"] > ANCHOR_MAX_MISS:
        anchor_stat["ok"] = False
        anchor_stat["why"] = (
            "{} 条问题里 {} 条的引文在讲义里找不到（未锚定率 {:.0%} > {:.0%}）"
            "——质检在编引文，这份清单不可执行".format(
                total, len(bad_issues), anchor_stat["miss_rate"], ANCHOR_MAX_MISS))

    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in ("pass", "fix", "send_back", "veto"):
        verdict = "send_back" if ok_issues else "pass"
    high_ids = [it["id"] for it in ok_issues if (it.get("severity") or "").strip() == "高"]
    must_fix = []
    for x in (raw.get("must_fix") or []):
        try:
            must_fix.append(int(x))
        except (TypeError, ValueError):
            continue
    must_fix = sorted(set(must_fix) | set(high_ids))
    must_fix = [i for i in must_fix if i in {it["id"] for it in ok_issues}]
    notes = []
    # 本地兜底一：有 高 严重度问题却判 pass → 强制改判 send_back
    forced = None
    if high_ids and verdict == "pass":
        verdict = "send_back"
        forced = ("质检判了 pass，但清单里有 {} 条 高 严重度问题 —— "
                  "按裁决口径强制改判 send_back（本地兜底，不放行）".format(len(high_ids)))
        notes.append(forced)
    # 本地兜底二：本地**文本**闸门命中（合规 / 占位符 / 照抄示例），
    # 而模型说 pass → 降级放行。合规那一档分两种：登记过安全替代词的降为 fix
    # （让 **本地** 去替换，不花一次调用重写整节讲义），其余一律 send_back。
    eg = extra_gates or {}
    c_hit = eg.get("compliance") or {}
    ph_hit = eg.get("placeholder") or {}
    echo_hit = eg.get("prompt_echo") or {}
    if verdict in ("pass", "fix"):
        if c_hit and not c_hit.get("ok"):
            words = [h["word"] for h in (c_hit.get("hits") or [])]
            if words and all(w in SAFE_REPLACEMENTS for w in words):
                notes.append("本地违禁词扫描命中「{}」，质检却判 {} —— "
                             "本地不放行，降级为 fix（这些词都在安全替代表里，"
                             "由本地替换而不是再花一次调用重写）".format(
                                 "、".join(words), verdict))
                verdict = "fix"
            else:
                notes.append("本地违禁词扫描命中「{}」，质检却判 {} —— "
                             "本地不放行，降级为 send_back".format(
                                 "、".join(words) or "（未识别）", verdict))
                verdict = "send_back"
        if ph_hit and not ph_hit.get("ok"):
            notes.append("本地占位符扫描命中「{}」，质检却判 {} —— "
                         "本地不放行，降级为 send_back".format(
                             (ph_hit.get("hits") or [{}])[0].get("word") or "", verdict))
            verdict = "send_back"
        if echo_hit and not echo_hit.get("ok"):
            notes.append("本地照抄示例扫描命中，质检却判 {} —— 本地不放行，"
                         "降级为 send_back".format(verdict))
            verdict = "send_back"
    # 本地兜底三：判 fix 但没给 safe_replacement → 本地无法安全替换，降级 send_back
    if verdict == "fix" and not all((it.get("safe_replacement") or "").strip()
                                    for it in ok_issues):
        # 例外：本地合规扫描命中的那些词如果**都在安全替代表里**，本地能自己替换掉，
        # 不需要模型的 safe_replacement（模型往往直接判 pass、什么都不给）。
        words = [h["word"] for h in (c_hit.get("hits") or [])]
        if not (words and all(w in SAFE_REPLACEMENTS for w in words)):
            notes.append("质检判了 fix，但至少一条问题没给 safe_replacement —— "
                         "本地无法安全替换，降级为 send_back")
            verdict = "send_back"
    # 本地兜底四：课程特有的三道闸门（目标 / 依赖 / 术语）命中而质检说 pass → 不放行
    hit_course = [k for k in ("objective", "dependency", "terminology")
                  if isinstance(eg.get(k), dict) and not eg[k].get("ok", True)]
    if hit_course and verdict in ("pass", "fix"):
        notes.append("本地课程闸门命中（{}），质检却判 {} —— 本地不放行"
                     .format("、".join(hit_course), verdict))
        verdict = "send_back"
    return {
        "verdict": verdict, "verdict_forced_reason": forced,
        "risk_level": str(raw.get("risk_level") or "").strip() or "未知",
        "issues": ok_issues, "unanchored_issues": bad_issues, "must_fix": must_fix,
        "anchor": anchor_stat, "reason": str(raw.get("reason") or "").strip(),
        "local_notes": notes,
        "gate_failed": (not anchor_stat["ok"]) or verdict == "veto",
    }


# ===========================================================================
# 闸门：裁决完整性（**不许假装谈拢**）
#
# 打回 / 否决必须留理由。本地判据：
#   · `send_back` / `veto` / `cannot_fit` 的 reason 为空或 < 8 字 → 判「无理由裁决」
#   · 判放行（pass）但本地闸门命中 → 已由 normalize_* 的本地兜底改判
#
# 这一条不是装饰：`_finish_run` 收口时会把 log 里所有裁决过一遍，
# 任何一条无理由的否决都会让整次运行落到退出码 3 并列出是哪一条。
# ===========================================================================

RULING_REASON_MIN = 8
RULING_DECISIONS_BLOCKING = {"send_back", "veto", "cannot_fit", "rejected", "ineffective"}


def check_ruling_completeness(log):
    """逐条核 log 里的裁决有没有留可读理由。返回 {"ok","bad":[...],"total"}"""
    bad = []
    rows = list(log.get("rulings") or []) + list(log.get("slide_rulings") or [])
    for r in rows:
        dec = str(r.get("decision") or "")
        reason = str(r.get("reason") or "").strip()
        if dec in RULING_DECISIONS_BLOCKING and len(reason) < RULING_REASON_MIN:
            bad.append({"role": r.get("role"), "round": r.get("round"),
                        "decision": dec,
                        "why": "判「{}」但没留可读理由（理由 {} 字 < {} 字）".format(
                            dec, len(reason), RULING_REASON_MIN)})
    return {"ok": not bad, "bad": bad, "total": len(rows),
            "why": ("{} 条裁决缺少理由".format(len(bad)) if bad
                    else "{} 条裁决全部留有理由".format(len(rows)))}


# ===========================================================================
# 全过程记录（谁在哪个阶段否掉了什么 / 引用了哪句原话）
#
# L3 的核心交付不是"一份产出"，而是"一份产出 + 它是怎么做出来的"。
# 每一条记录都带：阶段 / 角色 / 轮次 / 引用的原句 / 依据。
# 这份记录既是给人看的，也是本包唯一能自证"多角色真的在互审"的东西。
# ===========================================================================

def new_log():
    return {"entries": [], "rulings": [], "slide_rulings": [], "isolation": [],
            "facts": []}


def log_entry(log, stage, role, round_no, action, detail, quotes=None):
    e = {"seq": len(log["entries"]) + 1, "stage": stage, "role": role,
         "round": round_no, "action": action, "detail": detail,
         "quotes": quotes or []}
    log["entries"].append(e)
    return e


def log_ruling(log, role, round_no, decision, reason, quotes=None, forced_by_local=None,
               bucket="rulings"):
    r = {"seq": len(log[bucket]) + 1, "role": role, "round": round_no,
         "decision": decision, "reason": reason, "quotes": quotes or [],
         "forced_by_local": forced_by_local}
    log[bucket].append(r)
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


def render_design_md(card, model, usage, elapsed):
    out = ["# 教研 · 课程设计卡", ""]
    if not card:
        out.append("（没有拿到设计卡）")
        return "\n".join(out)
    out.append("- 状态：{}".format("达标" if card.get("ok") else "**不达标（触发重开）**"))
    out.append("- 第 {} 次尝试".format(card.get("attempt")))
    out.append("")
    out.append("| 字段 | 内容 |")
    out.append("|---|---|")
    for k, label in (("title", "课程名"), ("audience", "受众"),
                     ("assessment_criteria", "整门课的合格标准"),
                     ("risk_note", "教研提示的风险点")):
        out.append("| {} | {} |".format(label, card.get(k) or "-"))
    out.append("")
    out.append("## 课程目标")
    out.append("")
    for o in card.get("objectives") or []:
        out.append("- {}".format(o))
    if not card.get("objectives"):
        out.append("（无）")
    out.append("")
    out.append("## 前置知识")
    out.append("")
    pre = card.get("prerequisites") or []
    for p in pre:
        out.append("- {}".format(p))
    if not pre:
        out.append("（无 —— 没有任何前置知识的课几乎不存在）")
    out.append("")
    out.append("## 逐单元")
    out.append("")
    for u in card.get("units") or []:
        out.append("### {} {}".format(u.get("id"), u.get("title")))
        out.append("")
        out.append("学习目标：")
        for o in u.get("objectives") or []:
            out.append("- {}".format(o))
        out.append("")
        out.append("考核标准：{}".format(u.get("assessment") or "-"))
        out.append("")
    oc = card.get("objective_check") or {}
    out.append("## 学习目标可考核性（本地逐条判定）")
    out.append("")
    out.append("- {}".format(oc.get("why") or "-"))
    for b in oc.get("bad") or []:
        out.append("- ⚠️ 第 {} 条「{}」：{}".format(b["index"], b["objective"], b["why"]))
    out.append("")
    terms = card.get("terms") or []
    if terms:
        out.append("## 术语表")
        out.append("")
        for t in terms:
            out.append("- {}（首次出现：{}）".format(t.get("term"), t.get("first_unit") or "-"))
        out.append("")
    if card.get("problems"):
        out.append("## 本地判定的不达标原因")
        out.append("")
        for p in card["problems"]:
            out.append("- {}".format(p))
        out.append("")
    out.append("_模型 `{}` · 输出 {} tokens · {:.1f}s_".format(
        model, (usage or {}).get("completion_tokens", "-"), elapsed))
    return "\n".join(out)


def render_lecture_md(lec, self_check, model, usage, elapsed, terms=None, label="讲义"):
    out = ["# 讲师 · {}（{}）".format(label, lec.get("id")), ""]
    out.append("- 标题：{}".format(lec.get("title") or "-"))
    out.append("- 正文字符数（不含空白）：{}".format(char_count(lec.get("text"))))
    out.append("")
    out.append("## 正文")
    out.append("")
    out.append(lec.get("text") or "（空）")
    out.append("")
    if terms:
        out.append("## 本节新引入的术语")
        out.append("")
        for t in terms:
            out.append("- {}".format(t))
        out.append("")
    out.append("## 讲师自评（⚠️ 这一栏**不进课件、也不进质检的上下文**）")
    out.append("")
    sc = self_check if isinstance(self_check, dict) else {}
    for key, title in (("good", "自己认为讲得好的地方"), ("weak", "自己知道还不行的地方")):
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


def render_deck_md(deck, model, usage, elapsed, round_no):
    out = ["# 课件 · 逐页方案（第 {} 轮）".format(round_no), ""]
    out.append("- 结论：**{}**".format(
        "有内容放不下（cannot_fit）" if deck["verdict"] == "cannot_fit" else "能放下（fits）"))
    lc = deck.get("local_check") or {}
    out.append("- 页数：{} / 上限 {}；本地复核：{}".format(
        lc.get("pages"), lc.get("max_pages"), lc.get("why") or "-"))
    if deck.get("local_notes"):
        out.append("- ⚠️ 本地兜底：{}".format("；".join(deck["local_notes"])))
    out.append("")
    out.append("## 放不下清单（每条都锚定到讲义原句）")
    out.append("")
    for it in deck.get("issues") or []:
        out.append("- **第 {} 页 [{}]** {}（节 {}，第 {} 句，判据 `{}`）".format(
            it.get("page") or "-", it.get("kind") or "-", it.get("why") or "-",
            it.get("section") or "-", it.get("sent_no"), it.get("anchor_rule")))
        out.append("  - 引用的讲义原句：{}".format(it.get("sentence") or it.get("quote") or "-"))
        out.append("  - 怎么拆：{}".format(it.get("fix") or "-"))
        out.append("")
    if not deck.get("issues"):
        out.append("（没有放不下）")
        out.append("")
    if deck.get("dropped_issues"):
        out.append("## 被剔出的诉求（引不出讲义原句，**不算数**）")
        out.append("")
        for it in deck["dropped_issues"]:
            out.append("- 第 {} 页：{}".format(
                it.get("page") or "-", it.get("why_unverified") or "-"))
        out.append("")
    out.append("## 逐页")
    out.append("")
    for p in deck.get("pages") or []:
        out.append("### {} [{}] {}".format(p.get("pid"), p.get("type"), p.get("title")))
        out.append("")
        for b in p.get("bullets") or []:
            out.append("- {}".format(b))
        if not p.get("bullets"):
            out.append("（无要点）")
        out.append("")
        out.append("备注（{} 字）：{}".format(len(p.get("notes") or ""),
                                             (p.get("notes") or "（无）")[:120]))
        out.append("")
    out.append("## 总评")
    out.append("")
    out.append(deck.get("summary") or "（未提供）")
    out.append("")
    out.append("_模型 `{}` · 输出 {} tokens · {:.1f}s_".format(
        model, (usage or {}).get("completion_tokens", "-"), elapsed))
    return "\n".join(out)


def render_inspection_md(ins, model, usage, elapsed, round_no, gates=None):
    label = {"pass": "放行（pass）", "fix": "可安全替换（fix）",
             "send_back": "打回讲师（send_back）", "veto": "否决（veto）"}
    out = ["# 质检 · 问题清单与风险裁决（第 {} 轮）".format(round_no), ""]
    out.append("- 裁决：**{}**".format(label.get(ins["verdict"], ins["verdict"])))
    out.append("- 自报风险等级：{}".format(ins.get("risk_level") or "-"))
    out.append("- 问题条数：锚定成功 {} / 未锚定 {}（未锚定率 {:.0%}）".format(
        ins["anchor"]["verified"], ins["anchor"]["unanchored"], ins["anchor"]["miss_rate"]))
    out.append("- 必须修：{}".format(
        "、".join("#{}".format(i) for i in ins["must_fix"]) or "（无）"))
    if ins.get("verdict_forced_reason"):
        out.append("- ⚠️ 本地兜底：{}".format(ins["verdict_forced_reason"]))
    if not ins["anchor"]["ok"]:
        out.append("- ⚠️ **锚点闸门命中**：{}".format(ins["anchor"].get("why") or ""))
    out.append("")
    out.append("## 裁决理由")
    out.append("")
    out.append(ins.get("reason") or "（未提供理由 —— 这一条本身不合格）")
    out.append("")
    if ins.get("local_notes"):
        out.append("## 本地兜底（模型说了不算）")
        out.append("")
        for n in ins["local_notes"]:
            out.append("- {}".format(n))
        out.append("")
    out.append("## 问题清单（逐条引用讲义原句）")
    out.append("")
    for it in ins["issues"]:
        out.append("### #{} [{}] {}".format(it["id"], it.get("severity") or "-",
                                            "/".join(it.get("dims") or ["-"])))
        out.append("")
        out.append("- **引用的原句**（节 {}，第 {} 句，锚定判据 `{}`）：{}".format(
            it.get("section") or "-", it.get("sent_no"), it.get("anchor_rule"),
            it.get("sentence") or it.get("quote")))
        out.append("- 问题：{}".format(it.get("why") or "-"))
        out.append("- 建议改法：{}".format(it.get("fix") or "-"))
        if it.get("safe_replacement"):
            out.append("- 安全替代：{}".format(it["safe_replacement"]))
        out.append("")
    if not ins["issues"]:
        out.append("（没有锚定成功的问题）")
        out.append("")
    if ins["unanchored_issues"]:
        out.append("## 被剔出的问题（引文在讲义里找不到）")
        out.append("")
        for it in ins["unanchored_issues"]:
            out.append("- 引文「{}」—— {}".format(
                (it.get("quote") or "")[:40], it.get("why_unverified") or ""))
        out.append("")
    if gates:
        out.append("## 本地课程闸门（确定性判定）")
        out.append("")
        for k in ("objectives", "prerequisites", "terminology"):
            v = gates.get(k) or {}
            out.append("- **{}**：{}".format(k, v.get("why") or "-"))
        out.append("")
    out.append("_模型 `{}` · 输出 {} tokens · {:.1f}s_".format(
        model, (usage or {}).get("completion_tokens", "-"), elapsed))
    return "\n".join(out)


def render_report_md(log, escalation, convergence, gates, final_text, cost_rec, extra=None):
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
                (r["reason"] or "-").replace("|", "／")[:70], q,
                (r.get("forced_by_local") or "-").replace("|", "／")[:40]))
    else:
        out.append("（没有裁决记录）")
    out.append("")
    out.append("## 课件侧的裁决（放不放得下）")
    out.append("")
    if log.get("slide_rulings"):
        out.append("| # | 角色 | 轮次 | 裁决 | 理由 | 引用讲义原句 |")
        out.append("|---|---|---|---|---|---|")
        for r in log["slide_rulings"]:
            q = "；".join("「{}」".format(x[:24]) for x in (r["quotes"] or [])[:2]) or "-"
            out.append("| {} | {} | {} | **{}** | {} | {} |".format(
                r["seq"], r["role"], r["round"], r["decision"],
                (r["reason"] or "-").replace("|", "／")[:70], q))
    else:
        out.append("（没有课件侧的裁决）")
    out.append("")
    out.append("## 动作流水（谁在第几轮改了什么）")
    out.append("")
    out.append("| # | 阶段 | 角色 | 轮次 | 动作 | 说明 |")
    out.append("|---|---|---|---|---|---|")
    for e in log["entries"]:
        out.append("| {} | {} | {} | {} | {} | {} |".format(
            e["seq"], e["stage"], e["role"], e["round"], e["action"],
            (e["detail"] or "").replace("|", "／").replace("\n", " ")[:110]))
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
        out.append("- 出口：无（全流程走通，质检放行）")
    out.append("")
    out.append("## 硬闸门（本地确定性判定）")
    out.append("")
    hit = gate_failed_keys(gates)
    if hit:
        for k in hit:
            out.append("- **{}**：{}".format(k, json.dumps(
                gates[k], ensure_ascii=False)[:400]))
    else:
        out.append("- 全部通过")
    out.append("")
    if extra:
        out.append("## 课程特有闸门明细")
        out.append("")
        for k, v in extra.items():
            out.append("- **{}**：{}".format(k, (v or {}).get("why") or "-"))
        out.append("")
    if final_text:
        out.append("## 讲义合计（{} 字符）".format(char_count(final_text)))
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
    out = ["# 三剪客 · 课程教研组 —— 四个角色与职权", ""]
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
    out.append("于是课件永远看不到一个它不知道的自评、质检永远顺着课件的结论走 —— "
               "**对抗是假的**。")
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
    out.append("三条最关键的排除：")
    out.append("")
    out.append("1. **讲师的自评（`self_check`）不进课件的上下文** —— "
               "课件只看到讲义正文与课程结构，不知道作者自己觉得哪里好、哪里弱。")
    out.append("2. **讲师的 `self_check` 也不进质检的上下文**；"
               "**课件的放不下清单（`slide_issues`）同样不进质检的上下文** —— "
               "质检提示词里明说「本团队内部没有向你提供任何风险结论」，"
               "它必须从讲义正文独立判断。")
    out.append("3. **考核标准（`assessment`）只给质检，不给讲师** —— "
               "讲师一旦看到考核标准，就会把讲义写成对着考点划重点的形态。")
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
    out.append("教研 design ──▶ 讲师 lecture ──▶ 课件 slides ──┬─ fits ──────▶ 质检 inspect ──┬─ pass/fix ─▶ 交付")
    out.append("   ▲                     ▲                    │                          ├─ send_back ─┐")
    out.append("   │                     └── 放不下清单（引讲义原句）┘ cannot_fit               └─ veto ──────┼─▶ 带未决项产出")
    out.append("   └── 设计卡不达标 / 重开（上限 --design-retries）      └──── 讲师按反馈改写（上限给定）──┘")
    out.append("```")
    out.append("")
    out.append("**三个否决是串行关系，不是投票**：设计卡不达标就轮不到讲师；"
               "课件说放不下就先改讲义；质检在两者之后仍可独立否决。")
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


def read_json_file(path, what="JSON 文件"):
    if not path:
        raise UsageError("{}的路径是空的".format(what))
    p = Path(path)
    if not p.is_file():
        raise UsageError("{}不存在：{}".format(what, path))
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise UsageError("{}不是合法 JSON：{}（{}）".format(what, path, exc))


def check_budget(a):
    """**每个会花钱子命令的第一步**都要调它。

    为什么不给单价就不让用 --budget：不给单价时金额未知，`over_budget()` 永远返回
    False —— 那等于用户设了个**看起来生效、实际永远不触发**的上限。本包宁可直接
    报用法错，也不留一个假的保险丝。
    """
    if getattr(a, "budget", None) is not None and (
            getattr(a, "price_in", None) is None or getattr(a, "price_out", None) is None):
        raise UsageError("用了 --budget 就必须给 --price-in / --price-out —— "
                         "不给单价无法核预算，本包**不会**替你编一个单价。"
                         "（没有单价时 --budget 会永远不触发，那是个假保险丝。）")


def check_target_chars(n):
    if n < TARGET_CHARS_MIN or n > TARGET_CHARS_MAX:
        raise UsageError("--target-chars {} 超出可用区间 {}~{}（这是**单节讲义**的目标篇幅）。"
                         .format(n, TARGET_CHARS_MIN, TARGET_CHARS_MAX))
    return int(n)


def check_positive(name, v, allow_zero=True):
    lo = 0 if allow_zero else 1
    if v is None or int(v) < lo:
        raise UsageError("{} 必须 ≥ {}（给的是 {}）".format(name, lo, v))
    return int(v)


def check_sections_count(n):
    """`--sections` 的校验。**没给（None）时按上限 12 处理**，不是当 0 节。

    事故复盘（本包自测时踩到的真实坑）：`--sections` 的默认值是 `None`（表示"不限制"），
    但 `check_sections_count(None)` 里直接写 `if n < 1` 会让 `None < 1` 抛 TypeError，
    整条命令变成 `internal` 信封 —— **一个没给的参数把整条命令打崩了**。
    """
    if n is None:
        return MAX_SECTIONS
    n = int(n)
    if n < 1:
        raise UsageError("--sections 至少为 1（默认不限制，最多 {} 节）".format(MAX_SECTIONS))
    if n > MAX_SECTIONS:
        raise UsageError(
            "--sections {} 超过上限 {}。一节讲义一次调用，一次跑太多节的报价会失控；"
            "请拆成两次跑（第二次把已完成的节交给同一个 --outdir 续跑）。".format(
                n, MAX_SECTIONS))
    return n


def design_from_file(path):
    """读一份 `design --json --out` 的结果当设计卡（零成本复用）。"""
    if not path:
        return None
    obj = read_json_file(path, "课程设计卡")
    card = obj.get("card") if isinstance(obj, dict) and isinstance(obj.get("card"), dict) \
        else obj
    if not isinstance(card, dict) or not card.get("units"):
        raise UsageError("课程设计卡文件里没有可用的 card.units：{}".format(path))
    if "ok" not in card:
        card = normalize_design(card, attempt=int(card.get("attempt") or 1))
    return card


def lectures_from_file(path):
    """读一份 `lecture --json --out` 的结果当讲义（零成本复用）。"""
    if not path:
        return None
    obj = read_json_file(path, "讲义")
    lecs = obj.get("lectures") if isinstance(obj, dict) else obj
    if isinstance(obj, dict) and not isinstance(lecs, list):
        lecs = None
    if not isinstance(lecs, list) or not lecs:
        raise UsageError("讲义文件里没有可用的 lectures 列表：{}".format(path))
    out = []
    for x in lecs:
        if not isinstance(x, dict):
            continue
        out.append({"id": str(x.get("id") or ""), "unit_id": x.get("unit_id"),
                    "title": x.get("title") or "", "text": x.get("text") or ""})
    if not out:
        raise UsageError("讲义文件里的 lectures 是空的：{}".format(path))
    return out


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
            out_path = ensure_outside_pkg_file(a.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 {}\n".format(a.out))
        _json_write(body)
        return
    if getattr(a, "out", None):
        out_path = ensure_outside_pkg_file(a.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    print(md_text)


def _gate_stderr(label, gates):
    """把硬闸门命中汇总到 stderr（标红 + 逐条原因），返回是否命中。"""
    hit = [(k, gates[k]) for k in HARD_GATE_KEYS
           if isinstance(gates.get(k), dict) and not gates[k].get("ok", True)]
    if not hit:
        return False
    sys.stderr.write("\n{}\n".format(_red(
        "{}：{} 项硬闸门命中，交付前必须处理".format(label, len(hit)))))
    for k, v in hit:
        if k == "compliance":
            sys.stderr.write("   [合规] 命中 " + "、".join(
                "「{}」({})".format(h["word"], h["level"]) for h in v["hits"]) + "\n")
        elif k == "placeholder":
            sys.stderr.write("   [占位符] " + "；".join(h["why"] for h in v["hits"]) + "\n")
        elif k == "prompt_echo":
            sys.stderr.write("   [照抄示例] " + "；".join(h["why"] for h in v["hits"]) + "\n")
        elif k == "objectives":
            sys.stderr.write("   [学习目标可考核性] {}\n".format(v.get("why") or ""))
            for b in (v.get("bad") or [])[:6]:
                sys.stderr.write("      · 第 {} 条「{}」：{}\n".format(
                    b.get("index"), (b.get("objective") or "")[:40], b.get("why")))
        elif k == "prerequisites":
            sys.stderr.write("   [前置缺失] {}\n".format(v.get("why") or ""))
            for m in (v.get("missing") or [])[:6]:
                sys.stderr.write("      · {} 用到「{}」但前面没讲过：{}\n".format(
                    m.get("section"), m.get("term"), (m.get("sentence") or "")[:40]))
        elif k == "terminology":
            sys.stderr.write("   [术语一致性] {}\n".format(v.get("why") or ""))
            for m in (v.get("suspects") or [])[:4]:
                sys.stderr.write("      · 第 {} 节：「{}」vs「{}」\n".format(
                    m.get("section"), m.get("a"), m.get("b")))
        elif k == "length":
            sys.stderr.write("   [篇幅] {} 不在 {}~{} 区间（偏离 {} 字）\n".format(
                v["chars"], v["lo"], v["hi"], abs(v["delta"])))
        elif k == "anchor":
            sys.stderr.write("   [质检锚点] {}（已锚定 {} / {} 条）\n".format(
                v.get("why") or "未锚定率过高", v.get("verified"), v.get("total")))
    ex = (gates.get("compliance") or {}).get("exempted") or []
    if ex:
        sys.stderr.write("   提示：产出侧放过 {} 处疑似违禁词（每一处都留了原因），"
                         "请人工确认：\n".format(len(ex)))
        for e in ex[:6]:
            sys.stderr.write("      · 「{}」—— {}　上下文：{}\n".format(
                e["word"], e["reason"], e.get("context") or ""))
    return True


# ===========================================================================
# 子命令：roles（零成本）
# ===========================================================================

def build_roles_result():
    return {
        "mode": "roles", "role_version": ROLE_VERSION,
        "roles": [{
            "key": k, "name": ROLES[k]["name"], "goal": ROLES[k]["goal"],
            "deliverable": ROLES[k]["deliverable"], "veto": ROLES[k]["veto"],
            "inputs": ROLES[k]["inputs"], "forbidden": ROLES[k]["forbidden"],
            "exit_on_fail": ROLES[k]["exit_on_fail"],
        } for k in ROLE_ORDER],
        "exits": EXIT_KIND,
        "isolation": {
            "self_check_not_in_slides": (
                "讲师的 self_check 被显式排除在课件上下文之外（ROLES.slides.forbidden），"
                "每次调用前由 assert_isolation 做文本级检查，泄漏则中止调用并退出码 3"),
            "self_check_and_slide_issues_not_in_inspector": (
                "讲师的 self_check 与课件的 slide_issues 都被显式排除在质检上下文之外"
                "（ROLES.inspector.forbidden），质检提示词里明写"
                "「本团队内部没有向你提供任何风险结论」"),
            "assessment_only_to_inspector": (
                "单元的考核标准（assessment）只进质检的上下文，不进讲师的 —— "
                "讲师一旦看到考核标准，就会把讲义写成对着考点划重点的形态"),
            "markers": ISOLATION_MARKERS,
        },
        "course_specific_gates": {
            "objectives": "每条学习目标必须能被考核（可观察行为或可测标准）；"
                          "写成「了解 / 熟悉 / 掌握」判不可考核并标红",
            "prerequisites": "讲义里用到但前面从未讲过的术语 → 列为「前置缺失」",
            "terminology": "同一门课里同一概念两种叫法 → 记一致性疑点",
        },
        "note": "本包是 L3：角色各有目标函数与产出物，且**能否掉彼此**。"
                "若课件次次说放得下、质检条条放行，那就是假协作 —— 看 log 的裁决记录。",
    }


def run_roles(a):
    _emit(a, build_roles_result(), render_roles_md(), ok=True)
    return EXIT_OK


# ===========================================================================
# 子命令：design
# ===========================================================================

def design_once(a, brief, chapters, spc, target_chars, model, key, tracker, attempt,
                attempt_note, outdir, state=None, brief_sha=None):
    """跑一次教研。返回 (card, usage, elapsed, iso, prompt_chars)。

    ⚠️ `--dry-run` 下**抛 DryRunStop 把提示词带出来**，而不是返回一个"假的 card"。
    dry-run 的全部价值就是让你看清将要发出去的提示词，打 null 等于这个开关废了。
    """
    skey = state_key("design", brief_sha=brief_sha, brief_chars=char_count(brief),
                     model=model, temperature=a.temperature, round_no=attempt,
                     target_chars=target_chars, chapters=chapters,
                     sections_per_chapter=spc)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("教研（第 {} 次尝试）已在断点里，跳过（零成本）。\n".format(attempt))
            return (normalize_design(hit["raw"], attempt), hit.get("usage") or {}, 0.0,
                    hit.get("iso") or {"excluded": [], "markers_checked": 0,
                                       "leaked": [], "ok": True},
                    hit.get("prompt_chars") or 0)
    prompt = build_design_prompt(brief, chapters, spc, target_chars, attempt_note)
    obj, usage, elapsed, iso, pchars = _role_call(
        "designer", prompt, model, key, tracker, a, "课程设计卡", DESIGN_OUT_TOKENS)
    card = normalize_design(obj, attempt)
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "raw": {k: card.get(k) for k in
                    ("title", "audience", "objectives", "prerequisites", "units",
                     "terms", "assessment_criteria", "risk_note")},
            "usage": usage, "iso": iso, "prompt_chars": pchars}
        if outdir:
            save_state(outdir, state)
    return card, usage, elapsed, iso, pchars


def run_design(a):
    brief = read_text(a.brief, "用户材料")
    if not brief.strip():
        raise UsageError("用户材料是空的：{}".format(a.brief))
    # ⚠️ 预算校验**提到第一步**：超了就地停，一次调用都不发
    check_budget(a)
    target_chars = check_target_chars(a.target_chars)
    chapters = check_positive("--chapters", a.chapters, allow_zero=False)
    spc = check_positive("--sections-per-chapter", a.sections_per_chapter, allow_zero=False)
    retries = check_positive("--design-retries", a.design_retries)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = state = None
    if a.outdir:
        outdir = ensure_outside_pkg(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    log = new_log()
    tried, card, usage, elapsed, iso, pchars = [], None, {}, 0.0, None, 0
    for attempt in range(1, retries + 2):
        note = None
        if tried:
            note = ("上一次的设计卡被本地判为不达标，原因：\n"
                    + "\n".join("  · " + p for p in tried[-1]["problems"])
                    + "\n请重出一张，**不要只是把上一版换几个词**。"
                      "学习目标一定要落在可观察的行为或可测的标准上。")
        card, usage, elapsed, iso, pchars = design_once(
            a, brief, chapters, spc, target_chars, a.model, a.key, tracker, attempt,
            note, outdir, state, text_sha(brief))
        log_isolation(log, "designer", iso, pchars, attempt)
        tried.append(card)
        log_entry(log, "design", "教研", attempt, "交课程设计卡",
                  "课程名「{}」；{} 个单元；目标可考核性 {}；{}".format(
                      card["title"], len(card["units"]),
                      (card.get("objective_check") or {}).get("why"),
                      "达标" if card["ok"] else "**不达标**：" + "；".join(card["problems"])))
        if card["ok"]:
            log_ruling(log, "教研", attempt, "accepted",
                       "设计卡达标：目标可考核、每单元有考核标准、前置知识非空",
                       (card.get("objectives") or [])[:2])
            break
        log_ruling(log, "教研", attempt, "rejected",
                   "设计卡不达标（重开）：{}".format("；".join(card["problems"])[:120]),
                   card["problems"][:2])
    rc = EXIT_OK
    escalation = None
    if card and not card["ok"]:
        escalation = {"kind": "design_retries_exhausted", "rounds_run": len(tried),
                      "unresolved": card["problems"]}
        rc = EXIT_GATE
        sys.stderr.write("\n{}\n".format(_red(
            "教研重开上限（--design-retries {}）用尽，设计卡仍不达标 —— "
            "升级给人看，不硬着头皮往下写。".format(retries))))
    result = {
        "mode": "design", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model, "target_chars": target_chars,
        "chapters": chapters, "sections_per_chapter": spc,
        "brief": {"path": str(a.brief), "sha": text_sha(brief), "chars": char_count(brief)},
        "attempts": len(tried), "card": card, "escalation": escalation,
        "log": log, "usage": usage, "elapsed": elapsed,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
    }
    if outdir is not None:
        (outdir / "design.json").write_text(
            json.dumps({"card": card, "attempts": tried, "escalation": escalation},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "design.md").write_text(
            render_design_md(card, a.model, usage, elapsed) + "\n", encoding="utf-8")
        sys.stderr.write("目录产物：{}（design.json / design.md）\n".format(outdir))
    _emit(a, result, render_design_md(card, a.model, usage, elapsed), ok=not rc)
    return rc


# ===========================================================================
# 子命令：lecture
# ===========================================================================

def lecture_once(a, brief, digest, section, target_chars, prior_digests, model, key,
                 tracker, outdir, state=None, brief_sha=None, card_sha=None,
                 chapters=None, spc=None, attempt=0, stage_note=None):
    skey = state_key("lecture", brief_sha=brief_sha, brief_chars=char_count(brief),
                     card_sha=card_sha, model=model, temperature=a.temperature,
                     round_no=attempt, target_chars=target_chars, chapters=chapters,
                     sections_per_chapter=spc, section_id=section.get("id"))
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("讲义 {} 已在断点里，跳过（零成本）。\n".format(section.get("id")))
            return (hit["lecture"], hit.get("self_check") or {},
                    hit.get("terms") or [], hit.get("usage") or {}, 0.0,
                    hit.get("iso") or {"excluded": [], "markers_checked": 0,
                                       "leaked": [], "ok": True},
                    hit.get("prompt_chars") or 0)
    prompt = build_lecture_prompt(brief, digest, section, target_chars, prior_digests,
                                  stage_note)
    obj, usage, elapsed, iso, pchars = _role_call(
        "instructor", prompt, model, key, tracker, a,
        "讲义 {}".format(section.get("id")),
        int(target_chars * TOKENS_PER_CHAR_OUT))
    lec, sc, terms = normalize_lecture(obj, section)
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "lecture": lec, "self_check": sc, "terms": terms,
            "usage": usage, "iso": iso, "prompt_chars": pchars}
        if outdir:
            save_state(outdir, state)
    return lec, sc, terms, usage, elapsed, iso, pchars


def run_lecture(a):
    brief = read_text(a.brief, "用户材料")
    if not brief.strip():
        raise UsageError("用户材料是空的：{}".format(a.brief))
    check_budget(a)
    target_chars = check_target_chars(a.target_chars)
    card = design_from_file(a.design)
    if a.design:
        card = card or {}
    chapters = check_positive("--chapters", a.chapters, allow_zero=False)
    spc = check_positive("--sections-per-chapter", a.sections_per_chapter, allow_zero=False)
    limit_secs = check_sections_count(a.sections)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = state = None
    if a.outdir:
        outdir = ensure_outside_pkg(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    log = new_log()
    usages = []
    digest = design_digest_for_instructor(card)
    sections = limit_sections(section_plan(card.get("units") or [], spc), limit_secs)
    if not sections:
        raise UsageError("设计卡里没有可用的单元 —— 拿不到要写哪几节。")
    if len(section_plan(card.get("units") or [], spc)) > limit_secs:
        sys.stderr.write("注意：本次只写前 {} 节（共 {} 节），"
                         "不是静默截断，是 --sections 的显式限制。\n".format(
                             limit_secs, len(section_plan(card.get("units") or [], spc))))
    if a.design:
        sys.stderr.write("⚠️ 只给了 --design（没有活动课程结构参数）："
                         "课程规模按 --chapters/--sections-per-chapter 计算，"
                         "如果与设计卡不一致，请对齐这两个参数。\n")
    lectures, prior = [], []
    for sec in sections:
        lec, sc, terms, usage, elapsed, iso, pchars = lecture_once(
            a, brief, digest, sec, target_chars, prior, a.model, a.key, tracker, outdir,
            state, text_sha(brief), card.get("card_sha"), chapters, spc)
        usages.append(usage)
        log_isolation(log, "instructor", iso, pchars, sec.get("section_index"))
        log_entry(log, "lecture", "讲师", sec.get("section_index"), "交讲义",
                  "{}「{}」{} 字符；新引入术语 {} 个；"
                  "自评 {} 条（**课件与质检都看不到这一栏**）".format(
                      sec.get("id"), lec.get("title"), char_count(lec.get("text")),
                      len(terms),
                      len((sc or {}).get("good") or []) + len((sc or {}).get("weak") or [])))
        lectures.append({"id": lec["id"], "unit_id": lec.get("unit_id"),
                         "title": lec.get("title"), "text": lec.get("text"),
                         "terms_introduced": terms})
        prior.append({"id": lec["id"], "title": lec.get("title"), "terms": terms})
        if outdir is not None:
            p = outdir / "lectures"
            p.mkdir(parents=True, exist_ok=True)
            (p / "{}.md".format(lec["id"])).write_text(
                render_lecture_md(lec, sc, a.model, usage, elapsed, terms) + "\n",
                encoding="utf-8")
    gate = evaluate_course_gates(card, sections_from_lectures(lectures))
    rc = EXIT_OK if gate["ok"] else EXIT_GATE
    result = {
        "mode": "lecture", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model, "target_chars": target_chars,
        "brief": {"path": str(a.brief), "sha": text_sha(brief), "chars": char_count(brief)},
        "sections_planned": len(section_plan(card.get("units") or [], spc)),
        "sections_written": len(lectures),
        "lectures": lectures, "gates": gate, "gate_failed": not gate["ok"],
        "log": log, "usage": _sum_usage(usages), "cost": fmt_cost_dict(tracker) if
        tracker.calls else None,
    }
    if outdir is not None:
        (outdir / "lectures.json").write_text(
            json.dumps({"lectures": lectures, "gates": gate},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        sys.stderr.write("目录产物：{}（lectures.json / lectures/*.md）\n".format(outdir))
    _gate_stderr("讲义", gate)
    md = "\n\n".join(render_lecture_md(
        {"id": l["id"], "title": l["title"], "text": l["text"]}, {}, a.model, {}, 0.0,
        l.get("terms_introduced")) for l in lectures)
    _emit(a, result, md, ok=not rc)
    return rc


# ===========================================================================
# 课程特有的三道本地闸门（学习目标 / 前置知识 / 术语一致性）
# ===========================================================================

def evaluate_course_gates(card, sections):
    """跑本包特有的三道课程闸门。

    这三道是本包区别于「一篇文章 + 一个排版包」的地方：
      · objectives    学习目标能不能被考核
      · prerequisites 讲义里用到但前面从没讲过的术语
      · terminology   同一概念两种叫法
    """
    card = card if isinstance(card, dict) else {}
    obj_pool = list(card.get("objectives") or [])
    for u in card.get("units") or []:
        obj_pool.extend(u.get("objectives") or [])
    obj_stat = check_objectives(obj_pool)
    obj_stat["scope"] = "课程目标 + 各单元目标（共 {} 条）".format(len(obj_pool))
    prereq = check_prerequisites(sections, card.get("prerequisites"))
    term = check_terminology(sections)
    gates = {
        "objectives": obj_stat,
        "prerequisites": prereq,
        "terminology": term,
        "ok": bool(obj_stat["ok"] and prereq["ok"] and term["ok"]),
    }
    return gates


# ===========================================================================
# 子命令：slides
# ===========================================================================

def slides_once(a, brief, card, lectures, max_pages, model, key, tracker, outdir,
                state=None, brief_sha=None, round_no=1, chapters=None, spc=None):
    card_sha = card.get("card_sha") if isinstance(card, dict) else None
    deck_in_sha = text_sha(json.dumps(
        [{"id": l.get("id"), "text": l.get("text")} for l in lectures],
        ensure_ascii=False, sort_keys=True))
    skey = state_key("slides", brief_sha=brief_sha, brief_chars=char_count(brief),
                     text_sha_=deck_in_sha, card_sha=card_sha, model=model,
                     temperature=a.temperature, round_no=round_no, max_pages=max_pages,
                     chapters=chapters, sections_per_chapter=spc)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("课件方案（第 {} 轮）已在断点里，跳过（零成本）。\n".format(round_no))
            return (hit["deck"], hit.get("usage") or {}, 0.0,
                    hit.get("iso") or {"excluded": [], "markers_checked": 0,
                                       "leaked": [], "ok": True},
                    hit.get("prompt_chars") or 0)
    prompt = build_slides_prompt(brief, design_digest_for_slides(card), lectures, max_pages)
    obj, usage, elapsed, iso, pchars = _role_call(
        "slides", prompt, model, key, tracker, a,
        "逐页课件方案（第 {} 轮）".format(round_no), SLIDES_OUT_TOKENS)
    deck = normalize_deck(obj, sections_from_lectures(lectures), max_pages)
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "deck": deck, "usage": usage, "iso": iso, "prompt_chars": pchars}
        if outdir:
            save_state(outdir, state)
    return deck, usage, elapsed, iso, pchars


def run_slides(a):
    brief = read_text(a.brief, "用户材料")
    if not brief.strip():
        raise UsageError("用户材料是空的：{}".format(a.brief))
    check_budget(a)
    max_pages = check_positive("--max-pages", a.max_pages, allow_zero=False)
    card = design_from_file(a.design)
    lectures = lectures_from_file(a.lectures)
    if not lectures:
        raise UsageError("--lectures 是必填的：课件要基于讲义才能判断放不放得下。")
    check_positive("--chapters", a.chapters, allow_zero=False)
    spc = check_positive("--sections-per-chapter", a.sections_per_chapter, allow_zero=False)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = state = None
    if a.outdir:
        outdir = ensure_outside_pkg(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    log = new_log()
    deck, usage, elapsed, iso, pchars = slides_once(
        a, brief, card, lectures, max_pages, a.model, a.key, tracker, outdir, state,
        text_sha(brief), 1, a.chapters, spc)
    log_isolation(log, "slides", iso, pchars, 1)
    log_entry(log, "slides", "课件", 1, "交逐页方案",
              "{} 页；结论 {}；放不下 {} 条；本地复核：{}".format(
                  len(deck["pages"]), deck["verdict"], len(deck["issues"]),
                  (deck.get("local_check") or {}).get("why")))
    if deck["verdict"] == "cannot_fit":
        log_ruling(log, "课件", 1, "cannot_fit",
                   "{} 页里有 {} 处放不下：{}".format(
                       len(deck["pages"]), len(deck["issues"]),
                       "；".join((i.get("why") or "")[:40] for i in deck["issues"][:3])),
                   [i.get("sentence") or i.get("quote") for i in deck["issues"][:3]],
                   bucket="slide_rulings")
    else:
        log_ruling(log, "课件", 1, "fits", deck.get("summary") or "逐页复核，全部放得下",
                   bucket="slide_rulings")
    if deck.get("local_notes"):
        log_ruling(log, "课件（本地复核）", 1, "本地判定 " + str(deck["verdict"]),
                   "；".join(deck["local_notes"]),
                   [i.get("sentence") or i.get("quote") for i in deck["issues"][:3]],
                   bucket="slide_rulings")
    rc = EXIT_OK if not deck["gate_failed"] else EXIT_GATE
    result = {
        "mode": "slides", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model, "max_pages": max_pages,
        "brief": {"path": str(a.brief), "sha": text_sha(brief), "chars": char_count(brief)},
        "deck": deck, "gate_failed": deck["gate_failed"],
        "log": log, "usage": usage, "elapsed": elapsed,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
    }
    if outdir is not None:
        (outdir / "deck.json").write_text(
            json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "deck.md").write_text(
            render_deck_md(deck, a.model, usage, elapsed, 1) + "\n", encoding="utf-8")
        sys.stderr.write("目录产物：{}（deck.json / deck.md）\n".format(outdir))
    if rc:
        sys.stderr.write("\n{}\n".format(_red(
            "课件侧说「放不下」：{} 处。请把这些页对应的讲义内容压缩或拆分后重跑。".format(
                len(deck["issues"])))))
    _emit(a, result, render_deck_md(deck, a.model, usage, elapsed, 1), ok=not rc)
    return rc


# ===========================================================================
# 子命令：inspect
# ===========================================================================

def scan_lecture_text(lectures, produce_side=True):
    """对讲义全文跑**确定性**的文本闸门：合规 / 占位符 / 照抄示例。

    【为什么必须单独有这一步】`inspect` 子命令的说明里写着它审「前后一致 + 事实与合规」，
    但真机自测发现：这条路径**只**跑了课程特有的三道闸门（目标 / 依赖 / 术语），
    合规、占位符、prompt_echo 三道文本闸门一次都没跑 —— 于是讲义里写着
    「保证提分 / 保过」时，只要质检模型自己没发现，命令就放行了。
    **闸门写在文档里、实现里却没有，等于没有。** 所以把这三道抽出来，
    `inspect` 与 `run` 共用同一份实现。
    """
    text = "\n\n".join(str(l.get("text") or "") for l in (lectures or []))
    hits_c, exempted = compliance_scan(text, produce_side=produce_side)
    ph = placeholder_hits(text)
    echo = prompt_echo_scan(text)
    return {
        "compliance": {"ok": not hits_c, "hits": hits_c, "exempted": exempted,
                       "cap": (COMPLIANCE_CAP.get(hits_c[0]["level"]) if hits_c else None),
                       "side": "产出侧（含警告语境豁免）" if produce_side else "材料侧"},
        "placeholder": {"ok": not ph, "hits": ph},
        "prompt_echo": {"ok": not echo, "hits": echo},
    }


def inspect_once(a, brief, card, lectures, model, key, tracker, outdir, state=None,
                 brief_sha=None, round_no=1, stage_note=None, chapters=None, spc=None):
    lec_sha = text_sha(json.dumps(
        [{"id": l.get("id"), "text": l.get("text")} for l in lectures],
        ensure_ascii=False, sort_keys=True))
    skey = state_key("inspect", brief_sha=brief_sha, brief_chars=char_count(brief),
                     text_sha_=lec_sha, card_sha=(card or {}).get("card_sha"), model=model,
                     temperature=a.temperature, round_no=round_no, chapters=chapters,
                     sections_per_chapter=spc)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("质检（第 {} 轮）已在断点里，跳过（零成本）。\n".format(round_no))
            return (hit["inspection"], hit.get("usage") or {}, 0.0,
                    hit.get("iso") or {"excluded": [], "markers_checked": 0,
                                       "leaked": [], "ok": True},
                    hit.get("prompt_chars") or 0, hit.get("gates") or {})
    prompt = build_inspect_prompt(brief, card, lectures, stage_note)
    obj, usage, elapsed, iso, pchars = _role_call(
        "inspector", prompt, model, key, tracker, a,
        "质检问题清单与风险裁决（第 {} 轮）".format(round_no), INSPECT_OUT_TOKENS)
    course_gates = evaluate_course_gates(card, sections_from_lectures(lectures))
    # 文本闸门（合规 / 占位符 / 照抄示例）：与课程闸门一起交给归一化做本地兜底
    text_gates = scan_lecture_text(lectures)
    gate_bundle = dict(course_gates)
    gate_bundle.update({"objective": course_gates.get("objectives") or {},
                        "dependency": course_gates.get("prerequisites") or {},
                        "terminology": course_gates.get("terminology") or {},
                        "compliance": text_gates["compliance"],
                        "placeholder": text_gates["placeholder"],
                        "prompt_echo": text_gates["prompt_echo"]})
    ins = normalize_inspection(obj, sections_from_lectures(lectures), gate_bundle)
    if state is not None:
        state.setdefault("entries", {})[skey] = {
            "inspection": ins, "usage": usage, "iso": iso, "prompt_chars": pchars,
            "gates": course_gates}
        if outdir:
            save_state(outdir, state)
    return ins, usage, elapsed, iso, pchars, gate_bundle


def run_inspect(a):
    brief = read_text(a.brief, "用户材料")
    if not brief.strip():
        raise UsageError("用户材料是空的：{}".format(a.brief))
    check_budget(a)
    card = design_from_file(a.design)
    lectures = lectures_from_file(a.lectures)
    if not lectures:
        raise UsageError("--lectures 是必填的：质检要基于讲义才能逐条引用原句。")
    check_positive("--chapters", a.chapters, allow_zero=False)
    spc = check_positive("--sections-per-chapter", a.sections_per_chapter, allow_zero=False)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = state = None
    if a.outdir:
        outdir = ensure_outside_pkg(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    log = new_log()
    ins, usage, elapsed, iso, pchars, gates = inspect_once(
        a, brief, card, lectures, a.model, a.key, tracker, outdir, state,
        text_sha(brief), 1, None, a.chapters, spc)
    log_isolation(log, "inspector", iso, pchars, 1)
    log_entry(log, "inspect", "质检", 1, "出问题清单与风险裁决",
              "锚定 {} / 未锚定 {}（未锚定率 {:.0%}）；裁决 {}；本地课程闸门 {}".format(
                  ins["anchor"]["verified"], ins["anchor"]["unanchored"],
                  ins["anchor"]["miss_rate"], ins["verdict"],
                  "命中" if not gates["ok"] else "全过"),
              [it.get("sentence") or it.get("quote") for it in ins["issues"][:3]])
    log_ruling(log, "质检", 1, ins["verdict"],
               ins.get("reason") or "（未给理由）",
               [it.get("sentence") or it.get("quote") for it in ins["issues"][:3]],
               forced_by_local="；".join(ins["local_notes"]) or None)
    if ins.get("verdict_forced_reason") or ins.get("local_notes"):
        log_ruling(log, "质检（本地兜底）", 1, "改判为 " + str(ins["verdict"]),
                   "；".join(ins["local_notes"]) or str(ins.get("verdict_forced_reason")),
                   [it.get("sentence") or it.get("quote") for it in ins["issues"][:3]],
                   forced_by_local="；".join(ins["local_notes"]) or None)
    combined = dict(gates)
    combined["objectives"] = gates.get("objective") or {}
    combined["prerequisites"] = gates.get("dependency") or {}
    combined["anchor"] = ins["anchor"]
    rc = EXIT_OK if (not gate_failed(combined) and ins["verdict"] in ("pass", "fix")) \
        else EXIT_GATE
    result = {
        "mode": "inspect", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model,
        "brief": {"path": str(a.brief), "sha": text_sha(brief), "chars": char_count(brief)},
        "inspection": ins, "course_gates": gates, "gate_failed": bool(rc),
        "log": log, "usage": usage, "elapsed": elapsed,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
    }
    if outdir is not None:
        (outdir / "inspection.json").write_text(
            json.dumps({"inspection": ins, "course_gates": gates},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "inspection.md").write_text(
            render_inspection_md(ins, a.model, usage, elapsed, 1, gates) + "\n",
            encoding="utf-8")
        sys.stderr.write("目录产物：{}（inspection.json / inspection.md）\n".format(outdir))
    _gate_stderr("质检", combined)
    _emit(a, result, render_inspection_md(ins, a.model, usage, elapsed, 1, gates),
          ok=not rc)
    return rc


# ===========================================================================
# 子命令：run —— 一条命令出整门课，带裁决、轮次上限与明确出口
# ===========================================================================

def run_run(a):
    if getattr(a, "out", None):
        # `run` 的产物是一个**目录**（design.json / lectures.json / deck.json /
        # REPORT.md / log.json / state.json），不是单个文件。
        # 同族踩过 "--out 被静默当成 --outdir 的缩写"，本包不允许长选项缩写，
        # 但 `run` 子命令又确实注册了 --out（共用模型选项组），
        # 于是 `run --out x.json` 会被**收下却完全没用** —— 用户以为写盘了。
        # 与其留一个静默无效的参数，不如直接报用法错。
        raise UsageError(
            "`run` 没有单文件产出，请用 --outdir 指定产出目录"
            "（design.json / lectures.json / deck.json / final.md / REPORT.md / "
            "log.json / state.json）。要单文件结果请用 design / lecture / slides / "
            "inspect 的 --out。")
    brief = read_text(a.brief, "用户材料")
    if not brief.strip():
        raise UsageError("用户材料是空的：{}".format(a.brief))
    # ⚠️ 全部参数先校验、预算先核 —— **一次调用都还没发生**
    check_budget(a)
    target_chars = check_target_chars(a.target_chars)
    chapters = check_positive("--chapters", a.chapters, allow_zero=False)
    spc = check_positive("--sections-per-chapter", a.sections_per_chapter, allow_zero=False)
    max_pages = check_positive("--max-pages", a.max_pages, allow_zero=False)
    design_retries = check_positive("--design-retries", a.design_retries)
    rounds = check_positive("--rounds", a.rounds)
    slide_rework = check_positive("--slide-rework", a.slide_rework)
    inspect_rework = check_positive("--inspect-rework", a.inspect_rework)
    limit_secs = check_sections_count(a.sections)
    if rounds < 1:
        raise UsageError("--rounds 至少为 1 —— 本包的语义是"
                         "「教研 → 讲师 → 课件 → 质检 → 修订」，0 轮没有协作可谈。")
    outdir = ensure_outside_pkg(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state = {"version": STATE_VERSION, "entries": {}} if a.force else load_state(outdir)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    log = new_log()
    usages = []
    rulings_summary = {"designer_reject": 0, "slides_cannot_fit": 0,
                       "inspector_send_back": 0, "inspector_veto": 0,
                       "slide_rework": 0, "inspect_rework": 0}
    all_sections = None

    # ---------------- 1) 教研 ----------------
    card, tried = None, []
    for attempt in range(1, design_retries + 2):
        note = None
        if tried:
            note = ("上一次的设计卡被本地判为不达标，原因：\n"
                    + "\n".join("  · " + p for p in tried[-1]["problems"])
                    + "\n请重出一张，**不要只是把上一版换几个词**。")
        card, usage, elapsed, iso, pchars = design_once(
            a, brief, chapters, spc, target_chars, a.model, a.key, tracker, attempt,
            note, outdir, state, text_sha(brief))
        usages.append(usage)
        log_isolation(log, "designer", iso, pchars, attempt)
        tried.append(card)
        log_entry(log, "design", "教研", attempt, "交课程设计卡",
                  "课程名「{}」；{} 个单元；{}".format(
                      card["title"], len(card["units"]),
                      "达标" if card["ok"] else "不达标：" + "；".join(card["problems"])[:100]))
        if card["ok"]:
            log_ruling(log, "教研", attempt, "accepted",
                       "设计卡达标：目标可考核、每单元有考核标准、前置知识非空",
                       (card.get("objectives") or [])[:2])
            break
        rulings_summary["designer_reject"] += 1
        log_ruling(log, "教研", attempt, "rejected",
                   "设计卡不达标（重开）：{}".format("；".join(card["problems"])[:120]),
                   card["problems"][:2])

    escalation = None
    if card is None or not card["ok"]:
        escalation = {"kind": "design_retries_exhausted", "rounds_run": len(tried),
                      "unresolved": (card or {}).get("problems") or ["教研没有交出可用设计卡"]}
        return _finish_run(a, outdir, log, escalation, None, brief, card, target_chars,
                           chapters, spc, max_pages, rounds, usages, tracker,
                           rulings_summary, [], None, None, [])

    # ---------------- 2) 讲师逐节写讲义 ----------------
    digest = design_digest_for_instructor(card)
    all_sections = section_plan(card.get("units") or [], spc)
    sections = limit_sections(all_sections, limit_secs)
    if len(all_sections) > len(sections):
        log_entry(log, "lecture", "讲师", 0, "按 --sections 限制节数",
                  "设计卡展开共 {} 节，本次只写前 {} 节（显式限制，不是静默截断）".format(
                      len(all_sections), len(sections)))
    lectures, prior, self_checks, terms_by_id = [], [], {}, {}
    for sec in sections:
        lec, sc, terms, usage, elapsed, iso, pchars = lecture_once(
            a, brief, digest, sec, target_chars, prior, a.model, a.key, tracker, outdir,
            state, text_sha(brief), card.get("card_sha"), chapters, spc)
        usages.append(usage)
        log_isolation(log, "instructor", iso, pchars, sec.get("section_index"))
        log_entry(log, "lecture", "讲师", sec.get("section_index"), "交讲义",
                  "{}「{}」{} 字符；自评 {} 条（**课件与质检都看不到这一栏**）".format(
                      sec.get("id"), lec.get("title"), char_count(lec.get("text")),
                      len((sc or {}).get("good") or []) + len((sc or {}).get("weak") or [])))
        lectures.append({"id": lec["id"], "unit_id": lec.get("unit_id"),
                         "title": lec.get("title"), "text": lec.get("text"),
                         "terms_introduced": terms})
        prior.append({"id": lec["id"], "title": lec.get("title"), "terms": terms})
        self_checks[lec["id"]] = sc
        terms_by_id[lec["id"]] = terms
        _write_lecture_dir(outdir, None, lec, sc, a.model, usage, elapsed, terms)

    # ---------------- 3) 课件：逐页方案，**能说放不下** ----------------
    deck, slide_round = None, 0
    slide_rework_used = 0
    while True:
        slide_round += 1
        deck, usage, elapsed, iso, pchars = slides_once(
            a, brief, card, lectures, max_pages, a.model, a.key, tracker, outdir, state,
            text_sha(brief), slide_round, chapters, spc)
        usages.append(usage)
        log_isolation(log, "slides", iso, pchars, slide_round)
        lc = deck.get("local_check") or {}
        log_entry(log, "slides", "课件", slide_round, "交逐页方案",
                  "{} 页（上限 {}）；结论 {}；放不下 {} 条；本地复核：{}".format(
                      len(deck["pages"]), max_pages, deck["verdict"],
                      len(deck["issues"]), lc.get("why")))
        if deck["verdict"] == "cannot_fit":
            rulings_summary["slides_cannot_fit"] += 1
            log_ruling(log, "课件", slide_round, "cannot_fit",
                       "{} 页里有 {} 处放不下：{}".format(
                           len(deck["pages"]), len(deck["issues"]),
                           "；".join((i.get("why") or "")[:50] for i in deck["issues"][:3])),
                       [i.get("sentence") or i.get("quote") for i in deck["issues"][:3]],
                       bucket="slide_rulings")
        else:
            log_ruling(log, "课件", slide_round, "fits",
                       deck.get("summary") or "逐页复核，全部放得下", bucket="slide_rulings")
        # 本地兜底单独入账（模型自报的结论与本地复核不一致时，必须让人看得出是谁改的判）
        if deck.get("local_notes"):
            log_ruling(log, "课件（本地复核）", slide_round,
                       "本地判定 " + str(deck["verdict"]),
                       "；".join(deck["local_notes"]),
                       [i.get("sentence") or i.get("quote") for i in deck["issues"][:3]],
                       bucket="slide_rulings")
        _write_deck_dir(outdir, slide_round, deck, a.model, usage, elapsed)
        if deck["verdict"] != "cannot_fit":
            break
        # 课件说放不下 → 让讲师按清单改写被点到的节
        if slide_rework_used >= slide_rework:
            escalation = {"kind": "slide_rework_exhausted", "rounds_run": slide_round,
                          "unresolved": ["课件重做 {} 次后仍说放不下：{}".format(
                              slide_rework_used,
                              "；".join("第 {} 页（{}）".format(
                                  i.get("page"), (i.get("why") or "")[:50])
                                  for i in deck["issues"][:5]))]}
            break
        slide_rework_used += 1
        rulings_summary["slide_rework"] += 1
        rc2 = _apply_slide_feedback(a, brief, card, digest, sections, lectures, deck,
                                    target_chars, chapters, spc, outdir, state, tracker,
                                    usages, log, self_checks, terms_by_id)
        if rc2:                       # 改写失败 → 出口
            escalation = rc2
            break

    # ---------------- 4) 质检 ↔ 讲师修订 ----------------
    comp = None
    if escalation is None:
        cur = lectures
        inspect_used = 0
        strikes = 0
        prev_rejected_quotes = set()
        stalled_quote = None
        round_runs = []
        while True:
            inspect_used += 1
            ins, usage, elapsed, iso, pchars, gates = inspect_once(
                a, brief, card, cur, a.model, a.key, tracker, outdir, state,
                text_sha(brief), inspect_used, None, chapters, spc)
            usages.append(usage)
            log_isolation(log, "inspector", iso, pchars, inspect_used)
            log_entry(log, "inspect", "质检", inspect_used, "出问题清单与风险裁决",
                      "锚定 {} / 未锚定 {}（未锚定率 {:.0%}）；裁决 {}；"
                      "本地课程闸门 {}".format(
                          ins["anchor"]["verified"], ins["anchor"]["unanchored"],
                          ins["anchor"]["miss_rate"], ins["verdict"],
                          "命中" if not gates["ok"] else "全过"),
                      [it.get("sentence") or it.get("quote") for it in ins["issues"][:3]])
            log_ruling(log, "质检", inspect_used, ins["verdict"],
                       ins.get("reason") or "（未给理由）",
                       [it.get("sentence") or it.get("quote") for it in ins["issues"][:3]],
                       forced_by_local="；".join(ins["local_notes"]) or None)
            # **本地兜底必须单独入账**：模型可能自报 pass，但本地课程闸门把它改判成了
            # send_back。真机第一次跑就出现了「裁决表写着 pass、出口却是
            # inspect_send_back_exhausted」的矛盾 —— 记录里只留模型的自报值，
            # 读报告的人根本看不出哪一步把它挡住了。所以改判另起一条。
            if ins.get("verdict_forced_reason") or ins.get("local_notes"):
                log_ruling(log, "质检（本地兜底）", inspect_used,
                           "改判为 " + str(ins["verdict"]),
                           "；".join(ins["local_notes"]) or str(ins.get("verdict_forced_reason")),
                           [it.get("sentence") or it.get("quote") for it in ins["issues"][:3]],
                           forced_by_local="；".join(ins["local_notes"]) or None)
            _write_inspect_dir(outdir, inspect_used, ins, gates, a.model, usage, elapsed)
            if ins["verdict"] == "veto":
                rulings_summary["inspector_veto"] += 1
            elif ins["verdict"] == "send_back":
                rulings_summary["inspector_send_back"] += 1
            if ins["verdict"] in ("pass", "fix") and ins["anchor"]["ok"]:
                comp = ins
                break
            if ins["verdict"] == "veto":
                escalation = {"kind": "inspect_send_back_exhausted",
                              "rounds_run": inspect_used,
                              "unresolved": ["质检否决：{}".format(ins.get("reason") or "未给理由")]
                              + ["[{}] {}".format(i.get("severity"), (i.get("quote") or "")[:60])
                                 for i in ins["issues"][:5]]}
                comp = ins
                break
            if not ins["anchor"]["ok"]:
                escalation = {"kind": "rounds_exhausted", "rounds_run": inspect_used,
                              "unresolved": ["质检锚点闸门命中：" + (ins["anchor"].get("why") or "")]}
                comp = ins
                break
            # send_back → 检查是不是"讲师改不动"（连续两次指向同一批文字）
            cur_quotes = set(_norm_anchor(it.get("sentence") or it.get("quote") or "")
                             for it in ins["issues"] if it["id"] in ins["must_fix"])
            if prev_rejected_quotes and cur_quotes and \
                    len(cur_quotes & prev_rejected_quotes) >= max(1, len(cur_quotes) // 2):
                stalled_quote = sorted(cur_quotes & prev_rejected_quotes)[0][:40]
            prev_rejected_quotes = cur_quotes
            if inspect_used > inspect_rework:
                escalation = {"kind": "inspect_send_back_exhausted",
                              "rounds_run": inspect_used,
                              "unresolved": ["质检打回 {} 次仍不放行：{}".format(
                                  inspect_used, ins.get("reason") or "未给理由")]
                              + ["#{}({})".format(it["id"], (it.get("sentence") or "")[:40])
                                 for it in ins["issues"] if it["id"] in ins["must_fix"]]}
                comp = ins
                break
            if stalled_quote:
                escalation = {"kind": "stalled_same_quote", "rounds_run": inspect_used,
                              "unresolved": ["质检连续两轮指向同一段文字仍然被拒：{}".format(
                                  stalled_quote)]}
                comp = ins
                break
            rulings_summary["inspect_rework"] += 1
            cur, eff, strikes = _apply_inspection_feedback(
                a, brief, card, digest, sections, cur, ins, target_chars, chapters, spc,
                outdir, state, tracker, usages, log, self_checks, terms_by_id, strikes,
                inspect_used)
            if strikes > MAX_NO_CHANGE_STRIKES:
                escalation = {"kind": "no_effective_change", "rounds_run": inspect_used,
                              "unresolved": ["讲师连续 {} 轮修订没有实质改动：{}".format(
                                  strikes, eff.get("why") or "")]}
                comp = ins
                break
            round_runs.append({"round": inspect_used, "inspect_verdict": "send_back"})
        if comp is None:
            comp = ins
    else:
        round_runs = []

    return _finish_run(a, outdir, log, escalation, deck, brief, card, target_chars,
                       chapters, spc, max_pages, rounds, usages, tracker,
                       rulings_summary, lectures, comp, all_sections, round_runs)


def _write_lecture_dir(outdir, _unused, lec, sc, model, usage, elapsed, terms):
    p = Path(outdir) / "lectures"
    p.mkdir(parents=True, exist_ok=True)
    (p / "{}.md".format(lec["id"])).write_text(
        render_lecture_md(lec, sc, model, usage, elapsed, terms) + "\n", encoding="utf-8")


def _write_deck_dir(outdir, round_no, deck, model, usage, elapsed):
    p = Path(outdir) / "slides"
    p.mkdir(parents=True, exist_ok=True)
    (p / "deck.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    (p / "deck-r{}.md".format(round_no)).write_text(
        render_deck_md(deck, model, usage, elapsed, round_no) + "\n", encoding="utf-8")


def _write_inspect_dir(outdir, round_no, ins, gates, model, usage, elapsed):
    p = Path(outdir) / "inspect"
    p.mkdir(parents=True, exist_ok=True)
    (p / "inspection-r{}.md".format(round_no)).write_text(
        render_inspection_md(ins, model, usage, elapsed, round_no, gates) + "\n",
        encoding="utf-8")
    (p / "inspection-r{}.json".format(round_no)).write_text(
        json.dumps({"inspection": ins, "course_gates": gates},
                   ensure_ascii=False, indent=1), encoding="utf-8")


def _replace_lecture(lectures, sec_id, new_text, new_title=None):
    """把某一节的讲义正文换掉（保序）。返回新的 lectures 列表。"""
    out = []
    for lec in lectures:
        if str(lec.get("id")) == str(sec_id):
            upd = dict(lec)
            upd["text"] = new_text
            if new_title:
                upd["title"] = new_title
            out.append(upd)
        else:
            out.append(lec)
    return out


def _apply_slide_feedback(a, brief, card, digest, sections, lectures, deck, target_chars,
                          chapters, spc, outdir, state, tracker, usages, log,
                          self_checks, terms_by_id):
    """课件说放不下 → 只让讲师改**被点到的那几节**。返回 None 或一个 escalation。"""
    by_id = {str(l.get("id")): l for l in lectures}
    touched = []
    for it in deck.get("issues") or []:
        sid = resolve_issue_section(it, sections, deck.get("pages"))
        if sid and sid in by_id and sid not in touched:
            touched.append(sid)
    if not touched and deck.get("issues"):
        # 连三级回退都定位不到：把所有节都改一遍代价太大，如实报出来（不假装改过）
        return {"kind": "slide_rework_exhausted", "rounds_run": 1,
                "unresolved": ["课件说放不下，但 {} 条诉求通过「节 id → 页 id → 引文锚点」"
                               "三级回退都定位不到具体的节 —— 无法派工给讲师：{}".format(
                                   len(deck["issues"]),
                                   "；".join((i.get("why") or "")[:60]
                                             for i in deck["issues"][:3]))]}
    for sid in touched:
        lec = by_id[sid]
        sec = next((s for s in sections if str(s.get("id")) == sid), None) or \
            {"id": sid, "unit_id": lec.get("unit_id"), "title": lec.get("title"),
             "unit_index": 0, "section_index": 0}
        issues = [i for i in deck["issues"]
                  if resolve_issue_section(i, sections, deck.get("pages")) == sid]
        prompt = build_slide_revise_prompt(brief, digest, sec, lec.get("text") or "",
                                           issues, target_chars)
        obj, usage, elapsed, iso, pchars = _role_call(
            "instructor", prompt, a.model, a.key, tracker, a,
            "按课件反馈改写讲义 {}".format(sid),
            int(target_chars * TOKENS_PER_CHAR_OUT))
        usages.append(usage)
        log_isolation(log, "instructor", iso, pchars, len(log["entries"]))
        new_lec, new_sc, _terms = normalize_lecture(obj, sec)
        fix_lines = [f for f in (obj.get("fixes") or []) if isinstance(f, dict)]
        eff = revision_effective(lec.get("text") or "", new_lec["text"], len(issues),
                                 len(fix_lines))
        # **本地复核**：改完之后这一节的字数是不是真的收下来了
        before_chars, after_chars = char_count(lec.get("text")), char_count(new_lec["text"])
        log_entry(log, "revise", "讲师", len(log["entries"]), "按课件「放不下」清单改写",
                  "{} {} → {} 字符；自报修 {} 条（点名 {} 条）；正文相似度 {:.2f}；{}".format(
                      sid, before_chars, after_chars, len(fix_lines), len(issues),
                      eff["body_sim"],
                      "**判为没有实质改动**：" + eff["why"] if not eff["effective"]
                      else "有实质改动"))
        self_checks[sid] = new_sc
        lectures = _replace_lecture(lectures, sid, new_lec["text"], new_lec.get("title"))
        # 就地更新 by_id，后面的节看到的是改过的版本
        by_id[sid] = new_lec
    return None


def _apply_inspection_feedback(a, brief, card, digest, sections, lectures, ins,
                               target_chars, chapters, spc, outdir, state, tracker,
                               usages, log, self_checks, terms_by_id, strikes, round_no):
    """质检打回 → 只让讲师改**被点名的那几节**。返回 (新 lectures, 效果, strikes)。"""
    by_id = {str(l.get("id")): l for l in lectures}
    must = [it for it in ins["issues"] if it["id"] in ins["must_fix"]] or ins["issues"]
    touched = []
    for it in must:
        sid = resolve_issue_section(it, sections, None)
        if sid and sid in by_id and sid not in touched:
            touched.append(sid)
    if not touched:
        # 引文锚定成功但节号缺失（全课程模糊命中）→ 退化为全部节都改一遍太重，
        # 这里只报出来让人看（显式，不假装改过）
        log_entry(log, "revise", "讲师", round_no, "无法派工",
                  "质检打回，但没有一条问题能定位到具体的节 —— 未派工给讲师")
        return lectures, {"effective": False, "why": "无法定位到节"}, strikes + 1
    total_eff = {"effective": True, "why": ""}
    for sid in touched:
        lec = by_id[sid]
        sec = next((s for s in sections if str(s.get("id")) == sid), None) or \
            {"id": sid, "unit_id": lec.get("unit_id"), "title": lec.get("title"),
             "unit_index": 0, "section_index": 0}
        issues = [i for i in must if resolve_issue_section(i, sections, None) == sid]
        prompt = build_inspect_revise_prompt(brief, digest, sec, lec.get("text") or "",
                                             issues, target_chars)
        obj, usage, elapsed, iso, pchars = _role_call(
            "instructor", prompt, a.model, a.key, tracker, a,
            "按质检意见改写讲义 {}".format(sid),
            int(target_chars * TOKENS_PER_CHAR_OUT))
        usages.append(usage)
        log_isolation(log, "instructor", iso, pchars, round_no)
        new_lec, new_sc, _terms = normalize_lecture(obj, sec)
        fix_lines = obj.get("fixes") or []
        eff = revision_effective(lec.get("text") or "", new_lec["text"], len(issues),
                                 len(fix_lines))
        log_entry(log, "revise", "讲师", round_no, "按质检必须修清单修订",
                  "{} {} → {} 字符；自报修 {} 条（点名 {} 条）；正文相似度 {:.2f}；{}".format(
                      sid, char_count(lec.get("text")), char_count(new_lec["text"]),
                      len(fix_lines), len(issues), eff["body_sim"],
                      "**判为没有实质改动**：" + eff["why"] if not eff["effective"]
                      else "有实质改动"),
                  [f.get("before") for f in fix_lines[:2] if isinstance(f, dict)
                   and f.get("before")])
        self_checks[sid] = new_sc
        lectures = _replace_lecture(lectures, sid, new_lec["text"], new_lec.get("title"))
        if not eff["effective"] and total_eff["effective"]:
            total_eff = eff
    return lectures, total_eff, (strikes + 1 if not total_eff["effective"] else 0)


def build_inspect_revise_prompt(brief, digest, section, text, issues, target_chars):
    """讲师按质检的必须修清单改某一节。**只拿到锚定过的、可执行的那几条。**"""
    lines = []
    for it in issues:
        lines.append("  {}. [{}] 节 {} / 第 {} 句\n     引用的原句：{}\n"
                     "     问题：{}\n     建议改法：{}".format(
                         it.get("id") or "-",
                         "/".join(it.get("dims") or ["-"]),
                         it.get("section") or "-", it.get("sent_no") or "-",
                         it.get("sentence") or it.get("quote") or "",
                         it.get("why") or "-", it.get("fix") or "-"))
    issue_block = "\n".join(lines) if lines else "  （无：本轮没有被点名的问题）"
    return (
        "这是质检打回后的修订。请照下面的**必须修清单**改这一节。\n"
        + "\n课程设计卡（不许改它定的目标）：\n" + _digest_block(digest, full=True)
        + "\n本节：{}「{}」\n".format(section.get("id"), section.get("title"))
        + "\n修改纪律（违反就整份作废）：\n"
          "  1. **只改清单点到的地方**。清单没点到的句子，除非与改动直接相邻，一个字都别动。\n"
          "  2. 不许改课程目标、不许删掉目标覆盖的知识点。\n"
          "  3. 本节第一次出现的术语必须在同一句里解释掉；不许留下没讲过的术语。\n"
          "  4. 篇幅目标约 {n} 字符；改完仍要满足四段结构。\n".format(n=target_chars)
        + "  5. 不许把清单里的编号、字段名、本提示词的词句写进正文；"
          "不许输出 Markdown 代码围栏或占位符。\n"
        + "\n===== 必须修清单（本地已逐条锚定到讲义里的句子）=====\n" + issue_block
        + _json_req({
            "section_id": "本节 id（原样抄回来）",
            "text": "修订后的完整讲义正文",
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
        + "\n补充要求：`fixes` 覆盖你**实际做过**的每一处修改。**不要为了凑数编改动。**\n"
        + "\n===== 当前讲义开始 =====\n" + (text or "") + "\n===== 当前讲义结束 =====\n"
        + "\n===== 用户材料开始 =====\n" + (brief or "") + "\n===== 用户材料结束 =====\n"
    )


def _finish_run(a, outdir, log, escalation, deck, brief, card, target_chars, chapters, spc,
                max_pages, rounds, usages, tracker, rulings_summary, lectures, comp,
                all_sections, round_runs):
    """收口：跑定稿的硬闸门、写全部产物、决定退出码。"""
    lectures = lectures or []
    sections = sections_from_lectures(lectures)
    final_text = "\n\n".join(
        "## {} {}\n\n{}".format(l.get("id"), l.get("title") or "", l.get("text") or "")
        for l in lectures)
    course_gates = evaluate_course_gates(card, sections)
    # 文本闸门（合规 / 占位符 / 照抄示例）走与 `inspect` **同一份实现**：
    # 讲义正文（产出侧，带警告语境豁免）+ 课件方案文字
    gates = scan_lecture_text(lectures, produce_side=True)
    # 用户材料单独扫一遍：**材料侧不走警告语境豁免**
    brief_hits, brief_exempted = compliance_scan(brief, produce_side=False)
    gates["compliance_material"] = {
        "ok": not brief_hits, "hits": brief_hits, "exempted": brief_exempted,
        "side": "材料侧（**不走警告语境豁免**：用户材料里写了就拦）",
    }
    # 课程特有的三道闸门
    gates["objectives"] = course_gates["objectives"]
    gates["prerequisites"] = course_gates["prerequisites"]
    gates["terminology"] = course_gates["terminology"]
    # 质检锚点
    gates["anchor"] = ((comp or {}).get("anchor") if isinstance(comp, dict)
                       else {"ok": True, "total": 0, "verified": 0, "unanchored": 0,
                             "miss_rate": 0.0, "rules": {}})
    # 课件放不下也算一条硬闸门（产出不完整）
    gates["slide_fit"] = {
        "ok": bool(deck and deck.get("verdict") == "fits"),
        "why": ((deck or {}).get("local_check") or {}).get("why") or "（没有课件方案）",
        "cannot_fit": len((deck or {}).get("issues") or []),
    }
    run_gate_keys = tuple(HARD_GATE_KEYS) + ("compliance_material", "slide_fit")
    failed_keys = [k for k in run_gate_keys
                   if isinstance(gates.get(k), dict) and not gates[k].get("ok", True)]
    # 裁决完整性（**不许假装谈拢**）
    ruling_chk = check_ruling_completeness(log)
    gates["ruling_completeness"] = ruling_chk
    if not ruling_chk["ok"]:
        failed_keys = list(failed_keys) + ["ruling_completeness"]
    converged = bool(
        escalation is None
        and isinstance(comp, dict)
        and comp.get("verdict") in ("pass", "fix")
        and comp.get("anchor", {}).get("ok", True)
        and not failed_keys)
    if escalation is None and not converged:
        escalation = {"kind": "rounds_exhausted",
                      "rounds_run": len(round_runs) or 1,
                      "unresolved": ["硬闸门未全过：{}".format(
                          "、".join(failed_keys) or "无")]}
    why = ("全流程走通：课件 {} 页全部放得下，质检 {}，硬闸门全过。".format(
        len((deck or {}).get("pages") or []), (comp or {}).get("verdict"))
        if converged else
        "**未收敛**（出口：{}）。{}".format(
            (escalation or {}).get("kind"),
            EXIT_KIND.get((escalation or {}).get("kind"), "")))
    convergence = {"converged": converged, "why": why,
                   "exit_kind": (escalation or {}).get("kind"),
                   "unresolved": (escalation or {}).get("unresolved") or []}

    iso_all = log["isolation"]
    asym = {
        "verified_calls": len(iso_all),
        "all_ok": all(x["ok"] for x in iso_all),
        "self_check_excluded_from_slides": (
            all("self_check" in x["excluded_fields"] for x in iso_all
                if x["stage"] == "slides")
            if any(x["stage"] == "slides" for x in iso_all) else None),
        "self_check_and_slide_issues_excluded_from_inspector": (
            all("self_check" in x["excluded_fields"]
                and "slide_issues" in x["excluded_fields"]
                for x in iso_all if x["stage"] == "inspector")
            if any(x["stage"] == "inspector" for x in iso_all) else None),
        "note": "每次调用前对**真实提示词文本**扫标记词；泄漏会当场中止调用（退出码 3），"
                "所以 all_ok 为真意味着这些调用确实在信息不对称下发生。",
    }
    # 互审是否真的发生（一张可复核的账）
    interlock = {
        "designer_rejected_design": rulings_summary.get("designer_reject", 0),
        "slides_said_cannot_fit": rulings_summary.get("slides_cannot_fit", 0),
        "inspector_send_back": rulings_summary.get("inspector_send_back", 0),
        "inspector_veto": rulings_summary.get("inspector_veto", 0),
        "notes": ["课件说「放不下」会把讲师打回去改写讲义：{} 次".format(
                      rulings_summary.get("slide_rework", 0)),
                  "质检打回会让讲师按必须修清单修订：{} 次".format(
                      rulings_summary.get("inspect_rework", 0))],
        "fake_collab_warning": (
            "如果上面四个数全是 0，说明课件次次说放得下、质检条条放行 —— "
            "**那就是假协作**（各写各的，没有互相否过）。请自己判断这次是不是这种情况。"),
    }
    result = {
        "mode": "run", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "ruling_version": RULING_VERSION,
        "model": a.model, "target_chars": target_chars,
        "chapters": chapters, "sections_per_chapter": spc, "max_pages": max_pages,
        "rounds": rounds, "rounds_run": len(round_runs),
        "design_retries": a.design_retries, "slide_rework": a.slide_rework,
        "inspect_rework": a.inspect_rework,
        "brief": {"path": str(a.brief), "sha": text_sha(brief), "chars": char_count(brief)},
        "card": card,
        "sections_planned": len(all_sections or []),
        "sections_written": len(lectures),
        "roles": {k: {"name": ROLES[k]["name"], "veto": ROLES[k]["veto"],
                      "forbidden": ROLES[k]["forbidden"]} for k in ROLE_ORDER},
        "lectures": lectures,
        "deck": deck,
        "inspection": comp,
        "convergence": convergence, "escalation": escalation,
        "rulings_summary": rulings_summary,
        "gates": gates, "gate_failed": bool(failed_keys), "gate_failed_keys": failed_keys,
        "information_asymmetry": asym,
        "interlock": interlock,
        "log": log, "log_entries": len(log["entries"]),
        "rounds_detail": round_runs,
        "usage": _sum_usage(usages),
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
        "ok_bool": converged,
    }

    # ---------------- 写产物 ----------------
    (outdir / "final.md").write_text(final_text + "\n", encoding="utf-8")
    (outdir / "final.json").write_text(json.dumps({
        "brief": result["brief"], "card": card, "lectures": lectures, "deck": deck,
        "inspection": comp, "convergence": convergence,
        "gates": gates, "interlock": interlock,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    (outdir / "REPORT.md").write_text(
        render_report_md(log, escalation, convergence, gates, final_text, result["cost"],
                         {"objectives": gates.get("objectives") or {},
                          "prerequisites": gates.get("prerequisites") or {},
                          "terminology": gates.get("terminology") or {}}) + "\n",
        encoding="utf-8")
    if card:
        (outdir / "design.json").write_text(
            json.dumps({"card": card}, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / "lectures.json").write_text(
        json.dumps({"lectures": lectures}, ensure_ascii=False, indent=1), encoding="utf-8")
    if deck:
        (outdir / "deck.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1),
                                          encoding="utf-8")

    sys.stderr.write("\n{}\n".format(tracker.line()))
    _gate_stderr("整门课", gates)
    if interlock["slides_said_cannot_fit"] == 0 and interlock["inspector_send_back"] == 0 \
            and interlock["inspector_veto"] == 0 and interlock["designer_rejected_design"] == 0:
        sys.stderr.write("\n{}\n".format(_red(
            "注意：本次运行里**没有任何一次否决或打回** —— "
            "课件没有说放不下、质检没有打回、教研没有重开设计。"
            "这可能是产出真的干净，也可能是各写各的（假协作）。"
            "请自己看 REPORT.md 的裁决记录再下结论。")))
    if escalation:
        sys.stderr.write("\n{}\n".format(_red(
            "未收敛，出口 = {}：{}".format(
                escalation["kind"], EXIT_KIND.get(escalation["kind"], "")))))
        for u in escalation.get("unresolved") or []:
            sys.stderr.write("   · {}\n".format(u))
    else:
        sys.stderr.write("收敛：课件逐页放得下 + 质检 {} + 硬闸门全过。\n".format(
            (comp or {}).get("verdict")))
    sys.stderr.write("目录产物：{}（final.md / final.json / REPORT.md / log.json / "
                     "design.json / lectures.json / deck.json / lectures/ / slides/ / "
                     "inspect/ / state.json）\n".format(outdir))

    md = render_report_md(log, escalation, convergence, gates, final_text, result["cost"],
                          {"objectives": gates.get("objectives") or {},
                           "prerequisites": gates.get("prerequisites") or {},
                           "terminology": gates.get("terminology") or {}})
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
    rulings = log.get("rulings") or []
    slide_rulings = log.get("slide_rulings") or []
    vetoes = [r for r in rulings if r["decision"] in
              ("veto", "rejected", "send_back", "ineffective", "auto_fix_failed")]
    cannot_fit = [r for r in slide_rulings if r["decision"] == "cannot_fit"]
    ruling_chk = check_ruling_completeness(log)
    result = {
        "mode": "log", "outdir": str(outdir),
        "entries": len(log.get("entries") or []), "rulings": len(rulings),
        "slide_rulings": len(slide_rulings),
        "vetoes_or_rejections": len(vetoes) + len(cannot_fit),
        "by_decision": _count_by(rulings, "decision"),
        "by_slide_decision": _count_by(slide_rulings, "decision"),
        "by_role": _count_by(rulings, "role"),
        "ruling_completeness": ruling_chk,
        "isolation": log.get("isolation") or [],
        "final_chars": char_count(final_text),
        "final_preview": final_text[:400],
        "log": log,
        "report_path": str(repf) if repf.is_file() else None,
        "answer": ("这份记录里 {} 条裁决（含课件侧 {} 条）中有 {} 条是否决 / 打回类决定 —— "
                   "如果这个数是 0，说明多角色互审没有真的发生（各写各的）。".format(
                       len(rulings), len(slide_rulings), len(vetoes) + len(cannot_fit))),
    }
    if a.json:
        _json_out(result, a, indent=2)
        return EXIT_OK
    out = ["# 全过程记录：{}".format(outdir), ""]
    out.append("- 动作流水 {} 条 · 裁决 {} 条（其中课件侧 {} 条）· 否决/打回 {} 条".format(
        result["entries"], result["rulings"], result["slide_rulings"],
        result["vetoes_or_rejections"]))
    out.append("- 裁决分布：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in result["by_decision"].items()) or "（无）"))
    out.append("- 课件侧裁决：{}".format(
        "、".join("{}×{}".format(k, v) for k, v in result["by_slide_decision"].items())
        or "（无）"))
    out.append("- 裁决完整性：{}".format(ruling_chk["why"]))
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
    chapters = check_positive("--chapters", a.chapters, allow_zero=False)
    spc = check_positive("--sections-per-chapter", a.sections_per_chapter, allow_zero=False)
    design_retries = check_positive("--design-retries", a.design_retries)
    slide_rework = check_positive("--slide-rework", a.slide_rework)
    inspect_rework = check_positive("--inspect-rework", a.inspect_rework)
    total_sections = chapters * spc
    eff_sections = min(total_sections, check_sections_count(a.sections)
                       if a.sections else total_sections)
    calls = estimate_calls(len(text), eff_sections, target_chars, a.max_pages,
                           design_retries, slide_rework, inspect_rework)
    tin = sum(c["tokens_in"] for c in calls)
    tout = sum(c["tokens_out"] for c in calls)
    total_calls = sum(c["calls"] for c in calls)
    rec = compute_cost(tin, tout, a.price_in, a.price_out)
    rep = {
        "mode": "cost", "target_chars": target_chars,
        "chapters": chapters, "sections_per_chapter": spc,
        "sections": eff_sections, "sections_planned": total_sections,
        "max_pages": a.max_pages,
        "design_retries": design_retries, "slide_rework": slide_rework,
        "inspect_rework": inspect_rework,
        "brief_chars": len(text or ""), "total_calls": total_calls,
        "calls": calls,
        "tokens_in": tin, "tokens_out": tout,
        "chars_per_token_in": CHARS_PER_TOKEN_IN,
        "tokens_per_char_out": TOKENS_PER_CHAR_OUT,
        "points_per_yuan": POINTS_PER_YUAN,
        "cost": rec,
        "note": "这是**估算，不是账单**：字符→token 的比值来自同族实测标定，"
                "不是厂商文档。真实扣费以账户流水为准。按**最坏情况**估"
                "（含设计重开、课件重做、质检打回各一次的上界）。"
                "**本包只出 token：文本模型网关不公布单价，不编价。**",
    }
    out = ["# 课程协作成本估算", ""]
    out.append("- 材料：{} 字符　单节篇幅：{} 字符　规模：{} 单元 × {} 节 = {} 节".format(
        len(text or ""), target_chars, chapters, spc, total_sections))
    if eff_sections != total_sections:
        out.append("- **本次只按 {} 节估**（--sections 限制；不是静默截断）".format(eff_sections))
    out.append("- 页数上限：{}　设计重开上限：{}　课件重做上限：{}　质检打回上限：{}".format(
        a.max_pages, design_retries, slide_rework, inspect_rework))
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
        # 同样要说清单位：--budget 是元，points 是点数
        if rec["points"] > float(a.budget) * POINTS_PER_YUAN:
            rc = EXIT_BUDGET
            sys.stderr.write("\n{}\n".format(_red(
                "预算闸门：预估 {:g} 点（≈ ¥{:g}）超过 --budget ¥{:g}，"
                "run 会在发起调用前停下".format(
                    rec["points"], rec["points"] / POINTS_PER_YUAN, a.budget))))
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
        p.add_argument("--out", help="把结果写到这个文件（**必须在包外**）")
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
                   help="预算上限（**元**）。超了就地中止，退出码 5；"
                        "**用 --budget 必须给单价**，否则退出码 2")


def _add_course_opts(p, brief_required=True):
    p.add_argument("--brief", required=brief_required,
                   help="用户材料（.md / .txt，UTF-8）：这一个主题的来源 + 事实基准")
    p.add_argument("--chapters", type=int, default=DEFAULT_CHAPTERS,
                   help="单元数，默认 {}".format(DEFAULT_CHAPTERS))
    p.add_argument("--sections-per-chapter", type=int,
                   default=DEFAULT_SECTIONS_PER_CHAPTER, dest="sections_per_chapter",
                   help="每单元几节，默认 {}".format(DEFAULT_SECTIONS_PER_CHAPTER))
    p.add_argument("--target-chars", type=int, default=DEFAULT_TARGET_CHARS,
                   dest="target_chars",
                   help="**单节讲义**的目标字符数（不含空白），默认 {}".format(
                       DEFAULT_TARGET_CHARS))
    p.add_argument("--sections", type=int, default=None,
                   help="最多写前几节（一节一次调用，上限 {}）".format(MAX_SECTIONS))
    p.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, dest="max_pages",
                   help="逐页课件方案的目标页数上限，默认 {}".format(DEFAULT_MAX_PAGES))


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
        description="三剪客 · 课程教研组 —— L3 多智能体协作开一门课"
                    "（教研 / 讲师 / 课件 / 质检，走 api.a7w.cn 的 OpenAI 兼容端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    # 每个子命令的 parser 也必须关掉缩写：argparse 的缩写开关是**每个 parser 各自**的
    # 属性，只在父级设一遍不够（子 parser 是另造的实例，默认仍然允许缩写）。
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("roles", help="列出四个角色的职权、产出物与否决权（零成本）")
    _add_json(p)
    p.add_argument("--out", help="把职权表写到这个文件（**必须在包外**）")
    p.set_defaults(func=run_roles)

    p = sub.add_parser("design", help="教研出课程设计卡（不达标会自动重开）")
    _add_course_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--design-retries", type=int, default=1, dest="design_retries",
                   help="设计卡不达标时最多重开几次，默认 1（合计最多试 2 次）")
    p.add_argument("--outdir", help="目录产物落这里（**必须在包外**）：design.json / design.md")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")
    p.set_defaults(func=run_design)

    p = sub.add_parser("lecture", help="讲师按设计卡写逐节讲义（附自评；自评不进下游）")
    _add_course_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--design", required=True, help="课程设计卡 JSON（design --json --out 的产物）")
    p.add_argument("--outdir", help="目录产物落这里（**必须在包外**）")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")
    p.set_defaults(func=run_lecture)

    p = sub.add_parser("slides", help="课件出逐页方案，**能说「这页放不下」**")
    _add_course_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--design", required=True, help="课程设计卡 JSON")
    p.add_argument("--lectures", required=True, help="讲义 JSON（lecture --json --out 的产物）")
    p.add_argument("--outdir", help="目录产物落这里（**必须在包外**）")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")
    p.set_defaults(func=run_slides)

    p = sub.add_parser("inspect", help="质检出问题清单（引用讲义原句）+ 风险裁决，**能否决**")
    _add_course_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--design", required=True, help="课程设计卡 JSON")
    p.add_argument("--lectures", required=True, help="讲义 JSON")
    p.add_argument("--outdir", help="目录产物落这里（**必须在包外**）")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")
    p.set_defaults(func=run_inspect)

    p = sub.add_parser("run", help="一条命令出整门课：带裁决、轮次上限与明确出口")
    _add_course_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--design-retries", type=int, default=1, dest="design_retries",
                   help="设计卡不达标时最多重开几次，默认 1")
    p.add_argument("--slide-rework", type=int, default=1, dest="slide_rework",
                   help="课件说「放不下」后最多让讲师重做几次，默认 1")
    p.add_argument("--inspect-rework", type=int, default=1, dest="inspect_rework",
                   help="质检打回后最多让讲师改几次，默认 1")
    p.add_argument("--rounds", type=int, default=2,
                   help="质检↔讲师修订的总轮次上限，默认 2（至少 1）")
    p.add_argument("--outdir",
                   default=str(Path(os.environ.get("TEMP") or ".") / "course-crew-out"),
                   help="目录产物落这里（**必须在包外**）：final.md / REPORT.md / "
                        "log.json / design.json / lectures.json / deck.json / "
                        "lectures/ / slides/ / inspect/ / state.json")
    p.add_argument("--force", action="store_true",
                   help="忽略断点文件，从头重跑（key 没命中就会重新花钱）")
    p.set_defaults(func=run_run)

    p = sub.add_parser("log", help="读回全过程记录：谁在第几轮否掉了什么、引用哪句原话")
    p.add_argument("--outdir", required=True, help="run 的 --outdir")
    _add_json(p)
    p.set_defaults(func=run_log)

    p = sub.add_parser("cost", help="报价：一次协作大概花多少 token（金额要你填单价）")
    p.add_argument("--file", help="按这份材料估")
    p.add_argument("--text", help="或直接给文本")
    _add_course_opts(p, brief_required=False)
    _add_cost_opts(p)
    p.add_argument("--design-retries", type=int, default=1, dest="design_retries",
                   help="按最多重开几次估，默认 1")
    p.add_argument("--slide-rework", type=int, default=1, dest="slide_rework",
                   help="按课件最多重做几次估，默认 1")
    p.add_argument("--inspect-rework", type=int, default=1, dest="inspect_rework",
                   help="按质检最多打回几次估，默认 1")
    _add_json(p)
    p.add_argument("--out", help="把报价写到这个文件（**必须在包外**）")
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
                 ("price_out", None), ("force", False), ("brief", None),
                 ("chapters", DEFAULT_CHAPTERS),
                 ("sections_per_chapter", DEFAULT_SECTIONS_PER_CHAPTER),
                 ("target_chars", DEFAULT_TARGET_CHARS), ("sections", None),
                 ("max_pages", DEFAULT_MAX_PAGES), ("design", None), ("lectures", None),
                 ("design_retries", 1), ("slide_rework", 1), ("inspect_rework", 1),
                 ("rounds", 0), ("outdir", None), ("file", None), ("text", None),
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
    except CcError as exc:
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


def _emit_dry(a, stage, payload):
    if a.json:
        _json_out({"dry_run": True, "stage": stage, "prompt": payload}, a, indent=2)
    else:
        print(payload)


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
