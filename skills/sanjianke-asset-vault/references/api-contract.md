# 接口契约（文档原文 + 实测返回）

> 权威文档：`https://api.a7w.cn/assets/docdata.json` 里的节点「公共文件临时上传」「Seedance 2.0 · 创建素材资产组合 / 上传素材 / 删除素材」「Wan 视频生成 - 创建视频任务」「水印消除 · 去除水印」「Happy Horse · 创建任务」。
> 本文每条结论都在 2026-11-08 真机跑过：**只读 GET + 一次免费上传 + 一次缺参上传探针**，没有建过任何生成任务。

---

## 一、接入信息

| 项目 | 值 |
|---|---|
| 接口根地址 | `https://api.a7w.cn/api/v1` |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 本包用到的写接口 | `POST /api/v1/upload`（免费）；`POST /api/v1/apps/<app>/<create|submit|remove>`（计费，只在 `bind` / `release`） |
| 本包用到的读接口 | `GET /pricing` · `GET /apps` · `GET /me/tasks` · `GET /tasks/<id>` · `GET /user/balance` · `GET /user/balance/logs` |
| 价格源 | `GET /api/v1/pricing`（免费，115 条规则） |
| 1 元 | 100 点 |

---

## 二、上传（`POST /api/v1/upload`，免费）

### 2.1 文档原文要点

- 只用临时中转；成功响应里的 `url` **最长有效期 24 小时**，平台可因存储回收、容量治理或安全策略提前失效。
- `multipart/form-data`，单个字段名 **`file`**；默认单文件最大 **512 MB**。
- 「接口不收取模型调用费用」。

### 2.2 价目表里的规则（`GET /api/v1/pricing`，逐字）

```json
"/api/v1/upload": {
  "note": "★上传不计费（2026-10-04 站主批准）。上传是生成的前置动作、不是可计费服务。此前本路径【无专属规则】⇒ 命中通配 flat 50 ⇒ 走 server.js 的 fallback 兜底 ⇒ 每次上传扣 50×1.3=65 点，且页面『预计消耗』完全不披露 ⇒ 违反『预计消耗=实收』。计费引擎对 cost:0 有显式语义：server.js isFreePath 里 ruleCost === 0 …"
}
```

### 2.3 实测：上传一个 252 B 的假 mp4

```
POST https://api.a7w.cn/api/v1/upload
Content-Type: multipart/form-data; boundary=----sanjianke<hex>
Authorization: Bearer <key>

file: probe.mp4 (252 B)
```

返回（HTTP 200，字段取自本包台账，2026-11-08 12:02:39）：

```json
{"code":1,"msg":"success","data":{
  "url":"https://oss.gpu.likeadmin.cn/openapi/18/20261108/08ec12ff6d07ae8bfbe7a790c90ca50a.mp4",
  "path":"openapi/18/20261108/08ec12ff6d07ae8bfbe7a790c90ca50a.mp4",
  "name":"probe.mp4","size":252,"mime_type":"video/mp4","type":"video"}}
```

| 字段 | 说明 |
|---|---|
| `url` | 临时访问地址，最长 24 小时；本包台账按 `at + 24h` 记 `expires` |
| `path` | 临时存储相对路径，仅供排查 |
| `name` | 原始文件名 |
| `size` | 字节数 |
| `mime_type` | 平台识别到的 MIME |
| `type` | `image` / `video` / `file` |

> 同网关的 `sanjianke-video-lab` 2026-11-07 用 256 B 假 mp4 实测，`code/msg` 与本条一致；本包这次拿到的是 `video/mp4`（同一条上传接口，MIME 由文件内容推断）。

### 2.4 缺 file 的探针（`doctor` 每次跑）

```
POST /api/v1/upload        （multipart 里不放 file 字段）
-> HTTP 200 {"code":0,"msg":"请使用 file 字段提交一个文件","data":null}
```

**HTTP 状态码也是 200，成败看 `code`（1 成功 / 0 失败）**，这是上传线与应用线（HTTP 400 + `{"error":{...}}`）两套错误风格并存的典型。

### 2.5 `GET /api/v1/upload` 不存在

```
GET /api/v1/upload -> HTTP 404 <!DOCTYPE html> …（前端 SPA 兜底页）
```

上传只有 POST 一条路。

---

## 三、价目表（`GET /api/v1/pricing`）

### 3.1 结构

```json
 "site":"https://api.a7w.cn",
 "pricing":{ "…115 条…" }}
```

### 3.2 11 个应用的 22 条 create/remove（逐条实测）

| 应用 | create 规则 | remove 规则 |
|---|---|---|
| `dressing_diffusion` | flat, cost **200** | flat, cost 0 |
| `grok_video` | flat, cost **300** | flat, cost 0 |
| `happy_horse` | flat, cost **650** | flat, cost 0 |
| `image_human` | per_second, `modelRates` fast 10 / standard 15 / 2k 30 / 4k 60, `defaultModel=fast` | flat, cost 0 |
| `nano_banana` | flat, cost **72**（note：带 `views[]` 时 25 点 × 视角数） | flat, cost 0 |
| `seedance` | flat, cost **11000** | flat, cost 0 |
| `seedsvc` | flat, cost **220** | flat, cost 0 |
| `smart_clip` | flat, cost **45** | flat, cost 0 |

原文示例（两条最能说明问题的）：

```json
  "note":"去水印/分享链解析：固定 100 点/次"}

```

### 3.3 全局通配规则（所有没定价的接口都掉进来）

```json
```

---

## 四、应用目录（`GET /api/v1/apps`）

### 4.1 结构

```json
{"code":1,"msg":"success","data":[{ "id":19,"name":"人物替换","code":"person_replacement",
  "description":"…","driver_code":"elastic_gpu","billing_mode":1,
  "category_code":"other","category_name":"其他",
  "apis":[{"id":52,"code":"submit","name":"提交任务","method":"POST","call_type":2,
           "category_code":"video","max_reference_images":1,…}]}]}
```

- `data` 共 **22 个应用**。
- `apis[]` 里 `code` 是接口名，`method` 是方法，`call_type`（1 同步 / 2 异步）。
- **目录里没有的接口，价目表里可能有规则** —— 这是本包第三条干货的来源。

### 4.2 11 个目标应用的入口登记（2026-11-08 实测）

| 应用 | 目录里登记的 apis | 本包默认入口 |
|---|---|---|
| `dressing_diffusion` | submit, query | submit |
| `grok_video` | submit, query | submit |
| `happy_horse` | submit, **create**, query | create |
| `image_human` | submit, query | submit |
| `lipsync` | submit, query | submit |
| `nano_banana` | submit, query | submit |
| `seedance` | createGroup, createAsset, getAsset, updateAsset, deleteAsset, query, **create** | create |
| `seedsvc` | submit, query | submit |
| `smart_clip` | template, template_detail, realman_broadcast, broadcast_mixcut, news_mixcut | broadcast_mixcut |
| `wan` | query, **create** | create |
| `watermark_removal` | **remove**, xhs_note_detail, xhs_user_note_list, douyin_user_video_list, xhs_user_detail, douyin_video_detail, douyin_search_video, xhs_search_note | remove |

`watermark_removal` 没有 create / submit：它的主业务就是 `/remove`（去水印），所以本包把它的默认入口设成 `remove`，价格固定 100 点/次。

---

## 五、我的任务（`GET /api/v1/me/tasks`，免费）

### 5.1 结构

```json
{"page":1,"size":20,"total":1398,
 "sumPoints":…,"sumRefund":…,"sumYuan":…,
 "tasks":[{"taskId":"task_…","model":"voice_tts","type":"应用",
  "path":"/api/v1/apps/voice_tts/tts_async","status":"refunded",
  "reservePrice":150,"actualPrice":150,"refund":300,
  "frozenPoints":150,"chargedPoints":150,"refundedPoints":150,"netPoints":0,
  "rateNote":"官方价 × 2.00（≈ +100%）","at":1794058610213,
  "elapsedMs":…,"error":"","failReason":"","resultUrl":"","resultUrls":[],
  "posterUrl":"","transferStatus":"","provider":"","tool":"",
  "tokensIn":0,"tokensOut":0,"tokens":"0/0","moduleCount":0,
  "keyFp":"…","charges":[…]}]}
```

- 每页固定 **20 条**；`size` / `per_page` 无效；`limit` 是「统计最近 N 条」的窗口（本包统一带 `limit=2000`）。
- `actualPrice` 是预扣 / 标价，`netPoints` 是真扣，`refundedPoints` 是已退。
- 翻完 1,398 条实测需要 69 页（第 69 页偶发 502，重试即可）。

### 5.2 实测成交价（本轮全量扫描 1,360 条）

| 路径 | 笔数 | actualPrice | 备注 |
|---|---|---|---|
| `/api/v1/apps/nano_banana/submit` | 165 | 72 | 与标价一致 |
| `/api/v1/apps/wan/create` | 124 | 120 / 480 / 720 / 960 / 1,200 / 1,440 / 2,400，另有 108,000 / 162,000 / 270,000 | 动态 ×3，价格随输入秒数与分辨率走 |
| `/api/v1/apps/smart_clip/realman_broadcast` | 163 | 0 - 1,476 | 按秒计价，最低 0 |
| `/api/v1/apps/image_human/submit` | 14 | 90 - 12,748.8 | 按输入秒 × 档位 |
| `/api/v1/apps/seedance/create` | 7 | 388 / 405.94 / 10,000 / 11,000 | 固定标价 11,000 也有 388 的实测 |
| `/api/v1/apps/grok_video/submit` | 7 | 193.48 - 300 | |
| `/api/v1/apps/happy_horse/submit` | 5 | 520 - 650 | |
| `/api/v1/apps/lipsync/submit` | 2 | 14.25 / 14.97 | |
| `/api/v1/apps/dressing_diffusion/submit` | 1 | 200 | |

`cost --live` 读的就是这张表（`source=live`）；没有历史成交的路径退回价目表（`source=pricing`）或内置基线（`source=baseline`）。

---

## 六、任务查询（`GET /api/v1/tasks/<id>`，免费）

假 id 实测：

```
GET /api/v1/tasks/probe-no-such-task
-> HTTP 200 {"code":0,"msg":"任务不存在","data":null}
```

`code=0` 是「任务不存在」，不是「接口不存在」。`doctor` 用它证明查询路由在，且不扣费。
真正的任务状态：`status` 取 `pending` / `processing` / `completed` / `failed` / `cancelled`，结果在 `result`，用量在 `usage.points_cost`。

---

## 七、余额与流水（免费）

### 7.1 `GET /user/balance`

```json
{"available_points": 999997393055.9279, "points": 999997393055.9279,
 "frozen": 0, "member_points": 0, "yuan": 9999973930.56, "rate": 100,
 "currency": "points",
 "note": "本平台按用户/Key 隔离统计，非上游租户级数字"}
```

### 7.2 `GET /user/balance/logs?limit=1000`

```json
{"balanceMoving": -176274.11, "consumePoints": 74567.18, "count": 1000,
 "currency": "points", "inPoints": 276742.8095, "netPoints": -405740.1157,
 "outPoints": 682482.9252, "rate": 100, "total": 8011,
 "logs": [{"at": 1794109457268, "type": "refund", "typeName": "退款", "kind": "in",
           "balanceMoving": true, "isSettle": false, "points": 60, "amount": 60,
           "balanceAfter": 999997393378.728, "path": "", "taskId": "",
           "reference": "refund:sync_error:/api/v1/chat/completions",
           "orderId": "", "model": "", "provider": ""}]}
```

- `limit` 上限 1000（传更大也只回 1000）。
- 流水页的 `netPoints` 是流水口径（预扣 + 退款来回都算），`balanceMoving` 才是真净 —— 这条口径见 `sanjianke-billing`。
- 本包用 `reference` 字段判断「这笔是不是本包端点产生的」：`/api/v1/upload` 与 `/api/v1/apps/<app>/{create,submit,remove}`。

---

## 八、种子素材三件套（seedance）

### 8.1 创建素材分组 `POST /api/v1/apps/seedance/createGroup`

同步。字段：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `Name` | string | **是** | 分组名，≤64 字符 |
| `GroupType` | string | 否 | `AIGC` 表示虚拟人像分组 |
| `Description` | string | 否 | ≤300 字符 |
| `ProjectName` | string | 否 | 默认 `default` |

### 8.2 上传素材 `POST /api/v1/apps/seedance/createAsset`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `URL` | string | **是** | 素材公网可访问 URL，由上游拉取入库 |
| `Name` | string | 否 | ≤64 字符 |
| `GroupId` | string | **是** | 来自 createGroup 返回的 `Result.Id` |
| `AssetType` | string | **是** | `Image` / `Video` / `Audio` |
| `ProjectName` | string | 否 | 默认 `default` |

### 8.3 删除素材 `POST /api/v1/apps/seedance/deleteAsset`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `Id` | string | **是** | 素材 Id |
| `GroupId` | string | **是** | 所属分组 |

### 8.4 价格：没有专属规则，命中应用通配

`/api/v1/pricing` 里没有 `createGroup` / `createAsset` / `deleteAsset` 三条，但有一条：

```json
  "note":"固定 11000 点/次"}
```

按价目表字面，这三条素材接口都会命中 **11,000 点/次**。本包不替你花钱验证，`catalog` 只把规则原文摆出来 —— 先看清，再决定。

---

## 九、三个 create/remove 的请求字段（文档原文）

### 9.1 `POST /api/v1/apps/wan/create`（异步）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | 是 | `wan2.7` / `wan2.7-r2v` / `wan2.7-videoedit` |
| `prompt` | string | 是 | 画面/动作/镜头描述 |
| `resolution` | string | 否 | `720p` / `1080p`，默认 720p |
| `duration` | int | 否 | `2-15`（videoedit `2-10`），默认 5 |
| `image_with_roles` | array | r2v 必填 | `[{"url":"…","role":"reference_image"}]`，最多 2 张 |
| `image_urls` | array | 否 | 参考图 URL 列表，`wan2.7` 最多 2 张 |
| `video_urls` | array | videoedit 必填 | 待编辑视频，最多 1 段 |
| `audio_url` | string | 否 | 参考音频 |
| `watermark` / `seed` / `callback_url` | — | 否 | |

素材字段是**数组**，所以本包 `bind --app wan` 要求用 `--param` 明确给，不自动注入。

### 9.2 `POST /api/v1/apps/happy_horse/create`（异步）

与 `submit` **完全相同**的请求体格式（DashScope 风格：`model`、`prompt`、`resolution`、`duration`、`ratio`、`seed`、`watermark`、`media`），区别是固定走 happyhorse 上游渠道。素材字段是 `media`。

### 9.3 `POST /api/v1/apps/watermark_removal/remove`（同步）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `url` | string | **是** | 短视频分享链接（各主流平台） |

---

## 十、探针禁区（本轮为什么一条 create 都没探）

| 探针 | 后果 |
|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 的计价，`sync:` 即时扣费**不退**（dressing_diffusion 200 点 / nano_banana 72 点，2026-11-07 实测流水） |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结点数，再参数校验失败 → `refund` 全额退。净额 0，但钱包被短暂动过 |
| `POST /api/v1/apps/<app>/create` 缺必填 | 同上，先冻再退 |
| `GET /api/v1/apps` | 安全，规则 `cost:0`（专门为目录类只读接口加的） |

所以本包 `doctor` **只用价目表规则 + 应用目录登记** 证明 22 条 create/remove 存在，一条 POST 都不发。
唯一的 POST 是 `/api/v1/upload` 不带 file —— 停在参数校验层，不落文件、不计费。

---

## 十一、本轮**没有**验证的事（写清楚，别当成已验证）

1. `bind` 成功提交长什么样 —— 没有投过真实素材，`task_id` / `status` 的字段名是按 `wan` / `seedance` 文档与通用响应结构兼容取的（`task_id` / `taskId` / `id` / `TaskId` / `RequestId` 依次回退）。
2. 22 条 create/remove 里，除了 `happy_horse` / `wan` / `seedance` / `watermark_removal`，其余 create 路由是否可通 —— 应用目录没登记，价目表有规则，本轮 0 点铁律下不探。
3. `seedance/createAsset` 实际扣多少 —— 按价目表字面是 11,000 点/次，没有真跑。
4. `image_human` 的 `mode` 取值边界（`fast` / `standard` / `2k` / `4k`）在真实请求里的校验规则。
5. `nano_banana` 带 `views[]` 时 25 点/视角的实际结算（价目表 note 写的，没有真跑）。
6. 上传地址「24 小时」的精确边界与提前回收条件 —— 只按文档记 `expires`。

---

## 十二、复现本文的探针（全部免费）

```bash
# 上传探针（不放 file，不落文件）
curl -s -X POST "https://api.a7w.cn/api/v1/upload" \
  -H "Authorization: Bearer $KEY" -F "x=1"

# 价目表 / 应用目录 / 余额 / 流水
curl -s "https://api.a7w.cn/api/v1/pricing" -H "Authorization: Bearer $KEY"
curl -s "https://api.a7w.cn/api/v1/apps"    -H "Authorization: Bearer $KEY"
curl -s "https://api.a7w.cn/user/balance"   -H "Authorization: Bearer $KEY"
curl -s "https://api.a7w.cn/user/balance/logs?limit=100" -H "Authorization: Bearer $KEY"

# 任务查询（假 id）
curl -s "https://api.a7w.cn/api/v1/tasks/probe-no-such-task" -H "Authorization: Bearer $KEY"

# 我的任务（真实成交价来源）
curl -s "https://api.a7w.cn/api/v1/me/tasks?limit=2000&page=1" -H "Authorization: Bearer $KEY"
```

`python3 scripts/run.py doctor` 会把上面这些一次跑完并打勾。
