# 部署与首次调用

本文负责把「选哪条路 → 跑通第一次调用 → 验证」这三步走完。接口参数细节见 `api-playbook.md`，报错与成本见 `pitfalls.md`。

---

## 一、先选路：云端还是自托管

| 判断条件 | 选云端 API | 选 Docker 自托管 |
|---|---|---|
| 你想多快拿到数据 | 注册完就能调，零运维 | 要装 Docker、构建镜像、盯服务 |
| 数据能不能出厂 | 请求经第三方中转 | 全在自己机器内网 |
| 截屏 / actions / agent / 商品音视频 format | 全部可用 | 默认栈**不含** Fire-engine，这些能力不可用 |
| 反爬强度 | 自带代理池与 Enhanced 模式 | 只有 bundled Playwright + 基础 fetch 回退 |
| 成本模型 | 按 credits 计费，有月额度 | 只花自己的机器电费和带宽 |
| 谁负责可用性 | 上游 | **你自己**：升级、备份、监控、恢复、合规 |
| 许可证 | 无需关心 | 上游主项目 AGPL-3.0，对外提供服务前须评估传染性条款 |

一句话结论：**要能力全、要快，走云端；要数据不出内网且有运维能力，走自托管。** 两者接口格式一致，自托管就是换个 Base URL。

---

## 二、路线 A：云端 API 首次调用

### 1. 拿 Key

在服务方控制台创建 API Key，形如 `fc-xxxxxxxx`。免费档每月 1000 credits，额度月初重置、不结转，不含按量付费，额度用尽后请求返回 402。

无 Key 也能用，但有严格限制：

- 只能调 **Search、Scrape、Parse**（官方 CLI / SDK / REST 客户端下额外开放 **Interact**）。
- 按 **IP** 计算，同时限制「每日请求数」和「每日 credits 消耗」两个上限，任一超限返回 **429**。
- **crawl、extract、map、batch scrape 等接口无 Key 一律不可用。**

### 2. 落 Key 到环境变量

```bash
# Linux / macOS
export FIRECRAWL_API_KEY=fc-你的Key

# Windows PowerShell（当前会话）
$env:FIRECRAWL_API_KEY = "fc-你的Key"

# Windows 永久写入用户环境变量
[Environment]::SetEnvironmentVariable("FIRECRAWL_API_KEY","fc-你的Key","User")
```

**不要把 Key 写进脚本源码、SKILL.md 或 git 提交。**

### 3. 第一次调用：单页抓取

```bash
curl -s -X POST https://api.firecrawl.dev/v2/scrape \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://example.com",
    "formats": ["markdown"],
    "onlyMainContent": true,
    "maxAge": 3600000,
    "timeout": 60000
  }'
```

期望返回形状：

```json
{
  "success": true,
  "data": {
    "markdown": "# Example Domain\n\n...",
    "metadata": {
      "title": "Example Domain",
      "sourceURL": "https://example.com",
      "statusCode": 200
    }
  }
}
```

**验收要点（两层状态都要看）**：

1. 请求层：HTTP `200` 且 `success: true`——这只说明接口受理并处理完了。
2. 页面层：`data.metadata.statusCode` 是 `200` / `304` 才算页面干净加载。它是 `403`、`404`、`500` 都**不影响** `success: true`，而且**照样计 1 credit**。

### 4. 第一次搜索

```bash
curl -s -X POST https://api.firecrawl.dev/v2/search \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "web scraping best practices",
    "limit": 5,
    "sources": ["web"],
    "scrapeOptions": { "formats": ["markdown"] }
  }'
```

去掉 `scrapeOptions` 只拿标题和摘要，计费是 2 credits / 10 条结果（向上取整）；带上 `scrapeOptions` 后每条结果再按 scrape 规则叠加计费。

### 5. 第一次整站抓取（异步）

```bash
# 提交作业
curl -s -X POST https://api.firecrawl.dev/v2/crawl \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://docs.example.com",
    "limit": 100,
    "scrapeOptions": { "formats": ["markdown"] }
  }'
# → {"success":true,"id":"<jobId>","url":".../v2/crawl/<jobId>"}

# 轮询直到 status 为 completed / failed / cancelled
curl -s -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/crawl/<jobId>

# 查失败页（别只看 completed == total）
curl -s -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/crawl/<jobId>/errors
```

`limit` 建议**永远显式指定**。不传时默认上限是 10000 页，提交时的额度预检只按 1 credit 做，不会为整站预留——很容易在不知情的情况下把额度打光。

---

## 三、路线 B：Docker Compose 自托管

### 1. 前置检查

| 项 | 要求 |
|---|---|
| Git | 任意近期版本 |
| Docker | Docker Engine 或 Docker Desktop |
| Compose | v2，命令必须是 `docker compose`（不是 `docker-compose`） |
| 端口 | 宿主 `3002` 空闲（只有 API 默认对外发布） |
| 资源 | 要同时跑 API、worker、Playwright、Redis、RabbitMQ、NuQ PostgreSQL，官方**未给出**验证过的最小主机规格，不够就加 CPU/内存/磁盘 |
| curl | 用于验证请求 |

### 2. 固定到具体 release

不要直接跑 `main`。浮动的镜像 tag 会自己变，配置和代码会对不上：

```bash
git clone https://github.com/firecrawl/firecrawl.git
cd firecrawl
git checkout v2.11.162        # 自托管指南验证过的版本
```

换版本前先读那个版本的 `docker-compose.yaml`，Compose 契约可能不同。

### 3. 写最小可用的 `.env`

```bash
cat > .env <<'EOF'
USE_DB_AUTHENTICATION=false
POSTGRES_USER=postgres
POSTGRES_PASSWORD=replace-with-at-least-32-random-characters
POSTGRES_DB=postgres
EOF
```

注意事项：

- `POSTGRES_PASSWORD` 必须换成至少 32 位随机串，且 **`.env` 不要提交**。
- `POSTGRES_DB` 保持 `postgres`，该版本内建的 `pg_cron` 配置指向这个库。
- `USE_DB_AUTHENTICATION=false` 只是**评估环境**的免鉴权开关。改这一个变量**不等于**完成了带鉴权的部署。
- 不要用 `apps/api/.env.example` 当 Compose 的配置来源——那是给 API 开发用的。
- `NUQ_BACKEND` 和 `BULL_AUTH_KEY` 保持不设，用 PostgreSQL 队列且不开队列管理 UI。
- 根 `.env` 只会覆盖 `docker-compose.yaml` 真正引用到的变量。

### 4. 构建并启动

```bash
docker compose up --build -d
docker compose ps --all
```

`ps --all` 里一次性初始化服务显示为已完成是正常的；未设置的可选变量告警也是正常的。

### 5. 两级验证：探活 + 冒烟

```bash
# 探活：只证明 API 进程能应答 HTTP
curl --fail --silent --show-error --max-time 5 \
  http://localhost:3002/v0/health/readiness
# → {"status":"ok"}

# 冒烟：这一次成功才算端到端通了
curl --fail-with-body --silent --show-error --max-time 75 \
  -X POST http://localhost:3002/v2/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["markdown"],"timeout":60000}'
# → {"success":true,"data":{"markdown":"...","metadata":{"statusCode":200}}}
```

`/v0/health/readiness` **不检查** Redis、PostgreSQL、RabbitMQ、Playwright、worker 和外网出口。它返回 `ok` 但 `/v2/scrape` 失败，是完全可能的。请求体里的 `timeout` 单位是**毫秒**，curl 的 `--max-time` 单位是**秒**，后者要留得比前者长，好让 API 有机会返回它自己的超时响应。

### 6. 自托管能力矩阵

第一次抓取成功之后，按需加能力，别一次全上：

| 你想要 | 怎么办 |
|---|---|
| scrape / crawl / map / search 核心路由 | 默认栈就够，含 fetch 与 Playwright 两条处理路径 |
| LLM 类抽取与 format | 自己接 OpenAI 兼容端点或 Ollama，然后**单独验证**这条路径 |
| Fire-engine 及其高级反爬 | 需要另外单独部署与配置，默认不含 |
| 截屏 / 页面 actions | **默认栈不支持**——fetch 与 Playwright 都报不支持，两者都要 Fire-engine |
| Agent / Browser / interact / feedback 及商品、菜单、音视频等专项 format | 走云端，或自行确认所需外部服务依赖 |

### 7. 上生产前必须补的账

Compose 只是让你跑通第一次，它不是生产架构：

- **持久化**：Compose 文件**没有**给 NuQ PostgreSQL、Redis、RabbitMQ 定义持久卷。数据要活过服务重建，就得自己加卷并演练备份恢复。
- **鉴权与 TLS**：默认 API **无鉴权**。只要它会离开可信网络，就必须先补完整的身份方案、TLS 终止和网络策略。
- **端口**：PostgreSQL、Redis、RabbitMQ、worker 端口默认保持私有，别随手发布出去。
- **可观测性**：定义监控、资源上限、扩容触发条件、升级与回滚流程。
- **密钥管理**：把数据库口令从 `.env` 挪进平台的密钥管理系统。
- **数据流向**：如果启用第三方 AI / 代理 / 解析服务，先梳理数据会流到哪里，再决定要不要开。

Kubernetes 与 Helm 样例是**版本化的起点**，不是「生产决策已经替你做完了」的证明。

### 8. 自托管排障速查

| 症状 | 处置 |
|---|---|
| 看到「正在绕过鉴权」告警 | `USE_DB_AUTHENTICATION=false` 下的预期行为，请求免 Key。若 API 可被不可信网络访问，立即停并补控制措施 |
| 某个长驻服务反复退出 | `docker compose ps --all` 看状态，`docker compose logs --tail=200` 看日志；再确认源码版本是否为既定 release，资源是否够 |
| PostgreSQL 起不来 | 检查 `.env` 语法、`POSTGRES_DB=postgres`、用户名口令在 API 和 DB 两侧是否一致 |
| 容器连不上 Redis | Compose 网络内地址必须是 `redis://redis:6379`；`localhost` 在容器里指向容器自身。若你加过 `REDIS_URL` / `REDIS_RATE_LIMIT_URL` 覆盖，删掉恢复默认 |
| `3002` 端口无响应 | `docker compose ps api` + `docker compose logs --tail=200 api`；端口被别的进程占用就停掉它或同步改发布端口；API 容器状态 running 后再重试 |
| 探活成功但 `/v2/scrape` 失败 | `docker compose logs --tail=200 api playwright-service`——探活不校验这些依赖 |
| scrape 请求超时 | 确认部署能出网到目标站、API 与 Playwright 都在跑；把 curl 的 `--max-time` 调得比请求体 `timeout` 更长 |

---

## 四、CLI 与 SDK 接入

### CLI

```bash
npm install -g firecrawl-cli
# 或免安装直接跑
npx -y firecrawl-cli@latest --help
```

常用命令：

```bash
# 抓取
firecrawl scrape https://example.com
firecrawl https://example.com --only-main-content

# 搜索
firecrawl search "AI news" --limit 10
firecrawl search "AI" --sources web,news,images
firecrawl search "react hooks" --categories developer
firecrawl search "machine learning" --categories research,pdf
firecrawl search "tech news" --tbs qdr:h        # 近一小时：qdr:h|d|w|m|y
firecrawl search "restaurants" --location "Berlin,Germany" --country DE
firecrawl search "documentation" --scrape --scrape-formats markdown
firecrawl search "firecrawl" --pretty -o results.json

# 站点地图
firecrawl map https://example.com --limit 500
firecrawl map https://example.com --search "blog"
firecrawl map https://example.com --sitemap only
firecrawl map https://example.com --include-subdomains
firecrawl map https://example.com -o urls.txt

# 交互（先 scrape 出会话，再用 interact 操作）
firecrawl scrape https://www.amazon.com
firecrawl interact "Search for iPhone 16 Pro Max"
firecrawl interact "Click on the first result and tell me the price"
firecrawl interact stop
```

`firecrawl browser` 是已废弃的隐藏命令，不要用于 Agent 工作流。

### SDK 包名

| 语言 | 安装 |
|---|---|
| Python | `pip install firecrawl-py` |
| Node.js | `npm install firecrawl` |
| CLI | `npm install -g firecrawl-cli` |
| Go | `go get github.com/firecrawl/firecrawl/apps/go-sdk` |
| Java / Rust / Ruby / PHP / .NET / Elixir | 见上游文档的 SDK 章节 |

SDK 的核心价值是**自动处理异步轮询与结果分页**——crawl / batch / agent 这类作业用 SDK 会少写一大段状态机。

### MCP 挂载（给支持 MCP 的客户端）

```json
{
  "mcpServers": {
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": { "FIRECRAWL_API_KEY": "fc-你的Key" }
    }
  }
}
```

托管版 MCP 的免密钥入口只暴露 Search、Scrape、Parse；其它工具需要连接账号或提供 Key。自托管栈也可以用本地 MCP 指向 `http://localhost:3002`。挂载完需要重启客户端进程。

---

## 五、首次接入自检

- [ ] 选定云端或自托管，并写下选择理由（数据合规 or 能力完整）。
- [ ] Key 只存在于环境变量，仓库里 grep 不到 `fc-` 开头的明文串。
- [ ] 至少一次 `/v2/scrape` 返回 `success: true` 且 `metadata.statusCode` 为 2xx/304。
- [ ] 异步作业的轮询以 `status` 终态退出，并以 `/errors` 端点核对失败页。
- [ ] 显式设置了 `limit`，没有依赖默认 10000。
- [ ] 自托管场景确认了截屏 / actions 是否需要，以及要不要额外部署 Fire-engine。
- [ ] 生产暴露前补齐了鉴权、TLS、持久化与备份。
