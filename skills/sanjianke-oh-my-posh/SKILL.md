---
name: sanjianke-oh-my-posh
slug: sanjianke-oh-my-posh
displayName: 三剪客 · 跨 Shell 提示符主题引擎
description: "oh-my-posh：跨 Shell 提示符主题引擎 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "oh-my-posh：跨 Shell 提示符主题引擎 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · 跨 Shell 提示符主题引擎

命令行提示符是每天看几百次的东西，但想让它显示 git 分支、语言版本、执行耗时、当前目录，往往要在每个 shell 里各写一份脚本。oh-my-posh 把提示符做成**一份配置 + 一条 init 命令**：同一个主题文件可以同时喂给 PowerShell、bash、zsh、fish 等多套 shell，换 shell 不用重写提示符。

它由两部分组成：一个二进制负责「渲染」，一段 `init` 生成的脚本负责「接到你的 shell 上」。绝大多数问题都出在后者——初始化位置、执行策略、字体、编码，而不是主题本身。

注意名字里的「posh」指的是 PowerShell 血统，但它早已不限于 PowerShell。

**上游项目**：`oh-my-posh`　**仓库**：https://github.com/JanDeDobbeleer/oh-my-posh

## 什么时候用 / 不用

**用它**：

- 「我想让终端提示符显示 git 分支、语言版本、上条命令耗时。」
- 「我现在这套提示符配置，能不能在 zsh 和 PowerShell 里都用同一份？」
- 「提示符里那些图标显示成方块了，怎么修？」
- 「有没有现成的主题可以挑，别让我从零写配置。」
- 「升级 Nerd Font 之后图标全变了，有没有迁移的办法？」

**不要用它**：

- **不想装字体**：它默认主题大量使用 Nerd Font 图标，没有对应字体就会看到方块。若你的环境不允许换字体，必须选极简主题或自己重写 `template`；这种条件下它不是一个「装上就好」的工具。
- 想要**彩色 `ls` / 别名 / 自动补全 / 给终端换整体外观**（配色方案、背景、透明度）：这些分别属于其它工具和终端模拟器自己的设置，它只管提示符。
- 提示符**越简单越好、追求启动最快**：它会为每段信息调用外部命令或读取状态，段越多提示符越慢；极简需求直接写原生 `PS1` 更轻。
- 在**受限执行策略 / 受限语言模式**的生产环境里：初始化脚本的执行会受限，需要额外的编码与策略处理。

## 安装

```bash
# ---- Windows ----
winget install JanDeDobbeleer.OhMyPosh --source winget
# 升级
winget upgrade JanDeDobbeleer.OhMyPosh --source winget

# ---- macOS ----
brew install jandedobbeleer/oh-my-posh/oh-my-posh
brew update && brew upgrade oh-my-posh

# ---- Linux：官方安装脚本 ----
# 需要 curl、unzip、realpath、dirname；装之前先更新 curl 与证书库
curl -s https://ohmyposh.dev/install.sh | bash -s
curl -s https://ohmyposh.dev/install.sh | bash -s -- -d ~/bin   # 指定安装目录
```

以上命令取自官方安装页。**Linux 各发行版仓库、与其它包管理器渠道的包名以官方安装页为准**（此处的权威入口是 <https://ohmyposh.dev/docs/installation>，不要照抄记忆里的包名）。

装完的第一件事是**装 Nerd Font**（否则主题里的图标显示不出来）：

```bash
oh-my-posh font install              # 交互式挑字体
```

## 常用操作

```bash
# 1) 先知道自己用的是哪个 shell
oh-my-posh get shell

# 2) 接到 shell 上：把这一行放到配置文件的最末尾
oh-my-posh init pwsh | Invoke-Expression        # PowerShell，写进 $PROFILE
eval "$(oh-my-posh init bash)"                  # bash，写进 ~/.bashrc
eval "$(oh-my-posh init zsh)"                   # zsh，写进 ~/.zshrc
oh-my-posh init fish | source                   # fish，写进 config.fish
# 其它 shell（cmd / nu / xonsh / elvish / yash 等）用官方给的对应写法

# 3) 换主题：--config 支持三种取值
oh-my-posh init pwsh --config 'C:/Users/me/myconfig.omp.json' | Invoke-Expression   # 本地文件
oh-my-posh init pwsh --config 'jandedobbeleer' | Invoke-Expression                  # 内置主题名
oh-my-posh init pwsh --config 'https://example.com/t.omp.json' | Invoke-Expression  # 远程 URL

# 4) 把主题落成本地文件再改
oh-my-posh config export --config jandedobbeleer --output ~/.mytheme.omp.json
oh-my-posh config export --config jandedobbeleer --output ~/.mytheme.omp.yaml   # 也可导出为 yaml / toml

# 5) 改完想立刻看到效果（默认配置是带缓存的）
oh-my-posh enable reload
oh-my-posh print preview                # 预览所有已配置的提示符
oh-my-posh print preview --force        # 忽略当前上下文，把所有段都渲染出来
oh-my-posh disable reload               # 关掉实时重载

# 6) 排错：看每段花了多少时间
oh-my-posh debug
oh-my-posh debug prompt                 # 只渲染一次提示符并输出调试信息

# 7) 字体与升级
oh-my-posh font install
oh-my-posh upgrade                      # 手动升到最新版
oh-my-posh enable upgrade               # 打开自动升级
oh-my-posh disable notice               # 关掉升级提示
```

几个常用开关：

| 需求 | 用法 |
|---|---|
| 包管理器升级后路径失效、shell 仍指向旧路径 | 初始化时加 `--strict`，改为经 `PATH` 解析：`eval "$(oh-my-posh init bash --strict)"` |
| 执行策略禁止运行未签名脚本 | 改用 `--eval` 让脚本被求值：`oh-my-posh init pwsh --eval \| Invoke-Expression`（初始化会变慢） |
| 想手动刷新提示符 | Fish / Zsh 用 `omp_repaint_prompt`；PowerShell 用 `Invoke-PoshPromptRepaint` |

`--config` 选内置主题名或远程 URL 时**每次开 shell 都要联网下载**（有缓存，但本地文件才是性能最优解）；官方也因此建议日常使用本地配置文件。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 提示符里是方块 / 问号，不是图标 | 当前字体不含所需的扩展字形，或终端没被配置成使用该字体 | `oh-my-posh font install` 装 Nerd Font，**并在终端设置里把字体改成它**；实在不能换字体就选带 `.minimal` 的极简主题 |
| 升级 Nerd Font 到 v3 后图标变成未知字符 | Nerd Font v3 把图标挪了位置 | `oh-my-posh config migrate glyphs --write` 迁移配置（会在同目录留一份 `.bak` 备份） |
| PowerShell 里提示符完全没生效 | `init` 那一行没加、没加在 `$PROFILE` 末尾被后续脚本覆盖，或执行策略禁止未签名脚本 | `notepad $PROFILE` 直接看，确认那一行在**最后**；profile 不存在就先 `New-Item -Path $PROFILE -Type File -Force`；策略问题设 `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine`、给 profile 签名，或改用 `--eval` |
| PowerShell 7.4 上渲染错乱，或用户名含非 ASCII 时提示找不到 `oh-my-posh.exe` | 该版本 / 该环境下 PowerShell 默认不是 UTF-8，路径被解错 | 初始化时把会话切到 UTF-8：`[Console]::OutputEncoding = [Text.Encoding]::UTF8`；更稳的写法是用 `try/finally` 临时切换再还原。官方提示对整个会话强制 UTF-8 可能有副作用，属临时绕过 |
| 看到「ConstrainedLanguage mode detected」告警 | PowerShell 处于受限语言模式，无法设置控制台编码 | 从系统层面把控制台设为 UTF-8；之后可在 `$PROFILE` 里设 `$env:POSH_CONSTRAINED_LANGUAGE = 1` 去掉告警 |
| 提示符在每条命令后明显卡顿 | 某个段在调用慢命令；Windows 上还常见于杀软实时扫描 | 用 `oh-my-posh debug` 看各段耗时；把可执行文件路径加入杀软排除；只涉及 git 仓库慢时可试 `git gc` |
| Windows Terminal 里段之间多出一个空格，或两段之间分隔符颜色对不上 | 终端对某些字形的宽度处理有已知问题；「调整难以区分的颜色」会自动改对比度 | 多出的空格：在图标后追加不可见字符（如 `\u2800`）或零宽字符（如 `\u200a`）。颜色对不上：把该项设为 `never`（`settings.json` 里 `"adjustIndistinguishableColors": "never"`）。两者都需要先把配置导成本地文件再改 |
| 升级后提示符整体崩坏 | 配置 schema 随大版本变化 | 先用 `oh-my-posh config validate` 校验，再用 `config migrate` 迁移；`config migrate` 会自行留 `.bak` 备份，但建议自己也留一份 |
| zsh 里 Ctrl+R 历史搜索失效，或报 `no such shell function 'zle-line-init'` | 裸 zsh 缺历史相关配置；或 `.zshrc` 里出现了两行 init | 前者在 `~/.zshrc` 里设 `HISTFILE`、`HISTSIZE`、`SAVEHIST` 并 `setopt appendhistory`；后者删掉多余的那一行 |
| Conda / venv 的环境名重复出现在提示符前 | 这些工具自己也会改写提示符 | Conda：在初始化 oh-my-posh **之前**执行 `conda config --set changeps1 False`；venv：设 `VIRTUAL_ENV_DISABLE_PROMPT=1` |
| 改了主题文件但提示符没变 | 配置默认被缓存以提升性能 | `oh-my-posh enable reload` 打开实时重载，或重开 shell |
| 开 shell 明显变慢 | `--config` 用了内置主题名或远程 URL，每次都要拉取；或包管理器升级后路径变了 | 换成指向本地文件的 `--config` 路径；路径失效时改用 `--strict` 经 `PATH` 解析，或在升级后重开 shell |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视情况 | `--config` 用内置主题名或远程 URL 时会下载配置；`font install` 下载字体；升级检查与 `upgrade` 会访问官方源 |
| 读取文件 | 是 | 读取主题/配置文件、`$PROFILE` 与 shell rc 文件、git 仓库状态、当前目录信息 |
| 写入文件 | 是 | `config export` 写主题文件、`config migrate` 就地改写配置（会留 `.bak`）、`font install` 写字体文件、初始化脚本会写入 shell 配置 |
| 凭证 | 否 | 不需要账号或 Key |
| 子进程 / 后台常驻 | 是 | 渲染提示符时会调用外部命令取值（git 等），PowerShell 下还会引导部分模块。它本身是短时进程，**不常驻**，但每次出提示符都会执行 |

## 触发场景

- 「我的终端提示符想显示 git 分支和命令耗时。」
- 「这套主题能不能 zsh 和 PowerShell 通用？」
- 「提示符里全是方块，怎么办？」
- 「有没有现成主题，我不想自己写配置。」
- 「提示符变得很卡，帮我找出慢在哪。」
- 「换字体后图标都变了，怎么修？」

## 能力边界

**覆盖**：

- 跨 shell 的统一提示符：初始化支持 bash、zsh、fish、PowerShell、cmd、nu、xonsh、elvish、yash 等（以官方安装页列出的为准）。
- 主题/配置文件：单个配置文件可被多个 shell 共用；`--config` 接受本地路径、内置主题名、远程 URL。
- 配置格式：JSON，且 `config export` 可导出为 yaml / toml（见官方配置文档）。
- 内置主题库与在线主题预览（不联网时只能手改本地文件）。
- 配置运维：`config export` / `config migrate` / `config validate` / `config edit` 等一整套子命令。
- 字体：`font install` 交互式安装 Nerd Font。
- 调试与预览：`debug` 看各段耗时，`print preview` 预览全部已配置提示符。
- 升级管理：`upgrade`、`enable upgrade`、`disable notice`、`enable notice`、`enable reload` / `disable reload`。
- 增强行为：`--strict`（经 PATH 解析）、`--eval`（受执行策略限制时的替代路径）。

**不覆盖**：

- **终端本身的配色与外观**：背景、透明度、配色方案属于终端模拟器。
- **彩色 `ls`、别名、自动补全、目录跳转**：那是别的工具的事。
- **字体以外的字体配置**：它只帮你装 Nerd Font，不替你在终端里选定字体。
- **图形界面**：本体是命令行；只有网站在线预览，没有本地 GUI。
- **shell 插件管理**：不管理 zsh / fish 的插件生态。
- **跨机器同步配置**：主题文件怎么分发由你自己决定（放 dotfiles 仓库是常见做法）。

## 依赖条件

- 需要联网安装（Windows 用 winget、macOS 用 Homebrew、Linux 用安装脚本）。
- Linux 安装脚本要求系统已有 `curl`、`unzip`、`realpath`、`dirname`，并建议先更新 `curl` 与证书库。
- 想正常显示图标需要 **Nerd Font**，且要**在终端里选定该字体**。
- 需要能修改 shell 的启动文件（`$PROFILE`、`~/.bashrc`、`~/.zshrc`、fish 的 `config.fish` 等）。
- PowerShell 场景下受本机执行策略约束。
- 不需要账号、Key 或登录。
- 命令与配置细节以 <https://ohmyposh.dev/docs> 为准；本文只写了能对上官方文档的部分，其余以 `oh-my-posh --help` 与各子命令 `--help` 的实际输出为准。

## 已知限制

- **字体是前置条件**，不是可选项：不想装 Nerd Font 就只能用极简主题或自定义模板。
- **提示符性能与段数量正相关**：每个段都可能调用外部命令，段越多越慢；官方建议用 `debug` 定位。
- **远程 / 主题名配置需联网**：每次开 shell 都要拉取（有缓存），因此官方推荐本地文件。
- **配置 schema 会随大版本变化**：升级后可能需要 `config migrate`，并保留 `.bak` 备份。
- **平台与终端差异明显**：Windows Terminal、JetBrains 终端、PowerShell 版本、受限语言模式各有已知问题。
- **`--eval` 是代价换兼容**：绕过执行策略限制，但会让 shell 初始化更慢。
- **同名工具的历史包袱**：名字里的「posh」容易让人以为只服务 PowerShell，实际覆盖多 shell。

## 自检清单

执行前：

- [ ] `oh-my-posh get shell` 确认当前 shell，别配错文件。
- [ ] 确认已装 Nerd Font，且**终端设置里已选中该字体**。
- [ ] 主题来源定了：本地文件（推荐）／内置主题名／远程 URL。
- [ ] PowerShell 用户先确认 `$PROFILE` 是否存在、执行策略是否允许运行脚本。
- [ ] 改配置前先备份，或用 `config export` 生成一份可控的本地副本。

执行后：

- [ ] 重开一个终端，提示符按预期渲染，图标不是方块。
- [ ] `init` 那一行确实在配置文件的**最后**。
- [ ] 耗时明显变慢时，用 `oh-my-posh debug` 找出是哪一段。
- [ ] 升级过字体或大版本的，已跑 `config migrate` 并确认 `.bak` 备份在。
- [ ] 配置改动生效（必要时 `enable reload` 或重开 shell）。
- [ ] 记录当前版本，便于之后排查配置兼容性。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/JanDeDobbeleer/oh-my-posh | 上游仓库（安装与完整文档以它为准） |

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
