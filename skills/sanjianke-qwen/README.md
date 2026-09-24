# 三剪客 · 通义千问开源模型 Skill

从「用哪个尺寸」到「起一个本地服务」：通义千问第一代开源模型的选型、权重下载、推理、部署与微调。

---

## 前置条件

- **先确认两件事**：这个仓库上游已不再积极维护（新项目应看更新的 Qwen 仓库）；许可证按尺寸分档，7B / 14B / 72B 商用需申请，1.8B 是研究许可。
- Python 3.8+、PyTorch 1.12+（建议 2.0+）、transformers 4.32+、CUDA 11.4+（GPU 场景）。
- **足够的显存**：按尺寸选，并额外为 KV cache 留余量；上下文越长占用越高。
- **足够的磁盘**与一条能访问 HuggingFace 或 ModelScope 的下载通路（国内优先 ModelScope）。
- 走 Docker 路线时，需要符合版本要求的 NVIDIA 驱动与 nvidia-container-toolkit。

---

## 使用

1. 先看 SKILL.md 里的两张表，按**能力**和**显存**选定尺寸（注意 14B 最大长度只有 8K 且未做系统提示增强）。
2. 用 ModelScope 的 `snapshot_download` 或 HuggingFace 模型名把权重下到本地。
3. 用 Transformers 加载（记得 `trust_remote_code=True`），`model.chat(tokenizer, query, history=history)` 做多轮对话。
4. 要常驻服务：轻量用 `python openai_api.py`，要多并发 / 多卡用 vLLM + FastChat，要省事用官方 Docker 脚本。
5. 要微调：用仓库里的 LoRA / Q-LoRA 脚本，先读分词器与特殊 token 的说明。

完整命令、坑表与显存参考见 `SKILL.md`。

---

## 依赖

- Python / PyTorch / transformers / CUDA，版本要求见上。
- 权重与代码从 HuggingFace 或 ModelScope 获取。
- 可选：flash-attention（提速降显存，编译较慢）、qwen.cpp（CPU 场景）、vLLM + FastChat（高性能服务）、Docker + nvidia-container-toolkit（镜像部署）。
- 上游项目自身依赖以仓库 `requirements.txt` 与官方文档为准。

---

## 安全

- 不内嵌任何密钥
- `trust_remote_code=True` 会执行模型仓库里的自定义代码，**只对你信任的来源开启**。
- 模型权重是几十 GB 级的大文件，下载前确认磁盘与网络成本；微调还会额外产生 checkpoint。
- 自建服务（`openai_api.py` / FastChat）默认不做鉴权，对外暴露前必须自行加访问控制。
- 商用前完成授权确认：代码是 Apache 2.0，模型权重另有协议，两者不是一回事。
- 能力边界见 SKILL.md 的「能力边界」一节。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Qwen`
- 仓库：https://github.com/QwenLM/Qwen

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
