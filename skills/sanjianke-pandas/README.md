# 三剪客 · Python 表格数据分析库 Skill

把爬回来或导出的一堆表格变成能算的数据：读入、体检、清洗、分组、透视、合并、落地

---

## 前置条件

- 已装 Python 3，并能使用 pip 或 conda
- 建议在虚拟环境里安装，避免和系统 Python 的依赖互相打架
- 要读 Excel / Parquet / HDF5 / 数据库时，需要额外装对应的可选依赖（见「依赖」）
- 待处理的数据文件在本地可读路径下，或在脚本里显式给出网络地址、数据库连接串

---

## 使用

1. 装好 pandas 并确认版本：`python -c "import pandas as pd; print(pd.__version__)"`
2. 按数据形态选读入函数：CSV 用 `read_csv`、Excel 用 `read_excel`、JSON 用 `read_json`、数据库用 `read_sql`、Parquet 用 `read_parquet`
3. 先体检再动手：`df.shape` / `df.info()` / `df.describe()` / `df.isna().sum()`，确认行列数、dtype、空值分布
4. 清洗与计算：选列筛行、`assign` 派生列、`groupby().agg()` 聚合、`pivot_table()` 透视、`merge()` 合并
5. 落地：`to_csv` / `to_excel` / `to_parquet` 写文件，或 `to_sql` 写数据库
6. 完整操作清单、可复制的代码片段、高频坑对照表，见 `SKILL.md`

关键约定：所有涉及"改值"的操作都用 `.loc` 写成单条语句；从 3.0 起链式赋值不再生效。

---

## 依赖

- Python 3
- 必需：NumPy（官方安装页标注最低 1.26.0）、python-dateutil（最低 2.8.2）
- Windows 与 Pyodide 环境额外需要 tzdata（提供 IANA 时区库）
- 可选（按功能装）：
  - `pandas[excel]`：`read_excel` / `to_excel`
  - `pandas[performance]`：numexpr、bottleneck、numba，官方建议装
  - `pandas[html]`：`read_html`，需要 BeautifulSoup4 加 lxml 或 html5lib
  - `pandas[parquet]`：pyarrow，Parquet / Feather
  - `pandas[hdf5]`：PyTables
  - `pandas[postgresql,mysql,sql-other]`：SQLAlchemy 与各数据库驱动
  - `pandas[all]`：一次装齐
- 不需要账号或 API Key；只有连数据库、对象存储或需鉴权的数据源时才需要凭证

---

## 安全

- 不内嵌任何密钥
- 数据库与对象存储凭证从环境变量或配置文件读取，不要写进脚本、不要提交进仓库
- `read_csv` 可以直接读 URL，但不要用它去抓不可信来源并直接喂给后续处理链；采集与清洗分开，先落地再处理
- `to_sql` 前确认目标表名与 `if_exists` 策略（`fail` / `replace` / `append`），避免误覆盖生产表
- 处理他人数据时注意合规：只处理已获得授权的数据源，不要在结果里保留不必要的个人标识字段
- 脚本里不要对来源不明的 pickle / HDF5 文件调用反序列化接口

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pandas`
- 仓库：https://github.com/pandas-dev/pandas

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
