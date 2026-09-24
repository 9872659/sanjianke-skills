# 流式读写与超大文件

excelize 有两套 API。普通 API 把工作簿读进内存、可以随便改；流式 API 只做「顺序写」
或「顺序读」，换来的是几十万行也不爆内存。**同一张工作表上两套不能混用。**

## 什么时候必须换流式

- 写：要生成几万行以上、或列数很多（几百列）的报表
- 读：要处理的 xlsx 打开就吃掉几个 GB 内存
- 判断依据：普通模式下每个单元格都是一个结构体，10 万行 × 50 列就是 500 万个对象

## 流式写：StreamWriter

```go
f := excelize.NewFile()
defer f.Close()

sw, err := f.NewStreamWriter("Sheet1")
if err != nil {
    return
}

// 1) 列的设置必须在第一次 SetRow 之前
sw.SetColWidth(1, 1, 12)
sw.SetColStyle(2, 3, styleID)
sw.SetColVisible(4, 4, false)
sw.SetPanes(&excelize.Panes{Freeze: true, Split: false, YSplit: 1, TopLeftCell: "A2", ActivePane: "bottomLeft"})

// 2) 逐行写，行号必须递增
for rowID := 1; rowID <= 200000; rowID++ {
    cell, _ := excelize.CoordinatesToCellName(1, rowID)
    row := []interface{}{rowID, "商品", rowID * 2}
    if err := sw.SetRow(cell, row, excelize.RowOpts{Height: 20}); err != nil {
        return
    }
}

// 3) 表格对象要在写完行之后、Flush 之前加；一个 StreamWriter 只允许一个表
sw.AddTable(&excelize.Table{Range: "A1:C200000", Name: "Table1", StyleName: "TableStyleMedium2"})

// 4) 必须 Flush
if err := sw.Flush(); err != nil {
    return
}
f.SaveAs("big.xlsx")
```

要点：

- **顺序**：`SetColWidth` / `SetColStyle` / `SetColVisible` / `SetColOutlineLevel` /
  `SetPanes` 必须在第一次 `SetRow` 之前，否则返回顺序错误。
- **行号递增**：`SetRow` 的行号小于等于已写行号会直接报错。
- **单元格粒度的样式**：把 `excelize.Cell{Value: ..., StyleID: id, Formula: "SUM(A1,B1)"}`
  放进行切片里，或用 `*excelize.Cell`。
- **富文本**：该列的值可以直接放 `[]excelize.RichTextRun`。
- **行属性**：`excelize.RowOpts{Height, Hidden, StyleID, OutlineLevel}`。
- **合并单元格**：`sw.MergeCell(topLeft, bottomRight)`；不要与已有合并区重叠。
- **落盘**：`Flush()` 之前数据都在缓冲里；不 Flush 等于白写。

## 流式读：Rows 迭代器

```go
f, err := excelize.OpenFile("big.xlsx")
if err != nil {
    return
}
defer f.Close()

rows, err := f.Rows("Sheet1")
if err != nil {
    return
}
for rows.Next() {
    cols, err := rows.Columns()          // 可传 excelize.Options{RawCellValue: true}
    if err != nil {
        break
    }
    // 处理一行
    _ = cols
}
if err := rows.Error(); err != nil {     // 迭代中途的错误在这里
    return
}
if err := rows.Close(); err != nil {     // 关闭临时文件
    return
}
```

- `Rows.Next()` 前进到下一行，`Rows.Columns()` 拿当前行的单元格字符串。
- `Rows.GetRowOpts()` 能拿到当前行的行属性（高度、隐藏、样式 ID）。
- `Rows.Close()` **必须**调用：工作表的 XML 若超过阈值会被解压到系统临时目录，
  不关就一直留在磁盘上。
- `GetRows()` 本质就是把迭代器走完收集成二维数组，所以它不适合超大表。

## 临时文件与内存阈值

- `Options.UnzipXMLSizeLimit` 默认 **16MB**：打开文件时，工作表 XML 和共享字符串表
  超过这个值就解压到系统临时目录，不再常驻内存。这也是为什么 `Close()` 不能省。
- `Options.UnzipSizeLimit` 默认 **16GB**，是解压总大小的上限，必须 ≥ `UnzipXMLSizeLimit`。
- 想换临时目录：`Options{TmpDir: "/data/tmp"}`（流式写的缓冲落盘也走这个目录）。
- 流式写的内存缓冲超过阈值后同样落临时文件，此时**不能再读取单元格值**。
- 清场检查：跑完任务后看系统临时目录里有没有残留 `excelize-*` 文件；
  有就说明某处漏了 `Close()`。

## 内存之外的性能开关

- 样式的复用：`NewStyle` 会去重，但反复创建相同的样式仍然有开销，循环外建一次。
- 共享字符串表：写字符串会进共享字符串表，重复文本越多越省；如果都是唯一长文本，
  考虑改写成数值或缩短内容。
- 先建样式、再批量写值，避免逐格 `SetCellStyle`。
- 只读场景不需要样式时，考虑把源文件先转成 CSV 再处理，往往比解析 xlsx 快得多。
