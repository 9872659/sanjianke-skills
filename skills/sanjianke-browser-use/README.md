# 三剪客 · 让 Agent 操控浏览器 Skill

用自然语言任务驱动 Agent 操控真实浏览器，完成没有 API 的网页操作与数据提取。

---

## 前置条件

- **Python 3.11 及以上**。
- 浏览器已就绪：执行 `uvx browser-use install` 下载 Chromium，或使用本机 Chrome / 云端浏览器。
- 至少一个模型供应商的 API Key；用 BU2 或云端浏览器还需要 `BROWSER_USE_API_KEY`。
- 本地模式需要能运行浏览器的桌面环境；CI / 无头服务器建议改用云端浏览器。

---

## 使用

```bash
uv add browser-use          # 或 pip install browser-use
uvx browser-use install     # 下载 Chromium，这一步不能省
```

最小可跑示例（存成 `agent.py`，配好 `.env` 后 `uv run agent.py`）：

```python
import asyncio
from browser_use import Agent, ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

async def main():
    llm = ChatOpenAI(model="gpt-4.1-mini")
    agent = Agent(task="Find the number of stars of the browser-use repo", llm=llm)
    history = await agent.run()
    print(history.final_result())

asyncio.run(main())
```

README 只给最小入口；模型选择、复用本机 Chrome 登录态、云端浏览器、自定义工具与结构化输出等，见 `SKILL.md` 的「常用操作」与「常见坑」。

---

## 依赖

- `browser-use`（Python 包，要求 Python ≥ 3.11）。
- 一个浏览器：本地 Chromium、本机系统 Chrome 配置，或官方云端浏览器。
- 模型：官方 BU2、OpenAI / Anthropic / Google 等包装类，或本地 Ollama。
- 可选：`BROWSER_USE_API_KEY`（BU2 与云端浏览器）、代理与 profile 同步（云端）。
- 具体版本与支持的模型清单以 PyPI 与官方文档当前内容为准。

---

## 安全

- 不内嵌任何密钥
- 模型 API Key 与 `BROWSER_USE_API_KEY` 一律走环境变量 / `.env`
- 复用本机 Chrome 配置意味着 Agent 能接触你已登录的账号，务必限定任务范围并避免不可逆操作
- 包默认开启匿名遥测，企业环境建议设 `ANONYMIZED_TELEMETRY=false`
- 目标站点的服务条款、robots 与数据合规由使用者自行确认，本 Skill 不提供规避反爬的保证

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Browser Use`
- 仓库：https://github.com/browser-use/browser-use

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
