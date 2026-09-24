# 表设计与 RLS 权限

**这份文件是本包的核心。** 表建错可以改，权限配错会泄露数据 ——
而且泄露时不报错：接口返回 200，行数对不上你也不会注意到，直到有人在别处看到别人的数据。

读法建议：先读完第一节（模型）与第二节（坑），然后**把第五节那份检查清单存下来**，
每次加表或改策略跑一遍。

---

## 一、权限是两层，不是一层

这是所有误解的源头。请求到达一张表之前，Postgres 做**两次**独立判断：

```
客户端请求
   │
   ▼
① GRANT（授权）：这个角色能不能对这张表做这个动作？
   └─ 不能 → 直接报错（错误码 42501），策略根本不会被求值
   ▼
② POLICY（策略）：这个动作能作用在哪些行上？
   └─ 策略等价于给每条 SQL 隐式加一个 WHERE
   ▼
返回结果（可能是一个空数组，也可能是别人的数据）
```

**两层的语义完全不同，缺一不可：**

- **只有策略、没有授权** → 请求直接失败，你以为是策略写错了，其实是没授权。
- **只有授权、没有策略** → 表上没开 RLS 的话，角色能读写全部行；开了 RLS 但没有任何策略，
  则默认全部拒绝（这是安全的默认值）。
- **加了策略并不会撤销已有的授权。** 这是最要命的一条：
  一张表你只写了「本人可读」的 select 策略，只要 `anon` 还留着 insert 授权，
  陌生人就能往里写数据。

### 角色映射

每个请求都会被映射成三个 Postgres 角色之一：

| 角色 | 来源 | 说明 |
|---|---|---|
| `anon` | 未登录请求 | 拿着 publishable / anon key 但没带用户 JWT |
| `authenticated` | 已登录请求 | 带了有效用户 JWT |
| `service_role` | 服务端 key | **绕过 RLS**，只能存在于服务端 |

策略里用 `to` 子句限定角色：

```sql
create policy "本人可读自己的订单"
on public.orders for select
to authenticated                     -- 显式限定，别省
using ( (select auth.uid()) = user_id );
```

**永远不要省 `to`**。不写 `to` 的策略对所有角色生效，
意味着 `anon` 也要走一遍完整的策略求值 —— 既浪费数据库算力，
又给「只靠 `auth.uid()` 不等于 null 来挡匿名用户」这种脆弱写法留下空间。

---

## 二、RLS 配置错误的七种典型形态

### 形态 1：新表忘了开 RLS（最常见的泄露源）

在默认权限较老的项目里，`public` schema 下新建的表会自动拿到
`select / insert / update / delete` 授权给 `anon`、`authenticated`、`service_role`。
函数则自动拿到 `execute`。

**结果**：表建好了、数据写进去了、接口也通了 —— 陌生人也通了。

```sql
-- 危险：建完表就走了
create table public.notes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  body text not null
);
-- 此时 public.notes 对 anon 是完全可读可写的
```

平台正在把默认权限改成「不自动发、要显式授权」，所以**同一份迁移在不同项目上表现可能不同**。
不要靠假设，跑检查清单。

### 形态 2：开了 RLS，但一种操作都没写策略

```sql
alter table public.notes enable row level security;
-- 然后就没有然后了
```

表是安全的（默认全拒），但**功能也是废的**，连你自己都读不出来。
排查时看到「接口不报错但永远返回空数组」，先确认是不是这种情况。

### 形态 3：只写 `using`，忘了 `with check`

这两个子句管的事情不一样：

| 子句 | 生效于 | 管什么 |
|---|---|---|
| `using` | `select` / `update` / `delete` | 哪些**已有行**能被看见或改动 |
| `with check` | `insert` / `update` | 写入的**新行**必须满足什么 |

```sql
-- 危险：update 只写了 using
create policy "本人可改订单"
on public.orders for update
to authenticated
using ( (select auth.uid()) = user_id );
-- 用户能改自己的行，但能把 user_id 改成别人的 —— 相当于把行送出去了
```

正确写法：

```sql
create policy "本人可改订单"
on public.orders for update
to authenticated
using ( (select auth.uid()) = user_id )
with check ( (select auth.uid()) = user_id );
```

`insert` 策略**必须**用 `with check`，写 `using` 是无效的。

### 形态 4：一张表只写了一条 `for all` 策略

```sql
create policy "本人可操作"
on public.orders for all
to authenticated
using ( (select auth.uid()) = user_id );
```

看起来简洁，但 `for all` 在 `insert` 时不会用 `using` 做检查，
而只会套用 `with check`。**四个操作分开写**。多写三行，省掉一次事故调查。

### 形态 5：视图绕过底层表的 RLS

视图默认以**视图所有者**的权限执行。如果所有者是能绕过 RLS 的角色，
那么一张视图就能把底层表的 RLS 整个绕开。

```sql
-- 让视图以调用者的权限执行
alter view public.my_orders set (security_invoker = on);
```

**规则**：任何暴露给接口的视图，都要显式设置 `security_invoker`。

### 形态 6：`security definer` 函数成为越权入口

策略里要跨表查询（比如「查一下这个用户是不是管理员」），
常见做法是用 `security definer` 函数来绕开被查表的 RLS。但：

- 函数内部若不固定 `search_path`，调用者可能通过构造 schema 劫持函数内部的表名解析
- 函数若放在**暴露 schema** 里，客户端可以直接通过接口调用它，
  拿到它返回的判断结果（甚至把结果当查询用）

```sql
-- 正确写法
create or replace function public.has_role(required_role text)
returns boolean
language sql
security definer
set search_path = ''            -- 必须固定，空字符串最严格
stable
as $$
  select exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = required_role
  );
$$;

revoke all on function public.has_role(text) from public, anon;
grant execute on function public.has_role(text) to authenticated;
```

**规则**：内部的 helper 函数放进**不暴露的 schema**；
必须暴露的函数一律固定 `search_path`，并显式收窄 execute 授权。

### 形态 7：策略里的连接方向写反

策略中用子查询去关联大表时，写法决定性能，也常常暴露建模问题：

```sql
-- 慢：对每一行都要去比对 join 条件
using ( (select auth.uid()) in (
  select user_id from public.team_members where team_members.team_id = teams.id
) )
```

```sql
-- 快：先把「属于我的 team_id 集合」算出来，再拿它去比对行
using ( id in ( select team_id from public.team_members where user_id = (select auth.uid()) ) )
```

方向是「**行里的列** 属于 **我的一批 id**」，不是「我的 id 出现在 **满足行条件的记录**里」。
如果 `in` 列表会长到上万项，说明模型该换了（比如换成一张物化的成员表）。

---

## 三、表设计规范

以下约定不是风格偏好，每一条都直接关系到权限能不能写干净。

### 1. 主键与时间戳

```sql
create table public.projects (
  id          uuid primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
```

- 主键用 `uuid`：策略里比对 `auth.uid()`（也是 uuid）不用转换。
- 时间一律 `timestamptz`，不要用 `timestamp`（时区问题会在跨区部署时爆发）。

### 2. 归属列必须有，且非空

```sql
owner_id uuid not null references auth.users(id) on delete cascade
```

- **有归属列，策略才有东西可比。** 没有归属列的表，要么不该暴露，要么需要成员表。
- 归属列尽量 `not null` + 外键，避免出现孤儿行（孤儿行在策略里可能匹配到异常逻辑）。
- **归属列必须建索引**，这是 RLS 性能的第一杠杆（见第六节）。

### 3. 多租户用成员表，不要用数组列

```sql
create table public.teams (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table public.team_members (
  team_id uuid not null references public.teams(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner','admin','member')),
  created_at timestamptz not null default now(),
  primary key (team_id, user_id)
);

create index team_members_user_id_idx on public.team_members (user_id);
```

- 成员关系**独立成表**：策略里能高效地取出「我的一批 team_id」，
  角色也能放在这里做细粒度控制。
- 用数组列（`member_ids uuid[]`）看起来简单，但策略会变成
  `(select auth.uid()) = any(member_ids)` —— 无法有效利用索引，
  且角色、加入时间这些元数据没地方放。

### 4. 枚举用 check 约束或独立类型，不要用自由文本

```sql
status text not null default 'draft' check (status in ('draft','published','archived'))
```

自由文本的 `status` 迟早会出现拼写不一致，然后写策略时你得猜有哪些值。

### 5. 软删要单独考虑策略

如果业务用 `deleted_at is not null` 表示已删，**策略里也要带上这个条件**：

```sql
create policy "本人可读未删除的项目"
on public.projects for select
to authenticated
using ( (select auth.uid()) = owner_id and deleted_at is null );
```

忘了这句，用户会看到自己「已删除」的数据 —— 属于功能 bug，但也常被当成权限问题来排查。

### 6. 暴露 schema 只放该暴露的东西

内部表（日志、临时队列、缓存镜像）放到**不在接口暴露列表里**的 schema。
默认只有 `public` 等少数 schema 通过接口暴露。

好处很直接：暴露面小，检查清单跑起来也快。

### 7. 一次迁移写完整

**建表、授权、开 RLS、写策略，必须在同一个迁移文件里。**

```sql
-- supabase/migrations/20260101000000_notes.sql
create table public.notes ( ... );

alter table public.notes enable row level security;
alter table public.notes force row level security;

revoke all on public.notes from anon, authenticated;
grant select, insert, update, delete on public.notes to authenticated;

create policy "本人可读" on public.notes for select to authenticated
  using ( (select auth.uid()) = user_id );
-- ...其余三条策略
```

分成两次迁移部署（先建表、后补策略）意味着**中间有一段时间表是裸的**。
生产上是几秒还是几小时，取决于你怎么发布的 —— 不值得赌。

---

## 四、完整的一遍：从建表到策略

以下是一个可以直接改字段就用的完整写法。

```sql
-- ============ 1. 建表 ============
create table public.notes (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  team_id    uuid references public.teams(id) on delete cascade,
  title      text not null check (length(title) between 1 and 200),
  body       text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============ 2. 索引（策略要用到的列）============
create index notes_user_id_idx on public.notes (user_id);
create index notes_team_id_idx on public.notes (team_id);

-- ============ 3. 开 RLS ============
alter table public.notes enable row level security;
alter table public.notes force  row level security;   -- 连表所有者也要走策略

-- ============ 4. 授权：最小化，先清空再按需给 ============
revoke all on public.notes from anon, authenticated;
grant select, insert, update, delete on public.notes to authenticated;
-- 注意：没有给 anon 任何授权。匿名用户不该碰这张表。

-- ============ 5. 策略：四种操作分开写 ============
create policy "notes_select_own"
on public.notes for select
to authenticated
using ( (select auth.uid()) = user_id );

create policy "notes_insert_own"
on public.notes for insert
to authenticated
with check ( (select auth.uid()) = user_id );

create policy "notes_update_own"
on public.notes for update
to authenticated
using ( (select auth.uid()) = user_id )
with check ( (select auth.uid()) = user_id );

create policy "notes_delete_own"
on public.notes for delete
to authenticated
using ( (select auth.uid()) = user_id );

-- ============ 6. updated_at 自动维护 ============
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger notes_touch_updated_at
before update on public.notes
for each row execute function public.touch_updated_at();
```

带团队可见性的版本（读：本人或本团队；写：仅本人）：

```sql
create policy "notes_select_own_or_team"
on public.notes for select
to authenticated
using (
  (select auth.uid()) = user_id
  or team_id in (
    select tm.team_id from public.team_members tm
    where tm.user_id = (select auth.uid())
  )
);
```

---

## 五、漏权检查清单（可直接粘贴执行）

**每次加表、改策略、上线前，把这一整段跑一遍。** 全部 SQL 只读，不改数据。

### 第 1 条：暴露 schema 里有哪些表没开 RLS —— 必须为空

```sql
select n.nspname as schema_name, c.relname as table_name
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'r'
  and n.nspname = 'public'          -- 换成你的暴露 schema
  and c.relrowsecurity = false
order by 1, 2;
```

**结果不为空 = 有泄露风险，立刻停下来处理。**

### 第 2 条：哪些表开了 RLS 但一条策略都没有

```sql
select n.nspname, c.relname,
       c.relrowsecurity as rls_enabled,
       c.relforcerowsecurity as rls_forced
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'r'
  and n.nspname = 'public'
  and c.relrowsecurity = true
  and not exists (select 1 from pg_policy p where p.polrelid = c.oid)
order by 1, 2;
```

这些表默认全拒 —— 安全但功能不通。要么补策略，要么确认它本就不该被访问。

### 第 3 条：`anon` / `authenticated` 到底拿到了哪些授权

```sql
select table_schema, table_name, grantee, string_agg(privilege_type, ', ' order by privilege_type) as privileges
from information_schema.role_table_grants
where grantee in ('anon', 'authenticated')
  and table_schema = 'public'
group by 1, 2, 3
order by 1, 2, 3;
```

**逐行确认这是不是你要的。** 任何一行出现 `anon` + `INSERT/UPDATE/DELETE`，
都要能说出「为什么匿名用户可以写」。

### 第 4 条：逐表列出策略，检查四件事

```sql
select schemaname, tablename, policyname, cmd,
       roles, qual as using_expr, with_check
from pg_policies
where schemaname = 'public'
order by tablename, cmd, policyname;
```

对每一行问：

- `roles` 是 `{public}` 吗？→ 没写 `to`，改掉
- `cmd` 是 `ALL` 吗？→ 拆成四条
- `cmd` 是 `INSERT` 且 `using_expr` 有值、`with_check` 为空？→ **这条策略不生效，立刻修**
- `qual` 或 `with_check` 里有 `true` 吗？→ 确认这是有意为之

### 第 5 条：策略引用到的列有没有索引

```sql
-- 把上一句查出来的策略表达式人工看一遍，取出用到的列，然后：
select schemaname, tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public'
order by tablename;
```

对照检查：策略里出现的每一列（尤其是 `user_id`、`team_id`、`owner_id`），
是否都有索引。没有就补上。

### 第 6 条：暴露给接口的视图有没有 `security_invoker`

```sql
select n.nspname as schema_name,
       c.relname as view_name,
       coalesce(array_to_string(c.reloptions, ', '), '(none)') as options
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'v'
  and n.nspname = 'public'
order by 1, 2;
```

`options` 里没有 `security_invoker=on` 的视图，都要复核一遍。

### 第 7 条：`security definer` 函数有没有固定 `search_path`

```sql
select n.nspname as schema_name,
       p.proname as function_name,
       p.prosecdef as security_definer,
       coalesce(array_to_string(p.proconfig, ', '), '(none)') as config
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where p.prosecdef = true
  and n.nspname not in ('pg_catalog', 'information_schema')
order by 1, 2;
```

`security_definer = true` 且 `config` 为 `(none)` 的行 —— **每一行都要处理**。

### 第 8 条：真正模拟一次匿名请求（最有效的一步）

静态检查会漏，实跑不会。**在本地或预发环境**模拟匿名身份：

```sql
set local role anon;
set local request.jwt.claims to '{"role":"anon"}';

select count(*) from public.notes;      -- 期望：要么 42501，要么 0
reset role;
```

```sql
-- 模拟某个具体用户，验证只能看到自己的行
begin;
set local role authenticated;
set local request.jwt.claims to
  '{"role":"authenticated","sub":"00000000-0000-0000-0000-000000000001"}';
select count(*) from public.notes;
reset role;
rollback;
```

**这一步在本地/预发做，不要在生产库上切角色。**

### 第 9 条：静态检查与测试

```bash
npx supabase db lint       # 看 rls_disabled_in_public 与函数 search_path 相关的告警
npx supabase test db       # 用 pgTAP 写策略用例，跑一遍
```

策略测试值得写，因为它是**回归防线**：以后有人改了策略，测试会拦住。

---

## 六、RLS 性能：十万行级别差上百倍

策略等于给每条查询加一个 `WHERE`，所以它天然会影响性能。
影响能有多大？官方给出的实测对比（10 万行表）：

| 写法 | 优化前 | 优化后 |
|---|---|---|
| `auth.uid() = user_id` | 171 ms | < 0.1 ms（加了索引） |
| `auth.uid() = user_id` | 179 ms | 9 ms（包上 `(select ...)`） |
| `is_admin()`（表关联） | 11,000 ms | 7 ms |
| `is_admin() or auth.uid() = user_id` | 11,000 ms | 10 ms |
| `has_role() = role` | 178,000 ms | 12 ms |
| 无 `to` 策略（anon 访问） | 170 ms | < 0.1 ms（加 `to authenticated`） |

六条优化手法，按性价比排序：

### 1. 给策略列建索引（收益最大、最简单）

```sql
create index if not exists notes_user_id_idx on public.notes (user_id);
```

只要策略里出现 `= auth.uid()` 这类按列的比对，那一列就该有索引。
**这是第一条要做的，别的都排在它后面。**

### 2. 把函数包进 `(select ...)`

```sql
-- 慢：每一行都调用一次
using ( auth.uid() = user_id )

-- 快：优化器把它当成 initPlan，只算一次
using ( (select auth.uid()) = user_id )
```

**前提**：这个函数的结果**不能随行变化**。`auth.uid()`、`auth.jwt()`、
`is_admin()`、`has_role()` 这类「本次请求内固定」的值都适用。

如果函数带**行相关的入参**，就没法这么包，只能实测。

### 3. 不要指望 RLS 做过滤

策略是**安全边界**，不是查询优化器。列表页该带的过滤条件还是要带：

```js
// 只靠 RLS：扫全表再过滤
.from('notes').select()

// 加上过滤：直接走索引
.from('notes').select().eq('user_id', userId)
```

两句话记住：**RLS 保证你拿不到别人的行；过滤条件保证你拿得快。**

### 4. 跨表判断用 `security definer` 函数

策略里直接 `exists (select ... from 另一张表)` 会连带触发那张表的 RLS。
把逻辑封进 `security definer` 函数里，既绕开了额外策略求值，也能被 `(select ...)` 缓存：

```sql
using ( (select public.has_role('admin')) or (select auth.uid()) = user_id )
```

### 5. 优化连接方向

见第二节「形态 7」。原则是**先算出「我的一批 id」，再拿它去比行上的列**。

### 6. 显式 `to authenticated`

```sql
-- 慢：anon 用户也要完整求值一遍策略
create policy "p" on public.notes for select using ( (select auth.uid()) = user_id );

-- 快：匿名用户在角色检查阶段就被拦掉
create policy "p" on public.notes for select to authenticated using ( (select auth.uid()) = user_id );
```

### 怎么量化

```sql
-- 模拟身份，测量执行时间
set local role authenticated;
set local request.jwt.claims to '{"role":"authenticated","sub":"<user-uuid>"}';

explain analyze select count(*) from public.notes;

reset role;
```

对比「开 RLS」与「关 RLS」的执行时间：

- 两者接近 → 慢在查询本身或索引，不在策略
- 差距巨大 → 按上面六条逐个试

PostgREST 还提供了 `explain` 能力（需开启后重载配置，**只在非生产环境用**）：

```sql
alter role authenticator set pgrst.db_plan_enabled to true;
notify pgrst, 'reload config';
```

```js
const { data } = await supabase
  .from('notes').select('*').eq('id', 1)
  .explain({ analyze: true })
```

### 索引没效果怎么办

如果加了索引用处不大，**把它删掉** —— 无用索引会拖慢写入，还要占空间。
只有确实改善了 RLS 性能、或本身作为过滤索引有用时，才留着。

---

## 七、`service_role` 与 Agent 访问

这是本包被问得最多的一个问题：**「我要让 Agent / 定时任务访问数据库，能不能给它 service_role key？」**

先看清代价：`service_role`（以及新式的 `sb_secret_*`）**完全绕过 RLS**。
给它，就等于给了整库读写权限 —— 包括你的用户表、别人家的数据、所有历史记录。

判断口径：

| 场景 | 推荐做法 |
|---|---|
| 服务端后台任务，只需访问特定几张表 | **不要用 service_role。** 建一个专用角色，只授权那几张表 |
| 定时统计、跑批 | 同上，或走 `security definer` 函数 + 精确 `execute` 授权 |
| 管理后台（需要按管理员身份操作） | 用用户 JWT + `is_admin()` 类策略，**不要降级成 service_role** |
| 数据迁移 / 运维脚本 | 用 service_role，但只在受控环境、不常驻、不写进代码 |

给 Agent 建专用角色的写法：

```sql
-- 1. 建角色
create role agent_reader nologin;

-- 2. 只给需要的表的只读授权（注意：这个角色不通过接口暴露，所以不用管 RLS）
grant usage on schema public to agent_reader;
grant select on public.notes, public.teams to agent_reader;

-- 3. 若 Agent 通过接口访问（会走 RLS），则要给它策略
--    策略里不能用 auth.uid() 判断，改用角色判断：
create policy "agent 可读"
on public.notes for select
to agent_reader
using ( true );
```

**一条铁律**：任何 key 在写进 Agent 的提示词、配置文件或日志之前，
先问「如果这段内容被完整贴到公网上，损失有多大」。答案不该是「整库」。
