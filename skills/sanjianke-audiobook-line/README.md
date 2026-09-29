# 三剪客 · 有声书生产线

给一本**小说或长文本**，一条链路产出一本**能听的有声书**：

```
split   →   cast    →   voice   →   subtitle  →   join
章节切分    对白/旁白    分角色      字级时间戳    章节清单 +
（纯本地）   分配音色     逐章配音     SRT / VTT    时长台账
```

面向有声书、听书号、播客改编。**跑之前先告诉你花多少钱**，配错了包不给你发出去。

```
split     →  章节切分（纯本地，零调用）
cast      →  识别对白 / 旁白并分配音色（默认本地正则，零成本）
voices    →  现查可用音色，拿配音要的 reference_id（免费）
voice     →  逐章分角色配音，先报价，断点续跑
subtitle  →  字级时间戳出 SRT / VTT（voice_tts/stt）
join      →  章节拼接 + 章节清单与时长台账（纯本地）
all       →  串起全流程，断点续跑
cost      →  只算钱，一次调用都不发
models    →  列出在架模型
```

## 30 秒上手

```bash
# 1) 拿 Key（新用户有赠送点数）
#    到 https://api.a7w.cn/ 注册，创建一个 API Key

# 2) 配 Key
export A7W_API_KEY="<你的Key>"          # Windows: $env:A7W_API_KEY="<你的Key>"

# 3) 章节切分（纯本地，先看切得对不对，不花钱）
python3 scripts/run.py split --text novel.txt --outdir D:/book/b01

# 4) 角色分配（默认纯本地；先看音色）
python3 scripts/run.py voices
python3 scripts/run.py cast --outdir D:/book/b01 --voice-pool 6

# 5) 配音：先不带 --yes 报价，确认了再加（先拿 300 字试链路）
python3 scripts/run.py voice --outdir D:/book/b01 --sample-chars 300 --yes

# 6) 字级时间戳字幕
python3 scripts/run.py subtitle --outdir D:/book/b01 --yes

# 7) 章节拼接 + 章节清单
python3 scripts/run.py join --outdir D:/book/b01 --title "旧城拾光"

# 8) 想一条命令跑完
python3 scripts/run.py all --text novel.txt --outdir D:/book/b01 --budget 3000
```

**零依赖**：只要 Python 3.7+，不用 `pip install` 任何东西。
`join` 有 `ffmpeg` 更好；没有的话它会用**标准库**把 PCM wav 逐块拼起来，
如果是 mp3 就**明确报降级**、不假装成功（见「没有 ffmpeg 时会怎样」）。

`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端（我们靠 SHA256 校验各包副本
是否一致），本包**逐字节没有改它**；本包的业务逻辑全在 `scripts/run.py` 里。

## 能做什么

| 子命令 | 做什么 | 花不花钱 | 产出 |
|---|---|---|---|
| `split` | 章节切分 | **纯本地，零调用** | `chapters.json` + `chapters.md` |
| `cast` | 识别对白 / 旁白 + 分配音色 | 本地零成本；`--llm` 才逐章一次文本调用 | `cast.json` + `cast.md` |
| `voice` | 逐章配音（旁白 + 对白多音色） | **先报价**，按千字计费 | `voice/*.mp3` + `voice/index.json` |
| `subtitle` | 字级时间戳出 SRT / VTT | **先报价**，按次计费 | `subtitle/*.srt` + `*.vtt` + `book.srt` |
| `join` | 章节拼接 + 章节清单与时长台账 | **纯本地，零调用** | `book.mp3`（或 `book.wav`）+ `playlist.txt` |
| `all` | 串起来跑完整条链路 | 先报价，**断点续跑** | 上面全部 |
| `cost` | 只算钱 | 零网络零成本 | 成本表 |
| `models` | 现查在架模型 | 免费 | 模型清单 |
| `voices` | 现查可用音色（拿 `reference_id`） | 免费 | 音色清单 |

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 配音 **50 点/千字**（实测）、字幕 **40 点/次**（实测，与文本长度无关）；1 元 = 100 点。中篇 20 万字 ≈ **116 元** |
| 要装什么 | **什么都不用装**。只用 Python 标准库；`join` 有 ffmpeg 更好（没有也能拼 wav，见下） |
| 中断了怎么办 | **断点续跑**（实测 12 段全跳过、**0 次调用、0 点**）；**但断点 key 含十一维**——改了正文 / 音色 / 模型 / 格式 / 语速 / 采样率 / 比特率里任何一项都会重配重扣 |
| 会瞎编吗 | `--llm` 模式下模型只被允许"切段 + 标角色"，返回内容与原文**逐字不一致就直接报错** |
| 说话人识别不准怎么办 | 本地正则搞不定的归到「旁白」并登记数量；要更准加 `--llm` |

## 怎么用（命令行）

```bash
# 配 Key（三种方式任选）
export A7W_API_KEY="<你的Key>"            # Windows: $env:A7W_API_KEY="<你的Key>"
#   或者 --key <你的Key>，或者 python3 scripts/a7w.py login --key <你的Key>

# 章节切分（纯本地）：先用它确认切得对不对，再花钱
python3 scripts/run.py split --text novel.txt --outdir D:/book/b01
python3 scripts/run.py split --text novel.txt --outdir D:/book/b01 \
        --heading-pattern "^第[0-9]+话"

# 角色分配：默认本地零成本；--llm 更准但每章一次文本调用
python3 scripts/run.py cast --outdir D:/book/b01 --voice-pool 6
python3 scripts/run.py cast --outdir D:/book/b01 --limit 3 --llm     # 只用前 3 章试

# 配音：先报价，确认了再加 --yes（或用 --budget 封顶）
python3 scripts/run.py voice --outdir D:/book/b01
python3 scripts/run.py voice --outdir D:/book/b01 --yes --budget 3000
python3 scripts/run.py voice --outdir D:/book/b01 \
        --voice-map "林砚=<音色ID>,老人=<音色ID>" --narrator-voice <旁白ID>

# 字级时间戳字幕（SRT + VTT）
python3 scripts/run.py subtitle --outdir D:/book/b01 --yes

# 章节拼接 + 章节清单与时长台账
python3 scripts/run.py join --outdir D:/book/b01 --title "旧城拾光"
python3 scripts/run.py join --outdir D:/book/b01 --ffmpeg "C:/ffmpeg/bin/ffmpeg.exe"

# 整条链路（断点续跑，中断了原样重跑即可）
python3 scripts/run.py all --text novel.txt --outdir D:/book/b01 --budget 3000

# 只算钱，一次调用都不发
python3 scripts/run.py cost --chars 200000 --chapters 40
```

真实端点（都在 api.a7w.cn 上）：

| 用途 | 端点 |
|---|---|
| 大模型（`cast --llm`） | `POST /api/v1/chat/completions` |
| 模型清单 | `GET /api/v1/models` |
| 配音（同步，≤500 字） | `POST /api/v1/apps/voice_tts/tts` |
| 配音（异步，长文本） | `POST /api/v1/apps/voice_tts/tts_async` |
| 音色列表 | `POST /api/v1/apps/voice_tts/list_voices` |
| **字级时间戳** | `POST /api/v1/apps/voice_tts/stt` |
| 任务轮询 | `GET /api/v1/tasks/<task_id>` |

**开工前先现查一遍 schema，别照抄记忆**：

```bash
python3 scripts/a7w.py schema voice_tts
```

三条实测确认的接口事实（本包就是踩过才写下来的）：

1. **配音的音色参数叫 `reference_id`，不叫 `voice_id`**。值是 `list_voices` 返回的
   `id` / `model_id`，**32 位十六进制，抄短一位就得到「任务处理失败」**。
   语速是 `prosody.speed`（**对象**），格式参数叫 `format`。
2. **同步配音接口 schema 原文「建议不超过 500 字符」**。所以逐块按 500 字硬上限拆；
   单块超过 5000 字才切 `tts_async`。最"看不出来"的失败就是被上游悄悄截断——
   音频少一句但没有任何报错。
3. **字级时间戳来自 `voice_tts/stt` 的 `ignore_timestamps: false`**。
   平台默认 `true`，那一档 `result.segments` 是**空数组**。显式传 `false` 后，
   中文实测**一字一段**：`[{"text":"旧","start":0.08,"end":0.16}, ...]`。

另外两条平台口径：

- `/chat/completions` 的**成功响应不带 `code`**；生成应用**`code == 1` 才是成功**。
- 异步任务的 **`status` 在任务 `data` 顶层**，不在 `data.result` 里（平台文档写错了）。

## 七道硬闸门

命中即**标红 + stderr 汇总 + 退出码非 0**，可以直接进 CI。

| # | 闸门 | 判定 | 退出码 |
|---|---|---|---|
| 1 | 合规 | 广告法违禁词 + 音频口播红线；「最X」按可枚举语境豁免 | 3 |
| 2 | 占位符残留 | `{}`、`[待填]`、`XXX`、`此处省略`、`TODO` | 3 |
| 3 | prompt_echo | 去标点相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60 | 3 |
| 4 | **章节结构** | **章数为 0 或存在空章 → 拦**；空标题、超长标题也拦 | 3 |
| 5 | **角色一致性** | 同一角色全书**同一音色**；分配了没用到的角色也拦 | 3 |
| 6 | 成本上限 | 跑前必须报价 + `--yes` 或 `--budget` | 2 / 5 |
| 7 | 产出位置 | `--outdir` 指到包内直接 `exit=2` | 2 |

`--outdir` 落包内直接 `exit=2`（包内不许出现音频，SkillHub 的扩展名白名单只放
`.md .py .txt .json .sh .js .yaml .yml .csv`）。

### 第 4、5 道闸门为什么是本包最值钱的两道

一份**切不出章节**的长文本：字数对、时长对、合规干净、读起来也顺——
它在任何一道常规检查里都是合格的，但它配出来只是一条几小时的音频，**没法上架**。
同理，**空章**（有目录没正文）听出来就是一段静音，平台直接判残包。

一份**角色音色乱掉**的稿子：声音好听、内容对、时长对——但它会让听众立刻跳戏，
而且音色一换就必须重配，**重配就是重扣费**。所以它在配音**之前**就过闸门
（零成本本地校验），而不是等配完几千个片段才发现。

两道闸门都**不采信内存里的对象**，而是拿正则去读**渲染后的成品 Markdown**：

```
## 第 1 章　雨夜的书店
```

读不出章节标题、某一章正文为空、或某个角色出现两个音色，一律拦。

## 参数说明

### 通用

| 参数 | 说明 |
|---|---|
| `--outdir` | 产出目录。**不许指到包内**，默认 `./audiobook-out` |
| `--json` | JSON 输出，写在子命令**前后都可以**；失败走 `{"ok":false,"exit":N,"error":{...}}` |
| `--key` | 临时指定 API Key（也可用 `A7W_API_KEY` 或 `~/.a7w/config.json`） |
| `--chars-per-minute` | 语速口径（字/分钟），默认 250。**同时**影响成本报价、时长估算、join 兜底时长 |
| `--out` | 把结果写到指定文件 |

### split

| 参数 | 说明 |
|---|---|
| `--text` | **必填**。小说 / 长文本；UTF-8 / GBK / Big5 / UTF-16 自动识别 |
| `--heading-pattern` | 自定义章节标题正则，覆盖内置的 5 套 |
| `--chunk-blocks` | 没识别到标题时按空行分块（**不是**按作者章节切，产出里会登记） |
| `--minutes` | 目标总时长，只用于时长估算 |

内置 5 套标题形态（都**行首锚定**）：`第N章`（含回/节/卷/部/篇/话/集）、
`Chapter N`、`1. 标题`、`卷X / 上部`、`楔子 / 序章 / 尾声 / 番外 / 大结局`。

### cast

| 参数 | 说明 |
|---|---|
| `--chapters` | 章节文件，默认 `<outdir>/chapters.json`（也认 `.md`） |
| `--limit N` | 只处理前 N 章（**省钱预演用**） |
| `--llm` | 用大模型逐章切段与标注（每章一次文本调用） |
| `--no-fetch-voices` | 只切分，不拉音色池（纯离线，零调用） |
| `--voice-pool N` | 自动取用多少个音色，默认 6 |
| `--narrator-voice` | 旁白音色 `reference_id` |
| `--voice-map` | `"主角=<reference_id>,配角=<reference_id>"` |

### voice

| 参数 | 说明 |
|---|---|
| `--cast` | 角色分配文件，默认 `<outdir>/cast.json` |
| `--chapters` | 只配这些章（逗号分隔，例如 `1,2`） |
| `--format` | `mp3` / `wav` / `pcm` / `opus`，默认 `mp3` |
| `--tts-model` | `s1` / `s2-pro`，默认 `s2-pro` |
| `--speed` / `--sample-rate` / `--mp3-bitrate` | 语速 / 采样率 / MP3 比特率 |
| `--sample-chars N` | **只配前 N 个字**（试链路省钱用；0 = 全部） |
| `--points-per-1k` | 覆盖配音单价，默认用实测值 50 |
| `--force` | 忽略断点全部重配（**会重复扣费**） |
| `--yes` / `--budget` | 确认报价 / 预算封顶，二者给其一 |

### subtitle

| 参数 | 说明 |
|---|---|
| `--voice-index` | 配音台账，默认 `<outdir>/voice/index.json` |
| `--limit N` | 只处理前 N 个片段（**省钱预演用**） |
| `--chars-per-line` / `--max-seconds` | 一条字幕最多几个字（默认 16）/ 最多停留几秒（默认 8） |
| `--points-per-call` | 覆盖字幕单价，默认用实测值 40 |

### join

| 参数 | 说明 |
|---|---|
| `--chapters` | 只拼这些章（逗号分隔） |
| `--ffmpeg` | ffmpeg 路径（默认找 PATH 与 `FFMPEG` 环境变量） |
| `--filename` | 合并音频文件名，默认 `book.mp3`（无 ffmpeg 且是 wav 时 `book.wav`） |
| `--title` | 书名（写进清单） |

### all / cost / voices / models

`all` 是各子命令参数的并集，额外有 `--skip-subtitle`（只出章节音频）。
`cost` 有 `--chars` / `--minutes` / `--chapters` 与三个单价覆盖
（`--points-per-1k` / `--points-per-call` / `--points-per-ktok`）。
`voices` 有 `--tag` / `--title-search` / `--language` / `--page-size`。
`models` 有 `--type`（默认 `text`，传 `all` 看全部）。

## 断点 key 含哪些维度（**这一节最该看**）

断点 key 少一维的后果**不是报错**，而是「用户以为改了、其实静默复用了旧音频」。

同族包已实测踩过三种形态：提示词截断到 24 字（改第 25 字之后 key 没变）、
`resolution` 不入 key（从 1K 改到 4K 拿回的还是 1K）、死参数
（参数在命令行存在、在 key 里不存在）。

本包把音频断点 key 做成**显式白名单**，共十一维：

| 维度 | 为什么必须进 key |
|---|---|
| `text` | 正文全文（**不截断**，整段入 hash） |
| `role` | 换角色 = 换音色 = 必须重配 |
| `reference_id` | 音色本身；空字符串（平台默认音色）与指定了音色是两回事 |
| `model` | `s1` / `s2-pro` 音色表现不同 |
| `format` | `mp3` / `wav` / `pcm` / `opus`：拿 wav 的脚本拿到 mp3 会静默出错 |
| `speed` | `prosody.speed` |
| `sample_rate` | 采样率 |
| `mp3_bitrate` | MP3 比特率 |
| `endpoint` | `tts` / `tts_async`：上游不同实现，产物不同 |
| `chapter` | 归属章节，决定 `join` 的拼接顺序 |
| `part` | 同章同角色被 500 字上限拆开后的第几块 |

字幕断点 key 六维：`audio_sig` / `language` / `ignore_timestamps` /
`chars_per_line` / `max_seconds` / `endpoint`。

**实测（13 组改动逐一验证）：改任何一维，`sig` 都变。**

## 产出目录长这样

```
D:/book/b01/
├── chapters.json / chapters.md     章节切分结果（闸门读的是 chapters.md）
├── cast.json     / cast.md         角色与音色分配 + 逐片段角色标注
├── voice/                          逐片段音频 + index.json（含 audio_url，字幕要用）
├── subtitle/                       book.srt / book.vtt + 逐片段 srt/vtt + subtitle.json
├── audiobook-state.json            断点文件 + 成本台账（cost.items 可逐笔核对）
├── book.mp3（有 ffmpeg）或 book.wav（无 ffmpeg 且 wav 输出）
├── chapters.json / chapters.md     合并后的章节清单与时长台账
└── playlist.txt                    播放清单（起点 / 章号 / 时长 / 角色）
```

音频与字幕一律落在**包外**的 `--outdir` 里。

## 没有 ffmpeg 时会怎样

| 情况 | 行为 |
|---|---|
| 有 ffmpeg | 按章节顺序拼成一条 **mp3** + ffmpeg metadata 章节标记 |
| 无 ffmpeg，音频是 **wav / pcm** | **纯标准库**逐块接起来并重建 RIFF 头，产出真 `book.wav` |
| 无 ffmpeg，音频是 **mp3** | mp3 不能靠拼字节接起来 → 写出章节清单与播放清单，**明确报降级**（`exit=2`），不假装成功 |

第三种情况下装上 ffmpeg 后**原样重跑同一条命令即可**——断点续跑，
不会重复扣配音与字幕的钱。

wav 逐块拼接前会校验**参数一致性**（采样率 / 声道 / 位宽）；不一致直接拒绝，
因为硬拼会得到一条变速或变调的音频，那种错误听起来像"设备有问题"，很难查。

## 时长台账的三个来源

| 优先级 | 来源 | 精度 |
|---|---|---|
| 1 | `stt` 的字级时间戳（`result.duration`） | 精确 |
| 2 | wav 文件头（自己解析 RIFF，不依赖 ffprobe） | 精确 |
| 3 | 字数估算 | **估算**，会在产出里逐章标注 |

只有 1、2 都拿不到时才退回 3，并在 `chapters.json` 的 `basis` 字段里
明确写出「字数估算（**不是真实时长**）」，不静默估算。

## 真机实测（跑出来的，不是估算）

| 项目 | 实测值 |
|---|---|
| 章节切分（2 章 198 字短篇） | 2 章、15 个片段（6 对白 + 9 旁白），方式「标题识别（第N章）」 |
| 角色分配（本地正则） | 3 个角色 → 3 个音色；2 段推不出说话人，归旁白并登记 |
| 配音单价 | **50 点/千字**，报价与实际**逐片段完全一致** |
| 配音样本 | 145 字 / 12 个片段 = **7.25 点**（≈ 0.0725 元） |
| 字幕单价 | **40 点/次**，与文本长度无关 |
| 字幕样本 | 2 个片段 = **80 点**（≈ 0.80 元）；14 个汉字 → **14 个 segment** 的一字一段时间戳 |
| 断点续跑 | 12 段全部跳过，**0 次调用、0 点** |
| 断点 key | 13 组改动逐一验证，全部换 key（无一维静默复用） |
| 本地 wav 拼接 | 3 段 22050Hz/mono/16bit → 1 个 132,344 字节、3.0 秒的合法 wav |
| 全链路试跑花费 | 配音 7.25 点 + 字幕 80 点 = **87.25 点 ≈ 0.87 元** |
| 中篇 20 万字口径 | 10000 点配音 + 字幕 ≈ **116 元** |

结算只认 `usage.points_cost`。平台的 `pricing_matrix` / `tenant_*` 字段半数不可信，
本包不拿它们算钱；文本大模型的单价平台不公开，`cost` 不给 `--points-per-ktok`
就**只报 token 数、不报金额**——不编单价。

## 三条实测确认的接口事实

```bash
python3 scripts/a7w.py schema voice_tts      # 配音 / 语音识别的真实参数
```

1. **配音的音色参数叫 `reference_id`，不叫 `voice_id`**。32 位十六进制，
   抄短一位就得到「任务处理失败」。语速是 `prosody.speed`（对象），
   格式参数叫 `format`（不是 `audio_format`）。
2. **同步配音接口的建议上限是 500 字符**（schema 原文）。所以按 500 字硬上限拆块；
   单块超过 5000 字才切 `tts_async`。被上游悄悄截断的音频少一句但看不出来，
   这是最坏的一种失败。
3. **字级时间戳来自 `voice_tts/stt` 的 `ignore_timestamps: false`**。
   平台默认 `true`，那一档 `result.segments` 是**空数组**。
   显式传 `false` 后中文实测**一字一段**，正好是出 SRT / VTT 要的粒度。
   ⚠️ 回读文字与原文**不保证逐字一致**（属上游能力边界），
   所以字幕默认用 ASR 回读文字（它与时间戳对齐），差异登记在 `subtitle.json`。

## 排错

| 现象 | 原因与解法 |
|---|---|
| `code=0 任务处理失败`（配音） | **`reference_id` 不完整或不存在**。用 `run.py voices` 整条复制。去掉 `--narrator-voice` 可区分是音色问题还是文本问题 |
| `stt 没有返回字级时间戳` | `ignore_timestamps` 没传 `False`（平台默认 `true`）。本包已固定传 `False` |
| `有 N 段引号里的话推不出说话人` | 本地启发式的能力边界。加 `--llm`；或给 `--voice-map` 手工指派 |
| `拒绝执行：--outdir 指到了包内` | 产出音频不许进包。换 `%TEMP%\audiobook` 或 `D:/book/b01` |
| `报价 X 点已超过 --budget` | 钱还没花就中止了。核对 `--chars-per-minute` 或提高预算 |
| `跑前必须报价并确认` | 加 `--yes`，或用 `--budget N` 封顶 |
| `有 1 章正文为空` | 切分把正文吞进标题行了，或那一章确实是空的。看 `chapters.md` 手工修 |
| `角色音色不一致` | 同一角色用了不同 `reference_id`。用 `--voice-map` 统一——**不修就会重配重扣** |
| 重跑又扣了一次钱 | 断点 key 含十一维。改了正文 / 音色 / 格式 / 语速 / 采样率 / 比特率任何一项都会重配。先用 `cost` 核价，或看 `audiobook-state.json` 的 `cost.items` |
| `本机没有 ffmpeg，音频是 mp3` | 装上 ffmpeg 后原样重跑；或 `--format wav` 重配（**会重扣费**）后走标准库拼接 |
| `读不出这个文本文件的编码` | 试过 utf-8 / gb18030 / big5 / utf-16。先用编辑器转成 UTF-8 |
| 时长台账标了「字数估算」 | 该片段既没字幕时间戳、也不是可解析 wav。跑 `subtitle` 可拿到精确时长 |
| 字幕文字和原文差几个字 | ASR 回读误差（专有名词尤其明显），属上游能力边界。逐条差异在 `subtitle.json` 的 `text_mismatch` |

## 文档

| 文件 | 内容 |
|---|---|
| `references/audiobook-narration-method.md` | 有声书演播方法：章节切分、角色分配、多音色演播、字幕排版 |
| `references/voice-and-format.md` | 音色挑选、配音参数（`reference_id` / `prosody` / 格式）与字级时间戳 |
| `references/cost-and-troubleshooting.md` | 实测单价、报价口径、断点 key 维度与排错手册 |

## 许可证

MIT，见 `LICENSE.md`。

---

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
