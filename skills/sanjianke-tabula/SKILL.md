---
name: sanjianke-tabula
slug: sanjianke-tabula
displayName: 三剪客 · PDF 表格抽取
description: "tabula：PDF 表格抽取 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "tabula：PDF 表格抽取 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - PDF
  - 表格
  - Java
  - Python
---

# 三剪客 · PDF 表格抽取

它把 PDF 里画成表格的那部分内容，还原成有行有列的数据，而不是把整页文字揉成一坨。
常见场景是财报、对账单、银行流水、报表类 PDF——这些文件里的数字离开行列结构就没法用，
而通用文本抽取工具恰恰会把表格拍平。

这条线上有两个东西需要分清：**tabula-java** 是真正的抽取引擎（Java 库 + 命令行工具），
**tabula-py** 是它的 Python 封装，把引擎的输出来接成 pandas DataFrame。
也就是说，Python 里 `pip install tabula-py` 之后，本机仍然必须有一个 Java 运行时，
底层跑的还是那个 Java 引擎。

**上游项目**：`tabula`　**仓库**：https://github.com/tabulapdf/tabula-java

## 什么时候用 / 不用

**用它**：

- 用户说「这个 PDF 里有个表格，帮我导成 Excel / CSV」——行列表结构完整可还原。
- 要做批量对账、财报入库：一批格式相同的表格型 PDF，按页抽表写进数据库。
- PDF 有清晰的框线（表格线），想要最稳的抽取：lattice 模式对这类文件几乎开箱可用。
- 表格没有框线但列对齐规整（文字行按列排布）：stream 模式能靠文字位置切列。
- 需要在 Python 里直接把结果接进 pandas 做后续清洗、计算、可视化。

**不要用它**：

- 表格在扫描件里（没有文本层）——它读的是 PDF 文字层，扫描件必须先做 OCR。
- 只是想要整页纯文本——用普通文本抽取工具更省事，表格工具反而会引入多余切分。
- 表格结构极不规则、跨页合并、单元格内嵌套子表——按线条/位置推断的规则容易散架，人工校对成本可能超过收益。
- 环境里不能装 JVM（如极简容器、部分 Serverless 运行时）——tabula-py 依赖 Java，绕不开。
- 要抽取图表、图片、公式等非表格内容——不在能力范围内。
- 需要处理加密文件却不知道密码——引擎支持 `password` 参数，但没密码就没戏。

## 安装

先把两个概念对上：**tabula-java** 是引擎（提供 jar 与 `java -jar` 命令行），
**tabula-py** 是 Python 封装（内部调 Java 引擎，返回 DataFrame）。
所以**两条路都需要 Java 运行时**，只是操作入口不同。

```bash
# ============ 路线 A：tabula-py（Python 用户首选）============
# 前置：Java 8+ 已安装并加入 PATH（java -version 能跑）
pip install tabula-py

# 想要更快的执行（走 jpype 常驻 JVM，而不是每次起子进程）
pip install tabula-py[jpype]

# 最简验证
python -c "import tabula; print(tabula.read_pdf('test.pdf', pages='all'))"
```

```bash
# ============ 路线 B：tabula-java（纯 Java / 命令行）============
# 前置：Java 运行时
# 到仓库 releases 页下载带依赖的 jar：tabula-<版本>-jar-with-dependencies.jar
# 具体文件名与版本以 https://github.com/tabulapdf/tabula-java/releases 为准
java -jar target/tabula-<版本>-jar-with-dependencies.jar --help

# 从源码自行构建（需要 Maven）
git clone https://github.com/tabulapdf/tabula-java.git
cd tabula-java
mvn clean compile assembly:single
```

Python 封装默认会使用它自带的那份 tabula-java jar；如果你想换成自己准备的 jar，
设置环境变量 `TABULA_JAR` 指向该 jar 的路径即可。

## 常用操作

### A. Python（tabula-py）

```python
import tabula

# 1. 读出 DataFrame 列表：默认只抽第 1 页，要全部必须显式写 pages="all"
dfs = tabula.read_pdf("test.pdf", pages="all")
print(len(dfs), dfs[0].head())
# 传 URL 也可以，tabula-py 会先下载
dfs2 = tabula.read_pdf("https://example.com/report.pdf", pages="all")
```

```python
# 2. 直接导出文件：csv / tsv / json 三选一
tabula.convert_into("test.pdf", "output.csv", output_format="csv", pages="all")

# 3. 整目录批量转换，输出落在同目录下
tabula.convert_into_by_batch("input_directory", output_format="csv", pages="all")
```

```python
# 4. 切换抽取模式：有框线用 lattice，无框线靠文字位置用 stream
with_lines = tabula.read_pdf("test.pdf", pages=1, lattice=True)
no_lines   = tabula.read_pdf("test.pdf", pages=1, stream=True)
```

```python
# 5. 表格挤在一页的某个区域时，用 area 限定范围（top,left,bottom,right）
#    area 一给，guess 会自动失效；百分比要配合 relative_area=True
t = tabula.read_pdf("test.pdf", pages=1, area=[269.875, 12.75, 790.5, 561])
t_pct = tabula.read_pdf("test.pdf", pages=1, area=[0, 0, 100, 50], relative_area=True)

# 6. 列切得不对时手动指定列边界 x 坐标（必须升序）
t = tabula.read_pdf("test.pdf", pages=1, columns=[10.1, 20.2, 30.3])

# 7. 复用 Tabula App 导出的模板，保证多次抽取口径一致
tabula.read_pdf_with_template("test.pdf", "/path/to/data.tabula-template.json")

# 8. 加密文件、禁用 stderr 噪声、加大 JVM 内存
t = tabula.read_pdf("test.pdf", pages="all", password="****", silent=True,
                    java_options=["-Xmx256m"])
```

`read_pdf` 常用参数一览：`pages`（默认 `1`，可写 `'1-2,3'`、`'all'`、`[1,2]`）、`guess`（默认 `True`，
给了 `area` 就失效）、`area` / `relative_area`、`lattice` / `stream`、`columns` / `relative_columns`、
`multiple_tables`（默认 `True`）、`pandas_options`（如 `{'header': None}`）、`output_format`
（`dataframe` 或 `json`）、`force_subprocess`、`options`（直接透传 tabula-java 原始参数串）。

### B. 命令行（tabula-java）

```bash
JAR=target/tabula-1.0.5-jar-with-dependencies.jar

# 抽取所有页导出 CSV（--pages 默认只抽第 1 页，务必显式指定）
java -jar $JAR -p all -o out.csv report.pdf

# 无框线表格用 stream 模式，有框线用 lattice 模式
java -jar $JAR -t -p all -o out.csv report.pdf      # -t / --stream
java -jar $JAR -l -p all -o out.csv report.pdf      # -l / --lattice

# 限定分析区域与列边界，输出 JSON
java -jar $JAR -a 269.875,12.75,790.5,561 -c 10.1,20.2,30.3 -f JSON -p 1 report.pdf

# 整目录批量转换，并抑制 stderr 输出
java -jar $JAR -b /path/to/pdfs -f CSV -p all -i

# 带密码的文档
java -jar $JAR -s 'secret' -p all -o out.csv report.pdf
```

命令行主要开关：`-p/--pages`、`-o/--outfile`、`-f/--format`（CSV/TSV/JSON）、
`-a/--area`、`-c/--columns`、`-l/--lattice`、`-t/--stream`、`-g/--guess`、`-b/--batch`、
`-s/--password`、`-u/--use-line-returns`、`-i/--silent`、`-v/--version`。
`-n/--no-spreadsheet` 与 `-r/--spreadsheet` 已废弃，分别被 `-t` 与 `-l` 取代。
完整参数以 `--help` 输出和上游 README 为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 只抽出了第 1 页，后面的表格都没了 | `pages` 默认值是 `1`，不是 `all`，命令行 `-p` 同样默认第 1 页 | Python 传 `pages="all"` 或 `'1-3,5'`；命令行传 `-p all` |
| 报 `JavaNotFoundError` 或 `java` 不是内部命令 | tabula-py 是 Java 引擎的封装，只装了 Python 包不够 | 装 Java 8+ 并确保 `java -version` 在 PATH 里可执行；JVM 路径异常时设置 `JAVA_HOME` |
| 明明有表却抽不出来 / 抽出一堆碎块 | 抽取模式选错：lattice 靠框线，stream 靠文字位置 | 有框线用 `lattice=True`（`-l`），无框线用 `stream=True`（`-t`），两种都试一遍对比结果 |
| `multiple_tables=True` 时 `pandas_options` 报参数错误 | 该模式下走的是 `pd.DataFrame()` 而不是 `pd.read_csv()`，两者接受的选项不同 | 改用 `pd.DataFrame()` 支持的选项；或设 `multiple_tables=False` 走 `read_csv` 路径 |
| 报 `CSVParseError`，提示列数不一致 | 不同表格列数不同，合并解析失败 | 按提示设 `multiple_tables=True`，或给 `pandas_options` 传 `names` 显式指定列名 |
| 抽出来的数字是字符串 / 表头跑到第一行 | 结果由 `pd.DataFrame` 组装，列名可能变成 `Unnamed: 0` | 用 `pandas_options={'header': None}` 或 `names=[...]` 控制表头；数值列后面自己 `astype` 转换 |
| 指定了 `area` 但 `guess` 好像没生效 | 传了 `area` 时 `guess` 会被自动置为 `False` | 这是预期行为；想自动猜区域就不要传 `area` |
| 用百分比区域/列时结果完全不对 | 百分比值必须都在 0–100 之间且同时打开相对模式 | 区域用 `relative_area=True`，列用 `relative_columns=True` |
| `columns` 报错或切列诡异 | 列边界坐标必须按升序排列 | 把 `columns` 排好序再传（用 list/tuple 这类保序类型） |
| 每次都重新起 JVM，批量处理特别慢 | JVM 启动开销占了大部分时间 | 装 `tabula-py[jpype]` 走常驻 JVM；或改用命令行 `-b` 一次性处理整个目录；或自己写 JVM 程序复用 |
| 同一份文件每次抽的结果略有差异 | 自动猜测区域/列的结果会受参数影响 | 用 Tabula App 导出模板后走 `read_pdf_with_template`，把口径固定下来 |
| 中文/特殊字符乱码 | 编码不匹配 | 传 `encoding=` 指定编码；命令行加 `-Dfile.encoding=UTF8`（tabula-py 已在 encoding 为 utf-8 时自动补上该 JVM 参数） |
| `java_options` 设了没反应 | JVM 一旦启动就不再接受新的启动参数 | 把 `java_options` 放在同一个进程的第一次调用里；需要重置请重启 Python 进程 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视情况 | 输入传 URL 时会自动下载 PDF；本机路径输入不联网 |
| 读取文件 | 是 | 读取目标 PDF；批量模式还会遍历输入目录 |
| 写入文件 | 是 | `convert_into` / `convert_into_by_batch` 会写出 CSV/TSV/JSON；只调 `read_pdf` 则只在内存里返回 DataFrame |
| 凭证 | 否 | 不需要账号或 API Key；仅可能用到 PDF 自身的打开密码 |
| 子进程 / 后台常驻 | 是 | 默认以子进程方式调用 `java -jar`；安装 `jpype` 后会在进程内维护一个常驻 JVM |

## 触发场景

- 「把这份财报 PDF 的表格导成 Excel。」
- 「这 50 份对账单里都有流水表，帮我批量抽成 CSV。」
- 「PDF 里的表格复制出来就乱了，帮我还原成行列。」
- 「只要第 3 页那个表，别的地方不要。」
- 「抽完直接给我 DataFrame，我要接着算合计。」

## 能力边界

**覆盖**：

- 从 PDF 文字层抽取表格，输出为 pandas DataFrame、CSV、TSV 或 JSON。
- 两种抽取策略：lattice（依赖单元格框线）、stream（依赖文字位置对齐）。
- 精确定位：按页范围、按页面区域（`area`，支持百分比）、按列边界（`columns`）限定抽取范围。
- 多表处理：一页多表可分别返回（`multiple_tables=True`，默认）。
- 批量：整目录转换（Python `convert_into_by_batch` / 命令行 `-b`）。
- 模板复用：读取 Tabula App 导出的 JSON 模板，固定抽取口径。
- 加密文档：支持传入打开密码。
- Java 侧可以当库用：在任何 JVM 语言里编程式调用，自己取 `Table` / 行列对象做二次处理。
  上游 README 给出的最小路径是 `ObjectExtractor` 遍历页面 + `SpreadsheetExtractionAlgorithm` 抽表；
  仓库里另有表格区域检测与调试相关类（如 `technology.tabula.detectors.NurminenDetectionAlgorithm`
  与 `technology.tabula.debug.Debug`），用前请对照 Javadoc 确认签名。

**不覆盖**：

- 不做 OCR：扫描件、图片型 PDF 没有文字层，抽不出来。
- 不做版面分析与通用文档结构还原，只针对「表格」这一种结构。
- 不输出单元格的样式、颜色、合并单元格语义等版式信息。
- 不生成 PDF、不改 PDF、不做加密解密（只能读取时用密码打开）。
- 不是服务器 / API：官方路线图里才有服务化方案，现在要靠自己包一层。
- 不保证对任意 PDF 都准：结果质量取决于原文件的框线与排版规整程度。

## 依赖条件

- Java 运行时 8 或更高（tabula-py 官方要求 Java 8+，tabula-java 同理）。
- Python 侧（路线 A）：Python 3.9+，`tabula-py`，以及 pandas / numpy（随包安装）。
- Java 侧（路线 B）：只需 JRE 即可跑 jar；从源码构建需要 Maven 与 JDK。
- 选装：`jpype`（`pip install tabula-py[jpype]`）以获得更快执行。
- 环境变量 `TABULA_JAR` 可指定自带之外的自定义 jar 路径。
- 无需账号、无需 API Key。

## 已知限制

- 依赖 Java：环境里没有 JVM 就无法使用，Python 封装也不例外。
- JVM 启动开销明显，逐文件调用很慢，需要靠 jpype、批量模式或自写 JVM 程序摊薄。
- 对无框线且列未严格对齐的表格，stream 模式的列切分容易出错。
- 一页多表时切分结果取决于参数，可能需要用模板固定。
- 抽取结果是纯文本单元格，数值类型、日期类型都需要后续自行转换。
- 官方自述在 macOS 与 Ubuntu 上验证充分，Windows 可用但需按文档额外配置。

## 自检清单

- 执行前：
  - `java -version` 能输出（tabula-py 也要求）。
  - 用 `pdftotext` 或任意阅读器确认该 PDF **有文字层**，不是纯扫描图。
  - 先跑第 1 页看效果，再决定 lattice 还是 stream。
  - 表格只占页面一部分时，先量好区域坐标或百分比，避免把页眉页脚一起抽进来。
- 执行后：
  - 核对行数、列数与源文件是否一致，重点检查合计行和跨页表。
  - 检查数值列是否被当成字符串或出现 `Unnamed` 列名，必要时用 `pandas_options` 修正。
  - 批量任务先抽 2~3 份做人工比对，确认口径后再全量跑。
  - 结果要交付给别人时，保留一份可视化/截图对照，便于对方复核。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/tabulapdf/tabula-java | 上游仓库（安装与完整文档以它为准） |

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
