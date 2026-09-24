---
name: sanjianke-metabase
slug: sanjianke-metabase
displayName: 三剪客 · 自助式 BI 与数据看板
description: "Metabase 的 Docker / JAR 自托管部署、接数据库、做问题与看板、定时订阅与告警、备份与升级，以及默认 H2 应用库、容器内 localhost、时区、插件目录权限、密码明文等生产部署高频坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "把公司的数据库接上来，让不会写 SQL 的同事用点选的方式提问、拼看板、定时收邮件。含 Docker 与 JAR 两种自托管方式、生产环境必须换掉默认应用库、Docker Secrets 传密码、应用库备份与升级注意点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - BI

---

# 三剪客 · 自助式 BI 与数据看板

团队里想看一眼数据的人很多，会写 SQL 的往往就一两个。Metabase 解决的就是这个错位：把数据库连上来一次，之后不会 SQL 的同事用点选的方式"问问题"、把结果拼成看板、设定时把看板发到邮箱或群里；会 SQL 的人仍然可以直接写原生查询，并把它保存成别人能复用的"问题"。

它的形态是**一个要长期跑在服务器上的 Web 服务**，不是一个跑完就结束的命令。所以真正要小心的不是"怎么用"，而是"应用数据存在哪、升级怎么升、密码怎么放"。

**上游项目**：`metabase`　**仓库**：https://github.com/metabase/metabase

## 什么时候用 / 不用

**用它**：

- "业务同事想自己看数据，不想每次都来提需求让开发跑 SQL。"——自助提问加看板是它的主场景。
- "同一张日报看板，每天早上自动发到邮箱或群里。"——看板订阅与告警。
- "数据散在几个库里，想在一个界面上横着看。"——支持同时接入多个数据库，官方列了支持清单与社区驱动。
- "想把分析结果嵌到自己产品的后台里给客户看。"——官方提供嵌入式方案（模块化嵌入、交互式嵌入）。
- "不想买商业 BI，又要私有化部署、数据不出内网。"——可自托管，Docker 一个容器就能起。

**不要用它**：

- **只是自己临时算一下一张 CSV**——那是 pandas 的活；为了看一次数据去部署一个 Web 服务不划算。
- **要做 ETL / 数仓调度**——它不是调度器；原始库到分析库的搬运、分层建模交给专门的工具，它更擅长"接上已经建好的表去查"。
- **要做面向公网的高并发埋点查询**——它是给团队看数的 BI 前端，不适合当高 QPS 的查询网关。
- **团队完全不打算维护一台服务器**——自托管意味着你要管应用库备份、升级、时区、权限；只想省事就该用它的云版本或换别的方式。
- **需要官方 Helm chart 或云市场一键部署**——官方明确说不提供 Helm chart，也没有上架主流云市场，编排要自己写。

## 安装

官方推荐自托管走 Docker；不想用 Docker 才用 JAR。

**方式一：Docker（官方推荐的自托管方式）**

```bash
# 拉取镜像
docker pull metabase/metabase:latest

# 起一个本地实例（默认端口 3000）
docker run -d -p 3000:3000 --name metabase metabase/metabase

# 看启动日志，等到出现初始化完成的日志再访问
docker logs -f metabase

# 换端口，例如对外用 12345
docker run -d -p 12345:3000 --name metabase metabase/metabase
```

启动完成后访问 `http://localhost:3000`，首次进入会引导建管理员账号并连接业务数据库。

**方式二：JAR**

需要先装 Java 运行时。官方建议使用 **Java 25**（JRE，HotSpot JVM），并明确说明更早的 Java 版本不受支持。

```bash
# 1. 从官方页面下载 oss 版 jar，放进一个新建的空目录
#    https://www.metabase.com/start/oss/jar

# 2. 在该目录下启动
java --add-opens java.base/java.nio=ALL-UNNAMED -jar metabase.jar
```

看到初始化完成的日志后访问 `http://localhost:3000/setup`。用 `MB_JETTY_PORT` 可以换端口。

**方式三：生产部署（关键差别：换掉默认应用库）**

官方提示：默认的嵌入式 H2 应用库把数据存在文件系统里，**删掉容器就会丢掉全部问题、看板和集合**。生产环境要换成 Postgres 之类的正式数据库：

```bash
docker run -d -p 3000:3000 \
  -e "MB_DB_TYPE=postgres" \
  -e "MB_DB_DBNAME=metabaseappdb" \
  -e "MB_DB_PORT=5432" \
  -e "MB_DB_USER=name" \
  -e "MB_DB_PASS=password" \
  -e "MB_DB_HOST=my-database-host" \
  --name metabase metabase/metabase
```

应用库不需要预先建表，Metabase 启动时会自己建。

其他安装方式（Podman、systemd 服务、从源码构建、air-gapped 环境）见官方安装文档。

## 常用操作

**1. 用 docker compose 一起起应用库和服务**

```yaml
services:
  metabase:
    image: metabase/metabase:latest
    container_name: metabase
    hostname: metabase
    volumes:
      - /dev/urandom:/dev/random:ro
    ports:
      - 3000:3000
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabaseappdb
      MB_DB_PORT: 5432
      MB_DB_USER: metabase
      MB_DB_PASS: mysecretpassword
      MB_DB_HOST: postgres
    networks:
      - metanet1
    healthcheck:
      test: curl --fail -I http://localhost:3000/api/health || exit 1
      interval: 15s
      timeout: 5s
      retries: 5
  postgres:
    image: postgres:16
    container_name: postgres
    hostname: postgres
    environment:
      POSTGRES_USER: metabase
      POSTGRES_DB: metabaseappdb
      POSTGRES_PASSWORD: mysecretpassword
    volumes:
      - ./pg_data:/var/lib/postgresql/data
    networks:
      - metanet1
networks:
  metanet1:
    driver: bridge
```

**2. 起完先验活：看日志和健康检查接口**

```bash
docker logs -f metabase
curl -I http://localhost:3000/api/health
```

`/api/health` 是官方 docker compose 示例里用的健康检查地址，接到编排或监控里很省事。

**3. 把应用数据挂到宿主机（想保留又不想立刻上生产库时的过渡做法）**

```bash
docker run -d -p 3000:3000 \
  -v ~/metabase-data:/metabase-data \
  -e "MB_DB_FILE=/metabase-data/metabase.db" \
  -e MUID=$UID -e MGID=$GID \
  --name metabase metabase/metabase
```

`MUID` / `MGID` 是 Docker 专用变量，用来让容器内进程的用户和组 ID 跟宿主机文件属主对上。

**4. 设时区，让报表按本地日期切分**

```bash
docker run -d -p 3000:3000 \
  -e "JAVA_TIMEZONE=Asia/Shanghai" \
  --name metabase metabase/metabase
```

**5. 挂插件目录装数据库驱动（Oracle、Vertica 或社区驱动）**

```bash
docker run -d -p 3000:3000 \
  --mount type=bind,source=/path/to/plugins,destination=/plugins \
  --name metabase metabase/metabase
```

注意这个目录必须**可读写**：Metabase 会用它解压随发行版自带的驱动（比如 SQLite）。

**6. 用 Docker Secrets 藏住密码**

把连接参数写进文件，环境变量名后面加 `_FILE`：

```yaml
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabase
      MB_DB_PORT: 5432
      MB_DB_USER_FILE: /run/secrets/db_user
      MB_DB_PASS_FILE: /run/secrets/db_password
      MB_DB_HOST: postgres
```

官方列出支持这种写法的变量包括：`MB_DB_USER`、`MB_DB_PASS`、`MB_DB_CONNECTION_URI`、`MB_EMAIL_SMTP_PASSWORD`、`MB_EMAIL_SMTP_USERNAME`、`MB_LDAP_PASSWORD`、`MB_LDAP_BIND_DN`。

**7. 备份应用库（默认 H2 的情况下）**

```bash
# 默认路径 /metabase.db/metabase.db.mv.db，复制出来即可
docker cp metabase:/metabase.db ./
```

换成 Postgres 应用库之后，备份就走数据库自己的备份手段。

**8. 从 H2 迁到生产应用库**

已经用默认应用库跑出了看板再想换库，不要手工搬文件——按官方 `migrating-from-h2` 文档给出的流程操作。原则是**越早换越好**。

**9. 用 API 对接**

登录建立会话后，后续请求带上会话头 `X-Metabase-Session`（具体的端点、字段与示例以官方 API 文档为准）。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 升级或重建容器之后，所有问题、看板、集合全没了 | 默认应用库是嵌入式 H2，把应用数据存在容器文件系统里；删掉容器就一起删了 | 生产环境一开始就用 Postgres 等正式数据库当应用库（`MB_DB_*` 系列变量），本地试用阶段至少把 `/metabase-data` 挂到宿主机 |
| 容器里连不上宿主机上的数据库，报连接超时 | 容器内的 `localhost` 指容器自己，不是宿主机 | 用宿主机在容器网络里可达的主机名或服务名；官方也提示可以给容器的 `/etc/hosts` 加条目。用 compose 时直接用服务名（如 `postgres`） |
| 报找不到驱动 / 装的自定义驱动没生效 / 插件目录只读报错 | Metabase 会用 `/plugins` 目录解压自带驱动，这个目录必须可读写 | 用 `--mount type=bind,source=/path/to/plugins,destination=/plugins` 挂载宿主机目录并确保容器内可写 |
| 报表的日期分组和业务口径差一天或几小时 | JVM 时区与数据库、业务时区不一致 | 设 `JAVA_TIMEZONE`（例如 `Asia/Shanghai`），并让数据库时区、看板里的时间字段口径一致 |
| 用非 root 用户跑，应用库文件属主不对，启动时报权限错误 | 容器内进程的 UID/GID 与宿主机挂载出来的文件属主不匹配 | 用 Docker 专用变量 `MUID` / `MGID` 指定容器内的用户与组 ID |
| `docker inspect`、CI 日志、命令历史里能看到数据库密码 | 密码直接写在 `docker run -e` 或 compose 的 environment 里，都是明文 | 用 Docker Secrets，把密钥放文件、变量名加 `_FILE` 后缀；官方支持的那几个变量见「常用操作」第 6 条 |
| JAR 方式启动直接失败，提示类文件版本或 JVM 相关错误 | 本机 Java 版本低于官方要求；官方建议 Java 25 并明确不支持更早版本 | 先 `java -version` 确认版本，按官方要求升级 JRE 后重试 |
| 照着教程找 Helm chart 找不到 | 官方明确表示不提供官方支持的 Helm chart，也未在主流云市场上架 | 自己写 Kubernetes 编排，或按官方生产部署指南用容器编排；别照抄来路不明的第三方 chart |
| 升级镜像后打不开或数据异常 | Metabase 升级会对应用库做结构迁移，跳版本或没备份风险很高 | 升级前先备份应用库，并严格按官方升级文档的版本路径操作 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 对外提供 Web 界面（默认 3000 端口）；同时要能访问被接入的业务数据库，以及邮件 / Slack / Webhook 等通知出口 |
| 读取文件 | 是 | 读取自身配置文件与挂载进来的插件目录；默认应用库模式下读取 `/metabase.db` |
| 写入文件 | 是 | 应用数据落盘（默认 H2 应用库文件、日志、缓存），并向挂载的 `/plugins` 目录解压驱动 |
| 凭证 | 是 | 业务数据库连接串、应用库连接串、管理员账号、邮件 SMTP 与 LDAP 密码、嵌入用的签名密钥。建议用 Docker Secrets 或环境变量注入，不要写进镜像和仓库 |
| 子进程 / 后台常驻 | 是 | 本体就是常驻 Web 服务，通常以容器或 systemd 服务方式后台运行，需要随机器自启 |

## 触发场景

- "帮我用 Docker 起一个 Metabase，接我们自己的 Postgres。"
- "业务方要自己看数，搭个能点选查询的看板服务。"
- "这个看板每天早上 9 点自动发到邮箱。"
- "Metabase 重启后看板全丢了，怎么回事？"
- "容器里连不上宿主机的 MySQL。"
- "要升级 Metabase 版本，先备份什么？"
- "想把报表嵌到我们自己的后台里。"

## 能力边界

**覆盖**：

- 自助提问：点选式查询构建器，不写 SQL 也能筛选、分组、汇总；也提供原生 SQL 编辑器与保存成可复用"问题"
- 看板与文档：交互式看板、筛选器、定时订阅、告警、长文分析文档，以及多种图表类型
- 数据接入：官方支持一批主流数据库，并有社区驱动可扩展；可直接查、也可做模型层（模型、指标、分段）
- 组织与治理：集合、权限（可细到表与行级场景）、内容验证、检索历史
- 嵌入与集成：模块化嵌入组件、整站交互式嵌入、对外开放 API
- 部署形态：Docker / Podman / JAR / systemd 服务 / 从源码构建 / air-gapped 环境
- 运维配套：健康检查接口、应用库可替换、应用库备份与升级路径

**不覆盖**：

- 数据抽取与调度：它不是 ETL 工具，不做跨库定时搬运与依赖编排
- 数据存储：不落业务数据，只存自己的应用数据（问题、看板、设置）和查询缓存
- 高并发查询网关：定位是团队看数，不适合扛公网大流量埋点查询
- 官方 Kubernetes 交付物：不提供官方 Helm chart，也没上架主流云市场
- 官方免费支持：开源版按 AGPL 发布，商业版本另有许可；软件本身的问题要走上游仓库
- 自动帮你设计指标口径：指标定义、权限划分这类治理工作仍需人来定

## 依赖条件

- Docker 方式：装好并运行 Docker（或 Podman），能拉取镜像
- JAR 方式：Java 运行时，官方建议 Java 25（HotSpot JVM），更早版本不受支持
- 生产环境另需一个正式数据库作为应用库（官方文档列出了支持的清单）
- 至少一个要分析的业务数据库的连接信息（地址、端口、库名、只读账号）
- 要发邮件订阅时需 SMTP 服务器；要接企业账号需 LDAP 配置
- 服务器资源视数据量与并发而定：它自身要占内存，查询压力主要落在被接的业务库上

## 已知限制

1. 默认 H2 应用库不适合生产，容器一删数据就没；这个默认值很容易在试用阶段被忽略。
2. 官方不提供 Helm chart，Kubernetes 部署要自己写；云市场也没有官方包。
3. 自托管意味着应用库备份、升级路径、时区、权限都要自己维护，官方推荐的做法是走它的云服务，自托管只解决"必须私有化"的问题。
4. 安全边界依赖你对数据库账号的授权：接入用的账号权限越大，Metabase 里能看到的就越多，建议按只读最小权限建账号。
5. 商业版本与开源自托管版本功能不同，评估功能前先确认版本口径。
6. 具体环境变量、API 端点与升级步骤随版本演进，以本机版本对应的官方文档为准。

## 自检清单

执行前：

- [ ] 明确这是试用还是生产：生产必须先准备正式应用库（不要用 H2）
- [ ] 数据库连接信息确认可达，容器网络里能用服务名/主机名解析到业务库
- [ ] 应用库账号有建表权限（Metabase 启动时会自己建表）
- [ ] 决定密码的注入方式（Docker Secrets / 环境变量），不要写进镜像和仓库
- [ ] 规划端口映射与反向代理、HTTPS，别把 3000 直接裸奔到公网
- [ ] 时区口径想清楚，先把 `JAVA_TIMEZONE` 定下来

执行后：

- [ ] `curl -I http://<host>:3000/api/health` 返回正常
- [ ] 日志里出现初始化完成，浏览器能进 setup 或登录页
- [ ] 建管理员账号、接上业务库，能跑通一个最简单的计数查询
- [ ] 确认应用数据落在预期位置（挂载卷或生产库），并做一次备份演练
- [ ] 配一次订阅或告警，确认真能收到
- [ ] 升级前再确认一次应用库备份是最新的

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/metabase/metabase | 上游仓库（安装与完整文档以它为准） |
| https://www.metabase.com/docs/latest/installation-and-operation/installing-metabase | 官方安装总览：Docker、JAR、Podman、systemd 等各方式 |
| https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker | 官方 Docker 部署说明：compose 示例、Docker 专用变量、Secrets、插件挂载 |

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
