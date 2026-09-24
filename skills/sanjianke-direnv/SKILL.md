---
name: sanjianke-direnv
slug: sanjianke-direnv
displayName: 三剪客 · 目录级环境变量自动加载
description: "direnv 是 shell 扩展：按当前目录自动加载 / 卸载 .envrc 里的环境变量，进目录生效、出目录还原。含 hook 配置、所有子命令、stdlib 常用函数与安全机制避坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "direnv 的安装与 hook、allow/deny 安全机制、export/exec/status 调试命令、.envrc 里的 stdlib 函数（PATH_add / dotenv / layout / watch_file）以及 direnv.toml 配置项，附带 12 条高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · 目录级环境变量自动加载

每个项目都有自己的环境变量：数据库地址、API Key、PATH 里要加的 `bin` 目录、Python 虚拟环境。把这些写进 `~/.bashrc` 会越堆越乱，写进一堆 `source env.sh` 又会忘记执行。direnv 解决的就是这一件事——**进目录自动加载，出目录自动还原**，而且不用改你原来的 shell 配置。

它在你每次敲回车之前检查当前目录及各级父目录里有没有 `.envrc`，有就先交给你信任过的授权流程，再放进一个 bash 子进程里执行，只把"环境变量发生了哪些增减"回传到当前 shell。所以它支持 bash / zsh / fish / tcsh / elvish / pwsh / murex / nushell 等一票 shell，而且因为只回传 diff，退出目录时能精确地把你带进去的变量原样撤回。

**上游项目**：`direnv`　**仓库**：https://github.com/direnv/direnv

## 什么时候用 / 不用

**用它**：

- "我有好几个项目，每个项目的数据库连接串和 Key 都不一样，不想每次都 export 一遍。"——每个目录放一个 `.envrc`，`direnv allow` 一次，以后 `cd` 进去就生效。
- "这个仓库的 `bin/` 目录要加到 PATH 里，但我老写成 `export PATH=bin` 把 PATH 覆盖掉。"——`.envrc` 里写 `PATH_add bin`，它会前置而不是替换。
- "同事拉下代码后要手工 source 一堆环境脚本，总漏步骤。"——把环境初始化写成 `.envrc` 提交进仓库，作者只维护一份，别人 `direnv allow` 即可。
- "想让项目自动用独立的虚拟环境 / 独立 GEM_HOME / 独立 GOPATH。"——stdlib 有 `layout python`、`layout ruby`、`layout node`、`layout go` 等语义化布局函数。
- "改完 `Gemfile` 或某个配置文件后，希望环境自动重载。"——`.envrc` 里写 `watch_file Gemfile` 或 `watch_dir src`。
- "只是想在某个目录下临时跑一条命令，但要在完整环境里跑。"——`direnv exec DIR COMMAND`，不用先 `cd` 进去。

**不要用它**：

- **Windows 原生环境**——别把它当主力。官方文档的前置条件写的是 **Unix-like 操作系统（macOS、Linux 等）**；Windows 上通过 winget 装的也是它自带的实验性 hook，行为与 Unix 版有差异（比如 `layout` 系列函数依赖 bash 工具链，往往直接不可用）。Windows 上要用就在 **WSL** 里用。
- **"把密钥安全地藏起来"**——`.envrc` 是明文 bash 代码，写进去的 Key 就是明文躺在磁盘上。direnv 的授权机制防的是"别人塞给你的仓库偷偷执行代码"，**不是**防读取。密钥该用密钥管理器。
- **`.envrc` 里写复杂逻辑或长耗时任务**——它每次进入目录都会跑，每敲一次回车都可能触发。跑几十秒的脚本会让 shell 明显卡顿。重活应该留在 Makefile / 脚本里手动跑。
- **想让别名（alias）和 shell 函数跨过去**——direnv 是在独立 bash 子进程里执行 `.envrc` 的，只回传**环境变量的 diff**，所以 `.envrc` 里定义的 alias、function 都不会出现在你的交互 shell 里；用 fish 等非 bash shell 时连 stdlib 的可用函数范围也要打折。
- **只想读一个 `.env` 文件**——杀鸡用牛刀。如果需求只是"把一个 dotenv 文件读进环境"，`dotenv` 类工具或语言自带的加载器更直接；direnv 的价值在于"随目录自动切换"。

## 安装

安装分两步：先装二进制，再 hook 进 shell（只装不 hook 等于没装）。

### 第一步：装二进制

```bash
# macOS
brew install direnv

# Debian / Ubuntu
sudo apt update && sudo apt install direnv

# Fedora
sudo dnf install direnv

# Arch Linux
sudo pacman -S direnv

# openSUSE
sudo zypper install direnv
```

官方也提供 bash 安装脚本和各个 release 的预编译二进制：

```bash
# 官方安装脚本
curl -sfL https://direnv.net/install.sh | bash

# 或从 releases 页下载对应架构的二进制，然后
chmod +x direnv
mv direnv /usr/local/bin/     # 放到 PATH 里的任意位置
```

Windows 上官方文档指向 winget（按官方说明它属于受限/实验性支持，建议优先考虑 WSL）：

```powershell
winget install direnv.direnv
```

其他发行版（Gentoo、NetBSD、NixOS、MacPorts、GNU Guix 等）与最新打包状态见官方安装文档与打包状态页；具体包名以官方文档为准。

### 第二步：hook 进 shell

**把这一行加在配置文件的最末尾**，尤其要放在 rvm、git-prompt 之类会改写提示符的扩展**之后**：

```bash
# bash：加在 ~/.bashrc 末尾
eval "$(direnv hook bash)"

# zsh：加在 ~/.zshrc 末尾
eval "$(direnv hook zsh)"

# PowerShell：加在 $PROFILE 里
Invoke-Expression "$(direnv hook pwsh)"

# tcsh：加在 ~/.cshrc 末尾
eval `direnv hook tcsh`
```

fish、elvish、murex、nushell 的写法不同（fish 是 `direnv hook fish | source`，elvish 需要先生成到 `~/.config/elvish/lib/direnv.elv` 再 `use direnv`），以官方 hook 文档为准。改完配置文件**重启 shell**。

验证：

```bash
direnv version          # 打印版本
direnv status           # 打印当前目录的加载状态与配置文件位置
```

## 常用操作

下面每一条都能直接跑。假设项目目录是 `~/my-project`。

```bash
# 1) 最小闭环：建 .envrc → 被拦下 → 授权 → 变量生效 → 离开目录自动还原
mkdir -p ~/my-project && cd ~/my-project
echo 'export FOO=foo' > .envrc
#   此时 direnv 会提示 .envrc is not allowed
direnv allow .
echo ${FOO-nope}        # 输出 foo
cd ..                   # direnv: unloading
echo ${FOO-nope}        # 又变回 nope

# 2) 用 stdlib 函数写 PATH，而不是粗暴覆盖 PATH
cat > .envrc <<'EOF'
PATH_add bin                 # 前置 $PWD/bin，不破坏原 PATH
PATH_add node_modules/.bin
layout python3               # 在 .direnv/python-* 下建/用虚拟环境
dotenv_if_exists .env        # 有 .env 就加载，没有就跳过
watch_file requirements.txt  # 依赖文件变了就自动重载
EOF
direnv allow .

# 3) 授权状态管理
direnv status                # 看当前目录有没有 .envrc、是否已授权、走了哪些配置文件
direnv deny .                # 撤销授权（文件被改过之后 direnv 也会自动要求重新 allow）
direnv prune                 # 清掉 $XDG_DATA_HOME/direnv/allow 里已经过期的授权记录

# 4) 用 $EDITOR 改 .envrc，退出编辑器后自动重新授权 + 重载
direnv edit .

# 5) 不改当前目录，在指定目录的环境里执行命令
direnv exec ~/my-project python -c 'import os; print(os.environ.get("FOO"))'

# 6) 手动重载 / 看导出内容 / 看 stdlib
direnv reload                # 触发一次重载
direnv export bash           # 打印环境变量 diff（调试"为什么变量没生效"最有用）
direnv export json           # 同样的 diff，JSON 格式
direnv stdlib | head -n 40   # 打印 .envrc 可用的全部 stdlib 函数
```

`.envrc` 里最常用的 stdlib 函数（完整列表用 `direnv stdlib` 或看官方 stdlib 文档）：

| 函数 | 作用 |
|---|---|
| `PATH_add <path>` | 把展开后的路径**前置**到 PATH（不会覆盖） |
| `path_add <VAR> <path>` | 同上，但作用于任意变量名 |
| `PATH_rm <pattern>...` | 从 PATH 里按 shell 通配符删掉匹配项 |
| `dotenv` / `dotenv_if_exists [file]` | 加载 `.env`（后者文件不存在也不报错） |
| `source_env <file_or_dir>` | 加载另一个 `.envrc`（注意：不经过授权检查） |
| `source_up` / `source_up_if_exists` | 向上查找并加载父级 `.envrc` |
| `env_vars_required <VAR>...` | 变量缺失或为空时直接报错，常用于配合 `source_env` 校验密钥 |
| `layout <type>` | 语义化布局：`layout python3`、`layout node`、`layout ruby`、`layout go`、`layout php` 等 |
| `use <program>` | 语义化加载外部依赖：`use nix`、`use rbenv`、`use node`、`use guix` 等 |
| `watch_file <path>` / `watch_dir <dir>` | 把文件或目录（递归）加入监听，变了就重载 |
| `find_up <filename>` | 从当前目录向上找文件，输出路径 |
| `has <command>` | 命令是否存在（可当条件用） |
| `strict_env` / `unstrict_env` | 打开/关闭 `.envrc` 的 `set -euo pipefail` 严格模式 |
| `direnv_version <version>` | 校验本地 direnv 版本下限，方便共享 `.envrc` |
| `on_git_branch [branch]` | 判断当前是否在某个 git 分支上 |

### 配置 direnv 本身

配置文件在 `$XDG_CONFIG_HOME/direnv/direnv.toml`（通常 `~/.config/direnv/direnv.toml`），TOML 格式：

```toml
[global]
# 让 .envrc 以 set -euo pipefail 执行（官方说这将是未来的默认值）
strict_env = true
# 除了 .envrc，也自动加载 .env（两者都有时优先 .envrc）
load_dotenv = true
# 环境变量 diff 太吵时关掉打印
hide_env_diff = false
# 单条命令执行超过多久给个警告
warn_timeout = "5s"
# 明确指定 bash 路径，避免 PATH 被改坏后 direnv 找不到 bash
# bash_path = "/bin/bash"

[whitelist]
# ⚠️ 谨慎使用：命中前缀的目录会被隐式信任，任何人都能往里写文件即可执行代码
# prefix = ["~/code/project-a"]
```

个人扩展函数放在 `~/.config/direnv/direnvrc`，第三方扩展放 `~/.config/direnv/lib/*.sh`，它们都在每个 `.envrc` 之前被加载。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 装完 `direnv` 命令能用，但 `cd` 进目录毫无反应 | 只装了二进制，没做 shell hook | 在**配置文件末尾**加 `eval "$(direnv hook bash)"`（zsh 同理），然后重启 shell；`direnv hook <你的shell>` 的输出就是该加的代码 |
| 每次进目录都提示 `.envrc is not allowed` | 这是设计好的安全机制：新出现的 `.envrc` 一律视为不可信 | 确认内容可信后 `direnv allow .`；文件被改动后授权会失效，需要重新 allow，或改用 `direnv edit .` 让编辑器保存后自动授权 |
| `.envrc` 里写了 `FOO=bar`，但 shell 里没有 `FOO` | 只有**导出**的变量才会回传到当前 shell | 一律写 `export FOO=bar`，或者写 `dotenv` 加载 `.env`；用 `direnv export bash` 能看到实际回传了什么 |
| `.envrc` 里定义 alias / function 不生效 | `.envrc` 跑在独立 bash 子进程里，只回传环境变量的 diff，函数和别名不跨进程 | 环境相关的用变量表达；非环境逻辑写成项目脚本，需要时手工执行 |
| 变量 `unbound variable` 报错，脚本中途退出 | 开了 `strict_env`（或 `direnv.toml` 里 `strict_env = true`），引用未声明变量会直接退出 | 给变量加默认值 `${VAR:-}`，或用 `declare` 先声明；确实不需要严格模式就 `unstrict_env` 局部关掉 |
| 父目录也有 `.envrc`，加载结果和预期不一样 | direnv 会把当前目录到根路径上的 `.envrc` 依次生效，就近覆盖 | 用 `direnv status` 看清到底加载了哪些文件；需要显式继承时用 `source_up` / `source_up_if_exists` |
| `layout python` 报找不到相关命令 | 该布局依赖本机确实装了 virtualenv / python 工具链 | 先确认工具在 PATH 里；`layout python3` 只是 `layout python python3` 的简写，不会替你装解释器 |
| 进入目录顿一下再出现提示符 | `.envrc` 每次进入都执行，里面的命令太重（拉依赖、连网络、跑编译） | 把耗时操作移出 `.envrc`，只留环境变量设置；用 `watch_file` 精确控制重载时机，而不是放一坨一次性初始化 |
| 改了 `.envrc` 里 `export` 的值，变量还是旧值 | 没有触发重载 | `direnv reload`，或退出目录再进；`direnv status` 会显示该文件是否已加载 |
| `use nix` / `layout` 系列函数在 fish 里不可用 | 部分 stdlib 函数是 bash 实现，非 bash shell 下能力受限 | 环境脚本逻辑复杂的项目，建议把交互 shell 换成 bash/zsh，或把逻辑写成独立脚本再在 `.envrc` 里调用 |
| Windows 上 hook 装上了但 `.envrc` 里的命令大量报错 | 官方前置条件是 Unix-like 系统，Windows 属于受限/实验性支持，且 stdlib 的 `layout` 等依赖 Unix 工具链 | 换 WSL 使用；不要在 Windows 原生环境里依赖 direnv 做关键环境管理 |
| macOS 上终端里 direnv 命令找不到 | Homebrew 装在 `/opt/homebrew` 而当前 shell 的 PATH 没包含它 | 确认 PATH 里有 Homebrew 的 bin 目录；或在 `direnv.toml` 里显式设置 `bash_path` 避免 PATH 被改写后找不到 bash |
| 担心"拉个别人仓库就被执行代码" | 授权机制只挡没授权过的文件，`whitelist` 会绕过它 | **不要**随手配 `[whitelist] prefix`；确需配就限定到极窄的自有目录，清楚这意味着该目录下任何 `.envrc` 都会被无条件执行 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视情况 | 只有在 `.envrc` 主动调用 `fetchurl` / `source_url` / `use nix` 这类会联网的 stdlib 函数时才需要；direnv 主体不联网 |
| 读取文件 | 是 | 读取当前及各级父目录的 `.envrc` / `.env`、`direnv.toml`、`direnvrc`、`lib/*.sh`，以及 `PATH_add`、`source_env` 指向的文件 |
| 写入文件 | 是 | 向 `$XDG_DATA_HOME/direnv/` 写授权记录与缓存；`layout python` 会在项目下建 `.direnv/` 虚拟环境；`direnv edit` 会调起 `$EDITOR` 修改 `.envrc` |
| 凭证 | 否 | direnv 自身不需要账号、Token 或 API Key；但 `.envrc` 里可能**明文**存放数据库密码、云厂商 Key——这是明文文件，务必别提交进版本库 |
| 子进程 / 后台常驻 | 是 | 每次进入目录会启动一个 bash 子进程执行 `.envrc`；shell hook 常驻在你的交互 shell 里，无独立守护进程 |

## 触发场景

- "怎么让一个目录自动带上自己的环境变量？"
- "direnv 装好了但 cd 进去没反应。"
- "`.envrc is not allowed` 怎么解决？"
- "怎么把项目 bin 目录加到 PATH 又不覆盖原来的 PATH？"
- "怎么让项目自动用独立的 Python 虚拟环境？"
- "改了 `.envrc` 里面的变量，为什么还是旧值？"

## 能力边界

**覆盖**：

- 按目录自动加载 / 卸载环境变量，进入生效、离开还原，精确回传 diff
- `.envrc` 的授权与撤销（`allow` / `deny` / `edit` / `prune`），以及 `direnv.toml` 的 `[global]`、`[whitelist]` 配置
- 一整套 stdlib：PATH 操作、dotenv 加载、`.envrc` 互继（`source_env` / `source_up`）、语义化布局与依赖加载（`layout` / `use`）、文件监听重载（`watch_file` / `watch_dir`）、版本与前置条件校验
- 用 `direnv exec` 在别的目录环境里执行命令；用 `direnv export bash|json|...` 导出环境 diff；用 `direnv status` / `direnv reload` 排查与手动重载
- 通过 `~/.config/direnv/direnvrc` 和 `lib/*.sh` 定义自己的扩展函数

**不覆盖**：

- 不做密钥管理：没有加密、没有密钥托管，`.envrc` 是明文 bash 文件
- 不管理依赖本身：`layout python` 只是把虚拟环境建在项目下并切换过去，不负责装包；`use nix` 只是转发给对应工具
- 不提供跨 shell 的函数 / 别名导出（只回传环境变量）
- 不负责进程编排、容器、CI 执行——它只服务于你的交互 shell 与 `direnv exec` 那一次调用
- 不解释 `.envrc` 里的语法错误：它的报错来自 bash，需要自己看 bash 的提示
- Windows 原生支持受限且属实验性，不作为主力平台承诺

## 依赖条件

- **操作系统**：官方前置条件是 Unix-like（macOS、Linux 等）；Windows 属受限/实验性支持，建议改用 WSL
- **shell**：需要是它支持的其中一种（bash、zsh、fish、tcsh、elvish、pwsh、murex、nushell），并完成 hook
- **bash**：`.envrc` 在 bash 子进程里求值，所以系统里必须有可用的 bash；PATH 可能被改写导致找不到 bash 时，可在 `direnv.toml` 里设置 `bash_path` 固定它
- **可选的配套工具**：用 `layout python` 需要相应 Python 工具链；`layout ruby` / `use rbenv` 需要对应版本管理器；`use nix` / `use guix` 需要装 nix / guix；`on_git_branch` 需要 git
- **不需要账号、Key 或在线服务**——除你自己在 `.envrc` 里调用的联网函数外
- 配置文件位置：`$XDG_CONFIG_HOME/direnv/direnv.toml`，授权记录在 `$XDG_DATA_HOME/direnv/allow`

## 已知限制

1. **只回传环境变量**：alias、shell function、shell 选项不会跨过子进程边界。
2. **每次进入目录都执行**：`.envrc` 里放重活会拖慢提示符；这也是它只在进入/变更时执行的原因。
3. **明文存储**：`.envrc` 与 `.env` 中的密钥都是明文，授权机制防的是执行不防读取。
4. **授权粒度是文件级**：`.envrc` 内容一变授权即失效；跨机器、跨克隆目录都要各自 allow 一次。
5. **非 bash shell 下 stdlib 能力打折**：部分函数在 fish 等 shell 里行为不同或不可用。
6. **短暂窗口**：`cd` 后、direnv 求值完成前，环境变量还是"目录外"的那一套；脚本里判断环境不能假设瞬间生效。

## 自检清单

执行前：

- [ ] 已经装好**且** hook 进 shell 了吗（`direnv version` 与 `direnv hook bash` 都能正常输出）？
- [ ] 目标目录有 `.envrc` 吗？是否已 `direnv allow` 过（用 `direnv status` 确认）？
- [ ] `.envrc` 内容是否可信？来源不明的仓库里的 `.envrc` 一律先读再决定是否 allow。
- [ ] 操作系统是不是 Unix-like 或 WSL？Windows 原生下不要承诺可用性。
- [ ] `.envrc` 里有没有明文密钥？如果有，确认它不会被提交进版本库。

执行后：

- [ ] 用 `direnv export bash` 确认目标变量真的出现在 diff 里。
- [ ] 用 `direnv status` 确认加载的是预期的那个 `.envrc`，没有被父目录的同名文件覆盖。
- [ ] 若改了 `.envrc` 却没生效，`direnv reload` 或重新进出目录。
- [ ] 若进了目录却没反应，回头检查 hook 那一行是否在配置文件**末尾**、以及是否重启过 shell。
- [ ] 若脚本里依赖环境变量，先跑一次 `direnv exec <dir> <command>` 验证，再放进自动化。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/direnv/direnv | 上游仓库（安装与完整文档以它为准） |

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
