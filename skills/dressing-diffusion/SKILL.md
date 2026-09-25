---
name: dressing-diffusion
slug: dressing-diffusion
displayName: 三剪客 · AI换装
description: "智能图片换装，上传模特图和服装图，AI 自动完成试穿效果生成。支持上衣、下装、全身换装。模型可在后台 extra_config 中切换。支持 提交换装任务、查询换装结果。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「AI换装」的完整调用封装：2 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 换装
  - 图像生成
---

# AI换装

`api.a7w.cn` 插件 **`dressing_diffusion`**，共 **2 个接口**。提交图片换装任务，返回 task_id 用于查询结果

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema dressing_diffusion

# 3. 调用（示例）
python3 scripts/client.py call dressing_diffusion submit --json '{"garment": {}, "model_url": "https://example.com/model.jpg"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 提交换装任务 | 异步 | 按次固定价 0.1 点（租户价） |
| `query` | 查询换装结果 | 同步 | 免费 |

## 接口详情

### `submit` · 提交换装任务

**请求**：`POST /api/v1/apps/dressing_diffusion/submit`

**模式**：异步（提交后轮询任务） ｜ **计费**：按次固定价 0.1 点（租户价）

提交图片换装任务，返回 task_id 用于查询结果

上传模特图和服装图，AI 自动生成试穿效果。 支持单件上衣、单件下装、上下套装、连衣裙/全身装四种模式。 - 格式：JPG / JPEG / PNG，建议 JPG - 模特图：主体清晰、光线均匀 - 服装图：白底或纯色背景、平铺展示 { "model_url": "https://example.com/model.jpg", "garment": { "data": [ {"category": "upper", "url": "https://example.com/shirt.jpg"}, {"category": "bottom", "url": "https://example.com/pants.jpg"} ] } } {"task_id": "7xxxxxxxxxxxxxx", "status": "pending"} 提交成功后使用 `query` 接口轮询结果。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `garment` | object | **是** |  | 服装配置。格式：{"data": [{"category": "upper", "url": "服装图URL"}, ...]}。category 可选值：upper（上衣）、bottom（下装）、full（连衣裙/全身装）。支持单件或上下套装组合，服装图建议白底平铺。 |
| `model_url` | string | **是** |  | 模特图片 URL，建议主体清晰、光线均匀的正面或半身模特图。格式：JPG/PNG　例：`https://example.com/model.jpg` |

```bash
python3 scripts/client.py call dressing_diffusion submit --json '{"garment": {}, "model_url": "https://example.com/model.jpg"}' --no-wait
```

官方文档全文：[`references/api-submit.md`](references/api-submit.md)

### `query` · 查询换装结果

**请求**：`POST /api/v1/apps/dressing_diffusion/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

根据 task_id 查询换装任务状态和结果图片

根据 `submit` 返回的 `task_id` 查询换装任务状态和结果图片。 任务处理通常需要 10~30 秒，建议每 3~5 秒轮询一次。 {"task_id": "7xxxxxxxxxxxxxx", "status": "processing"} { "task_id": "7xxxxxxxxxxxxxx", "status": "done", "images": ["https://cdn.example.com/result_1.jpg"] }

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | **是** |  | 提交换装任务时返回的任务 ID　例：`7xxxxxxxxxxxxxx` |

```bash
python3 scripts/client.py call dressing_diffusion query --json '{"task_id": "7xxxxxxxxxxxxxx"}'
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
