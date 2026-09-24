---
name: sanjianke-yazi
slug: sanjianke-yazi
displayName: 三剪客 · 终端文件管理器
description: "yazi：终端文件管理器 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "yazi：终端文件管理器 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文件管理
  - 转换
---

# 三剪客 · 终端文件管理器

在服务器、跳板机、或者懒得开图形界面的时候，用键盘把文件翻完、挑出来、搬走——这就是它解决的问题。
它是跑在终端里的文件管理器：三栏布局、异步 I/O、能直接在终端里出图，选中文件后复制 / 移动 / 删除 / 重命名 / 解压都是单键操作。
比 `ls` + `cd` + `mv` 快得多的地方在于：它有可视化预览、多选、批量重命名、后台任务队列，还能记住你上次选中的东西。
Claude / Agent 用它的时候，通常是**人**在交互式终端里操作，Agent 负责装依赖、改配置、写 keymap、排错。

**上游项目**：`yazi`　**仓库**：https://github.com/sxyazi/yazi

## 什么时候用 / 不用

**用它**：

- 用户在纯终端环境（SSH 连服务器、WSL、tmux 里）要浏览和整理目录，且希望有预览不要靠 `ls` 一条条敲。
- 需要「看一眼再动手」的批量操作：批量重命名、跨目录挑选文件、把一堆文件移动/复制到多个位置。
- 机器上已经装了 `fd` / `rg` / `fzf` / `zoxide`，希望用它们做文件名和内容搜索，不想自己拼一长串 shell 命令。
- 用户明确问「终端文件管理器」「yazi 怎么装 / 怎么配置 / 这个键位是什么」。
- 要给它加插件、换配色、改键位，需要有人帮忙写 `~/.config/yazi/` 下的 TOML 配置。

**不要用它**：

- 用户要的是**无人值守的批处理**（比如「把 /data 下所有 CSV 转 Parquet」）。它不是脚本工具，交互式界面反而是障碍，直接写 shell 或 Python。
- 用户要的是**带 Web 界面、多人账号、权限隔离**的文件服务。它没有服务端、没有用户系统，这种情况应该用别的方案。
- 用户要的是**备份 / 版本化 / 增量归档**。它只做文件搬运，不保存历史版本，删了就是删了（除非走回收站）。
- 目标环境是**图形桌面**且用户已经习惯 GUI 文件管理器。装了也用不上，属于白费功夫。
- 只想**查看单个文件内容**（`cat` / `less` / `bat` 就够）。为了看一个文件装一个 TUI 文件管理器不划算。

## 安装

先确认一个硬前置：它靠 `file(1)` 判断文件类型，**这个必须有**，否则启动后预览和打开行为都不正常。

Arch Linux（一次把可选依赖装全）：

```bash
sudo pacman -S yazi ffmpeg 7zip jq poppler fd ripgrep fzf zoxide resvg imagemagick
```

Debian / Ubuntu（官方 APT 源，有 amd64 与 arm64 的 stable 和 nightly）：

```bash
curl -fsSL https://yazi-rs.github.io/builds/yazi-keyring.gpg | sudo tee /usr/share/keyrings/yazi-keyring.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/yazi-keyring.gpg] https://yazi-rs.github.io/builds/ stable main' | sudo tee /etc/apt/sources.list.d/yazi.list >/dev/null
sudo apt update && sudo apt install yazi
```

macOS（Homebrew）：

```bash
brew update
brew install yazi ffmpeg-full sevenzip jq poppler fd ripgrep fzf zoxide resvg imagemagick-full font-symbols-only-nerd-font
brew link ffmpeg-full imagemagick-full -f --overwrite
```

Windows（Scoop / WinGet 二选一）：

```powershell
scoop install yazi
scoop install ffmpeg 7zip jq poppler fd ripgrep fzf zoxide resvg imagemagick
```

```powershell
winget install sxyazi.yazi
winget install Gyan.FFmpeg 7zip.7zip jqlang.jq oschwartz10612.Poppler sharkdp.fd BurntSushi.ripgrep.MSVC junegunn.fzf ajeetdsouza.zoxide ImageMagick.ImageMagick
```

Fedora / RHEL 9+（走社区 COPR）：

```bash
sudo dnf copr enable lihaohong/yazi
sudo dnf install yazi
```

Docker / 容器环境没有官方镜像，容器里通常直接用发行版包管理器装；真要在容器里用，记得把终端和字形一起带进去，否则界面会是乱码方块。

Windows 上还有一步必须做——让它能找到 `file.exe`，加一个环境变量指向 Git for Windows 自带的那份：

```powershell
$env:YAZI_FILE_ONE = 'C:\Program Files\Git\usr\bin\file.exe'
```

装完先验一下，两个命令都要能出版本号：

```bash
yazi --version
ya --version
```

`ya` 是配套命令行工具（插件/配色管理、DDS 消息收发），多数发行版的包会一起装；如果只装到了主程序，`ya` 需要自己从源码编译，且**两者版本必须完全一致**。

## 常用操作

**1. 起界面，并让退出时把 shell 的当前目录带过去**

裸跑 `yazi` 也能用，但退出后 shell 还停在原目录。官方给的 shell wrapper 解决这个问题，把它写进 `~/.bashrc`：

```bash
function y() {
	local tmp cwd; tmp="$(mktemp -t "yazi-cwd.XXXXXX")"
	command yazi "$@" --cwd-file="$tmp"
	IFS= read -r -d '' cwd < "$tmp"
	[ "$cwd" != "$PWD" ] && [ -d "$cwd" ] && builtin cd -- "$cwd" || builtin true
	command rm -f -- "$tmp"
}
```

之后用 `y` 启动、用 `q` 退出就会留在离开时的目录；想退出但**不**换目录就按 `Q`。
PowerShell / CMD / fish / nushell 各有对应写法，见官方 Quick Start 页。

**2. 装插件和配色（`ya pkg`）**

`owner/repo` 形式，或从 monorepo 里取子目录（用 `:` 隔开）：

```bash
ya pkg add yazi-rs/plugins:git
ya pkg add owner/my-plugin
ya pkg list
```

一次装多个、或者删掉：

```bash
ya pkg add owner/my-plugin yazi-rs/plugins:git
ya pkg delete yazi-rs/plugins:git
```

换机器时按锁定版本恢复，或整体升级：

```bash
ya pkg install     # 按 package.toml 里锁定的版本装齐
ya pkg upgrade     # 升到最新
```

注意 `ya pkg delete` 默认会**保留**你对插件做的本地改动，想连改动一起丢掉要加 `--discard`。

**3. 清缓存**

图片预览和缩略图会落在缓存目录里，长期用下来会明显涨体积：

```bash
ya cache clear
```

**4. 修改键位**

配置文件在 `~/.config/yazi/`（Windows 是 `%APPDATA%\yazi\config\`），主文件是 `keymap.toml`、`yazi.toml`、`theme.toml`。
想改键位不要直接改默认文件，把自己的绑定写进 `keymap.toml` 的 `mgr.prepend_keymap`：

```toml
[[mgr.prepend_keymap]]
on   = [ "c", "m" ]
run  = "plugin chmod"
desc = "修改选中文件的权限"
```

`run` 里既可以写内置动作名，也可以写 `plugin <插件名> <参数>`；`desc` 是 `~` 帮助菜单里显示的文字，建议写清楚。

**5. 用内部动作做批处理式的定位**

常用键位（Vim 风格，方向键同样可用）：

| 操作 | 键位 |
|---|---|
| 上/下移动光标 | `k` / `j` |
| 进入目录 / 返回上级 | `l` / `h` |
| 多选切换 / 可视模式 | `Space` / `v` |
| 复制(剪切) / 粘贴 | `y`(`x`) / `p`（`P` 覆盖粘贴） |
| 移到回收站 / 彻底删除 | `d` / `D` |
| 新建 / 重命名 | `a` / `r` |
| 按文件名搜 / 按内容搜 | `s`（找 `fd`）/ `S`（找 `rg`） |
| 过滤 / 查找 | `f` / `/` |
| 跳转目录 | `z`（走 `fzf`）/ `Z`（走 `zoxide`） |
| 任务管理器 | `w` |
| 帮助菜单 | `F1` 或 `~` |

**6. 查运行环境和配置落点**

配置不生效、或者插件找不到路径时，先让它自己报：

```bash
ya env
```

它会打印环境与配置信息，比猜路径快。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 预览里图片是乱码方块，或者干脆不出图 | 终端不支持图像协议，或走的是兜底 ASCII 分支 | 换用原生支持 Kitty / iTerm2 / Sixel 协议的终端；X11/Wayland 下需要额外装 Überzug++，纯 ASCII 兜底需要 Chafa。见官方 image-preview 页确认自己的终端走哪条路 |
| 图标全是豆腐块 | 没装 Nerd Fonts，或终端字体没切换过去 | 装 nerd-fonts 并在终端设置里把字体改成它；官方 FAQ 有「不喜欢 Nerd Fonts」的替代做法 |
| 启动直接报找不到 `file` | 它是靠 `file(1)` 判类型的，缺了就跑不起来 | Linux 装 `file` 包；Windows 必须把 Git for Windows 自带的 `file.exe` 路径写进 `YAZI_FILE_ONE` 环境变量，改完重开终端 |
| Windows 上用 Scoop/Chocolatey 装的 `file` 读不了中文名或带变音符号的文件 | 那两个渠道的 `file` 处理 Unicode 文件名有问题，也缺必需参数 | 不要在 Windows 上从这两个渠道装 `file`；改用 Git for Windows 自带的那份，或装扩展名判类型的插件 |
| `ya: command not found`，或 `ya` 与 `yazi` 行为对不上 | 发行版只装了主程序，或者两者版本不一致 | 两个版本必须完全一致；缺失时从源码一起编译安装 |
| `ya pkg` 拉取插件报网络错误 | 它从代码托管站直接 clone，国内网络经常连不上 | 给 git 配代理，或手工把插件目录放到配置目录的 `plugins/` 下再补 `package.toml` 条目 |
| 改完 `yazi.toml` / `keymap.toml` 没反应 | TOML 语法写错被静默忽略，或者改的是别的配置目录 | 用 TOML 校验器过一遍；如果设置了 `YAZI_CONFIG_HOME`，配置就在那个目录而**不是**默认的 `~/.config/yazi/` |
| `q` 退出后 shell 目录没变 | 没有用 shell wrapper，或者退出时按的是大写 `Q` | 把 wrapper 函数写进 shell 配置并重新 source；`q` 带目录、`Q` 不带 |
| 任务跑一半想退出，被拦住 | 有未完成的后台任务时会弹确认 | 按 `w` 打开任务管理器，等任务结束或取消它，再退出 |
| Windows Terminal 里图片预览高度不对 | 版本太老，Sixel 支持不完整 | 升级到较新的 Windows Terminal；官方安装页列出了要求的最低版本 |
| 大目录下翻页发卡 | 预览预加载吃了太多内存/线程 | 调 `[tasks]` 下的 `preload_workers`、`image_alloc`，或把 `suppress_preload` 打开 |
| 装完 `yazi` 后 `y` 命令不存在 | wrapper 是可选的手动步骤，包管理器不会替你装 | 按上面「常用操作」第 1 条自己写进 shell 配置 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（间接用） | 程序本身不联网；`ya pkg add/install/upgrade` 会从代码托管站 clone 插件、配色，这一步要网络 |
| 读取文件 | 是 | 这是它的核心功能：读取目录列表、文件元数据、文件内容用于预览与搜索 |
| 写入文件 | 是 | 复制、移动、重命名、删除文件；写入回收站；写 `~/.config/yazi/` 下配置；写缓存目录（图片缩略图、插件包） |
| 凭证 | 否 | 不需要账号或 Key；插件若接第三方服务，凭据由用户自行在插件配置里提供 |
| 子进程 / 后台常驻 | 是 | 会调用 `file`、`fd`、`rg`、`fzf`、`zoxide`、`ffmpeg`、`7z`、`poppler` 等外部命令；打开文件时会按 `opener` 配置拉起外部程序；同时内建后台任务队列（异步 I/O + 多线程） |

## 触发场景

- 「服务器上怎么快速翻文件，不想一直 `ls`」
- 「yazi 怎么装 / 怎么配图标字体 / 图片预览不出来」
- 「怎么给 yazi 装插件和配色」
- 「yazi 的快捷键有哪些，怎么改键位」
- 「终端里的文件管理器推荐一个，要能预览图片的」
- 「yazi 退出之后能停在我离开的目录吗」

## 能力边界

**覆盖**：

- 终端内的文件浏览、多选、复制/移动/删除/重命名、批量重命名、新建、软硬链接、回收站。
- 用外部工具做文件名搜索（`fd`）和内容搜索（`rg`）、历史目录跳转（`zoxide`）、模糊跳转（`fzf`）。
- 文件预览：图片、视频缩略图、PDF、压缩包内容、代码高亮、字体、各类归档与磁盘镜像。
- 插件体系（UI / 预览器 / 预加载器 / 取词器 / 功能插件）、配色包、键位与主题自定义。
- 远程文件管理能力（虚拟文件系统），以及基于客户端-服务端架构的跨实例消息发布订阅。

**不覆盖**：

- 任何形式的**备份、版本历史、增量归档**——它不做数据保护。
- **文件同步**到你自己的多台设备，也没有 Web 界面、多用户、权限体系。
- **批量脚本化处理**：不能拿它当流水线的一环去转换/编码文件。
- 它**不遵循符号链接**去备份或递归（浏览时可以进去，但这不是「复制链接目标」的语义）。
- 不负责**文件内容编辑**：编辑器由 `opener` 配置决定，它只负责把你交给外部程序。

## 依赖条件

- 硬依赖：`file(1)`（文件类型识别）。没有它无法正常工作。
- 可选但强烈建议：`nerd-fonts`（图标）、`ffmpeg`（视频缩略图）、`7-Zip`（非 standalone 版，用于解压与归档预览）、`jq`（JSON 预览）、`poppler`（PDF 预览）、`resvg`（SVG 预览）、ImageMagick（字体 / HEIC / JPEG XL 预览）、`fd`、`rg`、`fzf`、`zoxide`。
- Linux 剪贴板支持需要 `xclip` / `wl-clipboard` / `xsel` 之一。
- 终端需要支持对应的图像协议（Kitty / iTerm2 / Sixel 等）才能出图，否则只能走 ASCII 兜底。
- 不需要账号、不需要 API Key。
- 版本注意：它目前处于公开 beta、迭代很快，会有破坏性变更；升级前建议先看一眼 release 说明。

## 已知限制

1. 项目自述为 public beta，配置项与插件接口都可能变动，锁版本的发行版包往往偏旧。
2. Windows 上 `file(1)` 的问题只能按官方建议的那一种方式解决，其他渠道装的那份对 Unicode 文件名不可靠。
3. 走 Flatpak 版本受沙箱限制较多，功能会有缺失，重度使用不建议。
4. 视频缩略图需要用 `ffmpeg` 先**生成**缩略图缓存，第一次预览大视频会慢，不是卡死。
5. `ya pkg` 的插件来源是代码托管站直连，网络受限环境下需要自行配置代理或手工放置。

## 自检清单

- [ ] `yazi --version` 与 `ya --version` 都能输出，且版本号一致
- [ ] `file --version` 可执行（Windows 上确认 `YAZI_FILE_ONE` 已指向 `file.exe`）
- [ ] 启动后能看到图标而不是豆腐块，说明终端字体已切到 Nerd Font
- [ ] 预览一张图片，确认图像协议生效而不是 ASCII 方块
- [ ] 按 `F1`（或 `~`）能打开帮助菜单，说明界面没退化到兜底模式
- [ ] 若装了 wrapper：用 `y` 进入子目录、`q` 退出，确认 shell 目录真的变了
- [ ] 改过配置后按 `ya env` 确认配置目录是不是你以为的那个

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/sxyazi/yazi | 上游仓库（安装与完整文档以它为准） |
| https://yazi-rs.github.io/docs/installation | 各平台安装方式与依赖清单（以它为准） |
| https://yazi-rs.github.io/docs/quick-start | 键位表与 shell wrapper 原文 |
| https://yazi-rs.github.io/docs/cli | `ya` 子命令说明 |

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
