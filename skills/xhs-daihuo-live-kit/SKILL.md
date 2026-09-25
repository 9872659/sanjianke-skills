---
name: xhs-daihuo-live-kit
slug: xhs-daihuo-live-kit
displayName: 三剪客 · 小红书带货直播作战包
description: "小红书电商带货全链路作战包：选品测算、商品笔记、直播脚本、评论话术、数据复盘与违禁词合规自检。适用于商品笔记批量出稿、直播间从开场到逼单的分钟级脚本设计、带货文案的广告法与平台规则预检，以及账号冷启动与投放前的毛利测算。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.2.4
summary: "从小红书选品测算到商品笔记、直播脚本、评论话术与数据复盘的一体化工作流，含 8 份参考资料、5 个可离线运行的 Python 脚本（选品计算器、时间轴生成、笔记评分、合规扫描、内置自测）。明确划出覆盖与不覆盖的边界——本 Skill 是单人可用的方法论与轻量工具。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - xiaohongshu
  - 电商带货
  - 直播脚本
  - 商品笔记
  - 内容合规
  - 选品
---

# 小红书带货直播作战包

把「账号定位 → 选品 → 商品笔记 → 直播脚本 → 评论承接 → 数据复盘 → 合规自检」串成一条
可复用的流水线。

本技能不是提示词集合，而是一套带**输入契约、量化模型、结构模板和可执行脚本**的工作流：
选品有毛利公式和评分卡，笔记有解析格式和评分数值，直播有分钟级时间轴，合规有能接进 CI 的扫描器。

## 这个 Skill 能做什么

- **选品测算**：售价/成本/物流/佣金/退货率 → 佣金后毛利、保本 CPA、建议 CPA 上限，可按目标 ROAS 反推获客成本。
- **六维选品决策**：六维各 0–5 分，输出「可主推 / 可测试 / 放弃」与 7 天内可验证的最小动作。
- **笔记批量出稿**：五类标题钩子各一条，三段式正文 + 6–10 个标签 + 封面大字，格式脚本可直接解析。
- **分钟级直播脚本**：五段式时间轴 + 单品七步讲解法 + 十二类照念话术 + 排品策略。
- **评论与私信承接**：8 类高频评论合规回复、差评处理口径、私信硬边界。
- **复盘与合规自检**：两套漏斗诊断表、归因纪律，以及可接进 CI 的离线违禁词扫描器。

## 工作流 / 方法

先收齐输入，缺什么就问、拿不到就在交付物里标「待补充」：账号（赛道、人群限定、人设、是否过冷启动）；
商品（售价、成本、物流、包材、佣金率、退货率、类目资质）；数据（后台导出的曝光/点击/互动/成交，
本技能不抓取平台数据）；素材（证据优先级 实拍 > 检测报告 > 参数 > 形容词）。

**1. 账号定位。** 人设三要素要一句话说完：**身份**（凭什么讲）、**场景**（在什么处境用）、**立场**
（会不会说真话）。定位 = 一个主赛道 + 一个人群限定；判据是陌生人刷你 3 篇能否说出「讲 xx 给 xx 看」。
冷启动 30 天五阶段：定位 1–3 / 试水 4–10 / 收敛 11–18 / 稳定 19–25 / 放量 26–30，**试水期不要投流**。

**2. 选品：先算账，再谈感觉。** 单件毛利 = 售价 - 成本 - 物流 - 包材；佣金后毛利 = 单件毛利 -
售价 × 佣金率；退货后毛利 = 佣金后毛利 × (1 - 退货率)；**保本 CPA = 退货后毛利**（投放超过就是纯亏），
**建议 CPA 上限 = 退货后毛利 × 0.5**。判定线（佣金后毛利占售价）：**< 20%** 无投放空间；**20%–35%**
可测试、预算克制；**≥ 35%** 有投放余量；**退货后毛利 ≤ 0** 放弃。六维评分卡（每维 0–5，满分 30）：
**≥ 24** 主推，**18–23** 测试并附最小验证动作，**< 18** 放弃；**任一维度为 0 且属合规或毛利 → 直接
放弃，不看总分**。退货率用真实数据替换经验值：服饰类常被低估，**先用 40% 算一遍，还能赚再考虑做**。

**3. 商品笔记。** 标题先写 5 条，分属痛点/对比/攻略/反常识/价格五型，每条 ≤ 20 字、含至少 1 个搜索词、
不用极限词。正文三段式：开头 2 行讲「关我什么事」（禁以「本产品」开头）→ 中间 3–6 段给证据，一个卖点
一段、具体 > 形容词、每 3–4 行断句、单行 ≤ 60 字 → 结尾 2 行给行动指令。**至少给 1 个「不适合谁」的
反向说明**。标签 = 1 个大词（最多 2 个）+ 2–3 个精准词 + 1 个长尾词 + 1–2 个品牌词。封面 3:4
（1242 × 1660 px）：顶部 15% 留白、中部 55% 主体、下部 30% 大字、四周 8% 边距，大字 ≤ 9 字最多 2 行。
交付固定用 `## 标题候选` / `## 正文` / `## 标签` / `## 封面大字`，`note_score.py` 依赖此契约。

**4. 直播脚本。** 五段式比例**不可调换**：开场留人 10% ｜ 痛点共鸣 17% ｜ 产品引入 23% ｜ 信任建立 23% ｜
逼单转化 27%——先解决「为什么留下」，再解决「为什么买」。单品七步：痛点提问 20s → 外观展示 15s →
卖点一 40s → 卖点二 40s → 演示验证 60s → 价格锚点 30s → 下单指令 20s，**只讲 3 个卖点**。排品：
引流款 → 利润款 → 形象款 → 清仓款，90 分钟以上循环 2–3 轮；**上架时间与主播口播对齐**。**红线**：
不承诺疗效、不虚构价格、不诱导私下交易、不虚构库存与销量、不贬低竞品、不诱导好评返现。憋单只允许
「给等待一个真实理由」，不允许编造倒计时、假装卡顿、虚构「最后 3 件」。

**5. 评论承接与私信。** 四原则：公开回答、给信息不给承诺、主动露缺点、不重复贴商品。硬边界：**不批量
私信、不群发、不留站外联系方式、不引导私下交易、不诱导好评返现**。节奏：30 分钟内回前 10 条并置顶链接
→ 2 小时补一轮 → 当天睡前清完真实提问 → 次日把高频问题变成下一篇选题。

**6. 数据复盘。** 笔记漏斗：曝光 → 点击 → 停留 → 互动 → 主页访问 → 商品点击 → 成交；判读顺序**先点击率，
再互动率，最后转化**，前一层不达标时优化后一层没有意义。直播漏斗：场观 → 平均停留 → 互动 → 商品点击 →
下单 → 支付。归因纪律：**一次只改一个变量**；比点击率与互动率而非绝对曝光数；固定发布时段后再比内容；
至少 7 篇同变量样本再下结论。

**7. 合规自检（发布前必跑）。** 五类基础规则：**极限词/绝对化用语、医疗功效、金融收益承诺、站外导流、
平台敏感操作**；用 `--category` 叠加类目规则（cosmetics / food / health / mother-baby / apparel / digital /
appliance）。`high` 必须改、不允许发布，`medium` 建议改或补真实依据，`low` 逐条确认；`verdict` 取
`blocked`/`review`/`check`/`pass`，配 `--strict` 在 CI 卡门禁。口径：按子串匹配、不理解语义、不看图片、
不做谐音识别，高风险类目必须人工复核；**不等于平台官方审核规则，也不构成法律意见**。

## 参考文件

| 文件 | 内容 |
|---|---|
| `references/account-positioning.md` | 人设三要素、定位矩阵、简介模板、主页装修清单、冷启动 30 天计划、矩阵号禁忌；开号或账号起不来时翻。 |
| `references/selection-scorecard.md` | 毛利公式、毛利率判定线、七类目退货率区间、六维评分卡阈值、高风险类目资质清单；决定做不做这个品时翻。 |
| `references/note-formulas.md` | 五类标题钩子、三段式正文、分品类角度、标签组合、3:4 封面构图、失败模式与交付格式契约；写笔记时翻。 |
| `references/live-script-playbook.md` | 五段式节奏、七步讲解法、十二类话术库、排品策略、助播中控分工、90 分钟大场骨架、憋单边界；排直播时翻。 |
| `references/comment-and-dm-scripts.md` | 回复四原则、8 类高频评论模板、差评处理、私信边界、违规话术对照表与运营节奏；写承接话术时翻。 |
| `references/data-review.md` | 两套漏斗、指标健康信号、时段诊断表、复盘与周报模板、六条归因纪律；复盘时翻。 |
| `references/compliance-rules.md` | 五类规则明细与替换建议、七类目规则、资质对照表、自定义规则 JSON、退出码与 CI 集成；被限流时翻。 |
| `references/category-playbooks.md` | 家居清洁/食品/美妆/服饰/3C/母婴/家电七类的角度、演示、直播重点、红线与坑，加五条通用打法。 |

## 脚本

| 脚本 | 用途 | 用法 |
|---|---|---|
| `selection_calc.py` | 毛利与投放空间：佣金后毛利、保本 CPA、建议 CPA 上限，支持 ROAS 反推与批量 CSV | `python3 scripts/selection_calc.py --price 89 --cost 32 --shipping 6 --commission 0.2 --return-rate 0.08`<br>加 `--target-roas 3`／`--json`／`--out f`；批量 `--batch products.csv` |
| `live_timer.py` | 五段式比例生成分钟级直播时间轴，商品平分到「产品引入」窗口 | `python3 scripts/live_timer.py --minutes 30 --products "便携榨汁杯,收纳盒"`<br>选项 `--format md\|csv\|json`、`--out` |
| `note_score.py` | 按交付格式解析笔记，五维打分（0–100）并给改进项 | `python3 scripts/note_score.py --file note.md`<br>选项 `--json`、`--min-score 80`（低于分数线退出码 1） |
| `compliance_check.py` | 离线违禁词扫描：五类基础 + 七类目 + 自定义词表，支持 text/json/csv 与 CI 退出码 | `python3 scripts/compliance_check.py --file note.md -c cosmetics --strict`<br>另有 `--text` `--format json\|csv` `--rules` `--min-level` `--out` `--list-rules` `--explain` |
| `selftest.py` | 内置自测，验证全部脚本核心行为；不联网、不写盘 | `python3 scripts/selftest.py`（`-v` 打印用例；退出码 0 全通过） |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 不申请 | 全部脚本纯离线，仅用 Python 标准库 |
| 读取文件 | 申请（仅用户传入的路径） | 读取待评分/待扫描文案、批量 CSV 与自定义规则 JSON |
| 写入文件 | 仅在传入 `--out` 时 | 写测算结果、时间轴或扫描报告；不传则不写盘 |
| 凭证 / API Key | 不申请 | 不读取任何密钥、环境变量或登录态 |

本技能不抓取任何平台数据，指标需由用户从创作者后台导出或提供。

---

## 怎么用

本包是**纯文本 + 零依赖 Python 脚本**，不需要装任何第三方包：

1. **先读 [`SKILL.md`](SKILL.md)** —— 主入口：完整流程、判断标准、常见坑
2. **`references/` 里有 8 份细节文档** —— 需要展开某一步时再翻
3. **`scripts/` 里有 5 个可直接跑的脚本**（只用 Python 标准库，Python 3.8+）

```bash
# 每个脚本都能直接跑，先看它的参数说明
python3 scripts/compliance_check.py --help
python3 scripts/live_timer.py --help
python3 scripts/note_score.py --help
python3 scripts/selection_calc.py --help
python3 scripts/selftest.py --help
```

| 脚本 | 用途 |
|---|---|
| [`scripts/compliance_check.py`](scripts/compliance_check.py) | 见 SKILL.md 的「脚本」一节 |
| [`scripts/live_timer.py`](scripts/live_timer.py) | 见 SKILL.md 的「脚本」一节 |
| [`scripts/note_score.py`](scripts/note_score.py) | 见 SKILL.md 的「脚本」一节 |
| [`scripts/selection_calc.py`](scripts/selection_calc.py) | 见 SKILL.md 的「脚本」一节 |
| [`scripts/selftest.py`](scripts/selftest.py) | 见 SKILL.md 的「脚本」一节 |

| 文档 |
|---|
| [`references/account-positioning.md`](references/account-positioning.md) |
| [`references/category-playbooks.md`](references/category-playbooks.md) |
| [`references/comment-and-dm-scripts.md`](references/comment-and-dm-scripts.md) |
| [`references/compliance-rules.md`](references/compliance-rules.md) |
| [`references/data-review.md`](references/data-review.md) |
| [`references/live-script-playbook.md`](references/live-script-playbook.md) |
| [`references/note-formulas.md`](references/note-formulas.md) |
| [`references/selection-scorecard.md`](references/selection-scorecard.md) |

> 没有 API Key、或者想让人给你一份能直接跑的示例，看文末「联系我们」。

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
