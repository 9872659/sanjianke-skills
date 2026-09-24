---
name: sanjianke-cal-com
slug: sanjianke-cal-com
displayName: 三剪客 · 开源预约排期系统
description: "自建一套属于自己的预约排期系统：Cal.diy 的 Docker/源码部署、环境变量配置、事件类型与预约链路排查。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Cal.diy 自助部署与排期配置指引：社区版与商业版的区别、必须生成的两个密钥、数据库迁移与 Docker 编排、日历集成回调地址与常见启动报错的定位。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 开源预约排期系统

Cal.diy 要解决的是「别再用聊天记录约时间」。它把你可预约的时段变成一个链接，对方自己挑空档，约完自动写进你的日历、带上视频会议链接、按需发提醒。整个系统跑在你自己的服务器和数据库上。

它面向的是愿意自己管服务器、并且能接受「社区版 = 去掉商业化功能」这套取舍的人。项目本身明确说明它是社区维护的开源自托管版本，**严格建议用于个人、非生产场景**，没有托管版，也没有商业支持。

**上游项目**：`Cal.com`　**仓库**：https://github.com/calcom/cal.diy

## 什么时候用 / 不用

**用它**：

- 用户要**自建预约系统**：不想按人按月付订阅费，也不想把客户名单交给第三方 SaaS。
- 需要**完全开源的排期底座**：项目是 MIT 授权、没有「企业版功能」这类商业分层，不需要许可证密钥。
- 要**二次开发或私有化改造**：团队、组织、工作流、SSO 这类企业功能已被移除，代码面更小，改起来边界清楚。
- 要**把预约接进已有系统**：支持通过环境变量对接 Google 日历、Microsoft 365、Zoom、Daily、CRM 等服务。
- 内部有**服务器运维能力**（会 Docker Compose、会管 PostgreSQL、会配反向代理），部署和升级可以自己扛。

**不要用它**：

- 要**生产级、多人协作的排期基础设施**。上游明确建议这类需求走商业托管版，而不是这个社区版。
- 需要 **SSO / SAML、团队与组织管理、Insights、Workflows** 这些能力——在这个版本里是被**主动移除**的，装完也不会有。
- 期望**开箱即用的托管服务**：没有官方托管版，也没有官方技术支持通道，运维责任全在使用者。
- 团队里**没有人会管 PostgreSQL、反向代理和证书**。这套系统自托管需要数据库管理、服务器运维和数据安全方面的高级知识。
- 只想要一个**单次约会议的临时链接**。为一次约会搭一套数据库 + Web 应用不划算，用现成的轻量工具更快。

## 安装

### 前置条件

上游给出的要求：Node.js **>= 18.x**、PostgreSQL **>= 13.x**、Yarn（推荐）。走快速启动还需要 Docker 与 Docker Compose。

### 方式一：Docker Compose（部署首选）

```bash
# 1) 取代码（仓库带子模块，需要 --recursive）
git clone --recursive https://github.com/calcom/cal.diy.git
cd cal.diy

# 2) 准备配置
cp .env.example .env
```

`.env` 里**必须**先生成两个密钥，不要沿用默认占位值：

```bash
# Cookie 加密密钥
openssl rand -base64 32          # 填到 NEXTAUTH_SECRET

# AES256 用的 32 字节加密密钥
openssl rand -base64 24          # 填到 CALENDSO_ENCRYPTION_KEY
```

另外，如果启动后报 `No key set vapidDetails.publicKey`，说明缺少 Web Push 密钥：

```bash
npx web-push generate-vapid-keys   # 结果分别填 NEXT_PUBLIC_VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY
```

然后拉起服务：

```bash
docker compose pull
docker compose up -d                 # 完整栈：本地 Postgres + Web 应用 + Prisma Studio
docker compose up -d calcom          # 只用外置数据库时，只起 Web 应用
```

浏览器打开 `http://localhost:3000`，首次进入会走安装向导，创建第一个用户。

### 方式二：源码开发

```bash
git clone https://github.com/calcom/cal.diy.git
cd cal.diy
yarn

# 复制 .env.example 为 .env，并写入上面生成的两个密钥

yarn workspace @calcom/prisma db-migrate   # 开发环境
yarn dev
```

想省掉手工配库，用内置的 Docker 快速启动：`yarn dx`（要求已装 Docker 与 Docker Compose，会起一个本地 Postgres 并创建若干测试账号，账号密码在控制台里打印出来）。

生产构建则是：

```bash
yarn build
yarn start
```

### 方式三：自己构建镜像

构建期就需要一个可用的数据库：

```bash
docker compose up -d database
DOCKER_BUILDKIT=0 docker compose build calcom
docker compose up -d
```

## 常用操作

**1. 升级已有实例**

```bash
git pull
yarn
yarn predev                                # 检查 .env 变量是否有增减
yarn workspace @calcom/prisma db-deploy    # 生产环境跑迁移
yarn build && yarn start
```

Docker 部署的升级是三步：`docker compose down` → `docker compose pull` → `docker compose up -d`。

**2. 造第一个用户（已经过了向导或需要补用户时）**

```bash
yarn db-studio
```

在 Prisma Studio 里选 `User` 模型新增记录，填 `email`、`username`、`password`（密码要用 BCrypt 加密后的值），`metadata` 填空的 `{}`。也可以直接播种测试数据：

```bash
cd packages/prisma
yarn db-seed
```

**3. 配置 Google 日历集成**

在云控制台启用日历 API，创建「Web 应用」类型的 OAuth 客户端，并把下面两个回调地址都加进去（把域名换成你自己的）：

```
<你的URL>/api/integrations/googlecalendar/callback
<你的URL>/api/auth/callback/google
```

下载凭据 JSON，整段内容填进 `.env` 的 `GOOGLE_API_CREDENTIALS`。之后刷新应用商店里的应用项：

```bash
cd packages/prisma
yarn seed-app-store
```

**4. 本地开发看邮件**

```bash
docker pull mailhog/mailhog
docker run -d -p 8025:8025 -p 1025:1025 mailhog/mailhog
```

MailHog 的界面在 `http://localhost:8025`。

**5. 跑端到端测试**

```bash
npx playwright install     # 首次需要下载浏览器
yarn test-e2e
yarn playwright show-report test-results/reports/playwright-html-report
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 容器日志报 `CLIENT_FETCH_ERROR`、`getaddrinfo ENOTFOUND ...` | 认证回调把 `WEBAPP_URL` 当基址，而容器内部的 DNS 跟宿主机不是一套，容器解析不了你的域名 | 显式让后端回环到自己，设置 `NEXTAUTH_URL=http://localhost:3000/api/auth`（按实际端口调整） |
| 构建镜像时报找不到数据库 | 这个应用在构建期就要读数据库配置，不是只在运行期才需要 | 构建前先确认 `DATABASE_URL` 指向一个可用库；本地没有就 `docker compose up -d database` 起一个临时的 |
| 构建时网络不通、依赖拉不下来 | 构建过程需要网络桥接，而默认的 BuildKit 方式在这套配置下不支持 | 按上游写法加上环境变量降级：`DOCKER_BUILDKIT=0 docker compose build calcom` |
| 在 Prisma Studio 里建用户报 `Invalid 'prisma.user.create()'` | 空值字段的兼容性问题，`metadata` 为空时会触发 | 把 `metadata` 填成空的 JSON 对象 `{}`；`id` 是自增的，留空即可 |
| 启动报 `No key set vapidDetails.publicKey` | 推送通知的 VAPID 密钥没配 | `npx web-push generate-vapid-keys` 生成后写入 `NEXT_PUBLIC_VAPID_PUBLIC_KEY` 与 `VAPID_PRIVATE_KEY` |
| 改完 `.env` 的 `NEXT_PUBLIC_WEBAPP_URL` 后站点行为不对 | 这个值同时有构建期和运行期两份，两者不一致时容器启动要花额外时间改写静态文件，容易出现地址错乱 | 让构建期与运行期的 `NEXT_PUBLIC_WEBAPP_URL` 保持一致；改完地址后重启容器并等它完成改写 |
| Windows 上跑数据库迁移脚本报 `Environment variable not found: DATABASE_DIRECT_URL` | 任务编排工具没能把根目录 `.env` 注入进来 | 进到 prisma 包目录手动设变量再执行，例如用 PowerShell 设好 `DATABASE_URL` 与 `DATABASE_DIRECT_URL` 后跑 `npx prisma db push` |
| 走 Nginx 等负载均衡做 SSL 卸载，页面一直报错 | 证书校验失败导致请求被拒 | 上游给的应急做法是设 `NODE_TLS_REJECT_UNAUTHORIZED=0`，但这是降低安全等级的操作，仅在你完全清楚链路并信任该负载均衡时才用；更好的做法是把证书链配对 |
| 安装向导卡在「连接日历」这一步 | 这一步看起来像必填，实则可以不连 | 直接跳到 `<你的URL>/event-types` 即可继续；日历集成后面在设置的集成页里补 |
| Windows 上 clone 或构建出问题 | 仓库里有软链接，普通 clone 拿不到，Prisma 读 `.env` 软链接也会报 `unexpected character / in variable name` | clone 时带上符号链接支持（`git clone -c core.symlinks=true ...`）；把 `packages/prisma/.env` 这个软链接换成真实拷贝 |
| 构建时内存被打爆 | 默认的 Node 内存上限不够这套单体的构建 | 按上游建议调大堆内存，例如设置 `NODE_OPTIONS=--max-old-space-size=16384`（数值按机器内存定） |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取依赖与镜像；应用运行期要访问外部日历、视频会议与 CRM 服务商的 API；推送通知出网 |
| 读取文件 | 是 | 读取 `.env` 与 `packages/prisma/.env` 等配置、Prisma schema、构建产物；子模块与软链接也在仓库内 |
| 写入文件 | 是 | 写入构建产物（`.next` 等）、迁移记录、容器卷中的数据库数据；`yarn build` 会改写静态文件中的注入地址 |
| 凭证 | 是 | `DATABASE_URL`、`NEXTAUTH_SECRET`、`CALENDSO_ENCRYPTION_KEY` 三项必填；日历、会议、CRM 集成的 OAuth 客户端与密钥；Web Push 的 VAPID 密钥。这些都应放在 `.env` 中且不要提交到版本库 |
| 子进程 / 后台常驻 | 是 | Docker Compose 常驻多个容器（应用、数据库、Prisma Studio）；开发模式常驻 `yarn dev`；构建与测试会拉起 Node 与 Playwright 浏览器进程 |

## 触发场景

- 「想在自己服务器上搭一套预约系统，客户自己选时间的那种」
- 「Cal.diy 用 Docker 怎么部署？需要配哪些环境变量？」
- 「启动报 CLIENT_FETCH_ERROR，怎么解决？」
- 「怎么给这套系统接上 Google 日历 / Zoom？」
- 「数据库迁移该用 db-migrate 还是 db-deploy？」
- 「这套自托管的能做团队协作和 SSO 吗？」

## 能力边界

**覆盖**：

- 三条安装路径：Docker Compose 部署、源码开发、自行构建镜像。
- 必需环境变量的生成与含义，以及邮件、日历、会议、CRM 等集成的配置入口与回调地址规则。
- 数据库迁移与播种（`db-migrate` / `db-deploy` / `db-seed` / `db-studio`），首个用户的两种创建方式。
- 升级流程，以及常见启动与构建报错的定位思路。
- 本地开发辅助：`yarn dx` 快速启动、MailHog 收信、Playwright 端到端测试。
- 社区版与商业版的功能差异判断——明确哪些请求应该转到别的方案。

**不覆盖**：

- 具体版本号、镜像标签与发布时间；这些以实际拉取到的版本和上游说明为准。ARM 平台另有带架构后缀的镜像，用之前先核对。
- 各类第三方服务商账号的开通流程（Google Cloud、Azure、Zoom 等控制台里的操作细节由服务商文档决定）。
- 企业级功能的替代实现（SSO、组织管理、工作流等在本版本中被移除，不提供绕过方案）。
- 生产环境的容量规划、数据库高可用与备份策略。
- 上游的托管服务与商业授权，本包不涉及也不代售。

## 依赖条件

- Node.js >= 18.x、PostgreSQL >= 13.x、Yarn。
- Docker 与 Docker Compose（走容器部署或 `yarn dx` 时需要）。
- 一个可被外网访问的域名与 HTTPS（要接第三方日历、会议服务的 OAuth 回调就必须有）。
- 三个必备密钥：`NEXTAUTH_SECRET`、`CALENDSO_ENCRYPTION_KEY`，以及数据库连接串 `DATABASE_URL`。
- 按需的第三方凭据：Google / Microsoft 日历、Zoom / Daily、HubSpot / Zoho / Pipedrive 等。
- 限流用的 Unkey 密钥是可选项，不配也能正常跑。

## 已知限制

- 上游定位为个人、非生产场景，自托管需要数据库管理与服务器安全方面的经验，风险由使用者承担。
- 团队、组织、Insights、Workflows、SSO/SAML 等企业功能已被移除，不是未启用而是不存在。
- 没有官方托管版本，也没有商业支持通道；社区版问题走上游仓库的 issue。
- 构建期依赖数据库，这让纯前端式的快速试跑变得不可能。
- 该仓库是社区分支，向这里提交的改动不会回流到商业版代码库。
- 部分能力（如严格 CSP）仍在演进，登录页与其他页面、SSG 页面的支持程度并不一致。

## 自检清单

执行前：

- [ ] 明确这是社区版：不要承诺 SSO / 团队协作 / 工作流这类企业能力
- [ ] 确认目标机器满足 Node 18+、PostgreSQL 13+、Docker 可用
- [ ] 确认 `NEXTAUTH_SECRET` 与 `CALENDSO_ENCRYPTION_KEY` 是新生成的，而不是 `.env.example` 里的占位值
- [ ] 确认构建期与运行期的 `NEXT_PUBLIC_WEBAPP_URL` 一致，且 `NEXTAUTH_URL` 能让容器回环到自身
- [ ] 集成类配置先确认回调地址写的是实际域名，不是示例域名

执行后：

- [ ] 打开站点能完成安装向导并成功登录
- [ ] 日历 / 会议集成在设置页里显示为已连接，而不是只有环境变量
- [ ] 走一遍真实预约链路：挑时段 → 下单 → 收到邮件 → 日历里出现事件
- [ ] 汇报时说明用的是哪条安装路径与哪个数据库，不编造版本号与镜像标签

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/calcom/cal.diy | 上游仓库（安装与完整文档以它为准） |

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
