---
name: sanjianke-git-extras
slug: sanjianke-git-extras
displayName: 三剪客 · Git 增强命令集
description: "git-extras 把仓库摘要、代码热度、变更日志、发版打标、.gitignore 维护这批日常 Git 操作补成一条条独立子命令，本文给出安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "git-extras 是一组 git 子命令扩展，补齐 git summary / git effort / git changelog / git release / git ignore / git squash 等原生 git 没有的日常操作，本文给出安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · Git 增强命令集

`git` 本身够用，但很多「顺手一查」的动作它没做：这个仓库谁贡献了多少、哪几个文件改得最凶、上次发版到现在都有什么改动、把三条提交压成一条、临时想 ignore 一个文件又不想污染 `.gitignore`。git-extras 就是把这些补成一批独立的 `git-<name>` 子命令，装上以后直接 `git summary`、`git effort` 这样用。

它不改写 git 本身，只是在你的 `PATH` 里多加了几十个可执行脚本，所以装不装都不影响原有 git 行为，卸载也干净。

**上游项目**：`git-extras`　**仓库**：https://github.com/tj/git-extras

## 什么时候用 / 不用

**用它**：

- 「这个仓库大概什么规模、谁在提交」——`git summary` 一行拿到项目名、年龄、提交数、文件数、作者贡献占比。
- 「哪几个文件最需要重构」——`git effort --above N` 按提交次数和活跃天数排序，比 `git log --stat` 直观得多。
- 「帮我从上次 tag 到现在生成一份变更日志」——`git changelog` 直接写 `History.md`（或指定文件），也能 `--stdout` 只打印。
- 「发版：提交 + 打 tag + 推上去一条命令搞定」——`git release <tagname>`，还能 `--semver minor` 递增版本号。
- 「就想让某个文件被忽略，但不想动 `.gitignore`」——`git ignore -p <pattern>` 写进 `.git/info/exclude`，私有且不进版本库。
- 「把最近 N 条提交压成一条」——`git squash HEAD~3 "message"`。

**不要用它**：

- 你只需要标准 git 功能（`add` / `commit` / `push` / `log` / `rebase`）——直接调原生 git，多装一层子命令只会让脚本更难移植到没装 extras 的机器上。
- 目标机器不能或不允许往 git 的安装目录（`libexec/git-core`）写文件，且也不方便改 `PATH`——安装脚本默认要落在这类位置；这种情况先确认你有权限，否则别硬上。
- 脚本要在 CI 里长期稳定复现——extras 是外部依赖，CI 镜像不预装就得每次额外装一遍；能用原生 git 或 `git log --pretty` 表达的就别依赖它。
- 你要的是**重写历史**这类高风险操作（`git obliterate`、`git reauthor`、`git sed`）——它们会改 commit，需要强推并通知所有协作者。除非明确知道后果，否则不要代用户执行。
- 你想要的其实是别的工具——例如格式化 diff、交互式暂存、提交信息规范校验，这些不是 extras 的职责，装了也找不到对应命令。

## 安装

macOS 走 Homebrew：

```bash
brew install git-extras
```

Debian / Ubuntu 走 apt：

```bash
sudo apt-get install git-extras
```

通用做法是从仓库源码装（需要 `make`、`bash`，以及能写入 git 的 `libexec` 目录）：

```bash
git clone https://github.com/tj/git-extras.git
cd git-extras
sudo make install
```

装到用户目录、不碰系统（把 `PREFIX` 指到自己有写权限的位置）：

```bash
PREFIX=$HOME/.local make install
```

Makefile 支持 `PREFIX`、`DESTDIR` 这类变量；具体可用哪些安装目标与变量以仓库里的 `Makefile` / `Installation` 说明为准，不要凭印象拼参数。

Windows 上原生没有 apt / brew 这条路。可行的是：在 WSL 里按 Linux 方式装；或在 Git Bash 里 `git clone` 后 `make install`，但依赖 Git for Windows 自带的 MSYS 环境提供了 `make` 和基础工具链。装完确认 `git summary` 能跑起来，再考虑长期使用。

## 常用操作

1）看仓库总览：项目名、仓库年龄、分支、提交数、文件数、未提交变更与作者占比。

```bash
git summary
git summary v1.0.0..        # 只统计某个范围
git summary --dedup-by-email # 同一人多个邮箱合并成一条
git summary --line bin/      # 按改动行数统计，最后一个是路径
```

2）找最需要关注的文件（提交次数 + 活跃天数），`--above` 过滤掉改动少的：

```bash
git effort --above 5
git effort bin/* -- --after="one year ago" --author="someone"
```

注意 `--` 后面才是传给 `git log` 的参数，`--` 前面是 extras 自己的参数。

3）生成变更日志（默认更新/创建 `History.md`，也可指定文件名）：

```bash
git changelog                      # 从最近一个 tag 到现在
git changelog --list               # 只列 commit，不带标题和日期
git changelog --start-tag 2.1.0    # 从指定 tag 到现在
git changelog -s 0.5.0 -f 1.0.0    # 指定区间
git changelog --stdout             # 打到标准输出，不写文件
git changelog --prune-old          # 覆盖已有日志而不是追加
```

4）发版：提交 + 打 tag + 推送，一条命令：

```bash
git release 0.1.0
git release 0.1.0 -m "custom commit message"
git release 0.1.0 -r origin -c      # 指定 remote 并顺带生成 changelog
git release --semver minor          # 最新 tag 是 4.4.0 时递增为 4.5.0
git release --semver minor --prefix r  # r4.4.0 -> r4.5.0
```

5）维护忽略规则（默认写当前目录 `.gitignore`）：

```bash
git ignore                       # 不带参数时打印 global 与 local 的忽略内容
git ignore '*.log'               # 追加到 .gitignore
git ignore -g '*.log'            # 写进全局 gitignore
git ignore -p '*.log'            # 写进 .git/info/exclude（私有，不进版本库）
```

6）压缩提交：把从某个 ref 到 HEAD 的提交压成一条：

```bash
git squash HEAD~3 "Commit message"   # 压缩并直接提交
git squash --squash-msg @~3          # 压缩并拼接所有原提交信息作为提交信息
git squash my-other-branch           # 只压入索引，之后自己再 commit
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `git summary` 报 `is not a git command` | extras 的脚本没进 `PATH`，或安装目录不在 git 的 `libexec/git-core` 下 | 确认 `make install` 的输出落在 git 能找到的位置；重开一个 shell 让 `PATH` 刷新 |
| `git summary` 输出把同一个作者列成好几行 | 同一个人用了多个邮箱地址 | 加 `--dedup-by-email` 合并 |
| `git summary --line` 想同时加 `--dedup-by-email` 报错 | `--line` 与 `--dedup-by-email`、`--no-merges` 互斥 | 分开跑两次，或先确认这次到底要看行数还是看提交数 |
| `git effort` 输出先是乱序、然后屏幕被清掉 | 该命令先打印未排序列表再清屏输出排序结果 | 属预期行为。要接管道时留意前面的噪声，必要时重定向到文件后再读 |
| `git effort --author=...` 报参数错误 | `--author` 是 `git log` 的参数，不是 extras 的 | 写成 `git effort -- --author="name"`，用 `--` 分隔 |
| `git release` 多出一条空提交 | 该命令默认总是创建 release 提交，即使工作区没有改动 | 加 `--no-empty-commit` 跳过空提交 |
| `git changelog --prune-old` 之后旧记录全没了 | 该选项是「用新内容整体替换」，不是追加 | 执行前先提交或备份现有日志文件 |
| `git ignore -p` 写的规则换台机器就失效 | `-p` 写的是 `.git/info/exclude`，只对当前 clone 有效且不进版本库 | 团队要共享的规则用默认的本地 `.gitignore` 并提交 |
| `git squash` 之后还停在旧分支上 | 不带提交信息时，squash 结果只压进索引，需要你自己再 `git commit` | 想一步到位就把提交信息作为第二个参数传进去 |
| `git obliterate` / `git reauthor` / `git sed` 跑完历史变了 | 这几个命令会重写已有 commit | 只在你完全清楚后果时使用；跑完必须强推并通知所有协作者 |
| 装了 extras 后某些自定义 git 别名被顶掉 | extras 提供同名子命令时会覆盖既有行为 | 装之前先 `git config --get-regexp alias` 看一遍，冲突的改名 |
| Windows 的 Git Bash 里脚本报缺工具 | extras 的部分脚本依赖 Unix 工具链 | 优先走 WSL；或在 Git Bash 的 MSYS 环境里补齐依赖后再试 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 仅安装时 | `git clone` 拉源码；`git release` / 推送类命令按你配置的 remote 联网。命令本身不向第三方服务上报数据 |
| 读取文件 | 是 | 读取 `.git` 目录（提交历史、tag、配置）、工作区文件、`.gitignore` 与全局 gitignore |
| 写入文件 | 是 | 安装时写 git 安装目录；`git changelog` 写日志文件；`git ignore` 写 `.gitignore` / `.git/info/exclude`；`git release` 创建提交与 tag |
| 凭证 | 否（复用 git 自身） | 不保存任何账号密码；需要推送时沿用你已经配置好的 git 凭据（SSH key / credential helper） |
| 子进程 / 后台常驻 | 子进程：是；后台常驻：否 | 每条 extras 命令都是一个 shell 脚本，内部再调 `git log` / `git push` 等；不驻留后台进程 |

## 触发场景

- 「帮我看看这个仓库谁提交最多、大概多大」
- 「哪几个文件改得最频繁，我想挑出来重构」
- 「从上一个 tag 到现在生成一份 changelog」
- 「发个 1.2.0 版本，提交打 tag 推上去」
- 「把最近三次提交合成一条」
- 「这个文件我想忽略掉，但是不想改 .gitignore」

## 能力边界

**覆盖**：

- 仓库层面的统计类查询：提交数、文件数、作者贡献、按文件的热度（`summary` / `effort` / `count` / `authors` / `contrib`）
- 发版流程辅助：`changelog` 生成变更日志、`release` 提交打标推送、`delete-tag` / `rename-tag`
- 忽略规则维护：`ignore` 支持本地、全局、仓库私有三种上下文
- 分支与提交的批量整理：`squash`、`undo`、`delete-branch`、`delete-merged-branches`、`fresh-branch`、`graft`
- 一批文件级与信息类小工具：`touch`、`info`、`root`、`local-commits`、`missing`、`show-tree`
- 子模块与远程辅助：`delete-submodule`、`rename-remote`、`fork`

**不覆盖**：

- 不替代 git 本体：所有底层对象模型、合并、rebase 语义仍由 git 决定，extras 只是包一层脚本
- 不做交互式 TUI（没有类似交互式暂存、可视化历史图那样的界面）
- 不做代码格式化、lint、提交信息规范校验，这些属于别的工具
- 不做 diff 渲染美化，也不接管 `git log` 的默认输出样式
- 不负责凭据管理，推送权限完全依赖你本地已有的 git 配置

## 依赖条件

- 已安装 `git`，且 `git` 在 `PATH` 上
- 从源码安装时需要 `make` 与 `bash`；有写权限的安装目标目录
- 部分子命令内部会调 `awk`、`sed`、`grep` 这类 Unix 工具，Linux / macOS 自带；Windows 建议走 WSL
- 包管理器安装（brew / apt 等）不需要 Rust、Go、Node 之类的额外工具链

## 已知限制

- 命令集是 shell 脚本实现，不同平台（尤其 Windows 原生）行为不完全一致，部分命令只在 MSYS/WSL 下可用。
- 依赖 git 本身的输出格式，git 大版本升级后个别命令可能需要更新 extras 版本才正常。
- 部分功能依赖你的 git 配置（例如 `changelog.format` 控制每条提交的格式），不配置就用默认格式。
- `summary` 的作者统计以邮箱/名字为准，同一个人的多个身份需要 `--dedup-by-email` 手工合并。
- 上游的各个子命令成熟度不一，长尾命令（如 `obliterate`、`psykorebase`）使用面较窄，遇问题优先查该命令自己的帮助输出。

## 自检清单

执行前：

- [ ] 确认 `git --version` 可用，且当前目录确实在一个 git 仓库里（多数命令会直接报错）
- [ ] 确认要跑的命令是只读统计（`summary` / `effort` / `changelog --stdout`）还是会写东西（`release` / `ignore` / `squash` / `obliterate`）
- [ ] 涉及重写历史的命令，先确认工作区干净、目标分支没有被别人依赖
- [ ] 需要联网推送的，先确认 remote 和凭据就绪

执行后：

- [ ] 只读命令：核对输出口径（是否合并了同一作者、是否排除了 merge 提交）
- [ ] 写入命令：`git status` 确认新增/修改的文件符合预期
- [ ] `release` / `squash` 之后：`git log --oneline -5` 确认提交与 tag 落在预期位置
- [ ] 重写历史的：确认已通知协作者，并准备好强推

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/tj/git-extras | 上游仓库（安装与完整命令清单以它为准） |
| https://github.com/tj/git-extras/tree/master/man | 各子命令的 man 源文件，查参数最快 |

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
