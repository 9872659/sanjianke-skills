---
name: sanjianke-lf
slug: sanjianke-lf
displayName: 三剪客 · 终端文件管理器
description: "lf：终端文件管理器 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "lf：终端文件管理器 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文件管理
  - 转换
---

# 三剪客 · 终端文件管理器

`lf`（list files）是一个在终端里浏览和管理文件的工具：多栏布局、vi 风格按键、原生代码实现所以启动快、内存占用低，复制与移动是异步的、不会卡住界面。它还有服务端与客户端架构，可以用命令行远程控制正在运行的实例。适合 SSH 会话里挑文件、批量选择再复制移动，或者把「选择文件」这一步交给它、把结果喂给别的程序。

**上游项目**：`lf`　**仓库**：https://github.com/gokcehan/lf

## 什么时候用 / 不用

**用它**：

- 用户想要「在终端里浏览和管理文件」「不想离开键盘」。
- 在 SSH 或远程会话里挑文件、多选、复制、移动、重命名。
- 想把文件选择结果交给别的程序：`lf -print-selection` 当「打开文件」对话框，`lf -print-last-dir` 让 shell 跟随目录。
- 想用自己的脚本接管打开、预览、复制、删除动作（`cmd open`、`previewer`、`paste`、`delete` 都可覆盖）。
- 需要远程控制多个实例：`lf -remote` 的 send、query、list、quit。

**不要用它**：

- 要图形界面的文件管理器、拖拽或缩略图墙——这是终端界面。
- 想要内置的 pager 或编辑器——它刻意不内置，交给你的 `$EDITOR` 与 `$PAGER`。
- 需要多标签、多窗口——它刻意不做，交给终端复用器或窗口管理器。
- 想要一堆内置文件操作命令（`mkdir`、`touch`、`chmod`、`ln` 等）——这些交给底层 shell 工具。
- 只是想在脚本里列目录或判断文件类型——`ls`、`find` 更直接，`lf` 是给人用的界面。

## 安装

```bash
# 从源码构建（需要 Go），Unix
env CGO_ENABLED=0 go install -trimpath -ldflags="-s -w" github.com/gokcehan/lf@latest

# Windows cmd
set CGO_ENABLED=0
go install -trimpath -ldflags="-s -w" github.com/gokcehan/lf@latest

# Windows PowerShell
$env:CGO_ENABLED = '0'
go install -trimpath -ldflags="-s -w" github.com/gokcehan/lf@latest
```

预编译二进制在发行版页面；各平台社区维护的包清单在上游 wiki 的 Packages 页，包名以该页为准，拿不准就先在包管理器里搜 `lf`。装好后把 Go 的 bin 目录（`go env GOPATH` 下的 `bin`）加进 `PATH`。

装完先确认能跑：

```bash
lf -version
lf -help      # 命令行选项
lf -doc       # 完整文档，装好后可离线看
```

## 常用操作

```bash
# 1) 启动：不带参数从当前目录开始；给路径则进入该目录，给文件则选中它
lf
lf ~/projects
lf ~/projects/README.md

# 2) 当「选择文件」对话框用：选好后按 l 确认，退出时打印选中路径
lf -print-selection
lf -print-selection -selection-path /tmp/selected.txt

# 3) 让 shell 跟随 lf 的退出目录
cd "$(lf -print-last-dir)"

# 4) 用命令行参数临时改配置（可多次 -command，多条命令用 ; 连）
lf -command 'set nohidden' -command 'set hiddenfiles "*mp4:*pdf:*txt"' -print-selection
lf -command 'set sortby btime; set info btime' ~/Downloads
lf -config /dev/null -log /tmp/lf.log      # 用默认配置并记日志，便于排查

# 5) 远程控制正在运行的实例
lf -remote 'send $id quit'      # 给某个客户端发命令（$id 见 lf 导出的 id 变量）
lf -remote 'query $id maps'     # 查询某个实例的按键绑定
lf -remote 'list'               # 列出所有已连接实例的 ID
lf -remote 'quit!'              # 强制退出服务端
```

常用默认按键（不改配置就能用）：`j`/`k` 上下、`h`/`l` 进出目录、`y` 复制、`d` 剪切、`p` 粘贴、`c` 清空剪贴板、`r` 重命名、`v` 反选、`/` 搜索、`f` 查找、`t` 打标签、`m` 存书签、`:` 执行命令、`$` 执行 shell、`q` 退出；`zh` 切换隐藏文件、`zr` 反序、`ss` 按大小排序。

配置文件（Unix 在 `~/.config/lf/lfrc`，Windows 在 `%APPDATA%\lf\lfrc`）可以覆盖默认行为：

```bash
set shellopts '-eu'
set ifs "\n"
set scrolloff 10

# 自定义打开动作：文本走编辑器，其余走系统打开器
cmd open &{{
    set -f
    case $(file --mime-type -Lb "$f") in
        text/*) lf -remote "send $id \$$EDITOR \$fx";;
        *) for f in $fx; do $OPENER "$f" > /dev/null 2> /dev/null & done;;
    esac
}}

# 移到回收站，而不是直接删除
cmd trash %set -f; mv -t ~/.trash -- $fx
map <delete> trash
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 退出后 shell 还在原目录 | 进程退出时会回到启动目录 | 用 `cd "$(lf -print-last-dir)"`，或用仓库 `etc` 目录里的包装脚本 |
| 按删除键没反应 | 默认刻意不给 `delete` 绑键，保护新用户 | 自己写 `cmd delete ...` 再 `map <delete> delete`，或先绑定示例里的 trash 方案 |
| 复制后文件名多了 `~1~` 之类的后缀 | 内置复制移动不覆盖同名文件，按带编号备份的规则加后缀 | 这是设计行为；需要覆盖就自定义 `paste` 命令 |
| 粘贴后发现属主、权限、扩展属性丢了 | 内置实现只保留文件模式和部分时间戳 | 需要完整保留就自定义 `paste` 调 `cp -a`、`rsync` 之类 |
| 快速滚动时预览卡顿 | 每次选中变化都会调用预览脚本 | 打开 `preload` 预加载；预览脚本对大文件加 `|| true`，避免非零退出导致不缓存 |
| 配置文件改了没生效 | 配置路径不对或语法有错 | Unix 看 `~/.config/lf/lfrc`，Windows 看 `%APPDATA%\lf\lfrc`；也可用 `-config` 指定；用 `-log` 看报错 |
| 图标或颜色不显示 | 图标要显式打开且字体要支持；颜色受多级变量覆盖 | `set icons true`；颜色按 `LSCOLORS`、`LS_COLORS`、`LF_COLORS`、colors 文件的顺序排查 |
| shell 命令里文件名带空格或通配符出问题 | 变量是列表、分隔符是换行，但通配符展开仍会咬人 | 配置里 `set shellopts '-eu'`，命令里 `set -f`，变量一律加引号 |
| Windows 上默认配置报错 | 默认配置用的是 `cmd` 语法 | 用仓库 `etc/lfrc.ps1.example` 这份 PowerShell 兼容配置起步 |
| `-remote` 报连不上 | 客户端默认会自动起服务端，但 `-single` 起的实例没有服务端可连 | 去掉 `-single`，或先显式 `lf -server` 再连 |
| 全局配置与个人配置冲突 | 系统级在 `/etc/lf/lfrc`（Windows 在 `C:\ProgramData\lf\lfrc`），个人级优先 | 排查时先看个人配置文件，再确认系统级有没有额外绑定 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 本地终端界面；远程控制走本机服务端进程，不出网 |
| 读取文件 | 是 | 读取目录列表与文件元数据；预览会读取文件内容 |
| 写入文件 | 是 | 复制、移动、重命名、删除（删除需你自行绑定命令）；并写选择、书签、标签、历史等状态文件 |
| 凭证 | 否 | 不需要账号、Token 或 Key |
| 子进程 / 后台常驻 | 是 | 会为打开、预览、自定义命令启动子进程，并可能常驻一个服务端进程（客户端会自动拉起） |

## 触发场景

- 「终端里有没有类似 ranger 的文件管理器」
- 「帮我在服务器上批量选文件再拷到另一个目录」
- 「我想用键盘而不是鼠标管理文件」
- 「怎么把 lf 选中的文件路径传给编辑器打开」
- 「怎么让 lf 退出后 shell 还停在我刚浏览的目录」
- 「lf 里怎么删文件，为什么按删除键没反应」

## 能力边界

**覆盖**：

- 终端内的目录浏览与选择：多栏布局、vi 风格默认按键、可自定义映射。
- 文件操作：异步复制与移动（内置实现不覆盖同名文件）、重命名、标签、书签。
- 搜索与查找：text、glob、regex 三种匹配方式，以及增量搜索与查找跳转。
- 预览：可挂外部预览脚本，可开启预加载。
- 自定义钩子：打开、粘贴、重命名、删除、切换目录前后、目录加载、选中与退出等。
- shell 命令模板与导出的环境变量（当前文件、选中列表、宽高、模式等）。
- 服务端与客户端架构，以及远程命令（send、query、list、quit）。
- 跨平台支持：Linux、macOS、BSDs、Windows。
- 用 `-command` 在启动时执行配置命令。

**不覆盖**：

- 图形界面、拖拽、缩略图与图像渲染（预览能不能显示图取决于你挂的外部程序）。
- 内置编辑器与 pager。
- 标签页与多窗口（交给终端复用器或窗口管理器）。
- 内置的 `mkdir`、`touch`、`chmod`、`chown`、`ln` 等文件操作命令。
- 文件同步、网络传输协议、远端存储挂载。
- `lf` 自身的打包与分发（用发行版包或自行构建）。

## 依赖条件

- 一个可执行文件即可，运行时无外部依赖（Go 静态二进制）。
- 从源码构建需要 Go 工具链。
- 自定义能力依赖你环境里的工具：shell、`file`、编辑器、pager、预览脚本等。
- Windows 上的默认配置假设 `cmd`；用 PowerShell 需要换配置示例。
- 不需要网络、账号或 Key。

## 已知限制

- 必须在真实终端里使用；重定向输出或没有 TTY 的环境里没有实际意义。
- 内置复制移动不覆盖同名目标（加编号后缀），且只保留文件模式和部分时间戳。
- 默认不绑定删除键，删除能力要靠自定义命令补齐。
- 预览依赖外部脚本，慢或行为异常的程序会影响体验，必要时在脚本末尾加 `|| true`。
- 具体选项、默认值与命令行参数以 `lf -doc` 或 `lf -help` 的输出为准。

## 自检清单

执行前：

- 确认在真实终端里运行，而不是无 TTY 的管道或计划任务。
- 确认配置文件路径与语法正确，必要时用 `-log` 观察解析结果。
- 确认 `$EDITOR`、`$PAGER`、`$OPENER` 已经设置。
- 要做删除操作时，确认已经为 `delete` 绑定了安全实现（或先移入回收站）。

执行后：

- 选择结果场景下，确认打印出的路径清单符合预期。
- 确认复制、移动的目标确实存在，没有被加编号后缀而落在意外的位置。
- 确认没有残留的服务端进程：用 `lf -remote list` 查看，必要时 `lf -remote 'quit!'`。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/gokcehan/lf | 上游仓库（安装与完整文档以它为准） |

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
