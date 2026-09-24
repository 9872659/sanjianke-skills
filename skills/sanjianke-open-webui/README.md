# 三剪客 · 自托管 AI 对话界面 Skill

自己托管一个能完全离线运行的 AI 对话前端的操作指引

---

## 前置条件

- pip 路径官方建议使用 Python 3.11，避免兼容问题。
- Docker 路径需要本机 Docker；GPU 加速需要 NVIDIA CUDA container toolkit（Linux/WSL）。
- 至少准备一个模型来源：本机或内网的 Ollama 服务，或某个 OpenAI 兼容 API 及其 Key。
- Docker 方式必须挂载 `-v open-webui:/app/backend/data`，否则重启丢数据。
- 离线环境需设置 `HF_HUB_OFFLINE=1`，并预先备好所需模型资源。

---

## 使用

1. 选安装路径：`pip install open-webui` + `open-webui serve`，或直接用官方 Docker 命令。
2. 按路径访问对应端口：pip 是 `http://localhost:8080`，Docker 映射默认是 `http://localhost:3000`。
3. 注册第一个账号（即管理员），随后关闭开放注册。
4. 接入模型后端：Ollama 地址或 OpenAI 兼容 API 与 Key。
5. 需要知识库就上传文档并配置向量数据库。
6. 需要扩展就装插件（过滤器、动作、管道、工具），或用 MCP / OpenAPI 工具服务器接外部服务。
7. 升级前确认数据卷会保留，并做好备份。

详细命令与避坑见 `SKILL.md`。

---

## 依赖

- Python 3.11（pip 路径）或 Docker（容器路径）。
- 一个可用的模型后端：Ollama 或任意 OpenAI 兼容 API。
- 可选：PostgreSQL（多用户/生产）、Redis（多节点）、向量数据库（本地 RAG）。
- 上游文档：<https://docs.openwebui.com/>

---

## 安全

- 不内嵌任何密钥；上游模型服务的 API Key 由使用者在管理面板中自行配置。
- 首次部署后开放注册默认可用，注册完管理员账号请立即关闭，并配置合适的认证方式。
- 对公网暴露前必须自行补上 HTTPS、访问控制与网络隔离；多副本还要配置 Redis 会话与 WebSocket 负载均衡。
- 数据默认落在 `open-webui` 数据卷与内置数据库中，请按需备份；不要执行会移除数据卷的清理操作。
- 若正文涉及联网或读写文件，权限范围已在 SKILL.md 的「权限与用途说明」中逐项列明。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Open WebUI`
- 仓库：https://github.com/open-webui/open-webui

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
