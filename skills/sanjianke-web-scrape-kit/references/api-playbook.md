# 接口实战策略

一站式说清：**该调哪个接口、参数怎么填、返回怎么读、异步作业怎么取结果**。部署与首次跑通见 `quickstart.md`，报错与成本见 `pitfalls.md`。

接口路径以 **v2** 为准，示例中的 Base URL 云端为 `https://api.firecrawl.dev`，自托管为 `http://localhost:3002`。两者路径与请求体格式一致。

---

## 一、接口总览

| 接口 | 方法与路径 | 同步/异步 | 计费 | 什么时候用它 |
|---|---|---|---|---|
| Scrape | `POST /v2/scrape` | 同步 | 1 credit/页（+ 选项附加） | 已知确切 URL，要一页内容 |
| Map | `POST /v2/map` | 同步 | 1 credit/次 | 只要 URL 清单，不要正文 |
| Crawl | `POST /v2/crawl` | 异步（返回 jobId） | 1 credit/页 | 从种子 URL 递归吃整站 |
| Crawl 状态 | `GET /v2/crawl/{jobId}` | 同步 | 免费 | 轮询进度、翻页取结果 |
| Crawl 错误 | `GET /v2/crawl/{jobId}/errors` | 同步 | 免费 | 核对失败页与 robots 拦截 |
| Crawl 取消 | `DELETE /v2/crawl/{jobId}` | 同步 | — | 提前止损 |
| Batch Scrape | `POST /v2/batch/scrape` | 异步 | 1 credit/页 | URL 已知但数量巨大 |
| Batch 状态/错误 | `GET /v2/batch/scrape/{jobId}`（含 `/errors`） | 同步 | 免费 | 同 crawl，复用同一套状态控制器 |
| Search | `POST /v2/search` | 同步 | 2 credits/10 条结果（向上取整） | 只给关键词，不给 URL |
| Agent | `POST /v2/agent` | 异步 | 按实际抓取页数与模型消耗 | 连 URL 都不知道，一句话取数 |
| Agent 状态 | `GET /v2/agent/{jobId}` | 同步 | 免费 | 轮询结果 |
| Interact | `POST /v2/scrape/{scrapeId}/interact` | 同步 | 2–7 credits/浏览器分钟 | 页面上要先点、先滚、先填表 |
| Parse | `POST /v2/parse` | 同步 | 同 scrape | 上传本地文件解析（含 `/parse/upload-url`） |
| 实时结果 | `WS /v2/crawl/{jobId}` | 长连接 | 免费 | 不想轮询，要边抓边收 |
| 额度 | `GET /v2/team/credit-usage`、`.../historical` | 同步 | 免费 | 查已用 credits |
| 并发 | `GET /v2/concurrency-check` | 同步 | 免费 | 提交大批量前先看有没有槽位 |
| 队列 | `GET /v2/team/queue-status` | 同步 | 免费 | 看排队情况，决定要不要等 |

**用 v2，别用 v1。** v1 里 `/extract`、`/llmstxt`、`/deep-research` 已标记废弃，相关能力被 `/agent` 与 v2 的 `json` format 取代。v1 仍有 `/v1/scrape`、`/v1/crawl`、`/v1/map`、`/v1/search`、`/v1/batch/scrape`、`/v1/concurrency-check`、`/v1/crawl/{jobId}/errors` 等基础路由，但新项目没有理由从 v1 起步。

### 路由决策速查

```
只知道关键词，不知道去哪抓        → POST /v2/search
知道域名，想知道有哪些页面        → POST /v2/map
知道确切 URL，要一页内容          → POST /v2/scrape
知道一批确切 URL（几十~几万）     → POST /v2/batch/scrape
知道种子 URL，要整站              → POST /v2/crawl
连 URL 都不确定，只想描述需求     → POST /v2/agent
页面必须先交互才出内容            → POST /v2/scrape 再 /interact
要本地文件（PDF/文档）解析        → POST /v2/parse
```

---

## 二、`POST /v2/scrape` —— 单页抓取（最核心）

### 请求骨架

```bash
curl -X POST https://api.firecrawl.dev/v2/scrape \
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

只有 `url` 是必填。`formats` 默认 `["markdown"]`。

### 2.1 formats：决定返回什么

**字符串形式**（直接写名字）：

| format | 内容 |
|---|---|
| `markdown` | 页面正文转干净 Markdown（默认） |
| `html` | 清理过冗余元素的 HTML |
| `rawHtml` | 服务端原样返回的 HTML |
| `rawBase64` | 原始响应体的 Base64 串 |
| `links` | 页面上所有链接 |
| `images` | 页面上所有图片 |
| `summary` | LLM 生成的页面摘要 |
| `branding` | 品牌识别：配色、字体、排版、间距、UI 组件 |
| `product` | 商品页结构化字段（标题、价格、库存、图片、规格） |

**对象形式**（带 `type` 与额外选项）：

| format | 可用选项 | 说明 |
|---|---|---|
| `json` | `prompt?`、`schema?` | 用 LLM 抽结构化数据；prompt 上限 10000 字符 |
| `screenshot` | `fullPage?`、`quality?`、`viewport?` | 截屏，单请求最多一张；viewport 上限 7680×4320；**URL 24 小时后过期** |
| `changeTracking` | `modes?`（`json` / `git-diff`）、`tag?`、`schema?`、`prompt?` | 抓取间比对变更；**必须同时带 `markdown`** |
| `attributes` | `selectors: [{selector, attribute}]` | 按 CSS 选择器取 HTML 属性 |

`audio` 与 `video` 两种 format 可从受支持的视频 URL（如 YouTube）提取，返回带签名的存储 URL，**1 小时过期**。

几个易踩的坑：

- **`rawBase64` 必须单独使用**。与其它 format 同时出现会被 API 拒绝。它返回的是**裸 Base64 串**，不是 data URI；MIME 类型去 `metadata.contentType` 里读。它只含该 URL 那一个文件，**不含** CSS、图片等子资源。
- **`screenshot` 单请求最多一张**，viewport 最大 7680×4320。
- **`changeTracking` 依赖 `markdown`**，格式数组里没有 `markdown` 会失败。

### 2.2 内容过滤：要正文还是整页

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `onlyMainContent` | boolean | `true` | 只留正文，剥掉导航页脚等样板 |
| `includeTags` | array | — | CSS 选择器白名单，如 `["h1","p",".main-content","[data-testid=\"main\"]"]` |
| `excludeTags` | array | — | CSS 选择器黑名单，如 `["#ad","#footer","[role=\"banner\"]"]` |

**`includeTags` / `excludeTags` 作用在原始页面 DOM 上**，不是过滤后的结果上，所以选择器要按源 HTML 写。用整页做标签过滤的起点时，把 `onlyMainContent` 设成 `false`。

### 2.3 时间与缓存

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `waitFor` | int (ms) | `0` | 智能等待之外的额外等待，慎用 |
| `maxAge` | int (ms) | `172800000`（2 天） | 缓存副本比这个新鲜就直接返回；`0` = 永远重新抓 |
| `timeout` | int (ms) | `60000` | 单请求最长时长，最小 `1000` |

**`maxAge` 是最省钱也最省时的开关。** 默认 2 天内命中缓存直接秒回，官方口径是最快可到 500% 的提速。文档、文章、商品页、批量入库、开发测试都适合开缓存；股价、比分、突发新闻这类实时数据必须 `maxAge: 0`——代价是每次都走完整渲染管线，更慢更容易失败。不想让这次结果进缓存，用 `storeInCache: false`。

### 2.4 actions：先操作页面再抓

最多 50 个动作，所有 `wait` 与 `waitFor` 的累计等待**不得超过 60 秒**。

| 动作 | 参数 | 说明 |
|---|---|---|
| `wait` | `milliseconds?` 或 `selector?` | 等固定时长**或**等元素可见（二选一，别同时给）；用 `selector` 时 30 秒超时 |
| `click` | `selector`、`all?` | 点击匹配元素；`all: true` 点全部匹配项 |
| `write` | `text` | 往当前聚焦的输入框打字；**必须先有 `click` 聚焦** |
| `press` | `key` | 按键，如 `Enter` / `Tab` / `Escape` |
| `scroll` | `direction?`（默认 `down`）、`selector?` | 滚页面或滚指定元素 |
| `screenshot` | `fullPage?`、`quality?`、`viewport?` | 截屏，viewport 上限 7680×4320 |
| `scrape` | — | 在动作序列的当前位置抓取当前页 HTML |
| `executeJavascript` | `script` | 页面内执行 JS；返回值在响应的 `actions.javascriptReturns` 数组里 |
| `pdf` | `format?`、`landscape?`、`scale?` | 生成 PDF，支持 `A0`–`A6` / `Letter` / `Legal` / `Tabloid` / `Ledger`，默认 `Letter` |

行为约定：

- 动作**顺序执行**，上一步完成才走下一步。
- **PDF 不支持 actions**。URL 最终解析成 PDF 时，带 actions 的请求会失败。
- `write` 之前没有 `click` 聚焦目标元素，打字不会落在你要的框里。

典型登录/搜索流程：

```json
{
  "url": "https://example.com/search",
  "actions": [
    { "type": "wait", "milliseconds": 1000 },
    { "type": "click", "selector": "#accept-cookies" },
    { "type": "scroll", "direction": "down" },
    { "type": "click", "selector": "#q" },
    { "type": "write", "text": "firecrawl" },
    { "type": "press", "key": "Enter" },
    { "type": "wait", "milliseconds": 2000 }
  ],
  "formats": ["markdown"]
}
```

### 2.5 json format：结构化抽取

```bash
curl -X POST https://api.firecrawl.dev/v2/scrape \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://example.com/pricing",
    "formats": [{
      "type": "json",
      "prompt": "提取所有套餐名称、月付价格与是否包含 SSO",
      "schema": {
        "type": "object",
        "properties": {
          "plans": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": { "type": "string" },
                "monthlyPrice": { "type": "number" },
                "supportsSSO": { "type": "boolean" }
              },
              "required": ["name"]
            }
          }
        },
        "required": ["plans"]
      }
    }],
    "onlyMainContent": false,
    "timeout": 120000
  }'
```

- `schema` 与 `prompt` 可以只给一个，也可以都给。prompt 上限 10000 字符。
- **商品页优先用免 LLM 的 `product` format**——不加 credits、不用定义 schema。需要自定义字段或非商品页时才上 `json`。
- 抽取失败的典型责任方是 schema 本身：`422` 表示 schema 不是合法 JSON Schema，或模型产不出符合结构的结果。放宽 `required`、减少嵌套层级通常能救回来。

### 2.6 地区、语言、移动端

```json
{
  "url": "https://example.com",
  "mobile": true,
  "location": { "country": "GB", "languages": ["en-GB"] },
  "onlyMainContent": false,
  "waitFor": 2000
}
```

- `mobile: true` 模拟移动设备，应对响应式站点在桌面端藏内容的情况。
- `location.country` 选代理出口国家（两字母代码）；`languages` 影响 `Accept-Language`。
- 站方顽固地给桌面布局时，在 `headers` 里补一个移动端 `User-Agent`。

### 2.7 返回结构

```json
{
  "success": true,
  "data": {
    "markdown": "...",
    "metadata": {
      "title": "页面标题",
      "sourceURL": "https://example.com",
      "statusCode": 200,
      "contentType": "text/html",
      "error": "（页面出错时可能有）"
    }
  }
}
```

**两层状态必须分开看**：

| 层 | 看哪里 | 含义 |
|---|---|---|
| 请求层 | HTTP 状态码 + `success` | 接口是否受理并处理完成。目标页返回 403，这里**依然是 200 + true** |
| 页面层 | `data.metadata.statusCode` | 目标站对该页的真实响应。`2xx` 或 `304` 才算干净加载 |

可靠姿势：先确认 `HTTP 200` + `success: true`，再查 `data.metadata.statusCode`。遇到 `403` 反复出现，去 `data.metadata.error` 找细节，并且**别再重试这个 URL**——它不仅会一直失败，还会一直计费。

---

## 三、`POST /v2/map` —— 秒出全站 URL

```bash
curl -X POST https://api.firecrawl.dev/v2/map \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com", "search": "pricing", "limit": 200}'
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `search` | string | — | 按文本匹配过滤链接，返回按相关度排序 |
| `limit` | integer | `100` | 最多返回多少链接 |
| `sitemap` | string | `"include"` | `include` / `skip` / `only` |
| `includeSubdomains` | boolean | `true` | 是否包含子域 |

返回：

```json
{
  "success": true,
  "links": [
    { "url": "https://example.com/pricing", "title": "Pricing", "description": "..." }
  ]
}
```

**`/map` 只发现 URL，不抓正文**，每次调用 1 credit。它是整站抓取前最划算的一步：先看清有什么，再决定 `/crawl` 的 `includePaths` 怎么配，能省下大量无效页的 credits。

---

## 四、`POST /v2/crawl` —— 整站递归抓取

### 4.1 提交与取结果

```bash
# 1) 提交
curl -X POST https://api.firecrawl.dev/v2/crawl \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://docs.example.com",
    "limit": 100,
    "maxDiscoveryDepth": 3,
    "includePaths": ["docs", "blog"],
    "excludePaths": ["legal"],
    "scrapeOptions": { "formats": ["markdown"] }
  }'
# → {"success":true,"id":"<jobId>","url":"https://api.firecrawl.dev/v2/crawl/<jobId>"}

# 2) 轮询
curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/crawl/<jobId>

# 3) 失败页
curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/crawl/<jobId>/errors

# 4) 提前终止
curl -X DELETE -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/crawl/<jobId>
```

状态响应：

```json
{
  "status": "completed",
  "total": 50,
  "completed": 50,
  "creditsUsed": 50,
  "createdAt": "...",
  "completedAt": "...",
  "duration": 42,
  "expiresAt": "...",
  "next": "https://api.firecrawl.dev/v2/crawl/<jobId>?page=2",
  "data": [
    { "markdown": "# 标题\n\n正文...", "metadata": { "title": "标题", "sourceURL": "https://..." } }
  ]
}
```

| 字段 | 含义 |
|---|---|
| `status` | `scraping` / `completed` / `failed` / `cancelled` |
| `total` | `completed` + 在飞页数（active + queued + backlogged）。**不含失败页** |
| `completed` | 成功抓完的页数 |
| `creditsUsed` | 已消耗 credits |
| `expiresAt` | 结果还能从 API 取到的截止时间 |
| `next` | 下一页结果的 URL（响应上限 10MB 时出现；**`status` 非 `completed` 时也会出现**） |

### 4.2 结果读取的硬规则

1. **轮询退出条件只看 `status`**：`completed` / `failed` / `cancelled`。
2. **`next` 存在 ≠ 还有数据。** failed / cancelled 的作业也会带 `next`，用它当循环退出的判据会死循环。
3. **翻页的正确条件**：`next` 存在 **且** 上一页返回的 `data` 数组非空。
4. **`completed == total` 不代表全成功。** 终态下 active / queued / backlog 都归零，两个计数器必然相等，跟有没有失败页无关。**失败清单只能从 `/errors` 读**。
5. **`data` 里只有抓成功的页。** 目标站返回 404 的页**不算**抓取错误——它被成功抓到了，会带 `metadata.statusCode: 404` 出现在 `data` 里。

`/errors` 返回两个数组：

- `errors`：`id`、`url`、`error`（错误消息）、`timestamp`。网络错误、超时等都在这里；被有意跳过的外站首页以 `error` 码 `EXTERNAL_LINK` 出现。
- `robotsBlocked`：被目标站 robots.txt 拦下的 URL。

> `/errors` **不保证是全部失败的完备枚举**——某些内部失败类别在构造响应前就被过滤掉了。把它当作「上游报告了哪些失败」，而不是「没别的问题了」的证明。

### 4.3 抓取范围参数全集

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `url` | string | 必填 | 起始 URL |
| `limit` | integer | `10000` | 最多抓多少页。**建议永远显式给** |
| `maxDiscoveryDepth` | integer | — | 按**链接发现跳数**算的最大深度，不是 URL 里的 `/` 段数。根页与 sitemap 页深度为 0。达到最大深度的页仍会被抓，但**不再跟随它上面的链接** |
| `includePaths` | string[] | — | 只抓匹配的路径名，正则 |
| `excludePaths` | string[] | — | 排除匹配的路径名，正则 |
| `regexOnFullURL` | boolean | `false` | 让上面两个参数匹配**完整 URL**（含查询串）而非仅路径名 |
| `crawlEntireDomain` | boolean | `false` | 跟随同级与上级路径，而不只是子路径 |
| `allowSubdomains` | boolean | `false` | 跟随子域链接 |
| `allowExternalLinks` | boolean | `false` | 跟随外链。**只跟一跳**，外链页上的链接不再爬；指向外站**首页**的链接会被有意跳过 |
| `sitemap` | string | `"include"` | `include`（sitemap + 链接发现）/ `skip`（只用 HTML 链接）/ `only`（只用 sitemap + 起始 URL，不做链接发现） |
| `ignoreQueryParameters` | boolean | `false` | 避免同一路径因查询串不同被反复抓 |
| `ignoreRobotsTxt` | boolean | `false` | 忽略 robots.txt。**企业版专属** |
| `robotsUserAgent` | string | — | 评估 robots.txt 时用的自定义 UA。**企业版专属** |
| `delay` | number | — | 每次抓取之间的秒级延迟。**设了它并发会被强制为 1** |
| `maxConcurrency` | integer | 团队并发上限 | 最大并发抓取数 |
| `scrapeOptions` | object | — | 应用到每一页的 scrape 选项（formats、proxy、缓存、actions…） |
| `webhook` | object | — | Webhook 通知配置 |
| `prompt` | string | — | 用自然语言生成抓取参数；显式给的参数优先于生成值 |

**路径正则的坑（高频返工点）**：

- 匹配的是 **URL 的 pathname**，不是完整 URL，也不含查询参数。要匹配完整 URL 得开 `regexOnFullURL: true`。
- 语法是 **Rust regex（RE2 风格）**：**不支持环视（look-around）与反向引用**。编译不过直接 `400`，不会静默忽略。
- 单字段最多 1000 条模式、每条最长 2000 字符；`includePaths` 与 `excludePaths` **合计**最多 1000 条、100000 字符。
- 关键词式过滤请**一个词一条短模式**（`["pricing","docs","blog"]`），别把多个词拼成长长的 alternation。
- **起始 URL 也要过 `includePaths`**。起始 URL 不匹配时，整个 crawl 可能返回 0 页。这是「明明配了路径却一页没抓」的头号原因。

**默认只抓子路径**——`website.com/other-parent/blog-1` 在你抓 `website.com/blogs/` 时不会被返回，需要 `crawlEntireDomain`。想抓 `blog.website.com` 需要 `allowSubdomains`。

### 4.4 同一份配置为什么每次结果不同

页面是**并发**抓的，链接发现顺序取决于网络时序和哪一页先加载完，所以靠近深度边界的分支覆盖程度每轮都可能不一样。

想更可复现：

- **`maxConcurrency: 1`**（或设 `delay`，它会强制并发为 1）。这能削弱时序交织，但**不能消除**波动：sitemap 发现是在并发上限之外入队的，嵌套 sitemap 作为独立作业抓取，返回的 `data` 按**完成时间**而非发现顺序排列。
- **站点有完整 sitemap 时用 `sitemap: "only"`**，让 URL 集合来自 sitemap 而不是链接发现。

### 4.5 完成通知

不轮询就走 Webhook：每成功抓一页触发 `crawl.page`，整轮结束触发 `crawl.completed`（失败则 `crawl.failed`）。也可以连 `WS /v2/crawl/{jobId}` 实时收结果。

**作业完成后结果只在 API 上保留 24 小时**，过期只能去控制台看日志。

---

## 五、`POST /v2/batch/scrape` —— 大批量 URL

URL 清单已知、数量上千时用它，不要用循环打 `/scrape`。

```bash
# 提交
curl -X POST https://api.firecrawl.dev/v2/batch/scrape \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "urls": ["https://a.com", "https://b.com", "https://c.com"],
    "formats": ["markdown"]
  }'

# 状态（与 crawl 共用同一套状态控制器）
curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/batch/scrape/<jobId>

# 失败页
curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/batch/scrape/<jobId>/errors

# 取消
curl -X DELETE -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/batch/scrape/<jobId>
```

状态机、分页规则、`/errors` 语义与 crawl **完全一致**，直接套用 4.2 节的硬规则。Python SDK 写法：

```python
job = app.batch_scrape(
    ["https://a.com", "https://b.com", "https://c.com"],
    formats=["markdown"],
)
for doc in job.data:
    print(doc.metadata.source_url)
```

---

## 六、`POST /v2/search` —— 边搜边抓

```bash
curl -X POST https://api.firecrawl.dev/v2/search \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "web scraping tools comparison",
    "limit": 10,
    "sources": ["web"],
    "tbs": "qdr:m",
    "includeDomains": ["github.com", "docs.example.com"],
    "scrapeOptions": { "formats": ["markdown"], "onlyMainContent": true }
  }'
```

### 6.1 结果源与分类

**`sources`（结果类型）**：

| 值 | 内容 |
|---|---|
| `web` | 标准网页结果（默认） |
| `news` | 新闻类结果 |
| `images` | 图片搜索结果 |

可以一次要多种，如 `sources: ["web","news"]`。**此时 `limit` 按每种源分别生效**——`limit: 5` + 两种源 = 最多 5 条 web + 5 条 news。要给不同源配不同参数（不同 limit、不同 `scrapeOptions`），必须**拆成多次调用**。

**`categories`（分类过滤）**：

| 值 | 内容 |
|---|---|
| `research` | 限定学术与研究站点（arXiv、Nature、PubMed 等） |
| `pdf` | 搜 PDF |
| `developer` | 代码仓库的 issue、已合并 PR、README，外加精选文档站 |

注意：`developer` **返回在标准 `web` 分组里**，每条带 `category: "developer"`，且**不能与其它分类组合**。`research` 分类后续会改为检索论文记录（结果从 `data.web` 迁到 `data.research`，字段变为 `paperId` / `primaryId` / `ids` / `title` / `abstract` / `score`）；在那之前，每次用它都会在响应里带一条 `warnings`。要今天就拿论文记录，用 `/v2/search/research/papers`——它在 `web` 分组里返回标准网页结果。

### 6.2 常用筛选参数

| 参数 | 说明 |
|---|---|
| `limit` | 结果条数；多源时**每源各算一次** |
| `includeDomains` / `excludeDomains` | 域名白/黑名单 |
| `tbs` | 时间过滤：`qdr:h`（近一小时）/ `qdr:d` / `qdr:w` / `qdr:m` / `qdr:y`。**只对 `web` 源生效**，不过滤 `news` 与 `images`。要时间受限的新闻，用 `web` 源配 `site:` 语法定向新闻域名 |
| `location` | 地区，如 `"Germany"` 或 `"San Francisco,California,United States"` |
| `sources` | 结果类型数组 |
| `categories` | 分类数组 |
| `scrapeOptions` | 对每条结果做抓取；**除了 FIRE-1 Agent 与 Change Tracking，scrape 的参数都可用** |
| `timeout` | 单请求超时 |
| `safeSearch` | 安全搜索 |

### 6.3 两步模式 vs 一步模式

```python
# 一步：搜 + 抓，最快拿到正文
results = app.search("cache invalidation strategies", limit=3,
                     scrape_options={"formats": ["markdown"]})

# 两步：先看结果决定抓哪些，更省 credits
hits = app.search("cache invalidation strategies", limit=10)
for hit in hits.data.web[:3]:
    doc = app.scrape(hit["url"], formats=["markdown"])
```

**先搜后抓的可控性更好**：你能在读完整列表之后再决定抓哪几条。直接一步抓 10 条结果是 10 页的抓取成本，其中可能一半是噪音。

### 6.4 成本要点

`2 credits / 10 条结果`，**向上取整**：1–10 条 = 2 credits，11–20 条 = 4 credits。启用了抓取选项后，每条结果再按 scrape 计费叠加（基础 1 credit/页，PDF 解析 +1/页，JSON +4/页）。

省钱手段：

- **`parsers: []`** —— 不需要解析 PDF 就关掉它。
- **`limit` 收紧** —— 别默认拉 50 条只为看前 3 条。
- **分批 `tbs` 收窄时间窗** —— 减少无关结果。

搜索结果不理想可以用 `POST /v2/search/{jobId}/feedback` 反馈：**每个搜索作业的首次反馈可退还 1 credit**（受团队限制约束）。

---

## 七、`POST /v2/agent` —— 一句话取数

URL 都不知道、或者要跨多个站点比对时用它。它是 `/extract` 能力的演进版：更快、更稳、**不需要你预先知道 URL**。

```bash
curl -X POST https://api.firecrawl.dev/v2/agent \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "找出 Notion 的定价套餐并对比"}'
```

返回：

```json
{
  "success": true,
  "data": {
    "result": "Notion 提供以下套餐：\n1. Free - $0/月...\n2. Plus - $10/席位/月...",
    "sources": ["https://www.notion.so/pricing"]
  }
}
```

**异步**：`POST` 提交拿到 jobId，`GET /v2/agent/{jobId}` 轮询。配套还有 `/v2/agent/{jobId}/trace`（执行轨迹）、`/v2/agent/{jobId}/skill`、`/v2/agent/{jobId}/snapshots/{snapshotId}`（快照）。

### 参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `prompt` | string | 必填 | 自然语言描述要抽什么数据，上限 10000 字符 |
| `urls` | array | — | 把 Agent 约束在这些 URL 上 |
| `schema` | object | — | JSON Schema，用于结构化输出 |
| `maxCredits` | number | `2500` | 本次运行最多能花多少 credits。控制台最高支持 2500；更高的值只能走 API 传，且**超过 2500 一律按付费请求计费** |
| `strictConstrainToURLs` | boolean | `false` | `true` 时只访问你给的 URL |
| `model` | string | `"spark-2"` | AI 模型。Spark 1 系列已废弃，当前会路由到 `spark-2` |
| `effort` | string | 未设 | 推理预算：`low` / `medium` / `high`。所有运行都在 `spark-2` 上执行，所以 `effort` 可以带也可以不带 `model` |

`effort` 三档怎么选：

| 档位 | 适合 |
|---|---|
| `low` | 单站点上的简单查询 |
| `medium` | 几个页面上的多步任务 |
| `high` | 深度调研、复杂导航、关键数据 |

**`effort` 改的是推理预算，不是模型。** 想换模型用 `model`。

**`model` 与 `effort` 不要同时传**——同时出现返回 `400`。两者都不传时按 `spark-1-pro` 处理（在旧模型体系下的默认值）。

结构化输出示例：

```python
class Founder(BaseModel):
    name: str = Field(description="创始人全名")
    role: Optional[str] = Field(None, description="职位")

class FoundersSchema(BaseModel):
    founders: List[Founder]

result = app.agent(prompt="找出这家公司的创始人", schema=FoundersSchema,
                   urls=["https://example.com/about"])
print(result.data)
```

**用 `maxCredits` 兜底。** Agent 是唯一一个花钱不确定性最高的接口，不设上限时可能为了一个模糊 prompt 抓很多页。把 prompt 写具体、把 `urls` 收窄、把 `strictConstrainToURLs` 打开，三者叠加比事后看账单有效得多。

---

## 八、`POST /v2/scrape/{scrapeId}/interact` —— 页面交互沙箱

先 scrape 拿 `scrapeId`，再在同一个会话上连续执行交互。适合必须先点开弹窗、翻页、填表单才能看到内容的页面。

```python
result = app.scrape("https://example.com/list")
scrape_id = result.metadata.scrape_id

app.interact(scrape_id, prompt="搜索 '机械键盘'")
app.interact(scrape_id, prompt="点击第一条结果")
```

```bash
curl -X POST 'https://api.firecrawl.dev/v2/scrape/<SCRAPE_ID>/interact' \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "搜索 mechanical keyboard"}'
```

返回：

```json
{
  "success": true,
  "output": "Keyboard available at $100",
  "liveViewUrl": "https://liveview.firecrawl.dev/..."
}
```

计费：**2–7 credits / 浏览器分钟**，不足一分钟按一分钟算。

| 会话类型 | 费率 |
|---|---|
| 带 `prompt` 的会话 | 7 credits / 浏览器分钟 |
| 不带 `prompt`（只有 Playwright `code`） | 2 credits / 浏览器分钟 |

相关路径还有 `/v2/browser/{sessionId}/execute`、`/v2/browser/{sessionId}/replay`（会话回放）。`/browser` 是 `/interact` 的别名。CLI 流程是 `firecrawl scrape <url>` 先出会话，再 `firecrawl interact "..."`。

---

## 九、Parse：本地文件解析

`POST /v2/parse` 处理文件而不只是 URL。带上传的流程：

1. `POST /v2/parse/upload-url` 拿上传地址。
2. 把文件传到该地址。
3. `POST /v2/parse`（或 `GET /v2/parse/upload/{uploadId}`）触发解析。

托管 MCP 的免密钥入口把 Parse 跟 Search、Scrape 一起开放，这是无 Key 可用的三个能力。

---

## 十、Webhook 与实时结果

不想轮询就配 webhook：

```json
{
  "url": "https://docs.example.com",
  "limit": 100,
  "webhook": {
    "url": "https://your-server.example.com/hooks/firecrawl",
    "events": ["crawl.page", "crawl.completed", "crawl.failed"]
  }
}
```

| 事件 | 何时触发 |
|---|---|
| `crawl.page` | 每成功抓取一页，payload 里带该页文档 |
| `crawl.completed` | 整个作业结束 |
| `crawl.failed` | 作业失败 |

**Webhook 请求必须验签**——上游提供了签名校验机制，收到 webhook 时先验证再信任内容，否则你的回调端点就是一个公开的数据注入入口。生产环境还要考虑重放、幂等与失败重试。

也可以连 WebSocket 实时收结果：`WS /v2/crawl/{jobId}`，路径与状态接口相同，协议从 HTTP 换成 WS。

---

## 十一、账号与运维端点

| 端点 | 用途 |
|---|---|
| `GET /v2/team/credit-usage` | 当前额度使用情况 |
| `GET /v2/team/credit-usage/historical` | 历史用量 |
| `GET /v2/team/token-usage`、`.../historical` | token 用量（AI 类能力） |
| `GET /v2/concurrency-check` | 查当前并发余量，提交大批量前必看 |
| `GET /v2/team/queue-status` | 队列排队状况。**排队时间会计入请求的 `timeout`**，所以可以用更低的 `timeout` 让它快速失败而不是干等 |
| `GET /v2/crawl/ongoing`、`GET /v2/crawl/active` | 列出进行中的 crawl 作业 |
| `POST /v2/scrape/{jobId}` 的 `GET` 版本 `/v2/scrape/{jobId}` | 查单个 scrape 作业状态 |

`/concurrency-check` + `/team/credit-usage` 是提交批量作业前的标准前置动作：前者告诉你有没有槽位，后者告诉你额度够不够。排队中的任务**最多等 48 小时**后超时。

---

## 十二、错误响应的统一结构

```json
{
  "success": false,
  "error": "人类可读的错误消息",
  "details": "（可选）逐字段的校验错误"
}
```

排查时**先用 `error` 字符串去错误码表定位原因**，再看 `details` 找具体哪个字段不合法。完整的错误码、成因、处置与是否可重试，见 `pitfalls.md` 第二节。
