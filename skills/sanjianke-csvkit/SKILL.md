---
name: sanjianke-csvkit
slug: sanjianke-csvkit
displayName: 三剪客 · CSV 处理 CLI 套件
description: "csvkit 是一组 CSV 命令行工具：in2csv 转格式、csvcut/csvgrep/csvsort 筛选排序、csvjoin/csvstack 合并、csvsql 直接对 CSV 跑 SQL。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "csvkit 全部子命令的安装与实战用法：Excel/JSON 转 CSV、查列、清洗坏行、按列合并、用 SQL 查 CSV，以及 CSV 嗅探失败、类型推断误判、管道重复传参等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档处理
  - CSV
  - 数据清洗
---

# 三剪客 · CSV 处理 CLI 套件

表格文件最烦的场景不是"打不开"，而是"要动一下但不想写代码"：把十几个 xlsx 转成 csv、看一眼某列有哪些值、按某列筛一批行、两个表按 key 拼起来、按某列排序取前几。这些事在 Excel 里点半天、在 Python 里写几十行，用 csvkit 就是一条管道命令。

csvkit 不是单个程序，是 **14 个命令组成的套件**，全部读写标准输入输出，所以能像乐高一样用 `|` 串起来，串起来的中间过程不落盘。

**上游项目**：`csvkit`　**仓库**：https://github.com/wireservice/csvkit

## 什么时候用 / 不用

**用它**：

- "把这批 xlsx / json / dbf 全转成 csv。"——`in2csv` 覆盖 csv、dbf、fixed、geojson、json、ndjson、xls、xlsx 八种输入。
- "这 csv 有哪些列？先给我看看。"——`csvcut -n` 直接列出列名和序号，不用打开文件。
- "按 county 列筛出 LANCASTER 的行，再按金额倒序。"——`csvgrep -c county -m LANCASTER | csvsort -c total_cost -r`。
- "这两个表都有 fips 列，拼一张宽表。"——`csvjoin -c fips a.csv b.csv`，等价于 SQL 的 JOIN。
- "我不想建库，就想对 csv 写一句 SQL。"——`csvsql --query "SELECT ..." data.csv`，内部用内存 SQLite。
- "文件里有几行列数不对，先体检一下哪儿坏了。"——`csvclean --length-mismatch` 把坏行报到标准错误并给出退出码。
- "要把 csv 喂给前端或 API。"——`csvjson` 输出 JSON，加 `--lat/--lon` 还能直接出 GeoJSON。

**不要用它**：

- **几百万行以上的大文件做聚合**——`csvstat`、`csvsql --query` 这类会把整份数据读进内存，官方文档明确说大数据集上会"非常慢"。这种量级换 DuckDB、qsv 或直接写 SQL。
- **要改字段内容**——csvkit 能筛行、选列、排序、合并，但**没有替换/改写的子命令**。官方推荐改值用 qsv 的 `replace` 或 miller 的 `mlr put`；转置也推荐 qsv / miller。
- **CSV 去重与模糊合并**——官方明确点名用 `csvdedupe`，不是 csvkit 的活。
- **解析畸形 CSV 的极端情况**——嗅探机制对"没有统一标准"的 CSV 会误判。格式越怪，越应该直接上 polars / pandas 显式指定参数。
- **要出图、要交互式探索**——画图推荐 `jp`，交互浏览推荐 VisiData，都不在 csvkit 里。

## 安装

官方推荐装在虚拟环境里。要求 Python 3，支持 Linux / macOS / Windows 上非 EOL 的 Python 版本。

```bash
# 通用
pip install csvkit

# 要读 .zst（Zstandard）压缩文件，加这个
pip install csvkit[zstandard]

# macOS 用 Homebrew
brew install csvkit
```

macOS 上如果装完命令跑不起来，按官方 Troubleshooting 的顺序试：

```bash
pip install --upgrade setuptools
pip install --upgrade csvkit
# 若报 OSError: [Errno 1] Operation not permitted
sudo pip install --ignore-installed csvkit
# 若报 /usr/local/bin/pip: bad interpreter
python3 -m pip install csvkit
```

装完验证（能打印版本即可）：

```bash
csvcut --version
in2csv --help | head -n 5
```

Windows 原生环境同样 `pip install csvkit` 可用；如果命令行输出中文/重音字符报 `'ascii' codec can't encode`，见「常见坑」。

## 常用操作

**1. 列出 CSV 的列名（几乎是所有操作的第一步）**

```bash
csvcut -n data.csv
```

**2. 选列、按列筛行、排序，串成一条管道**

```bash
csvcut -c county,item_name,total_cost data.csv \
  | csvgrep -c county -m LANCASTER \
  | csvsort -c total_cost -r \
  | csvlook
```

`csvgrep` 用 `-m` 是子串匹配，`-r` 是正则匹配；`csvlook` 输出 Markdown 风格的表格预览。列多表宽时接 `| less -S` 或用 `csvcut` 先减列。

**3. Excel / JSON 转 CSV**

```bash
in2csv ne_1033_data.xlsx > data.csv            # xlsx / xls 直接转
in2csv -n book.xlsx                            # 先列出有哪些 sheet
in2csv --sheet "Sheet2" book.xlsx > s2.csv     # 指定 sheet
in2csv --write-sheets - --use-sheet-names book.xlsx   # 所有 sheet 各写一个文件

curl -s 'https://api.github.com/repos/wireservice/csvkit/issues?state=open' \
  | in2csv -f json > issues.csv                # API 返回的 JSON 直接转
```

**4. 看数据全貌的统计**

```bash
csvstat data.csv                     # 每列的类型、空值、唯一值、最值、均值等
csvstat -c acquisition_cost data.csv # 只看指定列
csvstat --count data.csv             # 只数行数
```

**5. 合并：按 key join，或纵向 stack**

```bash
csvjoin -c fips data.csv population.csv > joined.csv     # 横向 JOIN
csvstack ne_1033_data.csv ks_1033_data.csv > region.csv  # 纵向堆叠（列名需一致）
csvstack -g state ne.csv ks.csv > region.csv             # -g 额外加一列标记来源文件
```

**6. 不建库，直接对 CSV 跑 SQL**

```bash
# 内存 SQLite，把 csv 当表查
csvsql --query "select county, item_name from joined where quantity > 5;" joined.csv | csvlook

# 生成建表语句（默认方言 sqlite，用 -i 指定）
csvsql -i postgresql joined.csv

# 真的写进数据库：先建表再插数据
createdb test
csvsql --db postgresql:///test --tables fy09 --insert data.csv
sql2csv --db sqlite:///leso.db --query "select * from joined where county='DOUGLAS';" > douglas.csv
```

**7. 清洗与格式检查**

```bash
csvclean -a bad.csv                       # 打开全部检查，坏行报到 stderr
csvclean --length-mismatch --omit-error-rows bad.csv 2> errors.csv   # 只保好行，坏行另存
csvclean --fill-short-rows --fillvalue "US" short.csv   # 补上缺失的字段
csvclean --join-short-rows --separator ", " broken.csv  # 把被断行拆开的记录拼回去
```

**8. 导出 JSON / GeoJSON**

```bash
csvjson data.csv > data.json                        # 数组形式
csvjson -k "State Abbreviate" -i 4 data.csv         # 以某列为 key 输出对象（值必须唯一）
csvjson --lat latitude --lon longitude --k slug --crs EPSG:4269 -i 4 geo.csv  # GeoJSON
```

**9. 常用通用参数（几乎每个子命令都支持，完整列表见 `--help`）**

```bash
csvstat -d ';' -e gbk -H data.csv    # 分号分隔、GBK 编码、无表头行
csvstat --no-inference data.csv      # 关掉类型推断，全部按文本处理
csvcut -y 0 -d ',' -q '"' data.csv   # 关掉嗅探，自己指定分隔符与引号符
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 值跑到错误的列里；本该一个字段却被拆成多列；报 `Row # has # values, but Table only has # columns.` | CSV 没有统一标准，csvkit 用 Python 的 `csv.Sniffer` 猜分隔符和引号符，默认只拿文件**前 1024 字节**做样本，猜错了就整列错位 | 先试 `-y -1`（`--snifflimit -1`，用整个文件做样本）；还错就 `-y 0` 彻底关掉嗅探，手动指定 `-d` 分隔符和 `-q` 引号符。注意 `csvstat -c 1` 与 `csvstat --count` 行数不一致，往往也是嗅探问题 |
| `1` / `0` 变成 `True` / `False`；电话号码被当数字丢掉前导 `+` 或 `0`；文本被识别成日期；意大利有个市镇叫 "None" 被当成空值 | csvkit 的**类型推断**过于积极，把文本反推成了数字/布尔/日期类型 | 加 `--no-inference` 全部按文本处理；只想阻止日期化就把 `--date-format` 和 `--datetime-format` 设成一个文件里不存在的格式串（如 `-`）；想保留 `""`、`na`、`none`、`null` 这类字面量，加 `--blanks` |
| 管道第二步开始报参数错误或结果不对 | 规范说明：csvkit 输出**永远是默认格式化**（取消可选引号、统一逗号分隔、统一 LF 换行、统一 UTF-8）。也就是说这些参数**只需在第一个命令上指定一次**，后面再指定反而会把工具搞崩 | 只在管道链条的第一个 csvkit 命令上传 `-d` / `-q` / `-u` / `-e` 等参数，后续命令不要再传 |
| `csvsql --query` 跑到卡死，或者吃光内存 | 该模式会把**整份 CSV 加载进内存 SQLite**，官方明确说大数据集会非常慢 | 小文件直接用；大文件改成真正建库再查（`csvsql --db ... --insert` 然后 `sql2csv --query`），或者换数据库/列式引擎 |
| crontab 里跑 csvkit 报错或读不到文件 | cron 环境**没有分配 tty**，csvkit 读文件的方式会失败 | 把文件用标准输入喂进去而不是当参数传：`csvsql --query '...' --tables t < /my/file.csv`（官方给的可用写法） |
| 装完 csvkit 但连 PostgreSQL / MySQL 报 `You don't appear to have the necessary database backend installed` | 数据库后端驱动不在 csvkit 的默认依赖里 | 按提示装驱动：PostgreSQL 用 `pip install psycopg2`，MySQL 用 `pip install mysql-connector-python` 或 `mysqlclient`。用 Homebrew 装的 csvkit 要用**同一个** pip：`$(brew --prefix csvkit)/libexec/bin/pip install psycopg2` |
| 输出含重音字符或中文时抛 `'ascii' codec can't encode character ...` | Python 标准流编码不是 UTF-8（常见于 `csvlook ... \| less` 这类管道） | 用环境变量指定：`env PYTHONIOENCODING=utf8 csvlook dummy.csv \| less`。另外 csvkit 能直接读 `.gz` / `.bz2` / `.xz`，但**是在内存里解压**，只是方便不是性能优化 |
| xlsx 转出来行数或列数比实际少 | 生成该 xlsx 的程序把工作表尺寸写错了 | 加 `--reset-dimensions`（in2csv）忽略文件自带的尺寸信息 |
| 文件开头几行是版权声明/空行，转换报列数不匹配 | 表头前有杂行 | 用 `-K 3`（`--skip-lines 3`）跳过前 3 行 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 安装依赖时 pip 需要联网；处理本地 CSV 全程离线。只有你自己显式 `curl \| in2csv` 时才联网取数据 |
| 读取文件 | 是 | 读取待处理的 CSV / Excel / JSON / DBF 等输入文件 |
| 写入文件 | 是 | 通过 `>` 重定向或 `--write-sheets` 写出结果；不重定向则只打印到标准输出。`csvsql --db ... --insert` 会写入外部数据库 |
| 凭证 | 视情况 | 默认无。连 PostgreSQL / MySQL 才需要连接串，连接串里可能含用户名密码，建议走密码文件（如 PostgreSQL 的 `.pgpass`）而不是写进命令 |
| 子进程 / 后台常驻 | 是 | 安装与执行都会调用 pip / python 子进程；csvkit 本身是一次性命令，无常驻服务 |

## 触发场景

- "这个 Excel 转成 CSV。"
- "这批 CSV 帮我合并成一个文件。"
- "这两个表按 id 字段拼一下。"
- "筛出某个字段等于某值的行，按另一列排个序。"
- "这个 CSV 各列有哪些值、有没有空值？"
- "我不想建数据库，就想对这几个 CSV 写句 SQL 查一下。"
- "这文件读进来列全乱了，帮我定位问题。"

## 能力边界

**覆盖**：

- 输入转换：`in2csv` 支持 csv、dbf、fixed（定宽，需 schema）、geojson、json、ndjson、xls、xlsx；`sql2csv` 从数据库取数
- 处理：`csvclean` 查/修常见错误、`csvcut` 选删列、`csvgrep` 按子串或正则筛行、`csvjoin` 按列 JOIN、`csvsort` 排序、`csvstack` 纵向合并
- 输出与分析：`csvformat` 改输出格式、`csvjson` 出 JSON / GeoJSON、`csvlook` 表格预览、`csvpy` 进 Python 交互、`csvsql` 生成 SQL 或直接查库、`csvstat` 出列级统计
- 全套工具都支持标准输入输出，可任意管道串联；能自动读取 `.gz` / `.bz2` / `.xz` 压缩输入
- 统一的通用参数：分隔符、引号符、编码、嗅探范围、类型推断开关、空值定义、日期格式等

**不覆盖**：

- 字段值的替换与改写（官方推荐 qsv 的 `replace` 或 miller 的 `mlr put`）
- CSV 去重与实体合并（官方推荐 `csvdedupe`）
- CSV 转置（官方推荐 qsv 的 `flatten` 或 miller 的 XTAB）
- 画图（推荐 `jp`）与交互式浏览（推荐 VisiData）
- 从 HTML 表格提取（官方推荐 `messytables`）
- 大规模数据的内存内聚合：大数据集请换数据库或列式引擎

## 依赖条件

- Python 3（官方口径：支持 Linux / macOS / Windows 上非 EOL 的 Python 版本）
- `pip install csvkit`；读 `.zst` 需 `pip install csvkit[zstandard]`
- 使用数据库功能时需额外装驱动：PostgreSQL 用 `psycopg2`，MySQL 用 `mysql-connector-python` 或 `mysqlclient`；连接串遵循 SQLAlchemy 方言写法
- 不需要账号或 API Key
- 在 Windows 原生环境可用；文中示例多为 POSIX 写法，Windows 上请改重定向与引号写法

## 已知限制

1. 没有"改写字段值"的能力，只有筛行、选列、排序、连接、堆叠。
2. 类型推断对文本型数据容易误判（`1/0` → 布尔、电话号码 → 数字、日期格式猜错），必要时必须用 `--no-inference` 兜住。
3. CSV 嗅探只取前 1024 字节做样本，对格式不规范的 CSV 会猜错；格式越怪越需要手动指定参数。
4. `csvstat`、`csvsql --query` 等会把整个文件读进内存，官方承认大数据集上非常慢。
5. 压缩输入是"在内存里解压"，是便利性功能而非性能优化。
6. 各版本之间参数可能有差异（官方文档当前为 2.2.0 一线），具体以本机 `--help` 输出为准。

## 自检清单

执行前：

- [ ] 先用 `csvcut -n file.csv` 或 `csvstat file.csv` 确认列名与行数，别凭猜测写 `-c` 的列名
- [ ] 输入文件编码确认过（非 UTF-8 要显式 `-e`，如 `-e gbk`、`-e iso-8859-1`）
- [ ] 非逗号分隔的文件先确认分隔符，必要时 `-d`；怪格式直接 `-y 0` 关嗅探
- [ ] 含前导零、`1/0` 布尔嫌疑、日期文本的列，考虑加 `--no-inference`
- [ ] 管道链条中后续命令**不要**重复传 `-d` / `-q` / `-e` 等格式参数
- [ ] 涉及写数据库前确认连接串正确，密码不要明文留在命令历史里

执行后：

- [ ] 对比输入输出行数（`csvstat --count` 或 `wc -l`），确认没有静默丢行
- [ ] 检查 `csvclean` 的退出码：有坏行时退出码为 1，是发现问题的信号而不是脚本故障
- [ ] 抽查首尾若干行，确认列没有错位、引号没有残留
- [ ] 涉及中文字符时确认输出编码为 UTF-8，必要时设 `PYTHONIOENCODING=utf8`

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/wireservice/csvkit | 上游仓库（安装与完整文档以它为准） |
| https://csvkit.readthedocs.io | 官方文档：各子命令参数、通用参数、Tips and Troubleshooting |

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
