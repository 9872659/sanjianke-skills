# 三剪客 · 开源预约排期系统 Skill

在自己服务器上搭一套预约排期系统的落地指引，含部署、环境变量、集成配置与常见报错定位。

---

## 前置条件

- Node.js **>= 18.x**（上游给出的下限）、PostgreSQL **>= 13.x**、Yarn。
- Docker 与 Docker Compose：走容器部署或内置快速启动时需要。
- 一个可被外网访问的域名与 HTTPS：要接第三方日历 / 会议服务的 OAuth 回调就必须有。
- 三个必备配置项：
  - `DATABASE_URL`：PostgreSQL 连接串；
  - `NEXTAUTH_SECRET`：用 `openssl rand -base64 32` 生成；
  - `CALENDSO_ENCRYPTION_KEY`：用 `openssl rand -base64 24` 生成。
- 心理准备：这是社区维护的自托管版本，上游**严格建议用于个人、非生产场景**，需要数据库管理与服务器运维经验。

---

## 使用

按部署形态选路径，不要混用命令。

1. **想最快看到界面** → Docker Compose：
   ```bash
   git clone --recursive https://github.com/calcom/cal.diy.git
   cd cal.diy && cp .env.example .env
   # 生成并填入 NEXTAUTH_SECRET、CALENDSO_ENCRYPTION_KEY
   docker compose up -d
   ```
   打开 `http://localhost:3000` 走安装向导。
2. **要改代码或调试** → 源码模式：`yarn` → 配 `.env` → `yarn workspace @calcom/prisma db-migrate` → `yarn dev`。
3. **要省掉手工配库** → `yarn dx`，需要 Docker，会起本地 Postgres 并创建测试账号（密码在控制台输出）。
4. **建首个 / 补充用户** → `yarn db-studio` 手工加记录，或 `cd packages/prisma && yarn db-seed` 播种测试数据。
5. **要接入日历或会议服务** → 在对应服务商控制台创建 OAuth 客户端，回调地址填 `<你的URL>/api/integrations/<集成名>/callback`，凭据写进 `.env`，然后 `yarn seed-app-store` 刷新应用项。
6. **要升级** → `docker compose down` → `docker compose pull` → `docker compose up -d`；源码模式则 `git pull` → `yarn` → `yarn predev` → `db-deploy` → `yarn build && yarn start`。

完整的命令参数与排错对照写在 `SKILL.md` 的「安装」「常用操作」「常见坑」三节。

---

## 依赖

- 运行时：Node.js >= 18.x、PostgreSQL >= 13.x。
- 包管理与构建：Yarn；构建期需要数据库可用。
- 容器：Docker 与 Docker Compose（`docker compose` 无连字符写法）。
- 可选外部服务：Google 日历、Microsoft 365、Zoom、Daily、HubSpot / Zoho / Pipedrive 等，各自的 OAuth 凭据在服务商侧申请。
- 可选限流服务：Unkey（不配置也能正常运行）。
- 推送通知需要 VAPID 密钥对，用 `npx web-push generate-vapid-keys` 生成。

---

## 安全

- 不内嵌任何密钥。
- `NEXTAUTH_SECRET` 与 `CALENDSO_ENCRYPTION_KEY` 必须自行生成，**不要在生产环境沿用示例里的默认值**，那是明确的安全风险。
- `.env` 不要提交到版本库；`.env.example` 里只放占位符。
- 第三方集成凭据（日历、会议、CRM 的客户端密钥）属于敏感信息，按最小权限申请，并只写进本地 `.env`。
- 上游提到的 `NODE_TLS_REJECT_UNAUTHORIZED=0` 是关闭证书校验的应急开关，会降低整体安全等级，仅在完全清楚链路并信任该负载均衡时使用；优先修好证书链。
- 自托管意味着数据库、备份与访问控制都由使用者负责；数据库里存的是客户姓名、邮箱与预约记录。
- 社区版不含 SSO / 组织权限体系，若把管理权限开放给多人，需要自行控制。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Cal.com`
- 仓库：https://github.com/calcom/cal.diy

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
