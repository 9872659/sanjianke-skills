# 接口契约（2026-11-08 实测原文 + 单价反推法）

网关根地址 `https://api.a7w.cn`，业务前缀 `/api/v1`。
Key 走 `Authorization: Bearer sk-…`。
本文所有「实测」都是 2026-11-08 本轮在同一个账号上打出来的，本轮花费 **0 点**。

---

## 一、路径一览

| 用途 | 方法与路径 | 单价 | 形态 |
|---|---|---|---|
| 文生图 | `POST /api/v1/images/generations` | 按型号计次 | JSON，同步 |
| 改图 | `POST /api/v1/images/edits` | 按型号计次 | multipart |
| 型号目录 | `GET /api/v1/models` | **0 点** | JSON |
| 任务台账 | `GET /api/v1/me/tasks` | **0 点** | JSON，20 条/页 |
| 价目表 | `GET /api/v1/pricing` | **0 点** | 裸对象 |
| 任务查询 | `GET /api/v1/tasks/<id>` | **0 点** | JSON |
| 余额 | `GET /user/balance` | **0 点** | JSON |
| 流水 | `GET /user/balance/logs` | **0 点** | JSON，limit 上限 1000 |
| 应用目录 | `GET /api/v1/apps` | **0 点** | JSON |

应用层的 `POST /api/v1/apps/nano_banana/query` **每查一次扣 72 点**（家族实测 216 笔 = 15,552 点），
所以本包查任务只走 `GET /api/v1/tasks/<id>`。

---

## 二、`GET /api/v1/models` → 200

```
共 316 条 = 221 条目录模型（带 model_code）+ 95 条裸模型层 ID（只有 id / owned_by）
其中 type_code=image 50 条记录、去重后 49 个型号
```

`gpt-image-2.6` 的记录（原文，节选）：

```json
{"model_code": "gpt-image-2.6", "model_name": "GPT Image 2.6",
 "description": "1K 图片生成与参考图编辑，按次计费。", "call_type": 2, "call_type_desc": "异步",
 "max_reference_images": 6, "channel_code": "OpenAIYI", "channel_name": "官方平台",
 "vendor_code": "openai", "type_code": "image", "type_name": "图片生成",
 "capabilities": {"supports_vision": true, "max_reference_images": 6},
 "id": "gpt-image-2.6", "object": "model", "owned_by": "openai"}
```

### 待验证型号的判据（本包 catalog 用它分栏）

```json
{"model_code": "flux-2-flex", "model_name": "FLUX 2 Flex",
 "description": "模型接口及可用规格详见开发文档；同步后请先验证并完成上架。",
 "channel_code": "official", "channel_name": "Official", "vendor_code": "official",
 "material_capabilities": {"modes": [
   {"code": "text_to_image", "fields": [], "images": "不接受"},
   {"code": "image_to_image", "fields": [{"field": "input_urls", "minimum": 1, "maximum": 8}]}]}}
```

特征：`channel_code = "official"`、`vendor_code = "official"`、描述里带「完成上架」。
`material_capabilities.modes` 还会给出每个型号的参考图字段名，例如
`flux-2-flex` 是 `input_urls`、`seedream-5-0-flash` 是 `image_urls`、`ideogram-v3` 是 `image_url`。

本轮统计：

```
50 条图片记录（49 个型号）里
  14 个可调用（channel 为 OpenAIYI / OpenaiM / openaiD / Google / dashscope_compatible）
  35 个待验证（channel = official）
```

---

## 三、`GET /api/v1/me/tasks` → 200（单价从这里来）

```json
{"tasks": [{"taskId": "task_c6ba98b2…", "model": "nano_banana",
  "path": "/api/v1/apps/nano_banana/submit", "status": "refunded",
  "reservePrice": 72, "actualPrice": 72, "refund": 144,
  "chargedPoints": 72, "refundedPoints": 72, "netPoints": 0,
  "rateNote": "固定 72 点/次"}],
 "total": 1398, "page": 1, "size": 20, "sumPoints": 1616059.4818}
```

要点：

- `size` 固定 20，`limit=2000` 只影响统计窗口、不影响每页条数；
- `actualPrice` 是这一笔的真实成交价，`netPoints` 是净额；
- **单价按 model 归集**：只取 `actualPrice > 0` 的记录，取最小值 / 最大值当区间。

本轮可用的图片型号成交价：

| model | path | actualPrice | 笔数 |
|---|---|---|---|
| `gpt-image-2` | `/api/v1/tasks` | 26.00 | 1 |
| `gpt-image-2-pro` | `/api/v1/tasks` | 39 / 78 / 104 | 17 |
| `seedream-5-0-flash` | `/api/v1/tasks` | 15.60 | 1 |
| `qwen-image-3.0-pro` | `/api/v1/apps/aigc_photo_restore/generate/index` | 105.00 | 16 |
| `nano-banana*` | `/api/v1/apps/nano_banana/submit` | 72.00 | 98+ |

`path` 以 `/api/v1/apps/` 开头的记 `layer=app`（应用层同型号参考价），
以 `/api/v1/tasks` 记账的记 `layer=model`。

---

## 四、`GET /api/v1/pricing` → 200（这里查不到图片单价）

顶层是**裸对象**（不套 `code/data`）：

```json
 "pricing": { … 115 条 … }}
```

通配规则原文：

```json
```

**115 条规则里没有 `/api/v1/images/*`**（`GET /api/v1/pricing` 里搜不到这个键）。
通配的「保底 50 点」与图片线的实际成交（4 - 13.78 点）不是一回事，
所以本包不用 50 点当图片型号的估价，而是用同路成交区间。

---

## 五、`POST /api/v1/images/generations`

### 请求体

| 字段 | 必填 | 取值 | 本包用法 |
|---|---|---|---|
| `model` | 是 | 型号 code，例如 `gpt-image-2.6` | `--models` 逐个 |
| `prompt` | 是 | 非空字符串 | 同一句给所有型号 |
| `n` | 否 | 1 - 4 | `--n` |
| `size` | 否 | `auto` / `1k` / `2k` / `4k` / 宽x高 | `--size` |
| `output_format` | 否 | `png` / `jpeg` / `webp` / `gif` | `--output-format` |
| `response_format` | 否 | `b64_json` / `url` | 默认不传（拿 b64），`--want-url` 改成 url |

### 探针：带 model + 空 prompt

```http
POST /api/v1/images/generations
{"model": "gpt-image-2.6", "prompt": ""}
```

```json
HTTP 422
{"error": {"message": "prompt: String should have at least 1 character",
           "type": "invalid_request_error", "param": "", "code": "bad_request"}}
```

停在参数校验层：**不建任务、不冻结、不扣费**。`doctor` 只用这一条探针。

### 未上架型号：404 HTML

```http
POST /api/v1/images/generations
{"model": "flux-2-flex", "prompt": ""}
```

```html
HTTP 404
<!DOCTYPE html><html><head><meta charset="utf-8">…
<div class="nuxt-spa-loading">…        ← 网关的 SPA 兜底页面，长度 7,859 B
```

同一路径、同一个 Key，换成 `gpt-image-2.6` 就是 422。
说明 404 不是路径错，而是**这个型号没有对应的路由**。

### 上游未激活：502 + 先冻再退

```http
POST /api/v1/images/generations
{"model": "qwen-image-3.0", "prompt": ""}
```

```json
HTTP 502
{"code": 0, "msg": "百炼提交失败：Access denied, please make sure your account is in good standing.
  （该模型可能尚未在阿里云百炼控制台开通/激活，请先在…）"}
```

同秒流水（原文，两条）：

```json
{"at": 1794100560264, "type": "charge", "typeName": "冻结/预扣", "points": -20,
 "reference": "reserve_sync:/api/v1/images/generations", "balanceMoving": true}
{"at": 1794100561106, "type": "refund", "typeName": "退款", "points": 20,
 "reference": "refund:submit_failed:/api/v1/images/generations", "balanceMoving": true}
```

**净 0 点，但钱包被短暂冻结过。** 这是本包只探一条探针的直接原因。

### 同步成功的返回

```json
{"created": 1794000000,
 "data": [{"b64_json": "iVBORw0KGgo…"}, {"b64_json": "iVBORw0KGgo…"}],
 "usage": {"points_cost": 12}}
```

- 没有 `code` 字段（OpenAI 兼容格式），判断成功看 HTTP 200/201 + `data` 非空；
- `response_format: "url"` 时给 `data[0].url`，**约 3 小时过期**、要原样使用
  （追加查询参数会 404），下载不需要 Key 但 `urllib` 要自带 UA，否则 403；
- 部分型号是异步：返回 `data.task_id`，用 `GET /api/v1/tasks/<id>` 查。

---

## 六、流水里能看到的图片价位（`GET /user/balance/logs?limit=1000`）

本轮取最近 1000 条，`reference` 含 `images/generations` 的共 **73 条**（含冻结/退款），
其中真正的结算（`sync:`）71 笔：

| points | 笔数 |
|---|---|
| -6 | 43 |
| -10.54 | 11 |
| -10.6 | 7 |
| -13.78 | 5 |
| -4 | 2（`fallback:`） |
| -7.8 | 1 |
| -12 | 1 |
| -199.9998 | 1 |
| -20 / +20 | 1 / 1（本轮探针的冻结与退款） |

流水条目里 `model` 字段**为空**（73 条全是 `""`），所以流水只能告诉你「一共花了多少」，
**按型号的单价必须从 `/api/v1/me/tasks` 的 `actualPrice` 反推** —— 这是本包的核心方法。

整号流水：`count=1000`（窗口），`total=7891`，`consumePoints=74567.18`。

---

## 七、`GET /api/v1/tasks/<id>` → 200（免费）

```json
{"code": 0, "msg": "任务不存在", "data": null}
```

不存在的 id 也返回 **HTTP 200**，所以判断要看 `code` 与 `data`，不能只看状态码。

真实任务返回（家族实测）：

```json
{"code": 1, "data": {"status": "completed", "tool": "nano_banana",
  "image_urls": ["https://…"], "usage": {"points_cost": 72}}}
```

终态：`completed` / `complete` / `done` / `success` / `succeeded`；
失败：`failed` / `error` / `canceled` / `cancelled` / `timeout` / `refunded`。

---

## 八、`GET /user/balance` 与流水

```json
{"available_points": 999997393470.2579, "points": 999997393470.2579, "frozen": 0,
 "member_points": 0, "yuan": 9999973934.7, "rate": 100, "currency": "points",
 "note": "本平台按用户/Key 独立统计，不与上游租户混用"}
```

`rate = 100` ⇒ **1 元 = 100 点**。

日志顶层：

```json
{"currency": "points", "rate": 100, "count": 1000, "total": 7891,
 "inPoints": 274295.5268, "outPoints": 679944.1125, "netPoints": -405648.5857,
 "consumePoints": 74567.18, "logs": [ … ]}
```

`limit` 上限 1000；`page` 参数不生效（翻页拿到同一批）。

### 本轮 0 点的证明方式

1. `doctor` 打印余额前后对比：`前 999,997,393,470.26 点 -> 后 999,997,393,470.26 点 · 差 0 点`；
2. 流水最新两笔是 09:16 的 `reserve_sync -20` 与 `refund +20`（qwen 探针），净 0；
3. 跑完 doctor 后 `GET /api/v1/me/tasks` 的 `total` 仍是 **1398**，没有新增任务。

---

## 九、计费口径一页纸

| 项 | 口径 |
|---|---|
| 出图 | 按型号计次，`n` 张 = n 倍；单价从 me/tasks 的 actualPrice 反推 |
| 图片线 | 价目表 115 条里没有 `/api/v1/images/*`，走型号计价 |
| 参数错 | 422 / 400 停在提交前，不扣费 |
| 异步失败 | `refunded` + `netPoints = 0`，钱包短暂冻结 |
| 查任务 | `GET /api/v1/tasks/<id>` 免费；应用层 `query` 每次 72 点 |
| 余额口径 | `available_points` 是可用点数，`frozen` 是冻结点数 |
| 图片链接 | 约 3 小时有效，原样使用，下载自带 UA |

---

## 十、本包自己产出的两个文件

`manifest.json`：

```json
{"runId": "20261108-093000", "at": "2026-11-08T09:30:00",
 "prompt": "雨夜街头", "n": 1, "size": "auto", "outdir": "…/run-20261108-093000",
 "results": [{"model": "gpt-image-2.6", "status": "ok", "source": "baseline",
              "unitPoints": 6, "files": ["…/01-gpt_image_2_6-01.png"],
              "actualPoints": 6, "elapsed": 43.6}],
 "totalEstimated": 6, "totalActual": 6}
```

`对比清单.md`：一张表，列为
`型号 / 状态 / 单价（点/张）/ 来源 / 用时 / 出图 / 实际点数`，
末尾按型号列出文件，并给出「合计预估 X 点，实际 Y 点」。
