# 三剪客 · 向量相似度检索 Skill

Qdrant：向量相似度检索 的安装、常用命令与避坑要点

---

## 前置条件

- 服务端：已安装并运行 Docker（推荐），能映射 6333 与 6334 端口。
- 客户端：目标语言的官方库；Python 用 `pip install qdrant-client`。
- 已经确定 embedding 模型的输出维度，以及要用哪种相似度度量（Cosine / Dot / Euclid 等）。
- 想清楚哪些 payload 字段会参与过滤，这些字段需要提前建索引。
- 若要用 FastEmbed 本地算向量，需额外装可选依赖并能下载模型权重。
- 若非本机使用，先准备好网络隔离、鉴权与 TLS 方案。

---

## 使用

把本目录作为 Skill 交给 Agent，或直接对照 `SKILL.md` 操作。典型流程：

1. `docker run` 起服务，确认 `http://localhost:6333/dashboard` 能打开。
2. 按 embedding 维度建集合，并把过滤字段建成 payload 索引。
3. 用 `upload_collection` 批量灌数据，不要循环单条 upsert。
4. 用 `query_points` 检索，需要业务字段就带 `with_payload=True`。
5. 加过滤条件再跑一次，核对结果与延迟。
6. 重启服务验证数据持久化，确认存储目录确实挂到了宿主机。

REST 端点与请求体以 https://api.qdrant.tech/ 的 OpenAPI 规范为准；本 Skill 记录的是常用路径与已知坑位。

---

## 依赖

- Qdrant 服务端（Docker 镜像或按官方安装说明部署）。
- 官方客户端库：Python / JS / Rust / Go / .NET / Java 任选其一。
- 可选：FastEmbed（本地算 embedding）、Qdrant Cloud（托管与云端推理）。
- 可选：Qdrant Edge（设备侧进程内形态，支持 Python 与 Rust）。
- 上游自带的 Web 控制台无需额外安装，起服务即可用。

---

## 安全

- 不内嵌任何密钥
- 服务默认**无加密、无鉴权**，不要把 6333 / 6334 直接暴露到公网。
- 对外开放前按官方安全说明配置 API Key 与 TLS，并在前面加反向代理与访问控制。
- Cloud 的 `api_key` 与自建实例的密钥通过环境变量注入，不要写进代码或提交进版本库。
- 删除集合、按条件删除点都是不可逆操作，生产环境先做快照再执行。
- 向量与 payload 可能包含敏感原文，落盘目录、快照与备份按同等密级管理。
- 用多租户场景时按租户隔离分区，避免一次误查跨租户取数。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Qdrant`
- 仓库：https://github.com/qdrant/qdrant

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
