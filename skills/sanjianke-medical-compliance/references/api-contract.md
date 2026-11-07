# 接口契约（现查价目 + 实测原文）

> 数据源：`GET https://api.a7w.cn/api/v1/pricing`（2026-11-08 现查，115 个定价键）
> 　　　　`GET https://api.a7w.cn/api/v1/apps`（22 个在架应用）
> 　　　　`GET https://api.a7w.cn/user/balance`（`rate: 100`，`currency: points`）
> 本文件每条结论都可复现：命令见文末「本轮实测记录」。

---

## 一、接入信息

| 项目 | 值 |
|---|---|
| 接口根地址 | `https://api.a7w.cn/api/v1` |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 点与元 | **1 元 = 100 点**（`/user/balance` 的 `rate` = 100） |
| 上传 | `POST /api/v1/upload`，multipart，字段名 **`file`**，`cost: 0` |
| 查任务 | `GET /api/v1/tasks/<task_id>`，`cost: 0` |

---

## 二、出图 `POST /api/v1/images/generations`

| 参数 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | `gpt-image-2.6`（用它才路由到 Images API） |
| `prompt` | 是 | 画面描述；空字符串 → **422**「String should have at least 1 character」 |
| `n` | 否 | 1–4，默认 1 |
| `size` | 否 | `auto` / `1k` / `2k` / `4k` / `宽x高`（本包默认 `1024x1536`） |

- 返回 `data[]`，每项是 `b64_json` 或 `url`，本包两种都落盘。
- **6 点/张**，与尺寸、质量、格式无关；按 `data` 里实际返回张数计费。
- 价目表里**没有** `/api/v1/images/generations` 这个键（115 个键里搜不到），
  单价来自文档 + 流水实证：`-6  sync:/api/v1/images/generations`。
- 链接约 3 小时失效，且要**原样使用**（追加查询参数 404）。

---

## 三、配音 `POST /api/v1/apps/voice_tts/tts`

| 参数 | 必填 | 说明 |
|---|---|---|
| `text` | 是 | 文稿，单条 500 字内（超了按段落拆两条） |
| `model` | 否 | `s2-pro`（本包默认）或 `s1` |
| `format` | 否 | `mp3`（默认）/ `wav` / `opus` |
| `reference_id` | 否 | 克隆音色的 `model_id`（`clone_voice` 返回） |

- 计价规则：`/api/v1/apps/voice_tts/*` → `mode: flat`、`cost: 0`、**`markupPercent: 200`**，
  即按上游真实点数 **x3**。实测 `tts_live` 33 字上游 1.98 点 → 我方 5.94 点 ≈ **0.18 点/字**。
- 响应里读 `usage.points_cost`（或 `actual_points`）拿实际点数。
- 同应用还有 `tts_async`（长文本异步）、`tts_live`（流式）、`clone_voice`、`list_voices`、`stt`。

---

## 四、图片口播 `POST /api/v1/apps/pic_lipsync/submit`

| 参数 | 必填 | 说明 |
|---|---|---|
| `mode` | 是 | `text`（文案驱动）或 `audio` |
| `model` | 是 | `super-lipsync-pro` |
| `quality` | 否 | `standard`（默认）/ `fast` / `max` |
| `content` | 是（text 模式） | 口播文案；口播由它驱动，**不用再单独出 tts** |
| `image_url` | 是 | 出镜形象，必须白名单地址（本地图先 `upload`） |
| `audio_url` | 是（text 模式） | 参考音色，白名单地址 |
| `prompt` | 否 | 人物动作提示 |

- 计价规则：`/api/v1/apps/pic_lipsync/submit` → `mode: flat`、`cost: 0`、
  **`markupPercent: 400`**（上游 x5）、**`minPoints: 50`**（声明值，通用计费不读）。
  上游 standard 档 3 点/秒 → **15 点/秒**。
- 提交后返回 `task_id`；查进度用 `GET /api/v1/tasks/<task_id>`（0 点）。
- 应用层还有 `POST /api/v1/apps/pic_lipsync/query`，与 submit 同 path 计价，本包不用它轮询。
- 输出实测约 **480x832 / 24fps**，合成 1080x1920 时再放大。

---

## 五、成片 `POST /api/v1/apps/full_video/submit`

| 参数 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | `full-video` |
| `content` | 是 | 数组：`{"type":"text","text":"…"}` + 可选 `{"type":"image_url","role":"first_frame","image_url":{"url":"…"}}` |
| `duration` | 是 | **单段 4–15 秒**；总时长按段拆 |
| `resolution` | 否 | `480P` / `768P` / `1080P` / `2K` / `4K` |
| `ratio` | 否 | `9:16` / `16:9` / `3:4` / `1:1` / `adaptive` |
| `aigc_watermark` | 否 | 本包**默认 `true`**：AI 生成标识留在画面里 |

按秒 x 分辨率计费（`mode: per_second`，`resolutionRates` 原文）：

| 档位 | 点/秒 | 元/秒 |
|---|---|---|
| 480P | 14 | 0.14 |
| 768P | 28 | 0.28 |
| 1080P | 60 | 0.60 |
| 2K | 80 | 0.80 |
| 4K | 80 | 0.80 |

---

## 六、上传 `POST /api/v1/upload`

- `Content-Type: multipart/form-data`，字段名 **`file`**，单文件 512 MB 内。
- 返回 `{"code":1,"data":{"url":"https://oss.gpu.likeadmin.cn/openapi/…","path":…,"name":…,"size":…,"mime_type":…,"type":…}}`。
- `url` 在域名白名单内，可以直接喂给 `pic_lipsync` 的 `image_url` / `audio_url`、`full_video` 的 `first_frame`。
- 缺 `file` 时返回 `200 / code 1`，`msg`：「请使用 file 字段提交一个文件」——**这不扣费**，`doctor` 用它验通路。

### 地址白名单（上游报错原文）

```
400 url_not_allowed
  "videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
   或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）"
```

本包 `url_allowed()` 在本地就拦这三类之外的主机名，不合格直接退 2，把请求省下来。

---

## 七、查任务 `GET /api/v1/tasks/<task_id>`

- 假 id → `200`，`{"code":0,"msg":"任务不存在"}`，**0 点**。
- 应用层任务（口播、成片）用这条看不到时，才考虑应用自己的 `/query`（口径说不清，需 `--yes`）。

---

## 八、探针禁区（2026-11-07 用 472 点买来的）

| 形态 | 后果 | 本包怎么绕 |
|---|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配计价，**即时扣费不退**（dressing_diffusion 200、nano_banana 72） | 只读 `GET /api/v1/apps` 列表 + `GET /api/v1/pricing` |
| `POST /api/v1/apps/<app>/submit` 缺必填 | `reserve_sync`：**先冻再验再全额退**（pic_lipsync 冻 250） | `doctor` 一条应用层 submit 都不发 |
| 应用层 `/query` 轮询 | 与 submit 同 path 计价，算不算钱说不清 | 只用 `GET /api/v1/tasks/<id>` |
| `POST /api/v1/images/generations` `{"model":…,"prompt":""}` | **422**，停在参数校验 | `doctor` 就用它验出图端点 |
| `POST /api/v1/video/viapi/<tier>` `{}` | **400 empty_url**，不建任务 | `doctor` 用 enhance 这一档 |

**判断端点是否存在的免费判据**

| 返回 | 含义 |
|---|---|
| `400` / `422` + 参数报错 | 存在，停在校验层 |
| `404` + HTML | 未注册 |
| `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，不可信 |
| `502` + `InvalidMpsUser` | 路由在，上游凭据坏了 |

---

## 九、同目录的 29 个音频接口（`media_services_33`）

医疗合规素材只在片头片尾配乐时才碰这条线，路径统一是
`POST /api/v1/apps/media_services_33/<code>`，契约见 `_media33.json`（29 项）。常用的三个：

| code | 必填 | 用途 |
|---|---|---|
| `music_generate` | `model`、`custom_mode`、`instrumental` | 生成一首配乐（Suno 线） |
| `music_generate_lyrics` | `prompt` | 只要歌词 |
| `music_sounds` | `model`、`prompt` | 音效（转场、器械声） |

- 价目：落到通配 `*` → `mode: flat`、`cost: 0`、`markupPercent: 100`（上游 x2）、**保底 50 点/笔**。
- 口播配音走 `voice_tts`（按字，约 0.18 点/字）比这条线便宜，所以 `tts` 默认走 `voice_tts`。

---

## 十、本轮实测记录（真实花费 0 点）

```
2026-11-08 02:2x  账户余额 999,997,393,470.2579 点 · 冻结 0 点
GET  /api/v1/pricing      → 200，115 个定价键
GET  /api/v1/apps         → 200，22 个应用（full_video / voice_tts / pic_lipsync 均在架）
POST /images/generations {"model":"gpt-image-2.6","prompt":""} → 422，0 点
POST /video/viapi/enhance {} → 400 empty_url，0 点
GET  /api/v1/tasks/med-compliance-probe → 200「任务不存在」，0 点
POST /api/v1/upload（无 file）→ 200「请使用 file 字段提交一个文件」，0 点
GET  /user/balance/logs?limit=1 → 最近一笔仍是
      2026-11-08 01:46:12  charge  -6  sync:/api/v1/images/generations
```

自检前后最新一笔流水**完全一致**，余额小数点后四位未变 → 本轮 0 点、0 冻结、0 建任务。
