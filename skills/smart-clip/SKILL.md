---
name: smart-clip
slug: smart-clip
displayName: 三剪客 · 智能剪辑
description: "智能剪辑应用，支持模板查询、真人口播混剪、素材混剪和新闻体视频制作。支持 模板列表、模板详情、真人口播混剪、素材混剪、新闻体视频。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。**作者已亲测实操，下载后可自用或商用。**运行只需一把 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。使用中遇到任何问题，加技术微信 9872659 与作者交流。"
version: 1.0.5
summary: "「智能剪辑」的完整调用封装：5 个接口的官方文档、参数表与一个零依赖客户端。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。**作者已亲测实操，下载后可自用或商用。**运行只需一把 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。使用中遇到任何问题，加技术微信 9872659 与作者交流。"
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

### `template` · 模板列表template### `template_detail` · 模板详情template_detail### `realman_broadcast` · 真人口播混剪realman_broadcast### `broadcast_mixcut` · 素材混剪broadcast_mixcut### `news_mixcut` · 新闻体视频news_mixcuttemplate

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
| 遇到问题找谁 | **直接加技术微信 9872659**，作者本人答疑 |

> **使用中碰到任何问题 —— 报错、效果不理想、想省钱、想批量 —— 都欢迎加微信聊。**
> 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的示例。
