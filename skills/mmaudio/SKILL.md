---
name: mmaudio
slug: mmaudio
displayName: 三剪客 · 音效生成、视频配音
description: "音效生成、视频配音，任务由平台弹性部署调度。支持 提交任务、查询任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「音效生成、视频配音」的完整调用封装：2 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 音效生成
  - 音频
---

# 音效生成、视频配音

`api.a7w.cn` 插件 **`mmaudio`**，共 **2 个接口**。创建一条弹性 GPU 任务，返回平台任务 id

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema mmaudio

# 3. 调用（示例）
python3 scripts/client.py call mmaudio submit --json '{"prompt": "Generate natural cinematic sound effects and ambience for this video.", "duration": 15.695, "audio_url": "https://example.com/reference_audio.wav", "input_url": "https://example.com/silent_video.mp4"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 提交任务 | 异步 | 按次固定价 0.1 点（租户价） |
| `query` | 查询任务 | 同步 | 按次固定价 0.1 点（租户价） |

## 接口详情

### `submit` · 提交任务

**请求**：`POST /api/v1/apps/mmaudio/submit`

**模式**：异步（提交后轮询任务） ｜ **计费**：按次固定价 0.1 点（租户价）

创建一条弹性 GPU 任务，返回平台任务 id

**输入上限**：参考音频 ≤ 1 个

音效生成、视频配音任务，提供视频 URL、可选 duration 视频时长和可选 prompt 音频生成提示词，平台将自动生成匹配的音频配音。可选提供参考音频 URL。 返回示例：`{ "task_id": 123, "status": "pending" }`（task_id 为弹性任务主键）

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `mode` | string | 否 | `async_query` | 任务模式，默认 async_query |
| `prompt` | string | 否 |  | 音频生成提示词，用于描述期望的音效、环境声或配乐风格；未传时使用系统默认提示词　例：`Generate natural cinematic sound effects and ambience for this video.` |
| `duration` | number | 否 |  | 输入视频时长，单位秒；未传时平台从 input_url 探测　例：`15.695` |
| `audio_url` | string | 否 |  | 可选的输入音频 URL，用于参考配音风格　例：`https://example.com/reference_audio.wav` |
| `input_url` | string | **是** |  | 输入视频文件 URL　例：`https://example.com/silent_video.mp4` |

```bash
python3 scripts/client.py call mmaudio submit --json '{"prompt": "Generate natural cinematic sound effects and ambience for this video.", "duration": 15.695, "audio_url": "https://example.com/reference_audio.wav", "input_url": "https://example.com/silent_video.mp4"}' --no-wait
```

官方文档全文：[`references/api-submit.md`](references/api-submit.md)

### `query` · 查询任务

**请求**：`POST /api/v1/apps/mmaudio/query`

**模式**：同步（直接返回结果） ｜ **计费**：按次固定价 0.1 点（租户价）

按弹性任务 id 查询状态与结果

根据 `submit` 返回的 `task_id` 查询执行状态与结果。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | integer | 否 |  | 同 elastic_task_id |
| `elastic_task_id` | integer | 否 |  | 弹性任务 id（与 task_id 二选一） |

```bash
python3 scripts/client.py call mmaudio query --json '{}'
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
