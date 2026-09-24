---
name: sanjianke-unstructured
slug: sanjianke-unstructured
displayName: 三剪客 · 多格式文档解析
description: "unstructured：多格式文档解析 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "unstructured：多格式文档解析 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · 多格式文档解析

PDF、Word、PPT、Excel、HTML、邮件、EPUB、图片……几十种格式各写一套解析代码是件苦差事。这个库把它们统一成一条路：进去一个文件，出来一串**带类型标签的元素**——这是标题、这是正文段、这是列表项、这是表格，每块都带页码、文件名等元数据。之后不管是丢进向量库做 RAG，还是按类型过滤出正文做摘要，都有统一的抓手。它的真实成本在于：要解析 PDF 和 Office 文档，光装 Python 包不够，系统级依赖（poppler、tesseract、libreoffice）得先在机器上备齐。

**上游项目**：`unstructured`　**仓库**：https://github.com/Unstructured-IO/unstructured

## 什么时候用 / 不用

**用它**：

- 要做 **RAG 的文档入库**：把各种格式的文档切成带语义边界的块，再喂向量库
- 输入是**混合格式**（一批 PDF + docx + html + 邮件），希望用同一套代码处理
- 需要**按元素类型筛选**内容（只要 `NarrativeText`、只要 `Table`），而不是一坨纯文本
- 扫描件 / 图片型 PDF 需要走 OCR，或者需要 hi_res 策略做版面与表格结构还原
- 需要元素级元数据：页码、文件名、坐标、表格的 HTML 表示

**不要用它**：

- 只要纯文本，不需要元素类型和元数据 → `pdftotext`、`python-docx` 更快更省事
- 表格精修：要像素级还原复杂表格、要处理跨页跨行 → 专门的表格识别工具更合适（hi_res 能给出结构，但不保证和原表一致）
- 环境**装不了系统依赖**（无 root、精简容器）→ PDF/Office 解析会直接失败，要么换基础镜像，要么用官方容器
- 要的是**批量连接器**（S3、SharePoint、Confluence 拉数据）→ 那部分在独立的 ingest 项目里，不在本库
- 追求**解析质量天花板** → 商用高精度 API 与开源版本能力不同，开源版够用但不是最强
- 数据**不允许任何形式的外呼统计**又没设退出变量 → 库默认会发匿名使用统计（可关，见下）

## 安装

```bash
# 1) 全格式：一次性装上所有文档类型的 Python 依赖（体积最大）
pip install "unstructured[all-docs]"

# 2) 只要纯文本 / HTML / XML / JSON / 邮件，这些不需要额外依赖
pip install unstructured

# 3) 按需装：只处理哪几类就装哪几个 extras
pip install "unstructured[docx,pptx]"
pip install "unstructured[pdf]"          # PDF：含图像处理与 hi_res 相关依赖

# 4) 系统依赖（按要解析的类型选装，Linux 为例）
#    这些不在 pip 里，缺一个对应格式就会报错
sudo apt-get install -y libmagic-dev      # 文件类型探测
sudo apt-get install -y poppler-utils     # PDF 与图片
sudo apt-get install -y tesseract-ocr     # OCR（中文等语言另装 tesseract-lang）
sudo apt-get install -y libreoffice       # MS Office 文档
#    pandoc 不需要系统安装，已通过 pypandoc-binary 打包进 Python 依赖

# 5) 不想折腾系统依赖：用官方容器
docker pull downloads.unstructured.io/unstructured-io/unstructured:latest
docker run -dt --name unstructured downloads.unstructured.io/unstructured-io/unstructured:latest
docker exec -it unstructured bash          # 进去直接 python3

# 6) 本地开发（源码仓库，用 uv 管理依赖）
make install            # 等价于 uv sync --locked --all-extras --all-groups
uv sync --extra pdf     # 只要某几个 extras
```

装完验证一行：

```python
from unstructured.partition.auto import partition
elements = partition(filename="example.pdf")
print("\n\n".join(str(el) for el in elements))
```

具体 extras 名称、系统包名随版本变动，**以官方安装文档为准**。

## 常用操作

**1）万能入口：自动识别格式并分区**

```python
from unstructured.partition.auto import partition

# 用 libmagic 探测类型；探测不到时退回扩展名
elements = partition(filename="example-docs/fake-email.eml")
for el in elements:
    print(el.category, "|", el.metadata.filename, "|", str(el)[:60])

# 已知类型时可直接指定，跳过探测
elements = partition(filename="paper.pdf", content_type="application/pdf")
```

**2）PDF：先选策略，再决定要不要 OCR / 表格结构**

```python
from unstructured.partition.pdf import partition_pdf

elements = partition_pdf(
    filename="paper.pdf",
    strategy="hi_res",              # auto | fast | hi_res | ocr_only
    infer_table_structure=True,     # 让表格元素带上 text_as_html
    languages=["eng"],              # OCR 语言（中文用 chi_sim 之类）
    include_page_breaks=True,       # 输出里插入 PageBreak 元素
)
```

策略怎么选：`fast` 只抽文字层，最快；`hi_res` 走模型做版面/表格，最准也最慢；
`ocr_only` 纯 OCR；`auto` 由库自己判断。

**3）指定类型的解析函数（比 auto 更可控）**

```python
from unstructured.partition.docx import partition_docx
from unstructured.partition.pptx import partition_pptx
from unstructured.partition.xlsx import partition_xlsx
from unstructured.partition.html import partition_html
from unstructured.partition.md import partition_md
from unstructured.partition.email import partition_email
from unstructured.partition.image import partition_image

# 都能吃 filename=... 或 file=<文件对象>；HTML 还支持 url=...
elements = partition_html(url="https://example.com", include_page_breaks=True)
```

**4）分块：直接给 RAG 用**

```python
from unstructured.chunking.title import chunk_by_title
from unstructured.partition.pdf import partition_pdf

elements = partition_pdf(filename="report.pdf", strategy="fast")
chunks = chunk_by_title(
    elements,
    max_characters=1500,        # 硬上限，默认 500
    new_after_n_chars=1000,     # 软上限，超了就不再拼接下一个元素
    overlap=100,                # 只在超大元素被文本切分时生效
    overlap_all=False,          # 普通块之间也做重叠（默认否）
)
# 块只有三种类型：CompositeElement、Table、TableChunk
for c in chunks:
    print(c.category, len(str(c)))
```

也可以在分区时一步完成：`partition_pdf(..., chunking_strategy="by_title")`
（另一种取值是 `"basic"`）。

**5）序列化：存成 JSON / 从 JSON 读回**

```python
from unstructured.staging.base import elements_to_json, elements_from_json

elements_to_json(elements, filename="elements.json")
restored = elements_from_json(filename="elements.json")

# 单元素也行：el.to_dict()
print(elements[0].to_dict().keys())
```

**6）按类型过滤，只留正文**

```python
from unstructured.documents.elements import NarrativeText, Table, Title

narrative = [el for el in elements if isinstance(el, NarrativeText)]
tables = [el for el in elements if isinstance(el, Table)]
for t in tables:
    print(t.metadata.text_as_html[:200])   # 表格的 HTML 表示
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 装完 `pip install unstructured` 后解析 PDF 报缺依赖 | 基础包只覆盖纯文本 / HTML / XML / JSON / 邮件，其它格式要装 extras | PDF 用 `pip install "unstructured[pdf]"`，全都要用 `[all-docs]` |
| 报 `libmagic`、`poppler`、`tesseract` 找不到 | 这些是**系统级**依赖，pip 装不了 | 按格式补装系统包（libmagic-dev / poppler-utils / tesseract-ocr / libreoffice），或直接用官方容器 |
| `hi_res` 策略特别慢，甚至卡住 | hi_res 会跑版面模型（可能含 OCR），CPU 上代价很大 | 能用 `fast` 就用 fast；必须 hi_res 时上 GPU、只处理必要页面，或改用容器/服务化部署 |
| 中文扫描件识别成一堆乱码 | OCR 默认语言不含中文，tesseract 也没装中文语言包 | 装 `tesseract-lang`，并在调用时传 `languages=["chi_sim"]` 之类的语言代码 |
| 表格拿不到结构，`metadata.text_as_html` 是空的 | 没开表格结构推断 | 分区时传 `infer_table_structure=True`（并注意它通常需要 hi_res 策略） |
| 输出顺序/分块效果和预期不同 | `chunk_by_title` 依赖标题元素划分章节，没有标题的文档退化成按长度拼 | 先看分区结果里有没有 `Title` 类元素；纯散文文档改用 `basic` 策略 |
| 内网 / 离线环境发现程序在往外发请求 | 库**默认开启匿名使用统计** | 导入前设置环境变量 `DO_NOT_TRACK` 或 `SCARF_NO_ANALYTICS`（任意非空值，如 `true`）即可全部关闭 |
| 大文件解析被截断 | 文本类分区函数有 `max_partition` 之类的上限参数 | 按需调大 `max_partition`，或自行分页处理 |
| 代码里写死了 `pip install "unstructured[local-inference]"` 之类的旧 extras | 版本演进中 extras 名字变过 | 以当前官方安装文档的 extras 名单为准，不要照抄老教程 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（默认开启统计） | 库默认向官方统计端点发送匿名使用数据；用 `DO_NOT_TRACK` / `SCARF_NO_ANALYTICS` 可关闭。解析本身不需要联网，除非使用 `url=` 形式或自带模型下载 |
| 读取文件 | 是 | 读取待解析的文档、图片，以及本地模型文件 |
| 写入文件 | 是 | 仅在调用方要求时写结果（如 `elements_to_json(...)`）；hi_res 可能写缓存 |
| 凭证 | 否 | 开源库本地解析不需要 Key；只有改用托管 API 时才需要账号与 API Key |
| 子进程 / 后台常驻 | 是 | 会调用系统工具（poppler、tesseract、libreoffice）作为子进程；不常驻服务 |

## 触发场景

- 「把这批 PDF 和 Word 解析成带结构的 JSON，我要入向量库」
- 「文档切成适合 RAG 的块，块之间别把一段话劈开」
- 「提取文档里所有表格，输出 HTML」
- 「扫描版 PDF 要 OCR，中英文混排」
- 「一批混杂格式的文件，按统一流程处理一遍」
- 「文档里的标题、正文、页眉页脚分开，只要正文」

## 能力边界

**覆盖**：

- 分区：CSV / TSV / 邮件(.eml/.msg) / EPUB / Excel / HTML / 图片 / Markdown / Org / ODT / PDF / PPT / PPTX / RST / RTF / 文本与常见代码文件 / Word(.doc/.docx) / XML
- 元素类型识别：`Title`、`NarrativeText`、`ListItem`、`Table`、`PageBreak` 等，可按类型筛选
- PDF 与图片的策略选择：`auto` / `fast` / `hi_res` / `ocr_only`，可选 OCR 语言、表格结构推断
- 分块：`basic` 与 `by_title` 两种策略，支持硬/软上限与重叠参数
- 序列化：元素转 JSON / 从 JSON 读回，元素可 `to_dict()`
- 元数据：文件名、页码、坐标（hi_res 下）、表格 HTML 等
- 容器化运行与本地开发工作流（uv / make）

**不覆盖**：

- 数据源连接器（S3、SharePoint、Confluence 等批量摄取）——在独立的 ingest 项目里
- 商用高精度解析模型与托管服务的全部能力（开源版是另一条产品线）
- 表格的像素级还原：复杂跨页表格出来的结构可能与原表有出入
- 文档理解本身：不做摘要、问答、分类，只做解析与结构化
- 手写体、极端低质量扫描件的稳定识别
- 直接生成嵌入向量（嵌入要自己接模型）

## 依赖条件

- Python 环境；视格式安装对应 extras（`unstructured[all-docs]` 一网打尽）
- 系统依赖：`libmagic-dev`（类型探测）、`poppler-utils`（PDF/图片）、`tesseract-ocr`（OCR，多语言需 `tesseract-lang`）、`libreoffice`（Office 文档）
- `pandoc` 由 Python 包 `pypandoc-binary` 自带，不用系统安装
- hi_res 路线对算力有要求：CPU 能用但慢，批量场景建议 GPU 或容器/服务化
- 本地开发需要 `uv` 与 `make`
- 数据合规：默认匿名统计需显式关闭（`DO_NOT_TRACK` / `SCARF_NO_ANALYTICS`）

## 已知限制

1. 系统依赖是硬门槛，精简容器里装不全就跑不动对应格式
2. hi_res 精度更高但慢得多，批量处理要算清时间成本
3. 分块质量取决于分区是否识别出标题结构，没有标题的文档效果一般
4. 表格结构化不保证与原表逐格一致，复杂表格要人工抽查
5. 版本迭代较快，extras 名称与函数可选参数会变，老教程容易踩空
6. 默认发送匿名使用统计，合规敏感的环境必须显式关闭

## 自检清单

**执行前**

- [ ] 明确要解析的格式清单 → 决定装哪些 extras 和系统依赖
- [ ] PDF 先确认有没有文字层：有就优先 `fast`，别一上来 `hi_res`
- [ ] 批量场景确认算力：hi_res + OCR 在大批量下的耗时能不能接受
- [ ] 中文/多语言 OCR：tesseract 语言包与 `languages` 参数都对齐
- [ ] 合规敏感：导入前设置 `DO_NOT_TRACK` 或 `SCARF_NO_ANALYTICS`
- [ ] 确认没有把旧文档里的 `[local-inference]` 之类已变更的 extras 抄进来

**执行后**

- [ ] 抽查元素类型分布：标题/正文/表格是否被正确识别
- [ ] 检查 `metadata` 里页码、文件名是否符合预期
- [ ] 需要表格时确认 `text_as_html` 非空
- [ ] 分块后统计块长分布，确认没有超长块或大量过短块
- [ ] 序列化结果能 `elements_from_json` 读回并复原

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| `references/partition-functions.md` | 各格式对应的分区函数、策略与常用参数 |
| `references/chunking-and-output.md` | 分块策略、元素字段与序列化 |
| https://github.com/Unstructured-IO/unstructured | 上游仓库（安装与完整文档以它为准） |

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
