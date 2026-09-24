# Docling Python API 速查

> 覆盖 `DocumentConverter` 的用法、管线选项、批量转换、chunking、遍历文档结构、离线配置与报错定位。
> 所有类名与方法名都来自官方参考文档；字段级细节以官方「Pipeline options」与「Docling Document」参考页为准。

## 一、最小可用

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("report.pdf")      # 本地路径或 http(s) URL
doc = result.document

print(doc.export_to_markdown())
print(doc.export_to_text())
```

一次转换的结果对象（`ConversionResult`）里，常用的字段：

| 字段/方法 | 说明 |
|---|---|
| `document` | 解析出来的 `DoclingDocument` |
| `status` | `ConversionStatus`，取值 `SUCCESS` / `PARTIAL_SUCCESS` / `FAILURE` / `SKIPPED` / `PENDING` / `STARTED` |
| `input` | 本次处理的输入（格式、路径等） |
| `pages` | 页级结果（每页的解析产物） |
| `errors` | 错误列表；配套 `has_errors` / `has_parse_errors` / `has_inference_errors` / `has_timeout_errors` |
| `timings` | 各阶段耗时 |
| `confidence` | 置信度信息 |
| `save()` / `load()` | 结果对象的落盘与读回 |

**判断成功不能只看有没有抛异常**：一条命令里某几页失败时状态可能是 `PARTIAL_SUCCESS`，务必检查 `status` 与 `errors`。

## 二、按格式定制管线

PDF 与图片走管线（可配 OCR、表格、设备、artifacts 等），其他声明式格式（docx / pptx / xlsx / html / md…）不需要模型，也没有这些开关。

```python
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.ocr_options = TesseractOcrOptions()        # 换 OCR 引擎
pipeline_options.ocr_options.lang = ["zh-Hans", "en"]       # OCR 语言，统一用 BCP-47 词汇表
pipeline_options.artifacts_path = "/path/to/models"         # 离线：指向本地模型目录

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)
result = converter.convert("scan.pdf")
```

要点：

- `ocr_options` 决定引擎。官方列出的可选类型包括 `EasyOcrOptions`、`TesseractOcrOptions`、`TesseractCliOcrOptions`、`OcrMacOptions`、`RapidOcrOptions`、`OnnxtrOcrOptions`、`NemotronOcrOptions`；用哪个要先把对应 extra 或系统依赖装好。
- **OCR 语言不做回退**：所选引擎没有该语言模型时会报错，不会自动换一个相近的。
- 表格、代码、公式、图片分类/描述、图表抽取在 Python 侧同样是"开了才跑"，语义与命令行的 `--tables`、`--enrich-*` 一一对应；具体属性名见官方 Pipeline options 参考页（版本间可能调整，建议以你装的版本为准）。
- 设备与加速：`AcceleratorOptions`（来自 `docling.datamodel.accelerator_options`）可指定加速器；CUDA 上想启用 Flash Attention 2，可设环境变量 `DOCLING_CUDA_USE_FLASH_ATTENTION2=1`，或在 `AcceleratorOptions(cuda_use_flash_attention2=True)` 里打开（需要额外装 `flash-attn`）。
- 用远程模型（远程 VLM、远程图片描述等）必须显式允许远程服务（Python 侧 `enable_remote_services`，对应命令行 `--enable-remote-services`）。**默认不允许，这是防数据外发的设计。**

## 三、批量转换

```python
from pathlib import Path
from docling.document_converter import DocumentConverter

converter = DocumentConverter()

# 流式处理：边转换边处理结果，不必把所有文档同时读进内存
results = converter.convert_all(
    [Path("docs/a.pdf"), Path("docs/b.docx")],
    raises_on_error=False,      # 单个失败不要中断整批
)

for res in results:
    if res.status.name != "SUCCESS":
        print("跳过失败文档：", res.input, res.errors)
        continue
    out = Path("out") / (Path(str(res.input.file)).stem + ".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(res.document.export_to_markdown(), encoding="utf-8")
```

另外两个入口：

- `converter.convert_string(...)`：直接转换内存里的字符串内容（不需要先落盘）。
- `converter.initialize_pipeline(...)`：提前把管线模型加载好，避免第一批文档把加载时间算进去；`initialized_pipelines` 可以查看已初始化的管线，`allowed_formats` / `format_to_options` 可以查看当前转换器支持的格式与选项。

## 四、chunking：把文档切成 RAG 可用的块

```python
from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker

doc = DocumentConverter().convert("report.pdf").document

chunker = HybridChunker()                       # 默认按结构切，再按 token 上限细化
for chunk in chunker.chunk(dl_doc=doc):
    text = chunker.serialize(chunk=chunk)       # 该块的文本
    ctx = chunker.contextualize(chunk=chunk)    # 带上下文/元数据的文本，适合喂 embedding 模型
    print(ctx)
    print("---")
```

三种 chunker：

| 类 | 切法 | 适用 |
|---|---|---|
| `HybridChunker` | 先按文档层级切，再按 tokenizer 上限拆分、并把相邻同标题的小块合并（`merge_peers` 默认 `True`，可关） | 通用 RAG，最常用 |
| `HierarchicalChunker` | 严格按检测到的文档元素一块（默认会合并列表项，可用 `merge_list_items` 关掉） | 要"一个元素一块"的可控场景 |
| `LineBasedTokenChunker` | 保行边界，只在单行自身超限时才拆行 | 表格、代码、日志、列表等结构化内容 |

几个参数：

- `--chunks-max-tokens` 对应 chunker 的 token 上限；不设就用 tokenizer 自身上限。
- 表格跨块时，`repeat_table_header`（默认 `True`）会把表头重复到每一块；`omit_header_on_overflow`（默认 `False`）允许在"带表头就超限、不带刚好"时省掉表头。`LineBasedTokenChunker` 有对应的 `omit_prefix_on_overflow`。
- chunk 对象带 `meta`（来源条目、标题层级等信息）。**字段名随版本演进，具体结构以官方 chunking 文档为准**；用于喂模型时优先用 `contextualize()`，它已经把上下文拼进去了。

只用 `docling-core` 而不装 `docling` 时，要装 chunking extra：

```bash
pip install 'docling-core[chunking]'          # HuggingFace tokenizers
pip install 'docling-core[chunking-openai]'   # 或 tiktoken
```

导入路径对应变成 `from docling_core.transforms.chunker.hybrid_chunker import HybridChunker` / `from docling_core.transforms.chunker.line_chunker import LineBasedTokenChunker`。

## 五、遍历文档结构

`DoclingDocument` 上可直接取的集合：`texts`、`tables`、`pictures`、`groups`、`pages`、`body`、`furniture`；另有 `num_pages`、`iterate_items()`（按阅读顺序遍历）、`get_visualization()`、`export_to_element_tree()`、`filter()`、`concatenate()`。

```python
doc = converter.convert("report.pdf").document

for i, table in enumerate(doc.tables):
    print(f"表格 {i}")
    print(table.export_to_dataframe(doc=doc))   # 表格 → DataFrame（需要 pandas）
    # 也可以导出成 CSV / HTML，方法名与参数以官方 Docling Document 参考页为准

for i, pic in enumerate(doc.pictures):
    print(f"图片 {i}", pic.get_image(doc))  # 取图片对象（用 doc 解析引用）

for item, level in doc.iterate_items():     # 按阅读顺序，level 是层级
    print("  " * level, type(item).__name__)
```

导出方法（都在 `DoclingDocument` 上）：`export_to_markdown()`、`export_to_html()`、`export_to_text()`、`export_to_dict()`、`export_to_doctags()`、`export_to_vtt()`、`export_to_doclang()`，以及 `save_as_*` / `load_from_json|yaml|doctags` 系列。要把结果落盘，最稳的写法是拿导出字符串自己写文件：

```python
from pathlib import Path
Path("out.md").write_text(doc.export_to_markdown(), encoding="utf-8")
```

需要多格式产出时，命令行 `--to` 一次给多种格式通常比在 Python 里逐个导出更省事。

## 六、完全离线

官方说明 Docling 本身不依赖任何远程服务，可跑在气隙环境；唯一要做的是把模型 artifacts 位置告诉它。

```bash
# 有网的机器：把模型下到本地缓存
docling-tools models download
```

```python
from docling.datamodel.pipeline_options import PdfPipelineOptions

pipeline_options = PdfPipelineOptions(artifacts_path="/path/to/models")
# 之后按第二节的方式把 pipeline_options 塞进 PdfFormatOption
```

命令行侧等价写法是 `docling convert x.pdf --artifacts-path /path/to/models`。

## 七、报错定位顺序

按这个顺序排查，绝大多数问题能在前三步定位：

1. **看状态，不只看异常**：`result.status` 是不是 `PARTIAL_SUCCESS`？`result.errors` 里写了什么？`has_parse_errors` / `has_inference_errors` / `has_timeout_errors` 分别是哪个？
2. **看是不是模型/网络问题**：首次运行卡住多半在下模型；SSL 报错多是证书列表过期；内网环境要确认 `artifacts_path` 指对了。
3. **看依赖冲突**：`libGL.so.1` 缺失是 OpenCV 两个发行版混装；numpy 解析失败是版本约束冲突；macOS Intel 是 torch wheel 缺失。
4. **看输入本身**：扫描件要确认开了 OCR 且语言对得上；加密 PDF 要传 `--pdf-password`；WMF 图片在非 Windows 上必然缺失。
5. **看是不是选错管线**：普通 PDF 用 `standard`；版面复杂到 `standard` 也搞不定时，再用 `vlm` 管线对比结果。
6. **还是看不出**：`--show-layout` 出可视化图、`--profiling` 看耗时分布、`-vv` 看调试日志，三件套一起上。
