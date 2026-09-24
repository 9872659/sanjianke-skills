# 三剪客 · PDF 高精度转 Markdown Skill

论文、研报、合同、试卷这类复杂 PDF 的解析利器：不是简单抽文本，而是重建标题层级、表格、公式和阅读顺序，输出能直接进 RAG 的 Markdown / JSON。纯 CPU 也能跑。

---

## 前置条件

- Python 3.10~3.13（Windows 仅 3.10~3.12）；macOS 需 14.0 及以上。
- 先想清楚用哪个后端：`pipeline`（纯 CPU 可跑）/ `vlm-engine` / `hybrid-engine` / `*-http-client`。
- 高精度后端有硬件门槛：显存 8GB 起、内存建议 32GB 以上、磁盘建议 SSD。
- Docker 只用于 Linux 或带 WSL2 的 Windows；macOS 用 pip / uv 装。
- 首次运行要下载模型权重，需要网络与磁盘空间。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
pip install --upgrade pip
pip install uv
uv pip install -U "mineru[all]"

# GPU 可用时
mineru -p <input_path> -o <output_path>

# 纯 CPU
mineru -p <input_path> -o <output_path> -b pipeline
```

起服务：

```bash
mineru-api --host 127.0.0.1 --port 8000     # FastAPI，文档在 /docs
mineru-gradio                               # WebUI
mineru-router                               # 多服务 / 多 GPU 统一入口
```

支持的输入是 PDF、图片、DOCX、PPTX、XLSX 的文件或目录。完整的 CLI 参数与环境变量清单以 `mineru --help` 和官方「命令行工具使用说明」文档为准。

---

## 依赖

- Python 3.10~3.13（Windows 因 `ray` 限制只能用 3.10~3.12）
- `mineru[all]` 及 vllm 等推理依赖（Docker 方式已内置）
- 可选：OpenAI 兼容推理服务（vLLM / SGLang / LMDeploy）用于 http-client 后端
- 可选：Docker（仅 Linux / WSL2）

---

## 安全

- 不内嵌任何密钥
- 本地部署时文档不出机器；用 http-client 或云端推理服务时文档内容会发往该服务，需自行评估
- 起 `mineru-api` / `mineru-router` / Gradio 服务时注意监听地址，别把无鉴权的解析接口暴露到公网
- 连接带鉴权的远端服务时用 `MINERU_VL_API_KEY` 注入 Key，不要写进脚本或镜像

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`MinerU`
- 仓库：https://github.com/opendatalab/MinerU

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
