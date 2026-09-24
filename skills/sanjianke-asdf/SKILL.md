---
name: sanjianke-asdf
slug: sanjianke-asdf
displayName: 三剪客 · 多语言运行时版本管理
description: "asdf：多语言运行时版本管理 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "asdf：多语言运行时版本管理 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · 多语言运行时版本管理

同一个项目要 Node 18、下一个项目要 Node 20，机器上还并存着两套 Python —— 这类「多版本运行时并存」的麻烦，靠手工改 `PATH` 迟早出错。asdf 用**一个可执行文件**统一管住所有语言运行时：插件负责「怎么装」，`.tool-versions` 文件负责「这个目录用哪一版」，你进目录执行 `node` 时它按就近原则解析版本。

它的价值不在「装得多」，而在**版本跟着目录走**：版本声明可以随代码一起提交进 Git，换机器、换同事、换 CI 都自动一致。

注意 asdf 经历过大改版，网上大量老资料里的 `asdf global` / `asdf local` 已经不是主线写法，本文按新版命令给。

**上游项目**：`asdf`　**仓库**：https://github.com/asdf-vm/asdf

## 什么时候用 / 不用

**用它**：

- 「我同时做三个项目，一个要 Python 3.9、一个要 3.12，怎么让它们互不打扰？」
- 「仓库里有个 `.tool-versions`，帮我看看该装哪几个版本。」
- 「新同事拉了这个仓库跑不起来，提示运行时版本不对」——需要统一团队本机的语言版本。
- 「给 CI 固定一份运行时版本清单」——`.tool-versions` 能跟着代码一起提交。
- 「装 Node / Python / Ruby / Go 的某个具体版本，别用系统自带那份。」

**不要用它**：

- **Windows 原生环境**：asdf 主线面向 Linux / macOS，Windows 侧官方安装说明走 **WSL**；不要在纯 Windows 上硬装。
- 只装**一个**运行时、以后也不换版本：直接从官网装更省事，不必引入「插件 + shim」这两层。
- 需要**容器级强隔离或可复现构建**：容器镜像、虚拟环境、语言自带的依赖锁文件才是那类需求的正解；asdf 只管「用哪个解释器」，不管依赖锁定。
- 团队已经在用 **nvm / pyenv / rbenv 那套流程且不打算迁移**：换版本管理器是团队决策，单机换过去只会让版本来源更乱。
- 只想跑系统自带那份运行时：`asdf set <name> system` 能把管理权交回系统，但若连插件都不想加，就不该引入它。

## 安装

下面命令来自官方文档的安装页。asdf 本体只依赖 `git`，另外请装好 `bash`。

```bash
# ---- Linux / macOS：包管理器（官方推荐） ----
brew install asdf                       # Homebrew（macOS / Linux 均可）
zypper install asdf                     # openSUSE
# Arch（AUR）
git clone https://aur.archlinux.org/asdf-vm.git && cd asdf-vm && makepkg -si

# ---- 预编译二进制（最省事） ----
# 到 releases 页下载对应系统/架构的压缩包，
# 解出 asdf 二进制放进 $PATH 里的某个目录，然后核对：
type -a asdf

# ---- go install ----
go install github.com/asdf-vm/asdf/cmd/asdf@v0.20.0

# ---- 从源码构建 ----
git clone https://github.com/asdf-vm/asdf.git --branch v0.20.0
cd asdf && make
# 再把编出来的 asdf 二进制复制进 $PATH
```

装完**必须配置 shell**，否则版本不会生效。核心只有一件事：把 shims 目录加进 `PATH`。

```bash
# Bash：写进 ~/.bash_profile
export PATH="${ASDF_DATA_DIR:-$HOME/.asdf}/shims:$PATH"

# ZSH：写进 ~/.zshrc
export PATH="${ASDF_DATA_DIR:-$HOME/.asdf}/shims:$PATH"

# POSIX sh：写进 ~/.profile
export PATH="${ASDF_DATA_DIR:-$HOME/.asdf}/shims:$PATH"

# Fish：写进 ~/.config/fish/config.fish（片段）
if test -z $ASDF_DATA_DIR
    set _asdf_shims "$HOME/.asdf/shims"
else
    set _asdf_shims "$ASDF_DATA_DIR/shims"
end
if not contains $_asdf_shims $PATH
    set -gx --prepend PATH $_asdf_shims
end
set --erase _asdf_shims
```

可选：命令补全。Bash 用 `. <(asdf completion bash)`；Fish 用 `asdf completion fish > ~/.config/fish/completions/asdf.fish`；ZSH 用 `asdf completion zsh > "${ASDF_DATA_DIR:-$HOME/.asdf}/completions/_asdf"`；Nushell 用 `asdf completion nushell | save -f <路径>`。PowerShell Core 侧官方标注**暂无补全**。

数据目录默认是 `$HOME/.asdf`。要换位置就设 `ASDF_DATA_DIR`，并把它写在 `PATH` 那行**之前**。

Windows 用户：官方安装说明对 Windows 走 **WSL**，装完按 Linux 那套配。<https://asdf-vm.com/guide/getting-started.html>

## 常用操作

```bash
# 1) 装插件。短名会去官方插件索引里查，也可以直接给 Git 地址
asdf plugin add nodejs https://github.com/asdf-vm/asdf-nodejs.git
asdf plugin list                 # 已装插件
asdf plugin list all             # 索引里能装的全部插件
asdf plugin update --all         # 更新所有插件

# 2) 看有哪些版本可装 / 装一个
asdf list all nodejs             # 该工具的可用版本
asdf list all nodejs 20          # 只看 20.x
asdf install nodejs latest       # latest 会解析成当下真实版本号
asdf install nodejs 20.11.1      # 精确版本
asdf install nodejs latest:20    # 20.x 里最新的稳定版
asdf install                     # 按当前目录 .tool-versions 把缺的都装上

# 3) 设版本（写进当前目录的 .tool-versions，文件不存在会创建）
asdf set nodejs 20.11.1
asdf set -u nodejs 20.11.1       # -u/--home：写到 $HOME/.tool-versions，当全局默认
asdf set -p nodejs 20.11.1       # -p/--parent：写到最近的上级 .tool-versions
asdf set python system           # 把管理权交回系统自带的那份

# 4) 看当前到底用的哪个版本 / 装在哪
asdf current                     # 所有工具 + 版本 + 来源文件
asdf current nodejs
asdf where nodejs                # 安装目录
asdf which node                  # 可执行文件路径
asdf shimversions node           # 哪些插件/版本提供了这个命令

# 5) 卸载与维护
asdf uninstall nodejs 20.11.1
asdf reshim nodejs 20.11.1       # 重建 shim
asdf plugin remove nodejs        # 连版本一起移除
asdf info                        # 排错时先跑它：OS / Shell / asdf 版本
asdf version

# 6) 临时覆盖：只在这条命令生效，不落文件
ASDF_NODEJS_VERSION=20.11.1 node -v
```

版本还可以用**环境变量**临时顶掉 `.tool-versions`：规则是 `ASDF_${TOOL}_VERSION`，工具名里的短横线要换成下划线（例如工具 `aws-sam-cli` 对应 `ASDF_AWS_SAM_CLI_VERSION`）。

```bash
export ASDF_ELIXIR_VERSION=1.18.1
ASDF_ELIXIR_VERSION=1.4.0 mix test
```

要复用别的版本管理器留下的文件（比如 `.nvmrc`、`.node-version`、`.ruby-version`），在 `$HOME/.asdfrc` 里打开开关：

```
legacy_version_file = yes
```

完整命令清单见 <https://asdf-vm.com/manage/commands.html>，运行时直接 `asdf --help` 或 `asdf help <name>` 也能拿到说明。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 装完 `asdf install` 报「command not found」或版本不生效 | 只装了二进制，没配 shell，shims 目录不在 `PATH` | 按上面把 `PATH` 那行写进对应 shell 的启动文件，**重启 shell** 后 `asdf info` 核对 |
| 工具装了，敲 `node` 还是系统那个 | shims 没进 `PATH`，或 `PATH` 里系统目录排在前面 | `asdf which node` 看实际命中路径；确认 `PATH` 里 shims 在系统目录之前 |
| 换了安装方式后出现两个 asdf，行为不一致 | 旧安装方式残留，`PATH` 命中另一个 | `type -a asdf` 看命中顺序，删掉多余那份 |
| 执行工具报版本解析失败 | 当前目录一路向上都没有 `.tool-versions` | `asdf current` 看解析结果；用 `asdf set` 补一份，或 `asdf set -u` 设全局默认 |
| 装完新版本，命令还是老版本 | shim 没重建 | `asdf reshim <name> <version>` |
| 脚本里 `source` 某个包内的脚本报错 | shim 是 `exec` 包装，**不能 source** | 用 `asdf which` / `asdf where` 拿到真实路径再 source |
| 版本号写了 `latest`，之后行为变了 | `latest` 是执行时解析的助手，不是固定值 | 需要可复现就把 `.tool-versions` 里的 `latest` 换成具体版本号 |
| `.tool-versions` 是有的，但只有某些工具能跑 | 文件里只列了部分工具，没列的会报错 | `asdf current` 逐项核对，把缺的补进文件 |
| 设了 `ASDF_XXX_VERSION` 却没生效 | 变量只在设置它的那个 shell 会话有效 | 要么在当前会话设，要么写进 `.tool-versions` |
| Windows 上装不动 | asdf 主线不覆盖 Windows 原生 | 用 **WSL**，按 Linux 那套装 |
| 装插件后立刻 `asdf install` 失败 | 该插件自己还有系统依赖（编译工具、`curl`、`gawk` 等） | 先打开插件仓库看它列的依赖并装齐，再 `asdf install` |
| 别人给的命令里有 `asdf global` / `asdf local` 报错 | 那是 0.16 之前的老命令 | 新版改用 `asdf set`；全局默认用 `asdf set -u`，上级目录用 `asdf set -p` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 从插件仓库拉取插件与版本清单；下载并编译/解包运行时本体 |
| 读取文件 | 是 | 读取 `.tool-versions`、`$HOME/.asdfrc`、插件脚本 |
| 写入文件 | 是 | 写入或更新 `.tool-versions`；在数据目录（默认 `~/.asdf`）下安装运行时、生成 shims |
| 凭证 | 否 | 不需要账号或 Key。有些插件会调用被管工具自己的登录流程（如 npm），那是被管工具的事 |
| 子进程 / 后台常驻 | 是 | 安装阶段会调用 `git`、`curl`、`make`、`gcc` 等外部程序；运行期由 shim `exec` 真正的可执行文件。asdf 本身不常驻 |

## 触发场景

- 「帮我装个 Node 20，但别动系统里那个 18。」
- 「这个仓库的 `.tool-versions` 怎么用？」
- 「三个项目语言版本冲突，有没有办法按目录自动切？」
- 「团队想统一本机的 Python 版本，怎么固化下来？」
- 「`asdf current` 显示版本是空的，怎么修？」
- 「我把 Node 升级了，为什么命令行还是老版本？」

## 能力边界

**覆盖**：

- 用一个二进制管理多种语言的多个版本：插件机制，官方插件索引 + 任意 Git 仓库作为插件源。
- 按目录解析版本：`.tool-versions` 从当前目录逐级向上查找，`-u` 写 `$HOME`、`-p` 写最近上级。
- 单次命令级覆盖与 shell 级覆盖：`ASDF_${TOOL}_VERSION` 环境变量。
- `latest` / `latest:<前缀>` 解析、`system` 回退、`ref:<分支或提交>` 装源码引用（插件支持时）。
- shim 机制：为包内每个可执行文件生成包装器，运行期解析版本并 `exec`。
- 兼容其它版本管理器的版本文件（`.nvmrc`、`.node-version`、`.ruby-version` 等，按插件支持情况，需开 `legacy_version_file`）。
- 查询类操作：`current` / `where` / `which` / `list` / `list all` / `latest` / `shimversions` / `info`。
- 多 shell 配置片段：Bash、ZSH、Fish、Elvish、Nushell、POSIX sh、PowerShell Core（不含补全）。

**不覆盖**：

- **Windows 原生**：官方安装路径是 WSL，不提供 Windows 原生主线支持。
- **依赖管理与依赖锁定**：它只管运行时版本，不管 `node_modules` / `pip` 包 / `Gemfile.lock`。
- **环境变量注入与自动切换**：进目录自动切换需要额外插件（如 direnv 那类）配合，asdf 本体不做。
- **图形界面**：纯 CLI。
- **系统级包管理**：不会替你装系统库；插件需要的系统依赖要自己装。
- **运行时构建环境**：不内嵌编译器，装需要编译的版本时要系统里已有对应工具链。

## 依赖条件

- 本体依赖 `git`；官方建议同时备好 `bash`。
- 需要 `bash` 的补全还要装 `bash-completion`（部分发行版）。
- 各插件有**自己的**系统依赖，装之前先看插件仓库列的清单（常见的有 `curl`、`gawk`、`gpg`、编译器、`dirmngr` 等）。
- `go install` 方式需要 Go；源码构建方式需要 `make`。
- 不需要账号、Key 或登录。
- 文档与命令以 <https://asdf-vm.com/manage/commands.html> 为准；本站快照对应版本号为 0.20.0，换版本后请以 `asdf --help` 实际输出为准。

## 已知限制

- **老命令已改**：`asdf global` / `asdf local` 在 0.16 之后不再是主线，改用 `asdf set`（`-u` 全局、`-p` 上级）；旧教程里的写法直接照抄会失败。
- **版本解析是隐式的**：`.tool-versions` 逐级向上查找这件事不出现在命令里，排查问题必须靠 `asdf current`。
- **未声明即报错**：某个工具在当前目录链路里没有版本，执行它会直接报错，而不是悄悄回落系统版本。
- **shim 不能 source**：包内需要 `source` 的脚本必须通过 `asdf which` / `asdf where` 拿真实路径。
- **安装耗时取决于插件**：有些插件是下载预编译包，有些要本地编译，慢是正常的。
- **插件质量参差**：插件由社区各自维护，行为、依赖、更新频率都不统一。
- **版本号会随上游漂移**：本文出现的 `v0.20.0` 是抓取时官方文档站显示的版本，不代表唯一的可用版本。

## 自检清单

执行前：

- [ ] `asdf version` 可用即说明装好了；`asdf info` 确认 OS / Shell / 数据目录。
- [ ] `type -a asdf` 只命中一份安装，且 shims 目录已在 `PATH` 里。
- [ ] 明确目标工具与版本；不确定就 `asdf list all <name>` 先看。
- [ ] 该插件的系统依赖是否齐了。
- [ ] 版本要写进哪个文件：当前目录、上级目录，还是 `$HOME`。

执行后：

- [ ] `asdf current` 显示的工具与版本符合预期，来源文件路径正确。
- [ ] `asdf which <命令>` 指向 asdf 管理的路径，而不是系统那份。
- [ ] 真正跑一下被管命令（如 `node -v`），确认版本号对得上。
- [ ] 需要重建 shim 时已 `asdf reshim`。
- [ ] 目标目录里生成的 `.tool-versions` 内容正确；要提交的话记得一起进 Git。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/asdf-vm/asdf | 上游仓库（安装与完整文档以它为准） |

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
