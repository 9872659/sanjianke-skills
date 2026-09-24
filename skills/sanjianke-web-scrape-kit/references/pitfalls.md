# 反爬 · 限流 · 成本 · 常见错误

这份文件处理「已经跑起来但结果不对/账单不对」的问题。接口参数见 `api-playbook.md`，部署见 `quickstart.md`。

排查顺序建议固定为：**先看 HTTP 状态码 → 再看 `success` → 再看 `data.metadata.statusCode` → 最后看 `creditsUsed`**。四层信息串起来看，90% 的问题能当场定位。

---

## 一、反爬：为什么抓不到内容

### 1.1 代理是默认可用的，别自己再套一层

Firecrawl **默认就把所有请求走代理**，即使你不传 `proxy` 参数。自行在请求里塞代理配置通常是多余的，还可能让出口 IP 更可疑。

`proxy` 参数取三个值：

| 值 | 行为 |
|---|---|
| `basic` | 标准代理，够用于大多数站点 |
| `enhanced` | 增强代理，用于复杂站点 |
| `auto` | **推荐，也是默认值**。先用 `basic`，失败后自动用 `enhanced` 重试同一 URL |

`auto` 的**升级触发条件是目标站返回 `401`、`403` 或 `429`**——这三种被解释为「代理不够好」，于是换增强代理重试。**`404` 和 `5xx` 不触发升级**，因为换个代理也不会改变答案。

升级**每个请求最多发生一次**。已经在增强代理上还拿到 401/403/429，就直接把结果返回给你，不会无限重试。

**成本上不吃亏**：增强代理请求与基础代理同价，**1 credit/请求**。升级重试**不单独计费**——从 basic 起步、最终在 enhanced 上完成的请求仍然是 1 credit。

### 1.2 地理位置决定出口 IP

不指定时代理走 **US**。要指定就用 `location.country` 传两字母国家码，例如德国 `DE`：

```json
{
  "url": "https://example.com",
  "formats": ["markdown"],
  "location": { "country": "DE", "languages": ["de-DE"] }
}
```

同样是「网页内容」，不同出口国看到的可能是完全不同的价格、库存和页面语言。**跨国电商、票务、新闻站务必显式指定国家**，否则拿到的数据可能整体错位。

支持基础代理的国家较多（AE / AT / AU / BE / BR / CA / CH / CN / DE / DK / EG / ES / FR / GB / GR / IL / IN / IT / JP / MX / NL / PL / QA / SE / TR / US 等），但**增强代理目前只在 NL 与 US 可用**。这个名单会变，需要冷门地区时先确认当前支持情况。

### 1.3 动态渲染：先等，再操作

内容靠 JS 渲染时，按这个顺序加手段：

1. **`waitFor`** —— 智能等待之外的额外毫秒数，如 `"waitFor": 2000`。**这是最后手段**，因为它对每个请求固定加时延。先用智能等待，确实拿不到再加。
2. **`actions` 里的 `wait` + `selector`** —— 等某个具体元素可见，比盲等固定时长精准得多（超时 30 秒）。
3. **完整的 `actions` 序列** —— 点掉 Cookie 弹窗、滚动触发懒加载、点击「加载更多」、填搜索框回车。

```json
{
  "url": "https://example.com/list",
  "actions": [
    { "type": "click", "selector": "#accept-cookies" },
    { "type": "wait", "selector": ".product-card" },
    { "type": "click", "selector": "#load-more" },
    { "type": "wait", "milliseconds": 1500 }
  ],
  "formats": ["markdown"]
}
```

**actions 的两条硬约束**：单请求最多 **50 个动作**；所有 `wait` 加 `waitFor` 的累计等待**不能超过 60 秒**。超了请求直接失败。

**actions 与 PDF 互斥**：URL 最终解析成 PDF 时，带 actions 的请求会失败。

### 1.4 移动端布局差异

响应式站点在桌面端可能把内容藏起来，或者给移动端返回完全不同的结构。`mobile: true` 模拟移动设备：

```json
{
  "url": "https://example.com",
  "mobile": true,
  "location": { "country": "GB", "languages": ["en-GB"] },
  "formats": ["markdown", { "type": "screenshot", "fullPage": true, "viewport": { "width": 390, "height": 844 } }]
}
```

加了 `mobile: true` 站方仍给桌面布局时，在 `headers` 里补一个移动端 UA（如 iPhone Safari 的 UA 串）。

### 1.5 强反爬站：先诊断，别硬刚

遇到稳定 403 的排查顺序：

1. **看 `data.metadata.statusCode` 和 `data.metadata.error`。** 反复 403 就说明这个 URL 在这个配置下拿不到。
2. **确认是不是代理问题。** 如果请求没走 `auto`（默认值），显式改成 `auto` 让它有机会升级到增强代理。
3. **试 `location.country`** 换出口国家。部分站点按地区做访问控制。
4. **试 `mobile: true` + 移动 UA。**
5. **试加上 actions** 走完整浏览器路径。
6. **仍然 403 就停止重试这个 URL。**

第 6 步是重点：**页面返回 403 时 Firecrawl 依然把那个响应当成一份「文档」返回给你，所以照样计 1 credit。** 反复重试一个稳定 403 的 URL 就是纯粹烧钱。正确做法是读 `metadata.statusCode` 做判定，把这类 URL 记进黑名单跳过。

### 1.6 robots.txt 与合规红线

- **robots.txt 默认被遵守**。被拦下的 URL 会出现在 `GET /v2/crawl/{jobId}/errors` 的 `robotsBlocked` 数组里。
- `ignoreRobotsTxt` 和 `robotsUserAgent` 是**企业版专属**能力，普通档位用不了。
- crawl 默认**只跟随子路径**。要覆盖同级/上级路径用 `crawlEntireDomain`，要子域用 `allowSubdomains`，要外链用 `allowExternalLinks`（只跟一跳，且指向外站首页的链接会被有意跳过并记为 `EXTERNAL_LINK`）。

**合规责任在调用方**。抓取前确认目标站的使用条款、robots.txt 与所在地法规；涉及个人数据的场景评估是否需要 ZDR（零数据留存，+1 credit/页）或干脆不抓。需要登录态的页面必须自己有合法授权，本 Skill 不提供任何绕过登录的手段。

---

## 二、限流：429 与并发

### 2.1 先分清两种 429

| 报错 | 含义 | 处置 |
|---|---|---|
| `Rate limit exceeded` | 团队每分钟请求数超了 | 按 `Retry-After` 秒数退避后重试 |
| `Concurrency limit reached` | 并发作业数超了 | 等在飞作业结束、降低并发，或升级档位 |

**限流是按团队算的**——同一团队下所有 API Key 共享同一套计数器。你以为是「多开几个 Key 就能绕开」，其实不行。

「每分钟请求数」只用于防滥用，**真正的瓶颈是并发浏览器数**（同时能处理多少页面）。超过并发上限的作业会排队，**排队时间计入请求的 `timeout`**——所以设一个更低的 `timeout` 可以让它快速失败，而不是干等一个注定超时的结果。排队中的任务**最多等 48 小时后超时**。

### 2.2 并发与每分钟限额

| 档位 | 并发浏览器 | /scrape | /map | /crawl | /search | /agent | /crawl/status | /agent/status |
|---|---|---|---|---|---|---|---|---|
| Free | 2 | 10 | 10 | 2 | 10 | 2 | 500 | 500 |
| Hobby | 5 | 100 | 100 | 20 | 100 | 20 | 5000 | 5000 |
| Standard | 25 | 500 | 500 | 100 | 500 | 100 | 25000 | 25000 |
| Growth | 50 | 5000 | 5000 | 1000 | 5000 | 1000 | 250000 | 250000 |
| Scale | 100+ | 10000 | 10000 | 2000 | 10000 | 2000 | 500000 | 500000 |

几个容易忽略的归属规则：

- **`/extract` 系列与 `/agent` 共用限额。**
- **`/batch/scrape` 系列与 `/crawl` 共用限额。**（所以批量抓取的每分钟上限远低于单页抓取，这是最常见的意外限流来源。）
- **浏览器沙箱**另有独立限额，Free 档 `/interact` 只有 2 次/分钟，`/interact/{id}/execute` 10 次/分钟；Hobby 为 20 / 100；Standard 为 100 / 500；Growth 为 1000 / 5000；Scale 为 1500 / 7500。并发浏览器会话数也同样受限，超了返回 429 直到旧会话销毁。

**无 Key（Keyless）模式**：按 IP 计算，同时限制**每日请求数**和**每日 credits 消耗**，任一超限返回 429。而且它只开放 Search、Scrape、Parse（官方 SDK/CLI 下额外有 Interact），**crawl、extract、map、batch scrape 一律不可用**。

**最大排队作业数**：Free/Hobby/Standard 均为 50000，Growth 为 100000，Scale/Enterprise 为 200000+。自定义并发档位的上限是「并发数 × 2000」，封顶 200 万。超了直接 429，直到已有作业完成。

### 2.3 退避重试的正确写法

**可重试**：`408`、`429`、`500`、`502`、`503`、`504`
**不可重试**：`400`、`401`、`402`、`403`、`404`、`409`、`413`
**看情况**：`422`（schema 或模型产出问题，改完再试）

```javascript
const RETRYABLE = new Set([408, 429, 500, 502, 503, 504]);

async function callWithBackoff(fn, maxAttempts = 5) {
  let delay = 1000;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const status = err?.status ?? err?.response?.status;
      if (!RETRYABLE.has(status) || attempt === maxAttempts) throw err;

      // 429 优先听服务端的 Retry-After
      const retryAfter = Number(err?.response?.headers?.['retry-after']);
      const wait = Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : delay;

      await new Promise((r) => setTimeout(r, wait));
      delay = Math.min(delay * 2, 60000);   // 指数退避，封顶 60s
    }
  }
}
```

要点：

- **加上随机抖动**（`wait * (0.5 + Math.random())`），否则多进程同时退避会在同一时刻一起重试，把限流踩得更死。
- **异步作业提交失败时不要重复提交。** crawl / batch / agent 支持幂等键，但更稳的做法是先在本地记录「已提交的请求指纹 → jobId」，重试时先查 jobId 而不是重新 POST。
- **`402` 绝不重试。** 它是额度耗尽，重试一万次也是 402，正确动作是开启按量付费或升级档位。

### 2.4 提交批量作业前的两个前置调用

```bash
# 1. 还有没有并发槽位
curl -s -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/concurrency-check

# 2. 还有多少额度
curl -s -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/team/credit-usage

# 3. 队列排得多长（决定要不要等）
curl -s -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/team/queue-status
```

养成习惯：**批量作业前先跑这三个**，比事后从日志里反推限流原因便宜得多。

---

## 三、成本：credits 到底花在哪

### 3.1 计费单价表

| 项目 | 单价 |
|---|---|
| Scrape | 1 credit / 页 |
| Crawl | 1 credit / 页（每页都按 scrape 规则，附加费同样叠加） |
| Map | 1 credit / 次调用 |
| Search | 2 credits / 10 条结果，**向上取整**（1–10 条 = 2，11–20 条 = 4） |
| Interact | 2–7 credits / 浏览器分钟，不足一分钟按一分钟算 |
| Interact 带 `prompt` | 7 credits / 浏览器分钟 |
| Interact 不带 `prompt`（只有 Playwright `code`） | 2 credits / 浏览器分钟 |

### 3.2 附加费会叠加

| 附加项 | 加价 |
|---|---|
| PDF 解析 | +1 credit / PDF 页 |
| JSON format（LLM 抽取） | +4 credits / 页 |
| Prompt 注入检测（`checkPromptInjection`） | +4 credits / 页；检测跑完后即使抓取失败也计 5 credits |
| 零数据留存（ZDR） | +1 credit / 页 |
| 威胁防护扫描 | 2 credits / 被扫描的 URL（**包括被扫描自己拦下的抓取**） |
| `lockdown` 缓存未命中 | 1 credit |

**叠加是累加的**：JSON format + ZDR 抓一页 = `1 + 4 + 1 = 6 credits`。同一套规则适用于 crawl 与 search 里内嵌的每一次 scrape。

### 3.3 什么时候扣费，什么时候不扣

**扣费**：

- **返回了文档就扣 1 credit/页**，外加上面的选项费。**目标站返回 403 Forbidden 或 404 Not Found 也算**——目标站应答了，Firecrawl 抓到了那个响应，并且把它作为文档返回给你。
- 因此**必须查 `metadata.statusCode`**，把稳定报错的 URL 从重试队列里摘掉。

**不扣费**：

- **没有返回任何文档 = 0 credits。** 彻底失败的抓取（站点始终无响应、所有渲染尝试都失败）不收费。
- **轮询状态、查批量进度、读 `/errors` 都不消耗 credits。**

个别例外：Monitor 检查中出错的页面仍按基础 1 credit/页计。

### 3.4 批量与 crawl 的计费是异步的

`/batch/scrape` 与 `/crawl` 的 credits 是**每页处理完成时**异步扣除的，**不是提交时一次性扣**。这意味着：

- 提交作业和账面上看到完整消耗之间**有延迟**。
- 批量任务大、或赶上高流量排队时，credits 可能在提交后**几分钟甚至几小时**才陆续出现。

所以不要以为「刚提交时没扣费 = 这次免费」。

### 3.5 crawl 的额度预检行为

这块最容易产生「额度被打光了我还不知道」的意外：

- **显式传了 `limit` 时**：Firecrawl 按这个数量做额度校验。**校验通过（含按量付费兜底）后，limit 不会被削减到你的剩余额度。** 校验不通过时，它会尝试把 limit 降到剩余额度再校验一次；如果降到没有正数可用，或者降完仍不通过（含被单 Key 消费上限拦下），返回 `402`。
- **不传 `limit` 时**：预检**只按 1 credit** 做，不会为整站预留。请求通过后**默认上限 10000 页也不会被削到余额以内**——页面处理一页算一页的钱。

结论：**`limit` 永远显式写。** 不写就等于让一个预检只花 1 credit 的请求，拥有刷掉 10000 页额度的权限。

### 3.6 省钱清单

按投入产出比排序：

1. **非实时场景一定带 `maxAge`（非零）**。默认 2 天缓存命中直接秒回，最快可提速到 5 倍。文档、文章、商品页、批量入库全部适用。只有股价、比分、突发新闻才用 `maxAge: 0`。
2. **先 `/map` 再 `/crawl`**。1 credit 换一份完整 URL 清单，据此精确配置 `includePaths` / `excludePaths`，避免抓一堆法律条款页和标签页。
3. **`limit` 显式设小**，确认覆盖面够了再逐次放大。
4. **`sitemap: "skip"` 要慎用**。它只看 HTML 链接，sitemap-only 的页面（PDF、深层嵌套页）会被漏掉——省了钱但少了数据。要省钱且站点 sitemap 完整，用 `sitemap: "only"` 更划算。
5. **不需要 PDF 解析就把 `parsers` 设成 `[]`**，避免为 PDF 页额外付 +1/页。
6. **商品页优先用 `product` format**，它不加 credits 也不需要 schema；只有自定义字段才上 `json`（+4/页）。
7. **`/search` 先拿列表再决定抓几条**。一步抓 10 条 = 10 页的抓取成本，其中一半可能是噪音。
8. **搜索结果不理想就提交反馈**。`POST /v2/search/{jobId}/feedback`，**每个搜索作业的首次反馈可退 1 credit**（受团队限制约束）。
9. **给 `/agent` 设 `maxCredits`**。默认 2500，是花钱不确定性最高的接口。控制台最高支持 2500，更高的值只能走 API 传，且**超过 2500 一律按付费请求计费**。
10. **把 403/404 的 URL 记进黑名单**，别让它们在三轮重试里反复计费。

### 3.7 额度耗尽与免费档

- 免费档：**每月 1000 credits**，月初重置，**不结转**，2 并发浏览器，**不含按量付费**——额度用尽后请求返回 **402**。所有核心接口在免费档都可用，credits 单价与付费档完全相同。
- 付费档支持按量付费：余额归零时自动加**一档 5 美元的 credits** 并扣卡。这需要**已付费的自助档位**，免费档用不了。
- 也可以随时手动买：控制台的 **Load more credits**，输入 5 美元的整数倍。
- **结转规则**：默认不结转。例外是 **Scale 年付结转 1 个月**、**Enterprise 年付结转 2 个月**。月付与年付的 credits 都是**每月**重置（年付按虚拟的月度续订日重置）。
- **升级立即生效，不按比例折算**：当天收全新档位的整月/整年费用，计费周期重置；旧档位未用完的 credits 会带过来。

---

## 四、错误码对照表

统一响应结构：

```json
{ "success": false, "error": "错误消息", "details": "（可选）逐字段校验错误" }
```

| HTTP | 典型 `error` | 成因 | 处置 | 可重试 |
|---|---|---|---|---|
| 400 | `Bad Request` / 校验消息 | 请求体没过 schema（字段缺失或非法） | 按接口文档修 payload，看 `details` 定位字段 | 否 |
| 400 | `Invalid URL` | `url` 缺失、格式错，或用了不支持的 scheme | 传绝对的 `http(s)://` URL | 否 |
| 401 | `Unauthorized: Invalid token` | Key 缺失、格式错或已吊销 | 带上 `Authorization: Bearer fc-...`，用有效 Key | 否 |
| 402 | `Payment Required: Insufficient credits` | 额度耗尽或未配置计费 | 开按量付费，或升级档位 | 否 |
| 403 | `Forbidden` | Key 没有该接口/功能的权限 | 换有对应权限的 Key，或升级门控该功能的档位 | 否 |
| 403 | `SCRAPE_PROMPT_INJECTION_DETECTED` | 开了 `checkPromptInjection`，在被抓页面里检出提示注入，抽取被中止 | 人工看页面内容；确认是误报就去掉该开关重试 | 否 |
| 404 | `Not Found` | jobId、资源或路径不存在 | 核对资源 ID 与接口路径 | 否 |
| 408 | `Request Timeout` | 页面加载超过了请求的 `timeout` | 调大 `timeout`、精简 actions，或用 `fastMode` | **是**（退避） |
| 409 | `Conflict` | 资源状态不允许该操作（如已删除） | 重新拉状态对齐后再操作 | 否 |
| 413 | `Payload Too Large` | 请求体超过上限 | 缩小 payload：schema 写短些、每批 URL 少些 | 否 |
| 422 | `Unprocessable Entity` / 抽取 schema 错误 | schema 不是合法 JSON Schema，或模型产不出符合结构的结果 | 校验 schema、放宽 `required`，或换 `model` | 有时 |
| 429 | `Rate limit exceeded` | 团队每分钟请求数超限 | 按 `Retry-After` 退避重试 | **是**（退避） |
| 429 | `Concurrency limit reached` | 并发浏览器数达到档位上限 | 等在飞作业结束、降并发，或升级 | **是**（退避） |
| 500 | `Internal Server Error` | 服务端未处理异常 | 指数退避重试；持续出现就带上 request ID 反馈 | **是**（退避） |
| 502 | `Bad Gateway` | 上游代理或 worker 返回了无效响应 | 退避重试 | **是**（退避） |
| 503 | `Service Unavailable` | 服务暂时无法处理 | 退避重试 | **是**（退避） |
| 504 | `Gateway Timeout` | 超过网关超时（多见于长 crawl） | **改用异步的 crawl / batch 接口 + 轮询**，不要死磕同步接口 | **是**（退避） |

### `/agent` 专属错误

| HTTP | 错误 | 处置 |
|---|---|---|
| 400 | `Invalid job ID format. Job ID must be a valid UUID.` | `jobId` 路径段不是 UUID，用 `POST /v2/agent` 返回的 `id` |
| 400 | `Invalid snapshot ID` | 用 trace 事件里 `artifact.updated` 给的 `snapshotId` |
| 400 | `Trace is only available for Spark 2 extracts` | 该作业早于 Spark 2。新作业都在 `spark-2` 上跑，自带 trace |
| 400 | `Snapshots are only available for Spark 2 extracts` | 同上 |
| 400 | `Your team has zero data retention enabled...` | 强制 ZDR 的团队不能跑 extract/agent，需要联系服务方解除 |
| 404 | `Agent job not found` | jobId 不存在，或属于别的团队。用发起该作业的那个团队的 Key 查 |
| 404 | `Snapshot not found` | 重新拉 trace，用当前有效的 `snapshotId` |
| 409 | `Agent already finished` | 对已终态的作业调 cancel。改为轮询 `GET /v2/agent/{jobId}` |
| 409 | `Agent is already cancelled` | 重复取消。取消后的作业报 `failed` 并带取消消息 |
| 500 | `Failed to passthrough agent request.` | 提交时被 agent 服务拒收。退避重试；持续出现带上 request ID |

### Agent 作业的终态原因码

| `code` | 含义与处置 |
|---|---|
| `cancelled` | 你主动取消的。要重做就重新发起 |
| `credit_limit_reached` | 撞上了 `maxCredits` 上限。提高 `maxCredits`，或把 prompt 收窄降低工作量 |
| `parent_finished` | 子 agent 因为派生它的父 agent 先结束而停止。去看父 agent 自己的终态事件找真实原因 |
| `refused` | agent 拒绝执行任务。改写 prompt，或把它限定在你确实有权采集的 URL 上 |
| `internal` | 运行内部意外失败。重试；持续出现带上 jobId |

---

## 五、结果异常排查

### 5.1 「抓完了但页面少了」

**先接受一个事实：`completed == total` 不代表全成功。** `total` = completed + 在飞页数（active + queued + backlogged），**不统计失败页**。终态下在飞数必然归零，所以两个计数器一定相等，跟有没有失败页毫无关系。

失败页**只能**从 `GET /v2/crawl/{jobId}/errors` 读：

- `errors`：`id`、`url`、`error`、`timestamp`。网络错误、超时都在这里；被有意跳过的外站首页记为 `EXTERNAL_LINK`。
- `robotsBlocked`：被 robots.txt 拦下的 URL。

而且这份清单**不保证完备**——某些内部失败类别在构造响应前就被过滤掉了。把它当「上游报告了哪些失败」，不是「没有别的问题」的证明。

另外注意：**目标站返回 404 的页面不算 crawl 错误**。它被成功抓到了，会带 `metadata.statusCode: 404` 出现在 `data` 里。

### 5.2 「配了 includePaths 却一页都没抓」

按可能性排序：

1. **起始 URL 自己没过 `includePaths`。** 起始 URL 也要参与匹配，不匹配时整个 crawl 可能返回 0 页。这是头号原因。
2. **写法不是路径名而是完整 URL。** `includePaths` 匹配的是 **pathname**，不含域名、不含查询串。要匹配完整 URL 得开 `regexOnFullURL: true`。
3. **用了 RE2 不支持的正则。** 环视（`(?=...)`、`(?<!...)`）和反向引用都不支持，编译不过会直接 `400`，不会静默忽略。
4. **关键词拼成了长 alternation。** 请一个词一条短模式：`["pricing","docs","blog"]`。
5. **默认只跟子路径。** `website.com/other-parent/blog-1` 不在 `website.com/blogs/` 的子路径下，要 `crawlEntireDomain`。

### 5.3 「`next` 一直存在，循环停不下来」

`next` **不是**「还有更多数据」的纯信号。**只要 `status` 不是 `completed`，响应就会带 `next`**——终态的 `failed` 或 `cancelled` 作业也会有。拿 `next` 是否存在当退出条件，在失败或取消的作业上会死循环。

正确读法：

1. 轮询 `GET /v2/crawl/{jobId}` 直到 `status` 是 `completed` / `failed` / `cancelled`。
2. 在 `next` 存在 **且** 上一页 `data` 非空时，跟着 `next` 继续取。
3. `next` 消失，或某页没有新文档时停止。

响应体上限 **10MB**，超了才分页。官方 SDK 会自动处理分页，一次性返回全部结果——这是用 SDK 而不是裸 HTTP 的主要理由之一。

### 5.4 「同一份配置每次结果都不一样」

页面是并发抓的，链接发现顺序取决于网络时序和哪一页先加载完，所以每轮在不同分支上的覆盖深度会漂移，`maxDiscoveryDepth` 越大越明显（`data` 数组还是按**完成时间**而非发现顺序排的）。

想更可复现：

- **`maxConcurrency: 1`**（或设 `delay`，它会强制并发为 1）。能削弱时序交织，但**不能消除**波动：sitemap 发现是在并发上限之外入队的，嵌套 sitemap 作为独立作业抓取。
- **站点 sitemap 完整时用 `sitemap: "only"`**，让 URL 集合来自 sitemap 而不是链接发现。

### 5.5 「结果读不到了」

- **作业完成后结果只在 API 上保留 24 小时**，过期只能去控制台看日志。
- **截屏 URL 24 小时过期。**
- **音频/视频返回的签名 URL 1 小时过期。** 要长期保存必须在这一小时内转存到自己的存储。

### 5.6 超时排查

`timeout` 默认 **60000 ms**，最小 **1000 ms**。超时后的动作：

| 场景 | 处置 |
|---|---|
| 单页超时（408） | 调大 `timeout`；精简 actions；确需快速返回时试 `fastMode` |
| 长 crawl 超时（504） | **改用异步 `/crawl` + 轮询状态**，别用同步接口硬等 |
| 自托管 curl 超时 | curl 的 `--max-time`（秒）要设得比请求体的 `timeout`（毫秒）长，好让 API 有机会返回它自己的超时响应 |
| 排队导致超时 | 排队时间**计入**请求 `timeout`。用 `/team/queue-status` 看排队情况，或主动调低 `timeout` 快速失败 |

```
规则：请求体 timeout 是毫秒；curl --max-time 是秒；后者 > 前者。
```

### 5.7 抽取结果不符预期

- **`422`** —— schema 不是合法 JSON Schema，或模型产不出符合结构的结果。放宽 `required`、减少嵌套层级，或换 `model`。
- **商品页拿不到干净字段** —— 优先用免 LLM 的 `product` format，它是确定性的、不需要 schema。
- **正文里混着导航和页脚** —— `onlyMainContent` 默认是 `true`，若你关掉过就打开；还不够就用 `excludeTags` 精确剔除（如 `["#ad","#footer","[role=\"banner\"]"]`）。
- **`includeTags` / `excludeTags` 不生效** —— 它们作用在**原始 DOM** 上，不是过滤后的结果上。选择器要按源 HTML 写。用整页作起点时把 `onlyMainContent` 设成 `false`。
- **`rawBase64` 报错** —— 它**必须单独使用**，与其它 format 同时出现会被拒。它返回裸 Base64 串（不是 data URI），MIME 从 `metadata.contentType` 读，且只含该 URL 一个文件、不含子资源。
- **`changeTracking` 失败** —— 它**要求 formats 里同时有 `markdown`**。
- **`screenshot` 失败** —— 单请求最多一张，viewport 上限 7680×4320。

---

## 六、自托管专属坑

| 症状 | 原因与处置 |
|---|---|
| 截屏/actions 报不支持 | **默认自托管栈不含 Fire-engine**，fetch 与 Playwright 都报不支持。要这些能力只能走云端，或自行单独部署配置 Fire-engine |
| `/agent`、interact、商品/菜单/音视频 format 不可用 | 这些能力主要面向云端，自托管下需自行确认外部服务依赖 |
| `json` 抽取、`summary` 报错 | 自托管**默认没有配置任何模型提供方**。自行接入 OpenAI 兼容端点或 Ollama，并**单独验证这条路径** |
| 数据在重建服务后丢了 | Compose 文件**没有**给 NuQ PostgreSQL、Redis、RabbitMQ 定义持久卷。要数据活着就自己加卷，并演练备份恢复 |
| API 裸奔在公网上 | 默认 **`USE_DB_AUTHENTICATION=false` 即无鉴权**，且只发布 `3002` 一个端口。放公网前必须补鉴权、TLS、网络策略 |
| 服务莫名退出 | `docker compose ps --all` + `docker compose logs --tail=200`；确认源码版本是既定 release；确认资源充足 |
| 容器连不上 Redis | 必须用 Compose 网络内地址 `redis://redis:6379`；容器里的 `localhost` 指向容器自己。删掉任何 `REDIS_URL` / `REDIS_RATE_LIMIT_URL` 覆盖 |
| PostgreSQL 起不来 | 检查 `.env` 语法；`POSTGRES_DB` 必须是 `postgres`（该版本 `pg_cron` 指向这个库）；用户名口令在 API 与 DB 两侧要一致 |
| 探活 OK 但 scrape 失败 | 探活**不校验** Redis/PostgreSQL/RabbitMQ/Playwright/worker/出网。看 `docker compose logs --tail=200 api playwright-service` |
| `3002` 无响应 | `docker compose ps api` + 日志；端口被别的进程占了就停掉它或同步改发布端口；API 状态为 running 后再重试 |

**别做的三件事**：不要用 `main` 分支或浮动镜像 tag 部署（配置会漂）；不要把 `apps/api/.env.example` 当作 Compose 的配置契约（那是开发用的）；不要在没设强 `BULL_AUTH_KEY` 和网络限制的情况下打开队列管理 UI。

---

## 七、上线前复核

- [ ] 所有 403/404 的 URL 已记入黑名单，不在重试队列里反复烧 credits。
- [ ] 只对 408/429/500/502/503/504 做退避重试，退避带随机抖动。
- [ ] `402` 的处置路径是开按量付费或升级，不是重试。
- [ ] 批量作业前调过 `/concurrency-check` 与 `/team/credit-usage`。
- [ ] 非实时抓取都带了非零 `maxAge`。
- [ ] 每个 crawl 都显式写了 `limit`。
- [ ] 读结果用的是 `status` 终态 + `next` 且 `data` 非空的双条件。
- [ ] 每次批量结束都读了 `/errors` 核对失败页。
- [ ] 截屏和音视频的签名 URL 在过期前已转存。
- [ ] `/agent` 都设了 `maxCredits`。
- [ ] 目标站条款、robots.txt 与所在地区法规已确认；个人数据场景评估过 ZDR。
- [ ] 自托管部署未误用需 Fire-engine 的能力，公网暴露前已补鉴权与 TLS。
