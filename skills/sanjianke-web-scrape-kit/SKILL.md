---
name: sanjianke-web-scrape-kit
slug: sanjianke-web-scrape-kit
displayName: 三剪客 · 全网数据采集引擎
description: "网页搜索、抓取与交互一体化的数据采集 API 与命令行工具。 遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Firecrawl 用一套接口打通搜索、抓取、站点地图、批量抓取与结构化抽取，输出干净 Markdown 或 JSON，支持云端 API 与 Docker 自托管，覆盖反爬代理、缓存加速、浏览器动作与限流计费全流程。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 网页采集
  - 搜索
---

# 三剪客 · 全网数据采集引擎

网页搜索、抓取与交互一体化的数据采集 API 与命令行工具。

你要给 Agent 喂实时网页数据时，自己写 requests + BeautifulSoup 那条路通常活不过三天：动态渲染拿不到、反爬拦一半、正文里混着导航和广告、PDF 和分页链接还得单独处理。Firecrawl 把这些活收进一套 HTTP 接口——`/scrape` 单页转 Markdown 或结构化 JSON，`/map` 秒出全站 URL 清单，`/crawl` 递归吃下整站，`/search` 边搜边抓正文，`/agent` 用一句自然语言直接取数。

它同时提供云端 API 和 AGPL-3.0 开源自托管两条路：不碰运维就用云端，要求数据不出内网就把 Docker Compose 栈跑在自己机器上。TypeScript 实现，官方还配了 Python / Node / Go / Java / Rust / Ruby / PHP / .NET / Elixir 多语言 SDK 与 CLI。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（必需） | 调用上游 HTTP 接口（云端 `api.firecrawl.dev` 或你自托管的 `localhost:3002`），并由该服务出网访问目标站点 |
| 读取文件 | 视需要 | 读取待抓 URL 清单、JSON Schema 定义、`.env` 配置与站点白名单 |
| 写入文件 | 视需要 | 把结果落盘为 `.md` / `.json` / `.jsonl`，或生成待入库的本地语料目录 |
| 凭证 | 是（云端模式） | 从环境变量读取 `FIRECRAWL_API_KEY`，以 `Authorization: Bearer` 发送；自托管模式可关闭鉴权 |
| 子进程 / 后台常驻 | 视需要 | 执行 CLI（`npx firecrawl-cli@latest`）或 `docker compose up` 拉起自托管栈；长抓取任务应放后台运行 |

**密钥与费用**：本 Skill 不内嵌任何密钥，不代理转发你的请求，也不代收任何费用。云端模式下请求产生的额度消耗由使用者自己的上游账号承担，Key 从上游控制台自行获取；自托管模式下所有流量与成本都落在你自己的机器上。请勿把 Key 写进 SKILL.md、脚本源码或提交记录，一律走环境变量。

## 触发场景

- 「把这个网页的内容抓下来，转成干净的 Markdown 给模型用」——单页抓取与正文净化。
- 「这个站有几百个页面，帮我全爬下来做知识库」——整站 `/crawl` 或 `/batch/scrape` 批量抓取。
- 「先看看这个域名下到底有哪些 URL，别急着抓」——`/map` 出站点地图，再决定抓哪些。
- 「搜一下这个关键词，把前 10 条结果的正文也一并取回来」——`/search` 带 `scrapeOptions` 一步到位。
- 「这个页面的价格/标题/参数要变成结构化字段，不要一堆文本」——`json` format 配 JSON Schema 抽取。
- 「页面要点一下才出内容，需要点击、滚动、填表单」——`actions` 浏览器动作序列。
- 「不想把数据发到外部服务，要本地跑」——Docker Compose 自托管。
- 「抓不动了 / 一直报 429 / 账单涨太快」——反爬代理、限流退避与成本核算排查。

## 快速开始

### 路径一：零密钥试跑（最快确认链路通不通）

官方对 Search / Scrape / Parse 开放了无 Key 入口，按 IP 有每日请求数和每日额度两个上限，超了返回 429：

```bash
curl -s -X POST https://api.firecrawl.dev/v2/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["markdown"]}'
```

### 路径二：带 Key 正式调用

```bash
export FIRECRAWL_API_KEY=fc-你的Key

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

`maxAge: 3600000` 表示一小时内的缓存副本可以直接返回，省时也省钱；要绝对实时就设 `maxAge: 0`，代价是每次都走全量渲染管线，更慢也更容易失败。

### 路径三：Node SDK（自动轮询异步任务）

```bash
npm install firecrawl
```

```javascript
import { Firecrawl } from 'firecrawl';

const app = new Firecrawl({ apiKey: process.env.FIRECRAWL_API_KEY });

const doc = await app.scrape('https://example.com', { formats: ['markdown'] });
console.log(doc.markdown);

// 整站抓取，SDK 会帮你等到结束
const job = await app.crawl('https://docs.example.com', { limit: 50 });
for (const page of job.data) console.log(page.metadata.sourceURL);
```

### 路径四：CLI（终端里最快）

```bash
npm install -g firecrawl-cli

firecrawl scrape https://example.com
firecrawl search "web scraping tutorials" --limit 5 --pretty
firecrawl map https://example.com --limit 500 -o urls.txt
firecrawl crawl https://docs.example.com --limit 50 --wait
```

### 路径五：Docker 自托管

```bash
git clone https://github.com/firecrawl/firecrawl.git
cd firecrawl

cat > .env <<'EOF'
USE_DB_AUTHENTICATION=false
POSTGRES_USER=postgres
POSTGRES_PASSWORD=换成至少32位随机串
POSTGRES_DB=postgres
EOF

docker compose up --build -d
docker compose ps --all

# 心跳探活
curl --fail --silent --show-error --max-time 5 http://localhost:3002/v0/health/readiness

# 端到端冒烟：这一次成功才算真的通了
curl --fail-with-body --silent --show-error --max-time 75 \
  -X POST http://localhost:3002/v2/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["markdown"],"timeout":60000}'
```

`/v0/health/readiness` 只证明 API 进程活着，不检查 Redis、PostgreSQL、RabbitMQ、Playwright 和外网出口，必须以一次真实 `/v2/scrape` 返回 `success: true` 为准。默认只把 API 暴露到宿主 `3002` 端口，且**没有鉴权**，别直接挂公网。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 部署方式选型、首次跑通、CLI/SDK/MCP 接入、自托管栈起不来 | `references/quickstart.md` |
| 各接口的准确参数、返回字段、批量与异步任务的取结果姿势 | `references/api-playbook.md` |
| 被反爬挡住、429/402 报错、成本失控、结果缺失或超时 | `references/pitfalls.md` |

## 能力边界

**覆盖**：

- 单页抓取：URL → Markdown / HTML / rawHtml / rawBase64 / links / images / summary / screenshot / json / branding / product / query / audio / video 多种输出格式。
- 结构化抽取：`json` format 支持 JSON Schema + 自然语言 prompt（prompt 上限 10000 字符），也可用免 LLM 的 `product` format 直接取商品字段。
- 站点发现：`/map` 出全站链接（含 `search` 关键词过滤、`limit` 默认 100、`sitemap` 三态、子域开关）。
- 整站抓取：`/crawl` 支持 `limit`（默认 10000）、`maxDiscoveryDepth`、`includePaths` / `excludePaths`（RE2 风格正则）、`crawlEntireDomain`、`allowSubdomains`、`allowExternalLinks`、`ignoreQueryParameters`、`delay`、`maxConcurrency`。
- 批量抓取：`/batch/scrape` 一次提交成千上万 URL，异步作业 + 分页取回。
- 搜索：`/search` 支持 `web` / `news` / `images` 三类源，`research` / `pdf` / `developer` 分类，`includeDomains` / `excludeDomains`、`tbs` 时间过滤（`qdr:h|d|w|m|y`）、地区与语言、结果正文随抓。
- 浏览器交互：`actions` 动作序列（wait / click / write / press / scroll / screenshot / scrape / executeJavascript / pdf），单请求最多 50 个动作，所有等待累计不超过 60 秒。
- Agent 取数：`/agent` 用 prompt（+ 可选 `urls`、`schema`、`effort`、`maxCredits`）自然语言直取数据，不用先知道 URL。
- 工程化：Webhook 事件（`crawl.page` / `crawl.completed` / `crawl.failed`）、WebSocket 实时取结果、`/team/credit-usage` 查额度、`/concurrency-check` 查并发、幂等键、ZDR 零数据留存、自托管 Docker Compose 与 K8s/Helm 样例。

**不覆盖**：

- 不替代目标站点的账号授权。需要登录态的页面要么自带 `headers`（Cookie/UA），要么走交互式方案，本 Skill 不提供任何绕过登录的手段。
- 不做数据清洗之后的业务加工（去重、入库、向量化、翻译），那是下游环节的事。
- 不提供反爬对抗的「破解」能力。代理与 Enhanced 模式只是提升成功率，不是保证。
- 自托管栈**默认不含** Fire-engine，因此**截屏、页面 actions 在默认自托管组合里不可用**；`/agent`、浏览器交互、商品/菜单/音视频等专项 format 也主要面向云端。
- 不包含 Change Tracking 在 `/search` 中的使用（Search 端点不支持 FIRE-1 与变更追踪）。
- 本 Skill 内不含任何可复制的第三方源码。正文为原创整理，仅引用接口路径、参数名、许可证等事实性信息。

## 依赖条件

- **网络**：能访问 `https://api.firecrawl.dev`（云端）或你自己的自托管地址；自托管节点还必须能出网访问目标站点。
- **凭据**：云端模式需要 `FIRECRAWL_API_KEY`（形如 `fc-...`）；自托管模式设 `USE_DB_AUTHENTICATION=false` 可免 Key，但这只是本地评估配置。
- **运行时**：CLI 与 Node SDK 需要 Node.js 18+；Python SDK 为 `pip install firecrawl-py`，需要 Python 3.9+。
- **自托管**：Docker Engine 或 Docker Desktop + Docker Compose v2（命令为 `docker compose`），宿主 `3002` 端口空闲，机器容量足够同时跑 API、worker、Playwright、Redis、RabbitMQ、NuQ PostgreSQL（及可选的 FoundationDB）。
- **AI 类能力**：`json` 抽取、`summary`、`/agent` 等依赖模型的能力，自托管时需要自行接入 OpenAI 兼容端点或 Ollama。

## 已知限制

- **robots.txt 默认遵守**。被 robots 拦下的 URL 会出现在 `GET /v2/crawl/{id}/errors` 的 `robotsBlocked` 数组里。`ignoreRobotsTxt` 与自定义 `robotsUserAgent` 属企业版能力。抓取合规责任在调用方，请自行确认目标站条款与当地法规。
- **结果只留 24 小时**。作业完成后 24 小时内可继续用 API 取回，过期只能去控制台看日志。截屏 URL 同样是 24 小时过期；音频/视频返回的签名 URL 1 小时过期。
- **爬取结果不保证完整，而且每次都可能不一样**。页面是并发抓的，链接发现顺序受网络时序影响，同一份配置不同轮次的覆盖范围会漂移。`completed == total` **不代表**没有失败页——`total` 不统计失败页，失败清单只能从 `/errors` 端点读。想要更可复现：把 `maxConcurrency` 设成 1，或在有完整 sitemap 的站点上用 `sitemap: "only"`。
- **`next` 不能当作「还有数据」的判据**。只要 `status` 不是 `completed`，响应就会带 `next`，failed / cancelled 的作业也会有。循环退出条件必须以 `status` 终态为准。
- **`includePaths` / `excludePaths` 匹配的是路径名而非完整 URL**，且是 RE2 风格正则（不支持环视和反向引用），编译失败直接 400。两个字段合计最多 1000 条模式、100000 字符；起始 URL 也要过 `includePaths`，不匹配可能一页都抓不到。
- **响应体上限 10MB**，超了要跟着 `next` 翻页。
- **计费口径**：抓取基础 1 credit/页，PDF 解析 +1 credit/PDF 页，JSON 格式 +4 credits/页，Prompt 注入检测 +4 credits/页，ZDR +1 credit/页，可叠加（JSON + ZDR 即 6 credits/页）。**返回了文档就算钱**——目标站返回 403/404 也照样计 1 credit，因为 Firecrawl 确实拿到了那个响应；彻底失败、没有任何文档返回才不计费。Crawl 和 Search 的每页都按同一套 scrape 计费规则叠加。
- **并发与限流**：瓶颈通常是并发浏览器数而非每分钟请求数。免费档 2 并发，Hobby 5，Standard 25，Growth 50，Scale/Enterprise 100+；排队中的任务最多等 48 小时后超时。超限返回 429，需要按 `Retry-After` 退避。
- **许可证**：上游主项目为 AGPL-3.0，SDK 与部分 UI 组件为 MIT。自托管后若对外提供修改过的服务，AGPL 的传染性条款需要你自行评估。
- **自托管不是生产架构**。官方给的 Compose 文件不含持久化卷、TLS、认证与高可用；把 API 放公网前必须补齐鉴权、TLS、网络策略、备份恢复与容量规划。

## 自检清单

- [ ] `FIRECRAWL_API_KEY` 走的是环境变量，没有硬编码进任何脚本或文档。
- [ ] 先用一次 `/v2/scrape` 的 `success: true` 验通链路，再跑批量任务。
- [ ] 请求里同时检查了两层状态：HTTP 200 + `success: true`（请求层），以及 `data.metadata.statusCode`（页面层）。
- [ ] 异步作业（crawl / batch / agent）用 `status` 终态判断结束，没有拿 `next` 是否存在当退出条件。
- [ ] 分页循环同时满足「`next` 存在」且「上一页 `data` 非空」才继续。
- [ ] 抓取结束后调了 `/errors` 端点核对失败页，没有把 `completed == total` 当成全成功。
- [ ] 明确设了 `limit`，没有依赖 crawl 默认的 10000 页上限。
- [ ] 非实时场景带了非零 `maxAge`，省时省钱；只有确需实时才用 `maxAge: 0`。
- [ ] 目标站点 robots.txt 与使用条款已确认；需要登录态的内容有合法授权。
- [ ] 跑批量前用 `/concurrency-check` 和 `/team/credit-usage` 估过并发与额度，知道这批要花多少 credits。
- [ ] 对 429 / 500 / 502 / 503 / 504 做了指数退避重试，对 400 / 401 / 402 / 403 / 404 / 409 / 413 不做重试。
- [ ] 自托管部署下没有误用截屏、actions 等需要 Fire-engine 的能力。
- [ ] 抓取结果落盘时确认了存储位置与体积，敏感数据按需开启 ZDR。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/quickstart.md` | 部署与首次调用：云端 / 自托管选型、Docker Compose 全流程、CLI 与 SDK 接入、MCP 挂载、冒烟验证与排障 |
| `references/api-playbook.md` | 各接口的用法、参数、返回：scrape / map / crawl / batch scrape / search / agent / interact 的路由选择、参数表、返回结构与取结果姿势 |
| `references/pitfalls.md` | 反爬、限流、成本、常见错误的实战处置：代理与 Enhanced 模式、429/402/408 退避、credits 核算、结果缺失与超时排查 |

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
