# 三剪客 · 结构化 LLM 推理 Skill

SGLang：结构化 LLM 推理 的安装、常用命令与避坑要点

---

## 前置条件

- Python 3.10 或更高。
- 一台带加速卡（NVIDIA / AMD，或对应平台的 TPU、NPU）的机器，显存足够放下目标模型。
- CUDA 环境与要安装的 wheel 主版本一致；CUDA 12 必须按官方给定的顺序重装若干包。
- 模型可从 Hugging Face 获取；受限模型需要先在页面接受协议并准备 token。
- Docker 方式要求本机 Docker 支持 GPU，并且启动时给足共享内存。
- 磁盘留出模型权重与编译缓存的空间，大模型动辄几十 GB。

---

## 使用

把本目录作为 Skill 交给 Agent，或直接对照 `SKILL.md` 操作。典型流程：

1. 先 `python3 -m sglang.launch_server --help` 确认安装成功、参数名与当前版本一致。
2. 用 `--model-path` 拉起服务，本地默认端口 30000。
3. 浏览器打开 `http://localhost:30000/docs` 看真实接口定义。
4. 用 OpenAI 客户端只换 `base_url` 打通一次普通对话。
5. 再加 `response_format`（json_schema）或 `extra_body`（regex / ebnf）验证结构约束生效。
6. 需要批量离线处理时改用 `sgl.Engine`，不必起 HTTP 服务。

---

## 依赖

- `sglang` 本体及其 Python 依赖，推荐用 `uv` 安装。
- 与 CUDA 版本匹配的 torch 及算子包（CUDA 12 需要额外步骤）。
- FlashInfer（默认注意力后端，仅支持 sm75 及以上）、XGrammar（默认语法后端，随包安装）。
- 可选：Outlines 或 llguidance 作为替代语法后端。
- 可选：Docker（容器部署）、Hugging Face token（拉取受限模型）。

---

## 安全

- 不内嵌任何密钥
- 服务默认不带鉴权，**不要直接暴露到公网**；需要对外时前面加反向代理并做认证与限流。
- Hugging Face token 通过环境变量或 `huggingface-cli login` 提供，不要写进脚本或镜像。
- 模型权重与自定义模型代码可能执行任意逻辑，只加载可信来源的模型。
- 多卡部署涉及跨进程共享内存与高速互联，注意同机其他负载的资源竞争。
- 结构化输出只约束格式，不约束内容；涉及对外发布的字段仍要做业务校验。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`SGLang`
- 仓库：https://github.com/sgl-project/sglang

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
