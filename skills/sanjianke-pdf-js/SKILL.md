---
name: sanjianke-pdf-js
slug: sanjianke-pdf-js
displayName: 三剪客 · PDF 解析与渲染
description: "pdf.js：PDF 解析与渲染 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "pdf.js：PDF 解析与渲染 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档处理
---

# 三剪客 · PDF 解析与渲染

**不装插件、不靠原生库，用 JavaScript 把 PDF 打开、画出来、把文字读出来。**

它是浏览器里那个"内置 PDF 阅读器"的引擎（Firefox 19+ 内置），同时也是一个通用库：给定一份 PDF，你可以拿它的**元数据、页数、大纲、文本内容（带坐标）、批注、操作符列表**，也可以把某一页**渲染到 canvas** 上变成画面。解析和渲染默认跑在 Web Worker 里，不阻塞主线程；服务器支持 HTTP Range 时，它会**自动分段按需拉取**，大文件不必整份下载完才显示。

它有两个使用面，先分清再动手：

1. **直接用 API**（`pdfjs-dist` 这个 npm 包）。你要自己写界面，或只想抽文本/元数据/缩略图。**绝大多数集成场景走这条。**
2. **直接用现成的 viewer**（官方预编译 release 里的 `web/viewer.html`）。开箱即用的完整阅读界面：缩放、搜索、目录、旋转、打印、批注显示。想省事就用它，但官方明确希望你不要原样嵌入自己的站点——**至少换个皮或用它的 viewer 组件自己搭**。

一句话记住边界：**它是"读"的工具，不是"写"的工具。** 生成、编辑、合并、拆分、加密、签名这些事它不做（批注也只支持很有限的添加子集）。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视用法 | 从 URL 加载 PDF 会发起真实请求，受浏览器同源策略约束；服务器支持 Range 时自动**分段拉取**（不会傻等整份下载）。通过 CDN 引库时另有一次静态资源请求 |
| 读取文件 | 是（必需） | Node 侧用 `fs` 读本地 PDF 成 `Uint8Array`；浏览器侧读用户选择的文件。另外读取库自带的 `cmaps/` 与 `standard_fonts/` 资源目录 |
| 写入文件 | 视用法 | Node 渲染示例会把 canvas 转成 PNG 写盘；浏览器侧通常走 `toBlob` / `toDataURL` 让用户下载，或写进页面 DOM |
| 凭证 | 视需要 | 库本身不需要账号或 Key。**加密 PDF** 需要在加载参数里传口令（`password`） |
| 子进程 / 后台常驻 | 是（内部） | 浏览器里解析与渲染默认在 **Web Worker** 中执行，避免卡住主线程；Node 环境走同进程的 fake worker。worker 位置用 `GlobalWorkerOptions.workerSrc` 指定 |
| 本地端口 | 视用法 | 源码开发时 `npx gulp server` 会起一个本地开发服务器（默认 `http://localhost:8888/web/viewer.html`）用于调试，不是生产部署方式 |

**安全提醒**：PDF 是不可信输入。加载来路不明的文件时，建议关掉基于 `eval` 的加速路径（`isEvalSupported: false`），并注意跨域加载需要目标服务器配合 CORS；纯前端解析的好处是**文件不必上传到你自己的服务器**，但反过来意味着任何取巧的"本地预览"也不受服务端校验保护。

## 触发场景

- "网页里要一个能搜索、能翻页、能看目录的 PDF 阅读界面，但我不要浏览器默认那个样式"——用 viewer 组件或官方 viewer 改皮。
- "把 PDF 第一页渲染成缩略图/封面图"——`getPage` + `render` 到 canvas。
- "要在文档里做全文搜索、关键词高亮、跳到命中位置"——`getTextContent()` 拿文本项与坐标。
- "只想要元数据（标题、作者、页数）和大纲"——`getMetadata()` / `getOutline()`。
- "前端直接读用户选的文件，不上传服务器"——浏览器端 `getDocument({ data })` 本地解析。
- "Node 里批量抽 PDF 的文字做索引"——`legacy` 构建 + `getDocument`，不需要 canvas。
- "大文件不想整份下载就想先看第一页"——服务器开 Range 支持，它会自动分段取。
- "想自己搭阅读器 UI（工具栏、页码、缩放、侧边栏）"——用 viewer 组件层而不是从零写。

## 什么时候用 / 不用

**用它**：

1. **网页里自建 PDF 阅读体验**。要自定义工具栏、水印、权限提示、埋点、内嵌到自己的应用里，这是最主流的选择。
2. **前端做纯客户端解析**。文件不出浏览器：合规上很舒服，用户也不必先上传。
3. **抽文本与元数据**。`getTextContent()` 给出每个文本片段的字符串、变换矩阵与宽高，能做搜索、高亮、定位、简单版面判断。
4. **渲染成图像**。缩略图、封面图、页面预览、canvas 上再叠自己的图层。
5. **大文件按需加载**。服务器支持 HTTP Range 时自动分段取，配合"只渲染可见页"的策略体验很好。
6. **跨浏览器一致的渲染**。不想依赖各家浏览器内置查看器的差异（或想覆盖内置查看器行为的场景）。
7. **Node 里做轻量文本抽取**。不需要渲染时，`legacy` 构建够用，也不用装 canvas。

**不要用它**：

1. **要生成 / 编辑 / 合并 / 拆分 / 加密 / 签名 PDF**。它不是写入端工具；批注也只支持很有限的一部分类型。这类需求换专门的 PDF 处理库。
2. **扫描件要出文字**。没有文字层时 `getTextContent()` 只会给你空结果——它不 OCR。先过 OCR，再谈文本。
3. **Node 里要跑重型批量渲染流水线**。官方 FAQ 明确写的支持矩阵里，Node 属于"mostly / limited"，渲染还需要额外的 canvas 实现（带原生编译依赖）。服务端大批量出图，用更对口的工具更稳。
4. **只想让浏览器显示一个 PDF**。`<embed>` / `<iframe>` 或浏览器内置查看器更快更省事，别为了"显示"引入一个库。
5. **要精确还原排版结构（转 HTML / Markdown / 表格）**。它渲染的是视觉画面、抽的是文本片段；版式语义重建不是它的目标。
6. **要解析表单、填表、做 PDF 结构级改造**。这些超出它的核心范围。

## 安装

### npm（推荐，集成到自己的项目）

```bash
npm install pdfjs-dist
# Webpack 场景官方 wiki 给的写法是 --save-dev
npm install pdfjs-dist --save-dev
```

包名是 `pdfjs-dist`。**注意构建路径有两套**：

- `pdfjs-dist/build/pdf.mjs` —— 面向最新浏览器的现代构建。
- `pdfjs-dist/legacy/build/pdf.mjs` —— 面向旧环境（含 Node）的翻译/补丁版本。**Node 里用它。**

配套资源目录：`pdfjs-dist/cmaps/`（CJK 等需要）、`pdfjs-dist/standard_fonts/`。

### CDN

不想走打包工具时可以直接引：

- jsDelivr：`https://www.jsdelivr.com/package/npm/pdfjs-dist`
- cdnjs：`https://cdnjs.com/libraries/pdf.js`
- unpkg：`https://unpkg.com/pdfjs-dist/`

**用 CDN 时必须保证 pdf.js 主文件与 worker 文件是同一个版本**，否则会报版本不匹配（见"常见坑"）。

### 官方预编译 release（要现成 viewer）

到项目 releases 页下载官方发行包，里面含 generic 构建与完整 viewer。把 `build/` 与 `web/` 一起部署，然后：

```
https://你的域名/web/viewer.html?file=<encodeURIComponent(PDF地址)>
```

想看官方在线效果：现代浏览器版 `https://mozilla.github.io/pdf.js/web/viewer.html`，旧浏览器版加 `/legacy`。

### 从源码构建（要改库本身或自建产物）

```bash
git clone https://github.com/mozilla/pdf.js.git
cd pdf.js
npm install

npx gulp server            # 开发服务器，浏览器打开 http://localhost:8888/web/viewer.html
npx gulp generic           # 产出 build/generic/build/pdf.js 与 pdf.worker.js
npx gulp generic-legacy    # 需要支持旧浏览器时用这个
npx gulp minified          # 压缩版（官方用的 Terser，别自己换高级压缩选项）
npx gulp chromium          # 构建 Chromium 扩展到 build/chromium
npx gulp dist-install      # 在本仓库目录里生成并安装 pdfjs-dist 包（跑官方示例用）
```

构建产物的规则要记住：**`pdf.js` 和 `pdf.worker.js` 两个文件都要有，但页面里只需要引 `pdf.js`**——worker 由它自己加载。官方同时提醒这些文件体积很大，生产环境应当压缩。

### 其他产物

- **Chrome 扩展**：官方仓库文档给了自行构建法（`npx gulp chromium` 后在 `chrome://extensions` 加载 `build/chromium`）。
- **PDF 调试器**：可以浏览 PDF 内部结构，官方在线地址见下方链接。

## 常用操作

### 1. 浏览器里渲染一页到 canvas（最小可用）

```js
import * as pdfjsLib from "pdfjs-dist";

// 必须指定 worker，否则会退回 fake worker 并报错/变慢
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.mjs",
  import.meta.url
).toString();

const loadingTask = pdfjsLib.getDocument({ url: "/files/demo.pdf" });
const pdf = await loadingTask.promise;

const page = await pdf.getPage(1);
const viewport = page.getViewport({ scale: 1.5 });

const canvas = document.getElementById("c");
canvas.width = viewport.width;
canvas.height = viewport.height;

const renderTask = page.render({
  canvasContext: canvas.getContext("2d"),
  viewport,
});
await renderTask.promise;          // 必须 await，否则图片是空的

page.cleanup();                    // 释放该页资源
```

### 2. Node 里抽元数据与文本（官方示例的写法）

```js
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

const loadingTask = getDocument({ url: "demo.pdf" });
const pdfDoc = await loadingTask.promise;

console.log("页数:", pdfDoc.numPages);

const { info, metadata } = await pdfDoc.getMetadata();

for (let i = 1; i <= pdfDoc.numPages; i++) {
  const pdfPage = await pdfDoc.getPage(i);
  const viewport = pdfPage.getViewport({ scale: 1.0 });   // 拿页面尺寸
  const { items } = await pdfPage.getTextContent();
  console.log(`第 ${i} 页 ${viewport.width}x${viewport.height}`);
  console.log(items.map((item) => item.str).join(" "));
  pdfPage.cleanup();
}

await loadingTask.destroy();       // 用完销毁，长进程里很重要
```

用内存里的数据加载（比如从数据库/上传流拿到的 Buffer）：

```js
import fs from "fs";
const data = new Uint8Array(fs.readFileSync("demo.pdf"));
const loadingTask = getDocument({ data });
```

### 3. 中文 / 非嵌入字体必须配的资源路径

PDF 里的 CJK 字符集（cmap）和标准字体数据**不在主包里**，得指过去，否则会出现乱码或缺字：

```js
const loadingTask = getDocument({
  data,
  cMapUrl: "../../../node_modules/pdfjs-dist/cmaps/",
  cMapPacked: true,
  standardFontDataUrl: "../../../node_modules/pdfjs-dist/standard_fonts/",
});
```

这是官方 Node 渲染示例里的真实写法；路径按你的项目结构调整即可。

### 4. 渲染成 PNG（Node，需要 canvas 实现）

官方示例用文档自带的 canvas 工厂，流程是：

```js
const page = await pdfDoc.getPage(1);
const viewport = page.getViewport({ scale: 1.0 });

const canvasFactory = pdfDoc.canvasFactory;
const canvasAndContext = canvasFactory.create(viewport.width, viewport.height);

const renderTask = page.render({
  canvasContext: canvasAndContext.context,
  viewport,
});
await renderTask.promise;

fs.writeFileSync("output.png", canvasAndContext.canvas.toBuffer("image/png"));
page.cleanup();
```

**前置条件**：Node 侧要有一个可用的 canvas 实现（官方示例依赖仓库里的 canvas 包）。canvas 有原生编译依赖，装不上时更省事的替代是走无头浏览器渲染。

### 5. 用现成 viewer，而不是自己写界面

```js
// 通过查询参数指定文件（URL 需要 encodeURIComponent）
// https://你的域名/web/viewer.html?file=https%3A%2F%2Fexample.com%2Fa.pdf

// 或者在页面里控制：先不带文件打开，再手动 open
PDFViewerApplication.open({ url: "/files/demo.pdf" });

// 也可以直接喂二进制（比 base64 更省内存）
PDFViewerApplication.open({ data: new Uint8Array(buffer) });
```

不加载任何文件启动：把 viewer 的 `defaultUrl` 应用选项设成空字符串，或用不带地址的 `?file=`。

### 6. 加载加密 PDF

```js
const loadingTask = getDocument({ url: "locked.pdf", password: "口令" });
```

### 7. 只在可见页渲染（性能与内存的关键）

官方 FAQ 明确不建议一次渲染全部页面：一页 Letter 尺寸在 96 DPI 下是 816×1056 像素，画布占用约 `816×1056×4 ≈ 3.5MB`；HiDPI（`devicePixelRatio = 2`）还要再乘 4，单页就可能 14MB。100 页同时留着，内存直接爆。

```js
// 思路：只对进入视口的页创建 canvas 并 render，离开视口就 cleanup
// 官方 demo viewer 就是这么做的
```

### 8. 加固：加载不可信 PDF

```js
const loadingTask = getDocument({
  data,
  isEvalSupported: false,     // 关掉基于 eval 的加速路径
});
```

配合"只渲染可见页 + 及时 `cleanup()` / `destroy()`"，能显著降低一个坏文件带来的影响与资源占用。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 报 `The API version "x.y.z" does not match the Worker version "a.b.c"` | pdf.js 主文件与 worker 文件**版本不一致**（最常见于：升级了库但浏览器缓存了旧 worker；或本地引主文件、worker 却从 CDN 拿） | 保证两者同版本；清浏览器缓存后刷新；从 CDN 取 worker 时锁定与主文件一致的版本。版本号可以在分发文件里搜 `pdfjsVersion` 找到 |
| "Setting up fake worker failed" 或明显变慢 | 没配 worker，退回主线程 fake worker | 设置 `GlobalWorkerOptions.workerSrc` 指向 worker 文件（`pdfjs-dist/build/pdf.worker.mjs`，旧环境用 `legacy` 对应文件）；打包工具要单独产出 worker bundle |
| Node 里 import `build/pdf.mjs` 报错或行为异常 | 现代构建面向最新浏览器，Node 应用 `legacy` 构建 | 改成 `pdfjs-dist/legacy/build/pdf.mjs` |
| 从别的域加载 PDF 失败 | 浏览器同源策略；PDF.js 与普通 JS 权限相同，不能跨域请求 | 目标服务器开 CORS；或在自己域下做代理；注意官方 demo viewer 部署在非自家域时**会主动拦截** `?file=` 以防内容伪装 |
| 中文/日文显示成乱码或缺字 | PDF 用了外部 cmap 或标准字体，而库自带的 `cmaps/`、`standard_fonts/` 没指过去 | 配 `cMapUrl` + `cMapPacked: true` + `standardFontDataUrl`，路径指向 `pdfjs-dist` 对应目录 |
| 渲染出来是空白 canvas | 没 `await renderTask.promise` 就去取图/显示；或 canvas 尺寸没按 viewport 设 | 先 `await renderTask.promise`，再读 canvas；`canvas.width/height` 用 viewport 的宽高（HiDPI 场景按 `devicePixelRatio` 放大并配合 `transform`） |
| 页面开久了内存一直涨 | 没释放页资源与文档 | 每页处理完 `page.cleanup()`；整份用完 `loadingTask.destroy()`；只渲染可见页 |
| 一次渲染几十上百页高分辨率，浏览器卡死或崩 | 每个 canvas 都占数 MB 内存（HiDPI 下乘以 4） | 只创建/渲染可见页；离开视口即销毁；需要整本导出就走 Node 侧流水线而不是浏览器 |
| 自己压缩后的产物运行不正常 | 某些高级压缩选项会破坏 PDF.js 代码 | 用官方 `npx gulp minified`（Terser）；若坚持用别的压缩器，**必须保留原始类名/函数名**，只做空白与注释清理 |
| `getTextContent()` 返回空 | 该 PDF 是纯扫描图片，没有文字层 | 它不做 OCR；先过 OCR 生成文字层，或改用 OCR 方案 |
| 大文件加载慢、迟迟不出第一页 | 服务器没开 HTTP Range 支持，无法分段按需取 | 让服务器返回 Range 相关头；PDF.js 会自动利用它只取渲染可见页所需的部分 |
| 想设置默认打开哪个 PDF，改了没生效 | viewer 的默认地址由应用选项控制 | 改 `web/app_options.js` 里的 `defaultUrl`；或直接用 `?file=` 查询参数（记得 `encodeURIComponent`）；想"先空着再手动打开"就把它设成空字符串 |

## 能力边界

**覆盖**：

- **解析**：页数、页面尺寸（viewport）、文档元数据（`info` / XMP `metadata`）、大纲、批注、文本内容（每个片段的字符串、变换矩阵、宽高）、页面操作符列表（可做更底层的分析与定制渲染）。
- **渲染**：把页面渲染到 canvas，支持缩放与旋转（通过 viewport），可作为缩略图/封面/预览；渲染默认在 Web Worker 中执行，不阻塞主线程。
- **完整的阅读器 UI**：官方预编译 release 内含 viewer，具备缩放、翻页、搜索、目录、旋转、演示模式、打印、下载、批注显示等能力（浏览器内置的阅读体验就是它）。
- **两套构建**：现代构建（最新浏览器）与 `legacy` 构建（旧浏览器、Node 等）；可自行构建、压缩，也可构建 Chromium 扩展。
- **按需加载**：服务器支持 HTTP Range 时自动分段拉取，不必先下完整文件。
- **容错**：损坏的 PDF 会尝试恢复可用数据（页、内容、字体）后显示。
- **有限的批注写入**：支持添加一部分批注类型（官方 FAQ 明确"支持用一部分批注类型添加"），但不是完整编辑能力。
- **多环境可用**：npm 包、CDN、官方 release、源码构建；embed 到 Webpack 等打包流程（官方提供 `pdfjs-dist/webpack` 自动配置模块与示例）。

**不覆盖**：

- **不生成 PDF**：没有从 HTML/图片/数据生成 PDF 的能力。
- **不做 PDF 编辑**：不合并、不拆分、不裁剪、不重排、不改页面内容；批注只支持很有限的添加子集。
- **不做加密与签名**：不提供加密、解密、数字签名能力（加密 PDF 只是能靠口令"读"）。
- **不 OCR**：没有文字层的扫描件，它给不出文字。
- **不做版式语义重建**：不把 PDF 转成 HTML/Markdown/表格结构；它渲染画面、抽文本片段，语义要你自己拼。
- **不做服务端重型流水线**：Node 属"mostly / limited"支持，渲染还要额外 canvas 实现；大批量服务端处理请选更对口的工具。
- **不含字体与字体授权**：库提供标准字体数据与 cmap 查找，但不替你解决 PDF 内嵌字体缺失或字体授权问题。
- **不提供云服务**：本 Skill 不代理任何在线转换/渲染服务，不内嵌 Key，不代收费用。

## 依赖条件

| 项 | 要求 |
|---|---|
| 运行环境（浏览器） | 现代构建面向最新版浏览器（Firefox / Chrome 等）；需要旧环境时用带 `legacy` 后缀的构建，官方支持矩阵里旧环境包括 Firefox ESR+、Chrome 125+、Opera、Chromium 版 Edge，Safari 18+ 为"基本可用" |
| 运行环境（Node） | 官方支持矩阵中列为"mostly / limited"，**需要 Node.js 22+**；用 `legacy` 构建 |
| 安装方式 | `npm install pdfjs-dist`；或 CDN；或官方 release；或用 Rust 无关的 `npx gulp generic` 自行构建 |
| 渲染到图片（Node） | 需要额外的 canvas 实现（官方示例依赖仓库内的 canvas 包），可能有原生编译依赖；装不上就改用无头浏览器 |
| 资源文件 | CJK 等需要 `cmaps/`；标准字体数据在 `standard_fonts/`。两者都要显式传路径 |
| Worker | 浏览器里必须能用 Web Worker；打包工具需单独产出 worker bundle |
| 账号 / Key | **不需要**，无费用 |
| 授权注意 | 该库为第三方开源项目，**嵌入自己的站点时官方希望你不要原样照搬 viewer，应改造或基于其组件自建** |

## 已知限制

- **Node 支持是"能用但非一等公民"**：官方支持矩阵写明 Node.js 22+ 为 mostly / limited，部分特性缺失，渲染还要额外的原生 canvas 依赖。
- **只读为主**：编辑、生成、加密、签名都不在范围内；批注写入只覆盖部分类型。
- **版本必须成对**：主文件与 worker 版本不一致会直接抛错，这是设计上的保护。升级、缓存、CDN 混用是三个高发场景。
- **不同大版本之间 API 会破坏性变更**：官方采用语义化版本，**主版本升级意味着可能引入破坏性 API 变更**，次要版本才是向后兼容的新功能。生产项目请锁版本并读对应版本的文档。
- **内存开销与页面尺寸正相关，与页数无关**：文件越小、单页越小渲染越快（官方 FAQ 原话）；一次渲染大量页面会吃光内存。
- **跨域受同源策略限制**，需要 CORS 或代理；官方 demo viewer 在非自家域会拦截外部 `?file=`。
- **压缩有坑**：非官方压缩流程若开启高级选项会破坏代码，必须保留类名/函数名。
- **不解决字体缺失**：PDF 未内嵌字体时，只能靠标准字体数据与 cmap 兜底，个别文档仍会出现替代字体或字形偏差。

## 自检清单

执行前：

- [ ] 定位清楚：要的是 **API 自己搭界面**，还是**现成 viewer**；后者官方希望改皮或基于组件自建，别原样嵌入。
- [ ] 版本关系已确认：主文件与 worker 文件同版本；生产项目锁了 `pdfjs-dist` 版本。
- [ ] 环境选对构建：浏览器用现代构建；Node / 旧浏览器用 `legacy` 构建。
- [ ] worker 已配置（`GlobalWorkerOptions.workerSrc`），打包工具已单独产出 worker bundle。
- [ ] 需要渲染图片吗？Node 侧确认 canvas 实现可用；只用文本/元数据就别引入 canvas。
- [ ] 文档含 CJK 或非嵌入字体吗？是则配好 `cMapUrl` / `cMapPacked` / `standardFontDataUrl`。
- [ ] 输入可信吗？不可信就设 `isEvalSupported: false`。
- [ ] 跨域加载的话，目标服务器是否允许（CORS/代理）；大文件所在服务器是否支持 HTTP Range。

执行后：

- [ ] 渲染结果非空白，尺寸与方向正确（viewport 缩放、旋转都验一下）。
- [ ] 文本抽取结果抽查：中文有没有乱码，页序是否正确，文本片段顺序是否可用。
- [ ] 释放到位：每页 `cleanup()`，整份 `destroy()`；长时间会话下内存曲线平稳。
- [ ] 是"只渲染可见页"而不是一次全渲染；页数多的文档尤其要确认。
- [ ] 加密文档确认口令路径可用，失败时有明确错误处理而不是静默空白。
- [ ] 生产构建用的是压缩产物（官方 `npx gulp minified`），且页面只引 `pdf.js` 不重复引 worker。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/api-and-viewer.md` | API 与集成细节：`getDocument` 常用参数、页面对象方法、文本项字段怎么读、viewer 集成与自建、构建目标与产物说明、调试工具 |
| `README.md` | 包说明 |
| https://github.com/mozilla/pdf.js | 上游仓库（安装与完整文档以它为准） |
| https://mozilla.github.io/pdf.js/api/ | 官方 API 文档 |
| https://github.com/mozilla/pdf.js/wiki | 官方 FAQ 与集成说明（版本不匹配、支持矩阵、性能建议都在这里） |

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
