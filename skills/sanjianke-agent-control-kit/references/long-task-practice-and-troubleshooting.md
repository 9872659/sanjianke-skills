# 长任务实践与排错

> 上游项目：[loopx](https://github.com/huangruiteng/loopx)（Apache-2.0）。本文是三剪客团队在跨天任务上的实际操作口径与故障处理路径。

## 1. 每天开工的三条命令

不用多，三条就够：

```bash
loopx status
loopx history --goal-id <goal-id>
loopx quota should-run --goal-id <goal-id>
```

- `status`：目标、闸门、注意力队列、下一步动作。先看**有没有一个具体的用户闸门在等我**，那是唯一必须由人处理的东西。
- `history`：紧凑运行历史。看最近几轮的**结论**，不是看过程。
- `quota should-run`：这一轮到底该不该跑、跑哪种。任何自动轮动手前都必须先问这一条。

收尾再加一条，把交接包发给下一个 agent 或自己：

```bash
loopx review-packet --goal-id <goal-id>
```

## 2. 怎么判断它是在真推进，还是在空转

盯四个地方，比盯日志有效得多：

1. **看回写里有没有内聚产物。** 一段实现加一次验收，比十轮「已检查状态」有价值。
2. **看 `long_task_cadence_hint.signal`。** 连续出现 `thin_progress` 就要介入（见第 3 节）。
3. **看 `event_ledger_summary`。** 证据事件和工作事件在增长，说明有实质动作；只有状态事件在涨，就是在打转。
4. **看用户待办有没有一直挂着。** 只要还有 open 的用户待办，就不许把这轮报告成「没有新的用户动作」——报告里必须列出这些待办。

## 3. 节拍信号怎么读、怎么动手

| signal | 建议 | 你该做什么 |
|---|---|---|
| `blocked` | `wait` | 不放宽范围，把那个具体闸门或阻塞点摆到人面前 |
| `active_work` | `keep` | 跟随最终裁决；`superseded` 只用来诊断，不要拿它改结论 |
| `thin_progress` | `widen` | 要求下一轮产出一个内聚产物 + 验收/回写，或者写明为什么放宽不安全 |
| `thin_progress` | `keep` | 连续次数还不够，先不动节拍；但记下这是个观察点 |
| `material_progress` | `keep` | 已经有实质推进，别乱改自动化 |
| `unknown` | `keep` | 元数据不足，不要做激进的自动化调整 |

一个真实的坑：早期兼容性建议可能说 `wait`，但最终 agent 作用域通道要求必须尝试、且不允许静默空转时，配额会把建议改写为 `active_work` + `keep`，并在 `authority` 里点名裁决者、把早先的信号留在 `superseded`。**这个改写不适用于真正阻塞的用户闸门**——闸门就是闸门。

## 4. `quota should-run` 的字段含义

这是心跳必须遵守的机器契约，逐条看：

| 字段 | 含义 |
|---|---|
| `should_run` | 现在是否可以跑交付工作 |
| `waiting_on` | 在等谁：user、controller、Codex、外部证据、health 还是 quota |
| `work_lane_contract` | 下一条可执行泳道，或监控/阻塞泳道 |
| `execution_obligation` | agent 是否**必须**尝试一段有界工作 |
| 用户/agent 待办摘要 | agent 待办会区分 `first_executable_items` 与 `monitor_open_items`：前者驱动主行动，后者是补充观察上下文，只有在产生实质转变或阻塞时才花算力 |
| 安全绕行 / 自修复提示 | 仅在显式启用时出现 |
| 花费策略 | 精确的记账口径 |

两个衍生点：

- 返回 `gate_prompt` 或 `operator_question` 时，心跳应当**主动去问那个具体问题**，而不是自己编一个更模糊的等法。
- `safe_bypass_allowed=true` 时，心跳仍可做**一步**与受阻闸门无关的有界只读引导或分析。注意是「无关且只读」，不是绕过闸门。
- `control_plane.self_repair.enabled=true` 时，`quota should-run` 可以对可修复的控制平面停滞返回 `decision=self_repair` 的有界契约；策略缺失时默认关闭，其他目标保持正常的跳过或等待行为。

## 5. 心跳怎么配

生成受保护的心跳正文：

```bash
loopx heartbeat-prompt --thin --goal-id <goal-id>
```

- **首次接入的心跳装 3 分钟引导节拍**，除非用户明确要求别的间隔。
- 之后**跟随 `quota should-run.scheduler_hint`**，不要自己写死一个「每 5 分钟」。
- 使用了 Codex App 自动化时，用返回的 `ack_hint.cli_args` 认领当前提示。

多 Agent 共用一个控制平面时，身份与范围必须写进自动化提示词：

```bash
loopx register-agent --goal-id <goal-id> \
  --agent-id codex-main-control \
  --agent-id codex-side-bypass \
  --execute

loopx heartbeat-prompt --compact --goal-id <goal-id> \
  --agent-id codex-side-bypass \
  --agent-scope "control-plane coordination"
```

**一旦 registry 里设了 `coordination.registered_agents`，不带 `--agent-id` 调 `heartbeat-prompt` 就会 fail closed。** 这是刻意设计：让过期的 Codex App 自动化报出升级错误，而不是静默地以无身份、无范围的状态运行。老 registry 缺这个字段时，只要带范围的调用点了 agent 名，同样 fail closed——所以先注册身份，别让 worker 现编认领 id。

新身份默认是新建：`agent-onboard` 或不带 `--agent-id` 的 `start-goal --guided` 会走新 agent 注册的预览/应用命令。**只有一个已注册 agent 并不构成「接管它」的意图**；要接管必须用户明确说了。新路径用 `--require-new`，预览只是参考——必须等执行结果报告 `ok=true`、`changed=true`、`written=true`、全局同步成功，并且读回校验过源/全局注册，才能继续。

## 6. 记账：什么时候花槽，什么时候不花

只有**真的花掉交付算力**的自动轮，才追加一条花费事件：

```bash
loopx quota spend-slot --goal-id <goal-id> --slots 1 --source heartbeat --execute
```

**以下三种一律不记账**：

- `should_run=false` 的静默跳过；
- 预检失败；
- 纯 dry-run 预览。

默认粒度下一槽等于一分钟算力（`slot_minutes` 默认 1）；粗粒度控制器应按调度分钟数花对应槽数。

## 7. 待办的生命周期

加显式工作：

```bash
loopx todo add --goal-id <goal-id> --role user \
  --text "Review the owner checklist."

loopx todo add --goal-id <goal-id> --role agent \
  --text "Summarize the safe read-only evidence." \
  --task-class advancement_task --action-kind evidence_summary
```

完成一个 agent 待办，同时原子地挂上下一个可执行项：

```bash
loopx todo complete --goal-id <goal-id> \
  --todo-id todo_ab12cd34ef56 \
  --evidence "Validated with examples/demo-cli-smoke.py" \
  --next-agent-todo "Run the next bounded validation slice." \
  --next-task-class advancement_task --next-action-kind validation \
  --execute
```

本地状态或文档变化后追加一次纯状态刷新：

```bash
loopx refresh-state --goal-id <goal-id>
```

对等体在**交付前** `todo claim`，在**验收后** `todo update`，归属和证据才留得下来。并发写同一片工作时，用硬租约：

```bash
loopx task-lease --help      # 获取、续期、转移、释放、查看
```

## 8. 多 Agent 的隔离纪律

- 写仓库的 peer 在任务或目标策略要求时，必须使用**独立 worktree**；隔离缺失时 `workspace_guard` fail closed。
- 小的、符合 AGENTS 规范且已验收的改动，可以带着明确的 loopx 证据自行合并。
- 更高风险的改动，创建独立的后续者，或走普通的 `independent_handoff`（`action_kind=review`）。
- 只有在必须强制「执行者 ≠ 复核者」时，才用 `excluded_agents`。
- 主控与旁路 worker 通过同一个账本协调，才不会「重复花槽、藏阻塞、在陈旧状态上打架」。

## 9. 备份、恢复与状态回滚

**在危险迁移、本地调度变更或发布修复之前**，先做归档预览：

```bash
loopx backup-state --project .              # 只读预览
loopx backup-state --project . --execute    # 确认无误再落盘
```

默认写到 `~/.codex/loopx/backups`，内容涵盖共享运行根、Codex App 自动化、已安装的 `loopx-*` 技能、当前项目状态，以及**每一个可达项目**的 `.loopx`、`.codex/goals`、`.claude/goals`、`.local/goals`、registry 声明的活跃状态和源 registry。只有在你确定要一个很窄的归档时，才用 `--current-project-only`。

两个读数细节：预览里报的是**压缩前的逻辑源字节**，不是最终归档体积；`--execute` 之后要看 `archive_size_bytes` 和归档/逻辑比值来估真实存储成本。归档和清单属于私有恢复材料，不要提交、不要外发。

只想暂停目标、不删历史时，用生命周期命令而不是手工删目录：

```bash
loopx goal-lifecycle --help    # 预览、停止、恢复
```

## 10. 历史索引冲突怎么重建

历史写入者会原子地预留它的 JSON/Markdown 产物对。若旧运行时报告了遗留的索引身份冲突，**先看完整重建计划，再动索引**：

```bash
loopx --format json history rebuild-index-collisions \
  --goal-id <goal-id> | jq '.review_plan' > reviewed-plan.json

loopx history rebuild-index-collisions \
  --goal-id <goal-id> \
  --review-plan-json reviewed-plan.json \
  --execute
```

执行路径要求**完全一致**的已复核计划，会保留重建前的索引备份，并且对归属不明的遗留产物**只保留不猜**。被截断的计划不可执行——先把 `--limit` 调大，看清完整摘要再说。

## 11. 故障定位表

| 症状 | 大概率原因 | 处理路径 |
|---|---|---|
| `loopx status` 说没连上项目 | 项目没 bootstrap / registry 缺失 | 在项目根 `loopx connect`；仍不行用 `loopx start-goal --guided --project .` |
| status 长期显示「等待」但没有具体问题 | 闸门没被具体化，或只是在等配额 | 看 `waiting_on` 到底是 user 还是 quota；是 user 就必须落成一个具体问题 |
| 自动轮一直跑但没推进 | 节拍被切碎 | 看 `long_task_cadence_hint`；`thin_progress` + `widen` 时要求产出内聚产物 + 验收 |
| `heartbeat-prompt` 报错退出 | registry 已设 `coordination.registered_agents` 但调用没带 `--agent-id` | 先 `register-agent ... --execute`，再带 `--agent-id` 重生成 |
| `register-agent` 提示全局 registry 写入被拒 | `~/.codex/loopx/registry.global.json` 不可写 | 修运行根权限或换可写宿主重跑；只有明确要本地专用连接才加 `--no-global-sync` |
| 两个 agent 重复干同一件事 | 没有认领/租约 | 交付前 `todo claim`，必要时 `task-lease`；高风险改动走 `independent_handoff` |
| 写仓库的动作被 `workspace_guard` 挡 | 需要独立 worktree 的隔离没建立 | 按策略建独立 worktree，而不是绕守卫 |
| `history` 报索引冲突 | 遗留索引身份冲突 | 走第 10 节的两步重建，不要手改索引文件 |
| 升级后行为不一致 | 宿主材料 / 托管运行时 / 扩展三层里有一层陈旧 | 逐层读回（见 `install-and-connect.md` 第 7 节），别混通道 |
| 心跳在没有任何有效转变时继续花算力 | 没先问 `quota should-run` | 所有自动轮入口统一先查配额；跳过的轮不记账 |
| 状态迁移前想留退路 | 没有归档 | `loopx backup-state --project .` 预览，确认后 `--execute` |
| 对外发布被边界扫描拦下 | 命中了私有材料 | 清掉真实本地路径、任务 id、生产日志、原始实验指标、凭证、活跃目标状态后再扫 |

## 12. 交给 agent 自诊断

不要自己一条条敲命令。把下面这段直接丢给你的 harness，让它自己跑、自己判断：

```text
端到端诊断这个项目的 loopx，不要让我去敲 shell 命令。

如果 loopx 不存在，先装或修好它。然后你自己跑 loopx diagnose，
读诊断包，用你的推理告诉我：
- 这个项目现在能不能自驱；
- 支撑这个结论的证据是什么；
- 如果卡住了，卡在哪；
- 如果存在用户/控制器闸门，我需要回答的那个具体问题是什么；
- 你接下来要做什么。

不要把 loopx 的机器信号当成最终判决，它只是你诊断用的证据。
```

`loopx diagnose` 会收集紧凑的 status、`quota should-run`、待办、交互契约和边界信号，再给 agent 一张推理清单——**判断是 agent 做的，信号只是输入**。

## 13. 发布前的边界扫描

任何要对外发布的文档、示例或产物，先扫一遍：

```bash
loopx check \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

**可以公开**：registry schema 与运行时布局、适配器生命周期与通用控制平面契约、脱敏示例与 smoke fixture、通用校验命令。

**必须留在本地**：真实本地路径、任务 id 与内部文档链接、生产日志与原始实验指标、凭证与认证材料、用户特定的活跃目标状态与本地 registry、原始 agent 会话或基准 trace。

顺带一句：`loopx first-run-report` 只在本机打印同样内容的预填回执，**不会把任何东西发出去**，也没有遥测。
