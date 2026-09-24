---
name: sanjianke-pdfcpu
slug: sanjianke-pdfcpu
displayName: 三剪客 · Go PDF 处理 CLI
description: "pdfcpu：Go PDF 处理 CLI 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "pdfcpu：Go PDF 处理 CLI 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - PDF
  - Go
  - CLI
---

# 三剪客 · Go PDF 处理 CLI

一个装在本地就自带全部能力的 PDF 命令行工具：合并、拆分、裁剪、旋转、加密解密、加水印、
压体积、提图提字、看元数据，全都不依赖外部服务，也不依赖 Java 或 Office。它是单文件可执行程序，
扔进 PATH 就能用，最适合放进批处理脚本里跑成百上千个 PDF。

它的强项是「重排与治理」——把一堆散 PDF 拼成一本、按页范围切出来、统一加密、统一盖戳；
弱项是「理解内容」——它不认表格结构、不认版式语义，也不会帮你把 PDF 转成 Word。

**上游项目**：`pdfcpu`　**仓库**：https://github.com/pdfcpu/pdfcpu

## 什么时候用 / 不用

**用它**：

- 用户说「把这十几个 PDF 合成一个」「按章节拆开」「只要第 3 到 8 页」。
- 用户说「这个 PDF 太大了，压一压」「把图片抽出来」「去掉里面的签名」。
- 用户说「给每页加水印 / 页码 / 密级标记」，或要批量统一加密、改权限。
- 用户说「看看这个 PDF 有没有问题」——`validate` 是最快的体检手段，能报出结构错误。
- 需要在脚本、CI、定时任务里无人值守跑 PDF 批处理，不想要 GUI、不想装 JVM。

**不要用它**：

- 要 PDF 转 Word / Excel / Markdown / HTML——它不做格式转换，找 LibreOffice 或专门的转换器。
- 要抽取表格数据并保留行列结构——用 tabula 这类按线条和文字位置重建表格的工具。
- 要从扫描件里读出文字——它是 PDF 结构工具，不是 OCR，扫描件得先走 OCR。
- 要精细排版、生成复杂报表版式——它是拼接和修饰工具，不是排版引擎，复杂版面要生成器来写。
- 要处理加密文件却不知道密码——`validate`/`optimize` 都会因为解不开而失败，先拿到密码。

## 安装

`pdfcpu` 是 Go 单文件程序，官方推荐直接下预编译包。装完第一件事是跑 `pdfcpu version` 确认可执行。

```bash
# 方式一：预编译二进制（官方推荐，各平台都有）
#   到上游 releases 页下载对应包后解压，把 pdfcpu 放进 PATH：
#   Windows: pdfcpu_<版本>_Windows_x86_64.zip
#   macOS  : pdfcpu_<版本>_Darwin_arm64.tar.xz（Intel 用 x86_64）
#   Linux  : pdfcpu_<版本>_Linux_x86_64.tar.xz
#   官方下载页与各平台文件名以 https://pdfcpu.io/getting_started/install_cli 为准
sudo mv pdfcpu /usr/local/bin/     # Windows 则把目录加入 PATH
pdfcpu version

# 方式二：有 Go 工具链（需 Go 1.21 或更高，具体下限以官方文档为准）
go install github.com/pdfcpu/pdfcpu/cmd/pdfcpu@latest
pdfcpu version

# 需要内置 EU Trusted List 证书包时（用于签名信任链校验）
go install -tags pdfcpu_eutl github.com/pdfcpu/pdfcpu/cmd/pdfcpu@latest

# 方式三：包管理器
brew install pdfcpu                 # macOS / Linuxbrew
sudo port install pdfcpu            # MacPorts
sudo dnf install golang-github-pdfcpu   # Fedora

# 方式四：Docker（在仓库根目录构建，挂载当前目录到 /app）
docker build -t pdfcpu .
docker run -it -v "$(pwd)":/app pdfcpu validate a.pdf
```

命令与参数不确定时，用自带帮助，不要猜：`pdfcpu --help`、`pdfcpu <command> --help`、`pdfcpu selectedpages --help`。

## 常用操作

```bash
# 1. 体检：先看文件是否结构完好、共几页、加密状态（出错时加 -vv 拿详细日志）
pdfcpu validate -vv input.pdf
pdfcpu info input.pdf

# 2. 合并 / 拆分：merge 是「输出在前、输入在后」；split 支持按 span 或指定页号切
pdfcpu merge merged.pdf in1.pdf in2.pdf
pdfcpu split input.pdf ./outdir          # 每页一个文件
pdfcpu split input.pdf ./outdir 5        # 每 5 页一个文件

# 3. 按页范围处理：--pages 支持 even/odd/单页/区间/取反（! 在 shell 里要加单引号）
pdfcpu trim -pages -3,5,7- input.pdf out.pdf     # 前 3 页 + 第 5 页 + 第 7 页到末页
pdfcpu trim -pages '4-7,!6' input.pdf out.pdf    # 4~7 页但排除第 6 页
pdfcpu rotate -pages odd 90 input.pdf out.pdf    # 奇数页转 90 度

# 4. 压体积与加密（加密时 -opw 所有者密码必填且非空；密码建议走环境变量）
pdfcpu optimize input.pdf out.pdf
pdfcpu encrypt input.pdf out.pdf --upw "$UPW" --opw "$OPW" --mode aes --key 256
pdfcpu decrypt -upw "$UPW" encrypted.pdf clear.pdf

# 5. 加水印 / 盖戳（watermark 在内容之下，stamp 在内容之上；描述串在输入文件之前）
#    描述串为逗号分隔的 key:value，常用 pos / rot / scale / op / points / fo
pdfcpu watermark add 'DRAFT' 'pos:bc, rot:45, scale:1.5 abs' in.pdf out.pdf -m text
pdfcpu watermark add 'Draft' 'points:48, scale:1, color:.8 .8 .4, op:.6' in.pdf out.pdf --mode text
pdfcpu stamp add '这是一个测试' 'fo:SimSun' in.pdf out.pdf -m text   # 中文需先装用户字体
pdfcpu stamp add -m text -- 'Page %p of %P' 'scale:1.0 abs, pos:bc, rot:0' in.pdf out.pdf

# 6. 抽资源与看结构数据（-m 必填：image / font / content / page / meta）
pdfcpu extract -m image in.pdf ./imgs
pdfcpu extract -m page -p 1-3 in.pdf ./pages
pdfcpu images list in.pdf
pdfcpu fonts list
```

Go 代码里调用同一套能力，核心入口是 `pkg/api`：

```go
import "github.com/pdfcpu/pdfcpu/pkg/api"

// 合并多个 PDF 到 out.pdf；第三个参数为 true 时在文件之间插入空白页
err := api.MergeCreateFile([]string{"in1.pdf", "in2.pdf"}, "out.pdf", false, nil)
```

最小描述串、`--mode` 取值、`-pages` 可用范围这类细节，以 `pdfcpu <command> --help` 与
https://pdfcpu.io 上对应命令页为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `merge` 报参数错误或结果不对 | `merge` 的入参顺序是「先输出文件，再输入文件」，和常见「输入…输出」相反 | 用 `pdfcpu merge out.pdf in1.pdf in2.pdf`，不要按直觉写 |
| 命令报 `unknown flag` / 提示缺 mode | 多数内容类命令要求显式给 `-m`（watermark/stamp 用 text\|image\|pdf，extract 用 image\|font\|content\|page\|meta） | 先跑 `pdfcpu <command> --help` 看该命令自己的 flag，别套用别家 PDF 工具的参数 |
| `--pages '4-7,!6'` 报错或被 shell 吃掉 `!` | `!` 是取反语法，在 bash/zsh 里需要单引号包住；也可改用 `n` 前缀（如 `n6`） | 写成 `--pages '4-7,!6'` 或 `--pages 4-7,n6` |
| 水印加上去但页面上看不到 | watermark 在内容之下，扫描件整页是位图会把背景整块盖住 | 改用 `pdfcpu stamp` 并把 `op` 设成小于 1（如水印设置加 `op:.3`），它叠在内容之上 |
| 中文水印/戳记变成方框或报编码错误 | 默认字体 Helvetica 不含 CJK 字形，需先安装用户字体再用 `fo:` 指定 | 装好字体后用 `-m text '内容' 'fo:SimSun'`；`pdfcpu fonts list` 可查可用字体 |
| `encrypt` 报缺少所有者密码 | pdfcpu 明确要求 `--opw` 非空，空所有者密码会被拒绝 | 传 `--opw "$OPW"`；只设 opw 时文件仍可被任何人打开 |
| `trim` 之后书签、批注、表单没了 | `trim` 是「按页选择重建文档」，规范上不携带 annotations / outlines / struct trees / forms | 要保留这些元素就别用 `trim`，或改用其它保留结构的流程；`crop` 才是改可见页范围 |
| 加密文件上任何命令都失败 | 未提供 `--upw` 解不开；pdfcpu 不做暴力破解 | 找用户拿打开密码，或在 `validate` 里带上 `-upw` 验证 |
| 处理大文件报内存不足 | pdfcpu 会在内存里重建文档结构，超大文件或超多页时占用明显 | 拆批处理、`optimize` 先瘦身，或改用管道逐段处理 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（仅安装阶段需要） | 只在下载二进制/依赖时联网；`--offline` 可关闭运行期的出站请求（用于链接校验、图像框填充等场景） |
| 读取文件 | 是 | 读取待处理的 PDF 与图片、字体文件 |
| 写入文件 | 是 | 写出结果 PDF、拆分目录、抽取出的图片/字体/页面文件；省略 outFile 时会就地覆盖输入文件 |
| 凭证 | 否 | 不使用任何云端账号或 API Key；只用命令行传入的 PDF 打开/所有者密码 |
| 子进程 / 后台常驻 | 否 | 一次性执行的命令行程序，跑完即退出，不驻留 |

## 触发场景

- 「帮我把这 20 个 PDF 合成一份。」
- 「这个 PDF 太大了，压一下再发。」
- 「只保留第 3 到第 8 页，导出成一个新文件。」
- 「给每一页右下角加上页码 / 加上『内部资料』。」
- 「把这份文件加密，禁止别人复制内容。」
- 「把 PDF 里的图片都提取出来。」
- 「先帮我看看这个 PDF 是不是坏了。」

## 能力边界

**覆盖**：

- 文档装配：合并（可插入分隔页）、拆分（按页数或页号）、按页选择生成新文档、拼接成册。
- 页面几何：旋转、缩放、裁切（crop/cut/poster/zoom）、nup 拼版、booklet 小册子、页框（boxes）管理。
- 内容加注：文字/图片/PDF 页作为水印或戳记，支持位置、旋转、缩放、颜色、透明度，支持 `%p`/`%P` 页码占位符。
- 安全：AES/RC4 加密、解密、改所有者/用户密码、读写权限位、签名有效性与证据报告、移除签名。
- 资源与元数据：抽图片/字体/原始内容流/单页 PDF/XML 元数据；附件与 portfolio 增删抽；关键词、自定义属性、书签、页面模式、视图偏好。
- 表单：列出、导出、填充、批量填充、重置、锁定/解锁、删除字段。
- 结构体检：`validate` 校验，`info` 输出页数、版本、加密与权限摘要。
- 管道：输入/输出位置用 `-` 接 stdin/stdout，可串进 shell 流水线。
- Go 库：`pkg/api` 提供与 CLI 同源的 API。

**不覆盖**：

- 不做格式转换（PDF → Word/Excel/Markdown/HTML/图片序列的排版还原）。
- 不识别扫描件文字（无 OCR 能力），也不做版面语义理解与表格结构重建。
- 不做 PDF 生成排版引擎：复杂报表/图文混排的原始生成要靠专门的生成器。
- 不破解密码，不绕过加密。
- 不能编辑正文里已有的文字内容（不能改某一行字），只能加注、盖戳、裁剪、重排页面。

## 依赖条件

- 无需运行时依赖：`pdfcpu` 是静态可执行程序，装了就能跑。
- 用 `go install` 方式安装时，本机需要 Go 工具链（具体最低版本以官方安装页为准）。
- Docker 方式需要本机有 Docker，并在仓库根目录执行 `docker build`。
- 无需账号、无需 API Key、无需联网即可离线处理本地文件。
- 处理中文水印/戳记时，需要额外准备并安装一个含中文字形的 TrueType 字体。

## 已知限制

- PDF 2.0 的支持仍在完善中，校验能力对 PDF 2.0 属于基础级别。
- `trim` 生成的新文档不携带批注、书签大纲、结构树、表单。
- 水印位于页面内容之下，位图扫描页会遮挡水印；需要可见请改用 stamp。
- 加密时所有者密码强制非空，这与 PDF 规范允许空所有者密码不同。
- 表单填充需要外部 JSON 数据文件，字段名要与 PDF 内字段一致，字段名不匹配会失败。
- 部分功能（如链接校验相关处理）会发起出站请求，可用 `--offline` 关闭。

## 自检清单

- 执行前：
  - `pdfcpu version` 能输出，确认 PATH 已生效。
  - `pdfcpu <子命令> --help` 看过一遍，确认参数名和本 Skill 写的一致（版本间可能有差异）。
  - 确认输入 PDF 是否加密；加密的要知道打开密码，并准备 `--upw`。
  - 确认不会误覆盖原文件——省略 outFile 时 pdfcpu 就地改写输入文件，先备份。
- 执行后：
  - `pdfcpu validate out.pdf` 对结果做一次体检。
  - `pdfcpu info out.pdf` 核对页数、加密状态是否符合预期。
  - 抽查关键页（首页、末页、被排除的页）确认裁剪与合并顺序正确。
  - 若加了水印/戳记，至少渲染一页肉眼确认可见性。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/pdfcpu/pdfcpu | 上游仓库（安装与完整文档以它为准） |

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
