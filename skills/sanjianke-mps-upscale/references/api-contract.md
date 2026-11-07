# 接口契约（文档原文 + 实测）

> 权威来源：网关文档 `https://api.a7w.cn/docs.html#/docs/tencent-superres`（腾讯云超分 · 总览）
> 同系列：`/docs/tencent-superres-submit`（提交任务）、`/docs/tencent-superres-query`（查询任务）、
> `/docs/video-superres-price`（视频超分价格与调用方式）
> 本文件的每条结论都经过真机验证（2026-11-07），**验证方式全部零扣费**，见第十节。

---

## 一、接入信息

| 项目 | 值 |
|---|---|
| 接口根地址 | `https://api.a7w.cn/api/v1` |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 调用方式 | **异步任务**：提交拿 `task_id` → 轮询查询 |
| 凭据 | 平台侧统一配置腾讯云 SecretId / SecretKey / COS Bucket / Region，调用方只用 `api.a7w.cn` 的 Key |

三档按**路径**区分：

| 档位 | 提交 | 查询 |
|---|---|---|
| 1080P | `POST /api/v1/video/tencent1080` | `GET /api/v1/video/tencent1080/{task_id}` |
| 2K | `POST /api/v1/video/tencent2k` | `GET /api/v1/video/tencent2k/{task_id}` |
| 4K | `POST /api/v1/video/tencent4k` | `GET /api/v1/video/tencent4k/{task_id}` |

能力：基于**腾讯云媒体处理（MPS）音视频增强（超分）**，把低清视频提升至 1080P / 2K / 4K。

---

## 二、提交任务

```
POST https://api.a7w.cn/api/v1/video/tencent4k
Content-Type: application/json
Authorization: Bearer <key>

{"video_url": "https://example.com/low.mp4", "duration": 10}
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `video_url` | **是** | 可公网访问的视频地址（也可写 `videoUrl` / `url`，三个名字都认） |
| `duration` | **实际必传** | 视频秒数。文档写作「否：不传则平台用 ffprobe 自动探测，探测失败会拒绝建单避免误扣」，实测探测失败即拒单，**所以按必传处理** |
| `callback_url` | 否 | 任务完成回调地址 |

响应（文档原文）：

```json
{ "task_id": "task_xxx", "provider": "tencent-mps", "resolution": "4K",
  "seconds": 10, "points": 80, "status": "processing" }
```

---

## 三、查询任务

```
GET https://api.a7w.cn/api/v1/video/tencent4k/{task_id}
Authorization: Bearer <key>
```

三种状态（文档原文）：

```json
{ "status": "processing", "mps_status": "PROCESSING" }
{ "status": "success", "video_url": "https://<cos>/superres/xxx.mp4", "points": 80 }
{ "status": "failed", "message": "...", "refunded": 80 }
```

**失败自动全额退款**。成品文件保留 **24 小时**，请及时下载。

### 实测：文档这条 GET 路由当前打不通

| 请求 | 实测返回 |
|---|---|
| `GET /api/v1/video/tencent1080/999999999` | **404**（Nuxt SPA 的 HTML 兜底，不是 JSON） |
| `GET /api/v1/video/tencent2k/999999999` | 404（同上） |
| `GET /api/v1/video/tencent4k/999999999` | 404（同上） |
| `GET /api/v1/video/tencent1080/task_nonexistent_xyz` | 404（同上） |
| `GET /api/v1/video/tencent1080/999999999/`（尾斜杠） | 404（同上） |
| `GET /api/v1/video/tencent1080/task/999999999` | 404（同上） |
| `GET /api/v1/video/tencent1080/status/999999999` | 404（同上） |
| `GET /api/v1/video/tencent1080?task_id=999999999` | 404（同上） |
| `POST /api/v1/video/tencent1080/query` | 404（同上） |

判据：同一个网关里，**存在的 GET 路由返回 JSON**（例如 `/user/balance` → 200 JSON），
**不存在的返回 SPA 的 HTML 404**。所以上表这批路径当前都没注册。

### 实测：能通的两条查询路由

| 请求 | 实测返回 |
|---|---|
| `GET /api/v1/videos/{task_id}` | **200 + 统一任务 JSON**：`{"id","model","object","status","progress","seconds","size","url","video_url","created_at","completed_at","expires_at"}` |
| `GET /api/v1/videos/999999999` | **400** `{"code":"task_not_exist","message":"task_not_exist","data":null}` |
| `GET /api/v1/me/tasks?per_page=50` | **200**：`{"tasks":[…],"total","page","size","sumPoints","sumRefund","sumYuan"}` |

`/api/v1/me/tasks` 每条任务带 `taskId` / `model` / `path` / `status` / `resultUrl` /
`chargedPoints` / `refundedPoints` / `netPoints`，**是查历史与对账最稳的一条**。

所以本包 `status` 做三级回退：文档路由 → `/videos/{task_id}` → `/me/tasks` 台账匹配。

---

## 四、计费

| 档位 | 单价 | 单笔保底 | 10 秒 | 10 分钟 | 30 分钟 |
|---|---|---|---|---|---|
| 1080P | **2 点/秒（¥0.02）** | 10 点 | 20 点 | 1200 点（¥12） | 3600 点（¥36） |
| 2K | **4 点/秒（¥0.04）** | 10 点 | 40 点 | 2400 点（¥24） | 7200 点（¥72） |
| 4K | **8 点/秒（¥0.08）** | 10 点 | 80 点 | 4800 点（¥48） | 14400 点（¥144） |

- 计费依据是**输入视频时长**（不是输出）
- 单笔**保底 10 点**：低于 10 点的部分按 10 点收
- 任务**失败不扣费**（已冻结的全额退回）
- **查询接口一律免费**
- 1 元 = 100 点

### 与阿里 VIAPI 的对比（平台价目表原文）

| 线路 | 接口 | 单价 | 保底 |
|---|---|---|---|
| 腾讯云超分 1080P | `POST /api/v1/video/tencent1080` | **2 点/秒** | 10 点 |
| 腾讯云超分 2K | `POST /api/v1/video/tencent2k` | **4 点/秒** | 10 点 |
| 腾讯云超分 4K | `POST /api/v1/video/tencent4k` | **8 点/秒** | 10 点 |
| VIAPI 标准 1080P | `POST /api/v1/video/viapi/superres` | 9 点/秒 | — |
| VIAPI 高清 2K / 60 帧 | `POST /api/v1/video/viapi/superres2k` | 15 点/秒 | — |
| VIAPI 超清 4K | `POST /api/v1/video/viapi/superres4k` | 20 点/秒 | — |
| 视频超分（flashvsr） | `POST /api/v1/apps/flashvsr/submit` | 10 点/秒 | 20 点 |

倍率：1080P **4.5×**、2K **3.75×**、4K **2.5×**（都是腾讯线更便宜）。

---

## 五、实测：参数校验（原始返回）

全部用「必然被参数校验拦下」的 body，**一次真实任务都没建**：

| 请求体 | 状态码 | 原始返回 |
|---|---|---|
| `{}` | **400** | `{"error":{"code":"video_url_required","message":"请提供 video_url（可公网访问的视频地址）","type":"relay"}}` |
| `{"videoUrl":"https://example.invalid/x.mp4"}` | **400** | `{"error":{"code":"duration_unknown","message":"无法探测视频时长，请显式传 duration（秒）","type":"relay"}}` |
| `{"video_url":"https://example.invalid/x.mp4"}` | **400** | 同上 `duration_unknown` |
| `{"url":"https://example.invalid/x.mp4"}` | **400** | 同上 `duration_unknown` |
| `{"videoUrl":"…","duration":"abc"}` | **400** | 同上 `duration_unknown`（非数字按「没传」处理） |
| `{"videoUrl":"…","duration":null / [] / {}}` | **400** | 同上 `duration_unknown` |
| `{"videoUrl":"…","durations":"abc"}` | **400** | 同上 `duration_unknown`（键名拼错 = 没传） |
| `{"videoUrl":"…","duration":"12.5"}` | **502** | `{"error":{"code":"FailedOperation.InvalidMpsUser","message":"腾讯云超分提交失败：[FailedOperation.InvalidMpsUser] invalid mps user","type":"relay"}}` |

**结论**：

1. `video_url` / `videoUrl` / `url` **三个名字都认**
2. `duration` **接受小数**（字符串 `"12.5"` 被解析成 12.5 秒并真的送到了上游）
3. `duration` 传非数字，等价于没传 → `duration_unknown`
4. 上游凭据异常时报 **502**，且**不会建单**

---

## 六、实测：`tsc_*` 系列的路由

价目表里有 `tsc_teshd`（短剧增强）、`tsc_shortplay` 等 11 个 `tsc_*` 档位，路由复验：

| 请求 | 实测返回 |
|---|---|
| `POST /api/v1/video/tsc_teshd` | **404**（SPA HTML 兜底） |
| `POST /api/v1/video/tsc_shortplay` | 404 |
| `POST /api/v1/video/tsc_quality` | 404 |
| `POST /api/v1/video/tsc_uhd` | 404 |
| `GET /api/v1/video/tsc_teshd/999999999` | 404 |
| `POST /api/v1/video/tencent/tsc_teshd` | 404 |
| `POST /api/v1/video/tsc/teshd` | 404 |
| `POST /api/v1/video/tencent/teshd` | 404 |
| `POST /api/v1/video/teshd` | 404 |
| `POST /api/v1/apps/tsc_teshd/submit` | 200 `{"code":0,"msg":"应用或 API 不可用或未配置价格","data":null}` |
| `POST /api/v1/apps/tencent_mps/submit` | 200 同上 |
| `POST /api/v1/apps/media_services_33/teshd` | 200 同上 |
| `POST /api/v1/apps/media_services_33/submit` | 200 同上 |

注意最后四条不是「路由存在」：`/api/v1/apps/{任意下划线代号}/submit` 都会返回
`{"code":0,"msg":"应用或 API 不可用或未配置价格"}`（拿 `nonexistent_xyz_123` 也得到同一句），
这是**应用层的兜底话术**，含义是该应用 / 接口不在架。真在架的应用会返回 `task_id`。

**价目有、路由没上。** 本包只做 `tencent1080` / `tencent2k` / `tencent4k` 三档。

---

## 七、错误码

| 场景 | 状态码 | `code` | 处理 |
|---|---|---|---|
| 缺视频地址 | 400 | `video_url_required` | 补 `--url`（要 `http(s)://` 公网地址） |
| 缺 / 非数字 duration | 400 | `duration_unknown` | 补 `--duration 秒数` |
| 上游凭据异常 | 502 | `FailedOperation.InvalidMpsUser` | 不建单、不扣点；平台侧处理 |
| 查询不存在的任务 | 400 | `task_not_exist` | 核对 `task_id` 与 `--tier` |
| 路由没注册 | 404 | （HTML 兜底） | 本条路径不存在 |

---

## 八、上传前的准备

- 视频要**公网可访问**（腾讯云 MPS 侧要能拉到），本地文件请先传到对象存储 / 图床
- 链接有效期要覆盖整个处理时间（10 分钟 4K 片子建议链接至少 2 小时有效）
- `duration` 用 `ffprobe` 先量好，别手估 —— 少填会按比例少算，多填会多扣

```bash
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 low.mp4
```

---

## 九、与 WEB 版的关系

- 网页版批量超分：[vr.a7w.cn](https://vr.a7w.cn/)（拖进去就能跑，最高 4K）
- 本包是**同一条腾讯云 MPS 产线**的命令行入口，按秒计费口径与网页版一致

---

## 十、这些结论怎么做到零扣费

| 手段 | 为什么免费 |
|---|---|
| `GET /user/balance`、`GET /api/v1/videos/{id}`、`GET /api/v1/me/tasks` | 只读接口，查询不扣费 |
| `POST /api/v1/video/{tier}` 只发 `{}` | 命中 `video_url_required`，**在计费之前**被拦 |
| `POST` 只发 `video_url` 不发 `duration` | 命中 `duration_unknown`，**在计费之前**被拦 |
| `POST` 发非数字 `duration` | 等价于没传，同样被拦 |

唯一一次越过校验的是 `duration: "12.5"`（小数被接受），它走到了上游提交并被
`InvalidMpsUser` 拒绝 —— **没有返回 `task_id`，没有冻结点数**，所以仍是 0 点。
