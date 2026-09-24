# 三剪客 · PDF 转 Markdown Skill

教你用 marker 把 PDF（以及图片、Office、EPUB 等）转成结构化 Markdown / JSON / HTML：怎么准备推理后端、常用命令怎么写、许可边界在哪、哪些情况转不好。

---

## 前置条件

- **Python 3.10+** 与 PyTorch。
- 安装：`pip install marker-pdf`；要处理 PDF 以外的格式加 `pip install marker-pdf[full]`。
- **必须有可用的推理后端**：NVIDIA GPU 路径需要 Docker + NVIDIA Container Toolkit（后端走 vLLM）；CPU / Apple Silicon 路径需要 llama.cpp 的 `llama-server`。
- 首次使用会自动下载模型权重，需要网络与磁盘空间。
- **许可提示**：代码是 Apache 2.0，模型权重使用修改过的 OpenRAIL-M 许可，仅研究、个人使用以及融资 / 营收低于 500 万美元的初创免费；商用超出范围需另行取得许可。
- `--use_llm` 需要对应 LLM 服务的 Key（默认走云端），内网可改用 Ollama 等本地服务。

---

## 使用

1. 先确认参数：`marker_single --help`、`config --help`（版本间差异较大）。
2. 单文件：`marker_single file.pdf --output_dir ./out`。
3. 批量：`marker /path/to/folder --output_dir ./out --workers 4`，续跑加 `--skip_existing`。
4. 扫描件：`marker_single scan.pdf --force_ocr`。
5. 结构化输出：`--output_format json` 或 `--output_format chunks`（后者适合 RAG 切片）。
6. 嵌进管线：用 Python API（`PdfConverter` + `create_model_dict`），模型只加载一次。
7. 参数、环境变量、输出结构细节见 `references/cli-and-api.md`。

完整操作步骤、常见坑、能力边界见 `SKILL.md`。

---

## 依赖

- `marker-pdf`（含 `marker_single` / `marker` / `marker_server` / `marker_gui` 等入口）。
- PyTorch；推理后端：Docker + NVIDIA Container Toolkit（GPU）或 llama.cpp（CPU / Apple Silicon）。
- `marker-pdf[full]`：处理 PPTX / DOCX / XLSX / HTML / EPUB 等非 PDF 格式。
- 可选：`streamlit` + `streamlit-ace`（界面）、`uvicorn` + `fastapi` + `python-multipart`（HTTP 服务）。
- 可选：LLM 服务的 API Key，或本地 Ollama。

---

## 安全

- 不内嵌任何密钥；`--gemini_api_key` 等凭证由使用方自行提供，不要写进脚本或仓库。
- 本地转换不联网；`--use_llm` 会把文档内容发给所选 LLM 服务，**敏感文档请改用本地模型（如 Ollama）或先做脱敏**。
- 首次运行会下载模型权重，后续可离线使用。
- 项目自带 HTTP 服务只暴露少量参数且不够健壮，不要直接暴露到公网。
- 商用前确认模型权重许可范围（见「前置条件」）。
- Skill 本体只包含文档，不含上游项目的源代码；上游代码的问题请走上游仓库的 Issues。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`marker`
- 仓库：https://github.com/datalab-to/marker

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
