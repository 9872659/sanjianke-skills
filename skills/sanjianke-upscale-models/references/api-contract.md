# 超分接口契约 · 实测原文（2026-11-08）

网关：`https://api.a7w.cn`，前缀 `/api/v1`，鉴权 `Authorization: Bearer <Key>`。
计费单位：**1 元 = 100 点**。本文件所有响应均为本账号实测原文，未做改写。

---

## 1. 端点清单

| 方法 | 路径 | 计费 | 用途 |
|---|---|---|---|
| GET | `/api/v1/pricing` | 0 点 | 115 条价目规则（超分线单价来源） |
| GET | `/api/v1/models` | 0 点 | 316 条模型目录（4 个超分模型） |
| GET | `/api/v1/apps` | 0 点 | 22 个应用（含 flashvsr） |
| GET | `/api/v1/me/tasks?limit=2000&page=N` | 0 点 | 我的任务台账（actualPrice 反推） |
| GET | `/user/balance` | 0 点 | 余额 / 冻结 |
| GET | `/user/balance/logs?limit=1000` | 0 点 | 流水（证明本轮花费） |
| GET | `/api/v1/tasks/<id>` | 0 点 | 通用任务查询 |
| GET | `/api/v1/videos/<id>` | 0 点 | 模型层 / 腾讯任务查询 |
| GET | `/api/v1/video/viapi/result/<id>` | 0 点 | VIAPI 结果查询 |
| POST | `/api/v1/video/viapi/superres` | 9 点/秒 | VIAPI 1080P |
| POST | `/api/v1/video/viapi/superres2k` | 15 点/秒 | VIAPI 2K |
| POST | `/api/v1/video/viapi/superres4k` | 20 点/秒 | VIAPI 4K |
| POST | `/api/v1/video/tencent1080` | 2 点/秒，保底 10 | 腾讯 1080P |
| POST | `/api/v1/video/tencent2k` | 4 点/秒，保底 10 | 腾讯 2K |
| POST | `/api/v1/video/tencent4k` | 8 点/秒，保底 10 | 腾讯 4K |
| POST | `/api/v1/video/upscale` | 30 点/秒 | 4K 旗舰版 |
| POST | `/api/v1/apps/flashvsr/submit` | 10 点/秒，保底 20 | FlashVSR 应用 |
| POST | `/api/v1/apps/flashvsr/query` | 查询不计费 | FlashVSR 查询 |
| POST | `/api/v1/videos` | 通配：上游 x 2，保底 50 | 模型层视频超分 |
| POST | `/api/v1/images/generations` | 通配：上游 x 2，保底 50 | 模型层图像超分 |
| POST | `/api/v1/upload` | 0 点 | multipart 上传，字段名 `file` |

---

## 2. `GET /api/v1/pricing` 里的超分规则

顶层：`{"currency":"CNY","markupPercent":20,"note":"...","site":"...","pricing":{...}}`，
共 115 条规则。超分相关原文：

```json
"/api/v1/video/viapi/superres":   {"mode":"per_second","perSecond":9,  "note":"标准超分 1080P"},
"/api/v1/video/viapi/superres2k": {"mode":"per_second","perSecond":15, "note":"高清超分 2K/60帧"},
"/api/v1/video/viapi/superres4k": {"mode":"per_second","perSecond":20, "note":"超清 4K"},
"/api/v1/video/tencent1080":      {"mode":"per_second","perSecond":2, "minPoints":10, "note":"腾讯云 MPS 超分：2 点/秒（上游价 x2），单笔保底 10 点"},
"/api/v1/video/tencent2k":        {"mode":"per_second","perSecond":4, "minPoints":10, "note":"腾讯云 MPS 超分：4 点/秒（上游价 x2），单笔保底 10 点"},
"/api/v1/video/tencent4k":        {"mode":"per_second","perSecond":8, "minPoints":10, "note":"腾讯云 MPS 超分：8 点/秒（上游价 x2），单笔保底 10 点"},
"/api/v1/video/upscale":          {"mode":"per_second","perSecond":30,"note":"4K旗舰版：30 点/秒（上游成本 0.15 元/秒，毛利 +100%）"},
"/api/v1/apps/flashvsr/submit":   {"mode":"per_second","perSecond":10,"minPoints":20, "note":"视频超分(flashvsr/likeadmin)：对外 10 点/秒，单笔保底 20 点"},
"/api/v1/apps/flashvsr/query":    {"mode":"flat","cost":0,"note":"查询不计费"}
```

**关键**：`/api/v1/videos`、`/api/v1/videos/generations`、`/api/v1/images/generations`
**没有**专属规则。它们命中通配键 `*`：

```json
"*": {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
      "note":"未单独定价的接口：对外 = 上游实际点数 x 2，单笔保底 50 点"}
```

所以模型层单价**不在价目表里**，只能从 `/api/v1/me/tasks` 的 `actualPrice` 反推。

---

## 3. `GET /api/v1/models` 里的 4 个超分模型

目录 316 条。4 条超分模型原文（删去 `smart_route_*` 长字段）：

```json
{"model_code":"topaz-video-upscale","model_name":"Topaz视频优化","call_type":2,
 "call_type_desc":"异步","type_code":"other","type_name":"其他",
 "operation_label":"视频放大","operation_description":"提升输入视频的分辨率和细节。",
 "material_capabilities":{"modes":[{"fields":[
   {"field":"video_url","kind":"video","required":true,"minimum":1,"maximum":1}]}]}}

{"model_code":"topaz-image-upscale","model_name":"Topaz 图像优化","call_type":2,
 "operation_label":"图像放大",
 "material_capabilities":{"modes":[{"fields":[
   {"field":"image_url","kind":"image","required":true,"minimum":1,"maximum":1}]}]}}

{"model_code":"recraft-crisp-upscale","model_name":"Recraft 图像优化","call_type":2,
 "operation_label":"图像放大",
 "material_capabilities":{"modes":[{"fields":[
   {"field":"image","kind":"image","required":true,"minimum":1,"maximum":1}]}]}}

{"model_code":"grok-imagine-upscale","model_name":"放大 Grok Imagine 视频","call_type":2,
 "operation_label":"视频放大",
 "operation_description":"使用本账号已完成的对应视频任务 task_id 提升分辨率；"
                         "不能直接传入外部视频代替任务。",
 "material_capabilities":{"modes":[{"fields":[]}]}}
```

注意两条没有 `pricing` 字段：目录里的 `pricing` 只出现在 92 条文本模型上，
是「每百万 token」价，和超分无关。

---

## 4. 零扣费探针原文（空 body / 缺参）

### 4.1 VIAPI 三档：端点存在，停在参数校验

```http
POST /api/v1/video/viapi/superres  {}
→ 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}

POST /api/v1/video/viapi/superres2k {}
→ 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}

POST /api/v1/video/viapi/superres4k {}
→ 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
```

### 4.2 腾讯三档：端点存在，缺 video_url

```http
POST /api/v1/video/tencent1080 {}
→ 400 {"error":{"code":"video_url_required","message":"请提供 video_url（可公网访问的视频地址）","type":"relay"}}

POST /api/v1/video/tencent2k {}
→ 400 {"error":{"code":"video_url_required","message":"..."}}

POST /api/v1/video/tencent4k {}
→ 400 {"error":{"code":"video_url_required","message":"..."}}
```

### 4.3 4K 旗舰：端点存在，空 body 是 `pixverse_empty_url`

```http
POST /api/v1/video/upscale {}
→ 400 {"error":{"code":"pixverse_empty_url","message":"videoUrl 不能为空","type":"relay"}}
```

### 4.4 模型层视频：空 body 好办，传模型名就 404

```http
POST /api/v1/videos {}
→ 400 {"error":{"code":"","message":"Model name not specified, model name cannot be empty (request id: ...)","type":"new_api_error"}}

POST /api/v1/videos {"model":"topaz-video-upscale"}
→ 404 {"error":{"code":"model_not_found",
        "message":"The model `topaz-video-upscale` does not exist or you do not have access to it.",
        "type":"invalid_request_error"}}
```

### 4.5 模型层图片：缺素材会先冻再退

```http
POST /api/v1/images/generations {"model":"recraft-crisp-upscale"}
→ 404 HTML（Nuxt SPA 兜底）
```

同端点流水（2026-11-08 09:16，净 0 点）：

```text
1794100560264  charge  -20  reserve_sync:/api/v1/images/generations
1794100561106  refund  +20  refund:submit_failed:/api/v1/images/generations
```

**结论**：这个端点出现过先 `reserve_sync` 冻结，再失败退款。`doctor` 因此**不探**
`images/generations` 和 `apps/flashvsr/submit`，只探空 body 会 400 的 7 个端点。

---

## 5. 腾讯 502 原文

完整参数（有 `video_url` + `duration`）提交：

```http
POST /api/v1/video/tencent1080
{"video_url":"https://...","duration":"12.5"}
→ 502 {"error":{"code":"FailedOperation.InvalidMpsUser",
        "message":"腾讯云超分提交失败：[FailedOperation.InvalidMpsUser] invalid mps user",
        "type":"relay"}}
```

任务台账里 3 条腾讯 4K 记录：

```json
{"path":"/api/v1/video/tencent4k","status":"refunded","reservePrice":120,
 "actualPrice":120,"refund":120,"chargedPoints":0,"refundedPoints":120,"netPoints":-120}
{"path":"/api/v1/video/tencent4k","status":"refunded","reservePrice":48,
 "actualPrice":48,"refund":48,"chargedPoints":0,"refundedPoints":48,"netPoints":-48}
```

含义：**提交失败，冻结全额退回，实扣 0 点**。但会短暂动钱包，且拿不到成片。

---

## 6. `/api/v1/me/tasks` 里的超分样本

全量 1,398 条任务，超分相关 14 条（2026-11-08 扫描）：

| path | model | status | actualPrice | refunded | netPoints |
|---|---|---|---|---|---|
| `/api/v1/apps/flashvsr/submit` | flashvsr | settled | 72.348 | 0 | 0 |
| `/api/v1/apps/flashvsr/submit` | flashvsr | settled | 288.312 | 0 | 0 |
| `/api/v1/video/tencent4k` | - | refunded | 120 | 120 | -120 |
| `/api/v1/video/tencent4k` | - | refunded | 120 | 120 | -120 |
| `/api/v1/video/tencent4k` | - | refunded | 48 | 48 | -48 |
| `/api/v1/video/viapi/superres` | - | refunded | 18 | 0 | 0 |
| `/api/v1/video/upscale` | - | refunded | 60 / 150 | 0 | 0 |

`flashvsr` 的 `actualPrice` 与 `reservePrice` 不同（72.348 vs 60.28；288.312 vs 240.16），
说明**预付只是估算，最终按实际时长结算**。`rateNote` 写的是 10 点/秒。

4 个模型层超分模型（topaz / recraft / grok）在 1,398 条任务里 **0 条成交样本**，
所以本包对它们一律 `source=baseline`，只报「50 点起」，不报具体单价。

---

## 7. 查询路由

```http
GET /api/v1/tasks/probe-no-such-task
→ 200 {"code":0,"msg":"任务不存在","data":null}

GET /api/v1/videos/probe-no-such-task
→ 400 {"code":"task_not_exist","message":"task_not_exist","data":null}
```

VIAPI 结果路由：`GET /api/v1/video/viapi/result/<taskId>`。
FlashVSR：`POST /api/v1/apps/flashvsr/query {"task_id": ...}`（查询不计费）。

---

## 8. 本轮零花费证明

`GET /user/balance/logs?limit=1000`，筛选本轮开始后的全部流水：

```text
entries=2  netPoints=0.00
  1794100561106  refund  +20  refund:submit_failed:/api/v1/images/generations
  1794100560264  charge  -20  reserve_sync:/api/v1/images/generations
```

唯一一对「冻结 + 退款」来自一次故意做的模型层缺素材探针，正负相抵，**净 0 点**。
`doctor` 的 14 个请求全是 GET 或空 body POST，没有新增流水。

---

## 9. 请求 / 响应形态

### VIAPI（`videoUrl` + `duration`）

```json
POST /api/v1/video/viapi/superres
{"videoUrl":"https://oss.gpu.likeadmin.cn/openapi/...","duration":60}
```

### 腾讯（`video_url` + `duration`）

```json
POST /api/v1/video/tencent1080
{"video_url":"https://oss.gpu.likeadmin.cn/openapi/...","duration":60}
```

### FlashVSR 应用（`input_url` + `duration`）

```json
POST /api/v1/apps/flashvsr/submit
{"input_url":"https://...","duration":15.695}
```

### 模型层视频（`model` + `video_url`）

```json
POST /api/v1/videos
{"model":"topaz-video-upscale","video_url":"https://..."}
```

### 模型层图片（`model` + `image` / `image_url`）

```json
POST /api/v1/images/generations
{"model":"recraft-crisp-upscale","image":"https://..."}

POST /api/v1/images/generations
{"model":"topaz-image-upscale","image_url":"https://..."}
```

成功响应取 `task_id` / `taskId` / `id` / `data.task_id` 之一；
失败响应统一 `{"error":{"code","message","type"}}`。
