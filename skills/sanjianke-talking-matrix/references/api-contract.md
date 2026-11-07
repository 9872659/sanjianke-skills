# 接口契约（实测原文 + live 定价）

本包用三个应用拼一条流水线，全程只有五个端点：

```
接口根地址   https://api.a7w.cn/api/v1
配音         POST /apps/voice_tts/tts            同步，直接回 audio_url
图片数字人   POST /apps/pic_lipsync/submit       异步，回 task_id
全驱数字人   POST /apps/image_human/submit       异步，回 task_id
上传         POST /upload                        multipart 字段名 file（0 点）
任务查询     GET  /tasks/<task_id>               0 点，唯一合法轮询线
价目         GET  /pricing                       115 条规则（裸对象，不套 code/data）
应用目录     GET  /apps                          22 个应用（cost:0，免费）
```

**三个应用都没有 `list / result / cancel / callback / status` 这些动作**，只有
`pic_lipsync` / `image_human` 的 `submit + query`、`voice_tts` 的六个接口（见下）。
应用层 `query` 本包不调用 —— 理由见第 6 节。

---

## 1. `voice_tts` · 配音（同步）

`POST /api/v1/apps/voice_tts/tts`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | string | **是** | 待合成文本，同步接口 ≤500 字 |
| `reference_id` | string | 否 | 音色模型 ID（`list_voices` 的第一列）|
| `model` | string | 否 | 合成引擎，本包默认 `s2-pro` |
| `format` | string | 否 | `mp3`（默认）/ wav / ogg / opus / pcm |
| `prosody` | object | 否 | `{speed, volume, normalize_loudness}`，本包用 `--speed` 映射 |
| `sample_rate` / `mp3_bitrate` / `temperature` | — | 否 | 见平台 schema |

返回：

```json
{"code":1,"msg":"success","data":{"audio_url":"https://…/tts_xxx.mp3","format":"mp3"}}
```

### 计费（`/pricing` 原文，规则键 `/api/v1/apps/voice_tts/*`）

```json
{"mode":"flat","cost":0,"markupPercent":200,
 "note":"…对外价 = 上游实际点数（usage.points_cost）× 3，单笔保底 > 0。
          实测：voice_tts/stt 上游真实 40 点 → 我方 120 点；
          tts_live 33 字上游真实 1.98 点 → 我方 5.94 点。"}
```

折算 **0.18 点/字 = 180 点/千字**。`doctor` 用 `markupPercent == 200` 这条卡自检。
`clone_voice` 是 600 点/次（上游 200 × 3），本包不自动调用。

> 另一条音频线 `media_services_33`（29 个接口：ElevenLabs / Gemini TTS / Suno 音乐）不在本包范围，
> 配音统一走 `voice_tts` —— 矩阵只需要「一段文本 → 一个音频地址」，同步接口最省事。

### 音色库 `list_voices`（免费，但会冻结点数）

`GET /api/v1/apps/voice_tts/list_voices?page_number=1&page_size=100`

实测 `total = 58`。**这条"免费"接口也会走 `reserve_sync`**（先冻 150 点再全额退），
所以本包只在 `voices --yes` 与 `doctor --probe-voices` 里显式调用。

---

## 2. `pic_lipsync` · 图片数字人

`POST /api/v1/apps/pic_lipsync/submit`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `image_url` | string | **是** | 人物图片 URL（平台托管）|
| `audio_url` | string | **是** | audio 模式是驱动音频；text 模式是参考音色 |
| `mode` | string | 否 | `audio`（默认）/ `text`；本包固定 `audio` |
| `content` | string | text 模式必填 | 本包不用 text 模式（配音独立做，一次配音多个形象复用）|
| `quality` | string | 否 | `standard`（默认）/ fast / max —— **档位真名是 quality，不是 mode** |
| `model` | string | 否 | 枚举里只有 `super-lipsync-pro` |
| `prompt` | string | 否 | 人物动作、表情、画面风格 |

返回：

```json
{"code":1,"msg":"success","data":{"task_id":"task_xxx","status":"pending","frozen_points":"250"}}
```

### 计费（`/pricing` 原文，键 `/api/v1/apps/pic_lipsync/submit`）

```json
{"mode":"flat","cost":0,"markupPercent":400,"minPoints":50,
 "note":"对外 = 上游实际点数 × 5。上游不发 quality 时按 standard 3 点/秒收，
         所以成本固定 3 点/秒 ⇒ 我方 15 点/秒。cost 必须为 0。minPoints:50 目前是声明性字段。"}
```

本包按 **15 点/秒**估算，并对每条套 `max(50, 15 × 秒)` —— 短文案按 50 点兜底，不低估。

---

## 3. `image_human` · 全驱数字人

`POST /api/v1/apps/image_human/submit`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_url` | string | **是** | 人物图片 URL |
| `ref_file_url` | string | **是** | 驱动音频 URL |
| `duration` | number | 否 | 输入音频秒数；**给了它价格才被费率卡锁死** |
| `mode` | string | 否 | `fast` / `standard` / `2k` / `4k`（本包强制显式给）|
| `resolution` | string | 否 | `2k` / `4k`，`mode` 的兼容别名 |
| `prompt` | string | 否 | 画面提示词 |

### 默认档位自相矛盾（本包用必填参数堵死）

| 来源 | 字段 | 值 |
|---|---|---|
| `GET /api/v1/apps/image_human`（本包不调用，见第 6 节）| `params_schema.mode.default` | `standard` |
| `GET /api/v1/pricing` | `defaultModel` + note「缺省 mode=fast（=10）」| `fast` |

不显式传 `mode`：**出片按 standard、收钱按 fast**（15 vs 10 点/秒）。
所以 `--engine human` 把 `--mode` 做成必填，本包永不下发省略 mode 的请求。

### 计费（`/pricing` 原文，键 `/api/v1/apps/image_human/submit`）

```json
{"mode":"per_second","markupPercent":400,
 "modelRates":{"fast":{"*":10},"standard":{"*":15},"2k":{"*":30},"4k":{"*":60}},
 "defaultModel":"fast",
 "note":"快速 10 / 标准 15 / 2K 30 / 4K 60 点/输入秒（= 上游成本 2/3/6/12 ×5）"}
```

`doctor` 会把 live 的 `modelRates` 与本地这张卡逐档比对。

---

## 4. 上传

`POST /api/v1/upload`，`multipart/form-data`，字段名 **`file`**，**0 点**。

```json
{"code":1,"msg":"success","data":{"url":"https://oss.gpu.likeadmin.cn/openapi/…","name":"a.png","size":12345}}
```

上游对图片来源同样有白名单（`oss.gpu.likeadmin.cn/openapi/` 是上传接口返回的地址，
直接拿去提交最稳）。上传地址 24 小时内有效，过夜批量请重新上传。

---

## 5. 任务查询与信封

`GET /api/v1/tasks/<task_id>`，**0 点**。

```jsonc
// 存在
{"code":1,"msg":"success","data":{"task_id":"task_xxx","status":"completed",
  "result":{"video_url":"https://…/out.mp4"},"usage":{"points_cost":210}}}
// 不存在
{"code":0,"msg":"任务不存在","data":null}
```

`status` 枚举：`pending` / `processing` / `completed` / `failed` / `cancelled`。

两个形态坑（本包已处理，见 `dig_task()`）：

1. **`result` 是双重身份字段**：完成任务里也有一个 `result`，和中转包装层的 `result` 同名。
   一路往下钻会丢掉 `status`，轮询就永远等不到终态。
2. **视频地址不在固定字段**：按 `video_url` / `video_uri` / `output_url` / `result_url`
   兜底，最后再递归扫所有 http 字符串 + 视频后缀。

---

## 6. 探针禁区（2026-11-07 用 472 点买来的，本包全部绕开）

### 6.1 `GET /api/v1/apps/<app>` 会即时扣费，不退

```
19:35:08  -200  sync:/api/v1/apps/dressing_diffusion   ← 读 schema 造成，无退款
19:35:11   -72  sync:/api/v1/apps/nano_banana
```

应用参数一律从 `GET /apps`（目录，cost:0）与 `/pricing` 取，**本包不读单个 app 的 schema**。

### 6.2 应用层 `submit` 是「先预扣、后验参」

```
11:37:01Z  冻结/预扣  -250  ref=reserve_sync:/api/v1/apps/pic_lipsync/submit
11:37:02Z  退款       +250  ref=refund:sync:/api/v1/apps/pic_lipsync/submit
11:37:16Z  冻结/预扣  -250  ref=reserve_sync:/api/v1/apps/image_human/submit
11:37:19Z  退款       +250  ref=refund:sync:/api/v1/apps/image_human/submit
```

**缺必填也是先冻再退，净 0 但钱包被动过。** 所以 `doctor` 一个 submit 都不发，
端点存在性用「`GET /apps` 目录里有这八个接口」+「`/pricing` 里这三张卡都在」来证明。

### 6.3 「免费」的音色库 GET 也会 `reserve_sync`

`GET /apps/voice_tts/list_voices` 流水同样是 `reserve_sync:… → refund:…` 各 150 点。
本包把它放进 `voices --yes` 与 `doctor --probe-voices`，默认不碰。

### 6.4 应用层 `/query` 每调一次就是一次的钱

`nano_banana/query` 实测 72 点/次，历史累计在这条路上烧掉 15,552 点。
**本包代码里没有 `query` 这个字符串所在的请求路径**，轮询只走 `GET /tasks/<id>`。

### 6.5 `voice_tts` 空 body 会直接建任务

```
POST /api/v1/apps/voice_tts/tts_async  {}
→ {"code":1,"data":{"task_id":"task_…","status":"pending","frozen_points":150}}
```

它**不会**停在参数校验层，而是建任务 + 冻 150 点，随后 failed 全额退。
本包不在自检里发任何 voice_tts 的 POST。

---

## 7. 矩阵成本公式

```
配音点数 = ceil(字数 × 0.18) × 音色数              ← 只乘 M，不乘 N
单条视频 = max(50, 15 × 秒)                       ← lipsync
         = ceil(档位费率 × 秒)                     ← human
总点数   = 配音点数 + 单条视频 × 形象数 × 音色数
秒数     = ceil(字数 ÷ 4.5)                        ← 中文口播约 4.5 字/秒
```

60 字 → 14 秒，对照：

| 形象 × 音色 | 配音 | 视频 | 合计 | 元 |
|---|---|---|---|---|
| 1 × 1 | 11 | 210 | 221 | 2.21 |
| 2 × 2 | 22 | 840 | 862 | 8.62 |
| 3 × 4 | 44 | 2,520 | 2,564 | 25.64 |
| 5 × 6 | 66 | 6,300 | 6,366 | 63.66 |
| 10 × 10 | 110 | 21,000 | 21,110 | 211.10 |

---

## 8. 本轮实测记录（净花费 0 点）

基线（会话开始时抓的 `GET /user/balance/logs`）：最新一条流水 `at = 1794059270612`，
是上一轮 `list_voices` 的 `refund +150`。

```
探针    GET /user/balance · GET /apps · GET /pricing · GET /tasks/<假id>
        catalog / cost / 两道闸门 / --dry-run 全在本地，零请求
复测    GET /user/balance/logs?limit=200
        窗口 200 条 · 窗口总额 7,893 · consumePoints 74,736.09
        at > 基线的新增流水：0 条 · isSettle 新条目：0 · 支出点数：0
余额    available_points 999,997,393,482.2579 · frozen 0（前后一致）
```

`doctor` 只发四个只读 GET：`/user/balance`、`/apps`、`/pricing`、`/tasks/<假id>`。
`voices` 与 `doctor --probe-voices` 会各产生一对「冻结 150 → 退款 150」，净额 0，
默认不执行，执行时也有 `--yes` 打招呼。
