---
name: sanjianke-gitleaks
slug: sanjianke-gitleaks
displayName: 三剪客 · gitleaks 密钥扫描
description: "{desc}。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "{summary}。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
  - 安全扫描
---

# 三剪客 · gitleaks 密钥扫描

密钥泄漏最麻烦的地方在于"它已经在历史里了"——当前文件删掉没用，`git log` 里的那个 commit 还在。想在上线前把这类问题拦住、想在接手一个老仓库时先摸一遍底、想在 CI 里加一道"不许提交 AK/SK"的闸门，都需要一个能**同时看当前文件和历史提交**的扫描器。

gitleaks 就是这个定位：一条命令扫完，给出一份带文件、行号、commit 与指纹的报告，发现泄漏时用退出码告诉你。它靠内置规则做正则匹配加熵与解码分析，**不联网验证密钥是否真的有效**——这是它和"会调用外部 API 验证凭证"的那类工具最大的区别。

**上游项目**：`gitleaks`　**仓库**：https://github.com/gitleaks/gitleaks

## 什么时候用 / 不用

**用它**：

- "这个仓库里有没有硬编码的密钥？连历史一起看。"——`gitleaks git` 走 `git log -p` 扫补丁，覆盖全部提交历史。
- "上线前在 CI 里加一道密钥检查，泄漏就阻断合并。"——发现泄漏默认退出码 1，流水线判一个码即可。
- "把当前目录（不关心历史）过一遍，比如一个构建产物目录或一个非 git 的文件夹。"——`gitleaks dir <path>`。
- "我要一份机器可读的报告给安全平台。"——`--report-format sarif` 直接对接代码扫描平台，也支持 json / csv / junit / template。
- "这个仓库历史太长、误报一堆已知问题，我只想看**新**引入的。"——先用 `--report-path` 存一份基线，再用 `--baseline-path` 忽略存量，报告里只剩新问题。

**不要用它**：

- **想知道扫出来的密钥是不是还有效**——gitleaks 只做静态匹配，不做联网验证。要判断"这 key 还能不能用"得用带主动验证能力的工具。
- **想扫云存储、聊天记录、日志系统、Docker 镜像**——gitleaks 的输入只有 git 仓库、目录/文件和标准输入，不接对象存储与 SaaS 数据源。
- **想让扫描器顺便告诉你这个 key 能访问哪些资源**——那是"凭证取证"能力，不在 gitleaks 范围内。
- **想当成实时拦截的守护进程**——它是一次性命令（含 `stdin` 模式可接管道），没有常驻服务形态；实时拦截要靠 git hook 或 CI 触发。
- **想自动改掉或轮换泄漏的密钥**——只报告，不修复。

## 安装

Homebrew（macOS / Linux）：

```bash
brew install gitleaks
```

Docker（DockerHub 镜像）：

```bash
docker pull zricethezav/gitleaks:latest
docker run -v ${path_to_host_folder_to_scan}:/path zricethezav/gitleaks:latest [COMMAND] [OPTIONS] [SOURCE_PATH]
```

Docker（GitHub 容器仓库镜像）：

```bash
docker pull ghcr.io/gitleaks/gitleaks:latest
docker run -v ${path_to_host_folder_to_scan}:/path ghcr.io/gitleaks/gitleaks:latest [COMMAND] [OPTIONS] [SOURCE_PATH]
```

从源码构建（需要 Go 工具链）：

```bash
git clone https://github.com/gitleaks/gitleaks.git
cd gitleaks
make build
```

官方 Releases 页也提供各平台二进制包。装完确认：

```bash
gitleaks version
```

用包管理器安装的版本可能落后于上游，遇到参数不认识时先确认版本：

```bash
gitleaks version
gitleaks --help
gitleaks git --help
```

## 常用操作

**1. 扫 git 仓库的完整历史（最常用）**

```bash
gitleaks git                          # 不指定路径则扫当前目录
gitleaks git path_to_repo             # 指定仓库路径
gitleaks git -v path_to_repo          # -v 打印扫描细节，排查"为什么没扫到"很有用
```

**2. 只扫某段提交范围**

`git` 模式底层是 `git log -p`，通过 `--log-opts` 把参数透传给 `git log`：

```bash
gitleaks git -v --log-opts="--all commitA..commitB" path_to_repo
```

**3. 扫目录或单个文件（不看 git 历史）**

```bash
gitleaks dir -v path_to_directory_or_file
gitleaks dir                          # 不指定则扫当前工作目录
```

`dir` 这一命令还接受别名 `file` 与 `directory`。

**4. 从标准输入扫（接管道）**

```bash
cat some_file | gitleaks -v stdin
```

**5. 出报告：格式、路径与"输出到终端"**

```bash
# 存一份 JSON 报告（也常用作后续的基线）
gitleaks git --report-path gitleaks-report.json

# 显式指定格式，并直接输出到 stdout
gitleaks git --report-format json --report-path -

# SARIF 给代码扫描平台用
gitleaks git --report-format sarif --report-path gitleaks.sarif

# 用自定义模板
gitleaks git --report-format template --report-template my.tmpl --report-path out.txt
```

不指定 `--report-format` 时会**按 `--report-path` 的扩展名推断**，可识别的扩展名只有 `.json`、`.csv`、`.sarif`；推断不出来会直接报错。可用的格式值是 `json`、`csv`、`junit`、`sarif`、`template`。

**6. 用基线忽略存量问题**

```bash
# 第一次：把现有问题存成基线
gitleaks git --report-path gitleaks-report.json

# 之后：忽略基线里的问题，报告只留新增
gitleaks git --baseline-path gitleaks-report.json --report-path findings.json
```

**7. CI 里改判定行为**

```bash
gitleaks git --exit-code 1 --report-format sarif --report-path results.sarif
gitleaks git --redact=20 --report-path masked.json   # 只保留 20% 原文，其余打码
gitleaks git --no-banner --log-level warn            # 日志干净一点
```

**8. pre-commit 只扫暂存改动**

```bash
gitleaks git --pre-commit --staged          # 等价于旧写法 gitleaks protect --staged
gitleaks git --staged                       # 扫已 staged 的提交内容
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 脚本里写的 `gitleaks detect` / `gitleaks protect` 突然报未知命令或参数 | 这两个子命令在 v8.19.0 起被**弃用并隐藏**，`--help` 里看不到，官方已明确它们不再是推荐入口 | 按官方对照关系改写：`detect --source={repo}` → `git {repo}`；`detect --no-git --source={dir}` → `dir {dir}`；`detect --no-git --pipe` → `stdin`；`protect --source={repo}` → `git --pre-commit {repo}`；`protect --staged --source={repo}` → `git --pre-commit --staged {repo}` |
| 照旧文档写 `[allowlist]` 或 `[rules.allowlist]`，升级后感觉不生效 | 配置里的 allowlist 已改名为复数数组：`[rules.allowlist]` 在 v8.21.0 被 `[[rules.allowlists]]` 取代，全局 `[allowlist]` 在 v8.25.0 被 `[[allowlists]]` 取代 | 新配置一律写 `[[rules.allowlists]]` 与 `[[allowlists]]`。旧写法目前仍向后兼容，但别指望长期可用；一个规则可以定义多个 allowlist，**任意一个匹配就忽略该 finding** |
| 只写了 `--report-path` 没写 `--report-format`，程序报 `Unknown report format` | 扩展名推断只认 `.json`、`.csv`、`.sarif`，写别的后缀（如 `.txt`、无后缀）就推不出来 | 显式加 `--report-format json`（或 csv / junit / sarif / template），别依赖推断 |
| 报 `Report format must be 'template' if --report-template is specified` | 给了模板文件但格式不是 template | 用模板时必须同时写 `--report-format template` |
| CI 只克隆了最近一次提交，历史里的密钥一个都没扫出来 | 浅克隆（shallow clone）拿不到完整历史，而 `git` 模式是翻 `git log` 的 | 让 CI 做完整克隆（如取全量 fetch depth），或退一步用 `dir` 只扫当前文件快照并明确知道这是降级 |
| 历史很长的大仓库扫一次特别慢 | `git` 模式要逐提交扫补丁，耗时可观 | 用 `--log-opts` 缩小范围（如只扫最近一段或某个区间）；用 `--baseline-path` 忽略存量，避免每次都在处理老问题；必要时 `--timeout` 兜底 |
| 误报挡不住，每次都要人工看 | 内置规则走正则 + 熵，对测试数据、示例 key、文档里的假密钥会命中 | 三种手段按粒度选：行内加 `#gitleaks:allow` 注释；仓库根放 `.gitleaksignore` 写 finding 的 `Fingerprint`；或在配置里写 `[[rules.allowlists]]` 按正则/路径/行范围批量忽略 |
| 报告里出现明文密钥，被贴进工单或聊天记录 | 默认不脱敏 | 加 `--redact`（等价 `--redact=100`）全打码，或 `--redact=20` 只保留 20% 原文；`--redact` 不带值时默认就是 100 |
| `--enable-rule` 写了规则 id 却直接 fatal | 该 id 在内置规则里不存在时会报 `Requested rule ... not found in rules` 并退出 | 先确认规则 id 拼写；`--enable-rule` 的语义是**只启用指定规则**，不是"额外加一条"，别拿它当增量开关 |
| 扫描超时没有任何输出就结束 | 用了 `--timeout` 且扫描超过了它 | `--timeout 0` 表示不设超时（默认），报错时先确认是不是自己设了值；`git` 模式超时与历史长度强相关 |
| 解开的嵌套内容扫不到，或解码层级不够 | 默认不解码也不解压：`--max-decode-depth` 与 `--max-archive-depth` 都是 0 | 需要时显式打开，例如 `--max-decode-depth 5`、`--max-archive-depth 1`。注意 README 的 `--help` 片段与本仓库源码在同一项上的默认值写法并不一致，**以本机 `gitleaks --help` 输出为准** |
| 参数名写错时退出码不是 1 而是 126 | 未知 flag 会被专门处理成 126（命令无法执行），与"发现泄漏"的退出码区分开 | CI 判定时把 126（以及 fatal 的 1）与"扫到密钥的退出码"分开处理，别把写错参数当成有泄漏 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 扫描全程离线，规则内置于二进制；只有安装（brew / docker pull / 拉取源码）时需要联网 |
| 读取文件 | 是 | 扫描目标仓库、目录或文件；读取 `.gitleaks.toml` 与 `.gitleaksignore` |
| 写入文件 | 是 | `--report-path` 写报告文件；不指定则只打印到终端 |
| 凭证 | 否 | gitleaks 本身不需要任何 token 或账号；它不做联网验证，所以不需要调用外部 API 的凭证 |
| 子进程 / 后台常驻 | 是 | `git` 模式会调用本机 `git log`（要求目标目录可用 git 命令）；进程一次性执行完即退出，无常驻服务 |

## 触发场景

- "帮我检查一下这个仓库有没有泄漏的密钥。"
- "连 git 历史一起扫，别只看当前文件。"
- "在 CI 里加一道密钥扫描，有泄漏就失败。"
- "历史里有几个已知的假密钥，我不想每次都看到它们。"
- "出一份 SARIF 报告给代码扫描平台。"
- "只扫这次提交改动的内容，不要全仓库。"
- "为什么我这条老命令 `gitleaks detect` 不能用了？"

## 能力边界

**覆盖**：

- 三种扫描模式：`git`（扫仓库历史提交补丁）、`dir`（扫目录与文件，含别名 `file` / `directory`）、`stdin`（从标准输入读）
- 内置规则库，含正则匹配、熵检测与递归解码；解码深度与归档遍历深度可调
- 报告输出：json、csv、junit、sarif、template 五种格式，可写文件也可写 stdout（`--report-path -`）
- 免打扰机制：`#gitleaks:allow` 行内注释、`.gitleaksignore` 指纹文件、配置内的 `[[rules.allowlists]]` / `[[allowlists]]`
- 基线机制：用历史报告忽略存量问题，报告里只保留新增
- 配置可扩展与覆盖：`[extend]` 支持 `useDefault = true` 继承内置规则，或用 `path` 指向外部配置（二者不能同时用，链式扩展深度为 2，即至多嵌套两层）
- 脱敏（`--redact`）、退出码自定义（`--exit-code`）、日志级别与诊断信息输出
- 支持作为 pre-commit 钩子（另有独立的 gitleaks-action 供 CI 使用）

**不覆盖**：

- **凭证有效性验证**：不联网测试密钥是否仍然可用，只做静态匹配
- **非 git / 目录 / stdin 的数据源**：不接对象存储、聊天记录、日志系统、容器镜像等
- **凭证取证与分析**：不告诉你这个密钥能访问哪些资源、属于谁
- **自动修复**：不删除、不轮换、不改写任何文件内容
- **常驻守护与实时拦截**：是命令行工具，实时拦截要靠 git hook 或 CI 调度
- **对加密/压缩内容的无限层扫描**：解码与归档深度默认关闭，且必须显式限额
- 该工具上游已声明进入"功能完成"状态，后续以安全修复为主，新特性不保证会加入

## 依赖条件

- 单二进制，无运行时依赖；Homebrew、Docker 镜像、源码构建（需 Go 工具链）或官方 Release 二进制包均可
- `git` 模式要求本机可执行 `git` 命令，且目标目录是一个 git 仓库
- 配置解析依赖 TOML：可用 `--config`、环境变量 `GITLEAKS_CONFIG`（指向文件路径）或 `GITLEAKS_CONFIG_TOML`（直接给文件内容）
- 不需要账号、API Key 或任何凭证
- 不同版本间行为有差异（子命令弃用、配置字段改名），以本机 `gitleaks --help` 为准

## 已知限制

1. `detect` 与 `protect` 已被弃用并从帮助列表隐藏，官方不再推荐使用，新脚本一律用 `git` / `dir` / `stdin`。
2. 配置里的 allowlist 字段经历过改名，照抄老文章的配置容易失效。
3. `--report-format` 的扩展名推断只认 `.json`、`.csv`、`.sarif`，其余后缀必须显式指定格式。
4. 浅克隆的仓库扫不到历史内容，会给人"很干净"的错觉。
5. 报告默认含明文密钥，直接上传工单或日志有二次泄漏风险，需要主动加 `--redact`。
6. 源码内置的 `--max-decode-depth` 默认值与 README 帮助片段的写法存在出入，必须以本机 `--help` 为准；不确定时不要假设"默认会解码"。
7. 上游已公开声明进入功能完成状态，未来以安全补丁为主。

## 自检清单

执行前：

- [ ] `gitleaks version` 确认版本，并据此核对子命令与配置字段写法（v8.19 / v8.21 / v8.25 前后的行为差异明显）
- [ ] 确认扫描模式选对：要历史用 `git`，只要当前快照用 `dir`，管道输入用 `stdin`
- [ ] 若在 CI 中运行，确认仓库是完整克隆而不是浅克隆，否则历史扫描无意义
- [ ] 大仓库先规划 `--log-opts` 范围与 `--timeout`，避免一次跑到卡死
- [ ] 已有存量问题的话，先准备好基线报告，避免每次都被老问题淹没
- [ ] 报告可能含明文密钥，确认输出路径与后续处理方式（是否需要 `--redact`）
- [ ] 需要 SARIF 时同时确认 `--report-format sarif` 与目标平台能接收

执行后：

- [ ] 检查退出码：发现泄漏为 `--exit-code` 的值（默认 1），参数写错为 126，其余 fatal 情况也要区分对待
- [ ] 确认报告文件真的写了内容（`--report-path -` 是输出到 stdout，不会落盘）
- [ ] 抽查几条 finding 的文件、行号与 commit 是否正确，排除误报
- [ ] 真泄漏要按流程处置：**先轮换/吊销密钥再清理历史**，只删文件不回滚历史等于没处理
- [ ] 把确认的误报沉淀成 allowlist 或 `.gitleaksignore`，减少下次噪音

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/gitleaks/gitleaks | 上游仓库（安装、命令、完整配置说明与命令对照关系以它为准；CI 集成与 pre-commit 钩子的接线方式也在此仓库文档内） |

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
