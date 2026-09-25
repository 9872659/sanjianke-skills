---
name: full-video
slug: full-video
displayName: 三剪客 · 全能视频生成
description: "支持文生视频、首尾帧视频生成及多模态参考视频生成。支持 提交任务、查询任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「全能视频生成」的完整调用封装：2 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 长视频
  - 成片
---

# 全能视频生成

`api.a7w.cn` 插件 **`full_video`**，共 **2 个接口**。创建一条全能视频生成任务，返回平台任务 ID。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema full_video

# 3. 调用（示例）
python3 scripts/client.py call full_video submit --json '{"content": []}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 提交任务 | 异步 | 免费 |
| `query` | 查询任务 | 同步 | 免费 |

## 接口详情

### `submit` · 提交任务

**请求**：`POST /api/v1/apps/full_video/submit`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

创建一条全能视频生成任务，返回平台任务 ID。

全能视频生成任务须传入一条文本内容。输出分辨率支持 480P、768P、1080P、2K 和 4K。首帧和尾帧各最多 1 张；参考图片最多 9 张，参考视频和参考音频各最多 3 个。首尾帧模式不能与参考媒体模式混用；参考媒体模式至少包含 1 张参考图片或 1 个参考视频，不能只传参考音频。时长仅支持 4 到 15 秒整数；768P、1080P、2K 的文本总长度最多 5000 个字符，其他分辨率最多 7000 个字符。 计费：按分辨率 SKU 和生成时长计量；默认前 5 张 reference_image 免费，超出部分每张加 20 点，实际规则以当前应用配置为准。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `model` | string | 否 | `full-video` | 视频生成模型标识，固定为 full-video。　例：`full-video` |
| `ratio` | string | 否 | `16:9` | 视频画幅比例；图生视频可使用 adaptive。　例：`16:9` |
| `content` | array | **是** |  | 内容列表，须包含文本项；可按模式传入首帧、尾帧或参考媒体。 |
| `duration` | integer | 否 | `4` | 生成时长，单位秒，范围 4 到 15。　例：`4` |
| `resolution` | enum | 否 | `480P` | 输出分辨率；不同分辨率对应独立的按秒 SKU，具体售价以当前租户价格配置为准。　可选值：`480P` / `768P` / `1080P` / `2K` / `4K` |
| `aigc_watermark` | boolean | 否 | `False` | 是否添加生成标识。　例：`False` |

```bash
python3 scripts/client.py call full_video submit --json '{"content": []}' --no-wait
```

官方文档全文：[`references/api-submit.md`](references/api-submit.md)

### `query` · 查询任务

**请求**：`POST /api/v1/apps/full_video/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按平台任务 ID 查询状态与结果。

根据 `submit` 返回的 `task_id` 查询执行状态与结果。查询接口不重复计费。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | 否 |  | 提交接口返回的平台任务 ID。与 elastic_task_id 二选一。 |
| `elastic_task_id` | integer | 否 |  | 兼容弹性任务数字 ID。与 task_id 二选一。 |

```bash
python3 scripts/client.py call full_video query --json '{}'
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
