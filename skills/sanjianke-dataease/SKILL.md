---
name: sanjianke-dataease
slug: sanjianke-dataease
displayName: 三剪客 · 开源 BI 数据可视化平台
description: "DataEase：开源的数据可视化分析平台，连上数据库或 Excel 后拖拽出图表、仪表板与数据大屏。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "DataEase 是自建的开源 BI 平台，本 Skill 覆盖 Docker 一键/离线安装、dectl 运维命令、数据源与仪表板落地路径、备份还原，以及默认密码、MySQL 参数要求、地图白屏等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - BI
  - 数据可视化

---

# 三剪客 · 开源 BI 数据可视化平台

团队里有数据但没人会写 SQL 画图，或者每次做周报都要手工截图拼 PPT——这类需求不该靠一个人加班解决，而是该有个地方把数据源接上，然后谁都能拖出图来、把图拼成仪表板、再投到大屏上。

DataEase 就是干这个的自建平台：它自己是一套 Docker 编排的 Web 服务，浏览器打开就是工作台，连上 MySQL / Oracle / ClickHouse / Excel / API 这类数据源，用鼠标拖拽出图表，仪表板和数据大屏都从同一套数据集长出来。

**上游项目**：`dataease`　**仓库**：https://github.com/dataease/dataease

## 什么时候用 / 不用

**用它**：

- "公司内部数据想做个看板，每周自动刷新，不想买 SaaS 席位。"——自建部署，浏览器访问，数据留在自己服务器上。
- "这台服务器不联外网，给我离线装一套 BI。"——官方提供离线安装包，解压改配置后跑安装脚本即可。
- "数据库表结构很杂，业务同事要自己拉图看，别每次都找我写 SQL。"——接上数据源、建好数据集之后，业务侧只做拖拽。
- "会议室有块大屏，要一个能全屏轮播的实时数据大屏。"——仪表板与数据大屏是两个独立能力，大屏专门为投屏场景做。
- "想把 MySQL、ClickHouse、Excel 三类数据放到同一张图上对比。"——同一平台支持多数据源与本地 Excel/CSV 上传。
- "已经跑了 DataEase，要升级版本、备份、看服务状态。"——机上自带 `dectl` 运维命令。

**不要用它**：

- **想在命令行里跑 SQL、把结果导出成文件**——DataEase 是 Web 可视化平台，不是数据库客户端；命令行侧只有运维命令，没有查询命令。这种活该用数据库自带的 CLI 或 csvkit 一类的工具。
- **要做 ETL 数据管道与定时调度开发**——它的定位是分析展示层，不是调度编排引擎。复杂数据加工应该在数仓侧做完再让平台直连。
- **只有一两张表、要一次性出个图**——装一套 Docker 编排的 BI 平台成本远高于直接 matplotlib / Excel 出图。
- **要世界地图、流向地图且服务器完全不通外网**——这类组件依赖在线地图服务，不通外网会白屏，除非自行申请地图 Key 并配置。
- **期望纯社区版就有企业级权限、告警、血缘**——这些归属于 X-Pack 能力，社区版与企业版功能范围不同，先对照官方版本对比再决定。
- **要求二次开发闭源分发**——项目采用 GPLv3，商用与再分发前先确认许可证义务。

## 安装

### 在线一键安装（推荐先试这条）

官方要求：64 位 Linux（文档口径为 Ubuntu 22.04 / CentOS 7.6），4 核 8G 起，磁盘 200G，服务器**能访问互联网**，以 root 执行：

```bash
curl -sSL https://dataease.oss-cn-hangzhou.aliyuncs.com/quick_start_v2.sh | bash
```

注意别拿成 `quick_start.sh`（那一版对应的是已停止维护的 v1 社区版）。

### 离线安装

1. 到官方社区下载页取最新基础安装包，复制到目标机 `/tmp`；
2. 解压并进入目录（包名以实际下载到的为准）：

```bash
cd /tmp
tar zxvf dataease-online-installer-<版本>.tar.gz
cd dataease-online-installer-<版本>
```

3. 按需改 `install.conf`：安装目录 `DE_BASE`、服务端口 `DE_PORT`（默认 8100）、登录超时 `DE_LOGIN_TIMEOUT`、安装模式 `DE_INSTALL_MODE`，以及 `DE_EXTERNAL_MYSQL=false` 与 `DE_MYSQL_*` 一组外部库参数。**具体字段以安装包里那份 `install.conf` 为准**，不同版本可能增删。
4. 跑安装脚本：

```bash
/bin/bash install.sh
```

### 部署前提

- Docker 版本过旧会导致安装失败。官方建议直接用安装包内自带的 Docker，或使用 v23.0.5 及以上版本。
- 默认安装目录为 `/opt/dataease2.0`，配置、数据、日志都在里面，规划磁盘时把它算进去。
- 需要放通 22（SSH 运维）与 8100（Web 服务）端口，云主机还要检查安全组。
- 登录地址 `http://<服务器IP>:8100`，初始账号 `admin` / `DataEase@123456`。

## 常用操作

**1. 看服务和各容器状态**

```bash
dectl status
```

等价于系统 Service 的 `dataease status`。排查"页面打不开"先跑这条，确认容器是起来了还是挂了。

**2. 启停与重启**

```bash
dectl start
dectl stop      # 停止服务，并清理相关运行容器与 docker 网络等资源
dectl restart
dectl reload    # 改了配置后重新加载
```

**3. 查版本、在线升级、清镜像**

```bash
dectl version
dectl upgrade
dectl clear-images    # 清理旧版本遗留镜像，升完级腾磁盘用
dectl clear-logs      # 清理历史日志
```

**4. 备份与恢复（需要 v2.4 及以上）**

```bash
dectl backup
dectl restore
```

参数与备份产物位置以 `dectl help` 和官方安装部署文档中的说明为准。**升级前先备份**，这是这套系统里最值钱的一条纪律。

**5. 忘记 admin 密码时用数据库重置**

先在 `/opt/dataease2.0/conf/mysql.env` 里取到系统数据库密码，连上 DataEase 用的 MySQL 后：

```sql
-- 用户表为 per_user，pwd 字段存的是密码的 md5 值
update per_user set pwd='504c8c8dfcbbe5b50d676ad65ef43909' where account='admin';
```

上面这条哈希对应密码 `DataEase@123456`，也就是重置回初始密码。

**6. 外部 MySQL 的建库语句**

```sql
CREATE DATABASE `dataease` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

服务启动时会自动在配置的库里建表并写初始化数据，不需要手工导表结构。

**7. 服务端超时的调整入口**

出现 `timeout of xxx exceeded` 一类报错时，走【系统管理】→【系统参数】→【基础设置】调大超时时间；单个数据源还可以在它的【高级设置】里单独改查询超时。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 跟着旧教程装完发现版本对不上、功能缺失 | 文档里 `quick_start.sh` 对应的是 v1 社区版，而 v1 社区版已停止维护 | 新装一律用 `quick_start_v2.sh` 或 v2 的离线安装包；已有 v1 环境按官方生命周期说明规划迁移 |
| 装到一半失败，或容器起不来 | 宿主机 Docker 版本过旧 | 用安装包内自带的 Docker，或升到 v23.0.5 及以上再装 |
| 接了外部 MySQL 后建库/启动报错 | 外部库对版本与一串 `[mysqld]` 参数有硬要求 | 外部库要求 MySQL 8.0.16 以上；重点确认 `character_set_server=utf8`、`lower_case_table_names=1`、`group_concat_max_len=1024000`，其余参数照官方给的那份 `[mysqld]` 段抄 |
| 流向地图、符号地图加进仪表板后一片白 | 这些组件用的是在线地图服务，服务器出不了外网就取不到底图 | 让服务器能访问地图服务，或自行申请在线地图 Key 并在系统参数里配置 |
| 改了密码又忘了，登不进去 | 忘记当前密码时界面上没有自助重置入口 | 走数据库重置：从 `/opt/dataease2.0/conf/mysql.env` 拿库密码，改 `per_user.pwd` 为某个密码的 md5 |
| 升级后磁盘告急 | 旧版本镜像不会自动清 | 升级完成后执行 `dectl clear-images`，日志多了用 `dectl clear-logs` |
| 页面打得开但图表一直转圈、偶尔报超时 | 查询链路本身慢或网络抖动，默认超时不够 | 系统参数里调大基础超时，并按数据源在【高级设置】里单独放宽查询超时 |
| 云主机上本地 curl 通、外面打不开 | 只放通了系统防火墙，没开云平台安全组 | 云主机需同时确认安全组里 8100 已放通 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 在线安装脚本要从官方对象存储拉包；服务本身要连你配置的数据源；地图类组件还要访问在线地图服务 |
| 读取文件 | 是 | 读取 `/opt/dataease2.0` 下的配置（如 `conf/mysql.env`）与数据目录；读取本地 Excel/CSV 上传的数据文件 |
| 写入文件 | 是 | 安装脚本写入安装目录与 Docker 数据卷；导入 Excel 会落盘；备份命令会产出备份文件 |
| 凭证 | 是 | 需要目标机 root/sudo 执行安装；需要各数据源的连接账号；初始 Web 账号为 `admin`，首次登录后应立即改密 |
| 子进程 / 后台常驻 | 是 | 安装与运维都经 Docker 拉起多个长期运行的容器（应用、MySQL、APISIX 等），并注册系统 Service |

## 触发场景

- "给我装一套开源的 BI，能连 MySQL 出图表。"
- "这台服务器不联网，怎么离线部署数据可视化平台？"
- "想做个每周更新的经营看板，业务同事能自己拖图。"
- "会议室的屏幕要放实时数据大屏。"
- "DataEase 页面打不开了，帮我看看容器状态。"
- "要升级 DataEase，先怎么备份？"
- "admin 密码忘了，只能进服务器，怎么重置？"

## 能力边界

**覆盖**：

- 部署形态：Linux 服务器上的 Docker 编排部署，官方提供在线一键安装、离线安装包、源码部署、云平台与 1Panel 安装等多条路径
- 数据源：MySQL、MariaDB、Oracle、SQL Server、DB2、PostgreSQL、ClickHouse、Doris、StarRocks、TiDB、MongoDB-BI、Elasticsearch、Hive、Impala、PrestoDB、Kylin、Redshift、达梦、人大金仓，以及本地/远程 Excel 与 API 数据源
- 分析呈现：数据集、仪表板、数据大屏、图表与过滤组件，支持 PC / 移动端 / 大屏三种展示形态
- 数据引擎：支持直连模式，也支持本地模式（基于 Apache Doris）
- 运维：`dectl` 与系统 Service 提供状态查看、启停、重启、重载、在线升级、版本查询、镜像与日志清理、备份恢复

**不覆盖**：

- 命令行查询与数据导出：没有 SQL CLI，分析操作都在浏览器里完成
- ETL 编排与作业调度：不做数据加工流水线，脏数据要在上游数仓处理
- 机器学习 / 预测建模：只做描述性分析与可视化呈现
- 桌面单机版之外的个人绘图需求：一次性画图交给 matplotlib 一类库更划算
- 社区版不含 X-Pack 的企业能力（组织管理、权限体系、定时报告、血缘、告警、Webhook、嵌入等），这些属于另一套版本范围

## 依赖条件

- 64 位 Linux 服务器（文档口径 Ubuntu 22.04 / CentOS 7.6），4 核 8G 内存、200G 磁盘起
- Docker：建议用安装包内自带的，或 v23.0.5 及以上
- 在线安装需要服务器可访问互联网；离线安装需要先手工取得安装包
- 若使用外部数据库，要求 MySQL 8.0.16 以上并按官方参数调优
- root 权限用于安装与运维；Web 端初始账号 `admin` / `DataEase@123456`
- 服务器开放 22 与 8100 端口（端口可在 `install.conf` 中更改）

## 已知限制

1. 社区版与企业版功能范围不同，权限、告警、定时报告、血缘、嵌入等能力需要对照官方版本对比确认。
2. v1 社区版已停止维护，网络上大量旧教程与旧安装脚本仍指向 v1，照抄会走错路。
3. `install.conf` 的字段、`dectl` 的子命令在不同版本间可能有差异，以本机实际文件与 `dectl help` 输出为准。
4. 地图类可视化依赖在线地图服务，纯内网环境需自行申请 Key 并配置。
5. 备份/恢复命令自 v2.4 起提供，低版本没有这两个子命令。
6. 项目为 GPLv3 许可，商用与再分发前需自行确认合规义务。
7. 官方文档站会随版本更新，文中链接指向的章节结构也可能调整。

## 自检清单

执行前：

- [ ] 确认目标机是 64 位 Linux，内存不低于 8G，磁盘留够 200G
- [ ] 确认 Docker 版本满足要求（自带安装包或 v23.0.5+）
- [ ] 确认这是全新环境还是要复用已有数据库：复用则必须满足 MySQL 8.0.16+ 与那组 `[mysqld]` 参数
- [ ] 确认服务器能出外网（在线安装 / 地图组件）
- [ ] 确认 8100 端口在系统防火墙与云安全组两处都放通
- [ ] 离线安装前核对下载到的安装包版本，不要拿 v1 的包
- [ ] 升级场景必须先 `dectl backup` 再动手

执行后：

- [ ] `dectl status` 各容器为运行状态
- [ ] 浏览器能打开 `http://<IP>:8100` 并用 admin 登录
- [ ] **立刻修改 admin 初始密码**
- [ ] 接一个数据源、建一个数据集、拖出一张图，确认查询链路通
- [ ] 需要备份策略的话，确认 `dectl backup` 能跑通并把产物挪到别的机器

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/dataease/dataease | 上游仓库（安装与完整文档以它为准） |
| https://dataease.io/docs/v2/installation/offline_INSTL_and_UPG/ | 官方安装指南：环境要求、离线包、install.conf 参数 |
| https://dataease.io/docs/v2/installation/online_installation/ | 官方在线安装：一键脚本、端口要求 |
| https://dataease.io/docs/v2/installation/cli/ | 官方命令行工具说明：dectl 子命令与系统 Service |
| https://dataease.io/docs/v2/faq/system_management/ | 官方系统管理常见问题：改密、重置密码、超时、地图白屏 |

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
