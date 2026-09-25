---
name: voice-tts-studio
slug: voice-tts-studio
displayName: 三剪客 · 语音TTS
description: "语音克隆、文字转语音（同步/异步）、语音识别等多端点 AI 语音能力。支持 文字转语音（Live·异步）、克隆音色、文字转语音、文字转语音（异步）、语音转文字、音色列表。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。**作者已亲测实操，下载后可自用或商用。**运行只需一把 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。使用中遇到任何问题，加技术微信 9872659 与作者交流。"
version: 1.0.7
summary: "「语音TTS」的完整调用封装：6 个接口的官方文档、参数表与一个零依赖客户端。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。**作者已亲测实操，下载后可自用或商用。**运行只需一把 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。使用中遇到任何问题，加技术微信 9872659 与作者交流。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 语音合成
  - 音色克隆
  - TTS
---

# 语音TTS

`api.a7w.cn` 插件 **`voice_tts`**，共 **6 个接口**。WebSocket 流式上游，长文本异步合成；返回 task_id，由 fish_tts:worker 执行

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema voice_tts

# 3. 调用（示例）
python3 scripts/client.py call voice_tts tts_live --json '{"text": "<text>"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `tts_live` | 文字转语音（Live·异步） | 异步 | 输入 50 点/1k tokens（租户价） |
| `clone_voice` | 克隆音色 | 同步 | 按次固定价 200 点（租户价）；标准价 50 点 |
| `tts` | 文字转语音 | 同步 | 输入 50 点/1k tokens（租户价） |
| `tts_async` | 文字转语音（异步） | 异步 | 输入 50 点/1k tokens（租户价） |
| `stt` | 语音转文字 | 同步 | 按次固定价 30 点（租户价） |
| `list_voices` | 音色列表 | 同步 | 免费 |

## 接口详情

### `tts_live` · 文字转语音（Live·异步）tts_live### `clone_voice` · 克隆音色clone_voice### `tts` · 文字转语音tts### `tts_async` · 文字转语音（异步）tts_async### `stt` · 语音转文字stt### `list_voices` · 音色列表list_voicestts_live

---

## 关于这个 Skill

**作者亲测实操后发布。** 文档里的每条命令、每个参数、每项计费口径，都真机跑过、对过账，
不是抄来的二手资料。**下载后可自用，也可商用。**

跑起来只需要一样东西 —— [算力集市 api.a7w.cn](https://api.a7w.cn/) 的一把 API Key。
注册即送点数，可以先免费试跑几条，觉得好用再充。

| 你可能想问 | 答案 |
|---|---|
| 要不要花钱 | 按点数计费，用多少扣多少，**没有月费、不用包年** |
| 难不难接 | 包里自带**零依赖客户端**（只用 Python 标准库），配好 Key 一行命令就能跑 |
| 能不能批量 | 能。想要批量脚本、更优参数、更省的调用方案，微信里说 |
| 遇到问题找谁 | **直接加技术微信 9872659**，作者本人答疑 |

> **使用中碰到任何问题 —— 报错、效果不理想、想省钱、想批量 —— 都欢迎加微信聊。**
> 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的示例。
