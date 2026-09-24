---
name: sanjianke-ocrmypdf
slug: sanjianke-ocrmypdf
displayName: 三剪客 · 扫描件叠加 OCR 层
description: "OCRmyPDF：扫描件叠加 OCR 层 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "OCRmyPDF：扫描件叠加 OCR 层 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · 扫描件叠加 OCR 层

扫描出来的 PDF 看着清楚，但复制不了、搜不到、选中不了。OCRmyPDF 干的事很专注：**在原始 PDF 的每一页下面垫一层不可见的文字层**，页面外观基本不变，文件从此可以搜索、可以复制、可以被下游程序读。它把文本侧车文件、PDF/A 归档、自动纠偏、去噪、旋转这些事串成一条流水线，一条命令跑完。

它的关键设计是「**不改画面，只加层**」——所以它不重新生成 PDF，也不替你排版。需要「把扫描件重排成一份新文档」的任务，不属于它。

**上游项目**：`OCRmyPDF`　**仓库**：https://github.com/ocrmypdf/OCRmyPDF

## 什么时候用 / 不用

**用它**：

- 「这批扫描的合同/发票要能搜索」——给已有扫描 PDF 补文字层，这是它的主场。
- 「把扫描件做成 PDF/A 归档」——`--output-type pdfa` 走归档路线，适合长期保存。
- 「顺便把图上文字导出来」——`--sidecar` 直接产出纯文本文件，不用再跑一遍 OCR。
- 「扫描件歪了、脏了、方向不对」——`--deskew` `--clean` `--rotate-pages` 一次处理掉。
- 「只要文字不要 PDF」——`--output-type none` 配 `--sidecar`，只出文本。
- 「PDF 里只有一部分页是扫描件」——它**默认就会跳过已经有文字层的页**，混合文档可以直接喂进去。

**不要用它**：

- **要识别图片/照片/截图里的文字（不是 PDF）**——单张图能转成一页 PDF，但如果你要的是「结构化的识别结果、坐标、置信度」，这是通用 OCR 库的活，不是它的定位。
- **要抽取表格结构、版面、段落层级**——它只加纯文字层，不做版面重建；底层识别引擎也不提供段落/标题结构。
- **要处理手写体**——底层引擎的识别能力里没有手写。
- **要 OCR 加密或带数字签名的 PDF**——证书加密的文件打不开；带数字签名的文件会被拒绝修改（除非明确接受签名失效）。
- **要在没有识别引擎的运行环境里「装一个库就完事」**——它自己不实现 OCR，必须由系统包管理器提供识别引擎；pip 装不出这些外部程序。
- **要批量并发跑几百个大文件**——并发数是内存的直接倍数，`--jobs` 开大很容易把机器打爆。

## 安装

它由两部分组成：一个 Python 包 + 若干**必须由系统包管理器提供**的外部程序（识别引擎、PDF 处理工具）。官方安装文档明确说这些外部依赖 pip 给不了。

**各平台一条命令**（官方安装文档给出的形式）：

```bash
# Debian / Ubuntu（含 WSL 里的 Ubuntu）
apt install ocrmypdf

# Fedora
dnf install ocrmypdf tesseract-osd

# macOS / Linux 上的 Homebrew
brew install ocrmypdf

# 其它：MacPorts: port install ocrmypdf ｜ nix: nix-env -i ocrmypdf
#       Snap: snap install ocrmypdf ｜ Alpine: apk add ocrmypdf
#       OpenBSD: pkg_add ocrmypdf ｜ Gentoo: emerge --ask app-text/OCRmyPDF
```

**Docker（最省事，推荐给服务器）**。官方镜像把外部依赖都配好了：

```bash
docker pull jbarlow83/ocrmypdf-alpine      # 官方推荐；另有 ocrmypdf-ubuntu 与同名别名镜像

# 官方给出的调用形式：参数照常写在镜像后面，输入输出都用 - 走标准流
docker run --rm -i jbarlow83/ocrmypdf-alpine --deskew -l eng - -
```

容器里固定用非 root 用户 `app`（uid/gid 1000），默认工作目录是 `/data`。要按宿主目录读写文件，就挂载目录并视情况调整用户；具体写法以官方 Docker 页为准。

**pip / pipx / uv**（前提是外部依赖已经由系统装好）：

```bash
pip install --user ocrmypdf
pip install --user --upgrade ocrmypdf
pipx install ocrmypdf          # 或 pipx run ocrmypdf
```

**Windows 没有一键安装**。官方安装文档的结论是目前不存在一条命令装完 Windows。要点是分开装 Python 与识别引擎，Ghostscript 需要手工从官网下载安装（静默安装已停用）：

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id UB-Mannheim.TesseractOCR
py -m pip install ocrmypdf
py -m ocrmypdf --version
```

不支持的组合要提前说清：**32 位 Windows 不支持**；Cygwin 下没有 unpaper，`--clean` 会报错（不加它仍可正常出文字层）。

## 常用操作

**1）最常用的一条：加文字层，输出到新文件**

```bash
ocrmypdf input.pdf output.pdf
```

**2）原地替换**（输入输出同名即可；跑之前先备份）

```bash
ocrmypdf myfile.pdf myfile.pdf
```

**3）指定语言**。中文简体语言包要另装（见「常见坑」）；`-l` 可以叠加：

```bash
ocrmypdf -l chi_sim+eng input.pdf output.pdf
ocrmypdf -l eng -l fra input.pdf output.pdf     # 两种写法都行
```

**4）扫描件质量差：纠偏 + 去噪 + 自动旋转**

```bash
ocrmypdf --deskew --clean --rotate-pages input.pdf output.pdf
```

`--clean` 依赖 unpaper；`--remove-background` 也可用（对单色图无效）。

**5）归档 + 顺手导出文本**

```bash
ocrmypdf --output-type pdfa --sidecar output.txt input.pdf output.pdf
```

`--sidecar` 会把每页识别出的文字拼成一个纯文本文件。

**6）只要文本，不要 PDF**

```bash
ocrmypdf --output-type none --sidecar output.txt input.pdf output.pdf
```

**7）只要指定的几页 / 控制资源占用**

```bash
ocrmypdf --pages 2,3,13-17 input.pdf part.pdf
ocrmypdf --pages 3-end input.pdf tail.pdf
ocrmypdf --jobs 2 --max-ocr-image-mpixels 8 input.pdf output.pdf   # 内存吃紧时收窄
```

**8）图片转成带文字层的 PDF**（只支持单张图；多张先用 img2pdf 拼）

```bash
ocrmypdf --image-dpi 300 image.png myfile.pdf
img2pdf my-images*.jpg | ocrmypdf - myfile.pdf
```

**9）批量处理**。它没有一次传多个输入文件的参数，官方给的思路是交给 parallel：

```bash
parallel --tag -j 2 ocrmypdf '{}' 'output/{}' ::: *.pdf
find . -name '*.pdf' | parallel --tag -j 2 ocrmypdf '{}' '{}'
```

**10）Docker 里跑，文件不进容器**

```bash
docker run --rm -i jbarlow83/ocrmypdf-alpine - - <input.pdf >output.pdf
```

**11）Python 里调用**（v17 起的写法）：

```python
from ocrmypdf import OcrOptions
import ocrmypdf

options = OcrOptions(
    input_file="input.pdf",
    output_file="output.pdf",
    deskew=True,
    languages=["eng"],
)
ocrmypdf.ocr(options)
```

旧式写法是把命令行参数当关键字传：`ocrmypdf.ocr('input.pdf', 'output.pdf', deskew=True)`。**Windows 与 macOS 上，调用脚本必须放在 `if __name__ == '__main__':` 保护里**，否则会因多进程启动方式报错。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 报错 `page already has text! – aborting`，退出码 6 | 输入页已经存在文字层（或带标记结构），默认认为无需 OCR 而中止 | 明确选一个模式：`--force-ocr`（重做并丢弃原文字层）、`--skip-text`（跳过有文字的页）、`--redo-ocr`（只重做已有文字层、保留非文字内容）；v17 也可用 `--mode force\|skip\|redo` |
| 输出的「PDF/A 身份」和预期不一致 | 官方文档自身存在版本差异：README 与介绍页说默认产出 PDF/A，而高级页写明自 17.0.0 起 `--output-type` 默认是 `auto`（尽力而为的 PDF/A，不强制依赖 Ghostscript）；缺 Ghostscript/verapdf 时会退化成普通 PDF | 归档交付一定**显式**写 `--output-type pdfa`（或 pdfa-2/pdfa-3），不要依赖默认值 |
| 中文识别不出来，英文数字却还行 | 识别引擎默认只装英文语言包，且底层引擎不会自动判断语言 | 先装语言包再指定 `-l`：Debian/Ubuntu `apt-get install tesseract-ocr-chi-sim`；Fedora `dnf install tesseract-langpack-chi_sim`；Arch `pacman -S tesseract-data-...`；Homebrew `brew install tesseract-lang`；Windows 把 `.traineddata` 放进 Tesseract 的 `tessdata` 目录 |
| 手工拼的 tessdata 什么都识别不出 | 自建语言数据里缺 `configs/hocr`、`configs/txt` 这类配置目录 | 用系统包管理器装语言包，别只拷 `.traineddata` 单文件 |
| 处理大图时内存飙升甚至被 OOM 杀掉 | 峰值内存与「最大页面的像素数 × 并发数」直接相关，官方给的经验值是每像素约 15 字节：A4/Letter 600dpi 大约在 `--jobs 1` 时 500MB、`--jobs 4` 时 2GB | 降 `--jobs`、加 `--max-ocr-image-mpixels` 限制单页像素；注意 `--max-image-mpixels` 是解码炸弹防护，**不是**内存控制开关 |
| 处理完文件反而比原来大 | 加文字层会增体积；PDF/A 还会内嵌字体等资源，通常更大 | 想压体积就调优化级别与图像编码：`--optimize 2 --jpeg-quality 60`、`--pdfa-image-compression jpeg`；追求速度则 `--optimize 0` |
| 带数字签名的 PDF 处理失败 | 工具默认拒绝修改已签名的文件 | 确认可以承受签名失效后再加 `--invalidate-digital-signatures`；证书加密的 PDF 无法打开，只能让用户先解密 |
| 显式要求 PDF/A 直接报错退出 | 文件里有未内嵌的 CID（CJK）字体，PDF/A 转换无法完成 | 用默认的 `auto` 或显式 `--output-type pdf` 出普通 PDF；要归档就先解决字体内嵌问题 |
| 输出的 PDF 在阅读器里弹 PDF/A 提示 | PDF/A 合规文件本来就不允许加密，阅读器会据此提示 | 属于预期行为；给普通用户分发时考虑出普通 PDF |
| 转换后目录结构/链接丢了 | 走 Ghostscript 做 PDF/A 时，10.x 版本会丢弃结构树；超链接可能被移除或失效 | 需要保留结构与链接就用 `--output-type pdf`；或评估换渲染路径（`--rasterizer` 可选 `auto\|pypdfium\|ghostscript`） |
| 扫描件上原本可见的文字，处理后被压在文字层下面 | `--force-ocr` 会栅格化整页再叠层，原本的可见文字变成图像 | 混合文档优先 `--skip-text`；只有确定「原文字层不可信」时才用 `--force-ocr` |
| 处理超时中断 | 默认每页识别超时 180 秒 | 单页信息量大时提高 `--tesseract-timeout`；先确认是慢还是卡死 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 安装时从各包管理器/Docker 仓库拉取；运行时本身不需要联网 |
| 读取文件 | 是 | 读取待处理的 PDF/图片，路径由用户指定 |
| 写入文件 | 是 | 写出处理后的 PDF、`--sidecar` 文本文件，以及系统临时目录里的中间文件 |
| 凭证 | 否 | 无需账号或 API Key；加密 PDF 的密码由用户自行处理，本工具不解密 |
| 子进程 / 后台常驻 | 是 | 会调用 Tesseract、Ghostscript（或 pypdfium2）、unpaper 等外部程序；Docker 镜像里另有可选的常驻 watcher 与 Web 服务包装 |

## 触发场景

- 「这份扫描的 PDF 搜不到字，帮我加个文字层。」
- 「把一叠扫描件批量做成可搜索的 PDF。」
- 「合同扫描件要归档成 PDF/A。」
- 「把扫描 PDF 里的文字导出来给我一份 txt。」
- 「扫描件是歪的、还有底色噪声，先修一下再 OCR。」
- 「这批 PDF 里只有几页是扫描的，其余是电子版，混在一起处理。」

## 能力边界

**覆盖**：

- 给扫描 PDF 叠加不可见文字层，输入输出都是 PDF，页面外观基本保持。
- 图像预处理：纠偏（`--deskew`）、自动旋转（`--rotate-pages`）、去背景（`--remove-background`）、去噪清理（`--clean` / `--clean-final`，依赖 unpaper）。
- 归档输出：PDF/A（`pdfa` / `pdfa-1` / `pdfa-2` / `pdfa-3`）。
- 文本侧车文件（`--sidecar`）、只出文本（`--output-type none`）。
- 页范围、按大小跳过、超时、按需优化级别、并发数等资源控制（`--pages`、`--skip-big`、`--tesseract-timeout`、`--optimize`、`--jobs`）。
- 单张图片转成带文字层的 PDF（多图需先用 img2pdf 拼成一册）。
- 提供 Python API，可嵌进自己的流水线。

**不覆盖**：

- 不实现 OCR 引擎本身：识别交给 Tesseract，栅格化交给 pypdfium2 或 Ghostscript，PDF/A 校验交给 verapdf，清理交给 unpaper。
- 不做版面重建：没有段落、标题、表格结构、字体家族信息，只产出文字行。
- 不支持手写体；识别精度低于商业 OCR，扫描质量差时会输出乱码。
- 不处理证书加密的 PDF；带数字签名的文件默认拒绝修改。
- 不做 PDF 与 Office 格式之间的转换，也不做通用图片批处理。
- 不保证对抗恶意构造的 PDF——官方明确说明它不是为防御此类文件设计的，不要把它当作不可信文件的安全边界。

## 依赖条件

- **必装外部程序**：识别引擎 Tesseract 4.1.1+（外加你需要的语言包）；栅格化用 Ghostscript 9.54+ 或 pypdfium2；PDF/A 校验用 Ghostscript 9.54+ 或 verapdf。
- **Python 侧依赖**：Python 3.11+（官方推荐 3.12+）、fpdf2 2.8+、uharfbuzz；建议装 fonts-noto 或同类字体。
- **可选增强**：jbig2enc 0.29+、pngquant 2.5+、unpaper 6.1+（`--clean` 需要）。
- 官方文档在 17.x 版本明确 Ghostscript 已变为可选依赖；但要走 PDF/A 能力仍需要它或 verapdf。
- 磁盘：处理过程中会在临时目录写中间文件，可用 `TMPDIR`（Windows 是 `TEMP`）改到空间充足的位置。
- 不需要账号、Key 或联网服务。

## 已知限制

- **默认输出类型存在版本差异**：17.0.0 起默认是 `auto`，早期文档口径是默认 PDF/A。依赖「默认就是 PDF/A」的脚本在不同版本上行为可能不同，归档场景务必显式指定。
- 体积只会增不会减（相对原文件），加层与内嵌资源都要占空间；优化只能缓解。
- 内存由「最大页面像素 × 并发数」决定，二者都是你选出来的，判断失误就会 OOM。
- 语言必须在调用时给出，底层引擎没有语言自动判定能力；语言给错就是整篇错。
- 识别质量主要取决于扫描质量与语言包，工具层能做的只有预处理与参数微调。
- 许可证是 Mozilla Public License 2.0；它调用的 Ghostscript 为 AGPLv3，Docker 镜像里的 Web 服务包装同样是 AGPLv3——把这套东西集成进闭源产品前，务必先确认这几个许可证的实际影响。

## 自检清单

执行前：

- [ ] 确认输入是**扫描件**；对已经有文字层的文件先决定用 `--skip-text` 还是 `--redo-ocr`，不要默认硬上 `--force-ocr`。
- [ ] 确认 Tesseract 与语言包都已安装，`-l` 里的每个语言都有对应的 `traineddata`。
- [ ] 确认临时目录空间足够（中间文件可能远大于原文件）。
- [ ] 看一遍目标机器内存，据此定 `--jobs` 与 `--max-ocr-image-mpixels`。
- [ ] 归档需求要写死 `--output-type pdfa`，不依赖默认值。

执行中：

- [ ] 先用 1~2 页样本跑通（`--pages`），确认语言、方向、纠偏效果，再放全量。
- [ ] 关注退出码：6 表示「已经处理过/已有文字层」，不是崩溃。
- [ ] 批量任务用 parallel 控制并发，不要放开到无限并行。

执行后：

- [ ] 打开输出 PDF，确认**页面外观**没有变化，且可以搜索、复制文字。
- [ ] 抽查 3 页文字的准确性，特别是数字、金额、编号这类关键字段。
- [ ] 如果是归档交付，用 PDF/A 校验工具复核（或确认 `--output-type pdfa` 未报错）。
- [ ] 体积、页数、文本侧车文件内容与预期一致；保留原始文件直到验收通过。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/ocrmypdf/OCRmyPDF | 上游仓库（安装与完整文档以它为准） |
| https://ocrmypdf.readthedocs.io/en/latest/installation.html | 各平台安装与外部依赖清单 |
| https://ocrmypdf.readthedocs.io/en/latest/advanced.html | 输出类型与 PDF/A 行为的版本变更说明 |

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
