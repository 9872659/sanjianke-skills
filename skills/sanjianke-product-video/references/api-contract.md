# 接口契约（文档原文 + 实测返回 + 价目原文）

> 权威文档：平台官方文档节点 `nano-banana`、`full-video`、`voice-tts`、`seedance`（本仓库
> `a7w-nano-banana` / `a7w-full-video` / `a7w-voice-tts` / `a7w-seedance` 三个包的 `references/` 是原文摘录）。
> 本文所有「实测」都在 2026-11-07 真机跑过，**只发只读 GET，没有建过一条任务、没有冻结过一点**。
> 表格里的价格全部抄自 `GET /api/v1/pricing` 的原文。

---

## 一、接入信息

| 项目 | 值 |
|---|---|
| 接口根地址 | `https://api.a7w.cn/api/v1` |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 应用层形态 | `POST /api/v1/apps/<app>/<api>` |
| 成功返回 | `{"code":1,"msg":"success","data":{...}}`；校验失败也是 HTTP 200 + `code:0` |
| 另一套错误风格 | 视频/图片线路走 HTTP 4xx + `{"error":{"code":"…","message":"…"}}` |
| 任务查询 | `GET /api/v1/tasks/<task_id>`（**价目表 cost:0**） |
| 价格源 | `GET /api/v1/pricing`（返回 115 条规则，只读） |
| 目录源 | `GET /api/v1/apps`（22 个应用，只读，cost:0） |

两套错误风格并存，所以 `run.py` 的 `err_text` 两边都认。

---

## 二、4 个应用 / 17 个接口（`GET /api/v1/apps` 实测）

```
nano_banana   name=nano-banana     billing_mode=1  category=image
    submit    POST  id=69  创建图片任务
    query     GET   id=70  查询图片任务

full_video    name=全能视频生成     billing_mode=1  category=video
    submit    POST  id=73  提交任务
    query     POST  id=74  查询任务

voice_tts     name=语音TTS          billing_mode=1  category=audio
    tts          POST  id=2   文字转语音（同步）
    tts_async    POST  id=5   文字转语音（异步）
    tts_live     POST  id=26  文字转语音（Live·异步）
    stt          POST  id=3   语音转文字
    clone_voice  POST  id=1   克隆音色
    list_voices  GET   id=4   音色列表

seedance      name=Seedance 2.0     billing_mode=1  category=video
    create        POST  id=27  创建任务（唯一出片口）
    createGroup   POST  id=29  创建素材资产组合
    createAsset   POST  id=30  上传素材
    getAsset      POST  id=31  获取素材详情
    updateAsset   POST  id=32  更新素材
    deleteAsset   POST  id=33  删除素材
    query         GET   id=28  查询任务
```

**seedance 7 个接口的分工**（`call_type` 与 `Content-Type` 两处细节决定怎么写）：

| 接口 | 是生成吗 | Content-Type | 必填字段 |
|---|---|---|---|
| `create` | **是**（唯一出片） | JSON | `content[]`（须含 text 项） |
| `createGroup` | 否，素材托管 | multipart | `Name` |
| `createAsset` | 否，素材托管 | multipart | `URL` / `GroupId` / `AssetType` |
| `getAsset` | 否，素材托管 | multipart | `Id` |
| `updateAsset` | 否，素材托管 | multipart | `Id` |
| `deleteAsset` | 否，素材托管 | multipart | `Id` |
| `query` | 否，查询 | GET | `task_id` |

---

## 三、价目原文（`GET /api/v1/pricing` 实测，2026-11-07）

### 3.1 full_video：按秒 + 按分辨率（本包的定价核心）

```json
"/api/v1/apps/full_video/submit": {
  "mode": "per_second",
  "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80},
  "note": "2026-11-06 站主定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80（1 元=100 点，价格已含利润，不再叠加上游倍率）"
}
```

### 3.2 nano_banana：固定按次

```json
"/api/v1/apps/nano_banana/submit": {
  "note": "★★ Q52（2026-10-05 站主指定定价「商品多角度是视角选项每一个选择25点，AI商品图固定价格72点」）：AI商品图 = 固定 72 点/次；商品多角度 = 25 点 × 选中视角数（请求体带 views[] 时生效，不带 views 时仍按本固定价 72）。"
}
```

`/api/v1/apps/nano_banana/*` 与 `/api/v1/apps/nano_banana/submit` 同价 —— 所以 `query` 也按 72 点。

### 3.3 seedance：固定按次，且通配整条线

```json
  "note": "固定 11000 点/次"}
  "note": "固定 11000 点/次"}
```

`/api/v1/apps/seedance/*` 覆盖了 5 个素材管理接口 —— 官方文档写「免费」，站内价目表按 11,000 点/次落。

### 3.4 voice_tts：按上游真实点数 × 3

```json
```

### 3.5 两条免费路径（本包自检全靠它们）

```json
  "note": "★应用目录（只读）不计费（2026-10-04）…"}
  "note": "★上传不计费（2026-10-04 站主批准）… 计费引擎对 cost:0 有显式语义：server.js isFreePath 里 ruleCost === 0 即视为免费路径。"}
"/api/v1/tasks":  {"mode": "per_module", "cost": 50, "unitFrom": "module_codes",
  "note": "按模块计价：仅当请求体带非空 module_codes[] 时 = 50 点 × 模块数；不带则退回模型线。"}
```

### 3.6 兜底通配（没专属规则的接口落这里）

```json
```

---

## 四、full_video `submit`（平台 schema 原文）

```
POST /api/v1/apps/full_video/submit
Content-Type: application/json
```

| 字段 | 类型 | 必填 | 说明（原文） |
|---|---|---|---|
| `content` | array | **是** | 内容列表，须包含文本项；可按模式传入首帧、尾帧或参考媒体 |
| `model` | string | 否 | 固定 `full-video` |
| `ratio` | string | 否 | 画幅比例，默认 `16:9`；图生视频可用 `adaptive` |
| `duration` | integer | 否 | 生成时长秒数，**范围 4~15**，默认 4 |
| `resolution` | enum | 否 | `480P` / `768P` / `1080P` / `2K` / `4K`，默认 `480P` |
| `aigc_watermark` | boolean | 否 | 是否添加生成标识，默认 false |

`content` 项（`type` 取 `text` / `image_url` / `video_url` / `audio_url`，`role` 决定用途）：

```json
[
  {"type": "text", "text": "轻到 0.9 克，戴一天忘了它在耳朵里。"},
  {"type": "image_url", "role": "first_frame", "image_url": {"url": "https://…/商品图.png"}}
]
```

文档原文的边界（本包据此做预检）：

- 首帧、尾帧各最多 1 张；参考图片最多 9 张；参考视频、参考音频各最多 3 个。
- 首尾帧模式与参考媒体模式二选一，不混用；参考媒体模式至少 1 张图或 1 个视频，不能只传音频。
- 时长只收 4~15 的整数；`768P` / `1080P` / `2K` 的文本总长最多 5,000 字符，其余分辨率最多 7,000。
- 计费：按分辨率 SKU × 生成时长；**默认前 5 张 reference_image 免费，超出每张加 20 点**。

`run.py` 的 `clip` / `make` 就把 `text` + `first_frame` 拼成这个 `content`，`--ref-image` 追加

---

## 五、nano_banana `submit`（平台 schema 原文 + 真实任务返回）

```
POST /api/v1/apps/nano_banana/submit      （JSON，异步，返回 task_id）
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `prompt` | string | **是** | 图片内容 / 主体 / 风格 / 构图 / 细节 |
| `action` | string | 否 | `generate`（文生图，默认）/ `edit`（基于参考图编辑） |
| `model` | string | 否 | `nano-banana`（默认）/ `-2` / `-2-lite` / `-pro` / `…:official` |
| `image_urls` | array | `edit` 必填 | 参考图 http(s) 列表 |
| `resolution` | string | 否 | `1K`（默认）/ `2K` / `4K`，官方高清模型按档计价 |
| `aspect_ratio` | string | 否 | `auto` / `1:1` / `16:9` / `9:16` / `4:3` / `3:4` / `3:2` / `2:3` / `5:4` / `4:5` / `21:9` |
| `callback_url` | string | 否 | 完成 / 失败回调 |

真实任务返回（`GET /api/v1/tasks/task_6e616ef0605f1b919e7f0b93`，实测原文，prompt 已省略）：

```json
{"code":1,"msg":"success","data":{
  "task_id":"task_6e616ef0605f1b919e7f0b93","model":"nano_banana/submit",
  "type":"app","call_type":"async","status":"completed",
  "created_at":"2026-10-08T15:14:25Z",
  "result":{"data":[{"prompt":"…","image_url":"https://cdn3.saasos.cn/aigc/awimg_6d9a7ecd50fc82d5.png"}],
            "success":true,"trace_id":"…","image_url":"https://cdn3.saasos.cn/aigc/awimg_6d9a7ecd50fc82d5.png",
            "upstream_task_id":"575d7ee5-…","results":[{"image_url":"https://cdn3.saasos.cn/aigc/awimg_6d9a7ecd50fc82d5.png"}]},
  "usage":{"input_tokens":0,"output_tokens":0,"total_tokens":0,"points_cost":24},
  "completed_at":"2026-10-08T15:14:41Z"}}
```

（`result.image_url` / `result.data[].image_url` / `result.results[].image_url`），`pick_asset` 按
扩展名兜一层，三处任意一处命中都能取到。

---

## 六、voice_tts `tts`（同步，直接回音频地址）

```
POST /api/v1/apps/voice_tts/tts           （JSON，同步，直接返回 audio_url）
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | string | **是** | 待合成文本，同步接口建议 ≤500 字符 |
| `model` | string | 否 | `s1` / `s2-pro`（默认 `s2-pro`） |
| `format` | string | 否 | `mp3`（默认）/ `wav` / `pcm` / `opus` |
| `reference_id` | string | 否 | 克隆音色的 model_id，单说话人传 string |
| `sample_rate` | integer | 否 | 8000 / 16000 / 22050 / 44100 |
| `mp3_bitrate` | integer | 否 | 64 / 128 / 192 |
| `temperature` / `top_p` | number | 否 | 默认 0.7 / 0.8 |
| `prosody` | object | 否 | `speed` / `volume` / `normalize_loudness` |

同步返回（文档原文）：

```json
{"code":1,"msg":"success","data":{"audio_url":"https://your-domain.com/uploads/ai_app/202604/tts_xxxxxxxx.mp3","format":"mp3"}}
```

真实任务（`GET /api/v1/tasks/task_54bbb07ca0935d36fcb8aa67`，走的是同一应用的 `tts_live`）：

```json
{"code":1,"msg":"success","data":{
  "task_id":"task_54bbb07ca0935d36fcb8aa67","model":"voice_tts/tts_live",
  "type":"app","call_type":"async","status":"completed",
  "result":{"format":"mp3","audio_url":"https://cdn3.saasos.cn/aigc/awaud_6bb57166f6f565c3.mp3"},
  "usage":{"input_tokens":0,"output_tokens":0,"total_tokens":0,"points_cost":2.64}}}
```

同一 `task_id` 的余额流水是 `settle −7.920` —— 2.64 × 3 = 7.92，**站内口径 = 上游真实点数 × 3** 得到确认。
所以本包按 **0.18 点/字** 估（5.94 ÷ 33 = 0.18），`cost` 会明确标注这是下限估算。

---

## 七、seedance（7 个接口的参数原文）

### 7.1 `create`（JSON，唯一出片口）

```
POST /api/v1/apps/seedance/create
```

| 字段 | 说明 |
|---|---|
| `model` | `seedance-2-text-2-video` / `seedance-2-video-2-video` / `seedance-2-fast-text-2-video` / `seedance-2-fast-video-2-video` |
| `content[]` | `{type, text|image_url|video_url|audio_url, role}`，图片 ≤9、视频 ≤3、音频 ≤3，不可只传音频 |
| `duration` | 4~15 秒，或 −1 由模型决定 |
| `resolution` | `480p` / `720p` / `1080p`（默认 720p） |
| `ratio` | `16:9` / `4:3` / `1:1` / `3:4` / `9:16` / `21:9` / `adaptive` |
| `generate_audio` | 是否生成与画面同步的音频 |
| `watermark` / `callback_url` / `seed` / `draft` | 可选 |

计费原文：「按输出 `total_tokens` 与定价矩阵结算…不同分辨率 × 是否含视频输入 单价不同；创建任务时预扣可为
0，完成后按矩阵扣点。」站内则钉死 **11,000 点/次**。

### 7.2 素材管理 5 个（全部 `multipart/form-data`）

| 接口 | 必填字段 | 说明 |
|---|---|---|
| `createGroup` | `Name`（≤64） | 可选 `GroupType=AIGC`、`Description`（≤300）、`ProjectName`（默认 default） |
| `createAsset` | `URL` / `GroupId` / `AssetType` | `AssetType` 取 `Image` / `Video` / `Audio`；上游异步拉取入库 |
| `getAsset` | `Id` | `Result.Status`：`Active`（可用）/ `Processing` / `Failed` |
| `updateAsset` | `Id` | 可选 `Name` |
| `deleteAsset` | `Id` | — |

素材入库后可在 `create` 的 `content` 里用 `asset://<ASSET_ID>` 引用。

---

## 八、查任务：只用 `GET /api/v1/tasks/<task_id>`

| 情形 | 实测返回 |
|---|---|
| 假 id | `200 {"code":0,"msg":"任务不存在","data":null}` |
| 真任务 | `200 {"code":1,"msg":"success","data":{"task_id","model","type","call_type","status","result","usage","completed_at"}}` |

`status` 取值实测见过：`completed` / `failed` / `processing` / `SUCCESS`（大小写都出现过，本包统一 `lower`）；

为什么不用应用层 `query`：

```
/api/v1/apps/nano_banana/query   → 落在 /api/v1/apps/nano_banana/*   = 72 点/次
/api/v1/apps/seedance/query      → 落在 /api/v1/apps/seedance/*      = 11,000 点/次
/api/v1/apps/full_video/query    → 没有专属规则，落通配           = 上游点数 ×2、保底 50 点
```

---

## 九、本轮**没有**验证的事（写清楚，别当成已验证）

1. **成功提交的返回体**。`clip` / `scene` / `make` 提取 `task_id` 的字段名是
   `task_id` / `taskId` / `id` 三个都试；文档示例是 `data.task_id`（nano-banana 的官方示例原文：
   `{"code":1,"msg":"success","data":{"task_id":"task_xxxxxxxxxxxx","status":"pending","app":"nano_banana","api":"submit","frozen_points":24}}`）。
2. **full_video 成功任务的 `result` 里成片字段名**。本包用 `pick_asset` 按 `.mp4/.mov/.webm/.m4v`
   扩展名 + 字段名含 `video` 两层兜底，不赌某一个键。
3. **字幕是否需要烧进画面**。接口只出无水印成片，字幕是本地生成的 SRT，烧录要靠本机 ffmpeg。
4. **seedance 素材管理是否真的按 11,000 点收费**。价目表是这么写的（`/seedance/*` 通配），
   但官方文档标「免费」。本包按 11,000 点做**保守估算**并卡在 `--budget` 后面，没有发过这类请求。
5. **`voice_tts/list_voices` 的冻结额**。它是 GET，但同账户流水里能看到成对的
   `reserve_sync −150` / `refund +150`（2026-11-07 21:46–21:47 区间，净 0，不是本包发的）。本包不做这类探针。

---

## 十、复现本文的探针（全部免费）

```bash
KEY=sk-你的key
# 1) 余额
curl -s "https://api.a7w.cn/user/balance" -H "Authorization: Bearer $KEY"

# 2) 应用目录（cost:0）
curl -s "https://api.a7w.cn/api/v1/apps" -H "Authorization: Bearer $KEY"

# 3) 价目（只读）
curl -s "https://api.a7w.cn/api/v1/pricing" -H "Authorization: Bearer $KEY"

# 4) 任务查询路由（假 id）
curl -s "https://api.a7w.cn/api/v1/tasks/product-video-doctor-probe" -H "Authorization: Bearer $KEY"
```

`python3 scripts/run.py doctor` 就是把上面 4 条跑一遍并打勾，**0 点**。
