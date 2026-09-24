---
name: sanjianke-chatwoot
slug: sanjianke-chatwoot
displayName: 三剪客 · 自托管多渠道客服工作台
description: "把网站聊天、邮件、社交平台私信等渠道的客户消息收进一个自托管收件箱：Docker Compose 部署、数据库初始化、反向代理要点、升级与运维，以及用官方 CLI 和三类 HTTP API 做批量处理。遇到问题可加技术微信 9872659。"
summary: "客户消息散在邮箱、社媒私信和网页聊天里，客服靠人肉切换窗口——Chatwoot 把它们统一到一个可自己托管的收件箱，再做分配、打标签、快捷回复与报表。含 Docker 上线全流程、Nginx 反代要点、升级口径、超级管理员与 CLI/API 用法。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 客服
---

# 三剪客 · 自托管多渠道客服工作台

客户的消息从来不只从一个地方来：网站上的在线咨询、发给客服邮箱的信、社交平台的私信。人少的团队靠人肉切窗口还能撑，一旦要有第二个人接手、要统计响应时间、要让客户数据留在自己服务器上，就需要一个真正的客服工作台。

Chatwoot 就是补这一环的：它把多个渠道的会话收进同一个收件箱，支持坐席分配、私有备注、标签、快捷回复、营业时间与帮助中心，并且可以完全自托管——数据库、附件、会话记录都落在你自己的机器上。

它的代价也很明确：这是一套**要自己运维的 Web 服务**（Ruby 应用 + PostgreSQL + Redis + 后台任务进程），不是一段塞进页面的前端脚本。

**上游项目**：`Chatwoot`　**仓库**：https://github.com/chatwoot/chatwoot

## 什么时候用 / 不用

**用它**：

- 用户说「给网站加在线客服」并且需要**坐席侧**多人协作：分配、转交、私有备注、@提及。
- 客户消息同时从网页聊天、邮件、Telegram、WhatsApp、Facebook、Instagram 等渠道进来，想统一排队处理。
- 有「数据不想出境 / 不想按坐席数付月费」的诉求，要自己托管客户会话数据。
- 需要把会话、联系人、标签接进自己的系统做统计或自动化——它提供应用侧、客户端侧、平台侧三类 HTTP API。
- 想让脚本或 AI 助手直接读会话、回消息、分配工单——官方命令行客户端支持非交互调用与结构化输出。

**不要用它**：

- **不想维护服务器**。它需要 PostgreSQL、Redis、常驻 Web 进程和后台任务进程；没有运维余力就别选自托管。
- 只是想给页面挂一个**极简聊天挂件**，没有坐席协作和工单需求。这种情况下运维成本远大于收益。
- 目的是**同事之间的内部沟通**，或想拿它当**通用工单 / 项目管理**系统。它以会话为中心，面向「客户—客服」这条线，群组协作与跨部门任务流不是它的范围。
- **依赖企业版专属能力**（例如免改代码的自定义品牌、部分高级治理能力）。社区版拿不到，选型前先确认。
- 想做**面向公网的高并发 SaaS 转售**：社区版许可允许改造，但架构仍要按官方要求扩到多应用服务器 + 独立 worker。

## 安装

**前置条件**（官方口径）：Docker 与 Compose 建议不低于 `Docker 20.10.10`、`Docker Compose v2.14.1`。Linux 上可用官方脚本装 Docker：

```bash
apt-get update && apt-get upgrade
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
apt install docker-compose-plugin
```

**第一步：拉取官方模板**

```bash
wget -O .env https://raw.githubusercontent.com/chatwoot/chatwoot/develop/.env.example
wget -O docker-compose.yaml https://raw.githubusercontent.com/chatwoot/chatwoot/develop/docker-compose.production.yaml
```

**第二步：改配置**（只列必须动的，其余按需）

| 变量 | 说明 |
|---|---|
| `SECRET_KEY_BASE` | 校验签名 cookie 用，必须换成随机长串；官方说明用 `rake secret` 生成，且只允许字母数字 |
| `FRONTEND_URL` | 这个实例最终对外的地址 |
| `ENABLE_ACCOUNT_SIGNUP` | 设 `false` 关掉注册入口；设 `api_only` 则只保留 API 建号 |
| `POSTGRES_PASSWORD` / `REDIS_PASSWORD` | 数据库与 Redis 密码，**compose 文件与 `.env` 两处都要对上** |
| `ACTIVE_STORAGE_SERVICE` | 默认 `local`；换 S3 兼容对象存储时改这里并填 `S3_BUCKET_NAME` 等 |
| `RAILS_INBOUND_EMAIL_SERVICE` + `RAILS_INBOUND_EMAIL_PASSWORD` | 要走邮件渠道**收信**时必须单独配 |

```bash
nano .env
nano docker-compose.yaml     # postgres 密码要与 .env 一致
```

**第三步：初始化数据库并启动**

```bash
# 首次建库必须用 chatwoot_prepare，不能用 db:migrate
docker compose run --rm rails bundle exec rails db:chatwoot_prepare
docker compose up -d
curl -I localhost:3000/api     # 期望返回 200
```

**第四步：套反向代理**。官方 compose 里 Web 进程只绑 `127.0.0.1:3000`，**默认不对公网开放**，需要自己加 Nginx（或同类代理）并配 HTTPS。Nginx 配置里有一个不能漏的关键项：

```nginx
server {
  server_name <yourdomain.com>;
  set $upstream 127.0.0.1:3000;

  # 必须：Nginx 默认丢弃带下划线的请求头，而 API 依赖这类请求头
  underscores_in_headers on;

  location / {
    proxy_pass_header Authorization;
    proxy_pass http://$upstream;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_http_version 1.1;
    proxy_buffering off;
    client_max_body_size 0;
    proxy_read_timeout 36000s;
    proxy_redirect off;
  }
  listen 80;
}
```

```bash
nginx -t && systemctl reload nginx
apt install certbot python3-certbot-nginx
mkdir -p /var/www/ssl-proof/chatwoot/.well-known
certbot --webroot -w /var/www/ssl-proof/chatwoot/ -d yourdomain.com -i nginx
```

**想跑社区版镜像**：把镜像 tag 换成对应 `-ce` 形式（当前 `master` 对应 `latest-ce`，具体版本形如 `v*-ce`）。

**其他官方支持的路径**：Heroku 一键部署、DigitalOcean 一键 Kubernetes、Helm Chart，以及 Linux VM 原生安装（源码构建的 Ruby / Node 版本要求见官方 Requirements 页）。

## 常用操作

**1. 首次进站完成初始化**

浏览器打开你的域名，首次访问会出现引导流程，在里面创建账号与组织。之后用 `/super_admin` 进入超级管理员控制台（AI 相关配置、应用配置都在这里）。

如果引导页没出现、直接跳到登录页，官方给的处理办法是在 Rails 控制台执行下面这条并重启服务：

```ruby
Redis::Alfred.set(Redis::Alfred::CHATWOOT_INSTALLATION_ONBOARDING, true)
```

**2. 进 Rails 控制台**（官方命令，容器名按当前目录拼）

```bash
docker exec -it $(basename $(pwd))-rails-1 sh -c 'RAILS_ENV=production bundle exec rails c'
```

进去后可做只读排查，例如确认邮件配置是否真的生效：

```ruby
ActionMailer::Base.smtp_settings
```

**3. 升级**

```bash
docker compose pull
docker compose up -d
docker compose run --rm rails bundle exec rails db:chatwoot_prepare
```

官方提醒：跨度大的老版本不要一步跳到最新，应依次经过中间镜像 tag，并在每一跳之后都执行一次上面的数据库准备命令。

**4. 用官方 CLI 在终端处理会话**（适合脚本化，也适合交给 AI 助手调用）

```bash
# 安装（macOS / Linux）
curl -fsSL https://chwt.app/install-cli | sh

# 登录：依次填实例地址、坐席资料页里的 API access token、账号 ID
chatwoot auth login

# 看我名下待处理的会话；按状态 / 坐席 / 收件箱 / 标签筛
chatwoot convs -s open --assignee me
chatwoot convs --inbox 5 -l billing,urgent

# 看一条、回一条、写内部备注、改状态、分配、打标签
chatwoot conv 123 messages
chatwoot conv 123 reply "Thanks, looking into it"
chatwoot conv 123 reply "internal note" --private
chatwoot conv 123 resolve
chatwoot conv 123 assign --agent alice
chatwoot conv 123 label billing,urgent

# 结构化输出便于脚本消费
chatwoot convs -o json
```

CLI 的语法口径：复数名词是列表（`convs` / `contacts` / `agents`），单数 + ID 是查看，单数 + ID + 动词是操作。

**5. 直接用 HTTP API**

官方把接口分成三类，选错是最常见的返工原因：

| 类型 | 认证方式 | 适用 |
|---|---|---|
| 应用接口 | 坐席资料页生成的 access token | 账号内的会话、联系人、标签等业务自动化 |
| 客户端接口 | `inbox_identifier` + `contact_identifier` | 自建面向终端用户的聊天界面 |
| 平台接口 | 超级管理员控制台里平台应用生成的 token | 跨账号管理用户与账号，仅自托管可用 |

```bash
# 读一条会话（请求头名与具体参数以 API 文档页面为准）
curl -X GET "https://your-domain.com/api/v1/accounts/1/conversations/123" \
  -H "api_access_token: <你的 access token>"

# CLI 里没有对应命令的接口可以直接透传（账号相对路径会自动补 /api/v1/accounts/<id>）
chatwoot api /conversations/123
chatwoot api -X PATCH /conversations/123 --data '{"status":"open"}'
chatwoot api --exact /api/v1/profile     # 不属于账号范围的接口加 --exact
```

**6. 换存储到 S3 兼容对象存储**

```bash
# .env
ACTIVE_STORAGE_SERVICE=s3
S3_BUCKET_NAME=your-bucket
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=...
```

改完重建容器。附件体量大的实例建议一开始就走对象存储，避免本地卷无限膨胀。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 首次初始化数据库就报错 | 用了 `rails db:migrate` | 官方明确说明首次必须用 `db:chatwoot_prepare`，此时跑 migrate 会出错 |
| 装完了外网访问不到 3000 端口 | compose 里 Web 只绑 `127.0.0.1:3000`，这是官方设计 | 不要图省事把它改成 `0.0.0.0` 裸奔，加 Nginx/代理并配 HTTPS |
| 反代之后 API 调用全部认证失败，直连却正常 | Nginx 默认会丢掉带下划线的请求头，而 API 依赖这类请求头 | `nginx.conf` 里加 `underscores_in_headers on;`，`nginx -t` 后 reload |
| 平台接口报 401「Non permissible resource」 | 平台 token 只能访问它自己创建的对象，或显式授权给它的对象；UI 里建的账号不在其中 | 在 Rails 控制台授权，例如 `PlatformAppPermissible.create!(platform_app: PlatformApp.find(1), permissible: Account.find(1))` |
| 注册 / 找回密码邮件发不出去，账号卡在未确认 | `SMTP_ADDRESS` 为空时应用会退回去用本机 sendmail，容器里通常没有 | 明确配好 `SMTP_ADDRESS` / `SMTP_PORT` / 账号密码，并用控制台 `ActionMailer::Base.smtp_settings` 核对实际生效值 |
| 换了 `SECRET_KEY_BASE` 后所有人被登出、会话异常 | 这个值用于校验签名 cookie，换掉等于让所有旧会话失效 | 首次部署就生成并固定留档，不要每次重建容器时重新随机 |
| 重建容器后 Redis 连不上 | `.env` 的 `REDIS_PASSWORD` 与 compose 里 redis 启动参数不一致 | 两处一起改；Redis 密码是 compose 通过环境变量注入的，不是 redis 自带的默认值 |
| 升级后功能报错或数据对不上 | 跨版本跳得太多，数据库结构没跟上 | 按官方升级说明依次经过中间 tag，每一跳都执行 `db:chatwoot_prepare`；升级前先备份 |
| 邮件渠道收不到客户回信 | 入站邮件需要单独的入口配置（入口类型、入站密码、对应服务商的 webhook） | 只配好发信 SMTP ≠ 收信可用，要按官方 Email Channel 文档把入站那条链路单独配通 |
| 用了默认镜像却想跑社区版 | 默认 tag 不是社区版 | 换成 `-ce` 系列 tag（如 `latest-ce`）；企业版的分发与坐席数受其许可约束 |
| 内存吃紧，升级时机器卡死 | 官方要求最低 4GB 内存，并建议加至少 1GB swap 以扛住升级过程 | 按官方 Requirements 页核对 CPU / 内存 / swap，再考虑把 worker 与应用分离部署 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取镜像与模板文件；各渠道（网页挂件、邮件、社交平台、Telegram 等）的收发与回调；对接对象存储；调用 HTTP API |
| 读取文件 | 是 | 读取 `.env`、compose 文件、Nginx 配置、本地存储卷中的附件；控制台排查时读取应用配置 |
| 写入文件 | 是 | 生成 `.env` 与 compose 配置、Nginx 站点配置；向本地存储卷写入附件（升级/重建容器前必须保留卷） |
| 凭证 | 是 | 数据库与 Redis 密码、`SECRET_KEY_BASE`、SMTP 账号、各渠道应用密钥、API token、对象存储密钥。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | 常驻运行 Web、后台任务、Postgres、Redis 多个容器；建议 `restart: always` |

## 触发场景

- 「客户消息太散了，想收进一个后台」
- 「不想把客户数据放在别人的云上，能不能自己部署一套客服系统」
- 「网站上加个在线客服，还要能分配给同事」
- 「把客服邮箱和社媒私信也接到一起」
- 「想用脚本批量导出会话、自动打标签」
- 「这个客服系统怎么用 Docker 装、装完怎么升级」

## 能力边界

**覆盖**：

- 多渠道统一收件箱：网页聊天挂件、邮件、社交平台私信、Telegram、短信等（完整渠道清单以官方 Supported Features 页为准）。
- 客服协作：会话分配与转交、团队、私有备注与 @提及、标签、快捷回复、自定义视图与筛选、营业时间与自动回复、坐席容量管理。
- 联系人管理、自定义属性、分段、主动触达活动、预聊天表单。
- 帮助中心站点（可用独立域名）与文章检索。
- 报表：会话 / 坐席 / 收件箱 / 标签 / 团队报表、满意度调查、可导出。
- 集成：Slack、Linear、Shopify、对话机器人框架、实时翻译、可内嵌自建工具的仪表盘应用。
- 自动化与扩展：自动化规则、Webhook、三类 HTTP API、官方 CLI。
- 部署形态：Docker Compose、Helm、Heroku / DigitalOcean 等托管路径；存储可落本地或 S3 兼容对象存储。

**不覆盖**：

- 不提供模型能力本身；AI 相关功能要自行接入外部模型服务并在超级管理员控制台里配置密钥。
- 不做同事之间的内部即时沟通与群组协作。
- 不做通用项目管理 / 看板 / 迭代排期。
- 不代管证书与域名：HTTPS、反向代理、备份策略、监控告警都要自己落地。
- 不包含企业版专属能力；社区版的自定义品牌需要改源码。
- 不提供官方代部署服务，也不对改造过的老版本负责（上游 FAQ 口径）。
- 移动端 App 的构建与分发不在范围内；自建移动端需按官方 Custom Mobile App 文档自行处理。

## 依赖条件

- Docker 与 Compose：官方建议不低于 `Docker 20.10.10`、`Docker Compose v2.14.1`。
- 操作系统：官方支持 Ubuntu 20.04 一类的 Linux 环境；项目本身按 Linux 开发，Windows 上官方建议走虚拟机。
- 数据库：只支持 PostgreSQL（compose 模板用的是带 pgvector 的 pg16 镜像），磁盘另需 5–10GB 起。
- 缓存与队列：Redis 建议 7.0 以上，起步 100MB 即可。
- 硬件：官方给出的最低口径是 4 核 / 4GB 内存，并建议额外加至少 1GB swap；更高并发按官方 Requirements 页放大或横向扩应用服务器。
- 域名与证书：对公网提供服务必须自备域名、反向代理与 TLS 证书。
- 邮件：发注册确认、密码重置、邮件渠道消息需要自备可用 SMTP；要收邮件还要单独配入站链路。
- 渠道凭证：接入社交平台、Telegram 等渠道需要对应平台的开发者应用与密钥。
- 源码构建方式额外要求：Ruby 3.2 及以上（官方要求 MRI）、Node.js 20.x。

## 已知限制

- Web 容器默认只监听本机回环地址，直接暴露公网需自行调整并承担安全后果。
- 后台任务进程在繁忙实例上会持续涨内存，官方建议条件允许时与应用服务器分开部署。
- 邮件渠道的收发是两条独立链路，只配发信往往会被误判为「渠道已通」。
- 平台接口的权限模型是「只认自己创建或显式授权的对象」，与直觉不同，容易卡住。
- 社区版与企业版功能有差异且镜像 tag 不同；品牌定制在社区版要动源码。
- 界面、环境变量与镜像 tag 随上游迭代变化；命令与参数请以官方文档站当前内容为准。
- 具体版本号、发布日期与 star 数请以仓库与官方发布页面的实时信息为准，这里不做断言。

## 自检清单

- [ ] 已确认部署路径（Docker Compose / Helm / 托管平台 / 原生安装），并核对机器满足官方最低配置。
- [ ] `SECRET_KEY_BASE` 已生成随机值并单独留档，`FRONTEND_URL` 填的是最终对外地址。
- [ ] `POSTGRES_PASSWORD` 与 `REDIS_PASSWORD` 在 `.env` 和 compose 文件里保持一致。
- [ ] 首次建库用的是 `db:chatwoot_prepare`，且 `docker compose up -d` 后 `curl -I localhost:3000/api` 返回 200。
- [ ] 反向代理已配好且包含 `underscores_in_headers on;`；HTTPS 证书已签发并会自动续期。
- [ ] 已完成首次引导、建好管理员，并按需关掉注册入口或设为仅 API 建号。
- [ ] SMTP 已配通并实测能发信；需要邮件渠道时入站链路也已单独配通。
- [ ] 数据卷（Postgres、Redis、storage）已确认持久化，并有备份方案。
- [ ] 升级前已备份，且按「拉镜像 → 起容器 → `db:chatwoot_prepare`」顺序执行。
- [ ] 已确认自己需要的功能不在企业版专属范围内（尤其自定义品牌）。
- [ ] 用到的 API 类型选对了（应用 / 客户端 / 平台），token 来源正确。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/chatwoot/chatwoot | 上游仓库（安装与完整文档以它为准） |
| https://developers.chatwoot.com/self-hosted/deployment/docker | 官方 Docker 部署步骤（本文安装命令来源） |
| https://developers.chatwoot.com/cli/commands | 官方 CLI 命令参考（本文终端操作来源） |
| https://developers.chatwoot.com/self-hosted/configuration/environment-variables | 环境变量清单 |

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
