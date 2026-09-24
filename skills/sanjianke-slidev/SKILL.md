---
name: sanjianke-slidev
slug: sanjianke-slidev
displayName: 三剪客 · Markdown 写演示文稿
description: "Slidev：Markdown 写演示文稿 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Slidev：Markdown 写演示文稿 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · Markdown 写演示文稿

Slidev 把一份 Markdown 讲稿直接跑成能放的网页幻灯片：`---` 分页、YAML 写每页配置、代码块自带高亮和逐步演示，还能塞 Vue 组件做真交互。适合「内容是文字和代码、不想在 PPT 里拖排版」的人。

它省事的地方在于**内容与样式分离**：你只维护 `slides.md`，主题、字体、页眉页脚由主题包决定；要交付时再一条命令导出 PDF 或 PPTX。

要注意它是**开发者工具**，不是 Office 替代品——产物是网页，PPTX 导出只是位图快照。

**上游项目**：`Slidev`　**仓库**：https://github.com/slidevjs/slidev

## 什么时候用 / 不用

**用它**：

- 「我把讲稿写成 Markdown 了，想直接当幻灯片放」——技术分享、内部分享、课程讲义。
- 内容里大量代码，需要高亮、行号、逐行点击展开。
- 需要公式（LaTeX）、流程图（Mermaid / PlantUML）、图标，且希望写在文本里而不是画出来。
- 需要把 deck 变成一个网址，发给别人在线看，并保留动画和交互。
- 需要演示者模式：一块屏给观众，另一块屏给自己看备注、下一页和计时。

**不要用它**：

- 需求核心是「给我一个能在 PowerPoint 里继续改的 .pptx」——Slidev 导出的 PPTX 每页都是图片，文字不可选、不可编辑。
- 要严格套用公司 Office 母版、占位符、审阅批注流程——这是 PowerPoint / WPS 的强项。
- 需要精细自由排版（任意拖拽、图层、精确到点的图文绕排）——用 Keynote / Figma / Canva。
- 只有三五页、发完就丢——直接写 Markdown 或纯 PDF 更快，不值得起一个 Node 工程。
- 执行环境不能装 Node.js、不能拉依赖、不能跑浏览器渲染——`slidev export` 依赖 Playwright 下载 Chromium，受限沙箱里通常跑不通。

## 安装

前置要求（官方明确写明）：**Node.js >= 20.12.0**。包管理器 pnpm / npm / yarn / bun / deno 任选，官方推荐 pnpm。

```bash
# 方式一（推荐）：建一个带工程结构的 Slidev 项目
npm i -g pnpm          # 没装过 pnpm 才需要
pnpm create slidev

# 方式二：官方标注 Not recommended——npm 每次新建都会重新下载依赖，慢且占空间
npm init slidev@latest

# 方式三：单文件用法，全局装 CLI 后直接对 md 起服务
npm i -g @slidev/cli
slidev slides.md

# 导出 PDF / PPTX / PNG 的额外依赖（必须装，否则 export 会失败）
npm i -D playwright-chromium
```

Windows 上命令相同，在 PowerShell 里执行即可。若 `npm i -g` 报权限错误，改用无需管理员的全局目录或调整 npm 全局前缀，不要长期用管理员权限跑。

## 常用操作

```bash
# 1) 起本地开发服务器：默认 3030 端口，改端口 / 自动开浏览器
slidev slides.md --port 3030 --open
npm run dev                  # npm init slidev 生成的项目里已配好这条脚本

# 2) 远程控制：手机当遥控器（传了密码则演示者模式私有）
slidev slides.md --remote mypassword

# 3) 导出 PDF：默认输出 ./slides-export.pdf
slidev export
slidev export --output 我的分享 --dark            # 指定文件名 + 暗色主题
slidev export --range 1,6-8,10                     # 只导第 1、6~8、10 页
slidev export --with-clicks                        # 每个点击动画各出一页
slidev export --timeout 60000 --wait 1000          # 大 deck / 动画没渲完时给足时间
slidev export slides1.md slides2.md                # 一次导多个文件，各自出一份

# 4) 导出其它格式
slidev export --format pptx        # 每页是图片；讲者备注会带进 PPTX
slidev export --format png         # 一页一张 PNG
slidev export --format md          # Markdown，内嵌编译后的 PNG

# 5) 构建可托管的静态站点，产物在 dist/
slidev build --base /my-talk/ --out dist
slidev build --download            # SPA 里允许访客下载 PDF
slidev build --without-notes       # 不把讲者备注打包进 SPA

# 6) 其它子命令
slidev format slides.md            # 只整理 md 的组织结构，不改内容
slidev theme eject --dir theme     # 把当前主题弹到本地改
slidev mcp slides.md               # 起 MCP server，让 AI 直接读改这份 deck
```

一份最小可跑的 `slides.md`：

```md
---
theme: seriph
title: 我的分享
---

# 第一页

正文内容。文件开头这段 frontmatter 是 headmatter，管全局。

---
layout: center
background: /bg.png
---

# 第二页

<!-- 备注必须放在本页最后，只在演示者模式显示 -->
```

要点：页面用**前后带空行的 `---`** 分隔；每页开头可写自己的 frontmatter（`layout` / `background` / `class` 等）；代码块写成 ` ```ts ` 指定语言即可高亮。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `npx slidev` 找不到包 / 404 | 包名是 `@slidev/cli` 而不是 `slidev`，官方也提示通常不支持这样调用 | 用全局 `slidev`，或 `npx @slidev/cli`；工程内直接用 `npm run dev` |
| `slidev export` 报 Playwright / 找不到浏览器 | 没装渲染依赖 | `npm i -D playwright-chromium`；Linux 容器还要补 Chromium 的系统依赖 |
| 导出的 PDF 缺内容或动画停在一半 | 渲染速度快过动画播放 | `slidev export --wait 1000`；仍不行再试 `--wait-until domcontentloaded` |
| 导出的 PDF / PNG 里 emoji 变方块 | 环境缺 emoji 字体，CI 容器里最常见 | 装 Noto Color Emoji 到系统字体目录后执行 `fc-cache -fv` |
| 拿到的 PPTX 里文字选不中、改不了 | PPTX 每页导出为图片，设计如此 | 别承诺「可编辑 PPTX」；要能改就交付 PDF，或让对方也装 Slidev 用 `.md` |
| 页面被错误合并 / 多切出一页 | `---` 前后没留空行；或正文里出现了裸的连续 `---`（例如示例代码） | 分隔线前后各留空行；示例里的分隔符用四个反引号的外层代码块包起来 |
| 本该全局生效的配置（主题等）只在第一页生效 | 只有第一段 frontmatter 是 headmatter，才是全局的 | 主题、标题、`addons`、`fonts` 一律写在文件开头的块里 |
| 讲者备注在演示者模式里不显示 | 备注不在该页末尾 | 备注必须是该页**最后一个** `<!-- -->` 块，页中间的注释不算备注 |
| `npm run slidev --port 8080` 参数没生效 | npm 把参数自己吃掉了 | 加 `--` 分隔：`npm run slidev -- --port 8080` |
| 起服务报端口被占用 | 默认 3030 被别的进程占了 | 换端口：`slidev slides.md --port 8081` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 首次安装依赖、拉取主题 / 图标 / 字体；开发服务器监听本地端口 |
| 读取文件 | 是 | 读取 `slides.md`、`public/` 下的图片、样式与组件 |
| 写入文件 | 是 | 生成 `node_modules/`、`dist/`、导出的 PDF / PPTX / PNG |
| 凭证 | 否 | 不需要任何账号或 API Key |
| 子进程 / 后台常驻 | 是 | 开发服务器与导出时的浏览器渲染进程需要常驻，用完要主动关掉 |

## 触发场景

- 「帮我把这份 Markdown 讲稿做成幻灯片。」
- 「这个技术分享想用代码高亮、逐行展示，怎么做？」
- 「把 slides.md 导成 PDF 发群里。」
- 「我想让幻灯片能在线看，给我一个链接。」
- 「演示的时候我想看到备注和下一页，还要计时。」
- 「这份 deck 想换个主题 / 加个 logo / 改配色。」

## 能力边界

**覆盖**：

- 用 Markdown 写网页幻灯片，支持逐页 frontmatter、点击动画、LaTeX 公式、Mermaid / PlantUML 图、图标与 UnoCSS 工具类。
- 内嵌 Vue 组件做真交互（可运行的代码演示、实时状态）。
- 导出 PDF / PPTX / PNG / md；也可以在浏览器 `/export` 页面里导出。
- `slidev build` 产出静态 SPA，可部署到任意静态托管。
- 演示者模式、绘画批注、录制、手机远程遥控。
- 主题与插件按 npm 包管理，可 `theme eject` 后本地改。

**不覆盖**：

- 不以「可编辑 .pptx」为产物；导出 PPTX 是位图快照。
- 不做 Office 母版 / 占位符级别的模板还原，也不参与 Office 审阅批注流程。
- 不做视频剪辑与成片输出；录制只到屏幕录制加摄像头画面。
- 不做部署：只给 `dist/` 或本地服务，托管要交给别的平台。
- 不替代 Keynote / PowerPoint 的自由图形排版能力。

## 依赖条件

- **Node.js >= 20.12.0**（官方硬性要求），配一个包管理器（pnpm / npm / yarn / bun / deno）。
- 导出 PDF / PPTX / PNG 需额外安装 `playwright-chromium`，首次会下载 Chromium，体积较大。
- 浏览器内的导出 UI 需要现代 Chromium 系浏览器。
- 不需要账号、不需要 API Key；装好之后本地演示无需联网。

## 已知限制

- PPTX 每页是图片：文字不可选、不可编辑；PPTX 模式下 `--with-clicks` 默认开启，要关掉得显式传 `--with-clicks false`。
- 交互能力（跑代码、Vue 组件状态、点击动画）在导出的 PDF / PPTX / PNG 里不可用；要保留交互只能托管 SPA。
- 首装成本高：Node 工具链加 Chromium，冷启动机器上比较慢。
- 导出渲染受本机字体影响，容器环境里 emoji、中文字体、代码连字都可能缺。
- 主题与插件是独立 npm 包，上游更新可能带来样式差异，正式交付前建议锁版本。

## 自检清单

执行前：

- [ ] 确认 Node.js 版本 >= 20.12.0（`node -v`）。
- [ ] 确认交付形态：只在线看 → `build`；要发文件 → `export` 且已装 `playwright-chromium`。
- [ ] 确认入口文件名（默认 `slides.md`），多文件时逐个列出。

执行后：

- [ ] 导出 / 构建命令退出码为 0，产物文件确实存在且体积合理。
- [ ] 抽查产物：页数对不对、中文字体和 emoji 有没有变方块、代码高亮是否正常。
- [ ] 用了 `--range` 或 `--with-clicks` 的场景，核对页数是否符合预期。
- [ ] 关掉遗留的开发服务器与浏览器渲染进程。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| `references/cli-reference.md` | CLI 子命令与导出参数速查（dev / build / export / format / theme / mcp） |
| https://github.com/slidevjs/slidev | 上游仓库（安装与完整文档以它为准） |

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
