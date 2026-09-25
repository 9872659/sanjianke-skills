---
name: nano-banana-image
slug: nano-banana-image
displayName: 三剪客 · nano-banana
description: "图片生成与编辑应用，支持文生图、图生图和多规格模型选择。支持 创建图片任务、查询图片任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「nano-banana」的完整调用封装：2 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 图像生成
  - 文生图
---

# nano-banana

`api.a7w.cn` 插件 **`nano_banana`**，共 **2 个接口**。提交图片生成或编辑任务，返回平台任务 ID。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema nano_banana

# 3. 调用（示例）
python3 scripts/client.py call nano_banana submit --json '{"prompt": "A clean product photo of a yellow banana-shaped speaker on a white table.", "image_urls": ["https://example.com/reference.png"], "aspect_ratio": "1:1", "callback_url": "https://example.com/api/ai/callback"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 创建图片任务 | 异步 | 免费 |
| `query` | 查询图片任务 | 同步 | 免费 |

## 接口详情

### `submit` · 创建图片任务

**请求**：`POST /api/v1/apps/nano_banana/submit`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

提交图片生成或编辑任务，返回平台任务 ID。

**输入上限**：参考图 ≤ 12 张

提交图片生成或编辑任务。接口返回平台 `task_id`，客户端通过查询接口或统一任务查询接口获取结果。 | 字段 | 内容 | | 应用编码 | `nano_banana` | | API 编码 | `submit` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/nano_banana/submit` | | 调用模式 | 异步 | | 默认模型 | `nano-banana` | | 默认分辨率 | `1K` | Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 默认值 | 可选值 / 格式 | 说明 | | `prompt` | string | 是 | - | - | 图片内容、主体、风格、构图和细节描述 | | `action` | string | 否 | `…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `model` | string | 否 | `nano-banana` | 模型规格。普通模型适合常规生成，官方模型适合更高一致性和高清档位。　例：`nano-banana` |
| `action` | string | 否 | `generate` | 任务类型。generate 为文生图，edit 为基于参考图编辑。　例：`generate` |
| `prompt` | string | 否 |  | 图片内容、风格、主体和细节描述。　例：`A clean product photo of a yellow banana-shaped speaker on a white table.` |
| `image_urls` | array | 否 |  | 参考图片 URL 列表。action=edit 时必填。　例：`['https://example.com/reference.png']` |
| `resolution` | string | 否 | `1K` | 输出分辨率。官方高清模型按 1K、2K、4K 分档计费。　例：`1K` |
| `aspect_ratio` | string | 否 |  | 图片宽高比。　例：`1:1` |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址。　例：`https://example.com/api/ai/callback` |

```bash
python3 scripts/client.py call nano_banana submit --json '{"prompt": "A clean product photo of a yellow banana-shaped speaker on a white table.", "image_urls": ["https://example.com/reference.png"], "aspect_ratio": "1:1", "callback_url": "https://example.com/api/ai/callback"}' --no-wait
```

官方文档全文：[`references/api-submit.md`](references/api-submit.md)

### `query` · 查询图片任务

**请求**：`POST /api/v1/apps/nano_banana/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按平台 task_id 查询任务状态与图片结果。

按平台 `task_id` 查询任务状态与图片结果。本接口只读取平台任务，不产生新的扣点。 | 字段 | 内容 | | 应用编码 | `nano_banana` | | API 编码 | `query` | | 请求方式 | `GET` | | 请求路径 | `/api/v1/apps/nano_banana/query` | | 调用模式 | 同步 | | 是否计费 | 否 | GET /api/v1/apps/nano_banana/query?task_id=task_xxxxxxxxxxxx Authorization: Bearer <YOUR_API_KEY> | 参数 | 类型 | 必填 | 说明 | | `task_id` | string | 是 | 创建图片任务接口返回的平台任务 ID | { "code": 1, "msg": "success", "data": { "result": { "status…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | 否 |  | 创建任务后返回的平台任务 ID。　例：`task_xxxxxxxxxxxx` |

```bash
python3 scripts/client.py call nano_banana query --json '{"task_id": "task_xxxxxxxxxxxx"}'
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
