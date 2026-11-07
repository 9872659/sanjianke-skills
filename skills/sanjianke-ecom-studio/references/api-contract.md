# 接口契约（实测原文）

三条线的端点都在 `https://api.a7w.cn/api/v1`，鉴权只有一个头：

```http
Authorization: Bearer <YOUR_API_KEY>
Accept: application/json
```

网关信封统一为 `{"code": 1, "msg": "success", "data": {...}}`——**`code == 1` 才是成功，`0` 是失败**。
本包按 `code == 1` 判成功（参考实现里踩过把 0 当成功的坑）。

---

## ① 换装 · dressing_diffusion/submit（200 点/次）

### 参数（`GET /api/v1/apps/dressing_diffusion` 的 `params_schema` 原文）

```json
{
  "garment": {
    "type": "object",
    "required": true,
    "description": "服装配置。格式：{\"data\": [{\"category\": \"upper\", \"url\": \"服装图URL\"}, ...]}。category 可选值：upper（上衣）、bottom（下装）、full（连衣裙/全身装）。支持单件或上下套装组合，服装图建议白底平铺。"
  },
  "model_url": {
    "type": "string",
    "example": "https://example.com/model.jpg",
    "required": true,
    "description": "模特图片 URL，建议主体清晰、光线均匀的正面或半身模特图。格式：JPG/PNG"
  }
}
```

> 这份 schema **不是** JSON-Schema 的 `properties` 结构，而是扁平的「字段名 → 定义」。
> `a7w.py schema` 两种都能解析，自己写解析时别只认 `properties`。

### 请求

```http
POST https://api.a7w.cn/api/v1/apps/dressing_diffusion/submit
Content-Type: application/json

{
  "model_url": "https://example.com/model.jpg",
  "garment": {
    "data": [
      {"category": "upper", "url": "https://example.com/shirt.jpg"},
      {"category": "bottom", "url": "https://example.com/pants.jpg"}
    ]
  }
}
```

### 返回（文档原文）

```json
{"task_id": "7xxxxxxxxxxxxxx", "status": "pending"}
```

文档：提交成功后用 `query` 接口轮询，任务通常 **10~30 秒**；建议每 3~5 秒查一次。
**本包轮询走统一的 `GET /api/v1/tasks/<task_id>`**，理由见本文末「价格表」。

### 空 body 的实测（重要）

`POST .../submit` 传 `{}` → **HTTP 200、`code: 1`、`success`，并且真的返回了 `task_id`**（今天实测）。
也就是说这两条应用线的 `submit` 在参数校验之前就把任务建了。**本包任何代码路径都不会发空 body**，
`dress` 缺 `--model-url` 或缺 `--garment` 直接在本地退 2。

---

## ② 出图 · nano_banana/submit（72 点/次）

### 参数（`params_schema` 原文，摘关键字段）

| 参数 | 类型 | 必填 | 默认 | 可选值 |
|---|---|---|---|---|
| `prompt` | string | **是** | — | 画面描述 |
| `action` | string | 否 | `generate` | `generate` / `edit` |
| `model` | string | 否 | `nano-banana` | `nano-banana` / `nano-banana-2` / `nano-banana-2-lite` / `nano-banana-pro` / `nano-banana:official` / `nano-banana-2-lite:official` / `nano-banana-2:official` / `nano-banana-pro:official` |
| `image_urls` | array | `edit` 必填 | — | 参考图 URL 列表（`max_reference_images: 12`） |
| `resolution` | string | 否 | `1K` | `1K` / `2K` / `4K` |
| `aspect_ratio` | string | 否 | `auto` | `auto` / `1:1` / `16:9` / `9:16` / `4:3` / `3:4` / `3:2` / `2:3` / `5:4` / `4:5` / `21:9` |
| `callback_url` | string | 否 | — | HTTPS 回调地址 |

### 请求与返回

```http
POST https://api.a7w.cn/api/v1/apps/nano_banana/submit
Content-Type: application/json

{"prompt": "白色亚麻衬衫平铺在白底上，柔光棚拍", "model": "nano-banana", "aspect_ratio": "1:1"}
```

```json
{"code": 1, "msg": "success",
 "data": {"task_id": "task_xxxxxxxxxxxx", "status": "pending",
          "app": "nano_banana", "api": "submit", "frozen_points": 24}}
```

失败长这样（`code: 0`）：

```json
{"code": 0, "msg": "当前请求未命中可用计费规格，请检查模型、分辨率是否在支持范围内。",
 "data": [], "show": 1}
```

文档列的常见失败：`prompt` 为空、`action` 无效、`model` 不支持、普通模型传入非 `1K` 分辨率、
点数不足、Key 无权限。**这类失败不产生扣费**（平台会退回预扣）。

### 文档里的模型价格摘要（只是摘要，实际按价格表）

| 模型 | 分辨率 | 文档价 |
|---|---|---|
| `nano-banana` | 1K | 24 点/次 |
| `nano-banana-2` | 1K | 38 点/次 |
| `nano-banana-pro` | 1K | 45 点/次 |
| `nano-banana:official` | 1K | 28.03 点/次 |
| `nano-banana-2:official` | 1K / 2K / 4K | 35.76 点/次起 |
| `nano-banana-pro:official` | 1K / 2K / 4K | 61.52 点/次起 |

⚠ 这张表是**上游模型档位价**，不是本站售价。本站 `/api/v1/pricing` 对 `nano_banana/submit`
是 **flat 72 点/次**（见下），以价格表为准；本站文档也写明了「完整实时价格以当前租户配置和价格查询接口为准」。

---

## ③ 主图 · images/generations（gpt-image-2.6，6 点/张）

沿用同族 `sanjianke-gpt-image` 已实测的契约：

```http
POST https://api.a7w.cn/api/v1/images/generations
Content-Type: application/json

{"model": "gpt-image-2.6", "prompt": "...", "n": 1,
 "size": "1024x1024", "output_format": "png", "response_format": "b64_json"}
```

- **同步**返回；`data[]` 里是 `b64_json` 或 `url`（两种都要处理）
- **6 点/张**，按 `data` 里实际返回张数计费；`n` 只能 1–4
- 参数错 / 失败 / 没出图 → 不扣费
- 缺 `prompt`（空字符串）→ **422**「String should have at least 1 character」，本包 `doctor` 就拿它当探针
- 端点少写 `/api` 会被路由到网关默认应用并**静默忽略 model**（同族实测），所以 `doctor` 必须验这条

---

## 统一任务查询 · GET /api/v1/tasks/{task_id}（免费）

```http
GET https://api.a7w.cn/api/v1/tasks/task_xxxxxxxxxxxx
```

实测（一条历史失败任务）：

```json
{"code":1,"msg":"success","data":{"task_id":"task_702b8f9678f9eaadbd92fab3",
 "model":"grok_video/submit","type":"app","call_type":"async","status":"failed",
 "created_at":"2026-11-07T17:51:39Z",
 "error":{"code":"missing_input","message":"任务处理失败，请稍后重试"}}}
```

不存在的任务：

```json
{"code":0,"msg":"任务不存在","data":null}
```

状态取值见过 `pending` / `processing` / `completed` / `failed`。本包把
`completed|complete|done|success|succeeded` 当成功终态，
`failed|error|canceled|cancelled|timeout` 当失败终态，其余继续等。

---

## 价格表 · GET /api/v1/pricing（免费，裸对象不套信封）

`GET /api/v1/pricing` 返回的是**裸对象**（没有 `code`/`data` 信封）：

```json
{"currency":"points","markupPercent":20,
 "note":"User price = upstream points x (1 + markup%). 实际成本以上游响应标记为准。",
 "pricing":{ ... }}
```

`pricing` 里与本包三条线相关的原文：

```json
"/api/v1/apps/dressing_diffusion/*":  {"mode":"flat","cost":200,"markupPercent":0,
  "note":"固定 200 点/次（上游约 100 点 ×2）"},
"/api/v1/apps/dressing_diffusion/submit": {"mode":"flat","cost":200,"markupPercent":0,
  "note":"固定 200 点/次（上游约 100 点 ×2）"},
"/api/v1/apps/nano_banana/*": {"mode":"flat","cost":72,"markupPercent":0,
  "note":"★★ Q52（2026-10-05 站主指定定价「商品多角度是视角选项每一个选择25点，AI商品图固定价格72点」）：AI商品图 = 固定 72 点/次；商品多角度 = 25 点 × 选中视角数（请求体带 views[] 时生效，不带 views 时仍按本固定价 72）。"},
"/api/v1/apps/nano_banana/submit": {"mode":"flat","cost":72,"markupPercent":0}
```

两条要记在心里的推论：

1. **`/api/v1/apps/<app>` 这个 schema 读路径也落在 `<app>/*` 里**。实测读一次
   `GET /api/v1/apps/dressing_diffusion` 就记了一条 `sync:/api/v1/apps/dressing_diffusion −200`，
   读一次 `nano_banana` 记 `−72`。想免费看能力，用 `/api/v1/apps` 列表（价格表里 `cost: 0`）。
2. **应用级 `query` 没有单独标 0**。同表的 `pic_lipsync/query`、`flashvsr/query` 都显式写了
   `"cost": 0`，而 `dressing_diffusion`、`nano_banana` 的 `query` 会命中 `<app>/*`（200 / 72）。
   所以本包的轮询一律走 `/api/v1/tasks/<task_id>`。

另有隐藏口径：`nano_banana` 请求体带 `views[]` 时按 **25 点 × 视角数** 计费。本包不传 `views`。

---

## 本轮探针记录（0 个任务，0 次 submit）

| 探针 | 形态 | 结果 | 花费 |
|---|---|---|---|
| `GET /api/v1/models` | 只读 | 200 | 0 |
| `GET /api/v1/apps` | 只读（价格表 `cost: 0`） | 200，22 个应用 | 0 |
| `GET /api/v1/pricing` | 只读 | 200，115 条规则 | 0 |
| `GET /api/v1/tasks/<id>` | 只读 | 200 / `任务不存在` | 0 |
| `POST /api/v1/images/generations` `{"model":…,"prompt":""}` | 参数校验 | **422** | 0 |
| `GET /api/v1/apps/dressing_diffusion` | 读 schema | 200 | **−200**（见下） |
| `GET /api/v1/apps/nano_banana` | 读 schema | 200 | **−72**（见下） |
| 两个应用的 `submit` | **一次都没发** | — | 0 |

余额流水原文（`GET /user/balance/logs`，节选三条本包探针造成的预扣）：

```
19:35:08  out  冻结/预扣  -200  sync:/api/v1/apps/dressing_diffusion
19:35:11  out  冻结/预扣   -72  sync:/api/v1/apps/nano_banana
19:35:34  out  冻结/预扣  -200  sync:/api/v1/apps/dressing_diffusion
```

第一、三条是同一条 schema 被读了两次（第一次拿参数、第二次复核），第二次是多花的 200 点。
**结论写进 `doctor`：单应用 schema 一次都不读。**
