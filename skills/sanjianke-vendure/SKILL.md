---
name: sanjianke-vendure
slug: sanjianke-vendure
displayName: 三剪客 · 电商后端框架
description: "vendure：电商后端框架 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "vendure：电商后端框架 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 运营
---

# 三剪客 · 电商后端框架

你想自己掌控商品、订单、库存、促销这套后端逻辑，而不是把生意塞进一个改不动的商城模板里——这个框架就是干这个的。它不给你现成的店铺页面，只给你一套可编程的后端：商品与变体、订单状态机、库存与履约、促销与税费、多语言多币种，全部通过 GraphQL 接口暴露，前端爱用什么写就用什么。

它的价值在于「后端可扩展」：插件机制把支付、物流、搜索、促销钩子都留了口子，业务规则用 TypeScript 写在服务端，不靠改模板。所以它适合有研发能力、打算长期自建商城的团队；如果你只想三天上线一个卖货页，它会显得很重。

**上游项目**：`vendure`　**仓库**：https://github.com/vendurehq/vendure

## 什么时候用 / 不用

**用它**：

- 你要自建一套电商后端，前端（网站、小程序、App）各自独立，只要一个统一的商品/订单 API。
- 现有 SaaS 商城改不动：促销规则、订单流转、库存策略有自家逻辑，必须写在服务端。
- 需要多语言、多币种、多区域定价，或者同一个后端要同时支撑多个销售渠道。
- 团队是 TypeScript / Node.js 技术栈，希望后端和前端共用类型与工具链。
- 你要在商品、订单、支付流程上挂插件做二次开发，而不是只改样式。

**不要用它**：

- 只是想快速上线一个卖货页面、没有研发投入——用成熟 SaaS 商城或开源整站更省事。
- 团队不写 TypeScript，也没有维护 Node.js 服务的经验；它的扩展点就是代码。
- 你要的是现成主题市场、装修拖拽、开箱即用的前台页面——它默认只给一个管理后台。
- 只做内容展示或单一商品落地页，不需要订单、库存、履约这套状态机。
- 你的部署环境不允许常驻 Node.js 服务与数据库（纯静态托管场景）。

## 安装

前提：Node.js v20 / v22 / v24（官方测试并支持的版本）；想走 Quick Start 里的 Postgres，需要本机装好 Docker Desktop，没装则脚本退回 SQLite。

官方推荐的建项目方式（`my-shop` 换成你的项目名）：

```bash
npx @vendure/create my-shop
```

运行后会交互式选择：

- **How should we proceed**：选 `Quick Start`（一步配好数据库，Docker 在跑就用 Postgres，否则用 SQLite）；想自己选数据库就选 `Manual Configuration`。
- **Would you like to include a storefront**：可选 `None` / `TanStack Start` / `Next.js`，只是想先把后端跑起来就选 `None`。
- 手工模式下还会问数据库类型（MySQL / MariaDB / Postgres / SQLite）以及是否灌入示例商品数据——建议灌入，方便马上试 API。

装完启动：

```bash
cd my-shop
npm run dev
```

默认入口：

- 管理后台 Dashboard：http://localhost:3000/dashboard
- Admin GraphQL API：http://localhost:3000/admin-api
- Shop GraphQL API：http://localhost:3000/shop-api
- 前台（若装了 storefront starter）：http://localhost:3001/

装好终端会打印后台登录账号，默认是 `superadmin` / `superadmin`。

选 MySQL / MariaDB / Postgres 时，官方要求先确认三件事：数据库服务已启动（本机、云上或 Docker 都行），已经建好一个空库，并且有一个对该库有建表/改表/增删改查权限的账号。

如果创建过程失败，加详细日志重跑：

```bash
npx @vendure/create my-shop --log-level verbose
```

其他安装形态（Docker 镜像、云平台一键部署等）以官方文档为准。

## 常用操作

**1. 启动开发服务**（后端 + 前台一起起，如果项目里含前台）

```bash
npm run dev
```

**2. 用交互式 CLI 加插件或自定义功能**（在项目根目录执行，官方推荐用它生成脚手架代码）

```bash
npx vendure add
```

**3. 试一次 Shop API 查询**，确认服务端活了（取一个最简查询，POST 到 shop-api 端点）

```bash
curl -s http://localhost:3000/shop-api \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ activeChannel { id code } }"}'
```

**4. 带鉴权调 Admin API**（先登录拿 token，再用 token 查询，登录 mutation 以官方文档为准）

```bash
curl -s http://localhost:3000/admin-api \
  -H 'Content-Type: application/json' \
  -d '{"query":"mutation { login(username: \"superadmin\", password: \"superadmin\") { ... on CurrentUser { id identifier } } }"}'
```

**5. 重新灌示例商品数据**（建项目时没灌、或想重置演示数据时用）

```bash
npm run populate
```

> 第 3、4 条里的字段名与 mutation 名称随版本变动，实际以 Dashboard 里的 API Playground 或官方文档为准；第 5 条的脚本名以你项目 `package.json` 里 `scripts` 的实际内容为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `npx @vendure/create` 卡在数据库那步失败 | 选了 MySQL / Postgres 但本机没有可连的数据库服务，或库没建出来 | 先用 `Quick Start`（Docker 起 Postgres 或退回 SQLite）把流程跑通，再回头接自己的库 |
| 启动后访问 `/dashboard` 打不开 | 服务其实没起来，或者端口被占用后换了端口 | 看终端输出的实际端口，Dashboard、`/admin-api`、`/shop-api` 都挂在这个端口上 |
| 前台 3001 起不来 | 建项目时选了 `None`，项目里没有 storefront | 到项目目录用 CLI 补装官方 storefront starter，或单独拉一个 starter 仓库接上 `shop-api` |
| 升级 TypeScript 后编译报一堆错 | 建项目时锁定的 TypeScript 版本被手动升上去了，新版本引入了更严格的检查 | 把 TypeScript 版本退回项目初始化时的版本；别单独升它 |
| 用 Yarn 装依赖失败 | 旧版 Yarn 1（Classic）不被支持 | 换成 Yarn 2（Berry）及以上，或者直接用 npm / pnpm |
| Node 版本报错或构建出诡异问题 | 用了奇数版本或过新的 Node | 换到官方测试过的 v20 / v22 / v24 |
| 数据库连上了但表不存在，接口报错 | 只建了空库，没跑迁移 | 按项目里的迁移脚本初始化表结构（`package.json` 的 `scripts` 里找 migration 相关命令） |
| 插件写完没生效 | 插件只在文件里定义了，没注册进服务端配置 | 按官方插件文档把插件加进配置的 plugins 列表，重启服务 |
| 改了 GraphQL schema 但前端拿不到新字段 | schema 由服务端代码生成，改动后需要重启/重新生成 | 重启开发服务，必要时重新生成 schema 产物再让前端拉取 |
| 登录后台一直转圈或 401 | 用了非默认账号密码却仍填默认值，或 token 过期 | 用建项目时终端打印的凭据；GraphQL 请求记得带上鉴权头 |
| `npm run dev` 后端口冲突 | 3000 / 3001 已被其他程序占用 | 关掉占用进程，或按项目配置改端口；改端口后所有访问地址同步改 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取 npm 依赖、下载 Docker 镜像、必要时访问官方文档；本地开发还会监听 3000 / 3001 端口 |
| 读取文件 | 是 | 读取项目源码、`package.json`、配置文件、迁移脚本，用于安装与排错 |
| 写入文件 | 是 | 创建项目目录、写入依赖、生成配置与迁移文件；改动源码做二次开发 |
| 凭证 | 视情况 | 数据库账号密码、后台管理员账号；生产环境还会涉及支付/物流等第三方密钥。凭据只放环境变量或本地配置，不要提交进仓库 |
| 子进程 / 后台常驻 | 是 | 执行 `npx` / `npm` 命令，以及常驻运行的 Node.js 服务与数据库容器 |

## 触发场景

- 「我想自己搭一套电商后端，商品订单库存都要能自己改。」
- 「帮我用 vendure 起一个能在本地跑起来的商城服务端。」
- 「我这个商城要同时给网站和小程序供数据，怎么拆？」
- 「vendure 的后台进不去 / 起不来，帮我看看。」
- 「我要给下单流程加一段自家规则，vendure 里怎么写？」
- 「vendure 和现成 SaaS 商城比，我该选哪个？」

## 能力边界

**覆盖**：

- 用官方脚手架创建并运行一个 Vendure 服务端，含管理后台与两个 GraphQL 端点。
- 说明它的定位与适用团队，帮你在自建后端和现成商城之间做选择。
- 商品、订单、库存、促销、多语言多币种这些核心域的能力范围与扩展方式。
- 常见安装与启动故障的定位思路（数据库、端口、Node/Yarn 版本、storefront 缺失）。

**不覆盖**：

- 不提供现成前台页面：storefront 需要你自行开发或使用官方 starter 二次开发。
- 不替代支付、物流、发票等外部系统的接入实现，这些要走插件自行对接。
- 不包含生产环境的运维方案（容器编排、备份、监控、灰度），这些与你的部署平台有关。
- 不保证具体 API 字段名、mutation 名在各版本间不变，联调前请以 Dashboard 内的 API Playground 与官方文档为准。

## 依赖条件

- Node.js v20 / v22 / v24（官方测试并支持的版本）。
- 包管理器：npm、pnpm，或 Yarn 2（Berry）及以上。
- 数据库：SQLite（零依赖，适合试跑）、MySQL、MariaDB 或 Postgres；选后三者需自备可连的实例与一个有权限的账号。
- 想用 Quick Start 里的 Postgres，需要本机装好 Docker Desktop。
- 生产环境需要一台能常驻 Node.js 服务与数据库的机器或容器平台。

## 已知限制

- 它是无头（headless）后端，前台必须另做，不存在「装完就有店」。
- 二次开发门槛在 TypeScript 与 GraphQL，纯运营人员无法独立完成业务规则改动。
- 版本升级可能带来 TypeScript 严格度与 schema 变化，需要预留回归时间。
- 官方 starter 覆盖常见前端栈，但样式与业务页面仍需自行实现。
- 生产部署的数据库迁移、密钥管理、备份策略需要另行设计，工具不自带这些保障。

## 自检清单

执行前：

- [ ] 确认 `node -v` 落在官方支持的版本区间内。
- [ ] 确认目标端口 3000 / 3001 未被占用。
- [ ] 若用 MySQL / Postgres，先确认库已建好且账号有建表权限。
- [ ] 想清前台方案：选官方 starter，还是只先跑后端。

执行后：

- [ ] 终端打印了后台登录凭据与项目路径。
- [ ] 浏览器能打开 `/dashboard` 并用凭据登录。
- [ ] `/shop-api` 与 `/admin-api` 能返回 GraphQL 响应，而不是 404。
- [ ] 服务重启后数据仍在（说明数据库配置生效，没退回内存态）。
- [ ] 项目里的凭据没有出现在版本控制提交中。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/vendurehq/vendure | 上游仓库（安装与完整文档以它为准） |
| https://docs.vendure.io/ | 官方文档：安装、配置、插件、API 参考 |

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
