---
name: sanjianke-jimureport
slug: sanjianke-jimureport
displayName: 三剪客 · 在线报表与大屏设计器
description: "JimuReport：给 Java 后端项目套一层在线报表与大屏设计器——类 Excel 的 Web 拖拽设计、30 多种数据源、分组/交叉/主子报表与套打打印，还能用自然语言让 AI 直接生成报表和大屏。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "JimuReport 的集成与部署：SpringBoot starter 引入、初始化 SQL、示例项目启动、Docker Compose 起服务、默认账号与入口地址、AI 助手接入配置，以及 JDK 版本、数据库脚本、端口、授权协议等关键坑位。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - BI

---

# 三剪客 · 在线报表与大屏设计器

业务系统里总有一批"数据要对、格式还要跟纸质单据一致"的报表需求：财务报表、出入库单、发票套打、参数化查询、分组交叉汇总。手写的话每张报表都是一次前后端联调加导出适配；JimuReport 的思路是把这些做成 Web 端拖拽设计，业务改格式不用改代码。

它的形态是一个**集成进 SpringBoot 项目的报表引擎**：引入 starter 依赖、执行一次初始化 SQL、启动项目，就能在设计器里像搭积木一样拖单元格、配数据源、绑字段，做完直接预览和打印。同一套体系下还有大屏与仪表盘设计器，以及一个对话式的数据分析模块。

**上游项目**：`jimureport`　**仓库**：https://github.com/jeecgboot/jimureport

> 版本信息：仓库 README 头部标注的版本号为 v2.5.2。starter 的 artifactId 与版本号在不同 SpringBoot 大版本下**不一样**，务必按你项目的 SpringBoot 版本对照官方集成文档选依赖，不要照抄另一个版本的坐标。

## 什么时候用 / 不用

**用它**：

- "这个系统要出一批格式复杂的报表，分组、交叉、主子表、多表头都有。"——设计器覆盖分组 / 交叉 / 主子 / 明细 / 多表头 / 多 Sheet 等报表形态。
- "客户要套打发票 / 证照 / 入库单，版式毫米级对齐。"——支持套打、背景打印和自定义打印模板。
- "数据源不止一个库，还有 Hive、ClickHouse、Doris、ES、MongoDB。"——官方列出 30 多种数据源，支持 SQL / API / JSON / WebSocket 方式绑定。
- "不想为了几张报表单独买商业报表工具。"——开源版功能免费可商用，类 Excel 的在线设计器是核心替代点。
- "想让 AI 直接按一句话生成报表或大屏。"——可接入 OpenAI 兼容的模型服务，在设计器里用自然语言或截图生成报表 / 大屏 / 仪表盘。
- "要在信创环境里跑，数据库是达梦 / 人大金仓 / 高斯，系统是麒麟或统信。"——官方明确列出了国产数据库与操作系统的适配。

**不要用它**：

- **不是 Java / SpringBoot 项目**——它是 SpringBoot starter 形态的引擎，Python、Node、Go 项目集成不了（这类场景看 Metabase、Superset、Lightdash 一类独立部署的 BI）。
- **只是临时导出几张 Excel**——用 EasyExcel / Apache POI 之类的库直接写更轻，不必引入一套报表引擎和它的元数据库。
- **不想为它单独准备一个数据库**——它需要初始化自己的元数据表（示例工程用 MySQL 5.7+），这是硬前置。
- **需要完全自由的 BI 探索式分析（拖拽任意维度、下钻、即席查询）**——它的强项是"固定版式的复杂报表 + 大屏"，探索式分析用专业 BI 工具更合适。
- **不接受它的授权条款**——开源版是 LGPL 与附加条款的双许可模式，且**明确禁止**基于它修改包装后发布或销售同类竞争产品，二次开发还必须保留官方版权标识（预览页的 "Powered by" 字样、Logo 与官方链接）。商用去版权标识需要购买商业授权。用之前先把授权协议读完。
- **只想做一个简单看板，团队没人维护 Java 服务**——引入后要跟着它升级、要管元数据库、要维护 JDK 版本，运维成本要提前算。

## 安装

### 方式一：集成进已有 SpringBoot 项目

**第一步**，按你的 SpringBoot 大版本引入对应 starter（以下坐标取自仓库 README，**版本号请以官方集成文档当前值为准**）：

```xml
<!-- SpringBoot3 -->
<dependency>
  <groupId>org.jeecgframework.jimureport</groupId>
  <artifactId>jimureport-spring-boot3-starter</artifactId>
  <version>2.5.2</version>
</dependency>

<!-- 大屏与仪表盘（JimuBI） -->
<dependency>
  <groupId>org.jeecgframework.jimureport</groupId>
  <artifactId>jimubi-spring-boot3-starter</artifactId>
  <version>2.5.2</version>
</dependency>

<!-- SpringBoot4 -->
<dependency>
  <groupId>org.jeecgframework.jimureport</groupId>
  <artifactId>jimureport-spring-boot4-starter</artifactId>
  <version>2.5.2</version>
</dependency>
```

SpringBoot2 用 `jimureport-spring-boot-starter`，但**不支持 AI 助手**；另有 `jimureport-nosql-starter*`（MongoDB / Redis / 文件数据集）与 `jimureport-echarts-starter`（后台导出接口的图表支持）按需引入。

**第二步**，初始化数据库：执行仓库里的建库脚本（示例工程用的是 `db/jimureport.mysql5.7.create.sql`，会自动创建 `jimureport` 库）。

**第三步**，配置数据源与必要参数（示例工程配置在 `src/main/resources/application-dev.yml`），启动项目。

### 方式二：直接跑示例工程

```bash
git clone https://github.com/jeecgboot/jimureport.git
cd jimureport/jimureport-example
mvn clean package
# 右键运行 com.jeecg.JimuReportApplication，或
mvn spring-boot:run
```

环境要求：JDK 17+（示例工程为 SpringBoot 4 架构）、MySQL 5.7+（先手工执行 `db/jimureport.mysql5.7.create.sql`）、Redis 可选。

启动后访问（默认账号 `admin` / 密码 `123456`，**上线前务必改密码**）：

- 报表工作台：`http://localhost:8085/jmreport/list`
- 仪表盘工作台：`http://localhost:8085/drag/list`

### 方式三：Docker Compose

在 `jimureport-example` 根目录（先 `mvn clean package` 打好包）：

```bash
docker-compose up -d
```

Mac M 系列芯片需要把基础镜像换成 arm 平台：把 `db/Dockerfile` 第一行改为 `FROM arm64v8/mysql:8`；`Dockerfile` 里的 JDK 基础镜像同样要换成 arm 架构的镜像。

## 常用操作

**1. 只引入报表引擎（最小集成）**

```xml
<dependency>
  <groupId>org.jeecgframework.jimureport</groupId>
  <artifactId>jimureport-spring-boot3-starter</artifactId>
  <version>2.5.2</version>
</dependency>
```

引入后重启项目，设计器入口随 starter 一起生效，不需要单独部署前端。

**2. 配置 AI 助手（在设计器里用自然语言生成报表）**

在 `application.yml` 里按下面这段配置（取自仓库 README）：

```yaml
jeecg:
  jmreport:
    ai:
      base-url: https://api.deepseek.com     # OpenAI 兼容接口地址（必填）
      api-key: sk-xxxxxxxxxxxxxxxxxxxx       # API Key（必填，留空 AI 功能不可用）
      model: deepseek-v4-pro                  # 模型名（必填）
      max-tokens:                             # 可选，单次生成最大 token
      temperature: 0                          # 可选，建议 0 保证输出稳定
      completions-path: /v1/chat/completions  # 可选，默认值就是它
      autoTableEnabled: false                 # 允许 AI 执行 DDL/DML，生产务必 false
```

只要是兼容 OpenAI Chat Completions 格式的服务商都能接，把 `base-url` 指过去即可（官方 README 里列了几家常用服务商的地址与推荐模型）。

**3. 初始化数据库**

```bash
mysql -u <用户> -p < db/jimureport.mysql5.7.create.sql
```

脚本会创建 `jimureport` 库与所需元数据表。换其它数据库时，官方只提供了部分库的脚本，其余需要按官方文档自行转换。

**4. 以 Java 方式构建并启动示例**

```bash
cd jimureport-example
mvn clean package
java -jar target/*.jar
```

**5. 用 Docker Compose 起一套（含 MySQL）**

```bash
cd jimureport-example
mvn clean package
docker-compose up -d
docker-compose logs -f          # 看启动日志
docker-compose down             # 停掉
```

**6. 配好一个数据源后的典型设计流程**

在报表设计器里：新建数据源（填 JDBC 连接）→ 新建数据集（写 SQL、加参数）→ 单元格绑定字段（`#{数据集.字段}` 之类的表达式）→ 设置分组 / 合计 / 打印区域 → 预览 → 导出 Excel / PDF / Word / 图片。**具体表达式语法与函数（SUMIFS、VLOOKUP、IF 等）以官方开发文档为准**，各版本间可能有差异。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 项目启动报类找不到 / 依赖冲突，或 starter 坐标报红 | starter 的 artifactId 与 SpringBoot 大版本是绑定的（2 / 3 / 4 三套），拿错版本就装不上 | 先确认自己的 SpringBoot 大版本，再按官方集成文档选对应 artifactId；不要混用不同版本的 starter |
| 启动报 `Unknown database 'jimureport'` 或元数据表不存在 | 只加了依赖，没有执行初始化 SQL | 手工执行仓库里的建库脚本（MySQL 示例脚本会创建 `jimureport` 库），再启动 |
| 启动直接报 JDK 版本不兼容（UnsupportedClassVersionError 之类） | 示例工程要求 JDK 17+（SpringBoot 4 架构）；SpringBoot2 版要求 JDK 8+ | 用与 starter 版本匹配的 JDK；多版本 JDK 的机器上确认 `JAVA_HOME` 和 IDE 的编译级别都改了 |
| 8085 端口起不来 / 启动日志报端口占用 | 示例工程默认 8085，容易被别的服务占 | 改 `application-dev.yml` 里的 `server.port`，或者先停掉占用进程 |
| 登录不上，或者一直提示密码错误 | 默认账号是 `admin` / `123456`，但实际库里可能已被改过；也可能是初始化脚本没跑全 | 确认 SQL 脚本完整执行；默认密码能登进去后**第一件事就是改密码**，别把 `123456` 带上生产 |
| 设计器里能连数据源，但预览报无数据 | 数据集 SQL 与数据源不是同一个库、参数没传、或者数据集没设成允许参数为空 | 先在数据集里直接执行 SQL 看有没有结果，再排查参数绑定；跨库取数要用多源报表配置 |
| Docker Compose 起来后应用一直重启 | 应用启动比 MySQL 就绪快，连不上库 | 看 `docker-compose logs`；等 MySQL 健康后再重启应用容器，或给应用加依赖等待 / 重试配置 |
| Mac M 系列芯片上镜像跑不起来 | 官方给的 MySQL / JDK 基础镜像是 x86 平台 | 按官方说明把 `db/Dockerfile` 第一行改成 `FROM arm64v8/mysql:8`，并准备一个 arm 架构的 JDK 基础镜像替换应用 Dockerfile 的第一行 |
| 导出 Excel / PDF 时图表缺失 | 后台导出接口的图表需要额外的 echarts 支持包 | 按需引入 `jimureport-echarts-starter` |
| 用了 Mongo / Redis / 文件数据集报错 | 这些数据源在单独的 nosql starter 里 | 引入 `jimureport-nosql-starter3`（SpringBoot3）或对应版本的 nosql starter |
| 升级版本后老报表打不开或样式异常 | 报表元数据结构的版本兼容问题 | 升级前备份元数据库，按官方「升级注意」文档逐版本升级，不要跨大版本直接跳 |
| 想拿掉预览页的官方版权标识被拒 | 开源协议明确要求保留版权标识，去掉属于商业授权范围 | 要么保留标识，要么按官方渠道购买商业授权；不要自行抹除 |
| AI 生成的报表把库表改了 | 开了 `autoTableEnabled: true`，它会真的执行 DDL/DML | 生产环境保持 `false`；只在隔离的测试库上开启验证 |
| 想基于它改一版卖给客户 | 授权条款明确禁止修改包装后发布 / 销售同类竞争产品 | 先读完整的授权协议和补充条款；这类用途需要走商业授权谈 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 服务端要连数据源（数据库 / API / ES / MongoDB 等）；开启 AI 助手时还要访问外部模型服务接口 |
| 读取文件 | 视情况 | 文件数据集、Excel / CSV / JSON 导入会读本地或上传的文件 |
| 写入文件 | 视情况 | 导出 Excel / PDF / Word / 图片会生成文件；日志与临时目录也涉及写入 |
| 凭证 | 是 | 数据源连接串含库的用户名密码；AI 配置含模型服务的 API Key。这些都要放在配置中心或环境变量里，**不要提交到仓库** |
| 子进程 / 后台常驻 | 是 | 它本身就是一个常驻的 Java Web 服务；Docker 方式还会拉起数据库容器 |
| 执行数据库 DDL/DML | 视情况 | `autoTableEnabled: true` 时 AI 能建表改表；数据填报功能会回写业务库。生产环境必须收紧 |
| 对外暴露 Web 界面 | 是 | 设计器与预览页默认对访问者开放，默认账号密码必须立刻更换并接入你们自己的鉴权 |

## 触发场景

- "我们系统要出一批复杂报表，分组交叉加主子表，有没有在线设计的工具。"
- "客户要套打发票，版式要跟纸质单据对齐。"
- "这个报表要连 Hive 和 ClickHouse，能一个工具搞定吗。"
- "帮我在 SpringBoot 项目里集成一个报表模块。"
- "能不能让 AI 按一句话直接生成报表和看板。"
- "要做数据大屏，组件能拖拽、图表类型多。"
- "报表要支持导出 Excel、PDF、Word 和图片。"
- "能不能适配达梦 / 人大金仓这些国产库。"

## 能力边界

**覆盖**：

- **报表设计**：类 Excel 的 Web 拖拽设计器，分组 / 交叉 / 主子 / 明细 / 多表头 / 多 Sheet / 条件查询 / 表达式合计、数据钻取、二维码条码、预警
- **打印**：自定义打印模板、套打、背景打印、分页与打印区域、发票与证照类精准打印
- **数据源**：官方口径 30 多种，含 MySQL、Oracle、SQL Server、PostgreSQL、DB2、MariaDB、SQLite、Hive、ClickHouse、Doris、TiDB、ES、MongoDB，以及达梦、人大金仓、神通、高斯等国产库；支持 SQL / API / JSON / WebSocket / 存储过程 / 文件数据集，支持多源报表
- **数据填报**：在线录入、校验规则、下拉/字典/日期控件、批量导入、回写数据库
- **大屏与仪表盘**：大屏拖拽设计（含地图类组件）、栅格仪表盘、门户看板，PC / 移动 / 大屏多端适配
- **导出**：Excel、PDF、Word、图片
- **AI 能力**：接入 OpenAI 兼容接口后，可用自然语言生成报表 / 大屏 / 仪表盘、上传截图还原模板，以及对话式数据分析模块
- **信创**：国产数据库与麒麟 / 统信 UOS 等国产操作系统的适配

**不覆盖**：

- **非 Java 技术栈的集成**——它是 SpringBoot starter 形态，Python / Node / Go 项目无法直接引入
- **数据库本身的安装与运维**——它只提供建库脚本，生产库的部署、备份、高可用要你自己负责
- **数据仓库建模与调度**——不做 ETL、不做数据分层、不做任务编排
- **探索式即席 BI**——强项是固定版式报表与看板，自由探索式分析不是它的定位
- **移动端原生 App**——提供的是移动端 H5 适配，不是原生客户端
- **帮你判断数据合规**——报表里放什么数据、给谁看、留多久，需要使用者自己按行业与法规要求把关
- **免除授权义务**——去版权标识、做同类竞品、商用分发都要先解决授权问题

## 依赖条件

- **集成方式**：JDK 17+ 配合 SpringBoot4 版 starter；SpringBoot3 版支持 AI 助手；SpringBoot2 版不支持 AI 助手（具体以官方集成文档为准）
- **数据库**：需要为它准备一个库来存报表元数据，示例工程用 MySQL 5.7+；换库需按官方文档转换脚本
- **Redis**：可选（用于权限相关集成）
- **构建**：Maven（示例工程 `mvn clean package`）
- **容器化**：Docker 与 Docker Compose（走容器方式时）
- **AI 助手**：需要自备兼容 OpenAI Chat Completions 格式的模型服务地址与 API Key
- **授权**：开源版为 LGPL 与附加条款的双许可模式，商用去标识需购买商业授权

## 已知限制

1. starter 坐标与 SpringBoot 大版本强绑定，选错版本无法启动，升级 SpringBoot 时要同步换 starter。
2. 强依赖一个元数据库，必须完成初始化 SQL 才能启动，这是无法绕过的部署步骤。
3. 官方只提供了部分数据库的初始化脚本，其它库需要自行按文档转换。
4. 开源版**要求保留官方版权标识**，且**禁止**修改包装后发布或销售同类竞争产品；这两条会直接影响部分商业用途。
5. AI 助手的能力取决于你接入的模型服务；`autoTableEnabled` 打开后 AI 会真实执行 DDL/DML，是明确的安全风险点。
6. 默认账号密码是公开的 `admin` / `123456`，且界面默认对外可访问，上线前必须换密码并接入自己的鉴权。
7. 跨大版本升级涉及元数据结构变化，需要按官方升级说明逐步进行并先备份。

## 自检清单

执行前：

- [ ] 确认项目是 SpringBoot 且版本与所选 starter 匹配（2 / 3 / 4 三套坐标别拿错）
- [ ] JDK 版本满足要求（示例工程为 JDK 17+），IDE 编译级别也改过
- [ ] 元数据库已就绪，初始化 SQL 已完整执行，并已备份
- [ ] 数据源连接串与 AI 的 API Key 走配置中心或环境变量，没有硬编码进仓库
- [ ] 端口 8085（或你改后的端口）没有冲突
- [ ] **读完了授权协议**，确认去标识 / 竞品 / 商用分发的边界
- [ ] 默认密码已改，设计器入口已接入你们自己的鉴权，不是裸奔

执行后：

- [ ] 用默认账号登进报表工作台与仪表盘工作台，各建一张最小报表验证数据源连通
- [ ] 验证导出（Excel / PDF / 图片）和打印预览符合预期
- [ ] 确认元数据库里已写入报表定义，并把它纳入备份策略
- [ ] 检查 `autoTableEnabled` 在生产配置里是 `false`
- [ ] 确认服务端日志里没有把连接串密码、API Key 打成明文
- [ ] Docker 方式部署时确认容器重启后数据仍在（数据卷挂载正确）

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/jeecgboot/jimureport | 上游仓库（安装与完整文档以它为准） |
| https://help.jimureport.com | 官方开发文档：集成步骤、设计器用法、常见问题 |
| https://github.com/jeecgboot/jimureport/tree/master/jimureport-example | 官方集成示例工程（含建库脚本） |

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
