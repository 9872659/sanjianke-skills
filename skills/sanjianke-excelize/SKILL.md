---
name: sanjianke-excelize
slug: sanjianke-excelize
displayName: 三剪客 · Go 操作 Excel
description: "excelize：Go 操作 Excel 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "excelize：Go 操作 Excel 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · Go 操作 Excel

用纯 Go 读写 xlsx 这类电子表格文件，不依赖 Office、不需要装 Excel、也不需要 CGO——丢一个二进制到服务器上就能把数据库里的数据导出成报表，或者把别人上传的表格读进来。它同时提供两套 API：一套是普通读写（打开整个工作簿、按单元格随便改），一套是流式读写（几十万行不进内存，边写边落临时文件）。选哪套、什么时候会踩坑，是这个 Skill 想讲清的事。

**上游项目**：`excelize`　**仓库**：https://github.com/qax-os/excelize

## 什么时候用 / 不用

**用它**：

- 服务端要**生成 Excel 报表**（含样式、合并单元格、图表、数据透视表、条件格式、下拉校验）
- 要**读取用户上传的 xlsx/xlsm**，按工作表、按行列取值，或做批量导入
- 数据量在**几十万行级别**，普通读写会把内存吃爆，需要流式 API
- 需要处理**密码保护的工作簿**（打开时传 `Options{Password: ...}`），或写宏工作簿（XLSM + vbaProject.bin）
- 现有技术栈是 Go，不想为了导表引入 Python/Java 或 LibreOffice

**不要用它**：

- 只想跑一条命令把 xlsx 转 CSV / 转 JSON → 这是库不是命令行程序，写个小 `main.go` 才行
- 处理的是 **.xls（2003 及更早）或 .ods、Google Sheets 导出格式** → 它只认 XLAM / XLSM / XLSX / XLTM / XLTX
- 需要**渲染出和 Excel 一模一样的排版或截图**、要跑宏、要算极其复杂的公式 → 它是文件读写库，不是表格引擎
- 需要的语言不是 Go（Python 用 openpyxl、Java 用 POI 更合适）
- 只想解析文本型表格数据（CSV、TSV）→ 标准库 `encoding/csv` 就够了

## 安装

它是个 Go 库，没有独立安装器，通过 go modules 引：

```bash
# 推荐：go modules
go get github.com/xuri/excelize/v2

# 老式 GOPATH 用法（不推荐）
go get github.com/xuri/excelize
```

最小可运行程序：

```go
package main

import (
	"fmt"

	"github.com/xuri/excelize/v2"
)

func main() {
	f := excelize.NewFile()
	defer func() {
		if err := f.Close(); err != nil {
			fmt.Println(err)
		}
	}()
	f.SetCellValue("Sheet1", "A1", "Hello")
	if err := f.SaveAs("Book1.xlsx"); err != nil {
		fmt.Println(err)
	}
}
```

```bash
go mod init demo && go mod tidy
go run .
```

注意：导入路径是 `github.com/xuri/excelize/v2`（带 `/v2`），**要求 Go 1.25.0 或更高版本**；
具体版本要求随上游变动，以仓库说明与实际构建结果为准。

## 常用操作

**1）新建 + 多个工作表 + 存盘**

```go
f := excelize.NewFile()
defer f.Close()

// NewFile 已经自带一个 Sheet1；要加表就换名字，别重复建 Sheet1
idx, err := f.NewSheet("订单")
if err != nil {
	fmt.Println(err)
	return
}
f.SetCellValue("订单", "A1", "订单号")
f.SetCellValue("订单", "B1", 1024)
f.SetActiveSheet(idx)          // 打开文件时默认显示这张表
if err := f.SaveAs("report.xlsx"); err != nil {
	fmt.Println(err)
}
```

**2）整行写入（注意要传指针）**

```go
row := []interface{}{"2026-01-01", "张三", 128.5, nil, "已付款"}
// SetSheetRow 的第三个参数必须是「指向切片的指针」
if err := f.SetSheetRow("订单", "A2", &row); err != nil {
	fmt.Println(err)
}
// 按列写入同理：f.SetSheetCol("订单", "B6", &[]interface{}{"1", nil, 2})
```

**3）读文件：整表读用 GetRows，大文件用流式迭代器**

```go
f, err := excelize.OpenFile("report.xlsx")
if err != nil {
	fmt.Println(err)
	return
}
defer f.Close()

// 小文件：一次拿到二维数组
rows, err := f.GetRows("订单")
if err != nil {
	fmt.Println(err)
	return
}
for _, row := range rows {
	fmt.Println(row)
}

// 大文件：按行流式读，不把整表塞进内存
r, err := f.Rows("订单")
if err != nil {
	fmt.Println(err)
	return
}
for r.Next() {
	cols, err := r.Columns()
	if err != nil {
		fmt.Println(err)
		break
	}
	fmt.Println(cols)
}
if err := r.Close(); err != nil {   // 释放临时文件
	fmt.Println(err)
}
```

**4）写入大文件：StreamWriter（几十万行不进内存）**

```go
f := excelize.NewFile()
defer f.Close()

sw, err := f.NewStreamWriter("Sheet1")
if err != nil {
	fmt.Println(err)
	return
}
// 列宽/列样式/冻结窗格必须在 SetRow 之前调用
if err := sw.SetColWidth(1, 3, 20); err != nil {
	fmt.Println(err)
}
styleID, _ := f.NewStyle(&excelize.Style{Font: &excelize.Font{Color: "777777"}})
if err := sw.SetRow("A1", []interface{}{
	excelize.Cell{StyleID: styleID, Value: "ID"},
	excelize.Cell{Value: "名称"},
	excelize.Cell{Formula: "SUM(C2:C3)"},
}, excelize.RowOpts{Height: 20}); err != nil {
	fmt.Println(err)
	return
}
for rowID := 2; rowID <= 100000; rowID++ {   // 行号必须递增
	cell, _ := excelize.CoordinatesToCellName(1, rowID)
	if err := sw.SetRow(cell, []interface{}{rowID, "商品", rowID * 2}); err != nil {
		fmt.Println(err)
		break
	}
}
if err := sw.Flush(); err != nil {   // 必须 Flush，否则数据不落盘
	fmt.Println(err)
	return
}
if err := f.SaveAs("big.xlsx"); err != nil {
	fmt.Println(err)
}
```

**5）样式、合并、公式、超链接**

```go
// 样式：先 NewStyle 拿 styleID，再 SetCellStyle 应用到区域
styleID, err := f.NewStyle(&excelize.Style{
	Font:      &excelize.Font{Bold: true, Color: "1265BE"},
	Alignment: &excelize.Alignment{WrapText: true, Horizontal: "center"},
})
if err == nil {
	_ = f.SetCellStyle("订单", "A1", "D1", styleID)
}

_ = f.MergeCell("订单", "A1", "B1")      // 合并 A1:B1
_ = f.SetColWidth("订单", "A", "A", 20)  // 列宽
_ = f.SetRowHeight("订单", 1, 35)        // 行高；传 0 隐藏该行，传 -1 取消自定义行高
_ = f.SetCellFormula("订单", "D2", "SUM(B2:C2)")
v, err := f.CalcCellValue("订单", "D2")  // 库里自己算公式结果
_ = f.SetCellHyperLink("订单", "E2", "https://example.com", "External")
```

**6）表格、图表、图片**

```go
// 建 Excel「表格对象」（带筛选器和样式），表头那行必须是唯一字符串
_ = f.AddTable("订单", &excelize.Table{
	Range: "A1:D10", Name: "Table1", StyleName: "TableStyleMedium2",
})

// 插入图片（gif/jpeg/png 需要按需 import 对应解码器）
_ = f.AddPicture("订单", "F2", "logo.png", &excelize.GraphicOptions{ScaleX: 0.5, ScaleY: 0.5})

// 图表：数据系列用 "Sheet!$B$2:$D$2" 这种引用写法
_ = f.AddChart("订单", "H2", &excelize.Chart{
	Type: excelize.Col3DClustered,
	Series: []excelize.ChartSeries{
		{Name: "订单!$A$2", Categories: "订单!$B$1:$D$1", Values: "订单!$B$2:$D$2"},
	},
})
```

更多方法签名与分组速查见 `references/api-cheatsheet.md`，
流式读写与超大文件的细节见 `references/streaming-and-large-files.md`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `NewSheet("Sheet1")` 报「工作表已存在」 | `NewFile()` 创建的工作簿里**已经有一张 Sheet1** | 要么改用别的名字，要么用 `SetSheetName("Sheet1", "订单")` 改名 |
| 跑完在系统临时目录里堆了一堆 `excelize-*` 文件 | 流式读写和共享字符串表会在超过阈值时落临时文件，只有 `Close()` 才清理 | 每个 `OpenFile`/`NewFile` 都 `defer f.Close()`；流式读还要 `rows.Close()` |
| `SetSheetRow` 报参数错误（ErrParameterInvalid） | 第三个参数必须是**指向切片的指针**，不是切片本身 | 写 `&row` 而不是 `row` |
| 往合并单元格区域写数据，值跑到左上角去了 | 合并区域内只有左上角是真实单元格，写入会被重定向；反过来 `GetCellValue` 对区域内任意单元格返回同一个值 | 记住「合并区只有左上角」这个模型；要分格写就先 `UnmergeCell` |
| 很长的文本写进去被截断 | 单元格内容上限 32767 个字符，超了会静默截断 | 长文本拆多格，或改成附件/文件路径 |
| 写完公式，读回来是空字符串 | 库只写公式不负责计算；读到的是文件里的**缓存值**，程序生成的簿通常没有缓存值 | 读之前用 `CalcCellValue` 自己算，或按官方说明在写公式后调用 `UpdateLinkedValue`，让 Excel 打开时重算 |
| 插入/删除行之后，打开文件提示损坏 | `InsertRows` / `RemoveRow` / `DuplicateRow` 只会**部分**更新公式、图表等引用 | 这类操作后重新核对公式区域；对公式密集的表，宁可按值重建工作簿 |
| 流式写完发现列宽/样式没生效，或报顺序错误 | 流式模式下 `SetColWidth` / `SetColStyle` / `SetColVisible` / `SetPanes` 必须**在第一次 SetRow 之前**调用；行号还必须递增 | 调整调用顺序；不要在流式写同一张表时混用普通模式 API |
| `GetRows` 出来的每行长度不一致 | 行尾连续空白单元格会被跳过 | 自己按最大列数补齐；或改用 `Rows().Columns()` 逐行处理 |
| 读到的日期是 `2024/1/1` 这种字符串，想拿数字拿不到 | 默认会套用单元格的数字格式；这是设计行为 | 传 `excelize.Options{RawCellValue: true}` 拿原始值，再用 `excelize.ExcelDateToTime` 转时间 |
| 构建报 Go 版本太低 | 这个库对 Go 版本要求跟着上游走，比较靠前 | 升级 Go 工具链到仓库 README 要求的版本 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 库本身不联网；只有 `go get` 拉依赖时才需要 |
| 读取文件 | 是 | 打开待处理的 xlsx/xlsm 等文件；插入图片时读取图片文件 |
| 写入文件 | 是 | `SaveAs` / `Save` 写出工作簿；流式模式写系统临时目录 |
| 凭证 | 否 | 打开密码保护的工作簿时，密码是用户输入的业务参数，不由本 Skill 提供或保存 |
| 子进程 / 后台常驻 | 否 | 纯 Go 库，无外部进程；只在调用方自己的服务进程里跑 |

## 触发场景

- 「帮我把数据库查出来的数据导出成带格式的 Excel 报表」
- 「用户上传的 xlsx 要批量导入，按表头对字段」
- 「要生成几十万行的对账单，用 Go 写，不能爆内存」
- 「给导出的表加表头样式、合并单元格、冻结首行、加个合计公式」
- 「这个 xlsx 加了密码，怎么读」
- 「要在 Go 服务里把表格转成 xlsm 并塞宏」

## 能力边界

**覆盖**：

- 读写 XLAM / XLSM / XLSX / XLTM / XLTX（2007 及以后格式），纯 Go、无 CGO
- 单元格级读写：值、公式、富文本、超链接、批注、样式
- 工作表级操作：增删改重命名、复制、移动、分组、隐藏、保护
- 行与列：插入、删除、复制、行高列宽、隐藏、分组（大纲级别 1~7）
- 复杂组件：图表、图片、表格对象、数据透视表、切片器、条件格式、数据验证、迷你图、形状
- 公式计算：自带 `CalcCellValue` 可计算一部分公式
- 流式 API：超大工作表的流式写入与流式读取
- 加密：读写带密码的工作簿、`Encrypt` / `Decrypt`

**不覆盖**：

- .xls（BIFF8）等旧格式，以及 .ods / .csv / Google Sheets 原生格式
- 打开、渲染、打印预览、截图 Excel 的视觉效果（输出的是文件，不是画面）
- 执行 VBA 宏（只能把 vbaProject.bin 塞进 XLSM，由 Excel 去跑）
- 公式的全量计算：`CalcCellValue` 覆盖常见函数，遇到不支持或复杂引用结构要自己处理
- 图表、透视表的可视化编辑，只能按结构化参数生成

## 依赖条件

- Go 工具链，版本要求见仓库 README（当前为 1.25.0 或更高）
- `go get github.com/xuri/excelize/v2`，走 go modules
- 纯 Go 实现，不需要 Office、不需要 CGO、不需要外部服务
- 插图片时按格式 `import _ "image/png"` 之类注册解码器
- 写宏工作簿需要自备 vbaProject.bin

## 已知限制

1. 只支持 OOXML 系列格式，旧版 .xls 读不了
2. 插入/删除行这类结构调整对公式、图表引用的更新只是部分完成，复杂表容易出问题
3. 库不计算也不缓存公式结果，跨程序写入的文件读回来可能没有值
4. 流式模式下普通 API 不可用：混用会报错，且超过阈值落临时文件后无法再读单元格值
5. 超长文本按单元格上限静默截断，不会报错
6. 单元格内容与样式的写入是逐格调用，几十万行的场景必须走 StreamWriter，否则慢且占内存

## 自检清单

**执行前**

- [ ] 确认输入是 OOXML 格式（xlsx/xlsm/xltx/xltm/xlam），不是 .xls 或 .ods
- [ ] 确认 Go 版本满足仓库要求
- [ ] 数据量多大？几万行以内用普通 API，几十万行以上必须 StreamWriter
- [ ] 是否需要保留原文件的公式/图表/透视表？（重写整个文件会丢部件，改局部优先）
- [ ] 打开密码保护文件时，密码从哪来

**执行后**

- [ ] 每个 `NewFile` / `OpenFile` 都有 `defer f.Close()`；流式读有 `rows.Close()`
- [ ] 流式写调了 `Flush()`，并且 `SetRow` 的行号递增
- [ ] 用真实数据打开生成的文件抽查：公式是否有值、合并区是否正确、中文是否乱码
- [ ] 检查系统临时目录没有残留 `excelize-*` 文件
- [ ] 大文件场景记录内存占用，确认没有把整表读进内存

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| `references/api-cheatsheet.md` | 常用方法签名与分组速查 |
| `references/streaming-and-large-files.md` | 流式读写、临时文件与超大表处理 |
| https://github.com/qax-os/excelize | 上游仓库（安装与完整文档以它为准） |

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
