# RAGFlow 部署形态、配置清单与错误码

内容取自上游 README 与官方 Python API 参考。凡涉及具体版本号、端口号、参数名，都以你手上那份代码与官方文档的当前内容为准。

---

## 一、四种跑法怎么选

| 形态 | 适合谁 | 关键步骤 |
|---|---|---|
| Docker Compose（CPU） | 绝大多数自建场景 | `cd ragflow/docker` → `docker compose -f docker-compose.yml up -d` |
| Docker Compose（GPU） | DeepDoc 解析量大，想用 GPU 加速 | 先在 `.env` 首行加 `DEVICE=gpu`，再 `up -d` |
| 自建镜像 | ARM64 平台、要改镜像内容、要跟内网仓库 | `docker build --platform linux/amd64 -f Dockerfile -t infiniflow/ragflow:nightly .` |
| 源码开发 | 要改后端/前端代码 | `uv sync --python 3.13` → 起基础组件 → 起后端 → `cd web && npm install && npm run dev` |

源码开发模式的完整顺序（官方步骤）：

```bash
pipx install uv
git clone https://github.com/infiniflow/ragflow.git
cd ragflow/
uv sync --python 3.13
uv run python3 ragflow_deps/download_deps.py
git config --local --unset core.hooksPath
uv tool install lefthook
lefthook install

docker compose -f docker/docker-compose-base.yml up -d   # MinIO / ES / Redis / MySQL
# 在 /etc/hosts 里把 docker/.env 用到的主机名指到 127.0.0.1：
# 127.0.0.1  es01 infinity mysql minio redis sandbox-executor-manager

source .venv/bin/activate
export PYTHONPATH=$(pwd)
bash docker/launch_backend_service.sh

# 另开终端：前端
cd web && npm install && npm run dev

# 收工
pkill -f "ragflow_server.py|task_executor.py"
```

国内网络或对 HF 拉取慢时：`export HF_ENDPOINT=https://hf-mirror.com`。系统缺 jemalloc 时按发行版装（Ubuntu `libjemalloc-dev` / CentOS `jemalloc` / OpenSUSE `jemalloc` / macOS `brew install jemalloc`）。

---

## 二、配置文件清单

| 文件 | 管什么 |
|---|---|
| `docker/.env` | 系统级设置：`SVR_HTTP_PORT`、`MYSQL_PASSWORD`、`MINIO_PASSWORD`、`RAGFLOW_IMAGE`、`DOC_ENGINE`、`DEVICE` 等 |
| `docker/service_conf.yaml.template` | 后端服务配置；里面的 `${ENV_VARS}` 在容器启动时由环境变量渲染。默认 LLM 工厂与 API Key 在这里配（`user_default_llm`） |
| `docker/docker-compose.yml` | 服务编排；改端口映射（`80:80`）在这里 |
| `docker/docker-compose-base.yml` | 只起基础依赖组件（源码开发模式用） |
| `docker/README.md` | 上游对上述环境变量与配置项的详细说明 |

**共同规则：改完这些配置必须重启容器才生效。**

```bash
docker compose -f docker-compose.yml up -d
```

---

## 三、文档引擎切换（Elasticsearch ↔ Infinity）

```bash
# 1) 停掉全部容器（-v 会删数据卷，数据会清空）
docker compose -f docker/docker-compose.yml down -v

# 2) 在 docker/.env 里把 DOC_ENGINE 设为 infinity
# 3) 起服务
docker compose -f docker/docker-compose.yml up -d
```

注意：Linux/arm64 上切 Infinity 官方尚不支持。默认引擎是 Elasticsearch，负责全文与向量存储。

---

## 四、Python SDK 能力面（按官方 API 参考归类）

| 分类 | 主要方法 |
|---|---|
| 数据集 | `create_dataset`、`list_datasets`、`delete_datasets`、`DataSet.update` |
| 文档 | `upload_documents`、`list_documents`、`delete_documents`、`Document.update`、`Document.download` |
| 解析 | `async_parse_documents`、`parse_documents`（等结果并返回状态/切片数/token 数）、`async_cancel_parse_documents` |
| 切片 | `add_chunk`、`list_chunks`、`delete_chunks`、`update_chunk`、检索切片 |
| Chat 助手 | `create_chat`、`update`、`list_chats`、`delete_chats` |
| 会话 | `create_session`、`list_sessions`、`update`、`delete_sessions`、`Session.ask` |
| Agent | `list_agents`、`get_agent`、`create_agent`、`update_agent`、`delete_agent`、`create_session`、`Session.ask` |
| Memory | `create_memory`、`list_memory`、`delete_memory`、`add_message`、`search_message`、`get_recent_messages`、`forget_message`、`update_message_status` |

`Session.ask` 得到的 `Message.reference` 是命中的 `Chunk` 列表，带 `similarity`、`vector_similarity`、`term_similarity`、`position`、`document_name` 等字段——这就是「可追溯引用」的数据形态。

对话助手的 `prompt_config` 关键项：

| 键 | 作用 |
|---|---|
| `system` | 系统提示词 / 人设 |
| `empty_response` | 检索不到内容时返回什么 |
| `prologue` | 开场白 |
| `quote` | 是否带引用，默认 `True` |
| `parameters` | 系统提示词里的变量列表，`knowledge` 为保留键（放检索到的上下文） |

---

## 五、错误码：一定要分两层看

官方明确：响应里可能**同时**有 HTTP 状态码和响应体里的业务码，两者要分别判断。

HTTP 层：`200` 成功（但业务未必成功）、`400`、`401`、`403`、`404`、`409`、`500`。

业务层（响应体 `code`）：`0` 成功、`10` 未生效、`100` 异常、`101` 请求参数非法、`102` 数据非法或缺失、`103` 操作错误、`105` 连接错误、`106` 操作仍在进行、`108` 权限错误、`109` 认证错误，以及 `400/401/403/404/409/500`。

实践含义：**只看 HTTP 200 就当成成功是最容易踩的一个坑**，脚本里必须读 `code`。

---

## 六、排错顺序建议

1. `sysctl vm.max_map_count` 是否 ≥ 262144 → 不满足先改，再重启容器。
2. `docker ps` 看是不是所有容器都活着；`docker logs -f docker-ragflow-cpu-1` 看到 banner 没有。
3. 内存够不够 16 GB。
4. 架构是不是 x86；ARM64 要么自建镜像，要么接受限制。
5. 配置改了有没有重启容器。
6. SDK 连的端口（9380）与 Web 端口（默认 80）别混。
7. 再看业务码，别只看 HTTP 状态。

---

## 七、本文件不覆盖

- 各模型厂商的接入参数细节（在 `service_conf.yaml.template` 与官方 LLM 配置文档里）。
- 具体版本的镜像 tag 与发布时间（以仓库 releases 为准）。
- 托管版（cloud）的使用方式。
- Agent 画布 DSL 的完整语法。
