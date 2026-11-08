# 接口契约（实测原文 + 计费口径）

> 全部走 `https://api.a7w.cn`，鉴权 `Authorization: Bearer <你的 Key>`。
> 返回信封：`{"code":1,"msg":"success","data":{…}}`；部分接口是裸对象，本包三种都兜。
> 单位：**1 元 = 100 点**。价目来源 `GET /api/v1/pricing`（2026-11-08 现查）+ 流水实测。

---

## 一、`POST /api/v1/images/generations` · 出图（同步）

端点**必须带 `/api` 前缀**：少一层会被路由到网关默认应用，`model` 被静默忽略。

```json
{"model": "gpt-image-2.6", "prompt": "游戏宣发主视觉，二次元卡牌，主角与世界观同框",
 "n": 2, "size": "1280x720", "output_format": "png"}
```

| 字段 | 说明 |
|---|---|
| `model` | `gpt-image-2.6` |
| `prompt` | 必填；空字符串返回 **422** `prompt: String should have at least 1 character` |
| `n` | **1~4**，一次多图，按张计费 |
| `size` | `auto` / `1024x1024` / `1024x1536` / `宽x高`；16 的倍数、长短边 ≤3:1、单边 ≤3840、总像素 655,360~8,294,400 |
| `output_format` | png / jpeg / webp / gif |

**计费**：**6 点/张**，与尺寸、质量、输出格式无关，按响应 `data` 里**实际返回张数**计。返回默认 `b64_json`，本包自动解码落盘成 png。

---

## 二、`POST /api/v1/images/edits` · 改图（同步，multipart）

有草稿图或实拍参考时走这条，构图与主体不走样。字段与出图相同，文件字段名 **`image`**：

```
multipart/form-data
  model         gpt-image-2.6
  prompt        "把这版草稿改成 16:9 商店页头图，保留角色与构图"
  n             1
  size          1280x720
  output_format png
  image         <本地文件>
```

**计费**：同样 **6 点/张**。

---

## 三、`POST /api/v1/apps/full_video/submit` · 买量片 / 品牌片（异步）

```json
{
  "model": "full-video",
  "content": [
    {"type": "text", "text": "15 秒买量片，0-3 秒战斗高光，3-9 秒角色技能，9-15 秒下载引导"},
    {"type": "image_url", "role": "first_frame",
     "image_url": {"url": "https://oss.gpu.likeadmin.cn/openapi/…"}}
  ],
  "duration": 15,
  "resolution": "1080P",
  "ratio": "9:16",
  "aigc_watermark": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `content` | array | 是 | 必含一条 `{"type":"text"}`；可带首帧 / 尾帧 / 参考媒体 |
| `duration` | int | 否 | **4~15**，默认 4 |
| `resolution` | string | 否 | 480P / 768P / 1080P / 2K / 4K，默认 480P |
| `ratio` | string | 否 | 16:9 / 9:16 / 1:1 / 4:3 / 3:4 / adaptive |
| `aigc_watermark` | bool | 否 | 是否加生成标识，默认 false |

**计费**（`/api/v1/pricing` 原文，2026-11-08 现查）：

```json
"/api/v1/apps/full_video/submit": {
  "mode": "per_second",
  "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80},
  "note": "2026-11-06 站主定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80"
}
```

15 秒 1080P = 60 x 15 = **900 点 = 9 元**；30 秒品牌片拆 15 + 15 两段提交 = **1,800 点 = 18 元**，在本机用 ffmpeg 拼。

**限制**：首帧 / 尾帧各最多 1 张；参考图最多 9 张；参考视频与参考音频各最多 3 个；首尾帧模式与参考媒体模式不混用；768P 及以上文本上限 5,000 字符。

---

## 四、`seedance` 的 7 个接口（2026-11-08 `GET /api/v1/apps` 现查）

```
createGroup   POST  id=29  创建素材资产组合
createAsset   POST  id=30  上传素材
getAsset      POST  id=31  查素材状态
updateAsset   POST  id=32  更新素材
deleteAsset   POST  id=33  删除素材
query         GET   id=34  查任务
create        POST  id=35  创建视频任务
```

### 4.1 `create`（JSON，唯一出片口）

```
POST /api/v1/apps/seedance/create
```

| 字段 | 说明 |
|---|---|
| `model` | `seedance-2-text-2-video` / `seedance-2-video-2-video` / `seedance-2-fast-text-2-video` / `seedance-2-fast-video-2-video` |
| `content[]` | `{type, text|image_url|video_url|audio_url, role}`，图片 ≤9、视频 ≤3、音频 ≤3 |
| `duration` | 4~15 秒，或 −1 由模型决定 |
| `resolution` | `480p` / `720p` / `1080p`（默认 720p） |
| `ratio` | `16:9` / `4:3` / `1:1` / `3:4` / `9:16` / `21:9` / `adaptive` |
| `generate_audio` | 是否生成与画面同步的音频 |

**计费**：价目表 `/api/v1/apps/seedance/create` 与 `/api/v1/apps/seedance/*` 都是 `mode=flat, cost=11000`，即 **11,000 点/次 = 110 元**，与时长、分辨率无关。

### 4.2 素材管理 5 个（全部 `multipart/form-data`）

| 接口 | 必填字段 | 说明 |
|---|---|---|
| `createGroup` | `Name`（≤64） | 可选 `GroupType=AIGC`、`Description`（≤300）、`ProjectName`（默认 default） |
| `createAsset` | `URL` / `GroupId` / `AssetType` | `AssetType` 取 `Image` / `Video` / `Audio`；上游异步拉取入库 |
| `getAsset` | `Id` | `Result.Status`：`Active`（可用）/ `Processing` / `Failed` |
| `updateAsset` | `Id` | 可选 `Name` |
| `deleteAsset` | `Id` | — |

素材入库后可在 `create` 的 `content` 里用 `asset://<ASSET_ID>` 引用。

**计费口径**：官方文档标「免费」，站内价目表 `/api/v1/apps/seedance/*` 是 flat 11,000 点/次。本包按 **11,000 点/次**保守估算并卡在 `--budget` 后面，本轮没有发过这类请求。

### 4.3 `query`：本包不直接打

```
/api/v1/apps/seedance/query  → 命中 /api/v1/apps/seedance/*  →  11,000 点/次
```

所以 `--action query` 直接转成 `GET /api/v1/tasks/<task_id>`（cost:0），一次 0 点。

---

## 五、`POST /api/v1/apps/voice_tts/tts` · 多语言配音（同步）

```json
{"text": "今日公测，登录领限定角色", "model": "s2-pro", "format": "mp3"}
```

| 字段 | 说明 |
|---|---|
| `text` | 必填；同步接口建议 500 字内，长文走 `tts_async` |
| `model` | `s1` / `s2-pro`，默认 `s2-pro` |
| `format` | mp3 / wav / ogg / opus / pcm |
| `reference_id` | 克隆音色 ID，可选 |

返回 `data.audio_url`。

实测基准：`tts_live` 33 字上游 1.98 点 → 我方 5.94 点，所以本包按 **0.18 点/字**估，实际以 `usage.points_cost` 为准。

---

## 六、`POST /api/v1/apps/media_services_33/music_generate` · 宣发配乐（异步）

必填 `model` / `custom_mode` / `instrumental`；`prompt`、`style`、`title`、`duration`、`negative_tags` 等可选。

```json
{"model": "V6", "custom_mode": false, "instrumental": true,
 "prompt": "史诗管弦，鼓点推进，适合 30 秒游戏宣发片"}
```

`media_services_33` 在架 **29 个接口**（`/api/v1/apps` 2026-11-08 现查），配乐取 `music_generate`；
同一应用下还有 28 条：`music_extend`、`music_sounds`、`music_mashup`、`music_generate_lyrics`、
`music_separate_vocals`、`elevenlabs_text_to_speech_multilingual_v2`、`google_gemini_2_5_pro_tts` 等，
需要多语种人声或音效时按需取（计价同样落通配）。

---

## 七、`GET /api/v1/tasks/<task_id>` · 查进度（免费）

```bash
curl -H "Authorization: Bearer $A7W_API_KEY" \
  https://api.a7w.cn/api/v1/tasks/tsk_xxxxxxxx
```

- 任务不存在时：HTTP 200 + `{"code":0,"msg":"任务不存在"}`，**0 点**。
- 真任务：HTTP 200 + `data` 里有 `task_id` / `model` / `status` / `result` / `usage` / `completed_at`。
- `status` 实测见过 `completed` / `failed` / `processing` / `SUCCESS`（大小写都出现过，本包统一 `lower`）。
- 价目表里 `/api/v1/tasks` 是 `per_module`，**只在请求体带非空 `module_codes[]` 时**按 50 点 x 模块数；本包只发 GET，不触发。

---

## 八、`POST /api/v1/upload` · 换白名单地址（免费）

`multipart/form-data`，字段名 **`file`**。价目表 `"/api/v1/upload": {"mode":"flat","cost":0}`，
note 原文「上传不计费（2026-10-04 站主批准）。上传是生成的前置动作、不是可计费服务」。

返回 `data.url`，形如 `https://oss.gpu.likeadmin.cn/openapi/…`，约 24 小时有效。

`full_video` 对首帧 / 参考图做域名白名单校验，实测报错原文：

```
400 url_not_allowed
"videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
 或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）"
```

| 放行 | 判定 |
|---|---|
| `vr.a7w.cn` / `*.a7w.cn` | 本站 |
| `cdn2.jiujiushuyuan.cn/vr/…` | 本站七牛 |
| `oss.gpu.likeadmin.cn/openapi/…` | 本站上传接口 |

---

## 九、尺寸校验（`qc` 与 `img` 共用的四条）

| 规则 | 说明 |
|---|---|
| 长短边 ≤ 3:1 | 9:16 = 1.78、4:5 = 1.25，都过 |
| 单边 ≤ 3840 | 上架尺寸 1920 是后期放大，不占生成预算 |
| 总像素 655,360~8,294,400 | 800x800 只有 640,000，低于下限，所以 1:1 请求 1024x1024 |

平台与尺寸的对应关系（`qc` 的「尺寸与平台」一项就按这张表验）：

| 平台 | 可用尺寸 |
|---|---|
| `taptap` | 9x16 / 3x4 |
| `bilibili` | 16x9 / 3x4 / 1x1 |
| `douyin` | 9x16 / 1x1 |
| `steam` | 16x9 / 1x1 |
| `wechat` | 9x16 / 1x1 |

---

## 十、探针禁区（2026-11-07 实测，472 点换来的）

| 端点 | 行为 | 本包做法 |
|---|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配计价，**即时结算、不退**（dressing_diffusion 200、nano_banana 72） | 一次都不打 |
| `POST /api/v1/apps/<app>/query` | 每查一次按该应用单价计费（seedance/query 11,000 点/次） | 只走 `GET /tasks/<id>` |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结，再校验失败 refund（净额 0，钱包被短暂动过） | 必填在本地卡死，缺了退 2 |

**完全安全、`doctor` 只用这些**：

```
GET  /api/v1/models           GET  /api/v1/apps        GET  /api/v1/pricing
GET  /api/v1/tasks/<id>       GET  /user/balance       GET  /user/balance/logs
POST /api/v1/upload（缺 file）  POST /api/v1/images/generations {"prompt":""} → 422
POST /api/v1/video/viapi/<tier> {} → 400 empty_url
```

`doctor` 的判据：`400/422` + 参数报错 = 端点存在，停在校验层；`404` + HTML = 未注册；
`200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` = 应用层兜底话术，不可信。

---

## 十一、本轮实测记录（2026-11-08）

`doctor` 11 项全 √，9 个请求全部只读或停在参数校验层：

| # | 检查 | 实测返回 |
|---|---|---|
| 1 | Key + 余额 | HTTP 200，可用 999,997,393,482 点，冻结 0 点 |
| 2 | 4 个应用在架 | 目录 22 个应用，full_video / voice_tts / media_services_33 / seedance 都在 |
| 3 | media_services_33 接口数 | 29 个 |
| 4 | seedance 接口数 | 7 个（createGroup / createAsset / getAsset / updateAsset / deleteAsset / query / create） |
| 5 | full_video 5 档按秒价 | HTTP 200，5 档与线上一致（14 / 28 / 60 / 80 / 80） |
| 6 | 预告片 11,000 + 配乐保底 50 + upload 0 | seedance 11000 · 通配保底 50 · upload 0 |
| 7 | 出图端点 | HTTP 422 `prompt: String should have at least 1 character` |
| 8 | 视频线 | HTTP 400 `empty_url` |
| 9 | 任务查询 | HTTP 200 `任务不存在` |
| 10 | 上传口 | HTTP 200 `请使用 file 字段提交一个文件` |
| 11 | 本轮无新增流水 | 自检前后最新一笔流水一致 |

**本轮花费 = 0 点，证据**：`doctor` 在自检前后各读一次 `GET /user/balance/logs?limit=1`，
两次返回的最新一笔都是 `2026-11-07 23:54:08 · refund · +300 · refund:submit_failed:/api/v1/videos`，
时间戳、点数、reference 完全一致 —— 中间 9 个请求没有产生任何流水，冻结额 0 点。

---

## 十二、本轮没有验证的事（写清楚，别当成已验证）

1. **成功提交的返回体**。本包提取 `task_id` 的字段名是 `task_id` / `taskId` / `id` 三个都试；
   文档示例是 `data.task_id`。
2. **seedance 素材管理是否真的按 11,000 点收费**。价目表是这么写的（`/seedance/*` 通配），
   官方文档标「免费」。本包按 11,000 点做保守估算，本轮没有发过这类请求。
3. **seedance 成功任务的 `result` 里成片字段名**。本包 `status` 用扩展名扫描（`.mp4` / `.mov` /
   `.webm` / `.m4v`）+ 字段名含 `video` 两层兜底，不赌某一个键。
4. **30 秒品牌片的拼接**。两段 15 秒由本机 ffmpeg 拼，接口只出单段。
5. **多语种配音的发音质量**。五个语种走同一个 `tts` 通道，实际以试听为准，`--reference-id` 可换音色。
