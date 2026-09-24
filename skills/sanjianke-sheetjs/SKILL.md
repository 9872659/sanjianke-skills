---
name: sanjianke-sheetjs
slug: sanjianke-sheetjs
displayName: 三剪客 · 电子表格读写
description: "SheetJS：电子表格读写 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "SheetJS：电子表格读写 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · 电子表格读写

手上有一堆 `xlsx` / `xls` / `csv` / `ods`，要批量抽数据、清洗、再生成一张新表交出去——这件事不需要 Office，也不需要 Python。SheetJS 是一个纯 JavaScript 的电子表格读写库，同一套 API 在 Node 脚本、浏览器页面、Deno/Bun 里都能跑，读进来的是普通对象，写出去的是标准文件。

它的定位很明确：**在代码里把表格当数据结构处理**。凡是「读表格 → 拿数据 → 或生成新表格」的任务，它是首选；凡是「保留原表样式、图表、公式结果」的任务，它不合适——那部分在社区版里不做。

**上游项目**：`SheetJS`　**仓库**：https://github.com/SheetJS/sheetjs

## 什么时候用 / 不用

**用它**：

- 「把这个目录下所有 xlsx 的第 2 个 sheet 汇总成一张表」——批量读取 + 汇总导出。
- 「CSV 转 xlsx / xlsx 转 CSV / xls 转 xlsx」——纯格式搬运，不碰样式。
- 「从接口下载的表格里抽出需要的列，导出成新的 Excel 给客户」——服务端无人值守跑脚本。
- 「网页上让用户上传表格、解析后直接渲染成表格/图表」——浏览器端全前端解析，文件不离开用户电脑。
- 「把数据库查询结果导成 xlsx 附件发邮件」——内存里组表，直接写 Buffer。
- 「要读 2007 年前的老 xls、Lotus、DBF、Numbers 文件」——它支持的遗留格式比大多数库都全。

**不要用它**：

- **要保留或生成样式**（字体、颜色、条件格式、图表、图片、数据透视表）——社区版明确不做，只有商业版覆盖。这种情况宁可让用户在原表上手工操作，或改用 Python 侧的 openpyxl/xlsxwriter 一类方案。
- **要计算公式结果**——它只保存公式文本，不做求值；需要值就用 Excel 或带计算引擎的表格库。
- **要处理加密的 xlsx/xlsb**——社区版只支持 XLS 的 XOR 加密，AES 加密的文件会直接抛错。
- **输入不是表格**：PDF 表格、扫描件、图片里的表格——这是 OCR 的活，不在它范围内。
- **要做多人协作/在线编辑、与 Excel 的宏（VBA）联动**——它不做宿主环境。
- **超大文件（几十万行以上）的流式 ETL**——它能读，但整本 workbook 在内存里，内存吃紧时不如直接用数据库或专用流式方案。

## 安装

**Node 项目（官方推荐路径）**。注意：公开 npm registry 上的 `xlsx` 停在 0.18.5，已经过时；官方 CDN `https://cdn.sheetjs.com` 才是权威来源。安装时把 tarball 地址交给包管理器：

```bash
# npm：直接装官方 CDN 的 tarball（文档当前版本 0.20.3）
npm i --save https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz

# yarn：先卸掉可能从 npm 装进来的旧版，再装 tarball
yarn remove xlsx
yarn add https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz
```

新版 Yarn 会抱怨直接给 URL，按它的提示把包名前缀带上：

```bash
yarn add xlsx@https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz
```

npm 与 pnpm 的等价写法在同一份安装文档里，同样是「把 URL 交给包管理器」；以你所用包管理器的实际报错提示为准。

**推荐做法：把 tarball 落到仓库里（vendoring）**，避免以后 CDN 不可达或版本漂移：

```bash
curl -O https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz
mkdir -p vendor
mv xlsx-0.20.3.tgz vendor
git add vendor/xlsx-0.20.3.tgz
yarn add file:vendor/xlsx-0.20.3.tgz
```

如果 `xlsx` 是被别的依赖间接引入的，用 `package.json` 的 `overrides` 强制指向同一份 tarball：

```json
{
  "overrides": {
    "xlsx": "https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz"
  }
}
```

**浏览器 / 无构建工具**。直接引官方 CDN 的独立脚本，它会挂到 `window.XLSX`：

```html
<script src="https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js"></script>
```

`xlsx.mini.min.js` 是精简版，省掉了 CSV/SYLK 编码、XLSB/XLS/Lotus/SpreadsheetML 2003/Numbers 这些格式和流式工具函数；只要不是只顾 xlsx，就用 full 版。

**ESM 页面（`type="module"`）**：

```html
<script type="module">
import { read, writeFileXLSX } from "https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs";
</script>
```

Deno / Bun / AMD / ExtendScript 各有独立安装页，以官方安装文档为准。**没有官方 Docker 镜像**——容器里按普通 Node 依赖装即可。

## 常用操作

**1）读本地文件，先看有哪些 sheet**（这是排查一切表格问题的第一步）：

```js
const XLSX = require("xlsx");
const wb = XLSX.readFile("input.xlsx");
console.log(wb.SheetNames);              // 工作表名列表
const ws = wb.Sheets[wb.SheetNames[0]];  // 取第一张表
console.log(ws["!ref"]);                 // 表的实际范围，如 "A1:H120"
```

**2）工作表 → JSON**。默认把首行当表头，输出对象数组；`header: 1` 输出「数组的数组」，适合表头不规整的表：

```js
const rows = XLSX.utils.sheet_to_json(ws);                 // [{姓名:"A",数量:1}, ...]
const aoa  = XLSX.utils.sheet_to_json(ws, { header: 1 });  // [["姓名","数量"],["A",1], ...]
```

**3）组一张新表并写成 xlsx**：

```js
const wb2 = XLSX.utils.book_new();
const ws2 = XLSX.utils.aoa_to_sheet([["姓名", "数量"], ["A", 1], ["B", 2]]);
XLSX.utils.book_append_sheet(wb2, ws2, "统计");
XLSX.writeFile(wb2, "out.xlsx", { compression: true });
```

**4）格式转换**（读进来、按新扩展名写出去，`bookType` 不写时会按文件名后缀推断）：

```js
// CSV -> xlsx
const wb3 = XLSX.readFile("in.csv", { raw: true });
XLSX.writeFile(wb3, "out.xlsx", { bookType: "xlsx" });
// xls -> xlsx
XLSX.writeFile(XLSX.readFile("old.xls"), "new.xlsx");
```

**5）从网络/内存读**，显式给 `type`，别让它猜：

```js
const ab = await (await fetch(url)).arrayBuffer();
const wb4 = XLSX.read(ab, { type: "array", cellDates: true });

const fs = require("fs");
const wb5 = XLSX.read(fs.readFileSync("in.xlsx"), { type: "buffer" });
```

**6）写成 Buffer 再交给上传 / 对象存储**（服务端导出附件的主要写法）：

```js
const buf = XLSX.write(wb2, { bookType: "xlsx", type: "buffer", compression: true });
fs.writeFileSync("out.xlsx", buf);
```

**7）只出数据、不要文件**：`sheet_to_json` 之外，`sheet_to_html(ws)` 生成 HTML 表格（社区版不带样式），`sheet_to_csv(ws)` 生成 CSV 字符串（注意它不带 BOM）。

**8）Node 里用 ESM 时，必须手动注入依赖**（这是官方明确的设计取舍，不是 bug）：

```js
import * as XLSX from "xlsx";
import * as fs from "fs";
import { Readable } from "stream";
import * as cpexcel from "xlsx/dist/cpexcel.full.mjs";

XLSX.set_fs(fs);                      // 让 readFile / writeFile 可用
XLSX.stream.set_readable(Readable);   // 让流式导出可用
XLSX.set_cptable(cpexcel);            // 老编码支持
```

Node 场景官方建议优先用 CommonJS，能省掉这一整段。

**9）只想限制读取量，做预览**：

```js
const wb6 = XLSX.readFile("huge.xlsx", { sheetRows: 20, sheets: 0 });
```

`sheetRows` 大于 0 时只解析指定行数；`sheets` 可以是下标、表名或它们的数组。

**10）大文件要流式出 CSV**，不要先转成对象数组再拼字符串：

```js
const XLSX = require("xlsx");
const fs = require("fs");
const wb = XLSX.readFile(process.argv[2], { dense: true });
const ws = wb.Sheets[wb.SheetNames[0]];
XLSX.stream.to_csv(ws).pipe(fs.createWriteStream("out.csv"));
```

**11）不动代码、只在命令行转一手**。仓库带一个独立的分发命令行工具（当前 1.1.4），随用随跑：

```bash
npx -p https://cdn.sheetjs.com/xlsx-cli/xlsx-cli-1.1.4.tgz xlsx-cli --help
# 仓库说明里的示例：把 test.csv 转成 test.csv.xlsx
npx -p https://cdn.sheetjs.com/xlsx-cli/xlsx-cli-1.1.4.tgz xlsx-cli --xlsx test.csv
```

也可以全局装：`npm install -g https://cdn.sheetjs.com/xlsx-cli/xlsx-cli-1.1.4.tgz`。其余参数以该工具 `--help` 的实际输出为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `npm i xlsx` 装到的版本很老，缺新特性 | 公开 npm registry 上的 `xlsx` 停在 0.18.5，官方说明这是 registry 侧的同步问题，权威源是官方 CDN | 卸掉后从 `https://cdn.sheetjs.com/xlsx-<版本>/xlsx-<版本>.tgz` 安装；间接依赖用 `overrides` 顶掉 |
| Node ESM 里 `readFile` / `writeFile` 报错或行为异常 | ESM 无法可靠地按需加载 `fs` / `stream`，社区版把依赖注入交给调用方 | 优先用 CommonJS；必须 ESM 就先调 `XLSX.set_fs(fs)`、`XLSX.stream.set_readable(Readable)`、必要时 `XLSX.set_cptable(...)` |
| 日期读出来是 `45291` 这样的数字 | 默认按表格软件习惯把日期存成数值 + 数字格式，不是 Date 对象 | 读取时加 `{ cellDates: true }`；反过来写文件时也要意识到，生成「真日期单元格」的文件第三方阅读器不一定认 |
| 导出的 CSV 用 Excel 打开中文乱码 | CSV 的编码/BOM 问题 | `XLSX.writeFile(wb, "x.csv")` 生成的 CSV 会自带 UTF-8 BOM；如果用 `sheet_to_csv` 自己拼文件，需要自己补 BOM |
| 合并单元格下面的行取值为空 | 合并区域的数值只存在左上角单元格，其余位置本来就是空的 | `sheet_to_json(ws, {header:1})` 拿到空位后自己向下填充；解析阶段不会替你补 |
| 手机号/订单号前面的 0 消失了，`SEPT1` 变成了日期 | 纯文本格式（CSV/HTML/RTF/DIF/PRN）会被激进地做类型推断 | 读取时加 `{ raw: true }` 关闭值解析，全部当字符串 |
| 打开加密的 xlsx/xlsb 直接抛错 | 社区版只支持 XLS 的 XOR 加密，AES 等方案在商业版 | 让用户先去掉密码，或改用商业版/其它工具；不要试图绕过 |
| 公式列拿到的是公式文本，不是结果 | 社区版解析公式到 `f` 字段，但不做公式求值 | 需要结果值就用能计算表格的宿主（Excel/LibreOffice 转换），或读别人已经算好的文件 |
| 大数据量脚本内存暴涨 / 很慢 | 整本 workbook 常驻内存；默认稀疏存储 | `sheetRows` 限制行数、`sheets` 只读需要的表、必要时用 `dense: true`；分批处理而不是一次读全量 |
| 安全扫描器报「原型污染」漏洞 | 官方文档明确说明这是扫描工具的误报（该问题在 0.19.3 已处理） | 按官方建议在扫描配置里抑制该条告警，并在说明里记录理由 |
| 输出给第三方工具的文件被拒 / 少内容 | 不同格式的能力不同，且生成文件不保证被第三方阅读器接受 | 对外交付优先用 xlsx；给 Numbers 用时考虑加 `bookSST: true` 提升兼容性 |
| 解析报错被吞了，只读到一半的表 | 默认会抑制工作表解析错误，保证多表文件里正常的表能出来 | 排查阶段加 `{ WTF: true }` 让错误抛出 |
| 某些非标准导出器生成的文件行数不对 | 这类文件自报的范围不可信 | 加 `{ nodim: true }`，让库按实际单元格推算范围 |
| 写文件时抛异常：工作簿是空的 / 表名重复 | 写出器不允许空工作簿；`book_append_sheet` 遇到重名会抛错 | 写之前确认至少追加过一张表；要自动去重就给 `book_append_sheet(wb, ws, name, true)` 传第四个参数 |
| 日期整体偏移了 4 年 | 工作簿用的是 1904 起算的日期系统（老版 Mac Excel 遗留） | 读出来后检查 `wb.Workbook.WBProps.date1904`，需要时自行做基准换算 |
| 从 `f` 字段拿到的公式带不带 `=` 说不清 | 单元格里的公式是以**不带**前导 `=` 的 A1 风格文本存放的 | 取值后按需自行补/去 `=`；写回公式时同样不要带前导 `=` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 安装时从官方 CDN 取 tarball；浏览器版从 CDN 载脚本；业务代码里可能 `fetch` 表格数据 |
| 读取文件 | 是 | `readFile` / `read` 读取用户指定的表格文件，路径由调用方给定 |
| 写入文件 | 是 | `writeFile` 生成 xlsx/csv 等结果文件，只写调用方指定的输出路径 |
| 凭证 | 否 | 库本身不需要任何账号、Key 或 Token；如需读取加密文件的密码由用户显式提供 |
| 子进程 / 后台常驻 | 否 | 纯库，无常驻进程；只有调用仓库内的命令行工具时才会起子进程 |

## 触发场景

- 「帮我把这个 xlsx 里的数据整理成 JSON / CSV。」
- 「这几个 csv 合并成一个 xlsx，每个文件一个 sheet。」
- 「把老系统的 xls 批量转成 xlsx。」
- 「从下载的表格里挑出我需要的列，再导出一份新的表。」
- 「网页上传表格后直接展示，不要传到后端。」
- 「把查询结果导出成 Excel 附件。」

## 能力边界

**覆盖**：

- 读取：xlsx/xlsm/xlsb、BIFF2-8 的 xls、SpreadsheetML 2003、ODS/FODS、Numbers、CSV/TSV/PSV/SSV 等分隔文本、HTML 表格、DBF、DIF、SYLK、RTF、PRN、Lotus WK1/WK3、Ethercalc 记录格式。
- 写出（`bookType` 可选）：xlsx、xlsm、xlsb、biff8/biff5 等 xls、xlml、ods、fods、numbers、csv、txt、sylk、html、dif、dbf、wk1、wk3、rtf、prn、eth。
- 数据层能力：单元格/行列表、多工作表、合并区域信息、公式文本（`f`）、数字格式（`z`）、格式化文本（`w`）、日期单元格（`cellDates`）、共享字符串表（`bookSST`）、ZIP 压缩、VBA blob 透传（`bookVBA`）、流式 CSV 导出。
- 运行环境：Node（CommonJS 优先，也支持 ESM）、浏览器（独立脚本 / ESM / 打包器）、Deno、Bun、AMD、ExtendScript。

**不覆盖**：

- 样式与图形：字体、颜色、边框、条件格式、图表、图片、数据透视表、批注渲染——社区版不做，属商业版范围。
- 公式求值、计算链重算。
- AES 加密的 xlsx/xlsm/xlsb，以及新版 XLS 的 RC4 加密。
- 表格之外的一切：PDF/图片里的表格、扫描件识别（属 OCR 类工具）、数据库连接。
- 文件托管与协作：不做 Office 宿主、不做在线协同编辑、不执行宏。

## 依赖条件

- Node.js、浏览器、Deno 或 Bun 任一运行环境即可；官方安装页分别给出各环境的装法。
- 没有必须的系统级依赖（不需要 Office、不需要 LibreOffice、不需要 Java）。
- 不需要账号或 API Key；`xlsx.zahl` 这类附加脚本只在你确实要导出 Numbers 格式时才需要，它提供的是 `numbers` 选项要求的 Base64 载荷。
- 从 CDN 安装/引用需要能访问 `https://cdn.sheetjs.com`；内网环境请提前把 tarball 或脚本 vendoring 进仓库。
- 仓库里另有一个 Node 命令行工具包（`packages/xlsx-cli`），参数以仓库内该包的说明为准。

## 已知限制

- 社区版与商业版能力有明确分界：**数据**在社区版，**样式/图形/加密/公式求值**在商业版。选型时必须先确认需求落在哪一侧。
- 写入能力比读取窄：不是所有能读的格式都能写，且写出结果不保证被第三方阅读器完全接受。
- 日期处理有两种取向（数值单元格 vs 真 Date 对象），默认取向与表格软件一致；一旦开启 `cellDates`，导出的文件在别的工具里可能表现不同。
- 使用 `sheetRows` 限制行数时，转对象数组的结果会比指定值少一行（表头自身占一行被计入）。
- 明文格式的类型推断很激进，无法完全关掉推断以外的全部启发式行为；要不要「当字符串」必须在读取时决定。
- 日期与时间处理在 0.20.0 做过一次整体调整，跨版本升级时要重新验证日期相关的结果。
- 合并区域只保存范围信息，不保存「哪些格子被覆盖」的推导结果；重叠的合并区域也不会被自动发现。
- Deno 与 Bun 的安装页在官方文档里都标注为实验性支持；生产项目优先 Node + CommonJS。

## 自检清单

执行前：

- [ ] 确认任务落在社区版能力内——**不需要保留样式/图表/公式结果**，否则先换方案。
- [ ] 确认输入文件没有 AES 加密；有密码的 XLS 之外一律不要硬试。
- [ ] 确认 `xlsx` 是从官方 CDN 或 vendored tarball 装的，而不是 npm 上的旧版。
- [ ] 确认运行环境是 CommonJS 还是 ESM；ESM 需先注入 `fs` / `stream` / `cptable`。

执行中：

- [ ] 拿到文件先打印 `SheetNames` 和 `!ref`，用真实结构决定取哪张表、从哪一行开始。
- [ ] 表头不规整就先用 `{header: 1}` 看「数组的数组」，不要直接假设首行是表头。
- [ ] 涉及编号、日期、金额的列，先小样本验证类型，再决定 `raw` / `cellDates` 的取值。

执行后：

- [ ] 用同一份数据做一次抽样核对（行数、首尾行、日期列、以 0 开头的编号）。
- [ ] 导出的 CSV 用 Excel 实际打开一次，确认中文与编号没被破坏。
- [ ] 生成的文件路径、字段命名、sheet 名符合交付要求；需要压缩就带上 `compression: true`。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/SheetJS/sheetjs | 上游仓库（安装与完整文档以它为准） |
| https://docs.sheetjs.com/docs/api/parse-options | 读取参数完整清单 |
| https://docs.sheetjs.com/docs/api/write-options | 写出参数与支持的输出格式清单 |

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
