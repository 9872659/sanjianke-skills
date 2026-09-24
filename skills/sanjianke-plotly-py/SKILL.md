---
name: sanjianke-plotly-py
slug: sanjianke-plotly-py
displayName: 三剪客 · 交互式数据可视化图表
description: "plotly.py：交互式数据可视化图表的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "plotly.py：交互式数据可视化图表的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 数据可视化

---

# 三剪客 · 交互式数据可视化图表

它管的是「数据有了，怎么变成一张能看、能转、能分享的图」这一段：在 Python 里几行代码就能出
折线、柱状、散点、饼图、3D 曲面、地图、金融 K 线这类浏览器端可交互的图表，鼠标悬停有提示、
可以缩放框选，还能直接存成 HTML 或图片。写数据爬虫的人常在这里撞墙——静态绘图的中文和
导出麻烦，而它同时给出「交互 HTML」和「静态图片」两条落地产出路径。

**上游项目**：`plotly.py`　**仓库**：https://github.com/plotly/plotly.py

## 什么时候用 / 不用

**用它**：

- 你要把采集或分析的结果出成给人看的图：趋势、分布、占比、地区对比。
- 你需要图表可交互——能缩放、能悬停看数值、能点图例开关数据系列。
- 你要把图嵌进 Jupyter 笔记本、导出成单文件 HTML 发给别人，或塞进用 Dash 搭的看板。
- 你需要静态图片产物（PNG / JPG / SVG / PDF）写进报告、文档或素材流水线。
- 你要一张现成的、带大量图表类型的库来试配图风格，而不是自己从底层画原语。

**不要用它**：

- 你要的是数据本身。它只负责画图，不抓数据、不存数据。
- 你需要出版级排版精度的静态图，且不愿为核心渲染再装 Chrome / Chromium。这种场景用 Matplotlib 一类更直接。
- 你要做实时刷新的重型仪表盘或流式渲染。这类需求用专门的 Web 前端框架更合适，它是绘图库不是前端框架。
- 你只要几张临时图、又不想多装依赖，且环境里连 Chrome 都不能装：交互 HTML 能出，静态图片会卡住。
- 你要的图表类型它没有（例如甘特图或某些统计图的特殊变体），这时换别的库成本更低。

## 安装

```bash
# 基础安装（pip）
pip install plotly

# conda 用户
conda install -c conda-forge plotly
```

```bash
# 想在 Jupyter 里当控件用（可交互、可回写）
pip install jupyter anywidget
conda install jupyter anywidget
```

```bash
# 静态图片导出：官方要求 Kaleido 1.0 或更高
pip install -U kaleido
conda install -c conda-forge python-kaleido
```

```bash
# Kaleido 出图需要 Chrome / Chromium。默认复用系统上已装的浏览器；
# 找不到时可以执行官方提供的这条命令来装（具体行为以官方静态导出文档为准）
plotly_get_chrome
```

## 常用操作

```python
# 1. 最小示例：一张柱状图，show() 在笔记本里内联渲染，在脚本里会开浏览器
import plotly.express as px
fig = px.bar(x=["a", "b", "c"], y=[1, 3, 2])
fig.show()
```

```python
# 2. 落一个交互 HTML：单文件、离线可开、能直接发给别人
fig.write_html("chart.html")
```

```python
# 3. 存静态图片：需要先装 Kaleido 且能拿到 Chrome / Chromium
fig.write_image("chart.png")
fig.write_image("chart.svg")
```

```python
# 4. 结构化输出：把图定义成 JSON，交给前端或别的服务去渲染
payload = fig.to_json()
```

```python
# 5. 精细控制：express 出粗图，graph_objects 补细节（标题、轴、图例、标注）
import plotly.graph_objects as go
fig = go.Figure()
fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode="lines+markers", name="系列 A"))
fig.update_layout(title="标题", xaxis_title="X", yaxis_title="Y")
fig.show()
```

```python
# 6. 数据量大的散点：显式打开 WebGL 版本，别用默认的 SVG 散点
import plotly.express as px
fig = px.scatter(df, x="x", y="y", render_mode="webgl")
fig.show()
```

`write_image` 支持的格式、渲染后端选项与分辨率参数随版本变化，具体参数以官方静态导出文档和
`help(fig.write_image)` 为准，不要凭印象传参。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 中文标题、坐标轴、图例显示成方块 | 渲染后端里没有中文字体，或字体族没指定 | 给图面显式指定一个系统里确实存在的中文字体；出图环境与开发环境字体要一致 |
| `write_image` 报错说找不到浏览器 | Kaleido 出图依赖 Chrome / Chromium，默认复用系统安装 | 装好 Chrome / Chromium，或用官方命令补装；容器镜像里要显式带上浏览器 |
| 装了 Kaleido 仍然导出失败 | 绘图库与 Kaleido 的版本要求不匹配 | 按官方静态导出文档对齐版本要求（文档明确要求 1.0 或更高） |
| 本地能互动、发给别人就打不开 | HTML 里引用了在线 JS，接收方没网 | 用自包含（内联）方式写出 HTML；代价是文件变大 |
| 图表数据量大时页面卡死 | 默认散点是 SVG 逐个节点渲染 | 换 WebGL 渲染模式，或先聚合降采样再画 |
| 依赖装到一半报 pandas / numpy 版本冲突 | 绘图层的 DataFrame 接口对 `pandas` 有版本范围要求 | 先 `pip check` 看清冲突链，在独立虚拟环境里按需锁版本 |
| 出现 `nbformat` 相关报错 | 只有 JSON 内联渲染路径需要 `nbformat`，环境里缺 | 补装 `nbformat`，或改用 HTML / 图片导出而不是 JSON 内联 |
| 老代码大面积报错 | 版本演进后子模块收进包命名空间，旧的顶层导入方式不再可用 | 按官方迁移说明改成新的导入路径，别逐条去猜 |
| 容器 / CI 里图出得来但排版乱 | 无头环境没有字体配置，回退到了默认字体 | 镜像里装中文字体并刷新字体缓存，再跑一次导出 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（默认） | 图表计算全在本地；只有显式使用在线渲染能力（云端渲染、在线图案与底图资源）时才需要出网 |
| 读取文件 | 视用法 | 读入要绘图的数据文件（CSV / Excel 等由你的代码负责） |
| 写入文件 | 是 | 导出 HTML、PNG / JPG / SVG / PDF 等产物 |
| 凭证 | 否 | 本地绘图不需要任何 Key；只有用官方托管服务时才涉及账号 |
| 子进程 / 后台常驻 | 是 | 静态导出时会拉起 Kaleido 的渲染进程（内部驱动 Chrome / Chromium） |

## 触发场景

- 「把这批数据画成折线图，要能悬停看数值那种」
- 「帮我出一张可以发给客户、双击就能在浏览器里打开的交互图表」
- 「图表要导出 PNG 放进周报，中文字体别乱码」
- 「同一份数据想在笔记本里看，也想导出成图片存档」
- 「带几十种图表的绘图库，帮我挑一种适合画占比 / 地区分布的」
- 「我环境里导出图片总报错，看看是不是浏览器或版本的问题」

## 能力边界

**覆盖**：

- 交互式图表：折线、柱状、散点、饼图、箱线、热力、3D 曲面、地图、金融 K 线等一大批类型（具体种类以官方文档为准）。
- 两条产出路径：交互 HTML（含自包含离线单文件）与静态图片导出（PNG / JPG / SVG / PDF，需 Kaleido 与浏览器）。
- 三种使用形态：Jupyter 笔记本内联、导出的独立 HTML 文件、嵌进 Dash 应用。
- 两层 API：`plotly.express` 面向 DataFrame 的快速出图，`plotly.graph_objects` 面向精细控制。
- 结构化输出：把整张图序列化成 JSON，交给前端或其他服务渲染。

**不覆盖**：

- 数据获取与清洗：不做爬虫、不做数据库连接、不做缺失值处理。
- 后端服务：不提供 HTTP 服务或持久化存储；要做可交互看板请配合 Dash 一类框架。
- 浏览器渲染之外的排版引擎：复杂多子图组版、中文竖排、印刷级出血这类需求超出它的定位。
- 不是所有图表类型都有：某些专用图形需要换库，或自己用底层图元拼。
- 不负责图表的可访问性与无障碍替代文本，这些要在你的产出流程里补。

## 依赖条件

- Python 环境；用 pip 或 conda 安装。
- 在 Jupyter 里作为控件使用需要 `jupyter` 与 `anywidget`。
- 静态图片导出需要 Kaleido（官方要求 1.0 或更高），并且环境里要有 Chrome 或 Chromium。
- 走 DataFrame 快速接口时需要 `pandas`；内联到笔记本的 JSON 渲染路径还需要 `nbformat`。

## 已知限制

- 静态导出依赖外部浏览器：无头容器、CI 环境里要自己把 Chrome / Chromium 和字体装进镜像。
- 导出图片里的文字字体来自渲染环境，开发机与出图机不一致时会出现中文乱码或宽度变化。
- 版本边界变化明显：子模块收进包命名空间之后，旧版顶层导入写法不再可用。
- 交互 HTML 若引用在线 JS，离线环境打不开；自包含写法会显著增大文件体积。
- 大数据量默认走 SVG 渲染会明显变慢，需要显式切换渲染模式或先做聚合。

## 自检清单

- 目标产出是交互 HTML 还是静态图片？两条路径的依赖完全不同，先定下来再装。
- 要导出图片时，Kaleido 装了吗？版本满足官方要求吗？系统里有 Chrome / Chromium 吗？
- 出图环境里有中文字体吗？图面上指定字体了吗？
- 交互图是给别人离线看的吗？是的话用自包含写法，别让它去网上取 JS。
- 数据量多大？超过常规量级就换 WebGL 渲染模式或先降采样。
- 用的是 `express` 还是 `graph_objects`？需要精细控制时不要硬在 `express` 上凑。
- 现有代码是老版本写法吗？先按官方迁移说明改导入路径，再排查别的报错。
- 图要进报告或素材流水线时，分辨率与格式是否满足下游要求？

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/plotly/plotly.py | 上游仓库（安装与完整文档以它为准） |

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
