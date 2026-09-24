# 三剪客 · Python 数据可视化绘图库 Skill

matplotlib：Python 数据可视化绘图库 的安装、常用命令与避坑要点

---

## 前置条件

- 一个 64 位 Python 3 环境（支持的最低版本以官方安装文档为准），能正常执行 `python -m pip`。
- 建议先建虚拟环境再装，避免和系统包管理器装的同名包互相覆盖。
- 要显示窗口的场景需要 GUI 依赖（如 Tk 绑定）；只在服务器上出图则不需要。
- 图里要出现中文时，运行环境里必须已经装了中文字体。
- 无界面环境需要非交互后端（`Agg` 等），并在导入 pyplot 之前指定。

---

## 使用

最短跑通路径：

```bash
python -m pip install -U pip
python -m pip install -U matplotlib
python -c "import matplotlib; print(matplotlib.__version__, matplotlib.__file__)"
```

然后在服务器上出图（不需要显示器）：

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([1, 2, 3], [1, 4, 9])
fig.savefig("out.png", bbox_inches="tight")
```

或者在脚本里固定用环境变量切换后端，不改代码：

```bash
MPLBACKEND=Agg python plot.py
```

完整的安装方式（conda / pixi / uv / 各 Linux 发行版包管理器）、6 组常用操作、
11 条常见坑与排查办法，见 `SKILL.md`。

---

## 依赖

- **运行期依赖**：numpy 等由 pip / conda 自动安装，不需要手工处理。
- **可选依赖**：`TkAgg` 窗口后端需要 Tk 绑定（Linux 上通常是 `python3-tk`）；
  其它 GUI 框架、LaTeX 渲染、动画保存、更多导出格式各自有对应的可选依赖。
- **字体**：中文字体由操作系统或容器镜像提供，本包不附带字体文件。
- **不需要**：GPU、显存、模型权重、模型服务地址或任何 API Key。

---

## 安全

- 不内嵌任何密钥，也不需要任何账号或凭证。
- 安装阶段会访问 Python 包源下载 wheel；绘图与保存过程本身不联网，不会把数据发到外部。
- 读文件仅限你在脚本里指定的输入（CSV、图片、字体等）；写文件仅限你指定的输出路径
  以及配置目录里的 rcParams 与字体缓存。
- 首次运行会启动子进程扫描系统字体，属正常行为；容器环境可用 `MPL_IGNORE_SYSTEM_FONTS`
  限制扫描范围，用 `MPLCONFIGDIR` 把配置与缓存挪到可写目录。
- 绘图脚本会执行你在代码里写的任意 Python，只运行自己信任的脚本。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`matplotlib`
- 仓库：https://github.com/matplotlib/matplotlib

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
