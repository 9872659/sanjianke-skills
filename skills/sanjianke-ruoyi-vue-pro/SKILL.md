---
name: sanjianke-ruoyi-vue-pro
slug: sanjianke-ruoyi-vue-pro
displayName: 三剪客 · 企业级后台管理开发框架
description: "一套能直接开工的后台管理系统脚手架：Spring Boot 多模块后端 + Vue 管理后台，自带用户/角色/菜单权限、SaaS 多租户、工作流、代码生成器、定时任务与文件存储。含 JDK 与分支对应关系、数据库与 Redis 初始化、Maven 编译与启动、端口与 401 排查。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "从零写一套后台管理系统太慢，这套框架把「权限 + 组织 + 字典 + 日志 + 工作流 + 代码生成」都提前做好了，你要做的是在里面填自己的业务。含三条 JDK 版本线的选择、MySQL 与 Redis 初始化顺序、最小可运行路径与启动验证，以及分支选错、数据库驱动没启用、模块没开等典型卡点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 企业级后台管理开发框架

要做一套内部管理系统时，最耗时间的往往不是业务逻辑，而是那些每家公司都一样的部分：登录鉴权、用户与部门、角色与菜单权限、数据字典、操作日志、定时任务、文件上传。ruoyi-vue-pro 就是把这些**提前做完**的一套脚手架——后端是多模块的 Spring Boot 工程，前端已经给好了管理后台，你只需要在里面加自己的业务。

它的定位是**给开发者的起点，不是给最终用户的成品**。跑起来之后你看到的是一个功能齐备的后台，但真正的价值在于：权限模型、多租户、工作流、代码生成这些「地基」已经在里面了，业务开发可以直接往上叠。

**上游项目**：`ruoyi-vue-pro`　**仓库**：https://github.com/YunaiV/ruoyi-vue-pro

## 什么时候用 / 不用

**用它**：

- 用户说「要做一套内部管理系统 / 后台」，需要用户、角色、部门、菜单权限这些基础能力。
- 需要**代码生成器**：给一张表，自动生成前后端 CRUD 代码、SQL 与接口文档，省掉重复劳动。
- 需要**审批流**：请假、报销、工单这类流程，要求支持会签、或签、驳回、加签等常见节点行为。
- 需要 **SaaS 多租户**：一套代码给多个租户用，各租户的菜单与按钮权限可独立配置。
- 团队技术栈就是 Java（Spring Boot）+ Vue，希望拿到一个结构清晰、模块划分明确的起点，并且配套的接口文档、数据库文档与运行日志已经现成。

**不要用它**：

- **非技术用户想直接拿来用**。这是开发框架，必须由开发者二次开发与部署，不能当成品软件装完就用。
- **想要一个已经做完的业务系统**（比如现成的商城后台）。它提供的是可复用的地基，业务功能要自己实现或按需启用。
- **技术栈不是 Java / Vue**。前后端都是围绕 Spring Boot 与 Vue 设计的，异构技术栈硬套会失掉大部分收益。
- **只想做一个极小的单表工具**。为了几个接口引入整套多模块框架，理解与运维成本不划算。
- **机器资源极度紧张**。Spring Boot 多模块 + MySQL + Redis 是常驻占用，资源低于这个量级要慎重。

## 安装

**前置：选择版本线（分支与 JDK 必须对应）**

官方给出的三条线是：

| 分支 | 运行时 | 框架 |
|---|---|---|
| `master` | JDK 8 | Spring Boot 2.7 |
| `master-jdk17` | JDK 17 / 21 | Spring Boot 3.5 |
| `master-jdk25` | JDK 25 | Spring Boot 4.x |

**第 1 步：克隆并等待依赖下载**

```bash
git clone https://github.com/YunaiV/ruoyi-vue-pro.git
cd ruoyi-vue-pro
git checkout master-jdk17     # 想用 JDK 17/21 就切这条分支；默认 master 对应 JDK 8
```

官方建议用 IDEA 打开工程并安装 Lombok、MapStruct 插件；**不建议用 Eclipse**，因为它缺少这两个插件的支持。

**第 2 步：初始化 MySQL**

创建一个名为 `ruoyi-vue-pro` 的数据库，然后**只执行一次**仓库 `sql` 目录下对应数据库类型的 `ruoyi-vue-pro.sql`。默认配置下 MySQL 监听 `3306`，账号 `root`，密码 `123456`；不一致就改配置文件（默认走 `application-local.yaml`）。

```sql
CREATE DATABASE `ruoyi-vue-pro` DEFAULT CHARACTER SET utf8mb4;
```

**第 3 步：初始化 Redis**

默认配置下 Redis 监听 `6379`、不设账号密码；不一致同样改 `application-local.yaml`。

**第 4 步：编译（只需首次）**

```bash
mvn clean install package -Dmaven.test.skip=true
```

官方说明：只有首次需要执行这条 Maven 命令，用于解决基础 `pom.xml` 尚未安装、导致 `BaseDbUnitTest` 类找不到的问题。

**第 5 步：启动后端**

运行 `yudao-server` 模块下的启动类 `YudaoServerApplication`。启动完成后访问 `http://127.0.0.1:48080`，返回下面这段 JSON 就说明后端起来了（`401` 是正常的，代表「未登录」）：

```json
{ "code": 401, "data": null, "msg": "账号未登录" }
```

**第 6 步：启动前端**

前端是独立的仓库，按技术栈分为 Vue3 + element-plus、Vue3 + vben(ant-design-vue)、Vue2 + element-ui 三种实现，移动端走 uni-app 方案。前端工程与启动命令以官方《快速启动（前端项目）》为准。

## 常用操作

**1. 首次编译（跳过测试）**

```bash
mvn clean install package -Dmaven.test.skip=true
```

如果 shell 把 `-Dmaven.test.skip=true` 里的点号解析出问题、报 `Unknown lifecycle phase`，官方给的写法是去掉单引号再执行。

**2. 验证后端是否真的起来了**

```bash
curl -i http://127.0.0.1:48080
```

预期返回 `401` 与 `账号未登录` 这类 JSON。这一步能把「服务没起来」和「只是没登录」区分开。

**3. 换数据库连接（改配置文件，不改代码）**

在 `application-local.yaml` 中改数据源与 Redis 地址、账号、密码即可。框架支持 MySQL、Oracle、PostgreSQL、SQL Server、MariaDB、TiDB 等；如果用的是 PostgreSQL / Oracle / SQL Server，官方说明需要先在 `yudao-spring-boot-starter-mybatis` 模块的 `pom.xml` 里把对应 JDBC Driver 的 `optional` 去掉，并刷新 Maven 依赖。

**4. 按需开启业务模块**

默认只启动 `system`（系统功能）与 `infra`（基础设施）两个模块，这是为了加快启动速度。工作流、支付、商城、公众号、报表、会员、各类行业模块等都要按官方对应文档单独开启——**代码在仓库里不等于已启用**。

**5. 用代码生成器出业务代码**

后台的「基础设施 → 代码生成」支持导入数据库表，一键生成 Java、Vue 前后端代码、SQL 脚本与接口文档，覆盖单表、树表、主子表三种形态。生成的代码直接落到对应模块里再用。

**6. 清缓存解决「类不存在」**

官方给出的处置：如果启动仍报类不存在，在 IDEA 里执行 `File -> Invalidate Caches` 清缓存后重启。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 编译或启动报 Lombok / MapStruct 相关错误 | 用了不支持的 IDE，或没装这两个插件 | 官方明确建议用 IDEA 并安装 Lombok 与 MapStruct 插件；不建议用 Eclipse |
| 首次启动报 `BaseDbUnitTest` 类不存在 | 基础 `pom.xml` 还没安装到本地仓库 | 先在根目录执行一次 `mvn clean install package -Dmaven.test.skip=true` |
| Maven 报 `Unknown lifecycle phase ".test.skip=true"` | shell 对参数里的点号处理方式不同 | 按官方写法去掉引号：`mvn clean install package -Dmaven.test.skip=true` |
| 启动即连接失败 | MySQL 或 Redis 与默认配置不一致 | 默认是 MySQL `3306` / `root` / `123456`、Redis `6379` 无密码；改 `application-local.yaml` |
| 换了 PostgreSQL / Oracle / SQL Server 后连不上 | 对应 JDBC Driver 在依赖里被标了 `optional`，默认不生效 | 在 `yudao-spring-boot-starter-mybatis` 的 `pom.xml` 里移除该 Driver 的 `optional`，再刷新 Maven 依赖 |
| 访问 `48080` 返回 401，以为没启动成功 | 这正是后端正常运行的响应 | 把 `401 / 账号未登录` 作为启动成功的判据，登录问题走另一条排查路径 |
| 启动后找不到工作流 / 支付 / 商城等功能 | 默认只拉起 `system` 与 `infra` 两个模块 | 按官方对应模块的文档开启；模块存在 ≠ 已启用 |
| 前端页面打不开或调不到接口 | 前端是独立工程，默认与后端不在同一端口 | 后端默认 `48080`；前端工程与端口以官方前端启动文档为准，并检查接口代理配置 |
| 切了分支后编译失败、语法不兼容 | 分支与 JDK 版本没有对应上 | 三条线不能混用：`master` 要 JDK 8，`master-jdk17` 要 JDK 17/21，`master-jdk25` 要 JDK 25 |
| 启动报 `Command line is too long` | IDEA 拼接的启动命令过长 | 按官方给出的处置调整启动方式，或清缓存后重试 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取 Maven 与前端依赖；后端对外提供 RESTful 接口；对接短信、对象存储、支付、第三方登录等外部服务时也需要出网 |
| 读取文件 | 是 | 读取工程源码与配置（`application-*.yaml`）；代码生成器需要读取数据库表结构；上传功能需读取本地文件 |
| 写入文件 | 是 | 写入编译产物与前端构建产物；代码生成器会把生成的 Java / Vue / SQL 文件写入工程；文件服务会写本地目录或对象存储 |
| 凭证 | 是 | 数据库账号密码、Redis 密码、后台管理员账号，以及短信、存储、支付、第三方登录等第三方密钥。**本 Skill 不内嵌任何密钥**，请用配置文件与环境变量管理 |
| 子进程 / 后台常驻 | 是 | 后端为常驻 Java 进程（默认 `48080`），前端需要 Node 环境构建与运行；生产部署一般还要 MySQL、Redis，以及可选的消息队列 |

## 触发场景

- 「帮我搭一套后台管理系统」
- 「要能配角色和菜单权限的内部系统」
- 「用代码生成器把表变成 CRUD 页面」
- 「要支持多租户，一套系统给几家公司用」
- 「审批流要支持会签和或签」
- 「启动报 401 / 数据库连不上，帮我看看」

## 能力边界

**覆盖**：

- 系统功能：用户、角色、菜单与按钮权限、部门与岗位、数据字典、租户与租户套餐、站内信、通知公告、操作日志与登录日志、错误码、地区等。
- 基础设施：代码生成、接口文档、数据库文档、表单构建、配置管理、定时任务、文件服务、WebSocket 示例、API 日志、Redis / MySQL 监控、消息队列、分布式锁与限流等。
- 工作流：基于 Flowable，支持图形化流程设计、动态表单、会签 / 或签 / 依次审批、抄送、驳回、转办、委派、加签减签、撤销终止、超时审批与自动提醒、父子流程、条件 / 并行 / 包容 / 路由分支、触发节点与延迟节点。
- 多端与权限：Token + Redis 的认证体系，动态权限菜单，SaaS 多租户，SSO 单点登录，移动端 uni-app 方案。
- 数据与中间件可换：多种关系型数据库、多种消息队列实现。
- 业务模块（按需开启）：会员中心、数据报表与大屏设计器、商城、支付、公众号、CRM、ERP、WMS、MES、HRM、FMS、PMS、IM 即时通讯、AI 大模型、IoT 等。
- 工程质量：基于 JUnit + Mockito 的单元测试体系。

**不覆盖**：

- 不提供部署后即可使用的成品业务功能；业务逻辑必须由开发者实现，或按官方文档启用对应模块。
- 不做前端 UI 设计服务，也不包含设计稿与品牌资产。
- 不提供云资源、短信通道、存储桶、支付商户号等第三方账号与配额。
- 不替你完成生产级安全加固、容量规划与高可用架构设计。
- 不提供模型训练或推理能力；AI 相关模块只是业务侧的能力接入。

## 依赖条件

- JDK：按分支选择——`master` 用 JDK 8，`master-jdk17` 用 JDK 17/21，`master-jdk25` 用 JDK 25。
- 构建工具：Maven（首次需要执行一次完整编译安装）；前端需要 Node 环境。
- 数据库：MySQL（官方默认与主推）或其他受支持的关系型数据库；需要提前建库并执行初始化 SQL。
- 缓存：Redis，默认 `6379` 无密码。
- IDE：官方建议 IDEA，并安装 Lombok、MapStruct 插件。
- 可选：消息队列（多种实现可选）、对象存储、短信通道、支付渠道、第三方登录平台等，按启用的模块准备。
- 前端：独立仓库，按所选技术栈（Vue3 element-plus / Vue3 vben / Vue2 element-ui）单独启动。

## 已知限制

- 默认配置面向**本地开发**：数据库密码是 `123456`、Redis 无密码，上生产前必须全部替换。
- 默认只启动 `system` 与 `infra` 两个模块，其余模块需要按官方文档单独开启，容易误判为「功能缺失」。
- 上游按不同 JDK 版本维护三条分支，切换分支时运行环境必须同步切换，不能只改代码。
- 前端与后端是分开的仓库，联调时要自己确认端口与接口代理，不能假设一条命令就能跑通全栈。
- 上游迭代较快，模块划分、配置项与前端工程可能变化；**执行前请以官方文档与当前分支的实际文件为准**。
- 具体版本号、依赖版本与发布日期请以仓库与官方文档的实时信息为准，本 Skill 不做断言。

## 自检清单

- [ ] 已确认所选分支与本地 JDK 版本匹配（8 / 17·21 / 25 三条线不混用）。
- [ ] 使用的是 IDEA，并已安装 Lombok 与 MapStruct 插件。
- [ ] 已创建数据库并**只执行一次**对应数据库类型的初始化 SQL。
- [ ] MySQL 与 Redis 的地址、账号、密码已与 `application-local.yaml` 对齐。
- [ ] 首次已执行 `mvn clean install package -Dmaven.test.skip=true`。
- [ ] 启动类是 `YudaoServerApplication`，访问 `http://127.0.0.1:48080` 返回 `401 / 账号未登录`。
- [ ] 需要的业务模块已按官方文档单独开启，而不是假定默认全开。
- [ ] 若换用了非 MySQL 数据库，已移除对应 JDBC Driver 的 `optional` 并刷新依赖。
- [ ] 前端工程已单独启动，接口代理指向后端 `48080`。
- [ ] 生产化改造清单已列全：默认密码替换、HTTPS、日志与备份、权限收紧。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/YunaiV/ruoyi-vue-pro | 上游仓库（安装与完整文档以它为准） |
| https://doc.iocoder.cn/quick-start/ | 官方后端快速启动文档（分支、初始化、编译与启动步骤的出处） |

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
