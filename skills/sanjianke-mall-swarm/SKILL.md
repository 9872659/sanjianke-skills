---
name: sanjianke-mall-swarm
slug: sanjianke-mall-swarm
displayName: 三剪客 · 微服务电商商城系统
description: "mall-swarm：微服务电商商城系统 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "mall-swarm：微服务电商商城系统 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 运营
---

# 三剪客 · 微服务电商商城系统

`mall-swarm` 是一套完整的分布式电商后端：注册中心、配置中心、网关、认证中心、监控中心、后台服务、前台服务、搜索服务都已经拆好放在那里，商品、订单、营销、会员这些业务模块也一并实现。它替你解决的问题是"从单体走向微服务时，那些跟业务无关但必须有的基础设施我先给你搭起来"——你拿到的是一条能跑通的微服务电商链路，而不是一份架构图。

**上游项目**：`mall-swarm`　**仓库**：https://github.com/macrozheng/mall-swarm

## 什么时候用 / 不用

**用它**：

- 你要学或要演示 Spring Cloud Alibaba 这套微服务组合怎么落地：注册发现、配置中心、网关路由、统一认证各自在哪一层、怎么串起来。
- 你要一个能跑起来的电商后端基座，打算在上面长出自己行业的业务模块，不想从零写商品 SKU、订单履约、权限模型。
- 你的团队要评估"这套微服务拆分粒度是否适合我们"，需要一个真实可部署的参照系统来压测和评审。
- 你要做的是部署与运维工作：用 Docker Compose 起一整套依赖组件与应用，排查服务注册不上、配置拉不到、网关路由不通这类问题。
- 你需要一套现成的后台管理 + 前台商城的服务端接口，配合前端的运营后台和商城前端使用。

**不要用它**：

- 你要的是单体应用。它有注册中心、配置中心、网关、六个以上的服务进程和一套中间件，单机小项目上这套运维负担远大于收益。
- 你的服务器资源有限。它默认的组件清单（数据库、缓存、消息队列、搜索引擎、日志链路、对象存储）堆起来对内存和磁盘有硬要求，不是一台低配机器能舒服跑的。
- 你不想碰 Docker。官方给出的最短路径依赖容器化部署，纯手工装齐这些组件是另一项工程。
- 你只想要一个前端页面或一个静态站点——那是前端工程的活，跟这套后端无关。
- 你期待"下载即上线"。它的默认配置面向演示与学习，公网投产所需的密钥管理、限流、审计、备份都得自己补。
- 你的技术栈不是 Java 生态，且不打算引入 JVM 运行时。

## 安装

官方给出的部署方式基于 Docker 容器 + Docker Compose，文档以 CentOS 7.6 为例，运行配置推荐 **6G 以上内存**。

**1. 先起依赖的系统组件**

项目已提供现成的 Compose 脚本，直接执行即可：

```bash
# 脚本地址：https://github.com/macrozheng/mall-swarm/blob/master/document/docker/docker-compose-env.yml
docker-compose -f docker-compose-env.yml up -d
```

官方文档列出的组件与版本：

| 组件 | 版本 |
|---|---|
| Mysql | 5.7 |
| Redis | 7.0 |
| MongoDb | 4.x |
| RabbitMq | 3.9 |
| Nginx | 1.22 |
| Elasticsearch | 7.17.3 |
| Logstash | 7.17.3 |
| Kibana | 7.17.3 |
| Nacos | 2.1.0 |

这些组件在 Compose 脚本里对外暴露的端口：MySQL 3306、Redis 6379、Nginx 80、RabbitMQ 5672 与管理端 15672、Elasticsearch 9200/9300、Logstash 4560–4563、Kibana 5601、MongoDB 27017、Nacos 8848。

**2. 准备 Logstash**

新增了 Logstash 组件，需要预先建好配置文件目录，再进容器安装 JSON 插件：

```bash
# 创建好配置文件目录
mkdir /mydata/logstash

# 进入容器使用如下命令安装插件
logstash-plugin install logstash-codec-json_lines
```

配置文件地址：https://github.com/macrozheng/mall-swarm/tree/master/document/elk/logstash.conf

**3. 打包应用镜像**

一共 6 个应用服务需要打包成 Docker 镜像。如果打包过程中遇到找不到 `mall-common` 或 `mall-mbg` 模块，需要先按顺序把这些模块 install 到本地 Maven 仓库再进行打包。

| 应用 | 说明 |
|---|---|
| mall-monitor | 监控中心 |
| mall-gateway | 微服务网关 |
| mall-auth | 认证中心 |
| mall-admin | 商城后台服务 |
| mall-portal | 商城前台服务 |
| mall-search | 商城搜索服务 |

各应用在 Compose 脚本里的端口分别是：网关 8201、后台服务 8080、搜索服务 8081、前台服务 8085、认证中心 8401、监控中心 8101。

**4. 把配置导入 Nacos**

使用 Nacos 作为配置中心统一管理配置，需要把项目 `config` 目录下的所有配置添加到 Nacos 中。**配置文件的文件名称必须和 Nacos 中的 `Data Id` 一一对应。**

Nacos 控制台默认访问地址形如 `http://<你的服务器IP>:8848/nacos/`。

**5. 启动所有应用**

```bash
# 脚本地址：https://github.com/macrozheng/mall-swarm/blob/master/document/docker/docker-compose-app.yml
docker-compose -f docker-compose-app.yml up -d
```

启动成功后可以查看 API 文档，地址形如 `http://<你的服务器IP>:8201/doc.html`。

**6. 用前端连过来时，接口要走网关**

配好之后可以用前端的运营后台登录验收。默认管理账号为 `admin`，口令为 `macro123`（认证中心的 client_id 为 `admin-app`）。这些是项目自带的演示凭证，只在本地验证时用。

注意：微服务版的接口必须走网关，前端环境变量里的后端地址要写成网关地址加服务前缀，而不是直接指向某个业务服务的端口。

## 常用操作

**1. 起停整套依赖组件**

```bash
# 启动
docker-compose -f docker-compose-env.yml up -d

# 查看状态
docker-compose -f docker-compose-env.yml ps

# 停止并移除容器
docker-compose -f docker-compose-env.yml down
```

**2. 起停整套应用服务**

```bash
docker-compose -f docker-compose-app.yml up -d
docker-compose -f docker-compose-app.yml ps
docker-compose -f docker-compose-app.yml logs -f mall-gateway
```

**3. 看服务有没有注册上、配置有没有拉到**

打开 Nacos 控制台（`http://<服务器IP>:8848/nacos/`），在服务列表里核对各服务是否在线；配置列表里核对 `Data Id` 是否与项目 `config` 目录下的文件名一致。

**4. 看监控与日志**

- 监控中心：`http://<服务器IP>:8101`
- 日志收集（Kibana）：`http://<服务器IP>:5601`

**5. 用 Portainer 图形化管理容器**

```bash
docker pull portainer/portainer

docker run -p 9000:9000 -p 8000:8000 --name portainer \
--restart=always \
-v /var/run/docker.sock:/var/run/docker.sock \
-v /mydata/portainer/data:/data \
-d portainer/portainer
```

访问 `http://<服务器IP>:9000` 即可看到运行中的容器、镜像，以及单个应用的资源占用和日志。

**6. Elasticsearch 启动前的系统参数**

```bash
# 改变设置
sysctl -w vm.max_map_count=262144
# 使之立即生效
sysctl -p
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| Elasticsearch 容器反复重启或直接起不来 | 系统内核参数 `vm.max_map_count` 太小，或数据目录没有权限 | 执行 `sysctl -w vm.max_map_count=262144` 并 `sysctl -p`；创建 `/mydata/elasticsearch/data` 后 `chmod 777` 该目录 |
| Nginx / Logstash 挂载启动失败 | 挂载点对应的宿主机目录或配置文件不存在，挂载时找不到源 | 先把目录和配置建好：`/mydata/nginx/` 放 `nginx.conf`，`/mydata/logstash` 放 `logstash.conf`，再 `up -d` |
| 日志收集里看不到结构化日志 | 容器内没装 JSON 编解码插件 | 进 Logstash 容器执行 `logstash-plugin install logstash-codec-json_lines` |
| Logstash 连不上搜索引擎 | 配置文件里 `output` 的 Elasticsearch 地址没改成容器网络内的服务名 | 在 Compose 同一网络下把地址写成服务名加端口（例如 `es:9200`），而不是宿主机 IP |
| 应用容器起来了但一直注册不上 | 依赖组件还没就绪，应用先启动了 | 先确认 `docker-compose-env.yml` 起的组件全部健康，再起 `docker-compose-app.yml`；必要时看应用日志里的连接拒绝信息 |
| 服务启动了却读不到配置 | 配置没导入 Nacos，或 `Data Id` 与配置文件名不一致 | 把项目 `config` 目录下的配置逐条导入 Nacos，`Data Id` 严格对齐文件名 |
| Maven 打包报找不到 `mall-common` / `mall-mbg` | 公共模块没先进本地仓库，直接打应用模块 | 先按依赖顺序把这些模块 `install` 到本地 Maven 仓库，再打应用镜像 |
| 换了服务器 IP 之后前端全连不上 | 配置里的地址还是旧 IP，或服务注册的地址与实际不通 | 同步改 Nacos 里的相关配置并重启受影响的服务，确认注册到 Nacos 的 IP 能从调用方访问到 |
| 前端能打开但登录请求 404 | 微服务版的接口必须走网关，前端却被指到了某个业务服务的端口 | 把前端的后端地址改成网关地址加对应服务前缀（运营后台走 `mall-admin`，商城前台走 `mall-portal`） |
| 新版 Nacos 起不来 | Nacos 自身要求先补齐鉴权相关的配置项（身份标识、令牌密钥等），且新版的控制台端口与旧版不同 | 按该版本 Nacos 官方要求修改其配置文件后再启动，控制台地址以实际端口为准 |
| 端口冲突导致容器起不来 | 宿主机上已有进程占用同一端口 | 用 `docker-compose ps` 与 `ss -lntp` 对照找出占用者，改 Compose 里的端口映射或停掉冲突进程 |
| 磁盘很快写满 | 镜像、日志与数据库数据都堆在宿主机上，日志链路尤其吃空间 | 提前规划挂载盘与日志轮转，定期清理无用镜像与旧索引 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取 Docker 镜像、拉取 Maven 依赖、访问 Nacos 与各服务控制台 |
| 读取文件 | 是 | 读取项目的 Compose 脚本、`config` 配置目录、Nacos 与 Logstash 等配置文件 |
| 写入文件 | 是 | 生成构建产物与镜像、创建宿主机挂载目录、写入配置文件与日志 |
| 凭证 | 是 | 数据库、RabbitMQ、Nacos、对象存储等组件的账号密码；这些必须由你自建并保管，不要沿用示例值 |
| 子进程 / 后台常驻 | 是 | 执行 `mvn`、`docker`、`docker-compose` 等命令，容器与各微服务进程长期常驻 |

## 触发场景

- 「帮我部署一套微服务电商系统」
- 「mall-swarm 怎么用 Docker 跑起来」
- 「Nacos 配置怎么导入 / 服务注册不上怎么办」
- 「我要一个 Spring Cloud 电商项目的完整骨架」
- 「微服务拆分的注册中心、网关、认证中心怎么配」
- 「Elasticsearch / Logstash 容器起不来」

## 能力边界

**覆盖**：

- 官方文档给出的容器化部署路径：依赖组件与应用服务两段 Compose 脚本、组件版本清单、六类应用服务的职责划分。
- 配置中心接入方式（配置文件与 `Data Id` 一一对应）以及主要控制台入口。
- 部署阶段高频故障的定位顺序：内核参数、挂载目录、插件、启动顺序、配置一致性、打包依赖顺序。
- 基于该项目做二次开发时，微服务分层与模块依赖的基本认知。

**不覆盖**：

- 具体业务代码的实现细节与接口字段定义——以仓库当前代码与其接口文档为准。
- 生产级加固：密钥托管、限流熔断策略、审计、备份恢复、高可用拓扑，这些都需要你另行设计。
- Kubernetes 集群编排、CI/CD 流水线、监控告警体系的建设。
- 前端工程的搭建与配置（运营后台、商城前端各有独立工程）。
- 任何性能与容量的承诺。

## 依赖条件

- 一台 Linux 服务器（官方文档以 CentOS 7.6 为例），推荐 **6G 以上内存**。
- Docker 与 Docker Compose。
- JDK 与 Maven（用于构建应用镜像）。
- 能够拉取镜像与依赖的网络出口。
- 可用的服务器 IP / 域名，供服务注册与控制台访问使用。
- 不需要第三方大模型或算力服务。

## 已知限制

- 默认组件版本（数据库、搜索引擎、消息队列等）是官方文档给出的组合，替换版本时必须自行验证兼容性。
- 默认配置面向演示与学习环境，账号口令等示例值必须替换后才能对外提供服务。
- 服务数量与中间件数量决定了资源开销，单机部署只适合验证与演示。
- 配置分散在 Nacos 中，配置与代码的同步（尤其换环境时）需要人工维护，容易漏项。
- 上游文档以特定系统版本为例，其他发行版上的目录权限、内核参数、防火墙行为可能不同。

## 自检清单

执行前：

- [ ] 服务器内存是否达到推荐值，磁盘是否留够镜像与日志空间。
- [ ] Docker 与 Docker Compose 是否可用（`docker -v`、`docker-compose -v`）。
- [ ] JDK 与 Maven 是否可用，本地 Maven 仓库是否能写入。
- [ ] 依赖组件的宿主机挂载目录（`/mydata/...`）与配置文件是否已提前创建。
- [ ] 内核参数 `vm.max_map_count` 是否已调整，Elasticsearch 数据目录权限是否正确。

执行后：

- [ ] `docker-compose -f docker-compose-env.yml ps` 中所有组件是否健康。
- [ ] `docker-compose -f docker-compose-app.yml ps` 中六个应用是否都在运行。
- [ ] Nacos 服务列表里各服务是否已注册且为健康状态。
- [ ] Nacos 配置列表的 `Data Id` 是否与项目 `config` 目录下的文件名一一对应。
- [ ] API 文档地址（形如 `http://<服务器IP>:8201/doc.html`）能否打开。
- [ ] 监控中心与 Kibana 能否访问，日志是否正常落入索引。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/macrozheng/mall-swarm | 上游仓库（安装与完整文档以它为准） |
| https://github.com/macrozheng/mall-swarm/blob/master/document/docker/docker-compose-env.yml | 依赖组件的 Compose 脚本 |
| https://github.com/macrozheng/mall-swarm/blob/master/document/docker/docker-compose-app.yml | 应用服务的 Compose 脚本 |

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
