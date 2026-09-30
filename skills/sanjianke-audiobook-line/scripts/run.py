#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 有声书生产线（sanjianke-audiobook-line）。

给一本小说 / 一份长文本 → 一本**能听的有声书**：章节切分 → 逐章多音色朗读
（旁白 + 对白分角色）→ 章节音频 → 字级时间戳出 SRT / VTT 字幕 → 章节清单与时长台账。

子命令
    split     章节切分（**纯本地**，一次调用都不发）
    cast      识别对白 / 旁白并分配音色（本地正则，`--llm` 才用大模型）
    voice     逐章配音（先报价、断点续跑、分角色多音色）
    subtitle  字级时间戳出 SRT / VTT（走 voice_tts/stt）
    join      章节拼接 + 章节清单与时长台账
    all       整条链路（断点续跑）
    cost      只算钱，一次调用都不发
    voices    现查可用音色（配音要的 reference_id 从这里拿）
    models    现查 api.a7w.cn 在架模型（模型名会变，别写死）

真实端点（都在 api.a7w.cn 上；**开工前用 schema 现查，别照抄记忆**）
    大模型      POST https://api.a7w.cn/api/v1/chat/completions
    模型清单    GET  https://api.a7w.cn/api/v1/models
    配音（同步）POST https://api.a7w.cn/api/v1/apps/voice_tts/tts
    配音（异步）POST https://api.a7w.cn/api/v1/apps/voice_tts/tts_async
    音色列表    POST https://api.a7w.cn/api/v1/apps/voice_tts/list_voices
    语音识别    POST https://api.a7w.cn/api/v1/apps/voice_tts/stt
    任务轮询    GET  https://api.a7w.cn/api/v1/tasks/<task_id>

三条**实测确认过的**接口事实（本包开工前用 `python scripts/a7w.py schema voice_tts` 现查）
    1. 配音的音色参数叫 `reference_id`（值是 list_voices 返回的 model_id），
       **不叫 `voice_id`**。少一个字就是 400 / 音色不生效。
    2. `voice_tts/tts` 的 schema 原文是「同步接口建议不超过 500 字符」，
       所以逐块按 500 字硬上限拆；超长（>5000 字）自动改用 `tts_async`。
    3. **字级时间戳来自 `voice_tts/stt` 的 `ignore_timestamps: false`**：
       `result.segments` 每项是 `{text, start, end}`，中文实测**一字一段**
       （14 字 → 14 个 segment），正好是出 SRT / VTT 要的粒度。
       平台默认 `ignore_timestamps: true`，那一档 `segments` 是**空数组**。
       ⚠️ 回读文字与原文**不保证逐字一致**（实测 14 字里错 1 字），
       所以字幕默认用 ASR 回读文字（它与时间戳对齐），并另出一份对照文件登记差异。

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 scripts/run.py --help                     # 看用法
    python3 scripts/run.py voices --key <你的Key>
    Windows PowerShell:  $env:A7W_API_KEY="<你的Key>"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key <你的Key>）

七道本地硬闸门（都是**拦截**：标红 + stderr 汇总 + 退出码非 0，不是"提示一下"）
    1. 合规         广告法违禁词 + 音频平台红线；「最X」按可枚举语境豁免（见 _is_data_extreme）
    2. 占位符残留   `{}`、`[待填]`、`XXX`、`此处省略`、TODO
    3. prompt_echo  照抄提示词示例：去标点相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60
    4. 章节结构     切分后每章必须有标题与非空正文；**章数为 0 或存在空章 → 拦**
    5. 角色一致性   同一角色在全书中必须用同一个音色（本地可校验，零成本）
    6. 成本上限     配音 / 字幕跑前**必须报价**，且 --yes 或受 --budget 约束
    7. 产出位置     `--outdir` 落在包内 → exit=2（产出音频一律不许进包）

设计取舍
    · 闸门读的是**渲染后的产出本身**（在成品 Markdown 上正则重解析章节与角色），
      不采信任何自报的结构字段。吃过"只信自报值、闸门成假绿"的亏。
    · 结算只认 `usage.points_cost`。平台的 `pricing_matrix` / `tenant_*` 字段**半数不可信**，
      本包不拿它们算钱。
    · 缺失的单价不编：文本大模型单价平台不公开，`cost` 没给 `--points-per-ktok`
      就只报 token 数、不报金额。
    · **断点 key 含全部影响产出的维度**（正文全文 + 音色 reference_id + 模型 + 格式 +
      语速 prosody.speed + 采样率 + 比特率 + 端点 + 角色）。少任何一维都会导致
      "用户以为改了、其实静默复用旧音频"——同族包已实测踩过（提示词截断 24 字、
      `resolution` 不入 key、死参数三种形态）。本包第一版就把这一维做全。

用法示例
    python3 scripts/run.py split  --text novel.txt --outdir D:/book/b01
    python3 scripts/run.py cast   --outdir D:/book/b01 --outdir D:/book/b01
    python3 scripts/run.py voice  --outdir D:/book/b01 --sample-chars 200 --yes
    python3 scripts/run.py subtitle --outdir D:/book/b01 --yes
    python3 scripts/run.py join   --outdir D:/book/b01
    python3 scripts/run.py all    --text novel.txt --outdir D:/book/b01 --budget 3000
    python3 scripts/run.py cost   --chars 200000 --chapters 40
"""

import argparse
import hashlib
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
import wave
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
TASK_URL = a7w.HOST + "/api/v1/tasks/"          # 异步任务轮询（长文本配音）

APP_VOICE = "voice_tts"
TTS_ENDPOINT = "/api/v1/apps/voice_tts/tts"
TTS_ASYNC_ENDPOINT = "/api/v1/apps/voice_tts/tts_async"
VOICES_ENDPOINT = "/api/v1/apps/voice_tts/list_voices"
STT_ENDPOINT = "/api/v1/apps/voice_tts/stt"

# 实测可用：这个别名会路由到 deepseek-flash 一线。它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

STATE_NAME = "audiobook-state.json"
CHAPTERS_JSON = "chapters.json"
CHAPTERS_MD = "chapters.md"
CAST_JSON = "cast.json"
CAST_MD = "cast.md"
VOICE_INDEX = "index.json"
SUBTITLE_INDEX = "subtitle.json"

# 退出码（可直接用于 CI）
EXIT_OK = 0            # 全部干净
EXIT_USAGE = 2         # 参数/配置/环境错误（缺 --text、--outdir 指到包内、没报价就开跑）
EXIT_GATE = 3          # 有硬闸门命中（合规 / 占位符 / 照抄示例 / 章节结构 / 角色一致性）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名 / 音色 ID）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

# 平台计费口径：1 元 = 100 点（平台公开口径，1 点 = 0.01 元）。
# ⚠️ 这只是**换算**，不是单价。单价见下面四个实测常量。
POINTS_PER_YUAN = 100.0

# ---------------------------------------------------------------------------
# 实测单价（**只放我们真跑出来过的**，不搬平台 pricing_matrix / tenant_* 字段）
#
#   voice_tts/tts        50 点 / 千字   ← 6 组样本严格线性、无最低消费
#                                       （本包复测：15 字 = 0.75 点，一字不差）
#   voice_tts/stt        40 点 / 次     ← 与调用文本长度无关，按次计费
#   voice_tts/tts_async  与 tts 同价（按字数）
#   voice_tts/clone_voice 未实测，不在本包计费口径里（不报它的价，不编）
#
# 为什么把单价写成常量而不是现拉：平台 `GET /api/v1/pricing` 只覆盖少数接口，
# voice_tts 不在里面；`/api/v1/apps/<app>` 的 tenant_* 字段实测半数与结算价不一致。
# 所以本包用实测常量做报价，用 usage.points_cost 做对账：每次调用后把真实扣点打出来，
# 报价与实际不一致时明确报出来（见 _report_spend）。
# ---------------------------------------------------------------------------

TTS_POINTS_PER_1K_CHARS = 50.0
STT_POINTS_PER_CALL = 40.0

# 同步配音接口的平台建议上限：schema 原文「同步接口建议不超过 500 字符」。
# 超过就拆块；超长（>5000 字）自动改用 tts_async，见 draft_voice_chunks / do_tts。
TTS_SYNC_MAX_CHARS = 500
TTS_ASYNC_MIN_CHARS = 5000

# 默认输出的音频格式。schema 现查可选 wav / pcm / mp3 / opus，平台默认 mp3。
DEFAULT_FORMAT = "mp3"
DEFAULT_TTS_MODEL = "s2-pro"
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".pcm")


# ---------------------------------------------------------------------------
# 有声书规格表（**唯一事实来源**）
#
# 为什么做成表：语速、段落长度、音色池、字幕行长这些数字会变，而且提示词、闸门、
# 时长估算、字幕排版四处都要用同一个数。放一张表里，改口径只改这里，逻辑不动。
#
# 语速 250 字/分钟的依据：中文有声书**演播**（不是聊天）实测落在 230~280 字/分钟。
# 它同时是两条口径的来源，改它会同时改成本报价与时长闸门：
#   · 1 小时 ≈ 15000 字（≈「一章 20 分钟约 5000 字」）
#   · 200000 字（一本中篇）≈ 800 分钟 ≈ 13.3 小时
# 想按自己的演播节奏调就 `--chars-per-minute`。
# ---------------------------------------------------------------------------

BOOK = {
    "narrator_role": "旁白",
    "narrator_voice_hint": "沉稳男声",
    "chars_per_minute": 250,
    "duration_tolerance": 0.35,     # 字数估时长与目标偏离超过 ±35% 拦（演播比方差更大）
    "min_chapter_chars": 1,         # 一章正文至少 1 个非空白字符（空章直接拦）
    "max_heading_len": 40,          # 章标题超过 40 字基本是把正文当标题了
    "chapters": (1, 9999),
    # 字幕排版口径：一行最多多少字、一条字幕最多停留多少秒（长了要拆条）
    "subtitle_chars_per_line": 16,
    "subtitle_max_seconds": 8.0,
}

# `--chars-per-minute` 的运行时覆盖位。为什么不直接改 BOOK：
# BOOK 是**口径表**（只读的事实来源），命令行覆盖是**本次运行的选择**；
# 两者混在同一个字典里，下一次调用的默认值就被悄悄改掉了。
_CPM = {"v": None}


def cpm():
    return float(_CPM["v"] or BOOK["chars_per_minute"])


# ---------------------------------------------------------------------------
# 闸门一：合规自检（广告法违禁词 + 音频平台红线）
#
# 这是一道**粗筛**：宁可多报也别漏报，最终判断仍要人工复核，
# 且不等于任何平台的官方审核结论（官方标准不公开、会变）。
# 每项：正则 → 风险等级 → 人话解释 →（可选）语境判定标签
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    # 【比模板词表多三个词】`省` / `划算` / `实惠` 是口播里最常见的省钱类绝对化说法
    # （「最省钱的一套流程」），而模板词表里有「便宜」却没有「省」。
    # 加词只会让闸门更严、不会放松任何一处判定；这次扩表如实登记在此。
    (r"最(好|佳|优|低|便宜|省|划算|实惠|快|强|大|高|先进|新|流行|受欢迎|顶级|厉害)",
     "高", "广告法第九条禁止「最高级」用语", "superlative"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    # 【口径选择，与 multiplat-rewrite 有意不同】multiplat 用的是裸 `第一(?!次)`，
    # 在本包里会把正文里的「第一、第二」「第一步」「第一次」全判违规。小说与演播稿里
    # 枚举式表达是常态，误伤率太高（同族播客包被这条误拦过整篇）。
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

# 有声书特有的红线：**同一个表达在不同形态的内容里风险不一样**，所以单列一张表。
# 有声书是长音频 + 付费听书，口播里念出「加微信 / 私信我」比图文的违规概率更高
# （平台无法预审，上线后被投诉即下架），所以站外导流按「中」而不是「低」处理。
# 这张表是**经验口径**，不是任何有声书平台的官方审核标准。
AUDIO_REDLINES = [
    (r"加微信|微信号|加V|vx|VX|私信我|加我好友|扫码加", "中",
     "口播站外导流，音频类平台普遍限制；确有必要请人工确认后再录"),
    (r"点赞|收藏|关注我|订阅(一下|本书)|三连|打榜|投月票", "低",
     "诱导互动表述，部分平台会限流"),
    (r"付费(社群|群|专栏)|知识星球|会员群", "中",
     "二跳转化表述需与真实服务一致"),
]
AUDIO_REDLINE_RE = [(re.compile(p), lvl, why) for p, lvl, why in AUDIO_REDLINES]

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
# 小说里这个误伤只会更多：正文天然会写「最深的那道疤」「最慢的一步」。
# 豁免条件刻意做得很窄，只放过明确在说数据极值的形态：
#   · `最X` 前一个字是计量类名词（量/率/数/分/位/条/次/段/部/集/页/个/天/月/年）
#   · 且 `最X` 后面紧跟「的」或「之」
# 命中豁免时**整处放过**，但会在产出里登记下来（gates.compliance.exempted），
# 报告里会明说「本地放过了 N 处疑似绝对化用语」——**不静默放过**。
# 为什么不是「降级为低风险」：低风险在本包里同样拦截（与全库口径一致）。
#
# 豁免词表刻意**不含** `时`/`款`/`种`/`家`/`价`：
#   「课时最低的课程」「单价最低」都是真实的价格宣称形态，必须照拦。
# 句首不豁免：`before` 为空串时直接不认豁免（见 _is_data_extreme 的 `before and`）。
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
# 为什么单列一道闸门：长文本常常是别人给的模板或半成品，模型 / 编辑会把 `{主角名}`
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
# 举例只用**跨主题**的描述性说明；真实示例一律登记在 PROMPT_SAMPLES；
# 万一以后有人又把示例加回提示词，这道闸门兜住。
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
# 主题刻意选「旧书摊的收书账」，与三剪客真实业务主题（有声书 / 短剧 / 播客）明显不搭，
# 也和本包会产出的有声书内容（小说、演播）不搭——这样"命中"就一定是照抄，不是巧合。
PROMPT_SAMPLES = [
    "旧书摊的收书账，我记了整整三年",
    "先说结论：收旧书赚不赚钱，跟书的新旧不成正比",
    "我在旧书摊蹲了两年，收书这块踩过三个坑",
    "谈收书价之前没人告诉我，品相这一关才是最难过的",
    "三组数字说明，旧书摊的收书价没你想的那么低",
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

    **为什么不能只比整段**：一本有声书的正文有几十万字，而提示词示例只有二三十字。
    把整段正文拿去和示例算 Jaccard，分母被撑到几十万，相似度永远接近 0——
    也就是说**模型把示例原样抄进某一句，这道闸门完全看不见**。
    而「抄示例」在长文场景下恰恰就是「有几句是抄的」，不是整篇照抄。

    所以判定分两层：
      1. 整段比一次（兜住整篇照抄的极端情况），这一层**只认 exact / jaccard**：
         整段有几十万字，覆盖度在这里只能告诉你"正文里抄了一句"、指不出是哪一句
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
            why = ("正文里的「{}」有 {:.0f}% 的内容来自提示词示例「{}」"
                   "（覆盖度 ≥ {:.2f} 即判照抄；Jaccard 会随句子变长被摊薄）"
                   .format(seg[:20], score * 100, sample[:24], ECHO_CONTAIN))
        elif rule == "exact":
            why = "正文里的「{}」与提示词示例去掉标点后完全相同（照抄示例）".format(seg[:20])
        else:
            why = "正文里的「{}」与提示词示例相似度 {:.2f}，属同构照抄".format(seg[:20], score)
        hits.append({"part": label, "segment": seg[:40], "sim": round(score, 3),
                     "sample": sample, "why": why})
        break                      # 一处命中足够拦截，不用把整篇列完
    return hits


# 提示词卫生自检用的「脏东西」形态，**刻意比 PLACEHOLDER_RE 窄**。
#
# 事故复盘（写这个检查时踩到的）：直接把闸门二的 PLACEHOLDER_RE 拿来扫提示词，
# 结果本包自己的提示词被自己拦下了——因为提示词里为了说明输出结构写了
# `{no, title, speaker, text}` 这种字段说明，命中了 `[{}]` 这条规则。
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
# 闸门四：章节结构（本包**特有的核心形态闸门**）
#
# 为什么必须有：有声书与"一段长音频"的分水岭就是**章节**。听书的人靠章节跳转、
# 靠章节判断进度、平台靠章节做付费切分。一份切不出章节的长文本，配出来只是一条
# 几小时的音频——它不会报错、字数也对、读起来也顺，但**没法上架**。
# 这正是"闸门要拦的不是错误，而是表面上完全正确的错误"。
#
# 【为什么不采信自报的结构字段】这是本库吃过的亏：标题工坊上一版只信模型
# 自报的 formula 字段，闸门成了假绿。所以这里**只读渲染后的成品 Markdown**：
# 用正则在成品稿上重新解析章节标题与正文，解析不出标题的行、
# 或某一章正文为空 → 一律拦。
#
# 判定（全部命中才算过）：
#   · 章数 ≥ 1（切出来 0 章 = 没切动，等于后面全部白干）
#   · 每章都有**非空标题**（标题为空 = 把正文当标题吞了）
#   · 每章都有**非空正文**（空章 = 有目录没内容，听书时是一段静音）
#   · 章标题长度 ≤ max_heading_len（超过基本是标题识别错了）
# ---------------------------------------------------------------------------

# 成品稿里的章节标题形态：## 第 N 章　标题
CHAPTER_LINE_RE = re.compile(
    r"^##\s+(?P<no>[^\s　]{1,24})[　\s]+(?P<title>[^\n]*)$")


def parse_chapters_md(md_text):
    """从成品 Markdown 里解析出章节，返回 [{no, title, body}]。

    这是**闸门四的输入**：闸门读的永远是渲染后的成品稿，不是内存里的对象。
    """
    chapters, cur = [], None
    for raw in (md_text or "").splitlines():
        m = CHAPTER_LINE_RE.match(raw)
        if m:
            cur = {"no": m.group("no").strip(), "title": m.group("title").strip(),
                   "body": []}
            chapters.append(cur)
            continue
        if cur is not None:
            if raw.startswith("# "):
                continue                      # 下一级大标题：不属于本章正文
            cur["body"].append(raw)
    for c in chapters:
        c["body"] = "\n".join(c["body"]).strip()
    return chapters


def chapter_gate(md_text):
    """闸门四：成品稿里是不是**真的**有章节、且每章都有标题与正文。"""
    chapters = parse_chapters_md(md_text)
    empty_title = [c["no"] for c in chapters if not c["title"]]
    empty_body = [c["no"] for c in chapters if count_chars(c["body"]) < BOOK["min_chapter_chars"]]
    long_title = [c["no"] for c in chapters if len(c["title"]) > BOOK["max_heading_len"]]

    problems = []
    if len(chapters) == 0:
        problems.append("成品稿里**一章都没解析出来**（切不出章节 = 后面所有步骤都白干）。"
                        "检查原文本里的章节标题形态，或用 --heading-pattern 指定正则。")
    if empty_title:
        problems.append("有 %d 章**没有标题**（章号：%s）：标题为空会把正文吞进标题行"
                        % (len(empty_title), "、".join(str(x) for x in empty_title[:5])))
    if empty_body:
        problems.append("有 %d 章**正文为空**（章号：%s）：空章听出来就是一段静音，"
                        "有声书平台会直接判为残包"
                        % (len(empty_body), "、".join(str(x) for x in empty_body[:5])))
    if long_title:
        problems.append("有 %d 章标题超过 %d 字（章号：%s）：基本是把正文当标题了"
                        % (len(long_title), BOOK["max_heading_len"],
                           "、".join(str(x) for x in long_title[:5])))

    return {
        "ok": not problems,
        "problems": problems,
        "chapters": len(chapters),
        "empty_title": empty_title[:10],
        "empty_body": empty_body[:10],
        "long_title": long_title[:10],
        "chars": sum(count_chars(c["body"]) for c in chapters),
        "titles": ["%s　%s" % (c["no"], c["title"]) for c in chapters[:10]],
    }


# ---------------------------------------------------------------------------
# 闸门五：角色一致性（本包**第二道核心形态闸门**，与播客的对话稿结构同源）
#
# 为什么必须有：有声书的听感靠**音色认人**。同一个角色在两章里换了音色，
# 听众立刻跳戏；这不会报错、不会被平台拦、字数时长全对——
# 又是一个"表面上完全正确的错误"。
#
# 它同时又是一个**成本闸门**：音色一换就必须重配，重配就是重扣费。
# 所以这道闸门在配音**之前**就要过（零成本本地校验），而不是等配完才发现。
#
# 判定：
#   · 每个角色（含旁白）在全书里**只能对应一个 reference_id**
#   · 每个角色都必须真的出现了（分配了音色却没台词 = 白配一本的音色）
#   · 对白角色数 + 旁白 ≥ 1（纯旁白是允许的：单播有声书就是纯旁白）
# ---------------------------------------------------------------------------

def role_consistency_gate(cast):
    """闸门五：同一角色在全书中必须用同一音色。"""
    roles = cast.get("roles") or {}
    segs = cast.get("segments") or []
    seen = {}
    for s in segs:
        r = (s.get("role") or "").strip()
        v = (s.get("reference_id") or "").strip()
        if not r:
            continue
        seen.setdefault(r, set())
        if v:
            seen[r].add(v)
    conflicts = {r: sorted(vs) for r, vs in seen.items() if len(vs) > 1}
    unused = [r for r in roles if r not in seen]
    problems = []
    if conflicts:
        problems.append("角色音色不一致（同一个角色换了音色，听众会跳戏、且必须重配重扣）：%s"
                        % "；".join("「%s」→ %s" % (r, "、".join(vs))
                                    for r, vs in conflicts.items()))
    if unused:
        problems.append("分配了音色但全书没出现过的角色：%s（白占一个音色位）"
                        % "、".join(unused[:6]))
    if not seen:
        problems.append("全书没有解析出任何带角色的片段（cast 这一步没起作用）")
    return {"ok": not problems, "problems": problems,
            "roles": sorted(seen.keys()),
            "voice_map": {r: sorted(vs)[0] for r, vs in seen.items() if vs},
            "conflicts": conflicts, "unused_roles": unused}


# ---------------------------------------------------------------------------
# 闸门六：成本前置（报价 → --yes / --budget → 累计对账）
#
# 为什么报价与预算是**两道**而不是一道：
#   · 没有报价就开跑 = 用户不知道要花多少，被动扣费；
#   · 有报价没预算 = 报价算漏了（正文比预期长）就会一路花下去。
# 有声书尤其危险：一本中篇 20 万字 = 10000 点 = 100 元，
# 报价错一位数就是"睡一觉起来钱没了"。所以口径是：跑前必须报价，
# 且**要么 --yes 明确同意，要么 --budget 封顶**；两个都没有 → exit=2，一分钱都不花。
# 累计对账用**真实 usage.points_cost**，不是报价值；超了立刻停。
# ---------------------------------------------------------------------------

def quote_voice(chars, points_per_1k=None):
    rate = float(points_per_1k or TTS_POINTS_PER_1K_CHARS)
    pts = chars / 1000.0 * rate
    return {"item": "配音 voice_tts/tts", "chars": chars,
            "points_per_1k_chars": rate, "points": round(pts, 2),
            "yuan": round(pts / POINTS_PER_YUAN, 4)}


def quote_stt(calls, points_per_call=None):
    rate = float(points_per_call or STT_POINTS_PER_CALL)
    pts = max(0, int(calls)) * rate
    return {"item": "字级时间戳 voice_tts/stt", "calls": int(calls),
            "points_per_call": rate, "points": round(pts, 2),
            "yuan": round(pts / POINTS_PER_YUAN, 4)}


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
    """在任务结果里找产物地址——上游返回结构偶有差异，逐个试。"""
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


def read_text_any(path):
    """读文本文件：UTF-8 → UTF-8-BOM → GBK 依次试。

    中文小说 txt 有很大比例是 GBK，直接 UTF-8 读会得到一屏乱码，
    而乱码照样能过闸门（它只是"字符"）——所以这里必须试编码，且试不出就报错。
    """
    p = Path(path)
    if not p.is_file():
        raise UsageError("找不到文件：%s" % p)
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5", "utf-16"):
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    raise UsageError("读不出这个文本文件的编码（试过 utf-8 / gb18030 / big5 / utf-16）：%s" % p)


def safe_name(s):
    return re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", (s or "").strip())[:24] or "x"


def fmt_mmss(seconds):
    seconds = int(round(max(0.0, float(seconds))))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))


def fmt_srt_time(seconds):
    ms = int(round(max(0.0, float(seconds)) * 1000))
    h, rem = divmod(ms, 3600000)
    m, s = divmod(rem, 60000)
    sec, milli = divmod(s, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, sec, milli)


def fmt_vtt_time(seconds):
    return fmt_srt_time(seconds).replace(",", ".")


def fmt_minutes(m):
    if not m:
        return "未知"
    if m < 60:
        return "%d 分钟" % round(m)
    return "%d 小时 %d 分" % (int(m // 60), int(round(m % 60)))


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用 + 健壮 JSON 解析
# ---------------------------------------------------------------------------

class AudiobookError(a7w.A7wError):
    """生产 / 生成 / 调用失败（网络、鉴权、点数、模型名、音色）。→ 退出码 4"""


class UsageError(Exception):
    """参数/配置/环境用错了。→ 退出码 2

    为什么**不**继承 AudiobookError：这两类错误的**处理方式完全不同**。
    参数错了要改命令重跑，不花一分钱（比如 --outdir 指到包内、没报价就开跑）；
    调用失败要查 Key / 点数 / 模型名。混成一个退出码，CI 里就没法区分。
    也正因为不继承 a7w.A7wError，`_main` 的 except 顺序不会把它误吞成 exit=4。
    """


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
         max_tokens=4096, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见。
    一次章节目录识别的产出是几千字，被一次抖动打断要重跑整章，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。

    成功响应**不带 `code` 字段**（实测），所以这里不判 code；只判 choices 在不在。
    `code == 1` 那套信封是**生成应用**（voice_tts 等）的，不适用于本端点。
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
                raise AudiobookError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise AudiobookError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise AudiobookError(
                    "模型不存在（404）：{}  用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 429，{}s 后重试…\n".format(3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise AudiobookError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise AudiobookError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    if payload is None:
        raise AudiobookError("网络错误：{}".format(last_exc))

    # 兜底：万一网关换了形态包了一层 {"code":1,"data":{...}}，两种都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise AudiobookError("模型没返回 choices：{}".format(
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
    重复的 }），直接 json.loads 会炸。这里用 json.JSONDecoder().raw_decode()，
    从一个 { 或 [ 开始试解码，成功就返回，失败就往后挪一个字符接着试。
    """
    if not text:
        raise AudiobookError("模型返回空内容")
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
    raise AudiobookError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


# ---------------------------------------------------------------------------
# 生成应用调用（配音 / 语音识别）——code == 1 才是成功
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
        raise AudiobookError("{} {} 调用失败：{}".format(app, api, exc))


def do_tts(key, text, reference_id=None, fmt=DEFAULT_FORMAT, model=DEFAULT_TTS_MODEL,
           speed=None, sample_rate=None, mp3_bitrate=None, timeout=1800):
    """配音：短文本走同步 `voice_tts/tts`，超长走异步 `voice_tts/tts_async`。

    **实测参数名**（本包开工前用 `python scripts/a7w.py schema voice_tts` 现查确认）：
      · 音色是 `reference_id`（值是 list_voices 的 model_id），**不是 `voice_id`**
      · 格式参数叫 `format`，取值 wav / pcm / mp3 / opus，默认 mp3
      · 语速是 `prosody.speed`（对象），不是顶层 `speed`
      · 同步接口 schema 原文「建议不超过 500 字符」，所以按 TTS_SYNC_MAX_CHARS 分块；
        单块超过 TTS_ASYNC_MIN_CHARS 才切异步端点（异步支持约 10000 字符）
    """
    body = {"text": text, "model": model, "format": fmt}
    if reference_id:
        body["reference_id"] = reference_id
    prosody = {}
    if speed:
        prosody["speed"] = speed
    if prosody:
        body["prosody"] = prosody
    if sample_rate:
        body["sample_rate"] = int(sample_rate)
    if mp3_bitrate and fmt == "mp3":
        body["mp3_bitrate"] = int(mp3_bitrate)
    api = "tts_async" if len(text) > TTS_ASYNC_MIN_CHARS else "tts"
    try:
        return _call_app(APP_VOICE, api, body, key, wait=True, timeout=timeout)
    except AudiobookError as exc:
        if reference_id and "任务处理失败" in str(exc):
            raise AudiobookError(
                "%s\n  排查：这条错误最常见的成因是 **reference_id 不完整或不存在**——"
                "list_voices 返回的 id 是 32 位十六进制，抄短了就会得到这句"
                "「任务处理失败」。用 `run.py voices` 重新整条复制；"
                "去掉 --narrator-voice / --voice-map（不指定音色）可以立刻区分"
                "是音色问题还是文本问题。" % exc)
        raise


def do_stt(key, audio_url, language=None, timeout=1800):
    """字级时间戳：POST /api/v1/apps/voice_tts/stt（40 点/次，与文本长度无关）。

    **实测要点**（本包开工前 schema 现查 + 真机验证）：
      · 参数是 `audio_url`（公网可访问地址；本包用配音返回的 audio_url，不重复上传）
      · `ignore_timestamps` 默认 **true**，那一档 `result.segments` 是**空数组**
      · 要字级时间戳必须显式传 `ignore_timestamps=False`：
        实测 14 个汉字的音频 → 14 个 segment，每项 `{text, start, end}`，**一字一段**
      · `result.duration` / `result.language` / `result.text` 一并返回
    """
    body = {"audio_url": audio_url, "ignore_timestamps": False}
    if language:
        body["language"] = language
    return _call_app(APP_VOICE, "stt", body, key, wait=True, timeout=timeout)


def list_voices(key, tag=None, title=None, language=None, page_size=20, page_number=1):
    """POST /api/v1/apps/voice_tts/list_voices → 音色列表（同步，不扣点）。"""
    body = {"page_size": page_size, "page_number": page_number}
    if tag:
        body["tag"] = tag
    if title:
        body["title"] = title
    if language:
        body["language"] = language
    res = _call_app(APP_VOICE, "list_voices", body, key, wait=True, timeout=120)
    result = res.get("result") if isinstance(res, dict) else None
    lst = None
    for holder in (result, res):
        if isinstance(holder, dict):
            for k in ("items", "data", "list", "voices"):
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
    """取前 N 个可用音色（看不上就用 --narrator-voice / --voice-map 手动指定）。"""
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


def render_chapters_md(chapters, meta=None):
    """把章节列表渲染成**成品 Markdown**。

    这个渲染结果不是给人看的副产品——闸门四读的就是它。
    改这里的格式等于改闸门的输入，必须同步改 CHAPTER_LINE_RE。
    """
    meta = meta or {}
    out = ["# 章节切分 · %s" % (meta.get("title") or "未命名"), ""]
    if meta.get("source"):
        out.append("> 源文件：`%s`（编码 %s）" % (meta["source"], meta.get("encoding") or "-"))
    out.append("> 共 %d 章　正文 %d 字　切分方式：%s"
               % (len(chapters), sum(count_chars(c["body"]) for c in chapters),
                  meta.get("method") or "-"))
    if meta.get("heading_pattern"):
        out.append("> 章节标题正则：`%s`" % meta["heading_pattern"])
    out.append("")
    for c in chapters:
        out.append("## %s　%s" % (c["no"], c["title"]))
        out.append("")
        out.append(c["body"])
        out.append("")
    return "\n".join(out)


def render_cast_md(cast, meta=None):
    """把角色分配渲染成成品 Markdown（闸门五读的就是它的结构化版本）。"""
    meta = meta or {}
    out = ["# 角色与音色分配 · %s" % (meta.get("title") or "未命名"), ""]
    out.append("> 片段 %d 个　对白 %d 个　旁白 %d 个"
               % (cast.get("segment_count") or 0,
                  cast.get("dialogue_count") or 0,
                  cast.get("narration_count") or 0))
    out.append("> 识别方式：%s" % (meta.get("method") or "-"))
    out.append("")
    out.append("| 角色 | 类型 | 音色 reference_id | 片段数 | 字数 |")
    out.append("|---|---|---|---|---|")
    for r, info in sorted((cast.get("roles") or {}).items()):
        out.append("| %s | %s | `%s` | %s | %s |"
                   % (r, info.get("kind") or "-", info.get("reference_id") or "-",
                      info.get("segments") or 0, info.get("chars") or 0))
    out.append("")
    out.append("| # | 章 | 角色 | 类型 | 字数 | 正文（截断 40 字） |")
    out.append("|---|---|---|---|---|---|")
    for s in (cast.get("segments") or [])[:200]:
        out.append("| %s | %s | %s | %s | %s | %s |"
                   % (s.get("order"), s.get("chapter"), s.get("role"),
                      s.get("kind"), s.get("chars"),
                      (s.get("text") or "").replace("|", "丨")[:40]))
    return "\n".join(out)


def render_subtitle_md(rows, meta=None):
    """时间轴 / 字幕台账（人读版）。"""
    meta = meta or {}
    out = ["# 字级时间轴台账", ""]
    out.append("- 章节：%d 个　音频片段：%d 个" % (meta.get("chapters") or 0,
                                                  meta.get("segments") or 0))
    out.append("- 字幕条数：%d 条　总时长：%s" % (meta.get("cues") or 0,
                                                 fmt_mmss(meta.get("duration") or 0)))
    out.append("- 端点：`POST %s`（40 点/次，与文本长度无关）" % STT_ENDPOINT)
    out.append("- 计时依据：上游 `result.segments` 的**真实字级时间戳**，不是按字数估算")
    out.append("")
    out.append("| 章 | 片段 | 起点 | 终点 | 时长 | 字幕条数 |")
    out.append("|---|---|---|---|---|---|")
    for r in meta.get("by_segment") or []:
        out.append("| %s | %s | %s | %s | %s | %s |"
                   % (r.get("chapter"), r.get("order"), fmt_mmss(r.get("start") or 0),
                      fmt_mmss(r.get("end") or 0),
                      fmt_mmss((r.get("end") or 0) - (r.get("start") or 0)),
                      r.get("cues")))
    out.append("")
    if meta.get("mismatches"):
        out.append("> ⚠️ 有 %d 个片段的 ASR 回读文字与原文**不完全一致**"
                   "（语音识别本身有误差，属上游能力边界，不是本包 bug）。"
                   "字幕默认用 ASR 回读文字（它与时间戳对齐）；"
                   "差异登记见 `subtitle.json` 的 `text_mismatch`。" % len(meta["mismatches"]))
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 提示词构造（只有 `cast --llm` 与 `split --llm` 会用到大模型）
#
# 【铁律】提示词里**不许出现任何一句可直接复制的完整中文句子**。
# 举例只用描述性说明，真实示例一律登记在 PROMPT_SAMPLES，
# 并由 prompt_hygiene() 在 --dry-run 时自检。
# 依据见上面 prompt_echo 的事故复盘：模型会照抄示例，哪怕标着"这是错的写法"。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是三剪客的有声书制作人，做过大量中文小说的多人演播。"
    "你只输出 JSON，不输出任何解释、前言、Markdown 代码块围栏之外的文字。"
    "你只做**标注**，不改写、不增删、不润色一个字：输出里的文本必须与输入逐字一致。"
    "禁止编造输入里没有的人名、机构名、论文名、基金名、真实数据。"
)


def build_cast_prompt(title, body, known_roles):
    """让模型只做「切段 + 标角色」，不改一个字。

    【为什么限制成"只标注"】音频是逐字念出来的。只要模型顺手润色了一个字，
    字幕、正文、音频三者就对不上了，而且**肉眼看不出来**。
    所以这里的硬约束是「输出文本必须与输入逐字一致」，并在本地用
    `cast_md5` 校验（模型返回的片段拼起来归一化后必须与输入一致，不一致就报错）。
    """
    return "\n".join([
        "请把下面这一章的正文切成朗读片段，并给每个片段标注说话人。",
        "",
        "章标题：%s" % title,
        "已知角色（可能不全，也不知道谁出场了）：%s" % ("、".join(known_roles) or "（未知）"),
        "",
        "规则：",
        "  · 每个片段要么是旁白，要么是某个角色的台词；片段文本**必须与原文逐字一致**",
        "  · 只切分与标注，**不许改写、不许增删、不许合并**任何一个字",
        "  · 片段按出现顺序排列，拼起来必须等于原文（去掉换行后逐字相等）",
        "  · 引号里的话算台词；引号外叙述性文字算旁白",
        "  · 说话人从上下文推断（谁说的话、谁在回答）；无法确定就标成旁白",
        "  · 角色名用原文里出现过的称呼，不要自己起代号",
        "",
        "输出 JSON 对象，字段：",
        '  segments  数组，每项 {speaker, text}',
        '            speaker 是角色名，旁白固定写成「旁白」',
        '            text 是这一段的原文（逐字一致）',
        "",
        "再次强调：只输出这个 JSON 对象；text 必须与原文逐字一致。",
    ])


def normalize_cast(raw, body):
    """把模型返回的片段收拾成内部结构，并**校验逐字一致**。"""
    segs = (raw or {}).get("segments")
    if not isinstance(segs, list) or not segs:
        raise AudiobookError("模型没有返回 segments")
    out = []
    for s in segs:
        if not isinstance(s, dict):
            continue
        text = str(s.get("text") or "").strip()
        if not text:
            continue
        out.append({"speaker": str(s.get("speaker") or BOOK["narrator_role"]).strip(),
                    "text": text})
    if not out:
        raise AudiobookError("模型返回的 segments 里没有可用文本")
    joined = _norm_for_echo("".join(s["text"] for s in out))
    origin = _norm_for_echo(body)
    if joined != origin:
        raise AudiobookError(
            "模型把原文改了：片段拼起来与原文不逐字一致"
            "（原文 %d 字，返回 %d 字）。这道校验是故意的——音频是逐字念的，"
            "改一个字就会让字幕与音频对不上，而且肉眼看不出来。"
            "重跑一次，或改用本地分词（去掉 --llm）。" % (len(origin), len(joined)))
    return out


# ---------------------------------------------------------------------------
# 章节切分（纯本地）
#
# 事故复盘驱动的五条规则（都是真机读中文小说踩出来的）：
#   1. **行首锚定**：`^` 必须带上。正文里写「他翻到第一章」太常见了，
#      不锚行首会把每一句提到章节名的话都当成标题。
#   2. **标题行要短**：超过 40 字基本是正文被吞进来了（见 max_heading_len）。
#   3. **标题行不带句末标点**：`第一章　他说，算了。` 是正文不是标题。
#   4. **前缀正文归第一章**：标题之前的书名 / 作者 / 简介不能丢，
#      归到第一个真章节的开头（丢了就是静默丢内容）。
#   5. **没有标题也要能切**：`--heading-pattern` 兜底；
#      连模式都没有时按空行分块（`--chunk-blocks`），并**如实登记**
#      "这是按段落切、不是按作者章节切"，不假装切对了。
# ---------------------------------------------------------------------------

# 章节标题形态（按优先级）。每种都必须**行首锚定**且标题部分足够短。
CHAPTER_PATTERNS = [
    # 第1章 / 第一章 / 第 1 章　标题 / 第1节 第1回 第1卷 第1部 第1篇 第1话 第1集
    (r"^\s*第\s*([0-9０-９零一二三四五六七八九十百千两]{1,12})\s*"
     r"[章回节卷部篇话集]\s*[　:：\.、,，\-—]?\s*(\S.*)?$", "第N章"),
    # Chapter 1 / CHAPTER 12
    (r"^\s*(?:Chapter|CHAPTER|Chapter|Ch\.)\s*([0-9]{1,4})\s*[:：\.]?\s*(\S.*)?$", "Chapter N"),
    # 纯数字标题行：1. 标题 / 1、标题 / 01 标题（要求后面有非空标题文字）
    (r"^\s*([0-9]{1,4})\s*[\.、,，:：]\s*(\S.*)$", "N. 标题"),
    # 卷一 / 卷之一 / 上部
    (r"^\s*(卷[之]?[0-9０-９零一二三四五六七八九十百千两]{1,6}|上[部篇]|中[部篇]|下[部篇])"
     r"\s*[　:：\.、]?\s*(\S.*)?$", "卷/部"),
    # 楔子 / 序章 / 序 / 引子 / 尾声 / 后记 / 番外 / 终章 / 大结局
    (r"^\s*(楔子|序章|序言|序|引子|前言|尾声|终章|结局|大结局|后记|番外[0-9一二三四五六七八九十]*|"
     r"附录[0-9一二三四五六七八九十]*)\s*[　:：\.]?\s*(\S.*)?$", "特殊章"),
]
# 标题行**不许**带句末标点（带了就是正文）
_HEADING_STOP_PUNCT = "。！？!?；;…"


def _compile_heading_patterns(explicit=None):
    if explicit:
        try:
            return [("自定义", re.compile(explicit))]
        except re.error as exc:
            raise UsageError("--heading-pattern 不是合法正则：%s" % exc)
    return [(name, re.compile(rx)) for rx, name in CHAPTER_PATTERNS]


def detect_chapters(text, explicit_pattern=None):
    """找出所有章节标题行，返回 (hits, pattern_name)。

    hits 每项 {line, title, matched_text}，按出现顺序；`line` 是 0 基行号。
    """
    patterns = _compile_heading_patterns(explicit_pattern)
    lines = (text or "").splitlines()
    best_hits, best_name = [], None
    for name, rx in patterns:
        hits = []
        for i, raw in enumerate(lines):
            s = raw.strip()
            if not s or len(s) > BOOK["max_heading_len"] + 24:
                continue
            if s[-1] in _HEADING_STOP_PUNCT:
                continue
            m = rx.match(s)
            if not m:
                continue
            groups = [g.strip() for g in m.groups() if g and g.strip()]
            if not groups:
                continue
            title = groups[-1] if len(groups) > 1 else ""
            label = groups[0] if len(groups) > 1 else groups[0]
            # 形如 `第一章` 后面什么都没有：title 为空，用 label 兜
            disp = title or ("" if label == groups[0] and len(groups) > 1 else label)
            hits.append({"line": i, "label": label, "title": disp, "raw": s})
        # 多章才算切动；只有一个命中可能只是正文里提了一次
        if len(hits) > len(best_hits):
            best_hits, best_name = hits, name
    return best_hits, best_name


def split_text(text, explicit_pattern=None, chunk_blocks=False):
    """把长文本切成章节，返回 (chapters, method, pattern_name)。

    chapters 每项 {no, title, body}；`no` 是**从 1 开始的序号**（不是原文里的章号，
    因为原文的章号可能是汉字、可能跳号、可能重复）。
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    hits, name = detect_chapters(text, explicit_pattern)
    lines = text.splitlines()
    chapters = []
    if len(hits) >= 2:
        head = "\n".join(lines[:hits[0]["line"]]).strip()
        for idx, h in enumerate(hits):
            end = hits[idx + 1]["line"] if idx + 1 < len(hits) else len(lines)
            body = "\n".join(lines[h["line"] + 1:end]).strip()
            title = h["title"] or h["raw"]
            if idx == 0 and head:
                # 规则 4：标题之前的书名 / 作者 / 简介归到第一章，不丢
                body = (head + "\n\n" + body).strip()
            chapters.append({"no": idx + 1, "label": h["label"], "title": title,
                             "body": body, "raw_heading": h["raw"]})
        return chapters, "标题识别（%s）" % name, name

    if chunk_blocks:
        blocks, cur = [], []
        for raw in lines:
            if raw.strip():
                cur.append(raw)
            elif cur:
                blocks.append("\n".join(cur).strip())
                cur = []
        if cur:
            blocks.append("\n".join(cur).strip())
        for i, b in enumerate(blocks, 1):
            first = b.splitlines()[0].strip()
            title = first[:BOOK["max_heading_len"]] or ("第 %d 段" % i)
            body = "\n".join(b.splitlines()[1:]).strip() or first
            chapters.append({"no": i, "label": "", "title": title, "body": body,
                             "raw_heading": first})
        return chapters, "按空行分块（**不是**按作者章节切，请人工确认）", "blocks"

    # 一整篇，不切
    body = text.strip()
    if not body:
        return [], "空文本", None
    first = body.splitlines()[0].strip()
    return [{"no": 1, "label": "", "title": first[:BOOK["max_heading_len"]],
             "body": body, "raw_heading": ""}], "未识别到章节标题，整体作为一章", None


# ---------------------------------------------------------------------------
# 对白 / 旁白切分（本地正则，零成本）
#
# 中文小说的对白有明确的标点形态：`「…」` `“…”` `‘…’`。旁白就是引号外的文字。
# 说话人归属是**启发式**：看引号**前**紧邻的 `某某说/道/问/答`，
# 再看引号**后**的 `，某某说`。两条都没有 → 归"未知角色"，由 --voice-map 兜。
#
# 【为什么说话人不用大模型也能做】这只影响**音色分配**，不影响正文与音频长度。
# 启发式做不对的代价是"某个配角用了旁白音色"，而不是"内容错了"。
# 所以默认走本地（零成本、可复现）；要更准就 `--llm`，代价是逐章一次大模型调用。
# 事故复盘（本地分词第一版）：把 `「你好」他说` 里的「他说」也算进了对白文本，
# 于是音频里念出了"他说"两个字——对白文本必须**只取引号内部**，引号外全归旁白。
# ---------------------------------------------------------------------------

QUOTE_PAIRS = (("「", "」"), ("“", "”"), ("‘", "’"), ("『", "』"), ("《", "》"))
# 说话动词。按长度从长到短排在正则里（正则交替是"先匹配先赢"，
# `道` 放前面会把 `说道` 切掉一半，得到空说话人——写在这里免得下次又踩）。
SPEAK_VERBS = ("开口问道", "开口问", "应声道", "回答道", "反问", "追问", "问道", "说道",
               "喝道", "念道", "应道", "笑道", "叹道", "低声道", "轻声道", "沉声道",
               "嘀咕", "嘟囔", "低语", "开口", "回答", "低声", "大声", "冷冷地",
               "笑着", "缓缓", "轻轻", "接着说", "又说", "才说", "便说", "就说",
               "说", "道", "问", "答", "喊", "叫", "叹", "笑")
_SPEAK_ALT = "|".join(SPEAK_VERBS)
# 引号**前**的说话人引导：`林砚说：` / `老人笑着` / `「他」` 由调用方补
SPEAK_BEFORE_RE = re.compile(
    r"([\u4e00-\u9fff]{1,8})\s*(?:又|才|便|就|忽然|突然|轻轻|低声|大声|冷冷地|"
    r"笑着|沉声|缓缓|开口|接着|随后|终于|只好)?\s*(?:%s)\s*[：:]?\s*$" % _SPEAK_ALT)
# 引号**后**的说话人引导：`」老人说。` / `」林砚把伞收起来` 之后再由归属规则裁决
SPEAK_AFTER_RE = re.compile(r"^[，,。.、；;]?\s*([\u4e00-\u9fff]{1,8})\s*(?:%s)" % _SPEAK_ALT)
# 引号后紧跟「某某做某事」：也算引号**前**那句话的首选说话人（同句内的旁白主语）
ACTION_AFTER_RE = re.compile(r"^[，,。.、；;]?\s*([\u4e00-\u9fff]{1,8}?)(?:把|将|从|向|对|拿|点|摇|皱|转|站|坐|走|看|抬|低|伸|收|放)")
# 称谓：不能当稳定角色名，但可以作为音色槽
TITLE_WORDS = ("老人", "男人", "女人", "男孩", "女孩", "青年", "老者", "老太太", "大爷",
               "大妈", "少年", "少女", "孩子", "小孩", "中年人", "陌生人", "客人",
               "老板", "掌柜", "师父", "师傅", "医生", "护士", "警察", "士兵",
               "母亲", "父亲", "妈妈", "爸爸", "爷爷", "奶奶", "哥哥", "姐姐",
               "弟弟", "妹妹", "儿子", "女儿", "妻子", "丈夫")
# 代词 / 泛称：不能当角色名
PRONOUN_SPEAKERS = {"我", "你", "他", "她", "它", "我们", "你们", "他们", "她们",
                    "大家", "众人", "有人", "那人", "此人", "对方", "自己",
                    "两人", "二人", "众人", "所有人"}


def _clean_speaker(name):
    """把正则抠出来的说话人收拾成角色名。

    两个必须处理的形态（都是实测踩出来的）：
      · 正则的 `{1,8}` 会把前面的**旁白也吃进来**（`林砚把伞收起来。老人说` → `伞收起来。老人`）
        → 取最后一个标点之后的片段
      · 中文动词紧贴在名字后面会被一起吃进来（`林砚把` → `林砚`）
        → 逐个剥掉尾部的动词 / 助词
    """
    if not name:
        return None
    name = re.split(r"[，,。.、；;！!？?：:\s「」“”‘’]", name)[-1].strip()
    if not name:
        return None
    # 剥尾部动词 / 助词（最多剥 2 层：`把伞收起来` 这种要靠 ACTION_AFTER_RE 先切）
    for _ in range(3):
        cut = False
        for v in sorted(SPEAK_VERBS, key=len, reverse=True):
            if len(name) > 1 and name.endswith(v):
                name = name[:len(name) - len(v)]
                cut = True
                break
        if not cut:
            break
    for tail in ("把", "将", "的", "了", "着", "地", "得", "又", "才", "便", "就"):
        if len(name) > 1 and name.endswith(tail):
            name = name[:-1]
    if not name or name in PRONOUN_SPEAKERS:
        return None
    if len(name) > 6:
        name = name[-3:]
    return name


def _speaker_before(prefix, prev_speaker=None):
    """引号前的引导词 → 说话人。

    【极性规则】`「…」老人说` 里的 `老人` 是**上一句**的说话人，
    不能拿来当**这一句**（引号里的内容）的说话人——
    事故复盘：本包第一版把 `老人说` 之前的 `林砚` 归给了后一句
    `「那本书还在吗？」`，于是主角的台词配了配角的声音，
    而结果是"看起来完全正常"的一份角色表。
    所以：引号前若同时存在 `A说` 与更前面的 `B…`，
    只有**紧贴引号**的那个引导词才算当前说话人；带句号的引导词一律不算
    （`老人说。` 结尾是句号 = 那句已经讲完了）。
    """
    m = SPEAK_BEFORE_RE.search(prefix)
    if m:
        return _clean_speaker(m.group(1))
    return None


def _speaker_after(suffix):
    """引号后的引导词 → 说话人（`」老人说` 这种）。"""
    m = SPEAK_AFTER_RE.match(suffix)
    if m:
        name = _clean_speaker(m.group(1))
        if name:
            return name
    m = ACTION_AFTER_RE.match(suffix)
    if m:
        name = _clean_speaker(m.group(1))
        if name:
            return name
    return None


def split_dialogue_local(body):
    """把一个章节的正文切成 (speaker, text, kind) 片段列表（纯本地、零成本）。

    kind 是 "dialogue" 或 "narration"；speaker 为 None 表示旁白。

    【说话人归属规则（两轮）】
      第一轮：逐处引号独立判定——
        · 引号前紧贴引导词 → 用它
        · 引号后紧跟引导词  → 用它
        · 引号前是**人物动作**（`林砚把伞收起来，`）→ 用动作主语
        · 都没有 → 记 None，进第二轮
      第二轮：对 None 的引号，做**同段内的前后一致性推断**：
        · 段内已经出现过说话人，且**只有一个**候选 → 用它
          （中文小说的对话段基本是两个人一来一回，段内候选唯一时这个推断很稳）
        · 段内有多个候选 → 保持 None（宁可不猜，也不猜错：
          猜错等于给主角配了配角的声音，而且**结果看起来完全正常**）
      归 None 的引号会归到旁白并在产出里**登记数量**（cast.unassigned_speakers），
      要更准就 `--llm`。这里不静默丢掉任何一个字。
    """
    body = body or ""
    segs = []
    i, n = 0, len(body)
    buf = []
    pending = []          # 待定说话人的引号（第二轮处理）

    def flush_narration():
        if buf:
            t = "".join(buf).strip()
            if t:
                segs.append({"speaker": None, "text": t, "kind": "narration"})
            buf.clear()

    while i < n:
        ch = body[i]
        pair = next((p for p in QUOTE_PAIRS if p[0] == ch), None)
        if not pair:
            buf.append(ch)
            i += 1
            continue
        close = body.find(pair[1], i + 1)
        if close == -1:
            buf.append(ch)
            i += 1
            continue
        # 对白文本**只取引号内部**（引号外全归旁白——事故复盘见上）
        inner = body[i + 1:close].strip()
        prefix = "".join(buf)[-24:]
        suffix = body[close + 1:close + 20]
        spk = _speaker_before(prefix) or _speaker_after(suffix)
        flush_narration()
        if inner:
            entry = {"speaker": spk, "text": inner, "kind": "dialogue"}
            segs.append(entry)
            if not spk:
                pending.append(entry)
        i = close + 1
    flush_narration()

    # 第二轮：段内一致性推断（只在前一轮没结论的引号上做）
    if pending:
        resolved = []
        for s in segs:
            if s["kind"] == "dialogue" and s["speaker"] and s["speaker"] not in resolved:
                resolved.append(s["speaker"])
        if len(resolved) == 1:
            for e in pending:
                e["speaker"] = resolved[0]
        elif len(resolved) > 1:
            # 多个候选：用"离得最近的已判定说话人"（对话是一来一回，
            # 刚才说话的人很可能就是下一句那个推不出来的说话人）
            last = None
            pending_ids = {id(e) for e in pending}
            for s in segs:
                if s["kind"] != "dialogue":
                    continue
                if s["speaker"]:
                    if id(s) not in pending_ids:
                        last = s["speaker"]
                elif last:
                    s["speaker"] = last
    return segs


def split_dialogue_llm(key, title, body, known_roles, model=DEFAULT_MODEL,
                       temperature=0.2, timeout=600, max_tokens=8192):
    """用大模型做切段 + 标注（`--llm`）。返回 (speaker, text, kind) 片段列表。"""
    prompt = build_cast_prompt(title, body, known_roles)
    hygiene = prompt_hygiene(SYSTEM_PROMPT + "\n" + prompt)
    if hygiene:
        raise UsageError("提示词卫生自检失败：提示词里混进了可照抄的示例/占位符（%s）。"
                         "这是本包的红线，请改提示词。"
                         % json.dumps(hygiene, ensure_ascii=False))
    content, usage = chat(prompt, SYSTEM_PROMPT, model=model, temperature=temperature,
                          max_tokens=max_tokens, key=key, timeout=timeout)
    segs = normalize_cast(parse_first_json(content), body)
    return [{"speaker": None if s["speaker"] == BOOK["narrator_role"] else s["speaker"],
             "text": s["text"],
             "kind": "narration" if s["speaker"] == BOOK["narrator_role"] else "dialogue"}
            for s in segs], usage


# ---------------------------------------------------------------------------
# 产出口径：音频 / 字幕的断点 key
#
# 【这是本包最容易出错、也最贵的一处】
# 断点 key 必须含**全部影响产出的维度**。少一维的后果不是报错，而是
# 「用户以为改了、其实静默复用了旧产物」——用户听到的还是旧音色 / 旧语速，
# 但命令行的输出一切正常。同族包已实测踩过三种形态：
#   · 提示词截断到 24 字 → 改了提示词第 25 字之后，key 没变，静默复用旧图
#   · `resolution` 不入 key → 用户从 1K 改到 4K，拿回的还是 1K 的图
#   · 死参数 → 参数在命令行存在、在 key 里不存在，改了什么都不会变
# 所以本包把 key 做成**显式白名单**，并在 README / SKILL.md 里逐维登记。
# 新增任何影响音频的参数，都必须同时加进 VOICE_KEY_FIELDS 并登记到文档里。
# 文本维度**不截断**（全文入 hash）。
# ---------------------------------------------------------------------------

# 影响音频产出的维度（缺一不可）
VOICE_KEY_FIELDS = (
    "text",           # 正文全文（**不截断**）
    "role",           # 角色名（换角色 = 换音色 = 必须重配）
    "reference_id",   # 音色（值本身；空字符串代表平台默认音色，与"指定了音色"是两回事）
    "model",          # TTS 模型（s1 / s2-pro 音色表现不同）
    "format",         # mp3 / wav / pcm / opus（拿 wav 的脚本拿到 mp3 会静默出错）
    "speed",          # prosody.speed
    "sample_rate",    # 采样率
    "mp3_bitrate",    # MP3 比特率
    "endpoint",       # tts / tts_async（上游不同实现，产物不同）
    "chapter",        # 归属章节（决定 join 的拼接顺序）
    "part",           # 同章同角色被 500 字上限拆开后的第几块
)


def voice_sig(**kw):
    """算一个音频片段的断点指纹。

    用 JSON + sha256，字段名与值都入 hash：改任何一维都换 key。
    `None` 统一成 "null"，避免 `speed=None` 与 `speed=0` 撞在一起。
    """
    payload = {k: ("null" if kw.get(k) is None else str(kw.get(k)))
               for k in VOICE_KEY_FIELDS}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


# 影响字幕产出的维度
SUBTITLE_KEY_FIELDS = ("audio_sig", "language", "ignore_timestamps",
                       "chars_per_line", "max_seconds", "endpoint")


def subtitle_sig(**kw):
    payload = {k: ("null" if kw.get(k) is None else str(kw.get(k)))
               for k in SUBTITLE_KEY_FIELDS}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def text_hash(s):
    """片段指纹：用标准库 hashlib（不引第三方）。"""
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


def draft_voice_chunks(cast, sample_chars=0):
    """把角色片段组织成配音任务列表。

    切法：**同一章内、同一角色的连续片段合成一块**（≤500 字）。
    为什么不每句一块：实测配音无最低消费（50 点/千字严格线性），
    合并不会多花钱，但能把调用次数从几万次压到几百次——
    调用次数直接决定失败率与重试成本，而一本中篇的台词条数是以万计的。
    """
    chunks, used = [], 0
    by_chapter = {}
    for s in cast.get("segments") or []:
        by_chapter.setdefault(s.get("chapter"), []).append(s)
    for chapter in sorted(by_chapter, key=lambda x: (x is None, x)):
        cur = None
        for s in by_chapter[chapter]:
            text = (s.get("text") or "").strip()
            role = (s.get("role") or "").strip()
            rid = (s.get("reference_id") or "").strip()
            if not text or not role:
                continue
            if sample_chars and used >= sample_chars:
                break
            if sample_chars and used + len(text) > sample_chars:
                text = text[:max(0, sample_chars - used)]
            if not text:
                break
            used += len(text)
            if cur and cur["role"] == role and cur["reference_id"] == rid and \
                    len(cur["text"]) + len(text) <= TTS_SYNC_MAX_CHARS:
                cur["text"] += text
                cur["lines"] += 1
                cur["sources"] += 1
                continue
            cur = {"chapter": chapter, "role": role, "reference_id": rid,
                   "text": text, "lines": 1, "sources": 1}
            chunks.append(cur)
        if sample_chars and used >= sample_chars:
            break
    # 逐块再按 500 字硬上限拆开
    final = []
    for ch in chunks:
        for i, piece in enumerate(split_long_text(ch["text"]) or [""]):
            final.append({"chapter": ch["chapter"], "role": ch["role"],
                          "reference_id": ch["reference_id"], "text": piece,
                          "part": i + 1, "sources": ch["sources"]})
    for i, ch in enumerate(final, 1):
        ch["order"] = i
        ch["chars"] = len(ch["text"])
        ch["key"] = "voice:%04d" % i
    return final


def voice_task_sig(ch, fmt=DEFAULT_FORMAT, model=DEFAULT_TTS_MODEL, speed=None,
                   sample_rate=None, mp3_bitrate=None):
    """一个配音任务的断点指纹——**含全部影响产出的维度**（见 VOICE_KEY_FIELDS）。"""
    endpoint = TTS_ASYNC_ENDPOINT if len(ch["text"]) > TTS_ASYNC_MIN_CHARS else TTS_ENDPOINT
    return voice_sig(text=ch["text"], role=ch["role"],
                     reference_id=ch["reference_id"], model=model, format=fmt,
                     speed=speed, sample_rate=sample_rate, mp3_bitrate=mp3_bitrate,
                     endpoint=endpoint, chapter=ch["chapter"], part=ch["part"])


# ---------------------------------------------------------------------------
# 闸门执行：对一份成品产出跑全部本地检查
# ---------------------------------------------------------------------------

def compliance_scan(text, audio_redlines=True):
    """扫违禁词 + 音频平台红线。

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
    if audio_redlines:
        for rx, lvl, why in AUDIO_REDLINE_RE:
            m = rx.search(text)
            if m:
                hits.append({"word": m.group(0), "level": lvl, "why": why,
                             "scope": "音频口播红线"})
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


def text_gates(text, label="正文"):
    """闸门一 / 二 / 三：对任意一段产出跑合规 + 占位符 + 照抄示例。"""
    scan = compliance_scan(text)
    ph = placeholder_scan(text)
    echoes = prompt_echo_scan(text, label=label)
    g = {
        "compliance": {"ok": not scan["hits"], "hits": scan["hits"],
                       "exempted": scan["exempted"]},
        "placeholder": {"ok": not ph, "hits": ph},
        "prompt_echo": {"ok": not echoes, "hits": echoes},
    }
    g["ok"] = all(g[k]["ok"] for k in ("compliance", "placeholder", "prompt_echo"))
    return g


def duration_gate(chars, target_minutes, chars_per_minute=None):
    """闸门（时长估算）：按字数估时长，与目标偏离超过容差就拦。

    有声书是**按时长卖**的：一条标 20 分钟的章节，实际 35 分钟，
    听众体感与平台推荐位都会错。音频阶段的**真实时长**由 subtitle / join 报出来
    （来自字级时间戳与 wav 文件头），两者不一致时人工看得到。
    """
    rate = float(chars_per_minute or cpm())
    est = chars / rate if rate else 0.0
    tol = BOOK["duration_tolerance"]
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


def gate_chapters(md_text):
    """对章节成品稿跑闸门一 / 二 / 三 / 四。"""
    g = text_gates(md_text, label="章节稿")
    g["chapters"] = chapter_gate(md_text)
    g["ok"] = g["ok"] and g["chapters"]["ok"]
    return g


def gate_cast(md_text, cast):
    """对角色分配跑闸门一 / 二 / 三 / 五。"""
    g = text_gates(md_text, label="角色分配")
    g["roles"] = role_consistency_gate(cast)
    g["ok"] = g["ok"] and g["roles"]["ok"]
    return g


def _gate_report(g, show_name=""):
    """把命中汇总到 stderr，并返回退出码。命中即退出码 3。"""
    names = {"compliance": "合规", "placeholder": "占位符", "prompt_echo": "照抄示例",
             "chapters": "章节结构", "roles": "角色一致性", "duration": "时长"}
    if g.get("ok"):
        ex = (g.get("compliance") or {}).get("exempted") or []
        if ex:
            sys.stderr.write("\n提示：本地放过 %d 处疑似绝对化用语（判定为「在说数据极值」"
                             "而不是商品宣称）。这是启发式判断，请人工确认：\n" % len(ex))
            for e in ex:
                sys.stderr.write("   「%s」：…%s…\n" % (e["word"], e["context"]))
        return EXIT_OK
    sys.stderr.write("\n")
    sys.stderr.write(_red("!! 产出被硬闸门拦下，不可直接发布%s\n"
                          % (("（%s）" % show_name) if show_name else "")) + "\n")
    if not (g.get("compliance") or {}).get("ok", True):
        sys.stderr.write("   [合规] " + "、".join(
            "「%s」(%s/%s：%s)" % (h["word"], h["level"], h["scope"], h["why"])
            for h in g["compliance"]["hits"]) + "\n")
    if not (g.get("placeholder") or {}).get("ok", True):
        sys.stderr.write("   [占位符] " + "；".join(
            h["why"] for h in g["placeholder"]["hits"]) + "\n")
    if not (g.get("prompt_echo") or {}).get("ok", True):
        sys.stderr.write("   [照抄示例] " + "；".join(
            h["why"] for h in g["prompt_echo"]["hits"]) + "\n")
    for key in ("chapters", "roles"):
        sec = g.get(key)
        if isinstance(sec, dict) and not sec.get("ok", True):
            for p in sec.get("problems") or []:
                sys.stderr.write("   [%s] %s\n" % (names.get(key, key), p))
    if isinstance(g.get("duration"), dict) and not g["duration"].get("ok"):
        d = g["duration"]
        sys.stderr.write("   [时长] %s（偏离目标 %+.1f 分钟）\n"
                         % (d["why"], d["delta_minutes"]))
    sys.stderr.write("\n   人读结果见标准输出；机器读用 --json。\n")
    return EXIT_GATE


# ---------------------------------------------------------------------------
# 产出目录与断点续跑
# ---------------------------------------------------------------------------

def _resolve(p):
    return Path(p).expanduser().resolve()


def _is_in_pkg(p):
    try:
        _resolve(p).relative_to(PKG_ROOT)
        return True
    except ValueError:
        return False


def check_outdir(outdir):
    """`--outdir` 不许指到包内。

    **为什么这条是硬闸门而不是提醒**：本库的包要过 SkillHub 的文件类型白名单，
    包内出现任何 mp3 / wav / 中间 wav 都会让整个包 400。产出音频本来就不该进包，
    所以这里**拒绝执行**（exit=2），不是"警告后继续"。
    """
    p = _resolve(outdir)
    if _is_in_pkg(p):
        raise UsageError(
            "拒绝执行：--outdir 指到了包内（%s）。\n"
            "  产出音频与中间件**一律不许进包**（包内只允许 %s）。\n"
            "  请换到包外目录，例如 %%TEMP%%\\audiobook 或 D:/book/b01。"
            % (p, " / ".join(sorted({'.md', '.py', '.txt', '.json', '.sh', '.js',
                                     '.yaml', '.yml', '.csv'}))))
    return p


def refuse_audio_in_pkg(path):
    """产出文件路径的兜底检查：音频后缀 + 落在包内 = 拒绝。"""
    p = _resolve(path)
    if _is_in_pkg(p) and str(p).lower().endswith(AUDIO_EXT):
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
# 这一点在本包里格外重要：`cast` / `subtitle` / `join` 都会往 stdout 打人读表格，
# 一旦表格混进 `--json` 的 stdout，`json.loads` 就废了。
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
# JSON"这条不变量**（同族包实测踩过：json.loads 报 `Extra data: line 61`）。
# 这个收集位让 `all` 把子步骤的产出收进内存，最后合并成一份再吐。
_EMIT = {"collect": None}


def _emit(a, result, md_text, ok=True):
    """统一出口：`--json` 时补 ok 写**真 stdout**（同时落 `--out`），否则原样打人读文本。

    `_EMIT["collect"]` 不是 None 时只收集、不输出（`all` 用）。
    """
    out = getattr(a, "out", None)
    if _EMIT["collect"] is not None:
        _EMIT["collect"].append({"result": result, "md": md_text, "ok": ok})
        return
    if a.json:
        body = _json_text(result, indent=2, ok=ok)
        if out:
            Path(out).write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 %s\n" % out)
        _json_write(body)
        return
    if out:
        Path(out).write_text(md_text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 %s\n" % out)
    print(md_text)


# ---------------------------------------------------------------------------
# 子命令的公共部分
# ---------------------------------------------------------------------------

def _read_chapters(a):
    """读章节文件，返回 (chapters, 成品 Markdown, meta)。

    支持两种形态：
      · `chapters.json`（本包 `split` 的产出）
      · 任意 `.md` —— 用 CHAPTER_LINE_RE 解析（这样手工改过的稿子也能进配音）
    两种都最终渲染成 Markdown 再过闸门：**闸门读的永远是成品稿**。
    """
    p = Path(a.chapters) if getattr(a, "chapters", None) else (Path(a.outdir) / CHAPTERS_JSON)
    if not p.is_file():
        alt = Path(a.outdir) / CHAPTERS_MD
        if not getattr(a, "chapters", None) and alt.is_file():
            p = alt
        else:
            raise UsageError("找不到章节文件：%s（先跑 `split`，或 --chapters 指定）" % p)
    if p.suffix.lower() == ".md":
        md = p.read_text(encoding="utf-8", errors="replace")
        chapters = [{"no": i + 1, "title": c["title"], "body": c["body"]}
                    for i, c in enumerate(parse_chapters_md(md))]
        meta = {"source": str(p), "method": "读已有 Markdown", "title": ""}
        return chapters, md, meta
    obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    chapters = obj.get("chapters") if isinstance(obj, dict) else obj
    if not isinstance(chapters, list) or not chapters:
        # 兜底：只跑过 `join`（没跑过 `split`）时，chapters.json 里没有 chapters 数组，
        # 只有 join 段。这时从 join 段的章节清单里把结构还原出来（正文为空，
        # 但 `cast --llm` 之外的路径不需要正文）。
        jn = (obj or {}).get("join") if isinstance(obj, dict) else None
        cl = (jn or {}).get("chapter_list") if isinstance(jn, dict) else None
        if isinstance(cl, list) and cl:
            chapters = [{"no": c.get("chapter"), "title": "第 %s 章" % c.get("chapter"),
                         "body": ""} for c in cl]
            sys.stderr.write("提示：%s 里没有 chapters 数组（只有 join 段），"
                             "已从 join 的章节清单还原 %d 章的骨架（正文为空）。\n"
                             "需要正文请重跑 `split`。\n" % (p, len(chapters)))
        else:
            raise UsageError("章节文件里没有 chapters：%s" % p)
    meta = {"source": obj.get("source"), "encoding": obj.get("encoding"),
            "method": obj.get("method"), "title": obj.get("title"),
            "heading_pattern": obj.get("heading_pattern"),
            "target_minutes": obj.get("target_minutes")}
    md = render_chapters_md(chapters, meta)
    return chapters, md, meta


def _read_cast(a):
    p = Path(a.cast) if getattr(a, "cast", None) else (Path(a.outdir) / CAST_JSON)
    if not p.is_file():
        raise UsageError("找不到角色分配文件：%s（先跑 `cast`，或 --cast 指定）" % p)
    obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    cast = obj.get("cast") if isinstance(obj, dict) and "cast" in obj else obj
    if not isinstance(cast, dict) or not cast.get("segments"):
        raise UsageError("角色分配文件里没有 segments：%s" % p)
    return cast, obj if isinstance(obj, dict) else {}


def _target_minutes(a, chapters=None):
    """目标总时长（分钟）。

    优先级：`--minutes` > 按正文字数折算 > `BOOK` 默认。
    **为什么不给一个固定的默认分钟数**：有声书的时长完全由正文长度决定，
    写死 60 分钟会让一本 8 万字的书在时长闸门里被判"严重偏短"。
    所以默认就是「按字数折算」，`--minutes` 只在用户明确要求对齐某个时长时才用。
    """
    if getattr(a, "minutes", None):
        return float(a.minutes)
    chars = sum(count_chars(c.get("body") or "") for c in (chapters or []))
    if chars:
        return round(chars / cpm(), 2) or 0.01
    return round(60000.0 / cpm(), 2)          # 兜底：按 6 万字估


def _confirm_spend(a, quotes, what):
    """闸门六的入口：报价 → 要 --yes 或 --budget。

    返回 None 表示放行；返回退出码表示就地中止（一分钱没花）。
    """
    total = round(sum(q.get("points") or 0 for q in quotes), 2)
    sys.stderr.write("\n=== %s 成本前置报价 ===\n" % what)
    for q in quotes:
        sys.stderr.write("  · %-34s %10s 点  ≈ %s 元\n"
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


def _add_cost(state, label, points):
    """把每一次真实扣点记进断点文件，供 `cost` 复盘与超预算排查。"""
    ledger = state.setdefault("cost", {"total_points": 0.0, "items": []})
    if points is None:
        ledger["items"].append({"label": label, "points": None,
                                "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        return
    ledger["total_points"] = round(float(ledger.get("total_points") or 0) + float(points), 4)
    ledger["items"].append({"label": label, "points": float(points),
                            "at": time.strftime("%Y-%m-%dT%H:%M:%S")})


# ---------------------------------------------------------------------------
# 子命令：split（章节切分，纯本地）
# ---------------------------------------------------------------------------

def _run_split(a):
    text, enc = read_text_any(a.text)
    if not text.strip():
        raise UsageError("文本是空的：%s" % a.text)
    chapters, method, pattern_name = split_text(
        text, explicit_pattern=a.heading_pattern, chunk_blocks=a.chunk_blocks)
    minutes = _target_minutes(a, chapters)
    md = render_chapters_md(chapters, {"source": str(_resolve(a.text)), "encoding": enc,
                                       "method": method,
                                       "heading_pattern": a.heading_pattern,
                                       "title": Path(a.text).stem})
    g = gate_chapters(md)
    if method.startswith("按空行"):
        sys.stderr.write("提示：没识别到章节标题，已按空行分块。"
                         "这是**段落切分**不是作者的章节切分，请人工确认后再配音。\n")
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    chars = sum(count_chars(c["body"]) for c in chapters)
    (outdir / CHAPTERS_JSON).write_text(json.dumps(
        {"title": Path(a.text).stem, "source": str(_resolve(a.text)), "encoding": enc,
         "method": method, "heading_pattern": a.heading_pattern,
         "target_minutes": minutes,
         "stats": {"chapters": len(chapters), "chars": chars,
                   "chars_per_minute": cpm(),
                   "est_minutes": round(chars / cpm(), 1) if cpm() else None},
         "chapters": chapters, "gates": g},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / CHAPTERS_MD).write_text(md + "\n", encoding="utf-8")
    result = {"stage": "split", "source": str(_resolve(a.text)), "encoding": enc,
              "method": method, "heading_pattern": a.heading_pattern,
              "chapters": len(chapters), "chars": chars,
              "est_minutes": round(chars / cpm(), 1) if cpm() else None,
              "spent_points": 0,
              "note": "本步骤纯本地，一次调用都不发",
              "chapter_list": [{"no": c["no"], "title": c["title"],
                                "chars": count_chars(c["body"])} for c in chapters],
              "gates": g, "outdir": str(outdir),
              "files": {"json": str(outdir / CHAPTERS_JSON),
                        "md": str(outdir / CHAPTERS_MD)}}
    _emit(a, result, md, ok=g["ok"])
    return _gate_report(g, Path(a.text).stem)


# ---------------------------------------------------------------------------
# 子命令：cast（识别对白 / 旁白，分配音色）
# ---------------------------------------------------------------------------

def _collect_roles(chapters, key, use_llm, model, temperature, timeout, max_tokens):
    """逐章切段，返回 (chapter_segments, usages)。

    usages 是每章大模型调用的 usage（本地分词时为空列表）。
    """
    out, usages = [], []
    known = [BOOK["narrator_role"]]
    for c in chapters:
        body = c.get("body") or ""
        if not body.strip():
            out.append((c, []))
            continue
        if use_llm:
            segs, usage = split_dialogue_llm(key, c.get("title") or "", body, known,
                                             model=model, temperature=temperature,
                                             timeout=timeout, max_tokens=max_tokens)
            usages.append(usage or {})
        else:
            segs = split_dialogue_local(body)
        for s in segs:
            if s.get("kind") == "dialogue" and s.get("speaker") \
                    and s["speaker"] not in known:
                known.append(s["speaker"])
        out.append((c, segs))
    return out, usages


def _assign_voices(chapters_segs, narrator_voice, voice_map, extra_voice_ids,
                   narrator_role=BOOK["narrator_role"]):
    """给每个角色分音色。返回 (roles_dict, segments)。

    · 旁白：--narrator-voice，没给就用 --voice-map 里的，再没有就取第一个可用音色
    · 对角白角色：--voice-map「角色=reference_id」优先；没给的按 extra_voice_ids 依次分
    · 未识别出说话人的对白（`_speaker_before/after` 都没命中）：**归旁白**并登记，
      不静默丢掉——丢掉就是整句内容消失，这是最坏的那种静默失败。
    """
    voice_map = dict(voice_map or {})
    roles = {}
    segments = []
    pool = list(extra_voice_ids or [])
    claimed = set()

    def take_voice(role):
        if role in voice_map:
            return voice_map[role]
        for v in pool:
            if v not in claimed:
                claimed.add(v)
                voice_map[role] = v
                return v
        return None

    nar_voice = narrator_voice or voice_map.get(narrator_role) or take_voice(narrator_role)
    if nar_voice:
        voice_map[narrator_role] = nar_voice
        claimed.add(nar_voice)

    order = 0
    unassigned = 0
    for c, segs in chapters_segs:
        for s in segs:
            text = (s.get("text") or "").strip()
            if not text:
                continue
            if s.get("kind") == "dialogue" and s.get("speaker"):
                role = s["speaker"]
            else:
                role = narrator_role
                if s.get("kind") == "dialogue":
                    unassigned += 1          # 引号里的话但推不出说话人
            rid = (voice_map.get(role) if role != narrator_role
                   else nar_voice) or take_voice(role)
            if rid:
                voice_map[role] = rid
                claimed.add(rid)
            order += 1
            segments.append({
                "order": order, "chapter": c.get("no"),
                "chapter_title": c.get("title"), "role": role,
                "kind": ("narration" if role == narrator_role else "dialogue"),
                "reference_id": rid, "text": text, "chars": count_chars(text)})
    for s in segments:
        r = s["role"]
        info = roles.setdefault(r, {"kind": "narration" if r == narrator_role else "dialogue",
                                    "reference_id": s["reference_id"],
                                    "segments": 0, "chars": 0})
        info["segments"] += 1
        info["chars"] += s["chars"]
    return roles, segments, voice_map, unassigned


def _run_cast(a):
    want_voices = not getattr(a, "no_fetch_voices", False)
    key = a7w.load_key(a.key) if (a.llm or want_voices) else None
    chapters, _md, meta = _read_chapters(a)
    if a.limit:
        chapters = chapters[:int(a.limit)]
    if a.llm:
        sys.stderr.write("正在用大模型逐章切段与标注（%d 章，每章一次调用）…\n" % len(chapters))
    chapters_segs, usages = _collect_roles(chapters, key, a.llm, a.model,
                                           a.temperature, a.timeout, a.max_tokens)

    extra_ids = []
    if want_voices:
        ids, _lst = first_voice_ids(key, want=int(a.voice_pool))
        extra_ids = ids
    roles, segments, voice_map, unassigned = _assign_voices(
        chapters_segs, a.narrator_voice, _parse_voice_map(a.voice_map), extra_ids)

    for r, info in roles.items():
        if r != BOOK["narrator_role"]:
            info["kind"] = "dialogue"
    cast = {"title": meta.get("title") or "", "roles": roles, "segments": segments,
            "segment_count": len(segments),
            "dialogue_count": sum(1 for s in segments if s["kind"] == "dialogue"),
            "narration_count": sum(1 for s in segments if s["kind"] == "narration"),
            "unassigned_speakers": unassigned,
            "voice_map": voice_map}
    md = render_cast_md(cast, {"title": meta.get("title"),
                               "method": "大模型标注" if a.llm else "本地正则分句"})
    g = gate_cast(md, cast)
    if unassigned:
        sys.stderr.write("提示：有 %d 段引号里的话推不出说话人，已归到「%s」并登记。"
                         "要更准就加 --llm（逐章一次大模型调用）。\n"
                         % (unassigned, BOOK["narrator_role"]))
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    state = load_state(outdir)
    for i, u in enumerate(usages, 1):
        pts = points_of({"usage": u}) if u else None
        if pts is not None:
            spent += pts
        _add_cost(state, "cast-llm 第 %d 章" % i, pts)
    if usages:
        save_state(outdir, state)
    (outdir / CAST_JSON).write_text(json.dumps(
        {"cast": cast, "method": "llm" if a.llm else "local",
         "endpoint": "/api/v1/chat/completions" if a.llm else None,
         "usages": usages, "gates": g}, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / CAST_MD).write_text(md + "\n", encoding="utf-8")
    result = {"stage": "cast", "method": "大模型标注" if a.llm else "本地正则分句",
              "endpoint": "/api/v1/chat/completions" if a.llm else None,
              "segments": len(segments), "dialogue": cast["dialogue_count"],
              "narration": cast["narration_count"],
              "roles": {r: info["reference_id"] for r, info in roles.items()},
              "role_segments": {r: info["segments"] for r, info in roles.items()},
              "unassigned_speakers": unassigned,
              "spent_points": round(spent, 4),
              "note": ("本地分词零成本；--llm 每章一次文本调用，单价平台未公开，"
                       "只报 token 不报金额"),
              "usages": usages, "gates": g, "outdir": str(outdir),
              "files": {"json": str(outdir / CAST_JSON), "md": str(outdir / CAST_MD)}}
    _emit(a, result, md, ok=g["ok"])
    return _gate_report(g, meta.get("title") or "")


def _parse_voice_map(s):
    """`--voice-map "主角=xxxx,配角=yyyy"` → dict。"""
    out = {}
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise UsageError('--voice-map 的格式是 "角色=reference_id,角色=reference_id"，'
                             "给的是：%s" % part)
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------------------
# 子命令：voices（拿 reference_id）
# ---------------------------------------------------------------------------

def _run_voices(a):
    key = a7w.load_key(a.key)
    lst = list_voices(key, tag=a.tag, title=a.title_search, language=a.language,
                      page_size=a.page_size)
    rows = []
    for it in lst:
        if not isinstance(it, dict):
            continue
        rows.append({"reference_id": voice_id_of(it),
                     "title": a7w.dig(it, "title") or a7w.dig(it, "name"),
                     "type": a7w.dig(it, "type"),
                     "state": a7w.dig(it, "state"),
                     "language": a7w.dig(it, "language"),
                     "tags": a7w.dig(it, "tags"),
                     "task_count": a7w.dig(it, "task_count")})
    if a.json:
        _json_out({"endpoint": VOICES_ENDPOINT, "count": len(rows), "data": rows}, a, indent=1)
        return EXIT_OK
    print("可用音色 %d 个（POST %s）\n" % (len(rows), VOICES_ENDPOINT))
    for r in rows:
        # ⚠️ reference_id **必须整条打出来**，不许截断。
        # 事故复盘：同族包第一版按 `%-28s` 截断显示了，实测时照着屏幕抄了前 28 位，
        # 结果 tts 返回 `code=0 任务处理失败`——真正的 id 是 32 位十六进制。
        # 列表里唯一要"抄下来用"的字段被截断，是最蠢的一种 bug。
        print("  %s" % (r["reference_id"] or "-"))
        print("      %-22s %-10s %-10s" % (str(r["title"])[:22],
                                           str(r["type"] or "-")[:10],
                                           str(r["state"] or "-")[:10]))
    print("")
    print("把 reference_id **整条**交给 cast / voice：")
    print("  --narrator-voice <ID>   # 旁白音色")
    print('  --voice-map "主角=<ID>,配角=<ID>"')
    print("不给就自动取前面的可用音色（脚本会在 stderr 说明取了哪些）。")
    print("id 是 32 位十六进制；抄短了会得到 code=0「任务处理失败」。")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：voice（逐章配音）
# ---------------------------------------------------------------------------

def _run_voice(a):
    outdir = check_outdir(a.outdir)
    cast, _obj = _read_cast(a)
    md = render_cast_md(cast, {"title": cast.get("title"), "method": "读已有角色分配"})
    # 配音**先过闸门再报价**：拿一份角色音色乱掉的分配去配音，
    # 等于把错误放大到几千个音频片段上，而且钱已经花了。
    g = gate_cast(md, cast)
    if not g["ok"]:
        result = {"stage": "voice", "gates": g, "spent_points": 0,
                  "note": "闸门未通过，未发起任何配音调用，未扣费"}
        _emit(a, result, "# 配音中止：角色分配未过闸门\n", ok=False)
        return _gate_report(g, cast.get("title") or "")

    if a.narrator_voice:
        for s in cast["segments"]:
            if s.get("role") == BOOK["narrator_role"]:
                s["reference_id"] = a.narrator_voice
    vm = _parse_voice_map(a.voice_map)
    for s in cast["segments"]:
        if s.get("role") in vm:
            s["reference_id"] = vm[s["role"]]
    for r, rid in vm.items():
        cast.setdefault("roles", {}).setdefault(r, {})["reference_id"] = rid

    key = a7w.load_key(a.key)
    need = sorted({s["role"] for s in cast["segments"] if not s.get("reference_id")})
    if need:
        ids, _lst = first_voice_ids(key, want=max(len(need), 2))
        if not ids:
            raise AudiobookError("取不到可用音色：用 `run.py voices` 看列表，"
                                 "再 --narrator-voice / --voice-map 手动指定")
        sys.stderr.write("未指定音色的角色已自动取用：%s\n"
                         % "、".join("%s→%s" % (r, ids[i % len(ids)])
                                     for i, r in enumerate(need)))
        for i, r in enumerate(need):
            rid = ids[i % len(ids)]
            for s in cast["segments"]:
                if s["role"] == r:
                    s["reference_id"] = rid
            cast.setdefault("roles", {}).setdefault(r, {})["reference_id"] = rid

    chunks = draft_voice_chunks(cast, sample_chars=a.sample_chars)
    if not chunks:
        raise UsageError("角色分配里没有可配音的片段（检查 cast.json 的 segments）")
    total_chars = sum(c["chars"] for c in chunks)
    quotes = [quote_voice(total_chars, a.points_per_1k)]
    rc = _confirm_spend(a, quotes, "配音（%d 个片段 / %d 字 / %d 个角色）"
                        % (len(chunks), total_chars, len(cast.get("roles") or {})))
    if rc:
        return rc

    vdir = outdir / "voice"
    vdir.mkdir(parents=True, exist_ok=True)
    state = load_state(outdir)
    st_voice = state.setdefault("voice", {})
    index, spent, skipped = [], 0.0, 0
    t_all = time.time()
    for ch in chunks:
        fname = "%05d-%s.%s" % (ch["order"], safe_name(ch["role"]), a.format)
        fpath = vdir / fname
        sig = voice_task_sig(ch, fmt=a.format, model=a.tts_model, speed=a.speed,
                             sample_rate=a.sample_rate, mp3_bitrate=a.mp3_bitrate)
        prev = st_voice.get(ch["key"])
        if prev and prev.get("sig") == sig and fpath.is_file() and not a.force:
            skipped += 1
            index.append({"file": str(fpath), "role": ch["role"], "chars": ch["chars"],
                          "chapter": ch["chapter"], "order": ch["order"], "sig": sig,
                          "points": prev.get("points"), "url": prev.get("url"),
                          "resumed": True})
            sys.stderr.write("  [%d/%d] %s 已存在，跳过（断点续跑，不重复扣费）\n"
                             % (ch["order"], len(chunks), fname))
            continue
        rid = ch["reference_id"]
        sys.stderr.write("  [%d/%d] %s ← %s（%d 字，端点是 %s）\n"
                         % (ch["order"], len(chunks), fname, rid or "平台默认音色",
                            ch["chars"],
                            TTS_ASYNC_ENDPOINT if ch["chars"] > TTS_ASYNC_MIN_CHARS
                            else TTS_ENDPOINT))
        res = do_tts(key, ch["text"], reference_id=rid, fmt=a.format,
                     model=a.tts_model, speed=a.speed, sample_rate=a.sample_rate,
                     mp3_bitrate=a.mp3_bitrate, timeout=a.timeout)
        pts = points_of(res)
        if pts is not None:
            spent += pts
        _report_spend("配音 %s" % fname, ch["chars"] / 1000.0 * TTS_POINTS_PER_1K_CHARS, pts)
        _add_cost(state, "voice %s" % fname, pts)
        url = pick_url(res.get("result") if isinstance(res, dict) else res,
                       "audio_url", "url", "output_url", "file_url")
        if not url:
            raise AudiobookError("配音返回里没找到音频地址（片段 %s）：%s"
                                 % (fname, json.dumps(res, ensure_ascii=False)[:400]))
        try:
            a7w.save(url, fpath)
        except (a7w.A7wError, OSError) as exc:
            raise AudiobookError("音频下载失败（片段 %s）：%s（地址：%s）" % (fname, exc, url))
        # 把 audio_url 一起存下来：subtitle 直接用这个 URL 调 stt，
        # 不用把本地文件再传一遍（少一跳、少一次上传失败的可能）。
        st_voice[ch["key"]] = {"sig": sig, "chars": ch["chars"], "role": ch["role"],
                               "reference_id": rid, "file": str(fpath),
                               "url": url, "points": pts,
                               "params": {"format": a.format, "model": a.tts_model,
                                          "speed": a.speed, "sample_rate": a.sample_rate,
                                          "mp3_bitrate": a.mp3_bitrate},
                               "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_state(outdir, state)     # 每片都落盘：中断后重跑不重复扣费
        index.append({"file": str(fpath), "role": ch["role"], "chars": ch["chars"],
                      "chapter": ch["chapter"], "order": ch["order"], "sig": sig,
                      "points": pts, "url": url})
        left = _budget_left(a, spent)
        if left is not None and left < 0:
            (vdir / VOICE_INDEX).write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
            result = {"stage": "voice", "spent_points": round(spent, 2),
                      "chars": total_chars, "segments": len(index),
                      "endpoint": TTS_ENDPOINT, "voice_map": cast.get("voice_map"),
                      "files": [i["file"] for i in index], "gates": g}
            _emit(a, result, "配音已花 %.2f 点，超过 --budget %s 点，就地中止"
                  % (spent, a.budget), ok=False)
            return _fail(EXIT_BUDGET, "budget",
                         "配音已花 %.2f 点超过 --budget %s 点，就地中止（已完成 %d 个片段）"
                         % (spent, a.budget, len(index)))

    (vdir / VOICE_INDEX).write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    cast["voice_map"] = {r: (cast["roles"].get(r) or {}).get("reference_id")
                         for r in (cast.get("roles") or {})}
    (outdir / CAST_JSON).write_text(json.dumps(
        {"cast": cast, "method": _obj.get("method"), "usages": _obj.get("usages") or [],
         "gates": g}, ensure_ascii=False, indent=1), encoding="utf-8")
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
              "roles": len(cast.get("roles") or {}),
              "voice_map": cast.get("voice_map"),
              "audio_params": {"format": a.format, "tts_model": a.tts_model,
                               "speed": a.speed, "sample_rate": a.sample_rate,
                               "mp3_bitrate": a.mp3_bitrate},
              "breakpoint_key_fields": list(VOICE_KEY_FIELDS),
              "elapsed": round(elapsed, 1),
              "files": [i["file"] for i in index], "index": str(vdir / VOICE_INDEX),
              "gates": {"ok": True, "roles": g["roles"]}}
    md_out = "\n".join([
        "# 配音完成",
        "",
        "- 片段：%d 个（跳过 %d 个已完成的）" % (len(index), skipped),
        "- 字数：%d 字　端点：`POST %s`" % (total_chars, TTS_ENDPOINT),
        "- 角色：%d 个　音色：%s" % (len(cast.get("roles") or {}),
                                     "、".join("%s → %s" % (k, v)
                                               for k, v in sorted((cast.get("voice_map") or {}).items())
                                               if v)),
        "- 音频参数：格式 %s　模型 %s　语速 %s　采样率 %s　比特率 %s"
        % (a.format, a.tts_model, a.speed or "默认", a.sample_rate or "默认",
           a.mp3_bitrate or "默认"),
        "- 实际扣费：%s 点 ≈ %s 元" % (round(spent, 2), money(spent)),
        "- 实测单价：%s 点/千字（本包申报口径 %s 点/千字）"
        % (round(per_1k, 2) if per_1k else "-", TTS_POINTS_PER_1K_CHARS),
        "- 断点 key 维度：%s" % " / ".join(VOICE_KEY_FIELDS),
        "",
        "| # | 章 | 角色 | 字数 | 扣点 | 文件 |",
        "|---|---|---|---|---|---|",
    ] + ["| %(order)s | %(chapter)s | %(role)s | %(chars)s | %(points)s | `%(file)s` |" % {
        "order": i["order"], "chapter": i["chapter"], "role": i["role"],
        "chars": i["chars"], "points": i["points"], "file": Path(i["file"]).name}
        for i in index])
    _emit(a, result, md_out)
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：subtitle（字级时间戳出 SRT / VTT）
# ---------------------------------------------------------------------------

def _stt_segments(res):
    """从 stt 返回里抠出 (segments, text, duration, language)。

    **实测结构**：`result.segments` = [{text, start, end}, ...]，中文一字一段；
    `result.text` 是整段回读；`result.duration` 是音频秒数。
    抠不出 segments 就报错，**不用字数估算冒充时间戳**。
    """
    result = res.get("result") if isinstance(res, dict) else None
    if not isinstance(result, dict):
        result = res if isinstance(res, dict) else {}
    segs = result.get("segments")
    if not isinstance(segs, list) or not segs:
        raise AudiobookError(
            "stt 没有返回字级时间戳（result.segments 为空）。"
            "检查是否传了 ignore_timestamps=False——平台默认是 True，"
            "那一档 segments 是空数组，只有整段文本。"
            "本包不拿字数估算冒充时间戳，所以这里直接失败。")
    rows = []
    for s in segs:
        if not isinstance(s, dict):
            continue
        t = str(s.get("text") or "")
        try:
            a0 = float(s.get("start") or 0.0)
            a1 = float(s.get("end") or 0.0)
        except (TypeError, ValueError):
            continue
        if t:
            rows.append({"text": t, "start": a0, "end": max(a1, a0)})
    if not rows:
        raise AudiobookError("stt 的 segments 里没有可用条目")
    return rows, str(result.get("text") or ""), float(result.get("duration") or 0.0), \
        result.get("language")


def build_cues(segs, chars_per_line=None, max_seconds=None):
    """把字级 segment 聚成**字幕条**。

    为什么要聚合：逐字出一条字幕，一本有声书会有几十万条 SRT，
    播放器直接卡死，人也没法读。这里按两条上限聚合：
      · 一条字幕最多 chars_per_line 个字
      · 一条字幕最多停留 max_seconds 秒
    并**在句末标点处优先断条**（读起来像一句话）。
    """
    cpl = int(chars_per_line or BOOK["subtitle_chars_per_line"])
    maxs = float(max_seconds or BOOK["subtitle_max_seconds"])
    cues, cur = [], None
    for s in segs:
        if cur is None:
            cur = {"text": s["text"], "start": s["start"], "end": s["end"], "n": 1}
            continue
        too_long = (cur["n"] + 1) > cpl
        too_slow = (s["end"] - cur["start"]) > maxs
        if too_long or too_slow:
            cues.append(cur)
            cur = {"text": s["text"], "start": s["start"], "end": s["end"], "n": 1}
            continue
        cur["text"] += s["text"]
        cur["end"] = s["end"]
        cur["n"] += 1
    if cur:
        cues.append(cur)
    # 后处理：句子结束时如果刚好在条尾，保留；否则不强拆（避免把词切开）
    for c in cues:
        c["text"] = c["text"].strip()
    return [c for c in cues if c["text"]]


SRT_CUE_BLOCK = "%d\n%s --> %s\n%s\n"


def write_srt(cues, path, offset=0.0):
    parts = []
    for i, c in enumerate(cues, 1):
        parts.append(SRT_CUE_BLOCK % (i, fmt_srt_time(c["start"] + offset),
                                      fmt_srt_time(c["end"] + offset), c["text"]))
    Path(path).write_text("\n".join(parts), encoding="utf-8")
    return path


def write_vtt(cues, path, offset=0.0, title=None):
    out = ["WEBVTT"]
    if title:
        out.append("NOTE %s" % title)
    out.append("")
    for i, c in enumerate(cues, 1):
        out.append("%d" % i)
        out.append("%s --> %s" % (fmt_vtt_time(c["start"] + offset),
                                  fmt_vtt_time(c["end"] + offset)))
        out.append(c["text"])
        out.append("")
    Path(path).write_text("\n".join(out), encoding="utf-8")
    return path


def _run_subtitle(a):
    outdir = check_outdir(a.outdir)
    key = a7w.load_key(a.key)
    vdir = outdir / "voice"
    index_file = vdir / VOICE_INDEX
    if not index_file.is_file():
        raise UsageError("找不到配音台账：%s（先跑 `voice`，或 --voice-index 指定）"
                         % index_file)
    segs = json.loads(index_file.read_text(encoding="utf-8"))
    if not isinstance(segs, list) or not segs:
        raise UsageError("配音台账是空的：%s" % index_file)
    if a.subtitle_limit:
        segs = segs[:int(a.subtitle_limit)]
    if a.chapters:
        want = {int(x) for x in str(a.chapters).split(",") if str(x).strip()}
        segs = [s for s in segs if s.get("chapter") in want]
    missing_url = [s for s in segs if not s.get("url")]
    if missing_url:
        raise UsageError(
            "有 %d 个片段没有 audio_url（配音台账里没有 url 字段）：%s\n"
            "  stt 的 schema 参数是 `audio_url`——公网地址。本包用配音返回的 audio_url，"
            "所以请重跑 `voice` 让它把 url 记进台账（断点续跑会跳过已配好的片段，"
            "**不会重复扣费**）。" % (len(missing_url), missing_url[0].get("file")))

    quotes = [quote_stt(len(segs), a.points_per_call)]
    rc = _confirm_spend(a, quotes, "字级时间戳（%d 个音频片段 × %s 点/次）"
                        % (len(segs), a.points_per_call or STT_POINTS_PER_CALL))
    if rc:
        return rc

    state = load_state(outdir)
    st_sub = state.setdefault("subtitle", {})
    out_dir = outdir / "subtitle"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows, spent, skipped, mismatches = [], 0.0, 0, []
    cursor = 0.0
    t_all = time.time()

    for s in segs:
        order = s.get("order")
        sig = subtitle_sig(audio_sig=s.get("sig"), language=a.language,
                           ignore_timestamps=False,
                           chars_per_line=a.chars_per_line,
                           max_seconds=a.max_seconds, endpoint=STT_ENDPOINT)
        srt_path = out_dir / ("%05d.srt" % (order or 0))
        vtt_path = out_dir / ("%05d.vtt" % (order or 0))
        prev = st_sub.get(str(order))
        resumed = bool(prev and prev.get("sig") == sig and srt_path.is_file() and not a.force)
        if resumed:
            skipped += 1
            rows = prev.get("segments") or []
            sys.stderr.write("  [%s] 字幕已存在，跳过（断点续跑，不重复扣费）\n" % order)
        else:
            sys.stderr.write("  [%s] POST %s ← %s（%s 点/次）\n"
                             % (order, STT_ENDPOINT, s["url"],
                                a.points_per_call or STT_POINTS_PER_CALL))
            res = do_stt(key, s["url"], language=a.language, timeout=a.timeout)
            pts = points_of(res)
            if pts is not None:
                spent += pts
            _report_spend("字幕 %s" % order, a.points_per_call or STT_POINTS_PER_CALL, pts)
            _add_cost(state, "subtitle %s" % order, pts)
            rows, asr_text, dur, lang = _stt_segments(res)
            cues = build_cues(rows, a.chars_per_line, a.max_seconds)
            write_srt(cues, srt_path)
            write_vtt(cues, vtt_path, title="第 %s 章" % s.get("chapter"))
            src = ""
            for c in (cast_segments_for(outdir) or []):
                if c.get("order") == order:
                    src = c.get("text") or ""
                    break
            if src and _norm_for_echo(asr_text) != _norm_for_echo(src):
                mismatches.append({"order": order, "chapter": s.get("chapter"),
                                   "asr": asr_text[:120], "source": src[:120],
                                   "asr_chars": count_chars(asr_text),
                                   "source_chars": count_chars(src)})
            st_sub[str(order)] = {"sig": sig, "file": str(srt_path),
                                  "vtt": str(vtt_path), "segments": rows,
                                  "cues": len(cues), "asr_text": asr_text,
                                  "duration": dur, "language": lang,
                                  "points": pts,
                                  "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            save_state(outdir, state)      # 每片都落盘：中断后重跑不重复扣费
            left = _budget_left(a, spent)
            if left is not None and left < 0:
                result = {"stage": "subtitle", "spent_points": round(spent, 2),
                          "segments": len(all_rows), "endpoint": STT_ENDPOINT}
                _emit(a, result, "字幕已花 %.2f 点，超过 --budget %s 点，就地中止"
                      % (spent, a.budget), ok=False)
                return _fail(EXIT_BUDGET, "budget",
                             "字幕已花 %.2f 点超过 --budget %s 点，就地中止"
                             % (spent, a.budget))
        cues = build_cues(rows, a.chars_per_line, a.max_seconds)
        dur = (st_sub.get(str(order)) or {}).get("duration") or 0.0
        all_rows.append({"order": order, "chapter": s.get("chapter"), "role": s.get("role"),
                         "start": cursor, "end": cursor + float(dur), "cues": len(cues),
                         "duration": round(float(dur), 3)})
        cursor += float(dur)

    # 全书合并字幕（拼起来的 mp3 用得上）
    merged_srt = out_dir / "book.srt"
    merged_vtt = out_dir / "book.vtt"
    merged_cues = []
    for r in all_rows:
        st = st_sub.get(str(r["order"])) or {}
        for c in build_cues(st.get("segments") or [], a.chars_per_line, a.max_seconds):
            merged_cues.append({"text": c["text"], "start": c["start"] + r["start"],
                                "end": c["end"] + r["start"], "n": c["n"]})
    write_srt(merged_cues, merged_srt)
    write_vtt(merged_cues, merged_vtt, title="全书合并字幕")

    save_state(outdir, state)
    elapsed = time.time() - t_all
    result = {"stage": "subtitle", "endpoint": STT_ENDPOINT,
              "segments": len(segs), "skipped": skipped,
              "cues": len(merged_cues), "duration_seconds": round(cursor, 2),
              "duration_mmss": fmt_mmss(cursor),
              "spent_points": round(spent, 2), "spent_yuan": money(spent),
              "quoted_points": quotes[0]["points"],
              "measured_points_per_call": (round(spent / max(1, len(segs) - skipped), 2)
                                           if len(segs) - skipped else None),
              "declared_points_per_call": STT_POINTS_PER_CALL,
              "text_mismatch": mismatches[:20],
              "text_mismatch_count": len(mismatches),
              "note": "计时来自上游 result.segments 的真实字级时间戳，不是按字数估算；"
                      "字幕文字用 ASR 回读（它与时间戳对齐），与原文的差异登记在 "
                      "text_mismatch",
              "breakpoint_key_fields": list(SUBTITLE_KEY_FIELDS),
              "elapsed": round(elapsed, 1), "outdir": str(outdir),
              "files": {"srt": str(merged_srt), "vtt": str(merged_vtt),
                        "per_segment_dir": str(out_dir),
                        "index": str(out_dir / SUBTITLE_INDEX)},
              "by_segment": all_rows}
    (out_dir / SUBTITLE_INDEX).write_text(json.dumps(
        {"result": result, "merged_cues": merged_cues,
         "per_segment": {k: {kk: vv for kk, vv in v.items() if kk != "segments"}
                         for k, v in st_sub.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    md_out = render_subtitle_md(all_rows, {"chapters": len({r["chapter"] for r in all_rows}),
                                           "segments": len(segs), "cues": len(merged_cues),
                                           "duration": cursor, "by_segment": all_rows,
                                           "mismatches": mismatches})
    _emit(a, result, md_out)
    return EXIT_OK


def cast_segments_for(outdir):
    p = Path(outdir) / CAST_JSON
    if not p.is_file():
        return []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    cast = obj.get("cast") if isinstance(obj, dict) and "cast" in obj else obj
    return (cast or {}).get("segments") or []


# ---------------------------------------------------------------------------
# 子命令：join（章节拼接 + 章节清单与时长台账）
#
# 为什么"拼接"要有两条路：
#   · 有 ffmpeg → 按章节顺序真拼成一条 mp3，并写章节标记（平台 / 播放器识别）
#   · 没有 ffmpeg → **纯标准库**把 PCM WAV 逐块接起来（重建 RIFF 头），
#     这条路对本包**实测有效**：wav 输出走的就是这条。
#     mp3 是压缩格式、不能靠拼字节接起来，这一档只出清单，
#     **明确报"没有产出合并音频"**，不假装成功。
# 时长一律从**真实来源**取：wav 文件头（精确）/ stt 的 duration（精确）/
# 最后才退回字数估算，并**在产出里标注哪一章是估算的**。
# ---------------------------------------------------------------------------

def wav_info(path):
    """读 wav 文件头，返回 {seconds, rate, channels, bits, frames} 或 None。

    **为什么自己读文件头而不是调 ffprobe**：本机实测只有 ffmpeg、没有 ffprobe
    （ffprobe 是另一个可执行文件）。而且只读文件头那几十个字节，
    不用把几十 MB 的 wav 读进内存。
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        with wave.open(str(p), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            ch = w.getnchannels()
            bits = w.getsampwidth() * 8
            return {"seconds": frames / float(rate) if rate else 0.0, "rate": rate,
                    "channels": ch, "bits": bits, "frames": frames,
                    "comptype": w.getcomptype()}
    except (wave.Error, OSError, EOFError):
        return None


def concat_wavs(paths, out_path):
    """把多个**参数完全一致**的 PCM wav 逐块拼成一个 wav（纯标准库）。

    返回 (是否成功, 原因)。参数不一致（采样率/声道/位宽）就拒绝——
    硬拼会得到一条变速或变调的音频，那种错误听起来像"设备有问题"，很难查。
    """
    infos = []
    for p in paths:
        info = wav_info(p)
        if not info:
            return False, "不是可解析的 PCM wav：%s" % p
        if info["comptype"] != "NONE":
            return False, "压缩过的 wav（comptype=%s），不能逐块拼：%s" % (info["comptype"], p)
        infos.append(info)
    if not infos:
        return False, "没有可拼的 wav"
    base = infos[0]
    for p, info in zip(paths, infos):
        if (info["rate"], info["channels"], info["bits"]) != \
                (base["rate"], base["channels"], base["bits"]):
            return False, ("参数不一致（采样率/声道/位宽）：%s 是 %sHz/%sch/%sbit，"
                           "基准是 %sHz/%sch/%sbit" % (p, info["rate"], info["channels"],
                                                       info["bits"], base["rate"],
                                                       base["channels"], base["bits"]))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(base["channels"])
        w.setsampwidth(base["bits"] // 8)
        w.setframerate(base["rate"])
        for p in paths:
            with wave.open(str(p), "rb") as r:
                w.writeframes(r.readframes(r.getnframes()))
    return True, "ok"


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


def _run_ffmpeg(ffmpeg, args, timeout=1800):
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"] + args
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout)
    except OSError as exc:
        raise AudiobookError("调用 ffmpeg 失败：%s" % exc)
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-4:]
        raise AudiobookError("ffmpeg 返回 %d：%s" % (proc.returncode, " | ".join(tail)))
    return proc


def _run_join(a):
    outdir = check_outdir(a.outdir)
    vdir = outdir / "voice"
    index_file = vdir / VOICE_INDEX
    if not index_file.is_file():
        raise UsageError("找不到配音台账：%s（先跑 `voice`）" % index_file)
    index = json.loads(index_file.read_text(encoding="utf-8"))
    if not isinstance(index, list) or not index:
        raise UsageError("配音台账是空的：%s" % index_file)
    rows = sorted([s for s in index if isinstance(s, dict)],
                  key=lambda x: x.get("order") or 0)
    if a.chapters:
        want = {int(x) for x in str(a.chapters).split(",") if str(x).strip()}
        rows = [s for s in rows if s.get("chapter") in want]
    if not rows:
        raise UsageError("按 --chapters 过滤后没有片段可拼")
    for s in rows:
        if not Path(s["file"]).is_file():
            raise UsageError("找不到音频文件：%s" % s["file"])

    # 时长：stt 的 duration（精确）> wav 文件头（精确）> 字数估算（并标注）
    st_sub = (load_state(outdir).get("subtitle") or {})
    chapters, cursor = [], 0.0
    for s in rows:
        st = st_sub.get(str(s.get("order"))) or {}
        dur = st.get("duration")
        basis = "stt 时间戳"
        if not dur:
            info = wav_info(s["file"])
            if info:
                dur = info["seconds"]
                basis = "wav 文件头"
        if not dur:
            dur = (s.get("chars") or 0) / cpm() * 60.0
            basis = "字数估算（**不是真实时长**）"
        start = cursor
        cursor += float(dur)
        if chapters and chapters[-1]["chapter"] == s.get("chapter"):
            chapters[-1]["end"] = cursor
            chapters[-1]["chars"] += s.get("chars") or 0
            chapters[-1]["fonts"] += 1
            # basis 去重后再拼：同一章里几十个片段都按同一种方式计时时，
            # 直接把 basis 一个个接起来会得到一列几百字的重复串（实测踩过）
            bases = chapters[-1]["_bases"]
            if basis not in bases:
                bases.append(basis)
            chapters[-1]["basis"] = " + ".join(bases)
            continue
        chapters.append({"chapter": s.get("chapter"), "start": start, "end": cursor,
                         "seconds": round(float(dur), 3), "fonts": 1,
                         "chars": s.get("chars") or 0, "basis": basis,
                         "_bases": [basis],
                         "roles": [s.get("role")] if s.get("role") else []})
    for c in chapters:
        c.pop("_bases", None)
    for c in chapters:
        c["start"] = round(c["start"], 3)
        c["end"] = round(c["end"], 3)
        c["seconds"] = round(c["end"] - c["start"], 3)
        c["mmss"] = fmt_mmss(c["seconds"])
        c["est_minutes_by_chars"] = round(c["chars"] / cpm(), 2) if cpm() else None

    # 章节清单（给播放器 / 平台）
    #
    # ⚠️ 字段名刻意用 `chapter_count` 而不是 `chapters`：`chapters` 这个名字在本包里
    #    是**章节数组**（`split` 的产出、`cast` / `voice` 的输入）。如果清单里也用
    #    `chapters` 放"章数"（一个整数），就会把数组顶掉 —— 第一版正是这么写的，
    #    结果 `join` 之后跑 `cast` 报"章节文件里没有 chapters"，
    #    而且看起来像是 `split` 坏了（这是写这一版时实际踩到的自坑）。
    manifest = {"title": a.title or outdir.name, "total_seconds": round(cursor, 3),
                "total_mmss": fmt_mmss(cursor), "chapter_count": len(chapters),
                "segments": len(rows), "chars": sum(c["chars"] for c in chapters),
                "chapter_list": chapters}
    cj = outdir / CHAPTERS_JSON
    obj = {}
    if cj.is_file():
        try:
            obj = json.loads(cj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            obj = {}
    if not isinstance(obj, dict):
        obj = {}
    # 清掉历史版本写坏的同名字段（它们与 `split` 的产出同键但语义不同）
    for stale in ("source", "chapters_raw"):
        if stale in obj and isinstance(obj.get(stale), (int, float)):
            obj.pop(stale, None)
    if not isinstance(obj.get("chapters"), list):
        # 没有章节数组（只跑过 join）→ 从清单还原骨架，保住 `chapters` 这个键的语义
        obj["chapters"] = [{"no": c["chapter"], "title": "第 %s 章" % c["chapter"],
                            "body": ""} for c in chapters]
    obj["join"] = manifest
    cj.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")

    ffmpeg = find_ffmpeg(getattr(a, "ffmpeg", None))
    merged, merge_note, merge_kind = None, None, None
    wav_only = all(str(s["file"]).lower().endswith(".wav") for s in rows)
    if ffmpeg:
        work = outdir / ".join"
        work.mkdir(parents=True, exist_ok=True)
        listfile = work / "concat.txt"
        listfile.write_text("".join("file '%s'\n" % str(s["file"]).replace("'", "'\\''")
                                    for s in rows), encoding="utf-8")
        chapters_txt = work / "chapters.txt"
        lines = [";FFMETADATA1"]
        for c in chapters:
            lines += ["[CHAPTER]", "TIMEBASE=1/1000",
                      "START=%d" % int(round(c["start"] * 1000)),
                      "END=%d" % int(round(c["end"] * 1000)),
                      "title=%s" % ("第 %s 章" % c["chapter"]).replace("\n", " ")]
        chapters_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        outfile = refuse_audio_in_pkg(a.filename or (outdir / "book.mp3"))
        _run_ffmpeg(ffmpeg, ["-f", "concat", "-safe", "0", "-i", str(listfile),
                             "-i", str(chapters_txt), "-map_metadata", "1",
                             "-c:a", "libmp3lame", "-b:a", "128k",
                             "-id3v2_version", "3", str(outfile)], timeout=3600)
        if not outfile.is_file() or outfile.stat().st_size <= 0:
            raise AudiobookError("ffmpeg 没报错但没有产出音频：%s" % outfile)
        merged, merge_kind = str(outfile), "ffmpeg 拼接 mp3 + 章节标记"
        (outdir / "chapters.txt").write_text(chapters_txt.read_text(encoding="utf-8"),
                                             encoding="utf-8")
    elif wav_only:
        target = a.filename or (outdir / "book.wav")
        ok, why = concat_wavs([s["file"] for s in rows], refuse_audio_in_pkg(target))
        if ok:
            merged, merge_kind = str(_resolve(target)), "纯标准库拼接 PCM wav"
        else:
            merge_note = ("本机没有 ffmpeg，且这些音频不能靠拼字节接起来：%s。"
                          "已写出章节清单与播放清单，**没有产出合并音频**。"
                          "装上 ffmpeg 后重跑同一条命令即可。" % why)
    else:
        merge_note = ("本机没有 ffmpeg，音频是 mp3（压缩格式，不能靠拼字节接起来）。"
                      "已写出章节清单与播放清单，**没有产出合并音频**。"
                      "装上 ffmpeg 后重跑同一条命令即可"
                      "（断点续跑，不会重复扣配音与字幕的钱）。")

    playlist = outdir / "playlist.txt"
    playlist.write_text("".join(
        "%s\t第 %s 章\t%s\t%s\n" % (fmt_mmss(c["start"]), c["chapter"], c["mmss"],
                                    "、".join(sorted(set(json.dumps(x, ensure_ascii=False)
                                                         .strip('"') for x in c["roles"]))))
        for c in chapters), encoding="utf-8")

    if merge_note:
        sys.stderr.write(_red("\n!! %s" % merge_note) + "\n")

    md = "\n".join([
        "# 章节清单与时长台账 · %s" % manifest["title"], "",
        "- 章节：%d 个　音频片段：%d 个　正文：%d 字"
        % (manifest["chapter_count"], manifest["segments"], manifest["chars"]),
        "- 总时长：%s（%d 秒）" % (manifest["total_mmss"], round(cursor)),
        "- 计时依据：%s" % ("逐片段真实时长累加（stt 时间戳 / wav 文件头）"
                            if not any("估算" in c["basis"] for c in chapters)
                            else "**部分章节按字数估算**（明细见下表 basis 列）"),
        "- 合并音频：%s" % (merged or "未产出（见 stderr 的原因）"),
        "",
        "| 章 | 起点 | 终点 | 时长 | 片段 | 字数 | 计时依据 |",
        "|---|---|---|---|---|---|---|",
    ] + ["| %s | %s | %s | %s | %s | %s | %s |"
         % (c["chapter"], fmt_mmss(c["start"]), fmt_mmss(c["end"]), c["mmss"],
            c["fonts"], c["chars"], c["basis"]) for c in chapters] + ["",
        "> 时长一律取**真实来源**（stt 的字级时间戳 / wav 文件头）；",
        "> 只有两级都拿不到时才退回字数估算，并在上表 basis 列明确标注，不静默估算。"])
    result = {"stage": "join", "title": manifest["title"],
              "chapters": manifest["chapter_count"], "segments": manifest["segments"],
              "chars": manifest["chars"], "total_seconds": round(cursor, 3),
              "total_mmss": fmt_mmss(cursor),
              "merged_audio": merged, "merge_kind": merge_kind,
              "merge_warning": merge_note, "degraded": bool(merge_note),
              "ffmpeg": ffmpeg,
              "spent_points": 0,
              "note": "join 是纯本地步骤：只读音频与台账，一次调用都不发",
              "chapter_list": [{"chapter": c["chapter"], "start": c["start"],
                                "end": c["end"], "mmss": c["mmss"],
                                "basis": c["basis"]} for c in chapters],
              "files": {"chapters_json": str(outdir / CHAPTERS_JSON),
                        "playlist": str(playlist)},
              "outdir": str(outdir)}
    # 降级（没产出合并音频）时 ok=False：信封的 ok 与退出码必须一致，
    # 不能让调用方看到 `{"ok":true}` 却拿到 exit=2（那是两个互相打脸的信号）。
    _emit(a, result, md, ok=not merge_note)
    (outdir / CHAPTERS_MD).write_text(md + "\n", encoding="utf-8")
    if merge_note:
        return _fail(EXIT_USAGE, "usage", merge_note)
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：cost（只算钱，一次调用都不发）
# ---------------------------------------------------------------------------

def _run_cost(a):
    chars = int(a.chars) if a.chars else int(float(a.minutes or 60) * cpm())
    chapters_n = int(a.chapters or 1)
    minutes = chars / cpm() if cpm() else 0.0
    qv = quote_voice(chars, a.points_per_1k)
    qs = quote_stt(chapters_n, a.points_per_call)
    total = qv["points"] + qs["points"]
    text_est = None
    if a.points_per_ktok:
        # 文本大模型的单价平台不公开（models 列表里没有任何价格字段、
        # pricing 表也不覆盖 chat/completions），所以**不给单价就不报金额**，绝不编。
        # `--llm` 的 cast 是逐章一次调用；token 粗估：中文约 1 字 ≈ 0.7 token。
        tok_in = int(chars * 0.7 * 1.4)
        tok_out = int(chars * 0.7 * 1.1)
        pts = (tok_in + tok_out) / 1000.0 * float(a.points_per_ktok)
        text_est = {"assumed_prompt_tokens": tok_in, "assumed_completion_tokens": tok_out,
                    "points_per_ktok": float(a.points_per_ktok),
                    "points": round(pts, 2), "yuan": round(pts / POINTS_PER_YUAN, 4),
                    "note": "token 是粗估；文本单价由 --points-per-ktok 给出，不是平台值"}
        total += pts
    result = {"chars": chars, "chapters": chapters_n, "minutes": round(minutes, 1),
              "chars_per_minute": cpm(),
              "voice": qv, "subtitle": qs, "text": text_est,
              "total_points": round(total, 2),
              "total_yuan": round(total / POINTS_PER_YUAN, 4),
              "points_per_yuan": POINTS_PER_YUAN,
              "endpoints": {"tts": TTS_ENDPOINT, "tts_async": TTS_ASYNC_ENDPOINT,
                            "stt": STT_ENDPOINT, "chat": "/api/v1/chat/completions",
                            "tasks": "/api/v1/tasks/"},
              "units": {"tts_points_per_1k_chars": TTS_POINTS_PER_1K_CHARS,
                        "stt_points_per_call": STT_POINTS_PER_CALL},
              "note": "配音 / 字幕单价是本包实测值；文本大模型单价平台不公开，"
                      "给了 --points-per-ktok 才算金额。结算以 usage.points_cost 为准。"}
    lines = [
        "# 成本测算（本地计算，未发起任何调用）", "",
        "- 正文：%d 字　按 %d 字/分钟折算 ≈ %s" % (chars, cpm(), fmt_minutes(minutes)),
        "- 章节：%d 章（字幕按**片段**计次，这里按章粗估）" % chapters_n,
        "- 换算口径：1 元 = %d 点" % int(POINTS_PER_YUAN), "",
        "| 项目 | 单价 | 数量 | 点数 | 金额 |", "|---|---|---|---|---|",
        "| 配音 `voice_tts/tts` | %s 点/千字 | %d 字 | %s | %s 元 |"
        % (TTS_POINTS_PER_1K_CHARS, chars, qv["points"], qv["yuan"]),
        "| 字级时间戳 `voice_tts/stt` | %s 点/次 | %d 次 | %s | %s 元 |"
        % (STT_POINTS_PER_CALL, chapters_n, qs["points"], qs["yuan"]),
    ]
    if text_est:
        lines.append("| 文本大模型（`cast --llm`，估算） | %s 点/千 token | ~%d+%d token | %s | %s 元 |"
                     % (text_est["points_per_ktok"], text_est["assumed_prompt_tokens"],
                        text_est["assumed_completion_tokens"], text_est["points"],
                        text_est["yuan"]))
    else:
        lines.append("| 文本大模型（`cast --llm`） | 平台未公开 | — | 未计 | 未计（给 --points-per-ktok 才计） |")
    lines += ["| **合计** | | | **%s** | **%s 元** |" % (round(total, 2),
                                                       round(total / POINTS_PER_YUAN, 4)),
              "",
              "端点：`POST %s` · `POST %s` · `POST %s` · `/api/v1/chat/completions`"
              " · `/api/v1/tasks/`" % (TTS_ENDPOINT, TTS_ASYNC_ENDPOINT, STT_ENDPOINT),
              "",
              "> 配音与字幕的单价是本包真机实测值；文本大模型的单价平台不公开，"
              "本包**不编价**。实际结算以 `usage.points_cost` 为准。",
              "> **按章计费提示**：字幕是按**片段**调 stt 的（40 点/次）。",
              "> 片段数是「同章同角色的连续台词合并成一块」之后的数量，通常远小于章数×角色数，",
              "> 精确数字用 `voice` 的报价看（它会打片段数）。"]
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

    为什么要包装：`all` 复用各子命令的处理函数，每个都会 `_emit` 一次。
    不收起来的话 `all --json` 会吐 5 个 JSON 文档，调用方 `json.loads` 直接失败。
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
        "merged_audio": next((s["result"].get("merged_audio") for s in steps
                              if isinstance(s["result"], dict)
                              and s["result"].get("merged_audio")), None),
    }
    md = "\n\n---\n\n".join(s["md"] for s in steps if s.get("md"))
    _emit(a, combined, md, ok=(rc == EXIT_OK))
    return rc


def _run_all_body(a):
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # [1/5] 章节切分
    c_json = outdir / CHAPTERS_JSON
    if c_json.is_file() and not a.force and not a.text:
        sys.stderr.write("[1/5] 章节文件已存在，跳过（断点续跑）：%s\n" % c_json)
    else:
        if not (a.text or "").strip():
            raise UsageError("还没有章节文件，请给 --text 指向小说原文；"
                             "已有 chapters.json 时可以不重复给（会走断点续跑）")
        sys.stderr.write("[1/5] 切分章节…\n")
        rc = _run_split(_split_args(a, outdir))
        if rc:
            return rc

    # [2/5] 角色分配
    cast_json = outdir / CAST_JSON
    if cast_json.is_file() and not a.force:
        sys.stderr.write("[2/5] 角色分配已存在，跳过（断点续跑）：%s\n" % cast_json)
    else:
        sys.stderr.write("[2/5] 识别对白与旁白、分配音色…\n")
        rc = _run_cast(_cast_args(a, outdir))
        if rc:
            return rc

    # [3/5] 配音（先闸门后报价，见 _run_voice）
    sys.stderr.write("[3/5] 逐章配音…\n")
    rc = _run_voice(_voice_args(a, outdir))
    if rc:
        return rc

    # [4/5] 字级时间戳字幕
    if a.skip_subtitle:
        sys.stderr.write("[4/5] 按 --skip-subtitle 跳过字幕\n")
    else:
        sys.stderr.write("[4/5] 出字级时间戳字幕…\n")
        rc = _run_subtitle(_subtitle_args(a, outdir))
        if rc:
            return rc

    # [5/5] 章节拼接
    sys.stderr.write("[5/5] 章节拼接与时长台账…\n")
    rc = _run_join(_join_args(a, outdir))
    if rc:
        return rc
    sys.stderr.write("\n完成：%s\n" % outdir)
    return EXIT_OK


def _ns(**kw):
    """造一个临时命名空间（给内部复用其它子命令用）。"""
    return argparse.Namespace(**kw)


def _split_args(a, outdir):
    return _ns(text=a.text, outdir=str(outdir), chapters=None,
               heading_pattern=a.heading_pattern, chunk_blocks=a.chunk_blocks,
               minutes=a.minutes, chars_per_minute=a.chars_per_minute,
               json=a.json, out=None)


def _cast_args(a, outdir):
    return _ns(outdir=str(outdir), chapters=None, cast=None, limit=a.limit,
               llm=a.llm, fetch_voices=True, no_fetch_voices=False,
               voice_pool=a.voice_pool,
               narrator_voice=a.narrator_voice, voice_map=a.voice_map,
               key=a.key, model=a.model, temperature=a.temperature,
               max_tokens=a.max_tokens, timeout=a.timeout,
               json=a.json, out=None)


def _voice_args(a, outdir):
    return _ns(outdir=str(outdir), cast=None, chapters=None, minutes=a.minutes,
               sample_chars=a.sample_chars, points_per_1k=a.points_per_1k,
               narrator_voice=a.narrator_voice, voice_map=a.voice_map,
               format=a.format, tts_model=a.tts_model, speed=a.speed,
               sample_rate=a.sample_rate, mp3_bitrate=a.mp3_bitrate,
               timeout=a.timeout, force=a.force, yes=a.yes, budget=a.budget,
               chars_per_minute=a.chars_per_minute,
               json=a.json, out=None, key=a.key)


def _subtitle_args(a, outdir):
    return _ns(outdir=str(outdir), limit=a.subtitle_limit, chapters=a.chapters,
               language=a.language, chars_per_line=a.chars_per_line,
               max_seconds=a.max_seconds, points_per_call=a.points_per_call,
               timeout=a.timeout, force=a.force, yes=a.yes,
               budget=a.budget_after_voice, json=a.json, out=None, key=a.key,
               voice_index=None)


def _join_args(a, outdir):
    return _ns(outdir=str(outdir), chapters=a.chapters, ffmpeg=a.ffmpeg,
               filename=a.filename, title=a.title, json=a.json, out=None)


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def _add_cpm(p):
    """`--chars-per-minute`：覆盖语速口径。

    为什么给这个开关：语速直接决定「字数 ↔ 时长」的换算，而不同的演播差得很远
    （慢读 220，快读 290）。它会**同时**影响三处：成本报价、时长估算、join 的兜底时长
    ——这正是它必须是一个显式开关、而不是三处各自一个参数的原因。
    """
    p.add_argument("--chars-per-minute", type=float, dest="chars_per_minute",
                   help="语速口径（字/分钟），默认 %s" % BOOK["chars_per_minute"])


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与全库同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py cost --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_audio_opts(p):
    """影响音频产出的参数**集中定义**——它们同时也是断点 key 的维度。

    为什么集中：这几个参数每一个都必须进 `VOICE_KEY_FIELDS`。
    分散定义时最容易漏掉某个（同族包实测就漏过 `resolution`，
    导致用户从 1K 改到 4K 拿回的还是 1K 的图）。集中在一处，
    加参数时"要不要进 key"这个问题就摆在眼前。
    """
    p.add_argument("--format", default=DEFAULT_FORMAT,
                   help="音频格式：mp3 / wav / pcm / opus，默认 %s（schema 现查确认）"
                        % DEFAULT_FORMAT)
    p.add_argument("--tts-model", default=DEFAULT_TTS_MODEL, dest="tts_model",
                   help="TTS 模型：s1 / s2-pro，默认 %s" % DEFAULT_TTS_MODEL)
    p.add_argument("--speed", type=float,
                   help="语速（prosody.speed，1.0 为原速；影响断点 key）")
    p.add_argument("--sample-rate", type=int, dest="sample_rate",
                   help="采样率（影响断点 key）")
    p.add_argument("--mp3-bitrate", type=int, dest="mp3_bitrate",
                   help="MP3 比特率：64 / 128 / 192（影响断点 key）")


def _add_model_opts(p, with_out=True):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="大模型名（只有 cast --llm 用），默认 %s"
                        "（实测可用；用 `run.py models` 现查在架模型）" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.2, help="采样温度，默认 0.2")
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens",
                   help="最大输出 token，默认 8192（一章的标注产出可能上千字）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    if with_out:
        p.add_argument("--out", help="把结果写到这个文件")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 有声书生产线（走 api.a7w.cn 的 OpenAI 兼容端点与生成应用）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models · "
               "POST https://api.a7w.cn/api/v1/apps/voice_tts/tts · "
               "POST https://api.a7w.cn/api/v1/apps/voice_tts/tts_async · "
               "POST https://api.a7w.cn/api/v1/apps/voice_tts/stt · "
               "GET https://api.a7w.cn/api/v1/tasks/<task_id>",
        allow_abbrev=False)
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("split", help="章节切分（纯本地，一次调用都不发）", allow_abbrev=False)
    p.add_argument("--text", required=True, help="小说 / 长文本文件（UTF-8 / GBK 自动识别）")
    p.add_argument("--outdir", default="audiobook-out", help="产出目录（**不许在包内**）")
    p.add_argument("--heading-pattern", dest="heading_pattern",
                   help="自定义章节标题正则（不给就用内置的 5 套）")
    p.add_argument("--chunk-blocks", action="store_true", dest="chunk_blocks",
                   help="没识别到章节标题时按空行分块（**不是**按作者章节切）")
    p.add_argument("--minutes", type=float, help="目标总时长（分钟），只用于时长估算")
    _add_cpm(p)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_split)

    p = sub.add_parser("cast", help="识别对白 / 旁白并分配音色（默认纯本地，零成本）", allow_abbrev=False)
    p.add_argument("--outdir", default="audiobook-out", help="产出目录（**不许在包内**）")
    p.add_argument("--chapters", help="章节文件，默认 <outdir>/chapters.json")
    p.add_argument("--cast", help="角色分配文件（一般不用给）")
    p.add_argument("--limit", type=int, help="只处理前 N 章（**省钱预演用**）")
    p.add_argument("--llm", action="store_true",
                   help="用大模型逐章切段与标注（更准，但每章一次文本调用）")
    p.add_argument("--no-fetch-voices", action="store_true", dest="no_fetch_voices",
                   help="不自动拉取音色池（只做切分，不分配音色）")
    p.add_argument("--voice-pool", type=int, default=6, dest="voice_pool",
                   help="自动取用多少个音色（默认 6）")
    p.add_argument("--narrator-voice", dest="narrator_voice",
                   help="旁白音色 reference_id")
    p.add_argument("--voice-map", dest="voice_map",
                   help='角色音色映射："主角=<reference_id>,配角=<reference_id>"')
    p.add_argument("--timeout", type=int, default=600,
                   help="单次文本调用超时（秒），默认 600（只有 --llm 用）")
    _add_model_opts(p)
    p.set_defaults(func=_run_cast)

    p = sub.add_parser("voice", help="逐章配音（先报价、断点续跑、多音色）", allow_abbrev=False)
    p.add_argument("--outdir", default="audiobook-out", help="产出目录（**不许在包内**）")
    p.add_argument("--cast", help="角色分配文件，默认 <outdir>/cast.json")
    p.add_argument("--chapters", help="只配这些章（逗号分隔章号，例如 1,2）")
    p.add_argument("--minutes", type=float, help="覆盖目标总时长（只影响时长闸门）")
    p.add_argument("--narrator-voice", dest="narrator_voice", help="旁白音色 reference_id")
    p.add_argument("--voice-map", dest="voice_map",
                   help='角色音色映射："主角=<reference_id>,配角=<reference_id>"')
    _add_audio_opts(p)
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

    p = sub.add_parser("subtitle", help="字级时间戳出 SRT / VTT（走 voice_tts/stt）", allow_abbrev=False)
    p.add_argument("--outdir", default="audiobook-out", help="产出目录")
    p.add_argument("--voice-index", dest="voice_index",
                   help="配音台账，默认 <outdir>/voice/index.json")
    p.add_argument("--chapters", help="只处理这些章（逗号分隔）")
    p.add_argument("--limit", type=int, dest="subtitle_limit",
                   help="只处理前 N 个片段（**省钱预演用**）")
    p.add_argument("--language", help="识别语言（不给则上游自动检测）")
    p.add_argument("--chars-per-line", type=int, dest="chars_per_line", default=None,
                   help="一条字幕最多几个字，默认 %s" % BOOK["subtitle_chars_per_line"])
    p.add_argument("--max-seconds", type=float, dest="max_seconds", default=None,
                   help="一条字幕最多停留几秒，默认 %s" % BOOK["subtitle_max_seconds"])
    p.add_argument("--points-per-call", type=float, dest="points_per_call",
                   help="覆盖字幕单价（点/次），默认用实测值 %s" % STT_POINTS_PER_CALL)
    p.add_argument("--timeout", type=int, default=1800, help="单个任务轮询超时（秒）")
    p.add_argument("--force", action="store_true", help="忽略断点全部重做（**会重复扣费**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_subtitle)

    p = sub.add_parser("join", help="章节拼接 + 章节清单与时长台账（纯本地）", allow_abbrev=False)
    p.add_argument("--outdir", default="audiobook-out", help="产出目录")
    p.add_argument("--chapters", help="只拼这些章（逗号分隔）")
    p.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径（默认找 PATH 与 FFMPEG 环境变量）")
    p.add_argument("--filename", help="合并音频文件名，默认 book.mp3（无 ffmpeg 且是 wav 时 book.wav）")
    p.add_argument("--title", help="书名（写进清单）")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_join)

    p = sub.add_parser("all", help="整条链路：切分 → 角色 → 配音 → 字幕 → 拼接", allow_abbrev=False)
    p.add_argument("--text", help="小说 / 长文本文件（已有 chapters.json 时可省）")
    p.add_argument("--outdir", default="audiobook-out", help="产出目录（**不许在包内**）")
    p.add_argument("--heading-pattern", dest="heading_pattern")
    p.add_argument("--chunk-blocks", action="store_true", dest="chunk_blocks")
    p.add_argument("--minutes", type=float, default=None,
                   help="目标总时长（分钟）；不给就按字数折算")
    p.add_argument("--limit", type=int, help="cast 只处理前 N 章（**省钱预演用**）")
    p.add_argument("--llm", action="store_true", help="cast 用大模型切段与标注")
    p.add_argument("--voice-pool", type=int, default=6, dest="voice_pool")
    p.add_argument("--narrator-voice", dest="narrator_voice")
    p.add_argument("--voice-map", dest="voice_map")
    _add_audio_opts(p)
    p.add_argument("--sample-chars", type=int, default=0, dest="sample_chars",
                   help="配音只配前 N 个字（**试链路省钱用**）")
    p.add_argument("--points-per-1k", type=float, dest="points_per_1k")
    p.add_argument("--points-per-call", type=float, dest="points_per_call")
    p.add_argument("--subtitle-limit", type=int, default=0, dest="subtitle_limit",
                   help="字幕只处理前 N 个片段（**省钱预演用**）")
    p.add_argument("--chars-per-line", type=int, dest="chars_per_line", default=None)
    p.add_argument("--max-seconds", type=float, dest="max_seconds", default=None)
    p.add_argument("--language", help="字幕识别语言")
    p.add_argument("--skip-subtitle", action="store_true", dest="skip_subtitle",
                   help="跳过字幕（只出章节音频）")
    p.add_argument("--chapters", help="只处理这些章（逗号分隔）")
    p.add_argument("--ffmpeg")
    p.add_argument("--filename")
    p.add_argument("--title")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑（**会重复扣费**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="整条链路的预算上限（点）")
    _add_cpm(p)
    _add_model_opts(p)
    p.set_defaults(func=_run_all)

    p = sub.add_parser("cost", help="只算钱（本地计算，一次调用都不发）", allow_abbrev=False)
    p.add_argument("--chars", type=int, help="正文字数（不给就按 --minutes 折算）")
    p.add_argument("--minutes", type=float, default=60, help="目标总时长（分钟），默认 60")
    p.add_argument("--chapters", type=int, default=1, help="章节数（字幕计次粗估用）")
    p.add_argument("--points-per-1k", type=float, dest="points_per_1k",
                   help="覆盖配音单价（点/千字）")
    p.add_argument("--points-per-call", type=float, dest="points_per_call",
                   help="覆盖字幕单价（点/次）")
    p.add_argument("--points-per-ktok", type=float, dest="points_per_ktok",
                   help="文本大模型单价（点/千 token）；不给就**不报文本金额**（平台未公开）")
    _add_cpm(p)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）", allow_abbrev=False)
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=_run_models)

    p = sub.add_parser("voices", help="列出可用音色，拿配音要的 reference_id（免费）", allow_abbrev=False)
    p.add_argument("--tag", help="按标签筛选")
    p.add_argument("--title-search", dest="title_search", help="按音色名称搜索")
    p.add_argument("--language", help="按语言筛选")
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
    # 语速口径的运行时覆盖（只影响本次进程，不动 BOOK 这张口径表）
    _CPM["v"] = getattr(a, "chars_per_minute", None) or None
    if _CPM["v"] is not None and not (100 <= _CPM["v"] <= 500):
        sys.stderr.write("参数错误：--chars-per-minute 要在 100~500 之间（给的是 %s）\n"
                         % _CPM["v"])
        _json_fail(EXIT_USAGE, "usage", "--chars-per-minute 越界")
        return EXIT_USAGE
    # `all` 的预算要拆成两段：配音先花，剩下的额度才给字幕
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
