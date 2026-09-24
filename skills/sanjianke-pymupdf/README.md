# 三剪客 · 高性能 PDF 处理 Skill

要处理成千上万份 PDF 时，纯 Python 解析器的速度会成为瓶颈。PyMuPDF 直接绑到 MuPDF 这个 C 引擎上，文本提取快一个数量级、页面渲染快两个数量级，而且读写都能做——提取、渲染、批注、脱敏、合并、加密、OCR 全在一个包里。它对中文有完整支持，跑完全离线。

---

## 前置条件

- **Python 3.10 – 3.14**（截至 v1.27.x）。官方为 Windows / macOS / Linux 提供预编译 wheel。
- **pip**：`pip install pymupdf`，无强制外部依赖。
- **OCR 场景额外需要**：Tesseract 及其语言数据（`tessdata`）。注意 PyMuPDF **不需要** Python 层的 `pytesseract`。
- **Office 文档支持**属于 PyMuPDF Pro，需要单独的商业许可证 Key。
- 没有任何账号、API Key 或云端订阅要求——开源版本装完即可用，且无遥测。

---

## ⚠️ 许可证必读

**PyMuPDF 采用 AGPL-3.0 / Artifex 商业双授权。** 选型前请务必确认你的场景属于哪一类：

| 场景 | 通常结论 |
|---|---|
| 开源项目、个人脚本、不外发的内部工具 | AGPL 基本无额外负担 |
| **SaaS / 网络服务**、**内部平台**、**对外分发的 Docker 镜像**、**闭源桌面应用** | 需要认真评估，很可能需要商业许可证 |

AGPL 第 13 条**专门针对网络交互**：「我们不分发、只做 SaaS」**不是**安全港。

完整判定清单、替代方案（MIT / BSD 许可的 pdfplumber、pypdf 等）与实务建议，见 `references/licensing.md`。

> 本 Skill 包自身是 MIT 许可；PyMuPDF 的许可与之无关。许可证合规责任在调用方。

---

## 使用

1. `pip install pymupdf`，导入时用 `import pymupdf`（`fitz` 是仍可用但不推荐的旧别名）。
2. **先确认许可证**符合你的场景，再做后续投入。
3. 按 `references/recipes.md` 里的配方找最接近的任务：文本提取、表格、渲染、批注、脱敏、合并拆分、加密、OCR、表单、多进程批处理。
4. **批量处理只用多进程**——PyMuPDF 明确不支持多线程。
5. 重复提取同一页时复用 `page.get_textpage()`，官方称可省 50–95% 时间。

**最该记住的三条**：

- **不支持多线程**，批量任务必须用 `multiprocessing`。
- 脱敏必须调 `apply_redactions()`，只加批注不算抹掉。
- `get_images()` 只拿得到嵌入位图，矢量图表要整页 `get_pixmap()`。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| MuPDF | C 引擎，已随 wheel 打包，无需单独安装 |
| `pymupdf-fonts` | 可选，扩展字体集（写中文等非拉丁文本时有用） |
| `pymupdf4llm` | 可选，面向 RAG 的 Markdown / JSON 输出，**授权需单独确认** |
| `pymupdfpro` | 可选，Office / HWP 支持，**需商业许可证** |
| Tesseract | 可选，OCR 用；需单独安装并准备语言数据 |

---

## 安全

- 不内嵌任何密钥。本 Skill 不含凭据、不联网。
- 完全本地运行：官方明确说明**没有遥测、没有许可校验回调、没有任何云端依赖**，可在完全隔离（air-gapped）的环境里使用。适合医疗、金融、法律、政府等对数据出境敏感的场景。
- **脱敏不是画框**：必须调用 `apply_redactions()`，之后原始内容从保存的文件中永久消失、不可恢复。改完后请用文本提取验证敏感词确实取不出来了。
- **加密的权限位不是安全边界**：很多阅读器不强制执行「禁止复制」。真正的机密内容必须实际删除。
- 处理来源不明的 PDF 建议放在隔离环境：解析器本身可能成为攻击面。
- 这是 AGPL 软件，**许可合规**（而非运行安全）是使用它的主要风险点，见上方「许可证必读」。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`PyMuPDF`
- 仓库：https://github.com/pymupdf/PyMuPDF

---

## 许可证

MIT，见 `LICENSE.md`。

（再次提醒：这是**本 Skill 文档**的许可，PyMuPDF 本身是 AGPL-3.0 / 商业双授权。详见 `references/licensing.md`。）

---

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
