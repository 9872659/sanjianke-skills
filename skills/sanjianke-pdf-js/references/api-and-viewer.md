# PDF.js API 与集成细节

> 覆盖：`getDocument` 参数、文档/页面对象方法、文本项字段怎么读、viewer 集成与自建、构建目标与产物、调试工具。
> 参数与方法清单以官方 API 文档与官方 examples 为准；**主版本升级可能带来破坏性 API 变更**，用前对照你装的版本。

## 一、getDocument：常用加载参数

```js
import * as pdfjsLib from "pdfjs-dist";
const loadingTask = pdfjsLib.getDocument({ /* 参数 */ });
const pdf = await loadingTask.promise;
```

| 参数 | 作用 |
|---|---|
| `url` | 从地址加载（受同源策略约束；服务器支持 HTTP Range 时会自动分段取） |
| `data` | 直接给 `Uint8Array`（本地文件、内存数据、用户上传都走这个） |
| `password` | 加密 PDF 的口令 |
| `cMapUrl` / `cMapPacked` | CJK 等字符集映射数据的位置与是否压缩包（指向 `pdfjs-dist/cmaps/`） |
| `standardFontDataUrl` | 标准字体数据位置（指向 `pdfjs-dist/standard_fonts/`） |
| `isEvalSupported` | 设为 `false` 可关掉基于 `eval` 的加速路径，处理不可信文件时建议关闭 |

官方 Node 示例里实际用的是这一组：

```js
const loadingTask = getDocument({
  data,
  cMapUrl: "../../../node_modules/pdfjs-dist/cmaps/",
  cMapPacked: true,
  standardFontDataUrl: "../../../node_modules/pdfjs-dist/standard_fonts/",
});
```

加载任务对象本身有两个常用点：`loadingTask.promise`（拿到文档）和 `loadingTask.destroy()`（用完销毁）。

## 二、文档对象（PDFDocumentProxy）

官方示例里用到的：

```js
const pdfDoc = await loadingTask.promise;

pdfDoc.numPages                       // 页数
await pdfDoc.getPage(1)               // 取某一页（从 1 开始）
await pdfDoc.getMetadata()            // { info, metadata }：info 是文档信息字典，metadata 是 XMP
pdfDoc.canvasFactory                  // canvas 工厂（Node 渲染示例用它创建画布）
```

其他与"文档级信息"相关的常用方法（不同版本可能增删，按官方 API 文档核对）：`getOutline()`（书签/大纲）、`getDestinations()`、`getAttachments()`、`getData()`、`getFingerprints()`、`cleanup()`、`destroy()`。

**销毁别忘**：`loadingTask.destroy()` 会释放 worker 与相关资源；长时间运行的服务或单页应用里，不销毁会累积内存。

## 三、页面对象（PDFPageProxy）

```js
const page = await pdfDoc.getPage(1);

// 1) 尺寸与缩放
const viewport = page.getViewport({ scale: 1.5 });   // 还支持 rotation 等，详见官方文档
console.log(viewport.width, viewport.height);

// 2) 渲染到 canvas（必须 await）
const renderTask = page.render({
  canvasContext: canvas.getContext("2d"),
  viewport,
});
await renderTask.promise;

// 3) 取文本
const { items } = await page.getTextContent();

// 4) 批注、操作符列表（需要更底层处理时用）
const annotations = await page.getAnnotations();
const ops = await page.getOperatorList();

page.cleanup();   // 用完释放本页资源
```

**文本项（items）里有什么**：每个元素是一个文本片段，常用字段包括 `str`（字符串）、`dir`（书写方向）、`width` / `height`（尺寸）、`transform`（变换矩阵，用来算位置与字号）、`fontName`，以及 `hasEOL` 之类的行信息。

定位一个词的大致做法：取 `transform` 的第 5、6 个分量（水平/垂直位移）配合 `width`/`height`，再用同一个 `viewport` 做坐标变换——**必须和渲染用同一套 viewport**，否则高亮框会对不上。

## 四、渲染成图片（Node）

流程与官方示例一致：取页面 → 建 viewport → 用 `canvasFactory` 建画布 → `page.render` → `await` → 从 canvas 导出 PNG。

```js
const page = await pdfDoc.getPage(1);
const viewport = page.getViewport({ scale: 1.0 });
const canvasAndContext = pdfDoc.canvasFactory.create(viewport.width, viewport.height);

await page.render({ canvasContext: canvasAndContext.context, viewport }).promise;
fs.writeFileSync("output.png", canvasAndContext.canvas.toBuffer("image/png"));
page.cleanup();
```

要点：

- Node 侧需要一个可用的 canvas 实现（官方示例依赖仓库里的 canvas 包）。它有原生编译依赖，装不上就改走无头浏览器渲染。
- 只要文本和元数据时**完全不需要 canvas**，别为了抽文本引入原生依赖。

## 五、viewer：三种集成方式

### 1. 用官方预编译 viewer（最快）

下载官方 release，把 `build/` 与 `web/` 一起部署：

```
https://你的域名/web/viewer.html?file=<encodeURIComponent(PDF地址)>
```

- 想改默认打开的文档：改 `web/app_options.js` 里的 `defaultUrl`。
- 想"先不加载任何文件"：把 `defaultUrl` 设为空字符串，或用不带地址的 `?file=`。
- 官方明确希望：**嵌入自己站点时不要原样照搬，至少换个皮或在它基础上改**。

### 2. 在页面里手动控制 viewer

```js
// 用地址打开
PDFViewerApplication.open({ url: "/files/demo.pdf" });

// 用二进制打开（比 base64 更省内存；base64 需要先解码）
PDFViewerApplication.open({ data: new Uint8Array(arrayBuffer) });
```

### 3. 用 npm 包里的 viewer 组件自建界面

`pdfjs-dist` 包里除了核心库，还带 viewer 组件层（`web/` 目录下的 pdf_viewer 模块与样式）。适合"我要自己的工具栏/侧边栏/水印"这类需求。

**组件层的导出名与文件路径随版本变化**，务必以你安装的那一版 `node_modules/pdfjs-dist/` 目录结构与官方 `examples/` 为准；仓库里的示例可以用 `npx gulp dist-install` 生成本地 `pdfjs-dist` 后直接运行。

## 六、构建目标与产物

| 命令 | 产出 |
|---|---|
| `npx gulp server` | 本地开发服务器，访问 `http://localhost:8888/web/viewer.html`（还能看 `test/pdfs/?frame` 里的测试文件） |
| `npx gulp generic` | `build/generic/build/` 下的 `pdf.js` 与 `pdf.worker.js` |
| `npx gulp generic-legacy` | 同上，但面向旧浏览器 |
| `npx gulp minified` | 压缩版（官方用 Terser） |
| `npx gulp chromium` | Chromium 扩展，产出在 `build/chromium` |
| `npx gulp dist-install` | 在本仓库目录里生成并安装 `pdfjs-dist` 包（跑官方示例用） |

**两个文件的关系**：`pdf.js` 与 `pdf.worker.js` 都需要存在，但页面里只引 `pdf.js`——worker 由它自己加载。文件体积很大，生产环境要压缩（用官方 `minified` 任务；换别的压缩器必须保留原始类名/函数名）。

打包工具场景（如 Webpack）：官方 wiki 给的思路是把 worker 单独产出一个 bundle，再用 `GlobalWorkerOptions.workerSrc` 指过去；包里还提供 `pdfjs-dist/webpack` 模块做自动配置，仓库 `examples/webpack` 有完整示例。

## 七、环境支持矩阵（官方 FAQ）

| 环境 | 支持情况 |
|---|---|
| 现代构建 | 最新版 Firefox / Chrome 等 |
| `legacy` 构建 | Firefox ESR+、Chrome 125+、Opera、Chromium 版 Edge；Safari 18+ 为"基本可用"（个别特性缺失）；**Node.js 22+ 为"mostly / limited"** |

结论很直接：**Node 不是一等公民**，能用，但别把它当服务端重型渲染方案。

## 八、调试与排查工具

| 工具 | 用途 |
|---|---|
| 官方 PDF 调试器 | 浏览 PDF 内部结构（在线地址见下） |
| 搜 `pdfjsVersion` | 在 `pdf.js` / `pdf.worker.js` 文件里查实际版本号，排查版本不匹配 |
| 官方 API 文档 | `https://mozilla.github.io/pdf.js/api/` |
| 官方 examples 目录 | 仓库 `examples/`，含 Node 与 Webpack 用法的可运行示例 |
| 在线交互示例 | 官方文档站的 interactive examples，可直接在浏览器里试 API |

## 九、性能与内存：官方给的数字与建议

- 单页 Letter 尺寸在 96 DPI 下是 **816×1056 像素**，canvas 占用约 `816×1056×4 ≈ 3.5MB`；HiDPI（`devicePixelRatio = 2`）再乘 4，**单页可能到 14MB**。
- 因此官方明确不建议"一次性渲染全部页面"，推荐**只创建和渲染可见页**——官方 demo viewer 就是这么做的。
- 渲染速度与**文件大小、单页大小**相关，与页数无关（官方原话）。
- 优化 PDF 的方向：扫描图降到约 150 DPI 够屏幕用、彩色照片优先 JPEG/RGB、避免复杂混合与透明、避免生成器产出大量无意义小图、使用 web 优化/线性化输出、不要产出不符合 PDF 规范的损坏文件。
- 服务器支持 HTTP Range 时，PDF.js 会自动只取渲染可见页所需的部分——这是"首屏快"的关键，值得在服务端确认。

## 十、容错与不可信输入

- **损坏 PDF**：官方 FAQ 明确会尝试恢复可用数据（页、内容、字体）后显示。恢复结果不保证正确，生产链路里要做好失败兜底。
- **不可信 PDF**：关掉 `isEvalSupported`；只渲染需要的页；处理完及时 `cleanup()` / `destroy()`；跨域来源要确认对方可信。
- **加密 PDF**：只支持用口令"读"，不涉及解密导出或移除保护。
