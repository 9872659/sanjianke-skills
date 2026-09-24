# 三剪客 · React 全栈框架 Skill

让 AI Agent 在 Next.js 项目里少犯错的协作规范

---

## 前置条件

- **Node.js 20.9 或更高**。Next.js 16 起已不支持 Node 18，这条不满足会直接构建失败。
- **TypeScript 5.1 或更高**（如果用 TS）。类型助手 `PageProps` / `LayoutProps` 依赖较新的 TS。
- 一个能跑 `next dev` 与 `next build` 的项目环境。
- **推荐**：项目根有 `AGENTS.md`，或在 `next dev` 检测到 Agent 环境时让它自动生成。
- **推荐**：`node_modules/next/dist/docs/` 可读（Next.js 16.2+ 随包发布完整文档）。这一条直接决定 Agent 是照你这个版本的文档写，还是照它的训练记忆写。
- **不需要**：任何 API Key、付费服务、数据库、Docker。本 Skill 只讲规范与结构。

---

## 使用

**第 1 步 · 对齐版本**

```bash
node -p "require('next/package.json').version"
ls node_modules/next/dist/docs/ 2>/dev/null || echo "版本较早，文档不在包内"
```

**第 2 步 · 把约束写进 `AGENTS.md`**

`references/agent-safe-conventions.md` 里有可直接粘贴的约束段模板，覆盖版本纪律、目录约定、边界铁律、禁止写法、提交前检查。这一段的成本最低、收益最大。

**第 3 步 · 按场景查对应的参考文件**

| 你要做的事 | 看哪份 |
|---|---|
| 定目录结构、让 Agent 好定位文件 | `references/project-structure-and-rendering.md` §1、§2 |
| 判断页面该用哪种渲染模式 | `references/project-structure-and-rendering.md` §3（含决策表） |
| 划服务端 / 客户端边界 | `references/agent-safe-conventions.md` §1 |
| 查 Agent 又写了哪个过时 API | `references/agent-safe-conventions.md` §2（速查表） |
| 构建报错、CI 挂了 | `references/build-deploy-troubleshooting.md` §2 |
| 自托管 / Docker / 多实例部署 | `references/build-deploy-troubleshooting.md` §3、§4 |
| 升级 Next.js 大版本 | `references/build-deploy-troubleshooting.md` §6 |

**第 4 步 · 收尾验证**

```bash
next build       # 构建期的预渲染校验是主要安全网
npm run lint     # 16 起构建不再自动跑 lint，必须单独跑
next dev         # 真实打开页面，看终端里的浏览器日志
```

---

## 依赖

- **必需**：Node.js ≥ 20.9、npm / pnpm / yarn / bun 任一。
- **必需**：Next.js 16.x（正文以此为准；老版本用法本文有标注，但请以项目内随包文档为最终依据）。
- **可选**：`server-only` / `client-only` 包。Next.js 内部已处理这两个导入并提供类型声明，装上只是为了满足 lint 的依赖检查。
- **可选**：`agent-browser` 之类能给 Agent 提供 DOM / 控制台结构化视图的 CLI。不带也能用——Next.js 默认会把浏览器错误转发到终端。
- **本 Skill 自身不需要任何运行时依赖。** 它是纯 Markdown 规范，不包含可执行代码。

---

## 安全

- 不内嵌任何密钥，不要求提供任何账号。
- **只读环境变量的名字，不读值**。不会把 `.env.local` 的内容写进任何文件或命令输出。
- **不覆盖已有文件**：目标路径存在时先给你看差异。
- **不擅自改 `package.json` 的依赖版本**，不装全局依赖，不注册后台常驻进程。
- 只跑一次性的短命令（`next dev` / `next build` / `next typegen` / `lint`），用于验证改动。
- 安装新依赖、执行 codemod、跑大版本升级这类有副作用的操作，都需要你先确认。
- 参考文件里提到的第三方工具（MCP、各类平台适配器）都是可选项，本 Skill 不替你安装。

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：Next.js（MIT）

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
