# 三剪客 · Java Agent 框架 Skill

Java 生态 AI Agent 框架接入、选型与踩坑排查

---

## 前置条件

- **JDK**：按目标工程核对。上游多数模块 JDK 8+ 可跑，但 **MCP 模块要求 JDK 17+**
- **构建工具**：Maven（上游为 Maven 多模块工程）；用 Gradle 需自行映射坐标
- **网络**：核对坐标与拉依赖需能访问 Maven 中央仓库；企业内网要配私服或镜像
- **模型侧**：至少一个可用模型端点及其 API Key（自备，走环境变量注入）
- **可选**：向量库（Redis / Qdrant / Chroma / Pgvector / MariaDB / Milvus / OpenSearch /
  Elasticsearch 等）；JDBC 或 Redis（Agent 运行时与异步任务持久化）

> **接入前必做**：核对坐标。上游仓库声明的版本与 Maven 中央仓库上实际可拉到的版本**不一致**
> —— 中央仓库 `com.agentsflex` 可见版本停在 `1.0.0-rc.6`（2025-02 后未再发布），
> 而上游仓库根 pom 的 `revision` 已到 `2.2.9`。先定版本线，再写代码。

---

## 使用

本 Skill 的入口是 `SKILL.md`，按「工作流路由」表转到对应参考文件：

| 你想做什么 | 看哪份 |
|---|---|
| 搞清框架由哪些模块组成、抽象怎么分层、责任链怎么排 | `references/core-concepts.md` |
| 动手接入：依赖、最小可跑示例、工具/MCP/Skills/向量库怎么接 | `references/integration.md` |
| 做框架选型对比，或线上问题排查 | `references/selection-and-troubleshooting.md` |

典型对话问法：

- 「Java 服务要接大模型，Agents-Flex / Spring AI / LangChain4j 选哪个？」
- 「pom 里写了 2.x 版本拉不下来，或者拉下来是老包名」
- 「工具模型不调用，上一轮的工具还泄漏到这一轮」
- 「同步跑通，流式报错」
- 「要用 Agent 运行时做工具审批和断点恢复，怎么落地」

**本包不替你做最终选型决策**，给的是判断维度与代价清单。

---

## 依赖

| 项 | 说明 |
|---|---|
| 运行时 | 无（本 Skill 全部为文字作业规范，不含可执行脚本） |
| 网络 | 仅在核对坐标时访问 Maven 中央仓库与上游仓库页面 |
| 上游软件 | 需自行获取与安装，本包不分发其源码或构建产物 |

---

## 安全

- 不内嵌任何密钥、Token 或 Cookie
- 不读取、不代持使用者的模型账号与 API Key；示例中的密钥一律用环境变量占位
- 不执行任何生产变更：不写库、不发消息、不改线上配置
- 涉及智能问数（Text2SQL）时**强制只读账号 + 只读校验 + LIMIT 限额**，三重防线缺一不可
- 涉及文件系统 Skills 时要求配置沙箱隔离执行，不用管理员账号运行模型脚本

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

本包主题对应的上游开源项目为 Agents-Flex（Apache-2.0）：https://gitee.com/agents-flex/agents-flex 。本包未收录该项目的源码、构建产物或文档原文，仅记录独立核对的公开事实与原创工程实践。

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
