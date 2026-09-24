# 排障与坑

按「现象 → 定位 → 处置」组织。每条都是实际会撞上的，不是理论风险。

---

## 一、字体与文字

### PDF 里中文变方块 / 空白

**定位**：镜像自带 `fonts-noto-cjk`，中文字体本身是有的。方块通常来自模板里指定了 `Arial`、`Calibri`、`Times New Roman` 这类**微软核心字体**——镜像因授权原因不含它们，只提供度量兼容的 Carlito（Calibri）、Caladea（Cambria）、Liberation（Arial / Times New Roman / Courier New）。字体名对不上，落到没有中文字形的兜底字体上就成了方块。

**处置**：
1. 首选改 CSS，把字体名换成 `Liberation Sans` / `Noto Sans CJK SC` 这类镜像里真实存在的。
2. 需要真字体时自建镜像装 `ttf-mscorefonts-installer`，注意安装时要预置 EULA 接受项，且镜像体积会变大。
3. 如果是 Office 文档里的字体，同理——LibreOffice 会做字体替换，替换表决定了版面是否走样。

### 特殊文种缺字

阿拉伯、泰文、希伯来等文种，`fonts-noto-core` 覆盖了大部分，但装饰性 / 传统字形（如 Naskh 体的 Amiri）需要单独装包。官方给了一张文种 → 字体包的对照表。

---

## 二、渲染结果和浏览器不一致

### 背景色、背景图全没了

Chromium **默认按 `print` 媒体类型渲染**。这是最常见也最容易误判为 bug 的一条。

**处置**：
- 要保留背景：传 `printBackground=true`。
- 要完全还原屏幕效果：传 `emulatedMediaType=screen`。
- 想通过 CSS 精确控制纸张：配 `preferCssPageSize=true`，让 `@page` 规则生效。

三者的组合结果见 `references/routes.md` 的背景逻辑表。

### 导航栏、按钮也印出来了 / 反而有元素消失了

模板里有 `@media print` 规则在起作用。要么调整 `@media print`，要么切到 `emulatedMediaType=screen` 再看差异。

### 想强制暗色模式

用 `emulatedMediaFeatures` 覆盖 CSS 媒体特性：

```bash
--form 'emulatedMediaFeatures=[{"name":"prefers-color-scheme","value":"dark"}]'
```

可用的特性名还有 `prefers-reduced-motion`、`color-gamut`、`forced-colors`。

---

## 三、内容空白 / 截断

### 图表、列表数据没渲染出来

**根因**：Chromium 抓的是**当前时刻已渲染的 DOM**。页面用 JS 异步取数再画图时，转换很可能在数据回来之前就开始了。

**处置优先级**（别一上来就用定时等待）：
1. **`waitForSelector`**：让页面在就绪时插一个标记元素，然后等它的 CSS 选择器。
   ```js
   await heavyCalculation()
   const marker = document.createElement("div")
   marker.id = "app-ready"
   document.body.appendChild(marker)
   ```
   ```bash
   --form 'waitForSelector=#app-ready'
   ```
2. **`waitForExpression`**：等一个 JS 表达式为真，支持返回 Promise（会被 await），可以在里面做点击、延时等准备动作。
   ```bash
   --form 'waitForExpression=window.status === "ready"'
   ```
3. **`waitDelay`**：纯定时，是兜底手段。页面快就白等，页面慢就还是出半截。**只有在无法改动目标页面时才用它。**

### `convert/url` 返回 400

`file://` 协议被明确禁止。本地文件改走 `/forms/chromium/convert/html`，把 HTML 上传上去。

---

## 四、本地资源丢失

### HTML 里的图片、CSS、字体全没生效

Gotenberg 把上传的文件放在一个临时工作目录里，**HTML 里用相对路径引用的资源必须一起上传**，并且保持相对路径结构一致。

```bash
curl --request POST http://localhost:3000/forms/chromium/convert/html \
  --form files=@index.html \
  --form files=@style.css \
  --form files=@logo.png \
  -o out.pdf
```

漏传任何一个，那部分就是静默丢失，不会报错。

---

## 五、超时与并发

### 请求固定 30 秒左右就挂

`--api-timeout` 默认就是 **30s**。Office 大文档、慢站点、复杂 JS 页面都很容易超。

```bash
docker run --rm -p "3000:3000" gotenberg/gotenberg:8 gotenberg --api-timeout=120s
```

用 webhook 异步模式时还要同步放大 `--gotenberg-graceful-shutdown-duration`，否则容器在任务跑完前就开始优雅关停。

### 并发上不去，排队严重

先认清两个硬上限：

| 模块 | 并发能力 |
|---|---|
| Chromium | 单浏览器**最多 6 个**并行操作（`--chromium-max-concurrency` 上限就是 6） |
| LibreOffice | **完全不能并行**——因为有独占锁，一个实例同一时刻只跑一个转换 |

重负载下请求会在队列里堆积，直到被处理、超时，或**队列满被直接丢弃**（返回 503）。

**正确做法是加 Gotenberg 实例横向扩展**，而不是继续调大单实例参数。负载均衡层把请求分到多个容器即可。

另外 `--pdfengines-max-concurrency` 默认是 `1`，且是**跨所有请求**的全局限制。多文件请求想快可以调大，但会增加内存占用；这个参数对 LibreOffice 无效。

### 浏览器越跑越慢 / 内存涨

`--chromium-restart-after` 默认每 100 次转换重启一次浏览器，`--libreoffice-restart-after` 默认每 10 次。设成 `0` 会关掉这个保护，长跑场景不建议关。

### 每次转换之间状态串了

Cookie、缓存、本地存储默认是跨转换保留的（会话存储本来就按转换隔离）。需要严格隔离就打开：

```
--chromium-clear-cache --chromium-clear-cookies --chromium-clear-storage
```

代价是每次都冷启动，转换变慢。

---

## 六、PDF 后处理

### 合并后页序不对

合并顺序是**按文件名的字母数字序**（数字优先），**不是上传顺序**。想让顺序可控，上传前把文件重命名成 `01_`、`02_`、`03_` 前缀。

例外：自 8.37.0 起，**同名文件**会全部保留并按上传顺序参与合并；在这之前同名文件只会有一个进结果。

### 拆分出来的结果和预期不符 / 报引擎的语法错

`splitMode=pages` 时 **Gotenberg 不校验 `splitSpan` 的语法**，原样透传给底层引擎，而三个引擎的页范围语法各不相同：

| 引擎 | 参考 |
|---|---|
| pdfcpu（默认） | pdfcpu `/trim` 文档 |
| QPDF | QPDF page-ranges 文档 |
| PDFtk | PDFtk `cat` 操作文档 |

还有个容易踩的：**PDFtk 与 QPDF 的拆分只支持 `pages` 模式且要求 unify**。所以一旦你调整了 `--pdfengines-split-engines` 的顺序，原本能用的 `intervals` 拆分可能就失效了。

### 某条特性突然不可用

PDF 引擎模块是**按顺序挨个尝试，直到有一个成功**。改了引擎顺序、或者用了不含某引擎的变体，特性就会失效。完整的分工矩阵见 `references/routes.md` 第六节。

典型差异：
- **PDFtk 加密要求用户密码和所有者密码必须不同**，不支持只有所有者密码的情况，也不支持细粒度权限限制，且只有 AES-128；其他引擎支持 AES-256。
- **QPDF 逐条尊重文档权限设置，pdfcpu 是一刀切**——用 pdfcpu 限制任意一条权限就等于全部禁掉。
- **读 / 写元数据只有 ExifTool 支持**。
- **扁平化只有 QPDF 支持**。
- **优化图片只有 pdfcpu 支持**。

### 写 metadata 报 400

键名和 ExifTool 的选项名撞了。`csv`、`json`、`o`、`config` 这几个都会触发。加分组前缀即可：写成 `XMP:csv`。

另外，**写元数据通常会让文档不再符合 PDF/A**。

### 同时要 PDF/A 和加密，报 400

这两者**互斥**，只能二选一。

### PDF/A 场景下附件加不上

PDF/A-1b 与 PDF/A-2b **不支持文件附件**，要用 PDF/A-3b。做 Factur-X 电子发票时这是硬要求。

### PDF/A 转换特别慢，而且元数据被改了

PDF/A（和 PDF/UA）走 LibreOffice 做二次处理，**比原生转换慢**。而且当它与其他后处理同时执行时，LibreOffice 会**覆盖 `CreateDate`、`ModDate`、`Keywords`**，其他元数据字段保留。

还有一个副作用：**LibreOffice 会把带背景色的表格单元格栅格化成图片**，这会损害无障碍性（PDF/UA 场景下要留意）。

### 水印 / 图章报 400

`watermarkExpression` / `stampExpression` **不能引用任意文件系统路径**，只接受文本内容，或者已上传文件的文件名。`image` / `pdf` 来源必须另传 `watermark`（或 `stamp`）文件。

多个水印可重复字段按序应用，`image` / `pdf` 类型会**按顺序消耗**上传的 `watermark` 文件。

### 水印跑到内容上面了 / 图章跑到下面了

这是两个不同特性，别用混：**`watermark` 垫在内容下方，`stamp` 盖在内容上方**。

### 输出文件名改不了

`Gotenberg-Output-Filename` 只影响**响应头 `Content-Disposition` 里的附件名**，扩展名还是 Gotenberg 自己追加的。它**决定不了本地磁盘路径**——那是你 `curl -o` 或 HTTP 客户端写文件时定的。

---

## 七、安全

### 服务被公网扫到

这是最需要前置处理的一条。官方在安装页第一行就写了：**不要把 Gotenberg 暴露到公网，像对待数据库一样放在防火墙后面**。

原因很直接：默认**完全没有任何鉴权**，而且 `-p 3000:3000` 默认对所有网卡开放。它还是一个能出网、能拉任意 URL、能渲染任意 JS 的浏览器，被滥用就是 SSRF 跳板。

**处置顺序**：
1. 端口绑定到回环：`-p "127.0.0.1:3000:3000"`。
2. 必须跨机访问时，开 `--api-enable-basic-auth`（凭据走服务端环境变量 `GOTENBERG_API_BASIC_AUTH_USERNAME` / `_PASSWORD`）或 `--api-enable-oidc-auth`。
3. 前面再加反向代理做 TLS、限流、来源 IP 白名单。
4. 出站侧配 `--chromium-deny-private-ips=true`，防止它被用来扫内网。
5. `/debug` 只在需要时开，用完关掉。

### 出站请求的 DNS rebind 防护被绕过

自 8.32.0 起，Chromium 的每个出站请求都走进程内的 pinning 代理（DNS 解析一次，拨号到已校验的 IP）。但**一旦设置 `--chromium-proxy-server` 或 `--chromium-host-resolver-rules`，这个代理就被跳过**，等于把出站安全责任交回给你。设置 `--chromium-host-resolver-rules` 的官方说明是「你自己对出站安全负责」。

### allow-list 写错反而打开缺口

`--chromium-allow-list` / `--api-download-from-allow-list` 用的是**正则**，而且匹配会**绕过 IP 段检查**。正则如果不锚定主机名边界，`example.com` 这个模式会连带匹配 `evil-example.com`。官方专门有一篇《Writing a Safe Allow-List》讲这个，建议模式要终止在主机名边界上。

另外注意优先级：**deny-list 命中一律拒绝**，优先级高于 allow-list 和 IP 段开关。

### 自定义请求头被用来打内网

`extraHttpHeaders` 的 `;scope=` 正则支持按 URL 匹配发送头。如果 scope 写得过宽，等于把你的内部令牌发给了每一个第三方请求（字体 CDN、分析脚本……）。要终止主机名边界，并且别用嵌套量词（如 `(a+)+`）——回溯会吃满匹配预算，官方对 scoped 头的匹配时间有上限，超了剩余的头就不发了。

### 上传文档里的外链被自动抓取

自 8.34.0 起 LibreOffice **不再把上传文档视为可信**：文档里链接的 `file://` 路径和外部 URL 会在任何抓取发生前就被拦截。在这之前的版本，恶意 docx 可以通过 `INCLUDEPICTURE` 之类的手段让服务去抓内网资源。保持版本更新，并用 `--libreoffice-allow-list` / `--libreoffice-deny-list` 把出站抓取收窄。

---

## 八、部署形态

### 转了 Office 报功能不可用

用的是 `:8-chromium` 变体，它**不含 LibreOffice**。换 `gotenberg/gotenberg:8` 或 `:8-libreoffice`。请求不支持的功能是**直接报错**，不会静默降级。

### Cloud Run 上容器被停掉，异步任务丢了

Cloud Run 没有 HTTP 活动就会停容器，所以官方变体默认开了**同步 webhook 模式**。别自己去关它。

### Lambda 上大文件转换失败

`buffered` 调用模式的**响应上限是 6MB**。超出就得改用 webhook 把结果上传到 S3，而不是直接返回 body。

### 容器权限报错

镜像以 UID/GID **1001** 的非 root 用户 `gotenberg` 运行。K8s 里要设 `runAsUser: 1001`；`readOnlyRootFilesystem` 必须为 `false`（Chromium 和 LibreOffice 都要写临时文件）。8.21.0 起支持任意 UID，OpenShift 的随机 UID 场景也能跑。

### 内存不够（OOM / 转换被杀）

官方给的基线是 K8s **512Mi + 0.2 CPU**，Cloud Run **1Gi**。但这只是「能跑」的下限。实际转复杂网页或大 Office 文档时给到 **1–2GB** 更稳。Chromium 是多进程架构，一个页面就能吃掉几百 MB。

---

## 九、排障用的最小命令集

```bash
# 服务活着吗
curl -sf http://localhost:3000/health

# 跑的是哪个版本（报 bug 时必带）
curl -sf http://localhost:3000/version

# 实际生效的运行时配置（需先开 --api-enable-debug-route）
curl -sf http://localhost:3000/debug

# 拿 trace id 去日志里捞这次请求
curl -si --request POST http://localhost:3000/forms/chromium/convert/url \
  --header 'Gotenberg-Trace: my-debug-001' \
  --form url=https://example.com -o /dev/null

# 看完整错误体（--fail-with-body 很关键，否则 4xx/5xx 的 body 看不见）
curl --fail-with-body --silent --show-error \
  --request POST http://localhost:3000/forms/libreoffice/convert \
  --form files=@broken.docx -o /dev/null

# 容器日志（json 格式更易读）
docker logs <container> 2>&1 | tail -50
```

调日志级别到 debug 能拿到更多细节：

```bash
docker run --rm -p "3000:3000" gotenberg/gotenberg:8 gotenberg --log-level=debug
```

---

## 十、升级前必查

从 7.x 升到 8.x 有 breaking change，官方专门发了 release note 说明。升级前请：

1. 读对应版本的 release note（仓库 releases 页）。
2. 检查配置里是否用了已弃用参数——`--api-trace-header`、`--api-disable-health-check-logging`、`--log-format`、`--log-enable-gcp-fields`、`--prometheus-disable-route-logging`、`--pdfengines-engines`、`--webhook-error-allow-list`、`--webhook-error-deny-list`、`--chromium-incognito`（8.29.0 起被忽略）。
3. 重新跑一遍「转换 + Office 转换 + 合并 + 加密」四条冒烟路径。
4. 如果依赖出站过滤默认值，注意 8.32.0 起**默认改为放行**，8.31.0 引入的 deny-list 正则默认值被移除了。
