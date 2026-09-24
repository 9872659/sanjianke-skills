# 三剪客 · PDF 精细提取 Skill

表格取不准的时候，光有 `extract_text()` 是不够的——你需要看到字符、线条、矩形各自的坐标，才能判断该用哪种策略。pdfplumber 把 PDF 拆到每个字符和每条线，配上裁剪、过滤与可视化调试，让「为什么这个表格取错了」变成能看出来的事。

---

## 前置条件

- **Python 3.10 – 3.14**（官方 CI 覆盖范围；PyPI 声明 `>=3.8`，但按 3.10+ 走更稳）。
- **pip**，`pip install pdfplumber` 会把 `pdfminer.six` 一起装好。
- **Pillow** 用于可视化功能，通常随包安装。
- **PDF 类型**：最适合**机器生成**的 PDF。扫描件不含文字层，提取结果会是空的。
- 不需要任何账号、API Key 或云端订阅。

---

## 使用

1. `pip install pdfplumber`，建议在虚拟环境里装，避免和系统的 `pdfminer.six` 版本冲突。
2. 先跑一遍最小代码确认能取到文本——**如果是空的，先判断是不是扫描件**，别急着调参数。
3. 命令行 `pdfplumber file.pdf` 可以快速摸底，看这份 PDF 里到底有多少字符、线条、矩形对象。
4. 表格提取失败时，**先跑 `debug_tablefinder()` 出图看**识别结果，再决定调哪个参数，不要盲调。
5. 详细策略与参数表见 `references/tables.md`；对象属性与坐标系约定见 `references/objects.md`。

**最该记住的三条**：

- 默认表格策略靠**页面上的线条**，无框线表格必须换 `vertical_strategy` / `horizontal_strategy` 为 `text`。
- 提表前先 `crop()` 掉页眉页脚——这是表格提取失败的头号原因。
- `to_image()` 反映 `crop()` 的结果，但**不反映 `filter()`**。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| `pdfminer.six` | 底层 PDF 解析引擎，随 pdfplumber 自动安装 |
| Pillow | 可视化（`to_image()` / `debug_tablefinder()`）依赖它 |
| Python | 官方测试覆盖 3.10 – 3.14 |

---

## 安全

- 不内嵌任何密钥。本 Skill 不含凭据、不联网。
- 只读操作：pdfplumber **不修改也不生成** PDF，处理不可信 PDF 时不会写回原文件。
- 加密 PDF 用 `password=` 参数正常打开；本 Skill 不涉及任何绕过保护的手段。
- 处理超大 PDF 时注意内存：`Page` 默认缓存布局信息，逐页 `close()` 或分批处理。
- **别用不可信 PDF 当作安全边界**：解析器本身可能有漏洞，处理来源不明的文件建议放在隔离环境里。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pdfplumber`
- 仓库：https://github.com/jsvine/pdfplumber

---

## 许可证

MIT，见 `LICENSE.md`。

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
