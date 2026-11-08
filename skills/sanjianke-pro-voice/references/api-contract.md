# 接口契约（实测原文，2026-11-07）

所有结论都来自 **零成本探针**：只读 GET + 故意坏参数的 POST。原文照抄，不做转述。

---

## 1. 身份与形态

| 项 | 值 |
|---|---|
| 网关 | `https://api.a7w.cn` |
| 应用 | `media_services_33`（Official 音频与辅助服务，app id 29） |
| 鉴权 | `Authorization: Bearer <key>` |
| 提交 | `POST /api/v1/apps/media_services_33/<接口code>`，`Content-Type: application/json` |
| 查询 | `GET /api/v1/tasks/<task_id>` |
| 成功 | `{"code":1,"msg":"success","data":{...}}` |
| 校验失败 | **HTTP 200** + `{"code":0,"msg":"input.<字段>: …","data":null}` |

> **判成功只能看 `code == 1`。** 参数校验失败也回 HTTP 200，状态码没有区分度。

`GET /api/v1/tasks/<不存在的 id>` 实测返回：

```json
{"code":0,"msg":"任务不存在","data":null}
```

---

## 2. 本包接的 8 个接口

| `--line` | 接口 code | 必填 | 常用可选 |
|---|---|---|---|
| `v2` | `elevenlabs_text_to_speech_multilingual_v2` | `text` `voice` | `speed` `style` `stability` `similarity_boost` `language_code` `timestamps` `previous_text` `next_text` |
| `turbo` | `elevenlabs_text_to_speech_turbo_2_5` | `text` `voice` | 同上 |
| `v3` | `elevenlabs_text_to_dialogue_v3` | `dialogue` | `stability` `language_code` |
| `gemini38` | `google_gemini_3_8_flash_tts` | `speakers` `dialogue_turns` | `temperature` `filler_words` |
| `gemini38lite` | `google_gemini_3_8_flash_lite_tts` | `speakers` `dialogue_turns` | `temperature` `filler_words` |
| `gemini25pro` | `google_gemini_2_5_pro_tts` | `speakers` `dialogue_turns` | `scene` `temperature` `sample_context` |
| `omni` | `gemini_omni_audio` | `name` `audio_id` | `example_dialogue` `voice_description` |
| `character` | `gemini_omni_character` | `image_urls` `descriptions` | `audio_ids` `character_name` |

同一应用下另外 21 个 `music_*` 接口属于 `sanjianke-suno-music`，本包不接。

---

## 3. 参数形态（探针原文）

### 3.1 `voice` 是**音色 ID**，不是名字

请求与返回（HTTP 200）：

```json
POST /api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
{"text": "hi", "voice": "bogus"}

{"code":0,"msg":"input.voice: 不在允许选项内","data":null}
```

`params_schema` 里 `voice` 是 **67 个 20 位 ID 的枚举**，名字只写在字段说明里：

```
EkK5I93UQWFDigLMpZcX - James - 沙哑、引人入胜、大胆
Z3R5wn05IrDiVCyEkUrK - Arabella - 神秘、富有情感
NNl6r8mD7vthiJatiJt1 - Bradford - 富有表现力、口齿清晰
…（共 67 条，`python3 scripts/run.py voices --line v2` 列全表）
```

### 3.2 `dialogue` 是**数组**，不是字符串

```json
POST /api/v1/apps/media_services_33/elevenlabs_text_to_dialogue_v3
{"dialogue": "x"}

{"code":0,"msg":"input.dialogue: 类型不正确","data":null}
```

正确形态（`params_schema`）：数组，每项 `{"text","voice"}`，`voice` 同样是 67 个 ID 之一；
**所有 `text` 加起来不得超过 5000 字符**。

```json
{"dialogue": [
  {"text": "你终于来了。", "voice": "EkK5I93UQWFDigLMpZcX"},
  {"text": "我一直在等你。", "voice": "Z3R5wn05IrDiVCyEkUrK"}
]}
```

### 3.3 `speakers` / `dialogue_turns` 都是**数组**

这两个字段的类型错了，ElevenLabs 那条线回的是字段级报错，Gemini 这条线回的是 HTTP 500：

```json
POST /api/v1/apps/media_services_33/google_gemini_3_8_flash_tts
{"speakers": "x", "dialogue_turns": "x"}

HTTP 500  {"code":0,"msg":"服务内部错误","data":null}
```

正确形态：

```json
{"speakers": [{"speaker_id": "Speaker 1", "voice_name": "Kore"}],
 "dialogue_turns": [{"speaker_id": "Speaker 1", "text": "门外有人。"}]}
```

- `speaker_id` 必须是 **「Speaker N」** 格式（`params_schema` 原文：「必须为「Speaker N」格式」）。
  本包把剧本里的角色名自动编号成 `Speaker 1..N`，映射会打出来。
- 3.8 两条线的 `voice_name` 有 **70 个**，默认 `Fola`；`speaker_id` 必填、`voice_name` 与
  `replica`（声音克隆，两段 WAV）**互斥**。
- 2.5 Pro 的 `voice_name` 只有 **30 个**，且 `accent` 也是必填（8 种口音），另有
  `pace`（4 档）/ `style`（6 种）/ `audio_profile`。
- 3.8 的每一句 `text` 可带 `<laugh>` 这类语气标签，40 个；逐句还能给 `style` 描述。

---

## 4. 价格：pricing 里**没有**这 8 条的专属规则

`GET /api/v1/pricing` 返回 115 条规则，逐条筛过：

```
keys with 'elevenlabs'    : []
keys with 'media_services': []
keys with 'apps/media'    : []
keys with 'gemini'        : []
keys with 'tts'           : ['/api/v1/apps/voice_tts/*', '/api/v1/apps/indextts/*']
```

所以这 8 条全部落通配：

```json
```

### 预冻结 = 60 点/条（实测）

四次坏参数 POST 的流水（`GET /user/balance/logs`）：

```
20:50:36  charge  -60  reserve_sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
20:50:37  refund  +60  refund:sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
20:50:38  charge  -60  reserve_sync:/api/v1/apps/media_services_33/elevenlabs_text_to_dialogue_v3
20:50:39  refund  +60  refund:sync:/api/v1/apps/media_services_33/elevenlabs_text_to_dialogue_v3
20:50:41  charge  -60  reserve_sync:/api/v1/apps/media_services_33/google_gemini_3_8_flash_tts
20:50:42  refund  +60  refund:sync_error:/api/v1/apps/media_services_33/google_gemini_3_8_flash_tts
20:50:43  charge  -60  reserve_sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
20:50:44  refund  +60  refund:sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
```

所以本包 `cost` 给的是 **60 点/条 的下限**，不是成交价：成交价 = 上游真实点数 × 2
（保底 50 点），得真跑一条才看得见。

---

## 5. 还没实测到的那一段（诚实标注）

`params_schema` 和文档只给了**请求**契约。文档页（`media-services-33-*`，28 篇）里
请求参数一栏写的是「以该应用说明为准」，**没有成功响应示例**。

因此本包对成功返回做**兼容解析**，不写死一种结构：

| 找什么 | 在哪找 |
|---|---|
| 任务号 | `data.task_id` / `data.taskId` / `data.id` / 顶层同名 |
| 音频地址 | 递归扫 `data` 与整个返回里所有 `*url` / `*audio*` 的 http(s) 值 |

两条都为空时，`speak` 会把原始返回打出来（前 600 字），并提示用 `task --task-id` 追。
`--json` 下 `taskId` 与 `audioUrls` 字段名固定，脚本可以照这两个字段取。

---

## 6. 免费面清单（本轮逐条验过）

| 接口 | 结论 |
|---|---|
| `GET /user/balance` | 200，返回 `available_points` / `frozen` |
| `GET /api/v1/apps` | 200，22 个应用 96 KB，规则 `cost:0` 免费；能确认 8 个端点已注册 |
| `GET /api/v1/pricing` | 200，裸对象（不套 `code`/`data`），115 条规则 |
| `GET /api/v1/tasks/<id>` | 200，假 id 回「任务不存在」，不扣费 |
| `POST …/media_services_33/<code>` | 坏参数：冻 60 → 校验/上游失败 → 全额退，净 0 |
| `GET /api/v1/apps/<app>` | **不要调用**，命中 `/apps/<app>/*` 通配计价，`sync:` 即时扣、不退 |
