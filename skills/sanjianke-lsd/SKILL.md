---
name: sanjianke-lsd
slug: sanjianke-lsd
displayName: 三剪客 · 现代化 ls 替代品
description: "lsd：现代化 ls 替代品 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "lsd：现代化 ls 替代品 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · 现代化 ls 替代品

在终端里看目录，`ls` 只给你一列名字；想知道哪个是目录、哪个最近改过、这个仓库里哪些文件有未提交改动，得再敲一两条命令。这个工具把这几件事合成一条：彩色、带图标、支持树形展开、`-l` 长格式里能直接列出 git 状态。

它适合「人眼看目录」这个场景——日常翻项目、确认文件在哪、看目录结构。装完通常再配一句 `alias ls='lsd'`，就把原来的 `ls` 顶掉了。

**上游项目**：`lsd`　**仓库**：https://github.com/lsd-rs/lsd

## 什么时候用 / 不用

**用它**：

- 用户说「帮我看一下这个目录里有什么」「这个项目的目录结构是怎样的」，需要人眼友好的输出。
- 想在长格式列表里顺便看到每个文件的 git 状态（新增/修改/未跟踪），而不是先 `ls` 再 `git status` 两趟。
- 要快速摸清一个陌生仓库的层级：`--tree --depth` 比手动 `find` 更直观。
- 想按大小、时间、扩展名、版本号排序，或者按 glob 排除掉 `node_modules`、`dist` 这类噪声目录。
- 终端已经装了 Nerd Font，希望文件名前面有类型图标，一眼区分语言和文件种类。

**不要用它**：

- 要在脚本里解析目录列表：它的输出带颜色、图标和宽度对齐，格式会随终端宽度变化，是给人看的，不是给程序读的。
- 需要 GNU `ls` 那些它没实现的参数（例如 `--quoting-style`、`--format=commas`、`--time-style=full-iso` 等）：别指望它全兼容，遇到不认识的参数它会直接报错。
- 服务器或 CI 里没有配 patched 字体：图标会显示成方块或问号，这时候不如直接用 `--icon never`，甚至就别装。
- 要递归扫描超大目录树做统计：`--tree` / `-R` 会把结果全渲染出来，量级上去以后很慢，这种活该交给专门的遍历工具。
- 要按 `.gitignore` 规则过滤：它不读 `.gitignore`，被忽略的文件照样列出来。

## 安装

各发行版与包管理器的命令如下（安装矩阵以官方文档为准：https://github.com/lsd-rs/lsd#installation）。

```bash
# macOS / Linuxbrew
brew install lsd
sudo port install lsd          # MacPorts

# Windows
scoop install lsd
winget install --id lsd-rs.lsd
choco install lsd

# Linux 发行版
sudo pacman -S lsd             # Arch
dnf install lsd                # Fedora
sudo zypper install lsd        # openSUSE
sudo xbps-install lsd          # Void
apt install lsd                # Debian sid / bookworm、Ubuntu 23.04 及以后
apk add lsd                    # Alpine

# 从源码装（需要 Rust 工具链）
cargo install lsd
cargo install --git https://github.com/lsd-rs/lsd.git --branch main

# 确认装上了
lsd --version
lsd --help
```

旧的 Debian / Ubuntu 版本已经不再提供 snap 包，改用发行页里的预编译二进制，或上面的 `cargo install` 路径。

可选但强烈建议：装一个 Nerd Font 并在终端里选中它，否则图标显示不出来。

```bash
# 图标是否可用，先跑这一句验证
echo $'\uf115'          # 能打印出文件夹图标才算配好
```

## 常用操作

```bash
# 1) 最常用：长格式 + 隐藏文件 + 人类可读大小
lsd -la

# 2) 树形看结构，并用 --depth 限制层数（别直接对根目录裸跑 --tree）
lsd --tree --depth 2
lsd --tree --depth 3 ./src

# 3) 长格式里直接带 git 状态列（目录的状态是内部文件状态的汇总）
lsd -l --git

# 4) 按大小 / 时间 / 扩展名排序，或反序
lsd -lS                      # 按大小
lsd -lt                      # 按修改时间
lsd -lX                      # 按扩展名
lsd -lSr                     # 按大小反序

# 5) 排除噪声目录（可重复指定多个 glob），并按目录优先分组
lsd -l --group-dirs=first \
  --ignore-glob 'node_modules' \
  --ignore-glob 'target' \
  --ignore-glob '.git'

# 6) 控制显示什么：图标、颜色、日期格式、权限写法
lsd --icon never --color never            # 纯净输出，给不支持图标的终端用
lsd -l --date relative                    # 相对时间（如 "2 hours ago"）
lsd -l --permission octal                 # 权限用八进制显示
lsd -l --total-size                       # 目录显示总大小（会递归统计，慢）

# 7) 自定义配置：只对本次生效，用来试配置
lsd --config-file ./my-config.yaml
lsd --ignore-config                       # 完全忽略已有配置，排查配置问题时用
```

想彻底替代 `ls`，在 shell 配置里加别名：

```bash
alias ls='lsd'
alias l='lsd -l'
alias la='lsd -a'
alias lla='lsd -la'
alias lt='lsd --tree'
```

配置放在固定位置，按需创建 `config.yaml`、`colors.yaml`、`icons.yaml` 三个文件中的任意一个即可，不必三个都建：

- Unix：`$HOME/.config/lsd/` 或 `$XDG_CONFIG_HOME/lsd`
- Windows：优先 `%USERPROFILE%\.config\lsd`，其次 `%APPDATA%\lsd`

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 文件名前面显示成方块、问号或乱码 | 当前终端字体不含 Nerd Font 的那些字形 | 装 patched 字体并在终端里选中；先跑 `echo $'\uf115'` 验证；实在不想折腾就用 `--icon never` |
| 每个文件名前面第一个字符被吃掉 | 少部分终端模拟器对双宽图标的渲染有已知问题 | 换终端（Alacritty、Kitty 之类），或临时 `lsd --icon never --ignore-config` 规避 |
| 配置改了完全不生效 | 配置文件放错位置了，或环境变量指向了别处 | 用 `--config-file <文件路径>` 显式指定（注意它收的是文件路径，不是目录）来验证；再用 `lsd --help` 确认 `XDG_CONFIG_HOME` 当前取值 |
| Windows 上自定义配色没有效果 | 自定义配色依赖 `LS_COLORS` 这个环境变量，缺了它就退回默认 | 在 Windows 里显式设置 `LS_COLORS` 后再启动终端 |
| 在 Debian 12 以下装 .deb 报 `unknown compression for member 'control.tar.zst'` | 旧系统的 dpkg 不认 zstd 压缩 | 改用发行页里带 `_xz` 后缀的包，或者用 `cargo install` 从源码装 |
| 脚本里 `ls -l \| awk ...` 换成 `lsd` 之后全乱了 | 输出带颜色、图标、宽度对齐，是终端排版而不是稳定的机器格式 | 解析用途不要换；必须换时至少加 `--icon never --color never -1`，但仍不建议用于解析 |
| 对仓库根目录跑 `--tree` 卡住很久 | 递归渲染整个目录树，含 `.git`、依赖目录在内全部展开 | 加 `--depth` 限制层数，并用 `--ignore-glob` 排除大目录 |
| `lsd -l` 显示目录大小是 4096 之类的小数字 | 默认显示的是目录项自身的大小，不是内容总和 | 需要真实总大小加 `--total-size`，但它会递归统计，大目录上会更慢 |
| 隐藏文件没显示 | 和 `ls` 一样，点开头的条目默认不列 | 加 `-a`；只想排除 `.` 和 `..` 用 `-A` |
| `lsd --tree -L 2` 报参数错误 | `-L` 在这里是「跟随符号链接」的意思，不是限定层数 | 限制层数用 `--depth 2` |
| 输出里出现 `�` 替换字符 | 文件名里本身含有非法 UTF-8 字节 | 这是文件名的问题，不是显示问题；用 `lsd --icon never` 或换文件管理方式确认原始字节 |
| 图标看起来「错位」或指向别的类型 | 图标字体的版本与当前图标集不匹配 | 换成用较新版本 Nerd Fonts 打过补丁的字体；`--icon-theme unicode` 可退回 emoji 风格 |
| 找不到「只列目录」的短选项 | 这里对应的是 `-d/--directory-only`，语义与 `ls -d` 接近但不是一回事 | 用 `lsd -d`；与 `--tree` 同用时它会递归地只显示目录本身 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 纯本地文件系统操作，不联网 |
| 读取文件 | 是 | 读取目录内容与文件元数据（大小、权限、时间、符号链接目标）；`--git` 还会读仓库状态，`--total-size` 会递归统计大小 |
| 写入文件 | 否 | 只读工具，不修改被列出的文件；仅在生成 shell 补全脚本时会向 `SHELL_COMPLETIONS_DIR` 或 `OUT_DIR` 写文件 |
| 凭证 | 否 | 不需要任何账号或 Key |
| 子进程 / 后台常驻 | 否 | 一次性进程，不驻留、不开端口 |

## 触发场景

- 「看看这个目录里有什么」
- 「这个项目的目录结构大概是什么样，展开两层就行」
- 「哪些文件改过还没提交？」
- 「按文件大小排一下，看看哪个占地方」
- 「ls 输出太丑了，有没有彩色带图标的」
- 「把 node_modules 和 .git 排除掉再列出来」

## 能力边界

**覆盖**：

- 目录列举：颜色、图标、长格式、单列、递归、树形与深度限制。
- 排序与过滤：按名字/大小/时间/扩展名/版本号/git 排序，glob 排除，目录优先分组。
- 展示细节：权限（rwx / 八进制 / 属性）、大小（默认 / short / bytes / 目录总计）、时间（date / locale / relative / 自定义格式）、inode、符号链接目标、git 状态。
- 外观定制：`config.yaml` / `colors.yaml` / `icons.yaml` 三份可选配置，按名称/扩展名/文件类型覆盖图标。
- 环境联动：读 `LS_COLORS` 决定配色，按 XDG 规范定位配置目录。

**不覆盖**：

- 不遵守 `.gitignore`：被忽略的文件默认照样列出来。
- 不替代 `find` / `fd`：不做条件查找、不做批量文件操作，也不输出结构化数据。
- 不提供稳定的机器可读输出（无 JSON / CSV 输出格式）。
- 不兼容 GNU `ls` 的全部参数，遇到不认识的参数直接报错而不是忽略。
- 不修改文件，不做删除、移动、权限变更。

## 依赖条件

- 预编译二进制：无需额外运行时，直接可用。
- 从源码安装：需要可用的 Rust 工具链与 Cargo。
- 显示图标：需要安装 Nerd Font（或 font-awesome 一类）并让终端使用它；纯文字场景可关掉图标。
- Windows 上要自定义配色：需要 `LS_COLORS` 环境变量。
- 不需要账号、不需要 Key、不需要网络（`--git` 也只读本地仓库状态）。

## 已知限制

- 图标显示依赖终端字体，字体没配好时观感比 `ls` 更差。
- 少数终端模拟器存在图标首字符被裁剪的问题，只能换终端或关图标。
- `--total-size` 需要递归统计，在超大目录上会明显变慢。
- 输出面向人眼，列宽随终端变化，不适合当脚本的输入。
- 不读 `.gitignore`，需要手动用 `--ignore-glob` 一个个排除。

## 自检清单

执行前：

- [ ] 确认端口场景是「人眼看目录」，而不是脚本要解析输出；后者不要用这个工具。
- [ ] 确认当前终端是否配了 patched 字体；没配就加 `--icon never`，别让用户看到一堆方块。
- [ ] 对目录树做递归/树形输出时，先想好 `--depth` 和 `--ignore-glob`，避免把 `.git`、依赖目录全渲染出来。
- [ ] 如果用户已有配置文件，改动前先用 `--ignore-config` 或 `--config-file` 验证差异。

执行后：

- [ ] 输出是否符合人眼阅读习惯（颜色、图标、对齐），而不是被重定向后丢掉样式。
- [ ] 递归或总计大小的操作耗时是否可以接受，是否需要提示用户这是慢操作。
- [ ] 没有对文件做任何写操作（本工具只读）。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/lsd-rs/lsd | 上游仓库（安装与完整文档以它为准） |
| https://github.com/lsd-rs/lsd/tree/master/doc/samples | 官方提供的 `config.yaml` / `colors.yaml` / `icons.yaml` 样例 |

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
