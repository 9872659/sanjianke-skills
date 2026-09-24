# 三剪客 · 文档转结构化数据 Skill

把 PDF、Word、PPT、Excel、HTML、EPUB 等文档解析成结构化数据：标题层级、阅读顺序、表格结构、图片与公式位置，并导出 Markdown / HTML / JSON / DocTags，或直接切成 RAG 可用的 chunk。

---

## 前置条件

- **Python 3.10 以上**（3.9 自 docling 2.70.0 起不再支持；3.13 需 ≥ 2.18.0，3.14 需 ≥ 2.59.0）。
- **PDF / 图片管线首次运行要从 Hugging Face 下模型权重**，内存与磁盘占用都不小。不能出网的环境请先在有网机器上 `docling-tools models download`，再把模型目录拷进去，用 `--artifacts-path` 指过去。
- **docx / pptx / xlsx / html / md 这类声明式格式不需要模型**，装完就能用。
- **默认不允许调用远程服务**（防数据外发）。要用远程 VLM 或远程图片描述，必须显式加 `--enable-remote-services`。
- macOS Intel 机器需要特殊版本组合（PyTorch 停供 Intel Mac wheel）；无头容器注意 OpenCV 的 `libGL` 依赖。
- 上游仓库早年挂在 `DS4SD` 组织，现已迁到 `docling-project`，旧教程链接可能失效。

---

## 使用

最短路径：

```bash
# 1. 装
pip install docling
# CPU-only Linux 建议：pip install docling --extra-index-url https://download.pytorch.org/whl/cpu
# macOS Intel：pip install "docling[mac_intel]"  并保证 numpy<2.0.0

# 2. 自检
docling --version

# 3. 转一份文档（默认出 Markdown 到当前目录）
docling convert report.pdf
docling convert https://example.com/paper.pdf --output ./out/
docling convert ./docs/ --output ./out/

# 4. 一次出多种格式
docling convert report.pdf --to md,json,doctags --output ./out/

# 5. 直接切 chunk 喂 RAG
docling convert report.pdf --to chunks --chunks-type hybrid --chunks-max-tokens 512

# 6. 扫描件指定 OCR 与语言
docling convert scan.pdf --ocr-engine tesseract --ocr-lang chi_sim,eng
```

Python 里用（推荐方式，方便接自己的流水线）：

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("report.pdf")        # 本地路径或 URL
print(result.document.export_to_markdown())
```

更细的 API 用法（管线选项、`convert_all` 批量、chunker、遍历表格与图片、完全离线配置、报错定位顺序）见 `references/python-api.md`。

---

## 依赖

| 项 | 说明 |
|---|---|
| Python | 3.10 以上 |
| 核心依赖 | PyTorch（CPU-only 机器建议换 PyTorch 的 CPU 索引以减小体积） |
| 平台 | macOS / Linux / Windows，x86_64 与 arm64 |
| 模型权重 | PDF 管线首次运行需联网下载；声明式格式不需要 |
| 网络 | 首次下模型需要出网，之后可完全离线（`--artifacts-path`） |
| 加速器 | 可选 CUDA / MPS / XPU；CPU 也能跑，`--num-threads` 默认 4 |
| 可选 extras | `vlm`、`asr`、`easyocr`、`rapidocr`、`tesserocr`、`ocrmac`、`htmlrender`、`feat-ocr-nemotron` |
| 可选系统依赖 | 用 Tesseract 引擎时要系统装 tesseract，并设 `TESSDATA_PREFIX`（结尾带 `/`） |
| 账号 / Key | 本地转换不需要；只有 `convert-remote` 对接自建服务时才需要 |

---

## 安全

- 不内嵌任何密钥。本地转换全程不需要 Key。
- **默认不外发数据**：Docling 默认不联系任何远程服务，官方明确它可在气隙环境运行。数据外发只有三个口子——把 URL 当输入、打开 `--enable-remote-services`、使用 `convert-remote`。处理敏感文档时逐个确认。
- 模型权重默认从 Hugging Face 下载；如需经过内网镜像或完全离线，用 `docling-tools models download` + `--artifacts-path`。
- 加密 PDF 用 `--pdf-password` 传入，注意它可能留在 shell 历史里；建议用环境变量或配置文件间接传入。
- 输出物（Markdown / JSON / 导出的 PNG / profiling json）会落在本地磁盘，可能包含文档全文；敏感场景记得清理输出目录与模型缓存。
- 本 Skill 不代理转发、不代收费用，也不提供任何云端算力。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`docling`
- 仓库：https://github.com/docling-project/docling

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
