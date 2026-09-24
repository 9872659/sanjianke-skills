# 三剪客 · gitleaks 密钥扫描 Skill

扫代码仓库里的硬编码密钥：翻 git 全历史或扫当前目录，出 json/csv/junit/sarif 报告，用退出码做 CI 门禁。

---

## 前置条件

- 能装二进制的机器，或本机有 Docker
- 扫描对象是本地 git 仓库或本地目录/文件；`git` 模式需要本机 `git` 命令可用
- CI 场景下要求**完整克隆**目标仓库，浅克隆会导致历史扫描失效
- 不需要账号、API Key 或联网（安装阶段除外）

---

## 使用

最短跑通路径：

```bash
brew install gitleaks                 # 或 docker pull ghcr.io/gitleaks/gitleaks:latest
gitleaks version
cd /path/to/repo
gitleaks git -v                       # 扫当前仓库的全部历史
echo $?                               # 1 = 发现泄漏；126 = 参数写错
```

只扫当前文件快照（不看历史）：

```bash
gitleaks dir -v /path/to/dir
```

出报告 + 建立基线，之后只看新增问题：

```bash
gitleaks git --report-path gitleaks-report.json
gitleaks git --baseline-path gitleaks-report.json --report-path findings.json
```

CI 门禁写法（SARIF + 发现即失败）：

```bash
gitleaks git --report-format sarif --report-path results.sarif --exit-code 1 --no-banner
```

`SKILL.md` 里有三种扫描模式的取舍、报告格式与扩展名推断规则、allowlist 与 `.gitleaksignore` 的用法、以及 `detect`/`protect` 到新子命令的完整对照表。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| 运行时 | 无。单个二进制，规则内置，扫描全程离线 |
| 安装方式 | Homebrew / DockerHub 镜像 / GitHub 容器仓库镜像 / 官方 Release 二进制 / 源码构建 |
| Go 工具链 | 仅在从源码构建时需要（`make build`） |
| git | `git` 扫描模式需要本机 `git`，因为底层走 `git log -p` |
| 配置 | 可选。TOML 格式，可经 `--config`、`GITLEAKS_CONFIG` 或 `GITLEAKS_CONFIG_TOML` 提供 |
| 网络 | 仅安装阶段需要；扫描不需要联网，也不做凭证验证 |
| 凭证 | 不需要任何 token 或账号 |

---

## 安全

- 不内嵌任何密钥：本技能只给命令与用法，扫描不需要凭证
- **报告默认包含明文密钥**：`--report-path` 写出的文件不要直接提交进仓库或贴进公开工单，必要时加 `--redact`
- 扫描发现真实泄漏时，处置顺序是先轮换/吊销凭证，再清理仓库历史；只删当前文件无法消除历史里的记录
- `docker run -v ...` 会把宿主机目录挂载进容器，确认挂载范围只覆盖要扫的目录，不要挂根目录
- `.gitleaksignore` 与 allowlist 只是免除告警，不等于风险消失；写 allowlist 时尽量用精确正则或路径，避免把整类规则一起放过

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`gitleaks`
- 仓库：https://github.com/gitleaks/gitleaks

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
