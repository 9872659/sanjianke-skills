# pandoc 选项与格式速查

格式名与选项来自上游 README 与官方示例页。**大版本之间选项名可能变化**，脚本里用到新选项时请用 `pandoc --help` 做一次探测，或直接查官方 User's Guide。

## 一、核心选项

| 选项 | 作用 |
|---|---|
| `-f FORMAT` / `-r FORMAT` | 指定输入格式（reader） |
| `-t FORMAT` / `-w FORMAT` | 指定输出格式（writer） |
| `-o FILE` | 输出到文件；省略则写到标准输出 |
| `-s` / `--standalone` | 生成独立完整文档（带 head、模板包装） |
| `--toc` / `--toc-depth=N` | 生成目录 / 限定目录层级 |
| `-N` / `--number-sections` | 章节自动编号 |
| `-c FILE` / `--css=FILE` | 输出 HTML 时外链 CSS，可重复 |
| `-A FILE` | 文末追加内容（如页脚 HTML） |
| `-H FILE` / `--include-in-header` | 插入到 head 区 |
| `--template=FILE` | 用自定义模板；`-D FORMAT` 可打印默认模板 |
| `-V KEY=VAL` / `--variable` | 传给模板的变量，如 `geometry=margin=1.2in` |
| `--metadata KEY=VAL` | 设置文档元数据 |
| `--pdf-engine=NAME` | 出 PDF 时使用的排版引擎 |
| `--reference-doc=FILE` | docx / pptx / odt 的样式参考文档 |
| `--extract-media=DIR` | 把内嵌媒体抽到指定目录 |
| `--embed-resources` | 把图片等资源内嵌进 HTML（旧版对应 `--self-contained`，新版已更名；以 `--help` 为准） |
| `--mathjax` / `--katex` / `--mathml` / `--webtex` | HTML 输出的数学渲染方式 |
| `--syntax-highlighting=STYLE` | 代码高亮风格（新版名称；更早版本为 `--highlight-style`） |
| `--citeproc` | 处理引用并生成参考文献表 |
| `--bibliography=FILE` | 参考文献库（bib / biblatex / json / yaml 等） |
| `--csl=FILE` | 引用样式文件 |
| `--lua-filter=FILE` | 应用 Lua filter 修改 AST |
| `--filter=CMD` | 应用外部 JSON filter |
| `--wrap=none` / `--wrap=auto` | 控制输出换行方式 |
| `--columns=N` | 输出行宽 |
| `-i` / `--incremental` | 幻灯片列表逐条显示 |
| `--list-input-formats` | 列出本机支持的输入格式 |
| `--list-output-formats` | 列出本机支持的输出格式 |
| `--list-extensions=FORMAT` | 列出某格式的扩展开关 |
| `--print-default-data-file=FILE` | 导出内置数据文件（如 `reference.docx`） |

## 二、常用输入格式（reader）

Markdown 家族：`markdown`（pandoc 自家）、`markdown_strict`、`markdown_phpextra`、`markdown_mmd`、`commonmark`、`commonmark_x`、`gfm`（`markdown_github` 已废弃）。
文档类：`docx`、`odt`、`epub`、`fb2`、`html`、`latex`、`rst`、`org`、`asciidoc`、`textile`、`creole`、`muse`、`t2t`、`typst`、`ipynb`、`csv`、`tsv`、`xlsx`、`pptx`。
Wiki 与结构化：`mediawiki`、`dokuwiki`、`tikiwiki`、`twiki`、`vimwiki`、`jira`、`docbook`、`jats` / `bits`、`opml`、`haddock`、`pod`、`man`、`mdoc`。
参考文献：`bibtex`、`biblatex`、`csljson`、`ris`、`endnotexml`。
AST：`json`、`xml`、`native`。

## 三、常用输出格式（writer）

文档类：`docx`、`odt`、`pdf`、`epub` / `epub3` / `epub2`、`fb2`、`rtf`、`plain`、`ansi`、`icml`、`tei`、`opendocument`、`chunkedhtml`（多文件 HTML 打包）。
Markup：`html` / `html5`、`html4`、`latex`、`context`、`typst`、`markdown`（及 `_strict` / `_phpextra` / `_mmd`）、`commonmark` / `commonmark_x`、`gfm`、`rst`、`org`、`asciidoc` / `asciidoc_legacy`、`textile`、`t2t`、`markua`、`djot`、`vimdoc`、`man`、`ms`、`texinfo`。
Wiki 与 XML：`mediawiki`、`dokuwiki`、`jira`、`xwiki`、`zimwiki`、`docbook4` / `docbook5`、`jats_*`、`opml`。
幻灯片：`pptx`、`beamer`、`revealjs`、`slidy`、`slideous`、`dzslides`、`s5`。
参考文献：`bibtex`、`biblatex`、`csljson`。
其它：`json` / `xml` / `native` 输出 AST；BBCode 家族（`bbcode` 及 `bbcode_phpbb` / `bbcode_fluxbb` / `bbcode_steam` / `bbcode_hubzilla` / `bbcode_xenforo`）。

注意部分格式是单向的：`csv`、`tsv`、`xlsx`、`ris`、`endnotexml` 只能读不能写；`pdf`、`plain`、`ansi`、`chunkedhtml`、`html4`、`epub2` 只能写不能读。用 `pandoc --list-input-formats` / `--list-output-formats` 可以确认真实能力。

## 四、格式扩展的写法

在格式名后用 `+扩展` 打开、`-扩展` 关闭，可叠加：

```bash
pandoc -f markdown+tex_math_dollars+footnotes -t gfm input.md -o out.md
pandoc --list-extensions=gfm          # 查某个格式有哪些扩展
```

## 五、按任务挑命令

**Word 进 Git**：

```bash
pandoc -s report.docx -t gfm --extract-media=./assets -o report.md
```

**Markdown 出多种交付物**：

```bash
pandoc -s doc.md -o doc.html --toc --css=style.css
pandoc -s doc.md -o doc.docx --reference-doc=company-reference.docx
pandoc doc.md -o doc.pdf --pdf-engine=xelatex -V CJKmainfont="Noto Serif CJK SC" --toc -N
```

**网页归档**：

```bash
pandoc -f html -t gfm https://example.com/article -o article.md
```

**幻灯片**：

```bash
pandoc -t beamer slides.md -o slides.pdf
pandoc -s --mathjax -i -t revealjs slides.md -o slides.html
```

**学术文档**：

```bash
pandoc -s --citeproc --bibliography refs.bib --csl ieee.csl paper.md -o paper.html
pandoc refs.bib -t csljson -o refs.json
```

**Jupyter 笔记本**：

```bash
pandoc notebook.md -o notebook.ipynb
```

**AST 调试（看中间结构长什么样）**：

```bash
pandoc -t native input.md
pandoc -t json input.md
```

## 六、Docker 与 CI

```bash
# 只要 pandoc
docker run --rm --volume "`pwd`:/data" --user `id -u`:`id -g` pandoc/core input.md -o output.docx

# 要出 PDF（镜像是 pandoc/latex，自带最小 LaTeX）
docker run --rm --volume "`pwd`:/data" --user `id -u`:`id -g` pandoc/latex README.md -o README.pdf
```

GitHub Actions 与 GitLab CI 的现成示例见上游跨平台示例仓库（链接见官方安装页的 GitHub Actions / GitLab CI/CD 小节）。
