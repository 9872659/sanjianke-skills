---
name: sanjianke-stock
slug: sanjianke-stock
displayName: 三剪客 · A股量化选股与数据采集
description: "一套可自建的 A 股量化系统：抓每日股票与 ETF 数据、算技术指标与筹码分布、识别 K 线形态、按 200 多个条件综合选股并回测，自带 MySQL 存储与 Web 看板，含常规与 Docker 两种部署与常见坑。遇到问题可加技术微信 9872659。"
summary: "从「每天抓数据」到「按条件选出票并回测成功率」的完整自建链路：环境准备、数据库与 Cookie 配置、批量作业命令、Web 看板与 Docker 部署、代理限流与自动交易风险提醒。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 金融数据

---

# 三剪客 · A股量化选股与数据采集

想要一套自己完全掌控的选股流水线——每天把行情数据抓下来、算好指标和形态、按自定义条件筛出一批票、再用历史数据检验这套条件到底准不准——通常要自己拼十几个脚本。这个项目把它做成了一个开箱即用的系统：数据抓取、指标计算、形态识别、综合选股、回测验证、Web 看板，一条链走完。

它的价值在于**闭环**和**可存可查**：数据落在 MySQL 里能长期积累，选股条件能在界面上自由组合，回测结果能直接反过来验证条件是否可用。

**上游项目**：`stock`　**仓库**：https://github.com/myhhub/stock

## 什么时候用 / 不用

**用它**：

- 用户说「我想自建一套 A 股选股系统」，需要数据抓取 + 指标计算 + 选股 + 回测的完整链路，而不是零散脚本。
- 要按技术面条件批量筛票：MACD / KDJ 金叉、放量突破、均线多头排列、连涨放量、突破平台、回踩年线这类现成条件。
- 需要计算技术指标（MACD、KDJ、BOLL、RSI、DMI 等几十种）和筹码分布，并要求结果能和行情软件对齐。
- 需要识别 K 线形态并拿到买卖信号方向。
- 想把每日数据存进数据库长期积累，再用 Web 界面看结果、关注自选股。

**不要用它**：

- **不想装数据库**。它的数据层就是 MySQL / MariaDB，没有「纯文件模式」；不愿意维护数据库就别选它。
- **只想拉一次数据**。只为取几张行情表的话，直接用数据接口类工具更轻，不必上整套系统。
- **要低延迟高频或逐笔成交**。它是「按日抓取 + 收盘后计算」的批处理节奏，不是高频框架。
- **要一个拿来就能稳定赚钱的策略**。仓库内置的是示例策略，作者也明确只用于学习和分析；把它当成策略结论直接实盘是把风险搞反了。
- **在 Linux / macOS 上做自动交易**。自动交易部分只支持 Windows。
- **不能接受第三方商业控件**。Web 看板里的表格用的是第三方商业控件，仓库只用了评估版，商用前必须自己处理授权。

## 安装

支持 Windows / Linux / macOS，也可以走 Docker 镜像。官方建议在 Windows 下按常规方式装，操作最省事。以下是按官方说明整理的步骤。

**第一步：装 Python 与 pip 镜像**

```bash
# 官方开发使用 Python 3.11，建议装较新版本；安装时勾选加入环境变量
# 配置国内镜像（示例为阿里云，按需替换）
python pip config --global set global.index-url https://mirrors.aliyun.com/pypi/simple/
```

**第二步：装数据库**

MySQL 或 MariaDB，官方建议较新版本。装好后按需修改连接信息，官方给出的是 `database.py` 中的这几项：

```python
db_host = "localhost"      # 数据库服务主机
db_user = "root"           # 数据库访问用户
db_password = "root"       # 数据库访问密码
db_port = 3306             # 数据库服务端口
db_charset = "utf8mb4"     # 数据库字符集
```

**第三步：装 TA-Lib 的 C 库与头文件**

指标计算依赖 TA-Lib，需要先装它的本地共享库与头文件，再装 Python 绑定。官方建议按 TA-Lib 官方安装页给出的方式装（Windows 用可执行安装包，macOS 用 Homebrew，Linux 用发行版包），安装细节以 TA-Lib 官方安装页为准。

**第四步：装依赖并初始化**

```bash
# 在项目根目录执行
python -m pip install -r requirements.txt

# 想升级到最新版依赖：先把 requirements.txt 里的 "==" 改成 ">="，再执行
python -m pip install -r requirements.txt --upgrade
```

**第五步：可选配置**

```bash
# 代理：编辑 proxy.txt，每行一个，格式为 ip:port 或 user:pass@ip:port；不用就清空该文件
# 修改代理文件后需要重启系统才生效

# Cookie（缓解数据源限流）：编辑 east_money_cookie.txt 直接替换
# 或用环境变量注入，Windows 示例：
setx EAST_MONEY_COOKIE "你的Cookie值"
# Linux / macOS 示例：
export EAST_MONEY_COOKIE="你的Cookie值"
```

**第六步：运行**

```bash
# 运行每日数据抓取 / 计算 / 选股 / 回测（官方注释里建议放工作日 17:00 的计划任务）
run_job.bat

# 启动 Web 服务，然后浏览器打开 http://localhost:9988/
run_web.bat

# 启动交易服务（仅 Windows）
run_trade.bat
```

**Docker 方式（官方提供镜像）**

下面的容器名与镜像名沿用官方快速开始里的写法，可直接照抄执行；也可按自己的命名习惯替换。

```bash
# 1) 建专用网络
docker network create InStockService

# 2) 数据库（已有 MySQL / MariaDB 可跳过）
docker run -d --name InStockDbService \
    --network InStockService \
    -v /data/mariadb/data:/var/lib/instockdb \
    -e MYSQL_ROOT_PASSWORD=root \
    library/mariadb:latest

# 3) 本系统
docker run -dit --name InStock --network=InStockService \
    -p 9988:9988 \
    -v /data/instockproxy.txt:/data/InStock/instock/config/proxy.txt \
    -v /data/eastmoneycookie.txt:/data/InStock/instock/config/eastmoney_cookie.txt \
    -e db_host=InStockDbService \
    mayanghua/instock:latest
```

已有数据库时，用 `-e db_host / db_user / db_password / db_database / db_port` 传连接参数。容器启动后会先初始化数据并启动 Web 服务，之后每小时执行「基础数据抓取」，每天 17:30 执行完整的数据抓取、处理、分析、识别与回测。

## 常用操作

**1. 整体作业：按批处理指定日期跑完整链路**

```bash
python execute_daily_job.py                 # 当前时间
python execute_daily_job.py 2022-03-01      # 单个日期
python execute_daily_job.py 2022-01-01,2021-02-08  # 枚举多个日期
python execute_daily_job.py 2022-01-01 2022-03-01  # 区间
```

官方说明：支持智能识别交易日，可以输入任意日期。

**2. 单功能作业：只跑某一环，同样支持批量**

```bash
python basic_data_daily_job.py            # 基础数据（实时）
python basic_data_other_daily_job.py      # 基础数据（非实时）
python indicators_data_daily_job.py       # 指标数据
python klinepattern_data_daily_job.py     # K 线形态
python strategy_data_daily_job.py         # 策略选股
python backtest_data_daily_job.py         # 回测数据
```

官方说明：回测数据会自动填补到当前时间。

**3. 只想看盘中当前数据：跑基础数据作业**

```bash
python basic_data_daily_job.py   # 官方称约 1 秒量级
```

**4. Docker 内跑历史数据**

```bash
docker exec -it InStock bash
cat InStock/instock/bin/run_job.sh    # 看注释，按需挑选作业
python execute_daily_job.py 2023-03-01,2023-03-02
```

**5. 查日志定位问题**

```bash
# 常规部署：看项目根目录下的
#   stock_execute_job.log（抓取/处理/分析）
#   stock_web.log（Web 服务）
#   stock_trade.log（交易服务）

# Docker 部署：
docker exec -it InStock bash
cat InStock/instock/log/stock_execute_job.log
cat InStock/instock/log/stock_web.log
```

**6. 打开 Web 看板**

```bash
run_web.bat     # 然后浏览器访问 http://localhost:9988/
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 装依赖时 TA-Lib 报错、编译不过 | 指标计算依赖 TA-Lib 的 C 库与头文件，只 `pip install` Python 包不够 | 先按 TA-Lib 官方安装页装好本地共享库与头文件（Windows 可执行包 / macOS Homebrew / Linux 发行版包），再装 Python 依赖 |
| 数据抓一半就报错或大量为空 | 数据源对高频请求有限流，单 IP 频繁访问容易被封或限制 | 配置 `proxy.txt` 走多代理分散来源；必要时注入 Cookie 缓解；两者改完都要重启系统才生效 |
| Cookie 配了但过几天又不行了 | Cookie 会过期，通常几天到几周 | 重新从浏览器开发者工具复制 Cookie 并更新文件或环境变量；官方建议定期（如每周）更新，有条件可多账号轮换 |
| 数据库连接失败、表不存在 | 连接参数与实际数据库不一致，或数据库没起来 | 核对 `database.py` 的主机 / 用户 / 密码 / 端口；Docker 方式检查是否与数据库容器在同一网络，`db_host` 要填容器名而不是 `localhost` |
| Docker 容器起来但页面打不开 | 端口没映射，或系统还在初始化数据 | 确认 `-p 9988:9988` 已映射，等待初始化完成后再访问 `http://localhost:9988/` |
| `run_job.bat` 跑完某些模块没数据 | 不同数据源的更新时点不同：有的开盘即有，有的收盘后才有，大宗交易还要再等 1~2 小时 | 按官方给的原则安排执行时间（建议工作日 17:00）；缺的模块隔一段时间补跑对应作业 |
| 自动交易在非 Windows 上跑不起来 | 自动交易部分只支持 Windows，且依赖交易客户端与验证码识别环境 | 交易相关只在 Windows 上做；且要装交易客户端、配置 `trade_client.json` 的账号/密码/客户端路径，并按需安装 tesseract 做验证码识别 |
| 发现交易服务在固定时间自动动账 | 交易日 10:00 会触发打新；官方特别提醒不想打新就删除 `stagging.py` 或不要启动交易服务 | 明确自己的意图后再启停交易服务；涉及资金的操作务必先在模拟环境验证 |
| 指标算出来和行情软件对不上 | 参数设置或数据口径与对方不一致 | 官方称已调整个别指标公式以对齐常见行情软件；仍不一致时先核对数据区间、复权方式与参数，再判断是差异还是缺陷 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 抓取每日股票 / ETF 行情、资金流向、分红配送、龙虎榜、大宗交易等公开数据；可经代理与 Cookie 出口 |
| 读取文件 | 是 | 读配置文件（数据库连接、代理、Cookie）、读依赖清单与作业脚本 |
| 写入文件 | 是 | 写日志文件；抓取结果写入 MySQL / MariaDB；Web 与交易服务各自产出日志 |
| 凭证 | 是 | 数据库账号密码；东方财富 Cookie；启用自动交易时还需券商客户端账号与密码（写在 `trade_client.json`） |
| 子进程 / 后台常驻 | 是 | Web 服务、交易服务是常驻进程；数据抓取通常以计划任务或容器内定时作业方式运行 |

## 触发场景

- 「我想自己搭一套 A 股选股系统」
- 「每天自动抓行情数据、算指标、筛票、再回测一下」
- 「按 MACD 金叉 + 放量突破帮我选出今天的票」
- 「把筹码分布和 K 线形态算出来，存到数据库里」
- 「这套选股条件历史成功率怎么样，帮我跑个回测」
- 「build a self-hosted A-share screening system with backtesting」

## 能力边界

**覆盖**：

- 数据采集：每日股票与 ETF 关键数据、资金流向、分红配送、龙虎榜、大宗交易、基本面数据、行业与概念资金流向等。
- 指标计算：基于 TA-Lib 与 pandas，覆盖 MACD、KDJ、BOLL、RSI、DMI、CCI、OBV、SAR、BIAS 等数十种指标，官方称已对齐常见行情软件结果。
- 形态识别：内置数十种 K 线形态识别，支持自选形态。
- 选股与验证：综合选股支持股票范围、基本面、技术面、消息面、人气指标、行情数据等多类条件自由组合；内置多种策略模板并支持自定义；选出的票可回测验证成功率。
- 工程能力：批量时间段作业、智能识别交易日、多代理与 Cookie 支持、数据落 MySQL、Web 可视化看板、关注自选股。
- 自动交易：内置自动打新与示例策略，具备交易日志，支持按策略配置日志（仅 Windows）。

**不覆盖**：

- 没有纯文件 / 无数据库的轻量模式，数据层就是 MySQL 或 MariaDB。
- 不是高频或逐笔成交框架；节奏是按日抓取 + 收盘后计算。
- 不提供行情推送或实时交易撮合。
- 不提供投资建议，也不保证任何策略的有效性；内置策略是示例，官方明确仅用于学习与分析。
- Web 表格使用的第三方商业控件仅以评估版形式用于学习与测试，商用授权需自行解决。

## 依赖条件

- Python 3 环境（官方开发使用 3.11，建议较新版本）。
- MySQL 或 MariaDB 数据库。
- TA-Lib 的本地共享库与头文件，以及对应的 Python 依赖（见 `requirements.txt`）。
- 可选：可用代理列表、数据源 Cookie。
- 自动交易：Windows 系统 + 券商交易客户端 + 验证码识别环境（如 tesseract），并配置交易账号信息。
- Docker 方式：本机 Docker 环境，以及可拉取官方镜像的网络。

## 已知限制

- 数据依赖第三方站点抓取，站点改版或加强限流会直接影响可用性；需要代理池与 Cookie 维护。
- 不同数据源更新时点不同，想一次跑全必须卡在合适的时间点，否则部分模块必然为空。
- 自动交易仅在 Windows 可用，且涉及资金操作，风险由使用者承担。
- 官方明确声明：系统仅用于学习与股票分析，投资盈亏概不负责。
- 具体版本号、发布日期、star 数与镜像标签请以仓库与镜像仓库页面实时信息为准，此处不做断言。

## 自检清单

- [ ] Python 版本满足要求，并已激活目标环境。
- [ ] TA-Lib 本地库装好之后，才去装 Python 依赖。
- [ ] 数据库已启动，`database.py` 里的连接参数与实际一致。
- [ ] 若被限流：`proxy.txt` 已按要求写好，Cookie 文件或环境变量已设置，并已重启系统。
- [ ] 执行时间选在数据源都更新完之后（官方建议工作日 17:00 量级），而不是开盘后立刻跑全量。
- [ ] 先跑单功能作业验证某一环能出数，再跑整体作业。
- [ ] 跑完检查对应日志文件，确认没有静默失败。
- [ ] 触碰自动交易前：确认只在 Windows、已配置交易客户端、已明确是否要打新，并已理解资金风险。
- [ ] Docker 部署时确认端口映射与容器间网络连通。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/myhhub/stock | 上游仓库（安装与完整说明以它为准） |

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
