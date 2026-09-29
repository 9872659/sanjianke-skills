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

本技能包内置的**广告法违禁词表、播客口播红线表、对话稿结构判定都是启发式自检工具**，
来自公开经验整理与团队实测，**不构成法律意见**，也不代表任何播客平台 / 音频平台的
官方审核标准（官方标准不公开且会变）。使用者应自行确认所生成与发布的音频、
shownotes 与配乐符合当地法律法规与平台规则。

**版权与授权（本包重点）**：播客是音频作品，本包只负责生成素材，不替你取得授权。

- 配音音色：使用 `list_voices` 里的音色、或用 `clone_voice` 克隆音色之前，
  **请自行确认你对该音色有使用权**。克隆他人声音涉及声音权益，未经许可不要做。
- 配乐：`music_generation` 生成的是原创音频，但**平台条款与商业使用范围由平台决定**，
  正式商用前请自行核对平台许可。
- 对话稿里出现的观点、数据、案例由使用者负责。本包提示词里写死了"不许编人名、
  机构、论文、数据"，但那是一道提示，不是事实核查。

**内容合规**：合规闸门是**粗筛**，宁可多报也不漏报，它**不能替你判断**某期节目
是否合规。医疗、保健食品、金融投资、教育培训、招商加盟这些高风险类目必须人工复核。

**费用提示**：配音按千字、配乐按次扣费。`voice` / `music` / `all` 跑前都会报价，
每次调用后都会把**真实扣费**（`usage.points_cost`）打出来，并在与报价差得明显时
明确标出。本包不做代付，也不内嵌任何密钥——Key 由使用者自己准备。
