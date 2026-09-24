# 三剪客 · 多平台 IM 接大模型的机器人平台 Skill

LangBot（原 QChatGPT）：多平台 IM 接大模型的机器人平台 的安装、常用命令与避坑要点

---

## 前置条件

- 一台能稳定出网的机器：Linux / Windows / macOS 均可，容器方式需 Docker 与 Docker Compose v2。
- 源码方式需要 **Python 3.10 ~ 3.13** 与包管理器 **uv**；版本不在区间内会在依赖同步阶段直接失败。
- 至少一个大模型或 LLMOps 平台的可用凭证（云端 API Key，或本地 Ollama / LM Studio 服务地址）。
- 目标 IM 平台侧已开通机器人能力并拿到凭证；对外提供服务时还需域名、反向代理与 TLS 证书。
- 默认控制台端口 **5300** 需可用；若从公网访问，建议只经反向代理暴露。

## 使用

1. **先跑起来**。最短路径是 `uvx langbot`，跑完访问 `http://localhost:5300`；长期运行改用 `LangBot/docker` 目录下的 `docker compose --profile all up -d`。
2. **源码方式的两步不能省**：先下 Releases 页带 WebUI 的整包 `langbot-*-all.zip` 并解压（Source Code 包里没有 WebUI），再 `pip install uv && uv sync && uv run main.py`。首次启动会自动生成 `data/config.yaml`，改完重启。
3. **在面板里配三件事**：机器人（接哪个 IM、填平台凭证与回调）→ 模型（接哪个模型、填 Key 或地址）→ 对话流水线（把人设、知识库、工具串起来）。多流水线可给不同群配不同行为。
4. **接 MCP**（可选）：Web 面板"API 与 MCP"标签页里配置，管理端点暴露在 `/mcp`，用同一套 API Key 鉴权，无需登录流程。
5. 详细命令与逐平台字段见 `SKILL.md`；**所有参数与平台字段以官方文档和实际界面为准**，不要凭记忆填。

## 依赖

- **运行时**：Python 3.10 ~ 3.13；或 Docker + Docker Compose v2。
- **工具**：uv（免安装启动与源码方式都需要）。
- **外部服务**：IM 平台开放接口 / 机器人协议；大模型 API 或本地模型服务；可选 LLMOps 平台（Dify、Coze、n8n、Langflow 等）。
- **可选**：SeekDB 向量库与内置嵌入模型（需 `uv sync --extra seekdb`，其平台支持取决于对应的 Python wheel）。
- **网络**：容器拉取镜像、依赖下载、平台回调进出站均需放行。

## 安全

- 不内嵌任何密钥；所有 API Key 与平台凭证由使用者在配置或环境变量中自行填入。
- 配置文件与日志可能包含凭证与会话内容，请确保 `data/` 目录不被提交到代码仓库、不被公网直接访问。
- 公开演示环境是共享的，**不要在其中填入任何真实资料**。
- 个人号协议类接入存在账号封禁与合规风险，请自行评估并按平台规则使用；本 Skill 不提供规避平台风控的方法。
- 对外开放实例建议置于反向代理之后并启用 TLS，同时打开访问控制与限速。
- 更新镜像或代码前先确认数据卷已持久化，避免升级过程中丢配置与会话。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LangBot（原 QChatGPT）`
- 仓库：https://github.com/langbot-app/LangBot

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
