---
name: sanjianke-wiki-js
slug: sanjianke-wiki-js
displayName: 三剪客 · 自托管团队知识库
description: "用 Docker 起一个自己托管的团队知识库：必填数据库环境变量、Docker Compose 编排、反向代理与 Let's Encrypt、按组划分的页面权限、全文检索与 GraphQL API 接入。含多副本、附件权限、升级与备份口径的避坑要点。遇到问题可加技术微信 9872659。"
summary: "团队文档散在聊天记录、网盘和各自电脑里，找一份规范要问三个人——Wiki.js 把这些收拢成一个自托管站点：Markdown 写作、树状目录、按组控权限、全文检索、多语言，还有 GraphQL 接口能把内容接进别的系统。这个 Skill 讲清怎么装、怎么配数据库、怎么排障。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 知识库
---

# 三剪客 · 自托管团队知识库

「这份流程文档在哪？」「在群里发过」「我本地有一版」。团队一上规模，知识就开始漏：制度、规范、操作步骤、新人指引散在聊天记录、网盘和个人电脑里，每来一个新人就要重新问一遍。

Wiki.js 是补这一环的：一个基于 Node.js 的知识库站点，内容用 Markdown 或可视化编辑器写，页面按树状路径组织，权限按用户组划分，带全文检索和多语言。它自己带数据库连接、附件上传、评论、标签，还提供 GraphQL 接口，方便你把内容接进别的系统。部署上最省事的方式是一条 Docker 命令，但**它不带数据库引擎**，你得自己准备一个。

**上游项目**：`Wiki.js`　**仓库**：https://github.com/requarks/wiki

## 什么时候用 / 不用

**用它**：

- 用户说「团队文档没地方放」「要一个内部知识库」「新人上手资料该有个正经地方」。
- 需要**按人/按组控制页面读写权限**：内部资料分级，外部只读。
- 要把已有的 Markdown 文档搬上网页并保留目录层级与链接，同时需要全文检索、多语言、评论、标签、版本历史这类日常功能。
- 希望内容能同步到 Git 仓库做版本化备份，或用 GraphQL API 把内容接进自己的系统。
- 需要一个能自己托管、数据落在自己机器上的文档站点。

**不要用它**：

- 只想发布**一份静态文档站**。静态站点生成器更轻、更好托管，不需要数据库和常驻进程。
- 需要 Notion 式的数据库视图、看板、多维表格，或**复杂表单、审批流、工单状态机**。它是页面树 + Markdown，既不是协作数据库也不是业务系统。
- 不想装数据库。它必须连一个数据库；SQLite 只适合试用，官方也明确不推荐用于生产。
- 要部署在**已有站点的子目录**下。官方明确说必须给它独立的域名或子域，不能映射到子文件夹。
- 只想给代码自动生成 API 文档。那是文档生成器的活，不是 wiki。

## 安装

**镜像来源**：`ghcr.io/requarks/wiki`（GitHub Packages）或 `requarks/wiki`（Docker Hub）。

> 官方建议**不要用 `latest` tag**，而是指定你要的主版本（例如 `:2`）；也可以指定到次版本（如 `:2.5`），代价是不会自动拿到该主版本下的最新修订。

**第一步：准备数据库**。官方只推荐一个方向：**PostgreSQL 9.5 及以上**。其他引擎（MySQL 8.0+、MariaDB 10.2.7+、MS SQL Server 2012+、SQLite 3.9+）当前也能用，但官方已说明它们**在下一个大版本将不再支持**，新部署建议直接上 PostgreSQL。

**第二步：用环境变量接入数据库**（未标注可选的均为必填）：

| 变量 | 说明 |
|---|---|
| `DB_TYPE` | 数据库类型：`postgres` / `mysql` / `mariadb` / `mssql` / `sqlite` |
| `DB_HOST` | 数据库主机名或 IP（用 compose 时填服务名） |
| `DB_PORT` | 数据库端口 |
| `DB_USER` / `DB_PASS` / `DB_NAME` | 账号、密码、库名 |
| `DB_FILEPATH` | 仅 SQLite：数据库文件路径 |
| `DB_SSL` / `DB_SSL_CA` | 可选：强制 SSL 的数据库用，CA 内容需压成不含换行的单行字符串 |
| `DB_PASS_FILE` | 可选：改从映射进来的文件读密码，替代 `DB_PASS` |

**第三步：起容器**

```bash
# 连 PostgreSQL（假定数据库容器名为 db，且在同一网络里）
docker run -d -p 8080:3000 --name wiki --restart unless-stopped \
  -e "DB_TYPE=postgres" -e "DB_HOST=db" -e "DB_PORT=5432" \
  -e "DB_USER=wikijs" -e "DB_PASS=wikijsrocks" -e "DB_NAME=wiki" \
  ghcr.io/requarks/wiki:2
```

**推荐的 Docker Compose 写法**（官方示例，PostgreSQL + Wiki.js，对外 80 端口）：

```yaml
services:

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: wiki
      POSTGRES_PASSWORD: wikijsrocks
      POSTGRES_USER: wikijs
    logging:
      driver: none
    restart: unless-stopped
    volumes:
      - db-data:/var/lib/postgresql/data

  wiki:
    image: ghcr.io/requarks/wiki:2
    depends_on:
      - db
    init: true
    environment:
      DB_TYPE: postgres
      DB_HOST: db
      DB_PORT: 5432
      DB_USER: wikijs
      DB_PASS: wikijsrocks
      DB_NAME: wiki
    restart: unless-stopped
    ports:
      - "80:3000"

volumes:
  db-data:
```

注意 `DB_HOST` 要和数据库服务名一致（上面是 `db`）；如果给该服务写了 `container_name`，就要填那个值。

**想用内置的 Let's Encrypt**（2.1 起提供）：

```bash
docker run -d -p 80:3000 -p 443:3443 \
  -e "LETSENCRYPT_DOMAIN=wiki.example.com" -e "LETSENCRYPT_EMAIL=admin@example.com" \
  --name wiki --restart unless-stopped \
  -e "DB_TYPE=postgres" -e "DB_HOST=db" -e "DB_PORT=5432" \
  -e "DB_USER=wikijs" -e "DB_PASS=wikijsrocks" -e "DB_NAME=wiki" \
  ghcr.io/requarks/wiki:2
```

HTTPS 对外端口是 **3443**；`SSL_ACTIVE` 设为 `1`/`true` 开启。证书签发与续期都要求 HTTP 端口**长期**可从公网访问，之后可以在管理后台的 SSL 区域打开自动跳转 HTTPS。

**改用配置文件挂载**：不想写一堆环境变量时，按官方 `config.sample.yml` 生成自己的配置，然后：

```bash
docker run -d -p 8080:3000 --name wiki --restart unless-stopped \
  -v YOUR-FILE.yml:/wiki/config.yml ghcr.io/requarks/wiki:2
```

也可以用 `CONFIG_FILE` 指定配置文件路径，适合挂载整个配置目录。

**原生安装**：官方支持 Linux / macOS / Windows，Node.js 运行时要求为 **Node.js 24（24.0+）或 Node.js 22（22.0+）**（自 v2.5.302 起）。用 Docker 则不需要在宿主机装 Node.js。具体安装命令以官方安装文档为准。

## 常用操作

**1. 首次初始化**

访问 `http://<你的地址>:8080`（容器内监听 3000，按上面的映射对外是 8080 或 80），会出现设置向导：填管理员邮箱与密码、站点地址，然后自动建表建账号。之后管理后台里配 SSL、邮件、用户组、权限、检索、存储、API 等。

**2. 用 GraphQL 接口程序化读写内容**

接口地址是站点根路径下的 `/graphql`，浏览器直接打开会进入 GraphQL Playground，可以试查询、看字段文档。

认证用管理后台 **API Access** 里生成 token，放在 `Authorization` 头里当 Bearer：

```
Authorization: Bearer eyJhbGc...aXczt18H6437W
```

常用查询（按官方示例口径）：

```graphql
# 列出全部页面，按标题排序
{ pages { list (orderBy: TITLE) { id path title } } }

# 看某个页面
{ pages { single (id: 15) { path title createdAt updatedAt } } }

# 看用户组
{ groups { list { id name } } }

# 按名字或邮箱搜人
{ users { search (query: "john") { id name email } } }
```

写操作用 mutation，返回值里带 `responseResult`（`succeeded` / `errorCode` / `slug` / `message`），脚本里要判这个而不是只看有没有报错：

```graphql
mutation {
  users { create (
    email: "john.doe@example.com", name: "John Doe",
    passwordRaw: "Password123", providerKey: "local",
    groups: [1], mustChangePassword: true, sendWelcomeEmail: false
  ) { responseResult { succeeded slug message } user { id } } }
}
```

常见错误码：`6002` 同路径页面已存在、`6003` 页面不存在、`6005` 页面路径含非法字符、`1004` 邮箱已被占用、`3002` 邮件配置不完整。token 的权限是**按范围授权**的，某个资源查询失败先看 token 有没有勾上对应权限。

**3. 打开全文检索**

在管理后台启用检索模块即可。用 PostgreSQL 的检索模块时，宿主机需要 `pg_trgm` 扩展（多数发行版在 `postgresql-contrib` 包里；官方 PostgreSQL 镜像已自带）。

**4. 多副本 / 集群部署**

多实例（Kubernetes、Swarm 等）必须开启高可用：把 `HA_ACTIVE` 设为 `1`/`true`，否则一个实例上的改动不会同步到其他实例。官方明确要求：**该功能只能配 PostgreSQL**。

**5. 挂载文件遇到权限问题时的官方兜底**

镜像默认以 `wiki` 用户运行；挂载 SQLite 文件或私钥遇到权限报错，可以覆盖运行用户：

```bash
docker run -d -p 8080:3000 -u="root" --name wiki --restart unless-stopped \
  -e "DB_TYPE=postgres" -e "DB_HOST=db" -e "DB_PORT=5432" \
  -e "DB_USER=wikijs" -e "DB_PASS=wikijsrocks" -e "DB_NAME=wiki" \
  ghcr.io/requarks/wiki:2
```

官方同时说明这不是安全的跑法，优先做法是把宿主机上被挂载目录的属主/权限调对。

**6. 前置反向代理**

应用本身不需要 Nginx/Apache 这类 Web 服务器，但要做更细的 DNS / 网络配置时可以前置一层代理。注意它**不支持子目录映射**，只能给独立域名或子域。

**7. 升级**

切换目标版本的镜像 tag 后重新拉取并重建容器，改动前先备份数据库与上传的附件。具体升级步骤以官方升级文档为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 某天重启后界面大变、插件失效 | 用了 `latest` tag，被静默带到了新版本 | 官方建议固定主版本 tag（如 `:2`）；需要新特性时再显式改 tag 升级 |
| 容器起来了但连不上数据库 | `DB_HOST` 填错；用 compose 时要填**数据库服务名**，若该服务设了 `container_name` 则填那一个 | 核对 `DB_HOST` / `DB_PORT` 与数据库容器实际暴露的端口 |
| 想部署在 `example.com/wiki` 这样的子目录，怎么调都不对 | 官方明确不支持映射到子文件夹 | 给它一个独立子域，例如 `wiki.example.com` |
| 开了 Let's Encrypt 但证书签不下来，或到期没续上 | 签发与续期都要求 HTTP 端口能从公网访问 | 保持 80 端口长期开放（内网更要检查端口映射与安全组）；HTTPS 对外端口是 3443，别按 3000 去连 |
| 多副本部署后，在 A 实例改的内容 B 实例看不到 | 没开高可用 | 设 `HA_ACTIVE=1`；且必须用 PostgreSQL，其他引擎不支持 |
| 挂载 SQLite 文件或私钥后启动即报权限错误 | 镜像默认以非 root 的 `wiki` 用户运行 | 优先修正宿主机被挂载目录的属主与权限；实在要用 `-u root` 兜底，需知道这会放宽容器权限 |
| 全文检索搜不到内容 | 用 PostgreSQL 检索模块时缺 `pg_trgm` 扩展 | 安装 `postgresql-contrib`（官方 PostgreSQL 镜像已自带），再回后台重新启用检索模块 |
| 接口调用返回「未授权」或权限不足 | GraphQL token 是**按范围**授权的，新资源没勾权限 | 到管理后台 API Access 里编辑该 token 的权限范围后重试 |
| 小内存机器上页面渲染或索引时被 OOM | 渲染/索引等事件会造成短时内存冲高 | 官方口径：Linux 至少 1GB 内存、建议 2 核以上，按实际内容量留余量 |
| 老树莓派上的 ARMv7 镜像拉不到新版本 | ARMv7 自 v2.5.304 起不再支持 | 停在最后支持 ARMv7 的版本，或换 ARM64 设备（ARM64 自 2.4 起与 AMD64 同 tag） |
| 用 SQLite 跑生产，备份和并发都难受 | 官方不推荐 SQLite 用于生产 | 迁移到 PostgreSQL；官方也提示其余引擎在下一个大版本将不再支持，早点迁 |
| 升级后数据库结构对不上 | 直接换镜像但没备份，迁移出问题无法回退 | 升级前备份数据库与附件卷，再按官方升级文档逐步操作 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取镜像；连接数据库；可选向 Let's Encrypt 申请与续期证书；周期性检查更新、语言包与主题；接入外部检索/存储/认证服务 |
| 读取文件 | 是 | 读取挂载进来的配置文件（config.yml）、SQLite 数据库文件、上传的附件与私钥文件 |
| 写入文件 | 是 | 向本地存储写入上传的附件（用 SQLite 时还包括数据库文件）；写入容器内的工作目录与日志 |
| 凭证 | 是 | 数据库账号密码、管理员账号、GraphQL API token、邮件与第三方认证/存储的密钥。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | 以常驻服务运行，且包含后台工作进程（渲染、索引等）；建议 `restart: unless-stopped`，多副本需开高可用 |

## 触发场景

- 「团队文档没地方放，想搭个内部 wiki」
- 「要能按部门/角色控制页面权限」
- 「把现有的 Markdown 文档搬到网页上」
- 「wiki 怎么用 Docker 装、数据库怎么配」
- 「想让 wiki 内容能被脚本读写」
- 「知识库要自己托管，数据不出内网」

## 能力边界

**覆盖**：

- 页面组织：树状路径、多级目录、标签、页面历史与版本对比、评论。
- 写作体验：Markdown 与可视化编辑器、代码高亮、数学公式、图表、脚注、任务列表等扩展语法。
- 权限：用户与用户组、按组/按页面的读写控制、访客只读、账号与两步验证。
- 检索：内置检索与外部搜索引擎模块（如 Elasticsearch/OpenSearch、Algolia、Solr 一类）。
- 多语言界面与内容本地化。
- 内容同步：可把内容同步到 Git 仓库（含 SSH 方式）做版本化与备份。
- 存储目标：本地磁盘与多家对象存储/云盘（S3 兼容、Azure、云厂商对象存储等）。
- 认证方式：本地账号以及多种企业身份源（LDAP/AD、SAML、OIDC、OAuth2、CAS 等）。
- 接口：暴露 GraphQL API，可用 API token 按权限范围读写资源。
- 部署形态：Docker / Kubernetes / 原生安装；多副本需 PostgreSQL + 高可用开关；自带 Let's Encrypt 集成。

**不覆盖**：

- 不带数据库引擎，数据库要自备；也不做数据库本身的备份、容灾与调优。
- 不是协作数据库：没有表格视图、看板、关系字段、公式字段这类能力。
- 不做业务表单、审批流与工单状态机。
- 不支持部署在已有站点的子目录下。
- 不做代码 API 文档的自动生成。
- 不提供托管服务与代运维；官方文档说明了哪些数据库引擎在未来版本会被移出支持范围。
- 上游项目按其仓库声明以 AGPL-3.0 发布，二次分发或改造前请自行确认许可义务。

## 依赖条件

- 一个数据库实例（空库 + 独立账号）：官方首推 PostgreSQL 9.5 及以上；其余引擎可用但未来不再支持。
- Docker（推荐路径，镜像已内置 Node.js 运行时）或原生安装所需运行环境。
- 原生安装：Node.js 24（24.0+）或 Node.js 22（22.0+），自 v2.5.302 起支持。
- 硬件：Linux 至少 1GB 内存，官方建议 2 核以上以发挥后台工作进程；文本为主的站点磁盘占用很小，官方建议至少预留 1GB 存储并按附件量放大。
- 独立域名或子域（不支持子目录）。
- 要签 HTTPS 证书时需要域名解析、可被公网访问的 HTTP 入口与管理员邮箱。
- 需要程序化读写时要一个带足够权限范围的 API token。
- 需要对接外部认证、对象存储或搜索引擎时，相应服务的账号与密钥。

## 已知限制

- 必须有数据库，且官方已宣布除 PostgreSQL 外的引擎在下一个大版本将不再支持——新部署别选错。
- 不支持子目录部署，站点路径规划要在域名层面解决。
- 内置 Let's Encrypt 的续期依赖 HTTP 端口长期开放，网络一变证书就可能续不上。
- 多副本必须依赖 PostgreSQL 并显式开启高可用，否则实例间不同步。
- 内存占用平时不高（官方说进程常在 70MB 量级），但渲染、索引等操作会短时冲高，低配机器要留余量。
- 部分能力（高可用、内置 HTTPS、API Access 等）有最低版本要求，老版本升级前先查版本阈值。
- ARMv7 已在较新版本中被放弃；ARM64 自 2.4 起与 AMD64 共用 tag。
- 界面、环境变量与文档站内容会随版本演进；执行前以官方文档站当前内容为准，本文不做版本号断言。

## 自检清单

- [ ] 数据库已就绪（空库 + 独立账号），并确认用的是官方优先推荐的 PostgreSQL。
- [ ] 镜像用的是主版本 tag 而不是 `latest`，且已记录当前版本号。
- [ ] `DB_TYPE` / `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_NAME` 全部填好，`DB_HOST` 与 compose 服务名一致。
- [ ] 数据库数据卷与附件存储已持久化，并有备份方案。
- [ ] 已完成首次设置向导并创建管理员账号，站点地址填的是最终对外地址。
- [ ] 已确认没有把它部署到子目录，域名规划正确。
- [ ] 若用内置 HTTPS：`SSL_ACTIVE` 已开，80 与 3443 端口映射正确，HTTP 端口长期可从公网访问。
- [ ] 若做多副本：`HA_ACTIVE` 已开且数据库是 PostgreSQL。
- [ ] 用户组与页面权限已按最小必要原则配置，访客权限确认过。
- [ ] 全文检索已启用并实测能搜到内容（PostgreSQL 场景确认 `pg_trgm` 可用）。
- [ ] GraphQL 调用用的 token 权限范围最小化，且不写进代码仓库或前端。
- [ ] 升级前已备份数据库与附件，并确认可以从旧镜像 tag 回退。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/requarks/wiki | 上游仓库（安装与完整文档以它为准） |
| https://docs.requarks.io/install/docker | 官方 Docker 安装与环境变量说明（本文安装内容来源） |
| https://docs.requarks.io/install/requirements | 官方系统与数据库版本要求 |
| https://docs.requarks.io/dev/api | 官方 GraphQL API 说明与错误码表 |

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
