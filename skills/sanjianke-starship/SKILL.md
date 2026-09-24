---
name: sanjianke-starship
slug: sanjianke-starship
displayName: 三剪客 · 跨 Shell 提示符引擎
description: "starship：跨 Shell 提示符引擎 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "starship：跨 Shell 提示符引擎 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · 跨 Shell 提示符引擎

终端提示符一旦自己手写，就会变成一堆越堆越乱的 `PS1` 拼接：Git 分支、Python 虚拟环境、Node 版本、上一条命令耗时，全靠一张 `if` 网撑着，换个 Shell 又得重写一遍。starship 把这件事收进一个跨 Shell 的提示符引擎——你只维护一份 TOML 配置，Bash、Zsh、Fish、PowerShell、Nushell 等都能读到同一套提示符；模块按需出现，没进 Git 仓库就不显示分支，没装 Node 就不显示版本号。

**上游项目**：`starship`　**仓库**：https://github.com/starship/starship

## 什么时候用 / 不用

**用它**：

- 用户说「我的终端提示符太丑 / 看不到 Git 分支和当前 Python 环境」，想要一个开箱可用的现代提示符。
- 同一个人要在多台机器、多个 Shell（本机 Zsh + 服务器 Bash + Windows PowerShell）之间保持一致的外观。
- 希望在提示符里看到「上一条命令跑了多久」「当前是哪个云账号/which context」这类上下文，而不是每次手敲命令查。
- 需要一个可版本化的提示符配置：把 `starship.toml` 提交进 dotfiles 仓库，换机即还原。
- 想在现有主题之上做减法——大概率只需要关掉几个模块，而不是换掉整个主题。

**不要用它**：

- Shell 是 **Cmd（传统命令提示符）** 且不打算装 Clink：starship 在 Cmd 里依赖 Clink 才能工作，纯 Cmd 不是它的运行环境。
- 用户要的是「命令补全、语法高亮、历史搜索」这类交互增强——那是补全/高亮插件的事，starship 只管提示符那一行。
- 想要图形化、可拖拽、所见即所得的提示符设计器：starship 的配置就是文本文件，没有 GUI。
- 机器上有严格的安全审计要求，不允许提示符渲染时执行外部命令：starship 的模块会按需调用 `git`、`node --version` 等命令取信息，取不到就空着，但确实会产生子进程调用。
- 只想要一个固定在 `.bashrc` 里、永不改动的静态 `PS1`：引入引擎反而多一层依赖和启动开销。

## 安装

Windows（PowerShell）：

```powershell
winget install --id Starship.Starship
# 或
scoop install starship
# 或
choco install starship
```

macOS：

```bash
brew install starship
# 或
curl -sS https://starship.rs/install.sh | sh
```

Linux：

```bash
curl -sS https://starship.rs/install.sh | sh   # 通用安装脚本
# 发行版包管理器
sudo pacman -S starship          # Arch / Manjaro
sudo apt install starship        # Debian 13+ / Ubuntu 25.04+
sudo dnf install starship        # Fedora（必要时先启用对应 Copr 源）
sudo apk add starship            # Alpine 3.13+
```

任何平台都可以用 Rust 工具链安装：

```bash
cargo install starship --locked
```

装完必须**在你的 Shell 启动文件里初始化**，通常是**最后一行**：

```bash
# Bash：~/.bashrc 末尾
eval "$(starship init bash)"

# Zsh：~/.zshrc 末尾
eval "$(starship init zsh)"

# Fish：~/.config/fish/config.fish
starship init fish | source
```

```powershell
# PowerShell：$PROFILE 末尾
Invoke-Expression (&starship init powershell)
```

Nushell 用户需要在配置里写到 autoload 目录（用 `$nu.config-path` 找配置文件）：

```bash
mkdir ($nu.data-dir | path join "vendor/autoload")
starship init nu | save -f ($nu.data-dir | path join "vendor/autoload/starship.nu")
```

## 常用操作

**1. 建配置文件并写第一条自定义**

```bash
mkdir -p ~/.config && touch ~/.config/starship.toml
```

```toml
# ~/.config/starship.toml
"$schema" = 'https://starship.rs/config-schema.json'
add_newline = true                       # 提示符之间插入空行

[character]                              # 提示符最前面那个箭头
success_symbol = '[➜](bold green)'
error_symbol = '[✗](bold red)'

[package]                                # 不需要的模块直接关掉
disabled = true
```

**2. 单次临时换一份配置（不动默认文件）**

```bash
STARSHIP_CONFIG=~/dotfiles/starship.work.toml exec zsh
```

PowerShell 等价写法（加进 `$PROFILE`）：

```powershell
$ENV:STARSHIP_CONFIG = "$HOME\dotfiles\starship.work.toml"
```

**3. 把模块内容单独打印出来，排查某个模块到底渲染了什么**

```bash
starship module character
starship module directory
starship module git_status
```

**4. 用官方预设起步，再按需改**

```bash
starship preset --list
starship preset nerd-font-symbols -o ~/.config/starship.toml
```

预设名与可用清单以官方文档为准。注意 `-o` 会**整份覆盖**目标文件，建议先备份现有配置。

**5. 把右侧区域也利用起来（多行/右对齐提示符）**

```toml
# ~/.config/starship.toml
format = """$character"""      # 左侧只留箭头
right_format = """$all"""      # 其余模块全部推到右边
```

Zsh 用户如果发现右侧对齐差一格，在 `~/.zshrc` 里加：

```bash
ZLE_RPROMPT_INDENT=0
```

**6. 调整扫描/命令超时，避免大仓库里卡顿**

```toml
# ~/.config/starship.toml
scan_timeout = 10        # 文件扫描超时（毫秒），默认 30
command_timeout = 500    # 外部命令超时（毫秒），默认 500
follow_symlinks = false  # 符号链接指向网络盘时建议关掉
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 提示符里出现方框、问号、乱码小方块 | 终端字体不含 Nerd Font 图标字形 | 安装并在终端里显式选中一款 Nerd Font（如 FiraCode Nerd Font），然后重开终端 |
| 装完没任何变化 | 只装了二进制，没在 Shell 启动文件里 `init`；或 `init` 那行不是最后一行，被后面的主题设置覆盖 | 确认 `starship init <shell>` 写在启动文件**末尾**，并 `exec zsh` / 重开终端，不要用 `source ~/.zshrc` |
| `starship: command not found`，但明明装过 | `cargo install` 的默认输出目录不在 `PATH`（通常是 `~/.cargo/bin`） | 把该目录加进 `PATH`，或用包管理器/安装脚本重装 |
| 提示符每次回车都有明显延迟 | 自定义模块或 `command_timeout` 内执行的命令本身慢；仓库巨大导致扫描慢 | 调小 `scan_timeout`，给慢模块设 `disabled = true`，或把自定义命令改成读缓存文件 |
| 想在 `format` 里显示 `$`、`[`、`]`、`(`、`)` 却显示异常 | 这些字符在格式串里有特殊含义 | 用 `\` 转义，例如 `format = '\[\$\] '` |
| Git 分支/状态不显示 | 当前目录不在 Git 仓库内（这是设计行为，不是 bug）；或模块被显式 `disabled` | 先 `git status` 确认在仓库里，再检查配置里是否关掉了 `[git_branch]` / `[git_status]` |
| Bash 里命令耗时模块失效或行为怪异 | 在 `starship init bash` 之后又挂了 `DEBUG` trap，覆盖了 starship 的钩子 | 先设置 trap 再初始化，或改用 `starship_precmd_user_func` 这类官方钩子 |
| Windows 上 PowerShell 报「禁止运行脚本」 | 执行策略限制，配置文件的加载被拦 | 按组织策略调整执行策略或改用其他 Shell；不要为了绕过策略而放宽全局安全设置 |
| 出错时完全看不到原因 | 默认日志落在 `~/.cache/starship/session_${STARSHIP_SESSION_KEY}.log`，平时没人会去看 | `export STARSHIP_CACHE=~/.starship/cache` 换到好找的目录，出问题时读日志 |
| 多行提示符在终端缩放后错位 | 终端对长行做 reflow，提示符行高变化 | 用 `$fill` 模块做右对齐替代手写空格；把提示符行数固定下来，避免依赖会被 reflow 的长行 |
| 改了 `starship.toml` 但样式没变 | 配置改的是别的路径，或用 `STARSHIP_CONFIG` 指向了另一份文件 | `echo $STARSHIP_CONFIG` 确认实际生效路径；没设置时默认是 `~/.config/starship.toml` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（仅安装时） | 安装脚本/包管理器需要联网下载二进制；提示符运行期不联网 |
| 读取文件 | 是 | 读取 `starship.toml` 配置文件、当前目录文件列表（用于模块探测）、`~/.gitconfig` 等 |
| 写入文件 | 是（受限） | `starship preset -o` 覆盖写出配置文件；运行期写日志到缓存目录 |
| 凭证 | 否 | starship 自身不保存任何账号、Key、Token；只读取环境变量与已有配置文件的内容来决定显示什么 |
| 子进程 / 后台常驻 | 是 | 为模块信息按需调用 `git`、`node`、`python` 等命令；无常驻后台进程 |

## 触发场景

- 「帮我配一个好看的终端提示符」
- 「怎么让终端显示 Git 分支、当前 Python/Node 版本」
- 「换电脑之后提示符不一样了，怎么统一」
- 「PowerShell 里怎么显示上一条命令跑了多久」
- 「提示符里的图标显示成方框了」
- 「starship 装好了但没生效」

## 能力边界

**覆盖**：

- 跨 Shell（Bash / Zsh / Fish / PowerShell / Nushell / Elvish / Tcsh / Xonsh / Ion / Cmd+Clink）的统一提示符渲染。
- 提示符内容模块化配置：目录、Git 状态、语言运行时版本、云账号上下文、命令耗时、电量、时间等，按目录内容自动出现或隐藏。
- 配置文件路径与日志路径的环境变量覆盖（`STARSHIP_CONFIG`、`STARSHIP_CACHE`）。
- 官方预设的应用，以及 `format` / `right_format` / `continuation_prompt` 级别的版式控制。
- Windows、macOS、Linux 三平台的多种安装途径。

**不覆盖**：

- 命令补全、语法高亮、历史模糊搜索——这些不属于提示符引擎的职责。
- 图形化配置界面；所有定制都通过编辑 TOML 完成。
- Shell 本身的配置管理（函数、别名、插件管理器的安装与维护）。
- 远程/容器环境的 Shell 初始化分发；跨机器同步配置需要你自己用 dotfiles 工具解决。
- 提示符的最终渲染效果——字体、行高、powerline 字形是否对齐由终端与字体决定，starship 无法保证像素级效果。

## 依赖条件

- 一个受支持的 Shell：Bash、Zsh、Fish、PowerShell、Nushell（v0.96+）、Elvish（v0.18+）等。
- 建议安装一款 Nerd Font 并在终端中启用，否则图标类字形会显示为方框。
- Windows 下若坚持用 Cmd，需要另装 Clink（v1.2.30+）。
- 无需任何账号或 API Key。
- 通过 `cargo install` 安装时，需要 Rust 工具链，并注意 `~/.cargo/bin` 是否在 `PATH` 中。

## 已知限制

- 提示符渲染依赖外部命令取信息，取不到就按空值处理；不会报错，也不会回退到猜测值。
- `scan_timeout` 与 `command_timeout` 是毫秒级硬超时，网络盘、巨型仓库、慢命令下会出现模块信息缺失而不是等待。
- 主题效果强依赖终端与字体，powerline 字形在不同终端里可能出现亚像素错位，这属于终端渲染范畴。
- 官方文档标注部分高级配置项可能在未来版本变动，升级前建议先看变更说明。
- Cmd 下的能力明显弱于其他 Shell，且需要 Clink 作为前置。

## 自检清单

- 执行前：确认目标 Shell 与操作系统；确认字体是否支持 Nerd Font；确认 `starship.toml` 的实际生效路径（`echo $STARSHIP_CONFIG` 或默认路径）。
- 执行中：`init` 那行必须写在 Shell 启动文件的最后；改动配置后优先重开终端或用 `exec <shell>`，不要 `source` 启动文件。
- 执行后：新开一个终端确认提示符生效；进 Git 仓库确认分支模块出现；`starship module <名称>` 单独验证可疑模块；出问题先读缓存目录下的 session 日志。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/starship/starship | 上游仓库（安装与完整文档以它为准） |
| https://starship.rs/config/ | 全部模块与配置项的官方说明 |

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
