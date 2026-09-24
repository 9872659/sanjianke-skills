---
name: sanjianke-mattermost
slug: sanjianke-mattermost
displayName: 三剪客 · 自托管团队协作沟通平台
description: "把团队沟通搬回自己的服务器：Mattermost 的 Docker Compose 部署、环境变量与数据目录权限、NGINX 反向代理与证书、镜像版本升级，以及数据卷没挂对、目录属主错误、环境变量覆盖了界面设置、拿试用镜像上生产这类高频事故的排查。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "一个自托管的团队协作平台：频道聊天、线程讨论、语音通话与屏幕共享、工作流自动化，还能通过 Webhook、斜杠命令和插件接自家系统。含容器化部署全流程、必须改的环境变量、目录权限与反向代理要点，以及官方明确划出的「哪些场景不能用 Docker」的边界。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 自托管团队协作沟通平台

团队聊天工具最尴尬的地方在于：消息、文件、讨论记录全在别人的服务器上，而它同时又是公司信息密度最高的地方。Mattermost 解决的就是这件事——它是一个**自托管的团队协作平台**，把频道聊天、线程讨论、语音通话、屏幕共享放在你自己能掌控的环境里，同时提供 Webhook、斜杠命令、插件等扩展方式，让聊天工具能接上你自己的系统。

它的形态很轻：官方说明核心是用 Go 和 React 写的，可以跑成单个 Linux 二进制，依赖 PostgreSQL。也就是说，只要一台 Linux 机器加一个数据库，你就能拥有一套完整的团队沟通平台。

**上游项目**：`Mattermost`　**仓库**：https://github.com/mattermost/mattermost

## 什么时候用 / 不用

**用它**：

- 用户说「想搭一个自己的团队聊天工具」「聊天记录不要放别人服务器上」。
- 需要一个**自托管沟通平台**：频道、私聊、线程回复、文件共享、搜索与归档。
- 想把聊天和自有系统打通：用 Webhook、斜杠命令、插件或 Apps 把告警、工单、构建结果推进频道。
- 需要**语音通话与屏幕共享**，并且希望它和聊天在同一套系统里，客户端覆盖 Web、桌面端与移动端。
- 要做**工作流自动化**：把消息、审批与外部动作串起来。

**不要用它**：

- **不想运维、只要一个聊天工具**。自托管意味着你要自己管数据库、升级、备份和证书。
- **要求开箱即用的高可用与集群**。官方明确说明 Docker 方式**不支持开箱的集群部署与高可用**，这类场景要转向 Kubernetes 方案。
- **想在 macOS / Windows 上正式部署**。官方只对 Linux 上的 Docker 部署提供支持，这两个系统仅限测试与开发用途。
- **机器资源很紧张**。官方示例里应用容器限了 4G 内存、数据库容器限了 16G，资源明显低于这个量级要重新做容量规划。
- **只想要一个纯语音/视频会议系统**。它的重心是团队协作与消息，不是专业会议产品。

## 安装

**方式一：Docker Compose（官方推荐的容器化路径，仅 Linux 正式支持）**

前置：Docker Engine 与 Docker Compose（官方要求 Compose release 1.28 或更高）。

```bash
# 1. 克隆官方部署仓库并进入目录
git clone https://github.com/mattermost/docker
cd docker

# 2. 用示例文件生成 .env，然后修改（至少必须改 DOMAIN）
cp env.example .env

# 3. 建好数据目录并设置属主——应用容器内的 uid/gid 是 2000
mkdir -p ./volumes/app/mattermost/{config,data,logs,plugins,client/plugins,bleve-indexes}
sudo chown -R 2000:2000 ./volumes/app/mattermost

# 4a. 不带 NGINX 部署：访问 http://<你的域名>:8065/
docker compose -f docker-compose.yml -f docker-compose.without-nginx.yml up -d

# 4b. 带官方 NGINX 部署：访问 https://<你的域名>/
docker compose -f docker-compose.yml -f docker-compose.nginx.yml up -d
```

**方式二：Docker Preview 镜像（单机试用，官方明确不可用于生产）**

```bash
docker run --name mattermost-preview -d --publish 8065:8065 --publish 8443:8443 mattermost/mattermost-preview
```

之后访问 `http://localhost:8065/`。它是一个自带数据库的自包含镜像，开箱即用；官方同时列出了它的限制：使用已知密码、邮件功能关闭、数据不持久（全在容器内）、不支持升级。

**方式三：其它部署形态**

官方部署文档还提供 tar 包、Linux 发行版安装包、Kubernetes 与 Helm 等路径；需要高可用时官方建议走 Kubernetes。具体命令以官方部署文档对应页面为准。

> 官方另外说明：容器镜像还提供 FIPS / STIG 加固变体，切换镜像标签即可使用。

## 常用操作

**1. 改 .env 里必须改的几项**

`env.example` 里给出的关键变量（示例值随仓库更新，**以文件当前内容为准**）：

```ini
DOMAIN=mm.example.com                     # 至少必须改成你自己的域名
MM_SERVICESETTINGS_SITEURL=https://${DOMAIN}
APP_PORT=8065                             # 不带 NGINX 时的访问端口
POSTGRES_USER=mmuser
POSTGRES_PASSWORD=mmuser_password
MATTERMOST_IMAGE=mattermost-enterprise-edition
MATTERMOST_IMAGE_TAG=11.7.0
```

`MM_SQLSETTINGS_DRIVERNAME=postgres` 与 `MM_SQLSETTINGS_DATASOURCE` 指向数据库连接串（示例用 `${POSTGRES_USER}`/`${POSTGRES_PASSWORD}` 拼装）。

**2. 起停与看日志**

```bash
docker compose -f docker-compose.yml -f docker-compose.without-nginx.yml up -d
docker compose -f docker-compose.yml -f docker-compose.without-nginx.yml down
docker compose logs -f
```

**3.（可选）用脚本签发证书，供官方 NGINX 使用**

```bash
bash scripts/issue-certificate.sh -d <YOUR_MM_DOMAIN> -o ${PWD}/certs
```

签发完成后，在 `.env` 里取消注释并指到对应文件：

```ini
CERT_PATH=./certs/etc/letsencrypt/live/${DOMAIN}/fullchain.pem
KEY_PATH=./certs/etc/letsencrypt/live/${DOMAIN}/privkey.pem
```

如果是已有证书，官方给的做法是把它们拷进 `./volumes/web/cert/`，命名为 `cert.pem` 与 `key-no-password.pem`，再把 `CERT_PATH` / `KEY_PATH` 指过去。

**4. 进容器排查**

```bash
# 试点镜像为例
docker exec -ti mattermost-preview /bin/bash
```

**5. 升级到新版本**

方式 A（容器化部署）：停掉部署 → `git pull` 并留意 `env.example` 是否变化 → 修改 `.env` 里的 `MATTERMOST_IMAGE_TAG` → 重新 `up -d`。官方强调：**生产环境建议用具体版本标签（例如 `release-10.5`），不要用 `release-10` 这类浮动标签**，浮动标签面向开发用途，不会自动跟进该主版本下的补丁。

方式 B（试用镜像）：拉新镜像 → 停容器 → 删容器 → 重新 `docker run`。

```bash
docker pull mattermost/mattermost-preview
docker stop mattermost-preview
docker rm mattermost-preview
```

**6. 用 NGINX 反代（官方给出的基本示例）**

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    location / {
        proxy_pass http://mattermost:8065;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

官方建议改完先用 `nginx -t` 校验配置再应用。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 容器反复重启、日志报权限拒绝 | 数据目录属主不对。应用容器内 uid/gid 是 `2000`，NGINX 容器内是 `101` | 按官方步骤 `sudo chown -R 2000:2000 ./volumes/app/mattermost`；需要时对 NGINX 目录做 `101:101` |
| 站点里的链接、邀请邮件地址全指向错误域名 | `.env` 里的 `DOMAIN` 没改，而 `MM_SERVICESETTINGS_SITEURL` 是基于它拼的 | 部署前先把 `DOMAIN` 改成真实域名；SITEURL 也一并确认 |
| 在系统控制台改了设置却不生效、选项还是灰的 | 这些项被 `.env` 里的环境变量接管了，**环境变量优先级高于 config.json**，覆盖了包括控制台在内的设置 | 要改就去改 `.env` 并重启；用环境变量管理的项在控制台里本就不可编辑 |
| 用 Preview 镜像跑正式团队 | 官方明确列出：已知密码、邮件关闭、数据不持久、不支持升级 | Preview 只用来试用；正式环境用 Docker Compose 部署路径 |
| 想做多节点/高可用却用 Docker Compose 硬撑 | 官方说明 Docker 方式不支持开箱的集群与高可用，缺少自动故障转移、共享存储与负载均衡 | 需要 HA 时按官方建议转向 Kubernetes 部署 |
| 在 macOS / Windows 上正式部署 | 官方只支持 Linux 上的 Docker 部署，另两个系统仅限测试与开发 | 正式环境换 Linux 主机；本地只用来验证 |
| 在 Apple 芯片的 Mac 上按文档 `chown` 后反而起不来 | 官方给出的处置就是重做建目录步骤并**跳过** `sudo chown -R 2000:2000` | 按官方 troubleshooting 处理；本地测试环境可以跳过该命令 |
| 生产环境用了浮动镜像标签，补丁没跟上 | 官方说明 `release-x` 这类通用标签面向开发，不会自动接收该主版本下的新补丁版本 | 生产改成具体版本标签，例如 `MATTERMOST_IMAGE_TAG=release-10.5` |
| 清空部署时把数据一起删了 | 数据在 `./volumes` 下，官方清理命令是 `sudo rm -rf ./volumes` | 执行前先备份；日常也不要随手删这个目录 |
| 接自签名证书的 SSO 时报证书不受信任 | 容器内没有该 CA 的信任链，典型报错是 `certificate signed by unknown authority` | 按官方做法把对方 PKI 链文件挂进容器，并在 `docker-compose.yml` 里取消对应注释行 |
| 高负载下容器不稳定 | 自定义 Compose 里用了较低的 `pids_limit`，限制了线程/进程创建 | 官方建议改用 `mem_limit` 约束资源；仓库默认应用容器为 `mem_limit: 4G` |
| 语音通话连不上 | 通话相关端口没开或未走 HTTPS | 关注 `CALLS_PORT`（默认 `8443`）与官方通话部署文档的网络要求；对外使用建议 HTTPS |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取镜像与仓库；对外提供 Web 服务、WebSocket 与通话端口；推送通知、Webhook 与外部集成需要出网 |
| 读取文件 | 是 | 读取 `.env` 配置、TLS 证书与私钥、NGINX 配置；容器启动时读取挂载出来的配置目录 |
| 写入文件 | 是 | 写入 `./volumes` 下的配置、数据、日志、插件与搜索索引；用户上传的附件也落在数据目录 |
| 凭证 | 是 | 数据库账号密码、管理员账号，以及 SSO / 邮件 / 推送等第三方凭据。**本 Skill 不内嵌任何密钥**；`.env` 里的默认密码必须在部署时替换 |
| 子进程 / 后台常驻 | 是 | 以常驻容器形式运行（应用 + 数据库，可选 NGINX 共三个容器）；建议设置 `RESTART_POLICY` 让容器随主机重启 |

## 触发场景

- 「帮我搭一个自己的团队聊天工具」
- 「聊天记录要存在公司自己的服务器上」
- 「用 Docker Compose 部署 Mattermost」
- 「要把告警推到聊天频道里」
- 「要能语音通话和屏幕共享」
- 「容器一直重启 / 域名不对，帮我排查」

## 能力边界

**覆盖**：

- 团队沟通：频道（公开/私有）、私聊、群组消息、线程回复、文件共享、全文搜索与历史归档。
- 富媒体与实时能力：语音通话、屏幕共享，以及配套的通话服务部署路径。
- 扩展与集成：完整的 API、Webhook（入站/出站）、斜杠命令、插件、Apps 等扩展方式。
- 工作流自动化：把消息与外部动作串起来，用于事件响应、工单流转这类场景。
- 客户端覆盖：Web 界面，以及桌面端与移动端应用。
- 部署形态：容器化（Compose + 可选 NGINX）、tar 包、Linux 发行版安装包，以及 Kubernetes / Helm。
- 企业向能力：SSO 对接、加固镜像变体（FIPS / STIG）、合规相关构建。
- 数据侧：官方容器镜像支持 PostgreSQL 数据库（官方说明支持 v11+ 及以上）。

**不覆盖**：

- 不替你做备份、监控与灾备：这些需要自己规划（官方另有备份与恢复、故障排查文档）。
- 不提供开箱即用的高可用集群：Docker 方式不支持集群与 HA，需要走 Kubernetes。
- 不提供模型能力；AI 集成属于通过扩展方式接入外部服务，不是本平台自带。
- 不保证 macOS / Windows 上 Docker 部署的可用性——官方将这两个系统限定为测试与开发用途。
- 不提供托管服务、账号或证书；域名、TLS 证书与邮件通道都要自备。

## 依赖条件

- 操作系统：Docker 部署正式支持 Linux；macOS / Windows 仅限测试与开发。
- Docker Engine 与 Docker Compose（官方要求 Compose release 1.28 或更高）。
- 数据库：PostgreSQL（官方镜像支持，官方说明支持 v11+ 及以上）。
- 磁盘：`./volumes` 下要容纳数据库数据、附件、日志与搜索索引，需提前规划容量与备份。
- 网络：至少开放 Web 端口（不带 NGINX 时默认 `8065`；带 NGINX 时为 `80`/`443`），通话功能还需 `8443` 及相应网络要求。
- 可选：域名与 TLS 证书（对外提供 HTTPS 时必需）、SMTP 邮件通道（邀请与通知）。
- 资源：官方 Compose 默认给应用容器 `mem_limit: 4G`、数据库容器 `16G`，并启用只读根文件系统与 `no-new-privileges`。

## 已知限制

- 官方明确说明 Docker 部署方式**不应作为生产环境方案**的替代：它不支持开箱的集群部署与高可用，缺少自动故障转移、共享存储与负载均衡。
- Preview 试用镜像存在已知密码、邮件关闭、数据不持久、不支持升级等限制，绝不可用于生产。
- 环境变量优先级高于 `config.json`：被环境变量接管的设置项在系统控制台里会变灰且不可修改，排查设置「改了没生效」时要先想到这一层。
- 目录属主必须与容器内 uid/gid 对齐（应用 `2000`、NGINX `101`），否则会出现难以定位的权限问题。
- 数据库连接串、镜像标签等关键值集中在 `.env`，升级时官方提示要留意 `env.example` 的变化，容易漏改。
- 上游说明按月发布新编译版本，具体版本号、发布节奏与镜像标签请以仓库与官方文档的实时信息为准，本 Skill 不做断言。

## 自检清单

- [ ] 部署主机是 Linux（或已确认此部署只用于测试开发）。
- [ ] Docker Compose 版本满足官方要求（1.28 或更高）。
- [ ] `.env` 里的 `DOMAIN` 已改成真实域名，`MM_SERVICESETTINGS_SITEURL` 与之匹配。
- [ ] `.env` 里的数据库账号密码已替换默认值。
- [ ] 数据目录已创建，且属主为 `2000:2000`（NGINX 目录按需为 `101:101`）。
- [ ] 已确认用的是「带 NGINX」还是「不带 NGINX」的 Compose 组合，并对应正确的访问地址与端口。
- [ ] 生产环境使用的是**具体版本标签**，而不是 `release-x` 这类浮动标签。
- [ ] TLS 证书路径正确（`CERT_PATH` / `KEY_PATH`），改完 NGINX 配置执行过 `nginx -t`。
- [ ] 已创建首个系统管理员账号，并按需关闭开放注册。
- [ ] 备份与升级流程已验证：知道数据在 `./volumes`，也知道升级要先停服务再改镜像标签。
- [ ] 需要高可用时，方案是 Kubernetes 而不是把 Docker Compose 横向堆叠。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/mattermost/mattermost | 上游仓库（安装与完整文档以它为准） |
| https://github.com/mattermost/docker | 官方容器化部署仓库（Compose 文件、`env.example`、证书脚本的出处） |
| https://docs.mattermost.com/deployment-guide/server/deploy-containers | 官方容器部署文档（部署步骤、试用镜像、故障排查与安全建议） |

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
