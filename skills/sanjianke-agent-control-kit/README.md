# 三剪客 · 长任务 Agent 控制平面 Skill

为长周期 Agent 任务提供可持久、可治理的本地控制平面，跨 harness 续跑

---

## 前置条件

- **Python 3.11+**（loopx 1.0.3 声明 `requires-python >=3.11`）
- **Node.js 22.18.0+**，推荐 24 LTS：loopx 用 Node 跑一个被托管的 TypeScript 运行时，会自动拉起并在空闲后自行退出
- 一个受支持的 agent harness：Codex App / Codex CLI / Claude Code / Cursor / OpenCode / Pi / ZCode / agy / Kiro CLI / KunlunCode / DeepSeek Harness，或你自己的 runner
- macOS / Linux 用 POSIX shell；原生 Windows 用 PowerShell 7，并确保 Python 的 console script 在 `PATH` 上
- 只有走贡献者路径（clone 仓库 + 本地安装脚本）才需要 Git

---

## 使用

```bash
python3 -m pip install --upgrade loopx
loopx workflow-skills --install
loopx doctor

cd /path/to/your-project
loopx connect
loopx status
loopx quota should-run --goal-id <goal-id>
```

装完先重启 agent host，它才会重新加载 loopx 交付的工作流技能；并把 `.loopx/`、`.codex/goals/`、`goals/**/ACTIVE_GOAL_STATE.md` 写进 `.gitignore`。

正文分三份：

| 文件 | 用途 |
|---|---|
| `SKILL.md` | 入口：权限与用途、触发场景、快速开始、路由、能力边界、自检清单 |
| `references/concepts-and-architecture.md` | 概念与架构：四层边界、八个状态存储、事件账本、配额口径、选型判据 |
| `references/install-and-connect.md` | 安装与接入：三条安装通道、项目连接、11 类 harness、升级回滚卸载 |
| `references/long-task-practice-and-troubleshooting.md` | 长任务实践与排错：每日巡检、节拍信号、记账规则、12 类故障 |

---

## 依赖

- 运行时：Python 3.11+ 与 Node.js 22.18.0+（推荐 24 LTS）
- loopx 本体在 `pyproject.toml` 中的运行期第三方依赖为**空**（`dependencies = []`）
- 无需任何模型 API Key：loopx 驱动的是你本机已登录的 harness
- 本 Skill 自身**零依赖**：纯文档，不安装任何包，不写任何脚本

---

## 安全

- 不内嵌任何密钥
- 本 Skill 自身不联网、不读写文件、不启动进程；所有动作都是你在本机手动执行 loopx 时的行为
- 带破坏性的 loopx 命令需要显式 `--execute`，不带就是只读预览（如 `backup-state`、`configure-goal`）
- 绝不提交 `.loopx/`、`.codex/goals/`、`.opencode/goals/`、活跃的 `ACTIVE_GOAL_STATE.md`、原始基准 trace、凭证或私有日志
- 状态归档与清单属于私有恢复材料，不要提交、不要外发
- 危险权限、发布动作、生产写入与最终所有权始终留给人，loopx 不代你授权

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：loopx（Apache-2.0）

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
