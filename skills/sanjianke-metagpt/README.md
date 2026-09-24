# 三剪客 · 多智能体软件公司 Skill

MetaGPT：用一句需求跑出一套项目文档与代码骨架——角色化 SOP 流水线的安装、模型配置、CLI 与 Python API 用法、Data Interpreter，以及版本与成本避坑。

---

## 前置条件

- **Python 3.9 及以上，但低于 3.12**（官方要求）。这是最容易踩的一条，别用 3.12+。
- **Node.js 与 pnpm**：官方明确要求"实际使用前"装好，它不是一个纯 Python 包。
- **一个可用的模型服务**：需要 `api_type` / `model` / `base_url` / `api_key` 四项齐全，支持 openai、azure、ollama、groq 等类型与自定义转发地址。
- **网络**：能访问你配置的模型服务地址，并能拉取 pip / Docker 依赖。
- **磁盘**：每次任务会在工作目录下生成一个完整项目目录。
- **Docker（可选）**：走容器路径时需要，且要把宿主机配置与 workspace 目录都挂载进容器。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
conda create -n metagpt python=3.9 && conda activate metagpt
pip install --upgrade metagpt
metagpt --init-config          # 生成 ~/.metagpt/config2.yaml，填好 api_key
metagpt "Create a 2048 game"   # 产物落在当前目录 ./workspace
```

当库用：

```python
from metagpt.software_company import generate_repo
from metagpt.utils.project_repo import ProjectRepo

repo: ProjectRepo = generate_repo("Create a 2048 game")
print(repo)
```

Data Interpreter：

```python
import asyncio
from metagpt.roles.di.data_interpreter import DataInterpreter

async def main():
    di = DataInterpreter()
    await di.run("Run data analysis on sklearn Iris dataset, include a plot")

asyncio.run(main())
```

配置项、导入路径与示例位置随版本演进，落地前以官方文档与仓库当前内容为准。

---

## 依赖

- Python 3.9 ≤ 版本 < 3.12
- Node.js + pnpm（官方要求实际使用前安装）
- 一个可用的模型服务及其 API Key（openai / azure / ollama / groq 等类型，或自定义 base_url）
- 可选：Docker（容器方式运行）
- 可选：在线体验入口（Hugging Face Space），用于先试效果再决定是否本地安装

---

## 安全

- 不内嵌任何密钥
- API Key 写在 `~/.metagpt/config2.yaml` 里，不要提交进 Git
- Agent 会自己写代码并可能在本地执行（Data Interpreter 尤其如此），跑之前确认工作目录范围，不要在含敏感数据的机器上直接跑未审的需求
- 任务产物写在 `./workspace` 下，注意该目录的写入与后续执行风险
- 官方 Docker 示例带 `--privileged`，权限偏大，非必要不用，更不要在生产机器上照抄

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`MetaGPT`
- 仓库：https://github.com/FoundationAgents/MetaGPT

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
