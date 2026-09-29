# 更新日志

本文件记录 xhs-daihuo-live-kit 的版本变更。版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## 1.2.5

**新增：真的接上 api.a7w.cn（不再只是方法论）**

此前本包是纯方法论 + 离线脚本，包里没有任何一处真正请求 `api.a7w.cn`，因此被判定不合规。
这一版把「出稿」这一段接上算力，方法论与原有脚本的结论一个字没改。

- `scripts/a7w.py`：复制进来的 api.a7w.cn 零依赖客户端（`login / whoami / apps / points / schema / call / task`），
  不内嵌任何密钥，Key 由使用者自己提供
- `scripts/run.py`：新增出稿与预检层，四个子命令，全部只用标准库
  - `note` —— 商品笔记出稿，严格套 `references/note-formulas.md` 的交付契约，
    产出可直接被 `note_score.py` 解析打分
  - `live` —— 直播脚本出稿，套 `references/live-script-playbook.md` 的五段式比例
  - `compliance` —— 违禁词 / 广告法**语义**预检，与离线 `compliance_check.py`（子串匹配）互补，
    支持 `--format md|json|csv` 与 `--strict` 退出码
  - `models` —— 列出平台在架的文本模型（免费）
- 真实调用的端点：`POST https://api.a7w.cn/api/v1/chat/completions`（OpenAI 兼容）、
  `GET https://api.a7w.cn/api/v1/models`
- `SKILL.md`：新增「怎么用（命令行）」一节，给出可跑命令、参数说明、端点与实测输出；
  「权限与用途说明」表按实情更新（网络访问与 API Key 只在跑 `run.py` 时申请）
- 实测：`note` 出稿经 `note_score.py` 打分 94/100（A 级），`compliance` 对
  「全网最低价，7天见效」判定 `blocked` 并列出 4 条 high

**兼容性**：原有 5 个离线脚本与全部方法论内容不变；不跑 `run.py` 就完全不联网、不产生任何费用。

## 1.2.3

**修复（SkillHub 上架被拦的问题）**

- 去掉 frontmatter 的 `homepage`：SkillHub 会把它渲染到技能详情页上
- 去掉 frontmatter 的 `x-astron-category`：模板残留字段，无实际作用
- 移出 `assets/icon.svg`：SkillHub 只收文本类文件（md / py / txt / json / sh / js / yaml / csv），
  图片留在包里会直接让发布失败。图标已挪到 `SKILL图标/xhs-daihuo-live-kit.svg`，
  需要设技能 iconUrl 时从那里上传

## 1.1.1

**新增**

- `assets/icon.svg`：512×512 图标素材，可在 SkillHub 技能详情页设置 iconUrl 时直接上传

**变更**

- `SKILL.md` 的 `x-astron-category` 由 `内容写作与创作` 改为平台类目键名 `content-creation`，便于跨客户端识别
- `SKILL.md` 参考文件表补充 `assets/` 说明

## 1.1.0

**新增资料（4 份）**

- `references/comment-and-dm-scripts.md`：评论区回复四原则、8 类高频评论模板、差评处理、私信边界、违规话术对照表
- `references/data-review.md`：笔记与直播两套漏斗、时段诊断表、单篇复盘模板、周报模板、归因纪律
- `references/account-positioning.md`：人设三要素、垂直定位矩阵、简介模板、主页装修清单、冷启动 30 天计划、矩阵号注意事项
- `references/category-playbooks.md`：家居清洁 / 食品 / 美妆 / 服饰 / 3C / 母婴 / 家电 七类打法

**新增脚本（4 个）**

- `scripts/selection_calc.py`：毛利与投放空间计算器，支持目标 ROAS 反推 CPA、批量 CSV
- `scripts/live_timer.py`：按五段式比例生成分钟级直播时间轴，商品在「产品引入」窗口内自动平分时段
- `scripts/note_score.py`：按交付格式解析笔记，从标题/正文/标签/封面/合规五个维度评分（0–100）
- `scripts/selftest.py`：24 个内置用例，一键验证全部脚本行为

**增强**

- `compliance_check.py`：新增七类目规则（`--category`）、自定义词表（`--rules`）、CSV 输出、`verdict` 结论、`--explain`；规则表大幅扩充
- `references/note-formulas.md`：五类标题钩子各补 3 条示例、七类品类内容角度、3:4 封面构图规范、交付格式契约
- `references/live-script-playbook.md`：新增单品七步讲解法、十二类照念话术库、排品与过品策略、助播中控分工、90 分钟大场骨架
- `references/selection-scorecard.md`：新增类目经验退货率表、目标 ROAS 反推、竞品调研表、批量测算用法
- `references/compliance-rules.md`：新增类目资质对照表、自定义规则 JSON 格式、CI 集成示例
- `SKILL.md`：新增工作流路由表、输入契约、7 条工作流、7 个调用示例、脚本清单、版本历史

**修复**

- `note_score.py`：标签行以 `#` 开头时被误判为 Markdown 标题，导致标签维度恒为空
- `live_timer.py`：多个商品被挤在同一时段，现按商品数平分「产品引入」窗口
- `selection_calc.py`：文本报告使用命名占位符却按位置传参，导致 `KeyError`

**兼容性**

- 目录结构、slug 与 `SKILL.md` frontmatter 字段保持向后兼容，1.0.0 的调用方式全部仍然有效
- 1.0.0 的 `compliance_check.py --file/--text/--json/--strict/--min-level` 参数全部保留

## 1.0.0

首次发布。

- `SKILL.md`：场景、输入契约、四条工作流、调用示例、能力边界、依赖与限制
- `references/selection-scorecard.md`：六维选品评分卡与毛利测算口径
- `references/note-formulas.md`：标题钩子、正文三段式、标签组合、封面规则
- `references/live-script-playbook.md`：五段式直播节奏表、憋单与异议处理话术库
- `references/compliance-rules.md`：五类合规规则、判定口径与免责说明
- `scripts/compliance_check.py`：离线违规词扫描（仅标准库，不联网）
