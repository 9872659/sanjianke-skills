# 更新日志

本文件记录 xhs-daihuo-live-kit 的版本变更。版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

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
