# 接口契约（实测原文，2026-11-08）

本文件每一条都来自本账号真实返回，不是文档抄的。
网关：`https://api.a7w.cn`。鉴权：`Authorization: Bearer <你的 Key>`。
1 元 = 100 点（`GET /user/balance` 的 `rate: 100`）。

---

## 1. 模型目录：8 个数字人 ID

`GET /api/v1/models` → 316 条 = 221 条目录模型（带 `model_code`）+ 95 条裸模型层 ID。
数字人相关 8 个，全部 `type_code=other`：

| ID | 名称 | 操作 | 图片 / 视频字段 | 音频 | 出视频 |
|---|---|---|---|---|---|
| `omnihuman-2-0` | OmniHuman 2.0 | 数字人驱动 | `image_urls`（数组，1 张） | `audio_url` | 是 |
| `omnihuman-1-5` | OmniHuman 1.5 | 数字人驱动 | `image_url` + `mask_url`（0-5） | `audio_url` | 是 |
| `infinitalk-from-audio` | Infinitalk 视频生成 | 音频驱动口播 | `image_url` | `audio_url` | 是 |
| `kling-ai-avatar-standard` | Kling AI Avatar Standard | 数字人口播 | `image_url` | `audio_url` | 是 |
| `kling-ai-avatar-pro` | Kling AI Avatar Pro | 数字人口播 | `image_url` | `audio_url` | 是 |
| `omnihuman-1-5-human-identification` | Omnihuman 1.5 主体识别 | 主体识别 | `image_url` | — | 否（前置） |
| `omnihuman-1-5-subject-detection` | Omnihuman 1.5 主体检测 | 主体检测 | `image_url` | — | 否（前置） |
| `volcengine-video-to-video-lip-sync` | Volcengine 视频对口型 | 视频对口型 | `video_url` | `audio_url` | 是 |

字段名来自每条记录的 `material_capabilities.modes[0].fields`，原文示例（`omnihuman-2-0`）：

```json
{"field":"image_urls","kind":"image","required":true,"minimum":1,"maximum":1,
 "scope":"本次请求","role":"reference"}
{"field":"audio_url","kind":"audio","required":true,"minimum":1,"maximum":1,
 "scope":"本次请求","role":"reference"}
```

`omnihuman-1-5` 多一个可选字段：

```json
{"field":"mask_url","kind":"image","required":false,"minimum":0,"maximum":5,
 "scope":"本次请求","role":"mask"}
```

这 8 条记录都**没有** `pricing` / `price` / `params_schema` 字段，只有文字说明、`material_capabilities` 与智能路由开关。

---

## 2. 提交端点：只有 `/videos/generations`

### 2.1 正确的路

```http
POST /api/v1/videos/generations
{"model":"omnihuman-2-0"}

HTTP 400
{"error":"prompt or content field is required","type":"invalid_request_error"}
```

8 个数字人 ID 逐条实测，全部返回同一句 `400 prompt or content field is required`：

```
omnihuman-2-0                          400 prompt or content field is required
omnihuman-1-5                          400 prompt or content field is required
infinitalk-from-audio                  400 prompt or content field is required
kling-ai-avatar-standard               400 prompt or content field is required
kling-ai-avatar-pro                    400 prompt or content field is required
omnihuman-1-5-human-identification     400 prompt or content field is required
omnihuman-1-5-subject-detection        400 prompt or content field is required
volcengine-video-to-video-lip-sync     400 prompt or content field is required
```

`400 prompt ... required` 说明**型号已解析、参数校验拦下**，这是「这条路由认这个型号」的免费判据。发完 8 条探针，余额与流水都没有变化（见 §8）。

### 2.2 错误的路

```http
POST /api/v1/videos
{"model":"omnihuman-2-0"}

HTTP 404
{"error":{"code":"model_not_found",
          "message":"The model `omnihuman-2-0` does not exist or you do not have access to it.",
          "type":"invalid_request_error"}}
```

`/api/v1/videos` 只认 4 个裸视频 ID（`muse-video`、`sd/doubao-seedance-2-0-260128`、
`volcengine/doubao-seedance-2-5-260628`、`wan3.0-video`）。目录里的数字人型号打进去就是 404。

### 2.3 空 body

```http
POST /api/v1/videos/generations   {}
HTTP 400  {"error":"model field is required","type":"invalid_request_error"}

POST /api/v1/videos               {}
HTTP 400  {"error":{"code":"","message":"Model name not specified, model name cannot be empty ...",
                    "type":"new_api_error"}}
```

两条都停在模型名校验，不建任务。

---

## 3. 请求体（本包 `gen` 发出的）

```json
{"model": "omnihuman-2-0",
 "prompt": "人物面对镜头自然口播，口型与表情跟着音频，画面稳定，半身构图",
 "image_urls": ["https://oss.gpu.likeadmin.cn/openapi/..."],
 "audio_url": "https://oss.gpu.likeadmin.cn/openapi/..."}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | 8 个 ID 之一；缺了 `400 model field is required` |
| `prompt` | 是 | 共用一句；缺了 `400 prompt or content field is required` |
| `image_urls` | 按型号 | 只有 `omnihuman-2-0` 用数组 |
| `image_url` | 按型号 | 其余图驱动型号用单值 |
| `video_url` | 按型号 | 只有 `volcengine-video-to-video-lip-sync` 用 |
| `audio_url` | 是 | 驱动音频 |
| `mask_url` | 否 | `omnihuman-1-5` 的局部处理，0-5 张 |
| `--extra` | 否 | 透传 JSON，例如 `{"resolution":"1080p"}` |

`--seconds` 只用于报价与预算闸门，不写进请求体；平台按音频实际时长冻结与结算。

---

## 4. 查询与轮询

```http
GET /api/v1/tasks/probe-no-such-task
HTTP 200
{"code":0,"msg":"任务不存在"}
```

假 id 回 `code: 0` + 中文说明 —— 路由在、且不扣费。真实任务返回里带 `status` / `progress` / `task_id`，
成片地址在 `video_url` / `url` / `result.video_url` 之一。本包按 `data` 或扁平结构两种形态都解析。

**轮询只走这一条：`GET /api/v1/tasks/<id>`，每查一次 0 点。**

---

## 5. 模型层单价：价目表里没有

没有 `/api/v1/videos/generations`，也没有 `modelPricing` 键。模型层命中通配：

```json
```

真实单价只在 `GET /api/v1/me/tasks` 的 `actualPrice` 里。归集规则：

1. 取 `path` 不含 `/apps/` 且 `model` 非空的记录；
2. 按 `model` 分组，`actualPrice > 0` 的进样本；
3. 组内最小 / 最大 = 报价区间，条数 = n，标 `source=live`；
5. 跑成功一次，下一次报价值变成你账号的成交价。

本账号 1,398 条台账里，模型层只有 7 个模型、43 笔成交：

```
gpt-image-2-pro                          17 笔   39.00 / 78.00 / 104.00
muse-video                                8 笔   44.00 / 55.00 / 260.00
wan3.0-video                              8 笔   300.00（全部）
sd/doubao-seedance-2-0-260128             5 笔   145.73 / 181.79 / 3000.00
volcengine/doubao-seedance-2-5-260628     3 笔   762.30 / 3000.00 / 3045.71
gpt-image-2                               1 笔   26.00
seedream-5-0-flash                        1 笔   15.60
```

数字人模型层 **0 笔** —— 所以 5 个模型全部是 `baseline`，不是编出来的单价。

---

## 6. 应用层锚点（只比价，不提交）

`GET /api/v1/pricing` 原文（节选）：

```json
"/api/v1/apps/image_human/submit": {
  "mode": "per_second",
  "rateFrom": "mode",
  "modelRates": {"fast":{"*":10},"standard":{"*":15},"2k":{"*":30},"4k":{"*":60}},
  "defaultModel": "fast",
  "note": "全驱数字人 快速 10 / 标准 15 / 2K 30 / 4K 60 点/输入秒（= 上游 2/3/6/12 x5）"
}

"/api/v1/apps/pic_lipsync/submit": {
}

"/api/v1/apps/lipsync/submit": {
}
```

由此得到同一段 10 秒音频：

```
image_human fast      10 点/输入秒 x10 = 100 点
image_human standard  15 点/输入秒 x10 = 150 点
image_human 2k        30 点/输入秒 x10 = 300 点
image_human 4k        60 点/输入秒 x10 = 600 点
pic_lipsync           15 点/秒 x10 = 150 点（保底 50）
lipsync 1.0           2.7 点/秒 x10 = 27 点（输入是视频）
```

---

## 7. 探针安全区与禁区

| 调用 | 实测后果 |
|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配计价，`sync:` 即时扣费、不退 |
| `POST /api/v1/apps/<app>/query` | 每查一次就是一次的钱 |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结，再校验失败全额退，净 0 但钱包被短暂动过 |
| `POST /api/v1/videos {"model":"wan3.0-video"}` 缺 prompt | 2026-11-07 实测先冻 300 点再退 |

安全区（本包 `doctor` 只碰这些）：

```
GET  /api/v1/models
GET  /api/v1/pricing
GET  /api/v1/me/tasks?limit=2000&page=N
GET  /api/v1/tasks/<id>
GET  /user/balance
GET  /user/balance/logs?limit=N
POST /api/v1/upload                       （multipart，字段名 file）
POST /api/v1/videos/generations  {}       （400 不冻结）
POST /api/v1/videos/generations  {"model": 8 个数字人 ID}  （400 不冻结）
POST /api/v1/videos              {"model": 数字人 ID}       （404 不冻结）
```

---

## 8. 本包探针窗口的 0 点原始证据

```
探针前：GET /user/balance  available_points = 999997393470.2579  frozen = 0
探针后：GET /user/balance  available_points = 999997393470.2579  frozen = 0
差额：0.0 点

探针前：GET /user/balance/logs?limit=3
        at = 1794100561106
        reference = refund:submit_failed:/api/v1/images/generations
        total = 7885
探针后：完全一致（时间戳、reference、total 都没变）

doctor 输出：本包视频线新增 0 条 · 视频线今日净 0 点
```

本包没有建任务、没有冻结、没有新增流水。

---

## 8.1 外部并发流水（与本包无关，照实记）

2026-11-08 11:18:40，账户出现一条与本包无关的预扣：

```json
{"at":1794107920196,"type":"charge","typeName":"冻结/预扣","kind":"out",
 "points":-321.3,"amount":321.3,"balanceAfter":999997393148.9578,
 "path":"","taskId":"","reference":"gpu:prepay:32ceabe6c96e44bdb1e4d80358a3b8ae",
 "orderId":"","model":"","provider":""}
```

它没有 `path` / `taskId` / `model`，不是任何 HTTP API 调用的记账；本包 4 条 POST 探针
全部是 400 / 404，`~/.a7w/avatar-models-ledger.json` 也不存在（本包没有提交过任务）。
余额因此从 `999,997,393,470.2579` 变为 `999,997,393,148.9579`（-321.3 点），
这 -321.3 点不计入本包。`doctor` 会把「本包视频线新增流水」与「外部流水」分开报。
