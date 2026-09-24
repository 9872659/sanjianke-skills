# 三剪客 · 电子表格读写 Skill

SheetJS：电子表格读写 的安装、常用命令与避坑要点

---

## 前置条件

- 一个 JavaScript 运行环境：Node.js（推荐，且优先用 CommonJS）、浏览器、Deno 或 Bun。
- 无需安装 Office / LibreOffice / Java，没有系统级依赖。
- 需要能访问官方 CDN `https://cdn.sheetjs.com`；内网环境请先按 `SKILL.md` 里的 vendoring 做法把 tarball 存进仓库。

---

## 使用

这个包把「怎么装、怎么写、什么时候别用」讲清楚，主体是 `SKILL.md`，建议按顺序读：

1. **什么时候用 / 不用** —— 先判断需求是否落在社区版能力内（数据 vs 样式）。
2. **安装** —— Node 的 tarball 装法、浏览器独立脚本、ESM 页面的写法。
3. **常用操作** —— 读文件、工作表转 JSON、组新表写文件、格式转换、写 Buffer、流式出 CSV、命令行转一手。
4. **常见坑** —— npm 上的旧版本、ESM 依赖注入、日期基准、CSV 的 BOM、加密格式、内存占用等。

典型调用方式：

```js
const XLSX = require("xlsx");
const wb = XLSX.readFile("input.xlsx");
const ws = wb.Sheets[wb.SheetNames[0]];
const rows = XLSX.utils.sheet_to_json(ws);
```

---

## 依赖

- 运行时：Node.js / 浏览器 / Deno / Bun 任一；库本体是纯 JavaScript。
- 库本体通过官方 CDN 的 tarball 安装，包名依旧是 `xlsx`。
- 公开 npm registry 上的 `xlsx` 不是权威来源（版本停在 0.18.5），不要从那里装。
- 导出 Apple Numbers 格式时需要额外的 `xlsx.zahl.js` 提供 Base64 载荷。

---

## 安全

- 不内嵌任何密钥、Token 或 Cookie。
- 只读写调用方显式指定的文件路径，不做目录遍历、不主动上传数据。
- 不处理加密工作簿：社区版仅支持 XLS 的 XOR，其余加密方式会直接报错，遇到时如实告知用户，不做绕过。
- 官方文档说明扫描工具报出的「原型污染」为误报（相关问题在 0.19.3 已处理）；若在扫描配置中抑制该告警，请记录理由。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`SheetJS`
- 仓库：https://github.com/SheetJS/sheetjs

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
