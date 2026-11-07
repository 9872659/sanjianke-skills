# 接口契约（2026-11-07 实测原文）

网关：`https://api.a7w.cn`，业务前缀 `/api/v1`。
鉴权：`Authorization: Bearer <API Key>`。
点数口径：**1 元 = 100 点**。

本文所有「实测」都来自**空 body 探针**或**只读 GET**：前者停在上游参数校验层，
后者是纯读接口 —— 全程 0 条任务、0 点冻结、0 点扣费。

---

## 1. 提交（异步两步的第一步）

每档一条路径，**restore 是扁平的，其余 6 档是 viapi 的**：

| 工序 | 方法 | 路径 | 空 body 实测 |
|---|---|---|---|
| `colorize` | POST | `/api/v1/video/viapi/colorize` | `400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}` |
| `superres` | POST | `/api/v1/video/viapi/superres` | 同上 `400 empty_url` |
| `enhance` | POST | `/api/v1/video/viapi/enhance` | 同上 `400 empty_url` |
| `superres2k` | POST | `/api/v1/video/viapi/superres2k` | 同上 `400 empty_url` |
| `portrait` | POST | `/api/v1/video/viapi/portrait` | 同上 `400 empty_url` |
| `superres4k` | POST | `/api/v1/video/viapi/superres4k` | 同上 `400 empty_url` |
| `restore` | POST | `/api/v1/video/restore` | `400 {"error":{"code":"pixverse_empty_url","message":"videoUrl 不能为空","type":"relay"}}` |

两条反例（打错了会白等）：

```
POST /api/v1/video/viapi/restore   → 404 {"error":{"code":"unknown_tool",
                                          "message":"未知的视频工具名: restore","type":"relay"}}
POST /api/v1/video/superres        → 404（扁平路径没有超分，只有 restore 有扁平路径）
```

### 请求体

必填只有 `videoUrl`（平台托管地址，见第 3 节）。

```json
{
  "videoUrl": "https://oss.gpu.likeadmin.cn/openapi/18/20261107/xxxx.mp4",
  "duration": 60
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `videoUrl` | 是 | 必须是白名单域名，否则 400 `url_not_allowed` |
| `duration` | 否 | 秒。文档缺省 5 秒，用于**预冻结**；本包按实测时长显式传 |

### 成功响应

```json
{"code":1,"msg":"success","data":{"taskId":"task_xxx","status":"pending",
 "duration":60,"cost":540,"balance":999997393482.26}}
```

`data` 里取 `taskId`（也认 `task_id` / `id`）。`cost` 是这一次的预冻结点数。

---

## 2. 查询（免费，异步两步的第二步）

| 工序 | 方法 | 路径 | 假 taskId 实测 |
|---|---|---|---|
| viapi 6 档 | GET | `/api/v1/video/viapi/result/<taskId>` | `404 {"error":{"code":"not_found","message":"Task not found.","type":"relay"}}` |
| `restore` | GET | `/api/v1/video/restore/<taskId>` | 同上 `404 not_found` |

两个路由**同源**，返回：

```json
{"status":"completed","tool":"superres","videoUrl":"https://…/result.mp4",
 "cost":540,"refund":0,"message":"","error":null,"result":{...}}
```

`status` 终态：`completed / success / succeeded / done` 为成功，
`failed / error / cancelled / canceled / timeout / expired` 为失败（失败全额退回 `refund`）。

### 通用任务路由查不到这一类任务

```
GET /api/v1/tasks/<taskId>   → 200 {"code":0,"msg":"任务不存在","data":null}
```

它服务模型与应用任务，**视频后处理任务不在里面** —— 所以 `status` 子命令走的是上面
`result` 路由，而不是 `/tasks`。

### 应用层 `/query` 是计费读

`POST /api/v1/apps/<app>/query` 每调一次按该应用的 flat 单价结算一次。
历史流水里 `nano_banana/query` 记过 **216 笔、每笔 −72 点、合计 −15,552 点**。
本包所有等待都只打 `result` 路由。

---

## 3. 上传（免费，拿白名单地址）

```
POST /api/v1/upload
Content-Type: multipart/form-data; boundary=…
字段名：file
```

实测（`_devr_tiny.mp4`，4,858 字节）：

```json
{"code":1,"msg":"success","data":{
  "url":"https://oss.gpu.likeadmin.cn/openapi/18/20261107/f1d911c95d13f04ba303dc87ea5ec883.mp4",
  "path":"openapi/18/20261107/f1d911c95d13f04ba303dc87ea5ec883.mp4",
  "name":"_devr_tiny.mp4","size":4858,"mime_type":"video/mp4","type":"video"}}
```

不带 `file` 字段时是 **HTTP 200 + `code:0`**（不是 4xx）：

```json
{"code":0,"msg":"请使用 file 字段提交一个文件","data":null}
```

### `videoUrl` 的白名单（400 时报错原文）

```
videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）
```

| 域名 | 路径要求 | 归属 |
|---|---|---|
| `vr.a7w.cn` / `*.a7w.cn` | 任意 | 本站 |
| `cdn2.jiujiushuyuan.cn` | 必须以 `/vr/` 开头 | 本站七牛 |
| `oss.gpu.likeadmin.cn` | 必须以 `/openapi/` 开头 | 上传接口 |

`https://example.invalid/x.mp4` 实测 400 `url_not_allowed`；
`oss.gpu.likeadmin.cn/openapi/…`（upload 返回的）实测可以建任务。

---

## 4. 价目（`GET /api/v1/pricing` 实测，单位：点/秒）

```json
"/api/v1/video/viapi/colorize"   {"mode":"per_second","perSecond":9, "note":"视频校色（VIAPI AdjustVideoColor）：9 点/秒"}
"/api/v1/video/viapi/superres"   {"mode":"per_second","perSecond":9, "note":"标准超分 1080P"}
"/api/v1/video/viapi/enhance"    {"mode":"per_second","perSecond":15,"note":"画质综合增强（VIAPI EnhanceVideoQuality）：15 点/秒"}
"/api/v1/video/viapi/superres2k" {"mode":"per_second","perSecond":15,"note":"高清超分 2K/60帧"}
"/api/v1/video/viapi/portrait"   {"mode":"per_second","perSecond":18,"note":"人像增强（公测免费）"}
"/api/v1/video/viapi/superres4k" {"mode":"per_second","perSecond":20,"note":"超清 4K"}
"/api/v1/video/restore"          {"mode":"per_second","perSecond":36,"note":"视频修复：固定 36 点/秒（4K超清的 2 倍）"}
```

要点：

- `restore` 的价格键是**扁平路径** `/api/v1/video/restore`，没有 `viapi` 版本；
- `portrait` 的 note 写「公测免费」，按秒规则仍是 18 —— 以实际账单为准；
- `restore` 的 note 写「固定 36 点/秒（4K超清的 2 倍）」—— 36 点/秒本身就是 4K 超清档的两倍价；
- `superres4k` 的 note 只有「超清 4K」四个字，没有额外倍率说明。

---

## 5. 余额与流水（免费）

```
GET /api/v1/user/balance        → {"available_points":…, "frozen":…, "rate":100}
GET /user/balance/logs?limit=5  → {"total":7901,"logs":[{"at":1794065607768,"type":"charge",
                                   "points":-60,"balanceAfter":…,"taskId":""}]}
```

**流水要打 `/user/balance/logs`，路径里没有 `/api/v1`。**
带上 `/api/v1` 会命中余额路由并原样返回余额对象（`{"available_points":…}`），
永远看不到 `logs` 字段 —— 这一条是实测踩到的。

---

## 6. 状态文件契约（本包自己的）

`oldfilm-work/state.json`：

```json
{
  "version": 1, "preset": "standard", "seconds": 60,
  "input": "老片.mp4", "videoUrl": null,
  "createdAt": "2026-11-07T23:40:00", "updatedAt": "2026-11-07T23:52:10",
  "estimatedPoints": 1980,
  "steps": [
    {"i": 1, "tier": "superres", "status": "completed", "taskId": "task_xxx",
     "pointsPerSecond": 9, "points": 540, "finalStatus": "completed",
     "resultUrl": "https://…/a.mp4", "feedUrl": "https://…/a.mp4",
     "file": "oldfilm-work/01-superres.mp4", "bytes": 1234567},
    {"i": 2, "tier": "colorize", "status": "pending", "pointsPerSecond": 9, "points": 540}
  ]
}
```

`status` 取值：`pending` → `submitted` → `completed` / `failed`。
`resume` 的判据只看这一列：`completed` 跳过；有 `taskId` 只查；都没才提交。
