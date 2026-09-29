---
name: sanjianke-radio-dj
slug: sanjianke-radio-dj
displayName: 三剪客 · AI 电台
description: "给一个主题或一份歌单，产出一期可播出的电台节目：节目单（选曲顺序 + 每段串词意图）→ 串词（开场 + 每首前的过渡 + 结尾，三段缺一不可）→ 主持人口播配音（先报价、断点续跑）→ 选曲（music_search 搜索或读本地歌单）→ 与歌曲拼接成 mp3 + 节目单 + 时间轴。六道硬闸门：违禁词（「最X」可枚举语境豁免、句首不豁免）、占位符、照抄示例（三条判据）、**串词结构（过渡条数须等于歌曲数）**、时长台账（±25%）、成本上限。走 api.a7w.cn 的 `/api/v1/chat/completions` 与生成应用端点。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.2
summary: "电台节目最难的不是选歌，是「这一期怎么开始、每首歌之间说什么、怎么收」。本包把这条链路做成命令：`plan` 出节目单并逐首标出串词意图；`script` 写串词（开场 + 每首前一条过渡 + 结尾，逐段带字数与句数配额）；`voice` 串词配音（先报价再扣费、断点续跑、按段落切块，好插进歌与歌之间）；`pick` 选曲（music_search 按次扣点，或读本地歌单离线不花钱）；`music` 出垫乐；`mix` 用本地 ffmpeg 拼成 mp3 + 每首歌一条章节标记 + 时间轴；`all` 串全流程；`cost` 只算钱；`models`/`voices` 现查在架模型与音色。真机实测：节目单 1840 token、串词 2499 字、配音 278/318/496 字三组样本逐条吻合 50 点/千字、选曲 10 点/次、配乐 65 点/次、混音产出 17.5 MB mp3 与 5 条章节标记、重跑跳过全部片段 0 点。最值钱的闸门是串词结构：只有歌单的稿子字数对、时长对、读起来也顺，但它是报幕不是电台节目——只有机器看得出来。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 电台
  - 播客
  - api.a7w.cn
---

# 三剪客 · AI 电台 / 歌单串词

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几次）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

## 能做什么

给一个**主题**或一份**歌单**，一条链路产出一期**可播出的电台节目**：

```
plan    →   script   →   voice    →   pick        →   mix
 节目单      串词稿      主持人口播     选曲          串词 + 歌曲拼接
选曲顺序     开场+过渡N   先报价        在线搜索/本地    mp3 + 节目单
+ 串词意图   + 结尾      断点续跑       歌单             + 时间轴
```

它替代的是电台生产里最卡人的那一段：不是"找不到歌"，而是
"**这一期怎么开始、每首歌之间说什么、怎么收**"。这三件事定不清楚，
剪出来就是一段连着放歌的音频。

| 子命令 | 做什么 | 花不花钱 | 产出 |
|---|---|---|---|
| `plan` | 节目单：选曲顺序 + 每段串词的意图 | 一次文本调用（很便宜） | `plan.json` + `plan.md` |
| `script` | 串词：开场 + 每首前的过渡 + 结尾 | 一次文本调用 | `script.json` + `script.md` |
| `voice` | 串词配音（按段落切块） | **先报价**，按千字计费 | `voice/*.mp3` + `voice/index.json` |
| `pick` | 选曲：在线搜索 / 本地歌单 | 搜索**10 点/次**；`--from-file` 免费 | `playlist.json` + `program-list.txt` |
| `music` | 垫乐 | **先报价**，65 点/次 | `music/bed.mp3` |
| `mix` | 拼接 + 节目单 + 时间轴 | **零网络零成本** | `program.mp3` + `chapters.txt` + `timeline.md` |
| `all` | 串起来跑完整条链路 | 先报价，**断点续跑** | 上面全部 |
| `cost` | 只算钱 | 零网络零成本 | 成本表 |
| `models` | 现查在架模型 + 本包用到的 app 真实接口 | 免费 | 模型与接口清单 |
| `voices` | 现查可用音色（拿 `reference_id`） | 免费 | 音色清单 |

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 配音 **50 点/千字**（实测）、选曲 **10 点/次**（实测）、配乐 **65 点/次**（实测）；1 元 = 100 点。30 分钟一期（5 首）≈ 95 点配音 ≈ **0.95 元** |
| 要多久 | 实测 30 分钟一期：节目单 7 秒、串词约 20 秒、一段配音约 20 秒、一段垫乐约 90 秒 |
| 要装什么 | **什么都不用装**。只用 Python 标准库；`mix` 需要本机有 `ffmpeg`（没有会明确降级，见下） |
| 中断了怎么办 | **断点续跑**：已完成的配音片段与垫乐直接跳过，重跑 0 次调用、0 点；**但配音断点按「正文 + 音色 + 语速 + 模型」判定——台词一改就重配重扣** |
| 歌放几首合适 | 不给 `--songs` 就**按目标时长反推**（30 分钟 → 4~5 首）。曲目数写死会撞上"装不下"预检：30 分钟塞 8 首（各 190 秒）只剩 2 分钟说话，这档规格本身不成立 |
| 会瞎编吗 | 提示词里写死了"不许编人名、机构、榜单、奖项"，并用合规闸门兜底 |
| 只有歌单的稿子能用吗 | **不能**。串词结构闸门会拦——见「六道硬闸门」 |

### 六道硬闸门（都是拦截，不是提醒）

命中即**标红 + stderr 汇总 + 退出码非 0**，可直接进 CI；`--json` 下走统一信封。

| # | 闸门 | 判定口径 | 退出码 |
|---|---|---|---|
| 1 | 合规 | 广告法违禁词 + 口播红线；「最X」按**可枚举语境**豁免（见下） | 3 |
| 2 | 占位符残留 | `{}`、`[待填]`、`XXX`、`此处省略`、`TODO` | 3 |
| 3 | prompt_echo | 去标点相等 / 二元组 Jaccard ≥ 0.75 / 示例覆盖度 ≥ 0.60 + 相对长度守卫 | 3 |
| 4 | **串词结构** | **开场 + 每首前的过渡（条数必须等于歌曲数）+ 结尾**；缺开场、缺结尾、缺过渡、过渡条数不符、过渡编号断号、有孤儿正文，全部拦 | 3 |
| 5 | 时长台账 | 串词字数折算时长 + 歌曲时长合计，偏离目标超过 ±25% | 3 |
| 6 | 成本上限 | `voice`/`pick`/`music`/`all` 跑前必须报价；`--yes` 或 `--budget` 二选一，超预算就地中止 | 2 / 5 |

外加一条**产出位置**闸门：`--outdir` 指到包内直接 `exit=2`（包内不许出现音频，
SkillHub 的扩展名白名单只放 `.md .py .txt .json .sh .js .yaml .yml .csv`）。

### 为什么第 4 道闸门是本包最值钱的那道

电台节目与"一个歌单"的分水岭就是**有人在三个位置上说话**：

- **开场**：告诉听众现在在听什么、这一期为什么值得听下去
- **每首前的过渡**：把上一首的情绪接到下一首上（缺了就是硬切歌）
- **结尾**：给一个可以被单独转述的收束句（缺了就是音乐淡出）

一份只有开场和结尾、或者只有一堆歌单描述的稿子：字数够、时长对、
合规干净、读起来也顺——**它在任何一道常规检查里都是合格的**，
但它配出来只是"报幕"，不是电台节目。发出去才发现形态不对。

所以这道闸门的判定**不采信模型自报的结构字段**，而是拿正则去读**渲染后的成品稿**：

```
## 【开场】
## 【过渡 1】
## 【过渡 2】
## 【结尾】
```

读不出开场 / 读不出结尾 / 过渡条数不等于歌曲数，一律拦。
依据是本库吃过的亏：标题工坊上一版只信模型自报的 `formula` 字段，闸门成了假绿。

### 「最X」的语境豁免

「回头翻一条自己播放量最低的视频」这种话是在**描述自己的数据**，
不是对商品做绝对化宣称。全库为它定了一条很窄的豁免：

- `最X` **不在句首**，且它前一个字是计量类名词（量 / 率 / 数 / 分 / 位 / 首 / 条 / 次 / 段 / 部 / 集 / 期 / 页 / 个 / 天 / 月 / 年）
- **且** `最X` 后面紧跟「的」或「之」

命中豁免时**整处放过，但在产出里登记**（`gates.compliance.exempted`），
报告里会明说"本地放过了 N 处疑似绝对化用语"，**不静默放过**。
句首的「最好 / 最低」**不豁免**——豁免词表刻意不含 `时 / 款 / 种 / 家 / 价`，
因为「课时最低的课程」「单价最低」都是真实的价格宣称形态，必须照拦。

### prompt_echo：模型会照抄示例

本库实测过两次：提示词里写过正例，模型就产出了几乎一字不差的标题；
其中一次那条还拿了**最高分**——不是"真的最好"，是"抄了标准答案"。
所以本包的提示词里**不出现任何一句可直接复制的完整中文句子**，
举例只用描述性说明；真实示例登记在 `PROMPT_SAMPLES`，并由
`prompt_hygiene()` 在 `--dry-run` 时对**即将发送的提示词**做前置自检。

## 怎么用（命令行）

```bash
# 1) 配 Key（三种方式任选）
export A7W_API_KEY="<你的Key>"            # Windows: $env:A7W_API_KEY="<你的Key>"
#   或者 --key <你的Key>，或者 python3 scripts/a7w.py login --key <你的Key>

# 2) 节目单（不给 --songs 就按目标时长反推曲目数）
python3 scripts/run.py plan --topic "深夜开车听的 City Pop" --minutes 30 \
        --mode "深夜陪伴" --outdir D:/radio/ep01

# 3) 串词（开场 + 每首前一条过渡 + 结尾，逐段带配额）
python3 scripts/run.py script --outdir D:/radio/ep01

# 4) 选曲：本地歌单（离线不花钱）
python3 scripts/run.py pick --outdir D:/radio/ep01 --from-file D:/radio/playlist.txt
#    或者在线搜索（**10 点/次**，先报价）
python3 scripts/run.py pick --outdir D:/radio/ep01 --budget 100

# 5) 看音色，整条复制 reference_id（32 位十六进制，抄短了会失败）
python3 scripts/run.py voices

# 6) 配音：先报价，确认了再加 --yes（或用 --budget 封顶）
python3 scripts/run.py voice --outdir D:/radio/ep01
python3 scripts/run.py voice --outdir D:/radio/ep01 --yes

# 7) 本地拼接（需要 ffmpeg）：mp3 + 每首歌一条章节标记 + 时间轴
python3 scripts/run.py mix --outdir D:/radio/ep01
python3 scripts/run.py mix --outdir D:/radio/ep01 --ffmpeg "C:/ffmpeg/bin/ffmpeg.exe"

# 8) 整条链路（断点续跑，中断了原样重跑即可）
python3 scripts/run.py all --topic "深夜开车听的 City Pop" --minutes 30 \
        --outdir D:/radio/ep01 --budget 600

# 只算钱，一次调用都不发
python3 scripts/run.py cost --minutes 30
```

真实端点（都在 api.a7w.cn 上）：

| 用途 | 端点 |
|---|---|
| 大模型（节目单 / 串词） | `POST /api/v1/chat/completions` |
| 模型清单 | `GET /api/v1/models` |
| 串词配音（同步，≤500 字） | `POST /api/v1/apps/voice_tts/tts` |
| 串词配音（异步，长文本） | `POST /api/v1/apps/voice_tts/tts_async` |
| 音色列表 | `POST /api/v1/apps/voice_tts/list_voices` |
| **选曲搜索（同步，10 点/次）** | `POST /api/v1/apps/music_search/search` |
| 配乐 | `POST /api/v1/apps/music_generation/create` |
| 歌词 | `POST /api/v1/apps/music_generation/lyrics` |
| 任务轮询 | `GET /api/v1/tasks/<task_id>` |

**开工前先现查一遍 schema，别照抄记忆**：

```bash
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py schema music_generation
python3 scripts/a7w.py schema music_search
```

三条实测确认的接口事实（本包就是踩过才写下来的）：

1. **配音的音色参数叫 `reference_id`，不叫 `voice_id`**。值是 `list_voices` 返回的
   `id` / `model_id`，**32 位十六进制，抄短一位就得到 `code=0 任务处理失败`**。
2. **配乐的创建动作叫 `create`，不叫 `generate`**。接口代码里没有 `generate`；
   `generate` 只是 `create` 的 `type` 参数的一个取值。而且 `create` 的参数表里
   **没有时长参数**，垫乐多长由上游决定，长度控制在 `mix` 里用 ffmpeg 做。
3. **`music_search` 是真实存在的 app**，只有一个同步接口
   `POST /api/v1/apps/music_search/search`，入参 `{keyword, page, page_size≤20}`，
   返回 `data.result.items[]`（`title / author / url / link / pic / songid`），
   `url` 是可直接下载的 mp3。**它按次扣点（实测 10 点/次），不是免费接口。**

另外两条平台口径：

- `/chat/completions` 的**成功响应不带 `code` 字段**；生成应用（配音 / 选曲 / 配乐）
  **`code == 1` 才是成功**。两者不能互相套用。
- 异步任务的 **`status` 在任务 `data` 顶层**，不在 `data.result` 里（平台文档写错了）。
  实测原文：`data.status = 'completed'`、`data.result.status = None`。

## 参数说明

### 通用

| 参数 | 说明 |
|---|---|
| `--outdir` | 产出目录。**不许指到包内**（指到包内 `exit=2`），默认 `./radio-out` |
| `--json` | JSON 输出，写在子命令**前后都可以**；失败走 `{"ok":false,"exit":N,"error":{...}}` |
| `--key` | 临时指定 API Key（也可用 `A7W_API_KEY` 或 `~/.a7w/config.json`） |
| `--model` | 文本模型名，默认 `deepseek-chat`；用 `models` 现查在架名 |
| `--temperature` / `--max-tokens` | 采样温度（默认 0.7）/ 最大输出 token（默认 8192） |
| `--dry-run` | 只打印将发送的提示词 + 提示词卫生自检，不花钱 |
| `--force` | 忽略断点重跑这一步（**会重复扣费**） |
| `--chars-per-minute` | 语速口径（字/分钟），默认 250。它**同时**决定提示词配额、时长台账与成本报价 |

### `plan`

| 参数 | 说明 |
|---|---|
| `--topic` | 主题，一句话说清听什么（必填） |
| `--minutes` | 目标节目时长（分钟），默认 30，允许 5~240 |
| `--songs` | 歌曲数；**不给就按目标时长反推**（30 分钟 → 4 首） |
| `--mode` | 节目类型（深夜陪伴 / 通勤 / 咖啡馆背景音…） |
| `--audience` / `--host` / `--brief` | 目标听众 / 主播人设 / 额外要求 |
| `--from-file` | 已有歌单；给了就以它为准，不许模型改曲目 |

### `script`

| 参数 | 说明 |
|---|---|
| `--plan` | 节目单文件，默认 `<outdir>/plan.json` |
| `--minutes` / `--songs` | 覆盖目标时长 / 曲目数 |
| `--song-seconds` | 每首曲长（秒）的**声明值**，默认 190（**假设值**，拿到本地文件后以真实时长为准） |

### `voice`

| 参数 | 说明 |
|---|---|
| `--script` | 串词稿（`script.json` 或 `.md`），默认 `<outdir>/script.json` |
| `--voice` | 音色 `reference_id`（用 `voices` 查） |
| `--tts-model` | TTS 模型：`s1` / `s2-pro`，默认 `s2-pro` |
| `--speed` | 语速（`prosody.speed`，1.0 为原速） |
| `--sample-chars` | **只配前 N 个字**（试链路省钱用；0 = 全部） |
| `--points-per-1k` | 覆盖配音单价（点/千字），默认用实测值 50 |
| `--yes` / `--budget` | 二者给其一：确认报价 / 预算封顶（点） |

### `pick`

| 参数 | 说明 |
|---|---|
| `--from-file` | 读本地歌单（`.txt` / `.csv` / `.json`）——**离线，不花钱** |
| `--plan` | 节目单文件，搜索路线要用它定曲目 |
| `--download` | 把搜到的 mp3 下到 `<outdir>/songs/`（默认只存元信息） |
| `--page-size` | 每页条数，最大 20，默认 5 |
| `--tries` | 每首最多搜几次（第 2 次带上歌手名；**每次调用都扣点**） |
| `--points-per-search` | 覆盖选曲单价（点/次），默认用实测值 10 |
| `--yes` / `--budget` | 同 `voice` |

### `music`

| 参数 | 说明 |
|---|---|
| `--cue` | 档位，目前只有 `bed`（垫乐） |
| `--style` / `--prompt` / `--title` | 覆盖风格 / 提示词 / 标题 |
| `--with-lyrics` | 先生成歌词再谱曲（歌词 12 点/次；默认纯器乐） |
| `--yes` / `--budget` | 同 `voice` |

### `mix`

| 参数 | 说明 |
|---|---|
| `--ffmpeg` | ffmpeg 可执行文件路径（默认找 `PATH` 与 `FFMPEG` 环境变量） |
| `--filename` | 成片文件名，默认 `program.mp3` |
| `--bed-seconds` / `--bed-volume` | 垫乐铺多少秒（0 = 不铺，默认）/ 垫乐音量（默认 0.18） |

`music_generation/create` 的参数表里**没有时长参数**，生成多长由上游决定，
所以垫乐长度控制在 `mix` 阶段用 ffmpeg 做。

### 产出目录长这样

```
D:/radio/ep01/
├── plan.json / plan.md               节目单
├── script.json / script.md           串词稿（成品稿，闸门读的就是它）
├── playlist.json / program-list.txt  选曲结果与排播节目单
├── voice/                            串词配音片段 + index.json
├── music/bed.mp3                     垫乐（可选）
├── songs/                            本地音频（--download 或手工放）
├── radio-state.json                  断点文件
├── program.mp3                       **成片**
├── chapters.txt / chapters.json      章节标记（每首歌一条）
├── timeline.md / playlist.txt        时间轴与拼接清单
└── .mix/                             归一化后的 wav 中间件（可整目录删掉）
```

音频一律落在**包外**的 `--outdir` 里，包内只有文本与脚本。

## 排错

### 1. 配音返回 `code=0「任务处理失败，请稍后重试」`

九成是 **`reference_id` 抄短了**。`list_voices` 返回的 `id` 是 **32 位十六进制**
（例：`0705a04a4c3f4b65b888d2aa7a4e6b08`）。用 `run.py voices` 重新**整条**复制。

判断方法：去掉 `--voice` 再跑一次。不指定音色会用平台默认音色，
能成功就说明是音色 ID 的问题，不是文本的问题。

### 2. 报「规格不成立（加上 --force 才会照跑）」

那是**规格预检**：目标时长装不下这么多歌 + 串词。它会明确告诉你推荐曲目数：

```
参数错误：规格不成立（加上 --force 才会照跑）：30 分钟 − 8 首（曲长按 190 秒/首估
≈ 25.3 分钟，占 84%）≈ 留给串词 4.7 分钟；开场+结尾+8 条过渡按中位口径约需 2.5 分钟
——**装不下**（歌曲占目标时长 84% > 上限 75%）。要么把节目加到 31 分钟以上，
要么降到 4 首 …
```

按提示改 `--minutes` 或 `--songs`（或去掉 `--songs` 让本包自己推荐）。
真的想照跑就加 `--force`——它是"提醒"，不是"禁止"。

### 3. 时长台账拦下串词稿

```
[时长台账] 串词 1554 字 ÷ 250 字/分钟 ≈ 6.2 分钟；4 首歌 ≈ 12.7 分钟；
合计 ≈ 18.9 分钟；目标 30.0 分钟，容差 25%（22.5~37.5 分钟）（偏离目标 -11.1 分钟）
```

三种原因，处理方式不同：

- **真的是模型写少了**：重跑 `script`。提示词里已经逐段给了「约 X 字 / 不少于 N 句」
  的配额（这个配额就是被这条闸门逼出来的）；还是短就换模型，或把 `--max-tokens` 调大。
- **语速口径不对**：你的节目语速跟 250 字/分钟差得远，用 `--chars-per-minute`
  改成自己的值，闸门与成本报价会一起跟着改。
- **曲长假设值偏了**：默认按 190 秒/首估；用 `--song-seconds` 给真实的平均曲长，
  或先跑 `pick` 拿到本地文件（时间轴会以真实时长为准）。

### 4. 串词结构闸门报「过渡段有 N 条，但歌曲有 M 首」

每条过渡对应一首歌，数量必须相等。常见成因是节目单中途被改过（手动改了曲目数）
而串词稿没重跑。**先把 `plan` 定下来再跑 `script`**，或给 `script --songs` 指明曲目数。

### 5. `--outdir 指到了包内`

产出音频会让整个 Skill 包在 SkillHub 上 400（白名单只放文本类后缀）。
换到包外目录，例如 `%TEMP%\radio` 或 `D:/radio/ep01`。

### 6. 本机没有 ffmpeg，mix 降级

`mix` 会写出 `playlist.txt`、`chapters.txt`、`program-list.txt`、`mix-commands.txt`
（都是文本），**但不产出 mp3**，并以 `exit=2` 明确报错——不假装成功。
装上 ffmpeg 后**原样重跑同一条命令即可**（断点续跑，不会重复扣配音/选曲的钱）。

ffmpeg 不一定要在 PATH 上：`--ffmpeg <路径>` 或环境变量 `FFMPEG` 都行。

### 7. `401 / 402 / 404`

- `401`：Key 无效或过期，重新到 https://api.a7w.cn/ 领一个。
- `402`：点数不足，充值后重试（失败任务平台会退回点数）。
- `404`：模型名不对。`deepseek-chat` 这个别名实测可用，但它**不在**
  `/api/v1/models` 的返回列表里——"列表里没有"不等于"不能用"，
  也不等于"有价格"。用 `run.py models` 现查在架名字。

### 8. 报价和实际扣费不一致

以 `usage.points_cost` 为准，本包的报价是实测常量：
配音 50 点/千字、选曲 10 点/次、配乐 create 65 点/次、歌词 12 点/次。
每次调用后都会把真实扣点打出来，与报价差得明显时会明确标出来
（`_report_spend`），不会糊过去。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

## 相关链接

- 算力集市（注册领 Key、充值、控制台）：https://api.a7w.cn/
- 配音参数与自己音色的克隆入口：`POST /api/v1/apps/voice_tts/list_voices`、
  `POST /api/v1/apps/voice_tts/clone_voice`
- 选曲搜索：`POST /api/v1/apps/music_search/search`（**按次扣点**）
- 配乐参数与歌词：`POST /api/v1/apps/music_generation/create`、
  `POST /api/v1/apps/music_generation/lyrics`
- 任务查询：`GET /api/v1/tasks/<task_id>`
- 文档三份：
  - `references/radio-script-method.md` —— 串词方法与时长 / 字数换算
  - `references/pick-and-voice.md` —— 选曲路线、音色挑选与配音参数
  - `references/cost-and-troubleshooting.md` —— 实测单价、报价口径与排错手册

---

## 已知取舍（写在这里，免得下次又"优化"回去）

1. **文本大模型的单价本包不报**。平台 `/api/v1/models` 里没有任何价格字段，
   `/api/v1/pricing` 也不覆盖 `chat/completions`。想算文本的钱请显式给
   `cost --points-per-ktok N`——本包**不编单价**。
2. **「第一」类口径取了限定式写法**，与 `sanjianke-multiplat-rewrite` 的裸
   `第一(?!次)` 有意不同：电台串词里报歌序是常态（「第一首」），
   裸写法一次实测就会把整篇误拦。仍然照拦的是「全国 / 行业 / 收听率…第一」
   「第一品牌」「排名第一」这类**排他性宣称**。
3. **违禁词表比模板多三个词**：`省` / `划算` / `实惠`。模板词表里有「便宜」
   却没有「省」，而「最省钱的套餐」是口播里最常见的绝对化说法。
   加词只会让闸门更严，不放松任何一处判定。
4. **选曲默认不下载音频**（只存元信息与可下载 URL）。原因是搜索结果来自
   流媒体源，批量落盘既慢又涉及授权问题。要本地拼接就显式加 `--download`，
   或者用 `--from-file` 给你自己确认过授权的歌单。
5. **曲长在拿到本地文件前是假设值**（默认 190 秒/首），产出里一律标注
   `song_seconds_source: assumed`；只有 `mix` 报出的时间轴是真实时长。
   本包**不把假设当实测**。
6. **付费步骤与本地步骤严格分开**：`mix` 永远不会自己去调付费接口。
   把一次 65 点的 create 塞进零成本的 `mix` 里，会让"我只是想重新拼一次"
   变成"又花了 65 点"。
7. **过渡段编号一律按稿子里的位置重编**，不采信模型自报的 `no`。
   实测模型会把 4 条过渡编成 2/3/4/5；过渡的语义是"第 i 首歌之前那条"，
   **位置就是它的定义**。
8. **串词按段落切块配音，不整篇合成一段**。整篇一段音频没法插到歌与歌之间，
   而电台的形态就是"说一句 → 放一首 → 再说一句"。
