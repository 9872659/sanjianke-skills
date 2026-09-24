# 三剪客 · 一站式模型微调 Skill

LLaMA-Factory：用一份 YAML 配置微调上百种开源大模型——源码与 Docker 安装、命令行与图形界面、微调/推理/合并闭环、OpenAI 兼容 API 部署，以及显存与依赖避坑。

---

## 前置条件

- **Python 3.11 及以上**（官方要求最低 3.11）。
- **一块 NVIDIA GPU**（CUDA 11.6+，推荐 12.2）；也支持 Ascend NPU（需 CANN）与 AMD ROCm。
- **先查官方显存估算表再选档位**：7B 全参约 120GB，LoRA/Freeze 约 16GB，2bit QLoRA 约 4GB。选错档位就是白折腾。
- **磁盘空间**：模型权重 + 检查点 + 合并产物，通常是模型本身体积的数倍。
- **Windows 用户额外注意**：需手动装 CUDA 版 PyTorch，bitsandbytes 也要单独处理（见 `SKILL.md` 安装一节）。
- **凭证**：下载受限模型 / 数据集需要 Hub 访问令牌；要上报实验则需要 W&B 或 SwanLab 的 key。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
git clone --depth 1 https://github.com/hiyouga/LlamaFactory.git
cd LlamaFactory
pip install -e .
pip install -r requirements/metrics.txt
```

微调 → 试聊 → 合并三连：

```bash
llamafactory-cli train examples/train_lora/qwen3_lora_sft.yaml
llamafactory-cli chat examples/inference/qwen3_lora_sft.yaml
llamafactory-cli export examples/merge_lora/qwen3_lora_sft.yaml
```

图形界面：

```bash
llamafactory-cli webui
```

起 OpenAI 兼容 API（vLLM 后端）：

```bash
API_PORT=8000 llamafactory-cli api examples/inference/qwen3.yaml infer_backend=vllm vllm_enforce_eager=true
```

参数名、示例路径与模板名随版本演进，落地前以仓库 `examples/` 与官方文档为准。

---

## 依赖

- Python ≥ 3.11
- torch ≥ 2.0.0（推荐 2.6.0）、transformers ≥ 4.49.0、datasets ≥ 2.16.0、accelerate ≥ 0.34.0、peft ≥ 0.14.0、trl ≥ 0.8.6
- 可选：deepspeed（分布式）、bitsandbytes（量化）、vllm / sglang（快速推理）、flash-attn（加速）、metrics（评测）
- Docker（容器路径），仓库提供 CUDA / NPU / ROCm 三套 Dockerfile
- Hub 访问令牌（受限模型与数据集）；W&B / SwanLab key（实验跟踪）

---

## 安全

- 不内嵌任何密钥
- Hub 令牌与实验跟踪 key 只放环境变量或本地配置里，不要提交进 Git
- 训练任务会读取你指定的数据集路径并写入输出目录，跑前确认路径范围，别把整个盘挂进容器
- 起 `webui` 或 `api` 时注意监听地址：默认面向本机，若要对外提供，需自行加上访问控制，否则等于把模型服务公开
- 仓库代码是 Apache-2.0，但**模型权重各有自己的许可**，上线前必须查清所用模型那一份

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LLaMA-Factory`
- 仓库：https://github.com/hiyouga/LlamaFactory

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
