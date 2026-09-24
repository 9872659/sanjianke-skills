# 三剪客 · LLM 应用开发框架 Skill

用一套统一接口把模型、工具、记忆、检索串成能跑完的 LLM 应用与 Agent。

---

## 前置条件

- Python **3.10 及以上**，建议独立虚拟环境（`uv` / `venv` / `conda`）。
- 至少一个模型供应商的 API Key，或一个本地推理服务（如 Ollama）。
- 走 RAG 时另需向量库与嵌入模型，都需要单独安装与配置。

---

## 使用

安装主包与所需集成包（集成包不含在主包里）：

```bash
uv add langchain
pip install langchain-openai        # 按供应商替换：langchain-anthropic / langchain-google-genai / langchain-ollama
```

最小 Agent：

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

agent = create_agent(model="openai:gpt-5.5", tools=[search])
result = agent.invoke({"messages": [{"role": "user", "content": "帮我查一下今天的汇率"}]})
print(result["messages"][-1].text)
```

换模型只改 `model=` 字符串；多轮对话要挂 checkpointer 并复用 `thread_id`。
完整的六块内容（定位 / 什么时候用·不用 / 安装 / 常用操作 / 常见坑 / 能力边界）见 `SKILL.md`。

---

## 依赖

- `langchain`（主包）——提供模型统一接口、`create_agent`、中间件。
- `langchain-<provider>`（集成包）——每个供应商一个，独立发版。
- `langgraph`——状态化编排与 checkpointer 的实现依赖。
- 可选：向量库客户端、嵌入模型包、`pydantic`（结构化输出）。
- 各包的具体版本以 PyPI 与上游仓库当前发布为准。

---

## 安全

- 不内嵌任何密钥
- API Key 一律走环境变量或 `.env`，不要写进代码与提交历史
- 给 Agent 的工具会真实执行副作用操作，删改类工具建议配人工审批中间件
- Agent 会读取工具返回的全部内容进上下文，接入外部数据源前先做可信度与敏感信息评估

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LangChain`
- 仓库：https://github.com/langchain-ai/langchain

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
