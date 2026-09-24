---
name: sanjianke-appflowy
slug: sanjianke-appflowy
displayName: 三剪客 · 开源协作工作空间
description: "AppFlowy 工作空间的部署与用法整理：桌面端与移动端安装、Docker Compose 自托管云、文档与数据库视图、实时协作架构，以及自托管部署常见坑与开源/商业版边界。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "一套把文档、数据库视图和看板装进同一个工作空间的开源协作工具的落地要点：从官方渠道装客户端、用 Docker Compose 起自托管云、配置域名与凭据，并说清哪些能力仍属闭源商业部分。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 开源协作工作空间

它是一个把「文档 + 多视图数据库 + 看板」放进同一个空间里的协作工具，客户端覆盖桌面和移动端，可以只用官方托管服务，也可以整套跑在自己的服务器上。真正让人选它的理由通常是两条：内容不锁在别人的云里，以及多端同步是原生的。

所以这个 Skill 要解决的是「怎么把它跑起来、怎么让别人也能用、以及哪些部分是开源而哪些不是」——尤其是最后一条，很多人自托管到一半才发现服务端已经不是开源代码了。

**上游项目**：`AppFlowy`　**仓库**：https://github.com/AppFlowy-IO/AppFlowy

## 什么时候用 / 不用

**用它**：

- 「想找个能自己掌控数据的 Notion 类工具」——文档、待办、项目表放一起，客户端装在自己电脑上。
- 需要**自托管一整套协作云**：自己的域名、自己的 Postgres/MinIO、团队通过自己的服务器登录而不是官方云。
- 团队要的东西是「文档 + 数据库视图 + 看板」三合一的轻量工作台，不想为排版和美术效果付额外成本。
- 要跨 macOS / Windows / Linux / iOS / Android 用同一份内容。
- 关心「代码是不是开源的、数据落在哪」这类问题，需要给出明确边界。

**不要用它**：

- **只想要浏览器里随手记一条**。装客户端、配同步、拉容器，这条链对碎片速记来说太重了。
- **要的是高保真版式**。它面向结构化内容编辑，不解决「把这份 Word 原样复刻出来、能直接打印」的需求。
- **想让 Agent 通过 HTTP 接口批量写页面**。主干仓库对外提供的是协作云能力，不是一套面向自动化的内容 API；要程序化写入得自己评估自托管服务端的接口，别假设有稳定公开的写入端点。
- **需要处理海量附件或大规模多媒体**。自托管时对象存储（MinIO 或 S3 兼容后端）由你自己运维和扩容，容量与成本都在你这边。
- **只是要一份本地 Markdown 文件**。它是常驻的多端同步应用，不是一次性导出工具。

## 安装

### 客户端（桌面 / 移动）

桌面端在仓库的 Releases 页面按平台下载（macOS、Windows、Linux）；Linux 用户也可以走 FlatHub、Snapcraft 这类发行渠道。移动端在 App Store 与 Play Store 上架，移动端对系统版本有要求（Android 需较新版本，ARMv7 不支持）。具体版本号以 Releases 页面当前内容为准，这里不写死。

### 自托管云（Docker Compose）

官方给出的自托管路径是 `AppFlowy-SelfHost-Commercial` 仓库，只需要宿主机装好 Docker：

```bash
git clone https://github.com/AppFlowy-IO/AppFlowy-SelfHost-Commercial
cd AppFlowy-SelfHost-Commercial
cp deploy.env .env
docker compose up -d
```

起来之后默认在宿主机 80 和 443 端口提供服务，按路径分流：`/gotrue` 是认证服务，`/api` 是协作云接口，`/ws` 是实时同步 WebSocket，`/web` 是用户管理后台，`/pgadmin` 是数据库面板，`/minio` 是对象存储界面，`/portainer` 是容器管理。

上线前至少要改这几项（都在 `.env`）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `FQDN` | `localhost` | 换成你自己的域名 |
| `SCHEME` / `WS_SCHEME` | `http` / `ws` | 启用 TLS 后改成 `https` / `wss` |
| `POSTGRES_PASSWORD` | `password` | 必须换掉 |
| `AWS_ACCESS_KEY` / `AWS_SECRET` | `minioadmin` / `minioadmin` | 对象存储凭据，必须换掉 |
| `GOTRUE_JWT_SECRET` | `hello456` | 认证签名密钥，必须换掉并妥善保管 |
| `GOTRUE_ADMIN_EMAIL` / `GOTRUE_ADMIN_PASSWORD` | `admin@example.com` / `password` | 后台管理员账户 |
| `AI_OPENAI_API_KEY` | 空 | 留空可用核心功能，只是没有内置 AI |

`APPFLOWY_BASE_URL`、`APPFLOWY_WEBSOCKET_BASE_URL` 由 `FQDN` 和 `SCHEME` 拼出来，通常不用单独改。改完 `docker compose up -d` 重新拉起即可。

## 常用操作

**1. 拉起整套服务并确认状态**

```bash
docker compose up -d
docker compose ps
```

**2. 查某个服务的日志（服务名以 compose 文件为准，常见有 appflowy_cloud、gotrue、postgres、minio、redis、nginx）**

```bash
docker compose logs -f appflowy_cloud
```

**3. 日常更新：拉新镜像后重建**

```bash
docker compose pull
docker compose up -d
```

**4. 进 Postgres 容器看一眼数据（容器名以 compose 文件为准）**

```bash
docker compose exec postgres psql -U postgres -d postgres
```

**5. 直接用官方预构建镜像，跑一个最小依赖组合**

```bash
docker pull appflowyinc/appflowy_cloud
```

镜像标签可在 Docker Hub 上按当前可用版本选择。这个方式绕开了官方 compose 的一体化编排，需要你自己把 Postgres、Redis、对象存储和认证服务接上。

**6. 客户端连自托管服务**

客户端登录页选择自托管入口，填你部署好的服务器地址即可，不需要额外参数。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 服务端起不来、日志报缺组件，或客户端连上后功能对不上 | 拿归档的 `AppFlowy-Cloud` 仓库去构建服务端了；新版服务端不再由开源仓库产出 | 自托管统一走 `AppFlowy-SelfHost-Commercial` 与官方预构建镜像，不要自己从归档仓库编译服务端 |
| 部署完被人扫到、对象存储被访问 | `.env` 里的默认口令（Postgres、MinIO、JWT、管理员）没换就直接对外开端口 | 首次启动前把这些值全部替换成随机强口令，且不要提交进版本库 |
| 服务起了但一直报数据库连不上 | `APPFLOWY_DATABASE_URL` 里直接放了含特殊字符的密码，URL 没做百分号编码 | 把密码里的 `@`、`:` 之类字符转成 URL 编码形式再拼进去（比如 `@` 写成 `%40`） |
| 前端能打开，实时协作、页面同步不工作 | 换了域名或上了 HTTPS，但 WebSocket 地址还是 `ws://`，或者没走 `/ws` 路径 | `SCHEME` 与 `WS_SCHEME` 成对改，确认 `APPFLOWY_WEBSOCKET_BASE_URL` 指向 `wss://<域名>/ws/v2` |
| 新用户注册后卡在确认邮件那一步 | 自动确认关闭（`GOTRUE_MAILER_AUTOCONFIRM=false`）却没有配 SMTP | 要么打开自动确认，要么把 SMTP 相关变量配全；不确定就先看 gotrue 容器日志 |
| 打开 `/web` 或 `/pgadmin` 登录不了后台 | 后台管理员账户由认证服务首次启动时按 `.env` 里的值创建；中途改 `.env` 不会自动改已有账户 | 启动前定好管理员邮箱口令；已经创建过就按官方方式在用户管理里重置 |
| 镜像拉取慢或失败 | 部署依赖 Docker Hub、GitHub 容器仓库等多个源，网络受限时容易断 | 提前确认各组件镜像可访问；离线环境按官方提供的镜像导出/导入方式处理，不要临时改 compose 指向不明来源 |
| 把服务端当成「全开源」对外承诺 | 客户端与编辑器是开源的，但协作云的当前服务端代码是闭源商业发行版，且早期开源云仓库已归档 | 回答合规问题时按实际边界说话：开源的是客户端与本仓库主干代码，自托管服务端走官方商业发行版 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 下载客户端安装包或容器镜像；客户端与自托管服务端之间做内容同步 |
| 读取文件 | 是 | 读取 `deploy.env`、compose 文件与 `.env` 等部署配置；导入本地文档时读取源文件 |
| 写入文件 | 是 | 生成 `.env` / compose 配置；服务端把附件写入挂载的对象存储目录；客户端把本地库写入用户数据目录 |
| 凭证 | 是（部署方自备） | 数据库口令、对象存储 Access Key、JWT 密钥、后台管理员账户，以及可选的大模型 API Key。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | 自托管是一组长期运行容器（网关、协作云、认证、数据库、缓存、对象存储、后台任务），需要常驻 |

## 触发场景

- 「帮我找一个能自己部署、数据在本地的工作空间，替代 Notion」
- 「AppFlowy 怎么自托管？给我一套能跑的 Docker Compose 流程」
- 「我们团队想用 AppFlowy，怎么把服务器搭起来、怎么配域名」
- 「这个工具是开源的吗？自托管版和官网版有什么区别」
- 「文档、看板、表格放一个空间里，有没有开源方案」
- 「客户端装好了，怎么连到我们自己的服务器」

## 能力边界

**覆盖**：

- 客户端侧：桌面端（macOS / Windows / Linux）、移动端（iOS / Android）、Linux 发行渠道与应用的获取与使用。
- 自托管云：基于 Docker Compose 的一体化部署，含网关、认证、协作云、数据库、缓存、对象存储与后台任务。
- 内容形态：文档块编辑、多视图数据库（表格 / 看板 / 日历 / 画廊）、页面发布、工作区与成员管理。
- 协作能力：多端实时同步、权限控制（`APPFLOWY_ACCESS_CONTROL` 控制基于权限的访问控制）。
- 可选增强：接入 OpenAI 或 Azure OpenAI 后启用语义检索与 AI 摘要；接入实时转写服务后启用相应能力。
- 部署配置：域名、TLS、SMTP、OAuth（Google / GitHub / Discord / Apple）、SAML、对象存储切换（MinIO ↔ AWS S3）。

**不覆盖**：

- 不提供面向自动化的内容写入接口。想程序化批量建页面、批量改数据库，本 Skill 不给方案，也不假设存在稳定的公开写入端点。
- 不做文档格式转换。把 Word / PDF 原样高保真转成它的页面结构，不在能力范围内。
- 不替代对象存储运维。附件容量、备份、生命周期策略由你自己在 MinIO / S3 那一层解决。
- 不负责 SaaS 账号、官方订阅与商业授权代办，也不提供该项目的官方技术支持。
- 不覆盖从源码构建客户端的完整工具链，那是另一条路径，官方有单独的开发文档。

## 依赖条件

- 用客户端：按平台下载安装包即可，无需自备服务端。
- 自托管：宿主机装 Docker 与 Docker Compose；官方部署目标是单机单容器组，宿主机需要开放 80 / 443（或你在 `.env` 里改成别的端口）。
- 自托管的组件依赖：PostgreSQL、Redis、S3 兼容对象存储（默认 MinIO）、认证服务、反向代理，随官方 compose 一起拉起。
- 对外提供服务需要域名与 HTTPS 证书；只在内网试用时用 IP 或 localhost 即可。
- 需要自备：数据库口令、对象存储凭据、JWT 密钥、后台管理员账户。
- 可选：OpenAI 或 Azure OpenAI 的 Key（AI 功能）、SMTP 账号（邮件确认）、OAuth/SAML 应用凭据（第三方登录）、转写服务 Key。

## 已知限制

- 客户端开源（AGPLv3），但协作云的当前服务端由闭源商业发行版提供，早期开源云仓库已归档、不再维护。规划合规与二次开发时要按这个边界判断，不要默认服务端可以自由 fork 改造。
- 自托管的免费档位有人数限制（单席位，另加有限数量的访客编辑者），往上要企业档；具体额度以官方定价页当前内容为准。
- 主干客户端项目的构建依赖 Flutter 与 Rust 工具链，自己编译需要按官方开发文档准备对应版本，容易在环境上耗时。
- 部分依赖需要外网可达（镜像源、可选的大模型接口、可选邮件服务）。完全离线部署需要额外做镜像导入。
- 变量名、服务名与镜像标签会随版本调整，执行前建议以官方自托管仓库的 `deploy.env` 与 compose 文件当前内容为准。

## 自检清单

- [ ] 先确认要的是**客户端**还是**自托管服务端**，两件事的命令完全不同。
- [ ] 客户端：从官方 Releases 或官方推荐的应用商店渠道获取，不要在来源不明的站点下载安装包。
- [ ] 自托管：确认用的是 `AppFlowy-SelfHost-Commercial` 仓库，而不是已归档的开源云仓库。
- [ ] 自托管：宿主机已装 Docker 与 Docker Compose，端口 80 / 443（或自定义端口）未被占用。
- [ ] `cp deploy.env .env` 之后，**逐项**确认 `POSTGRES_PASSWORD`、`AWS_ACCESS_KEY` / `AWS_SECRET`、`GOTRUE_JWT_SECRET`、管理员账户都已改过默认值。
- [ ] 改了 `FQDN` 或 `SCHEME`，就顺手确认 `APPFLOWY_WEBSOCKET_BASE_URL` 是 `wss://` 且带 `/ws/v2`。
- [ ] 数据库口令含特殊字符时，已做 URL 编码再写进 `APPFLOWY_DATABASE_URL`。
- [ ] `docker compose up -d` 后逐个确认容器状态，异常的先看对应服务日志再改配置。
- [ ] 对外暴露之前，确认 `.env`、compose 文件、备份文件都不在公开可访问的位置。
- [ ] 涉及 AI 或邮件功能时，确认对应 Key / SMTP 已配置，否则明确告知用户这些能力不可用。
- [ ] 回答「是不是开源」这类问题时，按实际边界说明客户端与服务端的不同授权状态。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/AppFlowy-IO/AppFlowy | 上游仓库（安装与完整文档以它为准） |

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
