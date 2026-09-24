---
name: sanjianke-duckdb
slug: sanjianke-duckdb
displayName: 三剪客 · 单机分析型 SQL 引擎
description: "duckdb：把 CSV / Parquet / 多份表格文件当数据库查，用 SQL 做单机分析、清洗与导出，不用起服务、不用导入。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "duckdb：单机分析型 SQL 引擎。把 CSV / Parquet / 多份表格文件当数据库查，用 SQL 做单机分析、清洗与导出，不用起服务、不用导入。含安装、常用命令、6 条常见坑与能力边界。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析

---

# 三剪客 · 单机分析型 SQL 引擎

手里有一堆 CSV、Parquet、Excel 导出的表格，想用 SQL 直接查、直接聚合、直接导成另一种格式，但又不想装数据库、不想建表、不想起服务——DuckDB 就是为这件事准备的。它把整个分析引擎塞进一个进程，文件路径写在 `FROM` 后面就能当表用。

它的定位是「分析的 SQLite」：单进程、列式存储、向量化执行，擅长一次扫描几个 GB 的宽表做聚合；不适合当网站后端那种多人并发的业务库。

**上游项目**：`duckdb`　**仓库**：https://github.com/duckdb/duckdb

> 本文命令取自上游仓库 README 与官方文档站，版本号取自实测环境（Python 包 1.5.5）。参数随版本变化时，以官方文档与 `duckdb -help` 为准。

## 什么时候用 / 不用

**用它**：

1. 「把这个 2GB 的 CSV 按省份聚合一下，再导成 Parquet」——不需要建库，把文件路径当表名查就行。
2. 「这几个 Parquet 分片我要 join 起来对账」——多文件、不同格式可以放在同一条 SQL 里互相 join。
3. 「我想在 Python 里用 SQL 处理 pandas / polars 的 DataFrame」——它可以直接把内存里的表注册成视图来查，省掉一堆 `groupby` 链式调用。
4. 「单机跑一次性的清洗 / 去重 / 字段重命名，跑完就扔」——不需要部署，不需要维护 schema，脚本里几行就结束。
5. 「同一份数据我要反复换角度切」——SQL 的交互式探索比反复改 `for` 循环快得多，改一行 `WHERE` 就能换个口径。

**不要用它**：

1. 需要多人并发写入的业务库（订单、账务、后台 CRUD）——它是单写者的分析引擎，不是 OLTP 数据库。
2. 单表只有几百上千行、逻辑就是过滤加排序——直接 pandas / polars 更省事，引入 SQL 层反而多一层心智负担。
3. 需要跨机器分布式计算（几十 TB 级集群任务）——那是 Spark / 数仓的活，DuckDB 在一台机器上跑。
4. 需要高频小事务逐条写入（每来一条消息就 `INSERT` 一行）——分析引擎的写入模型不匹配这种负载。
5. 只想把文件转个格式、不做任何筛选聚合——`xsv`、`csvkit` 或 pandas 一行搞定，不必上 SQL 引擎。

## 安装

DuckDB 有两种用法，按需要选一种或都装。官方安装页：https://duckdb.org/install/

**方式一：命令行客户端（CLI）**

CLI 是一个无依赖的单文件可执行程序，官方为 Windows / macOS / Linux 预编译了稳定版与 nightly 版。下载后解压，放到任意目录，在该目录下执行即可（PowerShell 或 POSIX shell 里要写 `./duckdb`）：

```bash
./duckdb
```

关于各平台的确切下载方式与包管理器命令，以 https://duckdb.org/install/ 的 CLI 页签为准。

**方式二：Python 包（本文实测路径）**

```bash
pip install duckdb
```

也支持 conda：`conda install python-duckdb -c conda-forge`。

实测环境：Python 3.11.9 + `duckdb` 1.5.5，Windows 下安装与以下所有示例均可用。官方要求 Python 3.9 或更新。

**方式三：其它语言绑定**

官方还提供 R、Java、Node.js、Rust、Go、C/C++、Wasm 等客户端，安装方式见官方文档的 Client APIs 章节。

> 注意：`pip install duckdb` 装的是 Python 包，**它不等于 CLI**。实测 `python -m duckdb` 会直接报 `No module named duckdb.__main__`。要命令行就得单独下载 CLI 可执行文件。

## 常用操作

**1. 文件路径直接当表查（最核心的用法）**

```sql
SELECT * FROM 'myfile.csv';
SELECT * FROM 'myfile.parquet';
```

不需要 `CREATE TABLE`，不需要导入步骤，这是官方 README 给出的入门方式。

**2. 打开一个持久化数据库文件并做聚合**

```bash
duckdb my_database.duckdb -c "SELECT count(*) FROM events;"
```

`-c COMMAND` 表示「执行这条命令然后退出」，适合放进脚本和流水线。不带文件名参数时打开的是临时内存库，退出即丢。

**3. 把 CSV 转成 Parquet，或按条件导出**

```bash
duckdb -c "COPY (SELECT * FROM 'in.csv' WHERE amount > 0) TO 'out.parquet' (FORMAT PARQUET)"
```

官方 COPY 文档给出的同类写法还有 `(FORMAT csv, DELIMITER '|', HEADER)` 与 `(COMPRESSION zstd)`，完整选项见 https://duckdb.org/docs/current/sql/statements/copy 。

**4. Python 里用 SQL 查内存表 / 文件，不经过 pandas**

```python
import duckdb

con = duckdb.connect()                      # 内存库
con.execute("CREATE TABLE t AS SELECT * FROM (VALUES (1,'a'),(2,'b')) AS v(id,name)")
print(con.sql("SELECT * FROM t WHERE id > 1").fetchall())   # [(2, 'b')]
print(con.sql("SELECT version()").fetchall())               # [('v1.5.5',)]
print(con.sql("DESCRIBE t").fetchall())
```

`.fetchall()` 走的是 DuckDB 自己的结果对象，**不需要** pandas 或 pyarrow。

**5. 查看与安装扩展（读 Excel、连远端等能力都在扩展里）**

```python
print(con.sql("SELECT extension_name, installed, loaded FROM duckdb_extensions() LIMIT 3").fetchall())
```

```sql
INSTALL excel;
LOAD excel;
```

实测 `installed` / `loaded` 都是布尔值，可以先用它确认扩展到底装上没有。扩展的默认行为与离线安装方式以官方 Extensions 文档为准。

**6. 命令行里换输出格式，方便接管道**

```bash
duckdb -csv -c "SELECT * FROM 'myfile.csv' LIMIT 10" > sample.csv
duckdb -json -c "SELECT 1 AS a"
```

官方文档列出的输出模式参数还有 `-ascii`、`-box`、`-column`、`-line`、`-list`、`-markdown`、`-table`、`-html`、`-quote`，以及 `-header` / `-noheader` 控制表头。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `Invalid Input Error: 'pandas' is required for this operation but it was not installed` | 调了 `.df()` / `fetchdf()` 这类转 DataFrame 的方法，但环境里没装 pandas；DuckDB 自己不带这个依赖 | 用 `.fetchall()` 拿原生结果，或 `pip install pandas`（要 Arrow 就再装 `pyarrow`） |
| `python -m duckdb` 报 `No module named duckdb.__main__` | `pip install duckdb` 只装 Python 库，CLI 是另一个独立可执行文件 | 去 https://duckdb.org/install/ 的 CLI 页签下载单文件客户端，别指望 Python 包能当命令行用 |
| 查询结果里字段名带引号、或者 `FROM 'x.csv'` 报路径找不到 | SQL 里单引号是字符串字面量，Windows 路径里的反斜杠又容易被当转义 | 路径统一用正斜杠或双写转义；标识符要用双引号，别用单引号 |
| 同一个 `.duckdb` 文件两边同时写，后开的那个报错或卡住 | 文件数据库是单写者模型，被一个进程持有写锁时别的进程不能同时写 | 读的场景用 `-readonly` 打开；真要并发就各自写各自的库再合并，或者走「一个写者 + 多个读者」 |
| 扩展 `INSTALL` 失败 / 超时 | 扩展默认要从网络下载，离线或内网环境拿不到 | 先确认网络可达；离线场景按官方 Extensions 文档走离线安装（下载扩展文件后本地安装），别反复重试 |
| 大 CSV 直接 `SELECT *` 把内存吃爆 | 结果集全量物化，`SELECT *` 又会拉上所有列，列存引擎也救不了返回全表 | 只选需要的列、先加 `LIMIT` 探路、聚合尽量下推到 SQL 里做，别拉回本地再算 |
| 以为它能像 MySQL 那样给应用当后端 | 它是分析引擎，OLTP 的高频小事务、并发写入、行级锁这些语义都不匹配 | 业务库还是用事务型数据库；DuckDB 只放在分析、清洗、导出的环节 |
| 想直接 `INSERT` / `UPDATE` 改一个 pandas / polars DataFrame | 官方文档明确：这些内存表被当成表查询时是**只读**的，不能回写 | 把查询结果存成新表或新文件，再自己写回原 DataFrame；别指望 SQL 直接改内存对象 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 需要（仅安装扩展时） | 从官方扩展仓库下载 `excel`、`httpfs` 等扩展；查询本地文件与本地库本身不需要网络 |
| 读取文件 | 需要 | 把 CSV / Parquet / JSON 等文件当表读；读取已有的 `.duckdb` 数据库文件 |
| 写入文件 | 需要 | `COPY ... TO ...` 导出结果；`INSTALL` 落盘扩展；创建 / 更新 `.duckdb` 数据库文件与其 WAL |
| 凭证 | 一般不涉及 | 本地文件分析无需任何 Key；只有连远端对象存储 / 远端数据库时才会用到对应服务的凭证，届时按官方文档配置 |
| 子进程 / 后台常驻 | 视用法而定 | CLI 是前台一次性进程，跑完即退；Python 里是进程内的库，不常驻、不起服务、不监听端口 |

## 触发场景

- 「这个 CSV 太大了，pandas 打开就卡，帮我用 SQL 聚合一下」
- 「把这几份 Parquet 拼起来对一下账」
- 「不改代码，直接查一下这个 parquet 里有多少条异常记录」
- 「帮我把 CSV 转成 Parquet」
- 「在 Python 里用 SQL 查我这个 DataFrame」
- 「有没有不用装数据库就能跑 SQL 的工具」

## 能力边界

**覆盖**：

- 对本地文件（CSV、Parquet 等）直接执行标准 SQL：过滤、聚合、窗口函数、多表 join、CTE、子查询。
- 单机上的中型数据分析：实测环境能顺畅处理到 GB 级文件，具体上限取决于机器内存与查询形态。
- 与 Python / pandas / polars / Arrow 的内存数据互操作（转 DataFrame 需要额外装 pandas 或 pyarrow）。
- 通过扩展读取 Excel 等额外格式、访问远端存储或数据库；扩展清单与能力以官方文档为准。
- 持久化为单文件数据库，或纯内存跑完即弃。

**不覆盖**：

- 不做分布式计算，不跨机器扩算力。
- 不是 OLTP 数据库：不适合高并发写入、逐条小事务、需要行级锁的业务系统。
- 不提供用户权限体系、连接池、服务端监听这些数据库服务端能力。
- 不做数据可视化、不出图表，也不做调度；它只把查询结果交出来。
- 不做爬虫、不解析网页，正文里「爬虫」是这个技能包所在分类的标签，不是它的功能。

## 依赖条件

- **CLI**：Windows / macOS / Linux 的预编译单文件可执行程序，无额外运行时依赖。版本以官方安装页为准（本文写作时稳定版为 1.5.5）。
- **Python 包**：官方要求 Python 3.9 或更新；实测 Python 3.11.9 + `duckdb` 1.5.5 可用。pip 与 conda 两种安装方式官方都支持。
- 若要 `pip install duckdb` 后使用 `.df()` / `fetchdf()`，需要额外安装 pandas；要 Arrow 输出需要 pyarrow。
- 可以直接把 pandas / polars 的 DataFrame 或 Arrow 表当表查（官方文档明确它们是**只读**的，不能通过 `INSERT` / `UPDATE` 改）。
- 安装扩展时需要能访问官方扩展仓库。
- 不需要任何账号、Key 或注册。

## 已知限制

1. **单机单写者**：同一数据库文件的并发写入能力有限，多进程场景要按读写分离来设计。
2. **版本间存储格式可能不兼容**：打开旧版本创建的数据库文件时可能提示需要迁移，跨版本共用同一个库文件前先确认存储版本；CLI 提供 `-storage-version` 参数用于指定兼容版本。
3. **扩展要联网**：核心功能开箱可用，但 Excel、远端存储等能力依赖扩展下载。
4. **转换方法有隐式依赖**：`.df()` 依赖 pandas、`.arrow()` 依赖 pyarrow，缺了会在调用时报错而不是安装时就提示。
5. **`SELECT *` 不等于省内存**：列存能省的是「不读的列不读」，一旦你要求返回全表全列，物化开销照付。

## 自检清单

执行前：

- [ ] 确认输入文件的真实路径与分隔符、编码（先 `SELECT * ... LIMIT 5` 探一下）。
- [ ] 确认这次是「读文件」还是「开已有库」——写错会创建出一个空的新库文件。
- [ ] 需要 pandas / Arrow 结果的话，先确认环境装没装。
- [ ] 写操作前确认目标库文件没有被别的进程占用。

执行后：

- [ ] 结果行数与预期量级对不对（先 `count(*)` 再取明细）。
- [ ] 导出文件确实落盘且大小合理，没有因为是内存库而白跑。
- [ ] 打开的库是 `-readonly` 还是可写，别在只读场景误加了写操作。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/duckdb/duckdb | 上游仓库（安装与完整文档以它为准） |
| https://duckdb.org/docs/current/clients/cli/arguments | CLI 参数完整列表（`duckdb -help` 同源） |
| https://duckdb.org/docs/current/clients/cli/dot_commands | CLI 点命令列表（`.help` 同源） |

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
