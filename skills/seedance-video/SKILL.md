---
name: seedance-video
slug: seedance-video
displayName: 三剪客 · Seedance 2.0
description: "基于火山方舟 Seedance 2.0 的多模态视频生成应用。支持文本/图片/视频/音频任意组合输入，可输出 480p/720p/1080p 分辨率、4~15 秒时长的视频，并可选生成同步音频。按 token 计费，按分辨率和是否含视频输入分档。支持 创建素材资产组合、上传素材、获取素材详情、更新素材、删除素材、查询任务、创建任务。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.3
summary: "「Seedance 2.0」的完整调用封装：7 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 视频生成
  - 图生视频
---

# Seedance 2.0

`api.a7w.cn` 插件 **`seedance`**，共 **7 个接口**。创建 Asset Group（素材资产组合），上传素材前需先创建分组。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema seedance

# 3. 调用（示例）
python3 scripts/client.py call seedance createGroup --json '{"Name": "demo-group", "GroupType": "AIGC"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `createGroup` | 创建素材资产组合 | 同步 | 免费 |
| `createAsset` | 上传素材 | 同步 | 免费 |
| `getAsset` | 获取素材详情 | 同步 | 免费 |
| `updateAsset` | 更新素材 | 同步 | 免费 |
| `deleteAsset` | 删除素材 | 同步 | 免费 |
| `query` | 查询任务 | 同步 | 免费 |
| `create` | 创建任务 | 异步 | 免费 |

## 接口详情

### `createGroup` · 创建素材资产组合

**请求**：`POST /api/v1/apps/ant/createAssetGroup`

**模式**：同步（直接返回结果） ｜ **计费**：免费

创建 Asset Group（素材资产组合），上传素材前需先创建分组。

Content-Type: `multipart/form-data` 同步接口；调用成功后返回上游 `Result.Id`，用于后续上传素材时填入 `GroupId`。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `Name` | string | **是** |  | Asset Group 名称，上限 64 字符　例：`demo-group` |
| `GroupType` | string | 否 |  | 分组类型；AIGC 表示虚拟人像分组　例：`AIGC` |
| `Description` | string | 否 |  | 分组描述，上限 300 字符 |
| `ProjectName` | string | 否 | `default` | 项目名称，默认 default；非默认项目需填写正确名称 |

```bash
python3 scripts/client.py call seedance createGroup --json '{"Name": "demo-group", "GroupType": "AIGC"}'
```

官方文档全文：[`references/api-createGroup.md`](references/api-createGroup.md)

### `createAsset` · 上传素材

**请求**：`POST /api/v1/apps/ant/createAsset`

**模式**：同步（直接返回结果） ｜ **计费**：免费

将公网可访问的素材文件上传到指定 Asset Group。支持图像 / 视频 / 音频。

Content-Type: `multipart/form-data` 上游会异步处理素材，调用 `getAsset` 查询 `Status` 为 `Active` 后即可在创建任务中以 `asset://<ASSET_ID>` 引用。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `URL` | string | **是** |  | 素材公网可访问 URL；将由上游拉取并入库　例：`https://your-domain.com/uploads/image.png` |
| `Name` | string | 否 |  | 素材名称，上限 64 字符 |
| `GroupId` | string | **是** |  | Asset 所属的 Asset Group Id（来自 createGroup 返回的 Result.Id）　例：`group-20260402173639-97brg` |
| `AssetType` | string | **是** |  | 素材类型：Image / Video / Audio　例：`Image` |
| `ProjectName` | string | 否 | `default` | 项目名称，默认 default |

```bash
python3 scripts/client.py call seedance createAsset --json '{"URL": "https://your-domain.com/uploads/image.png", "GroupId": "group-20260402173639-97brg", "AssetType": "Image"}'
```

官方文档全文：[`references/api-createAsset.md`](references/api-createAsset.md)

### `getAsset` · 获取素材详情

**请求**：`POST /api/v1/apps/ant/getAsset`

**模式**：同步（直接返回结果） ｜ **计费**：免费

查询素材信息，包括状态（Active / Processing / Failed）、URL、所属分组等。

Content-Type: `multipart/form-data` `Result.Status`： - Active：处理完毕，可以使用 - Processing：正在预处理 - Failed：处理失败

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `Id` | string | **是** |  | Asset Id（来自 createAsset 返回的 Result.Id）　例：`asset-20260402224305-54j64` |
| `ProjectName` | string | 否 | `default` | 项目名称，默认 default |

```bash
python3 scripts/client.py call seedance getAsset --json '{"Id": "asset-20260402224305-54j64"}'
```

官方文档全文：[`references/api-getAsset.md`](references/api-getAsset.md)

### `updateAsset` · 更新素材

**请求**：`POST /api/v1/apps/ant/updateAsset`

**模式**：同步（直接返回结果） ｜ **计费**：免费

更新素材的名称等元数据。

Content-Type: `multipart/form-data`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `Id` | string | **是** |  | Asset Id　例：`asset-20260402224305-54j64` |
| `Name` | string | 否 |  | 新的素材名称，上限 64 字符 |
| `ProjectName` | string | 否 | `default` | 项目名称，默认 default |

```bash
python3 scripts/client.py call seedance updateAsset --json '{"Id": "asset-20260402224305-54j64"}'
```

官方文档全文：[`references/api-updateAsset.md`](references/api-updateAsset.md)

### `deleteAsset` · 删除素材

**请求**：`POST /api/v1/apps/ant/deleteAsset`

**模式**：同步（直接返回结果） ｜ **计费**：免费

删除指定素材；删除后无法在创建任务中再以 asset:// 形式引用。

Content-Type: `multipart/form-data`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `Id` | string | **是** |  | Asset Id　例：`asset-20260402224305-54j64` |
| `ProjectName` | string | 否 | `default` | 项目名称，默认 default |

```bash
python3 scripts/client.py call seedance deleteAsset --json '{"Id": "asset-20260402224305-54j64"}'
```

官方文档全文：[`references/api-deleteAsset.md`](references/api-deleteAsset.md)

### `query` · 查询任务

**请求**：`POST /api/v1/apps/ant/query`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按服务任务 ID 查询 Seedance 任务状态（平台服务）

`GET /api/v1/tasks/{task_id}` 直接查询 maplego 网关任务状态；不计费或按 0 点固定价。 常规集成更推荐使用开放平台统一任务接口：`GET /api/v1/tasks/{task_id}`（使用本平台的 task_id）。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task_id` | string | 否 |  | 上游返回的任务 ID（与创建接口响应 data.id 一致）。也可使用查询参数 id。　例：`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |

```bash
python3 scripts/client.py call seedance query --json '{"task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}'
```

官方文档全文：[`references/api-query.md`](references/api-query.md)

### `create` · 创建任务

**请求**：`POST /api/v1/apps/ant/createTask`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

提交 Seedance 2.0 视频生成任务。支持文生/图生/视频编辑/延长/多模态参考等场景。

**输入上限**：参考图 ≤ 9 张，参考音频 ≤ 3 个，参考视频 ≤ 3 个

**分档：`480p`=3000/5000，`720p`=3200/5500，`1080p`=3500/6000**

异步任务：提交后返回 `task_id`，可通过 `GET /api/v1/tasks/{task_id}` 或 `GET /api/v1/tasks/{task_id}` 查询进度与结果。 请求体中的 `model` 只能使用下表的公开模型名称。模型类型、名称和适用场景一一对应： | 模型类型 | 模型名称 | 描述 | | Seedance 2.0 标准版 | `seedance-2-text-2-video` | 输入内容不包含视频，适合文生视频、图生视频、首尾帧生成 | | Seedance 2.0 标准版 | `seedance-2-video-2-video` | 输入内容包含视频，适合视频编辑、视频延长、视频参考 | | Seedance 2.0 快速版 | `seedance-2-fast-text-2-video` | 输入内容不包含视频，优先生成速度 | | Seedance 2.0 快速版 | `seeda…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `seed` | integer | 否 |  | 随机种子，可复现结果（若上游支持） |
| `draft` | boolean | 否 |  | 是否草稿模式（若上游支持） |
| `model` | string | 否 |  | 公开模型名称。请从模型名称与使用场景表中选择一个名称。　例：`seedance-2-text-2-video` |
| `ratio` | string | 否 | `adaptive` | 画面宽高比。adaptive 表示由模型根据输入自动选择　例：`16:9` |
| `tools` | array | 否 |  | 可选工具（仅文生视频支持 web_search 联网搜索）　例：`[{'type': 'web_search'}]` |
| `frames` | integer | 否 |  | 帧数相关参数（若上游支持） |
| `content` | array | 否 |  | 多模态输入列表：支持 文本 + 图片 + 视频 + 音频 的任意组合。图片最多 9 张、视频最多 3 个、音频最多 3 段，且不可单独传音频。含 video_url 时按「含视频输入」档位计费。　例：`[{'text': '一只金毛犬在海边奔跑，夕阳西下', 'type': 'text'}]` |
| `duration` | integer | 否 | `5` | 生成视频时长（秒）。取值 4~15，或 -1 由模型自动决定　例：`5` |
| `watermark` | boolean | 否 |  | 是否在视频右下角添加水印 |
| `resolution` | string | 否 | `720p` | 输出分辨率　例：`720p` |
| `callback_url` | string | 否 |  | 异步任务完成/失败时的回调地址　例：`https://your-domain.com/webhook/seedance` |
| `camera_fixed` | boolean | 否 |  | 是否固定机位（若上游支持） |
| `service_tier` | string | 否 |  | 服务档位（若上游支持） |
| `generate_audio` | boolean | 否 | `1` | 是否生成与画面同步的音频　例：`1` |

```bash
python3 scripts/client.py call seedance create --json '{"model": "seedance-2-text-2-video", "ratio": "16:9", "tools": [{"type": "web_search"}], "content": [{"text": "一只金毛犬在海边奔跑，夕阳西下", "type": "text"}], "callback_url": "https://your-domain.com/webhook/seedance"}' --no-wait
```

官方文档全文：[`references/api-create.md`](references/api-create.md)

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/通用说明.md` | 权限表、异步任务机制、常见错误、能力边界、计费口径 |
| `references/getting-started.md` | 注册、充值、获取与配置 API Key |
| `references/api-createGroup.md` | `createGroup` 的平台官方文档全文 + schema 原文 |
| `references/api-createAsset.md` | `createAsset` 的平台官方文档全文 + schema 原文 |
| `references/api-getAsset.md` | `getAsset` 的平台官方文档全文 + schema 原文 |
| `references/api-updateAsset.md` | `updateAsset` 的平台官方文档全文 + schema 原文 |
| `references/api-deleteAsset.md` | `deleteAsset` 的平台官方文档全文 + schema 原文 |
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
