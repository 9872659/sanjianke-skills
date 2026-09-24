# 三剪客 · 深度文档理解 RAG Skill

RAGFlow 的部署前置条件与 Docker Compose 启动、Python SDK 建库/上传/解析/对话、OpenAI 兼容接口、切文档引擎与排错要点

---

## 前置条件

- 机器规格：CPU ≥ 4 核、内存 ≥ 16 GB、磁盘 ≥ 50 GB（官方前置条件）。
- Docker ≥ 24.0.0，Docker Compose ≥ v2.26.1。
- 宿主内核参数：`vm.max_map_count` ≥ 262144，否则 Elasticsearch 起不来。
- 架构：官方 Docker 镜像只针对 x86 构建；ARM64 需要自己构建镜像，且 Infinity 引擎在 Linux/arm64 上官方尚不支持。
- 一个可用的 LLM（必须）与 Embedding 模型（建库时需要），配在 `docker/service_conf.yaml.template`。
- 可选：gVisor（仅使用代码执行器功能时）；NVIDIA GPU 与容器运行时（用 `DEVICE=gpu` 加速 DeepDoc 时）。
- Python ≥ 3.13：仅源码开发模式需要，日常使用走 Docker 不需要本地 Python 环境。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径（Docker）：

```bash
sudo sysctl -w vm.max_map_count=262144

git clone https://github.com/infiniflow/ragflow.git
cd ragflow/docker
git checkout v0.27.2
docker compose -f docker-compose.yml up -d

docker logs -f docker-ragflow-cpu-1   # 看到启动 banner 再打开网页
```

灌库与提问（Python SDK）：

```python
from ragflow_sdk import RAGFlow

rag_object = RAGFlow(api_key="<YOUR_API_KEY>", base_url="http://<YOUR_BASE_URL>:9380")
dataset = rag_object.create_dataset(name="kb_1")

with open("1.txt", "rb") as file:
    documents = dataset.upload_documents([{"display_name": "1.txt", "blob": file.read()}])

dataset.async_parse_documents([documents[0].id])

assistant = rag_object.create_chat("Miss R", dataset_ids=[dataset.id])
session = assistant.create_session()
for ans in session.ask("安装方式是什么？", stream=True):
    print(ans.content)
```

配置文件清单、引擎切换与错误码见 `references/deploy-and-config.md`。版本号、端口与参数名以你手上那份代码和官方文档当前内容为准。

---

## 依赖

- Docker 与 Docker Compose（运行整套服务的唯一硬依赖）
- 一个 LLM 服务与一个 Embedding 模型（自备 API Key）
- `ragflow-sdk`（用 Python SDK 接入时：`pip install ragflow-sdk`）
- 可选：gVisor（代码执行器）
- 可选：NVIDIA GPU + 容器运行时（`DEVICE=gpu`）
- 源码开发模式额外需要：Python ≥ 3.13、`uv`、`lefthook`、`jemalloc`、Node.js

---

## 安全

- 不内嵌任何密钥
- API Key 与模型厂商 Key 都放在配置文件或环境变量里，不要写进镜像、不要提交到仓库
- 服务默认把 Web 端口映射到宿主的 80；公网可访问前请放在反向代理 / 鉴权之后，并限制来源
- 数据卷里是原始文档与解析结果，属于敏感数据；`down -v` 会清空数据，执行前必须确认已备份
- 首次启动需要拉取解析模型（会从外部下载权重），受限网络环境请先确认出口策略
- 该服务以容器方式持有宿主挂载目录的读写权限；挂载范围按最小必要原则给

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`RAGFlow`
- 仓库：https://github.com/infiniflow/ragflow

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
