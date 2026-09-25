---
name: sanjianke-agent-control-kit
slug: sanjianke-agent-control-kit
displayName: 三剪客 · 长任务 Agent 控制平面
description: "为长周期 Agent 任务提供可持久、可治理的本地控制平面，跨 harness 续跑。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.2
summary: "把 loopx 的长任务控制平面讲清并落地：目标、待办、闸门、证据、配额五件持久状态，quota should-run 决定这一轮跑不跑，todo claim 定归属，refresh-state 与证据留痕，跨 Codex / Claude Code 等 harness 续跑。含安装接入、每日巡检与故障排查。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 长任务
  - 控制平面
---

# 三剪客 · 长任务 Agent 控制平面

为长周期 Agent 任务提供可持久、可治理的本地控制平面，跨 harness 续跑。

**loopx 不替你干活，它负责「别忘、别乱、别偷偷花算力」。** 真正执行代码、跑命令、改文件的仍然是 Codex、Claude Code 这类 harness；loopx 只是把长任务最容易被上下文冲掉的那部分——目标、下一步待办、等人决策的闸门、已验收的证据、以及还能不能继续跑——搬到项目目录里变成可读可查的持久状态。

这套东西值得上，通常是因为踩到了下面三个坑里的至少一个：

1. **一关窗口就失忆。** 活干到第 3 天，重启之后要把前两天的来龙去脉重新讲一遍，讲漏一处就走偏。
2. **定时唤醒把长任务切碎。** 心跳每几分钟醒一次，每轮只回一句「一切正常」，看着一直在跑，其实没有可交付的推进。
3. **多 Agent 撞车。** 两个 Agent 同时改一个仓库，重复花算力、互相覆盖，出问题时也说不清是谁在什么权限下做的。

把它当一块「给长任务用的看板」来理解最省力：卡片带着身份、授权、证据和续跑指令，移动卡片是被校验的动作（认领、放行、监视、回写），而看板只是投影，真正的权威状态在 loopx 里。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（仅指导） | 本 Skill 自身不发起任何网络请求。只有当你按下面步骤装 loopx 时，才会由你本机的 `pip` 访问 PyPI，或用 `curl` 走 GitHub Pages 归档通道；若你另外接了外部 IM 看板类投影，联网的是 loopx 本身，不是你这条指令 |
| 读取文件 | 否（仅指导） | 本 Skill 不主动读盘。你执行命令时，loopx 会读取项目根下的 `.loopx/registry.json`、`.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`，以及运行根 `~/.codex/loopx/` 下的历史与配额记录 |
| 写入文件 | 否（仅指导） | 本 Skill 不主动写盘。`bootstrap/connect`、`todo add`、`refresh-state`、`quota spend-slot` 这类写操作会改动 `.loopx/`、`goals/` 和全局 registry；凡是破坏性动作都需要显式 `--execute`，不带就是只读预览 |
| 凭证 | 否 | 本包不内嵌、不索取、不转发任何密钥或 token。loopx 也不需要模型 API Key——它驱动的是你本机已经登录好的 harness |
| 子进程 / 后台常驻 | 否（仅指导） | 本 Skill 不拉起任何进程。可选操作会启动常驻服务：`loopx dashboard` 默认监听 `127.0.0.1:8767`，`loopx serve-status` 常用 `--port 8766`；其中托管的 Node 运行时是空闲自退的 |

**本 Skill 不内嵌任何密钥。** 上面标「仅指导」的项，意思是本包只给你命令和判断依据，真正动手的是你在自己机器上执行的 loopx——它申请多少权限，取决于你怎么配、跑哪条子命令。

## 触发场景

- 「这个重构要跨好几天，我不想每次开新会话都从头讲一遍。」
- 「我昨晚关机了，今天怎么让它接着上次那一步继续，而不是重头再来？」
- 「夜里让它自己跑，第二天给我一份能看的记录，同时别让它偷偷把算力烧光。」
- 「两个 Agent 一起动这个仓库，怎么保证不撞车、不重复干同一件事？」
- 「loopx 我装上了，但 `loopx status` 说没连上项目 / 一直说在等，帮我看到底卡哪。」
- 「它一直在跑，可每轮只写一句状态，这算真在推进吗？」

## 快速开始

最小可用路径，四步一条不漏：

```bash
# 1) 装本体（Python 3.11+，Node.js 22.18.0+，推荐 24 LTS）
python3 -m pip install --upgrade loopx
loopx workflow-skills --install        # 把工作流技能交付给当前 host
loopx doctor                           # 装没装好，先看这一条的结论

# 2) 接到你的项目（在项目根执行）
cd /path/to/your-project
loopx connect                          # 建立或接上项目本地状态
loopx status                           # 看：当前目标、卡人的闸门、下一个待办

# 3) 决定这一轮跑不跑
loopx quota should-run --goal-id <goal-id>
```

原生 Windows 用 PowerShell 7，同一条发布通道，不需要 POSIX 兼容层：

```powershell
py -3.11 -m pip install --upgrade loopx
loopx workflow-skills --install
loopx doctor
```

两个容易漏的点：**首次装完要重启你的 agent host**，否则它不会重新加载 loopx 交付的工作流技能；**`.loopx/`、`.codex/goals/`、`goals/**/ACTIVE_GOAL_STATE.md` 要进 `.gitignore`**，那是本机运行状态，不该提交。

项目还没初始化、`connect` 提示缺状态时，走引导路径：

```bash
loopx start-goal --guided --project . --goal-text "你的长周期目标"
```

想先空跑感受一下，不碰真实仓库：

```bash
loopx demo
cd /tmp/loopx-demo
loopx status
loopx quota should-run --goal-id demo-goal
loopx history --goal-id demo-goal
```

`loopx demo` 的正常信号：输出里出现 `ok: True`，`/tmp/loopx-demo` 下生成了项目本地 registry 和活跃目标状态，`status` 里一个用户待办加一个 agent 待办，并且 `quota should-run` 返回 `should_run=True`、`state=eligible`。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 搞懂 loopx 到底是什么、和直接跑 Agent 差在哪 | `references/concepts-and-architecture.md` |
| 判断我这个任务该不该上控制平面 | `references/concepts-and-architecture.md` |
| 装 loopx、把它接到我的项目和我的 harness | `references/install-and-connect.md` |
| 换 harness、升级、回滚、彻底卸掉 | `references/install-and-connect.md` |
| 每天怎么巡检、怎么判断它是在真推进 | `references/long-task-practice-and-troubleshooting.md` |
| 配心跳/定时唤醒、算配额与算力账 | `references/long-task-practice-and-troubleshooting.md` |
| status 不对、连不上、迁移报错、状态想回滚 | `references/long-task-practice-and-troubleshooting.md` |

## 能力边界

**覆盖**：

- 用 loopx 的持久状态（目标 / 待办 / 闸门 / 证据 / 配额）组织跨天、跨会话、跨 harness 的长任务
- 安装、连接、日常巡检、心跳节拍与配额记账的标准命令序列
- 多 Agent 的归属与交接：`register-agent`、`todo claim`、`task-lease`、`review-packet`、`evidence-log`
- 常见故障的定位路径与恢复动作（全局 registry 只读、心跳缺身份、历史索引冲突、升级后各层不同步、状态备份与回滚）
- 把三剪客自己的长流水线挂在控制平面之下：出片、交付、发布这类动作依然由人放行

**不覆盖**：

- **不替代 harness。** loopx 不做模型调用、不生产代码或文案，跑活的始终是 Codex / Claude Code 等宿主
- **不做生产授权。** 不发放凭证、不批准破坏性或生产写入、不代你对外发布
- **不承诺无人自治。** 官方给自己的定位就是本地控制平面，不是自主生产控制器；危险权限与最终所有权始终留给人
- **不含价格、客户信息、内部账号。** 本包是方法+命令规范，不涉及任何商业条款
- **不覆盖 loopx 的源码贡献与二次开发流程**，只讲怎么把它用起来
- **不提供算力或模型 API 的转售、代充、代注册**

## 依赖条件

- **Python 3.11 或更高**（loopx 1.0.3 的 `requires-python` 就是 `>=3.11`）
- **Node.js 22.18.0 或更高**，推荐 24 LTS：loopx 用 Node 跑一个被托管的 TypeScript 运行时，会自动拉起，空闲后自行退出
- 一个受支持的 **agent harness**（Codex App / Codex CLI / Claude Code / Cursor / OpenCode / Pi / ZCode / agy / Kiro CLI / KunlunCode / DeepSeek Harness），或你自己的 runner
- **macOS / Linux 用 POSIX shell；原生 Windows 用 PowerShell 7**，并确保当前 Python 环境的 console script 在 `PATH` 上
- 只有**贡献者路径**才需要 Git（clone 仓库 + 本地安装脚本）；普通使用不必装 Git
- loopx 本体在 `pyproject.toml` 里的运行期第三方依赖是**空**的（`dependencies = []`），装的是一份自带的 Python + 一个托管 Node 运行时

## 已知限制

- **版本口径**：本包按 loopx `1.0.3` 的命令面整理。命令名、字段、默认值会随小版本变化，最终以你装的那份 `loopx commands` 和 `loopx <命令> --help` 为准
- **证据口径**：上游公开的长任务案例（例如 200+ 小时级别的贡献弧、4 天无人值守报告）计的是**挂钟时间**，不是连续模型执行，也不是无人生产结论。本包不复述任何未经验证的收益数字
- **部分能力默认关**：Claude Code 的原生 `/loop` 门控、Explore 图、auto research、Reward Memory 都属于 opt-in 或实验状态，不开就是不开
- **心跳是建议节拍，不是硬门禁**：在多数 host 适配下，quota 起到的是协商性限速作用，靠的是每一轮自觉先查 `quota should-run`，而不是宿主强制执行
- **Windows 桌面预览版**目前要手动更新，CLI 还需单独安装
- **loopx 保的是控制状态，不是聊天记录**：会话上下文本身不在它的保存范围内

## 自检清单

一条条打完，才算真的接上了：

- [ ] `loopx doctor` 结论健康（安装、PATH、发布快照、工作流技能、导入都过）
- [ ] 项目根存在 `.loopx/registry.json`，并且有投影出来的活跃目标状态
- [ ] `loopx status` 同时给出：当前目标、一个**具体**的用户闸门、下一个 agent 待办（只写「等待 owner」不算）
- [ ] `.gitignore` 已包含 `.loopx/`、`.codex/goals/`、`goals/**/ACTIVE_GOAL_STATE.md`
- [ ] `loopx quota should-run --goal-id <goal-id>` 能返回 `should_run` 与 `waiting_on`
- [ ] 真花了算力的自动轮之后补 `quota spend-slot --execute`；静默跳过、预检失败、纯 dry-run 一律不记
- [ ] 多 Agent 场景下每个 Agent 都有 `register-agent` 注册的 id 与 scope，交付前 `todo claim`、验证通过后 `todo update`
- [ ] 凡要对外发布文档或示例，先跑 `loopx check --scan-path ...`

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/concepts-and-architecture.md` | 控制平面的定位、四层边界、状态存储、事件账本与配额模型；含「和直接跑 Agent 的差别」对照表与选型判据 |
| `references/install-and-connect.md` | 三种安装通道、连接与初始化、11 类 harness 的接入命令、升级/回滚/卸载与验收读回 |
| `references/long-task-practice-and-troubleshooting.md` | 每日巡检、节拍信号解读、配额与算力记账、多 Agent 归属，以及 12 类故障的定位与恢复 |

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
