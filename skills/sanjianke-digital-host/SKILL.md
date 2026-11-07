---
name: sanjianke-digital-host
slug: sanjianke-digital-host
displayName: 数字人口播台 一张图一段话一个人开口
description: "**不用出镜、不用录音、不用剪辑 —— 一张照片加一段文案，三分钟给你一条口播视频。** 三个数字人应用收成一个入口：`talk` 文案驱动（15 点/秒）、`drive` 全驱动（10/15/30/60 点/输入秒）、`dub` 已有视频重新对口型（上游×3）。`catalog` 一屏对照三种做法，`cost` 三路算钱，`doctor` 只用四个只读 GET（apps / pricing / tasks / balance），并核对 live 速率卡。两个花钱的坑做进了默认动作：image_human 不传 mode 会「按 standard 出片、按 fast 收钱」，所以 `--mode` 必填；pic_lipsync 的档位真名是 `quality`。需要自备 API Key，注册见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "数字人口播三件套：talk（pic_lipsync 文案驱动，图 + 参考音色 + 文案）、drive（image_human 全驱动，图 + 音频，快速 10 / 标准 15 / 2K 30 / 4K 60 点/输入秒）、dub（lipsync 给已有视频重新对口型，上游实际点数 ×3）。三条线共用一套提交 + 轮询与台账。免费命令先把钱讲清楚：catalog 对照三路参数与价格，cost 分别算到点，doctor 六项自检覆盖 Key、三个 submit 端点是否已配价、两张速率卡、任务查询线与余额，全程只发四个只读 GET。两条实测口径写进了默认动作：image_human 的 schema 默认 standard、计费卡默认 fast，不传 mode 就变成按标准出片、按快速收钱，所以 --mode 必填；pic_lipsync 的档位真名是 quality，mode 只切 audio/text，且 text 模式的 audio_url 是参考音色。dub 里 1.0 折算 2.7 点/秒，2.0 / 3.0 是 13.5 点/秒。缺 --yes 退 4 并报出要花多少点，超过 --budget 退 5 且一个请求都不发。零依赖。需要自备 API Key，注册见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数字人
  - 口播视频
  - api.a7w.cn
---

# 数字人口播台 · 一张图 + 一段话 → 一个人开口

> **不用出镜、不用录音、不用剪辑。** 一张照片 + 一段话，三分钟一条口播视频。
> **先申请你自己的 API Key。** 本包不内嵌 Key，扣的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的账户余额，
> 存起来只要一条命令：`python3 scripts/a7w.py login --key sk-你的key`

## 三种做法，先看这张表

| 你要的效果 | 命令 | 应用 | 你给什么 | 价格 |
|---|---|---|---|---|
| 一张图 + 一段文案 → 人开口念 | **`talk`** | `pic_lipsync` | 图 + 参考音色 + 文案 | **15 点/秒** |
| 一张图 + 一段录音 → 人对口型 | **`drive`** | `image_human` | 图 + 音频 + 秒数 + 档位 | **10 / 15 / 30 / 60 点/秒** |
| 已有视频 + 新配音 → 重新对口型 | **`dub`** | `lipsync` | 视频 + 音频 + 秒数 | **上游实际 ×3** |

三者一句话分清楚：**文案驱动最轻（talk），全驱动最稳可调档（drive），已有视频换口型最省（dub）。**

## 价目（2026-10-10 站主批准）

| 做法 | 档位 | 价格 | 30 秒 |
|---|---|---|---|
| `talk` | 标准（默认） | **15 点/秒** | 450 点 = ¥4.50 |
| `drive` | `fast` 快速 | **10 点/秒** | 300 点 = ¥3.00 |
| `drive` | `standard` 标准 | **15 点/秒** | 450 点 = ¥4.50 |
| `drive` | `2k` | **30 点/秒** | 900 点 = ¥9.00 |
| `drive` | `4k` | **60 点/秒** | 1800 点 = ¥18.00 |
| `dub` | `xiaojiayu1.0` | 2.7 点/秒 | 81 点 = ¥0.81 |
| `dub` | `xiaojiayu2.0` / `3.0` | 13.5 点/秒 | 405 点 = ¥4.05 |

**1 元 = 100 点。** `talk` 按公开文档的 50 点保底下限预估，短文案不会比 50 点更低。

### 三条别人不会告诉你的口径

1. **`talk` 的档位参数真名是 `quality`**（`standard` / `fast` / `max`），`mode` 只负责切 `audio` / `text`。
   按 `mode=max` 传的人不少，上游会安静地按 `standard` 收费。
2. **`drive` 不传 `mode` = 按标准出片、按快速收钱。** schema 默认 `standard`、计费卡默认 `fast`，
   两边不一致，所以本包的 `--mode` **必填**，宁可报错也不让档位和账单对不上。
3. **`drive` 带上 `duration`，价格才被锁死 = 费率 × 秒数。** 不给则由平台按上游冻结点计费，估不准。
   这是 `--duration` 也做成必填的原因。

## 一条完整链路：选形象 → 写文案 → 出片 → 下载

### 第 0 步 · 拿 Key（免费）

到 [api.a7w.cn](https://api.a7w.cn/) 注册并创建 Key（形如 `sk-...`），存成环境变量或写进本机配置：
`export A7W_API_KEY=sk-你的key`（Windows：`$env:A7W_API_KEY="sk-你的key"`），
或者直接 `python3 scripts/a7w.py login --key sk-你的key`。

### 第 1 步 · 自检（免费，不扣费）

```bash
python3 scripts/run.py doctor
```

六项：Key 与应用目录 · 三个 submit 端点已配价 · image_human 速率卡 10/15/30/60 · lipsync ×3 与 pic_lipsync ×5 · 任务查询线 · 余额可读。

**全程只发四个只读 GET，一个 submit 都不发。** 实测记一笔：应用层 `submit` 会**先同步预扣、再校验参数**，
连「缺一个必填」的请求都会产生「冻结 −N → 退款 +N」的一对流水，净额 0 但钱包被短暂动过。
自检不该动钱包，所以端点存在性用定价表里已配价的三条规则来证明。

### 第 2 步 · 算钱（免费）

```bash
python3 scripts/run.py cost --way talk --content "大家好，今天聊一个很多人关心的问题…"
python3 scripts/run.py cost --way drive --mode 4k --duration 30     # 1800 点
python3 scripts/run.py cost --way dub --seconds 30                  # 81 点
```

### 第 3 步 · 出片

```bash
# 最轻的一条：图 + 文案 + 参考音色
python3 scripts/run.py talk --image face.png --voice-ref voice.mp3 \
    --content "大家好，今天聊一个很多人关心的问题：为什么同样一条短视频，有人三天出一条，有人一天出十条。" \
    --upload --save --yes

# 全驱动：图 + 录音，指定档位和秒数
python3 scripts/run.py drive --image face.png --audio speech.mp3 \
    --mode standard --duration 30 --upload --save --yes

# 已有视频换口型
python3 scripts/run.py dub --video old.mp4 --audio new.mp3 --seconds 30 --upload --save --yes
```

**不加 `--yes` 退 `4`**，并直接告诉你这次要花多少点。想先看请求体：加 `--dry-run`，不提交、不扣费。

### 第 4 步 · 拿成片

```bash
python3 scripts/run.py status --task-id task_xxx --save   # 查任务 + 下载成片
python3 scripts/run.py log                                # 本地台账：每一单的点数与状态
```

## 和 avatar-autoclip 的分工

| 你要什么 | 用哪个 |
|---|---|
| 只要一段「人说话」的视频（单步、最轻、不套模板） | **本包 `talk`** |
| 图 + 文案 → 配音 → 口播 → 套模板 → 出成片（五步流水线） | `avatar-autoclip make` |
| 全驱动数字人、可调 10 / 15 / 30 / 60 四档 | **本包 `drive`** |
| 已有视频 + 新音频 → 重新对口型 | **本包 `dub`** |
| 数字人 + 自动字幕 + 自动封面 + 智能剪辑成 1080×1920 | `avatar-autoclip` |
| 只要网页版、不配 Key | `aigc-digital-human-studio` |

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 三种做法对照（参数 + 价格，一屏看完）|
| `cost` | 免费 | 三路各自算钱（`--way talk/drive/dub`）|
| `doctor` | 免费 | 六项自检，四个只读 GET |
| `talk` | **15 点/秒** | 文案驱动口播（`pic_lipsync` mode=text）|
| `drive` | **10/15/30/60 点/秒** | 全驱动数字人（`image_human`）|
| `dub` | **上游 ×3** | 已有视频对口型（`lipsync`）|
| `status` | 免费 | 查任务、可下载成片 |
| `log` | 免费 | 本地台账 |

**常用参数**：`--image` 图片 · `--voice-ref` 参考音色 · `--audio` 驱动音频 · `--video` 已有视频 ·
`--content` 文案 · `--quality` 档位 · `--mode` 档位（drive 必填）· `--duration` 秒数（drive 必填）·
`--seconds` 秒数（dub 必填）· `--upload` 本地文件先传平台临时地址（上传不计费）·
`--save` / `--outdir` 下载成片 · `--budget` 点数上限 · `--yes` 确认扣费 · `--dry-run` 只看请求。
完整参数见 `--help`。

## 退出码与 `--json`

`0` 成功 / `2` 用法错 / `4` 需要 `--yes` / `5` 预算不足（**一个请求都不发**）/ `6` 调用失败 / `1` 内部错 / `130` 中断。

`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档：
成功 `{"ok": true, "app": "pic_lipsync", "taskId": "task_xxx", "status": "completed", "urls": [...], "points": 181.5}`；
失败 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`。

## 免责

- 人像合成请自备**肖像权授权**；用真人形象、真人声音前，确保你拿到了对方同意。
- `cost` 是预估；真实扣费以平台结算的 `usage` 为准。
- 生成内容的合规责任在使用者：不用于伪造他人身份、侵权素材或违法用途。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
