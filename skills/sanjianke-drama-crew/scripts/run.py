#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 短剧剧组（sanjianke-drama-crew）—— **L3 多智能体协作型**。

一条命令跑完一个剧组：**编剧 → 导演 → 美术 → 场记**，四个角色各有自己的目标与职权，
**导演能打回编剧、美术能说"这场拍不出来"、场记能否决（连续性错误必须修）**。

L1 = 一个输入一个产出；L2 = 一个声音自己抽档→写→自检→迭代；
L3 = **多角色分工互审**，一条命令出成品。本包是 L3。

本包**不出片、不出图**。产物是**剧本 + 分镜包**：
    剧本（scenes/台词/情绪）+ 分镜表（景别/机位/时长/转场）+ 美术设定卡（文本）
    + 矛盾清单（每条引用剧本原文）+ 全过程记录（含每次打回与否决）

出图与出片是既有包的活（`sanjianke-storyboard-art` 出图、`sanjianke-drama-engine` 出片）。

子命令
    crew        列出四个角色与职权（**零成本**，一次调用都不发）
    outline     编剧出分集大纲（钩子 / 卡点 / 集尾悬念）
    script      编剧出剧本（场景 / 台词 / 情绪）
    board       导演出分镜表（景别 / 机位 / 时长 / 转场）—— **可以打回编剧**
    art         美术出场景与角色视觉设定卡（文本）—— **可以说"这场拍不出来"**
    continuity  场记出矛盾清单（**每条必须引用剧本原文**）
    run         一条命令跑完剧组协作（多轮，含打回重写）
    log         读全过程记录（每一轮的产出、打回、否决、未决项、token）
    cost        只算钱，一次调用都不发
    models      现查 api.a7w.cn 在架模型

真实端点（都在 api.a7w.cn 上）
    文本        POST https://api.a7w.cn/api/v1/chat/completions   ← **成功响应不带 code**
    模型清单    GET  https://api.a7w.cn/api/v1/models
本包只用这两个端点：**不出图、不出片、不碰生成应用**。

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 scripts/run.py crew --key <你的Key>            （crew 不需要 Key）
    Windows PowerShell:  $env:A7W_API_KEY="<你的Key>"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json

八道本地硬闸门（都是**拦截**：标红 + stderr 汇总 + 退出码非 0，不是"提示一下"）
    1. 合规         广告法违禁词 + 短剧常见风险（血腥/软色情/赌博/迷信的表述边界）
    2. 占位符残留   `{}`、`[待填]`、`XXX`
    3. prompt_echo  照抄提示词示例：去标点相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60
                    （含**相对长度守卫**与 **contain 适用窗口**，见 ECHO_CONTAIN_MARGIN）
    4. 矛盾清单锚点 每条矛盾**必须引用剧本原文**；本地校验锚点，编造引文剔出
    5. 分镜结构     每镜必须有**景别 + 画面描述 + 时长**；缺项标红；镜数为 0 → 拦
    6. 角色一致性   同一角色在**剧本**与**美术设定卡**里的硬项必须一致
    7. 裁决完整性   打回/否决必须留可读理由；**不许假装谈拢**
    8. 成本上限 + 产出位置  `--outdir` 在包内 → exit=2

设计取舍
    · **信息不对称是本包的机制，不是 bug**：编剧看不到导演的偏好与"拍不了"的清单，
      导演也看不到美术的产能约束。这不是省 token，是让四个角色**真的各有立场**。
      每个角色的输入摘要会打印出来（`--show-inputs`），用来证明不对称真实存在。
    · 闸门读的是**渲染后的成品文本**（剧本 Markdown / 分镜表 / 设定卡 / 矛盾清单），
      不采信模型自报的结构字段——吃过"只信自报值、闸门成假绿"的亏。
    · **不许假装谈拢**：轮次用完仍未达成一致时，显式列未决项并以 exit=6 报出分歧。
    · 结算只认 `usage.total_tokens`。**文本网关不公布单价 → 只出 token，不编价。**

用法示例
    python3 scripts/run.py crew
    python3 scripts/run.py run --topic "外卖骑手穿越成财阀私生子" --episodes 2 \\
            --outdir %TEMP%\\drama-crew/ep01 --max-rounds 2 --yes
    python3 scripts/run.py log --outdir %TEMP%\\drama-crew/ep01
    python3 scripts/run.py cost --episodes 2 --max-rounds 2
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

# 不许在包里留下 __pycache__：本库的包要过 SkillHub 的文件类型白名单，
# 一个 .pyc 就会让整包被拒。放在 import a7w 之前，连 a7w 的缓存也一起关掉。
sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402  ← 共用零依赖客户端；**逐字节等于规范版，本包不改它**

# 控制台统一按 UTF-8 输出：Windows 代码页会把中文打成乱码，
# 而且 `--json` 的产物要能被 json.loads 直接吃。
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 包根目录：scripts/ 的上一级。`--outdir` 落在这里面就是违规（包内不许有产出）。
PKG_ROOT = Path(__file__).resolve().parent.parent

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash 一线。它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

STATE_NAME = "crew-state.json"
LOG_NAME = "crew-log.md"

SCRIPT_JSON = "script.json"
SCRIPT_MD = "script.md"
OUTLINE_JSON = "outline.json"
OUTLINE_MD = "outline.md"
BOARD_JSON = "board.json"
BOARD_MD = "board.md"
ART_JSON = "art.json"
ART_MD = "art.md"
CONTINUITY_JSON = "continuity.json"
CONTINUITY_MD = "continuity.md"
REPORT_JSON = "run-report.json"
REPORT_MD = "run-report.md"

# 退出码（可直接用于 CI）
EXIT_OK = 0            # 一致通过
EXIT_INTERNAL = 1      # 未捕获异常（--json 下给 kind:"internal" 信封）
EXIT_USAGE = 2         # 参数/配置/环境错误（--outdir 指到包内、没报价就开跑）
EXIT_GATE = 3          # 有硬闸门命中（合规 / 占位符 / 照抄示例 / 分镜结构 / 一致性 / 裁决）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 成本上限，已就地中止
EXIT_UNRESOLVED = 6    # 轮次用完仍有未决项（**分歧如实报出，不许假装谈拢**）
EXIT_INTERRUPT = 130   # 用户中断

# 平台计费口径：1 元 = 100 点（平台公开口径，1 点 = 0.01 元）。
# ⚠️ 这只是**换算**，不是单价。文本网关的单价平台不公开 → 本包不报金额、只报 token。
POINTS_PER_YUAN = 100.0


# ---------------------------------------------------------------------------
# 剧组规格表（**唯一事实来源**）
#
# 为什么做成表：轮次上限、镜头时长、集数这些数字会变，而且提示词、闸门、
# 成本估算三处都要用同一个数。放一张表里，改口径只改这里，逻辑不动。
# ---------------------------------------------------------------------------

CREW = {
    "max_rounds": 2,          # 默认最多两轮（一轮初稿 + 一轮返修）
    "hard_max_rounds": 4,     # 上限：再多轮就是谈不拢了，该报未决项而不是继续烧钱
    "episodes": 2,            # 默认出几集
    "hard_max_episodes": 12,
    "scenes_per_episode": (3, 6),
    "shots_per_scene": (3, 8),
    "shot_seconds": (2, 12),  # 单镜时长区间（秒）；短剧单镜普遍 2~12 秒
    "episode_seconds": (60, 120),
    "default_budget": 5000.0,  # 点（= 50 元）：两轮十次文本调用的安全上限
}

# 角色卡：**四个角色各自的目标、产出物、职权**。这是 L3 的核心定义。
# 为什么把"否决权"写成数据而不是写进提示词：闸门七要按它判"谁的话必须被听"。
ROLES = {
    "writer": {
        "cn": "编剧",
        "goal": "故事好不好看、钩子够不够",
        "artifact": "分集大纲 + 剧本（场景/台词/情绪）",
        "power": [],                       # 无否决权
        "power_cn": "无否决权",
        "must_not": [
            "不评价这场戏能不能拍出来（那是导演的职权）",
            "不管场景与服化道能不能产出（那是美术的职权）",
            "不核对前后是否矛盾（那是场记的职权）",
        ],
    },
    "director": {
        "cn": "导演",
        "goal": "节奏与可视化：这场戏能不能拍出来",
        "artifact": "分镜表（景别/机位/时长/转场）",
        "power": ["reject_writer"],        # 能打回编剧
        "power_cn": "能打回编剧（「这场写不了」）",
        "must_not": [
            "不改故事走向与人物关系（那是编剧的职权）",
            "不管服化道能不能做出来（那是美术的职权）",
        ],
    },
    "art": {
        "cn": "美术",
        "goal": "场景/服化道是否可产出、一致性",
        "artifact": "场景与角色视觉设定卡（文本，供出图用）",
        "power": ["veto_production"],      # 能说"这场拍不出来"
        "power_cn": "能说「这场拍不出来」并要求改",
        "must_not": [
            "不参与故事评价（好不好看不是美术的判断）",
            "不评节奏与镜头（那是导演的职权）",
        ],
    },
    "scripty": {
        "cn": "场记",
        "goal": "前后一致：人物/时间线/道具/服装",
        "artifact": "矛盾清单（**必须引用原文**）",
        "power": ["block_continuity"],     # 能否决
        "power_cn": "能否决（连续性错误必须修）",
        "must_not": [
            "不提改戏建议（只报矛盾，怎么改是编剧的职权）",
            "不评价故事与镜头",
        ],
    },
}
ROLE_ORDER = ("writer", "director", "art", "scripty")

# 各角色的提示词版本。**它是断点 key 的一维**：改了提示词，缓存必须失效。
# 单人改动就 bump 这里，重跑时会自动重出，不会静默复用旧产出。
PROMPT_VERSION = {
    "writer.outline": "1.0.0",
    "writer.script": "1.0.0",
    "director.board": "1.0.0",
    "art.cards": "1.0.0",
    "scripty.continuity": "1.0.0",
}


# ---------------------------------------------------------------------------
# 闸门一：合规自检（广告法违禁词 + **短剧常见风险**）
#
# 这是一道**粗筛**：宁可多报也别漏报，最终判断仍要人工复核，
# 且不等于任何平台的官方审核结论（官方标准不公开、会变）。
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    # 【表述边界】"最新"在剧情里是常用词（「最新的检查报告」「最新的订单」），
    # 它说的是"时间最近"，不是"最好"。所以「最新」只在**商业宣称**语境里算最高级：
    # 后面接的是技术/配方/版本/机型/产品这类**商品属性词**时才命中。
    # 其余（最好/最佳/最优/最低/最便宜/最快/最强/最大/最高/最先进…）性质是绝对化
    # 比较，无歧义，照拦。
    (r"最(好|佳|优|低|便宜|省|划算|实惠|快|强|大|高|先进|流行|受欢迎|顶级|厉害)",
     "高", "广告法第九条禁止「最高级」用语", "superlative"),
    (r"最新(技术|配方|版本|机型|款|产品|科技|工艺|研发|升级|方案|设备)",
     "高", "广告法第九条禁止「最高级」用语（商业宣称形态）", "superlative"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    (r"(全国|全球|全网|行业|销量|口碑|人气)第一|第一(品牌|选择)|排名第一|"
     r"No\.?\s*1|TOP\s*1", "高", "「第一」类排他性表述"),
    (r"国家级|世界级|全球级|国际级", "高", "「国家级」等权威性词汇属明令禁止"),
    (r"100\s*%|百分之百|百分百", "高", "绝对化效果承诺"),
    (r"绝对(有效|安全|放心|不会|能|可以)|保证(有效|成功|瘦|赚)|无效退款", "高",
     "绝对化保证与效果担保"),
    # 【加限定，去误伤】裸「特效」会把"特效化妆/后期特效/特效镜头"（短剧制作术语）
    # 全部判成医疗违规。这里只收紧到**药品疗效**形态。
    (r"根治|治愈率|痊愈|药到病除|包治(百病|万病)|特效药|特效疗法|特效偏方|祖传秘方|"
     r"无副作用|零副作用|抗癌|降(血压|血糖|血脂)", "高",
     "医疗功效宣称，普通内容不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|保本|保收益|日入过万|月入十万|高回报", "高",
     "投资类收益承诺"),
    (r"包过|保过|保录取|保证提分|不过退费|100%\s*就业", "高",
     "教育培训效果承诺，属明令禁止"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐|官方指定", "高",
     "不得虚构权威背书"),
    (r"催情|壮阳|丰胸|减肥(药|神器)|美白针|生发(神器)", "高",
     "特殊功效与特殊品类敏感词"),
    (r"免费领|免费送|0\s*元购|白送", "中", "可能构成虚假优惠或诱导分享"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天", "中",
     "促销时限表述需与实际活动一致"),
    # 【比模板更窄】裸的「唯一」「独家」在**剧情对白**里是常态
    #（「唯一的亲人」「独家消息」），一律拦会把整篇剧本判红。
    # 这里只在**带商业宣称后缀**时命中（唯一正品/全网独家/独家配方）。
    (r"唯一(正品|官方|指定|授权|配方|渠道)|全网独家|独家(配方|工艺|渠道|资源|首发)|"
     r"首(个|创)(推出|发布|研发|发明)|填补(行业)?空白|领先(品牌|技术|水平)",
     "中", "排他性表述需有可举证依据"),
    (r"纯天然|无添加|零添加|无毒无害", "中", "成分/材质宣称需与检测报告一致"),
    (r"点击链接|加微信|私信我|扫码(加|进|领)|vx|VX|微信号|加V", "中",
     "站外导流，平台普遍限制"),
    # 【比模板更窄】把裸「震惊」收成标题党固定搭配——剧情里「震惊」是常用词
    #（「他震惊地看着她」），按裸词拦是误伤；而「震惊体」的形态是可枚举的。
    (r"震惊(体|部|全网|全国|了[！!])|惊呆(了)?[！!]|不看后悔|错过再等一年|"
     r"速看|删前必看|赶紧转发|不转不是", "中", "标题党式诱导"),
    (r"[！!]{2,}|[?？]{3,}", "低", "标点堆砌，易被判标题党/低质"),
]

# **短剧常见风险**：同一个表达在不同形态的内容里风险不一样，所以单列一张表。
#
# 为什么短剧要单列：短剧是**剧情向**内容，"冲突"是它的基本燃料——所以不能简单地
# 把"打/杀/死"这类词一律拦下（那样任何一部剧都过不了）。这里刻意只拦**表述边界**：
#   · 血腥：拦"细节化展示"，不拦剧情里的死亡与冲突（`血腥描写` 级别）
#   · 软色情：拦暗示性描写与身体部位特写，不拦正常的感情戏
#   · 赌博：拦具体玩法与"稳赢"话术（部分与广告法重叠），不拦剧情里的赌局设定
#   · 迷信：拦"改命/化煞/转运"这类**可被当成现实方案**的表述，不拦剧情里的封建设定
#
# 这张表是**经验口径**，不是任何平台的官方审核标准；等级只用于排序，
# 本包**全部等级都拦截**（与全库口径一致：低风险同样拦）。
DRAMA_REDLINES = [
    (r"开膛|剖腹|剖开|内脏|脑浆|断肢|挖(眼|心)|砍(下|掉)(头|手|脚)|血(浆|泊|淋淋)|"
     r"血肉模糊|尸(块|体被(肢解|分尸))|碎尸", "高",
     "血腥细节化描写（剧情里的冲突可以写，血腥细节不能展示）"),
    (r"凌迟|虐杀|折磨致死|活活(打死|烧死)|虐(待|童|猫|狗)", "高",
     "虐待与极端暴力细节"),
    # 【表述边界，不是词表】"喘息"在动作戏里到处都是（跑完喘、喘着说话），
    # 只有与性动作词搭配才是软色情；身体部位同理，必须与暴露类词同现。
    (r"床戏|脱(光|下|衣)|裸(体|身|照)|肉(欲|体)|呻吟|挑逗|撩拨|勾引|一夜情|开房|"
     r"共浴|下体|私处|(?:胸口|胸前|大腿|腰肢)[^。！？\n]{0,8}(?:露|裸|紧贴|湿透|摩挲)|"
     r"(?:喘息|娇喘|喘气)[^。！？\n]{0,6}(?:呻吟|撩|挑逗|床上|身下|贴)", "中",
     "软色情暗示与身体部位描写（感情戏可以写，暗示性描写不能）"),
    # 【写法边界】"赌局""赌场"作为**剧情场景**是允许的（赌博题材短剧很多），
    # 不能展示的是**具体玩法与操作**。所以只拦玩法词与下注动作，不拦场景名词。
    (r"百家乐|轮盘|老虎机|德州扑克|六合彩|时时彩|扎金花|牛牛|"
     r"押注|下注|开盘口|坐庄|赔率|一把梭|梭哈", "中",
     "赌博玩法与操作（剧情里的赌局设定可以，具体玩法不能展示）"),
    (r"改命|化煞|转运|开光|驱邪|做法事|阴阳眼|大师指点|算命(准|改)|"
     r"风水(布局|改)|符水|招财符", "中",
     "迷信类可操作方案（剧情里的封建设定可以，「照着做能改命」不能）"),
    (r"自杀|自残|割腕|上吊|跳楼|服毒|轻生", "高",
     "自杀自残细节，平台明令限制"),
    (r"吸毒|冰毒|摇头丸|大麻|白粉|贩毒", "高", "毒品相关表述"),
    (r"传销(组织|团伙|模式|课程)|拉人头(返利|分红)?|庞氏骗局|资金盘|杀猪盘|"
     r"三级分销|发展下线", "中", "涉传销与诈骗手法"),
]
BANNED_RE = []
for _t in BANNED_PATTERNS + DRAMA_REDLINES:
    BANNED_RE.append((re.compile(_t[0]), _t[1], _t[2],
                      _t[3] if len(_t) > 3 else None))
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}

# ---------------------------------------------------------------------------
# 「最高级」用语的语境豁免（**照抄本库已统一的判断逻辑**）
#
# 事故复盘：真实原稿里「回头翻一条自己播放量最低的视频」被本地闸门判成
# 「命中高风险（广告法第九条）」并整篇拦截。这个诊断是**错的**——那是在描述
# 自己的数据，不是对商品/服务的绝对化宣称。
#
# 豁免条件刻意做得很窄：`最X` 前一个字是计量类名词，**且** `最X` 后紧跟「的」或「之」。
# 句首**不豁免**：「最低价」单独成句时必须照拦。
#   ⚠️ 下面那个 `before and` 不能省：空串在 Python 里 `"" in "量率数…"` 是 True，
#   漏了它句首的「最好/最低」会被全部误豁免。
# 豁免词表刻意**不含** `时`/`款`/`种`/`家`/`价`：「课时最低」「单价最低」是真实价格宣称。
#
# 【第二条豁免：说人的「最X」】这是本包**为剧情文本新增**的一条：
#   短剧对白里「最好的医生」「最大的对手」「最信任的朋友」是**叙事**，
#   不是对商品/服务的绝对化宣称。判据刻意做得很窄——`最X的` **紧跟一个人物类名词**
#   才算豁免；后面接商品/服务类名词（最好的设备、最低的价格）**照样拦**。
#   实测依据：3 轮真机里「最快」「最大」「最好」各命中一次，逐条核对**全部**是台词里
#   说人或说事，没有一处是商业宣称。假命中会让使用者开始无视闸门，所以必须收这一刀。
# ---------------------------------------------------------------------------

MEASURE_PREFIX = "量率数分位条次段部集页个天月年"
PERSON_NOUNS = ("医生", "律师", "人", "朋友", "对手", "敌人", "亲人", "家人", "儿子",
                "女儿", "父亲", "母亲", "哥哥", "姐姐", "弟弟", "妹妹", "男人", "女人",
                "孩子", "老师", "警察", "老板", "仇人", "伙伴", "搭档", "兄弟")


def _is_data_extreme(text, m):
    start, end = m.start(), m.end()
    before = text[start - 1] if start > 0 else ""
    after = text[end:end + 1]
    return bool(before) and before in MEASURE_PREFIX and after in ("的", "之")


def _is_person_extreme(text, m):
    """`最X的` + 人物类名词 → 判为叙事（说人），不是商业宣称。

    ⚠️ 句首**仍然不豁免**（`if not before: return False`），与第一条豁免同一口径。
    """
    start, end = m.start(), m.end()
    before = text[start - 1] if start > 0 else ""
    if not before:
        return False
    if text[end:end + 1] != "的":
        return False
    rest = text[end + 1:end + 5]
    return any(rest.startswith(n) for n in PERSON_NOUNS)


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
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
# 关键结论：**模型会照抄示例，哪怕那个示例标着「这是错的写法」。**
# 所以本包的提示词里不出现任何一句可直接复制的完整中文句子，
# 举例只用**跨主题**的描述性说明，真实示例一律登记在 PROMPT_SAMPLES。
#
# 判定三条（任一即命中）：
#   · 去标点后**完全相同**
#   · 字符二元组 Jaccard ≥ ECHO_SIM (0.75)
#   · 示例的二元组**覆盖度 ≥ ECHO_CONTAIN (0.60)**
#
# ⚠️ **contain 会饱和误报**（本库踩过）：覆盖度 = |交集| / |示例二元组|。
#    当目标文本**远长于**示例时，示例的二元组几乎必然全被长文本包含，
#    覆盖度直接冲到 1.00 —— 哪怕两者毫无关系。也就是说长文对短示例
#    用 contain 判据**只会误报**。所以给 contain 加一个**适用窗口**：
#    只有目标归一化长度落在 [示例长度, 示例长度 × ECHO_CONTAIN_MARGIN] 里时才启用。
#    超出窗口的比对一律不启用 contain（靠 exact / jaccard 兜）。
#    叠加**相对长度守卫** max(6, len(示例)//2)：太短的目标不比，短串二元组集合太小、指标虚高。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6
ECHO_CONTAIN_MARGIN = 4          # contain 适用窗口上界倍数：len(目标) ≤ len(示例) × 4


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


# 提示词 / 文档里出现过的示例文本（**跨主题**，正常不该被抄）。
# 主题刻意选「社区菜市场摊位租金」，与本包会产出的短剧题材（穿越 / 复仇 / 都市）
# 明显不搭——这样"命中"就一定是照抄，不是巧合。新增示例必须登记到这里。
PROMPT_SAMPLES = [
    "菜市场摊位租金这笔账，我记了三个月",
    "先说结论：摊位租金高不高，跟人流量不成正比",
    "我在菜市场摆了两年摊，租金这块踩过三个坑",
    "谈摊位之前没人告诉我，押金这一关才是最难的",
    "三组数字说明，社区菜市场的摊位没你想的贵",
]


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的文案往往只改标点（`，`↔`、`↔空格）或换行位置，所以先抹平标点再看。
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


def prompt_echo(text, samples=None, allow_contain=True):
    """文本是否与提示词里登记过的示例「抄得太近」。

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"。
    `allow_contain=False` 时**不启用**覆盖度判据（整段长文比对用，见 prompt_echo_scan）。
    """
    target = _norm_for_echo(text)
    if not target:
        return False, 0.0, "", ""
    best_score, best_sample, best_rule = 0.0, "", ""
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        ns = _norm_for_echo(s)
        if target == ns:
            return True, 1.0, s, "exact"
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(text, s)
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        # contain **只在适用窗口内**启用：目标不能长过示例的 ECHO_CONTAIN_MARGIN 倍。
        base = _bigrams(s)
        in_window = bool(ns) and len(target) <= len(ns) * ECHO_CONTAIN_MARGIN
        if allow_contain and in_window and base:
            contain = len(_bigrams(text) & base) / float(len(base))
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

    **为什么不能只比整段**：一集剧本有几千字，而提示词示例只有二三十字。
    整段比 Jaccard 分母被撑到几千，相似度永远接近 0——模型把示例原样抄进某一句，
    这道闸门完全看不见。所以判定分两层：
      1. 整段比一次（兜住整篇照抄），这一层**只认 exact / jaccard**：
         长文用 contain 只会饱和误报（见常量区注释）
      2. **逐句比一次**（兜住「某一句是抄的」这个真实形态），三层判据都启用
    """
    hits = []
    whole_hit, score, sample, rule = prompt_echo(text, samples, allow_contain=False)
    if whole_hit:
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
            why = ("稿子里的「{}」有 {:.0f}% 的内容来自提示词示例「{}」"
                   "（覆盖度 ≥ {:.2f} 即判照抄；适用窗口内才启用，见 ECHO_CONTAIN_MARGIN）"
                   .format(seg[:20], score * 100, sample[:24], ECHO_CONTAIN))
        elif rule == "exact":
            why = "稿子里的「{}」与提示词示例去掉标点后完全相同（照抄示例）".format(seg[:20])
        else:
            why = "稿子里的「{}」与提示词示例相似度 {:.2f}，属同构照抄".format(seg[:20], score)
        hits.append({"part": label, "segment": seg[:40], "sim": round(score, 3),
                     "sample": sample, "why": why})
        break                      # 一处命中足够拦截，不用把整篇列完
    return hits


# 提示词卫生自检用的「脏东西」形态，**刻意比 PLACEHOLDER_RE 窄**。
# 教训是通用的：一个为**产出**设计的检查，不能直接拿去扫**输入**
# （提示词里为说明输出结构写的 `{...}` 不是没填干净的模板）。
PROMPT_DIRT_PATTERNS = [
    (r"\{\s*\}", "提示词里有空占位花括号"),
    (r"待填|待补充|待定", "提示词里有「待填/待补充」字样"),
    (r"\bXXX+\b|\bxxx+\b", "提示词里有连续占位字母"),
    (r"\bTODO\b|\bTBD\b|\bFIXME\b", "提示词里有 TODO/TBD 标记"),
    (r"请(填写|替换|补充)", "提示词里有「请填写/请替换」提示语"),
]
PROMPT_DIRT_RE = [(re.compile(p), why) for p, why in PROMPT_DIRT_PATTERNS]


def prompt_hygiene(prompt):
    """提示词卫生自检：即将发送的提示词里**不许混进**登记过的完整示例句。

    这是 prompt_echo 的前置防线。事后闸门只能拦"模型抄了"，
    拦不住"我们把示例写进了提示词"——而后者才是可避免的根因。
    """
    hits = []
    whole_hit, score, sample, rule = prompt_echo(prompt, allow_contain=False)
    if whole_hit:
        hits.append({"sample": sample, "rule": rule, "sim": round(score, 3)})
    for seg in split_sentences(prompt):
        hit, score, sample, rule = prompt_echo(seg)
        if hit:
            hits.append({"sample": sample, "rule": rule, "sim": round(score, 3)})
            break
    for rx, why in PROMPT_DIRT_RE:
        m = rx.search(prompt or "")
        if m:
            hits.append({"prompt_dirt": m.group(0)[:20], "why": why})
            break
    return hits

# ---------------------------------------------------------------------------
# 分镜枚举（闸门五用它判「每镜有没有景别」）
#
# 为什么景别要判枚举而不是"非空就行"：景别是分镜表的骨架——它决定观众离人物多远。
# 一镜写"中景"、一镜写"看得见人"、一镜写"常规"，节奏就没了。
# 但口语化写法给别名表兜住（别把"半身"这种正经说法判成错）。
# ---------------------------------------------------------------------------

SHOT_SIZES = ("大远景", "远景", "全景", "中景", "中近景", "近景", "特写", "大特写")
SHOT_SIZE_ALIASES = {
    "大全景": "远景", "大全": "远景", "远镜头": "远景", "广角": "远景",
    "全身": "全景", "全身景": "全景", "full": "全景",
    "medium": "中景", "中": "中景",
    "中近": "中近景", "中特写": "中近景", "半身": "中近景", "半身景": "中近景",
    "近": "近景", "近镜头": "近景",
    "closeup": "特写", "close-up": "特写", "局部": "特写",
    "大特": "大特写", "极特写": "大特写",
}
CAMERAS = ("平视", "微俯", "俯视", "仰视", "过肩", "越肩", "主观视角", "斜侧", "背身", "正面")
# 口语别名表：真机实测里导演写过「跟拍」「手持微晃」「微仰」——都是正经机位说法，
# 认不出来就把好数据判成错（**假命中**）。别名表只做**归一化**，不放松枚举本身。
CAMERA_ALIASES = {
    "微仰": "仰视", "略仰": "仰视", "仰拍": "仰视", "低角度": "仰视",
    "略俯": "微俯", "俯拍": "俯视", "高角度": "俯视",
    "跟拍": "斜侧", "跟镜头": "斜侧", "手持": "斜侧", "手持微晃": "斜侧", "侧拍": "斜侧",
    "客观视角": "平视", "正拍": "正面", "正对": "正面",
    "过肩镜头": "过肩", "越肩镜头": "越肩", "第一人称": "主观视角", "第三人称": "平视",
}
TRANSITIONS = ("硬切", "叠化", "淡入", "淡出", "划像", "闪白", "黑场", "甩镜", "匹配剪辑")


def normalize_shot_size(raw):
    """把模型写的景别收拾成枚举值；认不出来返回 None（闸门会标红）。"""
    s = re.sub(r"[\s·、,，]", "", str(raw or ""))
    if not s:
        return None
    if s in SHOT_SIZES:
        return s
    low = s.lower().replace("镜头", "").replace("景", "") or s
    if low in SHOT_SIZES:
        return low
    for alias, canon in SHOT_SIZE_ALIASES.items():
        if s == alias or low == alias.lower():
            return canon
    for canon in SHOT_SIZES:                     # 兜底：包含关系
        if canon in s:
            return canon
    return None


def normalize_camera(raw):
    s = re.sub(r"[\s·、,，]", "", str(raw or ""))
    if not s:
        return None
    if s in CAMERAS:
        return s
    if s in CAMERA_ALIASES:
        return CAMERA_ALIASES[s]
    for canon in CAMERAS:
        if canon in s:
            return canon
    return None


def _slug_loose_match(a, b):
    """场名模糊匹配：两边归一化后**互相包含**才算同一个场。

    为什么只认"互相包含"：`陈默家客厅` 与 `出租屋客厅` 都含「客厅」，
    但它们是**不同的场**，靠"共同词"判会假匹配。而"同一个场被写成略不同的名字"
    的真实形态就是互相包含（`雨夜街头` vs `雨夜街头·电动车旁`）。
    """
    na, nb = _norm_for_echo(a), _norm_for_echo(b)
    if not na or not nb:
        return False
    return na in nb or nb in na


def _to_seconds(v):
    """把时长写法统一成秒（float）。认不出来返回 None。

    接受：`3`、`3.5`、`"3秒"`、`"3s"`、`"00:03"`、`"1分20秒"`。
    """
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d+):(\d{1,2})", s)
    if m:
        return float(int(m.group(1)) * 60 + int(m.group(2)))
    m = re.search(r"(?:(\d+(?:\.\d+)?)\s*分)?\s*(\d+(?:\.\d+)?)\s*(?:秒|s|S)?", s)
    if not m:
        return None
    mins = float(m.group(1) or 0)
    secs = float(m.group(2) or 0)
    total = mins * 60 + secs
    return total if total > 0 else None


# ---------------------------------------------------------------------------
# 闸门四：矛盾清单锚点（**本包最容易造假的一道**）
#
# 场记的任务是报"前后矛盾"。矛盾清单本身读起来永远很像真的——
# 所以造假成本极低：模型完全可能编一句"第 2 场说伞是黑色的，第 5 场变成红色"，
# 而剧本里根本没写过伞。
#
# 判定：每条矛盾**必须带 quote**（引用剧本原文），且：
#   · quote 去标点后长度 ≥ MIN_QUOTE_LEN（4 字）——太短的引文（"他"、"伞"）
#     在剧本里随便都能撞上，等于没有锚点
#   · quote 去标点后必须**真的出现在剧本归一化全文里**——编造的引文直接剔出
# 被剔出的条目**不是悄悄删掉**，而是登记进 dropped_quotes 并报出来，
# 让它自己成为一条可复核的产出（"场记编了 2 条引文"这件事本身就是信息）。
# ---------------------------------------------------------------------------

MIN_QUOTE_LEN = 4


def _find_quote(quote, corpus_norm):
    """引文是否真的锚在剧本原文里（去标点后包含判定）。"""
    q = _norm_for_echo(quote)
    if len(q) < MIN_QUOTE_LEN:
        return False
    return q in corpus_norm


def continuity_gate(conflicts, script_md):
    """闸门四：校验矛盾清单的每一条引文。返回 (kept, dropped, problems)。

    `kept` 只保留引文真实锚定在剧本里的条目；`dropped` 是编造引文的条目；
    `problems` 是结构性缺项（没有 quote 字段、字段为空、分类非法）。
    """
    corpus = _norm_for_echo(script_md)
    kept, dropped, problems = [], [], []
    for i, c in enumerate(conflicts or [], 1):
        if not isinstance(c, dict):
            problems.append("第 %d 条矛盾不是对象，已剔出" % i)
            continue
        quote = (c.get("quote") or "").strip()
        cat = (c.get("category") or "").strip()
        where = (c.get("where") or "").strip()
        rec = dict(c)
        rec["no"] = i
        if not quote:
            problems.append("第 %d 条矛盾没有引用原文（quote 为空）——**没有锚点的矛盾不予采信**" % i)
            dropped.append(rec)
            continue
        if not _find_quote(quote, corpus):
            rec["dropped_why"] = ("引文「%s」在剧本原文里找不到"
                                  "（去标点后逐字比对不上）——判为**编造引文**，剔出"
                                  % quote[:24])
            dropped.append(rec)
            continue
        if cat not in CONTINUITY_CATEGORIES:
            problems.append("第 %d 条矛盾的分类 %r 不在枚举里（可用：%s）"
                            % (i, cat, " / ".join(CONTINUITY_CATEGORIES)))
        if not where:
            problems.append("第 %d 条矛盾没写 where（哪一集/哪一场），无法定位" % i)
        kept.append(rec)
    return kept, dropped, problems


# ---------------------------------------------------------------------------
# 闸门五：分镜结构（每镜必须有 景别 + 画面描述 + 时长；镜数为 0 → 拦）
#
# 这条闸门是「分镜」与「剧情梗概」的分界线：
#   梗概只要说清发生了什么；分镜必须能读出**镜头**——景别决定观众离人物多远，
#   机位决定观众站在哪，时长决定这一镜占多少节奏。缺了这些，分镜表无法开工。
# ⚠️ 本包**不替导演补字段**：缺了就是缺了，报出「第几集 第几镜 缺了哪个字段」。
#    自动补全 = 假绿闸门，比没有闸门更危险。
# ---------------------------------------------------------------------------

MIN_VISUAL_LEN = 8


def board_gate(board, script=None):
    """闸门五：分镜结构自检。返回 (problems, stats)。"""
    problems = []
    anchoring = []
    eps = board.get("episodes") or []
    shots_total = 0
    durations = []
    known_scenes = set()
    if script is not None:
        for e in script.get("episodes") or []:
            for s in e.get("scenes") or []:
                known_scenes.add((int(e.get("no") or 0), (s.get("slug") or "").strip()))
    for e in eps:
        eno = e.get("no")
        shots = e.get("shots") or []
        if not shots:
            problems.append("第 %s 集没有任何镜头（镜数为 0 的分镜表不能开工）" % eno)
        for i, sh in enumerate(shots, 1):
            shots_total += 1
            tag = "第 %s 集 第 %d 镜" % (eno, i)
            ss_raw = sh.get("shot_size")
            ss = sh.get("shot_size_norm") or normalize_shot_size(ss_raw)
            if not ss_raw:
                problems.append("%s 没有景别（景别是分镜的骨架）" % tag)
            elif not ss:
                problems.append("%s 的景别 %r 不在枚举里（可用：%s）"
                                % (tag, ss_raw, " / ".join(SHOT_SIZES)))
            visual = (sh.get("visual") or "").strip()
            if not visual:
                problems.append("%s 没有画面描述" % tag)
            elif len(_norm_for_echo(visual)) < MIN_VISUAL_LEN:
                problems.append("%s 的画面描述只有 %d 个字（少于 %d 字基本等于没写）：%r"
                                % (tag, len(_norm_for_echo(visual)), MIN_VISUAL_LEN,
                                   visual[:30]))
            secs = _to_seconds(sh.get("seconds"))
            if secs is None:
                problems.append("%s 没有可识别的时长（用秒数或 mm:ss）" % tag)
            else:
                durations.append(secs)
                lo, hi = CREW["shot_seconds"]
                if not (lo <= secs <= hi):
                    problems.append("%s 的时长 %.1f 秒不在 %d~%d 秒区间（短剧单镜时长口径）"
                                    % (tag, secs, lo, hi))
            cam = sh.get("camera")
            if not cam:
                problems.append("%s 没有机位（机位决定观众站在哪）" % tag)
            elif not (sh.get("camera_norm") or normalize_camera(cam)):
                problems.append("%s 的机位 %r 不在枚举里（可用：%s）"
                                % (tag, cam, " / ".join(CAMERAS)))
            tr = (sh.get("transition") or "").strip()
            if not tr:
                problems.append("%s 没有转场（转场决定这一镜怎么接到下一镜）" % tag)
            # 剧本锚点：分镜应当指向剧本里真实存在的场次。
            #
            # ⚠️ 这里刻意做成**软提示**，不是硬拦。实测教训（3 轮真机）：
            #   导演把场名写成「陈默家客厅」，而剧本里那一场叫「出租屋客厅」——
            #   于是同一个第 2 集刷出 **18 条**"场次不存在"，把真正的问题全淹了。
            #   场名是**人写的自然语言**，两处措辞不同是常态；硬判等于把噪声当信号。
            #   所以：能归一化匹配上就算锚定成功；匹配不上只记进 anchoring，
            #   **不进 problems（不拦）**，但在 --json 与报告里如实列出。
            if known_scenes and (sh.get("scene_slug") or "").strip():
                raw_slug = (sh.get("scene_slug") or "").strip()
                key = (int(sh.get("episode") or eno or 0), raw_slug)
                hit = key in known_scenes
                if not hit:
                    hit = any(abs(k[0] - key[0]) <= 1
                              and _slug_loose_match(raw_slug, k[1]) for k in known_scenes)
                if not hit:
                    anchoring.append(
                        "%s 的场名 %r 与剧本对不上（第 %s 集的场名是：%s）"
                        % (tag, raw_slug, key[0],
                           " / ".join(sorted(k[1] for k in known_scenes if k[0] == key[0]))
                           or "（无）"))
    stats = {"episodes": len(eps), "shots": shots_total,
             "total_seconds": round(sum(durations), 1),
             "avg_seconds": round(sum(durations) / len(durations), 1) if durations else 0.0,
             # 场名对不上是**提示**不是拦（见上面注释）；报告里单独一节列出来
             "unanchored_shots": len(anchoring),
             "anchoring": anchoring[:12]}
    return problems, stats


CONTINUITY_CATEGORIES = ("人物", "时间线", "道具", "服装", "空间", "因果")


def continuity_stats(conflicts):
    by_cat, by_sev = {}, {}
    for c in conflicts or []:
        by_cat[c.get("category") or "未分类"] = by_cat.get(c.get("category") or "未分类", 0) + 1
        by_sev[c.get("severity") or "未分级"] = by_sev.get(c.get("severity") or "未分级", 0) + 1
    blocking = [c for c in (conflicts or []) if (c.get("severity") or "") in ("高", "中")]
    return {"total": len(conflicts or []), "by_category": by_cat, "by_severity": by_sev,
            "blocking": len(blocking)}


# ---------------------------------------------------------------------------
# 闸门六：角色一致性（剧本 ↔ 美术设定卡）
#
# 这是**本地可比对的硬项**，所以做成硬闸门：
#   · 剧本里出现的每个角色名，设定卡里必须有（漏一个 = 出图时没人知道画谁）
#   · 性别硬项：两边都写了性别且不一致 → 拦（这是"同一个角色两张脸"的根因之一）
#   · 年龄段硬项：两边都写了年龄段且不一致 → 拦（"少女" vs "中年"不能同时成立）
#   · 场记报的「人物」类矛盾里，涉及的角色名必须能在剧本里找到（与闸门四互补）
#
# 刻意**不**比对 soft 项（气质、色彩偏好）：那是风格软约束，
# 两边措辞不同很正常，硬比会大面积误报，反而让闸门被无视。
# ---------------------------------------------------------------------------

AGE_BUCKETS = {
    "幼": ("幼", "童", "小孩", "儿童", "五六岁", "七八岁"),
    "少年": ("少年", "少女", "十几", "十六", "十七", "高中", "初中", "青少年"),
    "青年": ("青年", "年轻", "二十", "二十几", "三十", "而立", "大学"),
    "中年": ("中年", "四十", "五十", "半百", "不惑", "知天命"),
    "老年": ("老年", "老人", "六十", "七十", "花甲", "古稀", "耄耋"),
}


def _age_bucket(text):
    s = str(text or "")
    for bucket, keys in AGE_BUCKETS.items():
        for k in keys:
            if k in s:
                return bucket
    return None


def _gender_of(text):
    s = str(text or "")
    has_f = bool(re.search(r"女|她|母亲|妈妈|姐姐|妹妹|姑娘|女主", s))
    has_m = bool(re.search(r"男|他|父亲|爸爸|哥哥|弟弟|小伙|男主", s))
    if has_f and not has_m:
        return "女"
    if has_m and not has_f:
        return "男"
    return None


# 角色名里的"舞台提示"后缀：`阿深（电话）`、`陈默（画外音）`、`苏晚(旁白)`。
# 它们指的是**同一个角色**，不是另一个人——不去掉的话闸门六会对每一部剧
# 都报"这个角色没有设定卡"，那是纯误伤（实测踩到）。只剥括号提示，
# 不剥真正的名字差异（"陈默"和"陈默然"仍然是两个人）。
_ROLE_TAG_RE = re.compile(r"[（(][^）)]{1,12}[）)]\s*$")


def canonical_name(name):
    """角色名归一化：去掉结尾的舞台提示括号与空白。"""
    nm = str(name or "").strip()
    for _ in range(3):
        new = _ROLE_TAG_RE.sub("", nm).strip()
        if new == nm:
            break
        nm = new
    return re.sub(r"[\s·、,，]+", "", nm)


def role_consistency(script, art):
    """闸门六：剧本与美术设定卡的硬项一致性。返回 problems 列表。"""
    problems = []
    script_chars = {}
    for e in script.get("episodes") or []:
        for s in e.get("scenes") or []:
            for nm in s.get("characters") or []:
                nm = canonical_name(nm)
                if nm:
                    script_chars[nm] = script_chars.get(nm, 0) + 1
    for c in script.get("characters") or []:
        nm = canonical_name(c.get("name"))
        if nm:
            script_chars.setdefault(nm, 0)
    cards = {}
    for c in art.get("characters") or []:
        nm = canonical_name(c.get("name"))
        if nm:
            cards[nm] = c
    if script_chars and not cards:
        problems.append("剧本里有 %d 个角色，但美术设定卡里一个角色都没有"
                        "（设定卡是出图的凭据，不能为空）" % len(script_chars))
        return problems
    for nm, cnt in sorted(script_chars.items()):
        if nm not in cards:
            problems.append("角色「%s」在剧本里出场 %d 次，但美术设定卡里没有这个角色"
                            "（跨镜一致性没有凭据）" % (nm, cnt))
    for nm, card in sorted(cards.items()):
        src = None
        for c in script.get("characters") or []:
            if canonical_name(c.get("name")) == nm:
                src = c
                break
        if src is None:
            continue                      # 剧本角色表里没有的人物：不硬判（可能只出现在设定卡）
        g1, g2 = _gender_of(src.get("gender") or src.get("desc") or ""), \
            _gender_of(card.get("gender") or card.get("appearance") or "")
        if g1 and g2 and g1 != g2:
            problems.append("角色「%s」的性别在剧本里是「%s」、在设定卡里是「%s」——"
                            "两边必须一致" % (nm, g1, g2))
        a1 = _age_bucket(src.get("age") or src.get("desc") or "")
        a2 = _age_bucket(card.get("age") or card.get("appearance") or "")
        if a1 and a2 and a1 != a2:
            problems.append("角色「%s」的年龄段在剧本里是「%s」、在设定卡里是「%s」——"
                            "两边必须一致" % (nm, a1, a2))
    return problems


# ---------------------------------------------------------------------------
# 闸门七：裁决完整性（**不许假装谈拢**）
#
# L3 与 L2 的分界就在这道闸门：多角色协作如果只在"各自写了一段话"这个层面，
# 它就不是协作。所以：
#   · 导演 verdict=reject 必须给 reasons（≥1 条可读理由）+ unshootable（≥1 条）
#     ——"这场写不了"必须说清**哪一场、为什么**
#   · 美术 verdict=not_producible 必须给 reasons 与 要求改的场次
#   · 场记的 高/中 等级矛盾 = 否决：报告里必须出现，且最终必须被处理（改了或显式挂起）
#   · 轮次用完仍未达成一致 → **显式列未决项 + exit=6**，不许把分歧写成"已通过"
#
# 还有一条"死循环"检测：编剧返修后**正文一字未变**（内容指纹相同）时，
# 说明这一轮没有真的改。这不算"重写完成"，要如实报出，否则会出现
# "跑满 4 轮、每轮都打回、报告里却写着已收敛"这种假收敛。
# ---------------------------------------------------------------------------

VERDICTS = {
    "writer": ("draft", "revised"),
    "director": ("approve", "reject"),
    "art": ("producible", "not_producible"),
    "scripty": ("clear", "blocking"),
}


def verdict_gate(verdict, role):
    """闸门七（单个裁决）：裁决必须合法且**必须留可读理由**。返回 problems。

    ⚠️ 入参容错：既可以是**纯 verdict 对象**（`{"verdict": ..., "reasons": [...]}`），
    也可以是**整个产出对象**（分镜表 / 矛盾清单，verdict 嵌在里面）。
    实测踩过两次坑：一次是场记把 conflicts 找在 verdict 上（假命中），
    一次是把整对象当 verdict 传进来，`v` 变成
    `"{'verdict': 'clear', 'auto': None}"` 这串字面量，被判成"裁决不在枚举里"
    （也是假命中）。**闸门的假命中比漏判更有害**——使用者会开始无视闸门。
    所以这里在入口把两种形态统一归一化。
    """
    if isinstance(verdict, dict) and isinstance(verdict.get("verdict"), (dict, type(None))):
        obj = verdict
        verdict = verdict.get("verdict") or {}
    else:
        obj = {"verdict": verdict}
    problems = []
    v = str((verdict or {}).get("verdict") or "").strip()
    allowed = VERDICTS.get(role) or ()
    if not v:
        problems.append("%s 没给裁决（verdict 为空）——裁决缺失等于没开会" % ROLES[role]["cn"])
        return problems
    if allowed and v not in allowed:
        problems.append("%s 的裁决 %r 不在枚举里（可用：%s）"
                        % (ROLES[role]["cn"], v, " / ".join(allowed)))
        return problems
    if role == "director" and v == "reject":
        if not (verdict.get("reasons") or []):
            problems.append("导演打回了编剧，但**没有给任何理由**（打回必须留可读理由）")
        if not (verdict.get("unshootable") or []):
            problems.append("导演打回了编剧，但没指出**哪一场写不了**"
                            "（「这场写不了」必须指到具体场次）")
    if role == "art" and v == "not_producible":
        if not (verdict.get("reasons") or []):
            problems.append("美术否决了这场戏，但**没有给任何理由**")
        if not (verdict.get("scenes") or []):
            problems.append("美术否决了，但没指出**哪一场拍不出来**")
    if role == "scripty" and v == "blocking":
        # ⚠️ 这里**不能**在 verdict 上找 conflicts：verdict 是
        # `{"verdict": "...", "auto": ...}`，conflicts 在**整个矛盾清单对象**上。
        # 写错过一次，后果是**假命中**——每一份正常的否决都被判成
        # 「有否决但矛盾清单是空的」，报告里因此多出一条根本不存在的违规。
        # 所以入参允许是"整对象"或"纯 verdict"，两种都认。
        if isinstance(obj, dict) and "conflicts" in obj:
            conf = obj.get("conflicts") or []
        else:
            conf = (verdict or {}).get("conflicts") or []
        # 口径：**否决 = 中高等级矛盾**。低等级矛盾只是瑕疵，不足以构成否决。
        blocking = [c for c in conf if (c.get("severity") or "") in ("高", "中")]
        if not blocking:
            problems.append("场记给的是否决（blocking），但矛盾清单里没有中高等级矛盾"
                            "（共 %d 条，逐条等级见 --json）——"
                            "「否决」与「至少一条中高等级矛盾」必须同时成立"
                            % len(conf))
    return problems


def dropped_quote_problems(cont_obj):
    """闸门四的**硬信号**：一旦有引文被剔出（编造引文），就必须拦下。

    为什么不能"剔掉就算了"：剔出是**信息**——它说明场记报了它无法举证的东西。
    如果因为"剔掉之后还剩一条真矛盾"就放行，那种"编造引文"的行为就被奖励了
    （反正只要顺便报一条真的就能过关）。所以这里把它当作硬违规报出来。
    报告里仍保留原文与剔出理由，供人工复核——**剔出不等于隐藏**。
    """
    dropped = (cont_obj or {}).get("dropped") or []
    if not dropped:
        return []
    out = ["闸门四：%d 条矛盾的引文在剧本原文里**找不到**（编造引文，已剔出、"
           "不计入矛盾数）" % len(dropped)]
    for c in dropped[:3]:
        out.append("　引文「%s」→ %s" % ((c.get("quote") or "")[:30],
                                        c.get("dropped_why") or "未通过逐字校验"))
    if len(dropped) > 3:
        out.append("　（其余 %d 条见 --json 的 dropped）" % (len(dropped) - 3))
    return out


def decision_closure(director, art, scripty, unresolved):
    """众裁决是否真的收敛。返回 (agreed, unresolved_items, notes)。

    入参形态要容错：`scripty` 既可能是 **verdict 对象**，也可能是**整个矛盾清单对象**
    （含 verdict + conflicts）。实测踩过：收尾时传了整对象，于是
    `scripty["conflicts"]` 取到 None，未决项被写成「0 条中高等级矛盾未修」——
    而同一份报告上面明明列着 3 条。**数字对不上的报告比没有报告更危险**，
    所以这里显式归一化两种形态。
    """
    items, notes = [], []
    d = (director or {}).get("verdict")
    a = (art or {}).get("verdict")
    if isinstance(scripty, dict) and "verdict" in scripty and "conflicts" in scripty:
        s = (scripty.get("verdict") or {}).get("verdict")
        s_conf = scripty.get("conflicts") or []
    else:
        s = (scripty or {}).get("verdict")
        s_conf = (scripty or {}).get("conflicts") or []
    if d == "reject":
        items.append({"role": "director", "role_cn": "导演", "kind": "reject",
                      "why": "导演仍打回编剧：%s"
                             % ("；".join((director.get("reasons") or [])[:2]) or "未给理由")})
    if a == "not_producible":
        items.append({"role": "art", "role_cn": "美术", "kind": "veto",
                      "why": "美术仍判定拍不出来：%s"
                             % ("；".join((art.get("reasons") or [])[:2]) or "未给理由")})
    if s == "blocking":
        n = len([c for c in s_conf if (c.get("severity") or "") in ("高", "中")])
        items.append({"role": "scripty", "role_cn": "场记", "kind": "block",
                      "why": "场记仍否决：%d 条中高等级矛盾未修" % n})
    for u in unresolved or []:
        items.append({"role": u.get("role"),
                      "role_cn": u.get("role_cn") or ROLES.get(u.get("role"), {}).get("cn")
                      or u.get("role"),
                      "kind": u.get("kind") or "unresolved",
                      "why": u.get("why") or ""})
    if items:
        notes.append("未达成一致：%d 项未决（轮次用完仍未收敛）" % len(items))
    return (not items), items, notes


MORE_MARKERS = ("打回", "否决", "拍不出来", "拍不了", "改戏", "重写", "不通过",
                "必须改", "需改", "不能开工")
APPROVE_MARKERS = ("打回", "否决", "拍不出来", "拍不了", "改戏", "重写", "不通过",
                   "必须改", "需改", "不能开工", "矛盾", "不一致", "冲突")


def critique_gate(verdict, role):
    """审出「说了话但等于没说话」：审稿意见里既没有具体问题词、又没指到场次。

    这道检查刻意很松（只报**空转**），因为审稿意见的写法本来就多样。
    判据：reasons 为空，**或** 所有 reasons 加起来不含任何"问题标记词"、
    且 unshootable/scenes 也没指到具体场次 → 判为空转。
    """
    problems = []
    if role in ("director", "art"):
        reasons = " ".join(str(x) for x in (verdict.get("reasons") or []))
        targets = (verdict.get("unshootable") or []) + (verdict.get("scenes") or [])
        if verdict.get("verdict") in ("reject", "not_producible"):
            if not reasons.strip():
                problems.append("%s 只给了结论、没给理由" % ROLES[role]["cn"])
            elif not any(k in reasons for k in MORE_MARKERS) and not targets:
                problems.append("%s 的理由里没有任何具体问题词，也没指到具体场次"
                                "（疑似空转：说了话但等于没说话）" % ROLES[role]["cn"])
    return problems


# ---------------------------------------------------------------------------
# 文本工具
# ---------------------------------------------------------------------------

def count_chars(s):
    """正文字数：非空白字符数（含中文标点）。"""
    return len(re.sub(r"\s", "", s or ""))


def text_hash(s):
    """片段指纹：用标准库 hashlib（不引第三方）。"""
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


def safe_name(s):
    return re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", (s or "").strip())[:24] or "x"


def _clip(text, limit=9000):
    t = str(text or "")
    return t if len(t) <= limit else t[:limit] + "\n……（原文过长，此处截断，只保留前 %d 字）" % limit


# ---------------------------------------------------------------------------
# 异常分层
#
# 为什么要把 UsageError 与 CrewError 分开：这两类错误的**处理方式完全不同**。
# 参数错了要改命令重跑，不花一分钱（--outdir 指到包内、没报价就开跑）；
# 调用失败要查 Key / 点数 / 模型名。混成一个退出码，CI 里就没法区分。
# ---------------------------------------------------------------------------

class CrewError(a7w.A7wError):
    """生产 / 生成 / 调用失败（网络、鉴权、点数、模型名）。→ 退出码 4"""


class UsageError(CrewError):
    """参数/配置/环境用错了。→ 退出码 2"""


class GateError(CrewError):
    """闸门命中（本地确定性判定）。→ 退出码 3"""


class BudgetError(CrewError):
    """成本上限。→ 退出码 5"""


# ---------------------------------------------------------------------------
# 文本计费口径：**只出 token，禁止编价**
#
# 为什么本包不报金额：平台把图像/视频/语音的单价公布到生成应用的 schema 里，
# 但**文本网关的单价平台不公开**（`/api/v1/pricing` 不覆盖 chat/completions）。
# 报一个自己编的"每千 token 几分钱"就是编数据——所以本包：
#   · 每次都把 `usage` 原文打出来（prompt / completion / total token）
#   · `cost` 不给 `--points-per-ktok` 就**只报 token 数、不报金额**
#   · 给了 `--points-per-ktok` 也只是"按你给的价换算"，并在输出里标明这是外部口径
# ---------------------------------------------------------------------------

def usage_of(usage):
    u = usage or {}
    pt = u.get("prompt_tokens")
    ct = u.get("completion_tokens")
    tt = u.get("total_tokens")
    if tt is None and (pt is not None or ct is not None):
        tt = (pt or 0) + (ct or 0)
    return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}


def add_usage(acc, usage):
    u = usage_of(usage)
    acc["calls"] += 1
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if u[k] is not None:
            acc[k] = (acc.get(k) or 0) + u[k]
    acc.setdefault("raw", []).append(usage or {})
    return acc


def new_usage():
    return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "raw": []}


def points_of_tokens(tokens, points_per_ktok):
    """按**外部给定的**单价换算点数。单价不给就返回 None（不编价）。"""
    if not points_per_ktok or tokens is None:
        return None
    return round(float(tokens) / 1000.0 * float(points_per_ktok), 2)


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=6000, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见。
    一次抖动打断一集剧本要重跑整集，很亏。5xx 与网络类错误退避重试；
    4xx 是业务错误，直接报出来不浪费额度。

    成功响应**不带 `code` 字段**（实测），所以这里不判 code；只判 choices 在不在。
    `code == 1` 那套信封是**生成应用**的，不适用于本端点。
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
                raise CrewError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise CrewError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise CrewError(
                    "模型不存在（404）：{}  用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 429，{}s 后重试…\n".format(3 * (attempt + 1)))
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

    if payload is None:
        raise CrewError("网络错误：{}".format(last_exc))

    # 兜底：万一网关换了形态包了一层 {"code":1,"data":{...}}，两种都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise CrewError("模型没返回 choices：{}".format(
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
        raise CrewError("模型返回空内容")
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
    raise CrewError("模型返回的不是合法 JSON：{}".format(
        text[:300].replace("\n", " ")))


# ---------------------------------------------------------------------------
# 产出目录与断点续跑
# ---------------------------------------------------------------------------

def _resolve(p):
    return Path(p).expanduser().resolve()


def check_outdir(outdir):
    """`--outdir` 不许指到包内。

    **为什么这条是硬闸门而不是提醒**：本库的包要过 SkillHub 的文件类型白名单，
    包内出现任何产出（更别说图片/音视频）都会让整个包 400。产出本来就不该进包，
    所以这里**拒绝执行**（exit=2），不是"警告后继续"。
    """
    p = _resolve(outdir)
    try:
        p.relative_to(PKG_ROOT)
    except ValueError:
        return p
    raise UsageError(
        "拒绝执行：--outdir 指到了包内（%s）。\n"
        "  产出**一律不许进包**（包内只允许 %s）。\n"
        "  请换到包外目录，例如 %%TEMP%%\\drama-crew 或 D:/drama-crew/ep01。"
        % (p, " / ".join(sorted({'.md', '.py', '.txt', '.json', '.sh', '.js',
                                 '.yaml', '.yml', '.csv'}))))


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


# ---------------------------------------------------------------------------
# 断点 key：**必须含全部影响产出的维度**
#
# 本库其他包的教训是「key 少一维 → 改了东西却静默复用旧产出」。剧本创作这条链上，
# 影响一次产出结果的东西一共有 8 个维度：
#   1. 角色              writer / director / art / scripty
#   2. 阶段              outline / script / board / cards / continuity
#   3. 题材全文摘要      topic_sha  ← **剧本全文摘要**（上游剧本/大纲变了必须重出）
#   4. 轮次              round      ← 第几轮返修（同一份输入在不同轮次产出不同）
#   5. 角色提示词版本    prompt_ver ← 改了提示词必须失效
#   6. 模型              model
#   7. 温度              temperature
#   8. 上一轮裁决摘要    verdict_sha← 导演打回的理由变了，返修方向就变了
# 另加一个**产出侧自我描述**，不含在 key 里但落盘留档（便于事后复核为什么重跑）。
# ---------------------------------------------------------------------------

def bp_key(role, stage, upstream_text, rnd, prompt_ver, model, temperature, verdict_text):
    dims = {
        "role": role,
        "stage": stage,
        "topic_sha": text_hash(upstream_text or "")[:12],
        "round": int(rnd or 0),
        "prompt_ver": prompt_ver,
        "model": model,
        "temperature": round(float(temperature or 0), 3),
        "verdict_sha": text_hash(verdict_text or "")[:12],
    }
    blob = json.dumps(dims, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:20], dims


# ---------------------------------------------------------------------------
# 渲染（**闸门读的就是这些渲染后的成品文本**）
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "✗ " + s
    return "\x1b[31m%s\x1b[0m" % s


def render_outline_md(outline, meta=None):
    meta = meta or {}
    out = ["# 分集大纲 · %s" % (outline.get("title") or "（无标题）"), ""]
    meta_lines = []
    if meta.get("model"):
        meta_lines.append("- 编剧角色 · 模型：`%s`　端点：`POST /api/v1/chat/completions`"
                          % meta["model"])
    if meta.get("usage"):
        u = usage_of(meta["usage"])
        meta_lines.append("- token 用量：prompt=%s completion=%s total=%s"
                          % (u["prompt_tokens"], u["completion_tokens"], u["total_tokens"]))
    if meta.get("elapsed") is not None:
        meta_lines.append("- 耗时：%.1fs" % meta["elapsed"])
    if meta.get("round"):
        meta_lines.append("- 轮次：第 %s 轮" % meta["round"])
    if meta_lines:
        out.append("<!--")
        out.extend(meta_lines)
        out.append("-->")
    out.append("")
    if outline.get("logline"):
        out.append("> **一句话故事**：%s" % outline["logline"])
        out.append("")
    if outline.get("hook"):
        out.append("> **开场钩子**：%s" % outline["hook"])
        out.append("")
    if outline.get("audience"):
        out.append("> **目标受众**：%s" % outline["audience"])
        out.append("")
    out.append("## 分集大纲")
    out.append("")
    out.append("| 集 | 标题 | 本集钩子 | 卡点（第几分钟） | 集尾悬念 | 剧情要点 |")
    out.append("|---|---|---|---|---|---|")
    for e in outline.get("episodes") or []:
        pts = "<br>".join("· " + str(x) for x in (e.get("points") or []))
        out.append("| %s | %s | %s | %s | %s | %s |" % (
            e.get("no"), e.get("title") or "（缺）", e.get("hook") or "（缺）",
            e.get("paywall_at") or "（缺）", e.get("cliffhanger") or "（缺）", pts))
    out.append("")
    if outline.get("characters"):
        out.append("## 人物")
        out.append("")
        out.append("| 角色 | 性别 | 年龄 | 身份 | 关键特征 |")
        out.append("|---|---|---|---|---|")
        for c in outline["characters"]:
            out.append("| %s | %s | %s | %s | %s |" % (
                c.get("name") or "（缺）", c.get("gender") or "（缺）",
                c.get("age") or "（缺）", c.get("role") or "（缺）",
                c.get("desc") or "（缺）"))
        out.append("")
    return "\n".join(out)


def render_script_md(script, meta=None):
    meta = meta or {}
    out = ["# 剧本 · %s" % (script.get("title") or "（无标题）"), ""]
    meta_lines = []
    if meta.get("model"):
        meta_lines.append("- 编剧角色 · 模型：`%s`" % meta["model"])
    if meta.get("usage"):
        u = usage_of(meta["usage"])
        meta_lines.append("- token 用量：prompt=%s completion=%s total=%s"
                          % (u["prompt_tokens"], u["completion_tokens"], u["total_tokens"]))
    if meta.get("round"):
        meta_lines.append("- 轮次：第 %s 轮" % meta["round"])
    if meta.get("note"):
        meta_lines.append("- 返修说明：%s" % meta["note"])
    if meta_lines:
        out.append("<!--")
        out.extend(meta_lines)
        out.append("-->")
    out.append("")
    if script.get("characters"):
        out.append("## 人物表")
        out.append("")
        out.append("| 角色 | 性别 | 年龄 | 身份 | 关键特征 |")
        out.append("|---|---|---|---|---|")
        for c in script["characters"]:
            out.append("| %s | %s | %s | %s | %s |" % (
                c.get("name") or "（缺）", c.get("gender") or "（缺）",
                c.get("age") or "（缺）", c.get("role") or "（缺）",
                c.get("desc") or "（缺）"))
        out.append("")
    for e in script.get("episodes") or []:
        out.append("## 第 %s 集　%s" % (e.get("no"), e.get("title") or ""))
        out.append("")
        if e.get("cliffhanger"):
            out.append("> 集尾悬念：%s" % e["cliffhanger"])
            out.append("")
        for s in e.get("scenes") or []:
            out.append("### 第 %s 集 场 %s　%s　%s" % (
                e.get("no"), s.get("no"), s.get("slug") or "",
                s.get("location") or ""))
            out.append("")
            out.append("- 时间：%s　出场：%s" % (
                s.get("time") or "（缺）", "、".join(s.get("characters") or []) or "（缺）"))
            if s.get("beat"):
                out.append("- 本场作用：%s" % s["beat"])
            out.append("")
            for i, line in enumerate(s.get("lines") or [], 1):
                out.append("**%s**（%s）：%s" % (
                    line.get("who") or "（缺）", line.get("emotion") or "（缺）",
                    line.get("text") or "（缺）"))
                out.append("")
    return "\n".join(out)


def render_board_md(board, meta=None):
    meta = meta or {}
    out = ["# 分镜表 · %s" % (board.get("title") or "（无标题）"), ""]
    meta_lines = []
    if meta.get("model"):
        meta_lines.append("- 导演角色 · 模型：`%s`" % meta["model"])
    if meta.get("usage"):
        u = usage_of(meta["usage"])
        meta_lines.append("- token 用量：prompt=%s completion=%s total=%s"
                          % (u["prompt_tokens"], u["completion_tokens"], u["total_tokens"]))
    if meta.get("round"):
        meta_lines.append("- 轮次：第 %s 轮" % meta["round"])
    if meta_lines:
        out.append("<!--")
        out.extend(meta_lines)
        out.append("-->")
    v = board.get("verdict") or {}
    out.append("- **导演裁决：`%s`**" % (v.get("verdict") or "（缺）"))
    out.append("")
    if v.get("reasons"):
        out.append("**打回理由**（导演 → 编剧）")
        out.append("")
        for r in v["reasons"]:
            out.append("- %s" % r)
        out.append("")
    if v.get("unshootable"):
        out.append("**写不了的场次**")
        out.append("")
        for r in v["unshootable"]:
            out.append("- %s" % r)
        out.append("")
    for e in board.get("episodes") or []:
        out.append("## 第 %s 集" % e.get("no"))
        out.append("")
        out.append("| 镜 | 场 | 景别 | 机位 | 画面描述 | 时长(s) | 转场 | 台词/音效 |")
        out.append("|---|---|---|---|---|---|---|---|")
        for i, sh in enumerate(e.get("shots") or [], 1):
            ss = sh.get("shot_size_norm") or normalize_shot_size(sh.get("shot_size")) \
                or sh.get("shot_size") or "（缺）"
            cam = sh.get("camera_norm") or normalize_camera(sh.get("camera")) \
                or sh.get("camera") or "（缺）"
            out.append("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
                i, sh.get("scene_slug") or "（缺）", ss, cam,
                sh.get("visual") or "（缺）",
                sh.get("seconds") if sh.get("seconds") is not None else "（缺）",
                sh.get("transition") or "（缺）", sh.get("audio") or ""))
        out.append("")
    return "\n".join(out)


def render_art_md(art, meta=None):
    meta = meta or {}
    out = ["# 美术设定卡 · %s" % (art.get("title") or "（无标题）"), ""]
    out.append("> 本卡是**文本**设定，供既有出图包（如 `sanjianke-storyboard-art`）使用；"
               "本包**不出图**。")
    out.append("")
    meta_lines = []
    if meta.get("model"):
        meta_lines.append("- 美术角色 · 模型：`%s`" % meta["model"])
    if meta.get("usage"):
        u = usage_of(meta["usage"])
        meta_lines.append("- token 用量：prompt=%s completion=%s total=%s"
                          % (u["prompt_tokens"], u["completion_tokens"], u["total_tokens"]))
    if meta_lines:
        out.append("<!--")
        out.extend(meta_lines)
        out.append("-->")
    v = art.get("verdict") or {}
    out.append("- **美术裁决：`%s`**" % (v.get("verdict") or "（缺）"))
    out.append("")
    if v.get("reasons"):
        out.append("**否决理由**（美术 → 编剧/导演）")
        out.append("")
        for r in v["reasons"]:
            out.append("- %s" % r)
        out.append("")
    if v.get("scenes"):
        out.append("**拍不出来的场次**")
        out.append("")
        for r in v["scenes"]:
            out.append("- %s" % r)
        out.append("")
    out.append("## 角色视觉设定")
    out.append("")
    for c in art.get("characters") or []:
        out.append("### %s" % (c.get("name") or "（缺）"))
        out.append("")
        out.append("- 性别/年龄：%s / %s" % (c.get("gender") or "（缺）",
                                            c.get("age") or "（缺）"))
        out.append("- 外貌：%s" % (c.get("appearance") or "（缺）"))
        out.append("- 服装：%s" % (c.get("costume") or "（缺）"))
        out.append("- 可视觉特征词（**逐字可复述**）：%s"
                   % ("、".join(c.get("features") or []) or "（缺）"))
        out.append("- 参考色：%s" % ("、".join(
            "%s %s" % (p.get("name"), p.get("hex")) for p in (c.get("palette") or []))
            or "（缺）"))
        out.append("")
    out.append("## 场景视觉设定")
    out.append("")
    for s in art.get("scenes") or []:
        out.append("### %s" % (s.get("slug") or "（缺）"))
        out.append("")
        out.append("- 空间：%s" % (s.get("space") or "（缺）"))
        out.append("- 陈设/道具：%s" % ("、".join(s.get("props") or []) or "（缺）"))
        out.append("- 光线/氛围：%s" % (s.get("light") or "（缺）"))
        out.append("- 色彩：%s" % (s.get("palette") or "（缺）"))
        out.append("- 可产出性：%s%s" % (
            s.get("difficulty") or "（缺）",
            ("　说明：" + str(s.get("difficulty_why"))) if s.get("difficulty_why") else ""))
        out.append("")
    return "\n".join(out)


def render_continuity_md(cont, meta=None):
    meta = meta or {}
    out = ["# 矛盾清单 · %s" % (cont.get("title") or "（无标题）"), ""]
    out.append("> **场记的产出只有这一份矛盾清单**。每条矛盾都**引用剧本原文**——"
               "引文在本地逐字校验过，编造的引文已被剔出（见文末「被剔出的引文」）。")
    out.append("")
    meta_lines = []
    if meta.get("model"):
        meta_lines.append("- 场记角色 · 模型：`%s`" % meta["model"])
    if meta.get("usage"):
        u = usage_of(meta["usage"])
        meta_lines.append("- token 用量：prompt=%s completion=%s total=%s"
                          % (u["prompt_tokens"], u["completion_tokens"], u["total_tokens"]))
    st = cont.get("stats") or {}
    meta_lines.append("- 统计：%s 条矛盾（%s）" % (
        st.get("total"),
        "；".join("%s %s 条" % (k, v) for k, v in (st.get("by_severity") or {}).items())))
    v = cont.get("verdict") or {}
    meta_lines.append("- **场记裁决：`%s`**（中高等级矛盾 = 否决，必须修）"
                      % (v.get("verdict") or "（缺）"))
    out.append("<!--")
    out.extend(meta_lines)
    out.append("-->")
    out.append("")
    if not cont.get("conflicts"):
        out.append("✅ 未发现前后矛盾。")
        out.append("")
    for c in cont.get("conflicts") or []:
        out.append("### 矛盾 %s　[%s · %s]" % (c.get("no"), c.get("category") or "未分类",
                                              c.get("severity") or "未分级"))
        out.append("")
        out.append("- 位置：%s" % (c.get("where") or "（缺）"))
        out.append("- 原文引证：「%s」" % (c.get("quote") or "（缺）"))
        out.append("- 矛盾点：%s" % (c.get("problem") or "（缺）"))
        out.append("- 与什么冲突：%s" % (c.get("clash") or "（缺）"))
        out.append("- 必须怎么改：%s" % (c.get("fix") or "（缺）"))
        out.append("")
    dropped = cont.get("dropped") or []
    if dropped:
        out.append("## 被剔出的引文（本地校验未通过）")
        out.append("")
        out.append("> 下面这些条目**引文在剧本原文里找不到**，已按编造引文剔出、不计入矛盾数。")
        out.append("")
        for c in dropped:
            out.append("- 第 %s 条：%s　（引文「%s」）" % (
                c.get("no"), c.get("dropped_why") or "引文未通过校验",
                (c.get("quote") or "")[:30]))
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 提示词构造 —— **信息不对称就在这里落地**
#
# 四个角色的立场差异不是靠"你是导演，请严格一点"这种话术，而是靠**给它们不同的输入**：
#
#   编剧收到：题材 + 集数 + 一句话要求 +（第二轮的）导演/美术/场记打回意见
#             ❌ **收不到**导演的偏好、美术的产能约束、场记的历史台账
#   导演收到：剧本原文 + 上一轮自己的打回记录
#             ❌ **收不到**题材的自由发挥空间提示（只能基于已写出的剧本判断能不能拍）
#   美术收到：剧本里的**场次清单与出场人物**（**只有这些**）
#             ❌ **收不到**故事评价的邀请（提示词里明确禁止它评故事）
#   场记收到：剧本全文 + 分镜表
#             ❌ **收不到**任何改戏建议的邀请（只报矛盾）
#
# 每个角色的"输入摘要"会被打印出来（`--show-inputs`），用来**证明不对称真实存在**。
# ---------------------------------------------------------------------------

WRITER_SYSTEM = (
    "你是一名短剧编剧，只对一件事负责：**故事好不好看、钩子够不够**。\n"
    "你的产出物是分集大纲与剧本（场景/台词/情绪）。\n"
    "你**不做**这些判断（它们不是你的职权）：\n"
    "  · 这场戏能不能拍出来（导演的职权）\n"
    "  · 场景与服化道能不能产出（美术的职权）\n"
    "  · 前后是否矛盾（场记的职权）\n"
    "只输出 JSON，不要任何解释文字。"
)

DIRECTOR_SYSTEM = (
    "你是一名短剧导演，只对一件事负责：**节奏与可视化——这场戏能不能拍出来**。\n"
    "你的产出物是分镜表（景别/机位/时长/转场），并且你**有权打回编剧**。\n"
    "打回时必须说清**哪一场写不了、为什么写不了**——没有具体理由的打回不算打回。\n"
    "你**不改**故事走向与人物关系（那是编剧的职权），也**不管**服化道能不能做出来（美术的职权）。\n"
    "只输出 JSON，不要任何解释文字。"
)

ART_SYSTEM = (
    "你是一名美术。你只对一件事负责：**场景与服化道能不能产出、能不能保持一致**。\n"
    "你的产出物是**文本**形式的场景与角色视觉设定卡（供后续出图使用），本环节不出图。\n"
    "你**有权说「这场戏拍不出来」**并要求改——判断依据只能是**可产出性**：\n"
    "  · 需要大规模实景/群演/特效才能成立的场面\n"
    "  · 同一个场景在不同场次里空间结构自相矛盾，无法搭出来\n"
    "  · 角色视觉特征描述不足以稳定复现（说不清长什么样）\n"
    "你**不参与故事评价**（好不好看不是你的判断），也**不评**节奏与镜头（导演的职权）。\n"
    "⚠️ **角色卡必须出全**：清单里有名字的角色，每一个都要有一张卡——"
    "只出场一次的角色也要。漏一个，后续出图时没人知道该画谁。\n"
    "只输出 JSON，不要任何解释文字。"
)

SCRIPTY_SYSTEM = (
    "你是一名场记，只对一件事负责：**前后一致**——人物、时间线、道具、服装、空间、因果。\n"
    "你的产出物是**矛盾清单**，而且**每条矛盾必须引用剧本原文**（逐字照抄一小段）。\n"
    "**编造引文是最严重的错误**：引文会在本地逐字校验，找不到的条目会被整条剔出并公示。\n"
    "你不能提出改戏建议（怎么改是编剧的职权），也不能评价故事与镜头。\n"
    "只输出 JSON，不要任何解释文字。"
)


def _script_facts(script):
    """从剧本里抽出**场次清单与出场人物**——这是美术唯一能看到的剧本信息。

    为什么只给这些：美术的职权是"能不能产出"，它需要知道有哪些场、哪些人、什么空间；
    它**不需要**知道剧情好不好看。给它全文就等于邀请它评故事，那四个角色就退化成
    "四个都在评故事"——这正是 L2 假协作的典型形态。
    """
    scenes = []
    for e in script.get("episodes") or []:
        for s in e.get("scenes") or []:
            scenes.append({
                "episode": e.get("no"), "scene": s.get("no"),
                "slug": s.get("slug"), "location": s.get("location"),
                "time": s.get("time"), "characters": s.get("characters") or [],
                "beat": s.get("beat"),
            })
    chars = [{"name": c.get("name"), "gender": c.get("gender"), "age": c.get("age"),
              "role": c.get("role"), "desc": c.get("desc")}
             for c in (script.get("characters") or [])]
    return {"scenes": scenes, "characters": chars}


def build_outline_prompt(topic, episodes, audience=None, brief=None, notes=None,
                         round_no=1):
    p = []
    p.append("给下面这个短剧题材写**分集大纲**。")
    p.append("")
    p.append("题材：%s" % topic)
    p.append("集数：%s 集" % episodes)
    if audience:
        p.append("目标受众：%s" % audience)
    if brief:
        p.append("额外要求：%s" % brief)
    p.append("")
    p.append("每一集要有：一个能立刻抓人的**本集钩子**、一个**付费卡点**（写明第几分钟）、"
             "一个**集尾悬念**、以及 3~5 条剧情要点。")
    p.append("人物表要给出：姓名、性别、年龄段（用「青年/中年」这类词）、身份、关键特征。")
    if notes:
        p.append("")
        p.append("【上一轮被打回/否决的意见，这一轮必须正面处理】")
        for n in notes:
            p.append("- [%s] %s" % (n.get("role"), n.get("why")))
        p.append("只改被指出的地方，没被指出的地方**不要动**。")
    p.append("")
    p.append('输出 JSON：{"title": "剧名", "logline": "一句话故事", '
             '"hook": "开场钩子", "audience": "目标受众", '
             '"episodes": [{"no": 1, "title": "集名", "hook": "本集钩子", '
             '"paywall_at": "第3分钟", "cliffhanger": "集尾悬念", '
             '"points": ["要点1", "要点2"]}], '
             '"characters": [{"name": "姓名", "gender": "男/女", "age": "年龄段", '
             '"role": "身份", "desc": "关键特征"}]}')
    return "\n".join(p)


def build_script_prompt(outline_md, episodes, notes=None, prior_script_md=None,
                        round_no=1):
    p = []
    p.append("按下面这份分集大纲写**剧本**（第 %d 轮）。" % round_no)
    p.append("")
    p.append("【分集大纲】")
    p.append(_clip(outline_md, 6000))
    p.append("")
    p.append("每一场都要写清：场号、场名（slug，如 `雨夜街头`）、地点、时间、出场人物、"
             "本场作用（beat），以及**逐句台词**——每句台词标注说话人和情绪。")
    p.append("⚠️ **场名要短、要稳定**（2~6 个字，如「雨夜街头」「出租屋客厅」）。"
             "下游的分镜表**按场名挂镜**：场名一改，分镜就挂不上。"
             "**返修时不要改场名**，只改被指出的场次内容。")
    p.append("台词要口语、要有信息差与金句感；不要写旁白式说明。")
    if prior_script_md:
        p.append("")
        p.append("【你上一轮的剧本（本轮在它基础上返修）】")
        p.append(_clip(prior_script_md, 9000))
    if notes:
        p.append("")
        p.append("【必须正面处理的意见】")
        for n in notes:
            p.append("- [%s · %s] %s" % (n.get("role_cn") or n.get("role"),
                                         n.get("kind") or "", n.get("why")))
        p.append("返修要求：**逐条处理上面的意见**，只改被指出的地方；"
                 "没被指出的场次与台词**原样保留**，不要顺手重写全篇。")
    p.append("")
    p.append('输出 JSON：{"title": "剧名", '
             '"characters": [{"name": "姓名", "gender": "男/女", "age": "年龄段", '
             '"role": "身份", "desc": "关键特征"}], '
             '"episodes": [{"no": 1, "title": "集名", "cliffhanger": "集尾悬念", '
             '"scenes": [{"no": 1, "slug": "场名", "location": "地点", "time": "时间", '
             '"characters": ["出场人物"], "beat": "本场作用", '
             '"lines": [{"who": "说话人", "emotion": "情绪", "text": "台词"}]}]}]}')
    return "\n".join(p)


def build_board_prompt(script_md, rounds_notes=None, round_no=1):
    p = []
    p.append("把下面这份剧本拆成**分镜表**（第 %d 轮）。" % round_no)
    p.append("")
    p.append("【剧本】")
    p.append(_clip(script_md, 14000))
    p.append("")
    p.append("每一镜必须有：**景别**（%s）、**机位**（%s）、**画面描述**（不少于 8 个字，"
             "要能直接照着拍）、**时长（秒）**、**转场**（%s）、以及这一镜的台词或音效。"
             % (" / ".join(SHOT_SIZES), " / ".join(CAMERAS), " / ".join(TRANSITIONS)))
    p.append("单镜时长落在 %d~%d 秒；每场 %d~%d 镜。"
             % (CREW["shot_seconds"][0], CREW["shot_seconds"][1],
                CREW["shots_per_scene"][0], CREW["shots_per_scene"][1]))
    p.append("")
    p.append("**你的职权**：如果某一场的写法在镜头层面根本立不住"
             "（例如整场只有内心活动、没有可拍的动作；或一场里塞了十几个物理上无法"
             "在同一时空完成的动作；或节奏上一场戏没有任何可切分的镜头），"
             "就**打回编剧**：verdict 填 `reject`，并在 `unshootable` 里逐条写明"
             "「第几集第几场 为什么写不了」，在 `reasons` 里给出可读理由。")
    p.append("打回时**仍然要给出分镜表**——但要标出哪些镜是你为了指出问题而勉强写的。")
    p.append("能拍就填 `approve`，此时 `reasons` 与 `unshootable` 留空数组。")
    if rounds_notes:
        p.append("")
        p.append("【你上一轮的打回记录（本轮复核编剧是否真的改了）】")
        for n in rounds_notes:
            p.append("- %s" % n)
    p.append("")
    p.append('输出 JSON：{"title": "剧名", '
             '"verdict": {"verdict": "approve|reject", "reasons": ["理由"], '
             '"unshootable": ["第1集第2场 ……"]}, '
             '"episodes": [{"no": 1, "shots": [{"episode": 1, "scene_slug": "场名", '
             '"shot_size": "景别", "camera": "机位", "visual": "画面描述", '
             '"seconds": 4, "transition": "转场", "audio": "台词或音效"}]}]}')
    return "\n".join(p)


def build_art_prompt(facts, rounds_notes=None, round_no=1):
    p = []
    p.append("下面是这部剧的**场次清单与出场人物**（第 %d 轮）。" % round_no)
    p.append("")
    p.append("【场次与人物】")
    p.append(_clip(json.dumps(facts, ensure_ascii=False, indent=1), 12000))
    p.append("")
    names = [canonical_name(c.get("name"))
             for c in (facts.get("characters") or []) if c.get("name")]
    if names:
        p.append("**角色卡必须出全，一个都不能漏**（含只出场一次的角色）——"
                 "后续出图全靠这张卡当凭据，本地闸门会逐名核对。")
        p.append("要出卡的角色名一共 %d 个，**下面这一行就是硬清单**，"
                 "请逐名建卡、名字照抄：%s" % (len(names), "、".join(names)))
        p.append("自检一遍：上面每个名字，在 characters 数组里都能找到同名的一项吗？"
                 "缺哪个补哪个。**只出场一次的配角（医生、打手、保安、律师…）同样要卡**"
                 "——它们一样会出现在画面上，没有卡就没有视觉凭据。"
                 "名字里带舞台提示的（如「阿深（电话）」）按主干名建卡：「阿深」。")
    p.append("请产出**可产出的**场景与角色视觉设定卡（文本）：")
    p.append("  · 角色卡：性别、年龄段、外貌、服装、**可视觉特征词**（4~8 条，每条 4~12 字，"
             "只写看得见的东西，不写情绪）、参考色（名称 + 十六进制）")
    p.append("  · 场景卡：空间结构、陈设道具、光线氛围、色彩、**可产出性**"
             "（`easy` / `medium` / `hard`）与理由")
    p.append("")
    p.append("**你的职权**：如果某一场按上面的写法**拍不出来**（需要大规模实景、群演、"
             "高成本特效；或同一场景在不同场次里空间自相矛盾；或角色特征说不清、"
             "后续出图必然漂移），就判 `not_producible`：在 `scenes` 里逐条列出"
             "**哪一场、为什么拍不出来**，在 `reasons` 里给可读理由。")
    p.append("你**不评价故事好不好看**，也不评节奏与镜头——那都不是你的职权。")
    if rounds_notes:
        p.append("")
        p.append("【你上一轮的否决记录（本轮复核是否真的改了）】")
        for n in rounds_notes:
            p.append("- %s" % n)
    p.append("")
    p.append('输出 JSON：{"title": "剧名", '
             '"verdict": {"verdict": "producible|not_producible", "reasons": ["理由"], '
             '"scenes": ["第1集第2场 ……"]}, '
             '"characters": [{"name": "姓名", "gender": "男/女", "age": "年龄段", '
             '"appearance": "外貌", "costume": "服装", '
             '"features": ["特征词"], "palette": [{"name": "色名", "hex": "#000000"}]}], '
             '"scenes": [{"slug": "场名", "space": "空间结构", "props": ["道具"], '
             '"light": "光线氛围", "palette": "色彩", "difficulty": "easy|medium|hard", '
             '"difficulty_why": "理由"}]}')
    return "\n".join(p)


def build_continuity_prompt(script_md, board_md=None, prior=None, round_no=1):
    p = []
    p.append("下面是一部短剧的**剧本**（第 %d 轮）。" % round_no)
    p.append("")
    p.append("【剧本】")
    p.append(_clip(script_md, 14000))
    if board_md:
        p.append("")
        p.append("【分镜表】（用来核对同一场戏在分镜里有没有写出与剧本不同的设定）")
        p.append(_clip(board_md, 7000))
    p.append("")
    p.append("请逐场核对**前后一致性**，分类只能是：%s。" % " / ".join(CONTINUITY_CATEGORIES))
    p.append("")
    p.append("**铁律**：每条矛盾都必须给 `quote` 字段，内容是**从上面剧本里逐字照抄**的"
             "一小段原文（8~40 字，必须能在剧本里原样找到）。")
    p.append("引文会在本地逐字校验：**找不到的条目会被整条剔出并公示为「编造引文」**。")
    p.append("不要为了凑数而报矛盾；没有矛盾就返回空数组——**空数组是合格产出**。")
    p.append("等级口径：`高` = 会直接让观众出戏（人物身份/生死/时间线冲突）；"
             "`中` = 会让细心观众发现（道具/服装/空间冲突）；`低` = 瑕疵（措辞/称呼不一致）。")
    p.append("中高等级矛盾 = **否决**（verdict 填 `blocking`），低等级填 `clear`。")
    if prior:
        p.append("")
        p.append("【上一轮你报过的矛盾（本轮复核是否真的改了）】")
        for c in prior:
            p.append("- 第%s条 [%s] 引文「%s」→ %s"
                     % (c.get("no"), c.get("category"), (c.get("quote") or "")[:20],
                        c.get("problem")))
    p.append("")
    p.append('输出 JSON：{"title": "剧名", '
             '"verdict": {"verdict": "clear|blocking"}, '
             '"conflicts": [{"category": "人物", "severity": "高|中|低", '
             '"where": "第1集 场2", "quote": "逐字引文", "problem": "矛盾点", '
             '"clash": "与什么冲突", "fix": "必须怎么改"}]}')
    return "\n".join(p)


# ---------------------------------------------------------------------------
# 归一化（把模型的随手 JSON 收拾成本包的结构）
# ---------------------------------------------------------------------------

def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _as_str_list(v):
    out = []
    for x in _as_list(v):
        if isinstance(x, dict):
            x = x.get("text") or x.get("why") or x.get("title") or ""
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out


def normalize_outline(raw, episodes):
    o = raw if isinstance(raw, dict) else {}
    eps = []
    for i, e in enumerate(_as_list(o.get("episodes")), 1):
        if not isinstance(e, dict):
            continue
        eps.append({
            "no": e.get("no") or i,
            "title": (e.get("title") or "").strip(),
            "hook": (e.get("hook") or "").strip(),
            "paywall_at": str(e.get("paywall_at") or "").strip(),
            "cliffhanger": (e.get("cliffhanger") or "").strip(),
            "points": _as_str_list(e.get("points")),
        })
    chars = []
    for c in _as_list(o.get("characters")):
        if not isinstance(c, dict):
            continue
        chars.append({"name": (c.get("name") or "").strip(),
                      "gender": (c.get("gender") or "").strip(),
                      "age": (c.get("age") or "").strip(),
                      "role": (c.get("role") or "").strip(),
                      "desc": (c.get("desc") or "").strip()})
    return {"title": (o.get("title") or "").strip(),
            "logline": (o.get("logline") or "").strip(),
            "hook": (o.get("hook") or "").strip(),
            "audience": (o.get("audience") or "").strip(),
            "episodes": eps, "characters": chars,
            "episodes_wanted": episodes}


def normalize_script(raw):
    o = raw if isinstance(raw, dict) else {}
    chars = []
    for c in _as_list(o.get("characters")):
        if not isinstance(c, dict):
            continue
        chars.append({"name": (c.get("name") or "").strip(),
                      "gender": (c.get("gender") or "").strip(),
                      "age": (c.get("age") or "").strip(),
                      "role": (c.get("role") or "").strip(),
                      "desc": (c.get("desc") or "").strip()})
    eps = []
    for i, e in enumerate(_as_list(o.get("episodes")), 1):
        if not isinstance(e, dict):
            continue
        scenes = []
        for j, s in enumerate(_as_list(e.get("scenes")), 1):
            if not isinstance(s, dict):
                continue
            lines = []
            for ln in _as_list(s.get("lines")):
                if isinstance(ln, dict):
                    lines.append({"who": (ln.get("who") or "").strip(),
                                  "emotion": (ln.get("emotion") or "").strip(),
                                  "text": (ln.get("text") or "").strip()})
                elif str(ln or "").strip():
                    lines.append({"who": "", "emotion": "", "text": str(ln).strip()})
            scenes.append({
                "no": s.get("no") or j,
                "slug": (s.get("slug") or "").strip(),
                "location": (s.get("location") or "").strip(),
                "time": (s.get("time") or "").strip(),
                "characters": _as_str_list(s.get("characters")),
                "beat": (s.get("beat") or "").strip(),
                "lines": lines,
            })
        eps.append({"no": e.get("no") or i, "title": (e.get("title") or "").strip(),
                    "cliffhanger": (e.get("cliffhanger") or "").strip(),
                    "scenes": scenes})
    return {"title": (o.get("title") or "").strip(), "characters": chars,
            "episodes": eps}


def normalize_board(raw, script=None):
    o = raw if isinstance(raw, dict) else {}
    v = o.get("verdict") if isinstance(o.get("verdict"), dict) else {}
    verdict = {"verdict": (v.get("verdict") or "").strip(),
               "reasons": _as_str_list(v.get("reasons")),
               "unshootable": _as_str_list(v.get("unshootable"))}
    eps = []
    for i, e in enumerate(_as_list(o.get("episodes")), 1):
        if not isinstance(e, dict):
            continue
        shots = []
        for s in _as_list(e.get("shots")):
            if not isinstance(s, dict):
                continue
            secs = _to_seconds(s.get("seconds"))
            shots.append({
                "episode": s.get("episode") or e.get("no") or i,
                "scene_slug": (s.get("scene_slug") or s.get("scene") or "").strip(),
                "shot_size": (s.get("shot_size") or "").strip(),
                "shot_size_norm": normalize_shot_size(s.get("shot_size")),
                "camera": (s.get("camera") or "").strip(),
                "camera_norm": normalize_camera(s.get("camera")),
                "visual": (s.get("visual") or "").strip(),
                "seconds": secs if secs is not None else s.get("seconds"),
                "transition": (s.get("transition") or "").strip(),
                "audio": (s.get("audio") or "").strip(),
            })
        eps.append({"no": e.get("no") or i, "shots": shots})
    return {"title": (o.get("title") or "").strip(), "verdict": verdict, "episodes": eps}


def normalize_art(raw):
    o = raw if isinstance(raw, dict) else {}
    v = o.get("verdict") if isinstance(o.get("verdict"), dict) else {}
    verdict = {"verdict": (v.get("verdict") or "").strip(),
               "reasons": _as_str_list(v.get("reasons")),
               "scenes": _as_str_list(v.get("scenes"))}
    chars = []
    for c in _as_list(o.get("characters")):
        if not isinstance(c, dict):
            continue
        pal = []
        for p in _as_list(c.get("palette")):
            if isinstance(p, dict):
                pal.append({"name": (p.get("name") or "").strip(),
                            "hex": (p.get("hex") or "").strip()})
            elif str(p or "").strip():
                pal.append({"name": str(p).strip(), "hex": ""})
        chars.append({"name": (c.get("name") or "").strip(),
                      "gender": (c.get("gender") or "").strip(),
                      "age": (c.get("age") or "").strip(),
                      "appearance": (c.get("appearance") or "").strip(),
                      "costume": (c.get("costume") or "").strip(),
                      "features": _as_str_list(c.get("features")),
                      "palette": pal})
    scenes = []
    for s in _as_list(o.get("scenes")):
        if not isinstance(s, dict):
            continue
        scenes.append({"slug": (s.get("slug") or "").strip(),
                       "space": (s.get("space") or "").strip(),
                       "props": _as_str_list(s.get("props")),
                       "light": (s.get("light") or "").strip(),
                       "palette": (s.get("palette") or "").strip(),
                       "difficulty": (s.get("difficulty") or "").strip(),
                       "difficulty_why": (s.get("difficulty_why") or "").strip()})
    return {"title": (o.get("title") or "").strip(), "verdict": verdict,
            "characters": chars, "scenes": scenes}


def normalize_continuity(raw, script_md):
    o = raw if isinstance(raw, dict) else {}
    v = o.get("verdict") if isinstance(o.get("verdict"), dict) else {}
    raw_conf = [c for c in _as_list(o.get("conflicts")) if isinstance(c, dict)]
    kept, dropped, problems = continuity_gate(raw_conf, script_md)
    stats = continuity_stats(kept)
    # 裁决与矛盾必须自洽。
    #
    # 【闸门七：有否决却拿不出矛盾 → 拦】这是**自相矛盾的裁决**：
    #   场记说"我否决"，但矛盾清单是空的。两种可能，都是硬问题——
    #   (a) 它没有真的逐场核对，只是走了个"我否了"的形式；
    #   (b) 它报了矛盾但引文全部编造，被闸门四剔光了。
    #   无论哪种，都不能当成"场记行使了否决权"。这里的处置是：
    #   **给出问题时一个都不降级**——报出来，由 CLI 以 exit=3 拦下；
    #   若确实没矛盾（decl 本来就是 clear），那才是正常放行。
    # ⚠️ 这一段的 `decl` 必须在**任何就地纠正之前**取出来：纠正会把 blocking 改写成
    #   clear，纠正之后再判就永远判不出来（写这段时自己踩到的顺序坑）。
    decl_raw = (v.get("verdict") or "").strip()
    if decl_raw == "blocking" and not stats["blocking"]:
        problems.append(
            "场记给的是否决（blocking），但经过引文校验后**一条中高等级矛盾都没有**"
            "（原生 %d 条、有效 %d 条、其中中高等级 %d 条、因编造引文剔出 %d 条）——"
            "「否决」与「至少一条中高等级矛盾」必须同时成立，"
            "否则这不是行使否决权，只是走了个形式"
            % (len(raw_conf), stats["total"], stats["blocking"], len(dropped)))
    # 其余不自洽就地纠正并登记（不静默改，写在 verdict.auto 里）。
    auto = None
    real = "blocking" if stats["blocking"] else "clear"
    decl = decl_raw
    if decl not in VERDICTS["scripty"]:
        auto = "裁决缺失或非法（%r），按矛盾清单就地判定为 `%s`" % (decl, real)
        decl = real
    elif decl != real:
        auto = "裁决（`%s`）与矛盾清单（%d 条中高等级）不一致，按矛盾清单就地判定为 `%s`" \
               % (decl, stats["blocking"], real)
        decl = real
    verdict = {"verdict": decl, "auto": auto}
    return {"title": (o.get("title") or "").strip(),
            "verdict": verdict, "conflicts": kept, "dropped": dropped,
            "gate_problems": problems, "stats": stats}


# ---------------------------------------------------------------------------
# 一致性闸门（闸门一~三 + 占位符）对**产出文本**的统一扫描
# ---------------------------------------------------------------------------

def compliance_scan(text, show_redlines=True):
    """扫一遍广告法违禁词 + 短剧常见风险。返回命中列表（按等级排序）。

    ⚠️ 扫的是**去元信息、去逐字引文之后**的正文（见 strip_meta / strip_quotes 的说明）。
    """
    text = strip_quotes(strip_meta(text or ""))
    hits = []
    for rx, level, why, tag in BANNED_RE:
        for m in rx.finditer(text or ""):
            if tag == "superlative" and _is_data_extreme(text, m):
                hits.append({"level": level, "match": m.group(0), "why": why,
                             "exempt": True,
                             "exempt_why": "计量名词 + 「的/之」语境，判为描述数据极值"})
                continue
            if tag == "superlative" and _is_person_extreme(text, m):
                hits.append({"level": level, "match": m.group(0), "why": why,
                             "exempt": True,
                             "exempt_why": "「最X的」+ 人物类名词，判为剧情叙事（说人）"})
                continue
            hits.append({"level": level, "match": m.group(0), "why": why,
                         "exempt": False})
    hits.sort(key=lambda h: (LEVEL_ORDER.get(h["level"], 9), h["match"]))
    return hits


def placeholder_scan(text):
    text = strip_meta(text or "")
    hits = []
    for rx, why in PLACEHOLDER_RE:
        m = rx.search(text or "")
        if m:
            hits.append({"match": m.group(0)[:30], "why": why})
    return hits


# 元信息块：渲染时用 HTML 注释包起来的行（模型/用量/轮次/返修说明）。
# 为什么要把它们排除在正文扫描之外：这些**不是剧本内容**，是我们自己加的表头。
# 不排除的实测后果是"自己拦自己"——闸门把渲染器写的
# 「> 本卡是**文本**设定，供既有出图包使用；本包**不出图**」判成
# 命中「唯一」（因为句子里有"唯一"两个字），于是一份完全合格的设定卡被整卡拦截。
# 教训是通用的：**闸门只能扫产出内容，不能扫产出周围的元信息。**
_META_RE = re.compile(r"<!--.*?-->", re.S)
# 逐字引文行：矛盾清单里 `- 原文引证：「…」` 与分镜表里的台词列。
# 引文的作用是**可核对**（本地逐字校验过），它本身不是要发布的内容文案；
# 把引文也拿去扫合规，会让"引一段带敏感词的原文来说明矛盾"这件事变成不可能。
_QUOTE_RE = re.compile(r"原文引证：「[^」]*」")


def strip_meta(text):
    """去掉元信息注释块，只留产出正文。"""
    return _META_RE.sub("", text or "")


def strip_quotes(text):
    """去掉逐字引文，只留其余正文。"""
    return _QUOTE_RE.sub("「（引文）」", text or "")


def text_gates(text, label="产出"):
    """闸门一/二/三的统一入口。返回 (problems, detail)。"""
    problems = []
    detail = {}
    comp = compliance_scan(text)
    real = [h for h in comp if not h.get("exempt")]
    exempt = [h for h in comp if h.get("exempt")]
    if real:
        detail["compliance"] = real
        for h in real[:3]:
            problems.append("合规命中【%s】「%s」：%s" % (h["level"], h["match"], h["why"]))
        if len(real) > 3:
            problems.append("合规还有 %d 处命中（见 --json 的 gates.compliance）"
                            % (len(real) - 3))
    if exempt:
        detail["compliance_exempted"] = exempt
    ph = placeholder_scan(text)
    if ph:
        detail["placeholder"] = ph
        for h in ph[:3]:
            problems.append("占位符残留：%s（%s）" % (h["match"], h["why"]))
    echo = prompt_echo_scan(text, label=label)
    if echo:
        detail["prompt_echo"] = echo
        for h in echo[:2]:
            problems.append("照抄提示词示例：%s" % h["why"])
    return problems, detail


# ---------------------------------------------------------------------------
# 四个角色的调用封装
#
# 每个 `_produce_*` 都做同样四件事：算断点 key → 命中缓存就跳过（省钱）→ 否则调模型
# → 归一并过闸门。断点命中时打印**为什么命中**（key 的八维摘要），
# 免得出现"改了东西却静默复用"这种本库踩过的坑。
# ---------------------------------------------------------------------------

def _cache_lookup(state, key, invalidate=False):
    rec = (state.get("breakpoints") or {}).get(key)
    if not rec or invalidate:
        return None
    return rec.get("payload")


def _cache_store(state, key, dims, payload, label):
    state.setdefault("breakpoints", {})[key] = {
        "dims": dims, "label": label, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "payload": payload,
    }


def _run_chat(prompt, system, a, usage_acc, role, stage):
    """发一次请求（含 dry-run 与提示词卫生自检）。返回 (raw_obj, usage, elapsed)。"""
    hy = prompt_hygiene(prompt)
    if hy:
        raise GateError("提示词卫生自检失败（%s.%s）：提示词里混进了可照抄的示例或脏占位\n"
                        "  %s" % (role, stage, json.dumps(hy, ensure_ascii=False)[:300]))
    if getattr(a, "dry_run", False):
        return None, {}, 0.0
    stub = _stub_dir()
    if stub:
        # ---- 测试用桩：**只有显式设了环境变量才生效**，正常使用永不触发 ----
        # 为什么不放一个"离线模式"开关进产品：闸门的行为必须能被零成本复现，
        # 但一个能绕过真实调用的产品开关会让人拿假产出当真产出。
        # 所以这里只认环境变量，并且桩会**自己声明**（raw 里带 stub 标记）。
        path = Path(stub) / ("%s.%s.json" % (role, stage))
        if not path.is_file():
            raise CrewError("测试桩缺失：%s（设了 DCP_MODEL_STUB 就必须为每个 "
                            "role.stage 准备桩文件）" % path)
        obj = json.loads(path.read_text(encoding="utf-8"))
        usage = {"prompt_tokens": 800, "completion_tokens": 1200, "total_tokens": 2000,
                 "stub": True}
        add_usage(usage_acc, usage)
        _budget_guard(a, usage_acc, "剧组协作 run")
        return obj, usage, 0.0
    t0 = time.time()
    content, usage = chat(prompt, system=system, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=getattr(a, "key", None),
                          json_mode=not getattr(a, "no_json_mode", False))
    elapsed = time.time() - t0
    add_usage(usage_acc, usage)
    # 每次调用后立刻查预算（止损要发生在钱花出去之后的第一时间）
    _budget_guard(a, usage_acc, "剧组协作 run")
    return parse_first_json(content), usage, elapsed


def _stub_dir():
    """测试桩目录（环境变量 `DCP_MODEL_STUB`）。**正常使用返回 None。**"""
    d = os.environ.get("DCP_MODEL_STUB")
    if d and Path(d).is_dir():
        return d
    return None


def produce_outline(a, state, usage_acc, upstream_text, round_no, notes=None):
    prompt = build_outline_prompt(a.topic, a.episodes, audience=a.audience,
                                 brief=a.brief, notes=notes, round_no=round_no)
    vkey = json.dumps(notes or [], ensure_ascii=False, sort_keys=True)
    key, dims = bp_key("writer", "outline", upstream_text, round_no,
                       PROMPT_VERSION["writer.outline"], a.model, a.temperature, vkey)
    cached = _cache_lookup(state, key, getattr(a, "force", False))
    if cached is not None:
        sys.stderr.write("断点命中：编剧·大纲（第 %s 轮）跳过调用，0 点\n  key=%s\n"
                         "  维度：%s\n" % (round_no, key, json.dumps(dims, ensure_ascii=False)))
        return cached, {}, 0.0, prompt, key, dims, True
    raw, usage, elapsed = _run_chat(prompt, WRITER_SYSTEM, a, usage_acc, "writer", "outline")
    if raw is None:
        return None, {}, 0.0, prompt, key, dims, False
    obj = normalize_outline(raw, a.episodes)
    md = render_outline_md(obj, {"model": a.model, "usage": usage, "elapsed": elapsed,
                                 "round": round_no})
    _cache_store(state, key, dims, {"obj": obj, "md": md}, "writer.outline")
    return {"obj": obj, "md": md}, usage, elapsed, prompt, key, dims, False


def produce_script(a, state, usage_acc, upstream_text, round_no, notes=None,
                   prior_md=None):
    prompt = build_script_prompt(upstream_text, a.episodes, notes=notes,
                                 prior_script_md=prior_md, round_no=round_no)
    vkey = json.dumps(notes or [], ensure_ascii=False, sort_keys=True)
    key, dims = bp_key("writer", "script", upstream_text + "|" + (prior_md or ""),
                       round_no, PROMPT_VERSION["writer.script"], a.model,
                       a.temperature, vkey)
    cached = _cache_lookup(state, key, getattr(a, "force", False))
    if cached is not None:
        sys.stderr.write("断点命中：编剧·剧本（第 %s 轮）跳过调用，0 点\n  key=%s\n"
                         "  维度：%s\n" % (round_no, key, json.dumps(dims, ensure_ascii=False)))
        return cached, {}, 0.0, prompt, key, dims, True
    raw, usage, elapsed = _run_chat(prompt, WRITER_SYSTEM, a, usage_acc, "writer", "script")
    if raw is None:
        return None, {}, 0.0, prompt, key, dims, False
    obj = normalize_script(raw)
    md = render_script_md(obj, {"model": a.model, "usage": usage, "round": round_no,
                                "note": ("针对上一轮意见返修" if notes else None)})
    _cache_store(state, key, dims, {"obj": obj, "md": md}, "writer.script")
    return {"obj": obj, "md": md}, usage, elapsed, prompt, key, dims, False


def produce_board(a, state, usage_acc, script_md, round_no, rounds_notes=None):
    prompt = build_board_prompt(script_md, rounds_notes=rounds_notes, round_no=round_no)
    vkey = json.dumps(rounds_notes or [], ensure_ascii=False, sort_keys=True)
    key, dims = bp_key("director", "board", script_md, round_no,
                       PROMPT_VERSION["director.board"], a.model, a.temperature, vkey)
    cached = _cache_lookup(state, key, getattr(a, "force", False))
    if cached is not None:
        sys.stderr.write("断点命中：导演·分镜表（第 %s 轮）跳过调用，0 点\n  key=%s\n"
                         "  维度：%s\n" % (round_no, key, json.dumps(dims, ensure_ascii=False)))
        return cached, {}, 0.0, prompt, key, dims, True
    raw, usage, elapsed = _run_chat(prompt, DIRECTOR_SYSTEM, a, usage_acc,
                                    "director", "board")
    if raw is None:
        return None, {}, 0.0, prompt, key, dims, False
    obj = normalize_board(raw)
    md = render_board_md(obj, {"model": a.model, "usage": usage, "round": round_no})
    _cache_store(state, key, dims, {"obj": obj, "md": md}, "director.board")
    return {"obj": obj, "md": md}, usage, elapsed, prompt, key, dims, False


def produce_art(a, state, usage_acc, facts, round_no, rounds_notes=None):
    upstream = json.dumps(facts, ensure_ascii=False, sort_keys=True)
    prompt = build_art_prompt(facts, rounds_notes=rounds_notes, round_no=round_no)
    vkey = json.dumps(rounds_notes or [], ensure_ascii=False, sort_keys=True)
    key, dims = bp_key("art", "cards", upstream, round_no,
                       PROMPT_VERSION["art.cards"], a.model, a.temperature, vkey)
    cached = _cache_lookup(state, key, getattr(a, "force", False))
    if cached is not None:
        sys.stderr.write("断点命中：美术·设定卡（第 %s 轮）跳过调用，0 点\n  key=%s\n"
                         "  维度：%s\n" % (round_no, key, json.dumps(dims, ensure_ascii=False)))
        return cached, {}, 0.0, prompt, key, dims, True
    raw, usage, elapsed = _run_chat(prompt, ART_SYSTEM, a, usage_acc, "art", "cards")
    if raw is None:
        return None, {}, 0.0, prompt, key, dims, False
    obj = normalize_art(raw)
    md = render_art_md(obj, {"model": a.model, "usage": usage})
    _cache_store(state, key, dims, {"obj": obj, "md": md}, "art.cards")
    return {"obj": obj, "md": md}, usage, elapsed, prompt, key, dims, False


def produce_continuity(a, state, usage_acc, script_md, board_md, round_no, prior=None):
    upstream = script_md + "|" + (board_md or "")
    prompt = build_continuity_prompt(script_md, board_md=board_md, prior=prior,
                                     round_no=round_no)
    vkey = json.dumps(prior or [], ensure_ascii=False, sort_keys=True)
    key, dims = bp_key("scripty", "continuity", upstream, round_no,
                       PROMPT_VERSION["scripty.continuity"], a.model, a.temperature, vkey)
    cached = _cache_lookup(state, key, getattr(a, "force", False))
    if cached is not None:
        sys.stderr.write("断点命中：场记·矛盾清单（第 %s 轮）跳过调用，0 点\n  key=%s\n"
                         "  维度：%s\n" % (round_no, key, json.dumps(dims, ensure_ascii=False)))
        return cached, {}, 0.0, prompt, key, dims, True
    raw, usage, elapsed = _run_chat(prompt, SCRIPTY_SYSTEM, a, usage_acc,
                                    "scripty", "continuity")
    if raw is None:
        return None, {}, 0.0, prompt, key, dims, False
    obj = normalize_continuity(raw, script_md)
    md = render_continuity_md(obj, {"model": a.model, "usage": usage})
    _cache_store(state, key, dims, {"obj": obj, "md": md}, "scripty.continuity")
    return {"obj": obj, "md": md}, usage, elapsed, prompt, key, dims, False


# ---------------------------------------------------------------------------
# 闸门八之一：成本前置（报价 → --yes / --budget → 累计对账）
#
# 为什么报价与预算是**两道**而不是一道：
#   · 没有报价就开跑 = 用户不知道要花多少，被动扣费；
#   · 有报价没预算 = 报价算漏了就会一路花下去。
# 口径：跑前必须报价，且**要么 --yes 明确同意，要么 --budget 封顶**。
# 两个都没有 → exit=2（参数错误），一次调用都不发。
#
# ⚠️ 文本网关的单价平台不公开，所以本包**只报 token 与调用次数、不报金额**。
#    给了 `--points-per-ktok` 才按外部口径折算点数，并在输出里标明那是外部口径。
# ---------------------------------------------------------------------------

def quote_run(episodes, max_rounds, points_per_ktok=None):
    """按"每轮 5 次调用"报价（编剧 2 次 + 导演 / 美术 / 场记 各 1 次）。

    为什么是 5 而不是 4：编剧在一轮里要出**两件**东西（大纲 + 剧本），
    这是本包刻意的取舍——大纲与剧本分开出，才能在大纲阶段就被打回，
    而不是等整篇剧本写完才发现方向不对。
    """
    per_round = 5
    calls = per_round * max(1, int(max_rounds))
    est = {
        "episodes": episodes, "max_rounds": max_rounds,
        "calls_per_round": per_round, "calls_est": calls,
        "roles_per_round": {"writer": 2, "director": 1, "art": 1, "scripty": 1},
        "token_hint": "单次调用实测在 1.5k~6k total token 之间（随集数与剧本长度变化）",
        "points": None, "yuan": None,
        "pricing_note": ("文本网关**不公布单价** → 本包不报金额，只报调用次数与 token。"
                         "给 --points-per-ktok 才按你给的口径折算。"),
        "budget_note": ("`--budget` 的点数闸门只在同时给了 `--points-per-ktok` 时才按点数判；"
                        "没给口径时**不编换算率**，改按**调用次数**守。"),
    }
    if points_per_ktok:
        est["points_per_ktok"] = points_per_ktok
        est["points"] = None
        est["points_formula"] = "total_tokens / 1000 × %s" % points_per_ktok
    return est


def _budget_check(a, spent_points, label):
    """跑前与跑中的预算闸门。返回剩余额度（None = 无上限但有 --yes）。"""
    budget = getattr(a, "budget", None)
    if budget is None:
        return None
    if spent_points is not None and spent_points > budget:
        raise BudgetError("%s 已超预算：已花 %.2f 点 > 上限 %.2f 点（就地中止）"
                          % (label, spent_points, budget))
    return budget


def _budget_guard(a, usage_acc, label):
    """**每次模型调用之后**就查预算。

    为什么不能只在每轮末尾查：实测过——`--budget 0` 时整轮 5 次调用已经发出去了，
    回来才报超限。预算闸门的意义是**止损**，跑完一轮才发现等于没有闸门。
    口径：给了 `--points-per-ktok` 就按 token 折点数判；没给口径时**不编换算率**，
    改按"调用次数"判（`--budget` 此时被当作次数上限），并在报错里说清楚。
    """
    if getattr(a, "budget", None) is None:
        return
    pts = points_of_tokens(usage_acc.get("total_tokens"),
                           getattr(a, "points_per_ktok", None))
    if pts is not None:
        if pts > a.budget:
            raise BudgetError(
                "%s 已超预算：约 %.2f 点 > --budget %.2f（按 --points-per-ktok %.4f "
                "折算，%d 次调用后**就地中止**）"
                % (label, pts, a.budget, a.points_per_ktok,
                   usage_acc["calls"]))
    elif usage_acc["calls"] > a.budget:
        raise BudgetError(
            "%s 已超预算：已调用 %d 次 > --budget %s（未给 --points-per-ktok，"
            "无法把 token 折成点数，因此 `--budget` 被当作**调用次数上限**；"
            "要按点数守就同时给 --points-per-ktok）——**就地中止**"
            % (label, usage_acc["calls"], a.budget))


def _confirm_spend(a, quote, what):
    """没报价就开跑 = 拒绝执行（exit=2）。"""
    if getattr(a, "yes", False) or getattr(a, "budget", None) is not None:
        return
    raise UsageError(
        "拒绝执行：%s 会真的调模型花钱，必须先确认。\n"
        "  预计调用：%d 次（每轮 5 次 × %d 轮）\n"
        "  两种确认方式任选：`--yes` 明确同意，或 `--budget <点数>` 封顶。\n"
        "  想先看看不花钱：加 `--dry-run`（只打印将发送的提示词与输入摘要）。\n"
        "  文本网关不公布单价，本包只报**调用次数与 token**，不报金额。"
        % (what, quote["calls_est"], quote["max_rounds"]))


# ---------------------------------------------------------------------------
# JSON 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#   · **stdout 只有一个 JSON 文档**（这条是靠"暂存 + 最后 flush 一次"保证的，
#     见 _stage_json 的说明；早期版本会把 5 个子步骤的 JSON 连着吐出来，
#     `json.loads` 直接报 `Extra data`）
#   · 人读文案走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#   · `--json` 写在子命令**前后都认**（见 _add_json）
# ---------------------------------------------------------------------------

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None,
         "pending": None}

_KIND_BY_EXIT = {1: "internal", 2: "usage", 3: "gate", 4: "call", 5: "budget",
                 6: "unresolved", 130: "interrupt"}


def _json_payload(obj, ok=True):
    if isinstance(obj, dict):
        out = {"ok": bool(ok)}
        out.update(obj)
        return out
    return {"ok": bool(ok), "data": obj}


def _json_text(obj, indent=1, ok=True):
    return json.dumps(_json_payload(obj, ok), ensure_ascii=False, indent=indent)


def _json_stdout():
    return _JSON["stdout"] or sys.stdout


def _json_write(text):
    """把 JSON 文本写到**真 stdout** 并记账。**只允许被调用一次。**"""
    _json_stdout().write(text + "\n")
    _JSON["emitted"] = True


def _json_want(a=None):
    if a is not None:
        return bool(getattr(a, "json", False))
    return bool(_JSON["want"])


def _stage_json(obj, out=None, indent=1, ok=True):
    """**暂存**一份要写的 JSON，不落盘、不写 stdout。

    为什么暂存：命令函数只能给出 `ok=not bad`，**还不知道最终退出码**
    （退出码是 `_main` 兜住异常之后才定下来的）。先写出去的话，
    `_main` 发现 rc != 0 再想补 `error` 字段就只能在同一个 stdout 上再写一份，
    立刻变成两个 JSON 文档。所以真正写出统一推迟到 `_flush_json()`。
    """
    _JSON["pending"] = {"obj": obj, "out": out, "indent": indent, "ok": bool(ok)}
    return True


def _flush_json(rc=0, kind=None, message=None, detail=None):
    """把暂存的 JSON 写到真 stdout（顺带落 `--out`）。**全程只写一次。**"""
    pending = _JSON["pending"]
    if not pending:
        return False
    obj, out = pending["obj"], pending["out"]
    indent = pending["indent"]
    if rc:
        k = kind or _KIND_BY_EXIT.get(rc, "gate")
        m = message or "命令以退出码 %s 结束（人读原因见 stderr）" % rc
        body = _result_with_error(obj, k, m, detail, indent, rc=rc)
    else:
        body = _json_text(obj, indent=indent, ok=pending["ok"])
    _JSON["pending"] = None
    if out:
        try:
            p = Path(out)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 %s\n" % out)
        except OSError as exc:
            sys.stderr.write("写 --out 失败：%s\n" % exc)
    _json_write(body)
    return True


def _json_out(obj, a=None, indent=1, ok=True):
    if not _json_want(a):
        return False
    if _JSON["pending"] is not None:
        sys.stderr.write("内部错误：一次运行里暂存了两份 JSON 结果（后一份覆盖前一份），"
                         "这是脚本 bug，请连同命令一起反馈。\n")
    return _stage_json(obj, getattr(a, "out", None) if a is not None else None,
                       indent=indent, ok=ok)


def _json_fail(rc, kind=None, message=None, detail=None, a=None):
    """失败出口：**只在本次没有任何结果要写时**才发独立信封。"""
    if _JSON["emitted"] or _JSON["pending"] is not None or not _json_want(a):
        return
    err = {"kind": kind or _KIND_BY_EXIT.get(rc, "call"),
           "message": message or "命令以退出码 %s 结束（人读原因见 stderr）" % rc}
    if detail is not None:
        err["detail"] = detail
    _json_write(json.dumps({"ok": False, "exit": rc, "error": err},
                           ensure_ascii=False, indent=1))


def _json_internal(exc):
    """未预料异常的兜底信封 —— **报 bug，不藏 bug**。

    只写 stdout（真 stdout）；完整 traceback 由 main() 的兜底层原样打到 stderr。
    """
    if _JSON["emitted"]:
        return
    _JSON["pending"] = None          # 未预料异常：丢掉半成品结果，只发兜底信封
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
    if _JSON["reason"] is None:
        _JSON["reason"] = {"kind": kind, "message": message, "detail": detail}
    return rc


def _emit(a, text, json_obj=None, ok=True):
    """统一出口：`--json` 且有 json_obj 时**暂存**（补 ok 后由 _main 落 stdout / --out）；
    否则原样输出人读文本。"""
    if json_obj is not None and getattr(a, "json", False):
        _json_out(json_obj, a, indent=2, ok=ok)
        return
    if getattr(a, "out", None):
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 %s\n" % a.out)
    print(text)


def _result_with_error(json_obj, kind, message, detail=None, indent=1, rc=None):
    """结果主体 + `error` / `exit` 信封字段，`ok` 如实为 false。

    为什么不是另发一个信封文档：stdout 只许有一个 JSON 文档，而结果主体
    （剧本、逐条闸门命中原因、打回记录）恰恰是失败时最需要机读的东西。
    补齐 `exit` 让两套消费姿势都能只靠 ok / exit / error 判失败。
    """
    obj = dict(json_obj) if isinstance(json_obj, dict) else {"data": json_obj}
    obj["error"] = {"kind": kind, "message": message}
    if detail is not None:
        obj["error"]["detail"] = detail
    if rc is not None:
        obj["exit"] = rc
    return json.dumps(_json_payload(obj, False), ensure_ascii=False, indent=indent)


# ---------------------------------------------------------------------------
# 全过程记录（`log`）
#
# 为什么单独落一份 Markdown：L3 的产出**不只是成品**，还包括"这个成品是怎么被审出来的"。
# 打回、否决、未决项都是可复核的证据——只留最终剧本，事后没人能证明发生过打回。
# 记录里**不写提示词全文**（太长），只写提示词指纹与输入摘要。
# ---------------------------------------------------------------------------

def log_append(outdir, text):
    p = Path(outdir) / LOG_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    with io.open(str(p), "a", encoding="utf-8") as fh:
        fh.write(text)
        if not text.endswith("\n"):
            fh.write("\n")


def log_round_header(outdir, rnd, topic, inputs):
    lines = ["", "---", "", "## 第 %s 轮" % rnd, "",
             "- 题材：%s" % topic, ""]
    lines.append("### 本轮各角色看到的信息（**信息不对称的证据**）")
    lines.append("")
    lines.append("| 角色 | 能看到 | 看不到 | 输入摘要 |")
    lines.append("|---|---|---|---|")
    for r in ROLE_ORDER:
        info = ROLES[r]
        lines.append("| %s | %s | %s | %s |" % (
            info["cn"], inputs[r].get("saw"), inputs[r].get("not_saw"),
            inputs[r].get("digest")))
    lines.append("")
    log_append(outdir, "\n".join(lines))


def log_verdict(outdir, rnd, role, verdict, extra=None):
    info = ROLES[role]
    lines = ["### %s 的裁决（第 %s 轮）：`%s`" % (info["cn"], rnd,
                                                 (verdict or {}).get("verdict") or "（缺）")]
    if verdict and verdict.get("reasons"):
        lines.append("")
        lines.append("**理由**：")
        for r in verdict["reasons"]:
            lines.append("- %s" % r)
    if verdict and verdict.get("unshootable"):
        lines.append("")
        lines.append("**写不了的场次**：")
        for r in verdict["unshootable"]:
            lines.append("- %s" % r)
    if verdict and verdict.get("scenes"):
        lines.append("")
        lines.append("**拍不出来的场次**：")
        for r in verdict["scenes"]:
            lines.append("- %s" % r)
    if verdict and verdict.get("auto"):
        lines.append("")
        lines.append("> 就地判定说明：%s" % verdict["auto"])
    if extra:
        lines.append("")
        lines.append(extra)
    lines.append("")
    log_append(outdir, "\n".join(lines))


def log_conflicts(outdir, rnd, cont):
    lines = ["### 场记的矛盾清单（第 %s 轮）：`%s`　共 %s 条"
             % (rnd, (cont.get("verdict") or {}).get("verdict"),
                (cont.get("stats") or {}).get("total"))]
    lines.append("")
    for c in cont.get("conflicts") or []:
        lines.append("- [%s · %s] %s　原文引证：「%s」　→ %s"
                     % (c.get("category"), c.get("severity"), c.get("where"),
                        (c.get("quote") or "")[:36], c.get("problem")))
    dropped = cont.get("dropped") or []
    if dropped:
        lines.append("")
        lines.append("**被剔出的编造引文 %d 条**：" % len(dropped))
        for c in dropped:
            lines.append("- 第 %s 条：%s" % (c.get("no"), c.get("dropped_why")))
    lines.append("")
    log_append(outdir, "\n".join(lines))


def log_decisions(outdir, rnd, decisions, note=None):
    lines = ["### 本轮结论"]
    lines.append("")
    lines.append("| 角色 | 裁决 | 摘要 |")
    lines.append("|---|---|---|")
    for d in decisions:
        lines.append("| %s | `%s` | %s |" % (d.get("role_cn"), d.get("verdict"),
                                             d.get("summary")))
    lines.append("")
    if decisions:
        verdicts = [d.get("verdict") for d in decisions]
        if any(v in ("reject", "not_producible", "blocking") for v in verdicts):
            bad = [d for d in decisions
                   if d.get("verdict") in ("reject", "not_producible", "blocking")]
            lines.append("**本轮被打回/否决**：%s —— 下一轮编剧必须正面处理。"
                         % "；".join("%s(%s)" % (d["role_cn"], d["verdict"]) for d in bad))
        else:
            lines.append("**四个角色本轮全部通过**，剧组收工。")
    if note:
        lines.append("")
        lines.append("> %s" % note)
    lines.append("")
    log_append(outdir, "\n".join(lines))


def log_init(outdir, topic, a):
    p = Path(outdir) / LOG_NAME
    header = ["# 短剧剧组 · 全过程记录", "",
              "- 题材：%s" % topic,
              "- 集数：%s" % a.episodes,
              "- 最大轮次：%s" % a.max_rounds,
              "- 模型：`%s`　温度：%s" % (a.model, a.temperature),
              "- 端点：`POST https://api.a7w.cn/api/v1/chat/completions`",
              "- 角色提示词版本：%s" % json.dumps(PROMPT_VERSION, ensure_ascii=False),
              "",
              "> 本文件记录**每一轮四个角色分别看到了什么、裁了什么、理由是什么**。",
              "> 「打回」与「否决」是 L3 的正常行为，不是错误。",
              ""]
    p.write_text("\n".join(header), encoding="utf-8")


# ---------------------------------------------------------------------------
# **信息不对称**（本包的机制核心，不是 bug）
#
# L3 与"调多次模型"的区别就在这里：四个角色的**立场差异来自输入差异**。
# 如果四个角色都拿到剧本全文 + 同一条"请严格评审"的指令，
# 出来的就是四段互不相干的话（假协作）。所以这里刻意让它们看到不同的东西：
#
#   编剧  ❌ 看不到导演的偏好、美术的产能约束、场记的历史台账
#   导演  ❌ 看不到题材的创意意图（只能基于**已写出的剧本**判断能不能拍）
#   美术  ❌ 看不到故事评价的邀请（只拿到场次与人物清单）
#   场记  ❌ 不参与改戏（只报矛盾）
#
# 打印这些摘要（`--show-inputs` 默认开）就是为了**证明不对称真实存在**，
# 而不是只在文档里声明。
# ---------------------------------------------------------------------------

def describe_inputs(rnd, topic, a, upstream_text, script_md, facts, board_md,
                    notes=None):
    notes_txt = ("；".join("[%s] %s" % (n.get("role"), n.get("why")[:40])
                           for n in (notes or []))) or "（无）"
    return {
        "writer": {
            "saw": "题材 / 集数 / 目标受众 / 额外要求%s"
                   % ("；上一轮被打回的意见" if notes else ""),
            "not_saw": "导演的镜头偏好；美术的产能约束；场记的历史台账",
            "digest": "题材=%s；集数=%s；上游文本 %d 字（sha %s）；意见=%s"
                      % (topic, a.episodes, len(upstream_text or ""),
                         text_hash(upstream_text)[:8], notes_txt),
        },
        "director": {
            "saw": "剧本全文（%d 字，sha %s）" % (len(script_md or ""),
                                                  text_hash(script_md)[:8]),
            "not_saw": "题材的创意意图与原始需求；美术的产能结论；场记的矛盾台账",
            "digest": "输入只有剧本本身，没有题材说明——"
                      "导演只能对着**已写出的字**判断能不能拍",
        },
        "art": {
            "saw": "场次清单 %d 场 + 出场人物 %d 人（**只有这些**）"
                   % (len(facts.get("scenes") or []), len(facts.get("characters") or [])),
            "not_saw": "剧本全文；台词；**故事评价的邀请**（提示词里明确禁止它评故事）",
            "digest": "输入是结构化场次/人物清单（sha %s），"
                      "不是剧本全文——它无从评价故事好不好看"
                      % text_hash(json.dumps(facts, ensure_ascii=False, sort_keys=True))[:8],
        },
        "scripty": {
            "saw": "剧本全文（sha %s）%s"
                   % (text_hash(script_md)[:8],
                      " + 分镜表（sha %s）" % text_hash(board_md)[:8] if board_md else ""),
            "not_saw": "创作过程与修改痕迹；改戏建议的授权（只报矛盾，不指出怎么改戏）",
            "digest": "逐场核对前后一致性；每条必须引用原文，引文本地逐字校验",
        },
    }


# ---------------------------------------------------------------------------
# 剧组主循环（`run`）
# ---------------------------------------------------------------------------

def _decision_of(role, verdict, extra=""):
    return {"role": role, "role_cn": ROLES[role]["cn"],
            "verdict": (verdict or {}).get("verdict") or "（缺）",
            "summary": extra or ("；".join((verdict or {}).get("reasons") or [])[:80]
                                 or ROLES[role]["power_cn"])}


def _notes_from(decisions, director, art, scripty):
    """把三个审阅角色的意见汇总成**编剧返修指令**。

    导演与美术的 reasons / unshootable / scenes 必须原样带过去——
    这是"打回"能落地的前提。场记的高中等级矛盾连着引文一起给。
    """
    notes = []
    for d in decisions:
        role = d["role"]
        v = d["verdict"]
        if role == "director" and v == "reject":
            for r in (director.get("reasons") or []):
                notes.append({"role": "导演", "role_cn": "导演", "kind": "reject", "why": r})
            for r in (director.get("unshootable") or []):
                notes.append({"role": "导演", "role_cn": "导演", "kind": "reject",
                              "why": "写不了的场次：%s" % r})
        if role == "art" and v == "not_producible":
            for r in (art.get("reasons") or []):
                notes.append({"role": "美术", "role_cn": "美术",
                              "kind": "not_producible", "why": r})
            for r in (art.get("scenes") or []):
                notes.append({"role": "美术", "role_cn": "美术",
                              "kind": "not_producible", "why": "拍不出来：%s" % r})
        if role == "scripty" and v == "blocking":
            for c in (scripty.get("conflicts") or [])[:6]:
                if (c.get("severity") or "") in ("高", "中"):
                    notes.append({"role": "场记", "role_cn": "场记", "kind": "blocking",
                                  "why": "[%s] %s　原文引证「%s」→ %s"
                                         % (c.get("category"), c.get("where"),
                                            (c.get("quote") or "")[:30],
                                            c.get("problem"))})
    return notes


def gate_feedback(artifact, problems, detail=None):
    """把闸门命中翻译成**下一轮的返修指令**（按角色路由）。

    为什么必须回流：闸门只在最后拦一下、却不让角色看到命中点，就会出现
    "跑满轮次、每轮都命中同一处、报告里一路红"——那不是协作，是空转。
    所以这里把命中分成三类，各自派给能修它的那个角色：
      · 合规 / 占位符（产出文本级）  → **编剧**（台词是编剧写的）
      · 分镜结构 / 分镜里的合规      → **导演**（分镜是导演写的）
      · 设定卡的角色一致性 / 合规    → **美术**（设定卡是美术写的）
      · 矛盾清单的引文锚点           → **场记**（引文是场记引的）
    同名问题每轮只派一次（去重），不会重复堆叠。
    """
    detail = detail or {}
    out = {"writer": [], "director": [], "art": [], "scripty": []}

    def add(role, kind, why):
        out[role].append({"role": ROLES[role]["cn"], "role_cn": ROLES[role]["cn"],
                          "kind": kind, "why": why})

    for p in problems or []:
        txt = str(p)
        if artifact in ("outline", "script"):
            if txt.startswith("合规命中") or txt.startswith("占位符残留") \
                    or txt.startswith("照抄提示词示例"):
                add("writer", "gate", "%s：%s" % (artifact, txt))
            elif txt.startswith("角色"):
                add("writer", "gate", txt)
        elif artifact == "board":
            # 分镜表的**结构缺项**归导演（镜头是他拆的）；而分镜里出现的
            # 合规/占位符问题**同时**要编剧知道——那通常是剧本台词被原样搬进了分镜。
            if txt.startswith(("合规命中", "占位符残留", "照抄提示词示例")):
                add("director", "gate", "分镜表：%s" % txt)
                add("writer", "gate", "分镜表里带出的问题（源头在剧本台词）：%s" % txt)
            else:
                add("director", "gate", "分镜表：%s" % txt)
        elif artifact == "art":
            # 缺卡、性别/年龄冲突都是**美术能自己修的**，原样派回去；
            # 再加上一条"必须出全"的硬指令，避免下一轮又漏。
            if txt.startswith("设定卡缺卡"):
                add("art", "gate", "%s　**必须为剧本里每个有名字的角色都出一张卡**"
                                   "（含只出场一次的角色），否则后续出图没有凭据" % txt)
            elif txt.startswith("角色"):
                add("art", "gate", "设定卡：%s" % txt)
            elif txt.startswith(("合规命中", "占位符残留", "照抄提示词示例")):
                add("art", "gate", "设定卡：%s" % txt)
        elif artifact == "continuity":
            add("scripty", "gate", "矛盾清单：%s" % txt)
    for r in out:
        seen, uniq = set(), []
        for n in out[r]:
            if n["why"] in seen:
                continue
            seen.add(n["why"])
            uniq.append(n)
        out[r] = uniq[:8]
    return out


def _merge_notes(by_role, flat, gate_fb):
    """把三类意见合成 (flat 全部, by_role 分角色)。by_role 是**调用时实际给谁的**。"""
    merged = {r: list((by_role or {}).get(r) or []) for r in ROLE_ORDER}
    for r in ROLE_ORDER:
        for n in (gate_fb or {}).get(r) or []:
            if n["why"] not in {x.get("why") for x in merged[r]}:
                merged[r].append(n)
    allf = list(flat or [])
    seen = {x.get("why") for x in allf}
    for r in ROLE_ORDER:
        for n in merged[r]:
            if n["why"] not in seen:
                seen.add(n["why"])
                allf.append(n)
    return allf, merged


def _run_crew(a, outdir, usage_acc, state):
    """剧场主循环。返回 (report, rc)。"""
    topic = a.topic
    quote = quote_run(a.episodes, a.max_rounds, a.points_per_ktok)
    _confirm_spend(a, quote, "剧组协作 run")
    log_init(outdir, topic, a)

    outline_md = ""
    prior_script_md = None
    notes = list(a.note or []) if getattr(a, "note", None) else []
    if notes:
        notes = [{"role": "人工", "role_cn": "人工", "kind": "note", "why": n}
                 for n in notes]
    notes_by_role = {r: list(notes) for r in ROLE_ORDER}   # 人工意见先给所有角色
    history = []
    final = {}
    rounds_used = 0
    prev_script_sha = None
    deadlock = None
    all_problems = []
    show_inputs = not getattr(a, "no_show_inputs", False)

    for rnd in range(1, int(a.max_rounds) + 1):
        rounds_used = rnd
        sys.stderr.write("\n=== 第 %s 轮 ===\n" % rnd)

        # ---- 编剧：大纲（第一轮）→ 剧本 ----
        gate_fb = {}
        out_res, o_usage, o_el, o_prompt, o_key, o_dims, o_cached = produce_outline(
            a, state, usage_acc, topic, rnd,
            notes=notes_by_role["writer"] if notes_by_role["writer"] else None)
        if out_res is None:
            raise CrewError("编剧没有产出大纲（--dry-run 下不产出）")
        outline_md = out_res["md"]
        o_problems, o_detail = text_gates(outline_md, "大纲")
        if o_problems:
            all_problems.append({"artifact": "outline", "round": rnd,
                                 "problems": o_problems, "detail": o_detail})
        # 大纲的命中**派给编剧**（大纲是编剧写的），这一轮就能修
        notes_by_role["writer"] = notes_by_role["writer"] + \
            gate_feedback("outline", o_problems, o_detail)["writer"]

        sc_res, s_usage, s_el, s_prompt, s_key, s_dims, s_cached = produce_script(
            a, state, usage_acc, outline_md, rnd,
            notes=notes_by_role["writer"] or None,
            prior_md=prior_script_md)
        if sc_res is None:
            raise CrewError("编剧没有产出剧本（--dry-run 下不产出）")
        script_md = sc_res["md"]
        script_obj = sc_res["obj"]
        script_sha = text_hash(script_md)
        s_problems, s_detail = text_gates(script_md, "剧本")
        if s_problems:
            all_problems.append({"artifact": "script", "round": rnd,
                                 "problems": s_problems, "detail": s_detail})

        # 注意：这里**还不能**打印输入摘要——美术的输入（场次/人物清单）要靠
        # `_script_facts(script_obj)` 算出来，放这里打印会显示"0 场 0 人"，
        # 而那是**错的数字**（实测踩到）。真正的打印挪到四个角色都跑完之后。
        inputs_now = describe_inputs(rnd, topic, a, outline_md, script_md, {}, None, notes)

        # ---- 导演：分镜表 + 可打回 ----
        bd_res, b_usage, b_el, b_prompt, b_key, b_dims, b_cached = produce_board(
            a, state, usage_acc, script_md, rnd,
            rounds_notes=[n.get("why") for n in notes_by_role["director"]][:6] or None)
        if bd_res is None:
            raise CrewError("导演没有产出分镜表（--dry-run 下不产出）")
        board_md, board_obj = bd_res["md"], bd_res["obj"]
        dir_verdict = board_obj.get("verdict") or {}
        v_problems = verdict_gate(dir_verdict, "director") + \
            critique_gate(dir_verdict, "director")
        st_problems, board_stats = board_gate(board_obj, script=script_obj)
        b_problems, b_detail = text_gates(board_md, "分镜表")
        if v_problems or st_problems or b_problems:
            all_problems.append({"artifact": "board", "round": rnd,
                                 "problems": v_problems + st_problems + b_problems,
                                 "detail": b_detail})
        # 分镜表的命中**派给导演**（分镜是导演写的）
        board_fb = gate_feedback("board",
                                 st_problems + [p for p in b_problems],
                                 b_detail)["director"]
        notes_by_role["director"] = notes_by_role["director"] + board_fb
        log_verdict(outdir, rnd, "director", dir_verdict,
                    extra="分镜统计：%s" % json.dumps(board_stats, ensure_ascii=False))

        # 导演的输入（**注意：只有剧本，没有题材说明**）
        inputs_now["director"]["digest"] = (
            "输入=剧本全文 %d 字（sha %s）+ 自己上一轮的打回记录 %d 条；"
            "**没有题材说明**"
            % (len(script_md), script_sha[:8],
               len([n for n in notes if n.get("role") == "导演"])))
        inputs_now["director"]["saw"] = "剧本全文（%d 字，sha %s）" % (len(script_md),
                                                                     script_sha[:8])

        # ---- 美术：设定卡 + 可否决 ----
        facts = _script_facts(script_obj)
        ar_res, a_usage, a_el, a_prompt, a_key, a_dims, a_cached = produce_art(
            a, state, usage_acc, facts, rnd,
            rounds_notes=[n.get("why") for n in notes_by_role["art"]][:6] or None)
        if ar_res is None:
            raise CrewError("美术没有产出设定卡（--dry-run 下不产出）")
        art_md, art_obj = ar_res["md"], ar_res["obj"]
        art_verdict = art_obj.get("verdict") or {}
        av_problems = verdict_gate(art_verdict, "art") + critique_gate(art_verdict, "art")
        rc_problems = role_consistency(script_obj, art_obj)
        ar_problems, ar_detail = text_gates(art_md, "设定卡")
        if av_problems or rc_problems or ar_problems:
            all_problems.append({"artifact": "art", "round": rnd,
                                 "problems": av_problems + rc_problems + ar_problems,
                                 "detail": ar_detail})
        # 设定卡的命中**派给美术**；角色卡缺口必须补齐，否则出图没有凭据
        art_fb = gate_feedback("art", rc_problems + ar_problems, ar_detail)["art"]
        for x in rc_problems:
            if str(x).startswith("角色") and "设定卡里没有" in str(x):
                art_fb.append({"role": "美术", "role_cn": "美术", "kind": "gate",
                               "why": "设定卡缺卡：%s　**必须为剧本里每个有名字的"
                                      "角色都出一张卡**（含只出场一次的角色），"
                                      "否则后续出图没有凭据" % str(x)})
        notes_by_role["art"] = notes_by_role["art"] + art_fb
        log_verdict(outdir, rnd, "art", art_verdict)

        # ---- 场记：矛盾清单 ----
        co_res, c_usage, c_el, c_prompt, c_key, c_dims, c_cached = produce_continuity(
            a, state, usage_acc, script_md, board_md, rnd,
            prior=[n for n in notes_by_role["scripty"]][:6] or None)
        if co_res is None:
            raise CrewError("场记没有产出矛盾清单（--dry-run 下不产出）")
        cont_md, cont_obj = co_res["md"], co_res["obj"]
        scripty_verdict = cont_obj.get("verdict") or {}
        cv_problems = verdict_gate(cont_obj, "scripty")
        if cont_obj.get("gate_problems"):
            cv_problems = cv_problems + cont_obj["gate_problems"]
        c_problems, c_detail = text_gates(cont_md, "矛盾清单")
        if cv_problems or c_problems:
            all_problems.append({"artifact": "continuity", "round": rnd,
                                 "problems": cv_problems + c_problems,
                                 "detail": c_detail})
        c_fb = gate_feedback("continuity", cv_problems + c_problems, c_detail)
        notes_by_role["scripty"] = notes_by_role["scripty"] + c_fb["scripty"]
        # 引文造假/锚点失败**同时派给编剧**：它要给出可被逐字引用的台词
        notes_by_role["writer"] = notes_by_role["writer"] + c_fb["scripty"][:2]
        log_conflicts(outdir, rnd, cont_obj)

        # 输入摘要（此时 facts 已经算出来了，数字才是真的）
        inputs_now = describe_inputs(rnd, topic, a, outline_md, script_md, facts,
                                     board_md, notes)
        log_round_header(outdir, rnd, topic, inputs_now)

        # ---- 本轮结论 ----
        decisions = [
            _decision_of("writer", {"verdict": "revised" if rnd > 1 else "draft"},
                         "剧本 %d 字 / %d 集 / %d 场"
                         % (count_chars(script_md), len(script_obj.get("episodes") or []),
                            sum(len(e.get("scenes") or [])
                                for e in script_obj.get("episodes") or []))),
            _decision_of("director", dir_verdict,
                         "分镜 %d 镜 / 合计 %.1f 秒"
                         % (board_stats["shots"], board_stats["total_seconds"])),
            _decision_of("art", art_verdict,
                         "角色卡 %d / 场景卡 %d"
                         % (len(art_obj.get("characters") or []),
                            len(art_obj.get("scenes") or []))),
            _decision_of("scripty", scripty_verdict,
                         "矛盾 %d 条（否决 %d）"
                         % (cont_obj["stats"]["total"], cont_obj["stats"]["blocking"])),
        ]
        # 死循环检测：编剧返修后**正文一字未变**时，这一轮没有真的改
        if rnd > 1 and prev_script_sha == script_sha:
            deadlock = ("第 %s 轮编剧返修后剧本正文与第 %s 轮**一字未变**"
                        "（内容指纹 %s）—— 这不是重写，是空转"
                        % (rnd, rnd - 1, script_sha))
            sys.stderr.write(_red("警告：%s\n" % deadlock))
        prev_script_sha = script_sha

        agreed, items, dnotes = decision_closure(dir_verdict, art_verdict,
                                                 scripty_verdict, None)
        # 【闭环】"四个角色都点头"还不算收工：**闸门命中同样是未决项**。
        # 少了这一步就会出现"角色全过、报告一路红、exit=3"这种半成品状态——
        # 既然命中已经被派回各角色了（gate_feedback），就该让它真的再修一轮。
        round_hits = [h for h in all_problems if h["round"] == rnd]
        round_problem_count = sum(len(h["problems"]) for h in round_hits)
        settled = agreed and not round_problem_count
        if not agreed:
            note = deadlock if deadlock else "未达成一致：%d 项未决" % len(items)
        elif round_problem_count:
            note = ("四个角色都点了头，但**闸门仍有 %d 处命中**"
                    "（已按角色派回返修方向，不算收工）" % round_problem_count)
        else:
            note = deadlock
        log_decisions(outdir, rnd, decisions, note=note)

        history.append({
            "round": rnd,
            "script_sha": script_sha,
            "script_chars": count_chars(script_md),
            "scenes": sum(len(e.get("scenes") or [])
                          for e in script_obj.get("episodes") or []),
            "board_stats": board_stats,
            "conflicts": cont_obj["stats"],
            "dropped_quotes": len(cont_obj.get("dropped") or []),
            "decisions": decisions,
            "agreed": agreed,
            "settled": settled,
            "gate_hits": round_problem_count,
            "unresolved": items,
            "tokens": {"outline": usage_of(o_usage), "script": usage_of(s_usage),
                       "board": usage_of(b_usage), "art": usage_of(a_usage),
                       "continuity": usage_of(c_usage)},
            "cached": {"outline": o_cached, "script": s_cached, "board": b_cached,
                       "art": a_cached, "continuity": c_cached},
            "note": note,
        })
        final = {"outline_md": outline_md, "script_md": script_md,
                 "script_obj": script_obj, "board_md": board_md,
                 "board_obj": board_obj, "art_md": art_md, "art_obj": art_obj,
                 "cont_md": cont_md, "cont_obj": cont_obj,
                 "decisions": decisions}
        if show_inputs:
            _print_inputs(rnd, inputs_now)
        save_state(outdir, state)
        # 预算已由 _budget_guard 在**每次调用后**即时把关（见那里的说明）。
        if settled:
            sys.stderr.write("\n第 %s 轮：四个角色全部通过，且闸门在这轮无命中——收工。\n"
                             % rnd)
            break
        if agreed:
            sys.stderr.write("\n第 %s 轮四个角色点头，但闸门仍有 %d 处命中，继续返修。\n"
                             % (rnd, round_problem_count))

        # 未达成一致：把「审阅意见 + 闸门命中」合成下一轮的返修指令（按角色分桶）
        notes = _notes_from(decisions, dir_verdict, art_verdict, scripty_verdict)
        notes, notes_by_role = _merge_notes(notes_by_role, notes, gate_fb)
        prior_script_md = script_md
        if rnd == int(a.max_rounds):
            sys.stderr.write("\n轮次用完，仍有 %d 项未决（%d 项裁决未决 + %d 处闸门命中）"
                             "——**如实报出，不假装谈拢**。\n"
                             % (len(items) + round_problem_count, len(items),
                                round_problem_count))

    # ---- 收尾：重新用最终产物算一次收敛状态 ----
    agreed, items, dnotes = decision_closure(
        final["board_obj"].get("verdict"), final["art_obj"].get("verdict"),
        final["cont_obj"],
        ([{"role": "writer", "role_cn": "编剧", "kind": "deadlock", "why": deadlock}]
         if deadlock else None))
    # 最后一轮仍有闸门命中 → 也是未决项（**不写成"已通过"**）。
    last_hits = [h for h in all_problems if h["round"] == rounds_used]
    last_count = sum(len(h["problems"]) for h in last_hits)
    unresolved = [] if (agreed and not last_count) else list(items)
    if last_count and agreed:
        unresolved.append({"role": "gate", "role_cn": "闸门",
                           "kind": "gate",
                           "why": "轮次用完，最后一轮仍被本地闸门拦下 %d 处"
                                  "（合规/占位符/照抄示例/分镜结构/角色一致性/裁决完整性）"
                                  % last_count})
    settled = bool(agreed and not last_count and not deadlock)

    # ---- 落盘所有产出 ----
    _write_artifacts(outdir, a, final, history, unresolved, deadlock,
                     all_problems, usage_acc, quote, settled, agreed)

    report = {
        "topic": topic, "episodes": a.episodes, "max_rounds": a.max_rounds,
        "rounds_used": rounds_used, "model": a.model, "temperature": a.temperature,
        "prompt_version": PROMPT_VERSION,
        "crew": {r: {"cn": ROLES[r]["cn"], "goal": ROLES[r]["goal"],
                     "artifact": ROLES[r]["artifact"], "power": ROLES[r]["power_cn"]}
                 for r in ROLE_ORDER},
        "history": history,
        "agreed": agreed, "settled": settled, "unresolved": unresolved,
        "deadlock": deadlock,
        "gate_hits_last_round": last_count,
        "outdir": str(outdir),
        "artifacts": {"outline": OUTLINE_MD, "script": SCRIPT_MD, "board": BOARD_MD,
                      "art": ART_MD, "continuity": CONTINUITY_MD, "log": LOG_NAME,
                      "report": REPORT_MD},
        "usage": {k: v for k, v in usage_acc.items() if k != "raw"},
        "usage_raw": usage_acc.get("raw") or [],
        "gates": {"problems": all_problems,
                  "text_gate_hits": sum(len(p["problems"]) for p in all_problems)},
        "cost": {"calls_est": quote["calls_est"], "calls_actual": usage_acc["calls"],
                 "points": points_of_tokens(usage_acc.get("total_tokens"),
                                            getattr(a, "points_per_ktok", None)),
                 "pricing_note": quote["pricing_note"]},
    }
    # 退出码语义（**不许假装谈拢**，也不许把红报告写成绿报告）：
    #   0  四个角色全部通过 + 最后一轮闸门无命中
    #   6  轮次用完仍有未决项（含"最后一轮仍被闸门拦下"这一种）
    #   3  未到轮次上限就因别的原因停下（正常流程里不会出现，兜底用）
    if settled:
        rc = EXIT_OK
    elif not agreed or last_count:
        rc = EXIT_UNRESOLVED
    else:
        rc = EXIT_GATE
    return report, rc


def _print_inputs(rnd, inputs):
    """打印四个角色**分别看到了什么**——信息不对称的现场证据。"""
    sys.stderr.write("\n---- 第 %s 轮：各角色看到的信息 ----\n" % rnd)
    for r in ROLE_ORDER:
        i = inputs[r]
        sys.stderr.write("  [%s] 看到：%s\n" % (ROLES[r]["cn"], i.get("saw")))
        sys.stderr.write("  %s看不到：%s\n" % (" " * (len(ROLES[r]["cn"]) + 2),
                                             i.get("not_saw")))
        sys.stderr.write("  %s输入摘要：%s\n" % (" " * (len(ROLES[r]["cn"]) + 2),
                                               i.get("digest")))
    sys.stderr.write("\n")


def _write_artifacts(outdir, a, final, history, unresolved, deadlock,
                     all_problems, usage_acc, quote, settled=False, agreed=False):
    p = Path(outdir)
    p.mkdir(parents=True, exist_ok=True)
    (p / OUTLINE_MD).write_text(final["outline_md"] + "\n", encoding="utf-8")
    (p / SCRIPT_MD).write_text(final["script_md"] + "\n", encoding="utf-8")
    (p / BOARD_MD).write_text(final["board_md"] + "\n", encoding="utf-8")
    (p / ART_MD).write_text(final["art_md"] + "\n", encoding="utf-8")
    (p / CONTINUITY_MD).write_text(final["cont_md"] + "\n", encoding="utf-8")
    (p / SCRIPT_JSON).write_text(json.dumps(
        {"ok": True, "data": final["script_obj"]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (p / BOARD_JSON).write_text(json.dumps(
        {"ok": True, "data": final["board_obj"]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (p / ART_JSON).write_text(json.dumps(
        {"ok": True, "data": final["art_obj"]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (p / CONTINUITY_JSON).write_text(json.dumps(
        {"ok": True, "data": final["cont_obj"]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    lines = ["# 剧组报告 · %s" % a.topic, "",
             "- 集数：%s　最大轮次：%s　实际用轮：%s" % (a.episodes, a.max_rounds,
                                                       len(history)),
             "- 模型：`%s`　端点：`POST /api/v1/chat/completions`" % a.model,
             "- token 总计：%s（%s 次调用）" % (usage_acc.get("total_tokens"),
                                               usage_acc.get("calls")),
             "- 结算口径：**只出 token，不编价**（文本网关不公布单价）",
             ""]
    if deadlock:
        lines.append("> ⚠️ **空转警告**：%s" % deadlock)
        lines.append("")
    lines.append("## 是不是真的在互相否")
    lines.append("")
    reject_rounds = [h for h in history
                     if any(d["verdict"] in ("reject", "not_producible", "blocking")
                            for d in h["decisions"])]
    if reject_rounds:
        lines.append("**是。**下面这些轮次里出现了真实的打回 / 否决：")
        lines.append("")
        lines.append("| 轮 | 谁否了谁 | 裁决 | 理由/引证 |")
        lines.append("|---|---|---|---|")
        for h in reject_rounds:
            for d in h["decisions"]:
                if d["verdict"] in ("reject", "not_producible", "blocking"):
                    lines.append("| %s | %s | `%s` | %s |" % (
                        h["round"], d["role_cn"], d["verdict"], d["summary"]))
        lines.append("")
    else:
        lines.append("**没有。**本次运行里没有任何一处打回或否决——"
                     "如果没有出现真实的互否，那就是**假协作**，本包不把它算成 L3 成功。"
                     "（注意：这只说明最后一轮没人否；要判断是否真的互否，"
                     "看上面的裁决表与 `crew-log.md`。）")
        lines.append("")
    lines.append("## 逐轮记录")
    lines.append("")
    lines.append("| 轮 | 剧本字数 | 场数 | 镜数 | 镜总时长(s) | 矛盾(否决) | 编造引文 | "
                 "角色全过 | 闸门命中 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for h in history:
        lines.append("| %s | %s | %s | %s | %s | %s(%s) | %s | %s | %s |" % (
            h["round"], h["script_chars"], h["scenes"], h["board_stats"]["shots"],
            h["board_stats"]["total_seconds"],
            h["conflicts"]["total"], h["conflicts"]["blocking"],
            h["dropped_quotes"], "✅" if h["agreed"] else "❌",
            h.get("gate_hits", 0)))
    lines.append("")
    lines.append("## 未决项（轮次用完仍未收敛）")
    lines.append("")
    if unresolved:
        for u in unresolved:
            lines.append("- **[%s]** %s" % (u.get("role_cn") or u.get("role"),
                                            u.get("why")))
        lines.append("")
        lines.append("> 这些项**没有谈拢**。本包不把它们写成「已通过」——"
                     "要收敛就加轮次（`--max-rounds`）或按上面的理由改题材/口径。")
    else:
        lines.append("无。四个角色在最后一轮全部通过，且该轮闸门无命中。")
    lines.append("")
    lines.append("## 闸门命中")
    lines.append("")
    if all_problems:
        for pr in all_problems:
            lines.append("- **%s（第 %s 轮）**" % (pr["artifact"], pr["round"]))
            for x in pr["problems"]:
                lines.append("  - %s" % x)
    else:
        lines.append("无命中。")
    lines.append("")
    lines.append("## token 台账")
    lines.append("")
    lines.append("| 轮 | 大纲 | 剧本 | 分镜 | 设定卡 | 矛盾清单 |")
    lines.append("|---|---|---|---|---|---|")
    for h in history:
        row = []
        for k in ("outline", "script", "board", "art", "continuity"):
            u = h["tokens"][k]
            row.append("%s%s" % (u.get("total_tokens") or "-",
                                 "（缓存）" if h["cached"].get(k) else ""))
        lines.append("| %s | %s |" % (h["round"], " | ".join(row)))
    lines.append("")
    lines.append("> 结算只认 `usage.total_tokens`。**文本网关不公布单价 → 本包不报金额、不编价。**")
    lines.append("")
    (p / REPORT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (p / REPORT_JSON).write_text(json.dumps(
        {"ok": bool(settled and not unresolved), "agreed": agreed,
         "settled": bool(settled and not unresolved),
         "rounds": len(history), "history": history, "unresolved": unresolved,
         "deadlock": deadlock, "gates": all_problems,
         "usage": {k: v for k, v in usage_acc.items() if k != "raw"},
         "usage_raw": usage_acc.get("raw") or [],
         "cost": {"calls_est": quote["calls_est"],
                  "calls_actual": usage_acc["calls"],
                  "points": points_of_tokens(usage_acc.get("total_tokens"),
                                             getattr(a, "points_per_ktok", None))}},
        ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# 产出文件读写（子命令之间靠这些 JSON 串起来）
# ---------------------------------------------------------------------------

def ensure_outdir(outdir):
    p = check_outdir(outdir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json_artifact(outdir, name, what):
    p = Path(outdir) / name
    if not p.is_file():
        raise UsageError("找不到 %s：%s（先跑出它的那条命令）" % (what, p))
    try:
        obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise UsageError("%s 不是合法 JSON：%s（%s）" % (what, p, exc))
    if isinstance(obj, dict) and "data" in obj:
        return obj["data"]
    return obj


def _read_md_artifact(outdir, name, what):
    p = Path(outdir) / name
    if not p.is_file():
        raise UsageError("找不到 %s：%s（先跑出它的那条命令）" % (what, p))
    return p.read_text(encoding="utf-8", errors="replace")


def _load_from_file(path, what):
    p = Path(path)
    if not p.is_file():
        raise UsageError("%s 文件不存在：%s" % (what, p))
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise UsageError("%s 不是合法 JSON：%s（%s）" % (what, p, exc))


def _write_artifact(outdir, name, obj, md_name=None, md=None):
    p = Path(outdir) / name
    p.write_text(json.dumps({"ok": True, "data": obj}, ensure_ascii=False, indent=1),
                 encoding="utf-8")
    if md_name and md is not None:
        (Path(outdir) / md_name).write_text(md + "\n", encoding="utf-8")
    return p


def _gate_exit(problems, detail, where, a, payload=None):
    """闸门命中的统一出口：标红 + stderr 汇总 + 非 0 退出码。"""
    if not problems:
        return EXIT_OK
    sys.stderr.write("\n" + _red("闸门命中（%s）：" % where) + "\n")
    for x in problems:
        sys.stderr.write("   " + _red(str(x)) + "\n")
    if detail.get("compliance_exempted"):
        sys.stderr.write("   本地放过了 %d 处疑似绝对化用语（计量名词 + 「的/之」语境，"
                         "已登记在 --json 的 gates.compliance_exempted）\n"
                         % len(detail["compliance_exempted"]))
    sys.stderr.write("\n   人读结果见标准输出；机器读用 --json。\n")
    _fail(EXIT_GATE, "gate", "；".join(str(p) for p in problems[:3]),
          {"where": where, "problems": problems, "hits": detail})
    return EXIT_GATE


def _print_prompt_preview(prompt, system, title):
    print("# %s" % title)
    print("")
    print("> **dry-run：只打印将发送的提示词，不调模型、不花钱。**")
    print("")
    hy = prompt_hygiene(prompt)
    print("- 提示词卫生自检：%s" % ("✅ 通过（没有混进登记过的示例）" if not hy
                                   else "❌ 命中 %s" % json.dumps(hy, ensure_ascii=False)))
    print("- 提示词长度：%d 字　system：%d 字" % (len(prompt), len(system or "")))
    print("")
    print("## system")
    print("")
    print("```")
    print(system or "")
    print("```")
    print("")
    print("## user")
    print("")
    print("```")
    print(prompt)
    print("```")


# ---------------------------------------------------------------------------
# 子命令：crew / outline
# ---------------------------------------------------------------------------

def cmd_crew(a):
    """列出四个角色与职权（**零成本**，一次调用都不发）。"""
    lines = ["# 短剧剧组 · 四个角色与职权", "",
             "> 本包是 **L3 多智能体协作型**：多角色分工互审，一条命令出成品。",
             "> L1 = 一个输入一个产出；L2 = 一个声音自己迭代；"
             "L3 = **每个角色有自己的目标与立场，且会互相否掉对方**。",
             "> 本包**不出片、不出图**——产出是**剧本 + 分镜包**。",
             "",
             "## 角色表", "",
             "| 角色 | 代号 | 目标 | 产出物 | 否决权 |",
             "|---|---|---|---|---|"]
    for r in ROLE_ORDER:
        i = ROLES[r]
        lines.append("| **%s** | `%s` | %s | %s | %s |"
                     % (i["cn"], r, i["goal"], i["artifact"], i["power_cn"]))
    lines.append("")
    lines.append("## 各角色**不做**什么（立场边界）")
    lines.append("")
    for r in ROLE_ORDER:
        lines.append("### %s" % ROLES[r]["cn"])
        lines.append("")
        for m in ROLES[r]["must_not"]:
            lines.append("- %s" % m)
        lines.append("")
    lines.append("## 表决与终止")
    lines.append("")
    lines.append("| 规则 | 口径 |")
    lines.append("|---|---|")
    lines.append("| 打回 | 导演 `verdict=reject` 必须给出理由 + 写不了的场次 |")
    lines.append("| 否决 | 美术 `not_producible` 必须指出哪一场拍不出来 |")
    lines.append("| 否决 | 场记的中高等级矛盾 = 否决，必须修 |")
    lines.append("| 轮次 | 默认 %d 轮，上限 %d 轮（`--max-rounds`）"
                 % (CREW["max_rounds"], CREW["hard_max_rounds"]))
    lines.append("| 终止 | 四个角色同一轮全部通过 → 收工（exit=0） |")
    lines.append("| **不许假装谈拢** | 轮次用完仍有未决项 → 显式列未决项 + exit=%d"
                 % EXIT_UNRESOLVED)
    lines.append("| 空转检测 | 编剧返修后正文一字未变 → 报「空转」，不算收敛 |")
    lines.append("")
    lines.append("## 信息不对称（**机制核心**）")
    lines.append("")
    lines.append("| 角色 | 看得到 | **看不到** |")
    lines.append("|---|---|---|")
    lines.append("| 编剧 | 题材、集数、受众、额外要求、上一轮被打回的意见 "
                 "| 导演的镜头偏好；美术的产能约束；场记的历史台账 |")
    lines.append("| 导演 | 剧本全文 + 自己上一轮的打回记录 "
                 "| 题材的创意意图；美术的产能结论；场记的矛盾台账 |")
    lines.append("| 美术 | 场次清单 + 出场人物（**只有这些**） "
                 "| 剧本全文与台词；**故事评价的邀请** |")
    lines.append("| 场记 | 剧本全文 + 分镜表 | 创作过程与修改痕迹；改戏建议的授权 |")
    lines.append("")
    lines.append("`run` 会逐轮打印各角色的输入摘要（`--show-inputs`，默认开），"
                 "用来证明不对称真实存在。")
    lines.append("")
    lines.append("## 退出码")
    lines.append("")
    lines.append("| 码 | 含义 |")
    lines.append("|---|---|")
    lines.append("| 0 | 四个角色全部通过，闸门无命中 |")
    lines.append("| 1 | 未预料异常（`--json` 下给 `kind:\"internal\"` 信封 + stderr 完整 traceback） |")
    lines.append("| 2 | 参数/环境错误（`--outdir` 指到包内、没报价就开跑） |")
    lines.append("| 3 | 硬闸门命中（合规/占位符/照抄示例/分镜结构/一致性/裁决完整性） |")
    lines.append("| 4 | 调用失败（网络/鉴权/点数/模型名） |")
    lines.append("| 5 | 成本上限 |")
    lines.append("| 6 | **轮次用完仍有未决项**（分歧如实报出，不许假装谈拢） |")
    lines.append("| 130 | 用户中断 |")
    lines.append("")
    payload = {"ok": True,
               "roles": [{"code": r, "cn": ROLES[r]["cn"], "goal": ROLES[r]["goal"],
                          "artifact": ROLES[r]["artifact"],
                          "power": ROLES[r]["power"],
                          "power_cn": ROLES[r]["power_cn"],
                          "must_not": ROLES[r]["must_not"]} for r in ROLE_ORDER],
               "rules": {"max_rounds": CREW["max_rounds"],
                         "hard_max_rounds": CREW["hard_max_rounds"],
                         "unresolved_exit": EXIT_UNRESOLVED,
                         "deadlock_detection": True},
               "cost": {"calls": 0, "points": 0.0,
                        "note": "crew 是纯本地输出，零成本"}}
    _emit(a, "\n".join(lines), payload)
    return EXIT_OK


def cmd_outline(a):
    outdir = ensure_outdir(a.outdir)
    state = load_state(outdir)
    usage_acc = new_usage()
    if a.from_file:
        raw = _load_from_file(a.from_file, "大纲")
        obj = normalize_outline(raw.get("data") if isinstance(raw, dict)
                                and "data" in raw else raw, a.episodes)
        md = render_outline_md(obj, {"model": "(from-file，未调用模型)"})
        problems, detail = text_gates(md, "大纲")
        _emit(a, md, {"topic": a.topic, "episodes": a.episodes, "gates": detail,
                      "from_file": a.from_file, "usage": {"calls": 0}})
        return _gate_exit(problems, detail, "大纲", a)
    quote = quote_run(a.episodes, 1, a.points_per_ktok)
    _confirm_spend(a, quote, "编剧出大纲")
    res, usage, elapsed, prompt, key, dims, cached = produce_outline(
        a, state, usage_acc, a.topic, 1)
    if res is None:
        _print_prompt_preview(prompt, WRITER_SYSTEM, "编剧 · 分集大纲（dry-run）")
        _emit(a, "# dry-run\n\n（未调用模型，未产出大纲）",
              {"topic": a.topic, "dry_run": True, "prompt_sha": text_hash(prompt),
               "key": key, "key_dims": dims, "usage": {"calls": 0}})
        return EXIT_OK
    save_state(outdir, state)
    _write_artifact(outdir, OUTLINE_JSON, res["obj"], OUTLINE_MD, res["md"])
    problems, detail = text_gates(res["md"], "大纲")
    _emit(a, res["md"], {"topic": a.topic, "episodes": a.episodes,
                         "round": 1, "breakpoint_key": key, "key_dims": dims,
                         "cached": cached, "outdir": str(outdir),
                         "usage": usage_of(usage), "usage_raw": usage,
                         "gates": detail,
                         "saved": [OUTLINE_MD, OUTLINE_JSON]})
    if cached:
        sys.stderr.write("（断点命中，本次未花钱）\n")
    return _gate_exit(problems, detail, "大纲", a)


def cmd_script(a):
    outdir = ensure_outdir(a.outdir)
    state = load_state(outdir)
    usage_acc = new_usage()
    outline_md = _read_md_artifact(outdir, OUTLINE_MD, "大纲")
    if a.from_file:
        raw = _load_from_file(a.from_file, "剧本")
        obj = normalize_script(raw.get("data") if isinstance(raw, dict)
                               and "data" in raw else raw)
        md = render_script_md(obj, {"model": "(from-file，未调用模型)"})
        problems, detail = text_gates(md, "剧本")
        _emit(a, md, {"gates": detail, "from_file": a.from_file,
                      "usage": {"calls": 0}})
        return _gate_exit(problems, detail, "剧本", a)
    quote = quote_run(a.episodes, 1, a.points_per_ktok)
    _confirm_spend(a, quote, "编剧出剧本")
    obj = normalize_json_safe(outline_md)
    res, usage, elapsed, prompt, key, dims, cached = produce_script(
        a, state, usage_acc, outline_md, 1, notes=None, prior_md=None)
    if res is None:
        _print_prompt_preview(prompt, WRITER_SYSTEM, "编剧 · 剧本（dry-run）")
        _emit(a, "# dry-run\n\n（未调用模型，未产出剧本）",
              {"dry_run": True, "prompt_sha": text_hash(prompt), "key": key,
               "key_dims": dims, "usage": {"calls": 0}})
        return EXIT_OK
    save_state(outdir, state)
    _write_artifact(outdir, SCRIPT_JSON, res["obj"], SCRIPT_MD, res["md"])
    problems, detail = text_gates(res["md"], "剧本")
    _emit(a, res["md"], {"round": 1, "breakpoint_key": key, "key_dims": dims,
                         "cached": cached, "outdir": str(outdir),
                         "chars": count_chars(res["md"]), "obj_note": obj,
                         "usage": usage_of(usage), "usage_raw": usage,
                         "gates": detail, "saved": [SCRIPT_MD, SCRIPT_JSON]})
    if cached:
        sys.stderr.write("（断点命中，本次未花钱）\n")
    return _gate_exit(problems, detail, "剧本", a)


def normalize_json_safe(text):
    """给 `script` 用的小工具：把大纲 Markdown 的标题取出来做上报（不影响调用）。"""
    m = re.search(r"^#\s*分集大纲\s*·\s*(.+)$", text or "", re.M)
    return {"outline_title": (m.group(1).strip() if m else None)}


# ---------------------------------------------------------------------------
# 子命令：board / art / continuity
#
# 三条命令都支持 `--from-file`：**不调模型**，直接拿一份 JSON 过闸门。
# 这是为"闸门自检"设计的——闸门的行为必须能零成本复现，
# 否则没人有动力去测它（本库的口径：用例设计成不花钱）。
# ---------------------------------------------------------------------------

def cmd_board(a):
    outdir = ensure_outdir(a.outdir)
    state = load_state(outdir)
    usage_acc = new_usage()
    script_md = _read_md_artifact(outdir, SCRIPT_MD, "剧本")
    script_obj = _read_json_artifact(outdir, SCRIPT_JSON, "剧本 JSON")
    if a.from_file:
        raw = _load_from_file(a.from_file, "分镜表")
        obj = normalize_board(raw.get("data") if isinstance(raw, dict)
                              and "data" in raw else raw, script=script_obj)
        md = render_board_md(obj, {"model": "(from-file，未调用模型)"})
        v_problems = verdict_gate(obj["verdict"], "director") + \
            critique_gate(obj["verdict"], "director")
        st_problems, stats = board_gate(obj, script=script_obj)
        t_problems, detail = text_gates(md, "分镜表")
        problems = v_problems + st_problems + t_problems
        _emit(a, md, {"from_file": a.from_file, "verdict": obj["verdict"],
                      "board_stats": stats, "gates": detail, "usage": {"calls": 0}})
        return _gate_exit(problems, detail, "分镜表", a)
    quote = quote_run(a.episodes, 1, a.points_per_ktok)
    _confirm_spend(a, quote, "导演出分镜表")
    res, usage, elapsed, prompt, key, dims, cached = produce_board(
        a, state, usage_acc, script_md, 1)
    if res is None:
        _print_prompt_preview(prompt, DIRECTOR_SYSTEM, "导演 · 分镜表（dry-run）")
        _emit(a, "# dry-run\n\n（未调用模型，未产出分镜表）",
              {"dry_run": True, "prompt_sha": text_hash(prompt), "key": key,
               "key_dims": dims, "usage": {"calls": 0}})
        return EXIT_OK
    save_state(outdir, state)
    obj = res["obj"]
    _write_artifact(outdir, BOARD_JSON, obj, BOARD_MD, res["md"])
    v_problems = verdict_gate(obj["verdict"], "director") + \
        critique_gate(obj["verdict"], "director")
    st_problems, stats = board_gate(obj, script=script_obj)
    t_problems, detail = text_gates(res["md"], "分镜表")
    problems = v_problems + st_problems + t_problems
    _emit(a, res["md"], {"round": 1, "breakpoint_key": key, "key_dims": dims,
                         "cached": cached, "verdict": obj["verdict"],
                         "board_stats": stats, "outdir": str(outdir),
                         "usage": usage_of(usage), "usage_raw": usage,
                         "gates": detail, "saved": [BOARD_MD, BOARD_JSON]})
    if obj["verdict"].get("verdict") == "reject":
        sys.stderr.write("\n" + _red("导演打回了编剧") + "：%s\n"
                         % "；".join(obj["verdict"].get("reasons") or ["（未给理由）"]))
        sys.stderr.write("  写不了的场次：%s\n"
                         % "；".join(obj["verdict"].get("unshootable") or ["（未指出）"]))
        sys.stderr.write("  这是 L3 的正常行为——用 `run` 走完返修，"
                         "或用手上的剧本改完再重跑 `board`。\n")
    return _gate_exit(problems, detail, "分镜表", a)


def cmd_art(a):
    outdir = ensure_outdir(a.outdir)
    state = load_state(outdir)
    usage_acc = new_usage()
    script_obj = _read_json_artifact(outdir, SCRIPT_JSON, "剧本 JSON")
    facts = _script_facts(script_obj)
    if a.from_file:
        raw = _load_from_file(a.from_file, "美术设定卡")
        obj = normalize_art(raw.get("data") if isinstance(raw, dict)
                            and "data" in raw else raw)
        md = render_art_md(obj, {"model": "(from-file，未调用模型)"})
        av = verdict_gate(obj["verdict"], "art") + critique_gate(obj["verdict"], "art")
        rc = role_consistency(script_obj, obj)
        t_problems, detail = text_gates(md, "设定卡")
        problems = av + rc + t_problems
        _emit(a, md, {"from_file": a.from_file, "verdict": obj["verdict"],
                      "facts": facts, "gates": detail, "usage": {"calls": 0}})
        return _gate_exit(problems, detail, "美术设定卡", a)
    quote = quote_run(a.episodes, 1, a.points_per_ktok)
    _confirm_spend(a, quote, "美术出设定卡")
    res, usage, elapsed, prompt, key, dims, cached = produce_art(
        a, state, usage_acc, facts, 1)
    if res is None:
        _print_prompt_preview(prompt, ART_SYSTEM, "美术 · 设定卡（dry-run）")
        _emit(a, "# dry-run\n\n（未调用模型，未产出设定卡）",
              {"dry_run": True, "prompt_sha": text_hash(prompt), "key": key,
               "key_dims": dims, "facts": facts, "usage": {"calls": 0}})
        return EXIT_OK
    save_state(outdir, state)
    obj = res["obj"]
    _write_artifact(outdir, ART_JSON, obj, ART_MD, res["md"])
    av = verdict_gate(obj["verdict"], "art") + critique_gate(obj["verdict"], "art")
    rc = role_consistency(script_obj, obj)
    t_problems, detail = text_gates(res["md"], "设定卡")
    problems = av + rc + t_problems
    _emit(a, res["md"], {"round": 1, "breakpoint_key": key, "key_dims": dims,
                         "cached": cached, "verdict": obj["verdict"],
                         "facts": facts, "outdir": str(outdir),
                         "usage": usage_of(usage), "usage_raw": usage,
                         "gates": detail, "saved": [ART_MD, ART_JSON]})
    if obj["verdict"].get("verdict") == "not_producible":
        sys.stderr.write("\n" + _red("美术判定这场戏拍不出来") + "：%s\n"
                         % "；".join(obj["verdict"].get("reasons") or ["（未给理由）"]))
        sys.stderr.write("  拍不出来的场次：%s\n"
                         % "；".join(obj["verdict"].get("scenes") or ["（未指出）"]))
    return _gate_exit(problems, detail, "美术设定卡", a)


def cmd_continuity(a):
    outdir = ensure_outdir(a.outdir)
    state = load_state(outdir)
    usage_acc = new_usage()
    script_md = _read_md_artifact(outdir, SCRIPT_MD, "剧本")
    board_md = _read_md_artifact(outdir, BOARD_MD, "分镜表")
    if a.from_file:
        raw = _load_from_file(a.from_file, "矛盾清单")
        obj = normalize_continuity(raw.get("data") if isinstance(raw, dict)
                                   and "data" in raw else raw, script_md)
        md = render_continuity_md(obj, {"model": "(from-file，未调用模型)"})
        problems = verdict_gate(obj, "scripty") + obj["gate_problems"]
        problems = problems + dropped_quote_problems(obj)
        t_problems, detail = text_gates(md, "矛盾清单")
        problems = problems + t_problems
        _emit(a, md, {"from_file": a.from_file, "verdict": obj["verdict"],
                      "conflicts": obj["conflicts"], "dropped": obj["dropped"],
                      "stats": obj["stats"], "gates": detail, "usage": {"calls": 0}})
        return _gate_exit(problems, detail, "矛盾清单", a)
    quote = quote_run(a.episodes, 1, a.points_per_ktok)
    _confirm_spend(a, quote, "场记出矛盾清单")
    res, usage, elapsed, prompt, key, dims, cached = produce_continuity(
        a, state, usage_acc, script_md, board_md, 1)
    if res is None:
        _print_prompt_preview(prompt, SCRIPTY_SYSTEM, "场记 · 矛盾清单（dry-run）")
        _emit(a, "# dry-run\n\n（未调用模型，未产出矛盾清单）",
              {"dry_run": True, "prompt_sha": text_hash(prompt), "key": key,
               "key_dims": dims, "usage": {"calls": 0}})
        return EXIT_OK
    save_state(outdir, state)
    obj = res["obj"]
    _write_artifact(outdir, CONTINUITY_JSON, obj, CONTINUITY_MD, res["md"])
    problems = verdict_gate(obj, "scripty") + obj["gate_problems"]
    problems = problems + dropped_quote_problems(obj)
    t_problems, detail = text_gates(res["md"], "矛盾清单")
    problems = problems + t_problems
    _emit(a, res["md"], {"round": 1, "breakpoint_key": key, "key_dims": dims,
                         "cached": cached, "verdict": obj["verdict"],
                         "conflicts": obj["conflicts"], "dropped": obj["dropped"],
                         "stats": obj["stats"], "outdir": str(outdir),
                         "usage": usage_of(usage), "usage_raw": usage,
                         "gates": detail, "saved": [CONTINUITY_MD, CONTINUITY_JSON]})
    if obj["dropped"]:
        sys.stderr.write("\n" + _red("场记报了 %d 条引文在剧本里找不到（编造引文已剔出）"
                                     % len(obj["dropped"])) + "\n")
        for c in obj["dropped"][:3]:
            sys.stderr.write("   第 %s 条：%s\n" % (c.get("no"), c.get("dropped_why")))
    if obj["verdict"].get("verdict") == "blocking":
        sys.stderr.write("\n" + _red("场记否决：%d 条中高等级矛盾必须修"
                                     % obj["stats"]["blocking"]) + "\n")
    return _gate_exit(problems, detail, "矛盾清单", a)


# ---------------------------------------------------------------------------
# 子命令：run / log / cost / models
# ---------------------------------------------------------------------------

def cmd_run(a):
    if a.max_rounds < 1:
        raise UsageError("--max-rounds 至少为 1")
    if a.max_rounds > CREW["hard_max_rounds"]:
        raise UsageError("--max-rounds 上限是 %d（再多轮就是谈不拢了，"
                         "该报未决项而不是继续烧钱）" % CREW["hard_max_rounds"])
    if a.episodes < 1 or a.episodes > CREW["hard_max_episodes"]:
        raise UsageError("--episodes 要在 1~%d 之间" % CREW["hard_max_episodes"])
    outdir = ensure_outdir(a.outdir)
    state = load_state(outdir)
    usage_acc = new_usage()
    report, rc = _run_crew(a, outdir, usage_acc, state)
    save_state(outdir, state)
    md = (Path(outdir) / REPORT_MD).read_text(encoding="utf-8", errors="replace")
    payload = dict(report)
    payload["cost"] = dict(report["cost"])
    payload["cost"]["budget"] = getattr(a, "budget", None)
    payload["cost"]["points_per_ktok"] = getattr(a, "points_per_ktok", None)
    _emit(a, md, payload, ok=(rc == EXIT_OK))
    if rc == EXIT_OK:
        sys.stderr.write("\n剧组收工：四个角色在最后一轮全部通过，且该轮闸门无命中。\n")
    if rc == EXIT_UNRESOLVED:
        sys.stderr.write("\n" + _red("未决项 %d 条：轮次用完仍未收敛"
                                     % len(report["unresolved"])) + "\n")
        for u in report["unresolved"]:
            sys.stderr.write("   [%s] %s\n" % (u.get("role_cn") or u.get("role"),
                                               u.get("why")))
        if report.get("agreed") and report.get("gate_hits_last_round"):
            sys.stderr.write("   注：四个角色是点了头的，卡住的是**本地闸门**"
                             "（最后一轮仍有 %d 处命中）——\n"
                             "   这同样算未收敛：不写成「已通过」。\n"
                             % report["gate_hits_last_round"])
        sys.stderr.write("   **本包不把这些写成「已通过」**——要收敛就加 "
                         "`--max-rounds` 或按上面的理由改题材/口径。\n")
        _fail(EXIT_UNRESOLVED, "unresolved",
              "轮次用完仍有 %d 项未决（不许假装谈拢）" % len(report["unresolved"]),
              report["unresolved"])
    elif rc == EXIT_GATE:
        _fail(EXIT_GATE, "gate", "闸门命中：%s"
              % json.dumps(report["gates"]["problems"], ensure_ascii=False)[:200],
              report["gates"])
    if report.get("deadlock"):
        sys.stderr.write("\n" + _red(report["deadlock"]) + "\n")
    return rc


def cmd_log(a):
    outdir = check_outdir(a.outdir)
    p = Path(outdir) / LOG_NAME
    if not p.is_file():
        raise UsageError("找不到全过程记录：%s（先跑 `run`）" % p)
    text = p.read_text(encoding="utf-8", errors="replace")
    rp = Path(outdir) / REPORT_JSON
    rep = {}
    if rp.is_file():
        try:
            rep = json.loads(rp.read_text(encoding="utf-8"))
        except ValueError:
            rep = {}
    hist = rep.get("history") or []
    payload = {"log_text": text, "rounds": len(hist), "history": hist,
               "unresolved": rep.get("unresolved") or [],
               "deadlock": rep.get("deadlock"),
               "usage": rep.get("usage") or {},
               "usage_raw": rep.get("usage_raw") or [],
               "log_path": str(p)}
    _emit(a, text, payload)
    return EXIT_OK


def cmd_cost(a):
    """只算钱，一次调用都不发。

    ⚠️ **不报金额**：文本网关的单价平台不公开。给 `--points-per-ktok` 才按外部口径折算。
    """
    q = quote_run(a.episodes, a.max_rounds, a.points_per_ktok)
    per_call_lo, per_call_hi = 1500, 6000      # 实测区间（token）
    rows = []
    rows.append("# 剧组成本估算 · %s 集 × %s 轮" % (a.episodes, a.max_rounds))
    rows.append("")
    rows.append("> **本包只出 token，不编价。** 文本网关的单价平台不公开"
                "（`/api/v1/pricing` 不覆盖 `chat/completions`），"
                "所以这里报**调用次数**与**实测 token 区间**，不报金额。")
    rows.append("")
    rows.append("## 调用次数")
    rows.append("")
    rows.append("| 项目 | 值 |")
    rows.append("|---|---|")
    rows.append("| 每轮调用 | %d 次（编剧 2 + 导演 1 + 美术 1 + 场记 1）"
                % q["calls_per_round"])
    rows.append("| 轮次 | %d |" % q["max_rounds"])
    rows.append("| **合计调用** | **%d 次** |" % q["calls_est"])
    rows.append("")
    rows.append("## token 量级（单次调用实测区间）")
    rows.append("")
    rows.append("| 单次调用 token | 合计 token（下限~上限） |")
    rows.append("|---|---|")
    rows.append("| %d ~ %d | %d ~ %d |" % (
        per_call_lo, per_call_hi, per_call_lo * q["calls_est"],
        per_call_hi * q["calls_est"]))
    rows.append("")
    rows.append("## 断点续跑能省多少")
    rows.append("")
    rows.append("| 情形 | 行为 |")
    rows.append("|---|---|")
    rows.append("| 同一份输入重跑同一个子命令 | 断点命中，**0 次调用、0 token** |")
    rows.append("| 改了题材 / 轮次 / 提示词版本 / 模型 / 温度 / 上一轮裁决 | "
                "对应那一步重出（断点 key 含全部八维） |")
    rows.append("| 第二轮编剧**只改了被指出的场次** | 导演/美术/场记若输入没变，命中缓存 |")
    rows.append("")
    if a.points_per_ktok:
        rows.append("## 按你给的口径折算（**外部单价，非平台公布**）")
        rows.append("")
        rows.append("| 单次 token | 合计 token | 点数 |")
        rows.append("|---|---|---|")
        for tk in (per_call_lo, per_call_hi):
            tot = tk * q["calls_est"]
            pts = points_of_tokens(tot, a.points_per_ktok)
            rows.append("| %d | %d | %s |" % (tk, tot, pts))
        rows.append("")
        rows.append("> `--points-per-ktok %s` 是你给的单价；"
                    "本包**不声称它是平台真实价**。" % a.points_per_ktok)
        rows.append("")
    else:
        rows.append("## 要金额请自己给单价")
        rows.append("")
        rows.append("```")
        rows.append("python3 scripts/run.py cost --episodes %s --max-rounds %s "
                    "--points-per-ktok <点/千token>" % (a.episodes, a.max_rounds))
        rows.append("```")
        rows.append("")
    payload = dict(q)
    payload.update({"token_per_call_range": [per_call_lo, per_call_hi],
                    "token_est_range": [per_call_lo * q["calls_est"],
                                        per_call_hi * q["calls_est"]],
                    "points": points_of_tokens(per_call_hi * q["calls_est"],
                                               a.points_per_ktok),
                    "calls": 0})
    _emit(a, "\n".join(rows), payload)
    return EXIT_OK


def cmd_models(a):
    key = a7w.load_key(getattr(a, "key", None))
    payload = a7w._request("GET", MODELS_URL, key)
    items = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(items, dict):
        items = items.get("data") or items.get("models") or []
    if not isinstance(items, list):
        items = []
    rows = ["# api.a7w.cn 在架模型", ""]
    rows.append("> 模型名会变，**别写死**。上面这个列表里没有 `%s` 也照样能用："
                "它是个别名，会路由到 deepseek-flash 一线。" % DEFAULT_MODEL)
    rows.append("")
    if a.type and a.type != "all":
        f = [m for m in items if str(m.get("type") or m.get("model_type")
                                     or "").lower() == a.type.lower()]
        if f:
            items = f
    rows.append("| 模型名 | 类型 | 说明 |")
    rows.append("|---|---|---|")
    for m in items:
        if isinstance(m, str):
            rows.append("| `%s` | - | - |" % m)
            continue
        rows.append("| `%s` | %s | %s |" % (
            m.get("id") or m.get("model") or m.get("name"),
            m.get("type") or m.get("model_type") or "-",
            (m.get("description") or m.get("owned_by") or "-")[:60]))
    if not items:
        rows.append("| （没有拿到列表） | - | 原始响应见 --json |")
    _emit(a, "\n".join(rows), {"type": a.type, "count": len(items), "models": items})
    return EXIT_OK


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与全库同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py cost --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_model_opts(p, with_out=True):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 %s（实测可用；用 `run.py models` 现查在架模型）"
                        % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=6000, dest="max_tokens",
                   help="最大输出 token，默认 6000（一集剧本给少了会被截断）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词 + 输入摘要 + 提示词卫生自检，"
                        "**不调模型不花钱**")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")
    p.add_argument("--points-per-ktok", type=float, dest="points_per_ktok",
                   help="文本单价（点/千 token）；**平台不公开单价**，"
                        "不给就只报 token、不报金额")
    _add_json(p)
    if with_out:
        p.add_argument("--out", help="把结果写到这个文件（--json 时写 JSON 文本）")


def build_parser():
    # ⚠️ `allow_abbrev=False` 是必须的：默认的"前缀缩写"会把 `--out` 静默当成 `--outdir`，
    # 于是 `--out x.json` 变成"产出目录叫 x.json"，**不报错但写错地方**。
    # 本库踩过这个坑，全族统一关掉缩写。
    ap = argparse.ArgumentParser(
        prog="run.py", allow_abbrev=False,
        description="三剪客 · 短剧剧组（L3 多智能体协作型；只用 api.a7w.cn 的文本端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models　"
               "本包**不出图、不出片**（视频生成是既有包的活）")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("crew", help="列出四个角色与职权（**零成本**，一次调用都不发）",
                       allow_abbrev=False)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件（--json 时写 JSON 文本）")
    p.set_defaults(func=cmd_crew)

    p = sub.add_parser("outline", help="编剧出分集大纲（钩子 / 卡点 / 集尾悬念）",
                       allow_abbrev=False)
    p.add_argument("--topic", required=True, help="短剧题材（一句话说清讲什么）")
    p.add_argument("--episodes", type=int, default=CREW["episodes"],
                   help="集数，默认 %d" % CREW["episodes"])
    p.add_argument("--audience", help="目标受众（不给就让模型自己定）")
    p.add_argument("--brief", help="额外要求")
    p.add_argument("--outdir", default="drama-crew-out", help="产出目录（**不许在包内**）")
    p.add_argument("--from-file", dest="from_file",
                   help="**闸门自检用**：不调模型，直接拿一份 JSON 过闸门")
    p.add_argument("--force", action="store_true", help="忽略断点重做（**会重复花钱**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    _add_model_opts(p)
    p.set_defaults(func=cmd_outline)

    p = sub.add_parser("script", help="编剧出剧本（场景 / 台词 / 情绪）", allow_abbrev=False)
    p.add_argument("--outdir", default="drama-crew-out", help="产出目录（**不许在包内**）")
    p.add_argument("--episodes", type=int, default=CREW["episodes"], help="集数")
    p.add_argument("--from-file", dest="from_file", help="**闸门自检用**：直接拿 JSON 过闸门")
    p.add_argument("--force", action="store_true", help="忽略断点重做（**会重复花钱**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    _add_model_opts(p)
    p.set_defaults(func=cmd_script)

    p = sub.add_parser("board",
                       help="导演出分镜表（景别/机位/时长/转场）—— **可以打回编剧**",
                       allow_abbrev=False)
    p.add_argument("--outdir", default="drama-crew-out", help="产出目录")
    p.add_argument("--episodes", type=int, default=CREW["episodes"], help="集数")
    p.add_argument("--from-file", dest="from_file", help="**闸门自检用**：直接拿 JSON 过闸门")
    p.add_argument("--force", action="store_true", help="忽略断点重做（**会重复花钱**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    _add_model_opts(p)
    p.set_defaults(func=cmd_board)

    p = sub.add_parser("art",
                       help="美术出场景与角色设定卡（文本）—— **可否决「这场拍不出来」**",
                       allow_abbrev=False)
    p.add_argument("--outdir", default="drama-crew-out", help="产出目录")
    p.add_argument("--episodes", type=int, default=CREW["episodes"], help="集数")
    p.add_argument("--from-file", dest="from_file", help="**闸门自检用**：直接拿 JSON 过闸门")
    p.add_argument("--force", action="store_true", help="忽略断点重做（**会重复花钱**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    _add_model_opts(p)
    p.set_defaults(func=cmd_art)

    p = sub.add_parser("continuity",
                       help="场记出矛盾清单（**每条必须引用剧本原文**）", allow_abbrev=False)
    p.add_argument("--outdir", default="drama-crew-out", help="产出目录")
    p.add_argument("--episodes", type=int, default=CREW["episodes"], help="集数")
    p.add_argument("--from-file", dest="from_file", help="**闸门自检用**：直接拿 JSON 过闸门")
    p.add_argument("--force", action="store_true", help="忽略断点重做（**会重复花钱**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    _add_model_opts(p)
    p.set_defaults(func=cmd_continuity)

    p = sub.add_parser("run",
                       help="一条命令跑完剧组协作（多轮，含打回重写与未决项）",
                       allow_abbrev=False)
    p.add_argument("--topic", required=True, help="短剧题材")
    p.add_argument("--episodes", type=int, default=CREW["episodes"], help="集数")
    p.add_argument("--max-rounds", type=int, default=CREW["max_rounds"], dest="max_rounds",
                   help="最多几轮（默认 %d，上限 %d）"
                        % (CREW["max_rounds"], CREW["hard_max_rounds"]))
    p.add_argument("--audience", help="目标受众")
    p.add_argument("--brief", help="额外要求")
    p.add_argument("--note", action="append",
                   help="人工意见（可重复），会作为第一轮返修指令给编剧")
    p.add_argument("--outdir", default="drama-crew-out", help="产出目录（**不许在包内**）")
    p.add_argument("--show-inputs", action="store_true", dest="show_inputs", default=True,
                   help="打印各角色看到的信息（**信息不对称的现场证据**，默认开）")
    p.add_argument("--no-show-inputs", action="store_true", dest="no_show_inputs",
                   help="关掉输入摘要打印")
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑（**会重复花钱**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="整条链路的预算上限（点）")
    _add_model_opts(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("log", help="读全过程记录（每一轮的产出、打回、否决、未决项、token）",
                       allow_abbrev=False)
    p.add_argument("--outdir", default="drama-crew-out", help="产出目录")
    _add_json(p)
    p.add_argument("--out", help="把记录写到这个文件")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("cost", help="只算钱（本地计算，一次调用都不发；**只报 token 不报金额**）",
                       allow_abbrev=False)
    p.add_argument("--episodes", type=int, default=CREW["episodes"], help="集数")
    p.add_argument("--max-rounds", type=int, default=CREW["max_rounds"], dest="max_rounds",
                   help="轮次")
    p.add_argument("--points-per-ktok", type=float, dest="points_per_ktok",
                   help="文本单价（点/千 token）；不给就**不报金额**（平台未公开单价）")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=cmd_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）",
                       allow_abbrev=False)
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=cmd_models)

    return ap


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与不用 `--json` 时完全一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout          # 记住真 stdout（信封不许被重定向吞掉）
    _JSON["want"] = "--json" in argv_eff  # argparse 失败时还没有 a，先按命令行判断
    _JSON["emitted"] = False
    _JSON["reason"] = None
    _JSON["pending"] = None
    try:
        return _main(argv_eff)
    except Exception as exc:                      # noqa: BLE001 —— 故意的：契约要求给信封
        if not _JSON["want"]:
            raise                                 # 非 --json：原样冒泡
        traceback.print_exc()                     # 完整栈 → stderr（不吞、不截断）
        _json_internal(exc)
        return EXIT_INTERNAL


def _main(argv_eff):
    ap = build_parser()
    try:
        a = ap.parse_args(argv_eff)
    except SystemExit as exc:
        # argparse 的参数错（退出码 2）也要给信封；--help（0）不算失败
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    if getattr(a, "no_show_inputs", False):
        a.show_inputs = False
    kind, msg = None, None
    try:
        rc = a.func(a)
    except UsageError as exc:
        sys.stderr.write("\n%s\n" % _red(str(exc)))
        rc, kind, msg = EXIT_USAGE, "usage", str(exc)
    except GateError as exc:
        sys.stderr.write("\n%s\n" % _red(str(exc)))
        rc, kind, msg = EXIT_GATE, "gate", str(exc)
    except BudgetError as exc:
        sys.stderr.write("\n%s\n" % _red(str(exc)))
        rc, kind, msg = EXIT_BUDGET, "budget", str(exc)
    except CrewError as exc:
        sys.stderr.write("失败：%s\n" % exc)
        rc, kind, msg = EXIT_CALL, "call", str(exc)
    except KeyboardInterrupt:
        sys.stderr.write("已中断\n")
        rc, kind, msg = EXIT_INTERRUPT, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        k = reason.get("kind") or kind or _KIND_BY_EXIT.get(rc, "gate")
        m = reason.get("message") or msg or "命令以退出码 %s 结束（人读原因见 stderr）" % rc
        det = reason.get("detail")
        # 有暂存结果 → 并入 error/exit 一起写（stdout 只有一个 JSON 文档）；
        # 没有暂存结果 → 发独立错误信封。两条路都只调用一次 `_json_write`。
        if _JSON["pending"] is not None and _json_want(a):
            _flush_json(rc, k, m, det)
        else:
            _json_fail(rc, k, m, det, a)
    else:
        _flush_json(0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
