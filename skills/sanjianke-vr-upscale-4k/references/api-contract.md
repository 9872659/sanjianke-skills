# `upscale`（4K 旗舰版）· 完整接口契约

> 全部来自 **POST 实测** + 线上只读接口 + relay 服务端源码。
> 未确认的地方都标了「未确认」，不要凭前端文案猜。

---

## 1. 本档一览

| 项 | 值 |
|---|---|
| 档位 id | `upscale` |
| 中文名 | 4K 旗舰版 |
| 提交路径 | `/api/v1/video/upscale` |
| 售价 | **30 点/秒**（¥0.30/秒） |
| 上游 action | `pixverse/pixverse-upscale` |
| 单条上限 | **30 秒** |
| 输入规格 | 生成式；**无输入分辨率门槛** |
| 典型场景 | 展示型成片、社媒/广告，观感最强 |

**已下线，不要做**：`interp` / `/api/v1/video/viapi/interp`（`InterpolateVideoFrame`，25 点/秒）—— 线上档位说明原文写着「视频插帧 60fps（**已下线**）」。

---

## 2. 提交

```
POST /api/v1/video/upscale
Authorization: Bearer <你的 api.a7w.cn Key>
Content-Type: application/json
```

```json
{
  "videoUrl": "https://...mp4",     // 必填（也接受 video_url / url）
  "duration": 12,                   // 可选，但**强烈建议给**（见 §5）
  "callback_url": "https://..."     // 可选
}
```

- `upscale` 另有 `targetResolution`，**当前只支持 `"4k"`**
  （传 `1080p` → `400 invalid_resolution：不支持的 targetResolution: 1080p（当前仅支持 4k）`）。本包固定传 `4k`，不用你操心。

### 提交成功（HTTP 201）

```json
{
  "taskId": "task_e2c1f5245568838a888ec3cc",
  "status": "PENDING",
  "tool": "upscale",
  "duration": 2,
  "costIn": 60,
  "cost": 60,
  "balance": 999997920934.5667
}
```

**余额只在这个响应里给**，`GET /api/v1/me/tasks` 不返回余额。

### 提交失败（HTTP 4xx/5xx）

```json
{"error": {"code": "url_not_allowed", "message": "...", "type": "relay"}}
```

---

## 3. 查询

**路径形式**：

```
GET /api/v1/video/upscale/<taskId>
```

⚠️ **不要用 `GET /api/v1/tasks/<id>`** —— 那是网关自有层，返回
`{"code":0,"msg":"任务不存在","data":null}`，**查不到本档的任务**。

其它可用查询：

| 接口 | 说明 |
|---|---|
| `GET /api/v1/me/tasks` | 网关自有层任务列表，**包含本档**（带 `provider`/`path`/`status`），需 Key |
| `GET /api/v1/apps` | 网关自有 app 列表，需 Key（本包 `whoami` / `points` 用） |
| `GET /health` | relay 健康检查，**免鉴权**：`{"ok":true,"service":"relay-platform"}` |

### 查询成功（HTTP 200）

```json
{
  "taskId": "task_e2c1f5245568838a888ec3cc",
  "status": "processing",
  "videoUrl": "",
  "posterUrl": "",
  "transferStatus": "",
  "note": "正在转存到本站，请稍候…",
  "duration": 0,
  "cost": 0,
  "costIn": 0
}
```

`status` 取值：`processing` / `completed` / `failed` / `transfer_failed`。

- **`videoUrl` 为空是正常的**：成片要先「转存到本站/七牛」，转存完才有地址，
  `note` 会说明原因。轮询要容忍这一点。
- `transfer_failed` → 成片转存失败，**会自动退款**，让用户重新提交。

### 查询失败

```
404 {"error":{"code":"not_found","message":"Task not found.","type":"relay"}}
403 {"error":{"code":"forbidden","message":"Task belongs to another user.","type":"relay"}}
```

---

## 4. 素材入口判据

本档**不收素材白名单**，任意公网可下载地址都能提交。

⚠️ 但本档**不校验素材可达性**：喂一个 404 地址它照样返回 201 并冻结点数。
所以本包对每一档都**先探素材可达性再提交**，探不到就拒提交（要强行绕过必须显式 `--force`）。

也可以先用 `upload` 把本地文件传上来，拿返回的地址提交 —— 免费、且不必自己找图床。

### 实测（`POST /api/v1/video/upscale`）

| 输入地址 | 返回 | 判定 |
|---|---|---|
| `https://example.invalid/x.mp4` | **201 并冻结 60 点**（2 秒） | ⚠️ 上游不看可达性 |
| `https://oss.gpu.likeadmin.cn/.../x.mp4` | 201 并冻结 60 点 | ⚠️ 同上 |
| 可达的公网 mp4 | 201，正常建任务 | ✅ |

**这就是本包为什么要在提交前先探一次素材可达性。**

---

## 5. ★ 闸门顺序（决定「哪些失败是免费的」）

线上服务端的判定顺序：

```
1. empty_url        空 videoUrl          → 400 empty_url / pixverse_empty_url
2. （本档无素材入口判据）
3. 素材镜像/可达性                        → 502 oss_mirror_failed    （未扣费）
4. ffprobe 时长     不传 duration 时探测  → 探测不到则按 5 秒
5. 输入规格预检                           → 400 superres_input_too_large 等
6. charge           冻结扣费  ★★★ 扣费点在这里 ★★★
7. 提交上游                               → 502 viapi_error
```

**结论：参数错、白名单不过、规格不符，全部在扣费之前返回，天然免费。**
本包的 `--dry-run` 就是靠这一点做到「把能免费验的全验掉」。

### ⚠️ 本档必须记住的坑

**(a) 本档不校验素材可达性。** 实测三个地址**全部返回 201 并冻结点数**：

```
{"videoUrl":"https://example.invalid/x.mp4","duration":2}                → 201 costIn=60
{"videoUrl":"https://oss.gpu.likeadmin.cn/.../x.mp4","duration":2}       → 201 costIn=60
```

**(b) `duration` 不传就可能被按 5 秒收费。** 服务端逻辑：

```js
let duration = Math.ceil(Number(payload.duration) || 0);
if (!duration) duration = Math.ceil(await probeVideoDuration(url));
if (!(duration > 0)) duration = 5;      // ← 探测不到就按 5 秒
```

→ 所以**一定要显式传 `duration`**（本包本地 ffprobe 先取；取不到就要求你显式给）。

---

## 6. 错误码对照

| code | HTTP | 含义与处置 |
|---|---|---|
| `empty_url` / `pixverse_empty_url` | 400 | 没给 `videoUrl` |
| `url_not_allowed` | 400 | 本档只收本网关素材：先 `upload`，再用返回的地址 |
| `invalid_resolution` | 400 | `upscale` 只支持 `4k` |
| `superres_input_too_large` | 400 | 超分输入需 <1920×1080 |
| `interp_input_too_large` | 400 | 插帧仅支持 ≤720P（该档已下线） |
| `oss_mirror_failed` | 502 | 素材转存失败（**未扣费**） |
| `insufficient_points` | 402 | 点数不足 |
| `tool_not_launched` | 501 | 该档未开放 |
| `unknown_tool` | 404 | 档位 id 不认识 |
| `viapi_not_configured` | 400 | 平台侧凭据未配置（服务端问题） |
| `unauthorized` | 401 | Key 无效/缺失 |
| `not_found` | 404 | 任务不存在 |
| `forbidden` | 403 | 任务属于别的用户 |
| `transfer_failed`（status，非 code） | 200 | 成片转存失败，**已退款**，重新提交 |

---

## 7. 上传入口

```
POST /api/v1/upload      multipart/form-data，字段名 file
```

- **必须带 Key**：匿名调用返回 `401 {"error":{"code":"unauthorized","message":"Missing or invalid relay API key.","type":"relay"}}`。
- 空 body 带 Key → `200 {"code":0,"msg":"请使用 file 字段提交一个文件","data":null}`。
- 真上传（带 Key）→ `200`：

```json
{"code":1,"msg":"success","data":{
  "url":"https://oss.gpu.likeadmin.cn/openapi/18/20261001/<32hex>.mp4",
  "name":"a7w_probe_1s.mp4","size":32,"mime_type":"video/mp4","type":"video"}}
```

**返回域名稳定是 `oss.gpu.likeadmin.cn`**（取样一致）。本档不收白名单，所以这个地址**直接可用**。

其它上传入口全部 404（返回前端 Nuxt 页面）：`/api/v1/files/upload`、`/api/v1/upload/file`、`/api/v1/file/upload`、`/api/v1/uploads`、`/api/v1/storage/upload`。

---

## 8. 免费只读接口（本包 `info` / `doctor` 用）

```
GET /api/v1/video/viapi/tools
{"provider":"viapi","configured":true,
 "tools":[{"tool":"upscale","action":"pixverse/pixverse-upscale","perSecond":30,
           "costPerSecond":...,"note":"展示型成片、社媒/广告，观感最强"}, ...]}
```

⚠️ **这个接口的状态变了**（同一天实测）：

| 时刻 | 无 Key | 带有效 Key |
|---|---|---|
| 早先 | **200**（1294 B，完整档位表） | — |
| 后来（复测 3 次 + 间隔 60 秒） | **401** `Missing or invalid relay API key.` | **404**（前端 Nuxt 页面） |

`POST` 同路径会掉进单档处理器：`404 {"error":{"code":"unknown_tool","message":"未知的视频能力：tools"}}`。
`GET .../tools/x` 仍正常回 `404 not_found`（查询路由还在）。

→ 说明 relay 的 `tools` **GET 路由掉了**。本包因此**优雅降级**到内置档位表（单价取自 `api.a7w.cn` 在架能力），并如实打印「在线源当前不可达」。**价格与规格以线上为准。****如果这条恢复了，把 `fetch_tiers()` 的注释更新一下即可，代码无需改。**

对照（同一时刻全部正常）：`/health` 200、`/api/v1/apps` 200、`/api/v1/me/tasks` 200、`POST /api/v1/video/upscale` 400 `url_not_allowed`（提交链路与闸门都正常）。

---

## 9. 未确认的事

1. 本档的**线上真实单价与上限**，除 `tools` 接口那一次读取外，未在线上直接核对过（配置在服务器上，只读查看也需要授权）。**价格与规格以线上为准。**
