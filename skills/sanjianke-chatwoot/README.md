# 三剪客 · 自托管多渠道客服工作台 Skill

客户消息散在网页聊天、客服邮箱和社交平台私信里，客服靠切窗口硬扛——这个 Skill 带你用 Chatwoot 把它们收进一个自己托管的收件箱，并跑通部署、运维与自动化。

---

## 前置条件

- 一台 Linux 服务器（官方支持 Ubuntu 20.04 一类环境），官方最低口径 4 核 / 4GB 内存，并建议加至少 1GB swap。
- 已装 Docker 与 Compose（官方建议不低于 `Docker 20.10.10`、`Docker Compose v2.14.1`）。
- 一个域名，以及愿意自己配反向代理与 HTTPS 证书。
- 一套可用的 SMTP（否则注册确认、密码重置、邮件渠道都发不出去）。
- 要接社交平台 / Telegram 等渠道时，需先拿到对应平台的开发者应用与密钥。

---

## 使用

1. 按 `SKILL.md` 的「安装」一节拉取官方 `.env` 与 compose 模板，改好 `SECRET_KEY_BASE`、`FRONTEND_URL`、数据库与 Redis 密码。
2. 用 `db:chatwoot_prepare` 初始化数据库，`docker compose up -d` 起服务，`curl -I localhost:3000/api` 验活。
3. 套上反向代理（别忘 `underscores_in_headers on;`）并签发证书，浏览器打开域名走完首次引导。
4. 之后按「常用操作」里的 CLI、HTTP API 与 Rails 控制台做日常处理、排障与升级。
5. 出问题先看「常见坑」表，多数事故（初始化方式、代理丢头、平台接口 401、SMTP 缺失）都在里面。

---

## 依赖

- Docker 与 Docker Compose。
- PostgreSQL（官方只支持这一种数据库；compose 模板用 pgvector 版 pg16 镜像）。
- Redis（建议 7.0 以上）。
- 常驻的 Web 进程与后台任务进程（由 compose 编排）。
- 反向代理（Nginx 或同类）与 TLS 证书。
- 可选：S3 兼容对象存储（MinIO、云厂商对象存储等）用于存放附件。
- 可选：官方 CLI（macOS / Linux 一键脚本或 Go 源码安装）用于终端操作与脚本化。

---

## 安全

- 不内嵌任何密钥；数据库密码、Redis 密码、`SECRET_KEY_BASE`、SMTP 与渠道密钥都由使用者自行生成与保管。
- `SECRET_KEY_BASE` 一旦更换会让所有已登录会话失效，请首次部署就固定并留档。
- compose 模板默认把 Web、数据库、Redis 都绑在 `127.0.0.1`，这是有意的安全默认值；不要为了省事直接暴露到公网。
- 反向代理要保留带下划线的请求头（`underscores_in_headers on;`），否则 API 认证会失败。
- 首次部署后建议立刻关闭开放注册（`ENABLE_ACCOUNT_SIGNUP=false`），并只给必要的人开超级管理员。
- 附件、数据库卷与 `.env` 都要纳入备份；升级前必须先备份。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Chatwoot`
- 仓库：https://github.com/chatwoot/chatwoot

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
