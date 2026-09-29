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

本技能包内置的**广告法违禁词表、教育类效果承诺表、文字溢出判定、比例真伪判定
都是启发式自检工具**，来自公开经验整理与团队实测，**不构成法律意见**，
也不代表任何培训平台 / 课程平台的官方审核标准（官方标准不公开且会变）。
使用者应自行确认所生成与发放的课件符合当地法律法规与平台规则。

**版权与授权（本包重点）**：课件是**要拿去讲、拿去卖**的东西，本包只负责生成素材，
不替你取得授权。

- **字体**：本包**不打包任何字体**，只从**本机系统字体**里找。
  字体授权归字体厂商，**正式商用（尤其是录课出售、企业内训交付）前请自行确认
  你对该字体的商用许可**。这一步脚本不能替你判断。
- **配图**：`images` 产出的图是模型生成物，**平台条款与商业使用范围由平台决定**，
  正式商用前请自行核对平台许可。本包提示词里写死了"画面里不许出现任何文字"，
  所以图上不会有错字，但**画面内容本身是否合适**仍需你过目。
- **讲义与课件里的观点、数据、案例**由使用者负责。提示词里写死了"不许编人名、
  机构、数据"，但那是一道提示，**不是事实核查**。

**内容合规**：合规闸门是**粗筛**，宁可多报也不漏报，它**不能替你判断**一份课件
是否合规。医疗、保健食品、金融投资、**教育培训（效果承诺是高压线）**、招商加盟
这些高风险类目必须人工复核。本包对教育类效果承诺（保过 / 包学会 / 保证提分 等）
**不设任何豁免**。

**版式与可读性**：文字溢出闸门给的是**像素级结论**（这一页放不下多少内容），
不是"好不好看"的结论。版式合适与否、讲法是否得当，仍然只有讲课的人自己知道。

**费用提示**：文本按 token 计费（本包给的是 `0.02 元/千 token` 的**估算口径**），
出图按张扣费（实测 1K = **24 点/张**，1 元 = 100 点）。`images` / `all` 跑前都会报价，
每次出图后都会把**真实扣费**（`usage.points_cost`）打出来。**2K / 4K 没有实测价，
本包拒绝估算**（`exit=3`），除非你自己用 `--points-per-image` 给单价。
本包不做代付，也不内嵌任何密钥——Key 由使用者自己准备。
**账单以 api.a7w.cn 控制台为准。**
