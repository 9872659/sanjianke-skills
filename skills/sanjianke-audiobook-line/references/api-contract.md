# 接口契约（实测原文）

> 全部参数与返回来自 2026-11-07 的本机实测与平台 schema 原文。
> 本文件只记事实：哪条接口存在、吃什么参数、回什么结构、按什么价结算。

---

## 一、端点地图

| 用途 | 方法 | 路径 | 同步/异步 | 实测 |
|---|---|---|---|---|
| 长文本配音（默认） | POST | `/api/v1/apps/voice_tts/tts_async` | 异步，回 `task_id` | 空 body 会建任务，见第五节 |
| 长文本配音（流式） | POST | `/api/v1/apps/voice_tts/tts_live` | 异步，回 `task_id` | 目录里在架（`call_type=2`） |
| 短句配音 | POST | `/api/v1/apps/voice_tts/tts` | 同步 | 空 body 回 `{"code":0,"msg":"任务处理失败，请稍后重试"}` |
| 音色克隆 | POST | `/api/v1/apps/voice_tts/clone_voice` | 同步，回 `model_id` | 缺 `title` 时回同一句失败话术 |
| 语音转写 | POST | `/api/v1/apps/voice_tts/stt` | 同步 | 空 body 回同一句失败话术 |
| 音色库 | GET | `/api/v1/apps/voice_tts/list_voices?page_number=1&page_size=50` | 同步 | 200，`total=58` |
| ElevenLabs 配音 | POST | `/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2` | 异步 | 目录里在架 |
| 带时间戳歌词 | POST | `/api/v1/apps/media_services_33/music_timestamped_lyrics` | 异步 | 缺必填停在校验层 |
| 任务查询 | GET | `/api/v1/tasks/<task_id>` | 只读 | 假 id → `{"code":0,"msg":"任务不存在"}` |
| 应用目录（免费） | GET | `/api/v1/apps` | 只读 | 22 个应用，`voice_tts` 6 接口、`media_services_33` 29 接口 |
| 价目表（裸对象） | GET | `/api/v1/pricing` | 只读 | 115 条规则，**不套 `code`/`data`** |
| 余额（裸对象） | GET | `/user/balance` | 只读 | `available_points` / `frozen` / `rate=100` |
| 流水（裸对象） | GET | `/user/balance/logs?limit=20` | 只读 | `logs[]` / `inPoints` / `outPoints` / `balanceMoving` |

**不要打 `GET /api/v1/apps/<app>`。** 那条命中 `/api/v1/apps/<app>/*` 的通配计价，
会按该应用的 flat 单价即时结算（`sync:`，失败也**不退**）。
本包判断接口是否存在统一走 `GET /api/v1/apps` 目录，一次请求看全 22 个应用、0 点。

---

## 二、`voice_tts` 六个接口（目录实测）

```
GET /api/v1/apps  → data[] 里 code=voice_tts 的条目，apis 六条：

  tts_live      call_type=2  POST   长文本（WebSocket 上游），回 task_id
  clone_voice   call_type=1  POST   建音色，回 model_id
  tts           call_type=1  POST   短文本（≤500 字），回 audio_url
  tts_async     call_type=2  POST   长文本（≤10000 字符），回 task_id
  stt           call_type=1  POST   转写，可带字级时间戳
  list_voices   call_type=1  GET    分页查音色
```

`call_type=2` 的同步判据：`data.code==1` 且 `data.data.task_id` 非空 → 轮询 `GET /api/v1/tasks/{task_id}`。

---

## 三、参数（平台 schema 原文）

### 3.1 `tts_async` / `tts_live`（长文本）

```json
{
  "text":        {"type":"string","required":"1","description":"待合成文本（异步最大约 10000 字符）"},
  "model":       {"type":"string","required":"","description":"TTS 模型：s1 / s2-pro，默认 s2-pro"},
  "format":      {"type":"string","required":"","description":"wav / pcm / mp3 / opus，默认 mp3"},
  "reference_id":{"type":"string","required":"","description":"音色模型ID（克隆返回的 model_id）；多说话人可传 string[]（仅 s2-pro）"},
  "mp3_bitrate": {"type":"integer","required":"","description":"64 / 128 / 192"},
  "sample_rate": {"type":"integer","required":"","description":"按格式限制"},
  "chunk_length":{"type":"integer","required":"","description":"文本分块 100–300，默认 300"},
  "prosody":     {"type":"object","required":"","description":"speed / volume / normalize_loudness（仅 s2-pro）"},
  "top_p":       {"type":"number","required":"","description":"0–1，默认 0.7"},
  "temperature": {"type":"number","required":"","description":"0–1，默认 0.7"},
  "normalize":   {"type":"boolean","required":"","description":"文本规范化，默认 true"},
  "latency":     {"type":"string","required":"","description":"low / normal / balanced"},
  "callback_url":{"type":"string","required":"","description":"完成回调地址；不传则轮询"},
  "max_new_tokens":               {"type":"integer","required":"","description":"每块最大音频 token，默认 1024"},
  "min_chunk_length":             {"type":"integer","required":"","description":"0–100，默认 50"},
  "repetition_penalty":           {"type":"number","required":"","description":"默认 1.2"},
  "early_stop_threshold":         {"type":"number","required":"","description":"0–1，默认 1"},
  "condition_on_previous_chunks": {"type":"boolean","required":"","description":"默认 true"},
  "opus_bitrate": {"type":"integer","required":"","description":"-1000 / 24 / 32 / 48 / 64"}
}
```

### 3.2 `tts`（同步短句）

参数同上，文档标注「建议不超过 500 字符」，返回直接给 `audio_url`：

```json
{"code":1,"msg":"success","data":{"audio_url":"https://…/tts_xxx.mp3","format":"mp3"}}
```

### 3.3 `stt`（转写）

```json
{
  "language":          {"type":"string","required":"","description":"识别语言，不传自动检测"},
  "audio_url":         {"type":"string","required":"","description":"音频地址（与文件上传二选一）"},
  "ignore_timestamps": {"type":"boolean","required":"","description":"是否忽略精确时间戳，默认 true"}
}
```

要做字幕就显式传 `"ignore_timestamps": false`（默认 true 会把时间戳丢掉）。
本地文件走 multipart，文件字段名 `audio`；`--file` 分支就是这么发的。

### 3.4 `clone_voice`（建音色）

| 参数 | 必填 | 说明 |
|---|---|---|
| `title` | **是** | 音色名字 |
| `audio_url` | 否 | 参考音频地址（与上传二选一），mp3 / wav / ogg / flac |
| `description` | 否 | 音色描述 |
| `enhance_audio_quality` | 否 | 默认 false |
| `visibility` | 否 | `public` / `unlist` / `private`，默认 private |
| `tags` / `texts` | 否 | 标签数组 / 与音频对应的文本数组（不传自动 ASR） |

参考音频建议 10 秒–5 分钟。返回 `{"id":"model_xxx","model_id":"model_xxx","title":"…","type":"tts"}`，
`model_id` 就是 `reference_id`。本地文件走 multipart，文件字段名 `voices`。

### 3.5 `list_voices`（音色库）

`page_number` / `page_size` / `title` / `language` / `sort_by` / `tag` / `title_language`，全部可选。

实测返回（`page_size=2`）：

```json
{"code":1,"msg":"success","data":{"total":58,"items":[
  {"id":"8a0091a876d9409db305e16b15e8a42f","model_id":"8a0091a876d9409db305e16b15e8a42f",
   "title":"音色-trim-10s","type":"tts","state":"trained","created_at":"2026-11-05T12:28:19.881850Z"},
  {"id":"99489fa3838d41d5875089e4bf9b4cf4","model_id":"99489fa3838d41d5875089e4bf9b4cf4",
   "title":"音色-trim-10s","type":"tts","state":"trained","created_at":"2026-11-05T12:28:19.328679Z"}],
 "page_size":2,"page_number":1}}
```

`state=trained` 才可用；`id` 与 `model_id` 实测同值。

---

## 四、`media_services_33` 两条（辅线）

统一形态：`POST /api/v1/apps/media_services_33/<接口code>`，返回 `{"code":1,"msg":"success","data":{…}}`。

### 4.1 `elevenlabs_text_to_speech_multilingual_v2`

必填 `text`（≤5000 字）、`voice`（音色 ID）。可选：
`speed` / `style` / `stability` / `similarity_boost`（0–1）、`timestamps`（要逐词时间戳）、
`language_code`、`previous_text` / `next_text`（跨段连贯）、`speed`。

### 4.2 `music_timestamped_lyrics`

必填 `task_id`、`audio_id` —— 两个都来自 `media_services_33` 那条异步任务的返回。
缺参实测原文：

```json
{"code":0,"msg":"input.task_id: 缺少必填参数；input.audio_id: 缺少必填参数","data":null}
```

---

## 五、实测返回（原文照抄）

### 5.1 空 body POST 到 `voice_tts/tts_async` —— 它建了任务

```http
POST /api/v1/apps/voice_tts/tts_async
Content-Type: application/json

{}
```

```json
{"code":1,"msg":"success","data":{"task_id":"task_7257444313a43caac40607bf",
 "status":"pending","app":"voice_tts","api":"tts_async","frozen_points":150,
 "actual_points":0,"created_at":"2026-11-07T21:36:19Z","relay_points":150}}
```

随后 `GET /api/v1/tasks/task_7257444313a43caac40607bf`：

```json
{"code":1,"msg":"success","data":{"task_id":"task_7257444313a43caac40607bf",
 "model":"voice_tts/tts_async","type":"app","call_type":"async","status":"failed",
 "created_at":"2026-11-07T21:36:19Z",
 "error":{"code":"invalid_request","message":"任务处理失败，请稍后重试"}}}
```

流水里对应的两条：

```
reserve  -150  reserve (balanceMoving=false)  path=/api/v1/apps/voice_tts/tts_async
refund   +150  refund:task_failed:task_7257444313a43caac40607bf
```

**净 0，但确实建了任务、动了钱包。** 所以 `doctor` 默认不发任何 POST。

### 5.2 `voice_tts` 其余四个接口空 body

```
POST tts           {}  → {"code":0,"msg":"任务处理失败，请稍后重试","data":null}   reserve_sync 150 → refund 150
POST clone_voice   {}  → {"code":0,"msg":"任务处理失败，请稍后重试","data":null}   reserve_sync 150 → refund 150
POST stt           {}  → {"code":0,"msg":"任务处理失败，请稍后重试","data":null}   reserve_sync 150 → refund 150
```

三条都先 `reserve_sync` 冻 150 点、再全额退；这三条**不建任务**，只是失败话术统一成了一句话。

### 5.3 连 `GET list_voices` 也会预扣

```
GET /api/v1/apps/voice_tts/list_voices?page_number=1&page_size=1
流水：reserve_sync -150  →  refund:sync:/api/v1/apps/voice_tts/list_voices +150
```

路径级规则是「`/api/v1/apps/voice_tts/*` 一律先预扣 150 点」，与方法无关。
净额 0，但每次都要动一次钱包，所以 `doctor` 只打一次，另给 `--no-voices` 能整条跳过。

### 5.4 假 `task_id`

```
GET /api/v1/tasks/sanjianke-doctor-probe
→ HTTP 200 {"code":0,"msg":"任务不存在","data":null}
```

判据：HTTP 200 + `code==0` + 含「任务不存在」⇒ 路由在、鉴权过、`task_id` 确实不存在。

---

## 六、价格（`GET /api/v1/pricing` 原文）

### 6.1 `voice_tts` 专属规则

```json
"/api/v1/apps/voice_tts/*": {
  "mode": "flat", "cost": 0, "markupPercent": 200,
  "note": "语音 TTS / 克隆合成 / 语音识别（2026-10-03 决策 A：语音/音频线 ×5 → ×3；
           一律按上游**真实**点数计费）。对外价 = 上游实际点数
           （响应 usage.points_cost / actual_points，单位是点）× 3，单笔保底 > 0。
           实测：voice_tts/stt 上游真实 40 点 → 我方 120 点；
           tts_live 33 字上游真实 1.98 点 → 我方 5.94 点。"
}
```

折算：**0.18 点/字 = 180 点/千字**；`stt` 120 点/次；`clone_voice` 600 点/次。

### 6.2 通配规则（`media_services_33` 走这条）

```json
"*": {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
      "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}
```

实测 `music_timestamped_lyrics` 预扣 **60 点**，即本包 `timeline` 报的「60 点/次起」。

### 6.3 目录类只读接口

```json
"/api/v1/apps":  {"mode":"flat","cost":0,"markupPercent":0,"note":"★应用目录（只读）不计费（2026-10-04）…"}
"/api/v1/models":{"mode":"flat","cost":0,"markupPercent":0,"note":"★模型目录（只读）不计费（2026-10-04）…"}
```

---

## 七、本包口径与实测边界

| 项 | 本包口径 | 依据 |
|---|---|---|
| 每字点数 | 0.18（向上取整到 1 点） | `markupPercent=200` + 两个实测锚点 |
| `stt` | 120 点/次 | 规则 note 实测锚点 |
| `clone_voice` | 600 点/次 | 规则 note + `indextts` 条实测 200 × 3 |
| `timeline` | 60 点/次起 | 实测预扣 60 点 |
| 预扣 | `voice_tts/*` 150 点/次，`media_services_33/*` 60 点/次 | 实测流水 |
| 失败 | 全额退回 | 实测 `refund:task_failed:…` |

**还没实跑过的两处**（本轮零花费，留个明确的边界）：

1. `tts_async` / `tts` / `stt` / `clone_voice` 的**成功**返回结构。
   `tts_async` 的成功形态按平台文档是 `data.task_id` + 轮询后 `result.audio_url`；
   本包的解析器对 `audio_url` / `audioUrl` / `url` / `result.audio_url` 递归兜底，
   真跑一次就知道落在哪个键，`status --task-id … --json` 能看到原始结构。
2. 本地文件走 multipart 的字段名（`stt` 用 `audio`、`clone_voice` 用 `voices`）取自平台文档，
   本轮没发过带文件的请求。
