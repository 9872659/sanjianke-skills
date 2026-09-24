---
name: sanjianke-polars
slug: sanjianke-polars
displayName: 三剪客 · 高性能 DataFrame 计算库
description: "polars：比 pandas 更快、更省内存的 DataFrame 计算库，带惰性查询优化与流出式执行，能处理超过内存的数据集，也能在 Python / Rust / Node.js / R 里用。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "polars：高性能 DataFrame 计算库。惰性查询、多线程向量化执行，能处理超过内存的数据集；含安装、常用命令、6 条常见坑与能力边界。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析

---

# 三剪客 · 高性能 DataFrame 计算库

Polars 是一个用 Rust 写的 DataFrame 分析查询引擎。它的价值在于两点：把「写数据变换」变成写表达式（可组合、可下推、能被引擎优化），以及在单机上把多核吃满——数据大到内存装不下时，可以用流出式执行分块跑完。

如果你现在用 pandas 处理几百万行开始卡、内存开始爆，或者一堆链式 `groupby` 已经看不懂了，就是换它的时候。如果你只是对几百行数据做个小筛选，它带来的收益很小。

**上游项目**：`polars`　**仓库**：https://github.com/pola-rs/polars

> 版本号与行为取自实测环境（Python 包 1.44.2）。可选功能（extras）与安装选项随版本变化，以官方安装文档为准。

## 什么时候用 / 不用

**用它**：

1. 「pandas 读这个 CSV 直接内存溢出」——惰性扫描加流出式执行，可以跑超过内存的数据集。
2. 「这段 groupby 链式代码又慢又难读」——表达式 API 能把变换写清楚，还能让引擎自动优化查询计划。
3. 「我只想先看一列、别的列别读」——列存加惰性扫描，不用的列根本不进内存。
4. 「同一份数据要反复切口径」——表达式与惰性计划可以复用、可以打印出来看，排查比黑盒快。
5. 「要跨 Python / Rust / Node.js / R 用同一套数据处理逻辑」——官方多语言绑定，概念模型一致。

**不要用它**：

1. 数据只有几百上千行、操作是一次性筛选加排序——pandas 的生态和示例更多，迁移成本不划算。
2. 需要大量依赖「带索引」的 API（按 index 对齐、`.loc` 切片、时间序列索引重采样）——Polars 没有 pandas 那种行索引，硬搬会处处别扭。
3. 团队完全没写过表达式 API，且项目已经用 pandas 稳定运行——重写风险大于收益。
4. 需要的是交互式探索画图、而不是可复现的数据管线——那是 notebook 加可视化库的活。
5. 需要跨机器分布式计算（集群上跑几十 TB）——Polars 是单机引擎，横向扩展不是它的事。

## 安装

**Python（主流用法，本文实测路径）**

```bash
pip install polars
```

实测环境：Python 3.11.9 + `polars` 1.44.2（Windows）。安装后会同时得到 `polars` 包与 `polars` 模块，`import polars as pl` 即可。

可选功能（Excel、数据库连接、云存储、GPU、互操作等）需要装对应的 extras / 可选依赖，官方安装文档的「Feature flags」一节按类别列出，实测抓到的确切名字包括：

| 类别 | extras |
|---|---|
| 全部 | `all` |
| GPU | `gpu` |
| 互操作 | `pandas`、`numpy`、`pyarrow`、`pydantic` |
| Excel | `calamine`、`openpyxl`、`xlsx2csv`、`xlsxwriter`、`excel` |
| 数据库 | `adbc`、`connectorx`、`sqlalchemy`、`database` |
| 云存储 | `fsspec` |
| 其它 I/O | `deltalake`、`iceberg` |
| 其它 | `async`、`cloudpickle`、`graph`、`plot`、`style`、`timezone`（官方标注仅在 Windows 上需要） |

写多个用逗号连起来：

```bash
pip install 'polars[numpy,fsspec]'
```

还有两个与运行环境和数据规模相关的：

```bash
polars[rtcompat]   # 老 CPU（无 AVX2 支持）需要
polars[rt64]       # 默认行数上限约 2^32，用它把上限提到 2^64
```

注意 1.0 升级指南里的破坏性变更：`fastexcel`、`gevent`、`matplotlib` 这几个旧 extras 名已改名，例如旧写法 `polars[fastexcel,gevent,matplotlib]` 现在要写 `polars[calamine,async,graph]`。照抄老教程的 extras 名会直接装不上。

**其它语言**

官方提供 Rust crate、Node.js 包、R 包，各自的安装方式见仓库 README 中对应的文档入口。从源码编译 Python 绑定属于高级用法，官方文档有专门步骤，普通使用不需要。

## 常用操作

**1. 直接读文件做一次聚合（eager 方式）**

```python
import polars as pl

df = pl.read_csv("data.csv")
print(df.filter(pl.col("amount") > 0).group_by("region").agg(pl.col("amount").sum()))
```

`read_csv` / `read_parquet` / `read_json` 是无状态即时读取，读完立刻在内存里。

**2. 惰性扫描 + 收集 + 看查询计划（最推荐的姿势）**

```python
import polars as pl

q = (
    pl.scan_parquet("orders.parquet")
    .filter(pl.col("status") == "shipped")
    .group_by("customer_id")
    .agg(
        pl.col("amount").sum().alias("total"),
        pl.len().alias("n_orders"),
    )
    .sort("total", descending=True)
)

print(q.explain())     # 打印优化后的查询计划
result = q.collect()   # 到这里才真正执行
```

`scan_*` 返回 LazyFrame，不 `collect()` 就不会算。`explain()` 能让你看到过滤和投影有没有被下推到扫描阶段。

**3. 内存装不下时：切流出式引擎**

```python
result = q.collect(engine="streaming")
```

官方文档明确：给 `collect` 传 `engine="streaming"` 即以分块方式执行，可处理放不进内存的数据集，且流式引擎在内存压力之外通常也更快。实测 `collect(engine="streaming")` 在 1.44.2 下可用。

`collect` 的 `engine` 参数官方文档列出四个取值：

| 取值 | 含义 |
|---|---|
| `"auto"` | 默认值。按 `Config.set_engine_affinity` 或 `POLARS_ENGINE_AFFINITY` 环境变量决定，未设置时回落到 `"in-memory"` |
| `"in-memory"` | 内存引擎，当前默认引擎 |
| `"streaming"` | 流式引擎，官方说明它「即将成为默认引擎」 |
| `"gpu"` | CUDA GPU 引擎，需要 N 卡与 `cudf-polars` |

官方还提示：若所选引擎跑不了该查询，Polars 会回落到内存引擎。

**关于下一个大版本**：2.0 升级指南说明 `collect` / `collect_async` 仍默认 `engine="auto"`，但 `"auto"` 的解析目标将从内存引擎改为流式引擎。要恢复旧行为，可以用 `pl.Config.set_engine_affinity("in-memory")`（进程级）、`lf.collect(engine="in-memory")`（单次查询），或设 `POLARS_ENGINE_AFFINITY=in-memory`。另外 `explain()` / `show_graph()` 只有在显式传 `engine="streaming"` 时才渲染流式计划，`sink_*` 不受影响。

**4. 写回文件 / 转给别的库**

```python
df.write_parquet("out.parquet")
df.write_csv("out.csv")

pdf = df.to_pandas()      # 需要装 pandas
tbl = df.to_arrow()       # Apache Arrow 表
```

Polars 内部使用 Apache Arrow 列式格式，与 Arrow / pandas 之间可以零拷贝或低成本共享。

**5. 控制线程数**

```python
import polars as pl
print(pl.thread_pool_size())   # 实测输出：12（由本机核数决定）
```

Polars 默认就会用满 CPU 核。官方 API 文档给出的控制方式是在**进程启动前**设置 `POLARS_MAX_THREADS` 环境变量；线程池没有加锁，一旦设好就不能再改，官方也明确「除此之外强烈建议不要覆盖这个值，引擎会自动设置它」，典型适用场景是在 PySpark UDF 之类的上下文里临时限流。

另外注意：老函数名 `polars.threadpool_size()` 已废弃，改用 `thread_pool_size()`。

**6. 和 Python 的 multiprocessing 一起用时，必须用 spawn**

```python
from multiprocessing import get_context

with get_context("spawn").Pool() as pool:
    pool.map(my_fun, ["input1", "input2"])
```

官方专门写了这一节：Polars 本身是多线程的，不能与 `fork` 启动方式（Unix 上的默认值）组合使用，必须显式用 `spawn` 或 `forkserver`，其中 `spawn` 是官方推荐且跨平台可用的选择。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `AttributeError`，或结果和 pandas 预期完全不一样 | 把 pandas 的习惯直接搬过来了：Polars 没有 index，也就没有 `.loc` / `.iloc`；取值与赋值方式都不同 | 换表达式写法：`pl.col("x")`、`df.select(...)`、`df.filter(...)`，把返回的新对象重新赋值给变量 |
| 调用 `df.with_columns(...)` 后发现原变量没变 | 官方记录的行为是返回新的 DataFrame（因此也不会出现 pandas 的 `SettingWithCopyWarning`），不是就地修改 | 接住返回值：`df = df.with_columns(...)` |
| `q.filter(...)` 之后打印出来还是「查询」而不是数据 | 用了 `scan_*` 或 `.lazy()`，拿到的是 LazyFrame，惰性计划不会自动执行 | 末尾加 `.collect()`；调试时先 `.explain()` 看计划，再决定收不收 |
| `collect(engine="streaming")` 报未知参数 | 旧版本还没有这个参数名，或写法与该版本不符 | 先 `print(pl.__version__)` 确认版本，再对照该版本文档；升级 polars 往往是最省事的解法 |
| 和 `multiprocessing` 一起用时抛出与 multiprocessing 方法相关的错误 | 在 Unix 上默认用 `fork`，而 Polars 是多线程的，不能安全 fork | 显式用 `get_context("spawn").Pool()`，不要依赖平台默认值 |
| 空值和 NaN 的处理结果和 pandas 不一致 | 官方迁移文档明确：pandas 用 `NaN` / `None` 表示缺失且可能把整型列变成浮点，而 Polars 里缺失一律是 `null`；浮点列里的 `NaN` **不被当作缺失**，只是一个特殊浮点值 | 显式处理：先 `fill_null` / `drop_nulls`，需要区分时用对应的判空表达式，别默认两者等价 |
| 照抄老教程的 extras 名字，`pip install` 直接失败 | 1.0 升过一轮 extras 名（例如 `fastexcel` / `gevent` / `matplotlib` 已改名） | 对照官方安装文档当前的 Feature flags 表写 extras，别用旧文章里的名字 |
| 读 Parquet 目录时行为和老版本不同、分区列没出现 | 1.0 起 `read/scan_parquet` 对**文件输入**（单文件、glob、文件列表）默认关闭 Hive 分区推断，目录输入才默认开启 | 需要老行为就显式传 `hive_partitioning=True` |
| 读 `lf.schema` / `lf.columns` 时收到性能警告 | 这些惰性属性会触发 schema 解析，官方已将其标记为废弃并给出替代方法 | 改用 `LazyFrame.collect_schema` 取 schema |
| 以为加 `multiprocessing` 就能更快 | Polars 已经把可并行的计算放到多线程里，再套一层进程池往往只是抢内存和 CPU | 先看 `explain()` 有没有优化空间、要不要切 streaming；只有当瓶颈在别的单线程库上时，才考虑多进程 |
| 大结果集直接 `to_pandas()` 把内存打爆 | 转换成 pandas 意味着额外物化一份数据，惰性引擎省下的内存被这一步吃回去 | 先在 Polars 侧聚合 / 裁剪到需要规模，再转换；能不下沉到 pandas 就别下沉 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 默认不需要 | 核心计算是纯本地的。只有读取云存储 / 远端数据库、或安装可选依赖时才需要联网 |
| 读取文件 | 需要 | `read_csv` / `scan_parquet` / `read_json` 等读取本地数据文件 |
| 写入文件 | 需要 | `write_parquet` / `write_csv` 等把结果落盘 |
| 凭证 | 一般不涉及 | 纯本地文件分析不需要任何 Key；只有接远端存储或数据库时才用到对应凭证，按官方文档配置 |
| 子进程 / 后台常驻 | 视用法而定 | 库本身在进程内运行，不起服务、不监听端口；只有你自己用 `multiprocessing` 时才会开子进程，这时必须用 `spawn` |

## 触发场景

- 「这个文件 pandas 读不进内存，帮我换 polars 试试」
- 「把这段 pandas 的 groupby 改写成 polars」
- 「为什么我的 polars 代码没报错但也不出结果」
- 「怎么让 polars 少占点内存 / 用流式跑」
- 「polars 和 pandas 到底差在哪，我该换吗」
- 「polars 跑多进程报错了」

## 能力边界

**覆盖**：

- 单机 DataFrame 变换：读取、过滤、聚合、join、排序、窗口函数、pivot / unpivot、时间序列处理。
- 惰性查询与自动查询优化，可用 `explain()` 查看优化后的计划。
- 流出式执行：通过 `collect(engine="streaming")` 处理放不进内存的数据集。
- 多线程、向量化执行，默认使用全部 CPU 核。
- 与 Apache Arrow 生态互操作，可与 pandas / Arrow / NumPy 互转。
- 多语言：Python、Rust、Node.js、R 绑定，另有 SQL 接口。
- 可选 GPU 加速与其它可选功能依赖（按官方安装文档启用）。

**不覆盖**：

- 不做分布式计算，不能跨机器水平扩展算力（官方另有面向集群的产品线，不属于本库）。
- 不做绘图、不做报表渲染，也不做调度编排——它只负责把计算做出来。
- 不替代 pandas 的全套生态：很多第三方库只接受 pandas 对象，仍需要 `to_pandas()` 过桥。
- 不做爬虫、不解析网页，也不负责文件下载。
- 不提供持久化数据库或服务端能力。

## 依赖条件

- **Python**：`pip install polars`；实测 Python 3.11.9 + polars 1.44.2。官方支持的最低 Python 版本以官方安装文档为准。
- **可选依赖**：Excel、数据库、云存储、Arrow / pandas 互操作、GPU 等能力需要额外安装对应可选依赖。
- **其它语言**：Rust、Node.js、R 各有自己的包管理器，按仓库 README 的文档入口安装。
- **平台**：Windows / macOS / Linux 均可；实测为 Windows。
- 无账号、无 Key、无注册要求。

## 已知限制

1. **没有 pandas 那种行索引**：官方迁移文档说明，因为 Polars 没有 index，所以也没有 `.loc` / `.iloc`，同样不会出现 pandas 那个设置副本警告。依赖 index 的惯用写法要整体改写，不能逐行替换。
2. **类型更严格**：官方把「Polars is strict」列为与 pandas 的概念差异之一——pandas 会宽松地转换类型（整型列出现缺失就变浮点），Polars 不会。1.0 起 Series 构造函数的 `strict` 行为也改得更严，混类型要显式传 `strict=False`。
3. **API 在版本间出现过不兼容变更**：从 0.x 到 1.0 有过大规模破坏性变更（`replace` 拆成 `replace` / `replace_strict`、越界索引默认改为抛错、extras 更名等），官方发布了升级指南。建议锁定版本，升级前先读升级指南。
4. **惰性属性被废弃**：`LazyFrame` 的 `schema` / `dtypes` / `columns` / `width` 会触发性能警告，官方替代方法是 `collect_schema`。
5. **流出式执行不是万能的**：并非所有查询形态都能完全流式化，部分算子仍需要物化中间结果，内存上限依然存在；而且所选引擎跑不了时会静默回落到内存引擎。
6. **与多进程组合有约束**：必须用 `spawn` 启动方式，用 `fork` 会直接出错。
7. **第三方生态仍有缺口**：不少周边库只认 pandas，桥接转换会带来额外内存开销。

## 自检清单

执行前：

- [ ] 确认环境里的 polars 版本（`pl.__version__`），再决定用哪些参数名。
- [ ] 分清楚这次用的是 `read_*`（即时）还是 `scan_*` / `.lazy()`（惰性）。
- [ ] 判断数据量级：小数据用 eager 更省心，大数据或高于内存先走惰性加流式。

执行后：

- [ ] 惰性查询确认已经 `collect()`，别拿着未执行的 LazyFrame 当结果用。
- [ ] 检查行数与列名是否和预期一致，尤其是 join 与聚合之后。
- [ ] 大结果集转换到 pandas 之前，先估算内存余量。
- [ ] 用了 `multiprocessing` 的话，确认启动方式是 `spawn`。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/pola-rs/polars | 上游仓库（安装与完整文档以它为准） |
| https://docs.pola.rs/user-guide/installation/ | 官方安装文档（含可选功能列表） |
| https://docs.pola.rs/user-guide/concepts/streaming/ | 流出式执行的官方说明 |

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
