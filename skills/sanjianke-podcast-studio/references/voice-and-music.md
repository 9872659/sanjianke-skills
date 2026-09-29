# 音色与配乐 · 两个端点怎么用

对应子命令 `voices` / `voice` / `music`。所有参数都以**现查 schema**为准：

```bash
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py schema music_generation
```

> **别照抄记忆**。本包开工前现查确认了两条我们自己也记错的接口事实：
> 配音的音色参数叫 **`reference_id`**（不是 `voice_id`），
> 配乐的创建动作叫 **`create`**（不是 `generate`）。

---

## 一、音色：先拿 `reference_id`

```bash
python3 scripts/run.py voices
python3 scripts/run.py voices --title-search 解说
python3 scripts/run.py voices --tag v-6d78566e9ec8 --page-size 50
```

`POST /api/v1/apps/voice_tts/list_voices`（同步，**免费**）返回的关键字段：

| 字段 | 说明 |
|---|---|
| `id` / `model_id` | **32 位十六进制**，这就是配音要的 `reference_id` |
| `title` | 音色名称 |
| `type` | `tts` |
| `state` | `trained` 才可用 |

### ⚠️ 实测踩过的坑：抄短一位就失败

```
id = 0705a04a4c3f4b65b888d2aa7a4e6b08      ← 32 位
抄成 0705a04a4c3f4b65b888d2aa7a4e          ← 28 位（列表显示截断导致的）
→ code=0  「任务处理失败，请稍后重试」
```

**排查方法**：去掉 `--voice-a` / `--voice-b` 再跑一次。不指定音色会用平台默认音色；
能成功就说明是音色 ID 的问题，不是文本的问题。
（本包第一版 `voices` 列表按 28 字符截断显示，实测时照着屏幕抄就中招了；
现在**整条打印**，并会在 TTS 返回 `任务处理失败` 时把这条排查提示打出来。）

### 克隆自己的音色

`POST /api/v1/apps/voice_tts/clone_voice`（同步），关键参数：

| 参数 | 说明 |
|---|---|
| `title` | 音色名称（必填） |
| `audio_url` | 参考音频 URL（与上传文件二选一），支持 mp3 / wav / ogg / flac |
| `texts` | 与音频对应的文本数组；不传会自动 ASR |
| `tags` | 标签数组，便于以后筛选 |
| `visibility` | `public` / `unlist` / `private`（平台默认 private） |
| `enhance_audio_quality` | 是否增强音质，默认 false |

克隆完的 `id` 同样交给 `--voice-a` / `--voice-b`。
**克隆他人声音涉及声音权益，未经许可不要做**（见 `LICENSE.md`）。

---

## 二、配音：`voice` 子命令

### 端点选择

| 端点 | 类型 | 适用 |
|---|---|---|
| `POST /api/v1/apps/voice_tts/tts` | 同步 | **建议不超过 500 字符**（schema 原文） |
| `POST /api/v1/apps/voice_tts/tts_async` | 异步 | 长文本，最大约 10000 字符 |
| `POST /api/v1/apps/voice_tts/tts_live` | 异步（WebSocket 上游） | 超长文本流式合成 |

本包默认走同步 `tts`，每块不超过 500 字（`TTS_SYNC_MAX_CHARS`）；
单块超过 5000 字才切异步。**为什么坚持切块而不是整篇丢给 `tts_async`**：
500 字一块的失败重试只损失一块，整篇丢过去失败就全丢。

### 参数表（`voice_tts/tts`，现查 schema 的原文）

| 参数 | 说明 |
|---|---|
| `text` * | 待合成文本 |
| `model` | `s1` / `s2-pro`，默认 `s2-pro` |
| `format` | `wav` / `pcm` / `mp3` / `opus`，默认 `mp3` |
| `reference_id` | **音色模型 ID**（单说话人传 string；多说话人可传 string[]，仅 s2-pro） |
| `prosody` | 语调对象：`speed`、`volume`、`normalize_loudness` |
| `normalize` | 文本规范化，默认 true |
| `mp3_bitrate` | 64 / 128 / 192 |
| `sample_rate` | 采样率（按格式限制） |
| `temperature` / `top_p` | 采样参数 |
| `chunk_length` | 文本分块长度 100~300，默认 300 |
| `max_new_tokens` / `min_chunk_length` | 分块音频 token 上限 / 下限 |
| `repetition_penalty` | 重复惩罚，默认 1.2 |
| `early_stop_threshold` | 提前停止阈值 0~1，默认 1 |
| `condition_on_previous_chunks` | 是否用前一段音频做上下文，默认 true |

命令行对应：`--voice-a` / `--voice-b` → `reference_id`；`--speed` → `prosody.speed`。

### 断点续跑

`voice` 每完成一块就把 `{hash, 字数, 角色, 文件, 扣点}` 写进
`<outdir>/podcast-state.json`。重跑时按 **`hash(text + role)`** 比对：

- 命中且文件在 → **跳过**，0 调用 0 扣费（实测 5 段全跳过、0.0 秒）
- 稿子改了 → hash 变了 → **重新配那一块**（不会拿旧音频凑）
- 想强制全部重配：`--force`（**会重复扣费**）

### 试链路省钱

```bash
python3 scripts/run.py voice --outdir D:/podcast/ep01 --sample-chars 200 --budget 30
```

`--sample-chars 200` 只配前 200 字（约 10 点 ≈ 0.1 元），用来验证
音色对不对、链路通不通，再决定要不要配整期。

---

## 三、配乐：`music` 子命令

### 端点

`POST /api/v1/apps/music_generation/create`（**异步**，自动轮询 `/api/v1/tasks/<task_id>`）。

关键参数：

| 参数 | 说明 |
|---|---|
| `type` | 操作类型。**`generate` 是这个参数的一个取值**，不是接口名 |
| `style` | 音乐风格描述，常规模型最多 200 字符 |
| `title` | 曲目标题，最多 80 字符 |
| `prompt` | 生成提示词，灵感模式不超过 500 字符 |
| `custom` | 是否启用自定义模式 |
| `lyric` | 自定义模式下的歌词，常规模型最多 3000 字符 |
| `lyric_prompt` | 自动生成歌词的提示词（`custom=true` 且 `lyric` 为空时生效） |
| `instrumental` | 纯伴奏模式（本包默认 true） |
| `vocal_gender` | `m` / `f`，只是偏好，不保证 |
| `weirdness` / `style_influence` | 创意强度 / 风格强度，0~1 |

音频二次处理还有一组：`vox`（人声处理）、`wav`（导出 WAV）、`mp3`（…见 schema）、`midi`（导出 MIDI）、
`timing`（歌词时间轴）、`mashup_lyrics`（歌词混合）、`persona`（创建歌手风格）、
`voice_clone`（声音克隆）、`upload_audio`（上传参考音频）、`query`（查任务）、`style`（优化风格）。

### 本包的三个档位

| 档位 | 用途 | 混音时裁剪到 | 内置风格 |
|---|---|---|---|
| `intro` | 片头 | 15 秒 | 轻快明亮、有推进感、无人声、中频清晰不抢话 |
| `bed` | 章节转场 | 6 秒 | 短促干净的垫乐，情绪平缓不抢注意力 |
| `outro` | 片尾 | 20 秒 | 温暖收束，尾音自然衰减 |

```bash
python3 scripts/run.py music --outdir D:/podcast/ep01                    # 三个都做 = 195 点
python3 scripts/run.py music --outdir D:/podcast/ep01 --cues intro        # 只做片头 = 65 点
python3 scripts/run.py music --outdir D:/podcast/ep01 --cues intro,outro --budget 140
python3 scripts/run.py music --outdir D:/podcast/ep01 --with-lyrics       # 先生成歌词再谱曲
```

### ⚠️ 这个接口没有时长参数

`create` 的参数表里**没有**任何时长 / 秒数字段（现查 schema 确认）。
生成多长由上游决定，所以本包把**长度控制放在 `mix` 阶段**：

```bash
python3 scripts/run.py mix --outdir D:/podcast/ep01 \
        --intro-seconds 12 --bed-seconds 5 --outro-seconds 25
```

`mix` 会用 `ffmpeg -t` 把每段音乐裁到指定秒数；如果某段本来就更短，
就按它真实的长度用（时间轴里如实记）。

### 歌词（可选，12 点/次）

`POST /api/v1/apps/music_generation/lyrics`（同步）。
`--with-lyrics` 会先出歌词，再以 `custom=true` + `lyric` 谱曲
（此时 `instrumental` 自动关掉）。

### 断点续跑

同配音：按 `hash(style + prompt + with_lyrics)` 比对，命中就跳过，0 扣费。
换了 `--style` 就会重做那一个档位。

---

## 四、混音：`mix` 子命令（本地，零网络零成本）

### 顺序

```
片头 → 第 1 章人声 → 转场 → 第 2 章人声 → 转场 → … → 片尾
```

转场只在**章与章之间**插，同一章内的角色切换不插。

### 为什么时长从 wav 文件头算，而不是用 ffprobe

本机实测环境里**只有 `ffmpeg`、没有 `ffprobe`**（ffprobe 是另一个可执行文件）。
所以混合分两步：

1. 每段先解码成**参数完全一致**的 wav（mono / 44100 / 16bit）
   → 时长 = `data 块字节数 ÷ (采样率 × 声道 × 位宽/8)`，**是精确值不是估算**
2. 用 concat 解复用器拼起来编成 mp3，并把章节元数据一起 remux 进去

只读文件头那几十个字节，不把几十 MB 的 wav 读进内存。

### 产出

| 文件 | 内容 |
|---|---|
| `episode.mp3` | 成片 |
| `chapters.txt` | FFmpeg metadata 格式的章节标记（`-map_metadata 1` 已写进 mp3） |
| `chapters.json` | 章节（按章聚合）+ 逐段轨道 |
| `timeline.md` | 人读时间轴：起点 / 终点 / 时长 / 内容 / 类型 |
| `playlist.txt` | 拼接清单 |
| `.mix/` | 归一化后的 wav 中间件（可整目录删掉） |

**章节标记按"章"聚合，不是按段。** 实测初版按段生成，
一期 30 分钟的节目会得到几十条章节标记，播放器里的章节列表就废了。

### 缺 ffmpeg

写出 `playlist.txt` / `chapters.txt` / `mix-commands.txt`（都是文本），
**不产出 mp3**，并以 `exit=2` 明确报错。装上 ffmpeg 后原样重跑即可
（断点续跑，不会重复扣配音 / 配乐的钱）。

ffmpeg 不一定要在 PATH 上：`--ffmpeg <路径>` 或环境变量 `FFMPEG` 都行。

> 实测环境备注：同一台机器上，某个 82 MB 的 ffmpeg 构建在 `%TEMP%` 下写文件会
> `Permission denied`，而另外几个构建正常。遇到 `Error opening output ... Permission denied`
> 时，先换成系统里另一个 ffmpeg 构建试试，别怀疑磁盘权限。
