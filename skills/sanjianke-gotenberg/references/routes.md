# 路由与表单字段速查

这份文件是 `SKILL.md` 的展开。字段名与路由路径来自官方文档（gotenberg.dev/docs），版本以 Gotenberg 8.x 为准；升级大版本前请对照官方文档复核。

**通用约定**

- 所有路由都是 `POST`，请求体 `multipart/form-data`，响应的 body 就是文件本身（不是 JSON 包裹的 base64）。
- 文件字段统一叫 `files`。同一请求里重复多次 `--form files=@...` 即可上传多个文件。
- 两个可选请求头：
  - `Gotenberg-Output-Filename`：设置响应 `Content-Disposition` 里的文件名，**扩展名由 Gotenberg 追加**。
  - `Gotenberg-Trace`：自定义请求 ID，用于在日志里串起一次调用。
- 成功返回 `200`；参数错 `400`；主页面或资源命中失败状态码 `409`；引擎不可用 / 队列满 `503`。

---

## 一、转 PDF（Chromium）

| 任务 | 路由 |
|---|---|
| 按 URL 转 | `/forms/chromium/convert/url` |
| 转 HTML 文件 | `/forms/chromium/convert/html` |
| 转 Markdown | `/forms/chromium/convert/markdown` |

来源字段：`url`（`convert/url` 必填，**`file://` 会返回 400**），或 `files`（HTML / Markdown 及其引用的本地资源）。

### 页面布局

| 字段 | 说明 | 默认 |
|---|---|---|
| `paperWidth` / `paperHeight` | 纸张宽高，支持 `in` / `pt` / `cm`，不写单位按英寸 | `8.5` / `11` |
| `marginTop` / `marginBottom` / `marginLeft` / `marginRight` | 四边页边距 | `0.39` |
| `landscape` | 横版 | `false` |
| `scale` | 页面缩放系数 | `1.0` |
| `singlePage` | 全部内容塞进一张超长页；**开启后会覆盖 `paperHeight` 与 `nativePageRanges`** | `false` |
| `preferCssPageSize` | 优先用 CSS `@page` 定义的尺寸，而不是接口参数 | `false` |

常用纸张（英寸）：A4 `8.27 x 11.7`、A3 `11.7 x 16.54`、Letter `8.5 x 11`、Legal `8.5 x 14`。

### 背景与媒体类型

| 字段 | 说明 | 默认 |
|---|---|---|
| `printBackground` | 保留背景色与背景图 | `false` |
| `omitBackground` | 去掉默认白底（允许透明） | `false` |
| `emulatedMediaType` | `screen` 或 `print` | `print` |
| `emulatedMediaFeatures` | JSON 数组，覆盖 CSS 媒体特性 | 无 |

背景的最终结果取决于三者组合：

| `printBackground` | `omitBackground` | HTML 有背景 CSS | 结果 |
|---|---|---|---|
| `false` | 任意 | 任意 | 无背景 |
| `true` | 任意 | 有 | 用 HTML 的 CSS 背景 |
| `true` | `true` | 无 | 透明 |
| `true` | `false` | 无 | 白色（默认） |

`emulatedMediaFeatures` 写法（可以强推暗色模式）：

```
--form 'emulatedMediaFeatures=[{"name":"prefers-color-scheme","value":"dark"},{"name":"prefers-reduced-motion","value":"reduce"}]'
```

### 等待动态内容

三种策略，优先级从高到低：

| 字段 | 语义 | 备注 |
|---|---|---|
| `waitForExpression` | 页面内 JS 表达式返回 `true` 时开转；返回 Promise 会被 await | 最稳，推荐 |
| `waitForSelector` | CSS 选择器出现匹配元素时开转 | 适合 React / Vue 这类 SPA |
| `waitDelay` | 固定等待时长，如 `5s`、`500ms` | 最粗暴：快了浪费时间，慢了出半截 |

配合写法——页面自己打标记：

```js
window.status = "loading"
fetchData().then(() => {
  renderCharts()
  window.status = "ready"
})
```

```bash
--form 'waitForExpression=window.status === "ready"'
```

### 网络与请求头

| 字段 | 说明 |
|---|---|
| `cookies` | JSON 数组，键为 `name` / `value` / `domain`（必填）、`path` / `secure` / `httpOnly` / `sameSite`（可选）。Cookie 随请求超时一起过期 |
| `extraHttpHeaders` | JSON 对象，作用于**每个**浏览器请求（含图片、样式、脚本） |
| `userAgent` | 覆盖默认 UA |
| `failOnHttpStatusCodes` | 主页面命中这些码就返回 409，默认 `[499,599]`，用 X99 记法表示区间 |
| `failOnResourceHttpStatusCodes` | 任一资源命中就 409，默认不启用 |
| `ignoreResourceHttpStatusDomains` | 把这些域名排除出资源状态码检查，如 `["sentry-cdn.com"]` |

`extraHttpHeaders` 支持用 `;scope=` 把某个头限定到匹配的 URL：

```
--form-string 'extraHttpHeaders={"X-Internal-Token":"secret-123;scope=.*\\.internal\\.api"}'
```

单个请求最多 64 个头，单个 scope 正则最长 1024 字符。**别写嵌套量词**（如 `(a+)+`），回溯会吃满匹配时间预算，超预算后剩余 scope 头就不再发送。

---

## 二、截图

| 任务 | 路由 |
|---|---|
| 截图 URL | `/forms/chromium/screenshot/url` |
| 截图 HTML | `/forms/chromium/screenshot/html` |
| 截图 Markdown | `/forms/chromium/screenshot/markdown` |

返回 PNG。等待策略、Cookie、请求头等字段与转换路由共用。

---

## 三、转 PDF（LibreOffice）

| 任务 | 路由 |
|---|---|
| Office 文档转 PDF | `/forms/libreoffice/convert` |

覆盖 `.docx` / `.xlsx` / `.pptx` 等 100+ 格式。可以一次上传多个文件，**合并成一个 PDF**。要拆分出多个结果文件时另有 `splitMode` 相关字段，具体名称与取值以官方 LibreOffice 路由页面为准。

该模块的并发上限由 `--libreoffice-max-concurrency` 相关配置与独占锁决定：一个实例同一时刻只能跑一个转换。

---

## 四、PDF 后处理（PDF Engines）

| 任务 | 路由 |
|---|---|
| 合并 | `/forms/pdfengines/merge` |
| 拆分 | `/forms/pdfengines/split` |
| 转 PDF/A 或 PDF/UA | `/forms/pdfengines/convert` |
| 读元数据 | `/forms/pdfengines/metadata/read` |
| 写元数据 | `/forms/pdfengines/metadata/write` |
| 读书签 | `/forms/pdfengines/bookmarks/read` |
| 写书签 | `/forms/pdfengines/bookmarks/write` |
| 内嵌附件 | `/forms/pdfengines/embed` |
| Factur-X / ZUGFeRD | `/forms/pdfengines/factur-x` |
| 扁平化表单与批注 | `/forms/pdfengines/flatten` |
| 水印（垫在内容下方） | `/forms/pdfengines/watermark` |
| 图章（盖在内容上方） | `/forms/pdfengines/stamp` |
| 旋转 | `/forms/pdfengines/rotate` |
| 加密 | `/forms/pdfengines/encrypt` |

**关键设计**：转换类路由（Chromium / LibreOffice）也接受上述大部分 PDF 引擎特性，可以写在**同一个请求**里。所以「转 PDF + 加水印 + 压缩 + 设密码」是一次调用而不是四次。各能力的详细字段请查对应路由页面。

### 合并 / 拆分要点

`/forms/pdfengines/merge`

- `files`：待合并的 PDF。
- 合并顺序 = **文件名（数字优先，再字母）**，不是上传顺序。8.37.0 起同名文件会全部保留并按上传顺序合并。
- `autoIndexBookmarks=true`：抽取各文件的原有书签，并按其在合并文档中的位置**平移页码**。
- `titleBookmarks=true`：为每份输入生成一个书签（标题取 `Title` 元数据，没有就用文件名），指向该文件首页，原有书签嵌套其下——等于自动生成目录。
- `bookmarks`：JSON。给**列表**时直接应用到最终 PDF；给**文件名→书签**的**映射**时，先按文件平移页码再合并。可与 `autoIndexBookmarks` 同时用：映射过的文件尊重你的设置，其余自动重算。

`/forms/pdfengines/split`

- `splitMode`（必填）：`intervals` 或 `pages`。
- `splitSpan`（必填）：`intervals` 下是每份的页数（如 `2`）；`pages` 下是页范围（如 `1-3`）。
- `splitUnify`：仅 `pages` 模式有效。`true` 时把抽出的页合成一个 PDF，`false` 时每个范围一个文件。
- **`pages` 模式下 Gotenberg 不校验 `splitSpan` 语法**，原样透传给底层引擎，合法写法取决于当前生效的引擎：
  - pdfcpu（默认）→ 见 pdfcpu `/trim` 文档
  - QPDF → 见 QPDF page-ranges 文档
  - PDFtk → 见 PDFtk `cat` 操作文档
- 输出通常是 ZIP；当单文件 + `pages` 模式 + `splitUnify=true` 时输出单个 PDF。

### 通用后处理字段（在转换路由与后处理路由上都能用）

| 字段 | 说明 |
|---|---|
| `metadata` | JSON，注入 XMP 元数据（Author / Title / Copyright / Keywords 等）。**键不能与 ExifTool 选项同名**（`csv` / `json` / `o` / `config` 会 400），要写得加分组前缀，如 `XMP:csv` |
| `embeds` | 把外部文件塞进 PDF 容器；配 `embedsMetadata` 指定每个附件的 `mimeType` 与 `relationship`（`Source` / `Data` / `Alternative` / `Supplement` / `Unspecified`） |
| `facturxXml` + `facturxConformanceLevel` | 生成 Factur-X 电子发票，两者必须成对出现。级别：`MINIMUM` / `BASIC WL` / `BASIC` / `EN 16931` / `EXTENDED` / `XRECHNUNG`；另有 `facturxDocumentType`（默认 `INVOICE`）与 `facturxVersion`（默认 `1.0`） |
| `flatten=true` | 把表单域、批注合并进页面内容，变成不可编辑 |
| `watermarkSource` / `watermarkExpression` / `watermarkPages` / `watermarkOptions` | 水印，垫在内容下方。来源 `text` / `image` / `pdf`；`image` 与 `pdf` 需另传 `watermark` 文件。可重复多次，按序应用 |
| `stampSource` / `stampExpression` / `stampPages` / `stampOptions` | 图章，盖在内容上方。规则同上，文件字段是 `stamp` |
| `rotateAngle` / `rotatePages` | 旋转，角度只接受 `90` / `180` / `270`；`rotatePages` 形如 `1-3, 5`，留空即全篇 |
| `optimizeImages` / `imageQuality` | 把图片重编码为 JPEG 以减小体积；质量为 1–100，默认 `80`。文字、矢量、字体、结构不动 |
| `pdfa` / `pdfuaboolean` | 归档 / 无障碍合规。`pdfa` 取值 `PDF/A-1b` / `PDF/A-2b` / `PDF/A-3b` |

`watermarkOptions` / `stampOptions` 的可选键取决于当前生效引擎（默认 pdfcpu），常见有 `font`、`points`（字号）、`color`、`rotation`、`opacity`、`scale`、`offset`：

```json
{"font": "Helvetica", "points": 48, "color": "#808080", "rotation": 45, "opacity": 0.15}
```

`watermarkExpression` / `stampExpression` **不能引用任意文件系统路径**，写了会 400。

---

## 五、系统与运维路由

| 任务 | 路由 | 说明 |
|---|---|---|
| 健康检查 | `/health` | 进程级探活；**不检查 Chromium / LibreOffice 是否可用** |
| 版本 | `/version` | 取当前版本号 |
| 运行时配置 | `/debug` | 必须先用 `--api-enable-debug-route` 打开 |
| 异步处理 | Webhook | 见 `references/operations.md` |
| 远端输入 | `downloadFrom` | 让服务自己去远端 URL 拉输入文件，见 `references/operations.md` |

Prometheus 指标默认在 `/prometheus/metrics`；从 8.29.0 起该模块**已弃用**，官方建议改用 OpenTelemetry。

---

## 六、引擎分工表（决定某条特性能不能用）

| 特性 | ExifTool | PDFtk | pdfcpu | QPDF | UNO |
|---|:--:|:--:|:--:|:--:|:--:|
| 合并 | ✗ | ✓ | ✓ | ✓ | ✗ |
| 拆分 | ✗ | ✓ | ✓ | ✓ | ✗ |
| 扁平化 | ✗ | ✗ | ✗ | ✓ | ✗ |
| PDF/A 与 PDF/UA 转换 | ✗ | ✗ | ✗ | ✗ | ✓ |
| 优化图片 | ✗ | ✗ | ✓ | ✗ | ✗ |
| 读元数据 | ✓ | ✗ | ✗ | ✗ | ✗ |
| 写元数据 | ✓ | ✗ | ✗ | ✗ | ✗ |
| 加密 | ✗ | ✓ | ✓ | ✓ | ✗ |
| 内嵌文件 | ✗ | ✗ | ✓ | ✗ | ✗ |
| Factur-X（XMP） | ✗ | ✗ | ✗ | ✓ | ✗ |
| 水印 | ✗ | ✓ | ✓ | ✗ | ✗ |
| 图章 | ✗ | ✓ | ✓ | ✗ | ✗ |
| 读书签 | ✗ | ✗ | ✓ | ✗ | ✗ |
| 写书签 | ✗ | ✗ | ✓ | ✗ | ✗ |
| 旋转 | ✗ | ✓ | ✓ | ✗ | ✗ |

默认链（可用 `--pdfengines-*-engines` 调整顺序，留空表示全部）：

| 特性 | 默认顺序 |
|---|---|
| 合并 | `qpdf,pdfcpu,pdftk` |
| 拆分 | `pdfcpu,qpdf,pdftk` |
| 扁平化 | `qpdf` |
| 转换（PDF/A） | `libreoffice-pdfengine` |
| 优化图片 | `pdfcpu` |
| 读 / 写元数据 | `exiftool` |
| 加密 | `qpdf,pdftk,pdfcpu` |
| 内嵌 | `pdfcpu` |
| 水印 / 图章 | `pdfcpu,pdftk` |
| 旋转 | `pdfcpu,pdftk` |

注意差异：**PDFtk 与 QPDF 的拆分只支持 `pages` 模式且必须 unify**；**PDFtk 加密要求用户密码与所有者密码不同**，且只到 AES-128，而其他引擎支持 AES-256；**QPDF 逐条尊重文档权限，pdfcpu 则是一刀切**（限制任意一条权限就等于全禁）。
