# 接口契约（实测原文 + live 定价，2026-11-07）

三个应用共用一套平台外壳：

```
接口根地址   https://api.a7w.cn/api/v1
提交         POST /apps/{app}/{api}        JSON，返回 data.task_id
任务查询     GET  /tasks/{task_id}         只读、免费
价目         GET  /pricing?type=app_api&app_code=&api_code=
临时上传     POST /upload                  multipart 单字段 file（不计费）
余额         GET  /user/balance
流水         GET  /user/balance/logs?limit=1000   上限 1000 条
```

本包用到的三条链路：

| 环节 | 端点 |
|---|---|
| 分节配音 | `POST /api/v1/apps/voice_tts/tts_async` |
| 课件图出片 | `POST /api/v1/apps/image_human/submit` |
| 一图口播 | `POST /api/v1/apps/pic_lipsync/submit` |

---

## 1. `voice_tts/tts_async`（分节配音）

`POST /api/v1/apps/voice_tts/tts_async`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | string | **是** | 待合成文本，异步接口适合长文本（约 10000 字符内） |
| `model` | string | 否 | `s1` / `s2-pro`，默认 `s2-pro` |
| `format` | string | 否 | `wav` / `pcm` / `mp3` / `opus`，默认 `mp3` |
| `reference_id` | string | 否 | 音色模型 ID（克隆音色返回的 model_id） |
| `prosody` | object | 否 | `speed` / `volume` / `normalize_loudness` |
| `callback_url` | string | 否 | 给了就走回调，不给就用 `GET /tasks/{id}` 轮询 |
| `normalize` | boolean | 否 | 文本规范化，默认 `true` |

返回（原文）：

```json
{"code":1,"msg":"success","data":{"task_id":"tsk_xxxxxxxxxxxx",
 "status":"pending","app":"voice_tts","api":"tts_async"}}
```

**计费**：`/api/v1/pricing` 命中 `/api/v1/apps/voice_tts/*`

```json
{"mode":"flat","cost":0,"markupPercent":200,
 "note":"语音 TTS / 克隆合成 / 语音识别（2026-10-03 决策 A：语音/音频线 ×5 → ×3；
  一律按上游真实点数计费）…实测：voice_tts/stt 上游真实 40 点 → 我方 120 点；
  tts_live 33 字上游真实 1.98 点 → 我方 5.94 点。"}
```

⇒ 对外 = 上游实际点数 × 3。本包用 `0.18 点/字` 估算（33 字 → 5.94 点折出来），单笔按 6 点起。

---

## 2. `image_human/submit`（课件图出片）

`POST /api/v1/apps/image_human/submit`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `file_url` | string | **是** | — | 课件 / 讲师图 URL |
| `ref_file_url` | string | **是** | — | 驱动音频 URL；平台按该音频时长计费 |
| `duration` | number | 否 | — | 输入音频秒数；**给了它价格才被费率卡锁死** |
| `mode` | string | 否 | schema 写 `standard` | `fast` / `standard` / `2k` / `4k` |
| `resolution` | string | 否 | — | `2k` / `4k`，`mode` 的兼容别名 |
| `prompt` | string | 否 | 人物说话自然，面对镜头… | 画面提示词 |

**能力限制（平台字段原文）**：`max_reference_images = 1`、`max_reference_audios = 0`、`max_reference_videos = 0`。

### 默认档位自相矛盾（本包用必填参数堵死）

| 来源 | 字段 | 值 |
|---|---|---|
| `params_schema.mode.default` | 出片 | `standard` |
| `/api/v1/pricing` 的 `defaultModel` | 计费 | `fast` |

不显式传 `mode` 时：**出片按 standard、收钱按 fast**（15 vs 10 点/秒）。
所以本包 `slide --mode` 必填，永不下发省略 mode 的请求。

### 计费（live 定价原文，`/api/v1/apps/image_human/submit`）

```json
{"mode":"per_second","markupPercent":400,"rateFrom":"mode",
 "modelRates":{"fast":{"*":10},"standard":{"*":15},"2k":{"*":30},"4k":{"*":60}},
 "defaultModel":"fast"}
```

= 上游成本 2 / 3 / 6 / 12 点/秒 ×5。

### 实测报错原文

```json
// 只给 file_url + ref_file_url，缺 duration，且地址拉不到
{"code":0,"msg":"无法从该地址下载媒体，请确认链接可公网访问、未过期，且允许本平台服务器拉取（防盗链/OSS 权限需放行）。 详情：Could not resolve host: example.invalid; Name or service not known","data":null}
```

---

## 3. `pic_lipsync/submit`（一图口播）

`POST /api/v1/apps/pic_lipsync/submit`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `image_url` | string | **是** | — | 人物图片 URL |
| `audio_url` | string | **是** | — | `audio` 模式是驱动音频；**`text` 模式是参考音色** |
| `mode` | string | 否 | `audio` | `audio` 音频驱动 / `text` 文案驱动 |
| `content` | string | text 模式必填 | — | 图片人物用参考音色朗读的文案 |
| `quality` | string | 否 | `standard` | `standard` / `fast` / `max`（**档位真名是 quality**）|
| `model` | string | 否 | `super-lipsync-pro` | 枚举里只有这一个值 |
| `prompt` | string | 否 | — | 人物动作、表情、画面风格 |

### 实测报错原文

```json
{"code":0,"msg":"请提供 image_url","data":null}
{"code":0,"msg":"text 模式请提供 audio_url 作为参考音色","data":null}
```

第二条是本包最重要的注解：**文案驱动省掉录音，但省不掉「参考音色」**。

### 计费（live 定价原文）

```json
"/api/v1/apps/pic_lipsync/submit":{"mode":"flat","cost":0,"markupPercent":400,"minPoints":50,
 "note":"对外 = 上游实际点数 × 5；档位参数真名是 quality ⇒ 费率卡从未生效；
  10-07 实测不发 quality ⇒ 上游按 standard 3 点/秒 收 ⇒ 成本固定 3 点/秒 ⇒ ×5 = 15 点/秒。
  cost 必须为 0。minPoints:50 目前是声明性字段（通用计费不读）。"}
```

⇒ 对外 **15 点/秒**，本包 `cost`、`plan` 都按 15 点/秒估，单笔按 50 点下限预估。

---

## 4. 任务查询：只走 `GET /api/v1/tasks/{id}`

| 路径 | 形态 | 计费 | 本包 |
|---|---|---|---|
| `GET /api/v1/tasks/{task_id}` | 平台任务线 | **免费**（只读） | ✅ 唯一轮询路径 |
| `POST /api/v1/apps/{code}/query` | 应用级查询 | **每轮询一次就是一次的钱** | ⛔ 在 `http_json()` 里拦死 |

历史流水（`GET /user/balance/logs`，2026-11-03 至 11-07）：

```
sync:/api/v1/apps/nano_banana/query      108 次   -72 点/次   合计 -7,776 点
```

`status` 枚举：`pending` / `processing` / `completed` / `failed` / `cancelled`。

### 三个真会踩的形态坑

1. **`result` 是双重身份字段**：任务完成后 `data` 里也有一个 `result`，与「中转包装层」同名。无脑往下钻会丢掉 `status`。
2. **地址不在固定字段**：按 `video_url` / `video_uri` / `output_url` / `result_url` 兜，本包直接递归扫所有 http 字符串再按后缀挑。
3. **刚 `completed` 时地址偶尔是空串**（实测竞态）：本包检测到终态但没地址时，会多等两轮再认。

---

## 5. 平台信封

```jsonc
// 成功
{"code":1,"msg":"success","data":{"task_id":"task_xxx","frozen_points":"17.52"}}
// 参数 / 计费错误（HTTP 依然是 200）
{"code":0,"msg":"请提供 image_url","data":null}
// 网关错误对象
{"error":{"message":"点数余额不足","type":"insufficient_points","code":"insufficient_points"}}
```

判据：`code == 1` 且 `data` 非空才算成功；其余取 `msg` / `message` 当错误文案。

---

## 6. 本轮实测记录（净花费 0 点）

```
探针前  GET /user/balance           可用 999,997,393,482.2579 点 · 冻结 0
        GET /user/balance/logs      1000 条，最新一条 2026-11-07 13:47:50Z
探针    GET /api/v1/apps             HTTP 200，22 个应用
        GET /api/v1/pricing ×3       HTTP 200，115 条计价规则
        GET /api/v1/tasks/{假 id}    HTTP 200 「任务不存在」
        GET /api/v1/apps/voice_tts/list_voices  ← 已知会冻 150 点，本轮一次都没发
探针后  GET /user/balance/logs      条数不变、最新一条时间不变、可用点数不变
结论    本轮真实花费 0 点
```

`doctor` 的 6 项检查全部只读，脚本里没有任何 submit 调用路径。

---

## 7. 🔴 应用层 submit 是「先预扣、后验参」

`GET /user/balance/logs` 的实测流水（时间 UTC）：

```
11:37:01Z  冻结/预扣   -250  ref=reserve_sync:/api/v1/apps/pic_lipsync/submit
11:37:02Z  退款       +250  ref=refund:sync:/api/v1/apps/pic_lipsync/submit
11:37:16Z  冻结/预扣   -250  ref=reserve_sync:/api/v1/apps/image_human/submit
11:37:19Z  退款       +250  ref=refund:sync:/api/v1/apps/image_human/submit
09:01:37Z  冻结/预扣   -150  ref=reserve_sync:/api/v1/apps/voice_tts/list_voices
09:01:42Z  退款       +150  ref=refund:sync:/api/v1/apps/voice_tts/list_voices
```

**连「缺 image_url」「缺 audio_url」这种必然被校验拦下的请求，也是先扣再退。**
净额 0，但钱包被真动过 —— 所以：

1. `doctor` 只发 4 个只读 GET，端点存在性用定价表里已配价的三条规则证明；
2. 任何 submit 只出现在付费子命令里，且必须先过 `--budget` 与 `--yes` 两道闸门。
