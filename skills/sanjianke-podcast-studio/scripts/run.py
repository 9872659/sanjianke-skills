#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 播客全自动生产（sanjianke-podcast-studio）。

给一个主题 → 一期**可发布的播客**：选题与提纲 → 双人对话稿 → 分角色配音（两个音色）
→ 片头 / 转场 / 片尾配乐 → 本地混音成 mp3 + 章节标记 + 时间轴。

子命令
    outline   选题 + 提纲（标题 / 角度 / 受众 / 章节 / 片头钩子 / 片尾收束）
    script    双人对话稿（**必须两个角色标注且交替发言**，每句标语气）
    voice     分角色配音（两个音色；跑前报价；断点续跑，已完成的片段不重复扣费）
    music     片头 / 转场 / 片尾配乐（music_generation/create）
    mix       本地拼接成 mp3 + 章节标记 chapters.txt + 时间轴 timeline.md
    all       整条链路（断点续跑）
    cost      只算钱，一次调用都不发
    models    现查 api.a7w.cn 在架模型（模型名会变，别写死）
    voices    现查可用音色（配音要的 reference_id 从这里拿）

真实端点（都在 api.a7w.cn 上；**开工前用 schema 现查，别照抄记忆**）
    大模型      POST https://api.a7w.cn/api/v1/chat/completions
    模型清单    GET  https://api.a7w.cn/api/v1/models
    配音（同步）POST https://api.a7w.cn/api/v1/apps/voice_tts/tts
    配音（异步）POST https://api.a7w.cn/api/v1/apps/voice_tts/tts_async
    音色列表    POST https://api.a7w.cn/api/v1/apps/voice_tts/list_voices
    配乐        POST https://api.a7w.cn/api/v1/apps/music_generation/create
    任务轮询    GET  https://api.a7w.cn/api/v1/tasks/<task_id>

两条**实测踩过的**接口事实（本包开工前用 `python scripts/a7w.py schema ...` 现查确认过）
    1. 配音的音色参数叫 `reference_id`（值是 list_voices 返回的 model_id），
       **不叫 `voice_id`**。少一个字就是 400 / 音色不生效。
    2. 配乐的创建动作叫 `create`，**不叫 `generate`**。
       接口代码里没有 `generate`，只有 `create` 的 `type` 参数取 `generate`。

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 scripts/run.py outline --topic "..." --key <你的Key>
    Windows PowerShell:  $env:A7W_API_KEY="<你的Key>"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key <你的Key>）

六道本地硬闸门（都是**拦截**：标红 + stderr 汇总 + 退出码非 0，不是"提示一下"）
    1. 合规         广告法违禁词 + 播客平台红线；「最X」按可枚举语境豁免（见 _is_data_extreme）
    2. 占位符残留   `{}`、`[待填]`、`XXX`、`此处省略`、TODO
    3. prompt_echo  照抄提示词示例：去标点相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60
    4. 对话稿结构   **两个角色标注 + 交替发言**；单角色或无角色标注直接拦（播客的核心形态）
    5. 时长估算     按字数估时长，与目标时长偏离超过 ±25% 拦
    6. 成本上限     配音/配乐/整链路跑前**必须报价**，且 --yes 或受 --budget 约束

设计取舍
    · 闸门读的是**渲染后的稿子本身**（正则解析 `**角色**（语气）：台词`），
      不采信模型自报的结构字段。吃过"只信自报值、闸门成假绿"的亏。
    · 结算只认 `usage.points_cost`。平台的 `pricing_matrix` / `tenant_*` 字段**半数不可信**，
      本包不拿它们算钱。
    · 缺失的单价不编：文本大模型的单价平台不公开，`cost` 没给 `--points-per-ktok`
      就只报 token 数、不报金额。
    · 产出（音频 / 混音中间件）**一律不许落进包内**，`--outdir` 指到包内直接 exit=2。

用法示例
    python3 scripts/run.py outline --topic "AI 剪辑到底省了谁的时间" --minutes 30
    python3 scripts/run.py script  --outdir D:/podcast/ep01 --json
    python3 scripts/run.py voice   --outdir D:/podcast/ep01 --yes
    python3 scripts/run.py music   --outdir D:/podcast/ep01 --cues intro,outro --budget 200
    python3 scripts/run.py mix     --outdir D:/podcast/ep01 --ffmpeg C:/ffmpeg/bin/ffmpeg.exe
    python3 scripts/run.py cost    --minutes 30 --cues intro,bed,outro
"""

import argparse
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import traceback
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402  ← 共用零依赖客户端；**逐字节等于规范版，本包不改它**

# 控制台统一按 UTF-8 输出：Windows 代码页会把中文和 emoji 打成乱码，
# 而且 `--json` 的产物要能被 json.loads 直接吃。
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 包根目录：scripts/ 的上一级。`--outdir` 落在这里面就是违规（包内不许有音频/二进制）。
PKG_ROOT = Path(__file__).resolve().parent.parent

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"
TASK_URL = a7w.HOST + "/api/v1/tasks/"          # 异步任务轮询（配音长文 / 配乐）

APP_VOICE = "voice_tts"
APP_MUSIC = "music_generation"
TTS_ENDPOINT = "/api/v1/apps/voice_tts/tts"
TTS_ASYNC_ENDPOINT = "/api/v1/apps/voice_tts/tts_async"
VOICES_ENDPOINT = "/api/v1/apps/voice_tts/list_voices"
MUSIC_ENDPOINT = "/api/v1/apps/music_generation/create"
LYRICS_ENDPOINT = "/api/v1/apps/music_generation/lyrics"

# 实测可用：这个别名会路由到 deepseek-flash 一线。它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

STATE_NAME = "podcast-state.json"
SCRIPT_JSON = "script.json"
SCRIPT_MD = "script.md"
OUTLINE_JSON = "outline.json"
OUTLINE_MD = "outline.md"
VOICE_INDEX = "index.json"

# 退出码（可直接用于 CI）
EXIT_OK = 0            # 全部干净
EXIT_USAGE = 2         # 参数/配置/环境错误（缺 ffmpeg、--outdir 指到包内、没报价就开跑）
EXIT_GATE = 3          # 有硬闸门命中（合规 / 占位符 / 照抄示例 / 对话结构 / 时长）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名 / 音色 ID）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

# 平台计费口径：1 元 = 100 点（平台公开口径，1 点 = 0.01 元）。
# ⚠️ 这只是**换算**，不是单价。单价见下面三个实测常量与 SKILL.md。
POINTS_PER_YUAN = 100.0

# ---------------------------------------------------------------------------
# 实测单价（**只放我们真跑出来过的**，不搬平台 pricing_matrix / tenant_* 字段）
#
#   voice_tts/tts        50 点 / 千字   ← 6 组样本严格线性、无最低消费
#   music_generation     创建 65 点 / 次，歌词 12 点 / 次
#   voice_tts/stt        40 点 / 次（本包没用到，仅登记）
#
# 为什么把单价写成常量而不是现拉：平台 `GET /api/v1/pricing` 只覆盖少数接口，
# voice_tts / music_generation 都不在里面；`/api/v1/apps/<app>` 的 tenant_* 字段
# 实测半数与结算价不一致。所以**本包用实测常量做报价，用 usage.points_cost 做对账**：
# 每次调用后把真实扣点打出来，报价与实际不一致时会明确报出来（见 _report_spend）。
# ---------------------------------------------------------------------------

TTS_POINTS_PER_1K_CHARS = 50.0
MUSIC_POINTS_PER_CREATE = 65.0
MUSIC_POINTS_PER_LYRICS = 12.0
STT_POINTS_PER_CALL = 40.0        # 未使用，仅登记

# 同步配音接口的平台建议上限：schema 原文「同步接口建议不超过 500 字符」。
# 超过就拆块；超长（>5000 字）自动改用 tts_async，见 draft_voice_chunks / do_tts。
TTS_SYNC_MAX_CHARS = 500
TTS_ASYNC_MIN_CHARS = 5000

MUSIC_CUE_KEYS = ("intro", "bed", "outro")


# ---------------------------------------------------------------------------
# 节目规格表（**唯一事实来源**）
#
# 为什么做成表：语速、章节数、片头长度这些数字会变，而且提示词、闸门、
# 时长估算三处都要用同一个数。放一张表里，改口径只改这里，逻辑不动。
#
# 语速 265 字/分钟的依据：中文播客对白（不是朗读）实测落在 240~280 字/分钟，
# 取中位偏上。它同时是两条成本口径的来源，改它会同时改成本报价与时长闸门：
#   · 30 分钟 ≈ 7950 字（≈「一期 30 分钟约 8000 字」这条实测口径）
#   · 8000 字 × 50 点/千字 = 400 点 = 4 元
# 想按自己的节目节奏调就 `--chars-per-minute`。
# ---------------------------------------------------------------------------

SHOW = {
    "role_a": "主持人",
    "role_b": "嘉宾",
    "chars_per_minute": 265,
    "default_minutes": 30,
    "min_minutes": 5,
    "max_minutes": 90,
    "chapters": (3, 8),
    "min_turns_per_role": 3,
    "min_total_turns": 6,
    "duration_tolerance": 0.25,      # 与目标时长偏离超过 ±25% 拦
    "alternate_max_same": 0.20,      # 相邻同角色占比上限（超过就不是交替发言了）
}

# `--chars-per-minute` 的运行时覆盖位。为什么不直接改 SHOW：
# SHOW 是**口径表**（只读的事实来源），命令行覆盖是**本次运行的选择**；
# 两者混在同一个字典里，下一次调用的默认值就被悄悄改掉了。
_CPM = {"v": None}


def cpm():
    return float(_CPM["v"] or SHOW["chars_per_minute"])

# 片头 / 转场 / 片尾三个 cue 的口径。`seconds` 只用于**混音时裁剪**——
# `music_generation/create` 的参数表里**没有时长参数**（schema 现查确认），
# 生成多长由上游决定，所以长度控制放在 mix 里用 ffmpeg `-t` 做，见 build_playlist。
MUSIC_CUES = {
    "intro": {
        "label": "片头",
        "seconds": 15,
        "style": "轻快明亮的播客片头音乐，节奏有推进感，无人声，中频清晰不抢话",
        "prompt": "一段用于知识类播客开场的纯器乐片头，明亮、有推进感，最后两秒自然收进人声",
    },
    "bed": {
        "label": "转场",
        "seconds": 6,
        "style": "短促干净的转场配乐垫，无人声，情绪平缓不抢注意力",
        "prompt": "一段六秒左右的纯器乐转场垫乐，情绪平稳、干净，用来分隔播客的两个章节",
    },
    "outro": {
        "label": "片尾",
        "seconds": 20,
        "style": "温暖收束的播客片尾音乐，无人声，尾音自然衰减",
        "prompt": "一段用于播客结尾的纯器乐音乐，温暖、松弛，有收束感，尾音自然衰减",
    },
}


# ---------------------------------------------------------------------------
# 闸门一：合规自检（广告法违禁词 + 播客平台红线）
#
# 这是一道**粗筛**：宁可多报也别漏报，最终判断仍要人工复核，
# 且不等于任何平台的官方审核结论（官方标准不公开、会变）。
# 每项：正则 → 风险等级 → 人话解释 →（可选）语境判定标签
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    # 【比模板词表多三个词】`省` / `划算` / `实惠` 是播客口播里最常见的省钱类
    # 绝对化说法（「最省钱的一套流程」），而模板词表里有「便宜」却没有「省」。
    # 加词只会让闸门更严、不会放松任何一处判定；这次扩表如实登记在此。
    (r"最(好|佳|优|低|便宜|省|划算|实惠|快|强|大|高|先进|新|流行|受欢迎|顶级|厉害)",
     "高", "广告法第九条禁止「最高级」用语", "superlative"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    # 【口径选择，与 multiplat-rewrite 有意不同】multiplat 用的是裸 `第一(?!次)`，
    # 在本包里会把对白里的「第一、第二」「第一步」全判违规。播客是口语稿，
    # 枚举式表达是常态，误伤率太高（一次实测就被这条误拦了整篇）。
    # 所以这里取 course-outline 的**限定式**写法：只有「全国/行业/销量…第一」「第一品牌」
    # 「排名第一」这类**排他性宣称**才拦，裸的序数词放过。
    (r"(全国|全球|全网|行业|销量|口碑|人气)第一|第一(品牌|选择)|排名第一|"
     r"No\.?\s*1|TOP\s*1", "高", "「第一」类排他性表述"),
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
    (r"独家|唯一|首个|首创|填补空白|领先(品牌|技术)", "中",
     "排他性表述需有可举证依据"),
    (r"纯天然|无添加|零添加|无毒无害", "中",
     "成分/材质宣称需与检测报告一致"),
    (r"点击链接|加微信|私信我|扫码(加|进|领)|vx|VX|微信号|加V", "中",
     "站外导流，平台普遍限制"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看|赶紧转发", "中",
     "标题党式诱导"),
    (r"[！!]{2,}|[?？]{3,}", "低",
     "标点堆砌，易被判标题党/低质"),
]
BANNED_RE = []
for _t in BANNED_PATTERNS:
    BANNED_RE.append((re.compile(_t[0]), _t[1], _t[2],
                      _t[3] if len(_t) > 3 else None))
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}

# 播客平台特有的红线：**同一个表达在不同形态的内容里风险不一样**，所以单列一张表。
# 播客是长音频，口播里念出「加微信 / 私信我」比图文的违规概率更高（平台无法预审，
# 上线后被投诉即下架），所以站外导流按「中」而不是「低」处理。
# 这张表是**经验口径**，不是任何播客平台的官方审核标准。
SHOW_REDLINES = [
    (r"加微信|微信号|加V|vx|VX|私信我|加我好友|扫码加", "中",
     "口播站外导流，音频类平台普遍限制；确有必要请人工确认后再录"),
    (r"点赞|收藏|关注我|订阅(一下|本节目)|三连|打榜|投月票", "低",
     "诱导互动表述，部分平台会限流"),
    (r"付费(社群|群|专栏)|知识星球|会员群", "中",
     "二跳转化表述需与真实服务一致"),
]
SHOW_REDLINE_RE = [(re.compile(p), lvl, why) for p, lvl, why in SHOW_REDLINES]

# ---------------------------------------------------------------------------
# 「最高级」用语的语境豁免（**照抄本库已统一的判断逻辑**，这是被实测误伤逼出来的）
#
# 事故复盘：真实原稿改写后，公众号那篇的结尾写「回头翻一条自己播放量最低的视频」，
# 被本地闸门判成「命中高风险（广告法第九条禁止最高级用语）」并整篇拦截。
# 这个诊断是**错的**——「播放量最低的视频」是在描述自己的数据，
# 不是对商品/服务的绝对化宣称。错的不只是等级，是理由本身就不成立。
# 「宁可多报也别漏报」在这里代价过高：一个正确写法的稿子被判违规，
# 使用者就会开始无视闸门，闸门等于废了。
#
# 播客里这个误伤只会更多：对话稿天然会说「最贵的设备」「最常被问到的问题」。
# 豁免条件刻意做得很窄，只放过明确在说数据极值的形态：
#   · `最X` 前一个字是计量类名词（量/率/数/分/位/条/次/段/部/集/页/个/天/月/年）
#   · 且 `最X` 后面紧跟「的」或「之」
# 命中豁免时**整处放过**，但会在产出里登记下来（gates.compliance.exempted），
# 报告里会明说「本地放过了 N 处疑似绝对化用语」——**不静默放过**。
# 为什么不是「降级为低风险」：低风险在本包里同样拦截（与全库口径一致）。
#
# 豁免词表刻意**不含** `时`/`款`/`种`/`家`/`价`：
#   「课时最低的课程」「单价最低」都是真实的价格宣称形态，必须照拦。
# ---------------------------------------------------------------------------

MEASURE_PREFIX = "量率数分位条次段部集页个天月年"


def _is_data_extreme(text, m):
    start, end = m.start(), m.end()
    before = text[start - 1] if start > 0 else ""
    after = text[end:end + 1]
    # 注意 `before and`：空字符串在 Python 里 `"" in "量率数…"` 是 True，
    # 漏了这一步句首的「最好/最低」会被全部误豁免（这是写这段时自己踩到的坑）。
    return bool(before) and before in MEASURE_PREFIX and after in ("的", "之")


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
#
# 为什么单列一道闸门：选题稿常常是别人给的模板，模型会把 `{主题名}`
# `[待填]` 这类「编稿脚手架」原样留在产出里。这种稿子看起来是完整的，
# 录出来才发现有一半是空白——比明显报错更危险。
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
# 事故复盘（来自本库标题工坊的实测，两次）：
#   1. 提示词里写过正例 `结论先说：便携榨汁杯不适合三类人` → 模型直接产出
#      `结论先说：这类产品不适合三类人`
#   2. 提示词里留过 `便携榨汁杯不适合这三类人，理由有三个` → 那一轮**最高分 89.0**
#      的标题**一字不差就是它**
# 第 2 例性质更重：最高分那条是「抄了标准答案」，不是「真的最好」。
#
# 关键结论：**模型会照抄示例，哪怕那个示例标着「这是错的写法」。**
# 所以本包的提示词里不出现任何一句可直接复制的完整中文句子，
# 举例只用**跨主题**的描述性说明（「主持人抛出一个反直觉的数字」这种），
# 真实示例一律登记在 PROMPT_SAMPLES；万一以后有人又把示例加回提示词，这道闸门兜住。
# 本包另加一道**提示词卫生自检**（prompt_hygiene）：--dry-run 时直接检查
# 即将发送的提示词里有没有混进登记过的示例，混进去就报错，不等模型照抄。
#
# 判定：去标点后完全相等 → 命中；字符二元组 Jaccard ≥ ECHO_SIM → 命中；
#       示例的二元组覆盖度 ≥ ECHO_CONTAIN → 命中（第三条，见下）。
# 阈值标定依据（本库实测）：196 条正常产出与跨主题示例的最高相似度只有 0.174，
# 而「少两个字的同构照抄」是 0.765。0.75 既能兜住轻改写，离正常上限还有 4 倍余量。
# 长度守卫是**相对**的：目标归一化长度 < max(ECHO_MIN_LEN_FLOOR, len(示例)//2) 就不比，
# 因为短串的二元组集合太小、指标会虚高。
#
# 【为什么「整段 + 逐句」两层之外还要第三条】逐句比对的**比对单位是一句话**，
# 而拆句只在 。！？； 和换行处切（见 _SENT_SPLIT），**不在逗号处切**。
# 所以当模型把示例揉进自己那句话里（不在示例末尾断句）时，比对单位被撑到
# 30~36 字，Jaccard 照样被摊薄 —— 实测：
#   · 示例1 独立成句 → 逐句 Jaccard 1.000，抓住 ✓
#   · 示例1 揉进长句（36 字）→ 逐句 Jaccard 0.576，**漏**；覆盖度 1.000，抓住 ✓
# 也就是说逐句层只兜得住「示例自己独立成句」这一种形态，覆盖度不是冗余而是互补。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)

# 提示词 / 文档里出现过的示例文本（**跨主题**，正常不该被抄）。新增示例必须登记到这里。
# 主题刻意选「社区菜市场摊位租金」，与三剪客真实业务主题（内容创作 / 短剧 / 播客）明显不搭，
# 也和本包会产出的播客话题（AI、剪辑、创作）不搭——这样"命中"就一定是照抄，不是巧合。
PROMPT_SAMPLES = [
    "菜市场摊位租金这笔账，我记了三个月",
    "先说结论：摊位租金高不高，跟人流量不成正比",
    "我在菜市场摆了两年摊，租金这块踩过三个坑",
    "谈摊位之前没人告诉我，押金这一关才是最难的",
    "三组数字说明，社区菜市场的摊位没你想的贵",
]


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的文案往往只改标点（`，`↔`、`↔空格）或换行位置，
    所以必须先抹平标点与空白再看。
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
    """文本是否与提示词里登记过的示例「抄得太近」。

    三条命中路径（任一即命中）：
      · 去标点后**完全相同**（最直接的照抄）
      · 字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
      · 示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（把示例夹带进更长的句子里；
        Jaccard 会被长度摊薄，只有覆盖度抓得住，依据见常量区注释）

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


# 拆句：中文句末标点 + 换行。用于**逐句**比对提示词示例。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def split_sentences(text):
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def prompt_echo_scan(text, samples=None, label="正文"):
    """在一段长文本里找「照抄提示词示例」的地方。

    **为什么不能只比整段**：一期播客对话稿有 7000+ 字，而提示词示例只有二三十字。
    把整段稿子拿去和示例算 Jaccard，分母被撑到 7000 多，相似度永远接近 0——
    也就是说**模型把示例原样抄进某一句，这道闸门完全看不见**。
    而「抄示例」在长稿场景下恰恰就是「有几句是抄的」，不是整篇照抄。

    所以判定分两层：
      1. 整段比一次（兜住整篇照抄的极端情况），这一层**只认 exact / jaccard**：
         整段有 7000+ 字，覆盖度在这里只能告诉你"稿子里抄了一句"、指不出是哪一句
      2. **逐句比一次**（兜住「某一句是抄的」这个真实形态），含覆盖度判据
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
            why = ("稿子里的「{}」有 {:.0f}% 的内容来自提示词示例「{}」"
                   "（覆盖度 ≥ {:.2f} 即判照抄；Jaccard 会随句子变长被摊薄）"
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
#
# 事故复盘（写这个检查时踩到的）：直接把闸门二的 PLACEHOLDER_RE 拿来扫提示词，
# 结果本包自己的提示词被自己拦下了——因为提示词里为了说明输出结构写了
# `{no, title, gist, minutes, points[]}` 这种字段说明，命中了 `[{}]` 这条规则。
# 那是个**假阳性**：提示词里的花括号是 JSON 结构说明，不是没填干净的模板。
# 所以这里只认真正"该被替换掉却没替换"的形态：空花括号、待填字样、连续占位字母。
# 教训是通用的：一个为**产出**设计的检查，不能直接拿去扫**输入**。
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

    这是 prompt_echo 的前置防线。事后闸门（prompt_echo）只能拦"模型抄了"，
    拦不住"我们把示例写进了提示词"——而后者才是可避免的根因。
    """
    hits = []
    whole_hit, score, sample, rule = prompt_echo(prompt)
    if whole_hit and rule != "contain":
        hits.append({"sample": sample, "rule": rule, "sim": round(score, 3)})
    for seg in split_sentences(prompt):
        hit, score, sample, rule = prompt_echo(seg)
        if hit:
            hits.append({"sample": sample, "rule": rule, "sim": round(score, 3)})
            break
    # 提示词里出现可照抄的占位形态也算不卫生（模型会原样抄出来）
    for rx, why in PROMPT_DIRT_RE:
        m = rx.search(prompt or "")
        if m:
            hits.append({"prompt_dirt": m.group(0)[:20], "why": why})
            break
    return hits


# ---------------------------------------------------------------------------
# 闸门四：对话稿结构（本包**特有的核心形态闸门**）
#
# 为什么必须有：播客与"一篇文章"的分水岭就是**两个人在说话**。
# 一个单角色的稿子，配出来的音频只是"朗读"，不是播客——
# 它不会报错、时长也对、字数也对，发出去才发现形态不对。这正是
# "闸门要拦的不是错误，而是表面上完全正确的错误"。
#
# 【为什么不采信模型自报的结构字段】这是本库吃过的亏：标题工坊上一版只信模型
# 自报的 formula 字段，闸门成了假绿。所以这里**只读渲染后的稿子本身**：
# 用正则在成品 Markdown 上重新解析出角色与台词，解析不出角色标注的发言行
# 单独计数（unlabeled），非空即拦。哪怕模型 JSON 里写了 role 字段、
# 渲染也写了角色，只要成品稿里读不出两个角色标注，一样拦。
#
# 判定（全部命中才算过）：
#   · 台词行 ≥ min_total_turns（6）
#   · 角色**恰好 2 个**（--allow-multi-role 才放宽到 ≥2）
#   · 每个角色台词 ≥ min_turns_per_role（3）
#   · 相邻同角色占比 ≤ alternate_max_same（0.20）—— 这是"交替发言"的机器口径
#   · 没有"无角色标注的发言行"
# ---------------------------------------------------------------------------

# 成品稿里一句台词的形态：**角色**（语气）：台词
ROLE_LINE_RE = re.compile(
    r"^\*\*(?P<role>[^*\n]{1,12})\*\*(?:（(?P<tone>[^）\n]{0,24})）)?\s*[：:]\s*(?P<text>\S.*)$")

# 渲染稿里这些行不算"发言"：标题、引用（元信息）、表格、列表
_NON_TURN_PREFIX = ("#", ">", "|", "-", "*", "+")


def parse_script_md(md_text):
    """从成品 Markdown 里解析出角色发言，返回 (turns, unlabeled, headings)。"""
    turns, unlabeled, headings = [], [], []
    for raw in (md_text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            headings.append(s.lstrip("# ").strip())
            continue
        if s.startswith(">") or s.startswith("|") or s.startswith("- ") or s.startswith("* "):
            continue
        m = ROLE_LINE_RE.match(s)
        if m:
            turns.append({"role": m.group("role").strip(),
                          "tone": (m.group("tone") or "").strip(),
                          "text": m.group("text").strip()})
        else:
            unlabeled.append(s[:60])
    return turns, unlabeled, headings


def dialogue_gate(md_text, allow_multi_role=False):
    """闸门四：成品稿里是不是**真的**两个角色交替发言。"""
    turns, unlabeled, headings = parse_script_md(md_text)
    roles = []
    for t in turns:
        if t["role"] not in roles:
            roles.append(t["role"])
    per_role = {r: sum(1 for t in turns if t["role"] == r) for r in roles}
    same_adj = 0
    for i in range(1, len(turns)):
        if turns[i]["role"] == turns[i - 1]["role"]:
            same_adj += 1
    transitions = max(1, len(turns) - 1)
    same_ratio = same_adj / float(transitions)
    max_roles = 99 if allow_multi_role else 2

    problems = []
    if len(turns) < SHOW["min_total_turns"]:
        problems.append("成品稿里只解析出 %d 句带角色标注的台词（至少要 %d 句）"
                        % (len(turns), SHOW["min_total_turns"]))
    if len(roles) == 0:
        problems.append("整篇稿子**没有任何角色标注**（播客必须是对话形态，"
                        "每句要写成 `**角色**（语气）：台词`）")
    elif len(roles) == 1:
        problems.append("只有 **1 个角色**（%s）：这是朗读稿不是播客，"
                        "播客必须有两个人交替说话" % roles[0])
    elif len(roles) > max_roles:
        problems.append("出现了 %d 个角色（%s），本包默认只做双人对话；"
                        "确认要做多人对谈请加 --allow-multi-role"
                        % (len(roles), "、".join(roles)))
    for r, n in per_role.items():
        if n < SHOW["min_turns_per_role"]:
            problems.append("角色「%s」只有 %d 句台词（每人至少 %d 句），"
                            "配角化/独角戏都会被拦" % (r, n, SHOW["min_turns_per_role"]))
    if len(roles) >= 2 and same_ratio > SHOW["alternate_max_same"]:
        problems.append("相邻同角色占比 %.0f%%（上限 %.0f%%）：不是交替发言，"
                        "像是把两段独白拼在一起"
                        % (same_ratio * 100, SHOW["alternate_max_same"] * 100))
    if unlabeled:
        problems.append("有 %d 行**没有角色标注**的发言（例：「%s」）"
                        % (len(unlabeled), unlabeled[0]))

    return {
        "ok": not problems,
        "problems": problems,
        "turns": len(turns),
        "roles": roles,
        "turns_per_role": per_role,
        "same_speaker_ratio": round(same_ratio, 3),
        "unlabeled_lines": unlabeled[:5],
        "chapters": [h for h in headings if not h.startswith("第 0 期")][:20],
    }


# ---------------------------------------------------------------------------
# 闸门五：时长估算
#
# 播客是**按时长卖**的：一期标 30 分钟，实际 52 分钟，听众体感与平台推荐位都会错。
# 但脚本阶段拿不到真实音频时长，所以只能用字数估。口径写在 SHOW["chars_per_minute"]，
# 偏离超过 ±25% 就拦——这个容差是按"对白语速因人/因话题波动"定的，
# 不是拍脑袋：同一话题快慢两种讲法实测能差 15% 左右，25% 留了余量。
# 音频阶段的**真实时长**由 mix 报出来（timeline.md），两者不一致时人工看得到。
# ---------------------------------------------------------------------------

def duration_gate(chars, target_minutes, chars_per_minute=None):
    rate = float(chars_per_minute or cpm())
    est = chars / rate if rate else 0.0
    tol = SHOW["duration_tolerance"]
    lo, hi = target_minutes * (1 - tol), target_minutes * (1 + tol)
    return {
        "ok": lo <= est <= hi,
        "chars": chars,
        "chars_per_minute": rate,
        "est_minutes": round(est, 1),
        "target_minutes": target_minutes,
        "accept_minutes": [round(lo, 1), round(hi, 1)],
        "delta_minutes": round(est - target_minutes, 1),
        "why": ("按 %d 字/分钟估，约 %.1f 分钟；目标 %.1f 分钟，"
                "容差 %.0f%%（%.1f~%.1f 分钟）"
                % (rate, est, target_minutes, tol * 100, lo, hi)),
    }


# ---------------------------------------------------------------------------
# 闸门六：成本前置（报价 → --yes / --budget → 累计对账）
#
# 为什么报价与预算是**两道**而不是一道：
#   · 没有报价就开跑 = 用户不知道要花多少，被动扣费；
#   · 有报价没预算 = 报价算漏了（稿子比预期长）就会一路花下去。
# 所以口径是：跑前必须报价，且**要么 --yes 明确同意，要么 --budget 封顶**。
# 两个都没有 → exit=2（参数错误），一分钱都不花。
# 累计对账用**真实 usage.points_cost**，不是报价值；超了立刻停。
# ---------------------------------------------------------------------------

def quote_voice(chars, points_per_1k=None):
    rate = float(points_per_1k or TTS_POINTS_PER_1K_CHARS)
    pts = chars / 1000.0 * rate
    return {"item": "配音 voice_tts/tts", "chars": chars,
            "points_per_1k_chars": rate, "points": round(pts, 2),
            "yuan": round(pts / POINTS_PER_YUAN, 4)}


def quote_music(cues, with_lyrics=False):
    n = len(cues)
    pts = n * MUSIC_POINTS_PER_CREATE
    items = [{"item": "配乐 music_generation/create:%s" % c, "points": MUSIC_POINTS_PER_CREATE}
             for c in cues]
    if with_lyrics:
        pts += n * MUSIC_POINTS_PER_LYRICS
        items.append({"item": "歌词 music_generation/lyrics", "points": MUSIC_POINTS_PER_LYRICS})
    return {"item": "配乐", "cues": list(cues), "items": items,
            "points": round(pts, 2), "yuan": round(pts / POINTS_PER_YUAN, 4)}


def money(points):
    return None if points is None else round(points / POINTS_PER_YUAN, 4)


def points_of(res):
    """把**实际扣点**抓出来。

    结算只认 `usage.points_cost`（平台的 pricing_matrix / tenant_* 字段半数不可信）。
    同步接口见过 `actual_points`，异步任务见过 `points_cost`，两个位置都试：
    任务顶层（本包的 a7w.call 把 task 顶层的 usage 拿回来了）与 result 里。
    """
    for holder in (a7w.dig(res, "usage"), res, a7w.dig(res, "result", "usage"),
                   a7w.dig(res, "result")):
        if not isinstance(holder, dict):
            continue
        for k in ("points_cost", "actual_points", "points", "cost"):
            v = holder.get(k)
            if isinstance(v, (int, float)):
                return float(v)
    return None


def pick_url(result, *names):
    """在任务结果里找产物地址——图片/视频/音频的返回结构不一致，逐个试。"""
    if isinstance(result, dict):
        for name in names:
            v = a7w.dig(result, "data", name) or a7w.dig(result, name)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for seq_key in ("data", "results", "outputs", "audios", "musics"):
            seq = a7w.dig(result, seq_key)
            if isinstance(seq, list) and seq:
                first = seq[0]
                if isinstance(first, str) and first.startswith("http"):
                    return first
                if isinstance(first, dict):
                    found = pick_url(first, *names)
                    if found:
                        return found
            if isinstance(seq, dict):
                found = pick_url(seq, *names)
                if found:
                    return found
    elif isinstance(result, str) and result.startswith("http"):
        return result
    return None


# ---------------------------------------------------------------------------
# 文本工具
# ---------------------------------------------------------------------------

def count_chars(s):
    """正文字数：非空白字符数（含中文标点）。"""
    return len(re.sub(r"\s", "", s or ""))


def count_lines(s):
    return len([x for x in (s or "").splitlines() if x.strip()])


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class PodcastError(a7w.A7wError):
    """生产 / 生成 / 调用失败（网络、鉴权、点数、模型名、音色）。→ 退出码 4"""


class UsageError(PodcastError):
    """参数/配置/环境用错了。→ 退出码 2

    为什么要跟 PodcastError 分开：这两类错误的**处理方式完全不同**。
    参数错了要改命令重跑，不花一分钱（比如 --outdir 指到包内、没报价就开跑）；
    调用失败要查 Key / 点数 / 模型名。混成一个退出码，CI 里就没法区分。
    """


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=4096, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见。
    一期播客的对话稿是一个几千字的长产出，被一次抖动打断要重跑整篇，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。

    成功响应**不带 `code` 字段**（实测），所以这里不判 code；只判 choices 在不在。
    `code == 1` 那套信封是**生成应用**（voice_tts / music_generation）的，不适用于本端点。
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
                raise PodcastError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise PodcastError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise PodcastError(
                    "模型不存在（404）：{}  用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 429，{}s 后重试…\n".format(3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise PodcastError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise PodcastError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    if payload is None:
        raise PodcastError("网络错误：{}".format(last_exc))

    # 兜底：万一网关换了形态包了一层 {"code":1,"data":{...}}，两种都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise PodcastError("模型没返回 choices：{}".format(
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
        raise PodcastError("模型返回空内容")
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
    raise PodcastError("模型返回的不是合法 JSON：{}".format(
        text[:300].replace("\n", " ")))


# ---------------------------------------------------------------------------
# 生成应用调用（配音 / 配乐）——code == 1 才是成功
# ---------------------------------------------------------------------------

def _call_app(app, api, body, key, wait=True, timeout=1800):
    """调一个生成应用接口。

    `a7w.call` 内部走 `_unwrap`：`code` 不在 (1, 200, None) 里就抛 A7wError。
    **生成应用的成功码是 1**（不是 0、也不是"没有 code"）。所以这里不用再判一遍，
    但错误信息要带上 app/api，否则用户看不出来是哪一步炸的。

    异步任务的状态在**任务 data 顶层**（`data.status`），不在 `data.result.status`——
    平台文档把这一条写错了，客户端读的是 `data.status`，实测正确。
    """
    try:
        return a7w.call(app, api, body, key=key, wait=wait, timeout=timeout)
    except a7w.A7wError as exc:
        raise PodcastError("{} {} 调用失败：{}".format(app, api, exc))


def do_tts(key, text, reference_id=None, fmt="mp3", model="s2-pro",
           speed=None, timeout=1800):
    """配音：短文本走同步 `voice_tts/tts`，超长走异步 `voice_tts/tts_async`。

    **实测参数名**：音色是 `reference_id`（值是 list_voices 的 model_id），
    **不是 `voice_id`**——本包开工前用 `python scripts/a7w.py schema voice_tts` 现查确认。
    同步接口 schema 原文「建议不超过 500 字符」，所以这里按 TTS_SYNC_MAX_CHARS 分块；
    单块超过 TTS_ASYNC_MIN_CHARS 才切异步端点（异步支持约 10000 字符）。
    """
    body = {"text": text, "model": model, "format": fmt}
    if reference_id:
        body["reference_id"] = reference_id
    if speed:
        body["prosody"] = {"speed": speed}
    api = "tts_async" if len(text) > TTS_ASYNC_MIN_CHARS else "tts"
    try:
        return _call_app(APP_VOICE, api, body, key, wait=True, timeout=timeout)
    except PodcastError as exc:
        if reference_id and "任务处理失败" in str(exc):
            raise PodcastError(
                "%s\n  排查：这条错误最常见的成因是 **reference_id 不完整或不存在**——"
                "list_voices 返回的 id 是 32 位十六进制，抄短了就会得到这句"
                "「任务处理失败」。用 `run.py voices` 重新整条复制；"
                "去掉 --voice-a/--voice-b（不指定音色）可以立刻区分是音色问题还是文本问题。"
                % exc)
        raise


def do_music(key, style=None, prompt=None, title=None, lyric=None,
             instrumental=True, timeout=1800):
    """配乐：POST /api/v1/apps/music_generation/create。

    **实测动作名是 `create`，不是 `generate`**（本包开工前用
    `python scripts/a7w.py schema music_generation` 现查确认；接口代码里没有 `generate`，
    `generate` 只是 `type` 参数的一个取值）。
    长度参数在这个接口的参数表里**不存在**，所以片头/转场/片尾的长度控制在 mix 阶段做。
    """
    body = {"type": "generate", "instrumental": bool(instrumental)}
    if title:
        body["title"] = title[:80]                 # schema：常规模型最多 80 字符
    if style:
        body["style"] = style[:200]                # schema：常规模型最多 200 字符
    if lyric:
        body["custom"] = True
        body["lyric"] = lyric[:3000]               # schema：常规模型最多 3000 字符
    if prompt:
        body["prompt"] = prompt[:500]              # schema：灵感模式不超过 500 个字符
    return _call_app(APP_MUSIC, "create", body, key, wait=True, timeout=timeout)


def do_lyrics(key, prompt, timeout=300):
    """歌词：POST /api/v1/apps/music_generation/lyrics（同步，12 点/次）。"""
    return _call_app(APP_MUSIC, "lyrics", {"prompt": prompt}, key, wait=True, timeout=timeout)


def list_voices(key, tag=None, title=None, page_size=20, page_number=1):
    """POST /api/v1/apps/voice_tts/list_voices → 音色列表（同步，不扣点）。"""
    body = {"page_size": page_size, "page_number": page_number}
    if tag:
        body["tag"] = tag
    if title:
        body["title"] = title
    res = _call_app(APP_VOICE, "list_voices", body, key, wait=True, timeout=120)
    result = res.get("result") if isinstance(res, dict) else None
    lst = None
    for holder in (result, res):
        if isinstance(holder, dict):
            for k in ("data", "list", "voices", "items"):
                v = holder.get(k)
                if isinstance(v, list):
                    lst = v
                    break
        if lst is not None:
            break
    if lst is None and isinstance(result, list):
        lst = result
    return lst or []


def voice_id_of(item):
    """从音色条目里取 reference_id。字段名上游给过 model_id / id / reference_id 三种。"""
    for k in ("reference_id", "model_id", "id"):
        v = a7w.dig(item, k)
        if v:
            return str(v)
    return None


def first_voice_ids(key, want=2):
    """取前 N 个可用音色（看不上就用 --voice-a / --voice-b 手动指定）。"""
    lst = list_voices(key, page_size=max(want * 3, 10))
    ids = []
    for it in lst:
        vid = voice_id_of(it)
        if vid and vid not in ids:
            ids.append(vid)
        if len(ids) >= want:
            break
    return ids, lst


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _red(s, force_plain=False):
    """命中标红。终端支持 ANSI 就打红色，否则用醒目前缀。"""
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "✗ " + s
    return "\x1b[31m%s\x1b[0m" % s


def fmt_mmss(seconds):
    seconds = int(round(max(0.0, float(seconds))))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))


def fmt_minutes(m):
    if not m:
        return "未知"
    if m < 60:
        return "%d 分钟" % round(m)
    return "%d 小时 %d 分" % (int(m // 60), int(round(m % 60)))


def render_outline_md(plan, model=None, usage=None, elapsed=None, minutes=None):
    out = ["# 选题与提纲 · %s" % plan.get("title") or "", ""]
    if plan.get("subtitle"):
        out.append("- 副标题：%s" % plan["subtitle"])
    if plan.get("angle"):
        out.append("- 切入角度：%s" % plan["angle"])
    if plan.get("audience"):
        out.append("- 目标听众：%s" % plan["audience"])
    if minutes:
        out.append("- 目标时长：%s" % fmt_minutes(minutes))
    if plan.get("hook"):
        out.append("- 片头钩子：%s" % plan["hook"])
    if model:
        out.append("- 模型：`%s`　命令端点：`POST /api/v1/chat/completions`" % model)
    if usage:
        out.append("- token 用量：prompt=%s completion=%s total=%s" % (
            usage.get("prompt_tokens", "-"), usage.get("completion_tokens", "-"),
            usage.get("total_tokens", "-")))
    if elapsed is not None:
        out.append("- 耗时：%.1fs" % elapsed)
    out.append("")
    out.append("| 章 | 标题 | 时长 | 本章要点 |")
    out.append("|---|---|---|---|")
    for c in plan.get("chapters") or []:
        pts = "<br>".join("· " + p for p in (c.get("points") or [])) or "（缺）"
        out.append("| %s | %s | %s | %s |" % (
            c.get("no"), c.get("title") or "（缺标题）",
            fmt_minutes(c.get("minutes") or 0), pts))
    out.append("")
    if plan.get("outro"):
        out.append("> 片尾收束：%s" % plan["outro"])
        out.append("")
    return "\n".join(out)


def render_script_md(script, meta=None):
    """把对话稿渲染成**成品 Markdown**。

    这个渲染结果不是给人看的副产品——闸门四、闸门三读的就是它。
    改这里的格式等于改闸门的输入，必须同步改 ROLE_LINE_RE。
    """
    meta = meta or {}
    out = ["# %s" % (script.get("title") or "未命名"),
           ""]
    if meta.get("subtitle"):
        out.append("> 副标题：%s" % meta["subtitle"])
    out.append("> 角色：%s" % "、".join(meta.get("roles") or []) )
    if meta.get("minutes"):
        out.append("> 目标时长：%s（按 %d 字/分钟估）"
                   % (fmt_minutes(meta["minutes"]), cpm()))
    out.append("")
    for c in script.get("chapters") or []:
        out.append("## 第 %s 章　%s" % (c.get("no"), c.get("title") or ""))
        out.append("")
        if c.get("gist"):
            out.append("> 本章主线：%s" % c["gist"])
            out.append("")
        for ln in c.get("lines") or []:
            tone = ("（%s）" % ln["tone"]) if ln.get("tone") else ""
            out.append("**%s**%s：%s" % (ln.get("role"), tone, ln.get("text")))
            out.append("")
    return "\n".join(out)


def render_timeline_md(rows, total_seconds, meta=None):
    meta = meta or {}
    out = ["# 章节时间轴", ""]
    if meta.get("title"):
        out.append("- 节目：%s" % meta["title"])
    out.append("- 总时长：%s（%d 秒）" % (fmt_mmss(total_seconds), round(total_seconds)))
    out.append("- 生成方式：本地 ffmpeg 拼接后按每段真实时长累加（不估算）")
    out.append("")
    out.append("| 起点 | 终点 | 时长 | 内容 | 类型 |")
    out.append("|---|---|---|---|---|")
    for r in rows:
        out.append("| %s | %s | %s | %s | %s |" % (
            fmt_mmss(r["start"]), fmt_mmss(r["end"]),
            fmt_mmss(r["end"] - r["start"]), r["label"], r["kind"]))
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 提示词构造
#
# 【铁律】提示词里**不许出现任何一句可直接复制的完整中文句子**。
# 举例只用描述性说明（「主持人抛出一个反直觉的数字」），
# 真实示例一律登记在 PROMPT_SAMPLES，并由 prompt_hygiene() 在 --dry-run 时自检。
# 依据见上面 prompt_echo 的事故复盘：模型会照抄示例，哪怕标着"这是错的写法"。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是三剪客的播客制作人，做过大量中文双人对话播客。"
    "你只输出 JSON，不输出任何解释、前言、Markdown 代码块围栏之外的文字。"
    "你写的东西必须是**可以直接照读的口语对白**，不是文章。"
    "禁止编造具体的人名、机构名、论文名、基金名、真实数据；"
    "需要举例时只能用可核查的泛指表述，不许指名具体的人、机构、论文。"
    "禁止使用广告法违禁的最高级用语与效果承诺。"
)


def _role_block(role_a, role_b):
    return (
        "本期是双人对话播客，两个角色固定：\n"
        "  · 「%s」——负责推进：铺垫背景、提出疑问、把跑偏的话题拉回来、做小结\n"
        "  · 「%s」——负责内容：给出判断、解释原因、举可核查的例子、承认不确定性\n"
        "对白要求（这几条会被本地闸门逐条检查）：\n"
        "  · 每一句都必须标出说话人，且**两个角色交替出现**，不许一个人连说一大段\n"
        "  · 每个人至少 3 句；不许出现第三个说话人、也不许有旁白\n"
        "  · 每句都自带语气标注（一个词或一个短语，例如平稳/加快/笑着/停顿一下）\n"
        "  · 句子是口语：可以有短句、追问、自我纠正，不要写成书面长句\n"
        "  · 不许出现变量占位符（成对花括号、方括号里留空、连续大写占位字母）\n"
        % (role_a, role_b)
    )


def _outline_spec_block(minutes, chapters_hint):
    return (
        "节目规格：\n"
        "  · 目标时长 %d 分钟（按 %d 字/分钟折算，正文对白合计约 %d 字）\n"
        "  · 章节数 %d~%d 个，每章标出预计分钟数与 2~4 条本章要点\n"
        "  · 章节之间要有递进：前一章留下的问题由后一章回答，不要并列罗列\n"
        "  · 片头钩子要具体：直接说清听众听完能拿到什么，不许只报节目名再寒暄\n"
        "  · 片尾收束要给出一个能被单独转述的结论，不许只是道别收场\n"
        % (minutes, cpm(), int(minutes * cpm()),
           chapters_hint[0], chapters_hint[1])
    )


def build_outline_prompt(topic, minutes, brief=None, audience=None):
    parts = [
        "请为下面这个主题设计一期播客的选题与提纲。",
        "",
        "主题：%s" % topic,
    ]
    if audience:
        parts.append("目标听众：%s" % audience)
    if brief:
        parts.append("额外要求：%s" % brief)
    parts += ["", _outline_spec_block(minutes, SHOW["chapters"]), "",
              "输出 JSON 对象，字段：",
              '  title      字符串，节目标题，18~30 字，一眼看出讲什么、给谁听',
              '  subtitle   字符串，一句副标题，可空',
              '  angle     字符串，切入角度：为什么这个话题值得现在讲',
              '  audience  字符串，目标听众画像',
              '  hook      字符串，片头钩子，1~2 句口语',
              '  chapters  数组，每项 {no, title, gist, minutes, points[]}',
              '            points 是 2~4 条本章要点，每条一句短语',
              '  outro     字符串，片尾收束，1~2 句口语',
              "",
              "再次强调：只输出这个 JSON 对象。"]
    return "\n".join(parts)


def build_script_prompt(plan, minutes, role_a, role_b, brief=None):
    """拼对话稿提示词。

    【逐章字数配额是实测逼出来的，不是设计洁癖】
    第一版只在末尾写了一句「合计约 2120 字」。实测模型按 4 章只写了 1035 字
    （每条台词 36 字左右，条数也只给了 29 条），被时长闸门拦下——闸门拦得对，
    但这次调用白花了，而且用户拿到的是"重跑一次吧"。
    第二版把配额挂到每一章那一行后面，模型仍然没对齐（只到 3.9 分钟）。
    第三版改成**独立的逐章配额块**，并且把配额换算成模型能直接对齐的
    「本章约 X 字 / 不少于 N 条台词」（N 按实测每条台词约 40 字折算），
    实测一轮就把总字数打到闸门区间内。
    结论：给模型的约束要**落在它能逐项对齐的粒度上**，写在括号里的总目标它不当回事。
    """
    outline_lines = []
    for c in plan.get("chapters") or []:
        pts = "；".join(c.get("points") or [])
        outline_lines.append("  第 %s 章《%s》｜主线：%s｜要点：%s"
                             % (c.get("no"), c.get("title"),
                                c.get("gist") or "-", pts or "-"))
    target_chars = int(minutes * cpm())
    tot_min = sum(float(c.get("minutes") or 0) for c in plan.get("chapters") or [])
    n_ch = max(1, len(plan.get("chapters") or []))
    quota_lines = []
    for c in plan.get("chapters") or []:
        m = float(c.get("minutes") or 0) or (minutes / float(n_ch))
        share = (m / tot_min) if tot_min else (1.0 / n_ch)
        q = int(round(target_chars * share * 1.08))       # 宁多不少：多了只是稍长
        n = max(6, int(round(q / 40.0)))                  # 实测每条台词约 40 字
        quota_lines.append("  第 %s 章：本章对白不少于 %d 字，不少于 %d 条台词"
                           % (c.get("no"), q, n))
    parts = [
        "请按下面这份提纲，写出这一期播客的**完整双人对话稿**。",
        "",
        "节目标题：%s" % (plan.get("title") or ""),
        "切入角度：%s" % (plan.get("angle") or "-"),
        "片头钩子：%s" % (plan.get("hook") or "-"),
        "片尾收束：%s" % (plan.get("outro") or "-"),
    ]
    if brief:
        parts.append("额外要求：%s" % brief)
    parts += [
        "",
        "提纲：",
    ] + outline_lines + [
        "",
        "篇幅配额（这是硬指标，本地闸门会按总字数估算时长并核对）：",
    ] + quota_lines + [
        "  合计不少于 %d 字。" % int(target_chars * 0.95),
        "",
        _role_block(role_a, role_b),
        "输出 JSON 对象，字段：",
        '  title     字符串，与上面标题一致',
        '  chapters  数组，顺序与提纲一致，每项 {no, title, gist, lines[]}',
        '            lines 是数组，每项 {role, text, tone}',
        '              role 只能是「%s」或「%s」' % (role_a, role_b),
        '              text 是要照读的台词，一条 40~90 字、一到三句，口语',
        '              tone 是语气标注，一个词或一个短语',
        "",
        "再次强调：逐章配额是硬指标，写不够本地闸门会拦；不许用省略标记代替正文。",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 产出归一化
# ---------------------------------------------------------------------------

def normalize_outline(raw, minutes):
    """把模型返回的提纲收拾成内部结构（缺项如实登记，不偷偷补）。"""
    plan = {
        "title": str((raw or {}).get("title") or "").strip(),
        "subtitle": str((raw or {}).get("subtitle") or "").strip(),
        "angle": str((raw or {}).get("angle") or "").strip(),
        "audience": str((raw or {}).get("audience") or "").strip(),
        "hook": str((raw or {}).get("hook") or "").strip(),
        "outro": str((raw or {}).get("outro") or "").strip(),
        "chapters": [],
    }
    chapters = (raw or {}).get("chapters") or []
    if not isinstance(chapters, list):
        chapters = []
    for i, c in enumerate(chapters, 1):
        if not isinstance(c, dict):
            continue
        pts = c.get("points") or []
        if not isinstance(pts, list):
            pts = [str(pts)]
        try:
            ch_min = float(c.get("minutes") or 0)
        except (TypeError, ValueError):
            ch_min = 0.0
        plan["chapters"].append({
            "no": c.get("no") or i,
            "title": str(c.get("title") or "").strip(),
            "gist": str(c.get("gist") or "").strip(),
            "minutes": round(ch_min, 1),
            "points": [str(p).strip() for p in pts if str(p).strip()],
        })
    if not plan["chapters"]:
        raise PodcastError("模型返回的提纲里没有 chapters，重跑一次或换个模型")
    # 章节时长缺失就按目标时长均分——**如实登记**这件事，不假装模型给了
    plan["minutes_filled"] = False
    if sum(c["minutes"] for c in plan["chapters"]) <= 0:
        each = round(minutes / float(len(plan["chapters"])), 1)
        for c in plan["chapters"]:
            c["minutes"] = each
        plan["minutes_filled"] = True
    return plan


def normalize_script(raw, plan, role_a, role_b):
    """把模型返回的对话稿收拾成内部结构。"""
    chapters = (raw or {}).get("chapters") or []
    if not isinstance(chapters, list):
        chapters = []
    out = []
    for i, c in enumerate(chapters, 1):
        if not isinstance(c, dict):
            continue
        lines = []
        for ln in (c.get("lines") or []):
            if not isinstance(ln, dict):
                continue
            text = str(ln.get("text") or "").strip()
            role = str(ln.get("role") or "").strip()
            if not text:
                continue
            if not role:
                role = ""
            lines.append({"role": role, "text": text,
                          "tone": str(ln.get("tone") or "").strip()})
        out.append({"no": c.get("no") or i,
                    "title": str(c.get("title") or "").strip(),
                    "gist": str(c.get("gist") or "").strip(),
                    "lines": lines})
    if not out:
        raise PodcastError("模型返回的对话稿里没有 chapters")
    return {
        "title": str((raw or {}).get("title") or plan.get("title") or "").strip(),
        "chapters": out,
        "role_a": role_a,
        "role_b": role_b,
    }


def script_chars(script):
    return sum(count_chars(ln["text"])
               for c in script.get("chapters") or []
               for ln in c.get("lines") or [])


# ---------------------------------------------------------------------------
# 闸门执行：对一份对话稿跑全部本地检查
# ---------------------------------------------------------------------------

def compliance_scan(text, show_redlines=True):
    """扫违禁词 + 播客平台红线。

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
        hits.append({"word": m.group(0), "level": lvl, "why": why, "scope": "广告法"})
    if show_redlines:
        for rx, lvl, why in SHOW_REDLINE_RE:
            m = rx.search(text)
            if m:
                hits.append({"word": m.group(0), "level": lvl, "why": why,
                             "scope": "播客口播红线"})
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


def gate_script(script, md_text, target_minutes, allow_multi_role=False):
    """对一份成品对话稿跑闸门一~五。闸门六（成本）在调用方单独管。"""
    scan = compliance_scan(md_text)
    ph = placeholder_scan(md_text)
    echoes = prompt_echo_scan(md_text, label="对话稿")
    dlg = dialogue_gate(md_text, allow_multi_role=allow_multi_role)
    chars = script_chars(script)
    dur = duration_gate(chars, target_minutes)
    g = {
        "compliance": {"ok": not scan["hits"], "hits": scan["hits"],
                       "exempted": scan["exempted"]},
        "placeholder": {"ok": not ph, "hits": ph},
        "prompt_echo": {"ok": not echoes, "hits": echoes},
        "dialogue": dlg,
        "duration": dur,
    }
    g["ok"] = all(g[k]["ok"] for k in
                  ("compliance", "placeholder", "prompt_echo", "dialogue", "duration"))
    return g


def _gate_report(g, show_name=""):
    """把命中汇总到 stderr，并返回退出码。命中即退出码 3。"""
    if g["ok"]:
        ex = g["compliance"].get("exempted") or []
        if ex:
            sys.stderr.write("\n提示：本地放过 %d 处疑似绝对化用语（判定为「在说数据极值」"
                             "而不是商品宣称）。这是启发式判断，请人工确认：\n" % len(ex))
            for e in ex:
                sys.stderr.write("   「%s」：…%s…\n" % (e["word"], e["context"]))
        return EXIT_OK
    sys.stderr.write("\n")
    sys.stderr.write(_red("!! 对话稿被硬闸门拦下，不可直接录制/发布%s\n"
                          % (("（%s）" % show_name) if show_name else "")) + "\n")
    if not g["compliance"]["ok"]:
        sys.stderr.write("   [合规] " + "、".join(
            "「%s」(%s/%s：%s)" % (h["word"], h["level"], h["scope"], h["why"])
            for h in g["compliance"]["hits"]) + "\n")
    if not g["placeholder"]["ok"]:
        sys.stderr.write("   [占位符] " + "；".join(
            h["why"] for h in g["placeholder"]["hits"]) + "\n")
    if not g["prompt_echo"]["ok"]:
        sys.stderr.write("   [照抄示例] " + "；".join(
            h["why"] for h in g["prompt_echo"]["hits"]) + "\n")
    if not g["dialogue"]["ok"]:
        for p in g["dialogue"]["problems"]:
            sys.stderr.write("   [对话结构] %s\n" % p)
    if not g["duration"]["ok"]:
        d = g["duration"]
        sys.stderr.write("   [时长] %s（偏离目标 %+.1f 分钟）\n"
                         % (d["why"], d["delta_minutes"]))
    sys.stderr.write("\n   人读结果见标准输出；机器读用 --json。\n")
    return EXIT_GATE


# ---------------------------------------------------------------------------
# 产出目录与断点续跑
# ---------------------------------------------------------------------------

AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".pcm")


def _resolve(p):
    return Path(p).expanduser().resolve()


def check_outdir(outdir):
    """`--outdir` 不许指到包内。

    **为什么这条是硬闸门而不是提醒**：本库的包要过 SkillHub 的文件类型白名单，
    包内出现任何 mp3 / wav / 中间 wav 都会让整个包 400。产出音频本来就不该进包，
    所以这里**拒绝执行**（exit=2），不是"警告后继续"。
    """
    p = _resolve(outdir)
    try:
        p.relative_to(PKG_ROOT)
    except ValueError:
        return p
    raise UsageError(
        "拒绝执行：--outdir 指到了包内（%s）。\n"
        "  产出音频与混音中间件**一律不许进包**（包内只允许 %s）。\n"
        "  请换到包外目录，例如 %%TEMP%%\\podcast 或 D:/podcast/ep01。"
        % (p, " / ".join(sorted({'.md', '.py', '.txt', '.json', '.sh', '.js',
                                 '.yaml', '.yml', '.csv'}))))


def refuse_audio_in_pkg(path):
    """产出文件路径的兜底检查：音频后缀 + 落在包内 = 拒绝。"""
    p = _resolve(path)
    try:
        p.relative_to(PKG_ROOT)
    except ValueError:
        return p
    if str(p).lower().endswith(AUDIO_EXT):
        raise UsageError("拒绝执行：产出音频路径落在包内（%s）" % p)
    return p


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


def text_hash(s):
    """片段指纹：用标准库 hashlib（不引第三方）。"""
    import hashlib
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 配音分块
# ---------------------------------------------------------------------------

def split_long_text(text, limit=TTS_SYNC_MAX_CHARS):
    """把一段长文本按句末标点切成不超过 limit 的块。

    为什么要切：同步 TTS 的 schema 原文是「建议不超过 500 字符」，
    超了上游会截断或报错——而"被截断"是最坏的情况：音频少一句但看不出错。
    """
    out, cur = [], ""
    for sent in split_sentences(text):
        if cur and len(cur) + len(sent) > limit:
            out.append(cur)
            cur = ""
        while len(sent) > limit:                 # 单句超长（少见）：硬切
            out.append(sent[:limit])
            sent = sent[limit:]
        cur += sent
    if cur:
        out.append(cur)
    return out or [text[:limit]]


def draft_voice_chunks(script, sample_chars=0):
    """把对话稿切成配音片段。

    切法：**同一章节内、同一角色的连续台词合成一块**（≤500 字）。
    为什么不每句一块：实测配音无最低消费（50 点/千字严格线性），
    合并不会多花钱，但能把调用次数从几百次压到几十次——
    调用次数直接决定失败率与重试成本。
    """
    chunks, used = [], 0
    for c in script.get("chapters") or []:
        cur = None
        for ln in c.get("lines") or []:
            text = (ln.get("text") or "").strip()
            role = (ln.get("role") or "").strip()
            if not text or not role:
                continue
            if sample_chars and used >= sample_chars:
                break
            if sample_chars and used + len(text) > sample_chars:
                text = text[:max(0, sample_chars - used)]
            if not text:
                break
            used += len(text)
            if cur and cur["role"] == role and \
                    len(cur["text"]) + len(text) <= TTS_SYNC_MAX_CHARS:
                cur["text"] += text
                cur["lines"] += 1
                continue
            cur = {"chapter": c.get("no"), "chapter_title": c.get("title"),
                   "role": role, "text": text, "lines": 1}
            chunks.append(cur)
        if sample_chars and used >= sample_chars:
            break
    # 逐块再按 500 字硬上限拆开
    final = []
    for ch in chunks:
        for i, piece in enumerate(split_long_text(ch["text"])):
            final.append({"chapter": ch["chapter"], "chapter_title": ch["chapter_title"],
                          "role": ch["role"], "text": piece,
                          "part": i + 1})
    for i, ch in enumerate(final, 1):
        ch["order"] = i
        ch["chars"] = len(ch["text"])
        ch["key"] = "voice:%03d" % i
        ch["hash"] = text_hash(ch["text"] + "|" + ch["role"])
    return final


def safe_name(s):
    return re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", (s or "").strip())[:24] or "x"


# ---------------------------------------------------------------------------
# JSON 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封（已经吐过结果的，ok 写在那个结果里）
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符都不变
#   · `--json` 写在子命令**前后都认**（见 _add_json 的注释）
#
# 信封必须落在**真 stdout**：JSON 文本统一经 `_json_write` 写。
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

    只写 stdout（真 stdout）；完整 traceback 由 main() 的兜底层原样打到 stderr。
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
    if _JSON["reason"] is None:
        _JSON["reason"] = {"kind": kind, "message": message, "detail": detail}
    return rc


# `all` 会复用各子命令的处理函数，而那些函数各自会 `_emit` 一次 —— 于是
# `run.py all --json` 会把 5 个 JSON 文档连着吐到 stdout，**破了"stdout 只有一个
# JSON"这条不变量**（实测：json.loads 报 `Extra data: line 61`）。
# 这个收集位让 `all` 把子步骤的产出收进内存，最后合并成一份再吐。
_EMIT = {"collect": None}


def _emit(a, result, md_text, ok=True):
    """统一出口：`--json` 时补 ok 写**真 stdout**（同时落 `--out`），否则原样打人读文本。

    `_EMIT["collect"]` 不是 None 时只收集、不输出（`all` 用）。
    """
    if _EMIT["collect"] is not None:
        _EMIT["collect"].append({"result": result, "md": md_text, "ok": ok})
        return
    if a.json:
        body = _json_text(result, indent=2, ok=ok)
        if a.out:
            Path(a.out).write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 %s\n" % a.out)
        _json_write(body)
        return
    if a.out:
        Path(a.out).write_text(md_text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 %s\n" % a.out)
    print(md_text)


# ---------------------------------------------------------------------------
# 子命令的公共部分
# ---------------------------------------------------------------------------

def _read_outline(a):
    p = Path(a.outline) if a.outline else (Path(a.outdir) / OUTLINE_JSON)
    if not p.is_file():
        raise UsageError("找不到提纲文件：%s（先跑 `outline`，或 --outline 指定）" % p)
    obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    plan = obj.get("plan") if isinstance(obj, dict) and "plan" in obj else obj
    if not isinstance(plan, dict) or not plan.get("chapters"):
        raise UsageError("提纲文件里没有 chapters：%s" % p)
    plan.setdefault("minutes_filled", False)
    for c in plan["chapters"]:
        c.setdefault("points", [])
        c.setdefault("minutes", 0)
    return plan


def _read_script(a):
    """读对话稿，返回 (script, 成品 Markdown, meta)。

    支持两种形态：
      · `script.json`（本包 `script` 的产出）—— 读 JSON 里的 chapters
      · 任意 `.md` —— 用 ROLE_LINE_RE 解析（这样手工改过的稿子也能进配音/混音）
    两种都最终渲染成 Markdown 再过闸门：**闸门读的永远是成品稿**。

    meta["target_minutes"] 是**时长闸门的基准**，必须从稿子本身带过来：
    第一版 `voice` 没带，默认用了 30 分钟，于是拿一期 8 分钟的稿子去配音时，
    被自己的时长闸门以「约 7.5 分钟 ≠ 30 分钟」拦下——闸门没错，是**基准取错了**。
    对 `.md` 稿子就从渲染稿里的「目标时长」那一行反解，解不出才退回默认值。
    """
    p = Path(a.script) if a.script else (Path(a.outdir) / SCRIPT_JSON)
    if not p.is_file():
        alt = Path(a.outdir) / SCRIPT_MD
        if not a.script and alt.is_file():
            p = alt
        else:
            raise UsageError("找不到对话稿：%s（先跑 `script`，或 --script 指定）" % p)
    if p.suffix.lower() == ".md":
        md = p.read_text(encoding="utf-8", errors="replace")
        turns, _un, _hd = parse_script_md(md)
        chapters, cur = [], None
        for t in turns:
            if cur is None:
                cur = {"no": 1, "title": "", "gist": "", "lines": []}
                chapters.append(cur)
            cur["lines"].append(t)
        title = ""
        for line in md.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        script = {"title": title, "chapters": chapters,
                  "role_a": SHOW["role_a"], "role_b": SHOW["role_b"]}
        m = re.search(r"目标时长：(\d+(?:\.\d+)?)\s*分钟", md)
        meta = {"subtitle": None, "roles": [SHOW["role_a"], SHOW["role_b"]],
                "target_minutes": float(m.group(1)) if m else None}
        return script, md, meta
    obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    script = obj.get("script") if isinstance(obj, dict) and "script" in obj else obj
    if not isinstance(script, dict) or not script.get("chapters"):
        raise UsageError("对话稿文件里没有 chapters：%s" % p)
    script.setdefault("role_a", SHOW["role_a"])
    script.setdefault("role_b", SHOW["role_b"])
    script["chapters"] = [c for c in script["chapters"] if isinstance(c, dict)]
    missing = [(c.get("no"), i) for i, c in enumerate(script["chapters"])
               for _ in [0] if not isinstance(c.get("lines"), list)]
    if missing:
        # 行不是数组就没法解析角色 → 如实报错，别静默当空
        bad = missing[0]
        raise UsageError("第 %s 章的 lines 不是数组（对话稿格式不对）：%s"
                         % (bad[1], p))
    meta = {"subtitle": obj.get("subtitle") if isinstance(obj, dict) else None,
            "roles": [script.get("role_a"), script.get("role_b")],
            "minutes": (obj or {}).get("target_minutes"),
            "target_minutes": (obj or {}).get("target_minutes")}
    return script, render_script_md(script, meta), meta


def _target_minutes(a, outline=None):
    if getattr(a, "minutes", None):
        return float(a.minutes)
    if outline:
        tot = sum(float(c.get("minutes") or 0) for c in outline.get("chapters") or [])
        if tot > 0:
            return round(tot, 1)
    return float(SHOW["default_minutes"])


def _confirm_spend(a, quotes, what):
    """闸门六的入口：报价 → 要 --yes 或 --budget。

    返回 None 表示放行；返回退出码表示就地中止（一分钱没花）。
    """
    total = round(sum(q.get("points") or 0 for q in quotes), 2)
    sys.stderr.write("\n=== %s 成本前置报价 ===\n" % what)
    for q in quotes:
        sys.stderr.write("  · %-34s %8s 点  ≈ %s 元\n"
                         % (q.get("item"), q.get("points"), money(q.get("points"))))
    sys.stderr.write("  合计 %s 点 ≈ %s 元（1 元 = %d 点；结算只认 usage.points_cost）\n"
                     % (total, money(total), int(POINTS_PER_YUAN)))
    if a.budget is not None and total > a.budget:
        sys.stderr.write(_red("!! 报价 %s 点已超过 --budget %s 点，就地中止（还没花钱）。"
                              % (total, a.budget)) + "\n")
        return _fail(EXIT_BUDGET, "budget",
                     "报价 %s 点已超过 --budget %s 点，就地中止（还没花钱）"
                     % (total, a.budget))
    if a.budget is None and not getattr(a, "yes", False):
        sys.stderr.write(_red(
            "!! 没有确认就开跑：请加 --yes 明确同意，或用 --budget N 封顶。") + "\n")
        return _fail(EXIT_USAGE, "usage",
                     "跑前必须报价并确认：加 --yes 或 --budget N（本次未花费）")
    return None


def _budget_left(a, spent):
    if a.budget is None:
        return None
    return round(float(a.budget) - float(spent), 2)


def _report_spend(label, quoted, actual):
    """把**真实扣点**打出来，并与报价对账。不一致就明说，不糊过去。"""
    if actual is None:
        sys.stderr.write("  %s：返回里没有 usage.points_cost，无法核对实际扣费\n" % label)
        return
    note = ""
    if quoted:
        diff = actual - quoted
        if abs(diff) > max(0.5, quoted * 0.05):
            note = "（与报价 %.2f 点相差 %+.2f 点，以实际为准）" % (quoted, diff)
    sys.stderr.write("  %s：实际扣费 %s 点 ≈ %s 元%s\n"
                     % (label, actual, money(actual), note))


# ---------------------------------------------------------------------------
# 子命令：outline
# ---------------------------------------------------------------------------

def _run_outline(a):
    minutes = _target_minutes(a)
    if not (SHOW["min_minutes"] <= minutes <= SHOW["max_minutes"]):
        raise UsageError("--minutes 要在 %d~%d 之间（给的是 %s）"
                         % (SHOW["min_minutes"], SHOW["max_minutes"], minutes))
    prompt = build_outline_prompt(a.topic, minutes, a.brief, a.audience)
    hygiene = prompt_hygiene(SYSTEM_PROMPT + "\n" + prompt)
    if hygiene:
        raise UsageError("提示词卫生自检失败：提示词里混进了可照抄的示例/占位符（%s）。"
                         "这是本包的红线，请改提示词。" % json.dumps(hygiene, ensure_ascii=False))
    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "endpoint": "/api/v1/chat/completions",
                       "minutes": minutes, "system": SYSTEM_PROMPT, "user": prompt,
                       "prompt_hygiene": hygiene}, a, indent=2)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (SYSTEM_PROMPT, prompt))
        return EXIT_OK
    sys.stderr.write("正在选题与列提纲（目标 %s）…\n" % fmt_minutes(minutes))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    plan = normalize_outline(parse_first_json(content), minutes)
    # 提纲也要过闸门一/二/三：选题阶段写进「最」字和占位符，后面会被放大到整期节目
    md = render_outline_md(plan, a.model, usage, elapsed, minutes)
    scan = compliance_scan(md)
    ph = placeholder_scan(md)
    echoes = prompt_echo_scan(md, label="提纲")
    g = {"compliance": {"ok": not scan["hits"], "hits": scan["hits"],
                        "exempted": scan["exempted"]},
         "placeholder": {"ok": not ph, "hits": ph},
         "prompt_echo": {"ok": not echoes, "hits": echoes}}
    g["ok"] = all(v["ok"] for k, v in g.items() if k != "ok")
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / OUTLINE_JSON).write_text(json.dumps(
        {"plan": plan, "model": a.model, "usage": usage, "target_minutes": minutes,
         "endpoint": "/api/v1/chat/completions", "gates": g},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / OUTLINE_MD).write_text(md + "\n", encoding="utf-8")
    result = {"topic": a.topic, "minutes": minutes, "model": a.model,
              "endpoint": "/api/v1/chat/completions", "usage": usage,
              "elapsed": round(elapsed, 1), "plan": plan, "gates": g,
              "outdir": str(outdir), "files": {"json": str(outdir / OUTLINE_JSON),
                                               "md": str(outdir / OUTLINE_MD)}}
    _emit(a, result, md, ok=g["ok"])
    if not g["ok"]:
        return _fail(EXIT_GATE, "gate", "提纲命中闸门（%s）"
                     % "、".join(k for k, v in g.items() if k != "ok" and not v["ok"]))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：script
# ---------------------------------------------------------------------------

def _run_script(a):
    plan = _read_outline(a)
    minutes = _target_minutes(a, plan)
    role_a = a.role_a or SHOW["role_a"]
    role_b = a.role_b or SHOW["role_b"]
    prompt = build_script_prompt(plan, minutes, role_a, role_b, a.brief)
    hygiene = prompt_hygiene(SYSTEM_PROMPT + "\n" + prompt)
    if hygiene:
        raise UsageError("提示词卫生自检失败：提示词里混进了可照抄的示例/占位符（%s）。"
                         % json.dumps(hygiene, ensure_ascii=False))
    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "endpoint": "/api/v1/chat/completions",
                       "minutes": minutes, "target_chars": int(minutes * cpm()),
                       "system": SYSTEM_PROMPT, "user": prompt,
                       "prompt_hygiene": hygiene}, a, indent=2)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (SYSTEM_PROMPT, prompt))
        return EXIT_OK
    sys.stderr.write("正在写对话稿（目标 %s ≈ %d 字）…\n"
                     % (fmt_minutes(minutes), int(minutes * cpm())))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    script = normalize_script(parse_first_json(content), plan, role_a, role_b)
    md = render_script_md(script, {"subtitle": plan.get("subtitle"),
                                   "roles": [role_a, role_b], "minutes": minutes})
    g = gate_script(script, md, minutes, allow_multi_role=a.allow_multi_role)
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / SCRIPT_JSON).write_text(json.dumps(
        {"script": script, "target_minutes": minutes,
         "chars": script_chars(script), "model": a.model, "usage": usage,
         "endpoint": "/api/v1/chat/completions",
         "outline_title": plan.get("title"), "gates": g},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / SCRIPT_MD).write_text(md + "\n", encoding="utf-8")
    result = {"minutes": minutes, "model": a.model,
              "endpoint": "/api/v1/chat/completions", "usage": usage,
              "elapsed": round(elapsed, 1), "chars": script_chars(script),
              "turns": g["dialogue"]["turns"], "roles": g["dialogue"]["roles"],
              "script": script, "gates": g, "outdir": str(outdir),
              "files": {"json": str(outdir / SCRIPT_JSON), "md": str(outdir / SCRIPT_MD)}}
    _emit(a, result, md, ok=g["ok"])
    return _gate_report(g, plan.get("title") or "")


# ---------------------------------------------------------------------------
# 子命令：voices（拿 reference_id）
# ---------------------------------------------------------------------------

def _run_voices(a):
    key = a7w.load_key(a.key)
    lst = list_voices(key, tag=a.tag, title=a.title_search, page_size=a.page_size)
    rows = []
    for it in lst:
        if not isinstance(it, dict):
            continue
        rows.append({"reference_id": voice_id_of(it),
                     "title": a7w.dig(it, "title") or a7w.dig(it, "name"),
                     "language": a7w.dig(it, "language"),
                     "tags": a7w.dig(it, "tags"),
                     "task_count": a7w.dig(it, "task_count")})
    if a.json:
        _json_out({"endpoint": VOICES_ENDPOINT, "count": len(rows), "data": rows}, a, indent=1)
        return EXIT_OK
    print("可用音色 %d 个（POST %s）\n" % (len(rows), VOICES_ENDPOINT))
    for r in rows:
        # ⚠️ reference_id **必须整条打出来**，不许截断。
        # 事故复盘：第一版按 `%-28s` 截断显示了，实测时照着屏幕抄了前 28 位，
        # 结果 tts 返回 `code=0 任务处理失败`——真正的 id 是 32 位十六进制。
        # 列表里唯一要"抄下来用"的字段被截断，是这一版最蠢的一个 bug。
        print("  %s" % (r["reference_id"] or "-"))
        print("      %-22s %-8s %s" % (str(r["title"])[:22],
                                       str(r["language"] or "-")[:8],
                                       str(r["tags"] or "")))
    print("")
    print("把 reference_id **整条**交给配音：--voice-a <ID> --voice-b <ID>")
    print("不给就自动取前两个（脚本会在 stderr 说明取了哪两个）。")
    print("id 是 32 位十六进制；抄短了会得到 code=0「任务处理失败」。")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：voice（分角色配音）
# ---------------------------------------------------------------------------

def _run_voice(a):
    outdir = check_outdir(a.outdir)
    # 时长闸门的基准优先取稿子自带的目标时长（见 _read_script 的说明）
    script, md, meta = _read_script(a)
    minutes = (float(a.minutes) if getattr(a, "minutes", None)
               else (meta.get("target_minutes") or SHOW["default_minutes"]))
    # 配音**先过闸门再报价**：拿一份结构残缺的稿子去配音，
    # 等于把错误放大到几十个音频片段上，而且钱已经花了。
    g = gate_script(script, md, minutes, allow_multi_role=a.allow_multi_role)
    if not g["ok"]:
        result = {"stage": "voice", "gates": g, "spent_points": 0,
                  "note": "闸门未通过，未发起任何配音调用，未扣费"}
        _emit(a, result, render_outline_md({"title": "配音中止：对话稿未过闸门"}, None),
              ok=False)
        return _gate_report(g, script.get("title") or "")

    chunks = draft_voice_chunks(script, sample_chars=a.sample_chars)
    if not chunks:
        raise UsageError("对话稿里没有可配音的台词（检查 script.json 的 lines）")
    total_chars = sum(c["chars"] for c in chunks)
    quotes = [quote_voice(total_chars, a.points_per_1k)]
    rc = _confirm_spend(a, quotes, "配音（%d 个片段 / %d 字）" % (len(chunks), total_chars))
    if rc:
        return rc

    key = a7w.load_key(a.key)
    role_order = g["dialogue"]["roles"]
    voice_map = {}
    if a.voice_a:
        voice_map[role_order[0]] = a.voice_a
    if a.voice_b and len(role_order) > 1:
        voice_map[role_order[1]] = a.voice_b
    need = [r for r in role_order if r not in voice_map]
    if need:
        ids, _lst = first_voice_ids(key, want=len(need))
        for r, vid in zip(need, ids):
            voice_map[r] = vid
        if not ids:
            raise PodcastError("取不到可用音色：用 `run.py voices` 看列表，"
                               "再 --voice-a / --voice-b 手动指定")
        sys.stderr.write("未指定的音色已自动取用：%s\n"
                         % "、".join("%s→%s" % (r, voice_map.get(r)) for r in need))

    vdir = outdir / "voice"
    vdir.mkdir(parents=True, exist_ok=True)
    state = load_state(outdir)
    st_voice = state.setdefault("voice", {})
    index, spent, skipped = [], 0.0, 0
    t_all = time.time()
    for ch in chunks:
        fname = "%03d-%s.mp3" % (ch["order"], safe_name(ch["role"]))
        fpath = vdir / fname
        prev = st_voice.get(ch["key"])
        if prev and prev.get("hash") == ch["hash"] and fpath.is_file() and not a.force:
            skipped += 1
            index.append({"file": str(fpath), "role": ch["role"], "chars": ch["chars"],
                          "chapter": ch["chapter"], "chapter_title": ch["chapter_title"],
                          "order": ch["order"],
                          "points": prev.get("points"), "resumed": True})
            sys.stderr.write("  [%d/%d] %s 已存在，跳过（断点续跑，不重复扣费）\n"
                             % (ch["order"], len(chunks), fname))
            continue
        rid = voice_map.get(ch["role"])
        sys.stderr.write("  [%d/%d] %s ← %s（%d 字，端点是 %s）\n"
                         % (ch["order"], len(chunks), fname, rid or "平台默认音色",
                            ch["chars"], TTS_ENDPOINT))
        res = do_tts(key, ch["text"], reference_id=rid, fmt="mp3",
                     speed=a.speed, timeout=a.timeout)
        pts = points_of(res)
        if pts is not None:
            spent += pts
        _report_spend("配音 %s" % fname, ch["chars"] / 1000.0 * TTS_POINTS_PER_1K_CHARS, pts)
        url = pick_url(res.get("result") if isinstance(res, dict) else res,
                       "audio_url", "url", "output_url", "file_url")
        if not url:
            raise PodcastError("配音返回里没找到音频地址（片段 %s）：%s"
                               % (fname, json.dumps(res, ensure_ascii=False)[:400]))
        try:
            a7w.save(url, fpath)
        except (a7w.A7wError, OSError) as exc:
            raise PodcastError("音频下载失败（片段 %s）：%s（地址：%s）" % (fname, exc, url))
        st_voice[ch["key"]] = {"hash": ch["hash"], "chars": ch["chars"],
                               "role": ch["role"], "file": str(fpath),
                               "points": pts, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_state(outdir, state)     # 每片都落盘：中断后重跑不重复扣费
        index.append({"file": str(fpath), "role": ch["role"], "chars": ch["chars"],
                      "chapter": ch["chapter"], "chapter_title": ch["chapter_title"],
                      "order": ch["order"], "points": pts, "url": url})
        left = _budget_left(a, spent)
        if left is not None and left < 0:
            (vdir / VOICE_INDEX).write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
            result = {"stage": "voice", "spent_points": round(spent, 2),
                      "chars": total_chars, "segments": len(index),
                      "endpoint": TTS_ENDPOINT, "voice_map": voice_map,
                      "files": [i["file"] for i in index], "gates": g}
            _emit(a, result, "配音已花 %.2f 点，超过 --budget %s 点，就地中止" % (spent, a.budget),
                  ok=False)
            return _fail(EXIT_BUDGET, "budget",
                         "配音已花 %.2f 点超过 --budget %s 点，就地中止（已完成 %d 个片段）"
                         % (spent, a.budget, len(index)))

    (vdir / VOICE_INDEX).write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    save_state(outdir, state)
    elapsed = time.time() - t_all
    # 报价 vs 实际的**单价校验**：这是本包对「50 点/千字」这条实测结论的自我对账
    per_1k = (spent * 1000.0 / total_chars) if total_chars else None
    result = {"stage": "voice", "endpoint": TTS_ENDPOINT,
              "chars": total_chars, "segments": len(index), "skipped": skipped,
              "spent_points": round(spent, 2), "spent_yuan": money(spent),
              "quoted_points": quotes[0]["points"],
              "measured_points_per_1k_chars": (round(per_1k, 2) if per_1k else None),
              "declared_points_per_1k_chars": TTS_POINTS_PER_1K_CHARS,
              "voice_map": voice_map, "elapsed": round(elapsed, 1),
              "files": [i["file"] for i in index], "index": str(vdir / VOICE_INDEX),
              "gates": {"ok": True, "dialogue": g["dialogue"], "duration": g["duration"]}}
    md_out = "\n".join([
        "# 配音完成",
        "",
        "- 片段：%d 个（跳过 %d 个已完成的）" % (len(index), skipped),
        "- 字数：%d 字　端点：`POST %s`" % (total_chars, TTS_ENDPOINT),
        "- 音色：%s" % "、".join("%s → %s" % (k, v) for k, v in voice_map.items()),
        "- 实际扣费：%s 点 ≈ %s 元" % (round(spent, 2), money(spent)),
        "- 实测单价：%s 点/千字（本包申报口径 %s 点/千字）"
        % (round(per_1k, 2) if per_1k else "-", TTS_POINTS_PER_1K_CHARS),
        "",
        "| # | 章节 | 角色 | 字数 | 扣点 | 文件 |",
        "|---|---|---|---|---|---|",
    ] + ["| %(order)s | %(chapter)s | %(role)s | %(chars)s | %(points)s | `%(file)s` |" % {
        "order": i["order"], "chapter": i["chapter"], "role": i["role"],
        "chars": i["chars"], "points": i["points"], "file": Path(i["file"]).name}
        for i in index])
    _emit(a, result, md_out)
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：music（片头 / 转场 / 片尾）
# ---------------------------------------------------------------------------

def _run_music(a):
    outdir = check_outdir(a.outdir)
    cues = [c.strip() for c in (a.cues or ",".join(MUSIC_CUE_KEYS)).split(",") if c.strip()]
    bad = [c for c in cues if c not in MUSIC_CUES]
    if bad:
        raise UsageError("不认识的配乐档位：%s（可选：%s）"
                         % ("、".join(bad), "、".join(MUSIC_CUE_KEYS)))
    if not cues:
        raise UsageError("--cues 至少给一个（可选：%s）" % "、".join(MUSIC_CUE_KEYS))
    title = a.title or "播客片头"
    quotes = [quote_music(cues, with_lyrics=a.with_lyrics)]
    rc = _confirm_spend(a, quotes, "配乐（%d 个档位）" % len(cues))
    if rc:
        return rc
    key = a7w.load_key(a.key)
    mdir = outdir / "music"
    mdir.mkdir(parents=True, exist_ok=True)
    state = load_state(outdir)
    st_music = state.setdefault("music", {})
    made, spent, skipped = [], 0.0, 0
    for cue in cues:
        spec = MUSIC_CUES[cue]
        style = a.style or spec["style"]
        prompt = spec["prompt"]
        fpath = mdir / ("%s.mp3" % cue)
        sig = text_hash(style + "|" + prompt + "|" + str(a.with_lyrics))
        prev = st_music.get(cue)
        if prev and prev.get("hash") == sig and fpath.is_file() and not a.force:
            skipped += 1
            made.append({"cue": cue, "file": str(fpath), "points": prev.get("points"),
                         "resumed": True})
            sys.stderr.write("  [%s] 已存在，跳过（断点续跑，不重复扣费）\n" % cue)
            continue
        lyric = None
        if a.with_lyrics:
            sys.stderr.write("  [%s] 先生成歌词（POST %s，%s 点）\n"
                             % (cue, LYRICS_ENDPOINT, MUSIC_POINTS_PER_LYRICS))
            lres = do_lyrics(key, "%s；风格：%s" % (prompt, style))
            pts_l = points_of(lres)
            if pts_l is not None:
                spent += pts_l
            _report_spend("歌词 %s" % cue, MUSIC_POINTS_PER_LYRICS, pts_l)
            lyric = (lres.get("result") if isinstance(lres, dict) else None)
            if isinstance(lyric, dict):
                lyric = lyric.get("lyric") or lyric.get("text")
            lyric = str(lyric or "") or None
        sys.stderr.write("  [%s] 生成配乐（POST %s，%s 点，%s 秒后用 ffmpeg 裁剪）\n"
                         % (cue, MUSIC_ENDPOINT, MUSIC_POINTS_PER_CREATE, spec["seconds"]))
        res = do_music(key, style=style, prompt=prompt,
                       title="%s-%s" % (title, spec["label"]),
                       lyric=lyric, instrumental=not (a.with_lyrics and lyric),
                       timeout=a.timeout)
        pts = points_of(res)
        if pts is not None:
            spent += pts
        _report_spend("配乐 %s" % cue, MUSIC_POINTS_PER_CREATE, pts)
        url = pick_url(res.get("result") if isinstance(res, dict) else res,
                       "audio_url", "url", "output_url", "file_url", "music_url")
        if not url:
            raise PodcastError("配乐返回里没找到音频地址（%s）：%s"
                               % (cue, json.dumps(res, ensure_ascii=False)[:400]))
        try:
            a7w.save(url, fpath)
        except (a7w.A7wError, OSError) as exc:
            raise PodcastError("配乐下载失败（%s）：%s（地址：%s）" % (cue, exc, url))
        st_music[cue] = {"hash": sig, "file": str(fpath), "points": pts, "style": style,
                         "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_state(outdir, state)
        made.append({"cue": cue, "file": str(fpath), "points": pts,
                     "style": style, "url": url, "trim_seconds": spec["seconds"]})
        if a.budget is not None and spent > a.budget:
            result = {"stage": "music", "spent_points": round(spent, 2), "cues": made,
                      "endpoint": MUSIC_ENDPOINT}
            _emit(a, result, "配乐已花 %.2f 点，超过 --budget %s 点，就地中止"
                  % (spent, a.budget), ok=False)
            return _fail(EXIT_BUDGET, "budget",
                         "配乐已花 %.2f 点超过 --budget %s 点（已完成 %d 个档位）"
                         % (spent, a.budget, len(made)))
    per_create = (spent / len([m for m in made if not m.get("resumed")])
                  if any(not m.get("resumed") for m in made) else None)
    result = {"stage": "music", "endpoint": MUSIC_ENDPOINT,
              "cues": [m["cue"] for m in made], "skipped": skipped,
              "spent_points": round(spent, 2), "spent_yuan": money(spent),
              "quoted_points": quotes[0]["points"],
              "measured_points_per_create": (round(per_create, 2) if per_create else None),
              "declared_points_per_create": MUSIC_POINTS_PER_CREATE,
              "with_lyrics": bool(a.with_lyrics), "files": made,
              "note": "create 接口的参数表里没有时长参数；片头/转场/片尾的长度在 mix 阶段用 "
                      "ffmpeg -t 裁剪，裁剪口径见 music_plan"}
    md_out = "\n".join([
        "# 配乐完成",
        "",
        "- 档位：%s（跳过 %d 个已完成的）" % ("、".join(m["cue"] for m in made), skipped),
        "- 端点：`POST %s`" % MUSIC_ENDPOINT,
        "- 实际扣费：%s 点 ≈ %s 元" % (round(spent, 2), money(spent)),
        "- 实测单价：%s 点/次（本包申报口径 %s 点/次）"
        % (round(per_create, 2) if per_create else "-", MUSIC_POINTS_PER_CREATE),
        "",
        "| 档位 | 文件 | 扣点 | mix 裁剪到 |",
        "|---|---|---|---|",
    ] + ["| %s | `%s` | %s | %s 秒 |" % (m["cue"], Path(m["file"]).name,
                                          m["points"], m.get("trim_seconds"))
         for m in made])
    _emit(a, result, md_out)
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：mix（本地拼接成 mp3 + 章节标记 + 时间轴）
#
# 【为什么时长从 wav 文件头算、而不是 ffprobe】
# 本机实测只有 ffmpeg、没有 ffprobe（ffprobe 是另一个可执行文件）。
# 所以混合分两步：先把每段解码成参数完全一致的 wav（mono / 44100 / 16bit），
# 这样 wav 时长 = data 块字节数 ÷ (采样率 × 声道 × 位宽/8)，**是精确值不是估算**；
# 再用 concat 解复用器拼起来编成 mp3。章节时间轴就按这些精确时长累加。
# 只读文件头那几十个字节，不用把几十 MB 的 wav 读进内存。
# ---------------------------------------------------------------------------

def wav_seconds(path):
    """从 wav 文件头算出精确时长（秒）。解析不出来返回 None，**不猜**。"""
    p = Path(path)
    if not p.is_file():
        return None
    with p.open("rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            return None
        rate = channels = bits = None
        data_size = None
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            cid, size = hdr[:4], struct.unpack("<I", hdr[4:8])[0]
            if cid == b"fmt ":
                fmt = f.read(size)
                if len(fmt) >= 16:
                    channels = struct.unpack("<H", fmt[2:4])[0]
                    rate = struct.unpack("<I", fmt[4:8])[0]
                    bits = struct.unpack("<H", fmt[14:16])[0]
            elif cid == b"data":
                data_size = size
                break
            else:
                f.seek(size + (size & 1), 1)
    if not rate or not channels or not bits or data_size is None:
        return None
    return data_size / float(rate * channels * (bits // 8))


def find_ffmpeg(explicit=None):
    """找 ffmpeg：--ffmpeg > 环境变量 FFMPEG > PATH。找不到返回 None。"""
    for cand in (explicit, os.environ.get("FFMPEG")):
        if cand:
            p = Path(cand)
            if p.is_file():
                return str(p)
            found = shutil.which(cand)
            if found:
                return found
    return shutil.which("ffmpeg")


def build_playlist(outdir, intro_seconds, bed_seconds, outro_seconds):
    """排出混音顺序：片头 → 第1章人声 → 转场 → 第2章人声 → … → 片尾。

    返回 (items, missing)：items 每项 {kind, label, path, trim, chapter}，按播放顺序。
    `chapter` 用来聚合成**章节标记**——一个章节标记应该对应节目的一章，
    而不是「某个角色的某一段」，否则 30 分钟的成片会有几十个章节标记（实测踩过）。
    """
    items, missing = [], []
    vdir = outdir / "voice"
    index_file = vdir / VOICE_INDEX
    segs = []
    if index_file.is_file():
        try:
            segs = json.loads(index_file.read_text(encoding="utf-8"))
        except ValueError:
            segs = []
    if not segs:
        segs = [{"file": str(p), "role": None, "chapter": None, "order": i}
                for i, p in enumerate(sorted(vdir.glob("*.mp3")), 1)]
    if not segs:
        raise UsageError("在 %s 里没找到配音片段（先跑 `voice`）" % vdir)

    mdir = outdir / "music"
    intro = mdir / "intro.mp3"
    bed = mdir / "bed.mp3"
    outro = mdir / "outro.mp3"
    if intro.is_file():
        items.append({"kind": "music", "label": "片头", "path": intro,
                      "trim": intro_seconds, "chapter": None})
    else:
        missing.append("片头 intro.mp3（跑 `music --cues intro` 生成）")

    last_chapter = None
    for s in sorted(segs, key=lambda x: x.get("order") or 0):
        ch = s.get("chapter")
        ctitle = s.get("chapter_title") or ""
        if last_chapter is not None and ch != last_chapter and bed.is_file():
            items.append({"kind": "music", "label": "转场（第 %s 章前）" % ch,
                          "path": bed, "trim": bed_seconds, "chapter": None})
        label = "第 %s 章" % ch
        if ctitle:
            label += "　%s" % ctitle
        if s.get("role"):
            label += "（%s）" % s["role"]
        items.append({"kind": "voice", "label": label, "path": Path(s["file"]),
                      "trim": None, "chapter": ch, "chapter_title": ctitle})
        last_chapter = ch
    if outro.is_file():
        items.append({"kind": "music", "label": "片尾", "path": outro,
                      "trim": outro_seconds, "chapter": None})
    else:
        missing.append("片尾 outro.mp3（跑 `music --cues outro` 生成）")
    return items, missing


def chapter_marks(rows):
    """把逐段的行聚合成**每章一条**的章节标记。

    输入 rows：每项 {start, end, label, kind, chapter, chapter_title}，按播放顺序。
    输出：{start, end, title} 列表——同一章的连续人声段合并成一条。
    """
    marks = []
    for r in rows:
        if r.get("kind") != "voice":
            continue
        ch = r.get("chapter")
        if marks and marks[-1]["chapter"] == ch:
            marks[-1]["end"] = r["end"]
            continue
        title = ("第 %s 章" % ch) if ch is not None else r["label"]
        if r.get("chapter_title"):
            title += "　%s" % r["chapter_title"]
        marks.append({"chapter": ch, "title": title,
                      "start": r["start"], "end": r["end"]})
    return marks


def _run_ffmpeg(ffmpeg, args, timeout=1800):
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"] + args
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout)
    except OSError as exc:
        raise PodcastError("调用 ffmpeg 失败：%s" % exc)
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-4:]
        raise PodcastError("ffmpeg 返回 %d：%s" % (proc.returncode, " | ".join(tail)))
    return proc


def _run_mix(a):
    outdir = check_outdir(a.outdir)
    items, missing = build_playlist(outdir, a.intro_seconds, a.bed_seconds, a.outro_seconds)
    for p in [i["path"] for i in items]:
        if not Path(p).is_file():
            raise UsageError("找不到音频片段：%s" % p)
    ffmpeg = find_ffmpeg(getattr(a, "ffmpeg", None))
    outfile = refuse_audio_in_pkg(a.filename or (outdir / "episode.mp3"))

    if not ffmpeg:
        # 降级：把能产的东西全产出来（都是文本），然后**明确报错退出**，不假装成功。
        text_files = write_mix_texts(outdir, items, None)
        sys.stderr.write(_red(
            "\n!! 本机没有 ffmpeg，mix 降级：\n"
            "   已写出拼接清单与章节文件（%s），**没有产出 mp3**。\n"
            "   装上 ffmpeg 后重跑同一条命令即可（断点续跑，不会重复扣配音/配乐的钱）。\n"
            "   ffmpeg 可以不在 PATH 上，用 --ffmpeg <路径> 或环境变量 FFMPEG 指定。\n"
            % "、".join(Path(p).name for p in text_files)) + "\n")
        result = {"stage": "mix", "degraded": True, "reason": "本机没有 ffmpeg",
                  "ffmpeg": None, "playlist": [{"kind": i["kind"], "label": i["label"],
                                                "file": str(i["path"]), "trim": i["trim"]}
                                               for i in items],
                  "missing_music": missing, "text_outputs": [str(p) for p in text_files],
                  "episode": None}
        _emit(a, result, render_timeline_md([], 0, {"title": "（未产出 mp3：缺 ffmpeg）"}),
              ok=False)
        return _fail(EXIT_USAGE, "usage",
                     "本机没有 ffmpeg，mix 只写出拼接清单与章节文件、没有 mp3（装上 ffmpeg 后重跑）")

    work = outdir / ".mix"
    work.mkdir(parents=True, exist_ok=True)
    wavs = []
    sys.stderr.write("正在归一化 %d 段音频（mono / 44100 / 16bit）…\n" % len(items))
    for i, it in enumerate(items, 1):
        wav = work / ("%03d.wav" % i)
        args = ["-i", str(it["path"])]
        if it.get("trim"):
            args += ["-t", str(it["trim"])]
        args += ["-ac", "1", "-ar", "44100", "-acodec", "pcm_s16le", str(wav)]
        _run_ffmpeg(ffmpeg, args)
        dur = wav_seconds(wav)
        if dur is None:
            raise PodcastError("读不出片段时长（文件头异常）：%s" % wav)
        wavs.append({"item": it, "wav": wav, "seconds": dur, "out": True})

    listfile = work / "concat.txt"
    listfile.write_text("".join("file '%s'\n" % str(w["wav"]).replace("'", "'\\''")
                                for w in wavs), encoding="utf-8")
    rows, cursor = [], 0.0
    for w in wavs:
        rows.append({"start": cursor, "end": cursor + w["seconds"],
                     "label": w["item"]["label"], "kind": w["item"]["kind"],
                     "chapter": w["item"].get("chapter"),
                     "chapter_title": w["item"].get("chapter_title")})
        cursor += w["seconds"]

    # 章节标记按**章**聚合，不是按段：实测按段会给 30 分钟的成片打几十个标记，
    # 播放器里那一条章节列表就废了。见 chapter_marks 的说明。
    marks = chapter_marks(rows)
    chapters_txt = work / "chapters.txt"
    chapters_lines = [";FFMETADATA1"]
    for mk in marks:
        chapters_lines += ["[CHAPTER]", "TIMEBASE=1/1000",
                           "START=%d" % int(round(mk["start"] * 1000)),
                           "END=%d" % int(round(mk["end"] * 1000)),
                           "title=%s" % mk["title"].replace("\n", " ")]
    chapters_txt.write_text("\n".join(chapters_lines) + "\n", encoding="utf-8")

    sys.stderr.write("正在拼接并编码 mp3…\n")
    _run_ffmpeg(ffmpeg, ["-f", "concat", "-safe", "0", "-i", str(listfile),
                         "-i", str(chapters_txt), "-map_metadata", "1",
                         "-c:a", "libmp3lame", "-b:a", "128k",
                         "-id3v2_version", "3", str(outfile)], timeout=3600)
    if not outfile.is_file() or outfile.stat().st_size <= 0:
        raise PodcastError("ffmpeg 没报错但没有产出 mp3：%s" % outfile)

    (outdir / "chapters.json").write_text(json.dumps(
        {"total_seconds": round(cursor, 2),
         "chapters": [{"start": round(m["start"], 2), "end": round(m["end"], 2),
                       "label": m["title"], "chapter": m["chapter"]} for m in marks],
         "tracks": [{"start": round(r["start"], 2), "end": round(r["end"], 2),
                     "label": r["label"], "kind": r["kind"]} for r in rows]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / "chapters.txt").write_text(chapters_txt.read_text(encoding="utf-8"),
                                         encoding="utf-8")
    timeline = render_timeline_md(rows, cursor, {"title": a.title or outdir.name})
    (outdir / "timeline.md").write_text(timeline + "\n", encoding="utf-8")
    (outdir / "playlist.txt").write_text(
        "".join("%s\t%s\t%s\n" % (fmt_mmss(r["start"]), r["kind"], r["label"]) for r in rows),
        encoding="utf-8")

    result = {"stage": "mix", "degraded": False, "ffmpeg": ffmpeg,
              "episode": str(outfile), "size_bytes": outfile.stat().st_size,
              "total_seconds": round(cursor, 2), "total_mmss": fmt_mmss(cursor),
              "items": len(items), "missing_music": missing,
              "chapters": [{"start": fmt_mmss(m["start"]), "end": fmt_mmss(m["end"]),
                            "title": m["title"]} for m in marks],
              "chapters_file": str(outdir / "chapters.txt"),
              "chapters_json": str(outdir / "chapters.json"),
              "timeline": str(outdir / "timeline.md"),
              "playlist": str(outdir / "playlist.txt"),
              "timeline_rows": [{"start": fmt_mmss(r["start"]), "end": fmt_mmss(r["end"]),
                                 "label": r["label"], "kind": r["kind"]} for r in rows]}
    _emit(a, result, timeline)
    if missing:
        sys.stderr.write("\n提示：缺 %s——已跳过，成片没有这一段。\n" % "；".join(missing))
    return EXIT_OK


def write_mix_texts(outdir, items, durations):
    """没 ffmpeg 时的降级产出：拼接清单 + 章节骨架（都是文本，可离线看）。"""
    out = []
    p = outdir / "playlist.txt"
    p.write_text("".join("%02d\t%s\t%s\t%s\t%s\n"
                         % (i, it["kind"], it.get("trim") or "-", it["label"], it["path"])
                         for i, it in enumerate(items, 1)), encoding="utf-8")
    out.append(p)
    q = outdir / "chapters.txt"
    q.write_text("\n".join([";FFMETADATA1 （本机无 ffmpeg，未产出 mp3；"
                            "这是按裁剪口径预估的章节骨架，装上 ffmpeg 后重跑 mix 会重算）"]
                           + ["[CHAPTER]", "TIMEBASE=1/1000", "START=?", "END=?"]
                           + ["title=%s" % it["label"] for it in items]) + "\n",
                 encoding="utf-8")
    out.append(q)
    r = outdir / "mix-commands.txt"
    r.write_text("把下面这条粘到有 ffmpeg 的机器上即可得到 episode.mp3：\n\n"
                 "ffmpeg -f concat -safe 0 -i concat.txt -i chapters.txt -map_metadata 1 "
                 "-c:a libmp3lame -b:a 128k episode.mp3\n", encoding="utf-8")
    out.append(r)
    return out


# ---------------------------------------------------------------------------
# 子命令：cost（只算钱，一次调用都不发）
# ---------------------------------------------------------------------------

def _run_cost(a):
    minutes = float(a.minutes or SHOW["default_minutes"])
    chars = int(a.chars) if a.chars else int(minutes * cpm())
    cues = [c.strip() for c in (a.cues or ",".join(MUSIC_CUE_KEYS)).split(",") if c.strip()]
    bad = [c for c in cues if c not in MUSIC_CUES]
    if bad:
        raise UsageError("不认识的配乐档位：%s" % "、".join(bad))
    qv = quote_voice(chars, a.points_per_1k)
    qm = quote_music(cues, with_lyrics=a.with_lyrics)
    total = qv["points"] + qm["points"]
    text_est = None
    if a.points_per_ktok:
        # 文本大模型的单价平台不公开（models 列表里没有任何价格字段、
        # pricing 表也不覆盖 chat/completions），所以**不给单价就不报金额**，绝不编。
        # token 粗估：中文约 1 字 ≈ 0.7 token，输出按目标字数的 1.2 倍留余量。
        tok_in = int(chars * 0.7 * 1.5)
        tok_out = int(chars * 0.7 * 1.2)
        pts = (tok_in + tok_out) / 1000.0 * float(a.points_per_ktok)
        text_est = {"assumed_prompt_tokens": tok_in, "assumed_completion_tokens": tok_out,
                    "points_per_ktok": float(a.points_per_ktok),
                    "points": round(pts, 2), "yuan": round(pts / POINTS_PER_YUAN, 4),
                    "note": "token 是粗估；文本单价由 --points-per-ktok 给出，不是平台值"}
        total += pts
    result = {"minutes": minutes, "chars": chars,
              "chars_per_minute": cpm(),
              "voice": qv, "music": qm, "text": text_est,
              "total_points": round(total, 2),
              "total_yuan": round(total / POINTS_PER_YUAN, 4),
              "points_per_yuan": POINTS_PER_YUAN,
              "endpoints": {"tts": TTS_ENDPOINT, "music": MUSIC_ENDPOINT,
                            "lyrics": LYRICS_ENDPOINT,
                            "chat": "/api/v1/chat/completions",
                            "tasks": "/api/v1/tasks/"},
              "units": {"tts_points_per_1k_chars": TTS_POINTS_PER_1K_CHARS,
                        "music_points_per_create": MUSIC_POINTS_PER_CREATE,
                        "music_points_per_lyrics": MUSIC_POINTS_PER_LYRICS},
              "note": "配音/配乐单价是本包实测值；文本大模型单价平台不公开，"
                      "给了 --points-per-ktok 才算金额。结算以 usage.points_cost 为准。"}
    lines = [
        "# 成本测算（本地计算，未发起任何调用）", "",
        "- 目标时长：%s　按 %d 字/分钟折算 %d 字"
        % (fmt_minutes(minutes), cpm(), chars),
        "- 换算口径：1 元 = %d 点" % int(POINTS_PER_YUAN), "",
        "| 项目 | 单价 | 数量 | 点数 | 金额 |", "|---|---|---|---|---|",
        "| 配音 `voice_tts/tts` | %s 点/千字 | %d 字 | %s | %s 元 |"
        % (TTS_POINTS_PER_1K_CHARS, chars, qv["points"], qv["yuan"]),
        "| 配乐 `music_generation/create` | %s 点/次 | %d 次 | %s | %s 元 |"
        % (MUSIC_POINTS_PER_CREATE, len(cues), qm["points"] - (len(cues) * MUSIC_POINTS_PER_LYRICS if a.with_lyrics else 0), qm["yuan"]),
    ]
    if a.with_lyrics:
        lines.append("| 歌词 `music_generation/lyrics` | %s 点/次 | %d 次 | %s | — |"
                     % (MUSIC_POINTS_PER_LYRICS, len(cues),
                        len(cues) * MUSIC_POINTS_PER_LYRICS))
    if text_est:
        lines.append("| 文本大模型（估算） | %s 点/千 token | ~%d+%d token | %s | %s 元 |"
                     % (text_est["points_per_ktok"], text_est["assumed_prompt_tokens"],
                        text_est["assumed_completion_tokens"], text_est["points"],
                        text_est["yuan"]))
    else:
        lines.append("| 文本大模型 | 平台未公开 | — | 未计 | 未计（给 --points-per-ktok 才计） |")
    lines += ["| **合计** | | | **%s** | **%s 元** |" % (round(total, 2),
                                                       round(total / POINTS_PER_YUAN, 4)),
              "",
              "端点：`POST %s` · `POST %s` · `POST %s` · `/api/v1/chat/completions`"
              " · `/api/v1/tasks/`" % (TTS_ENDPOINT, MUSIC_ENDPOINT, LYRICS_ENDPOINT),
              "",
              "> 配音与配乐的单价是本包真机实测值；文本大模型的单价平台不公开，"
              "本包**不编价**。实际结算以 `usage.points_cost` 为准。"]
    _emit(a, result, "\n".join(lines))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：models
# ---------------------------------------------------------------------------

def _run_models(a):
    key = a7w.load_key(a.key)
    try:
        payload = a7w._request("GET", MODELS_URL, key, timeout=60)
    except a7w.A7wError as exc:
        sys.stderr.write("拉模型清单失败：%s\n" % exc)
        return _fail(EXIT_CALL, "call", "拉取模型清单失败（网络 / 鉴权 / Key）")
    lst = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(lst, dict):
        lst = lst.get("data") or lst.get("list") or []
    lst = [m for m in (lst or []) if isinstance(m, dict)]
    if a.type and a.type != "all":
        lst = [m for m in lst if str(m.get("type_code")) == a.type]
    if a.json:
        _json_out({"endpoint": MODELS_URL, "count": len(lst), "data": lst}, a, indent=1)
        return EXIT_OK
    print("在架模型 %d 个（%s）\n" % (len(lst), MODELS_URL))
    for m in lst:
        print("  %-28s %-8s call_type=%s  %-22s %s" % (
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            m.get("call_type"), str(m.get("vendor_name") or "-"),
            str(m.get("model_name") or "")[:26]))
    print("")
    print("提示：模型名会变，以本命令现查为准，别写死在脚本里。")
    print("      `%s` 实测可用（路由到 deepseek-flash 一线），但它**不在**上面这份列表里，"
          % DEFAULT_MODEL)
    print("      所以「列表里没有」不等于「不能用」，也不等于「有价格」。")
    print("      本列表里实测**没有任何价格字段**；要算钱用 `run.py cost`。")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：all（整条链路，断点续跑）
# ---------------------------------------------------------------------------

def _run_all(a):
    """整条链路的**外层包装**：把子步骤的产出收起来，最后合并成一份输出。

    为什么要包装：`all` 复用 `_run_outline` / `_run_script` / `_run_voice` /
    `_run_music` / `_run_mix`，每个都会 `_emit` 一次。不收起来的话
    `all --json` 会吐 5 个 JSON 文档，调用方 `json.loads` 直接失败（实测踩过）。
    """
    steps = []
    _EMIT["collect"] = steps
    try:
        rc = _run_all_body(a)
    finally:
        _EMIT["collect"] = None
    combined = {
        "stage": "all",
        "outdir": str(_resolve(a.outdir)),
        "steps": [s["result"] for s in steps],
        "step_count": len(steps),
        "episode": next((s["result"].get("episode") for s in steps
                         if isinstance(s["result"], dict) and s["result"].get("episode")),
                        None),
    }
    md = "\n\n---\n\n".join(s["md"] for s in steps if s.get("md"))
    _emit(a, combined, md, ok=(rc == EXIT_OK))
    return rc


def _run_all_body(a):
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    minutes = _target_minutes(a)
    state = load_state(outdir)

    # [1/4] 提纲
    o_json = outdir / OUTLINE_JSON
    if not o_json.is_file() and not (a.topic or "").strip():
        # 没有提纲也没有主题 = 无从下手。在这里拦住，别让 "主题：None" 发到模型那边。
        raise UsageError("还没有提纲文件，请给 --topic \"主题\"；"
                         "已有提纲时可以不重复给（会走断点续跑）")
    if o_json.is_file() and not a.force and not a.topic_override:
        sys.stderr.write("[1/5] 提纲已存在，跳过（断点续跑，不重复扣费）：%s\n" % o_json)
    else:
        sys.stderr.write("[1/5] 出提纲…\n")
        rc = _run_outline(_outline_args(a, outdir, minutes))
        if rc:
            return rc
    # `--dry-run` 到这里就该收：dry-run **不写任何文件**，继续往下会去读一个
    # 不存在的 outline.json，报出"找不到提纲文件"这种假错误（第一版就是这样）。
    # 已有提纲时顺手把对话稿的提示词也晾一遍，方便一次看全两个提示词。
    if a.dry_run:
        if o_json.is_file():
            sys.stderr.write("[2/5] --dry-run：已有提纲，顺带打印对话稿提示词…\n")
            rc = _run_script(_script_args(a, outdir))
            if rc:
                return rc
        sys.stderr.write("\n--dry-run 结束：没有调用任何接口，没有写任何文件。\n")
        return EXIT_OK
    plan = _read_outline(_ns(outline=str(o_json), outdir=str(outdir)))
    minutes = _target_minutes(a, plan)

    # [2/5] 对话稿
    s_json = outdir / SCRIPT_JSON
    if s_json.is_file() and not a.force:
        sys.stderr.write("[2/5] 对话稿已存在，跳过（断点续跑）：%s\n" % s_json)
    else:
        sys.stderr.write("[2/5] 写对话稿…\n")
        rc = _run_script(_script_args(a, outdir))
        if rc:
            return rc

    # [3/5] 配音（先闸门后报价，见 _run_voice）
    sys.stderr.write("[3/5] 分角色配音…\n")
    rc = _run_voice(_voice_args(a, outdir, minutes))
    if rc:
        return rc

    # [4/5] 配乐
    if a.skip_music:
        sys.stderr.write("[4/5] 按 --skip-music 跳过配乐\n")
    else:
        sys.stderr.write("[4/5] 生成片头/转场/片尾…\n")
        rc = _run_music(_music_args(a, outdir))
        if rc:
            return rc

    # [5/5] 混音
    sys.stderr.write("[5/5] 本地混音…\n")
    rc = _run_mix(_mix_args(a, outdir))
    if rc:
        return rc
    sys.stderr.write("\n完成：%s\n" % (outdir / (a.filename or "episode.mp3")))
    return EXIT_OK


def _ns(**kw):
    """造一个临时命名空间（给内部复用其它子命令用）。"""
    return argparse.Namespace(**kw)


def _outline_args(a, outdir, minutes):
    return _ns(topic=a.topic, minutes=minutes, brief=a.brief, audience=a.audience,
               outdir=str(outdir), outline=None, json=a.json, out=None, model=a.model,
               temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
               dry_run=a.dry_run, no_json_mode=a.no_json_mode)


def _script_args(a, outdir):
    return _ns(outdir=str(outdir), outline=None, minutes=a.minutes, brief=a.brief,
               role_a=a.role_a, role_b=a.role_b, allow_multi_role=a.allow_multi_role,
               json=a.json, out=None, model=a.model, temperature=a.temperature,
               max_tokens=a.max_tokens, key=a.key, dry_run=a.dry_run,
               no_json_mode=a.no_json_mode)


def _voice_args(a, outdir, minutes=None):
    # minutes 必须传**从提纲算出来的那个值**，不能直接透传 a.minutes：
    # `all` 的 --minutes 默认是 30，而用户可能是按提纲各章之和（比如 8 分钟）做的稿子，
    # 直接透传会让配音步骤拿 30 分钟当基准，被自己的时长闸门误拦（实测踩过一次）。
    return _ns(outdir=str(outdir), script=None, minutes=minutes,
               allow_multi_role=a.allow_multi_role, sample_chars=a.sample_chars,
               points_per_1k=a.points_per_1k, voice_a=a.voice_a, voice_b=a.voice_b,
               speed=a.speed, timeout=a.timeout, force=a.force, yes=a.yes,
               budget=a.budget, json=a.json, out=None, key=a.key)


def _music_args(a, outdir):
    return _ns(outdir=str(outdir), cues=a.cues, with_lyrics=a.with_lyrics,
               style=a.style, title=a.title, timeout=a.timeout, force=a.force,
               yes=a.yes, budget=a.budget_after_voice, json=a.json, out=None, key=a.key)


def _mix_args(a, outdir):
    return _ns(outdir=str(outdir), ffmpeg=a.ffmpeg, filename=a.filename,
               intro_seconds=a.intro_seconds, bed_seconds=a.bed_seconds,
               outro_seconds=a.outro_seconds, title=a.title, json=a.json, out=None)


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def _add_cpm(p):
    """`--chars-per-minute`：覆盖语速口径。

    为什么给这个开关：语速直接决定「目标时长 ↔ 字数」的换算，而不同节目差得很远
    （一个人慢聊 220，两个人快聊 290）。默认值是实测口径，但不是所有人的口径。
    它会**同时**影响三处：提示词里给模型的目标字数、时长闸门的判定、成本报价——
    这正是它必须是一个显式开关、而不是三处各自一个参数的原因。
    """
    p.add_argument("--chars-per-minute", type=float, dest="chars_per_minute",
                   help="语速口径（字/分钟），默认 %s" % SHOW["chars_per_minute"])


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与 sanjianke-portrait-studio 同口径）。

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
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens",
                   help="最大输出 token，默认 8192（一期对话稿 7000+ 字，给少了会被截断）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词 + 提示词卫生自检，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")
    if with_out:
        p.add_argument("--out", help="把结果写到这个文件")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 播客全自动生产（走 api.a7w.cn 的 OpenAI 兼容端点与生成应用）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models · "
               "POST https://api.a7w.cn/api/v1/apps/voice_tts/tts · "
               "POST https://api.a7w.cn/api/v1/apps/music_generation/create · "
               "GET https://api.a7w.cn/api/v1/tasks/<task_id>")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("outline", help="选题 + 提纲（标题/角度/受众/章节/片头钩子/片尾收束）")
    p.add_argument("--topic", required=True, help="播客主题（一句话说清讲什么）")
    p.add_argument("--minutes", type=float, default=SHOW["default_minutes"],
                   help="目标时长（分钟），默认 %d" % SHOW["default_minutes"])
    p.add_argument("--audience", help="目标听众（不给就让模型自己定）")
    p.add_argument("--brief", help="额外要求（口述的意图）")
    p.add_argument("--outdir", default="podcast-out", help="产出目录（**不许在包内**）")
    p.add_argument("--outline", help="读已有提纲文件（一般不用给）")
    _add_cpm(p)
    _add_model_opts(p)
    p.set_defaults(func=_run_outline)

    p = sub.add_parser("script", help="写双人对话稿（两个角色 + 交替发言 + 语气标注）")
    p.add_argument("--outdir", default="podcast-out", help="产出目录（**不许在包内**）")
    p.add_argument("--outline", help="提纲文件，默认 <outdir>/outline.json")
    p.add_argument("--minutes", type=float, help="覆盖目标时长（默认取提纲各章之和）")
    p.add_argument("--brief", help="额外要求")
    p.add_argument("--role-a", dest="role_a", help="角色 A 的名字，默认「%s」" % SHOW["role_a"])
    p.add_argument("--role-b", dest="role_b", help="角色 B 的名字，默认「%s」" % SHOW["role_b"])
    p.add_argument("--allow-multi-role", action="store_true", dest="allow_multi_role",
                   help="放宽对话结构闸门：允许 3 个以上角色（默认只认双人）")
    _add_cpm(p)
    _add_model_opts(p)
    p.set_defaults(func=_run_script)

    p = sub.add_parser("voice", help="分角色配音（两个音色；先报价；断点续跑）")
    p.add_argument("--outdir", default="podcast-out", help="产出目录（**不许在包内**）")
    p.add_argument("--script", help="对话稿（script.json 或 .md），默认 <outdir>/script.json")
    p.add_argument("--minutes", type=float, help="覆盖目标时长（只影响时长闸门）")
    p.add_argument("--allow-multi-role", action="store_true", dest="allow_multi_role")
    p.add_argument("--voice-a", dest="voice_a", help="角色 A 的音色 reference_id")
    p.add_argument("--voice-b", dest="voice_b", help="角色 B 的音色 reference_id")
    p.add_argument("--speed", type=float, help="语速（prosody.speed，1.0 为原速）")
    p.add_argument("--sample-chars", type=int, default=0, dest="sample_chars",
                   help="只配前 N 个字（**试链路省钱用**；0 = 全部）")
    p.add_argument("--points-per-1k", type=float, dest="points_per_1k",
                   help="覆盖配音单价（点/千字），默认用实测值 %s" % TTS_POINTS_PER_1K_CHARS)
    p.add_argument("--timeout", type=int, default=1800, help="单个任务轮询超时（秒）")
    p.add_argument("--force", action="store_true", help="忽略断点全部重配（**会重复扣费**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）；与 --yes 二者给其一即可")
    _add_cpm(p)
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_voice)

    p = sub.add_parser("music", help="片头 / 转场 / 片尾配乐（music_generation/create）")
    p.add_argument("--outdir", default="podcast-out", help="产出目录（**不许在包内**）")
    p.add_argument("--cues", help="要生成哪些：intro,bed,outro（默认三个都做）")
    p.add_argument("--style", help="覆盖音乐风格描述（默认按档位内置）")
    p.add_argument("--title", help="曲目标题前缀，默认「播客片头」")
    p.add_argument("--with-lyrics", action="store_true", dest="with_lyrics",
                   help="先生成歌词再谱曲（歌词 %s 点/次，默认做纯器乐）"
                        % MUSIC_POINTS_PER_LYRICS)
    p.add_argument("--timeout", type=int, default=1800, help="任务轮询超时（秒）")
    p.add_argument("--force", action="store_true", help="忽略断点重做（**会重复扣费**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_music)

    p = sub.add_parser("mix", help="本地拼接成 mp3 + 章节标记 + 时间轴（需要 ffmpeg）")
    p.add_argument("--outdir", default="podcast-out", help="产出目录")
    p.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径（默认找 PATH 与 FFMPEG 环境变量）")
    p.add_argument("--filename", help="成片文件名，默认 episode.mp3")
    p.add_argument("--intro-seconds", type=float, default=15.0, dest="intro_seconds",
                   help="片头裁剪到多少秒，默认 15")
    p.add_argument("--bed-seconds", type=float, default=6.0, dest="bed_seconds",
                   help="转场裁剪到多少秒，默认 6")
    p.add_argument("--outro-seconds", type=float, default=20.0, dest="outro_seconds",
                   help="片尾裁剪到多少秒，默认 20")
    p.add_argument("--title", help="节目名（写进时间轴）")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_mix)

    p = sub.add_parser("all", help="整条链路：提纲 → 对话稿 → 配音 → 配乐 → 混音")
    p.add_argument("--topic", help="播客主题（outline 用；已存在提纲时可省）")
    p.add_argument("--topic-override", action="store_true", dest="topic_override",
                   help="即使已有提纲也重新出题（**会重复扣费**）")
    # 默认 **None** 而不是 30：`all` 的时长基准应当优先取**提纲各章之和**，
    # 只有用户显式给了 --minutes 才覆盖它。给默认值 30 会让 8 分钟的稿子在配音
    # 步骤被按 30 分钟校验，撞上时长闸门（实测踩过一次）。
    p.add_argument("--minutes", type=float, default=None,
                   help="目标时长（分钟）；不给就取提纲各章之和，再退到 %d"
                        % SHOW["default_minutes"])
    p.add_argument("--audience", help="目标听众")
    p.add_argument("--brief", help="额外要求")
    p.add_argument("--outdir", default="podcast-out", help="产出目录（**不许在包内**）")
    p.add_argument("--role-a", dest="role_a")
    p.add_argument("--role-b", dest="role_b")
    p.add_argument("--allow-multi-role", action="store_true", dest="allow_multi_role")
    p.add_argument("--voice-a", dest="voice_a")
    p.add_argument("--voice-b", dest="voice_b")
    p.add_argument("--speed", type=float)
    p.add_argument("--sample-chars", type=int, default=0, dest="sample_chars")
    p.add_argument("--points-per-1k", type=float, dest="points_per_1k")
    p.add_argument("--cues", help="配乐档位，默认三个都做")
    p.add_argument("--with-lyrics", action="store_true", dest="with_lyrics")
    p.add_argument("--style", help="覆盖音乐风格")
    p.add_argument("--skip-music", action="store_true", dest="skip_music",
                   help="跳过配乐（只出人声与混音）")
    p.add_argument("--ffmpeg")
    p.add_argument("--filename")
    p.add_argument("--intro-seconds", type=float, default=15.0, dest="intro_seconds")
    p.add_argument("--bed-seconds", type=float, default=6.0, dest="bed_seconds")
    p.add_argument("--outro-seconds", type=float, default=20.0, dest="outro_seconds")
    p.add_argument("--title")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑（**会重复扣费**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="整条链路的预算上限（点）")
    _add_cpm(p)
    _add_model_opts(p)
    p.set_defaults(func=_run_all)

    p = sub.add_parser("cost", help="只算钱（本地计算，一次调用都不发）")
    p.add_argument("--minutes", type=float, default=SHOW["default_minutes"], help="目标时长")
    p.add_argument("--chars", type=int, help="直接给字数（默认按目标时长折算）")
    p.add_argument("--cues", help="配乐档位，默认三个都做")
    p.add_argument("--with-lyrics", action="store_true", dest="with_lyrics")
    p.add_argument("--points-per-1k", type=float, dest="points_per_1k",
                   help="覆盖配音单价（点/千字）")
    p.add_argument("--points-per-ktok", type=float, dest="points_per_ktok",
                   help="文本大模型单价（点/千 token）；不给就**不报文本金额**（平台未公开）")
    _add_cpm(p)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）")
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=_run_models)

    p = sub.add_parser("voices", help="列出可用音色，拿配音要的 reference_id（免费）")
    p.add_argument("--tag", help="按标签筛选")
    p.add_argument("--title-search", dest="title_search", help="按音色名称搜索")
    p.add_argument("--page-size", type=int, default=20, dest="page_size", help="每页数量")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=_run_voices)

    return ap


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与以前完全一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout
    _JSON["want"] = "--json" in argv_eff
    _JSON["emitted"] = False
    _JSON["reason"] = None
    try:
        return _main(argv_eff)
    except Exception as exc:                      # noqa: BLE001 —— 故意的：契约要求给信封
        if not _JSON["want"]:
            raise
        traceback.print_exc()
        _json_internal(exc)
        return 1


def _main(argv_eff):
    ap = build_parser()
    try:
        a = ap.parse_args(argv_eff)
    except SystemExit as exc:
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    # 语速口径的运行时覆盖（只影响本次进程，不动 SHOW 这张口径表）
    _CPM["v"] = getattr(a, "chars_per_minute", None) or None
    if _CPM["v"] is not None and not (100 <= _CPM["v"] <= 500):
        sys.stderr.write("参数错误：--chars-per-minute 要在 100~500 之间（给的是 %s）\n"
                         % _CPM["v"])
        _json_fail(EXIT_USAGE, "usage", "--chars-per-minute 越界")
        return EXIT_USAGE
    # `all` 的预算要拆成两段：配音先花，剩下的额度才给配乐
    if getattr(a, "budget", None) is not None and a.cmd == "all":
        a.budget_after_voice = a.budget
    elif not hasattr(a, "budget_after_voice"):
        a.budget_after_voice = None
    kind, msg = None, None
    try:
        rc = a.func(a)
    except UsageError as exc:
        sys.stderr.write("参数错误：%s\n" % exc)
        rc, kind, msg = EXIT_USAGE, "usage", str(exc)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：%s\n" % exc)
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
