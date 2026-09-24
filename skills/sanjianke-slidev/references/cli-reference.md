# Slidev CLI 速查

参数来源：官方文档 CLI 页与导出页（<https://sli.dev/builtin/cli>、<https://sli.dev/guide/exporting>）。不同版本可能新增参数，实际以 `slidev --help` 与官方文档为准。

## 通用约定

- 选项值可用空格或 `=` 传入：`slidev --port 8080` 等价于 `slidev --port=8080`。
- 布尔选项可省略 `true`：`slidev --open` 等价于 `slidev --open true`。
- 用 npm 跑脚本时要在选项前加 `--`，否则参数被 npm 吃掉：`npm run slidev -- --remote --port 8080 --open`。
- 二进制名是 `slidev`，但 npm 包名是 `@slidev/cli`。

## `slidev [entry]` — 开发服务器

| 选项 | 类型 / 默认值 | 说明 |
|---|---|---|
| `[entry]` | string，默认 `slides.md` | 幻灯片 Markdown 入口 |
| `--port`, `-p` | number，默认 `3030` | 端口 |
| `--base` | string，默认 `/` | base URL |
| `--open`, `-o` | boolean，默认 `false` | 自动打开浏览器 |
| `--remote [password]` | string | 监听公网地址并开启远程控制；传密码则演示者模式私有 |
| `--bind` | string，默认 `0.0.0.0` | remote 模式下监听的 IP |
| `--log` | `error` / `warn` / `info` / `silent`，默认 `warn` | 日志级别 |
| `--force`, `-f` | boolean，默认 `false` | 忽略缓存重新打包 |
| `--theme`, `-t` | string | 覆盖主题 |

## `slidev build [entry]` — 构建静态 SPA

| 选项 | 类型 / 默认值 | 说明 |
|---|---|---|
| `--out`, `-o` | string，默认 `dist` | 输出目录 |
| `--base` | string，默认 `/` | base URL，部署到子路径时必须改 |
| `--download` | boolean，默认 `false` | 允许在 SPA 内下载 PDF |
| `--theme`, `-t` | string | 覆盖主题 |
| `--without-notes` | boolean，默认 `false` | 不把讲者备注打进 SPA |

## `slidev export [...entry]` — 导出

依赖：先装 `playwright-chromium`（`npm i -D playwright-chromium`）。

| 选项 | 类型 / 默认值 | 说明 |
|---|---|---|
| `--output` | string，默认取 `exportFilename` 或 `[entry]-export` | 输出路径 |
| `--format` | `pdf` / `png` / `pptx` / `md`，默认 `pdf` | 输出格式 |
| `--timeout` | number，默认 `30000` | 打印页面渲染超时（毫秒） |
| `--range` | string，如 `1,6-8,10` | 只导指定页 |
| `--dark` | boolean，默认 `false` | 导出暗色版本 |
| `--with-clicks`, `-c` | boolean，默认 `false` | 每个点击动画各出一页；PPTX 模式下默认开启 |
| `--theme`, `-t` | string | 覆盖主题 |
| `--omit-background` | boolean，默认 `false` | 去掉浏览器默认背景（PNG 用，需自行补 CSS 才透明） |
| `--with-toc` | boolean | 生成 PDF 目录（书签） |
| `--wait` | number | 每页导出前额外等待毫秒数 |
| `--wait-until` | `networkidle`（默认）/ `domcontentloaded` / `load` / `none` | 等待页面到达哪个状态 |
| `--executable-path` | path | 指定 Playwright 使用的 Chrome / Edge 可执行文件（解决视频编解码等问题） |

多文件导出：`slidev export slides1.md slides2.md`，每个入口各生成一份产物。

## `slidev format [entry]`

只整理 Markdown 文件的组织结构（分页、frontmatter 位置），**不会**格式化每页内容。

## `slidev theme [subcommand]`

- `slidev theme eject [entry] --dir theme`：把当前主题弹出到本地 `theme/` 目录，便于改样式。
  - `--dir`（string，默认 `theme`）、`--theme`, `-t`。

## `slidev mcp [entry]`

通过 stdio 起一个 MCP（Model Context Protocol）服务，让 AI Agent 读取并编辑这份幻灯片。

## 浏览器导出（v0.50.0-beta.11 起）

开发服务器运行时，打开 `http://localhost:<port>/export`，或在导航栏「More options」里点 Export。可导 PDF，也可把每页截图后打包成 PPTX 或 zip。该 UI 只对现代 Chromium 系浏览器表现良好，出问题就改用 CLI。

## 排错速记

- 内容缺失 / 动画未完成：`--wait 1000`，必要时配合 `--wait-until domcontentloaded`。
- 大 deck 超时：`--timeout 60000`。
- emoji 变方块：环境缺 emoji 字体，装上 Noto Emoji 后 `fc-cache -fv`。
- 视频解码失败：`--executable-path` 指向本机 Chrome / Edge。
