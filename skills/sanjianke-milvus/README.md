# 三剪客 · 分布式向量数据库 Skill

把文本、图片、多模态数据算成的向量存起来并做相似度检索；覆盖 Lite / standalone / 集群三种部署、客户端最小用法与运维避坑。

---

## 前置条件

- Python 侧准备 `pymilvus`；本地试跑再加装 `pymilvus[milvus-lite]`。
- Docker 方式需本机有 Docker（一键脚本内部调用 `sudo docker`）与一个可写工作目录。
- 集群方式需 Kubernetes 环境与存储规划。
- 向量由你自己的嵌入模型生成，Milvus 只负责存与检索。
- 生产使用前想清楚数据卷位置、备份与监控。

---

## 使用

本 Skill 按「选形态 → 装 → 起服务 → 建集合 → 灌数据 → 检索」的顺序组织：

1. 选形态：本地开发用 Milvus Lite（`MilvusClient("xxx.db")`），单机生产用 standalone（一键脚本或 Docker Compose），规模化用集群。
2. 装客户端：`pip install -U pymilvus`，本地库模式加 `[milvus-lite]`。
3. 起服务：`bash standalone_embed.sh start`，或 `docker compose up -d`；用 `curl -f http://localhost:9091/healthz` 确认健康。
4. 建集合：`client.create_collection(collection_name=..., dimension=...)`，维度必须与嵌入模型一致。
5. 灌数据：`client.insert(collection_name=..., data=...)`。
6. 检索：`client.search(collection_name=..., data=query_vectors, limit=K, output_fields=[...])`。
7. 运维：改配置写 `user.yaml` 后重启；升级用 `standalone_embed.sh upgrade`。

---

## 依赖

- Python 与 `pymilvus`（版本需与服务端成对管理）。
- Docker / Docker Compose（standalone 与 Compose 方式）。
- Compose 模板额外依赖 etcd 与 MinIO 两个服务容器。
- 源码编译路径的硬要求：Go >= 1.21、CMake >= 3.26.4 且 < 4、GCC >= 11（macOS 用 llvm >= 15）、Python > 3.8 且 <= 3.11。
- 一个嵌入模型或向量生成流程，用于产出待存储的向量。

---

## 安全

- 不内嵌任何密钥
- 连接信息（URI 与 token）通过环境变量或配置注入，不要写进代码仓库。
- 对外暴露 19530 前先确认已启用认证与 TLS，并按需配置 RBAC。
- 数据卷里是向量与元数据，属于业务资产，需要备份与访问控制。
- 一键脚本会用 `sudo` 运行容器，执行前先看清脚本内容与它挂载的目录。
- 生产环境不要把 Milvus Lite 的本地文件当共享存储使用。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Milvus`
- 仓库：https://github.com/milvus-io/milvus

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
