# MIT License

Copyright (c) 2026 三剪客

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 使用提示

本技能包里的违禁词表、术语一致性核对、数字单位保全、市场文化口径都是
**启发式自检工具**，来自公开经验整理与真机实测标定，**不构成法律意见**，
也不代表任何国家/地区的监管标准或任何平台的官方审核标准。
使用者应自行确认译文与最终发布内容符合目标市场的法律法规与平台规则。

**特别提醒：本包的"目标市场合规"是模型对文本的独立判断 + 本地可枚举规则，
它不等于任何国家的正式法律审查。** 高风险类目（医疗、药品、保健食品、
金融、母婴、特殊化妆品、酒类、儿童用品）在目标市场的准入与宣称规则往往
需要资质与事前备案，**必须由具备当地资质的专业人士复核**，
不能以本包"放行"作为发布依据。

**四个角色都是大模型扮演的，不是人类译审、不是文化顾问、不是法务。**
它们之间的否决与裁决是一种结构化的质量流程，**不等于人工审校**。
「文化适配」判定的红线基于模型对目标市场的一般性认知，可能漏报也可能误报
（同一句话在不同子文化、不同渠道下的接受度并不一致）。

**已知会误报的两处**，遇到时请人工确认而不是关掉闸门：

- **术语一致性**：同一源词的两种译法在具体语境里可能都是合理的
  （例如品牌名与通用词同形）。判为不一致时会列出全部出现位置，
  请逐处看过再决定是否统一。
- **数字与单位保全**：合理的说法转换（例如「3 斤」译成「1.5 kg」、
  「约 1.5 公斤」）可能被记为"原数字不在译文里"。
  报告里会把「原数字在不在」与「换算后的值在不在」分开记，
  请按那一栏判断，而不是只看"丢了"。

**货币换算需要你显式给汇率**（`--fx-rate`）。本包**不猜汇率、不编价** ——
没给汇率时只检查数字在不在，不判断金额对不对。汇率本身随时间变动，
本包不提供、也不缓存任何汇率数据。

本包只负责把「译审 → 术语官 / 文化适配 / 合规」这条互审流程跑完并如实报告结果，
**不替使用者做发布决策**。走显式出口（退出码 6，轮次用尽仍有打回或否决）时
产出的译文**带有未决项**，直接发布前必须由人处理这些未决项。
最终发布与否由使用者负责。
