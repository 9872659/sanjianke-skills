# 三剪客 · 大规模并行训练 Skill

单卡装不下的模型，用数据 / 流水线 / 张量 / 序列并行与 ZeRO、异构内存管理拆到多卡多机上去训练。

---

## 前置条件

- Linux 操作系统（硬性要求，官方目前只支持 Linux）。
- PyTorch >= 2.2、Python >= 3.7、CUDA >= 11.0。
- NVIDIA GPU，计算能力 >= 7.0（V100 / RTX20 及以上）。
- 多机训练需要节点间网络互通，以及一份写有真实主机名或 IP 的 hostfile。
- 走 Docker 需要本机 Docker 与 Nvidia Docker Runtime。

---

## 使用

1. 按 `SKILL.md` 的「安装」一节装好 Colossal-AI；用 fused optimizer 必须走 `BUILD_EXT=1`。
2. 跑 `colossalai check -i` 自检环境。
3. 把并行策略写进配置（`parallel = dict(pipeline=..., tensor=dict(mode=..., size=...))`）。
4. 用 `colossalai run --nproc_per_node <本机 GPU 数> train.py --config config.py` 启动；多机再加 `--hostfile`。
5. 出现 OOM 时按 `SKILL.md`「常见坑」表逐项排查，优先考虑换用带卸载的脚本变体。

`SKILL.md` 里有完整的命令、配置片段、坑位对照表与自检清单。

---

## 依赖

- Colossal-AI 本体（PyPI 的 `colossalai` / `colossalai-nightly`，或源码安装）。
- PyTorch、CUDA 运行时与 NVIDIA 驱动。
- 训练任务自身的依赖：数据集加载、tokenizer、模型定义等。
- 可选：Docker 与 Nvidia Docker Runtime。

---

## 安全

- 不内嵌任何密钥。
- `colossalai run` 会拉起多个训练进程，属于长时任务；确认目标机器与卡是你要用的那台再启动。
- 多机训练会在节点间建立 TCP 连接并在 hostfile 列出的机器上执行命令，hostfile 必须来自可信来源。
- 训练脚本会写检查点与日志，注意落盘路径与磁盘配额，避免写满系统盘。
- 使用官方 Docker 镜像或自行构建镜像时，注意镜像来源可信；不要在镜像里固化私有凭证。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`ColossalAI`
- 仓库：https://github.com/hpcaitech/ColossalAI

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
