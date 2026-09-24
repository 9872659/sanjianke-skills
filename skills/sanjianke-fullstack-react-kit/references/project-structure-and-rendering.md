# 项目结构与渲染模式选型

面向 Agent 协作的 Next.js 项目组织与渲染档位决策。上游项目：[Next.js](https://github.com/vercel/next.js)（MIT）。本文为独立编写，不是官方文档的翻译或摘抄。

---

## 一、目录与文件约定（Agent 必须先记住的部分）

### 1.1 顶层长什么样

```text
my-app/
├── app/                    # App Router：路由在这里，改动最频繁
│   ├── layout.tsx          # 根布局，必须有 <html> 和 <body>
│   ├── page.tsx            # 首页
│   └── globals.css
├── public/                 # 静态资源，按根路径直接访问
├── next.config.ts          # 框架配置
├── proxy.ts                # 请求前置处理（16 起取代 middleware.ts）
├── instrumentation.ts      # 启动期钩子、OpenTelemetry
├── .env.local              # 本地环境变量，不进版本库
├── AGENTS.md               # 给 Agent 的约束，越早写越好
├── tsconfig.json
└── package.json
```

四个顶层目录的职责边界很清楚，不要混：

| 目录 | 放什么 | 不该放什么 |
|---|---|---|
| `app/` | 路由、布局、页面、路由处理器 | 与路由无关的通用工具（可放但不推荐堆这里） |
| `pages/` | 老的 Pages Router，仅在存量项目里存在 | 新代码 |
| `public/` | 图片、字体、`robots.txt` 类原样资源 | 需要构建处理的代码 |
| `src/`（可选） | 整套应用代码，把配置文件和业务代码分开 | 配置文件 |

> **给 Agent 的提示**：`app/` 和 `pages/` 同时存在时，`app/` 优先。看到项目里有 `pages/` 不要以为它在生效，先确认对应路由有没有被 `app/` 里的同名路由接管。

### 1.2 路由文件约定（决定 URL 的那个字）

文件是**约定命名**，名字错了路由就静默消失。完整清单：

| 文件名 | 作用 | 何时用 |
|---|---|---|
| `page.tsx` | 让该目录成为可访问路由 | 任何需要 URL 的页面 |
| `layout.tsx` | 包住自己及所有子路由的共享 UI，跨导航保持状态 | 导航栏、侧边栏 |
| `template.tsx` | 类似 layout，但每次导航重新挂载 | 需要重置状态的场景（动画、表单） |
| `loading.tsx` | 该段落的加载占位 | 数据慢、需要骨架屏 |
| `error.tsx` | 该段落的错误边界（必须是客户端组件） | 局部容错 |
| `global-error.tsx` | 根级兜底错误页 | 根布局自身出错 |
| `not-found.tsx` | 404 UI | 自定义 404 |
| `route.ts` | 该目录成为接口端点 | 需要 JSON / 流式接口 |
| `default.tsx` | 并行路由的兜底页 | **并行路由槽必备** |

**渲染层级**（从外到内，Agent 排错时要按这个顺序看）：

```text
layout → template → error → loading → not-found → page
```

`loading` 是 React Suspense 边界，`error` 是 React 错误边界。子段的组件嵌在父段的组件**内部**。

### 1.3 三种括号语法，含义完全不同

| 写法 | 名字 | 对 URL 的影响 | 典型用途 |
|---|---|---|---|
| `(shop)` | 路由组 | **不影响**，括号被吃掉 | 同一层级套不同布局、按业务分区 |
| `_components` | 私有目录 | 完全不参与路由 | 放组件、工具、数据访问层 |
| `[slug]` | 动态段 | 匹配一段路径 | 详情页 |
| `[...slug]` | 全捕获 | 匹配一段或多段，**至少要有一段** | 文档树 |
| `[[...slug]]` | 可选全捕获 | 同上去掉「至少要一段」 | 文档树根路径也要命中 |
| `@modal` | 并行槽 | 不作为 URL 段，作为 prop 传给父布局 | 侧栏 + 主内容双视图 |
| `(.)photo` | 拦截路由 | 不改 URL，在当前布局里渲染 | 列表点开弹窗，刷新变整页 |

**Agent 最容易搞混的三件事**：

1. 把 `_components` 写成 `components`——后者会成为真实路由段，而且里面的 `page.tsx` 会突然可访问。
2. 以为 `blog/authors/page.tsx` 需要中间层 `page.tsx`：不需要。文件夹定义 URL，只有存在 `page` / `route` 的段才对外的那个路径生效。
3. 需要以下划线开头的真实 URL 段时忘了转义：写 `%5Ffolder`。

### 1.4 共置（colocation）是安全的

在 `app/` 里，**只有 `page` / `route` 返回的内容会发给浏览器**。同一个路由目录里放 `_components/`、`_lib/`、`types.ts`、测试文件都不会变成路由，也不会被打包到客户端（除非被客户端组件导入）。

这条对 Agent 友好度影响极大：**Agent 可以就近改文件，不需要在「页面目录」和「全局组件目录」之间来回跳**。但如果团队没统一策略，就近放会变成到处都是重复组件。所以必须选一种组织策略并写进 `AGENTS.md`。

---

## 二、四种组织策略（选一个，写进约定）

### 策略 A · 业务代码全在 `app/` 外面

```text
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── blog/page.tsx
├── components/
├── lib/
└── hooks/
```

- **优点**：`app/` 只剩路由，一眼看清全站 URL 结构。
- **缺点**：改一个页面要在两个地方跳（`app/blog/page.tsx` 和 `components/`），Agent 容易只改一半。
- **适合**：路由少、组件复用率高的站点。

### 策略 B · 业务代码集中在 `app/` 顶部

```text
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── components/
│   ├── lib/
│   └── blog/page.tsx
```

- **优点**：所有应用代码在一个根下，Agent 的搜索范围收敛。
- **缺点**：`app/` 下混着路由段和工具目录，新人（和 Agent）会分不清 `app/blog` 和 `app/components` 哪个是路由。
- **适合**：中小项目。

### 策略 C · 按功能就近切（**推荐给 Agent 协作的项目**）

```text
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── blog/
│       ├── page.tsx
│       ├── _components/
│       │   └── post-card.tsx
│       ├── _lib/
│       │   └── queries.ts
│       └── [slug]/page.tsx
├── components/          # 真的跨功能复用的才放这
└── lib/                 # 数据库、鉴权等基础设施
```

- **优点**：**改动半径最小**。Agent 要改「博客列表卡片」，只需在 `app/blog/` 里找；一次请求里读到的文件都在附近，上下文不浪费。跨功能的才升级到顶层，职责天然清晰。
- **缺点**：需要纪律。看到两个功能长得像就想抽公共组件的冲动要克制。
- **适合**：有多个业务模块、需要 Agent 频繁改动的项目。**默认推荐这一种。**

### 策略 D · 按路由组分区

```text
├── app/
│   ├── (marketing)/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   └── (shop)/
│       ├── layout.tsx
│       └── cart/page.tsx
```

- **优点**：同一 URL 层级下可以有完全不同的布局，甚至多个根布局（删掉顶层 `layout.tsx`，每个组各写一个，`<html>` / `<body>` 各自带）。
- **缺点**：URL 和目录不再对应，Agent 靠目录猜 URL 会猜错。
- **适合**：营销站 + 应用后台这类体验差异极大的分区。

### 选型建议（写进 `AGENTS.md` 的版本）

```md
## 目录约定

- 采用「按功能就近切」。新的页面逻辑写在对应路由段的 `_components/` 与 `_lib/` 下。
- 只有被 **两个以上** 路由段使用的组件才升级到顶层 `components/`；跨模块的数据访问放 `lib/`。
- 私有目录统一用 `_` 前缀，禁止在 `app/` 下新建不带 `_` 的组件目录。
- 禁止把 `page.tsx` 之外的路由文件改名为 `index.tsx`——框架不认这个名字。
```

---

## 三、渲染模式选型

### 3.1 先搞清楚 16.x 的模型变了

老版本的模型是「整页二选一」：这个页面要么静态、要么动态，用的是 `getStaticProps` / `getServerSideProps` 那种页面级导出，或者靠「有没有用动态 API」自动判定。

**16.x 的模型是「按组件决定」**：静态外壳 + 缓存内容 + 流式动态内容可以在同一个页面里共存。对应的开关是 `next.config.ts` 里的 `cacheComponents`：

```ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  cacheComponents: true,
}

export default nextConfig
```

开启后的行为变化，是 Agent 最容易踩的：

| 你写的代码 | 不开 `cacheComponents` | 开了 `cacheComponents` |
|---|---|---|
| `await fetch(...)` 直接在页面里 | 可能被自动静态化 | **构建报错**：未缓存数据要么加缓存，要么包 `<Suspense>` |
| 读 `cookies()` / `headers()` | 整页转为动态渲染 | 只让该子树流式，其余仍进静态外壳 |
| `Math.random()` / `Date.now()` | 原样输出 | **构建报错**：需显式用 `connection()` 或缓存 |
| `fs.readFileSync` / 模块级导入 | 构建期执行 | 构建期执行，进静态外壳（视为可预测值） |

**迁移建议**：存量项目不要一次性打开这个开关。它会把你原本靠「自动降级为动态渲染」糊过去的地方全部变成硬错误。按路由分批迁移，每批跑完 `next build` 再继续。

### 3.2 决策表（按页面主体判断）

| # | 页面特征 | 渲染档位 | 代码落点 |
|---|---|---|---|
| 1 | 所有人看到同样内容，很少变（关于页、定价页） | 预渲染 | 什么都不用写，纯同步组件自动进静态外壳 |
| 2 | 同样内容，但要按小时/天更新（文章列表） | 数据级缓存 | 数据函数加 `'use cache'` + `cacheLife('hours')` |
| 3 | 同样内容，需要内容一变就刷（商品详情） | 带标签缓存 | 上面基础上加 `cacheTag('product-<id>')`，写操作后 `revalidateTag` |
| 4 | 外壳相同，局部因人而异（导航 + 购物车） | 局部预渲染 + 流式 | 读 `cookies()` 的子树包 `<Suspense>`，外壳照常静态 |
| 5 | 每次请求都不同（后台、实时行情） | 请求时渲染 | 先 `await connection()`，并确保被 `<Suspense>` 包住 |
| 6 | 依赖搜索参数的列表页 | 缓存 + 流式组合 | 读 `searchParams` 的部分包 `<Suspense>`，查询函数加 `'use cache'` |
| 7 | 无服务端需求的纯静态站 | 静态导出 | `output: 'export'`，**放弃** Proxy、图片优化、ISR 等需要服务端的能力 |
| 8 | 随时可能变的落地页，又不想管缓存 | 短期缓存 | `cacheLife` 用较短 profile，配 `revalidateTag` 兜底 |

### 3.3 缓存指令怎么写

**数据级**——把「怎么取数」缓存起来，多个组件共用：

```ts
// app/lib/data.ts
import { cacheLife, cacheTag } from 'next/cache'

export async function getPosts() {
  'use cache'
  cacheLife('hours')
  cacheTag('posts')

  const res = await fetch('https://example.com/api/posts')
  return res.json()
}
```

**UI 级**——把「整块界面」缓存起来：

```tsx
// app/blog/page.tsx
import { cacheLife, cacheTag } from 'next/cache'

async function PostList() {
  'use cache'
  cacheLife('hours')
  cacheTag('posts')

  const posts = await getPosts()
  return (
    <ul>
      {posts.map((p) => (
        <li key={p.id}>{p.title}</li>
      ))}
    </ul>
  )
}
```

> **约束**：`'use cache'` 写在**文件顶部**时，该文件所有导出函数都被缓存——这是 Agent 常犯的过度缓存错误。默认写在**函数体内**。

**给缓存一个寿命**。不写 `cacheLife` 会落到隐式 `default` 档，行为不可预期。常用档位：

| profile | 大致语义 | 适用 |
|---|---|---|
| `seconds` | 秒级 | 热点但允许轻微延迟 |
| `minutes` | 分钟级 | 榜单、聚合统计 |
| `hours` | 小时级 | 内容列表、目录 |
| `days` | 天级 | 极少变的长文 |
| `max` | 尽量长 | 归档内容 |

**再验证的三种选择**（写错会导致用户看不到自己刚提交的数据）：

| API | 语义 | 用在哪 |
|---|---|---|
| `revalidateTag(tag, profile)` | 标记为陈旧，读者先看到旧内容，后台刷新 | 博客、商品目录这类允许延迟的 |
| `updateTag(tag)` | 立即过期并刷新，用户马上看到自己的修改 | 表单提交、用户设置 |
| `refresh()` | 刷新客户端路由 | 操作后需要更新页面统计数字 |

> **Agent 注意**：`revalidateTag` 现在需要第二个参数（缓存寿命 profile），单参数形式已废弃。写单参数会在类型检查里报错——报错是好事，别用 `as any` 盖掉。

### 3.4 流式与 `<Suspense>`

**关键认知**：`<Suspense>` 本身**不会**让组件变成动态渲染。它只是给异步工作提供一个占位。一个只做同步计算的组件，包了 `<Suspense>` 也照样在预渲染阶段完成。

它真正的作用是：**把「必须等到请求时才知道的东西」圈起来，让外层的外壳照常进静态输出**。

```tsx
import { Suspense } from 'react'
import { cookies } from 'next/headers'

async function UserGreeting() {
  const theme = (await cookies()).get('theme')?.value ?? 'light'
  return <p>当前主题：{theme}</p>
}

export default function Page() {
  return (
    <>
      <h1>控制台</h1>
      {/* 这行会进静态外壳 */}
      <Suspense fallback={<p>加载中…</p>}>
        {/* 这行在请求时才产出 */}
        <UserGreeting />
      </Suspense>
    </>
  )
}
```

**「把读取往下推」是提升静态外壳占比的核心手法**。对比：

```tsx
// 差：在布局这一层 await 了动态参数，整个布局都进不了静态外壳
export default async function Layout({ children, params }) {
  const { slug } = await params
  return (
    <div>
      <Sidebar />
      <h1>{slug}</h1>
      {children}
    </div>
  )
}
```

```tsx
// 好：布局不 await，把 promise 往下传，在边界内部解包
import { Suspense } from 'react'

export default function Layout({ children, params }) {
  return (
    <div>
      <Sidebar />
      <Suspense fallback={<h1>加载中…</h1>}>
        {params.then(({ slug }) => (
          <SlugHeading slug={slug} />
        ))}
      </Suspense>
      {children}
    </div>
  )
}

function SlugHeading({ slug }: { slug: string }) {
  return <h1>{slug}</h1>
}
```

**异步工作埋得越深，能预渲染的部分越多。**这条规律对所有运行时 API（`cookies` / `headers` / `searchParams` / `params`）都成立。

### 3.5 随机值与时间戳

开了 `cacheComponents` 以后，`Math.random()`、`Date.now()`、`crypto.randomUUID()` 会被拦下来。两种正当处理：

```tsx
// 方案一：请求时生成（每人不同）
import { connection } from 'next/server'

async function RequestId() {
  await connection()
  return <p>请求 ID：{crypto.randomUUID()}</p>
}
```

```tsx
// 方案二：缓存共享（所有人看到同一个，直到过期）
export default async function Page() {
  'use cache'
  const buildId = crypto.randomUUID()
  return <p>构建标识：{buildId}</p>
}
```

`performance.now()` 不在此列——它是给打点用的，不会被拦截，但也别拿去渲染。

### 3.6 局部预渲染（PPR）与 ISR

- **PPR 就是开了 `cacheComponents` 之后的默认行为**，不是一个单独的开关。16 起 `experimental.ppr` 和路由级 `experimental_ppr` 都已移除。
- 静态外壳可以直接由 CDN 返回，不经过源站。这是「直接访问某个 URL 也很快」的来源。
- **动态参数未知时**，先出「应用外壳」（URL 无关的那版），然后后台用真实参数渲染并缓存给下一个人，这就是 ISR 在 16.x 下的形态。
- 已知的参数用 `generateStaticParams` 在构建期预渲染；不在列表里的走上面的后台补渲染路径。

### 3.7 爬虫路径与人类路径不一样

这是一个反直觉但必须知道的行为：**用爬虫 UA 访问时，Next.js 会跳过静态外壳，完整地动态渲染整页再返回**。

后果：构建期能跑通的假设，在爬虫路径上可能不成立。典型失败是「外壳里嵌了只有构建环境才有的数据源」，人类访问正常，搜索引擎抓取报错。**上线前用真实爬虫 UA 抓一次关键页面**，别只看浏览器。

### 3.8 选择一览（给 Agent 的速查）

```text
这页所有人的内容一样吗？
├── 是 → 会变吗？
│        ├── 很少变 → 什么都不写（自动预渲染）
│        ├── 按时间变 → 'use cache' + cacheLife
│        └── 内容驱动 → 'use cache' + cacheTag + revalidateTag/updateTag
└── 否 → 差异有多大？
         ├── 只有一小块不同 → 把那块包 <Suspense>，其余保持静态
         └── 整页都不同 → await connection()（或读 cookies/headers），确保有 <Suspense>
```

**不确定的时候**：先按最静态的写法写，跑 `next build`。构建错误会精确地告诉你哪一行挡住了预渲染，并给出三条修法（流式 / 缓存 / 放弃预渲染）。**让构建器告诉你答案，比让 Agent 猜要快得多。**
