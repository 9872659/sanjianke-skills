---
name: sanjianke-fastfetch
slug: sanjianke-fastfetch
displayName: 三剪客 · 终端系统信息速览
description: "fastfetch：终端系统信息速览 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "fastfetch：终端系统信息速览 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · 终端系统信息速览

`neofetch` 停更之后想给自己机器拍一张「配置身份证」，fastfetch 是目前最常见的选择。它主要用 C 写，主打快，一次性把系统、内核、桌面环境、CPU、GPU、内存、磁盘、网络这些信息连同发行版图标打在一屏里。

对 Agent 来说它最实用的两个面：一是**给人看**的默认输出，二是 `--structure` 挑模块和 `--format json` 出机器可读结果——后者可以直接接进后续处理，比截图靠谱。

**上游项目**：`fastfetch`　**仓库**：https://github.com/fastfetch-cli/fastfetch

## 什么时候用 / 不用

**用它**：

- 「帮我看下这台机器的配置」，要一眼能读、还带发行版图标的那种输出；想要 neofetch 的观感但它已停更时，也是它。
- 「把这台机器的硬件信息导出来，我要存成文件或接后续脚本」——用 `--format json`。
- 「只打印内存和 CPU，别的都不要」——`--structure` 可以精确挑模块、定顺序。
- 「每次开终端都自动打一遍」——写进 shell 启动文件，或生成配置文件固定下来。
- 「在 CI 里记录跑测机器的环境」——一条命令拿到结构化机器信息，比截图靠谱。

**不要用它**：

- 需要**实时、持续的性能监控**：它是「打印一次就退出」的静态快照工具，不是 `top` / `htop` 那类监视器。虽然支持 `--watch` 反复刷新，但那是重绘整屏，不是采样曲线。
- 要**采集指标做长期趋势**：没有时序库、没有告警，自己 `--format json` 存起来才是正路。
- 想用它**查硬件是否故障或做压测**：它只读系统已有的信息源，不做诊断、不做压力测试。
- 环境**没有 TTY 又要彩色对齐输出**：非终端输出会自动降级（可用 `--pipe` 显式关色），图标和对齐在日志里通常很难看。
- 依赖内核模块或受限权限才能拿到的字段（某些传感器、部分 GPU 信息）：取不到就是取不到——这类需求请换专门的硬件检测工具。

## 安装

Windows 与 macOS 的命令已核对到官方渠道；Linux 各发行版的包名以发行版仓库和上游 README 为准，不要照抄记忆里的名字。

```bash
# ---- Windows ----
winget install -e --id Fastfetch-cli.Fastfetch
# 另有 Scoop / Chocolatey 渠道，具体包名以上游 README 为准

# ---- macOS / Linux ----
brew install fastfetch                 # Homebrew，macOS 与 Linux 都可用

# ---- Linux 发行版仓库 ----
# 主流发行版的官方仓库大多已有此包；包名与安装命令以上游 README 为准，
# 常见形式如 apt / dnf / pacman 各自 install fastfetch

# ---- Nix ----
nix-env -iA nixpkgs.fastfetch          # 具体属性名以 nixpkgs 实际为准

# ---- 预编译二进制 ----
# 上游 releases 页提供各系统/架构的压缩包，解出来放进 $PATH 即可

# ---- 从源码构建（需要 CMake 与 C 工具链）----
git clone https://github.com/fastfetch-cli/fastfetch
cd fastfetch && cmake -B build && cmake --build build
```

装完确认：

```bash
fastfetch --version          # 完整版本信息
fastfetch --version-raw      # 只要 major.minor.patch
fastfetch --list-features    # 这个构建编进了哪些能力（编译期开关决定）
```

Windows 官方要求 Windows 7 或更新；在 WSL 里跑要走 Linux 那套装法。

## 常用操作

```bash
# 1) 默认输出：系统 + 图标一屏
fastfetch

# 2) 挑模块、定顺序。结构是冒号分隔的模块名
fastfetch --structure title:os:kernel:uptime:memory
fastfetch --list-modules                 # 有哪些模块名可用（这是权威清单）
fastfetch --print-structure              # 看默认结构长什么样
fastfetch --structure-disabled disk      # 在现有结构里关掉某几个模块

# 3) 换图标
fastfetch --logo arch                    # 内置图标名，或图片文件路径
fastfetch --logo none                    # 干脆不要图标
fastfetch --list-logos                   # 有哪些内置图标
fastfetch --logo-type kitty --logo /path/to/pic.png   # 指定渲染方式
fastfetch --logo-width 30 --logo-height 15            # 图片图标的字符尺寸

# 4) 机器可读输出（接脚本用这个）
fastfetch --format json
fastfetch -j                             # --json 是 --format json 的快捷写法

# 5) 生成 / 使用配置文件
fastfetch --gen-config                   # 生成到 ~/.config/fastfetch/config.jsonc
fastfetch --gen-config -                # 打印到标准输出而不是写文件
fastfetch <一串选项> --gen-config         # 把这次用到的选项固化成配置文件
fastfetch --config neofetch              # 载入内置预设
fastfetch --list-presets                 # 有哪些预设
fastfetch --list-config-paths            # 配置文件会从哪些位置找
fastfetch --list-data-paths              # 预设与图标从哪些位置找

# 6) 改样式：颜色、分隔符、键宽
fastfetch --color-keys blue --color-title red
fastfetch --separator ": "
fastfetch --key-width 12
fastfetch --pipe                         # 关掉颜色，适合贴进日志

# 7) 常用排错开关
fastfetch -h logo-type                   # 查某个选项的详细说明（去掉前面的横线）
fastfetch --stat                         # 每个模块各花了多少毫秒
fastfetch --show-errors                  # 出问题时把错误打出来
fastfetch --dynamic-interval 2000        # 每 2 秒重绘一次，常驻
fastfetch -w 5                           # 同上，单位是秒
```

配置文件是 **JSONC**（允许注释），扩展名必须是 `.jsonc`。默认路径 `~/.config/fastfetch/config.jsonc`。想要编辑器补全，在文件开头加 `$schema` 指向上游的 `doc/json_schema.json`。最小可用示例：

```jsonc
// ~/.config/fastfetch/config.jsonc
{
  "logo": { "type": "auto", "source": "arch" },
  "display": {
    "separator": ": ",
    "color": { "keys": "blue", "title": "red" },
    "key": { "width": 12 }
  },
  "modules": [
    "title", "separator", "os", "kernel", "uptime",
    { "type": "memory", "format": "{used}/{total} ({used_percent}%)" }
  ]
}
```

注意：选项解析**不区分大小写**，`--logo-type` 与 `--LOGO-TYPE` 等价；方括号里的参数是可选的，布尔类选项写了不带值就等于 `true`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 图标不对、或者干脆没图标 | `--logo` 给的名字不是内置图标名，也没走文件路径 | `fastfetch --list-logos` 核对名字；用图片就配 `--logo-type file` 之类并给路径 |
| 图片图标只显示一角 / 被拉伸 | 没给字符尺寸，或终端协议的宽高要求没满足 | 配 `--logo-width` / `--logo-height`；iTerm 协议下这两项是必需的 |
| 输出到文件或管道后满屏乱码颜色 | 默认按 `isatty` 自动判断是否上色，重定向时行为不符预期 | 显式加 `--pipe` 关色；需要结构化就直接 `--format json` |
| `--structure` 里写了模块但没输出 | 模块名拼错，或该模块在当前平台/权限下取不到值 | `fastfetch --list-modules` 抄准确名字；再看 `--show-errors` 有没有报错 |
| `--watch` / `--dynamic-interval` 出错 | 这两个选项与 `--json` 不兼容 | 监控用彩色输出，采集用一次性 `--json`，别混用 |
| 生成配置文件时卡住不动 | `--gen-config` 在终端里会进交互式界面 | 非交互场景把 stdout 重定向、或设 `$NO_COLOR` 让它走非交互生成；也可以 `--gen-config -` 直接打印 |
| 配置文件改了没生效 | 文件没放在搜索路径里，或扩展名不是 `.jsonc` | `fastfetch --list-config-paths` 看搜索顺序；用 `--config` 显式指定 |
| 某些硬件信息取不到（温度、部分 GPU） | 依赖系统数据源、内核模块或驱动 | 属正常能力边界；确认 `--list-features` 里该能力已编译进来，再核对系统侧是否提供数据 |
| 同一份 JSON 解析脚本换机器就报错 | JSON 结构会随版本变化 | 采集脚本里记录 `--version-raw`，解析时对缺失字段做兜底 |
| 换机器后图标/字段差异很大 | 不同平台支持的模块和数据源不同 | 跨平台脚本别硬编码字段；先 `--list-modules` 探测 |
| 在 CI 里输出巨大且难读 | 默认结构是给人看的 | 用 `--structure` 裁到几个关键模块，或 `--format json` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视情况 | 默认本地采集不联网；`--thread` 涉及 HTTP 请求、以及某些需要联网取数据的模块才用到 |
| 读取文件 | 是 | 读取配置文件、预设、图标图片；读取系统信息源（`/proc`、`/sys`、系统 API 等） |
| 写入文件 | 是 | 仅在你主动 `--gen-config` 时写入配置文件；默认运行不写盘 |
| 凭证 | 否 | 不需要账号或 Key |
| 子进程 / 后台常驻 | 视情况 | 部分模块会调用系统命令取值；`--watch` / `--dynamic-interval` 会让它持续运行不退出 |

## 触发场景

- 「看下这台机器的配置。」
- 「只给我内存和 CPU 的信息。」
- 「把系统信息导成 JSON，我要写进脚本。」
- 「终端里那个带图标的系统信息怎么装的？」
- 「怎么让每次开终端都自动显示一遍？」
- 「neofetch 不能用了，有没有替代？」

## 能力边界

**覆盖**：

- 一次性系统信息速览：系统与内核、桌面环境、CPU/GPU、内存、磁盘、网络、终端与 shell、主题字体等（可用模块见 `--list-modules`）。
- 用 `--structure` / `--structure-disabled` 精确控制显示哪些模块及其顺序。
- 图标：内置图标名、图片文件，以及多种渲染方式（`--logo-type`，含 kitty / iTerm / sixel / chafa 等，具体支持取决于编译进来的能力，用 `--list-features` 确认）。
- 机器可读输出：`--format json` / `-j`。
- 配置体系：JSONC 配置文件、`$schema` 编辑器补全、`--gen-config` 把当前选项固化成配置、内置预设。
- 显示细节：颜色、分隔符、键宽、百分比样式与进度条字符、大小与温度的单位与小数位等（选项很多，见 `-h`）。
- 常驻重绘：`--watch`（秒）/ `--dynamic-interval`（毫秒）。
- 排错辅助：`--stat` 看各模块耗时，`--show-errors` 打印错误，`--list-*` 系列查询路径与可用项。
- 平台：Linux、Android、FreeBSD、macOS、Windows 7 或更新。

**不覆盖**：

- **持续监控与告警**：不做采样、不做历史、不做阈值告警。
- **硬件诊断与压测**：只读系统已有信息，不测好坏。
- **图形界面**：纯命令行。
- **跨版本稳定的数据契约**：JSON 结构随版本演进，不承诺字段长期不变。
- **数据源本身不提供的字段**：内核未暴露或权限不足的信息取不到。
- **安装系统依赖**：只负责显示，不替你装驱动或内核模块。

## 依赖条件

- 各平台都有官方包或预编译二进制；Windows 需 Windows 7 或更新。
- 从源码构建需要 CMake 与 C 工具链。
- 部分能力是**编译期决定**的（如图片渲染相关的后端），用 `fastfetch --list-features` 确认当前构建支持什么。
- 配置需要是可读的 `.jsonc` 文件。
- 不需要账号、Key 或登录。
- 本文选项名、配置路径与结构语法取自官方文档页（对应版本号为 2.68.1）；版本不同时以 `fastfetch -h` 实际输出为准。

## 已知限制

- **快照工具**：默认跑一次就退出，`--watch` 是整屏重绘，不适合当作实时监视器。
- **`--json` 与刷新选项互斥**：`--dynamic-interval` 不能与 `--json` 同时用。
- **JSON 结构会变**：跨版本的解析脚本必须自己兜底缺失字段。
- **能力因构建而异**：同一份配置代码在不同平台/不同构建上取到的模块可能不同。
- **非 TTY 环境自动降级**：重定向或管道下颜色被关，图标与对齐通常不美观。
- **部分硬件字段依赖系统侧**：驱动、内核模块或权限不到位时取不到值，这是数据源限制而非工具缺陷。
- **选项数量庞大**：不同版本的选项会增删，脚本里用到较新选项时应在启动时做一次能力探测。

## 自检清单

执行前：

- [ ] `fastfetch --version` 确认可用；`--list-features` 确认所需能力已编入。
- [ ] 明确要展示还是采集：展示用默认/`--structure`，采集用 `--format json`。
- [ ] 模块名从 `--list-modules` 抄，不凭印象拼。
- [ ] 要写盘才用 `--gen-config`，其余情况避免意外生成文件。

执行后：

- [ ] 退出码为 0，输出非空。
- [ ] `--structure` 里列出的模块都真的出现了；缺的用 `--show-errors` 查原因。
- [ ] JSON 输出能被解析器正常解析，缺失字段有兜底。
- [ ] 重定向/管道场景已显式处理颜色（`--pipe` 或 `--format json`）。
- [ ] 需要长期复用时，把这次用到的选项用 `--gen-config` 固化下来。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/fastfetch-cli/fastfetch | 上游仓库（安装与完整文档以它为准） |

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
