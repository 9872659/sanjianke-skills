# 接口契约（实测原文，2026-11-08）

本文件里的每一条都是本账号真实返回，不是文档抄的。
网关：`https://api.a7w.cn`。鉴权：`Authorization: Bearer <你的 Key>`。
1 元 = 100 点（`GET /user/balance` 里 `rate: 100`）。

---

## 1. 两条提交端点，别混用

| 端点 | 认哪些 model | 实测状态 |
|---|---|---|
| `POST /api/v1/videos` | 只有 4 个裸模型层 ID：`muse-video`、`sd/doubao-seedance-2-0-260128`、`volcengine/doubao-seedance-2-5-260628`、`wan3.0-video` | 目录型号打进来是 `404 model_not_found` |
| `POST /api/v1/videos/generations` | 全部 47 个目录视频型号 + 上面 4 个裸 ID | 13 个型号逐条实测都停在 `400 prompt is required` |

同一台机器、同一个 Key、同一个型号名，两条路由的返回完全不同：

```http
POST /api/v1/videos
{"model":"kling-4-0"}

HTTP 404
{"error":{"code":"model_not_found",
          "message":"The model `kling-4-0` does not exist or you do not have access to it.",
          "type":"invalid_request_error"}}
```

```http
POST /api/v1/videos/generations
{"model":"kling-4-0"}

HTTP 400
{"error":"prompt or content field is required","type":"invalid_request_error"}
```

`400 prompt ... required` 说明**型号已解析、参数校验拦下**，这是「这条路由认这个型号」的免费判据。
`404 model_not_found` 说明这条路由的模型清单里没有它。

### 空 body 探针（0 点）

```http
POST /api/v1/videos                 {}
HTTP 400  {"error":{"code":"","message":"Model name not specified, model name cannot be empty (request id: 20261108014259... )","type":"new_api_error"}}

POST /api/v1/videos                 {"prompt":"probe only"}
HTTP 400  同上（先查 model）

POST /api/v1/videos                 {"model":"muse-video"}
HTTP 400  {"code":"plugin_request_invalid","message":"field prompt is required","data":null}

POST /api/v1/videos                 {"model":"sd/doubao-seedance-2-0-260128"}
HTTP 400  {"error":"prompt or content field is required","type":"invalid_request_error"}

POST /api/v1/videos/generations     {}
HTTP 400  {"error":"model field is required","type":"invalid_request_error"}

POST /api/v1/videos/generations     {"model":"kling-4-0"}
HTTP 400  {"error":"prompt or content field is required","type":"invalid_request_error"}
```

六次探针，流水 0 条新增（`GET /user/balance/logs?limit=3` 前后一致）。

### 28 个型号逐条探针结果（全部 400、全部 0 点）

```
kling-4-0                          400 prompt or content field is required
kling-v2-1-pro                     400 prompt or content field is required
kling-v2-1-standard                400 prompt or content field is required
kling-2-1-master                   400 prompt or content field is required
kling-ai-avatar-standard           400 prompt or content field is required
kling-ai-avatar-pro                400 prompt or content field is required
kling-2-5-turbo-pro                400 prompt or content field is required
kling-2-6                          400 prompt or content field is required
kling-2.6-motion-control           400 prompt or content field is required
kling-3.0-video                    400 prompt or content field is required
kling-3.0-motion-control           400 prompt or content field is required
kling-3-0-turbo                    400 prompt or content field is required
kling-3.0-omni-transformation      400 prompt or content field is required
kling-3-0-omni                     400 prompt or content field is required
veo3.1-pro                         400 prompt or content field is required
veo3.1-fast                        400 prompt or content field is required
hailuo-02-standard                 400 prompt or content field is required
hailuo-02-pro                      400 prompt or content field is required
vidu-q4                            400 prompt or content field is required
runway                             400 prompt or content field is required
pixverse-v6                        400 prompt or content field is required
pixverse-v6-max                    400 prompt or content field is required
muse-video                         400 plugin_request_invalid（field prompt is required）
grok-video                         400 prompt or content field is required
minimax-h3                         400 prompt or content field is required
h3-video                           400 prompt or content field is required
sd/doubao-seedance-2-0-260128      400 prompt or content field is required
volcengine/doubao-seedance-2-5-260628  400 prompt or content field is required
```

`wan3.0-video` 本轮**没有**探：2026-11-07 实测它在 `/videos` 上 `502` 且
`reserve_sync -300` 先冻再 `refund +300`，净 0 但钱包被冻过。
它的价格用台账 8 笔成交作证（全是 300 点）。

---

## 2. 请求体

本包发出的 body（`gen`）：

```json
{"model": "kling-4-0", "prompt": "雨夜街头，霓虹灯下撑伞的女孩回头", "seconds": 5}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | 型号名（见 `catalog`）；缺了 `400 model field is required` |
| `prompt` | 是 | ≤4000 字；缺了 `400 prompt or content field is required` |
| `seconds` | 否 | 每条多少秒，本包默认 5（1 - 180） |
| `size` | 否 | `宽x高`，例如 `1280x720` / `720x1280`；不给就用模型默认 |
| `ratio` 等 | 否 | 拼在 `--extra` 里透传，例如 `--extra '{"ratio":"9:16"}'` |

---

## 3. 查询与轮询

```http
GET /api/v1/tasks/probe-no-such-task
HTTP 200
{"code":0,"msg":"任务不存在"}
```

假 id 回 `code: 0` + 中文说明 —— 说明路由在、且**不扣费**。真实任务返回里带
`status` / `progress` / `task_id`，可能套在 `data` 下，成片地址在 `video_url` / `url` /
`result.url` 之一。

轮询只走这一条：`GET /api/v1/tasks/<id>`。**每查一次都是 0 点**。
`POST /api/v1/apps/<app>/query` 那种应用层轮询每查一次就是一次的钱（历史烧掉 15,552 点），本包一次都不发。

---

## 4. 只读端点（全部 0 点）

| 端点 | 实测返回 |
|---|---|
| `GET /api/v1/models` | 316 条 = 221 条目录 + 95 条裸模型层 ID；`type_code=video` 47 个；kling 家族 14 条 |
| `GET /api/v1/apps` | 22 个应用；`seedance` 7 个接口、`wan` / `grok_video` / `full_video` 各 2 个 |
| `GET /api/v1/me/tasks?limit=2000&page=N` | 每页固定 20 条，共 1,398 条（70 页） |
| `GET /api/v1/tasks/<id>` | 真实任务给状态；假 id 回 `{"code":0,"msg":"任务不存在"}` |
| `GET /user/balance` | `{"available_points":…,"frozen":0,"rate":100}` |
| `GET /user/balance/logs?limit=N` | `{"count":N,"total":7885,"logs":[…]}`，每条含 `at/type/points/reference` |

应用层价格（同一条 `/pricing` 里，用来做对照）：

```
/api/v1/apps/seedance/submit   11000 点/次（固定）
/api/v1/apps/wan/submit          800 点/次
/api/v1/apps/grok_video/submit   300 点/次
```

所以同一个 Seedance 模型：应用层 11,000 点，模型层实测最低 145.73 点 = **75.5 倍**。

---

## 5. 单价怎么反推

`/api/v1/pricing` 里模型层没有专属规则，命中通配：

```json
```

真实单价只在 `GET /api/v1/me/tasks` 的 `actualPrice` 里。归集规则：

1. 取 `path` 不含 `/apps/` 且 `model` 非空的记录；
2. 按 `model` 分组，`actualPrice > 0` 的进样本；
3. 组内最小 / 最大 = 报价区间，条数 = n，标 `source=live`；
4. 没有样本 → 官方写死单价（只有 muse-video：11 点/秒）→ 本机基线 → 同路区间；
5. 任何一步都没有 → 按同路区间 + 保底 50 点，标 `source=baseline`。

本账号 1,398 条台账里，视频模型层只有 4 个有成交：

```
muse-video                            8 笔   44.0 / 55.0 / 55.0 / 55.0 / 55.0 / 55.0 / 55.0 / 260.0
sd/doubao-seedance-2-0-260128         5 笔   145.73 / 181.79 / 181.79 / 3000 / 3000
wan3.0-video                          8 笔   300 x 8（status: refunded, settled）
volcengine/doubao-seedance-2-5-260628 3 笔   762.30 / 3000 / 3045.71
```

16 笔合计就是本包对「没有样本的型号」用的同路区间 **44 - 3,045.71 点**。

---

## 6. 探针禁区（花钱买来的）

| 调用 | 后果 |
|---|---|
| `GET /api/v1/apps/<app>` | `sync:` 即时结算，按该应用 flat 单价扣，**不退**（dressing_diffusion 200 点 / nano_banana 72 点） |
| `POST /api/v1/apps/<app>/query` | 每查一次就是一次的钱 |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结，再校验失败 `refund` 全额退，**净 0 但钱包动过** |
| `POST /api/v1/videos {"model":"wan3.0-video"}` 缺 prompt | 实测先冻 300 点再退（2026-11-07） |

安全区（已逐条实测）：

```
GET  /api/v1/models  /apps  /pricing  /tasks/<id>  /me/tasks
GET  /user/balance   /user/balance/logs
POST /api/v1/videos {}                               400 不冻结
POST /api/v1/videos/generations {}                    400 不冻结
POST /api/v1/videos {"model": 任意裸 ID}               400 不冻结
POST /api/v1/videos/generations {"model": 任意型号}     400 不冻结
```

---

## 7. 本轮 0 点的三个证据

1. 每次 POST 探针后立刻 `GET /user/balance/logs?limit=3`，最新记录时间戳始终不变
   （`1794100561106`，2026-11-08 09:16:01）。
2. `doctor` 里余额前后对比：`999,997,393,470.26 -> 999,997,393,470.26`，差 0 点。
3. `doctor` 里流水净额：最近 100 条里视频线 2 笔、今日净 **0 点**。
