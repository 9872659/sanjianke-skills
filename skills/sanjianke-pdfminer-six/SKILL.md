---
name: sanjianke-pdfminer-six
slug: sanjianke-pdfminer-six
displayName: 三剪客 · PDF 文本布局解析
description: "pdfminer.six 纯 Python 解析 PDF：pdf2txt.py 抽文本、按坐标取字号字色与页面元素，不依赖外部渲染器。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "pdfminer.six 安装与 pdf2txt.py / dumppdf.py 常用命令，extract_text 与 extract_pages 的最小代码，以及 cid 乱码、扫描件无文本、版面顺序错乱等避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档处理
  - PDF
  - Python
---

# 三剪客 · PDF 文本布局解析

当一批 PDF 需要把文字拿出来用，而且**光有文字还不够**——还要知道每段文字在页面上的坐标、字号、字体、颜色，pdfminer.six 就是对口的工具。它纯 Python 实现，不依赖 poppler、不依赖 Ghostscript、不调外部命令，装完就能跑。

它和"PDF 转 Word""PDF 编辑"不是一类东西：它只做**解析和读取**，产出文本、HTML、XML 或页面元素对象，从不改写原文件。

**上游项目**：`pdfminer.six`　**仓库**：https://github.com/pdfminer/pdfminer.six

## 什么时候用 / 不用

**用它**：

- "把这个 PDF 的正文抽成 txt，我要丢给大模型做摘要"——`pdf2txt.py` 一条命令就够。
- "找出这份合同里所有加粗的条款"——`extract_pages()` 能拿到每个字符的 `fontname`、`size`、`bbox`，按属性筛。
- "PDF 里的文字按阅读顺序排乱了，我要自己控制段落顺序"——`LAParams` 的 `boxes_flow`、`line_margin` 这类参数就是给这种情况留的。
- "把 PDF 每页转成带坐标的 XML / HTML 方便做后续抽取"——`--output_type xml` 或 `html`。
- "是加密 PDF，我知道密码"——`--password` / `extract_text(password=...)` 直接支持 RC4 与 AES。
- "我想在纯 Python 环境里跑，不想在服务器上装 poppler-utils"——这是它相对 pdftotext 的最大优势。

**不要用它**：

- **扫描件、图片版 PDF**——pdfminer.six 是文本解析器，不做 OCR。抽出来是空的不是 bug，先去判断这 PDF 有没有文本层。
- **想改 PDF**：删页、合并、加水印、压缩——它没有写入能力，换 pikepdf / pypdf / pdfarranger。
- **急着抽表格**——它不认识"表格"这个概念，只认识文字块和线条，表格重建要自己写逻辑，或换 camelot / pdfplumber。
- **源 PDF 本身就没有 Unicode 映射**——抽出来会是 `(cid:xx)`，任何解析器都救不了，见下面「常见坑」。
- **追求极致速度的批量抽取**——纯 Python 解析比 poppler 命令慢，几万个文件的话先用 `pdftotext -layout` 做粗筛。

## 安装

要求 Python 3.10 或更新。官方推荐 pip 安装：

```bash
pip install pdfminer.six

# 需要抽 PDF 内嵌图片时，装可选依赖
pip install 'pdfminer.six[image]'

# 在虚拟环境里（推荐，避免污染系统 Python）
python -m venv .venv
.venv/bin/pip install pdfminer.six        # Windows: .venv\Scripts\pip install pdfminer.six
```

装完先验一下，这条能出信息就说明 `pdf2txt.py` 已经在 PATH 里：

```bash
pdf2txt.py --version
python -c "import pdfminer; print(pdfminer.__version__)"
```

其他安装途径（Conda、系统包管理器）以官方文档 https://pdfminersix.readthedocs.io 为准，本包不保证这些途径的包名与版本。

## 常用操作

**1. 抽全篇文本到文件**

```bash
pdf2txt.py -o out.txt input.pdf
```

不写 `-o` 时默认输出到标准输出，直接接管道更方便：

```bash
pdf2txt.py input.pdf | head -n 50
```

**2. 只抽指定页 / 限制页数**

```bash
# 只抽第 1、3、5 页（从 1 开始计数）
pdf2txt.py --page-numbers 1 3 5 input.pdf -o picked.txt

# 只处理前 10 页，用于快速试跑大文件
pdf2txt.py --maxpages 10 input.pdf -o head10.txt
```

**3. 输出 HTML / XML / tag，保留版面坐标信息**

```bash
pdf2txt.py -t xml  input.pdf -o out.xml     # 带每个字符的坐标
pdf2txt.py -t html input.pdf -o out.html    # html 专用参数见下
pdf2txt.py -t tag  input.pdf -o out.tag
```

`-t html` 时可以调版面模式与缩放：

```bash
pdf2txt.py -t html --layoutmode exact --scale 2.0 input.pdf -o out.html
```

**4. 从 PDF 里把图片抠出来**

```bash
pdf2txt.py input.pdf --output-dir extracted-images
```

必须有 `--output-dir`，不传这个参数**不会**抽图（图片默认被忽略）。且需要先装 `pdfminer.six[image]`。

**5. 加密 PDF**

```bash
pdf2txt.py --password 'your-password' locked.pdf -o out.txt
```

**6. 用 Python 直接取文本（最省事的高层接口）**

```python
from pdfminer.high_level import extract_text

text = extract_text("input.pdf")
print(text)

# 只取第 0、1、2 页（注意：这里的 page_numbers 是 0 基）
text = extract_text("input.pdf", page_numbers=[0, 1, 2], maxpages=3)
```

**7. 用 Python 取页面元素（要坐标 / 字号 / 字体时）**

```python
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar

for page_layout in extract_pages("input.pdf"):
    for element in page_layout:
        if isinstance(element, LTTextContainer):
            for text_line in element:
                for character in text_line:
                    if isinstance(character, LTChar):
                        # bbox 是 (x0, y0, x1, y1)，y 轴原点在页面左下角
                        print(character.get_text(), character.fontname,
                              round(character.size, 1), character.bbox)
```

**8. 调试用：把 PDF 内部结构导成 XML**

```bash
dumppdf.py -a input.pdf -o dump.xml       # 导出所有对象
dumppdf.py -T input.pdf                   # 只看大纲 / 目录结构
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 抽出来的文本里满是 `(cid:123)` | 该 PDF 字体缺少 ToUnicode 映射表，字符的 Unicode 值在文件里根本没存 | 先做官方给的判定法：用 PDF 阅读器**复制粘贴**这段文字。粘贴出来正常，说明还有救，换最新版 pdfminer.six 再试；粘贴出来也是乱码，说明源文件就没这个信息，任何工具都无解，只能走 OCR 重建文本层 |
| 输出是空文件，或只有页眉页脚 | 这是扫描/图片版 PDF，没有文本层；或者文字在图形对象里没被扫描到 | 用 `pdf2txt.py -A input.pdf`（`--all-texts`，对图形内的文字也做版面分析）先试一次；仍然为空就判定为扫描件，改走 OCR 路线 |
| 段落顺序乱、左右分栏被串成一坨 | 默认 `boxes-flow=0.5` 是横竖位置折中，双栏排版容易误判 | 双栏且内容以竖排流为主时试 `--boxes-flow 1.0`；只按水平位置排时试 `-1.0`；也可用 `--boxes-flow disabled` 退化成按文本框左下角排序。逐个值试，没有通解 |
| 单词之间没有空格，或者每个字母被拆成一行 | `word-margin`（默认 0.1）和 `char-margin`（默认 2.0）与这份 PDF 的字距不匹配 | 空格丢失就把 `--word-margin` 调大（如 0.2~0.5）；被拆行就调小 `--char-margin`。CJK 文档尤其常见，中文之间本就没有空格，属正常 |
| 抽图时报错或一张图都没有 | 没装 `pdfminer.six[image]`，或者忘了传 `--output-dir` | 两件事都要做：先 `pip install 'pdfminer.six[image]'`，再 `pdf2txt.py input.pdf --output-dir out-images` |
| 大 PDF 跑到内存爆掉 | `extract_text()` 会把整份文档的文本攒在内存里一次性返回 | 大文件用 `extract_text_to_fp()` 流式写文件，或分段处理：`extract_text(pdf, page_numbers=range(0, 100))` 一页页拿；也可以设 `caching=False` 关掉资源缓存换内存 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 安装依赖时 pip 需要联网；解析 PDF 本身完全离线 |
| 读取文件 | 是 | 读取待解析的 PDF 路径 |
| 写入文件 | 视情况 | 仅在指定 `-o` / `--output-dir` 时写出 txt/html/xml/tag 或图片；不加就只往标准输出打印 |
| 凭证 | 否 | 无账号、无 API Key。仅加密 PDF 需要用户自备打开密码，密码只在本机命令行使用 |
| 子进程 / 后台常驻 | 否 | 纯 Python 库 + 一次性命令行调用，无守护进程 |

## 触发场景

- "帮我把这份 PDF 的文字提取出来。"
- "这几百份 PDF 批量转成 txt，放一个目录里。"
- "我想知道 PDF 里标题用的是多大字号、什么字体。"
- "把 PDF 转成带坐标的 XML，我要按位置抽字段。"
- "PDF 有密码，密码是 xxxx，帮我打开读一下。"
- "这份 PDF 复制出来的文字是乱码，怎么回事？"

## 能力边界

**覆盖**：

- 从 PDF 源文件中提取文本，并按行、按段落做版面分析（`LAParams` 可调）
- 取到每个字符级别的属性：坐标 `bbox`、字号 `size`、字体 `fontname`、颜色等
- 输出 text / html / xml / tag 四种格式
- 抽取内嵌图片（JPG、PNG、TIFF、JBIG2、位图），需可选依赖
- 支持 CJK 与竖排文字，支持 Type1 / TrueType / Type3 / CID 字体
- 支持 RC4 与 AES 加密 PDF 的解密读取
- 提取 AcroForm 交互表单字段、大纲目录、tagged 内容
- 解析 ASCIIHex / ASCII85 / LZW / Flate / RunLength / CCITTFax 等压缩流

**不覆盖**：

- OCR：不识别图片里的文字，不生成文本层
- 写入与修改：不合并、不拆分、不删页、不加水印、不压缩、不重排页面
- 表格结构化：没有"表格"语义，行列还原需要自己写，或换专门工具
- 矢量图形、图层、批注的语义化提取
- 把 PDF 完美还原成 Word / Markdown 的排版

## 依赖条件

- Python 3.10 或更新版本（官方要求）
- `pip install pdfminer.six`；抽图额外装 `pdfminer.six[image]`
- 无需任何账号、Key 或外部二进制（不需要 poppler / Ghostscript / Java）
- 命令行工具 `pdf2txt.py`、`dumppdf.py` 随包安装，需保证 Python 的 Scripts 目录在 PATH 中

## 已知限制

1. 字体缺 ToUnicode 映射时只能输出 `(cid:x)`，这是 PDF 文件本身的信息缺失，换工具也解决不了。
2. 扫描件与纯图片 PDF 完全抽不出文字，官方定位就是文本解析器而非 OCR 工具。
3. 版面分析是启发式的，复杂双栏、图文混排、表格排版经常需要手工调 `LAParams` 参数，且参数值随文档而异，没有一组通用最优解。
4. 纯 Python 实现，解析速度慢于 poppler 的 `pdftotext`，超大文件或海量文件场景要权衡。
5. `extract_text()` 会把全文读进内存，超大 PDF 应改用流式接口或分批调用，否则可能 OOM。
6. 在 pdfminer.six 里 `extract_text_to_fp` 的 `output_type` 虽然列出 html / xml / hocr / tag，但官方注明只有 `text` 能正常工作，其他格式的稳定性以实际版本为准。

## 自检清单

执行前：

- [ ] 确认 PDF 有文本层（阅读器里能选中复制文字），否则先转 OCR 路线
- [ ] 确认 Python ≥ 3.10，且 `pdf2txt.py --version` 能正常输出
- [ ] 需要抽图时，确认已装 `pdfminer.six[image]` 并会传 `--output-dir`
- [ ] 加密 PDF 先拿到密码，别把密码写进脚本或日志
- [ ] 大文件先 `--maxpages 10` 试跑，确认版面参数合适再全量跑

执行后：

- [ ] 检查输出是否含大量 `(cid:` 或整体为空，若有先判定是文件问题还是参数问题
- [ ] 抽查段落顺序与换行是否符合预期，双栏文档重点看跨栏错位
- [ ] 统计输出字符数与页数大致匹配，防止静默丢页
- [ ] 确认输出文件路径与编码（默认 utf-8，可用 `-c` 指定）

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/pdfminer/pdfminer.six | 上游仓库（安装与完整文档以它为准） |
| https://pdfminersix.readthedocs.io | 官方文档：命令行参数、高层与组合式 API |

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
