# 安装与配置

覆盖范围：装到能用为止的全过程——安装路线选型、Gateway 服务化、目录与端口、模型接入、通道接入、容器化部署、远程访问、备份与升级。

---

## 1. 先定路线

| 你的情况 | 走哪条 |
|---|---|
| 想最快跑通，不介意脚本代管 Node | 安装脚本（macOS / Linux / WSL2 / Windows 各一条） |
| 自己管 Node，或要塞进已有 CI 镜像 | 包管理器装 `openclaw` 全局包 |
| 要改源码、要跟 main 分支 | 从源码构建（pnpm workspace） |
| 要隔离环境、要丢完就删、宿主机不想留东西 | Docker / Podman 容器化 Gateway |
| 无网络或内网隔离 | 先在有网机器拉镜像 → `docker load` → `setup.sh --offline` |

三条路线装的都是同一个 CLI 入口 `openclaw`，配置与状态目录也一致，先选一条跑通再考虑换。

---

## 2. 运行时前置条件

- **Node.js**：`>=24.16.0 <25` 或 `>=26.1.0`。这是硬性的 `engines` 字段，不是建议值。
- 官方安装脚本的行为：检测不到受支持的 Node 时自动补装——macOS 装 Node 26，Linux 装 Node 24 LTS。
- 从源码构建额外需要 **Corepack**（按 `package.json` 的 `packageManager` 自动选 pnpm 12.3.4）。Corepack 不可用时，显式装 `npm install -g pnpm@12.3.4 --allow-scripts=pnpm@12.3.4`，并保持 npm 的生命周期脚本与可选依赖开启，否则 pnpm 的原生可执行文件装不出来。
- 端口：默认 Gateway 端口 **18789**；`--dev` 模式换到 **19001** 并按规则偏移其它派生端口。

---

## 3. 安装脚本（推荐路径）

```bash
# macOS / Linux / WSL2
curl -fsSL https://openclaw.ai/install.sh | bash
```

```powershell
# Windows PowerShell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

不跑引导、只安装：

```bash
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard
```

```powershell
& ([scriptblock]::Create((iwr -useb https://openclaw.ai/install.ps1))) -NoOnboard
```

安装脚本会检测操作系统、按需补装 Node、安装包，然后自动拉起引导向导。脚本代管 npm 时不受你自己 npm 策略里的新鲜度过滤（例如 `min-release-age`）限制；手动用 npm 装则受你自己的策略约束。

**本地前缀安装**：想把 OpenClaw 和 Node 都放在 `~/.openclaw` 这类前缀下、不依赖系统级 Node，用 `install-cli.sh`：

```bash
curl -fsSL https://openclaw.ai/install-cli.sh | bash
```

它同时支持包安装与 git checkout 安装。已经装过之后，用 `openclaw update --channel dev` / `openclaw update --channel stable` 在两种安装形态之间切换。

**指定从 main 分支安装**：

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --install-method git --version main
```

---

## 4. 包管理器安装

```bash
# npm 12 或 npm 11.16+
npm install -g openclaw@latest --allow-scripts=openclaw

# npm 11.15 及更早：没有这套策略，直接装
npm install -g openclaw@latest

# pnpm
pnpm add -g --allow-build=openclaw openclaw@latest

# bun（1.4+）
bun add -g --trust openclaw@latest
```

参数差异的来由：

- **npm 12** 默认拦掉未批准的包生命周期脚本。`--allow-scripts=openclaw` 是显式放行 `preinstall` / `postinstall`，不加会报 `blocked because they are not covered by allowScripts`。
- **npm 11.16** 接受该参数，但即使不加也只是警告并照常执行。
- npm 11.16 提示的 `npm approve-scripts openclaw` 对全局安装无效，会以 `ENOMATCH` 失败——别照抄。
- **pnpm** 需要显式批准带构建脚本的包，而 `approve-builds -g` 不支持全局安装，所以在 `pnpm add -g` 上直接给 `--allow-build=openclaw`。
- **bun** 的 `--trust` 只放行本次安装的生命周期脚本。Node 仍是主运行时，`openclaw` 可执行文件保留 Node shebang；要强制用 Bun 跑，用 `bun run --bun openclaw ...`，并把托管 Gateway 装在 Bun 下时加 `--daemon-runtime bun`。

装完继续走引导：

```bash
openclaw onboard --install-daemon
```

**`openclaw` 命令找不到**时，九成是 PATH 问题：npm 的全局 bin 目录没进 shell 的 PATH。三步自查：

```bash
node -v           # Node 装了没
npm prefix -g     # 全局包装在哪
echo "$PATH"      # 那个 bin 目录在不在 PATH 里
```

---

## 5. 从源码构建

仓库是 pnpm workspace，**根目录直接 `npm install` 不受支持**。

```bash
git clone <上游仓库地址>
cd openclaw
corepack enable
pnpm install && pnpm build && pnpm ui:build
pnpm add --global "openclaw@link:$PWD"
openclaw onboard --install-daemon
```

- `pnpm add --global "openclaw@link:$PWD"` 把 CLI 链到当前 checkout，且不改动包的依赖文件。
- pnpm 报全局 bin 目录不在 PATH 时，跑 `pnpm setup`，重开 shell 再试。
- 不想装全局，也可以在仓库里用 `pnpm openclaw ...` 调用。

---

## 6. 引导向导

```bash
npx openclaw@latest        # 新装可直接这么起
openclaw setup             # 先验证推理，再配 Gateway、workspace、通道、技能与健康检查
openclaw onboard           # 同上，引导式
openclaw onboard --classic # 经典分步向导
openclaw setup --baseline  # 只建基线配置与 workspace，不走向导
openclaw configure         # 改已有配置的某一部分：模型认证、Gateway、通道、插件、技能
```

引导会做三件事：验证模型可用（用一次真实补全，而不是只看 Key 存不存在）、创建 workspace、写 Gateway 配置。之后 `openclaw configure` 用来增量调整，`openclaw config get|set|patch|unset|file|schema|validate` 用来精确改某个键。

---

## 7. 把 Gateway 装成常驻服务

引导里的 Quick start 会把 Gateway 留在当前终端前台（**Ctrl+C** 就停）。要它常驻并开机自启：

```bash
openclaw gateway install
```

按平台落到不同的托管方式：

| 平台 | 托管方式 |
|---|---|
| macOS | LaunchAgent |
| Linux / WSL2 | systemd 用户单元 |
| 原生 Windows | 计划任务；创建被拒时回退到用户「启动」文件夹的登录项 |

停止前台 Gateway 再装服务不会丢配置——配置是持久化的。

常用操作：

```bash
openclaw gateway status      # Runtime / 连通性探针 / 能力级别
openclaw gateway probe       # Reachable: yes 才算通
openclaw gateway start|stop|restart
openclaw gateway health
openclaw gateway diagnostics export
openclaw gateway call <method> <params>
openclaw gateway usage-cost
```

`openclaw gateway status --require-rpc` 会额外要求读作用域 RPC 证明。看到 `Read probe: limited - missing scope: operator.read` 属于诊断降级，不是连接失败。

---

## 8. 控制台、端口与自定义前端

```bash
openclaw dashboard          # 打开浏览器控制台
openclaw tui                # 终端界面（chat / terminal 是 tui --local 的别名）
```

控制台默认地址是 `http://127.0.0.1:18789/`。Gateway 的 HTTP 服务同时提供两个托管界面路径：`/__openclaw__/canvas/`（托管界面文档）与 `/__openclaw__/a2ui/`（A2UI 渲染资源），用的是同一个端口。

要挂自己构建的本地化前端，把 `gateway.controlUi.root` 指向含 `index.html` 的静态资源目录：

```json
{
  "gateway": {
    "controlUi": {
      "enabled": true,
      "root": "${HOME}/.openclaw/control-ui-custom"
    }
  }
}
```

改完 `openclaw gateway restart` 再 `openclaw dashboard`。

---

## 9. 目录、配置与环境变量

默认路径：

| 项目 | 默认值 |
|---|---|
| 状态目录 | `~/.openclaw` |
| 配置文件 | `~/.openclaw/openclaw.json` |
| 各 agent 的目录 | `~/.openclaw/agents/<agentId>` |
| dev 模式状态目录 | `~/.openclaw-dev`（端口 19001） |
| 具名 profile 状态目录 | `~/.openclaw-<name>` |

环境变量（配置文件的优先级说明在下一节）：

| 变量 | 作用 |
|---|---|
| `OPENCLAW_HOME` | 内部路径解析用的「家目录」 |
| `OPENCLAW_STATE_DIR` | 覆盖状态目录 |
| `OPENCLAW_CONFIG_PATH` | 覆盖配置文件路径 |
| `OPENCLAW_GATEWAY_TOKEN` | Gateway 共享密钥；留空会在首次启动时自动生成。**不能**直接把文档里的示例占位值粘进去，Gateway 会拒绝启动 |
| `OPENCLAW_GATEWAY_PASSWORD` | 另一种可选认证方式（与 token 二选一） |
| `OPENCLAW_INCLUDE_ROOTS` | 允许 `$include` 从哪些额外目录取文件（POSIX 用 `:`、Windows 用 `;` 分隔，支持 `~` 展开）；不设则只允许配置文件所在目录 |
| `OPENCLAW_LOAD_SHELL_ENV` | 从登录 shell profile 补齐缺失的变量 |
| `OPENCLAW_CONTAINER` | 默认在哪个运行中的容器里执行 CLI |
| `OPENCLAW_IMAGE` / `OPENCLAW_SANDBOX` / `OPENCLAW_DOCKER_SOCKET` | 容器化部署用的镜像与沙箱开关、Docker socket 位置 |

**环境变量的来源优先级（高 → 低）**：进程环境 → `./.env` → `~/.openclaw/.env` → `openclaw.json` 的 `env` 块。已存在的非空进程环境变量不会被 dotenv 覆盖。注意：直接写进配置的键（例如 `gateway.auth.token` 或通道 token）走另一套解析，常常优先于环境变量兜底值。

**多实例隔离**用全局参数，而不是手改路径：

```bash
openclaw --dev <命令>              # 状态隔离在 ~/.openclaw-dev
openclaw --profile <name> <命令>   # 状态隔离在 ~/.openclaw-<name>
openclaw --container <name> <命令> # 在指定容器里跑 CLI
```

具名 profile 会顶掉从别的 profile 继承来的规范状态与配置路径（含正在运行的 Gateway 服务）；你自己显式改过的状态目录与配置路径不受影响。

---

## 10. 模型接入

### 10.1 命令行接入

```bash
openclaw models list
openclaw models status
openclaw models set <provider>/<model>
openclaw models set-image <provider>/<model>
openclaw models aliases add <alias> <model>
openclaw models fallbacks list
openclaw models fallbacks add <model>
openclaw models image-fallbacks add <model>
openclaw models scan                     # 扫描本机可用的推理入口
openclaw models auth list
openclaw models auth add                 # 追加一组认证
openclaw models auth login               # 交互式登录
openclaw models auth setup-token
openclaw models auth paste-token
openclaw models auth paste-api-key
openclaw models auth login-github-copilot
openclaw models auth order get|set|clear # 认证轮换顺序
```

关键语义：**增加一组 provider 认证不会改你的主模型**。认证决定「能不能用」，`models set` 决定「默认用哪个」。

### 10.2 环境变量接入

`.env` 里按需填，至少填一个：

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
```

多 Key 轮换两种写法，可混用：

```
OPENAI_API_KEY_1=sk-...
OPENAI_API_KEY_2=sk-...
OPENAI_API_KEYS=sk-a,sk-b
```

Key 的来源与优先级、轮换在什么时候触发，在控制台的 Settings → Models 里也能配。

### 10.3 自定义与本地推理

自建服务走 `models.providers` 配自定义 base URL。已内置支持的自托管运行时包括 Ollama、vLLM、SGLang、llama.cpp、LM Studio，以及任意 OpenAI 兼容或 Anthropic 兼容端点；本地反向代理（LM Studio、vLLM、LiteLLM 这类）同样按自定义 provider 处理。

排错要点（这条最常踩）：**本地 OpenAI 兼容后端直连能用，但经过 Gateway 就失败**，通常出在 base URL 或路由整形规则上，而不是网络不通——先用 `openclaw infer model run` 这种最小调用复现，再回头查 provider 配置。

### 10.4 用量与成本

```bash
openclaw status --usage
```

能用到的 provider 会给出额度信息，并归一化成 `X% left` 显示；具体支持哪些取决于你装的 provider 插件。`openclaw gateway usage-cost` 看 Gateway 侧的用量成本。

---

## 11. 通道接入

```bash
openclaw channels add                 # 引导式；也可用参数走脚本化直连
openclaw channels list
openclaw channels status
openclaw channels status --probe      # Gateway 可达时给真实传输状态
openclaw channels capabilities
openclaw channels resolve
openclaw channels login --channel <id> --account <name>
openclaw channels logout --channel <id>
openclaw channels logs
openclaw channels dead-letters list|resubmit
```

- **核心自带**：A2A、Reef、Telegram、WebChat。Telegram 是最快的通道——一个 Bot Token 就够。
- **插件通道**：23 条，用 `openclaw plugins install @openclaw/<id>` 装；`openclaw onboard` 与 `openclaw channels add` 过程中也可以按需装。
- **仓库外维护**：WeChat、Yuanbao、Zalo ClawBot。
- 群聊支持基于 @ 提及的激活；私聊有白名单与配对两道控制。
- **示例（多账号）**：WhatsApp 按号码逐个登录 `openclaw channels login --channel whatsapp --account work`。

### 配对（把陌生人挡在外面）

未知发件人默认需要配对。`openclaw pairing list` 看请求，`openclaw pairing approve <channel> <code>` 批准。设备侧用 `openclaw devices list|approve|reject|rotate|revoke|remove|clear`。本地回环连接可以被自动批准，但**局域网与 tailnet 的连接（包括同主机上的 tailnet 绑定）仍需显式批准**。

---

## 12. 容器化部署

Docker 是**可选**的，用来做隔离的、可随时丢弃的 Gateway 环境，或宿主机不想装任何东西的场合。沙箱和容器化是两件独立的事：沙箱默认关闭，且不需要 Gateway 本身跑在容器里。

前置：Docker Desktop 或 Docker Engine + Compose v2；**本地从源码构建镜像建议 ≥6GB RAM**（用预构建镜像则不需要）。

```bash
# 从仓库根构建本地镜像 openclaw:local
./scripts/docker/setup.sh

# 用预构建镜像（GHCR 是主注册表）
export OPENCLAW_IMAGE="ghcr.io/openclaw/openclaw:latest"
./scripts/docker/setup.sh

# 或用 Docker Hub 上的同名镜像
export OPENCLAW_IMAGE="openclaw/openclaw:latest"
./scripts/docker/setup.sh
```

`setup.sh` 会同步 `.env`、修正权限、跑引导、同步 Gateway 配置并启动 Compose。引导会提示填 provider Key、生成 Gateway token 写进 `.env`、建认证资料的密钥目录。

镜像 tag 与变体：

| 类型 | 例子 |
|---|---|
| 具体版本 | `2026.9.3` |
| 预发布 | `2026.9.1-beta.1` |
| 稳定/主干 | `latest`、`main`；按月的 Gateway 发布只推 `extended-stable` |
| 精简变体 | `slim`、`main-slim`、`extended-stable-slim` |
| 带浏览器变体 | `latest-browser`、`main-browser`、`extended-stable-browser` |

默认镜像内置 `codex` 与 `diagnostics-otel` 两个插件；`-browser` 变体额外烤进 Chromium，供 Gateway 控制的浏览器使用（agent 沙箱浏览器用的是另一个镜像）。请只用官方注册表，非官方镜像不共享同一套发布节奏与保留策略。

打开控制台：访问 `http://127.0.0.1:18789/`，把 `.env` 里那个 token 粘进设置。忘了地址就：

```bash
docker compose run --rm openclaw-cli dashboard --no-open
```

自定义了 `OPENCLAW_GATEWAY_PORT` 时，把打印 URL 里的 `18789` 换成宿主端口，其余路径不要动。

**离线/内网**：

```bash
docker load -i openclaw-image.tar
export OPENCLAW_IMAGE="ghcr.io/openclaw/openclaw:latest"
./scripts/docker/setup.sh --offline
```

`--offline` 会先确认镜像已存在于本地，再禁用隐式拉取与构建，然后走正常流程。开了 `OPENCLAW_SANDBOX=1` 时，离线流程还会校验默认与各 agent 的沙箱镜像是否在位；缺了或过期就直接退出，不会写坏沙箱配置。

其它部署面：Kubernetes、Podman（无 root）、Nix flake、Ansible 批量供给、云主机与 VPS（多家服务商模板）、Render、Cloudflare Containers（实验）、macOS 虚拟机。多用户场景走「一租户一 Gateway cell」模型。

---

## 13. 远程访问

- **首选**：Tailscale 或 VPN。
- **次选**：SSH 隧道

  ```bash
  ssh -N -L 18789:127.0.0.1:18789 user@gateway-host
  ```

  隧道上沿用同一套握手与鉴权；远端场景可对 WebSocket 开 TLS 与可选 pinning。

鉴权模式由 `gateway.auth.mode` 选择取值来源（`gateway.auth.token` 或 `gateway.auth.password`）；带身份的模式（例如 Tailscale Serve 的 `gateway.auth.allowTailscale: true`，或非回环下的 `gateway.auth.mode: "trusted-proxy"`）从请求头取认证，而不是 `connect.params.auth.*`。`gateway.auth.mode: "none"` 会彻底关掉共享密钥认证，**只允许用在私有入口**。

另外两条容易忽略的约束：所有连接都必须签 `connect.challenge` 的 nonce，签名负载 `v3` 还会绑定 `platform` 与 `deviceFamily`；非本地连接一律需要显式批准。

---

## 14. 备份、升级、迁移与卸载

```bash
# 备份
openclaw backup create
openclaw backup verify
openclaw backup restore
openclaw backup sqlite create|list|verify|restore
openclaw backup git init|create|log|verify|restore

# 升级
openclaw update
openclaw update wizard
openclaw update status
openclaw update repair
openclaw update --channel dev|stable

# 迁移（换机器 / 换 provider）
openclaw migrate list
openclaw migrate plan <provider>
openclaw migrate apply <provider>

# 收尾
openclaw doctor            # 查配置与服务问题
openclaw doctor --fix      # 含状态库迁移；旧版本遗留的会话 exec 策略要在升级后跑这个
openclaw reset
openclaw uninstall
```

升级或大改配置前先 `backup create`，并用 `backup verify` 确认归档可用。`doctor` 负责状态库迁移这类工作，运维姿态是「把部署当可替换基础设施」——坏了就按验证过的备份重部署，而不是就地修。

---

## 15. 装完的验收顺序

```bash
openclaw --version          # CLI 在不在
openclaw doctor             # 有没有阻塞性配置/服务错误
openclaw gateway status     # Runtime: running / 连通性 ok / 端口 18789
openclaw dashboard          # 控制台能打开
openclaw channels status --probe
```

最后在控制台对话框里发一句话，拿到真实回复才算真的通了。任何一步不对，跳到 `references/extend-and-troubleshoot.md` 的排查阶梯。
