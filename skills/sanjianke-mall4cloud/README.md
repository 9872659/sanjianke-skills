# 三剪客 · 微服务电商中台 Skill

mall4cloud：微服务电商中台 的安装、常用命令与避坑要点

---

## 前置条件

- **JDK 17**：根 `pom.xml` 里 `java.version` 为 `17`，JDK 8 / 11 编不过。
- **Maven 3.9+**：多模块工程，需要能解析根 `pom.xml` 的模块列表。
- **Node.js `^20.19.0 || >=22.12.0` 与 pnpm `>=8 <11`**：两个管理后台是 Vite 工程，`package.json` 带 `only-allow pnpm`，用 npm / yarn 会被拦。
- **MySQL 8 与 Redis 7 必须可用**，Nacos 必须可用（服务注册与配置都走它）；要验证上传需 MinIO，要验证搜索需 Elasticsearch + RocketMQ + Canal。
- **一个真实可用的 IP**：compose 与初始化 SQL 里是示例地址 `192.168.1.46`，必须换成你的服务器或本机局域网地址。
- Linux 上跑中间件 compose 需要 **Docker 与 Docker Compose**；本地开发一般是「服务器起中间件 + 本地起业务服务」。

---

## 使用

最短跑通路径（管理后台能登录即算通）：

1. `git clone https://gitee.com/gz-yami/mall4cloud.git`（GitHub 同名仓库内容一致）。
2. 进 `doc/8-部署运维/2-中间件-docker-compose/`，先给 `rocketmq`、`minio/data`、`elasticsearch/data` 目录权限，再 `docker compose -f docker-compose.yaml up -d --build`。
3. 把 compose、`mysql/initdb/mall4cloud_nacos.sql`、`seata/application.yml`、canal 配置里的示例 IP 换成自己的。
4. `mysql -uroot -p < db/mall4cloud-all.sql` 导入业务库（它会一次性建好各业务库）。
5. 按最小链路起后端：`gateway` → `auth` → `rbac` → `platform`（或 `multishop`）→ `biz`，逐个 `mvn -pl <模块> -am spring-boot:run`。
6. `cd front-end/mall4cloud-platform && pnpm install && pnpm dev`，`.env.development` 里 `VITE_APP_BASE_API` 指向网关 `8000`。
7. 用初始化账号登录平台端或商家端（默认 `admin / 123456`，仅示例环境有效）。

验收：`curl -i http://127.0.0.1:8000/mall4cloud_rbac/menu/route` 返回未授权，说明网关路由已通；后台能登录并看到左侧菜单。

---

## 依赖

| 类别 | 依赖 | 说明 |
|---|---|---|
| 运行时 | JDK 17、Maven 3.9+ | 后端构建与启动 |
| 前端 | Node.js `^20.19.0 \|\| >=22.12.0`、pnpm `>=8 <11`、Vue 3.5.x、Vite 8.x | 平台端 / 商家端 / uni-app 用户端 |
| 框架 | Spring Boot `4.0.3`、Spring Cloud `2025.1.1`、Spring Cloud Alibaba `2025.1.0.0` | 依据根 `pom.xml` |
| 中间件（必装） | MySQL `8.0.x`、Redis `7.0`、Nacos `3.1.1` | 数据库、缓存、注册与配置中心 |
| 中间件（按需） | Seata `2.6.0`、RocketMQ `5.2.0`、Elasticsearch `7.17.21`、MinIO `RELEASE.2024-04-18T19-09-19Z`、Canal `1.1.7` | 分布式事务、消息、搜索、对象存储、索引同步 |
| 数据库脚本 | `db/mall4cloud-all.sql` 或 `db/` 下单库脚本 | 建库、建表、初始账号与权限数据 |
| 前端目录 | `front-end/mall4cloud-platform`、`front-end/mall4cloud-multishop`、`front-end/mall4cloud-uniapp` | 平台端、商家端、用户端 |
| 授权 | AGPLv3（开源版） | 闭源商用需另行取得商业授权 |

依赖版本随仓库迭代变动，以根 `pom.xml` 与各前端 `package.json` 的当前值为准。

---

## 安全

- 不内嵌任何密钥：本包只描述安装与排错步骤，不含真实账号、口令或 Token。
- 仓库自带的 compose 与初始化 SQL 使用**示例 IP 与示例口令**，仅供本地 / 内网示例环境；对外部署前必须全部替换，并限制中间件只在内网可达。
- RocketMQ dashboard 默认没有登录保护，**不要暴露到公网**；Nacos、MySQL、Redis、MinIO、Elasticsearch 同理。
- 初始化账号 `admin / 123456` 只用于第一次登录，部署后立即改密并清理演示数据。
- 生产环境按文档核对：数据源、Redis、OSS、RocketMQ、Seata 与网关路由都要改成真实地址，只改前端 `.env.production` 不够。
- 开源版为 AGPLv3，闭源分发与商业交付需先确认授权范围。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`mall4cloud`
- 仓库：https://github.com/gz-yami/mall4cloud

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
