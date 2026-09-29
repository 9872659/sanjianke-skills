---
name: sanjianke-podcast-studio
slug: sanjianke-podcast-studio
displayName: 三剪客 · 播客全自动生产
description: "给一个主题，一条链路产出一期可发布的播客：选题与提纲 → 双人对话稿（标注角色与语气）→ 分角色配音（两个音色）→ 片头 / 转场 / 片尾配乐 → 本地混音成 mp3 + 章节标记 + 时间轴。六道硬闸门全拦截：广告法违禁词、占位符残留、照抄示例、**对话稿必须两个角色交替发言**、时长偏离 ±25%、成本上限；配音与配乐跑前先报价，`--yes` 或 `--budget` 二选一，断点续跑按台词判定，结算只认 `usage.points_cost`。走 api.a7w.cn 的 `/api/v1/chat/completions` 与生成应用端点。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.4
summary: "播客最难的不是录音，是「一期节目说什么、说多久、谁在说」。本包把这条链路做成命令：`outline` 出选题与提纲，`script` 写双人对话稿并逐句标角色与语气，`voice` 分角色配音（两个音色、先报价再扣费、断点续跑），`music` 出片头 / 转场 / 片尾，`mix` 用本地 ffmpeg 拼成 mp3 并生成章节标记与时间轴，`all` 串全流程，`cost` 只算钱，`models`/`voices` 现查在架模型与音色。真机实测一期 8 分钟：提纲 1211 token、对话稿 4367 token（63 句、两个角色、相邻同角色占比 0.032）、配音 200 字 = 10.0 点（实测 50 点/千字，21~57 字五组样本逐条线性、无最低消费）、配乐 create = 65 点、混音产出 887 KB mp3 与章节标记。最值钱的闸门是对话稿结构：单角色稿字数对、时长对、读起来也顺，但它是朗读不是播客——只有机器看得出来。30 分钟一期口径：7950 字 ≈ 398 点配音 + 195 点配乐 ≈ 5.93 元。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 播客
  - 配音
  - api.a7w.cn
---

# 三剪客 · 播客全自动生产

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几次）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

## 能做什么

给一个**主题**，一条链路产出一期**可发布的播客**：

```
outline →  script  →  voice  →  music  →  mix
 选题      双人      分角色     片头/转场    mp3 +
 提纲      对话稿     配音      /片尾配乐   章节标记 + 时间轴
```

它替代的是播客生产里最卡人的那一段：不是"录不出来"，而是"要先定清楚讲什么、
讲多长、谁在说、说完怎么收"。这四件事定不清楚，录出来就是一期
正确但没人听完的节目。

| 子命令 | 做什么 | 花不花钱 | 产出 |
|---|---|---|---|
| `outline` | 选题 + 提纲 | 一次文本调用（很便宜） | `outline.json` + `outline.md` |
| `script` | 双人对话稿（角色 + 语气 + 字数配额） | 一次文本调用 | `script.json` + `script.md` |
| `voice` | 分角色配音（两个音色） | **先报价**，按千字计费 | `voice/*.mp3` + `voice/index.json` |
| `music` | 片头 / 转场 / 片尾配乐 | **先报价**，按次计费 | `music/{intro,bed,outro}.mp3` |
| `mix` | 本地拼成 mp3 + 章节标记 + 时间轴 | **零网络零成本** | `episode.mp3` + `chapters.txt` + `timeline.md` |
| `all` | 串起来跑完整条链路 | 先报价，**断点续跑** | 上面全部 |
| `cost` | 只算钱 | 零网络零成本 | 成本表 |
| `models` | 现查在架模型 | 免费 | 模型清单 |
| `voices` | 现查可用音色（拿 `reference_id`） | 免费 | 音色清单 |

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 配音 **50 点/千字**（实测）、配乐 **65 点/次**（实测）；1 元 = 100 点。30 分钟一期 ≈ 7950 字 ≈ 398 点配音 + 195 点配乐 ≈ **5.93 元** |
| 要多久 | 实测 8 分钟一期：提纲 5 秒、对话稿 15 秒、5 段配音 45 秒、一段配乐约 90 秒 |
| 要装什么 | **什么都不用装**。只用 Python 标准库；`mix` 需要本机有 `ffmpeg`（没有会明确降级，见下） |
| 中断了怎么办 | **断点续跑**：已完成的配音片段与配乐直接跳过，重跑 0 次调用、0 点（实测 5 段全跳过、0.0 秒）；**但配音断点按「台词 + 角色」判定、配乐按「风格 + 提示词」判定——台词一改就重配重扣**。重跑前先确认台词没变，或先用 `cost` 核对预估花费 |
| 会瞎编吗 | 提示词里写死了"不许编人名、机构、论文、数据"，并用合规闸门兜底 |
| 单角色的稿子能用吗 | **不能**。对话稿结构闸门会拦——见「六道硬闸门」 |

### 六道硬闸门（都是拦截，不是提醒）

命中即**标红 + stderr 汇总 + 退出码非 0**，可直接进 CI；`--json` 下走统一信封。

| # | 闸门 | 判定口径 | 退出码 |
|---|---|---|---|
| 1 | 合规 | 广告法违禁词 + 播客口播红线；「最X」按**可枚举语境**豁免（见下） | 3 |
| 2 | 占位符残留 | `{}`、`[待填]`、`XXX`、`此处省略`、`TODO` | 3 |
| 3 | prompt_echo | 去标点相等 / 二元组 Jaccard ≥ 0.75 / 示例覆盖度 ≥ 0.60 | 3 |
| 4 | **对话稿结构** | **恰好两个角色标注 + 交替发言**；单角色、无角色标注、某个角色不足 3 句、相邻同角色占比 > 20%，全部拦 | 3 |
| 5 | 时长估算 | 按字数估时长，偏离目标超过 ±25% | 3 |
| 6 | 成本上限 | `voice`/`music`/`all` 跑前必须报价；`--yes` 或 `--budget` 二选一，超预算就地中止 | 2 / 5 |

外加一条**产出位置**闸门：`--outdir` 指到包内直接 `exit=2`（包内不许出现音频，
SkillHub 的扩展名白名单只放 `.md .py .txt .json .sh .js .yaml .yml .csv`）。

### 为什么第 4 道闸门是本包最值钱的那道

播客与"一篇文章"的分水岭就是**两个人在说话**。一份单角色的稿子：
字数对、时长对、合规干净、读起来也顺——**它在任何一道常规检查里都是合格的**，
但它配出来只是朗读，不是播客。发出去才发现形态不对。

所以这道闸门的判定**不采信模型自报的结构字段**，而是拿正则去读**渲染后的成品稿**：

```
**主持人**（平稳）：...
**嘉宾**（追问）：...
```

读不出两个角色、或者有"没有角色标注的发言行"，一律拦。
依据是本库吃过的亏：标题工坊上一版只信模型自报的 `formula` 字段，闸门成了假绿。

### 「最X」的语境豁免

「回头翻一条自己播放量最低的视频」这种话是在**描述自己的数据**，
不是对商品做绝对化宣称。全库为它定了一条很窄的豁免：

- `最X` 前一个字是计量类名词（量 / 率 / 数 / 分 / 位 / 条 / 次 / 段 / 部 / 集 / 页 / 个 / 天 / 月 / 年）
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

# 2) 选题与提纲
python3 scripts/run.py outline --topic "AI 剪辑到底省了谁的时间" --minutes 8 \
        --outdir D:/podcast/ep01

# 3) 双人对话稿（两个角色 + 交替发言 + 逐章字数配额）
python3 scripts/run.py script --outdir D:/podcast/ep01

# 4) 看音色，拿 reference_id（免费）
python3 scripts/run.py voices
python3 scripts/run.py voices --title-search 解说

# 5) 配音：先报价，确认了再加 --yes（或用 --budget 封顶）
python3 scripts/run.py voice --outdir D:/podcast/ep01 \
        --voice-a <音色A的reference_id> --voice-b <音色B的reference_id>
python3 scripts/run.py voice --outdir D:/podcast/ep01 --yes

# 6) 配乐：片头 / 转场 / 片尾
python3 scripts/run.py music --outdir D:/podcast/ep01 --cues intro,bed,outro --budget 200

# 7) 本地混音（需要 ffmpeg）：mp3 + 章节标记 + 时间轴
python3 scripts/run.py mix --outdir D:/podcast/ep01
python3 scripts/run.py mix --outdir D:/podcast/ep01 --ffmpeg "C:/ffmpeg/bin/ffmpeg.exe"

# 8) 整条链路（断点续跑，中断了原样重跑即可）
python3 scripts/run.py all --topic "AI 剪辑到底省了谁的时间" --minutes 30 \
        --outdir D:/podcast/ep01 --budget 600

# 只算钱，一次调用都不发
python3 scripts/run.py cost --minutes 30 --cues intro,bed,outro
```

真实端点（都在 api.a7w.cn 上）：

| 用途 | 端点 |
|---|---|
| 大模型（提纲 / 对话稿） | `POST /api/v1/chat/completions` |
| 模型清单 | `GET /api/v1/models` |
| 配音（同步，≤500 字） | `POST /api/v1/apps/voice_tts/tts` |
| 配音（异步，长文本） | `POST /api/v1/apps/voice_tts/tts_async` |
| 音色列表 | `POST /api/v1/apps/voice_tts/list_voices` |
| 配乐 | `POST /api/v1/apps/music_generation/create` |
| 歌词 | `POST /api/v1/apps/music_generation/lyrics` |
| 任务轮询 | `GET /api/v1/tasks/<task_id>` |

**开工前先现查一遍 schema，别照抄记忆**：

```bash
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py schema music_generation
```

两条实测确认的接口事实（本包就是踩过才写下来的）：

1. **配音的音色参数叫 `reference_id`，不叫 `voice_id`**。值是 `list_voices` 返回的
   `id` / `model_id`，**32 位十六进制，抄短一位就得到 `code=0 任务处理失败`**。
2. **配乐的创建动作叫 `create`，不叫 `generate`**。接口代码里没有 `generate`；
   `generate` 只是 `create` 的 `type` 参数的一个取值。

另外两条平台口径：

- `/chat/completions` 的**成功响应不带 `code` 字段**；生成应用（配音 / 配乐）
  **`code == 1` 才是成功**。两者不能互相套用。
- 异步任务的 **`status` 在任务 `data` 顶层**，不在 `data.result` 里（平台文档写错了）。
  实测原文：`data.status = 'completed'`、`data.result.status = None`。

## 参数说明

### 通用

| 参数 | 说明 |
|---|---|
| `--outdir` | 产出目录。**不许指到包内**（指到包内 `exit=2`），默认 `./podcast-out` |
| `--json` | JSON 输出，写在子命令**前后都可以**；失败走 `{"ok":false,"exit":N,"error":{...}}` |
| `--key` | 临时指定 API Key（也可用 `A7W_API_KEY` 或 `~/.a7w/config.json`） |
| `--model` | 文本模型名，默认 `deepseek-chat`；用 `models` 现查在架名 |
| `--temperature` / `--max-tokens` | 采样温度（默认 0.7）/ 最大输出 token（默认 8192） |
| `--dry-run` | 只打印将发送的提示词 + 提示词卫生自检，不花钱 |
| `--chars-per-minute` | 语速口径（字/分钟），默认 265。它**同时**决定提示词配额、时长闸门与成本报价 |

### `outline`

| 参数 | 说明 |
|---|---|
| `--topic` | 主题，一句话说清讲什么（必填） |
| `--minutes` | 目标时长（分钟），默认 30，允许 5~90 |
| `--audience` | 目标听众 |
| `--brief` | 额外要求 |

### `script`

| 参数 | 说明 |
|---|---|
| `--outline` | 提纲文件，默认 `<outdir>/outline.json` |
| `--minutes` | 覆盖目标时长（默认取提纲各章之和） |
| `--role-a` / `--role-b` | 两个角色的名字，默认「主持人」「嘉宾」 |
| `--allow-multi-role` | 放宽结构闸门，允许 3 个以上角色（默认只认双人） |

### `voice`

| 参数 | 说明 |
|---|---|
| `--script` | 对话稿（`script.json` 或 `.md`），默认 `<outdir>/script.json` |
| `--voice-a` / `--voice-b` | 两个角色的音色 `reference_id`（用 `voices` 查） |
| `--speed` | 语速（`prosody.speed`，1.0 为原速） |
| `--sample-chars` | **只配前 N 个字**（试链路省钱用；0 = 全部） |
| `--points-per-1k` | 覆盖配音单价（点/千字），默认用实测值 50 |
| `--yes` / `--budget` | 二者给其一：确认报价 / 预算封顶（点） |
| `--force` | 忽略断点全部重配（**会重复扣费**） |

### `music`

| 参数 | 说明 |
|---|---|
| `--cues` | 要生成哪些：`intro,bed,outro`（默认三个都做） |
| `--style` | 覆盖音乐风格描述（默认按档位内置） |
| `--title` | 曲目标题前缀 |
| `--with-lyrics` | 先生成歌词再谱曲（歌词 12 点/次；默认做纯器乐） |
| `--yes` / `--budget` | 同 `voice` |

### `mix`

| 参数 | 说明 |
|---|---|
| `--ffmpeg` | ffmpeg 可执行文件路径（默认找 `PATH` 与 `FFMPEG` 环境变量） |
| `--filename` | 成片文件名，默认 `episode.mp3` |
| `--intro-seconds` / `--bed-seconds` / `--outro-seconds` | 片头 / 转场 / 片尾裁剪到多少秒（默认 15 / 6 / 20） |

`music_generation/create` 的参数表里**没有时长参数**，生成多长由上游决定，
所以片头 / 转场 / 片尾的长度控制在 `mix` 阶段用 `ffmpeg -t` 做。

### 产出目录长这样

```
D:/podcast/ep01/
├── outline.json / outline.md      选题与提纲
├── script.json  / script.md       双人对话稿（成品稿，闸门读的就是它）
├── voice/                         分角色配音片段 + index.json
├── music/intro.mp3 bed.mp3 …      片头 / 转场 / 片尾配乐
├── podcast-state.json             断点文件（重跑不重复扣费；配音按「台词 + 角色」判定，改台词会重配重扣）
├── episode.mp3                    **成片**
├── chapters.txt / chapters.json   章节标记（FFmpeg metadata 格式）
├── timeline.md / playlist.txt     时间轴与拼接清单
└── .mix/                          归一化后的 wav 中间件（可整目录删掉）
```

音频一律落在**包外**的 `--outdir` 里，包内只有文本与脚本。

## 排错

### 1. 配音返回 `code=0「任务处理失败，请稍后重试」`

九成是 **`reference_id` 抄短了**。`list_voices` 返回的 `id` 是 **32 位十六进制**
（例：`0705a04a4c3f4b65b888d2aa7a4e6b08`）。用 `run.py voices` 重新**整条**复制。

判断方法：去掉 `--voice-a` / `--voice-b` 再跑一次。不指定音色会用平台默认音色，
能成功就说明是音色 ID 的问题，不是文本的问题。

### 2. `本机没有 ffmpeg，mix 降级`

`mix` 会写出 `playlist.txt`、`chapters.txt`、`mix-commands.txt`（都是文本），
**但不产出 mp3**，并以 `exit=2` 明确报错——不假装成功。
装上 ffmpeg 后**原样重跑同一条命令即可**（断点续跑：台词与配乐提示词没变就不会重复扣配音 / 配乐的钱；台词一改就要重配重扣）。

ffmpeg 不一定要在 PATH 上：`--ffmpeg <路径>` 或环境变量 `FFMPEG` 都行。

### 3. 时长闸门拦下对话稿

```
[时长] 按 265 字/分钟估，约 3.5 分钟；目标 8.0 分钟，容差 25%（6.0~10.0 分钟）
```

两种原因，处理方式不同：

- **真的是模型写少了**：重跑 `script`。提示词里已经按章给了「本章不少于 X 字、
  不少于 N 条台词」的配额（这个配额就是被这条闸门逼出来的）；还是短就换模型，
  或把 `--max-tokens` 调大。
- **语速口径不对**：你的节目语速跟 265 字/分钟差得远，用 `--chars-per-minute`
  改成自己的值，闸门与成本报价会一起跟着改。

### 4. 对话结构闸门报「只有 1 个角色」

模型写了朗读稿。检查 `--role-a` / `--role-b` 是否被改成了同一个名字；
重跑一次通常就好。真的要做单人播客，本包不提供绕过开关——
那道闸门就是这个包的立身之本。

### 5. `--outdir 指到了包内`

产出音频会让整个 Skill 包在 SkillHub 上 400（白名单只放文本类后缀）。
换到包外目录，例如 `%TEMP%\podcast` 或 `D:/podcast/ep01`。

### 6. `401 / 402 / 404`

- `401`：Key 无效或过期，重新到 https://api.a7w.cn/ 领一个。
- `402`：点数不足，充值后重试（失败任务平台会退回点数）。
- `404`：模型名不对。`deepseek-chat` 这个别名实测可用，但它**不在**
  `/api/v1/models` 的返回列表里——"列表里没有"不等于"不能用"，
  也不等于"有价格"。用 `run.py models` 现查在架名字。

### 7. 报价和实际扣费不一致

以 `usage.points_cost` 为准，本包的报价是实测常量：
配音 50 点/千字、配乐 create 65 点/次、歌词 12 点/次。
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
- 配乐参数与歌词：`POST /api/v1/apps/music_generation/create`、
  `POST /api/v1/apps/music_generation/lyrics`
- 任务查询：`GET /api/v1/tasks/<task_id>`
- 文档三份：
  - `references/podcast-script-method.md` —— 对话稿方法与时长 / 字数换算
  - `references/voice-and-music.md` —— 音色挑选、配音参数与配乐档位
  - `references/cost-and-troubleshooting.md` —— 实测单价、报价口径与排错手册

---

## 已知取舍（写在这里，免得下次又"优化"回去）

1. **文本大模型的单价本包不报**。平台 `/api/v1/models` 里没有任何价格字段，
   `/api/v1/pricing` 也不覆盖 `chat/completions`。想算文本的钱请显式给
   `cost --points-per-ktok N`——本包**不编单价**。
2. **「第一」类口径取了限定式写法**，与 `sanjianke-multiplat-rewrite` 的裸
   `第一(?!次)` 有意不同：播客是对白稿，「第一、第二」「第一步」是常态，
   裸写法一次实测就把整篇误拦了。仍然照拦的是「全国 / 行业 / 销量…第一」
   「第一品牌」「排名第一」这类**排他性宣称**。
3. **违禁词表比模板多三个词**：`省` / `划算` / `实惠`。模板词表里有「便宜」
   却没有「省」，而「最省钱的一套流程」是口播里最常见的绝对化说法。
   加词只会让闸门更严，不放松任何一处判定。
4. **无 ffmpeg 时 `mix` 以非零码退出**（`exit=2`），不返回"成功但没文件"。
   宁可让 CI 红，也不出一个"看起来跑完了"的假绿。
5. **只做双人对话**。多人对谈需要 `--allow-multi-role` 显式放宽，
   默认拦下——因为"真的有两个角色在交替说话"是这个包唯一无法自动补救的形态要求。
