# 三剪客 · A股量化选股与数据采集 Skill

从「每天抓数据」到「按条件选出票并回测成功率」的完整自建链路：环境准备、数据库与 Cookie 配置、批量作业命令、Web 看板与 Docker 部署、代理限流与自动交易风险提醒

---

## 前置条件

- **Python 3 环境**。官方开发使用 Python 3.11，建议装较新版本，并在安装时勾选加入环境变量。
- **MySQL 或 MariaDB**。系统的数据层就是数据库，不存在无数据库的轻量模式；需要提前装好并确认连接参数。
- **TA-Lib 本地库与头文件**。技术指标计算依赖 TA-Lib，必须先装它的 C 库与头文件，再装 Python 依赖。
- **操作系统**。Windows / Linux / macOS 都可以跑数据与 Web；**自动交易部分只支持 Windows**。
- **可选凭证与出口**：可用代理列表（`proxy.txt`）、数据源 Cookie（文件或环境变量）。数据抓取频率高时基本是必需品。
- **可选 Docker**：官方提供镜像，机器上需有可用的 Docker，并能拉取镜像。

---

## 使用

按「先跑通一环，再跑全链路」的顺序推进：

1. 读 `SKILL.md` 的「什么时候用 / 不用」，确认这是「自建系统」级需求，而不是「拉几张表」的需求。
2. 按「安装」一节把环境搭好：Python → 数据库 → TA-Lib → `pip install -r requirements.txt` → 按需配代理与 Cookie。
3. 用单功能作业验证链路：先跑 `python basic_data_daily_job.py` 看能不能抓到数据并入库。
4. 再跑整体作业：`python execute_daily_job.py`，或按日期 / 区间 / 枚举批量跑历史。
5. 启动 Web 看板 `run_web.bat`，访问 `http://localhost:9988/` 查看选股与回测结果。
6. 出问题时先看日志：`stock_execute_job.log`、`stock_web.log`、`stock_trade.log`。
7. 只有明确要动资金时，才去碰 `run_trade.bat`（Windows only）。

Docker 方式则按容器内路径运行同样的作业脚本，日志在 `InStock/instock/log/` 下。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| Python 3 | 官方开发使用 3.11，建议较新版本 |
| MySQL / MariaDB | 数据存储与查询 |
| TA-Lib（C 库 + Python 绑定） | 技术指标计算的核心依赖 |
| numpy / pandas | 数据处理与指标计算 |
| py_mini_racer / mini-racer | JS 执行相关依赖 |
| bokeh / tornado | Web 看板与服务 |
| PyMySQL / SQLAlchemy | 数据库驱动与 ORM |
| requests / beautifulsoup4 / urllib3 | 数据抓取 |
| easytrader / pycryptodome | 自动交易相关（仅 Windows） |
| arrow / python_dateutil / tqdm / Logbook | 时间处理、进度与日志 |
| Docker（可选） | 走镜像部署方式时需要 |
| tesseract（可选） | 自动交易时识别验证码 |

具体版本以仓库 `requirements.txt` 当前内容为准；升级到最新版前官方建议先把文件里的 `==` 改为 `>=`，升级可能引入不兼容变更，需自行评估。

---

## 安全

- 不内嵌任何密钥：本 Skill 正文不含数据库密码、Cookie、交易账号或任何可用凭证。
- 数据库账号密码、券商交易账号密码都应视为敏感信息：不要写进示例脚本，也不要提交进版本库。
- 代理文件与 Cookie 文件同样是敏感资产，注意文件权限与备份渠道。
- **自动交易涉及真实资金**：官方特别提醒交易日 10:00 会触发打新，不想打新就删除 `stagging.py` 或不要启动交易服务。启用前必须先在非实盘环境验证，并自行承担盈亏。
- 抓取行为应遵守目标站点的使用条款与 robots 约定；代理与 Cookie 只用于降低对单一来源的请求压力，不用于绕过访问控制。
- Web 看板使用的第三方商业控件为评估版，商用前需自行完成授权，避免法律风险。
- 系统的数据与选股结果仅供学习与分析，不构成投资建议。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`stock`
- 仓库：https://github.com/myhhub/stock

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
