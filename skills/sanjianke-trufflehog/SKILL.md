---
name: sanjianke-trufflehog
slug: sanjianke-trufflehog
displayName: 三剪客 · trufflehog 密钥与凭证扫描
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

# 三剪客 · trufflehog 密钥与凭证扫描

正则扫密钥的通病是噪音大：`AKIA` 开头的东西可能是真 key，也可能是文档里的示例。要回答"这堆命中里**哪些还是活的**"，只有一条路——拿着它去调对应服务的 API 试一下。trufflehog 就是围绕这件事设计的：扫到候选凭证后主动验证，把结果分成"确认有效"、"未验证"、"验证失败"三态，让安全同学先处理真正有风险的那几条。

它的覆盖面也比"扫文件"宽：git 历史、GitHub 组织、GitLab、文件系统、S3、GCS、Docker 镜像、syslog、CI 平台的日志，都是一等公民的子命令。

**代价要提前知道**：验证是**真实调用外部 API**，会联网、会在对方平台留下调用记录，某些检测器还会发多条请求去探权限。这不是纯本地工具。

**上游项目**：`trufflehog`　**仓库**：https://github.com/trufflesecurity/trufflehog

## 什么时候用 / 不用

**用它**：

- "扫出来一堆疑似密钥，我要先知道**哪些还能用**。"——默认就对每条候选做 API 验证，`--results=verified` 只看确认有效的。
- "这个 GitHub 组织下所有仓库（含 issue 和 PR 评论）都过一遍。"——`trufflehog github --org=...`，还能 `--issue-comments --pr-comments`。
- "接手一个 git 仓库，历史里有没有泄漏的凭证。"——`trufflehog git file://repo --results=verified,unknown`。
- "S3 桶 / GCS / Docker 镜像 / 日志系统里有没有凭证。"——`s3`、`gcs`、`docker`、`syslog`、`elasticsearch`、`jenkins` 等各有子命令。
- "在 CI 里发现有效凭证就让流水线失败。"——加 `--fail`，发现结果时退出码固定为 **183**。

**不要用它**：

- **离线 / 内网隔离环境，又不想改参数**——默认验证要联网，离线会让所有候选落到"unknown"或拖慢扫描；这种场景必须加 `--no-verification`，但那也就等于放弃了它最大的价值。
- **不想让被扫凭证在第三方平台产生调用记录**——验证是真实 API 调用，可能触发对方告警、风控甚至锁定，敏感环境要事先评估。
- **想要自动轮换或吊销凭证**——只发现与分析，不修复。
- **拿它当常驻服务做实时拦截**——是一次性命令（可接管道或 pre-commit），没有守护进程形态。
- **只想快速扫本地目录、且不关心有效性**——纯本地正则扫描用轻量工具更快，trufflehog 的验证开销是额外成本。

## 安装

Homebrew：

```bash
brew install trufflehog
```

Docker：

```bash
docker run --rm -it -v "$PWD:/pwd" trufflesecurity/trufflehog:latest github --org=trufflesecurity
```

Windows（CMD 与 PowerShell 的挂载写法不同）：

```bash
# CMD
docker run --rm -it -v "%cd:/=\%:/pwd" trufflesecurity/trufflehog:latest github --repo https://github.com/trufflesecurity/test_keys

# PowerShell
docker run --rm -it -v "${PWD}:/pwd" trufflesecurity/trufflehog github --repo https://github.com/trufflesecurity/test_keys
```

Apple Silicon 上显式指定平台架构：

```bash
docker run --platform linux/arm64 --rm -it -v "$PWD:/pwd" trufflesecurity/trufflehog:latest github --repo https://github.com/trufflesecurity/test_keys
```

官方安装脚本（可加 `-v` 走签名校验，末尾可跟 Release 标签）：

```bash
curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin
curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -v -b /usr/local/bin
```

从源码构建：

```bash
git clone https://github.com/trufflesecurity/trufflehog.git
cd trufflehog; go install
```

官方 Releases 页也提供各平台二进制包，并附校验和文件。装完确认：

```bash
trufflehog --version
trufflehog --help
```

## 常用操作

**1. 只扫确认有效的凭证（最常用的收敛姿势）**

```bash
trufflehog git https://github.com/trufflesecurity/test_keys --results=verified
```

**2. 扫本地仓库 / 文件系统**

```bash
# 本地 git 仓库：在仓库的**父目录**执行，用 file:// 前缀
trufflehog git file://test_keys --results=verified,unknown

# 文件与目录，可一次给多个路径
trufflehog filesystem path/to/file1.txt path/to/dir
```

**3. 拿 JSON 输出给下游处理**

```bash
trufflehog git https://github.com/trufflesecurity/test_keys --results=verified --json
```

不加 `--json` 就是彩色的人类可读输出；另有 `--sarif` 与 `--github-actions` 两种面向平台的格式。

**4. 扫 GitHub 组织 / 仓库**

```bash
trufflehog github --org=trufflesecurity --results=verified
trufflehog github --org=trufflesecurity --exclude-archived          # 跳过归档仓库
trufflehog github --repo=https://github.com/trufflesecurity/test_keys --issue-comments --pr-comments
trufflehog github --org=trufflesecurity --token=<personal-access-token>   # 提升限流额度
```

**5. CI 门禁：只看新提交、发现即失败**

```bash
trufflehog git file://. --since-commit main --branch feature-1 --results=verified,unknown --fail
```

`--fail` 在有结果时返回 **183**；`--fail-on-scan-errors` 则用于"扫描自身出错"时也要非零退出。

**6. 对象存储与容器镜像**

```bash
trufflehog s3 --bucket=<bucket-name> --results=verified,unknown
trufflehog s3 --role-arn=<iam-role-arn>                    # 通过 AssumeRole 扫多个账号
trufflehog s3 --bucket=<name> --include-prefix=infra/ --exclude-prefix=infra/vendor/
trufflehog gcs --project-id=<project-ID> --cloud-environment --results=verified
trufflehog docker --image trufflesecurity/secrets --results=verified
trufflehog docker --image docker://new_image:tag --results=verified
trufflehog docker --image file://path_to_image.tar --results=verified
```

**7. 离线或内网：关掉验证**

```bash
trufflehog filesystem /path --no-verification --json
trufflehog git file://repo --no-verification --results=unverified
```

**8. 调并发与日志，减少 CI 噪音**

```bash
trufflehog git file://repo --concurrency=4 --log-level=1 --json
trufflehog git file://repo --no-update            # CI 里不检查新版本
```

**9. 配置文件（自定义正则检测器 + 多来源）**

```bash
trufflehog --config=config.yaml multi-scan
```

配置里用 `sources:` 定义多个来源，`multi-scan` 会并发扫描它们；自定义正则检测器则对所有子命令生效。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 扫出来的结果比预期少很多，怀疑漏报 | `--results=verified` 只输出"确认有效"的；未验证到的、以及验证时因网络/API 报错而落到 unknown 的都会被过滤掉 | 需要高置信但不愿漏，用 `--results=verified,unknown`（官方 CI 示例就是这个组合）；默认值是 `verified,unverified,unknown` |
| 扫描期间被对方平台限流、报错或变慢 | 验证是**真实 API 调用**；某些操作会向第三方平台发请求并留下记录，未认证访问还会撞上接口限流 | 心里有数再扫：敏感环境先评估影响面；扫 GitHub 加 `--token`；用 `--concurrency` 降并发；必要时 `--no-verification` 或 `--verifier` 指到自建验证端点 |
| 在 CI 里扫完了，进程却仍然成功退出 | 默认**不会**因为发现结果而失败 | 显式加 `--fail`（有结果时退出 183）；若还想在扫描自身报错时失败，再加 `--fail-on-scan-errors` |
| 输出是一堆带颜色的文本，解析不动 | 没有加 `--json` | 加 `--json`；要对接代码扫描平台用 `--sarif`；要在 Actions 里注释用 `--github-actions` |
| 本地 git 仓库扫不到东西 | 本地扫描要在**仓库父目录**执行并用 `file://` 前缀，而不是进到仓库里直接扫当前目录 | 用 `trufflehog git file://test_keys` 这种写法；另外新版会先克隆本地仓库到临时目录再扫（防恶意 git 配置，见 CVE-2025-41390），可用 `--clone-path` 指定路径，仅对可信仓库才考虑 `--trust-local-git-config` 跳过克隆 |
| Docker 里扫不到本地仓库 / 路径不存在 | 容器看不到宿主机文件 | 用 `-v "$PWD:/pwd"` 挂载并把工作目录指进去；用 SSH 拉仓库时还要挂 `-v "$HOME/.ssh:/root/.ssh:ro"`；Windows 的 CMD 与 PowerShell 挂载语法不同 |
| 扫描结果特别多时内存涨得厉害（尤其出 SARIF） | SARIF 需要单个 JSON 文档，结果会**全量缓存在内存**、扫描结束才写出 | 结果量大的场景改用 `--json` 流式输出，或用 `--filter-unverified`、`--results=verified` 收敛结果规模 |
| 老版本的脚本参数突然不认识 | v3 起改为**子命令式**：`trufflehog <source>` 这种老写法不再是入口，现在是 `trufflehog git <uri>` 这类形式 | 按子命令改写；`--json-legacy` 只适用于 git / gitlab / github 三种来源的旧 JSON 格式 |
| 内网机器上跑得非常慢或大量 unknown | 验证要访问外部 API，网络不通时全部走"验证失败"路径 | `--no-verification` 关掉验证，或用 `--verifier` 指向自建端点；接受结果里多为 unverified 的现实 |
| 想在 CI 里锁死版本却总在拉新版本 | 程序默认会检查更新 | 加 `--no-update` |
| `filesystem` 扫出来的东西主体不对 | 该子命令接受多个路径并按位置参数解析 | 路径写全；需要时用 `--include-detectors` / `--exclude-detectors` 限定检测器范围 |
| 只想要"某几类检测器"或排除某几类 | 默认 `--include-detectors="all"` | 用检测器的名字或编号（支持区间/范围）指定；注意 `--exclude-detectors` 的优先级**高于** include 列表 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 核心能力之一：对候选凭证**真实调用对应服务的 API** 做有效性验证；扫描远端 git / GitHub / GitLab / S3 / GCS 也需要联网 |
| 读取文件 | 是 | 扫文件系统、本地 git 仓库、配置文件、Docker 镜像 tar 包 |
| 写入文件 | 视情况 | 默认只输出到 stdout；把 `--json` / `--sarif` 的结果重定向或交给下游即可落盘。本地 git 扫描会先把仓库克隆到临时目录（可用 `--clone-path` 指定位置） |
| 凭证 | 是（视来源） | 扫 GitHub 私有范围需要 `--token`（个人访问令牌）；GitLab 的 `--token=TOKEN` 是必填；CircleCI / TravisCI / Postman 等来源同样需要各平台 token；S3 走本机 AWS 凭证或 `--role-arn`；GCS 用 `--cloud-environment` 走环境凭证 |
| 子进程 / 后台常驻 | 是 | 扫描 git 会调用 `git` 命令，并会克隆仓库到临时目录；程序本身一次性执行完退出，无常驻服务。`--profile` 会在本地开一个 pprof/fgprof 调试端口（默认 18066），非调试场景不要开 |

## 触发场景

- "扫一下这个组织下所有仓库，只给我能用的密钥。"
- "这些疑似 key 里哪些还是活的？"
- "接手了一个老仓库，看看历史里有没有泄漏的凭证。"
- "S3 桶 / Docker 镜像 / 日志里有没有凭证。"
- "CI 里扫到有效凭证就阻断，用退出码判定。"
- "这个 key 到底能访问哪些资源？"
- "内网环境不能联网，怎么跑这个扫描？"

## 能力边界

**覆盖**：

- 分层的凭证处理：发现（Discovery）→ 分类（Classification）→ **主动验证**（Validation）→ 权限分析（Analysis）；AWS 这类检测器会真的调 `GetCallerIdentity` 确认凭证是否有效
- 结果三态语义：`verified`（API 确认有效）、`unverified`（检测到但未确认为有效）、`unknown`（验证因网络/API 错误失败），并可用 `--results` 组合筛选
- 数据源子命令：`git`、`github`、`gitlab`、`filesystem`、`s3`、`gcs`、`docker`、`syslog`、`circleci`、`travisci`、`jenkins`、`elasticsearch`、`postman`、`huggingface`、`stdin`、`multi-scan`、`json-enumerator`
- 输出格式：彩色文本、`--json`、`--json-legacy`、`--sarif`、`--github-actions`
- 检测器范围控制：`--include-detectors` / `--exclude-detectors`（名字或编号，支持范围；exclude 优先级更高）
- 抑制噪音：`--filter-unverified`、`--filter-entropy`（Shannon 熵阈值，从 3.0 起调）
- 自定义能力：`--config` 提供自定义正则检测器（alpha，可选配验证 webhook）与 `multi-scan` 的多来源定义；`--verifier` 可指向自建验证端点
- CI 集成：`--fail`（有结果退出 183）、`--fail-on-scan-errors`、`--github-actions`、SARIF 上传代码扫描平台

**不覆盖**：

- **离线可用性**：默认行为依赖联网验证，隔离环境必须显式关闭验证并接受结果质量下降
- **自动修复**：不轮换、不吊销、不删除、不改写任何凭证或文件
- **无副作用的验证**：验证必然向第三方平台发请求，无法做到"验证但不惊动对方"
- **未列出的数据源**：内部自研系统等需要先自行导出成文件再用 `filesystem`
- **常驻守护 / 实时阻断**：是命令行工具，实时拦截要靠 pre-commit 钩子或 CI 调度
- **公共 API 稳定性承诺**：上游明确说明作为库使用时公共 API 不做稳定性保证；命令行界面相对稳定

## 依赖条件

- 单二进制，Homebrew / Docker 镜像 / 官方安装脚本 / 源码构建（需 Go 工具链）/ Release 二进制均可
- 扫描 git 需要有 `git` 命令；Docker 方式需要 Docker 引擎在运行
- **网络**：默认验证流程需要访问各服务的公开 API；离线环境需 `--no-verification` 或自建 `--verifier`
- 凭证按来源不同：GitHub 用 `--token`，GitLab 的 `--token` 必填，S3 用本机 AWS 凭证或 `--role-arn`，GCS 用 `--cloud-environment`，CI 平台与 Postman 各自需要 token
- 配置文件为 YAML，来源定义写在 `sources:` 下（`multi-scan` 专用），自定义正则检测器对所有子命令生效

## 已知限制

1. 验证过程会真实访问外部服务，可能触发限流、风控或在对方平台留下记录——这是使用前必须评估的前置条件。
2. `--results=verified` 会过滤掉未验证与 unknown 的结果，容易造成"漏报"的错觉。
3. 默认不因发现结果而让进程失败，CI 门禁必须显式加 `--fail`。
4. SARIF 输出会把结果全量缓存在内存中，结果量极大时内存占用显著上升。
5. `--json-legacy` 只支持 git / gitlab / github 三种来源。
6. 自定义正则检测器官方标注为 alpha，行为可能变化。
7. 本地 git 扫描会先克隆到临时目录（安全修复的一部分），会额外消耗磁盘与时间。
8. `--profile` 会在本机开调试端口，非调试场景应保持关闭。

## 自检清单

执行前：

- [ ] `trufflehog --help` 与 `trufflehog <子命令> --help` 确认参数（子命令名与 flag 在不同版本间有变化，尤其 v3 前后的写法差异）
- [ ] 明确本次是否需要验证：要验证就得联网并接受对第三方 API 的调用；离线场景先决定用 `--no-verification` 还是自建 `--verifier`
- [ ] 确认结果过滤口径：默认 `verified,unverified,unknown`，只要高置信常用 `verified,unknown`，只扫有效用 `verified`
- [ ] 扫 GitHub 组织前准备好 `--token`，否则会撞限流
- [ ] 确认结果输出格式：给程序处理加 `--json`，给代码扫描平台用 `--sarif`
- [ ] CI 场景确认已加 `--fail`（否则发现凭证也不会失败）与 `--no-update`
- [ ] 大范围扫描前先评估结果规模，必要时降 `--concurrency` 或用 `--filter-unverified` 收敛

执行后：

- [ ] 检查退出码：`--fail` 命中为 183，`--fail-on-scan-errors` 命中为扫描错误码，别把两者混为一谈
- [ ] 人工复核 `verified` 结果的真实影响面（必要时用 `analyze` 看权限），再决定处置顺序
- [ ] 确认 private key / 云凭证这类高危项优先轮换；**处置顺序是先吊销轮换，再清理来源**
- [ ] 把确认的误报沉淀进配置（检测器范围、熵阈值、`--filter-unverified`、ignore 注释）以减少下次噪音
- [ ] 记录本次扫描的来源、参数与结果统计，便于下次对比

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/trufflesecurity/trufflehog | 上游仓库（安装、子命令、各来源参数与 CI 示例以它为准） |

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
