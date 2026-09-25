---
name: voice-tts-studio
slug: voice-tts-studio
displayName: 三剪客 · 语音TTS
description: "语音克隆、文字转语音（同步/异步）、语音识别等多端点 AI 语音能力。支持 文字转语音（Live·异步）、克隆音色、文字转语音、文字转语音（异步）、语音转文字、音色列表。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「语音TTS」的完整调用封装：6 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 语音合成
  - 音色克隆
  - TTS
---

# 语音TTS

`api.a7w.cn` 插件 **`voice_tts`**，共 **6 个接口**。WebSocket 流式上游，长文本异步合成；返回 task_id，由 fish_tts:worker 执行

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema voice_tts

# 3. 调用（示例）
python3 scripts/client.py call voice_tts tts_live --json '{"text": "<text>"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `tts_live` | 文字转语音（Live·异步） | 异步 | 输入 50 点/1k tokens（租户价） |
| `clone_voice` | 克隆音色 | 同步 | 按次固定价 200 点（租户价）；标准价 50 点 |
| `tts` | 文字转语音 | 同步 | 输入 50 点/1k tokens（租户价） |
| `tts_async` | 文字转语音（异步） | 异步 | 输入 50 点/1k tokens（租户价） |
| `stt` | 语音转文字 | 同步 | 按次固定价 30 点（租户价） |
| `list_voices` | 音色列表 | 同步 | 免费 |

## 接口详情

### `tts_live` · 文字转语音（Live·异步）

**请求**：`POST /api/v1/apps/v1/tts/live`

**模式**：异步（提交后轮询任务） ｜ **计费**：输入 50 点/1k tokens（租户价）

WebSocket 流式上游，长文本异步合成；返回 task_id，由 fish_tts:worker 执行

使用 Fish Audio **WebSocket `wss://…/v1/tts/live`** 流式合成，适合长文本；**提交后立即返回 `task_id`**，实际合成在后台 **独立 Worker** 中执行，避免 HTTP 网关超时。 `GET /api/v1/tasks/{task_id}` 直至 `status` 为 `completed`，结果中 `result.audio_url` 为音频地址。 可选 `callback_url`，与 `tts_async` 行为一致。 服务器需执行： `php think fish_tts:worker`（常驻）或 `php think fish_tts:worker --once`（crontab 每分钟）。 Composer 已包含 `rybakit/msgpack`、`textalk/websocket`；服务端需能访问 `wss://api.fish.audio`。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `text` | string | **是** |  | 待合成文本（WebSocket 流式上游，适合长文本） |
| `model` | string | 否 |  | TTS 模型：s1 / s2-pro，默认 s2-pro |
| `top_p` | number | 否 |  | Top-P |
| `format` | string | 否 |  | wav / pcm / mp3 / opus，默认 mp3 |
| `latency` | string | 否 |  | low / normal / balanced |
| `prosody` | object | 否 |  | 语调：speed、volume、normalize_loudness（仅 s2-pro） |
| `normalize` | boolean | 否 |  | 文本规范化，默认 true |
| `mp3_bitrate` | integer | 否 |  | MP3 比特率：64 / 128 / 192 |
| `sample_rate` | integer | 否 |  | 采样率 |
| `temperature` | number | 否 |  | 生成温度 |
| `callback_url` | string | 否 |  | 回调 URL；不传则 GET /api/v1/tasks/{task_id} 轮询 |
| `chunk_length` | integer | 否 |  | 文本分块长度 100~300，默认 300 |
| `opus_bitrate` | integer | 否 |  | Opus 比特率 |
| `reference_id` | string | 否 |  | 音色模型ID。单说话人传 string；多说话人可传 string[]（仅 s2-pro） |
| `max_new_tokens` | integer | 否 |  | 每分块最大音频 token |
| `min_chunk_length` | integer | 否 |  | 最小分块长度 0~100 |
| `repetition_penalty` | number | 否 |  | 重复惩罚 |
| `early_stop_threshold` | number | 否 |  | 提前停止阈值，0~1 |
| `condition_on_previous_chunks` | boolean | 否 |  | 是否利用前一段音频作为上下文 |

```bash
python3 scripts/client.py call voice_tts tts_live --json '{"text": "<text>"}' --no-wait
```

官方文档全文：[`references/api-tts_live.md`](references/api-tts_live.md)

### `clone_voice` · 克隆音色

**请求**：`POST /api/v1/apps/model`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 200 点（租户价）；标准价 50 点

上传参考音频或提供音频URL，创建专属语音音色模型

**输入上限**：参考音频 ≤ 1 个

上传一段参考音频（或提供音频URL），系统将自动训练生成专属语音音色模型。创建成功后返回 model_id，可用于后续文字转语音调用。 - **方式一**（推荐）：JSON Body 传入 `audio_url` 音频链接 - **方式二**：multipart/form-data 上传 `voices` 文件字段 | 参数 | 类型 | 必填 | 说明 | | audio_url | string | 否 | 参考音频URL（与文件上传二选一），支持mp3/wav/ogg | | title | string | 是 | 音色名称 | | description | string | 否 | 音色描述 | | enhance_audio_quality | boolean | 否 | 是否增强音频质量 | { "code": 1, "msg": "success", "data": { "id": "model_xxxxxxx…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `tags` | array | 否 |  | 模型标签数组 |
| `texts` | array | 否 |  | 与音频对应的文本数组；不传时自动ASR |
| `title` | string | **是** |  | 音色名称 |
| `audio_url` | string | 否 |  | 参考音频URL（与上传文件二选一），支持 mp3/wav/ogg/flac |
| `visibility` | string | 否 |  | 可见性：public / unlist / private，平台默认 private |
| `description` | string | 否 |  | 音色描述 |
| `enhance_audio_quality` | boolean | 否 |  | 是否增强音频质量，默认 false |

```bash
python3 scripts/client.py call voice_tts clone_voice --json '{"title": "<title>"}'
```

官方文档全文：[`references/api-clone_voice.md`](references/api-clone_voice.md)

### `tts` · 文字转语音

**请求**：`POST /api/v1/apps/v1/tts`

**模式**：同步（直接返回结果） ｜ **计费**：输入 50 点/1k tokens（租户价）

将文本同步合成为语音音频文件（适合短文本，500字符内），直接返回音频URL

将文本内容同步合成为语音音频文件。请求后直接返回结果，适合短文本（建议 500 字符内）。长文本请使用异步接口 `tts_async`。 **同步接口** - 请求后直接返回合成结果（含音频URL），无需轮询。 | 参数 | 类型 | 必填 | 说明 | | text | string | 是 | 待合成文本，建议不超过500字符 | | reference_id | string | 否 | 音色模型ID（克隆音色返回的 model_id） | | model | string | 否 | 合成引擎：speech-1.5 / speech-1.5-turbo | | format | string | 否 | 输出格式：mp3(默认)/wav/ogg/opus/pcm | | sample_rate | integer | 否 | 采样率：8000/16000/22050/44100(默认) | | chunk_length…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `text` | string | **是** |  | 待合成文本，同步接口建议不超过 500 字符 |
| `model` | string | 否 |  | TTS 模型，可选 s1 / s2-pro，默认 s2-pro |
| `top_p` | number | 否 |  | Top-P 采样，0~1，默认 0.7 |
| `format` | string | 否 |  | 输出格式：wav / pcm / mp3 / opus，默认 mp3 |
| `latency` | string | 否 |  | 延迟模式：low / normal / balanced |
| `prosody` | object | 否 |  | 语调控制对象：speed、volume、normalize_loudness |
| `normalize` | boolean | 否 |  | 文本规范化，默认 true |
| `mp3_bitrate` | integer | 否 |  | MP3 比特率：64 / 128 / 192 |
| `sample_rate` | integer | 否 |  | 采样率按格式限制 |
| `temperature` | number | 否 |  | 生成温度，0~1，默认 0.7 |
| `chunk_length` | integer | 否 |  | 文本分块长度，范围 100~300，默认 300 |
| `opus_bitrate` | integer | 否 |  | Opus 比特率：-1000 / 24 / 32 / 48 / 64 |
| `reference_id` | string | 否 |  | 音色模型ID。单说话人传 string；多说话人模式可传 string[]（仅 s2-pro） |
| `max_new_tokens` | integer | 否 |  | 每个分块最多生成音频 token，默认 1024 |
| `min_chunk_length` | integer | 否 |  | 最小分块长度，范围 0~100，默认 50 |
| `repetition_penalty` | number | 否 |  | 重复惩罚，默认 1.2 |
| `early_stop_threshold` | number | 否 |  | 提前停止阈值，范围 0~1，默认 1 |
| `condition_on_previous_chunks` | boolean | 否 |  | 是否利用前一段音频作为上下文，默认 true |

```bash
python3 scripts/client.py call voice_tts tts --json '{"text": "<text>"}'
```

官方文档全文：[`references/api-tts.md`](references/api-tts.md)

### `tts_async` · 文字转语音（异步）

**请求**：`POST /api/v1/apps/v1/tts`

**模式**：异步（提交后轮询任务） ｜ **计费**：输入 50 点/1k tokens（租户价）

将文本异步合成为语音音频文件（适合长文本），通过回调或轮询获取结果

将文本内容异步合成为语音音频文件。适合长文本，提交后立即返回 `task_id`，通过回调或轮询获取结果。 **异步接口** - 提交后返回 task_id。 - 传 `callback_url`：任务完成后自动回调 - 不传 `callback_url`：通过 `GET /api/v1/tasks/{task_id}` 轮询 { "code": 1, "msg": "success", "data": { "task_id": "tsk_xxxxxxxxxxxx", "status": "pending", "app": "voice_tts", "api": "tts_async" } }

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `text` | string | **是** |  | 待合成文本，适合长文本（最大约 10000 字符） |
| `model` | string | 否 |  | TTS 模型，可选 s1 / s2-pro，默认 s2-pro |
| `top_p` | number | 否 |  | Top-P 采样，0~1，默认 0.7 |
| `format` | string | 否 |  | 输出格式：wav / pcm / mp3 / opus，默认 mp3 |
| `latency` | string | 否 |  | 延迟模式：low / normal / balanced |
| `prosody` | object | 否 |  | 语调控制对象：speed、volume、normalize_loudness |
| `normalize` | boolean | 否 |  | 文本规范化，默认 true |
| `mp3_bitrate` | integer | 否 |  | MP3 比特率：64 / 128 / 192 |
| `sample_rate` | integer | 否 |  | 采样率按格式限制 |
| `temperature` | number | 否 |  | 生成温度，0~1，默认 0.7 |
| `callback_url` | string | 否 |  | 回调通知URL；不传则通过任务接口轮询 |
| `chunk_length` | integer | 否 |  | 文本分块长度，范围 100~300，默认 300 |
| `opus_bitrate` | integer | 否 |  | Opus 比特率：-1000 / 24 / 32 / 48 / 64 |
| `reference_id` | string | 否 |  | 音色模型ID。单说话人传 string；多说话人模式可传 string[]（仅 s2-pro） |
| `max_new_tokens` | integer | 否 |  | 每个分块最多生成音频 token，默认 1024 |
| `min_chunk_length` | integer | 否 |  | 最小分块长度，范围 0~100，默认 50 |
| `repetition_penalty` | number | 否 |  | 重复惩罚，默认 1.2 |
| `early_stop_threshold` | number | 否 |  | 提前停止阈值，范围 0~1，默认 1 |
| `condition_on_previous_chunks` | boolean | 否 |  | 是否利用前一段音频作为上下文，默认 true |

```bash
python3 scripts/client.py call voice_tts tts_async --json '{"text": "<text>"}' --no-wait
```

官方文档全文：[`references/api-tts_async.md`](references/api-tts_async.md)

### `stt` · 语音转文字

**请求**：`POST /api/v1/apps/v1/asr`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 30 点（租户价）

将语音音频识别转写为文本，支持文件上传或音频URL

**输入上限**：参考音频 ≤ 1 个

将音频文件中的语音内容识别并转写为文本。支持多种语言自动检测。 - **方式一**（推荐）：JSON Body 传入 `audio_url` 音频链接 - **方式二**：multipart/form-data 上传 `audio` 文件字段 | 参数 | 类型 | 必填 | 说明 | | audio_url | string | 否 | 音频文件URL（与文件上传二选一） | | language | string | 否 | 语言代码(zh/en/ja等)，不填自动检测 | | ignore_timestamps | boolean | 否 | 是否忽略时间戳，默认true | { "code": 1, "msg": "success", "data": { "text": "识别出的文本内容", "duration": 12.5, "language": "zh" } } - 支持 mp3/wav/ogg 格式 - 单个文…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `language` | string | 否 |  | 识别语言，不传则自动检测 |
| `audio_url` | string | 否 |  | 音频文件URL（与文件上传二选一） |
| `ignore_timestamps` | boolean | 否 |  | 是否忽略精确时间戳，默认 true |

```bash
python3 scripts/client.py call voice_tts stt --json '{"ignore_timestamps": "1"}'
```

官方文档全文：[`references/api-stt.md`](references/api-stt.md)

### `list_voices` · 音色列表

**请求**：`POST /api/v1/apps/model`

**模式**：同步（直接返回结果） ｜ **计费**：免费

查询当前用户创建的语音音色模型列表

`GET /api/v1/apps/voice_tts/list_voices` 分页查询已创建的语音音色模型，可按名称、语言筛选。 | 参数 | 类型 | 必填 | 说明 | | page_size | integer | 否 | 每页数量，默认20，最大100 | | page_number | integer | 否 | 页码，从1开始 | | title | string | 否 | 按名称模糊搜索 | | self | boolean | 否 | 仅查询自己创建的音色，默认true | | language | string | 否 | 按语言筛选 | { "code": 1, "msg": "success", "data": { "total": 5, "items": [ { "id": "model_xxxxxxxxxxxx", "title": "我的音色", "type": "tts", "created_…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `tag` | string | 否 |  | 按标签筛选 |
| `title` | string | 否 |  | 按音色名称搜索 |
| `sort_by` | string | 否 |  | 排序：score / task_count / created_at |
| `language` | string | 否 |  | 按语言筛选 |
| `page_size` | integer | 否 |  | 每页数量，官方默认 10 |
| `page_number` | integer | 否 |  | 页码，默认 1 |
| `title_language` | string | 否 |  | 按标题语言筛选 |

```bash
python3 scripts/client.py call voice_tts list_voices --json '{"self": "1", "page_size": "20", "page_number": "1"}'
```

官方文档全文：[`references/api-list_voices.md`](references/api-list_voices.md)

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/通用说明.md` | 权限表、异步任务机制、常见错误、能力边界、计费口径 |
| `references/getting-started.md` | 注册、充值、获取与配置 API Key |
| `references/api-tts_live.md` | `tts_live` 的平台官方文档全文 + schema 原文 |
| `references/api-clone_voice.md` | `clone_voice` 的平台官方文档全文 + schema 原文 |
| `references/api-tts.md` | `tts` 的平台官方文档全文 + schema 原文 |
| `references/api-tts_async.md` | `tts_async` 的平台官方文档全文 + schema 原文 |
| `references/api-stt.md` | `stt` 的平台官方文档全文 + schema 原文 |
| `references/api-list_voices.md` | `list_voices` 的平台官方文档全文 + schema 原文 |
| `scripts/client.py` | 通用客户端（零依赖） |

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
