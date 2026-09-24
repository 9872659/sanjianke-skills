---
name: sanjianke-ai-classroom-kit
slug: sanjianke-ai-classroom-kit
displayName: 三剪客 · 多智能体互动课堂
description: "把主题或文档一键变成多智能体互动课堂。 遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "面向想快速产出互动课堂的团队：一条命令起本地课堂，AI 教师带多名智能体同学授课、答疑、白板推演；支持 19 家模型服务商、四种课堂场景与深度交互模式。覆盖部署、角色编排、题库与排错。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 教育学习
  - 教学
  - AI 课堂
---

# 三剪客 · 多智能体互动课堂

把主题或文档一键变成多智能体互动课堂。

一句话需求、一份 PDF、一个 `.pptx`，都能变成一节「能播放、能提问、能动手」的互动课：AI 教师负责讲，多名智能体同学负责追问和讨论，白板实时推演，测验自动判分，交互实验可以上手拖。适合要批量产出教学内容的团队、做知识付费的讲师、把内部资料转成培训课的企业。

本 Skill 只解决「怎么把它跑起来、角色怎么编排、配置怎么改、报错怎么查」这四件事，不替你做课程设计决策。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取 OpenMAIC 仓库与依赖；调用你自备的模型 / 语音 / 搜索接口；做健康检查与生成任务轮询 |
| 读取文件 | 是 | 读取你指定的 PDF、PPTX、音视频素材用于生成课堂；读取 `.env.local` 与 `server-providers.yml` |
| 写入文件 | 是 | 创建代码目录、写入环境变量与服务商配置；落盘 `.pptx` / `.html` / `.maic.zip` 成果物 |
| 凭证 | 是，且必须由你本人填写 | 模型与媒体服务商的 Key 只写进你本机的 `.env.local` 或 `server-providers.yml`；本 Skill 不内嵌、不代填、不回显任何密钥 |
| 子进程 / 后台常驻 | 是 | 执行 `pnpm install`、`pnpm dev`、`pnpm build`、`docker compose`，并让本地服务常驻在 3000 端口 |

OpenMAIC 是独立的上游开源项目（MIT 协议），本项目不内嵌它的任何密钥，也不代管它的服务商账号。所有模型调用都走你自己申请、自己付费的 Key。

## 触发场景

- 「我手里这份 PDF 能不能直接变成一节能互动的课？」
- 「帮我在本地起一个 OpenMAIC，模型我自己配。」
- 「怎么让 AI 老师带着两个同学一起讨论，而不是自己念幻灯片？」
- 「课堂生成卡在某个步骤不动了，帮我定位是模型还是网络的问题。」
- 「生成一节 20 分钟的课大概要烧多少 token，换哪家模型更划算？」
- 「把生成的幻灯片导成 PPTX 发同事，公式不能丢。」

## 快速开始

先核对环境：**Node.js ≥ 22.19**、**pnpm ≥ 10**，再准备至少一个模型服务商的 API Key。

```bash
# 1. 取代码并装依赖
git clone https://github.com/THU-MAIC/OpenMAIC.git
cd OpenMAIC
pnpm install

# 2. 生成配置文件
cp .env.example .env.local
```

在 `.env.local` 里**至少**填一组 Key 和默认模型（下面用 OpenAI 举例）：

```env
OPENAI_API_KEY=sk-...
DEFAULT_MODEL=openai:gpt-5.5
```

注意 `DEFAULT_MODEL` 必须带服务商前缀，裸模型名会被服务端在启动阶段拒绝。

```bash
# 3. 起服务
pnpm dev
# 4. 自检：期望 status=ok
curl -s http://localhost:3000/api/health
```

打开 `http://localhost:3000`，输入主题即可生成。想用命令行提交异步生成任务：

```bash
curl -s -X POST http://localhost:3000/api/generate-classroom \
  -H 'Content-Type: application/json' \
  -d '{"requirement":"用 20 分钟讲清傅里叶变换的直觉","agentMode":true}'
# 返回 202 + jobId + pollUrl + pollIntervalMs(5000)，之后轮询 pollUrl
```

生产构建用 `pnpm build && pnpm start`，容器化用 `docker compose up --build`（应用映射宿主机 3000 端口）。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 跑起来、换端口、上 Docker 或云服务器、加站点访问密码 | `references/01-deploy-and-start.md` |
| 搞清 AI 教师与智能体同学怎么分工、课堂怎么推进、怎么加角色 | `references/02-roles-and-classroom-flow.md` |
| 换模型、接自己的技能包、导出与二次开发、报错排查 | `references/03-customize-and-troubleshoot.md` |

## 能力边界

**覆盖**：

- 三种启动路线（本地开发、生产构建、容器）的完整命令、端口与健康检查
- 多智能体角色模型：`teacher` / `assistant` / `student` 三类角色、角色到行动权限的映射、按人设生成角色名册
- 课堂内容结构：幻灯片、测验、交互实验、项目制学习四种场景，以及两阶段生成流水线
- 回放状态机与实时讨论：`idle → playing → paused → live` 的切换条件，讨论话题的开启与收束
- 模型与媒体服务商接入：19 家 LLM 服务商的环境变量前缀、`DEFAULT_MODEL` 解析、`server-providers.yml` 写法
- 导出（`.pptx` / 交互式 `.html` / `.maic.zip`）与常见故障的定位顺序

**不覆盖**：

- 不替你写课程大纲，也不做学科内容的正确性审核——生成结果必须由你自己过一遍
- 不管模型服务商的开户、充值、限流申诉，也不代你申请任何 Key
- 不做修改上游源码的深度二次开发，只覆盖 fork、环境变量与配置层
- 不提供 MP4 渲染算力：走视频导出需要你单独起 Chromium + FFmpeg 渲染容器
- 不保证第三方模型在长上下文下的稳定性，也不对生成内容的版权做兜底

## 依赖条件

| 项目 | 要求 |
|---|---|
| 运行时 | Node.js ≥ 22.19；包管理器 pnpm ≥ 10 |
| 模型 | 至少 1 个 LLM 服务商 Key；要语音讲解再加 TTS Key；要联网检索再加搜索 Key |
| 容器路线 | Docker Engine + Compose v2（镜像内已含 Node 22） |
| 服务端持久化 | PostgreSQL 16，走 `--profile server-persistence` |
| MP4 导出 | `--profile video-export` 拉起独立渲染容器；标准档默认 8 GiB 内存上限、2 GB 共享内存，低内存档可降到 4 GiB |
| 网络 | 能访问你选定的服务商 API 域名；容器路线下首次构建需要拉取基础镜像与 npm 包 |

## 已知限制

- Node 版本低于 22.19 会在安装阶段直接失败，不是告警。
- `NEXT_PUBLIC_*` 系列是**编译期**变量，改完必须重新 build 才生效，热更新不会带上新值。
- 服务端持久化的开发令牌会被编译进浏览器 bundle，任何人可提取；该模式只适用于本机或可信内网的单用户场景。
- 课堂生成是异步长任务，一次几分钟很正常；不开持久化时，进程重启会丢掉进行中的任务状态。
- 导出「可离线播放」的课堂时，抓不到的外部资源会退回保留原始 URL，播放时仍需要公网。
- 能力位是按服务商独立判断的：`/api/health` 里的 `tts`、`imageGeneration`、`videoGeneration`、`webSearch` 四项可能只亮其中几项。
- 界面本地化覆盖 12 个区域，但生成内容的语言质量取决于你选的模型。

## 自检清单

- [ ] `curl -s http://localhost:3000/api/health` 返回 `status: ok`
- [ ] `capabilities` 里你实际要用的能力位为 `true`（TTS / 图片 / 视频 / 检索）
- [ ] `DEFAULT_MODEL` 带服务商前缀，形如 `openai:gpt-5.5`
- [ ] `.env.local` 已被 `.gitignore` 忽略，没有混进提交
- [ ] 生成任务返回 202，且 `pollUrl` 可直接访问
- [ ] 导出的 `.pptx` 能打开，公式与图表未错位
- [ ] 对外提供服务时 `ACCESS_CODE` 已设置
- [ ] 重载或重启后，已生成的课堂还在（用持久化时）

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/01-deploy-and-start.md` | 环境核对、依赖安装、三种启动路线、端口与健康检查、容器与持久化、站点密码 |
| `references/02-roles-and-classroom-flow.md` | 角色字段与行动权限、角色名册生成、四种场景、两阶段生成、回放状态机 |
| `references/03-customize-and-troubleshoot.md` | 服务商接入与模型路由、内置技能包、自定义技能、导出、排错速查表 |

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
