# 三剪客 · 大模型训练加速 Skill

用 ZeRO 切分优化器状态与梯度、把显存挪到 CPU/NVMe，让原本 OOM 的模型跑起来；覆盖安装、配置、单机与多机启动命令和踩坑清单。

---

## 前置条件

- 必须先装 PyTorch，再装 DeepSpeed（顺序不能反）；完整特性建议 PyTorch >= 2.0。
- CUDA 或 ROCm 编译器（`nvcc` / `hipcc`）与 ninja，供扩展 JIT 编译使用。
- 多机训练需要互通的网络；默认启动模式还要求免密 SSH，没有则改用 `--no_ssh` 逐节点启动。
- 用 offload / ZeRO-Infinity 时预留足够的 CPU 内存与本地 NVMe 空间。
- Windows 需要 Visual C++ build tools，并注意官方声明不支持 AIO 与 GDS。

---

## 使用

本 Skill 按「装 → 自检 → 接代码 → 写配置 → 启动 → 存检查点」的顺序组织：

1. 装：先 PyTorch 后 `pip install deepspeed`。
2. 自检：`ds_report` 确认本机可用的扩展/ops。
3. 接代码：把训练入口换成 `deepspeed.initialize(...)`，训练循环保持 forward / backward / step 三步；原来手写的 `init_process_group` 换成 `deepspeed.init_distributed()`。
4. 写配置：准备 `ds_config.json`（batch size、optimizer、fp16/bf16、`zero_optimization`）。
5. 启动：单机 `deepspeed --include localhost:0,1 ...`；多机加 `--hostfile`；无免密 SSH 用 `--no_ssh --node_rank --master_addr --master_port`。
6. 检查点：`save_checkpoint` / `load_checkpoint` 必须所有进程都调用，不能只在 rank 0。
7. 传环境变量：需要的自定义变量写进 `.deepspeed_env`，或用 `DS_ENV_FILE` 指定文件。

---

## 依赖

- PyTorch（先装），建议 >= 2.0。
- CUDA / ROCm 编译器与 ninja。
- 多机场景的网络与 SSH 配置，或 `--no_ssh` 模式所需的主节点地址与端口。
- 官方主要测试硬件：NVIDIA Pascal / Volta / Ampere / Hopper，AMD MI100 / MI200；其他加速器由贡献者支持，验证程度不一。
- 充足的本地磁盘：检查点与 offload 场景会显著占用空间。

---

## 安全

- 不内嵌任何密钥
- 多机模式会通过 SSH 在远端节点拉起训练进程，需自行控制密钥范围与主机可信边界。
- 从私有源拉模型/数据时用独立的只读凭证，避免把长期 token 写进配置文件。
- 检查点目录里是完整模型权重，按核心资产对待，控制目录权限并做备份。
- 按官方声明使用受支持的特性组合，不要在 Windows 上强行启用 AIO / GDS。
- 训练前先小规模跑通配置，再放到集群上长时间运行。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`DeepSpeed`
- 仓库：https://github.com/deepspeedai/DeepSpeed

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
