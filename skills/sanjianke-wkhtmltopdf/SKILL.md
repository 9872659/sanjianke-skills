---
name: sanjianke-wkhtmltopdf
slug: sanjianke-wkhtmltopdf
displayName: 三剪客 · HTML 转 PDF
description: "wkhtmltopdf：HTML 转 PDF 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "wkhtmltopdf：HTML 转 PDF 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · HTML 转 PDF

拿现成的 HTML + CSS 直接渲染成 PDF，不用为打印另做一套排版。它内置浏览器引擎（Qt WebKit）、完全无头运行，不需要显示器，一条命令就能把网页或本地 HTML 变成带页眉页脚、页码、书签和目录的 PDF；同门的 `wkhtmltoimage` 还能顺手出图片。它的天花板也很明确：内核停留在 2012 年前后的 WebKit，现代 CSS、新语法 JS 都不认；上游仓库已经归档，最后一个稳定版是 2020 年的 0.12.6。

**上游项目**：`wkhtmltopdf`　**仓库**：https://github.com/wkhtmltopdf/wkhtmltopdf

## 什么时候用 / 不用

**用它**：

- 已有 **服务端渲染好的 HTML**（报表、发票、对账单、合同），想原样输出成 PDF
- 需要 **页眉页脚 + 页码**（`[page]/[topage]`）、**PDF 书签大纲**、**目录页**这类印刷特性
- 渲染环境**没有显卡也没有显示器**，且不想装一套 Chromium
- 要把**网页/HTML 截图成图片**（`wkhtmltoimage` 支持 PNG/JPEG 等）
- 页面 CSS 是「打印友好」的老式写法（table 布局、float、绝对定位），没有 flex/grid

**不要用它**：

- HTML 用了 **flex / grid / CSS 变量 / ES6+ 语法**，或者依赖现代前端框架的运行时 → 内核太老，渲染结果会崩
- 页面内容**完全靠 JS 异步渲染**（SPA、前端图表库） → 等不到结果或大概率白页，考虑无头 Chromium 系方案
- 处理**不可信的用户 HTML** → 官方明确警告：不消毒就等于把服务器交出去（详见「常见坑」）
- 需要**长期维护、持续跟进浏览器安全更新** → 上游已归档，引擎不会更新
- 只想**简单合并/操作 PDF**（拆页、加水印、加密） → 它只负责 HTML→PDF，PDF 后期处理要用别的工具
- 追求**和打印浏览器逐像素一致** → 不同版本、不同发行版编译方式差异会导致排版和字体都不完全一致

## 安装

官方安装包都放在独立的 packaging 仓库的 Releases 里，按发行版选对应包（**当前稳定系列 0.12.6，2020-06-11 发布**）：

```bash
# Debian / Ubuntu：从 Releases 下对应发行版的 .deb（bullseye / buster / jammy / focal / bionic / xenial …）
sudo apt-get install -y ./wkhtmltox_0.12.6.1-2.jammy_amd64.deb
# 注意：发行版仓库里的 wkhtmltopdf 多为「未打补丁的 Qt」编译，功能会缺（见「常见坑」）

# RHEL 系：AlmaLinux / CentOS / openSUSE / Amazon Linux 有对应 .rpm
sudo rpm -Uvh wkhtmltox-0.12.6.1-2.almalinux9.x86_64.rpm

# Arch：官方 Releases 提供 pkg.tar.xz
sudo pacman -U wkhtmltox-0.12.6-3.archlinux-x86_64.pkg.tar.xz

# Windows：下载 installer（Vista 及以上，64/32 位）或 7z 免安装包
wkhtmltox-0.12.6-1.msvc2015-win64.exe

# macOS：官方提供 10.7+ 的 .pkg 安装包
# 各包管理器（如 Homebrew）当前是否提供、提供的是哪个版本，以各自仓库现状为准

# 验证装的是不是「打了补丁的 Qt」版本
wkhtmltopdf --version     # 期望输出里带 (with patched qt)
```

AWS Lambda 场景官方提供 Amazon Linux 2 的 lambda zip：解包后需要设置
`LD_LIBRARY_PATH=/opt/lib` 与 `FONTCONFIG_PATH=/opt/fonts` 才能跑起来。

## 常用操作

```bash
# 1) 最基本：HTML 文件 → PDF
wkhtmltopdf input.html output.pdf

# 2) 本地 HTML 引用本地图片/CSS/字体：0.12.6 起默认禁止本地文件读取，必须显式打开
wkhtmltopdf --enable-local-file-access input.html output.pdf
#    或者只放行某个目录（可重复）
wkhtmltopdf --allow /srv/assets input.html output.pdf

# 3) 纸张与页边距：A4 / 横向 / 四边边距（单位可用 mm、cm、in 等）
wkhtmltopdf -s A4 -O Landscape \
  -T 20mm -B 20mm -L 15mm -R 15mm \
  input.html output.pdf

# 4) 页眉页脚：文字版用占位符，[page] 当前页、[topage] 总页数
wkhtmltopdf \
  --header-center "月度对账单" --header-font-size 9 --header-line --header-spacing 5 \
  --footer-center "第 [page] / [topage] 页" --footer-font-size 9 --footer-spacing 5 \
  input.html output.pdf

# 5) 页眉页脚用 HTML（可以做表格、logo、多栏）
wkhtmltopdf --header-html header.html --footer-html footer.html input.html output.pdf

# 6) 封面 + 目录 + 正文：对象按命令行顺序组装
wkhtmltopdf cover cover.html toc --xsl-style-sheet my-toc.xsl body.html out.pdf

# 7) 页面靠 JS 渲染时：等它跑完（等待毫秒数）并允许慢脚本
wkhtmltopdf --javascript-delay 3000 --no-stop-slow-scripts \
  --enable-local-file-access page.html out.pdf

# 8) 按打印样式渲染（走 @media print），并禁用智能缩放让像素/DPI 比例恒定
wkhtmltopdf --print-media-type --disable-smart-shrinking input.html out.pdf

# 9) 只出一个 PDF 但带封面的情况，也可以把「封面不入目录」交给 cover 对象自动完成
#    另外可用 --title 指定 PDF 标题（不指定则用第一个文档的标题）

# 10) 截图：同门的 wkhtmltoimage
wkhtmltoimage --width 1200 input.html output.png
```

**批量**：反复启动进程很慢时，用 `--read-args-from-stdin`，每行一个任务，参数与命令行合并：

```bash
# cmds 里每行形如：input1.html out1.pdf
wkhtmltopdf --read-args-from-stdin --enable-local-file-access < cmds
```

参数多且杂（全局选项 / 页面选项 / 页眉页脚 / 目录 / 大纲），完整分组速查见
`references/options.md`；目录与大纲的定制、批量与 Serverless 细节见
`references/toc-and-batch.md`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 退出码 1，报 `ContentNotFoundError` / 本地图片、CSS、字体全丢 | 0.12.6 起**默认禁止本地文件互相读取**（`--disable-local-file-access` 是默认值） | 加 `--enable-local-file-access`，或用 `--allow <目录>` 精准放行 |
| `--header-html` / `--footer-html` / `toc` 被忽略或提示不支持 | 装的是发行版仓库里**未打补丁的 Qt 编译**，这些特性依赖上游补丁 | `wkhtmltopdf --version` 看有没有 `(with patched qt)`；没有就换成官方 Releases 的对应发行版安装包 |
| flex / grid 布局、CSS 变量全部失效，排版错乱 | 内核是 2012 年前后的 Qt WebKit，不支持现代 CSS | 页面回退到 table / float / 绝对定位；或者换渲染引擎（无头 Chromium 系、其他 HTML→PDF 工具） |
| JS 渲染的页面输出白页 | 页面还没渲染完就抓取了；或慢脚本被中断 | 加 `--javascript-delay <毫秒>`，必要时 `--no-stop-slow-scripts`；更稳妥的是用 `--window-status` 等页面自己给信号 |
| 任何一个资源 404 导致整份 PDF 生成失败 | `--load-error-handling` 默认是 `abort` | 改成 `--load-error-handling ignore`（媒体文件则是 `--load-media-error-handling`） |
| 容器/服务器里中文变成方块或整段丢失 | 系统没装对应字体，fontconfig 找不到字体 | 在镜像里装中文字体；Serverless 环境按官方做法设 `FONTCONFIG_PATH`（Lambda 层是 `/opt/fonts`） |
| Alpine 镜像里跑不起来（找不到动态库） | 通用/发行版构建依赖 glibc，Alpine 是 musl | 换 glibc 基础镜像（Debian/Ubuntu 系），或在 Alpine 上自行编译 |
| 输出 PDF 的尺寸/字号和设计稿对不上 | `--enable-smart-shrinking` 默认开启，会做智能缩放，像素与 DPI 比例不是常数 | 加 `--disable-smart-shrinking`，同时统一纸张尺寸与边距 |
| 想用管道或 `-` 传 HTML 内容 | 这个工具要的是**文件路径或 URL**，不读 stdin 内容 | 先落成临时文件再传路径；批量任务用 `--read-args-from-stdin` |
| 页眉页脚里的 `[page]` 没被替换 | 用了 `--header-html` 时占位符不是自动替换的，HTML 页眉需要自己写脚本取 URL 参数 | 按官方示例在页眉 HTML 里用 `onload` 读 `document.location.search` 再回填（详见 `references/toc-and-batch.md`） |
| 服务器有被入侵风险 | 官方警告：**不要用不可信 HTML**，其中的 JS 可以完全接管运行它的服务器 | 只渲染自己控制的 HTML；用户内容必须先消毒，并用 AppArmor/SELinux 之类的强制访问控制限制进程 |
| 升级后行为变了 | 不同发行版编译方式不同（是否打补丁、引擎版本不同） | 固定安装包来源与版本，把 `wkhtmltopdf --version` 写进部署自检 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 可以渲染 `http(s)://` 页面，并会去拉页面引用的远程图片、CSS、字体；支持 `--proxy` 与环境变量代理 |
| 读取文件 | 是 | 读取 HTML、图片、CSS、字体、页眉页脚 HTML、XSL 样式表；本地互读需 `--enable-local-file-access` 或 `--allow` |
| 写入文件 | 是 | 写出 PDF（或图片）；`--dump-outline`、`--dump-default-toc-xsl` 会额外写文件/标准输出 |
| 凭证 | 视情况 | 支持 HTTP 基本认证（`--username`/`--password`）与 `--cookie`、`--custom-header`；这些是业务侧传入的参数，不应硬编码在脚本里 |
| 子进程 / 后台常驻 | 是 | 调用方以子进程方式运行它；它本身不常驻服务，但会启动内部渲染进程 |

## 触发场景

- 「把这份 HTML 模板渲染成 PDF，要有页码和页眉页脚」
- 「给 PDF 加个封面和目录页，正文保持原有排版」
- 「服务器上没有浏览器，要出 PDF」
- 「把长网页导出成 PDF 存档」
- 「HTML 渲染成图片，做缩略图」
- 「一批 HTML 批量出 PDF，别一个个重启进程」

## 能力边界

**覆盖**：

- HTML（本地文件或 URL）→ PDF；多个页面对象按顺序合并进一个 PDF
- 封面对象（不进目录、无页眉页脚）与目录对象（基于 H 标签生成，可用 XSL 自定义样式）
- 页眉 / 页脚：文字版（左右中三段 + 占位符变量）与 HTML 版；可加分隔线、设字体与间距
- PDF 大纲（书签）与目录深度控制
- 纸张：`A4`/`A3`/`Letter`/`Legal` 等标准尺寸，或 `--page-width` / `--page-height` 自定义；方向、四边边距
- 渲染控制：JS 开关与等待、慢脚本策略、打印媒体类型、缩放、最小字号、用户样式表、视口尺寸
- 资源与网络：本地文件放行、代理、Cookie、自定义请求头、HTTP 认证、SSL 客户端证书、POST 数据
- 表单字段转成 PDF 表单（`--enable-forms`）、链接处理、灰度/低质量/图像质量与 DPI
- 同仓库的 `wkhtmltoimage`：HTML → 图片

**不覆盖**：

- PDF 的后期加工：合并/拆分/加密/加水印/压缩（要另配工具）
- 现代 Web 平台：flex/grid、CSS 变量、ES6+、WebAssembly、以及依赖现代浏览器内核的框架
- 保证与某浏览器逐像素一致：引擎老旧且不同发行版编译差异大
- 内容安全：不消毒的 HTML/JS 会带来服务器失守风险，它不做隔离
- 持续的安全更新：上游仓库已归档，最后稳定版是 2020 年的 0.12.6

## 依赖条件

- 各平台的安装包（Windows installer / macOS pkg / Linux 的 deb、rpm、pkg.tar.xz）
- 想要页眉页脚、目录、大纲这些功能，必须是**打了 Qt 补丁**的构建（官方 Releases 的包是，多数发行版仓库的包不是）
- 运行需要系统字体（fontconfig / freetype 与具体字体），中文字体要自己装
- 容器化注意：glibc 系基础镜像；Alpine 需要额外折腾
- Serverless：官方提供 Amazon Linux 2 的 lambda zip，需设 `LD_LIBRARY_PATH` 与 `FONTCONFIG_PATH`
- 上游许可为 LGPL-3.0；本 Skill 只是使用说明，不包含其源码

## 已知限制

1. 上游仓库**已归档**，不再有新功能与安全更新；稳定系列停在 0.12.6（2020-06-11）
2. 内核老旧：现代 CSS/JS 能力缺失，前端渲染型页面基本无解
3. 发行版仓库的构建常缺少补丁，同一命令在不同机器上行为不一致
4. 输出尺寸受智能缩放影响，像素级还原需要额外参数校准
5. 对不可信 HTML 没有隔离能力，官方直接建议不要这么用
6. 启动开销明显，批量任务不合并调用会浪费大量时间

## 自检清单

**执行前**

- [ ] 确认 `wkhtmltopdf --version` 里有 `(with patched qt)`（要用页眉页脚/目录时）
- [ ] 确认要渲染的 HTML **不含 flex/grid/ES6+**，也不依赖运行时异步渲染
- [ ] 如果是用户上传的 HTML：先消毒，并确认有 AppArmor/SELinux 之类的限制
- [ ] 本地资源引用是否齐全？需要时加 `--enable-local-file-access` 或 `--allow`
- [ ] 中文字体是否已安装（容器里尤其容易漏）

**执行后**

- [ ] 打开 PDF 抽查：字体、分页、页眉页脚、目录链接是否正确
- [ ] 检查退出码与 stderr；资源缺失时考虑 `--load-error-handling ignore`
- [ ] 需要印刷时确认纸张、边距、缩放（`--disable-smart-shrinking`）符合预期
- [ ] 批量场景确认没有为每个文件重复启动进程
- [ ] 记录实际使用的安装包来源与版本，避免换机器后结果不一致

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| `references/options.md` | 命令行选项分组速查与页眉页脚占位符 |
| `references/toc-and-batch.md` | 目录/大纲定制、批量与 Serverless 运行 |
| https://github.com/wkhtmltopdf/wkhtmltopdf | 上游仓库（安装与完整文档以它为准） |

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
