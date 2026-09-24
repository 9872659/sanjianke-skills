---
name: sanjianke-mall4cloud
slug: sanjianke-mall4cloud
displayName: 三剪客 · 微服务电商中台
description: "mall4cloud：微服务电商中台 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "mall4cloud：微服务电商中台 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 运营
---

# 三剪客 · 微服务电商中台

要做的是**多商户商城**——平台方管店铺、商家管自己的商品订单、买家在移动端下单——而不是一个单商户小店，这套代码就是为这个场景写的：Java 微服务后端，网关 + 鉴权 + 权限 + 商品 + 订单 + 支付 + 搜索各自独立成服务，中间件用 Nacos 做注册与配置、Seata 管分布式事务，商品和订单通过 Canal → RocketMQ 同步进 Elasticsearch。

它替用户解决的问题是：**不用从零设计一套 B2B2C 商城的服务拆分和上下游链路**，直接拿现成的服务清单、端口约定、启动顺序去跑通和二次开发。代价是中间件多、启动顺序敏感，本 Skill 的价值就在于把「先起什么、后起什么、错了看哪里」写清楚。

**上游项目**：`mall4cloud`　**仓库**：https://github.com/gz-yami/mall4cloud

## 什么时候用 / 不用

**用它**：

- 要做 **B2B2C 多商户商城**（平台端 + 商家端 + 用户端三端齐备）的技术选型或原型搭建。
- 团队要**评估微服务电商架构**：网关路由、服务注册与配置中心、分布式事务、跨服务 Feign 调用、商品索引同步链路到底怎么落地。
- 本地或单机服务器要**真正跑起来一套商城**：需要中间件 Docker Compose、数据库脚本、最小启动链路和端口清单。
- 已经跑起来但**出问题要排**：登录 401 / 网关 503、菜单和按钮不显示、图片 404、商品发布后搜索不到、RocketMQ 报 `No route info of this topic`。
- 要给三个前端**配接口地址与资源地址**：`VITE_APP_BASE_API` 指网关、`VITE_APP_RESOURCES_URL` 指对象存储。

**不要用它**：

- 只想要**单商户 B2C 商城**：那用单体的 `mall4j` 包就够了，上微服务只会让本地启动变成十几分钟。
- 不是 Java 技术栈，或想要的是 SaaS 多租户、跨境、供应链等**企业版本能力**——本仓库开源版不覆盖这些，别照它承诺功能范围。
- 打算**闭源商用**：开源版是 AGPLv3，闭源分发需要另行取得商业授权，不能直接打包卖。
- 要的是**开箱即用的生产级高可用集群**：仓库里是参考实现，中间件默认口令、示例 IP、无鉴权的 dashboard 都得自己改，生产安全要另做。
- 只是**改改前端样式或看看页面**：不必按这里的中间件清单把一整套服务拉起来。

## 安装

**运行环境（依据仓库根 `pom.xml` 与前端 `package.json`）**

| 组件 | 要求 | 组件 | 要求 |
|---|---|---|---|
| JDK | `17` | MySQL | `8.0.x` |
| Maven | `3.9+` 多模块工程 | Redis | `7.0` |
| Node.js | `^20.19.0 \|\| >=22.12.0` | Nacos | `3.1.1` |
| pnpm | `>=8 <11` | Seata | `2.6.0` |
| 前端框架 | Vue 3.5.x + Vite 8.x | RocketMQ / ES / MinIO / Canal | `5.2.0` / `7.17.21` / `RELEASE.2024-04-18T19-09-19Z` / `1.1.7` |

**1. 拿源码**（两个地址内容一致，哪个通就用哪个）

```bash
git clone https://gitee.com/gz-yami/mall4cloud.git
# 备用：git clone https://github.com/gz-yami/mall4cloud.git
cd mall4cloud
```

**2. 起中间件（Docker Compose，Linux 服务器上执行）**

仓库内已带一份 compose，位于 `doc/8-部署运维/2-中间件-docker-compose/`：

```bash
cd doc/8-部署运维/2-中间件-docker-compose

# 启动前必须给这几个目录权限，否则 RocketMQ / MinIO / ES 起不来
chmod -R 777 ./rocketmq
chmod -R 666 ./minio/data
chmod -R 777 ./elasticsearch/data

# 优先用带国内镜像地址的那份
docker compose -f docker-compose.yaml up -d --build
# Docker Hub 稳定时可用原生镜像版本
# docker compose -f docker-compose-native.yaml up -d --build
```

**3. 改示例 IP**（这一步不做，服务会注册到错误地址）

compose 与初始化 SQL 中保留了示例地址 `192.168.1.46`，启动前统一换成你的服务器 / 本机局域网 IP。重点核对：`docker-compose.yaml`（Nacos、MinIO、Seata、RocketMQ）、`mysql/initdb/mall4cloud_nacos.sql`（配置中心里的 Redis / Seata / OSS / RocketMQ / 各服务数据源地址）、`seata/application.yml`、`canal/conf/example/instance.properties`。不要无脑全仓替换。

**4. 导入业务库**

`db/mall4cloud-all.sql` 会把 `mall4cloud_auth`、`mall4cloud_rbac`、`mall4cloud_product`、`mall4cloud_order` 等库一次性建好；也可以按需只导 `db/` 下的单个库脚本（例如只调商品服务时用 `mall4cloud_product.sql`）。

```bash
mysql -uroot -p < db/mall4cloud-all.sql
```

**5. 起后端与前端**

后端按模块用 Maven 起（各服务模块都配了 `spring-boot-maven-plugin`），前端平台端 / 商家端用 pnpm：

```bash
mvn -pl mall4cloud-gateway -am spring-boot:run
cd front-end/mall4cloud-platform && pnpm install && pnpm dev
```

也可以按各服务 `src/main/resources/bootstrap.yml` 在 IDE 里直接跑启动类，两种方式等价。中间件默认账号密码见 `doc/8-部署运维/2-中间件-docker-compose/README.md`，**只用于本地/示例环境，部署完必须立刻改**。

## 常用操作

**1. 起最小平台端链路（登录 + 权限 + 一个后台就能用）**

先起中间件的 MySQL、Redis、Nacos、MinIO 四个，然后每个服务开一个终端：

```bash
mvn -pl mall4cloud-gateway  -am spring-boot:run   # 8000，前端唯一入口
mvn -pl mall4cloud-auth     -am spring-boot:run   # 9101，登录与 Token 校验
mvn -pl mall4cloud-rbac     -am spring-boot:run   # 9102，菜单与按钮权限
mvn -pl mall4cloud-platform -am spring-boot:run   # 9112，平台端业务
mvn -pl mall4cloud-biz      -am spring-boot:run   # 9000，上传/短信等
```

商家端把第 4 条换成 `mall4cloud-multishop`（`9103`）；要商品管理页面再加 `mall4cloud-product`（`9104`）。端口一律以各服务 `bootstrap.yml` 为准。

**2. 起管理后台前端**

```bash
cd front-end/mall4cloud-platform   # 平台端；商家端是 front-end/mall4cloud-multishop
pnpm install
pnpm dev                           # Vite dev server 默认 9527
```

`.env.development` 里只配三项：

```text
VITE_APP_BASE_API = 'http://<网关IP>:8000'
VITE_APP_RESOURCES_URL = 'http://<MinIO-IP>:9000/mall4cloud'
VITE_APP_RESOURCES_TYPE = '1'
```

**3. 验收网关路由是否打通**

```bash
curl -i http://127.0.0.1:8000/mall4cloud_rbac/menu/route
```

未登录时返回未授权，说明请求已经过网关路由到后端，只是没带 Token——这是**正常**的验收结果。

**4. 看中间件状态与日志**

```bash
docker ps -a
docker logs -f mall4cloud-nacos
```

**5. 建对象存储桶**

进 MinIO 控制台 `http://<IP>:9001` 建桶 `mall4cloud`。`9000` 给业务读写，`9001` 只给运维进控制台。

**6. 建 Elasticsearch 索引**

搜索服务依赖 `product`、`order` 两类索引，mapping 以仓库根目录 `es/product.md`、`es/order.md` 为准，按文档在 ES 中创建索引。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 服务连不上 Nacos / 配置读写报错 | 各服务默认读 `${NACOS_HOST:192.168.1.46}:${NACOS_PORT:8848}`，本机不是这个 IP；且 bootstrap 里默认 `nacos/nacos`，而 compose 初始化 SQL 写的是 `nacos / 80jpnH4.r5g` | 设 `NACOS_HOST`/`NACOS_PORT` 并把两边账号统一；Nacos v3 控制台在 `8080`、客户端走 `8848`，还要放开 `9848`、`9849`，别只放控制台端口；Nacos 配置里的 Redis / Seata / OSS 地址也要同步 |
| 前端登录请求 404 | `VITE_APP_BASE_API` 指到了某个业务端口 | 前端只连网关 `8000`；`auth`、`rbac` 等业务端口是给本机启动和注册 Nacos 用的 |
| 前端请求 503 | 网关能收到请求，但后面的服务没起或没注册成功 | 按最小链路把 `auth`/`rbac`/`platform`（或 `multishop`）`biz` 起齐，再到 Nacos 服务列表确认有实例 |
| `pnpm install` 装不动、被 `only-allow` 拦 | 平台端 / 商家端 `package.json` 有 `preinstall: npx only-allow pnpm` | 必须用 pnpm（版本区间 `>=8 <11`），npm / yarn 会被直接拒绝 |
| 两个后台同时开发时端口冲突 | Vite dev server 默认都是 `9527` | 第二个按 Vite 提示换端口，别去改后端 |
| 图片上传成功但页面 404 | MinIO 桶不存在 / 桶策略不允许读 / `VITE_APP_RESOURCES_URL` 与 Nacos `biz.oss.resources-url` 不一致 | 两处都写成 `http://<MinIO-IP>:9000/mall4cloud`，并确认桶策略允许读取 |
| 商品发布后搜索不到 | 索引更新链路（Canal → RocketMQ → ES → search 服务）某一段断了，商品表写入成功不代表能搜到 | 依次看 `SHOW MASTER STATUS`、`canal/conf/example/instance.properties`、`canal-topic` 是否进 broker、`mall4cloud-search` 是否消费、ES 里 `product`/`order` mapping 是否建好 |
| RocketMQ 报 `No route info of this topic` | broker 没读到挂载的 `broker.conf`，或 `rocketmq/` 目录权限不足 | 先按文档 `chmod -R 777 ./rocketmq`，再重建 broker / dashboard / namesrv |
| 服务注册到错误 IP | compose 和初始化 SQL 里的示例 IP `192.168.1.46` 没换 | 逐处核对 bootstrap、Nacos 配置、compose、Canal、Seata、RocketMQ、前端 `.env.*`，别全仓盲替换 |
| Seata 连接失败 | 该 compose 的 Seata 只暴露 `8091`，本仓库没有启用控制台端口 | 核对 `seata/application.yml` 的数据库地址与 `application.yml` 中 `seata.service.grouplist.default`；不要自己往配置里加未经验证的 console 项 |
| 本地全量启动后机器卡死 | 十几个微服务同时在 IDE 里跑，内存吃紧 | 只起最小链路，单服务加 `-Xms512m -Xmx512m -Xss256k` 之类的启动参数 |
| 环境变量写了但不生效 | 后台当前只读 `VITE_APP_*` | 别再用 `VUE_APP_*` 命名，改了记得重启 dev server |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取依赖与镜像、访问 Nacos / MinIO / ES 等中间件、验收网关接口 |
| 读取文件 | 是 | 读取仓库配置（`pom.xml`、`bootstrap.yml`、`.env.*`、`db/*.sql`）以核对地址与端口 |
| 写入文件 | 是 | 修改示例 IP、环境变量与本地配置；导入数据库脚本 |
| 凭证 | 是 | 需要 MySQL / Redis / Nacos / MinIO 的账号口令；仓库内为示例默认值，必须替换为你自己的 |
| 子进程 / 后台常驻 | 是 | `docker compose`、`mvn spring-boot:run`、`pnpm dev` 都是长驻进程，需要能启停与看日志 |

## 触发场景

- 「帮我搭一套能入驻商家的多商户商城，要平台端和商家端」
- 「这套微服务商城本地怎么起？先起哪个服务？」
- 「前端登录报 404 / 网关报 503，怎么查？」
- 「商品发布了但搜索里搜不到，是哪里断了？」
- 「商城图片上传成功但显示 404」
- 「我想看看 Java 微服务做电商是怎么拆服务的」

## 能力边界

**覆盖**：

- 开源版微服务商城的**启动全链路**：中间件 compose、示例 IP 替换、数据库初始化、最小 / 完整服务链路的启动顺序与端口。
- **三端前端的接口与资源地址配置**，以及登录、菜单、按钮权限这条链路的排查方向。
- **典型故障的现象→原因→动作**：Nacos 注册、网关 404/503、图片 404、索引不同步、RocketMQ topic 路由、Seata 配置。
- 基于仓库内文档与配置文件的**二次开发入口指引**（模块划分、`api` 模块下的内部 Feign 接口约定）。

**不覆盖**：

- 不开源的企业版本能力：SaaS 多租户、跨境、供应链、B2B2B 等，也不替使用者做商业授权判断。
- 不提供生产级方案：高可用集群、容器编排、灰度发布、安全加固只给注意事项，不给成品编排文件。
- 不代写业务代码：具体商品 / 订单 / 支付业务逻辑的二次开发，只指路到对应服务，不产出实现。
- 不覆盖第三方中间件的通用运维（Docker / MySQL / Nacos / RocketMQ 自身安装与调优按各自官方文档）。

## 依赖条件

- **JDK 17 + Maven 3.9+**（根 `pom.xml` 中 `java.version` 为 `17`）；Node.js `^20.19.0 || >=22.12.0` + pnpm `>=8 <11`。
- **MySQL 8 与 Redis 7 必装**；Nacos 必须可用（注册与配置都靠它）；不做上传 / 图片展示可暂不起 MinIO。
- 需要验证搜索或索引同步时，再起 **Elasticsearch、RocketMQ、Canal**；Seata 只在跨服务的分布式事务场景下必需。
- 需要**可用的服务器或本机 IP**（不能是 `192.168.1.46` 这类示例地址），Linux 上的 compose 还需要 Docker 与 Docker Compose。
- 前端**只能连网关端口**，所以 `auth`、`rbac` 等业务服务必须能注册到同一个 Nacos。

## 已知限制

1. 仓库内 compose 与初始化 SQL 保留示例 IP 和**示例口令**，直接用于生产等于把中间件裸奔，必须替换并加访问控制；RocketMQ dashboard 默认没有登录保护。
2. 本地开发依赖 IDE / Maven 逐个起服务，**没有一键全量启动脚本**；机器内存不足时只能起最小链路。
3. 端口分散在多个 `bootstrap.yml` 与 Nacos 配置中，**改端口要成套改**（服务、网关路由、前端 `VITE_APP_BASE_API`），漏一处就是 404 或 503。
4. 文档只覆盖开源版现有功能点；企业版本与商业授权相关内容以官方渠道为准。
5. 不同版本迭代较快，`pom.xml` / `package.json` 里的依赖版本随时可能变动，遇到冲突以仓库当前配置为准。

## 自检清单

执行前：

- [ ] 确认是**多商户 B2B2C** 场景；单商户 B2C 请改用 `mall4j` 包。
- [ ] 确认 `java -version` 是 17，`mvn -v` 可用，`pnpm -v` 在 `>=8 <11`。
- [ ] 确认已把示例 IP 逐处替换，而不是只改了一两个文件。
- [ ] 明确本次只跑最小链路还是完整链路，不要一上来全量启动。

执行后：

- [ ] `docker ps` 能看到 MySQL、Redis、Nacos 等容器在运行，没有反复重启。
- [ ] Nacos 控制台能登录，配置列表里有 `application.yml`、`mall4cloud-gateway.yml`，服务列表里有已启动的服务。
- [ ] MySQL 中存在 `mall4cloud_auth`、`mall4cloud_rbac` 等库，账号数据已导入。
- [ ] `curl -i http://127.0.0.1:8000/mall4cloud_rbac/menu/route` 返回未授权（说明路由通了）。
- [ ] 平台端 / 商家端能打开页面并登录，登录后左侧菜单正常。
- [ ] 若配置了上传，MinIO 桶 `mall4cloud` 存在且图片能正常显示。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/gz-yami/mall4cloud | 上游仓库（安装与完整文档以它为准） |
| `doc/8-部署运维/2-中间件-docker-compose/README.md` | 中间件 compose 的端口、默认账号、权限与验收清单 |

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
