---
name: sanjianke-sqlalchemy
slug: sanjianke-sqlalchemy
displayName: 三剪客 · Python SQL 工具包与 ORM
description: "SQLAlchemy：Python 的 SQL 工具包与 ORM。既能用 Core 表达式语言拼 SQL，也能用声明式模型把表映射成对象，自带连接池、事务与多数据库方言。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "SQLAlchemy 2.x 的安装、引擎与会话配置、声明式模型、select() 查询、批量写入、反射与连接池调优，以及延迟加载、提交后过期、会话跨线程、分页误用等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 数据库

---

# 三剪客 · Python SQL 工具包与 ORM

写 Python 存数据时最烦的不是 SQL 本身，而是"连一个库要写多少样板"：建连接、管事务、防注入、换数据库要重写、连接用完忘了关。SQLAlchemy 就是把这些收进一层：你描述"要什么样的查询"，它负责渲染成目标数据库的 SQL 并在连接池上执行。

它其实有两层，这点决定了你会不会用错。**Core** 是 SQL 表达式语言加 DBAPI 交互层，不涉及对象映射；**ORM** 建在 Core 之上，用声明式类把表映射成对象，靠 identity map + unit of work 自动把 Python 里的改动同步成 SQL。两边可以混用。

**上游项目**：`sqlalchemy`　**仓库**：https://github.com/sqlalchemy/sqlalchemy

> 版本实测：本 Skill 的示例在 SQLAlchemy 2.0.52 / Python 3.11.9 上跑通。2.0 与 1.4 的查询写法差别很大，网上大量 1.x 的 `session.query(...)` 老例子仍然能跑但属于遗留 API，新代码请统一用 2.0 风格。

## 什么时候用 / 不用

**用它**：

- "我要在 Python 里连数据库、建表、增删改查，但不想每个项目重写一遍连接和事务。"——`create_engine` + `Session` 一次配好，业务代码只写查询。
- "同一套代码要能跑 MySQL 开发、PostgreSQL 生产，SQL 方言不一样。"——换 URL 里的方言前缀即可，SQL 由表达式语言渲染。
- "想用对象的方式改数据，不想手写 INSERT/UPDATE。"——声明式模型 `Mapped[...]` + `mapped_column`，改属性后 `commit()` 自动落库（工作单元模式）。
- "这条 SQL 需要 join、子查询、关联，但我又要参数化防注入。"——`select()` 表达式语言把 SQL 结构显式暴露出来，绑定参数自动处理。
- "连接要复用、要限并发、要断线重连。"——`create_engine` 自带连接池（`pool_size`、`max_overflow`、`pool_pre_ping`）。
- "库里已经有一堆表，我不想手写模型类。"——反射（`MetaData.reflect` / `autoload_with`）一步把表结构读成 Python 元数据。

**不要用它**：

- **只是 CSV / Parquet 文件做分析**——那是 pandas、polars、DuckDB 的活，为了读文件引入 ORM 只会更重。
- **一次性脚本跑一句 SQL 就完事**——直接用驱动（`sqlite3` / `psycopg` / `pymysql`）更短，不必包一层。
- **要做大批量 ETL 的高速写入**——ORM 逐对象 flush 有开销。要么用 Core 的 `insert()` 配合批量执行，要么用数据库原生批量装载（各库的 COPY / LOAD DATA）。
- **想要"自动建好数据模型、自动迁移"**——SQLAlchemy 不管数据迁移版本管理，那是 Alembic 的职责；`create_all()` 只建不存在的表，不会改已有表结构。
- **想要完整 Web 框架的 ORM 集成**——Django 自带 ORM 与迁移，如果整个项目在 Django 里，没必要混搭。
- **想要 Python 对象图的复杂关系自动级联到数据库**——SQLAlchemy 有意不做"隐式魔法"，级联行为要自己在 `relationship()` 上声明。

## 安装

要求 Python 3.7 及以上（2.0 一线的实际支持范围随版本推进，以官方安装文档为准）。纯 Python 实现，无编译依赖。

```bash
# 只装 SQLAlchemy 本体
pip install SQLAlchemy

# 需要 mypy 插件做静态检查时
pip install "SQLAlchemy[mypy]"

# 用官方 asyncio 扩展（AsyncSession，额外带 greenlet 依赖）
pip install "SQLAlchemy[asyncio]"
```

数据库驱动要单独装，SQLAlchemy 只带 SQLite 的标准库驱动（`sqlite+pysqlite`）：

```bash
# PostgreSQL（psycopg3 与 psycopg2 二选一，URL 前缀不同）
pip install psycopg            # URL: postgresql+psycopg://
pip install psycopg2-binary    # URL: postgresql+psycopg2://

# MySQL / MariaDB
pip install pymysql            # URL: mysql+pymysql://
pip install mysqlclient        # URL: mysql+mysqldb://

# 异步驱动（配合 AsyncSession）
pip install asyncpg            # URL: postgresql+asyncpg://
pip install aiosqlite          # URL: sqlite+aiosqlite://
```

验证安装（能打印出实际版本号即成功）：

```bash
python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

装完想确认方言与驱动解析正确：

```bash
python -c "
from sqlalchemy import create_engine
e = create_engine('sqlite://')
print(e.dialect.name, e.dialect.driver)
"
```

## 常用操作

**1. 建引擎并验证连通性（一切从这里开始）**

```python
from sqlalchemy import create_engine, text

engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
with engine.connect() as conn:
    print(conn.execute(text("select 1")).scalar())   # 1
```

URL 形状是 `方言+驱动://用户名:密码@主机:端口/库名`。密码里有 `@`、`/` 等字符要 URL 编码，不要直接拼字符串。

**2. 声明式模型 + 建表**

```python
from typing import List
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user_account"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    addresses: Mapped[List["Address"]] = relationship(back_populates="user")


class Address(Base):
    __tablename__ = "address"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    user: Mapped["User"] = relationship(back_populates="addresses")


Base.metadata.create_all(engine)
```

`Mapped[str]` 里的类型标注会被用来推断列类型（`String`、`Integer` 等），不需要每个字段都显式写。

**3. 会话：写入、查询、提交**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

with Session(engine) as session:
    session.add_all([
        User(name="spongebob", addresses=[Address(email="a@b.c")]),
        User(name="patrick"),
    ])
    session.commit()

    stmt = select(User).where(User.name.in_(["spongebob", "patrick"])).order_by(User.id)
    for user in session.scalars(stmt):
        print(user.id, user.name)
```

`session.scalars()` 拿单个实体，`session.execute()` 拿 Row 元组。更省事的写法是 `with Session.begin() as session:`，出错自动回滚。

**4. 聚合、join、分组（直接对应 SQL 结构）**

```python
from sqlalchemy import func, select

stmt = (
    select(User.name, func.count(Address.id))
    .join(Address, isouter=True)
    .group_by(User.name)
)
print(session.execute(stmt).all())   # [('patrick', 0), ('spongebob', 1)]
```

`isouter=True` 是 LEFT OUTER JOIN，`full=True` 是 FULL OUTER JOIN（不是所有数据库都支持）。

**5. 按主键取对象、批量更新删除**

```python
from sqlalchemy import delete, update

user = session.get(User, 1)                  # 先查 identity map，没有再发 SQL

session.execute(update(User).where(User.name == "patrick").values(name="pat"))
session.execute(delete(Address).where(Address.email == "a@b.c"))
session.commit()
```

`session.get()` 只能按主键；按其它字段筛还是用 `select()`。

**6. 反射已有库的表结构**

```python
from sqlalchemy import MetaData, create_engine, select

engine = create_engine("postgresql+psycopg://<用户>:<密码>@localhost/<库名>")
metadata = MetaData()
metadata.reflect(bind=engine, only=["orders"])        # 只反射需要的表，别全库拉

orders = metadata.tables["orders"]
with engine.connect() as conn:
    for row in conn.execute(select(orders).limit(5)):
        print(row)
```

全库反射在表多的库上会很慢，尽量用 `only=` 限定。

**7. 连接池参数（生产环境重点）**

```python
engine = create_engine(
    "postgresql+psycopg://<用户>:<密码>@localhost/<库名>",
    pool_size=10,          # 常驻连接数
    max_overflow=20,       # 高峰期额外可开的连接
    pool_pre_ping=True,    # 取连接前先探活，解决"服务器已断开"类报错
    pool_recycle=1800,     # 超过 1800 秒的连接回收重建
)
```

Web 服务进程数 ×（`pool_size` + `max_overflow`）不能超过数据库的 `max_connections`，这是最常见的打满连接原因。SQLite 内存库要用 `StaticPool` 才能跨连接共享同一份数据。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `DetachedInstanceError: Instance <User> is not bound to a Session` | 会话关掉（`with` 块结束）后对象就 detached 了，但某个属性还没加载，访问时想回数据库取却已经没有会话 | 在会话内把要用的数据读完（已加载的字段可以直接用），或者取出后立刻转成 dict / dataclass 再往外传；渲染模板的场景常用 `selectinload()` 预加载关联集合 |
| `commit()` 之后访问对象属性又发了一次 SQL，或者对象像"变空了" | 默认 `expire_on_commit=True`，提交后所有对象被标记过期，下次访问属性会重新查询 | 明确知道会立即复用数据时，用 `Session(engine, expire_on_commit=False)`；但要注意这时对象里的值可能已经落后于数据库，需要时显式 `session.refresh(obj)` |
| 生成了一条又一条 SQL（N+1），几百个对象发了几百条查询 | 关联关系默认是**延迟加载**：访问 `user.addresses` 才去查 | 不要循环里逐个访问，改成 `select(User).options(selectinload(User.addresses))`（发少量 IN 查询）或 `joinedload(User.addresses)`（发 JOIN，集合大时结果集膨胀） |
| 多线程下偶发报错、数据串号 | `Session` **不是线程安全的**，也不是协程安全的；而 `Engine` 和 `sessionmaker` 是线程安全的工厂，可以在模块级别共享 | Engine / sessionmaker 放模块级；Session 每个请求或每个工作单元新建；异步场景用 `AsyncSession`，同样一个任务一个 |
| `This Session's transaction has been rolled back due to a previous exception during flush` | flush 中途失败后，会话的事务已经是失败状态，继续在里面跑查询就会报这个 | 捕获异常后先 `session.rollback()`（或用 `with Session.begin():` 让它自动回滚），再重新开始一个事务；不要吞掉异常继续用同一个会话 |
| 出现 `QueuePool limit of size ... overflow ... connection timed out` | 连接池被耗尽：大多是会话或连接没关（异常路径漏了 `close()`），或者 `pool_size` 相对并发太小 | 一律用 `with Session(engine) as s:` / `with engine.connect() as c:` 上下文管理；先查有没有连接泄漏，再考虑调大池子 |
| 报 `'Session' object has no attribute 'query'` 之类旧写法失效 | 用的是 2.0 环境，但代码是 1.x 的 `session.query()` 风格 | 2.0 标准写法是 `select()` 配合 `session.scalars()` / `execute()`；`Query` 仍可用但属于遗留 API，新代码别再用 |
| 写入带 `%` 的字符串报参数错误，或拼 SQL 出安全问题 | 用了 f-string 拼 SQL | 永远不要拼字符串：`text()` 里用命名绑定参数（`text("... where name = :n")` 配合参数字典），表达式语言本身就更安全 |
| `InvalidRequestError: A transaction is already begun on this Session` | 用了 `autobegin=False`，又在没结束上一个事务时直接调用 `begin()` | 用默认的 autobegin，或者确保每次 `begin()` 前上一个事务已 commit / rollback |
| SQLite 内存库换了一个连接就"表不存在" | `:memory:` 库默认每连接一份独立数据，连接池换连接等于换库 | 用 `create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})`，或直接落到临时文件库 |
| 大结果集 `.all()` 把内存吃光 | `.all()` 一次性把全部行物化到内存 | 用 `for row in session.scalars(stmt):` 流式迭代；需要分批时用 `yield_per`，或改用 Core 层 `conn.execution_options(stream_results=True)` |
| 多进程 / 多 worker 下报 `Table 'x' is already defined for this MetaData` | 同一个 `MetaData` 里重复登记了同名表（常见于热重载把模块执行了两遍） | 保证模型模块只被导入一次；不要在多处对同一个 Base 重复声明同名 `__tablename__` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视情况 | 只有连远程数据库时才需要；用本地 SQLite 文件时全程不联网。装驱动时 pip 需要联网 |
| 读取文件 | 视情况 | SQLite 这类嵌入式库会读写本地数据库文件 |
| 写入文件 | 视情况 | 同上。连远程库时不落本地文件 |
| 凭证 | 是 | 数据库连接串含用户名、密码，可能还有 SSL 证书路径。**不要硬编码进代码或提交到仓库**，用环境变量、密钥管理服务或各库自带的密码文件（如 `~/.pgpass`） |
| 子进程 / 后台常驻 | 否 | 纯库调用，不启动后台服务。连接池在进程内，进程退出即释放 |
| 执行写操作 | 视情况 | ORM/Core 能发出 `update` / `delete`；`create_all()` 会建表，`drop_all()` 会**删表**，执行前必须确认目标库和备份 |

## 触发场景

- "用 Python 连一下这个数据库，把表结构拉出来看看。"
- "帮我写一段 SQLAlchemy 代码，按部门分组统计人数。"
- "这套代码要从 MySQL 迁到 PostgreSQL，SQL 部分怎么改。"
- "库里已经有表了，直接生成模型类。"
- "我这个服务老是报连接池超时，帮我看看配置。"
- "为什么我 commit 之后访问对象属性又发了一条 SQL？"
- "这个接口发了 300 条 SQL，帮我查一下哪里 N+1 了。"

## 能力边界

**覆盖**：

- **Core 层**：SQL 表达式语言（`select` / `insert` / `update` / `delete`，join、子查询、关联子查询、CTE、集合运算）、类型系统与自定义类型、`MetaData` 与 DDL 生成
- **ORM 层**：声明式映射（`DeclarativeBase` / `Mapped` / `mapped_column`）、`relationship()` 与各种加载策略（延迟加载、`joinedload`、`selectinload`、`subqueryload`、`raiseload`）、identity map、工作单元、`Session` 生命周期与嵌套事务
- **连接与事务**：`Engine`、连接池（`QueuePool` / `StaticPool` / `NullPool`）、`begin()` 事务块、SAVEPOINT
- **多数据库**：统一的方言层，覆盖 PostgreSQL、MySQL / MariaDB、SQLite、Oracle、SQL Server 等主流库；异步驱动通过 `AsyncSession` 支持
- **数据库结构**：反射把已有表读成 Python 元数据，再反向生成 DDL
- 与 Alembic 配合做 schema 迁移（迁移工具本身不在这个包里）

**不覆盖**：

- **数据模型迁移版本管理**——只建不改。`create_all()` 不会给已存在的表加列，改表要走 Alembic 之类的迁移工具
- **连接池之外的中间件**——不做读写分离、分库分表、SQL 审计、慢查询统计
- **结果集分析**——没有 DataFrame、没有分组透视、没有画图。要做分析请把结果交给 pandas / polars
- **缓存层**——identity map 只是单次会话内的对象去重，不是跨进程缓存
- **自动重试业务逻辑**——连接层有 `pool_pre_ping` 这类探活，但"写失败了重试"这种语义要自己在应用层做
- **CSV / Excel / JSON 文件读取**——没有文件格式解析能力
- **SQL 执行计划优化**——写错了由数据库报错，它不会替你优化执行计划

## 依赖条件

- Python 3.7+（2.0 一线的实际支持范围随版本推进，以官方安装文档为准）
- `pip install SQLAlchemy`；纯 Python，无编译步骤
- 目标数据库的 DBAPI 驱动必须单独安装（`psycopg` / `psycopg2-binary` / `pymysql` / `mysqlclient` / `asyncpg` / `aiosqlite` 等），URL 里的驱动名要和已装的驱动一致
- 异步用法需要 `SQLAlchemy[asyncio]` 与对应的异步驱动
- schema 迁移需要另外安装 Alembic
- 不需要账号或 API Key；只连你自己有权访问的数据库

## 已知限制

1. `Session` 不是线程安全的，也不是协程安全的；跨线程 / 跨任务复用是未定义行为。
2. 默认 `expire_on_commit=True`，提交后对象过期，访问属性会触发新的查询——服务端渲染与缓存序列化场景经常踩到。
3. 关联默认延迟加载，N+1 是默认行为而不是 bug，必须显式配置加载策略。
4. 只建不改：`create_all()` 不会修改已存在的表结构，schema 演进要外部迁移工具。
5. 反射全库在表数量大时很慢，且拿不到注释、分区等全部数据库特性。
6. 不同数据库方言能力不一致（例如 FULL OUTER JOIN、部分 DDL）；表达式语言会尽力渲染，个别语法要落到 `text()` 里写原生 SQL。
7. 版本之间（尤其 1.4 与 2.0）API 风格差异明显，抄网上的例子前先确认它对应哪个大版本。

## 自检清单

执行前：

- [ ] 连接串里的方言与驱动名和已安装的驱动一致（`postgresql+psycopg` 与 `postgresql+psycopg2` 是两个东西）
- [ ] 密码等敏感信息来自环境变量或密钥服务，不在代码和命令历史里
- [ ] 每个会话都有 `with` 上下文或明确的 `close()`，异常路径也不会漏
- [ ] 写操作前确认目标库、是否要备份、有没有 WHERE 条件（漏 WHERE 会全表更新 / 删除）
- [ ] `drop_all()` / `delete()` 这类破坏性调用执行前二次确认
- [ ] 生产环境的池参数与数据库 `max_connections`、应用进程数一起算过

执行后：

- [ ] 确认事务已提交（读连接、看影响行数），没有留下挂起事务
- [ ] 如果开了 `echo=True` 或日志，检查生成的 SQL 数量是否符合预期（重点看有没有 N+1）
- [ ] 检查返回对象是否会被带出会话作用域使用（会不会 detached）
- [ ] 大批量操作后确认内存占用没有异常增长（避免 `.all()` 物化大结果集）

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/sqlalchemy/sqlalchemy | 上游仓库（安装与完整文档以它为准） |
| https://docs.sqlalchemy.org/en/20/orm/quickstart.html | 官方 ORM 快速上手 |
| https://docs.sqlalchemy.org/en/20/orm/session_basics.html | 官方 Session 基础：生命周期、flush、autobegin、expire |
| https://docs.sqlalchemy.org/en/20/orm/queryguide/index.html | 官方 ORM 查询指南（2.0 风格） |

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
