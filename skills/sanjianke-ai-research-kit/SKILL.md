---
name: sanjianke-ai-research-kit
slug: sanjianke-ai-research-kit
displayName: 三剪客 · AI 科研全流程
description: "把选题、查文献、做实验、写论文串成一条可执行流水线；信息抽取/摘要/对比接大模型（`/api/v1/chat/completions`），公网文档问答接 `file_qa`（`/api/v1/apps/file_qa/chat`）。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "覆盖科研四个阶段：选题与头脑风暴、文献检索与综述、实验设计与复现、论文写作与投稿；每阶段给可执行步骤、模板与检查清单，并明确 AI 能做与不能做的事，最终结论由人负责。四段里要动手的动作已接到 api.a7w.cn：`scripts/run.py extract/summarize/matrix/review` 走 `/api/v1/chat/completions`，`doc-qa` 走 `/api/v1/apps/file_qa/chat`，全程零第三方依赖、不编造引用。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 科研
  - 文献
---

# 三剪客 · AI 科研全流程

科研真正拖慢人的，往往不是想不出点子，而是流程断在半路：想法留在聊天记录里，文献散在几个文件夹，
实验配置只活在终端的历史滚动里，等到写论文时已经想不起当初为什么做了那个消融。

这套流程把「选题 → 文献 → 实验 → 写作」四段接成一条线。每一段都给输入契约、可执行步骤、
留痕模板和收尾检查清单，让下一步永远能接上上一步。

它不替你产出结论，也不替你做判断。它负责的是让每一步都有痕迹、可回溯、可被别人复算——
想法为什么被淘汰、某个数字从哪次运行来、某条引用出自哪篇原文，随手就能翻出来。

---

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 需要 | 检索与核对公开文献信息时使用（标题、作者、年份、出处、DOI、语种）；显式调用 `scripts/run.py` 时会请求 `api.a7w.cn` 的大模型与文档问答接口。不向任何站点上传你的稿件、数据或实验配置——**除了你自己主动用 `--file/--text` 交给大模型整理的那部分材料** |
| 读取文件 | 需要 | 读取项目目录内的笔记、检索结果、实验日志、结果文件、`.bib` 与草稿，用于生成综述矩阵、实验台账与写作骨架 |
| 写入文件 | 需要 | 只在项目目录内新建或更新工作区文件（选题池、文献卡、综述矩阵、实验台账、草稿骨架）。不覆盖已有文件，除非你明确要求 |
| 凭证 | 只在调用算力时读取你自己的 Key | Key 从 `--key`、环境变量 `A7W_API_KEY` 或 `~/.a7w/config.json` 读取；**不内嵌、不写入任何交付文件**。需要机构订阅才能打开的数据库，由你在浏览器里自己完成访问 |
| 子进程 / 后台常驻 | 不需要 | 不装后台服务、不常驻进程。只有你要求跑本地脚本时才执行一次性命令 |

本 Skill 不内嵌任何密钥。若你想接入自建的检索服务，凭证放在你自己的环境变量里；
本 Skill 只按变量名读取，不会把它写进任何交付文件。

> 不跑 `scripts/run.py` 时，这份方法论完全不联网：发散、整理、写骨架都能离线做完。

涉及人类受试者、个人隐私数据、生物样本或其他受监管材料的研究，
合规与伦理判断必须走你所在机构的正式审查流程，本 Skill 不能替代。

---

## 触发场景

- 「我只有一个大概方向，不知道能不能做成一个题。」
- 「帮我看看这个方向近三年还有没有空位，主要在争什么。」
- 「我这个想法好像有人做过了，帮我确认一下到底做到哪一步。」
- 「实验跑出来跟预期反了，接下来该怎么走。」
- 「帮我把这堆结果整理成论文的图表顺序和段落骨架。」
- 「投稿之前，请你按审稿人的角度先把我的稿子挑一遍刺。」

---

## 快速开始

最小可用路径：先立工作区，再走四段。

**第 1 步：立工作区**（一次就好，之后所有产物都落在这里）

```text
research/
├─ 00-选题池.md          # 候选选题 + 打分 + 淘汰理由
├─ 01-文献卡/            # 一篇文献一张卡
├─ 02-综述矩阵.md        # 把文献卡横向摊开，找空白
├─ 03-实验台账.md        # 每次运行一行，配置/命令/结果路径
└─ 04-草稿/              # 骨架、图表清单、正文
```

**第 2 步：发散**——把方向原话丢进来，要求出 8~12 个候选，并明确「不要现在评好坏」。
看 `references/01-选题与头脑风暴.md`。

**第 3 步：验证**——对留下的 2~3 个候选各做一轮检索，确认是真空白还是你没搜到。
看 `references/02-文献检索与综述.md`。

**第 4 步：落地**——写一句可证伪的主张，据此定基线、变量、重复次数，开台账。
看 `references/03-实验设计与复现.md`。

**第 5 步：成文**——先定图表，再写正文；投稿前跑一遍审稿人视角预演。
看 `references/04-论文写作与投稿.md`。

每段开工前把该段的检查清单贴到对话里，收尾时逐条打勾再进下一段。

**想少手抄**：四段里那些「要动手做」的动作已经做成命令——
`scripts/run.py` 的 `extract` / `summarize` / `matrix` / `review` / `doc-qa`，
全部走 `api.a7w.cn`，零第三方依赖。命令与参数见下面「怎么用（命令行）」。不跑脚本时，
这份方法论完全不联网。

---

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 把模糊方向变成 1~3 个可证伪的候选选题 | `references/01-选题与头脑风暴.md` |
| 生成检索式、筛选标准、文献卡与综述矩阵，定位空白 | `references/02-文献检索与综述.md` |
| 设计实验、选基线、定重复次数、维护实验台账 | `references/03-实验设计与复现.md` |
| 组织论文骨架、图表顺序、投稿自检与返修应对 | `references/04-论文写作与投稿.md` |

---

## 怎么用（命令行）

四段流程里那些**要动手做**的动作（抽取、摘要、对比、就着一份文档提问）已经接到
`api.a7w.cn` 上，零第三方依赖，本机只要有 Python 3.8+。配 Key：

```bash
python scripts/a7w.py login --key sk-xxxx      # 验证并保存到 ~/.a7w/config.json
export A7W_API_KEY=sk-xxxx                     # Windows: set A7W_API_KEY=sk-xxxx
# 或临时指定：python scripts/run.py summarize --file x.md --key sk-xxxx
```

拿 Key：到 [算力集市](https://api.a7w.cn/) 注册领取，新用户有赠送点数；
**1 元 = 100 点**（1 点 = 0.01 元），失败全额退回。

### 0. 先查模型名，别猜

```bash
python scripts/run.py models --filter deepseek
python scripts/run.py models --category text
```

### 1. 文献卡：从一份材料里抽结构化字段（阶段二）

```bash
python scripts/run.py extract --file 01-文献卡/paper-2024-x.md --out card.json
python scripts/run.py extract --file note.md \
  --fields "研究问题,方法,数据与样本,主要结论,局限,可复用点,待核对项"
```

输出是 JSON，字段固定，方便直接进综述矩阵。材料里没有的字段会写
「未提供(需回原文核对)」，**不会替你编**。

### 2. 摘要：把长材料压成带出处的要点（阶段二 / 四）

```bash
python scripts/run.py summarize --file 长综述.md --length medium --out 摘要.md
```

### 3. 综述矩阵：多份材料横向对比，找空白点（阶段二）

```bash
python scripts/run.py matrix --file a.md --file b.md --file c.md \
  --out 02-综述矩阵.md
python scripts/run.py matrix --dir 01-文献卡/ --out 02-综述矩阵.md
```

产出 Markdown 表 + 「可能的空白点」（逐条标明是「确认没人做」还是
「本次材料里没搜到」）+ 「冲突与分歧」。

### 4. 审稿人预演：投稿前先挑一遍刺（阶段四）

```bash
python scripts/run.py review --file 04-草稿/正文.md --venue "目标会议" --out 预演.md
```

### 5. 文档问答：就着一份**公网**文档提问（阶段一 / 二）

```bash
python scripts/run.py doc-qa \
  --url "https://arxiv.org/pdf/1706.03762" \
  "这篇的核心主张是什么？有哪些消融实验？"
```

`doc-qa` 走平台的文档问答应用，只吃**公网 HTTP(S) 地址**（一次 1~8 个），
**不支持本地文件**；要问本地文件，把内容用 `--text` 贴进 `extract` / `summarize`。

### 6. 裸调一次大模型（自己给 system）

```bash
python scripts/run.py chat --system "只输出 JSON" --prompt "给我 3 个字段名" --json
python scripts/run.py chat --prompt "解释一下注意力机制" --stream
```

## 接入 api.a7w.cn 的真实端点

| 动作 | 接口 | 关键参数 | 备注 |
|---|---|---|---|
| 抽取 / 摘要 / 对比 / 审稿预演 | `POST /api/v1/chat/completions` | `model`、`messages`、`temperature`、`max_tokens`、`stream` | OpenAI 兼容协议；换 `base_url` 与 `model` 名即可，Key 与账单不变 |
| 模型清单 | `GET /api/v1/models` | — | 字段是 `model_code` / `model_name`；上架很快，**先查再猜** |
| 公网文档问答 | `POST /api/v1/apps/file_qa/chat` | `file_urls`（数组，1~8 个公网地址）、`question`、`mode`(sync/async)、`stream` | 正文在 `result.answer`，用量在 `result.usage` |
| 文档结构化解析 | `POST /api/v1/apps/file_qa/parse` | `file_urls`、`parse_mode`、`preserve_original=true`（固定 true，传 false 会被拒） | 异步；剧本/小说/大纲类解析 |
| 访谈录音转写 | `POST /api/v1/apps/voice_tts/stt` | `audio_url`（公网音频地址）或文件上传、`language`、`ignore_timestamps` | 同步；转出来的逐字稿再喂给上面的抽取/摘要 |

裸调用：

```bash
curl -sS https://api.a7w.cn/api/v1/chat/completions \
  -H "Authorization: Bearer $A7W_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"用一句话解释 RAG"}]}'

curl -sS -X POST "https://api.a7w.cn/api/v1/apps/file_qa/chat" \
  -H "Authorization: Bearer $A7W_API_KEY" -H "Content-Type: application/json" \
  -d '{"file_urls":["https://example.org/paper.pdf"],"question":"核心主张是什么？"}'
```

三条必须记住的口径：

1. **`code == 1` 才算业务成功**（不是 0）。HTTP 200 不等于调用成功。
2. **实际扣费看 `usage.points_cost`**（同步接口有时是 `usage.actual_points`）；1 元 = 100 点，失败全额退回。
3. 大模型按**点 / 百万 Token** 计，**输入输出分别计价**；
   `file_qa` 实测输入 2,600 点/百万 Token、输出 13,000 点/百万 Token
   （实测：124 输入 + 70 输出 = 1.2324 点 ≈ 0.012 元）。压 `--max-tokens` 是控成本的主旋钮。

> 「不编造引用」这条纪律已经写进 `scripts/run.py` 的 system prompt：
> 材料里没有的字段一律写「未提供(需回原文核对)」，不生成、不补全、不猜测
> 参考文献条目、作者、年份、DOI 与数字。但**这不能替代你回原文核对**。

---

## 能力边界

**覆盖**：

- 把一句模糊方向收敛成 1~3 个候选选题，给出打分、淘汰理由和「若结果相反会怎样」
- 生成检索式与纳入/排除标准，产出文献卡与综述矩阵，标出可能是空白的位置
- 设计实验计划（假设 → 预测 → 最小实验、变量、基线、消融、重复与方差报告）
- 维护实验台账，让每个数字都能追到某次运行、某份配置
- 按目标会议的通行结构组织写作骨架、图表顺序与投稿前自检
- 全程留痕：每条结论都标注来自哪份材料、哪次运行
- **四段里的动手动作有命令行落地**：`scripts/run.py` 的 `extract`（结构化抽取）、
  `summarize`（带出处摘要）、`matrix`（综述矩阵与空白点）、`review`（审稿人预演）
  走 `/api/v1/chat/completions`；`doc-qa` 走 `/api/v1/apps/file_qa/chat`；
  纪律（不编造引用、缺失字段标「未提供」）写在 system prompt 里

**不覆盖**：

- 不替你判断选题的学术价值，也不替你决定做什么方向
- 不代替你阅读原文。检索到的条目必须由你打开核对，本 Skill 不对自动抓取内容的准确性作保证
- 不生成、不补全、不猜测参考文献条目。无法核对来源的引用一律留空并标注，绝不编造
- 不代替你运行实验，不改你的训练或评测代码，不解释你没有提供的结果文件
- 不承诺录用。投稿结果由期刊或会议的评审决定，本 Skill 只能帮你把材料准备齐、把漏洞暴露得早一点
- 不提供法律、伦理或数据合规的正式意见
- 不对 `scripts/run.py` 的模型输出负责。它是「整理器」不是「事实来源」：
  抽出来的字段、写出来的摘要与空白点判断，都必须由你回原文复核后才能进稿件

---

## 依赖条件

- 一句写下来的方向描述，一句话就够，但必须写下来
- 项目目录可读写
- 需要检索时有网络；完全离线时只能做发散、整理与写作
- 要核对文献，需要你自己具备打开原文的权限（预印本站点、机构订阅等）
- 文献管理工具可选（任意引用管理器或纯文本清单），没有也能跑完整条流程
- **可选**：想用命令行做抽取 / 摘要 / 对比 / 审稿预演 / 公网文档问答，需要
  Python 3.8+（零第三方依赖）与一把 `api.a7w.cn` 的 API Key

---

## 已知限制

- 检索只覆盖可公开获取的来源，覆盖面不等于穷尽；预印本与数据库收录之间有时间差
- 中英文之外的语种支持有限，非英语文献容易漏
- 选题打分卡是启发式排序工具，换个人打分会不同，不构成任何评价结论
- 跨数周以上的项目需要你定期把台账同步回文件，否则早期上下文会丢
- 需要专有数据、专有算力或安全审查的方向，只能做规划，不能在本流程内执行
- 对同一份材料的两次整理可能措辞不同，凡涉及数字与引用，以你项目里的原始文件为准
- `scripts/run.py` 的抽取 / 摘要 / 对比是**模型输出**，会有遗漏与措辞漂移；
  「未提供(需回原文核对)」是纪律不是保证，凡引用与数字一律回原文核对
- 大模型按 Token 计费（1 元 = 100 点，失败退回）。长材料一次塞太多会显著加价，
  建议先用 `--dir` 限定范围、用 `--max-tokens` 压输出
- `doc-qa`（`file_qa/chat`）只吃**公网 HTTP(S) 文档地址**，一次 1~8 个；
  本地文件与需要登录才能打开的文献，本流程内不代取
- 平台模型清单上下架频繁，本文写下的模型名（如 `deepseek-chat`）只是示例，
  请用 `python scripts/run.py models` 现查

---

## 自检清单

进入下一段之前，逐条打勾：

- [ ] 选题能写成一句可证伪的主张，含比较对象与评价指标
- [ ] 每个候选选题都写清了「若结果相反会怎样」
- [ ] 每条引用都能打开原文核对，标题、年份、出处一致
- [ ] 综述矩阵里的空白点标明了是「确认没人做」还是「我没搜到」
- [ ] 实验计划写明了基线、自变量、控制变量、随机种子与重复次数
- [ ] 实验台账每次运行都有配置、命令与结果路径
- [ ] 图表在写正文之前已经定稿
- [ ] 稿件里每个数字都能追到某次运行或某张原始表
- [ ] 稿件没有编造的引用，也没有未声明的 AI 生成内容
- [ ] 用脚本产出的文案已标注是模型整理结果，且每条结论都回原文核过
- [ ] 你本人通读并认可终稿的每一句话

---

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/01-选题与头脑风暴.md` | 发散框架、收敛打分卡、选题锐化的三步流程与检查清单 |
| `references/02-文献检索与综述.md` | 检索式构造、三关筛选、文献卡模板、综述矩阵与引文核对纪律 |
| `references/03-实验设计与复现.md` | 假设转实验、变量与基线设计、重复与方差、实验台账与负结果处理 |
| `references/04-论文写作与投稿.md` | 叙事与骨架、图表先行、投稿前自检、审稿人预演与返修应对 |
| `scripts/run.py` | **算力接入层**：`extract` / `summarize` / `matrix` / `review` / `doc-qa` / `models` / `chat`，走 `api.a7w.cn` |
| `scripts/a7w.py` | 零依赖客户端：`login / whoami / apps / points / schema / call / task` 七个子命令 |

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
