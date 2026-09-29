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

本技能包内置的**广告法违禁词表、主图位判定、视觉可产性判定、裁决完整性判定
都是启发式自检工具**，来自公开经验整理与团队实测，**不构成法律意见**，
也不代表淘宝 / 天猫 / 拼多多 / 抖音商城的官方审核标准（官方标准不公开且会变）。
使用者应自行确认所生成的物料与所发布的商品页符合当地法律法规与平台规则。

### 一、资质与宣称（本包重点）

- **本包不生成资质、不替你取得授权。** 没有真实持有的资质就不许做资质宣称 ——
  视觉角色会标 `no_real_cert`、合规角色会据此否决，这是设计意图，不是故障。
- **不许伪造销量 / 评价 / 资质 / 检测报告。** 提示词里写死了这条纪律，
  本地合规闸门也会把「刷单 / 好评返现 / 保证过审 / 国家级认证」这类表述拦下。
- **无法举证的宣称要改。** 「100% 有效」「行业第一」「七天见效」这类如果拿不出
  检测报告或后台数据，合规角色会打回；打回后仍拿不出，本包会如实报「未收敛」，
  **不会替你把它写成能过审的样子**。

### 二、内容合规

合规闸门是**粗筛**，宁可多报也不漏报，它**不能替你判断**某套物料是否合规。
医疗器械、食品、保健食品、化妆品、金融投资、教育培训、招商加盟这些高风险类目
**必须人工复核**。违禁词表按子串匹配、不理解语义、不看图片、不做谐音识别。

### 三、决策责任

选品角色的结论（含本地的毛利判定线）是**运营参考**，不是投资或经营建议；
毛利测算依赖你输入的成本参数，参数错了结论就错了。所有对外发布的内容与
商务决策由使用者负责。

### 四、费用提示

本包与 api.a7w.cn 之间不代付、不内嵌任何密钥 —— Key 由使用者自己准备，
用量与费用记在 Key 所属账号上。`cost` 会先报价，`run` 每次调用后都会报**真实 token**。
文本模型网关不公布单价，因此本包**只报 token、不报金额**，也**不会编一个金额出来**；
要折算金额请自己传 `--price-in` / `--price-out`。
