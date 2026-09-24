# Typst 常用写法速查

> 定位：写 `.typ` 源文件时的"够用清单"。**参数细节一律以官方 reference 为准**（版本间会新增/调整），这里只保证语法与函数名是主流用法。
> 文档站：https://typst.app/docs/reference/

## 一、标记语法（不用写代码就能排的部分）

```typst
= 一级标题
== 二级标题

这是一段正文。_斜体_、*粗体*、`等宽文本`、下标 #sub[2]、上标 #super[2]。

- 无序列表项
- 第二项
  - 嵌套一层

+ 有序列表项
+ 第二项

/ 术语：解释文字

// 单行注释
/* 块注释 */

转义：\# 不是代码起始，\* 不是粗体。
```

- `=` 的个数就是层级（`=` 一级、`==` 二级，以此类推）。
- 段落之间空一行；**标记语法对空格敏感**（数学里尤其，见下）。
- 想插代码/函数，用 `#` 起头：`#函数名(...)`；想插一段代码块用 `#{ ... }`。

## 二、函数、变量与脚本

```typst
#let count = 8                       // 变量
#let fib(n) = (                      // 函数（递归也没问题）
  if n <= 2 { 1 } else { fib(n - 1) + fib(n - 2) }
)
#let nums = range(1, count + 1)      // 数组

前 #count 项是：#nums.map(n => str(fib(n))).join("、")

#for i in range(1, 4) [第 #i 段。]

#if count > 5 [数量偏多] else [数量正常]

取值：#nums.at(0)、#nums.first()、#nums.last()、#nums.len()
```

- **内容块 `[ ... ]`** 是一等公民：可以当参数传，也可以当函数的返回值。
- **展开运算符 `..`** 把数组摊成逐个参数（`#table(..nums)` 这种写法就是靠它）。
- 表达式太长想换行，用括号包起来即可。

## 三、set 规则（配置元素默认行为）

```typst
#set page(paper: "a4", margin: 2cm, numbering: "1 / 1")
#set text(font: ("Noto Sans CJK SC", "Noto Serif CJK SC"), size: 10.5pt)
#set heading(numbering: "1.")
#set par(justify: true, leading: 0.8em)
#set document(title: "季度报告", author: "数据组")
```

页面尺寸可以跟随内容（适合做证书、单据这类"一页刚好"的文档）：

```typst
#set page(width: 10cm, height: auto)
```

## 四、show 规则（改写元素外观）

```typst
// show-set：只改某个元素的某个属性
#show heading: set text(font: "Noto Serif CJK SC")

// show：完全接管渲染
#show heading.where(level: 1): it => block(
  fill: luma(240), inset: 8pt, radius: 4pt, width: 100%, it,
)

// 纯文本替换
#show "teh": "the"
```

`show` 的通用写法是 `#show 选择器: 处理函数`，处理函数收到元素本身（习惯叫 `it`），返回新的内容。

## 五、数学

```typst
行内公式 $F_n = F_(n-1) + F_(n-2)$ 。

// 两侧留空格 → 独立公式块
$ F_n = round(1 / sqrt(5) phi.alt^n), quad
  phi.alt = (1 + sqrt(5)) / 2 $
```

- 多字母标识符会被当成 Typst 的标识符/函数（所以 `sqrt`、`floor` 不用反斜杠）；要当变量名连写就用引号包起来。
- 常见排版函数：`frac(a, b)`、`sqrt(x)`、`mat(...)`、`cases(...)`、`vec(...)`、`sum_(i=1)^n`、`integral_0^1`、`upright(...)`、`bold(...)`、`attach(...)`。
- 下标 `_`、上标 `^` 只吃一个 token，多项要加括号：`F_(n-1)`。

## 六、表格、图与目录

```typst
#table(
  columns: 3,
  table.header([地区], [数量], [金额]),
  [华东], [120], [¥12,000],
  [华南], [98],  [¥9,800],
  table.hline(),
  [合计], [218], [¥21,800],
)

#figure(
  image("chart.png", width: 80%),
  caption: [月度趋势],
) <fig-trend>

见 @fig-trend 。

#outline(title: [目录], depth: 2)
#pagebreak()
```

- `table` 的单元格是按行依次传的，所以配合 `..数组` 展开就能用循环铺数据。
- 交叉引用：给元素挂标签 `<名字>`，用 `@名字` 引它。
- 其他常用布局元素：`grid`、`columns`、`block`、`box`、`align`、`place`、`rect`、`line`。

## 七、读外部数据（模板化出 PDF 的关键）

```typst
#let data = json("data.json")           // JSON → 字典/数组
#let rows = csv("sales.csv")            // CSV → 数组的数组
#let conf = yaml("conf.yaml")           // YAML
#let raw  = read("note.txt")            // 纯文本
#let img  = image("logo.png")           // 图片
#include "chapter1.typ"                 // 把另一个文件的内容插进来
```

CSV 常见用法：

```typst
#let rows = csv("sales.csv", row-type: dictionary)   // 用表头当键
#for r in rows [地区：#r.at("region")，金额：#r.at("amount") ]

// 默认（数组形式）时按下标取，值都是字符串，要算数得自己转
#let total = rows.map(r => int(r.at(1))).sum()
合计 #total 。
```

## 八、一个完整骨架：数据驱动出报告

```typst
#set page(paper: "a4", margin: 2cm, numbering: "1 / 1")
#set text(font: ("Noto Sans CJK SC",), size: 10.5pt)
#set heading(numbering: "1.")
#set par(justify: true)

#let title = sys.inputs.at("title", default: "未命名报告")

#show heading.where(level: 1): it => block(
  fill: luma(240), inset: 8pt, radius: 4pt, width: 100%, it,
)

#align(center)[
  #text(size: 20pt, weight: "bold")[#title]
]

= 概览

本文由数据文件生成，共 #csv("sales.csv").len() 条记录。

#outline(title: [目录], depth: 2)

= 明细

#let rows = csv("sales.csv")
#table(
  columns: 2,
  table.header([地区], [金额]),
  ..rows.flatten(),
  stroke: none,
)

#pagebreak()

= 结论

数据截至编译时刻，金额为含税口径。
```

命令行跑：

```bash
typst compile -i title=2026年Q1销售报告 report.typ report.pdf
typst watch report.typ
```

## 九、容易踩的写法细节

| 想做的事 | 常见错误 | 正确写法 |
|---|---|---|
| 调用函数 | 直接写 `pagebreak()` | 加 `#`：`#pagebreak()` |
| 在标记里插变量 | 写 `count` | 加 `#`：`#count` |
| 数学里的多字母变量 | `$sqrt5$` 被当成一个标识符 | 用函数/括号：`$sqrt(5)$`；或给变量加引号 |
| 传数组当多个参数 | 写成 `#table(nums)` | 展开：`#table(..nums)` |
| 从数据里取数字直接相加 | `rows.at(0).at(1) + 1`（字符串） | 先转换：`int(rows.at(0).at(1)) + 1` |
| 多点号/换行 | 一行太长硬换行 | 用括号包住表达式再换行 |
