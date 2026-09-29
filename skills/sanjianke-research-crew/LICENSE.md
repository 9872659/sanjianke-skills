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

### 1) 违禁词表是启发式自检，不是法律意见

本技能包里的违禁词表、锚点校验、质疑有效性判定、降级表述完整性检查都是**启发式自检工具**，
来自公开经验整理与真机实测标定，**不构成法律意见**，也不代表任何平台的官方审核标准。
使用者应自行确认所评材料与最终对外内容符合当地法律法规与平台规则。

高风险类目（医疗、保健食品、食品、金融、母婴、特殊化妆品）必须经过人工复核。

### 2) ⚠️ 本包**不联网检索**，它给的是证据强度的**评级**，不是事实核查结论

本包只调用两个接口：大模型与在架模型清单。它**不会**去外部数据库、搜索引擎或任何端点
查证你材料里的事实。它做的是**本地推理与评级**：按一张形态表判断"手里那点东西有多硬"、
按挑战七类找出主张的漏洞、给出可采信的边界与可用的替代表述。

**「强」不等于「真」。** 一条证据被评「强」只说明它的形态（来源可核实、样本与口径交代清楚、
结论不外推、时效在有效期内）达到标准，**不说明它描述的事实真的成立**。
反之评「弱」也不等于事实为假。最终事实认定责任在使用者。

### 3) 产出侧的合规口径是"宁松勿误"的

材料侧全档全查（材料是会被公开发布的东西）；产出侧只查高风险，并排除两类正常写法——
**引用**（材料里已有的词）与**提到**（命中前后 24 字内有禁止 / 举证 / 撤回类标记词）。
这样设计是因为本包的材料本身就是"对一组主张做取证"的场所：
产出里出现「全网最低价」这类字样的概率远高于其它包，但语义通常是在**引用、在挑战、在要求撤回**。

代价是：产出侧**不保证**裁决书里每一句都合规，它只拦"本包自己造了一个违规说法"。
被排除的条目全部带 `not_counted_reason` 留在产物里，可人工复查。

### 4) 「最X」有两类豁免，边界是**可判定的**

- **可度量断言**：`度量名词 + 最X + 标点/句尾`（如「订单量最高」「转化率最高」），**不看句首**
- **句中程度用法**：`最X` 后接程度/比较词且不在句首（如「最大的区别是…」）

句首的商品宣称照拦（「最好的选择」「效果最好」），「最高品质」「最高性价比」这类
**给商品名词下定语**的写法也照拦。豁免是启发式的，覆盖不到的地方仍可能漏报或误报。

### 5) 挑战「成立」是**本地的两条判据**，不是模型的自我声明

一条挑战要算成立，必须同时满足：`verdict=challenged`，**且** `reason` 与 `required_fix`
归一后各 ≥ 8 字。这是为了挡住"客客气气写一句建议补充数据"式的伪挑战。

反过来，一条**真的成立但写得很短**的挑战会被判为不成立。
写挑战时把"漏洞是什么、要补成什么样"写全，既是为了过闸门，也是为了裁决方能直接用。

### 6) 四道工序共用同一个模型

四道工序靠**调用边界 + 提示词边界**隔离，不靠不同模型。换 `--model` 会整体改变
四道工序的表达与文风，裁定结果也会随之变化。

### 7) 本包不替你做发布决策

裁决书给的是"哪句能原样说、哪句要怎么改、哪句必须删"。
最终发不发、怎么发，由使用者负责。
