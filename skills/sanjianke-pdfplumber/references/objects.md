# 对象、坐标系与文本提取

## 一、坐标系

pdfplumber 里所有对象的位置都用 PDF 点（point）表示，1 点 = 1/72 英寸。**关键：原点在页面左上角，`top` 向下增大**——这跟 PDF 规范内部的坐标系（原点在左下角）是反的，pdfplumber 已经替你转好了。

| 字段 | 含义 |
|---|---|
| `x0` / `x1` | 左边界 / 右边界到页面左边的距离 |
| `y0` / `y1` | 下边界 / 上边界到页面**底边**的距离（保留 PDF 原生的自下而上口径） |
| `top` | 上边界到页面**顶边**的距离 |
| `bottom` | 下边界到页面**顶边**的距离 |
| `doctop` | 上边界到**整份文档顶部**的距离（跨页累计） |

实际写代码时：

- **判断上下位置用 `top`**（越小越靠上），比 `y0` / `y1` 直观。
- **判断跨页的纵向位置用 `doctop`**，它是文档级累计坐标，能把多页摊平成一条纵轴。
- `top` / `bottom` / `doctop` 三者是同一套口径（从上往下），`y0` / `y1` 是另一套（从下往上）。**不要混用**。

页面尺寸：

```python
page.width    # 页宽
page.height   # 页高
```

`crop()` 等方法的 `bounding_box` 统一是 `(x0, top, x1, bottom)` 四元组——注意第二、四个元素是 `top` 系口径，不是 `y0` 系。

## 二、对象类型总览

`PDF` 与 `Page` 都提供这些列表属性：

| 属性 | 每个元素代表 |
|---|---|
| `.chars` | 单个文本字符 |
| `.lines` | 一条一维线 |
| `.rects` | 一个二维矩形 |
| `.curves` | 一连串相连的点，pdfminer 没识别成线或矩形 |
| `.images` | 一张图片 |
| `.annots` | 一条 PDF 批注 |
| `.hyperlinks` | 一条 `Link` 子类型且有 `URI` 动作的批注 |

派生列表：

| 属性 | 含义 |
|---|---|
| `.rect_edges` | 把每个矩形拆成它的四条边 |
| `.curve_edges` | 对曲线做同样处理 |
| `.edges` | `rect_edges` + `curve_edges` + `lines` 的合集——**表格识别用的就是这个** |

所有对象都是普通 Python `dict`，用 `obj["x0"]` 这样取值。

## 三、`char` 属性表

| 属性 | 说明 |
|---|---|
| `page_number` | 所在页码 |
| `text` | 字符本身，如 `"z"`、`"Z"`、`" "` |
| `fontname` | 字体名 |
| `size` | 字号 |
| `adv` | 等于文本宽度 × 字号 × 缩放因子 |
| `upright` | 是否正立（**判断斜排文字的关键**） |
| `height` / `width` | 字符的高 / 宽 |
| `x0` / `x1` | 左右边界 |
| `y0` / `y1` | 上下边界（自下而上口径） |
| `top` / `bottom` | 上下边界（自上而下口径） |
| `doctop` | 到文档顶部的距离 |
| `matrix` | 当前变换矩阵（CTM），控制缩放、倾斜、平移 |
| `mcid` | 所属标记内容段的 ID，无则 `None`（**实验性**） |
| `tag` | 所属标记内容段的标签，无则 `None`（**实验性**） |
| `stroking_color` | 描边（轮廓）颜色 |
| `non_stroking_color` | 填充（内部）颜色 |
| `ncs` / `stroking_pattern` / `non_stroking_pattern` | 官方文档里标注为 **TKTK**（待补），不要依赖 |
| `object_type` | `"char"` |

### 用矩阵算旋转角

```python
from pdfplumber.ctm import CTM

my_char = pdf.pages[0].chars[3]
my_char_ctm = CTM(*my_char["matrix"])
print(my_char_ctm.skew_x)
```

`matrix` 定义见 PDF 规范（第 6 版）4.2.2 节。矩阵控制字符的缩放、倾斜与位置平移；旋转是缩放与倾斜的组合，多数情况下可视为等于 x 轴倾斜。

**但更简单是先看 `upright`**：`False` 就说明这个字符不是正立的，多半是旋转页或水印。用 `extract_words()` 时它内部会分别处理正立与非正立字符。

## 四、`line` / `rect` / `curve` 属性

### `line`

`page_number`、`height`、`width`、`x0`、`x1`、`y0`、`y1`、`top`、`bottom`、`doctop`、`linewidth`（线宽）、`stroking_color`、`non_stroking_color`、`mcid`、`tag`、`object_type`（`"line"`）。

**没有 `pts`**——`line` 就是两个端点构成的线段，靠 `x0`/`x1`/`top`/`bottom` 表达。

### `rect`

与 `line` 基本一致，多一个 `linewidth`，且 `stroking_color` 是边框色、`non_stroking_color` 是**填充色**。

一份 PDF 里如果有一个覆盖整页的白色背景矩形，它会在 `rect_edges` 里产生 4 条贯穿页面的边，这会**严重干扰表格识别**。这就是 `lines_strict` 策略存在的理由——它不把矩形的边当作表格线。

### `curve`

比 `line` / `rect` 丰富得多：

| 属性 | 说明 |
|---|---|
| `pts` | 曲线**上的点**列表，元素是 `(x, top)` 元组 |
| `path` | **完整路径描述**，元素是 `(cmd, *(x, top))` 元组，包含贝塞尔曲线的控制点 |
| `fill` | 该路径围成的形状是否被填充 |
| `dash` | 虚线样式，`([dash_array], dash_phase)` 元组 |
| 其余 | `height` / `width` / `x0` / `x1` / `y0` / `y1` / `top` / `bottom` / `doctop` / `linewidth` / 颜色 / `mcid` / `tag` |

`pts` 是「点在曲线上」，`path` 是「怎么画出这条曲线」。要做几何分析（判断这是个圆还是圆角矩形）用 `pts`；要重绘用 `path`。

## 五、`image` 属性

| 属性 | 说明 |
|---|---|
| `page_number` | 所在页码 |
| `height` / `width` | 在页面上的显示尺寸 |
| `x0` / `x1` / `y0` / `y1` / `top` / `bottom` / `doctop` | 位置 |
| `srcsize` | 图片**原始**像素尺寸，`(width, height)` 元组 |
| `colorspace` | 色彩空间，如 RGB |
| `bits` | 每个颜色分量的位数（8 对应 0–255） |
| `stream` | 像素值，是 `pdfminer.pdftypes.PDFStream` 对象 |
| `imagemask` | 可空布尔。为 `True` 表示该图数据用作模板蒙版 |
| `name` | 该图片 XObject 在资源字典里的引用名 |
| `mcid` / `tag` | 实验性 |
| `object_type` | `"image"` |

**重要限制**：pdfplumber **不提供重建图片内容的方法**。`images` 只给位置与格式元信息。要导出图片请换 PyMuPDF（`page.get_images()` + `Pixmap`）或类似的库。

## 六、文本提取方法

### `extract_text(...)`

```python
page.extract_text(
    x_tolerance=3, y_tolerance=3,
    layout=False, x_density=7.25, y_density=13,
    x_tolerance_ratio=None,
    line_dir_render=None, char_dir_render=None,
    **kwargs,
)
```

- `layout=False`（默认）：把所有字符拼成一个字符串。当**前一个字符的 `x1` 与后一个字符的 `x0` 之差大于 `x_tolerance`** 时插入空格；当**前后字符的 `doctop` 之差大于 `y_tolerance`** 时插入换行。
- `layout=True`（**实验性**）：尝试模仿页面上的版面结构，用 `x_density` / `y_density` 决定每「点」（PDF 度量单位）最少几个字符 / 换行。传 `line_dir_render` / `char_dir_render`（取值 `ttb` / `btt` / `ltr` / `rtl`）可以改变输出方向。所有多出来的 `**kwargs` 会传给 `extract_words()`——它是布局计算的第一步。

`x_tolerance_ratio` 不为 `None` 时，改用**动态容差**：等于 `x_tolerance_ratio × 前一个字符的 size`。这比固定容差更能适应同一页里的字号变化。

### `extract_text_simple(x_tolerance=3, y_tolerance=3)`

逻辑更简单的快速版。要速度又不在乎细节时用。

### `extract_words(...)`

返回所有「像词的东西」及其边界框。判定标准：正立字符之间，**前一个的 `x1` 与后一个的 `x0` 之差 ≤ `x_tolerance`**，且 **`doctop` 之差 ≤ `y_tolerance`**。非正立字符用类似思路，但量的是**纵向**距离。斜排文字的 `line_dir` / `char_dir`（正立）与 `line_dir_rotated` / `char_dir_rotated`（旋转）分别控制两个方向。

常用参数：

| 参数 | 作用 |
|---|---|
| `keep_blank_chars=True` | 把空白字符当作词的一部分，而不是词间分隔 |
| `use_text_flow=True` | 按 PDF **内部字符流顺序**排序与切词，而不是按 x/y 预排序。行为类似在 PDF 里拖选高亮——**顺序不一定符合阅读逻辑** |
| `extra_attrs=["fontname","size"]` | 限制每个词内的字符必须在这几个属性上完全一致（如 `["fontname","size"]`），返回的词字典里也会带上这些属性 |
| `split_at_punctuation=True` | 在标点处强制断词（标点集合取自 `string.punctuation`）；也可以传字符串自定义集合 |
| `expand_ligatures=False` | 关掉连字展开。默认 `True`，会把 `ﬁ` 这类连字展开成 `fi` |
| `return_chars=True` | 在每个词字典里加一个 `chars` 字段，列出组成它的字符 |

### `extract_text_lines(...)`（实验性）

```python
page.extract_text_lines(layout=False, strip=True, return_chars=True, **kwargs)
```

返回表示页面上文本行的字典列表。`strip` 的作用类似 Python 的 `str.strip()`（仅在 `layout=True` 时相关，用来去掉 `text` 属性前后的空白）。`return_chars=False` 则不返回组成该行的字符对象。其余 `**kwargs` 就是给 `extract_text(layout=True, ...)` 的那些。

### `search(...)`（实验性）

```python
page.search(pattern, regex=True, case=True, main_group=0,
            return_groups=True, return_chars=True, layout=False, **kwargs)
```

在页面文本里搜索，返回所有匹配。每个匹配的字典含匹配文本、正则分组、边界框坐标，以及字符对象本身。

- `pattern` 可以是已编译的正则、未编译的正则字符串，或普通字符串。
- `regex=False` 时按普通字符串处理。
- `case=False` 时忽略大小写。
- `main_group` 把结果限定到正则的某个分组（默认 `0` 表示整个匹配）。
- `return_groups=False` / `return_chars=False` 分别不返回 `groups` / `chars` 字段。
- **零宽匹配和全空白匹配会被丢弃**，因为它们在页面上没有明确位置。

### `dedupe_chars(tolerance=1, extra_attrs=("fontname","size"))`

返回一个把重复字符删掉的新页面。重复的判定标准：**文本相同、位置在 `tolerance` 容差内、且 `extra_attrs` 指定的属性也相同**。

用途：PDF 为了做出伪粗体效果，会把同一字符画两三层，导致提取结果里每个字出现两遍。

## 七、版面操作

| 方法 | 保留规则 | 备注 |
|---|---|---|
| `crop(bbox, relative=False, strict=True)` | 保留**至少有一部分**落在框内的对象；跨界的对象会被切齐到框边 | |
| `within_bbox(bbox, relative=False, strict=True)` | 只保留**完全在**框内的对象 | |
| `outside_bbox(bbox, relative=False, strict=True)` | 只保留**完全在**框外的对象 | |
| `filter(test_function)` | 只保留 `test_function(obj)` 返回 `True` 的对象 | 改动**不会**反映在 `to_image()` 里 |

- `bbox` 是 `(x0, top, x1, bottom)` 四元组。
- `relative=True` 时，框按页面左上角的偏移量算，而不是绝对坐标。
- `strict=True`（默认）要求框**必须完全落在页面范围内**，否则报错。跨页计算出来的框容易踩这个。

### 内存管理

`Page` 对象默认**缓存**布局与对象信息，避免重复解析。大 PDF 上这些缓存很占内存。用完一页就：

```python
page.close()      # 刷新该页缓存
```

`PDF.close()` 会对每页调 `Page.close()`，并关闭文件流（除非流是外部传入的、已经打开的）。

## 八、可视化

```python
im = page.to_image(resolution=150)     # 默认 72 DPI
```

`to_image()` 可以只传以下**其中之一**：`resolution`（每英寸像素数，默认 72）、`width`、`height`；另有 `antialias`（默认 `False`，开了字更平滑但文件更大）、`force_mediabox`（用页面 `mediabox` 尺寸而不是 `cropbox`，默认 `False`）。

在 REPL 里 `im.show()` 会打开本地图片查看器；在 Jupyter 里 `PageImage` 会自动渲染为单元格输出。

`PageImage` 方法：

| 方法 | 说明 |
|---|---|
| `im.reset()` | 清掉已画的所有内容 |
| `im.copy()` | 复制成一个新的 `PageImage` |
| `im.show()` | 用本地查看器打开 |
| `im.save(path, format="PNG", quantize=True, colors=256, bits=8)` | 存成 PNG。默认量化到 256 色调色板、8 位色深；`quantize=False` 关掉量化，`colors=N` 调色板大小 |

绘制方法（单对象 / 批量两版）：

| 单个 | 批量 | 说明 |
|---|---|---|
| `draw_line(line, stroke=…, stroke_width=1)` | `draw_lines(list, **kw)` | 从 `line` / `curve` 或二重二元组 `((x,y),(x,y))` 画线 |
| `draw_vline(location, …)` | `draw_vlines(list, **kw)` | 在给定 x 坐标画竖线 |
| `draw_hline(location, …)` | `draw_hlines(list, **kw)` | 在给定 y 坐标画横线 |
| `draw_rect(bbox_or_obj, fill=…, stroke=…, …)` | `draw_rects(list, **kw)` | 从 `rect` / `char` 等对象或四元组画矩形 |
| `draw_circle(center_or_obj, radius=5, …)` | `draw_circles(list, **kw)` | 在坐标或某对象中心画圆 |

参数命名对齐 SVG 的 `fill` / `stroke` / `stroke_width`，但底层是 Pillow 的 `ImageDraw`。

`im.debug_tablefinder(table_settings={})` 返回叠加了识别结果的版本：**线为红色、交点为圆圈、表格为浅蓝色**。

**注意**：`to_image()` 能正确反映 `crop()` / `CroppedPage` 的结果，但**无法体现 `filter()` / `FilteredPage` 做的改动**。

## 九、加载参数

```python
pdfplumber.open(
    path_or_file,
    password=None,
    laparams=None,
    unicode_norm=None,
    strict_metadata=False,
    **kwargs,
)
```

| 参数 | 说明 |
|---|---|
| `password` | 打开有密码保护的 PDF |
| `laparams` | 传给 `pdfminer.six` 版面引擎的参数字典，如 `{"line_overlap": 0.7}`、`{"detect_vertical": True}`。传了之后每页的 `.objects` 字典里会多出 pdfminer 的高层版面对象（如 `"textboxhorizontal"`） |
| `unicode_norm` | 预归一化 Unicode 文本。取值 `"NFC"` / `"NFD"` / `"NFKC"` / `"NFKD"`（Unicode 标准附件 15 的四种形式） |
| `strict_metadata` | 默认非法元数据只**警告**；设为 `True` 则解析失败时直接抛异常 |

`open()` 返回 `pdfplumber.PDF`，有两个主属性：`.metadata`（来自 PDF `Info` 尾部的键值对，通常含 `CreationDate`、`ModDate`、`Producer` 等）与 `.pages`。

**推荐用 `with` 语句**，确保文件流被关闭。

## 十、读表单字段

pdfplumber **没有现成的表单接口**，但可以借它的 `pdfminer` 包装自己解析 AcroForm：

```python
import pdfplumber
from pdfplumber.utils.pdfinternals import resolve_and_decode, resolve

pdf = pdfplumber.open("document_with_form.pdf")

def parse_field_helper(form_data, field, prefix=None):
    resolved_field = field.resolve()
    field_name = '.'.join(filter(lambda x: x, [prefix,
                          resolve_and_decode(resolved_field.get("T"))]))
    if "Kids" in resolved_field:
        for kid_field in resolved_field["Kids"]:
            parse_field_helper(form_data, kid_field, prefix=field_name)
    if "T" in resolved_field or "TU" in resolved_field:
        # "T" 是字段名，但有时缺失
        # "TU" 是备用字段名，通常更可读
        alternate = resolve_and_decode(resolved_field.get("TU")) \
            if resolved_field.get("TU") else None
        value = resolve_and_decode(resolved_field["V"]) \
            if "V" in resolved_field else None
        form_data.append([field_name, alternate, value])

form_data = []
fields = resolve(resolve(pdf.doc.catalog["AcroForm"])["Fields"])
for field in fields:
    parse_field_helper(form_data, field)
```

`form_data` 的每个元素是三元素列表：`[字段名, 备用字段名, 字段值]`。

这条路依赖 `pdfplumber.utils.pdfinternals` 的内部实现，**跨版本可能变动**。要稳定读写表单，PyMuPDF 的 `page.widgets()` 更直接。
