# 三剪客 · 终端文件管理器 Skill

yazi：终端文件管理器 的安装、常用命令与避坑要点

---

## 前置条件

- 一个支持真彩色的终端。要出图片预览，终端还得支持 Kitty 图像协议、iTerm2 内联图像或 Sixel 之一；否则只能退化成 ASCII 字符画。
- **`file(1)` 必须存在**——它靠这个判断文件 MIME 类型，缺了无法正常工作。
  - Linux / macOS：装 `file` 包即可。
  - Windows：推荐装 Git for Windows，然后把 `<Git 安装目录>\usr\bin\file.exe` 的路径写进 `YAZI_FILE_ONE` 环境变量，例如 `C:\Program Files\Git\usr\bin\file.exe`，然后重开终端。**不要**用 Scoop / Chocolatey 装 `file`，那两个渠道的版本处理 Unicode 文件名不可靠、还缺必需参数。
- 建议装 Nerd Fonts，否则界面里的图标会显示成方块。
- 需要 `~/.config/yazi/`（Windows 为 `%APPDATA%\yazi\config\`）的写权限，用于存放配置、插件和配色。
- 不需要任何账号、Key 或联网授权；只有 `ya pkg` 拉插件/配色时才需要网络。

---

## 使用

最短跑通路径（Arch Linux 为例，一次把主程序和常用可选依赖装齐）：

```bash
sudo pacman -S yazi ffmpeg 7zip jq poppler fd ripgrep fzf zoxide resvg imagemagick
yazi
```

macOS 走 Homebrew，Windows 走 Scoop 或 WinGet：

```bash
brew install yazi ffmpeg-full sevenzip jq poppler fd ripgrep fzf zoxide resvg imagemagick-full font-symbols-only-nerd-font
```

```powershell
scoop install yazi
scoop install ffmpeg 7zip jq poppler fd ripgrep fzf zoxide resvg imagemagick
```

装完先验证版本，`ya`（配套命令行工具）与主程序版本必须一致：

```bash
yazi --version
ya --version
```

进界面后，`hjkl` 或方向键移动，`q` 退出，`F1`（或 `~`）打开帮助菜单。想让退出时把 shell 的当前目录也带过去，把官方的 shell wrapper 写进 shell 配置（Bash 示例）：

```bash
function y() {
	local tmp cwd; tmp="$(mktemp -t "yazi-cwd.XXXXXX")"
	command yazi "$@" --cwd-file="$tmp"
	IFS= read -r -d '' cwd < "$tmp"
	[ "$cwd" != "$PWD" ] && [ -d "$cwd" ] && builtin cd -- "$cwd" || builtin true
	command rm -f -- "$tmp"
}
```

之后用 `y` 启动、`q` 退出会换目录，`Q` 退出不换。插件与配色用 `ya pkg` 管理：

```bash
ya pkg add yazi-rs/plugins:git
ya pkg list
ya pkg upgrade
```

本 Skill 的完整操作说明、键位表与排错表见 `SKILL.md`。

---

## 依赖

| 依赖 | 必要性 | 缺了会怎样 |
|---|---|---|
| `file` | **必需** | 无法识别文件类型，启动即报错 |
| Nerd Fonts | 强烈建议 | 图标显示为豆腐块 |
| `ffmpeg` | 可选 | 没有视频缩略图 |
| 7-Zip（非 standalone 版） | 可选 | 不能解压归档，也不能预览归档内容 |
| `jq` | 可选 | 没有 JSON 预览 |
| `poppler` | 可选 | 没有 PDF 预览 |
| `fd` | 可选 | `s` 键按文件名搜索不可用 |
| `rg` | 可选 | `S` 键按内容搜索不可用 |
| `fzf`（>= 0.53.0） | 可选 | `z` 键模糊跳转不可用 |
| `zoxide` | 可选 | `Z` 键历史目录跳转不可用（依赖 `fzf`） |
| `resvg` | 可选 | 没有 SVG 预览 |
| ImageMagick（>= 7.1.1） | 可选 | 字体 / HEIC / JPEG XL 预览不可用 |
| `xclip` / `wl-clipboard` / `xsel` | 可选 | Linux 下剪贴板功能不可用（三者取其一） |
| Überzug++ | 可选 | X11 / Wayland 下出图需要它 |
| Chafa（>= 1.16.0） | 可选 | 兜底的 ASCII 字符画需要它 |

程序本身是静态编译的 Rust 二进制，运行时不需要额外的语言运行时。

---

## 安全

- 不内嵌任何密钥。
- 它拥有**你当前用户的完整文件读写权限**：`D` 是彻底删除（不走回收站），`d` 才是移入回收站。删掉的东西没有版本历史可恢复。
- 打开文件时它会按 `opener` 配置**拉起外部程序**（默认如 `xdg-open`、`open`、`start`，以及 `$EDITOR`）。要跑不可信文件时，先看一眼自己的 `opener` 与 `open.rules` 配置。
- 配置支持插件（Lua）与 shell 命令。`prepend_keymap` / `opener` 里写什么就会执行什么，**不要**把来源不明的插件配置直接粘进自己的配置目录。
- `ya pkg add` 会从代码托管站 clone 代码并落盘到配置目录，属可执行内容的引入；只装你信任的来源，并注意 `package.toml` 里锁定的 `rev` 与 `hash`。
- 缓存目录会积累图片缩略图，属于可清理数据，不含敏感凭据。
- 以 root 运行它等于把一个可以执行任意 opener 的界面交给 root：确有必要时再用，用完即退。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`yazi`
- 仓库：https://github.com/sxyazi/yazi

---

## 许可证

MIT，见 `LICENSE.md`。

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
