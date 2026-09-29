#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 小红书笔记工厂 —— 真正干活的脚本（零第三方依赖）。

一条流水线，四个阶段，钱花在哪一段是分开的：

    angles   从母稿/产品信息出 N 个**互不重复**的切入角度   ← 默认零成本（本地角度库）
    notes    按角度逐篇写笔记正文 + 话题标签                ← 花钱（一篇一次调用）
    covers   出封面图方案 + 出图（3:4 大字标题）            ← 真花钱，先报价
    check    对已有笔记做本地合规自检                        ← 零成本
    all      整条链路，**断点续跑**（已完成的阶段直接跳过，不重复扣钱）
    cost     只算钱（文本按 token；出图按实测 24 点/张 1K）
    models   现查 api.a7w.cn 在架模型（模型名会变，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    出图提交   POST https://api.a7w.cn/api/v1/apps/nano_banana/submit （异步）
    任务轮询   GET  https://api.a7w.cn/api/v1/tasks/<task_id>
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py angles  --file 母稿.md --count 5
    python3 run.py notes   --file 母稿.md --count 5 --outdir %TEMP%/xhs-notes --json
    python3 run.py covers  --notes %TEMP%/xhs-notes/notes.json --count 2 --outdir %TEMP%/xhs-notes --yes
    python3 run.py check   --file %TEMP%/xhs-notes/notes.json
    python3 run.py all     --file 母稿.md --count 5 --outdir %TEMP%/xhs-notes --yes --budget 200
    python3 run.py cost    --file 母稿.md --count 5 --cover-count 5

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py notes ... --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）


================================================================================
设计取舍（每一条都是踩过坑才定下来的，改之前先读）
================================================================================

1. **一个角度一次调用，绝不让模型一次写完 N 篇。**
   这是本包最重要的一条。多平台改写那一次实测说明了问题：一次调用让模型产出多份，
   它会先写"最好写的那一份"，再把剩下的裁剪出来 —— 结果是同一套话换 N 张皮，
   单看每篇都像样，合起来等于只写了一篇。
   所以 `notes` 是**每个角度独立一次调用**，并且在提示词里明确给出"这一篇专属的角度"
   与"同批其它篇的角度（不许写）"。N 篇之间再用本地 `cross_note_check` 两两量相似度。

2. **角度是数据，不是提示词散文。**
   30 个切入角度放在 `ANGLES` 这张表里（人群 × 场景 × 情绪 × 落点），
   提示词与本地闸门都从表里读。换主题只换 `--file`，换角度库才改表。

3. **闸门是硬闸门。**
   命中即标红 + stderr 汇总 + 退出码非 0，不许只警告（退出码可直接进 CI）。
   只有"风格类"（标签数、emoji）与"结构类"的软项才只扣分 ——
   标准是「发出去会出事」：合规违禁会被罚，标签少一个是质量不达标，两者不是一回事。

4. **比例只看真实像素。**
   接口自报 `aspect_ratio=3:4` 不算数，读文件头的宽高才算数。
   上游按 32 对齐给像素，请求 3:4 实测给 **864x1184**（偏差 2.70%），
   所以容差 3% 内不算假但**一定打印真实像素与偏差**，想要像素级精确就用 `--snap`（裁到 864x1152）。

5. **成本前置。**
   出图前报价，没有 `--yes` 或 `--budget` 不提交任何任务；`--budget` 用**真实扣费**累计，
   超了就地停。文本模型网关不公布单价 —— 所以文本只出 token 数，**金额必须你自己填单价，本包拒绝编价**。
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import time
import traceback
import unicodedata
import urllib.error
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w       # noqa: E402  —— 逐字节等于规范版，**不要往它里面加业务代码**
import imgprobe  # noqa: E402  —— 本包自己的图片探针（只读真实像素）

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"
APP_IMAGE = "nano_banana"
SUBMIT_URL = "{}/api/v1/apps/{}/submit".format(a7w.HOST, APP_IMAGE)
TASK_URL = a7w.HOST + "/api/v1/tasks/{}"

# 实测可用：这个别名会路由到 deepseek-flash 一线。它**不在** /api/v1/models 的返回列表里
# （那个列表给的是 DeepSeek-V4-Pro / DeepSeek-V4-Flash / DeepSeek-V3.2 这些版本号名），
# 所以别拿「列表里没有」当「不能用」。要换模型用 `run.py models` 现查。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4
POLL_INTERVAL = 5
POLL_TIMEOUT = 600
STATE_NAME = "xhs-note-factory-state.json"
ANGLES_NAME = "angles.json"
NOTES_NAME = "notes.json"
COVERS_NAME = "covers.json"
COVER_DIR = "covers"

# 退出码（可直接用于 CI）
EXIT_OK = 0            # 全部干净
EXIT_INTERNAL = 1      # 没预料到的异常（代码 bug）；--json 下给 internal 信封
EXIT_USAGE = 2         # 参数/配置错误（含 --outdir 指到包内、给了 --budget 却没给单价）
EXIT_GATE = 3          # 有硬闸门命中（合规/占位符/照抄示例/笔记规格/跨篇换皮/出图比例）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断


# ===========================================================================
# 小红书笔记规格表（唯一事实来源）
#
# 【铁律】这里的每个字段都是「数据」：提示词与本地闸门都从这里读。
# 想改字数上限、标签数量、首行钩子判据，**只改这张表**，不要去改逻辑。
#
# 口径来源：小红书公开的创作规范 + 三剪客团队自己的投放经验整理，属于**经验口径**，
# 不是平台官方审核标准（官方标准不公开且会变）。取值偏保守，宁窄不宽。
# ===========================================================================

XHS = {
    "name": "小红书",
    # 正文上限：小红书单篇正文 1000 字（经验口径）。下限是"能说清一件事"的底线。
    "body_chars": (260, 1000),
    # 话题标签 5~8 个（本包的硬口径）
    "hashtags": (5, 8),
    # 段落：小红书一段就是一两句话，短、空行多
    "para_chars": (8, 90),
    "para_count": (4, 16),
    # 标题：口语短标题
    "title_chars": (8, 24),
    # 首行必须是钩子：这一行决定点不点开
    "hook": "第一行必须是钩子：一个问题、一个具体数字、一个身份自报、或一句反常识判断。"
            "不许用「大家好」「今天来分享」这类开场",
    "cta": r"收藏|评论|点赞|关注|告诉我|教教我|聊聊|说说|你们|有没有|评论区|留言|蹲|求",
    "must": [
        "正文里不许出现站外联系方式（微信号 / 手机号 / 私信我 / 加V）",
        "每段 1~3 行，段与段之间空一行",
        "5~8 个话题标签，放在正文最后，每个标签以 # 开头（不带空格）",
    ],
}

# 出图规格：小红书封面 3:4
COVER_RATIO = "3:4"
COVER_SIZE = (864, 1152)      # 本地裁准后的目标像素（--snap）
COVER_RESOLUTION = "1K"

# 封面大字标题（`cover_text`）的硬上限。
# 取值依据：1.0.4 及以前 `build_cover_prompt()` 里写死的是 `[:20]`（软上限），
# 文档（`references/cover-and-size.md`）给的是「12~18 字，超过 20 字一行放不下」——
# 代码更严且是实际生效的那一个（送进提示词的文案就是前 20 字），所以闸门按 20 判。
# 1.0.5 起**不再静默截断**：超限直接拦下（EXIT_GATE），把实际长度与上限都报出来。
COVER_TEXT_MAX = 20


# ===========================================================================
# 角度库（数据，不是提示词散文）
#
# 30 个切入角度 = 人群 × 场景 × 情绪 × 落点。角度之间刻意做到**互斥**：
# 「新手踩坑」与「老手复盘」不是一回事，「算账」与「清单」也不是一回事。
# `--strategy local`（默认）就是从这里按顺序取，**零成本、可复现**；
# 想让它针对具体主题更贴题，用 `--strategy llm`（一次调用）。
# ===========================================================================

ANGLES = [
    {"key": "newbie-pit", "name": "新手踩坑", "persona": "刚接触这件事半年的新手",
     "scene": "第一次自己动手，走了三段弯路", "emotion": "自嘲 + 庆幸",
     "focus": "把自己踩过、且别人一定会踩的坑按时间顺序讲出来，每个坑写清「当时怎么想 → 结果怎样」"},
    {"key": "cost-account", "name": "算账派", "persona": "习惯把每笔钱记下来的打工人",
     "scene": "把这件事三个月的花销一笔笔列出来", "emotion": "冷静 + 有点意外",
     "focus": "用真实账目说话：花了多少、省在哪、哪一笔事后觉得不值，不用形容词渲染"},
    {"key": "beginner-mind", "name": "反常识", "persona": "一开始也信了常见说法的人",
     "scene": "照常见说法做了，结果发现不成立", "emotion": "被纠正后的清醒",
     "focus": "先摆出那个大家都信的说法，再说自己实测的结果为什么不成立，给出你现在的判断"},
    {"key": "compare", "name": "横向对比", "persona": "买东西前一定比三家的人",
     "scene": "把三种常见选择摆在一起比", "emotion": "就事论事",
     "focus": "对比维度固定成三条（成本 / 耗时 / 上手难度），逐条说清各自适合谁，不下「谁最好」的结论"},
    {"key": "checklist", "name": "清单体", "persona": "不喜欢看长文的人",
     "scene": "把要点压缩成可以直接照着做的清单", "emotion": "干脆",
     "focus": "给 5~7 条可执行动作，每条一句话，不解释原理，读者照着做就行"},
    {"key": "time-saving", "name": "省时间", "persona": "每天只有一小时的上班族",
     "scene": "把流程从两小时压到二十分钟", "emotion": "轻松",
     "focus": "讲清「哪一步最费时间、砍掉它的代价是什么」，给一个能复制的顺序"},
    {"key": "avoid-overspend", "name": "防割韭菜", "persona": "被收过一次智商税的人",
     "scene": "识别出哪些支出其实不必要", "emotion": "提醒式、不指责",
     "focus": "列出哪些钱可以不花、判断依据是什么，刻意用「我的判断」而不是「一定」"},
    {"key": "lazy-way", "name": "懒人版", "persona": "很怕麻烦的人",
     "scene": "找到一条最省事的路径", "emotion": "坦然的偷懒",
     "focus": "只讲那条最省事的路，并诚实说清它牺牲了什么（别假装没有代价）"},
    {"key": "detail-nobody", "name": "细节控", "persona": "会盯着一个参数看半天的人",
     "scene": "在一个别人都忽略的细节上做对了", "emotion": "专注 + 得意",
     "focus": "整个笔记只讲一个细节，把这个细节为什么关键讲透，别铺开讲别的"},
    {"key": "small-space", "name": "空间受限", "persona": "住处或工位空间很小的人",
     "scene": "在有限空间里把这件事做成", "emotion": "踏实",
     "focus": "围绕「地方小」这个约束展开，给出取舍与替代方案，尺寸/数量尽量具体"},
    {"key": "busy-mom", "name": "带娃族", "persona": "一个人带娃还要顾自己的人",
     "scene": "只能利用碎片时间", "emotion": "疲惫但不想放弃",
     "focus": "围绕「时间被切碎」写：怎么把这件事塞进碎片时间，哪些步骤能提前做完"},
    {"key": "student-budget", "name": "预算党", "persona": "生活费有限的学生",
     "scene": "用很少的钱做到八成的效果", "emotion": "精打细算的乐观",
     "focus": "讲清「八成效果」具体指什么、剩下的两成缺在哪，不要吹成「一样好」"},
    {"key": "office-worker", "name": "打工人", "persona": "朝九晚六还要加班的人",
     "scene": "把这件事嵌进工作日", "emotion": "务实",
     "focus": "以工作日为单位排一个可执行的时间表，说明哪天做什么、为什么这样排"},
    {"key": "stay-home", "name": "宅家派", "persona": "休息日基本不出门的人",
     "scene": "完全在家把这件事办完", "emotion": "舒服",
     "focus": "全部步骤都要能在家里完成，凡是要出门的环节都给替代方案"},
    {"key": "long-term", "name": "长期主义", "persona": "已经坚持这件事一年以上的人",
     "scene": "回头看这一年的变化", "emotion": "平静 + 有底气",
     "focus": "讲时间尺度上的变化：第一个月、第三个月、现在各是什么状态，别夸大"},
    {"key": "quit-moment", "name": "差点放弃", "persona": "中途差点放弃的人",
     "scene": "卡在最难受的那个阶段", "emotion": "真实、不励志",
     "focus": "把「卡住」的那一段写具体：卡在哪、当时怎么想的、后来是什么让你继续的"},
    {"key": "single-item", "name": "单品深挖", "persona": "把一件东西用到底的人",
     "scene": "只用一件核心工具把事做完", "emotion": "专注",
     "focus": "整篇只围绕一件东西：怎么用、用多久、什么时候不该用它"},
    {"key": "quick-fix", "name": "应急方案", "persona": "被临时状况逼到墙角的人",
     "scene": "明天就要用，今天才开始准备", "emotion": "紧张但有条理",
     "focus": "按「还剩多少时间」给出分档方案（一天 / 三小时 / 一小时），每档都说清能到什么程度"},
    {"key": "mindset", "name": "心态篇", "persona": "被这件事搞得焦虑过的人",
     "scene": "把情绪这一关也过了", "emotion": "坦诚",
     "focus": "只谈情绪与预期管理：哪些焦虑是多余的、哪些预期要提前调低，少讲操作"},
    {"key": "tools", "name": "工具流", "persona": "喜欢折腾工具的人",
     "scene": "把流程拆给几个工具接力", "emotion": "清爽",
     "focus": "讲清每个环节用什么、为什么不用别的，工具只写到「做什么用」，不写站外导流"},
    {"key": "automation", "name": "自动化", "persona": "能省一步就省一步的人",
     "scene": "把重复动作固化下来", "emotion": "满足",
     "focus": "聚焦「重复动作」：哪几步每周都要做、怎么一次配置反复使用"},
    {"key": "one-person", "name": "一个人做", "persona": "没有团队、全靠自己的人",
     "scene": "一个人把这件事从头做到尾", "emotion": "独立",
     "focus": "按「一个人能扛多少」写：哪些环节必须外包或省掉，哪些能自己啃下来"},
    {"key": "low-budget-start", "name": "零预算起步", "persona": "一分钱都不想先投的人",
     "scene": "用现有的东西先跑起来", "emotion": "轻装",
     "focus": "先讲「什么都不买能不能开始」，再讲第一笔钱该花在哪、为什么是那一笔"},
    {"key": "night-owl", "name": "下班后做", "persona": "只有晚上十点后有空的人",
     "scene": "把这件事放在夜里做", "emotion": "安静",
     "focus": "围绕「精力已经不多」这个前提写：怎么降低每一步的启动成本"},
    {"key": "data-driven", "name": "数据复盘", "persona": "习惯记录过程的人",
     "scene": "用自己记下来的数字回看这件事", "emotion": "克制",
     "focus": "只讲自己记录的指标与它的变化，明确说清样本小、不代表所有人"},
    {"key": "mistake-list", "name": "错误清单", "persona": "复盘过很多次的人",
     "scene": "把常见的错误做法一条条列出来", "emotion": "直白",
     "focus": "每条只写「错在哪 + 正确做法一句」，不铺垫、不举长例"},
    {"key": "seasonal", "name": "时间点切入", "persona": "会在特定时间点做这件事的人",
     "scene": "换季 / 月初 / 新阶段开始的时候", "emotion": "有计划",
     "focus": "讲清为什么这个时间点做更合适，以及错过这个时间点该怎么办"},
    {"key": "first-week", "name": "第一周记录", "persona": "刚开始第一周的人",
     "scene": "把第一周每天的状态记下来", "emotion": "新鲜",
     "focus": "按天写第一周：每天做了什么、什么感觉、哪一天最难，别写成总结陈词"},
    {"key": "expert-review", "name": "同行复盘", "persona": "已经把这件事做成过几次的人",
     "scene": "回头把自己做对的几件事挑出来讲", "emotion": "笃定但不炫耀",
     "focus": "只讲「回头看，真正起作用的是哪几件事」，每条都要有具体场景支撑"},
    {"key": "qa", "name": "答疑体", "persona": "被问过很多次同样问题的人",
     "scene": "集中回答被问最多的几个问题", "emotion": "耐心",
     "focus": "以问句开头，一问一答，5 个问题以内，答案控制在三行内"},
]
ANGLE_KEYS = [a["key"] for a in ANGLES]


# ===========================================================================
# 闸门数据一：合规（广告法违禁词 + 小红书平台特有红线）
#
# 这是一道**粗筛**：宁可多报也别漏报，最终判断仍要人工复核，
# 且不等于任何平台的官方审核结论（官方标准不公开、会变）。
# ===========================================================================

BANNED_PATTERNS = [
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎|顶级|厉害)", "高",
     "广告法第九条禁止「最高级」用语", "superlative"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    # `(?<![国网史])`：不重复接「全国第一 / 全网第一 / 史上第一」——
    # 那三种整串已经被上一条规则按「绝对化价格承诺」抓走了。
    # 少了这个 lookbehind，「全国第一」会额外多报一条「第一」（重复报，且理由不对），
    # 而且序数豁免会把它误放过一半 —— 实测发现并修掉。
    (r"(?<![国网史])第一(名|品牌|选择|名)?(?!次)|No\.?\s*1|TOP\s*1|排名第一|销量第一|行业第一", "高",
     "「第一」类排他性表述", "ordinal"),
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
    (r"独家|首个|首创|填补空白|领先(品牌|技术)", "中",
     "排他性表述需有可举证依据"),
    # `唯一` 在真实笔记里最常见的用法是「不把 X 当成唯一入口 / 唯一标准」这种**否定式**，
    # 它不是排他性宣称（恰恰相反，是在反对排他）。所以只在「唯一 + 名词」时才判命中；
    # 「唯一入口」「唯一标准」「唯一选择」这些都带名词，照拦。
    (r"唯一的?(指标|标准|入口|选择|办法|方法|方案|答案|品牌|产品|理由|原因|出路|解)",
     "中", "排他性表述需有可举证依据"),
    (r"纯天然|无添加|零添加|无毒无害", "中",
     "成分/材质宣称需与检测报告一致"),
    (r"点击链接|加微信|私信我|扫码(加|进|领)|vx|VX|微信号|加V", "中",
     "站外导流，平台普遍限制"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看|赶紧转发", "中",
     "标题党式诱导"),
    (r"[！!]{2,}|[?？]{3,}", "低",
     "标点堆砌，易被判标题党/低质"),
]

# ---------------------------------------------------------------------------
# 小红书平台特有红线：**同一个表达在不同平台的风险不一样**，所以单列一张表。
# 平台文档里写的是"禁止站外导流"，落成可判定的正则就是下面这些。
# ---------------------------------------------------------------------------
PLATFORM_REDLINES = [
    (r"微信|vx|VX|手机号|电话|扣扣|QQ|私信|加我|联系我", "高",
     "小红书对站外导流零容忍，出现联系方式即高危"),
    (r"淘宝|天猫|京东|拼多多|链接在|评论区有链接", "高",
     "引导到站外电商平台，属违规导流"),
    # 以下三类是小红书特有的、比广告法更严的表述：
    (r"亲测|实测|绝对|闭眼入|人手一个|全网", "中",
     "虚假种草/绝对化体验表述，笔记社区严查"),
    (r"点赞|收藏|关注(我)?(才|才能)看|三连", "中",
     "诱导互动，笔记会被限流"),
    # 医疗 / 功效类红线：小红书对功效宣称比广告法抓得更细，
    # 「变白」「淡斑」这类日常说法在普通笔记里同样高危。
    (r"美白|祛斑|祛痘|淡斑|抗痘|生发|防脱|消炎|杀菌|抑菌|排毒|养胃|助眠|提高免疫", "高",
     "功效/身体结果宣称，普通内容不得使用（特殊化妆品、保健食品需资质）"),
    (r"医用|药用|药妆|械字号|消字号|蓝帽子|疗程", "高",
     "医疗器械/药品类表述，须与注册证范围一致"),
]

# 每项统一补成四元组 (正则, 等级, 解释, 语境标签)，语境标签只有 superlative 用了。
# 写成显式循环而不是花哨的推导式：上一版的花式推导式可读性差到我自己要看两遍。
BANNED_RE = []
for _pat in BANNED_PATTERNS:
    _p, _lvl, _why = _pat[0], _pat[1], _pat[2]
    _ctx = _pat[3] if len(_pat) > 3 else None
    BANNED_RE.append((re.compile(_p), _lvl, _why, _ctx))
PLATFORM_REDLINE_RE = [(re.compile(p), lvl, why) for p, lvl, why in PLATFORM_REDLINES]

LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}
COMPLIANCE_DEDUCT = {"高": 40, "中": 20, "低": 8}

# ---------------------------------------------------------------------------
# 「最高级」用语的语境豁免（**这是被实测误伤逼出来的**）
#
# 事故复盘：真实原稿里有一句「回头翻一条自己播放量最低的视频」，
# 被「最X」规则判成高风险「广告法第九条禁止最高级用语」并整篇拦截。
# 这个诊断是**错的** —— 那是在描述自己的数据，不是对商品/服务的绝对化宣称。
# 错的不只是等级，是理由本身就不成立。「宁可多报也别漏报」在这里代价过高：
# 一个正确写法的稿子被判违规，使用者就会开始无视闸门，闸门等于废了。
#
# 豁免条件刻意做得**很窄**，只放过明确在说数据极值的形态：
#   · `最X` 前一个字是计量类名词（量/率/数/分/位/条/次/段/部/集/页/个/天/月/年）
#   · 且 `最X` 后面紧跟「的」或「之」
# 命中豁免时**整处放过**，但会在产出里登记（`gates.compliance.exempted`），
# 报告里明说「本地放过了 1 处疑似绝对化用语」—— **不静默放过**。
#
# 句首的「最好/最低」**不豁免**：`bool(before)` 那一步就是为了它 ——
# 空字符串在 Python 里 `"" in "量率数…"` 是 True，
# 漏了这一步句首的绝对化用语会被全部误豁免（写这段时自己踩到的坑）。
#
# 豁免词表刻意**不含** `时`/`款`/`种`/`家`/`价`：
#   「课时最低的课程」「单价最低」都是真实的价格宣称形态，必须照拦。
# ---------------------------------------------------------------------------

MEASURE_PREFIX = "量率数分位条次段部集页个天月年"


def _is_data_extreme(text, m):
    start = m.start()
    end = m.end()
    before = text[start - 1] if start > 0 else ""
    after = text[end:end + 1]
    return bool(before) and before in MEASURE_PREFIX and after in ("的", "之")


# ---------------------------------------------------------------------------
# 「第一」用语的语境豁免（**这一条是第二次真机实测逼出来的，比上一条更微妙**）
#
# 事故复盘（本包真机实测第一轮）：三篇笔记**全部**因为同一个理由被判高风险拦截 ——
# 「命中『第一』类排他性表述」。但真实原文是叙事里的序数：
#     「第一个坑就来了」「第一个月做了 4 部」「第一部 80 集的剧」
# 这些不是排他性宣称，是「第一章」式的顺序词。三篇全红、理由全错，
# 使用者第一反应就是不再看这道闸门 —— 跟上一条豁免的成因完全一样。
#
# 豁免条件写得**很窄**，只放过「第 + 阿拉伯数字/中文数字 + 计量类量词」这一种形态，
# 也就是明确可数的序数：
#     「第一个坑」「第一部剧」「第 3 个月」→ 放过（并登记，不静默）
#     「排名第一」「销量第一」「行业第一」「第一品牌」→ 照拦（前面不是「第」字）
#     「第一次」→ 本来就不匹配（正则里的 `(?!次)` 已经排掉）
#
# 唯一漏不掉的风险形态是「第 1 的课程」这种表述，但中文里它不成立（得写「第一名」），
# 「第一名」前一个字是「第」、不满足括号外的「第」判定 → 仍然照拦。
# ---------------------------------------------------------------------------
ORDINAL_UNITS = "个种部集条次段页章节期款年月天周秒分钟遍轮套门项步版批届档层把回关"
CN_NUM = "一二三四五六七八九十百千万零两"


def _is_ordinal_sequence(text, m):
    """`第一(名|品牌|…)` 是否其实是「第 + 数字 + 量词」式的序数（叙事用法）。"""
    start, end = m.start(), m.end()
    if text[start:start + 1] != "第":
        return False
    rest = text[start + 1:]
    # 第 + 1~2 位数字 + 量词
    mm = re.match(r"^[\d%s]{1,2}" % CN_NUM, rest)
    if not mm:
        return False
    nxt = rest[mm.end():mm.end() + 1]
    return nxt in ORDINAL_UNITS


# ===========================================================================
# 闸门数据二：占位符残留
#
# 为什么单列一道闸门：模型把 `{产品名}` `[待填]` 这类「编稿脚手架」原样留在产出里，
# 稿子看起来是完整的，发出去才发现有一半是空白 —— 比明显报错更危险。
# ===========================================================================

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


# ===========================================================================
# 闸门三：prompt_echo（照抄提示词示例）
#
# 事故复盘（本库标题工坊实测，两次）：
#   1. 提示词里写过正例 → 模型直接产出同构句子
#   2. 提示词里留过的示例，是那一轮**最高分 89.0** 的标题，一字不差
# 第 2 例性质更重：最高分那条是「抄了标准答案」，不是「真的最好」，排序就废了。
#
# 关键结论：**模型会照抄示例，哪怕那个示例标着「这是错的写法」。**
# 所以本包的提示词里不出现任何一句可直接复制的完整中文句子，举例只用**跨主题**的
# 描述性说明；万一以后有人又把真实示例加回提示词，这道闸门会兜住。
#
# 三条判据（任一即命中）：
#   · 去标点后完全相等
#   · 字符二元组 Jaccard ≥ 0.75
#   · 示例的二元组**覆盖度 ≥ 0.60**（把示例夹带进更长的句子里，Jaccard 会被长度摊薄）
# 长度守卫是**相对**的：目标归一化长度 < max(6, len(示例)//2) 就不比，
# 因为短串的二元组集合太小、指标会虚高。
#
# 阈值标定依据（本库实测）：196 条正常产出与跨主题示例的最高相似度只有 0.174，
# 而「少两个字的同构照抄」是 0.765 —— 0.75 既能兜住轻改写，离正常上限还有 4 倍余量。
# ===========================================================================

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6

# 提示词里出现过的示例文本（**跨主题**，正常不该被抄）。新增示例必须登记到这里。
# 主题刻意选「阳台种小番茄 / 入门吉他」，与本包真实业务（小红书笔记）明显不搭。
PROMPT_SAMPLES = [
    "阳台种小番茄第三周，叶子发黄其实是水浇多了",
    "零基础学吉他，前两周手指会疼到想放弃",
    "租房族怎么在阳台种菜，我只用三个花盆",
    "学了三个月吉他，我发现卡住新手的不是和弦",
    "小番茄只开花不结果，我换了这一种授粉办法",
]

_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的文案往往只改标点（`，`↔`、`↔空格）或换行位置，所以必须先抹平再看。
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


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


def prompt_echo(text, samples=None):
    """文本是否与提示词里登记过的示例「抄得太近」。

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"。
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


def split_sentences(text):
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def prompt_echo_scan(text, samples=None, label="正文"):
    """在一段长文本里找「照抄提示词示例」的地方。

    **为什么不能只比整段**（写完闸门后自测发现的漏洞）：
    正文有几百上千字，示例只有二三十字，把整段拿去算 Jaccard，分母被撑大，
    相似度永远接近 0 —— 模型把示例原样抄进正文的某一段，这道闸门完全看不见。
    而长文里「抄示例」恰恰就是「有一段是抄的」。所以判定分两层：
      1. 整段比一次（兜住整篇照抄），这一层只认 exact / jaccard
      2. **逐句比一次**（含覆盖度判据），兜住「某一句是抄的」
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
            why = "正文里的「{}」与提示词示例去掉标点后完全相同（照抄示例）".format(seg[:20])
        else:
            why = ("正文里的「{}」与提示词示例相似度 {:.2f}，属同构照抄"
                   .format(seg[:20], score))
        hits.append({"part": label, "segment": seg[:40], "sim": round(score, 3),
                     "sample": sample, "why": why})
        break                      # 一处命中足够拦截，不用把整篇列完
    return hits


# ===========================================================================
# 闸门五：跨篇换皮检测（纯本地）
#
# 这是本包**最该有**的一道闸门。批量出笔记的失败模式不是"某一篇写坏了"，
# 而是"N 篇其实是同一篇换个开场" —— 单看每一篇都像样，合起来等于只写了一篇。
# 人眼很难发现（尤其 N 篇不并排看），但字符二元组 Jaccard 一眼看穿。
#
# 判定：两两比较正文，只有**两边都够长**（≥ 150 字）时才比，
# 因为短正文的二元组集合太小、相似度会虚高。
# 阈值 0.65 是经验标定：同一主题但角度不同的两篇实测在 0.20~0.45，
# 而"把一篇的开场换个说法再抄一遍"实测在 0.72 以上，0.65 落在中间的空白带。
# ===========================================================================

CROSS_MIN_CHARS = 150
CROSS_SIM = 0.65


def cross_note_check(items, sim=CROSS_SIM):
    """两两比较各篇笔记正文，返回相似度矩阵与命中列表。"""
    keys = [k for k in items if (items[k].get("body") or "")]
    pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            ba, bb = items[a]["body"], items[b]["body"]
            if count_chars(ba) < CROSS_MIN_CHARS or count_chars(bb) < CROSS_MIN_CHARS:
                continue
            s = _similarity(ba, bb)
            pairs.append({"a": a, "b": b,
                          "a_name": items[a].get("angle_name") or a,
                          "b_name": items[b].get("angle_name") or b,
                          "sim": round(s, 3), "flagged": s >= sim})
    pairs.sort(key=lambda p: -p["sim"])
    return {"threshold": sim, "min_chars": CROSS_MIN_CHARS, "pairs": pairs,
            "flagged": [p for p in pairs if p["flagged"]],
            "max_sim": pairs[0]["sim"] if pairs else None}


# ===========================================================================
# 文本工具
# ===========================================================================

def count_chars(s):
    """正文字数：去掉所有空白字符后的字符数（中文一个字算一个，emoji 算一个）。

    为什么去掉空白：小红书正文是一句一行、段间空行，如果换行算进字数，
    同一个内容「排成一段」和「排成十行」会差出十几个字，口径就不一致了。
    """
    return len(re.sub(r"\s+", "", s or ""))


def split_paras(body):
    """拆段：按换行拆，去掉空行。口径统一为「一个非空行 = 一段」。"""
    return [ln.strip() for ln in (body or "").splitlines() if ln.strip()]


def first_line(text):
    """取第一行（首行钩子的判定单位）。"""
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if ln:
            return ln
    return ""


# 首行钩子的判据（本地启发式，逐条都能解释给学生听）：
#   · 疑问式      —— 句尾问号，或含「为什么 / 怎么 / 是不是 / 要不要」
#   · 数字切入    —— 首行出现阿拉伯数字或中文数量词
#   · 身份自报    —— 以「我是 / 我 / 本人 / 作为一个 / 身为 / 干了N年」起头
#   · 反常识/劝阻 —— 「别 / 先别 / 千万别 / 劝你 / 其实 / 不是…而是」
#   · 冲突悬念    —— 「结果 / 才发现 / 没想到 / 直到 / 差点」
# 判据刻意写得宽：目的是拦「大家好，今天来分享一下」这类无钩子开场，不是评优。
HOOK_PATTERNS = [
    (r"[？?]\s*$|为什么|怎么|是不是|要不要|该不该|能不能|哪(个|种)更好", "疑问式"),
    (r"\d|[一二三四五六七八九十百千万]\s*(个|种|条|步|天|周|月|年|次|遍|块|元)",
     "数字切入"),
    (r"^(我|本人|作为|身为|干了|做了|用了|住了|练了|坚持了)", "身份自报"),
    (r"^(别|先别|千万别|劝你|不要|其实|不是)|千万别|先别急着", "反常识/劝阻"),
    # 「都说…其实…」这类**先立后破**的开场也是钩子。
    # 为什么不并进上一条：上一条要求句首就是判断词，而这类开场句首是「都说/很多人说」，
    # 实测（第一次真机跑）它被漏判成「未识别出钩子」——判据过窄就会误伤正确写法。
    (r"^(都|大家|很多人|不少人|别人|所有人)(都)?说|^都说|一开始我也(信|以为)", "先立后破"),
    # 「我以为…（结果/其实/后来）」也是钩子：先立一个错的判断，读者想知道为什么错。
    # 这一条与上一条同源，但句首是「我」不是「都说」，实测被漏判过一次。
    # **不加 `^` 锚**：实测「刚碰短剧二创那半年，我以为最难的是剪辑」里
    # 「我以为」出现在句中，锚住句首就漏了 —— 判据要跟着真实写法走，不是跟着想象走。
    (r"(本以为|原以为|我以为|我还以为|以为最难|觉得最难)", "认知反转"),
    (r"结果|才发现|没想到|直到|差点|终于明白|后来才|才明白|才搞懂", "冲突悬念"),
    # 「…，我走了三段弯路」这类**身份 + 已发生的代价**也是钩子：
    # 句首没有疑问词也没有数字时，它靠"我付出了代价"制造往下读的理由。
    # 实测漏判过（「第一次做短剧二创，我走了三段弯路」被判未识别），所以要单独列一条。
    (r"我(走|踩|绕|栽|翻|花|用|熬|试)了", "代价自述"),
]
HOOK_RE = [(re.compile(p), name) for p, name in HOOK_PATTERNS]
# 明确无钩子的开场（命中即标红，这是真会掉点击的写法）
FLAT_HOOK_RE = re.compile(r"^(大家好|哈喽|hello|hi|今天(来)?(给|跟)?大家|今天来分享|"
                          r"很高兴|分享一下|记录一下|碎碎念)")


def detect_hook(line):
    """判定首行是不是钩子，返回 (是否钩子, 钩子类型) 或 (False, '无钩子开场')。

    ⚠️ 判定的单位是**首行整行**，不是首句。实测踩到的坑：模型写的
    「刚碰短剧二创那半年，我以为最难的是剪辑。后来发现，难的是我一开始就想错了方向。」
    里「我以为」出现在逗号之后，"首句"（到第一个句号）根本截不到它 ——
    取首句就会把它误判成「未识别出钩子」。首行只有一两句话，整行看更贴近真实写法。
    """
    t = (line or "").strip()
    if not t:
        return False, "首行为空"
    if FLAT_HOOK_RE.match(t):
        return False, "无钩子开场"
    for rx, name in HOOK_RE:
        if rx.search(t):
            return True, name
    return False, "未识别出钩子"


def normalize_tag(t):
    """话题标签归一化：去掉 # 与空白，保留标签内容。"""
    return re.sub(r"\s+", "", str(t or "").lstrip("#").strip())


# ===========================================================================
# 成本模型
#
# 现实情况（实测，别猜）：
#   · `POST /api/v1/chat/completions` 的成功响应**不带 `code` 字段**
#     （`code==1` 那套信封只用于生成应用的响应），也不返回 points_cost；
#     usage 里只有 prompt_tokens / completion_tokens / total_tokens。
#   · `GET /api/v1/models` 的列表里**没有任何价格字段**。
#   · `GET /api/v1/pricing` 不含文本大模型。
#   · 出图：nano_banana 1K **实测 24 点/张**（= 0.24 元），只信任务返回的 usage.points_cost。
#
# 结论：**拿不到可信的文本模型单价，本包拒绝凭空编一个。**
#   · token 数我们估（用实测标定的比例），这是确定可算的；
#   · 金额必须由你给单价：`--price-in` / `--price-out`，单位「点 / 百万 token」；
#   · 出图的钱是实测价，可以直接算。
# ===========================================================================

# 字符 → token 的标定比例（**实测值**）：输入侧极稳，输出侧按均值并在文档里给区间。
CHARS_PER_TOKEN_IN = 1.61
TOKENS_PER_CHAR_OUT = 1.11
POINTS_PER_YUAN = 100.0            # 平台口径：1 元 = 100 点
POINTS_PER_IMAGE_1K = 24           # 实测：nano_banana 1K = 24 点/张


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_tokens_out(chars):
    """估输出 token。按「假设模型写到了目标字数」算，**故意往多了估**。"""
    return max(1, int(round((chars or 0) * TOKENS_PER_CHAR_OUT)))


def compute_cost(tokens_in, tokens_out, price_in=None, price_out=None):
    """算文本的钱。单价单位：点 / 百万 token。缺单价时诚实返回 None。"""
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
            "单价（点/百万 token）即可算出点数与金额。**本包拒绝凭空编一个单价。**")
        return rec
    pts = (rec["tokens_in"] / 1e6) * float(price_in) + \
          (rec["tokens_out"] / 1e6) * float(price_out)
    rec["points"] = round(pts, 4)
    rec["yuan"] = round(pts / POINTS_PER_YUAN, 4)
    rec["notes"].append("按你给的单价线性折算；真实扣费以账户流水为准。")
    return rec


def image_cost(count, resolution=COVER_RESOLUTION, override=None):
    """出图成本。1K 有实测价；其它档没有实测价就诚实说未知。"""
    unit = float(override) if override is not None else (
        float(POINTS_PER_IMAGE_1K) if str(resolution).upper() == "1K" else None)
    rec = {"count": int(count), "resolution": resolution,
           "points_per_image": unit,
           "source": "override" if override is not None else "实测",
           "notes": []}
    if unit is None:
        rec["total_points"] = None
        rec["total_yuan"] = None
        rec["notes"].append("%s 档没有实测单价，拒绝凭猜估算：用 --points-per-image 指定" % resolution)
        return rec
    rec["total_points"] = round(unit * rec["count"], 4)
    rec["total_yuan"] = round(rec["total_points"] / POINTS_PER_YUAN, 4)
    rec["notes"].append("按实测价 24 点/张（nano_banana 1K）；真实扣费以 usage.points_cost 为准")
    return rec


def fmt_cost(rec):
    if rec.get("points") is None and rec.get("total_points") is None:
        return "无法估算金额（%s）" % "；".join(rec.get("notes") or [])
    p = rec.get("points", rec.get("total_points"))
    y = rec.get("yuan", rec.get("total_yuan"))
    return "%g 点 = ¥%g" % (p, y)


# ===========================================================================
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ===========================================================================

class NoteError(a7w.A7wError):
    """调用 / 产出失败（网络、鉴权、点数、模型名）。→ 退出码 4"""


class UsageError(NoteError):
    """参数/配置用错了（没给母稿、路径不存在、--outdir 指到包内…）。→ 退出码 2

    为什么跟 NoteError 分开：这两类错误的**处理方式完全不同**。
    参数错了要改命令重跑（不花一分钱）；调用失败要查 Key / 点数 / 模型名。
    混成一个退出码，CI 里就没法区分「我命令写错了」和「网关挂了」。
    """


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.8,
         max_tokens=8192, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见。
    一次调用是一整篇笔记，被一次抖动打断要重跑整篇，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。

    成功响应**不带 `code` 字段**（实测），所以这里不判 code，只判 choices 在不在。
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
                raise NoteError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise NoteError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise NoteError(
                    "模型不存在（404）：{}  用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 429，{}s 后重试…\n".format(3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise NoteError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise NoteError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    if payload is None:
        raise NoteError("网络错误：{}".format(last_exc))

    # 兜底：万一网关换了形态包了一层 {"code":1,"data":{...}}，两种都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise NoteError("模型没返回 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    return content, usage


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    为什么要这么写：模型经常在合法 JSON 后面多吐几个字符（```、解释、第二个对象、
    重复的 `}`），直接 json.loads 会炸。这里用 json.JSONDecoder().raw_decode()，
    从一个 `{` 或 `[` 开始试解码，成功就返回，失败就往后挪一个字符接着试。
    """
    if not text:
        raise NoteError("模型返回空内容")
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
    raise NoteError("模型返回的不是合法 JSON：{}".format(text[:300].replace("\n", " ")))


# ===========================================================================
# 闸门执行：对一篇笔记跑全部本地检查
# ===========================================================================

def compliance_scan(text, platform="xiaohongshu"):
    """扫违禁词 + 小红书特有红线。

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
        if ctx == "ordinal" and _is_ordinal_sequence(text, m):
            exempted.append({
                "word": m.group(0),
                "why": "疑似「第一」类排他性表述，但形态是「第 + 数字 + 量词」的序数"
                       "（例如「第一个坑」「第一个月」），判断为叙事里的顺序词"
                       "而不是排他性宣称——本地放过，请人工确认",
                "context": text[max(0, m.start() - 8):m.end() + 8],
            })
            continue
        hits.append({"word": m.group(0), "level": lvl, "why": why, "scope": "广告法"})
    for rx, lvl, why in PLATFORM_REDLINE_RE:
        m = rx.search(text)
        if m:
            hits.append({"word": m.group(0), "level": lvl, "why": why,
                         "scope": "小红书特有红线"})
    # 去重（同一个词可能同时命中广告法和小红书红线）
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


def spec_gate(title, body, hashtags, first_ln=None):
    """闸门四：小红书笔记规格。返回 (是否达标, 明细 dict)。

    四件事一起判，因为它们共同定义「这篇能不能直接发」：
      · 正文字数 ≤ 1000（并给下限，太短的笔记讲不清一件事）
      · 话题标签 5~8 个
      · 首行必须是钩子（缺失标红）
      · 标题长度落在 8~24 字
    """
    chars = count_chars(body)
    lo, hi = XHS["body_chars"]
    n_tags = len(hashtags or [])
    tlo, thi = XHS["hashtags"]
    line = first_ln if first_ln is not None else first_line(body)
    hook_ok, hook_kind = detect_hook(line)
    tl = count_chars(title)
    T_lo, T_hi = XHS["title_chars"]
    d = {
        "chars": chars, "char_range": [lo, hi],
        "chars_ok": lo <= chars <= hi, "chars_over_limit": chars > hi,
        "tags": n_tags, "tag_range": [tlo, thi], "tags_ok": tlo <= n_tags <= thi,
        "hook_line": line[:40], "hook_ok": hook_ok, "hook_kind": hook_kind,
        "title_chars": tl, "title_range": [T_lo, T_hi],
        "title_ok": T_lo <= tl <= T_hi,
    }
    d["ok"] = d["chars_ok"] and d["tags_ok"] and d["hook_ok"]
    return d["ok"], d


def normalize_note(raw, angle, idx=1):
    """把模型返回的一篇笔记收拾成内部结构，并跑完全部本地闸门。"""
    raw = raw or {}
    title = re.sub(r"[ \t]+", " ", str(raw.get("title") or "").strip().strip('"').strip())
    body = re.sub(r"\n{3,}", "\n\n", str(raw.get("body") or "").strip())
    cover_text = str(raw.get("cover_text") or "").strip()
    cover_desc = str(raw.get("cover_desc") or "").strip()
    tags_raw = raw.get("hashtags") or []
    if isinstance(tags_raw, str):
        tags_raw = re.split(r"[,，、\s]+", tags_raw)
    hashtags = [normalize_tag(t) for t in tags_raw if normalize_tag(t)]
    # 去重保序（模型偶尔会重复同一个标签）
    # 注意别写成 `seen_t, hashtags = set(), [... if t in seen_t ...]`：
    # 同一行的推导式会因为 seen_t 在同一语句里被赋值而变成自由变量、直接 NameError
    # —— 这个坑是实测跑出来的（第一次真机调用就崩在这），不是想出来的。
    seen_t = set()
    hashtags = [t for t in hashtags if not (t in seen_t or seen_t.add(t))]

    # 正文里如果模型自己把标签写进去了，拆出来，避免字数口径被标签污染。
    body_lines = (body or "").splitlines()
    inline_tags = []
    keep = []
    for ln in body_lines:
        stripped = ln.strip()
        if stripped and all(p.strip().startswith("#") for p in stripped.split()):
            inline_tags.extend(normalize_tag(p) for p in stripped.split() if p.strip())
            continue
        keep.append(ln)
    if inline_tags:
        body = "\n".join(keep).strip()
        for t in inline_tags:
            if t and t not in seen_t:
                seen_t.add(t)
                hashtags.append(t)

    full = "\n".join([title, body, cover_text, cover_desc])

    # 闸门一：合规（广告法 + 小红书红线）
    scan = compliance_scan(full)
    comp, comp_exempt = scan["hits"], scan["exempted"]
    # 闸门二：占位符残留
    ph = placeholder_scan(full)
    # 闸门三：照抄提示词示例（标题整条比一次；正文走整段 + 逐句两层）
    echoes = prompt_echo_scan(title, label="标题") + prompt_echo_scan(body, label="正文")
    # 闸门四：小红书笔记规格
    spec_ok, spec = spec_gate(title, body, hashtags)

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
        deductions.append({"kind": "prompt_echo", "points": 30, "why": echoes[0]["why"]})
    if not spec["chars_ok"]:
        over = spec["chars"] - XHS["body_chars"][1]
        why = ("正文 {} 字，超过小红书上限 {} 字（超 {} 字）" .format(
            spec["chars"], XHS["body_chars"][1], over) if spec["chars_over_limit"]
            else "正文 {} 字，低于下限 {} 字".format(spec["chars"], XHS["body_chars"][0]))
        deductions.append({"kind": "length", "points": 30, "why": why})
    if not spec["hook_ok"]:
        deductions.append({"kind": "hook", "points": 25,
                           "why": "首行不是钩子（{}）：「{}」".format(
                               spec["hook_kind"], spec["hook_line"][:24])})
    if not spec["tags_ok"]:
        deductions.append({"kind": "hashtags", "points": 8,
                           "why": "话题标签 {} 个，不符合 5~8 个的口径".format(spec["tags"])})
    if not spec["title_ok"]:
        deductions.append({"kind": "title", "points": 5,
                           "why": "标题 {} 字，不在 {}~{} 字".format(
                               spec["title_chars"], *XHS["title_chars"])})
    score = max(0, 100 - sum(d["points"] for d in deductions))

    return {
        "id": "n%02d" % idx,
        "angle_key": angle.get("key"),
        "angle_name": angle.get("name"),
        "angle": angle,
        "title": title,
        "body": body,
        "hashtags": hashtags,
        "cover_text": cover_text,
        "cover_desc": cover_desc,
        "stats": {
            "chars": spec["chars"],
            "char_range": spec["char_range"],
            "paras": len(split_paras(body)),
            "tags": spec["tags"],
            "tag_range": spec["tag_range"],
            "hook_line": spec["hook_line"],
            "hook_kind": spec["hook_kind"],
            "title_chars": spec["title_chars"],
        },
        "gates": {
            "compliance": {"ok": not comp, "hits": comp, "exempted": comp_exempt},
            "placeholder": {"ok": not ph, "hits": ph},
            "prompt_echo": {"ok": not echoes, "hits": echoes},
            "spec": spec,
        },
        "score": score,
        "deductions": deductions,
    }


def note_gate_failed(it):
    """这一篇是否被硬闸门拦下（决定退出码）。

    口径：合规 / 占位符 / 照抄示例 / 笔记规格（字数上限 + 标签数 + 首行钩子）
    —— 四项任一不达标即拦截。
    标题长度、标签数偏少这类只扣分不拦截的，是风格问题，不是「发出去会出事」的问题，
    但一样会标红显示。
    """
    g = it["gates"]
    return (not g["compliance"]["ok"] or not g["placeholder"]["ok"]
            or not g["prompt_echo"]["ok"] or not g["spec"]["ok"])


# ===========================================================================
# 提示词
#
# 【铁律】提示词里**不许出现任何一句可直接复制的完整中文句子**作为示例。
# 事故复盘见上文「闸门三」。举例只用描述性语言 ——
# 这一点在本包里比在改写包里更关键：批量出 N 篇时，模型会优先抄它看到的那一句，
# 抄出来的还是同一句，N 篇的"角度分开"直接归零。
# ===========================================================================

SYSTEM_PROMPT = (
    "你是三剪客团队的小红书笔记编辑，一天要出很多篇不同角度的笔记。\n"
    "你只输出 JSON，不输出任何解释、前后缀或 Markdown 围栏。\n"
    "你写的每一篇都必须能被真实发布：\n"
    "  · 不编造母稿里没有的数据、案例、背书、检测结论\n"
    "  · 不使用广告法违禁词（最X / 第一 / 国家级 / 100% / 根治 / 绝对 / 保证 一律不许出现）\n"
    "  · 不使用小红书特有的功效宣称（美白 / 祛斑 / 祛痘 / 排毒 / 养胃 / 助眠 / 消炎 等）\n"
    "  · 不留任何占位符（不许出现 大括号、待填、XXX、此处省略 这类编稿脚手架）\n"
    "  · 不出现站外联系方式（微信 / 手机号 / 私信我 / 加V）\n"
    "  · 同一批不同篇之间，开场句、结构、用词都不许雷同 —— 换皮等于没写"
)


def _angle_block(angle):
    """把一个角度渲染成提示词片段。**改角度只改 ANGLES 表。**"""
    return (
        "本篇的切入角度（**只能用这一个**）：\n"
        "  · 角度名：{name}\n"
        "  · 写的人是谁：{persona}\n"
        "  · 具体场景：{scene}\n"
        "  · 情绪基调：{emotion}\n"
        "  · 这一篇要怎么落笔：{focus}".format(**angle)
    )


def build_note_prompt(source, angle, others=None, evidence=None, brief=None):
    """一篇笔记的提示词。

    `others` 是**同批其它角度的名字**：明确告诉模型"别写这些"，
    这是 N 篇不换皮的第一道防线（第二道是本地 cross_note 闸门）。
    注意这里只给**角度名**，不给其它篇的正文 —— 给了正文，模型就会照着那篇改。
    """
    lo, hi = XHS["body_chars"]
    tlo, thi = XHS["hashtags"]
    tlo_t, thi_t = XHS["title_chars"]
    parts = [
        "把下面这份材料改写成**一篇小红书笔记**。",
        "",
        "=== 材料（这一篇的真实信息来源）===",
        source.strip(),
        "",
        "=== 本篇角度 ===",
        _angle_block(angle),
    ]
    if others:
        parts += ["",
                  "=== 同批其它篇已经占掉的角度（**本篇一律不许写这些角度**）===",
                  "、".join(others)]
    parts += [
        "",
        "=== 硬性规格（逐条都要满足）===",
        "1. 正文 {}~{} 字（**绝不能超过 {} 字**；这是平台上限）。".format(lo, hi, hi),
        "2. 开头那一行必须是钩子：一个问题、一个具体数字、一个身份自报、或一句反常识判断。",
        "   不许以寒暄或「今天来分享一下」这类开场起头。",
        "3. 每段 1~3 行，段与段之间空一行；全篇 {}~{} 段。".format(*XHS["para_count"]),
        "4. 话题标签**恰好 {}~{} 个**，写在 hashtags 字段里（不要写进 body）。".format(tlo, thi),
        "5. 标题 {}~{} 字，口语，像朋友在说话。".format(tlo_t, thi_t),
        "6. 封面：给一句**大字标题**（cover_text，12~18 字，能被一眼读完）"
        "和一句画面描述（cover_desc，30~60 字，描述场景与主体，不要写违禁词）。",
        "",
        "=== 内容要求 ===",
        "· 只写这一个角度，写具体：写清「当时怎么想 → 做了什么 → 结果怎样」。",
        "· 材料里没有的数字、品牌、检测结论、他人评价，一律不许编。",
        "· 不要把材料整段搬运过来，要按这个角度重排信息的出场顺序。",
        "· 材料里没有的事实，宁可写主观感受（例如「我用下来觉得」），也不要写成客观结论。",
    ]
    if evidence:
        parts += ["", "=== 可以使用的真实素材（只有这些能用）===", str(evidence).strip()]
    if brief:
        parts += ["", "=== 作者的要求 ===", str(brief).strip()]
    parts += [
        "",
        "=== 输出（只输出这个 JSON 对象）===",
        '{"title": "...", "body": "...", "hashtags": ["标签1", "标签2", ...],',
        ' "cover_text": "...", "cover_desc": "..."}',
        "hashtags 里每一项不要带 # 号（带了也会被去掉）。",
    ]
    return "\n".join(parts)


def build_angles_prompt(source, count, existing=None):
    """让模型针对这份材料出 N 个**互不重复**的切入角度（一次调用，可不用）。"""
    parts = [
        "读下面这份材料，给出 {} 个**互不重复**的小红书笔记切入角度。".format(count),
        "",
        "=== 材料 ===",
        source.strip(),
        "",
        "=== 要求 ===",
        "· 角度之间必须真的不一样：人群、场景、情绪、落点四个维度上至少有两个不同。"
        "「新手踩坑」和「老手复盘」不是一回事；「算账」和「清单」也不是一回事。",
        "· 每个角度要能直接指导一篇笔记怎么写，不要写成营销词。",
        "· 不要引用材料里的原句。",
    ]
    if existing:
        parts += ["", "=== 已经用过的角度（不要再出）===", "、".join(existing)]
    parts += [
        "",
        "=== 输出（只输出这个 JSON 对象）===",
        '{"angles": [{"key": "英文短标识", "name": "中文角度名", "persona": "写的人是谁",',
        '  "scene": "具体场景", "emotion": "情绪基调", "focus": "这一篇怎么落笔"}]}',
    ]
    return "\n".join(parts)


def cover_text_of(note):
    """这条笔记**实际送进提示词**的封面大字标题（含兜底来源，一字不截）。

    `cover_text` 缺省时按 `title` 兜底 —— 这是 `build_cover_prompt()` 与
    `_cover_copy_text()` 共同的口径。闸门、key、提示词三处都调它，
    口径只有一份，就不会出现「闸门判的字数不是真正送出去的字数」。
    """
    return note.get("cover_text") or note.get("title") or ""


def build_cover_prompt(note):
    """封面出图提示词。3:4，含大字标题。

    ⚠️ 这里**不再静默截断**文案。旧版（1.0.4 及以前）是
    `(note.get("cover_text") or ...)[:20]`：超长时只改第 21 字之后，
    断点 key（取完整文案的摘要）变了 → 重新出图、重新扣费，
    而送去的提示词**逐字相同** → 出的图一模一样。
    用户付了钱、什么也没变。现在超长由 `COVER_TEXT_MAX` 闸门在提交前拦下
    （见 `_run_covers()`），到得了这里就说明长度已经合规。
    """
    return (
        "为一条小红书笔记做封面图，竖版 3:4。\n"
        "画面主体：{desc}\n"
        "封面上要有一行大号中文标题（醒目、粗体、可读）：\n"
        "「{text}」\n"
        "风格：干净的新媒体封面，背景简洁不杂乱，主体清晰，光线柔和，留出文字区域，"
        "文字不要压在主体上，不要水印，不要二维码，不要站外联系方式。\n"
        "不要在图中出现广告法违禁词、医疗功效词或任何促销倒计时文案。"
        .format(desc=(note.get("cover_desc") or note.get("angle_name") or "笔记封面场景"),
                text=cover_text_of(note))
    )


def _cover_copy_text(note):
    """一条笔记的**完整**封面文案：大字标题 + 画面描述，一个字都不截。

    两段各自归一化后再拼接（用换行做分隔），避免「两段之间挪一个字」被归一化抹平。
    `angle_name` / `title` 是 `cover_text` / `cover_desc` 缺省时的兜底来源，
    与 `build_cover_prompt()` 里的取值口径一致 —— 口径不一致就会出现
    「提示词变了但 key 没变」的假命中。
    """
    text = cover_text_of(note)
    desc = note.get("cover_desc") or note.get("angle_name") or ""
    return "\n".join([_norm_for_echo(text), _norm_for_echo(desc)])


def cover_state_key(item, resolution=COVER_RESOLUTION):
    """封面出图的断点 key：`<笔记 id>-<比例>-<分辨率>-<封面文案摘要>`。

    ⚠️ 这里**必须对完整的封面文案取摘要**，绝不能只截前 N 个字。
    旧版（1.0.3）的写法是 `"%s-%s" % (it["id"], COVER_RATIO.replace(":", "x"))`：
    key 里**完全没有封面文案**，于是用户改了 `cover_text` / `cover_desc` 再重跑，
    key 不变 → 断点命中 → **静默复用旧封面图**，连一句提示都没有。
    这是「静默复用过期产物」：多扣一次费用户立刻会发现，复用旧图不会。

    ⚠️ 这里**必须把 `resolution` 算进 key**（1.0.5 补的第 4 维）。
    1.0.4 的 key 只有「id + 比例 + 文案摘要」，用户先跑 1K 出了图、
    再改成 `--resolution 4K` 重跑 → key 不变 → 断点命中 →
    **复用 1K 的图，用户以为自己拿到了 4K**。同样是静默复用过期产物，
    而且这次连文案都没变，任何基于文案的兜底都发现不了。
    `resolution` 直接进 key（纯文本，不必哈希）：取值只有 1K/2K/4K 三个，
    长度可控，且比摘要更好读。

    摘要取 16 位十六进制（64 bit）：key 长度可控、可读，碰撞概率对本场景可忽略。
    归一化沿用本包已有的 `_norm_for_echo()`（只留中文/字母/数字），所以
    **只改标点或空白不算改动**（不该白扣一次费），改一个字就必变。
    key 里**按笔记 id 分**：改了文案只会重出那一条笔记的封面，不会整批重扣。
    「笔记 id」与「比例」两维都保留 —— 比例变了也必须重出，不能丢。
    """
    digest = hashlib.sha1(_cover_copy_text(item).encode("utf-8")).hexdigest()
    return "%s-%s-%s-%s" % (item["id"], COVER_RATIO.replace(":", "x"),
                            resolution, digest[:16])


# ===========================================================================
# 出图（nano_banana）—— 与配图工厂同口径
#
# 平台文档写的是 `data.result.status`，**实测不对**：status 在 `data` 顶层。
# 照文档写会永远读不到状态、一路轮询到超时，所以这里按实测结构取。
# ===========================================================================

ASPECT_RATIOS = ("auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
                 "5:4", "4:5", "21:9")
RESOLUTIONS = ("1K", "2K", "4K")
IMAGE_MODELS = ("nano-banana", "nano-banana-2", "nano-banana-2-lite")


def submit_image(prompt, aspect_ratio=COVER_RATIO, resolution=COVER_RESOLUTION,
                 model="nano-banana", action="generate", image_urls=None,
                 key=None, timeout=180):
    """提交一个出图任务，返回网关 data（含 task_id 与预冻结点数）。

    请求体字段用 `python a7w.py schema nano_banana` 实查过，不要凭记忆加字段：
        prompt / action / model / image_urls / resolution / aspect_ratio / callback_url
    """
    if aspect_ratio not in ASPECT_RATIOS:
        raise UsageError("aspect_ratio 只能是 {}，收到 {!r}".format(
            " / ".join(ASPECT_RATIOS), aspect_ratio))
    if resolution not in RESOLUTIONS:
        raise UsageError("resolution 只能是 {}，收到 {!r}".format(
            " / ".join(RESOLUTIONS), resolution))
    if action == "edit" and not image_urls:
        raise UsageError("action=edit 时必须提供 image_urls")
    body = {"prompt": prompt, "action": action, "model": model,
            "resolution": resolution, "aspect_ratio": aspect_ratio}
    if image_urls:
        body["image_urls"] = list(image_urls)
    return a7w._unwrap(a7w._request("POST", SUBMIT_URL, a7w.load_key(key),
                                    body=body, timeout=timeout))


def task_state(task_id, key=None):
    """查一次任务，返回 (状态, 归一化 data, 原始信封)。"""
    payload = a7w._request("GET", TASK_URL.format(task_id), a7w.load_key(key))
    data = a7w._unwrap(payload) or {}
    return data.get("status"), data, payload


def poll_task(task_id, key=None, timeout=POLL_TIMEOUT, interval=POLL_INTERVAL,
              on_tick=None):
    """轮询任务到终态。**必须有超时上限**：出图会卡在 processing，无限等会把批处理挂死。"""
    deadline = time.time() + timeout
    ticks = 0
    last = None
    while True:
        time.sleep(interval)
        ticks += 1
        status, data, payload = task_state(task_id, key)
        if status != last and on_tick:
            on_tick(status, data)
        last = status
        if status in a7w.TERMINAL:
            return status, data, payload, ticks
        if time.time() >= deadline:
            return "timeout", data, payload, ticks


def points_cost(data):
    """从任务返回里取**实际扣费**。

    ⚠️ 只信 usage.points_cost。提交响应里的 frozen_points 只是**预冻结**
    （实测 31.2），失败全额退回，不是最终扣费。
    """
    usage = (data or {}).get("usage") or {}
    for k in ("points_cost", "actual_points"):
        v = usage.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    res = (data or {}).get("result") or {}
    v = res.get("actual_points")
    return float(v) if isinstance(v, (int, float)) else None


def find_image_urls(data):
    """把任务结果里所有图片地址挖出来（结构会有差异，做深度搜索）。"""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("image_url", "url", "output_url") and isinstance(v, str) \
                        and v.startswith("http"):
                    if v not in found:
                        found.append(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk((data or {}).get("result"))
    return found


# ===========================================================================
# 闸门六：出图比例真伪（读真实像素，不信自报值）
#
# 事故来源：标题工坊上一版只信模型自报的 `formula` 字段做模板污染判定，
# 结果那个真该被判命的标题恰好漏判 —— 闸门是**假绿**的。
# 同一个错误在出图场景的形态是：接口自报 aspect_ratio=3:4，真实像素却是 1:1。
#
# ⚠️ 实测到的上游特性（必须写进文档，否则闸门天天误报）：
#   上游不是按比例给像素，而是先定总像素、再把每边向下取整到 32 的倍数。
#   所以 **请求 3:4 → 实测 864x1184 = 0.7297（3:4 = 0.75），偏差 2.70%**。
#   这不是网关 bug，是扩散模型按 32 对齐的常规做法。
#
# 处理方式（三条一起用，缺一条闸门就会变成天天误报的噪音）：
#   a) 默认容差 3%：容差内不算「假」，但会**明确打印真实像素与偏差**，不藏
#   b) 超过容差 → 标红 + 计入闸门失败 + 退出码 3
#   c) `--snap`：出图后按请求比例精确裁掉多余像素（3:4 → 864x1152），
#      裁剪结果再次读文件头复核，裁成功才记 exact
# ===========================================================================

RATIO_TOLERANCE = 0.03
# 容差地板：像素只能是整数，"裁到精确比例"本身就有量化误差（实测 3:4 → 864x1152 偏差 0%）。
RATIO_TOLERANCE_FLOOR = 0.0025

parse_ratio = imgprobe.parse_ratio
ratio_label = imgprobe.ratio_label


def check_ratio(path, want_ratio, tolerance=None):
    """闸门六：读真实像素，判是否等于请求比例。返回 dict（`ok` 为闸门结论）。"""
    tol = RATIO_TOLERANCE if tolerance is None else float(tolerance)
    clamped = max(tol, RATIO_TOLERANCE_FLOOR)
    rec_floor = clamped > tol
    tol = clamped
    # ⚠️ 这里**只认文件头里的宽高**，不采信任何接口返回的自报字段。
    w, h, fmt = imgprobe.image_size(path)
    rec = {"file": str(path), "format": fmt, "real_px": [w, h],
           "want_ratio": want_ratio, "tolerance": tol,
           "tolerance_floor_applied": rec_floor,
           "real_label": ratio_label(w, h), "ok": False, "deviation": None}
    if not w or not h:
        rec["why"] = "读不出真实像素（可能不是图片、或被截断下载）"
        return rec
    want = parse_ratio(want_ratio)
    real = w / float(h)
    rec["real_ratio"] = round(real, 4)
    if not want:
        rec["why"] = "请求比例 %r 无法解析" % (want_ratio,)
        rec["deviation"] = abs(real - 1.0)
        return rec
    dev = abs(real - want) / want
    rec["deviation"] = round(dev, 5)
    rec["ok"] = dev <= tol
    if not rec["ok"]:
        rec["why"] = ("真实像素 %dx%d（%s = %.4f）与请求比例 %s（%.4f）偏差 %.2f%%，"
                      "超过容差 %.2f%%——上游没有按请求比例出图"
                      % (w, h, rec["real_label"], real, want_ratio, want,
                         dev * 100, tol * 100))
    else:
        rec["why"] = ("真实像素 %dx%d（%s = %.4f），与请求比例 %s 偏差 %.2f%%，在容差 %.2f%% 内"
                      % (w, h, rec["real_label"], real, want_ratio, dev * 100, tol * 100))
    return rec


def _png_chunks(blob):
    pos = 8
    while pos + 8 <= len(blob):
        ln = struct.unpack(">I", blob[pos:pos + 4])[0]
        typ = blob[pos + 4:pos + 8]
        data = blob[pos + 8:pos + 8 + ln]
        yield typ, data
        pos += 12 + ln


def _unfilter(raw, stride, height, bpp):
    """还原 PNG 扫描线（只支持 bpp ∈ {3,4} 的 8 位真彩/真彩+alpha）。"""
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def _png_write(dst, w, h, bpp, rows):
    ctype = 6 if bpp == 4 else 2

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    blob = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))
    Path(dst).write_bytes(blob)


def _try_pil_crop(src, dst, want_ratio):
    try:
        from PIL import Image  # noqa
    except ImportError:
        return None
    try:
        im = Image.open(src)
        w, h = im.size
        want = parse_ratio(want_ratio)
        if w / float(h) > want:
            nw, nh = max(1, int(round(h * want))), h
        else:
            nw, nh = w, max(1, int(round(w / want)))
        left, top = (w - nw) // 2, (h - nh) // 2
        im.crop((left, top, left + nw, top + nh)).save(dst)
        return "pil", (left, top, nw, nh)
    except Exception:
        return None


def _try_stdlib_png_crop(src, dst, want_ratio):
    """内置 8 位 PNG 裁剪（仅支持 color_type 2/6）。没有 PIL 时的回落路径。"""
    try:
        blob = Path(src).read_bytes()
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        idat, idepth, ctype = bytearray(), None, None
        w = h = 0
        for typ, data in _png_chunks(blob):
            if typ == b"IHDR":
                w, h, idepth, ctype = struct.unpack(">IIBB", data[:10])
            elif typ == b"IDAT":
                idat.extend(data)
            elif typ == b"IEND":
                break
        if idepth != 8 or ctype not in (2, 6):
            return None
        bpp = 3 if ctype == 2 else 4
        stride = w * bpp
        pixels = _unfilter(zlib.decompress(bytes(idat)), stride, h, bpp)
        want = parse_ratio(want_ratio)
        if w / float(h) > want:
            nw, nh = max(1, int(round(h * want))), h
        else:
            nw, nh = w, max(1, int(round(w / want)))
        left, top = (w - nw) // 2, (h - nh) // 2
        rows = []
        for y in range(top, top + nh):
            off = y * stride + left * bpp
            rows.append(pixels[off:off + nw * bpp])
        _png_write(dst, nw, nh, bpp, rows)
        return "stdlib-png", (left, top, nw, nh)
    except Exception:
        return None


def snap_to_ratio(src, dst, want_ratio):
    """把图片按请求比例居中裁剪到 dst。返回 (方式, 裁剪框) 或 None。"""
    for fn in (_try_pil_crop, _try_stdlib_png_crop):
        got = fn(src, dst, want_ratio)
        if got:
            return got
    return None


# ===========================================================================
# 输出目录保护 / 断点文件
#
# 【红线】包内不许有任何图片（上传白名单只收文本）。
# 所以 --outdir 指到 Skill 包内 = 参数错误，退出码 2，**在花钱之前**就拦下。
# ===========================================================================

PKG_DIR = Path(__file__).resolve().parent.parent


def check_outdir(raw):
    """把 --outdir 解析成绝对路径，并拒绝包内路径（exit=2）。"""
    outdir = Path(raw).expanduser().resolve()
    try:
        outdir.relative_to(PKG_DIR)
    except ValueError:
        return outdir
    raise UsageError(
        "输出目录 {} 在 Skill 包内。包内不许有任何图片（上传白名单只收文本），"
        "请换到包外，例如 {}".format(
            outdir, Path(os.environ.get("TEMP") or ".") / "xhs-note-factory"))


def default_outdir():
    return Path(os.environ.get("TEMP") or ".") / "xhs-note-factory"


def load_json_file(p, what="结果文件"):
    p = Path(p)
    if not p.is_file():
        raise UsageError("找不到{}：{}".format(what, p))
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        raise UsageError("{}读不动或不是合法 JSON：{}（{}）".format(what, p, exc))


def load_state(path):
    """读断点文件。文件坏了不当错误 —— 直接当空的，重跑一遍比崩掉好。"""
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(obj, dict) and isinstance(obj.get("stages"), dict):
            return obj
    except (OSError, ValueError):
        pass
    return {"stages": {}, "items": {}}


def save_state(path, state):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _strip_bom(s):
    """去掉 UTF-8 BOM。

    Windows 上 `Out-File -Encoding utf8` / 记事本另存为 UTF-8 都会写 BOM（\\ufeff），
    带着它母稿的第一个字会被读成不可见字符，字数统计与相似度都会偏。
    """
    return s.lstrip("\ufeff") if s else s


def read_source(a):
    """读母稿：--file 或 --text，两者都给时以 --text 为准。"""
    if getattr(a, "text", None):
        return _strip_bom(a.text)
    if getattr(a, "file", None):
        p = Path(a.file)
        if not p.is_file():
            raise UsageError("找不到母稿文件：{}".format(p))
        return _strip_bom(p.read_text(encoding="utf-8", errors="replace"))
    raise UsageError("请给母稿：--file 母稿.md 或 --text \"产品/主题信息\"")


def sum_usage(usages):
    tot = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    for u in usages:
        if not u:
            continue
        tot["calls"] += 1
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if isinstance(u.get(k), int):
                tot[k] += u[k]
    return tot


def pick_angles(count, source, strategy="local", model=DEFAULT_MODEL, key=None,
                existing=None):
    """选出 N 个切入角度。

    `local`（默认）：从 ANGLES 表里按顺序取，**零成本、可复现、结果稳定**。
    `llm`：一次调用让模型针对这份材料出更贴题的角度，失败或条数不够时**自动回落到本地库**
          —— 不因为一次角度生成失败就让整条流水线挂掉。
    """
    if strategy == "llm":
        try:
            content, usage = chat(build_angles_prompt(source, count, existing),
                                  SYSTEM_PROMPT, model=model, temperature=0.9,
                                  key=key, json_mode=True)
            obj = parse_first_json(content)
            got = (obj or {}).get("angles") if isinstance(obj, dict) else obj
            out = []
            for i, it in enumerate(got or []):
                if not isinstance(it, dict):
                    continue
                out.append({
                    "key": str(it.get("key") or "llm-%02d" % (i + 1)),
                    "name": str(it.get("name") or "角度%d" % (i + 1)),
                    "persona": str(it.get("persona") or ""),
                    "scene": str(it.get("scene") or ""),
                    "emotion": str(it.get("emotion") or ""),
                    "focus": str(it.get("focus") or ""),
                    "source": "llm",
                })
            # 去重（按 name）并补齐到 count：不够的从本地库补，不让流水线停在这
            seen, uniq = set(), []
            for it in out:
                if it["name"] in seen:
                    continue
                seen.add(it["name"])
                uniq.append(it)
            if uniq:
                for it in ANGLES:
                    if len(uniq) >= count:
                        break
                    if it["name"] in seen or (existing and it["name"] in existing):
                        continue
                    seen.add(it["name"])
                    uniq.append(dict(it, source="local-fallback"))
                return uniq[:count], usage
            sys.stderr.write("角度生成没拿到可用条目，回落到本地角度库。\n")
        except (NoteError, ValueError) as exc:
            sys.stderr.write("角度生成失败（{}），回落到本地角度库（不影响后面出笔记）。\n".format(exc))
    out = []
    for it in ANGLES:
        if existing and it["name"] in existing:
            continue
        out.append(dict(it, source="local"))
        if len(out) >= count:
            break
    if not out:
        raise UsageError("本地角度库已经被用完了（--count 太大），换 --strategy llm 或减小 --count")
    return out, None


# ===========================================================================
# 文本渲染（人读输出）
# ===========================================================================

def _red(s, force_plain=False):
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return s
    return "\033[31m" + s + "\033[0m"


def render_angles_md(angles, source, strategy):
    lines = ["# 切入角度（{} 个，来源：{}）".format(len(angles), strategy), ""]
    lines.append("母稿：{} 字".format(count_chars(source)))
    lines.append("")
    lines.append("| # | 角度 | 写的人是谁 | 场景 | 情绪 | 落笔方式 |")
    lines.append("|---|---|---|---|---|---|")
    for i, a in enumerate(angles, 1):
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            i, a.get("name"), a.get("persona"), a.get("scene"),
            a.get("emotion"), (a.get("focus") or "")[:34]))
    lines.append("")
    lines.append("这些角度是**数据**（`scripts/run.py` 里的 `ANGLES` 表），不是提示词散文。")
    lines.append("`notes` 会一个角度一次调用，并把其它角度的名字写进提示词禁止重复。")
    return "\n".join(lines)


def render_notes_md(result):
    lines = ["# 小红书笔记（{} 篇）".format(len(result["notes"])), ""]
    for it in result["notes"]:
        g = it["gates"]
        flag = " ✗" if note_gate_failed(it) else ""
        lines.append("## {} {}（{}）{}".format(it["id"], it["title"],
                                              it["angle_name"], flag))
        lines.append("")
        lines.append("> 角度：{} · 正文 {} 字 · 标签 {} 个 · 首行钩子：{}（{}）"
                     .format(it["angle_name"], it["stats"]["chars"],
                             it["stats"]["tags"], it["stats"]["hook_kind"],
                             it["stats"]["hook_line"][:20]))
        lines.append("")
        lines.append(it["body"])
        lines.append("")
        lines.append(" ".join("#" + t for t in it["hashtags"]))
        lines.append("")
        if it.get("cover_text") or it.get("cover_desc"):
            lines.append("封面大字：{}".format(it.get("cover_text") or "-"))
            lines.append("")
            lines.append("封面画面：{}".format(it.get("cover_desc") or "-"))
            lines.append("")
        for d in it["deductions"]:
            lines.append(_red("  ✗ [{}] 扣 {} 分：{}".format(d["kind"], d["points"], d["why"])))
        if it["deductions"]:
            lines.append("")
        for e in g["compliance"].get("exempted") or []:
            lines.append("  · 本地放过 1 处疑似绝对化用语「{}」：…{}…（请人工确认）"
                         .format(e["word"], e["context"]))
    cp = result.get("cross_notes") or {}
    lines.append("## 跨篇相似度（阈值 {}）".format(cp.get("threshold")))
    lines.append("")
    if not cp.get("pairs"):
        lines.append("（没有两篇同时 ≥ {} 字，无法两两比较）".format(cp.get("min_chars")))
    else:
        for p in cp["pairs"][:10]:
            mark = " ⚠️ 疑似换皮" if p["flagged"] else ""
            lines.append("- {} ↔ {}：{}{}".format(p["a_name"], p["b_name"], p["sim"], mark))
    lines.append("")
    return "\n".join(lines)


def render_covers_md(summary):
    lines = ["# 封面（小红书 3:4）", ""]
    lines.append("请求比例：{} · 分辨率：{} · 容差：{:.1%}"
                 .format(summary["want_ratio"], summary["resolution"],
                         summary["tolerance"]))
    lines.append("")
    for c in summary["completed"]:
        lines.append("- {} ← {}：真实像素 {}x{}（{} = {}），偏差 {:.2%}，扣费 {} 点"
                     .format(Path(c["file"]).name if c.get("file") else "-",
                             c.get("title") or c.get("id"),
                             c["real_px"][0], c["real_px"][1], c.get("real_label"),
                             c.get("real_ratio"),
                             (c.get("deviation") or 0), c.get("points_cost")))
    for c in summary.get("ratio_failed") or []:
        lines.append(_red("- ✗ {}：{}".format(c.get("id"), c.get("why"))))
    for f in summary.get("failed") or []:
        lines.append(_red("- ✗ {} {} 失败：{}".format(f.get("id"), f.get("stage"),
                                                     f.get("error"))))
    lines.append("")
    lines.append("本次真花钱：{} 点 = ¥{}".format(summary["points_cost_this_run"],
                                                summary["yuan_this_run"]))
    return "\n".join(lines)


# ===========================================================================
# 子命令
# ===========================================================================

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


def _gate_report(notes, cross=None):
    """把命中汇总到 stderr，并返回退出码。"""
    rc = EXIT_OK
    hit = [it for it in notes if note_gate_failed(it)]
    if hit:
        rc = EXIT_GATE
        sys.stderr.write("\n!! 有 {} 篇被硬闸门拦下，不可直接发布：\n".format(len(hit)))
        for it in hit:
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
            sp = g["spec"]
            if not sp["chars_ok"]:
                reasons.append("正文 {} 字，不在 {}~{} 区间".format(
                    sp["chars"], sp["char_range"][0], sp["char_range"][1]))
            if not sp["tags_ok"]:
                reasons.append("话题标签 {} 个，不符合 {}~{} 个".format(
                    sp["tags"], sp["tag_range"][0], sp["tag_range"][1]))
            if not sp["hook_ok"]:
                reasons.append("首行不是钩子（{}）：「{}」".format(
                    sp["hook_kind"], sp["hook_line"][:20]))
            sys.stderr.write("   [{}] {} {} ← {}\n".format(
                it["id"], it["angle_name"], it["title"][:26], "；".join(reasons)))
    # 只扣分不拦截的项目也报一声，但不动退出码
    soft = [(it["id"], d) for it in notes for d in it["deductions"]
            if d["kind"] in ("hashtags", "title")]
    if soft:
        sys.stderr.write("\n提示：{} 项风格扣分（不拦截，但建议改）：\n".format(len(soft)))
        for nid, d in soft:
            sys.stderr.write("   [{}] 扣 {} 分：{}\n".format(nid, d["points"], d["why"]))
    if cross and cross.get("flagged"):
        rc = EXIT_GATE
        sys.stderr.write("\n!! 跨篇换皮：{} 对笔记正文相似度 ≥ {}，"
                         "等于同一篇换了个开场：\n".format(
                             len(cross["flagged"]), cross["threshold"]))
        for p in cross["flagged"]:
            sys.stderr.write("   {} ↔ {}：{}\n".format(p["a_name"], p["b_name"], p["sim"]))
    # 被豁免的疑似命中也要说一声，**不静默放过**
    ex = [(it["id"], e) for it in notes
          for e in (it["gates"]["compliance"].get("exempted") or [])]
    if ex:
        sys.stderr.write("\n提示：本地放过 {} 处疑似绝对化用语（判定为「在说数据极值」"
                         "而不是商品宣称）。这是启发式判断，请人工确认：\n".format(len(ex)))
        for nid, e in ex:
            sys.stderr.write("   [{}]「{}」：…{}…\n".format(nid, e["word"], e["context"]))
    return rc


# ---------------------------------------------------------------------------
# angles —— 出 N 个切入角度（默认零成本）
# ---------------------------------------------------------------------------

def _run_angles(a):
    source = read_source(a)
    angles, usage = pick_angles(a.count, source, a.strategy, model=a.model, key=a.key)
    result = {
        "strategy": a.strategy,
        "chat_endpoint": CHAT_URL if a.strategy == "llm" else None,
        "note": "角度是数据（run.py 的 ANGLES 表）。local = 零成本可复现；llm = 一次调用。"
                "**换皮检测看的是正文，不看角度名字**，所以 notes 阶段还会再量一次。",
        "source_chars": count_chars(source),
        "count": len(angles),
        "angles": angles,
        "usage": usage,
    }
    _emit(a, result, render_angles_md(angles, source, a.strategy))
    return EXIT_OK


# ---------------------------------------------------------------------------
# notes —— 按角度逐篇写正文 + 标签（一个角度一次调用）
# ---------------------------------------------------------------------------

def _notes_from_raw(raw_notes):
    """把落盘的 notes 列表恢复成可跑闸门的内部结构（check 用）。"""
    out = []
    for i, it in enumerate(raw_notes or [], 1):
        angle = it.get("angle") or {"key": it.get("angle_key"), "name": it.get("angle_name")}
        out.append(normalize_note({
            "title": it.get("title"), "body": it.get("body"),
            "hashtags": it.get("hashtags"), "cover_text": it.get("cover_text"),
            "cover_desc": it.get("cover_desc"),
        }, angle, idx=i))
    return out


def check_notes(notes):
    """对一批笔记跑闸门，返回 (是否硬闸门全绿, 退出码, 跨篇结果)。"""
    cross = cross_note_check({it["id"]: it for it in notes})
    rc = _gate_report(notes, cross)
    return rc == EXIT_OK, rc, cross


def _run_notes(a):
    source = read_source(a)
    price_in, price_out = a.price_in, a.price_out
    if a.budget is not None and (price_in is None or price_out is None):
        sys.stderr.write(
            "配置错误：给了 --budget 就必须给单价，否则预算没有任何意义。\n"
            "  接口的 pricing 表实测不含文本大模型、models 列表也没有价格字段，\n"
            "  所以本包拒绝凭空编一个单价。请补 --price-in / --price-out"
            "（单位：点/百万 token）。\n")
        return _fail(EXIT_USAGE, "usage", "给了 --budget 就必须给单价（本包拒绝编造单价）")

    angles, angles_usage = pick_angles(a.count, source, a.strategy,
                                       model=a.model, key=a.key)
    outdir = check_outdir(a.outdir) if a.outdir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)

    # 预估闸门：先算一遍，开局就知道会不会超预算
    prompts = [build_note_prompt(source, ang, [o["name"] for o in angles if o is not ang],
                                a.evidence, a.brief) for ang in angles]
    est_in = sum(estimate_tokens_in(SYSTEM_PROMPT + p) for p in prompts)
    est_out = len(angles) * estimate_tokens_out(XHS["body_chars"][0])
    est = compute_cost(est_in, est_out, price_in, price_out)
    if a.budget is not None:
        sys.stderr.write("预估：{}（{} 篇）\n".format(fmt_cost(est), len(angles)))
        if est["points"] is not None and est["points"] > a.budget:
            sys.stderr.write("!! 预估成本 {} 点已超过 --budget {} 点，就地中止（还没花钱）。\n"
                             "   想继续就跑少几篇，或调低 --max-tokens。\n".format(
                                 est["points"], a.budget))
            return _fail(EXIT_BUDGET, "budget",
                         "预估成本 %s 点已超过 --budget %s 点，就地中止（还没花钱）"
                         % (est["points"], a.budget))

    notes, usages = [], []
    if angles_usage:
        usages.append(angles_usage)
    spent_in = int((angles_usage or {}).get("prompt_tokens") or 0)
    spent_out = int((angles_usage or {}).get("completion_tokens") or 0)
    t_all = time.time()
    for idx, ang in enumerate(angles, 1):
        others = [o["name"] for o in angles if o["key"] != ang["key"]]
        prompt = build_note_prompt(source, ang, others, a.evidence, a.brief)
        if a.dry_run:
            if a.json:
                continue
            print("=== [{}] system ===\n{}\n\n=== [{}] user ===\n{}".format(
                ang["name"], SYSTEM_PROMPT, ang["name"], prompt))
            continue
        sys.stderr.write("[{}/{}] 正在写「{}」（目标 {}~{} 字）…\n".format(
            idx, len(angles), ang["name"], *XHS["body_chars"]))
        t0 = time.time()
        content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                              temperature=a.temperature, max_tokens=a.max_tokens,
                              key=a.key, json_mode=not a.no_json_mode)
        elapsed = time.time() - t0
        obj = parse_first_json(content)
        if not isinstance(obj, dict):
            raise NoteError("「{}」的返回不是 JSON 对象".format(ang["name"]))
        it = normalize_note(obj, ang, idx=idx)
        it["usage"] = usage
        it["elapsed"] = round(elapsed, 1)
        it["gate_failed"] = note_gate_failed(it)
        notes.append(it)
        usages.append(usage)
        spent_in += int(usage.get("prompt_tokens") or 0)
        spent_out += int(usage.get("completion_tokens") or 0)

        # 闸门：成本上限。用**真实 usage** 累计，超了就停，不再往下买。
        if a.budget is not None and price_in is not None:
            spent = compute_cost(spent_in, spent_out, price_in, price_out)
            if spent["points"] is not None and spent["points"] > a.budget:
                sys.stderr.write(
                    "!! 已花 {} 点，超过 --budget {} 点，就地中止（已完成 {} 篇，"
                    "结果仍会输出到标准输出）。\n".format(spent["points"], a.budget, len(notes)))
                result = _build_notes_result(a, source, angles, notes, usages,
                                             time.time() - t_all, est, price_in, price_out)
                if outdir:
                    (outdir / NOTES_NAME).write_text(
                        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
                _emit(a, result, render_notes_md(result), ok=False)
                return _fail(EXIT_BUDGET, "budget",
                             "已花 %s 点超过 --budget %s 点，就地中止（已完成 %d 篇）"
                             % (spent["points"], a.budget, len(notes)))

    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "system": SYSTEM_PROMPT,
                       "prompts": [{"angle": ang["name"], "user": p}
                                   for ang, p in zip(angles, prompts)]}, a, indent=2)
        return EXIT_OK

    if not notes:
        raise NoteError("没有任何一篇产出，检查一下模型名与 --max-tokens")

    result = _build_notes_result(a, source, angles, notes, usages,
                                 time.time() - t_all, est, price_in, price_out)
    if outdir:
        (outdir / NOTES_NAME).write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(outdir / NOTES_NAME))
    _emit(a, result, render_notes_md(result))
    return _gate_report(notes, result.get("cross_notes"))


def _build_notes_result(a, source, angles, notes, usages, elapsed, est,
                        price_in, price_out):
    tot = sum_usage(usages)
    actual = compute_cost(tot.get("prompt_tokens"), tot.get("completion_tokens"),
                          price_in, price_out)
    return {
        "model": a.model,
        "chat_endpoint": CHAT_URL,
        "source_chars": count_chars(source),
        "source_text": source,
        "angles": angles,
        "usage_totals": tot,
        "usage_per_note": {it["id"]: it.get("usage") for it in notes},
        "elapsed": round(elapsed, 1),
        "cost_estimate": est,
        "cost_actual_tokens": actual,
        "spec": {k: v for k, v in XHS.items() if k != "name"},
        "cross_notes": cross_note_check({it["id"]: it for it in notes}),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# covers —— 出封面（3:4，含大字标题）：先报价，再出图
# ---------------------------------------------------------------------------

def _load_notes_for_covers(a):
    obj = load_json_file(a.notes, "笔记文件")
    raw = obj.get("notes") if isinstance(obj, dict) else obj
    if not isinstance(raw, list) or not raw:
        raise UsageError("{} 里没有 notes 列表（先跑 `notes --outdir ...`）".format(a.notes))
    return obj, raw


def _run_covers(a):
    obj, raw = _load_notes_for_covers(a)
    items = []
    for n, it in enumerate(raw, 1):
        if a.only and it.get("id") not in a.only:
            continue
        note = {
            "id": it.get("id") or "n%02d" % n,
            "title": it.get("title"),
            "angle_name": it.get("angle_name"),
            "cover_text": it.get("cover_text") or it.get("title"),
            "cover_desc": it.get("cover_desc"),
        }
        note["prompt"] = build_cover_prompt(note)
        items.append(note)
    if a.count:
        items = items[:a.count]
    if not items:
        raise UsageError("没有可出图的条目（--only 过滤后为空？）")

    # 闸门：出图提示词先扫一遍（提示词里带违禁词，出到图上就删不掉了）
    blocked = []
    for it in items:
        leaks = []
        for h in compliance_scan(it["prompt"])["hits"]:
            leaks.append(("banned_word", "命中违禁词「{}」（{} 风险）：{}".format(
                h["word"], h["level"], h["why"])))
        for ch in "{}":
            if ch in it["prompt"]:
                leaks.append(("placeholder", "提示词里残留占位符 `{}`".format(ch)))
                break
        echoed, score, sample, rule = prompt_echo(it["prompt"])
        if echoed:
            leaks.append(("prompt_echo", "提示词与示例「{}」相似度 {:.2f}，属照抄/同构改写"
                          .format(sample[:28], score)))
        # 闸门：封面大字标题长度。**必须是显式拦截，不能静默截断。**
        # 旧版（1.0.4 及以前）在 `build_cover_prompt()` 里写 `[:20]`：
        # 20 字之后的内容被悄悄丢掉。而断点 key 取的是**完整**文案的摘要，
        # 所以「只改第 21 字之后」会先判定「文案变了」→ 重新提交、重新扣费，
        # 送去的提示词却逐字相同 → 出的图一模一样。用户付了钱、什么也没变。
        # 长度闸门用**未归一化**的原文计（标点与空格也占画面位置），
        # 与文档口径「12~18 字，超过 20 字一行放不下」一致。
        ctext = cover_text_of(it)
        if len(ctext) > COVER_TEXT_MAX:
            leaks.append(("cover_text_too_long",
                          "封面大字标题 {} 字，超过上限 {} 字（多出 {} 字：{}）".format(
                              len(ctext), COVER_TEXT_MAX, len(ctext) - COVER_TEXT_MAX,
                              ctext[COVER_TEXT_MAX:])))
        it["leaks"] = leaks
        if leaks:
            blocked.append(it)
    outdir = check_outdir(a.outdir) if a.outdir else default_outdir()
    # **包内不许有图**：翻页前先判一次，别等出了图才发现目录不对（那时钱已经花了）
    check_outdir(str(outdir))
    # `cover_text` 超长**不接受 --allow-prompt-hits 放行**。
    # 违禁词是"我知道有风险，我认了"，放行后送出去的提示词仍是用户写的原话；
    # 而文案超长放行后只能走回「静默截断」——用户以为改生效了、其实没有，
    # 正是这次要根除的失效类别。所以长度闸门是**无条件**的。
    too_long = [it for it in items if len(cover_text_of(it)) > COVER_TEXT_MAX]
    if too_long:
        for it in too_long:
            ctext = cover_text_of(it)
            sys.stderr.write("!! {} 的封面大字标题超长：{} 字 > 上限 {} 字\n".format(
                it["id"], len(ctext), COVER_TEXT_MAX))
            sys.stderr.write("     {}\n".format(_red(
                "多出 {} 字：{}".format(len(ctext) - COVER_TEXT_MAX, ctext[COVER_TEXT_MAX:]))))
            sys.stderr.write("     原文：{}\n".format(ctext))
        sys.stderr.write(
            "\n共 {} 张的 `cover_text` 超过 {} 字，**已拦截，未提交任何任务**（不花一分钱）。"
            "\n封面一行只放得下 {} 字；把超出的部分移到正文或 `cover_desc` 里再重跑。"
            "\n（这一条**不能**用 --allow-prompt-hits 放行：放行就等于回到静默截断，"
            "你会以为改了、其实图一模一样。）\n"
            .format(len(too_long), COVER_TEXT_MAX, COVER_TEXT_MAX))
        return _fail(EXIT_GATE, "gate",
                     "有封面大字标题超过 %d 字，已拦截、未提交任何任务" % COVER_TEXT_MAX)
    if blocked and not a.allow_prompt_hits:
        for it in blocked:
            sys.stderr.write("!! {} 的封面提示词命中闸门：\n".format(it["id"]))
            for kind, why in it["leaks"]:
                sys.stderr.write("     {}\n".format(_red("{}：{}".format(kind, why))))
        sys.stderr.write(
            "\n共 {} 张被判不合格，**已拦截，未提交任何任务**（不花一分钱）。\n"
            "改掉封面文案/描述后重跑；确实要带违禁词出图才加 --allow-prompt-hits。\n"
            .format(len(blocked)))
        return _fail(EXIT_GATE, "gate", "有封面提示词命中本地闸门，已拦截、未提交任何任务")

    outdir.mkdir(parents=True, exist_ok=True)
    state_path = a.state or str(outdir / STATE_NAME)
    state = load_state(state_path)

    cost = image_cost(len(items), a.resolution, a.points_per_image)
    sys.stderr.write("将要出图：%d 张（小红书封面 %s）\n" % (len(items), COVER_RATIO))
    for it in items:
        sys.stderr.write("  %-5s %-10s %s\n" % (
            it["id"], it.get("angle_name") or "-",
            (it.get("cover_text") or "")[:22]))
    sys.stderr.write("  输出目录：%s  （**必须不在 Skill 包内**）\n" % outdir)
    sys.stderr.write("预估成本：%s\n" % fmt_cost(cost))
    for n in cost.get("notes") or []:
        sys.stderr.write("  · %s\n" % n)

    # 闸门：成本上限。**在提交任何任务之前**判，超了直接停。
    if cost.get("total_points") is None:
        sys.stderr.write("\n!! 没有 %s 档的可信单价，拒绝盲跑。"
                         "用 --points-per-image <点数> 指定单价后重试。\n" % a.resolution)
        return _fail(EXIT_USAGE, "usage", "%s 档没有实测单价，拒绝凭猜估算" % a.resolution)
    if a.budget is not None and cost["total_points"] > a.budget:
        sys.stderr.write("\n!! 预估 %g 点超过预算上限 %g 点，**已中断，未提交任何任务**。\n"
                         % (cost["total_points"], a.budget))
        return _fail(EXIT_BUDGET, "budget",
                     "预估 %g 点超过 --budget 上限 %g 点，未提交任何任务"
                     % (cost["total_points"], a.budget))
    # 成本前置：没有 --yes 也没有 --budget 时，只报价不动作
    if not a.yes and a.budget is None:
        sys.stderr.write("\n这是一次**真花钱**的操作（约 %.2f 元）。"
                         "确认后加 --yes 重跑，或加 --budget 设上限。\n" % (cost["total_yuan"] or 0))
        return _fail(EXIT_USAGE, "usage", "这是一次真花钱的操作，确认后加 --yes（或 --budget）重跑")

    total_points = 0.0
    spent_this_run = 0.0
    done, skipped, failed, ratio_bad = [], [], [], []
    for n, it in enumerate(items, 1):
        key = cover_state_key(it, a.resolution)
        prev = (state.get("items") or {}).get(key)
        # 二次兜底：key 只认「笔记 id + 比例 + 分辨率 + 封面文案摘要」，
        # 正常不会出现「key 相同但文案或分辨率不同」。但断点文件可能是手工改过的、
        # 或由旧版本生成的，一旦真出现就必须**重出**，绝不能静默复用旧图。
        # （本包原则：断点命中不能只看状态标记，还要看记录里的文案对不对得上。）
        # 记录里没存 `cover_copy`（旧版断点、手改过的断点）也按「不一致」处理：
        # 说不出上次文案是什么，就没有复用旧图的依据。
        cur_copy = _cover_copy_text(it)
        prev_copy = prev.get("cover_copy") if prev else None
        if prev and (not isinstance(prev_copy, str) or prev_copy != cur_copy):
            sys.stderr.write("    %s 断点记录里的封面文案与本次不一致 → **不复用旧图**，重新出图\n"
                             % it["id"])
            prev = None
        # 分辨率兜底：与文案兜底同一口径。key 里已经带了 resolution，
        # 但断点文件是旧版生成的（那时 key 不含分辨率）或手改过时，
        # 记录里的 `resolution` 可能与本次对不上；对不上就重出。
        # 记录里**没存** `resolution`（旧断点）同样按「不一致」处理：
        # 说不出上次是什么档，就没有复用那张图的依据。
        prev_res = prev.get("resolution") if prev else None
        if prev and (not isinstance(prev_res, str) or prev_res.upper() != a.resolution.upper()):
            sys.stderr.write("    %s 断点记录里的分辨率（%s）与本次（%s）不一致 → "
                             "**不复用旧图**，重新出图\n"
                             % (it["id"], prev_res or "没存", a.resolution))
            prev = None
        if prev and prev.get("status") == "completed" and not a.force:
            pts = prev.get("points_cost")
            total_points += float(pts or 0)
            skipped.append((it, prev))
            sys.stderr.write("[%d/%d] %s 已完成，跳过（上次扣费 %s 点，不再重复扣）\n"
                             % (n, len(items), it["id"], pts))
            continue
        task_id = (prev or {}).get("task_id") if prev and prev.get("status") == "pending" else None
        if task_id and not a.force:
            sys.stderr.write("[%d/%d] %s 续查未完成任务 task_id=%s\n"
                             % (n, len(items), it["id"], task_id))
        else:
            if a.budget is not None:
                will_spend = total_points + (cost["points_per_image"] or 0)
                if will_spend > a.budget:
                    sys.stderr.write("\n!! 已花/待花 %g 点将超过预算 %g 点，**就此停下**"
                                     "（不再提交新任务）。\n   断点文件：%s\n"
                                     % (will_spend, a.budget, state_path))
                    save_state(state_path, state)
                    return _fail(EXIT_BUDGET, "budget",
                                 "已花/待花 %g 点将超过 --budget %g 点，就此停下"
                                 % (will_spend, a.budget))
            sys.stderr.write("[%d/%d] %s 提交：aspect_ratio=%s resolution=%s\n"
                             % (n, len(items), it["id"], COVER_RATIO, a.resolution))
            try:
                data = submit_image(it["prompt"], aspect_ratio=COVER_RATIO,
                                    resolution=a.resolution, model=a.image_model, key=a.key)
            except a7w.A7wError as exc:
                sys.stderr.write("    提交失败：%s\n" % exc)
                failed.append({"id": it["id"], "stage": "submit", "error": str(exc)})
                continue
            task_id = data.get("task_id")
            state.setdefault("items", {})[key] = {
                "id": it["id"], "prompt": it["prompt"], "aspect_ratio": COVER_RATIO,
                "resolution": a.resolution, "task_id": task_id, "status": "pending",
                # 存下本次封面文案（原文 + 归一化串）：下次重跑要拿它跟本次比，
                # 对不上就重出。`cover_copy` 是判据，原文两个字段是给人看的。
                "cover_text": it.get("cover_text"), "cover_desc": it.get("cover_desc"),
                "cover_copy": cur_copy,
                "frozen_points": data.get("frozen_points"),
                "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            save_state(state_path, state)      # 先落盘：崩了也能续查这个 task_id
        if a.no_wait:
            continue
        try:
            status, data, payload, ticks = poll_task(task_id, key=a.key,
                                                     timeout=a.poll_timeout)
        except a7w.A7wError as exc:
            sys.stderr.write("    轮询失败：%s（task_id=%s 可用 `a7w.py task` 续查）\n"
                             % (exc, task_id))
            failed.append({"id": it["id"], "stage": "poll", "task_id": task_id,
                           "error": str(exc)})
            continue
        rec = state["items"][key]
        rec["last_status"] = status
        rec["raw_task"] = payload
        if status != "completed":
            err = data.get("error") or (data.get("result") or {}).get("error") or ""
            rec["status"] = "failed"
            rec["error"] = "%s %s" % (status, err)
            save_state(state_path, state)
            failed.append({"id": it["id"], "stage": "task", "task_id": task_id,
                           "error": rec["error"], "raw_task": payload})
            continue
        pts = points_cost(data)
        rec["points_cost"] = pts
        if pts:
            total_points += float(pts)
            spent_this_run += float(pts)
        urls = find_image_urls(data)
        if not urls:
            rec["status"] = "failed"
            rec["error"] = "任务完成但没找到图片地址"
            save_state(state_path, state)
            failed.append({"id": it["id"], "stage": "no_url", "task_id": task_id,
                           "raw_task": payload})
            continue
        url = urls[0]
        dest = outdir / COVER_DIR / ("%s-%s%s" % (
            it["id"], COVER_RATIO.replace(":", "x"), ".png"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            a7w.save(url, str(dest))
        except a7w.A7wError as exc:
            rec["status"] = "failed"
            rec["error"] = "下载失败：%s" % exc
            rec["image_url"] = url
            save_state(state_path, state)
            failed.append({"id": it["id"], "stage": "download", "task_id": task_id,
                           "error": str(exc), "image_url": url})
            continue

        check = check_ratio(str(dest), COVER_RATIO, a.ratio_tolerance)
        first_check = dict(check)
        rec["image_url"] = url
        rec["file"] = str(dest)
        rec["first_check"] = first_check
        rec["real_px"] = check["real_px"]
        rec["real_ratio"] = check.get("real_ratio")
        rec["want_ratio"] = COVER_RATIO
        rec["ratio_deviation"] = check["deviation"]
        # `--snap` 的语义是「我要像素级等于请求比例」，不是「容差内就不裁」。
        # 实测踩到的坑：请求 3:4 拿到 864x1184 偏差 2.70%，在 3% 容差**内**，
        # 于是下面的 `not check["ok"]` 不成立，图根本没裁 —— 加了 --snap 却什么也没发生。
        # 所以只要给了 --snap 就一律裁，裁完再复核。
        if a.snap:
            snapped = str(dest.with_name(dest.stem + "-snapped" + dest.suffix))
            got = snap_to_ratio(str(dest), snapped, COVER_RATIO)
            if got:
                way, box = got
                after = check_ratio(snapped, COVER_RATIO, a.ratio_tolerance)
                rec["snap"] = {"method": way, "box": box, "file": snapped, "after": after}
                if after["ok"]:
                    dest = Path(snapped)
                    check = after
                    rec["real_px"] = after["real_px"]
                    rec["real_ratio"] = after.get("real_ratio")
                    rec["ratio_deviation"] = after["deviation"]
                    rec["file"] = str(snapped)
            else:
                rec["snap"] = {"method": None,
                               "why": "没有 PIL，内置裁剪器也不支持这个 PNG"
                                      "（需 8 位真彩/真彩+alpha）"}
        rec["raw_ratio_check"] = check
        rec["ratio_ok"] = bool(check["ok"])
        rec["status"] = "completed"
        save_state(state_path, state)
        # 容差内也要**明确打印真实像素与偏差**，不藏
        sys.stderr.write("    完成 真实像素 %sx%s（%s = %s） 请求 %s 偏差 %.2f%% 扣费 %s 点 → %s\n"
                         % (check["real_px"][0], check["real_px"][1],
                            check.get("real_label"), check.get("real_ratio"),
                            COVER_RATIO, (check.get("deviation") or 0) * 100,
                            pts, rec["file"]))
        if check["ok"]:
            done.append((it, rec))
        else:
            ratio_bad.append((it, rec))
            sys.stderr.write("    " + _red("比例不合格：%s\n" % check.get("why")))

    notes_obj = dict(obj) if isinstance(obj, dict) else {"notes": obj}
    summary = {
        "notes_file": str(Path(a.notes)),
        "outdir": str(outdir), "state": state_path,
        "want_ratio": COVER_RATIO, "resolution": a.resolution,
        "tolerance": RATIO_TOLERANCE if a.ratio_tolerance is None else a.ratio_tolerance,
        "cover_endpoint": SUBMIT_URL, "task_endpoint": TASK_URL,
        "planned_images": len(items),
        "completed": [{"id": it["id"], "title": it.get("cover_text"), "task_id": r.get("task_id"),
                       "file": r.get("file"), "image_url": r.get("image_url"),
                       "real_px": r.get("real_px"), "real_label": (r.get("raw_ratio_check") or {}).get("real_label"),
                       "real_ratio": r.get("real_ratio"), "want_ratio": r.get("want_ratio"),
                       "deviation": r.get("ratio_deviation"), "points_cost": r.get("points_cost"),
                       "first_check": r.get("first_check"), "snap": r.get("snap"),
                       "request": {"prompt": it["prompt"], "action": "generate",
                                   "model": a.image_model, "resolution": a.resolution,
                                   "aspect_ratio": COVER_RATIO},
                       "raw_task": r.get("raw_task")}
                      for it, r in done],
        "skipped_already_done": [
            {"id": it["id"], "task_id": r.get("task_id"), "file": r.get("file"),
             "points_cost": r.get("points_cost"), "real_px": r.get("real_px")}
            for it, r in skipped],
        "ratio_failed": [{"id": it["id"], "file": r.get("file"), "real_px": r.get("real_px"),
                          "want_ratio": COVER_RATIO,
                          "why": (r.get("raw_ratio_check") or {}).get("why")}
                         for it, r in ratio_bad],
        "failed": failed,
        "points_cost_total": total_points,
        "points_cost_this_run": spent_this_run,
        "yuan_this_run": round(spent_this_run / POINTS_PER_YUAN, 3),
        "estimate": cost,
        "notes_source": notes_obj.get("source_text"),
    }
    (outdir / COVERS_NAME).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    sys.stderr.write("封面记录已写入 %s\n" % (outdir / COVERS_NAME))
    if a.json:
        _json_write(_json_text(summary, indent=1, ok=not (failed or ratio_bad)))
    else:
        print(render_covers_md(summary))
    if failed:
        return _fail(EXIT_CALL, "call", "%d 张出图失败（明细见 stderr）" % len(failed))
    if ratio_bad:
        return _fail(EXIT_GATE, "gate",
                     "%d 张真实比例与请求不符（容差 %.1f%%）"
                     % (len(ratio_bad), summary["tolerance"] * 100))
    return EXIT_OK


# ---------------------------------------------------------------------------
# check —— 对已有笔记做本地合规自检（零成本，不调模型）
# ---------------------------------------------------------------------------

def _run_check(a):
    obj = load_json_file(a.file, "笔记文件")
    raw = obj.get("notes") if isinstance(obj, dict) else obj
    if not isinstance(raw, list) or not raw:
        raise UsageError("{} 里没有 notes 列表。本命令要的是 `notes --outdir` 生成的 "
                         "notes.json，不是母稿本身。".format(a.file))
    notes = _notes_from_raw(raw)
    cross = cross_note_check({it["id"]: it for it in notes})
    result = {
        "file": str(Path(a.file)),
        "chat_endpoint": None,
        "note": "**纯本地**：只跑确定性闸门（合规 / 占位符 / 照抄示例 / 笔记规格 / 跨篇换皮），"
                "不调模型、不花钱、同一个文件跑两次结果完全一样。",
        "spec": {k: v for k, v in XHS.items() if k != "name"},
        "cross_notes": cross,
        "count": len(notes),
        "blocked": [it["id"] for it in notes if note_gate_failed(it)],
        "notes": notes,
    }
    md = render_notes_md({"notes": notes, "cross_notes": cross})
    if a.json:
        _json_write(_json_text(result, indent=2, ok=not result["blocked"]
                               and not cross.get("flagged")))
    else:
        print(md)
    return _gate_report(notes, cross)


# ---------------------------------------------------------------------------
# all —— 整条链路，断点续跑
# ---------------------------------------------------------------------------

def _run_all(a):
    outdir = check_outdir(a.outdir) if a.outdir else default_outdir()
    check_outdir(str(outdir))
    outdir.mkdir(parents=True, exist_ok=True)
    state_path = a.state or str(outdir / STATE_NAME)
    state = load_state(state_path)
    stages = state.setdefault("stages", {})

    # `--dry-run` 下**绝不写断点**。实测踩过的坑：dry-run 跑一遍会留下
    # stages.notes.done=true，而 notes.json 根本没生成（dry-run 不产出），
    # 于是下一次真跑时"断点说已完成、文件不存在"，直接 exit 2。
    # 干跑不产生副作用，就不能改断点文件。
    dry = bool(getattr(a, "dry_run", False))
    save = (lambda: None) if dry else (lambda: save_state(state_path, state))

    sys.stderr.write("=== 小红书笔记工厂 · 整条链路 ===\n")
    sys.stderr.write("输出目录：%s（包外；包内不许有任何图片）\n" % outdir)
    if dry:
        sys.stderr.write("（--dry-run：只打印提示词，不调模型、不写断点）\n")

    # --- 阶段 1：角度 ---
    if not (stages.get("angles") or {}).get("done"):
        sys.stderr.write("\n[1/3] 出角度…\n")
        na = argparse.Namespace(**vars(a))
        na.out = None
        na.json = False
        rc = _run_angles(na)
        if rc:
            return rc
        stages["angles"] = {"done": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save()
    else:
        sys.stderr.write("\n[1/3] 角度已完成，跳过（断点续跑）\n")

    # --- 阶段 2：笔记 ---
    notes_path = outdir / NOTES_NAME
    if not (stages.get("notes") or {}).get("done"):
        sys.stderr.write("\n[2/3] 写笔记…\n")
        na = argparse.Namespace(**vars(a))
        na.outdir = str(outdir)
        na.out = None
        na.json = False
        rc = _run_notes(na)
        # 硬闸门命中（3）也要继续往下走：封面还是值得出的，最后按最重的退出码返回
        if rc not in (EXIT_OK, EXIT_GATE):
            return rc
        stages["notes"] = {"done": True, "rc": rc,
                           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save()
        notes_rc = rc
    else:
        sys.stderr.write("\n[2/3] 笔记已完成，跳过（断点续跑）\n")
        if not notes_path.is_file():
            raise UsageError("断点说笔记已完成，但 %s 不存在。删掉断点文件重跑。" % notes_path)
        notes_rc = EXIT_OK

    # --- 阶段 3：封面 ---
    # `--dry-run` 到这里就结束：干跑不产出 notes.json，而 covers 必须读它。
    # 实测踩过：不停下就会报「找不到笔记文件」，让一次干跑看起来像失败了。
    if dry:
        sys.stderr.write("\n（--dry-run 结束：没有调用任何模型、没有花钱、没有写断点）\n")
        return EXIT_OK if not notes_rc else EXIT_GATE
    if not (stages.get("covers") or {}).get("done"):
        sys.stderr.write("\n[3/3] 出封面…\n")
        na = argparse.Namespace(**vars(a))
        na.notes = str(notes_path)
        na.outdir = str(outdir)
        na.json = False
        # `all` 不定义 --only / --no-wait 的**默认值来自 `_add_image_opts`**，
        # 这里只做兜底：万一以后有人改了参数表，缺字段不会变成隐藏的运行时炸弹。
        for k, v in (("force", False), ("only", None), ("no_wait", False),
                     ("allow_prompt_hits", False)):
            if not hasattr(na, k):
                setattr(na, k, v)
        rc = _run_covers(na)
        if rc not in (EXIT_OK, EXIT_GATE):
            return rc
        stages["covers"] = {"done": True, "rc": rc,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save()
        covers_rc = rc
    else:
        sys.stderr.write("\n[3/3] 封面已完成，跳过（断点续跑）\n")
        covers_rc = EXIT_OK

    if dry:
        # 干跑没有产出文件可读，上面的分支已经返回；这里只是双保险。
        sys.stderr.write("\n（--dry-run 结束：没有调用任何模型、没有花钱、没有写断点）\n")
        return EXIT_OK if not (notes_rc or covers_rc) else EXIT_GATE

    notes_obj = load_json_file(notes_path, "笔记文件")
    covers_obj = load_json_file(outdir / COVERS_NAME, "封面记录")
    result = {
        "outdir": str(outdir),
        "state": state_path,
        "stages": stages,
        "angles": notes_obj.get("angles"),
        "notes": notes_obj.get("notes"),
        "cross_notes": notes_obj.get("cross_notes"),
        "covers": covers_obj,
        "usage_totals": notes_obj.get("usage_totals"),
        "cost_actual_tokens": notes_obj.get("cost_actual_tokens"),
        "points_cost_images": covers_obj.get("points_cost_this_run"),
        "yuan_images": covers_obj.get("yuan_this_run"),
    }
    if a.json:
        _json_write(_json_text(result, indent=1,
                               ok=not (notes_rc or covers_rc)))
    else:
        print("# 小红书笔记工厂 · 全链路完成")
        print("")
        print("输出目录：{}".format(outdir))
        print("笔记：{} 篇（{}）".format(len(result["notes"] or []),
                                        notes_path))
        print("封面：{} 张成功，出图花 {} 点 = ¥{}".format(
            len((covers_obj.get("completed") or [])),
            covers_obj.get("points_cost_this_run"), covers_obj.get("yuan_this_run")))
        print("断点文件：{}（重跑直接续，不会重复扣费）".format(state_path))
    return EXIT_GATE if (notes_rc == EXIT_GATE or covers_rc == EXIT_GATE) else EXIT_OK


# ---------------------------------------------------------------------------
# cost —— 只算钱
# ---------------------------------------------------------------------------

def _run_cost(a):
    source = read_source(a)
    angles, _ = pick_angles(a.count, source, "local")   # 估算用本地角度，零成本
    rows, per_in, per_out = [], [], []
    for ang in angles:
        prompt = build_note_prompt(source, ang,
                                   [o["name"] for o in angles if o["key"] != ang["key"]],
                                   a.evidence, a.brief)
        tin = estimate_tokens_in(SYSTEM_PROMPT + prompt)
        tout = estimate_tokens_out(XHS["body_chars"][0])
        per_in.append(tin)
        per_out.append(tout)
        rows.append({"angle": ang["name"], "tokens_in": tin, "tokens_out": tout})
    tot_in, tot_out = sum(per_in), sum(per_out)
    rec = compute_cost(tot_in, tot_out, a.price_in, a.price_out)
    rec["source"] = ("本地估算（输入按 %.2f 字/token、输出按 %.3f token/字标定，不是账单）"
                     % (CHARS_PER_TOKEN_IN, TOKENS_PER_CHAR_OUT))
    rec["source_chars"] = count_chars(source)
    rec["cost_rows"] = rows
    rec["cover_count"] = a.cover_count
    img = image_cost(a.cover_count, a.resolution, a.points_per_image)
    rec["image_cost"] = img
    if rec.get("points") is not None and img.get("total_points") is not None:
        rec["total_points"] = round(rec["points"] + img["total_points"], 4)
        rec["total_yuan"] = round(rec["total_points"] / POINTS_PER_YUAN, 4)
    else:
        rec["total_points"] = None
        rec["total_yuan"] = None
        rec["cost_note"] = ("文本部分的金额要你给单价才能算（本包拒绝编价）；"
                            "出图部分是实测价 24 点/张（1K）。")
    rc = EXIT_OK
    if a.budget is not None:
        if rec["total_points"] is None:
            sys.stderr.write("!! 给了 --budget 但缺单价/出图数，无法判断是否超预算。\n")
            rc = _fail(EXIT_USAGE, "usage", "给了 --budget 却缺单价，无法判断是否超预算")
        else:
            rec["budget"] = a.budget
            rec["over_budget"] = rec["total_points"] > a.budget
            if rec["over_budget"]:
                rc = EXIT_BUDGET
    if a.json:
        _json_out(rec, a, indent=2, ok=not rc)
    else:
        print("# 成本预估")
        print("")
        print("- 母稿：{} 字；笔记 {} 篇；封面 {} 张".format(
            rec["source_chars"], len(rows), a.cover_count))
        print("- 标定（实测）：输入 1 个原始字符 ≈ {:.3f} token；输出 1 个原始字符 ≈ {} token"
              .format(1.0 / CHARS_PER_TOKEN_IN, TOKENS_PER_CHAR_OUT))
        print("")
        print("| 角度 | 预估输入 token | 预估输出 token |")
        print("|---|---|---|")
        for r in rows:
            print("| {} | {} | {} |".format(r["angle"], r["tokens_in"], r["tokens_out"]))
        print("| **合计** | **{}** | **{}** |".format(tot_in, tot_out))
        print("")
        print("- 文本：{}".format(fmt_cost(rec)))
        print("- 出图：{} 张 × {} 点 = {} 点 = ¥{}".format(
            a.cover_count, img.get("points_per_image"),
            img.get("total_points"), img.get("total_yuan")))
        for n in rec.get("notes") or []:
            print("- 注：{}".format(n))
        if a.budget is not None and rec["total_points"] is not None:
            print("- 预算 {} 点：{}".format(
                a.budget, "超了" if rec.get("over_budget") else "在预算内"))
        print("")
        print("文本模型的单价网关不公布（pricing 表不含文本模型、models 无价格字段），")
        print("所以文本只出 token 数，金额必须你用 --price-in / --price-out 填。")
    return rc


# ---------------------------------------------------------------------------
# models —— 现查在架模型
# ---------------------------------------------------------------------------

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
    print("      `{}` 实测可用（路由到 deepseek-flash 一线），但它**不在**上面这份列表里，"
          .format(DEFAULT_MODEL))
    print("      所以「列表里没有」不等于「不能用」。")
    print("      实测本列表里也没有任何价格字段；算文本钱请用 cost --price-in/--price-out。")
    return EXIT_OK


# ===========================================================================
# 入口
# ===========================================================================

# ---------------------------------------------------------------------------
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封（已经吐过结果的，ok 写在那个结果里）
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#
# 【关键】信封必须落在**真 stdout**：`covers` 会把进度打到 stderr / 或临时换掉 sys.stdout，
# 所以这里专门记住原始 stdout（`_JSON["stdout"]`），JSON 文本统一经 `_json_write` 写。
# 这条不变量（stdout 里永远只有一个完整 JSON）是被 `json.loads` 直接消费的，
# 破一次整条流水线就崩。
# ---------------------------------------------------------------------------

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}

_KIND_BY_EXIT = {1: "internal", 2: "usage", 3: "gate", 4: "call", 5: "budget",
                 130: "interrupt"}


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
    """让 `--json` 写在子命令**前后都能用**。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py check --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_model_opts(p):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 {}（实测可用；用 `run.py models` 现查在架模型）".format(
                       DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.8, help="采样温度，默认 0.8")
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens",
                   help="最大输出 token，默认 8192（一篇笔记 + JSON 包装足够）")
    p.add_argument("--key", help="临时指定 A7W API Key（**别把它写进脚本或文档**）")
    p.add_argument("--out", help="把结果写到这个文件")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_source_opts(p):
    p.add_argument("--file", help="母稿 / 产品信息文件（.md / .txt）")
    p.add_argument("--text", help="直接给母稿正文（与 --file 二选一，同时给以 --text 为准）")
    p.add_argument("--count", type=int, default=5, help="篇数 / 角度数，默认 5")


def _add_cost_opts(p):
    p.add_argument("--price-in", type=float, dest="price_in",
                   help="文本输入单价，单位「点/百万 token」。不给我就不给金额（不编价）")
    p.add_argument("--price-out", type=float, dest="price_out",
                   help="文本输出单价，单位「点/百万 token」")
    p.add_argument("--budget", type=float,
                   help="预算上限（点）。超了就地中止，退出码 5；用 --budget 必须给文本单价")


def _add_outdir_opts(p):
    p.add_argument("--outdir", help="输出目录（**必须不在 Skill 包内**，包内不许有任何图片）")
    p.add_argument("--state", help="断点文件路径，默认 <outdir>/%s" % STATE_NAME)


def _add_only_opts(p):
    """出图相关的「续跑 / 挑选 / 不等待」三件套。抽出来是为了 `covers` 和 `all` 共用。

    抽出来的原因很实在：这两组参数在 `covers` 里由 `_add_image_opts` 定义、
    在 `all` 里又要用同一套。上一版我在 `all` 里又写了一遍 `--force`，
    结果 argparse 直接 `conflicting option string`，**所有子命令一起打不开**。
    一个重复定义就能把整包打挂，所以这类开关必须只有一处定义。
    """
    p.add_argument("--force", action="store_true",
                   help="忽略断点重出（**会重复扣费**）")
    p.add_argument("--only", action="append",
                   help="只出这几篇的封面（可重复，按笔记 id：--only n01）")
    p.add_argument("--no-wait", action="store_true", dest="no_wait",
                   help="只提交任务不等待（之后用 task_id 续查）")


def _add_image_opts(p, budget=True):
    # `budget=False` 给 `all` / `cost` 用：那两个子命令已经在 `_add_cost_opts` 里
    # 定义过 --budget，重复定义会让 argparse 直接抛 ConflictError。
    if budget:
        p.add_argument("--budget", type=float,
                       help="预算上限（点）。超了就地中止，退出码 5；有 --budget 就不必再加 --yes")
    p.add_argument("--image-model", default="nano-banana", dest="image_model",
                   choices=IMAGE_MODELS, help="出图模型，默认 nano-banana")
    p.add_argument("--resolution", default=COVER_RESOLUTION, choices=RESOLUTIONS,
                   help="出图分辨率，默认 1K（只有 1K 有实测价 24 点/张）")
    p.add_argument("--points-per-image", type=float, dest="points_per_image",
                   help="单张点数（覆盖实测价；2K/4K 没有实测价，必须自己给）")
    p.add_argument("--ratio-tolerance", type=float, dest="ratio_tolerance",
                   help="比例容差，默认 0.03（3 个百分点）；容差内也会打印真实偏差")
    p.add_argument("--snap", action="store_true",
                   help="出图后按 3:4 精确裁到 864x1152（上游按 32 对齐，请求 3:4 实测给 864x1184）")
    p.add_argument("--yes", action="store_true", help="确认这是一次真花钱的操作")
    _add_only_opts(p)
    p.add_argument("--allow-prompt-hits", action="store_true", dest="allow_prompt_hits",
                   help="封面提示词命中闸门也照出（默认拦截，不花钱）")
    p.add_argument("--poll-timeout", type=int, default=POLL_TIMEOUT, dest="poll_timeout",
                   help="单张轮询超时秒数，默认 600")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 小红书笔记工厂（母稿 → N 篇笔记 → 封面 → 合规自检）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "POST https://api.a7w.cn/api/v1/apps/nano_banana/submit · "
               "GET https://api.a7w.cn/api/v1/tasks/<task_id>")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("angles", help="出 N 个切入角度（默认零成本，本地角度库）")
    _add_source_opts(p)
    p.add_argument("--strategy", choices=("local", "llm"), default="local",
                   help="local=本地角度库（零成本、可复现）；llm=针对材料出角度（一次调用）")
    p.add_argument("--model", default=DEFAULT_MODEL, help="--strategy llm 时用的模型")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--out", help="把结果写到这个文件")
    _add_json(p)
    p.set_defaults(func=_run_angles)

    p = sub.add_parser("notes", help="按角度逐篇写笔记正文 + 话题标签（花钱）")
    _add_source_opts(p)
    p.add_argument("--strategy", choices=("local", "llm"), default="local",
                   help="角度来源，默认 local（零成本）")
    p.add_argument("--brief", help="作者的要求（口述的意图）")
    p.add_argument("--evidence", help="可以使用的真实素材（没写就不许编数字）")
    _add_outdir_opts(p)
    _add_cost_opts(p)
    _add_model_opts(p)
    p.set_defaults(func=_run_notes)

    p = sub.add_parser("covers", help="出封面图方案 + 出图（3:4 大字标题；先报价）")
    p.add_argument("--notes", required=True, help="notes --outdir 生成的 notes.json")
    p.add_argument("--count", type=int, default=0, help="只出前 N 张，默认全部")
    _add_outdir_opts(p)
    _add_image_opts(p)
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--out", help="把结果写到这个文件")
    _add_json(p)
    p.set_defaults(func=_run_covers)

    p = sub.add_parser("check", help="对已有笔记做本地合规自检（零成本，不调模型）")
    p.add_argument("--file", required=True, help="notes --outdir 生成的 notes.json")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_check)

    p = sub.add_parser("all", help="整条链路（角度 → 笔记 → 封面），断点续跑")
    _add_source_opts(p)
    p.add_argument("--strategy", choices=("local", "llm"), default="local",
                   help="角度来源，默认 local（零成本）")
    p.add_argument("--brief", help="作者的要求")
    p.add_argument("--evidence", help="可以使用的真实素材")
    _add_outdir_opts(p)
    _add_cost_opts(p)
    _add_image_opts(p, budget=False)
    p.add_argument("--model", default=DEFAULT_MODEL, help="文本模型名")
    p.add_argument("--temperature", type=float, default=0.8, help="采样温度")
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens",
                   help="最大输出 token")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    # 注意：**不要**在这里再定义 --force / --only / --no-wait ——
    # 下面的 `_add_image_opts` 已经定义了，重复定义会让 argparse 抛
    # `conflicting option string`，而且**是所有子命令一起打不开**（实测踩过两次）。
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=_run_all)

    p = sub.add_parser("cost", help="只算钱（不调模型）")
    _add_source_opts(p)
    p.add_argument("--cover-count", type=int, default=0, dest="cover_count",
                   help="要出几张封面（默认 0，只算文本）")
    p.add_argument("--brief", help="作者的要求（会影响提示词长度，从而影响估算）")
    p.add_argument("--evidence", help="真实素材（同上）")
    _add_cost_opts(p)
    _add_image_opts(p, budget=False)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）")
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=_run_models)
    return ap


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与以前完全一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout          # 记住真 stdout（信封不许被吞掉）
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
