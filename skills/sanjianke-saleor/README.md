# 三剪客 · GraphQL 原生电商后端平台 Skill

saleor：GraphQL 原生电商后端平台 的安装、常用命令与避坑要点

---

## 前置条件

- 走推荐的本地环境：装好 **Docker** 与 **Docker Compose**，并给 Docker 至少分配 **5 GB 内存**。
- Windows / macOS 上必须把克隆下来的项目目录加入 Docker 的文件共享列表（File sharing / Shared Drives），否则热重载与挂载会报错。
- 走非容器方式：**Python 3.12**（项目要求 `>=3.12,<3.13`）、PostgreSQL、Redis，以及系统编译依赖。
- 想用云端方案：先有一个开发者账号；命令行工具需要 Node.js 环境。
- 生产部署另需外部数据库、对象存储与真实域名；邮件、支付等外部服务要各自准备凭据。

---

## 使用

最短路径（本地全套：API + 面板 + 邮件调试）：

```bash
git clone https://github.com/saleor/saleor-platform.git
cd saleor-platform
docker compose pull
docker compose run --rm api python3 manage.py migrate
docker compose run --rm api python3 manage.py populatedb --createsuperuser
docker compose up
```

起来后：API `http://localhost:8000`、面板 `http://localhost:9000`、邮件调试 `http://localhost:8025`。默认管理员账号是 `admin@example.com`，示例数据把密码设成了 `admin`，对外可达前必须改掉。

云端最短路径：

```bash
npm i -g @saleor/cli
saleor register
```

常用命令、接口调用示例与排障顺序见 `SKILL.md`。

---

## 依赖

- Docker + Docker Compose（本地环境），或 Python 3.12 + PostgreSQL + Redis（非容器方式）。
- 三件套要版本对齐：API、管理面板、店面各自是独立项目，需用同一条 3.x 版本线。
- 本地环境附带邮件调试与链路追踪组件，属于开发期工具，不是上线依赖。
- 生产环境按官方自托管文档配置环境变量；媒体文件建议放对象存储而不是容器本地。

---

## 安全

- 不内嵌任何密钥；数据库密码、应用密钥、支付与邮件凭据全部走环境变量。
- 默认管理员密码是公开的（`admin`），任何对外可达的环境都必须先改。
- 本地那套编排只是开发环境，不要直接暴露到公网或当作生产部署。
- 生产务必为 GraphQL 接口配置限流与查询复杂度限制，避免被恶意查询拖垮。
- 数据库卷、媒体文件与备份文件都可能含客户个人信息，注意访问控制与留存期限。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`saleor`
- 仓库：https://github.com/saleor/saleor

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
