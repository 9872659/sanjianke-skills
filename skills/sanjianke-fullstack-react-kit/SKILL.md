---
name: sanjianke-fullstack-react-kit
slug: sanjianke-fullstack-react-kit
displayName: 三剪客 · React 全栈框架
description: "让 AI Agent 在 Next.js 项目里少犯错的协作规范。 遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "面向 Agent 协作的 Next.js 实战规范：项目结构与渲染模式选型、服务端与客户端边界划法、缓存与预渲染取舍、构建部署排错，附 Agent 高频错误清单与自检门禁。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 开发编程
  - React
  - 全栈
---

# 三剪客 · React 全栈框架

让 AI Agent 在 Next.js 项目里少犯错的协作规范

Next.js 是当下最主流的 React 全栈框架，文档全、生态大——但对 Agent 来说，这恰恰是最危险的一类项目：**它的训练数据里有三个版本的写法同时在打架**。Agent 会熟练地写出 `getServerSideProps`、同步 `params`、`middleware.ts`，然后在这个项目里全部编译不过；它会不假思索地给顶层组件加 `'use client'`，把整页数据读取赶到浏览器；它会绕过缓存声明，让每次构建都在 CI 里对着 prerender 报错发呆。

这份 Skill 不教你怎么从零学 Next.js。它解决的是**协作层面的问题**：怎么把项目结构组织到「Agent 一眼看得懂该改哪」，怎么划定服务端与客户端的边界让 Agent 不越界，怎么在三种渲染模式之间做选择并把选择写进代码，以及构建、部署、排错这条链路上 Agent 最容易翻车的地方。

**读完你会拿到**：3 份参考文件，1 张渲染模式决策表，1 份 Agent 高频错误速查表，1 个可以直接贴进项目的 `AGENTS.md` 段落。

---

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 仅在你明确要求时 | 本 Skill 规范本身完全离线。只有在需要确认 Next.js 当前版本号、或核对某条 API 的现行签名时，才会去查 npm registry 与官方站点。不会在后台自动联网 |
| 读取文件 | 是（项目内） | 读取 `package.json`、`next.config.*`、`tsconfig.json`、`app/` 下的路由文件、`node_modules/next/dist/docs/` 里的随包文档（这是判定「不写错版本」的依据），以及你仓库里的 `AGENTS.md` |
| 写入文件 | 是（项目内，需你确认） | 建目录、写路由文件、改组件、补 `next.config.*`。**不覆盖已有文件**：目标存在时先给你看差异；不擅自改 `package.json` 的依赖版本 |
| 凭证 | 否 | 不读取、不写入、不转发任何密钥、Token、Cookie 或数据库连接串。示例一律写占位符。**不要求你提供任何账号** |
| 子进程 / 后台常驻 | 是（单次执行，非后台） | 只跑一次性的短命令：`next dev` / `next build` / `next typegen` / `lint` 这类你本地已有的构建与校验命令，用来验证改动。不常驻、不注册定时任务、不装全局依赖 |

**关于第三方服务**：本 Skill 不内嵌任何密钥，也不要求你接入任何付费服务。Next.js 本身是 MIT 开源的，照着官方文档装即可。参考文件里提到的 `agent-browser`、MCP、各类平台适配器都是可选工具——用不用由你决定，本 Skill 不替你安装。

**关于环境变量**：Next.js 的项目里到处都是 `.env.local`，里面有数据库密码和第三方密钥。本 Skill 只读变量**名**（比如确认你用的是 `DATABASE_URL` 还是 `DB_URL`），不读变量**值**，更不会把值写进任何文件或命令输出里。

---

## 触发场景

- 「我要用 Next.js 起个新项目，但不想让 Agent 写出一堆过时写法，怎么开局？」
- 「Agent 又给我写了 `getServerSideProps` / 同步 `params`，这项目根本跑不起来。」
- 「这个页面到底该 SSR、该静态、还是该边缓存边流式？Agent 每次都随便选一个。」
- 「Agent 往顶层组件上盖了个 `'use client'`，现在整个页面都在浏览器里跑，怎么收拾？」
- 「`next build` 在 CI 里挂了，报 prerender 相关的一堆错，Agent 改了三轮还没修好。」
- 「项目越做越大，Agent 老是改错文件、找不到该改哪，目录结构该怎么重整？」

---

## 快速开始

最小可用路径只有三步，产出一段能贴进项目的约束 + 一个能跑通的骨架，不是一篇长文。

**第 1 步 · 先对齐版本（2 分钟）**

Agent 犯错的第一大来源是**版本错位**。动手前先把当前版本钉死，并让 Agent 读随包文档而不是训练数据：

```bash
# 看一眼装的是哪个版本
node -p "require('next/package.json').version"
```

```bash
# Next.js 16.2 起，完整文档随包发布在这个目录
ls node_modules/next/dist/docs/ 2>/dev/null || echo "版本较早，文档不在包内"
```

只要这个目录存在，就在项目根的 `AGENTS.md` 里把下面这段粘进去（它是给 Agent 的硬约束，别放在注释里）：

```md
## Next.js 版本纪律

- 本项目使用 Next.js 16.x。动手改任何 `.tsx` / `.ts` 前，先在
  `node_modules/next/dist/docs/` 里读对应主题的文档，不要凭记忆写。
- 禁止出现的过时写法：`getServerSideProps`、`getStaticProps`、`getStaticPaths`、
  `middleware.ts`、同步读取 `params` / `searchParams` / `cookies()` / `headers()`、
  `next lint`、`serverRuntimeConfig` / `publicRuntimeConfig`、`experimental.ppr`。
- 路由相关的文件约定（`page` / `layout` / `route` / `loading` / `error`）以
  `node_modules/next/dist/docs/` 为准，不确定就先读再写。
```

> 如果你的 Next.js 早于 16.2，包内没有 `dist/docs/`。这时用 `npx @next/codemod@canary agents-md` 生成一份随版本下载的文档索引，效果接近。

**第 2 步 · 定渲染模式（5 分钟）**

在写任何页面之前，先给它定一个渲染档位。选错了后面全是返工。用这张表拍板：

| 页面长什么样 | 选它 | 代码上落成什么 |
|---|---|---|
| 内容对所有用户相同，改动不频繁 | 预渲染 + 缓存 | 页面里加 `'use cache'` + `cacheLife('hours')` |
| 内容相同但要按需/定时更新 | 带标签的缓存 | 上面的基础上加 `cacheTag('posts')`，改动后 `revalidateTag` |
| 骨架相同、局部因人而异（购物车、用户偏好） | 局部预渲染 + 流式 | 静态部分正常写，读 `cookies()` 的子树包进 `<Suspense>` |
| 每个请求都不同（后台、实时报表） | 请求时渲染 | 先 `await connection()`，或整段包进 `<Suspense>` |
| 纯静态文档站、不需要服务端 | 静态导出 | `next.config.ts` 里 `output: 'export'` |

选型细节、常见误选和取舍，见 `references/project-structure-and-rendering.md`。

**第 3 步 · 跑起来验证**

```bash
next dev            # 开发服务，Turbopack 已是默认
next build          # 生产构建，会在这一步校验所有页面的预渲染是否成立
next typegen        # 生成 PageProps / LayoutProps 等类型助手，异步 params 迁移必备
```

`next build` 不通过就不要往下写新功能。构建期的 prerender 报错是这套框架最重要的安全网，它会把「这页其实没法预渲染」提前暴露出来。

---

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 新项目怎么定目录结构、怎么让 Agent 好定位文件 | `references/project-structure-and-rendering.md`（结构与组织策略） |
| 页面该 SSR 还是静态还是流式，怎么选 | `references/project-structure-and-rendering.md`（渲染模式决策表 + PPR/缓存组件） |
| 服务端与客户端边界怎么划、`'use client'` 加在哪 | `references/agent-safe-conventions.md`（边界铁律） |
| Agent 老写错版本、老用废弃 API | `references/agent-safe-conventions.md`（高频错误速查表） |
| 怎么把约定写进 `AGENTS.md` 让 Agent 自己守规矩 | `references/agent-safe-conventions.md`（约束段模板） |
| 构建报错、prerender 失败、CI 挂掉 | `references/build-deploy-troubleshooting.md`（错误分类与定位表） |
| 要自托管 / Docker / 多实例部署 | `references/build-deploy-troubleshooting.md`（部署形态与多实例坑） |
| 升级 Next.js 大版本 | `references/build-deploy-troubleshooting.md`（升级路径与破坏性变更） |

---

## 能力边界

**覆盖**：

- 判定 Agent 手里这个 Next.js 项目是哪个版本，并给出「读随包文档」的落地做法
- 项目结构的四种组织策略与选型建议，重点是让 Agent 能快速定位「该改哪个文件」
- `page` / `layout` / `route` / `loading` / `error` / 路由组 / 私有目录等文件约定的准确用法
- 渲染模式决策：预渲染、缓存组件、局部预渲染（PPR）、请求时渲染、静态导出，以及各自的代码写法
- 服务端与客户端边界：`'use client'` 的作用域、如何把边界压到最小、如何用 `server-only` 兜底
- 缓存与再验证：`'use cache'` 的数据级与 UI 级用法、`cacheLife` / `cacheTag` / `revalidateTag` / `updateTag` 的取舍
- 构建与部署：Turbopack 默认行为、`next build` 常见报错的分类定位、自托管与多实例的注意事项
- Agent 协作约束：一份可直接使用的 `AGENTS.md` 约束段模板，以及高频错误速查表

**不覆盖**：

- **不教 React 本身。** 组件、Hooks、状态管理怎么写，是 React 的活。这份 Skill 只在「React 遇到服务端/客户端边界」这个交叉点上讲话。
- **不替你选技术栈。** 数据库、ORM、鉴权库、UI 组件库、样式方案全部不由本 Skill 决定。选了以后怎么在 Next.js 里接，可以参考它给的边界规则。
- **不写业务代码。** 它给的是结构与约定，具体页面做什么、接口返回什么，得你说清楚。
- **不保证兼容 15 及更早版本的全部写法。** 正文以 16.x 为基准并对历史写法做了标注；如果你的项目锁在老版本，请以项目内随包文档或对应版本的升级指南为准。
- **不替你决定部署平台。** Vercel、自托管 Node、Docker、各种适配器各有取舍；本 Skill 只讲各形态下必须注意什么，不推荐你选哪个。
- **不做性能压测。** 它会告诉你「这样写会挡住预渲染」，不会告诉你「这个页面 P95 是多少毫秒」。真实数据得靠你自己的监控和 Lighthouse。
- **不含自动化校验脚本。** 约定靠人写、靠 `next build` 兜底，本 Skill 不附带 lint 插件（避免把「格式合规」当成「结构合理」）。

---

## 依赖条件

- **必需**：Node.js **20.9 或更高**。Next.js 16 起 Node 18 已不再支持，这条不满足会直接构建失败。
- **必需**：TypeScript **5.1 或更高**（如果用 TS）。`PageProps` / `LayoutProps` 这类类型助手依赖较新的 TS。
- **必需**：一个能跑 `next dev` / `next build` 的本地环境。写前端不跑起来看，等于没写。
- **推荐**：项目根有 `AGENTS.md`，或在 `next dev` 检测到 Agent 环境时让它自动生成——这是 Agent 不走神的最低成本手段。
- **推荐**：`node_modules/next/dist/docs/` 可读（Next.js 16.2+ 自带）。这一条直接决定 Agent 是照着你这个版本的文档写，还是照着它的记忆写。
- **推荐**：一个能读终端输出的浏览器视图（比如把控制台日志转发到终端）。Next.js 默认会把浏览器错误转发到终端，Agent 因此能在没有浏览器的情况下看到前端报错。
- **不需要**：任何 API Key、付费服务、数据库。本 Skill 只讲规范与结构。

---

## 已知限制

1. **版本漂移很快，正文会过时。** Next.js 的次版本迭代很密，本 Skill 的正文以 16.x 为基准写定。字段名、默认值、新增 API 都可能在新版本变化——所以整个流程的第一步永远是「确认真实版本并读随包文档」，而不是背下正文里的名字。
2. **`'use cache'` 与缓存组件需要你主动开启。** 数据级/UI 级缓存和局部预渲染依赖 `cacheComponents: true`。这个开关不是纯重命名式的开关，打开后会把原本能糊过去的「未缓存数据读取」全部变成构建错误。存量项目迁移前先读迁移指南，别一次性全量打开。
3. **三种渲染模式不是互斥的选项。** 同一页面里静态头部 + 缓存列表 + 流式个性化区块可以共存。正文给的决策表按「页面主体」判断，具体页面往往需要组合，组合方式需要人判断。
4. **构建期能预渲染 ≠ 运行时能渲染得动。** 用爬虫访问时，Next.js 会跳过静态外壳改走完整动态渲染，构建期成立的假设在这个路径上可能不成立（典型是只在构建环境存在的数据源）。这类问题构建不报错，得靠真实抓取验证。
5. **多实例部署的坑不由框架自动兜住。** 缓存标签失效、Server Function 的加密密钥、版本偏斜保护，这三件事在多实例下都需要显式配置，配错了表现为「偶发旧数据」「偶发功能报错」，很难复现。
6. **Agent 不遵守约定时本 Skill 拦不住。** 这里写的是提示词层的规范。真正能拦住错误提交的是类型检查、构建、CI 和你自己加的测试；要靠硬约束的地方请落到这些上面。
7. **它不评价你的架构决策。** 「该不该用 Server Component」「该不该上 Cache Components」这类问题，本 Skill 给判据和代价，不给结论。

---

## 自检清单

改动落进主干前逐条打勾。任何一条没打上，先别合并。

- [ ] **版本对齐**：确认过 `next` 的实际版本，且 Agent 动手前读过 `node_modules/next/dist/docs/` 里对应主题
- [ ] **无过时 API**：全仓搜过一轮，没有 `getServerSideProps` / `getStaticProps` / `middleware.ts` / `next lint` / `serverRuntimeConfig` 这些已废弃的东西
- [ ] **异步请求 API**：`params` / `searchParams` / `cookies()` / `headers()` / `draftMode()` 全部 `await` 过，没有同步访问残留
- [ ] **渲染意图明确**：每个页面都能一句话说清它属于哪个渲染档位，且代码里有对应声明（缓存指令或 `<Suspense>`）
- [ ] **边界最小**：`'use client'` 只加在真正需要交互或浏览器 API 的文件上，没有出现在 `layout.tsx` 或数据读取模块里
- [ ] **数据不上桥**：传给客户端组件的 props 都是可序列化的，没有函数、类实例、数据库连接对象
- [ ] **无密钥泄漏**：客户端代码里没用到非 `NEXT_PUBLIC_` 前缀的环境变量；服务端专用模块加了 `server-only`
- [ ] **构建绿**：`next build` 通过，没有靠 `instant = false` 或删声明绕过 prerender 校验
- [ ] **路由约定正确**：并行路由有 `default.tsx`；私有目录用 `_` 前缀；路由组用 `()` 且没意外改变 URL
- [ ] **检查命令齐全**：`package.json` 里有独立的 `lint` 脚本（Next.js 16 起 `next build` 不再跑 lint，别以为构建绿了就等于 lint 过了）
- [ ] **运行时不只构建时验证过**：至少在 `next dev` 里真实打开过页面，看过终端里的浏览器日志与 dev 提示

---

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/project-structure-and-rendering.md` | 目录与文件约定、四种组织策略、渲染模式决策表、缓存组件与局部预渲染的写法与取舍 |
| `references/agent-safe-conventions.md` | 服务端/客户端边界铁律、Agent 高频错误速查表、`AGENTS.md` 约束段模板、可序列化与数据安全 |
| `references/build-deploy-troubleshooting.md` | 构建报错分类定位、Turbopack 与 Webpack 取舍、部署形态、多实例坑、大版本升级路径 |

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
