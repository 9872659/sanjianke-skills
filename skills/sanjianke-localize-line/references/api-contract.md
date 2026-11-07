# 接口契约（schema 原文 + 实测锚点）

> 本文件只记事实：哪条接口、吃什么参数、回什么结构、按什么价结算。
> 参数与枚举来自网关 `params_schema`（2026-11-07 抓取）；价格来自 `GET /api/v1/pricing` 原文；
> 流水锚点是同账号同族会话的实测记录，**不是本轮**（本轮 0 花费，见 SKILL.md 末节）。

---

## 一、端点地图

| 用途 | 方法 | 路径 | 同步/异步 | 本包用不用 |
|---|---|---|---|---|
| 转写 | POST | `/api/v1/apps/voice_tts/stt` | 同步 | ✅ `transcribe` |
| ElevenLabs 多语言 V2 | POST | `/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2` | 异步，回 `task_id` | ✅ `voice` |
| 翻译 | POST | `/api/v1/chat/completions` | 同步 | ✅ `translate` |
| 任务查询 | GET | `/api/v1/tasks/<task_id>` | 只读 | ✅ 轮询只用它 |
| 应用目录 | GET | `/api/v1/apps` | 只读，0 点 | ✅ `doctor` |
| 价目表 | GET | `/api/v1/pricing` | 只读，**裸对象套 `pricing`** | ✅ `doctor` |
| 余额 | GET | `/user/balance` | 只读 | ✅ `doctor` |
| 流水 | GET | `/user/balance/logs?limit=N` | 只读，上限 1000 | ✅ 核算花费 |
| 模型目录 | GET | `/api/v1/models` | 只读 | ✅ `doctor` |
| 上传 | POST | `/api/v1/upload` | multipart，免费 | 本包不需要 |

---

## 二、探针禁区（会把钱动掉的动作）

| 动作 | 后果 |
|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配计价，`sync:` 即时结算、失败**不退** |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结（voice_tts 150 点 / media_services_33 60 点）再退回，净 0 但钱包被短暂动过 |
| `GET /api/v1/apps/voice_tts/list_voices` | 路径级规则 `/api/v1/apps/voice_tts/*` 与方法无关，同样 `reserve_sync` 150 点 |
| 应用层 `/query` 轮询 | **一次轮询就是一次的钱**（历史 nano_banana/query 72 点/次） |
| `videoUrl` 传外站地址 | `400 url_not_allowed`，白名单只认本站与 `/api/v1/upload` 返回的 `oss.gpu.likeadmin.cn` 地址 |

本包 `doctor` 因此**一个 POST 都不发**，5 条都是只读 GET。

---

## 三、转写 · `voice_tts/stt`

### 3.1 参数（schema 原文）

```json
{
  "language":          {"type": "string",  "required": false,
                        "description": "识别语言，不传自动检测"},
  "audio_url":         {"type": "string",  "required": false,
                        "description": "音频地址（与文件上传二选一）"},
  "ignore_timestamps": {"type": "boolean", "required": false,
                        "description": "是否忽略精确时间戳，默认 true"}
}
```

- **本地文件走 multipart，字段名 `audio`**（本包 `transcribe --input` 就是这么发的）。
- 要做字幕必须显式 `ignore_timestamps=false`；默认 `true` 会把时间戳丢掉。

### 3.2 返回（同族实测，2026-11-07）

```json
{"code": 1, "msg": "success", "data": {
  "text": "全文，带标点",
  "language_code": "zh",
  "duration": 123.4,
  "segments": [{"start": 0.0, "end": 0.18, "text": "你"}, …],
  "usage": {"points_cost": 40}
}}
```

- `result.segments` 是**字级**条目（一字一条），**不带标点**；标点只出现在 `result.text`。
- 计费 **120 点/次**（上游 40 点 x 3；`usage.points_cost` 是上游点数）。
- 预扣 **150 点/次**，失败全额退。

---

## 四、配音 · `elevenlabs_text_to_speech_multilingual_v2`

### 4.1 参数（schema 原文）

| 字段 | 类型 | 必填 | 约束 / 默认 | 说明 |
|---|---|---|---|---|
| `text` | string | **是** | `maxLength 5000` | 要转成语音的文本 |
| `voice` | string | **是** | enum 67 个，默认 `EkK5I93UQWFDigLMpZcX` | 音色 **ID** |
| `speed` | number | 否 | 0.7–1.2，默认 1 | 语速 |
| `style` | number | 否 | 0–1，默认 0 | 风格夸张程度 |
| `stability` | number | 否 | 0–1，默认 0.5 | 稳定性 |
| `similarity_boost` | number | 否 | 0–1，默认 0.75 | 相似度 |
| `timestamps` | boolean | 否 | 默认 false | 返回逐词时间戳 |
| `language_code` | string | 否 | ISO 639-1 | 见 4.2 |
| `previous_text` | string | 否 | `maxLength 5000` | 上一段，跨段连贯 |
| `next_text` | string | 否 | `maxLength 5000` | 下一段，跨段连贯 |

### 4.2 `language_code` 的原文警告

> 「语言代码（ISO 639-1），用于为模型强制指定语言。目前只有 Turbo v2.5 和 Flash v2.5
> 支持语言强制。**对于其他模型，如果提供了语言代码，将返回错误。**（最大长度：500 个字符）」

本包 `voice` 走的就是 m2 档，所以**不传 `language_code`**：配音语言由翻译稿本身决定。
真要强制语言，换成 `elevenlabs_text_to_speech_turbo_2_5`（同形参、同 67 音色）。

### 4.3 返回与计费

- 异步：`{"code":1,"msg":"success","data":{"task_id":"task_…","status":"pending"}}`。
- 轮询 `GET /api/v1/tasks/<task_id>`（免费），完成态 `status=completed`，音频地址在
  `result` 里（本包的解析器对 `audio_url` / `audioUrl` / `url` / `result.*` 递归兜底）。
- 计费：通配规则「上游实际点数 x 2、单笔保底 50 点」，**实测每次预扣 60 点**。

### 4.4 67 个音色（`voice.enum` 原文顺序）

| ID | 名字 | 特点 |
|---|---|---|
| EkK5I93UQWFDigLMpZcX | James | 沙哑、引人入胜、大胆（默认） |
| Z3R5wn05IrDiVCyEkUrK | Arabella | 神秘、富有情感 |
| NNl6r8mD7vthiJatiJt1 | Bradford | 富有表现力、口齿清晰 |
| YOq2y2Up4RgXP2HyXjE5 | Xavier | 霸气、金属感播音员 |
| B8gJV1IhpuegLxdpXFOE | Kuon | 开朗、清晰、稳定 |
| 2zRM7PkgwBPiau2jvVXc | Monika Sogam | 低沉、自然 |
| 1SM7GgM6IMuvQlz2BwM3 | Mark | 随意、放松、轻快 |
| 5l5f8iK3YPeGga21rQIX | Adeline | 女性化、对话式 |
| scOwDtmlUjD3prqpp97I | Sam | 客服代理 |
| NOpBlnGInO9m6vDvFkFC | Spuds Oxley | 睿智、平易近人 |
| BZgkqPqms7Kj9ulSkVzn | Eve | 真实、充满活力、快乐 |
| wo6udizrrtpIxWGp2qJk | Northern Terry | 北方口音 |
| gU0LNdkMOQCOrPrwtbee | British Football Announcer | 英国足球解说员 |
| DGzg6RaUqxGRTHSBjfgF | Brock | 威严、大声的军士 |
| x70vRnQBMBu4FAYhjJbO | Nathan | 虚拟电台主持人 |
| Sm1seazb4gs7RSlUVw7c | Anika | 活泼、友好、引人入胜 |
| P1bg08DkjqiVEzOn76yG | Viraj | 丰富、柔和 |
| qDuRKMlYmrm8trt5QyBn | Taksh | 平静、严肃、流畅 |
| qXpMhyvQqiRxWQs4qSSB | Horatius | 充满活力的角色配音 |
| TX3LPaxmHKxFdv7VOQHJ | Liam | 充满活力、社交媒体创作者 |
| N2lVS1w4EtoT3dr4eOWO | Callum | 沙哑的骗子 |
| FGY2WhTYpPnrIDTdsKH5 | Laura | 热情、古怪的态度 |
| kPzsL2i3teMYv0FxEYQ6 | Brittney | 社交媒体语音：有趣、年轻、信息丰富 |
| UgBBYS2sOqTuMpoF3BR0 | Mark 2 | 自然对话 |
| hpp4J3VqNfWAUOO0d1Us | Bella | 专业、明亮、温暖 |
| nPczCjzI2devNBz1zQrb | Brian | 低沉、共鸣、令人安慰 |
| uYXf8XasLslADfZ2MB4u | Hope | 活泼、八卦、少女感 |
| gs0tAILXbY5DNrJrsM6F | Jeff | 优雅、共鸣、强劲 |
| DTKMou8ccj1ZaWGBiotd | Jamahal | 年轻、充满活力、自然 |
| vBKc2FfBKJfcZNyEt1n6 | Finn | 年轻、热切、充满活力 |
| DYkrAHD8iwork3YSUBbs | Tom | 对话与书籍 |
| 56AoDkrOh6qfVPDXZ7Pt | Cassidy | 清脆、直接、清晰 |
| eR40ATw9ArzDf9h3v7t7 | Addison 2.0 | 澳大利亚有声书与播客 |
| g6xIsTj2HwM6VR4iXFCw | Jessica Anne Bogart | 健谈、友好 |
| lcMyyd2HUfFzxdCaC4Ta | Lucy | 清新、随意 |
| 6aDn1KB0hjpdcocrUkmq | Tiffany | 自然、热情 |
| Sq93GQT4X1lKDXsQcixO | Felix | 温暖、积极、现代 RP |
| flHkNRp1BlvT73UL6gyz | Jessica Anne Bogart 2 | 雄辩的反派 |
| 9yzdeviXkFddZ4Oz8Mok | Lutz | 咯咯笑、欢快 |
| pPdl9cQBQq4p6mRkZy2Z | Emma | 可爱、积极向上 |
| zYcjlYFOd3taleS0gkk3 | Edward | 大声、自信、自负 |
| nzeAacJi50IvxcyDnMXa | Marshal | 友好、幽默的教授 |
| ruirxsoakN0GWmGNIo04 | John Morgan | 粗犷、坚韧的牛仔 |
| TC0Zp7WVFzhA8zpTlRqV | Aria | 性感反派 |
| ljo9gAlSqKOvF6D8sOsX | Viking Bjorn | 史诗中世纪掠夺者 |
| PPzYpIqttlTYA83688JI | Pirate Marshal | 海盗元帅 |
| 8JVbfL6oEdmuxKn5DK2C | Johnny Kid | 严肃、平静的旁白 |
| iCrDUkL56s3C8sCRl7wb | Hope 2 | 诗意、浪漫、迷人 |
| wJqPPQ618aTW29mptyoc | Ana Rita | 流畅、富有表现力、明亮 |
| EiNlNiXeDU1pqqOPrYMO | John Doe | 低沉 |
| 4YYIPFl9wE5c4L2eu2Gb | Burt Reynolds | 低沉、流畅、清晰 |
| 6F5Zhi321D3Oq7v1oNT4 | Hank | 低沉、引人入胜的旁白 |
| YXpFCvM1S3JbWEJhoskW | Wyatt | 睿智乡村牛仔 |
| LG95yZDEHg6fCZdQjLqj | Phil | 爆发力、热情播音员 |
| CeNX9CMwmxDxUF5Q2Inm | Johnny Dynamite | 复古电台 DJ |
| aD6riP1btT197c6dACmy | Rachel M | 专业英国电台主持人 |
| mtrellq69YZsNwzUSyXh | Rex Thunder | 低沉强硬 |
| dHd5gvgSOzSfduK4CvEg | Ed | 深夜播音员 |
| eVItLK1UvXctxuaRV2Oq | Jean | 迷人、俏皮的蛇蝎美人 |
| esy0r39YPLQjOczyOib8 | Britney | 冷静、算计的反派 |
| Tsns2HvNFKfGiNjllgqo | Sven | 情感丰富、友善 |
| 1U02n4nD6AdIZ9CjF053 | Viraj 2 | 流畅、温柔 |
| AeRdCCKzvd23BpJoofzx | Nathaniel | 引人入胜、英式、平静 |
| LruHrtVF6PSyGItzMNHS | Benjamin | 低沉、温暖、平静 |
| 1wGbFxmAM3Fgw63G1zZJ | Allison | 平静、舒缓、冥想 |
| hqfrgApggtO1785R4Fsn | Theodore HQ | 宁静、沉稳 |
| MJ0RnG71ty4LH3dvNfSd | Leon | 舒缓、沉稳 |

---

## 五、翻译 · `POST /api/v1/chat/completions`

- OpenAI 兼容：`Authorization: Bearer <Key>`，请求体 `model` / `messages` / `temperature` / `max_tokens`。
- 默认模型 `deepseek-chat`，用 `GET /api/v1/models` 现查（实测 316 个）。
- **成功响应不带 `code` 字段**，就是标准 OpenAI 形态（`id` / `choices` / `usage`）；
  `code==1` 那套信封只用于生成应用，本包按 `choices` 判成败。
- 计费：平台不公布点数；`usage` 只有 `prompt_tokens` / `completion_tokens` / `total_tokens`。
  本包只报 token，不编金额。字符 -> token 标定（同族实测）：入 1 token 约 1.61 字、
  出 1 字约 1.11 token。

---

## 六、价格（`GET /api/v1/pricing` 原文）

响应是**裸对象**，规则在 `pricing` 键下，共 115 条：

```json
"/api/v1/apps/voice_tts/*": {
  "mode": "flat", "cost": 0, "markupPercent": 200,
  "note": "…对外价 = 上游实际点数（响应 usage.points_cost / actual_points）× 3，
           单笔保底 > 0。实测：voice_tts/stt 上游真实 40 点 → 我方 120 点；
           tts_live 33 字上游真实 1.98 点 → 我方 5.94 点。"
}
```

```json
"*": {"mode": "flat", "cost": 0, "markupPercent": 100, "minPoints": 50,
      "note": "未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}
```

折算：

| 项 | 点数 |
|---|---|
| `voice_tts/stt` | 120 点/次（上游 40 x 3） |
| `voice_tts/tts*` | 约 0.18 点/字 = 180 点/千字（同族锚点） |
| `media_services_33/*` 配音 | 60 点/条起（上游 x 2、保底 50；实测预扣 60） |
| 字幕（本地） | 0 点 |

### 6.1 流水锚点（同账号、同族会话实测，非本轮）

```
20:50:36  charge  -60  reserve_sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
20:50:37  refund  +60  refund:sync:/api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
…
21:36:19  reserve -150 reserve (balanceMoving=false) path=/api/v1/apps/voice_tts/tts_async
         refund  +150 refund:task_failed:task_7257…
```

结论：`media_services_33/*` 先冻 60、`voice_tts/*` 先冻 150；失败全额退，净 0。

---

## 七、本包口径与边界

| 项 | 本包口径 |
|---|---|
| 转写计费 | 120 点/次，按次不按时长 |
| 配音计费 | 60 点/条起，一条 <=5000 字；成交价 = 上游实际点数 x 2 |
| 翻译计费 | 只报 token |
| 字幕 | 0 点 |
| 预算闸门 | `--budget` 单位是点（1 元 = 100 点），超了发请求前就退 `5` |
| 轮询 | 只走 `GET /api/v1/tasks/<id>`；POST 不自动重试（重试 = 再扣一次） |

**本轮零花费留下的两处未实证**：

1. `elevenlabs_..._multilingual_v2` 的**成功**返回里音频地址与 `timestamps` 的确切键名。
   本包按平台文档与同族写法实现，并对 `audio_url` / `audioUrl` / `url` / `result.*` 递归兜底；
   真跑一条时 `voice --json` 会原样打印返回。
2. `chat/completions` 的翻译质量与 token 用量随模型与文稿变化，`cost` 里的 token 数是标定估算，
   不是账单。
