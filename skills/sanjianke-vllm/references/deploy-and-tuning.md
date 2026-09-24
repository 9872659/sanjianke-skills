# vLLM 部署形态与关键参数速查

本文只做两件事：把官方文档里「该选哪种装法」和「常用参数叫什么」摊开，以及给出出问题时的排查顺序。命令取自上游 README 与官方文档，参数名都以 `vllm serve --help` 的当前输出为准。

---

## 一、部署形态对照

| 形态 | 适用场景 | 关键命令 / 入口 |
|---|---|---|
| uv 虚拟环境 | 大多数场景，官方推荐 | `uv venv --python 3.12 --seed` → `uv pip install vllm --torch-backend=auto` |
| uv 临时环境 | 只想试一下，不想留环境 | `uv run --with vllm vllm --help` |
| pip | 已有 pip 工作流 | `pip install vllm --extra-index-url https://download.pytorch.org/whl/cu129` |
| conda | 团队用 conda 管环境 | `conda create -n myenv python=3.12 -y` → 在环境内 `uv pip install vllm --torch-backend=auto` |
| 官方 Docker 镜像 | 生产部署、不想管依赖 | `vllm/vllm-openai:latest`，容器内直接 `--model` |
| 源码 + 预编译轮子 | 只改 Python 逻辑要调试 | `VLLM_USE_PRECOMPILED=1 uv pip install --editable . --torch-backend=auto` |
| 源码全量编译 | 改了 C++ / CUDA kernel | `uv pip install -e . --torch-backend=auto`（GCC/G++ ≥ 11.3） |
| 自建镜像 | 要加官方镜像里没有的可选依赖 | `FROM vllm/vllm-openai:latest` + `RUN uv pip install --system vllm[audio]==<同版本>` |

不同硬件的安装入口：

| 硬件 | 安装方式 |
|---|---|
| NVIDIA CUDA | `uv pip install vllm --torch-backend=auto`；pip 走 cu129 索引 |
| AMD ROCm | `uv pip install vllm --extra-index-url https://wheels.vllm.ai/rocm/`（Python 3.12 / ROCm 7.0 / glibc ≥ 2.35） |
| Intel XPU | 官方镜像从 v0.26.0 起进正式发布；nightly 为 `vllm/vllm-openai-xpu:nightly` |
| Google TPU | `uv pip install vllm-tpu` |
| Ascend NPU | 走社区插件 vLLM Ascend 的快速开始 |
| Apple Silicon | 走 vLLM-Metal（MLX 后端，需要 MLX 转换过的模型） |
| CPU | 有 CPU 后端，线程绑定等参数见 CPU 安装文档 |

---

## 二、服务端常用参数

下表的引擎参数对应官方文档里的同名配置项（Python API 用下划线拼写，如 `tensor_parallel_size`；CLI 用连字符拼写，如 `--tensor-parallel-size`）。**具体拼写与可用值以 `vllm serve --help` 的当前输出为准。**

| 参数 | 作用 |
|---|---|
| `--model <hf_id 或本地路径>` | 指定托管的模型；Docker 镜像里模型名是位置参数 |
| `--host` / `--port` | 监听地址与端口，默认 `http://localhost:8000` |
| `--api-key` | 开启鉴权；可传多个实现轮换。也可用环境变量 `VLLM_API_KEY` |
| `--tensor-parallel-size N` | 张量并行，权重按层内切到 N 张卡 |
| `--pipeline-parallel-size N` | 流水线并行，按层切到多卡/多节点 |
| `--data-parallel-size N` / `-dp N` | 数据并行，整模型复制，横向扩吞吐 |
| `--gpu-memory-utilization` | 预分配给 KV 缓存的比例，调高可缓解 preemption |
| `--max-num-seqs` / `--max-num-batched-tokens` | 限制并发序列数 / 单批 token 预算 |
| `--kv-cache-memory` | 直接给定 KV 缓存大小，跳过显存探测（换卡或换共租户后要重新探测） |
| `--max-model-len`（配置项 `max_model_len`） | 限制上下文长度，是常见降显存手段 |
| `--limit-mm-per-prompt`（配置项 `limit_mm_per_prompt`） | 限制每条 prompt 的多模态输入数量，设 0 可整类关闭 |
| `--mm-processor-cache-gb`（配置项 `mm_processor_cache_gb`） | 多模态缓存预算，默认 4 GiB，设 0 可关 |
| `--compilation-config`（配置项 `compilation_config`） | 控制 CUDA graph 捕获尺寸，在速度和显存之间取舍 |
| `--enforce-eager` | 跳过编译与 CUDA graph 捕获，启动最快、稳态解码变慢 |
| `-O0` / `-O1` / `-O2` / `-O3` | 优化档位，用启动时间换性能 |
| `--chat-template` | 模型不带 chat template 时手动指定 Jinja 模板 |
| `--chat-template-content-format` | 覆盖内容格式（`string` / `openai`）的自动探测结果 |
| `--generation-config vllm` | 不用模型仓库的 `generation_config.json`，改用 vLLM 默认采样参数 |
| `--attention-backend` | 手动指定注意力后端，如 CUDA 上的 `FLASH_ATTN` / `FLASHINFER` |
| `--api-server-count` | API server 横向扩展，输入处理成为瓶颈时用（仅在线推理） |
| `--enable-offline-docs` | 内网环境也能打开 FastAPI 的 `/docs` |
| `--numa-bind` / `--numa-bind-nodes` / `--numa-bind-cpus` | 多路服务器上把 worker 绑到最近的 NUMA 节点 |
| `--tokens-only` | 只做 token 进出、由外部负责渲染的模式（配 `vllm launch render`） |

环境变量（官方文档明确出现过的）：

| 变量 | 作用 |
|---|---|
| `HF_TOKEN` | 拉取受限模型 |
| `VLLM_API_KEY` | 服务端鉴权 key |
| `VLLM_USE_MODELSCOPE=True` | 改从 ModelScope 取模型 |
| `VLLM_CACHE_ROOT` | 编译缓存目录，默认 `~/.cache/vllm` |
| `VLLM_FORCE_AOT_LOAD=1` | 缓存未命中时报错，而不是静默重编译 |
| `VLLM_ENABLE_CUDA_COMPATIBILITY=1` | 宿主驱动比镜像新时启用兼容库 |
| `VLLM_USE_FASTOKENS=1` | 启用 fastokens 分词后端（需另装 `fastokens>=0.2.0`） |
| `VLLM_WORKER_MULTIPROC_METHOD=spawn` | Python API 下配合 NUMA 绑定使用 |
| `VLLM_MEDIA_LOADING_THREAD_COUNT` | 多模态媒体加载线程数，API server 扩展时要留意 |
| `VLLM_CPU_KVCACHE_SPACE` | CPU 后端的 KV 缓存大小，默认 4 GiB |
| `VLLM_CPU_OMP_THREADS_BIND` | CPU 后端 OpenMP 线程绑定，默认 `auto`，可设 `nobind` |
| `VLLM_CPU_NUM_OF_RESERVED_CPU` / `CPU_VISIBLE_MEMORY_NODES` | CPU 后端预留核数与可见内存节点 |
| `CUDA_VISIBLE_DEVICES` | 指定使用哪些 GPU（官方建议用它而不是在初始化前调 `torch.accelerator.set_device_index`） |
| `MAX_JOBS` | 源码编译并发数，低配机器调小 |
| `VLLM_TARGET_DEVICE=empty` | 非 Linux 上只做导入验证的构建 |
| `VLLM_ENABLE_SCALE_OUT_ENDPOINTS=1` | 打开 `/inference/v1/generate` 等 scale-out 端点（默认关闭） |
| `VLLM_SERVER_DEV_MODE=1` | 打开开发端点（清缓存、暂停、改权重等）。官方明确警告不要用于生产 |

---

## 三、离线推理 vs 在线服务怎么选

| 维度 | 离线 `LLM` | 在线 `vllm serve` |
|---|---|---|
| 入口 | Python `from vllm import LLM, SamplingParams` | HTTP，OpenAI 兼容 |
| 适合 | 数据集评测、批量数据加工、一次性跑完 | 有并发用户/上游服务持续调用 |
| 生命周期 | 脚本进程内，跑完即退 | 常驻进程 |
| 并行参数 | 构造 `LLM(...)` 时传 | CLI 参数 |
| chat 模型 | `generate()` 不套模板，要用 `llm.chat()` 或自己套 | 服务端自动套 tokenizer 里的模板 |

---

## 四、出问题时的排查顺序

1. **先确认是不是环境问题**。干净环境 + 匹配的 CUDA/torch 是前提；`pip install` 装的 vLLM 与已有 torch 冲突是最常见的「import 就崩」。
2. **再看显存**。启动 OOM：换量化版本、降 `--max-model-len`、加 `--tensor-parallel-size`。运行中 preemption：调 `--gpu-memory-utilization` 或降 `--max-num-seqs` / `--max-num-batched-tokens`。
3. **再看 CPU**。GPU 利用率上不去、调度迟钝，先数物理核够不够 `2 + N`。
4. **再看容器**。张量并行报共享内存错误 → `--ipc=host`；驱动比镜像老 → `VLLM_ENABLE_CUDA_COMPATIBILITY=1`。
5. **最后看模型配置**。chat 请求全错 → 缺 chat template；采样行为和预期不符 → 检查 `generation_config.json`。
6. **别猜参数**。`vllm serve --help` 与官方配置文档永远优先于任何二手资料，包括本文件。

---

## 五、本文件不覆盖的部分

- 具体版本的下载地址与发布日期（上游迭代快，请以仓库 releases 为准）。
- 各模型的最优参数组合（模型相关，官方提供的是 Recipes 与基准数据）。
- 训练、微调、权重合并流程。
- 生产网关侧的多租户、计费、限流设计。
