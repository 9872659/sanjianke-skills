---
name: lipsync
slug: lipsync
displayName: 三剪客 · 数字人对口型
description: "数字人对口型（Lipsync），任务由平台弹性部署调度。支持 提交任务、查询任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.3
summary: "「数字人对口型」的完整调用封装：2 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 口型同步
  - 数字人
---

# 数字人对口型

`api.a7w.cn` 插件 **`lipsync`**，共 **2 个接口**。创建一条数字人对口型任务，返回平台任务 ID

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema lipsync

# 3. 调用（示例）
python3 scripts/client.py call lipsync submit --json '{"audio_url": "https://example.com/speech.wav", "video_url": "https://example.com/avatar_video.mp4"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 提交任务 | 异步 | 以站内计费为准 |
| `query` | 查询任务 | 同步 | 免费 |

## 接口详情

### `submit` · 提交任务

**请求**：`POST /api/v1/apps/lipsync/submit`

**模式**：异步（提交后轮询任务） ｜ **计费**：以站内计费为准

创建一条数字人对口型任务，返回平台任务 ID

**输入上限**：参考音频 ≤ 1 个，参考视频 ≤ 1 个

数字人对口型任务，提供数字人视频 URL、驱动音频 URL 和可选的数字人模型标识。xiaojiayu1.0 须配置弹性部署策略；xiaojiayu2.0/3.0 会先自动创建数字人，创建完成后提交视频生成任务。 返回示例：`{ "task_id": 123, "status": "pending" }`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `fps` | string | 否 |  | 可选帧率参数。 |
| `mode` | string | 否 | `async_query` | 任务模式，默认 async_query |
| `model` | string | 否 | `xiaojiayu1.0` | 数字人模型标识，支持 xiaojiayu1.0、xiaojiayu2.0、xiaojiayu3.0；亦可使用简写 1.0、2.0、3.0。xiaojiayu1.0 需配置弹性部署策略；2.0 和 3.0 会自动创建数字人后生成视频。 |
| `audio_url` | string | **是** |  | 输入音频文件 URL（驱动口型的语音）　例：`https://example.com/speech.wav` |
| `video_url` | string | **是** |  | 输入视频文件 URL（数字人原始视频）　例：`https://example.com/avatar_video.mp4` |
| `video_params` | object | 否 |  | 视频生成可选参数对象。 |

```bash
python3 scripts/client.py call lipsync submit --json '{"audio_url": "https://example.com/speech.wav", "video_url": "https://example.com/avatar_video.mp4"}' --no-wait
```

官方文档全文：[`references/api-submit.md`](references/api-submit.md)

### `query` · 查询任务

**请求**：`POST /api/v1/apps/lipsync/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按平台任务 ID 查询状态与结果

根据 `submit` 返回的 `task_id` 查询执行状态与结果。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | **是** |  | 平台任务 ID |

```bash
python3 scripts/client.py call lipsync query --json '{"task_id": "<task_id>"}'
```

官方文档全文：[`references/api-query.md`](references/api-query.md)

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/通用说明.md` | 权限表、异步任务机制、常见错误、能力边界、计费口径 |
| `references/getting-started.md` | 注册、充值、获取与配置 API Key |
| `references/api-submit.md` | `submit` 的平台官方文档全文 + schema 原文 |
| `references/api-query.md` | `query` 的平台官方文档全文 + schema 原文 |
| `scripts/client.py` | 通用客户端（零依赖） |

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
