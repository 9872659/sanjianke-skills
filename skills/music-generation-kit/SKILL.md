---
name: music-generation-kit
slug: music-generation-kit
displayName: 三剪客 · 音乐生成
description: "音乐生成应用，支持歌曲生成、歌词生成、参考音频、声音克隆、音频导出和分轨处理。支持 歌词混合、人声处理、优化音乐风格、导出 MIDI、歌词时间轴、导出 MP4、导出 WAV、声音克隆。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。**作者已亲测实操，下载后可自用或商用。**运行只需一把 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。使用中遇到任何问题，加技术微信 9872659 与作者交流。"
version: 1.0.8
summary: "「音乐生成」的完整调用封装：13 个接口的官方文档、参数表与一个零依赖客户端。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。**作者已亲测实操，下载后可自用或商用。**运行只需一把 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。使用中遇到任何问题，加技术微信 9872659 与作者交流。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 音乐生成
  - 音频
---

# 音乐生成

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。


`api.a7w.cn` 插件 **`music_generation`**，共 **13 个接口**。将两段歌词融合为新的混合版本。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema music_generation

# 3. 调用（示例）
python3 scripts/client.py call music_generation mashup_lyrics --json '{}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `mashup_lyrics` | 歌词混合 | 同步 | 按次固定价 12 点（租户价） |
| `vox` | 人声处理 | 异步 | 按次固定价 14 点（租户价） |
| `style` | 优化音乐风格 | 同步 | 按次固定价 14 点（租户价） |
| `midi` | 导出 MIDI | 异步 | 按次固定价 14 点（租户价） |
| `timing` | 歌词时间轴 | 同步 | 免费 |
| `mp4` | 导出 MP4 | 同步 | 按次固定价 20 点（租户价） |
| `wav` | 导出 WAV | 异步 | 按次固定价 14 点（租户价） |
| `voice_clone` | 声音克隆 | 同步 | 按次固定价 20 点（租户价） |
| `persona` | 创建歌手风格 | 同步 | 按次固定价 12 点（租户价） |
| `upload_audio` | 上传参考音频 | 同步 | 按次固定价 13 点（租户价） |
| `lyrics` | 生成歌词 | 同步 | 按次固定价 12 点（租户价） |
| `query` | 查询音乐任务 | 同步 | 免费 |
| `create` | 创建音乐任务 | 异步 | 按次固定价 65 点（租户价） |

## 接口详情

### `mashup_lyrics` · 歌词混合mashup_lyrics### `vox` · 人声处理vox### `style` · 优化音乐风格style### `midi` · 导出 MIDImidi### `timing` · 歌词时间轴timing### `mp4` · 导出 MP4mp4### `wav` · 导出 WAVwav### `voice_clone` · 声音克隆voice_clone### `persona` · 创建歌手风格persona### `upload_audio` · 上传参考音频upload_audio### `lyrics` · 生成歌词lyrics### `query` · 查询音乐任务query### `create` · 创建音乐任务createmashup_lyrics

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
