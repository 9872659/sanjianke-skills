# 接口契约（官方音频与辅助服务 `media_services_33`）

> 权威来源：`GET https://api.a7w.cn/api/v1/apps`（应用目录，pricing 里 cost:0，**免费**）
> 字段契约：网关接口 schema；应用目录给出 `required` / `optional` / `model` 枚举
> 本文件每条结论都在 2026-11-07 真机验过，验完账户**净消费 0 点**

---

## 一、接入信息

| 项目 | 值 |
|---|---|
| 接口根地址 | `https://api.a7w.cn/api/v1` |
| 调用形态 | `POST /api/v1/apps/media_services_33/<接口code>`，JSON body |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 任务查询 | `GET /api/v1/tasks/<task_id>`（**只读，免费**） |
| 应用代号 | `media_services_33`，名称「Official 音频与辅助服务」，驱动 `official` |
| 接口总数 | **29 个**；本包接其中 4 个（配乐线），其余 25 个是 Gemini TTS / ElevenLabs 语音与翻唱类 |

`GET /api/v1/apps` 实测返回 22 个应用、本应用 29 个接口，**不返回 params_schema**，
所以本包的必填项与 `model` 枚举来自 schema 原文，再由 `catalog` 与在线接口码对齐。

---

## 二、本包接的 4 个接口

### 1. `music_generate` 生成音乐

| 参数 | 必填 | 说明 |
|---|---|---|
| `model` | **是** | 枚举见下 |
| `custom_mode` | **是** | `true` 自定义（自己给风格/歌词），`false` 灵感模式（给一句话） |
| `instrumental` | **是** | `true` 纯音乐；配乐线默认 `true` |
| `style` | 否 | 风格标签（自定义模式下才是风格） |
| `title` | 否 | 标题，≤80 字符；自定义模式下建议给 |
| `lyrics` | 否 | 歌词 |
| `prompt` | 否 | 一句话描述（灵感模式用） |
| `duration` | 否 | **10-360 秒**，只在自定义模式 + V6 系生效 |
| `variety` | 否 | 多样性 0-4 |
| `negative_tags` | 否 | 要避开的风格 |
| `vocal_gender` | 否 | `m` / `f` |
| `persona_id` | 否 | 套用某个 Persona |
| `style_weight` | 否 | 风格遵循强度 0-1 |
| `weirdness_constraint` | 否 | 创意偏离 0-1 |
| `audio_urls` / `image_urls` / `video_urls` / `audio_weight` / `persona_model` | 否 | 参考素材（配乐线不用） |

**`duration` 的生效条件（本包据此做本地校验）**：`custom_mode=true` **且** `model ∈ {V6, V6_MINI, V6_WILD}`。

### 2. `music_extend` 延长音乐

| 参数 | 必填 | 说明 |
|---|---|---|
| `model` | **是** | 同上 9 档 |
| `audio_id` | **是** | 上一段返回的 `audio_id` |
| `continue_at` | 否 | 从原曲第几秒接下去，> 0 |
| `instrumental` | 否 | 续写纯音乐 |
| `style` / `title` / `lyrics` / `prompt` / `variety` / `persona_id` / `negative_tags` / `vocal_gender` / `style_weight` / `weirdness_constraint` / `audio_weight` / `persona_model` | 否 | 同上 |

### 3. `music_sounds` 生成声音（环境音 / 音效）

| 参数 | 必填 | 说明 |
|---|---|---|
| `model` | **是** | 只收 5 档：`V5` / `V5_5` / `V6` / `V6_MINI` / `V6_WILD` |
| `prompt` | **是** | ≤500 字符 |
| `sound_key` | 否 | 调性，默认 `Any`；可选 `C`…`B`、`Cm`…`Bm` 共 25 值 |
| `sound_tempo` | 否 | **schema 标「默认 Auto」，实际按类型校验** |
| `sound_loop` | 否 | 可循环 |
| `grab_lyrics` | 否 | 顺手抓歌词 |

> `input.sound_tempo: 类型不正确`。所以本包**总是显式传** `sound_tempo`（默认 120）。

### 4. `music_timestamped_lyrics` 获取带时间戳的歌词

| 参数 | 必填 |
|---|---|
| `task_id` | **是** |
| `audio_id` | **是** |

---

## 三、`model` 枚举

| 接口 | 枚举 |
|---|---|
| `music_generate` / `music_extend` | `V4` `V4_5` `V4_5PLUS` `V4_5ALL` `V5` `V5_5` `V6` `V6_MINI` `V6_WILD`（9 档） |
| `music_sounds` | `V5` `V5_5` `V6` `V6_MINI` `V6_WILD`（5 档） |

官方建议用 `V6` 系（`V6` / `V6_MINI` / `V6_WILD`），其余为历史版本。本包默认 `V6`。

---

## 四、返回结构

```json
{"code": 1, "msg": "success", "data": {"task_id": "task_xxx", "status": "processing"}}
```

- **成功判据是 `code`**：`1` / `200` 为成功，`0` 为校验失败或业务拒绝
- **校验失败也是 HTTP 200**，只是 `code=0`、`data=null`、`msg` 里写清哪几个参数缺
- 提交成功后到 `GET /api/v1/tasks/<task_id>` 取结果，`data` 里会有 `status`、音频 `audio_url`、`audio_id`、`duration`

任务状态：`processing` → `completed` / `failed`。

---

## 五、价格

`GET /api/v1/pricing` 顶层（实测原文）：

```json
 "pricing": {
         "note":"应用目录只读，不计费（2026-10-04 起 server.js 无计价分支）"},
   "/api/v1/apps/music_generation/*": {…}
 }}
```

**关键点**：

2. **没有 `media_services_33` 的专属规则**，所以整个应用落通配。
3. `minPoints` 写 50，但**实测每笔冻结 60 点**（= 上游 30 点 x 2），所以 50 只是理论保底。
4. 另一个应用 `music_generation`（Suno 老应用）**有**专属规则，两条线别混。

本包 `cost` 因此给的是**下限**：`max(50, 上游 x 2)`，默认 `upstream=30` → 60 点/次。

---

## 六、探针结论（2026-11-07 实测）

| 请求 | 结果 | 是否动钱包 |
|---|---|---|
| `GET /api/v1/models` | 200，`object=list`，316 条；**不含 `media_services_33`** | 否 |
| `GET /api/v1/apps` | 200，22 个应用 + 每个应用的接口码 | 否（pricing 里 `cost:0`） |
| `GET /api/v1/pricing` | 200，裸对象，不套 `code/data` | 否 |
| `GET /api/v1/tasks/<假 id>` | 200 `{"code":0,"msg":"任务不存在","data":null}` | 否 |
| `GET /api/v1/user/balance` | 200，`available_points` / `frozen` / `yuan` / `rate` | 否 |
| `GET /api/v1/me/billing` | 200，`balance` / `netConsumedPoints` / `rechargePoints` / `check` | 否 |
| `GET /user/usage` | 200，30 天 `calls` / `chargedPoints` / `refundedPoints` / `netPoints` / `byPath` | 否 |
| `GET /api/v1/user/balance/logs` | 200，**返回的是余额对象，不是流水** | 否 |
| `GET /api/v1/user/usage` / `/user/logs` / `/user/bills` | **403** `upstream_account_scope_blocked` | 否 |
| `POST …/music_generate {}` | 200 `code:0`，缺 custom_mode / instrumental / model | **冻结 60 点再全额退** |
| `POST …/music_extend {}` | 200 `code:0`，缺 audio_id / model | **冻结 60 点再全额退** |
| `POST …/music_sounds {}` | 200 `code:0`，缺 prompt / model + `sound_tempo` 类型不正确 | **冻结 60 点再全额退** |
| `POST …/music_timestamped_lyrics {}` | 200 `code:0`，缺 task_id / audio_id | **冻结 60 点再全额退** |

### 三条必须记住的结论

1. **空 body 也会冻结**：`reserve_sync` 发生在参数校验之前，一次空 body 提交 = 流水 `+60 / -60`，
   净 0、余额不动、**调用数 +1**。所以「缺参数停在扣费之前」这个说法在应用层路由上不成立。
2. **`GET /api/v1/apps/<app>` 别碰**：它命中 `/apps/<app>/*` 的通配计价，按该应用单价**直接扣、不退**
   （实测流水：`dressing_diffusion` 200 点/次、`nano_banana` 72 点/次，都没退）。
   要看接口码就查 `GET /api/v1/apps` 列表。
3. **应用层 `/query` 按次计费**：轮询只走 `GET /api/v1/tasks/<task_id>`，这条免费。

---

## 七、本包实测记录

```
2026-11-07  media_services_33 契约核对
  应用        id 29  driver=official  接口 29 个
  pricing     无专属规则，落通配 x2 / minPoints 50
  4 个接口    全部在架，返回 code:1/0 的判据一致
  探针        4 次空 body，每次 +60/-60，净 0
  余额        探针前后完全一致（frozen 0）
  花费        0 点
```
