# 安装与接入：从零到 `loopx status` 有内容

> 上游项目：[loopx](https://github.com/huangruiteng/loopx)（Apache-2.0）。命令按 loopx `1.0.3` 整理，跨小版本以 `loopx <命令> --help` 为准。

## 1. 装机前先自检

loopx 本体要求 **Python 3.11+**，并且需要 **Node.js 22.18.0+**（推荐 24 LTS）——Node 跑的是它托管的 TypeScript 运行时，loopx 会自动拉起，空闲后自行退出。

```bash
python3 --version    # 需要 >= 3.11
node --version       # 需要 >= 22.18.0，推荐 24.x LTS
```

原生 Windows 用 PowerShell 7（不是 5.1），并确认 Python 的 console script 在 `PATH` 上：

```powershell
py -3.11 --version
node --version
```

Git **只在贡献者路径**（clone 仓库 + 本地安装脚本）才需要，普通安装不必装。

## 2. 三种安装通道，选一条就好

| 场景 | 通道 | 安装命令 | 后续升级方式 |
|---|---|---|---|
| 常规发布 | Python 包环境 | `python3 -m pip install --upgrade loopx` | `loopx update apply`，或手动 pip 序列 |
| 机器受外部管理，想隔离 CLI | `pipx` | `pipx install loopx` | `pipx upgrade loopx`，然后刷新宿主材料 |
| 没有可用的 Python 包环境 / CLI 已损坏到跑不了自修 | 归档快照 | `curl -fsSL https://huangruiteng.github.io/loopx/install.sh \| bash` | `loopx update check / plan / apply` |

主通道是 PyPI：

```bash
python3 -m pip install --upgrade loopx
loopx workflow-skills --install
loopx doctor
```

原生 Windows PowerShell 7 走同一个 PyPI 发布，不需要 POSIX 兼容层：

```powershell
py -3.11 -m pip install --upgrade loopx
loopx workflow-skills --install
loopx doctor
```

归档通道（只在上面两条都不通顺时用），它会把归档快照、wrapper、man 页和宿主材料一起装上：

```bash
curl -fsSL https://huangruiteng.github.io/loopx/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
```

**关键一条：装完 `pip install` 不等于装完。** 还差 `loopx workflow-skills --install` 这一步，并且**要重启你的 agent host**，否则它加载的还是旧的工作流技能。

## 3. 装完先读两个健康入口

```bash
loopx doctor            # 安装、PATH、发布快照、工作流技能、导入
loopx doctor --deep     # 额外启动托管的 TypeScript 运行时并做深探
```

`--deep` 在首次安装后跑一次比较值：它验证托管运行时能否启动并回答深探。注意**空闲退出的 `stopped` 生命周期是健康的**，不要因为它没在跑就以为装坏了。

`loopx doctor` 在 PyPI 通道下会报告 `install_kind: python_distribution`；当打包技能缺失或陈旧时，它会给出同一套 pip 原生修复序列。同一命令也会检查必需的 TypeScript 运行时是否可用——因为运行时元数据按已安装源码做指纹，升级后的 loopx 会拉起匹配的新进程，而旧进程会在空闲后退出。

顺带看一下 registry 与边界扫描：

```bash
loopx registry
loopx check --scan-root .
```

## 4. 接入项目：先 `connect`，不行再引导

在**项目仓库根目录**执行：

```bash
cd /path/to/your-project
loopx connect
loopx status
```

`connect` 是 `bootstrap` 的别名。需要显式指定目标和目标文档时：

```bash
loopx bootstrap \
  --goal-id your-project-goal \
  --objective "Improve this project through bounded, verified goal segments." \
  --goal-doc GOAL.md
```

这一步会创建或接上：

```text
your-project/
  .loopx/registry.json
  .codex/goals/your-project-goal/ACTIVE_GOAL_STATE.md

~/.codex/loopx/
  goals/<goal-id>/runs/
```

**接入后第一件事是改 `.gitignore`**，这些是本机运行数据：

```gitignore
.loopx/
.codex/goals/
.opencode/goals/
goals/**/ACTIVE_GOAL_STATE.md
```

已初始化但 `connect` 报「state 缺失」时，用引导路径，它会先给预览再落盘：

```bash
loopx start-goal --guided --project . --goal-text "你的长周期目标"
```

loopx 的既定行为是**复用已有状态而不是覆盖**。如果它想覆盖你已有的目标状态，停下来先查清楚原因。

不想碰真实仓库就先空跑：

```bash
loopx demo                              # 在 /tmp/loopx-demo 造一个可丢弃目标
cd /tmp/loopx-demo
loopx status
loopx quota should-run --goal-id demo-goal
loopx history --goal-id demo-goal
```

## 5. 各类 harness 怎么接

| Harness | 推荐起手 | 循环驱动方式 |
|---|---|---|
| Codex App | 让 agent 把项目接到 loopx、跑 `loopx doctor`、保留既有状态并报出当前闸门与下一个待办；之后用 `$loopx <复杂任务>` 或从 `/skills` 里选 `loopx` | Codex App 心跳自动化，按 `quota should-run.scheduler_hint` 刷新 |
| Codex App over SSH | `loopx agent-onboard --agent-type codex-app-ssh --project .` | 用返回的可见 `/goal <task_body>` |
| Codex CLI | 在项目里启动 `codex`，让它连接并诊断，再用 `$loopx <复杂任务>` 或 `/skills` | 可见的 `/goal <task_body>`；默认不做隐藏的无头执行 |
| Claude Code | 安装 opt-in 适配器，然后 `/loopx <任务>` 接 `/loop` | 原生 `/loop`，由 loopx 门控 |
| KunlunCode | `loopx-kunluncode connect --project . --goal-id <id> --agent-id <id>`，加一个有界待办后 `loopx-kunluncode run --project .` | 走 app-server 的原生 Goal Pro；严格验收后才写完成与配额 |
| OpenCode | 装静态命令门面；需要周期性目标时再 opt-in `--with-goal-bridge` | OpenCode 命令门面 + 显式目标桥 |
| Pi | `loopx slash-commands --install --surface pi`，然后在可信会话里 `/loopx <任务>` | 可见的 Pi 目标扩展，由 loopx 配额门控 |
| ZCode | `loopx slash-commands --install --surface zcode`，然后在项目内 ZCode 会话里调 `$loopx` 或 `/loopx <复杂任务>` | 会话自身的轮次循环；每次续跑都从 `quota should-run` 进入 |
| Antigravity CLI（agy） | `loopx slash-commands --install --surface agy`，然后在 `agy` 会话里调 `loopx` 技能 | 会话原生 `/goal` 循环（审计到 `<!-- GOAL_COMPLETE -->`），靠 `schedule` 自唤醒；门控是**建议性节拍**，不是宿主强制 |
| Kiro CLI | `loopx slash-commands --install --surface kiro-cli`，然后在 `kiro-cli` 会话里 `/loopx <复杂任务>` | 会话原生 `/goal --max <N> ...`，受宿主自身迭代预算约束（默认 5）；同样是建议性节拍 |
| DeepSeek Harness（dsh） | 装原生 DSH 插件，选中 `loopx` 技能，然后直接描述任务 | 同会话原生续跑 + GoalBar，或走无头分段；两者都仍受 loopx 授权门控 |
| Cursor / shell / 自研 runner | 用安装器 + `loopx doctor`，手工连接或从你的 runner 里调 loopx | 你的 shell、调度器或 runner |

自研 runner 的路径是：先跑最小示例 `python3 examples/custom-runtime-minimal-cli-turn-smoke.py`，再读完整的嵌入指南。核心 tick 刻意做得很小，只有五条：

```text
loopx quota should-run      # 这个已注册 agent 现在该动吗？
loopx todo claim            # 这一小片归谁？
loopx todo update           # 变了什么？
loopx refresh-state         # 下一轮该看到什么？
loopx quota spend-slot      # 为一段已完成且已验收的工作记账
```

**注意 host 能力声明与授权是两件事。** `--available-capability shell` 只表示宿主观察到具备这种执行支撑，不代表拿到许可；真正的能力在提议状态变更前仍会自己过一遍策略与授权检查。

## 6. 怎么算「接上了」

四条同时成立才算成功：

- `loopx doctor` 通过；
- `.loopx/registry.json` 存在，并且有一个被投影出来的活跃目标状态；
- `loopx status` 能同时显示当前目标、一个具体的用户闸门、下一个 agent 待办；
- 有一个可见的循环驱动器，或者一条明确的激活指令。

外加两条容易忽略的：本机运行状态被 ignore 而不是被提交；心跳/自动化的节拍来自 `quota should-run.scheduler_hint` 而不是随手写死的间隔。

## 7. 升级、回滚、修复

`loopx update` 是**通道感知**的升级入口，三个动作的破坏性递增：

```bash
loopx update check       # 只读：新鲜度与安装归属检查
loopx update plan        # 只读：命令、校验与回滚计划
loopx update apply       # 显式修改本地环境
```

裸跑 `loopx update` 等同于只读的 plan。它会**保持检测到的 pip / pipx / 归档归属，不会擅自换通道**；遇到别的 Python 包管理器拥有安装时，它会报告归属和对应命令并 fail closed，而不是猜一个 pip 变更去执行。对活跃的源码检出，它会报出贡献者安装器，并且**绝不执行 `git pull` 或改写工作树**。

升级不是「包管理器那一步退出成功」就算合格。可能各自独立陈旧的层，要逐层读回：

| 层 | 读回命令 | 成功说明什么 | 不就绪时怎么办 |
|---|---|---|---|
| 安装归属与包 | `loopx update check` | 在不改动的前提下识别当前可执行文件、包归属、新鲜度与下一步 | 按报告出的归属命令做；不要把 pip、pipx、归档、源码检出的升级路径混用 |
| 宿主材料 | `loopx --format json doctor` | `skill_delivery.status` 描述当前宿主用的工作流技能交付状态 | 跑 `loopx workflow-skills --install`；用到门面时再 `loopx slash-commands --install`，然后重启宿主 |
| 托管运行时 | `loopx doctor --deep` | 打包的 TypeScript 运行时能启动并回答深探 | 按 doctor 建议处理，或重装所选的包版本；**不要**另起第二套 Python 规则路径 |
| 已启用扩展 | `loopx extension doctor --all-enabled --execute --format json` | 每个启用扩展都有当前运行时身份并通过就绪检查 | 修复被点名的 provider 或扩展后重跑它的 doctor；失败的 provider 保持关闭 |

回滚的做法是装回上一个版本再刷新各层：

```bash
python3 -m pip install "loopx==<previous-version>"
loopx workflow-skills --install
loopx slash-commands --install
loopx doctor
```

归档通道的 `apply` 会保留原子发布指针、doctor 校验、扩展读回、托管服务重启和一等公民的快照回滚；它的安装归属投影会防止这条路径与正在使用的 PyPI 可执行文件混在一起。

还有一个常见误判：**合进 `main` 的代码不等于你装的发布里已生效**。归档维护者可以用 `loopx update check --ref main` 看 `runtime_activation_qualification`；普通 pip / pipx 用户应留在 tagged 包通道等对应发布，不要把已安装的分发改成 `main`。

## 8. 卸载

顺序是先摘宿主材料，再卸 Python 包：

```bash
loopx slash-commands --uninstall
loopx workflow-skills --uninstall
python3 -m pip uninstall loopx
```

两个宿主卸载器都会**保留安装后被改动过的同名文件**。项目本地的 `.loopx/`、`.codex/goals/`、证据与运行状态**不会**被包卸载删掉——要清就自己确认后清。

## 9. 接入阶段常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `loopx: command not found` | console script 不在 `PATH`（macOS/Linux 常见于 `~/.local/bin`） | `export PATH="$HOME/.local/bin:$PATH"`，或改用 pipx 通道后重开 shell |
| 升级后行为还是老的 | 只做了 `pip install`，宿主材料没刷新 | `loopx workflow-skills --install` + `loopx slash-commands --install`，然后**重启 host** |
| `loopx doctor --deep` 说运行时不行 | Node 版本低于 22.18.0，或包版本与运行时指纹不匹配 | 升到 Node 24 LTS；按 doctor 建议重装当前版本，别另起第二套规则路径 |
| `update plan` 拒绝执行 | 安装归属不是 pip（例如 pipx、归档、源码检出） | 按它报告的归属命令升级，不要混通道 |
| 心跳/自动化静默失败 | 未注册 agent 身份，或老 registry 缺 `coordination.registered_agents` | 先 `loopx register-agent ... --execute`，再带 `--agent-id` 生成心跳提示词 |
| 全局 registry 写不进去 | 运行根 `~/.codex/loopx/registry.global.json` 不可写 | 修共享运行根权限，或在能写的宿主上重跑；只有在明确要本地专用连接时才用 `--no-global-sync` |
| 发布文档/示例前被拦 | 公私边界扫描命中私有材料 | 按命中项清掉真实路径、任务 id、生产日志、凭证后再扫描 |
