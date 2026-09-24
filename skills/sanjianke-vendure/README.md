# 三剪客 · 电商后端框架 Skill

vendure：电商后端框架 的安装、常用命令与避坑要点

---

## 前置条件

- **Node.js**：需要 v20 / v22 / v24（官方测试并支持的版本）。奇数版本或过新的版本不保证可用。
- **包管理器**：npm 或 pnpm；若用 Yarn，必须是 Yarn 2（Berry）及以上，Yarn 1（Classic）不受支持。
- **数据库**（三选一即可）：
  - SQLite —— 零外部依赖，适合本地试跑，选它就不用装数据库；
  - Postgres —— 想走官方 Quick Start 的 Postgres，需要本机装好 Docker Desktop，脚本会用容器起库；
  - MySQL / MariaDB / Postgres 自建实例 —— 需要先建好一个空库，并准备一个对该库有建表、改表、增删改查权限的账号。
- **端口**：默认监听 3000（后端 + 管理后台），若包含官方 storefront starter 还会占用 3001。
- **网络**：首次创建项目需要能访问 npm 源；用 Docker 起数据库还需要能拉镜像。

## 使用

最短跑通路径（`my-shop` 换成你的项目名）：

```bash
# 1. 创建项目（交互式）
npx @vendure/create my-shop

# 2. 进入目录并启动开发服务
cd my-shop
npm run dev
```

创建过程中的选择建议：

- **How should we proceed** → 第一次上手选 `Quick Start`，它会自己把数据库配好；想自己指定数据库再选 `Manual Configuration`。
- **Would you like to include a storefront** → 只想先看后端就选 `None`，需要前台再选 `TanStack Start` 或 `Next.js`。
- 手工模式下还会问数据库类型和「是否灌入示例商品数据」，建议灌入，方便马上试 API。

启动后终端会打印后台登录凭据与项目路径，默认账号是 `superadmin` / `superadmin`。可访问：

| 入口 | 地址 |
|---|---|
| 管理后台 Dashboard | http://localhost:3000/dashboard |
| Admin GraphQL API | http://localhost:3000/admin-api |
| Shop GraphQL API | http://localhost:3000/shop-api |
| 前台（装了 starter 才有） | http://localhost:3001/ |

排查安装问题时，加详细日志重跑：

```bash
npx @vendure/create my-shop --log-level verbose
```

更多操作与避坑要点见 `SKILL.md`。

## 依赖

- 运行环境：Node.js v20 / v22 / v24、npm 或 pnpm 或 Yarn 2+。
- 数据库驱动由所选数据库决定：SQLite 无需额外服务；MySQL / MariaDB / Postgres 需要可连的实例。
- 可选：Docker Desktop（用 Quick Start 的 Postgres 时需要）。
- 可选：官方 storefront starter（TanStack Start 或 Next.js），仅在需要现成前台时安装。
- 无必需的外部账号或 Key；生产环境接入支付、物流、搜索等第三方服务时，才会引入各自的密钥。

## 安全

- 不内嵌任何密钥；本包只包含说明文字，不含上游项目源码。
- 后台默认凭据 `superadmin` / `superadmin` 只用于本地开发，上线前必须改掉。
- 数据库账号密码、第三方支付/物流密钥一律放环境变量或本地配置文件，不要提交进版本控制。
- 管理后台与 Admin API 是对外攻击面，生产环境务必收紧访问来源、启用 HTTPS，并配合反向代理。
- 该框架需要常驻 Node.js 服务与数据库进程，请按最小权限原则运行，避免用 root 直接跑服务。
- 执行 `npx` 与安装依赖会从公网拉取代码，请在可信网络与受控的 npm 源下操作。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`vendure`
- 仓库：https://github.com/vendurehq/vendure

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
