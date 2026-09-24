---
name: sanjianke-typst
slug: sanjianke-typst
displayName: 三剪客 · 现代排版出 PDF
description: "typst：现代排版出 PDF 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "typst：现代排版出 PDF 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档处理
---

# 三剪客 · 现代排版出 PDF

用一份纯文本源文件，编出一份排版规整的 PDF——公式、目录、图表、参考文献、页眉页脚、页码编号全都由排版系统负责，你只写内容。

它的定位可以一句话说清：**目标是把 LaTeX 能做的事做得更简单、更快**。源文件基于标记语言（`= 标题` 就是一级标题，`_斜体_` 就是斜体），需要编程能力时直接在同一份文件里写脚本和函数；编译器是**增量编译**的，改一行再编译通常就是一瞬间，`typst watch` 可以边写边看。核心特性包括：常用排版任务的内建标记、万能的自定义函数、紧耦合的脚本系统、数学排版、参考文献管理、以及出错时相对友好的报错信息。

**它是什么、不是什么**：这个仓库包含的是 **Typst 编译器与命令行工具**——本地编译排版文档所需的一切。官方另有一个网页协作编辑器（那是另一个产品，本包不涉及）。所以本地没有图形界面，工作方式是"改 `.typ` → 跑命令 → 看 PDF"。

**为什么值得单独写一个包**：很多"批量生成 PDF"的需求（发票、合同、证书、周报、成绩单、数据报告）本质上就是"模板 + 数据"，而 Typst 把这两件事放在同一个文件里解决——数据可以直接从 JSON/CSV 读进来，用循环铺满表格，不需要在 Python 里拼 HTML 再交给浏览器打印。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视用法 | 只有两处需要出网：`typst update` 自更新（从上游 release 拉二进制），以及渲染时引用 `@preview/...` 的模板/包（从 Typst Universe 下载）。纯本地文档、不用外部包时**完全离线** |
| 读取文件 | 是（必需） | 读 `.typ` 源文件；以及文档里引用的图片、CSV/JSON/YAML 数据、`.bib` 文献库；另外读系统字体、`--font-path` 指定目录、包目录（`--package-path` / `--package-cache-path`） |
| 写入文件 | 是（必需） | 写出 PDF / PNG / SVG / HTML（`--format` 或按扩展名推断）；`--deps` 写依赖清单、`--timings` 写性能 JSON、`--make-deps` 写 Makefile 片段 |
| 凭证 | 否 | 不需要账号或 Key。企业代理下自签证书用 `--cert`（或环境变量 `TYPST_CERT`）指定 CA 证书 |
| 子进程 / 后台常驻 | 视用法 | CLI 通常是一次性进程；`typst watch` 会常驻监听文件变化，并在 HTML 导出场景可能起一个本地 HTTP 服务（默认在 3000–3005 中挑第一个空闲端口，可用 `--no-serve` 关掉） |
| 本地端口 | 视用法 | 仅 `typst watch` 的 HTML 预览场景会监听本地端口；纯 PDF 编译不开端口 |

**可复现与合规**：构建产物默认会写入创建时间戳，若要做**可复现构建**，用 `--creation-timestamp`（或 `SOURCE_DATE_EPOCH` 环境变量）固定它。另外，即使不生产 PDF/UA-1，Typst 默认也会写出**带标签的 PDF**（为无障碍提供基线）；想减小体积可以关掉，但会牺牲无障碍结构。

## 触发场景

- "我要按模板批量生成 200 份 PDF 证书/发票/工牌"——同一份 `.typ` + 数据文件，命令行循环跑。
- "写一份带公式和参考文献的论文/技术报告"——数学、引用、目录都是内建能力。
- "Markdown 转 PDF 出来的排版太丑，要控制页边距、字体、页眉页脚、分栏"——直接写规则控制版式。
- "要输出符合 PDF/A 或 PDF/UA-1 的归档/无障碍文档"——`--pdf-standard`。
- "要 PDF，但不想装几个 G 的 TeX 发行版"——Typst 是单个二进制。
- "只想要第 3 到第 6 页" / "导出成 PNG 插图"——`--pages` 与 `--format png/svg`。
- "把文档里的某个元素抽出来给程序用"——`typst eval`。
- "CI 里做文档构建，要知道这份文档依赖了哪些文件"——`--deps` / `--deps-format`。

## 什么时候用 / 不用

**用它**：

1. **模板 + 数据 → 批量 PDF**。数据驱动排版是它最舒服的场景，比"HTML 模板 + headless 浏览器打印"更可控：分页、页码、表格跨页、目录都能算准。
2. **要精细控制版式**。页边距、字号、行距、页眉页脚、分栏、首行缩进，用 set/show 规则声明清楚，不用和 CSS 打印规则打架。
3. **学术类文档**。数学公式、编号、交叉引用、参考文献、目录是内建能力，不用装一堆宏包。
4. **构建速度快**。增量编译使得"改一行、重出一版"几乎无感；`typst watch` 边写边看。
5. **部署轻**。单个二进制，没有 TeX 发行版的体积与依赖树；Docker 里也能直接跑官方镜像。
6. **要合规输出**。PDF/A 系列、PDF/UA-1、PDF 1.4–2.0 都能在命令行声明；默认还会产出带标签的 PDF。
7. **文档源要进版本库**。纯文本、可 diff、可 code review。

**不要用它**：

1. **要输出 Word / PPT / Excel**。Typst 只出 PDF、PNG、SVG、HTML（以及仍在开发中的 bundle），**不导出 Office 格式**；这类需求得走别的转换链。
2. **团队/期刊强制要求指定 LaTeX 模板**。要是交付方只收 `.tex` 编译结果或要求用某个 LaTeX 宏包，Typst 不能直接替代（它不解析 `.tex`）。
3. **依赖某个 LaTeX 生态独有的宏包**。专业绘图、化学结构式、特定学科的宏包在 Typst 里不一定有对应实现。
4. **要所见即所得编辑**。本地 CLI 没有 GUI；官方网页编辑器是独立产品，不在本包范围。
5. **主业是网页/HTML**。HTML 导出目前仍属开发中的特性（需要用 `--features` 打开，行为随版本变化），不要拿它当网页生成方案。
6. **只是偶尔把一段 Markdown 转成 PDF 看看**。装一个排版系统属于过度设计，用现成的轻量转换就够了。

## 安装

### 官方预编译二进制（推荐，跨平台）

到项目的 releases 页面下载对应平台的压缩包，解压后把二进制放进 `PATH`。之后可以直接自更新：

```bash
typst update              # 更新到最新版
typst update 0.13.0       # 指定版本（降级需要 --force）
typst update --revert     # 回退到上次更新前的版本
```

### 包管理器

```bash
# macOS
brew install typst

# Windows
winget install --id Typst.Typst

# Linux（snap，版本可能落后于最新 release）
sudo snap install typst
```

Linux 各发行版的包可用情况可以在 Repology 上查（见下方链接）。**官方明确提示：包管理器里的版本可能落后于最新 release**，遇到语法或参数不认的情况，先 `typst --version` 对一下版本。

### Rust 工具链

```bash
cargo install --locked typst-cli                                  # 最新发布版
cargo install --git https://github.com/typst/typst --locked typst-cli   # 开发版
```

### Nix

```bash
nix-shell -p typst
nix run github:typst/typst-flake -- --version
```

### Docker

```bash
docker run --rm ghcr.io/typst/typst:latest --help

# 实际编译（把当前目录挂进容器）
docker run --rm -v "$PWD:/work" -w /work ghcr.io/typst/typst:latest compile doc.typ
```

### 从源码构建

```bash
git clone https://github.com/typst/typst
cd typst
cargo build --release
# 产物在 target/release/
```

### 装完自检

```bash
typst --version
typst info          # 打印它用到的环境变量与默认值，排查配置问题很有用
typst fonts         # 看它到底能发现哪些字体
typst help
typst help compile  # 看某个子命令的完整参数
```

## 常用操作

### 1. 编译

```bash
typst compile file.typ                  # 在当前目录生成 file.pdf
typst compile src.typ out/report.pdf    # 指定输出路径
typst c file.typ                        # c 是 compile 的别名
typst compile - -  < file.typ > file.pdf  # 从 stdin 读、往 stdout 写
```

输出格式默认按扩展名推断，也可以显式指定：

```bash
typst compile --format pdf  doc.typ out.pdf
typst compile --format png  doc.typ page.png     # 单页
typst compile --format svg  doc.typ page.svg     # 单页
typst compile --format html doc.typ out.html     # HTML 导出属开发中特性，见"常见坑"
```

**多页 PNG/SVG 必须给页码模板**，否则报错：

```bash
typst compile --format png doc.typ "page-{p}.png"          # page-1.png, page-2.png ...
typst compile --format png doc.typ "page-{0p}-of-{t}.png"  # page-01-of-10.png ...（0p 补零，t 是总页数）
typst compile --format png --ppi 300 doc.typ "page-{p}.png" # PNG 默认 144 PPI
```

### 2. 边写边编译

```bash
typst watch file.typ          # 监听源文件变化并自动重编（增量编译，比重跑 compile 快）
typst w file.typ              # w 是别名
typst watch --no-fullscreen file.typ   # 不让 watcher 接管终端，只打普通日志（适合 CI 日志/重定向）
```

### 3. 只导出部分页

```bash
typst compile --pages 2,5 doc.typ out.pdf     # 只要第 2、5 页
typst compile --pages 2,3-6,8- doc.typ out.pdf # 第 2 页、3~6 页、第 8 页及之后
```

页号是**从 1 开始的物理页号**，不受文档内部页码计数器影响；写 `0` 会直接被拒绝。

### 4. 把参数传进文档（模板化的关键）

```bash
typst compile -i name=世界 -i version=1.2.0 doc.typ out.pdf
```

文档里通过 `sys.inputs` 读：

```typst
#let name = sys.inputs.at("name", default: "匿名")
你好，#name ！当前版本 #sys.inputs.at("version")
```

注意传进来的**都是字符串**，要当数字用需要自己转换。

### 5. 用模板起步

```bash
typst init @preview/charged-ieee my-paper     # 从 Typst Universe 拉模板并展开到 my-paper/
typst init @preview/charged-ieee:0.1.0 proj   # 锁定模板版本（不加则用最新版）
```

模板也支持本地路径；`typst init` 会把模板文件展开到 `dir`（默认用模板名）。

### 6. 字体管理（中文场景必看）

```bash
typst fonts --font-path ./fonts              # 列出系统字体 + 指定目录里发现的字体
typst fonts --font-path ./fonts --variants    # 连字体的样式变体一起列出

# 多个目录用系统路径分隔符（Linux/macOS 是 :，Windows 是 ;）
typst compile --font-path ./fonts --font-path ./assets/fonts doc.typ

# 也可以用环境变量
TYPST_FONT_PATHS=./fonts typst compile doc.typ

# 容器/CI 里想避免系统字体干扰复现，可以只认自己给的字体
typst compile --font-path ./fonts --ignore-system-fonts doc.typ
```

### 7. PDF 标准与无障碍

```bash
typst compile --pdf-standard a-2b,ua-1 doc.typ out.pdf   # 归档 + 无障碍
typst compile --pdf-standard 1.7 doc.typ out.pdf         # 指定 PDF 版本
typst compile --pdf-tagged=false doc.typ out.pdf         # 关掉标签（体积更小，牺牲无障碍基线）
```

可选标准：`1.4` / `1.5` / `1.6` / `1.7` / `2.0`，`a-1b` / `a-1a` / `a-2b` / `a-2u` / `a-2a` / `a-3b` / `a-3u` / `a-3a` / `a-4` / `a-4f` / `a-4e`，以及 `ua-1`。

### 8. 给构建系统用：依赖清单与计时

```bash
typst compile --deps deps.json --deps-format json doc.typ     # 依赖了哪些文件
typst compile --deps - --deps-format zero doc.typ             # 写到 stdout，NUL 分隔（路径最稳）
typst compile --deps-format make --make-deps doc.d doc.typ    # 生成 Makefile 片段
typst compile --timings timings.json doc.typ                  # 性能计时，可喂给 Perfetto 类工具
```

### 9. 抽文档里的东西给程序用

```bash
typst eval "#1 + 2"                        # 直接算一段 Typst 表达式（默认 JSON 输出）
typst eval --in doc.typ "#outline"         # 在某个文档的上下文里取值
typst eval --format raw --in doc.typ "#sys.inputs.at(\"name\")"   # raw 只支持字符串/字节
```

`query` 子命令仍然存在但已标记为废弃，官方建议用 `eval`。

### 10. 可复现构建与并行度

```bash
typst compile --creation-timestamp 0 doc.typ out.pdf   # 固定创建时间，产物可复现
typst compile --jobs 1 doc.typ out.pdf                 # 关掉并行（排查/复现问题时用）
typst compile --diagnostic-format short doc.typ out.pdf # 诊断信息改短格式，适合日志
```

### 11. 容器里批量出 PDF

```bash
docker run --rm -v "$PWD:/work" -w /work ghcr.io/typst/typst:latest \
  compile -i title=季度报告 --font-path /work/fonts report.typ out/report.pdf
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 中文/日文渲染成方框，或报字体找不到 | 系统里没有该字族，或字族名字写错；容器镜像里通常只有极少数字体 | `typst fonts` 看它发现了什么；把字体目录用 `--font-path` 传进去（或设 `TYPST_FONT_PATHS`）；文档里 `#set text(font: "你的字族名")` 要用**真实字族名**而不是文件名 |
| 导出多页 PNG/SVG 时报错 | PNG/SVG 是**一页一个文件**，文档渲染出多页时输出路径里必须带页码模板 | 用带占位符的输出名：`"page-{p}.png"` / `"page-{0p}-of-{t}.png"`（`{p}` 页号、`{0p}` 补零页号、`{t}` 总页数） |
| `--pretty true` 报参数错误 | 该参数要求用等号连接 | 写 `--pretty=true`（同理 `--open=程序名` 也必须用等号） |
| 文档里读 `-i` 传进来的值当数字用出错 | `sys.inputs` 里的值**全是字符串** | 自己转换：`#let n = int(sys.inputs.at("n"))`；取不到时给默认值 `sys.inputs.at("k", default: "0")` |
| 想引用项目外的文件（`../data.csv`、绝对路径）报错 | Typst 限制文件访问范围，默认根目录是项目目录 | 用 `--root` 指定项目根（或 `TYPST_ROOT`），把要用的文件放在根之内 |
| HTML 导出/`bundle` 相关参数时好时坏 | HTML、bundle、部分无障碍能力**属于开发中特性**，需要用 `--features html` 之类的开关打开，且随时可能变 | 不要把 HTML 导出放进稳定生产链路；要用就锁定 Typst 版本并读对应版本文档；以 `typst help compile` 的输出为准 |
| 包管理器装的版本不认识新语法/新参数 | 官方明确提示包管理器版本可能落后于最新 release | `typst --version` 对版本；用 `typst update` 或改用官方 release 二进制 |
| 拉 `@preview/...` 模板超时或失败 | 渲染时需要联网从 Typst Universe 下载包 | 联网环境重试；离线/内网环境预先准备好包目录，用 `--package-path` / `--package-cache-path` 指向本地（两者都有同名环境变量） |
| 企业代理/自签证书下联网失败 | 证书链不被信任 | 用 `--cert <CA 证书路径>` 或环境变量 `TYPST_CERT` 指定 CA |
| `--pages 0` 报错 | 页号从 1 开始 | 页号是物理页号，从 1 起；范围写法 `1-3` / `5-` / `-2` 都支持 |
| 每次构建出的 PDF 二进制不一致，没法做产物校验 | 文档创建时间戳被写进了产物 | 用 `--creation-timestamp`（或 `SOURCE_DATE_EPOCH`）固定时间戳 |
| `-i key=` 传空值/缺等号报错 | 参数必须是 `key=value` 形式，且 key 不能为空 | 检查 `-i` 写法：`-i name=value`，等号不能省 |
| 开的 PDF 体积明显偏大 | 默认会写**带标签的 PDF**（为了无障碍基线），即使不要求 PDF/UA-1 | 接受无障碍结构就留着；纯粹想减体积可 `--pdf-tagged=false`（旧参数 `--no-pdf-tags` 已废弃） |

## 能力边界

**覆盖**：

- **从标记语言编译出成品文档**：源文件为纯文本，内建标题、强调、列表、原始文本、引用等常用标记，其余用函数表达。
- **输出格式**：PDF、PNG、SVG、HTML（开发中）、bundle（开发中）；支持从 stdin 读、往 stdout 写，便于放进管道。
- **页级控制**：用 `--pages` 只导出指定页（支持 `2,3-6,8-` 这种逗号 + 区间写法）。
- **参数化文档**：`-i key=value` 注入变量，文档里通过 `sys.inputs` 读取，这是"模板 + 数据批量出 PDF"的基础。
- **脚本能力**：变量、函数、递归、循环、数组与字典操作、字符串处理，都在文档内直接写，不需要外部预处理。
- **数学排版与参考文献**：公式、编号、交叉引用、文献管理为内建能力。
- **版式控制**：set 规则配置元素属性（页面尺寸、标题编号等），show 规则完全重定义元素外观；页面尺寸支持 `auto` 跟随内容。
- **模板与包生态**：`typst init @preview/<name>` 拉模板并可锁版本；包目录位置可自定义。
- **字体管理**：`--font-path` 追加字体目录（可用环境变量），`typst fonts` 列出发现结果，`--ignore-system-fonts` / `--ignore-embedded-fonts` 控制字体来源（利于复现）。
- **PDF 合规**：`--pdf-standard` 支持 PDF 1.4–2.0 与 PDF/A-1a/1b/2a/2b/2u/3a/3b/3u/4/4f/4e、PDF/UA-1；默认产出带标签 PDF，可用 `--pdf-tagged=false` 关闭。
- **工程化能力**：依赖清单（`--deps`，json/zero/make 三种格式，可配合 `--make-deps`）、性能计时（`--timings`）、诊断格式选择（`--diagnostic-format`）、并行度（`--jobs`）、可复现时间戳、`watch` 增量重编、`eval` 取值、`completions` 生成补全、`info` 打印环境与默认值。
- **部署形态**：预编译二进制、brew / winget / snap / Repology 覆盖的发行版包、cargo、Nix、官方 Docker 镜像；也可从源码自行构建。

**不覆盖**：

- **不导出 Office 格式**：没有 docx / pptx / xlsx 输出。
- **不解析 LaTeX**：不读 `.tex`，也没有 LaTeX 宏包兼容层；现有 LaTeX 项目不能直接搬。
- **不含 GUI**：本地只有一个命令行程序；所见即所得的网页编辑器是另一个产品。
- **不是 Markdown 渲染器**：没有"输入 Markdown"这一模式，标记语法是它自己的。
- **不做 PDF 后处理**：不合并、不拆分、不加密、不签名、不做 OCR、不做压缩优化——这些要另外的工具。
- **不提供字体**：只使用系统字体与你显式提供的字体目录，不下载字体。
- **不提供云渲染**：本 Skill 不代理任何在线编译服务，不内嵌 Key，不代收费用。
- **不保证 PDF 合规自动达成**：`--pdf-standard` 是"按该标准约束编译"，文档本身的结构（标题层级、替代文本、标签信息）不满足时仍会失败——合规是内容和参数共同的结果。

## 依赖条件

| 项 | 要求 |
|---|---|
| 操作系统 | Windows / macOS / Linux，官方提供多平台预编译二进制 |
| 运行时 | **不需要 TeX 发行版**；预编译二进制零依赖。走 cargo 路线才需要 Rust 工具链 |
| 字体 | 需要字体才能排版；CJK 文档必须自备中文字体（系统装好或用 `--font-path` 指定目录） |
| 网络 | 仅 `typst update` 与使用 `@preview/...` 包/模板时需要；纯本地渲染可完全离线 |
| 磁盘 | 二进制体积小；包缓存与字体目录另行占用，可用 `--package-path` / `--package-cache-path` 指定位置 |
| 账号 / Key | **不需要**，无费用 |
| Docker（可选） | 官方镜像 `ghcr.io/typst/typst`；容器内通常缺字体，需挂载字体目录 |
| CPU | `--jobs` 控制并行度，默认用满 CPU；排查问题时可设 1 |

## 已知限制

- **包管理器版本滞后**：官方明确说明各发行版/包管理器里的 Typst 可能不是最新版。新语法、新参数看不见时，先确认版本。
- **HTML / bundle 仍是开发中特性**：需要通过 `--features` 之类开关启用，接口与行为随版本变化，不适合放进必须稳定的生产链路。
- **PNG/SVG 一页一文件**：多页文档必须给带页码占位符的输出路径，不能指望输出一个多页图片。
- **不导出 Office 格式**：交付方要求 docx/pptx 时只能另选方案。
- **不读 LaTeX**：迁移是重写，不是转换。
- **CLI 无图形界面**：预览靠 `watch` + PDF 阅读器，或外部编辑器插件。
- **合规不等于参数**：PDF/A、PDF/UA 需要内容侧也满足语义要求，参数只是强制约束。
- **文件访问受根目录限制**：默认只能在项目根内引用文件，跨目录要用 `--root` 重新划定。
- **`query` 已废弃**：仍可用但官方建议改用 `eval`，新脚本不要再用 `query`。

## 自检清单

执行前：

- [ ] `typst --version` 记下版本；参数与语法写法与该版本匹配（尤其是 HTML/bundle 这类开发中特性）。
- [ ] 目标输出格式明确：PDF / PNG / SVG / HTML（后者开发中）；多页图片已准备好带 `{p}` / `{0p}` / `{t}` 的输出名。
- [ ] 文档需要的字体确实存在：`typst fonts` 能看到，或用 `--font-path` 指了目录（CJK 尤其要查）。
- [ ] 数据与参数怎么进文档已定好：`-i key=value` + `sys.inputs`，并记住读出来是字符串。
- [ ] 文档里引用的图片、CSV/JSON、`.bib` 都在项目根之内（否则要设 `--root`）。
- [ ] 需要联网吗？要拉 `@preview` 包就确认网络与证书（必要时 `--cert`）；要离线就先备好包目录。
- [ ] 是否需要 PDF 合规（PDF/A、PDF/UA-1）？需要就明确写 `--pdf-standard`，并确保文档语义结构到位。
- [ ] 是否需要可复现产物？需要就固定 `--creation-timestamp`。

执行后：

- [ ] PDF/图片文件真的生成、非空、页数符合预期。
- [ ] 抽查渲染结果：中文有没有方框、公式有没有乱、表格有没有跨页断裂、目录页码对不对。
- [ ] 用了 `--pages` 的话确认导出的是**物理页号**对应的页，而不是文档里显示的页码。
- [ ] 批量场景：每份文档的输出路径互不覆盖，参数注入正确，抽查 2~3 份成品。
- [ ] 产物与中间文件（deps json、timings json、临时 PNG）按需保留或清理；涉及敏感数据的文档注意输出目录。
- [ ] 若声明了 PDF 标准，用合规检查工具再验一遍，别只信编译没报错。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/typst-syntax.md` | 常用标记与脚本写法：标题/强调/列表/公式/引用、set 与 show 规则、读 JSON/CSV 铺表格、模板与数据驱动出 PDF 的骨架 |
| `README.md` | 包说明 |
| https://github.com/typst/typst | 上游仓库（安装与完整文档以它为准） |
| https://typst.app/docs/ | 官方文档：教程、语法与函数参考 |
| https://typst.app/universe/ | 官方模板与包目录（`@preview/...` 来源） |

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
