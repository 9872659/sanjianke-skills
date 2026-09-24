---
name: sanjianke-pygwalker
slug: sanjianke-pygwalker
displayName: 三剪客 · 数据可视化探索
description: "把 pandas / polars / pyarrow 数据表变成拖拽式可视化界面：直接跑一行代码就能在 Jupyter、Streamlit 里做交互式探索、图表状态存取与代码回导。含安装、常用操作与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "数据表的交互式探索层：`pyg.walk(df)` 起界面、`Walker` 对象复用、结果导出 HTML、图表状态存盘与回导 Python 代码、Streamlit 集成与本地/内核/云三种计算后端选择。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 数据可视化

---

# 三剪客 · 数据可视化探索

数据分析里最耗时间的一步，往往不是算，而是「看一眼」。你想按维度切一刀、换个图型、加个筛选，然后发现每换一次都要回去改代码重跑。pygwalker 解决的就是这个来回：把你的 DataFrame 直接变成一个可拖拽的可视化界面，字段拖到行/列上就出图，不需要写绘图代码。

它本质上是「ECharts 级别的图表库」的另一种打开方式——不追求把图导出成图片文件，而是让你在浏览器/Notebook 里连续地探索，最后**把探索结果回导成 Python 代码**或**把图表状态存成一个 JSON**，下次接着改。

**上游项目**：`pygwalker`　**仓库**：https://github.com/Kanaries/pygwalker

## 什么时候用 / 不用

**用它**：

- 用户手里已经有一个 `pandas` / `polars` / `pyarrow` 数据表，说「想看看到底长什么样」「哪个字段和哪个字段有关系」，需要连续地切维度、换图型。
- 想给自己或同事做一个**零前端的探索界面**：Streamlit 应用里挂一个 `StreamlitRenderer`，不用写任何图表配置代码。
- 需要**一键把探索过程变成可复现的产物**：把图表状态存成 JSON 反复加载，或者用 `to_code()` 把界面里的图表回导成 Python 代码。
- 需要把交互式图表**分享出去**：`to_html()` 导出一个自己能打开、能交互的 HTML 文件。
- 在 Notebook 里做完 EDA，想让数据清洗、类型修正、筛选这些操作在界面上点着做，而不是写一堆 `df[...]`。

**不要用它**：

- **要的是「跑批出一堆图片」**。它没有面向批量渲染的 CLI，也不负责生成 PNG/SVG 流水线；每天定时把 50 张图存成文件，用它属于走错赛道。
- **要做印刷级、固定版式的报表**。它的强项是交互探索，不是排版；要严格控制坐标轴、注释、分页，用图表库直接写更省事。
- **要一个多页面、带权限、带后端的生产级 BI 系统**。它是嵌进 Notebook / Streamlit 里的一个组件，不是一套 BI 平台。
- **数据极其敏感、要求全程离线不留任何外联**。默认配置下它会做版本更新检查；要用必须先切到离线档并确认没有走到云端计算（见下面「常见坑」第一条与第三条）。
- **运行环境里没有浏览器/Notebook 内核**。它的产物要么靠 Notebook 的 HTML 输出渲染，要么靠浏览器打开；纯终端环境里只能拿到 HTML 字符串，看不到图。

## 安装

需要先把 Python 环境准备好，再装包。官方 README 给的是 pip 与 conda 两条路。

```bash
# 方式一：pip（推荐，版本最新）
pip install pygwalker

# 想保持最新版
pip install pygwalker --upgrade

# 想提前用上还没正式发布的能力
pip install pygwalker --upgrade --pre
```

```bash
# 方式二：conda / mamba（走 conda-forge 频道）
conda install -c conda-forge pygwalker
# 或
mamba install -c conda-forge pygwalker
```

```bash
# 方式三：源码安装
git clone https://github.com/Kanaries/pygwalker.git
cd pygwalker
# 具体安装步骤以仓库 README 与 AGENTS.md / docs/DEVELOPMENT.md 为准
```

```bash
# 方式四：Streamlit 场景，除了 pygwalker 还要有 streamlit 本身
pip install pygwalker streamlit
```

本次没有抓到这个项目的官方 Docker 镜像用法；如需容器化部署，以官方文档和仓库 README 的最新内容为准，不要照搬其他项目的镜像名。

## 常用操作

**1. 最小用法：一行起界面**

在 Jupyter 里跑完这两行，下面就会出现一个可拖拽的探索界面。

```python
import pandas as pd
import pygwalker as pyg

df = pd.read_csv("./bike_sharing_dc.csv")
walker = pyg.walk(df)
```

**2. 指定图表状态文件与计算后端**

`spec_path` 用来存/取图表配置；`computation` 决定数据查询在哪算：`"browser"` 纯前端、`"kernel"` 走本地内核（基于 DuckDB）、`"cloud"` 走云端，不写则自动选择。

```python
walker = pyg.walk(
    df,
    spec_path="./chart_meta_0.json",   # 本地文件，加载与保存图表状态
    computation="kernel",              # 数据量偏大时用本地内核算
)
```

**3. 用可复用的 `Walker` 对象，自己决定在哪渲染**

```python
walker = pyg.Walker(df, spec_path="./chart_meta_0.json", computation="browser")
walker.show()       # 自动判断 Notebook 还是脚本模式
html = walker.to_html()
html = pyg.to_html(walker)
```

**4. 把界面里的图表回导成 Python 代码**

```python
code = walker.to_code(dataset_name="df")
print(code)
```

**5. 存过的旧配置先迁移再用**

```python
migrated_spec = pyg.spec.migrate(open("./old_chart_meta.json").read())
```

**6. 在 Streamlit 里挂一个探索界面**

关键点是**必须缓存 renderer**，否则每次交互都重建，内存会炸。

```python
from pygwalker.api.streamlit import StreamlitRenderer
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Use Pygwalker In Streamlit", layout="wide")
st.title("Use Pygwalker In Streamlit")

@st.cache_resource
def get_pyg_renderer() -> "StreamlitRenderer":
    df = pd.read_csv("./bike_sharing_dc.csv")
    # 想让界面里能保存图表配置，就设 spec_io_mode="rw"
    return StreamlitRenderer(df, spec_path="./gw_config.json", spec_io_mode="rw")

renderer = get_pyg_renderer()
renderer.explorer()
```

如果已经有 `Walker` 对象，也可以直接交给 renderer：

```python
walker = pyg.Walker(df, spec_path="./gw_config.json", computation="kernel")
renderer = StreamlitRenderer(walker)
renderer.explorer()
```

**7. 程序化导出图表（界面里存过之后）**

```python
walker = pyg.walk(df, spec_path="./chart_meta_0.json")
# 在界面里编辑图表并点保存
walker.save_chart_to_file("Chart 1", "chart1.svg", save_type="svg")
png_bytes = walker.export_chart_png("Chart 1")
svg_bytes = walker.export_chart_svg("Chart 1")
```

**8. 隐私与 token 配置：用 `config` 子命令**

```bash
pygwalker config --list
pygwalker config --set privacy=offline
pygwalker config --reset-all
pygwalker config -- --help      # 想看子命令的完整帮助用这种写法，别直接写 config --help
```

`privacy` 三档：`offline`（完全离线，不发数据也不请求接口）、`update-only`（只检查是否有新版本，默认值）、`events`（上报功能使用事件，用于产品优化，不上报你分析的数据）。`kanaries_token` 用于云端能力，需要自己去上游站点申请。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 在 Streamlit 里每拖动一次界面就卡一下，内存一路涨 | `StreamlitRenderer` 没做缓存，脚本每次重跑都重建一个 renderer | 用 `@st.cache_resource` 包住创建 renderer 的函数；官方示例就是这么写的 |
| 大数据集下界面卡死或浏览器崩 | 默认的计算位置不合适，全量数据被推到了前端 | 显式传 `computation="kernel"` 让查询在本地内核里算；数据量再大就先在 pandas 里做聚合，只把结果给它探索 |
| 参数 `use_kernel_calc` / `kernel_computation` / `cloud_computation` 还能用，但日志提示过时 | 这几个是历史写法，官方已给出弃用时间表 | 统一改用 `computation="kernel"` / `"browser"` / `"cloud"`；旧参数按官方说明将在 0.7.0 移除 |
| 写了 `pygwalker config --help` 结果报错或输出的不是你想看的东西 | `config` 子命令下面有个同名的 `help` 选项，容易被参数解析器抢走 | 在子命令和帮助标志之间插一个 `--`：`pygwalker config -- --help` |
| 想彻底离线，但不确定还有没有外联 | `privacy` 默认是 `update-only`，会去检查新版本 | 先 `pygwalker config --set privacy=offline`；同时确认没在用云端计算和带 token 的能力 |
| 指定 `spec` 传本地路径，行为不符合预期 | `spec` 的语义更宽（配置 ID、JSON 字符串、本地路径、远程 URL 都能塞），本地文件路径有专用参数 | 本地文件一律走 `spec_path`，远程地址或 JSON 字符串才用 `spec` |
| 在云端 Notebook 里图出不来 / 数据不显示 | 前端计算在部分托管环境里受限，或环境不支持对应的渲染通道 | 简化环境变量设置；换用 `computation="kernel"`；渲染通道参数 `env` 对 `Jupyter` / `JupyterWidget` 的旧别名也已进入弃用流程，新代码直接省略 `env` 用默认值即可 |
| `to_html()` 生成的 HTML 用 `file://` 直接打开是空白 | 部分浏览器对本地文件的资源加载有限制 | 起一个本地静态服务（例如 `python -m http.server`）再访问，或直接把 HTML 嵌进已有的 Web 应用里 |
| 字段类型、聚合方式推断得和预期不一样 | 它的类型推断服务于「快速探索」，不是严格的数据契约 | 在进入界面之前把 `dtypes`、缺失值、异常值处理好；列名尽量用有语义的名字，界面里识别更准 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视情况 | 默认档位下会检查版本更新；使用云端计算、云端分享或远程图表配置时会请求网络。完全离线的场景请切 `privacy=offline` 并避免云能力 |
| 读取文件 | 是 | 读 `spec_path` / `spec` 指向的图表配置文件；数据本身由你自己的代码读入（`pd.read_csv` 等） |
| 写入文件 | 是 | `spec_path` 会落盘保存图表状态；`to_html()`、`save_chart_to_file()`、`export_chart_png()` / `export_chart_svg()` 会写出文件 |
| 凭证 | 视情况 | 只有用云端能力时才需要上游站点的 token（通过 `config` 写入，或实例化时传 `kanaries_api_key`）。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 否 | 它是库调用；在 Streamlit / Notebook 里随宿主进程运行，不需要自己起常驻服务。想让别人访问界面，是宿主 Web 框架在监听端口 |

## 触发场景

- 「我这个 DataFrame 想直接看图表，不想写 matplotlib 代码」
- 「帮我把这个 csv 生成一个能拖拽的探索界面」
- 「在 Streamlit 里加一个可以自己拖字段的分析页面」
- 「我上次调好的图表配置想存下来，下次接着改」
- 「把界面里这张图变成能复现的 Python 代码」
- 「导出一个能发给同事看的交互式 HTML 图表」

## 能力边界

**覆盖**：

- 数据入口：`pandas` DataFrame、`polars`、`pyarrow` 表，以及可复用的 `Walker` 对象、数据库连接器与 SQL/数据源字符串（以 `walk()` 签名为准）。
- 交互探索：拖拽字段出图、实时刷新、缩放/平移/筛选、数据表预览与分布概览、图型切换。
- 运行环境：Jupyter Notebook / JupyterLab / Jupyter Lite、Google Colab、Kaggle、Databricks Notebook、VS Code 的 Jupyter 扩展，以及 Streamlit 集成。
- 产物：图表状态 JSON 的存与取、`to_html()` 导出交互式 HTML、`to_code()` 回导 Python 代码、按名称导出 SVG/PNG。
- 三种计算后端：浏览器端、本地内核（DuckDB）、云端。

**不覆盖**：

- 不负责数据采集。它消费你已经读进来的表，不做爬取、不做接口请求。
- 不做模型训练、统计检验、特征工程流水线。
- 不做打印报表排版，也没有批量出图的命令行。
- 不提供多用户权限、账号体系、协作注释这类平台能力（那属于它的云端产品形态，不是这个库本身）。
- 不内嵌任何数据源凭证；数据库连接、代理、token 都得你自己提供。

## 依赖条件

- 一个可用的 Python 环境；具体最低版本以安装时包元数据与官方文档为准，不在此处硬写版本号。
- `pip` 或 `conda` / `mamba` 之一；conda 路线依赖 conda-forge 频道。
- Streamlit 场景需要额外安装 `streamlit`。
- 浏览器端渲染要求客户端能跑 JS；Notebook 场景依赖内核与前端组件的正常通信。
- 使用 `computation="cloud"` 需要上游站点的 token，并且会走外部网络。

## 已知限制

- 项目正处在 0.6 线向 0.7 线过渡的阶段，`env`、`use_kernel_calc`、`kernel_computation`、`cloud_computation` 等参数都带了弃用标记；写代码时优先用新写法，避免升级即报错。
- 输出是交互式 HTML/前端组件，不能直接当图片塞进 PPT，需要走导出接口或截图。
- 图表配置的 schema 会演进，旧 `spec` 文件可能要先 `pyg.spec.migrate()` 再使用。
- 单表探索型工具，跨表建模、多数据源关联不是它的定位。
- 本文所写的参数名与档位来自抓取时的上游 README；上游迭代较快，执行前请以 `pygwalker config -- --help`、`pyg.walk` 的实际签名与官方文档为准。具体版本号、发布日期与 star 数不做断言。

## 自检清单

- [ ] 确认数据已经是 `pandas` / `polars` / `pyarrow` 之一，且列名、类型、缺失值都清理过。
- [ ] 确认运行环境是 Notebook、Streamlit 或其他有前端渲染能力的环境，而不是纯终端。
- [ ] Streamlit 场景：renderer 创建函数已用 `@st.cache_resource` 缓存。
- [ ] 数据量偏大时已显式指定 `computation="kernel"`，或先在 pandas 里做过聚合。
- [ ] 没有使用已弃用的 `use_kernel_calc` / `kernel_computation` / `cloud_computation` / `env` 旧别名。
- [ ] 本地图表状态文件用 `spec_path`，不是 `spec`。
- [ ] 想让图表配置在界面里可保存时，Streamlit 的 `spec_io_mode` 已设为 `"rw"`。
- [ ] 敏感数据场景：已确认 `privacy` 档位，且没有走到云端计算或带 token 的能力。
- [ ] 需要交付文件时，确认 `to_html()` / 导出接口的输出路径存在且文件非空。
- [ ] 用 `pygwalker config --list` 看过当前生效的配置，心里有数再动手。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/Kanaries/pygwalker | 上游仓库（安装与完整文档以它为准） |

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
