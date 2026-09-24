# 三剪客 · Java 商城系统 Skill

mall4j：Java 商城系统 的安装、常用命令与避坑要点

---

## 前置条件

- **JDK 17**：根 `pom.xml` 中 `java.version` 为 `17`，低版本 JDK 编不过。
- **Maven**：能构建多模块工程即可，两个后端服务和公共模块在同一份 `pom.xml` 下。
- **MySQL `5.7+`**：库名 `yami_shops`，**必须先导入 `db/yami_shop.sql`**，否则登录、菜单、权限全都没有数据。
- **Redis `4.0+`**：本地默认 `6379`，登录态与缓存依赖它，没起 Redis 后台登不进去。
- **Node.js `^20.19.0` 或 `>=22.12.0`、pnpm `>=7`**：管理后台位于 `front-end/mall4v`，以该目录 `package.json` 的 `engines` 为准。
- 两套后端各有独立配置：`yami-shop-admin`（管理端接口）与 `yami-shop-api`（用户端接口）各有一份 `src/main/resources/application-dev.yml`，改数据库要改两处。

---

## 使用

最短跑通路径（管理后台能登录即算通）：

1. `git clone https://gitee.com/gz-yami/mall4j.git`（GitHub 同名仓库内容一致）。
2. 启动 MySQL，建库 `yami_shops`，导入 `db/yami_shop.sql`。
3. 启动 Redis（默认 `6379`）。
4. 起管理端后端：`mvn -pl yami-shop-admin -am spring-boot:run`，默认端口 `8085`。
5. 起管理后台前端：`cd front-end/mall4v && pnpm i && pnpm run dev`，默认端口 `9527`。
6. 确认 `front-end/mall4v/.env.development` 里 `VITE_APP_BASE_API = 'http://127.0.0.1:8085'`。
7. 用初始化账号 `admin / 123456` 登录（仅示例环境）。

需要用户端时再起 `mvn -pl yami-shop-api -am spring-boot:run`（`8086`），小程序 / uni-app 连 `8086`，管理后台连 `8085`，这两个端口不能混。

验收：`http://127.0.0.1:8085/doc.html` 能打开管理端接口文档；管理后台页面能打开、能登录、左侧菜单正常显示。

---

## 依赖

| 类别 | 依赖 | 说明 |
|---|---|---|
| 运行时 | JDK 17、Maven | 后端构建与启动 |
| 前端 | Node.js `^20.19.0 \|\| >=22.12.0`、pnpm `>=7` | 管理后台 `front-end/mall4v` |
| 框架 | Spring Boot `4.0.3`、MyBatis / MyBatis-Plus `3.5.16`、Sa-Token `1.44.0` | 依据根 `pom.xml` |
| 缓存与锁 | Redis `4.0+`、Redisson `4.3.0` | 登录态、缓存、分布式锁 |
| 数据库 | MySQL `5.7+`，库名 `yami_shops`，脚本 `db/yami_shop.sql` | 业务数据与菜单权限数据 |
| 可选 | XXL-JOB `2.4.2`、Knife4j `4.5.0` | 定时任务、接口文档页 |
| 前端目录 | `front-end/mall4v`、`front-end/mall4m`、`front-end/mall4uni` | 管理后台、微信小程序、uni-app 多端 |
| 授权 | AGPLv3（开源版） | 闭源商用需另行取得商业授权 |

依赖版本随仓库迭代变动，以根 `pom.xml` 与各前端 `package.json` 的当前值为准。

---

## 安全

- 不内嵌任何密钥：本包只描述安装与排错步骤，不含真实账号、口令或 Token。
- 默认账号 `admin / 123456` 与本地数据库账号 `root / root` 仅用于开发环境，部署前必须改密并清理演示数据。
- 后端接口权限由 `@PreAuthorize("@pms.hasPermission('权限标识')")` 控制，前端按钮隐藏**不是**权限边界，新接口必须补后端权限注解。
- 上传与静态资源地址（`VITE_APP_RESOURCES_URL`）不要指向未鉴权的公网存储；生产环境建议由 Nginx 同域反向代理，避免直接暴露后端端口。
- `application-prod.yml` 中的数据库、Redis 地址与端口必须改成真实环境值，不能沿用本地 `8085` / `8086`。
- 开源版为 AGPLv3，闭源分发与商业交付需先确认授权范围。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`mall4j`
- 仓库：https://github.com/gz-yami/mall4j

---

## 许可证

MIT，见 `LICENSE.md`。

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
