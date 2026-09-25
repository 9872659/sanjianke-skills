---
name: wan-video
slug: wan-video
displayName: 三剪客 · Wan 视频生成
description: "Wan 模型族视频生成应用。版本通过 model 参数选择，支持文生视频、角色参考生视频与视频编辑。支持 查询视频任务、创建视频任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "「Wan 视频生成」的完整调用封装：2 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 视频生成
  - 文生视频
---

# Wan 视频生成

`api.a7w.cn` 插件 **`wan`**，共 **2 个接口**。按平台 task_id 查询 Wan 任务状态与结果。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema wan

# 3. 调用（示例）
python3 scripts/client.py call wan query --json '{"task_id": "task_xxxxxxxxxxxx"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `query` | 查询视频任务 | 同步 | 免费 |
| `create` | 创建视频任务 | 异步 | 免费 |

## 接口详情

### `query` · 查询视频任务

**请求**：`POST /api/v1/apps/v1/tasks/{task_id}`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按平台 task_id 查询 Wan 任务状态与结果。

按平台 `task_id` 查询 Wan 视频任务状态、视频 URL 和计费快照。本接口只读取平台任务表中的数据。 <details> <summary>基本信息</summary> | 字段 | 内容 | | 类型 | 应用 API | | 应用编码 | `wan` | | API 编码 | `query` | | 请求方式 | `GET` | | 请求路径 | `/api/v1/apps/wan/query` | | 调用模式 | 同步 | | 计费方式 | 免费查询 | </details> Authorization: Bearer <YOUR_API_KEY> GET /api/v1/apps/wan/query?task_id={task_id} | 参数 | 类型 | 必填 | 示例 | 说明 | | `task_id` | string | 是 | `task_xxxxxxxxxxxx` | 创建接口返回的平台任…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | 否 |  | 创建任务后返回的平台任务 ID。　例：`task_xxxxxxxxxxxx` |

```bash
python3 scripts/client.py call wan query --json '{"task_id": "task_xxxxxxxxxxxx"}'
```

官方文档全文：[`references/api-query.md`](references/api-query.md)

### `create` · 创建视频任务

**请求**：`POST /api/v1/apps/v1/videos/generations`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

提交 Wan 视频生成任务。model 用于选择 Wan 版本与能力。

**输入上限**：参考图 ≤ 9 张，参考音频 ≤ 5 个，参考视频 ≤ 5 个

**分档：`models`={'720p': {'with_video': 47.81, 'without_video': 47.81}, '1080p': {'with_video': 78.91, 'without_video': 78.91}}**

提交 Wan 模型族视频任务。用户只对接平台统一接口；平台会按 `model` 选择对应能力，并负责参数过滤、任务入库、扣点冻结和轮询转存。 <details> <summary>基本信息</summary> | 字段 | 内容 | | 类型 | 应用 API | | 应用编码 | `wan` | | API 编码 | `create` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/wan/create` | | 调用模式 | 异步 | | 计费方式 | 按生成时长计费，单价来自租户价格矩阵 | </details> Authorization: Bearer <YOUR_API_KEY> Content-Type: application/json 提交成功后返回平台 `task_id`。请使用 `GET /api/v1/apps/wan/query?task_id={task_id}`…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `seed` | integer | 否 |  | 随机种子，用于结果复现。范围：0-2147483647。 |
| `size` | string | 否 |  | 视频画幅比例。　例：`16:9` |
| `model` | string | 否 |  | Wan 模型版本。不同版本支持的素材输入略有差异。　例：`wan2.7` |
| `prompt` | string | 否 |  | 视频画面与运动描述。　例：`一辆复古跑车沿着海岸公路行驶，电影感光影` |
| `duration` | integer | 否 | `5` | 生成视频时长，单位秒。wan2.7、wan2.7-r2v 支持 2-15；wan2.7-videoedit 支持 2-10。　例：`5` |
| `metadata` | object | 否 |  | 附加业务信息。wan2.7-videoedit 可在 metadata.audio_setting 中选择音频处理方式。　例：`{'biz_id': 'order_1001', 'audio_setting': 'auto'}` |
| `audio_url` | string | 否 |  | 参考音频 URL。需要音频驱动生成时传入。　例：`https://example.com/audio.mp3` |
| `watermark` | boolean | 否 |  | 是否添加水印。 |
| `image_urls` | array | 否 |  | 参考图片 URL 列表。wan2.7 最多 2 张；wan2.7-videoedit 最多 4 张。　例：`['https://example.com/reference.png']` |
| `resolution` | string | 否 | `720p` | 输出分辨率。　例：`720p` |
| `video_urls` | array | 否 |  | 视频素材地址列表，最多 1 段。wan2.7-videoedit 必填，并按含视频输入档计费。　例：`['https://example.com/input.mp4']` |
| `callback_url` | string | 否 |  | 任务完成或失败时由平台主动通知的 HTTPS 地址。　例：`https://your-domain.com/webhook/wan` |
| `prompt_extend` | boolean | 否 |  | 是否启用提示词扩展。 |
| `negative_prompt` | string | 否 |  | 不希望出现在画面中的内容。 |
| `image_with_roles` | array | 否 |  | 角色或参考图列表。wan2.7-r2v 必填，最多 2 张。　例：`[{'url': 'https://example.com/role.png', 'role': 'reference_image'}]` |

```bash
python3 scripts/client.py call wan create --json '{"size": "16:9", "prompt": "一辆复古跑车沿着海岸公路行驶，电影感光影", "metadata": {"biz_id": "order_1001", "audio_setting": "auto"}, "audio_url": "https://example.com/audio.mp3", "image_urls": ["https://example.com/reference.png"], "video_urls": ["https://example.com/input.mp4"], "callback_url": "https://your-domain.com/webhook/wan", "image_with_roles": [{"url": "https://example.com/role.png", "role": "reference_image"}]}' --no-wait
```

官方文档全文：[`references/api-create.md`](references/api-create.md)

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/通用说明.md` | 权限表、异步任务机制、常见错误、能力边界、计费口径 |
| `references/getting-started.md` | 注册、充值、获取与配置 API Key |
| `references/api-query.md` | `query` 的平台官方文档全文 + schema 原文 |
| `references/api-create.md` | `create` 的平台官方文档全文 + schema 原文 |
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
