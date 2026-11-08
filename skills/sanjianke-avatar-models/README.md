# 同一张图 + 同一段音频，5 个数字人模型先报价再出片

**10 秒口播：模型层基线 50–240 点，应用层 100–600 点，差 12 倍。**
先看价，再选型，最后才出片 —— 这就是本包和「直接跑一条」的全部差别。

## 为什么多这一步

数字人最容易花错钱的地方不是生成，是选型：同一个「图 + 音频」的需求，5 个模型层入口 + 3 条应用层路线，价差 12 倍，效果还各不相同。

控制台价目表查不到模型层单价：`GET /api/v1/pricing` 的 115 条规则里没有 `/api/v1/videos/generations`，模型层命中通配「上游实际点数 × 2、单笔保底 50 点」。真实单价只在你自己 `/api/v1/me/tasks` 的 `actualPrice` 里。

本包把这两件事都做了：**先报价**，再用同一张图、同一段音频把片子跑出来并排看。

## 8 个数字人 ID，一张表看全

| ID | 能干什么 | 输入 | 10 秒音频 |
|---|---|---|---|
| `omnihuman-2-0` | OmniHuman 2.0 数字人驱动 | 图（`image_urls` 数组）+ 音频 | 基线 50–240 点 |
| `omnihuman-1-5` | OmniHuman 1.5 数字人驱动 | 图（`image_url`）+ 音频 + 可选 mask | 基线 50–240 点 |
| `infinitalk-from-audio` | Infinitalk 音频驱动口播 | 图 + 音频 | 基线 50–240 点 |
| `kling-ai-avatar-standard` | 可灵数字人标准档 | 图 + 音频 | 基线 50–240 点 |
| `kling-ai-avatar-pro` | 可灵数字人 Pro 档 | 图 + 音频 | 基线 50–240 点 |
| `omnihuman-1-5-human-identification` | 主体识别（前置） | 图 | 不出视频 |
| `omnihuman-1-5-subject-detection` | 主体检测（前置） | 图 | 不出视频 |
| `volcengine-video-to-video-lip-sync` | 视频对口型 | 视频 + 音频 | 基线 50–240 点 |

OmniHuman 家族 4 个 ID 里，只有 2.0 与 1.5 出视频；另两个是主体识别 / 主体检测的前置步骤，先认出人、再驱动。

### 同一段 10 秒音频，应用层锚点

| 路线 | 单价 | 10 秒 |
|---|---|---|
| `image_human` fast | 10 点/输入秒 | 100 点 |
| `image_human` standard | 15 点/输入秒 | 150 点 |
| `image_human` 2k | 30 点/输入秒 | 300 点 |
| `image_human` 4k | 60 点/输入秒 | 600 点 |
| `pic_lipsync` | 15 点/秒，保底 50 点 | 150 点 |
| `lipsync` xiaojiayu1.0 | 2.7 点/秒（上游 ×3） | 27 点（输入是视频） |

`lipsync` 的输入是已有视频，只做参考，不计入「同一张图」的 12 倍。

## 三条干货

### 1. 提交端点只有一条，选错就 404

8 个数字人 ID 全部认 `POST /api/v1/videos/generations`：

```http
POST /api/v1/videos/generations
{"model":"omnihuman-2-0"}

HTTP 400
{"error":"prompt or content field is required","type":"invalid_request_error"}
```

拿目录型号打 `POST /api/v1/videos`：

```http
HTTP 404
{"error":{"code":"model_not_found",
          "message":"The model `omnihuman-2-0` does not exist ..."}}
```

`/videos` 只认 4 个裸视频 ID。`400 prompt ... required` 说明路由认这个型号、参数校验拦下，**不建任务、不冻结**，这是免费的可用性判据。

### 2. 图片字段不是同一个名字

- `omnihuman-2-0` → `image_urls`（数组，1 张）
- `omnihuman-1-5` → `image_url`（单值），另收 `mask_url`（0–5）
- `infinitalk-from-audio` / `kling-ai-avatar-*` → `image_url`
- `volcengine-video-to-video-lip-sync` → `video_url`
- 音频统一 `audio_url`

把 2.0 的图传成 `image_url`，会被上游当成缺图。本包按型号自动切字段名。

### 3. 模型层单价从自己的流水反推

`/api/v1/pricing` 里没有模型层价目。本包按 model 归集 `/api/v1/me/tasks` 的 `actualPrice`：

- 有成交 → 实测区间，标 `source=live`
- 没成交 → 上游数字人 2–12 点/秒 × 通配加价 100% = 4–24 点/秒，单笔保底 50 点，标 `source=baseline`
- 跑成功一次，下一次自动换成你的成交价

本账号 1,398 条台账、7 个模型层模型、43 笔成交，数字人 0 笔 —— 所以这一轮 5 个模型全部是 `baseline`，不编单价。

## 三步上手

### 第 1 步 · 自检（免费，0 点）

```bash
python3 scripts/run.py doctor
```

11 项：模型目录 8 个数字人 ID · 价目表 115 条且模型层无专属规则 · 台账 1,398 条里数字人成交 0 笔 · 空 body 400 · OmniHuman 2.0 缺 prompt 400 · Infinitalk 缺 prompt 400 · `/videos` 404 路由分工 · 假 id 查询 · 余额可读 · 流水本包视频线新增 0 条且今日净 0 点 · 余额变动全部来自外部流水。

### 第 2 步 · 先报价（免费）

```bash
python3 scripts/run.py cost --models omnihuman-2-0,kling-ai-avatar-pro --seconds 10
```

输出逐个模型的上界、来源、应用层同能力锚点，以及「同一张图的报价池」倍数。

### 第 3 步 · 出片横评

```bash
python3 scripts/run.py gen --models omnihuman-2-0,omnihuman-1-5,infinitalk-from-audio \
    --image face.png --audio speech.mp3 --seconds 10 --upload --wait --save --yes
```

不加 `--yes` 退 `4`，并直接告诉你这次要花多少点；超过 `--budget` 退 `5`，一个出片请求都不发。想先看请求体加 `--dry-run`，不提交、不扣费、也不上传。

## 命令一览

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 8 个数字人 ID、5 个可横评模型、7 条应用层锚点 |
| `cost` | 免费 | 同一段音频多模型逐个报价，按上界排序 |
| `doctor` | 免费 | 11 项自检，余额前后对比 + 流水今日净额 |
| `gen` | **按各自单价** | 同一张图 + 同一段音频多模型提交，出对比清单 |
| `status` | 免费 | 查任务、看点数与成片 |
| `sheet` | 免费 | 用 manifest 重新生成「对比清单.md」 |
| `log` | 免费 | 本地台账：每一单的上界与实际点数 |

## 出片之后：对比清单长什么样

`gen` 会在 `run-YYYYmmdd-HHMMSS/` 下写 `manifest.json` 和 `对比清单.md`（下表是示例，数字仅示意）：

```markdown
| 模型 | 上界（点） | 来源 | 状态 | 实际（点） | 用时 | 成片 |
|---|---|---|---|---|---|---|
| `omnihuman-2-0` | 240 | 基线 | completed | 96.4 | 83.2s | 01-omnihuman_2_0.mp4 |
| `kling-ai-avatar-pro` | 240 | 基线 | completed | 180.0 | 71.5s | 02-kling_ai_avatar_pro.mp4 |
```

同一张图、同一段音频、同一句提示词，只有 model 不同 —— 这才是可比的横评。

## 0 点怎么证明

`doctor` 每次都会打三行硬证据：

```
本包视频线新增流水 0 条 · 视频线今日净 0 点
探针前后余额差 0 点（构建时快照 999,997,393,470.2579）
外部并发流水 doctor 单独列出条数与点数，不计入本包
```

探针全部是「空 body」或「只带 model、缺 prompt」，停在校验层。`GET /api/v1/apps/<app>` 一次都不碰（命中通配计价，即时扣费不退）；应用层 `/query` 一次都不碰（每查一次就是一次的钱）；轮询只走 `GET /api/v1/tasks/<id>`。

## 和 sanjianke-digital-host / sanjianke-talking-matrix 的分工

| 你要什么 | 用哪个 |
|---|---|
| 一张图 + 一段音频，先看 5 个模型谁最像、哪个最便宜 | **本包 `cost` / `gen`** |
| 一张图 + 一段文案，直接出一条口播，不选型 | `sanjianke-digital-host talk` |
| 图 + 录音做全驱动数字人，固定四档 | `sanjianke-digital-host drive` |
| 已有视频 + 新配音，重新对口型 | `sanjianke-digital-host dub` |
| 3 个形象 × 4 个音色批量出 12 条 | `sanjianke-talking-matrix` |
| 一句话文生视频，横评 13 个视频模型 | `sanjianke-video-models` |
| 同一张图、同一段音频，要 5 个模型的成片并排 | **本包 `gen`** |

本包只做「选型 + 横评」：5 个模型层入口全提交，3 条应用层路线只做比价锚点，不重复提交。

## 规格

- **零依赖**：只用 Python 标准库；Key 三选一：`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。
- **提交**：`POST /api/v1/videos/generations`，字段按型号自动切 `image_urls` / `image_url` / `video_url` + `audio_url`。
- **上传**：`POST /api/v1/upload`（multipart，字段名 `file`），0 点，地址 24 小时有效。
- **轮询**：`GET /api/v1/tasks/<id>`，0 点；默认 10 秒一次，最长等 15 分钟。
- **输出**：`run-YYYYmmdd-HHMMSS/manifest.json` + `对比清单.md` + 成片（加 `--save`）。
- `cost` 是预估，真实扣费以平台结算的 `usage.points_cost` 为准。

## 许可证

MIT，见 `LICENSE.md`。

---

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
