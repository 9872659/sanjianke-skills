---
name: sanjianke-pro-voice
slug: sanjianke-pro-voice
displayName: 高保真语音台 短剧配音一句话一个角色
description: "**同一个剧本，五个角色，五种声音 —— 一人一句，一次出完，还能带时间戳字幕。** 走 api.a7w.cn 的语音通道，8 个接口一条命令：ElevenLabs 多语言 V2 的音质标杆、Turbo 2.5 的极速档、对话 V3 的多人对白，加上 Gemini 3.8 双档与 2.5 Pro 的 30 音色 8 口音。`voice` 传的是 20 位音色 ID（67 个，包里按名字自动换 ID），`dialogue` 是每个角色各带 `voice` 的数组 —— 这两处最容易白跑一趟，已经写进默认动作。`cost` 先算钱、`--budget` 与 `--yes` 两道闸门、`doctor` 默认零 POST 就把 8 个端点全验一遍。遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "短剧、播客、有声书的配音有三个坑：音色要 ID 不要名字、对白要数组不要段落、价格按上游实际点数算。本包把三条都做成了默认行为。**8 条线**（同一条 `POST /api/v1/apps/media_services_33/<code>`，换 code 就换线）：`v2` 多语言 V2（67 音色，音质标杆）、`turbo` Turbo 2.5（同款音色更快，唯一支持强制语言）、`v3` 对话 V3（多人对白，每句自带音色）、`gemini38` / `gemini38lite`（70 音色，逐句可给语气、可加语气词）、`gemini25pro`（30 音色 + 8 口音 + 4 档语速 + 6 种情感）、`omni` 音色设计、`character` 角色设计。**实测形态**：`voice` 传名字回「input.voice: 不在允许选项内」，`dialogue` 传字符串回「input.dialogue: 类型不正确」，`speakers` 类型错了回 HTTP 500 但同样不建单。**价格**：pricing 的 115 条规则里没有 media_services_33 也没有 elevenlabs_*，全部落通配「上游实际点数 × 2、保底 50 点」；实测每次 POST 预冻结 60 点，所以 `cost` 给的是 60 点/条的下限，成交价要真跑一条才知道。一次请求就是一条任务，十句对白也是一条。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 语音配音
  - 多角色对白
  - api.a7w.cn
---

# 高保真语音台 短剧配音一句话一个角色

> **本包不内嵌 Key**：用你自己在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**一个剧本进去，五种声音出来。** 三人对手戏、五人群戏、播客双人、有声书独白 —— 8 个语音接口一条命令，零依赖。

## 三条音色线，一眼选对

| 音色线 | 用哪个 | 音色 | 什么时候上 |
|---|---|---|---|
| **ElevenLabs 多语言 V2** | `--line v2` | 67 | 音质标杆。单人旁白、预告片、有声书，情绪 / 稳定性 / 相似度都能拧 |
| **ElevenLabs Turbo 2.5** | `--line turbo` | 67 | 同一套音色，出得更快；唯一能用 `--language-code` 强制语言的档 |
| **Gemini 对话式** | `--line gemini38` / `gemini38lite` / `gemini25pro` | 70 / 70 / 30 | 会接话。逐句给语气、两人对话加语气词、2.5 Pro 还能换口音和语速 |

```bash
python3 scripts/run.py speak --line v2    --text "你终于来了。" --voice James --yes
python3 scripts/run.py speak --line turbo --text "你终于来了。" --voice James --language-code zh --yes
```

## `dialogue` 怎么用 —— 本包和普通 TTS 最大的区别

普通 TTS 是「一段文本一个音色」，跑五个人得发五次、拼五次。**V3 的 `dialogue` 是数组，每句自带 `voice`**，一次请求出整段对手戏：

```json
{"dialogue": [
  {"text": "你终于来了。",   "voice": "EkK5I93UQWFDigLMpZcX"},
  {"text": "我一直在等你。", "voice": "Z3R5wn05IrDiVCyEkUrK"}
]}
```

传成字符串会被挡回来（实测原文 `{"code":0,"msg":"input.dialogue: 类型不正确","data":null}`）。所以本包用 `--voices` 分音色、`--turn` 或剧本文件给台词，组装交给我：

```bash
python3 scripts/run.py dialogue --voices "林晚=James" --voices "沈砚=Arabella" \
    --turn "林晚: 你终于来了。" --turn "沈砚: 我一直在等你。" --yes
```

规则三条：所有台词加起来 ≤ 5000 字符、每个角色必须分到音色、`voice` 只能是 67 个 ID 之一（写名字自动换）。

## 一条完整链路：剧本 → 分角色 → 配音 → 时间戳 → 对齐字幕

```bash
# 1) 剧本存成 UTF-8，一行一句「角色: 台词」（# 开头是注释）：林晚: 你终于来了。
# 2) 干跑：只看请求体，不发请求、不冻结
python3 scripts/run.py dialogue --script 剧本.txt \
    --voices "林晚=James" --voices "沈砚=Arabella" --dry-run

# 3) 真跑：一次出完整段对手戏
python3 scripts/run.py dialogue --script 剧本.txt \
    --voices "林晚=James" --voices "沈砚=Arabella" --yes

# 4) 逐句要时间戳（v2 / turbo 的 --timestamps），拿去对齐字幕
python3 scripts/run.py speak --line v2 --text "你终于来了。" --voice James --timestamps --yes

# 5) 拿到任务号就追结果
python3 scripts/run.py task --task-id task_xxx
```

各线的返回结构不完全一样，包里把 `taskId` 和所有音频地址都打出来；`--json` 固定给 `taskId` 与 `audioUrls` 两个键，写脚本照这两个取。

## 三步上手

```bash
python3 scripts/run.py doctor                  # 1) 自检：Key / 应用 / 8 端点 / 价目口径，默认零 POST
python3 scripts/run.py voices --line v2        # 2) 挑音色：67 个 ID（3.8 有 70 个名字，Omni 30 个）
python3 scripts/run.py cost                    # 3) 先算钱：下限 60 点/条
python3 scripts/run.py speak --text "你终于来了。" --voice James --yes
```

## 价目（1 元 = 100 点）

| 项 | 值 |
|---|---|
| 专属规则 | `pricing` 的 115 条里 **0 条**（逐条筛过 elevenlabs / media_services / gemini / tts），落通配 `{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50}` |
| 结算口径 | 上游实际点数 × 2，单笔保底 50 点；实测每次 POST 预冻结 **60 点**（50 × 站点 20% 加价） |

`cost` 给的是**下限估算**，一条到底多少钱 = 上游按字数算的真实点数 × 2，真跑一条才看得见。一次请求就是一条任务 —— 十句对白的群戏也是一条，不是十条。

## 三条别人不会告诉你的

**一、`voice` 是 ID，不是名字。** 67 个 20 位 ID 写在枚举里，名字只在字段说明文字里。传 "James" 出去会回 `input.voice: 不在允许选项内`。本包 `--voice James` 自动换成 `EkK5I93UQWFDigLMpZcX`，重名（Mark / Hope / Viraj 各两个）取第一个并告一声。

**二、校验失败也是 HTTP 200。** `{"code":0,"msg":"input.xxx: …","data":null}` —— 状态码没有区分度，判成功只能看 `code == 1`。Gemini 三条线遇类型错更直接：HTTP 500「服务内部错误」，同样不建单，冻结的 60 点原路退回（`refund:sync_error`）。

**三、2.5 Pro 的音色表和 3.8 不一样。** 3.8 有 70 个 `voice_name`，2.5 Pro 只有 30 个，而且 `accent` 必填（默认 Neutral）。拿 3.8 的名字打 2.5 Pro 会白跑，本包按线在本地校验，报错时一个请求都没发。

## 常用命令

```bash
python3 scripts/run.py catalog                                    # 8 条线 + 接口 code + 音色数
python3 scripts/run.py voices --line gemini38                     # 70 个音色 + 40 个语气标签
python3 scripts/run.py speak --text "…" --voice Arabella --speed 0.9 --stability 0.4 --yes
python3 scripts/run.py scene --line gemini38 --cast "1=Kore" --cast "2=Fenrir" --turn "1: 门外有人。" --turn "2: <whispering> 别开门。" --filler-words --yes
python3 scripts/run.py scene --line gemini25pro --cast "1=Kore" --accent "British (RP)" --turn "1: 门开了。" --scene "A quiet room with a fireplace." --yes
python3 scripts/run.py design --name "深夜电台-阿岚" --audio-id achernar --yes
python3 scripts/run.py task --task-id task_xxx
```

**不加 `--yes` 退 `4`** 并告诉你这次下限多少点；**下限 > `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 600 = 6 元）。

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--line` | `v2` | `speak` 用 v2 / turbo；`scene` 用 gemini38 / gemini38lite / gemini25pro |
| `--text` / `--text-file` | — | 单人台词，≤ 5000 字符（UTF-8） |
| `--voice` | 必填 | 音色 ID 或名字（67 个，见 `voices`） |
| `--turn` / `--script` | — | 「角色: 台词」重复给，或整份剧本文件 |
| `--voices` / `--cast` | 必填 | 角色=音色（V3 用 `--voices`，Gemini 用 `--cast`） |
| `--timestamps` | — | v2 / turbo 顺带要逐词时间戳 |
| `--budget` | 600 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实建单 / 只打印请求 |

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` / `voices` / `cost` | 免费 | 8 条线 / 音色库 / 下限估算 |
| `doctor` | 免费 | 自检（默认零 POST；`--probe-post` 才碰端点，每条冻 60 后退回，净 0） |
| `speak` / `dialogue` / `scene` | **计费** | 单人 / 多人对白 / 场景对话 |
| `design` / `character` | **计费** | 造音色 / 造角色 |
| `task` / `log` | 免费 | 查任务 / 本地台账 |

## 退出码

`0` 成功 / `2` 用法错（缺参数、音色不在表里、选项缩写）/ `3` doctor 出现 × / `4` 没给 `--yes` / `5` 预算不足（**一个请求都不发**）/ `6` 调用失败 / `1` 内部错 / `130` 中断。

## `--json` 契约

```json
{"ok": true, "line": "v2", "code": "elevenlabs_text_to_speech_multilingual_v2",
 "taskId": "task_xxx", "audioUrls": ["https://…"], "estimatedPoints": 60}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
