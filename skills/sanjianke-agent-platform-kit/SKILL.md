---
name: sanjianke-agent-platform-kit
slug: sanjianke-agent-platform-kit
displayName: 三剪客 · 全能 AI Agent 平台
description: "把 AI 助手跑在自己设备上的开源 Agent 平台。 遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "OpenClaw 是运行在自己设备上的开源 AI Agent：一个 Gateway 统管会话、工具与消息通道，支持 20+ 聊天平台与 macOS/iOS/Android/Windows/Linux，模型与执行 harness 皆可插拔。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - Agent 平台
  - 工具集成
---

# 三剪客 · 全能 AI Agent 平台

把 AI 助手跑在自己设备上的开源 Agent 平台。

OpenClaw 要解决的不是「再做一个聊天框」，而是让 AI 在你自己的机器上真的动手：读你的文件、跑你的命令、开浏览器、收发你已经在用的聊天软件里的消息，而状态、记忆和凭证都留在本地。它的形态是一个常驻本机的 Gateway，加上命令行、终端界面、浏览器控制台、桌面伴侣 App 和手机节点这几类客户端，默认只在回环地址上监听。

该用它的时候：你想要一个能跨聊天平台、能调工具、能后台常驻跑定时任务的私人助手，且不愿意把数据交给别人的托管服务；或者你要给团队搭一套可审计、可沙箱、可换模型的 Agent 底座。不该用它的时候：你只要一个网页版问答机器人，或者只是偶尔调一次模型 API 拿一段文本。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（必需） | 客户端与 Gateway 之间走 WebSocket（默认 `127.0.0.1:18789`）；推理请求发往你自己配置的 provider；通道插件出网连接 Telegram、Slack、Discord、WhatsApp 等消息服务；安装与更新时访问 npm 源和官方安装脚本地址 |
| 读取文件 | 是 | 读取 `~/.openclaw/openclaw.json`、`.env`、会话与状态库、workspace 内的工作文件；沙箱关闭时工具直接读宿主文件系统 |
| 写入文件 | 是 | 写状态目录 `~/.openclaw`（会话、记忆、日志、备份）、workspace 文件，以及 `openclaw backup create` 产生的归档 |
| 凭证 | 是 | 模型 provider 的 API Key 或 OAuth 登录态、聊天通道的 Bot Token 或账号登录态（如扫码登录）、Gateway 共享密钥 `OPENCLAW_GATEWAY_TOKEN`。这些都由使用者自行提供并保存在本机状态目录 |
| 子进程 / 后台常驻 | 是 | 需要 Node 运行时并常驻 Gateway 进程；`openclaw gateway install` 会注册开机自启（macOS 的 LaunchAgent、Linux 与 WSL2 的 systemd 用户单元、原生 Windows 的计划任务）；`exec`、`browser` 等工具会拉起子进程与浏览器 |

**密钥与费用**：本 Skill 不内嵌任何密钥，不代管你的凭证，也不代理转发任何请求。模型调用产生的费用由你自己的 provider 账号承担，聊天平台与第三方服务的额度同理。Gateway 默认只做每日一次版本检查，匿名功能统计默认关闭，配置里设 `update.checkOnStart: false` 可把两者一并关掉。想核对外发面，用 `openclaw security audit` 与 `openclaw secrets audit`。

## 触发场景

- 「我想在自己电脑上跑一个 AI 助手，能读文件、能执行命令，数据别出本机」——本机 Gateway 部署与工具策略配置。
- 「让它接上我的 Telegram / Slack / 飞书，我直接在聊天软件里使唤它」——通道插件安装与账号登录。
- 「公司要私有化部署，模型走我们自己的 vLLM / Ollama 端点」——自定义 provider 与本地推理服务接入。
- 「我要几个不同人设的 Agent，各管一摊、各用各的账号」——多 Agent 与 bindings 路由。
- 「每天早上自动跑一遍巡检，把结果发到群里」——cron 定时任务与 heartbeat。
- 「不确定装没装好 / 装了但助手像被阉割了，只会聊天不干活」——用 triage / status / doctor 这条阶梯定位。
- 「要给它加我们内部系统的工具，或者装一个现成技能」——skills 与 plugins 扩展。
- 「怕它乱删文件、乱跑命令，先把权限收紧」——权限模式、沙箱与 exec 审批。

## 快速开始

### 一步跑起来（最快确认能用）

Node 版本要求 `>=24.16 <25` 或 `>=26.1`（26 更推荐）。已经装过 Node 的话，连装都不用装就能试：

```bash
npx openclaw@latest
```

首次安装后引导向导会自动打开。选 **Quick start** 即可：它会探测机器上已有的 CLI 登录态或 API Key，用一次真实补全验证通过后写配置并打开 Web 控制台。想逐项走就选 **Custom setup**，或者稍后用 `openclaw onboard --classic` 打开经典分步向导。

### 正式安装（三条路选一条）

```bash
# macOS / Linux / WSL2
curl -fsSL https://openclaw.ai/install.sh | bash

# 只装、不跑引导
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard
```

```powershell
# Windows PowerShell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

自己管 Node 的，直接装包（npm 12 或 11.16+）：

```bash
npm install -g openclaw@latest --allow-scripts=openclaw
# npm 11.15 及更早：去掉 --allow-scripts=openclaw
pnpm add -g --allow-build=openclaw openclaw@latest
bun add -g --trust openclaw@latest
```

### 装成常驻服务并验证

```bash
openclaw onboard --install-daemon   # 走完引导并注册开机自启
openclaw gateway status             # 应看到 Gateway 在 18789 端口监听
openclaw dashboard                  # 打开浏览器控制台，在对话框里发一句话
```

### 接一个模型

```bash
openclaw models list                     # 看当前可用模型与 provider
openclaw models set <provider>/<model>   # 切换主模型
openclaw models fallbacks add <model>    # 主模型失败时自动降级
openclaw models auth list                # 看已配置的认证
openclaw infer list                      # 看当前可用的能力面（图像/音频/TTS/视频/搜索等）
```

也可以用环境变量：`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GEMINI_API_KEY`、`OPENROUTER_API_KEY` 等。要轮换多把 Key，用 `OPENAI_API_KEY_1` / `OPENAI_API_KEY_2`，或逗号分隔的 `OPENAI_API_KEYS=sk-1,sk-2`。自建推理走 OpenAI 兼容或 Anthropic 兼容端点，Ollama、vLLM、SGLang、llama.cpp、LM Studio 都有对应 provider 插件。

### 接一个聊天通道

```bash
openclaw channels add                 # 引导式添加通道账号
openclaw channels list
openclaw channels status --probe      # Gateway 可达时返回逐账号的真实连通状态
```

核心安装自带 A2A、Reef、Telegram、WebChat 四条通道，其余走官方插件：

```bash
openclaw plugins install @openclaw/<id>
```

未知发件人默认走配对，批准方式是：

```bash
openclaw pairing list
openclaw pairing approve <channel> <code>
```

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 选安装方式、装成常驻服务、定端口与目录、配模型与 Key、加通道与配对、Docker 与远程接入、备份与升级 | `references/install-and-config.md` |
| 工具有哪些、档位怎么调、会话权限与沙箱怎么设、多 Agent 怎么编排、记忆与定时任务、技能与插件怎么装怎么用 | `references/capabilities-and-usage.md` |
| 写自己的插件或技能、Gateway 起不来、通道连不上、工具被策略挡住、模型报错、升级回滚与卸载 | `references/extend-and-troubleshoot.md` |

## 能力边界

**覆盖**：

- 本地常驻控制面：单实例 Gateway 统一持有会话、工具、事件与通道连接，默认监听 `127.0.0.1:18789`，用 WebSocket 暴露经 JSON Schema 校验的类型化接口（首帧必须是 `connect`，设备身份需配对，副作用方法要带幂等键）。
- 客户端家族：命令行（`openclaw`）、终端界面（`openclaw tui`）、浏览器控制台（`openclaw dashboard`）、桌面伴侣（macOS 菜单栏 App、Windows Hub）、设备节点（iOS / Android / 无头节点，提供 `camera.*`、`screen.record`、`location.get` 等设备侧命令）。
- 平台覆盖：macOS、Linux、Windows（原生 Hub、PowerShell 安装器、WSL2 三条路）、iOS、Android、ChromeOS。
- 模型接入：内置大量 provider 插件（主流闭源 API、云厂商托管推理、聚合网关），外加任何 OpenAI 兼容 / Anthropic 兼容端点与本地推理服务；支持订阅式 OAuth 登录、多 Key 轮换与主备模型降级链。
- 通道：核心 4 条（A2A、Reef、Telegram、WebChat）+ 官方插件通道 23 条（Discord、Feishu、Google Chat、iMessage、IRC、LINE、Matrix、Mattermost、Microsoft Teams、Nextcloud Talk、Nostr、QQ Bot、Raft、Signal、Slack、SMS、Synology Chat、Tlon、Twitch、Voice Call、WhatsApp、Zalo、Zalo Personal），另有仓库外维护的 WeChat、Yuanbao、Zalo ClawBot。
- 工具面：运行时（`exec`、`process`、`terminal`、`code_execution`）、文件（`read`、`write`、`edit`、`apply_patch`）、人机确认（`ask_user`、`secrets`）、网页（`web_search`、`web_fetch`、`x_search`）、浏览器（`browser`）、界面（`screen`）、进度卡（`progress_card`），以及图像 / 音视频生成与语音转写等媒体工具。
- 工具档位：`tools.profile` 取 `minimal`（只放行会话状态查询）、`messaging`（窄，纯聊天）、`coding`（新本地配置的默认档，放行仓库 / 文件 / shell / 运行时）、`full`（去掉档位限制，只建议给受信操作者）。
- 权限与隔离：会话级四档权限模式 `read-only` / `guarded` / `workspace` / `full`（`full` 需要 `operator.admin`，其余需要 `operator.write`）；`tools.elevated` 是显式逃逸口；沙箱后端支持 docker、podman、ssh、openshell、crabbox。
- 多 Agent：`openclaw agents add <id>` 为每个 agent 建独立 workspace（`SOUL.md`、`AGENTS.md`、可选 `USER.md`）、独立 `agentDir` 与会话库（默认在 `~/.openclaw/agents/<agentId>`），再用 bindings 把通道账号绑到指定 agent；另支持子代理、ACP 代理与并发编排（swarm / code mode）。
- 自动化与运维：cron 定时任务、heartbeat、hooks、webhooks、任务与转录；`status` / `health` / `triage` / `doctor` / `logs` / `audit` 诊断链；`backup create|verify|restore`、`update`、`security audit`、`secrets audit`。
- 远程接入：优先 Tailscale 或 VPN，次选 SSH 隧道 `ssh -N -L 18789:127.0.0.1:18789 user@gateway-host`，隧道上沿用同一套握手与鉴权。
- 扩展体系：skills（`SKILL.md` 指令包）、plugins（可加工具、provider、通道、hooks、打包技能）、`mcp`、`hooks`、`webhooks`，以及公开的插件 SDK（约 150 个入口点，按只减不增的额度管理）。

**不覆盖**：

- 不提供托管服务。上游没有付费档位，也没有官方 SaaS；自己装、自己跑、自己向模型厂商付费。
- 不保证默认就安全。沙箱与 exec 审批默认关闭，默认形态是「受信任的单操作者助手」；要暴露到公网或给多人用，硬化配置得自己做。
- 不做多租户隔离。一个 Gateway 就是一个信任域，角色与会话归属只是协作护栏；多租户要一租户一个 Gateway，`fleet` 目前仍属实验特性。
- 不隔离原生插件。插件在当前进程内运行，没有沙箱保护；只能靠白名单、安装策略钩子、锁版本、锁依赖与 CI 强制的 SDK 边界降低风险。
- 不替你判断合规。抓取、群发、消息留存与个人数据处理的合规责任在部署方，本 Skill 只描述产品已有的能力。
- 不内嵌任何第三方源码。正文为原创整理，只引用产品名、命令、配置键、端口、版本号等事实性信息。

## 依赖条件

- 上游仓库：`https://github.com/openclaw/openclaw`（pnpm workspace，仓库语言 TypeScript，包元数据声明 MIT）。
- 运行时：Node.js `>=24.16.0 <25` 或 `>=26.1.0`。官方安装脚本会在缺失时自动装 Node（macOS 装 26，Linux 装 24 LTS）；从源码构建需要 Corepack 与 pnpm 12.3.4。
- 操作系统：macOS / Linux / Windows / WSL2 任一；桌面伴侣 App 只在对应平台提供。
- 磁盘与网络：需要可写的 `~/.openclaw` 状态目录，能出网访问模型 provider 与消息平台；容器化部署另需 Docker Engine 或 Desktop + Compose v2。
- 凭证：至少一个模型 provider 的 Key，或可复用的 CLI / OAuth 登录态；用聊天通道还需该平台的 Bot Token 或账号登录态；远程接入需要 `OPENCLAW_GATEWAY_TOKEN`（或密码）并完成配对授权。
- 内存：本地从源码构建 Docker 镜像建议 ≥6GB RAM；直接用预构建镜像可跳过这一步。

## 已知限制

- **默认只绑回环**。Gateway 默认监听 `127.0.0.1:18789`；改变绑定范围前先跑 `openclaw security audit`，并读完安全与沙箱相关文档。
- **Node 版本区间窄**。只支持 `>=24.16 <25` 或 `>=26.1`；Node 18 / 20 / 22 不在支持范围内。
- **沙箱不是完美的安全边界**。它只是「实质性降低爆炸半径」，不构成对恶意模型的牢不可破隔离；网络策略、挂载范围与出口白名单都要你自己确认。
- **出口白名单只覆盖配合的流量**。未沙箱化的宿主 `exec` 发出的原始 socket 归你的代理或宿主策略管，不由 OpenClaw 拦。
- **记忆没有基于时间的保留上限**。可追踪的产物能用 `openclaw memory forget` 清理，但直接写入、hook 写入与原始转录不在覆盖范围内。
- **版本检查只管守卫、不管结果**。Schema 有版本、升级有兼容检查、发布有签名，但这些都不保证每次升级一定成功；大改动前先 `openclaw backup create`。
- **`fleet` 仍属实验特性**。跨机器编排不要当生产依赖。
- **许可证需要自己核对**。包元数据与 README 声明 MIT，但仓库根 `LICENSE` 与标准 MIT 模板存在差异（代码平台的许可证识别结果是 `Other`）。二次分发或商用前请读一遍全文。
- **生态规模大不等于默认全开**。仓库里 `extensions/` 有 156 个子目录、`skills/` 有 50 个随安装分发的技能、`packages/` 有 23 个内部包；实际启用哪些由配置与安装策略决定。撰写时该项目在代码托管平台上约有 38.9 万 star、8.2 万 fork，热度同样不等于默认开启的覆盖面。
- **本文的时效**。正文按撰写时（上游包版本 2026.9.4）抓取的仓库结构、CLI 索引与官方文档整理；命令树会随后续版本变化，落地时以 `<命令> --help` 的实时输出为准。

## 自检清单

- [ ] Node 版本落在 `>=24.16 <25` 或 `>=26.1` 区间内。
- [ ] 装完先 `openclaw gateway status` 看到 18789 在监听，再 `openclaw dashboard` 发出第一条消息。
- [ ] 模型侧先 `openclaw models list` 确认可用，再考虑 `models set` 与 fallbacks。
- [ ] 至少一个 provider 的 Key 走环境变量或 `models auth`，没有硬编码进脚本或提交记录。
- [ ] 通道加完跑过 `openclaw channels status --probe`，确认逐账号真实连通而不是只看配置。
- [ ] 未知发件人走的是配对流程，`openclaw pairing list` 里的待批请求逐条确认过。
- [ ] 权限模式按最小够用选：能只读就别给写，能用 `guarded` 就别开 `full`。
- [ ] 清楚当前 `tools.profile` 是哪个档位，没把 `full` 给到不可信场景。
- [ ] 需要隔离执行的场景开了沙箱，并用 `openclaw sandbox explain` 看过生效配置。
- [ ] 对外暴露前跑过 `openclaw security audit`，并想清楚谁可以连上这个 Gateway。
- [ ] 定时任务、hook、webhook 上线前确认过触发频率与失败处理方式。
- [ ] 升级或大改配置前 `openclaw backup create`，并验证过归档能恢复。
- [ ] 抓取 / 群发类用法已确认目标平台条款与当地法规。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/install-and-config.md` | 安装与配置：三条安装路线、Docker 与自托管、Gateway 服务化、端口与目录、模型接入与 Key 轮换、通道添加与配对、备份与升级 |
| `references/capabilities-and-usage.md` | 能力与用法：工具清单与档位、浏览器与 exec、权限模式与沙箱、多 Agent 与绑定、记忆与定时任务、技能与插件安装、常用 CLI 速查 |
| `references/extend-and-troubleshoot.md` | 扩展与排错：技能与插件开发、四类故障的排查阶梯、升级回滚、日志与审计、卸载清理、常见误判 |

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
