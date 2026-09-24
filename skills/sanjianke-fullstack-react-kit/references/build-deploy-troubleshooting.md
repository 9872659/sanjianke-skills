# 构建部署与排错

构建期错误的分类定位、Turbopack 取舍、部署形态与多实例坑、大版本升级路径。上游项目：Next.js（MIT）。本文为独立编写，不是官方文档的翻译或摘抄。

---

## 一、命令与它们的真实行为

| 命令 | 做什么 | 容易误解的地方 |
|---|---|---|
| `next dev` | 开发服务器，**Turbopack 已是默认打包器** | 输出目录是 `.next/dev`，与构建产物分离；第二个实例会被锁文件拦住 |
| `next build` | 生产构建，**并在这一步校验每个页面的预渲染是否成立** | 16 起**不再跑 lint**；也不再输出体积指标 |
| `next start` | 启动生产服务器 | 需要先 `next build`；支持 `--inspect` 挂 Node 调试器 |
| `next typegen` | 生成 `PageProps` / `LayoutProps` / `RouteContext` 类型助手 | 异步 `params` 迁移时必跑，否则类型对不上 |
| `next upgrade` | 升级到最新版 | 16.1 以前没有这个命令，得换 codemod |
| `next build --webpack` | 用 Webpack 构建，绕过 Turbopack | 项目里有自定义 `webpack` 配置时，默认构建会**直接失败**，需要显式选一边 |
| `next build --debug-prerender` | 打开服务端 source map 并跳过首个失败继续构建 | 生产构建堆栈被压缩、定位不到源码时用 |

`package.json` 该有的样子：

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint",
    "lint:fix": "eslint --fix",
    "typecheck": "tsc --noEmit"
  }
}
```

> **从老项目迁移来的注意**：脚本里的 `--turbopack` / `--turbo` 参数已经不需要，删掉更干净。而 `lint` 脚本必须**单独存在**——构建不再替你跑它。

---

## 二、构建报错分类定位

### 2.1 先看错误属于哪一类

| 症状关键词 | 类别 | 往哪查 |
|---|---|---|
| `encountered uncached data during prerendering` | 预渲染受阻 | §2.2 |
| `blocking-prerender-random` / `current-time` / `crypto` | 不可预测值 | §2.2 第 3 条 |
| `You're importing a component that needs useState` | 边界错位 | §2.3 |
| `Module not found: Can't resolve 'fs'` | 服务端代码渗进客户端 | §2.3 |
| `Failed to find Server Action` | 多实例加密密钥不一致 | §4.2 |
| `Webpack is configured while Turbopack is not` | 打包器冲突 | §3.1 |
| `Another next dev server is already running` | 实例冲突 | §3.2 |
| `default.js is required for parallel routes` | 并行路由缺兜底 | §2.4 |
| 首屏内容与客户端不一致、闪烁 | 水合不匹配 | §5.1 |

### 2.2 预渲染受阻（最常见的一类）

终端会打出**成段的结构化提示**，包含三条修法。这是设计好的：读完整段，不要只看最后一行。

```text
Route "/products/[slug]": Next.js encountered uncached data during prerendering.

Ways to fix this:
  - [stream] Provide a placeholder with <Suspense fallback={...}> around the data access
  - [cache]  Cache the data access with "use cache" (does not apply to connection())
  - [block]  Set `export const instant = false` to allow a blocking route
```

**三条修法的取舍**：

| 修法 | 代价 | 什么时候选 |
|---|---|---|
| `[stream]` 包 `<Suspense>` | 该块内容延迟到达，需要设计骨架 UI | 内容必须每次请求都新（读取用户数据、实时值） |
| `[cache]` 加 `'use cache'` | 内容会过期，需要设计失效策略 | 内容对所有用户相同，允许按寿命陈旧 |
| `[block]` 放弃预渲染 | 该路由失去静态外壳，首屏变慢 | 确实无法预渲染，且已确认性能可接受 |

**给 Agent 的纪律**：选 `[block]` 之前必须说清为什么前两条不适用。看到「为了让报错消失而选 block」，一律打回。

**不可预测值**的处理（`Math.random()` / `Date.now()` / `crypto.randomUUID()`）：要么在操作前 `await connection()` 把它推到请求时，要么把整个组件 `'use cache'` 起来让大家共享一个值。

**日志里看到完整堆栈但生产构建定位不到源码**：

```bash
next build --debug-prerender
```

它会打开服务端 source map 并继续跑完剩余路由，一次拿到全部失败点，而不是修一个跑一次。

### 2.3 服务端 / 客户端边界错位

**症状一**：`You're importing a component that needs useState. It only works in a Client Component`

修法：给**真正需要状态的那个叶子组件**加 `'use client'`，不要加在父级页面上。三方库没带 directive 时，用本地文件重导出并加 directive。

**症状二**：`Module not found: Can't resolve 'fs'`（或 `node:crypto`、`path` 等）

含义：客户端的打包图里出现了 Node 原生模块。**不要用 alias 把错误静音**——那是掩盖问题。按顺序试：

1. 检查这个模块是被哪个客户端组件导入的，把导入链断开，改由服务端组件取数后传值下去。
2. 确认该模块顶部有 `import 'server-only'`，让构建器早点报出真正的越界点。
3. 确实无法重构时才考虑 `turbopack.resolveAlias`（官方也不推荐）。

**症状三**：`Event handlers cannot be passed to Client Component props` 或对象序列化失败

含义：传了函数 / 类实例 / 不可序列化的值。修法：在服务端把数据压成普通对象，函数留在服务端用 Server Function 暴露。

### 2.4 路由约定相关的构建失败

| 报错 | 原因 | 修法 |
|---|---|---|
| 并行路由缺 `default.js` | 16 起所有 `@slot` 必须有兜底页 | 每个槽目录建 `default.tsx`，`return null` 或调 `notFound()` |
| 路由冲突（同一路径两个 `page`） | 路由组之间的路径撞车 | 检查路由组的括号，两个组解析到同一 URL 是会冲突的 |
| `pageExtensions` 相关的文件没被识别 | 你改了 `pageExtensions` | 相应文件要跟着改名（如 `page.page.ts`） |

### 2.5 缓存相关的运行期问题

| 症状 | 原因 | 修法 |
|---|---|---|
| 用户提交后看不到自己的改动 | 用了 `revalidateTag`（先给旧值） | 表单/设置类用 `updateTag`（读己所写） |
| 缓存标签失效只在部分实例生效 | 多实例下没有同步标签状态 | 在自定义 cache handler 里实现 `refreshTags()`（见 §4.3） |
| 新部署后旧的 `use cache` 条目还在 | 缓存键包含构建 ID，新部署应当全失效 | 若确实看到旧数据，检查是否有外部 CDN 缓存了 HTML |
| 缓存命中率很低 | 默认是每实例内存缓存，无服务器环境下寿命极短 | 高命中率场景改用 `'use cache: remote'` 配自定义 cache handler |

---

## 三、Turbopack 与实例冲突

### 3.1 Turbopack 是默认，Webpack 要显式选

16 起 `next dev` 与 `next build` 都用 Turbopack。如果项目里有自定义 `webpack` 配置（可能是你自己写的，也可能是某个插件注入的），**默认构建会直接失败**而不是静默忽略。三条出路：

| 做法 | 命令 | 适用 |
|---|---|---|
| 全面转 Turbopack | 无参数 | 首选。把 webpack 配置迁移成 `turbopack` 顶层配置 |
| 只构建用 Webpack | `next build --webpack` | 迁移期间过渡 |
| 忽略 webpack 配置硬用 Turbopack | `next build --turbopack` | 确认那份配置已无用 |

Turbopack 的配置项已从 `experimental.turbopack` 提升为顶层的 `turbopack`：

```ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  turbopack: {
    // 以前的 experimental.turbopack 内容搬到这里
  },
}

export default nextConfig
```

**两个具体差异**（老项目迁移时容易卡住）：

- Sass 的 `~` 前缀不再支持。`@import '~bootstrap/...'` 要写成 `@import 'bootstrap/...'`。
- 客户端代码引用 Node 原生模块不再靠 `resolve.fallback` 静音，需要真正重构导入链。

### 3.2 dev / build 的实例与目录

- `next dev` 产物在 `.next/dev`，`next build` 产物在 `.next`，两者分离，**可以同时跑**。
- 启动时会把 PID、端口、URL 写进 `.next/dev/lock`。第二个实例读到锁文件后会**打印已有实例的 PID 和地址**，照它提示的做——连着现有实例，或者 `kill <PID>`，不要盲目重复启动。
- 这个锁同样防止两个 `next build` 同时跑（并发构建会破坏产物）。

> **Agent 场景下的价值**：Agent 经常不知道已经有个 dev server 在跑，反复启动然后拿到「端口被占用」。锁文件给出的结构化输出正好解决这个——它会直接告诉 Agent 该连哪里或该杀谁。

### 3.3 缓存与并发

- Turbopack 默认把编译产物落盘复用，`next dev` 与 `next build` 都开。改动配置或遇到诡异的陈旧报错时，清 `.next` 是有效的第一步。
- 构建期会生成一个构建 ID 标识这次部署。多容器部署**同一份构建**时，让它保持一致，否则缓存与静态资源会对不上。

---

## 四、部署形态

### 4.1 三种形态的能力边界

| 形态 | 支持能力 | 不支持 | 典型场景 |
|---|---|---|---|
| Node.js 服务器（`next start`） | 全部 | — | 自有服务器、容器编排 |
| Docker 容器 | 全部 | — | K8s、云容器服务 |
| 静态导出（`output: 'export'`） | 仅纯静态能力 | Proxy、图片按需优化、ISR、Server Function、按请求渲染 | 文档站、纯展示站 |

**静态导出的取舍要提前说清**。`output: 'export'` 一旦开启，上面那一列能力全部消失，而且是**部署时才发现**。带后台的站点不要走这条路。

```ts
// next.config.ts —— 只有确认不需要服务端能力时才加
const nextConfig = {
  output: 'export',
}
```

### 4.2 Docker 与多实例

**最小化镜像**用 standalone 输出：

```ts
// next.config.ts
const nextConfig = {
  output: 'standalone',
}
```

`next build` 之后，运行所需的文件与依赖会被收敛到 `.next/standalone`，镜像里不需要装完整 `node_modules`。

**多实例必配两件事**，否则表现为「偶发报错」，极难复现：

**① Server Function 的加密密钥**

Server Function 的闭包变量在发给客户端前会被加密，密钥**默认每次构建随机生成**。多实例部署时若各实例密钥不同，A 实例加密的请求 B 实例解不开，用户看到 `Failed to find Server Action`。

```bash
# 构建时固定，所有实例共用。必须是 base64 编码的 AES 合法长度（16/24/32 字节）
NEXT_SERVER_ACTIONS_ENCRYPTION_KEY=<生成好的密钥> next build
```

**② 部署标识（版本偏斜保护）**

滚动发布期间，老客户端可能请求到新实例。不配 `deploymentId` 的症状是：静态资源 404、Server Function ID 不匹配、预取的导航数据不兼容。配了之后，检测到版本不一致会退化为整页刷新。

```js
// next.config.js
module.exports = {
  deploymentId: process.env.DEPLOYMENT_VERSION,
}
```

代价是整页刷新会丢失组件内存里的状态（`useState` 之类）。URL 状态和 localStorage 会保留。

### 4.3 共享缓存与标签协调

默认缓存是**每实例内存 + 本地磁盘**，多实例之间互不可见。三个层次的修法：

| 需求 | 做法 |
|---|---|
| 缓存跨实例共享 | 配自定义 cache handler（`cacheHandlers`），存到 Redis / S3 之类 |
| 单实例内也彻底关掉内存缓存 | `cacheMaxMemorySize: 0` |
| 标签失效要跨实例可见 | 在 cache handler 里实现 `refreshTags()`，每次请求前从共享存储同步标签状态 |

**不配 `refreshTags()` 的症状**：在实例 A 上调了 `revalidateTag`，实例 B 还在继续吐旧内容，直到它自己发现失效。用户看到的就是「刷新几次有时新有时旧」。

### 4.4 自托管的三个细节

**① 一定要在 Next.js 前面放反向代理**

Nginx / Caddy 之类扛掉畸形请求、慢连接、超大 body、限流，让 Next.js 专心渲染。

**② 流式渲染要贯穿整条链路**

Next.js 的流式响应会被默认开启缓冲的 Nginx 掐死，变成「等全部渲染完再一起发」，流式和 PPR 的首字节优势直接归零。

```js
// next.config.js —— 让 Nginx 不要缓冲
module.exports = {
  async headers() {
    return [
      {
        source: '/:path*{/}?',
        headers: [{ key: 'X-Accel-Buffering', value: 'no' }],
      },
    ]
  },
}
```

不止 Nginx：负载均衡（部分云 LB 默认缓冲）、中间的反向代理都要支持 chunked 传输或 HTTP/2 流式。

**③ 优雅停机**

自托管时 `after()` 回调是在响应之后跑的。停机要发 `SIGINT` / `SIGTERM` 并等待，给 10~30 秒的排水时间，否则后台任务会被腰斩。

### 4.5 环境变量的部署纪律

| 变量类型 | 何时生效 | 部署含义 |
|---|---|---|
| `NEXT_PUBLIC_*` | `next build` 时内联进产物 | **改值必须重新构建**，不能靠改环境变量生效 |
| 普通 `process.env.*` | 请求时读取（配合 `connection()`） | 同一个镜像可以跨环境提升，不用重构 |

想要「一个镜像跑多套环境」，就让配置读运行时变量而不是 `NEXT_PUBLIC_`。

---

## 五、常用排错手法

### 5.1 水合不匹配（Hydration mismatch）

**症状**：控制台报 hydration 错误，页面内容闪一下变了，或者交互失效。

**原因**：服务端渲染出的 HTML 与客户端第一次渲染的结果不一致。常见来源：

- 渲染里用了 `Date.now()` / `Math.random()` / `new Date().toLocaleString()`（时区、语言不一致）
- 直接读 `localStorage` / `window` 的值参与首屏渲染
- 浏览器扩展往 DOM 里塞了东西
- 服务端和客户端的条件判断依赖了不同来源

**定位**：16.2 起错误浮层会把两侧的差异标出来（`+ Client` / `- Server`），能直接看出是哪一块不一致。

**修法模板**：

```tsx
// 差：服务端与客户端算出不同结果
export function Timestamp() {
  return <span>{new Date().toLocaleString()}</span>
}
```

```tsx
// 好：把时间在服务端算好，以字符串传下去
export function Timestamp({ iso }: { iso: string }) {
  return <span>{iso}</span>
}
```

```tsx
// 或者：确实只能在客户端才知道的值，挂载后再显示
'use client'
import { useEffect, useState } from 'react'

export function LocalTime() {
  const [text, setText] = useState<string | null>(null)
  useEffect(() => setText(new Date().toLocaleString()), [])
  return <span>{text ?? '—'}</span>
}
```

### 5.2 页面在浏览器里正常，爬虫抓取报错

**原因**：爬虫路径不走静态外壳，而是完整动态渲染整页。构建期成立、请求期不成立的假设会在这里暴露（典型是「只在构建环境存在的数据源」）。

**验证**：上线前用真实爬虫 UA 抓一次关键页面，别只看浏览器。

```bash
curl -sS -A "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" \
  https://your-site.example.com/ | head -50
```

### 5.3 「改了没生效」的排查顺序

按这个顺序走，能覆盖绝大多数情况：

1. **是不是两个 dev server？** 看终端有没有锁文件提示，确认你连的是哪个端口。
2. **是不是缓存？** 加个 `cacheTag` 然后手动失效一次，或者临时把 `cacheLife` 调短验证。
3. **是不是构建产物陈旧？** 清掉 `.next` 重跑。
4. **是不是环境变量？** `NEXT_PUBLIC_` 的值是构建时内联的，改了要重建。
5. **是不是 CDN？** 动态页面会带 `private` 缓存头，静态页面带 `public`。中间有没有一层缓存在兜。

### 5.4 图片相关的报错（16 起有变化）

| 现象 | 原因 | 修法 |
|---|---|---|
| 本地图片带查询串报错 | 16 起需要显式声明模式 | `images.localPatterns` 里加 `pathname` + `search` |
| 远程图升级后不显示 | `images.domains` 已废弃，且默认阻止内网地址 | 换 `images.remotePatterns`；内网场景才考虑 `dangerouslyAllowLocalIP` |
| 图片质量参数没反应 | 默认只允许 75 | `images.qualities` 里显式列出要用的档位 |
| 图片更新延迟变大 | `minimumCacheTTL` 默认从 60 秒提到 4 小时 | 需要更快刷新就把这个值调回去 |
| 重定向图片来源失败 | 默认最多跟 3 跳 | 需要更多就调 `images.maximumRedirects` |

> **Agent 提醒**：`images.domains` 和 `next/legacy/image` 都是旧写法，看到就应该替换，而不是照着错误信息补配置。

---

## 六、升级到 16 的路径

### 6.1 顺序不要打乱

1. **先让 Agent 有版本匹配的文档。** 没有这一步，Agent 会按记忆改代码，越改越错。
   ```bash
   npx @next/codemod@canary agents-md
   ```
   升级完成后复查 `AGENTS.md` 指向的是 `node_modules/next/dist/docs/`（16.2+ 的随包文档），如果以前下载到了 `.next-docs/`，改完把它删掉。

2. **跑升级 codemod。**
   ```bash
   npx @next/codemod@canary upgrade latest
   ```
   它能处理的：`next.config` 的 `turbopack` 配置迁移、`next lint` 到 ESLint CLI、`middleware` 到 `proxy`、去掉已稳定 API 的 `unstable_` 前缀、移除路由级 `experimental_ppr`。

3. **补跑异步请求 API 的 codemod**（老项目十有八九需要）：
   ```bash
   npx @next/codemod@canary next-async-request-api .
   ```

4. **逐个处理剩下的破坏性变更**（见 §6.2）。

5. **手动装包**（如果没用 codemod）：
   ```bash
   npm i next@latest react@latest react-dom@latest
   npm i -D @types/react@latest @types/react-dom@latest
   ```

### 6.2 检查清单（按会炸的顺序排）

- [ ] **Node 版本** ≥ 20.9（Node 18 已不支持）；TypeScript ≥ 5.1
- [ ] **异步请求 API**：`params` / `searchParams` / `cookies()` / `headers()` / `draftMode()` 全部 `await`。同步访问已**彻底移除**，不是警告
- [ ] **`middleware.ts` → `proxy.ts`**：文件改名 + 函数改名；注意 `proxy` 运行时固定为 Node.js，不可配 edge。仍要用 edge 的话留在 `middleware`
- [ ] **并行路由补 `default.tsx`**：否则构建直接失败
- [ ] **`next lint` 已移除**：把 lint 拆成独立脚本；`next build` 不再跑 lint
- [ ] **ESLint Flat Config**：插件已默认新格式，老 `.eslintrc` 要迁移
- [ ] **图片配置**：`domains` → `remotePatterns`；`next/legacy/image` → `next/image`；确认 `minimumCacheTTL`、`qualities`、`imageSizes` 的新默认值是否符合预期
- [ ] **运行时配置已移除**：`serverRuntimeConfig` / `publicRuntimeConfig` 换成环境变量
- [ ] **PPR 开关换掉**：`experimental.ppr` 与路由级 `experimental_ppr` 都已移除，改用 `cacheComponents`
- [ ] **`dynamicIO` / `experimental.useCache` 移除**：如果之前在用，迁到 `cacheComponents`
- [ ] **`revalidateTag` 补第二参数**，或改用 `updateTag`
- [ ] **`unstable_cacheLife` / `unstable_cacheTag` 去掉前缀**（已稳定）
- [ ] **AMP 相关全部移除**（`next/amp`、`amp` 配置）
- [ ] **`unstable_rootParams` 换成 `next/root-params`**
- [ ] **自定义 webpack 配置**：决定迁移到 `turbopack` 还是保留 `--webpack`
- [ ] **Sass 的 `~` 前缀去掉**
- [ ] **滚动行为变化**：全局 `scroll-behavior: smooth` 不再被自动覆盖；要旧行为就在 `<html>` 上加 `data-scroll-behavior="smooth"`
- [ ] **`opengraph-image` / `icon` / `sitemap` 的生成函数**：`params`（和 `generateImageMetadata` 产生的 `id`）现在是 Promise
- [ ] **构建输出指标变化**：`size` 与 `First Load JS` 不再打印，改用 Lighthouse 之类工具评估

### 6.3 升级后必须做的验证

```bash
next typegen      # 生成类型助手，TS 项目必跑
next build        # 预渲染校验全量过一遍
npm run lint      # 单独跑，构建不再代劳
next dev          # 真实打开关键页面，看终端里的浏览器日志与 dev 提示
```

**升级期间的建议**：把升级本身和新功能开发分成两个分支。Agent 在升级过程中最容易顺手「优化」无关代码，那会让破坏性变更的定位变得非常痛苦。
