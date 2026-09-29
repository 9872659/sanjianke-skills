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

本技能包里的违禁词表、学习目标可考核性判定、知识点依赖判定、术语一致性判定、
质检锚点校验都是**启发式自检工具**，来自公开经验整理与真机实测标定，
**不构成法律意见**，也不代表任何平台的官方审核标准。使用者应自行确认课程内容与
宣发物料符合当地法律法规与平台规则。

**四个角色都是大模型扮演的，不是人类。** 它们之间的否决与裁决是一种结构化的
质量流程，**不等于人工教研评审，也不等于法律合规审查**。「质检」角色的裁决基于
模型对文本的独立判断，可能漏报也可能误报，不能替代专业法务意见。

三道课程特有的闸门各自有已知的误报面，遇到时请人工确认后再决定处置方式，
**而不是把闸门关掉**：

- 「学习目标可考核性」按行为动词与刻度判，可能把确实可考核但写法简省的目标准判成
  不可考核；
- 「知识点依赖」按术语抽取判，可能把引用一次的例证（例如讲义里举的「老板讲用料」）
  误当成术语；
- 「术语一致性」只抓「同长度、只差一个字」的两种叫法，
  语义层面的不一致仍然要靠质检角色与人来看。

本包只负责把「教研 → 讲师 → 课件 → 质检」这条协作流程跑完并如实报告结果，
**不替使用者做交付决策**。走显式出口（未收敛）时产出的课程带有未决项，
直接交付前必须由人处理这些未决项。最终是否交付由使用者负责。

本包**不出图、不出 PPTX**，产出全部是文本（设计卡 / 讲义 / 课件方案 / 质检记录）。
排版与配图请交给既有的课件排版包。
