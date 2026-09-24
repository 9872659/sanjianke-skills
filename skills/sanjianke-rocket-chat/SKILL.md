---
name: sanjianke-rocket-chat
slug: sanjianke-rocket-chat
displayName: 三剪客 · Rocket.Chat 团队通讯
description: "Rocket.Chat：可完全自建的团队通讯平台，把即时消息、频道、语音、联邦与外部集成收进一套自己掌控的部署里。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Rocket.Chat：可完全自建的团队通讯平台，把即时消息、频道、语音、联邦与外部集成收进一套自己掌控的部署里。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · Rocket.Chat 团队通讯

Rocket.Chat 是一套可以完全跑在自己机器上的团队通讯平台。频道消息、私聊、文件、语音通话、角色权限、单点登录，都在你自己的数据库和域名下面，不依赖第三方 SaaS 的可用性和数据政策。

它的价值在「数据不出域」和「可深度改造」这两点上：部署方式覆盖 Docker、Podman、Kubernetes 和完全断网的隔离网络；扩展侧有应用框架和一套 RPC 风格的外部接口，能把消息、用户、频道接进自己的系统。

代价是它不是一个解压就完事的单体应用——至少要有 MongoDB，生产环境还要反代、对象存储、推送服务。所以用之前先想清楚：你是需要一个「自己完全掌控的团队通讯底座」，还是只想找个能聊天的工具。

**上游项目**：`Rocket.Chat`　**仓库**：https://github.com/RocketChat/Rocket.Chat

## 什么时候用 / 不用

**用它**：

- 「公司要求聊天记录和文件不能离开内网」，需要一个能跑在隔离网络里的通讯平台。
- 「要按组织架构做权限」，需要角色和属性级的访问控制，而不是只有群主/成员两档。
- 「要把内部系统和聊天打通」——用应用框架或外部接口做告警推送、审批卡片、消息归档。
- 「要和合作方跨组织通信」，且需要联邦这种能跨实例共享资源的模式。
- 「已经有 K8s 集群，想按自己的规格做高可用」，需要能横向扩多实例的通讯服务。

**不要用它**：

- 只想两三个人传话——装一套带数据库和反代的平台，运维成本远大于收益，用现成轻量工具更合适。
- 指望「拉个镜像就完事」——官方已经把单文件 compose 标为弃用，实际部署要处理数据库副本集、反代、持久化卷这些事。
- 需要开箱即用的托管服务、不想碰服务器——自建路线要自己负责升级、备份、证书、监控。
- 只想做纯文字通知机器人，对延迟和可靠性要求也不高——一个 webhook 加群机器人就够了，不必上整套平台。
- 组织里有强合规要求但没人能接手运维——平台本身支持合规能力，不代表你的部署自动合规。

## 安装

官方推荐的部署方式是 Docker、Podman 或 Kubernetes，完整步骤和系统要求以官方部署文档为准。

**单容器自建镜像**（适合先本地跑起来看看）：

```bash
docker run -d --name rocketchat \
  -p 3000:3000 \
  -e ROOT_URL=http://localhost:3000 \
  -e PORT=3000 \
  -e MONGO_URL=mongodb://<mongo主机>:27017/rocketchat?replicaSet=rs0 \
  -e MONGO_OPLOG_URL=mongodb://<oplog用户>:<密码>@<mongo主机>:27017/local?authSource=admin&replicaSet=rs0 \
  rocketchat/rocket.chat:latest
```

镜像也可以从 `registry.rocket.chat/rocketchat/rocket.chat` 拉取。**建议固定版本标签而不是用 `latest`**，这样升级节奏由你控制。

**Compose 部署**：官方维护的 compose 组合仓库是推荐的起点。

```bash
git clone --depth 1 https://github.com/RocketChat/rocketchat-compose.git
cd rocketchat-compose
cp .env.example .env
# 编辑 .env：DOMAIN、ROOT_URL、TRAEFIK_PROTOCOL 等
docker compose \
  -f compose.monitoring.yml \
  -f compose.traefik.yml \
  -f compose.database.yml \
  -f compose.yml \
  -f compose.nats.yml \
  -f docker.yml \
  up -d
```

这套组合默认会起 Rocket.Chat、Traefik、MongoDB、NATS 和 Prometheus 监控。要裁掉某个组件，把对应的 compose 文件从命令里去掉即可；用外部 MongoDB 或外部 NATS 则参考仓库里的 `docs/external-mongo.md` / `docs/external-nats.md`。Podman 用户把 `docker.yml` 换 `podman.yml`（无根模式），需要 rootful 时用 `podman-rootful.yml`。

进容器执行管理命令用：

```bash
docker compose exec rocketchat bash
```

## 常用操作

```bash
# 1. 看容器状态与日志（compose 组合部署时）
docker compose ps
docker compose logs -f rocketchat

# 2. 进容器拿管理命令行
docker compose exec rocketchat bash

# 3. 停掉整套（含带 profile 的服务）
docker compose -f docker.yml --profile '*' down

# 4. 升级：先备份数据库，再拉新镜像并重建
docker compose pull
docker compose up -d

# 5. 外部接口自检：换成你的域名，确认服务在响应
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/api/info
```

外部接口是 RPC 风格的 HTTP 接口，可以创建和追加消息、管理频道、开通账号、查历史等。**具体的接口路径、请求字段、鉴权头以官方 API 文档为准**（文档站在 `developer.rocket.chat` 下）。鉴权通常用账号或 token 换取会话凭据，再用该凭据调业务接口；**具体登录端点与请求体格式请以官方 API 文档为准，不要照抄第三方示例**。

扩展方向的两种做法：从集市安装现成应用，或用应用框架自己写一个应用并部署进去。前者适合标准集成，后者适合要访问内部系统、需要自定义界面或权限的场景。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 用官方旧单文件 `compose.yml` 启动，直接被拦下 | 该文件已标记弃用，容器里注入了 `DEPRECATED_COMPOSE` 环境变量强制要求确认 | 迁移到 `rocketchat-compose` 组合仓库的多文件方式，不要设 `DEPRECATED_COMPOSE_ACK` 硬顶过去 |
| 换过数据库镜像之后起不来、数据读不到 | 内置 MongoDB 的上游镜像发生过更换，旧数据目录与新镜像的初始化方式不兼容 | 按官方的迁移说明处理，先备份数据卷再切镜像；生产环境建议一开始就用外部托管的 MongoDB |
| 容器起来了但消息发不出、界面转圈 | 内存 MongoDB 没开副本集，或缺少 oplog 连接，实时消息依赖副本集 | 让 MongoDB 以 `--replSet` 启动并完成 `rs.initiate`，同时把 `MONGO_URL` 带上 `?replicaSet=<名字>`；生产环境补上 `MONGO_OPLOG_URL` |
| 上传的头像和大文件重启后不见了 | 存储目录没用持久化卷，容器重建就丢 | 给存储和数据库都挂持久化卷或改用对象存储；重建容器前确认卷还在 |
| 浏览器控制台报 WebSocket 连不上，消息不实时 | 反向代理只转发了 HTTP，没转发 WebSocket 升级 | 在 Nginx / Traefik 里为 WebSocket 配置转发；用官方 compose 的 Traefik 组合可省掉这一步 |
| 生成的分享链接、邮件里的链接指向 `localhost` | `ROOT_URL` 没改成对外的正式地址 | 部署前先把 `ROOT_URL` 设成用户实际访问的域名（含协议） |
| 多实例横向扩容后行为诡异 | 每个实例的 `INSTANCE_IP` 没设成各自宿主机地址，实例间认不出彼此 | 多节点部署时给每个节点单独设 `INSTANCE_IP`，并保证实例间 3000 端口互通 |
| 移动端收不到推送 | 自建实例没有配置推送网关 | 按官方文档配置推送服务，或者接受移动端需要保活/前台才能收消息的限制 |
| 直接在 `docker-compose.yml` 里写数据库密码并提交到仓库 | 镜像用的是环境变量，明文密码就落在文件里 | 用 `.env` 文件并加进 `.gitignore`，或用 Docker secrets；对外只暴露反代端口，不要暴露 Mongo |
| 反代配了 URL 重写做跳转 | 鉴权和会话路径被改写后对不上 | 直接配置反向代理转发，不要引进 URL 重写规则 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取镜像与 compose 组合仓库；监听对外端口供用户和客户端连接；启用联邦或集市时连外部服务 |
| 读取文件 | 是 | 读取 `.env` 配置、数据库与存储卷中的消息和文件、TLS 证书、日志 |
| 写入文件 | 是 | 数据库与文件存储的持久化写入；日志、上传文件、导出的归档数据 |
| 凭证 | 是 | 数据库账号密码、`ROOT_URL` 与域名证书、管理员账号、外部接口的会话凭据或 token、SMTP 与单点登录密钥。**全部按密钥管理，不要写进 compose 文件或提交进仓库** |
| 子进程 / 后台常驻 | 是 | 容器长期常驻；数据库、反代、NATS 监控等一组服务协同运行；升级与备份会启停容器 |

## 触发场景

- 「帮我在内网用 Docker 部署一套 Rocket.Chat，配上反代和数据库。」
- 「为什么我的 Rocket.Chat 消息不实时刷新？」
- 「从旧的单文件 compose 迁到官方推荐的多文件组合，怎么改？」
- 「我要写个内部机器人，把告警推到某个频道，走哪条路？」
- 「多实例扩容之后实例之间不通，`INSTANCE_IP` 该怎么设？」
- 「Rocket.Chat 升级前要做哪些备份？」

## 能力边界

**覆盖**：

- 部署选型与落地：Docker、Podman（无根与 rootful）、Kubernetes、隔离网络部署、云托管之间的差异和命令骨架。
- 运行时配置：`ROOT_URL`、`PORT`、`MONGO_URL`、`MONGO_OPLOG_URL`、`INSTANCE_IP` 等环境变量的作用与常见错配。
- 高可用与横向扩展：MongoDB 副本集、多实例、负载均衡与反代的关键点。
- 集成与扩展路线：集市应用、应用框架自研、外部接口的调用思路。
- 运维动作：日志查看、升级顺序、备份优先级、常见故障定位方向。

**不覆盖**：

- 外部接口的完整字段级参数说明——接口数量多且会变，**以官方 API 文档为准**。
- 应用框架与前端 SDK 的开发细节。
- 桌面端与移动端客户端的打包、发布和推送证书申请流程。
- 具体的合规认证结论（平台提供合规相关能力，不代表你的部署自动合规）。
- 替你决定是否该选它——这取决于数据主权要求、运维人力预算和现有通讯工具的现状。
- 商业版专属能力的授权与计费。

## 依赖条件

- 容器运行时：Docker 或 Podman；Kubernetes 路线需要可用集群。
- 数据库：MongoDB（生产环境建议副本集；外部托管实例需自行准备连接串与 oplog 权限）。
- 反向代理与 TLS：对外提供服务时需要，官方 compose 组合内置 Traefik 方案。
- 持久化存储：数据库卷 + 文件存储（本地卷或兼容对象存储）。
- 可选：NATS（消息总线）、Prometheus / Grafana（监控）、SMTP 账号、单点登录身份提供方凭据、推送服务。

## 已知限制

- 单文件 compose 已被官方标记为弃用，新部署不要沿用。
- 完整功能需要多个组件协同，不是单容器能覆盖的。
- 多实例部署对 `INSTANCE_IP` 和实例间网络互通有硬要求，配错会出现难以定位的异常。
- 部分能力（云托管、企业级特性、移动推送）依赖官方服务或商业授权。
- 升级涉及数据库结构变更，必须先备份；跨大版本升级的兼容范围以官方发布说明为准。

## 自检清单

执行前：

- [ ] 确认部署形态（Docker / Podman / K8s）和版本标签，不用 `latest` 裸跑生产。
- [ ] `ROOT_URL` 已设成对外正式地址，含协议。
- [ ] MongoDB 已启用副本集，`MONGO_URL` 带 `?replicaSet=`，生产环境已配 oplog。
- [ ] 数据库和文件存储都有持久化卷，且已完成一次备份。
- [ ] 密码与密钥走 `.env` 或 secrets，不在 compose 文件里明文出现。
- [ ] 反向代理已配置 WebSocket 转发，且没有引入 URL 重写。

执行后：

- [ ] `docker compose ps` 各服务状态正常，日志里没有数据库类连接报错。
- [ ] 用浏览器实际登录、发一条消息、上传一个文件，确认端到端通。
- [ ] 重启容器后确认消息和文件还在（验证持久化到位）。
- [ ] 确认对外只暴露反代端口，数据库端口没有直接暴露。
- [ ] 升级后核对版本号与官方发布说明的一致。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/RocketChat/Rocket.Chat | 上游仓库（安装与完整文档以它为准） |
| https://github.com/RocketChat/rocketchat-compose | 官方推荐的 compose 组合仓库 |
| https://github.com/RocketChat/Docker.Official.Image | 官方镜像仓库与 `env.example` |

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
