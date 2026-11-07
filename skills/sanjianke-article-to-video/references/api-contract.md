# 接口契约（实测原文 + 文档形态）

> 数据源：`GET https://api.a7w.cn/api/v1/apps`、`GET /api/v1/pricing`、`GET /user/balance`、
> `GET /user/balance/logs`，以及 2026-11-07 23:15–23:40（UTC+8）本轮的零扣费探针。
> 1 元 = 100 点。

---

## 一、总览

| 工序 | 应用 / 模型 | 方法与路径 | 计费 |
|---|---|---|---|
| 出图 | `gpt-image-2.6` | `POST /api/v1/images/generations` | 6 点/张 |
| 改图 | `nano_banana` | `POST /api/v1/apps/nano_banana/submit` | 72 点/次 |
| 出片 | `full_video` | `POST /api/v1/apps/full_video/submit` | 按秒 × 分辨率 |
| 旁白 | `voice_tts` | `POST /api/v1/apps/voice_tts/tts` | 上游真实点数 × 3 |
| 配乐 | `media_services_33` | `POST /api/v1/apps/media_services_33/music_generate` | 上游点数 × 2，保底 50 |
| 查任务 | — | `GET /api/v1/tasks/<task_id>` | **cost:0** |
| 传图 | — | `POST /api/v1/upload`（multipart，字段 `file`） | **cost:0** |

所有请求都要 `Authorization: Bearer <你的 Key>` 与 `Accept: application/json`。

---

## 二、`POST /api/v1/images/generations`（出图，6 点/张）

```json
{
  "model": "gpt-image-2.6",
  "prompt": "一座城，一条街，十七家小店，电影感纪实，高清写实摄影，16:9 构图，光线自然",
  "n": 1,
  "size": "1536x1024",
  "output_format": "png",
  "response_format": "b64_json"
}
```

```json
{
  "created": 1793900000,
  "data": [{"b64_json": "iVBORw0KGgo...", "revised_prompt": "...",
            "width": 1536, "height": 1024}],
  "usage": {"input_tokens": 13, "output_tokens": 1056, "total_tokens": 1069},
  "output_format": "png", "size": "1536x1024"
}
```

- 同步出图，常见 20–50 秒，客户端超时给到 180 秒以上。
- 价格与 `size` / `quality` / `output_format` 都无关，按 `data` 里**实际返回的张数**收 6 点/张。
- `n` 的区间是 1–4；本包固定 `n=1`，一镜一张，方便单独重出。
- 自定义尺寸的四条约束：宽高都是 16 的倍数、长短边比 ≤ 3:1、单边 ≤ 3840、
  总像素 655,360–8,294,400。`1536x1024` 满足全部四条。
- 端点不带 `/api` 会落到网关默认应用（`nano_banana`，72 点/次）且不报错 ——
  所以 `doctor` 用「带 model 的空 prompt」探这条，期望 **422**。

**本轮实测**（零扣费）：

```http
POST /api/v1/images/generations  {"model":"gpt-image-2.6","prompt":""}
HTTP/1.1 422
{"error":{"message":"prompt: String should have at least 1 character",
          "type":"invalid_request_error","param":"","code":"bad_request"}}
```

---

## 三、`POST /api/v1/apps/full_video/submit`（图生视频）

```json
{
  "model": "full-video",
  "content": [
    {"type": "text", "text": "这座城的老街，镜头缓慢推近，画面自然流动"},
    {"type": "image_url", "role": "first_frame",
     "image_url": {"url": "https://oss.gpu.likeadmin.cn/openapi/xxxx.png"}}
  ],
  "duration": 5,
  "resolution": "480P",
  "ratio": "16:9",
  "aigc_watermark": false
}
```

```json
{"code": 1, "msg": "success",
 "data": {"task_id": "task_xxxxxxxx", "status": "pending", "frozen_points": 70}}
```

- `content` 必填，至少要有一项 `text`；首帧用 `role: "first_frame"`，参考图用 `role: "reference_image"`。
- `duration` 只能 **4–15 的整数秒**；`ratio` 支持 `16:9 / 9:16 / 1:1 / 4:3 / 3:4 / adaptive`。
- 计费：`per_second` + 按分辨率的单价（见下），提交时按秒预冻结，完成后按实际结算，失败全额退回。
- **请求形态取自平台 schema 与既有包，本轮没有真跑**（真跑必扣费），首次使用时留意返回。

### 按秒价（`/api/v1/pricing` 原文）

```json
{"mode": "per_second", "markupPercent": 1e-07,
 "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}}
```

| 分辨率 | 点/秒 | 4 秒一段 | 5 秒一段 | 10 秒一段 |
|---|---|---|---|---|
| 480P | 14 | 56 | 70 | 140 |
| 768P | 28 | 112 | 140 | 280 |
| 1080P | 60 | 240 | 300 | 600 |
| 2K / 4K | 80 | 320 | 400 | 800 |

---

## 四、`POST /api/v1/apps/voice_tts/tts`（旁白）

```json
{"text": "一座城，一条街，十七家小店。这条街只有四百米……",
 "model": "s2-pro", "format": "mp3"}
```

```json
{"code": 1, "msg": "success",
 "data": {"audio_url": "https://your-domain.com/uploads/ai_app/tts_xxxxxxxx.mp3",
          "format": "mp3"}}
```

- 同步接口，文档建议**单次 500 字以内**；本包按 450 字切块，句间自动补句号。
- 模型可选 `s1` / `s2-pro`（默认 `s2-pro`），格式 `mp3` / `wav` / `opus` / `pcm`。
- 计费口径（`/api/v1/apps/voice_tts/*` 规则原文）：

```json
{"mode": "flat", "cost": 0, "markupPercent": 200,
 "note": "对外价 = 上游实际点数 × 3；一律按上游真实点数计费"}
```

- 实测反推：**33 字 = 5.94 点**，即 0.18 点/字。2,000 字正文全念约 360 点（3.6 元）。

---

## 五、`POST /api/v1/apps/media_services_33/music_generate`（配乐）

```json
{"model": "V6", "custom_mode": false, "instrumental": true,
 "prompt": "轻音乐，舒缓，钢琴与弦乐，适合纪录片旁白垫底"}
```

- 必填：`model` / `custom_mode` / `instrumental`。纯音乐就把 `instrumental` 设为 `true`。
- 返回 `task_id`（`{"code":1,"data":{"task_id":...}}`），进度查 `GET /api/v1/tasks/<id>`，
  产物在任务返回的 `audio_url` 一类字段里（本包用扩展名扫描兜底）。
- 计费：`media_services_33` 没有专属规则，落通配：

```json
{"mode": "flat", "cost": 0, "markupPercent": 100, "minPoints": 50,
 "note": "未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}
```

- 所以 `cost` 里配乐按 **50 点（下限）** 计，实际按任务详情结算。
- 这个应用在架 **29 个接口**（Suno 音乐 21 个 + Gemini / ElevenLabs 语音 8 个），
  本包只用 `music_generate`；其余接口的必填项见 `_media33.json` 的实测导出。

---

## 六、`POST /api/v1/apps/nano_banana/submit`（参考图改图，72 点/次）

```json
{"action": "edit", "model": "nano-banana",
 "prompt": "同一处老街，改成雨后清晨，冷色调",
 "image_urls": ["https://oss.gpu.likeadmin.cn/openapi/xxxx.png"],
 "resolution": "1K", "aspect_ratio": "16:9"}
```

```json
{"code": 1, "msg": "success",
 "data": {"task_id": "task_xxxxxxxx", "status": "pending", "frozen_points": 72}}
```

- `action`：`generate`（文生图）/ `edit`（拿 `image_urls` 改图）。
- `resolution`：`1K` / `2K` / `4K`；普通模型只吃 `1K`。`aspect_ratio` 与出图一致。
- 计费：`{"mode":"flat","cost":72}`，固定 72 点/次。
- 只有当 `image --ref` 给了参考图时才走这条；默认走 6 点的 gpt-image。

---

## 七、免费与收费的边界（2026-11-07 逐条实测）

### 安全（只读或停在参数校验）

```
GET  /api/v1/models                 cost:0    模型目录
GET  /api/v1/apps                   cost:0    应用列表（22 个应用）
GET  /api/v1/pricing                cost:0    裸对象，不套 code/data
GET  /api/v1/tasks/<id>             cost:0    假 id 返回 {"code":0,"msg":"任务不存在"}
GET  /user/balance                  cost:0    裸对象，含 available_points / frozen
GET  /user/balance/logs?limit=1000  cost:0    裸对象，数组键名是 logs
POST /api/v1/upload                 免费     multipart，字段名 file
POST /api/v1/images/generations     {"model":"gpt-image-2.6","prompt":""} → 422
POST /api/v1/video/viapi/<tier>     {} → 400 empty_url（视频线健康检查）
```

### 会真扣钱且不退（`sync:` 即时结算）

```
GET /api/v1/apps/<app>     ← 命中 /api/v1/apps/<app>/* 通配，按该应用 flat 单价扣
                             dressing_diffusion 200 · nano_banana 72 · pic_lipsync 保底 50
```

### 会先冻再退（`reserve_sync:`）

```
POST /api/v1/apps/<app>/submit 缺必填 → 先冻结、再参数校验失败、再全额退（净 0，但钱包被短暂动过）
```

所以「缺参数就不会扣钱」这句话只对 HTTP 层成立，对账层不成立。本包**不做**这类探针。

### 应用层 `/query` 与 `/list_voices`

```
POST /api/v1/apps/<app>/query     每查一次 = 一次的钱（nano_banana 72 点/次）
GET  /api/v1/apps/voice_tts/list_voices   也会先冻 150 点再退（流水可见 reserve_sync）
```

本包一律用 `GET /api/v1/tasks/<id>` 轮询；`voice_tts` 的音色列表一次都不打。

---

## 八、上传与地址白名单

`POST /api/v1/upload`（multipart/form-data，字段名 `file`）返回：

```json
{"code": 1, "msg": "success",
 "data": {"url": "https://oss.gpu.likeadmin.cn/openapi/xxxx.png",
          "path": "...", "name": "...", "size": 12345,
          "mime_type": "image/png", "type": "image"}}
```

提交视频时地址必须是本站托管：

- `vr.a7w.cn`（本站）
- `cdn2.jiujiushuyuan.cn/vr/`（本站七牛）
- `oss.gpu.likeadmin.cn/openapi/`（本站上传接口返回的）

外站地址会 `400 url_not_allowed`，实测原文：

```
videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）
```

**本轮实测**（零扣费）：

```http
POST /api/v1/upload  （空 multipart，没有 file 字段）
HTTP/1.1 200
{"code":0,"msg":"请使用 file 字段提交一个文件","data":null}
```

---

## 九、任务返回与产物字段

`GET /api/v1/tasks/<id>` 成功时是 `{"code":1,"data":{...}}`，`data` 里常见：

| 字段 | 含义 |
|---|---|
| `status` | `pending` / `processing` / `completed` / `failed` |
| `tool` | 哪个应用 / 哪个接口建的 |
| `videoUrl` / `video_url` | 成片地址 |
| `audio_url` / `audioUrl` | 音频地址 |
| `cost` / `refund` | 实扣 / 退回点数 |
| `usage.points_cost` | 上游真实点数 |
| `message` / `fail_reason` | 失败原因 |

本包的 `pick_asset` 不硬编码字段名：先按扩展名（`.mp4` / `.png` / `.mp3`…）扫整棵 `data`，
再按路径里是否含 `video` / `image` / `audio` 兜底。

---

## 十、错误码与判定

| 返回 | 含义 |
|---|---|
| `400` / `422` + 参数报错 | 端点在，停在校验层 |
| `404` + HTML | 这条前缀下没有该端点（SPA 兜底） |
| `200` + `{"code":1,...}` | 成功 |
| `200` + `{"code":0,"msg":"..."}` | 业务失败（参数 / 余额 / 应用未配置） |
| `502` + `InvalidMpsUser` | 路由在，上游凭据坏了 |

---

## 十一、本轮费用自查

```http
GET /user/balance
HTTP/1.1 200
{"available_points": 999997393482.2579, "points": 999997393482.2579,
 "frozen": 0, "yuan": 9999973934.82, "rate": 100, "currency": "points"}

GET /user/balance/logs?limit=1000
HTTP/1.1 200
{"currency":"points","rate":100,"count":1000,"total":7893,
 "logs":[{"at":1794059270612,"type":"refund","points":150, ...}]}
```

- 本轮全部请求：只读 GET + 空 prompt 422 + 空 multipart 上传，**没有发起任何建任务请求**。
- 流水 `count` / `total` / 最新一条 `at` 在整轮前后保持一致（见 README 与本文件同步记录），
  即本轮新增扣费 **0 点、0 冻结**。
