# 三剪客 · 自托管团队协作沟通平台 Skill

一个自托管的团队协作平台：频道聊天、线程讨论、语音通话与屏幕共享、工作流自动化，还能通过 Webhook、斜杠命令和插件接自家系统。

---

## 前置条件

- 一台 Linux 主机（官方只对 Linux 上的 Docker 部署提供支持；macOS / Windows 仅限测试开发）。
- Docker Engine 与 Docker Compose（官方要求 Compose release 1.28 或更高）。
- 一个 PostgreSQL 数据库实例（可用官方 Compose 里的数据库容器，也可用外部实例）。
- 一个域名；对外提供 HTTPS 时需要 TLS 证书。
- 规划好 `./volumes` 所在磁盘的容量与备份策略。
- 需要语音通话时，按官方网络要求准备 `8443` 等端口。

---

## 使用

1. 克隆官方容器化部署仓库并进入目录。
2. `cp env.example .env`，至少把 `DOMAIN` 改成自己的域名，并替换数据库默认密码。
3. 创建 `./volumes/app/mattermost` 下的各子目录，并把属主设为 `2000:2000`（应用容器内的 uid/gid）。
4. 选择部署组合：`docker compose -f docker-compose.yml -f docker-compose.without-nginx.yml up -d`（不带 NGINX，访问 `http://<域名>:8065/`），或加上 `docker-compose.nginx.yml`（带 NGINX，走 `https://<域名>/`）。
5. 创建首个系统管理员账号，按需关闭开放注册，再邀请成员。
6. 升级：停服务 → `git pull` → 改 `.env` 里的镜像标签（生产用具体版本标签）→ 重新 `up -d`。

完整的六块操作说明（什么时候用 / 不用、安装、常用操作、常见坑、权限与用途说明、能力边界）见 `SKILL.md`。

---

## 依赖

- 操作系统：Linux（容器化部署的正式支持范围）。
- Docker Engine + Docker Compose 1.28 或更高。
- 数据库：PostgreSQL（官方容器镜像支持，官方说明支持 v11+ 及以上）。
- 反向代理：可选，官方部署仓库自带 NGINX 组合与证书脚本。
- 资源：官方 Compose 默认给应用容器 `mem_limit: 4G`、数据库容器 `16G`，并启用只读根文件系统与 `no-new-privileges`。
- 可选：SMTP 邮件通道（邀请与通知）、SSO 身份提供方、对象存储与推送服务等按需接入。

---

## 安全

- 不内嵌任何密钥。数据库密码、管理员账号、邮件与 SSO 凭据都由使用方自行生成与保管。
- `env.example` 里的数据库账号密码是**示例值**，部署时必须替换，不要沿用示例密码。
- `.env` 会集中保存数据库密码与证书路径，务必限制文件权限，不要提交到公开仓库。
- 端口与目录按最小必要开放；应用容器与数据库容器的数据目录不要暴露给无关用户。
- TLS 私钥单独存放并限制权限，官方建议不要把私钥打进镜像里。
- 官方给出的容器安全建议包括：启用 `no-new-privileges`、避免 `--privileged`、使用可信镜像、定期更新镜像与 Docker 本体、按需配置限流与防火墙。
- 使用官方提供的**试用镜像**时请注意：它使用已知密码、关闭邮件、数据不持久且不支持升级，只能用于本机试用。
- 上游软件自身的漏洞与安全问题请走上游仓库的 Issues 与安全公告渠道。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Mattermost`
- 仓库：https://github.com/mattermost/mattermost

---

## 许可证

MIT，见 `LICENSE.md`。

---

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
