# 应用体系：21 个应用、参数读法与异步生命周期

聊天客户端解决的是「跟模型对话」。但很多时候你要的不是一段文字，而是**一个生成产物**：一张图、一段配音、一条视频、一个数字人口播。这类能力走的是另一条路 —— **应用任务**。

两句话先分清：

| | 模型网关 | 应用任务 |
|---|---|---|
| 路径 | `/api/v1/chat/completions` | `/api/v1/apps/<应用代号>/<接口代号>` |
| 入参 | `messages` 数组 | 业务参数（`text` / `image_url` / `video_url` …） |
| 返回 | `choices`，同步 | 多为 `task_id`，异步 |

**模型网关没有 `task_id`；应用任务也不吃 `messages` 数组。** 选错入口，这是最高频的一类报错。

## 一、21 个在架应用全量清单

`GET /api/v1/apps` 实测返回 **21 个应用**。以下是全量清单（应用代号 → 平台名称）：

| 应用代号 | 平台中文名 | 干什么 |
|---|---|---|
| `voice_tts` | 语音TTS | 文字转语音、音色克隆、语音转文字 |
| `music_generation` | 音乐生成 | 作曲、写词、编曲、音色克隆、混音 |
| `music_search` | 音乐搜索 | 按关键词找曲子 |
| `seedsvc` | 音色修改与AI翻唱 | 换音色、翻唱 |
| `mmaudio` | 音效生成 | 视频配声、环境音效 |
| `full_video` | 全能视频生成 | 文生视频 / 图生视频（按分辨率档位） |
| `wan` | Wan视频生成 | 万相视频生成 |
| `seedance` | Seedance | 视频生成 + 素材资产管理 |
| `grok_video` | Grok视频生成 | 视频生成 |
| `happy_horse` | Happy Horse | 视频生成 |
| `flashvsr` | 视频超分 | 视频清晰度提升 |
| `smart_clip` | 智能剪辑 | 模板化混剪、真人播报、新闻混剪 |
| `image_human` | 全驱动数字人 | 图片驱动的完整数字人 |
| `pic_lipsync` | 图片数字人 | 单图开口说话 |
| `lipsync` | 数字人对口型 | 视频对口型 |
| `dressing_diffusion` | AI换装 | 换衣服、换造型 |
| `person_replacement` | 人物替换 | 换人 |
| `action_transfer` | 动作迁移 | 把动作搬到另一个主体上 |
| `nano_banana` | nano-banana | 图像生成与编辑 |
| `watermark_removal` | 水印消除 | 去水印，另含若干平台内容解析接口 |
| `file_qa` | 文件问答 | 文档解析与基于文件的问答 |

每个应用下可用接口的完整清单：

| 应用代号 | 接口代号 |
|---|---|
| `person_replacement` | `submit`、`query` |
| `action_transfer` | `submit`、`query` |
| `full_video` | `submit`、`query` |
| `pic_lipsync` | `submit`、`query` |
| `happy_horse` | `submit`、`create`、`query` |
| `file_qa` | `chat`、`parse` |
| `music_search` | `search` |
| `grok_video` | `submit`、`query` |
| `nano_banana` | `submit`、`query` |
| `music_generation` | `create`、`query`、`upload_audio`、`lyrics`、`vox`、`style`、`midi`、`timing`、`mp4`、`wav`、`voice_clone`、`persona`、`mashup_lyrics` |
| `smart_clip` | `template`、`template_detail`、`realman_broadcast`、`broadcast_mixcut`、`news_mixcut` |
| `image_human` | `submit`、`query` |
| `wan` | `create`、`query` |
| `seedance` | `create`、`query`、`createGroup`、`createAsset`、`getAsset`、`updateAsset`、`deleteAsset` |
| `lipsync` | `submit`、`query` |
| `dressing_diffusion` | `submit`、`query` |
| `mmaudio` | `submit`、`query` |
| `flashvsr` | `submit`、`query` |
| `seedsvc` | `submit`、`query` |
| `watermark_removal` | `remove`、`xhs_note_detail`、`xhs_user_note_list`、`douyin_user_video_list`、`xhs_user_detail`、`douyin_video_detail`、`douyin_search_video`、`xhs_search_note` |
| `voice_tts` | `tts_live`、`clone_voice`、`tts`、`tts_async`、`stt`、`list_voices` |

> **应用代号用下划线，不是连字符。** 目录名、Skill 名常见写成 `voice-tts-studio`，但 API 里的代号是 `voice_tts`。用连字符会直接 404。

`voice_tts` 的实测细节：`tts_live` 异步、`clone_voice` 同步、`tts` 同步、`tts_async` 异步、`stt` 同步、`list_voices` 是 **GET**。

> 包内 `scripts/a7w.py` 的 `call` 一律用 POST，所以 `list_voices` 不要写成 `a7w.py call` 的示例；用 `curl` 发 GET 即可。

## 二、怎么读一个应用的接口与参数

```bash
curl -sS "https://api.a7w.cn/api/v1/apps/voice_tts" -H "Authorization: Bearer $A7W_API_KEY"
```

返回里每个接口都带这几样字段，**把它们当成唯一事实来源**：

| 字段 | 含义 |
|---|---|
| `code` | **接口代号**，如 `tts`、`submit`、`create` —— 调用时用它 |
| `name` | 中文展示名（如「文字转语音（Live·异步）」）—— **不要拿它去调用** |
| `method` | HTTP 方法，`POST` 或 `GET` |
| `call_type` | `1` = 同步，`2` = 异步 |
| `endpoint_path` | 平台内部路径（**形态不统一，见 3.2，不要拿来拼 URL**） |
| `params_schema` | **参数定义**（注意不是 `schema`） |
| `tenant_fixed_points` | **你的实际按次结算价**（点数） |
| `tenant_points_per_1k_input` / `tenant_points_per_1k_output` | **你的实际按千字 / 千 token 结算价**（点数） |
| `fixed_price` / `input_price` | 公示标准价 |

**做预算一律读 `tenant_*`。** 两套价格可能差一个数量级，公示价只适合对外展示与横向比价。

## 三、三个真实存在的坑

### 3.1 `params_schema` 有两种形态

```jsonc
// 形态 A：带 properties 包装
{ "type": "object", "properties": { "text": {...}, "model": {...} }, "required": ["text"] }

// 形态 B：扁平字典
{ "text": {...}, "model": {...} }
```

**只认 `properties` 的通用解析器会把形态 B 误判成「这个接口没有参数」**，然后你就以为参数是可选的，提交上去报 400。正确做法：先找 `properties`，找不到就把除元数据键（`required` / `type` / `title` / `description` / `$schema`）之外的顶层键当作参数。

### 3.2 `endpoint_path` 的形态不统一 —— 绝对不要拿来拼 URL

实测同一个字段至少有这几种形态：

| 形态 | 例子 | 说明 |
|---|---|---|
| 另一套路由族 | `/v1/tts`、`/v1/tts/live`、`/v1/asr`、`/model` | 不在 `apps/<应用>` 之下 |
| 相对路径 | `/flashvsr/submit`、`/seedsvc/submit` | 需要自己拼前缀 |
| 绝对路径 | `/api/v1/apps/grok_video/submit` | 再拼一次就重复了 |
| 带占位符 | `/v1/tasks/{task_id}` | 路径里含变量 |

**而真正能打通的方式只有一个**：

```
POST https://api.a7w.cn/api/v1/apps/<应用代号>/<接口代号>
```

两个代号都取自线上返回的 `code` 字段，与 `endpoint_path` 无关。

> **`endpoint_path` 当参考信息看，不要当 URL 用。** 有些应用的 `endpoint_path` 指的是平台内部另一套路由，照抄拼出来的地址打不通。

### 3.3 接口代号是 `code`，不是 `name`

接口代码实测都是 `tts`、`submit`、`query`、`create`、`remove`、`search` 这类简单单词，没有占位符。

真正会出错的是**拿 `name`（中文展示名）去调用** —— 那一定失败。看到「应用或 API 不可用」时，第一个要检查的就是这一点。

## 四、提交任务

### 方式一：curl

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/voice_tts/tts" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，这是一段试听"}'
```

### 方式二：包内零依赖客户端

```bash
# 先看参数与真实价
python3 scripts/a7w.py schema voice_tts

# 再提交
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好，这是一段试听"}'
```

`--body` 传请求体 JSON（旧文档里的 `--json` 是它的别名，两者等价）。异步接口 `call` 会**自动轮询到终态**（间隔 5 秒，上限 30 分钟），也可以加 `--no-wait` 只提交、加 `--out 文件` 把产物下载下来。

**响应外壳固定是 `code` / `msg` / `data`**：

```json
{ "code": 1, "msg": "success",
  "data": { "task_id": "tsk_xxx", "status": "pending", "created_at": 1740000000 } }
```

> **业务成功码是 `code == 1`**（`{"code":1,"msg":"success"}`）。`code == 0` 是失败，**但 HTTP 状态码仍可能是 200**。
>
> 所以：**不要只看 HTTP 状态码判断成败，务必检查 `code`。**

**如果 `data` 里没有 `task_id`，说明这是个同步接口**，结果已经在 `data` 里了。

## 五、异步生命周期

```
提交 → pending → processing → completed
                        └──→ failed / cancelled
```

轮询：

```bash
curl -sS "https://api.a7w.cn/api/v1/tasks/<task_id>" -H "Authorization: Bearer $A7W_API_KEY"
# 或
python3 scripts/a7w.py task tsk_xxxxxxxx
```

任务详情里关注四个字段：

| 字段 | 说明 |
|---|---|
| `status` | `pending` / `processing` / `completed` / `failed` / `cancelled` |
| `result` | 产物。视频常见 `result.data.videoUrl`，音频常见音频 URL |
| `usage` | 用量明细 |
| `actual_points` | **本次结算点数**（任务列表里的真实字段名） |
| `error` | 失败原因，通常在 `error.message` |

实测任务条目的字段为：`task_id`、`model_code`、`channel_code`、`type_code`、`call_type`、`status`、`actual_points`、`response_time_ms`、`completed_at`、`created_at`。其中 `model_code` 对应用任务形如 `voice_tts/tts`（应用代号/接口代号），对模型调用则是模型名。

**查询任务状态是免费的**，可以放心轮询。

## 六、幂等：提交即预冻结点数

> **异步任务在提交时就预冻结点数。** 网络超时、进程被杀、你以为失败了 —— 都可能只是「响应没收到」，而任务已经创建并冻结了点数。
>
> **规则：提交前先落盘记录意图（应用 + 接口 + 关键参数 + 时间），超时后先按 `task_id` 或任务列表确认，再决定是否重提。同一个任务重复提交会重复计费。**

落盘建议只记三样：`task_id`（拿到后立刻写）、提交时间、关键参数摘要。重提之前，先 `GET /api/v1/tasks/<task_id>` 看状态 —— 这一步免费。

## 七、回调：替代轮询

提交时带上 `callback_url` 就可以不轮询：

```json
{ "text": "你好世界", "callback_url": "https://your-domain.com/a7w/hook" }
```

任务完成后平台向该地址 **POST** JSON：

```json
{ "task_id": "tsk_xxx", "status": "completed", "result": { } }
```

接入的四条要求：

1. 你的接口**必须返回 2xx** 才算接收成功。
2. 非 2xx 会触发重试，次数在**用户中心 → 回调配置**里设置，范围 **1–10 次**。
3. 回调是「至少一次」语义 → **消费端必须按 `task_id` 幂等**，否则重试会让你重复登记同一笔产物。
4. 回调地址要**公网可达**，内网地址收不到。

> 轮询和回调二选一即可。任务少用轮询更简单；任务多用回调更省连接。

## 八、结果转存到对象存储

任务产物（图片 / 视频 / 音频）可以落到你自己的存储，避免链接过期。

在**用户中心 → 结果转存**里配置 `provider / bucket / accessKey / secretKey / region / domain`，支持七牛、阿里云 OSS、腾讯云 COS；调用时在请求体里传一个 `storage` 对象即可。

> 转存凭证同样是密钥，不要写进代码、不要提交进版本库。

## 九、一个端到端例子

目标：给一段文案配音，并把音频落到本地。

```bash
export A7W_API_KEY=sk-你的key

# 1) 先看接口、参数与真实结算价
python3 scripts/a7w.py schema voice_tts

# 2) 提交并等到完成，产物直接下载
python3 scripts/a7w.py call voice_tts tts \
  --body '{"text":"欢迎收听今天的节目。"}' \
  --out out.mp3
```

只提交不等结果：

```bash
python3 scripts/a7w.py call voice_tts tts --no-wait --body '{"text":"欢迎收听今天的节目。"}'
python3 scripts/a7w.py task tsk_xxxxxxxx
```

## 十、排错顺序

按这个顺序查，命中率最高：

1. **HTTP 200 但 `code:0`** → 接口或应用不可用。最常见原因：用了 `name`（中文展示名）而不是 `code`（接口代号）。
2. **HTTP 404 且响应体为空** → 应用代号拼错（是不是用了连字符？）。先拉一次 `GET /api/v1/apps` 拿真名。
3. **400 `invalid_request`** → 参数名或必填项不对。用 `schema <应用>` 对齐；注意 `params_schema` 的两种形态。
4. **402** → 先分清 `insufficient_points`（账号余额不足，去充值）与 `key_quota_exceeded`（这个 Key 的额度打满，**不用充值**）。
5. **403 `permission_denied`** → 这个 Key 没开该应用的权限，与余额无关。
6. **429 `queue_limit_exceeded`** → 并发太高。把批量提交改成有限并发（3~5 路）+ 指数退避。
7. **任务 `failed`** → 看 `error.message`；多为素材格式或内容不合规，换素材重试。

## 十一、自检清单

- [ ] 应用代号与接口代号都是从线上 `code` 字段逐字复制的
- [ ] 路径是 `/api/v1/apps/<应用代号>/<接口代号>`，没有用 `endpoint_path` 拼
- [ ] 判断成败看的是 `code == 1`，不是 HTTP 状态码
- [ ] 解析参数时 `params_schema` 的两种形态都认了
- [ ] 提交前落盘记录了 `task_id`，没有盲目重提
- [ ] 用回调的话，消费端按 `task_id` 幂等了，且会返回 2xx
- [ ] 预算按 `tenant_*` 算，不是按 `fixed_price` 算
- [ ] 批量提交做了有限并发，不是一次性全发出去
