# 部署运维与排错

前两份文件把路线和权限定下来了，这份管**跑起来之后**：启动、备份、升级、连接数、排错。
最后一节是给 Agent 的防错规则。

---

## 一、启动与健康检查

### 自托管 Docker 的启动顺序

```bash
cd supabase-project
docker compose pull
docker compose up -d
docker compose ps            # 等所有服务变成 healthy，1~2 分钟
docker compose logs -f       # 卡住时看这里，不要瞎猜
```

第一次起不来，90% 是这三件事：

1. **`.env` 里还是默认密码** —— 默认值公开可查，有些版本会直接拒绝启动或用不安全的凭据跑起来
2. **宿主机端口被占用** —— 报错里有 `address already in use`，改 `.env` 里的端口变量
3. **内存不够** —— 容器被杀，`docker compose ps` 看到反复重启

```bash
# 找端口占用（Linux）
ss -lntp | grep -E ':(8000|5432)'
# 看容器退出原因与退出码
docker compose ps -a
docker inspect --format '{{.State.ExitCode}} {{.State.Error}}' <container>
```

内存不足时，**不要硬扛**。从 compose 文件里删掉用不到的服务段落
（实时、存储、图片代理、边缘函数），内存需求会明显下降。
默认配置**不包含**日志与分析组件，需要的话要额外启用一个叠加文件，
并且它会进一步增加资源占用。

### 本地栈的健康检查

```bash
npx supabase status        # 服务状态 + URL + key
npx supabase status -o env # 机器可读
```

`status` 里某个服务是 `stopped`，别急着写代码，先把它起来。

### 端口与防火墙

自托管生产**只放行必要的端口**，其余一律关掉：

```bash
# UFW 示例
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp          # 运维入口
sudo ufw allow 443/tcp         # 对外 HTTPS
# 数据库端口不要直接对外 —— 走内网或隧道
sudo ufw enable
sudo ufw status verbose
```

**两条容易犯的错**：

- 图方便把数据库端口开在公网 IP 上，靠密码扛。密码泄露只是时间问题。
- 直接暴露网关的 HTTP 端口而不加 TLS。生产必须有反向代理终止 TLS，
  否则用户 token 在链路上裸奔。

`.env` 里的对外地址变量（`SUPABASE_PUBLIC_URL` / `API_EXTERNAL_URL` / `SITE_URL` /
`PROXY_DOMAIN`）填错会导致：邮件里的链接指向 localhost、OAuth 回调失败、
对象存储签名校验不过。**改完域名一定要回来看这几个变量。**

---

## 二、连接池：先把概念理清

**这是自托管里最容易被误配、出问题又最难查的一块。**

先记住一句话：**直连不是池**。把直连地址当池用，就是把连接数上限直接交给业务代码。

### 三种连法的区别

| 模式 | 适用 | 关键限制 |
|---|---|---|
| 直连（直连数据库端口） | 运维脚本、迁移、一次性任务 | 每个客户端一个真实连接，**不能用于高并发应用** |
| 事务模式（连接池的 transaction 端口） | 短请求、无状态服务、无服务器函数 | **不支持**会话级特性：预编译语句（prepared statements）、会话级 `set`、临时表、`LISTEN/NOTIFY` |
| 会话模式（连接池的 session 端口） | 长连接服务、需要事务跨越多次往返、要用预编译语句 | 连接在会话期间被独占，池化收益低于事务模式 |

### 怎么选

```
你的客户端是……
├─ 无服务器函数 / 边缘函数（生命周期短、并发高）
│    └─ 事务模式。并且：关掉客户端的预编译语句缓存
├─ 常驻服务（Node / Go / Java 后端进程）
│    ├─ 用 ORM 且开了预编译语句 → 会话模式
│    └─ 每次请求独立、不用会话状态 → 事务模式
├─ 迁移工具 / 运维脚本
│    └─ 直连（但要确保不在业务高峰跑）
└─ 本地开发
     └─ 直连本地库，别折腾池
```

### 最典型的事故现场

**现象**：接口平时正常，一压测或一上量就报错，错误信息大意是
「当前不支持预编译语句」（`prepared statement "s1" already exists` 一类）。

**原因**：客户端（ORM 或驱动）开了预编译语句缓存，连接的却是**事务模式**的池端口。
事务模式下，同一个客户端的不同请求可能落在不同的后端连接上，
客户端以为「我这条语句已经在连接上准备好了」，实际那条连接上根本没有。

**修法（任选其一）**：

- 换成会话模式的端口（最省事，代价是池化收益下降）
- 关掉驱动 / ORM 的预编译语句缓存
- 只用直连（仅在并发很低时可行）

**自托管的端口真值**：在 `.env` 里找连接池相关变量
（事务模式端口、会话模式端口两个键），不要背数字。
改完端口后需要重建容器才会生效。

### 连接数上限

Postgres 的连接数上限是有限的，而每个后端连接都占内存，**不是越大越好**。
判断依据：

```sql
show max_connections;
select count(*), state from pg_stat_activity group by state;
select pid, usename, application_name, state, now() - state_change as idle_for
from pg_stat_activity
where state = 'idle' and now() - state_change > interval '10 minutes'
order by idle_for desc;
```

- 大量 `idle` 长时间不释放 → 应用侧没归还连接，或者用了直连当池用
- `idle in transaction` 堆积 → 事务里有慢操作或漏了 commit，**这种最伤**
- 连接数打满 → 先加池、再调应用超时，最后才考虑抬 `max_connections`

---

## 三、备份与恢复

**没做过恢复演练的备份，等于没有备份。** 这句话请当成本节的标题。

### 自托管：备份要自己搭

自托管**没有**托管备份与时间点恢复（PITR），这两个能力属于云托管。
自己搭的话，最小可用方案：

```bash
# 逻辑备份（结构与数据）
docker compose exec -T db \
  pg_dump -U postgres -d postgres -Fc \
  > backup-$(date +%F-%H%M).dump

# 只备份结构（迁移之外再留一份，用于审计）
docker compose exec -T db \
  pg_dump -U postgres -d postgres --schema-only \
  > schema-$(date +%F).sql
```

要点：

- **`-Fc`（自定义格式）**：压缩比好，且能用 `pg_restore` 选择性恢复单表
- **备份文件要出机器**：放在同一台机器上，机器挂了备份一起挂
- **轮转与保留策略**：写清楚保留多少天、多少份，别越堆越多撑满磁盘
- **加密与访问控制**：备份里是全部业务数据，敏感度等于生产库

恢复演练（**在隔离环境做，不要动生产**）：

```bash
# 新建库再恢复
docker compose exec -T db createdb -U postgres restore_test
docker compose exec -T db \
  pg_restore -U postgres -d restore_test --no-owner < backup-2026-01-01-0300.dump

# 核对行数
docker compose exec -T db psql -U postgres -d restore_test \
  -c "select 'notes' t, count(*) from public.notes union all select 'teams', count(*) from public.teams;"
```

**演练要记录下来**：什么时候做的、恢复了什么、耗时多久、发现什么问题。
没记录等于没做。

必须自建且容易被忽略的两件事：

- **物理备份（文件级快照）**：逻辑备份慢且大，灾难恢复用物理快照更快
- **WAL 归档**：想要「恢复到某个时间点」，只有 WAL 归档能做到，逻辑备份做不到

### 云托管：能力有了，流程还是要自己定

备份与 PITR 是平台提供的，但以下仍是你的事：

- 恢复策略（恢复到哪个时间点、由谁决策、多久能完成）
- 定期导出到自己的存储（避免单一依赖）
- 恢复演练的排期与记录

### 数据迁移

进和出都用标准工具（`pg_dump` / `pg_restore` / CSV），这是选 Postgres 的核心好处之一。
迁移的**真实难点不是数据，是权限模型**：

- 自托管迁到云托管：确认云上的默认权限与你的老项目一致（平台正在改默认值），
  迁移后**必须重跑一遍漏权检查清单**
- 云托管迁到自托管：`service_role` 相关的服务端集成要重新配 key
- 认证数据（用户表）迁移要特别注意，用户 id 变了的话所有归属列全废

---

## 四、升级与回滚

### 记下当前版本（升级前必做）

```bash
cd supabase-project
cat .supabase-version        # 一键安装脚本会写这个文件，记录当前基础版本
docker compose images        # 各服务实际跑的镜像标签
```

### CLI 本地栈升级

```bash
# 先停容器、清数据卷（本地数据不要也能重建的话）
npx supabase stop
# 清掉本地卷后重启，让受管服务在干净的库上应用迁移
npx supabase start
```

本地数据无所谓随便清，**但如果本地库里有你还没写成迁移的改动，清了就没了**。
清之前先 `npx supabase db diff` 看一眼有没有漂移：

```bash
npx supabase db diff -f pending_changes   # 把手工改的 schema 反向生成迁移
```

### 自托管升级

关键动作是**同步配置文件**，不只是拉新镜像：

1. 读一遍新版 changelog，确认有没有破坏性变更
2. 把新的 `.env.example` 与自己的 `.env` **逐段对比合并**（新增的键要补上）
3. 更新 `docker-compose.yml` 以及需要的工具脚本、网关配置目录
4. 拉镜像、重建容器
5. 跑一遍漏权检查清单与冒烟测试

```bash
diff -u .env .env.example    # 注意：这会把你的密钥打到终端上，注意录屏/日志泄露
docker compose pull
docker compose up -d
sh run.sh recreate           # 或按你的版本用 run.sh restart <service>
```

**注意 `diff` 会回显密钥。** 在共享终端或带日志录制的环境里，
改用只看键名的方式：

```bash
grep -oE '^[A-Z_]+=' .env.example | sort > /tmp/keys.new
grep -oE '^[A-Z_]+=' .env         | sort > /tmp/keys.old
comm -23 /tmp/keys.new /tmp/keys.old     # 新版本新增、我还没配的键
```

### Postgres 主版本升级

数据库主版本升级（例如从旧主版本跨到新主版本）**不是换镜像就行**，
需要走标准的数据目录迁移流程，且**必须先备份**。
这类升级安排在维护窗口，预留回滚时间。

### 回滚

回滚能成立的前提是**升级前记录了版本标签**：

- 镜像回退：把 compose 里的标签改回原版本，重建容器
- 数据回退：用升级前的备份恢复 —— **升级后到回滚之间的数据会丢**，
  这是必须提前告知业务的事实
- 迁移文件：数据库迁移通常是单向的。回滚应用版本前，确认它与当前 schema 兼容

**判断口径**：如果答不出「回滚要多久、丢多少数据」，这次升级就还没准备好。

---

## 五、排错决策表

按现象查，先看「先查什么」，再看「常见原因」。

| 现象 | 先查什么 | 常见原因 |
|---|---|---|
| 容器起不来 / 反复重启 | `docker compose logs <service>` | 密钥缺失或仍是默认值、端口占用、内存不足 |
| `ExitCode 137` | `docker stats` | 被 OOM 杀掉，内存不够 |
| `address already in use` | `ss -lntp` | 宿主机端口冲突，改 `.env` 端口变量 |
| 数据库连不上 | `docker compose ps db`、`pg_isready` | 库没起完、端口映射不对、密码错、防火墙 |
| 接口 401 | 请求头里的 `apikey` 与 `Authorization` | key 与 URL 不匹配（本地 key 打到生产 URL）、`JWT_SECRET` 变更后旧 key 失效、token 过期 |
| 接口 403 / 存储上传失败 | 存储服务日志、策略与授权 | 未授权、策略拦截、签名 URL 的域名与 `PROXY_DOMAIN` 不一致 |
| 接口 42501 | 该表的 GRANT | 角色没有表级授权 —— **这是授权问题，不是策略问题** |
| 接口不报错但返回空数组 | 策略 + 模拟身份实跑 | 策略过滤掉了全部行，或表根本没策略 |
| 能查到别人的数据 | 漏权检查清单**全部 9 条** | 表没开 RLS、视图绕过 RLS、授权给太宽 |
| 列表页很慢、越大越慢 | `explain analyze` | 策略列无索引、`auth.uid()` 未包 `(select ...)`、未写 `to`、连接方向反了 |
| 写入偶尔失败且报错莫名 | 客户端连接串 | 用了事务模式端口但开着预编译语句缓存 |
| 实时连接连不上 / 立刻断开 | 浏览器控制台 + 网关配置 | key 未带在查询参数、网关 CORS、WebSocket 路由被拦 |
| 邮件收不到 / 链接指向 localhost | `.env` 的地址类变量 + 邮件服务 | `SITE_URL` / `API_EXTERNAL_URL` 错、SMTP 未配、本地环境要去 Mailpit 看 |
| OAuth 回调失败 | 回调地址 + 服务商配置 | 回调 URL 没在服务商侧登记、`SUPABASE_PUBLIC_URL` 不一致 |
| `prepared statement already exists` | 连接模式 | 见上一行「写入偶尔失败」 |
| 改了配置但没生效 | 是否需要重建容器 | 网关与环境变量类配置**需要重建容器**，仅 reload 不够 |

### 三条通用的排查纪律

1. **先看日志，再改配置。** `docker compose logs -f <service>` / `npx supabase status`。
   凭印象改配置是最慢的路径。
2. **一次只改一个变量。** 同时改三处，改好了也不知道是哪处起了作用，
   改坏了更不知道回退哪一处。
3. **权限类问题先分清是 ①GRANT 还是 ②POLICY。**
   `42501` 一定是授权；「空数组」多半是策略。
   分错层的排查会绕很久。

---

## 六、给 Agent 的防错规则

这一节是本包第三块要解决的事：**让 Agent 在这个项目里少犯错**。
上游体量极大、版本迭代快，模型的「记忆」在这里是负资产。

把下面这段作为给 Agent 的作业约束。

### 规则 1：端口、命令、默认值一律先实测

**禁止**凭记忆写端口号、默认密码、镜像标签、CLI 参数。
先跑核对命令，再写结论：

```bash
npx supabase status            # 本地端口与 key 的真值
npx supabase --version         # CLI 版本
docker compose ps              # 自托管服务的真值与健康状态
docker compose images          # 镜像实际标签
grep -nE '^[A-Z_]+=' .env | sed 's/=.*/=<hidden>/'   # 只看键名，绝不回显值
```

如果核对不了（没有环境、没有权限），**正确做法是说明「需要你执行这条命令确认」**，
而不是给一个看起来很确定的数字。

### 规则 2：本地栈与自托管是两套数字，不能混

CLI 本地栈、自托管 Docker、云托管三者的端口、凭据、配置来源**都不一样**。
Agent 最常见的错误是把本地那套 5432x 端口当成自托管端口写进部署文档。

**检查动作**：写完任何端口，问一句「这个数字来自哪份文件」。
答不出来就重查。

### 规则 3：改表 = 同一次迁移里同时搞定授权与策略

**禁止**输出「先建表，稍后再补策略」这种分步建议。
一次迁移必须包含：建表 → 索引 → `enable row level security` → 授权收窄 → 四条策略。

### 规则 4：新增暴露表后必须跑漏权检查

Agent 交付任何新表，都要附带一段漏权自检（至少前四条 SQL），
并明确告诉使用者「执行后第 1 条必须为空」。

### 规则 5：绝不代持、绝不出现在提示词里的东西

Agent **不得**索取、读取、回显、写入以下内容：

- `POSTGRES_PASSWORD`、`JWT_SECRET`
- `SERVICE_ROLE_KEY`、`sb_secret_*`
- 任何用户的 JWT 或 access token

如果用户主动贴出来，Agent 应该提示「这段内容已经泄露，请轮换」，
并且**不要在后续回答里重复它**。

### 规则 6：策略输出必须是完整四件套

只要涉及 RLS，输出模板固定为：

```sql
alter table <t> enable row level security;
revoke all on <t> from anon, authenticated;
grant <最小集合> on <t> to authenticated;
-- select / insert / update / delete 四条策略，每条都带 to
```

少任何一条，就要显式说明「这里省略了 X，原因是 Y」。

### 规则 7：区分「授权问题」与「策略问题」

Agent 排查权限故障时，第一步必须分清错误层：

- 报 `42501` → 查 GRANT
- 返回空数组 → 查 POLICY
- 查到别人的数据 → 查 RLS 是否开启 + 视图 `security_invoker` + 授权宽度

### 规则 8：性能建议必须给量化方法

不要只说「加索引会更快」。给验证命令：

```sql
set local role authenticated;
set local request.jwt.claims to '{"role":"authenticated","sub":"<uuid>"}';
explain analyze select count(*) from <t>;
reset role;
```

### 规则 9：不猜上游行为，标注不确定

涉及上游版本差异（网关组件、默认权限、key 格式）时，
Agent 要**明确写出「以你环境里的文件为准」并给出核对命令**，
而不是给一个笃定的结论。这一条比前八条加起来都重要 ——
一个自信的错答案，比一句「请你确认」代价高得多。

### 规则 10：不越权执行

Agent **不执行**：生产库写入、`docker compose down -v`（会删数据卷）、
生产 `.env` 修改、批量密钥轮换。
这类命令只输出、不执行，并要求人工确认。
