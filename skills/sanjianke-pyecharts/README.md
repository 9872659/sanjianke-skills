# 三剪客 · Python 图表生成 Skill

用 Python 描述图表、由 ECharts 渲染：链式 API 出 30 多种图表、400+ 地图资源、导出可交互 HTML、在 Notebook 与 Web 框架里嵌入，以及转静态图片要额外配的依赖。

---

## 前置条件

- Python 3.7 及以上（v1 / v2 版本线的要求）。
- 能访问 PyPI 安装包。
- 想清楚产物形态：**HTML 网页**（原生能力，开箱即用）还是 **PNG 图片**（需要额外装无头浏览器驱动）。
- 确认自己用的是 v1+ 写法，不要去抄 0.5.x 时代的教程——两代 API 不兼容。
- Web 集成场景需要一个已存在的 Flask / Django / Sanic 项目。

---

## 使用

安装：

```bash
pip install pyecharts -U
```

最小用法：

```python
from pyecharts.charts import Bar
from pyecharts import options as opts

bar = (
    Bar()
    .add_xaxis(["衬衫", "毛衣", "领带"])
    .add_yaxis("商家A", [114, 55, 27])
    .set_global_opts(title_opts=opts.TitleOpts(title="销售情况"))
)

bar.render()              # 写出 render.html
bar.render("out/bar.html")  # 指定路径
```

常见分支：

- Notebook 里显示用 `render_notebook()`，不是 `render()`。
- 一个页面拼多张图用 `Page`。
- 想导成 PNG 要先 `pip install snapshot-selenium`，再用 `make_snapshot()`。
- 地图、组合图、时间轴都在 `pyecharts.charts` 里，换类名即可。

更多操作与完整避坑清单见 `SKILL.md`。

---

## 依赖

- `pyecharts` 本体（pip 安装）。
- 数据侧通常配 `pandas`，但 `pyecharts` 本身只接收 list 一类的基础结构，不直接吃 DataFrame。
- 转图片：`snapshot-selenium`（需本机浏览器与匹配的 driver）或 `snapshot-phantomjs`，二选一。
- 渲染端需要能加载 ECharts 的 JS 资源；离线部署要改用内嵌/本地资源方式。
- 容器或无头环境导出图片时，需要系统里装有中文字体。

---

## 安全

- 不内嵌任何密钥。
- 图表数据不联网，工具本身也不上报任何内容；唯一的网络行为是渲染出的 HTML 去 CDN 取 JS 资源，可以改成内嵌或本地 host 关掉。
- 需要 Selenium 快照时，浏览器与 driver 由你自己安装，注意版本匹配；不要在生产服务器上跑不受控的浏览器进程。
- 图表内可能包含业务数据，导出的 HTML 会把它序列化进文件；分享前确认数据可对外。


---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pyecharts`
- 仓库：https://github.com/pyecharts/pyecharts

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
