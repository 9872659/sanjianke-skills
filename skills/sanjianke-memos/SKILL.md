---
name: sanjianke-memos
slug: sanjianke-memos
displayName: 三剪客 · 碎片笔记速记
description: "Memos 碎片笔记速记的部署与用法整理：单容器 Docker 起服务、MEMOS_* 环境变量、SQLite 与外部数据库切换、四级可见性与分享策略、个人访问令牌调用 API、内置 MCP 接入 AI 助手及常见坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "一个只按时间线组织的自托管速记服务的落地要点：一条 docker run 起服务、用环境变量配端口与数据库、用个人访问令牌打通 API 与 MCP，并说清可见性策略与升级注意事项。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 碎片笔记速记

大多数笔记工具在「记一条」这一步就要你先想好放哪个笔记本、起什么标题。它反过来：打开就写，写完就存，所有内容按时间倒序排成一条流，之后靠标签、搜索和置顶再找回来。

这个取舍换来的是极低的记录成本——随手一条链接、一段命令、一句会上听到的话，都可以直接扔进去，不用做任何归档决策。它同时是自托管的，一条命令起一个容器，数据落在你自己机器上的一个目录里。

**上游项目**：`Memos`　**仓库**：https://github.com/usememos/memos

## 什么时候用 / 不用

**用它**：

- 「我想要一个自己部署的速记本，随手记，不用选文件夹」。
- 需要**碎片信息的统一入口**：临时链接、命令片段、灵感、会上一句话，先记下来再整理。
- 团队或个人的**日志流**：按天/按周往下滚的时间线，比结构化的文档更贴近真实记录习惯。
- 想给 AI 助手接一个自己的笔记源——它自带 MCP 入口，可以用个人访问令牌挂上去。
- 要一个**可编程的轻量笔记后端**：每条内容都能通过 HTTP 接口读写，适合接脚本或小工具。

**不要用它**：

- **需要层级目录和复杂文档结构**。它不做文件夹树、不做长文排版，硬套会别扭。
- **要一个完整知识库工作空间**（文档 + 数据库 + 白板）。那是另一类工具，不是它。
- **要多人精细协作编辑**。它是「记录 + 分享」的模型，不是同一份文档多人同时改。
- **只是想临时在手机上记一条**。自托管意味着你得有一台一直在跑的机器；没有的话先用现成服务更实际。
- **要拿去当合规存档系统**。它不是为审计留痕、不可篡改这类需求设计的。

## 安装

### Docker（官方主推的单容器方式）

前置：宿主机装好 Docker。

```bash
docker run -d \
  --name memos \
  --restart unless-stopped \
  -p 5230:5230 \
  -v ~/.memos:/var/opt/memos \
  neosmemo/memos:stable
```

容器监听 `5230`，数据写在容器内 `/var/opt/memos`，映射到宿主机的 `~/.memos`。里面包含 SQLite 数据库和本地附件。

镜像标签的选择建议：`stable` 用于生产；有明确版本的标签（形如 `0.30.0`）用于完全固定版本；`latest` 偏开发向，不建议生产使用。具体可用标签以镜像仓库当前列表为准。

镜像提供多架构清单，会自动选对应变体（x86_64、ARM 64 位、ARM 32 位）。

容器内以非 root 用户运行（UID/GID 均为 `10001`），入口脚本会尝试修正挂载卷属主；宿主卷需要别的属主时用 `MEMOS_UID` / `MEMOS_GID` 覆盖：

```bash
docker run -d \
  --name memos \
  -p 5230:5230 \
  -v ~/.memos:/var/opt/memos \
  -e MEMOS_UID=1000 \
  -e MEMOS_GID=1000 \
  neosmemo/memos:stable
```

### 其它部署方式

官方文档另给了 Docker Compose、二进制、Kubernetes、源码构建四条路径：要可复现的配置与更省事的升级用 Compose；已有宿主级服务管理就上二进制；已在运维集群才用 Kubernetes；要定制或固定某个修订就源码构建。

### 常用环境变量

所有 `MEMOS_*` 变量与命令行参数一一对应：

| 变量 | 默认值 | 作用 |
|---|---|---|
| `MEMOS_PORT` | `8081` | HTTP 监听端口（容器镜像默认用 `5230`） |
| `MEMOS_ADDR` | 空 | 绑定地址，空表示所有网卡 |
| `MEMOS_DATA` | `/var/opt/memos` | 数据目录 |
| `MEMOS_DRIVER` | `sqlite` | 数据库后端 |
| `MEMOS_DSN` | 自动 | 数据库连接串 |
| `MEMOS_INSTANCE_URL` | 空 | 对外规范地址，与访问策略相互独立 |
| `MEMOS_DEMO` | `false` | 演示模式 |
| `MEMOS_LOG_LEVEL` | `info` | 日志级别（`debug` / `info` / `warn` / `error`） |
| `MEMOS_WEBHOOK_PRIVATE_NETWORK_ALLOWLIST` | 空 | 允许作为 Webhook 目标的私网主机名/IP/CIDR |

## 常用操作

**1. 起服务并确认在跑**

```bash
docker run -d --name memos --restart unless-stopped \
  -p 5230:5230 -v ~/.memos:/var/opt/memos neosmemo/memos:stable
docker logs memos
```

**2. 带上规范地址与端口启动（对外服务时建议给全）**

```bash
docker run -d --name memos --restart unless-stopped \
  -p 5230:5230 -v ~/.memos:/var/opt/memos \
  -e MEMOS_PORT=5230 \
  -e MEMOS_DRIVER=sqlite \
  -e MEMOS_INSTANCE_URL=https://memos.example.com \
  neosmemo/memos:stable
```

**3. 换 MySQL 或 PostgreSQL 作为后端**

```bash
# MySQL
docker run -d --name memos -p 5230:5230 -v ~/.memos:/var/opt/memos \
  -e MEMOS_DRIVER=mysql \
  -e MEMOS_DSN="user:password@tcp(mysql-host:3306)/memos" \
  neosmemo/memos:stable

# PostgreSQL
docker run -d --name memos -p 5230:5230 -v ~/.memos:/var/opt/memos \
  -e MEMOS_DRIVER=postgres \
  -e MEMOS_DSN="postgres://user:password@postgres-host:5432/memos?sslmode=disable" \
  neosmemo/memos:stable
```

用外部数据库时，挂载卷仍然有用——本地附件与实例数据还在里面。

**4. 用 Docker secret 传连接串（不把凭据写进环境变量）**

```bash
echo "postgres://user:password@host:5432/memos" | docker secret create memos_dsn -

docker run -d --name memos -p 5230:5230 -v ~/.memos:/var/opt/memos \
  -e MEMOS_DRIVER=postgres \
  -e MEMOS_DSN_FILE=/run/secrets/memos_dsn \
  --secret memos_dsn \
  neosmemo/memos:stable
```

`*_FILE` 后缀对任意 `MEMOS_*` 变量都生效。

**5. 升级：换容器，保留数据目录**

```bash
docker pull neosmemo/memos:stable
docker stop memos
docker rm memos
docker run -d --name memos --restart unless-stopped \
  -p 5230:5230 -v ~/.memos:/var/opt/memos neosmemo/memos:stable
```

因为数据在挂载卷里，只要沿用同一个数据目录且有备份，替换容器一般是安全的。

**6. 用个人访问令牌调接口**

令牌在应用内的用户设置里创建与吊销，形如 `memos_pat_` 前缀，明文只在创建时显示一次。

```bash
curl -H "Authorization: Bearer memos_pat_..." \
  https://memos.example.com/api/v1/memos
```

令牌以你的用户身份生效：用它调接口能做的事，等于你这个账号能做的事。

**7. 把 AI 助手接到内置的 MCP 入口**

该入口是主程序的一部分，不需要额外安装或开启，地址是 `https://<实例地址>/mcp`，用 Streamable HTTP 传输，认证同样用个人访问令牌。以 Claude Code 为例：

```bash
claude mcp add --transport http memos https://<实例地址>/mcp \
  --header "Authorization: Bearer <个人访问令牌>"
```

暴露的是一组围绕笔记的工具（列/查/建/改/删笔记、评论、附件、反应、关联、当前用户视图等），每条对应一个 REST 接口。工具带标准 MCP 注解（只读、破坏性、幂等），客户端可以据此在做删除类操作前先确认。

**8. 容器日常管理**

```bash
docker logs -f memos
docker stop memos
docker start memos
docker restart memos
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 按文档访问 8081 打不开，换成 5230 才行 | 二进制方式默认端口是 `8081`，容器镜像默认是 `5230`，两套默认值不一样 | 先分清你用的是容器还是二进制；容器按 `5230` 访问，也可以显式用 `MEMOS_PORT` 指定 |
| 挂载的目录写不进去，服务报权限错 | 容器以 UID/GID `10001` 的非 root 用户运行，宿主目录属主不匹配 | 让入口脚本自动修正属主，或用 `MEMOS_UID` / `MEMOS_GID` 覆盖成宿主目录的属主 |
| 新实例起来的策略和预期不符 | 访问策略（私密/公开）由实例设置决定，和规范地址是两件事；描述里也提到配置 URL 只在策略尚未存在时才初始化公开访问 | 明确用实例设置里的访问策略项来定，别指望改 URL 顺带改策略 |
| 关掉注册后自己都进不去 / 或者被陌生人注册 | 第一个注册的用户就是主机管理员，注册开关与首个账号的创建顺序很关键 | 起来后第一件事就是创建管理员并按需关掉注册；把这两步写进部署流程 |
| 明明上传了图片，笔记里却显示不出来 | 内联图片要求附件先绑定到该笔记，且要与引用它的那次修改在同一轮内完成；只上传未绑定不算 | 按接口约定在上传后完成绑定再引用；用官方客户端则不必手工处理 |
| 用了很久的集成在升级后突然报错 | 接口在新版本有过若干破坏性变更（视图相关服务与路径调整、评论可见性默认值、反应字段、S3 附件链接形式等） | 升级前对照官方迁移说明逐项核对客户端改动；把集成按版本固定，别盲升 |
| 分享出去的附件链接在换存储后失效 | 托管在对象存储上的附件不再通过原字段暴露预签名地址 | 改用带认证的文件路由，并保留分享链接的授权校验 |
| 浏览器里的第三方客户端连不上 | 跨域请求只接受 Bearer 令牌方式；Cookie 认证仅限同源 | 不要围绕浏览器会话 Cookie 做第三方客户端，统一用个人访问令牌 |
| 私网 Webhook 发不出去或收到告警 | 默认不允许指向私网地址；有一个已弃用的整体放行开关 | 用白名单变量精确列出允许的主机名/IP/CIDR，而不是打开已弃用的整体开关 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取容器镜像；客户端、脚本与 AI 助手访问实例的 HTTP 接口与 MCP 入口；实例对外发 Webhook |
| 读取文件 | 是 | 读取挂载的数据目录（SQLite 库与本地附件）；用 `*_FILE` 方式时读取其中的凭据文件 |
| 写入文件 | 是 | 数据目录持续写入数据库与附件；升级时替换容器不动数据目录 |
| 凭证 | 是 | 个人访问令牌用于调接口与接 MCP；外部数据库的连接串是敏感信息。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | 这是一个需要长期运行的常驻服务（容器或系统服务），不是一次性命令 |

## 触发场景

- 「给我一个能自己部署的速记本，随手记不用建文件夹」
- 「Memos 的 docker run 命令怎么写？数据存哪」
- 「我想用 Postgres 存笔记，不想要 SQLite，怎么配」
- 「怎么让 AI 助手能读我的笔记」
- 「怎么生成 API 令牌、用 curl 列一下我的笔记」
- 「笔记只想自己看，但偶尔要分享单条出去，怎么设」

## 能力边界

**覆盖**：

- 部署形态：Docker 单容器、Docker Compose、二进制、Kubernetes、源码构建。
- 配置面：`MEMOS_*` 环境变量与命令行参数的对应关系、端口与绑定地址、日志级别、演示模式、数据目录。
- 数据库：默认 SQLite，可切换 MySQL 或 PostgreSQL；连接串可通过 `*_FILE` 从文件读取。
- 内容形态：Markdown 正文、`#标签`、清单（`- [ ]`）、附件与图片、置顶。
- 可见性：`PRIVATE` / `PROTECTED` / `PUBLIC` / `SPACE` 四级，以及分享链接的创建与吊销。
- 集成：个人访问令牌调用 REST 接口、内置 MCP 入口接 AI 助手、Webhook 事件推送、浏览器扩展做网页剪藏。
- 运维：日志查看、容器启停、按数据目录做升级与回滚。

**不覆盖**：

- 不做多层级目录与复杂文档排版。想要文件夹树或长文编辑，它不合适。
- 不做同一份文档的多人实时协同编辑。它的协作模型是记录与分享。
- 不覆盖企业级合规能力（审计留痕、不可篡改存档、精细审批流）。
- 不负责反向代理与 HTTPS 的具体配置，那属于部署方的基础设施工作；官方另有反向代理章节可参考。
- 不提供该项目的官方技术支持，社区集成（例如某个即时通讯机器人）也由其各自维护者负责。

## 依赖条件

- 运行 Docker 的机器（容器方式）；或按二进制方式准备宿主级服务管理。
- 一条常驻的运行环境——它需要一直在线，客户端与 API 才有东西可连。
- 存储：数据目录所在的宿主路径需要有足够空间；用外部数据库时，附件与实例数据仍会写在该目录。
- 可选：MySQL 或 PostgreSQL 实例（切换后端时）；反向代理与证书（对外提供服务时）；SMTP 或 OAuth 相关配置（按需）。
- 使用 API 与 MCP 需要先创建个人访问令牌。

## 已知限制

- 升级不是完全无感的。接口层存在过破坏性变更，自有集成在升级前必须核对官方迁移说明，否则可能直接报错。
- 社区集成（如即时通讯机器人）由社区维护，行为与可用性不由本项目保证。
- 浏览器端的第三方客户端受同源与跨域策略限制：Cookie 认证仅限同源，跨域必须用 Bearer 令牌。
- 私网 Webhook 默认被拒，需要显式白名单；存在一个已弃用的整体放行开关，不建议使用。
- 版本号、默认端口、环境变量清单与接口路径都会随版本变化，执行前请以官方文档当前内容与镜像实际标签为准。

## 自检清单

- [ ] 确认部署形态（容器 / 二进制 / Compose），并按对应形态的默认端口访问（容器 `5230`，二进制 `8081`）。
- [ ] 数据目录已映射到宿主固定路径，且该路径在备份范围内。
- [ ] 宿主目录属主与容器运行用户（UID/GID `10001`）对得上，或用 `MEMOS_UID` / `MEMOS_GID` 显式覆盖。
- [ ] 实例起来后立刻创建管理员账户，并按需要决定注册是否开放。
- [ ] 明确设置访问策略（私密还是公开），不依赖「配了 URL 就会变成公开」这种假设。
- [ ] 用外部数据库时，连接串通过 `MEMOS_DSN` 或 `*_FILE` 传入，不要把凭据写进镜像或提交进版本库。
- [ ] 需要程序化访问时，在用户设置里创建独立令牌，并按集成分开管理，便于单独吊销。
- [ ] 需要接 AI 助手时，确认版本支持内置 MCP 入口、客户端用 Streamable HTTP、认证头带 Bearer 令牌。
- [ ] 升级前先备份数据目录，并对自有集成核对官方迁移说明。
- [ ] 需要给外部发事件时，用白名单变量精确限定目标，不启用已弃用的整体放行开关。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/usememos/memos | 上游仓库（安装与完整文档以它为准） |

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
