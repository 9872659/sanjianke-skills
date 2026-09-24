# 三剪客 · 数据接入与索引 Skill

把散落的文档、数据库、API 接成可检索、可问答的知识库；覆盖装包、模型与嵌入配置、索引构建与持久化、换本地模型与常见坑。

---

## 前置条件

- Python >= 3.10（各集成包的 `requires-python` 为 `>=3.10,<4.0`），建议独立虚拟环境。
- 一个模型服务的访问方式：云厂商 API Key，或本地服务（如 Ollama）。
- 一个嵌入模型：可用云厂商嵌入接口，或用 `llama-index-embeddings-huggingface` 在本地跑。
- 若要长期使用：一个外部向量库（索引不落盘、量大了内存存储吃不消）。
- 首次运行需要联网下载模型/tokenizer 权重与缓存。

---

## 使用

本 Skill 按「装包 → 配模型 → 建索引 → 落盘 → 查询 → 换后端」的顺序组织：

1. 装包：快速上手用 `llama-index`，长期项目用 `llama-index-core` 加按需集成包。
2. 配模型：默认用环境变量里的 API Key；换本地模型时同时设置 `Settings.llm`、`Settings.tokenizer`、`Settings.embed_model`。
3. 接入数据：`SimpleDirectoryReader` 读目录，其它来源用对应集成包的读取器。
4. 建索引：`VectorStoreIndex.from_documents(...)`。
5. 落盘：`index.storage_context.persist()`，下次用 `load_index_from_storage()` 加载。
6. 查询：`index.as_query_engine().query(...)`；需要多步骤逻辑时改走工作流编排。

导入路径规则是这一层最容易出错的地方：带 `core` 的是核心包，不带 `core` 的是某个集成包。

---

## 依赖

- Python >= 3.10。
- 至少一个 LLM 集成包与一个嵌入集成包。
- 可写目录用于索引持久化（默认 `./storage`）与模型缓存。
- 外部向量库（可选，但生产环境基本必需）。
- 版本约束：集成包会锁定 `llama-index-core` 的区间，升级核心前要核对。

---

## 安全

- 不内嵌任何密钥
- API Key 通过环境变量注入，不要写进代码、notebook 输出或版本库。
- 读取器会遍历你指定目录下的文件；只把需要的目录交给它，避免误读敏感路径。
- 索引持久化目录里保存的是原文切片的向量与文本，属于数据资产，需要按敏感数据管理并备份。
- 用外部向量库时注意连接凭证与网络暴露面。
- 离线或受限网络环境下，模型下载步骤需要提前规划。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LlamaIndex`
- 仓库：https://github.com/run-llama/llama_index

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
