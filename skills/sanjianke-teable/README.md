# 三剪客 · 多维表格数据库 Skill

Teable 的安装（Docker Compose 与源码开发）、必需环境变量、从表格到 API 的用法、记录增删改查与 Access Token 调用，以及默认密钥不可用于生产、卷被删即丢数据、升级回滚、外键批量更新超时等高频坑。

---

## 前置条件

- **Docker Compose 路径**：装好 Docker 与 Docker Compose；服务器建议 Linux（如 Ubuntu 20.04 LTS）、内存 ≥ 4GB、CPU ≥ 2 核、可用磁盘 ≥ 40GB
- **源码开发路径**：Node.js ≥ 22.0.0、pnpm ≥ 9.13.0（仓库 `engines` 字段），用 `corepack enable` 启用包管理器；仓库对 npm 的提示是 `please-use-pnpm`
- 需要一个 PostgreSQL 实例；Compose 示例自带，源码路径用 `make switch-db-mode` 初始化
- 需要 Redis；Compose 示例自带
- 需要自行生成一批签名与加密密钥，不能沿用默认值

---

## 使用

本 Skill 面向「让 Agent 会装、会用、知道什么时候不该用」，正文覆盖：

1. **什么时候用 / 不用**——什么时候适合自托管多维表格，什么时候该换 SaaS、换业务后端、或干脆用一条命令处理 CSV
2. **安装**——Docker Compose 自托管（含三容器构成）与源码开发两条路径，附版本验证命令
3. **常用操作**——升级、回滚、查迁移日志、用 Access Token 调 REST API 读写记录、生成密钥
4. **常见坑**——密钥缺失不阻塞启动但留安全洞、`PUBLIC_ORIGIN` 漏配、卷删除即丢数据、必须用 pnpm、事务超时、认证配置顺序、附件大小上限、反代信任配置
5. **能力边界**——覆盖的数据模型、视图、协作与 API 范围；精简版不含 AI 与 App Builder 等边界

最短上手路径：`mkdir teable && cd teable`，从仓库 `dockers/examples/standalone/` 取 `docker-compose.yaml` 与 `.env`，改完 `.env` 后 `docker compose up -d`，访问 `http://127.0.0.1:3000`。

---

## 依赖

- Docker 与 Docker Compose（官方脚本：`curl -fsSL https://get.docker.com | bash -s docker`）
- 镜像：Teable 应用、`postgres:15.4`、`redis:7.2.4`
- 源码路径：Node.js ≥ 22、pnpm ≥ 9.13、PostgreSQL
- 必需环境变量：`PUBLIC_ORIGIN`、`SECRET_KEY`、`PRISMA_DATABASE_URL`、`BACKEND_CACHE_REDIS_URI`，以及若干 `BACKEND_*_ENCRYPTION_KEY` / `_IV`
- 可选外部服务：SMTP 邮件、S3 / MinIO / 阿里云 OSS、OAuth / OIDC 身份源、OpenTelemetry
- 调用 API 需要个人 Access Token

---

## 安全

- 不内嵌任何密钥；所有密钥与口令都通过环境变量传入
- **官方明确警告**：密钥类变量缺失时不阻止启动，服务会退回旧版本内置的公开默认值，任何人都能伪造令牌或解密受保护数据；只有本地试用可以接受，其他场景必须自己生成
- 生成强随机值：`openssl rand -base64 32`；加密用的 key / IV 按文档要求为 16 字符随机串
- 数据卷必须做外部备份；官方示例注释也提醒，绑定挂载宿主机目录比命名卷更不容易误删
- 反向代理场景要正确配置 `BACKEND_TRUST_PROXY`，否则审计日志里的来源 IP 不可信
- `.env`、数据库连接串、Access Token 不要提交进仓库、不要贴进工单或聊天记录
- 该平台承载的是业务数据本身，注意数据分类分级与访问权限；`PASSWORD_LOGIN_DISABLED` 之类开关要先把替代登录方式验证通过再打开

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Teable`
- 仓库：https://github.com/teableio/teable

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
