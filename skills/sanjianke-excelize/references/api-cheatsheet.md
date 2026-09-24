# excelize 常用方法速查

签名取自 `github.com/xuri/excelize/v2` 的公开 API（v2 系列）。
`f` 是 `*excelize.File`。少数方法带可选参数（`opts ...Options` / `...RowOpts`），
列在“变参”里说明。**以 `go doc` 和官方文档为最终依据。**

## 打开与保存

| 方法 | 说明 |
|---|---|
| `excelize.NewFile(opts ...Options)` | 新建工作簿，自带一张 `Sheet1` |
| `excelize.OpenFile(filename, opts ...Options)` | 按路径打开 |
| `excelize.OpenReader(r io.Reader, opts ...Options)` | 从 `io.Reader` 打开（HTTP 上传体等） |
| `f.Save(opts ...Options)` | 存回原路径；`NewFile` 出来的没有路径，要用 `SaveAs` |
| `f.SaveAs(name string, opts ...Options)` | 另存为新路径 |
| `f.Write(w io.Writer, opts ...Options)` / `f.WriteTo(w, opts)` | 直接写到流 |
| `f.WriteToBuffer() (*bytes.Buffer, error)` | 写进内存缓冲 |
| `f.Close() error` | **必须调用**，清理临时文件 |

`Options` 字段（打开/读取行为）：`MaxCalcIterations`、`Password`、`RawCellValue`、
`UnzipSizeLimit`（默认 16GB）、`UnzipXMLSizeLimit`（默认 16MB）、`TmpDir`、
`ShortDatePattern`、`LongDatePattern`、`LongTimePattern`、`CultureInfo`。

```go
f, err := excelize.OpenFile("Book1.xlsx", excelize.Options{Password: "password"})
```

## 工作表

`NewSheet(name) (int, error)` / `DeleteSheet(name)` / `SetSheetName(source, target)` /
`GetSheetList() []string` / `GetSheetIndex(name) (int, error)` / `GetSheetName(index)` /
`SetActiveSheet(index)` / `CopySheet(from, to)` / `MoveSheet(source, target)` /
`SetSheetVisible(sheet, visible, veryHidden)` / `SetSheetRow` / `SetSheetCol` /
`GetSheetDimension(sheet)` / `SetSheetDimension(sheet, rangeRef)`

## 单元格读写

| 方法 | 说明 |
|---|---|
| `SetCellValue(sheet, cell, value interface{})` | 支持 int/uint 各宽度、float32/64、string、[]byte、bool、nil、`time.Time`、`time.Duration` |
| `SetCellStr` / `SetCellInt` / `SetCellUint` / `SetCellBool` / `SetCellFloat(sheet, cell, value, precision, bitSize)` | 指定类型写入 |
| `SetCellDefault(sheet, cell, value)` | 按默认格式写、不转义 |
| `GetCellValue(sheet, cell, opts ...Options) (string, error)` | 默认套用数字格式；`Options{RawCellValue: true}` 拿原始值 |
| `GetCellType(sheet, cell) (CellType, error)` | `CellTypeBool/Date/Error/Formula/InlineString/Number/SharedString/Unset` |
| `SetCellFormula(sheet, cell, formula, opts ...FormulaOpts)` | `FormulaOpts{Type, Ref}`，配合 `STCellFormulaTypeArray / Shared / DataTable / Normal` |
| `GetCellFormula(sheet, cell) (string, error)` | 读公式文本，不是计算结果 |
| `CalcCellValue(sheet, cell, opts ...Options) (string, error)` | 在库里算公式 |
| `SetCellRichText(sheet, cell, runs []RichTextRun)` / `GetCellRichText` | 富文本 |
| `SetCellHyperLink(sheet, cell, link, linkType, opts ...HyperlinkOpts)` | `linkType` 为 `External` / `Location` / `None`；`HyperlinkOpts{Display, Tooltip}` |
| `SetSheetRow(sheet, cell, slice interface{})` | **必须传切片指针**，如 `&[]interface{}{...}` |
| `SetSheetCol(sheet, cell, slice interface{})` | 同上，按列写 |
| `GetRows(sheet, opts ...Options) ([][]string, error)` | 整表读；行尾空白被裁掉 |
| `GetCols(sheet, opts ...Options) ([][]string, error)` | 按列读 |
| `SearchSheet(sheet, value string, reg bool) ([]string, error)` | 查值所在单元格 |
| `MergeCell(sheet, topLeftCell, bottomRightCell)` / `UnmergeCell` | 合并/取消合并 |
| `AddComment(sheet, opts *Comment)` / `GetComments(sheet)` | 批注 |

## 行列与尺寸

`SetColWidth(sheet, startCol, endCol, width)` / `GetColWidth` / `SetRowHeight(sheet, row, height)`
（`height` 为 0 隐藏该行，-1 取消自定义行高）/ `GetRowHeight` /
`SetRowVisible` / `SetColVisible` / `SetRowStyle(sheet, start, end, styleID)` /
`SetColStyle(sheet, columns, styleID)` / `SetRowOutlineLevel(sheet, row, level)`（1~7）/
`InsertRows(sheet, row, n)` / `RemoveRow(sheet, row)` / `InsertCols` / `RemoveCol` /
`DuplicateRow(sheet, row)` / `DuplicateRowTo(sheet, row, row2)` /
`AutoFilter(sheet, rangeRef, opts ...AutoFilterOptions)` / `AutoFitColWidth(sheet, columns)`

> `InsertRows` / `RemoveRow` / `DuplicateRow` 会牵动公式与图表引用，官方文档明确提示
> “请谨慎使用”，引用更新只是部分完成。

## 样式

```go
styleID, err := f.NewStyle(&excelize.Style{
    Font:      &excelize.Font{Bold: true, Color: "2354E8", Size: 12},
    Fill:      excelize.Fill{Type: "pattern", Pattern: 1, Color: []string{"FFFF00"}},
    Border:    []excelize.Border{{Type: "left", Color: "000000", Style: 1}},
    Alignment: &excelize.Alignment{Horizontal: "center", WrapText: true},
    NumFmt:    22,   // 内置数字格式编号
})
_ = f.SetCellStyle("Sheet1", "A1", "D1", styleID)
```

配套：`GetStyle(idx)` / `GetCellStyle(sheet, cell)` / `NewConditionalStyle` +
`SetConditionalFormat(sheet, rangeRef, opts)`。

## 复杂组件

| 方法 | 说明 |
|---|---|
| `AddChart(sheet, cell, chart *Chart, combo ...*Chart)` | 图表，`ChartSeries` 用 `"Sheet!$B$2:$D$2"` 引用 |
| `AddChartSheet(sheet, chart, combo...)` | 整张图表工作表 |
| `AddTable(sheet, table *Table)` | 表格对象，`Table{Range, Name, StyleName, ...}` |
| `AddPicture(sheet, cell, name, opts *GraphicOptions)` | 图片；`AddPictureFromBytes` 走内存字节 |
| `AddPivotTable(opts *PivotTableOptions)` | 数据透视表 |
| `AddSlicer(sheet, opts *SlicerOptions)` | 切片器 |
| `AddSparkline(sheet, opts *SparklineOptions)` | 迷你图 |
| `AddDataValidation(sheet, dv *DataValidation)` | 下拉/校验规则；`NewDataValidation` + `SetDropList` / `SetRange` |
| `AddVBAProject(file []byte)` | 塞入 `vbaProject.bin`，文件须为 XLSM/XLTM |
| `ProtectSheet(sheet, opts *SheetProtectionOptions)` / `ProtectWorkbook` | 保护 |
| `UpdateLinkedValue()` | 清掉公式的旧缓存值，让 Excel 打开时重算 |

## 工具函数

`CoordinatesToCellName(col, row int, abs ...bool) (string, error)`、
`CellNameToCoordinates(cell) (int, int, error)`、
`ColumnNumberToName(num) (string, error)`、`ColumnNameToNumber(name) (int, error)`、
`SplitCellName(cell) (string, int, error)`、`JoinCellName(col, row)`、
`ExcelDateToTime(excelDate float64, use1904Format bool) (time.Time, error)`、
`Encrypt(raw []byte, opts *Options) ([]byte, error)`、`Decrypt(raw, opts)`、
`RGBToHSL` / `HSLToRGB` / `ThemeColor`。
