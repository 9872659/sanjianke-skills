---
name: sanjianke-mall4j
slug: sanjianke-mall4j
displayName: 三剪客 · Java 商城系统
description: "mall4j：Java 商城系统 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "mall4j：Java 商城系统 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 运营
---

# 三剪客 · Java 商城系统

要开一个**自己家的商城**——一个后台管商品、订单、会员、运费模板、规格和权限，买家在小程序 / H5 / uni-app 下单——这套代码就是为单商户 B2C 场景写的：Java 后端只有两个 Spring Boot 服务（管理端接口 + 用户端接口），加一个 Vue 3 管理后台，中间件只要 MySQL 和 Redis。

它替用户解决的问题是：**不用从零写一遍商城后台和下单主链路**，拿现成的商品 SKU、购物车、下单、支付、菜单权限实现，跑起来、改页面、加字段。代价是它**不是**多商户、不是微服务，选错场景会白折腾——本 Skill 最重要的一块就是帮你判断该不该用它。

**上游项目**：`mall4j`　**仓库**：https://github.com/gz-yami/mall4j

## 什么时候用 / 不用

**用它**：

- 要做**单商户 B2C 商城**：一个管理后台 + 一个用户端接口就能覆盖，本地半天能跑通。
- 要在现成商城上**做后台管理二次开发**：加一个菜单、一个页面、一个新表，按仓库里的命名约定照抄一套即可。
- 需要**商品 SKU / 购物车 / 下单 / 支付**这条主链路的参考实现，或者要读它的表设计。
- 要在同一套后端上**接小程序、H5、uni-app 前端**，需要知道各端该连哪个端口、哪个配置文件。
- 后台已经跑起来但**出问题要排**：登录失败、验证码异常、401、菜单或按钮不显示、图片 404、跨域。

**不要用它**：

- 要**多商户入驻**（平台方 + 多个商家，B2B2C）、SaaS 多租户或跨境——开源版是单商户，这类需求改用 `mall4cloud` 包或按官方说明确认企业版本。
- 要**微服务架构**：它的后端是单体多模块，商品和订单不能独立部署扩容；要拆服务就别从它开始。
- 打算**闭源商用**：开源版是 AGPLv3，闭源分发需要另行取得商业授权。
- 想要**一条 `docker compose up` 起全套**：仓库根目录那份 compose 依赖的文件并不在仓库里，直接跑会失败。
- 不是 Java 技术栈，或者只是想要一个纯前端商城模板。

## 安装

**运行环境（依据根 `pom.xml` 与 `front-end/mall4v/package.json`）**

| 组件 | 要求 | 组件 | 要求 |
|---|---|---|---|
| JDK | `17` | MySQL | `5.7+`，库名 `yami_shops` |
| Maven | 能构建多模块工程 | Redis | `4.0+`，默认端口 `6379` |
| Node.js | `^20.19.0` 或 `>=22.12.0` | pnpm | `>=7` |
| 后端框架 | Spring Boot `4.0.3`、MyBatis-Plus `3.5.16`、Sa-Token `1.44.0` | 其他 | Redisson `4.3.0`、Knife4j `4.5.0`、XXL-JOB `2.4.2`（可选） |

**1. 拿源码**

```bash
git clone https://gitee.com/gz-yami/mall4j.git
# 备用：git clone https://github.com/gz-yami/mall4j.git
cd mall4j
```

**2. 初始化数据库**

```bash
mysql -uroot -p
```

进入 MySQL 后：

```sql
CREATE DATABASE IF NOT EXISTS yami_shops DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE yami_shops;
SOURCE D:/workspace/mall4j/db/yami_shop.sql;
```

`SOURCE` 后面的路径换成你本地的实际路径。导完应该有 `tz_sys_user`、`tz_sys_menu` 等表，并带初始化管理员 `admin / 123456`（仅示例环境）。

**3. 起 MySQL 与 Redis**（本地默认 `3306` / `6379`），核对 `yami-shop-admin` 与 `yami-shop-api` 各一份 `src/main/resources/application-dev.yml` 里的数据库地址、账号、密码。

**4. 起后端**（仓库根目录，各开一个终端）

```bash
mvn -pl yami-shop-admin -am spring-boot:run   # 管理端接口，8085
mvn -pl yami-shop-api   -am spring-boot:run   # 用户端接口，8086
```

只调管理后台时先起 `yami-shop-admin` 就够；也可以用 IDEA 导入 Maven 项目后直接跑 `WebApplication` / `ApiApplication`。

**5. 起管理后台前端**

```bash
cd front-end/mall4v
pnpm i
pnpm run dev        # Vite dev server，默认 9527
```

**6. 打包部署（可选）**

```bash
mvn clean package -DskipTests
# jar 生成在 yami-shop-admin/target/yami-shop-admin-0.0.1-SNAPSHOT.jar
#            yami-shop-api/target/yami-shop-api-0.0.1-SNAPSHOT.jar
cd front-end/mall4v && pnpm i && pnpm run build
```

仓库根目录的 `docker-compose.yml` 引用了 `db/Dockerfile`，而仓库里没有这个文件，`docker compose up -d` 会直接失败；要用容器部署请按仓库 `doc/8-部署运维/` 下的部署文档自己准备镜像，或只用官方 MySQL / Redis 镜像把中间件跑起来、业务服务仍用 jar 部署。

## 常用操作

**1. 验收管理端后端是否起来**

```bash
curl -I http://127.0.0.1:8085/doc.html
```

能打开管理端接口文档，说明管理端服务、数据库连接都正常。

**2. 导入与核对数据库**

```bash
mysql -uroot -p -e "use yami_shops; show tables like 'tz_sys_%';"
```

登录和菜单权限至少依赖 `tz_sys_user`、`tz_sys_role`、`tz_sys_menu`、`tz_sys_role_menu` 四张表。

**3. 起管理后台并核对接口地址**

```bash
cd front-end/mall4v
pnpm run dev
# 另开终端确认 .env.development 指向管理端接口
grep VITE_APP_BASE_API .env.development
```

期望值是 `http://127.0.0.1:8085`；指到 `8086` 就会出现验证码、登录、401 各种怪问题。

**4. 给小程序 / uni-app 配接口地址**

```text
front-end/mall4m/utils/config.js        小程序，应指向 http://127.0.0.1:8086
front-end/mall4uni/.env.development     uni-app，应指向 http://127.0.0.1:8086
```

**5. 打包两个后端服务**

```bash
mvn clean package -DskipTests
ls yami-shop-admin/target/*.jar yami-shop-api/target/*.jar
```

上线时注意 `prod` profile 的端口与管理端 / 用户端配置，不要照搬本地的 `8085` / `8086`。

**6. 排查权限问题直接查表**

```sql
-- 看菜单 / 按钮权限是否配了
SELECT menu_id, parent_id, name, url, type, perms FROM tz_sys_menu WHERE perms <> '' OR type = 1;
-- 看某个角色有没有分配
SELECT * FROM tz_sys_role_menu WHERE role_id = <角色ID>;
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 管理后台登录失败、验证码接口报错、401 | 管理后台连到了用户端接口 `8086` | `front-end/mall4v/.env.development` 的 `VITE_APP_BASE_API` 必须是 `http://127.0.0.1:8085` |
| 用户端 / 小程序接口全部异常 | 小程序或 uni-app 连到了管理端 `8085` | 小程序与 uni-app 必须连 `8086`，改 `mall4m/utils/config.js` 或 `mall4uni/.env.development` |
| `docker compose up -d` 直接失败 | 根目录 `docker-compose.yml` 引用了 `db/Dockerfile`，仓库里没有该文件 | 不要指望一键起全套；按 `doc/8-部署运维/` 的部署文档准备镜像，或只用官方 MySQL / Redis 镜像 |
| 后端启动失败 | JDK 不是 17 / MySQL 没起 / Redis 没起 / `application-dev.yml` 账号密码不对 / 没导入 `db/yami_shop.sql` / 端口被占 | 按 `java -version` → MySQL → Redis → 配置文件 → 导库 → 端口占用顺序逐个排除 |
| 登录成功但左侧菜单不显示 | 菜单没建、`url` 与页面路径对不上，或当前角色没分配该菜单 | 菜单要建 `type=1` 的记录，`url` 与 `front-end/mall4v/src/views/modules/...` 下的页面路径对应，并给角色分配 |
| 页面能进、按钮不显示但接口能调 | 按钮权限只在菜单表里配了，角色没拿到，或前端权限标识与后端不一致 | 查 `tz_sys_menu` 的按钮权限与 `tz_sys_role_menu` 分配；前端 `isAuth('xxx')` 要和后端 `@PreAuthorize("@pms.hasPermission('xxx')")` 用同一个标识 |
| 图片上传成功但页面 404 | 资源地址配错，或还在用旧变量名 | 管理后台用 `VITE_APP_RESOURCES_URL`（`VUE_APP_RESOURCES_URL` 是历史命名，当前不生效），指向真实可访问的静态资源地址 |
| 浏览器报跨域 / `OPTIONS` 请求失败 | 前端接口地址与后端端口不一致，或生产没做反向代理 | 本地先对齐端口；生产用 Nginx 同域反代；若用 `/apis` 这类相对路径，nginx 的 rewrite 和 `proxy_pass` 要同时配 |
| 生产环境按本地端口连不上 | 不同 profile 端口不同，`prod` 配置不是 `8085` / `8086` | 以实际启用的 profile 配置为准，前端接口地址同步改 |
| `pnpm i` / 启动前端报版本错误 | Node 或 pnpm 版本不满足 `package.json` 的 `engines` | Node 用 `^20.19.0` 或 `>=22.12.0`，pnpm 用 `>=7` |
| 登录后一会儿就掉线、Token 过期 | 后端重启过，或 Redis 里会话数据被清 | 重新登录；本地排查时确认 Redis 一直可用、没有被换库 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取 Maven / npm 依赖，访问本地 `8085` / `8086` 接口与文档页验收 |
| 读取文件 | 是 | 读取 `pom.xml`、`application-dev.yml`、`.env.development`、`db/yami_shop.sql` 以核对地址、端口与表结构 |
| 写入文件 | 是 | 修改本地配置与环境变量、执行数据库初始化脚本、构建产物落盘 |
| 凭证 | 是 | 需要 MySQL / Redis 账号口令，以及后台登录账号；仓库内默认值仅示例环境使用，必须替换 |
| 子进程 / 后台常驻 | 是 | `mvn spring-boot:run`、`pnpm run dev`、MySQL / Redis 都是长驻进程，需要能启停和看日志 |

## 触发场景

- 「帮我搭一个自己的单商户商城后台，能管商品订单会员」
- 「这个 Java 商城怎么本地跑起来？两个后端分别是什么？」
- 「后台登录一直 401，验证码也刷不出来」
- 「菜单加了但左侧不显示 / 按钮不见了」
- 「我想在商城后台加一个新页面和新表，怎么加？」
- 「小程序接口该连哪个端口？」

## 能力边界

**覆盖**：

- **本地到部署的完整启动路径**：数据库初始化、两个后端服务的启动与端口、管理后台前端启动、打包产物位置。
- **单商户商城的主链路实现指引**：商品与 SKU、购物车、下单、支付、权限与菜单按钮、文件上传、异常与日志约定。
- **后台管理功能二次开发的落点**：菜单表与页面路径的对应关系、权限标识的写法、`application-dev.yml` 与 `.env.development` 的改法。
- **典型故障的现象→原因→动作**：端口连错、导库缺失、401、菜单/按钮不显示、图片不显示、跨域、版本不满足。

**不覆盖**：

- 多商户、供应链、SaaS 多租户、跨境等能力，也不替使用者判断商业授权范围。
- 微服务拆分、分布式事务、独立扩容——需要这些请走微服务方案。
- 不代写业务代码：具体某个后台功能的完整实现（Controller / Service / Mapper / Vue 页面）只给落点和约定，不产出成品代码。
- 第三方组件的通用运维（MySQL / Redis / Nginx / Docker 自身安装调优）按各自官方文档处理。
- 前端页面的视觉设计与交互改造。

## 依赖条件

- **JDK 17 + Maven**（根 `pom.xml` 中 `java.version` 为 `17`）；Node.js `^20.19.0` 或 `>=22.12.0`，pnpm `>=7`。
- **MySQL `5.7+`**：库名 `yami_shops`，必须导入 `db/yami_shop.sql`，否则登录和菜单都用不了。
- **Redis `4.0+`**：默认 `6379`，登录态与缓存依赖它；不起 Redis 后台登不进去。
- **两套配置分开改**：`yami-shop-admin` 与 `yami-shop-api` 各有一份 `application-dev.yml`，数据库改了要改两处。
- 要接小程序 / H5 时，用户端接口 `yami-shop-api` 必须启动，且对应前端工程指向 `8086`。
- XXL-JOB 仅在需要定时任务时可选；不接支付回调时相关配置可以先留空。

## 已知限制

1. 开源版是**单商户 B2C**，不是多商户平台；商家入驻、分账、多店铺后台都不在该版本范围内。
2. 后端为**单体多模块**，两个服务共享同一套数据库与实体模块，无法按业务独立扩容。
3. 仓库根的 `docker-compose.yml` **当前不可直接使用**（引用的 `db/Dockerfile` 不在仓库内），容器化部署需要自行补镜像或改用 jar 部署。
4. 本地与生产端口不一致（`dev` 用 `8085` / `8086`，`prod` 配置为其他端口），照搬本地端口上线会连不上。
5. 依赖版本迭代较快，`pom.xml` 与 `front-end/*/package.json` 里的版本可能已变动，冲突时以仓库当前值为准。

## 自检清单

执行前：

- [ ] 确认是**单商户 B2C** 场景；要多商户请改用 `mall4cloud` 包。
- [ ] 确认 `java -version` 是 17，`pnpm -v` 满足 `>=7`，Node 版本满足 `engines`。
- [ ] 确认 MySQL 与 Redis 已启动，且 `yami_shops` 已导入 `db/yami_shop.sql`。
- [ ] 明确本次只跑管理后台闭环（`yami-shop-admin` + `mall4v`），不要一上来就同时起 Docker、Nginx、小程序。

执行后：

- [ ] `http://127.0.0.1:8085/doc.html` 能打开，控制台没有数据库 / Redis 连接报错。
- [ ] 管理后台页面能打开，Network 里接口请求发往 `8085`。
- [ ] `admin / 123456` 能登录，登录后左侧菜单正常显示。
- [ ] 若新增了菜单或按钮，对应角色已分配，前端权限标识与后端注解一致。
- [ ] 若改了配置，`yami-shop-admin` 与 `yami-shop-api` 两份 `application-dev.yml` 都已同步。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/gz-yami/mall4j | 上游仓库（安装与完整文档以它为准） |

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
