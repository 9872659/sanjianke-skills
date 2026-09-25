---
name: happy-horse-video
slug: happy-horse-video
displayName: 三剪客 · Happy Horse
description: "Happy Horse（HappyHorse-1.1 系列）面向文生/图生高质量短视频，采用统一多模态建模，可一阶段生成声画、支持多语言对白与多镜头场景衔接。计费按目标分辨率与生成秒数对应的参数档位计点。本能力为内测邀请制，正式调用前需完成内测申请。支持 提交任务、创建任务、查询任务。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。**作者已亲测实操，下载后可自用或商用。**运行只需一把 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。使用中遇到任何问题，加技术微信 9872659 与作者交流。"
version: 1.0.5
summary: "「Happy Horse」的完整调用封装：3 个接口的官方文档、参数表与一个零依赖客户端。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。**作者已亲测实操，下载后可自用或商用。**运行只需一把 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。使用中遇到任何问题，加技术微信 9872659 与作者交流。"
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

### `submit` · 提交任务submit### `create` · 创建任务create### `query` · 查询任务querysubmit

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
