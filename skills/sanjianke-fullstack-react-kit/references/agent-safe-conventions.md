# 让 Agent 少犯错的写法约定

服务端与客户端边界、高频错误、可粘贴的约束段。上游项目：Next.js（MIT）。本文为独立编写，不是官方文档的翻译或摘抄。

---

## 一、边界铁律

### 1.1 默认在服务端

`app/` 下的 `layout.tsx` 和 `page.tsx` **默认是服务端组件**。它们能直接 `await` 数据库、能读密钥、能少发 JavaScript 到浏览器。

Agent 最常见的退化动作是：**因为想用一个 `useState`，就在文件顶部加了 `'use client'`**。这一加，整个文件及其导入图都被拉进客户端包——包括你的数据访问层。

```text
'use client' 一旦出现：
  该文件 + 它 import 的一切 + 它直接渲染的组件
  → 全部进入客户端 bundle
```

### 1.2 `'use client'` 的作用域（精确版）

| 位置 | 是否进入客户端包 | 说明 |
|---|---|---|
| 标了 `'use client'` 的文件 | 是 | 边界起点 |
| 它 `import` 的模块 | 是 | 会被打进客户端包 |
| 它直接渲染的组件 | 是 | 同上 |
| 服务端组件作为 `children` / prop 传进来 | **否** | 这些在服务端渲染完，以结果形式传过去 |

最后一行是**最有用的一条**：客户端组件可以包住服务端内容，用 `children` 做插槽，而不会把服务端内容拖进客户端。

```tsx
// app/ui/modal.tsx —— 需要客户端状态，所以标了 use client
'use client'

export default function Modal({ children }: { children: React.ReactNode }) {
  return <div className="modal">{children}</div>
}
```

```tsx
// app/page.tsx —— 服务端组件，Modal 只是外壳
import Modal from './ui/modal'
import Cart from './ui/cart' // Cart 是服务端组件，自己取数

export default function Page() {
  return (
    <Modal>
      {/* Cart 在服务端渲染，不因为被 Modal 包住而变成客户端 */}
      <Cart />
    </Modal>
  )
}
```

### 1.3 把边界压到最小的四种手法

| 手法 | 做法 | 收益 |
|---|---|---|
| 下沉交互点 | 只给按钮 / 输入框这类真正需要 hander 的叶子组件加 `'use client'` | 客户端包最小 |
| `children` 插槽 | 客户端外壳 + 服务端内容 | 状态与数据各归其位 |
| 抽 provider | Context Provider 是客户端组件，但只包 `{children}` | 静态部分仍可被优化 |
| 三方组件包一层 | 依赖 `window` 的第三方组件，用本地文件重导出并加 `'use client'` | 服务端组件也能安全使用它 |

**三方组件的包法**（Agent 常漏的一步）：

```tsx
// app/carousel.tsx
'use client'

export { Carousel as default } from 'acme-carousel'
```

这样服务端组件里就能直接 `import Carousel from './carousel'` 使用，不需要把整页变成客户端。

### 1.4 需要客户端能力的判断表

| 你要用 | 环境 | 结论 |
|---|---|---|
| `useState` / `useReducer` | 客户端 | 该文件（或叶子组件）标 `'use client'` |
| `onClick` / `onChange` 等事件处理 | 客户端 | 同上 |
| `useEffect` / `useLayoutEffect` | 客户端 | 同上 |
| `window` / `document` / `localStorage` | 客户端 | 同上（或动态导入） |
| 自定义 Hook | 客户端 | 同上 |
| 读数据库 / 文件系统 | **服务端** | 不要加 `'use client'` |
| 读密钥、签名、发内部请求 | **服务端** | 同上 |
| 只做数据拼装与渲染 | **服务端** | 什么都不加 |

---

## 二、Agent 高频错误速查表

按「Agent 实际写错的频率」排序。每一条都给出识别信号与修法。

| # | 错误写法 | 为什么错 | 正确写法 |
|---|---|---|---|
| 1 | `export async function getServerSideProps()` | Pages Router 的页面级取数，App Router 没有这个概念 | 直接在页面组件里 `await`，或抽到 `'use cache'` 数据函数 |
| 2 | `getStaticProps` / `getStaticPaths` | 同上 | `generateStaticParams` + 直接 `await` |
| 3 | `export default function Page({ params }) { const { id } = params }` | 16 起 `params` 是 Promise，同步访问已彻底移除 | `const { id } = await params`，类型用 `PageProps<'/blog/[slug]'>` |
| 4 | `const c = cookies(); c.get('x')` | `cookies()` / `headers()` / `draftMode()` 都是异步的 | `const c = await cookies()` |
| 5 | 项目根建 `middleware.ts` | 16 起已更名为 `proxy.ts`，函数名也改成 `proxy`；且 `proxy` 的运行时固定为 Node.js，不可配 edge | 重命名为 `proxy.ts`，导出 `proxy` 函数 |
| 6 | 顶层 `layout.tsx` 第一行加 `'use client'` | 根布局变客户端组件，`metadata` 导出失效，全站包体暴涨 | 保持服务端；把交互部分抽成子组件再标 |
| 7 | 页面里 `await fetch(...)` 后没做任何缓存 / Suspense 声明 | 打开 `cacheComponents` 后构建直接报错 | 加 `'use cache'`，或把该子树包进 `<Suspense>` |
| 8 | 把函数、类实例、Date 对象塞给客户端组件当 prop | 非可序列化值无法跨 RSC 边界传递 | 只传字符串 / 数字 / 普通对象 / 数组；日期传 ISO 字符串 |
| 9 | `revalidateTag('posts')` 单参数 | 新签名要求第二个参数（缓存寿命 profile） | `revalidateTag('posts', 'max')`，或改用 `updateTag('posts')` |
| 10 | `experimental: { ppr: true }` | 16 起已移除，PPR 由 `cacheComponents` 提供 | 顶层 `cacheComponents: true` |
| 11 | `serverRuntimeConfig` / `publicRuntimeConfig` | 已移除 | 服务端读 `process.env.X`；客户端用 `NEXT_PUBLIC_` 前缀 |
| 12 | `next lint` / 依赖 `next build` 跑 lint | `next lint` 已移除，`next build` 不再自动 lint | `package.json` 里独立配 `"lint": "eslint"` 并单独跑 |
| 13 | `.eslintrc.json` 老格式 | 插件已默认 Flat Config | 迁移到 `eslint.config.mjs` |
| 14 | `import Image from 'next/legacy/image'` | 已废弃 | `next/image` |
| 15 | `images: { domains: [...] }` | 已废弃，且有安全顾虑 | `images: { remotePatterns: [...] }` |
| 16 | 并行路由槽没写 `default.tsx` | 16 起构建直接失败 | 每个 `@slot` 目录补 `default.tsx`，`return null` 或调 `notFound()` |
| 17 | `'use cache'` 写在文件顶行 | 该文件所有导出函数都被缓存，包括不该缓存的 | 写在函数体内，只缓存该函数 |
| 18 | 环境变量在客户端组件里当 `process.env.SECRET` 用 | 非 `NEXT_PUBLIC_` 的变量在客户端会被替换成空字符串，功能静默失效 | 挪到服务端组件；或确认要公开再改名 |
| 19 | `app/` 下建 `components/xxx.tsx` 且里面写 `page.tsx` | 该目录变成真实路由段，意外多出可访问 URL | 用 `_components/` 私有目录 |
| 20 | 用 `useEffect` + `fetch` 拉首屏数据 | 首屏变成「先空白再请求」，丢掉服务端渲染的全部好处 | 在服务端组件里 `await`；只有用户交互触发的请求才放客户端 |

### 2.1 三条「看到就回滚」的红线

1. **`'use client'` 出现在 `app/**/layout.tsx` 顶部** —— 除非你明确知道代价，否则一定是错的。
2. **`as any` 盖住了 `revalidateTag` 或缓存相关的类型错误** —— 类型错误在告诉你 API 改签名了，盖掉只是把问题推到运行时。
3. **`export const dynamic = 'force-dynamic'` 被当成万能解药** —— 它会让整页放弃预渲染。用在确实无法预渲染的页面上可以，用来「让报错消失」不行。

---

## 三、可序列化与数据安全

### 3.1 跨边界的数据规则

传给客户端组件的 props 必须能被 React 序列化。**能过关的**：字符串、数字、布尔、`null` / `undefined`、数组、普通对象、`Date`（部分场景）、Promise（配合 `use`）。**过不了关的**：函数、类实例、Symbol、Map / Set（取决于实现）、数据库连接、文件句柄。

Agent 常见的翻车方式是「把 ORM 查询结果直接传下去」——ORM 的模型对象往往带方法，序列化时静默丢失或报错。**做法：在服务端把它压成普通对象再传。**

```tsx
// 差：把 ORM 对象整只传下去
return <UserCard user={user} />
```

```tsx
// 好：只取需要的字段，构造一个最小的普通对象
return (
  <UserCard
    user={{ id: user.id, name: user.name, avatarUrl: user.avatarUrl }}
  />
)
```

### 3.2 用 `server-only` 把服务端模块钉死

只在服务端用的模块（数据库、密钥读取、内部接口），在文件顶部加一行：

```ts
import 'server-only'

export async function getSecretData() {
  // 这里用密钥是安全的
}
```

一旦有人（或 Agent）把它导进客户端组件，**构建期直接报错**，而不是等到运行时才发现密钥被打了包。反向的 `client-only` 用于标记依赖 `window` 的模块。

> 这两个包在 Next.js 里由框架内部处理，安装与否不影响报错效果（Next.js 自带类型声明）。项目里装了只是为了满足 lint 的依赖检查。

### 3.3 环境变量的三条规矩

| 规矩 | 原因 |
|---|---|
| 默认只在服务端可用。要让浏览器看见必须加 `NEXT_PUBLIC_` 前缀 | 前缀变量会在 `next build` 时**内联进打包产物**，改了值必须重新构建 |
| 想读运行时的值（而不是构建时固化的），先 `await connection()` 再读 | 否则 Docker 镜像一旦构建就锁死了那批值，无法跨环境提升同一镜像 |
| 服务端专用变量绝不加 `NEXT_PUBLIC_` | 加了就是公开的，改名也救不回来 |

```tsx
// 想要「同一个镜像，多环境不同配置」时的写法
import { connection } from 'next/server'

export default async function Page() {
  await connection()
  const cfg = process.env.RUNTIME_CONFIG // 真正在请求时读取
  return <p>{cfg}</p>
}
```

### 3.4 别在 Proxy 里做唯一的鉴权

`proxy.ts` 在网络边界上跑，适合重定向、改写、加响应头。**它不适合当唯一的鉴权闸门**，原因有三：

- Server Function（`'use server'` 的函数）不是独立路由，它是所在路径上的 POST 请求。**matcher 排除了某个路径，那个路径上的 Server Function 调用也一起被跳过。**
- 重构时把一个 Server Function 挪到别的路径，Proxy 覆盖会静默消失。
- matcher 默认对**所有**请求生效，写不好会连 `_next/static`、`_next/image`、`public/` 里的资源一起拦掉，页面样式直接崩。

**做法**：把鉴权与授权写进**每个** Server Function / 数据访问函数内部，Proxy 只做粗粒度的重定向与限流。

```ts
// proxy.ts —— 只做粗过滤
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function proxy(request: NextRequest) {
  if (!request.cookies.has('session')) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
}

export const config = {
  // 明确排除静态资源与图片优化，否则页面会缺样式
  matcher: ['/dashboard/:path*', '/settings/:path*'],
}
```

```ts
// 真正的授权放在数据层，谁调用都跑得到
// app/lib/auth.ts
import 'server-only'

export async function requireUser() {
  const user = await getSessionUser()
  if (!user) throw new Error('UNAUTHORIZED')
  return user
}
```

> **迁移提示**：`middleware.ts` → `proxy.ts` 有官方 codemod（`npx @next/codemod@canary middleware-to-proxy .`），它同时改函数名。相关配置项也从 `skipMiddlewareUrlNormalize` 改名为 `skipProxyUrlNormalize`。

---

## 四、约束段模板（直接贴进 `AGENTS.md`）

`AGENTS.md` 是让 Agent 自己守规矩的最低成本手段。Next.js 16.3 起，检测到 Agent 环境时 `next dev` 会自动生成它，并写入一段由框架管理的块（用 `<!-- BEGIN:nextjs-agent-rules -->` 标记）。**你自己的约定写在标记外面，升级时不会被覆盖。**

下面是给 React 全栈项目的建议段落，按需删减：

```md
<!-- 以下内容请写在 nextjs-agent-rules 标记块之外 -->

## 本项目的工作方式

### 动手之前
- 改任何 `.tsx` / `.ts` 之前，先在 `node_modules/next/dist/docs/` 读对应主题文档。
  你的训练数据里混着多个版本的写法，以本地文档为准。
- 不确定当前版本时，先跑 `node -p "require('next/package.json').version"`。

### 结构约定
- 采用「按功能就近切」：页面相关组件放该路由段的 `_components/`，取数放 `_lib/`。
- 只有被两个以上路由段使用的组件才放到顶层 `components/`。
- 私有目录一律用 `_` 前缀。禁止在 `app/` 下建不带 `_` 的组件目录。

### 边界约定
- `'use client'` 只加在真正需要状态、事件处理或浏览器 API 的**叶子**组件上。
- 禁止给 `app/**/layout.tsx` 加 `'use client'`。
- 客户端组件的 props 必须是可序列化的；ORM 对象先压成普通对象再传。
- 只在服务端使用的模块，顶部加 `import 'server-only'`。

### 渲染约定
- 新增页面前先明确它的渲染档位，并写进 PR 描述。
- 未缓存的数据读取必须包在 `<Suspense>` 里，或声明 `'use cache'`。
- 不允许用 `export const dynamic = 'force-dynamic'` 来消除构建错误。

### 禁止出现的写法
`getServerSideProps`、`getStaticProps`、`getStaticPaths`、`middleware.ts`、
同步读取 `params` / `searchParams` / `cookies()` / `headers()` / `draftMode()`、
`next lint`、`serverRuntimeConfig` / `publicRuntimeConfig`、
`experimental.ppr`、`experimental.useCache`、`experimental.dynamicIO`、
`next/legacy/image`、`images.domains`。

### 提交之前
- 跑 `next build`，必须通过。构建期的预渲染校验是主要安全网。
- 跑 `npm run lint`（构建不再自动跑 lint）。
- 至少在 `next dev` 里真实打开过改动的页面，看过终端的浏览器日志。

### 遇到构建报错时
- prerender 相关的错误会给出三条修法（流式 / 缓存 / 放弃预渲染），
  读完整段输出再改，不要只看最后一行。
- 生产构建的堆栈是压缩过的；需要定位源码时加 `--debug-prerender`。
```

---

## 五、给 Agent 的运行时反馈通道

这套框架给 Agent 留了几条「不看浏览器也能排错」的通道，值得在项目里明确启用：

| 通道 | 提供什么 | 怎么用上 |
|---|---|---|
| 构建/预渲染校验 | 精确到文件行号的「这行挡住了预渲染」+ 三条修法 | 每次改完跑 `next build` |
| 浏览器日志转发 | 客户端 `console` 错误与警告直接出现在终端 | 默认只转发错误；用 `logging.browserToTerminal` 调到 `'warn'` 或 `true` 看更多 |
| 开发服务器锁文件 | 第二个 `next dev` 启动时打印已有实例的 PID 与 URL | 遇到「另有一个 dev server 在跑」时读它，不要反复重启 |
| 随包文档 | 与安装版本一致的完整文档 | `AGENTS.md` 指过去即可 |
| 类型助手 | `PageProps` / `LayoutProps` / `RouteContext` | `next typegen` 生成，异步 `params` 迁移时尤其省事 |
| 错误页 | 每个构建错误都有一页对应的说明，含各种修法的取舍 | 终端输出里的 `Learn more` 链接 |

**为什么强调「不看浏览器也能排错」**：多数 Agent 会话只有终端，没有浏览器控制台。把上面几条打通，Agent 的自我纠错闭环才成立——否则它只能靠猜。

`.vscode/settings.json` 里加一组自定义标签，也能显著减少「同名文件改错」的概率：

```json
{
  "workbench.editor.customLabels.patterns": {
    "**/app/**/page.tsx": "${dirname(1)}/${dirname} - page.tsx",
    "**/app/**/layout.tsx": "${dirname(1)}/${dirname} - layout.tsx",
    "**/app/**/route.ts": "${dirname(1)}/${dirname} - route.ts"
  }
}
```
