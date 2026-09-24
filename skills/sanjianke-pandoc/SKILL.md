---
name: sanjianke-pandoc
slug: sanjianke-pandoc
displayName: 三剪客 · 万能格式转换
description: "pandoc：万能格式转换 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "pandoc：万能格式转换 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · 万能格式转换

pandoc 是一个命令行文档转换器：Markdown、Word、HTML、LaTeX、EPUB、PPTX、ODT、reStructuredText、Org、CSV 之间互转，一条命令搞定。它内部先把文档解析成统一的 AST，再写成目标格式。

对 Agent 来说它是一个**几乎没有学习成本、但很容易踩格式细节坑**的工具：命令不复杂，难的是知道「哪些东西转换后会丢」。这份 Skill 重点写的就是后者。

**上游项目**：`pandoc`　**仓库**：https://github.com/jgm/pandoc

## 什么时候用 / 不用

**用它**：

- 「把这份 Word 转成 Markdown，我要进 Git 管起来。」
- 「十几篇 Markdown 批量出 docx / PDF / HTML。」
- 「网页内容存一份 Markdown 归档」——能直接对 URL 做读取。
- 要写论文式文档：引用、参考文献、目录、章节编号、公式，pandoc 一条命令都能配上。
- CI 里做文档流水线：同一份源文件出多种格式，或走 Lua filter 批量改 AST。
- 需要脚本化、可重复的转换——它是纯 CLI，不需要 Office、不需要联网。

**不要用它**：

- 要求**版式像素级还原**：页边距、浮动图位置、精确套版，pandoc 官方明确说它只保留结构、不保留格式细节。
- 输入是**扫描版 PDF 或图片**——pandoc 不做 OCR，那要先跑 OCR（比如 Umi-OCR / Tesseract）拿到文本。
- 要做**复杂 Word 排版再回写 Word**：往返转换会掉样式，最好一次成型。
- 需要处理 **LaTeX 宏**：自定义宏不会展开，`\newcommand` 之类要靠外部工具或先在 LaTeX 里展开。
- 环境里没有 TeX 却要出 PDF：pandoc 本身不带排版引擎，得另装（或用 `--pdf-engine` 换 HTML 系引擎）。

## 安装

Windows / macOS / Linux 都有官方安装包，下载页在 <https://github.com/jgm/pandoc/releases/latest>。以下命令来自官方安装说明：

```bash
# Windows —— winget
winget install --source winget --exact --id JohnMacFarlane.Pandoc

# Windows —— Chocolatey（顺带装配套工具）
choco install pandoc
choco install rsvg-convert python miktex     # SVG 转换 / 过滤器 / 出 PDF 用

# macOS —— Homebrew
brew install pandoc
brew install librsvg python homebrew/cask/basictex   # 可选：SVG、过滤器、LaTeX

# macOS —— MacPorts
port install pandoc

# Linux —— 发行版仓库（注意可能偏旧）
sudo apt-get install pandoc          # Debian / Ubuntu
sudo apt-get install texlive         # 需要出 PDF 时装 TeX Live

# Linux —— 官方 deb 包（更新）
sudo dpkg -i $DEB                    # $DEB 为下载到的 deb 路径

# Linux —— 官方 tarball 解到自定义目录
tar xvzf $TGZ --strip-components 1 -C $DEST

# Conda / Mamba / Pixi
conda install -c conda-forge pandoc
micromamba install pandoc
pixi global install pandoc

# Chrome OS
crew install pandoc

# Docker（官方镜像：pandoc/core 只有 pandoc，pandoc/latex 带最小 LaTeX）
docker run --rm --volume "`pwd`:/data" --user `id -u`:`id -g` pandoc/latex README.md -o README.pdf
```

装完确认版本：`pandoc --version`。

注意（官方提示）：**多套安装方式并存会出现两个 pandoc**，换安装方式前先卸载干净。另外官方和 Conda Forge 提供的静态链接二进制有个限制——**依赖 C 模块的 Lua filter 用不了**，需要这种 filter 就换安装方式。

## 常用操作

```bash
# 1) Markdown → HTML：不加 -s 只是片段，加了才是完整网页
pandoc MANUAL.txt -o fragment.html
pandoc -s MANUAL.txt -o page.html
pandoc -s --toc -c pandoc.css -A footer.html MANUAL.txt -o page.html

# 2) Markdown → Word / PPTX / ODT / EPUB
pandoc -s MANUAL.txt -o out.docx
pandoc -s MANUAL.txt -o out.pptx
pandoc -s MANUAL.txt -o out.odt
pandoc MANUAL.txt -o out.epub

# 3) Word → Markdown：把内嵌图片抽出来
pandoc -s input.docx -t markdown --extract-media=./media -o out.md

# 4) Markdown → PDF：默认用 LaTeX，中文必须换 xelatex 并指定字体
pandoc MANUAL.txt --pdf-engine=xelatex -o out.pdf
pandoc note.md --pdf-engine=xelatex -V CJKmainfont="Noto Serif CJK SC" -o note.pdf
pandoc -N --toc --pdf-engine=lualatex -V geometry=margin=1.2in note.md -o note.pdf

# 5) 管道：从标准输入读到标准输出（不落中间文件）
pandoc -f html -t markdown < page.html > page.md
curl -s https://example.com | pandoc -f html -t gfm -o page.md

# 6) 引用与参考文献（--citeproc 负责生成文献表）
pandoc -s --bibliography refs.bib --citeproc paper.md -o paper.html
pandoc -s --bibliography refs.bib --citeproc --csl ieee.csl paper.md -o paper.html
pandoc refs.bib -t csljson -o refs.json          # 参考文献格式互转

# 7) 用参考文档控制 docx 样式（先导出 pandoc 默认模板，改完再用）
pandoc --print-default-data-file reference.docx > custom-reference.docx
pandoc --reference-doc=custom-reference.docx -o out.docx input.md

# 8) 查这台机器支持什么（换版本后格式名可能不同，以实际输出为准）
pandoc --list-input-formats
pandoc --list-output-formats
pandoc --list-extensions=gfm

# 9) 批量转换（PowerShell）
Get-ChildItem *.md | ForEach-Object { pandoc -s $_.FullName -o ($_.BaseName + ".docx") }

# 10) 自定义 AST：Lua filter 是最常用的扩展方式
pandoc --lua-filter=fix.lua input.md -o output.md
```

常用参数速记：`-f` / `-r` 指定输入格式，`-t` / `-w` 指定输出格式，`-o` 输出文件（省略则写标准输出），`-s` 生成独立完整文档，`--toc` 目录，`-N` 章节编号，`-c` 外链 CSS，`-A` 追加文件到文末，`--pdf-engine` 选 PDF 引擎，`-V` 传模板变量。完整选项与格式清单见 `references/options-and-formats.md`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 输出的 HTML 缺样式、没有 `<head>` | 没加 `-s`，拿到的是片段 | 加 `--standalone`（`-s`）；要目录再加 `--toc` |
| 中文 PDF 报缺字体 / 字符不显示 / 直接报错 | 默认引擎是 LaTeX 系，大多默认引擎不支持 CJK | 换 `--pdf-engine=xelatex` 并指定 `-V CJKmainfont="..."`（或 `-V mainfont="..."`），字体必须是系统里真实存在的 |
| docx 转 Markdown 后图片全丢 | 没告诉 pandoc 把媒体抽出来 | 加 `--extract-media=./media`；转换后在 md 里核对图片相对路径 |
| 表格、图注、页边距等版式变了 | pandoc 的中间 AST 表达能力弱于 Word / LaTeX，换算本身就是有损的（官方 README 明确说明） | 转换前先跟需求方确认「结构保留、版式不保证」；样式用 `--reference-doc` 统一，而不是指望它还原 |
| `--reference-doc` 传了但样式没变 | 参考文档必须是 pandoc 生成的 docx 结构 | 先 `pandoc --print-default-data-file reference.docx > custom-reference.docx`，改这个文件再引用 |
| `--self-contained` 报未知选项 | 新版把该选项改成了 `--embed-resources` | 改用 `--embed-resources`；不确定当前版本支持什么，一律用 `pandoc --help` 核对 |
| 从网页抓下来的公式 / 代码块样式丢失 | HTML 里的数学与高亮依赖前端脚本 | 输出 HTML 时加 `--mathjax`（或 `--katex` / `--mathml`）；代码块用 `--syntax-highlighting=样式名` |
| 在 GitHub 上渲染出来格式乱 | 默认输出是 pandoc 自家 Markdown，扩展语法 GitHub 不认 | 面向 GitHub 用 `-t gfm`；Pandoc 扩展语法（如 fenced div）只在 pandoc 生态里有效 |
| 同一台机器上 pandoc 版本忽新忽旧 | 多套安装方式共存，PATH 里命中了另一个 | `pandoc --version` 确认；官方建议换方式前先卸载旧的 |
| Lua filter 报找不到 C 模块 | 静态链接版本（官方二进制、Conda Forge）不支持依赖 C 模块的 Lua filter | 换非静态安装方式（如系统包管理器 / 自行编译），或改用纯 Lua 实现的 filter |
| 批量循环里文件名带空格报错 | 没加引号 | PowerShell 用 `$_.FullName` 并整体加引号；路径含空格务必加引号 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 通常否 | 本地文件转换不需要网络；只有给的是 URL（如 `pandoc -f html https://...`）或拉取远程资源时才联网 |
| 读取文件 | 是 | 读取输入文档、模板、CSS、参考文献文件、Lua filter |
| 写入文件 | 是 | 写出目标文档、`--extract-media` 抽出的图片、中间产物 |
| 凭证 | 否 | 不需要账号、Key 或登录 |
| 子进程 / 后台常驻 | 视情况 | 出 PDF 时会调用外部排版引擎（LaTeX / typst / wkhtmltopdf 等）；pandoc 本身是短时进程，不需要常驻 |

## 触发场景

- 「把这份 Word 转成 Markdown。」
- 「帮我把这批 Markdown 一起转成 PDF 和 docx。」
- 「这份文档要加目录和章节编号，再导 PDF。」
- 「把网页内容存成 Markdown。」
- 「引用和参考文献要按 IEEE 格式排。」
- 「我有一份 docx 模板，转换出来的 Word 要套它的样式。」

## 能力边界

**覆盖**：

- 输入与输出各几十种格式：Markdown 各变体（pandoc / gfm / commonmark / MultiMarkdown）、docx、odt、pptx、xlsx / csv / tsv、html、latex、epub / fb2、rst、org、asciidoc、mediawiki / dokuwiki / jira 等 wiki 标记、man / mdoc、ipynb、typst、json / xml / native（AST 形式）、多种参考文献格式（bibtex / biblatex / csljson / ris / endnotexml）等。
- PDF 输出（走外部引擎：LaTeX 系、HTML 系或 typst 等，具体可用引擎取决于安装情况）。
- 引用与文献表（`--citeproc` + `--bibliography` + `--csl`）、目录、章节编号、模板变量、自定义 CSS。
- 数学（MathML / MathJax / KaTeX / WebTeX）、代码语法高亮、多种 HTML 幻灯片输出（reveal.js / slidy / dzslides 等）、beamer 幻灯片。
- AST 级别的扩展：Lua filter、自定义 reader / writer。
- URL 直接作为输入读取。
- Docker 镜像（`pandoc/core`、`pandoc/latex`）与 CI 集成。

**不覆盖**：

- 不做 OCR：扫描件、图片必须先转成文本。
- 不内嵌任何排版引擎，出 PDF 需要外部程序。
- 不保证无损往返：结构可保，版式细节（页边距、浮动体、精确字号）不保。
- 不展开 LaTeX 宏，也不执行文档里的代码。
- 不做图片格式转换本身（SVG 之类要靠 `rsvg-convert` 等外部工具配合）。
- 不提供图形界面（有在线试用页，但不是本地 GUI）。

## 依赖条件

- 本体是单一可执行文件，无运行时依赖；Windows / macOS / Linux 均有官方包。
- 出 PDF 需额外装排版引擎：LaTeX 系（TeX Live / MiKTeX / BasicTeX / TinyTeX）或其他 `--pdf-engine` 支持的引擎。
- 使用 Python 过滤器需要 Python；渲染 SVG 需要 librsvg 之类的工具。
- 静态链接版本不支持依赖 C 模块的 Lua filter。
- 不需要账号或 Key。

## 已知限制

- 官方明确说明：中间 AST 的表达能力弱于许多源格式，复杂表格等元素可能对不齐，**从表达能力更强的格式转换过来必然有损**。
- PDF 输出质量与所用引擎强相关，LaTeX 报错信息通常来自引擎而不是 pandoc，需要看引擎日志。
- PPTX 输出适合从简单大纲生成，别指望还原设计稿；复杂版式要另想办法。
- 选项名会随大版本变化（例如 `--self-contained` 与 `--embed-resources`），脚本里用到较新选项时应在启动时用 `pandoc --help` 做一次能力探测。
- 静态构建下 Lua filter 能力受限。
- 同一文档多格式输出时，各自的样式需要在模板 / 参考文档层面分别维护。

## 自检清单

执行前：

- [ ] `pandoc --version` 确认版本，确认 PATH 里命中的是预期那份安装。
- [ ] 明确输入格式与输出格式（拿不准就 `pandoc --list-input-formats` / `--list-output-formats`）。
- [ ] 出 PDF 前先确认目标引擎已安装，中文字体名与系统实际字体名一致。
- [ ] docx → Markdown 的任务，先定好 `--extract-media` 的输出目录。

执行后：

- [ ] 命令退出码为 0，目标文件存在且体积合理（不是 0 字节）。
- [ ] 抽查转换结果：标题层级、表格、图片、公式、引用是否还在。
- [ ] 中文文档确认没有乱码、没有丢字。
- [ ] 向需求方说明哪些版式细节没有保留（有损点是预期的，不是 bug）。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| `references/options-and-formats.md` | 常用选项、格式名清单、扩展语法速查 |
| https://github.com/jgm/pandoc | 上游仓库（安装与完整文档以它为准） |

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
