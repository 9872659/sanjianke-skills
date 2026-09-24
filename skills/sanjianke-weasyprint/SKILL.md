---
name: sanjianke-weasyprint
slug: sanjianke-weasyprint
displayName: 三剪客 · HTML/CSS 转 PDF
description: "WeasyPrint：HTML/CSS 转 PDF 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "WeasyPrint：HTML/CSS 转 PDF 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - PDF
  - 文档处理
---

# 三剪客 · HTML/CSS 转 PDF

你已经有 HTML 了——报表模板、发票、对账单、带图表的数据页——现在要把它变成能发出去的 PDF。
`WeasyPrint` 就是这一步：把 HTML + CSS 按**打印规范**排版并导出 PDF，支持分页、页眉页脚、
页码、目录书签、PDF/A 归档、PDF/UA 无障碍、表单字段、附件。

它和浏览器「打印成 PDF」的区别在于**可控**：跑在服务端、可以脚本化、可以用 `@page` 精确控制
纸张尺寸与边距、可以生成 PDF/A-3u 这种归档标准文件。适合「模板 + 数据 → 批量出 PDF」这类活。

**上游项目**：`WeasyPrint`　**仓库**：https://github.com/Kozea/WeasyPrint

## 什么时候用 / 不用

**用它**：

- 已有 HTML/CSS 模板，要批量渲染成 PDF（发票、报表、证书、对账单、电子书）。
- 需要**服务端**出 PDF：跑在容器 / CI / 定时任务里，不接受人工点「打印」。
- 要生成**标准化的 PDF 变体**：PDF/A（归档）、PDF/UA（无障碍）、PDF/X（印刷交换）。
- 要精确控制纸张：`@page` 设尺寸、方向、边距、页眉页脚、页码、分页规则。
- 要 PDF 目录书签（从 HTML 标题层级自动生成）、内部链接、可填写的表单字段。

**不要用它**：

- 要**像素级还原真实网页**（复杂 JS 渲染、Flex/Grid 边角特性、Web 字体加载时序）——
  WeasyPrint 是自研排版引擎，不是浏览器内核，官网自己都说渲染结果与浏览器不同。
- 要**把现成的 PDF 转成图片或拆页**——它只负责「生成 PDF」，不做 PDF 后处理。
- 要**从扫描件里提取内容**——那是 OCR 的活。
- 输入是**不可信的用户 HTML/CSS**：官方专门列了一整节安全问题（死循环、超大值、
  `file://` 读本地文件、附件被 PDF 阅读器执行）。必须做沙箱、限时限内存、过滤 URL。
- 极长文档 / 复杂表格追求速度：官方明说渲染偏慢，表格跨页尤其慢，不追求性能。

## 安装

**Linux（最简单，用发行版包）**

```bash
# Debian / Ubuntu
apt install weasyprint

# Fedora
dnf install weasyprint

# Arch
pacman -S python-weasyprint

# Alpine
apk add weasyprint
```

**Linux 用 pip（需要先有 Python 与新版 Pango）**

```bash
python3 --version          # 需 ≥ 3.10
pango-view --version       # Pango 需 ≥ 1.44

python3 -m venv venv
source venv/bin/activate
pip install weasyprint
weasyprint --info          # 打印系统信息，用来确认装好了
```

用 wheel 装时依赖的**系统库**（Debian/Ubuntu 示例）：

```bash
apt install python3-pip libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
```

**macOS**

```bash
brew install weasyprint
```

**Windows**

```bash
# 最省事：直接下载官方 releases 里的可执行文件
# https://github.com/Kozea/WeasyPrint/releases
```

要在 Windows 上当 Python 库用，需要先有 Python 再装 Pango：

```bash
# 1) 安装 MSYS2（保持默认选项）
# 2) 在 MSYS2 UCRT64 shell 里执行：
pacman -S mingw-w64-ucrt-x86_64-pango
# 3) 回到 cmd：
python -m venv venv
venv\Scripts\activate.bat
python -m pip install weasyprint
python -m weasyprint --info
```

找不到 DLL 时报 `cannot load library 'xxx'` 时，指定库目录：

```bat
set WEASYPRINT_DLL_DIRECTORIES=C:\msys64\ucrt64\bin
```

**Conda / WSL / Docker**

```bash
conda install -c conda-forge weasyprint    # Linux 与 macOS

# WSL 里按 Linux 的方式装
```

官方文档提到有社区维护的 Docker 镜像（非官方测试路径），要容器化建议自己基于上面的
Debian/Ubuntu 依赖写 Dockerfile。

## 常用操作

**1. 命令行最小用法（HTML 文件 → PDF）**

```bash
weasyprint document.html document.pdf

# 输入也可以是 URL，输出用 - 表示 stdout
weasyprint https://weasyprint.org /tmp/weasyprint-website.pdf
```

**2. 用 `-s` 追加用户样式表控制纸张和边距**

```bash
weasyprint input.html output.pdf -s <(echo "@page { size: A3 landscape; margin: 3cm }")
```

对应的 CSS（写进文件或 `<style>` 里都一样）：

```css
@page {
  size: A4;          /* 也可 A3 landscape、210mm 297mm */
  margin: 2cm;
  @bottom-center { content: counter(page) " / " counter(pages); }
}
```

命令行**没有**页码 / 纸张尺寸这类参数，纸张和边距一律走 CSS `@page`。

**3. Python API：字符串 HTML 直接出 PDF**

```python
from weasyprint import HTML, CSS

HTML(string="<h1>标题</h1><p>正文</p>").write_pdf("out.pdf")

HTML("report.html").write_pdf(
    "out.pdf",
    stylesheets=[CSS(string="body { font-family: serif !important }")],
)
```

`write_pdf()` 不传 `target` 时返回 PDF 字节串，可以直接落库或走 HTTP 响应。

**4. `@font-face` 自定义字体必须用 FontConfiguration**

```python
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

font_config = FontConfiguration()
html = HTML(string="<h1>The title</h1>")
css = CSS(string="""
    @font-face { font-family: Gentium; src: url(fonts/Gentium.otf); }
    h1 { font-family: Gentium }
""", font_config=font_config)
html.write_pdf("out.pdf", stylesheets=[css], font_config=font_config)
```

**5. 生成 PDF/A 归档件**

```bash
weasyprint document.html --pdf-variant=pdf/a-3u document.pdf
```

```python
from weasyprint import HTML
HTML(string="<p>document</p>").write_pdf("document.pdf", pdf_variant="pdf/a-3u")
```

可选变体（`weasyprint --help` 会列出）：`pdf/a-1b`、`pdf/a-2b`、`pdf/a-3b`、
`pdf/a-2u`、`pdf/a-3u`、`pdf/a-4u`、`pdf/a-1a`~`pdf/a-3a`、`pdf/a-4e`、`pdf/a-4f`、
`pdf/ua-1`、`pdf/ua-2`、`pdf/x-1a`、`pdf/x-3`、`pdf/x-4`、`pdf/x-5g`、`debug`。
一般归档优先 `pdf/a-3u`，印刷交换优先 `pdf/x-4`。

**6. 前端模板 + 模板引擎的典型用法（数据填模板再渲染）**

```python
from jinja2 import Template
from weasyprint import HTML

html = Template(open("invoice.html", encoding="utf-8").read()).render(
    items=[{"name": "A", "price": 10}, {"name": "B", "price": 20}],
)
HTML(string=html, base_url=".").write_pdf("invoice.pdf")   # base_url 决定相对路径基准
```

**7. 附加文件与自定义元数据**

```bash
weasyprint document.html --attachment note.txt --attachment photo.jpg \
    --custom-metadata document.pdf
```

HTML 里也可以写：`<link rel="attachment" href="note.txt">`；
文档元数据（标题、作者、关键词、创建时间）在 `<head>` 里用标准 `<meta>` 声明即可被写入 PDF。

**8. 图片压缩与缓存（批量出图时省钱省时间）**

```python
from weasyprint import HTML

HTML("report.html").write_pdf("out.pdf", optimize_images=True, jpeg_quality=60, dpi=150)

cache = {}                       # 跨文档复用的内存缓存
for i in range(10):
    HTML("report.html").write_pdf(f"out-{i}.pdf", cache=cache)
```

**9. 调试：把日志打开**

```python
import logging
logger = logging.getLogger("weasyprint")
logger.setLevel(logging.WARNING)
logger.addHandler(logging.StreamHandler())
```

命令行加 `--verbose` / `--debug` 可以看到渲染进度。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `cannot load library 'gobject-2.0-0'` 之类 | 系统缺 Pango / HarfBuzz / fontconfig 等本地库，pip 只装 Python 包 | Linux 按安装节装 `libpango*`；Windows 用 MSYS2 装 pango 并设 `WEASYPRINT_DLL_DIRECTORIES`；macOS 设 `DYLD_FALLBACK_LIBRARY_PATH` |
| PDF 里中文字全是方块或空白 | 系统没有对应字体，或字体没被找到 | 装系统中文字体，或用 `@font-face` 显式指定字体文件 URL |
| 改了命令行参数纸张没变 | 命令行**不提供**页面尺寸 / 边距选项 | 用 `@page { size: ...; margin: ... }`，或 `-s` 传样式表 |
| 网页在浏览器里好看，转出来完全不一样 | WeasyPrint 不是 WebKit/Gecko，CSS 支持面不同 | 按打印语义写 CSS，避开依赖 JS 的布局；先在目标版本上试渲染再批量 |
| 渲染卡死 / CPU 内存飙满 | 官方已知问题：特制 HTML/CSS 会死循环、超大值、引用 `/dev/urandom` | 服务端限时限内存、用容器或 `ulimit`；输入先截断清洗；不要渲染不可信来源 |
| 生成的 PDF 把服务器本地文件带出去了 | 默认可以读 `file://`，也能把本地文件当附件打包 | 自定义 URL fetcher 禁掉 `file://`，或用 `--allowed-protocols` 限定协议 |
| 几百个文件批量跑很慢 | 每次启动都要初始化字体与引擎 | 用长驻 Python 进程复用同一个进程渲染多份，官方也是这么建议的 |
| 装了新版本后老模板样式错位 | 官方版本策略：版本号变化**会改变渲染结果** | 锁定版本号，升级前用样本回归对比 |
| 表格多页渲染异常慢 | 官方明确说表格（尤其跨页表格）是性能瓶颈 | 能用块级布局就别用表格；大表考虑拆页 |
| `@font-face` 不生效 | 没传 `FontConfiguration` | 建 `FontConfiguration()` 对象，并在 CSS 与 `write_pdf` 两边都传同一个 |
| PDF/A 校验不过 | 文档用了 PDF/A 不允许的特性（透明、未嵌字体、无色彩空间） | 优先用 `pdf/a-3u`；带图时加 `image-rendering: crisp-edges` |
| PDF/UA 校验不过 | 缺 `<title>` 或 `<html>` 上没有 `lang` | 补上 `<title>` 与 `lang`，并用语义化 HTML 结构 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 抓取远程 HTML / CSS / 图片 / 字体；**离线渲染可完全断网**（建议断网排查） |
| 读取文件 | 是 | 读本地 HTML、CSS、图片、字体；默认允许 `file://`，处理不可信输入时必须限制 |
| 写入文件 | 是 | 写出 PDF；**传文件名时会静默覆盖已有文件** |
| 凭证 | 否 | 不需要账号或 Key；但内置 HTTP 客户端不支持 Cookie / 认证，需登录态请自定义 URL fetcher 或改用框架扩展 |
| 子进程 / 后台常驻 | 视情况 | 命令行方式会启子进程；批量出件建议长驻进程以省启动开销 |

## 触发场景

- 「把这个 HTML 模板渲染成 PDF，做成对账单 / 发票 / 报表」
- 「我要在服务端批量生成 PDF，不要人点打印」
- 「这个 PDF 要归档，需要符合 PDF/A」
- 「给这个 PDF 加目录书签和页码」
- 「网页样式改一下，纸张改成 A3 横向、边距 3 厘米」
- 「把这份数据填进模板，一次出 200 份 PDF」

## 能力边界

**覆盖**：

- HTML + CSS 排版并导出 PDF，支持分页、页眉页脚、页码计数、分页控制
- 文档尺寸与边距通过 `@page` 精确控制（不是命令行参数）
- 目录书签与内部 / 外部链接（可从标题层级自动生成书签，`make_bookmark_tree()` 可读）
- 标准 PDF 变体：PDF/A 系列、PDF/UA 系列、PDF/X 系列
- 可填写的 PDF 表单（`--pdf-forms` / `pdf_forms=True`）
- 文件附件、自定义元数据（标题 / 作者 / 关键词 / 创建与修改时间）
- 图片优化与缓存（`optimize_images`、`jpeg_quality`、`dpi`、`cache` / `--cache-folder`）
- 单文档内页级操作：`render()` 拿到 `Document`，`copy()` 取页子集，分奇偶页输出

**不覆盖**：

- 不是浏览器：复杂 JS、部分现代 CSS 特性、与浏览器像素级一致的还原
- 不做 PDF 后处理：不合并、不拆分已有 PDF、不加密、不加水印、不提取文本
- 不做 OCR / 不解析扫描件
- 不做图像格式转换或截图
- 不提供守护进程或 HTTP 服务；服务化要自己包一层（或用 Flask / Django 的官方扩展）
- 不保证生成的 PDF/A、PDF/UA 一定通过校验，取决于输入是否符合对应规范的约束

## 依赖条件

- Python ≥ 3.10（WeasyPrint 70）
- 系统库 **Pango ≥ 1.44**（以及 HarfBuzz、fontconfig 等），这是最容易卡住的一环
- Python 依赖：pydyf ≥ 0.11.0、CFFI ≥ 0.6、tinyhtml5 ≥ 2.0.0b1、tinycss2 ≥ 1.5.0、
  cssselect2 ≥ 0.8.0、Pyphen ≥ 0.9.1、Pillow ≥ 9.1.0、fontTools ≥ 4.59.2
- 不需要账号、不需要 API Key
- 系统需要有覆盖目标语言的字体（中文文档务必确认中文字体可用）

## 已知限制

1. 渲染引擎自研，与浏览器结果**必然存在差异**，不能承诺像素级一致。
2. 性能一般：长文档、多页表格明显偏慢，官方不把性能作为优化目标。
3. 每个大版本都会改变渲染结果，升级必须做样本回归，不能盲升。
4. 处理不可信 HTML/CSS 有明确安全风险（死循环、超大值、读本地文件、附件被执行），
   生产环境必须自己加沙箱、限时限内存。
5. 命令行的渲染选项里**没有**页面尺寸与边距，只能走 CSS。
6. Windows 上作为库使用需要额外配置 MSYS2 + Pango，比 Linux 麻烦；
   杀毒软件会对官方可执行文件误报（官方已有 issue 说明，属误报）。

## 自检清单

执行前：

- [ ] `weasyprint --info` 能跑通，确认 Python 与 Pango 版本达标
- [ ] 确认中文字体在系统里可用（或已用 `@font-face` 指定）
- [ ] 确认输入 HTML 是否可信；不可信必须先做沙箱与限时限内存
- [ ] 确认目标 PDF 变体（普通 / PDF/A / PDF/UA / PDF/X）与对应约束
- [ ] 确认输出路径不会覆盖重要文件

执行后：

- [ ] 打开输出 PDF 抽几页核对分页、页眉页脚、页码是否正确
- [ ] 带图 / 带字体时确认没有丢图、没有方块字
- [ ] 声称 PDF/A、PDF/UA 时用校验工具实际验一遍
- [ ] 批量任务统计成功 / 失败数量，记录 WeasyPrint 版本便于复现
- [ ] 检查生成的 PDF 是否意外包含不该带出的本地文件或元数据

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/Kozea/WeasyPrint | 上游仓库（安装与完整文档以它为准） |
| https://doc.courtbouillon.org/weasyprint/stable/first_steps.html | 官方 First Steps：各平台安装、命令行、Python 库、安全章节 |
| https://doc.courtbouillon.org/weasyprint/stable/common_use_cases.html | 官方 Common Use Cases：PDF/A、表单、附件、元数据、性能优化 |

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
