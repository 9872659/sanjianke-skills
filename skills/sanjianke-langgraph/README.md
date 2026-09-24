# 三剪客 · 有状态 Agent 编排 Skill

用显式状态图编排 Agent：节点、边、共享 State、条件路由，配上检查点实现断点续跑、人工审批与跨会话记忆。

---

## 前置条件

- Python：配 LangChain 需 3.10+，用 CLI 需 3.11+。
- 至少一个模型厂商包与对应 API Key（示例默认 Anthropic）。
- 需要多轮记忆 / 断点恢复时，准备持久化后端：开发期可用内存版，生产用 PostgreSQL 或 SQLite。
- 想用本地服务与图形化调试，需要 LangSmith 账号（`langgraph dev` 与 Studio 都依赖它）。

---

## 使用

1. 按 `SKILL.md`「安装」装 `langgraph`，需要的话补 `langchain` 与厂商包。
2. 从「常用操作 1」的最小图开始跑通，再按需加条件边、检查点。
3. 要人机协同就在节点里调 `interrupt()`，用 `Command(resume=...)` 恢复。
4. 要本地调试服务就用 `langgraph new` 建项目、`langgraph dev` 起服务。
5. 上线前把内存检查点换成持久化后端，并规划检查点清理策略。
6. 遇到重复执行、中断顺序错乱等问题，对照 `SKILL.md`「常见坑」表排查。

---

## 依赖

- `langgraph`（`langgraph-prebuilt` 已内含其中，勿重复安装）。
- `langchain` 与具体模型厂商包（可选，但多数示例依赖）。
- 持久化：`langgraph-checkpoint-postgres` / `langgraph-checkpoint-sqlite` 系列（按后端选择）。
- 服务与客户端：`langgraph-cli[inmem]`、`langgraph-sdk`。
- 可选：LangSmith（追踪与 Studio 调试）。

---

## 安全

- 不内嵌任何密钥；模型 Key 与 `LANGSMITH_API_KEY` 一律走环境变量或 `.env`，不要提交进仓库。
- `langgraph dev` 起的服务默认只监听本机，但仍属开发用内存模式；不要把它暴露到公网或当生产服务使用。
- 引入 `interrupt()` 做审批时，注意其后的副作用只执行一次，之前的操作必须幂等，否则会出现重复下单、重复发信这类事故。
- 图会执行你定义的工具函数，工具能碰到什么就等于给 Agent 开了什么权限；给工具做最小权限约束，写操作前加人工确认。
- 检查点里会存下完整的对话与状态，属于敏感数据；选持久化后端时要一并考虑加密、访问控制与保留期限。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LangGraph`
- 仓库：https://github.com/langchain-ai/langgraph

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
