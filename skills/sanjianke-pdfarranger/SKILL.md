---
name: sanjianke-pdfarranger
slug: sanjianke-pdfarranger
displayName: 三剪客 · PDF 页面整理
description: "PDF Arranger 是用鼠标整理 PDF 页面的 GTK 桌面程序：合并、拆分、拖拽排序、旋转、裁剪、加页码式补白页，底层是 pikepdf。注意它是图形界面工具，不适合 Agent 无人值守调用。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "PDF Arranger 的跨平台安装方式、界面里能做哪些页面整理操作、书签与链接在什么操作后会丢失，以及为什么它是 GUI 工具、Agent 批量处理应改用 qpdf / pdfunite / pikepdf 等命令行方案。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档处理
  - PDF
  - 图形界面
---

# 三剪客 · PDF 页面整理

收到一堆扫描件、要拼成一份报告、把横向页面转正、把两页摊开的扫描拆成单页、把某个章节单独导出成一个文件——这些"页面级"的整理工作，PDF Arranger 做得又快又直观：所有页面平铺在窗口里，拖动就是排序，右键就是操作，改完了另存一份，源文件不动。

**但必须把这件事说在前面：PDF Arranger 是一个图形界面（GTK）桌面程序，不是命令行工具。** 官方 man page 的「OPTIONS」一节只有一句——*目前它不接受任何选项*——也就是说，除了启动时把文件路径当参数传进去，它没有任何命令行开关、没有批处理模式、没有无头模式。它需要有人坐在屏幕前用鼠标操作。**Agent 不能把它当作一个可无人值守调用的工具**，它的正确用法是「替人装好、帮人打开、教人怎么点」，或者干脆让 Agent 改用命令行方案（见下文）。

**上游项目**：`pdfarranger`　**仓库**：https://github.com/pdfarranger/pdfarranger

## 什么时候用 / 不用

**用它**：

- **有真人坐在屏幕前，要手工整理页面**——合并几份 PDF、按视觉顺序拖拽排页、删掉多余页、把扫描歪的页面转正，鼠标操作比写脚本快得多。
- "这几页的方向不对，帮我转过来"——支持 90 度步进旋转，所见即所得。
- "把这份扫描件两页摊开的版式拆成单页"——有 Split pages 功能；反向的 Merge pages 可以把多页合成一张。
- "扫描件白边太大，裁一下"——支持自动裁白边，也可以拖标记手工裁、隐藏页边距。
- "做个骑马钉小册子"——有 Generate and split booklet。
- "把这批图片拼成一份 PDF"——装了 `img2pdf` 后可以直接导入图片，自动转成 PDF 页。
- "只需要 30~50 页，单独导出一个文件"——可以只导出选中的页到一个或多个 PDF。

**不要用它**（这一块对 Agent 尤其关键）：

- **任何无人值守 / 批处理 / 服务器端场景**——它是 GTK 图形程序，**没有 CLI 参数、没有批处理模式**，无头环境（没有 X/Wayland 显示）下根本起不来。Agent 想自动化不要走这个工具。
- **要脚本化、可重复、可进 CI 的 PDF 页操作**——请直接用命令行工具：合页用 `pdfunite`（poppler）或 `qpdf --pages`，拆分/重排/旋转用 `qpdf`，批量压平与转换用 Ghostscript，Python 里用 `pikepdf`（PDF Arranger 本身就是它的前端）。这些才是 Agent 该调的东西。
- **要给文档加文字、加图章、加注释、填表单**——它不是编辑器，只能整理"页"这一层。
- **要 OCR**——它从扫描页里抽文字用的是文档已有的文本层，不识别图片里的字。
- **追求页面级精修的排版**——挪动页面内具体元素、调行距字距都不在能力范围内。
- **要保留原文档全部书签与链接且会改页面结构**——改页面尺寸（当页含链接时）、生成/拆分小册子、合并页面、隐藏边距、叠加粘贴之后，这些信息会丢失（见「常见坑」）。

## 安装

### Linux / BSD 各发行版（官方 README 给出的原生命令）

```bash
# Debian / Ubuntu 系
sudo apt-get install python3-pip python3-wheel python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-poppler-0.18 gir1.2-handy-1 python3-setuptools \
    gettext python3-dateutil python3-venv

# Arch Linux
sudo pacman -S poppler-glib python-pip python-gobject gtk3 python-cairo libhandy

# Fedora
sudo dnf install poppler-glib python3-pip python3-gobject gtk3 python3-cairo \
    python3-wheel python3-pikepdf python3-img2pdf python3-dateutil libhandy

# FreeBSD
sudo pkg install devel/gettext devel/py-gobject3 devel/py-pip \
    graphics/poppler-glib textproc/py-pikepdf x11-toolkits/gtk30 \
    x11-toolkits/libhandy
```

多数发行版的软件仓库里已经打包好了 PDF Arranger，直接装发行版包通常更省事；具体包名与是否有包，以各发行版仓库为准。

### Flatpak / Snap（跨发行版）

官方 README 的下载表给出 Flathub 与 Snap Store 两个渠道，具体安装命令以 flathub.org 与 snapcraft.io 上该应用的页面为准。

### 从源码装进虚拟环境

要求 **pikepdf >= 6**（系统里没有 pikepdf 时，pip 会自动装最新版）：

```bash
python3 -m venv --system-site-packages ~/myenv
~/myenv/bin/pip3 install --upgrade https://github.com/pdfarranger/pdfarranger/zipball/main

# 可选：建软链，之后终端里直接敲 pdfarranger 就能启动
sudo ln -s ~/myenv/bin/pdfarranger /usr/local/bin/pdfarranger
```

注意虚拟环境必须带 `--system-site-packages`，因为它要复用系统里的 GTK/PyGObject 绑定。

### Windows / macOS

- **Windows**：官方提供安装版与便携版，下载在项目 Releases 页面；从源码在 Windows 上构建的说明见仓库的 Win32.md。
- **macOS**：从源码构建的说明见仓库的 macOS.md；是否有官方预编译包以 Releases 页面为准。

### 可选依赖：图片导入

想要「把图片文件拖进来变成 PDF 页」这个功能，需要额外安装 `img2pdf`（官方说明 `img2pdf >= 0.4.2` 才支持透明图片）。没装就没有该功能。

### 验证安装

它是 GUI 程序，最直接的验证就是启动它：

```bash
pdfarranger --version      # 版本信息（若你的版本不支持此参数，改用发行版包管理器查询版本）
pdfarranger                # 直接启动图形界面
```

注意：官方 man page 明确说它不接受任何选项，因此 `--version` 之类是否可用取决于你的实际版本，以本机 `pdfarranger --help` 的实际输出为准。

## 常用操作

以下全部是**界面操作**。命令行部分只有一件事可说：启动时可以把一个或多个文件路径直接当参数传进去，它们会被打开成待整理的文档。

```bash
pdfarranger report.pdf              # 打开一个 PDF 进入界面
pdfarranger a.pdf b.pdf c.pdf       # 启动时就带上多个文件
```

界面里的高频操作（按官方用户文档整理）：

**1. 合并多份 PDF**
用窗口里的 `Open`（在新实例里打开）或 `Import`（把页追加到当前实例末尾），也可以直接从文件管理器拖拽文件进来、或复制粘贴文件路径。多个实例之间还能互相拖拽页面、复制粘贴页面。

**2. 重排 / 反转 / 交换奇偶页**
拖拽即排序，支持复制粘贴页面；有「颠倒顺序」和「交换奇数/偶数页」两个现成功能，处理双面扫描件很省事。

**3. 旋转、删除、复制、插入空白页**
旋转按 90 度步进；删除、复制页面都在右键菜单里；可以插入空白页用于分隔章节。

**4. 裁剪与调页尺寸**
自动裁白边、拖标记手工裁边距、隐藏页边距；页面可以按百分比或毫米调整尺寸。加边距有两条路：用 `Merge pages` 对话框把行列都设成 1 再填毫米边距，或用 `Page Size` 对话框选 `Fit to paper` 并把 `Fit mode` 设为 `Crop & Add margins`，然后加大宽或高。

**5. 拆页与合页**
`Split pages` 把一页拆开（摊开的双页扫描很常用），`Merge pages` 把多页合成一张；`Explode into images` 把某一页里的所有图片拆成新的独立页。

**6. 导出与保存**
`保存`（Save）把当前全部内容写成一个 PDF；`导出`（Export）可以只把选中的部分页导出成一个或多个 PDF，文件名末尾的数字每次导出会自增，所以重复导出不会互相覆盖；还能导出成 png / jpeg 图片，或导出为栅格化的 PDF。

**7. 选中页面的几种方式**
点一页再按住 Shift 点另一页选范围；在页与页之间按住拖拽也能选范围；`Ctrl+A` 全选、`Ctrl+Shift+A` 取消全选；还有按「同文件」「同格式」「范围」「反选」等选择方式。

**8. 与页面内容有关的零碎功能**
可以把一页粘贴成另一页的叠加层（overlay）或底层（underlay）；可以把文本或图片从页面抽取到剪贴板；可以编辑文档元数据；还能在 PDF 里搜索文字并打印。

**9. 视图操作**
`Ctrl` + 滚轮缩放，双击页面或按 `f` 切换缩放到适合窗口，`F11` 全屏；页宽超出窗口时 `Shift` + 滚轮横向滚动，按住 `Alt` 滚轮按页行步进；按住鼠标中键拖拽平移视图。

**10. 快捷键与界面语言**
快捷键可以自定义：在 `config.ini` 的 `[accelerators]` 段里把 `enable_custom` 设为 `true` 然后编辑。界面语言在 `Preferences` 对话框里选（该功能为 1.9.2 之后的版本提供）。配置文件位置：

- Linux：`~/.config/pdfarranger/config.ini`
- Windows 安装版：`C:\Users\用户名\AppData\Roaming\pdfarranger\config.ini`
- Windows 便携版：与 `pdfarranger.exe` 同目录（删掉该文件后，会回退用安装版的位置）

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| Agent 在服务器 / CI / 容器里调用它，直接报错起不来，或提示找不到显示 | 它是 GTK 图形程序，需要 X 或 Wayland 显示服务；官方 man page 的 OPTIONS 一节明确写着它**不接受任何选项**，没有无头 / 批处理模式 | 这条路走不通，不要在无人值守环境里用它。批量处理换命令行工具：`qpdf`、`pdfunite`、`pdfseparate`（poppler）、Ghostscript、Python 的 `pikepdf`。要用它就只能安排一台有桌面环境的机器，由人来操作 |
| 想写脚本自动合页/删页，翻遍文档找不到对应的命令 | 它的定位是「前端」而不是脚本工具，所有能力都在 GUI 事件里 | 放弃脚本化这个工具；直接对 `pikepdf` 编程，或用 `qpdf --pages` 这类参数化命令 |
| 整理完发现原文档的书签（outline）和链接丢了 | 官方用户文档列明了几种**必定丢失**这些信息的操作：改变页面尺寸（当页面含链接时）、生成与拆分小册子、合并页面、隐藏边距、粘贴为叠加层或底层 | 操作前把这些页面的链接记下来；只要书签与链接重要，就避开上述操作。另有一条相关设置：偏好里 `Preserve document information from the first file opened`（1.14.0 起）勾选后会用**第一个打开文件**的文档属性（含书签与链接，需 pikepdf >= 8.0），不勾选则合并所有文档的书签 |
| 勾了「从第一个文件保留文档信息」，书签还是不对 | 该设置的效果就是「以第一个文件为准」，而且依赖 pikepdf 版本 | 确认 pikepdf 满足版本要求；想合并所有文档书签就不要勾它。另注意：作为书签/链接**目标**的页面即使改了尺寸，仍可正常作为目标（官方文档特别说明） |
| 拖图片进去没反应，或透明 PNG 变成黑底 | 图片导入依赖 `img2pdf`；透明图片需要 `img2pdf >= 0.4.2` | 装上 `img2pdf` 并确认版本；版本不足就升级 |
| 导出结果和上一次导出混在一起，或者文件名上多了个数字 | 导出功能会在文件名末尾**自增数字**，这是设计行为，用来避免重复导出互相覆盖 | 想精确控制输出名就用「保存全部」另存，或每次导出前清理目标目录 |
| 从 pip 装完启动就崩，提示找不到 GTK / gi 模块 | 它复用系统级的 GTK / PyGObject 绑定，普通虚拟环境（不加 `--system-site-packages`）看不到系统包 | 建虚拟环境时加 `--system-site-packages`；或者直接装发行版自带的包，通常最省事 |
| Windows 上从 pip 装不起来 | Windows 需要 GTK 运行库，官方为 Windows 单独维护了构建说明 | 优先用官方 Releases 里的 Windows 安装版 / 便携版；一定要从源码构建就看仓库的 Win32.md |
| 自定义的快捷键不生效 | 快捷键自定义需要在配置文件的 `[accelerators]` 段里**同时**把 `enable_custom` 设为 `true` 并编辑键位，改完可能需要重启程序 | 按官方文档到对应平台的 `config.ini` 路径改，注意 Windows 便携版的配置在 exe 同目录 |
| 版本差异导致界面菜单和本文对不上 | PDF Arranger 迭代较快，不同版本功能与菜单项有增删（例如偏好里保留文档信息的选项是 1.14.0 起才有） | 以自己安装版本的界面和官方用户文档为准；不确定版本特性时先看 `About` / 发行包版本号 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 仅安装（apt / dnf / pacman / pip / flatpak）时需要联网；整理 PDF 全程本地 |
| 读取文件 | 是 | 读取需要打开的 PDF 与待导入的图片 |
| 写入文件 | 是 | 保存 / 导出 PDF，或以 png、jpeg、栅格化 PDF 形式导出 |
| 凭证 | 否 | 无账号、无 Key，无需登录任何服务 |
| 子进程 / 后台常驻 | 是 | 启动一个图形界面进程（需要显示服务）；不是后台常驻服务，进程随窗口关闭结束 |
| 图形界面 / 显示服务 | 是 | **必需**。这是本工具最关键的权限：它需要 X 或 Wayland 显示，无头环境无法运行 |

## 触发场景

- "帮我把这几份 PDF 合成一份。"（有桌面环境时用 GUI 最快，Agent 场景请改用 qpdf / pdfunite）
- "这份扫描件页序乱了，我要拖着重排。"
- "把横向的几页转正，再删掉空白页。"
- "把这份双面扫描的两页摊开版式拆成单页。"
- "只把第 30 到 50 页导出成一个新文件。"
- "把这十几张图拼成一份 PDF。"
- "这台机器上有没有能整理 PDF 页面的图形工具？"

## 能力边界

**覆盖**（全部通过图形界面操作）：

- 打开、导入、拖拽、复制粘贴多份 PDF；跨实例移动页面
- 页面排序：拖拽重排、复制粘贴、颠倒顺序、交换奇数/偶数页
- 页面级操作：旋转（90 度步进）、删除、复制、插入空白页、拆页、合页、爆炸成图片
- 版面调整：自动裁白边、手工裁边距、隐藏边距、按百分比或毫米改页尺寸、加边距
- 小册子：生成与拆分 booklet
- 导入图片转 PDF 页（需 `img2pdf`）
- 叠加与底层粘贴；从页面抽取文本或图片到剪贴板
- 导出：导出选中页为一个或多个 PDF、导出 png / jpeg、导出栅格化 PDF；保存全部为一个 PDF
- 其他：元数据编辑、页内文字搜索、打印、撤销重做、浅色/深色主题、自定义快捷键、多语言界面

**不覆盖**：

- **命令行选项、批处理、无头运行**——官方 man page 明确它不接受任何选项，这是硬边界
- 编辑页面内的内容：加文字、加图章、加批注、填表单、改字体字号
- OCR：不识别扫描图片里的文字
- 加密 / 解密 PDF、数字签名
- 压缩优化（要压体积走 Ghostscript 等工具）
- 从 PDF 转 Word / Markdown 等文档转换

## 依赖条件

- **图形界面环境**：需要 GTK 3 运行库与显示服务（X 或 Wayland）。无头服务器上无法使用
- **pikepdf >= 6**（从源码安装时；系统里没有的话 pip 会自动装最新版）。涉及保留书签与链接的偏好项需要 **pikepdf >= 8.0**
- Python 3 与 PyGObject（`python3-gi`）、GTK 3、poppler-glib、libhandy 等系统库
- 图片导入功能需额外安装 `img2pdf`（透明图片需 >= 0.4.2）
- 从源码装进虚拟环境时必须带 `--system-site-packages`
- 不需要账号、Key 或任何在线服务

## 已知限制

1. **没有命令行接口**：官方 man page 的 OPTIONS 一节明确写着它不接受任何选项，因此无法脚本化、无法进 CI、无法在无头环境运行。这是本工具对 Agent 场景最本质的限制。
2. 它只是 pikepdf 的前端：所有页面操作都能用 pikepdf 或 qpdf 以代码 / 命令方式完成，需要自动化时应直接走底层方案。
3. 若干操作会造成书签与内部链接丢失：改页尺寸（页含链接时）、生成与拆分小册子、合并页面、隐藏边距、粘贴为叠加/底层。
4. 仅做页面级整理，不编辑页内内容，也不做 OCR。
5. 版本迭代较快，界面菜单项与偏好项在不同版本间有差异，本包描述的功能以官方用户文档为准，实际以本机安装版本为准。
6. Windows 从源码构建路径与 Linux 差异较大，官方为 Windows 单列了构建文档，跨平台使用需分别对待。

## 自检清单

执行前（Agent 必须先判断这条）：

- [ ] **确认有可用的图形界面与操作它的人**。若无头 / 无人值守，立即放弃本工具，改用 `qpdf` / `pdfunite` / `pikepdf`
- [ ] 确认这是页面级整理需求（合并、排序、旋转、拆分、裁剪），而不是页内编辑或 OCR
- [ ] 需要导入图片时，确认已安装 `img2pdf` 且版本满足要求
- [ ] 文档有重要书签或内部链接时，先确认本次操作是否会触发丢失条件
- [ ] 操作前对源文件留一份备份，明确最终要「另存为新文件」还是覆盖

执行后：

- [ ] 在界面里逐页确认顺序、方向、尺寸是否符合预期（撤销重做可用，但别依赖）
- [ ] 打开导出的文件，确认书签与链接是否还在（若需要保留）
- [ ] 确认导出文件名与预期一致（注意导出会自动加自增数字）
- [ ] 抽查文件页数与页码连续性，确认没有多页漏页
- [ ] 确认源文件未被意外覆盖

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/pdfarranger/pdfarranger | 上游仓库（安装与完整文档以它为准） |
| https://github.com/pdfarranger/pdfarranger/wiki/User-Manual | 官方用户文档：界面功能、快捷键、配置文件位置 |

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
