---
name: sanjianke-gum
slug: sanjianke-gum
displayName: 三剪客 · Shell 脚本交互组件
description: "gum：Shell 脚本交互组件 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "gum：Shell 脚本交互组件 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · Shell 脚本交互组件

写 Shell 脚本最尴尬的一段，是「跟人要一个输入」：`read` 太素，想做个带多选、搜索、进度条的交互就得去写 Go 或者调 Python。gum 把一套终端交互组件做成**独立命令**，脚本里直接调用、把结果接进变量即可。

它的定位是「脚本的零件」而不是「应用框架」：`gum choose` 给一个选择列表，`gum input` 收一行字，`gum spin` 给长命令套个转圈，`gum style` 给提示加个框。你要做的只是把它们的标准输出接起来。

**上游项目**：`gum`　**仓库**：https://github.com/charmbracelet/gum

## 什么时候用 / 不用

**用它**：

- 「我想让脚本弹出菜单让我选分支 / 选会话 / 选文件，而不是手打名字。」
- 「要给长命令加个转圈和提示文字，别让脚本看起来卡死。」
- 「收一个密码或多行文本，别直接暴露在屏幕上。」
- 「写部署 / 安装脚本，中间要几个确认步骤」——`gum confirm` 直接给退出码。
- 「让交互提示好看点」——加边框、颜色、对齐，一行 `gum style` 就行。

**不要用它**：

- **非交互环境**（CI、cron、被管道驱动、stdout 不是终端）：交互组件需要键盘输入，在这类环境里会拿不到输入甚至挂住。要么跳过交互，要么设 `--timeout`，要么先判断有没有终端。
- 要写**功能完整的 TUI 应用**（多屏、状态机、自定义按键逻辑）：它是命令行零件，不适合当框架。
- 只是**单纯打印一段文本**：`echo` / `printf` 更直接，没必要为此装一个二进制。
- 需要**跨平台一致的终端表现**且终端很老旧：依赖 ANSI 转义与终端能力，老终端上样式会退化。
- 把它的输出**当作可解析的数据格式**：它是给人看的交互结果，不是稳定协议。

## 安装

```bash
# ---- 包管理器 ----
brew install gum                       # macOS / Linux
pacman -S gum                          # Arch
nix-env -iA nixpkgs.gum                # Nix
flox install gum                       # Flox
winget install charmbracelet.gum       # Windows
scoop install charm-gum                # Windows

# ---- Debian / Ubuntu：走官方 apt 源 ----
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg
echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list
sudo apt update && sudo apt install gum

# ---- Fedora / RHEL：走官方 yum 源 ----
echo '[charm]
name=Charm
baseurl=https://repo.charm.sh/yum/
enabled=1
gpgcheck=1
gpgkey=https://repo.charm.sh/yum/gpg.key' | sudo tee /etc/yum.repos.d/charm.repo
sudo yum install gum

# ---- 用 Go 装 ----
go install github.com/charmbracelet/gum@latest
```

上游 releases 页另有 Debian、RPM、Alpine 格式的包，以及 Linux / macOS / Windows / FreeBSD / OpenBSD / NetBSD 的预编译二进制，直接下载解包放进 `PATH` 也可以。

装完确认：

```bash
gum --version
gum --help           # 所有子命令
gum choose --help    # 单个子命令的完整参数
```

版本提示：gum 有 v1 与 v2 两条模块线，安装方式与包名可能不同；上面是 v1 的写法。若你的环境装到的是 v2，请以该版本 README 与 `--help` 为准。

## 常用操作

```bash
# 1) 单选：把结果接进变量
BRANCH=$(git branch --format='%(refname:short)' | gum choose --header "选分支")
echo "$BRANCH"

# 2) 输入：普通输入 / 密码 / 带回显初值
NAME=$(gum input --placeholder "你的名字")
PASS=$(gum input --password --placeholder "密码")
MSG=$(gum input --value "$TYPE$SCOPE: " --placeholder "改动摘要")

# 3) 多行文本（写完按 ctrl+d 结束），存文件
gum write --placeholder "详细说明" > details.txt

# 4) 模糊过滤：从候选里搜一条
FILE=$(ls | gum filter --placeholder "挑一个文件" --height 15)
EDITOR=$(cat flavors.txt | gum filter --limit 2)     # 多选

# 5) 确认：靠退出码判断，0 表示确认
gum confirm "确定要删除吗？" && rm file.txt || echo "已取消"

# 6) 转圈包住长命令。-- 之后的参数不会经过 shell 解析
gum spin --spinner dot --title "正在安装..." -- sleep 5
gum spin --title "构建中" --show-output -- sh -c 'make -j8 && echo done'

# 7) 样式与排版
gum style --foreground 212 --border double --border-foreground 212 \
          --align center --width 50 --margin "1 2" --padding "2 4" \
          '标题' '副标题'
gum style --faint "低对比度的一行说明"

# 8) 渲染内容：Markdown、代码高亮、模板、emoji
gum format -- "# 标题" "- 要点一" "- 要点二"
cat main.go | gum format -t code
echo 'Hello :heart: :candy:' | gum format -t emoji

# 9) 分页看长文本
gum pager < README.md

# 10) 表格：按分隔符读数据，选一行返回
gum table < flavors.csv
gum table --file users.csv --separator , --columns "ID,名字,邮箱" --print

# 11) 结构化日志
gum log --structured --level error "无法创建文件。" name file.txt
gum log --time rfc822 --level debug "开始处理"
```

**自定义有两条路**，可以叠加，命令行参数优先级高于环境变量：

```bash
# 参数
gum input --cursor.foreground "#FF0" --prompt.foreground "#0FF" \
          --placeholder "说点什么" --prompt "* " --width 80

# 环境变量，命名规则是 GUM_<子命令>_<参数>（大写、点变下划线）
export GUM_INPUT_CURSOR_FOREGROUND="#FF0"
export GUM_INPUT_PROMPT_FOREGROUND="#0FF"
export GUM_INPUT_PLACEHOLDER="说点什么"
export GUM_INPUT_PROMPT="* "
export GUM_INPUT_WIDTH=80
gum input
```

常用参数速记（完整清单见 `gum --help` 与 `gum <子命令> --help`）：

| 子命令 | 关键参数 |
|---|---|
| `choose` | `--limit`、`--no-limit`、`--ordered`、`--height`、`--header`、`--cursor`、`--cursor-prefix`、`--selected-prefix`、`--unselected-prefix`、`--selected`、`--select-if-one`、`--label-delimiter`、`--timeout` |
| `confirm` | 位置参数是提示语、`--affirmative`、`--negative`、`--default`、`--show-output`、`--timeout` |
| `input` | `--placeholder`、`--prompt`、`--value`、`--password`、`--char-limit`、`--width`、`--header`、`--cursor.mode`、`--timeout` |
| `write` | `--placeholder`、`--prompt`、`--value`、`--width`、`--height`、`--char-limit`、`--max-lines`、`--show-line-numbers`、`--timeout` |
| `filter` | `--placeholder`、`--indicator`、`--limit`、`--no-limit`、`--fuzzy`、`--fuzzy-sort`、`--reverse`、`--strict`、`--height`、`--value`、`--selected-prefix`、`--unselected-prefix` |
| `file` | 位置参数是起始目录、`--all`、`--cursor`、`--directory`、`--file`、`--permissions`、`--size`、`--height`、`--timeout` |
| `spin` | 位置参数是命令、`--spinner`、`--title`、`--align`、`--show-output`、`--show-stdout`、`--show-stderr`、`--show-error`、`--timeout` |
| `style` | `--foreground`、`--background`、`--border`、`--border-foreground`、`--align`、`--width`、`--height`、`--margin`、`--padding`、`--bold`、`--italic`、`--underline`、`--strikethrough`、`--faint`、`--trim` |
| `table` | `--file`、`--separator`、`--columns`、`--widths`、`--border`、`--print`、`--return-column`、`--fields-per-record`、`--lazy-quotes`、`--height`、`--timeout` |
| `format` | `--type`（`markdown` / `template` / `code` / `emoji`）、`--language`、`--theme` |
| `log` | `--level`、`--time`、`--prefix`、`--structured`、`--format`、`--formatter`、`--file`、`--min-level` |
| `join` | 位置参数是若干段文本、`--vertical`、`--horizontal`、`--align` |
| `pager` | 位置参数是内容、`--show-line-numbers`、`--soft-wrap`、`--border`、`--timeout` |

三种「按时间自动放行」的写法不同：`choose` / `confirm` / `filter` / `input` / `spin` / `table` / `pager` 都有 `--timeout`（例如 `--timeout 5s`），超时行为按子命令而定——`confirm` 若有 `--default` 会回落到默认项，其余多半是中止。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 在 CI / cron 里脚本卡死，或在管道里不响应 | 交互组件需要终端与键盘输入，非 TTY 环境拿不到 | 先判断是否有终端；不可交互时走非交互分支；或给 `--timeout 5s` |
| `gum spin --title "x" -- echo hi \| tee log` 报错 | `--` 之后的参数原样传给子进程，不经过 shell，管道符不会被当作管道 | 需要管道或变量展开时显式交给 shell：`gum spin --title "x" -- sh -c 'echo hi \| tee log'` |
| `gum spin` 跑完看不到命令的输出 | 默认不转发子命令输出 | 需要就加 `--show-output`（stdout+stderr），或只加 `--show-stdout` / `--show-stderr`；只关心失败时加 `--show-error` |
| `gum confirm` 后面那段没执行 / 判断反了 | 它不靠输出而是靠**退出码**：确认是 0、否定是 1 | 用 `&&` / `\|\|` 接后续动作；不要 `$(gum confirm ...)` 读字符串 |
| 用 `$(gum choose ...)` 接结果时命令被拆成两次执行，或文件名带空格导致打不开 | 命令替换按空白切词；路径未加引号会被拆成多个参数 | 结果整体加引号：`VAR="$(gum choose ...)"`、`"$EDITOR" "$(gum filter)"`；多选要按行读时配合 `--output-delimiter` 与 `while read` |
| 表格选完返回整行，取某一列很麻烦 | 默认返回整行字符串 | 用 `--return-column N` 指定列号，或对输出再 `cut` |
| 设置的环境变量没生效 | 参数名到环境变量的映射有规则，且命令行参数会覆盖环境变量 | 规则是 `GUM_<子命令>_<参数>`（大写、`.` 换 `_`）；先确认没被命令行参数覆盖，再用 `gum <子命令> --help` 核对真实参数名 |
| 颜色 / 边框在日志里变成乱码 | 输出被重定向或经管道时终端能力探测失效，转义序列原样落进文件 | 交互在终端里做，落到文件的内容用 `--strip-ansi` 之类的开关或自己剥掉转义 |
| 管道喂进去的列表整体被当成一项 | stdin 的候选分隔符不是换行 | 用 `--input-delimiter` 指定分隔符；输出侧对应 `--output-delimiter` |
| `--fuzzy` 没开时搜不到 | 默认是从词首匹配，不是模糊匹配 | 需要模糊匹配就加 `--fuzzy`；要按匹配分数排序再加 `--fuzzy-sort` |
| `gum style` 多行文本换行错乱 | 参数里的换行在不同 shell 中处理方式不同 | 复杂内容走 stdin 或把 `gum style` 的结果整体加引号再传给 `gum join` |
| `--limit` 设了却还是能选中超出数量 | 多选与单选是两套行为，`--no-limit` 会忽略 `--limit` | 明确是单选（`--limit 1`，默认）还是多选；`--selected` 可预设初始选中项 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 运行期不联网；只有你自己用包管理器安装时才下载 |
| 读取文件 | 是 | `gum file` 遍历目录、`gum table --file` 读数据文件、`gum pager` 读待分页内容 |
| 写入文件 | 视情况 | 本体不写盘；输出重定向到文件、`gum log --file` 写日志由你决定 |
| 凭证 | 否 | 不需要账号或 Key；`gum input --password` 只是把输入遮住，不做任何加密或存储 |
| 子进程 / 后台常驻 | 是 | `gum spin` 会以子进程方式运行你给的命令；其余子命令是短时进程，不常驻 |

## 触发场景

- 「写个脚本让我选分支，别让我手打。」
- 「给这段长命令加个进度提示。」
- 「让我在列表里搜一下再选。」
- 「脚本里要输密码，别显示出来。」
- 「怎么在脚本里弹个确认框？」
- 「终端里那行带框的提示是怎么做的？」

## 能力边界

**覆盖**：

- 交互取值：`choose`（单选/多选/排序/预设选中）、`confirm`（退出码语义）、`input`（普通/密码/初值/字符上限）、`write`（多行，含行号与最大行数）、`file`（文件树选择，可选显示权限与大小）、`filter`（模糊搜索、多选、反向、严格模式）、`table`（CSV 式数据选行，可指定列名与列宽）。
- 反馈与包装：`spin`（转圈，可转发子命令输出）、`pager`（分页，行号与软换行）。
- 输出美化：`style`（颜色、边框、对齐、宽高、内外边距、粗体/斜体/下划线/删除线/淡色）、`join`（横竖拼接）、`format`（Markdown、代码高亮、模板、emoji 四类）。
- 日志：`log`，含级别、时间格式、前缀、结构化输出与日志格式化器。
- 两条自定义途径：命令行参数，以及 `GUM_<子命令>_<参数>` 形式的环境变量（参数覆盖环境变量）。
- 超时：多数交互子命令支持 `--timeout`。
- 查询：`--help` / `--version`，以及版本约束检查子命令。

**不覆盖**：

- **非交互场景**：没有终端就没有交互，不会自动降级成默认值（`confirm --default` 是少数例外，且要配合超时）。
- **TUI 应用框架**：不做多屏、不做自定义按键状态机，不是写应用的底座。
- **数据格式契约**：输出是给人看的结果，不是稳定的机器接口。
- **图形界面**：纯终端。
- **终端能力兜底**：老终端或能力受限的环境下，颜色、边框、图标会退化。
- **加密与安全存储**：`--password` 只负责输入阶段不回显。

## 依赖条件

- 需要**交互式终端**（TTY）。这是最重要的一条。
- 各平台有包管理器渠道或预编译二进制；用 Go 安装需要 Go 环境。
- 不需要账号、Key 或登录。
- 本文参数名取自官方命令参考页（该页对应版本标注为 2026-09-11）；gum 存在 v1 与 v2 两条模块线，安装方式与参数可能随版本变化，用时以 `gum <子命令> --help` 实际输出为准。

## 已知限制

- **必须有终端**：这是所有交互子命令的前置条件，CI 与自动化里要显式分流。
- **退出码承载语义**：`confirm` 的结论在退出码里而不是输出里，写脚本时容易搞反。
- **命令替换会切词**：`$(gum ...)` 的结果按空白拆分，含空格或多选的返回值必须加引号或改分隔符。
- **`--` 之后不走 shell**：`spin` 包的复杂命令要显式交给 `sh -c`。
- **参数面很宽且随版本增删**：`--help` 是唯一可靠依据，不要照抄记忆里的参数名。
- **样式依赖终端能力**：同一段脚本在能力不同的终端、或输出被重定向时表现不一致。
- **版本线并存**：v1 / v2 的模块路径与安装方式不同，脚本里引用命令前先确认装的是哪条线。

## 自检清单

执行前：

- [ ] `gum --version` 确认已安装，并确认是 v1 还是 v2 那条线。
- [ ] 判断当前是否有交互终端；没有就走非交互分支。
- [ ] 明确要单值还是多值：单值直接 `VAR="$(gum ...)"`，多值要想好分隔符与读取方式。
- [ ] 参数名先 `gum <子命令> --help` 核对，不凭印象写。
- [ ] 交互步骤是否需要超时兜底。

执行后：

- [ ] 交互结果的引号与分隔符处理正确，路径含空格也能用。
- [ ] `confirm` 的逻辑靠退出码判断，没有误用输出。
- [ ] `spin` 包的输出按需要 `--show-output` / `--show-error` 转发。
- [ ] 落到文件或日志里的内容不含残留的 ANSI 转义序列。
- [ ] 在真实用户终端里手工跑一遍，确认样式与按键符合预期。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/charmbracelet/gum | 上游仓库（安装与完整文档以它为准） |

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
