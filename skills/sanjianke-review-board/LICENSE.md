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

本技能包里的违禁词表、锚点校验、立场重叠度、裁决完整性检查都是**启发式自检工具**，
来自公开经验整理与真机实测标定，**不构成法律意见**，也不代表任何平台的官方审核标准。
使用者应自行确认所评方案与最终对外内容符合当地法律法规与平台规则。

高风险类目（医疗、保健食品、食品、金融、母婴、特殊化妆品）必须经过人工复核。

### 2) 产出侧的合规口径是"宁松勿误"的

材料侧全档全查（材料是会被公开发布的东西）；产出侧只查高风险，并排除两类正常写法——
**引用**（材料里已有的词）与**提到**（命中前后 24 字内有禁止 / 举证 / 风险类标记词）。
这样设计是因为真机实测中，评审文书里"无法举证为 100% 成立""明确禁止刷量"这类
**在指出问题**的写法会被误判成违规宣称，而误报会让人把整个闸门关掉。

代价是：产出侧**不保证**裁决书里每一句都合规，它只拦"评审自己造了一个违规说法"。
被排除的条目全部带 `not_counted_reason` 留在产物里，可人工复查。

### 3) 评审锚点可能把真实引文判成幻觉

引文与原文差得较远（重述式引用）时，锚点校验会判 `unverified` 并剔出该条意见。
未锚定率超过 40% 才判「定位失败」，少量误报属正常。遇到时应人工确认后再决定处置，
而不是关掉闸门。

### 4) 立场失效告警要先排除"材料太短"这个原因

材料只有几句话时，四席的锚点会大量落在同一两句上，各自「自己的话」也会天然变少，
重叠度因此偏高。闸门五报「立场失效」时，先看材料是否信息量不足，
再判断是不是模型在"和稀泥"。

### 5) 四席共用同一个模型

四个立场靠**调用边界 + 提示词边界**隔离，不靠不同模型。换 `--model` 会整体改变
四个立场的表达与文风，评审结论也会随之变化。

### 6) 本包不替你做发布决策

裁决书给的是"该不该过 + 要过必须满足什么 + 谁在反对"。最终发布与否由使用者负责。
