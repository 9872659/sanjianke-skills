# 三剪客 · Python SQL 工具包与 ORM Skill

用一套代码在 Python 里连数据库、建模型、跑查询、管事务与连接池，换数据库时不用重写业务逻辑。

---

## 前置条件

- Python 3.7 及以上（2.0 一线的实际支持范围随版本推进，以官方安装文档为准）
- `pip` 可用
- 目标数据库的 DBAPI 驱动要单独安装，且 URL 里的驱动名与已装驱动一致
- 用异步用法时需装 `SQLAlchemy[asyncio]` 与对应异步驱动
- schema 迁移需另外安装 Alembic（不在本 Skill 范围）
- 不需要账号或 API Key；只连你自己有权访问的数据库

---

## 使用

```bash
pip install SQLAlchemy
pip install psycopg          # PostgreSQL 用；SQLite 无需额外驱动
python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

engine = create_engine("sqlite+pysqlite:///:memory:")

with Session(engine) as session:
    session.add_all([User(name="a"), User(name="b")])
    session.commit()

    stmt = select(User).order_by(User.id)
    print([u.name for u in session.scalars(stmt)])
```

`SKILL.md` 里有声明式模型、join 聚合、批量增删改、反射、连接池调优的完整用法与避坑表。

---

## 依赖

- 运行依赖：`sqlalchemy`
- 可选依赖：`SQLAlchemy[mypy]`（静态类型检查插件）、`SQLAlchemy[asyncio]`（`AsyncSession`）
- 数据库驱动（按需单独安装）：`psycopg` / `psycopg2-binary` / `pymysql` / `mysqlclient` / `asyncpg` / `aiosqlite` 等
- 迁移工具（可选，独立项目）：Alembic
- 纯 Python 实现，不依赖外部二进制
- 不需要账号、Key 或在线服务

---

## 安全

- 不内嵌任何密钥
- 数据库连接串含用户名与密码，请走环境变量或密钥管理服务，不要硬编码进代码或提交到仓库
- 服务端 SQL 一律用绑定参数（`text()` 的命名参数或表达式语言），不要用字符串拼接
- `create_all()` 会建表，`drop_all()` 会**删表**，`update` / `delete` 漏写 WHERE 会作用于全表——执行前确认目标库并做好备份
- 连接与会话必须用 `with` 上下文或显式 `close()` 释放，否则会耗尽连接池
- 生产环境连接池总量（进程数 ×（`pool_size` + `max_overflow`））不要超过数据库的 `max_connections`
- 数据库账号按最小权限授予，只读分析场景不要给写权限

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`sqlalchemy`
- 仓库：https://github.com/sqlalchemy/sqlalchemy

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
