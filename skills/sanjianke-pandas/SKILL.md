---
name: sanjianke-pandas
slug: sanjianke-pandas
displayName: 三剪客 · Python 表格数据分析库
description: "pandas 的安装、常用操作与避坑要点：读写 CSV/Excel/Parquet/数据库、选列筛行、分组聚合、透视、多表合并、时间序列重采样，以及 Copy-on-Write 下链式赋值失效、可选依赖缺失、前导零被吞等高频坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "把爬回来或导出的一堆表格变成能算的数据：读入、体检、清洗、分组、透视、合并、落地。含 3.0 起 Copy-on-Write 带来的行为变化，以及 read_csv 类型推断、excel/parquet/html 可选依赖相关坑位。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析

---

# 三剪客 · Python 表格数据分析库

爬虫抓到的东西最后几乎都要落到"一张表"上：接口返回的 JSON、页面里的表格、导出的 CSV、数据库里拉下来的一批行。pandas 就是把这些形态各异的表变成同一个 `DataFrame`，然后让你用列名和条件去筛、去分组、去合并、去算，最后存成 CSV / Excel / Parquet 或写回数据库。

它的位置是"分析层"，不是"采集层"：抓取交给 requests、浏览器自动化或可视化采集工具，落地之后的清洗和统计交给它。

**上游项目**：`pandas`　**仓库**：https://github.com/pandas-dev/pandas

## 什么时候用 / 不用

**用它**：

- "这批 CSV / Excel / Parquet 读进来，先看看有多少行、哪些列、空值多不多。"——`read_*` 加 `info()` / `describe()` / `isna().sum()` 是标准起手式。
- "按城市分组算金额合计和笔数，再按合计倒序取前 20。"——`groupby().agg()` 加 `sort_values()`，比建视图再查快得多。
- "两个表按 id 拼起来，只保留左表存在的行。"——`merge(..., how="left")`，等价于 SQL JOIN。
- "把长表转成 城市 × 月份 的宽表，空的地方填 0。"——`pivot_table()`。
- "抓下来的 JSON 是嵌套的，帮我拍平成表再导出。"——`json_normalize` 配 `explode`。
- "按天或按小时统计量，再算 7 日滑动平均。"——把日期列设成索引后 `resample()` / `rolling()`。
- "这份几百 MB 的 CSV 先转成 Parquet，后面读得快一点。"——`read_csv` 配 `to_parquet` 的列式落盘组合。

**不要用它**：

- **要做分布式计算或单机几十 GB 以上的数据**——pandas 是单机内存模型。这类场景换 DuckDB、Polars、Dask/Spark，接口思路相近但不会把机器打爆。
- **要抓网页、要过登录和验证码、要执行页面 JS**——它不是爬虫。`read_html` 只解析服务端返回的静态 HTML，不跑 JavaScript；动态页面先交给采集工具拿到 HTML 或 JSON，再喂给 pandas。
- **要做交互式看板或让非技术同事点着看**——Streamlit 一类框架负责把 pandas 结果做成网页应用，BI 工具负责给业务方自助查询；pandas 本身没有 UI。
- **要求精确的十进制金融计算**——默认浮点有误差，金额建议用整数分存储或换十进制库。
- **只想把 CSV 转个格式、看一眼列名**——几行就够的事用 csvkit 这类命令行工具更省事，不必进 Python 解释器。

## 安装

官方分发渠道是 conda-forge 与 PyPI 两个，其余来源不受官方管理。推荐在虚拟环境里装。

```bash
# 方式一：pip（最通用）
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install pandas

# 方式二：conda
conda install -c conda-forge pandas
```

按需装可选依赖（不装的话，用到对应方法时才报 `ImportError`）：

```bash
pip install "pandas[excel]"       # read_excel / to_excel：openpyxl、xlrd、pyxlsb、python-calamine 等
pip install "pandas[performance]" # numexpr、bottleneck、numba；官方强烈建议装，大数据集提速
pip install "pandas[html]"        # read_html：BeautifulSoup4 加 lxml 或 html5lib
pip install "pandas[parquet]"     # pyarrow，Parquet / Feather 读写
pip install "pandas[hdf5]"        # PyTables
pip install "pandas[postgresql,mysql,sql-other]"   # SQLAlchemy 加各数据库驱动
pip install "pandas[all]"         # 全部可选依赖
```

装完验证：

```bash
python -c "import pandas as pd; print(pd.__version__)"
```

必需依赖：NumPy（官方安装页标注最低 1.26.0）、python-dateutil（最低 2.8.2）；Windows 与 Pyodide 上还需要 tzdata 提供时区库。

## 常用操作

**1. 读进来，并且第一次就把类型定对**

```python
import pandas as pd

df = pd.read_csv(
    "orders.csv",
    encoding="utf-8",
    dtype={"zipcode": str, "phone": str},   # 邮编、手机号必须当文本，否则前导零被吃掉
    usecols=["order_id", "city", "amount", "created_at"],  # 只读要用的列，省内存
    parse_dates=["created_at"],
)

print(df.shape)
df.info()
```

**2. 体检：先看清数据再动手**

```python
df.head(10)
df.describe(include="all")                # 数值列统计加类别列频次
df.isna().sum()                           # 每列空值数
df["city"].value_counts(dropna=False)     # 类别分布，含空值
df.duplicated(subset=["order_id"]).sum()  # 重复主键有多少
```

**3. 清洗与派生列（用 loc 与 assign，不要链式赋值）**

```python
df["city"] = df["city"].str.strip().str.replace("市", "", regex=False)

# 条件赋值：一条语句写完
mask = df["amount"].isna()
df.loc[mask, "amount"] = 0

# 新增列：assign 返回新对象，适合串起来写
df = df.assign(month=df["created_at"].dt.to_period("M").astype(str))
```

**4. 分组聚合与透视**

```python
# 按城市分组，一次算多个指标
summary = (
    df.groupby("city", as_index=False)
      .agg(orders=("order_id", "count"),
           amount_sum=("amount", "sum"),
           amount_mean=("amount", "mean"))
      .sort_values("amount_sum", ascending=False)
)

# 长表转宽表，空位补 0
wide = df.pivot_table(index="city", columns="month", values="amount",
                      aggfunc="sum", fill_value=0)
```

**5. 合并多张表（取代已移除的 append）**

```python
# 纵向堆叠：列名对齐，忽略旧索引
all_rows = pd.concat([df_2024, df_2025], ignore_index=True)

# 横向 JOIN：validate 帮你在键不唯一时立刻报错
merged = df_orders.merge(df_users, on="user_id", how="left", validate="many_to_one")
```

**6. 时间序列：按周期汇总与滑动窗口**

```python
ts = df.set_index("created_at").sort_index()
daily = ts["amount"].resample("D").sum()    # 按天汇总
weekly = ts["amount"].resample("W").sum()   # 按周汇总
ma7 = daily.rolling(7).mean()               # 7 期滑动平均
```

**7. 大文件分块处理，别一次读进内存**

```python
total = 0
for chunk in pd.read_csv("huge.csv", chunksize=100_000, usecols=["city", "amount"]):
    total += chunk["amount"].sum()
print(total)
```

**8. 落地：换更快或更通用的格式**

```python
df.to_csv("out.csv", index=False, encoding="utf-8-sig")  # Excel 打开中文不乱码
df.to_parquet("out.parquet", index=False)                # 列式，需要 pyarrow
df.to_excel("out.xlsx", index=False)                     # 需要 openpyxl
```

**9. 直接与数据库交换数据**

```python
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg2://user:pwd@host:5432/db")
df = pd.read_sql("select * from orders where created_at >= '2026-01-01'", engine)
df.to_sql("orders_clean", engine, if_exists="append", index=False, chunksize=1000)
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `df["a"][mask] = 1` 之后原表没变，或抛 `ChainedAssignmentError` | 3.0 起 Copy-on-Write 是默认且唯一模式，链式赋值被明确禁止：从别的对象派生出来的对象一律按副本对待，一条语句只能改一个对象 | 改成单语句 `df.loc[mask, "a"] = 1`；对"取出来的那一列"调用 `inplace=True` 的方法也属于链式赋值，改写为 `df["a"] = df["a"].replace(...)`，或 `df.replace({"a": {...}}, inplace=True)` |
| `arr = df.to_numpy()` 后写 `arr[0, 0] = 100` 报 `ValueError: assignment destination is read-only` | 返回的 NumPy 数组与 DataFrame 共享内存时，CoW 会把它设为只读，防止绕过规则反写 | 需要改就在副本上改：`arr = df.to_numpy().copy()`；确认原 DataFrame 不再需要时才考虑 `arr.flags.writeable = True` |
| 用外部 NumPy 数组构造 DataFrame 后，改外部数组把表也改了 | 3.0 起 Series/DataFrame 构造器默认复制传入的 NumPy 数组，与旧版本相反 | 想共享内存、零拷贝时显式传 `copy=False`，并接受由此产生的联动修改 |
| 邮编 `012345` 变成 `12345`、长订单号精度丢失、`1/0` 变成 `True/False` | `read_csv` 会做类型推断，把长得像数字的文本列读成整数、浮点或布尔 | 读入时就用 `dtype={"zipcode": str}` 把关键列钉成文本；必要时配 `keep_default_na=False` 防止 `NA`/`NULL` 字面量被当空值，或用 `na_values=[...]` 自定义空值集合 |
| 中文 CSV 用 Excel 打开是乱码；或读 GBK 文件报 `UnicodeDecodeError` | 写文件时用了不带 BOM 的 UTF-8，或读文件时没声明真实编码 | 写：加 `encoding="utf-8-sig"`；读：加 `encoding="gbk"` 或 `encoding="utf-8-sig"`，先确认源文件真实编码再传参 |
| 调用某个方法突然抛 `ImportError`：`to_markdown` 要 tabulate、`read_html` 要 BeautifulSoup4 加解析器、`read_hdf` 要 tables、`to_parquet` 要 pyarrow 或 fastparquet、`DataFrame.style` 要 Jinja2 | 这些都在可选依赖里，没装就不给用；而且只装 BeautifulSoup4 不带 lxml 或 html5lib 时 `read_html` 依然不可用 | 缺什么装什么，最省事是 `pip install "pandas[all]"`；固定环境把 extras 写进 requirements.txt |
| Windows 上 `read_orc()` 不可用 | 官方安装页明确说明该函数与 Windows 不兼容 | 换 Parquet 格式；Parquet 优先用 pyarrow，条件允许时通过 conda 安装 |
| `groupby(...).apply(...)` 的输出列比预期多或少，并伴随弃用警告 | 分组列是否带进 `apply` 的结果，在 2.2 与 3.0 之间发生过行为变更 | 显式传 `include_groups=`，或改用 `agg()` / `transform()` 这类语义更明确的入口 |
| 读几十万行的 CSV 卡住或吃满内存 | 一次性把整份数据读进内存 | 用 `chunksize=` 分块、用 `usecols=` 只读需要列、中间结果转 Parquet；几 GB 以上该换 DuckDB / Polars，而不是继续调 pandas 参数 |
| 时间列带时区后报找不到时区 | Windows 与 Pyodide 环境不带 IANA 时区数据库 | 装 `tzdata`（或 `pip install "pandas[timezone]"`） |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 本体是本地计算库，不联网。只有显式用 `read_csv("https://...")`、`read_sql` 连远程库、或读写 S3/GCS 时才联网（云存储需装 `pandas[fss,aws,gcp]`） |
| 读取文件 | 是 | 读取 CSV、Excel、JSON、Parquet、HDF5、XML、HTML 等本地或远端文件 |
| 写入文件 | 是 | `to_csv` / `to_excel` / `to_parquet` 等落盘；`to_sql` 会写入外部数据库 |
| 凭证 | 视情况 | 纯文件处理不需要。连数据库、对象存储或需鉴权的数据源时连接串含账号密码，建议从环境变量或配置文件读取，不要写死在脚本里 |
| 子进程 / 后台常驻 | 否 | 它是被 import 的库，不起服务、不常驻；只有安装阶段会调用 pip / conda 子进程 |

## 触发场景

- "这几个 CSV 合并成一张表，顺便去个重。"
- "按城市分组算一下总金额和订单数。"
- "爬下来的 JSON 帮我拍平成表格再导出 Excel。"
- "这个 Excel 有十几个 sheet，只读需要的列，转成 Parquet。"
- "算一下每天的量的 7 天滑动平均。"
- "两个表按 id 拼起来，只看匹配上的。"
- "数据里空值很多，先看看哪些列缺得最厉害。"

## 能力边界

**覆盖**：

- I/O：CSV 与分隔文本、Excel（xls/xlsx/xlsm/xlsb/ods）、JSON 与 ndjson、HTML 表、XML、Parquet / Feather / ORC、HDF5、SQL（经 SQLAlchemy 或 ADBC 驱动）、SAS/SPSS/Stata 等统计格式
- 清洗：选列筛行、去重、缺值处理（`isna` / `fillna` / `dropna` / `interpolate`）、文本方法（`.str`）、类别与可空整型/布尔类型、`query` 与 `eval`
- 计算：分组聚合（`groupby` 配 `agg` / `transform` / `apply`）、透视与交叉表、窗口函数（`rolling` / `expanding` / `ewm`）、时间序列重采样与偏移
- 组合：`merge` / `join` / `concat`，含多键、索引连接与合并校验参数
- 输出：写回上述格式、写数据库、出图（经 matplotlib 后端）、`DataFrame.style` 条件格式、Markdown 表格（需 tabulate）
- 与采集侧衔接：把采集工具拿到的 JSON、HTML 表、CSV 统一成 DataFrame，作为清洗与统计的起点

**不覆盖**：

- 网页抓取本身：不发请求、不解析 DOM 做定位、不执行 JavaScript、不处理登录态与验证码。`read_html` 只把静态 HTML 里的 `<table>` 抠出来
- 分布式与超大数据集：没有多机调度，单机内存是硬边界
- 交互式界面与看板：没有 UI，不提供定时刷新、权限、分享链接
- 机器学习建模：能用它做特征表，模型训练要靠别的库
- 精确十进制金融计算：默认浮点存在误差
- 命令行工具：只有 Python API，没有 `pandas` 这个可执行命令
- Windows 上的 `read_orc()`：官方标注不兼容

## 依赖条件

- Python 3（支持策略见官方开发文档中的 Python support policy）
- 必需依赖：NumPy（官方标注最低 1.26.0）、python-dateutil（最低 2.8.2）；Windows 与 Pyodide 需要 tzdata
- 通过 pip 或 conda-forge 安装；按功能需要追加可选依赖，见「安装」一节
- 不需要账号或 API Key；只有连数据库、对象存储或需鉴权的数据源时才需要凭证
- 内存是主要约束：可用内存应显著大于数据量，超过就只能分块或换引擎

## 已知限制

1. 单机内存模型，数据集规模受内存限制；分块、选列、转 Parquet 只能缓解，不能根治。
2. 3.0 起 Copy-on-Write 为唯一模式，旧代码里的链式赋值和"改视图等于改原表"的写法会失效或报错，升级前需要按官方迁移路径逐项排查。
3. 类型推断对"看起来像数字的文本"过于激进，前导零、长数字、`1/0` 布尔都会被改掉，必须在读入时显式指定 dtype。
4. 大量功能依赖可选依赖，缺一个就只在那一个方法上抛 `ImportError`，容易运行到中段才暴露。
5. `read_html` 不执行 JavaScript，动态渲染的表格抓不到；官方也专门提示了只装单一解析器时的失败情形。
6. 官方文档当前对应 3.0 一线，不同版本之间的行为与参数存在差异，具体以本机 `pd.__version__` 对应版本的文档和实际运行为准。

## 自检清单

执行前：

- [ ] 确认 `pd.__version__`，3.0 前后的赋值与复制行为不同，先确定在哪个大版本上写代码
- [ ] 用 `df.shape` / `df.info()` 确认行列数与 dtype，再决定清洗策略
- [ ] 关键标识列（邮编、手机号、订单号）是否已用 `dtype` 钉成文本
- [ ] 涉及的格式是否已装对应 extras（excel / parquet / html / hdf5 / 数据库驱动）
- [ ] 数据量是否可能超过可用内存，决定是否分块或用 `usecols`
- [ ] 代码里没有 `df["a"][mask] = x` 这类链式赋值

执行后：

- [ ] 对比输入输出行数，确认 `merge` / `dropna` / `drop_duplicates` 没有静默丢行
- [ ] `merge` 是否传了 `validate=`，有没有因为键不唯一把行数放大
- [ ] 抽查结果的 dtype 与空值数量，尤其 `groupby` 之后整数列是否变成浮点
- [ ] 导出文件用目标程序实际打开一次（Excel 中文编码、日期格式）
- [ ] 写数据库前确认目标表名与 `if_exists` 策略，避免覆盖已有数据

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/pandas-dev/pandas | 上游仓库（安装与完整文档以它为准） |
| https://pandas.pydata.org/docs/getting_started/install.html | 官方安装页：各安装方式与全部可选依赖分组 |
| https://pandas.pydata.org/docs/user_guide/copy_on_write.html | 官方 Copy-on-Write 说明：链式赋值、只读数组、构造器复制行为 |

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
