# 接口契约（实测原文）

> 本包的 4 条能力线都走 `api.a7w.cn`，7 个端点全部实测可达。
> 记录时间：2026-11-08。单价来自 `GET /api/v1/pricing` 现查，1 元 = 100 点。
> 本轮**零扣费验证**：只发只读 GET 与空表单上传，未真实提交任何生成任务。

---

## 0. 一屏总览

| 工位 | 方法 | 路径 | 计费规则（pricing 原文口径） |
|---|---|---|---|
| 旁白配音 | POST | `/api/v1/apps/voice_tts/tts_async` | `markupPercent: 200` → 对外 = 上游实际点数 × 3 |
| 数字人口播 | POST | `/api/v1/apps/pic_lipsync/submit` | `markupPercent: 400` → 对外 = 上游实际点数 × 5 |
| 配乐 | POST | `/api/v1/apps/media_services_33/music_generate` | **未配价**，按默认预冻 60 点/次 |
| 卡点字幕 | POST | `/api/v1/apps/media_services_33/music_timestamped_lyrics` | **未配价**，按默认预冻 60 点/次 |
| 封面 / 片头 / 预告 | POST | `/api/v1/apps/full_video/submit` | `per_second` + `resolutionRates`（见 §5） |
| 上传素材 | POST | `/api/v1/upload` | `flat, cost: 0`（免费） |
| 查任务 | GET | `/api/v1/tasks/{task_id}` | 只读，免费 |

应用注册表（`GET /api/v1/apps` 实测，共 22 个应用）：

```
full_video          submit / query（两个都 POST）
voice_tts           tts_live / clone_voice / tts / tts_async / stt（POST）· list_voices（GET）
pic_lipsync         submit / query（两个都 POST）
media_services_33   29 个接口，全部 POST
```

---

## 1. 旁白配音 · `voice_tts/tts_async`

`POST /api/v1/apps/voice_tts/tts_async` · 异步，返回 `task_id`

**本包提交的 body**

```json
{"text": "她扫了三年地，转身在董事会上叫出了所有人的名字",
 "format": "mp3",
 "reference_id": "<音色模型 ID，可选>"}
```

**平台 schema 要点**

| 字段 | 必填 | 说明 |
|---|---|---|
| `text` | 是 | 待合成文本，长文本上限约 10000 字符 |
| `model` | 否 | `s1` / `s2-pro`，默认 `s2-pro` |
| `format` | 否 | `wav` / `pcm` / `mp3` / `opus`，默认 `mp3` |
| `reference_id` | 否 | 音色模型 ID；单说话人传 string，多说话人可传 string[]（仅 s2-pro） |
| `callback_url` | 否 | 给了就回调，不给就轮询 `GET /tasks/{task_id}` |
| `prosody` / `speed` / `sample_rate` / `chunk_length` | 否 | 语调、采样率、分块长度 |

**计费**

- 平台字段价：输入 50 点 / 1k tokens（租户价），`fixed_price=0.0200`
- 对外：`markupPercent: 200`，即**上游实际点数 × 3**
- 本包估价：**0.18 点/字**（350 字 = 63 点）。真实扣费看 `usage.points_cost`

**响应**

```json
{"code": 1, "msg": "success",
 "data": {"task_id": "tsk_xxxxxxxx", "status": "pending",
          "app": "voice_tts", "api": "tts_async"}}
```

---

## 2. 数字人口播 · `pic_lipsync/submit`（mode=text）

`POST /api/v1/apps/pic_lipsync/submit` · 异步，返回 `task_id`

**本包提交的 body**

```json
{"mode": "text",
 "model": "super-lipsync-pro",
 "quality": "standard",
 "content": "她扫了三年地，转身在董事会上叫出了所有人的名字",
 "audio_url": "https://oss.gpu.likeadmin.cn/openapi/.../*.mp3",
 "image_url": "https://oss.gpu.likeadmin.cn/openapi/.../*.jpg"}
```

**平台 schema 原文（逐字）**

```json
{
  "mode": {"enum": ["audio", "text"], "type": "string", "default": "audio",
           "required": false, "description": "audio 为音频驱动；text 为文案驱动。"},
  "model": {"enum": ["super-lipsync-pro"], "type": "string",
            "default": "super-lipsync-pro", "required": false},
  "prompt": {"type": "string", "required": false,
             "description": "人物动作、表情和画面风格提示词。"},
  "content": {"type": "string", "required": false,
              "description": "text 模式必填，图片人物将使用参考音色朗读该文案。"},
  "quality": {"enum": ["standard", "fast", "max"], "type": "string",
              "default": "standard", "required": false,
              "description": "fast 快速模式；standard 标准模式；max 模式较慢，但是效果最好。"},
  "audio_url": {"type": "string", "required": true,
                "description": "audio 模式的驱动音频；text 模式的参考音色音频。"},
  "image_url": {"type": "string", "required": true, "description": "人物图片 URL。"}
}
```

**三条要点**

1. `mode=text` 的 `audio_url` 不是驱动音频，是**参考音色**。文案由 `content` 给。
2. 档位参数真名是 `quality`（`standard` / `fast` / `max`），`mode` 只切音频驱动 / 文案驱动。
3. 按输入音频时长计费 —— `mode=text` 的时长由 `content` 长度决定，预估按秒数 × 单价算。

**计费**

- `markupPercent: 400`（×5），`minPoints: 50`
- pricing note 原文：上游按 `standard` 档 **3 点/秒** 收，我方 = 上游实际点数 × 5 = **15 点/秒**
- `minPoints: 50` 是**声明性字段**，通用计费不读它（只有 `VOICE_CLONE.minPoints` 生效）

---

## 3. 配乐 · `media_services_33/music_generate`

`POST /api/v1/apps/media_services_33/music_generate`

**必填**：`model` / `custom_mode` / `instrumental`

**本包提交的 body**

```json
{"model": "suno", "custom_mode": false, "instrumental": true,
 "title": "S01E03", "prompt": "短剧配乐 · 悬疑推进 · 45 秒", "duration": 45}
```

**可选字段（schema 原文）**：`style` / `title` / `lyrics` / `prompt` / `variety` /
`duration` / `audio_urls` / `image_urls` / `persona_id` / `video_urls` / `audio_weight` /
`style_weight` / `vocal_gender` / `negative_tags` / `persona_model` / `weirdness_constraint`

**计费：未配价**

`GET /api/v1/pricing` 里 **一条 `media_services_33` 规则都没有**（115 个条目全查过）。
行为是走默认预冻。实测流水（2026-11-07 ~ 11-08）：

```
reserve_sync:/api/v1/apps/media_services_33/music_generate             -60
refund:sync:/api/v1/apps/media_services_33/music_generate              +60
reserve_sync:/api/v1/apps/media_services_33/music_extend               -60
refund:sync:/api/v1/apps/media_services_33/music_extend                +60
reserve_sync:/api/v1/apps/media_services_33/music_sounds               -60
refund:sync:/api/v1/apps/media_services_33/music_sounds                +60
reserve_sync:/api/v1/apps/media_services_33/music_timestamped_lyrics   -60
refund:sync:/api/v1/apps/media_services_33/music_timestamped_lyrics    +60
```

净额 0（那几次都失败了），但**每次调用都会先冻 60 点**。所以本包按 60 点/条入账。
`model` 的取值按平台音乐线文档，示例值 `suno`；拿不准就先 `--dry-run` 看 body 再提交。

---

## 4. 卡点字幕 · `media_services_33/music_timestamped_lyrics`

`POST /api/v1/apps/media_services_33/music_timestamped_lyrics`

**必填**：`task_id`、`audio_id`（就是上一步 `music_generate` 返回的两个值）

```json
{"task_id": "<配乐 task_id>", "audio_id": "<配乐 audio_id>"}
```

出的是**带时间戳的歌词**，用于卡点字幕与时间轴对齐。计费同 §3：未配价，先冻 60 点。
本包在 `beat` 工位强制要求 `--music-task` 与 `--music-audio`，缺任何一个在本地就退回（exit 2）。

同一应用的 ElevenLabs 配音线（走 `media_services_33` 时同样未配价）：

| 接口 | 必填 | 可选 |
|---|---|---|
| `elevenlabs_text_to_speech_multilingual_v2` | `text`、`voice` | `speed` / `style` / `stability` / `timestamps` / `similarity_boost` / `language_code` / `previous_text` / `next_text` |
| `elevenlabs_text_to_speech_turbo_2_5` | `text`、`voice` | 同上 |
| `elevenlabs_text_to_dialogue_v3` | `dialogue` | `stability` / `language_code` |

> `timestamps` 打开后拿到的字级时间轴可以替代 `beat` 工位，出多语言版本时更省一步。

---

## 5. 封面 / 片头 / 预告 · `full_video/submit`

`POST /api/v1/apps/full_video/submit` · 有**专属按秒定价**

**本包提交的 body**

```json
{"model": "full-video", "ratio": "9:16", "duration": 4, "resolution": "480P",
 "content": [{"type": "text", "text": "S01E03 片头 · 她扫了三年地"}]}
```

**平台 schema 原文（逐字）**

```json
{
  "model": {"type": "string", "default": "full-video", "required": false},
  "ratio": {"type": "string", "default": "16:9", "required": false,
            "description": "视频画幅比例；图生视频可使用 adaptive。"},
  "content": {"type": "array", "required": true,
              "description": "内容列表，须包含文本项；可按模式传入首帧、尾帧或参考媒体。"},
  "duration": {"type": "integer", "default": 4, "minimum": 4, "maximum": 15,
               "required": false, "description": "生成时长，单位秒，范围 4 到 15。"},
  "resolution": {"enum": ["480P", "768P", "1080P", "2K", "4K"], "type": "string",
                 "default": "480P", "required": false},
  "aigc_watermark": {"type": "boolean", "default": false, "required": false,
                     "description": "是否添加生成标识。"}
}
```

**定价（pricing `resolutionRates` 原文，单位：点/秒）**

| 分辨率 | 480P | 768P | 1080P | 2K | 4K |
|---|---|---|---|---|---|
| 点/秒 | **14** | **28** | **60** | **80** | **80** |
| 折合元/秒 | 0.14 | 0.28 | 0.60 | 0.80 | 0.80 |

note 原文：「2026-11-06 站主定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80
（1 元=100 点，价格已含利润，不再叠加上游倍率）」。

**规则约束**

- 时长只收 **4–15 秒整数**
- 首帧与尾帧各最多 1 张；参考图片最多 9 张；参考视频与参考音频各最多 3 个
- 首尾帧模式与参考媒体模式互斥；参考媒体模式至少要 1 张参考图或 1 个参考视频
- 768P / 1080P / 2K 的文本总长上限 5000 字符，其余分辨率 7000
- 默认前 5 张 `reference_image` 免费，超出每张加 20 点

> **诚实边界**：`content` 数组项的具体键名以平台返回为准。本轮 0 点验证，
> 只确认了端点存在、定价规则、`duration` 与 `resolution` 的约束，未真实提交成片。

---

## 6. 上传 · `POST /api/v1/upload`

`multipart/form-data`，字段名 **`file`**，`flat cost: 0`（免费，pricing note 原文：
「上传是生成的前置动作、不是可计费服务」）。

**响应**

```json
{"code": 1, "msg": "success",
 "data": {"url": "https://oss.gpu.likeadmin.cn/openapi/18/20261108/xxxx.mp4",
          "name": "...", "size": 1234567, "mime_type": "video/mp4", "type": "video"}}
```

**空表单（不带 file）**实测返回：

```json
{"code": 0, "msg": "请使用 file 字段提交一个文件"}
```

`doctor` 就用这个形态验端点，停在校验层、不落文件、不动钱包。

**地址白名单（视频类 `videoUrl` 硬约束，报错原文）**

```
400 url_not_allowed
  "videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
   或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）"
```

所以本地素材一律先 `upload` 拿地址，再喂给 `avatar` 的 `--image-url` / `--voice-ref`。
`oss.gpu.likeadmin.cn/openapi/` 的地址有效期约 24 小时。

---

## 7. 查任务 · `GET /api/v1/tasks/{task_id}`

**本包唯一的轮询口**（免费）。

```json
{"code": 1, "msg": "success",
 "data": {"task_id": "...", "status": "completed",
          "videoUrl": "https://vr.a7w.cn/result/xxx.mp4",
          "audio_url": "...", "audio_id": "...",
          "usage": {"points_cost": 675}}}
```

假 id 的返回（`doctor` 用它证明路由在）：

```json
{"code": 0, "msg": "任务不存在"}
```

**为什么不走应用层 query**：`pic_lipsync/query`、`full_video/query`、`nano_banana/query`
都是 POST，按次计费。实测 `nano_banana/query` **每次 72 点**，流水里 216 笔就是这个数。
`pic_lipsync/query` 在 pricing note 里写「query 本身不计费」，但同一 path 的规则是
`markupPercent: 400` —— 一条免费通道已经够用，本包就不碰第二条。

---

## 8. 探针禁区（这一节值 472 点）

| 形态 | 后果 | 本包怎么做 |
|---|---|---|
| `GET /api/v1/apps/<app>` | **sync 即时扣费、不退**：`dressing_diffusion` 200 / `nano_banana` 72 / `pic_lipsync` 保底 50 / `image_human` 保底 250 | 一次都不发；应用存在性用 `GET /api/v1/apps`（`flat cost 0`）证 |
| 应用层 `/query` 轮询 | 按次扣费（`nano_banana/query` 72 点/次） | 只走 `GET /tasks/{id}` |
| `POST /submit` 缺必填 | **先 reserve_sync 冻结，再校验，再全额退** —— 净 0，但钱包被动过 | 每个工位先本地预检，提交前 `--dry-run` |
| `GET /apps/voice_tts/list_voices` | 文档写「免费」，实测每次**先冻 150 点**再退（15 条流水各 150） | `doctor` 一次都不调 |
| `POST /apps/media_services_33/*` | 未配价，先冻 60 点 | 按 60 点/条入账，不当免费接口 |

**完全安全（本包 `doctor` 用的 7 个请求）**

```
✅ GET  /user/balance
✅ GET  /user/balance/logs?limit=1        ← limit 上限 1000
✅ GET  /api/v1/pricing                   ← 裸对象，不套 code/data
✅ GET  /api/v1/apps                      ← 22 个应用 + 29 个 media33 接口，flat cost 0
✅ GET  /api/v1/tasks/<假id>              ← 200 + code 0「任务不存在」
✅ POST /api/v1/upload（空表单）           ← code 0 + 提示字段名
✅ GET  /user/balance（复采）              ← 余额前后一致 = 本轮 0 点
```

**端点存在性的免费判据**

| 返回 | 含义 |
|---|---|
| `400` / `422` + 参数报错 | 存在，停在校验层 |
| `404` + HTML | 未注册（SPA 兜底） |
| `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，不可信 |
| `502` + `InvalidMpsUser` | 路由在，上游凭据坏了 |
