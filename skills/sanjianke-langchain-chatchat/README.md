# 三剪客 · 本地知识库问答 Skill

全程用开源模型、可离线私有部署的知识库问答应用：文件入库、向量检索、Agent 调工具，带 WebUI 与 FastAPI 双入口。

---

## 前置条件

- Python 3.8–3.11（Windows / macOS / Linux 均可用）。
- **一个独立运行的模型推理框架**，并已加载 LLM 与 Embedding 模型（Xinference / Ollama / LocalAI / FastChat / One API 之一）。
- 建议为推理框架与本项目各建一个虚拟环境，避免依赖冲突。
- 建库需要足够的磁盘空间；Docker 部署需要本机 Docker。

---

## 使用

1. `pip install langchain-chatchat -U` 装本体。
2. 在**另一个**虚拟环境里起模型推理框架并加载模型。
3. 按需设置 `CHATCHAT_ROOT`，然后跑 `chatchat init` 生成配置与数据目录。
4. 改 `model_settings.yaml`（模型与平台地址）、按需改 `basic_settings.yaml` 与 `kb_settings.yaml`。
5. `chatchat kb -r` 初始化知识库，成功会打印文件数与知识条目统计。
6. `chatchat start -a` 启动 API 与 WebUI。
7. 出问题先查 `SKILL.md`「常见坑」表，`chatchat kb --help` 与 `chatchat start --help` 是查参数的第一入口。

---

## 依赖

- `langchain-chatchat`（配 Xinference 时用 `langchain-chatchat[xinference]`）。
- 外部模型推理框架及其加载的 LLM / Embedding 模型（可选 Reranker、多模态模型）。
- 向量库：默认 FAISS，可通过 `kb_settings.yaml` 更换。
- 元数据库：默认 SQLite，可换成其他数据库。
- 可选：Docker 与 docker-compose、搜索引擎 / 数据库的连接凭据（使用对应工具时）。

---

## 安全

- 不内嵌任何密钥；在线 API 与 One API 的 Key 放配置或环境变量，不要提交进仓库。
- 服务默认只监听 `127.0.0.1`；改成 `0.0.0.0` 即对外暴露，请先确认鉴权与访问控制（项目本身不附带完整的企业级权限体系）。
- 知识库中通常含内部资料，`KB_ROOT_PATH`、`info.db` 与向量索引都属敏感数据，注意目录权限与备份。
- 从 0.2.x 迁移前务必备份重要数据——官方说明迁移指南不保证完全兼容。
- Docker 部署建议用 compose 挂载数据卷，不要裸 `docker run` 后直接对外提供服务。
- Agent 启用后模型可自动调用工具（含搜索引擎、数据库等），等于给模型开了这些权限；按最小必要选择可用工具。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Langchain-Chatchat`
- 仓库：https://github.com/chatchat-space/Langchain-Chatchat

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
