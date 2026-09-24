---
name: sanjianke-doris
slug: sanjianke-doris
displayName: 三剪客 · 实时分析型数据库
description: "MPP 架构的实时分析型数据库：亚秒级查询、秒级写入、MySQL 协议接入，一套系统同时扛高并发点查与复杂分析，并支持湖仓加速与全文/向量混合检索。含 Docker 快速起步、本机集群部署、建表与传统运维坑点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "把实时分析和湖仓查询放进一个 SQL 引擎：Docker 五分钟起集群、本机部署 FE/BE、MySQL 客户端直连、建表分桶与数据导入、集群健康检查，以及单副本、WSL2 网段、系统参数这些必踩的坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析

---

# 三剪客 · 实时分析型数据库

当一个业务既要「写入之后马上能查到」，又要「在很大的数据量上跑聚合」，常规做法会被拆成两套系统：一套事务库扛写入，一套分析库扛查询，中间再拉一条同步链路。Apache Doris 想解决的就是这个拆分的麻烦——**一套 MPP 架构的分析数据库，写入是秒级可见的，查询是亚秒级返回的，对外用 MySQL 协议说话**，你现有的 MySQL 客户端和 BI 工具基本都能直接连。

它的另一个重点是「连得上生态」：对象存储 / 数据湖上的表能直接查，结构化的过滤、全文检索、向量检索可以写进同一条 SQL。所以它常出现在实时看板、日志分析、用户行为分析、以及给 AI 应用当检索底座这几类场景里。

**上游项目**：`doris`　**仓库**：https://github.com/apache/doris

## 什么时候用 / 不用

**用它**：

- 要**对外提供实时看板 / 报表**：数据写入后秒级可见，查询要在亚秒级返回，还得扛住较高并发。
- 要**建一个跨业务域的实时数仓**，把分散在各处的数据收敛到一个查询入口。
- 要做**可观测性分析**：把高吞吐的日志、事件、指标统一用 SQL 查。
- 要在**数据湖之上加速**：Iceberg / Hudi / Delta Lake 这类开放表格式上的查询想在 Doris 里跑，避免先把数据搬进来。
- 要**用一条 SQL 同时做结构化过滤 + 全文检索 + 向量检索**（AI 检索、RAG、语义搜索这类场景）。
- 团队已经在用 MySQL 生态的工具，希望新库能被现有客户端、BI、驱动**直接连上**，降低迁移成本。

**不要用它**：

- **需要强事务的 OLTP 业务**（订单、账务这类高频点写 + 事务一致性要求）。它定位是分析库，不是事务库。
- **数据量很小、只想做个本地小工具**。SQLite 或 DuckDB 这类嵌入式方案起手快得多，装集群是过度设计。
- **只要一张静态报表 / 一次性统计**。跑个脚本或者用轻量分析工具就够了，不需要维护集群。
- **机器资源很紧（内存小、要跑在笔记本上做 POC 之外的用途）**。它的生产形态是多节点集群，FE/BE 都要资源。
- **只想把 Docker 那个五分钟演示当成生产环境**。官方明确说那套只用于本地开发测试；按它上生产会丢数据。

## 安装

**路线一：Docker 快速起步（官方定位是本地体验，不要用于生产）**

```bash
# 一条命令：下载启动脚本并拉起集群
curl -fsSL https://doris.apache.org/files/start-doris.sh | bash

# 指定版本（示例用 -v 传版本号；具体可用版本以官方下载页为准）
curl -fsSL https://doris.apache.org/files/start-doris.sh | bash -s -- -v <版本号>
```

不指定版本时默认拉最新发布版。官方说明：Docker 部署仅用于本地开发与测试，容器销毁后数据会丢。

**路线二：本机完整部署（FE / BE 分开，生产可用）**

环境要求：主流的 AMD / ARM Linux 环境；**JDK 17+**；建一个专用系统用户，不要用 root 跑。

```bash
# 1) 从官方下载页取二进制包，解压到目标目录
#    下载地址：https://doris.apache.org/download

# 2) 系统参数：提高最大文件句柄数
vi /etc/security/limits.conf
#    * soft nofile 1000000
#    * hard nofile 1000000

# 3) 系统参数：提高虚拟内存区域上限
cat >> /etc/sysctl.conf << EOF
vm.max_map_count = 2000000
EOF
sysctl -p

# 4) 配 FE：编辑 apache-doris/fe/conf/fe.conf，指定 JAVA_HOME 与监听网段
#    JAVA_HOME=/home/doris/jdk
#    priority_networks=127.0.0.1/32
apache-doris/fe/bin/start_fe.sh --daemon

# 5) 配 BE：编辑 apache-doris/be/conf/be.conf，priority_networks 要与 FE 同网段
apache-doris/be/bin/start_be.sh --daemon

# 6) 把 BE 注册进集群（在 MySQL 客户端里执行）
#    ALTER SYSTEM ADD BACKEND "127.0.0.1:9050";
```

**路线三：Kubernetes（用 Doris Operator）**

官方文档的「Deploying on Kubernetes」章节给的是 Doris Operator 这条路；具体 CRD、Helm 或 YAML 以该章节当前内容为准。

**路线四：公有云**

官方文档另有 AWS 等公有云的部署章节；按所选云厂商的步骤走。

## 常用操作

**1. 用 MySQL 客户端连上去**

FE 的查询端口是 9030，所以直接用 `mysql` 客户端即可，不需要专门的驱动。

```bash
mysql -uroot -P9030 -h127.0.0.1
```

生产环境请立刻改掉默认的空密码并做访问控制；示例里的 `root` 无密码仅适用于刚起步的本地环境。

**2. 检查集群健康状况**

```bash
# FE 是否已入集群、是否存活
mysql -uroot -P9030 -h127.0.0.1 -e 'SELECT `host`, `join`, `alive` FROM frontends()'

# BE 是否在正常心跳
mysql -uroot -P9030 -h127.0.0.1 -e 'SELECT `host`, `alive` FROM backends()'
```

FE 期望 `Alive` 为真、BE 期望 `Alive` 为 1。也可以直接用 `SHOW FRONTENDS;` / `SHOW BACKENDS;` 看完整信息。

**3. 建库建表**

```sql
create database demo;
use demo;

create table mytable(
    k1 TINYINT,
    k2 DECIMAL(10, 2) DEFAULT "10.05",
    k3 CHAR(10) COMMENT "string column",
    k4 INT NOT NULL DEFAULT "1" COMMENT "int column"
)
COMMENT "my first table"
DISTRIBUTED BY HASH(k1) BUCKETS 1
PROPERTIES ("replication_num" = "1");
```

`BUCKETS` 决定分桶数，`replication_num` 是副本数——上面写的 1 副本只适合本地试验，生产必须多副本。

**4. 写入与查询**

```sql
insert into mytable values
    (1, 0.14, 'a1', 20),
    (2, 1.04, 'b2', 21),
    (3, 3.14, 'c3', 22),
    (4, 4.35, 'd4', 23);

select * from demo.mytable;
```

`insert` 只是验证通路用；真正导入数据走 Stream Load、Broker Load、Routine Load、Flink / Spark / Kafka Connector 这类批量与流式通道，见官方「数据导入」章节。

**5. 只验证 FE 是否起来**

```bash
mysql -uroot -P9030 -h127.0.0.1 -e "show frontends;"
```

期望看到 `Join=true`、`Alive=true`、`IsMaster=true`。

**6. 在流 / 批链路里接入**

Doris 提供 Flink Connector、Spark Connector、Kafka Connector、Stream Loader 等组件；具体依赖坐标与用法以官方「连接与集成」章节为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 按五分钟演示跑通了，直接拿去当生产环境，重启后数据没了 | Docker 那套是**本地开发测试**用的，容器销毁数据即丢 | 生产用本机完整部署或多节点部署；至少把数据目录挂到持久化卷上，但真正的生产形态仍是集群 |
| BE 加进集群后一直显示 Dead | BE 与 FE 的 `priority_networks` 不在同一网段；或者 BE 端口被防火墙挡住 | 确认两边网段一致；放通 BE 的 `9050` / `9060` / `8040` / `8060` 端口 |
| 在 WSL2 里本机部署，BE 死活不进集群 | WSL2 的 loopback 是按发行版隔离命名空间的，FE 和 BE 无法通过 `127.0.0.1` 互相访问，默认的 `127.0.0.1/32` 必然失败 | `ip addr show eth0` 查出真实网段（通常是 `172.16.0.0/12` 或 `172.x.x.x/20`），把 `fe/conf/fe.conf` 与 `be/conf/be.conf` 里的 `priority_networks` 都改成它，重启 FE/BE 后再执行一次 `ALTER SYSTEM ADD BACKEND` |
| 启动或跑查询时报「打开文件过多」 | 系统默认的最大文件句柄数对分析型工作负载不够 | 按官方步骤在 `/etc/security/limits.conf` 提高 `nofile` 软硬上限 |
| BE 启动报虚拟内存区域相关错误 | `vm.max_map_count` 默认值不够 | `vm.max_map_count = 2000000` 写进 `/etc/sysctl.conf` 后 `sysctl -p` |
| 示例建表能跑，一上量就慢或者报副本相关错误 | 示例用的是 1 副本 1 分桶，只为演示通路 | 生产按数据量与并发重新设计分区分桶，并把 `replication_num` 调到多副本 |
| 用 `root` 空密码连上了，就以为不用管账号 | 默认账号是给刚起步用的，生产暴露它就是拿数据冒险 | 建业务账号、设强密码、限制来源网段；不要把 9030 直接开到公网 |
| 部署脚本用 root 跑 FE/BE | 官方要求建专用用户；用 root 会带来权限与安全问题，也可能因权限过宽掩盖配置错误 | 建专用系统用户，目录与进程都归它；`fe.conf` 里的 `JAVA_HOME` 指向该用户可读的 JDK |
| macOS 上 Docker 报找不到 Docker 环境 / 凭证错误 | Docker Desktop 的二进制不在 `PATH`；或 `~/.docker/config.json` 里的 `credsStore` 有问题 | 建软链接把 `docker` 暴露到 `/usr/local/bin`；凭证问题可临时去掉 `credsStore`（官方说明该做法会明文存凭证，仅限本地开发） |
| 想直接查数据湖表却先想着「把数据搬进来」 | 没注意到它有湖仓加速这条能力 | 先看官方 Lakehouse 章节，很多场景可以直接在开放表格式上跑 SQL |
| 把向量检索和结构化过滤分成两次查询 | 没利用它的混合检索能力 | 混合检索可以在一条 SQL 里同时做向量相似度、关键词匹配和结构化过滤，再聚合排序 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 集群内部 FE 与 BE 通信、客户端连 FE 查询端口（9030）与 HTTP 端口、BE 数据传输端口，以及访问对象存储 / 数据湖外部存储 |
| 读取文件 | 是 | 读二进制包、配置文件（`fe.conf` / `be.conf`）、数据目录与日志目录；本地导入时读数据文件 |
| 写入文件 | 是 | 写数据目录、日志与元数据；`start_fe.sh` / `start_be.sh` 以 `--daemon` 方式运行时还会写 PID 文件 |
| 凭证 | 视情况 | 连库需要数据库账号密码；访问对象存储 / 数据湖需要对应存储的 AK/SK 或 IAM 凭证。本 Skill 不内嵌任何密钥，也不代管你的凭证 |
| 子进程 / 后台常驻 | 是 | FE 与 BE 都是以 `--daemon` 常驻的后台进程；容器化部署下由容器托管 |

## 触发场景

- 「要做一个数据写入后马上能看的实时看板」
- 「帮我起一个 Doris 集群，我要跑个 POC」
- 「这个日志量太大，想用 SQL 直接查」
- 「想查 Iceberg 表，但不想先把数据搬进仓库」
- 「要在一个查询里同时做关键词匹配和向量检索」
- 「现有 BI 工具能连 MySQL，想换个更快的分析库」

## 能力边界

**覆盖**：

- 部署形态：Docker 快速体验、本机 FE/BE 完整部署、Kubernetes（Doris Operator）、公有云。
- 架构形态：存算一体（FE + BE 多副本）与存算分离（多计算组 + 共享对象存储，可独立扩缩容、做负载隔离）。
- 接入方式：兼容 MySQL 协议的查询端口、ANSI SQL、各类 BI 与客户端工具。
- 存储侧：列式存储与编码压缩、多种索引（排序复合键、Min/Max、BloomFilter、倒排索引、向量索引）、多种数据模型（Duplicate / Aggregate / Unique，Unique 支持行级更新）、单表强一致物化视图与异步多表物化视图。
- 查询侧：MPP 并行执行、跨节点与节点内并行、大表分布式 Shuffle Join、向量化执行、Runtime Filter、自适应查询执行（AQE）、Pipeline 执行引擎。
- 湖仓：对 Iceberg、Delta Lake、Hudi 等开放表格式的 SQL 分析。
- 混合检索：结构化过滤、全文检索、向量检索在一条 SQL 中组合；`VARIANT` 类型支持动态 JSON，配合轻量 schema 变更。
- 生态连接器：Flink、Spark、Kafka Connector，Stream Loader，Kubernetes Operator。

**不覆盖**：

- 不是 OLTP 事务数据库；不要拿它做订单、账务这类强事务业务的主库。
- 不负责数据采集与 ETL 编排；它提供导入通道与连接器，上游怎么产出数据是另一套系统的事。
- 不做可视化。看板要接 BI 工具或自己写前端。
- 不自带账号体系之外的安全合规能力；权限、脱敏、审计要按官方管理章节自己配。
- 不保证把任意规模、任意 schema 的数据都塞进单机就能跑得好；容量规划与表设计是使用者的责任。
- 部分第三方依赖的许可证与 Apache 2.0 不兼容，官方说明需要**关闭某些功能**才能满足 Apache 2.0 合规；细节在仓库的第三方许可证清单里。

## 依赖条件

- 本机部署：主流 AMD / ARM Linux 环境；**JDK 17+**；专用系统用户（不要 root）。
- 系统参数：提高最大文件句柄数（`nofile`）与虚拟内存区域上限（`vm.max_map_count`）。
- 网络：FE 与 BE 的 `priority_networks` 要在同一网段，相关端口需放通。
- Docker 路线：本机 Docker（macOS 上用 Docker Desktop）。
- Kubernetes 路线：一个可用的 K8s 集群与 Doris Operator。
- 存算分离路线：可用的共享对象存储（S3 / HDFS / OSS 等）及对应访问凭证。
- 客户端工具：任意兼容 MySQL 协议的客户端（示例用 `mysql` 命令行）。

## 已知限制

- Docker 部署仅用于本地开发测试，容器销毁数据即丢；单副本示例没有数据冗余。
- 官方文档站点对「未发布版本」有明确标注，查阅时要选对版本线（文档站提供多条版本线）；照着 unreleased 文档操作可能与你装的版本对不上。
- 集群是多进程系统，FE 与 BE 都有各自的配置文件和端口，排障需要同时看两侧日志。
- 具体性能数字（延迟、QPS、存储规模）以官方「Overview」章节的表述为准；实际表现取决于表设计、分区分桶、硬件与查询形态，不要把它当成承诺值。
- 本文命令来自抓取时的官方快速上手与安装文档；上游迭代中参数与脚本可能调整，执行前请以官方文档当前版本与 `--help` 输出为准。具体版本号、发布日期与 star 数不做断言。

## 自检清单

- [ ] 已确认这次部署是**体验**还是**生产**：体验可以走 Docker，生产必须走本机集群或多节点。
- [ ] 部署用户是专用系统账号，不是 root。
- [ ] 已按要求调整 `nofile` 与 `vm.max_map_count`，并 `sysctl -p` 生效。
- [ ] JDK 版本满足 17+，`fe.conf` 里的 `JAVA_HOME` 指向正确路径。
- [ ] FE 与 BE 的 `priority_networks` 在同一网段（WSL2 环境下尤其要改）。
- [ ] BE 端口（9050 / 9060 / 8040 / 8060）在防火墙/安全组里已放通。
- [ ] `SHOW FRONTENDS;` 与 `SHOW BACKENDS;` 里所有节点的存活列都正常。
- [ ] 建表用的 `replication_num` 与 `BUCKETS` 是按生产需求设计的，不是照抄示例的 1。
- [ ] 默认账号已改密码并限制来源；9030 端口没有直接暴露到公网。
- [ ] 导入走的是正式通道（Stream Load / Broker Load / Routine Load / 连接器），不是大批量 `insert`。
- [ ] 需要查数据湖时，先确认是走湖仓加速还是先入仓，别默认选择搬数据。
- [ ] 涉及许可证合规时，已查阅第三方许可证清单，确认要关闭哪些功能。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/apache/doris | 上游仓库（安装与完整文档以它为准） |

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
