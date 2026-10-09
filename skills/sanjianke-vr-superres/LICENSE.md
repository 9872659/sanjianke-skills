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

本技能包内置的**人物合规词表、恶俗词表与广告法违禁词表都是启发式自检工具**，
来自公开经验整理，不构成法律意见，也不代表任何平台的官方审核标准。
使用者应自行确认所生成与发布的图片、文案符合当地法律法规与平台规则。

**肖像权的额外提示（本包重点）**：头像与写真天然涉及真人肖像。

- 本包的闸门拦的是「使用者把公众人物 / 政治人物 / 明星 / 未成年人这类明显不该做的要求
  写进了提示词」这一种最可控的情形，**它不能替你判断你有没有权利使用某张人像照**。
- 用他人照片做图生图（`--photo-url`）之前，必须取得**本人书面授权**。
- 本包含 `--person-blocklist` 外挂名单：需要按具体姓名拦截时请自行维护一份名单，
  一行一个名字。**本包刻意不内嵌任何在世真实个体的姓名**（理由见 `SKILL.md` 的「已知取舍」）。
- 生成结果如用于商业投放，请自行完成商标与肖像权排查。

**未成年人**：本包不做未成年写真类生成，命中相关词或年龄数字 < 18 一律拦截，
且没有提供绕过开关（`--allow-prompt-hits` 不建议用于此类内容）。

高风险类目（医疗、保健食品、食品、金融、母婴、特殊化妆品）必须经过人工复核。

**费用提示**：出图按次扣费，`--report` 产出的证据文件里逐张记了真实扣费
（`usage.points_cost`），请以它为准对账。本包不做代付，也不内嵌任何密钥。
