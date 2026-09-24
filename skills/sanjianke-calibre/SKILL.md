---
name: sanjianke-calibre
slug: sanjianke-calibre
displayName: 三剪客 · 电子书管理与转换
description: "calibre：电子书管理与转换 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "calibre：电子书管理与转换 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · 电子书管理与转换

它既是一个电子书**书库**（带封面、元数据、标签、系列、搜索），也是一整套**命令行工具**（转换、改元数据、精修、导出、起内容服务器）。绝大多数人只用它的图形界面，但真正能在自动化里干活的是那些命令：`ebook-convert` 管格式转换，`calibredb` 管书库增删导出，`ebook-meta` 管元数据读写，`ebook-polish` 在不做整本转换的前提下修书。

判断要不要用它，只看两点：**格式转换**（尤其目标格式是 Kindle 那一系）和**书库管理**。它不做解密，也从设计上拒绝这事。

**上游项目**：`calibre`　**仓库**：https://github.com/kovidgoyal/calibre

## 什么时候用 / 不用

**用它**：

- 「把这本 EPUB 转成 Kindle 能看的格式」——`ebook-convert` 配 `--output-profile kindle`，这是最常见的诉求。
- 「一堆电子书要批量统一改标题/作者/系列」——`ebook-meta` 与 `calibredb set_metadata`。
- 「要建一个能搜索、能按标签分类的书库」——`calibredb add` / `list` / `search`。
- 「书的内容没问题，只想压一下图片体积、嵌个字体、换封面」——`ebook-polish`，不用整本转换。
- 「要在局域网里把书库共享给手机/阅读器」——`calibre-server`。
- 「要抓取在线书源信息补全元数据」——`fetch-ebook-metadata`。

**不要用它**：

- **要处理带 DRM 的电子书**——它明确不支持、也不会打开这类文件，任何「怎么去掉 DRM」的期待都要当场打消。
- **要拿 PDF 当输入源做高质量转换**——官方自己的说法是 PDF 作为输入格式很糟，多栏、图片型、矢量图、表格都处理不了，链接与目录也不支持。
- **要把它的代码集成进闭源产品**——本体是 GPLv3，官方明确说明不能在不让自己的软件开源的前提下使用它的代码或库。
- **要找一个官方 Docker 镜像**——官方没有发布，第三方镜像不属于官方支持范围。
- **要命令行批量转换整目录**——官方没有这样的命令；批量转换是图形界面的功能，脚本里要自己写循环。
- **要输出 KFX**——官方文档里没有这条转换路径。

## 安装

**Linux（官方推荐用官方安装脚本，不要用发行版仓库里的包）**。官方下载页的原话大意是：请勿使用发行版提供的 calibre 包，那些包往往有缺陷或已过时。

```bash
sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin
```

安装脚本还能接参数，常见几种（写法是在脚本后追加）：

```bash
# 装到指定目录
... | sudo sh /dev/stdin install_dir=/opt
# 装到用户目录、与系统隔离
... | sudo sh /dev/stdin install_dir=~/calibre-bin isolated=y
# 指定版本
... | sudo sh /dev/stdin version=4.23.0
```

卸载：`sudo calibre-uninstall`。前置要求：`xdg-utils`、`wget`、`xz-utils`、Python。

**手动解压 tarball**：

```bash
sudo mkdir -p /opt/calibre && sudo rm -rf /opt/calibre/*
sudo tar xvf /path/to/downloaded/calibre-tarball.txz -C /opt/calibre
sudo /opt/calibre/calibre_postinstall
```

**从源码装**（需要系统里有 Python 3）：

```bash
curl -L https://calibre-ebook.com/dist/src | tar xvJ
cd calibre* && sudo python3 setup.py install
```

**macOS**：官方提供 `.dmg`，要求 macOS 14.0（Sonoma）及以上。官方特别说明：**不能直接在 dmg 里运行，必须拖到本机文件夹**。

**Windows**：官方提供 `.msi` 安装包，要求 Windows 10（1809 版）及以上。

**便携版（仅 Windows）**：把便携版安装器指向一个目录即可，运行 `calibre-portable.exe` 启动：

```powershell
calibre-portable-installer.exe "C:\Calibre Portable"
```

注意：官方说明便携版**只记住放在便携目录内部的书库**。

**命令行工具在哪**（这一步最容易绊住人）：

- Linux 官方安装：`/opt/calibre/` 下，例如 `/opt/calibre/ebook-convert`、`/opt/calibre/calibredb`、`/opt/calibre/calibre-server`。
- macOS：工具在应用包内部，例如 `/Applications/calibre.app/Contents/MacOS/ebook-convert`。
- Windows：通常直接用命令名（如 `calibre-debug`），需要绝对路径时用安装目录下的可执行文件。

**官方没有发布 Docker 镜像**；第三方镜像不经官方支持，用之前自行评估。

**常用的环境变量**（需要把配置、缓存、临时目录挪到别处时）：

| 变量 | 用途 |
|---|---|
| `CALIBRE_CONFIG_DIRECTORY` | 配置文件目录 |
| `CALIBRE_TEMP_DIR` | 临时文件目录 |
| `CALIBRE_CACHE_DIRECTORY` | 缓存目录 |
| `CALIBRE_OVERRIDE_DATABASE_PATH` | 覆盖元数据数据库路径（放在不支持文件锁的盘上时用） |
| `CALIBRE_OVERRIDE_LANG` | 覆盖界面/工具语言 |
| `CALIBRE_NO_NATIVE_FILEDIALOGS` | 关闭原生文件对话框 |
| `CALIBRE_USE_SYSTEM_CERTIFICATES` | 使用系统证书 |

`QT_QPA_PLATFORM` 官方文档只给出 `wayland` 与 `xcb` 两个取值；Wayland 下出问题时可用 `QT_QPA_PLATFORM=xcb calibre`。

## 常用操作

**1）格式转换**（基本形式就是「输入 输出」，目标格式由输出扩展名决定）：

```bash
ebook-convert book.epub book.azw3
ebook-convert report.docx report.epub
```

**2）转给 Kindle**：输出 `.mobi` 时配 `--output-profile kindle`（官方 FAQ 给出的做法）：

```bash
ebook-convert book.epub book.mobi --output-profile kindle
```

`--output-profile` 还有 `generic_eink`、`kobo`、`ipad`、`tablet` 等取值；`--input-profile` 用于描述输入源。

**3）边转换边写元数据**：

```bash
ebook-convert draft.html draft.epub \
  --title "示例书名" --authors "示例作者" --language zh \
  --tags "小说" --series "示例系列" --series-index 1 \
  --cover cover.jpg --publisher "示例出版社"
```

只想试参数、不看输出文件时，用 `-h` 查该格式的专属参数：

```bash
ebook-convert myfile.input_format myfile.output_format -h
```

**4）输出名从输入名推导**（`.扩展名` 的形式）：

```bash
ebook-convert draft.html .epub
```

**5）读写元数据**：

```bash
ebook-meta book.epub                                   # 查看
ebook-meta book.epub --title "新书名" --authors "作者"   # 写入
ebook-meta book.epub --get-cover cover.jpg             # 导出封面
```

**6）精修现有文件**（只支持 AZW3 / EPUB / KEPUB）：

```bash
ebook-polish --compress-images --embed-fonts --cover new-cover.jpg book.epub
```

不写输出文件时是原地修改，改动前先备份。

**7）书库操作**：

```bash
calibredb add --with-library /path/to/library book.epub
calibredb add --library-path /path/to/library --recurse /path/to/books   # 递归加一整个目录
calibredb list --fields title,authors --sort-by title --limit 20
calibredb remove 23,34,57-85
calibredb export --library-path /path/to/library --to-dir /tmp/out --formats epub
```

`--with-library` 与 `--library-path` 是同一个东西，既可以给本地路径，也可以给内容服务器地址（形如 `http://localhost:8080/#mylibrary`）；连远程库时用 `--username` / `--password` / `--timeout`。

**8）起内容服务器**：

```bash
calibre-server --port 8080 /path/to/the/library/you/want/to/share
```

**9）补元数据**（至少要给标题、作者或 ISBN 之一）：

```bash
fetch-ebook-metadata --title "示例书名" --authors "示例作者" --opf meta.opf
```

`--allowed-plugin` 可限定数据源，官方文档列出的名字有 Google、Google Images、Amazon.com、Edelweiss、Open Library。

**10）排查与调试**：`calibre-debug` 不带参数会进一个内嵌的 Python 解释器；`calibre-debug -g` 用于启动图形界面；`--paths` 打印各目录位置。

**11）批量**：官方**没有**命令行批量转换命令（批量转换在图形界面里）。脚本侧自己写成循环即可：

```bash
for f in *.epub; do ebook-convert "$f" "${f%.epub}.azw3"; done
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 书打不开，提示受 DRM 保护 | 官方明确拒绝打开 DRM 文件（理由是这样才不会被改造成去 DRM 的工具，而去 DRM 在多数地区违法） | 如实告诉用户这条路走不通；从正规渠道获取无 DRM 版本，`.acsm` 文件要先用 Adobe Digital Editions 处理 |
| 用发行版仓库装的 calibre 行为古怪 | 官方明确说明发行版的包往往有缺陷或过时 | 卸掉发行版包，改用官方安装脚本或官方安装包 |
| 服务器上跑命令报 Qt / ImportError | 命令行工具本身不需要 X 服务器，但部分工具依赖 Qt，从而需要 X 相关库存在 | 补装典型缺失库：`libxcb-cursor0`、`libxcb-xinerama0`、`libegl1`、`libopengl0`；同时确认 GLIBC 与 libstdc++ 满足要求（官方两处页面对最低版本的说法不完全一致，以安装页要求为准） |
| macOS 上命令找不到 | 工具不在 PATH 里，而在应用包内部 | 用完整路径，例如 `/Applications/calibre.app/Contents/MacOS/ebook-convert` |
| PDF 转出来的东西面目全非 | PDF 作为输入格式本身就很差：多栏/图片型文档、矢量图与表格抽取、链接与目录都不支持，非 Unicode 字体还会导致非英文字符乱码 | 能拿到 EPUB/MOBI/DOCX 就别用 PDF；官方给出的输入源优先级里 PDF 排最后。转换 PDF 输入时可留意「Line un-wrapping factor」这类参数 |
| 输出文件变成一堆文件夹 | 输出名没有扩展名时，会被当成 OEB 目录处理 | 输出一定要带目标扩展名（`.epub`、`.azw3`、`.mobi`…） |
| 命令报参数错误，说文件不存在 | 文件名以连字符开头会被当成选项 | 改名，或用 `./` 前缀分隔 |
| 转了 AZW3，Kindle 上翻页/目录异常 | 输出 AZW3 时，Kindle 固件在关闭「文件末尾内联目录」生成的情况下容易出问题 | 别手动关掉末尾内联目录的生成；MOBI 本身没有像样的元数据目录，只能靠末尾内联目录模拟 |
| 想给 Kindle 邮箱推送 AZW3 被拒 | 官方说明 Amazon 不接受 AZW3 与新式（KF8）MOBI 的邮件投递，且逐步转向 EPUB | 改用支持的格式与投递方式；封面显示问题可参考官方提到的「标记为个人文档」思路与固件版本要求 |
| 想用 Docker 一键部署 | 官方没有发布 Docker 镜像 | 用第三方镜像要自行评估；更稳的做法是按官方脚本装到宿主机或自建镜像 |
| 想把它嵌进商业产品 | 本体是 GPLv3，官方明确说明使用其代码或库会要求你的软件也开源 | 商用前先做许可证评估，通常改为「调用外部可执行文件」并遵守其条款，或换用许可更宽松的方案 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | `fetch-ebook-metadata` 抓取在线元数据源；安装与更新时下载官方包；内容服务器对外提供服务时也涉及网络 |
| 读取文件 | 是 | 读取电子书文件、书库目录、封面图片 |
| 写入文件 | 是 | 写出转换结果、修改元数据、写入书库与缓存/临时目录 |
| 凭证 | 否 | 工具本身不需要账号或 Key；连接远程内容服务器时的用户名/密码由用户提供 |
| 子进程 / 后台常驻 | 是 | 一个安装会带出十几个可执行工具；`calibre-server` 可作为常驻服务运行（Linux 支持 `--daemonize`） |

## 触发场景

- 「这本 EPUB 怎么放到 Kindle 上看？」
- 「把这几本书的作者名统一改一下。」
- 「建一个能按标签和系列搜索的书库。」
- 「不想整本重转，只想压缩一下书里的图片。」
- 「把书库共享到局域网，手机上看。」
- 「书名作者给我，帮我补全元数据。」

## 能力边界

**覆盖**：

- 输入格式：AZW、AZW3、AZW4、CBZ、CBR、CB7、CBC、CHM、DJVU、DOCX、EPUB、FB2、FBZ、HTML、HTMLZ、KEPUB、LIT、LRF、MOBI、ODT、PDF、PRC、PDB、PML、RB、RTF、SNB、TCR、TXT、TXTZ。
- 输出格式：AZW3、EPUB、DOCX、FB2、HTMLZ、KEPUB、OEB、LIT、LRF、MOBI、PDB、PMLZ、RB、PDF、RTF、SNB、TCR、TXT、TXTZ、ZIP。
- 只进不出的格式（不能作为输出目标）：AZW、AZW4、CBZ、CBR、CB7、CBC、CHM、DJVU、FBZ、HTML、ODT、PRC、PML。这几个是常见的选型误区，必须提前说清。
- 元数据读写：标题、作者、系列与序号、标签、评分、语言、ISBN、出版社、日期、封面等，读写都通过 `ebook-meta`。
- 书库管理：增删、按字段列表、搜索、排序、导出、自定义列、备份元数据、库健康检查。
- 精修：压缩图片、嵌入/子集化字体、换封面、去掉未用 CSS、智能标点、加软连字符（限 AZW3/EPUB/KEPUB）。
- 内容服务器：局域网/公网共享书库，支持鉴权、SSL 证书、URL 前缀、守护进程模式。
- 其它工具：`calibre-debug`（调试、内嵌 Python、插拔书、检查 MOBI）、`lrf2lrs`、`lrs2lrf`、`calibre-smtp`、`web2disk`、`calibre-customize`。另有少数未在文档中列出用法的工具，直接无参数运行可看用法。

**不覆盖**：

- 不支持打开或处理 DRM 文件；官方不提供也不协助任何去 DRM 手段。
- 不做 PDF 的版面还原：多栏、图片型文档、矢量图与表格抽取、链接与目录都不支持。
- 不输出 KFX，也没有对应的转换路径。
- 没有官方 Docker 镜像。
- 没有命令行批量转换入口（批量转换是图形界面功能）。
- 内容服务器是书库共享，不是阅读进度同步、账号体系或 DRM 分发平台。

## 依赖条件

- Linux 官方安装脚本要求：`xdg-utils`、`wget`、`xz-utils`、Python；运行时要求 GLIBC 与 libstdc++ 达到官方页面给出的最低版本（两个官方页面对最低版本的说法不完全一致，以安装页为准）。
- 部分命令行工具需要 Qt 及其依赖的 X 相关库（如 `libxcb-cursor0`、`libxcb-xinerama0`、`libegl1`、`libopengl0`），服务器上按需补装。
- macOS 要求 14.0（Sonoma）及以上；Windows 要求 Windows 10（1809）及以上；便携版仅 Windows。
- 从源码安装需要 Python 3。
- 补元数据依赖在线数据源，网络不通就只剩本地信息。

## 已知限制

- 各格式的输入/输出能力不对等（见「能力边界」的三种清单），选型前先确认目标格式在输出清单里。
- PDF 作为输入源的效果被官方自己定性为「很糟」，只能作为最后手段。
- 转换质量取决于源文件本身，必要时才用 `--enable-heuristics`、`--extra-css` 这类参数去修补版面；这些参数解决的是源文件的排版问题，不是识别问题。
- 元数据抓取依赖第三方数据源，官方只列出可用插件名，结果准确性不由 calibre 保证。
- 许可证为 GPLv3；官方明确说明不能在不让自身软件开源的前提下使用它的代码或库。
- 官方文档没有覆盖全部工具的参数（如 `ebook-edit`、`ebook-viewer`、`web2disk` 的细节），需要时以工具自身用法输出为准。

## 自检清单

执行前：

- [ ] 确认源文件**没有 DRM**；带 `.acsm` 的先解决渠道问题。
- [ ] 确认目标格式在官方输出格式清单里（比如 CHM、CBZ、ODT 都只能进不能出）。
- [ ] 确认输入不是 PDF；是的话先找 EPUB/MOBI/HTML/DOCX 版本的源。
- [ ] 确认命令行工具的完整路径（macOS 尤其），以及服务器上 Qt/X 库是否齐全。
- [ ] 确认书库路径与编号，改动前做一次备份（`calibredb backup_metadata` / 复制书库目录）。

执行中：

- [ ] 先用一本书试跑，检查目录、封面、字体、翻页效果，再批量。
- [ ] 需要专属格式参数时先 `-h`，不要凭记忆拼参数。
- [ ] 原地修改（`ebook-polish` 不指定输出文件、`calibredb set_metadata`）之前确认已备份。

执行后：

- [ ] 在目标设备/阅读器上实际打开一次，确认能翻页、目录可用、封面正常。
- [ ] 元数据抽查几条，确认标题/作者/系列没有被写乱。
- [ ] 记录本次使用的命令与参数，便于复现与交接。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/kovidgoyal/calibre | 上游仓库（安装与完整文档以它为准） |
| https://manual.calibre-ebook.com/cli/index.html | 全部命令行工具索引 |
| https://manual.calibre-ebook.com/generated/en/ebook-convert.html | `ebook-convert` 参数完全清单 |

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
