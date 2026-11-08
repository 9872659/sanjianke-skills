---
name: sanjianke-localize-line
slug: sanjianke-localize-line
displayName: 多语言出海 · 一条中文视频出 12 语版本（10 分钟 2.40 元起）
description: "**一条 10 分钟中文视频，240 点（2.40 元）起，出一版外语配音 + 双语字幕。** 走 api.a7w.cn 的四条线路：`voice_tts/stt` 转写拿字级时间轴（120 点/次）、`chat/completions` 逐条翻成 12 种语言、ElevenLabs 多语言 V2 出外语配音（67 个音色，60 点/条起，单条 5000 字）、字幕在本地生成 SRT / VTT（0 点）。一条 `run` 跑完四步，产物是源字幕 + 目标字幕 + 配音稿 + mp3 + manifest，剪辑软件直接吃。价目如实写：`voice_tts` 按上游真实点数 x3（stt 实测 40 点 -> 我方 120 点），`media_services_33` 落通配。`--budget` 是第一道闸门（单位：点，1 元 = 100 点）、`--yes` 是第二道，超预算一个请求都不发。`doctor` 只打 5 条只读 GET，一个 POST 都不发，0 点。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 视频本地化
  - 多语言配音
  - api.a7w.cn
---

# 多语言出海 · 一条中文视频出 12 语版本

> **API Key 自备**：本包不内嵌 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，
> 扣的是你自己账户的余额；注册、充值、创建 Key 都在 [api.a7w.cn](https://api.a7w.cn/)。
> 存起来反复用：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**一条 10 分钟中文视频，240 点（2.40 元）起，出一版外语配音 + 双语字幕。**
转写、翻译、配音、字幕四步接成一条 `run`，也能拆开单跑。

## 价目表（1 元 = 100 点）

| 步骤 | 走哪条 | 价 | 计费口径 |
|---|---|---|---|
| 转写 | `voice_tts/stt` | **120 点/次** | 上游真实 40 点 x 3，预扣 150 点 |
| 翻译 | `chat/completions` | 按 token | 平台不公布点数，本包只报 token |
| 配音 | `media_services_33` · ElevenLabs m2 | **60 点/条起** | 通配：上游 x 2、保底 50；预扣 60 |
| 字幕 | 本地纯 Python | **0 点** | 0 请求、0 网络 |

| 视频时长 | 源文约 | 目标语言约 | 配音条数 | 合计 |
|---|---|---|---|---|
| 5 分钟 | 1200 字 | 3600 字 | 1 条 | **180 点（1.80 元）起** |
| 10 分钟 | 2400 字 | 7200 字 | 2 条 | **240 点（2.40 元）起** |
| 30 分钟 | 7200 字 | 21600 字 | 5 条 | **420 点（4.20 元）起** |

## 三条干货

### 1. 5000 字是硬上限，60 点是保底、不是成交价

`schema` 原文 `text.maxLength = 5000`。一条 10 分钟中文视频的英文稿约 7000-8000 字，
所以要切 2 条请求，每条各预扣 60 点。**长片不是贵在内容，是贵在条数。**
`run` 算三次：提交前按 `--minutes` / `--chars` 估、转写后按真实字数复核、
翻译后按实际目标字数再复核 —— 三次都在**发钱之前**，超 `--budget` 就停。

### 2. `voice` 是 67 个 ID 的枚举，不是名字

`schema` 的 `voice.enum` 是 67 个固定 ID，默认 `EkK5I93UQWFDigLMpZcX`（James）。
本包支持填名字（`Brian`、`Bella`、`Addison 2.0`），**本地精确且唯一**才转成 ID；
猜不中直接退 `2` 并列出相近项，不把错参数交给上游。`language_code` 本包不传给 m2 档：
schema 原文写明「目前只有 Turbo v2.5 和 Flash v2.5 支持语言强制，其他模型带上会返回错误」。
m2 靠目标语言文本自己识别 —— 这也是 `translate` 要排在 `voice` 前面的原因。

### 3. 字幕不花第二次钱，字级时间轴要显式要

`stt` 的 `ignore_timestamps` **默认 true**，默认调用会把时间戳丢掉；本包固定传 `false`。
返回的 `result.segments` 是字级条目且**不带标点**，标点只在 `result.text` 里 ——
本包按顺序把标点回填到对应字上，两边对不齐就原样返回（宁可不补，也不补错位），
再按「句末标点 / 停顿 >0.7 秒 / 单行超 18 字」合并成字幕行。
SRT 与 VTT 全在本地生成，0 点；配音加 `--timestamps` 时还能按配音时间轴重排
（`subtitle --align dub`），烧进画面时口型更贴。

## 和 sanjianke-localize-crew 的分工

| 维度 | `sanjianke-localize-crew` | 本包 `sanjianke-localize-line` |
|---|---|---|
| 输入 | 文本稿（`.md` / `.txt`） | **中文视频 / 音频** |
| 输出 | 译文 + 术语表 + 四席裁决 | 源字幕 + 目标字幕 + 配音 mp3 + 配音稿 + manifest |
| 核心 | 四席独立互审、术语一致、数字单位 | **转写 -> 翻译 -> 配音 -> 字幕对齐** |
| 花钱 | 只花 token | 转写 120 点 + 配音 60 点/条起 |
| 什么时候用 | 文案要先定稿、要被否过 | 成片要出多语言版本 |

字幕线另有 `sanjianke-pyvideotrans`（只转写 + 出 SRT，配音与时间轴对齐要自己接）；
本包把配音与双语字幕一起收在一条命令里，多语言版本直接落盘。

## 完整链路

```
原视频 ─► voice_tts/stt ─► 台词稿 + 字级时间轴 ─┬─► 源语言 SRT / VTT（0 点）
                                               ▼
                       chat/completions（逐条翻译，行数锁死）─► ElevenLabs m2（67 音色，外语配音，<=5000 字/条）
                                               ▼
                    字幕对齐（原时间轴 / 配音逐词时间轴，本地 0 点）
                                               ▼
   <prefix>-source.srt · <prefix>-<lang>.srt / .vtt / .txt · <prefix>-dub-01.mp3 · manifest.json
```

## 三步上手

**第 1 步：填 Key**

```bash
export A7W_API_KEY=sk-你的key          # Windows PowerShell: $env:A7W_API_KEY="sk-你的key"
```

**第 2 步：免费自检（0 点、0 个 POST）**

```bash
python3 scripts/run.py doctor
```

```
√ Key 有效 + 余额接口可达                     HTTP 200 · 冻结 0 点
√ 应用目录里 voice_tts 与 media_services_33 都在架   22 个应用 · 6 / 29 个接口
√ 价目表两项对得上（voice_tts x3 + 通配保底）   115 条规则 · 200 / 50
```

**第 3 步：先看钱，再决定跑不跑**

```bash
python3 scripts/run.py cost --minutes 10
python3 scripts/run.py run --input 第03集.mp4 --to en --voice Brian --dry-run
python3 scripts/run.py run --input 第03集.mp4 --to en --voice Brian --outdir ./出片 --yes
```

## 常用命令

```bash
python3 scripts/run.py catalog --voices                 # 67 个音色全列 + 12 语言 + 价目
python3 scripts/run.py transcribe --input 第03集.mp4 --outdir ./出片 --yes
python3 scripts/run.py translate --in ./出片/localize-source.json --to ja --yes
python3 scripts/run.py voice --in ./出片/localize-ja.json --voice hpp4J3VqNfWAUOO0d1Us \
    --timestamps --outdir ./出片 --yes
python3 scripts/run.py subtitle --in ./出片/localize-ja.json --to ja \
    --align dub --dub ./出片/localize-dub-01.timestamps.json --outdir ./出片
python3 scripts/run.py run --input 预告.mp4 --to es --script 西班牙语台词.txt --yes
python3 scripts/run.py task --task-id task_xxx          # 查任务，免费
```

## 规格

| 项 | 说明 |
|---|---|
| 语言 | 12 种：`en` `ja` `ko` `es` `pt` `fr` `de` `ru` `ar` `th` `vi` `id` |
| 音色 | 67 个（`catalog --voices` 全列；默认 Brian） |
| 单条配音上限 | 5000 字（schema 原文），超了按行切块、一块一请求 |
| 字幕 / 依赖 | SRT + VTT + 纯文本，本地生成，UTF-8 无 BOM；零依赖，Python 3.7+ 标准库 |
| 退出码 | `0` 成功 / `2` 用法错 / `4` 缺 `--yes` / `5` 超 `--budget` / `6` 调用失败 / `1` 内部错 / `130` 中断 |
| `--json` | 成功 `{"ok": true, ...}`；失败 `{"ok": false, "exit": N, "error": {"kind","message"}}` |

## 我们这轮实测了什么

- `doctor` 在 `PYTHONIOENCODING=gbk` 下 **exit=0**，输出 824 字节全部可按 GBK 解码，
  0 个替换字符（`√` / `×` 在 cp936 里都有，金额一律写「元」）。
- 全程 **0 个 POST、0 次冻结、0 点**：`/user/balance/logs` 前后对比，没有新增流水。
- `--help` 父命令 + 10 个子命令全 exit=0；缺 `--yes` 退 `4`、`--budget 1` 退 `5` 且 0 请求。
- 边界（如实标注）：本轮零花费，配音成功后的返回结构与 `timestamps` 键名按平台文档与同族实测写，
  解析器做了递归兜底；真跑一条时 `voice --json` 会原样打出返回。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
