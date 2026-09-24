---
name: sanjianke-zoxide
slug: sanjianke-zoxide
displayName: 三剪客 · 智能目录跳转
description: "zoxide：记住你去过的目录，之后用 z 加一两个关键词就跳过去，不用再一层层 cd 或者翻 history。支持 bash / zsh / fish / PowerShell / Nushell。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "zoxide 的安装与 shell 初始化、z 与 zi 的日常用法、query / add / remove / import 的数据库管理，以及 _ZO_EXCLUDE_DIRS、_ZO_MAXAGE 等配置项，还有 z 命令缺失、数据库不更新、目录搬家后跳错地方等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
  - 终端效率
  - Rust
---

# 三剪客 · 智能目录跳转

深度目录最烦的不是进不去，是每次都要重新输一遍：`cd ~/work/2026/client-a/service/api`。这条路径你一天可能敲五遍，而它其实只需要两个字——`api`。

`zoxide` 的做法是持续记录你去过哪些目录、去了多少次、最近一次是什么时候，然后按这个排名让你用关键词跳转。它不是把 `cd` 换掉，而是叠在 `cd` 之上：装一个二进制、在 shell 配置里加一行初始化、之后正常 `cd`，剩下的交给它自己学。

**上游项目**：`zoxide`　**仓库**：https://github.com/ajeetdsouza/zoxide

## 什么时候用 / 不用

**用它**：

- "那个项目的目录在哪儿来着，我记不住完整路径。"——`z 项目名` 直接跳过去，按访问排名选最可能的那个。
- "两个目录名字很像，跳错了。"——`z 项目 api` 用多个关键词收窄，或 `zi 项目` 进交互式挑选（需要装模糊选择器）。
- "我原来用别的跳转工具，有一堆历史记录，不想重新养。"——`zoxide import autojump`，官方支持从多种同类工具导入。
- "有些目录不想被记录（比如 `/tmp` 或挂载的网盘）。"——在初始化之前设置 `_ZO_EXCLUDE_DIRS`。
- "它学的那些目录我想看一眼，或者备份/清理一下。"——`zoxide query --list` 列出来，`zoxide remove <路径>` 删掉过期项。
- "想换个更短的命令名，避免和已有别名冲突。"——`zoxide init --cmd j` 把命令改成 `j` 和 `ji`。
- "目录搬家了也会记录，我想看结果。"——`zoxide add <新路径>` 手动补一条；`_ZO_RESOLVE_SYMLINKS=1` 让它在记录前先解析软链接。

**不要用它**：

- **在脚本、CI、`make` 这类非交互场景里指望它工作**——`z` 是 shell 初始化生成的**函数**，不是可执行文件，脚本里通常没有这个函数；脚本里要跳目录就用 `cd`。
- **想用它管理文件或查文件内容**——它只记目录路径，不管文件。
- **要跨机器/跨用户共享同一份跳转记录**——数据库是本地按用户存的，不适合当共享索引。不过 `zoxide import` 可以从同类工具的历史迁移过来。
- **没装模糊选择器却想用 `zi`**——`z` 不需要额外依赖，但交互式挑选需要模糊选择器（如 fzf），官方对它有最低版本要求。
- **把 `--cmd cd` 当成"更聪明的 cd"随手替换**——`zoxide init --cmd cd` 会直接顶掉 `cd`，习惯和已有脚本都可能被打乱，官方建议先在临时 shell 里试。
- **目录量大到指望它做精确检索**——它是基于访问频率与时间的排序（frecency），不是全文索引；要找明确路径还是用文件查找工具。

## 安装

各平台常见入口（Windows 上官方推荐 winget；Linux / WSL 官方推荐安装脚本）：

```bash
# Linux / WSL：官方安装脚本，默认装到 ~/.local/bin
curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | sh

# Debian / Ubuntu（universe 源）
sudo apt update && sudo apt install zoxide

# Arch
sudo pacman -S zoxide

# macOS
brew install zoxide

# Windows（winget 是官方推荐路径）
winget install ajeetdsouza.zoxide

# 有 Rust 工具链
cargo install zoxide --locked
```

装完必须做 shell 初始化，否则只有 `zoxide` 命令、没有 `z`：

```bash
# zsh（放在 ~/.zshrc，若启用补全则放在 compinit 之后）
eval "$(zoxide init zsh)"

# bash（放进 ~/.bashrc）
eval "$(zoxide init bash)"

# fish
zoxide init fish | source

# PowerShell（放进 $PROFILE）
Invoke-Expression (& { (zoxide init powershell | Out-String) })

# Nushell
zoxide init nushell | save -f ~/.zoxide.nu
```

初始化行建议放在 shell 配置的**靠后位置**，避免被后面的别名或插件覆盖。验证三步，缺哪一步补哪一步：

```bash
zoxide --version     # 二进制在不在 PATH
type z               # shell 函数有没有生成
zoxide query --list  # 数据库里有没有内容
```

## 常用操作

**1. 日常跳转**

```bash
z project                # 跳到排名最高的匹配目录
z client portal          # 多关键词收窄（匹配更精确的路径片段）
z ~/code/project         # 直接给路径时，行为和 cd 一致
z ..                     # 上一级
z -                      # 回到上一个目录
zi project               # 交互式挑选（需要模糊选择器）
```

**2. 查看它到底记了些什么**

```bash
zoxide query project             # 只打印最佳匹配路径，不跳转
zoxide query --list              # 列出全部记录
zoxide query --list --score      # 连同得分一起看
zoxide query --all               # 连已删除的目录也列出来
zoxide query --interactive       # 交互式选择（依赖模糊选择器）
```

**3. 增删记录**

```bash
zoxide add ~/code/project        # 手动添加（已存在则提升它的排名）
zoxide remove ~/code/old-project # 移除过期条目（先 query --list 确认）
```

**4. 从别的工具迁移历史**

```bash
zoxide import autojump
zoxide import z
zoxide import fasd
```

官方支持的来源包含 autojump、atuin、fasd、z、z.lua、zsh-z。迁移期间建议保留原工具和它的数据文件，确认导入结果符合预期后再处理。

**5. 配置项（在初始化之前设置）**

```bash
export _ZO_EXCLUDE_DIRS="$HOME/tmp:/mnt/network"   # 不记录的目录（分隔符按操作系统）
export _ZO_MAXAGE=10000                            # 数据库老化阈值
export _ZO_ECHO=1                                  # 跳转前先打印选中的目录
export _ZO_RESOLVE_SYMLINKS=1                      # 记录前解析软链接
export _ZO_FZF_OPTS="--height 40%"                 # 传给模糊选择器的参数

# 换命令名，避免和已有别名冲突
eval "$(zoxide init bash --cmd j)"                 # 之后用 j / ji
```

**6. 一次性检查与排错**

```bash
command -v zoxide        # 二进制在哪个路径
type -a zoxide           # 多个安装来源时看全部匹配
type z                   # z 是不是函数
zoxide query --list | wc -l   # 记录条数
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `zoxide: command not found` | 二进制没装成功，或安装目录不在 PATH 里 | 用官方脚本装的默认落在 `~/.local/bin`，cargo 装的在 `~/.cargo/bin`；把对应目录加到 PATH，并确保 export 行排在初始化行之前。`type -a zoxide` 能看出是不是有多个来源 |
| `z: command not found`（但 `zoxide --version` 正常） | 只装了二进制，没做 shell 初始化；`z` 是由初始化脚本生成的**函数** | 在对应 shell 的配置文件里加 `eval "$(zoxide init <shell>)"`（fish 用 `zoxide init fish \| source`），开新终端后再 `type z` 确认 |
| 初始化行加了但重启终端就没了 | 加到了错误的配置文件，或加在了会被后续配置覆盖的位置 | 确认当前 shell（`ps -p $$ -o comm=` 之类），写到它真正加载的那个文件里；初始化行放到靠后位置 |
| `z 关键词` 报 no match found | 数据库里没有这个目录的记录 | 先用 `cd` 完整路径进去一次让它学到，或 `zoxide add <绝对路径>`；用 `zoxide query --list` 确认是否已记录 |
| 明明以前跳过，现在跳不过去了 | 数据库有老化机制，久未访问的低分条目会被淘汰 | 重新访问一次，或 `zoxide add`；也可以调 `_ZO_MAXAGE` 改老化阈值 |
| 跳进了一个已经被删掉或重命名的目录 | 数据库只记路径字符串，不跟踪文件系统的变化 | `zoxide query --list --all` 把失效项找出来，然后 `zoxide remove <路径>`；要精确控制就 `cd` |
| `zi` 打不开选择器或直接报错 | `z` 不依赖额外组件，但 `zi` 需要模糊选择器，且有最低版本要求 | 先 `fzf --version` 对比官方要求的最低版本；发行版自带版本偏旧时，改用上游方式装新版本 |
| 同一台机器上 `apt` 装的和官方脚本装的都在 PATH 里，版本对不上 | 两个安装来源共存，PATH 顺序决定了实际调用哪个 | `type -a zoxide` 看全部匹配，选定一条升级路径，把另一份卸掉，然后开新 shell |
| 软链接目录跳转后落到了解析后的真实路径 | 默认记录的是你 `cd` 进去的那个路径；开启解析后行为不同 | 想让它先解析再用 `_ZO_RESOLVE_SYMLINKS=1`；反过来想要原样保留就别开 |
| `--cmd cd` 之后，习惯的 `cd` 行为变了 | `zoxide init --cmd cd` 直接用 zoxide 顶替了 `cd` | 官方建议先在临时 shell 里试；不确定就先保留默认命令名，或用 `--cmd j` 换个不冲突的名字 |
| 在脚本里 `z foo` 报 command not found | `z` 是交互式 shell 里的函数，非交互脚本环境不加载 | 脚本里老老实实用 `cd` 和绝对路径；需要的话在脚本里先执行一次 `eval "$(zoxide init bash)"`，但多数场景没必要这么做 |
| 设置 `_ZO_EXCLUDE_DIRS` 没生效 | 变量必须在**初始化之前**就已经存在，且不同操作系统的列表分隔符不一样 | 把 export 行写在初始化行之前；分隔符以官方文档为准（Unix 用 `:`，Windows 用 `;`） |
| 从别的工具迁移后，原工具的跳转行为被打乱 | `import` 只是读原工具的数据，但两个工具同时拦同一个命令名会互相干扰 | 迁移时保留原工具与其数据文件，确认新库正常后再考虑清理；不要同时让两个工具接管同一个命令名 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 安装时下载二进制或走包管理器需要联网；日常跳转完全本地，不发起网络请求 |
| 读取文件 | 是 | 读取本地目录数据库；`zoxide import` 会读取其它跳转工具的历史数据文件；`cd` 本身需要读目录 |
| 写入文件 | 是 | 每次访问目录都会更新本地数据库（这是它的核心机制）；`zoxide add` / `remove` / `import` 也会写库 |
| 凭证 | 否 | 不需要账号、token 或 API Key |
| 子进程 / 后台常驻 | 视情况 | `zoxide init` 由 shell 在启动时执行一次；`zi` 会启动模糊选择器子进程。zoxide 本身无常驻守护进程，数据库更新由 shell 钩子在 `cd` 时触发 |

## 触发场景

- "那个项目的目录我总记不住路径。"
- "不想每次 cd 都敲一长串。"
- "有几个项目目录名字很像，怎么快速切。"
- "怎么把我以前的跳转历史迁过来？"
- "这个目录怎么老是被跳到，能不能别记它。"
- "z 命令用不了，提示找不到。"
- "看看它都学了哪些目录。"

## 能力边界

**覆盖**：

- 跳转：`z <关键词...>`（按 frecency 排名选最佳匹配）、多关键词收窄、`z <路径>` 直跳、`z ..` / `z -`
- 交互式选择：`zi`（依赖模糊选择器），以及 `zoxide query --interactive`
- 数据库管理：`query`（`--list` / `--score` / `--all` / `--interactive`）、`add`（新增或提升排名）、`remove`（删条目）
- 历史迁移：`import` 支持 autojump、atuin、fasd、z、z.lua、zsh-z 等来源
- Shell 集成：`init` 支持 bash、zsh、fish、PowerShell、Nushell 等，可用 `--cmd` 自定义命令名前缀
- 环境变量调节：`_ZO_EXCLUDE_DIRS`、`_ZO_MAXAGE`、`_ZO_ECHO`、`_ZO_RESOLVE_SYMLINKS`、`_ZO_FZF_OPTS` 等
- 跨平台：Linux、macOS、Windows，以及 WSL、Android 等；官方提供各架构预编译包与安装脚本

**不覆盖**：

- 文件级操作与文件内容检索（只管目录）
- 全盘索引式搜索（它是访问历史排名，不是文件系统索引）
- 非交互脚本环境里的可用性（`z` 是 shell 函数）
- 运行时目录的校验：不会主动验证记录里的路径是否还存在
- 跨机器/跨用户的共享数据库
- 图形界面或目录树浏览（交互选择只是把候选列表交给选择器）

## 依赖条件

- 官方提供 Linux（含 musl 静态构建）、macOS、Windows 各架构的预编译包，以及官网/上游给出的安装脚本；走包管理器时版本以该仓库为准（先用 `zoxide --version` 确认）
- 从源码构建需要 Rust 工具链（`cargo install zoxide --locked`）
- 必须做一次 shell 初始化，且初始化行要加在**实际被加载**的 shell 配置文件里
- `zi` 及 `query --interactive` 需要一个模糊选择器（如 fzf），且版本要满足官方最低要求
- 不需要账号、Key 或网络服务；数据库按用户本地存放
- 各平台的 `_ZO_EXCLUDE_DIRS` 列表分隔符不同

## 已知限制

1. `z` / `zi` 是 shell 初始化生成的函数，不是可执行文件，脚本等非交互场景不可用。
2. 数据库有老化机制，久未访问的条目会被淘汰。
3. 不跟踪文件系统变化，目录被删或改名后记录可能指向失效路径。
4. `zi` 额外依赖模糊选择器，且对它有最低版本要求。
5. `--cmd cd` 会直接顶替 `cd`，影响面大，官方建议先在临时 shell 中试验。
6. 数据库不跨机器、不跨用户共享。
7. 具体环境变量与子命令行为以本机 `zoxide --help` 和上游文档为准。

## 自检清单

执行前：

- [ ] `zoxide --version` 通过——二进制在 PATH 里，这是所有后续步骤的前提
- [ ] `type z` 能看到函数——说明初始化行确实加载了，否则先补配置
- [ ] 确认当前用的是哪个 shell，初始化行写进了它真正加载的配置文件
- [ ] 需要交互选择就确认模糊选择器已安装且版本达标
- [ ] 打算改 `_ZO_EXCLUDE_DIRS` / `_ZO_MAXAGE` 等变量时，把 export 写在初始化行之前
- [ ] 迁移历史前先备份原工具的数据文件，别急着删

执行后：

- [ ] `zoxide query --list` 确认记录符合预期，没有把不该记的目录收进去
- [ ] 用 `z <关键词>` 跑一次端到端验证：跳到的确实是目标目录
- [ ] 改过 `--cmd` 之后，确认新命令名没有和已有别名冲突
- [ ] `type -a zoxide` 确认没有多个安装来源同时存在

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/ajeetdsouza/zoxide | 上游仓库（安装与完整文档以它为准） |

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
