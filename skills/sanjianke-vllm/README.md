# 三剪客 · 高吞吐 LLM 推理服务 Skill

vLLM 的安装（uv/pip/Docker/ROCm/TPU）、vllm serve 在线服务、离线批量推理、张量并行与显存参数调优、常见报错与能力边界

---

## 前置条件

- 操作系统：Linux。官方明确不原生支持 Windows（需 WSL 或社区分支）；macOS 走 vLLM-Metal。
- Python 3.10 – 3.13，且建议使用**全新的干净环境**：编译出的 CUDA kernel 与其他 CUDA/PyTorch 组合二进制不兼容。
- 加速器：NVIDIA compute capability ≥ 7.5；AMD 需 ROCm 7.0 + Python 3.12 + glibc ≥ 2.35；Intel XPU / Google TPU / Ascend NPU / Apple Silicon 各有自己的安装路径。
- Docker 路线需要 Docker 与 NVIDIA Container Toolkit（或 Podman + CDI）。
- 拉取模型需要网络与磁盘；受限模型需要 `HF_TOKEN`。
- 从源码全量编译需要 GCC/G++ ≥ 11.3。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
uv venv --python 3.12 --seed
source .venv/bin/activate
uv pip install vllm --torch-backend=auto
vllm serve Qwen/Qwen2.5-1.5B-Instruct
```

离线批量推理：

```python
from vllm import LLM, SamplingParams

llm = LLM(model="facebook/opt-125m")
outputs = llm.generate(["Hello, my name is"], SamplingParams(temperature=0.8, top_p=0.95))
print(outputs[0].outputs[0].text)
```

引擎参数、环境变量与部署形态对照见 `references/deploy-and-tuning.md`。参数拼写以 `vllm serve --help` 与官方文档的当前内容为准。

---

## 依赖

- Python 3.10–3.13
- `uv`（官方推荐）或 `pip`；conda 环境内也可用 `uv pip`
- PyTorch 与匹配的 CUDA/ROCm 运行时（由安装命令自动带入）
- CPU 核数：V1 是 2 + N 进程架构，至少准备 2 + GPU 数 个物理核
- 可选：Docker / Podman 运行时
- 可选：`HF_TOKEN`（受限模型）、`VLLM_API_KEY`（服务端鉴权）
- 可选：`fastokens>=0.2.0`（启用 `VLLM_USE_FASTOKENS=1` 时需要）
- 可选：FlashInfer（手动指定 `--attention-backend FLASHINFER` 时需要，预编译轮子不含）

---

## 安全

- 不内嵌任何密钥
- 推理服务是常驻网络进程，**不要**把没有鉴权的端口暴露到公网；生产环境请设 `--api-key` 或 `VLLM_API_KEY`，并放在反向代理 / 网关之后
- 模型权重来自外部仓库，加载前确认来源可信；优先 `safetensors`，避免加载不可信来源的 pickle 格式权重
- `VLLM_SERVER_DEV_MODE=1` 会打开清缓存、暂停、改权重等端点，官方明确警告不要用于生产
- `--runtime nvidia --gpus all` 让容器直接使用宿主 GPU，多租户机器上需额外做设备与显存隔离
- 编译缓存与模型缓存可能含模型信息，共享机器上注意目录权限

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`vLLM`
- 仓库：https://github.com/vllm-project/vllm

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
