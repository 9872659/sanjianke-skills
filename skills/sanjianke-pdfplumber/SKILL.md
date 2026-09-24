---
name: sanjianke-pdfplumber
slug: sanjianke-pdfplumber
displayName: 三剪客 · PDF 精细提取
description: "逐字符、逐线条地拆解 PDF，带表格提取与可视化调参的 Python 库，适合从机器生成的 PDF 里稳定取数与定位。 遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "表格取不准的时候，光有 extract_text() 是不够的——你需要看到字符、线条、矩形各自的坐标，才能判断该用哪种策略。pdfplumber 把 PDF 拆到每个字符和每条线，配上裁剪、过滤与可视化调试，让「为什么这个表格取错了」变成能看出来的事。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - PDF
  - 文档处理
  - Python
  - 表格提取
---

# 三剪客 · PDF 精细提取

从 PDF 里取数是这种活：简单的时候一行 `extract_text()` 就够了，稍微复杂一点——跨页表格、双栏排版、页眉页脚混进正文、合并单元格——就会卡住，而且**你根本不知道错在哪**：是 PDF 里没有那条线？还是线太短被过滤了？还是列的间距被判定成了空格？

pdfplumber 的定位就是解这个问题：它不只给你文本，而是把 PDF 拆到**每个字符、每条线、每个矩形、每条曲线**，每个对象都带完整坐标（`x0`/`x1`/`top`/`bottom`/`size`/`fontname`）。在此基础上给两个更高层的能力：可高度定制的表格提取，以及**可视化调试**——把识别出的线、交点、单元格画回页面上，直接看算法是怎么理解你的 PDF 的。

它建立在 `pdfminer.six` 之上，**最适合机器生成的 PDF**（Word / LaTeX / 报表系统导出的），不是扫描件。

**上游项目**：`pdfplumber`　**仓库**：https://github.com/jsvine/pdfplumber

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 纯本地解析，不联网 |
| 读取文件 | 是（必需） | 打开待解析的 PDF 文件路径，或传入已加载的字节 / 文件对象 |
| 写入文件 | 视需要 | 导出 CSV / JSON，或把可视化调试图存成 PNG |
| 凭证 | 视需要 | 仅当 PDF 本身加密时用于 `password=` 参数解密；不涉及任何外部账号 |
| 子进程 / 后台常驻 | 视需要 | 用 `pdfplumber` 命令行工具时会有子进程；批量任务建议自己写脚本而不是拼命令 |

**密钥与费用**：本 Skill 不内嵌任何密钥、不代理请求、不代收费用。pdfplumber 是 MIT 许可的纯本地库，没有任何计费与配额。

## 什么时候用 / 不用

**该用**：

- 「帮我从这个 PDF 的表格里把数据抽出来，要结构化」——`extract_tables()`。
- 「表格提取结果不对，不知道是哪里识别错了」——`to_image()` + `debug_tablefinder()` 可视化排查。
- 「只要页面中间那一块，页眉页脚不要」——`crop()` / `within_bbox()` / `outside_bbox()`。
- 「这些字是斜的（扫描后旋转过），提取出来顺序乱了」——`chars` 里的 `upright` 与 `matrix`，配 `CTM` 算旋转角。
- 「要按坐标定位，找出每个字符在哪一行哪一列」——直接用 `chars` 的 `x0` / `top` / `doctop`。
- 「这份 PDF 的表单填了什么值，帮我读出来」——经 `pdfminer` 的底层包装读 AcroForm。
- 「把整份 PDF 的字符 / 线条 / 矩形转成 CSV 做分析」——命令行 `pdfplumber file.pdf`。


**不该用**：

- 要快 —— 底层是纯 Python 的 pdfminer.six，官方自己写明 PyMuPDF「substantially faster」；上百页或大批量请换 PyMuPDF。
- 面对扫描件或纯图片页 —— 没有文本层就一个字也抽不出来，先做 OCR。
- 要写、改、合并、拆分、加水印、改元数据 —— 它只读不写，这些交给 pypdf / pikepdf / qpdf。
- 要把页面里的图片导出成文件 —— `images` 只给位置与格式元信息，不提供重建图片内容的方法。
- 要自动识别标题层级、引用块这类版式语义 —— 它不做通用版面分析，得你自己按字号与坐标写规则。
- 对合并单元格、跨页表格、嵌套表格要求完全正确 —— 表格提取是启发式的，而且 Markdown 式二维数组本身就装不下这些结构。
- 要依赖官方文档里标为 TKTK（待补）的 `char` 字段（如 `ncs`、`stroking_pattern`）—— 这些字段未定稿，不要依赖。
- 要长期处理大文档又不打算 `close()` —— `Page` 会缓存布局与对象信息，内存会持续上涨。
- 要用 `extract_text(layout=True)`、`extract_text_lines()`、`search()` 做稳定生产依赖 —— 官方标注为实验性，跨版本行为可能变。

## 安装

```bash
pip install pdfplumber
```

升级到最新版：

```bash
pip install --upgrade pdfplumber
```

**Python 版本要求**：官方在 **Python 3.10 – 3.14** 上做测试。PyPI 上包的 `requires_python` 写的是 `>=3.8`，但官方 CI 覆盖范围是从 3.10 起——**以 3.10+ 为准更稳**。

**虚拟环境**（推荐，避免和系统里的 `pdfminer.six` 版本打架）：

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install pdfplumber
```

安装后会自动带上 `pdfminer.six`；命令行工具 `pdfplumber` 随包一起装好，无需额外步骤。

## 常用操作

**1. 最小可用：打开、取文本**

```python
import pdfplumber

with pdfplumber.open("path/to/file.pdf") as pdf:
    first_page = pdf.pages[0]
    print(first_page.extract_text())
```

`open()` 接受三种输入：文件路径、已加载字节的文件对象、或 bytes 本身。返回 `pdfplumber.PDF` 对象。

**2. 命令行快速摸底**

```bash
# 每个字符 / 线条 / 矩形一行，输出 CSV
pdfplumber background-checks.pdf > background-checks.csv

# 只要纯文本（等价于 extract_text(layout=True)）
pdfplumber --format text report.pdf

# 只要第 1、11–15 页
pdfplumber --pages "1, 11-15" report.pdf

# 只要字符和线条，不要图片，精度截到 2 位小数
pdfplumber --types char line --precision 2 report.pdf
```

命令行选项：

| 参数 | 说明 |
|---|---|
| `--format [format]` | `csv`（默认）/ `json` / `text`。`json` 比 `csv` 信息更全，含 PDF 级与页级元数据、字典嵌套属性；`text` 输出 `extract_text(layout=True)` 的纯文本 |
| `--pages [list]` | 1 起始的页码列表或连字符范围，如 `1, 11-15` |
| `--types [list]` | 要提取的对象类型：`char` / `rect` / `line` / `curve` / `image` / `annot` 等，默认全部 |
| `--laparams` | JSON 字符串，透传给 `pdfplumber.open(..., laparams=...)`，如 `'{"detect_vertical": true}'` |
| `--precision [int]` | 浮点数保留几位小数，默认不舍入 |

**3. 表格提取**

```python
import pdfplumber

with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]

    # 页面上所有表格：table -> row -> cell
    for table in page.extract_tables():
        for row in table:
            print(row)

    # 只要最大的那张表：row -> cell
    print(page.extract_table())
```

想拿到更丰富的对象（能访问 `.cells` / `.rows` / `.columns` / `.bbox`）用 `find_tables()`：

```python
with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]
    for table in page.find_tables():
        print(table.bbox)                 # 表格在页面上的位置
        print(table.extract())            # 二维内容
        print(len(table.rows), len(table.columns))
```

`find_table()` 只返回最大的一张（按单元格数量算，并列时取更靠页面顶部的）。

**4. 无框线表格：改用 text 策略**

默认两种策略都是 `"lines"`——靠页面上的**线条**当单元格边界。很多报表和论文的表格根本没有竖线，这时候要换策略：

```python
table_settings = {
    "vertical_strategy": "text",     # 靠文字对齐推出竖线
    "horizontal_strategy": "text",   # 靠文字顶部推出横线
    "min_words_vertical": 2,         # 至少 2 个词对齐才认这条线
    "min_words_horizontal": 1,
}

with pdfplumber.open("paper.pdf") as pdf:
    print(pdf.pages[0].extract_table(table_settings))
```

四种策略：

| 策略 | 含义 |
|---|---|
| `lines` | 用页面上的图形线条（**含矩形的边**）当边界 |
| `lines_strict` | 用图形线条，但**不把矩形的边**算进去 |
| `text` | 由文字的对齐推出边界：竖向用词的左/右/中心，横向用词的顶部 |
| `explicit` | 只用 `explicit_vertical_lines` / `explicit_horizontal_lines` 里明确给的行 |

**5. 裁剪 + 过滤，把噪音挡在外面**

页眉页脚、侧边栏是表格提取失败的头号原因。先把页面裁到目标区域再提表：

```python
with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]

    # 绝对坐标裁剪（x0, top, x1, bottom）
    cropped = page.crop((0, 100, page.width, page.height - 80))
    print(cropped.extract_table())

    # 或者用函数过滤对象：只保留某个字号以上的字符
    big = page.filter(lambda obj: obj.get("size", 0) >= 10)
    print(big.extract_text())
```

三个裁剪方法的区别很关键：

| 方法 | 保留规则 |
|---|---|
| `crop(bbox)` | 保留**至少有一部分**落在框内的对象，跨界对象会被切齐到框边 |
| `within_bbox(bbox)` | 只保留**完全在**框内的对象 |
| `outside_bbox(bbox)` | 只保留**完全在**框外的对象 |

三者都支持 `relative=True`（坐标按页面左上角偏移算）和 `strict=True`（默认，要求框必须在页面范围内）。

**6. 可视化调试：看清算法到底识别了什么**

这是 pdfplumber 最值钱的功能。表格提取不对时别瞎调参数，先把识别结果画出来看：

```python
with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]
    im = page.to_image(resolution=150)

    # 把识别出的线（红）、交点（圈）、表格（浅蓝）叠上去
    im.debug_tablefinder(table_settings={})

    im.save("debug.png")     # 存下来看
    # im.show()              # 或直接弹窗（REPL 里用）
```

`to_image()` 的常用参数：`resolution`（默认 72 DPI）、`width` / `height`、`antialias`、`force_mediabox`（用 mediabox 而不是 cropbox 的尺寸）。

拿到图后还能自己画：

```python
im = page.to_image(resolution=150)
im.draw_rects(page.extract_words()[0:5], stroke="red", stroke_width=1)
im.draw_hline(200, stroke="blue")
im.save("annotated.png")
```

**7. 逐字符定位**

需要精确坐标时直接读对象字典：

```python
with pdfplumber.open("file.pdf") as pdf:
    for ch in pdf.pages[0].chars:
        print(ch["text"], ch["x0"], ch["top"], ch["fontname"], ch["size"])
```

可用对象列表：`.chars`、`.lines`、`.rects`、`.curves`、`.images`、`.annots`、`.hyperlinks`，以及派生列表 `.rect_edges`、`.curve_edges`、`.edges`。

判断斜排文字（旋转过的）：

```python
from pdfplumber.ctm import CTM

my_char = pdf.pages[0].chars[3]
my_char_ctm = CTM(*my_char["matrix"])
print(my_char_ctm.skew_x)      # 旋转角
print(my_char["upright"])      # 是否正立
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 扫描件提取出来是空的 | pdfplumber **不做 OCR**，它只读 PDF 里已有的文字对象。扫描件里只有图片 | 先上 OCR（如 Tesseract）生成文字层，再用 pdfplumber；或换带 OCR 的方案 |
| 表格提取全空 / 结构错乱 | 默认策略是 `lines`，而这张表的单元格**没有线条**，或者只有横线没有竖线 | 换 `vertical_strategy` / `horizontal_strategy` 为 `text`，并按需调 `min_words_vertical` / `min_words_horizontal` |
| 表格多了一堆空行 / 少了列 | 页眉页脚、页码、侧边文字被当成表格内容 | 先 `crop()` 到正文区域再提表；或调 `edge_min_length` 过滤掉过短的线 |
| 线明明看得见却识别不到 | 线太短被 `edge_min_length`（默认 3）过滤了；虚线被初始过滤掉了 | 调小 `edge_min_length`；虚线场景调小 `edge_min_length_prefilter`（可试 `0.5`） |
| 单元格边界对不齐、列错位 | 相邻线之间有微小偏移，没被吸附到同一位置 | 调 `snap_tolerance`（默认 3），或分别调 `snap_x_tolerance` / `snap_y_tolerance` |
| 本该相连的线段断开成两截 | 线段端点差了一点点，超过了合并阈值 | 调 `join_tolerance`（或 `join_x_tolerance` / `join_y_tolerance`） |
| 垂直线和水平线明明交叉了却没构成交点 | 正交线的间距超过了 `intersection_tolerance`（默认 3） | 调大 `intersection_tolerance` 或分轴的 `intersection_x_tolerance` / `intersection_y_tolerance` |
| 同一段文字在输出里出现两遍 | PDF 为了做出**伪粗体**效果，把同样的字符叠画了两层 | 用 `page.dedupe_chars(tolerance=1)` 去重；它按文本 + 位置容差 + `extra_attrs` 判定重复 |
| 大 PDF 跑到一半内存爆了 | `Page` 对象默认**缓存**布局与对象信息以加速重复访问，大文件下很吃内存 | 用完一页就 `page.close()` 刷新缓存；或分批处理、及时释放 `PDF` 对象 |
| 处理 `filter()` 后的页面，转图片结果不对 | `to_image()` 能正确反映 `crop()` 的结果，但**无法体现 `filter()` 的改动** | 要出图就用 `crop()` 系列，别指望 `filter()` 的结果出现在图里 |
| 升级到 0.5.0 之后老代码全挂了 | 表格提取在 **v0.5.0** 做了彻底重设计，是不兼容变更 | 按新 API 重写（`extract_table(s)` + `table_settings`），参考官方示例 notebook |
| 多栏排版的文字顺序是乱的 | 默认按 x/y 位置排序，双栏页面会左右穿插 | 试 `extract_words(use_text_flow=True)`（按 PDF 内部字符流顺序，更接近拖选高亮的行为，但也不保证符合阅读逻辑）；或用 `crop()` 把每栏切开分别提取 |
| 元数据解析报警告 | 有些 PDF 的 Info 字段不合规，默认**只警告不报错** | 想严格失败就传 `strict_metadata=True`，让 `open()` 直接抛异常 |
| 中文提取出来是乱码或错字 | PDF 用了自定义字体编码但没有正确的 CMap，字形存在但映射不回 Unicode | 试 `unicode_norm="NFC"`（或 `NFD` / `NFKC` / `NFKD`）做 Unicode 归一化；根因是字体缺失 CMap，这种情况只能靠 OCR |
| 连字符断词导致搜索不到 | PDF 排版时把长单词从行尾断开，插入了连字符 | `search()` 用更宽松的正则（如 `impor-?\ntant` 这类模式），后处理时自己拼回 |

## 能力边界

**覆盖**：

- **对象级解析**：`chars`、`lines`、`rects`、`curves`、`images`、`annots`、`hyperlinks`，以及派生的 `rect_edges` / `curve_edges` / `edges`。每个对象都是带完整坐标与属性的 Python `dict`。
- **文本提取**：`extract_text()`（可用 `layout=True` 模拟版面）、`extract_text_simple()`、`extract_words()`（带边界框、支持 `extra_attrs` / `split_at_punctuation` / `expand_ligatures` / `return_chars`）、`extract_text_lines()`（实验性）、`search()`（正则或字符串、可忽略大小写、返回坐标与字符）、`dedupe_chars()`。
- **表格提取**：`extract_tables()` / `extract_table()` / `find_tables()` / `find_table()` / `debug_tablefinder()`。四种策略（`lines` / `lines_strict` / `text` / `explicit`）与全套容差参数可调。
- **页面几何操作**：`crop()` / `within_bbox()` / `outside_bbox()` / `filter()`，支持相对坐标。
- **可视化**：`to_image()` 出 `PageImage`，支持 `draw_line(s)` / `draw_vline(s)` / `draw_hline(s)` / `draw_rect(s)` / `draw_circle(s)`，以及 `debug_tablefinder()` 叠加识别结果。基于 Pillow。
- **加载控制**：`password=` 开加密 PDF、`laparams=` 透传给 pdfminer 的版面分析、`unicode_norm=` 做 Unicode 归一化、`strict_metadata=` 控制元数据容错。
- **底层访问**：通过 `pdfplumber.utils.pdfinternals` 里的 `resolve` / `resolve_and_decode` 读 AcroForm 表单字段（没有现成接口，需要自己写递归）。
- **命令行**：`pdfplumber` 可执行文件，支持 `--format` / `--pages` / `--types` / `--laparams` / `--precision`。

**不覆盖**：

- **不生成 PDF**。它只读不写，改不了内容。
- **不修改 PDF**。没有合并、拆分、编辑、加水印、改元数据这类能力。
- **不做 OCR**。扫描件、纯图片页提取不到任何文字。
- **对 OCR 后的 PDF 表格支持很弱**。即使先做了 OCR，OCR 生成的文字层往往没有可靠的对齐关系，表格策略会失效。
- **不导出图片内容**。`images` 只提供位置与元信息（尺寸、色彩空间、位深），**不提供重建图片内容的方法**。
- **不做通用版面分析**。不识别"这是一段引用""这是一个标题"，标题层级要你自己按字号/位置规则推断。
- **性能不是它的卖点**。它比 PyMuPDF 慢（后者是 C 引擎）——需要高速大批量处理时应该换 PyMuPDF。
- 本 Skill 内不含任何可复制的第三方源码，正文为原创整理，仅引用 API 名称、参数名、许可证等事实性信息。

## 依赖条件

- **Python**：官方测试覆盖 **3.10 – 3.14**。PyPI 声明 `>=3.8`，但建议按官方 CI 范围走 3.10+。
- **安装**：`pip install pdfplumber`，会带上 `pdfminer.six`。
- **可选依赖**：可视化功能（`to_image()`）依赖 **Pillow**，通常随 pdfplumber 一起装好。
- **网络**：不需要。完全离线。
- **凭据**：不需要任何账号或 Key。

## 已知限制

- **性能远低于 PyMuPDF**。底层是纯 Python 的 `pdfminer.six`。官方在文档里直接承认 PyMuPDF「substantially faster」，并把它列为需要速度时应该考虑的替代品。上百页的大文档要估好耗时。
- **表格提取是启发式的，没有保证**。它靠线条或文字对齐推断结构，对合并单元格、跨页表格、嵌套表格、表头跨列这些情况的处理都很有限——因为 Markdown 式的二维数组本身就装不下这些信息。
- **表格提取在 v0.5.0 是不兼容重写**。网上大量老教程用的是旧 API，照抄会失败。
- **内存占用需要主动管理**。`Page` 默认缓存布局与对象信息，大 PDF 上不 `close()` 会持续涨。
- **`filter()` 的结果无法可视化**。`to_image()` 只反映 `crop()` 系列的效果。
- **图像内容不可重建**。`images` 列表只有位置与格式元信息。
- **`extract_text(layout=True)`、`extract_text_lines()`、`search()` 属实验性功能**。官方明确标注了 experimental，跨版本行为可能有变化。
- **部分 `char` 属性在官方文档里标注为 TKTK**（待补），如 `ncs`、`stroking_pattern`、`non_stroking_pattern`，不要依赖这些字段。
- 许可证为 MIT。

## 自检清单

- [ ] 先确认这份 PDF 是**机器生成**的，不是扫描件——扫描件应先去 OCR，不要把空结果当成配置问题。
- [ ] 表格提取失败时，**先跑 `debug_tablefinder()` 出图看**，再决定调哪个参数，不要盲调。
- [ ] 判断过这张表靠什么分格：有线条用 `lines`，无框线用 `text`，都不行才考虑 `explicit`。
- [ ] 提表前已经 `crop()` 掉了页眉、页脚、页码。
- [ ] 调容差参数时一次只动一个（`snap_*` / `join_*` / `intersection_*` / `edge_min_length`），并观察 debug 图的变化。
- [ ] 输出疑似重复文字时，检查是不是伪粗体叠加，试过 `dedupe_chars()`。
- [ ] 大批量处理时，逐页 `close()` 或分批处理，确认内存没有单调增长。
- [ ] 需要可视化验证时用的是 `crop()`，没有用 `filter()`（它的改动不会出现在图里）。
- [ ] 加密 PDF 走的是 `password=` 参数，没有试图绕过保护。
- [ ] 需要性能的场景已评估是否该换 PyMuPDF，并记录了当前方案的耗时基线。
- [ ] 依赖版本锁定在 0.11.x 一线，避免 v0.5.0 那类不兼容变更带来的意外。
- [ ] 提取到的数据在入库前做过抽样人工核对，特别是数字列和合并单元格。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/tables.md` | 表格提取的完整策略与参数表、调参流程、跨页与无框线场景的处理思路 |
| `references/objects.md` | 对象属性全表（char / line / rect / curve / image）、坐标系约定、文本提取方法与容差语义 |
| `README.md` | 包说明 |
| https://github.com/jsvine/pdfplumber | 上游仓库（安装与完整文档以它为准） |

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
