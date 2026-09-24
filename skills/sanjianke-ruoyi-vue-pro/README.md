# 三剪客 · 企业级后台管理开发框架 Skill

从零写一套后台管理系统太慢，这套框架把「权限 + 组织 + 字典 + 日志 + 工作流 + 代码生成」都提前做好了，你要做的是在里面填自己的业务。

---

## 前置条件

- 一个与所选分支匹配的 JDK：`master` 对应 JDK 8，`master-jdk17` 对应 JDK 17/21，`master-jdk25` 对应 JDK 25。
- Maven，能够拉取依赖并完成首次编译安装。
- 一个关系型数据库：官方默认与主推 MySQL，也支持 PostgreSQL、Oracle、SQL Server、MariaDB、TiDB 等。
- 一个 Redis 实例，默认 `6379`、无密码。
- 一个 IDE：官方建议 IDEA，并安装 Lombok、MapStruct 插件。
- 可选：Node 环境用于启动前端；按需准备消息队列、对象存储、短信通道等。

---

## 使用

1. 克隆仓库并切到与本地 JDK 匹配的分支，用 IDEA 打开、等 Maven 依赖下载完成。
2. 建一个名为 `ruoyi-vue-pro` 的数据库，执行仓库 `sql` 目录下对应数据库类型的初始化脚本（只执行一次）。
3. 启动 Redis，并把 MySQL / Redis 的连接信息与 `application-local.yaml` 对齐。
4. 在根目录执行一次 `mvn clean install package -Dmaven.test.skip=true`。
5. 运行 `yudao-server` 模块的启动类 `YudaoServerApplication`，访问 `http://127.0.0.1:48080` 应返回 `401 / 账号未登录`。
6. 按需开启业务模块（默认只拉起 `system` 与 `infra`），再单独启动前端工程。

完整的六块操作说明（什么时候用 / 不用、安装、常用操作、常见坑、权限与用途说明、能力边界）见 `SKILL.md`。

---

## 依赖

- JDK 与分支强绑定，三条版本线不能混用；Spring Boot 版本随分支变化。
- Maven 负责后端构建；前端为独立仓库，需要 Node 环境。
- MySQL（默认）或其他受支持的关系型数据库，需要提前建库并初始化表结构。
- Redis：缓存、Token 与部分中间件能力依赖它。
- IDE 需支持 Lombok 与 MapStruct；官方明确不建议用缺失这两个插件支持的 IDE。
- 可选依赖按启用的模块准备：消息队列、对象存储、短信、支付渠道、第三方登录等。

---

## 安全

- 不内嵌任何密钥。数据库密码、Redis 密码、第三方服务密钥都由使用方自行配置与保管。
- **默认配置是开发配置**：数据库账号密码为 `root / 123456`、Redis 无密码。上生产前必须替换，并限制数据库与 Redis 的访问来源。
- 不要把 `application-*.yaml` 中的真实密钥提交到公开仓库；用环境变量或外置配置管理。
- 生产环境必须补齐 HTTPS、访问控制与日志审计；后台管理系统本身就是高价值攻击面。
- 代码生成器生成的代码要人工复核后再合入，避免把不合适的表结构或权限直接暴露出去。
- 上游软件自身的漏洞与安全问题请走上游仓库的 Issues 与安全公告渠道。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`ruoyi-vue-pro`
- 仓库：https://github.com/YunaiV/ruoyi-vue-pro

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
