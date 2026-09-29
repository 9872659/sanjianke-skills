# 音色与格式（`reference_id` / `prosody` / 字级时间戳）

这份文档讲**接口层的事实**：配音与语音识别的真实参数名、取值、
以及本包实测确认过的行为。命令与参数见 `SKILL.md`。

> **开工前先现查一遍**，别照抄这份文档、更别照抄记忆：
>
> ```bash
> python3 scripts/a7w.py schema voice_tts
> ```
>
> 平台会改接口。本包的所有参数名都是**当天现查**确认的，
> 你读这份文档时也应该再查一次。

---

## 一、配音：`POST /api/v1/apps/voice_tts/tts`（同步）

### 1.1 参数（schema 现查原文）

| 参数 | 类型 | 说明 |
|---|---|---|
| `text` | string | **必填**。待合成文本，同步接口**建议不超过 500 字符** |
| `model` | string | TTS 模型：`s1` / `s2-pro`，**默认 `s2-pro`** |
| `format` | string | 输出格式：`wav` / `pcm` / `mp3` / `opus`，**默认 `mp3`** |
| `reference_id` | string | **音色模型 ID**。单说话人传 string；多说话人可传 `string[]`（仅 s2-pro） |
| `prosody` | object | 语调控制对象：`speed`、`volume`、`normalize_loudness` |
| `top_p` | number | Top-P 采样，0~1，默认 0.7 |
| `temperature` | number | 生成温度，0~1，默认 0.7 |
| `normalize` | boolean | 文本规范化，默认 true |
| `mp3_bitrate` | integer | MP3 比特率：64 / 128 / 192 |
| `sample_rate` | integer | 采样率，**按格式限制** |
| `latency` | string | 延迟模式：`low` / `normal` / `balanced` |
| `chunk_length` | integer | 文本分块长度，100~300，默认 300 |
| `opus_bitrate` | integer | Opus 比特率：-1000 / 24 / 32 / 48 / 64 |
| `max_new_tokens` | integer | 每个分块最多生成音频 token，默认 1024 |
| `min_chunk_length` | integer | 最小分块长度，0~100，默认 50 |
| `repetition_penalty` | number | 重复惩罚，默认 1.2 |
| `early_stop_threshold` | number | 提前停止阈值，0~1，默认 1 |
| `condition_on_previous_chunks` | boolean | 是否利用前一段音频作为上下文，默认 true |

### 1.2 三个最容易踩错的点

**① 音色参数叫 `reference_id`，不叫 `voice_id`。**
少一个字就是 400，或者更糟——上游忽略这个参数、用了默认音色，
产出照常返回、听感却完全不对。取值是 `list_voices` 返回的
`id` / `model_id`，**32 位十六进制**：

```
0705a04a4c3f4b65b888d2aa7a4e6b08
```

抄短一位、少一位、混一个字符，都会得到 `code=0 任务处理失败`。
所以本包的 `voices` 命令**整条打印 ID，绝不截断**——
同族包第一版按 28 字符截断显示了，照屏幕抄的结果就是任务失败。

**② 语速是 `prosody.speed`（对象），不是顶层 `speed`。**
写成顶层 `speed` 不会报错，只会**静默不生效**——
用户以为调快了，拿到的是原速音频。

```json
{"text": "...", "prosody": {"speed": 1.15}}
```

**③ 格式参数叫 `format`，不是 `audio_format`。**
取值 `wav` / `pcm` / `mp3` / `opus`。

### 1.3 500 字符：那条"看不出来"的上限

schema 原文写的是「同步接口**建议**不超过 500 字符」。
"建议"两个字很危险——超了之后上游可能截断、也可能报错，
而**截断是最坏的一种失败**：音频少了一句，文件正常、返回正常、
扣费正常，你的耳朵也不一定听得出少了一句。

所以本包的处理是**按 500 字硬上限拆块**：

```python
TTS_SYNC_MAX_CHARS = 500
```

拆法在 `split_long_text()`：按句末标点（。！？；和换行）切，
块与块之间**不会把一句话切开**；只有单句本身就超过 500 字时才硬切。

超过 5000 字的单块才切异步端点：

```python
TTS_ASYNC_MIN_CHARS = 5000
```

`tts_async` 的 schema 原文是「适合长文本（最大约 10000 字符）」。
异步走任务模式：

```
POST /api/v1/apps/voice_tts/tts_async   →  {"task_id": "..."}
GET  /api/v1/tasks/<task_id>            →  轮询到 data.status == "completed"
```

⚠️ **`status` 在任务 `data` 顶层，不在 `data.result` 里**。
平台文档把这一条写错了。客户端读的是 `data.status`，实测正确。

### 1.4 三个端点怎么选

| 场景 | 端点 | 本包的自动判据 |
|---|---|---|
| 短文本（一个片段） | `tts`（同步） | 默认 |
| 单块 > 5000 字 | `tts_async` | `len(text) > 5000` |
| 长文本流式、要低延迟 | `tts_live`（异步） | 本包**没用**（`tts` + 拆块已够，且 `tts_live` 走 WebSocket 流式上游） |

---

## 二、字级时间戳：`POST /api/v1/apps/voice_tts/stt`

### 2.1 参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `audio_url` | string | 音频文件 URL（与文件上传二选一） |
| `language` | string | 识别语言，不传则自动检测 |
| `ignore_timestamps` | boolean | **是否忽略精确时间戳，默认 true** |

### 2.2 关键事实：默认那一档没有时间戳

这是本包**最重要的一个实测发现**。

`ignore_timestamps` 的默认值是 `true`，那一档返回的 `result.segments`
是**空数组**，只有整段文本：

```json
{"result": {"duration": 2.795, "language": "Chinese", "language_code": "zh",
            "segments": [], "text": "这是一次字级时间戳的探针测试。"},
 "usage": {"points_cost": 40, "actual_points": 40}}
```

显式传 `ignore_timestamps: false` 之后，中文实测**一字一段**：

```json
{"result": {
   "duration": 2.795125,
   "language": "Chinese", "language_code": "zh",
   "segments": [
     {"text": "这", "start": 0.08, "end": 0.16},
     {"text": "是", "start": 0.16, "end": 0.32},
     {"text": "一", "start": 0.32, "end": 0.40},
     {"text": "次", "start": 0.40, "end": 0.64},
     {"text": "自", "start": 0.64, "end": 0.88},
     {"text": "己", "start": 0.88, "end": 1.04},
     {"text": "时", "start": 1.04, "end": 1.20},
     {"text": "间", "start": 1.20, "end": 1.36},
     {"text": "戳", "start": 1.36, "end": 1.60},
     {"text": "的", "start": 1.60, "end": 1.68},
     {"text": "探", "start": 1.68, "end": 1.92},
     {"text": "针", "start": 1.92, "end": 2.08},
     {"text": "测", "start": 2.08, "end": 2.32},
     {"text": "试", "start": 2.32, "end": 2.48}],
   "text": "这是一次字级时间戳的探针测试。"},
 "usage": {"points_cost": 40, "actual_points": 40}}
```

**14 个汉字 → 14 个 segment**。这就是出 SRT / VTT 要的粒度。

### 2.3 计费：按次，与文本长度无关

实测 `usage.points_cost = 40`，两次调用都是 40（一次 2.795 秒的音频，
内容长短不影响）。所以：

| 策略 | 效果 |
|---|---|
| 逐片段调 `stt` | 片段数 × 40 点。片段已经被"同章同角色合并"，所以这个数已经压小了 |
| 把整章拼成一个音频再调 | 章数 × 40 点，省一次数倍的钱——但需要先拼音频（ffmpeg），且断点粒度变粗 |

本包取第一种（逐片段），因为：**断点续跑粒度细**、
**不需要先拼音频**、**逐片段的时间轴与章节台账天然同源**。
要省这笔钱就把 `--format wav` + 有 ffmpeg 时先 `join` 拼章节，
再对章节音频调 `stt`（这一步本包没做，需要你自己脚本化）。

### 2.4 回读文字不保证与原文逐字一致

上例里，原始文本是「这是一次**字**级时间戳的探针测试」，
回读成了「这是一次**自己**时间戳的探针测试」——**错了一个词**。这是 ASR 本身的能力边界（同音字、专有名词尤其明显），不是本包的 bug。

本包的处理：字幕**默认用回读文字**（它与时间戳同源对齐），
差异逐条登记在 `subtitle.json` 的 `text_mismatch` 里。
详见 `audiobook-narration-method.md` 的「字幕排版」一节。

### 2.5 `audio_url` 从哪来

必须是**公网可访问**地址。本包的做法：

1. `voice` 调 `tts` 拿到的 `result.audio_url` 是公网地址
2. `voice` 把它连同本地文件路径一起**记进 `voice/index.json`**
3. `subtitle` 直接读这个 URL，**不用把本地文件再传一遍**

少一跳、少一次上传失败的可能。如果你的 `index.json` 里没有 `url` 字段
（比如是手工造的台账），`subtitle` 会明确报错并告诉你重跑 `voice`
（**断点续跑会跳过已配好的片段，不会重复扣费**）。

---

## 三、音色列表：`POST /api/v1/apps/voice_tts/list_voices`

同步、免费、不扣点。

| 参数 | 说明 |
|---|---|
| `tag` | 按标签筛选 |
| `title` | 按音色名称搜索 |
| `sort_by` | 排序：`score` / `task_count` / `created_at` |
| `language` | 按语言筛选 |
| `title_language` | 按标题语言筛选 |
| `page_size` | 每页数量，**官方默认 10** |
| `page_number` | 页码，默认 1 |

返回结构（实测）：

```json
{"total": 23,
 "items": [{"id": "0705a04a4c3f4b65b888d2aa7a4e6b08",
            "model_id": "0705a04a4c3f4b65b888d2aa7a4e6b08",
            "title": "杰", "type": "tts", "state": "trained",
            "created_at": "2026-09-27T06:17:41.761228Z"}],
 "page_size": 5, "page_number": 1}
```

取 `reference_id` 的优先顺序（上游字段名给过三种）：
`reference_id` → `model_id` → `id`。
**每一项都要能整条拿到**，因为这是列表里唯一要"抄下来用"的字段。

注意 `page_size` 的**官方默认是 10**，本包默认给 20——
一本多角色的书，10 个音色往往不够选。

---

## 四、格式选择：mp3 / wav / pcm / opus

| 格式 | 适合 | 注意事项 |
|---|---|---|
| `mp3`（默认） | 直接分发、体积小 | **压缩格式，不能靠拼字节接起来**——`join` 时需要 ffmpeg |
| `wav` | 后期处理、需要无损拼接 | 体积大（一本 20 万字的书可能几个 GB）；但**无 ffmpeg 也能用标准库拼** |
| `pcm` | 二次处理管线 | 没有容器头，通用播放器打不开 |
| `opus` | 流媒体、低码率 | 兼容性不如 mp3 |

**一个实务建议**：如果本机没有 ffmpeg，用 `--format wav`。
本包的 `join` 检测到「无 ffmpeg + 全是 wav」时会走**纯标准库**的
PCM 逐块拼接（重建 RIFF 头），能真的产出一条 `book.wav`。

⚠️ 但 `--format` 是**断点 key 的一维**：从 mp3 改成 wav 会**重配重扣**。
所以格式最好在**第一次配音之前**就定下来。

### 4.1 采样率与比特率

| 参数 | 取值 | 影响 |
|---|---|---|
| `sample_rate` | 按格式限制 | 进断点 key |
| `mp3_bitrate` | 64 / 128 / 192 | 只在 `format=mp3` 时有意义；进断点 key |
| `opus_bitrate` | -1000 / 24 / 32 / 48 / 64 | 只在 `format=opus` 时有意义；**本包未封装** |

有声书建议 `mp3` + `128k`（体积与音质平衡点），
或 `wav` + 22050Hz/mono（够用且体积可控）。

---

## 五、`clone_voice`（本包不封装，仅登记）

schema 里 `voice_tts` 共 6 个接口：

| 接口 | 动作 | 本包是否封装 |
|---|---|---|
| `tts` | 文字转语音（同步） | ✅ |
| `tts_async` | 文字转语音（异步） | ✅（超长自动切） |
| `tts_live` | 文字转语音（Live·异步，WebSocket 流式） | ❌ |
| `stt` | 语音转文字（**字级时间戳**） | ✅ |
| `list_voices` | 音色列表 | ✅ |
| `clone_voice` | 克隆音色 | ❌ **有意不封装** |

不封装 `clone_voice` 的原因不是技术问题，是**合规问题**：
声音的可识别性受法律保护。用他人真实声音克隆后发布，
或把合成音伪装成真实人物发言，都是明确的风险。
本包的计费口径里**没有** `clone_voice` 的单价（未实测），
所以 `cost` 也不会报它的价——**不编**。

需要克隆自己的音色用于本人作品时，用平台的网页控制台或直接调接口，
拿到 `reference_id` 之后交给本包的 `--narrator-voice` / `--voice-map` 使用。
