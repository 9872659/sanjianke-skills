---
name: sanjianke-pdf-lib
slug: sanjianke-pdf-lib
displayName: 三剪客 · JS 创建修改 PDF
description: "pdf-lib：JS 创建修改 PDF 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "pdf-lib：JS 创建修改 PDF 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - PDF
  - JavaScript
  - Node
---

# 三剪客 · JS 创建修改 PDF

一个纯 JavaScript 的 PDF 生成与修改库，不需要本机装命令行工具、不需要 JVM、不需要渲染器。
它能新建文档、往既有 PDF 上写字贴图、跨文档拷贝页面、创建和填写表单、读写元数据，
同一份代码在 Node、浏览器、Deno、React Native 里都能跑。

和多数 JS PDF 库最大的区别是：它**能改已有的 PDF**，不只是从零生成；
反过来说，它不会帮你把 HTML/CSS 变成 PDF，也不能提取页面上已有的文字。

**上游项目**：`pdf-lib`　**仓库**：https://github.com/Hopding/pdf-lib

## 什么时候用 / 不用

**用它**：

- 要在 Node 服务里动态生成 PDF（发票、合同、证书、报表），且希望不依赖外部二进制。
- 要往既有 PDF 上叠内容：加水印文字、盖章图片、把另一个 PDF 的某页贴进来。
- 要按字段名自动填写 PDF 表单（含中文等非拉丁字符），或把填好的表单「压平」成静态内容。
- 要在前端浏览器里直接生成/修改 PDF 并触发下载，不经过服务器。
- 要跨多个 PDF 抽页合并成一个新文档，比如从一堆模板里挑页拼装。
- 要给 PDF 设置标题、作者等元数据，或添加附件。

**不要用它**：

- 要把 HTML/CSS 页面「打印」成 PDF——它不解析 HTML，用 Puppeteer / Playwright 这类无头浏览器。
- 要提取 PDF 页面上已有的正文文字——它只能读表单字段的值，不能读页面正文（作者明确说明该能力尚未实现）。
- 要处理加密 PDF——传进去会直接抛 `EncryptedPDFError`，`ignoreEncryption: true` 只是跳过报错、并不会解密，官方明确不建议用。
- 要压缩体积、拆分大文件、批量加密、加页码这类「整篇级」运维操作——用 pdfcpu 这类命令行工具更省事。
- 要做复杂分页排版（自动换行、表格跨页、页眉页脚流式布局）——它只给你画布级 API，排版逻辑要自己写，或换专门的排版方案。

## 安装

```bash
# npm
npm install --save pdf-lib

# yarn
yarn add pdf-lib

# 需要内嵌自定义字体（尤其中文/CJK）时必须再加装 fontkit，并注册到文档上
npm install --save @pdf-lib/fontkit
```

浏览器里不想走打包器的，可以直接用 UMD 构建，会挂到全局 `PDFLib`：

```html
<script src="https://unpkg.com/pdf-lib/dist/pdf-lib.min.js"></script>
<script>
  var PDFDocument = PDFLib.PDFDocument;
  var rgb = PDFLib.rgb;
</script>
```

生产环境请锁定版本号，例如 `https://unpkg.com/pdf-lib@1.4.0/dist/pdf-lib.min.js`（具体可用版本以 npm 上的实际发布为准）。

## 常用操作

```js
// 1. 从零创建一份 PDF 并写一段文字
import { PDFDocument, StandardFonts, rgb } from 'pdf-lib'

const pdfDoc = await PDFDocument.create()
const timesRoman = await pdfDoc.embedFont(StandardFonts.TimesRoman)
const page = pdfDoc.addPage()
const { width, height } = page.getSize()
page.drawText('Creating PDFs in JavaScript is awesome!', {
  x: 50, y: height - 120, size: 30, font: timesRoman, color: rgb(0, 0.53, 0.71),
})
const pdfBytes = await pdfDoc.save()   // Uint8Array，Node 里写文件即可
```

```js
// 2. 修改既有 PDF：在首页斜着叠加文字（角度用 degrees 包装）
import { degrees, PDFDocument, rgb, StandardFonts } from 'pdf-lib'

const pdfDoc = await PDFDocument.load(existingPdfBytes)
const helvetica = await pdfDoc.embedFont(StandardFonts.Helvetica)
const firstPage = pdfDoc.getPages()[0]
const { width, height } = firstPage.getSize()
firstPage.drawText('This text was added with JavaScript!', {
  x: 5, y: height / 2 + 300, size: 50, font: helvetica,
  color: rgb(0.95, 0.1, 0.1), rotate: degrees(-45),
})
const bytes = await pdfDoc.save()
```

```js
// 3. 跨文档拷贝页面并重排：取 A 的第 1 页、B 的第 743 页，插到新文档指定位置
const pdfDoc = await PDFDocument.create()
const donorA = await PDFDocument.load(firstDonorPdfBytes)
const donorB = await PDFDocument.load(secondDonorPdfBytes)
const [pageFromA] = await pdfDoc.copyPages(donorA, [0])
const [pageFromB] = await pdfDoc.copyPages(donorB, [742])
pdfDoc.addPage(pageFromA)
pdfDoc.insertPage(0, pageFromB)
```

```js
// 4. 填表单：先 embed 非拉丁字体，再 setText 并压平
import fontkit from '@pdf-lib/fontkit'

const pdfDoc = await PDFDocument.load(formPdfBytes)
pdfDoc.registerFontkit(fontkit)
const font = await pdfDoc.embedFont(fontBytes)
const form = pdfDoc.getForm()
form.getTextField('CharacterName 2').setText('马里奥')
form.getCheckBox('Check Box3').check()
form.getRadioGroup('Group2').select('Choice1')
form.updateFieldAppearances(font)   // 关键一步：用嵌入字体重绘字段外观
form.flatten()                      // 需要不可编辑的成品时再压平
const bytes = await pdfDoc.save()
```

```js
// 5. 贴图与元数据（PNG / JPG 各有独立方法，尺寸要先算好）
const jpgImage = await pdfDoc.embedJpg(jpgImageBytes)
const dims = jpgImage.scale(0.25)
const page = pdfDoc.addPage()
page.drawImage(jpgImage, { x: 50, y: 50, width: dims.width, height: dims.height })

pdfDoc.setTitle('二创素材清单')
pdfDoc.setAuthor('内容团队')
await pdfDoc.attach(otherPdfBytes, 'appendix.pdf', { mimeType: 'application/pdf' })
```

```js
// 6. 读写文档元数据、加 SVG 路径
const meta = pdfDoc.getTitle()                    // 也有 getAuthor / getKeywords / getSubject 等
page.drawSvgPath('M 0,20 L 100,160 L 200,20 Z', { x: 25, y: 500 })
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 写中文直接抛错：`WinAnsi cannot encode "Ω"` | 标准 14 字体用 WinAnsi 编码，只覆盖拉丁字符集 | 改用 `@pdf-lib/fontkit` + 自带中文字体：`pdfDoc.registerFontkit(fontkit)` 后 `embedFont(fontBytes)`，绘图时传该 font |
| 报 `FontkitNotRegisteredError` | 没注册 fontkit 就想嵌入自定义字体 | 先 `npm i @pdf-lib/fontkit`，再 `pdfDoc.registerFontkit(fontkit)`；标准字体不需要这步 |
| 表单填了中文，保存时报编码错误或显示空白 | 表单字段默认外观用 Helvetica，字段里塞了非拉丁字符 | 先 `form.updateFieldAppearances(customFont)` 用嵌入字体重绘外观，再 `save()` |
| 保存出来的 PDF 多了一张空白页 | `save()` 的 `addDefaultPage` 默认为 `true`，零页文档会自动补一页 | 文档确实要零页时传 `save({ addDefaultPage: false })`；多数情况下应显式 `addPage()` |
| `PDFDocument.load()` 抛 `EncryptedPDFError` | pdf-lib 明确不支持加密文档 | 先用有密码的工具（如 pdfcpu）解密；`ignoreEncryption: true` 只是不报错、并不解密，官方不建议 |
| 自定义字体嵌进去后文件体积暴涨 | 默认嵌入整个字体文件 | 传 `embedFont(fontBytes, { subset: true })` 做子集化；注意子集化并非对所有字体都有效 |
| `copyPages` 之后页面错位或报 `ForeignPageError` | 页面对象归属于原文档，必须先拷贝再插入新文档 | 用 `const [p] = await newDoc.copyPages(srcDoc, [i])`，再 `newDoc.addPage(p)` / `insertPage(idx, p)` |
| `save()` 输出体积比想象大或结构怪 | `useObjectStreams` 默认为 `true`，会写对象流 | 需要兼容老旧阅读器时传 `save({ useObjectStreams: false })` |
| 打开别人的 PDF 改完发现 Producer / 修改时间被改了 | 加载时 `updateMetadata` 默认为 `true`，会写入 pdf-lib 作为 Producer 并刷新 ModDate | 需要保持原始元数据就传 `PDFDocument.load(bytes, { updateMetadata: false })` |
| 想读页面上的正文文字却读不到 | 官方明确说明：只能读表单字段的值，不能提取表单之外的页面文字 | 换用专门的文本抽取工具，别在 pdf-lib 上绕 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 库本身不联网；除非你自己的代码去 fetch 字体、图片或 PDF 字节 |
| 读取文件 | 是 | 读取源 PDF、字体文件、图片、表单数据 |
| 写入文件 | 是 | 输出的 PDF 字节需要由调用方落盘或触发浏览器下载 |
| 凭证 | 否 | 不使用账号或 API Key；不提供密码解密能力 |
| 子进程 / 后台常驻 | 否 | 纯 JS 库，跑在调用方进程内，不启动外部程序 |

## 触发场景

- 「用 Node 生成一份带中文的 PDF 发票 / 证明。」
- 「在这个 PDF 每一页右上角盖上我们的 logo。」
- 「把这两个 PDF 的第 1 页拼成一份新文件。」
- 「帮我按 Excel 里的数据批量填这份 PDF 表单。」
- 「前端点一下就下载 PDF，不要走服务器。」
- 「把 PDF 的标题和作者信息改成我们公司的。」

## 能力边界

**覆盖**：

- 创建新 PDF、加载既有 PDF 并修改。
- 页面级操作：新增、插入、删除、跨文档拷贝、嵌入整页或裁剪某页区域再绘制。
- 绘制能力：文字（含旋转、颜色、自定义字体）、图片（PNG/JPG）、矢量图形、SVG 路径、PDF 页面。
- 表单：创建/读取/填写按钮、复选框、下拉框、选项列表、单选组、文本域，并支持压平。
- 字体：14 个标准字体，或通过 fontkit 嵌入任意 TTF/OTF 并可选做子集化。
- 元数据：标题、作者、主题、关键词、创建者、生产者、创建/修改时间、语言；视图偏好；文档附件；文档级 JavaScript。
- 环境：Node、浏览器、Deno、React Native 同一套 API；也提供 UMD 构建供 `<script>` 直接使用。

**不覆盖**：

- 不解析 HTML/CSS，不做「网页转 PDF」。
- 不能提取或编辑页面上已有的正文文字，只能读表单字段值。
- 不支持加密文档，也不提供解密、权限设置、数字签名。
- 不支持 XFA 表单（`getForm()` 会提示移除 XFA 数据）。
- 不做压缩优化、不重排已有内容、不做 OCR。
- 没有流式排版引擎：自动换行只有 `drawText` 的 `maxWidth`/`lineHeight` 这类基础支持，表格、分页、页眉页脚要自己实现。

## 依赖条件

- Node.js（现代 LTS 均可）或任意现代浏览器 / Deno / React Native 运行时。
- 包管理器：npm 或 yarn；也可直接用 UMD 构建不装包。
- 嵌入自定义字体时额外需要 `@pdf-lib/fontkit`，并准备字体文件字节。
- 无需账号、无需 API Key、无需外部二进制。

## 已知限制

- 加密文档只能绕开报错、无法真正解密。
- 页面正文文字无法提取，也无法编辑。
- `copy()` 不会复制表单、大纲等全部信息（官方注释已说明）。
- XFA 表单不受支持。
- 字体子集化对部分字体无效。
- 复杂排版需要自行实现，或交给无头浏览器方案。

## 自检清单

- 执行前：
  - 确认输入 PDF 未加密；加密的先解密。
  - 需要中文/非拉丁文字时，确认已装 `@pdf-lib/fontkit` 且已 `registerFontkit`。
  - 表单字段名用 `form.getFields()` 打印一遍核对，不要凭猜测写字段名。
  - 明确是否需要保留原始元数据（决定 `updateMetadata`）。
- 执行后：
  - 用真实阅读器（Acrobat / Chrome / Preview）打开结果，确认中文不乱码、水印位置正确。
  - 表单场景确认压平后的字段不可再编辑、值正确。
  - 核对页数与页序是否符合预期。
  - 发现 `EncryptedPDFError`、`FontkitNotRegisteredError`、`ForeignPageError` 时按上表逐条排查。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/Hopding/pdf-lib | 上游仓库（安装与完整文档以它为准） |

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
