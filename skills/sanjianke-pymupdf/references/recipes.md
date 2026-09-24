# 常见任务配方

所有片段都基于 `import pymupdf`。坐标单位是点（point，1/72 英寸），原点在**页面左上角**，y 向下增大。

---

## 一、打开与基本信息

```python
import pymupdf

# 推荐用上下文管理器，确保文件流关闭
with pymupdf.open("input.pdf") as doc:
    print("页数:", doc.page_count)
    print("是否加密:", doc.is_encrypted)
    print("是否需要密码:", doc.needs_pass)
    print("元数据:", doc.metadata)
    print("目录:", doc.get_toc())

    page = doc[0]                       # 支持下标与切片
    print("页面尺寸:", page.rect)        # Rect(x0, y0, x1, y1)
    print("宽高:", page.rect.width, page.rect.height)
```

打开加密文档：

```python
doc = pymupdf.open("secret.pdf", password="your-password")
```

从内存 / 字节流打开：

```python
with open("input.pdf", "rb") as f:
    data = f.read()

doc = pymupdf.open(stream=data, filetype="pdf")
```

---

## 二、文本提取的几种姿势

### 纯文本

```python
with pymupdf.open("input.pdf") as doc:
    full = "\n".join(page.get_text() for page in doc)
```

### 按页分块（RAG 常用）

```python
with pymupdf.open("input.pdf") as doc:
    for page in doc:
        text = page.get_text().strip()
        if text:
            print({"page": page.number + 1, "text": text})
```

`page.number` 是 **0 起始**的。对外输出页码时记得 +1。

### 词级（带边界框）

```python
with pymupdf.open("input.pdf") as doc:
    page = doc[0]
    for x0, y0, x1, y1, word, block_no, line_no, word_no in page.get_text("words"):
        print(f"{word!r}  bbox=({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f})")
```

### 富结构（字体、字号、颜色）

```python
with pymupdf.open("input.pdf") as doc:
    page = doc[0]
    d = page.get_text("dict")
    for block in d["blocks"]:
        if block["type"] != 0:          # 0 = 文本块，1 = 图片块
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                print(f"{span['text']!r}  font={span['font']}  "
                      f"size={span['size']:.1f}  color={span['color']:#08x}  "
                      f"bbox={span['bbox']}")
```

### 用字号推断标题层级

这是把 PDF 转成结构化 Markdown 的常见手段：

```python
from collections import Counter
import pymupdf

with pymupdf.open("input.pdf") as doc:
    page = doc[0]
    sizes = Counter()
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    sizes[round(span["size"], 1)] += len(span["text"])

    # 正文字号 = 出现字符数最多的那个
    body = sizes.most_common(1)[0][0]
    print("正文字号:", body)

    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["size"] > body * 1.2 and span["text"].strip():
                    print("#" * max(1, int(body * 2 / span["size"])), span["text"])
```

### 提取指定区域

```python
with pymupdf.open("input.pdf") as doc:
    page = doc[0]
    clip = pymupdf.Rect(50, 100, 400, 300)
    print(page.get_text("text", clip=clip))
```

### 多栏版面：按栏切开再提取

`pymupdf4llm` 能自动处理多栏，但纯核心包需要自己切：

```python
with pymupdf.open("paper.pdf") as doc:
    page = doc[0]
    mid = page.rect.width / 2
    left  = page.get_text("text", clip=pymupdf.Rect(0, 0, mid, page.rect.height))
    right = page.get_text("text", clip=pymupdf.Rect(mid, 0, page.rect.width, page.rect.height))
    print(left)
    print(right)
```

### 复用 TextPage 提速

```python
with pymupdf.open("input.pdf") as doc:
    page = doc[0]
    tp = page.get_textpage()                 # 只建一次，这是贵的部分
    text  = page.get_text("text",  textpage=tp)
    words = page.get_text("words", textpage=tp)
    d     = page.get_text("dict",  textpage=tp)
```

官方给的数字：反复提取同一页时能省 **50–95%** 时间。

---

## 三、表格

```python
import pymupdf

with pymupdf.open("spreadsheet.pdf") as doc:
    for page in doc:
        tables = page.find_tables()
        for i, table in enumerate(tables):
            print(f"--- 第 {page.number + 1} 页 表 {i} ---")
            print("位置:", table.bbox)
            print("行数:", table.row_count, "列数:", table.col_count)
            print(table.to_markdown())

            # 需要 pandas 时
            # df = table.to_pandas()
```

### 提取表格到 CSV

```python
import csv
import pymupdf

with pymupdf.open("report.pdf") as doc, \
     open("tables.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    for page in doc:
        for table in page.find_tables():
            for row in table.extract():
                writer.writerow(["" if c is None else c for c in row])
```

单元格可能是 `None`，写之前要兜底。

---

## 四、渲染与图片

### 页面转 PNG

```python
import pymupdf

with pymupdf.open("input.pdf") as doc:
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        pix.save(f"page_{page.number + 1:04d}.png")
```

`dpi` 与 `matrix` 二选一。需要精确控制缩放用矩阵：

```python
zoom = 2.0
mat = pymupdf.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
```

### 直接拿字节（不落盘）

```python
pix = page.get_pixmap(dpi=150)
png_bytes = pix.tobytes("png")
jpg_bytes = pix.tobytes("jpg", jpg_quality=85)
```

### 页面转 SVG

```python
with pymupdf.open("input.pdf") as doc:
    page = doc[0]
    svg = page.get_svg_image(text_as_path=False)
    with open("page.svg", "w", encoding="utf-8") as f:
        f.write(svg)
```

### 提取嵌入图片

```python
from pathlib import Path
import pymupdf

with pymupdf.open("input.pdf") as doc:
    out = Path("images")
    out.mkdir(exist_ok=True)

    for page in doc:
        for img in page.get_images():
            xref = img[0]
            pix = pymupdf.Pixmap(doc, xref)
            if pix.n > 4:                        # CMYK 等要转 RGB
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            pix.save(out / f"p{page.number}_{xref}.png")
```

**注意**：`get_images()` 只列嵌入的位图。图表如果是矢量绘制的，这里什么都拿不到——那种情况只能整页栅格化。

更完整的提取（含图片在页面上的位置与变换矩阵）用 `page.get_image_info()`。

---

## 五、批注、标注与脱敏

### 搜索 + 高亮

```python
import pymupdf

with pymupdf.open("input.pdf") as doc:
    for page in doc:
        for rect in page.search_for("confidential"):
            page.add_highlight_annot(rect)
    doc.save("highlighted.pdf")
```

斜排 / 竖排文字要高亮得准：

```python
quads = page.search_for("important term", quads=True)
page.add_highlight_annot(quads)
```

其他文本标注：`add_underline_annot()`、`add_strikeout_annot()`、`add_squiggly_annot()`。自由文本用 `add_freetext_annot()`。

### 永久脱敏（两步）

```python
import pymupdf

with pymupdf.open("contract.pdf") as doc:
    for page in doc:
        for rect in page.search_for("confidential"):
            page.add_redact_annot(rect, fill=(1, 1, 1))

        # 关键：不调这一步，内容还在文件里，只是被画了个框
        page.apply_redactions()

    doc.save("contract_redacted.pdf")
```

**验证脱敏真的生效**：

```python
with pymupdf.open("contract_redacted.pdf") as doc:
    for page in doc:
        assert "confidential" not in page.get_text().lower(), \
            f"第 {page.number + 1} 页还能提取出敏感词！"
```

`apply_redactions()` 之后原始内容**永久消失，无法恢复**。所以设计成两步，让你能先审阅标记结果再执行。

### 带自定义外观的脱敏

```python
page.add_redact_annot(
    rect,
    text="REDACTED",            # 在抹掉的位置写上替代文本
    fontname="helv",
    fontsize=8,
    fill=(0, 0, 0),
    text_color=(1, 1, 1),
    align=pymupdf.TEXT_ALIGN_CENTER,
)
page.apply_redactions()
```

---

## 六、创建与编辑

### 新建 PDF 并写文字

```python
import pymupdf

doc = pymupdf.new()                     # 或 pymupdf.open()
page = doc.new_page(width=595, height=842)      # A4，单位是点

page.insert_text(
    pymupdf.Point(72, 100),
    "Hello, PDF!",
    fontsize=12,
    fontname="helv",
)

doc.save("new.pdf")
```

**A4 尺寸**：595 × 842 点（72 DPI 下）。Letter 是 612 × 792。

### 从 Markdown 生成 PDF

```python
import pymupdf

md_doc = pymupdf.open("example.md")
md_doc.save("example.pdf")
```

### 写中文

内置基础字体不含中文字形。装 `pymupdf-fonts` 后用扩展字体，或显式加载字体文件：

```python
import pymupdf

doc = pymupdf.open()
page = doc.new_page()

# 方式一：用 pymupdf-fonts 里的字体名
page.insert_text(pymupdf.Point(72, 100), "中文测试", fontname="china-s")

# 方式二：加载字体文件
font = pymupdf.Font(fontfile="C:/Windows/Fonts/msyh.ttc")
page.insert_text(pymupdf.Point(72, 140), "中文测试", fontname="msyh", fontfile="C:/Windows/Fonts/msyh.ttc")

doc.save("cn.pdf")
```

### 插入图片

```python
with pymupdf.open("input.pdf") as doc:
    page = doc[0]
    rect = pymupdf.Rect(100, 100, 300, 200)
    page.insert_image(rect, filename="logo.png")
    doc.save("with_logo.pdf")
```

也支持传 `stream=`（字节）。插入已有 PDF 页作为图片用 `show_pdf_page()`。

### 合并

```python
import pymupdf

out = pymupdf.open()
for path in ["a.pdf", "b.pdf", "c.pdf"]:
    with pymupdf.open(path) as src:
        out.insert_pdf(src)

out.save("merged.pdf")
```

指定页码范围与逆序：

```python
out.insert_pdf(src, from_page=2, to_page=5)
out.insert_pdf(src, from_page=src.page_count - 1, to_page=0, reverse=True)
```

### 拆分

```python
import pymupdf

with pymupdf.open("input.pdf") as doc:
    for i in range(doc.page_count):
        out = pymupdf.open()
        out.insert_pdf(doc, from_page=i, to_page=i)
        out.save(f"page_{i + 1:04d}.pdf")
        out.close()
```

按固定份数拆分（每 10 页一个文件）：

```python
import pymupdf

with pymupdf.open("input.pdf") as doc:
    step = 10
    for start in range(0, doc.page_count, step):
        end = min(start + step - 1, doc.page_count - 1)
        out = pymupdf.open()
        out.insert_pdf(doc, from_page=start, to_page=end)
        out.save(f"part_{start // step + 1:03d}.pdf")
        out.close()
```

### 删除 / 重排页面

```python
with pymupdf.open("input.pdf") as doc:
    doc.delete_page(0)                        # 删第 1 页
    doc.delete_pages([2, 3, 5])               # 删多页
    doc.select([2, 0, 1])                     # 只保留这三页并按此顺序排列
    doc.move_page(0, 3)                       # 把第 1 页移到位置 3
    doc.save("edited.pdf")
```

### 水印

```python
import pymupdf

with pymupdf.open("input.pdf") as doc:
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

### 页码

```python
import pymupdf

with pymupdf.open("input.pdf") as doc:
    for page in doc:
        page.insert_text(
            pymupdf.Point(page.rect.width / 2, page.rect.height - 40),
            f"{page.number + 1} / {doc.page_count}",
            fontsize=9,
            fontname="helv",
        )
    doc.save("numbered.pdf")
```

---

## 七、元数据与书签

```python
import pymupdf

with pymupdf.open("input.pdf") as doc:
    print(doc.metadata)

    doc.set_metadata({
        "title": "Annual Report 2025",
        "author": "Finance Team",
        "subject": "Yearly summary",
        "keywords": "annual, finance, 2025",
        "creator": "My Tool",
    })

    doc.set_toc([
        [1, "第一章 概述",   1],
        [2, "1.1 背景",      1],
        [1, "第二章 方法",   5],
    ])

    doc.save("output.pdf")
```

`get_toc()` 返回 `[[level, title, page], ...]`，`level` 从 1 起，`page` 从 1 起。

`doc.metadata` 里的键：`format`、`title`、`author`、`subject`、`keywords`、`creator`、`producer`、`creationDate`、`modDate`、`encryption`。

---

## 八、加密与权限

```python
import pymupdf

with pymupdf.open("input.pdf") as doc:
    doc.save(
        "encrypted.pdf",
        encryption=pymupdf.PDF_ENCRYPT_AES_256,   # 或 PDF_ENCRYPT_AES_128 / RC4_128 / RC4_40
        owner_pw="owner-password",                 # 所有者密码：控制权限
        user_pw="user-password",                   # 用户密码：打开文档需要
        permissions=(
            pymupdf.PDF_PERM_PRINT
            | pymupdf.PDF_PERM_COPY
        ),
    )
```

常用权限标志：`PDF_PERM_PRINT`、`PDF_PERM_MODIFY`、`PDF_PERM_COPY`、`PDF_PERM_ANNOTATE`、`PDF_PERM_FORM`、`PDF_PERM_ACCESSIBILITY`、`PDF_PERM_ASSEMBLE`、`PDF_PERM_PRINT_HQ`。

**权限位不是安全边界**——很多阅读器不强制执行。真正的机密内容必须实际删除（脱敏），不能靠"禁止复制"。

---

## 九、OCR

### 先判断这一页需不需要 OCR

```python
with pymupdf.open("scan.pdf") as doc:
    page = doc[0]
    if not page.get_text().strip():
        print("没有文字层，需要 OCR")
```

### 整页 OCR

```python
import pymupdf

with pymupdf.open("scanned.pdf") as doc:
    page = doc[0]
    tp = page.get_textpage_ocr(language="eng")     # 多语言用 "eng+chi_sim"
    text = page.get_text(textpage=tp)
    print(text)
```

### 局部 OCR（只识别指定区域，更快）

```python
tp = page.get_textpage_ocr(language="eng", clip=pymupdf.Rect(50, 100, 500, 400))
text = page.get_text(textpage=tp)
```

### 把 OCR 结果做成可搜索的 PDF

```python
import pymupdf

with pymupdf.open("scanned.pdf") as doc:
    for page in doc:
        tp = page.get_textpage_ocr(language="eng")
        page.get_text(textpage=tp)
    # 会用 OCR 得到的文字层替换原页面的文字层
    doc.save("searchable.pdf", deflate=True)
```

### 对独立图片做 OCR

图片带 alpha 通道时 OCR 不支持，要先去掉：

```python
import pymupdf

pix = pymupdf.Pixmap("image.png")
if pix.alpha:
    pix = pymupdf.Pixmap(pix, 0)          # 去 alpha

doc = pymupdf.open()
page = doc.new_page(width=pix.width, height=pix.height)
page.insert_image(page.rect, pixmap=pix)

tp = page.get_textpage_ocr()
print(page.get_text(textpage=tp))
```

### 指定 tessdata 路径

自动发现可能调用 `tesseract` 可执行文件来列语言。受限环境里显式给路径：

```python
tp = page.get_textpage_ocr(
    language="eng",
    tessdata="/usr/share/tesseract-ocr/5/tessdata",
)
```

或设环境变量 `TESSDATA_PREFIX`。

---

## 十、表单

### 读取

```python
import pymupdf

with pymupdf.open("form.pdf") as doc:
    for page in doc:
        for field in page.widgets():
            print(f"{field.field_name!r} = {field.field_value!r}  type={field.field_type_string}")
```

### 填写

```python
import pymupdf

with pymupdf.open("form.pdf") as doc:
    page = doc[0]
    for field in page.widgets():
        if field.field_name == "First Name":
            field.field_value = "Ada"
            field.update()                    # 别忘了
    doc.save("filled.pdf")
```

复选框用 `field.field_value = True`（或者按 `field.on_state()` 取到的值）。

---

## 十一、批量处理：多进程

PyMuPDF **不支持多线程**。批量任务用多进程：

```python
import os
from multiprocessing import Pool
import pymupdf


def extract_page_text(args):
    path, start, end = args
    with pymupdf.open(path) as doc:
        return [
            {"file": os.path.basename(path), "page": i + 1, "text": doc[i].get_text()}
            for i in range(start, min(end, doc.page_count))
        ]


def chunk_ranges(page_count, chunk_size):
    return [(i, min(i + chunk_size, page_count)) for i in range(0, page_count, chunk_size)]


if __name__ == "__main__":                    # Windows 上必须
    path = "big.pdf"
    with pymupdf.open(path) as doc:
        total = doc.page_count

    jobs = [(path, s, e) for s, e in chunk_ranges(total, 25)]

    with Pool(os.cpu_count()) as pool:
        results = pool.map(extract_page_text, jobs)

    flat = [item for sub in results for item in sub]
    print("共提取", len(flat), "页")
```

**要点**：

- 每个进程**自己打开文件句柄**，不要跨进程传 `Document` 对象。
- `if __name__ == "__main__":` 保护在 Windows（spawn 启动方式）上**必需**，否则无限递归创建进程。
- 分块粒度要试：太细则进程启动开销占主导，太粗则负载不均。
- 每个 `Document` 用完就关，避免句柄泄漏。

### 批量转换目录下所有 PDF

```python
import os
from pathlib import Path
from multiprocessing import Pool
import pymupdf


def convert_one(path):
    try:
        with pymupdf.open(path) as doc:
            text = "\n".join(p.get_text() for p in doc)
        out = Path("out") / (Path(path).stem + ".txt")
        out.parent.mkdir(exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return (path, True, None)
    except Exception as e:                    # 单个文件失败不能拖垮整批
        return (path, False, repr(e))


if __name__ == "__main__":
    pdfs = sorted(str(p) for p in Path("pdfs").glob("*.pdf"))
    with Pool(os.cpu_count()) as pool:
        for path, ok, err in pool.map(convert_one, pdfs):
            print("OK " if ok else "FAIL", path, err or "")
```

---

## 十二、面向 LLM 的输出

```python
import pymupdf4llm

md = pymupdf4llm.to_markdown("report.pdf")
print(md)

# 其他入口
# data = pymupdf4llm.to_json("report.pdf")
# text = pymupdf4llm.to_text("report.pdf")
```

它会把正文与表格一起输出成整合的 Markdown：表格被检测、转成 GitHub 兼容语法，并按正确阅读顺序穿插在文本之间。支持多栏版面、自然阅读顺序与分页 chunk。

**注意**：`pymupdf4llm` 是独立的包，需要单独 `pip install pymupdf4llm`，其授权也需单独确认。

### 直接进向量库的分块套路

```python
import pymupdf4llm

chunks = pymupdf4llm.to_markdown(
    "report.pdf",
    page_chunks=True,          # 按页返回，便于带页码元数据
)

for ch in chunks:
    print(ch["metadata"])      # 含页码等信息
    print(ch["text"][:200])
```

具体参数名以你安装版本的官方文档为准。

---

## 十三、命令行

PyMuPDF 提供 `pymupdf` 命令行工具，具体子命令随版本变化。**以你安装版本的 `pymupdf --help` 与官方文档为准**，不要照搬网上旧版本的用法。日常操作建议直接写 Python 脚本，可控性更好。
