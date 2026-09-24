# 三剪客 · 角色化 Agent 协作 Skill

用招聘的思路描述 Agent（role / goal / backstory），让一组角色按顺序或按层级协作完成多步骤工作；需要精确控制时再用事件驱动 Flow 把 Crew 串起来。

---

## 前置条件

- Python **>=3.10 且 <3.14**（上游要求）。
- **uv**：CrewAI 用 uv 管理依赖与 CLI，必须先装。
- 一个可用的 LLM 与密钥：默认 OpenAI，走 `.env` 里的 `OPENAI_API_KEY`；本地模型走 Ollama / LM Studio。
- 用到网页搜索等工具时，需要该工具自己的 API Key（例如 `SERPER_API_KEY`）。
- Windows 上如需编译 `chroma-hnswlib`，先装 Visual Studio Build Tools 并勾选 **Desktop development with C++**。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
# 装 uv（Windows）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 装 CLI
uv tool install crewai
uv tool update-shell

# 起一个项目
crewai create crew my_project
cd my_project
crewai install
crewai run
```

纯 Python 写法（Agent / Task / Crew）：

```python
from crewai import Agent, Task, Crew, Process

researcher = Agent(
    role="Senior Data Researcher",
    goal="Uncover cutting-edge developments in {topic}",
    backstory="You're a seasoned researcher who finds relevant information and presents it clearly.",
)

task = Task(
    description="Analyze {sector} sector data",
    expected_output="Detailed market analysis with confidence score",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task], process=Process.sequential, verbose=True)
result = crew.kickoff(inputs={"sector": "tech"})
```

Flow + Crew 的组合写法见 `SKILL.md` 的「常用操作」第 6 条。

CLI 子命令与项目结构以 `crewai --help` 和 https://docs.crewai.com 的当前内容为准。

---

## 依赖

- uv（依赖与包管理）
- `crewai`（CLI 全局工具 + 项目内库）
- 一个 LLM 服务与密钥（默认 OpenAI）
- 所用工具各自的 API Key（如搜索类工具）
- Windows 编译场景：Visual Studio Build Tools（Desktop development with C++）

---

## 安全

- 不内嵌任何密钥
- 模型密钥与工具密钥统一放 `.env` 或环境变量，`.gitignore` 要覆盖 `.env`
- 默认开启匿名遥测；设 `OTEL_SDK_DISABLED=true` 可关闭。开启 `share_crew` 后会上报任务描述、目标、背景故事与输出等更详细内容，涉及敏感业务前务必确认
- Agent 挂载的工具会以你的权限访问外部服务与本地文件；自定义工具里要限制路径与网络目标
- 任务配置了 `output_file` 会直接写盘，注意输出目录别指向源码或系统目录
- 自主协作会持续调用模型，成本和时长都不可控，生产运行记得关 `verbose` 并设置预算与超时

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`CrewAI`
- 仓库：https://github.com/crewAIInc/crewAI

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
