# 各格式的分区函数与参数

`unstructured` 里每种格式都有自己的分区函数；不确定格式就用 `partition()`，
它靠 libmagic 探测类型（探测不到时退回扩展名）再路由到对应函数。

## 格式 → 函数对照

| 文档类型 | 分区函数 | 策略 | 表格支持 |
|---|---|---|---|
| CSV | `partition_csv` | 无 | 是 |
| TSV | `partition_tsv` | 无 | 是 |
| 邮件 .eml | `partition_email` | 无 | 否 |
| 邮件 .msg | `partition_msg` | 无 | 否 |
| EPUB | `partition_epub` | 无 | 是 |
| Excel .xlsx/.xls | `partition_xlsx` | 无 | 是 |
| HTML .html/.htm | `partition_html` | 无 | 否 |
| 图片 .png/.jpg/.jpeg/.tiff/.bmp/.heic | `partition_image` | `auto` / `hi_res` / `ocr_only` | 是 |
| Markdown .md | `partition_md` | 无 | 是 |
| Org Mode .org | `partition_org` | 无 | 是 |
| Open Office .odt | `partition_odt` | 无 | 是 |
| PDF .pdf | `partition_pdf` | `auto` / `fast` / `hi_res` / `ocr_only` | 是 |
| 纯文本 .txt/.text/.log | `partition_text` | 无 | 否 |
| PowerPoint .ppt | `partition_ppt` | 无 | 是 |
| PowerPoint .pptx | `partition_pptx` | 无 | 是 |
| reStructuredText .rst | `partition_rst` | 无 | 是 |
| RTF .rtf | `partition_rtf` | 无 | 是 |
| Word .doc | `partition_doc` | 无 | 是 |
| Word .docx | `partition_docx` | 无 | 是 |
| XML .xml | `partition_xml` | 无 | 否 |
| 代码文件（.js/.py/.java/.cpp/.c/.cs/.php/.rb/.swift/.ts/.go 等） | `partition_text` | 无 | 否 |

导入路径统一是 `unstructured.partition.<类型>`，例如
`from unstructured.partition.docx import partition_docx`。

## 入口形式

| 入口 | 说明 |
|---|---|
| `partition(filename="x.pdf")` | 传路径 |
| `partition(file=f)` | 传 file-like 对象（上传流、内存缓冲） |
| `partition_html(url="https://...")` | HTML 支持直接给 URL |
| `content_type="application/pdf"` | 跳过类型探测，配合 `filename` 或 `file` 使用 |

## 常用参数

按格式可用性不同，以下参数在文档里被逐格式列出：

| 参数 | 作用 | 出现在 |
|---|---|---|
| `strategy` | 解析策略：`auto` / `fast` / `hi_res` / `ocr_only`（图片无 `fast`） | PDF、图片 |
| `languages` | OCR 语言代码列表，如 `["eng"]`、`["chi_sim"]` | PDF、图片 |
| `infer_table_structure` | 推断表格结构，表格元素带上 `text_as_html` | PDF、图片 |
| `include_page_breaks` | 输出里插入 `PageBreak` 元素 | EPUB、HTML、图片、Markdown、Org、PDF、PPT/PPTX、RST、RTF、Word |
| `encoding` | 指定文本编码 | 邮件、HTML、PDF、文本、XML |
| `max_partition` | 单个分区内容的上限（超出会被拆分/截断） | 邮件、PDF、文本、XML |
| `include_headers` | 邮件是否把头部信息作为元素输出 | 邮件 |
| `process_attachments` | 是否继续解析邮件里的附件 | 邮件 |
| `xml_keep_tags` | 保留 XML 标签 | XML |
| `paragraph_grouper` | 自定义段落聚合函数 | 文本 |
| `chunking_strategy` | 分区时顺带分块：`basic` / `by_title` | 支持分区的各函数 |

## 策略怎么选（PDF / 图片）

- `fast`：只抽文字层，不跑模型。有文字层的 PDF 用它，秒级完成。
- `hi_res`：走版面模型，能识别标题层级、表格、图片区域，最准也最慢；
  表格结构推断基本都在这条路线上。
- `ocr_only`：不判断版面，直接 OCR 全页。纯扫描件、版面简单时可用。
- `auto`：交给库判断（例如有文字层就走 fast 路线）。

没有文字层的扫描件不要用 `fast`，会得到空结果。

## 典型调用

```python
# PDF + 高精度 + 表格 + 中文 OCR
from unstructured.partition.pdf import partition_pdf
elements = partition_pdf(
    filename="scan.pdf",
    strategy="hi_res",
    infer_table_structure=True,
    languages=["chi_sim", "eng"],
    include_page_breaks=True,
)

# 图片
from unstructured.partition.image import partition_image
elements = partition_image(filename="page.png", strategy="ocr_only", languages=["eng"])

# Word / PPT / Excel
from unstructured.partition.docx import partition_docx
from unstructured.partition.pptx import partition_pptx
from unstructured.partition.xlsx import partition_xlsx
docx_elements = partition_docx(filename="a.docx", include_page_breaks=True)
pptx_elements = partition_pptx(filename="b.pptx")
xlsx_elements = partition_xlsx(filename="c.xlsx")
```

多格式混批时，先按扩展名映射到函数表，或统一走 `partition()`——
记得把那批文件里出现过的所有 extras 都装上。
