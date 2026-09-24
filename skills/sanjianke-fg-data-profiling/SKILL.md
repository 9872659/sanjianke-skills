---
name: sanjianke-fg-data-profiling
slug: sanjianke-fg-data-profiling
displayName: 三剪客 · 数据画像与质量体检
description: "给一张数据表做一次性探索性分析：自动推断列类型、给出缺失/重复/异常等质量问题清单，产出可分享的 HTML 或 JSON 报告，也可在 Jupyter 里以控件查看，含迁移后的包名与导入名变更、大数据集降级策略等坑。遇到问题可加技术微信 9872659。"
summary: "接手一张陌生数据表时先做一次体检：一行代码生成包含单变量、多变量、时间序列、文本分析的报告，输出 HTML / JSON / Notebook 控件，并标注需要处理的数据质量问题。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 数据分析

---

# 三剪客 · 数据画像与质量体检

拿到一张别人给的表，第一件事不是建模，而是搞清楚它到底长什么样：有多少列、哪些列缺值严重、有没有重复行、数值分布是不是偏到离谱、分类列里是不是只填了同一个值。手工逐列 `describe()` 加可视化，做一遍要花不少时间。

这个库把这件事做成了一行调用：给一个 DataFrame，它自动做类型推断、单变量与多变量统计、相关性、缺失与重复分析，还会把发现的问题整理成一份「警报清单」一起放进报告。输出可以是能直接发给同事的 HTML，也可以是便于程序消费的 JSON。

它的定位是**探索性分析和质量体检**，不是清洗工具：它告诉你哪里有问题，修不修、怎么修还是你自己的事。

**上游项目**：`fg-data-profiling`　**仓库**：https://github.com/Data-Centric-AI-Community/fg-data-profiling

## 什么时候用 / 不用

**用它**：

- 用户说「这张表我不熟，先帮我看看数据质量怎么样」。
- 需要一份能直接分享的数据概览报告（HTML），放进数据交付或分析记录里。
- 要快速定位质量问题：缺失比例、重复行、常量列、高相关列、偏度异常、零值占比。
- 数据集包含时间列或文本列，想做对应的时序分析与文本特征概览。
- 需要把分析结果以 JSON 形式接入自动化流程（例如数据流水线里产出一份体检结果）。

**不要用它**：

- **数据量特别大还想全量跑**。它是把数据读进内存做统计的方式，几千万行级别全量跑会非常慢甚至爆内存；这类场景要用它的降级配置、抽样，或走 Spark 相关集成。
- **只想看几个数字**。只想看均值、分位数的话，`df.describe()` 就够了，不必生成一份报告。
- **要清洗、转换、补齐数据**。它只出诊断结论，不做任何改写；把报告当「自动修复」会误事。
- **要当数据质量的强制门禁**。报告里的警报是启发式的提示，不是校验规则引擎；需要「不达标就阻断流水线」要用专门的校验工具。
- **数据包含敏感信息且要对外发报告**。默认报告会把数据细节呈现在 HTML 里，直接外发有泄露风险；要改用敏感数据相关的配置项。

## 安装

需要 Python 3 环境。报告是 HTML + CSS 渲染的，查看时需要较新的浏览器。

```bash
# pip
pip install -U fg-data-profiling

# 可选扩展：按需安装
pip install -U fg-data-profiling[notebook,unicode,pyspark]
```

```bash
# conda
conda install -c conda-forge fg-data-profiling
```

```bash
# 从源码安装（clone 仓库后在其根目录执行）
pip install -e .
```

**如果你是老用户，注意包已经改名：**

```bash
# 1) 卸载旧包
pip uninstall ydata-profiling

# 2) 装新包
pip install fg-data-profiling

# 3) 改导入名（旧的是 ydata_profiling，新的是 data_profiling）
grep -r "ydata_profiling" . --include="*.py"
```

可选扩展说明：

| 扩展 | 用途 |
|---|---|
| `[notebook]` | 支持在 Jupyter 里以控件形式渲染报告 |
| `[unicode]` | 更详细的 Unicode 文本分析（占用更多磁盘） |
| `[pyspark]` | 支持用 Spark 处理大数据集 |

## 常用操作

**1. 最小用法：一行生成报告对象**

```python
import numpy as np
import pandas as pd
from data_profiling import ProfileReport

df = pd.DataFrame(np.random.rand(100, 5), columns=["a", "b", "c", "d", "e"])
profile = ProfileReport(df, title="Profiling Report")
```

**2. 导出成 HTML 文件（最常用的交付形态）**

```python
profile.to_file("your_report.html")
```

**3. 导出成 JSON（便于程序消费）**

```python
json_data = profile.to_json()          # 直接拿 JSON 字符串
profile.to_file("your_report.json")    # 或落成文件
```

**4. 在 Jupyter 里查看（两种方式）**

```python
profile.to_widgets()          # 以控件形式展示（需装 [notebook]）
profile.to_notebook_iframe()  # 把 HTML 报告嵌进 notebook
```

**5. 命令行用法：直接对 CSV 生成报告**

```bash
data_profiling --title "Example Profiling Report" --config_file default.yaml data.csv report.html
```

命令行支持的完整参数、配置文件字段与默认配置示例，以官方文档的快速开始与配置说明为准。

**6. 处理大数据集：先采样再出报告（思路）**

```python
sample = df.sample(n=100_000, random_state=0)
ProfileReport(sample, title="Sampled Report").to_file("sampled.html")
```

除了抽样，官方还提供了面向大数据集的配置与说明（含 Spark 方向的集成），具体配置项以官方文档「大数据集」章节为准。

**7. 对比两份数据（前后版本差异）**

官方支持一次性生成两份数据集的对比报告，配置方式以文档中「对比数据集」章节为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `import ydata_profiling` 报 ModuleNotFoundError | 包已改名为 `fg-data-profiling`，导入名也换成了 `data_profiling`，旧包不再更新 | 卸掉旧包、装新包，并把代码里的导入统一改成 `from data_profiling import ProfileReport` |
| 装了两个包，行为诡异或版本冲突 | 新旧包同时存在，环境里有两套同名模块来源 | 严格按迁移步骤先 `pip uninstall ydata-profiling` 再装新包；装完用 `pip list` 确认只剩一个 |
| 大表跑几十万行以上时极慢，甚至内存爆掉 | 它默认要逐列做较重的统计与可视化数据准备，全量在内存里算 | 先抽样再出报告；或使用官方针对大数据集提供的降级配置；数据量再大考虑 Spark 方向的集成 |
| `to_widgets()` 在 Jupyter 里不显示或报错 | 控件能力需要额外的 notebook 扩展依赖 | 装 `fg-data-profiling[notebook]`；还不行就直接用 `to_notebook_iframe()` 这条 HTML 路径 |
| 命令行对某些 CSV 报解析错误 | CLI 走的是「pandas 默认读法能直接读」的标准 CSV 假设 | 先用 pandas 手工 `read_csv` 带上正确分隔符 / 编码 / 表头参数读进来，再用 Python API 生成报告 |
| 报告里出现不该外发的数据细节 | HTML 报告会把列级样例与分布一起呈现 | 对含敏感信息的列使用官方「敏感数据」相关配置做处理后再生成；或只在受控环境内部分享报告 |
| 报告里警报一大堆，不知道该信哪条 | 警报是基于统计特征的自动提示，包含常量列、高相关、偏度、零值占比等多种启发式规则 | 把它当线索清单而不是结论：逐条回到业务语义判断，相关性提示尤其不能直接当因果关系 |
| 文本列分析结果很粗糙 | 详细的 Unicode 分析需要额外扩展，默认不装 | 需要就装 `[unicode]`；仍不满足时要换专门的文本分析方案 |
| 报告打开一片空白或样式错乱 | 报告依赖较新的浏览器渲染，旧内核或受限查看器可能不支持 | 换较新的浏览器打开；不要把 HTML 报告丢进只支持纯文本的查看器里 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（默认） | 核心流程是本地对 DataFrame 做统计，不需要联网；若接入外部数据源或 Spark 集群则由使用者自行决定 |
| 读取文件 | 视情况 | 使用命令行 `data_profiling a.csv report.html` 时读取输入数据文件 |
| 写入文件 | 是 | `to_file()` 写出 HTML 或 JSON 报告 |
| 凭证 | 否 | 不需要账号或密钥；连接外部数据库属于另一条路径，需自备凭据 |
| 子进程 / 后台常驻 | 否 | 纯 Python 库，在一次调用内完成分析；CLI 也是短时进程 |

## 触发场景

- 「这张表帮我做个数据体检，看有什么问题」
- 「生成一份数据概览报告，我要发给同事」
- 「哪些列缺失严重、有没有重复行和常量列」
- 「这个数据集我要先做 EDA，出一份报告」
- 「把数据质量分析结果输出成 JSON，我要接进流水线」
- 「profile this dataframe and give me an HTML report」

## 能力边界

**覆盖**：

- 类型推断：自动识别分类、数值、日期等列类型。
- 质量警报：缺失数据、不准确、偏度、常量值、零值、高相关、重复行等问题的汇总清单。
- 单变量分析：描述性统计（均值、中位数、众数等）与分布类可视化。
- 多变量分析：相关性、缺失数据细节、重复行、变量两两交互。
- 时间序列：自相关、季节性等时序统计，以及 ACF / PACF 图。
- 文本分析：常见类别、大小写、分隔符、文字脚本与 Unicode 块等。
- 文件与图像分析：文件大小、创建日期、尺寸、截断图像提示、EXIF 元数据是否存在。
- 数据集对比：一次性生成两份数据的对比报告。
- 报告结构：除各列详情外，还包含数据集总览、警报汇总、可复现性信息。
- 输出形态：HTML 文件、JSON（字符串或文件）、Jupyter 控件与内嵌 iframe。
- 命令行入口 `data_profiling`，以及 Spark 与若干数据生态集成。

**不覆盖**：

- 不做数据清洗、转换、插补、去重等写操作，只出诊断结论。
- 不做规则化的数据质量门禁（没有「不通过就阻断」的判定引擎）。
- 不做建模、特征工程与自动化机器学习。
- 不做数据库连接与抽取；连库取数属于另一类产品 / 集成路径。
- 默认不承诺大数据集上的全量性能，需要抽样或专用配置。

## 依赖条件

- Python 3 环境。
- pandas 及其数值依赖（随包安装）。
- 查看 HTML 报告需要较新版本的浏览器。
- 可选扩展按需安装：`[notebook]`、`[unicode]`、`[pyspark]`。
- 老用户迁移：需要 Python 环境里不再残留旧包。

## 已知限制

- 包与导入名都改过，历史代码、脚本、笔记与依赖清单里出现旧名字时必须同步更新，否则会直接导入失败。
- 大数据集上全量运行开销大，官方提供的是「准备数据 + 配置降级 + Spark 集成」的组合方案，而不是简单的开关。
- 报告是静态 HTML / JSON，没有服务端交互能力。
- 警报是基于统计特征的提示，存在误报与漏报，不能当作数据合格判定的依据。
- 具体版本号、发布日期与 star 数请以仓库及 PyPI 页面实时信息为准，此处不做断言。

## 自检清单

- [ ] 已确认环境里没有残留旧包，导入名统一为 `data_profiling`。
- [ ] pandas 能正常读入目标数据；CLI 报解析错误时先用 Python API 这条路。
- [ ] 数据规模已评估：超过内存舒适区就先抽样或使用大数据集配置。
- [ ] 使用 `to_widgets()` 前已装 `[notebook]` 扩展。
- [ ] 报告输出路径可写，生成后确认文件存在且非空。
- [ ] 数据含敏感信息时，已使用相应配置处理，并确认报告的分发范围。
- [ ] 报告里的警报已逐条结合业务语义复核，没有直接把相关性提示当结论。
- [ ] 生成的 HTML 用较新浏览器打开确认渲染正常。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/Data-Centric-AI-Community/fg-data-profiling | 上游仓库（安装与完整文档以它为准） |
| https://docs.profiling.ydata.ai/latest/ | 官方文档站（配置项、大数据集与敏感数据处理以它为准） |

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
