#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · AI 电台 / 歌单串词（sanjianke-radio-dj）。

给一个**主题**或一份**歌单**，一条链路产出一期**可播出的电台节目**：
节目单（选曲顺序 + 每段串词的意图）→ 串词撰写（开场 / 每首前的过渡 / 结尾）→
主持人口播配音 → 选曲（音乐搜索或本地歌单）→ 与歌曲拼接 → 节目单与时间轴。

子命令
    plan    节目单：选曲顺序 + 每段串词的意图（开场 / 过渡 / 结尾）
    script  写串词：开场 + 每首前的过渡 + 结尾（三段结构缺一不可）
    voice   串词配音（**先报价**；断点续跑，已完成的片段不重复扣费）
    pick    选曲：music_search 搜索，或 --from-file 读本地歌单（离线，不花钱）
    music   垫乐：music_generation/create（异步，先报价）
    mix     串词 + 歌曲拼接 + 节目单 / 时间轴（需要 ffmpeg）
    all     整条链路（断点续跑）
    cost    只算钱，一次调用都不发
    voices  现查可用音色（配音要的 reference_id 从这里拿）
    models  现查在架模型 + 本包用到 app 的真实接口

真实端点（都在 api.a7w.cn 上；**开工前用 `python scripts/a7w.py schema <app>` 现查，别照抄记忆**）
    大模型        POST https://api.a7w.cn/api/v1/chat/completions
    模型清单      GET  https://api.a7w.cn/api/v1/models
    串词配音      POST https://api.a7w.cn/api/v1/apps/voice_tts/tts          （同步，建议 <=500 字符）
    长文本配音    POST https://api.a7w.cn/api/v1/apps/voice_tts/tts_async    （异步，<=约 10000 字符）
    音色列表      POST https://api.a7w.cn/api/v1/apps/voice_tts/list_voices
    选曲搜索      POST https://api.a7w.cn/api/v1/apps/music_search/search    （实测存在，同步）
    配乐          POST https://api.a7w.cn/api/v1/apps/music_generation/create（异步）
    歌词          POST https://api.a7w.cn/api/v1/apps/music_generation/lyrics
    任务轮询      GET  https://api.a7w.cn/api/v1/tasks/<task_id>

三条**实测确认的**接口事实（本包开工前逐条 schema 现查 + 真机跑过）
    1. 配音的音色参数叫 `reference_id`（值是 list_voices 返回的 id / model_id，
       **32 位十六进制**，抄短一位就得到 code=0「任务处理失败」），**不叫 `voice_id`**。
    2. 配乐的创建动作叫 `create`，**不叫 `generate`**；`generate` 只是 `create` 的
       `type` 参数的一个取值。`create` 的参数表里**没有时长参数**，长度只能靠裁剪。
    3. **`music_search` 这个 app 是真实存在的**，只有一个同步接口：
       `POST /api/v1/apps/music_search/search`，入参 {keyword, page, page_size(<=20)}。
       返回 `data.result.items[]`，每项含 `title / author / url / link / pic / songid`，
       `url` 是可直接下载的 mp3 地址；`data.result.has_more` 指示还有没有下一页。
       **它按次扣点（实测 10 点/次，与 page_size 无关），不是免费接口。**

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    到 https://api.a7w.cn/ 注册后：`python3 scripts/a7w.py login --key <你的Key>`
    Windows PowerShell:  $env:A7W_API_KEY="<你的Key>"
    或命令行临时给：     `python3 scripts/run.py plan --topic "..." --key <你的Key>`

六道本地硬闸门（都是**拦截**：标红 + stderr 汇总 + 退出码非 0，不是"提示一下"）
    1. 合规         广告法违禁词 + 口播红线；「最X」按可枚举语境豁免（见 _is_data_extreme）
    2. 占位符残留   `{}`、`[待填]`、`XXX`、`此处省略`、TODO
    3. prompt_echo  照抄提示词示例：去标点相等 / Jaccard >= 0.75 / 覆盖度 >= 0.60
                    + 相对长度守卫 max(6, len(示例)//2)
    4. 串词结构     **开场 + 每首前的过渡 + 结尾，缺一不可**；过渡条数必须等于歌曲数
    5. 时长台账     串词时长 + 歌曲时长合计，与目标节目时长偏离超过 +-25% 拦
    6. 成本上限     配音/选曲/配乐/整链路跑前**必须报价**，且 --yes 或受 --budget 约束

设计取舍
    · 闸门读的是**渲染后的成品稿本身**（正则解析 `【开场】` / `【过渡 3】` / `【结尾】`），
      不采信模型自报的结构字段。吃过"只信自报值、闸门成假绿"的亏。
    · 结算只认 `usage.points_cost`。平台的 `pricing_matrix` / `tenant_*` 字段**半数不可信**。
    · 缺失的单价不编：文本大模型的单价平台不公开，`cost` 没给 `--points-per-ktok`
      就只报 token 数、不报金额。
    · 产出（音频 / 混音中间件）**一律不许落进包内**，`--outdir` 指到包内直接 exit=2。

用法示例
    python3 scripts/run.py plan   --topic "深夜开车听的 City Pop" --minutes 30 --outdir D:/radio/ep01
    python3 scripts/run.py script --outdir D:/radio/ep01
    python3 scripts/run.py pick   --outdir D:/radio/ep01 --from-file D:/radio/playlist.txt
    python3 scripts/run.py voice  --outdir D:/radio/ep01 --yes
    python3 scripts/run.py music  --outdir D:/radio/ep01 --budget 100
    python3 scripts/run.py mix    --outdir D:/radio/ep01 --ffmpeg C:/ffmpeg/bin/ffmpeg.exe
    python3 scripts/run.py cost   --minutes 30 --songs 8
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
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402  ← 共用零依赖客户端；**逐字节等于规范版，本包不改它**

# 控制台统一按 UTF-8 输出：Windows 代码页会把中文打成乱码，
# 而且 `--json` 的产物要能被 json.loads 直接吃。
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 包根目录：scripts/ 的上一级。`--outdir` 落在这里面就是违规（包内不许有音频/二进制）。
PKG_ROOT = Path(__file__).resolve().parent.parent

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"
APP_URL = a7w.HOST + "/api/v1/apps"
TASK_URL = a7w.HOST + "/api/v1/tasks/"          # 异步任务轮询（长文本配音 / 配乐）

APP_VOICE = "voice_tts"
APP_MUSIC = "music_generation"
APP_SEARCH = "music_search"
TTS_ENDPOINT = "/api/v1/apps/voice_tts/tts"
TTS_ASYNC_ENDPOINT = "/api/v1/apps/voice_tts/tts_async"
VOICES_ENDPOINT = "/api/v1/apps/voice_tts/list_voices"
SEARCH_ENDPOINT = "/api/v1/apps/music_search/search"
MUSIC_ENDPOINT = "/api/v1/apps/music_generation/create"
LYRICS_ENDPOINT = "/api/v1/apps/music_generation/lyrics"

# 实测可用：这个别名会路由到 deepseek-flash 一线。它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

STATE_NAME = "radio-state.json"
PLAN_JSON = "plan.json"
PLAN_MD = "plan.md"
SCRIPT_JSON = "script.json"
SCRIPT_MD = "script.md"
PLAYLIST_JSON = "playlist.json"
PLAYLIST_TXT = "program-list.txt"
VOICE_INDEX = "index.json"

# 退出码（可直接用于 CI）
EXIT_OK = 0            # 全部干净
EXIT_USAGE = 2         # 参数/配置/环境错误（缺 ffmpeg、--outdir 指到包内、没报价就开跑）
EXIT_GATE = 3          # 有硬闸门命中（合规 / 占位符 / 照抄示例 / 串词结构 / 时长台账）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名 / 音色 ID / 搜不到歌）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_INTERRUPT = 130   # 用户中断

# 平台计费口径：1 元 = 100 点（平台公开口径，1 点 = 0.01 元）。
# ⚠️ 这只是**换算**，不是单价。单价见下面四个实测常量与 SKILL.md。
POINTS_PER_YUAN = 100.0

# ---------------------------------------------------------------------------
# 实测单价（**只放我们真跑出来过的**，不搬平台 pricing_matrix / tenant_* 字段）
#
#   voice_tts/tts           50 点 / 千字   ← 真机样本严格线性、无最低消费
#   music_search/search     10 点 / 次     ← 实测与 page_size 无关（page_size 1~3 都是 10 点）
#   music_generation/create 65 点 / 次
#   music_generation/lyrics 12 点 / 次
#   voice_tts/stt           40 点 / 次（本包没用到，仅登记）
#
# 为什么把单价写成常量而不是现拉：平台 `GET /api/v1/pricing` 只覆盖少数接口，
# voice_tts / music_search / music_generation 都不在里面；`/api/v1/apps/<app>` 的
# tenant_* 字段实测半数与结算价不一致。所以**本包用实测常量做报价，用
# usage.points_cost 做对账**：每次调用后把真实扣点打出来，不一致就明确报出来。
# ---------------------------------------------------------------------------

TTS_POINTS_PER_1K_CHARS = 50.0
SEARCH_POINTS_PER_CALL = 10.0
MUSIC_POINTS_PER_CREATE = 65.0
MUSIC_POINTS_PER_LYRICS = 12.0
STT_POINTS_PER_CALL = 40.0        # 未使用，仅登记

# 同步配音接口的平台建议上限：schema 原文「同步接口建议不超过 500 字符」。
TTS_SYNC_MAX_CHARS = 500
TTS_ASYNC_MIN_CHARS = 5000
# music_search 单页上限：schema 原文「每页条数，最大 20」。
SEARCH_MAX_PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# 电台节目规格表（**唯一事实来源**）
#
# 为什么做成表：语速、歌曲数、曲长这些数字会变，而且提示词、闸门、时长台账、
# 成本报价四处都要用同一个数。放一张表里，改口径只改这里，逻辑不动。
#
# 语速 250 字/分钟的依据：**电台主持人是独白**，不是播客里的双人对白
# （对白实测 240~280 字/分钟，本包有意取更低的值）——独白有停顿、有留白、
# 要报歌名歌手、还要跟音乐起落配合，实测落在 220~260 字/分钟，取中位偏上。
# 它同时是四处口径的来源，改它会同时改成本报价与时长台账：
#   · 一期 30 分钟 ≈ 8 首歌（曲长按 210 秒估）+ 约 500 字串词
#   · 500 字 × 50 点/千字 = 25 点
# 想按自己的节目节奏调就 `--chars-per-minute`。
# ---------------------------------------------------------------------------

SHOW = {
    "host": "主播",
    "chars_per_minute": 250,
    "default_minutes": 30,
    "min_minutes": 5,
    "max_minutes": 240,
    "default_songs": 8,
    "min_songs": 1,
    "max_songs": 30,
    # 曲长假设值 190 秒：**这是"装得下多少串词"的分母，不是"歌有多长"的事实**。
    # 第一版取 210 秒，30 分钟被吃掉 28 分钟、只剩 2 分钟串词（≈500 字 / 6 分钟，
    # 合 83 字/分钟，没人这么说话）。190 秒配下面那条 0.75 的占用率，
    # 让 30 分钟的一期落在"约 5 首歌 + 约 1900 字串词"这个真实电台形态上。
    # 拿到真实音频文件后，时长台账一律以文件真实时长为准，这个值就退居为回退值。
    "song_seconds_fallback": 190,
    # 【每首歌至少占多少秒节目时长】曲长 **加上** 这首歌之前那条过渡的时长。
    # 用途是**反推推荐歌曲数**：30 分钟 × 0.75 ≈ 1350 秒 ÷ 300 秒 ≈ 4.5 → 4~5 首。
    "min_seconds_per_song": 300,
    # 【歌曲合计最多吃掉目标时长的多少】剩下的就是串词的空间。
    # 0.75 的依据：电台节目里音乐通常占七成上下；低于它，串词就只剩报幕的份。
    "song_share_max": 0.75,
    "duration_tolerance": 0.25,     # 时长台账偏离目标超过 +-25% 拦
    # 串词各段的字数下限/上限（字）。目的是把模型约束在**它能逐项对齐的粒度**上。
    "open_min_chars": 80, "open_max_chars": 220,
    "trans_min_chars": 40, "trans_max_chars": 130,
    "close_min_chars": 80, "close_max_chars": 220,
}

# `--chars-per-minute` 的运行时覆盖位。为什么不直接改 SHOW：
# SHOW 是**口径表**（只读的事实来源），命令行覆盖是**本次运行的选择**；
# 两者混在同一个字典里，下一次调用的默认值就被悄悄改掉了。
_CPM = {"v": None}


def cpm():
    return float(_CPM["v"] or SHOW["chars_per_minute"])


# 串词的三个固定段落。**这是本包的结构闸门口径，不是随手一写**：
# 电台节目与"一个歌单"的分水岭就是有人在对你说这三个位置的话——
# 没有开场，听众不知道自己在听什么；没有过渡，歌与歌之间是断的；
# 没有结尾，一期节目在最后一首歌的淡出里结束了，没有收束。
SEC_OPEN = "开场"
SEC_CLOSE = "结尾"
SEC_TRANS = "过渡"
SECTION_ORDER_HINT = ("开场", "过渡 1..N", "结尾")


def trans_label(i):
    """第 i 首之前的过渡段标题（i 从 1 开始）。"""
    return "%s %d" % (SEC_TRANS, int(i))


def suggest_songs(minutes, chars_per_minute=None):
    """按目标时长反推**合理的歌曲数**。

    口径：歌曲合计最多吃掉目标时长的 `song_share_max`（0.75），剩下的留给串词；
    再按每首至少 `min_seconds_per_song`（300 秒 = 190 秒曲 + 约 110 秒过渡）除。
    30 分钟 → 4 首，60 分钟 → 9 首，5 分钟 → 1 首。

    **这不是"最优解"，是"装得下"**：按这个数配曲，串词才有说话的时间。
    用户想多放歌当然可以（`--songs N`），但那时正确的做法是同步加长节目或调短曲长，
    而不是让闸门事后拦一下。
    """
    rate = float(chars_per_minute or cpm())
    per = float(SHOW["min_seconds_per_song"])
    budget_seconds = minutes * 60.0 * float(SHOW["song_share_max"])
    n = int(budget_seconds / per) if per else SHOW["default_songs"]
    n = max(SHOW["min_songs"], min(SHOW["max_songs"], n))
    # 最后一首常常顶不满：往下试一位，取"装得下且更接近上限"的那个
    if n < SHOW["max_songs"] and (n + 1) * per <= budget_seconds * 1.05:
        n += 1
    return n


def target_speech_min(minutes, songs, chars_per_minute=None):
    """这一档规格**应该**花多少分钟说话的**目标值**（不是区间）。

    口径：目标时长 − 歌曲估算时长，再砍掉容差的一半（±25% 里吃掉 12.5%）。
    这样"按这个目标写出来的稿子"落点就在时长台账区间的中偏上，
    而不是贴着下限勉强通过——**贴着下限通过的节目，听感上就是"歌多话少"**。
    实测教训：30 分钟 + 6 首（各 190 秒）时，模型写了 771 字，
    时长台账算出 24.1 分钟，落在 22.5~37.5 的区间里"通过"了，
    但目标本该是约 1900 字。闸门没错，是**目标值本身没告诉模型**。
    """
    rate = float(chars_per_minute or cpm())
    room = minutes - (songs * SHOW["song_seconds_fallback"]) / 60.0
    return max(0.0, room * (1 - SHOW["duration_tolerance"] / 2.0)), rate


def target_speech_chars(minutes, songs, chars_per_minute=None):
    """上面那个目标值换算成字数（提示词里给模型的就是这个数）。"""
    m, rate = target_speech_min(minutes, songs, chars_per_minute)
    return max(1, int(round(m * rate)))


def show_feasible(minutes, songs, chars_per_minute=None):
    """这档「时长 + 歌曲数」能不能装下一期**像样的**串词？返回 (是否可行, 说明)。

    【为什么用中位口径而不是下限】第一版用下限判（开场+结尾各 80 字），
    结果 30 分钟 + 8 首被判"可行"——留给串词 0.7 分钟，正好塞下 80 字开场
    和 80 字结尾，中间 8 条过渡**一个字都放不下**。那种成片是"报幕 + 连续放歌"，
    不是电台节目。所以这里按各段的**中位**估外加一条总占用率上限：
    开场与结尾取 (min+max)/2，每条过渡取下限，且歌曲合计不得超过目标时长的
    `song_share_max`。
    """
    rate = float(chars_per_minute or cpm())
    trans_total = songs * SHOW["trans_min_chars"]
    open_close = (SHOW["open_min_chars"] + SHOW["open_max_chars"]
                  + SHOW["close_min_chars"] + SHOW["close_max_chars"]) / 2.0
    speech_min = (open_close + trans_total) / rate
    song_min = (songs * SHOW["song_seconds_fallback"]) / 60.0
    room = minutes - song_min
    share = song_min / minutes if minutes else 1.0
    problems = []
    if room < speech_min - 1e-9:
        problems.append("留给串词 %.1f 分钟 < 开场+结尾+%d 条过渡所需 %.1f 分钟"
                        % (room, songs, speech_min))
    if share > float(SHOW["song_share_max"]) + 1e-9:
        problems.append("歌曲占目标时长 %.0f%% > 上限 %.0f%%"
                        % (share * 100, SHOW["song_share_max"] * 100))
    ok = not problems
    why = ("%d 分钟 − %d 首（曲长按 %.0f 秒/首估 ≈ %.1f 分钟，占 %.0f%%）"
           "≈ 留给串词 %.1f 分钟；开场+结尾+%d 条过渡按中位口径约需 %.1f 分钟"
           "（%.0f 字 ÷ %d 字/分钟）"
           % (minutes, songs, SHOW["song_seconds_fallback"], song_min, share * 100,
              room, songs, speech_min, open_close + trans_total, rate))
    if not ok:
        why += ("——**装不下**（%s）。这档规格本身不成立：要么把节目加到 %d 分钟以上，"
                "要么降到 %d 首，要么用 --song-seconds / --chars-per-minute 改口径"
                % ("；".join(problems),
                   int(song_min + speech_min) + 1, suggest_songs(minutes, rate)))
    return ok, why


# ---------------------------------------------------------------------------
# 闸门一：合规自检（广告法违禁词 + 口播红线）
#
# 这是一道**粗筛**：宁可多报也别漏报，最终判断仍要人工复核，
# 且不等于任何平台的官方审核结论（官方标准不公开、会变）。
# 每项：正则 → 风险等级 → 人话解释 →（可选）语境判定标签
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    # 【比模板词表多三个词】`省` / `划算` / `实惠` 是口播里最常见的省钱类绝对化说法
    # （「最省钱的套餐」），而模板词表里有「便宜」却没有「省」。
    # 加词只会让闸门更严、不会放松任何一处判定；这次扩表如实登记在此。
    # 这一条带 "superlative" 语境标签，命中后**逐处**走 _is_data_extreme 判豁免。
    (r"最(好|佳|优|低|便宜|省|划算|实惠|快|强|大|高|先进|新|流行|受欢迎|顶级|厉害|火|红)",
     "高", "广告法第九条禁止「最高级」用语", "superlative"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    # 【口径选择，与 multiplat-rewrite 有意不同】multiplat 用的是裸 `第一(?!次)`，
    # 在本包里会把口播里的「第一首」「第一步」全判违规。电台串词里报歌序是常态，
    # 误伤率太高。所以这里取 course-outline 的**限定式**写法：只有
    # 「全国/行业/销量…第一」「第一品牌」「排名第一」这类**排他性宣称**才拦。
    (r"(全国|全球|全网|行业|销量|口碑|人气|收听率)第一|第一(品牌|选择)|排名第一|"
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

# 音频 / 电台平台特有的红线：**同一个表达在不同形态的内容里风险不一样**。
# 电台是长音频，口播里念出「加微信 / 私信我」比图文的违规概率更高
# （平台无法预审，上线后被投诉即下架），所以站外导流按「中」而不是「低」处理。
# 这张表是**经验口径**，不是任何平台的官方审核标准。
SHOW_REDLINES = [
    (r"加微信|微信号|加V|vx|VX|私信我|加我好友|扫码加", "中",
     "口播站外导流，音频类平台普遍限制；确有必要请人工确认后再录"),
    (r"点赞|收藏|关注我|订阅(一下|本节目)|三连|打榜|投月票|扣1", "低",
     "诱导互动表述，部分平台会限流"),
    (r"付费(社群|群|专栏)|知识星球|会员群", "中",
     "二跳转化表述需与真实服务一致"),
    (r"下载(我们的|本)?(App|APP|客户端)", "中",
     "口播引导下载，音频平台普遍要报备"),
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
# 电台串词里这个误伤只会更多：主播天然会说「上周收听率最低的一期」
# 「排在最前面的那首」「我最早听到的一版」。
#
# 判定分两层，**两个条件都必须成立**，缺一不豁免：
#   A. `最` **不在句首**：它前面那一个字符存在，且属于计量类名词
#      （量/率/数/分/位/首/条/次/段/部/集/期/页/个/天/月/年…）
#   B. `最X` 那一处**在完整串词段内**匹配到了「最X的」或「最X之」
# 句首的「最好 / 最低」**一律不豁免**——「最省心的一套流程」这种是最典型的
# 绝对化宣称形态，而它恰恰出现在句首。
#
# 【为什么条件 A 必须显式判 `before` 非空】这是写这段时自己踩到的坑：
# 空字符串在 Python 里 `"" in "量率数…"` 是 True，漏了这一步
# 句首的「最好/最低」会被全部误豁免。别把这行"简化"掉。
#
# 豁免词表刻意**不含** `时`/`款`/`种`/`家`/`价`：
#   「课时最低的课程」「单价最低」都是真实的价格宣称形态，必须照拦。
# 命中豁免时**整处放过**，但会在产出里登记下来（gates.compliance.exempted），
# 报告里会明说「本地放过了 N 处疑似绝对化用语」——**不静默放过**。
# ---------------------------------------------------------------------------

MEASURE_PREFIX = "量率数分位首条次段部集期页个天月年轮张场篇"
# 条件 B：`最X` 后面必须紧跟「的」或「之」。
EXTREME_TAIL = ("的", "之")
# 一次扫出所有 `最X`（X 是 BANNED_PATTERNS 第一条里那组字，
# 另外把电台/歌单场景常见的 `火/红` 也算进来），再逐个判豁免。
SUPERLATIVE_RE = re.compile(
    r"最(?:好|佳|优|低|便宜|省|划算|实惠|快|强|大|高|先进|新|流行|受欢迎|顶级|厉害|火|红)")


def _is_data_extreme(text, m):
    """`m` 命中的 `最X` 是否属于「在描述数据极值」而不是「商品/服务绝对化宣称」。

    条件 A：`最` 前一个字是计量类名词（**句首不算**，见常量区注释）。
    条件 B：`最X` 后面紧跟「的」或「之」。
    """
    start, end = m.start(), m.end()
    before = text[start - 1] if start > 0 else ""
    ok_a = bool(before) and before in MEASURE_PREFIX
    ok_b = text[end:end + 1] in EXTREME_TAIL
    return ok_a and ok_b


# ---------------------------------------------------------------------------
# 闸门二：占位符残留
#
# 为什么单列一道闸门：节目单常常是别人给的模板，模型会把 `{主题名}`
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
# 举例只用**跨主题**的描述性说明；真实示例一律登记在 PROMPT_SAMPLES。
# 本包另加一道**提示词卫生自检**（prompt_hygiene）：--dry-run 时直接检查
# 即将发送的提示词里有没有混进登记过的示例，混进去就报错，不等模型照抄。
#
# 三条命中路径（任一即命中）：
#   · 去标点后**完全相同**
#   · 字符二元组 Jaccard >= ECHO_SIM（长度相当的同构改写）
#   · 示例的二元组**覆盖度 >= ECHO_CONTAIN**（把示例夹带进更长的句子里；
#     Jaccard 会被长度摊薄，只有覆盖度抓得住）
#
# 阈值标定依据（本库实测）：196 条正常产出与跨主题示例的最高相似度只有 0.174，
# 而「少两个字的同构照抄」是 0.765。0.75 既能兜住轻改写，离正常上限还有 4 倍余量。
# 长度守卫是**相对**的：目标归一化长度 < max(ECHO_MIN_LEN_FLOOR, len(示例)//2) 就不比，
# 因为短串的二元组集合太小、指标会虚高。
# ---------------------------------------------------------------------------

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


# 提示词 / 文档里出现过的示例文本（**跨主题**，正常不该被抄）。新增示例必须登记到这里。
# 主题刻意选「县城农机维修铺的排班」，与三剪客真实业务主题（内容创作 / 电台 / 歌单）
# 明显不搭，也和本包会产出的电台话题（音乐、通勤、深夜、咖啡馆）不搭——
# 这样"命中"就一定是照抄，不是巧合。
PROMPT_SAMPLES = [
    "农机维修铺的排班表，我贴在墙上贴了六年",
    "先说结论：配件到货快不快，跟店铺大小关系不大",
    "我在县城修了十年农机，排班这块踩过三个坑",
    "接活之前没人告诉我，农忙那两个月才是最难的",
    "三组数字说明，小维修铺的排班没必要按大厂的来",
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

    **为什么不能只比整段**：一期串词有 1500+ 字，而提示词示例只有二三十字。
    把整段稿子拿去和示例算 Jaccard，分母被撑到 1500 多，相似度永远接近 0——
    也就是说**模型把示例原样抄进某一句，这道闸门完全看不见**。

    所以判定分两层：
      1. 整段比一次（兜住整篇照抄的极端情况），这一层**只认 exact / jaccard**：
         整段有上千字，覆盖度在这里只能告诉你"稿子里抄了一句"、指不出是哪一句
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
                   "（覆盖度 >= {:.2f} 即判照抄；Jaccard 会随句子变长被摊薄）"
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
# `{title, host, tracks[]}` 这种字段说明，命中了 `[{}]` 这条规则。
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
# 闸门四：串词结构（本包**特有的核心形态闸门**）
#
# 为什么必须有：电台节目与"一个歌单"的分水岭就是**有人在对你说三件事**——
#   · 开场：告诉听众现在在听什么、这一期为什么值得听下去
#   · 每首前的过渡：把上一首的情绪接到下一首上（缺了就是硬切歌）
#   · 结尾：给一个收束、一个可以被单独转述的句子（缺了就是音乐淡出）
# 一份只有开场和结尾、或者只有一堆歌单描述的稿子：字数够、时长对、
# 合规干净、读起来也顺——**它在任何一道常规检查里都是合格的**，
# 但它配出来只是"报幕"，不是电台节目。发出去才发现形态不对。
#
# 【为什么不采信模型自报的结构字段】这是本库吃过的亏：标题工坊上一版只信模型
# 自报的 formula 字段，闸门成了假绿。所以这里**只读渲染后的成品稿本身**：
# 用正则在成品 Markdown 上重新解析出段落与标题，解析不出的正文行单独计数。
#
# 判定（全部命中才算过）：
#   · 有且仅有 1 个「开场」段，且正文 >= open_min_chars
#   · 「过渡 i」段**恰好 N 个（N = 歌曲数）**，每段 >= trans_min_chars
#   · 有且仅有 1 个「结尾」段，且正文 >= close_min_chars
#   · 没有"孤儿正文"（既不在开场、也不在任何过渡/结尾里的正文行）
# ---------------------------------------------------------------------------

# 成品稿里的段落标题形态：`## 【开场】` / `## 【过渡 3】` / `## 【结尾】`
SECTION_HEAD_RE = re.compile(
    r"^#{1,6}\s*【(?P<name>[^】\n]{1,24})】\s*$")
# 编辑视图行（引用/表格/列表）不算正文，也不算孤儿
_META_PREFIX = (">", "|", "-", "*", "+")


def parse_script_md(md_text):
    """从成品 Markdown 里解析出串词段落。

    返回 {"sections": [{name, kind, index, body}], "orphans": [行], "headings": [标题]}。
    kind ∈ open / trans / close / other。
    """
    sections, orphans, headings = [], [], []
    cur = None
    for raw in (md_text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            title = s.lstrip("# ").strip()
            headings.append(title)
            m = SECTION_HEAD_RE.match(s)
            name = (m.group("name").strip() if m else None)
            cur = None
            if name:
                kind, idx = classify_section(name)
                cur = {"name": name, "kind": kind, "index": idx, "body": []}
                sections.append(cur)
            continue
        if s.startswith(_META_PREFIX) and len(s) > 1:
            continue
        if cur is not None:
            cur["body"].append(s)
        else:
            orphans.append(s[:60])
    for sec in sections:
        sec["body"] = "\n".join(sec["body"]).strip()
        sec["chars"] = count_chars(sec["body"])
    return {"sections": sections, "orphans": orphans, "headings": headings}


def classify_section(name):
    """把段落名归到 open / trans / close / other，并给出过渡序号（其余为 None）。"""
    n = (name or "").strip()
    flat = re.sub(r"[\s\u3000]+", "", n)
    if flat in (SEC_OPEN, SEC_OPEN + "白", "开场白"):
        return "open", None
    if flat in (SEC_CLOSE, "收尾", "结束", "结尾语"):
        return "close", None
    m = re.match(r"^(?:过渡|串词|转折)(\d+)$", flat)
    if m:
        return "trans", int(m.group(1))
    if flat in (SEC_TRANS, "串词"):
        return "trans", None
    return "other", None


def script_structure_gate(md_text, songs):
    """闸门四：成品稿里开场 / 每首前的过渡 / 结尾**是不是都在**。

    `songs` 是歌曲数：过渡段必须**恰好**这么多条，多了少了都拦。
    这条比"有没有过渡"值钱得多——过渡少一条，就意味着有一首歌是硬切进去的。
    """
    parsed = parse_script_md(md_text)
    secs = parsed["sections"]
    opens = [s for s in secs if s["kind"] == "open"]
    closes = [s for s in secs if s["kind"] == "close"]
    trans = [s for s in secs if s["kind"] == "trans"]
    others = [s for s in secs if s["kind"] == "other"]
    trans_idx = sorted(s["index"] for s in trans if s["index"])

    problems = []
    if not opens:
        problems.append("**缺开场**：成品稿里读不出「【开场】」段。"
                        "电台节目没有开场，听众不知道自己在听什么")
    elif len(opens) > 1:
        problems.append("出现了 %d 个「开场」段（只能有一个）" % len(opens))
    elif opens[0]["chars"] < SHOW["open_min_chars"]:
        problems.append("「开场」只有 %d 字（至少 %d 字）：一句报幕不算开场"
                        % (opens[0]["chars"], SHOW["open_min_chars"]))

    if not closes:
        problems.append("**缺结尾**：成品稿里读不出「【结尾】」段。"
                        "没有结尾，一期节目就结束在最后一首歌的淡出里")
    elif len(closes) > 1:
        problems.append("出现了 %d 个「结尾」段（只能有一个）" % len(closes))
    elif closes[0]["chars"] < SHOW["close_min_chars"]:
        problems.append("「结尾」只有 %d 字（至少 %d 字）：收束要能被单独转述"
                        % (closes[0]["chars"], SHOW["close_min_chars"]))

    if not trans:
        problems.append("**缺过渡**：成品稿里一条「【过渡 i】」段都没有。"
                        "歌与歌之间没有串词，那就是一个歌单，不是电台节目")
    elif len(trans) != int(songs):
        problems.append("过渡段有 %d 条，但歌曲有 %d 首——**每条过渡对应一首歌**，"
                        "数量必须相等（少的那几首会被硬切进去）"
                        % (len(trans), int(songs)))
    if trans_idx and trans_idx != list(range(1, len(trans_idx) + 1)):
        problems.append("过渡段编号不连续：%s（应为 1~%d）"
                        % ("、".join(str(i) for i in trans_idx), len(trans_idx)))
    short = [s for s in trans if s["chars"] < SHOW["trans_min_chars"]]
    if short:
        problems.append("有 %d 条过渡不足 %d 字（例：「%s」只有 %d 字）"
                        % (len(short), SHOW["trans_min_chars"],
                           short[0]["name"], short[0]["chars"]))
    if others:
        problems.append("出现了 %d 个无法归类的段落标题（例：「%s」）；"
                        "只认「【%s】」「【%s i】」「【%s】」"
                        % (len(others), others[0]["name"],
                           SEC_OPEN, SEC_TRANS, SEC_CLOSE))
    if parsed["orphans"]:
        problems.append("有 %d 行**不在任何段落里**的正文（例：「%s」）——"
                        "这些内容配不出来，也没被闸门检查过"
                        % (len(parsed["orphans"]), parsed["orphans"][0]))

    return {
        "ok": not problems,
        "problems": problems,
        "songs": int(songs),
        "sections": [{"name": s["name"], "kind": s["kind"], "index": s["index"],
                      "chars": s["chars"]} for s in secs],
        "open_chars": opens[0]["chars"] if opens else 0,
        "close_chars": closes[0]["chars"] if closes else 0,
        "transitions": len(trans),
        "trans_chars": [s["chars"] for s in trans],
        "orphan_lines": parsed["orphans"][:5],
    }


# ---------------------------------------------------------------------------
# 闸门五：时长台账（串词时长 + 歌曲时长 vs 目标节目时长）
#
# 电台节目是**按时长卖**的：一期标 30 分钟，实际 52 分钟，听众体感与平台
# 推荐位都会错。脚本阶段拿不到真实音频时长，所以分两段口径：
#   · 串词时长 = 字数 ÷ 语速（口径写在 SHOW["chars_per_minute"]）
#   · 歌曲时长 = 本地文件的**真实时长**（读 wav 头 / 用 --song-seconds 声明）；
#     拿不到本地文件时用 SHOW["song_seconds_fallback"]，并在产出里**明确标注
#     这是假设值不是实测值**——不把假设当事实。
# 音频阶段的**真实总时长**由 mix 报出来（timeline.md），两者不一致时人工看得到。
# ---------------------------------------------------------------------------

def plan_duration_gate(plan, target_minutes, chars_per_minute=None):
    """节目单阶段的时长预检：**曲长之和 + 计划串词量**能不能撑到目标时长。

    【为什么要在 plan 阶段就查一次，而不是等 script】这是实测踩出来的：
    第一版只把「目标总时长 30 分钟」写进提示词，模型给 8 首都填了 `seconds: 300`
    （合计 40 分钟）——那是 40 分钟节目。这个错到 `script` 阶段会被时长台账拦下，
    但那时已经多花了一次文本调用的钱，而且用户拿到的是"改稿"而不是"改节目单"。
    节目单是曲目与曲长的**唯一来源**，所以这一条必须在它落地的那一刻就查。

    【串词量按配额算，不按段下限算】第一版这里用的是
    `(open_max + close_max + songs*trans_max)/rate`，结果 4 首 30 分钟的
    有效节目单被误判"撑不满"（预算 3.8 分钟 ≈ 950 字，而实际按配额要写 3792 字）。
    误判的代价和漏判一样大：**一个正确的产出被自己的闸门拦下，闸门就废了**。
    所以这里直接取 `script_quotas` 的目标字数——它才是"这一期会写多少字"的真值。

    【为什么只查下界】上界（曲长超标）在 `script` 阶段会被时长台账连同真实字数
    一起判，那时曲长与字数都是已知的；在 plan 阶段卡上界只会误伤
    "曲长在容差边缘但串词写短一点就正好"的合规节目单。
    """
    tracks = plan.get("tracks") or []
    songs = len(tracks)
    rate = float(chars_per_minute or cpm())
    planned_chars = target_speech_chars(target_minutes, songs, rate)
    speech_min = planned_chars / rate if rate else 0.0
    song_seconds = sum(float(t.get("seconds") or 0) for t in tracks)
    assumed = [t.get("no") for t in tracks if not (t.get("seconds") or 0)]
    total_min = (song_seconds / 60.0) + speech_min
    tol = SHOW["duration_tolerance"]
    lo, hi = target_minutes * (1 - tol), target_minutes * (1 + tol)
    problems = []
    if not song_seconds:
        problems.append("节目单里每首歌的 `seconds` 都是 0/缺失——曲长是时长台账的唯一来源，"
                        "缺了就没法核对节目长度")
    elif total_min < lo:
        problems.append("曲长之和 %d 秒（%.1f 分钟）+ 按配额要写的串词 %.1f 分钟 = 约 %.1f 分钟，"
                        "低于目标 %.1f 分钟的容差下限 %.1f 分钟——**这一期撑不满**。"
                        "把 tracks 的 seconds 按目标总时长重新分配（约 %d 秒/首）后重跑 `plan`"
                        % (int(song_seconds), song_seconds / 60.0, speech_min, total_min,
                           target_minutes, lo,
                           int(max(30, (target_minutes - speech_min) * 60 / max(1, songs)))))
    return {
        "ok": not problems,
        "problems": problems,
        "songs": songs,
        "song_seconds_total": round(song_seconds, 1),
        "song_seconds_each": [t.get("seconds") for t in tracks],
        "songs_without_seconds": assumed[:30],
        "planned_speech_chars": planned_chars,
        "planned_speech_minutes": round(speech_min, 1),
        "est_minutes": round(total_min, 1),
        "target_minutes": target_minutes,
        "accept_minutes": [round(lo, 1), round(hi, 1)],
        "why": ("曲长合计 %d 秒（%.1f 分钟）+ 按配额要写的串词 %d 字（%.1f 分钟）"
                "≈ %.1f 分钟；目标 %.1f 分钟，容差 %.0f%%（%.1f~%.1f 分钟）"
                % (int(song_seconds), song_seconds / 60.0, planned_chars, speech_min,
                   total_min, target_minutes, tol * 100, lo, hi)),
    }


def duration_gate(script_chars_value, songs, target_minutes,
                  song_seconds=None, chars_per_minute=None, measured_songs=None):
    """返回时长台账 dict。measured_songs 给的是 {index: seconds} 的真实时长。"""
    rate = float(chars_per_minute or cpm())
    songs = int(songs)
    measured = measured_songs or {}
    fallback = float(song_seconds if song_seconds else SHOW["song_seconds_fallback"])
    per_song = []
    for i in range(1, songs + 1):
        if i in measured:
            per_song.append({"song": i, "seconds": round(float(measured[i]), 2),
                             "source": "measured"})
        else:
            per_song.append({"song": i, "seconds": fallback, "source": "assumed"})
    song_total = sum(p["seconds"] for p in per_song)
    est_speech_min = (script_chars_value / rate) if rate else 0.0
    speech_seconds = est_speech_min * 60.0
    total_seconds = speech_seconds + song_total
    total_min = total_seconds / 60.0
    tol = SHOW["duration_tolerance"]
    lo, hi = target_minutes * (1 - tol), target_minutes * (1 + tol)
    assumed = [p["song"] for p in per_song if p["source"] == "assumed"]
    return {
        "ok": lo <= total_min <= hi,
        "target_minutes": target_minutes,
        "accept_minutes": [round(lo, 1), round(hi, 1)],
        "est_minutes": round(total_min, 1),
        "delta_minutes": round(total_min - target_minutes, 1),
        "chars": script_chars_value,
        "chars_per_minute": rate,
        "speech_minutes": round(est_speech_min, 1),
        "speech_seconds": round(speech_seconds, 2),
        "song_count": songs,
        "song_total_seconds": round(song_total, 2),
        "song_seconds_each": per_song,
        "song_seconds_assumed_for": assumed[:30],
        "song_seconds_source": ("mixed" if assumed and len(assumed) < songs
                                else ("assumed" if assumed else "measured")),
        "why": ("串词 %d 字 ÷ %d 字/分钟 ≈ %.1f 分钟；%d 首歌 ≈ %.1f 分钟；"
                "合计 ≈ %.1f 分钟；目标 %.1f 分钟，容差 %.0f%%（%.1f~%.1f 分钟）%s"
                % (script_chars_value, rate, est_speech_min, songs, song_total / 60.0,
                   total_min, target_minutes, tol * 100, lo, hi,
                   ("；其中 %d 首的曲长是**假设值**（%.0f 秒/首）不是实测值"
                    % (len(assumed), fallback)) if assumed else "")),
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
    return {"item": "串词配音 voice_tts/tts", "chars": chars,
            "points_per_1k_chars": rate, "points": round(pts, 2),
            "yuan": round(pts / POINTS_PER_YUAN, 4)}


def quote_search(calls, points_per_call=None):
    rate = float(points_per_call if points_per_call is not None else SEARCH_POINTS_PER_CALL)
    pts = max(0, int(calls)) * rate
    return {"item": "选曲 music_search/search", "calls": max(0, int(calls)),
            "points_per_call": rate, "points": round(pts, 2),
            "yuan": round(pts / POINTS_PER_YUAN, 4)}


def quote_music(creates=1, with_lyrics=False):
    n = max(0, int(creates))
    pts = n * MUSIC_POINTS_PER_CREATE
    items = [{"item": "配乐 music_generation/create x%d" % n,
              "points": n * MUSIC_POINTS_PER_CREATE}]
    if with_lyrics:
        pts += n * MUSIC_POINTS_PER_LYRICS
        items.append({"item": "歌词 music_generation/lyrics x%d" % n,
                      "points": n * MUSIC_POINTS_PER_LYRICS})
    return {"item": "配乐", "creates": n, "items": items,
            "points": round(pts, 2), "yuan": round(pts / POINTS_PER_YUAN, 4)}


def money(points):
    return None if points is None else round(points / POINTS_PER_YUAN, 4)


def points_of(res):
    """把**实际扣点**抓出来。

    结算只认 `usage.points_cost`（平台的 pricing_matrix / tenant_* 字段半数不可信）。
    同步接口见过 `actual_points`，异步任务见过 `points_cost`，两个位置都试：
    任务顶层（本包的 a7w.call 把 task 顶层的 usage 拿回来了）与 result / data 里。
    实测原文：`{"code":1,...,"data":{"result":{...},"usage":{"points_cost":10,
    "actual_points":10}}}`——music_search 的 usage 在 `data` 里，不在 `data.result`。
    """
    for holder in (a7w.dig(res, "usage"), a7w.dig(res, "data", "usage"),
                   a7w.dig(res, "result", "usage"), a7w.dig(res, "result"),
                   a7w.dig(res, "data"), res):
        if not isinstance(holder, dict):
            continue
        for k in ("points_cost", "actual_points", "points", "cost"):
            v = holder.get(k)
            if isinstance(v, (int, float)):
                return float(v)
    return None


def pick_url(result, *names):
    """在任务结果里找产物地址——音频与音乐的返回结构不一致，逐个试。"""
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

class RadioError(a7w.A7wError):
    """生产 / 生成 / 调用失败（网络、鉴权、点数、模型名、音色）。→ 退出码 4"""


class UsageError(RadioError):
    """参数/配置/环境用错了。→ 退出码 2

    为什么要跟 RadioError 分开：这两类错误的**处理方式完全不同**。
    参数错了要改命令重跑，不花一分钱（比如 --outdir 指到包内、没报价就开跑）；
    调用失败要查 Key / 点数 / 模型名 / 音色。混成一个退出码，CI 里就没法区分。
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
    一期串词是一个一千多字的长产出，被一次抖动打断要重跑整篇，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。

    成功响应**不带 `code` 字段**（实测），所以这里不判 code；只判 choices 在不在。
    `code == 1` 那套信封是**生成应用**（voice_tts / music_search / music_generation）
    的，不适用于本端点。
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
                raise RadioError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise RadioError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise RadioError(
                    "模型不存在（404）：{}  用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 429，{}s 后重试…\n".format(3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise RadioError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise RadioError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    if payload is None:
        raise RadioError("网络错误：{}".format(last_exc))

    # 兜底：万一网关换了形态包了一层 {"code":1,"data":{...}}，两种都认。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise RadioError("模型没返回 choices：{}".format(
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
        raise RadioError("模型返回空内容")
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
    raise RadioError("模型返回的不是合法 JSON：{}{}".format(
        text[:300].replace("\n", " "), _fr_hint()))


# ---------------------------------------------------------------------------
# 生成应用调用（配音 / 选曲 / 配乐）
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
        raise RadioError("{} {} 调用失败：{}".format(app, api, exc))


def do_tts(key, text, reference_id=None, fmt="mp3", model="s2-pro",
           speed=None, timeout=1800):
    """串词配音：短文本走同步 `voice_tts/tts`，超长走异步 `voice_tts/tts_async`。

    **实测参数名**：音色是 `reference_id`（值是 list_voices 的 id / model_id），
    **不是 `voice_id`**——本包开工前用 `python scripts/a7w.py schema voice_tts` 现查确认。
    同步接口 schema 原文「建议不超过 500 字符」，所以调用方按 TTS_SYNC_MAX_CHARS 分块；
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
    except RadioError as exc:
        if reference_id and "任务处理失败" in str(exc):
            raise RadioError(
                "%s\n  排查：这条错误最常见的成因是 **reference_id 不完整或不存在**——"
                "list_voices 返回的 id 是 32 位十六进制，抄短了就会得到这句"
                "「任务处理失败」。用 `run.py voices` 重新整条复制；"
                "去掉 --voice（不指定音色）可以立刻区分是音色问题还是文本问题。"
                % exc)
        raise


def do_search(key, keyword, page=1, page_size=5, timeout=90):
    """选曲搜索：POST /api/v1/apps/music_search/search（**同步**，实测 10 点/次）。

    schema 原文：`page` 页码从 1 开始；`keyword` 歌曲名/歌手名/专辑关键词；
    `page_size` 每页条数**最大 20**。返回 `data.result.items[]`，
    每项 `{type, songid, title, author, pic, link, url}`，`url` 是可直接下载的 mp3。
    **它不是免费接口**——本包每次调用前都会报价。
    """
    if page_size > SEARCH_MAX_PAGE_SIZE:
        page_size = SEARCH_MAX_PAGE_SIZE
    body = {"keyword": keyword, "page": int(page), "page_size": int(page_size)}
    return _call_app(APP_SEARCH, "search", body, key, wait=True, timeout=timeout)


def do_music(key, style=None, prompt=None, title=None, lyric=None,
             instrumental=True, timeout=1800):
    """配乐：POST /api/v1/apps/music_generation/create。

    **实测动作名是 `create`，不是 `generate`**（本包开工前用
    `python scripts/a7w.py schema music_generation` 现查确认；接口代码里没有 `generate`，
    `generate` 只是 `type` 参数的一个取值）。
    长度参数在这个接口的参数表里**不存在**，所以垫乐长度控制在 mix 阶段用 ffmpeg 做。
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


def search_items(res):
    """从 music_search 的返回里取出 items 列表（实测路径 data.result.items）。"""
    for holder in (a7w.dig(res, "result"), a7w.dig(res, "data", "result"),
                   a7w.dig(res, "data"), res):
        if isinstance(holder, dict):
            for k in ("items", "list", "songs", "data"):
                v = holder.get(k)
                if isinstance(v, list):
                    return v
        if isinstance(holder, list):
            return holder
    return []


def search_more(res):
    """`data.result.has_more`——还有没有下一页（实测字段名就是这个）。"""
    v = a7w.dig(res, "result", "has_more")
    if v is None:
        v = a7w.dig(res, "data", "result", "has_more")
    return bool(v) if v is not None else None


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


def section_breakdown(script):
    """串词各段的字数与总字数。"""
    rows = []
    for sec in script.get("sections") or []:
        rows.append({"name": sec.get("name"), "kind": sec.get("kind"),
                     "chars": count_chars(sec.get("body") or "")})
    return rows


def script_chars(script):
    return sum(count_chars(s.get("body") or "")
               for s in script.get("sections") or [])


def render_plan_md(plan, model=None, usage=None, elapsed=None):
    out = ["# 节目单 · %s" % (plan.get("title") or "")]
    out.append("")
    if plan.get("episode"):
        out.append("- 期号：%s" % plan["episode"])
    if plan.get("host"):
        out.append("- 主播人设：%s" % plan["host"])
    if plan.get("audience"):
        out.append("- 目标听众：%s" % plan["audience"])
    if plan.get("mode"):
        out.append("- 节目类型：%s" % plan["mode"])
    out.append("- 目标时长：%s" % fmt_minutes(plan.get("minutes") or 0))
    out.append("- 歌曲数：%d 首" % len(plan.get("tracks") or []))
    if plan.get("open_intent"):
        out.append("- 开场意图：%s" % plan["open_intent"])
    if plan.get("close_intent"):
        out.append("- 结尾意图：%s" % plan["close_intent"])
    if model:
        out.append("- 模型：`%s`　命令端点：`POST /api/v1/chat/completions`" % model)
    if usage:
        out.append("- token 用量：prompt=%s completion=%s total=%s" % (
            usage.get("prompt_tokens", "-"), usage.get("completion_tokens", "-"),
            usage.get("total_tokens", "-")))
    if elapsed is not None:
        out.append("- 耗时：%.1fs" % elapsed)
    out += ["", "| 序 | 曲目 | 歌手 | 曲长 | 串词意图 | 过渡要说什么 |",
            "|---|---|---|---|---|---|"]
    for t in plan.get("tracks") or []:
        out.append("| %s | %s | %s | %s | %s | %s |" % (
            t.get("no"), t.get("title") or "（缺）", t.get("artist") or "-",
            fmt_mmss(t.get("seconds") or 0), t.get("intent") or "-",
            t.get("transition_intent") or "（缺）"))
    out.append("")
    return "\n".join(out)


def render_script_md(script, meta=None):
    """把串词渲染成**成品 Markdown**。

    这个渲染结果不是给人看的副产品——闸门四、闸门三读的就是它。
    改这里的格式等于改闸门的输入，必须同步改 SECTION_HEAD_RE。
    """
    meta = meta or {}
    out = ["# %s" % (script.get("title") or "未命名")]
    out.append("")
    if meta.get("host"):
        out.append("> 主播：%s" % meta["host"])
    if meta.get("songs"):
        out.append("> 曲目：%d 首　过渡段：%d 条" % (meta["songs"], meta["songs"]))
    if meta.get("minutes"):
        out.append("> 目标时长：%s（按 %d 字/分钟估串词）"
                   % (fmt_minutes(meta["minutes"]), cpm()))
    out.append("")
    for sec in script.get("sections") or []:
        out.append("## 【%s】" % sec.get("name"))
        out.append("")
        out.append((sec.get("body") or "").strip())
        out.append("")
    return "\n".join(out)


def render_timeline_md(rows, total_seconds, meta=None):
    meta = meta or {}
    out = ["# 节目时间轴", ""]
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


def render_program_list(playlist, script, plan, outdir):
    """节目单：给排播 / 上架用的一张纯文本表。"""
    lines = ["# 节目单 / Program List", ""]
    lines.append("节目：%s" % (plan.get("title") or Path(outdir).name))
    if plan.get("episode"):
        lines.append("期号：%s" % plan["episode"])
    lines.append("主播：%s" % (plan.get("host") or SHOW["host"]))
    lines.append("曲目：%d 首" % len(playlist))
    lines.append("")
    lines.append("序号\t曲目\t歌手\t曲长\t来源\t本地文件\t过渡段")
    lines.append("----\t----\t----\t----\t----\t--------\t------")
    by_no = {}
    for sec in (script.get("sections") or []):
        if sec.get("kind") == "trans":
            by_no[sec.get("index")] = sec.get("name")
    for i, t in enumerate(playlist, 1):
        lines.append("%d\t%s\t%s\t%s\t%s\t%s\t%s" % (
            i, t.get("title") or "-", t.get("artist") or "-",
            fmt_mmss(t.get("seconds") or 0),
            t.get("source") or "-",
            Path(t["file"]).name if t.get("file") else "(缺)",
            by_no.get(i) or "（缺）"))
    lines.append("")
    lines.append("开场：%s" % ((script.get("open") or "")[:60] or "（缺）"))
    lines.append("结尾：%s" % ((script.get("close") or "")[:60] or "（缺）"))
    lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 提示词构造
#
# 【铁律】提示词里**不许出现任何一句可直接复制的完整中文句子**。
# 举例只用描述性说明（「主播先给一个具体的听觉场景」），
# 真实示例一律登记在 PROMPT_SAMPLES，并由 prompt_hygiene() 在 --dry-run 时自检。
# 依据见上面 prompt_echo 的事故复盘：模型会照抄示例，哪怕标着"这是错的写法"。
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是三剪客的电台节目制作人，做过大量中文音乐电台与歌单节目。"
    "你只输出 JSON，不输出任何解释、前言、Markdown 代码块围栏之外的文字。"
    "你写的东西必须是**主持人可以直接照读的口播稿**，不是文章、不是乐评。"
    "禁止编造具体的人名、机构名、奖项名、榜单名、真实数据与不存在的作品背景；"
    "需要提背景时只能用可核查的泛指表述，不确定就明说不确定。"
    "禁止使用广告法违禁的最高级用语与效果承诺。"
    "禁止在口播里念出联系方式、引导加好友、引导下载 App。"
)

# 「串词三件事」的说明块。写成**职责描述**而不是示例句——
# 一旦在这里放一句像样的串词，模型下一轮就会原样吐出来（本库实测过两次）。
SECTION_DUTY_BLOCK = (
    "串词必须写满三件事，缺一件本地闸门就拦：\n"
    "  1. 开场（只有一个）：把这一期的听觉场景与情绪基调先立住，"
    "说清这一期为什么值得从头听完；不要只报节目名再寒暄。\n"
    "  2. 每首歌之前的过渡（**每首歌一条，条数与歌数相等，编号从 1 连续到 N**）："
    "承接上一首留下的情绪，给出下一首为什么此刻响起的理由；"
    "可以点出歌名与歌手，但不要念参数、不要写成资料卡。\n"
    "  3. 结尾（只有一个）：给一个能被单独转述的收束句，"
    "让听众知道这一期到此完整了；不要只是道别。\n"
    "写法要求：\n"
    "  · 全部是口播口语：可以有短句、停顿、自我修正，不要书面长句\n"
    "  · **不要把歌名与歌手堆在一句话里报完**，那是报幕不是串词\n"
    "  · 不要出现变量占位符（成对花括号、方括号里留空、连续大写占位字母）\n"
    "  · 不要让模型自报结构字段代替正文：正文就是你要读的那些字\n"
)


def script_quotas(minutes, songs, chars_per_minute=None):
    """把目标串词字数**摊到每一段**上，返回可直接写进提示词的配额表。

    【为什么必须逐段给，而不是只给一个总数】实测两轮都栽在这里：
      · 第一轮只写「目标总时长 30 分钟」，模型写 771 字（应约 3792 字）；
      · 第二轮只写「串词合计约 3792 字」，模型写 623 字 —— 总数它在括号里看到了，
        但不把它当回事（同族播客包也踩过完全一样的坑：只写总字数，模型只写一半）。
    同族定稿的结论是：**给模型的约束要落在它能逐项对齐的粒度上**。

    【为什么不追求"各段之和恰好等于目标"】前两版都做了这个回填，结果都一样蠢：
    30 分钟只放 4 首时，唯一能装下余数的位置是开场，于是配额被回填成
    「开场 2052 字 + 4 条过渡 325 字」——**开场比四首歌的串词加起来还长**。
    配额表的作用是让模型逐段对齐，不是做账；所以这里改成：
      · 过渡按 `trans_max_chars` 的 2.5 倍封顶，超出部分**不进配额**（保留余地）
      · 开场/结尾按窗口封顶
      · `sum` 如实标出"按这个配额写出来大约多少字"，**不硬凑等于 total**
    真正的验收在时长台账那道闸门（±25%），它读的是成品稿的真实字数，
    对"两头写长一点、过渡写短一点"这种自然分布本来就是容错的。
    """
    rate = float(chars_per_minute or cpm())
    total = target_speech_chars(minutes, songs, rate)
    songs = max(1, int(songs))
    per_trans = min(max(SHOW["trans_min_chars"],
                        int(round(SHOW["trans_max_chars"] * 1.5))),
                    max(SHOW["trans_min_chars"], total // max(1, songs * 2)))
    win = total - per_trans * songs
    open_c = min(max(SHOW["open_min_chars"], int(round(win / 2.2))),
                 max(SHOW["open_min_chars"], int(round(SHOW["open_max_chars"] * 2.0))))
    close_c = min(max(SHOW["close_min_chars"], int(round(win / 2.6))),
                  max(SHOW["close_min_chars"], int(round(SHOW["close_max_chars"] * 2.0))))
    # 【余额再分配】上面那三行只是"初始分配"，两头之和常常远低于 total
    # （比如 60 分钟 9 首只分到 2635 字 / 目标 6891 字）。差额按剩余容量
    # 依次补给开场、结尾、过渡，**每一步都重新夹在各自的上下限里**。
    #
    # 上限怎么定：**长节目靠过渡扛，不能靠开场扛**。第一版的倍数是
    # （两头 2.0x / 过渡 3.0x），结果 60 分钟 9 首只到 67% 覆盖率——
    # 因为按那个上限，一头一尾最多 330 字、10 条过渡最多 1010 字，加起来就是不够。
    # 现在的口径是「两头封在 3.0x（约 660 字 ≈ 2.6 分钟，开场/结尾的正常上限），
    # 过渡放开到 5.0x」：过渡本来就是"承接 + 报曲名 + 一句引导"，
    # 在音乐占比高的长节目里它自然更长，而**开场不该比一首歌还长**。
    end_open_cap = max(SHOW["open_min_chars"], int(round(SHOW["open_max_chars"] * 3.0)))
    end_close_cap = max(SHOW["close_min_chars"], int(round(SHOW["close_max_chars"] * 3.0)))
    trans_cap = max(SHOW["trans_min_chars"], int(round(SHOW["trans_max_chars"] * 5.0)))
    for _ in range(3):
        gap = total - (open_c + close_c + per_trans * songs)
        if gap <= 0:
            break
        room_open = max(0, end_open_cap - open_c)
        room_close = max(0, end_close_cap - close_c)
        room_trans = max(0, (trans_cap - per_trans) * songs)
        room_all = room_open + room_close + room_trans
        if room_all <= 0:
            break
        take = min(gap, room_all)
        share_end = (room_open + room_close) / float(room_all)
        # 两头的容量优先吃掉大头（开场/结尾本来就比过渡能装），过渡补剩下的
        add_end = int(round(take * share_end))
        add_open = min(room_open, int(round(add_end * 0.5)))
        open_c += add_open
        add_close = min(room_close, max(0, add_end - add_open))
        close_c += add_close
        left = take - add_open - add_close
        if room_trans > 0 and left > 0:
            per_trans += min(trans_cap - per_trans, int(left / float(songs)))
    return {"total": total, "open": open_c, "close": close_c,
            "trans": per_trans, "songs": songs,
            "sum": open_c + close_c + per_trans * songs,
            "caps": {"open": end_open_cap, "close": end_close_cap, "trans": trans_cap}}


def build_plan_prompt(topic, minutes, songs, mode=None, audience=None,
                      brief=None, playlist=None, host=None):
    """拼节目单提示词。

    【逐首配额是实测逼出来的，不是设计洁癖】只写一句「合计约 N 字」时，
    模型会按歌数只写几百字，被时长台账拦下——闸门拦得对，但这次调用白花了。
    结论：给模型的约束要**落在它能逐项对齐的粒度上**。
    """
    song_total_min = (songs * SHOW["song_seconds_fallback"]) / 60.0
    # 【串词目标字数 = 目标时长 − 歌曲时长，再削掉一半容差】见 target_speech_min 的注释。
    # 第一版这里是 `minutes - song_total_min`（不含容差折减），得出的目标偏乐观；
    # 现在统一走同一个函数，**提示词、时长台账、成本报价三处用同一个数**。
    target_chars = target_speech_chars(minutes, songs)
    room_min = max(0.5, minutes - song_total_min)      # 留给串词的全部时间
    per_trans = max(SHOW["trans_min_chars"],
                    int((target_chars
                         - SHOW["open_max_chars"] - SHOW["close_max_chars"])
                        / max(1, songs)))
    parts = [
        "请为下面这个主题设计一期电台节目的**节目单**（选曲顺序 + 每段串词要说什么）。",
        "",
        "主题：%s" % topic,
    ]
    if mode:
        parts.append("节目类型：%s" % mode)
    if audience:
        parts.append("目标听众：%s" % audience)
    if host:
        parts.append("主播人设：%s" % host)
    if brief:
        parts.append("额外要求：%s" % brief)
    if playlist:
        parts += ["", "本期必须用的曲目（**顺序与歌手一律照抄，不许替换、不许增删**）："]
        for i, t in enumerate(playlist, 1):
            parts.append("  %d. %s —— %s" % (i, t.get("title") or "", t.get("artist") or ""))
    parts += [
        "",
        "节目规格：",
        "  · 目标总时长 %d 分钟；其中歌曲 %d 首，串词合计约 %d 字" % (
            minutes, songs, target_chars),
        "  · 开场约 %d~%d 字；结尾约 %d~%d 字；每首之前的过渡约 %d~%d 字" % (
            SHOW["open_min_chars"], SHOW["open_max_chars"],
            SHOW["close_min_chars"], SHOW["close_max_chars"],
            SHOW["trans_min_chars"], max(SHOW["trans_min_chars"], per_trans)),
        # 【这一条是实测逼出来的】：第一版只写了目标总时长，模型给 8 首都填 300 秒
        # （合计 40 分钟），一期 30 分钟的节目当场被时长台账拦下。
        # 教训与逐章字数配额同源：**给模型的约束要落在它能逐项对齐的粒度上**，
        # 所以这里把「seconds 之和」这个可加总的硬数写出来。
        "  · **tracks 的 seconds 之和必须约为 %d 秒**（= 目标 %d 分钟 − 串词约 %.1f 分钟）；"
        "单首按这个总数分配，不要每首都填 5 分钟（那合计就是 %.0f 分钟，是 %.0f 分钟节目）"
        % (int(song_total_min * 60), minutes, room_min,
           songs * 300.0 / 60.0, songs * 300.0 / 60.0),
        "  · 选曲要有**情绪推进**：前一首先立住场景，后一首再往深处走，不要并列罗列",
        "  · 每首歌的过渡意图要**具体**：说清这首歌解决的是上一首留下的什么情绪",
        "",
        SECTION_DUTY_BLOCK,
        "输出 JSON 对象，字段：",
        '  title        字符串，节目名，12~26 字，一眼看出听什么、什么时候听',
        '  episode      字符串，期号或副标题，可空',
        '  host         字符串，主播人设一句话',
        '  audience     字符串，目标听众画像',
        '  mode         字符串，节目类型（例如深夜陪伴 / 通勤 / 咖啡馆背景音）',
        '  open_intent  字符串，开场要立的听觉场景与情绪基调',
        '  tracks       数组，**恰好 N 项**，每项 {no, title, artist, seconds, intent,',
        '               transition_intent}',
        '               title/artist 是曲目与歌手；seconds 是估计曲长（秒，整数）',
        '               intent 是这首歌在整期里的作用；',
        '               transition_intent 是它之前那条过渡要说什么',
        '  close_intent 字符串，结尾要怎么收',
        "",
        "再次强调：只输出这个 JSON 对象，tracks 的条数必须等于 %d。" % songs,
    ]
    return "\n".join(parts)


def build_script_prompt(plan, playlist, host=None, brief=None, minutes=None,
                        songs=None):
    """拼串词提示词。

    **逐段配额挂到每一段那一行**，并且给出**总数**（两者都要）：
    只给总数，模型会少写一半（实测 3792 字的目标写成 623 字）；
    只给每段区间，模型会全部取下限（合计远低于目标）。
    同族的定稿口径是「配额落到能逐项对齐的粒度」，这里照办，并额外把
    每段配额的**合计**摆出来让模型自己能对数。
    """
    n = int(songs or len(plan.get("tracks") or []) or len(playlist or []) or 1)
    mins = float(minutes or plan.get("minutes") or SHOW["default_minutes"])
    q = script_quotas(mins, n)
    lines = []
    for i, t in enumerate(plan.get("tracks") or [], 1):
        lines.append("  第 %d 首《%s》—— %s｜这首歌的作用：%s｜过渡要说的：%s" % (
            i, t.get("title") or "", t.get("artist") or "",
            t.get("intent") or "-", t.get("transition_intent") or "-"))
    parts = [
        "请按下面这份节目单，写出这一期电台节目的**完整串词**（要照读的口播稿）。",
        "",
        "节目名：%s" % (plan.get("title") or ""),
        "主播：%s" % (host or plan.get("host") or SHOW["host"]),
        "开场要立的场景：%s" % (plan.get("open_intent") or "-"),
        "结尾要收的方向：%s" % (plan.get("close_intent") or "-"),
    ]
    if brief:
        parts.append("额外要求：%s" % brief)
    parts += ["", "曲目与每首之前的过渡要说什么："] + lines + [""]
    parts += [
        SECTION_DUTY_BLOCK,
        "字数配额（**这是硬指标**，本地闸门会按串词总字数估算时长并核对；"
        "写得比配额少会被拦下，整期重跑）：",
        "  ⚠️ 字数**不是越短越好**：一期 %d 分钟的节目，串词合计要写够 %d 字左右，"
        "只写几百字会被本地时长闸门判成「这一期撑不满」并整期拦下。"
        % (mins, q["total"]),
        "  开场：**约 %d 字 / 不少于 %d 句**（不少于 %d 字）"
        % (q["open"], max(3, int(round(q["open"] / 45.0))),
           max(SHOW["open_min_chars"], int(q["open"] * 0.8))),
    ]
    for i in range(1, n + 1):
        parts.append("  过渡 %d：**约 %d 字 / 不少于 %d 句**（不少于 %d 字）"
                     % (i, q["trans"], max(2, int(round(q["trans"] / 45.0))),
                        max(SHOW["trans_min_chars"], int(q["trans"] * 0.8))))
    parts += [
        "  结尾：**约 %d 字 / 不少于 %d 句**（不少于 %d 字）"
        % (q["close"], max(3, int(round(q["close"] / 45.0))),
           max(SHOW["close_min_chars"], int(q["close"] * 0.8))),
        "  （一句台词按 40~60 字估；**逐段数句数**比逐段数字数好对齐）",
        "",
        "  以上合计约：**%d 字**（开场 %d + 过渡 %d×%d + 结尾 %d）。"
        "**每段都要写够**；合计差得太远会被本地闸门按总时长拦下。"
        % (q["sum"], q["open"], q["trans"], n, q["close"]),
        "",
        "输出 JSON 对象，字段：",
        '  title     字符串，与上面节目名一致',
        '  host      字符串，主播人设',
        '  open      字符串，开场全文（口播稿）',
        '  transitions 数组，**恰好 %d 项**，每项 {no, body}' % n,
        '             no 从 1 连续编号，body 是要照读的过渡串词全文',
        '  close     字符串，结尾全文（口播稿）',
        "",
        "再次强调：transitions 的条数必须等于 %d；每段都要写成可照读的完整口播稿，"
        "不许用省略标记代替正文；每段都要按上面的配额写够字数。" % n,
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 产出归一化
# ---------------------------------------------------------------------------

def normalize_plan(raw, minutes, songs):
    """把模型返回的节目单收拾成内部结构（缺项如实登记，不偷偷补）。"""
    def s(v):
        return str(v if v is not None else "").strip()

    plan = {
        "title": s((raw or {}).get("title")),
        "episode": s((raw or {}).get("episode")),
        "host": s((raw or {}).get("host")),
        "audience": s((raw or {}).get("audience")),
        "mode": s((raw or {}).get("mode")),
        "open_intent": s((raw or {}).get("open_intent")),
        "close_intent": s((raw or {}).get("close_intent")),
        "minutes": float(minutes),
        "tracks": [],
    }
    tracks = (raw or {}).get("tracks") or []
    if not isinstance(tracks, list):
        tracks = []
    for i, t in enumerate(tracks, 1):
        if not isinstance(t, dict):
            continue
        try:
            sec = int(float(t.get("seconds") or 0))
        except (TypeError, ValueError):
            sec = 0
        plan["tracks"].append({
            "no": t.get("no") or i,
            "title": s(t.get("title")),
            "artist": s(t.get("artist")),
            "seconds": sec,
            "intent": s(t.get("intent")),
            "transition_intent": s(t.get("transition_intent")),
        })
    if not plan["tracks"]:
        raise RadioError("模型返回的节目单里没有 tracks（曲目表），重跑一次或换个模型")
    plan["songs_requested"] = int(songs)
    plan["songs_filled"] = (len(plan["tracks"]) != int(songs))
    return plan


def normalize_script(raw, plan, host=None):
    """把模型返回的串词收拾成内部结构：开场 + 过渡 N 条 + 结尾。"""
    def s(v):
        return str(v if v is not None else "").strip()

    n = len(plan.get("tracks") or [])
    raw_trans = (raw or {}).get("transitions") or []
    if not isinstance(raw_trans, list):
        # 模型偶尔写成 {"1": {...}} 这种字典形态，按 key 排序抢救一下
        if isinstance(raw_trans, dict):
            raw_trans = [raw_trans[k] for k in sorted(raw_trans, key=lambda x: str(x))]
        else:
            raw_trans = []
    sections = [{"name": SEC_OPEN, "kind": "open", "index": None,
                 "body": s((raw or {}).get("open"))}]
    for i, tr in enumerate(raw_trans, 1):
        if isinstance(tr, dict):
            body = s(tr.get("body") or tr.get("text"))
        else:
            body = s(tr)
        # 【编号一律用清单里的位置，不采信模型自报的 `no`】实测踩过：
        # 模型把 4 条过渡编成 2/3/4/5（第一条的前奏被它算进了开场），
        # 渲染出来就是「过渡 2..5」——编号闸门当场拦下，但那是一次白花的调用。
        # 过渡的语义是"第 i 首歌之前那条"，位置就是它的定义，
        # 模型自报的 `no` 只是它自己的计数习惯，**不能当事实用**。
        sections.append({"name": "%s %d" % (SEC_TRANS, i), "kind": "trans",
                         "index": i, "body": body})
    sections.append({"name": SEC_CLOSE, "kind": "close", "index": None,
                     "body": s((raw or {}).get("close"))})
    return {
        "title": s((raw or {}).get("title")) or (plan.get("title") or ""),
        "host": s((raw or {}).get("host")) or (host or plan.get("host") or SHOW["host"]),
        "songs": n,
        "sections": sections,
        "open": s((raw or {}).get("open")),
        "close": s((raw or {}).get("close")),
        "transitions": [{"no": sec["index"], "body": sec["body"]}
                        for sec in sections if sec["kind"] == "trans"],
    }


def script_from_md(md_text, songs=None):
    """从任意 `.md` 稿子反解出内部结构（手工改过的稿子也能进配音/混音）。

    **闸门读的永远是成品稿**，所以这条路也照样走 gate_script。
    """
    parsed = parse_script_md(md_text)
    sections = [{"name": x["name"], "kind": x["kind"], "index": x["index"],
                 "body": x["body"]} for x in parsed["sections"]]
    title = ""
    for line in (md_text or "").splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    host = None
    m = re.search(r"^>\s*主播[：:]\s*(.+)$", md_text or "", re.M)
    if m:
        host = m.group(1).strip()
    n = songs
    if n is None:
        n = len([x for x in sections if x["kind"] == "trans"]) or 1
    # 【过渡段按稿子里的编号排序后重新编号】手工改过的稿子可能写成「过渡 2..5」
    # （漏了 1 或从 0 起）。过渡的语义是"第 i 首歌之前那条"，**位置就是它的定义**，
    # 所以这里按声明编号排序、再重编 1..N；声明编号与原顺序不一致时明确提示。
    # 编号闸门仍然拦"条数不对"（那是真的缺内容），但不拦"编号写法不同"——
    # 拦后者只会让一份内容完整的稿子白跑一轮配音。
    trans = [x for x in sections if x["kind"] == "trans"]
    declared = [x["index"] for x in trans]
    trans_sorted = sorted(trans, key=lambda x: (x["index"] is None, x["index"] or 0))
    if declared and declared != list(range(1, len(trans) + 1)):
        sys.stderr.write("提示：稿子里的过渡编号是 %s，已按顺序重编为 1~%d\n"
                         % ("、".join(str(i) for i in declared), len(trans)))
    for i, x in enumerate(trans_sorted, 1):
        x["name"] = "%s %d" % (SEC_TRANS, i)
        x["index"] = i
    sections = ([x for x in sections if x["kind"] == "open"]
                + trans_sorted
                + [x for x in sections if x["kind"] == "close"]
                + [x for x in sections if x["kind"] not in ("open", "trans", "close")])
    return {
        "title": title,
        "host": host or SHOW["host"],
        "songs": int(n),
        "sections": sections,
        "open": next((x["body"] for x in sections if x["kind"] == "open"), ""),
        "close": next((x["body"] for x in sections if x["kind"] == "close"), ""),
        "transitions": [{"no": x["index"], "body": x["body"]}
                        for x in sections if x["kind"] == "trans"],
    }


# ---------------------------------------------------------------------------
# 闸门执行：对一份串词稿跑全部本地检查
# ---------------------------------------------------------------------------

def compliance_scan(text, show_redlines=True):
    """扫违禁词 + 口播红线。

    返回 {"hits": [...], "exempted": [...]}：
      · hits      —— 判定命中，硬闸门拦截
      · exempted  —— 疑似命中但语境判断为「在说数据极值而不是商品宣称」，放过但登记
    """
    text = text or ""
    hits, exempted = [], []
    for rx, lvl, why, ctx in BANNED_RE:
        if ctx != "superlative":
            m = rx.search(text)
            if m:
                hits.append({"word": m.group(0), "level": lvl, "why": why, "scope": "广告法"})
            continue
        # 最高级那一族：逐个 `最X` 判语境豁免（见 _is_data_extreme 的长注释）
        for m in SUPERLATIVE_RE.finditer(text):
            if _is_data_extreme(text, m):
                exempted.append({
                    "word": m.group(0),
                    "why": "疑似绝对化用语，但「最」不在句首、前一个字是计量类名词、"
                           "后面紧跟「的/之」，判断为在描述数据极值（不是商品/服务宣称）"
                           "——本地放过，请人工确认",
                    "context": text[max(0, m.start() - 10):m.end() + 10],
                })
                continue
            hits.append({"word": m.group(0), "level": lvl, "why": why, "scope": "广告法"})
    if show_redlines:
        for rx, lvl, why in SHOW_REDLINE_RE:
            m = rx.search(text)
            if m:
                hits.append({"word": m.group(0), "level": lvl, "why": why,
                             "scope": "口播红线"})
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


def gate_script(script, md_text, songs, target_minutes,
                song_seconds=None, measured_songs=None):
    """对一份成品串词稿跑闸门一~五。闸门六（成本）在调用方单独管。"""
    scan = compliance_scan(md_text)
    ph = placeholder_scan(md_text)
    echoes = prompt_echo_scan(md_text, label="串词")
    struct = script_structure_gate(md_text, songs)
    chars = script_chars(script)
    dur = duration_gate(chars, songs, target_minutes, song_seconds=song_seconds,
                        measured_songs=measured_songs)
    g = {
        "compliance": {"ok": not scan["hits"], "hits": scan["hits"],
                       "exempted": scan["exempted"]},
        "placeholder": {"ok": not ph, "hits": ph},
        "prompt_echo": {"ok": not echoes, "hits": echoes},
        "structure": struct,
        "duration": dur,
    }
    g["ok"] = all(g[k]["ok"] for k in
                  ("compliance", "placeholder", "prompt_echo", "structure", "duration"))
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
    sys.stderr.write(_red("!! %s被硬闸门拦下，不可直接录制/播出%s\n"
                          % ("串词稿" if g.get("structure") else "节目单",
                             ("（%s）" % show_name) if show_name else "")) + "\n")
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
    struct = g.get("structure")
    if struct and not struct["ok"]:
        for p in struct["problems"]:
            sys.stderr.write("   [串词结构] %s\n" % p)
    # 时长闸门有两种形态：节目单阶段是 problems 列表，串词阶段是时长台账 dict。
    # 两个都认——只认一种会让另一条路的命中**静默不出现在 stderr**（等于没报）。
    dur = g.get("duration") or {"ok": True}
    if not dur.get("ok", True):
        if dur.get("problems"):
            for p in dur["problems"]:
                sys.stderr.write("   [时长] %s\n" % p)
        elif dur.get("why"):
            sys.stderr.write("   [时长台账] %s（偏离目标 %+.1f 分钟）\n"
                             % (dur["why"], dur.get("delta_minutes") or 0.0))
        else:
            sys.stderr.write("   [时长] 未通过时长闸门\n")
    sys.stderr.write("\n   人读结果见标准输出；机器读用 --json。\n")
    return EXIT_GATE


# ---------------------------------------------------------------------------
# 产出目录与断点续跑
#
# 【断点 key 必须含全部影响产出的维度】
# 本库同族实测踩过三次，每次都是"静默复用旧产物"，比报错危险得多：
#   · 内容截断（`--sample-chars`）不入 key → 试跑的短音频被当成完整产物复用
#   · `resolution` 不入 key              → 改了档位却拿到旧档位的图
#   · 死参数（收了参数但没进 key 也没进请求）→ 用户以为改了，其实没改
# 本包的口径：**把真正发给接口的那个 body（加上所有影响产出的选项）整体入 key**，
# 而不是手挑几个字段。少挑一个就是一次静默复用。
# 配音的 key 里因此包含：正文 + reference_id + 语速 + 模型 + 格式 + 后端端点。
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
        "  请换到包外目录，例如 %%TEMP%%\\radio 或 D:/radio/ep01。"
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


def body_key(body):
    """把**真正要发出去的请求体**规范化成断点 key 的一部分。

    为什么要整体入 key 而不是手挑字段：同族实测踩过「resolution 不入 key」
    导致改了档位仍复用旧产物。手挑字段的错法永远是"漏了某个维度"，
    而整体入 key 的错法只有"忘了把某个字段放进 body"——后者在代码里看得见。
    """
    return text_hash(json.dumps(body, ensure_ascii=False, sort_keys=True))


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
    """把串词切成配音片段。

    切法：**按串词段切**（开场 / 过渡 i / 结尾各是独立音频），
    段内超过同步上限再拆块。为什么不整篇合成一段：
    电台里串词必须跟歌曲交替出现，一段整音频没法插到歌与歌之间。
    """
    chunks, used = [], 0
    for sec in script.get("sections") or []:
        body = (sec.get("body") or "").strip()
        if not body:
            continue
        if sample_chars and used >= sample_chars:
            break
        if sample_chars and used + len(body) > sample_chars:
            body = body[:max(0, sample_chars - used)]
        if not body:
            break
        used += len(body)
        for i, piece in enumerate(split_long_text(body), 1):
            chunks.append({"section": sec.get("name"), "kind": sec.get("kind"),
                           "index": sec.get("index"), "text": piece, "part": i})
    for i, ch in enumerate(chunks, 1):
        ch["order"] = i
        ch["chars"] = len(ch["text"])
        ch["file_stem"] = "%03d-%s" % (i, safe_name(ch["section"] or "sec"))
    return chunks


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
#   · `all` 复用子命令的处理函数，必须把子步骤产出**收集**起来合并成一份再吐，
#     否则 stdout 会出现好几个 JSON 文档、`json.loads` 直接 `Extra data`（同族实测踩过）
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


# `all` 会复用各子命令的处理函数，而那些函数各自会 `_emit` 一次。
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
        if getattr(a, "out", None):
            Path(a.out).write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("已写入 %s\n" % a.out)
        _json_write(body)
        return
    if getattr(a, "out", None):
        Path(a.out).write_text(md_text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 %s\n" % a.out)
    print(md_text)


# ---------------------------------------------------------------------------
# 子命令的公共部分
# ---------------------------------------------------------------------------

def _read_plan(a):
    p = Path(a.plan) if getattr(a, "plan", None) else (Path(a.outdir) / PLAN_JSON)
    if not p.is_file():
        raise UsageError("找不到节目单文件：%s（先跑 `plan`，或 --plan 指定）" % p)
    obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    plan = obj.get("plan") if isinstance(obj, dict) and "plan" in obj else obj
    if not isinstance(plan, dict) or not plan.get("tracks"):
        raise UsageError("节目单文件里没有 tracks：%s" % p)
    plan.setdefault("minutes", SHOW["default_minutes"])
    plan.setdefault("host", SHOW["host"])
    return plan


def _read_script(a, songs=None):
    """读串词稿，返回 (script, 成品 Markdown, meta)。

    支持两种形态：
      · `script.json`（本包 `script` 的产出）—— 读 JSON 里的 sections
      · 任意 `.md` —— 用 SECTION_HEAD_RE 解析（这样手工改过的稿子也能进配音/混音）
    两种都最终渲染成 Markdown 再过闸门：**闸门读的永远是成品稿**。

    meta["target_minutes"] 是**时长台账的基准**，必须从稿子本身带过来：
    第一版 `voice` 没带，默认用了 30 分钟，于是拿一期 8 分钟的稿子去配音时，
    被自己的时长闸门以「约 7.5 分钟 ≠ 30 分钟」拦下——闸门没错，是**基准取错了**。
    """
    p = Path(a.script) if getattr(a, "script", None) else (Path(a.outdir) / SCRIPT_JSON)
    if not p.is_file():
        alt = Path(a.outdir) / SCRIPT_MD
        if not getattr(a, "script", None) and alt.is_file():
            p = alt
        else:
            raise UsageError("找不到串词稿：%s（先跑 `script`，或 --script 指定）" % p)
    if p.suffix.lower() == ".md":
        md = p.read_text(encoding="utf-8", errors="replace")
        script = script_from_md(md, songs=songs)
        m = re.search(r"目标时长：(\d+(?:\.\d+)?)\s*分钟", md)
        meta = {"target_minutes": float(m.group(1)) if m else None,
                "host": script.get("host"), "songs": script.get("songs")}
        return script, md, meta
    obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    script = obj.get("script") if isinstance(obj, dict) and "script" in obj else obj
    if not isinstance(script, dict) or not script.get("sections"):
        raise UsageError("串词稿文件里没有 sections：%s" % p)
    script.setdefault("host", SHOW["host"])
    meta = {"target_minutes": (obj or {}).get("target_minutes"),
            "songs": (obj or {}).get("songs"), "host": script.get("host")}
    return script, render_script_md(script, meta), meta


def _read_playlist(a):
    """读歌单文件，返回 [{index, title, artist}]。

    支持三种写法（都用 `--from-file` 指同一个参数，按后缀分流）：
      · `.txt` / 无后缀：每行一首，`歌名 - 歌手` 或 `歌名 — 歌手` 或只有歌名；
        以 `#` 开头的行是注释
      · `.csv`：带表头 `title,artist`（也认中文表头「曲目/歌手」），或两列无表头
      · `.json`：`[{"title":..., "artist":...}]` 或 `{"tracks":[...]}`
    """
    p = Path(a.from_file)
    if not p.is_file():
        raise UsageError("找不到歌单文件：%s" % p)
    txt = p.read_text(encoding="utf-8", errors="replace")
    rows = []
    suf = p.suffix.lower()
    if suf == ".json":
        obj = json.loads(txt or "{}")
        seq = obj.get("tracks") if isinstance(obj, dict) else obj
        if not isinstance(seq, list):
            raise UsageError("歌单 JSON 里找不到 tracks 数组：%s" % p)
        for x in seq:
            if isinstance(x, dict):
                rows.append({"title": str(x.get("title") or x.get("name") or "").strip(),
                             "artist": str(x.get("artist") or x.get("author") or "").strip()})
            elif isinstance(x, str):
                rows.append({"title": x.strip(), "artist": ""})
    elif suf == ".csv":
        import csv as _csv
        for rec in _csv.reader(io.StringIO(txt)):
            if not rec or not any((c or "").strip() for c in rec):
                continue
            head = (rec[0] or "").strip()
            if head.lower() in ("title", "曲目", "歌名", "歌曲"):
                continue
            rows.append({"title": head,
                         "artist": ((rec[1] or "").strip() if len(rec) > 1 else "")})
    else:
        for line in txt.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            s = re.sub(r"^\s*\d+[.、)]\s*", "", s)          # 去掉行首序号
            parts = re.split(r"\s*[—–\-]{1,2}\s*", s, maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                rows.append({"title": parts[0].strip(), "artist": parts[1].strip()})
            else:
                rows.append({"title": s, "artist": ""})
    rows = [r for r in rows if r["title"]]
    if not rows:
        raise UsageError("歌单文件里没有解析出任何曲目：%s（每行写「歌名 - 歌手」）" % p)
    for i, r in enumerate(rows, 1):
        r["index"] = i
    return rows


def _target_minutes(a, plan=None):
    if getattr(a, "minutes", None):
        return float(a.minutes)
    if plan and plan.get("minutes"):
        return float(plan["minutes"])
    return float(SHOW["default_minutes"])


def _confirm_spend(a, quotes, what):
    """闸门六的入口：报价 → 要 --yes 或 --budget。

    返回 None 表示放行；返回退出码表示就地中止（一分钱没花）。
    """
    total = round(sum(q.get("points") or 0 for q in quotes), 2)
    sys.stderr.write("\n=== %s 成本前置报价 ===\n" % what)
    for q in quotes:
        sys.stderr.write("  · %-40s %8s 点  ≈ %s 元\n"
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
# 子命令：plan
# ---------------------------------------------------------------------------

def _run_plan(a):
    minutes = _target_minutes(a)
    if not (SHOW["min_minutes"] <= minutes <= SHOW["max_minutes"]):
        raise UsageError("--minutes 要在 %d~%d 之间（给的是 %s）"
                         % (SHOW["min_minutes"], SHOW["max_minutes"], minutes))
    # 【歌曲数的默认值按目标时长反推，而不是写死 8】见 suggest_songs 的注释：
    # 30 分钟 + 8 首（各 210 秒）只剩 500 字串词，这档规格本身不成立。
    songs = int(a.songs or suggest_songs(minutes))
    playlist = None
    if getattr(a, "from_file", None):
        playlist = _read_playlist(a)
        songs = len(playlist)
    if not (SHOW["min_songs"] <= songs <= SHOW["max_songs"]):
        raise UsageError("歌曲数要在 %d~%d 之间（给的是 %s）"
                         % (SHOW["min_songs"], SHOW["max_songs"], songs))
    # 【规格可行性预检】这一条是"拦截"，不是"提醒"：装不下的规格会让时长台账
    # 无论怎么调字数都过不去，与其花文本钱跑一轮再被拦，不如不花钱就讲清楚。
    feasible, why = show_feasible(minutes, songs)
    if not feasible and not a.force:
        raise UsageError("规格不成立（加上 --force 才会照跑）：%s\n"
                         "  提示：`--songs %d` 是这一档时长的推荐曲目数。"
                         % (why, suggest_songs(minutes)))
    prompt = build_plan_prompt(a.topic, minutes, songs, a.mode, a.audience,
                               a.brief, playlist, a.host)
    hygiene = prompt_hygiene(SYSTEM_PROMPT + "\n" + prompt)
    if hygiene:
        raise UsageError("提示词卫生自检失败：提示词里混进了可照抄的示例/占位符（%s）。"
                         "这是本包的红线，请改提示词。" % json.dumps(hygiene, ensure_ascii=False))
    # 【断点 key】把真正要发出去的请求体整体入 key —— 温度、模型、max_tokens、
    # 主题、曲目数、已有歌单，一个维度都不手挑（手挑就会漏，漏了就静默复用旧节目单）。
    req_body = {"model": a.model, "temperature": a.temperature,
                "max_tokens": a.max_tokens, "json_mode": (not a.no_json_mode),
                "system": SYSTEM_PROMPT, "prompt": prompt}
    key = "plan:" + body_key(req_body)
    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "endpoint": "/api/v1/chat/completions",
                       "minutes": minutes, "songs": songs, "system": SYSTEM_PROMPT,
                       "user": prompt, "state_key": key,
                       "prompt_hygiene": hygiene}, a, indent=2)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (SYSTEM_PROMPT, prompt))
        return EXIT_OK
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state = load_state(outdir)
    cached = (state.get("plan") or {})
    if cached.get("key") == key and (outdir / PLAN_JSON).is_file() and not a.force:
        obj = json.loads((outdir / PLAN_JSON).read_text(encoding="utf-8"))
        plan = obj.get("plan") or {}
        sys.stderr.write("节目单命中同一份请求（断点续跑），不再调用模型、不重复扣费\n")
        result = {"stage": "plan", "resumed": True, "state_key": key,
                  "endpoint": "/api/v1/chat/completions", "minutes": minutes,
                  "songs": len(plan.get("tracks") or []), "plan": plan,
                  "gates": obj.get("gates"), "outdir": str(outdir),
                  "files": {"json": str(outdir / PLAN_JSON), "md": str(outdir / PLAN_MD)}}
        _emit(a, result, (outdir / PLAN_MD).read_text(encoding="utf-8"), ok=True)
        return EXIT_OK

    sys.stderr.write("正在设计节目单（目标 %s，%d 首）…\n" % (fmt_minutes(minutes), songs))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    plan = normalize_plan(parse_first_json(content), minutes, songs)
    # 节目单也要过闸门一/二/三：选题阶段写进「最」字和占位符，后面会被放大到整期节目
    md = render_plan_md(plan, a.model, usage, elapsed)
    scan = compliance_scan(md)
    ph = placeholder_scan(md)
    echoes = prompt_echo_scan(md, label="节目单")
    g = {"compliance": {"ok": not scan["hits"], "hits": scan["hits"],
                        "exempted": scan["exempted"]},
         "placeholder": {"ok": not ph, "hits": ph},
         "prompt_echo": {"ok": not echoes, "hits": echoes},
         "duration": plan_duration_gate(plan, minutes)}
    g["ok"] = all(v["ok"] for k, v in g.items() if k != "ok")
    (outdir / PLAN_JSON).write_text(json.dumps(
        {"plan": plan, "model": a.model, "usage": usage, "target_minutes": minutes,
         "songs": songs, "state_key": key, "endpoint": "/api/v1/chat/completions",
         "gates": g}, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / PLAN_MD).write_text(md + "\n", encoding="utf-8")
    state["plan"] = {"key": key, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "tracks": len(plan.get("tracks") or [])}
    save_state(outdir, state)
    result = {"stage": "plan", "resumed": False, "state_key": key, "topic": a.topic,
              "minutes": minutes, "songs": len(plan.get("tracks") or []),
              "model": a.model, "endpoint": "/api/v1/chat/completions",
              "usage": usage, "elapsed": round(elapsed, 1), "plan": plan, "gates": g,
              "outdir": str(outdir),
              "files": {"json": str(outdir / PLAN_JSON), "md": str(outdir / PLAN_MD)}}
    _emit(a, result, md, ok=g["ok"])
    if not g["ok"]:
        # 节目单也要把命中**汇总到 stderr**（与串词阶段同一口径）：
        # 只写在 --json 里、stderr 一片安静，人读模式下等于没报。
        _gate_report(g, plan.get("title") or a.topic or "")
        return _fail(EXIT_GATE, "gate", "节目单命中闸门（%s）"
                     % "、".join(k for k, v in g.items() if k != "ok" and not v["ok"]))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：script
# ---------------------------------------------------------------------------

def _run_script(a):
    plan = _read_plan(a)
    songs = len(plan.get("tracks") or [])
    minutes = _target_minutes(a, plan)
    playlist = None
    if getattr(a, "from_file", None):
        playlist = _read_playlist(a)
        songs = len(playlist)
    prompt = build_script_prompt(plan, playlist, a.host or plan.get("host"), a.brief,
                                 minutes=minutes, songs=songs)
    hygiene = prompt_hygiene(SYSTEM_PROMPT + "\n" + prompt)
    if hygiene:
        raise UsageError("提示词卫生自检失败：提示词里混进了可照抄的示例/占位符（%s）。"
                         % json.dumps(hygiene, ensure_ascii=False))
    req_body = {"model": a.model, "temperature": a.temperature,
                "max_tokens": a.max_tokens, "json_mode": (not a.no_json_mode),
                "system": SYSTEM_PROMPT, "prompt": prompt}
    key = "script:" + body_key(req_body)
    if a.dry_run:
        if a.json:
            _json_out({"dry_run": True, "endpoint": "/api/v1/chat/completions",
                       "minutes": minutes, "songs": songs,
                       "system": SYSTEM_PROMPT, "user": prompt, "state_key": key,
                       "prompt_hygiene": hygiene}, a, indent=2)
        else:
            print("=== system ===\n%s\n\n=== user ===\n%s" % (SYSTEM_PROMPT, prompt))
        return EXIT_OK
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state = load_state(outdir)
    cached = (state.get("script") or {})
    if cached.get("key") == key and (outdir / SCRIPT_JSON).is_file() and not a.force:
        obj = json.loads((outdir / SCRIPT_JSON).read_text(encoding="utf-8"))
        script = obj.get("script") or {}
        sys.stderr.write("串词命中同一份请求（断点续跑），不再调用模型、不重复扣费\n")
        result = {"stage": "script", "resumed": True, "state_key": key, "songs": songs,
                  "minutes": minutes, "chars": obj.get("chars"),
                  "endpoint": "/api/v1/chat/completions", "script": script,
                  "gates": obj.get("gates"), "outdir": str(outdir),
                  "files": {"json": str(outdir / SCRIPT_JSON),
                            "md": str(outdir / SCRIPT_MD)}}
        _emit(a, result, (outdir / SCRIPT_MD).read_text(encoding="utf-8"),
              ok=bool((obj.get("gates") or {}).get("ok")))
        return EXIT_OK

    sys.stderr.write("正在写串词（%d 首 → 开场 + %d 条过渡 + 结尾）…\n" % (songs, songs))
    t0 = time.time()
    content, usage = chat(prompt, SYSTEM_PROMPT, model=a.model,
                          temperature=a.temperature, max_tokens=a.max_tokens,
                          key=a.key, json_mode=not a.no_json_mode)
    elapsed = time.time() - t0
    script = normalize_script(parse_first_json(content), plan, a.host)
    script["songs"] = songs
    md = render_script_md(script, {"host": script.get("host"), "songs": songs,
                                   "minutes": minutes})
    g = gate_script(script, md, songs, minutes, song_seconds=a.song_seconds)
    (outdir / SCRIPT_JSON).write_text(json.dumps(
        {"script": script, "target_minutes": minutes, "songs": songs,
         "chars": script_chars(script), "model": a.model, "usage": usage,
         "state_key": key, "endpoint": "/api/v1/chat/completions",
         "plan_title": plan.get("title"), "gates": g},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / SCRIPT_MD).write_text(md + "\n", encoding="utf-8")
    state["script"] = {"key": key, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "songs": songs, "chars": script_chars(script)}
    save_state(outdir, state)
    result = {"stage": "script", "resumed": False, "state_key": key, "songs": songs,
              "minutes": minutes, "model": a.model,
              "endpoint": "/api/v1/chat/completions", "usage": usage,
              "elapsed": round(elapsed, 1), "chars": script_chars(script),
              "sections": section_breakdown(script), "script": script, "gates": g,
              "outdir": str(outdir),
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
        # 事故复盘：同族第一版按 `%-28s` 截断显示了，实测时照着屏幕抄了前 28 位，
        # 结果 tts 返回 `code=0 任务处理失败`——真正的 id 是 32 位十六进制。
        # 列表里唯一要"抄下来用"的字段被截断，是那一版最蠢的一个 bug。
        print("  %s" % (r["reference_id"] or "-"))
        print("      %-22s %-8s %s" % (str(r["title"])[:22],
                                       str(r["language"] or "-")[:8],
                                       str(r["tags"] or "")))
    print("")
    print("把 reference_id **整条**交给配音：--voice <ID>")
    print("不给就自动取第一个（脚本会在 stderr 说明取了哪个）。")
    print("id 是 32 位十六进制；抄短了会得到 code=0「任务处理失败」。")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：voice（串词配音）
# ---------------------------------------------------------------------------

def _run_voice(a):
    outdir = check_outdir(a.outdir)
    # 稿子只读一次；下面每一步都复用这份内存里的稿子。
    script, md, meta = _read_script(a)
    # 【成本前置放在这里，而不是等闸门跑完再报价】成本前的意思是
    # "**在发起任何付费动作之前**"，而闸门是本地计算、不花钱，
    # 所以顺序是「报价确认 → 闸门 → 真扣费」。第一版把报价放在闸门之后，
    # 于是"报价超 --budget"这条在稿子结构不合格时永远走不到，
    # 用户会先看到一条闸门判词，误以为预算没问题。
    # 报价用 `--sample-chars` 截断后的真实字数（不是全文），与随后真正配的字数一致。
    quotes = [quote_voice(
        sum(c["chars"] for c in draft_voice_chunks(script, sample_chars=a.sample_chars)),
        a.points_per_1k)]
    rc = _confirm_spend(a, quotes, "配音（%d 字）" % quotes[0]["chars"])
    if rc:
        return rc

    # 闸门六已过，接着过闸门一~五
    songs = int(meta.get("songs") or script.get("songs") or SHOW["default_songs"])
    minutes = (float(a.minutes) if getattr(a, "minutes", None)
               else (meta.get("target_minutes") or SHOW["default_minutes"]))
    # 闸门一~五。**报价已经在上面确认过了**，所以这里只判"稿子能不能录"：
    # 闸门没过就地中止，一次配音调用都不发（`spent_points: 0`）。
    g = gate_script(script, md, songs, minutes, song_seconds=a.song_seconds)
    if not g["ok"]:
        result = {"stage": "voice", "gates": g, "spent_points": 0,
                  "quoted_points": quotes[0]["points"],
                  "note": "闸门未通过，未发起任何配音调用，未扣费"}
        _emit(a, result, render_timeline_md([], 0, {"title": "配音中止：串词稿未过闸门"}),
              ok=False)
        return _gate_report(g, script.get("title") or "")

    chunks = draft_voice_chunks(script, sample_chars=a.sample_chars)
    if not chunks:
        raise UsageError("串词稿里没有可配音的正文（检查 sections 的 body）")
    total_chars = sum(c["chars"] for c in chunks)
    # 报价时按同一份 chunks 算过字数；这里只做一次一致性断言，
    # 避免"报价说 300 字、真配 600 字"这种最伤信任的偏差（实测口径 50 点/千字是线性的）。
    if total_chars != quotes[0]["chars"]:
        raise UsageError("内部不一致：报价字数 %d 与实际待配字数 %d 不符，已中止（未扣费）"
                         % (quotes[0]["chars"], total_chars))

    key = a7w.load_key(a.key)
    rid = a.voice
    if not rid:
        lst = list_voices(key, page_size=5)
        ids = [voice_id_of(x) for x in lst if voice_id_of(x)]
        if not ids:
            raise RadioError("取不到可用音色：用 `run.py voices` 看列表，"
                             "再 --voice <reference_id> 手动指定")
        rid = ids[0]
        sys.stderr.write("未指定音色，已自动取用：%s\n" % rid)

    vdir = outdir / "voice"
    vdir.mkdir(parents=True, exist_ok=True)
    state = load_state(outdir)
    st_voice = state.setdefault("voice", {})
    index, spent, skipped = [], 0.0, 0
    t_all = time.time()
    for ch in chunks:
        fname = "%s.mp3" % ch["file_stem"]
        fpath = vdir / fname
        # 【断点 key 含全部影响产出的维度】见 body_key 的注释。
        # 这里把**将要发出的那个 body** 整体入 key：正文、音色、语速、模型、格式
        # 全在里面。上一版同族把 `resolution` 漏在 key 外面，改了档位仍复用旧产物——
        # 这类错误是不可见的，所以在结构上避开它。
        req = {"app": APP_VOICE, "kind": "voice", "text": ch["text"],
               "model": a.tts_model, "format": "mp3",
               "reference_id": rid, "speed": a.speed}
        chash = body_key(req)
        prev = st_voice.get(ch["file_stem"])
        if prev and prev.get("hash") == chash and fpath.is_file() and not a.force:
            skipped += 1
            index.append({"file": str(fpath), "section": ch["section"],
                          "kind": ch["kind"], "order": ch["order"], "chars": ch["chars"],
                          "points": prev.get("points"), "resumed": True})
            sys.stderr.write("  [%d/%d] %s 已存在且请求未变，跳过（断点续跑，不重复扣费）\n"
                             % (ch["order"], len(chunks), fname))
            continue
        sys.stderr.write("  [%d/%d] %s ← %s（%d 字，端点 %s）\n"
                         % (ch["order"], len(chunks), fname, rid, ch["chars"], TTS_ENDPOINT))
        res = do_tts(key, ch["text"], reference_id=rid, fmt="mp3",
                     model=a.tts_model, speed=a.speed, timeout=a.timeout)
        pts = points_of(res)
        if pts is not None:
            spent += pts
        _report_spend("配音 %s" % fname, ch["chars"] / 1000.0 * TTS_POINTS_PER_1K_CHARS, pts)
        url = pick_url(res.get("result") if isinstance(res, dict) else res,
                       "audio_url", "url", "output_url", "file_url")
        if not url:
            raise RadioError("配音返回里没找到音频地址（片段 %s）：%s"
                             % (fname, json.dumps(res, ensure_ascii=False)[:400]))
        try:
            a7w.save(url, fpath)
        except (a7w.A7wError, OSError) as exc:
            raise RadioError("音频下载失败（片段 %s）：%s（地址：%s）" % (fname, exc, url))
        st_voice[ch["file_stem"]] = {"hash": chash, "chars": ch["chars"],
                                     "section": ch["section"], "role": "host",
                                     "file": str(fpath), "points": pts,
                                     "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_state(outdir, state)     # 每片都落盘：中断后重跑不重复扣费
        index.append({"file": str(fpath), "section": ch["section"], "kind": ch["kind"],
                      "order": ch["order"], "chars": ch["chars"], "points": pts,
                      "url": url})
        left = _budget_left(a, spent)
        if left is not None and left < 0:
            (vdir / VOICE_INDEX).write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
            result = {"stage": "voice", "spent_points": round(spent, 2),
                      "chars": total_chars, "segments": len(index),
                      "endpoint": TTS_ENDPOINT, "voice": rid,
                      "files": [i["file"] for i in index], "gates": g}
            _emit(a, result, "配音已花 %.2f 点，超过 --budget %s 点，就地中止"
                  % (spent, a.budget), ok=False)
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
              "quoted_points": quotes[0]["points"], "voice": rid,
              "measured_points_per_1k_chars": (round(per_1k, 2) if per_1k else None),
              "declared_points_per_1k_chars": TTS_POINTS_PER_1K_CHARS,
              "elapsed": round(elapsed, 1),
              "files": [i["file"] for i in index], "index": str(vdir / VOICE_INDEX),
              "gates": {"ok": True, "structure": g["structure"], "duration": g["duration"]}}
    md_out = "\n".join([
        "# 配音完成",
        "",
        "- 片段：%d 个（跳过 %d 个已完成的）" % (len(index), skipped),
        "- 字数：%d 字　端点：`POST %s`" % (total_chars, TTS_ENDPOINT),
        "- 音色：`%s`（32 位十六进制，抄短会得到 code=0「任务处理失败」）" % rid,
        "- 实际扣费：%s 点 ≈ %s 元" % (round(spent, 2), money(spent)),
        "- 实测单价：%s 点/千字（本包申报口径 %s 点/千字）"
        % (round(per_1k, 2) if per_1k else "-", TTS_POINTS_PER_1K_CHARS),
        "",
        "| # | 段落 | 字数 | 扣点 | 文件 |",
        "|---|---|---|---|---|",
    ] + ["| %(order)s | %(section)s | %(chars)s | %(points)s | `%(name)s` |" % {
        "order": i["order"], "section": i["section"], "chars": i["chars"],
        "points": i["points"], "name": Path(i["file"]).name} for i in index])
    _emit(a, result, md_out)
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：pick（选曲）
# ---------------------------------------------------------------------------

def _match_score(item, want_title, want_artist):
    """给一个搜索结果打分：歌名像不像、歌手像不像。"""
    t = _norm_for_echo(item.get("title") or "")
    a = _norm_for_echo(item.get("author") or item.get("artist") or "")
    wt = _norm_for_echo(want_title or "")
    wa = _norm_for_echo(want_artist or "")
    score = 0.0
    if wt and t:
        if wt == t:
            score += 0.6
        elif wt in t or t in wt:
            score += 0.4
        else:
            score += 0.6 * _similarity(t, wt)
    if wa and a:
        if wa in a or a in wa:
            score += 0.4
        else:
            score += 0.4 * _similarity(a, wa)
    elif not wa:
        score += 0.2
    return round(score, 3)


def _do_pick_search(a, key, plan, minutes):
    """music_search 路线：逐首搜索 + 打分挑选。**每次调用都扣点，所以先报价。**"""
    requests = plan.get("tracks") or []
    if not requests:
        raise UsageError("节目单里没有 tracks，无法选曲")
    per_song = max(1, int(getattr(a, "tries", None) or 1))
    total_calls = len(requests) * per_song
    rc = _confirm_spend(a, [quote_search(total_calls, a.points_per_search)],
                        "选曲搜索（**最多** %d 次调用 × %d 首；首轮命中就少花）"
                        % (per_song, len(requests)))
    if rc:
        return rc
    outdir = check_outdir(a.outdir)
    chosen, spent, calls = [], 0.0, 0
    for i, t in enumerate(requests, 1):
        want_t, want_a = t.get("title") or "", t.get("artist") or ""
        best, best_score = None, -1.0
        for attempt in range(per_song):
            kw = want_t if attempt == 0 else ("%s %s" % (want_t, want_a)).strip()
            sys.stderr.write("  [%d/%d] 搜索「%s」（POST %s，%s 点/次）\n"
                             % (i, len(requests), kw, SEARCH_ENDPOINT,
                                SEARCH_POINTS_PER_CALL))
            res = do_search(key, kw, page=1, page_size=a.page_size, timeout=a.timeout)
            calls += 1
            pts = points_of(res)
            if pts is not None:
                spent += pts
            _report_spend("搜索「%s」" % kw, SEARCH_POINTS_PER_CALL, pts)
            items = [x for x in search_items(res) if isinstance(x, dict)]
            for it in items:
                sc = _match_score(it, want_t, want_a)
                if sc > best_score:
                    best, best_score = it, sc
            if best_score >= 0.75:            # 够像了，不再多花一次钱
                break
            left = _budget_left(a, spent)
            if left is not None and left < 0:
                _emit(a, {"stage": "pick", "spent_points": round(spent, 2),
                          "songs": chosen, "endpoint": SEARCH_ENDPOINT}, "预算超限",
                      ok=False)
                return _fail(EXIT_BUDGET, "budget",
                             "选曲已花 %.2f 点超过 --budget %s 点（已完成 %d 首）"
                             % (spent, a.budget, len(chosen)))
        if best is None:
            sys.stderr.write("  [%d/%d] 「%s」没搜到任何结果，跳过（不占位）\n"
                             % (i, len(requests), want_t))
            continue
        chosen.append({"index": i, "source": "music_search",
                       "query": want_t, "match_score": best_score,
                       "title": best.get("title") or want_t,
                       "artist": best.get("author") or best.get("artist") or want_a,
                       "songid": best.get("songid"), "link": best.get("link"),
                       "pic": best.get("pic"), "url": best.get("url"),
                       "requested_title": want_t, "requested_artist": want_a,
                       # 打分低于 0.55 就是"只能凑合"，如实标出来让人工复核
                       "approx": best_score < 0.55})
    return _finish_pick(a, plan, minutes, chosen,
                        {"search_calls": calls, "spent_points": round(spent, 2)})


def _finish_pick(a, plan, minutes, chosen, extra):
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    playlist = []
    need_download = bool(getattr(a, "download", False))
    sdir = outdir / "songs"
    for it in chosen:
        seconds = 0
        for t in (plan.get("tracks") or []):
            if _norm_for_echo(t.get("title") or "") == _norm_for_echo(it.get("title") or ""):
                seconds = int(t.get("seconds") or 0)
                break
        if not seconds:
            seconds = int(SHOW["song_seconds_fallback"])
        fpath = None
        if need_download and it.get("url"):
            sdir.mkdir(parents=True, exist_ok=True)
            fpath = sdir / ("%03d-%s.mp3" % (it["index"], safe_name(it.get("title"))))
            if fpath.is_file() and fpath.stat().st_size > 0 and not a.force:
                sys.stderr.write("  %s 已存在，跳过下载\n" % fpath.name)
            else:
                sys.stderr.write("  下载 %s → %s\n" % (it.get("title"), fpath.name))
                try:
                    a7w.save(it["url"], fpath)
                except (a7w.A7wError, OSError) as exc:
                    sys.stderr.write("  下载失败（%s），这一首只留元信息：%s\n"
                                     % (it.get("title"), exc))
                    fpath = None
        playlist.append({
            "index": it["index"], "title": it.get("title") or "",
            "artist": it.get("artist") or "", "seconds": seconds,
            "source": it.get("source") or "music_search",
            "file": str(fpath) if fpath else None,
            "url": it.get("url"), "link": it.get("link"), "pic": it.get("pic"),
            "songid": it.get("songid"), "match_score": it.get("match_score"),
            "approx": it.get("approx", False),
            "requested_title": it.get("requested_title"),
            "requested_artist": it.get("requested_artist"),
        })
    if not playlist:
        raise RadioError("一首歌都没选出来：换关键词重试，或改用 --from-file 给歌单")
    missing = [t.get("requested_title") for t in playlist
               if not t.get("file") and need_download]
    approx = [p for p in playlist if p.get("approx")]
    (outdir / PLAYLIST_JSON).write_text(json.dumps(
        {"playlist": playlist, "songs": len(playlist), "target_minutes": minutes,
         "endpoint": SEARCH_ENDPOINT, "extra": extra},
        ensure_ascii=False, indent=1), encoding="utf-8")
    md = _render_playlist_md(playlist, minutes, extra)
    (outdir / PLAYLIST_TXT).write_text(md + "\n", encoding="utf-8")
    result = {"stage": "pick", "endpoint": SEARCH_ENDPOINT, "songs": len(playlist),
              "playlist": playlist, "missing_audio": missing,
              "approx_matches": [p["title"] for p in approx],
              "spent_points": extra.get("spent_points"),
              "search_calls": extra.get("search_calls"),
              "outdir": str(outdir),
              "files": {"json": str(outdir / PLAYLIST_JSON),
                        "txt": str(outdir / PLAYLIST_TXT)}}
    if missing:
        sys.stderr.write("\n提示：有 %d 首没下载到本地音频文件——mix 阶段会明确报缺，"
                         "不会静默跳过。可以加 --download 重跑，或手工放文件。\n" % len(missing))
    if approx:
        sys.stderr.write("\n提示：有 %d 首是**近似匹配**（打分 < 0.55），"
                         "请人工复核是否选对了：%s\n"
                         % (len(approx), "、".join(p["title"] for p in approx[:6])))
    _emit(a, result, md)
    return EXIT_OK


def _render_playlist_md(playlist, minutes, extra):
    out = ["# 选曲结果", ""]
    out.append("- 曲目：%d 首　目标时长：%s" % (len(playlist), fmt_minutes(minutes)))
    if extra.get("search_calls"):
        out.append("- 搜索调用：%d 次（实测 %s 点/次，实际扣费 %s 点）"
                   % (extra["search_calls"], SEARCH_POINTS_PER_CALL,
                      extra.get("spent_points")))
    out += ["", "| 序 | 曲目 | 歌手 | 匹配度 | 本地文件 | 试听/来源 |",
            "|---|---|---|---|---|---|"]
    for p in playlist:
        out.append("| %s | %s | %s | %s%s | %s | %s |" % (
            p["index"], p["title"], p["artist"],
            p.get("match_score") if p.get("match_score") is not None else "-",
            "（近似，请复核）" if p.get("approx") else "",
            Path(p["file"]).name if p.get("file") else "（缺）",
            p.get("link") or p.get("url") or "-"))
    out.append("")
    out.append("> 选曲来源：`POST %s`（同步接口，按次扣点）。" % SEARCH_ENDPOINT)
    out.append("> 搜索结果是**流媒体源上的曲目**，本包只负责挑与排；"
               "播出/商用请自行确认授权。")
    out.append("")
    return "\n".join(out)


def _run_pick_from_file(a, plan, minutes):
    rows = _read_playlist(a)
    outdir = check_outdir(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    sdir = outdir / "songs"
    base = Path(a.from_file).resolve().parent
    playlist = []
    for r in rows:
        seconds = 0
        for t in (plan.get("tracks") or []):
            if _norm_for_echo(t.get("title") or "") == _norm_for_echo(r["title"]):
                seconds = int(t.get("seconds") or 0)
                break
        if not seconds:
            seconds = int(SHOW["song_seconds_fallback"])
        # 顺手在歌单文件同目录找同名音频（`歌名.mp3` / `歌名 - 歌手.mp3`）
        fpath = None
        for cand in (sdir / ("%03d-%s.mp3" % (r["index"], safe_name(r["title"]))),
                     base / ("%s.mp3" % r["title"]),
                     base / ("%s - %s.mp3" % (r["title"], r["artist"])),
                     sdir / ("%s.mp3" % r["title"])):
            if cand.is_file() and cand.stat().st_size > 0:
                fpath = cand
                break
        playlist.append({"index": r["index"], "title": r["title"], "artist": r["artist"],
                         "seconds": seconds, "source": "from-file",
                         "file": str(fpath) if fpath else None,
                         "url": None, "link": None, "pic": None, "songid": None,
                         "match_score": None, "approx": False,
                         "requested_title": r["title"], "requested_artist": r["artist"]})
    (outdir / PLAYLIST_JSON).write_text(json.dumps(
        {"playlist": playlist, "songs": len(playlist), "target_minutes": minutes,
         "endpoint": "from-file", "source_file": str(Path(a.from_file).resolve())},
        ensure_ascii=False, indent=1), encoding="utf-8")
    md = _render_playlist_md(playlist, minutes, {"search_calls": 0, "spent_points": 0})
    md = md.replace("> 选曲来源：`POST %s`（同步接口，按次扣点）。" % SEARCH_ENDPOINT,
                    "> 选曲来源：本地歌单文件 `%s`（**离线，不花钱**）。"
                    % Path(a.from_file).name)
    (outdir / PLAYLIST_TXT).write_text(md + "\n", encoding="utf-8")
    found = [p for p in playlist if p.get("file")]
    result = {"stage": "pick", "endpoint": "from-file", "songs": len(playlist),
              "spent_points": 0, "search_calls": 0, "playlist": playlist,
              "local_audio_found": [p["title"] for p in found],
              "missing_audio": [p["title"] for p in playlist if not p.get("file")],
              "outdir": str(outdir),
              "files": {"json": str(outdir / PLAYLIST_JSON),
                        "txt": str(outdir / PLAYLIST_TXT)}}
    if result["missing_audio"]:
        sys.stderr.write("\n提示：%d 首在本地没找到音频文件（会按曲长估算进时长台账，"
                         "但 mix 阶段需要一个真实文件才拼得进去）。\n"
                         % len(result["missing_audio"]))
    _emit(a, result, md)
    return EXIT_OK


def _run_pick(a):
    plan = _read_plan(a)
    minutes = _target_minutes(a, plan)
    if getattr(a, "from_file", None):
        return _run_pick_from_file(a, plan, minutes)
    if getattr(a, "offline", False):
        raise UsageError("--offline 需要配合 --from-file（离线路线不搜在线曲库）")
    key = a7w.load_key(a.key)
    return _do_pick_search(a, key, plan, minutes)


# ---------------------------------------------------------------------------
# 子命令：music（垫乐）
#
# 【为什么单独有这个子命令，而不是让 mix 顺手生成】
# `music_generation/create` 是**异步 + 65 点/次**的付费调用，而 mix 是零成本的本地步骤。
# 把付费调用塞进一个零成本步骤里，等于让"我只是想重新拼一次"变成"又花了 65 点"。
# 付费的归付费，本地的归本地——这是本包的取舍，写在 SKILL.md 的已知取舍里。
# ---------------------------------------------------------------------------

MUSIC_CUES = {
    "bed": {
        "label": "垫乐",
        "seconds": 30,
        "style": "舒缓的纯器乐电台垫乐，无人声，中低频饱满，音量适合压在口播之下",
        "prompt": "一段用于电台节目人声垫底的纯器乐循环，情绪平稳不抢话，无人声，尾音自然衰减",
    },
}


def _run_music(a):
    outdir = check_outdir(a.outdir)
    spec = MUSIC_CUES["bed"]
    style = a.style or spec["style"]
    prompt = a.prompt or spec["prompt"]
    title = a.title or "电台垫乐"
    mdir = outdir / "music"
    mdir.mkdir(parents=True, exist_ok=True)
    fpath = mdir / ("%s.mp3" % a.cue)
    # 【断点 key】把将要发出的 body 整体入 key：风格、提示词、标题、纯器乐、歌词开关。
    # 改了风格却复用旧垫乐 = 静默复用旧产物（同族踩过 `resolution` 不入 key 的坑）。
    req = {"app": APP_MUSIC, "api": "create", "type": "generate", "title": title,
           "style": style, "prompt": prompt, "with_lyrics": bool(a.with_lyrics)}
    sig = body_key(req)
    state = load_state(outdir)
    st_music = state.setdefault("music", {})
    prev = st_music.get(a.cue)
    # 【断点判断放在报价之前】同族实测踩过这个顺序问题：先报价再判断点，
    # 会让"其实不用花钱"的重跑也弹一次报价、要求 --yes —— 用户会以为又要花 65 点。
    # 报价只应该出现在**真的打算花钱**的那条路上。
    if prev and prev.get("hash") == sig and fpath.is_file() and not a.force:
        sys.stderr.write("  [%s] 已存在且请求未变，跳过（断点续跑，不重复扣费）\n" % a.cue)
        result = {"stage": "music", "endpoint": MUSIC_ENDPOINT, "resumed": True,
                  "cue": a.cue, "file": str(fpath), "points": prev.get("points"),
                  "spent_points": 0, "quoted_points": 0, "state_key": sig}
        _emit(a, result, "# 配乐（断点续跑，未扣费）\n\n- 文件：`%s`\n" % fpath)
        return EXIT_OK
    creates = 1
    quotes = [quote_music(creates, with_lyrics=a.with_lyrics)]
    rc = _confirm_spend(a, quotes, "配乐（%d 次 create）" % creates)
    if rc:
        return rc
    key = a7w.load_key(a.key)
    spent = 0.0
    lyric = None
    if a.with_lyrics:
        sys.stderr.write("  [%s] 先生成歌词（POST %s，%s 点）\n"
                         % (a.cue, LYRICS_ENDPOINT, MUSIC_POINTS_PER_LYRICS))
        lres = do_lyrics(key, "%s；风格：%s" % (prompt, style))
        pts_l = points_of(lres)
        if pts_l is not None:
            spent += pts_l
        _report_spend("歌词 %s" % a.cue, MUSIC_POINTS_PER_LYRICS, pts_l)
        lyric = (lres.get("result") if isinstance(lres, dict) else None)
        if isinstance(lyric, dict):
            lyric = lyric.get("lyric") or lyric.get("text")
        lyric = str(lyric or "") or None
    sys.stderr.write("  [%s] 生成垫乐（POST %s，%s 点）\n"
                     % (a.cue, MUSIC_ENDPOINT, MUSIC_POINTS_PER_CREATE))
    res = do_music(key, style=style, prompt=prompt, title=title, lyric=lyric,
                   instrumental=not (a.with_lyrics and lyric), timeout=a.timeout)
    pts = points_of(res)
    if pts is not None:
        spent += pts
    _report_spend("垫乐 %s" % a.cue, MUSIC_POINTS_PER_CREATE, pts)
    url = pick_url(res.get("result") if isinstance(res, dict) else res,
                   "audio_url", "url", "output_url", "file_url", "music_url")
    if not url:
        raise RadioError("配乐返回里没找到音频地址（%s）：%s"
                         % (a.cue, json.dumps(res, ensure_ascii=False)[:400]))
    try:
        a7w.save(url, fpath)
    except (a7w.A7wError, OSError) as exc:
        raise RadioError("垫乐下载失败（%s）：%s（地址：%s）" % (a.cue, exc, url))
    st_music[a.cue] = {"hash": sig, "file": str(fpath), "points": pts, "style": style,
                       "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_state(outdir, state)
    if a.budget is not None and spent > a.budget:
        result = {"stage": "music", "spent_points": round(spent, 2), "cue": a.cue,
                  "endpoint": MUSIC_ENDPOINT}
        _emit(a, result, "垫乐已花 %.2f 点，超过 --budget %s 点" % (spent, a.budget),
              ok=False)
        return _fail(EXIT_BUDGET, "budget",
                     "垫乐已花 %.2f 点超过 --budget %s 点" % (spent, a.budget))
    result = {"stage": "music", "endpoint": MUSIC_ENDPOINT, "resumed": False,
              "cue": a.cue, "file": str(fpath), "size_bytes": fpath.stat().st_size,
              "spent_points": round(spent, 2), "spent_yuan": money(spent),
              "quoted_points": quotes[0]["points"],
              "measured_points_per_create": (round(spent, 2) if not a.with_lyrics else None),
              "declared_points_per_create": MUSIC_POINTS_PER_CREATE,
              "with_lyrics": bool(a.with_lyrics), "state_key": sig, "url": url,
              "note": "create 接口的参数表里**没有时长参数**；垫乐多长由上游决定，"
                      "mix 阶段用 ffmpeg 循环/裁剪到需要的位置"}
    md_out = "\n".join([
        "# 配乐完成", "",
        "- 档位：%s　端点：`POST %s`" % (a.cue, MUSIC_ENDPOINT),
        "- 文件：`%s`（%d 字节）" % (fpath, fpath.stat().st_size),
        "- 实际扣费：%s 点 ≈ %s 元" % (round(spent, 2), money(spent)),
        "- 本包申报口径：create %s 点/次%s" % (
            MUSIC_POINTS_PER_CREATE,
            "，歌词 %s 点/次" % MUSIC_POINTS_PER_LYRICS if a.with_lyrics else ""),
        "",
        "- 断点 key（含风格/提示词/标题/纯器乐开关）：`%s`" % sig,
    ]) + "\n"
    _emit(a, result, md_out)
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：mix（串词 + 歌曲拼接 + 节目单 / 时间轴）
#
# 【为什么时长从 wav 文件头算、而不是 ffprobe】
# 同族实测环境里只有 ffmpeg、没有 ffprobe（ffprobe 是另一个可执行文件）。
# 所以混合分两步：先把每段解码成参数完全一致的 wav（mono / 44100 / 16bit），
# 这样 wav 时长 = data 块字节数 ÷ (采样率 × 声道 × 位宽/8)，**是精确值不是估算**；
# 再用 concat 解复用器拼起来编成 mp3。时间轴就按这些精确时长累加。
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


def load_playlist(outdir):
    p = Path(outdir) / PLAYLIST_JSON
    if not p.is_file():
        return []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return obj.get("playlist") or []


def load_voice_index(outdir):
    p = Path(outdir) / "voice" / VOICE_INDEX
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    vdir = Path(outdir) / "voice"
    if not vdir.is_dir():
        return []
    return [{"file": str(x), "order": i, "section": None, "kind": None}
            for i, x in enumerate(sorted(vdir.glob("*.mp3")), 1)]


def _sec_index(section):
    """从「过渡 i」这样的段落名里取出 i；取不到给一个很大的数（排到最后）。"""
    m = re.search(r"(\d+)", str(section or ""))
    return int(m.group(1)) if m else 10 ** 6


def build_program(outdir, plan, script, playlist, bed=None):
    """排出节目顺序：开场 → (过渡1 → 歌1) → (过渡2 → 歌2) → … → 结尾。

    返回 (items, missing)：items 每项 {kind, label, path, chapter}，按播出顺序。
    kind ∈ voice / song / bed。

    **歌曲数必须等于过渡条数**——这是本包的形态约定，不是巧合：
    每条过渡就是"这首歌之前要说的那句话"。数量不等时这里**明确报缺**，
    而不是挑几首拼上去让成片看起来完整。
    """
    items, missing = [], []
    voice = load_voice_index(outdir)
    by_kind = {}
    for v in voice:
        by_kind.setdefault(v.get("kind") or "open", []).append(v)
    open_seg = (by_kind.get("open") or [None])[0]
    close_seg = (by_kind.get("close") or [None])[0]
    # 【过渡段按**声明编号排序后重编 1..N**，再按位置绑到曲目上】不按编号查表是因为
    # 手工改过的稿子会出现「过渡 2..5」这种编号（内容是全的，只是编号写法不同）；
    # 而过渡的语义就是"第 i 首歌之前那条"，**位置才是它的定义**。
    # 条数与曲目数不等的检查仍然在（那是真的缺内容）。
    trans = sorted((by_kind.get("trans") or []),
                   key=lambda x: (_sec_index(x.get("section")), x.get("order") or 0))
    trans_by_pos = {i: t for i, t in enumerate(trans, 1)}
    if open_seg and Path(open_seg["file"]).is_file():
        items.append({"kind": "voice", "label": "开场", "path": Path(open_seg["file"]),
                      "chapter": 0, "chapter_title": "开场"})
    else:
        missing.append("开场配音（跑 `voice` 生成）")

    if bed:
        items.append({"kind": "bed", "label": "垫乐前段", "path": Path(bed),
                      "chapter": None, "chapter_title": None, "bed": True})

    for i, t in enumerate(playlist, 1):
        tr = trans_by_pos.get(i)
        if tr and Path(tr["file"]).is_file():
            items.append({"kind": "voice", "label": "过渡 %d" % i,
                          "path": Path(tr["file"]), "chapter": i, "chapter_title": None})
        else:
            missing.append("第 %d 首之前的过渡配音（【过渡 %d】段）" % (i, i))
        f = t.get("file")
        if f and Path(f).is_file():
            items.append({"kind": "song", "label": "第 %d 首《%s》- %s" % (
                i, t.get("title") or "", t.get("artist") or ""),
                "path": Path(f), "chapter": i,
                "chapter_title": t.get("title") or ""})
        else:
            missing.append("第 %d 首《%s》的音频文件（%s）"
                           % (i, t.get("title") or "", t.get("source") or "未知来源"))
    if close_seg and Path(close_seg["file"]).is_file():
        items.append({"kind": "voice", "label": "结尾", "path": Path(close_seg["file"]),
                      "chapter": 99, "chapter_title": "结尾"})
    else:
        missing.append("结尾配音（跑 `voice` 生成）")
    return items, missing


def chapter_marks(rows):
    """把逐段的行聚合成**每首歌一条**的章节标记。

    输入 rows：每项 {start, end, label, kind, chapter, chapter_title}，按播出顺序。
    输出：{start, end, title, chapter} 列表——过渡人声归到它所对应的那首歌那一条。
    """
    marks = []
    for r in rows:
        if r.get("kind") == "song":
            marks.append({"chapter": r.get("chapter"), "title": r.get("label") or "",
                          "start": r["start"], "end": r["end"]})
            continue
        if r.get("kind") == "voice" and r.get("chapter") in (0, 99):
            if marks and marks[-1].get("chapter") == r.get("chapter"):
                marks[-1]["end"] = r["end"]
                continue
            marks.append({"chapter": r.get("chapter"),
                          "title": ("开场" if r.get("chapter") == 0 else "结尾"),
                          "start": r["start"], "end": r["end"]})
    return marks


def _run_ffmpeg(ffmpeg, args, timeout=1800):
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"] + args
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout)
    except OSError as exc:
        raise RadioError("调用 ffmpeg 失败：%s" % exc)
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-4:]
        raise RadioError("ffmpeg 返回 %d：%s" % (proc.returncode, " | ".join(tail)))
    return proc


def _run_mix(a):
    outdir = check_outdir(a.outdir)
    plan = {}
    try:
        plan = _read_plan(_ns(outdir=str(outdir), plan=None))
    except UsageError:
        plan = {"title": Path(outdir).name, "host": SHOW["host"]}
    playlist = load_playlist(outdir)
    if not playlist:
        raise UsageError("在 %s 里没找到选曲结果 playlist.json（先跑 `pick`，"
                         "或 --from-file 给歌单）" % outdir)
    try:
        script, _md, _meta = _read_script(
            _ns(outdir=str(outdir), script=None), songs=len(playlist))
    except UsageError:
        script = {"sections": [], "title": plan.get("title"), "host": plan.get("host")}

    bp = Path(outdir) / "music" / ("%s.mp3" % a.cue)
    bed = bp if (bp.is_file() and a.bed_seconds) else None
    items, missing = build_program(outdir, plan, script, playlist, bed=bed)
    for p in [i["path"] for i in items]:
        if not Path(p).is_file():
            raise UsageError("找不到音频片段：%s" % p)
    ffmpeg = find_ffmpeg(getattr(a, "ffmpeg", None))
    outfile = refuse_audio_in_pkg(a.filename or (outdir / "program.mp3"))

    if not ffmpeg:
        # 降级：把能产的东西全产出来（都是文本），然后**明确报错退出**，不假装成功。
        text_files = write_mix_texts(outdir, items, missing, playlist, script, plan)
        sys.stderr.write(_red(
            "\n!! 本机没有 ffmpeg，mix 降级：\n"
            "   已写出节目单 / 拼接清单 / 时间轴骨架（%s），**没有产出 mp3**。\n"
            "   装上 ffmpeg 后重跑同一条命令即可（断点续跑，不会重复扣配音/选曲的钱）。\n"
            "   ffmpeg 可以不在 PATH 上，用 --ffmpeg <路径> 或环境变量 FFMPEG 指定。\n"
            % "、".join(Path(p).name for p in text_files)) + "\n")
        result = {"stage": "mix", "degraded": True, "reason": "本机没有 ffmpeg",
                  "ffmpeg": None, "episode": None,
                  "playlist": [{"kind": i["kind"], "label": i["label"],
                                "file": str(i["path"])} for i in items],
                  "missing": missing, "text_outputs": [str(p) for p in text_files]}
        _emit(a, result, render_timeline_md([], 0, {"title": "（未产出 mp3：缺 ffmpeg）"}),
              ok=False)
        return _fail(EXIT_USAGE, "usage",
                     "本机没有 ffmpeg，mix 只写出节目单与拼接清单、没有 mp3"
                     "（装上 ffmpeg 后重跑）")

    work = outdir / ".mix"
    work.mkdir(parents=True, exist_ok=True)
    wavs = []
    sys.stderr.write("正在归一化 %d 段音频（mono / 44100 / 16bit）…\n" % len(items))
    for i, it in enumerate(items, 1):
        wav = work / ("%03d.wav" % i)
        if it.get("bed") and a.bed_seconds:
            # 垫乐：循环到目标长度并压低音量，再与后面的内容接起来
            args = ["-stream_loop", "-1", "-i", str(it["path"]),
                    "-t", str(a.bed_seconds), "-filter:a", "volume=%.2f" % a.bed_volume]
        else:
            args = ["-i", str(it["path"])]
        args += ["-ac", "1", "-ar", "44100", "-acodec", "pcm_s16le", str(wav)]
        _run_ffmpeg(ffmpeg, args)
        dur = wav_seconds(wav)
        if dur is None:
            raise RadioError("读不出片段时长（文件头异常）：%s" % wav)
        wavs.append({"item": it, "wav": wav, "seconds": dur})

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

    # 章节标记按**首**聚合：过渡人声归到它对应那首歌那一条，播放器里才是"一首一条"。
    marks = chapter_marks(rows)
    chapters_txt = work / "chapters.txt"
    lines = [";FFMETADATA1"]
    for mk in marks:
        lines += ["[CHAPTER]", "TIMEBASE=1/1000",
                  "START=%d" % int(round(mk["start"] * 1000)),
                  "END=%d" % int(round(mk["end"] * 1000)),
                  "title=%s" % str(mk["title"]).replace("\n", " ")]
    chapters_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sys.stderr.write("正在拼接并编码 mp3…\n")
    _run_ffmpeg(ffmpeg, ["-f", "concat", "-safe", "0", "-i", str(listfile),
                         "-i", str(chapters_txt), "-map_metadata", "1",
                         "-c:a", "libmp3lame", "-b:a", "128k",
                         "-id3v2_version", "3", str(outfile)], timeout=3600)
    if not outfile.is_file() or outfile.stat().st_size <= 0:
        raise RadioError("ffmpeg 没报错但没有产出 mp3：%s" % outfile)

    (outdir / "chapters.json").write_text(json.dumps(
        {"total_seconds": round(cursor, 2),
         "chapters": [{"start": round(m["start"], 2), "end": round(m["end"], 2),
                       "label": m["title"], "chapter": m["chapter"]} for m in marks],
         "tracks": [{"start": round(r["start"], 2), "end": round(r["end"], 2),
                     "label": r["label"], "kind": r["kind"]} for r in rows]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / "chapters.txt").write_text(chapters_txt.read_text(encoding="utf-8"),
                                         encoding="utf-8")
    timeline = render_timeline_md(rows, cursor,
                                  {"title": plan.get("title") or Path(outdir).name})
    (outdir / "timeline.md").write_text(timeline + "\n", encoding="utf-8")
    (outdir / "program-list.txt").write_text(
        render_program_list(playlist, script, plan, outdir), encoding="utf-8")
    (outdir / "playlist.txt").write_text(
        "".join("%s\t%s\t%s\n" % (fmt_mmss(r["start"]), r["kind"], r["label"])
                for r in rows), encoding="utf-8")

    result = {"stage": "mix", "degraded": False, "ffmpeg": ffmpeg,
              "episode": str(outfile), "size_bytes": outfile.stat().st_size,
              "total_seconds": round(cursor, 2), "total_mmss": fmt_mmss(cursor),
              "items": len(items), "missing": missing, "bed": str(bed) if bed else None,
              "chapters": [{"start": fmt_mmss(m["start"]), "end": fmt_mmss(m["end"]),
                            "title": m["title"]} for m in marks],
              "chapters_file": str(outdir / "chapters.txt"),
              "chapters_json": str(outdir / "chapters.json"),
              "timeline": str(outdir / "timeline.md"),
              "program_list": str(outdir / "program-list.txt"),
              "playlist": str(outdir / "playlist.txt"),
              "timeline_rows": [{"start": fmt_mmss(r["start"]), "end": fmt_mmss(r["end"]),
                                 "label": r["label"], "kind": r["kind"]} for r in rows]}
    _emit(a, result, timeline)
    if missing:
        sys.stderr.write("\n提示：缺 %s——已跳过，成片没有这一段。\n" % "；".join(missing))
    return EXIT_OK


def write_mix_texts(outdir, items, missing, playlist, script, plan):
    """没 ffmpeg 时的降级产出：节目单 + 拼接清单 + 时间轴骨架（都是文本）。"""
    out = []
    p = Path(outdir) / "playlist.txt"
    p.write_text("".join("%02d\t%s\t%s\n" % (i, it["kind"], it["label"])
                         for i, it in enumerate(items, 1)), encoding="utf-8")
    out.append(p)
    q = Path(outdir) / "chapters.txt"
    q.write_text("\n".join([";FFMETADATA1 （本机无 ffmpeg，未产出 mp3；"
                            "这是按节目顺序预估的章节骨架，装上 ffmpeg 后重跑 mix 会重算）"]
                           + ["[CHAPTER]", "TIMEBASE=1/1000", "START=?", "END=?"]
                           + ["title=%s" % it["label"] for it in items
                              if it["kind"] == "song"]) + "\n", encoding="utf-8")
    out.append(q)
    r = Path(outdir) / "program-list.txt"
    r.write_text(render_program_list(playlist, script, plan, Path(outdir)),
                 encoding="utf-8")
    out.append(r)
    s = Path(outdir) / "mix-commands.txt"
    s.write_text("把下面这条粘到有 ffmpeg 的机器上即可得到 program.mp3：\n\n"
                 "ffmpeg -f concat -safe 0 -i .mix/concat.txt -i .mix/chapters.txt "
                 "-map_metadata 1 -c:a libmp3lame -b:a 128k program.mp3\n",
                 encoding="utf-8")
    out.append(s)
    if missing:
        t = Path(outdir) / "missing.txt"
        t.write_text("\n".join(missing) + "\n", encoding="utf-8")
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# 子命令：cost（只算钱，一次调用都不发）
# ---------------------------------------------------------------------------

def estimate_total(minutes, songs, searches=0, creates=0, with_lyrics=False,
                   points_per_1k=None, points_per_search=None,
                   points_per_ktok=None):
    # 【字数口径与提示词、时长台账**同一个来源**】见 target_speech_min。
    # 三处各算一遍是这类包最容易出的错：报价说 500 字、提示词让写 1900 字、
    # 闸门按区间判——三个数不一致时，用户永远不知道该信哪个。
    song_total_min = (songs * SHOW["song_seconds_fallback"]) / 60.0
    chars = target_speech_chars(minutes, songs)
    speech_min = chars / cpm() if cpm() else 0.0
    qv = quote_voice(chars, points_per_1k)
    qs = quote_search(searches, points_per_search)
    qm = quote_music(creates, with_lyrics=with_lyrics)
    total = qv["points"] + qs["points"] + qm["points"]
    text_est = None
    if points_per_ktok:
        # 文本大模型的单价平台不公开（models 列表里没有任何价格字段、
        # pricing 表也不覆盖 chat/completions），所以**不给单价就不报金额**，绝不编。
        # token 粗估：中文约 1 字 ≈ 0.7 token，输出按目标字数的 1.2 倍留余量。
        tok_in = int(chars * 0.7 * 1.5)
        tok_out = int(chars * 0.7 * 1.2)
        pts = (tok_in + tok_out) / 1000.0 * float(points_per_ktok)
        text_est = {"assumed_prompt_tokens": tok_in, "assumed_completion_tokens": tok_out,
                    "points_per_ktok": float(points_per_ktok),
                    "points": round(pts, 2), "yuan": round(pts / POINTS_PER_YUAN, 4),
                    "note": "token 是粗估；文本单价由 --points-per-ktok 给出，不是平台值"}
        total += pts
    return {"minutes": minutes, "songs": songs, "chars": chars,
            "chars_per_minute": cpm(),
            "song_seconds_assumed": SHOW["song_seconds_fallback"],
            "song_total_seconds": round(songs * SHOW["song_seconds_fallback"], 1),
            "speech_minutes": round(speech_min, 1),
            "voice": qv, "search": qs, "music": qm, "text": text_est,
            "total_points": round(total, 2),
            "total_yuan": round(total / POINTS_PER_YUAN, 4),
            "points_per_yuan": POINTS_PER_YUAN}


def _run_cost(a):
    minutes = float(a.minutes or SHOW["default_minutes"])
    # 歌曲数的默认值同样按目标时长反推（与 plan 一致，两边默认值不能打架）
    songs = int(a.songs or suggest_songs(minutes))
    if a.from_file:
        songs = len(_read_playlist(a)) or songs
    feasible, why = show_feasible(minutes, songs)
    searches = int(a.searches if a.searches is not None else 0)
    creates = int(a.creates if a.creates is not None else 0)
    rec = estimate_total(minutes, songs, searches=searches, creates=creates,
                         with_lyrics=a.with_lyrics, points_per_1k=a.points_per_1k,
                         points_per_search=a.points_per_search,
                         points_per_ktok=a.points_per_ktok)
    result = dict(rec)
    result.update({
        "endpoints": {"tts": TTS_ENDPOINT, "search": SEARCH_ENDPOINT,
                      "music": MUSIC_ENDPOINT, "lyrics": LYRICS_ENDPOINT,
                      "chat": "/api/v1/chat/completions", "tasks": "/api/v1/tasks/"},
        "units": {"tts_points_per_1k_chars": TTS_POINTS_PER_1K_CHARS,
                  "search_points_per_call": SEARCH_POINTS_PER_CALL,
                  "music_points_per_create": MUSIC_POINTS_PER_CREATE,
                  "music_points_per_lyrics": MUSIC_POINTS_PER_LYRICS},
        "note": "配音 / 选曲 / 配乐单价是本包真机实测值；文本大模型单价平台不公开，"
                "给了 --points-per-ktok 才算金额。结算以 usage.points_cost 为准。",
        "songs_suggested": suggest_songs(minutes),
        "spec_feasible": feasible,
        "spec_note": why,
    })
    rc = EXIT_OK
    if a.budget is not None and rec["total_points"] > a.budget:
        rc = _fail(EXIT_BUDGET, "budget",
                   "预估 %s 点超过 --budget %s 点" % (rec["total_points"], a.budget))
    lines = [
        "# 成本测算（本地计算，未发起任何调用）", "",
        "- 目标时长：%s　歌曲 %d 首（按 %.0f 秒/首**假设**）"
        % (fmt_minutes(minutes), songs, SHOW["song_seconds_fallback"]),
        "- 拆解：歌曲约占 %.1f 分钟，串词约占 %.1f 分钟 → 串词约 %d 字（%d 字/分钟）"
        % (rec["song_total_seconds"] / 60.0, rec["speech_minutes"],
           rec["chars"], cpm()),
        "- 规格自检：**%s**（%s）" % ("装得下" if feasible else "装不下", why),
        "- 这一档时长的推荐曲目数：**%d 首**" % suggest_songs(minutes),
        "- 换算口径：1 元 = %d 点" % int(POINTS_PER_YUAN), "",
        "| 项目 | 单价 | 数量 | 点数 | 金额 |", "|---|---|---|---|---|",
        "| 串词配音 `voice_tts/tts` | %s 点/千字 | %d 字 | %s | %s 元 |"
        % (TTS_POINTS_PER_1K_CHARS, rec["chars"], rec["voice"]["points"],
           rec["voice"]["yuan"]),
        "| 选曲 `music_search/search` | %s 点/次 | %d 次 | %s | %s 元 |"
        % (SEARCH_POINTS_PER_CALL, searches, rec["search"]["points"],
           rec["search"]["yuan"]),
        "| 配乐 `music_generation/create` | %s 点/次 | %d 次 | %s | %s 元 |"
        % (MUSIC_POINTS_PER_CREATE, creates,
           creates * MUSIC_POINTS_PER_CREATE, money(creates * MUSIC_POINTS_PER_CREATE)),
    ]
    if a.with_lyrics:
        lines.append("| 歌词 `music_generation/lyrics` | %s 点/次 | %d 次 | %s | — |"
                     % (MUSIC_POINTS_PER_LYRICS, creates,
                        creates * MUSIC_POINTS_PER_LYRICS))
    if rec["text"]:
        lines.append("| 文本大模型（估算） | %s 点/千 token | ~%d+%d token | %s | %s 元 |"
                     % (rec["text"]["points_per_ktok"],
                        rec["text"]["assumed_prompt_tokens"],
                        rec["text"]["assumed_completion_tokens"],
                        rec["text"]["points"], rec["text"]["yuan"]))
    else:
        lines.append("| 文本大模型 | 平台未公开 | — | 未计 | 未计"
                     "（给 --points-per-ktok 才计） |")
    lines += ["| **合计** | | | **%s** | **%s 元** |"
              % (rec["total_points"], rec["total_yuan"]),
              "",
              "端点：`POST %s` · `POST %s` · `POST %s` · `/api/v1/chat/completions`"
              " · `/api/v1/tasks/`" % (TTS_ENDPOINT, SEARCH_ENDPOINT, MUSIC_ENDPOINT),
              "",
              "> 配音 / 选曲 / 配乐单价是本包真机实测值；文本大模型的单价平台不公开，"
              "本包**不编价**。实际结算以 `usage.points_cost` 为准。",
              "> 曲长按 %.0f 秒/首**假设**——拿到本地音频文件后以真实时长为准。"
              % SHOW["song_seconds_fallback"]]
    if a.budget is not None:
        lines.append("> 预算 %g 点：%s"
                     % (a.budget, "超了，付费步骤会被拦下"
                        if rec["total_points"] > a.budget else "在预算内"))
    _emit(a, result, "\n".join(lines), ok=not rc)
    return rc


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
    # 顺手把本包用到的三个 app 的**真实接口名**拉出来现查一遍，
    # 这样"接口名对不对"不用靠记忆（本包就是靠这一步确认 music_search 存在的）。
    apps = {}
    try:
        ap = a7w._unwrap(a7w._request("GET", APP_URL, key, timeout=60))
        seq = ap.get("data") if isinstance(ap, dict) and "data" in ap else ap
        if isinstance(seq, dict):
            seq = seq.get("list") or seq.get("apps") or []
        for x in (seq or []):
            if isinstance(x, dict):
                apps[x.get("code")] = {
                    "name": x.get("name"),
                    "apis": [{"code": y.get("code"), "name": y.get("name"),
                              "call_type": y.get("call_type"),
                              "endpoint": "POST /api/v1/apps/%s/%s"
                                          % (x.get("code"), y.get("code"))}
                             for y in (x.get("apis") or []) if isinstance(y, dict)],
                }
    except a7w.A7wError as exc:
        sys.stderr.write("拉应用清单失败：%s\n" % exc)
    if a.json:
        _json_out({"endpoint": MODELS_URL, "count": len(lst), "data": lst,
                   "apps": apps}, a, indent=1)
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
    for app in (APP_VOICE, APP_SEARCH, APP_MUSIC):
        info = apps.get(app)
        print("")
        if not info:
            print("本包用到 %s：**当前 /api/v1/apps 里没有这个 app**，请现查确认" % app)
            continue
        print("本包用到 %s（%s）的真实接口：" % (app, info.get("name")))
        for x in info["apis"]:
            print("  %-16s %-18s %s" % (x["code"], x["name"], x["endpoint"]))
    print("")
    print("  ⚠️ 选曲走 `%s`，它**按次扣点**（实测 %s 点/次），"
          "不是免费接口。" % (SEARCH_ENDPOINT, SEARCH_POINTS_PER_CALL))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 子命令：all（整条链路，断点续跑）
# ---------------------------------------------------------------------------

def _run_all(a):
    """整条链路的**外层包装**：把子步骤的产出收起来，最后合并成一份输出。

    为什么要包装：`all` 复用 `_run_plan` / `_run_script` / `_run_pick` /
    `_run_voice` / `_run_music` / `_run_mix`，每个都会 `_emit` 一次。不收起来的话
    `all --json` 会吐好几个 JSON 文档，调用方 `json.loads` 直接失败（同族实测踩过）。
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
    steps_n = 5 if a.skip_music else 6

    # [1/6] 节目单
    p_json = outdir / PLAN_JSON
    if p_json.is_file() and not a.force and not a.topic_override:
        sys.stderr.write("[1/%d] 节目单已存在，跳过（断点续跑，不重复扣费）：%s\n"
                         % (steps_n, p_json))
    else:
        if not (a.topic or "").strip() and not a.from_file:
            # 没有节目单也没有主题 = 无从下手。在这里拦住，别让 "主题：None" 发到模型那边。
            raise UsageError("还没有节目单文件，请给 --topic \"主题\"（或用 --from-file 给歌单）；"
                             "已有节目单时可以不重复给（会走断点续跑）")
        sys.stderr.write("[1/%d] 出节目单…\n" % steps_n)
        rc = _run_plan(_plan_args(a, outdir, minutes))
        if rc:
            return rc
    if a.dry_run:
        sys.stderr.write("\n--dry-run 结束：没有调用任何接口，没有写任何文件。\n")
        return EXIT_OK
    plan = _read_plan(_ns(outdir=str(outdir), plan=None))
    minutes = _target_minutes(a, plan)

    # [2/6] 串词
    s_json = outdir / SCRIPT_JSON
    if s_json.is_file() and not a.force:
        sys.stderr.write("[2/%d] 串词已存在，跳过（断点续跑）：%s\n" % (steps_n, s_json))
    else:
        sys.stderr.write("[2/%d] 写串词…\n" % steps_n)
        rc = _run_script(_script_args(a, outdir, plan))
        if rc:
            return rc

    # [3/6] 选曲
    pl_json = outdir / PLAYLIST_JSON
    if pl_json.is_file() and not a.force:
        sys.stderr.write("[3/%d] 选曲已存在，跳过（断点续跑）：%s\n" % (steps_n, pl_json))
    else:
        sys.stderr.write("[3/%d] 选曲…\n" % steps_n)
        rc = _run_pick(_pick_args(a, outdir))
        if rc:
            return rc

    # [4/6] 配音（先闸门后报价，见 _run_voice）
    sys.stderr.write("[4/%d] 串词配音…\n" % steps_n)
    rc = _run_voice(_voice_args(a, outdir, minutes))
    if rc:
        return rc

    # [5/6] 垫乐（可选）
    if a.skip_music:
        sys.stderr.write("[5/%d] 按 --skip-music 跳过垫乐\n" % steps_n)
    else:
        sys.stderr.write("[5/%d] 生成垫乐…\n" % steps_n)
        rc = _run_music(_music_args(a, outdir))
        if rc:
            return rc

    # [6/6] 混音
    sys.stderr.write("[%d/%d] 本地混音…\n" % (steps_n, steps_n))
    rc = _run_mix(_mix_args(a, outdir))
    if rc:
        return rc
    sys.stderr.write("\n完成：%s\n" % (outdir / (a.filename or "program.mp3")))
    return EXIT_OK


def _ns(**kw):
    """造一个临时命名空间（给内部复用其它子命令用）。"""
    return argparse.Namespace(**kw)


def _plan_args(a, outdir, minutes):
    return _ns(topic=a.topic, minutes=minutes, songs=getattr(a, "songs", None),
               mode=a.mode, audience=a.audience, brief=a.brief, host=a.host,
               from_file=a.from_file, outdir=str(outdir), plan=None, json=a.json,
               out=None, model=a.model, temperature=a.temperature,
               max_tokens=a.max_tokens, key=a.key, dry_run=a.dry_run,
               no_json_mode=a.no_json_mode, force=a.force)


def _script_args(a, outdir, plan):
    return _ns(outdir=str(outdir), plan=None, minutes=None, songs=None,
               from_file=a.from_file, brief=a.brief, host=a.host,
               song_seconds=None, json=a.json, out=None, model=a.model,
               temperature=a.temperature, max_tokens=a.max_tokens, key=a.key,
               dry_run=a.dry_run, no_json_mode=a.no_json_mode, force=a.force)


def _pick_args(a, outdir):
    return _ns(outdir=str(outdir), plan=None, minutes=None, mode=None, host=None,
               audience=None, brief=None, from_file=a.from_file, offline=a.offline,
               download=a.download, page_size=a.page_size, tries=a.tries,
               points_per_search=a.points_per_search, timeout=a.timeout,
               force=a.force, yes=a.yes, budget=a.budget, json=a.json, out=None,
               key=a.key, topic=None, model=None)


def _voice_args(a, outdir, minutes=None):
    # minutes 必须传**从节目单算出来的那个值**，不能直接透传 a.minutes：
    # `all` 的 --minutes 默认是 None，而用户可能是按节目单的目标时长做的稿子，
    # 直接透传会让配音步骤拿默认值当基准，被自己的时长台账误拦（同族实测踩过一次）。
    return _ns(outdir=str(outdir), script=None, minutes=minutes, songs=None,
               voice=a.voice, speed=a.speed, tts_model=a.tts_model,
               sample_chars=a.sample_chars, points_per_1k=a.points_per_1k,
               song_seconds=None, timeout=a.timeout, force=a.force, yes=a.yes,
               budget=a.budget, json=a.json, out=None, key=a.key)


def _music_args(a, outdir):
    return _ns(outdir=str(outdir), cue="bed", style=a.style, prompt=a.prompt,
               title=a.title, with_lyrics=a.with_lyrics, timeout=a.timeout,
               force=a.force, yes=a.yes, budget=getattr(a, "budget_after_voice", None),
               json=a.json, out=None, key=a.key)


def _mix_args(a, outdir):
    return _ns(outdir=str(outdir), ffmpeg=a.ffmpeg, filename=a.filename,
               cue="bed", bed_seconds=a.bed_seconds, bed_volume=a.bed_volume,
               json=a.json, out=None)


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def _add_cpm(p):
    """`--chars-per-minute`：覆盖语速口径。

    为什么给这个开关：语速直接决定「目标时长 ↔ 字数」的换算，而不同节目差得很远
    （电台独白慢聊 220，快节奏资讯 300）。默认值是实测口径，但不是所有人的口径。
    它会**同时**影响三处：提示词里给模型的目标字数、时长台账的判定、成本报价——
    这正是它必须是一个显式开关、而不是三处各自一个参数的原因。
    """
    p.add_argument("--chars-per-minute", type=float, dest="chars_per_minute",
                   help="语速口径（字/分钟），默认 %s" % SHOW["chars_per_minute"])


def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**（与同族全部包同口径）。

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
                   help="最大输出 token，默认 8192（一期串词 1500+ 字，给少了会被截断）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词 + 提示词卫生自检，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")
    p.add_argument("--force", action="store_true",
                   help="忽略断点重跑这一步（**会重复扣费**）")
    if with_out:
        p.add_argument("--out", help="把结果写到这个文件")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · AI 电台 / 歌单串词（走 api.a7w.cn 的 OpenAI 兼容端点与生成应用）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models · "
               "POST https://api.a7w.cn/api/v1/apps/voice_tts/tts · "
               "POST https://api.a7w.cn/api/v1/apps/music_search/search · "
               "POST https://api.a7w.cn/api/v1/apps/music_generation/create · "
               "GET https://api.a7w.cn/api/v1/tasks/<task_id>",
        allow_abbrev=False)
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="节目单：选曲顺序 + 每段串词的意图", allow_abbrev=False)
    p.add_argument("--topic", required=True, help="节目主题（一句话说清听什么）")
    p.add_argument("--minutes", type=float, default=SHOW["default_minutes"],
                   help="目标节目时长（分钟），默认 %d" % SHOW["default_minutes"])
    p.add_argument("--songs", type=int, help="歌曲数，默认 %d" % SHOW["default_songs"])
    p.add_argument("--mode", help="节目类型（深夜陪伴 / 通勤 / 咖啡馆背景音…）")
    p.add_argument("--audience", help="目标听众（不给就让模型自己定）")
    p.add_argument("--host", help="主播人设（一句话）")
    p.add_argument("--brief", help="额外要求（口述的意图）")
    p.add_argument("--from-file", dest="from_file",
                   help="已有歌单文件（.txt/.csv/.json）；给了就以它为准，不许模型改曲目")
    p.add_argument("--outdir", default="radio-out", help="产出目录（**不许在包内**）")
    _add_cpm(p)
    _add_model_opts(p)
    p.set_defaults(func=_run_plan)

    p = sub.add_parser("script", help="写串词：开场 + 每首前的过渡 + 结尾（缺一不可）", allow_abbrev=False)
    p.add_argument("--outdir", default="radio-out", help="产出目录（**不许在包内**）")
    p.add_argument("--plan", help="节目单文件，默认 <outdir>/plan.json")
    p.add_argument("--minutes", type=float, help="覆盖目标时长（默认取节目单）")
    p.add_argument("--songs", type=int, help="覆盖歌曲数（默认取节目单的 tracks 条数）")
    p.add_argument("--host", help="覆盖主播人设")
    p.add_argument("--brief", help="额外要求")
    p.add_argument("--from-file", dest="from_file", help="歌单文件（覆盖曲目列表）")
    p.add_argument("--song-seconds", type=float, dest="song_seconds",
                   help="每首曲长（秒）的**声明值**，用于时长台账；默认 %s 秒/首（假设值）"
                        % SHOW["song_seconds_fallback"])
    _add_cpm(p)
    _add_model_opts(p)
    p.set_defaults(func=_run_script)

    p = sub.add_parser("voice", help="串词配音（**先报价**；断点续跑，不重复扣费）", allow_abbrev=False)
    p.add_argument("--outdir", default="radio-out", help="产出目录（**不许在包内**）")
    p.add_argument("--script", help="串词稿（script.json 或 .md），默认 <outdir>/script.json")
    p.add_argument("--voice", help="音色 reference_id（32 位十六进制；用 `voices` 查）")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro",
                   help="TTS 模型：s1 / s2-pro，默认 s2-pro")
    p.add_argument("--speed", type=float, help="语速（prosody.speed，1.0 为原速）")
    p.add_argument("--minutes", type=float, help="覆盖目标时长（只影响时长台账）")
    p.add_argument("--songs", type=int, help="覆盖歌曲数（只影响时长台账）")
    p.add_argument("--song-seconds", type=float, dest="song_seconds",
                   help="每首曲长（秒）的声明值，用于时长台账")
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

    p = sub.add_parser("pick", help="选曲：music_search 搜索，或 --from-file 读本地歌单", allow_abbrev=False)
    p.add_argument("--outdir", default="radio-out", help="产出目录（**不许在包内**）")
    p.add_argument("--plan", help="节目单文件，默认 <outdir>/plan.json（搜索路线要用它定曲目）")
    p.add_argument("--from-file", dest="from_file",
                   help="从本地歌单文件读曲目（.txt/.csv/.json）——**离线，不花钱**")
    p.add_argument("--offline", action="store_true",
                   help="明确表示不联网（必须配合 --from-file）")
    p.add_argument("--download", action="store_true",
                   help="把搜到的 mp3 下到 <outdir>/songs/（默认只存元信息）")
    p.add_argument("--page-size", type=int, default=5, dest="page_size",
                   help="每页条数，最大 %d，默认 5" % SEARCH_MAX_PAGE_SIZE)
    p.add_argument("--tries", type=int, default=1,
                   help="每首最多搜几次（第 2 次会带上歌手名再搜；**每次调用都扣点**）")
    p.add_argument("--points-per-search", type=float, dest="points_per_search",
                   help="覆盖选曲单价（点/次），默认用实测值 %s" % SEARCH_POINTS_PER_CALL)
    p.add_argument("--timeout", type=int, default=1800, help="任务轮询超时（秒）")
    p.add_argument("--force", action="store_true", help="忽略断点重下（**会重复扣点**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_pick)

    p = sub.add_parser("music", help="垫乐：music_generation/create（异步，先报价）", allow_abbrev=False)
    p.add_argument("--outdir", default="radio-out", help="产出目录（**不许在包内**）")
    p.add_argument("--cue", default="bed", choices=sorted(MUSIC_CUES),
                   help="档位，目前只有 bed（垫乐）")
    p.add_argument("--style", help="覆盖音乐风格描述（默认内置）")
    p.add_argument("--prompt", help="覆盖生成提示词（默认内置）")
    p.add_argument("--title", help="曲目标题，默认「电台垫乐」")
    p.add_argument("--with-lyrics", action="store_true", dest="with_lyrics",
                   help="先生成歌词再谱曲（歌词 %s 点/次；默认纯器乐）"
                        % MUSIC_POINTS_PER_LYRICS)
    p.add_argument("--timeout", type=int, default=1800, help="任务轮询超时（秒）")
    p.add_argument("--force", action="store_true", help="忽略断点重做（**会重复扣费**）")
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="预算上限（点）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_music)

    p = sub.add_parser("mix", help="串词 + 歌曲拼接 + 节目单 / 时间轴（需要 ffmpeg）", allow_abbrev=False)
    p.add_argument("--outdir", default="radio-out", help="产出目录")
    p.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径（默认找 PATH 与 FFMPEG 环境变量）")
    p.add_argument("--filename", help="成片文件名，默认 program.mp3")
    p.add_argument("--cue", default="bed", help="垫乐档位，默认 bed")
    p.add_argument("--bed-seconds", type=float, default=0.0, dest="bed_seconds",
                   help="垫乐铺多少秒（0 = 不铺垫乐，默认）")
    p.add_argument("--bed-volume", type=float, default=0.18, dest="bed_volume",
                   help="垫乐音量（0~1），默认 0.18")
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_mix)

    p = sub.add_parser("all", help="整条链路：节目单 → 串词 → 选曲 → 配音 → 垫乐 → 混音", allow_abbrev=False)
    p.add_argument("--topic", help="节目主题（plan 用；已有节目单时可省）")
    p.add_argument("--topic-override", action="store_true", dest="topic_override",
                   help="即使已有节目单也重新出题（**会重复扣费**）")
    # 默认 **None** 而不是 30：`all` 的时长基准应当优先取**节目单里的目标时长**，
    # 只有用户显式给了 --minutes 才覆盖它。给默认值会让短节目的稿子
    # 在配音步骤被按 30 分钟校验，撞上时长台账（同族实测踩过一次）。
    p.add_argument("--minutes", type=float, default=None,
                   help="目标时长（分钟）；不给就取节目单里的目标时长，再退到 %d"
                        % SHOW["default_minutes"])
    p.add_argument("--songs", type=int)
    p.add_argument("--mode")
    p.add_argument("--audience")
    p.add_argument("--host")
    p.add_argument("--brief")
    p.add_argument("--outdir", default="radio-out", help="产出目录（**不许在包内**）")
    p.add_argument("--from-file", dest="from_file", help="本地歌单文件（离线路线）")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--download", action="store_true", help="把搜到的 mp3 下到本地")
    p.add_argument("--page-size", type=int, default=5, dest="page_size")
    p.add_argument("--tries", type=int, default=1)
    p.add_argument("--points-per-search", type=float, dest="points_per_search")
    p.add_argument("--voice")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro")
    p.add_argument("--speed", type=float)
    p.add_argument("--sample-chars", type=int, default=0, dest="sample_chars")
    p.add_argument("--points-per-1k", type=float, dest="points_per_1k")
    p.add_argument("--skip-music", action="store_true", dest="skip_music",
                   help="跳过垫乐（只出串词 + 歌曲 + 混音）")
    p.add_argument("--style")
    p.add_argument("--prompt")
    p.add_argument("--with-lyrics", action="store_true", dest="with_lyrics")
    p.add_argument("--ffmpeg")
    p.add_argument("--filename")
    p.add_argument("--bed-seconds", type=float, default=0.0, dest="bed_seconds")
    p.add_argument("--bed-volume", type=float, default=0.18, dest="bed_volume")
    p.add_argument("--title")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--yes", action="store_true", help="确认报价，直接开跑")
    p.add_argument("--budget", type=float, help="整条链路的预算上限（点）")
    _add_cpm(p)
    # `--force` 由 _add_model_opts 统一提供（它同时被 plan/script 用），
    # 这里**不再重复定义**——重复会直接抛 `conflicting option string: --force`。
    _add_model_opts(p)
    p.set_defaults(func=_run_all)

    p = sub.add_parser("cost", help="只算钱（本地计算，一次调用都不发）", allow_abbrev=False)
    p.add_argument("--minutes", type=float, default=SHOW["default_minutes"], help="目标时长")
    # 默认 **None**：曲目数要按目标时长反推（见 suggest_songs），
    # 写死默认值会让「这一档的推荐曲目数」这条提示跟实际算的钱对不上（实测踩过）。
    p.add_argument("--songs", type=int, default=None,
                   help="歌曲数；不给就按目标时长反推（推荐值 %d 首 @%d 分钟）"
                        % (suggest_songs(SHOW["default_minutes"]),
                           SHOW["default_minutes"]))
    p.add_argument("--from-file", dest="from_file", help="按这个歌单文件的曲目数算")
    p.add_argument("--searches", type=int,
                   help="选曲搜索调用次数（每次扣点；按次计）")
    p.add_argument("--creates", type=int,
                   help="配乐 create 次数（每次 %s 点）" % MUSIC_POINTS_PER_CREATE)
    p.add_argument("--with-lyrics", action="store_true", dest="with_lyrics")
    p.add_argument("--points-per-1k", type=float, dest="points_per_1k",
                   help="覆盖配音单价（点/千字）")
    p.add_argument("--points-per-search", type=float, dest="points_per_search",
                   help="覆盖选曲单价（点/次）")
    p.add_argument("--points-per-ktok", type=float, dest="points_per_ktok",
                   help="文本大模型单价（点/千 token）；不给就**不报文本金额**（平台未公开）")
    p.add_argument("--budget", type=float, help="预算上限（点）；超了就非 0 退出")
    _add_cpm(p)
    _add_json(p)
    p.add_argument("--out", help="把结果写到这个文件")
    p.set_defaults(func=_run_cost)

    p = sub.add_parser("models", help="列出在架模型 + 本包用到的 app 的真实接口（免费）", allow_abbrev=False)
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=_run_models)

    p = sub.add_parser("voices", help="列出可用音色，拿配音要的 reference_id（免费）", allow_abbrev=False)
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
    _JSON["want"] = "--json" in argv_eff      # argparse 失败时还没有 a，先按命令行判断
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
    # `all` 的预算要拆成两段：配音先花，剩下的额度才给垫乐
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
