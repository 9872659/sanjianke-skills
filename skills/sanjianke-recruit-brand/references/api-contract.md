# 接口契约（实测原文 · 2026-11-08）

本包用到的 8 条接口，全部在 `https://api.a7w.cn` 上，`Authorization: Bearer <KEY>`。
**1 元 = 100 点。** 单价一律取自 `GET /api/v1/pricing`（cost:0，可随时自己再查一遍）。

| # | 用途 | 方法 + 路径 | 计费口径 | 单价 |
|---|---|---|---|---|
| 1 | 数字人提交 | `POST /api/v1/apps/pic_lipsync/submit` | 按输入音频时长 x 上游 3 点/秒 x5 | **15 点/秒**（声明保底 50 点） |
| 2 | 数字人查询 | `POST /api/v1/apps/pic_lipsync/query` | 价目表与 submit 同 path | 口径见下 |
| 3 | 企业音色 TTS | `POST /api/v1/apps/voice_tts/tts` | 上游真实点数 x3 | 约 **0.18 点/字** |
| 4 | 音色克隆 | `POST /api/v1/apps/voice_tts/clone_voice` | 上游固定 200 点 x3 | **600 点/次** |
| 5 | 空镜成片 | `POST /api/v1/apps/full_video/submit` | 按秒 x 分辨率 | 480P 14 / 768P 28 / **1080P 60** / 2K 80 / 4K 80 |
| 6 | 出图 | `POST /api/v1/images/generations` | Images API 按张 | **6 点/张** |
| 7 | 配乐 | `POST /api/v1/apps/media_services_33/music_generate` | 落通配：上游 x2 | **50 点起/首** |
| 8 | 上传 | `POST /api/v1/upload` | 站主 2026-10-04 批准免费 | **0 点** |
| 9 | 查任务 | `GET /api/v1/tasks/<task_id>` | 价目表 cost:0 | **0 点** |

---

## 1 · `POST /api/v1/apps/pic_lipsync/submit`

一张人物图 + 一段文案（text 模式）或一段音频（audio 模式）→ 口播视频。**异步**，返回 `task_id`。

平台 schema 原文（字段名逐字）：

```json
{
  "mode":     {"enum": ["audio", "text"], "type": "string", "default": "audio",
               "description": "audio 为音频驱动；text 为文案驱动。"},
  "model":    {"enum": ["super-lipsync-pro"], "type": "string",
               "default": "super-lipsync-pro", "description": "图片数字人模型标识。"},
  "prompt":   {"type": "string", "description": "人物动作、表情和画面风格提示词。"},
  "content":  {"type": "string", "description": "text 模式必填，图片人物将使用参考音色朗读该文案。"},
  "quality":  {"enum": ["standard", "fast", "max"], "type": "string",
               "default": "standard", "description": "fast 快速模式；standard 标准模式；max 模式较慢，但是效果最好。"},
  "audio_url": {"type": "string", "required": true,
                "description": "audio 模式的驱动音频；text 模式的参考音色音频。"},
  "image_url": {"type": "string", "required": true, "description": "人物图片 URL。"}
}
```

要点：

- **`audio_url` 两种模式都必填**，含义不同：audio 模式是驱动音频，text 模式是**参考音色**。
- 图片建议正脸、清晰、单人；口型质量几乎完全取决于脸部分辨率与角度。

## 2 · `POST /api/v1/apps/pic_lipsync/query`

`{"task_id": "<提交返回的 id>"}`，同步返回状态与成片地址。

虽然 note 写「query 本身不计费」，但这条口径没有独立验证过。查进度一律走 `GET /api/v1/tasks/<task_id>`
（价目表 `cost:0`）。通用查询说不存在时，才用 `status --app pic_lipsync --yes` 显式走这条路。

---

## 3 · `POST /api/v1/apps/voice_tts/tts`

同步合成，短文本（500 字内）。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | string | 是 | 待合成文本，建议不超过 500 字符 |
| `reference_id` | string | 否 | 音色模型 ID（`clone_voice` 返回的 `model_id`）；多说话人可传 string[]（仅 s2-pro） |
| `model` | string | 否 | `s1` / `s2-pro`（默认 `s2-pro`） |
| `format` | string | 否 | `mp3`（默认）/ `wav` / `ogg` / `opus` / `pcm` |
| `sample_rate` | integer | 否 | 8000 / 16000 / 22050 / 44100（默认） |

返回：

```json
{"code": 1, "msg": "success",
 "data": {"audio_url": "https://…/tts_xxxxxxxx.mp3", "format": "mp3"}}
```

## 4 · `POST /api/v1/apps/voice_tts/clone_voice`

两种提交方式：JSON 传 `audio_url`，或 `multipart/form-data` 上传 `voices` 文件字段。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | **是** | 音色名称 |
| `audio_url` | string | 否 | 参考音频 URL（与上传文件二选一），mp3 / wav / ogg / flac |
| `description` | string | 否 | 音色描述 |
| `enhance_audio_quality` | boolean | 否 | 是否增强音频质量，默认 false |
| `visibility` | string | 否 | `public` / `unlist` / `private`（平台默认 private） |

返回 `data.model_id`，后续当 `reference_id` 用。参考音频建议 **10 秒 ~ 5 分钟**。

---

## 5 · `POST /api/v1/apps/full_video/submit`

本包提交的 body（空镜段）：

```json
{
  "model": "full-video",
  "content": [
    {"type": "text", "text": "竖屏公司实拍氛围空镜，开放办公区横移……"},
    {"type": "image_url", "role": "first_frame",
     "image_url": {"url": "https://oss.gpu.likeadmin.cn/openapi/…"}}
  ],
  "duration": 15,
  "resolution": "1080P",
  "ratio": "9:16",
  "aigc_watermark": false
}
```

- **单段 4~15 秒**，超过就拆两段提交，按总秒数计费。
- `ratio` 取 `9:16` / `16:9` / `3:4` / `1:1` / `adaptive`。
- 首帧图有域名白名单，见第 10 节。

## 6 · `POST /api/v1/images/generations`

```json
{"model": "gpt-image-2.6", "prompt": "手机竖屏实拍，明亮开放办公区……", "n": 1, "size": "1024x1536"}
```

- **6 点/张，与尺寸、质量、输出格式都无关**，按 `data` 里实际返回的张数计费。
- 返回默认是 `b64_json`，也可能给 `url`；本包两种都处理，自动落盘成 png。
- 图片链接有效期约 3 小时，请原样使用（追加查询参数会 404）。
- `/api/v1/images/generations` **不在 `/api/v1/pricing` 的键里** —— 它走 Images API 自己的计价层，
  所以 `catalog` 把它单列成 6 点/张，而不是读 `/pricing`。

## 7 · `POST /api/v1/apps/media_services_33/music_generate`

必需字段（来自 29 接口契约）：`model`、`custom_mode`、`instrumental`。

```json
{"model": "V6", "custom_mode": false, "instrumental": true,
 "prompt": "轻快电子加清楚鼓点，112 BPM，适合 45 秒岗位介绍，中段留口播空隙"}
```

`media_services_33` 在架 **29 个接口**（`GET /api/v1/apps` 可数），配乐取 `music_generate` 这一条。

## 8 · `POST /api/v1/upload`

`multipart/form-data`，字段名 **`file`**，**0 点**。返回：

```json
{"code": 1, "data": {"url": "https://oss.gpu.likeadmin.cn/openapi/…",
                     "path": "…", "name": "…", "size": 12345, "mime_type": "image/png"}}
```

上传是生成的前置动作，不是可计费服务（价目表 `/api/v1/upload` 的 `cost` 为 0）。

## 9 · `GET /api/v1/tasks/<task_id>`

```json
{"code": 0, "msg": "任务不存在", "data": null}
```

假 taskId 也是 `200 + code 0`，所以「路由在、不扣费」这条判据成立。任务存在时
`data` 里有 `status` / `videoUrl` / `cost` / `refund`。**价目表 cost:0，查多少次都是 0 点。**

---

## 10 · videoUrl / imageUrl 的域名白名单（实测报错原文）

```
400 url_not_allowed
  "videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
   或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）"
```

正确做法：先 `POST /api/v1/upload`（免费）→ 拿 `data.url` → 再提交。
**实测**：`https://example.invalid/x.mp4` → 400；`oss.gpu.likeadmin.cn/openapi/…`（upload 返回的）→ 201 建任务。

本包 `avatar` / `film` 在本地就预检这条白名单：给本地路径会自动 upload 换地址，给外站地址会先退回、不发请求。

---

## 11 · 计费原文（`GET /api/v1/pricing` 摘录，2026-11-08 现查）

### pic_lipsync

```json
"\/api/v1\/apps\/pic_lipsync\/submit": {
           ★ minPoints:50 目前是声明性字段（通用计费不读）。"
}
```

→ **本包口径：15 点/秒，按提交时给的秒数估；`minPoints` 只当声明看，不当兜底看。**

### voice_tts

```json
"\/api\/v1\/apps\/voice_tts\/*": {
           实测：voice_tts/stt 上游真实 40 点 → 我方 120 点；tts_live 33 字上游真实 1.98 点 → 我方 5.94 点。"
}
```

→ **本包口径：0.18 点/字。** `clone_voice` 上游固定 200 点 x3 = **600 点/次**。

### full_video

```json
"\/api\/v1\/apps\/full_video\/submit": {
  "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80},
  "note": "2026-11-06 站主定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80（1 元=100 点，价格已含利润，不再叠加上游倍率）"
}
```

### 通配与上传

```json
      "note": "★上传不计费（2026-10-04 站主批准）…计费引擎对 cost:0 有显式语义：ruleCost === 0 即视为免费路径。"}
```

---

## 12 · 探针禁区（2026-11-07 用 472 点买来的教训）

### 会真扣钱、且**不退**（`sync:` 即时结算）

```
❌ GET /api/v1/apps/<app>          ← 命中 /apps/<app>/* 的通配计价，按该应用 flat 单价扣
   dressing_diffusion   200 点/次
   nano_banana           72 点/次
   pic_lipsync           50 点起（minPoints 声明值）
```

实测流水（2026-11-07，读 schema 造成）：

```
19:35:08  -200  sync:/api/v1/apps/dressing_diffusion     ← 无退款
19:35:11   -72  sync:/api/v1/apps/nano_banana            ← 无退款
19:35:34  -200  sync:/api/v1/apps/dressing_diffusion     ← 无退款
```

### 会预扣、但失败**全额退**（`reserve_sync:`）

```
⚠️ POST /api/v1/apps/<app>/submit  缺必填参数
   → 先 reserve_sync 冻结，再参数校验失败 → refund 全额退
   · pic_lipsync 冻 250 · image_human 冻 250 · lipsync 冻 150 · seedance 冻 11,000
净额 0，但钱包被短暂动过。所以「缺必填参数会停在扣费之前」这条不成立。
```

### 完全安全（已逐条实测）

```
✅ GET  /api/v1/models
✅ GET  /api/v1/apps                  ← 列表，价格表 cost:0
✅ GET  /api/v1/pricing               ← 裸对象，不套 code/data
✅ GET  /api/v1/tasks/<task_id>       ← 200 / "任务不存在"
✅ GET  /api/v1/videos/<task_id>      ← 400 task_not_exist
✅ GET  /user/balance
✅ GET  /user/balance/logs            ← limit 生效，上限 1000
✅ POST /api/v1/upload                ← multipart 字段名 file，免费
✅ POST /api/v1/images/generations {"model":"gpt-image-2.6","prompt":""} → 422
✅ POST /api/v1/video/<tier>  {}      ← 视频线在参数校验就停（实测 10 个 tier 全 400）
✅ POST /api/v1/video/viapi/<tier> {} → 400 empty_url
```

### 判断端点是否存在的免费判据

| 返回 | 含义 |
|---|---|
| `400` / `422` + 参数报错 | **存在**，停在校验层 |
| `404` + HTML | **未注册** |
| `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | **应用层兜底话术，不可信**（假代号也返回同一句） |
| `502` + `InvalidMpsUser` | 路由存在，**上游凭据坏了** |

---

## 13 · 本包 `doctor` 实际发的 9 个请求（全部 0 点）

| # | 请求 | 预期 |
|---|---|---|
| 1 | `GET /user/balance/logs?limit=1`（自检前留底） | 200 |
| 2 | `GET /user/balance` | 200 + `available_points` |
| 3 | `GET /api/v1/apps` | 200，22 个应用 |
| 4 | `GET /api/v1/pricing` | 200，115 个价目条目 |
| 5 | `POST /api/v1/images/generations {"model":"gpt-image-2.6","prompt":""}` | **422** prompt 至少 1 字符 |
| 6 | `POST /api/v1/video/viapi/enhance {}` | **400** `empty_url` |
| 7 | `GET /api/v1/tasks/sanjianke-recruit-doctor-probe` | 200 + `code 0` |
| 8 | `POST /api/v1/upload`（不带 file） | 200 + 「请使用 file 字段提交一个文件」 |
| 9 | `GET /user/balance/logs?limit=1`（自检后对账） | 与第 1 条一致 → 本轮 0 点 |

`pic_lipsync` 的「在架」结论来自第 3 条的 `apis` 列表（`submit` / `query` 都在）+ 第 4 条的价目条目，
**一条 `GET /api/v1/apps/pic_lipsync` 都没发，一条 `/submit` 也没发。**
