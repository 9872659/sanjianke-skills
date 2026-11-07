---
name: a7w-smart-clip
slug: a7w-smart-clip
displayName: 三剪客 · 智能剪辑
description: "一条 JSON 出成片：模板列表/模板详情查模板，真人口播混剪、素材混剪、新闻体视频三条生产链路直接提交，异步任务出 720p/1080p 成片。含 5 个接口的逐参数表（含必填项与 scene 对应关系）、上游真实分档价、真实模板 id 的取法，以及一个零依赖客户端（`SKILL.md` + `references/` + `scripts/client.py`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.11
summary: "「智能剪辑」的完整调用封装：`template` 列模板、`template_detail` 取模板结构、`realman_broadcast` 真人口播混剪、`broadcast_mixcut` 素材混剪、`news_mixcut` 新闻体视频。文档按上游 schema（2026-08-12 版）逐参数对齐，标清必填项与 scene 和提交接口的对应关系，并给出分档计费口径与零依赖客户端。需要自备 api.a7w.cn 的 API Key。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 批量混剪
  - 短剧二创
---

# 智能剪辑

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。


`api.a7w.cn` 插件 **`smart_clip`**（智能剪辑），共 **5 个接口**：查模板 2 个、出片 3 个。

本 Skill 是它的完整调用封装：逐接口参数表、平台官方文档摘录、真实计费口径，以及一个零依赖、可直接跑的 `client.py`。

## 快速开始

```bash
# 1. 配置你自己的 api.a7w.cn API Key（只需一次）
python3 scripts/client.py login --key sk-你的key

# 2. 看这个插件的接口与参数（实时读上游）
python3 scripts/client.py schema smart_clip

# 3. 列模板（scene 必填：realMan / oralMixCutting / newsMixCutting）
python3 scripts/client.py call smart_clip template --json '{"scene": "realMan", "pageSize": 10}'

# 4. 用上一步返回的真实模板 id 取模板结构
python3 scripts/client.py call smart_clip template_detail --json '{"id": "6a2668a137004e003477b6ed"}'

# 5. 提交一条新闻体视频（styleId 用上一步的模板 id）
python3 scripts/client.py call smart_clip news_mixcut --json '{
  "styleId": "6a2668a137004e003477b6ed",
  "title": "三分钟看懂这次调整",
  "materials": [{"type": "image", "fileUrl": "https://example.com/01.jpg"}]
}'
```

> **Windows / CMD 提示**：双引号会被 shell 吃掉，改用 `--json-file body.json` 或 `--param k=v` 逐个传。
> **`call` 默认自动轮询到完成**；想只提交不等结果，加 `--no-wait`，之后用 `client.py task <task_id>` 查。

> **没有 Key？** 见 `references/getting-started.md`——注册、充值、取 Key 的完整步骤。也可以直接去 [算力集市](https://api.a7w.cn/) 注册。

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `template` | 模板列表 | 同步 | 字段价 0（查询类） |
| `template_detail` | 模板详情 | 同步 | 字段价 0（查询类） |
| `realman_broadcast` | 真人口播混剪 | 异步 | 分档价：720p 0.2 / 1080p 0.3 |
| `broadcast_mixcut` | 素材混剪 | 异步 | 分档价：720p 0.2 / 1080p 0.3 |
| `news_mixcut` | 新闻体视频 | 异步 | 分档价：720p 0.2 / 1080p 0.3 |

> ⚠️ **计费口径修正**：旧版文档把 5 个接口一律写「免费」，但上游这三个出片接口带着
> `pricing_matrix = {"720p": {"with_video": 0.2}, "1080p": {"with_video": 0.3}}`（`billing_type=5`）。
> 本版按上游字段改为「分档价」，**真实扣费仍以返回里的 `data.usage.points_cost` 为准**。

## 场景与接口的对应关系

`template` 的 `scene` 决定你拿到哪一类模板，也决定后面用哪个提交接口：

| `scene` | 含义 | 对应提交接口 |
|---|---|---|
| `realMan` | 真人口播 | `realman_broadcast` |
| `oralMixCutting` | 素材混剪 | `broadcast_mixcut` |
| `newsMixCutting` | 新闻体视频 | `news_mixcut` |

> 拿错场景的模板去提交，轻则参数报错，重则渲染异常。先定场景 → 再列模板 → 最后提交。

## 接口详情

### `template` · 模板列表

`POST /api/v1/apps/smart_clip/template`（上游 `method` 标 GET，平台对外统一接收 POST，实测可用）

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `sid` | string | 否 | — | 分页游标，有值时代表存在下一页，翻页时传回该值 |
| `scene` | string / realMan / oralMixCutting / newsMixCutting | **是** | — | 模板使用场景 |
| `sortBy` | string / desc / asc | 否 | `desc` | 按上架时间排序 |
| `pageSize` | integer | 否 | `10` | 每页大小 |
| `searchKey` | string / name / id | 否 | — | 搜索字段 |
| `searchValue` | string | 否 | — | 搜索值 |

### `template_detail` · 模板详情

`POST /api/v1/apps/smart_clip/template_detail`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | string | **是** | — | 模板 id（用 `template` 返回的真实 id，不是序号） |

> 传不存在的 id 时，上游返回的是含糊的「任务处理失败，请稍后重试」——看着像服务故障，其实是 id 不对。
> 正确做法：先 `template` 拿一个真实 id（形如 `6a2668a137004e003477b6ed`）。

### `realman_broadcast` · 真人口播混剪

`POST /api/v1/apps/smart_clip/realman_broadcast` · 异步

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `styleId` | string | **是** | — | 视频模板 id |
| `videoUrl` | string | **是** | — | 口播视频 URL |
| `title` | string | 否 | — | 标题 |
| `language` | string | 否 | — | `videoUrl` 对应语种；音频驱动时传音频内容语种 |
| `subtitle` | array | 否 | — | 预跑过 ASR 的结果（兼容 `subtitles`），没跑就忽略 |
| `materials` | array | 否 | — | 素材 |
| `packRules` | object | 否 | — | 包装规则，无特殊要求不建议设置 |
| `processRules` | object | 否 | — | 处理规则（水印、时长、首帧封面等） |
| `structLayers` | array | 否 | — | 需要修改的图层数据 |
| `introduceCard` | object | 否 | — | 身份栏信息 |
| `materialSoundSwitch` | boolean | 否 | `false` | 素材为视频时的原声开关 |
| `callbackUrl` | string | 否 | — | 结果回调地址 |

### `broadcast_mixcut` · 素材混剪

`POST /api/v1/apps/smart_clip/broadcast_mixcut` · 异步

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `styleId` | string | **是** | — | 视频模板 id |
| `materials` | array | **是** | — | 素材 |
| `title` | string | 否 | — | 标题 |
| `audioUrl` | string | 否 | — | 音频 URL，与 `content` 二选一；本应用仅支持 audioUrl 或素材输入链路 |
| `content` | string | 否 | — | 文本，与 `audioUrl` 二选一（需配 `speakerId`，本应用不支持该分支） |
| `speakerId` | string | 否 | — | 音色 ID；本应用不支持 content + speakerId 定制声音 |
| `speakerExtra` | object | 否 | — | 音色扩展参数，传 `speakerId` 时有效 |
| `language` | string | 否 | — | `audioUrl` 对应语种 |
| `subtitle` | array | 否 | — | 预跑过 ASR 的结果，没跑就忽略 |
| `packRules` | object | 否 | — | 包装规则 |
| `processRules` | object | 否 | — | 处理规则 |
| `structLayers` | array | 否 | — | 图层数据 |
| `introduceCard` | object | 否 | — | 身份栏信息 |
| `callbackUrl` | string | 否 | — | 结果回调地址 |

### `news_mixcut` · 新闻体视频

`POST /api/v1/apps/smart_clip/news_mixcut` · 异步

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `styleId` | string | **是** | — | 视频模板 id |
| `title` | string | **是** | — | 标题（3-1800 字符） |
| `materials` | array | **是** | — | 素材，每项含 `type`（image/video）/`fileUrl`/`soundSwitch` |
| `packRules` | object | 否 | — | 包装规则 |
| `processRules` | object | 否 | — | 处理规则（水印/时长/元水印/素材组合/首帧封面） |
| `structLayers` | array | 否 | — | 图层数据 |
| `introduceCard` | object | 否 | — | 身份栏信息 |
| `callbackUrl` | string | 否 | — | 结果回调地址 |

> 未传 `processRules.videoDuration` 时平台会探测素材时长用于计费；**探测不到有效时长会直接拒绝提交**，不会退回默认时长。

## 三条容易踩的坑

1. **素材地址不能重名**：`materials[].fileUrl`、背景音乐 `packRules.backgroundMusic.audioUrl`、AI 封面 `resultImageUrl`
   如果同名，渲染会异常。批量生成时给文件名加随机后缀。
2. **`packRules` 只控制「要不要套包装」，不控制图层显隐**。不想出标题，就别传 `title`，而不是指望 `packRules` 关掉它。
3. **异步任务提交即预冻结点数**，别重复提交同一个任务；查询走通用接口 `GET /api/v1/tasks/{task_id}`（`client.py task` 已封装）。

---

## 关于这个 Skill

**作者亲测实操后发布。** 文档里的每条命令、每个参数、每项计费口径，都真机跑过、对过账，
不是抄来的二手资料。**下载后可自用，也可商用。**

跑起来只需要一样东西 —— [算力集市 api.a7w.cn](https://api.a7w.cn/) 的一把 API Key。
注册即送点数，可以先免费试跑几条，觉得好用再充。

| 你可能想问 | 答案 |
|---|---|
| 要不要花钱 | 按点数计费，用多少扣多少，**没有月费、不用包年** |
| 难不难接 | 包里自带**零依赖客户端**（只用 Python 标准库），配好 Key 一行命令就能跑 |
| 能不能批量 | 能。想要批量脚本、更优参数、更省的调用方案，微信里说 |
| 遇到问题找谁 | 见文末「联系我们」，作者本人答疑 |

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
