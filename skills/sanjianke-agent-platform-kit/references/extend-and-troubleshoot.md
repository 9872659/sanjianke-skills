# 扩展与排错

覆盖范围：怎么给它加东西（技能、插件、工具、provider、通道），以及坏掉时按什么顺序查（Gateway / 通道 / 工具 / 模型四类），最后是升级回滚、日志审计与卸载清理。

---

## 1. 扩展点怎么选

| 你缺什么 | 扩展点 | 判断依据 |
|---|---|---|
| 一套可复用的工作流、审查标准、命令序列或操作约束 | **技能**（`SKILL.md`） | agent 已经有工具了，缺的是「怎么做」 |
| 一个新的集成、运行时能力、凭证或生命周期钩子 | **插件** | 有能力代码、需要打包与安装 |
| 就是让 agent 多会一个动作 | **工具** | 通常是插件的一部分 |
| 一条新的消息出入口 | **通道插件** | 走通道 SDK |
| 一个新的模型 / 推理后端 | **provider 插件** | 走 provider SDK |

---

## 2. 写一个技能

### 2.1 最小形态

`SKILL.md` 的 frontmatter 最少需要 `name` 与 `description`：

```markdown
---
name: image-lab
description: 用 provider 支撑的图像工作流生成或编辑图片
---

当用户要求生成图片时，调用 `image_generate` 工具……
```

正文里用 `{baseDir}` 引用技能所在目录。frontmatter 先按 YAML 解析，失败则退回单行解析器；嵌套的 `metadata` 块会被压成 JSON 字符串再按 JSON5 解析，所以块状写法可用。

### 2.2 可选 frontmatter 键

| 键 | 类型 / 默认 | 作用 |
|---|---|---|
| `homepage` | string | 在桌面端技能界面里显示为「Website」；也可写在 `metadata.openclaw.homepage` |
| `user-invocable` | boolean，默认 `true` | 是否把它暴露成一个用户可调的斜杠命令 |
| `disable-model-invocation` | boolean，默认 `false` | 为 `true` 时不把技能说明放进常规提示词；若同时 `user-invocable: true`，它仍作为斜杠命令可用 |
| `command-dispatch` | `"tool"` | 设为 `tool` 时，斜杠命令绕过模型直接派发给已注册工具 |
| `command-tool` | string | `command-dispatch: tool` 时要调用的工具名 |
| `command-arg-mode` | `"raw"`，默认 `raw` | 工具派发时把原始参数串直接透传；工具收到 `{ command, commandName, skillName }` |

### 2.3 组织与共享

- 个人独占用 `~/.agents/skills`；项目内共享用 `<workspace>/skills` 或 `<workspace>/.agents/skills`；全机共享用 `<state-dir>/skills`（`--global` 装到这里）。
- 同名技能按加载优先级覆盖，**顺序不直观**：workspace/`skills` → workspace/`.agents/skills` → `~/.agents/skills` → `<state-dir>/skills` → workshop-skills → 随安装分发 → 额外目录与插件技能。调试「为什么我的技能没生效」时第一件事就是按这张表找同名覆盖。
- 技能可被 agent 白名单限制；插件也能打包技能一起分发。
- 有 Skill Workshop 一套 propose / revise / apply / reject / quarantine 流程，适合把临时经验沉淀成受管技能。
- **注意 token 成本**：技能说明会进提示词，塞太多技能会挤占上下文。用 `disable-model-invocation` 或收窄加载范围来控制。

### 2.4 安装与校验

```bash
openclaw skills install @owner/<slug>
openclaw skills install skills-sh:owner/repo/slug
openclaw skills install git:owner/repo@ref
openclaw skills install ./path/to/skill --as my-tool
openclaw skills install @owner/<slug> --global
openclaw skills update --all
openclaw skills verify @owner/<slug>
openclaw skills verify @owner/<slug> --card
openclaw skills list
openclaw skills info <name>
openclaw skills check
openclaw skills workshop list|inspect|propose-create|propose-update|revise|apply|reject|quarantine
```

`skills verify` 用来核验技能的信任信封；`--card` 打印生成的技能卡。发布与同步另有专用 CLI。

---

## 3. 写一个插件

### 3.1 生命周期命令

```bash
openclaw plugins init            # 脚手架
openclaw plugins build
openclaw plugins validate
openclaw plugins pack
openclaw plugins install <package>
openclaw plugins inspect <name>
openclaw plugins doctor
openclaw plugins enable|disable <name>
openclaw plugins update
openclaw plugins uninstall <name>
openclaw plugins registry
openclaw plugins marketplace list|entries|refresh
```

### 3.2 包形态的硬性要求

`package.json` 必须声明 `openclaw.extensions`，指向**构建后的**运行时文件（通常是 `./dist/index.js`）：

```json
{
  "name": "@openclaw/my-plugin",
  "version": "1.2.3",
  "openclaw": {
    "extensions": ["./dist/index.js"]
  }
}
```

报 `package.json missing openclaw.extensions` 就是这个形态不对——补上、重新发布、再 `openclaw plugins install`。

### 3.3 安全姿势

- 插件清单会在导入运行时代码**之前**被校验；但原生插件最终仍在进程内运行，**没有沙箱**。
- 缓解手段：白名单（`plugins.allow`）、安装策略钩子、锁版本、锁依赖、CI 强制的 SDK 边界。
- SDK 面上有依赖解析、子路径导出、打包与版本兼容等规则，`plugins validate` 与 `plugins doctor` 是第一道自检。

---

## 4. 排错阶梯（先跑这八条）

```bash
openclaw triage
openclaw status
openclaw status --all
openclaw gateway probe
openclaw gateway status
openclaw doctor
openclaw channels status --probe
openclaw logs --follow
```

每条的「好输出」长什么样：

| 命令 | 通过的样子 |
|---|---|
| `triage` | 写出一份脱敏的、可直接交给 agent 的诊断；Gateway 可达时还会附支持归档。**在你没有选择交给某个 agent 之前，什么都不会离开本机**，而且提示里排除了密钥、token、原始聊天负载与原始日志 |
| `status` | 配置的通道都在，没有认证错误 |
| `status --all` | 产出一份完整的、可分享的报告 |
| `gateway probe` | `Reachable: yes`。`Read probe: limited - missing scope: operator.read` 属于诊断降级，**不是**连接失败 |
| `gateway status` | `Runtime: running`、连通性探针 ok、能力级别合理；加 `--require-rpc` 还要求读作用域 RPC 证明 |
| `doctor` | 没有阻塞性配置或服务错误 |
| `channels status --probe` | Gateway 可达时给出逐账号的真实传输状态；不可达时退回只读配置摘要 |
| `logs --follow` | 有稳定活动，没有反复出现的致命错误 |

`triage` 是前门：它做只读健康检查，生成一份脱敏提示，然后**询问**要不要把这份诊断交给它在本机检测到的编码 agent；也可以选择「只打印命令」自己跑。

---

## 5. 第一类：Gateway 起不来

症状与处置：

| 症状 | 先查什么 |
|---|---|
| 端口被占 | 默认 18789；`--dev` 模式换 19001 并偏移派生端口。用 `openclaw gateway status` 与系统侧端口占用对照 |
| 拒绝启动并提示 token 有问题 | 检查是不是把文档里的示例占位值原样粘进了 `OPENCLAW_GATEWAY_TOKEN`。Gateway 明确拒绝文档占位值 |
| 前台能跑、装成服务后不行 | 服务托管方式按平台不同（LaunchAgent / systemd 用户单元 / 计划任务）；Windows 计划任务创建被拒会回退到启动文件夹登录项，确认回退路径是否生效 |
| 启动即退、有锁相关报错 | 同一主机只能有一个 Gateway 持有某个消息账号的会话；确认没有第二个实例 |
| 升级后启动异常 | `openclaw doctor`，必要时 `openclaw doctor --fix` 走状态库迁移；再考虑 `openclaw update repair` |
| 状态目录/配置路径串了 | `--dev`、`--profile <name>` 会改状态目录；显式设过 `OPENCLAW_STATE_DIR` / `OPENCLAW_CONFIG_PATH` 的以显式值为准 |

诊断资产：

```bash
openclaw gateway diagnostics export
openclaw gateway stability
openclaw gateway restart
openclaw gateway uninstall && openclaw gateway install
```

---

## 6. 第二类：通道连不上

1. `openclaw channels status --probe` 拿到逐账号真实状态；只看 `channels list` 的配置摘要会骗你。
2. 看死信：`openclaw channels dead-letters list`，处理后 `resubmit`。
3. 看通道日志：`openclaw channels logs`。
4. **它不回消息**：群聊默认要靠 @ 提及激活；私聊默认对未知发件人走配对——`openclaw pairing list` 看有没有卡住的待批请求。
5. **登录态过期**：`openclaw channels logout` 之后重新 `openclaw channels login --channel <id> --account <name>`；WhatsApp 这类要走扫码。
6. **机器人权限不够**：不同平台要求不同（例如需要消息内容意图、需要被拉进目标群、需要相应的管理权限）。平台侧改完记得重启 Gateway。
7. **能力不对**：`openclaw channels capabilities` 看这条通道到底支持哪些消息操作——很多「命令没反应」其实是该通道不支持这个子命令。
8. 局域网或 tailnet 上新设备连不上：**非本地连接一律要显式配对批准**，本地回环才有自动批准。

---

## 7. 第三类：工具像被阉割了 / 被策略挡住

「它只会聊天不干活」几乎都是工具可见性问题，按这个顺序查：

1. **档位**：`openclaw status`、`openclaw status --all`、`openclaw doctor`。确认 `tools.profile` 是什么——`minimal` 只给会话状态查询，`messaging` 很窄，`coding` 是新本地配置默认，`full` 才去掉限制。
2. **按 agent 的覆盖**：`agents.entries.*.tools` 可能在根档位之上又收窄了。
3. **允许/拒绝策略**：被全局或按 agent 拒绝的工具，开沙箱也救不回来。
4. **沙箱**：`openclaw sandbox explain [--session <key>] [--agent <id>]` 看生效模式、宿主 workspace、运行时工作目录、挂载与工具策略，并直接告诉你该改哪个配置键。
5. **通道权限**：工具在某个通道里可能没有权限。
6. **插件是否启用**：`openclaw plugins list` 看状态，`openclaw plugins doctor` 查一致性。
7. **approvals / exec-policy**：命令被拦不等于工具不存在。`openclaw approvals get` 与 `openclaw exec-policy show` 看当前审批与执行策略；`/exec` 只能收紧，放宽要改配置。
8. **作用域**：Gateway 认证如果没有读作用域，很多诊断会降级显示，看起来像「工具没了」，其实是「你看不到」。

判断「到底是谁挡的」的一行心法：**先工具策略，再沙箱，最后才是模型**。

---

## 8. 第四类：模型报错

| 症状 | 处置 |
|---|---|
| 加了认证但用起来还是老模型 | **增加 provider 认证不会改主模型**。用 `openclaw models set <provider>/<model>` 显式切换 |
| 认证明明配了却不生效 | `openclaw models auth list` 确认存在；`openclaw models auth order get` 看轮换顺序；再看环境变量与配置键的优先级 |
| 长上下文返回 429 | 这是上游的上下文/配额限制，先降上下文（压缩、裁剪会话、拆子任务），或换到配额更宽的模型 |
| 本地 OpenAI 兼容后端直连能用、经 Gateway 就失败 | 基本不是网络问题，查 base URL 与路由整形规则；先用最小调用（`openclaw infer model run`）复现，再改 provider 配置 |
| 主模型挂了整个任务失败 | 配降级链：`openclaw models fallbacks add <model>`，图像类另配 `openclaw models image-fallbacks add <model>` |
| 想先看有哪些能力面 | `openclaw infer list`、`openclaw infer inspect <capability>`、`openclaw infer model providers` |

---

## 9. 升级、迁移与回滚

```bash
openclaw backup create && openclaw backup verify      # 先备份并验证
openclaw update status
openclaw update wizard
openclaw update --channel dev|stable                  # 在包安装与 git checkout 之间切换
openclaw update repair
openclaw update                                       # 日常升级
openclaw doctor --fix                                 # 状态库迁移
openclaw migrate list
openclaw migrate plan <provider>
openclaw migrate apply <provider>
```

原则：

- **升级前必备份**。版本检查只能守卫升级，不保证每一次升级都成功。
- 状态是带 schema 版本的、迁移有归属，所以正规做法是 `doctor` 负责迁移、`backup` 负责可回退，而不是就地手改状态库。
- 旧版本遗留的会话级 exec 策略在升级后**不再被运行时读取**，要在 `openclaw doctor --fix` 里迁移；限制性策略迁移时不会放宽。
- 跨机器迁移用 `openclaw migrate`，不要直接拷 `~/.openclaw` 整目录。
- 运维姿态：把部署当**可替换基础设施**——坏了按验证过的备份重部署。

---

## 10. 日志、审计与可观测

```bash
openclaw logs
openclaw logs --follow
openclaw audit
openclaw security audit
openclaw security audit --deep
openclaw secrets audit
openclaw secrets reload|store|configure|apply
openclaw transcripts list|show|path
openclaw status --usage
```

- 日志级别可用全局参数 `--log-level <level>` 覆盖；`--no-color` 关 ANSI。
- 审计面分几层：命令/操作审计、安全体检、密钥体检、消息审计。定期跑 `openclaw security audit --deep`，并对它的检查项 ID 设告警。
- 可观测性通过插件导出（例如 OpenTelemetry、Prometheus 两类插件），导出目标的**保留策略与监控归你**，包括「数据被丢」这件事也要监控。
- 遥测默认行为：只做每日一次版本检查，匿名功能统计默认关闭，配置里设 `update.checkOnStart: false` 两者一并关。

---

## 11. 卸载与清理

```bash
openclaw uninstall          # 移除 CLI 与服务
openclaw gateway uninstall  # 只移除托管服务
openclaw daemon uninstall
openclaw reset              # 重置配置
```

卸载前想清楚三件事：状态目录 `~/.openclaw` 里有哪些凭证与记忆要留档；系统服务单元/计划任务是否也随之移除；容器化部署下卷与镜像要不要一起删。命令跑完不等于文件没了，自己核对一遍。

---

## 12. 常见误判（写下来省时间）

| 误判 | 事实 |
|---|---|
| 「装了就有沙箱保护」 | 沙箱与 exec 审批**默认关闭**。默认形态是受信任的单操作者助手 |
| 「一个 Gateway 能给多个租户用」 | 一个 Gateway 就是一个信任域。多租户要一租户一 Gateway；`fleet` 仍是实验特性 |
| 「插件是隔离运行的」 | 原生插件在当前进程内跑，没有沙箱 |
| 「角色配置就是安全边界」 | 角色与会话归属只是协作护栏，不是隔离机制 |
| 「配对过了就随便连」 | 非本地连接每次都要走配对批准；本地回环才有自动批准 |
| 「出口白名单能拦住一切外发」 | 它只覆盖配合的流量；未沙箱化的宿主 `exec` 的原始 socket 归你的代理或宿主策略管 |
| 「删了记忆就没了」 | 删除只覆盖被追踪的产物；直接写入、hook 写入与原始转录不在范围内 |
| 「升级是安全的，因为发布有签名」 | 签名与版本守卫保证的是「可追溯、有检查」，不保证升级一定成功 |
| 「许可证是 MIT 就可以随便用」 | npm 包元数据与 README 声明 MIT，但仓库根 `LICENSE` 与标准 MIT 模板有差异（许可证识别结果为 `Other`）。商用或二次分发前读全文 |
| 「默认就在给上游发数据」 | 默认只做每日一次版本检查，匿名统计默认关；想彻底关掉用 `update.checkOnStart: false` |
