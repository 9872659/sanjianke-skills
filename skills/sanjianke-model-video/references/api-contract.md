# 视频生成台（模型层）—— 接口契约

本文全部是**实测原文**（2026-11-07，本机真实 Key，逐条贴返回）。
凡是标「实测」的，都是本机跑出来的，不是文档抄的。

- 根地址：`https://api.a7w.cn/api/v1`
- 鉴权：`Authorization: Bearer <你的 API Key>`
- 1 元 = 100 点

---

## 1) `POST /api/v1/videos` —— 提交（OpenAI 视频接口形态）

`POST /api/v1/videos` 与 `POST /api/v1/videos/generations` **等价**，两条都能用。
模型层 ID 直接填在 `model` 里（不是 `model_code`）。

### 请求

```json
{
  "model": "sd/doubao-seedance-2-0-260128",
  "prompt": "山间的雾慢慢飘过松林，镜头缓慢推进",
  "seconds": 5,
  "size": "1280x720",
  "input_reference": "https://example.com/first-frame.jpg",
  "images": ["https://example.com/ref1.jpg", "data:image/png;base64,..."]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | 模型层 ID。`{}` 空 body 时返回 `Model name not specified` |
| `prompt` | 是 | 画面描述。`muse-video` 上限 4000 字 |
| `seconds` | 否 | 秒数。字符串或数字都行（`muse-video` 认 4–180） |
| `size` | 否 | `1280x720` / `720x1280`（`muse-video` 只出这两种） |
| `input_reference` | 否 | 首帧图：URL 或 data URL |
| `images` | 否 | 多图参考，第 1 张＝开头画面 |
| `content` | 否 | 原生形态（seedance 族认）；缺 `prompt` 时的报错会点它的名 |

`--extra` 可以把原生参数直接塞进去，例如 `{"ratio":"9:16","resolution":"720p"}`。

### 返回（`muse-video` 实测）

```json
{"id":"task_9xQe2Lm7Vb4R...","object":"video","model":"muse-video",
 "status":"queued","progress":0,"created_at":1793962453}
```

模型层 ID 的返回可能套一层 `{"code":1,"data":{...}}`，本包两种都认
（`id` / `task_id` / `taskId` 都试）。

### 错误（实测）

| 请求 | HTTP | 返回原文 |
|---|---|---|
| `{}` | 400 | `{"error":{"code":"","message":"Model name not specified, model name cannot be empty (request id: …)","type":"new_api_error"}}` |
| `{"model":"muse-video"}` | 400 | `{"code":"plugin_request_invalid","message":"field prompt is required","data":null}` |
| `{"model":"sd/doubao-seedance-2-0-260128"}` | 400 | `{"error":"prompt or content field is required","type":"invalid_request_error"}` |
| `{"model":"volcengine/doubao-seedance-2-5-260628"}` | 400 | 同上 |
| `{"model":"wan3.0-video"}` | **502** | `{"code":0,"msg":"百炼提交失败：Access denied, please make sure your account is in good standing…","data":null}` |

> **`wan3.0-video` 这条探针会动钱包。** 实测同一时刻的流水：
> `11-07 23:54:07 charge -300 reserve_sync:/api/v1/videos`
> → `11-07 23:54:08 refund +300 refund:submit_failed:/api/v1/videos`。
> 净 0 点，但冻结过一次，余额不再足额时这条会直接失败。本包 `doctor` 不探它。

---

## 2) `GET /api/v1/videos/{id}` —— 视频任务视图（Muse 族）

```json
{"id":"task_9xQe2Lm7Vb4R...","object":"video","model":"muse-video",
 "status":"completed","progress":100,"seconds":"5","size":"1280x720",
 "video_url":"https://cdn3.saasos.cn/vr/xxxx.mp4",
 "url":"https://cdn3.saasos.cn/vr/xxxx.mp4","expires_at":1794567332,
 "created_at":1793962453,"completed_at":1793962532}
```

- 假 id 实测：`400 {"code":"task_not_exist","message":"task_not_exist","data":null}`
- `status`：`queued` / `in_progress` / `completed` / `failed` / `unknown`
- `video_url` 与 `url` 同值，不需要密钥；实测 Muse 的 `expires_at` 比 `completed_at` 晚 7 天
- 失败：`{"error":{"code":"video_generation_failed","message":"…"}}`，预扣全额退回

---

## 2b) `GET /api/v1/videos/generations/{id}` —— 模型层 Seedance 族的查询路由

**这条是本包实测出来的关键一条**：Seedance 族的 taskId 是 UUID 形态，
打到 `/tasks/{id}` 会回 `404 page not found`、打到 `/videos/{id}` 会回 400 `task_not_exist`，
只有这条认得它（HTTP 200）：

```json
{"id":"3eeb28b9-3672-49ad-91a3-79a9d352f673",
 "model":"doubao-seedance-2-0-260128",
 "status":"succeeded","generation_status":"succeeded","delivery_status":"ready",
 "duration":4,"created_at":"2026-11-06T14:46:19Z","updated_at":"2026-11-06T14:49:00Z",
 "video_url":"https://xrtoken-storage-bj.tos-cn-beijing.volces.com/ark/…mp4?X-Tos-…",
 "video_url_expires_at":"2026-11-08T16:13:59.581602195Z",
 "video_url_source":"tos",
 "result":{"ratio":"16:9","resolution":"480p","framespersecond":24,"generate_audio":true,
           "output_format":"mp4","duration":4,"seed":7410,
           "usage":{"completion_tokens":40594,"total_tokens":40594},
           "video_url":"https://…mp4"},
 "storage":{"status":"ready","video_url":"https://…mp4"},
 "result_query_path":"/v1/videos/generations/3eeb28b9-3672-49ad-91a3-79a9d352f673"}
```

按 id 形态选路由：

| id 形态 | 谁在用 | 能用哪条 |
|---|---|---|
| `task_…`（22 位） | `muse-video`、Muse 族 | `/tasks/{id}`（200）· `/videos/{id}`（200）· `/videos/generations/{id}`（404 `task not found`） |
| UUID（`8-4-4-4-12`） | `sd/…`、`volcengine/…` Seedance 族 | **`/videos/generations/{id}`（200）** · `/tasks/{id}`（404 裸文本）· `/videos/{id}`（400 `task_not_exist`） |

`status` 与 `wait` 三条依次试，命中即用；`wait` 每 15 秒查一次，全程 0 点。
`result.usage.total_tokens` 是上游出片的 token 口径（本例 40,594），可与 `actualPrice` 互相印证。

---

## 3) `GET /api/v1/tasks/{id}` —— 通用任务查询（免费）

- 假 id 实测：`200 {"code":0,"msg":"任务不存在","data":null}`
- 真任务会带 `status` / 实扣 / 冻结等字段；本包把它和 `/videos/{id}` 合并成一屏。

---

## 4) `GET /api/v1/me/tasks?limit=2000&page=N` —— 报价数据源

**每页恒 20 条**（`size` / `per_page` 无效），`limit` 只影响统计窗口。响应顶层：

```json
{"page":1,"size":20,"total":1398,"sumPoints":1616059.4818,
 "sumRefund":…,"sumYuan":…,"tasks":[…20 条…]}
```

单条任务（模型层）长这样：

```json
{"taskId":"1666cb7e-…","model":"volcengine/doubao-seedance-2-5-260628",
 "type":"模型","path":"/api/v1/videos/generations","status":"succeeded",
 "reservePrice":3000.000003,"actualPrice":762.3,"refund":0,
 "frozenPoints":3000.000003,"chargedPoints":762.3,"netPoints":762.3,
 "rateNote":"官方价 × 2.00（≈ +100%）","feeYuan":7.62,
 "charges":[{"at":…,"type":"reserve","points":0},…]}
```

筛法：`path` 不含 `/apps/` 且 `model` 非空 → 这是模型层任务。
`rateNote` 恒为「官方价 × 2.00（≈ +100%）」，正好对上通配规则的 `markupPercent: 100`。

### 实测样本（本机 1398 条任务里筛出来的）

| model | path | actualPrice | 条数 |
|---|---|---|---|
| `sd/doubao-seedance-2-0-260128` | `/api/v1/videos/generations` | 145.73 / 181.79 / 3000 | 5 |
| `volcengine/doubao-seedance-2-5-260628` | `/api/v1/videos/generations` | 762.30 / 3000 / 3045.71 | 3 |
| `wan3.0-video` | `/api/v1/videos/generations` | 300（全部） | 8 |
| `muse-video` | `/api/v1/videos` | 44 / 55 / 260 | 8 |

Seedance 两档的 `reservePrice` 都是 `3000.000003`：**预冻结按 3,000 点冻**，
完成后才按 `actualPrice` 结算。这就是本包闸门按「区间上限」判定的原因。

---

## 5) `GET /api/v1/pricing` —— 价目表里没有模型层

结构：`{currency, markupPercent, note, site, pricing:{路径 -> 规则}}`，共 115 条规则。
模型层命中的是通配 `*`：

```json
"*": {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
      "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}
```

- 全表**没有** `modelPricing` 键；没有任何「模型 code → 单价」的映射。
- `modelRates` 只出现在 3 条 `image_human` 规则上，配 `rateFrom: "mode"`、
  `defaultModel: "fast"` 使用：

```json
"modelRates": {"fast":{"*":10},"standard":{"*":15},"2k":{"*":30},"4k":{"*":60}}
```

即「按请求体 `mode` 取费率」，**不是模型层价目表**。`doctor` 会把这条现状当一项检查。

---

## 6) `GET /api/v1/models` —— 模型目录

实测 316 条，分两类：

1. **221 条目录模型**（带 `model_code` / `type_code` / `max_reference_images` / `description`），
   其中 `type_code == "video"` 的 **47 条**（`muse-video`、`wan3.0-video`、`seedance-2` 族、
   `veo3.1-pro`、`kling-*`、`hailuo-*` …）。
2. **95 条「裸模型层 ID」**（只有 `id` / `object` / `owned_by` / `created`，没有价格字段）：

```json
{"id":"volcengine/doubao-seedance-2-5-260628","object":"model",
 "owned_by":"flagship","created":0}
```

本包用的 4 个 ID 里，`sd/doubao-seedance-2-0-260128` 与
`volcengine/doubao-seedance-2-5-260628` 在第 2 类里，`wan3.0-video` 与
`muse-video` 在第 1 类里 —— 两类都能直接塞进 `POST /api/v1/videos` 的 `model`。

---

## 7) 余额与流水

| 端点 | 实测 | 说明 |
|---|---|---|
| `GET /api/v1/user/balance` | 200 | `{available_points, points, frozen, yuan, rate:100, currency:"points"}` |
| `GET /user/balance/logs?limit=200` | 200 | `{count,total,inPoints,outPoints,netPoints,consumePoints,balanceMoving,logs[…]}` |
| `GET /api/v1/user/balance/logs` | 200（**回的是余额对象，164 B，没有 logs**） | 这个前缀下没有流水，用上面那条 |

一条流水：

```json
{"at":1794065607768,"type":"charge","typeName":"冻结/预扣","kind":"out",
 "points":-300,"balanceAfter":null,"path":"/api/v1/videos",
 "taskId":"…","reference":"reserve_sync:/api/v1/videos","model":"wan3.0-video",
 "provider":"bailian"}
```

- `type`：`charge`（冻结/预扣）/ `refund`（退回）/ `reserve`（预留冻结，不带 balance）
- `reference` 里的前缀就是计费形态：`reserve_sync:` / `refund:` / `refund:submit_failed:` / `refund:settle:`
- `limit` 上限 1000，`count` 是本次返回条数，`total` 是全量条数

---

## 8) 免费 / 收费端点速查（本机逐条实测）

| 端点 | 形态 | 计费 |
|---|---|---|
| `GET /api/v1/models` | 只读 | 0 |
| `GET /api/v1/apps` | 只读 | 0 |
| `GET /api/v1/pricing` | 只读 | 0 |
| `GET /api/v1/tasks/{id}` | 只读 | 0 |
| `GET /api/v1/videos/{id}` | 只读（假 id 400 `task_not_exist`） | **0** |
| `GET /api/v1/videos/generations/{id}` | 只读（Seedance 族唯一认的查询路由） | **0** |
| `GET /api/v1/me/tasks` | 只读 | 0 |
| `GET /api/v1/user/balance` | 只读 | 0 |
| `GET /user/balance/logs` | 只读 | 0 |
| `POST /api/v1/upload` | multipart，字段名 `file` | 0 |
| `POST /api/v1/videos` | 缺 prompt / 空 body | 400，0（`wan3.0-video` 例外：先冻 300 再退） |
| `POST /api/v1/apps/<app>/query` | **应用层轮询** | **按次扣，不退**（nano_banana 72 点/次） |
| `GET /api/v1/apps/<app>` | 应用详情 | **按该应用 flat 单价扣，不退**（dressing_diffusion 200、nano_banana 72） |
| `POST /api/v1/apps/<app>/submit` | 缺必填 | 先 `reserve_sync` 冻结再校验，失败全额退（净 0，钱包被冻过） |

---

## 9) 倍数换算（实测，全部可复算）

```
11,000 / 145.73 = 75.48    sd/doubao-seedance-2-0-260128
11,000 / 762.30 = 14.43    volcengine/doubao-seedance-2-5-260628
   800 / 300.00 =  2.67    wan3.0-video
```

应用层对照价来自 `GET /api/v1/pricing` 里 `/api/v1/apps/seedance/submit` 的
`flat cost: 11000`、`/api/v1/apps/wan/submit` 的 `flat cost: 800`。
