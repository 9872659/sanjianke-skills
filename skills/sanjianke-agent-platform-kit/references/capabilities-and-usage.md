# 能力与用法

覆盖范围：装好之后，怎么把它的能力用起来——体系结构、工具面与档位、权限与沙箱、会话与多 Agent、记忆与自动化、通道消息、媒体、技能与插件，以及一份 CLI 速查表。

---

## 1. 体系结构：先认清五个角色

| 角色 | 是什么 | 关键事实 |
|---|---|---|
| **Gateway** | 常驻本机的控制面 | 一台主机只有一个，是唯一持有某消息账号会话的地方；默认 WebSocket 监听 `127.0.0.1:18789`；负责校验入站帧、派发事件（`agent`、`chat`、`presence`、`health`、`heartbeat`、`cron`） |
| **客户端** | CLI、TUI、浏览器控制台、自动化 | 每个客户端一条 WS 连接；发 `health`、`status`、`send`、`agent`、`system-presence` 等请求，订阅 `tick`、`agent`、`presence`、`shutdown` 等事件 |
| **节点** | macOS / iOS / Android / 无头设备 | 连同一个 WS 服务但声明 `role: node` 与明确的 caps / commands / permissions；按设备配对；暴露 `camera.*`、`screen.record`、`location.get`，macOS 还有 `canvas.*` |
| **通道** | 消息出入口 | 把助手带到你已经在用的聊天软件里；核心 4 条 + 官方插件 23 条 |
| **工具 / 技能 / 插件** | 助手能做什么 | 工具是它可调用的动作，技能是教它怎么做的指令包，插件是给它加新能力 |

一次请求的链路（单客户端）：

```
connect(req)  →  hello-ok（含 presence + health 快照）
              →  event: presence / tick
agent(req)    →  res: accepted {runId}
              →  event: agent（流式）
              →  res: final {runId, status, summary}
```

三条不变量值得记：握手是强制的（首帧不是 JSON `connect` 直接硬关）；事件不重放（客户端要自己按缺口刷新）；副作用方法（`send`、`agent`）要求带幂等键，服务端只保留短期去重缓存。

---

## 2. 工具面

### 2.1 分类概览

| 类别 | 什么时候用 | 代表工具 |
|---|---|---|
| 运行时 | 跑命令、管进程、用共享操作终端、跑 provider 侧 Python | `exec`、`process`、`terminal`、`code_execution` |
| 文件 | 读写 workspace 文件 | `read`、`write`、`edit`、`apply_patch` |
| 人机确认 | 停下来等一个由你做的结构化决定，或在不看到明文的前提下取凭证 | `ask_user`、`secrets` |
| 网页 | 搜索、抓可读正文、搜 X 上的帖子 | `web_search`、`web_fetch`、`x_search` |
| 浏览器 | 操作一个浏览器会话 | `browser` |
| 界面 | 编排已连接控制台的面板与导航 | `screen` |
| 会话进度 | 更新父会话的持久进度卡（子代理不可用） | `progress_card` |
| 媒体 | 图像 / 视频 / 音乐生成、转写、TTS | 图像与音视频生成工具、语音相关工具 |
| 会话与协作 | 子代理、跨代理会话、任务编排 | 子代理工具、`agent send`、ACP、swarm、code mode |

**模型只能看到「活下来」的工具**：要同时通过当前 profile、允许/拒绝策略、provider 限制、沙箱状态、通道权限和插件可用性这几道筛子。

### 2.2 工具档位（`tools.profile`）

| 档位 | 含义 |
|---|---|
| `minimal` | 只放行 `session_status`，几乎什么都不给 |
| `messaging` | 窄档，给纯聊天场景 |
| `coding` | 新本地配置的默认档，放行仓库、文件、shell 与运行时工作 |
| `full` | 去掉档位限制，只建议给受信、由操作者控制的 agent |

每个 agent 还能用 `agents.entries.*.tools` 覆盖根档位，做更窄或更宽的调整。

### 2.3 浏览器自动化

```bash
openclaw browser status
openclaw browser start|stop
openclaw browser tabs|open|focus|close
openclaw browser navigate|screenshot|snapshot
openclaw browser click|type|press|hover|drag|select|fill|upload
openclaw browser wait|evaluate|console|pdf
openclaw browser profiles|create-profile|delete-profile|reset-profile
```

实战要点：优先用 `snapshot` 拿结构而不是 `screenshot` 拿图，模型更省 token 也更准；`evaluate` 是逃生口，不是常规手段。WSL2 / Windows 远程 CDP、Linux 无头环境这几类组合有各自的坑，遇到再按平台查专项排错；要长期稳定就跑带浏览器的容器镜像变体。

---

## 3. 执行、审批与沙箱

这三件事互相独立，排错时不要混为一谈：**工具策略**决定某个工具在不在；**沙箱**决定工具在哪里跑；**elevated** 是显式逃逸口，把 `exec` 拿到沙箱外执行（默认 `gateway`，exec 目标为节点时是 `node`）。

### 3.1 审批

```bash
openclaw approvals get
openclaw approvals set
openclaw approvals allowlist add|remove
openclaw exec-policy show
openclaw exec-policy preset
openclaw exec-policy set
```

- 需要审批的命令在审查前会绑定每个已解析段的可执行文件身份，启动前再查一次：受保护的可执行文件只用解析后的真实路径身份，可写的还用内容哈希。
- POSIX 登录 shell 或交互 shell 包装器会跳过自动审查，绑定成功时也要求人工批准。
- 会话级一次性收紧用 `/exec security=... ask=...`，它只作用于该条消息，且**只能收紧**一个显式会话模式。

### 3.2 会话权限模式（四档）

| 模式 | 文件系统访问 | exec 升级审查者 |
|---|---|---|
| `read-only` | 只能读 `sessionRoot` 下；受管的写入类工具直接不出现 | 无；`exec` 一律拒绝 |
| `guarded` | 可在 `sessionRoot` 下读写 | 先走白名单快速通道，之后由人审 |
| `workspace` | 可在 `sessionRoot` 下读写 | 由 LLM 审查：放行、拒绝，或转人工 |
| `full` | 文件系统不受限 | 无 |

- `full` 需要 `operator.admin`，其余三档需要 `operator.write`。
- `workspace` 模式下审查者拒绝会直接把理由返回给 agent，**不产生人工审批卡**；agent 必须换更安全的做法或来问你，不许绕过。连续三次 Gateway 侧拒绝会升级到人工。
- 权限是会话级的，可在控制台输入框的 **Permissions** 菜单里改；改动会取消旧权限下的待批请求（是取消，不是批准），也不会回滚已经完成的写入或已启动的进程。
- 已启动的 CLI 后端运行、以及整个 agent 跑在 worker 上的运行**不支持热改权限**，会直接被拒；这类要先停任务、改权限、再在原会话继续。

### 3.3 沙箱

沙箱默认**关闭**，由 `agents.defaults.sandbox`（全局）或 `agents.entries.*.sandbox`（按 agent）控制。开启后只有工具执行进沙箱，**Gateway 进程始终留在宿主上**。

最小开启示例：

```json5
{
  agents: {
    defaults: {
      sandbox: {
        mode: "non-main",
        scope: "session",
        workspaceAccess: "none",
      },
    },
  },
}
```

后端：docker（默认）、podman、ssh、openshell、crabbox。沙箱化的执行默认是内核级 `network: "none"`，或跑在 OpenShell 后端的默认拒绝策略白名单下。

```bash
openclaw sandbox list                                    # 容器、状态、镜像是否匹配、年龄、空闲时长、归属会话/agent
openclaw sandbox explain [--session <key>] [--agent <id>] # 生效模式、宿主 workspace、运行时工作目录、挂载、工具策略、该改哪个键
openclaw sandbox recreate [--all|--session <key>|--agent <id>] [--browser] [--force]
```

注意：工具允许/拒绝策略在沙箱规则之前生效——某个工具被全局或按 agent 拒了，开沙箱也救不回来。

---

## 4. 会话模型

- **直聊合并**：多个直聊会收敛到一个共享的 `main` 会话；**群组默认按组隔离**。
- 相关操作：

```bash
openclaw status
openclaw sessions cleanup
openclaw resume
openclaw attach
openclaw transcripts list|show|path
```

- 会话有搜索、裁剪、附件、队列与 steering（中途干预）、进度草稿等机制；长上下文会触发压缩（compaction）。
- **子代理**用于把独立子任务隔离到自己的上下文里跑，结果回传给父会话；`progress_card` 由父会话用来对外展示持久进度，子代理拿不到这个工具。
- 并发编排另有两条路：**swarm**（用代码从外部驱动多个并发 agent）与 **code mode**（把多个工具调用合进一段紧凑程序）。

---

## 5. 多 Agent 与绑定

一个 Gateway 可以带多个 agent，每个 agent 是一个独立的人设与状态边界。

```bash
openclaw agents add coding
openclaw agents add social
openclaw agents list
openclaw agents list --bindings
openclaw agents bindings
openclaw agents bind
openclaw agents unbind
openclaw agents set-identity
openclaw agents delete
```

- 每个 agent 有自己的 workspace（`SOUL.md`、`AGENTS.md`、可选 `USER.md`）、专属 `agentDir` 和独立会话库，默认落在 `~/.openclaw/agents/<agentId>`。
- 通道账号建在 `channels.<channel>.accounts` 下，用 `bindings` 把它们接到指定 agent 上；一个通道可以为每个 agent 开一个账号（例如一个 agent 一个 bot）。
- 改完重启并核对：

```bash
openclaw gateway restart
openclaw agents list --bindings
openclaw channels status --probe
```

- **跨 agent 会话访问默认开着**，由 `tools.agentToAgent` 管；要收窄用 `tools.sessions.visibility`，要限制配对的 agent 用 `tools.agentToAgent.allow`，要彻底禁掉就把 `tools.agentToAgent.enabled` 设为 `false`。**需要严格隔离就上独立 Gateway**，别指望一个 Gateway 里的可见性开关当安全边界。
- 记忆库也能按 agent 分开（例如把支持 agent 与市场 agent 的编译知识分库）。
- 让多个 agent 共用一个 Gateway、各自保持核心状态分离是受支持的模式；一个号码分给多个人（按私聊拆分）也有对应路由规则。

---

## 6. 记忆

- 内置记忆能力之外，还有记忆类插件（例如基于向量/文档库的记忆、以及按 wiki 组织的知识编译）。
- 记忆检索、来源追踪与「忘记」都有显式边界：

```bash
openclaw memory status
openclaw memory index
openclaw memory search <query>
openclaw memory forget
openclaw wiki status|doctor|init|compile|lint|ingest|search|get
```

- 记忆的写入来源、可追溯性与删除覆盖范围是不同的东西：被追踪的产物可以清；直接写入、hook 写入与原始转录不在删除覆盖范围内。做合规评审前先确认这两件事的差别。

---

## 7. 自动化：让它自己动起来

```bash
# 定时任务
openclaw cron status
openclaw cron list
openclaw cron get <id>
openclaw cron add
openclaw cron edit <id>
openclaw cron rm <id>
openclaw cron enable|disable <id>
openclaw cron runs <id>
openclaw cron run <id>

# 心跳与在线状态
openclaw system heartbeat last|enable|disable
openclaw system presence
openclaw system event

# 任务与转录
openclaw tasks list|show|notify|cancel|audit|maintenance
openclaw tasks flow list|show|cancel
openclaw transcripts list|show|path

# 事件钩子
openclaw hooks list|info|check|enable|disable|install|update
openclaw webhooks gmail setup|run
```

设计定时任务时先问三个问题：触发频率是多少、失败怎么办、输出发到哪里。三者没答案就先别上生产。

---

## 8. 通道与消息操作

```bash
openclaw channels list|status|capabilities|resolve|logs
openclaw channels add|remove|login|logout
openclaw channels dead-letters list|resubmit
```

发消息与消息管理（能力随通道而定，不是每条通道都支持全部子命令）：

```bash
openclaw message send
openclaw message broadcast
openclaw message poll
openclaw message react|reactions
openclaw message read|edit|delete
openclaw message pin|unpin|pins
openclaw message search
openclaw message thread create|list|reply
openclaw message permissions
openclaw message emoji list|upload
openclaw message sticker send|upload
openclaw message role info|add|remove
openclaw message channel info|list
openclaw message member info
openclaw message voice status
openclaw message event list|create
openclaw message timeout|kick|ban
```

群聊里的激活、群成员与权限、广播组、访问组、频道路由这些都有独立配置面；遇到「为什么不回话」，先看是不是群聊激活条件没满足。

---

## 9. 媒体能力

- 入向：图像、音频、视频、文档都能接收；语音短消息可转写。
- 出向：图像生成、视频生成、音乐生成、TTS 均有多家 provider 可选。

```bash
openclaw infer list
openclaw infer inspect <capability>
openclaw infer image generate|edit|describe|describe-many|providers
openclaw infer audio transcribe|providers
openclaw infer tts convert|voices|personas|providers|status|enable|disable|set-provider|set-persona
openclaw infer video generate|describe|providers
openclaw infer web search|fetch|providers
openclaw infer embedding create|providers
openclaw infer model run|list|inspect|providers|auth login|logout|status
```

`openclaw infer` 的别名是 `openclaw capability`。控制台、iOS / macOS、Android 与 Linux 伴侣端都支持音视频内联播放。

---

## 10. 技能与插件

**怎么选**：agent 已经有工具、只缺一套可复用的工作流与判断标准 → 用**技能**；需要全新的集成、运行时能力、凭证或生命周期钩子 → 用**插件**；只是要让 agent 执行一个动作 → 用**工具**。

### 10.1 技能（`SKILL.md` 指令包）

```bash
openclaw skills search <keyword>
openclaw skills install @owner/<slug>
openclaw skills install skills-sh:owner/repo/slug
openclaw skills install git:owner/repo@ref
openclaw skills install ./path/to/skill --as my-tool
openclaw skills install @owner/<slug> --global     # 装给本机所有 agent
openclaw skills update --all
openclaw skills update @owner/<slug> --global
openclaw skills verify @owner/<slug>
openclaw skills verify @owner/<slug> --card
openclaw skills list
openclaw skills info <name>
openclaw skills check
```

- 默认装进当前 workspace 的 `skills/` 目录；加 `--global` 装进共享管理目录。
- 加载优先级（高 → 低），同名时高优先级覆盖低的：

| 优先级 | 来源 | 路径 |
|---|---|---|
| 1 | workspace 技能 | `<workspace>/skills` |
| 2 | 项目 agent 技能 | `<workspace>/.agents/skills` |
| 3 | 个人 agent 技能 | `~/.agents/skills`（仅默认状态） |
| 4 | 受管 / 本地技能 | `<state-dir>/skills` |
| 5 | Workshop 技能 | `<state-dir>/agents/<agentId>/agent/workshop-skills` |
| 6 | 随安装分发 / 看护技能 | 随安装提供 |
| 7 | 额外目录与插件技能 | `skills.load.extraDirs` 加插件内置技能 |

沙箱化运行时读到的是物化副本，不是宿主上的原始路径。

### 10.2 插件

```bash
openclaw plugins list|search|inspect
openclaw plugins install <package>
openclaw plugins uninstall <name>
openclaw plugins update
openclaw plugins enable|disable <name>
openclaw plugins doctor
openclaw plugins build|validate|pack|init
openclaw plugins registry
openclaw plugins marketplace list|entries|refresh
```

插件来源可以是技能市场、npm 包、git 仓库、本地目录或压缩包。想钉住允许集合用 `plugins.allow`。原生插件跑在进程内、**没有沙箱隔离**，所以安装前要确认来源可信。

---

## 11. CLI 速查（按意图）

| 我要做什么 | 命令 |
|---|---|
| 装完看看哪里不对 | `openclaw triage`、`openclaw doctor`、`openclaw status --all` |
| 看 Gateway 活没活 | `openclaw gateway status`、`openclaw gateway probe`、`openclaw health` |
| 看日志 | `openclaw logs --follow` |
| 跟它说话 | `openclaw tui`、`openclaw dashboard`、`openclaw message send` |
| 换模型 | `openclaw models list`、`openclaw models set`、`openclaw models fallbacks add` |
| 试一个能力 | `openclaw infer list`、`openclaw infer model run` |
| 加通道 | `openclaw channels add`、`openclaw channels status --probe` |
| 管设备与配对 | `openclaw devices list`、`openclaw pairing approve`、`openclaw qr` |
| 管 agent | `openclaw agents add`、`openclaw agents list --bindings` |
| 管技能 | `openclaw skills search`、`openclaw skills install`、`openclaw skills check` |
| 管插件 | `openclaw plugins list`、`openclaw plugins install`、`openclaw plugins doctor` |
| 管权限 | `openclaw approvals`（`get` / `set` / `allowlist`）、`openclaw exec-policy show`、`openclaw sandbox explain` |
| 管凭证 | `openclaw secrets`（`reload` / `store` / `audit` / `configure` / `apply`） |
| 定时任务 | `openclaw cron add`、`openclaw cron runs <id>` |
| 备份升级 | `openclaw backup`（`create` / `verify` / `restore`）、`openclaw update` |
| 体检与外发面 | `openclaw security audit`、`openclaw audit`、`openclaw doctor` |
| 多环境隔离 | `openclaw --dev`、`openclaw --profile <name>`、`openclaw --container <name>` |

全局参数补充：`--log-level <level>` 覆盖日志级别；`--no-color` 关 ANSI（`NO_COLOR=1` 同样生效）；`--json` 让有界报告类命令只往 stdout 打一份 JSON 文档（失败时是 `{"ok": false, "error": {...}}` 这样一个信封，退出码非零），样式与进度被抑制，警告与诊断走 stderr。脚本要解析 stdout 并同时看退出码。

---

## 12. 一句话原则

先确认**工具在不在**（profile 与策略），再确认**它在哪跑**（沙箱与 elevated），最后才怀疑模型。九成的「它怎么不干活」都发生在第一层。
