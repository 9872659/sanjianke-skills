---
name: sanjianke-matplotlib
slug: sanjianke-matplotlib
displayName: 三剪客 · Python 数据可视化绘图库
description: "matplotlib：Python 数据可视化绘图库 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "matplotlib：Python 数据可视化绘图库 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 爬虫
  - 数据分析
---

# 三剪客 · Python 数据可视化绘图库

matplotlib 是 Python 生态里最底层的静态绘图库：你把数据（列表、numpy 数组、pandas 的列）交给它，
它把图渲染成 PNG / SVG / PDF 这类文件，或者显示在窗口里。它解决的是「数据已经有了，怎么画成一张
能交出去、能放进报告的图」——尤其是需要在没有显示器的服务器上、循环批量出图的时候。
凡是涉及坐标轴、刻度、图例、字体、多子图排版这类细粒度控制的需求，都以它为准；
它不做交互式 Web 图表，也不做数据清洗与统计建模。

**上游项目**：`matplotlib`　**仓库**：https://github.com/matplotlib/matplotlib

## 什么时候用 / 不用

**用它**：

- 手上有一份 CSV / DataFrame，要把结果画成折线、柱状、散点、箱线图，并导出 PNG 或矢量图交付。
- 要在没有图形界面的服务器、容器或 CI 里批量出图——这是它最不可替代的场景。
- 需要对坐标轴、刻度、图例位置、字体、子图网格做细粒度控制，做出可用于出版或对外汇报的图。
- 要画热力图、等高线、3D 曲面、矢量场这类科学计算图。
- 数据链路已经在 Python 里（numpy / pandas），想在同一条链路里直接出图，不再引入前端图表库。

**不要用它**：

- 要的是网页里能缩放、能悬浮提示的交互式图表——用前端图表库（如 ECharts、Plotly）更合适，
  别硬套 matplotlib 的 Web 后端。
- 要做秒级刷新的实时大屏或监控仪表盘——它不是为实时渲染设计的。
- 已经在用 seaborn、`DataFrame.plot()` 这类高层封装且够用，不必再回头手写 pyplot 状态机。
- 数据量到千万级、需要 GPU 渲染加速——要另找专门的渲染方案，这不是它的目标。
- 你要的是数据清洗、建模或统计检验——那是别的库的活，它只负责最后一步画出来。

## 安装

pip（推荐先升级 pip 再装，避免拿到过旧的 wheel）：

```bash
python -m pip install -U pip
python -m pip install -U matplotlib
```

conda / pixi / uv：

```bash
conda install -c conda-forge matplotlib   # 或 conda install matplotlib（main channel）
pixi add matplotlib
uv add matplotlib
```

用 Linux 发行版自带的 Python，也可以直接装系统包：

```bash
sudo apt-get install python3-matplotlib   # Debian / Ubuntu
sudo dnf install python3-matplotlib       # Fedora
sudo pacman -S python-matplotlib          # Arch
```

装完先确认装到了哪个解释器、哪个版本：

```bash
python -c "import matplotlib; print(matplotlib.__version__, matplotlib.__file__)"
```

几点前置说明：

- 无界面后端 `Agg`、`ps`、`pdf`、`svg` 开箱即用；要弹窗口的 `TkAgg` 还需要 Tk 绑定，
  Linux 上通常要另外装 `python3-tk`。
- 如果 pip 试图从源码编译并失败，可以加 `--prefer-binary`，让它挑一个提供预编译 wheel 的较新版本。
- 用 uv 这类自带 Python 构建的工具时，若窗口后端不工作，先升级工具本身与它自带的 Python，
  或改装 `pyside6` 等其它受支持的 GUI 依赖项。

## 常用操作

**1）最小可跑的出图脚本（无界面，直接落盘）**

```python
import matplotlib
matplotlib.use("Agg")          # 必须在 import pyplot 之前指定后端
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
ax.plot([1, 2, 3, 4], [1, 4, 9, 16], marker="o", label="y = x^2")
ax.set_xlabel("x")
ax.set_ylabel("y")
ax.legend()
fig.savefig("out.png", bbox_inches="tight")
plt.close(fig)
```

**2）不改代码，用环境变量指定后端**

```bash
# Linux / macOS
MPLBACKEND=Agg python plot.py
```

```powershell
# Windows PowerShell
$env:MPLBACKEND="Agg"; python plot.py
```

```bat
:: Windows cmd
set MPLBACKEND=Agg && python plot.py
```

**3）让中文标签和负号正常显示**

```python
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei"]   # 换成运行环境里真实存在的中文字体名
plt.rcParams["axes.unicode_minus"] = False     # 负号不再变成方块
```

**4）查看并套用内置样式表**

```python
import matplotlib.pyplot as plt

print(plt.style.available)          # 列出所有可用样式
plt.style.use("ggplot")             # 全局生效
# 局部生效：with plt.style.context("ggplot"):
```

**5）定位配置目录与缓存目录（字体、样式出问题时先看这里）**

```python
import matplotlib as mpl

print(mpl.get_configdir())   # 用户配置目录，可放 matplotlibrc
print(mpl.get_cachedir())    # 缓存目录，删掉后重跑可强制重建字体缓存
```

```bash
# 临时把配置与缓存挪到指定目录（容器里很常用）
MPLCONFIGDIR=/tmp/mplconfig python plot.py
```

**6）多子图 + 紧凑排版**

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, layout="constrained", figsize=(8, 6))
axes[0, 0].plot([1, 2, 3], [3, 2, 1])
fig.savefig("grid.png", bbox_inches="tight")
plt.close(fig)
```

若所用版本不支持 `layout="constrained"`，改用 `fig.tight_layout()`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `ModuleNotFoundError: No module named 'matplotlib'`，但明明装过 | 装进了另一个 Python 或另一个虚拟环境，`pip` 与 `python` 不是同一套 | 一律用 `python -m pip install ...`；先 `python -c "import sys; print(sys.executable)"` 对齐解释器 |
| 中文标签显示成方框 | 没有可用中文字体，或字体缓存陈旧 | 设 `font.sans-serif` 为环境里真实存在的字体；删掉 `get_cachedir()` 目录后重跑 |
| 负号也变成方框 | 中文字体缺负号字形，而 `axes.unicode_minus` 仍为 True | 设 `plt.rcParams["axes.unicode_minus"] = False` |
| 服务器上运行报无 `$DISPLAY` 或 TclError | 默认后端想开 GUI，环境里没有显示服务 | `matplotlib.use("Agg")`，或直接 `MPLBACKEND=Agg python script.py` |
| 调了 `use("Agg")` 却不生效 | pyplot 已经被导入，后端在那时就锁定了 | 把 `matplotlib.use(...)` 提到所有 matplotlib 导入之前，或改用环境变量 |
| 脚本跑完卡住不退出，或窗口一闪而过 | 无界面环境下调用了 `show()`，或交互后端阻塞 | 无界面环境只 `savefig`，不要 `show()` |
| 保存出来是白图 / 存的是上一张图 | 混用了 pyplot 状态机和 Figure 对象，当前 figure 不是你以为的那张 | 固定用 `fig.savefig(...)` 而不是 `plt.savefig(...)`；多图时显式管理 fig |
| 轴标签、图例被裁掉一块 | 默认保存范围不含轴外文字 | `savefig(..., bbox_inches="tight")`，或建图时用 `layout="constrained"` |
| 循环画几千张图后内存暴涨 | 每次新建 figure 都没关 | 每轮结束 `plt.close(fig)` |
| 调 `matplotlib.cm.get_cmap` 报 AttributeError | 该接口在新版本已被移除 | 改用 `plt.get_cmap("viridis")` 或 `matplotlib.colormaps["viridis"]` |
| 系统包管理器装了却 import 不到 | 系统分发的包不在虚拟环境里 | 统一在 venv / conda 环境内安装，别混用系统包 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（仅安装阶段需要） | 从包源下载 wheel；绘图与保存过程本身不联网 |
| 读取文件 | 是 | 读取 CSV、图片、字体文件等绘图输入 |
| 写入文件 | 是 | 把图保存为 PNG / SVG / PDF；在配置目录写 rcParams 与字体缓存 |
| 凭证 | 否 | 不需要任何账号或 API Key |
| 子进程 / 后台常驻 | 视情况 | 首次运行会启动子进程扫描系统字体；无界面环境常以后台任务方式批量出图 |

## 触发场景

- 「把这批数据画成折线图 / 柱状图，导出图片」
- 「出一张能放进报告的 PNG，中文标签要正常」
- 「服务器上批量画图，没有显示器，报 DISPLAY 错」
- 「图里的中文全是方框，怎么修」
- 「matplotlib 装不上 / 编译失败怎么办」
- 「我要 4 张子图拼成一张图」

## 能力边界

**覆盖**：

- 静态 2D / 3D 科学绘图：折线、散点、柱状、饼图、箱线、热力图、等高线、曲面、矢量场等。
- 细粒度排版控制：多子图网格、约束布局、坐标轴与刻度定制、图例、注释、双轴。
- 多种输出：PNG、JPG、SVG、PDF、PS、EPS 等，位图与矢量图都支持。
- 中文文本与数学公式渲染、样式表与 rcParams 全局定制。
- 无图形界面环境下的批量出图，以及与 numpy / pandas 数据的直接衔接。

**不覆盖**：

- 交互式 Web 图表、可缩放可悬浮提示的前端渲染、实时刷新的大屏看板。
- 数据采集、清洗、统计建模、机器学习本身——它只负责把已有数据画出来。
- GPU 加速渲染与超大规模数据的实时可视化。
- 图表可读性的自动评审、配色无障碍审计等主观质量判断。
- 动画只能靠自带的 Animation 接口生成文件，不做浏览器内播放与交互控制。

## 依赖条件

- 64 位 Python 3 环境（支持的最低 Python 版本以官方安装文档为准）。
- 运行期依赖（numpy 等）由 pip / conda 自动安装，无需手工处理。
- 中文字体必须由系统提供；容器镜像常缺中文字体，需要自己装或挂载。
- 无界面环境需要 `Agg` 等非交互后端，并在导入 pyplot 之前指定。
- 不需要 GPU、不需要模型服务、不需要任何账号或 Key。

## 已知限制

- 默认后端在无图形界面环境下不自动降级，不显式切换就会直接报错。
- 首次运行会扫描系统字体并建缓存，冷启动偏慢；容器里可用 `MPL_IGNORE_SYSTEM_FONTS`
  限制扫描范围，或把缓存目录预先构建好。
- 中文字体是否可用完全取决于运行环境，跨机器迁移脚本时最容易在这里翻车。
- 单张图里的数据点数量很大时（十万级散点以上）渲染明显变慢，需要降采样或换方案。
- 产出是静态图，不含任何交互能力，也不生成 HTML 图表。

## 自检清单

- 装完先 `python -c "import matplotlib; print(matplotlib.__version__, matplotlib.__file__)"`，
  确认版本和路径都属于目标解释器。
- 无界面环境是否在 `import matplotlib.pyplot` 之前设好了 `Agg` / `MPLBACKEND`。
- 图里出现中文时，字体名是否是运行环境里真实存在的字体。
- 保存时用的是 `fig.savefig(...)` 且带 `bbox_inches="tight"`。
- 循环批量出图时，每轮是否 `plt.close(fig)`。
- 交付格式是否选对：要无损放大用 SVG / PDF，只要预览用 PNG。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/matplotlib/matplotlib | 上游仓库（安装与完整文档以它为准） |
| https://matplotlib.org/stable/install/index.html | 官方安装说明：各包管理器命令、后端与依赖 |
| https://matplotlib.org/stable/install/environment_variables_faq.html | 官方环境变量说明：`MPLBACKEND`、`MPLCONFIGDIR` 等 |

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
