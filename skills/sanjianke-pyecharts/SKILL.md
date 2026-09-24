---
name: sanjianke-pyecharts
slug: sanjianke-pyecharts
displayName: 三剪客 · Python 图表生成
description: "用 Python 写配置、交给 ECharts 渲染的图表库：链式 API 出 30 多种图表、400+ 地图资源、导出可交互 HTML、在 Notebook 与 Web 框架里嵌入，以及转静态图片的额外依赖。含安装、常用操作与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Python 里的 ECharts 绑定：`Bar()` 链式出图、`render()` 导 HTML、`Page` 拼多图、Notebook 内嵌、Flask/Django 挂载、`make_snapshot` 转 PNG 与它背后的 Selenium / PhantomJS 依赖。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 数据可视化

---

# 三剪客 · Python 图表生成

如果你在 Python 里画图，嫌 `matplotlib` 的默认样式不够现代、又不想为了几张图去写 JavaScript，pyecharts 就是中间那条路：**你用 Python 描述图表，它把配置翻译成 ECharts 的配置项，最后吐出一个 HTML 文件**。样式、交互、提示框、缩放这些都是 ECharts 现成的能力，你不用碰 JS。

它最大的特点是「**产物是网页而不是图片**」。做后台报表、做数据看板、往 Flask/Django 里嵌一段图表，这一条就值回票价；反过来，如果你要的是一张 PNG 塞进 Word，那还得额外配一套无头浏览器（见下面「安装」和「常见坑」）。

**上游项目**：`pyecharts`　**仓库**：https://github.com/pyecharts/pyecharts

## 什么时候用 / 不用

**用它**：

- 用户说「用 Python 出几张好看的图」「要能鼠标悬停看数值的那种」，而不是只要一张静态图。
- 产物要**嵌进网页**：Flask、Sanic、Django 里挂一段交互式图表，或者在 Jupyter / marimo 里直接显示。
- 需要**地图类可视化**：它自带 400+ 地图资源，按地区编码填数据就能画，不用自己找 geojson。
- 需要**组合图表**：多张图拼一个页面、一张图里叠加折线柱状、时间轴轮播，这些都有对应的组合类。
- 需要高度定制的坐标轴、图例、提示框、主题配色，并且希望这些配置都用 Python 对象写出来、能进版本管理。

**不要用它**：

- **只想快速画一张统计图做中间过程**。`matplotlib` / `seaborn` 起手更快，pyecharts 是「要交付」时才划算。
- **必须要 PNG / JPG 文件**。它原生产物是 HTML；转图片要再装无头浏览器驱动，多一层环境依赖和踩坑成本。
- **做大规模统计计算或数据分析**。它只负责画，不负责算；分组聚合、透视表该用 `pandas`。
- **需要服务端渲染截图、跑批出几千张图**。每次快照都要启动浏览器，这条链路重且慢，更适合专门的渲染服务。
- **用的是老版本代码（0.5.x 那套 API）**。v0.5.x 与 v1 之后**不兼容**，0.5.x 已不再维护；照抄网上 0.5.x 的示例会直接报错。

## 安装

```bash
# 正式版（v1 以上）
pip install pyecharts -U

# 需要老版本 0.5.11 的场景（一般不推荐，已停止维护）
pip install pyecharts==0.5.11
```

```bash
# 源码安装
git clone https://github.com/pyecharts/pyecharts.git
cd pyecharts
pip install -r requirements.txt
python setup.py install
```

```bash
# 想把图导出成 PNG：还要装一个快照驱动（二选一）
pip install snapshot-selenium     # 基于 Selenium，需要本机有浏览器与对应驱动
pip install snapshot-phantomjs    # 基于 PhantomJS
```

版本线要分清楚：

| 版本线 | 说明 |
|---|---|
| v0.5.x | 只在该分支维护历史的代码，官方已不再维护；文档在独立的 05x 站点 |
| v1 | 全新的写法（链式调用从这一版开始），仅支持 Python 3.7+ |
| v2 | 渲染基于 ECharts 5.4.1+，文档与示例位置与 v1 相同 |

本次没有抓到这个项目的官方 Docker 镜像；要容器化就把「Python 环境 + 无头浏览器 + 字体」一起打进镜像，具体以官方文档为准。

## 常用操作

**1. 最小可用：出柱状图并存成 HTML**

```python
from pyecharts.charts import Bar
from pyecharts import options as opts

bar = (
    Bar()
    .add_xaxis(["衬衫", "毛衣", "领带", "裤子", "风衣", "高跟鞋", "袜子"])
    .add_yaxis("商家A", [114, 55, 27, 101, 125, 27, 105])
    .add_yaxis("商家B", [57, 134, 137, 129, 145, 60, 49])
    .set_global_opts(title_opts=opts.TitleOpts(title="某商场销售情况"))
)
bar.render()          # 默认写出 render.html
```

不习惯链式调用也可以一行一行写，两种写法等价：

```python
bar = Bar()
bar.add_xaxis(["衬衫", "毛衣", "领带"])
bar.add_yaxis("商家A", [114, 55, 27])
bar.set_global_opts(title_opts=opts.TitleOpts(title="某商场销售情况"))
bar.render()
```

**2. 指定输出路径**

```python
bar.render("output/bar.html")
```

**3. 在 Notebook 里内嵌显示**

在 Jupyter / JupyterLab 里，用 `render_notebook()` 直接把图表显示在单元格下面。

```python
bar.render_notebook()
```

如果渲染通道判断得不对（比如某些 Notebook 环境），可以显式指定；可选项以官方文档的「全局配置项」一节为准。

**4. 一个页面拼多张图**

```python
from pyecharts.charts import Bar, Line, Page

page = Page(layout=Page.SimplePageLayout)
page.add(bar, line)
page.render("report.html")
```

`Page` 提供几种布局常量用于控制多图排布；具体常量名以当前版本文档为准。

**5. 换图型：折线、饼图、散点、地图**

同一个套路——从 `pyecharts.charts` 里换类名，其余写法基本一致。

```python
from pyecharts.charts import Line, Pie, Map

line = Line().add_xaxis(["一月", "二月", "三月"]).add_yaxis("销量", [10, 20, 30])
pie = Pie().add("", [("A", 10), ("B", 20), ("C", 30)])
```

**6. 主题与初始化配置**

主题、画布宽高、渲染器这类都走 `InitOpts`：

```python
from pyecharts.charts import Bar
from pyecharts import options as opts

bar = (
    Bar(init_opts=opts.InitOpts(width="1000px", height="600px", theme="dark"))
    .add_xaxis(["一月", "二月", "三月"])
    .add_yaxis("销量", [10, 20, 30])
    .render("themed.html")
)
```

`theme` 的具体可选值、`InitOpts` 支持的全部参数，以官方文档的全局配置项页面为准。

**7. 转成图片（需要额外装快照驱动）**

```python
from snapshot_selenium import snapshot as driver
from pyecharts import options as opts
from pyecharts.charts import Bar
from pyecharts.render import make_snapshot


def bar_chart() -> Bar:
    c = (
        Bar()
        .add_xaxis(["衬衫", "毛衣", "领带", "裤子", "风衣", "高跟鞋", "袜子"])
        .add_yaxis("商家A", [114, 55, 27, 101, 125, 27, 105])
        .add_yaxis("商家B", [57, 134, 137, 129, 145, 60, 49])
        .reversal_axis()
        .set_series_opts(label_opts=opts.LabelOpts(position="right"))
        .set_global_opts(title_opts=opts.TitleOpts(title="Bar-测试渲染图片"))
    )
    return c


make_snapshot(driver, bar_chart().render(), "bar.png")
```

**8. 嵌进 Web 框架**

Flask / Django / Sanic 这类框架的集成方式，官方文档有专门的章节（模板注入与嵌入渲染）；照官方示例接即可，不要自己拼 HTML 字符串。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 照抄网上示例，报 `ImportError` / `AttributeError`：`Bar` 没有某个方法 | 抄的是 0.5.x 时代的代码，而 v0.5.x 与 v1 之后的 API **不兼容** | 认准版本线：v1+ 用 `pyecharts.charts` 的类 + 链式调用 + `from pyecharts import options as opts`；老代码去 05x 文档对照 |
| `bar.render()` 出来了 HTML，但双击打开是空白 | HTML 默认从 CDN 加载 ECharts 的 JS，离线或网络受限时加载失败 | 联网打开，或改用「内嵌 JS 资源」的输出方式（`CurrentConfig` 里可配置在线/本地 host 与内嵌策略），让 HTML 自包含 |
| 装完 pyecharts 就调 `make_snapshot`，报找不到驱动 | 转图片是**可选能力**，需要另外装 `snapshot-selenium` 或 `snapshot-phantomjs`，并配好浏览器/驱动 | `pip install snapshot-selenium`，确认本机浏览器与 driver 版本匹配；或改走「先出 HTML 再人工截图」 |
| 中文标签在导出的图片里变成方框 | 无头浏览器容器里没有中文字体 | 在镜像/系统里装中文字体；这是渲染环境问题，不是图表配置问题 |
| Notebook 里 `render()` 只落盘不显示，或者显示了两个图 | `render()` 是写文件，Notebook 内嵌要用 `render_notebook()` | Notebook 用 `render_notebook()`；Web 场景用「嵌入渲染」那条路 |
| 地图图画不出来 / 报缺少地图 | 地图数据要按地区名或编码匹配，名称写法不标准就匹配不上 | 用标准的行政区全称（与官方示例一致）；确认当前版本对应的地图资源已包含该地区 |
| 想把 `df` 直接丢进去画图，报类型错 | 它接收的是 list 一类的基础结构，不认识 DataFrame | 先用 `pandas` 把列取出来转成 list：`df["col"].tolist()` |
| 自定义 JS 回调（格式化标签等）写进 `opts` 后没生效 | 字符串会被当成普通文本，不会当函数执行 | 用官方提供的 JS 代码包装类型（`JsCode` 一类的写法）包住，具体写法以官方文档为准 |
| 多个图表对象复用同一个渲染结果，样式互相串 | 图表对象的 `options` 是实例状态，重复 `add_*` 会累加 | 每张图单独构造对象；需要复用就先定义构造函数，每次返回一个新实例 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视情况 | 渲染出来的 HTML 默认要从 CDN 拉 ECharts 的 JS；换成内嵌资源或本地 host 后可以完全离线。图表数据本身不联网 |
| 读取文件 | 否 | 它接收的是内存里的 Python 数据；只有嵌进 Web 框架时由你的框架去读模板 |
| 写入文件 | 是 | `render()` 写 HTML；`make_snapshot()` 写 PNG/其他图片格式 |
| 凭证 | 否 | 不需要任何 API Key 或账号。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是（仅转图片时） | `make_snapshot()` 会拉起无头浏览器进程去截图；纯出 HTML 的用法不需要 |

## 触发场景

- 「用 Python 给我画个柱状图 / 折线图 / 饼图，要能交互的」
- 「把这个 csv 出成一张网页图表，我要放进后台」
- 「在 Flask 页面里嵌一个 ECharts 图」
- 「画一张中国地图，按省份填数据」
- 「Jupyter 里直接显示图表，别只生成文件」
- 「把这个图导出成 PNG 我要贴报告里」

## 能力边界

**覆盖**：

- 30 多种图表类型，覆盖常见统计图、组合图、地理图、关系图、3D 图等（具体清单以 `pyecharts.charts` 与官方画廊为准）。
- 400+ 地图资源，支持按地区填数据的地理可视化。
- 高度可配的坐标轴、图例、提示框、标注、主题、动画（走 `pyecharts.options`）。
- 多图组合与页面拼装：叠加、组合、Page 布局、时间轴轮播等。
- 多种渲染出口：独立 HTML、Notebook 内嵌、Web 框架内嵌、静态图片快照。
- 主题系统，以及替换 JS 资源地址（在线 / 本地 / 内嵌）的能力。

**不覆盖**：

- 不做数据分析与统计计算，不做数据清洗，不读数据源；这些交给 `pandas` / 数据库客户端。
- 不产出 PDF、Word、Excel 这类文档格式；想要这些得自己把 HTML 或图片再拼进去。
- 不提供图表托管服务。`render()` 写出的是一个静态文件，要长期可访问需要你自己部署 Web 服务。
- 不做实时数据推送与流式刷新；数据更新要重新生成。
- 不做无头浏览器管理，转图片的浏览器与驱动要你自己装好。

## 依赖条件

- Python 3.7 及以上（v1 / v2 版本线的要求；0.5.x 那条线才支持更老的 Python，但已停止维护）。
- 能访问 PyPI 安装 `pyecharts`。
- 渲染 HTML 时，访问端要能联网加载 JS 资源，或者你改用内嵌/本地资源方式。
- 转静态图片需要额外安装快照驱动之一（`snapshot-selenium` 或 `snapshot-phantomjs`），并准备浏览器环境；容器场景还要装中文字体。
- Notebook 场景依赖 Notebook 环境本身；Web 集成依赖对应框架的项目结构。

## 已知限制

- v0.5.x 与 v1 之后不兼容，网上大量教程停留在老版本，照抄必踩坑。
- 原生产物是 HTML 而非图片，图片导出是附加能力且依赖外部浏览器。
- 地图资源虽多，但地区名称匹配对写法敏感；数据里的名称不标准会导致图上无数据。
- 图表配置项非常庞大，`opts` 的对象树需要查文档；本文只给出主干用法，细节一律以官方文档的配置项章节为准。
- 上游迭代中部分类与参数可能随版本调整；执行前请以实际安装版本的文档与示例为准。具体版本号、发布日期与 star 数不做断言。

## 自检清单

- [ ] 确认当前装的是 v1+ 还是 0.5.x，代码写法与版本线一致（不要混着抄）。
- [ ] 用的是 `render()`（写文件）还是 `render_notebook()`（Notebook 内嵌）——别用错。
- [ ] 需要交付图片时，快照驱动已经装上，且浏览器与 driver 版本匹配。
- [ ] 离线环境：已确认 HTML 能自行拿到 JS 资源，不依赖 CDN。
- [ ] 容器/无头环境：已安装中文字体，避免中文标签显示成方框。
- [ ] 数据源是 DataFrame 时，已转成 `list` 再喂给 `add_yaxis` / `add_xaxis`。
- [ ] 地图类图表：地区名称与官方示例的写法一致。
- [ ] 多张图共用逻辑时，每张图各自构造实例，没有复用同一个对象重复 `add_*`。
- [ ] 自定义 JS 回调已用官方提供的包装类型，而不是裸字符串。
- [ ] 确认输出路径可写，渲染后检查生成文件非空。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/pyecharts/pyecharts | 上游仓库（安装与完整文档以它为准） |

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
