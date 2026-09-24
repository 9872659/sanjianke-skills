# marker 参数与接口速查

参数来自上游仓库 README 与 `marker_single --help` 口径。**该项目版本间变化较大**，动手前先跑 `marker_single --help` 和 `config --help`，以实际输出为准。

## 一、两个命令入口

| 命令 | 用途 |
|---|---|
| `marker_single /path/to/file.pdf` | 转单个 PDF 或图片 |
| `marker /path/to/input/folder` | 批量转整个文件夹，支持与 `marker_single` 相同的选项 |
| `marker_gui` | 交互式界面（需 `pip install -U streamlit streamlit-ace`） |
| `marker_server --port 8001` | 简易 HTTP 服务（需 `pip install -U uvicorn fastapi python-multipart`） |
| `config --help` | 列出所有可用的 builder / processor / converter 及其配置项，用于生成 `--config_json` |

## 二、`marker_single` 常用选项

| 选项 | 说明 |
|---|---|
| `--mode balanced\|fast` | 转换模式。GPU 默认 `balanced`（VLM 做版面 + 整页重 OCR，质量最高）；CPU / MPS 默认 `fast`（轻量版面检测 + pdftext 文本层，VLM 只用于公式与坏块修复，速度快） |
| `--disable_ocr` | 完全关闭 VLM 调用，纯文本层提取；公式与扫描页会被跳过 |
| `--page_range TEXT` | 处理指定页，逗号与区间混用，如 `"0,5-10,20"` |
| `--output_format markdown\|json\|html\|chunks` | 输出格式 |
| `--output_dir PATH` | 输出目录 |
| `--paginate_output` | 分页标记：`\n\n{PAGE_NUMBER}` + 48 个 `-` + `\n\n` |
| `--use_llm` | 用 LLM 提升精度（跨页表格合并、行内公式、表单取值等） |
| `--force_ocr` | 全篇强制 OCR，即使有可提取文本 |
| `--block_correction_prompt` | LLM 模式下的修正提示，可定制输出格式或逻辑 |
| `--strip_existing_ocr` | 丢弃文档中已有的 OCR 文本，重新识别 |
| `--redo_inline_math` | 追求最高质量的行内公式（配合 `--use_llm`） |
| `--disable_image_extraction` | 不抽图片；若同时用 `--use_llm`，图片会被替换成描述 |
| `--keep_pageheader_in_output` / `--keep_pagefooter_in_output` | 保留页眉 / 页脚（默认移除） |
| `--debug` | 调试模式：保存每页版面与文本标注图，并输出额外坐标信息 |
| `--processors TEXT` | 用完整模块路径覆盖默认 processors，逗号分隔 |
| `--config_json PATH` | 传入 JSON 配置文件做更细的调整 |
| `--converter_cls` | `marker.converters.pdf.PdfConverter`（默认，整篇）或 `marker.converters.table.TableConverter`（只抽表） |
| `--llm_service` | 使用 `--use_llm` 时的服务类，默认 `marker.services.gemini.GoogleGeminiService` |

## 三、批量相关选项（`marker` 命令）

| 选项 | 说明 |
|---|---|
| `--workers N` | 并行转换 worker 数；默认自动设定，调高提升吞吐但更吃 CPU |
| `--skip_existing` | 跳过输出目录里已有结果的文件，用于断点续跑 |
| `--max_files N` | 本次最多转换多少个文件 |
| `--disable_multiprocessing` | 单进程运行 |
| `--num_chunks N --chunk_idx I` | 多机分片：分 N 片，本机处理第 I 片，每片各自起推理服务 |

所有 worker 共享同一个推理服务；父进程会自动按服务容量分配并发额度（在途请求约为容量的 1.5 倍），因此**增加 worker 不会把服务压爆**。`--disable_ocr` 时完全不启动推理服务，并行度只按 CPU 核数决定。

## 四、推理后端与环境变量

首次使用会自动拉起 surya 推理服务：NVIDIA GPU 上走 vLLM（需 Docker + NVIDIA Container Toolkit），其它环境走 llama.cpp（需 `llama-server`）。

| 环境变量 | 作用 |
|---|---|
| `SURYA_INFERENCE_URL` | 指向已经跑着的服务，如 `http://host:port/v1`，跳过自动拉起 |
| `SURYA_INFERENCE_BACKEND` | `vllm` 或 `llamacpp` |
| `SURYA_INFERENCE_PARALLEL` | 并发请求数；默认按服务容量自动伸缩，仅在需要覆盖时手动设整数 |
| `SURYA_INFERENCE_KEEP_ALIVE` | 调用之间是否保留服务常驻 |
| `VLLM_GPUS` | 推理服务使用的 GPU 索引，如 `0,1,2,3` |
| `TORCH_DEVICE` | 强制把本地小模型（OCR 错误检测等）放到指定设备；VLM 的位置由上面几个变量控制 |

批量规模参考（官方口径，1000 份文档级别）：

- 单 GPU 机器：`marker /folder --output_dir out`，默认即可；语料多为电子版可加 `--mode fast` 省钱提速。
- 多 GPU 单机：`VLLM_GPUS=0,1,2,3 marker /folder ...`。
- 多机：每台机器 `--num_chunks <节点数> --chunk_idx <本机序号>`。
- 纯 CPU / 不用 VLM：`marker /folder --disable_ocr`。

## 五、LLM 服务（配合 `--use_llm`）

| 服务 | 关键参数 | `--llm_service` |
|---|---|---|
| Gemini（默认） | `--gemini_api_key` | 默认值 |
| Google Vertex | `--vertex_project_id` | `marker.services.vertex.GoogleVertexService` |
| Ollama（本地） | `--ollama_base_url`、`--ollama_model` | `marker.services.ollama.OllamaService` |
| Claude | `--claude_api_key`、`--claude_model_name` | `marker.services.claude.ClaudeService` |
| OpenAI 兼容端点 | `--openai_api_key`、`--openai_model`、`--openai_base_url` | `marker.services.openai.OpenAIService` |
| Azure OpenAI | `--azure_endpoint`、`--azure_api_key`、`--deployment_name` | `marker.services.azure_openai.AzureOpenAIService` |
| OpenRouter | `--openrouter_api_key`（或 `OPENROUTER_API_KEY`）、`--openrouter_model`、`--openrouter_base_url` | `marker.services.openrouter.OpenRouterService` |

## 六、Python API

```python
# 整篇转换
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

converter = PdfConverter(artifact_dict=create_model_dict())
rendered = converter("FILEPATH")
text, _, images = text_from_rendered(rendered)
# markdown 输出：rendered.markdown / rendered.metadata / rendered.images
# json 输出：rendered.children / rendered.block_type / rendered.metadata
```

```python
# 自定义配置
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser

config = {"output_format": "json", "ADDITIONAL_KEY": "VALUE"}
config_parser = ConfigParser(config)

converter = PdfConverter(
    config=config_parser.generate_config_dict(),
    artifact_dict=create_model_dict(),
    processor_list=config_parser.get_processors(),
    renderer=config_parser.get_renderer(),
    llm_service=config_parser.get_llm_service(),
)
rendered = converter("FILEPATH")
```

```python
# 按块操作：例如取出文档里所有表单块
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.schema import BlockTypes

converter = PdfConverter(artifact_dict=create_model_dict())
document = converter.build_document("FILEPATH")
forms = document.contained_blocks((BlockTypes.Form,))
```

其它转换器：

```python
from marker.converters.table import TableConverter   # 只转表格
from marker.converters.ocr import OCRConverter       # 只做 OCR
```

- `TableConverter` 支持配置 `force_layout_block=Table`，跳过版面检测、直接假定整页是表格；表格以 HTML（`<table>`）块输出，`output_format=json` 能得到带页码与包围盒的表格块。
- `OCRConverter` 配 `--keep_chars` 可保留单字符与包围盒（仅对电子版 PDF 有效；走 VLM 的页面只返回块级 HTML，没有字符级坐标）。

对应 CLI：

```bash
marker_single file.pdf --use_llm --force_layout_block Table --converter_cls marker.converters.table.TableConverter --output_format json
marker_single file.pdf --converter_cls marker.converters.ocr.OCRConverter
```

## 七、输出格式要点

- **markdown**：图片链接（图片存同目录）、格式化表格、`$$` 包裹的 LaTeX 公式、三反引号代码块、脚注上标。
- **html**：图片用 `img` 标签，公式用 `<math>`，代码在 `pre` 里。
- **json**：树形结构，顶层是页，每页含 `id`、`block_type`、`html`（里面的 `content-ref` 需按子块递归替换）、`polygon`（四角坐标，左上起顺时针）、`children`；子块额外有 `section_hierarchy`（`1` 表示 h1）与 `images`（base64）。块类型包括 `Line`、`Span`、`FigureGroup`、`TableGroup`、`ListGroup`、`PictureGroup`、`Page`、`Caption`、`Code`、`Figure`、`Footnote`、`Form`、`Equation`、`Handwriting`、`TextInlineMath`、`ListItem`、`PageFooter`、`PageHeader`、`Picture`、`SectionHeader`、`Table`、`Text`、`TableOfContents`、`Document`。
- **chunks**：把 json 拍平成一个列表，只保留每页顶层块，且每块自带完整 HTML，便于直接切片进 RAG。
- **metadata**：所有格式都附带，含 `table_of_contents`（标题、层级、页 id、坐标）与 `page_stats`（每页的提取方式与块计数）。

## 八、HTTP 服务

```bash
pip install -U uvicorn fastapi python-multipart
marker_server --port 8001          # 用 --host 改绑定地址
```

```python
import json, requests
post_data = {
    "filepath": "FILEPATH",
    # 只接受：page_range, mode, force_ocr, paginate_output, output_format
}
requests.post("http://localhost:8001/marker", data=json.dumps(post_data)).json()
```

`http://localhost:8001/docs` 有端点说明。注意：`--use_llm` 与 `--disable_ocr` **不通过**这个接口暴露；官方明确说该服务不够健壮，只适合小规模使用。

## 九、排错速记

- 精度不满意：`--use_llm`（需配置 LLM Key），或直接换 `--mode balanced`。
- 文字乱码：`--force_ocr` 重新识别整篇。
- 显存不足：降低 `--workers`，或把长 PDF 拆成多个文件。
- 需要看清版面判断：`--debug` 会输出每页的版面与文本标注图。
