# surya 输出结构（results.json）

所有命令都会在输出目录写一个 `results.json`（或同名结果文件），
**顶层是以输入文件名（去掉扩展名）为 key 的字典**，value 是「每页一个 dict」的列表。
下面的字段按 Surya 2 的 README 整理；实际以运行版本为准。

## surya_ocr

每一页：

| 字段 | 含义 |
|---|---|
| `blocks` | 按阅读顺序排列的块 |
| `image_bbox` | `[0, 0, width, height]` |

每个 block：

| 字段 | 含义 |
|---|---|
| `label` | 归一化后的版面标签，如 `Text`、`SectionHeader`、`Table`、`Equation`、`Picture`、`Form`、`PageHeader` |
| `raw_label` | 模型原始输出、归一化之前的标签 |
| `reading_order` | 在版面输出中的 0 起始位置 |
| `html` | 块内容 HTML。公式包在 `<math>...</math>` 里，表格是 `<table>...</table>`。块被跳过的场合是 `""` |
| `polygon` | 四角多边形，顺序 `[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]` |
| `bbox` | 由 polygon 推出的轴对齐 `[x0, y0, x1, y1]` |
| `confidence` | 该块解码的平均 token 概率（0~1） |
| `skipped` | true 表示这是视觉类标签（如 Picture）没有做 OCR |
| `error` | true 表示这个块的 OCR 调用失败 |

完整标签集合见 `surya/layout/label.py` 里的 `LAYOUT_PRED_RELABEL`。

## surya_detect

每一页：

| 字段 | 含义 |
|---|---|
| `bboxes` | 文字行，每项含 `bbox`（`x1,y1,x2,y2`）、`polygon`（四角，从左上起顺时针）、`confidence` |
| `vertical_lines` | 检出的竖线，含 `bbox` |
| `page` | 页码 |
| `image_bbox` | 该页图像范围，所有行 bbox 都在它内部 |

## surya_layout

每一页：

| 字段 | 含义 |
|---|---|
| `bboxes` | 按阅读顺序的版面框 |
| `image_bbox` | `[0, 0, width, height]` |
| `raw` | 布局模型吐的原始 JSON，排错用 |
| `error` | 布局调用失败时为 true |

每个版面框：

| 字段 | 含义 |
|---|---|
| `polygon` / `bbox` | 同上 |
| `label` | 归一化标签，取值包括 `Caption`、`Footnote`、`Equation`、`ListGroup`、`PageHeader`、`PageFooter`、`Picture`、`SectionHeader`、`Table`、`Text`、`Figure`、`Code`、`Form`、`TableOfContents`、`ChemicalBlock`、`Diagram`、`Bibliography`、`BlankPage` |
| `raw_label` | 归一化之前的标签 |
| `position` | 0 起始阅读顺序 |
| `count` | 模型对该块 OCR 的 token 估算（按 50 取整），用来定这块的解码预算 |
| `confidence` | 版面解码的平均 token 概率 |

## surya_table

每一页 value 是「每个表格一个 dict」：

| 字段 | 含义 |
|---|---|
| `rows` | 按阅读顺序的行，含 `polygon` / `bbox`、`row_id`（0 起始） |
| `cols` | 列，含 `polygon` / `bbox`、`col_id` |
| `cells` | 行列交点的单元格（simple 模式），含几何与 `row_id` / `col_id` / `cell_id` |
| `html` | 完整 `<table>` HTML，**只在 full 模式下有值**（能处理跨行跨列与表头），simple 模式为 `null` |
| `mode` | `"simple"` 或 `"full"` |
| `image_bbox` | 表格裁切区域的 bbox |
| `error` | 表格调用失败时为 true |
| `raw` | 原始模型输出，排错用 |

## 读结果时的常见误判

- 拿到 `html: ""` 不一定是失败，可能是该块被 `skipped`（视觉类标签）
- `confidence` 低不等于文字错，版面块的置信度是解码平均概率，长块天然偏低
- 表格 simple 模式**没有** `is_header` / `colspan` / `rowspan`（v2 已移除），
  要这些信息就走 full 模式或下游转换工具
- 顶层 key 是去掉扩展名的文件名，同一批里若有两个同名不同扩展名的输入会互相覆盖
