---
name: sanjianke-hyperfine
slug: sanjianke-hyperfine
displayName: 三剪客 · hyperfine 命令行基准测试
description: "{desc}。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "{summary}。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
  - 性能测试
---

# 三剪客 · hyperfine 命令行基准测试

"这个写法是不是更快一点？"——这种问题用手表掐、用 `time` 看单次结果，都不可信：单次测量被磁盘缓存、CPU 调频和系统噪声左右，差个 20% 都可能只是抖动。想要一个能拿出去说服人的数字，得**同一条命令跑很多轮、给出均值和标准差、并识别离群值**。

hyperfine 干的就是这件事。它把"跑多轮 + 统计 + 对比 + 导出"做成一条命令，还支持把参数当变量做扫描（比如线程数 1 到 8 各跑一轮），以及多个候选命令并排比较。定位很收敛：**它只负责测，不负责优化**。

**上游项目**：`hyperfine`　**仓库**：https://github.com/sharkdp/hyperfine

## 什么时候用 / 不用

**用它**：

- "这两个实现哪个快？给我一个带误差范围的结论。"——一条命令给多个候选，输出 mean / 标准差 / min / max 对比表。
- "`make -j1` 到 `-j8` 分别是多久？"——`-P` 参数扫描或 `-L` 参数列表，自动把每个取值跑一遍并列表对比。
- "编译前需要清缓存、跑之前需要 setup。"——`--prepare` 每次计时前执行、`--cleanup` 整组结束执行一次，把准备动作和计时隔开。
- "结果要进文档或 CI 报告。"——直接导出 markdown / json / csv / asciidoc / org-mode。
- "我不想让被测命令的输出刷屏。"——默认输出被丢弃（`null`），需要看的时候再 `--show-output`。

**不要用它**：

- **要测的是服务端吞吐、并发响应时间**——hyperfine 测的是"命令跑完要多久"，不是压测工具。要看 QPS、p95 这类指标得用负载测试工具。
- **要测浏览器渲染、页面性能**——不在范围内，那是前端性能工具的事。
- **要 profile 性能热点**——hyperfine 只告诉你"慢了多少"，不告诉你"慢在哪"。要定位热点用 profiler。
- **想拿绝对值横向比较不同机器**——测量结果强依赖本机 CPU、磁盘、缓存状态与系统负载，跨机器、跨负载的绝对数字没有可比性。
- **单次就想要答案、且不在乎抖动**——直接 `time` 更快；hyperfine 的价值在多轮统计，跑轮数本身要花时间。

## 安装

Homebrew（macOS / Linux）：

```bash
brew install hyperfine
```

各 Linux 发行版与包管理器都有打包，**包名以你自己的包管理器为准**（Debian / Ubuntu 侧源码包名为 `rust-hyperfine`，二进制包名是 `hyperfine`）：

```bash
# 用你自己的包管理器安装 hyperfine 这个包，例如：
# Debian/Ubuntu、Fedora、Arch、Alpine、openSUSE 等主流发行版均已收录
sudo <你的包管理器> install hyperfine
```

其他常见渠道：MacPorts、nix、Chocolatey（Windows）、Scoop（Windows）都有对应包。官方 Releases 页也提供各平台预编译二进制。

装完确认：

```bash
hyperfine --version
hyperfine --help
```

各发行版打包版本可能落后于上游；`--ignore-failure`、`--conclude` 这类参数在不同版本的文档里写法不一致，**一律以本机 `hyperfine --help` 的输出为准**。

## 常用操作

**1. 最基础的一次基准测试**

```bash
hyperfine 'find . -name todo.txt'
```

它会做一次 shell 探测（首次运行会有额外开销），然后按默认轮数跑并给出统计结果。

**2. 多命令对比 + 设定轮数与预热**

```bash
hyperfine --warmup 3 'grep -R FIXME *'
hyperfine --min-runs 5 'sleep 0.2' 'sleep 3.2'
```

`--warmup 3` 表示正式计时前先空跑 3 次（把缓存预热掉），`--min-runs` 控制最少跑多少轮；`--max-runs` 可设上限（默认无上限）。

**3. 给每条命令起名字，避免长命令把表格撑乱**

```bash
hyperfine -n 'with cache' 'cmd --cache' -n 'without cache' 'cmd --no-cache'
```

`--command-name` 可以多次指定，按顺序对应各个命令。

**4. 参数扫描：同一个命令跑一组参数**

```bash
hyperfine -P threads 1 8 'make -j {threads}'
hyperfine -P size 0 3 'sleep $((2**{size}))'
hyperfine -P delay 0.3 0.7 -D 0.2 'sleep {delay}'
```

`-P/--parameter-scan <变量> <最小值> <最大值>`，`-D/--parameter-step-size` 用来改步长（必须配合 `-P`）。**每个参数值都会各跑完整一轮测试**，参数多的时候总耗时按倍数增长，先用大的步长试跑。

**5. 参数列表：枚举离散取值**

```bash
hyperfine -L compiler gcc,clang '{compiler} -O2 main.cpp'
```

`-L/--parameter-list` 接受逗号分隔的固定取值，可以重复指定来做组合。

**6. 准备与清理：把 setup 动作排除在计时之外**

```bash
hyperfine -r 2 --show-output \
  --setup 'echo setup n={n}' \
  --prepare 'echo prepare={n}' \
  --conclude 'echo conclude={n}' \
  --cleanup 'echo cleanup n={n}' \
  'echo command n={n}'
```

四条钩子的语义不同，别混用：

- `--setup`（短名 `-s`）：**每组命令计时开始前**执行一次
- `--prepare`（短名 `-p`）：**每次计时运行前**都执行
- `--conclude`：每次计时运行后执行
- `--cleanup`（短名 `-c`）：**整组命令的全部运行结束后**执行一次

**7. 导出结果**

```bash
hyperfine --export-markdown output.md --parameter-scan time 1 5 'sleep {time}'
hyperfine --export-json result.json 'cmd-a' 'cmd-b'
hyperfine --export-csv result.csv 'cmd-a' 'cmd-b'
```

还支持 `--export-asciidoc` 与 `--export-orgmode`。JSON 里同时包含汇总统计与逐次运行的耗时，**CSV 只有汇总且单位固定为秒**。

**8. 绕过 shell 直接执行（消除 shell 启动开销）**

```bash
hyperfine -N 'my-binary --flag'
hyperfine --shell=none 'my-binary --flag'
```

`-N` 就是 `--shell=none` 的别名，等价于短名 `-S/--shell` 传 `none`。

**9. 容忍被测命令的非零退出码**

```bash
hyperfine -i 'grep -q needle file' 'grep -q other file'
```

默认被测命令返回非零会让这次测量失败；`--ignore-failure` 用来忽略。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 写 `-s bash` 想换 shell，结果被当成 setup 命令 | **短名映射和直觉相反**：`-s` 是 `--setup`，`--shell` 的短名是 `-S` | 换 shell 写 `-S bash` 或 `--shell bash`；明确不要 shell 用 `-N`（`--shell=none` 的别名） |
| 测出来的耗时比预期偏快，尤其是 `grep` 这类会检测输出的命令 | `--output` 默认是 `null`（重定向到 `/dev/null`），被测程序检测到 stdout 不是终端后会启用优化分支，测到的不是你真实使用时的路径 | 需要真实输出行为时加 `--output=pipe`；`--output=inherit` 等价于 `--show-output` |
| 加了 `--show-output` 后结果变慢 | 打印输出本身要耗时，`--show-output` 只适合调试或专门测"输出速度"的场景 | 正式测量时不要开；需要真实输出路径又不想打印到终端，用 `--output=pipe` |
| 第一次运行特别慢，后续正常 | 首次会做 shell 探测等一次性开销 | 用 `--warmup`（官方例子常用 3 次）把首轮开销排除掉 |
| 跑完发现表格里的命令名长得看不懂 / 列错乱 | 直接用了完整命令当标签 | 用 `-n/--command-name` 给每条命令起短名字 |
| `-D` 单独使用报错 | 步长参数必须和 `-P` 参数扫描搭配 | 同时给出 `-P` 与 `-D`；枚举离散值改用 `-L` |
| 参数扫描跑得极慢，一条命令等了很久 | 每个参数取值都各跑一整轮完整测试，耗时是"轮数 × 取值个数"级别 | 先用大步长 / 大跨度粗扫定位范围，再对候选区间细扫；配合 `-m/--min-runs` 控制最小轮数 |
| 清理逻辑只跑了一次，没在每次运行后执行 | `--cleanup` 的语义是**整组结束后一次**，不是每次运行后 | 每次运行后要执行的动作改用 `--conclude` |
| 结果看起来卡死了，什么都不输出 | `--style none` 会关掉全部输出 | 去掉 `--style none`；`--style` 的值有 auto / basic / full / nocolor / color / none |
| markdown / asciidoc 导出表的顺序和我给命令的顺序不一致 | `--sort auto` 时，标记类导出表按输入顺序排；`--sort command` / `--sort mean-time` 会重排 | 想固定顺序就保持默认的 `auto`；要按速度排就用 `--sort mean-time` 并接受表格顺序变化 |
| 两个版本文档在 `-C/--conclude`、`-i/--ignore-failure[=MODE]` 上写法不一致 | 不同打包版本对应的文档内容有差异 | 以本机 `hyperfine --help` 为准；`--ignore-failure` 在部分版本支持传退出码列表（如 `--ignore-failure=1,2`）之类的带值形式 |
| 被测命令因为返回非零被判成失败 | 默认不容忍非零退出码 | 确实要忽略就加 `-i/--ignore-failure`；否则先修命令，别把失败当正常结果比快慢 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | hyperfine 自身不联网；只有被测命令本身访问网络时才产生流量 |
| 读取文件 | 是 | 读取被测命令触及的文件（那是被测程序的行为）；hyperfine 自身读取命令行参数 |
| 写入文件 | 是 | `--export-*` 写导出文件；`--output <文件>` 把被测命令输出重定向到文件 |
| 凭证 | 否 | 不需要账号或 API Key |
| 子进程 / 后台常驻 | 是 | 核心机制就是反复 fork 执行被测命令并计时；进程一次性执行完退出，无常驻服务。注意**被测命令会真实执行**，带副作用的命令（删文件、发请求、写库）会真的产生效果 |

## 触发场景

- "这两个写法哪个更快？"
- "帮我基准测试一下这条命令。"
- "多跑几轮，给我均值和误差。"
- "线程数从 1 到 8 分别测一下。"
- "这次优化到底快了多少？"
- "把结果导出成表格 / JSON 放进报告。"
- "怎么让被测命令的输出别刷屏？"

## 能力边界

**覆盖**：

- 同一条命令多轮执行与统计分析，含离群值检测（用来发现其他程序干扰与缓存效应）
- 多条命令并排对比，可给每条命令命名
- 预热（`--warmup`）、最小/最大轮数控制（`--min-runs` / `--max-runs`）、精确轮数（`--runs`）
- 参数扫描（`-P` 配 `-D`）与参数列表枚举（`-L`），支持组合
- 计时前后的钩子：`--setup`（每组一次）、`--prepare`（每次运行前）、`--conclude`（每次运行后）、`--cleanup`（整组结束一次）
- shell 控制：指定 shell（`-S/--shell`）或完全不用 shell（`-N` / `--shell=none`）
- 输出控制：`--style`（auto / basic / full / nocolor / color / none）、`--show-output`、`--output`（null / pipe / inherit / 文件）、`--input`
- 结果导出：json、csv、markdown、asciidoc、orgmode；`--sort` 控制排序；`--time-unit` 控制显示单位（对 CSV / JSON 无效）
- 容忍非零退出码（`--ignore-failure`）；环境变量 `$HYPERFINE_ITERATION` 可在导出文件名里区分轮次

**不覆盖**：

- 性能归因与热点定位（只给耗时，不给原因，要 profiler）
- 服务端并发 / 吞吐 / 延迟分位（要负载测试工具）
- 前端与浏览器渲染性能
- 跨机器绝对性能对比（结果依赖本机环境，无跨机可比性保证）
- 常驻服务或长跑进程的耗时测量
- 交互式命令的自动化（需要人工输入的命令不适合）

## 依赖条件

- 单二进制，官方提供各平台预编译包；Homebrew / MacPorts / nix / Chocolatey / Scoop 及各 Linux 发行版仓库均已收录
- 无运行时依赖，不需要 Node / Python 等运行时
- 不需要账号、API Key 或联网
- 被测命令必须能在本机执行；用 shell 模式时依赖系统可用的 shell
- 不同打包版本的参数细节有差异（如 `--ignore-failure` 是否支持带值、`--conclude` 的短名），以本机 `--help` 为准

## 已知限制

1. **参数名易记错**：`-s` 是 `--setup` 而非 `--shell`（`--shell` 是 `-S`），`-N` 是 `--shell=none` 的别名。这是最高频的误用。
2. 默认把被测命令输出重定向到 `/dev/null`，会让部分程序走优化分支，测出的数字偏乐观。
3. 参数扫描的成本是"轮数 × 取值数"级别，宽范围扫描很耗时。
4. 测量结果受本机 CPU 调频、系统负载、磁盘缓存影响，跨机器或跨时段的绝对值不可直接比较。
5. CSV 导出只有汇总统计且单位固定为秒；逐次运行的明细只在 JSON 里。
6. `--time-unit` 对 CSV 与 JSON 无效。
7. 官方文档中的部分参数在不同发行版文档里写法不一致，必须以本机 `--help` 为准。
8. 被测命令会真实执行，带副作用的命令会产生实际影响。

## 自检清单

执行前：

- [ ] `hyperfine --help` 确认本机版本的参数（尤其 `-s` / `-S` / `-N` 的真实含义）
- [ ] 确认被测命令**没有副作用**——它会被真实执行很多轮，删文件、发请求、写数据库都会重复发生
- [ ] 给足 `--warmup`，排除首次运行与缓存冷启动的影响
- [ ] 轮数量级合理：`--min-runs` 别设太小，否则统计量没有意义
- [ ] 用 `-n` 给命令起短名字，避免表格错乱
- [ ] 参数扫描先粗后细，评估总耗时（轮数 × 取值数）
- [ ] 如果被测程序会对输出做优化，决定用 `--output=pipe` 还是接受 `/dev/null` 的行为
- [ ] 多命令对比时尽量在同一台机器、同一时段、相近系统负载下跑

执行后：

- [ ] 看**标准差**而不是只看均值：标准差大说明环境噪声大，结论不可靠，应加大轮数或排查干扰
- [ ] 检查是否出现离群值提示，确认没有其他程序在干扰
- [ ] 确认被测命令都成功退出（否则要判断是命令失败还是真的更慢）
- [ ] 需要留存就把结果导出（json 含逐次数据，csv 只有汇总）
- [ ] 结论里注明机器与运行条件，避免被当成跨环境的绝对指标使用

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/sharkdp/hyperfine | 上游仓库（安装、完整参数说明与示例以它为准） |

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
