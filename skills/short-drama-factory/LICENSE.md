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

## 说明

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

### 关于 `assets/` 里的配图

包内 20 张配图**全部是本项目实测跑出来的产出**（AI 生成画面 + 界面截图），
不是从任何第三方项目或图库取得的素材。

- `assets/film/` —— 实跑项目的成片抽帧、分镜墙、锚点物料
- `assets/ui/` —— 本项目参考实现的界面截图（`hq.a7w.cn`）
- `assets/proof/` —— 一致性物料与选型界面截图

配图里可能出现的**模型名**（如 `h3-video`、`wan3.0-video`、`qwen-image-3.0-pro`）
是平台接口的**描述性名称**，用于说明参数差异，不构成对任何厂商的推荐或署名。

### 关于 `scripts/preflight.py`

零依赖（只用 Python 标准库），**不内嵌任何密钥、Token 或 Cookie**。
它只把使用者自己提供的 API Key 发往 `api.a7w.cn`。
