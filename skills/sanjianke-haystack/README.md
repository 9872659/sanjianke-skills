# 三剪客 · RAG 流水线框架 Skill

用 Python 搭一条可控、可替换、可序列化的检索增强生成流水线，并把它服务化。

---

## 前置条件

- Python 环境（最低版本以 PyPI 上 `haystack-ai` 的声明为准）与 pip / uv / conda 任一。
- 至少一个可用的 LLM：本地模型或 API；用 API 时需要对应的 Key 并注入到运行进程的环境变量里。
- 接外部向量库 / 搜索服务时，需要单独安装对应的集成包。
- 服务化（Hayhooks 等）时需要常驻进程与可访问端口。

---

## 使用

1. `pip install haystack-ai`。**注意包名是 `haystack-ai`**，1.x 时代的包是另一套不兼容的 API。
2. 用 `Pipeline()` + `add_component()` + `connect()` 把检索、拼 prompt、生成连成一条线。
3. `pipeline.run({"组件名": {"输入名": 值}})`，结果用 `results["组件名"]["输出名"]` 取。
4. 组件报 ImportError 就照提示 `pip install` 缺的那个可选依赖。
5. 要对外提供接口时接 Hayhooks，把流水线包成 HTTP / MCP 服务。

完整最小示例、坑表与自检清单见 `SKILL.md`。

---

## 依赖

- Python 运行环境与包管理器。
- 按需的可选依赖：核心包刻意保持轻量，用到哪个组件就装它提示的那个库。
- 按需的集成包：外部文档库、云模型供应商等都在官方 `haystack-core-integrations` 仓库里，各自独立发布，包名以官方 Integrations 页为准。
- 模型服务与相应凭据。
- 上游项目自身依赖与版本要求以仓库与官方文档为准。

---

## 安全

- 不内嵌任何密钥
- 模型与向量服务的 Key 通过环境变量注入，不要写进代码；注意 `.env` 文件不会被自动加载。
- 匿名遥测默认开启（每次组件初始化上报一次事件），合规敏感或内网环境请按官方 Telemetry 页先关闭再上线。
- 进入生产前确认所选的集成包与版本，避免引入来源不明的第三方组件。
- 能力边界见 SKILL.md 的「能力边界」一节。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Haystack`
- 仓库：https://github.com/deepset-ai/haystack

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
