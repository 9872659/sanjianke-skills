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

### 1) 违禁词表与各道闸门都是启发式自检，不是法律意见

本技能包里的违禁词表、打分锚点校验、提案独立性判定、裁决完整性检查都是**启发式自检工具**，
来自公开经验整理与真机实测标定，**不构成法律意见**，也不代表任何平台的官方审核标准。
使用者应自行确认参赛方案与最终对外内容符合当地法律法规与平台规则。

高风险类目（医疗、保健食品、食品、金融、母婴、特殊化妆品）必须经过人工复核。

### 2) 评分维度与权重是公开常量，改口径必须改版本号

四个维度（成本 / 可行性 / 差异化 / 风险）与权重写在 `scripts/run.py` 里，由 `rubric`
子命令公示。**它们刻意不交给模型现编**：竞标的公正性全押在"尺子先定"上。
改了维度或权重必须同时改 `RUBRIC_VERSION`，否则断点续跑会把旧尺子打的分配上新尺子的裁决。

`rubric` 必须在**提案之前**跑：没公示过就只能 `exit=2`。顺序倒了整场竞标的性质就变了 ——
先看方案后定尺子，那是为已经写出来的东西找理由。

### 3) "竞争"这件事是被本地核对过的，不是声明

三组提案如果高度重合（两两重合度 ≥ 0.75）会被判**假竞争**并 `exit=3`。
这不是不信任模型，而是"三个角色各写一段然后合并"本来就**不是竞争**，那是协作 ——
产物会看起来很像，但它没有胜负的意义，打分排序与合并建议也都失去落点。

### 4) 一票否决仍然要过本地校验

只有风险与合规评委有否决权，并且否决必须带理由与**锚到那一组方案原文**的引文；
没锚上的否决不计入否决名单（但原样保留在案）。被否决的组不能被判获胜。

### 5) 产出不许进包

`--outdir` / `--out` 落在 Skill 包内会直接 `exit=2`。包内只允许
`.md .py .txt .json .sh .js .yaml .yml .csv` 这类文本后缀。

### 6) 这个包不做的事

- **不代写对外发布文案**：它产出的是内部竞标结论（谁赢、别人差在哪、什么可以合并），
  不是可以直接发出去的成品。
- **不替你做法律判断**：合规闸门只是粗筛。
- **不出图、不出视频**：它只处理文本方案。
