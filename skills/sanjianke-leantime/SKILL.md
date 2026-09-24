---
name: sanjianke-leantime
slug: sanjianke-leantime
displayName: 三剪客 · 开源项目协作与任务管理台
description: "Leantime：自托管的开源项目管理系统，覆盖看板/甘特/工时/目标/KPI/知识库与 LDAP、OIDC、S3。本文讲清它的环境要求、Docker 与手动部署、初始化安装向导、配置项、升级备份与常见坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Leantime 的落地指引：PHP 8.2+ 与 MySQL/MariaDB 环境要求、官方 Docker 镜像与 compose 部署、config/.env 配置项、/install 与 /update 向导、CLI 升级命令、插件目录挂载与权限、反向代理与子目录部署，以及安装升级阶段的高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 项目管理
---

# 三剪客 · 开源项目协作与任务管理台

小团队要一个"能自己掌控数据"的项目管理台，通常绕不开三件事：任务看板得够用、工时和目标是同一个系统里的、账号要能接公司已有的登录体系。Leantime 就是冲着这三件事做的：它把战略规划、执行看板、工时表、知识库放在一个自托管实例里，同时提供 LDAP / OIDC 接入和 S3 附件存储。

它的定位更偏"团队协作台"而不是"研发流水线"——没有代码仓库、CI、制品库这些研发链路能力，别指望它顶替 DevOps 工具链。

**上游项目**：`Leantime`　**仓库**：https://github.com/Leantime/leantime

## 什么时候用 / 不用

**用它**：

- "我们要一个自己能部署的项目管理台，数据不出内网。"——它是完整可自托管的 PHP 应用，官方提供 Docker 镜像。
- "需要看板 + 甘特图 + 工时表 + 目标 KPI 在同一套系统里。"——这些都在同一个实例里，不需要拼三四个工具。
- "公司已经有 LDAP / Active Directory，登录要统一。"——配置里内置 LDAP 与 OIDC 开关。
- "附件要放对象存储，不要占服务器磁盘。"——支持 S3 及兼容端点。
- "想要能扩展、能对接外部系统。"——有插件机制和 JSON-RPC 接口。

**不要用它**：

- **想要零运维的 SaaS 体验**——它必须自己准备 PHP 运行环境、数据库和 Web 服务器，装完还得跑安装向导。
- **需要严格的研发过程管理**（代码托管、CI/CD、制品、测试用例管理）——不在它能力范围内，这类需求应看研发专用平台。
- **只想要一个纯 Markdown 文档站**——文档只是它的附属模块，专门做文档有更轻的选择。
- **团队规模很小、只想要一张待办清单**——为了几张卡片维护一套 PHP + MySQL + 定时任务不划算。
- **需要商业授权闭源二次分发**——上游许可是 AGPLv3（`app/Plugins` 目录有例外条款），闭源改造前请先确认合规。

## 安装

### 生产环境：官方 Docker 镜像

官方在 Docker Hub 维护 `leantime/leantime` 镜像，启动前先准备好一个 MySQL 数据库和网络：

```bash
docker network create leantime-net

docker run -d --restart unless-stopped -p 8080:8080 --network leantime-net \
  -e LEAN_DB_HOST=mysql_leantime \
  -e LEAN_DB_USER=admin \
  -e LEAN_DB_PASSWORD=321.qwerty \
  -e LEAN_DB_DATABASE=leantime \
  -e LEAN_EMAIL_RETURN=changeme@local.local \
  --name leantime leantime/leantime:latest
```

- 上面是官方 README 给出的示例命令，**数据库账号密码请换成自己的**。
- 官方推荐的做法是用它维护的 compose 文件（仓库 `Leantime/docker-leantime` 中的 `docker-compose.yml`），自己手搓 `docker run` 只适合已有外部数据库的场景。
- 如果**要用插件**，必须把插件目录挂出来：`-v <本地目录>:/var/www/html/app/Plugins`，并保证容器内 `www-data` 用户对该目录有权限，否则安装可能失败、或重启后插件被删掉。
- 放在反向代理后面时，要显式告诉应用对外地址：`-e LEAN_APP_URL=https://yourdomain.com`，否则生成的链接和回调地址会错。

启动后打开 `http://<你的域名或IP>:8080/install`，按向导建库表和第一个用户账号。

### 生产环境：手动部署

1. 从 release 页下载发布包（文件名形如 `Leantime-vx.x.x.zip`）。
2. 建一个空的 MySQL 数据库。
3. 把整份目录上传到服务器，并把域名根目录指向其中的 `public/` 子目录。
4. 把 `config/sample.env` 重命名为 `config/.env`，填好数据库主机、库名、用户名、密码。
5. 访问 `<你的域名>/install`，按向导完成数据库初始化和首个用户创建。

用 IIS 时还需要额外放行 `PATCH` 动词（在"处理程序映射 → 请求限制 → 谓词"里加上），否则部分请求会失败。

### 开发环境

```bash
# Docker 化的开发环境（需要 docker、docker compose、make、composer、git、npm）
make clean build
make run-dev          # 开发服务器起在 5080 端口
```

开发容器自带了 MySQL、邮件服务、phpMyAdmin 和 S3 模拟服务，端口分别是 5080（应用）、8081（邮件）、8082（phpMyAdmin，账号密码同为 `leantime`）、8083（S3 模拟，需在开发用 `.env` 里开启）。

### 验证

```bash
# 容器是否起来了
docker ps --filter name=leantime

# 应用日志（Docker 部署时把日志通道设为 stderr 便于查看）
docker logs -f leantime
```

## 常用操作

**1. 用环境变量覆盖任何 `.env` 配置项**

官方说明所有 `.env` 里的配置都可以改成环境变量传入，容器化部署基本都走这条路：

```bash
docker run -d --name leantime -p 8080:8080 \
  -e LEAN_DB_HOST=db -e LEAN_DB_DATABASE=leantime \
  -e LEAN_DB_USER=leantime -e LEAN_DB_PASSWORD='换成强密码' \
  -e LEAN_SITENAME='团队协作台' \
  -e LEAN_DEFAULT_TIMEZONE='Asia/Shanghai' \
  -e LEAN_LOG_CHANNELS='stderr' \
  leantime/leantime:latest
```

**2. 走安装向导与升级向导**

```text
http://<域名>/install    # 首次安装：初始化数据库、创建第一个账号
http://<域名>/update     # 版本升级后如涉及数据库变更，访问这里执行迁移
```

**3. 用 CLI 执行升级**

官方 README 给出的命令行升级方式：

```bash
php bin/leantime system:update
```

该入口还支持哪些子命令以本机代码为准，可先执行 `php bin/leantime` 查看当前版本支持的命令列表。

**4. 手动升级（非 Docker）**

```bash
# 1) 先备份数据库和整个应用目录
# 2) 用新版本文件整体替换旧目录
# 3) 若版本涉及数据库变更，访问 /update 完成迁移，或用上面的 CLI 命令
```

**5. Docker 升级**

```bash
# 升级前确认 mysql 容器是用挂载卷启动的，否则删容器会连数据一起删掉
docker compose down
docker compose pull
docker compose up -d
```

**6. 开启 S3 附件存储**

在 `config/.env`（或环境变量）里配置：

```ini
LEAN_USE_S3 = true
LEAN_S3_KEY = ''
LEAN_S3_SECRET = ''
LEAN_S3_BUCKET = ''
LEAN_S3_REGION = ''
LEAN_S3_END_POINT = null
LEAN_S3_USE_PATH_STYLE_ENDPOINT = false
```

`LEAN_S3_USE_PATH_STYLE_ENDPOINT` 在自建 MinIO 之类的路径风格端点下要设为 `true`。

**7. 接入企业登录**

```ini
# LDAP / Active Directory
LEAN_LDAP_USE_LDAP = true
LEAN_LDAP_HOST = 'ldap.example.com'
LEAN_LDAP_LDAP_TYPE = 'OL'      # OL = OpenLDAP，AD = Active Directory
LEAN_LDAP_DN = 'CN=users,DC=example,DC=com'

# OIDC
LEAN_OIDC_ENABLE = true
LEAN_OIDC_CLIENT_ID =
LEAN_OIDC_CLIENT_SECRET =
LEAN_OIDC_PROVIDER_URL =
LEAN_OIDC_CREATE_USER = false
```

LDAP 的属性映射由 `LEAN_LDAP_KEYS` 这个 JSON 串控制，AD 与 OpenLDAP 的属性名不同（如 `uid` vs `cn`、`displayname` vs `givenName`），照配置文件里的两套注释模板改。

**8. 用 Redis 托管会话与缓存**

```ini
LEAN_USE_REDIS = true
LEAN_REDIS_HOST = '127.0.0.1'
LEAN_REDIS_PORT = 6379
LEAN_REDIS_PASSWORD = ''
LEAN_REDIS_SESSION_DB = 1
```

注意 `LEAN_REDIS_SESSION_DB` 要和缓存用的库（`LEAN_REDIS_DB`，默认 0）分开，否则清缓存可能把所有人踢下线。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 首页能开、点进去 404 或静态资源全丢 | 域名根目录指到了应用根目录而不是 `public/` 子目录 | 把 Web 服务器站点根目录改成 `<应用目录>/public` |
| 反向代理 / HTTPS 后面生成的重定向和邮件链接指向内网地址 | 应用不知道对外域名 | 设置 `LEAN_APP_URL=https://yourdomain.com` |
| 装在子目录（如 `/pm`）下路由全乱 | 只改了服务器配置，没告诉应用自己的基路径 | 同时设置 `LEAN_APP_URL` 与 `LEAN_APP_DIR`（例如 `/pm`，不带结尾斜杠） |
| 插件装完重启就没了 / 安装插件报权限错误 | 容器内没挂载 `app/Plugins`，或挂载后容器用户写不进去 | 挂载 `-v <目录>:/var/www/html/app/Plugins` 并让 `www-data` 可写 |
| 数据库容器重建后数据全没了 | compose 里的 MySQL 没有用挂载卷持久化 | 升级/重建前确认卷已挂载，并先做数据库备份 |
| 会话频繁掉线或登录状态互相串 | `LEAN_SESSION_PASSWORD` 还是示例值，或多实例间没共享会话存储 | 把会话加密串换成自己的强随机值；多实例部署时开启 Redis 会话 |
| 容器里看不到应用日志 | 默认把日志写进文件 | 把 `LEAN_LOG_CHANNELS` 设为包含 `stderr`，用 `docker logs` 查看 |
| 内网离线环境页面加载卡顿 | 应用默认会联网拉取公告 | 设 `LEAN_NEWS_ENABLED=false` 关掉公告服务 |
| 用户被限流挡在门外，尤其批量邀请时 | 内置了按 IP / 用户的限流（登录、接口、邀请各有阈值） | 按需调整 `LEAN_RATELIMIT_AUTH`、`LEAN_RATELIMIT_INVITES_USER`、`LEAN_RATELIMIT_INVITES_TENANT`，不要通过关闭登录限流来图省事 |
| 邮件发不出去 | 默认走 PHP 的 `mail()`，而容器里通常没有可用 MTA | 设 `LEAN_EMAIL_USE_SMTP=true` 并填 `LEAN_EMAIL_SMTP_HOSTS` / `LEAN_EMAIL_SMTP_PORT` / `LEAN_EMAIL_SMTP_USERNAME` / `LEAN_EMAIL_SMTP_PASSWORD` / `LEAN_EMAIL_SMTP_SECURE` |
| IIS 上部分操作 405 | IIS 默认不允许 `PATCH` 方法 | 在 PHP 处理程序映射的"请求限制 → 谓词"里加入 `PATCH`；升级 PHP 后需重做 |
| 手动升级后页面报错 | 有数据库结构变更没执行迁移 | 访问 `/update`，或用 `php bin/leantime system:update` |
| 上传附件失败 | 本地上传目录或备份目录不可写 | 确认 `LEAN_USER_FILE_PATH`、`LEAN_DB_BACKUP_PATH` 指向的目录对运行用户可写（或改用 S3） |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取 Docker 镜像 / 发布包、容器内连数据库与 SMTP、启用 S3 或 OIDC 时访问外部端点。离线内网部署可在服务端关闭外网，但要关掉公告服务 |
| 读取文件 | 是 | 读取 `config/.env`、上传的附件、日志与模板文件 |
| 写入文件 | 是 | 写入会话文件、上传附件、日志、数据库备份；插件安装会写入 `app/Plugins` |
| 凭证 | 是 | 数据库账号密码、`LEAN_SESSION_PASSWORD`、SMTP 账号、S3 密钥、LDAP 绑定账号、OIDC 客户端密钥。建议走容器密钥或 `.env` 文件权限控制，不要写进镜像层 |
| 子进程 / 后台常驻 | 是 | 应用与数据库长期常驻；定时任务（cron）需要周期性触发应用内的 `/cron` 入口，否则通知、提醒类功能不会触发 |

## 触发场景

- "帮我把 Leantime 用 Docker 部署起来。"
- "这个项目管理台装完首页 404，帮我看看。"
- "Leantime 想接我们公司的 LDAP 登录，怎么配？"
- "版本升级后数据库要迁移，命令是什么？"
- "附件想放 S3，配置怎么写？"
- "Leantime 和 Jira 这类工具比，适合我们吗？"

## 能力边界

**覆盖**：

- 项目与任务管理：看板、甘特/时间线、表格与列表视图、里程碑、子任务与依赖、迭代管理
- 规划类工具：项目仪表盘与报表、目标与指标跟踪、精益画布与商业模式画布、SWOT、风险分析、回顾
- 工时与知识：时间追踪与工时表、Wiki/文档、想法看板、文件存储（本地或 S3）、评论与讨论
- 账号与权限：多角色与按项目授权、两步验证、LDAP / OIDC 集成
- 扩展与集成：插件机制、JSON-RPC 接口、与聊天协作工具的集成、多语言（20 种以上）

**不覆盖**：

- 代码托管、代码评审、CI/CD、制品与发布管理（不是它的场景）
- 完整的测试用例与缺陷追踪工作流（它做的是通用任务，不是测试管理系统）
- 原生的即时通讯（它做集成与通知，不自带聊天）
- 自动化运维：升级、备份、定时任务、TLS 都需自行在宿主机/容器层解决

## 依赖条件

- PHP 8.2+
- MySQL 8.0+ 或 MariaDB 10.6+
- Apache / Nginx（IIS 需额外放行 `PATCH` 动词等改动）
- 必需 PHP 扩展：bcmath、ctype、curl、dom、exif、fileinfo、filter、gd、hash、ldap、mbstring、mysql、opcache、openssl、pcntl、pcre、pdo、phar、session、tokenizer、zip、simplexml
- 用 Docker 部署时：Docker 与 docker compose；用开发环境时还需要 make、composer、git、npm
- 不需要外部账号或 API Key；接入 S3 / SMTP / LDAP / OIDC 时才需要对应的凭据

## 已知限制

1. 上游对自托管的支持范围限于官方 Docker 发布与标准手动安装，第三方发行封装不在支持范围内。
2. 官方表示只对最新版本提供支持，旧版本遇到问题通常只能先升级再排查。
3. 插件目录有独立的许可例外条款，混合使用商业插件时需自行确认授权。
4. 应用自身不内置 TLS、备份计划与定时任务调度，这些都要在宿主机或容器编排层完成。
5. 各版本的环境变量与限流默认值可能调整，最终以随版本发布的 `config/sample.env` 为准。
6. 官方安装与升级的排错条目集中在 `https://docs.leantime.io/installation/common-issues`，遇到部署问题先查这里。

## 自检清单

执行前：

- [ ] 确认目标机器的 PHP 版本与扩展满足要求，数据库已就绪
- [ ] 确认应用目录与上传目录对 Web 运行用户可写
- [ ] 域名根目录指向 `public/`，不是应用根目录
- [ ] 反向代理 / HTTPS 场景已准备 `LEAN_APP_URL`（子目录再加 `LEAN_APP_DIR`）
- [ ] 已把 `LEAN_SESSION_PASSWORD` 从示例值换成强随机值
- [ ] 需要插件功能时，已规划 `app/Plugins` 的挂载与属主

执行后：

- [ ] 访问 `/install`（或 `/update`）走完向导，没有残留报错
- [ ] 能正常登录、创建项目与任务，附件可上传下载
- [ ] 邮件通道验证过（用一次邀请或密码重置试发）
- [ ] 容器重启后数据与插件仍在
- [ ] 备份已经跑通一次，且知道恢复步骤

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/Leantime/leantime | 上游仓库（安装与完整文档以它为准） |
| https://docs.leantime.io/installation/common-issues | 官方安装与升级常见问题 |
| https://github.com/Leantime/leantime/blob/master/config/sample.env | 全部配置项与默认值的权威清单 |
| https://hub.docker.com/r/leantime/leantime | 官方镜像 |

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
