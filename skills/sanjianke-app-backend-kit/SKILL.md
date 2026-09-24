---
name: sanjianke-app-backend-kit
slug: sanjianke-app-backend-kit
displayName: 三剪客 · Postgres 应用后端
description: "Supabase 自托管选型、表设计与 RLS 权限落地。 遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "Supabase 应用后端落地包：自托管与云托管取舍、表设计与行级安全（RLS）防泄露配置、连接池与备份升级运维，附 Agent 防漏权规则与可复制 SQL/命令。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 开发编程
  - 后端
  - API
---

# 三剪客 · Postgres 应用后端

Supabase 把一个 Postgres 数据库和一圈现成的后端服务绑在一起：数据库直出 REST 与 GraphQL、
JWT 登录、对象存储、WebSocket 实时、边缘函数，再加一个可视化管理台。好处是后端不用从零写，
代价是**权限模型从「应用层判断」变成了「数据库层判断」** —— 一条写错的策略就是一次数据泄露，
而且不会有任何报错，接口照常返回 200。

这个包不教你写 Todo 示例。它解决的是三个真正卡人的问题：

1. **自托管还是云托管** —— 很多人卡在这一步，来回折腾几个月，最后两边都没落定。
2. **表怎么设计、行级安全（RLS）怎么配才不出漏洞** —— 这是唯一一类「上线时正常、被拖库时才发现」的错误。
3. **Agent 在这个项目里怎么少犯错** —— 上游文档体量极大、版本迭代快，模型很容易凭记忆写出
   过期的端口、命令和策略写法。

本包给的是**判断依据 + 可复制的 SQL/命令 + 一份漏权检查清单**，不是上游文档的搬运。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **仅核对事实时** | 查询容器镜像标签、组件端口分配、上游发布说明与许可证页面；不调用你的任何业务接口，不上传任何数据 |
| 读取文件 | 仅读取你指定的目录 | 读 `supabase/config.toml`、`supabase/migrations/*.sql`、`docker/docker-compose.yml`、`.env.example`（只读键名），用于诊断配置与策略问题 |
| 写入文件 | 默认不写；仅在你明确要求时 | 生成迁移 SQL、策略草稿或 `.env` 模板到你指定的路径；**不覆盖已有迁移文件** |
| 凭证 | **不读取、不打印** | 不接触 `POSTGRES_PASSWORD` / `JWT_SECRET` / `service_role` key / `sb_secret_*`。诊断时只输出键名与占位符，永不回显真实值 |
| 子进程 / 后台常驻 | 仅在你要求时执行只读命令 | `docker compose ps` / `logs`、`supabase status` / `db lint` / `db diff`、`psql -c`（只读查询）。不常驻、不改动全局 Docker 配置、不对生产库执行写操作 |

**本 Skill 不内嵌任何密钥、Token 或 Cookie，不代持你的数据库账号。** 文中的端口、命令、
组件名与许可证事实来自独立核对，属于公开信息；上游项目是第三方开源软件，其许可证、发布节奏与
兼容策略由该项目自行决定，安装与运行仍需你自行完成。

**必须知道的一条**：`service_role` key 与 `sb_secret_*` key **绕过 RLS**。它们只能出现在服务端。
任何一次把它们打进前端包、写进日志、贴进聊天记录，等于把整个库交出去。

## 触发场景

- 「我这个项目到底该用 Supabase 云托管，还是自己拿 Docker 起一套？」
- 「新加了一张表，怎么配权限才不会被陌生人直接读走 / 写脏？」
- 「前端退出登录后还能查到别人数据」「接口没报错但返回了空数组，到底是被策略挡了还是真没数据」
- 「RLS 打开之后列表页变得特别慢，几万行要好几秒」
- 「云上跑得好好的，搬到自托管之后登录 401、上传 403、实时连接连不上」
- 「要让 Agent / 定时任务访问数据库，能不能给它 service_role key？」（答案在 RLS 那一节）

**不适用于**：只想跑通一个五分钟 Todo 示例、用别的后端框架（Prisma + 自建 Node 服务等）
只把 Postgres 当普通数据库用、或者要做多租户企业级 HA 架构设计与容量规划。

## 快速开始

按顺序走，**第 2 步和第 4 步不能省**。第 4 步是本包存在的主要理由。

```bash
# 1. 装 CLI（项目内固定版本，团队才不会各跑各的）
npm install supabase --save-dev     # 之后一律用 npx supabase <command>
npx supabase --version              # Node.js 需 20+

# 2. 本地起一套，用它当「不花钱的测试场」
npx supabase init
npx supabase start                  # 首次拉镜像 2~3 GB，几分钟
npx supabase status                 # 拿本地 URL 与 key；真值看 config.toml，别背端口

# 3. 表结构一律走迁移，不在云上手工点
npx supabase migration new init_schema
#    编辑 supabase/migrations/<timestamp>_init_schema.sql
#    —— 建表、授权、开 RLS、写策略，一次写完
npx supabase db reset               # 本地重放全部迁移 + seed.sql

# 4. 漏权体检（每次改表必跑）
npx supabase db lint                # 静态检查，重点看 rls_disabled_in_public
npx supabase test db                # 跑 pgTAP 测试，含策略用例

# 5. 上云或上自托管
npx supabase link --project-ref <ref>
npx supabase db push
```

自托管 Docker 路线的最小路径：

```bash
# 仓库地址见同目录 README.md「版权」处的上游地址；务必钉住发布标签，不要跟主干
git clone --depth 1 --branch self-hosted/v0.8.1 <上游仓库地址>
mkdir supabase-project && cp -rf supabase/docker/. supabase-project
cd supabase-project && cp .env.example .env
sh ./utils/generate-keys.sh        # 生成 POSTGRES_PASSWORD / JWT_SECRET / key 对
grep -nE "your-super-secret|insecure|example" .env   # 必须无输出
docker compose pull && docker compose up -d
```

**三条铁律，先记住再动手**：

1. **端口和默认值以你机器上的文件为准**。`supabase status` 和 `.env` 的输出是真值，
   网上抄的端口号不是。本地 CLI 与自托管 Docker 的端口**完全不是一套**。
2. **授权（GRANT）与策略（POLICY）是两层，必须都配**。只写策略不撤销授权，
   照样留了一条写入路径。
3. **上线前跑一次漏权检查清单**（见 `references/tables-and-rls.md` 第五节），
   别等被拖库才发现。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 判断自托管还是云托管、算成本与运维代价、搞清两套端口与配置来源 | `references/self-host-vs-cloud.md` |
| 设计表、写迁移、配 RLS、排查「能查到不该查的数据」与 RLS 性能 | `references/tables-and-rls.md` |
| 启动 / 备份 / 升级 / 连接池 / 排错，以及 Agent 防错规则 | `references/deploy-and-troubleshoot.md` |
| 只想先确认「这事能不能干」 | 本页「能力边界」+「已知限制」 |

## 能力边界

**覆盖**：

- **两条部署路线的取舍**：云托管、Docker 自托管、CLI 本地栈三者的定位差异，
  以及「本地开发 ≠ 自托管」「自托管 = 单项目」这两个最容易搞错的前提
- **两套端口与配置来源**：CLI 本地栈（54321/54322/54323/54324 系列）与
  自托管 Docker（网关与数据库端口、`.env` 变量）的对照，以及「以本机文件为准」的核对方法
- **云托管缺失的能力清单**：分支、PITR 与托管备份、高级指标、向量桶、ETL、平台管理 API
- **表设计规范**：主键与时间戳、归属列 `user_id`、`references` 外键、枚举、软删、
  多租户成员表的建模方式
- **RLS 完整落地链路**：`enable row level security` → `create policy`（四种操作分开）→
  `to authenticated` 显式限定角色 → 撤销默认授权 → 索引与 `(select ...)` 性能写法
- **漏权检查清单**：可直接粘贴执行的 SQL，逐条回答「这张表陌生人能不能读 / 能不能写」
- **RLS 性能**：策略列建索引、`(select auth.uid())` 的 initPlan 缓存、`security definer`
  函数、连接方向优化、用 `explain analyze` 与 PostgREST `explain` 量化
- **函数与触发器安全**：`security definer` + 固定 `search_path`、把内部函数放进非暴露 schema
- **运维骨架**：备份、版本升级与回滚、连接池（直连 / 事务池 / 会话池）的选择与坑
- **Agent 防错规则**：先实测再断言、改表与改策略必须同一次迁移里完成、禁止代持密钥

**不覆盖**：

- 不搬运上游 README、文档原文、代码或 Skill 文件；只提炼事实与判断依据
- **不替你拍板选型**。本包给的是取舍维度与代价清单，最终结论取决于你的合规要求、团队规模与预算
- 不写你的业务代码（前端组件、具体语言的 ORM 用法、支付与业务逻辑）
- 不做多租户企业级 HA 架构设计、不做容量规划与压测方案设计
- 不涉及数据仓库 / ETL、向量检索与 AI 应用编排
- 不执行任何生产变更：不写你的生产库、不改线上 `.env`、不重启你的服务
- 不保证上游 API 与命令永久兼容 —— 本包给的是**核对方法**，不是永久快照

## 依赖条件

| 项 | 要求 |
|---|---|
| Docker | Docker Engine + Compose v2（命令是 `docker compose`，不是 `docker-compose`），自托管路线必需 |
| 资源（自托管） | 最低 4 GB 内存 / 2 核 / 40 GB 盘；推荐 8 GB+ / 4 核+ / 80 GB+。不需要实时、存储、函数时可删掉对应服务降配 |
| Node.js | 用 `npx supabase` 跑 CLI 需 Node.js 20 或更高（16 会直接失败） |
| 客户端 | `psql` 或任意 Postgres 客户端（排查策略必用）；`pgTAP` 扩展用于策略测试 |
| 网络 | 拉镜像、`npx` 安装、云托管 API 访问；自托管生产必须配好 TLS 反向代理 |
| 可选 | S3 兼容对象存储（存储服务）、SMTP（邮件验证与找回密码） |

## 已知限制

这一节是**核对结果**，动手前请读完：

- **本地栈绝不能直接当自托管用**。CLI 起的本地一套带的是固定开发凭据、没有加固，
  上游明确说明它不面向生产、不可暴露到公网。自托管请走 Docker Compose 或社区部署方案。
- **自托管是单项目的**。Studio 不支持多组织 / 多项目，多数设置通过环境变量配置；
  需要多项目管理或分支能力时，自托管给不了。
- **自托管由你负责的面很大**：服务器、加固、升级、Postgres 维护、高可用、备份与容灾、
  监控与可用性。这些不是「配好就不管」，是持续投入。
- **网关组件正在换代**。较新的自托管发行版默认用 Envoy 做 API 网关，同时保留 `kong` 网络别名
  以便旧配置过渡。看到别人写 Kong 不必困惑，但要**按自己那份 compose 文件为准**去确认
  实际跑的是哪个，别照抄旧文章改错文件。
- **API key 有两代并存**。旧的 `ANON_KEY` / `SERVICE_ROLE_KEY`（HS256 JWT）与新的
  `sb_publishable_*` / `sb_secret_*`（不透明 key）。两者语义不同：
  publishable 约等于 anon，secret 约等于 service_role（**都绕过 RLS**）。
  换 key 之后必须同步更新前端、函数与所有服务端集成。
- **默认权限模型正在变**。老项目里 `public` schema 的新表会自动给 `anon` / `authenticated`
  发 `select/insert/update/delete` 授权，而平台正在改成「不自动发、要显式授权」。
  同一份迁移在不同项目上表现可能不一样，**不要靠假设，用检查清单实测**。
- **RLS 是性能杠杆，不是免费开关**。策略里每行都要执行的函数调用会随表变大而放大，
  十万行级别上，写得随意与写得讲究差出上百倍。策略写完后必须用大表或
  `explain analyze` 验证一次。
- 本包未在你的具体环境复现全部命令，示例侧重**结构与判断依据**；执行前请用 `supabase status`、
  `.env` 与 compose 文件核对实际值。

## 自检清单

上线前逐条打勾，任何一条打不上就先别合：

- [ ] 已明确部署路线，并且写下了选择理由（合规 / 成本 / 运维人力三者中有明确的决定项）
- [ ] 本地开发用的是 CLI 栈，生产用的是自托管 Docker 或云托管 —— **没有把本地栈暴露到公网**
- [ ] `.env` 里没有任何默认密码残留：`grep -nE "your-super-secret|insecure|example" .env` 无输出
- [ ] `POSTGRES_PASSWORD` 与 `JWT_SECRET` 均为独立生成（≥32 字符），未在仓库中出现
- [ ] `service_role` / `sb_secret_*` key 只存在于服务端，前端产物全文检索无命中
- [ ] 每一张**暴露 schema**（默认 `public`）里的表都已启用 RLS，无遗漏（检查清单第 1 条必须为空结果）
- [ ] 每张表都**同时**有策略与最小化授权，授权不是「全给三个角色」
- [ ] 每条策略都带 `to authenticated` 或 `to anon`，没有裸策略
- [ ] `insert` / `update` 策略带 `with check`，没有只写 `using` 就以为能挡住写入
- [ ] 相关视图设置了 `security_invoker`，没有被视图绕过底层表的 RLS
- [ ] 所有 `security definer` 函数都固定了 `search_path`，内部函数不在暴露 schema
- [ ] 策略里用到的列已建索引；`auth.uid()` / `auth.jwt()` 已用 `(select ...)` 包裹
- [ ] 用 `explain analyze` 或大表实测过关键查询，慢查询已定位到是策略还是索引
- [ ] 已配自动化备份并**做过一次恢复演练**（没演练过的备份等于没有备份）
- [ ] 升级前记录了当前版本标签与迁移清单，并确认回滚路径
- [ ] 连接方式按负载选对了（长连接服务用会话池 / 短请求用事务池），没有把直连当池用
- [ ] TLS 已启用，防火墙只放行必要端口
- [ ] `npx supabase db lint` 与 `npx supabase test db` 均通过

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/self-host-vs-cloud.md` | 云托管 / Docker 自托管 / CLI 本地栈三路线对照、端口与配置来源、取舍维度与决策路径 |
| `references/tables-and-rls.md` | 表设计规范、GRANT 与 POLICY 两层模型、策略写法、**漏权检查清单**、错误码对照、RLS 性能优化 |
| `references/deploy-and-troubleshoot.md` | 启动顺序、连接池、备份与升级、端口与防火墙、故障排查决策表、Agent 防错规则 |

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
