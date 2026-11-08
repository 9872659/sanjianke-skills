# 接口契约（实测原文 + live 定价，2026-11-07）

四条能力线共用一套平台外壳：

```
接口根地址   https://api.a7w.cn/api/v1
提交         POST /apps/{app}/{api}           JSON，返回 data.task_id
文生图       POST /images/generations          OpenAI Images API 兼容，同步出图
任务查询     GET  /tasks/{task_id}             只读、免费
价目         GET  /pricing                     裸对象，不套 code/data
临时上传     POST /upload                      multipart 单字段 file（免费）
余额         GET  /user/balance
流水         GET  /user/balance/logs?limit=1000   上限 1000 条
```

| 环节 | 端点 | 单价 |
|---|---|---|
| 课件图 | `POST /api/v1/images/generations` | 6 点/张 |
| 课件出片 | `POST /api/v1/apps/image_human/submit` | 10 / 15 / 30 / 60 点/输入秒 |

---

## 0. 本轮实测证据（0 点）

```
GET  /user/balance                          HTTP 200
GET  /api/v1/apps                           HTTP 200，data[] 22 个应用
                                             voice_tts      apis: tts_live / clone_voice / tts / tts_async / stt / list_voices
                                             pic_lipsync    apis: submit / query
                                             image_human    apis: submit / query
GET  /api/v1/pricing                        HTTP 200，115 条规则
GET  /api/v1/tasks/probe-no-such-task       HTTP 200 {"code":0,"msg":"任务不存在"}
POST /api/v1/images/generations {"model":"gpt-image-2.6","prompt":""}
                                            HTTP 422 prompt: String should have at least 1 character
POST /api/v1/upload（不带 file）             HTTP 200 {"code":0,"msg":"请使用 file 字段提交一个文件"}
GET  /user/balance/logs?limit=1             条数与最新一条时间前后不变
```

`doctor` 只发以上只读请求 + 一次 422 + 一次空上传，**没有任何 submit**。

---

## 1. `images/generations`（课件图）

`POST /api/v1/images/generations`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | 是 | 固定 `gpt-image-2.6` |
| `prompt` | string | 是 | 提示词；空串返回 422，不扣费 |
| `n` | int | 否 | 1–4，默认 1 |
| `size` | string | 否 | `auto` / `1k` / `2k` / `4k` / `宽x高`；本包默认 `1536x864`（16:9） |
| `output_format` | string | 否 | `png` / `jpeg` / `webp` / `gif`，默认 `png` |

返回（两种形态都处理）：

```jsonc
{"created": 1762..., "data": [{"b64_json": "iVBORw0KGgo..."}]}
{"created": 1762..., "data": [{"url": "https://..."}]}
```

计费：**6 点/张**，与尺寸、质量、输出格式无关；按 `data` 里实际返回的张数计费。
参数错误 / 请求失败 / 没返回图片 → 不扣费。

> 端点必须带 `/api`：`POST /v1/images/generations` 也会出图，但会忽略 model 落到网关
> 默认应用（`nano_banana`，72 点/次）。本包把正确路径写死在代码里。

---

## 2. `voice_tts/tts_async`（分节配音）

`POST /api/v1/apps/voice_tts/tts_async`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | string | **是** | 待合成文本，异步接口适合长文本（约 10000 字符内） |
| `model` | string | 否 | `s1` / `s2-pro`，默认 `s2-pro` |
| `format` | string | 否 | `wav` / `pcm` / `mp3` / `opus`，默认 `mp3` |
| `reference_id` | string | 否 | 音色模型 ID（克隆音色返回的 model_id） |
| `prosody` | object | 否 | `speed` / `volume` / `normalize_loudness` |
| `callback_url` | string | 否 | 给了走回调；不给就轮询 `GET /tasks/{id}` |
| `normalize` | boolean | 否 | 文本规范化，默认 `true` |

返回：

```json
{"code":1,"msg":"success","data":{"task_id":"tsk_xxxxxxxxxxxx",
 "status":"pending","app":"voice_tts","api":"tts_async"}}
```

计费（`/pricing` 命中 `/api/v1/apps/voice_tts/*`）：

```json
```

⇒ 本包按 **0.18 点/字**估算（33 字 → 5.94 点折出来），单笔按 6 点起。

### 同账户还有 29 条音频接口（`media_services_33`）

同一账户的 `media_services_33` 应用还挂着 29 条音频接口，包括 ElevenLabs 多语言 TTS、
Gemini 2.5 / 3.8 文生语音、Suno 音乐与音色、人声分离、WAV 转换等。
本包选 `voice_tts/tts_async` 的理由：长文本、异步、按字数便宜、一口价口径清楚。
换多语言音色时对应的是
`POST /api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2`，
必填 `text` + `voice`，可选 `speed` / `style` / `stability` / `language_code` / `timestamps`。
本包不包装这 29 条，避免和音频能力包重复。

---

## 3. `pic_lipsync/submit`（一图口播）

`POST /api/v1/apps/pic_lipsync/submit`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `image_url` | string | **是** | — | 人物 / 讲师图片 URL |
| `audio_url` | string | **是** | — | `audio` 模式是驱动音频；**`text` 模式是参考音色** |
| `mode` | string | 否 | `audio` | `audio` 音频驱动 / `text` 文案驱动 |
| `content` | string | text 模式必填 | — | 图片人物用参考音色朗读的文案 |
| `quality` | string | 否 | `standard` | `standard` / `fast` / `max`（**档位真名**）|
| `model` | string | 否 | `super-lipsync-pro` | 枚举只有这一个值 |
| `prompt` | string | 否 | — | 人物动作、表情、画面风格 |

实测报错原文：

```json
{"code":0,"msg":"请提供 image_url","data":null}
{"code":0,"msg":"text 模式请提供 audio_url 作为参考音色","data":null}
```

计费（`/pricing`）：

```json
```

⇒ 对外 **15 点/秒**，单笔 50 点起。本包 `talk` 按 15 点/秒预估，`--quality` 必填。

---

## 4. `image_human/submit`（课件图 + 配音 → 口播视频）

`POST /api/v1/apps/image_human/submit`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_url` | string | **是** | 课件 / 讲师图 URL |
| `ref_file_url` | string | **是** | 驱动音频 URL；平台按该音频时长计费 |
| `duration` | number | 强烈建议 | 输入音频秒数；**给了它价格才被费率卡锁死** |
| `mode` | string | 强烈建议 | `fast` / `standard` / `2k` / `4k` |
| `resolution` | string | 否 | `2k` / `4k`，`mode` 的兼容别名 |
| `prompt` | string | 否 | 画面提示词 |

能力限制（平台字段原文）：`max_reference_images = 1`、`max_reference_audios = 0`、
`max_reference_videos = 0`。

### 默认档位自相矛盾（本包用必填参数堵死）

| 来源 | 字段 | 值 |
|---|---|---|
| `params_schema.mode.default` | 出片 | `standard` |
| `/pricing` 的 `defaultModel` | 计费 | `fast` |

不显式传 `mode` 时：**出片按 standard、收钱按 fast**（15 vs 10 点/秒）。
所以本包 `screen --mode` 必填，永不下发省略 mode 的请求。

### 计费（live 定价原文）

```json
 "modelRates":{"fast":{"*":10},"standard":{"*":15},"2k":{"*":30},"4k":{"*":60}},
 "defaultModel":"fast"}
```

---

## 5. 上传：本地素材变「公网可拉」

`POST /api/v1/upload`，`multipart/form-data`，字段名 `file`，**免费**。

```json
{"code":1,"msg":"success","data":{"url":"https://oss.gpu.likeadmin.cn/openapi/…",
 "path":"…","name":"buoyancy-s01.png","size":123456,"mime_type":"image/png"}}
```

返回地址归属 `oss.gpu.likeadmin.cn/openapi/`，有效期约 24 小时，可直接喂给
`image_url` / `audio_url` / `file_url` / `ref_file_url`。

上游对媒体地址有白名单（实测报错原文）：

```
400 url_not_allowed
  "videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
   或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）"
```

⇒ 本地文件先 `upload` 再提交；外站直链先在本地预检。

---

## 6. 任务查询：只走 `GET /api/v1/tasks/{id}`

| 路径 | 形态 | 计费 | 本包 |
|---|---|---|---|
| `GET /api/v1/tasks/{task_id}` | 平台任务线 | **免费**（只读） | ✅ 唯一轮询路径 |
| `POST /api/v1/apps/{code}/query` | 应用级查询 | **每轮询一次就是一次的钱** | ⛔ 在 `http_json` 里拦死 |

历史流水（`GET /user/balance/logs`，2026-11-03 至 11-07）：

```
sync:/api/v1/apps/nano_banana/query      108 次   -72 点/次   合计 -7,776 点
```

`status` 枚举：`pending` / `processing` / `completed` / `failed` / `cancelled`。
地址不在固定字段，按 `video_url` / `output_url` / `artifactUrl` 递归扫 http 字符串更稳。

---

## 7. 平台信封

```jsonc
// 成功
{"code":1,"msg":"success","data":{"task_id":"task_xxx","frozen_points":"17.52"}}
// 参数 / 计费错误（HTTP 依然是 200）
{"code":0,"msg":"请提供 image_url","data":null}
// 网关错误对象
{"error":{"message":"点数余额不足","type":"insufficient_points","code":"insufficient_points"}}
```

判据：`code == 1` 且 `data` 非空才算成功；其余取 `msg` / `message` 当错误文案。

---

## 8. 🔴 应用层 submit 是「先预扣、后验参」

`GET /user/balance/logs` 实测流水（时间 UTC）：

```
11:37:01Z  冻结/预扣   -250  ref=reserve_sync:/api/v1/apps/pic_lipsync/submit
11:37:02Z  退款       +250  ref=refund:sync:/api/v1/apps/pic_lipsync/submit
11:37:16Z  冻结/预扣   -250  ref=reserve_sync:/api/v1/apps/image_human/submit
11:37:19Z  退款       +250  ref=refund:sync:/api/v1/apps/image_human/submit
09:01:37Z  冻结/预扣   -150  ref=reserve_sync:/api/v1/apps/voice_tts/list_voices
```

**连「缺 image_url」这种必然被校验拦下的请求，也是先扣再退。** 净额 0，但钱包被真动过。
所以：

1. `doctor` 只发只读请求，端点存在性用 `/apps` + `/pricing` 证明；
2. 任何 submit 只出现在付费子命令里，且必须先过 `--budget` 与 `--yes` 两道闸门；
3. `GET /api/v1/apps/<app>`（单个应用）命中通配计价即时扣费且不退 —— 本包在
   `guard_path` 里拦死，只允许 `GET /api/v1/apps` 列表。
