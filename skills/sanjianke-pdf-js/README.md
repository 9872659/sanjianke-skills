# 三剪客 · PDF 解析与渲染 Skill

用 JavaScript 打开 PDF：读元数据、大纲、文本（带坐标）、批注，把页面渲染到 canvas 做预览/缩略图，或在网页里提供一套完整的阅读界面。解析与渲染默认跑在 Web Worker，服务器支持 HTTP Range 时自动按需分段拉取。

---

## 前置条件

- **先分清两条路**：用 API 自己搭界面（`pdfjs-dist`），还是用官方预编译 release 里的现成 viewer（`web/viewer.html`）。两条路的配置方式完全不同。
- **版本必须成对**：pdf.js 主文件与 worker 文件版本不一致会直接抛错。生产项目请锁定 `pdfjs-dist` 版本。
- **环境选对构建**：浏览器用现代构建（`build/pdf.mjs`）；Node 与旧浏览器用 `legacy` 构建（`legacy/build/pdf.mjs`）。官方支持矩阵里 Node.js 22+ 为"mostly / limited"。
- **Node 渲染成图片需要额外的 canvas 实现**（有原生编译依赖）；只抽文本与元数据则不需要 canvas。
- **含 CJK 或非嵌入字体的 PDF**，要显式配置 `cMapUrl` / `cMapPacked` / `standardFontDataUrl`，否则会乱码或缺字。
- 不需要账号、不需要 API Key、无费用。

---

## 使用

```bash
# 1. 装（集成到项目）
npm install pdfjs-dist
# Webpack 场景官方 wiki 的写法：npm install pdfjs-dist --save-dev

# 2. 要现成 viewer 就直接下官方 release，把 build/ 与 web/ 一起部署，然后访问：
#    https://你的域名/web/viewer.html?file=<encodeURIComponent(PDF地址)>

# 3. 要改库本身或自建产物（克隆源码后）
npm install
npx gulp server            # 开发服务器 http://localhost:8888/web/viewer.html
npx gulp generic           # 产出 build/generic/build/pdf.js 与 pdf.worker.js
npx gulp generic-legacy    # 需要旧浏览器时用
npx gulp minified          # 压缩版
npx gulp chromium          # Chromium 扩展
npx gulp dist-install      # 在本目录生成并安装 pdfjs-dist（跑官方示例用）
```

浏览器里渲染一页：

```js
import * as pdfjsLib from "pdfjs-dist";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.mjs",
  import.meta.url
).toString();

const pdf = await pdfjsLib.getDocument({ url: "/files/demo.pdf" }).promise;
const page = await pdf.getPage(1);
const viewport = page.getViewport({ scale: 1.5 });

const canvas = document.getElementById("c");
canvas.width = viewport.width;
canvas.height = viewport.height;

await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
page.cleanup();
```

Node 里抽元数据与文本（官方示例写法）：

```js
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

const loadingTask = getDocument({ url: "demo.pdf" });
const pdfDoc = await loadingTask.promise;

const { info, metadata } = await pdfDoc.getMetadata();
for (let i = 1; i <= pdfDoc.numPages; i++) {
  const p = await pdfDoc.getPage(i);
  const { items } = await p.getTextContent();
  console.log(items.map((item) => item.str).join(" "));
  p.cleanup();
}
await loadingTask.destroy();
```

加载参数、页面对象方法、viewer 集成、构建产物、性能与内存建议见 `references/api-and-viewer.md`。

---

## 依赖

| 项 | 说明 |
|---|---|
| 包名 | `pdfjs-dist`（npm）；也可用 CDN（jsDelivr / cdnjs / unpkg）或官方 release |
| 浏览器支持 | 现代构建面向最新版浏览器；`legacy` 构建覆盖 Firefox ESR+、Chrome 125+、Opera、Chromium 版 Edge，Safari 18+ 基本可用 |
| Node 支持 | 官方列为 mostly / limited，需要 Node.js 22+，用 `legacy` 构建 |
| 渲染到图片 | 浏览器用 canvas；Node 需额外 canvas 实现（原生编译依赖） |
| 资源文件 | `cmaps/`（CJK 等）与 `standard_fonts/`，需显式传路径 |
| 构建链 | 源码构建用仓库自带 gulp 任务；产物必须压缩且保留原始类名/函数名 |
| 账号 / Key | 不需要 |

---

## 安全

- 不内嵌任何密钥。
- **PDF 是不可信输入**：加载来路不明的文件时建议设 `isEvalSupported: false`，并只渲染需要的页面。
- 纯前端解析的好处是文件不必上传到你的服务器，但同样意味着没有服务端校验兜底；对外提供"预览任意 PDF"的功能时，注意跨域与来源限制。
- **跨域加载受同源策略限制**，需要目标服务器开 CORS 或自己域内做代理；官方 demo viewer 在非自家域会主动拦截外部 `?file=`，这是防内容伪装的设计。
- 资源释放要及时：每页 `cleanup()`、整份 `destroy()`；不要一次渲染大量页面（单页在高分屏下可能占用十几 MB 内存）。
- 本 Skill 不代理任何在线转换/渲染服务，不转发请求，不代收费用。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pdf.js`
- 仓库：https://github.com/mozilla/pdf.js

---

## 许可证

MIT，见 `LICENSE.md`。

---

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
