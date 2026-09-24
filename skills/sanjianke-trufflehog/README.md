# 三剪客 · trufflehog 密钥与凭证扫描 Skill

带主动验证能力的凭证扫描器：扫 git / GitHub / S3 / 文件系统等来源，并真实调用 API 确认凭证是否仍然有效。

---

## 前置条件

- 能装二进制的机器，或本机有 Docker；扫 git 需要有 `git` 命令
- **网络是硬条件**：默认会对候选凭证调用第三方 API 做验证；离线/内网环境必须改用 `--no-verification` 或自建验证端点
- 按数据源准备凭证：GitHub 用个人访问令牌（`--token`），GitLab 的 `--token` 必填，S3 用本机 AWS 凭证或 `--role-arn`，GCS 用 `--cloud-environment`
- 使用前请评估"扫描会对第三方平台产生真实 API 调用"这一影响面

---

## 使用

最短跑通路径：

```bash
brew install trufflehog
trufflehog --version

# 只扫确认有效的凭证
trufflehog git https://github.com/trufflesecurity/test_keys --results=verified

# 本地仓库：在仓库父目录执行
trufflehog git file://test_keys --results=verified,unknown

# 文件系统
trufflehog filesystem /path/to/dir
```

给程序处理时加 `--json`；CI 门禁加 `--fail`（有结果时退出 183）：

```bash
trufflehog git file://. --since-commit main --branch HEAD \
  --results=verified,unknown --fail --json --no-update
```

离线环境：

```bash
trufflehog filesystem /path --no-verification --json
```

`SKILL.md` 里有全部数据源子命令、`--results` 三态语义、对象存储与前缀过滤、配置文件与自定义检测器、以及常见坑对照表。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| 运行时 | 无。单个二进制 |
| 安装方式 | Homebrew / Docker 镜像 / 官方安装脚本（可签名校验）/ 源码构建 / Release 二进制 |
| Go 工具链 | 仅源码构建时需要 |
| git | 扫描 git 来源时需要；本地仓库扫描还会先克隆到临时目录 |
| Docker | 仅在用容器方式运行或扫描镜像时需要 |
| 网络 | **必需（默认）**。验证流程会调用第三方 API；离线需 `--no-verification` 或 `--verifier` |
| 凭证 | 视来源：GitHub 个人访问令牌、GitLab 令牌（必填）、AWS 凭证或 IAM Role、GCS 环境凭证、各 CI 平台 token |

---

## 安全

- 不内嵌任何密钥：本技能只给命令与用法，所有 token 通过参数或环境变量传入
- **验证会产生真实网络副作用**：扫描会对第三方服务发起 API 调用，可能在对方平台留下记录、触发限流或风控。扫生产凭证前先做影响评估
- 扫描结果里含明文凭证（`--json` 输出尤其完整），报告不要提交进仓库、不要贴到公开渠道
- 发现的真实凭证按"先轮换/吊销，再清理来源"的顺序处置；只删文件无法消除历史里的记录
- 传给 `--token` 的令牌权限按最小必要授予，尽量只读；不要在命令行历史里留下长期有效的密钥
- Docker 挂载范围要精确（只挂待扫目录）；用 SSH 时挂载 `~/.ssh` 属于高权限操作，用完及时确认容器已销毁

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`trufflehog`
- 仓库：https://github.com/trufflesecurity/trufflehog

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
