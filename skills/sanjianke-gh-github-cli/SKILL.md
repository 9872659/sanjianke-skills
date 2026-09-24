---
name: sanjianke-gh-github-cli
slug: sanjianke-gh-github-cli
displayName: 三剪客 · GitHub 命令行客户端
description: "gh (GitHub CLI)：把 issue、PR、Actions 日志、Release、API 查询搬到终端，登录一次之后一条命令搞定，不用在浏览器和命令行之间来回切。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "gh (GitHub CLI) 的安装、登录方式与高频命令：开 PR、看 CI 失败日志、建 issue、发 Release、用 gh api 顶替手写分页请求，以及无头环境认证、凭据落盘、--json 字段随版本变化等常见坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
  - GitHub
  - DevOps
---

# 三剪客 · GitHub 命令行客户端

一天里最碎的活不是写代码，是围着代码转的那些动作：把分支推上去开个 PR、看一眼 CI 为什么红、给 issue 补个标签、把 Release 的附件传上去、查一下这个仓库还有多少待评审的请求。这些事在浏览器里点四五层菜单，`gh` 里就是一条命令，而且输出能直接喂进管道。

`gh` 不是 git 的替代品：git 管本地仓库和提交图，`gh` 管 GitHub 这一侧的协作对象（issue / PR / Actions / Release / 仓库设置）。两者是配合关系，真正省时间的用法是「git 推完，紧接着 gh 开单」。

**上游项目**：`gh (GitHub CLI)`　**仓库**：https://github.com/cli/cli

## 什么时候用 / 不用

**用它**：

- "这条分支推上去了，帮我开个 PR 并写清改了什么。"——`gh pr create --title ... --body ...`，成功后直接打印 PR 的 URL。
- "CI 跑红了，把失败的 job 日志拉下来看看。"——`gh run list` 找到运行，再 `gh run view <id> --log-failed` 只取失败步骤的日志。
- "把这个仓库的 issue 全拉出来做统计。"——`gh issue list --json number,title,labels --jq '...'`，自己拼脚本，不依赖浏览器。
- "把某个仓库克隆下来。"——`gh repo clone owner/repo`，走 gh 自己的认证通道，不用先配 SSH key。
- "要调一个 GitHub 接口，但不想自己处理认证头和翻页。"——`gh api repos/{owner}/{repo}/issues --paginate`。
- "把打好的安装包传到 Release 上。"——`gh release create <tag> ./dist/*.tgz`，tag 一起建好。
- "手动触发一次 workflow，然后盯着它跑完。"——`gh workflow run <name>` + `gh run watch`。

**不要用它**：

- **要改文件内容、做代码检索或复杂数据加工**——`gh` 只负责跟 GitHub 对话，落地的文本处理交给 `jq`、`grep` 和脚本；拿它当数据处理工具会很别扭。
- **要 git 本身的能力**（rebase、cherry-pick、改提交历史、管理 submodule、stash）——`gh` 里没有这些。
- **托管平台不是 GitHub**（GitLab、Gitea、Bitbucket）——`--hostname` 只覆盖 GitHub Enterprise Server，对别的平台用不了。
- **纯无头、又拿不到 token 的环境**——`gh auth login` 默认要开浏览器或在终端里粘贴一次性码，这种环境下第一步就过不去。
- **把高风险操作交给无人值守的自动流程**——`gh pr merge`、`gh repo delete`、`gh secret set` 影响面大；`gh auth token` 更是直接明文打印令牌。
- **指望默认输出能被稳定解析**——默认是给人看的行式文本，字段措辞随版本变；要解析一定走 `--json`。

## 安装

官方发行包覆盖 Windows / macOS / Linux，各平台还有各自的包管理器入口。下面是最常见的一批；具体可用版本以官方 Releases 页面为准。

```bash
# Windows
winget install --id GitHub.cli
scoop install gh
choco install gh

# macOS
brew install gh

# Debian / Ubuntu：按官方文档配好 keyring 与 sources 文件后再装
sudo apt update && sudo apt install gh

# Fedora / RHEL
sudo dnf install gh

# Arch
sudo pacman -S github-cli

# 免 root 的兜底
conda install gh --channel conda-forge
```

装完先确认版本，再登录：

```bash
gh --version
gh auth login          # 交互式：选 host、选 HTTPS / SSH 协议、按提示授权
gh auth status         # 看当前账号、所用 host、token 的 scope
```

## 常用操作

**1. 登录与账号切换（配一次，后面免密）**

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth login --with-token < mytoken.txt      # 无头环境：从标准输入读 token
gh auth status                                 # 登录状态与 token 存放位置
gh auth refresh -s project                     # 追加 OAuth scope（如 PR 关联 Project）
gh auth switch                                 # 多账号之间切换
```

`--with-token` 读到的 token 至少要具备 `repo`、`read:org`、`gist` 三个 scope。细粒度 token 官方建议改用环境变量 `GH_TOKEN`，不要塞给 `--with-token`。

**2. 开 PR / 看 PR / 检出别人的 PR**

```bash
gh pr create --title "修复登录态丢失" --body "复现步骤见 #123" --base main
gh pr create --fill                      # 标题与正文直接从提交信息生成
gh pr create --draft --reviewer monalisa,hubot

gh pr list --state open --limit 50
gh pr view 321 --comments
gh pr diff 321
gh pr checkout 321                       # 把别人的 PR 分支拉到本地
gh pr checks 321                         # 这条 PR 的检查项状态
gh pr merge 321 --squash --delete-branch
```

**3. issue 的建、查、关**

```bash
gh issue create --title "导出 CSV 缺表头" --body "环境：Windows 11" --label bug
gh issue list --state open --assignee @me
gh issue view 42 --comments
gh issue close 42 --comment "已在 v1.2 修复"
```

**4. 看 Actions 运行与失败日志**

```bash
gh run list --limit 20
gh run view <run-id>
gh run view <run-id> --log-failed        # 只看失败步骤的日志
gh run watch <run-id>                    # 盯着这次运行直到结束
gh run rerun <run-id> --failed           # 只重跑失败的 job
gh workflow run deploy.yml --ref main    # 手动触发 workflow
```

**5. 发 Release 并挂附件**

```bash
gh release create v1.2.3 --generate-notes ./dist/*.tgz
gh release create v1.2.3 -F release-notes.md --verify-tag
gh release create v1.2.3 './dist/app.zip#Windows 安装包'   # # 后面是附件显示名
gh release list
gh release download v1.2.3 --pattern '*.tgz'
```

`--generate-notes` 走 GitHub 的 Release Notes API 自动生成说明，配 `--notes-start-tag` 可指定从哪个 tag 开始算。

**6. 用 `--json` 把输出变成可解析数据**

```bash
gh pr list --json number,title,author
gh pr list --json author --jq '.[].author.login'
gh issue list --json number,title,labels --jq 'map(select((.labels|length)>0))'
gh issue list --json title,url --template '{{range .}}{{hyperlink .url .title}}{{"\n"}}{{end}}'
```

`--json` 后面必须跟字段名列表；想知道某个子命令支持哪些字段，就先不带参数写 `--json`，gh 会把候选列出来。只有用了 `--json` 才能接 `--jq` 或 `--template`。`--jq` 是 jq 语法，但**本机不需要装 jq 命令**。

**7. 直接打 REST / GraphQL API**

```bash
gh api repos/cli/cli
gh api repos/{owner}/{repo}/issues --paginate          # 自动翻页
gh api --method POST repos/{owner}/{repo}/issues -f title="新问题" -f body="详情"
gh api graphql -f query='{ viewer { login } }'
gh api repos/cli/cli --jq '.stargazers_count'
```

`{owner}`、`{repo}` 这类占位符会按当前仓库自动替换；自动翻页必须显式加 `--paginate`。

**8. 其它高频杂活**

```bash
gh repo clone cli/cli
gh repo view --web                 # 在当前仓库打开浏览器
gh repo fork --clone
gh search repos "cli" --language=go --limit 20
gh search code "http.NewRequest" --owner=cli
gh gist create notes.md --public
gh extension install owner/gh-something && gh extension list
gh config set editor "code --wait"
gh completion -s bash              # 生成补全脚本
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 脚本或 CI 里跑 gh 卡住不动直到超时 | gh 默认是交互式的：猜不到标题就问、不知道往哪推就问、`gh run watch` 会一直等 | 把所有输入显式给全：`--title` / `--body` / `--base` / `--head`，或用 `--fill`；CI 里避开需要终端交互的子命令，`gh run watch` 换成 `gh run view` |
| `gh auth login` 说找不到浏览器，或在一个没有终端的环境里失败 | 默认走 web 浏览器授权流程，无头环境没有可控浏览器 | 改用 `gh auth login --with-token < token.txt`，或直接设置环境变量 `GH_TOKEN`；GitHub Actions 里加 `GH_TOKEN: ${{ github.token }}` |
| `gh auth status` 提示 token 存在明文文件里 | 系统没有可用的凭据存储时，gh 会退回把 token 写进纯文本文件 | 这是官方说明过的降级行为，不是 bug。装好平台凭据存储，或显式接受明文（`--insecure-storage`）并自行保护该文件；共享机器上尤其注意 |
| token 的 scope 不够，PR 关联 Project 之类的操作报权限错误 | 交互式登录默认拿到的 scope 不含 `project` | `gh auth refresh -s project` 追加；用 `--with-token` 时确保 token 至少含 `repo`、`read:org`、`gist` |
| `--json` 报「未知字段」，或同一命令换台机器就报错 | 不同版本的 gh 支持的 JSON 字段集合不一样 | 先跑不带字段名的 `--json` 让 gh 列出当前版本支持的字段，再照着写；升级或降级 gh 后重新核对 |
| 解析 gh 输出的脚本过一阵就崩 | 默认输出是给人看的文本，列宽、措辞、相对时间描述都可能随版本变 | 解析一律走 `--json`（必要时加 `--jq`），不要用正则去切默认表格 |
| 明明在仓库目录里，却报「not a git repository」或反问是哪个仓库 | 一部分子命令必须能解析出仓库上下文；目录不在仓库里、或仓库没有 remote 时会失败 | 显式指定 `-R owner/repo`（如 `gh pr list -R cli/cli`），或先 `cd` 进一个有 remote 的仓库 |
| Enterprise 上登录成功了，命令却报 404 | 默认 hostname 是 github.com | `gh auth login --hostname <企业域名>`；必要时用环境变量 `GH_HOST` 指定 host，`-R HOST/OWNER/REPO` 指定仓库 |
| 企业网络或自签证书环境下报 TLS 错误 | gh 走系统证书链 | 在本机/系统层面修好根证书，不要随手关校验 |
| `gh pr create` 报分支还没推送，或反问要不要 fork | 当前分支在远端没有对应分支 | 先 `git push -u origin <branch>`，或让它交互处理；想完全跳过推送与 fork 行为就用 `--head` 明确指定 |
| `gh release create` 建出来的 tag 不是我想要的位置 | 远端没有该 tag 时，gh 会从默认分支最新状态自动创建 tag | 要精确控制，就先本地建好并推送 tag 再执行；或加 `--verify-tag`，让它在 tag 不存在时直接失败 |
| 附件部分上传失败，但 Release 已经建出来了 | gh 是分步执行的：建（草稿）→ 传附件 → 发布，附件失败不回滚 | 看到命令以非零状态退出却打印了 URL 时别当成完全失败；用 `gh release upload` 把缺的附件补上 |
| `gh auth token` 的输出出现在日志里 | 这条命令本来就是打印明文令牌的 | 绝不要把它写进 CI 日志、终端录屏或提交记录；需要令牌时用环境变量而不是回显命令 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 全部功能都要访问 GitHub API（`api.github.com` 或指定的企业 host），离线不可用 |
| 读取文件 | 是 | 读本地 git 仓库状态（分支、remote、提交）以推断上下文；`--body-file` / `-F` / `--attach` 会读指定文件 |
| 写入文件 | 是 | `gh release download`、`gh run download`、`gh gist clone` 会往磁盘写文件；`gh auth login` 会写配置与凭据文件 |
| 凭证 | 是 | 核心依赖。token 由 `gh auth login` 获取，优先存进系统凭据存储，取不到时退回明文本地文件；也可用 `GH_TOKEN` / `GITHUB_TOKEN` 环境变量替代 |
| 子进程 / 后台常驻 | 是 | 背后会调用 `git`（clone、fetch、push）和系统浏览器；`gh run watch` 是长驻轮询，不常驻服务 |
| 修改远端状态 | 是 | 建/改/关 issue 与 PR、合并 PR、建 Release、写 secret 与 variable、触发 workflow——都会真实改变 GitHub 上的内容 |

## 触发场景

- "帮我把这个分支开成 PR。"
- "CI 红了，把失败原因拉出来。"
- "这个仓库现在有多少 open 的 issue / PR？"
- "把 release 的安装包传上去。"
- "把这个仓库克隆下来，再 fork 一份。"
- "我不想自己写分页，直接用命令行调 GitHub 接口。"
- "刚才那次 workflow，重跑一下失败的 job。"

## 能力边界

**覆盖**：

- 认证：`gh auth`（login / logout / status / switch / refresh / setup-git / token），支持 github.com 与 GitHub Enterprise Server
- 协作对象：issue、PR、discussion、label、project 的建查改关，以及评论、评审、合并
- Actions：`gh run`（list / view / watch / rerun / cancel / download）、`gh workflow`、`gh cache`、`gh secret`、`gh variable`
- 发布：`gh release`（create / upload / download / edit / delete / verify）、`gh attestation`
- 仓库操作：`gh repo`（clone / create / fork / view / edit / archive / sync / set-default）、`gh gist`、`gh ssh-key`、`gh gpg-key`、`gh codespace`
- 数据出口：`gh search`（repos / code / issues / prs / commits）与 `gh api`（REST + GraphQL），统一支持 `--json` / `--jq` / `--template`
- 扩展性：`gh alias` 自定义别名、`gh extension` 安装第三方扩展、`gh completion` 生成补全

**不覆盖**：

- 任何 git 自身的仓库操作（rebase、cherry-pick、改历史、submodule、stash 管理）
- 非 GitHub 系的托管平台（GitLab、Gitea、Bitbucket 等）
- 代码编辑、静态检查、构建与测试本身——gh 只负责触发和取回结果
- 通用文本与数据加工：JSON 复杂变换交给 jq，文本处理交给 grep / sed / awk
- 图形界面能力：`--web` 只是把页面丢给浏览器，gh 本身不做渲染
- 无凭据情况下的任何远端操作

## 依赖条件

- 一个 GitHub 账号；操作私有仓库时账号需有对应权限
- 通过 `gh auth login` 获取的 token，或环境变量 `GH_TOKEN` / `GITHUB_TOKEN`
- 需要本地仓库上下文的子命令要求系统装有 `git`，且当前目录在一个 git 仓库内（或能通过 `-R` 指定仓库）
- 能访问 GitHub API 的网络；企业环境要放行对应 host
- 官方提供 Windows / macOS / Linux 各架构的单文件发行包；用包管理器安装时版本以该包管理器为准
- 环境变量与认证的完整清单见 `gh help environment`

## 已知限制

1. 默认输出面向人阅读，格式随版本演进；稳定解析必须用 `--json`。
2. `--json` 的可用字段由当前 gh 版本决定，不同版本不一致。
3. 无头环境无法完成默认的浏览器登录流程，必须预置 token。
4. 系统缺少凭据存储时，token 会退化为明文文件保存。
5. `--head` 的 `<user>:<branch>` 语法目前不支持把组织名当 `<user>`（官方已知问题）。
6. Release 附件是分批上传的，部分失败不会回滚已创建的 Release。
7. 各子命令的参数名与可用性以本机 `gh <子命令> --help` 与官方命令参考为准。

## 自检清单

执行前：

- [ ] `gh auth status` 确认登录的账号、host 与 token scope 满足这次操作
- [ ] 确认当前目录是不是目标仓库；不是就用 `-R owner/repo` 明确指定
- [ ] 判断这条命令会不会弹交互提示：要在脚本里跑，先把 `--title` / `--body` / `--base` 之类的输入补齐
- [ ] 想用 `--json` 时，先不带字段名跑一次，确认当前版本支持这些字段
- [ ] 涉及写远端（合并 PR、建 Release、写 secret、删仓库）时，先确认分支、tag、目标仓库没搞错
- [ ] 命令里不要出现明文 token，改用环境变量或凭据存储

执行后：

- [ ] 看退出码：`gh release` 可能出现「整体非零但对象已创建」的情况，退出码要结合输出一起判断
- [ ] 会写文件的命令（`release download`、`run download`）核对目标目录里文件的完整性
- [ ] 会改变远端不可逆状态的命令（merge、delete、release publish）回网页确认一次结果
- [ ] 终端里出现过 `gh auth token` 输出的，清理日志与录屏记录

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/cli/cli | 上游仓库（安装与完整文档以它为准） |
| https://cli.github.com/manual | 官方命令参考：每个子命令的完整参数、示例与格式化说明 |

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
