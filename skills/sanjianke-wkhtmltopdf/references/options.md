# wkhtmltopdf 选项速查

本页按用途分组整理常用选项（对应 0.12.6 with patched qt）。
**完整列表以程序自带帮助为准**：

```bash
wkhtmltopdf --help            # 常用选项
wkhtmltopdf -H                # extended-help，列全部选项
wkhtmltopdf --htmldoc         # 输出 HTML 版帮助
wkhtmltopdf --manpage         # 输出 man page
```

## 命令行结构

```
wkhtmltopdf [GLOBAL OPTION]... [OBJECT]... <output file>
```

对象（按书写顺序组装进同一份 PDF）：

| 对象 | 写法 | 特点 |
|---|---|---|
| 页面 | `<url 或文件>` | 普通页面，可带页面选项 |
| 封面 | `cover <url 或文件>` | 不进目录、没有页眉页脚 |
| 目录 | `toc [TOC 选项]` | 基于 H 标签由 XSLT 生成 |
| 图片 | `wkhtmltoimage ...` 是另一个可执行文件 | 同样接受页面选项 |

## 全局选项（只能写在最前面）

| 选项 | 说明 |
|---|---|
| `-s, --page-size <Size>` | 纸张：A4（默认）、A3、Letter、Legal 等 |
| `--page-width` / `--page-height <unitreal>` | 自定义页面尺寸（比 page-size 更细） |
| `-O, --orientation <Portrait\|Landscape>` | 方向，默认纵向 |
| `-T/-B/-L/-R, --margin-top/-bottom/-left/-right <unitreal>` | 页边距；默认左右各 10mm |
| `-d, --dpi <dpi>` | DPI，默认 96（X11 系统上无效） |
| `--image-dpi` / `--image-quality` | 内嵌图片的缩放 DPI（默认 600）与 JPEG 质量（默认 94） |
| `-l, --lowquality` | 输出更低质量，体积更小 |
| `-g, --grayscale` | 灰度输出 |
| `--title <text>` | PDF 标题，不指定则用第一个文档的标题 |
| `--copies <number>` / `--collate` / `--no-collate` | 份数与是否逐份排序 |
| `--log-level <none\|error\|warn\|info>` | 日志级别，默认 info；`-q/--quiet` 等于 none |
| `--read-args-from-stdin` | 从标准输入逐行读任务（批量用） |
| `--cookie-jar <path>` | Cookie 读写文件 |
| `--use-xserver` | 使用 X server（某些插件需要） |
| `--no-pdf-compression` | 不做无损压缩 |

## 页面选项

**资源与网络**

| 选项 | 说明 |
|---|---|
| `--enable-local-file-access` | **允许本地文件互相读取**；默认关闭，本地图片/CSS 加载失败就靠它 |
| `--allow <path>` | 只放行指定目录（可重复） |
| `-p, --proxy <proxy>` | 代理，形如 `http://user:pass@host:8080`、`socks5://host`、`None` |
| `--bypass-proxy-for <value>` | 这些主机的请求不走代理（可重复） |
| `--username` / `--password` | HTTP 基本认证 |
| `--cookie <name> <value>` | 附加 Cookie（可重复，值需 URL 编码） |
| `--custom-header <name> <value>` | 附加请求头（可重复）；`--custom-header-propagation` 让它作用于每个子请求 |
| `--post <name> <value>` / `--post-file <name> <path>` | POST 字段与文件 |
| `--ssl-crt-path` / `--ssl-key-path` / `--ssl-key-password` | 客户端证书（PEM） |
| `--cache-dir <path>` | Web 缓存目录 |

**渲染与脚本**

| 选项 | 说明 |
|---|---|
| `--enable-javascript` / `-n, --disable-javascript` | JS 开关，默认开启 |
| `--javascript-delay <msec>` | 等 JS 执行的毫秒数，默认 200 |
| `--stop-slow-scripts` / `--no-stop-slow-scripts` | 是否中断慢脚本，默认中断 |
| `--window-status <string>` | 等 `window.status` 等于该字符串后再渲染（异步页面的可靠做法） |
| `--run-script <js>` | 页面加载完再执行自己的 JS（可重复） |
| `--debug-javascript` | 打印 JS 调试输出 |
| `--print-media-type` / `--no-print-media-type` | 用 `@media print` 而不是 screen，默认 screen |
| `--zoom <float>` | 缩放因子，默认 1 |
| `--minimum-font-size <int>` | 最小字号 |
| `--user-style-sheet <path>` | 注入用户样式表 |
| `--viewport-size` | 视口尺寸（模拟窗口宽度，处理自定义滚动条场景） |
| `--enable-smart-shrinking` / `--disable-smart-shrinking` | 智能缩放，默认开启；它让像素/DPI 比例不恒定 |
| `--encoding <encoding>` | 输入文本编码 |
| `--default-header` | 快捷页眉：左侧网页名、右侧页码，等价于一组 header 参数 |

**内容细节**

| 选项 | 说明 |
|---|---|
| `--background` / `--no-background` | 是否打印背景，默认打印 |
| `--images` / `--no-images` | 是否加载图片，默认加载 |
| `--enable-forms` / `--disable-forms` | HTML 表单字段是否转成 PDF 表单 |
| `--enable-external-links` / `--enable-internal-links` | 链接开关（默认都开）；`--keep-relative-links`、`--resolve-relative-links` 控制相对链接处理 |
| `--load-error-handling <abort\|ignore\|skip>` | 页面加载失败怎么办，**默认 abort** |
| `--load-media-error-handling <abort\|ignore\|skip>` | 媒体文件加载失败怎么办，默认 ignore |
| `--exclude-from-outline` / `--include-in-outline` | 该页是否进目录与大纲 |
| `--page-offset <offset>` | 起始页码，默认 0 |
| `--checkbox-svg` / `--radiobutton-svg` 等 | 自定义勾选框/单选框的 SVG |

## 页眉页脚选项

| 选项 | 说明 |
|---|---|
| `--header-left` / `--header-center` / `--header-right <text>` | 页眉三段文字 |
| `--footer-left` / `--footer-center` / `--footer-right <text>` | 页脚三段文字 |
| `--header-html <url>` / `--footer-html <url>` | 用 HTML 做页眉页脚 |
| `--header-font-name` / `--header-font-size` | 默认 Arial / 12 |
| `--footer-font-name` / `--footer-font-size` | 默认 Arial / 12 |
| `--header-line` / `--no-header-line` | 页眉下方分隔线（默认无） |
| `--footer-line` / `--no-footer-line` | 页脚上方分隔线（默认无） |
| `--header-spacing <real>` / `--footer-spacing <real>` | 与正文的间距（mm），默认 0 |
| `--replace <name> <value>` | 在页眉页脚里把 `[name]` 替换成指定值（可重复） |

### 可用的占位符

`[page]` 当前页、`[frompage]` 起始页、`[topage]` 末页、`[webpage]` 页面 URL、
`[section]` / `[subsection]` 章节名、`[date]` 本地日期、`[isodate]` ISO 日期、
`[time]` 本地时间、`[title]` 当前页对象标题、`[doctitle]` 输出文档标题、
`sitepage` / `sitepages` 站点内页码。

例：`--footer-center "第 [page] 页 / 共 [topage] 页"`。

> 注意：`--header-html` / `--footer-html` 用 HTML 时，这些变量是通过 URL 查询串传进
> 页眉文档的，需要页眉 HTML 自己用脚本回填，不会自动替换。写法见
> `references/toc-and-batch.md`。

## 目录与大纲选项

| 选项 | 说明 |
|---|---|
| `--outline` / `--no-outline` | 是否生成 PDF 书签大纲，默认生成 |
| `--outline-depth <level>` | 大纲深度，默认 4 |
| `--dump-outline <file>` | 把大纲 XML 导出到文件 |
| `--dump-default-toc-xsl` | 把默认目录 XSL 打印到标准输出 |
| `--xsl-style-sheet <file>` | 用自定义 XSL 渲染目录 |
| `--toc-header-text <text>` | 目录标题文字，默认 `Table of Contents` |
| `--toc-level-indentation <width>` | 每级缩进，默认 1em |
| `--toc-text-size-shrink <real>` | 每级字号缩放，默认 0.8 |
| `--disable-dotted-lines` | 目录不要点线 |
| `--disable-toc-links` / `--disable-toc-back-links` | 关闭目录跳转 / 关闭正文回跳目录 |
