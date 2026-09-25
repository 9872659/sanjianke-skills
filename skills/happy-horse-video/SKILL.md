---
name: happy-horse-video
slug: happy-horse-video
displayName: 三剪客 · Happy Horse
description: "Happy Horse（HappyHorse-1.1 系列）面向文生/图生高质量短视频，采用统一多模态建模，可一阶段生成声画、支持多语言对白与多镜头场景衔接。计费按目标分辨率与生成秒数对应的参数档位计点。本能力为内测邀请制，正式调用前需完成内测申请。支持 提交任务、创建任务、查询任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.3
summary: "「Happy Horse」的完整调用封装：3 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 文生视频
  - 视频生成
---

# Happy Horse

`api.a7w.cn` 插件 **`happy_horse`**，共 **3 个接口**。提交文生/图生视频任务（矩阵点数/秒 × 目标时长，内测中）

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema happy_horse

# 3. 调用（示例）
python3 scripts/client.py call happy_horse submit --json '{"seed": 42, "media": [{"url": "https://example.com/input.mp4", "type": "video"}, {"url": "https://example.com/ref1.jpg", "type": "image"}], "model": "happyhorse-1.1-t2v", "ratio": "16:9", "prompt": "一只猫在草地上奔跑", "watermark": true}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 提交任务 | 异步 | 免费 |
| `create` | 创建任务 | 异步 | 免费 |
| `query` | 查询任务 | 同步 | 免费 |

## 接口详情

### `submit` · 提交任务

**请求**：`POST /api/v1/apps/happy_horse/submit`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

提交文生/图生视频任务（矩阵点数/秒 × 目标时长，内测中）

**输入上限**：参考图 ≤ 9 张，参考视频 ≤ 1 个

**分档：`720p`=0.9，`1080p`=1.6**

创建一条视频生成任务，返回平台 `task_id`。 计费为 **定价矩阵（点数/秒）× 目标时长**：矩阵按输出分辨率 × 是否含视频输入分档（与 Seedance 矩阵 JSON 同形；Happy Horse 通常两档填相同点数/秒）。 平台需在应用管理中配置可用的服务地址与密钥；未配置时提交将提示服务未就绪。 - `resolution`：`720P` 或 `1080P` - `duration`：目标时长(秒)，文生 / 图生 / 多参考支持 3～15 秒；视频编辑时长由输入视频决定 - `prompt`：文本描述，必填 - `model`：能力代号，决定文生、图生、多参考或视频编辑 - `media`：统一参考素材数组；视频编辑传 1 个 video，可附参考图 { "resolution": "720P", "duration": 5, "prompt": "都市夜景，车流水灯，中景推进镜头" }

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `seed` | number | 否 |  | 随机种子，用于尽量复现生成效果；不传则随机　例：`42` |
| `media` | array | 否 |  | 统一参考素材数组。文生不传；单图首帧传 1 张 image；多参考传 1～9 张 image（建议至少 2 张）；视频编辑传 1 个 video，可附 0～5 张 image　例：`[{'url': 'https://example.com/input.mp4', 'type': 'video'}, {'url': 'https://example.com/ref1.jpg', 'type': 'image'}]` |
| `model` | string | **是** |  | 生成能力代号，决定 media 的使用规则　例：`happyhorse-1.1-t2v` |
| `ratio` | string | 否 |  | 画幅比例；文生和多参考可传，单图首帧不需要传　例：`16:9` |
| `prompt` | string | **是** |  | 画面、镜头、风格与对白等描述；最多 2500 字，不能为空　例：`一只猫在草地上奔跑` |
| `duration` | number | **是** |  | 目标视频时长(秒)，整数；文生、图生、多参考支持 3～15 秒。本平台按该值计费　例：`5` |
| `watermark` | boolean | 否 |  | 是否添加水印；不传默认 true　例：`True` |
| `resolution` | string | **是** |  | 目标分辨率；支持 720P、1080P（也接受小写，平台会归一）　例：`720P` |

```bash
python3 scripts/client.py call happy_horse submit --json '{"seed": 42, "media": [{"url": "https://example.com/input.mp4", "type": "video"}, {"url": "https://example.com/ref1.jpg", "type": "image"}], "model": "happyhorse-1.1-t2v", "ratio": "16:9", "prompt": "一只猫在草地上奔跑", "watermark": true}' --no-wait
```

官方文档全文：[`references/api-submit.md`](references/api-submit.md)

### `create` · 创建任务

**请求**：`POST /api/v1/apps/happy_horse/create`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

创建视频生成任务（happyhorse 渠道，矩阵点数/秒 × 目标时长）

**输入上限**：参考图 ≤ 9 张

**分档：`720p`=0.9，`1080p`=1.6**

与 `submit` 入参完全一致，但锁死 happyhorse 渠道：内部走 aorizon `/api/v2/tasks` 流水线， 需要在应用配置里填入 `api_secret`（aorizon Bearer token），可选 `extra_config.happyhorse_base_url` 覆盖默认网关。 计费同 submit：**点数/秒 × 目标时长**，矩阵按输出分辨率 × 是否含视频输入分档（独立维护，可与 submit 不同）。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `seed` | number | 否 |  | 随机种子；happyhorse 渠道暂不透传至上游，保留位以便日后启用　例：`42` |
| `media` | array | 否 |  | 统一参考素材数组。文生不传；图生 / 多参考传 1～9 张 image。happyhorse 渠道仅支持 image 类型　例：`[{'url': 'https://example.com/ref1.jpg', 'type': 'image'}]` |
| `model` | string | **是** |  | 生成能力代号；create 接口不支持 video-edit　例：`happyhorse-1.1-t2v` |
| `ratio` | string | 否 |  | 画幅比例；文生和多参考可传　例：`16:9` |
| `prompt` | string | **是** |  | 画面、镜头、风格与对白等描述；最多 2500 字，不能为空　例：`一只猫在草地上奔跑` |
| `duration` | number | **是** |  | 目标视频时长(秒)，整数；文生 / 图生 / 多参考支持 3～15 秒。本平台按该值计费　例：`5` |
| `watermark` | boolean | 否 |  | 是否添加水印；happyhorse 渠道暂不透传至上游，保留位以便日后启用　例：`True` |
| `resolution` | string | **是** |  | 目标分辨率；支持 720P、1080P（也接受小写，平台会归一）　例：`720P` |

```bash
python3 scripts/client.py call happy_horse create --json '{"seed": 42, "media": [{"url": "https://example.com/ref1.jpg", "type": "image"}], "model": "happyhorse-1.1-t2v", "ratio": "16:9", "prompt": "一只猫在草地上奔跑", "watermark": true}' --no-wait
```

官方文档全文：[`references/api-create.md`](references/api-create.md)

### `query` · 查询任务

**请求**：`POST /api/v1/apps/happy_horse/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按 task_id 查询任务状态与结果

按平台 `task_id` 拉取处理状态与结果。接口 **同步调用**，可与异步 submit 配合。 **内测期未放通时，会返回与 submit 一致的内测提示。**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | **是** |  | submit 返回的平台任务 id　例：`task_xxxxxxxxxxxxxxxx` |

```bash
python3 scripts/client.py call happy_horse query --json '{"task_id": "task_xxxxxxxxxxxxxxxx"}'
```

官方文档全文：[`references/api-query.md`](references/api-query.md)

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/通用说明.md` | 权限表、异步任务机制、常见错误、能力边界、计费口径 |
| `references/getting-started.md` | 注册、充值、获取与配置 API Key |
| `references/api-submit.md` | `submit` 的平台官方文档全文 + schema 原文 |
| `references/api-create.md` | `create` 的平台官方文档全文 + schema 原文 |
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
