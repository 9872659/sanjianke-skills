# 三剪客 · 模型加载与推理 Skill

在 Python 里加载 Hugging Face 预训练模型并做推理的操作指引

---

## 前置条件

- Python 3.10 及以上，PyTorch 2.5 及以上（官方要求）。
- 需要联网下载权重，除非模型已预先缓存到本地。
- 要用 GPU 需要匹配的 CUDA / 驱动环境；Apple Silicon 与各类加速卡的支持情况各不相同。
- 加载受限或私有仓库需要有效的 Hub 访问凭证。

---

## 使用

1. 建虚拟环境，安装 `transformers[torch]`。
2. 先用 `pipeline` 加一个小模型验证链路通不通。
3. 需要更细控制时改用 `AutoModel` / `AutoModelFor*` 加载权重。
4. 显存吃紧：依次考虑低精度 `dtype`、`device_map="auto"`、量化、磁盘卸载。
5. 要命令行对话：先 `transformers serve`，再 `transformers chat <模型>`。

详细命令与避坑见 `SKILL.md`。

---

## 依赖

- `transformers` 本体，及方括号里的额外依赖（如 `[torch]`）。
- `torch`（版本需 ≥ 2.5）。
- 使用 `device_map="auto"` 与磁盘卸载依赖 Accelerate，完全磁盘卸载对 Accelerate 版本有更高要求。
- 具体量化方案需要额外装对应的第三方库，且对硬件与后端有各自的限制。
- 上游文档：<https://huggingface.co/docs/transformers/index>

---

## 安全

- 不内嵌任何密钥；访问受限模型请使用自己的 Hub 凭证。
- `trust_remote_code=True` 会执行第三方仓库的建模代码，等同在本机运行他人代码；请固定 `revision` 到具体 commit 并确认来源可信。
- 加载外部模型权重前先确认来源可信。
- 若正文涉及联网或读写文件，权限范围已在 SKILL.md 的「权限与用途说明」中逐项列明。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Transformers`
- 仓库：https://github.com/huggingface/transformers

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
