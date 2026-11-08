# 接口契约 · media_services_33（实测原文）

> 全部来自网关 `GET /api/v1/apps/media_services_33` 的 `params_schema` 原文，
> 以及 2026-11-07 在 api.a7w.cn 上的**零成本探针**实测。本文件不含任何虚构字段。

---

## 1. 基本信息

| 字段 | 内容 |
|---|---|
| 应用名称 | Official 音频与辅助服务 |
| 应用代号 | `media_services_33` |
| 接口总数 | **29**（本包接其中 7 个 Suno 音乐接口） |
| 请求方式 | `POST` |
| 请求路径 | `/api/v1/apps/media_services_33/<接口code>` |
| 鉴权 | `Authorization: Bearer <key>` + `Content-Type: application/json` |
| 调用模式 | 异步（提交拿 `task_id`，再查任务） |
| 任务查询 | `GET /api/v1/tasks/<task_id>` |

### 成功判据（重要）

网关**参数校验失败也返回 HTTP 200**，只是 `code=0` + `data=null`：

```json
{"code":0,"msg":"input.custom_mode: 缺少必填参数；input.instrumental: 缺少必填参数；input.model: 缺少必填参数","data":null}
```

成功形如：

```json
{"code":1,"msg":"success","data":{...}}
```

**只看 HTTP 状态码会把校验失败当成成功**，必须看 `code`。

---

## 2. 本包接的 7 个接口

### 2.1 `music_generate` 生成音乐

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | ✅ | 枚举：`V4` `V4_5` `V4_5PLUS` `V4_5ALL` `V5` `V5_5` `V6` `V6_MINI` `V6_WILD`；官方建议用 `V6` / `V6_MINI` / `V6_WILD`，其余标注已废弃 |
| `custom_mode` | boolean | ✅ | `true` 自定义（按歌词+风格），`false` 灵感（按提示词） |
| `instrumental` | boolean | ✅ | 是否纯音乐（无人声） |
| `style` | string | — | 风格标签，V6 系最多 1000 字符 |
| `title` | string | — | 歌名，自定义模式下必填，≤80 字符 |
| `lyrics` | string | — | 歌词，V6 系最多 5000 字符 |
| `prompt` | string | — | 灵感模式的创意描述；自定义模式下会**严格当歌词唱** |
| `duration` | number | — | 10–360 秒（`custom_mode=true` 且 V6 系有效） |
| `variety` | number | — | 0–4 整数，默认 1 |
| `negative_tags` | string | — | 要避开的风格 |
| `vocal_gender` | string | — | `m` / `f` |
| `persona_id` | string | — | 套用 Persona / Voice |
| `style_weight` `audio_weight` `weirdness_constraint` | number | — | 0–1，两位小数 |
| `audio_urls` `image_urls` `video_urls` | array | — | 参考素材，仅 `custom_mode=false` 生效 |

schema 原文的补充约束：**自定义模式下 `style` / `lyrics` / `negative_tags` 至少给一项**；
**非自定义模式下 `image_urls` / `video_urls` / `audio_urls` / `style` / `lyrics` 至少给一项**。
本包在本地就按这两条拦（否则可能提交成功再在上游失败，白扣费）。

### 2.2 `music_extend` 延长音乐

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | ✅ | 同上（枚举顺序略异，取值相同） |
| `audio_id` | string | ✅ | **必须是本平台产出的** `audio_id` |
| `continue_at` | number | — | 从原曲第几秒接下去，大于 0 且小于总时长 |
| `style` `title` `lyrics` `prompt` `variety` `persona_id` `negative_tags` `vocal_gender` | — | — | 同生成音乐 |
| `instrumental` | boolean | — | 默认 `false`；为 `true` 时**禁止**传 `lyrics` / `prompt` / `vocal_gender` |

### 2.3 `music_sounds` 生成音效

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | ✅ | 枚举：`V5` `V5_5` `V6` `V6_WILD` `V6_MINI` |
| `prompt` | string | ✅ | 声音描述，≤500 字符 |
| `sound_key` | string | — | 调性，默认 `Any`；可选 `C`…`Bm` 共 24 个 |
| `sound_tempo` | integer | — | 1–300，schema 写「不传就是 Auto」 |
| `sound_loop` | boolean | — | 是否循环 |
| `grab_lyrics` | boolean | — | 完成后顺手抓歌词字幕 |

**实测坑**：省略 `sound_tempo` 时网关回 `input.sound_tempo: 类型不正确`，所以本包**总是显式传**
（默认 120）。这也是「Auto」在本网关不可达的原因。

### 2.4 `music_generate_voice` 自建音色

schema 里没有必填项，实际按 `action` 分两步：

| `action` | 必填 | 说明 |
|---|---|---|
| `prepare` | `voice_url` + `vocal_start_s` + `vocal_end_s` | 生成需要本人朗读的验证短句；`vocal_end_s` 必须大于 `vocal_start_s` |
| `create` | `verify_url` | 提交本人录制的验证音频；默认值就是 `create` |

其余可选：`voice_name`、`language`（`en` `zh` `es` `fr` `pt` `de` `ja` `ko` `hi` `ru`）、
`style`、`description`、`singer_skill_level`（`beginner` `intermediate` `advanced` `professional`）。

### 2.5 `music_timestamped_lyrics` 带时间戳歌词

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | string | ✅ | 生成音乐 / 延长音乐返回的 `task_id` |
| `audio_id` | string | ✅ | 那首歌的 `audio_id`（完成后的回调数据里给） |

### 2.6 `music_recovery_audio` 恢复音频

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | string | ✅ | 原音乐任务的 `task_id` |

### 2.7 `music_generate_persona` 生成 Persona

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | Persona 名称 |
| `task_id` | string | ✅ | 原任务 `task_id` |
| `audio_id` | string | ✅ | 原曲 `audio_id` |
| `description` | string | ✅ | 流派 / 情绪 / 乐器 / 人声特质 |
| `style` | string | — | 补充风格标签 |
| `vocal_start` | number | — | 默认 0；与 `vocal_end` 的差必须在 10–30 秒 |
| `vocal_end` | number | — | 默认 30 |

---

## 3. 另外 22 个接口（不在本包）

Gemini / ElevenLabs 语音线：
`google_gemini_3_8_flash_lite_tts`、`google_gemini_3_8_flash_tts`、`google_gemini_2_5_pro_tts`、
`gemini_omni_audio`、`gemini_omni_character`、
`elevenlabs_text_to_dialogue_v3`、`elevenlabs_text_to_speech_multilingual_v2`、
`elevenlabs_text_to_speech_turbo_2_5`。

Suno 音乐线里本包未接的 14 个：
`music_check_voice`、`music_replace_section`、`music_generate_lyrics`、`music_boost_music_style`、
`music_cover_generate`、`music_add_vocals`、`music_separate_vocals`、`music_generate_midi_from_audio`、
`music_mashup`、`music_create_music_video`、`music_upload_and_extend_audio`、
`music_upload_and_cover_audio`、`music_add_instrumental`、`music_convert_to_wav_format`。

它们仍是 `POST /api/v1/apps/media_services_33/<code>` 同一形态，参数在 `GET /api/v1/apps/media_services_33` 的
`params_schema` 里能直接读到。

---

## 4. 零成本探针实测（2026-11-07）

用「必然被参数校验拦下」的 body 逐个打，全部 `code=0` + `data=null`，**没有建任何任务**：

| 接口 | 请求 body | HTTP | 原始返回 |
|---|---|---|---|
| `music_generate` | `{}` | 200 | `input.custom_mode: 缺少必填参数；input.instrumental: 缺少必填参数；input.model: 缺少必填参数` |
| `music_generate` | `{"model":"bogus"}` | 200 | `input.custom_mode: 缺少必填参数；input.instrumental: 缺少必填参数；input.model: 不在允许选项内` |
| `music_extend` | `{"model":"V6","audio_id":"sanjianke-doctor-probe"}` | 200 | `请使用本平台返回的任务或资源标识` |
| `music_sounds` | `{"model":"V6","prompt":"probe","sound_key":"Zzz","sound_tempo":120}` | 200 | `input.sound_key: 不在允许选项内` |
| `music_generate_voice` | `{"action":"probe"}` | 200 | `音色操作步骤无效` |
| `music_timestamped_lyrics` | `{}` | 200 | `input.task_id: 缺少必填参数；input.audio_id: 缺少必填参数` |
| `music_recovery_audio` | `{}` | 200 | `input.task_id: 缺少必填参数` |
| `music_generate_persona` | `{}` | 200 | `input.task_id: 缺少必填参数；input.audio_id: 缺少必填参数；input.name: 缺少必填参数；input.description: 缺少必填参数` |

### 任务查询接口（实测存在）

```
GET /api/v1/tasks/sanjianke-probe-not-a-real-task
HTTP 200
{"code":0,"msg":"任务不存在","data":null}
```

判据：HTTP 200 + JSON `code` + 中文 `msg`，**而不是 404 HTML** —— 说明路由存在、只是这个 id 没有。

`GET /api/v1/me/tasks` 同样可读（返回 `tasks[]`，含 `taskId` / `status` / `chargedPoints` / `feeYuan`）。

---

## 5. 价格规则（`GET /api/v1/pricing` 原文）

`pricing` 共 115 条规则，**没有 `media_services_33` 的任何条目**（相关键只有 `*`、
`/api/v1/apps/music_generation/*` 等，后者是另一个应用）。所以本应用落通配：

```json
```

对外点数 = `max(50)`。上游真实点数在任务详情的 `usage` 里
（本仓同源应用 `music_generation` 的文档示例为 65 点/次，**仅供换算参考，不是本应用的报价**）。

---

## 6. 返回结构与解析

提交成功（本包实测只见到校验失败，成功形态取自同源 Suno 应用文档）：

```json
{"code":1,"msg":"success","data":{"task_id":"task_xxx","status":"processing"}}
```

任务完成：

```json
{"code":1,"msg":"success","data":{
  "status":"completed",
  "result":{"audio_url":"https://…","data":[{"id":"audio_xxx","title":"…",
            "duration":152.3,"lyric":"[主歌]…","audio_url":"https://…"}]},
  "usage":{"points_cost":65}}}
```

各字段位置在不同封装里可能略有差异，`scripts/run.py` 的 `find_audio` 会递归找
`audio_url` / `url` 与 `audio_id` / `id`，并对结果去重；解析不到时原样打印 JSON 不吞掉。
