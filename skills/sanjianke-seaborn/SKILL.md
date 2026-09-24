---
name: sanjianke-seaborn
slug: sanjianke-seaborn
displayName: 三剪客 · 统计数据可视化
description: "基于 matplotlib 的统计数据可视化库：用一行代码画出分布、分类、关系、回归与矩阵图，含主题与调色板设置、数据集接口、对象接口用法，以及版本升级与新环境下的常见坑。遇到问题可加技术微信 9872659。"
summary: "把「这批数据分布长什么样、两组之间有没有关系」快速画成图：安装与依赖、五种图的典型写法、主题与调色板、数据集接口与离线注意点、类别图默认外观变更等常见坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 数据可视化

---

# 三剪客 · 统计数据可视化

分析完一批数据，下一步通常是「看一眼」：这列是不是偏态、两列有没有相关性、不同分组的分布差多少。直接用底层绘图库写这些图，光是想清楚要画哪些元素就要写一长串代码。

这个库做的事情是提供一层高层封装：拿到 DataFrame 后，用「把哪些列映射到 x / y / 颜色 / 分面」的方式描述你要看的关系，它负责把统计变换和图形元素补齐，出来的图默认就有配色和样式。它底层仍然是 matplotlib，所以画完之后照样能用 matplotlib 的 API 继续改、继续存。

**上游项目**：`seaborn`　**仓库**：https://github.com/mwaskom/seaborn

## 什么时候用 / 不用

**用它**：

- 用户说「帮我把这些数据的分布画出来」，或者「看看这两列有没有相关性」。
- 需要一眼比较多组：不同类别的箱线图、分组柱状图、按类别着色的散点图。
- 做探索性数据分析，想快速串起一整套图（分布 → 关系 → 相关性矩阵）而不是逐个手写。
- 需要一个开箱就有较好默认配色与样式的统计图，而不是从零调 matplotlib 参数。
- 要把图落到文件里写进报告或看板。

**不要用它**：

- **要交互式图表**。它的输出是静态图；需要缩放、悬浮提示、页面里可交互，应该换交互式可视化库。
- **要仪表盘或 Web 前端图表**。那是前端图表库的领域，它只产出图片文件或 matplotlib 图对象。
- **要画示意图、流程图、信息图**。它面向统计图形，不擅长安卓式排版的图形设计。
- **只有几行数据、想画个最简单的折线**。直接用 matplotlib 就够了，多一层封装反而多一层要记的参数。
- **数据还没整理成结构化表格**。它的接口围绕 DataFrame / 向量展开，先把数据整理干净再进来。

## 安装

官方要求 Python **3.10 或更高**。安装时会带上 numpy、pandas、matplotlib；部分高级统计功能另外需要 scipy 和 / 或 statsmodels。

```bash
# pip（官方 README 给出的写法用 uv pip，普通 pip 同理）
pip install seaborn

# 连可选的统计依赖一起装
pip install seaborn[stats]
```

```bash
# conda
conda install seaborn
# 主仓库的发布通常滞后于 PyPI，追新可以指定 conda-forge
conda install -c conda-forge seaborn
```

```bash
# 从源码安装（clone 仓库后）
git clone https://github.com/mwaskom/seaborn.git
cd seaborn
pip install -e .
```

验证：

```bash
python -c "import seaborn as sns; print(sns.__version__)"
```

## 常用操作

**1. 先设主题，再画图**

```python
import seaborn as sns
import matplotlib.pyplot as plt

sns.set_theme()                       # 一次性设定配色与样式上下文
df = sns.load_dataset("penguins")     # 内置示例数据集，需要联网下载
sns.scatterplot(data=df, x="bill_length_mm", y="bill_depth_mm", hue="species")
plt.show()
```

**2. 看单列分布**

```python
sns.histplot(data=df, x="body_mass_g", bins=30)   # 直方图
sns.kdeplot(data=df, x="body_mass_g", hue="species")  # 核密度估计
```

**3. 比较多个分组的分布**

```python
sns.boxplot(data=df, x="species", y="body_mass_g")
# 想要每个箱子不同颜色（旧版默认行为），显式给一个冗余 hue：
sns.boxplot(data=df, x="species", y="body_mass_g", hue="species", legend=False)
```

**4. 相关性矩阵**

```python
corr = df.select_dtypes("number").corr()
sns.heatmap(corr, annot=True, cmap="vlag", center=0)
```

**5. 一眼看两两关系（成对图）**

```python
sns.pairplot(df, hue="species")
```

**6. 用对象接口做更细的声明式控制**

```python
import seaborn.objects as so

(
    so.Plot(df, x="bill_length_mm", y="bill_depth_mm", color="species")
    .add(so.Dot())
    .add(so.Line(), so.PolyFit())
    .label(x="喙长 (mm)", y="喙深 (mm)")
)
```

**7. 落盘成图片**

```python
sns.set_theme(context="talk")                 # 报告里字号可读性更好
ax = sns.histplot(data=df, x="body_mass_g")
fig = ax.figure
fig.savefig("dist.png", dpi=200, bbox_inches="tight")
```

**8. 内置数据集相关工具**

```python
sns.get_dataset_names()    # 列出可用的示例数据集名
sns.get_data_home()        # 看示例数据集的缓存目录
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `sns.load_dataset(...)` 报网络错误或卡住 | 示例数据集是从在线仓库拉取并缓存到本地的，**需要联网** | 有网时重跑一次即会缓存；离线环境不要依赖它，改用自己准备的 DataFrame |
| 升级后箱线图 / 柱状图「颜色全变成一个色」 | 类别绘图函数在 0.13 版本被重写：默认只给单色，除非显式指定 `hue` | 想恢复旧外观就显式加冗余 `hue`：`hue="x"`；想固定旧调色板可显式 `palette="deep"` |
| 传了 `palette` 但颜色没生效，还伴随告警 | 新版不再支持「不指定 `hue` 就传 `palette`」这种写法 | 显式指定 `hue` 再配 `palette`；想按单色做渐变改用 `palette="dark:{color}"` / `palette="light:{color}"` 这类写法 |
| 报错提示没有 `scipy` / `statsmodels` | 部分统计功能（如回归拟合、核密度等）依赖可选包，基础安装不带 | `pip install seaborn[stats]`，或按报错提示单独装缺失的包 |
| 中文标签变成方块 | matplotlib 默认字体不含中文字形，这是 matplotlib 的问题而不是库的问题 | 在绘图前设定支持中文的字体：`plt.rcParams["font.sans-serif"] = ["..."]`（按系统已装字体填），并按需设 `axes.unicode_minus=False` |
| 图上元素看着正常，但 `plt.show()` 没反应 | 在无图形界面的环境（服务器、容器、CI）里没有可用的显示后端 | 不要依赖 `show()`；直接保存文件（`fig.savefig(...)`），或显式使用非交互后端 |
| 图级函数返回的对象不能当坐标轴用 | 带 `relplot` / `displot` / `catplot` 这类名字的是**图级接口**，返回的是带多个子图的网格对象，不是单个 Axes | 需要单张坐标轴时用 `scatterplot` / `histplot` / `boxplot` 这类轴级函数；确实要用网格时按网格对象的 API 操作 |
| 重复绘图时图上叠了上一次的内容 | 在同一 Axes 上反复调用相当于叠加图层 | 每次画新图前建新图：`plt.figure()` / `plt.subplots()`；或在 notebook 里分单元格画 |
| 传给 `data=` 的列名不存在，报 KeyError | 列名拼写或类型不对（例如把索引当列用） | 先 `print(df.columns)` 核对；需要索引参与时先 `df.reset_index()` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视情况 | 仅在使用 `load_dataset()` 等内置数据集接口时需要联网下载并缓存；用自己传入的 DataFrame 画图不需要网络 |
| 读取文件 | 视情况 | 读取待分析的数据文件（通常由 pandas 读取后再交给本库） |
| 写入文件 | 视情况 | 通过 matplotlib 的 `savefig` 把图落盘成 PNG / PDF / SVG 等 |
| 凭证 | 否 | 不需要任何账号或密钥 |
| 子进程 / 后台常驻 | 否 | 纯 Python 库；Jupyter 内核或脚本进程由使用者自行管理 |

## 触发场景

- 「帮我把这批数据的分布画出来看看」
- 「这两列数据有没有相关性，画个热力图」
- 「按不同类别对比一下箱线图」
- 「画一组图我要放进报告里，要好看一点」
- 「plot a correlation heatmap of this dataframe」
- 「这批数据我想先做一轮探索性分析」

## 能力边界

**覆盖**：

- 关系图：`scatterplot` / `lineplot`，以及图级 `relplot`。
- 分布图：`histplot` / `kdeplot` / `ecdfplot` / `rugplot`，以及图级 `displot`。
- 类别图：`stripplot` / `swarmplot` / `boxplot` / `violinplot` / `boxenplot` / `pointplot` / `barplot` / `countplot`，以及图级 `catplot`。
- 回归图：`lmplot` / `regplot` / `residplot`（依赖 statsmodels）。
- 矩阵图：`heatmap` / `clustermap`（后者依赖 scipy 做层次聚类）。
- 多图网格：`FacetGrid` / `PairGrid` / `JointGrid` 及其便捷函数 `pairplot` / `jointplot`。
- 主题与配色：`set_theme` / `axes_style` / `set_context` / `color_palette` 及一系列调色板函数。
- 对象接口：`seaborn.objects`（`Plot` 加各类 Mark / Stat / Move / Scale）。
- 通过 dataframe 交换协议接受 pandas 之外的数据框对象（内部仍会转成 pandas）。

**不覆盖**：

- 不做交互式图表、不产出仪表盘或网页图表。
- 不提供数据加载、清洗、建模能力；它只负责把已有的结构化数据画出来。
- 不做非统计类图形（流程图、示意图、图标设计）。
- 不提供独立的命令行工具；它是 Python 库，想在命令行出图需要自己写一行脚本。
- 内置示例数据集依赖联网获取，离线场景不可用。

## 依赖条件

- Python 3.10 及以上（官方要求）。
- numpy、pandas、matplotlib（安装时必备）。
- scipy 与 / 或 statsmodels（可选）：回归图、聚类热图、部分统计功能需要。
- 使用内置示例数据集时需要网络。
- 需要中文标签时，系统需装有支持中文的字体，并在 matplotlib 中显式指定。

## 已知限制

- 输出为静态图，没有交互能力；交互需求要换工具。
- 对象接口仍在演进，不同小版本间 API 可能有调整；使用前建议对照官方 API 文档。
- 类别绘图函数在 0.13 版本有较大行为变更（默认配色、`dodge` 默认值、部分参数改名或废弃），升级旧代码必须逐图核对输出。
- 直接用底层接口（如 `matplotlib.pyplot`）与本库混用时，图层归属和主题生效顺序容易出错，需明确谁在什么时候设了 rcParams。
- 具体版本号、发布日期与 star 数请以仓库与官方文档页实时信息为准，此处不做断言。

## 自检清单

- [ ] Python 版本 ≥ 3.10。
- [ ] 已导入 pandas 并确认数据是结构化表格，列名拼写与 `data=` 参数一致。
- [ ] 需要统计功能（拟合、聚类等）时，已装 `seaborn[stats]` 或其缺失的具体包。
- [ ] 打算用内置示例数据集的话，确认当前环境能联网。
- [ ] 需要中文标签时，已设置支持中文的字体并处理负号显示。
- [ ] 在无显示后端的环境里，使用 `savefig` 而不是 `show`。
- [ ] 区分轴级函数与图级函数：要单张 Axes 用 `scatterplot` 这一档，要网格用 `relplot` 这一档。
- [ ] 旧代码升级到新版本后，逐图核对类别图的配色与默认外观是否符合预期。
- [ ] 输出文件已生成且非空（检查文件大小，而不是只看命令没报错）。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/mwaskom/seaborn | 上游仓库（安装与完整文档以它为准） |
| https://seaborn.pydata.org/api.html | 官方 API 参考（函数与对象清单以它为准） |

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
