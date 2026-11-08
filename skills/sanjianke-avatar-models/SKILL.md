---
name: sanjianke-avatar-models
slug: sanjianke-avatar-models
displayName: 数字人模型台 5 款横评 10 秒 50 点起
description: "**一张图 + 一段 10 秒音频，5 个模型先报价再出片：模型层 50–240 点，应用层 100–600 点，差 12 倍。** 8 个 ID：OmniHuman 2.0 / 1.5、Infinitalk、可灵 Avatar ×2、视频对口型。`catalog` 看 ID 与 7 条锚点，`cost` 报价，`gen` 出片带对比清单。实测提交只走 `/videos/generations`（`/videos` 404）；2.0 用 `image_urls` 数组，图驱动用 `image_url`；模型层单价不在表里，0 笔成交按 4–24 点/秒基线标 `baseline`，跑过换 `live`。轮询只走 `/api/v1/tasks/<id>`。缺 `--yes` 退 4，超预算退 5。Key 见 https://api.a7w.cn/。技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 数字人
  - 模型横评
  - api.a7w.cn
---

# 数字人模型台 · 同一张图 + 同一段音频，5 个模型先报价再出片

> **先申请你自己的 API Key。** 本包不内嵌 Key，扣的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的账户余额。
> 存起来只要一条命令：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**同一张图 + 同一段 10 秒音频：应用层要 100–600 点，模型层基线 50–240 点，最高差 12 倍。**
本包把 5 个音频驱动数字人模型放进同一张表：先报价、再选型、最后用同一张图和同一段音频出片并排看。

## 价目表（1 元 = 100 点；应用层 2026-11-08 现查）

| 路线 | 单价 | 10 秒音频 | 来源 |
|---|---|---|---|
| `omnihuman-2-0` | 基线 4–24 点/秒 | 50–240 点 | `baseline` |
| `omnihuman-1-5` | 基线 4–24 点/秒 | 50–240 点 | `baseline` |
| `infinitalk-from-audio` | 基线 4–24 点/秒 | 50–240 点 | `baseline` |
| `kling-ai-avatar-standard` | 基线 4–24 点/秒 | 50–240 点 | `baseline` |
| `kling-ai-avatar-pro` | 基线 4–24 点/秒 | 50–240 点 | `baseline` |
| `image_human` fast / standard / 2k / 4k | 10 / 15 / 30 / 60 点/输入秒 | 100 / 150 / 300 / 600 点 | 价目表现查 |
| `pic_lipsync` | 15 点/秒，保底 50 点 | 150 点 | 价目表现查 |
| `lipsync` xiaojiayu1.0 | 2.7 点/秒 | 27 点 | 价目表现查 |

`lipsync` 的输入是已有视频，只做参考，不计入「同一张图」的倍数；其余 7 条都是图 + 音频。

## 三条干货

1. **提交端点只有一条。** 8 个数字人 ID 全部认 `POST /api/v1/videos/generations`；拿目录型号打 `POST /api/v1/videos` 会回 `404 model_not_found`（那条只认 4 个裸视频 ID）。模型调用形态是「只带 model、缺 prompt」→ `400 prompt or content field is required`，停在校验层，不建任务、不冻结。轮询只走免费的 `GET /api/v1/tasks/<id>`；应用层 `/apps/<app>/query` 每查一次就是一次的钱。
2. **图片字段不是同一个名字。** `omnihuman-2-0` 要 `image_urls`（数组，1 张），其余要 `image_url`（单值）；`omnihuman-1-5` 另收 `mask_url`（0–5）；音频统一 `audio_url`。传错字段名会被上游当成缺图。OmniHuman 家族 4 个 ID 里只有 2.0 与 1.5 出视频，另两个是主体识别 / 主体检测的前置步骤。

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

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 8 个数字人 ID、5 个可横评模型、7 条应用层锚点 |
| `cost` | 免费 | 同一段音频多模型逐个报价，按上界排序 |
| `doctor` | 免费 | 11 项自检，余额前后对比 + 流水今日净额 |
| `gen` | **按各自单价** | 同一张图 + 同一段音频多模型提交，出对比清单 |
| `status` | 免费 | 查任务、看点数与成片 |
| `sheet` | 免费 | 用 manifest 重新生成「对比清单.md」|
| `log` | 免费 | 本地台账：每一单的上界与实际点数 |

## 三步上手

**第 1 步 · 自检（免费，0 点）**

```bash
python3 scripts/run.py doctor
```

11 项：模型目录 8 个数字人 ID · 价目表 115 条且模型层无专属规则 · 台账 1,398 条里数字人成交 0 笔 · 空 body 400 · OmniHuman 2.0 缺 prompt 400 · Infinitalk 缺 prompt 400 · `/videos` 404 路由分工 · 假 id 查询 · 余额可读 · 流水本包视频线新增 0 条且今日净 0 点 · 余额变动全部来自外部流水。

**第 2 步 · 先报价（免费）**

```bash
python3 scripts/run.py cost --models omnihuman-2-0,kling-ai-avatar-pro --seconds 10
```

输出逐个模型的上界、来源、应用层同能力锚点，并算出「同一张图的报价池」倍数。

**第 3 步 · 出片横评**

```bash
python3 scripts/run.py gen --models omnihuman-2-0,omnihuman-1-5,infinitalk-from-audio \
    --image face.png --audio speech.mp3 --seconds 10 --upload --wait --save --yes
```

不用 `--yes` 退 `4`，并直接告诉你这次要花多少点；超过 `--budget` 退 `5`，一个出片请求都不发。想先看请求体加 `--dry-run`，不提交、不扣费、也不上传。

## 常用命令

```bash
python3 scripts/run.py catalog --seconds 10
python3 scripts/run.py cost --seconds 10
python3 scripts/run.py doctor
python3 scripts/run.py gen --models omnihuman-2-0 --image face.png --audio speech.mp3 --upload --wait --save --yes
python3 scripts/run.py status --task-id task_xxx
python3 scripts/run.py sheet --run run-20261108-110000
python3 scripts/run.py log
```

常用参数：`--models` 逗号分隔 · `--image` 人物图 · `--audio` 驱动音频 · `--video` 已有视频（只视频对口型用）·
`--seconds` 音频秒数（只影响报价与预算）· `--prompt` 共用提示词 · `--upload` 本地文件先传平台（0 点）·
`--wait` 等完成 · `--save` 下载成片 · `--outdir` 落盘目录 · `--budget` 点数上限 · `--yes` 确认扣费 · `--dry-run` 只看请求。

## 退出码与 `--json`

`0` 成功 / `2` 用法错 / `4` 需要 `--yes` / `5` 预算不足（零出片请求）/ `6` 调用失败 / `1` 内部错 / `130` 中断。

`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档：

```json
{"ok": true, "seconds": 10, "totalPoints": 1200, "models": [{"model": "omnihuman-2-0", "gate": 240, "source": "baseline"}]}
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "预计 1,200 点超过 --budget 100 点…"}}
```

## 规格

- **零依赖**：只用 Python 标准库；Key 三选一：`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。
- **提交**：`POST /api/v1/videos/generations`，字段按型号自动切 `image_urls` / `image_url` / `video_url` + `audio_url`。
- **上传**：`POST /api/v1/upload`（multipart，字段名 `file`），0 点，地址 24 小时有效。
- **轮询**：`GET /api/v1/tasks/<id>`，0 点；默认 10 秒一次，最长等 15 分钟。
- **0 点实测**：探针窗口内余额未变、本包视频线新增流水 0 条（构建时 total 7,885）；账户里外部并发任务的流水由 `doctor` 单独统计，不计入本包。
- **文档**：接口原文见 `references/api-contract.md`，按报错找原因见 `references/troubleshooting.md`。
- `cost` 是预估，真实扣费以平台结算的 `usage.points_cost` 为准。

## 免责

- 人像合成请自备**肖像权授权**；用真人形象、真人声音前，确保你拿到了对方同意。
- 生成内容的合规责任在使用者：不用于伪造他人身份、侵权素材或违法用途。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
