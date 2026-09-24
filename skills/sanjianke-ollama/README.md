# 三剪客 · 本地跑大模型 Skill

把「下载模型权重、配置推理环境、启动服务」压成一条命令的操作指引。

---

## 前置条件

- 目标机器有足够磁盘存放模型权重，以及足够的显存或内存把模型加载起来。
- 需要联网下载模型（推理阶段可完全离线）。
- Docker 方式需要本机 Docker；GPU 加速还需要 NVIDIA Container Toolkit。
- 从源码编译需要 Go 工具链。

---

## 使用

1. 按平台装好 Ollama，确认服务在跑（`http://localhost:11434/api/version`）。
2. `ollama run <模型名>` 拉取并进入对话，确认基础可用。
3. 要接进程序：用 REST API（`/api/chat`、`/api/embed` 等）或官方 Python / JavaScript SDK。
4. 要定制行为：写 `Modelfile`，用 `ollama create` 生成自己的模型名。
5. 容器或跨机调用时，改用正确的宿主机地址或配置 `OLLAMA_HOST`。

详细命令与避坑见 `SKILL.md`。

---

## 依赖

- Ollama 本体（macOS / Windows / Linux 官方安装包，或 `ollama/ollama` 镜像）。
- 可选：Python `ollama` 包、Node `ollama` 包。
- 上游文档：<https://docs.ollama.com/>

---

## 安全

- 不内嵌任何密钥；本地使用无需任何 Key。
- 默认只监听本地回环。要对外暴露必须显式改 `OLLAMA_HOST`，请自行评估网络暴露风险。
- 从外部拉取的 GGUF / safetensors 文件来自不可信来源时，导入前先确认来源可信。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Ollama`
- 仓库：https://github.com/ollama/ollama

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
