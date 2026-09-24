---
name: sanjianke-pymupdf
slug: sanjianke-pymupdf
displayName: 三剪客 · 高性能 PDF 处理
description: "基于 MuPDF C 引擎的 Python 库，一个包搞定 PDF 文本与表格提取、页面渲染、批注、脱敏、合并拆分、加密与 OCR，速度远超纯 Python 方案。 遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "要处理成千上万份 PDF 时，纯 Python 解析器的速度会成为瓶颈。PyMuPDF 直接绑到 MuPDF 这个 C 引擎上，文本提取快一个数量级、页面渲染快两个数量级，而且读写都能做——提取、渲染、批注、脱敏、合并、加密、OCR 全在一个包里。它对中文有完整支持，跑完全离线。 遇到问题请先读「能力边界」里的许可说明。"
license: MIT
tags:
  - 三剪客
  - PDF
  - 文档处理
  - Python
  - AGPL
---

# 三剪客 · 高性能 PDF 处理

如果你的活是「把一堆 PDF 转成能进 RAG 的文本」或者「把页面批量渲染成图」，那选型的第一个问题不是功能够不够，而是**跑不跑得动**。纯 Python 的解析器在几百份文件上还行，上万份就得排队等——而 PyMuPDF 绑的是 MuPDF，一个 C 写的渲染引擎，官方给的口径是文本提取比纯 Python 库快 **10–50 倍**、页面渲染快 **100 倍以上**。

它同时是这批 PDF 工具里**能力最全**的一个：读得出文本、表格、图片、链接、书签、表单；写得了批注、图章、水印、页码；改得动页面顺序、元数据、加密方式；还能做**永久脱敏**和**OCR**。所以常见的选择是「用 PyMuPDF 做主处理，只在需要极致表格精细度时切到 pdfplumber 做局部补充」。

**但有一件事必须在动手前搞清楚：它是 AGPL-3.0 / 商业双授权。** 详细说明见下方「能力边界」，闭源商用前请务必读完那一节。

**上游项目**：`PyMuPDF`　**仓库**：https://github.com/pymupdf/PyMuPDF

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 完全本地运行。官方明确说明**没有任何遥测、许可校验回调或云端依赖**，装完就能在完全离线的机器上用 |
| 读取文件 | 是（必需） | 打开待处理的 PDF / XPS / EPUB / CBZ / MOBI / FB2 / SVG / TXT / Markdown / 图片文件 |
| 写入文件 | 是（批注、脱敏、合并场景必需） | 保存处理后的 PDF、导出 PNG/JPEG、导出 SVG、写 Markdown/JSON/文本 |
| 凭证 | 视需要 | 用于打开有密码的 PDF（`pymupdf.open(..., password=...)`），以及 PyMuPDF Pro 的许可证 Key（`pymupdf.pro.unlock(...)`，**普通开源版本不需要**） |
| 子进程 / 后台常驻 | 视需要 | OCR 时 MuPDF 可能调用 `tesseract` 可执行文件来枚举语言（显式给出 tessdata 路径可避免）；大批量任务建议用多进程而非多线程 |

**密钥与费用**：本 Skill 内嵌的 Key 是占位符，请替换为你自己的；不代理请求、不代收费用。开源版 PyMuPDF **免费**，无需任何 Key。只有 PyMuPDF Pro（Office / HWP 文档支持）需要向 Artifex 购买许可证。**许可证合规责任在调用方**——具体见「能力边界」。

## 什么时候用 / 不用

**该用**：

- 「几千份 PDF 要转成 Markdown 进 RAG」——`pymupdf4llm.to_markdown()`，或 `page.get_text()`。
- 「把 PDF 每页渲染成图给视觉模型看」——`page.get_pixmap(dpi=150).save(...)`。
- 「把几个 PDF 合并 / 拆开 / 重排页面」——`insert_pdf()` + `save()`。
- 「合同里的敏感信息要**永久**抹掉，不是盖个黑框」——`add_redact_annot()` + `apply_redactions()`。
- 「扫描件要 OCR 出文字」——`page.get_textpage_ocr()`（需另装 Tesseract 语言数据）。
- 「给文档批量加水印 / 页码 / 高亮」——`insert_text()` / `add_highlight_annot()`。
- 「读 PDF 表单填了什么 / 要自动填表」——`page.widgets()`。
- 「提取 PDF 里的图片、书签目录、超链接、元数据」——`get_images()` / `get_toc()` / `get_links()` / `metadata`。


**不该用**：

- 闭源商业产品里直接链接/分发，或把 PyMuPDF 打进镜像对外提供网络服务，又不打算买 Artifex 商业许可证 —— AGPL-3.0 含网络服务条款（第 13 条），SaaS 与内部平台对外供服务都可能触发源码提供义务；拿不准就换 pdfplumber / pypdf。
- 想靠多线程提速度 —— 官方立场明确：PyMuPDF 不支持多线程，批量处理必须用多进程。
- 要抓网页、爬取或做正文提取 —— 不做这些。
- 指望它自带 OCR 能力 —— 它只是调用 Tesseract，语言数据要你自己装；受限环境里自动发现语言还可能失败或被禁止。
- 要提取 matplotlib / Excel / R 生成的矢量图表 —— `get_images()` 只列嵌入的位图，矢量图只能整页栅格化。
- 要把 PDF 转回 docx / xlsx —— 能读 Office（还要 Pro），但不能反向转 Office。
- 面对没有 CMap 的 PDF 却期望拿到可读文本 —— 这是 PDF 自身的缺陷，PyMuPDF 只能靠 OCR 兜底。
- 不买 Pro 却要 Office / HWP 支持 —— 未解锁时只能访问任意文档的前 3 页，且有评估期时限。
- 对无框线表格要求最佳效果 —— 这种场景 `find_tables()` 不如 pdfplumber 的可调策略。
- 在同一个环境里装名为 `fitz` 的 PyPI 包并以为那是旧版 PyMuPDF —— 那是另一个包，会得到完全不同的东西；新代码请 `import pymupdf`。

## 安装

**基础安装**（一条命令，无强制外部依赖）：

```bash
pip install pymupdf
```

官方为 **Windows / macOS / Linux** 的 Python **3.10 – 3.14** 提供预编译 wheel。如果你的平台没有对应 wheel，pip 会尝试从源码编译，那时需要 C/C++ 工具链。

**可选扩展**：

```bash
pip install pymupdf-fonts      # 扩展字体集，用于文本输出
pip install pymupdf4llm        # 面向 LLM / RAG 的 Markdown 与 JSON 提取
pip install pymupdfpro         # 增加 Office 文档支持（需商业许可证）
```

```bash
# OCR 需要单独装 Tesseract
# macOS
brew install tesseract
# Ubuntu / Debian
sudo apt install tesseract-ocr
```

**导入方式**：用 `import pymupdf`。

```python
import pymupdf          # 推荐写法
# import fitz           # 旧别名，v1.24.0+ 仍可用，但新代码别这么写
```

两者可互换，但 `pymupdf` 是官方推荐且面向未来的名字。

**该选哪个包名**：PyPI 上的项目名是 `PyMuPDF`，导入名是 `pymupdf`。**从 PyMuPDF 1.24.3 起，旧的 `fitz` 包名已废弃**——如果你的依赖里出现 `pip install fitz`，那是个**不同且已过时的包**，要换掉。装的时候用 `pip install pymupdf`。

## 常用操作

**1. 提取纯文本**

```python
import pymupdf

doc = pymupdf.open("document.pdf")
for page in doc:
    print(page.get_text())
```

**2. 提取带版面元数据的文本**（字体、字号、位置）

`get_text("dict")` 返回结构化数据，方便做标题识别、字号分组：

```python
import pymupdf

doc = pymupdf.open("document.pdf")
page = doc[0]

blocks = page.get_text("dict")["blocks"]
for block in blocks:
    if block["type"] == 0:              # 0 = 文本块
        for line in block["lines"]:
            for span in line["spans"]:
                print(f"{span['text']!r}  font={span['font']}  size={span['size']:.1f}")
```

`get_text()` 的输出格式：`"text"`（默认）、`"dict"`（富结构）、`"words"`、`"blocks"`、`"html"`、`"xml"`、`"rawdict"`、`"rawjson"` 等。

**复用 TextPage 提速**：同一页上反复提取时，创建 `TextPage` 才是贵的部分，切格式很便宜。官方给的数字是**能省 50–95% 时间**：

```python
import pymupdf

doc = pymupdf.open("document.pdf")
page = doc[0]

tp = page.get_textpage()                       # 只建一次
text  = page.get_text("text",  textpage=tp)
words = page.get_text("words", textpage=tp)
data  = page.get_text("dict",  textpage=tp)
```

**3. 提取表格**

```python
import pymupdf

doc = pymupdf.open("spreadsheet.pdf")
page = doc[0]

tables = page.find_tables()
for table in tables:
    print(table.to_markdown())      # 直接出 GitHub 风格 Markdown 表格
    df = table.to_pandas()          # 或转成 DataFrame（需要 pandas）
```

**4. 页面渲染成图片**

```python
import pymupdf

doc = pymupdf.open("document.pdf")
page = doc[0]

pixmap = page.get_pixmap(dpi=150)       # 也可以传 matrix= 自己算缩放
pixmap.save("page_0.png")
```

**5. 定向提取：只要页面上某一块**

传一个 `clip` 矩形，坐标单位是点：

```python
import pymupdf

doc = pymupdf.open("input.pdf")
page = doc[0]

clip = pymupdf.Rect(50, 100, 400, 300)      # (x0, y0, x1, y1)
text = page.get_text("text", clip=clip)
print(text)
```

坐标系原点是**页面左上角**，y 向下增大——和 pdfplumber 一致。

**6. 搜索并定位 / 高亮**

```python
import pymupdf

doc = pymupdf.open("document.pdf")

for page in doc:
    hits = page.search_for("confidential")
    if hits:
        print(f"第 {page.number} 页：{len(hits)} 处")
        for rect in hits:
            page.add_highlight_annot(rect)

doc.save("highlighted.pdf")
```

非水平文字（斜排、竖排）要高亮得准，加 `quads=True`：

```python
quads = page.search_for("important term", quads=True)
page.add_highlight_annot(quads)
```

**7. 永久脱敏**（两步，故意的设计）

```python
import pymupdf

doc = pymupdf.open("contract.pdf")
page = doc[0]

# 第一步：标记要抹掉的区域
rect = page.search_for("confidential")[0]
page.add_redact_annot(rect, fill=(1, 1, 1))     # 白色填充

# 第二步：应用——底层内容被永久移除
page.apply_redactions()

doc.save("contract_redacted.pdf")
```

`apply_redactions()` 之后**原始内容从保存的文件里永久消失，无法恢复**。两步分离就是为了让你先审阅再执行。

**8. 合并 / 拆分**

```python
import pymupdf

# 合并
merger = pymupdf.open()
for path in ["part1.pdf", "part2.pdf", "part3.pdf"]:
    merger.insert_pdf(pymupdf.open(path))
merger.save("merged.pdf")

# 拆成单页文件
doc = pymupdf.open("document.pdf")
for i, page in enumerate(doc):
    out = pymupdf.open()
    out.insert_pdf(doc, from_page=i, to_page=i)
    out.save(f"page_{i + 1}.pdf")
```

**9. 读 / 写元数据与书签**

```python
import pymupdf

doc = pymupdf.open("input.pdf")

print(doc.metadata)      # {'title': ..., 'author': ..., 'subject': ..., 'keywords': ...}

doc.set_metadata({
    "title": "Annual Report 2025",
    "author": "Finance Team",
    "keywords": "annual, finance, 2025"
})
doc.save("output.pdf")

# 书签：列表项是 [层级, 标题, 页码]
toc = doc.get_toc()
for level, title, page in toc:
    print(" " * level, title, "→ 第", page, "页")

doc.set_toc([
    [1, "Introduction", 1],
    [1, "Methods",      5],
    [2, "Data sources", 6],
])
doc.save("output.pdf")
```

**10. 加水印**

```python
import pymupdf

doc = pymupdf.open("document.pdf")
for page in doc:
    page.insert_text(
        point=pymupdf.Point(72, page.rect.height / 2),
        text="DRAFT",
        fontsize=72,
        color=(0.8, 0.8, 0.8),
        rotate=45,
    )
doc.save("watermarked.pdf")
```

**11. OCR 扫描件**

```python
import pymupdf

doc = pymupdf.open("scanned.pdf")
page = doc[0]

# 需要装好 Tesseract 且在 PATH 上
text = page.get_textpage_ocr(language="eng").extractText()
print(text)
```

**12. 面向 LLM 的 Markdown 提取**（需 `pymupdf4llm`）

```python
import pymupdf4llm

md = pymupdf4llm.to_markdown("report.pdf")
print(md)
```

它会把文本和表格一起输出成**整合的 Markdown**：表格被检测出来转成 GitHub 兼容语法，并按正确阅读顺序穿插在正文里。还支持多栏版面、自然阅读顺序与分页 chunk。同族的还有 `to_json()` 与 `to_text()`。

**13. 读 / 填表单**

```python
import pymupdf

doc = pymupdf.open("form.pdf")
page = doc[0]

for field in page.widgets():
    print(f"{field.field_name}: {field.field_value}")

# 填表
for field in page.widgets():
    if field.field_name == "First Name":
        field.field_value = "Ada"
        field.update()

doc.save("filled_form.pdf")
```

**14. 提取图片**

```python
import pymupdf
from pathlib import Path

doc = pymupdf.open("document.pdf")
out = Path("images")
out.mkdir(exist_ok=True)

for page_index, page in enumerate(doc):
    for img_index, img in enumerate(page.get_images()):
        xref = img[0]
        pix = pymupdf.Pixmap(doc, xref)
        if pix.n > 4:                       # CMYK 要转一下
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        pix.save(out / f"page{page_index}_img{img_index}.png")
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| **多线程跑起来直接崩 / 结果错乱** | PyMuPDF **明确不支持多线程**，连 Python 新的 free-threading 模式也不行——底层 MuPDF 只有部分线程安全，做成全线程安全反而会引入单线程开销、把收益抵消掉 | **改用多进程**：每个进程独立打开文件、处理自己的页范围（见下方示例）。不要用 `ThreadPoolExecutor` |
| 提取出来是空的 | 扫描件 PDF 里没有文字层，只有图片 | 走 OCR：`page.get_textpage_ocr()`。**扫描件做文本提取永远返回空，这是预期行为** |
| 文字是乱码 / 提取不到 | PDF 用了**自定义字体编码但没有正确的 CMap**——字形在，但映射不回 Unicode | 用 OCR 兜底（`page.get_textpage_ocr()`）。这是字体层面的问题，没有纯解析的解 |
| `get_images()` 返回空，但页面上明明有图表 | 图表是**矢量图形**（PDF 绘图指令），不是嵌入的位图。`get_images()` 只列嵌入的位图对象 | 想拿到图表就整页栅格化：`page.get_pixmap()` |
| 反复提取同一页很慢 | 每次都重新建 `TextPage` | 建一次 `tp = page.get_textpage()`，之后用 `textpage=tp` 复用。官方称可省 50–95% 时间 |
| 装不上 / 导入报错说找不到 `fitz` | 或者反过来，装了 `pip install fitz` 那个**同名的老包** | 认准 `pip install pymupdf`，导入用 `import pymupdf`。`fitz` 只是仍可用的旧别名 |
| 处理完 Office 文档报错或只出前 3 页 | **Office 支持属于 PyMuPDF Pro**，开源版不含。未解锁 / 无 Key 时**只能访问前 3 页**，且有评估期限制 | 要么买 Pro 许可证并 `pymupdf.pro.unlock("你的Key")`，要么先用 LibreOffice 转成 PDF 再用开源版处理 |
| OCR 报找不到语言 | PyMuPDF 用的是 MuPDF 内置的 Tesseract 支持（**不需要 Python 层的 `pytesseract`**），但仍需 **Tesseract 的语言数据文件 `tessdata`**；不给路径时自动发现**可能调用 `tesseract` 可执行文件**来列语言 | 装上 Tesseract 让自动发现生效，或用 `tessdata=` 参数 / `TESSDATA_PREFIX` 环境变量显式指定路径。支持 100 多种语言 |
| 对图片做 OCR 失败 | 图片带 alpha 通道，OCR 不支持 | 先去 alpha：`if pix.alpha: pix = pymupdf.Pixmap(pix, 0)`，再插进一个单页 PDF 里 OCR |
| 脱敏之后用复制粘贴还能把内容抠出来 | 只调 `add_redact_annot()` 没调 `apply_redactions()`——此时只是画了个框，内容还在 | **必须调 `apply_redactions()`**。调用后内容从保存的文件里永久消失，不可恢复 |
| 加中文水印出方块 / 报错 | 用内置基础字体写非拉丁字符 | 用支持中文的字体：装 `pymupdf-fonts` 扩展字体集，或显式指定字体文件路径建 `Font` 对象 |
| 大批量处理内存一直涨 | `Document` 对象没关闭 | 用 `with pymupdf.open(...) as doc:`，或显式 `doc.close()`。多进程场景下每个进程只开自己那一段 |
| 保存时报文件被占用 | 目标路径和源文件是同一个，或文件被别的进程锁着 | 存到新文件名；`save()` 默认会做增量保存的尝试，同名覆盖容易出问题 |

### 多进程的正确写法

```python
from multiprocessing import Pool
import pymupdf

def process_pages(args):
    path, start, end = args
    doc = pymupdf.open(path)                  # 每个进程开自己的句柄
    results = []
    for i in range(start, end):
        results.append(doc[i].get_text())
    return results

if __name__ == "__main__":                    # Windows 上必须加这个保护
    with Pool(4) as pool:
        chunks = [("input.pdf", 0, 25), ("input.pdf", 25, 50)]
        all_results = pool.map(process_pages, chunks)
```

Windows 上 `multiprocessing` 用 spawn 启动，**没有 `if __name__ == "__main__":` 保护会无限递归创建进程**。

## 能力边界

### 许可证（务必先读这一节）

**PyMuPDF 与 MuPDF 由 Artifex Software, Inc. 维护，采用双授权：**

| 授权方式 | 适用场景 | 代价 |
|---|---|---|
| **GNU AGPL v3** | 开源项目 | 免费。但 AGPL 是**强传染性**许可证，且**含网络服务条款**——如果你修改了它并通过网络对外提供服务，必须按 AGPL 向使用者提供完整对应源码 |
| **Artifex 商业许可证** | 闭源 / 专有应用 | 需向 Artifex 付费购买 |

**这意味着什么，说清楚：**

- **开源项目**、内部研究脚本、自己用不外发——AGPL 基本没有额外负担。
- **闭源商业产品**里直接链接 / 分发 PyMuPDF——典型理解下需要商业许可证。**不要默认 AGPL 可以随便商用**。
- **SaaS / 网络服务**尤其要注意：AGPL 第 13 条专门针对网络交互，即使用户拿不到二进制，只要通过网络使用了你的服务，就可能触发源码提供义务。
- **最容易被忽略的一种**：把 PyMuPDF 打进 Docker 镜像对外提供服务、或做成内部平台给其他团队用——这已经算「通过网络提供服务」，需要评估。
- 判断责任在**你**，不在本 Skill。拿不准就找法务，或直接买商业许可证、换用 MIT/BSD 许可的替代方案（如 `pdfplumber`、`pypdf`，但功能和性能要打折）。

**PyMuPDF Pro / PyMuPDF4LLM 的授权另算**。Pro 需要单独的商业 Key；未解锁时有明确限制：**只能访问任意文档的前 3 页**，且有评估期时限。

### 覆盖

- **文本提取**：纯文本、富字典（含字体、字号、颜色、边界框）、HTML、XML、原始块、词级、块级。
- **表格**：`find_tables()` 定位、提取，并可导出为 Markdown（`to_markdown()`）或 pandas DataFrame（`to_pandas()`）。
- **图片**：提取嵌入图片、把任意页面渲染成高分辨率 `Pixmap`。
- **渲染**：页面栅格化到图片或 `Pixmap`，供 UI 或其他流程使用。输出还支持 SVG 矢量。
- **OCR**：Tesseract 集成，支持整页或局部 OCR、语言可配、100+ 语言。
- **批注**：读写高亮、下划线、波浪线、便签、自由文本、手写、图章。
- **脱敏**：添加并**永久应用**脱敏批注。
- **表单**：读写 PDF AcroForm 字段。
- **创建 PDF**：直接用 API 创建，或从 Markdown 文件快速转换。
- **编辑 PDF**：插入 / 删除 / 重排页面；设置元数据；合并与拆分。
- **绘图**：画线、曲线、矩形、圆；插入 HTML 框。
- **加密**：打开带密码的 PDF；用 RC4 或 AES 加密保存。
- **链接与书签**：提取超链接、内部交叉引用、URI 目标；读写大纲（目录）树。
- **元数据**：标题、作者、创建日期、生成器、主题，以及自定义条目。
- **色彩空间**：RGB、CMYK、灰度，以及相互转换。
- **输入格式**：PDF、XPS、EPUB、CBZ、MOBI、FB2、SVG、TXT、MD，以及 PNG / JPEG / BMP / TIFF / GIF 等图片。
- **LLM 输出**（需 `pymupdf4llm`）：`to_markdown()` / `to_json()` / `to_text()`，支持多栏版面、自然阅读顺序、分页 chunk。

### 不覆盖

- **不抓网页**。不做下载、爬取、正文提取。
- **不做 OCR 引擎本身**。它调用 Tesseract，语言数据要你自己装。
- **不提供云端能力**。没有 SaaS、没有托管 API——这是优点也是边界。
- **不能识别所有图表**。`get_images()` 拿不到矢量图形；`find_tables()` 对无框线表格的效果不如 pdfplumber 的可调策略。
- **不做 PDF 转 Office**。能读 Office（需 Pro），但不能把 PDF 转回 docx / xlsx。
- **不支持多线程**（见「已知限制」）。
- **不含 PyMuPDF Pro 的能力**（Office / HWP 支持）——那要单独付费。
- 本 Skill 内不含任何可复制的第三方源码，正文为原创整理，仅引用 API 名称、许可证等事实性信息。

## 依赖条件

- **Python 3.10 – 3.14**（截至 v1.27.x）。wheel 覆盖：manylinux x86_64 与 aarch64、musllinux x86_64、macOS x86_64 与 arm64、Windows x86 与 x86_64。
- **无强制外部依赖**。`pip install pymupdf` 装完即可用，不需要额外的系统库。
- **OCR 需要**：Tesseract 及其语言数据（`tessdata`）。PyMuPDF **不需要** Python 层的 `pytesseract`。
- **源码编译场景**：平台没有预编译 wheel 时，需要 C/C++ 工具链。
- **可选包**：`pymupdf-fonts`（扩展字体）、`pymupdf4llm`（LLM 输出）、`pymupdfpro`（Office 支持，需商业 Key）。
- **网络**：只在 `pip install` 时需要。之后可在完全隔离的环境里运行，无遥测、无许可校验回调、无云依赖。

## 已知限制

- **许可证是 AGPL-3.0 或商业授权，二选一**。闭源商用与网络服务场景需要认真评估，详见「能力边界」。这是选型时**第一个**要确认的事，不是最后一个。
- **不支持多线程**。官方立场很明确：即使 Python 有了 free-threading，PyMuPDF 也不支持——MuPDF 只提供部分线程安全，做成全线程安全会带来单线程开销，收益被抵消。**批量处理必须用多进程**。
- **OCR 依赖外部语言数据**。不给 tessdata 路径时，自动发现机制**可能调用 `tesseract` 可执行文件**来枚举可用语言——这在受限环境里可能失败或被禁止。
- **矢量图表拿不到**。`get_images()` 只列嵌入的位图；matplotlib / Excel / R 生成的图表是绘图指令，只能整页栅格化。
- **没有 CMap 的 PDF 提取不出可读文本**。这是 PDF 本身的问题，PyMuPDF 只能靠 OCR 兜底。
- **PyMuPDF Pro 有明确的评估限制**：不带 Key 调用 `pymupdf.pro.unlock()` 时**只能访问前 3 页**，且功能会在评估期后过期。
- **`fitz` 别名终将被移除**。v1.24.0+ 仍可用，但新代码应该用 `import pymupdf`。
- **PyPI 上的 `fitz` 是另一个包**，不是 PyMuPDF 的旧版本。误装会得到完全不同的东西。
- 版本号、性能倍数、平台覆盖范围以你实际安装的版本与官方文档为准。

## 自检清单

- [ ] **许可证已确认**：明确知道自己的使用场景属于 AGPL 合规范围，还是需要 Artifex 商业许可证。网络服务 / 闭源分发 / 打进对外镜像的情况已单独评估过。
- [ ] 装的是 `pip install pymupdf`，导入的是 `import pymupdf`，没有误装 PyPI 上那个同名的 `fitz` 包。
- [ ] 批量处理用的是**多进程**（`multiprocessing.Pool`），**没有用线程池**。
- [ ] Windows 上的多进程代码包在 `if __name__ == "__main__":` 保护里。
- [ ] `Document` 对象用 `with` 或显式 `close()`，长跑任务里内存没有单调增长。
- [ ] 提取结果为空时，第一步先确认**是不是扫描件**，而不是去调参数。
- [ ] 需要 OCR 时，Tesseract 与对应语言数据已装好，并验证了 `get_textpage_ocr(language=...)` 能跑通。
- [ ] 要提取图表时确认了它是位图还是矢量——矢量的走 `get_pixmap()`。
- [ ] 脱敏场景**调用了 `apply_redactions()`**，并且用复制粘贴 / 文本提取验证过内容确实取不出来了。
- [ ] 同一页要反复提取多个格式时，复用了 `TextPage` 对象。
- [ ] 加中文文本 / 水印时用了支持中文的字体，验证过输出没有方块。
- [ ] 用 `pymupdf4llm` 时确认它已单独安装，并且知道它和核心包是分开授权的。
- [ ] 涉及 Office 文档时确认了是否需要 Pro，未解锁版本只能读前 3 页。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/recipes.md` | 常见任务配方：提取、渲染、批注、脱敏、表单、合并拆分、加密、OCR、多进程批处理的完整代码 |
| `references/licensing.md` | AGPL 与商业授权的边界、判定场景清单、替代方案对比、Pro 与 PyMuPDF4LLM 的授权说明 |
| `README.md` | 包说明 |
| https://github.com/pymupdf/PyMuPDF | 上游仓库（安装与完整文档以它为准） |

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
