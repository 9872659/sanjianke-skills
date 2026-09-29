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

### 1) 本包**不接真实支付 / 工单系统**

这是本包最重要的边界。它**不连**任何支付网关、**不写**任何工单系统的数据库、
**不调**任何退款接口；唯一的外部调用是 api.a7w.cn 的大模型端点。
它产出的是**处置建议与话术**：补偿项、金额口径、升级对象、给用户的话。

**真的要退款、要赠额、要延期、要改用户额度，必须由人工在后台执行。**
报告里的「19800 点 ≈ ¥198」是**口径**，不是已退款金额，也不构成任何支付承诺。

### 2) 权限矩阵是**制度口径**，不是法律意见

那组数字（`L1` 5000 点 / `L2` 30000 点 / `L3` 200000 点）是**默认示例值**，
请按你公司实际的授权制度用 `--policy` 改掉再上线使用。
`--policy` 只能**收窄**补偿项枚举，不能新增 —— 能新增就等于把"不许自创补偿"这条
硬闸门关掉了，所以代码会直接 `exit=2` 拒绝。

### 3) 越权闸门拦的是"额度"，不是"该不该赔"

模型判"该赔多少"与本地判"本级能批多少"是**两件事**，本包把两者并列显示。
闸门五只拦后者：**即便本地认为该赔 198 元，只要本级上限是 50 元，就 `exit=3`。**
这不是判断模型说错了，而是判断**这笔钱不该由这个角色批**。
升级之后由上一级重新跑一遍（`--as-role L2_二线主管`）即可。

### 4) 时效判定依赖工单里写的时间，解析不出来时**不猜**

工单里的 `提交时间` 是时效闸门的基准（T0）。如果时间格式识别不了，
本包会标 `timing_checked=false` 并说明**未做超时判定** —— 而不是默认"没超时"。
真想判超时，请把时间写成 `YYYY-MM-DD HH:MM`。

### 5) 合规扫描是启发式自检，不是法律意见

违禁词表、承诺类话术表、锚点校验、时效判定都是**启发式自检工具**，
来自公开经验整理与真机实测标定，**不构成法律意见**，也不代表任何平台的官方规则。
高风险类目（医疗、保健食品、金融、母婴、特殊化妆品）必须经过人工复核。

### 6) 产出侧的合规口径与材料侧**故意不同**

- **材料侧**（用户提交的工单原文）：全档全查，**只报不拦**。
  用户生气时写"你们必须赔我""你们就是骗子"，那是**用户的话**，
  不是我们要发出去的字 —— 拦它等于"用户一情绪激动就没法处理"。
- **面客字段**（`voice_to_user`，真的要发给用户的话术）：**零豁免**。
- **审类字段**（内部说明 / 升级理由 / 复盘）：开「引用工单原文」与「提到/在禁止」
  两类排除，**被排除的必须留下原因**，照样列在案上可复查。

代价是：产出侧**不保证**每一句内部说明都合规，它只拦"我们自己造了一个违规说法"。

### 7) SLA 时限口径与商品宣称共用同一个「最X」闸门

客服话术里「最迟 24 小时」「最长 3 个工作日」含「最X」，但那是**承诺时限**，
不是最高级商品宣称。本包用一条**独立的 SLA 判据**豁免它
（`最迟/最长/最短/最快/最多/最少 + 数字 + 时间单位`）。
不带数字的「最迟明天」**不豁免**，照拦；句首的「最大区别是…」也照拦。
宁可让人工多看一眼，也不要把真宣称放出去。

### 8) 四席共用同一个模型

四个角色靠**调用边界 + 提示词边界**隔离，不靠不同模型。
换 `--model` 会整体改变四步的表达与结论。

### 9) 本包不替你做责任认定

它给的是"按权限该赔多少、超出该升给谁、话术怎么说、下次怎么不出现"。
**责任认定与最终金额由人工负责。**
