# 三剪客 · 数据可视化探索 Skill

把 pandas / polars / pyarrow 数据表变成可拖拽的可视化界面：Jupyter 与 Streamlit 两种用法、图表状态的存与取、导出 HTML、把界面里的图表回导成 Python 代码。

---

## 前置条件

- 一个可用的 Python 环境，能装 PyPI 包（`pip` 或 `conda` / `mamba`）。
- 数据已经在 Python 里读进来了：`pandas` DataFrame、`polars` 或 `pyarrow` 表。
- 需要有前端渲染能力的宿主环境：Jupyter Notebook / JupyterLab / Jupyter Lite、Colab、Kaggle、Databricks Notebook、VS Code 的 Jupyter 扩展，或一个 Streamlit 应用。
- 用 Streamlit 的话，除了 `pygwalker` 还要装 `streamlit` 本身。
- 想用云端计算或云端分享能力，需要自备上游站点的 token（通过 `pygwalker config` 写入或实例化时传入）。

---

## 使用

安装：

```bash
pip install pygwalker
# conda 路线
conda install -c conda-forge pygwalker
```

最小用法，在 Jupyter 里跑：

```python
import pandas as pd
import pygwalker as pyg

df = pd.read_csv("./bike_sharing_dc.csv")
walker = pyg.walk(df)
```

三个最常用的参数：

- `spec_path`：本地文件路径，用来加载和保存图表状态。
- `computation`：查询在哪算。`"browser"` 纯前端、`"kernel"` 本地内核（DuckDB）、`"cloud"` 云端；不写则自动选择。
- `walk()` 返回的 `Walker` 对象可以 `show()`、`to_html()`、`to_code()`，也能直接交给 Streamlit 的 `StreamlitRenderer`。

Streamlit 集成要点：把创建 renderer 的函数用 `@st.cache_resource` 缓存起来，否则每次交互都会重建。完整示例与更多操作见 `SKILL.md`。

---

## 依赖

- `pygwalker` 本体（pip 或 conda-forge 安装）。
- `pandas`；用 polars / pyarrow 表则装对应的包。
- Streamlit 场景额外需要 `streamlit`。
- `computation="kernel"` 走本地内核计算，由包自身带的内核计算能力提供，不需要你另外起服务。
- 浏览器端要能执行 JavaScript；Notebook 场景依赖内核与前端组件的正常通信。

---

## 安全

- 不内嵌任何密钥。
- 数据默认不出本地：`computation="browser"` 与 `"kernel"` 都在你本机算，只有 `"cloud"` 会把计算交给外部。
- 隐私档位可调：`pygwalker config --set privacy=offline` 表示完全离线、不发数据也不请求接口。默认档位是 `update-only`，只做版本更新检查。
- 云端能力需要 token 时才配置 token，不要把 token 写进代码仓库；用 `pygwalker config` 落到本机配置文件即可。
- 图表状态文件（`spec_path`）里可能包含你的字段名与筛选条件，分享前留意是否含敏感表结构信息。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pygwalker`
- 仓库：https://github.com/Kanaries/pygwalker

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
