# 三剪客 · 多智能体对话框架 Skill

把「一个写、一个审、改到通过」这类协作写成配置：AutoGen 的安装、四类团队预设选型、终止条件与状态管理，以及维护模式带来的选型风险。

---

## 前置条件

- Python **3.10 及以上**（上游要求）。
- 建议独立虚拟环境（venv 或 conda）。
- 装 `autogen-agentchat` 与 `autogen-ext[openai]`；用 Azure OpenAI 的 AAD 认证再加 `autogen-ext[azure]`。
- 一个可用的 LLM 与密钥：默认 OpenAI / Azure OpenAI，走 `OPENAI_API_KEY` 环境变量。
- 上手前先读一遍上游说明：AutoGen 已进入维护模式，官方建议新项目改用 Microsoft Agent Framework。
- 只有挂 Node 版 MCP 服务器（例如 Playwright MCP）时才需要 Node.js 与 `npx`。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
pip install -U "autogen-agentchat" "autogen-ext[openai]"
export OPENAI_API_KEY="sk-..."
```

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

async def main() -> None:
    model_client = OpenAIChatCompletionClient(model="gpt-4.1")
    agent = AssistantAgent("assistant", model_client=model_client)
    print(await agent.run(task="Say 'Hello World!'"))
    await model_client.close()

asyncio.run(main())
```

加一个评审 Agent 组成反思团队，用 `TextMentionTermination("APPROVE")` 收口，完整代码见 `SKILL.md` 的「常用操作」第 2 条。

不想写代码时先用 Studio 验证流程：

```bash
pip install -U "autogenstudio"
autogenstudio ui --port 8080 --appdir ./my-app
```

团队预设的参数名与终止条件类型以官方文档 https://microsoft.github.io/autogen/stable/ 的当前内容为准。

---

## 依赖

- `autogen-agentchat`（AgentChat 易用层）
- `autogen-ext[openai]`（OpenAI 客户端）；Azure AAD 场景追加 `autogen-ext[azure]`
- 按需的扩展：MCP 工具、代码执行等
- 一个 LLM 服务与密钥（默认 OpenAI / Azure OpenAI）
- 可选：`autogenstudio`（无代码原型）、Node.js + `npx`（Node 版 MCP 服务器）

---

## 安全

- 不内嵌任何密钥
- 模型密钥走环境变量（`OPENAI_API_KEY` 等），不要写进代码或仓库
- MCP 服务器会在本地执行命令、可能暴露敏感信息，上游对此有明确警告：只连可信服务器
- Agent 若挂了代码执行或文件读写类工具，等于把本机的一部分操作权交给模型输出；限制工作目录与可执行范围，必要时加人工确认
- 多 Agent 团队会持续调用模型，注意 token 消耗与死循环风险，务必设终止条件
- AutoGen Studio 不是生产应用，不要不做鉴权就对外暴露它的端口；`--appdir` 里可能有会话数据
- AutoGen 已进入维护模式，安全修复仍会收，但整体响应速度与支持力度需自行评估

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`AutoGen`
- 仓库：https://github.com/microsoft/autogen

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
