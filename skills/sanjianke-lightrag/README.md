# 三剪客 · 轻量图谱 RAG Skill

在向量检索之外再建一层知识图谱，用双层级检索回答跨文档、跨段落的关系型问题。

---

## 前置条件

- Python 3.10。
- 一个抽取能力足够的 LLM：官方建议至少 32B 参数、32KB 上下文（64KB 更佳），且索引阶段避免推理型模型。
- 一个 Embedding 模型，索引与查询必须一致；建议本地部署。
- 可选但强烈建议的 Rerank 模型。
- 生产环境需要持久化存储后端（PostgreSQL 为官方推荐）。
- 服务器模式的鉴权配置：`LIGHTRAG_API_KEY` 或 `AUTH_ACCOUNTS` + `TOKEN_SECRET`。

---

## 使用

1. 按 `SKILL.md`「安装」装 `lightrag-hku[api]` 并准备 `.env`。
2. 服务器用法：`lightrag-server` 起服务，访问 `/webui`（管理）或 `/workspace`（查询）。
3. SDK 用法：按「常用操作 1」的模板写，别忘 `await rag.initialize_storages()`。
4. 按问题类型选查询模式：细节用 `local`，全局关系用 `global`，要最全用 `mix`。
5. 遇到超时、内存、嵌入维度等问题，对照 `SKILL.md`「常见坑」表排查。

---

## 依赖

- `lightrag-hku`（服务器加 `[api]` extra）。
- LLM / Embedding / Rerank / VLM 服务（云端 API 或本地部署）。
- 生产级存储：PostgreSQL（推荐）、MongoDB、OpenSearch，或专业向量库与图库。
- 可选系统库 `libcairo`（仅处理含内嵌 SVG 的 markdown / textpack 时需要）。
- Docker（走 Compose 部署时）。

---

## 安全

- 不内嵌任何密钥；LLM / Embedding 的 Key 与 `LIGHTRAG_API_KEY` 一律放 `.env` 或环境变量。
- **服务器默认绑 `0.0.0.0` 且默认无鉴权**：对外暴露前必须配鉴权，或改为只绑 `127.0.0.1`。Ollama 兼容的 `/api/*` 路由默认仍开放，需要一并保护就设 `WHITELIST_PATHS=/health`。
- WebUI 有两个入口，隐藏管理界面只是体验上的区分，**不是权限边界**；真正的权限由服务端接口鉴权决定。
- 删除操作不可逆：按文档删除会重建受影响的图谱内容，执行前备份。
- LLM 缓存与检查数据落在 `WORKING_DIR`，其中含原始文本与抽取结果，属敏感数据，注意目录权限与备份策略。
- 文件型图谱后端为单写者模型，不要并发调用其管理写接口，否则可能丢数据。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LightRAG`
- 仓库：https://github.com/HKUDS/LightRAG

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
