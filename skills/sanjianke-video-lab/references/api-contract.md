# 接口契约（文档原文 + 实测返回）

> 权威文档：`https://api.a7w.cn/assets/docdata.json` 里的节点 `video-restore`、`video-colorize`、
> `video-enhance`、`video-viapi-catalog`、`video-face-swap`、`video-body-segment`、
> `video-portrait-enhance`、`video-subtitle-erase`、`video-delogo`、`video-shot-detect`、
> `video-castcrew-ocr`、`open-api-upload`、`open-api-task-query`。
> 本文每条结论都在 2026-11-07 真机跑过，**全部停在参数校验层，没有建过一条任务**。

---

## 一、接入信息

| 项目 | 值 |
|---|---|
| 接口根地址 | `https://api.a7w.cn/api/v1` |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 调用方式 | **异步两步**：POST 提交拿 `taskId` → GET 轮询结果 |
| 计费 | 按输出秒数（最小 1 秒）或按次；任务失败**全额退回** |
| 价格源 | `GET /api/v1/pricing`（免费） |

---

## 二、11 档路由（空 body 探针实测，2026-11-07）

### 2.1 结果总表

| 能力 | 扁平 `POST /api/v1/video/X` | `POST /api/v1/video/viapi/X` | 本包用 |
|---|---|---|---|
| `restore` 视频修复 | **400 `pixverse_empty_url`** | **404 `unknown_tool`** | **扁平** |
| `colorize` 校色 | 400 `empty_url` | 400 `empty_url` | viapi |
| `shot` 镜头检测 | 400 `empty_url` | 400 `empty_url` | viapi |
| `castcrew` 认演员表 | 400 `empty_url` | 400 `empty_url` | viapi |
| `delogo` 台标擦除 | 400 `empty_url` | 400 `empty_url` | viapi |
| `subtitle` 字幕擦除 | 400 `empty_url` | 400 `empty_url` | viapi |
| `enhance` 画质增强 | 400 `empty_url` | 400 `empty_url` | viapi |
| `faceswap` 换脸 | **404（SPA HTML 兜底）** | **400 `empty_url`** | **viapi** |
| `segment` 抠像 | **404（SPA HTML 兜底）** | **400 `empty_url`** | **viapi** |
| `cartoon` 卡通化 | **404（SPA HTML 兜底）** | **400 `empty_url`** | **viapi** |
| `portrait` 人像增强 | 400 `empty_url` | 400 `empty_url` | viapi |

**结论**：`restore` 只有扁平那条通；`faceswap` / `segment` / `cartoon` 只有 viapi 那条通；
其余 7 档两条都通，本包统一走 viapi。`catalog` 会逐档打印实际路径，`doctor` 每次重跑这 11 条探针。

### 2.2 原始返回（`-d '{}'`）

```
POST /api/v1/video/restore          -> 400 {"error":{"code":"pixverse_empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/viapi/restore    -> 404 {"error":{"code":"unknown_tool","message":"未知的视频工具：restore","type":"relay"}}
POST /api/v1/video/colorize         -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/viapi/colorize   -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/shot             -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/viapi/shot       -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/castcrew         -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/viapi/castcrew   -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/delogo           -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/viapi/delogo     -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/subtitle         -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/viapi/subtitle   -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/enhance          -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/viapi/enhance    -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/faceswap         -> 404 <!DOCTYPE html> ...  （前端 SPA 兜底页）
POST /api/v1/video/viapi/faceswap   -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/segment          -> 404 <!DOCTYPE html> ...
POST /api/v1/video/viapi/segment    -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/cartoon          -> 404 <!DOCTYPE html> ...
POST /api/v1/video/viapi/cartoon    -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/portrait         -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
POST /api/v1/video/viapi/portrait   -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}
```

> `viapi/cartoon` 第一次探针在 45 秒读超时，重试两次都 400 —— 是**冷启动**，不是路径问题。
> `doctor` 的默认探针超时 90 秒就是为它留的。

### 2.3 统一入口（文档有，本包没走）

```
POST /api/v1/video/viapi/submit  {"tool":"colorize"}   -> 400 empty_url
POST /api/v1/video/viapi/submit  {}                    -> 400 {"error":{"code":"empty_tool","message":"tool 不能为空，可用 tool=superres / segment / faceswap / cartoon…"}}
```

分路径已经够清楚，本包统一用 `/<tier>` 分路径，少一层 `tool` 参数。

---

## 三、提交参数

必填只有 **`videoUrl`**；空 body 的报错原文就是「videoUrl 不能为空」。

| 字段 | 必填 | 说明 |
|---|---|---|
| `videoUrl` | **是** | 视频地址，必须在平台白名单内（见第四节） |
| `duration` | 否 | 视频秒数，**用于预冻结**。文档原文：「视频秒数（用于预冻结，缺省 5 秒）」 |
| `faceUrl` | `faceswap` 必填 | 人脸参考图，任意 http(s) 图片地址；服务端自动镜像转存（单张 ≤15 MB、抓取超时 20 秒） |
| `seed` | 否 | 随机种子（restore / colorize / enhance 文档列出） |
| `callback_url` | 否 | 完成回调地址 |

### 关于 `duration` 的实测边界（诚实说明）

- 文档（`video-restore` / `video-colorize` / `video-enhance`）明确写：「`duration` 否，用于预冻结，缺省 5 秒」。
- 探针层面能确认的只有一件事：**缺 body / 缺 url 时，`duration` 相关的校验不会先报错** ——
  `{"duration": 10}`、`{"duration": "abc"}`、`{"duration": 0}` 三种写法，返回的都是
  `400 empty_url`（restore 是 `pixverse_empty_url`），说明 url 校验在前。
- 要确认「带合法 url 但缺 duration」的返回，必须投一个白名单内的可达地址 —— 那会**真实建任务并冻结**。
  本轮 0 点铁律下没做这一步。
- **本包的规避设计**：按秒档提交时**总是显式带 `duration`**（默认 5），所以 `duration` 必填与否都不影响使用。

---

## 四、`videoUrl` 白名单（这条最容易被忽略）

实测：`POST /api/v1/video/viapi/shot` body `{"videoUrl":"https://cdn.example.com/a.mp4"}`

```json
{"error":{"code":"url_not_allowed","message":"videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）","type":"relay"}}
```

| 可用来源 | 形态 |
|---|---|
| 本站成片 | `https://vr.a7w.cn/result/xxx.mp4` |
| 本站七牛 | `https://cdn2.jiujiushuyuan.cn/vr/xxx.mp4` |
| 本站上传接口 | `https://oss.gpu.likeadmin.cn/openapi/<租户>/<日期>/<hash>.mp4` |

**请求在参数校验层就被拒绝**：没有 `taskId`、没有冻结、没有任务记录（实测前后 `GET /api/v1/tasks` 条数不变）。

---

## 五、上传（`upload` 子命令）

```
POST https://api.a7w.cn/api/v1/upload
Content-Type: multipart/form-data
Authorization: Bearer <key>

file: <二进制>          ← 字段名就是 file，单文件默认上限 512 MB
```

文档原文：**「接口不收取模型调用费用」**，仅用于临时中转，返回地址**最长 24 小时**。

成功响应（实测，256 B 的假 mp4）：

```json
{"code":1,"msg":"success","data":{"url":"https://oss.gpu.likeadmin.cn/openapi/18/20261107/2758bb2664f5a95b7292afdfa8d26552.mp4","path":"openapi/18/20261107/2758bb2664f5a95b7292afdfa8d26552.mp4","name":"probe.mp4","size":256,"mime_type":"image/x-tga","type":"video"}}
```

不带 `file`（实测）：

```json
{"code":0,"msg":"请使用 file 字段提交一个文件","data":null}
```

> 注意这两个接口的 HTTP 状态码都是 **200**，成败看 `code`（1 成功 / 0 失败）和 `msg`。
> 视频提交线则是用 HTTP 400 + `{"error":{"code":…}}` 报错 —— **两套错误风格并存**，`err_text` 两种都认。

---

## 六、查询接口（三套，别串了）

| 路径 | 服务对象 | 假 id 实测返回 | 真 video 任务实测 |
|---|---|---|---|
| `GET /api/v1/tasks/{taskId}` | 模型任务 / 应用任务 | `200 {"code":0,"msg":"任务不存在","data":null}` | **`200 {"code":0,"msg":"任务不存在"}`** ← 查不到视频后处理任务 |
| `GET /api/v1/video/viapi/result/{taskId}` | 视频后处理（viapi 档） | `404 {"error":{"code":"not_found","message":"Task not found.","type":"relay"}}` | **200，见下** |
| `GET /api/v1/video/viapi/query/{taskId}` | 同上（等价路径） | 同上 | — |
| `GET /api/v1/video/viapi/<tier>/{taskId}` | 各档自己的查询 | 404 not_found | 200，**与 result 同源**，字段更全（`posterUrl` / `transferStatus` / `note` / `duration`） |
| `GET /api/v1/video/restore/{taskId}` | restore | 404 not_found | 未实测 |
| `GET /api/v1/videos/{id}` | **视频生成**家族（不是后处理） | `400 {"code":"task_not_exist","message":"task_not_exist","data":null}` | — |

**真任务实测原文**（别人建的 colorize，`task_2d920…` / `task_951b…`）：

```json
// GET /api/v1/video/viapi/result/task_2d920d1b195db68bb02bbd68
{"taskId":"task_2d920d1b195db68bb02bbd68","tool":"colorize","status":"failed",
 "message":"参数错误，请参考文档检查参数值 - 输入视频的格式无效，请检查输入文件是否是视频 - Input video is illegal and cannot get its info",
 "refund":45}
```

```json
// 同一 taskId，几分钟后再查（平台自动重试了）
{"taskId":"task_2d920d1b195db68bb02bbd68","tool":"colorize","status":"processing",
 "videoUrl":"","posterUrl":"","transferStatus":"","note":"正在转存到本站，请稍候…"}
```

> 两条别踩的坑：
> 1. **通用 `/tasks/{id}` 不认视频后处理任务** —— 它只服务模型/应用任务。查后处理用 `video/viapi/result`。
> 2. **状态会来回**：实测同一 taskId 先 `failed` + `refund: 45`，几分钟后又 `processing`（平台把失败的自动重试了）。
>    看到 `refund` 先别急着判死，隔 30 秒再查一次；最终以余额与 `settle` 后的流水为准。

`status` 子命令的查找顺序：`/tasks/{id}` → `video/viapi/result/{id}` → `video/viapi/query/{id}` →
`--tier` 指定档 → 其余 10 档各自的 `/<tier>/{id}`。全是只读 GET，**查询不产生扣费**。

通用查询的响应结构（文档原文）：

```json
{"code":1,"msg":"success","data":{"task_id":"task_xxx","model":"…","type":"video",
 "call_type":"async","status":"completed","result":{"video_url":"https://…"},
 "usage":{"points_cost":400}}}
```

`status` 取值：`pending` / `processing` / `completed` / `failed` / `cancelled`。

**任务列表**（免费，能一次看到全部任务与实扣）：`GET /api/v1/tasks?page=1&page_size=100`，
返回 `{"code":1,"data":{"lists":[{task_id, model_code, status, actual_points, created_at, completed_at}]}}`。
分页参数实测不生效（`page_size=5` 与 `=100` 返回一致），按返回值自己截。

---

## 七、价格（`GET /api/v1/pricing` 原文，单位：点）

```json
"/api/v1/video/colorize":      {"mode":"per_second","perSecond":9, "note":"视频校色（VIAPI AdjustVideoColor）：9 点/秒"}
"/api/v1/video/segment":       {"mode":"per_second","perSecond":9, "note":"人像抠像 mask（VIAPI）：9 点/秒"}
"/api/v1/video/subtitle":      {"mode":"per_second","perSecond":9, "note":"字幕擦除"}
"/api/v1/video/enhance":       {"mode":"per_second","perSecond":15,"note":"画质综合增强（VIAPI EnhanceVideoQuality）：15 点/秒"}
"/api/v1/video/portrait":      {"mode":"per_second","perSecond":18,"note":"人像增强（公测免费）"}
"/api/v1/video/faceswap":      {"mode":"per_second","perSecond":20,"note":"视频人脸融合/换脸（VIAPI MergeVideoFace）：20 点/秒"}
"/api/v1/video/shot":          {"mode":"per_second","perSecond":20,"note":"视频镜头检测（VIAPI DetectVideoShot）：20 点/次"}
"/api/v1/video/cartoon":       {"mode":"per_second","perSecond":24,"note":"人像卡通化（VIAPI）：24 点/秒"}
"/api/v1/video/castcrew":      {"mode":"per_second","perSecond":25,"note":"视频 OCR 硬字幕/演职员表（VIAPI RecognizeVideoCastCrewList）：25 点/次"}
"/api/v1/video/delogo":        {"mode":"per_second","perSecond":25,"note":"视频台标/Logo 擦除（VIAPI EraseVideoLogo）：25 点/次"}
"/api/v1/video/restore":       {"mode":"per_second","perSecond":36,"note":"视频修复：固定 36 点/秒（4K超清的 2 倍）"}
```

**口径冲突**：`shot` / `castcrew` / `delogo` 的 `rule` 是 `per_second`，`note` 写「点/次」。
本包按 `note` 计一次，`cost` 里把两种口径都写出来，最终以账单为准。

`portrait` 另一处冲突：`perSecond: 18`，`note` 写「公测免费」。同样以账单为准。

同一路由上还有 `superres`（9）/ `superres2k`（15）/ `superres4k`（20）/ `interp`（25）四档，
属超分与插帧，本包不收（超分有独立的 `sanjianke-vr-superres*` 包）。

---

## 八、计费口径

- 按秒档：按**输出**秒数计费，最小 1 秒；提交时按 `duration` 预冻结，完成后按实际时长结算。
- 按次档：与素材时长无关。
- 任务失败：**全额退回**。
- 成品链接有效期约 **30 分钟**（`video-portrait-enhance` / `video-body-segment` 文档原文），
  平台会把上游链接转存到本站/七牛后再交付。
- `shot` / `castcrew`：`status=completed` 时 `videoUrl` 为空，结果在 `result`；
  `castcrew` 另有一个 `artifactUrl`（SRT，30 分钟有效）。

---

## 九、本轮**没有**验证的事（写清楚，别当成已验证）

1. 成功提交长什么样 —— 没投过真实素材，`{"taskId","status","PENDING","duration","cost","balance"}`
   这组字段来自文档，不是实测。（旁证：别人用假 mp4 提交 `colorize` 的两个任务，`result` 路由能查到
   `tool` / `status` / `message` / `refund`，说明「提交 → 任务 → 失败 → 退款」整条链是通的。）
2. `duration` 缺失时上游是否接受 —— 见第三节。
3. `restore` 的 `GET /api/v1/video/restore/{taskId}` 是否与 `viapi/result` 同源 —— 只用假 id 验过「路由在」。
4. `castcrew` 的 `result` / `artifactUrl` 实际字段名 —— 文档原文如此，未实测。
5. `faceswap` 的 `faceUrl` 镜像转存 —— 文档原文，未实测。
6. 平台自动重试的触发条件与次数 —— 只观察到「failed + refund → processing」这一次。

---

## 十、复现本文的探针（全部免费）

```bash
# 11 条空 body 探针
for t in restore colorize shot castcrew delogo subtitle enhance faceswap segment cartoon portrait; do
  curl -s -o /dev/null -w "$t flat %{http_code}\n" -X POST \
    "https://api.a7w.cn/api/v1/video/$t" -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/json" -d '{}'
  curl -s -o /dev/null -w "$t viapi %{http_code}\n" -X POST \
    "https://api.a7w.cn/api/v1/video/viapi/$t" -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/json" -d '{}'
done

# 查询路由（假 id）
curl -s "https://api.a7w.cn/api/v1/tasks/probe-no-such-task" -H "Authorization: Bearer $KEY"
curl -s "https://api.a7w.cn/api/v1/video/viapi/result/probe-no-such-task" -H "Authorization: Bearer $KEY"

# 上传接口（不带 file，不落文件）
curl -s -X POST "https://api.a7w.cn/api/v1/upload" -H "Authorization: Bearer $KEY" -F "x=1"
```

`python3 scripts/run.py doctor` 会把上面这些一次跑完并打勾。
