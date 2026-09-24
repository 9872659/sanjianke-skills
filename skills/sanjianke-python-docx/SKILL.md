---
name: sanjianke-python-docx
slug: sanjianke-python-docx
displayName: 三剪客 · 读写 Word 文档
description: "python-docx：用 Python 读写 Word 文档 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "python-docx：用 Python 读写 Word 文档 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档处理
---

# 三剪客 · 读写 Word 文档

python-docx 是一个纯 Python 库，专门用来读、写、改 Word 2007+ 的 `.docx` 文件。
它不需要装 Office、不需要起 Word 进程，也不依赖 .NET 或 Java，靠 `lxml` 直接操作 docx 内部的 XML。

所以它的典型位置是：批量生成报告/合同/台账、往现成模板里填数、把一堆 docx 里的文字和表格抽出来。
它不是排版引擎，不负责决定「这页够不够放」，也不帮你把 Word 渲染成图片或 PDF。

**上游项目**：`python-docx`　**仓库**：https://github.com/python-openxml/python-docx

## 什么时候用 / 不用

**用它**：

- 用户说「按这个模板给 200 个客户各生成一份合同/通知书，字段从表格里取」。
- 用户说「把这几百个 docx 里的正文和表格内容抽出来，汇总成一个 Excel/CSV」。
- 用户说「在现成文档里替换某段文字、某个人名、某个日期」。
- 用户说「程序化生成一份带标题、表格、图片的 Word 报告」。
- 需要在 CI / 服务器 / 无图形界面环境里产出 Word，又不能装 Office。

**不要用它**：

- 文件是老的 `.doc`（Word 97-2003 二进制格式）——它只认 `.docx`，得先转换格式。
- 要精确控制分页、页码落点、页眉页脚在每一页的具体效果——它不做版面计算，也不重新排版页面。
- 要读批注、修订痕迹、内容控件、复杂域代码——这些不在它的对象模型里。
- 要 Word 转 PDF 或 docx 转图片——它既不渲染也不导出，找 LibreOffice 或专用转换器。
- 要处理 WPS 专有格式、或需要完美保真的复杂排版归档——用 Word 自动化或商业库更稳。

## 安装

```bash
# 标准安装（会自动带上 lxml 依赖）
pip install python-docx

# 国内网络慢时换源
pip install python-docx -i https://pypi.tuna.tsinghua.edu.cn/simple

# 指定版本
pip install "python-docx==1.2.0"

# 用 requirements 固定依赖
echo "python-docx>=1.1" >> requirements.txt
pip install -r requirements.txt
```

包名是 `python-docx`，但代码里导入的名字是 `docx`（`from docx import Document`），
两者不一致是最常见的「装完却说找不到模块」的原因，见下文常见坑。

## 常用操作

**1. 新建文档并分层级写入**

```python
from docx import Document

doc = Document()                      # 基于默认模板，相当于 Word 新建空白文档
doc.add_heading('季度结算说明', 0)     # level=0 是标题（Title）样式
doc.add_heading('一、总览', level=1)
doc.add_paragraph('本期共处理 1,284 笔。')
doc.save('report.docx')
```

**2. 段落里混排粗体/斜体——必须用 run**

```python
from docx import Document

doc = Document()
p = doc.add_paragraph('本期结论：')
p.add_run('超时率下降').bold = True   # 字符级格式落在 run 上
p.add_run('，但退单率上升。')          # run 之间不会自动加空格，要自己补
doc.save('runs.docx')
```

**3. 写表格（表头 + 逐行追加）**

```python
from docx import Document

doc = Document()
table = doc.add_table(rows=1, cols=3)
table.style = 'Table Grid'            # 不设样式就没有边框
hdr = table.rows[0].cells
hdr[0].text, hdr[1].text, hdr[2].text = '单号', '金额', '状态'

for no, amount, status in [('A001', '120.00', '已结'), ('A002', '88.50', '待结')]:
    cells = table.add_row().cells
    cells[0].text, cells[1].text, cells[2].text = no, amount, status

doc.save('table.docx')
```

**4. 插入图片并控制尺寸（不要直接写数字）**

```python
from docx import Document
from docx.shared import Inches, Cm

doc = Document()
doc.add_picture('logo.png', width=Inches(1.25))
doc.add_picture('chart.png', width=Cm(12))     # 只给一边，等比缩放
doc.save('with-image.docx')
```

**5. 打开已有文档并读取内容**

```python
from docx import Document

doc = Document('input.docx')

for i, p in enumerate(doc.paragraphs):
    if p.text.strip():
        print(i, p.style.name, p.text)

for t_i, table in enumerate(doc.tables):
    for row in table.rows:
        print(t_i, [cell.text for cell in row.cells])
```

**6. 页眉页脚（按节访问）**

```python
from docx import Document

doc = Document()
section = doc.sections[0]
section.header.paragraphs[0].text = '内部资料 · 请勿外传'
section.footer.paragraphs[0].text = '第 X 页'
doc.save('hdrftr.docx')
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `ModuleNotFoundError: No module named 'docx'` | 装的是名为 `docx` 的另一个包，或根本没装成功 | 先清掉冲突包再装本体：`pip uninstall docx python-docx`，然后 `pip install python-docx` |
| 打开 `.doc` 报 `PackageNotFoundError` / `BadZipFile` | `.doc` 是二进制格式，不是 zip 容器 | 先用转换器转成 `.docx`（例如 `soffice --headless --convert-to docx in.doc`）再处理 |
| `KeyError` 或样式不生效，如 `List Bullet` / `Intense Quote` 报错 | 这些样式名必须已在模板中定义；`Document()` 默认模板只带一部分 | 用自备模板 `Document('template.docx')`，先在 Word 里把样式建好；名称要与 Word 界面完全一致（含空格） |
| 只写 `width=2`，图片小到看不见 | 内部单位是 EMU，914400 EMU = 1 英寸，`2` 几乎等于零宽 | 一律用 `from docx.shared import Inches, Cm` 包一层 |
| 两个 run 拼起来少了空格 | run 之间不会自动插入空白 | 在前一个 run 的字符串末尾显式写空格 |
| 读取时漏掉表格里的文字 | `doc.paragraphs` 只返回正文段落，不含表格内文本 | 单独遍历 `doc.tables`；表格嵌套时还要往 `cell.tables` 里再走一层 |
| 生成的文档打开后页眉/页码不对 | 页眉页脚是「节」的属性，且默认 `is_linked_to_previous=True` | 先 `header.is_linked_to_previous = False` 再写内容，避免改到上一节的定义 |
| 想统计「第几页」却查不到 | 它不做版面计算，不知道分页结果 | 页码交给 Word 域或渲染器；不要指望在库里算出页数 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 仅安装时需要 | `pip install python-docx` 从 PyPI 拉包；运行时无需联网 |
| 读取文件 | 是 | 读取目标 `.docx`、模板与图片资源 |
| 写入文件 | 是 | 生成 `.docx` 输出；建议写新文件名而不是原地覆盖 |
| 凭证 | 否 | 不涉及账号、Key、密码 |
| 子进程 / 后台常驻 | 否 | 纯库调用，无常驻进程；仅格式转换时可能调外部转换器 |

## 触发场景

- 「把这批数据生成一份 Word 周报，带标题和表格」
- 「从 500 份简历 docx 里把姓名、电话、工作经历抽出来」
- 「把合同模板里的 `{甲方}` 替换成实际公司名，批量出 100 份」
- 「在文档末尾加一段带粗体重点的说明，再插一张图」
- 「给我一个不用装 Office 就能产 Word 的方案」
- 「这个 docx 读出来是乱码 / 读不到表格，帮我看看」

## 能力边界

**覆盖**：

- 创建、打开、修改、保存 `.docx`（Office Open XML 文字处理格式）。
- 段落、标题、run 级字符格式（粗体、斜体、下划线、字号、颜色）。
- 表格的创建、增行、单元格写入、内置表格样式套用。
- 段落样式与字符样式的应用（样式必须已在模板中定义）。
- 图片插入与等比缩放、分页符、节、页眉页脚。
- 正文与表格文本的提取，供后续做筛选、汇总、核对。

**不覆盖**：

- `.doc`、`.rtf`、`.odt`、`.wps` 等其他文字处理格式。
- 版面渲染：分页位置、页码实际值、字段计算结果、打印效果。
- Word 高级对象：批注、修订、内容控件、域代码、宏、目录自动更新、文本框与形状的完整模型。
- 导出 PDF / 图片 / HTML；也完全不涉及 OCR。
- 与 Office 365 云文档、SharePoint 的在线协作能力。

## 依赖条件

- Python 3.6 以上（实际使用建议 3.8+）。
- 自动依赖 `lxml`；`pip` 会一并装上，离线安装时要手动备好对应平台的 `lxml` 轮子。
- 不需要安装 Microsoft Office，也不需要 Windows。
- 不需要任何账号或 API Key。
- 若要处理 `.doc` 或导出 PDF，需要额外准备 LibreOffice 等外部转换器。

## 已知限制

1. 不重新排版页面：任何「这里放得下吗」「这是第几页」的问题它都回答不了。
2. 样式依赖模板：样式名必须先存在于打开的文档或模板中，库不会替你凭空创建内置样式。
3. 提取是「平铺」的：`doc.paragraphs` 与 `doc.tables` 分开取，段落与表格的原始先后顺序不直接给出。
4. 修订、批注等 Word 协作对象没有稳定的公开 API，遇到这类文件提取结果可能不完整。
5. 图片默认按像素与 DPI 推算尺寸，缺 DPI 信息时按 72 dpi 计算，往往需要显式指定宽或高。

## 自检清单

- [ ] 确认是 `.docx` 而不是 `.doc`；不是就先转换格式。
- [ ] 确认 `import docx` 能用，且版本符合预期（`pip show python-docx`）。
- [ ] 用到的样式名是否已在模板里定义？名字是否与 Word 界面完全一致？
- [ ] 图片尺寸是否用了 `Inches` / `Cm`，而不是裸数字？
- [ ] 是否遍历了 `doc.tables`，而不是只读 `doc.paragraphs`？
- [ ] 输出是否写到新文件，避免直接覆盖原始素材？
- [ ] 生成的文档是否用 Word / WPS / LibreOffice 真机打开验证过一遍？

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/python-openxml/python-docx | 上游仓库（安装与完整文档以它为准） |
| https://python-docx.readthedocs.io/en/latest/ | 官方文档：Quickstart、Tables、Sections、Headers/Footers、API 索引 |

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
