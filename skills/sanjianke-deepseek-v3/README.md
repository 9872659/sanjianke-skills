# 三剪客 · DeepSeek 开源大模型 Skill

DeepSeek-V3 的模型权重仓库使用说明：不是命令行工具，而是 671B 总参数 / 37B 激活的权重与若干自建部署路径。

---

## 前置条件

- **先确认是否真的需要自建**。官方在 `platform.deepseek.com` 提供 OpenAI 兼容 API，绝大多数需求到这一步就结束了。
- 自建需要多卡 GPU 集群：权重总量 685B，按 FP8 每参约 1 字节粗估就要 ~700GB 显存（官方 Demo 示例为 2 机 × 8 卡）。
- 几百 GB 可用磁盘空间与足够带宽；转换 BF16 还要更多。
- 官方 Demo 仅支持 **Linux + Python 3.10**，依赖版本钉死。
- 模型使用受 DeepSeek Model License 约束（代码部分是 MIT）。

---

## 使用

拿权重：

```bash
pip install -U "huggingface_hub[cli]"
hf download deepseek-ai/DeepSeek-V3 --local-dir ./DeepSeek-V3
```

然后用官方列出并推荐的推理框架之一（SGLang / vLLM / LMDeploy / TensorRT-LLM / LightLLM）部署——**启动命令以各框架当前官方文档为准**，官方 README 对这些路径给的也是指向各自文档的链接，而非写死的一行命令。

只有做最小验证时才走官方 Demo（Linux、2 机 × 8 卡）：

```shell
git clone https://github.com/deepseek-ai/DeepSeek-V3.git
cd DeepSeek-V3/inference && pip install -r requirements.txt

python convert.py --hf-ckpt-path /path/to/DeepSeek-V3 \
                  --save-path /path/to/DeepSeek-V3-Demo \
                  --n-experts 256 --model-parallel 16

torchrun --nnodes 2 --nproc-per-node 8 --node-rank $RANK --master-addr $ADDR \
  generate.py --ckpt-path /path/to/DeepSeek-V3-Demo \
  --config configs/config_671B.json --interactive --temperature 0.7 --max-new-tokens 200
```

完整的六块内容（定位 / 什么时候用·不用 / 安装 / 常用操作 / 常见坑 / 能力边界）见 `SKILL.md`。

---

## 依赖

- 权重：Hugging Face 上的 `deepseek-ai/DeepSeek-V3` 或 `deepseek-ai/DeepSeek-V3-Base`。
- 官方 Demo 路径：Linux + Python 3.10，`torch==2.4.1`、`triton==3.0.0`、`transformers==4.46.3`、`safetensors==0.4.5`。
- 生产路径：自选一个推理框架（SGLang / vLLM / LMDeploy / TRT-LLM / LightLLM），各框架有自己的安装要求。
- Hugging Face Transformers **尚未直接支持**该模型，不能 `from_pretrained` 直接加载。

---

## 安全

- 不内嵌任何密钥
- API Key 与 Hugging Face token 走环境变量，不要写进代码与提交历史
- 权重需从官方来源下载并校验，不要执行来源不明的转换脚本
- 自建推理服务对公网暴露前必须自行加鉴权与限流
- 商用前阅读 DeepSeek Model License 原文，确认条款与合规要求

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`DeepSeek-V3`
- 仓库：https://github.com/deepseek-ai/DeepSeek-V3

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
