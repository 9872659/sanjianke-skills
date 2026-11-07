# 接口契约 · 播客生产线的三条接口（实测原文）

> 本文件里的返回体都是 **2026-11-07 在 api.a7w.cn 上真机跑出来的原文**。
> 每条前面标了代价：`0 点` 或「冻 60 全退」。

## 1. 三条接口，一条形态

| 项 | 值 |
|---|---|
| 应用代号 | `media_services_33`（Official 音频与辅助服务，app id 29） |
| 提交 | `POST /api/v1/apps/media_services_33/<接口code>`，`Content-Type: application/json` |
| 查询 | `GET /api/v1/tasks/<task_id>`，只读 |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 成功判据 | **HTTP 200 且 `code` ∈ {1,200}**。校验失败**也是 HTTP 200**，但 `code=0` + `data=null` |
| 本包接的 3 条 | `elevenlabs_text_to_speech_multilingual_v2`（vo）、`music_generate`（bgm）、`music_timestamped_lyrics`（subs） |

`GET /api/v1/apps` 实测该应用在架 **29 个接口**，上面三条都在列表里（2026-11-07 现查）：

```
music_generate                                 生成音乐              method=POST call_type=2
elevenlabs_text_to_speech_multilingual_v2      ElevenLabs文生语音 多语言V2  method=POST call_type=2
music_timestamped_lyrics                       获取带时间戳的歌词        method=POST call_type=2
```

## 2. 配音 · `elevenlabs_text_to_speech_multilingual_v2`

`params_schema` 原文摘录（`required: true` 两项）：

| 字段 | 类型 | 必填 | 约束 / 默认 |
|---|---|---|---|
| `text` | string | **是** | `maxLength: 5000` |
| `voice` | string | **是** | enum **67 个音色 ID**，`default: EkK5I93UQWFDigLMpZcX` |
| `speed` | number | 否 | 0.7–1.2，默认 1 |
| `style` | number | 否 | 0–1，默认 0（风格夸张度） |
| `stability` | number | 否 | 0–1，默认 0.5 |
| `similarity_boost` | number | 否 | 0–1，默认 0.75 |
| `timestamps` | boolean | 否 | 返回逐词时间戳 |
| `language_code` | string | 否 | ISO 639-1；schema 注明只有 Turbo v2.5 / Flash v2.5 支持强制语言 |
| `previous_text` / `next_text` | string | 否 | ≤5000 字，改善跨片连贯 |

67 个音色 ID 全量内置在 `scripts/run.py` 的 `VOICES`（`catalog --voices` 打印）。
播客最常用的 8 个：

```
eR40ATw9ArzDf9h3v7t7  Addison 2.0 - 澳大利亚有声书与播客
8JVbfL6oEdmuxKn5DK2C  Johnny Kid - 严肃、平静的旁白
6F5Zhi321D3Oq7v1oNT4  Hank - 低沉、引人入胜的旁白
aD6riP1btT197c6dACmy  Rachel M - 专业英国电台主持人
x70vRnQBMBu4FAYhjJbO  Nathan - 虚拟电台主持人
nPczCjzI2devNBz1zQrb  Brian - 低沉、共鸣、令人安慰
hpp4J3VqNfWAUOO0d1Us  Bella - 专业、明亮、温暖
1SM7GgM6IMuvQlz2BwM3  Mark - 随意、放松、轻快
```

每个 ID 的名字与性格描述都抄自 schema 的 `description` 原文。

**实测：空 body（冻 60 → 全退）**

```
POST /api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
body   = {}
HTTP   = 200
return = {"code":0,"msg":"input.text: 缺少必填参数","data":null}
```

## 3. 配乐 · `music_generate`

三个必填项（schema 原文）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | **是** | enum：`V4` `V4_5` `V4_5PLUS` `V4_5ALL` `V5` `V5_5` `V6` `V6_MINI` `V6_WILD`；原文「请使用 V6、V6_MINI 或 V6_WILD」 |
| `custom_mode` | boolean | **是** | `true` 精细控 / `false` 简化 |
| `instrumental` | boolean | **是** | 是否纯音乐（无人声） |

常用可选项：

| 字段 | 约束 |
|---|---|
| `style` | 风格规范，V6 系 ≤1000 字符 |
| `lyrics` | V6 ≤5000 字符；`custom_mode=true` 时优先当歌词 |
| `prompt` | 非自定义模式下是核心创意（≤3000 字符） |
| `duration` | 10–360 秒；只在 `custom_mode=true` 且 V6 系时生效 |
| `variety` | 0–4 整数，默认 1 |
| `negative_tags` | 要避开的风格 |
| `audio_weight` / `style_weight` / `weirdness_constraint` | 0–1，两位小数，仅自定义模式 |
| `vocal_gender` | `m` / `f`，仅自定义模式生效 |

schema 原文补充：非自定义模式下 `image_urls` / `video_urls` / `audio_urls` / `style` / `lyrics` 至少一项；
自定义模式下 `style` / `lyrics` / `negative_tags` 至少一项，且 `title` 必填（≤80 字符）。

**实测：空 body（冻 60 → 全退）**

```
POST /api/v1/apps/media_services_33/music_generate
body   = {}
HTTP   = 200
return = {"code":0,"msg":"input.custom_mode: 缺少必填参数；input.instrumental: 缺少必填参数；input.model: 缺少必填参数","data":null}
```

## 4. 字幕 · `music_timestamped_lyrics`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | string | **是** | 「生成音乐」或「延长音乐」返回的 task_id |
| `audio_id` | string | **是** | 该任务里某一首曲子的 audio_id（在完成回调数据里返回） |

**实测：空 body（冻 60 → 全退）**

```
POST /api/v1/apps/media_services_33/music_timestamped_lyrics
body   = {}
HTTP   = 200
return = {"code":0,"msg":"input.task_id: 缺少必填参数；input.audio_id: 缺少必填参数","data":null}
```

## 5. 查询 · `GET /api/v1/tasks/<task_id>`

**实测（假 id，0 点）**

```
GET /api/v1/tasks/sanjianke-podcast-line-probe
HTTP = 200
return = {"code":0,"msg":"任务不存在","data":null}
```

真实任务的返回结构按上游走，本包用广度遍历把 `audio_url` / `audio_id` / `title` / `duration`
和逐句时间轴 `[{start,end,text}]` 挖出来，字段名不固定也能取（`start` / `start_time` / `startTime` 都认）。

## 6. 价格口径（诚实版）

`GET /api/v1/pricing` 实测：**115 条规则**，`media_services_33` **没有专属条目**，也没有
`music_generate` / `elevenlabs_*` 的条目 —— 全部落通配 `*`：

```json
{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
 "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}
```

同一个文件里，目录类只读接口的计价是 `{"mode":"flat","cost":0,"markupPercent":0}`：

| 路径 | 计价 | 实测 |
|---|---|---|
| `GET /api/v1/apps` | `cost: 0` | 0 点（本包 `catalog` / `doctor` 用它） |
| `GET /api/v1/models` | `cost: 0` | 0 点 |
| `GET /api/v1/upload` | `cost: 0` | 0 点 |
| `POST /api/v1/apps/media_services_33/<code>` | 通配，上游 × 2、保底 50 | 先冻 60 |

### 实测流水（原文，`GET /user/balance/logs`）

三条端点各发一次空 body 探针（2026-11-07 21:23 与 21:26），每一次都是「先冻 60、立刻退 60」：

```
21:23:23  charge      -60  reserve_sync:/api/v1/apps/media_services_33/music_generate
21:23:24  refund      +60  refund:sync:/api/v1/apps/media_services_33/music_generate
21:23:25  charge      -60  reserve_sync:/api/v1/apps/media_services_33/music_timestamped_lyrics
21:23:26  refund      +60  refund:sync:/api/v1/apps/media_services_33/music_timestamped_lyrics
21:26:48  charge      -60  reserve_sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
21:26:49  refund      +60  refund:sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
```

余额前后 `available_points` 完全一致，`frozen` 一直是 0 —— **净花费 0 点**。

### 一条真实提交的完整流水（任务失败，全额退）

```
21:27:24  charge    -60    reserve_sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
21:27:25  refund    +60    refund:sync_to_task:task_3e35ff8557d71550a048af4c
21:27:25  charge    -1.2   reserve:task_3e35ff8557d71550a048af4c
21:27:26  reserve   -1.2
21:27:43  refund    +1.2   refund:task_failed:task_3e35ff8557d71550a048af4c
```

三步读法：

1. POST 先冻 60（`reserve_sync`），任务建起来后冻结转成本任务（`refund:sync_to_task`）；
2. 任务级预扣按**上游实际点数**算 —— 这条是 1 个字，预扣 **1.2 点**，不是固定 60；
3. 任务失败 → `refund:task_failed` 全额退，净 0。

`21:27:26` 那条 `reserve -1.2` 的 `balanceMoving=false`、`balanceAfter=null`，是**不动的记账影子行**；
只统计 `balanceMoving=true` 的行，这一整段净额正好 **0.0000 点**，余额始终回到 `999997393482.2579`。

所以「保底 50 点」是**结算口径**，预扣走的是上游点数换算值；**真实成交价要成功跑一条、看任务详情的 `usage`**。

## 7. 探测禁区（读比写贵）

```
GET /api/v1/apps/<app>         命中 /apps/<app>/* 通配计价，sync: 即时扣、不退
                               （2026-11-07 上一轮读 schema 实测扣了 472 点，教训在本家族 _NEW_SKILL_FAMILY_SPEC.md §7.5）
```

本包的免费命令只打**这四条**，全部 `cost: 0` 或只读：

```
GET /user/balance
GET /api/v1/apps
GET /api/v1/pricing
GET /api/v1/tasks/<任意 id>
```

三条端点的参数校验放在 `doctor --probe`（默认关）：它发 3 条空 body POST，
每条冻 60 后立刻全退，跑完自动比对余额差值，**净 0**。
