# 三剪客 · 低代码企业级开发平台 Skill

在 Java + SpringBoot + Vue3 技术栈上快速搭建企业管理系统（OA / ERP / CRM / MIS）的落地指引。

---

## 前置条件

- **前端**：Node.js **20+**（上游说明 Vite 不再支持已 EOL 的 Node 18，需要用 20.19+ 或 22.12+），npm 或 pnpm（pnpm 要求 9+）。
- **后端**：Java（默认 JDK17，同时支持 JDK8 / JDK21）、Maven；IDE 建议 IntelliJ IDEA，**必须安装 lombok 插件**。
- **数据库**：MySQL 5.7+。平台**只提供 MySQL 建库脚本**，用 PostgreSQL / Oracle / SQL Server / MariaDB / 达梦 / 人大金仓 / TiDB / kingbase8 需要先自行转库。
- **缓存**：Redis。
- **分支选择**：新项目从 SpringBoot3 分支起步；基于 SpringBoot2 的分支上游已声明不再维护，仅用于兼容存量项目。
- **授权认知**：开源版为 Apache-2.0 附加补充条款，允许商用，但不得用于开发可能与本软件竞争的产品。

---

## 使用

按「先定分支 → 备环境 → 建库 → 起后端 → 起前端 → 生成业务代码」的顺序推进，跳步容易卡住。

1. **定分支**：`springboot3`（JDK17 + SpringBoot3 + Shiro，推荐）、`springboot3_sas`（换成 SpringAuthorizationServer）、`master`（JDK17/JDK8 + SpringBoot2，已停止维护）。
2. **取代码**：
   ```bash
   git clone -b springboot3 https://github.com/jeecgboot/JeecgBoot.git
   ```
   仓库里后端是 Java 多模块工程，前端是独立的 Vue3 工程，分别处理。
3. **备环境**：装 Node 20+、JDK17、Maven、Redis；IDEA 装 lombok 插件。
4. **建库**：创建数据库后导入平台自带的 MySQL 脚本；换库先转库。
5. **启动**：上游给了四条路径——开发环境搭建、IDEA 启动前后端（单体）、Docker 一键启动（单体）、Docker 一键启动（微服务）。**具体命令与配置字段随版本变化，以官方文档为准**；本包不复制也不猜测。
6. **沉淀业务**：简单功能用 Online 在线表单零代码配置；复杂功能走代码生成器（单表 / 树 / 一对多 / 一对一），生成后手工合并进自有模块。
7. **接 AI 能力**：平台自带 AI 应用模块（模型管理、知识库问答、流程编排、对话助手），默认接 DeepSeek，也支持 ChatGPT、Ollama 等。

默认登录账号 `admin` / `123456`，上线前必须修改。

---

## 依赖

- 前端：Node 20+、npm 或 pnpm 9+；技术栈为 Vue3 + TypeScript + Vite6 + Ant Design Vue4。
- 后端：Java（默认 JDK17）、Maven；SpringBoot3 分支搭配 Shiro，或 `springboot3_sas` 分支搭配 SpringAuthorizationServer；持久层 MyBatis-Plus；连接池 Druid；日志 logback。
- 数据与缓存：MySQL 5.7+（默认）、Redis。
- 微服务模式（可选）：Spring Cloud Alibaba 相关组件——注册与配置中心、网关、限流熔断、链路跟踪，以及消息中间件、分布式任务等。
- 文件存储（可选）：对象存储或本地存储。
- AI 模块（可选）：一个大模型服务的接入配置。
- 移动端配套（可选）：独立的多终端适配框架，支持 APP / 小程序 / H5 / 鸿蒙。

---

## 安全

- 不内嵌任何密钥。
- 平台默认账号密码是 `admin` / `123456`，属于公开信息，**上线前必须修改**，并复核角色、菜单与数据权限配置。
- 数据库口令、Redis 口令、对象存储密钥、短信与邮件通道凭据、大模型 API Key、单点登录凭据都写在项目配置文件里，不得提交到版本库，也不要贴进公开日志。
- 平台的数据权限可以控制到行级与字段级，涉及多租户或敏感数据的系统要在建表阶段就规划好权限粒度，事后补代价更高。
- 接口层支持基于 AK / SK 的认证鉴权，对外开放接口时优先走这套机制，不要直接暴露内部管理接口。
- 开源版与商业版功能有差异，不要把开源版当作已具备完整企业级能力的版本对外承诺。
- 商用前先阅读仓库中的 LICENSE 与补充条款，确认使用方式不违反「不得开发竞争性软件」这一条。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`JeecgBoot`
- 仓库：https://github.com/jeecgboot/JeecgBoot

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
