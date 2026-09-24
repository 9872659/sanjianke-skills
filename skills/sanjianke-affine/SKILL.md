---
name: sanjianke-affine
slug: sanjianke-affine
displayName: 三剪客 · 知识库与协作白板
description: "AFFiNE 知识库与协作白板的落地整理：Docker Compose 自托管、config.json 与外部访问地址配置、Postgres/Redis/对象存储与备份恢复、本地优先协作原理，以及部署与升级常见坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "一个把文档和无限画布合成一体的开源工作空间的部署要点：用 Docker Compose 起自托管实例、配置外部访问地址与可选 AI、备份 Postgres 与附件目录，并避开迁移容器与数据库角色这类典型报错。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 知识库与协作白板

它把「文档」和「无限画布」这两件原本分开的事合到一个页面里：同一块内容既能当结构化文档读，也能拖到画布上摆成白板、思维导图或演示稿。对用惯了「文档一个软件、白板另一个软件」的人来说，省掉的是两份内容来回同步的那一步。

除此之外它还有一个容易被低估的特点：本地优先。内容先落在你自己的设备上，再通过协作通道同步，所以断网时也能继续写；数据在你磁盘上，云只是同步层。这个 Skill 主要讲怎么把它自托管起来、怎么配才不出错，以及它的边界在哪。

**上游项目**：`AFFiNE`　**仓库**：https://github.com/toeverything/AFFiNE

## 什么时候用 / 不用

**用它**：

- 「我们要一个文档 + 白板二合一的知识库，而且要能自己部署」。
- 团队已经在自建服务器上跑别的服务，现在要把这套工作空间也纳入自己的域名和运维体系。
- 关心**数据落点**：文档、画布、附件都要在自己的 Postgres 与对象存储里，不接受托管版本。
- 强依赖**实时协作**，而且希望断网或服务短暂不可用时还能继续编辑（本地优先）。
- 需要给一份自托管实例做备份、恢复、升级的方案，而不是只把容器拉起来就完事。

**不要用它**：

- **不想维护 Postgres、Redis、备份、HTTPS、升级这条链**。托管版本才是更省事的选择，自托管会长期占用运维精力。
- **要的是纯白板工具**。只想画流程图、做无限画布，用专门的白板工具更直接，不必背上整套工作空间。
- **团队规模大、要 SSO、审计、细粒度管理后台**。这些属于另一档企业能力，当前可自由自托管的是社区版本。
- **只想把 Markdown 文件夹变成一个网站**。它的内容模型是块与画布，不是 Markdown 目录结构的渲染器。
- **想要一个纯 API 的内容后端**给程序批量读写。它面向的是人和界面的协作，不是给自动化流水线当数据库用的。

## 安装

### 客户端（桌面 / 移动）

从项目官网的下载页获取各平台客户端，或直接用官方在线实例试用功能。客户端既可以连官方云，也可以连你自己部署的实例。

### 自托管（Docker Compose，官方推荐方式）

前置：装好 Docker 与 Docker Compose v2，确认 `docker compose version` 能正常输出版本。

```bash
# 1) 建部署目录
mkdir affine
cd affine
mkdir -p config
```

```bash
# 2) 取当前版本的 Compose 文件
curl -L -o docker-compose.yml \
  https://github.com/toeverything/AFFiNE/releases/latest/download/docker-compose.yml
```

```bash
# 3) 取配置模板
curl -L -o config/config.json \
  https://github.com/toeverything/AFFiNE/releases/latest/download/config.json.example
```

打开 `config/config.json`，把 `server.externalUrl` 改成用户实际访问的地址。本地试用保持默认即可：

```json
{
  "server": {
    "name": "AFFiNE Self-hosted",
    "externalUrl": "http://localhost:3010"
  },
  "copilot": {
    "enabled": true,
    "byok": {
      "enabled": true
    }
  }
}
```

对外部署时改成最终 HTTPS 地址，例如 `https://affine.example.com`。新装不需要 `.env` 文件，运行时设置都在 `config/config.json` 里；Compose 文件本身已经包含了内部服务接线和相对数据目录。

```bash
# 4) 启动
docker compose up -d
docker compose ps
```

`affine_migration` 是一次性迁移容器，它跑完就退出，属于正常；`affine`、PostgreSQL、Redis 三个应保持运行。

```bash
# 5) 首次进入并创建管理员
# 浏览器打开 http://localhost:3010（或你配的 externalUrl），按页面引导创建初始管理员账户
```

官方 Compose 文件采用的镜像、端口与挂载目录（以当前版本为准）：

| 项 | 值 |
|---|---|
| 服务镜像 | `ghcr.io/toeverything/affine:stable`，迁移容器用同一镜像 |
| 主服务端口 | `3010` |
| Postgres 镜像 | `pgvector/pgvector:pg16` |
| 容器名 | `affine_server`、`affine_migration_job`、`affine_redis`、`affine_postgres` |
| 数据挂载 | Postgres 数据 `./data/postgres`、附件 `./data/storage`、配置 `./config` |

Compose 默认不对外发布 Postgres 与 Redis 端口，数据库的 trust 认证只在内部网络内有效。

## 常用操作

**1. 起服务并确认迁移是否成功**

```bash
docker compose up -d
docker compose ps
```

**2. 启动异常时看日志（迁移容器失败会让主服务一直等）**

```bash
docker compose logs --tail=200 affine affine_migration
```

**3. 备份 Postgres（从容器内读实际用户名与库名，兼容历史部署）**

```bash
docker exec affine_postgres sh -c \
  'pg_dump --format=custom --file=/tmp/affine.backup --username="$POSTGRES_USER" "$POSTGRES_DB"'
docker cp affine_postgres:/tmp/affine.backup ./affine.backup
```

**4. 校验备份文件可读，再挪到部署目录之外保存**

```bash
docker exec affine_postgres sh -c 'pg_restore --list /tmp/affine.backup >/dev/null'
```

**5. 恢复：先只起 Postgres，导入备份，再拉起整套**

```bash
docker compose up -d postgres
docker cp ./affine.backup affine_postgres:/tmp/affine.backup
docker exec affine_postgres sh -c \
  'pg_restore --format=custom --clean --if-exists --no-owner --no-privileges \
     --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" /tmp/affine.backup'
docker compose up -d
```

恢复前先停掉主服务；不要覆盖唯一一份数据库，也不要在验证恢复结果之前删掉旧的 Postgres 数据目录。

**6. 升级前先备份，再换镜像版本**

```bash
docker compose down
docker compose pull
docker compose up -d
```

具体版本切换方式与迁移注意事项以官方升级文档当前内容为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 主服务一直起不来，日志显示在等迁移 | `affine_migration` 是一次性任务，没成功完成主服务就不会启动 | 先看 `docker compose logs affine_migration`，多数是 Postgres 没就绪或数据库连接配置不对 |
| 备份/恢复时报 `role "affine" does not exist` | 把用户名写死成了 `affine`，而实际部署用的库角色不是这个名字 | 不要为了消掉报错去新建 `affine` 角色。改用运行中容器里的 `$POSTGRES_USER` / `$POSTGRES_DB` 来执行命令 |
| 换了数据库密码，但容器里还是旧密码 | 密码只在 Postgres 数据目录**首次初始化**时生效，事后改配置不改变已初始化的库 | 首次启动前就定好强口令；已经初始化过就按官方 Postgres 文档在库内改角色密码 |
| 部署后附件、图片全丢 | 附件默认落在 `./data/storage`，这个目录不在数据库备份里 | 备份时必须把 Postgres 归档和 storage 目录**成对**保存；数据库单独恢复恢复不出文件 |
| 实例数据攒起来之后不敢动目录 | `./data/postgres`、`./data/storage`、`./config` 三者共同构成完整实例 | 部署时就把目录定在稳定位置并纳入备份；不在有数据后迁移这两个目录，除非按备份恢复流程走 |
| 升级后服务报错、回退也回不去 | 新版镜像可能带数据库结构变更，旧版本服务读不了新结构 | 升级前完成备份并**实际验证过一次恢复**；按 release notes 安排维护窗口，别在生产高峰直接 `pull` |
| 照着老教程建 `.env`、改里面的变量却没生效 | 新装已不再用 `.env` 承载运行配置，配置在 `config/config.json` | 新装只改 `config/config.json`；如果是历史 `.env` 部署升级过来的，按官方迁移说明搬到新布局 |
| 自建 Postgres 上 AI 检索能力不完整 | AI 相关能力依赖 `pgvector` 扩展 | 自维护 Postgres 时手动安装该扩展；直接用官方 Compose 里的 `pgvector` 镜像则已包含 |
| 内网试用正常，对外发布后分享链接打不开 | `server.externalUrl` 还是 `localhost`，生成出去的链接都指向本机 | 对外前把 `externalUrl` 改成最终 HTTPS 域名，并配好反向代理与证书 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取官方 Compose 文件、配置模板与容器镜像；客户端与自托管实例之间做实时同步 |
| 读取文件 | 是 | 读取 `config/config.json` 与 Compose 文件；恢复流程中读取数据库备份归档 |
| 写入文件 | 是 | 写出 compose 与配置文件；Postgres 数据、附件与运行配置写入部署目录下的挂载卷 |
| 凭证 | 是（部署方自备） | 数据库口令、对象存储凭据、OAuth / SMTP 凭据；启用 AI 时需要自备模型服务商的 Key。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | 自托管实例由多个长期运行容器组成（应用服务、迁移任务、数据库、缓存，以及可选的监控组件） |

## 触发场景

- 「帮我自托管一个文档 + 白板的开源工作空间」
- 「AFFiNE 的 Docker Compose 怎么配？externalUrl 填什么」
- 「这套东西的数据怎么备份和恢复」
- 「升级后服务起不来，migration 容器好像失败了，怎么排查」
- 「本地优先是什么意思？断网还能用吗」
- 「我们想用社区版自托管，有什么限制需要注意」

## 能力边界

**覆盖**：

- 客户端获取与使用：桌面端、移动端，以及连接自托管实例的方式。
- 自托管全流程：Docker Compose 部署、首次管理员创建、`config/config.json` 配置、域名与 HTTPS 接入。
- 数据面：Postgres 备份与恢复、附件存储目录的备份、配置文件的留存。
- 组件面：Postgres（含 `pgvector` 用于 AI 检索）、Redis、对象存储（本地目录或 S3 兼容服务）。
- 可选管理能力：用户管理（导入、重置密码、封禁/删除）、OAuth 2.0 登录、SMTP 邮件通知、监控、索引器开关、AI 的 BYOK 配置。
- 升级路径：Compose 方式升级、历史 `.env` 部署的迁移。

**不覆盖**：

- 不做内容格式转换。把外部文档高保真导入成它的块结构，不在范围内。
- 不提供程序化的内容 API 方案。要拿它当自动化写入的后端，本 Skill 不给做法。
- 不覆盖企业版能力，例如品牌定制与 SSO 之类被划到另一档的功能。
- 不负责 Kubernetes 编排、集群高可用、多副本部署，官方自托管入口是单机 Compose。
- 不提供该项目的官方技术支持，也不代办授权与商业档位。

## 依赖条件

- 硬件（官方建议）：至少 4 核 CPU；基础使用 2 GB 内存，如果文档较大（上万字级别）建议 4 GB；服务端自身约需 1.5 GB 空闲磁盘，另外按文档与附件量预留 Postgres 与对象存储空间。
- 软件：Docker 与 Docker Compose v2。
- 必需组件：Postgres（唯一受支持的数据库）与 Redis（缓存、后台任务与同步的基础，缺了跑不起来）。
- 默认 Compose 自带 Postgres、Redis 与本地存储目录；生产环境可换成外部 Postgres、外部 Redis 与 S3 兼容对象存储（如兼容 AWS S3 的服务或 Cloudflare R2）。
- 对外提供服务需要域名、HTTPS 证书与反向代理配置。
- 可选：AI 功能需要自备模型服务商 Key（BYOK），官方文档给出了若干提供商的接入方式。

## 已知限制

- 官方推荐的自托管方式是 Docker Compose，单机部署；Kubernetes 与高可用不在官方自托管引导的主线上。
- 内存占用与文档规模强相关：官方给出的观测是合并一个上万次修改的文档，内存峰值可达 1 GB 级别，超大文档场景要预留资源。
- `pgvector` 需要自维护 Postgres 时手动安装，否则 AI 相关能力受限。
- AI 能力是 BYOK 模式，需要自备第三方模型服务 Key，费用与配额由该服务商决定，本项目不提供模型额度。
- 项目迭代频繁，配置方式发生过迁移（早期 `.env` 部署与新式 `config/config.json` 两种形态并存）。变量名、镜像标签与 Compose 内容会随版本变化，执行前请以官方文档与仓库当前内容为准。
- 社区版本可自由自托管；企业版本尚未发布，相关高级能力暂不可得。

## 自检清单

- [ ] 先判断形态：只是自己用 → 官网下载客户端；要独立域名与数据主权 → 自托管。
- [ ] `docker compose version` 能正常输出，确认用的是 Compose v2。
- [ ] 部署目录定在稳定位置（`./data/postgres`、`./data/storage`、`./config` 都会长期写入），不要放在临时目录。
- [ ] `config/config.json` 里的 `server.externalUrl` 已改成用户实际访问的地址；内网试用也要确认端口对得上。
- [ ] `docker compose up -d` 后确认迁移容器成功退出、其余容器保持运行。
- [ ] 首次进入界面完成管理员账户创建，并确认能正常登录。
- [ ] 备份同时覆盖三样：Postgres 归档、附件存储目录、配置文件；只备份数据库不算完整。
- [ ] **实际验证过一次恢复流程**，而不是只生成了备份文件。
- [ ] 对外发布前配好域名、HTTPS 与反向代理，避免出现 `localhost` 链接。
- [ ] 升级前完成备份、看过目标版本的变更说明，并安排了维护窗口。
- [ ] 启用 AI 时确认已配好模型服务商 Key（BYOK），并知道调用会产生第三方费用。
- [ ] 自建 Postgres 时确认 `pgvector` 扩展已装，否则 AI 检索能力会缺。
- [ ] 回答「社区版能不能商用自托管」这类问题时，按当前授权与实际档位说明，不夸大也不含糊。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/toeverything/AFFiNE | 上游仓库（安装与完整文档以它为准） |

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
