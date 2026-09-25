---
name: grok-video
slug: grok-video
displayName: 三剪客 · Grok 视频生成
description: "Grok 视频生成应用，支持快速视频生成和标准生成视频。支持 创建视频任务、查询视频任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「Grok 视频生成」的完整调用封装：2 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 视频生成
  - 图生视频
---

# Grok 视频生成

`api.a7w.cn` 插件 **`grok_video`**，共 **2 个接口**。提交 Grok 视频生成任务，返回平台任务 ID。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema grok_video

# 3. 调用（示例）
python3 scripts/client.py call grok_video submit --json '{"image_urls": ["https://example.com/main.jpg", "https://example.com/style.jpg"]}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 创建视频任务 | 异步 | 免费 |
| `query` | 查询视频任务 | 同步 | 免费 |

## 接口详情

### `submit` · 创建视频任务

**请求**：`POST /api/v1/apps/grok_video/submit`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

提交 Grok 视频生成任务，返回平台任务 ID。

**输入上限**：参考图 ≤ 7 张

创建接口始终异步返回。提交成功后立即获得平台 `task_id`。 | 名称 | 值 | | `Authorization` | `Bearer YOUR_API_KEY` | | `Content-Type` | `application/json` | | 参数 | 类型 | 必填 | 说明 | | `model` | string | 是 | `grok-imagine-video-1.5-fast` 或 `grok-imagine-video-1.5` | | `prompt` | string | 条件必填 | 快速生成未传 `image_urls` 时必填 | | `duration` | integer | 否 | 默认 8。快速生成范围 1-30；标准生成范围 1-15 | | `image_urls` | array | 条件必填 | 输入图片地址列表。第一张作为主图，其余图片作为参考图；标准生成至少需要一张…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `model` | string | 否 | `grok-imagine-video-1.5-fast` | 视频模型规格。 |
| `prompt` | string | 否 |  | 视频内容描述。快速生成在未提供 image_urls 时必填。 |
| `duration` | integer | 否 | `8` | 视频时长（秒）。快速生成支持 1-30，标准生成支持 1-15。 |
| `image_urls` | array | 否 |  | 输入图片地址列表。第一张作为主图，其余图片作为参考图；标准生成模型至少需要一张。　例：`['https://example.com/main.jpg', 'https://example.com/style.jpg']` |
| `resolution` | string | 否 | `480p` | 输出分辨率，影响价格。 |
| `aspect_ratio` | string | 否 |  | 视频宽高比。 |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址。 |

```bash
python3 scripts/client.py call grok_video submit --json '{"image_urls": ["https://example.com/main.jpg", "https://example.com/style.jpg"]}' --no-wait
```

官方文档全文：[`references/api-submit.md`](references/api-submit.md)

### `query` · 查询视频任务

**请求**：`POST /api/v1/apps/grok_video/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按平台任务 ID 查询 Grok 视频生成状态和视频结果。

`GET /api/v1/apps/grok_video/query?task_id=task_xxxxxxxxxxxx` 查询接口只读取平台任务状态，不扣点。 | 名称 | 值 | | `Authorization` | `Bearer YOUR_API_KEY` | | 参数 | 类型 | 必填 | 说明 | | `task_id` | string | 是 | 创建任务接口返回的平台任务 ID | | 状态 | 说明 | | `pending` | 任务已创建，等待处理 | | `processing` | 任务正在生成 | | `succeeded` | 任务成功，返回 `video_url` | | `failed` | 任务失败，返回错误信息 | { "code": 1, "msg": "success", "data": { "result": { "task_id": "task_xxxxxxxxxxxx", "…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | 否 |  | 创建视频任务后返回的平台任务 ID。　例：`task_xxxxxxxxxxxx` |

```bash
python3 scripts/client.py call grok_video query --json '{"task_id": "task_xxxxxxxxxxxx"}'
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
