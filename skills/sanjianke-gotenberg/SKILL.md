---
name: sanjianke-gotenberg
slug: sanjianke-gotenberg
displayName: 三剪客 · 文档转换 HTTP API
description: "把网页、HTML、Markdown、Office 文档批量转成 PDF，并顺带做合并、拆分、水印、加密与元数据读写的自托管 HTTP 服务。 遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Gotenberg 是一个 Docker 里跑起来的文档转换 API：发 multipart/form-data，拿回 PDF。它把 Chromium、LibreOffice 和一整套 PDF 引擎打包好，你不用自己装浏览器、字体和 Office 运行库，一个 curl 就能出 PDF。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - PDF
  - 文档处理
  - Docker
  - 服务端
---

# 三剪客 · 文档转换 HTTP API

你要把一批网页、HTML 模板或 Office 文档变成 PDF，自己装 Headless Chromium + LibreOffice + 字体那一套的代价，往往比转换本身大得多：中文字体缺失导致变成方块、并发跑崩、Office 转换卡死、PDF 还得再找工具合并加密。Gotenberg 把这些全部收进一个 Docker 镜像，对外只露一个 HTTP 接口——`POST` 一个 `multipart/form-data`，文件流直接回来。

它的接口风格很统一：转化类走 `/forms/chromium/*` 和 `/forms/libreoffice/convert`，PDF 后处理走 `/forms/pdfengines/*`（合并、拆分、旋转、水印、加密、元数据、书签、PDF/A）。而且这些后处理能力可以和转换写在**同一个请求**里，省掉一次上传下载。默认监听 `3000` 端口，**默认没有任何鉴权**，这是它最需要你留意的设计前提。

**上游项目**：`Gotenberg`　**仓库**：https://github.com/gotenberg/gotenberg

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（必需） | 调用本机或内网的 Gotenberg（默认 `http://localhost:3000`）；转 URL / 截图时由 Gotenberg 自己出网访问目标站点 |
| 读取文件 | 是 | 读取待转换的 HTML / Markdown / Office / PDF 文件，以及 Logo、水印图、附件等 |
| 写入文件 | 是 | 把返回的 PDF / ZIP / PNG 落盘；`Gotenberg-Output-Filename` 只影响响应头里的文件名，不决定本地存哪 |
| 凭证 | 视需要 | 仅当服务端开了 Basic Auth / OIDC 才需要；用户名密码走服务端的 `GOTENBERG_API_BASIC_AUTH_USERNAME` / `_PASSWORD` 环境变量，**不要写进请求脚本** |
| 子进程 / 后台常驻 | 是 | `docker run` 拉起并常驻一个 Gotenberg 容器；批量任务建议放后台跑 |

**密钥与费用**：本 Skill 不内嵌任何密钥、不代理请求、不代收费用。Gotenberg 是自托管软件，没有云端账号和计费，成本全部落在你跑容器的那台机器上。容器里的 Chromium 与 LibreOffice 会消耗可观内存，请按容量规划。

## 什么时候用 / 不用

**该用**：

- 「把这份报价单 HTML 模板转成 PDF」——`/forms/chromium/convert/html`。
- 「把这个网页存成 PDF，要等图表加载完」——`/forms/chromium/convert/url` 配 `waitForExpression` 或 `waitForSelector`。
- 「把这个 docx / xlsx / pptx 转成 PDF」——`/forms/libreoffice/convert`。
- 「把这几份 PDF 合成一份，并且加上书签目录」——`/forms/pdfengines/merge` 配 `titleBookmarks=true`。
- 「这份合同要拆页、要加水印、要设密码」——`/forms/pdfengines/split`、`/watermark`、`/encrypt`。
- 「转完顺手压一下体积」——同一个请求里带 `optimizeImages=true`。
- 「要归档，得是 PDF/A」——同一个请求里带 `pdfa=PDF/A-3b`。
- 「量很大，不想每次同步等」——Webhook 异步模式。


**不该用**：

- 要从 PDF 里抽文字、表格，或把 PDF / HTML 转成 Markdown —— 它的方向是单向「进 PDF」；取数请用 pdfplumber 或 PyMuPDF。
- 扫描件要出文字 —— 它不做 OCR，先过 OCRmyPDF / tesseract 再来。
- 要把 PDF 转成 docx —— 输出侧只有 PDF 与 PNG 截图。
- 想要一个自带鉴权、TLS、高可用的托管服务 —— 官方镜像默认无鉴权、不含 TLS，直连公网等于把未授权转换接口送出去。
- 要在单实例上追高吞吐 —— LibreOffice 因独占锁不能并行，Chromium 单实例上限 6 并发，超了只能排队，提吞吐靠加实例。
- 排版要精确复现微软核心字体 —— 授权原因镜像不随附，只能自建镜像并接受 EULA。
- 想在 Windows / macOS 上直接装个包跑起来 —— 唯一部署方式是 Docker。
- 需要默认就 PDF/A 又同时要加密 —— PDF/A 与加密互斥，且 PDF/A 走 LibreOffice 二次处理会更慢，还会覆盖创建/修改时间与关键词。

## 安装

官方只通过 Docker 分发，没有 `pip` / `npm` 这种包管理器安装方式。

```bash
# 完整版：Chromium + LibreOffice + PDF 引擎
docker run --rm -p "3000:3000" gotenberg/gotenberg:8

# 更安全的绑法：只监听本机回环，不暴露到局域网
docker run --rm -p "127.0.0.1:3000:3000" gotenberg/gotenberg:8

# 追一个参数：把请求超时从默认 30s 放宽到 120s
docker run --rm -p "3000:3000" gotenberg/gotenberg:8 \
  gotenberg --api-timeout=120s
```

三个镜像变体按需选，体积差得不少：

| 镜像 | 含什么 |
|---|---|
| `gotenberg/gotenberg:8` | 全部：Chromium、LibreOffice、PDF 引擎 |
| `gotenberg/gotenberg:8-chromium` | 只有 Chromium 与 PDF 引擎（约小 30%），**不能转 Office** |
| `gotenberg/gotenberg:8-libreoffice` | 只有 LibreOffice 与 PDF 引擎（约小 40%），**不能转 URL/HTML/Markdown、不能截图** |

Docker Compose（同网络内的其他服务用 `gotenberg:3000` 访问）：

```yaml
services:
  gotenberg:
    image: gotenberg/gotenberg:8
    ports:
      - "127.0.0.1:3000:3000"
```

改配置有两个等价入口：**覆盖 command**（`gotenberg --flag=value`）或**环境变量**（`-e API_TIMEOUT=120s`）。注意是覆盖 command，**不要覆盖 entrypoint**。

## 常用操作

**1. URL 转 PDF**（官方示例，可直接跑）

```bash
curl \
  --request POST http://localhost:3000/forms/chromium/convert/url \
  --form url=https://sparksuite.github.io/simple-html-invoice-template/ \
  -o invoice.pdf
```

**2. HTML 转 PDF，指定 A4 与页边距**

```bash
curl --request POST http://localhost:3000/forms/chromium/convert/html \
  --form files=@index.html \
  --form files=@style.css \
  --form paperWidth=8.27 --form paperHeight=11.7 \
  --form marginTop=0.4 --form marginBottom=0.4 \
  --form marginLeft=0.4 --form marginRight=0.4 \
  --form printBackground=true \
  -o out.pdf
```

HTML 里引用的本地静态资源，必须**一起作为同名文件上传**（同一请求里多次 `--form files=@...`），Gotenberg 会在同一目录下解析相对路径。

**3. Office 文档转 PDF**

```bash
curl --request POST http://localhost:3000/forms/libreoffice/convert \
  --form files=@report.docx \
  --form landscape=false \
  -o report.pdf
```

**4. 合并多份 PDF 并自动生成书签目录**

```bash
curl --request POST http://localhost:3000/forms/pdfengines/merge \
  --form files=@1_pdf.pdf \
  --form files=@2_pdf.pdf \
  --form files=@3_pdf.pdf \
  --form titleBookmarks=true \
  -o merged.pdf
```

合并顺序是**按文件名的字母数字序**，不是上传顺序（从 8.37.0 起，同名文件才改为按上传顺序保留全部）。想让顺序可控，就把文件命名成 `01_xxx.pdf`、`02_xxx.pdf` 这种前缀。

**5. 按间隔拆页，输出 ZIP**

```bash
curl --request POST http://localhost:3000/forms/pdfengines/split \
  --form files=@book.pdf \
  --form splitMode=intervals \
  --form splitSpan=1 \
  -o pages.zip
```

**6. 转 PDF 的同时加水印、加密、压缩**（一次请求做完，省一轮上传下载）

```bash
curl --request POST http://localhost:3000/forms/chromium/convert/url \
  --form url=https://example.com \
  --form watermarkSource=text \
  --form watermarkExpression=CONFIDENTIAL \
  --form 'watermarkOptions={"opacity":0.25,"rotation":45}' \
  --form optimizeImages=true --form imageQuality=80 \
  --form userPassword=user --form ownerPassword=owner \
  -o out.pdf
```

**7. 探活与版本**（部署后第一件事）

```bash
curl http://localhost:3000/health
curl http://localhost:3000/version
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| PDF 里中文全是方块或空白 | 镜像自带 Noto CJK，但**不含微软核心字体**（Arial / Times New Roman / Calibri）；网页指定了这些字体又没嵌入 | 模板 CSS 里改用 Liberation / Carlito / Caladea 这些度量兼容的替代字体，或自建镜像装 `ttf-mscorefonts-installer`（需接受微软 EULA） |
| PDF 出来和浏览器看到的不一样：背景没了、导航栏还在 | Chromium 默认用 **`print` 媒体类型**渲染 | 要还原屏幕效果就传 `emulatedMediaType=screen`；背景色要传 `printBackground=true` |
| 页面内容空白或截断 | Chromium 只截取**当前已渲染**的 DOM，JS 还没跑完就出图了 | 别用 `waitDelay` 硬等；优先 `waitForSelector=#app-ready` 或 `waitForExpression='window.status === "ready"'` |
| URL 转换返回 `400` | `file://` 协议的 URL 被禁止 | 本地文件走 `/forms/chromium/convert/html` 上传，不要用 `convert/url` 传 `file://` |
| 转 PDF 时图片/样式丢失 | HTML 里引用的本地资源没有随请求上传 | 把 HTML 和它引用的 CSS、图片、字体一起 `--form files=@...` 传上去，保持相对路径不变 |
| 请求 30 秒后就失败 | `--api-timeout` 默认 **30s**，Office 大文档和慢站点很容易超 | 启动时加 `--api-timeout=120s`；同时同步放大 `--gotenberg-graceful-shutdown-duration`，否则异步任务会被关停打断 |
| 高并发下大量请求超时 | Chromium 单实例最多 6 个并发，LibreOffice 因为独占锁**完全不能并行** | 增加 Gotenberg 容器实例横向扩，而不是一味调大并发参数；LibreOffice 任务串行排队是设计如此 |
| 转了 Office 报「feature unavailable」 | 用了 `:8-chromium` 变体，它**不含 LibreOffice** | 换回完整版 `gotenberg/gotenberg:8` 或 `:8-libreoffice` |
| 输出文件名不受控 | `Gotenberg-Output-Filename` 只设置**响应头里的附件名**，扩展名由 Gotenberg 自己追加 | 本地落盘路径由你 `curl -o` 决定；不要指望这个头能改磁盘路径 |
| 合并出来的页序不对 | 合并按**文件名排序**，不按上传顺序 | 上传前把文件名加 `01_` `02_` 数字前缀 |
| `metadata` 写入报 400 | 键名和 ExifTool 的选项名撞了（如 `csv`、`json`、`o`、`config`） | 加分组前缀写成 `XMP:csv` 这种形式 |
| 同时要 PDF/A 又要加密，报 400 | PDF/A 与加密**互斥** | 二选一；要附件就选 PDF/A-3b（1b / 2b 不支持附件） |
| 服务被人扫到并滥用 | 默认**没有任何鉴权**，且 `-p 3000:3000` 默认对外网开放 | 绑 `127.0.0.1:3000:3000`；必须对外时开 `--api-enable-basic-auth` 或 OIDC，并在前面加反代与限流 |

## 能力边界

**覆盖**：

- **转 PDF**：URL、HTML（含本地静态资源）、Markdown、Office 文档（`.docx` / `.xlsx` / `.pptx` 等 100+ 格式）。
- **截图**：URL / HTML / Markdown 三种来源的页面截图。
- **PDF 后处理**：合并、拆分、旋转、扁平化表单、加密、优化图片、水印、图章、内嵌附件、读/写元数据、读/写书签、Factur-X / ZUGFeRD 电子发票、PDF/A（1b/2b/3b）与 PDF/UA 转换。
- **渲染控制**：纸张尺寸与四边页边距、横竖版、缩放、单页长图、`preferCssPageSize`、`printBackground` / `omitBackground`、`emulatedMediaType`、`emulatedMediaFeatures`（如强制暗色）、Cookie 与自定义请求头（支持按正则 scope 限定域名）、User-Agent、失败状态码白名单。
- **等待策略**：`waitDelay`（定时）、`waitForSelector`（等元素）、`waitForExpression`（等 JS 表达式，支持 Promise）。
- **运维**：`/health`、`/version`、`/debug`（需开启）、Webhook 异步模式、`downloadFrom` 从远端 URL 拉输入、Prometheus / OpenTelemetry 指标、Basic Auth 与 OIDC。

**不覆盖**：

- **不做 OCR**。扫描件 PDF 进去还是扫描件，它只搬页面内容，不识别文字。要 OCR 请另配 tesseract 之类的方案。
- **不做 PDF 正文提取**。它不把 PDF 转成文本、Markdown 或结构化数据，方向是单向的「进 PDF」。PDF 取数请用 pdfplumber 或 PyMuPDF。
- **不是通用文档转换器**。输出侧只出 PDF（以及截图出 PNG）；不能把 PDF 转成 docx、不能 HTML 转 Markdown。
- **不含任何云端服务**。没有官方 SaaS，没有 API Key 体系，全部自己部署。
- **不内置高可用与持久化**。官方 Compose 样例里没有 TLS、没有认证、没有副本与备份，这些都是你的事。
- **不提供反爬对抗**。转 URL 就是普通浏览器访问，目标站封了就是封了。
- 本 Skill 内不含任何可复制的第三方源码，正文为原创整理，仅引用接口路径、参数名、许可证等事实性信息。

## 依赖条件

- **Docker**：Docker Engine 或 Docker Desktop。这是唯一的部署方式。
- **端口**：宿主 `3000` 空闲（或你映射成别的端口）。
- **内存**：官方建议 Kubernetes 场景**至少 512Mi 内存 + 0.2 CPU**；Cloud Run 建议至少 1Gi 才顺畅。实际跑 Chromium 转复杂页面时给到 1–2GB 更稳。
- **权限**：镜像以非 root 用户 `gotenberg`（UID/GID **1001**）运行；从 8.21.0 起也支持任意 UID（OpenShift）。K8s 里设 `runAsUser: 1001`、`allowPrivilegeEscalation: false`、`readOnlyRootFilesystem: false`。
- **网络**：转 URL / 截图时，容器必须能出网访问目标站点。
- **字体**：镜像自带 8 个字体包，覆盖拉丁、希腊、西里尔、CJK（Noto CJK）与彩色 emoji。中文字体是够的，缺的是微软核心字体。

## 已知限制

- **默认无鉴权**。官方文档原话是「不要把它暴露到公网，像对待数据库一样放在防火墙后面」。这是设计前提，不是配置疏漏。
- **LibreOffice 不能并行**。因为独占锁机制，一个实例同一时刻只能跑一个转换，重负载下请求会排队，直到处理完、超时或队列满被丢弃。要提吞吐只能加实例。
- **Chromium 单实例上限 6 并发**。超过就排队。`--chromium-restart-after` 默认每 100 次转换重启一次浏览器（8.15.2 之前重启会留僵尸进程）。
- **`--api-timeout` 默认只有 30s**，大文档转换很容易踩到；且它和 webhook 异步模式的宽限期需要配套调整。
- **`splitMode=pages` 时 Gotenberg 不校验 `splitSpan` 语法**，直接透传给底层引擎（默认 pdfcpu，可换 QPDF / PDFtk）。语法随引擎变化，写错了只会得到引擎的报错，不是 Gotenberg 的友好提示。
- **PDF 引擎能力不一致**。合并/拆分/加密/水印等由多个引擎分工（qpdf / pdfcpu / pdftk / exiftool / UNO），每条特性只由其中几个支持。例如 PDFtk 加密要求用户密码与所有者密码**必须不同**且只有 AES-128，而其他引擎支持 AES-256。
- **PDF/A 与加密互斥**；PDF/A-1b / 2b 不支持附件；PDF/A 与 PDF/UA 走 LibreOffice 二次处理，**比原生转换慢**，且会覆盖 `CreateDate` / `ModDate` / `Keywords`。
- **写入元数据会破坏 PDF/A 合规**，且键名不能与 ExifTool 选项同名。
- **微软核心字体因授权原因不随镜像分发**，只给了度量兼容的替代品；需要真字体必须自建镜像并接受 EULA。
- **Cloud Run / AWS Lambda 变体是特化的**，端口、日志格式、webhook 模式都已预设；Lambda 的 `buffered` 模式响应上限 6MB，更大输出要走 webhook 传到 S3。
- 许可证政策以官方仓库当前说明为准。

## 自检清单

- [ ] 容器绑的是 `127.0.0.1` 或内网地址，没有直接挂公网。
- [ ] 部署后先 `curl /health` 与 `/version` 确认活着，再跑真实转换。
- [ ] 用 `docker run ... gotenberg --api-timeout=...` 覆盖 **command**，没有动 entrypoint。
- [ ] 已按需要选对镜像变体：要转 Office 就不能用 `:8-chromium`。
- [ ] 转换后肉眼抽查了 PDF：中文字体正常、背景符合预期、没有半截空白页。
- [ ] HTML 引用的所有本地资源（CSS / 图片 / 字体）都随请求上传了。
- [ ] 需要等待动态内容时用的是 `waitForSelector` / `waitForExpression`，不是 `waitDelay` 硬等。
- [ ] 目标站是 `file://` 路径时改走了 `/convert/html`，没硬传 `convert/url`。
- [ ] 合并场景的文件名带了数字前缀，页序符合预期。
- [ ] 没有同时请求 PDF/A 与加密；要附件时用的是 PDF/A-3b。
- [ ] 并发规划是按「加实例」而不是「调大单实例并发」来做的，LibreOffice 任务已接受串行。
- [ ] Basic Auth 的用户名密码走的是服务端环境变量，没有硬编码进调用脚本。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/routes.md` | 全部路由与常用表单字段速查：转换、截图、PDF 后处理、系统路由 |
| `references/operations.md` | 部署与调参：镜像变体选择、配置项与环境变量、Webhook 异步、K8s / Cloud Run / Lambda |
| `references/pitfalls.md` | 排障：字体、渲染差异、超时、并发、引擎能力差异、元数据与 PDF/A 的坑 |
| `README.md` | 包说明 |
| https://github.com/gotenberg/gotenberg | 上游仓库（安装与完整文档以它为准） |

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
