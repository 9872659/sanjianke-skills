# 三剪客 · 拖拽式 LLM 编排 Skill

把「模型 + 提示词 + 检索 + 工具」画成流程图，起一个自带界面和 API 的流程服务；覆盖安装、启动、账号鉴权、导出导入、数据持久化与常见坑。

---

## 前置条件

- Node.js >= 20.0.0（官方 README 明确要求）；或本机已装 Docker 与 Docker Compose。
- 一个可长期运行的机器/容器，以及一个可写的数据目录。
- 自备模型服务的 API Key（或本地模型服务地址）；如需知识库检索，还要准备向量库。
- 首次启动后建议立刻配置 `FLOWISE_USERNAME` / `FLOWISE_PASSWORD` 并执行 `flowise user` 建账号。

---

## 使用

本 Skill 按「装 → 起 → 建账号 → 接流程 → 调 API → 迁环境」的顺序组织：

1. 安装：npm 全局、Docker 镜像、Docker Compose、源码开发四选一。
2. 启动：`flowise start`（或 `docker compose up -d`），默认 `http://localhost:3000`。
3. 鉴权：先设置环境变量并重启，再跑 `flowise user`。
4. 编排：在画布上连节点，跑通后为流程打开 API 访问。
5. 调用：`POST /api/v1/prediction/<chatflow-id>`（具体字段以实例上的 `/api-docs` 为准）。
6. 迁移：导出流程 JSON，在目标环境导入，并同步补齐 `.env` 中的密钥配置。

---

## 依赖

- Node.js >= 20.0.0；源码方式额外需要 pnpm 与足够的内存（构建可能触发堆内存不足）。
- Docker / Docker Compose（容器方式）。
- 外部模型服务或本地推理服务的地址与密钥。
- 默认使用内置 SQLite 文件保存数据；生产建议改用 Postgres 等外部数据库。

---

## 安全

- 不内嵌任何密钥
- 默认无强制鉴权，部署到可被公网访问的环境前必须开启账号密码并验证登录拦截。
- 模型与向量库凭证应通过环境变量或界面的凭据管理维护，不要写进流程 JSON 提交到代码库。
- Docker 部署时数据目录必须挂卷，避免容器重建导致数据与流程配置丢失。
- 商用与对外托管场景需先核对上游 `LICENSE.md` 中的附加条款。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Flowise`
- 仓库：https://github.com/FlowiseAI/Flowise

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
