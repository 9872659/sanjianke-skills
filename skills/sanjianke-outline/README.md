# 三剪客 · Outline 团队知识库 Skill

Outline：面向团队的知识库与文档协作服务，自建时用 Docker 起一套，文档全部以 Markdown 存储并可通过 RPC 接口批量读写。

---

## 前置条件

- 先决定用官方托管版还是自建：托管版不需要跑任何代码。
- 自建需要 Docker 与 Docker Compose，以及一个 PostgreSQL 和一个 Redis 实例。
- 必须准备至少一个第三方身份提供方（Slack / Google / Microsoft Entra / Discord / 通用 OIDC 之一），它没有内置账号密码登录。
- 对外提供服务需要一个域名与反向代理 / TLS 证书。
- 附件存储要有持久化卷，或配好 S3 兼容对象存储。
- 自建或商用前先确认许可范围。

---

## 使用

1. 按仓库里的 `.env.sample` 准备 `docker.env`，`URL`、`DATABASE_URL`、`REDIS_URL`、`SECRET_KEY` 是必需项。
2. `SECRET_KEY` 一定要自己生成随机值，不要沿用示例里的占位值。
3. 用官方 compose 骨架起服务：`docker compose up -d`，然后 `docker compose logs -f outline` 看连接类报错。
4. 配好身份提供方并实际登录一次，再建一篇文档、传一张图。
5. 需要程序化写入时用 RPC 风格接口，token 在账号设置里生成；接口清单以官方开发者文档为准。
6. 升级顺序固定：先备份数据库 → 拉新镜像 → 启动容器（数据库迁移默认自动执行）。

---

## 依赖

- Docker 与 Docker Compose。
- PostgreSQL 与 Redis（必需）。
- 至少一个第三方身份提供方账号。
- 域名与反向代理 / TLS（对外暴露时）。
- 任意 HTTP 客户端（调用接口时）。
- 可选：SMTP 账号、S3 兼容对象存储、错误上报服务。

---

## 安全

- 不内嵌任何密钥，数据库密码、`SECRET_KEY`、接口 token 都要在执行时提供。
- `.env` / `docker.env` 必须加进 `.gitignore`，里面是数据库密码和各服务 client secret。
- 不要用示例文件里的占位密钥上线；`SECRET_KEY` 用 `openssl rand -hex 32` 这类方式生成并妥善保存。
- 支持文件式密钥的环境，用变量名加 `_FILE` 后缀从文件读取密钥，避免密钥出现在环境变量列表里。
- 反向代理后面要正确设置客户端 IP 相关头，否则限流会把不同用户算成同一个来源。
- 升级前必须备份数据库；迁移在容器启动时自动执行，出错会影响线上数据。
- 关掉不需要的匿名统计上报（`ENABLE_UPDATES=false`）。
- 自建后不要用 `latest` 裸跑生产，固定版本标签才能控制升级窗口。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Outline`
- 仓库：https://github.com/outline/outline

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
