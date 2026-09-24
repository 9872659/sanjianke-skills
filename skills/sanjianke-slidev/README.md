# 三剪客 · Markdown 写演示文稿 Skill

教你用 Slidev 把一份 Markdown 讲稿变成能放的网页幻灯片：装什么、怎么起服务、怎么导出 PDF / PPTX / PNG、以及几个只有踩过才知道的坑。

---

## 前置条件

- **Node.js >= 20.12.0**（Slidev 官方硬性要求），并有一个包管理器（推荐 pnpm）。
- 想导出 PDF / PPTX / PNG，需要额外安装 `playwright-chromium`（首次会下载 Chromium）。
- 不需要账号，不需要 API Key。
- 用 npm 跑脚本传参时记得加 `--`：`npm run slidev -- --port 8080`。

---

## 使用

1. 建工程：`pnpm create slidev`（或全局装 `@slidev/cli` 后直接 `slidev slides.md`）。
2. 写内容：编辑 `slides.md`，用前后带空行的 `---` 分页；文件开头那段 frontmatter 是全局的 headmatter。
3. 预览：`slidev slides.md --open`，默认 <http://localhost:3030>。
4. 交付：`slidev export`（PDF）、`slidev export --format pptx`、或 `slidev build` 出静态站点。
5. 遇到具体报错，先查 `SKILL.md` 的「常见坑」表，再查 `references/cli-reference.md`。

完整操作步骤、常见坑、能力边界见 `SKILL.md`。

---

## 依赖

- Node.js 与包管理器：运行 Slidev 本体。
- `playwright-chromium`：导出 PDF / PPTX / PNG 时的渲染引擎。
- 系统字体：缺失 emoji 或中文字体时导出会出方块，需自行补字体。

---

## 安全

- 不内嵌任何密钥。
- 依赖安装会访问 npm registry，属于正常网络行为；离线环境请预先准备好依赖。
- 导出会启动无头浏览器并把渲染进程留在后台，任务结束后应关闭开发服务器与相关进程。
- Skill 本体只包含文档，不含上游项目的源代码；上游代码的问题请走上游仓库的 Issues。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Slidev`
- 仓库：https://github.com/slidevjs/slidev

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
