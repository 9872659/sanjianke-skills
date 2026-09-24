---
name: sanjianke-drama-engine
slug: sanjianke-drama-engine
displayName: 三剪客 · AI 短剧量产引擎
description: "三剪客 · AI 短剧量产引擎：把一本小说变成能投放的短剧，一整套跑通「策划 → 编剧 → 分镜 → 出片」的工业化流程。覆盖本地 / Docker / 云服务器三种部署、文本图像视频三类模型接入、章节事件图谱、故事骨架与付费卡点设计、分镜表十三铁律与片段过渡四类桥梁、11 个画风包与 12 个题材包的选用和自定义、出片成本估算与全链路排错。适用于批量出片、小说改编可行性评估、自建画风或题材技能包。遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "三剪客 · AI 短剧量产引擎：短剧工业化量产作战体系。三种部署方式、三类模型配置、编剧阶段的故事骨架规范（矛盾四级阶梯、三大密度、付费卡点比例公式）、制片阶段的分镜表十三铁律与片段过渡四类桥梁、11 个画风包与 12 个题材包的选用与自定义、成本估算与排错。三个离线脚本开箱可用：成本估算、技能包脚手架、结构校验。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 短剧
  - 小说改编
  - 批量出片
---

# 三剪客 · AI 短剧量产引擎

把一本小说，变成能投放的短剧。

这里是一整套跑通「策划 → 编剧 → 分镜 → 出片」的**工业化流程**——不是零散技巧，
而是可以直接照着执行、批量复制的作业体系。底下驱动的工具是开源项目 Toonflow，
本文覆盖它的全部关键环节。


## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **不申请** | 本 Skill 全程离线，不发起任何网络请求 |
| 读取文件 | 仅读取用户指定的目录或原著文件 | 供稿件分析、技能包结构校验 |
| 写入文件 | 仅在用户指定 `--out` 时 | 脚手架脚本生成技能包目录 |
| 凭证 | **不读取** | 本 Skill 不接触任何 API Key 或账号信息 |
| 子进程 / 后台常驻 | 不申请 | 三个脚本执行完即退出 |

**本 Skill 不内嵌任何密钥，不访问任何外部地址。** 涉及 Toonflow 的操作都需要使用者
自己在本机安装并运行该软件，本 Skill 只提供规范、判断依据和离线工具。

## 触发场景

- 想把一本小说改编成短剧，要评估可行性和改编方案
- 已经在用 Toonflow，但成片质量不稳定（剧情跳、角色漂移、节奏平）
- 要审 Toonflow 产出的故事骨架、分镜表，需要判断标准
- 要把 Toonflow 装到本机或服务器上，或配置模型供应商
- 想自己做一套画风包或题材包，需要目录规范和脚手架
- 要估算一部剧的出片成本

**不适用于**：单纯想剪已有视频（那是剪辑工具的活）、想直接生成成片而不经过改编流程。

## 快速开始

先问清三件事：**原著体量**、**集数与单集时长**、**成片走哪条路线**（本地 / 云端）。

```bash
# 1. 先算钱，再动手
python3 scripts/cost_estimate.py --episodes 30 --minutes 2

# 2. 要自建画风或题材包时，生成骨架
python3 scripts/new_toonflow_skill.py --kind art --name 2D_ink_wash --out ./my-skills

# 3. 建完校验结构（能查出手建最容易犯的目录名拼写错误）
python3 scripts/check_toonflow_skill.py ./my-skills/2D_ink_wash
```

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 装 Toonflow（本机 / Docker / 云服务器）、配模型 | `references/quickstart.md` |
| 搞清整条流水线怎么走、无限画布怎么用 | `references/pipeline.md` |
| 改小说、审故事骨架、设计付费卡点 | `references/script-stage.md` |
| 审分镜表、片段过渡、出片质检 | `references/storyboard-stage.md` |
| 搞清内置的 13 个 Agent 提示词和技能体系 | `references/builtin-skills.md` |
| 自己做一个画风包或题材包 | `references/custom-skills.md` |
| 选模型、算成本、省钱 | `references/models-and-cost.md` |
| 出问题了 | `references/troubleshooting.md` |

---

## 工作流 A：改编可行性评估（还没装软件）

用户拿着一本小说问「能不能改」时，别急着让他装软件。先做三件事：

1. **看体量与结构**：多少章、多少字、是否单线推进。短剧要单线，
   多线并行的长篇改起来会丢掉大半。
2. **找核心矛盾**：主角的「强欲望」和「强阻碍」分别是什么？
   对照**矛盾四级阶梯**判断在第几级——低于 3 级基本是平淡剧。
3. **看爽点类型**：属于优势/金手指、归属、还是秩序型？
   金手指是否新颖（市面出现 >10 次就别用）、是否有约束。

给出结论时要直说：**这本小说适合改 / 需要大改 / 不适合改**，以及理由。
不要含糊其辞地说「可以试试」。

详见 `references/script-stage.md`。

---

## 工作流 B：部署与模型配置

三种路线，先问用户属于哪种：

| 用户情况 | 路线 |
|---|---|
| 只想用 | 下 Release 安装包 |
| 要调提示词、接自己的模型 | `yarn dev:gui`（Electron 桌面端） |
| 团队用、要长期跑 | 云服务器 + PM2，或 Docker |

配完模型**必须检查两处**（这是最高频的坑）：

1. 模型服务里三个调用开关是否都开着
2. Agent 配置里各 Agent 引用的模型是否与所配一致

命令、PM2 配置、环境变量、`OSSURL` 陷阱详见 `references/quickstart.md`。

---

## 工作流 C：审故事骨架

用户拿来一份 Toonflow 生成的故事骨架要你判断时，逐条对：

- 压缩比 ≤40%？
- 每集有集末钩子？抽 3 集看
- 章节号能在事件表里找到？对不上就是编造
- 大三角贯穿始终？
- 核心矛盾在第几级？低于 3 级要打回
- 金手指有约束吗？没边界就是无敌外挂
- 人物小传 ≤4 人？
- 反派动机合理？「纯嫉妒」要打回
- 五个卡点按 N×10/30/50/70/90% 落位？**卡在主线上？**
- 前 10 集能剪出约 10 个 30 秒爆点？
- 结局是爽剧收尾？

完整清单和每条的理由见 `references/script-stage.md`。

**关键判断**：骨架阶段的问题必须在这一步拦下。改一句话的成本，
到分镜阶段是十几张图，到出片阶段是几百块。

---

## 工作流 D：审分镜表

Toonflow 的分镜表有 **13 条铁律 + 9 条红线**，写死在提示词里。审的时候按同一套标准：

最容易出问题的几条：

| 铁律 | 违反的表现 |
|---|---|
| 台词零删改 | 台词被精简、合并、省略修饰词 |
| 在场人物不能消失 | 剧本没写「离开」，人却在分镜里没了 |
| 人物外观交给图片资产 | 分镜提示词里出现服装/发型/长相 |
| 声音只写环境音 + 音效 | 出现 BGM、配乐、音乐 |
| 长台词超 20 字强制拆镜 | 长台词挤在一个固定镜头里 |
| 片段 ≤15 秒 | 有超长片段 |

另外专门查**片段间过渡**有没有做——这是分镜质量的分水岭。
四类桥梁（动作、情绪、空间与视线、台词与动作的黏合）见 `references/storyboard-stage.md`。

---

## 工作流 E：自建画风 / 题材技能包

先判断用户要改的是**画面**还是**讲故事**：

- 画面不对味（色彩、质感、长相）→ **画风包** `art_skills/`
- 节奏不对味（燃点、情绪、镜头）→ **题材包** `story_skills/`

```bash
python3 scripts/new_toonflow_skill.py --kind art --name 2D_ink_wash --out ./my-skills
python3 scripts/check_toonflow_skill.py ./my-skills/2D_ink_wash
```

**必须提醒用户的一件事**：导演目录名是 `driector_skills`——上游把 director 拼错了，
但**必须照抄**。写成 `director_skills` 不会报错，只会静默不加载。
校验脚本专门查这一条。

各文件该写什么、自检清单、七种常见错误见 `references/custom-skills.md`。

---

## 工作流 F：成本估算

```bash
python3 scripts/cost_estimate.py --episodes 30 --minutes 2
python3 scripts/cost_estimate.py --minutes 2 --video-price 1.2 --waste 0.5
python3 scripts/cost_estimate.py --minutes 2 --json
```

默认单价按官方 Demo 反推校准（约 2 分钟成片 ≈ ¥130），**不是报价**——
请使用者把真实单价传进来。

**要传达的核心结论**：视频生成占九成以上成本。省钱唯一有效方向是
**减少要生成的视频秒数**，而不是省图片钱（图片不足总额 1%）。

---

## 脚本清单

| 脚本 | 作用 |
|---|---|
| `scripts/cost_estimate.py` | 出片成本估算，按集数/时长/单价/废片率算 |
| `scripts/new_toonflow_skill.py` | 生成画风包或题材包骨架（结构与上游一致） |
| `scripts/check_toonflow_skill.py` | 校验技能包目录结构，专查目录名拼写错误 |
| `scripts/selftest.py` | 上面三个脚本的自测 |

全部零依赖，只用 Python 标准库。改动脚本后先跑自测：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/selftest.py -v
```

## 调用示例

**估算一句话的成本预期**：

```bash
python3 scripts/cost_estimate.py --minutes 2
# → 合计 ¥132.67，其中视频模型 ¥121.82（91.8%）
```

**判断一个画风包为什么没生效**：

```bash
python3 scripts/check_toonflow_skill.py ./broken-skill
# → [!] 警告：发现 director_skills 目录，但 Toonflow 读的是 driector_skills，请改名
```

**批量建包**：

```bash
python3 scripts/new_toonflow_skill.py --kind story --name Time_travel --out ./my-skills
python3 scripts/new_toonflow_skill.py --kind story --name Cyber_punk --out ./my-skills
```

## 能力边界

**覆盖**：

- Toonflow 的部署、配置、流水线、提示词体系、成本与排错的完整规范
- 短剧改编与分镜的方法论判断标准（矛盾四级阶梯、三大密度、付费卡点、分镜铁律）
- 三个离线工具：成本估算、技能包脚手架、结构校验

**不覆盖**：

- **不代替 Toonflow 本身**：本 Skill 不含该软件，也不能驱动它出片。
  所有生成动作都要使用者在本机/服务器上跑 Toonflow 完成
- **不调用任何 API**：不联网、不需要 Key、不产生任何费用
- **不保证成片质量**：方法论能提高稳定性，但成片效果取决于所用模型、原著质量与执行
- **不替代版权审查**：改编他人作品需要授权，本 Skill 不判断版权归属，
  也不提供规避授权的写法
- **不提供 Toonflow 的技术支持**：软件本身的 Bug 请走上游仓库的 Issues

## 依赖条件

- Python 3.8+，**仅标准库，无第三方包**
- 要实际出片的话，另需：本机或服务器装好 Toonflow、三类模型供应商的 API Key

## 已知限制

- **成本参数是校准值不是报价**：默认单价按官方 Demo 反推，
  实际价格随模型和供应商变化，需要使用者传真实单价
- **框架会变**：Toonflow 迭代较快（上游已到 v1.1.x），
  文件结构、路由、命令可能随版本变化。规范里涉及具体路径的地方，
  以使用者本机的实际版本为准
- **画风/题材清单取自 master 分支**：11 个画风包 + 12 个题材包是撰写时的快照，
  新版本可能增删
- **不覆盖 Toonflow 的 REST API**：它的后端有完整路由（端口 10588），
  理论上可以脚本化驱动生产，但接口未公开文档化，本 Skill 不做这部分

## 自检清单

用本 Skill 交付前自查：

- [ ] 涉及安装/配置的建议，是否核对过使用者实际的版本与系统？
- [ ] 给成本数字时，是否说明了那是校准值、需要换真实单价？
- [ ] 审骨架时，是否逐条对了那 12 项而不是泛泛说「还行」？
- [ ] 审分镜时，是否专门查了片段间过渡？
- [ ] 涉及自建技能包时，是否提醒了 `driector_skills` 的拼写陷阱？
- [ ] 涉及改编他人小说时，是否提示了版权授权是前提？
- [ ] 有没有把本 Skill 的方法论说成「保证出片质量」？

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/quickstart.md` | 三种部署方式、模型配置、项目结构 |
| `references/pipeline.md` | 全流程、三层 Agent、无限画布、推进顺序 |
| `references/script-stage.md` | 事件图谱、故事骨架、矛盾阶梯、付费卡点 |
| `references/storyboard-stage.md` | 分镜表格式、13 铁律、过渡桥梁、9 红线 |
| `references/builtin-skills.md` | 13 个 Agent 提示词、11 画风包、12 题材包 |
| `references/custom-skills.md` | 自建技能包的目录规范与自检 |
| `references/models-and-cost.md` | 模型分工与配置、成本结构与省钱 |
| `references/troubleshooting.md` | 按症状排错、数据备份 |

## 上游项目

本 Skill 由三剪客出品，独立编写。

底层的 Toonflow 是开源软件（Apache-2.0），与本团队无隶属关系。

| 项目 | 地址 |
|---|---|
| Toonflow（主仓库） | [Gitee](https://gitee.com/HBAI-Ltd/Toonflow-app) ｜ [GitHub](https://github.com/HBAI-Ltd/Toonflow-app) |
| Toonflow-web（前端源码） | [Gitee](https://gitee.com/HBAI-Ltd/Toonflow-web) ｜ [GitHub](https://github.com/HBAI-Ltd/Toonflow-web) |
| 视频教程（12 分钟上手） | [B 站 BV1oXD7BqEqJ](https://www.bilibili.com/video/BV1oXD7BqEqJ) |

本 Skill 不包含该项目的任何源代码。

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
