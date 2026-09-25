---
name: music-generation-kit
slug: music-generation-kit
displayName: 三剪客 · 音乐生成
description: "音乐生成应用，支持歌曲生成、歌词生成、参考音频、声音克隆、音频导出和分轨处理。支持 歌词混合、人声处理、优化音乐风格、导出 MIDI、歌词时间轴、导出 MP4、导出 WAV、声音克隆。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「音乐生成」的完整调用封装：13 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 音乐生成
  - 音频
---

# 音乐生成

`api.a7w.cn` 插件 **`music_generation`**，共 **13 个接口**。将两段歌词融合为新的混合版本。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema music_generation

# 3. 调用（示例）
python3 scripts/client.py call music_generation mashup_lyrics --json '{}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `mashup_lyrics` | 歌词混合 | 同步 | 按次固定价 12 点（租户价） |
| `vox` | 人声处理 | 异步 | 按次固定价 14 点（租户价） |
| `style` | 优化音乐风格 | 同步 | 按次固定价 14 点（租户价） |
| `midi` | 导出 MIDI | 异步 | 按次固定价 14 点（租户价） |
| `timing` | 歌词时间轴 | 同步 | 免费 |
| `mp4` | 导出 MP4 | 同步 | 按次固定价 20 点（租户价） |
| `wav` | 导出 WAV | 异步 | 按次固定价 14 点（租户价） |
| `voice_clone` | 声音克隆 | 同步 | 按次固定价 20 点（租户价） |
| `persona` | 创建歌手风格 | 同步 | 按次固定价 12 点（租户价） |
| `upload_audio` | 上传参考音频 | 同步 | 按次固定价 13 点（租户价） |
| `lyrics` | 生成歌词 | 同步 | 按次固定价 12 点（租户价） |
| `query` | 查询音乐任务 | 同步 | 免费 |
| `create` | 创建音乐任务 | 异步 | 按次固定价 65 点（租户价） |

## 接口详情

### `mashup_lyrics` · 歌词混合

**请求**：`POST /api/v1/apps/music_generation/mashup_lyrics`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 12 点（租户价）

将两段歌词融合为新的混合版本。

将两段歌词融合为新的混合版本。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `mashup_lyrics` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/mashup_lyrics` | | 调用模式 | 同步 | | 计费方式 | 固定价 12 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `lyrics_a` | string | 是 | - | - | - | 第一段歌词文本。 | | `lyrics_b` | string | 是 | - | - | - | 第二段歌词文本。 | 同步返回处理结果…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `lyrics_a` | string | 否 |  | 第一段歌词文本。 |
| `lyrics_b` | string | 否 |  | 第二段歌词文本。 |

```bash
python3 scripts/client.py call music_generation mashup_lyrics --json '{}'
```

官方文档全文：[`references/api-mashup_lyrics.md`](references/api-mashup_lyrics.md)

### `vox` · 人声处理

**请求**：`POST /api/v1/apps/music_generation/vox`

**模式**：异步（提交后轮询任务） ｜ **计费**：按次固定价 14 点（租户价）

基于音频 ID 提取指定片段的人声或伴奏处理结果。

基于音频 ID 提取指定片段的人声或伴奏处理结果。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `vox` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/vox` | | 调用模式 | 异步 | | 计费方式 | 固定价 14 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `audio_id` | string | 是 | - | - | `audio_xxxxxxxxxxxx` | 音频 ID，用于定位已生成或已上传的音频片段。 | | `vocal_start` | number | 否 | - |…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `audio_id` | string | 否 |  | 音频 ID，用于定位已生成或已上传的音频片段。　例：`audio_xxxxxxxxxxxx` |
| `vocal_end` | number | 否 |  | 人声提取结束时间，单位秒。 |
| `vocal_start` | number | 否 |  | 人声提取开始时间，单位秒。 |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址。 |

```bash
python3 scripts/client.py call music_generation vox --json '{"audio_id": "audio_xxxxxxxxxxxx"}' --no-wait
```

官方文档全文：[`references/api-vox.md`](references/api-vox.md)

### `style` · 优化音乐风格

**请求**：`POST /api/v1/apps/music_generation/style`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 14 点（租户价）

根据提示词生成更完整的音乐风格描述。

根据提示词生成更完整的音乐风格描述。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `style` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/style` | | 调用模式 | 同步 | | 计费方式 | 固定价 14 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `prompt` | string | 是 | - | - | `warm electronic pop with female vocal` | 需要优化的风格提示词。 | 同步返回处理结果。媒体类结果可能包含 `audio_url`、`v…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `prompt` | string | 否 |  | 需要优化的风格提示词。　例：`warm electronic pop with female vocal` |

```bash
python3 scripts/client.py call music_generation style --json '{"prompt": "warm electronic pop with female vocal"}'
```

官方文档全文：[`references/api-style.md`](references/api-style.md)

### `midi` · 导出 MIDI

**请求**：`POST /api/v1/apps/music_generation/midi`

**模式**：异步（提交后轮询任务） ｜ **计费**：按次固定价 14 点（租户价）

基于音频 ID 提取 MIDI 文件。

基于音频 ID 提取 MIDI 文件。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `midi` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/midi` | | 调用模式 | 异步 | | 计费方式 | 固定价 14 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `audio_id` | string | 是 | - | - | `audio_xxxxxxxxxxxx` | 音频 ID，用于定位已生成或已上传的音频片段。 | | `callback_url` | string | 否 | - | - |…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `audio_id` | string | 否 |  | 音频 ID，用于定位已生成或已上传的音频片段。　例：`audio_xxxxxxxxxxxx` |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址；同步接口可不传。 |

```bash
python3 scripts/client.py call music_generation midi --json '{"audio_id": "audio_xxxxxxxxxxxx"}' --no-wait
```

官方文档全文：[`references/api-midi.md`](references/api-midi.md)

### `timing` · 歌词时间轴

**请求**：`POST /api/v1/apps/music_generation/timing`

**模式**：同步（直接返回结果） ｜ **计费**：免费

基于音频 ID 获取歌词与音频时间轴信息。

基于音频 ID 获取歌词与音频时间轴信息。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `timing` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/timing` | | 调用模式 | 同步 | | 计费方式 | 免费 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `audio_id` | string | 是 | - | - | `audio_xxxxxxxxxxxx` | 音频 ID，用于定位已生成或已上传的音频片段。 | | `callback_url` | string | 否 | - | - | -…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `audio_id` | string | 否 |  | 音频 ID，用于定位已生成或已上传的音频片段。　例：`audio_xxxxxxxxxxxx` |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址；同步接口可不传。 |

```bash
python3 scripts/client.py call music_generation timing --json '{"audio_id": "audio_xxxxxxxxxxxx"}'
```

官方文档全文：[`references/api-timing.md`](references/api-timing.md)

### `mp4` · 导出 MP4

**请求**：`POST /api/v1/apps/music_generation/mp4`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 20 点（租户价）

基于音频 ID 获取视频文件链接。

基于音频 ID 获取视频文件链接。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `mp4` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/mp4` | | 调用模式 | 同步 | | 计费方式 | 固定价 20 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `audio_id` | string | 是 | - | - | `audio_xxxxxxxxxxxx` | 音频 ID，用于定位已生成或已上传的音频片段。 | | `callback_url` | string | 否 | - | - | - |…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `audio_id` | string | 否 |  | 音频 ID，用于定位已生成或已上传的音频片段。　例：`audio_xxxxxxxxxxxx` |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址；同步接口可不传。 |

```bash
python3 scripts/client.py call music_generation mp4 --json '{"audio_id": "audio_xxxxxxxxxxxx"}'
```

官方文档全文：[`references/api-mp4.md`](references/api-mp4.md)

### `wav` · 导出 WAV

**请求**：`POST /api/v1/apps/music_generation/wav`

**模式**：异步（提交后轮询任务） ｜ **计费**：按次固定价 14 点（租户价）

基于音频 ID 导出高质量 WAV 文件。

基于音频 ID 导出高质量 WAV 文件。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `wav` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/wav` | | 调用模式 | 异步 | | 计费方式 | 固定价 14 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `audio_id` | string | 是 | - | - | `audio_xxxxxxxxxxxx` | 音频 ID，用于定位已生成或已上传的音频片段。 | | `callback_url` | string | 否 | - | - |…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `audio_id` | string | 否 |  | 音频 ID，用于定位已生成或已上传的音频片段。　例：`audio_xxxxxxxxxxxx` |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址；同步接口可不传。 |

```bash
python3 scripts/client.py call music_generation wav --json '{"audio_id": "audio_xxxxxxxxxxxx"}' --no-wait
```

官方文档全文：[`references/api-wav.md`](references/api-wav.md)

### `voice_clone` · 声音克隆

**请求**：`POST /api/v1/apps/music_generation/voice_clone`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 20 点（租户价）

基于清晰人声音频创建私有声音风格 ID。

**输入上限**：参考音频 ≤ 1 个

基于清晰人声音频创建私有声音风格 ID。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `voice_clone` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/voice_clone` | | 调用模式 | 同步 | | 计费方式 | 固定价 20 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `audio_url` | string | 是 | - | - | `https://example.com/voice.mp3` | 可公开访问的 MP3 或 WAV 人声音频 URL。音频至少 10 秒，建议…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `name` | string | 否 |  | 自定义声音风格名称。　例：`My Voice` |
| `audio_url` | string | 否 |  | 可公开访问的 MP3 或 WAV 人声音频 URL。音频至少 10 秒，建议单人清晰人声，尽量避免背景噪音或背景音乐。　例：`https://example.com/voice.mp3` |
| `description` | string | 否 |  | 自定义声音风格描述。 |

```bash
python3 scripts/client.py call music_generation voice_clone --json '{"name": "My Voice", "audio_url": "https://example.com/voice.mp3"}'
```

官方文档全文：[`references/api-voice_clone.md`](references/api-voice_clone.md)

### `persona` · 创建歌手风格

**请求**：`POST /api/v1/apps/music_generation/persona`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 12 点（租户价）

基于已生成歌曲创建可复用的歌手风格 ID。

基于已生成歌曲创建可复用的歌手风格 ID。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `persona` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/persona` | | 调用模式 | 同步 | | 计费方式 | 固定价 12 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `audio_id` | string | 是 | - | - | `audio_xxxxxxxxxxxx` | 音频 ID，用于定位已生成或已上传的音频片段。 | | `name` | string | 是 | - | - |…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `name` | string | 否 |  | 歌手风格名称。　例：`My Singer Style` |
| `audio_id` | string | 否 |  | 音频 ID，用于定位已生成或已上传的音频片段。　例：`audio_xxxxxxxxxxxx` |
| `vocal_end` | number | 否 |  | 人声片段结束时间，单位秒。 |
| `description` | string | 否 |  | 歌手风格的文字描述。 |
| `vocal_start` | number | 否 |  | 人声片段开始时间，单位秒。 |
| `vox_audio_id` | string | 否 |  | 用于创建新歌手风格的人声参考音频 ID。 |

```bash
python3 scripts/client.py call music_generation persona --json '{"name": "My Singer Style", "audio_id": "audio_xxxxxxxxxxxx"}'
```

官方文档全文：[`references/api-persona.md`](references/api-persona.md)

### `upload_audio` · 上传参考音频

**请求**：`POST /api/v1/apps/music_generation/upload_audio`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 13 点（租户价）

提交可访问的音频地址并返回可用于后续创作的音频 ID。

**输入上限**：参考音频 ≤ 1 个

提交可访问的音频地址并返回可用于后续创作的音频 ID。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `upload_audio` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/upload_audio` | | 调用模式 | 同步 | | 计费方式 | 固定价 13 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `audio_url` | string | 是 | - | - | `https://example.com/ref.mp3` | 可公开访问的音频文件 URL，用于生成后续创作需要的音频 ID…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `audio_url` | string | 否 |  | 可公开访问的音频文件 URL，用于生成后续创作需要的音频 ID。　例：`https://example.com/ref.mp3` |

```bash
python3 scripts/client.py call music_generation upload_audio --json '{"audio_url": "https://example.com/ref.mp3"}'
```

官方文档全文：[`references/api-upload_audio.md`](references/api-upload_audio.md)

### `lyrics` · 生成歌词

**请求**：`POST /api/v1/apps/music_generation/lyrics`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 12 点（租户价）

根据主题或风格描述生成结构化歌词。

根据主题或风格描述生成结构化歌词。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `lyrics` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/lyrics` | | 调用模式 | 同步 | | 计费方式 | 固定价 12 点/次 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `prompt` | string | 是 | - | - | `A song about winter` | 歌词生成提示词，用于描述歌词主题、情绪或风格。 | 同步返回处理结果。媒体类结果可能包含 `audio_url`、`video_…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `prompt` | string | 否 |  | 歌词生成提示词，用于描述歌词主题、情绪或风格。　例：`A song about winter` |

```bash
python3 scripts/client.py call music_generation lyrics --json '{"prompt": "A song about winter"}'
```

官方文档全文：[`references/api-lyrics.md`](references/api-lyrics.md)

### `query` · 查询音乐任务

**请求**：`POST /api/v1/apps/music_generation/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按平台任务 ID 查询任务状态与结果。

按平台任务 ID 查询任务状态与结果。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `query` | | 请求方式 | `GET` | | 请求路径 | `/api/v1/apps/music_generation/query` | | 调用模式 | 同步 | | 计费方式 | 免费 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 示例 | 说明 | | `task_id` | string | 是 | - | - | `task_xxxxxxxxxxxx` | 创建任务后返回的平台任务 ID。 | 同步返回处理结果。媒体类结果可能包含 `audio_url`、`video_url`、`file_url`、`…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | 否 |  | 创建任务后返回的平台任务 ID。　例：`task_xxxxxxxxxxxx` |

```bash
python3 scripts/client.py call music_generation query --json '{"task_id": "task_xxxxxxxxxxxx"}'
```

官方文档全文：[`references/api-query.md`](references/api-query.md)

### `create` · 创建音乐任务

**请求**：`POST /api/v1/apps/music_generation/create`

**模式**：异步（提交后轮询任务） ｜ **计费**：按次固定价 65 点（租户价）

提交音乐生成、续写、翻唱、分轨或混音任务，返回平台任务 ID。

**输入上限**：参考音频 ≤ 1 个

提交音乐生成、续写、翻唱、分轨或混音任务，返回平台任务 ID。 | 字段 | 内容 | | 应用编码 | `music_generation` | | API 编码 | `create` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/music_generation/create` | | 调用模式 | 异步 | | 计费方式 | 按 `type` 对应固定规格计费 | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json 请求 `create` 接口时，`type` 字段决定具体创作动作和计费规格。 | type 参数值 | 规格说明 | 价格 | | `generate` | 生成音乐 | 65 点/次 | | `extend` | 续写音乐 | 65 点/次 | | `upload_extend` |…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `type` | enum | 否 | `generate` | 操作类型。generate 根据提示生成音乐；extend 基于已有音频续写；concat 拼接音频片段；cover 参考既有曲风重新演绎；upload_cover 对上传音频进行风格翻唱；upload_extend 续写上传音频；artist_consistency 按指定歌手风格生成；artist_consistency_vox 使用人声模式按歌手风格生成；stems 分离人声和伴奏；all_stems 分离人声、鼓、贝斯和其他乐器；replace_section 替换指定时间段；underpainting 为人声添加伴奏；overpainting 为伴奏添加人声；samples 在指定时间段添加采样；remaster 增强音质；mashup 混合多首歌曲；inspo 基于 1 到 4 段参考音频生成灵感作品。　可选值：`generate` / `extend` / `upload_extend` / `upload_cover` / `concat` / `cover` / `artist_consistency` / `artist_consistency_vox` / `stems` / `all_stems` / `replace_section` / `underpainting` / `overpainting` / `remaster` / `mashup` / `samples` / `inspo` |
| `lyric` | string | 否 |  | 自定义模式下使用的歌词。常规模型最多 3000 字符，高质量模型最多 5000 字符。 |
| `style` | string | 否 |  | 音乐风格描述。常规模型最多 200 字符，高质量模型最多 1000 字符。　例：`dream pop, warm synth, mellow vocal` |
| `title` | string | 否 |  | 自定义模式下的歌曲标题。常规模型最多 80 字符，高质量模型最多 100 字符。　例：`Neon Night` |
| `custom` | boolean | 否 |  | 是否启用自定义模式。请使用 JSON boolean；平台也兼容 true/false、1/0、yes/no、on/off 字符串。为 true 时按歌词和风格生成；为 false 时按提示词生成。 |
| `prompt` | string | 否 |  | 生成音乐的提示词。灵感模式下不超过 500 个字符；自定义歌词模式请优先使用 lyric 和 style。　例：`A warm synth-pop song about city nights` |
| `audio_id` | string | 否 |  | 已有音频 ID。extend、concat 等基于已有音频的操作需要填写。 |
| `weirdness` | number | 否 |  | 创意实验强度，范围 0 到 1；数值越高结果越开放，仅在自定义模式下生效。 |
| `audio_urls` | array | 否 |  | 参考音频 URL 列表。inspo 类型要求 1 到 4 个可公开访问的音频地址。　例：`['https://example.com/ref.mp3']` |
| `persona_id` | string | 否 |  | 歌手或声音风格 ID，用于让生成歌曲采用指定风格。 |
| `continue_at` | number | 否 |  | 从已有音频的指定秒数位置继续生成。例如 213.5 表示从 3 分 33.5 秒处续写。 |
| `samples_end` | number | 否 |  | 添加采样的结束时间，单位秒，需小于歌曲总时长。 |
| `audio_weight` | number | 否 |  | 参考音频权重，范围 0 到 1；数值越高越依赖参考音频，主要用于翻唱类操作。 |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址。 |
| `instrumental` | boolean | 否 |  | 纯伴奏模式。请使用 JSON boolean；平台也兼容 true/false、1/0、yes/no、on/off 字符串。开启后将忽略歌词内容。 |
| `lyric_prompt` | string | 否 |  | 自动生成歌词的提示词，仅在 custom 为 true 且 lyric 为空时生效。 |
| `vocal_gender` | enum | 否 |  | 人声性别偏好，m 表示男声，f 表示女声。该参数用于提高目标音色概率，但不保证严格符合。　可选值：`m` / `f` |
| `samples_start` | number | 否 |  | 添加采样的开始时间，单位秒，默认 0。 |
| `style_negative` | string | 否 |  | 不希望出现在音乐中的风格描述。 |
| `style_influence` | number | 否 |  | 风格影响强度，范围 0 到 1；数值越高越贴近填写的风格，仅在自定义模式下生效。 |
| `mashup_audio_ids` | array | 否 |  | 用于混合的音频 ID 列表。mashup 类型需要填写。 |
| `overpainting_end` | number | 否 |  | 添加人声的结束时间，单位秒，需小于歌曲总时长。 |
| `underpainting_end` | number | 否 |  | 添加伴奏的结束时间，单位秒，需小于歌曲总时长。 |
| `overpainting_start` | number | 否 |  | 添加人声的开始时间，单位秒，默认 0。 |
| `variation_category` | enum | 否 |  | 变化强度，可选 high、normal、subtle。　可选值：`high` / `normal` / `subtle` |
| `replace_section_end` | number | 否 |  | replace_section 类型中需要替换片段的结束时间，单位秒。 |
| `underpainting_start` | number | 否 |  | 添加伴奏的开始时间，单位秒，默认 0。 |
| `replace_section_start` | number | 否 |  | replace_section 类型中需要替换片段的开始时间，单位秒。 |

```bash
python3 scripts/client.py call music_generation create --json '{"style": "dream pop, warm synth, mellow vocal", "title": "Neon Night", "prompt": "A warm synth-pop song about city nights", "audio_urls": ["https://example.com/ref.mp3"]}' --no-wait
```

官方文档全文：[`references/api-create.md`](references/api-create.md)

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/通用说明.md` | 权限表、异步任务机制、常见错误、能力边界、计费口径 |
| `references/getting-started.md` | 注册、充值、获取与配置 API Key |
| `references/api-mashup_lyrics.md` | `mashup_lyrics` 的平台官方文档全文 + schema 原文 |
| `references/api-vox.md` | `vox` 的平台官方文档全文 + schema 原文 |
| `references/api-style.md` | `style` 的平台官方文档全文 + schema 原文 |
| `references/api-midi.md` | `midi` 的平台官方文档全文 + schema 原文 |
| `references/api-timing.md` | `timing` 的平台官方文档全文 + schema 原文 |
| `references/api-mp4.md` | `mp4` 的平台官方文档全文 + schema 原文 |
| `references/api-wav.md` | `wav` 的平台官方文档全文 + schema 原文 |
| `references/api-voice_clone.md` | `voice_clone` 的平台官方文档全文 + schema 原文 |
| `references/api-persona.md` | `persona` 的平台官方文档全文 + schema 原文 |
| `references/api-upload_audio.md` | `upload_audio` 的平台官方文档全文 + schema 原文 |
| `references/api-lyrics.md` | `lyrics` 的平台官方文档全文 + schema 原文 |
| `references/api-query.md` | `query` 的平台官方文档全文 + schema 原文 |
| `references/api-create.md` | `create` 的平台官方文档全文 + schema 原文 |
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
