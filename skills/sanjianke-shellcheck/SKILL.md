---
name: sanjianke-shellcheck
slug: sanjianke-shellcheck
displayName: 三剪客 · Shell 脚本静态检查
description: "shellcheck：不运行脚本就能找出会咬人的写法——没加引号的变量、[ ] 与 [[ ]] 的坑、命令替换的单词拆分、cd 失败后继续跑。CI 门禁和本地自查都好用。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "shellcheck 的安装与实战用法：批量检查脚本、用 -s 指定方言、用 -S 卡严重级别、用 -e/-i 精确增删规则、用 -f diff 直接出可应用的补丁、在 CI 里按退出码做门禁，以及 SC1090 动态 source、Docker 读不到配置、Windows 代码页等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
  - Shell
  - 静态检查
---

# 三剪客 · Shell 脚本静态检查

Shell 脚本最坑人的地方不是报错，而是**不报错**：变量忘了加引号，本地测试一切正常，到了文件名带空格的机器上就炸；`cd $dir` 失败后脚本继续往下跑，把文件删在了错误的目录；`for f in $(ls)` 遇到带空格的名字就默默少处理几个文件。这些写法在运行前就能被看出来。

`shellcheck` 干的就是这件事：只读脚本、不执行、不联网，按 shell 方言给出具体的规则编号和修法建议。因为有稳定的规则编号（SC2086 之类），它既能当编辑器的实时提示，也能当 CI 里的提交门禁。

**上游项目**：`shellcheck`　**仓库**：https://github.com/koalaman/shellcheck

## 什么时候用 / 不用

**用它**：

- "这个部署脚本上线前帮我过一遍，别留低级坑。"——`shellcheck deploy.sh`，退出码 1 就说明有问题。
- "仓库里几百个 `.sh` 一次性体检。"——`shellcheck -x $(fd -e sh)` 之类的组合，配 `-f` 换输出格式。
- "把结果喂给 CI 或自建看板。"——`shellcheck -f json1 scripts/*.sh`，结构化输出好解析。
- "它报的问题我想直接应用修复。"——`shellcheck -f diff script.sh | git apply`，官方支持出统一 diff 格式。
- "只想看真正会出事的那几条，风格问题先不管。"——`-S warning` 把 info 和 style 级别压掉。
- "这个脚本本来没写 shebang / 是被别的脚本 source 进来的。"——`-s bash` 显式指定方言，或用 `# shellcheck shell=bash` 指令。
- "本机不想装，就临时查一个脚本。"——官方提供 Docker 镜像，一条 `docker run` 就能跑。

**不要用它**：

- **想验证脚本"跑起来对不对"**——它是静态分析，不执行、不模拟运行；逻辑正确性与运行结果需要真实执行或测试框架。
- **要处理变量里到底装了什么值**——它靠数据流分析做推断，遇到运行时才确定的取值给的是近似结论，可能出现误报或漏报。
- **用它当格式化工具**——它不改写代码（`-f diff` 只是**生成**补丁，应用动作要你自己做），也不是自动修 lint 的工具。
- **要检查 zsh、fish 这类非 Bourne 系方言**——它支持的方言是 sh / bash / dash / ksh / busybox，其他 shell 不在范围内。
- **指望规则集能覆盖全部最佳实践**——可选检查需要显式 `-o` 打开，默认只跑基础规则；不同版本规则集也在变化。
- **想检查 shell 之外的脚本**（Python、PowerShell、bat）——不适用。

## 安装

官方 README 与官网给出的入口：Debian 系、Fedora 系、Arch、Homebrew、Cabal，以及官网的在线粘贴检查页。

```bash
# Debian / Ubuntu
sudo apt install shellcheck

# Fedora / RHEL
sudo dnf install shellcheck

# Arch
sudo pacman -S shellcheck

# Alpine
apk add shellcheck

# macOS
brew install shellcheck

# 有 GHC / Cabal 工具链
cabal update && cabal install shellcheck

# Windows：从官方 README 的安装章节找到 Windows 安装入口，
# 拿到 shellcheck.exe 后放进 PATH
```

不想本地安装时，可以用官方提供的容器镜像：

```bash
docker run --rm -v "$PWD:/mnt" koalaman/shellcheck:stable script.sh
```

装完验证：

```bash
shellcheck --version
shellcheck --help | head -n 20
echo 'echo $1' | shellcheck -     # 从标准输入读一个脚本片段
```

## 常用操作

**1. 检查单个文件 / 多个文件 / 整个目录**

```bash
shellcheck script.sh
shellcheck scripts/*.sh
shellcheck -x deploy.sh              # 连同 source 进来的文件一起检查
shellcheck - < script.sh             # 从标准输入读（"-" 代表 stdin）
```

**2. 指定方言（没有 shebang 的脚本必用）**

```bash
shellcheck -s bash lib/common.sh
shellcheck -s sh posix-only.sh       # sh 指 POSIX sh，会额外提示可移植性问题
```

可用值：`sh`、`bash`、`dash`、`ksh`、`busybox`。不上 `-s` 时按"shell 指令 → shebang → 扩展名"的顺序推断。

**3. 按严重级别与规则编号做取舍**

```bash
shellcheck -S warning script.sh          # 只报 error 与 warning
shellcheck -e SC2086 script.sh           # 排除指定规则
shellcheck -e SC2086,SC2046 script.sh    # 逗号一次写多个
shellcheck -i SC2086 script.sh           # 只报指定规则（-i 优先级高于 -e）
```

严重级别从高到低：`error`、`warning`、`info`、`style`。

**4. 换输出格式：给编辑器、CI、看板用**

```bash
shellcheck -f gcc script.sh        # file:line:col: type: message，编辑器可解析
shellcheck -f checkstyle script.sh # XML，IDE 与构建系统常见格式
shellcheck -f json1 script.sh      # 结构化 JSON（含 file/line/column/level/code/message）
shellcheck -f quiet script.sh      # 不输出内容，只用退出码表达"有没有问题"
```

**5. 直接生成修复补丁**

```bash
shellcheck -f diff script.sh > fix.patch
git apply fix.patch                    # 审查过再应用
shellcheck -f diff script.sh | patch -p1
```

**6. 用指令和配置文件固化例外**

```bash
# 文件内：写在第一行命令之前是文件级，写在某条命令之前只作用于它
# shellcheck shell=bash
# shellcheck disable=SC2086
# shellcheck source=./lib.sh
# shellcheck source-path=SCRIPTDIR

# 项目根放 .shellcheckrc（会在脚本目录及各级父目录里查找）
shellcheck --rcfile .shellcheckrc script.sh   # 指定配置文件
shellcheck --norc script.sh                   # 完全不用任何配置文件
shellcheck --list-optional                    # 看有哪些可选检查可以 -o 打开
shellcheck -o all script.sh                   # 打开全部可选检查
```

**7. 常用环境变量与容器组合**

```bash
export SHELLCHECK_OPTS='--shell=bash --exclude=SC2016'   # 每次调用都自动带上
docker run --rm -i koalaman/shellcheck:stable - <<< 'echo $1'
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 报 `SC1091: Not following ...`，说找不到 source 的文件 | 默认只跟随命令行上明确给出的文件（外加 `/dev/null`），被 source 的文件不在列表里就不展开 | 加 `-x`（`--external-sources`）允许跟随任意 source；或在 `.shellcheckrc` 里写 `external-sources=true` |
| 报 `SC1090: Can't follow non-constant source` | source 的路径是运行时算出来的（变量、命令替换），静态分析无法确定 | 用 `# shellcheck source=./lib.sh` 指令告诉它真实文件；不关心就 `source=/dev/null` 跳过 |
| source 的文件在别的目录，加 `-x` 还是找不到 | 搜索路径默认只有 ShellCheck 的工作目录 | 用 `-P`（`--source-path`）加目录，支持 `:` 分隔（Windows 上是 `;`）；在配置文件里可用 `source-path=SCRIPTDIR` 表示脚本自身所在目录 |
| 明明在 CI 里跑通了，本地却报一堆问题（或反过来） | 读取的配置文件不一样：它会从脚本目录逐级往上找 `.shellcheckrc` / `shellcheckrc`，找不到再看 `~/.shellcheckrc`、`$XDG_CONFIG_HOME/shellcheckrc`（Windows 是 `%APPDATA%/shellcheckrc`），且只用找到的第一个 | 想让行为绝对一致就固定配置：`--rcfile <文件>` 指定，或 `--norc` 完全禁用；`SHELLCHECK_OPTS` 也会影响每次调用 |
| 用 Docker 跑时 `~/.shellcheckrc` 不生效 | 容器里只能看到挂载进去的文件 | 把配置文件和脚本一起挂进容器，或改用 `--rcfile` 显式指定容器内可见路径 |
| 用 Snap 装的版本读不到隐藏配置文件 | Snap 沙箱不允许访问隐藏文件 | 按官方说明改用不带点的 `shellcheckrc` 文件名 |
| 脚本没 shebang，或 shebang 与实际运行方式不符，报了一堆不相干的错 | 方言推断顺序是 shell 指令 → shebang → 扩展名，推断错了结论就全偏 | 显式用 `-s bash`（或目标方言），或在文件里写 `# shellcheck shell=bash` |
| 有一批结果确定是误报，想永久压掉 | 每条规则都可以按编号关掉 | 局部用 `# shellcheck disable=SC2086` 写在对应命令前；项目级写进 `.shellcheckrc` 的 `disable=`；也支持范围写法 `disable=SC3000-SC4000` |
| CI 里既有"发现问题"又有"文件不存在"，脚本分不清该不该失败 | 退出码语义不同：有问题也是 1 | 0=全部扫描无问题，1=扫描完成但有问题，2=有文件没能处理（如文件不存在），3=调用语法错，4=选项错（如未知 formatter）。CI 里通常把 1 当"要修"，2/3/4 当"流程坏了" |
| Windows 终端中文输出乱码，或报 `commitBuffer: invalid argument` | 终端代码页不是 UTF-8 | `chcp 65001` 切到 UTF-8；PowerShell ISE 里可能还要设 `[Console]::OutputEncoding` |
| `-f diff` 出来的补丁 `git apply` 失败 | 补丁是基于当前文件内容生成的，文件在生成后被改过就对不上 | 先生成补丁、先审查，再应用；应用前确保文件没有被改动，或用 `patch -p1` 配合模糊匹配 |
| 几千行的生成脚本跑起来 CPU / 内存吃得很凶 | 默认开启数据流分析（extended analysis） | 用 `--extended-analysis=false` 关掉，或用 `# shellcheck extended-analysis=false` 指令；代价是少一部分检查 |
| 想只看真实风险，结果被大量风格提示淹没 | 默认最低严重级别是 `style`，全都会报 | 用 `-S warning`（或 `-S error`）抬高门槛 |
| 写了 `-F json` 之类报"未知选项"，或者输出格式没按预期变 | 格式开关是 `-f` / `--format`（小写），没有 `-F`；而且**同一命令里出现多个 `-f` 时只有第一个生效** | 按 `shellcheck --help` 核对拼写；需要多种输出格式就分多次调用 |
| 从标准输入读脚本时不知道写什么文件名 | 不是所有场景都支持用 `-` 读 stdin | 用 `shellcheck -` 明确表示从标准输入读；文件类操作还是传路径最稳 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 检查过程完全离线。只有安装时、或你主动用官网在线页面/容器拉镜像时才需要网络 |
| 读取文件 | 是 | 读取待检查的脚本；开启 `-x` 或读取 `.shellcheckrc` 时会额外读取被 source 的文件与各级配置文件 |
| 写入文件 | 否 | shellcheck 只往标准输出打印结果；`-f diff` 也只是打印补丁内容，落盘与应用由你决定 |
| 凭证 | 否 | 不需要账号、token 或任何 Key |
| 子进程 / 后台常驻 | 否 | 一次性命令行程序，不启动子进程、不常驻、不联网监听 |

## 触发场景

- "这个 shell 脚本帮我看看有没有问题。"
- "部署脚本上线前检查一遍。"
- "CI 里加个 shell 脚本检查环节。"
- "这堆 `.sh` 全部跑一遍，给我一份问题清单。"
- "为什么这个变量不加引号会出问题？"
- "这条警告能不能关掉，它在我这里是误报。"
- "脚本里 `source` 的文件也一起检查。"

## 能力边界

**覆盖**：

- 方言判定与方言相关建议：`sh`（POSIX sh，含可移植性提示）、`bash`、`dash`、`ksh`、`busybox`；推断顺序为 shell 指令 → shebang → `.bash` / `.bats` / `.dash` / `.ksh` 扩展名
- 规则增删：`-e` / `--exclude` 排除、`-i` / `--include` 只保留（`-i` 优先）、`-S` / `--severity` 按 error / warning / info / style 卡级别（默认 `style`）
- 可选检查：`--list-optional` 列出、`-o` / `--enable` 启用（`all` 表示全开）
- 跨文件分析：`-x` 跟随任意 source、`-P` / `--source-path` 指定搜索路径、`-a` 把被 source 文件里的问题也报出来
- 输出格式：`tty`（默认）、`gcc`、`checkstyle`（XML）、`json1`、`json`（旧格式，制表位为 8）、`diff`（可直连 git apply / patch）、`quiet`（只用退出码）
- 配置：脚本内 `# shellcheck key=value` 指令（含 `disable` / `enable` / `source` / `source-path` / `shell` / `external-sources` / `extended-analysis`，`disable` 支持 `SC3000-SC4000` 范围与 `all`）、`.shellcheckrc` / `shellcheckrc` 的逐级查找与 `--rcfile` / `--norc`
- 环境适配：`SHELLCHECK_OPTS` 预设默认参数、官方 Docker 镜像、terminal 颜色控制（`-C` / `--color`）、wiki 链接数量（`-W`）

**不覆盖**：

- 执行、模拟运行或对运行结果做断言
- 非 Bourne 系 shell（zsh、fish、csh 等）的语法检查
- 自动改写代码：`-f diff` 只生成补丁，不做应用
- shell 之外的语言与配置文件检查
- 运行时才确定的行为（真实的环境变量内容、外部命令的实际返回、网络与文件系统状态）
- 依赖关系、性能与安全漏洞扫描（不是它的职责范围）

## 依赖条件

- 官方发行包覆盖 Windows / macOS / Linux 各架构（含预编译二进制）；用包管理器安装时版本以该仓库为准，先用 `shellcheck --version` 确认
- 从源码构建需要 Haskell 工具链（GHC + Cabal）；官方 README 提到编译阶段内存占用不小
- 只支持 Bourne 系方言，检查目标脚本必须属于这一族
- 不需要账号、Key 或网络
- 使用官方镜像时需要可用的 Docker 环境
- 输出语言目前只有英文；文件按 UTF-8 宽松解码，非法字节序列回退 ISO-8859-1

## 已知限制

1. 纯静态分析，不做执行模拟；运行时才确定的信息只能给近似结论。
2. 不支持 zsh、fish 等非 Bourne 系 shell。
3. 不会自动改写文件；`-f diff` 只是生成补丁文本。
4. 同一命令里多个 `-f` 只有第一个生效。
5. 被 source 的文件默认不展开，需要 `-x` 加相应的搜索路径才能分析。
6. 配置文件按"脚本目录逐级向上 + 家目录兜底"的顺序查找且只用第一个，容易造成本地与 CI 结论不一致。
7. 可选检查默认关闭；规则集会随版本增删，具体编号与默认行为以本机 `shellcheck --version` 和上游 wiki 为准。

## 自检清单

执行前：

- [ ] 确认脚本的目标方言：用 `-s` 显式指定，或在文件里写 `# shellcheck shell=bash`，不要依赖推断
- [ ] 决定要不要跨文件检查：需要就加 `-x`，并用 `-P` / `source-path` 把 source 搜索路径配全
- [ ] 确认严重级别门槛（`-S`）符合本次目的：CI 门禁通常至少 `warning`
- [ ] 想固定结论一致性时，明确指定 `--rcfile`，并注意 `SHELLCHECK_OPTS` 会额外追加参数
- [ ] 需要机器可读结果就选好 `-f`（json1 / checkstyle / gcc），注意一条命令只认第一个 `-f`
- [ ] 输出到 Windows 终端前先切 UTF-8 代码页

执行后：

- [ ] 按退出码分流：0 无问题；1 有问题（要修）；2 有文件没处理成功；3 调用语法错；4 选项错——后面两类是流程故障，不是"代码有问题"
- [ ] 用 `-f diff` 时，补丁先人工审查再 `git apply`，应用前确认文件未被改动
- [ ] 为压掉的每条规则留理由：`disable` 写在最小作用域，项目级例外写进 `.shellcheckrc` 而不是散落在脚本里
- [ ] 大批量脚本检查时记录所用版本，升级后重新跑一次基线，避免规则集变化带来噪声

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/koalaman/shellcheck | 上游仓库（安装与完整文档以它为准） |
| https://www.shellcheck.net | 官网：规则说明与在线粘贴自查 |

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
