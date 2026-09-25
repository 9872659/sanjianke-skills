---
name: person-replacement
slug: person-replacement
displayName: 三剪客 · 人物替换
description: "人物替换，基于参考图片和输入视频生成替换后的视频结果。支持 提交任务、查询任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「人物替换」的完整调用封装：2 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 人物替换
  - 视频编辑
---

# 人物替换

`api.a7w.cn` 插件 **`person_replacement`**，共 **2 个接口**。创建一条人物替换任务，返回平台任务 ID

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema person_replacement

# 3. 调用（示例）
python3 scripts/client.py call person_replacement submit --json '{"prompt": "一个女生在跳舞", "file_url": "https://example.com/person.png", "video_url": "https://example.com/input.mp4"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 提交任务 | 异步 | 按用量 2 点（租户价）；按用量 2 点/单位 |
| `query` | 查询任务 | 同步 | 免费 |

## 接口详情

### `submit` · 提交任务

**请求**：`POST /api/v1/apps/person_replacement/submit`

**模式**：异步（提交后轮询任务） ｜ **计费**：按用量 2 点（租户价）；按用量 2 点/单位

创建一条人物替换任务，返回平台任务 ID

**输入上限**：参考图 ≤ 1 张，参考视频 ≤ 1 个

**分档：`max`=3，`fast`=1，`standard`=2**

提交人物替换异步任务。接口接收一张或多张参考人物图片、一个输入视频、可选提示词、生成模式和处理人数，返回平台任务 ID。任务完成后使用“人物替换 · 查询任务”接口获取结果。 Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json 本接口按输入视频时长计费。平台会优先使用请求中的 `duration`，未传时会从 `video_url` 探测视频秒数。 | mode | 计费单位 | 默认价格 | | `fast` | 输入视频秒 | 1 点/秒 | | `standard` | 输入视频秒 | 2 点/秒 | | `max` | 输入视频秒 | 3 点/秒 | 实际扣费以当前租户 SKU 售价为准。提交成功时会先冻结预估点数，任务完成后按实际输入视频时长结算。 | 参数 | 类型 | 必填 | 默认值 | 说明 | | `type` | strin…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `mode` | enum | 否 | `standard` | 生成模式：fast 快速模式，standard 标准模式，max 高质量模式　可选值：`fast` / `standard` / `max` |
| `prompt` | string | 否 |  | 提示词　例：`一个女生在跳舞` |
| `file_url` | ['string', 'array'] | **是** |  | 参考图片 URL，支持单个 URL 或 URL 数组　例：`https://example.com/person.png` |
| `video_url` | string | **是** |  | 输入视频 URL　例：`https://example.com/input.mp4` |
| `face_count` | integer | 否 | `1` | 处理人数，范围 1 到 7 |

```bash
python3 scripts/client.py call person_replacement submit --json '{"prompt": "一个女生在跳舞", "file_url": "https://example.com/person.png", "video_url": "https://example.com/input.mp4"}' --no-wait
```

官方文档全文：[`references/api-submit.md`](references/api-submit.md)

### `query` · 查询任务

**请求**：`POST /api/v1/apps/person_replacement/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按平台任务 ID 查询状态与结果

根据提交接口返回的 `task_id` 查询人物替换任务状态、生成结果与计费信息。查询接口不重复计费。 Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json | 参数 | 类型 | 必填 | 说明 | | `task_id` | string | 是 | 提交任务接口返回的平台任务 ID，例如 `task_xxxxxxxxxxxxxxxx`。 | { "task_id": "task_xxxxxxxxxxxxxxxx" } curl -X POST "https://你的域名/api/v1/apps/person_replacement/query" \ -H "Authorization: Bearer <YOUR_API_KEY>" \ -H "Content-Type: application/json" \ -d '{ "task_id":…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | **是** |  | 平台任务 ID |

```bash
python3 scripts/client.py call person_replacement query --json '{"task_id": "<task_id>"}'
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
