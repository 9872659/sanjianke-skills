---
name: sanjianke-turndown
slug: sanjianke-turndown
displayName: 三剪客 · HTML 转 Markdown
description: "把网页或 HTML 片段转成干净 Markdown 的 JavaScript 库，可按需扩展规则、保留原始 HTML、并配合 GFM 插件支持表格与删除线。 遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "抓下来的网页要喂给模型或存进知识库，直接塞 HTML 又脏又费 token。turndown 用一套可扩展的规则把 HTML 转成 CommonMark，浏览器和 Node 都能跑，表格、删除线这类 GFM 语法靠插件补。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - PDF
  - 文档处理
  - Markdown
  - JavaScript
---

# 三剪客 · HTML 转 Markdown

你从网页、富文本编辑器或某个 API 里拿到一段 HTML，想把它变成能进知识库、能喂给模型的 Markdown。手写正则替换那条路走不通——HTML 里嵌套、空白折叠、实体转义、代码块里的特殊字符，每一项都能让你的正则输出炸掉；而 HTML 本身又比 Markdown 啰嗦好几倍，直接丢给模型是在烧 token。

turndown 干的就是这一件事：接受 HTML 字符串或 DOM 节点，输出 CommonMark。它的扩展点是**规则（rule）**——每条规则用 `filter` 挑元素、用 `replacement` 决定怎么转，你可以加规则、保留某些元素为原始 HTML、或整段删掉。表格和删除线不属于 CommonMark，官方用 `turndown-plugin-gfm` 这个独立包补上。

**上游项目**：`turndown`　**仓库**：https://github.com/mixmark-io/turndown

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 纯本地字符串转换，不联网。HTML 的来源（抓取、读库）由上游环节负责 |
| 读取文件 | 视需要 | 读取待转换的 `.html` 文件或模板 |
| 写入文件 | 视需要 | 把转换结果落盘为 `.md` |
| 凭证 | 否 | 不需要任何 Key 或账号 |
| 子进程 / 后台常驻 | 否 | 就是个库，在你自己进程里跑；要批量处理可以包一层脚本 |

**密钥与费用**：本 Skill 不内嵌任何密钥、不代理请求、不代收费用。turndown 是 MIT 许可的纯本地库，没有任何计费和配额概念。

## 什么时候用 / 不用

**该用**：

- 「把这段网页 HTML 转成 Markdown 存进知识库」——最典型的一步转换。
- 「抓下来的正文里还混着 `<script>`、`<style>`、导航栏，帮我清掉」——用 `remove()` 过滤。
- 「这个页面的表格要保留成 Markdown 表格」——加载 GFM 插件。
- 「`<details>` / `<iframe>` 这些标签 Markdown 表达不了，原样留着」——用 `keep()` 保留为原始 HTML。
- 「默认转出来的 Markdown 转义太激进，满屏反斜杠」——覆写 `escape`。
- 「我要在 Node 里批量转一堆 HTML 文件」——配合 `fs` 写个循环。


**不该用**：

- 要抓网页、去广告、抽正文 —— 它只转你递给它的 HTML，抓取与正文提取是上游环节的事。
- 不装 GFM 插件就想要 Markdown 表格 —— 核心包明确把表格划在边界之外。
- 要做 Markdown → HTML 的反向转换 —— turndown 只有单向。
- 拿它当 HTML 净化器 —— 它不检测 XSS、不剥离危险属性、不校验 URL 协议；输出给不可信环境前必须另加 sanitize 环节。
- 要保留颜色、字号、对齐等样式 —— `<span style="color:red">` 这类信息在 Markdown 里无处安放，一律丢失。
- 要 `<details>` / `<figure>` / `<mark>` 原样保留 —— 默认降级成纯文本（`keep` 能补一部分，但覆盖不了 CommonMark 已有规则的标签）。
- 要处理合并单元格、嵌套表格 —— GFM 插件对这类复杂表格支持有限，输出通常不符合预期。
- 要求输出里没有多余反斜杠 —— 转义是基于正则的激进取舍，官方说明这是有意为之，属预期行为。

## 安装

**npm / Node.js**（推荐；需要 Node 18+、npm 9+）：

```bash
npm install turndown
```

```bash
# GFM 插件是独立的包，要表格和删除线必须单独装
npm install turndown-plugin-gfm
```

**浏览器**（直接用 CDN 的 IIFE 版本）：

```html
<script src="https://unpkg.com/turndown/dist/turndown.js"></script>
<script>
  var turndownService = new TurndownService()
  console.log(turndownService.turndown('<h1>Hello world!</h1>'))
</script>
```

**其他模块格式**：npm 包里带了 UMD 构建，`lib/turndown.umd.js` 给 Node 用、`lib/turndown.browser.umd.js` 给浏览器用。要在仓库里自己构建就 clone 下来跑 `npm run build`。

包同时提供了 CommonJS、ESM 和浏览器专用变体。Node 环境下它自带 HTML 解析依赖（`@mixmark-io/domino`），**不需要额外装 jsdom**。

## 常用操作

**1. 最小可用：字符串进，Markdown 出**

```js
const TurndownService = require('turndown')

const turndownService = new TurndownService()
const markdown = turndownService.turndown('<h1>Hello world!</h1>')
console.log(markdown)
```

**2. 配一套适合知识库的选项**

默认值是面向「再转回 HTML」设计的，写文档时通常要改。比如默认标题用 `setext` 风格（下划线式）、代码块用缩进式、列表符号是 `*`：

```js
const turndownService = new TurndownService({
  headingStyle: 'atx',        // 用 # 而不是下划线
  codeBlockStyle: 'fenced',   // 用 ``` 围栏而不是四空格缩进
  bulletListMarker: '-',
  emDelimiter: '*',
  strongDelimiter: '**',
  linkStyle: 'inlined',
  hr: '---'
})

const markdown = turndownService.turndown(html)
```

全部选项与默认值：

| 选项 | 可选值 | 默认 |
|---|---|---|
| `headingStyle` | `setext` / `atx` | `setext` |
| `hr` | 任意 thematic break | `* * *` |
| `bulletListMarker` | `-` / `+` / `*` | `*` |
| `codeBlockStyle` | `indented` / `fenced` | `indented` |
| `fence` | 三个反引号 / 三个波浪号 | 三个反引号 |
| `emDelimiter` | `_` / `*` | `_` |
| `strongDelimiter` | `**` / `__` | `**` |
| `linkStyle` | `inlined` / `referenced` | `inlined` |
| `linkReferenceStyle` | `full` / `collapsed` / `shortcut` | `full` |
| `preformattedCode` | `false` / `true` | `false` |

**3. 保留 Markdown 表达不了的元素为原始 HTML**

默认 turndown **不保留任何元素**，全部尝试转成 Markdown。转不了的会被降级成纯文本内容——比如 `<details>` 展开区、`<iframe>`、`<video>` 就没了。用 `keep()` 把它们原样留在输出里：

```js
turndownService.keep(['details', 'summary', 'iframe', 'video'])

turndownService.turndown('<p>Hello <del>world</del><ins>World</ins></p>')
// 若 keep(['del','ins']) → 'Hello <del>world</del><ins>World</ins>'
```

块级元素被保留时会与前后内容用空行隔开。

**4. 整段丢弃不要的元素**

抓来的页面里 `<nav>`、`<footer>`、`<aside>`、`<script>`、`<style>` 通常都是噪音，连内容一起删：

```js
turndownService.remove(['script', 'style', 'nav', 'footer', 'aside', 'noscript'])

turndownService.turndown('<p>Hello <del>world</del><ins>World</ins></p>')
// remove('del') → 'Hello World'
```

注意 `remove` 是**连子内容一起删**，不是只删标签。

**5. 用 GFM 插件补表格和删除线**

CommonMark 里没有表格，turndown 核心不管表格——`<table>` 会被拍成一行行纯文本。要 Markdown 表格必须装插件：

```js
const TurndownService = require('turndown')
const turndownPluginGfm = require('turndown-plugin-gfm')

const turndownService = new TurndownService({ headingStyle: 'atx' })

// 一次性全开：表格 + 删除线 + 任务列表
turndownService.use(turndownPluginGfm.gfm)

// 或只挑需要的
const { tables, strikethrough } = turndownPluginGfm
turndownService.use([tables, strikethrough])

console.log(turndownService.turndown(htmlWithTable))
```

插件也是 MIT。

**6. 自定义规则**

规则就是个 `{ filter, replacement }` 对象。比如让 `<mark>` 变成 `==高亮==`：

```js
turndownService.addRule('mark', {
  filter: ['mark'],
  replacement: function (content) {
    return '==' + content + '=='
  }
})
```

`filter` 可以是标签名字符串、标签名数组，或一个函数 `(node, options) => boolean`——函数形式能拿到节点属性，用来做条件判断：

```js
turndownService.addRule('internalLink', {
  filter: function (node, options) {
    return node.nodeName === 'A' && node.getAttribute('href')?.startsWith('/')
  },
  replacement: function (content, node) {
    return '[' + content + '](https://example.com' + node.getAttribute('href') + ')'
  }
})
```

`addRule` / `keep` / `remove` / `use` 都返回 service 实例，可以链式调用。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 表格转出来全是一行行纯文本 | **turndown 核心不支持表格**，CommonMark 规范里就没有表格语法 | 装 `turndown-plugin-gfm` 并 `service.use(gfm)` |
| 输出里满屏反斜杠（`1\.`、`\*`、`\-`） | turndown 不解析每个元素的 Markdown 语义，而是用一组正则**激进地**转义可能被误读的字符。这是刻意的性能取舍 | 觉得过度就覆写 `TurndownService.prototype.escape`。**代码元素里的文本不会被转义**，放心 |
| `<details>` / `<iframe>` / `<video>` 内容凭空消失 | 默认**不保留任何元素**，没有对应规则的节点只输出其文本内容，标签本身丢掉 | 用 `keep(['details','iframe'])` 保留为原始 HTML |
| `remove()` 之后文字也没了 | `remove` 的作用是**连内容一起删掉**，不是只剥标签 | 只想剥标签、保内容就别用 `remove`，交给默认规则；要精确控制就 `addRule` |
| 自定义规则不生效 | 规则优先级是固定顺序的，`keep` / `remove` / 自定义规则的相对次序会影响谁先命中 | 记住优先级：**空白规则 > 新增规则 > CommonMark 规则 > keep 规则 > remove 规则 > 默认规则**。要让自定义规则接管被 CommonMark 规则覆盖的元素，只能用 `addRule`，`keep` 不够 |
| 多个 `keep` / `remove` 冲突 | 多次调用时**后加的优先级高于先加的** | 按「从宽到严」的顺序调用，或者干脆合并成一个数组一次传 |
| Node 里直接传 DOM 节点报错 | 服务端没有全局 `document` | Node 里传**字符串**；确实要传节点就先在 jsdom / domino 里构造出 DOM |
| 空白元素被特殊处理了 | turndown 有独立的「空白规则」，**优先级高于一切**，连 `addRule` 加的规则都能被它盖过 | 只含空白、且不是 `<a>` / `<td>` / `<th>` / 空元素的节点算「空白」。要改行为用 `blankReplacement` 选项，不要指望加规则 |
| 升级后输出变了 | 不同版本对转义、空白折叠的处理有调整，且项目从 `to-markdown` 改名而来 | 锁住版本号；迁移期参照官方迁移说明。以实际安装版本的行为为准 |

## 能力边界

**覆盖**：

- HTML 字符串 / DOM 元素节点 / 文档节点 / 文档片段节点 → CommonMark 字符串。
- 标准 CommonMark 结构：标题、段落、强调、加粗、链接、图片、列表（有序/无序/嵌套）、引用、代码（行内与块）、水平分割线。
- 输出风格可配置：标题风格、代码块风格（围栏/缩进）、围栏字符、列表符号、强调与加粗分隔符、链接内联/引用式、引用式链接的三种形态、`hr` 字符。
- 扩展机制：`addRule`（加规则）、`keep`（保留为原始 HTML）、`remove`（连内容删除）、`use`（插件），以及 `blankReplacement` / `keepReplacement` / `defaultReplacement` 三个替换函数。
- GFM 支持（需插件）：表格、删除线，以及 `turndown-plugin-gfm` 里的 `gfm` 合集。
- 转义行为可整体替换：覆写 `TurndownService.prototype.escape`。
- 运行环境：Node.js（自带 HTML 解析依赖）与浏览器，含 CJS / ESM / UMD / IIFE 构建。

**不覆盖**：

- **不抓网页**。它只转你给它的 HTML。抓取、去广告、正文提取是上游环节的事。
- **不做表格转 Markdown**（核心）。这是工具自己明确划出的边界，必须装 GFM 插件。
- **不做反向转换**。Markdown → HTML 是另一件事，turndown 只有单向。
- **不做 HTML 净化**。它不检测 XSS、不剥离危险属性、不校验 URL 协议。要输出给不可信环境用，请在前面加 sanitize 环节。
- **不做 Markdown 规范化**。输出直接是字符串，不重排、不格式化、不校验合法性。
- **不保留样式**。`<span style="color:red">` 这类信息在 Markdown 里无处安放，颜色、字号、对齐一律丢失。
- 本 Skill 内不含任何可复制的第三方源码，正文为原创整理，仅引用 API 名称、选项名、许可证等事实性信息。

## 依赖条件

- **Node 路径**：Node.js **18+**、npm **9+**（这是包 `engines` 字段声明的下限）。运行时依赖只有 `@mixmark-io/domino`，随包自动装好。
- **浏览器路径**：任意支持 ES5 的现代浏览器即可；用 CDN 时无需构建工具。
- **网络**：仅安装阶段需要 npm registry。转换过程完全离线。
- **可选**：`turndown-plugin-gfm`（表格与删除线）、`jsdom` 或 `domino`（仅在 Node 里需要构造 DOM 节点时才用得上）。

## 已知限制

- **转义策略激进且基于正则**。官方明确说明这是为了避免「把每个元素内容都当 Markdown 解析」带来的复杂度和性能开销而做的取舍。所以输出里出现多余的反斜杠是预期行为，不是 bug。
- **表格需要插件，且插件对复杂表格支持有限**。合并单元格（`rowspan` / `colspan`）、嵌套表格、表头与数据行结构不规范的表格，转出来通常不符合预期——Markdown 表格语法本身就表达不了这些。
- **无对应规则的元素会丢失标签**（默认降级为文本），这包括 `<details>`、`<figure>`、`<mark>` 这类语义化标签，也包括嵌入式内容。
- **规则优先级固定**，`keep` 无法覆盖 CommonMark 已有规则的标签；要让 `<p>` 这种行为不同，只能 `addRule`。多个 `keep` / `remove` 的先后顺序也有语义（后加的更优先）。
- **`preformattedCode` 选项的 `true` 行为**指向一个上游 issue 讨论的空白折叠问题，不是完全等价的「保留原样」。
- **不处理 `<style>` 与内联 CSS 的语义**。视觉信息（颜色、字号、布局）在输出里无法体现。
- 许可证为 MIT。版本号与行为以你实际安装的版本为准。

## 自检清单

- [ ] 需要表格或删除线时，确认装了 `turndown-plugin-gfm` 并 `use()` 了它——只改选项是不够的。
- [ ] 抓来的 HTML 里明确 `remove()` 掉了 `script` / `style` / `nav` / `footer` 这类噪音，且知道 `remove` 会连内容一起删。
- [ ] 需要保留的语义元素（`details` / `iframe` / `video`）已加进 `keep()`，确认没有内容凭空消失。
- [ ] 转换前确认了 HTML 里没有需要保真的表格结构（合并单元格会丢）。
- [ ] 输出风格（`headingStyle` / `codeBlockStyle` / `bulletListMarker`）已按目标场景调整，没有沿用默认的 `setext` + 缩进代码块。
- [ ] 抽样肉眼比对过转换结果：标题层级、代码块内容、链接目标是否正确。
- [ ] 代码块里的内容没有被动过（turndown 不转义代码元素内的文本）。
- [ ] 如果输出会进不可信环境，前面已经接了 HTML 净化环节。
- [ ] 批量脚本里对每个文件做了 try/catch，单个文件失败不会中断整批。
- [ ] 锁定了依赖版本，避免升级后转义策略变化导致大批输出漂移。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/mixmark-io/turndown | 上游仓库（安装与完整文档以它为准） |

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
