# 三剪客 · HTML 转 Markdown Skill

抓下来的网页要喂给模型或存进知识库，直接塞 HTML 又脏又费 token。turndown 用一套可扩展的规则把 HTML 转成 CommonMark，浏览器和 Node 都能跑，表格、删除线这类 GFM 语法靠插件补。

---

## 前置条件

- **Node 路径**：Node.js 18+、npm 9+。
- **浏览器路径**：任意支持 ES5 的现代浏览器，用 CDN 时无需任何构建工具。
- **网络**：只有 `npm install` 需要联网，转换过程完全离线。
- 不需要任何账号、API Key 或云端订阅。

---

## 使用

1. `npm install turndown`，需要表格或删除线时再 `npm install turndown-plugin-gfm`。
2. `new TurndownService(选项)` 建实例，`service.turndown(html)` 出 Markdown。
3. **先按场景调选项**：默认是 `setext` 标题 + 缩进代码块 + `*` 列表符号，写文档时通常要换成 `atx` + `fenced` + `-`。
4. 抓来的网页记得 `remove()` 掉 `script` / `style` / `nav` / `footer`；Markdown 表达不了的标签用 `keep()` 保留。
5. 表格必须装 GFM 插件，只改选项不生效。

**最该记住的三条**：

- 核心**不支持表格**，`<table>` 会被拍成纯文本，要插件。
- `remove()` 是**连内容一起删**，不是只剥标签。
- 输出里满屏反斜杠是**预期行为**（基于正则的激进转义），要改就覆写 `TurndownService.prototype.escape`。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| `turndown` | 主包，唯一运行时依赖是 `@mixmark-io/domino`，随包自动安装 |
| `turndown-plugin-gfm` | 可选，提供表格与删除线 |
| `jsdom` / `domino` | 可选，仅在 Node 中需要构造 DOM 节点时使用 |

---

## 安全

- 不内嵌任何密钥。本 Skill 不含凭据、不联网。
- turndown **不做 HTML 净化**：它不检测 XSS、不剥离危险属性、不校验 URL 协议。输出若进入不可信环境，请在前面单独接一个 sanitize 环节。
- 转换是纯字符串处理，不会执行 HTML 里的脚本——但不要因此把它当成安全边界。
- 处理不可信 HTML 时注意内存：超大文档会整体载入构建 DOM。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`turndown`
- 仓库：https://github.com/mixmark-io/turndown

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
