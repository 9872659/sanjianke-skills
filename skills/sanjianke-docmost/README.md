# 三剪客 · 团队知识库与文档协作 Skill

Docmost 的安装（Docker Compose / 源码开发）、核心环境变量、空间与权限模型、导入导出与 API / MCP 接入，以及 APP_SECRET 不改就起不来、反代没开 WebSocket 编辑器变只读、附件大小限制、企业版功能边界等高频坑。

---

## 前置条件

- **Docker 路径**：服务器已装 Docker 与 Docker Compose
- **源码路径**：Node.js ≥ 22、Postgres ≥ 16、Redis 或 Valkey ≥ 7；pnpm 需全局安装（`npm install -g pnpm`）
- 一个可访问的域名（`APP_URL`），生产环境建议置于支持 WebSocket 的反向代理之后
- 一枚 ≥32 字符的应用密钥（`openssl rand -hex 32` 生成），以及自定的数据库强口令
- 需要邮件邀请成员时，准备可用的 SMTP 或 Postmark 账号
- 若要使用 API、AI、SSO、Bases、MCP 等能力，需有效的企业版授权

---

## 使用

本 Skill 面向「让 Agent 会装、会用、知道什么时候不该用」，正文覆盖：

1. **什么时候用 / 不用**——什么团队适合自托管知识库，什么时候该换静态文档站、任务系统或 SaaS
2. **安装**——Docker Compose 官方流程（三容器构成、必改配置）与源码开发流程（含手动迁移命令）
3. **常用操作**——升级、停止重启、健康检查、切 S3 存储、配邮件、调体积上限、API Key 与 MCP 接入
4. **常见坑**——`APP_SECRET` 不改起不来、WebSocket 没开编辑器变只读、`APP_URL` 致邮件链接错误、附件上限与反代双重限制、开发模式漏跑迁移、编辑器扩展包未构建、Draw.io 地址、iframe 嵌入、版本功能边界、内网 AI 与附件备份
5. **能力边界**——逐项区分社区版能用与企业版才有；以及它不做的事（任务管理、网盘、静态站点发布）

最短上手路径：

```bash
mkdir docmost && cd docmost
curl -O https://raw.githubusercontent.com/docmost/docmost/main/docker-compose.yml
# 改 APP_URL / APP_SECRET / POSTGRES_PASSWORD / DATABASE_URL
docker compose up -d
```

之后访问 `http://localhost:3000`（或你的域名）完成工作区初始化。

---

## 依赖

- Docker 与 Docker Compose；官方 compose 使用 `docmost/docmost:latest`、`postgres:18`、`redis:8`
- 源码路径额外需要：Node.js ≥ 22、Postgres ≥ 16、Redis/Valkey ≥ 7、pnpm、nx（仓库内置）
- 必需环境变量：`APP_SECRET`、`DATABASE_URL`、`REDIS_URL`；`APP_URL` 官方标注可选但影响邮件链接
- 反向代理必须支持 WebSocket，否则实时编辑不可用
- 可选外部依赖：SMTP / Postmark、S3 兼容存储（AWS S3 / MinIO / Wasabi / Backblaze / Spaces）、Azure Blob、Typesense（企业版）、AI 模型服务（OpenAI / openai-compatible / Gemini / Ollama，企业版）
- 企业版功能需要授权 Key

---

## 安全

- 不内嵌任何密钥；所有密钥、口令、Token 均通过环境变量或应用内设置传入
- `APP_SECRET` 必须替换成自生成的随机值（≥32 字符），官方明确留默认值会导致启动失败
- 数据库口令不要沿用模板里的示例值，且 `POSTGRES_PASSWORD` 与 `DATABASE_URL` 必须一致
- 个人 API Key 只在创建时显示一次，务必立即妥善保存；不同用户各自创建，权限随之走
- 默认只允许同源 iframe（`X-Frame-Options: SAMEORIGIN`）以防点击劫持；开放 `IFRAME_EMBED_ALLOWED` 时务必配 `IFRAME_ALLOWED_ORIGINS` 白名单，否则任何站点都能嵌入
- 公开分享页（`/share/...`）默认就可被任意来源嵌入，分享前确认内容确实适合公开
- 附件默认落在容器数据卷内，备份必须同时覆盖数据库与应用存储；改用外部对象存储时同样要备份
- MCP 与 API 沿用网页权限模型，但凭据一旦泄露就等于该账号的全部可见范围，请按账号最小权限发放
- 内网 / 气隙部署时留意图表、AI 等外部依赖是否可用，避免内容渲染或翻译资源被外部请求泄露

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Docmost`
- 仓库：https://github.com/docmost/docmost

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
