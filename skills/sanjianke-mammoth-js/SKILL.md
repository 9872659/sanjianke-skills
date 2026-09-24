---
name: sanjianke-mammoth-js
slug: sanjianke-mammoth-js
displayName: 三剪客 · docx 转 HTML
description: "mammoth.js 把 .docx 按语义转成干净 HTML：Heading 1 变 h1、列表变 ul/li，忽略字体字号颜色，输出可直接嵌网页。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "mammoth.js 的 CLI 与 Node 库用法、自定义 styleMap 写法、图片抽离与外链图片处理，以及不消毒不可信文档、样式靠语义映射、表格边框丢失、Markdown 支持已废弃等关键坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档处理
  - docx
  - Node.js
---

# 三剪客 · docx 转 HTML

Word 文档要进网页、进后台编辑器、进知识库，直接复制粘贴会带出一堆 `mso-` 样式和 `<span style="font-family:宋体">`，粘完 HTML 又脏又难维护。mammoth.js 换了个思路：**不看你的字体和颜色，只看你用了哪些样式名**——`Heading 1` 就转成 `<h1>`，列表就转成 `<ul>/<li>`，输出的是干净、语义化的 HTML 片段。

所以它对"用样式规范写出来的文档"效果很好，对"全靠手动加粗、手动调字号堆出来的文档"效果一般。这一点决定了它该不该用，比它的参数更重要。

**上游项目**：`mammoth.js`　**仓库**：https://github.com/mwilliamson/mammoth.js

## 什么时候用 / 不用

**用它**：

- "把这份 Word 转成 HTML，我要放到网站上。"——输出是**HTML 片段**（不是完整文档），正好嵌进现有页面。
- "批量把一批 docx 转成 HTML 存进知识库 / CMS。"——CLI 一条命令一个文件，适合脚本循环。
- "我的文档有自定义样式（比如 `WarningHeading`），要映射成我自己的 CSS 类。"——`--style-map` 或 API 的 `styleMap` 选项就是干这个的。
- "图片不要内联成一坨 base64，要单独存文件。"——加 `--output-dir`，图片会另存为独立文件。
- "我只要纯文本，不要任何格式。"——用 `mammoth.extractRawText()`，比 convertToHtml 更直接。
- "我要在浏览器里直接转，不想传服务器。"——仓库自带 web demo，也有 `mammoth.browser.js` 独立文件。

**不要用它**：

- **文档来自不可信来源（用户上传）且你要直接渲染结果**——官方明确警告 mammoth **不做任何消毒**，源文档可以带 `javascript:` 链接，也可以引用文档外部的文件。必须自己再过一遍 HTML 消毒（如 DOMPurify），否则是明确的 XSS 与本地文件泄露风险。
- **要像素级还原 Word 排版**——它故意丢掉字体、字号、颜色、页边距、分页，追求的是语义而不是外观。要保真用 LibreOffice 无头模式转 PDF 再看需求。
- **要转 Markdown**——官方已把 Markdown 支持标记为**废弃**，推荐先生成 HTML 再用别的库转 Markdown。`--output-format=markdown` 还能用，但官方不推荐、结果也可能更差。
- **要处理 .doc（老格式）**——mammoth 只吃 .docx。老 .doc 先转成 .docx。
- **表格要保留边框和样式**——官方明说表格本身的格式（比如边框）目前被忽略，只保留单元格里文字的格式。
- **要处理复杂文档的完美转换**——官方自己承认 docx 结构与 HTML 结构差异很大，复杂文档的转换"不太可能完美"，mammoth 在只用样式做语义标记的文档上表现最好。

## 安装

需要 Node.js 环境。作为库用：

```bash
npm install mammoth
```

作为命令行工具全局安装：

```bash
npm install -g mammoth
```

装完验证：

```bash
mammoth --help
```

浏览器端可以直接引用仓库里的独立构建文件 `mammoth.browser.js`（包含 mammoth 及其全部依赖）；自己从源码构建时用 `make setup` 生成该文件，开发用的 web demo 是 `browser-demo/index.html`。

其他语言的官方移植版本（Python、Java/JVM、.NET、WordPress 插件）各有独立仓库，不在本包范围内，用哪个语言就去对应仓库看安装方式。

## 常用操作

**1. 最基础的一次转换**

```bash
mammoth document.docx output.html
```

不写输出文件时结果写到标准输出：

```bash
mammoth document.docx
```

**2. 图片抽成独立文件**

默认图片是内联在 HTML 里的（base64 data URI）。指定 `--output-dir` 后改为写到独立文件：

```bash
mammoth document.docx --output-dir=output-dir
```

注意两点：同名文件会被**直接覆盖**；`--output-dir` 与输出文件路径参数是**互斥**的，加了 `--output-dir` 就不要再传 `output.html`，否则参数冲突报错。

**3. 自定义样式映射（把 Word 样式映射到自己的 HTML 结构）**

```bash
mammoth document.docx output.html --style-map=custom-style-map
```

样式映射文件内容形如：

```
p[style-name='Aside Heading'] => div.aside > h2:fresh
p[style-name='Aside Text'] => div.aside > p:fresh
```

**4. 在 Node 里用库（带消息回执）**

```javascript
var mammoth = require("mammoth");

mammoth.convertToHtml({path: "path/to/document.docx"})
    .then(function(result){
        var html = result.value;        // 生成的 HTML
        var messages = result.messages; // 转换过程中的警告与错误
        console.log(messages);
    })
    .catch(function(error) {
        console.error(error);
    });
```

入参也可以是缓冲区：Node 里用 `{buffer: buffer}`，浏览器里用 `{arrayBuffer: arrayBuffer}`。

**5. 只要纯文本**

```javascript
mammoth.extractRawText({path: "path/to/document.docx"})
    .then(function(result){
        var text = result.value;   // 纯文本，每个段落后面跟两个换行
    });
```

**6. 自定义图片处理（比如上传到对象存储再回填 URL）**

```javascript
var options = {
    convertImage: mammoth.images.imgElement(function(image) {
        return image.readAsBase64String().then(function(base64) {
            return { src: "data:" + image.contentType + ";base64," + base64 };
        });
    })
};
mammoth.convertToHtml({path: "document.docx"}, options);
```

`image` 对象提供 `contentType` 以及 `readAsArrayBuffer()` / `readAsBuffer()` / `readAsBase64String()` 三种读法。

**7. 用样式映射控制加粗、斜体、下划线、删除线的输出标签**

```
b => em              # 加粗改输出 <em>
i => strong          # 斜体改输出 <strong>
u => em              # 下划线（默认被忽略）改为输出 <em>
strike => del        # 删除线改输出 <del>
comment-reference => sup   # 让被默认忽略的批注显示出来
```

默认行为是：加粗 → `<strong>`、斜体 → `<em>`、删除线 → `<s>`、**下划线被忽略**（因为下划线在网页里容易和链接混淆）、**批注被忽略**（会附加到文档末尾，用 `comment-reference` 映射控制外层标签）。

**8. 把样式映射直接嵌进 docx 文件（之后任何人用 mammoth 打开都会用它）**

```javascript
mammoth.embedStyleMap({path: sourcePath},
    "p[style-name='Section Title'] => h1:fresh")
    .then(function(docx) {
        fs.writeFile(destinationPath, docx.toBuffer(), callback);
    });
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 转出来的 HTML 里字体、字号、颜色、行距全没了 | 这是**设计意图**，不是 bug。mammoth 用语义信息转换，刻意忽略这些纯外观细节 | 只要语义结构就接受它；要保真度就换路线（LibreOffice 无头转 PDF/HTML，或用别的保真型转换器） |
| 用户上传的 docx 转完直接插进页面，出现 `javascript:` 链接或读到服务器上的其他文件 | 官方明确说明：mammoth **不做任何消毒**。源文档可含 `javascript:` 链接，也可引用文档外文件（外部文件访问默认关闭，但可通过 `externalFileAccess: true` 打开） | 绝对不要把不可信文档的转换结果未经消毒直接嵌进页面。转换后过一遍 HTML 消毒库；除非来源可信，**不要**开 `externalFileAccess` |
| 两个连续的 `Heading 1` 段落被合并进同一个 `<h1>` | mammoth 的"新鲜度"（freshness）机制：只在必要时才关闭 HTML 元素，否则复用 | 在样式映射里加 `:fresh` 修饰符强制新建元素：`p[style-name='Heading 1'] => h1:fresh`。要嵌套结构时更要注意，如 `div.aside > h2:fresh` |
| 自定义的 styleMap 写法对，但完全没生效 | 匹配的是**样式名**（Word / LibreOffice 界面上显示的名字），不是 .docx 内部的 style ID；两者常被搞混 | 优先按名字匹配 `p[style-name='Heading 1']`；确知内部 ID 时可用 `p.Heading1` 的点号形式。前缀匹配用 `p[style-name^='Heading']` |
| 自定义 styleMap 加了，但默认映射还在干扰 | 用户定义的映射会优先于默认映射，但默认映射并不会自动关掉 | 需要完全接管时在 API 里设 `includeDefaultStyleMap: false`；文档内嵌的样式映射可用 `includeEmbeddedStyleMap: false` 忽略 |
| HTML 文件在浏览器里打开，中文/重音字符显示成乱码 | mammoth 输出的是**HTML 片段**，UTF-8 编码但片段里没有显式声明编码，浏览器默认编码不是 UTF-8 时就会错 | 把片段嵌进带 `<meta charset="utf-8">` 的完整页面，或在服务端以 `Content-Type: text/html; charset=utf-8` 返回 |
| 输出里的表格没有边框、没有底纹 | 官方说明：表格本身的格式（如边框）目前被忽略，只处理单元格内文字的格式 | 表格样式改由自己的 CSS 控制；需要保留表格视觉就走保真型转换器 |
| 处理某些文档时 CPU / 内存飙升 | 官方承认可以构造出导致性能病态的文档 | 处理不可信输入时把转换放到独立线程 / 子进程并加超时，避免拖垮服务；也可考虑限定文件大小 |
| 用 `--output-format=markdown` 转出来的结果质量差 | Markdown 支持已被官方标记为**废弃**，官方明确建议先生成 HTML 再用独立库转 Markdown，效果更好 | 按官方建议走两段式：`mammoth` 出 HTML → 用专门的 HTML 转 Markdown 库 |
| 输出文件被悄悄覆盖了 | `--output-dir` 写图片时官方说明已存在文件会被覆盖 | 每次转换输出到独立目录，或转换前检查目标路径 |
| 加了 `--output-dir` 又传了 `output.html`，命令报参数冲突 | CLI 把输出文件路径和 `--output-dir` 定义为**互斥**的两个选项 | 二选一：要图片内联就给输出文件路径，要图片独立就用 `--output-dir`（此时 HTML 也写进该目录，不写标准输出） |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 仅 `npm install` 时需要联网拉包；转换过程本身完全本地 |
| 读取文件 | 是 | 读取待转换的 .docx 文件 |
| 写入文件 | 是 | 写 HTML 输出文件；用 `--output-dir` 时还会写出抽取出来的图片（同名会被覆盖） |
| 凭证 | 否 | 无账号、无 Key。若你用自定义 `convertImage` 上传图片到云存储，则需要你自己另外配置该存储的凭证 |
| 子进程 / 后台常驻 | 否 | 一次性 CLI 调用或 Node 内的一次 Promise 调用，无常驻服务 |

## 触发场景

- "把这份 Word 转成 HTML。"
- "这批 docx 批量转网页，图片要单独存。"
- "Word 里的自定义样式要映射成我们前端的 CSS class。"
- "我只要 docx 里的纯文字，不要格式。"
- "转出来的 HTML 里 `<h1>` 都黏在一起了，怎么拆开？"
- "用户上传的 docx 转成 HTML 安全吗？"

## 能力边界

**覆盖**：

- .docx → HTML 片段（也支持浏览器端与 Node 端），可只抽纯文本
- 语义映射：标题、列表、表格（内容部分）、脚注与尾注、图片、加粗、斜体、下划线、删除线、上标、下标、链接、换行、文本框、批注
- 自定义 styleMap：按样式名 / 样式名前缀 / 样式 ID 匹配，支持 `:fresh`、`:separator('...')`、CSS class、属性、`!` 忽略、`>` 嵌套
- 自定义图片处理器（`mammoth.images.imgElement`），可把图片改写为任意形式的 `<img>` 属性
- 文档变换（`transformDocument` 及 `mammoth.transforms.paragraph` / `.run` / `.getDescendants` / `.getDescendantsOfType`）
- 把 styleMap 嵌入 docx 文件（`embedStyleMap`）
- 多条 `mammoth.convertToHtml` 返回的 promise 结果里带 `messages`，可读取转换过程中的警告与错误

**不覆盖**：

- 任何消毒工作：不清理 `javascript:` 链接，默认也不允许访问文档外部文件
- 视觉保真：字体、字号、颜色、页边距、分页等信息有意丢弃
- 表格的边框等表格级格式
- 老 .doc 格式（只支持 .docx）；也不同于该项目的 Python / Java / .NET 移植版
- Markdown 的可靠输出（官方已废弃该支持）
- PDF、PPT、Excel 等其他文档格式

## 依赖条件

- Node.js 环境（CLI 与 Node 库用法），上游 `package.json` 标注 `engines.node >= 12.0.0`；浏览器端需要支持 Promise 与相应模块系统
- `npm install mammoth`（库）或 `npm install -g mammoth`（命令）
- 无账号、无 Key、无外部服务依赖
- 转换本身离线；只有 `npm install` 需要联网

## 已知限制

1. 不做任何消毒，不可信文档的转换结果不能直接渲染，必须自己加消毒环节。
2. 输出是 HTML 片段而非完整文档，没有 `<meta charset>`，需要宿主页面自己声明 UTF-8。
3. 转换质量取决于文档是否"用样式做语义标记"；手动排版堆出来的文档效果差，官方承认复杂文档"不太可能完美"。
4. 表格级格式（边框等）被忽略。
5. Markdown 支持已废弃，官方推荐 HTML → 独立库转 Markdown 的两段式路线。
6. `transformDocument` 相关 API 被官方标注为**不稳定**，可能随版本变化，依赖它就要锁版本并充分测试。
7. 无法排除存在可构造的性能病态文档，处理不可信输入时建议隔离运行并加超时。

## 自检清单

执行前：

- [ ] 确认输入是 `.docx` 而不是老的 `.doc`
- [ ] 判断文档来源是否可信：不可信就必须在渲染前往 HTML 消毒
- [ ] 确认文档是用样式名规范标记的（否则转换结果会偏平），必要时先准备 styleMap
- [ ] 明确输出目标是 HTML 片段还是要嵌进完整页面（后者要自己补 `<meta charset="utf-8">`）
- [ ] 需要图片独立成文件时，确认 `--output-dir` 指向一个专门目录，避免覆盖已有文件

执行后：

- [ ] 检查 `result.messages` 或 CLI 的提示信息，确认有没有警告被忽略
- [ ] 抽查标题层级是否连续（连续同名标题要用 `:fresh`，否则会被合并）
- [ ] 检查图片：是内联 base64 还是已落盘，路径能否被目标页面访问到
- [ ] 检查链接里有无 `javascript:` 等危险协议
- [ ] 确认表格内容完整（边框丢失是预期行为，内容丢失不是）
- [ ] 确认中文字符在浏览器中显示正常

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/mwilliamson/mammoth.js | 上游仓库（安装与完整文档以它为准） |

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
