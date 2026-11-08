# 接口契约（实测原文，2026-11-07）

> 本文每条结论都在 2026-11-07 真机跑过。**只读 GET + 空 body 探针**，没有提交过真实素材：
> 0 条任务、0 点净花费（应用层两次免费 GET 先冻 50 / 150 点，随后全额退回，见第七节）。
> 价格原文取自 `GET /api/v1/pricing`（115 条规则）。

---

## 一、接入信息

| 项目 | 值 |
|---|---|
| 接口根地址 | `https://api.a7w.cn/api/v1` |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 调用方式 | 异步两步：POST 提交拿 taskId → GET 轮询结果 |
| 视频工位 | `POST /api/v1/video/viapi/<castcrew|delogo|subtitle|enhance>` |
| 配音 | `POST /api/v1/apps/voice_tts/tts_async` |
| 混剪 | `POST /api/v1/apps/smart_clip/broadcast_mixcut` |
| 上传 | `POST /api/v1/upload`（multipart，字段名 `file`） |
| 价格源 | `GET /api/v1/pricing`（免费） |
| 应用注册表 | `GET /api/v1/apps`（免费，22 个应用，带 apis 列表） |

---

## 二、六个工位的请求体

### 2.1 视频工位（`videoUrl` 必填）

```json
POST /api/v1/video/viapi/castcrew   {"videoUrl": "https://vr.a7w.cn/result/x.mp4"}
POST /api/v1/video/viapi/delogo     {"videoUrl": "https://vr.a7w.cn/result/x.mp4",
                                     "boxes": [{"X":0.05,"Y":0.05,"W":0.2,"H":0.1}]}
POST /api/v1/video/viapi/subtitle   {"videoUrl": "https://vr.a7w.cn/result/x.mp4", "duration": 60}
POST /api/v1/video/viapi/enhance    {"videoUrl": "https://vr.a7w.cn/result/x.mp4", "duration": 60}
```

- `duration` 用于**预冻结**，文档原文「视频秒数（用于预冻结，缺省 5 秒）」；本包按秒工位总是显式传。
- `castcrew` / `delogo` 按次计费，不带 `duration`。
- `delogo` 的 `boxes` 为可选，`X/Y/W/H` 是 0~1 的画面占比，缺省全画面。**参数形状取自文档，未实测**。

### 2.2 配音（`text` 必填）

```json
POST /api/v1/apps/voice_tts/tts_async
{"text": "解说词", "model": "s2-pro", "format": "mp3", "reference_id": "<音色ID>"}
```

- `model` 可选 `s1` / `s2-pro`（默认后者）；`format` 可选 `wav/pcm/mp3/opus`。
- `reference_id` 是音色模型 ID，先用 `GET /api/v1/apps/voice_tts/list_voices` 查（58 个音色）。

### 2.3 混剪（`styleId` + `materials` 必填）

```json
POST /api/v1/apps/smart_clip/broadcast_mixcut
{"styleId": "6ac8981c20d5010033eee1b7",
 "language": "zh-CN",
 "title": "可选，不填就不显示标题",
 "audioUrl": "tts 产出的音频",
 "materials": [{"type": "video", "fileUrl": "enhance 产出的视频", "soundSwitch": false}]}
```

- `styleId` 用 `GET /api/v1/apps/smart_clip/template?scene=oralMixCutting` 查（混剪场景固定用 `oralMixCutting`）。
- 平台文档明确：当前应用只支持 `audioUrl` 或素材输入链路；传 `content` 或 `speakerId` 会返回 `unsupported_speaker_branch`。

---

## 三、实测原始返回（空 body / 假 id，全部停在校验层）

```
POST /api/v1/video/viapi/castcrew  {}
  -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}

POST /api/v1/video/viapi/delogo    {}
  -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}

POST /api/v1/video/viapi/subtitle  {}
  -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}

POST /api/v1/video/viapi/enhance   {}
  -> 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}

POST /api/v1/video/viapi/subtitle  {"videoUrl":"https://example.invalid/x.mp4"}
  -> 400 {"error":{"code":"url_not_allowed",
          "message":"videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
                     或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）",
          "type":"relay"}}

GET  /api/v1/video/viapi/result/probe-no-such-task
  -> 404 {"error":{"code":"not_found","message":"Task not found.","type":"relay"}}

GET  /api/v1/tasks/probe-no-such-task
  -> 200 {"code":0,"msg":"任务不存在","data":null}

POST /api/v1/upload（multipart，不带 file）
  -> 200 {"code":0,"msg":"请使用 file 字段提交一个文件","data":null}

GET  /api/v1/apps
  -> 200，22 个应用；smart_clip/broadcast_mixcut = POST call_type 2；
     voice_tts/tts_async = POST call_type 2
```

> 两套错误风格并存：视频线是 HTTP 400 + `{"error":{"code":…}}`，应用线与上传是 HTTP 200 + `{"code":0,"msg":…}`。

---

## 四、上传（`POST /api/v1/upload`，免费）

```
POST https://api.a7w.cn/api/v1/upload
Content-Type: multipart/form-data
Authorization: Bearer <key>

file: <二进制>          ← 字段名就是 file，单文件默认上限 512 MB
```

成功响应（文档示例，本包 doctor 只验了「不带 file 回 code 0」这一形态）：

```json
{"code":1,"msg":"success","data":{
  "url":"https://oss.gpu.likeadmin.cn/openapi/18/20261107/xxxx.mp4",
  "path":"openapi/18/20261107/xxxx.mp4","name":"a.mp4","size":256,
  "mime_type":"video/mp4","type":"video"}}
```

- 地址**最长 24 小时**有效；上传不收取模型调用费用。
- `data.url` 在 `videoUrl` 白名单内，可直接给四个视频工位。

---

## 五、白名单（实测）

| 可用来源 | 形态 |
|---|---|
| 本站成片 | `https://vr.a7w.cn/result/xxx.mp4` |
| 本站七牛 | `https://cdn2.jiujiushuyuan.cn/vr/xxx.mp4` |
| 本站上传接口 | `https://oss.gpu.likeadmin.cn/openapi/<租户>/<日期>/<hash>.mp4` |

外站地址在**参数校验层**就被拒绝：没有 taskId、没有冻结、没有任务记录。本包 `run` 会在本地先按这张表预检，不合格直接退 `2`，不发请求。

---

## 六、查询

| 路径 | 服务对象 | 假 id 实测 |
|---|---|---|
| `GET /api/v1/video/viapi/result/{taskId}` | 视频工位 | `404 {"error":{"code":"not_found","message":"Task not found."}}` |
| `GET /api/v1/tasks/{taskId}` | 应用工位（tts / mixcut） | `200 {"code":0,"msg":"任务不存在","data":null}` |

真任务返回（文档 + 历史实测）：

```json
// 视频工位
{"taskId":"task_xxx","tool":"colorize","status":"failed",
 "message":"参数错误…","refund":45}

// 应用工位
{"code":1,"msg":"success","data":{"task_id":"task_xxx","status":"completed",
 "result":{"video_url":"https://…"},"usage":{"points_cost":270}}}
```

`status` 取值：`pending` / `processing` / `completed` / `failed` / `cancelled`。

> 视频工位实测过一个坑：同一 taskId 先 `failed` + `refund`，几分钟后又变 `processing`（平台自动重试）。
> 本包 `run` 看到 `failed` 会等 30 秒再确认一次，避免把「正在重试」判死。

---

## 七、价格原文（`GET /api/v1/pricing`）

```json
"/api/v1/video/viapi/castcrew": {"mode":"per_second","perSecond":25,
  "note":"视频 OCR 硬字幕/演职员表（VIAPI RecognizeVideoCastCrewList）：25 点/次"}
"/api/v1/video/viapi/delogo":   {"mode":"per_second","perSecond":25,
  "note":"视频台标/Logo 擦除（VIAPI EraseVideoLogo）：25 点/次"}
"/api/v1/video/viapi/subtitle": {"mode":"per_second","perSecond":9, "note":"字幕擦除"}
"/api/v1/video/viapi/enhance":  {"mode":"per_second","perSecond":15,
  "note":"画质综合增强（VIAPI EnhanceVideoQuality）：15 点/秒"}
"/api/v1/apps/smart_clip/*":    {"mode":"per_second","perSecond":4.5,"estimate":45,
  "note":"…对外 = 1.5 × 3 = 4.5 点/秒（15 秒 → 67.5 点）；无 duration 时按 estimate 45 点预估"}
```

**口径冲突**：`castcrew` / `delogo` 的 `rule` 是 `per_second`，`note` 写「点/次」。本包按 `note` 计一次，
`cost` 会把两种口径都打出来（`25 点/次` 与 `25 × 秒`），最终以账单为准。

---

## 八、`reserve_sync`：连免费 GET 都会先冻结

本包实测（2026-11-07 20:56–20:57，`GET /user/balance/logs` 原文）：

```
20:56:39  冻结/预扣  -50   reserve_sync:/api/v1/apps/smart_clip/template
20:56:57  退款       +50   refund:sync:/api/v1/apps/smart_clip/template
20:57:08  冻结/预扣 -150   reserve_sync:/api/v1/apps/voice_tts/list_voices
20:57:12  退款      +150   refund:sync:/api/v1/apps/voice_tts/list_voices
```

- 两次都是**免费查询**，也都是**净 0**，但钱包被短暂动过（余额先减后加，`frozen` 一度不为 0）。
- 结论：应用层的 `submit` 缺参数会先冻结再全额退；**免费的 GET 也会**。
- 所以 `doctor` 只查 `GET /api/v1/apps` 注册表（这条不冻结），把 `template` 单独做成子命令并在输出里写明「冻 50 退 50」。

---

## 九、本轮没有验证的事

1. 成功提交视频工位的真实返回 —— 没投真实素材；`{taskId,status,duration,cost,balance}` 来自文档。
2. `delogo` 的 `boxes` 形状 —— 文档写「X/Y/W/H 为 0~1 占比」，本包按 `[{"X","Y","W","H"}]` 发送，未实测。
3. `castcrew` 的 `result` / `artifactUrl` 实际字段名 —— 文档原文如此，未实测。
4. `mixcut` 的 `materials` 是否接受本站成片地址 —— 文档示例用任意公网地址，本包按白名单地址发送。
5. `tts_async` 的真实上游点数与 `usage.points_cost` 回填位置 —— 只按价目表的 ×3 口径估算。
6. `template` 的 `sid` 分页 —— 只取第一页，未翻页。
