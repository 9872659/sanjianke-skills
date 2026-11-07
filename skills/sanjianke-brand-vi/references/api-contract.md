# 接口契约（2026-11-08 实测原文）

全部请求走 `https://api.a7w.cn`，头：

```http
Authorization: Bearer <YOUR_API_KEY>
Content-Type: application/json          # images/edits 与 upload 是 multipart/form-data
User-Agent: sanjianke-brand-vi/1.0.0
```

1 元 = 100 点。

---

## 0. 计费口径（先看这段，省掉一半踩坑）

| 工序 | 路径 | 口径 | 实测依据 |
|---|---|---|---|
| 文生图 | `POST /api/v1/images/generations` | **6 点/张**，按 `data` 实际返回张数 | 流水两笔 `sync:/api/v1/images/generations` 各 −6 |
| 局部改图 | `POST /api/v1/images/edits` | **6 点/张**（同一条 images 线） | 与 generations 同模型同价 |
| 参考图派生 | `POST /api/v1/apps/nano_banana/submit` | **72 点/次** flat | `GET /api/v1/pricing` 的两条 flat |
| 上传 | `POST /api/v1/upload` | **0 点** | `pricing["/api/v1/upload"] = {mode: flat, cost: 0}` |
| 查任务 | `GET /api/v1/tasks/<id>` | **0 点** | 假 id 返回 `{"code":0,"msg":"任务不存在"}` |

`GET /api/v1/pricing` 里 **没有** `/api/v1/images/generations` 与 `/api/v1/images/edits`
的专属规则 —— 它们的价挂在模型线上，所以尺寸、质量、输出格式都不改价，`n` 是唯一乘数。

---

## 1. POST /api/v1/images/generations

```json
{"model": "gpt-image-2.6", "prompt": "…", "n": 4, "size": "1024x1024",
 "output_format": "png", "response_format": "b64_json"}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `model` | `gpt-image-2.6` | `/api/v1/models` 里 `type_code=image`，`max_reference_images=6` |
| `prompt` | 非空字符串 | 空 → 422 |
| `n` | 1–4 | 超出 → 校验错 |
| `size` | `auto` / `1k` / `2k` / `4k` / `宽x高` | 自定义尺寸四条硬约束见下 |
| `output_format` | `png` / `jpeg` / `webp` / `gif` | 不影响价格 |
| `response_format` | `b64_json`（默认）/ `url` | 两种都要处理 |

**参数校验实测**（本轮）：

```http
POST /api/v1/images/generations
{"model":"gpt-image-2.6","prompt":""}

HTTP 422
{"error":{"message":"prompt: String should have at least 1 character",
          "type":"invalid_request_error","param":"","code":"bad_request"}}
```

停在 pydantic 校验层，**没有冻结、没有建任务、没有扣点**。

**成功响应形态**（兄弟包 `sanjianke-gpt-image` 2026-11-07 实测，本包沿用同一处理）：

```json
{"data": [{"b64_json": "iVBORw0KG..."}], "size": "1024x1024", "output_format": "png"}
```

`data[]` 里也可能是 `url`，有效期约 3 小时，**原样使用**（追加查询参数会 404），下载不需要 Key。

### 自定义尺寸的四条硬约束

- 宽高都是 16 的倍数
- 长边 / 短边 ≤ 3:1
- 单边 ≤ 3840
- 总像素 655,360 – 8,294,400

本包七种物料的尺寸都预先过了一遍：

| 物料 | size | 像素 |
|---|---|---|
| logo / packaging / avatar | 1024x1024 | 1,048,576 |
| card | 1536x1024 | 1,572,864 |
| rollup | 1024x2560 | 2,621,440 |
| cover | 1536x864 | 1,327,104 |
| manual | 1040x1472 | 1,530,880 |

---

## 2. POST /api/v1/images/edits（multipart/form-data）

| 字段 | 说明 |
|---|---|
| `model` | `gpt-image-2.6` |
| `prompt` | 要改什么 |
| `n` | 1–4 |
| `size` | 可省；`auto` | 
| `output_format` / `response_format` | 同 generations |
| `image[]` | 参考图文件，可重复（上限 20） |
| `mask` | 蒙版文件，可选 |

**参数校验实测**（本轮，只带 model、无图）：

```http
POST /api/v1/images/edits   (multipart: model=gpt-image-2.6, 零文件)

HTTP 500
{"error":{"message":"image is required (request id: 202611071809326…)",
          "type":"new_api_error","param":"","code":"convert_request_failed"}}
```

**这是 `500` 而不是 `422`**，但它同样停在转换层，`request id` 里没有任务号，余额与流水前后一致 —— 所以 `doctor` 用它当第二探针，判据是 `500 + image is required`。

---

## 3. POST /api/v1/apps/nano_banana/submit

```json
{"action": "edit", "prompt": "…", "model": "nano-banana",
 "image_urls": ["https://oss.gpu.likeadmin.cn/openapi/…"],
 "aspect_ratio": "3:2", "resolution": "1K"}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `prompt` | 必填 | 要派生/改成什么 |
| `action` | `generate`（默认）/ `edit` | 本包固定 `edit` |
| `model` | `nano-banana`（默认）/ `nano-banana-2` / `-2-lite` / `-pro` / `…:official` | **本租户 flat 72，选哪个都不改价** |
| `image_urls` | URL 数组，`action=edit` 必填 | 应用层 `max_reference_images=12` |
| `resolution` | `1K` / `2K` / `4K` | 官方高清模型按档位计费；本租户被 flat 72 盖住 |
| `aspect_ratio` | `auto` / `1:1` / `16:9` / `9:16` / `4:3` / `3:4` / `3:2` / `2:3` / `5:4` / `4:5` / `21:9` | 对应本包物料的画幅 |
| `callback_url` | HTTPS | 可选回调 |

成功响应（文档原文）：

```json
{"code": 1, "msg": "success",
 "data": {"task_id": "task_xxxxxxxx", "status": "pending",
          "app": "nano_banana", "api": "submit", "frozen_points": 72}}
```

未命中计费规格时：

```json
{"code": 0, "msg": "当前请求未命中可用计费规格，请检查模型、分辨率是否在支持范围内。", "data": []}
```

**价目原文**（`GET /api/v1/pricing`，本轮实测）：

```json
"/api/v1/apps/nano_banana/submit": {
  "mode": "flat", "cost": 72, "markupPercent": 0,
  "note": "…AI商品图 = 固定 72 点/次；商品多角度 = 25 点 × 选中视角数…"}
"/api/v1/apps/nano_banana/*": {"mode": "flat", "cost": 72, "markupPercent": 0, …}
```

---

## 4. POST /api/v1/upload（multipart/form-data）

字段名 **`file`**，单文件 512 MB 上限，**不计费**。

```http
POST /api/v1/upload            (不带 file)

HTTP 200
{"code":0,"msg":"请使用 file 字段提交一个文件","data":null}
```

成功（兄弟包 `sanjianke-video-lab` 实测）：

```json
{"code": 1, "msg": "success",
 "data": {"url": "https://oss.gpu.likeadmin.cn/openapi/…", "name": "logo-01.png",
          "size": 1639194, "mime_type": "image/png", "type": "image"}}
```

`data.url` 在平台白名单内，直接进 `image_urls`；最长 24 小时有效，落了文件就转存。

---

## 5. GET /api/v1/tasks/<task_id>

```http
GET /api/v1/tasks/probe-no-such-task-brandvi

HTTP 200
{"code":0,"msg":"任务不存在","data":null}
```

真任务的字段按 `data.status` / `data.result` 读。这条路由 **cost 0**，轮询随便打。

---

## 6. 只读目录接口（本轮实测量）

```http
GET /api/v1/models     → 200，316 个模型，type_code=image 50 个
                          gpt-image-2.6: max_reference_images=6, supports_vision=1
GET /api/v1/apps       → 200，22 个应用；nano_banana id=22, billing_mode=1,
                          apis=[submit(POST, 参考图 12), query(GET)]
GET /api/v1/pricing    → 200，115 条规则（裸对象，不套 code/data）
GET /user/balance      → 200，available_points / frozen / rate=100
GET /user/balance/logs → 200，limit 生效，上限 1000
```

`/api/v1/pricing` 关键三条：

```json
"/api/v1/apps": {"mode":"flat","cost":0,"note":"★应用目录（只读）不计费"},
"/api/v1/models": {"mode":"flat","cost":0,"note":"★模型目录（只读）不计费"},
"/api/v1/upload": {"mode":"flat","cost":0,"note":"★上传不计费"},
"*": {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
      "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}
```

---

## 7. 🔴 探针禁区

| 动作 | 判定 | 证据 |
|---|---|---|
| `GET /api/v1/apps/nano_banana` | ❌ **扣 72 且不退** | 命中 `/apps/nano_banana/*` 通配 flat，`sync:` 即时结算 |
| `POST /api/v1/apps/nano_banana/submit` 缺必填 | ⚠️ **先冻 72 再退** | `reserve_sync:` 口径，净额 0 但钱包被动过 |
| `GET /api/v1/apps/<app>` 通读 schema | ❌ **按该应用 flat 单价扣** | 2026-11-07 实测：dressing_diffusion −200、nano_banana −72，均无退款 |
| `POST /api/v1/images/generations` 空 prompt | ✅ 422，不建任务 | 本轮实测 |
| `POST /api/v1/images/edits` 无图 | ✅ 500，不建任务 | 本轮实测 |
| `POST /api/v1/upload` 无 file | ✅ 200 提示补字段 | 本轮实测 |
| `GET /api/v1/apps` · `/models` · `/pricing` | ✅ cost 0 | 价目规则明文 |
| `GET /api/v1/tasks/<id>` | ✅ cost 0 | 本轮实测 |

**判断端点是否存在的免费判据**：

| 返回 | 含义 |
|---|---|
| `400` / `422` / `500` + 参数报错 | **存在**，停在校验层 |
| `404` + HTML | **未注册**（SPA 兜底） |
| `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，不可信 |
