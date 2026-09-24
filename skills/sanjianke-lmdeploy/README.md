# 三剪客 · 模型部署与量化 Skill

把大模型跑起来并压下去：离线批量推理、OpenAI 兼容服务、AWQ 4bit 权重量化、KV Cache 量化，以及 TurboMind / PyTorch 双引擎的选型。本 Skill 覆盖安装、引擎选择、量化全流程与真实坑点。

---

## 前置条件

- Python **3.10 – 3.13**，官方推荐用 conda 环境 + pip 安装。
- NVIDIA GPU 与匹配的驱动 / CUDA：PyPI 上默认的预编译 wheel 面向 **CUDA 12.8** 构建；其他 CUDA 版本按官方安装文档处理。
- 昇腾平台走 PyTorch 引擎，需按官方对应文档安装。
- 4bit AWQ / GPTQ 推理对 GPU 架构有要求（Volta sm70、Turing sm75、Ampere sm80/86、Ada sm89 等，以官方当前列表为准）。
- 模型权重需自行下载（默认 Hugging Face，可切 ModelScope / openMind Hub）；受控仓库需要 Token。
- VLM 模型需要额外安装上游视觉组件的依赖 —— 官方明确说明这些依赖不在 LMDeploy 的依赖列表里。

---

## 使用

正文按「先用不用 → 安装 → 常用操作 → 查坑」组织：

1. **什么时候用 / 不用**：先排除「只想本地跑个 GGUF 聊天」「要训练微调」「要企业级网关」这类误判。
2. **安装**：conda + pip 最短路径、CUDA 12.8 wheel 的适用范围、Docker 启动命令、切模型源的两种环境变量、其他平台指向官方安装文档。
3. **常用操作**：按需求分八段给出可直接跑的代码/命令——离线批量推理、选引擎并调显存参数、控制采样、起 OpenAI 兼容服务、终端验证、AWQ 量化 → 量化模型推理/服务、KV 量化（含 TurboQuant）、VLM 图文推理。
4. **常见坑**：`cache_max_entry_count` 的真实含义与 OOM 处方、量化模型必须声明 `model_format`、`--work-dir` 与 chat template 的模糊匹配、量化 OOM 处方、两引擎支持范围不同、VLM 依赖、CUDA 版本不匹配、模型源、**接口默认无鉴权**、`finish_reason=length`、TurboQuant 限制、多 token 停止词。

典型调用链：

```bash
conda create -n lmdeploy python=3.12 -y && conda activate lmdeploy
pip install lmdeploy
lmdeploy chat internlm/internlm2_5-7b-chat --backend turbomind     # 先验证模型与模板
lmdeploy serve api_server internlm/internlm2_5-7b-chat             # 默认 23333
```

```bash
# 显存不够时
lmdeploy lite auto_awq internlm/internlm2_5-7b-chat --work-dir internlm2_5-7b-chat-4bit
lmdeploy serve api_server ./internlm2_5-7b-chat-4bit --backend turbomind --model-format awq
```

---

## 依赖

- conda（推荐）或等价的 Python 3.10 – 3.13 环境。
- 与 wheel 构建目标匹配的 CUDA 与 NVIDIA 驱动。
- 可选：`modelscope`（切国内模型源）、`openmind_hub`、`fast_hadamard_transform`（TurboQuant 加速）、`openai`（客户端调用）。
- Docker 方式需要 Docker 与可用的 `--gpus all`。
- 具体依赖与版本要求以官方安装文档为准。

---

## 安全

- 不内嵌任何密钥
- 从需要授权的模型仓库拉权重时，Token 请用环境变量传入（如 `HUGGING_FACE_HUB_TOKEN`），不要写进脚本或镜像
- **`api_server` 默认不做鉴权**：官方示例里的 `api_key='YOUR_API_KEY'` 只是占位符。只在内网监听，对外必须在前面加带鉴权与限流的反向代理
- 量化校准数据集与产出目录可能包含内部数据，注意存放位置与清理
- 多卡 / 多机分发场景下，确认各节点端口与访问控制符合内网策略
- 若正文涉及联网或读写文件，权限范围已在 SKILL.md 的「权限与用途说明」中逐项列明
- 能力边界见 SKILL.md 的「能力边界」一节

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LMDeploy`
- 仓库：https://github.com/InternLM/lmdeploy

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
