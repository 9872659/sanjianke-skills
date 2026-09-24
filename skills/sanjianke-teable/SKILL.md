---
name: sanjianke-teable
slug: sanjianke-teable
displayName: 三剪客 · 多维表格数据库
description: "Teable 是把电子表格的操作体验架在真实 PostgreSQL 之上的多维表格平台：表格、看板、表单、日历多种视图，公式、关联、权限、自动化、API 一应俱全。这份 Skill 讲清自托管部署（Docker Compose / 源码开发两种路径）、环境变量与密钥、数据结构与 REST API 调用，以及密钥缺失、卷丢数据、升级回滚等实战坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Teable 的安装（Docker Compose 与源码开发）、必需环境变量、从表格到 API 的用法、记录增删改查与 Access Token 调用，以及默认密钥不可用于生产、卷被删即丢数据、升级回滚、外键批量更新超时等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 多维表格
  - 数据库
  - 自托管
---

# 三剪客 · 多维表格数据库

团队里最尴尬的一类工具是"表格不够用、数据库又太重"：业务同事要一个能随手改字段、随手加视图的表格，工程同事又希望这些数据最终能落在真正的数据库里、能写 SQL、能被程序读写。用 Excel 共享会冲突、用 SaaS 多维表格又担心数据出不去。

Teable 的定位就在这个缝里：**操作界面是电子表格，存储底座是 PostgreSQL**。同一份数据既能在网格视图里点着改，也能通过 REST API 让程序读写，需要时还能直接从数据库里跑只读 SQL。自托管部署时，表格、协作、API、自动化都在你自己的机器上。

**上游项目**：`Teable`　**仓库**：https://github.com/teableio/teable

## 什么时候用 / 不用

**用它**：

- "我们想要一个能自己改字段、改视图的表格式业务系统，数据还得留在自己服务器上。"——自托管 + PostgreSQL 底座正是为这个场景准备的。
- "业务在表里维护数据，程序要能读写同一份数据。"——平台自带 REST API 与 Access Token，不需要额外同步链路。
- "同一批基础数据，运营想看板、销售想表格、外部只想填表单。"——一个表可以挂多种视图类型，数据只有一份。
- "我们已经有 PostgreSQL 运维能力，不想再引入一套黑盒 SaaS。"——数据落在标准 PostgreSQL 里，备份、审计、只读查询都能沿用既有手段。
- "要在记录变更、定时、Webhook 上挂自动化流程。"——平台内置自动化触发器，可挂在数据所在的位置。

**不要用它**：

- **只是要一个静态文件共享盘 / 网盘**——它的核心是结构化数据与关系，存大文件不是它的主职。
- **团队规模远小于 50 人但只想要开箱 SaaS**——这种量级直接用它家的托管云更省事，自托管要自己承担升级、备份、密钥管理。
- **需要的是强一致的事务型业务后端（订单、支付账本）**——多维表格是给人协作的数据层，不是替代 OLTP 业务库的设计目标；这类需求应该直接写业务服务 + 数据库。
- **只是想临时处理一个 CSV 文件**——用 pandas / csvkit / DuckDB 一条命令的事，起一整套平台是杀鸡用牛刀。
- **没有能力维护 PostgreSQL 与容器，也不打算学**——自托管部署的运维责任全在你这边，密钥、卷、升级都要人管。
- **指望 AI 与 App Builder 功能在精简版自托管里开箱可用**——官方部署对比表里这两项只在托管云与全功能自托管里提供，精简版不含。

## 安装

**路径一：Docker Compose 自托管（官方推荐给 50 人以下小团队与评估场景）**

服务器建议（官方口径）：Linux（如 Ubuntu 20.04 LTS）、内存 ≥ 4GB、CPU ≥ 2 核、可用磁盘 ≥ 40GB。

```bash
# 装 Docker（官方文档给的脚本）
curl -fsSL https://get.docker.com | bash -s docker
docker --version
docker-compose --version

# 建部署目录
mkdir teable && cd teable
```

从仓库的 `dockers/examples/standalone/` 取 `docker-compose.yaml` 与 `.env` 两个文件放进该目录，**先按注释改掉 `.env` 里的值再启动**：

```bash
docker compose up -d
```

起来后访问 `http://127.0.0.1:3000`。这份官方示例的 compose 会同时拉起三个服务：Teable 应用（`ghcr.io/teableio/teable:latest`，端口 3000）、PostgreSQL（`postgres:15.4`）、Redis（`redis:7.2.4`，带密码启动）。

**路径二：源码开发环境**

```bash
# 启用包管理器
corepack enable

# 安装依赖（仓库明确要求使用 pnpm）
pnpm install

# 初始化 Postgres
make switch-db-mode

# 可选：自定义环境变量
cd apps/nextjs-app
cp .env.development .env.development.local

# 起开发服务（只起后端即可，它会自动把前端 next 服务一起拉起来，改文件自动重载）
cd apps/nestjs-backend
pnpm dev
```

仓库的 `package.json` 里写着 `engines`: Node.js ≥ 22.0.0、pnpm ≥ 9.13.0，并且对 npm 的提示是 `please-use-pnpm`——用 npm 装会直接不配合。许可证是 AGPL-3.0（`packages/` 下的包为 MIT）。

```bash
# 验证运行时版本
node -v     # 需 >= 22
pnpm -v     # 需 >= 9.13
```

## 常用操作

**1. 部署后升级：跟着 `latest` 频道走**

```bash
cd teable            # 你的部署目录
docker compose pull
docker compose up -d
```

官方说明：容器会用新镜像重建，数据在 Docker 卷（或你外接的数据库）里，不受影响。版本升级文档还明确说数据库迁移在启动时**自动执行**，不需要手动跑迁移脚本。

**2. 升级出问题要回滚**

```bash
# 把 docker-compose.yaml 里的镜像 tag 改回上一个具体的 release tag
docker compose up -d
```

镜像标签有三种：`latest`（稳定频道）、`beta`（滚动最新）、`release.<时间戳>.<构建号>`（不可变的具体版本）。官方建议 K8s 部署不要用浮动 tag，而是一次次故意升具体版本——回滚时才有"上一个版本号"可写。

**3. 看启动迁移是否正常**

```bash
docker compose logs teable | grep -i migration
```

官方在版本升级文档里给的就是这条排错命令。

**4. 用 Access Token 调 REST API**

先在界面里生成个人访问令牌（文档在 API 文档的 Access Token 一节），然后带上它请求你自己的实例：

```bash
# 列出记录（tableId 换成你自己的表 ID）
curl -s \
  -H "Authorization: Bearer <your-access-token>" \
  "http://127.0.0.1:3000/api/table/<tableId>/record"

# 带查询条件分页取记录（参数以官方 API 文档为准）
curl -s \
  -H "Authorization: Bearer <your-access-token>" \
  "http://127.0.0.1:3000/api/table/<tableId>/record?take=100&skip=0"
```

**5. 写入与更新记录**

```bash
# 创建记录（字段名与你自己表的字段名一致）
curl -s -X POST \
  -H "Authorization: Bearer <your-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"records":[{"fields":{"名称":"新记录"}}],"fieldKeyType":"name"}' \
  "http://127.0.0.1:3000/api/table/<tableId>/record"

# 更新记录
curl -s -X PATCH \
  -H "Authorization: Bearer <your-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"records":[{"id":"<recordId>","fields":{"名称":"改过的名字"}}],"fieldKeyType":"name"}' \
  "http://127.0.0.1:3000/api/table/<tableId>/record"
```

具体的请求体字段、查询参数与错误码请对照官方 API 文档的 Record 章节与 Error Codes 页面；各版本的参数细节以你实例的接口为准。

**6. 生成密钥与确认版本**

```bash
# 生成用于签名会话/令牌的强随机密钥
openssl rand -base64 32

# 看启动日志前几十行，确认版本与密钥告警
docker compose logs teable | head -n 30
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 部署跑起来没报错，但生产上其实极不安全 | 官方明确警告：一批密钥类环境变量**缺失时不会阻止启动**，服务会回退到旧版本内置的默认值；那些值已公开，任何人都能伪造令牌或解密受保护的数据 | 官方口径是"本地试用无所谓，其他场景都不安全"。新部署一律生成新值（如 `openssl rand -base64 32`）；老部署升级时把启动日志里打印的那段变量块原样加进去，重启后再规划轮换 |
| `PUBLIC_ORIGIN` 没设对，分享链接、附件地址全都不对 | 这个变量用于生成完整 URL，官方标注为必填 | 设成你的真实访问地址；反向代理后面尤其容易漏，见环境变量文档的 Core Configuration 一节 |
| 手滑删了卷，数据全没了 | compose 官方示例把数据放在命名卷里，示例注释自己也提醒"用宿主目录挂载更不容易误删" | 数据卷一定做好外部备份；想更保险就把 compose 里 `teable-data` / `teable-db` 换成宿主机目录绑定挂载（示例里已给出注释掉的写法） |
| 宿主机重启后容器没起来，或数据目录权限不对 | 三个服务都配了 `restart: always` 与健康检查，但 Postgres / Redis 的健康检查要配合正确的密码变量才通得过 | 确认 `.env` 里的 `POSTGRES_*`、`REDIS_PASSWORD` 与 `PRISMA_DATABASE_URL`、`BACKEND_CACHE_REDIS_URI` 保持一致，再看 `docker compose logs` 里健康检查的失败项 |
| 用 `npm install` 装依赖直接失败 | 根 `package.json` 的 `engines.npm` 写的是 `please-use-pnpm` | 用 `pnpm install`；本地 Node 需 ≥ 22，pnpm 需 ≥ 9.13，可用 `corepack enable` 直接启用 |
| 大字段的批量更新（外键多）中途超时 | Prisma 事务默认超时较短，官方环境变量文档标注 `PRISMA_TRANSACTION_TIMEOUT` 默认 5000ms | 按文档把这个值调大（例如 60000），同时可调 `PRISMA_TRANSACTION_MAX_WAIT`；导出大库这类超长事务还有 `BIG_TRANSACTION_TIMEOUT` |
| 记录历史 / 冷归档功能把库撑大或行为不符合预期 | 这些是可配置开关，官方提供了 `RECORD_HISTORY_DISABLED`、`BACKEND_STORAGE_COLD_ARCHIVE_DISABLED` 等 | 按需要显式关掉；注意归档只是停止后续归档，**已经归档的数据仍可读** |
| 想让外部账号登录，或接 OAuth / OIDC，结果配置不生效 | 这些是可选认证配置（如 `SOCIAL_AUTH_PROVIDERS`、`BACKEND_OIDC_*`），且 `PASSWORD_LOGIN_DISABLED` 关掉密码登录后只能靠它们 | 先把 OAuth / OIDC 配通并验证能登上，再关密码登录，否则会把自己锁在门外 |
| 附件上传超过大小上限被拒 | 上传大小是可配的上限项（如 `MAX_ATTACHMENT_UPLOAD_SIZE`） | 按环境变量文档调整上限，同时注意反向代理（nginx 等）也有自己的请求体上限，两边都要放 |
| 反向代理后面登录异常 / 审计日志里 IP 全一样 | 代理场景需要正确的信任配置 | 用 `BACKEND_TRUST_PROXY` 告诉服务信任哪些代理（接受 `true`/`false`、跳数或 IP/CIDR 列表）；官方还说明 `BACKEND_SESSION_ORIGIN_CHECK_ENABLED` 只有在代理或 CDN 会保留 Origin / Sec-Fetch-* 头时才该打开 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取 Docker 镜像与 npm 依赖；运行期对外提供 HTTP 服务。若使用邮件邀请 / 自动化邮件、外部存储（S3 / MinIO / 阿里云 OSS）、OIDC 登录，都要额外访问对应服务 |
| 读取文件 | 是 | 读取部署目录下的 `docker-compose.yaml`、`.env`（内含数据库口令等敏感值），源码路径下读取 `.env.development`；运行期读取本地存储目录里的附件 |
| 写入文件 | 是 | 写入 Docker 卷（数据库数据、Redis 数据、`/app/.assets` 附件目录）；源码开发时会写构建产物与日志 |
| 凭证 | 是 | 数据库连接串（`PRISMA_DATABASE_URL`）、Redis 口令、若干签名与加密密钥（`SECRET_KEY`、`BACKEND_*_ENCRYPTION_KEY/IV` 等）、存储服务 Access Key，以及调用 API 用的个人 Access Token。这些都属于高敏感值 |
| 子进程 / 后台常驻 | 是 | Compose 部署会常驻运行应用、PostgreSQL、Redis 三个容器；源码开发时 `pnpm dev` 常驻拉起后端与前端服务 |
| 数据读写（业务） | 是 | 平台本身就是数据平台，API 与界面都会真实增删改你数据库里的记录与附件 |

## 触发场景

- "帮我用 Docker 部署一套自托管的多维表格，数据要落 PostgreSQL。"
- "这个表我要程序读写，怎么拿 Access Token、怎么调 API？"
- "升级完数据还在吗？出问题怎么回滚？"
- "启动日志里提示密钥缺失，这是什么意思、要不要管？"
- "我们想从 SaaS 表格迁到自托管，怎么评估工作量？"
- "容器重启后数据丢了，帮我看看卷挂在哪里。"

## 能力边界

**覆盖**：

- 数据组织：表格（Base / Table / Field / Record / View）模型，落在真实 PostgreSQL 上
- 视图与呈现：网格、表单、看板、画廊、日历等多种视图；筛选、分组、排序、聚合、公式、字段类型转换
- 协作能力：评论、记录历史、撤销重做、实时协作、批量编辑、导入导出、附件预览、搜索、校验、图表、插件、SQL 查询
- 自动化：由记录变更、定时、Webhook 触发的流程
- 程序接口：完整的 REST API（记录、表、字段、视图、空间、权限、导入导出、附件等一整套端点）与 Access Token 鉴权；另有 OAuth 应用方式
- 部署形态：官方托管云、精简版自托管、全功能自托管三种；Docker Compose 适合 0–50 人，Kubernetes 走单独的部署仓库
- 运维能力：环境变量集中配置、自动数据库迁移、镜像三频道（`latest` / `beta` / 具体 release）升级与回滚路径、Telemetry 开关、管理员面板（用户、空间、实例设置、审计日志等）

**不覆盖**：

- 不做聊天协议的对接（它不是 IM 工具）
- 精简版自托管不含 AI 能力（对话、Agent）与 App Builder，这两项只在托管云与全功能自托管提供
- 不做通用对象存储与网盘；附件依赖本地存储或你自备的 S3 / MinIO / 阿里云 OSS
- 不做通用 ETL / 数据仓库：它的定位是协作数据层，跨源大规模同步要自己接外部工具
- 不替代 OLTP 业务后端；高并发事务型业务应写在独立服务里
- 不提供官方的托管运维服务；自托管部分的升级、备份、密钥轮换由使用者负责

## 依赖条件

- Docker Compose 路径：Docker 与 Docker Compose；官方示例会拉取 Teable 应用、`postgres:15.4`、`redis:7.2.4` 三个镜像
- 源码开发路径：Node.js ≥ 22.0.0、pnpm ≥ 9.13.0（仓库 `engines` 字段），用 `corepack enable` 启用包管理器；需要一个 PostgreSQL 实例，初始化用 `make switch-db-mode`
- 必需环境变量：`PUBLIC_ORIGIN`、`SECRET_KEY`、`PRISMA_DATABASE_URL`、`BACKEND_CACHE_REDIS_URI`，以及若干加密密钥与 IV（具体清单见环境变量文档）
- 可选外部服务：邮件服务器、S3 / MinIO / 阿里云 OSS、GitHub / Google / OIDC 登录、OpenTelemetry 收集端
- 服务器建议：Linux、≥4GB 内存、≥2 核、≥40GB 磁盘

## 已知限制

1. Docker Compose 方案官方定位是单机、0–50 人；要横向扩展得走 Kubernetes 部署仓库，那是另一套东西。
2. 密钥类变量缺失**不阻塞启动**，只回退到公开的默认值，等于默默留了个洞；必须自己检查启动日志。
3. 数据库迁移自动执行，升级路径省事，但也意味着跨大版本升级前必须先备份。
4. 精简版与全功能版的边界要认清：AI 能力与 App Builder 不在精简版里，混用文档会白折腾。
5. 浮动 tag（`latest`）省事但不可复现，K8s 场景官方明确要求钉住具体版本。
6. 本 Skill 里的环境变量名与命令来自官方文档与仓库示例；接口参数细节会随版本变化，请以你实例对应的官方文档与实测为准。

## 自检清单

执行前：

- [ ] 服务器满足最低配置，Docker 与 Docker Compose 版本可用
- [ ] `.env` 里的 `POSTGRES_*` 口令与 `PRISMA_DATABASE_URL`、`REDIS_PASSWORD` 与 `BACKEND_CACHE_REDIS_URI` 互相对得上
- [ ] `PUBLIC_ORIGIN` 设成真实访问地址（反代场景尤其要核对）
- [ ] `SECRET_KEY` 与全部加密密钥/IV 都是自己生成的新值，没有沿用默认
- [ ] 数据卷已规划备份策略，或已改为宿主机目录绑定挂载
- [ ] 源码开发路径确认用的是 pnpm，且 Node / pnpm 满足 `engines` 要求

执行后：

- [ ] `docker compose ps` 三个服务都是健康状态，`http://127.0.0.1:3000` 能正常打开
- [ ] `docker compose logs teable | grep -i migration` 没有异常
- [ ] 启动日志里**没有**关于缺失密钥的警告
- [ ] 建一张测试表，用 Access Token 跑通一次读和一次写
- [ ] 验证一次重启（`docker compose restart`）后数据仍在
- [ ] 记录下当前镜像的具体版本号，写进你自己的变更记录，便于回滚
- [ ] 确认敏感变量没有出现在截图、工单、聊天记录里

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/teableio/teable | 上游仓库（安装与完整文档以它为准） |
| https://help.teable.ai/en/deploy/docker | 官方 Docker 部署文档（服务器要求、compose 内容、启动步骤） |
| https://help.teable.ai/en/deploy/env | 官方环境变量全集与密钥说明 |
| https://help.teable.ai/en/api-doc/overview | 官方 API 文档入口（Access Token、记录增删改查、错误码） |
| https://help.teable.ai/en/deploy/upgrade | 官方版本升级与回滚说明 |

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
