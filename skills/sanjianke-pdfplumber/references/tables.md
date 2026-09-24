# 表格提取：策略、参数与调参流程

## 一、算法在做什么

pdfplumber 的表格检测思路（官方说明借鉴了 Anssi Nurminen 的硕士论文，并受 Tabula 启发）分五步：

1. 在页面上找出线——包括**明确画出来的线**，以及**由文字对齐隐含推出的线**。
2. 把重叠或几乎重叠的线合并。
3. 求出所有这些线的交点。
4. 以交点为顶点，找出最细粒度的一组矩形，也就是单元格。
5. 把相邻的单元格归组成表格。

所以「表格提取失败」永远可以归到这条链路的某一环：**线没找到 → 合并过头或不够 → 交点没算出来 → 单元格切碎或粘连**。可视化调试就是为了定位到底断在哪一环。

## 二、两种策略维度

表格识别有**竖向**和**横向**两个独立策略，默认都是 `lines`：

| 策略 | 竖向（`vertical_strategy`） | 横向（`horizontal_strategy`） |
|---|---|---|
| `lines` | 用页面上的图形线条当边界，**矩形的四条边也算线** | 同左 |
| `lines_strict` | 同 `lines`，但**不把矩形的边**算作线 | 同左 |
| `text` | 由词的左边缘、右边缘、中心推出隐含竖线 | 由**词的顶部**推出隐含横线 |
| `explicit` | 只用 `explicit_vertical_lines` 里给的线 | 只用 `explicit_horizontal_lines` 里给的线 |

**两个维度可以混搭**，这是最实用的技巧。真实报表里很常见「只有横线、没有竖线」的样式：

```python
table_settings = {
    "vertical_strategy": "text",     # 竖向靠文字对齐推
    "horizontal_strategy": "lines",  # 横向用实际的横线
}
```

反过来（只有竖线的清单式表格）就反着配。

## 三、`table_settings` 全参数与默认值

```python
{
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "explicit_vertical_lines": [],
    "explicit_horizontal_lines": [],
    "snap_tolerance": 3,
    "snap_x_tolerance": 3,
    "snap_y_tolerance": 3,
    "join_tolerance": 3,
    "join_x_tolerance": 3,
    "join_y_tolerance": 3,
    "edge_min_length": 3,
    "edge_min_length_prefilter": 1,
    "min_words_vertical": 3,
    "min_words_horizontal": 1,
    "intersection_tolerance": 3,
    "intersection_x_tolerance": 3,
    "intersection_y_tolerance": 3,
    "text_tolerance": 3,
    "text_x_tolerance": 3,
    "text_y_tolerance": 3,
    "text_*": ...,   # 见下
}
```

| 参数 | 作用 | 什么时候动它 |
|---|---|---|
| `explicit_vertical_lines` | 明确指定竖向分割线。可以是**数字**（表示一条贯穿整页的 x 坐标线），也可以是 `line` / `rect` / `curve` 对象。可与任何策略组合使用 | `text` 策略也推不出边界时，手工钉死 |
| `explicit_horizontal_lines` | 同上，横向。可以是数字（贯穿整页的 y 坐标线）或对象 | 同上 |
| `snap_tolerance` | 相距在这个容差内的平行线会被「吸附」到同一位置 | 列边界对不齐、同一列被切成两列时**调大** |
| `snap_x_tolerance` / `snap_y_tolerance` | 分轴版本的吸附容差 | 只想调一个方向时用 |
| `join_tolerance` | 在同一条无限直线上、端点距离在容差内的线段会被合并成一条 | 本该连通的线段断成两截时**调大** |
| `join_x_tolerance` / `join_y_tolerance` | 分轴版本 | 同上 |
| `edge_min_length` | 短于这个长度的边会在重建表格前被丢弃 | 识别到一堆碎线造成的假表格时**调大**；细碎的真线被丢掉时**调小** |
| `edge_min_length_prefilter` | 在最初从页面过滤边时就把短于它的丢掉 | 捕获短虚线。默认 1，虚线场景可试 **0.5** |
| `min_words_vertical` | 用 `vertical_strategy: "text"` 时，至少多少个词共享同一对齐才算一条线 | `text` 策略推出太多假竖线时**调大**；真竖线漏了**调小** |
| `min_words_horizontal` | 横向 `text` 策略的同名参数（默认 1） | 同上 |
| `intersection_tolerance` | 组合成单元格时，正交的两条边相距在此容差内才算相交 | 线明明交叉却没形成交点时**调大** |
| `intersection_x_tolerance` / `intersection_y_tolerance` | 分轴版本 | 同上 |
| `text_*` 前缀 | 这些设置**在从每个发现的表格里提文本时**生效。`Page.extract_text()` 的所有参数在这里都可用 | 单元格内文字粘连或断开时，调这里的容差 |
| `text_x_tolerance` / `text_y_tolerance` | 这两个**还额外作用于表格识别本身**——用 `text` 策略时，算法找词会期望同一词内字母间距不超过这两个值 | `text` 策略把词切碎了就调大 |

## 四、调参流程（按这个顺序做，别跳步）

**第 1 步：先看，不要先调。**

```python
import pdfplumber

with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]
    im = page.to_image(resolution=150)
    im.debug_tablefinder()          # 用默认设置
    im.save("step0.png")
```

看 `step0.png` 里：红色的线识别到了哪些？圆圈标记的交点在哪？浅蓝色的表格框是不是你想要的那张？

**第 2 步：裁掉噪音。**

页眉页脚是头号杀手。把页面裁到正文区再重跑第 1 步：

```python
cropped = page.crop((0, 100, page.width, page.height - 80))
cropped.to_image(resolution=150).debug_tablefinder().save("step1.png")
```

坐标单位是 PDF 点（point），原点是**页面左上角**，`top` 向下增大。页面尺寸从 `page.width` / `page.height` 拿。

**第 3 步：如果线根本没识别到，换策略。**

拿到 `page.edges`（等于 `rect_edges` + `curve_edges` + `lines`）看看里面有什么：

```python
print(len(page.lines), len(page.rects), len(page.curves))
print(page.lines[:3])
```

- 页面上**没有线对象**，但视觉上有表格 → 说明是**文字对齐**撑起来的，换 `text` 策略。
- 有 `rects` 但没 `lines` → 表格靠矩形的边构成，默认 `lines` 应该能识别；如果矩形边是干扰项（比如整页一个背景矩形），换 `lines_strict`。
- 线数量少得离谱 → 去调 `edge_min_length_prefilter`（试 0.5）和 `edge_min_length`（调小）。

**第 4 步：结构对但不齐/粘连，调容差。**

到了这一步才动 `snap_*` / `join_*` / `intersection_*`。**一次只改一个参数**，每改一次重新出图：

| debug 图里的症状 | 先试 |
|---|---|
| 同一列边界画了两条几乎重合的红线，单元格被切碎 | `snap_tolerance` 调大 |
| 一条完整的边框由多段短红线拼成，中间断开 | `join_tolerance` 调大 |
| 横竖线交叉处没有圆圈（没识别成交点），单元格连成一片 | `intersection_tolerance` 调大 |
| 出现大量细小碎格（噪点线造成的） | `edge_min_length` 调大 |
| `text` 策略下推出一堆无意义的竖线 | `min_words_vertical` 调大 |

**第 5 步：还不行就手工指定。**

```python
table_settings = {
    "vertical_strategy": "explicit",
    "horizontal_strategy": "explicit",
    "explicit_vertical_lines": [50, 200, 350, 500],      # x 坐标
    "explicit_horizontal_lines": [100, 120, 140, 160],   # y 坐标
}
```

坐标可以直接从 debug 图上读，或者从 `page.lines` / `page.rects` 的 `x0` / `top` 里取。也可以把线对象本身塞进去，比手写数字更稳。

## 五、从 Table 对象拿更多信息

`find_tables()` 返回的是 `Table` 对象，比 `extract_tables()` 的裸二维数组信息多：

```python
with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]
    for table in page.find_tables():
        print("位置:", table.bbox)          # 表格在页面上的边界框
        print("行列:", len(table.rows), len(table.columns))
        print("单元格:", len(table.cells))
        print("内容:", table.extract(x_tolerance=3, y_tolerance=3))
```

想要完整的识别中间产物：

```python
tf = page.debug_tablefinder(table_settings={})
print(tf.edges)          # 用到的所有边
print(tf.intersections)  # 所有交点
print(tf.cells)          # 所有单元格
print(tf.tables)         # 所有表格
```

排查「为什么少了这一列」时，直接看 `tf.edges` 里有没有对应位置的那条线。

## 六、跨页表格

pdfplumber **不自动拼接跨页表格**，每页独立处理。常见做法：

```python
import pdfplumber

all_rows = []
header = None

with pdfplumber.open("long-report.pdf") as pdf:
    for page in pdf.pages:
        rows = page.extract_table()
        if not rows:
            continue
        if header is None:
            header = rows[0]
        # 除首页外，丢掉重复的表头行
        body = rows[1:] if len(rows) > 1 else rows
        all_rows.extend(body)
```

要注意的点：

- 判断「这一页有没有表」不能只看 `rows` 是否为 `None`，还要看行数是否 > 1。
- 有些 PDF 每页都重复表头，有些只在首页有。是否需要 `rows[1:]` 得先抽样看几页。
- 列数可能会漂移（某页少一列）。宁可保留原始二维数组、入库时再对齐，也不要在提取阶段强行补齐。
- 跨页续表的第一行可能是上一页的延续行，需要业务规则判断。

## 七、无框线表格的实战配置

论文、财务报表、政府公文里的表格大多只有横线甚至完全没有线。起点配置：

```python
# 只有横线，没有竖线
table_settings = {
    "vertical_strategy": "text",
    "horizontal_strategy": "lines",
    "min_words_vertical": 2,
    "text_x_tolerance": 3,
}

# 完全没有线，纯靠对齐
table_settings = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "min_words_vertical": 2,
    "min_words_horizontal": 1,
}
```

`text` 策略的固有弱点：**某个单元格内容换行了**，词的对齐位置就可能偏离，导致那条隐含线断掉，整列被切碎。这种情况往往要把 `snap_tolerance` 调大，或者干脆回到 `explicit` 手工指定列坐标——因为这个表格的列位置实际上是固定版面，钉死反而最稳。

## 八、输出格式与下游衔接

`extract_table()` 返回 `list[list[str | None]]`（行 → 单元格），`extract_tables()` 再包一层（表 → 行 → 单元格）。

写 CSV 的最小代码：

```python
import csv
import pdfplumber

with pdfplumber.open("report.pdf") as pdf, \
     open("out.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    for page in pdf.pages:
        for table in page.extract_tables():
            writer.writerows(table)
```

几个实务提醒：

- **单元格可能是 `None`**（空单元格）。直接 `",".join(row)` 会报 `TypeError`，要先 `cell or ""`。
- **单元格内可能含换行符**，写 CSV 没问题，但做列对齐时要先规范化空白。
- **中文 Excel 打开 CSV 乱码**：用 `encoding="utf-8-sig"` 写，带 BOM。
- **数字识别是自己做**。pdfplumber 给的全是字符串，`1,234.56`、`(123)`（会计负数）、`12%` 这些都要你自己写清洗规则。
- 想直接进 pandas，可以 `import pandas as pd; pd.DataFrame(rows[1:], columns=rows[0])`，但表头行的判断要自己做。
