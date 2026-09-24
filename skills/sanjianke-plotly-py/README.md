# 三剪客 · 交互式数据可视化图表 Skill

plotly.py：交互式数据可视化图表的安装、常用命令与避坑要点

---

## 前置条件

- 本机有 Python 环境，能用 pip 或 conda 装包。
- 先定产出形态：要「交互 HTML」还是「静态图片」。前者只需基础安装，后者还要 Kaleido 和浏览器。
- 静态图片导出需要 Kaleido（官方要求 1.0 或更高）以及 Chrome / Chromium；无头容器与 CI 环境要自己把浏览器和字体装进镜像。
- 图里要用中文，就确认出图环境里确实装了中文字体，并在图面上显式指定字体族。
- 在 Jupyter 里当控件使用需要 `jupyter` 与 `anywidget`；走 DataFrame 接口需要 `pandas`。

---

## 使用

1. `pip install plotly`，用官方 Quickstart 的三行确认环境可用：`import plotly.express as px` 出一张柱状图再 `fig.show()`。
2. 要给人交互看，用 `fig.write_html(...)` 出自包含单文件；接收方离线也能打开。
3. 要进报告或文档，用 `fig.write_image(...)` 出 PNG / JPG / SVG / PDF，前提是 Kaleido 与浏览器就位。
4. 快速出图用 `plotly.express`；需要控标题、轴、图例、标注时改用 `plotly.graph_objects` 补细节。
5. 需要交给前端或其他服务渲染时，用 `fig.to_json()` 拿结构化定义。
6. 大数据量散点显式打开 WebGL 渲染模式，或先降采样，避免页面卡死。

---

## 依赖

- Python；pip 或 conda 均可安装。
- Jupyter 控件形态：`jupyter` + `anywidget`。
- 静态导出：Kaleido（官方要求 1.0 或更高）+ Chrome / Chromium。
- DataFrame 快速接口：`pandas`；JSON 内联渲染路径另需 `nbformat`。
- 底层绘图能力来自同一套 JavaScript 绘图引擎，Python 包负责生成图定义。

---

## 安全

- 不内嵌任何密钥；本地绘图不需要任何凭证。
- 默认不联网：图表计算全在本地。只有显式使用在线渲染或在线资源时才需要出网。
- 会写文件（HTML、图片）；导出目标路径由使用者控制，注意别覆盖重要文件。
- 会拉起子进程：静态导出时由 Kaleido 启动渲染进程并驱动 Chrome / Chromium；在受限环境里要先确认允许启动子进程。
- 不要把内部数据导出成引用在线资源的 HTML 后再公开分发，避免数据随图表外流。
- 图表里可能包含业务数据，导出文件等同于数据外带，分发前先确认权限。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`plotly.py`
- 仓库：https://github.com/plotly/plotly.py

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
