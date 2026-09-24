# 三剪客 · GitHub 命令行客户端 Skill

gh (GitHub CLI)：把 issue、PR、Actions 日志、Release 与 API 查询搬到终端，登录一次之后一条命令搞定，不用在浏览器和命令行之间来回切

---

## 前置条件

- 一个 GitHub 账号（或 GitHub Enterprise Server 上的账号）
- 系统里装有 `git`——gh 的仓库类子命令依赖它推断本地上下文
- 能访问 GitHub API 的网络；企业环境需要放行对应 host
- 首次使用必须先做一次认证，二选一：
  - 交互式：`gh auth login`（默认走浏览器授权，token 存进系统凭据存储）
  - 无头环境：`gh auth login --with-token < token.txt`，或直接设置环境变量 `GH_TOKEN`
- 用 `--with-token` 时，token 至少要有 `repo`、`read:org`、`gist` 三个 scope

---

## 使用

最短跑通路径：

```bash
gh --version                 # 1. 确认装好了
gh auth login                # 2. 交互式登录，按提示选 host / 协议 / 授权方式
gh auth status               # 3. 确认账号、host、token scope
gh repo clone cli/cli        # 4. 找一个仓库练手
cd cli && gh pr list         # 5. 在仓库里列出 open 的 PR
```

日常最高频的四条：

```bash
gh pr create --fill                       # 用提交信息生成 PR 标题与正文
gh pr view 321 --comments                 # 看 PR 详情与评论
gh run list --limit 20                    # 最近 20 次 Actions 运行
gh run view <run-id> --log-failed         # 只取失败步骤的日志
```

要写脚本的话，别解析默认输出，一律用 JSON：

```bash
gh issue list --limit 100 --json number,title,labels,state \
  --jq '.[] | select((.labels|length) > 0) | "\(.number)\t\(.title)"'
```

排错顺序：命令找不到 → 看 PATH 与安装方式；报未认证 → `gh auth status`；报权限不足 → `gh auth refresh -s <scope>`；报仓库上下文缺失 → 用 `-R owner/repo` 明确指定。

---

## 依赖

- **运行环境**：官方发行包覆盖 Windows / macOS / Linux（含各主流架构），是单文件可执行程序，不需要 Node / Python 之类的运行时
- **必需的外部程序**：`git`——`gh repo clone`、`gh pr checkout` 等命令会调用它
- **可选的外部程序**：系统浏览器（`--web`、交互式登录用）；不需要单独安装 `jq`，`--jq` 是 gh 内置的格式化能力
- **配置位置**：`gh config list` 查看当前生效的配置；`gh config set <key> <value>` 修改（如 `editor`、`git_protocol`）
- **网络**：所有功能依赖 GitHub API，无可用的离线模式
- **第三方扩展**：`gh extension install owner/name` 安装的扩展需要自行评估来源可信度

---

## 安全

- 不内嵌任何密钥：本 Skill 不包含任何账号、token 或凭据
- **token 是明文敏感信息**：`gh auth token` 会直接把令牌打印到标准输出，绝不要写进 CI 日志、录屏或提交记录
- **凭据落盘风险**：系统没有可用凭据存储时，gh 会把 token 写进纯文本文件（`gh auth status` 会提示该文件位置）；共享机器上要么装好凭据存储，要么清楚接受这个风险
- **明文保存只是显式选择**：`--insecure-storage` 是主动要求明文存储，不是默认行为，用了要自己负责保护该文件
- **高危命令会真实改动远端**：`gh pr merge`、`gh repo delete`、`gh repo edit`、`gh secret set`、`gh release delete`、`gh workflow run` 都直接作用于线上仓库，执行前确认目标仓库、分支、tag
- **无人值守场景**：只授予完成任务所需的最小 scope，优先用细粒度 token 并走 `GH_TOKEN` 环境变量，而不是把宽权限 token 落盘
- **第三方扩展**：`gh extension install` 安装的是第三方代码，gh 不做安全审计，装之前先确认来源
- **企业网络**：遇到 TLS 证书错误请在系统层面修好根证书链，不要用关闭校验的方式绕过

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`gh (GitHub CLI)`
- 仓库：https://github.com/cli/cli

---

## 许可证

MIT，见 `LICENSE.md`。

---

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
