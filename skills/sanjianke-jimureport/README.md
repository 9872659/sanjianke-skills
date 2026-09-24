# 三剪客 · 在线报表与大屏设计器 Skill

给 SpringBoot 项目套一层在线报表与大屏引擎：类 Excel 的 Web 拖拽设计、30 多种数据源、复杂报表与套打打印，还能用自然语言让 AI 生成报表和大屏。

---

## 前置条件

- Java 项目，使用 SpringBoot（starter 坐标按 2 / 3 / 4 三个大版本区分）
- JDK 17+（示例工程为 SpringBoot 4 架构；SpringBoot2 版要求 JDK 8+，具体以官方集成文档为准）
- 一个用于存放报表元数据的数据库，示例工程用 MySQL 5.7+，需先执行初始化 SQL
- Redis 可选（用于权限相关集成）
- 构建工具：Maven；走容器方式还需 Docker 与 Docker Compose
- 用 AI 助手能力需自备兼容 OpenAI Chat Completions 格式的模型服务地址与 API Key
- **授权前置**：开源版为 LGPL 与附加条款的双许可模式，去版权标识与商用分发需购买商业授权，使用前请读完整协议

---

## 使用

```bash
# 1. 初始化元数据库（脚本会创建 jimureport 库）
mysql -u <用户> -p < db/jimureport.mysql5.7.create.sql

# 2. 跑示例工程
git clone https://github.com/jeecgboot/jimureport.git
cd jimureport/jimureport-example
mvn clean package
mvn spring-boot:run

# 3. 或走 Docker Compose（先 package 再起容器）
docker-compose up -d
```

启动后（默认账号 `admin` / 密码 `123456`，上线前必须改）：

- 报表工作台：`http://localhost:8085/jmreport/list`
- 仪表盘工作台：`http://localhost:8085/drag/list`

`SKILL.md` 里有三种集成方式、AI 助手配置、常用操作命令，以及依赖版本、建库脚本、端口、授权条款等完整避坑表。

---

## 依赖

- 报表引擎：`jimureport-spring-boot{2,3,4}-starter`
- 大屏与仪表盘：`jimubi-spring-boot{2,3,4}-starter`
- 可选按需引入：`jimureport-nosql-starter*`（Mongo / Redis / 文件数据集）、`jimureport-echarts-starter`（后台导出接口的图表支持）、对话式分析模块 starter
- 元数据库：MySQL 5.7+（示例），其它库需按官方文档转换脚本
- 服务端运行时：JDK 17+（随 starter 版本不同）
- 容器方式：Docker + Docker Compose
- 不内嵌任何密钥；数据源与模型服务的凭证由使用者自行配置

---

## 安全

- 不内嵌任何密钥
- 默认账号密码是公开的 `admin` / `123456`，且设计器与该界面默认可访问——**上线前必须改密码并接入自己的鉴权体系**
- 数据源连接串含数据库账号密码，AI 配置含模型服务 API Key，都要放配置中心或环境变量，不要提交到仓库
- `autoTableEnabled: true` 会让 AI 在你的数据源上真实执行 DDL/DML，**生产环境必须保持 `false`**
- 数据填报功能会回写业务库，开放前确认权限与校验规则，避免被当成注入业务数据的入口
- 元数据库承载全部报表定义，必须纳入定期备份；升级前先备份
- 报表里展示什么数据、给谁看、留存多久，需按行业与法规要求自行把关
- 二次开发与部署时必须保留官方版权标识（预览页的 "Powered by" 字样、Logo 与官方链接），除非已购买商业授权

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`jimureport`
- 仓库：https://github.com/jeecgboot/jimureport

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
