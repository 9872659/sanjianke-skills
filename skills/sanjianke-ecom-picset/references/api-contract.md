# 接口契约（2026-11-07 实测原文 + 参数）

> 本文件记的是**这一轮真的打出来的返回**与**参数形态**。标「上一轮实测」的条目是
> 家族里别的包验过、本轮为 0 花费没有复测（复测会扣钱，见每条的说明）。

网关根地址：`https://api.a7w.cn`，业务前缀 `/api/v1`。
Key：`Authorization: Bearer sk-…`。

---

## 一、四条路径一览

| 用途 | 方法与路径 | 单价 | 形态 | 消息体 |
|---|---|---|---|---|
| 文生图 | `POST /api/v1/images/generations` | 6 点/张 | 同步 | JSON |
| 改图 | `POST /api/v1/images/edits` | 6 点/次 | 同步 | multipart/form-data |
| nano 出图 | `POST /api/v1/apps/nano_banana/submit` | 72 点/次 | 异步 | JSON |
| 换装 | `POST /api/v1/apps/dressing_diffusion/submit` | 200 点/次 | 异步 | JSON |
| 异步轮询 | `GET /api/v1/tasks/<task_id>` | **0 点** | 只读 | — |

---

## 二、免费只读接口（本轮原文）

### `GET /user/balance` → 200

```json
{"available_points": 999997393482.2579, "points": 999997393482.2579, "frozen": 0,
 "member_points": 0, "yuan": 9999973934.82, "rate": 100, "currency": "points",
 "note": "本平台按用户/Key 独立统计，不与上游租户混用"}
```

`rate = 100` ⇒ **1 元 = 100 点**。

### `GET /api/v1/models` → 200（总计 221 个模型）

`gpt-image-2.6` 的完整记录（原文，未删字段）：

```json
{"model_code": "gpt-image-2.6", "model_name": "GPT Image 2.6",
 "description": "1K 图片生成与参考图编辑，按次计费。", "call_type": 2,
 "supports_vision": 1, "max_reference_images": 6, "channel_code": "OpenAIYI",
 "channel_name": "官方平台", "vendor_code": "openai", "type_code": "image",
 "type_name": "图片生成", "call_type_desc": "异步",
 "capabilities": {"supports_vision": true, "max_reference_images": 6}}
```

要点：**`max_reference_images = 6`** ⇒ 改图一次最多带 6 张参考图（本包 `--ref` 上限 6）。
`nano-banana` / `nano-banana-2` / `nano-banana-pro` 的 `max_reference_images = 12`。

### `GET /api/v1/apps` → 200（22 个应用）

只读目录，价格表里 `cost: 0`。与本包相关的两个应用（原文）：

```json
{"id": 22, "name": "nano-banana", "code": "nano_banana", "billing_mode": 1,
 "apis": [{"code": "submit", "name": "创建图片任务", "method": "POST"},
          {"code": "query",  "name": "查询图片任务", "method": "GET"}]}

{"id": 9, "name": "AI换装", "code": "dressing_diffusion", "billing_mode": 1,
 "apis": [{"code": "submit", "name": "提交换装任务", "method": "POST"},
          {"code": "query",  "name": "查询换装结果", "method": "POST"}]}
```

**注意这条 `query`**：它虽然在架，但按次扣费（见第五节流水）。

### `GET /api/v1/pricing` → 200（115 条规则）

顶层是**裸对象**（不套 `code/data` 信封）：

```json
 "site": "api", "pricing": { … 115 条 … }}
```

与本包相关的四条原文：

```json

  "note": "AI商品图 = 固定 72 点/次；商品多角度 = 25 点 × 选中视角数（请求体带 views[] 时生效，
           不带 views 时仍按本固定价 72）"}

  "note": "固定 200 点/次"}

  "note": "★应用目录（只读）不计费（2026-10-04）…"}
```

**关键：115 条里没有 `/api/v1/images/*`。** 图片线按**模型**计次，不走路径 flat，
所以真实单价只能看流水（第五节），不能看这张表。

### `GET /api/v1/tasks/<不存在的 id>` → 200

```json
{"code": 0, "msg": "任务不存在", "data": null}
```

返回 200 但 `code = 0` ⇒ **判断成功必须看 `code`，不能只看 HTTP 状态**。
这条也是免费的，可以放心用来验路由。

---

## 三、文生图：`POST /api/v1/images/generations`

### 请求体（JSON）

| 字段 | 必填 | 取值 | 本包用法 |
|---|---|---|---|
| `model` | 是 | `gpt-image-2.6` | 固定 |
| `prompt` | 是 | 非空字符串 | 每个位一段（见 `plan.json`） |
| `n` | 否 | `1–4` | **固定 1**：一张一次请求，点数 = 张数，不打包赌价 |
| `size` | 否 | `auto` / `1k` / `2k` / `4k` / `宽x高` | 按平台换算（见第四节） |
| `output_format` | 否 | `png` / `jpeg` / `webp` / `gif` | `png` |
| `response_format` | 否 | `b64_json` / `url` | `b64_json`（两种返回本包都会处理） |
| `background` | 否 | `auto` / `transparent` / `opaque` | 未用 |
| `quality` | 否 | `auto/low/medium/high/xhigh/max` | 未用（只作提示，不影响价格） |
| `output_compression` | 否 | `0–100` | 未用（只对 jpeg/webp 生效） |

### 端点探针（本轮原文，0 点）

```http
POST /api/v1/images/generations
{"model": "gpt-image-2.6", "prompt": ""}
```

```json
HTTP 422
{"detail": [{"type": "string_too_short", "loc": ["body", "prompt"],
  "msg": "String should have at least 1 character", …}]}
```

**这就是 `doctor` 用的探针**：带 model、把 prompt 留空 → 参数校验层直接拦下，
停在扣费之前。拿到 422 且文案含 `at least 1 character` 才算端点对了。

### 返回

```json
{"created": 1794000000, "data": [{"b64_json": "iVBORw0KGgo…"}]}
```

- 没有 `code` 字段（OpenAI 兼容格式），判断成功看 HTTP 200/201 + `data` 非空；
- `response_format: "url"` 时改给 `data[0].url`，**约 3 小时过期**，且要**原样使用**
  （追加查询参数会 404），下载不需要 Key，但 `urllib` 必须自带 `User-Agent`，否则 403。

---

## 四、尺寸：四条硬约束 + 换算表

gpt-image 的自定义尺寸要同时满足：

1. 宽、高都是 **16 的倍数**；
2. 长边 / 短边 **≤ 3:1**；
3. 单边 **≤ 3840**；
4. 总像素 **655,360 – 8,294,400**。

**所以 800×800 是非法尺寸**：800 × 800 = **640,000**，比下限少 15,360。
本包在 `plan` 阶段就按平台换好，不等上游 400：

| 平台预设 | 平台要求 | 下单的 `size` | 像素 | 验证 |
|---|---|---|---|---|
| `taobao` / `1688` / `pinduoduo` | 800×800（1:1） | `1024x1024` | 1,048,576 | 16 倍数 ✓，比例 1:1 ✓ |
| `taobao34` | 750×1000（3:4） | `768x1024` | 786,432 | 750 不是 16 倍数；768×1024 恰 3:4 ✓ |
| `douyin` | 1200×1600（3:4） | `1200x1600` | 1,920,000 | 二者都是 16 倍数 ✓ |
| `detail` | 750 宽（详情单屏） | `768x1024` | 786,432 | 出完统一缩到 750 宽再拼 |

本地 `check_size` 会把这四条全验一遍，任一不过直接退 2，不发请求。

---

## 五、流水里的真实单价（`GET /user/balance/logs`）

`limit` 上限 1000，`page` 参数不生效（翻页两次拿到的是同一批）。取最近 1000 条统计：

| reference（流水里的记账键） | 笔数 | 每笔点数 | 小计 |
|---|---|---|---|
| `sync:/api/v1/images/generations` | 138 | **多数 −6**（82 笔）；另有 −4 / −7.8 / −10.54 / −10.6 / −12 / −13.78 / −36 / −60 | −1,641.68 |
| `fallback:/api/v1/images/generations` | 10 | −4（8 笔）/ −29.2（2 笔） | −90.40 |
| `sync:/api/v1/images/edits` | 2 | **−6**（两笔都是） | −12.00 |
| `sync:/api/v1/apps/nano_banana` | 2 | −72 | −144.00 |
| `sync:/api/v1/apps/nano_banana/query` | **216** | **−72** | **−15,552.00** |
| `/api/v1/apps/nano_banana/query` | 18 | −72 | −1,296.00 |
| `sync:/api/v1/apps/dressing_diffusion` | 4 | −200 | −800.00 |

结论：

1. **图片线 6 点/张、改图 6 点/次**——正文里的报价就是这两行的实测价；
   不同尺寸/模型会落到 −10.54、−13.78 这类非整数，所以本包固定 1024×1024 档的 6 点，
   不拿大尺寸去猜价。
2. **应用层 `query` 按次扣费**：nano 的 query 216 笔就烧掉 15,552 点。
   本包轮询因此只走 `GET /api/v1/tasks/<id>`（第五节下半）。
3. 流水里的 `path` 字段对异步任务指向 `/api/v1/tasks/<taskId>`，那是**任务自身的
   冻结/结算事件**，不是「读任务被扣费」。读任务免费的证据是本包 `doctor` 的
   余额前后对比（差 0）。

同一页流水里还能量到任务级的账（`GET /api/v1/me/tasks`）：

```json
{"taskId": "task_c6ba98b2…", "model": "nano_banana", "path": "/api/v1/apps/nano_banana/submit",
 "status": "refunded", "reservePrice": 72, "actualPrice": 72, "refund": 144,
 "chargedPoints": 72, "refundedPoints": 72, "netPoints": 0, "rateNote": "固定 72 点/次"}
```

⇒ 换装/出图这类异步任务失败会**全额退**（`netPoints = 0`），但钱包会被短暂冻结。

---

## 六、nano_banana：`POST /api/v1/apps/nano_banana/submit`

> 参数形态来自**上一轮**从应用 schema 读出的结果（读一次 `GET /api/v1/apps/nano_banana`
> 就是 72 点，本轮为 0 花费**没有复读**）。字段本身由 `--dry-run` 的请求体逐字打印，可核对。

| 字段 | 必填 | 取值 |
|---|---|---|
| `prompt` | 是 | 画面描述 |
| `action` | 否 | `generate` / `edit`（`edit` 时 `image_urls` 必填，最多 12 张） |
| `model` | 否 | `nano-banana` / `nano-banana-2` / `nano-banana-2-lite` / `nano-banana-pro`（含 `:official` 变体） |
| `resolution` | 否 | `1K` / `2K` / `4K` |
| `aspect_ratio` | 否 | `auto` / `1:1` / `16:9` / `9:16` / `4:3` / `3:4` / `3:2` / `2:3` / `5:4` / `4:5` / `21:9` |
| `image_urls` | 否 | 参考图 URL 数组 |

返回（网关信封，`code == 1` 才是成功）：

```json
{"code": 1, "msg": "success", "data": {"task_id": "task_…", "frozen_points": 72}}
```

**空 body 也会建单**（上一轮实测）⇒ 本包本地先校验必填，缺一个就退 2，一个请求都不发。

---

## 七、换装：`POST /api/v1/apps/dressing_diffusion/submit`

> 同上：参数来自上一轮 schema 读取（读一次 200 点），本轮未复读。

```json
{"model_url": "https://…/model.jpg",
 "garment": {"data": [{"category": "upper", "url": "https://…/shirt.jpg"}]}}
```

`category` 取 `upper` / `bottom` / `full`，可多件。异步，返回 `task_id`，文档说 10–30 秒出图。
本包的 `cost --dress` 只报价（200 点），**真实换装调用交给 `sanjianke-ecom-studio`**，
避免同一个动作两个包各写一套。

---

## 八、异步轮询：`GET /api/v1/tasks/<task_id>`

```json
{"code": 1, "data": {"status": "completed", "tool": "nano_banana",
  "image_urls": ["https://…"], "usage": {"points_cost": 72}}}
```

- 终态：`completed` / `complete` / `done` / `success` / `succeeded`；失败：`failed` / `error` /
  `canceled` / `cancelled` / `timeout` / `refunded`；
- 轮询间隔 5 秒、上限 600 秒（`--wait` / `--every` 可调）；
- **只走这一条**，因为应用层 `query` 每次 72 点（见第五节）。

---

## 九、计费口径一页纸

| 项 | 口径 |
|---|---|
| 文生图 | 6 点/张，按 `data` 里**实际返回张数**；本包 `n=1`，一张一次请求 |
| 改图 | 6 点/次（流水两笔各 −6） |
| nano 出图 | 72 点/次（价格表 flat；带 `views[]` 时改 25 点 × 视角数） |
| 换装 | 200 点/次（价格表 flat） |
| 失败 | 参数错 / 没出图 → 不扣费；异步任务失败 → 冻结全额退（`netPoints = 0`） |
| 对话式记账 | `GET /user/balance/logs` 的 `points` 是流水口径；净变动看 `balanceMoving` |
| 图片链接 | 约 3 小时过期，原样使用，下载免 Key 但要自带 UA |
