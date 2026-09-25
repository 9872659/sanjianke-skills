---
name: smart-clip
slug: smart-clip
displayName: 三剪客 · 智能剪辑
description: "智能剪辑应用，支持模板查询、真人口播混剪、素材混剪和新闻体视频制作。支持 模板列表、模板详情、真人口播混剪、素材混剪、新闻体视频。使用时需要你自己的 api.a7w.cn API Key。遇到问题可加技术微信 9872659。"
version: 1.0.3
summary: "「智能剪辑」的完整调用封装：5 个接口的官方文档、参数表与一个零依赖客户端。需要自带 api.a7w.cn 的 API Key，调用按点数计费。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 批量混剪
  - 短剧二创
---

# 智能剪辑

`api.a7w.cn` 插件 **`smart_clip`**，共 **5 个接口**。查询智能剪辑模板列表。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数
python3 scripts/client.py schema smart_clip

# 3. 调用（示例）
python3 scripts/client.py call smart_clip template --json '{"scene": "realMan", "sortBy": "desc", "pageSize": 10, "searchKey": "name", "searchValue": "口播"}'
```

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `template` | 模板列表 | 同步 | 免费 |
| `template_detail` | 模板详情 | 同步 | 免费 |
| `realman_broadcast` | 真人口播混剪 | 异步 | 免费 |
| `broadcast_mixcut` | 素材混剪 | 异步 | 免费 |
| `news_mixcut` | 新闻体视频 | 异步 | 免费 |

## 接口详情

### `template` · 模板列表

**请求**：`POST /api/v1/apps/v1/clip/template`

**模式**：同步（直接返回结果） ｜ **计费**：免费

查询智能剪辑模板列表。

查询智能剪辑可用模板列表。接口为同步免费查询。 | 字段 | 内容 | | 应用编码 | `smart_clip` | | API 编码 | `template` | | 请求方式 | `GET` | | 请求路径 | `/api/v1/apps/smart_clip/template` | | 调用模式 | 同步 | | 计费方式 | 免费查询 | | 参数 | 位置 | 类型 | 必填 | 默认值 | 可选值 | 说明 | | `pageSize` | query | integer | 否 | `10` | - | 每页大小 | | `sid` | query | string | 否 | - | - | 分页游标，当有值时代表存在下一页，继续查询下一页时需传入该值 | | `scene` | query | string | 是 | - | `realMan` / `oralMixCutting` / `newsMixC…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `sid` | string | 否 |  | 分页游标，当有值时代表存在下一页，继续查询下一页时需传入该值 |
| `scene` | enum | 否 |  | 模板使用场景：真人口播 realMan（提交接口 realman_broadcast）、素材混剪 oralMixCutting（提交接口 broadcast_mixcut）、新闻体视频 newsMixCutting（提交接口 news_mixcut）　可选值：`realMan` / `oralMixCutting` / `newsMixCutting` |
| `sortBy` | enum | 否 | `desc` | 排序方式，desc：按上架时间倒序排序，asc：按上架时间正序排序　可选值：`desc` / `asc` |
| `pageSize` | integer | 否 | `10` | 每页大小　例：`10` |
| `searchKey` | enum | 否 |  | 搜索字段　可选值：`name` / `id` |
| `searchValue` | string | 否 |  | 搜索值　例：`口播` |

```bash
python3 scripts/client.py call smart_clip template --json '{"scene": "realMan", "sortBy": "desc", "pageSize": 10, "searchKey": "name", "searchValue": "口播"}'
```

官方文档全文：[`references/api-template.md`](references/api-template.md)

### `template_detail` · 模板详情

**请求**：`POST /api/v1/apps/v1/clip/template/detail/{id}`

**模式**：同步（直接返回结果） ｜ **计费**：免费

按模板 ID 获取模板结构详情。

按模板 ID 获取模板结构详情。接口为同步免费查询。 | 字段 | 内容 | | 应用编码 | `smart_clip` | | API 编码 | `template_detail` | | 请求方式 | `GET` | | 请求路径 | `/api/v1/apps/smart_clip/template_detail?id={id}` | | 调用模式 | 同步 | | 计费方式 | 免费查询 | | 参数 | 位置 | 类型 | 必填 | 示例 | 说明 | | `id` | query | string | 是 | `67b7ee802b2beb0030cdeaaf` | 模板id | GET /api/v1/apps/smart_clip/template_detail?id=67b7ee802b2beb0030cdeaaf Authorization: Bearer <YOUR_API_KEY> | 字段 | 类型 |…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | string | 否 |  | 模板id　例：`67b7ee802b2beb0030cdeaaf` |

```bash
python3 scripts/client.py call smart_clip template_detail --json '{"id": "67b7ee802b2beb0030cdeaaf"}'
```

官方文档全文：[`references/api-template_detail.md`](references/api-template_detail.md)

### `realman_broadcast` · 真人口播混剪

**请求**：`POST /api/v1/apps/v1/clip/video/realman_broadcast`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

提交真人口播混剪视频制作任务。

**分档：`720p`=0.2，`1080p`=0.3**

提交真人口播混剪视频任务。提交成功后返回平台 `task_id`。请通过平台任务查询接口获取最终状态与结果，或传入 `callbackUrl` 接收任务通知。 | 字段 | 内容 | | 应用编码 | `smart_clip` | | API 编码 | `realman_broadcast` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/smart_clip/realman_broadcast` | | 调用模式 | 异步 | | 计费方式 | 按输入媒体时长计费 | | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 说明 | | `styleId` | string | 是 | - | - | 视频模板id | | `videoUrl` | string | 是 | - | mp4 / mov | 视频url。平台会优先探测该媒体时长用于计费 | | `language…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `title` | string | 否 |  | 标题　例：`聊AI行业` |
| `styleId` | string | 否 |  | 视频模板id　例：`68aebb91b8619ed6f4168f40` |
| `language` | string | 否 |  | 特指视频中（videoUrl）对应的语种，音频驱动时需要传音频中内容的语种，语种参考ASR支持的语种　例：`zh-CN` |
| `subtitle` | array | 否 |  | 字幕信息（兼容subtitles字段），该字段专用于填充语音识别（ASR）后的结果，如果您未预先进行语音识别（ASR），请忽略该字段。 |
| `videoUrl` | string | 否 |  | 视频url　例：`https://example.com/a.mp4` |
| `materials` | array | 否 |  | 素材，素材格式要求详见产品介绍-功能介绍 |
| `packRules` | object | 否 |  | 包装规则：仅用于控制标题、素材、字幕等是否参与模版的效果包装，无特殊要求不建议设置。 |
| `callbackUrl` | string | 否 |  | 结果通知回调地址　例：`https://example.com/hook` |
| `processRules` | object | 否 |  | 处理规则 |
| `structLayers` | array | 否 |  | 需要修改的图层数据 |
| `introduceCard` | object | 否 |  | 身份栏信息，含义详见常见问题库 |
| `materialSoundSwitch` | boolean | 否 | `False` | 当素材为视频时原声开关 |

```bash
python3 scripts/client.py call smart_clip realman_broadcast --json '{"title": "聊AI行业", "styleId": "68aebb91b8619ed6f4168f40", "language": "zh-CN", "videoUrl": "https://example.com/a.mp4", "callbackUrl": "https://example.com/hook"}' --no-wait
```

官方文档全文：[`references/api-realman_broadcast.md`](references/api-realman_broadcast.md)

### `broadcast_mixcut` · 素材混剪

**请求**：`POST /api/v1/apps/v1/clip/video/broadcast_mixcut`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

提交素材混剪视频制作任务，仅支持音频或素材输入链路。

**输入上限**：参考图 ≤ 1 张，参考音频 ≤ 1 个，参考视频 ≤ 1 个

**分档：`720p`=0.2，`1080p`=0.3**

提交素材混剪视频任务。当前应用仅支持 `audioUrl` 或素材输入链路；提交时如果传入 `content` 或 `speakerId`，平台会返回不支持该分支的明确错误。 | 字段 | 内容 | | 应用编码 | `smart_clip` | | API 编码 | `broadcast_mixcut` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/smart_clip/broadcast_mixcut` | | 调用模式 | 异步 | | 计费方式 | 按输入媒体时长计费 | | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 说明 | | `styleId` | string | 是 | - | - | 视频模板ID | | `title` | string | 否 | - | - | 标题；如果期望生成的视频不显示标题，请不要设置标题值 | | `audioUrl`…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `title` | string | 否 |  | 标题　例：`聊AI行业` |
| `content` | string | 否 |  | 文本，与audioUrl字段二选一，选择文本，则speakerId为必须；当前应用不支持该定制声音分支 |
| `styleId` | string | 否 |  | 视频模板ID　例：`68aebb91b8619ed6f4168f40` |
| `audioUrl` | string | 否 |  | 音频URL，与content字段二选一；当前应用仅支持 audioUrl 或素材输入链路　例：`https://example.com/a.mp3` |
| `language` | string | 否 |  | 语种，特指音频（audioUrl）对应的语种，语种参考ASR支持的语种　例：`zh-CN` |
| `subtitle` | array | 否 |  | 字幕信息（兼容subtitles字段），该字段专用于填充语音识别（ASR）后的结果，如果您未预先进行语音识别（ASR），请忽略该字段。 |
| `materials` | array | 否 |  | 素材 |
| `packRules` | object | 否 |  | 包装规则：仅用于控制标题、素材、字幕等是否参与模版的效果包装，无特殊要求不建议设置。 |
| `speakerId` | string | 否 |  | 音色ID；当前应用不支持 content + speakerId 定制声音分支 |
| `callbackUrl` | string | 否 |  | 结果通知回调地址　例：`https://example.com/hook` |
| `processRules` | object | 否 |  | 处理规则 |
| `speakerExtra` | object | 否 |  | 音色扩展参数，传speakerId时有效；当前应用不支持 content + speakerId 定制声音分支 |
| `structLayers` | array | 否 |  | 需要修改的图层数据 |
| `introduceCard` | object | 否 |  | 身份栏信息，含义详见常见问题库 |

```bash
python3 scripts/client.py call smart_clip broadcast_mixcut --json '{"title": "聊AI行业", "styleId": "68aebb91b8619ed6f4168f40", "audioUrl": "https://example.com/a.mp3", "language": "zh-CN", "callbackUrl": "https://example.com/hook"}' --no-wait
```

官方文档全文：[`references/api-broadcast_mixcut.md`](references/api-broadcast_mixcut.md)

### `news_mixcut` · 新闻体视频

**请求**：`POST /api/v1/apps/v1/clip/video/news_mixcut`

**模式**：异步（提交后轮询任务） ｜ **计费**：免费

提交新闻体视频制作任务。

**分档：`720p`=0.2，`1080p`=0.3**

提交新闻体视频任务。如未传 `processRules.videoDuration`，平台会探测素材媒体时长用于计费；无法获取有效输入媒体时长时会拒绝提交。 | 字段 | 内容 | | 应用编码 | `smart_clip` | | API 编码 | `news_mixcut` | | 请求方式 | `POST` | | 请求路径 | `/api/v1/apps/smart_clip/news_mixcut` | | 调用模式 | 异步 | | 计费方式 | 按输入媒体时长计费 | | 参数 | 类型 | 必填 | 默认值 | 可选值 / 范围 | 说明 | | `styleId` | string | 是 | - | - | 视频模板ID | | `title` | string | 是 | - | 3-1800字符 | 标题 | | `materials` | array | 是 | - | image / video |…

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `title` | string | 否 |  | 标题　例：`聊AI行业` |
| `styleId` | string | 否 |  | 视频模板ID　例：`68aebb91b8619ed6f4168f40` |
| `materials` | array | 否 |  | 素材 |
| `packRules` | object | 否 |  | 包装规则：仅用于控制标题、素材、字幕等是否参与模版的效果包装，无特殊要求不建议设置。 |
| `callbackUrl` | string | 否 |  | 结果通知回调地址　例：`https://example.com/hook` |
| `processRules` | object | 否 |  | 处理规则 |
| `structLayers` | array | 否 |  | 需要修改的图层数据 |
| `introduceCard` | object | 否 |  | 身份栏信息，含义详见常见问题库 |

```bash
python3 scripts/client.py call smart_clip news_mixcut --json '{"title": "聊AI行业", "styleId": "68aebb91b8619ed6f4168f40", "callbackUrl": "https://example.com/hook"}' --no-wait
```

官方文档全文：[`references/api-news_mixcut.md`](references/api-news_mixcut.md)

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/通用说明.md` | 权限表、异步任务机制、常见错误、能力边界、计费口径 |
| `references/getting-started.md` | 注册、充值、获取与配置 API Key |
| `references/api-template.md` | `template` 的平台官方文档全文 + schema 原文 |
| `references/api-template_detail.md` | `template_detail` 的平台官方文档全文 + schema 原文 |
| `references/api-realman_broadcast.md` | `realman_broadcast` 的平台官方文档全文 + schema 原文 |
| `references/api-broadcast_mixcut.md` | `broadcast_mixcut` 的平台官方文档全文 + schema 原文 |
| `references/api-news_mixcut.md` | `news_mixcut` 的平台官方文档全文 + schema 原文 |
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
