# 三剪客 · docx 转 HTML Skill

把 .docx 按语义转成干净的 HTML 片段：认样式名不认字体字号，输出可直接嵌进网页。

---

## 前置条件

- Node.js 环境（上游标注 `engines.node >= 12.0.0`）
- 输入必须是 `.docx`，老的 `.doc` 需先转换
- 文档最好是用样式名规范标记的（`Heading 1`、列表样式等），否则转换结果会比较扁平
- 处理**不可信来源**的文档时，必须自备 HTML 消毒环节，mammoth 本身不做消毒

---

## 使用

```bash
npm install -g mammoth

mammoth document.docx output.html                  # 基础转换，图片内联
mammoth document.docx                              # 不写输出文件则打到标准输出
mammoth document.docx --output-dir=output-dir      # 图片另存为独立文件（与输出路径互斥）
mammoth document.docx output.html --style-map=custom-style-map   # 自定义样式映射
```

Node 库用法：

```javascript
var mammoth = require("mammoth");
mammoth.convertToHtml({path: "path/to/document.docx"})
    .then(function(result){
        var html = result.value;
        var messages = result.messages;
    });
```

`SKILL.md` 里有 styleMap 写法、图片处理器、`extractRawText`、`embedStyleMap` 以及完整避坑表。

---

## 依赖

- 运行依赖：Node.js；`npm install mammoth` 会自动装上 jszip、underscore、argparse 等依赖
- 浏览器端可改用独立构建文件 `mammoth.browser.js`
- 无账号、无 Key、无外部服务；转换过程离线进行，只有安装依赖需要联网

---

## 安全

- 不内嵌任何密钥
- **mammoth 不做任何消毒**：源文档可含 `javascript:` 链接，也可引用文档外文件
- 不可信文档的转换结果必须自行消毒后再渲染，否则存在 XSS 与本地文件泄露风险
- 除非来源完全可信，不要开启 `externalFileAccess`
- 官方提示可构造出导致性能病态的文档，处理不可信输入建议隔离运行并加超时
- `--output-dir` 写出图片时会覆盖同名文件，输出目录请单独准备

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`mammoth.js`
- 仓库：https://github.com/mwilliamson/mammoth.js

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
