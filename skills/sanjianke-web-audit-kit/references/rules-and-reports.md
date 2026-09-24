# 规则分类与报告解读

本文解决两个问题：**规则到底分哪几类**（以及怎么按类裁剪），**报告上每个数字是什么意思**（以及怎么不被它误导）。安装与首次运行见 `install-and-first-audit.md`，接 CI 与修复流程见 `ci-and-fix-loop.md`。

---

## 一、先说清一件事：规则条数有三种口径

同一个项目在不同出口写了不同的数字，这不是笔误，是文案没跟版本同步：

| 出处 | 口径 |
|---|---|
| npm 包描述 | 260+ |
| 官网支持页 | 260+ |
| 首页宣传语 | 270+ |
| 文档站规则页 | 295 条 |

**别把任何一个数字当硬指标。** 规则集跟着版本涨，你装的那一版才是真的。以本地为准：

```bash
squirrel self version                 # 你装的是哪一版
squirrel config show                  # 当前生效的规则开关
squirrel audit <url> --rule-include core -f json -o /tmp/core.json   # 单类实际跑了多少条
```

---

## 二、两层分类：4 个评分组 + 20 多个类别

squirrelscan 的分类是**两层**，理解这点才能真正读懂报告：

- **第一层是评分组（group）**，只有 4 个，报告顶部那四个分数就是它们：**SEO / Performance / Security / Agents**。
- **第二层是类别（category）**，20 多个，每个类别归属唯一一个分组。规则 id 的写法是 `<类别>/<规则名>`，例如 `core/meta-title`、`content/word-count`、`images/alt-text`。

**类别不是报告的顶层章节**——报告是按「严重度」排的，一个既有 error 又有 warning 的类别会同时出现在两个严重度下面。这点后面还会再说。

### 分组 → 类别归属

| 评分组 | 管什么 | 包含的类别 |
|---|---|---|
| **SEO** | 能不能被抓到、被读懂、被收录、被信任 | `crawl` 可抓取性、`core` 核心 SEO、`links` 链接、`content` 内容、`schema` 结构化数据、`images` 图片、`social` 社交分享、`a11y` 无障碍、`mobile` 移动端、`url` URL 结构、`i18n` 国际化、`eeat` E-E-A-T、`local` 本地 SEO、`video` 视频、`analytics` 统计埋点、`gaps` 关键词/内容缺口 |
| **Performance** | 页面加载快不快 | `perf` |
| **Security** | 传输安全、被挂马、合规、被拦截 | `security` 传输与安全头、`integrity` 站点完整性（入侵特征）、`legal` 法律合规、`adblock` 被广告拦截器屏蔽 |
| **Agents** | AI Agent 能不能读、能不能操作 | `ax` Agent 体验、`ai` AI 可解析性 |

---

## 三、类别代码速查（`--rule-include` / `--rule-exclude` 用）

`--rule-include` / `--rule-exclude` 吃的是**类别代码或完整规则 id**。裸写类别名会自动展开成整类（`ax` → `ax/*`）：

```bash
squirrel audit <url> --rule-include ax,perf              # 只跑 Agent 体验 + 性能
squirrel audit <url> --rule-exclude images,social        # 除了图片和社交都跑
squirrel audit <url> --rule-include core/meta-title      # 只跑一条规则
squirrel audit <url> --rule-include ax --rule-include perf   # 可重复，也可逗号分隔
```

| 代码 | 中文 | 代表规则 |
|---|---|---|
| `crawl` | 可抓取性 | `crawl/robots-txt`、`crawl/sitemap-exists`、`crawl/sitemap-coverage`、`crawl/redirect-chain`、`crawl/soft-404`、`crawl/indexability` |
| `core` | 核心 SEO | `core/meta-title`、`core/meta-description`、`core/canonical`、`core/h1`、`core/og-tags`、`core/title-unique`、`core/charset` |
| `links` | 链接 | `links/broken-links`、`links/broken-external-links`、`links/orphan-pages`、`links/anchor-text`、`links/redirect-chains`、`links/https-downgrade` |
| `content` | 内容 | `content/word-count`、`content/duplicate-title`、`content/heading-hierarchy`、`content/reading-level`、`content/hidden-text`、`content/mojibake`、`content/placeholder-text` |
| `schema` | 结构化数据 | `schema/json-ld-valid`、`schema/article`、`schema/product`、`schema/faq`、`schema/breadcrumb`、`schema/entity-identity` |
| `images` | 图片 | `images/alt-text`、`images/dimensions`、`images/modern-format`、`images/srcset`、`images/image-file-size`、`images/broken-images` |
| `social` | 社交分享 | `social/og-image-size`、`social/og-url-match`、`social/social-profiles`、`social/asset-divergence` |
| `a11y` | 无障碍 | `a11y/color-contrast`、`a11y/button-name`、`a11y/form-labels`、`a11y/landmark-regions`、`a11y/tabindex`、`a11y/aria-roles` |
| `mobile` | 移动端 | `mobile/viewport`、`mobile/tap-targets`、`mobile/font-size`、`mobile/horizontal-scroll`、`mobile/interstitials` |
| `url` | URL 结构 | `url/length`、`url/hyphens`、`url/lowercase`、`url/trailing-slash`、`url/parameters`、`url/slug-convention` |
| `i18n` | 国际化 | `i18n/lang-attribute`、`i18n/hreflang` |
| `eeat` | E-E-A-T | `eeat/author-byline`、`eeat/content-dates`、`eeat/about-page`、`eeat/contact-page`、`eeat/privacy-policy`、`eeat/affiliate-disclosure` |
| `local` | 本地 SEO | `local/nap-consistency`、`local/geo-meta`、`local/service-area` |
| `video` | 视频 | `video/video-accessible`（字幕轨）、VideoObject 相关检查 |
| `analytics` | 统计埋点 | `analytics/gtm-present`、`analytics/consent-mode` |
| `gaps` | 关键词 / 内容缺口 | `gaps/keywords`、`gaps/content`（需云端实时搜索数据，默认不跑） |
| `perf` | 性能 | `perf/lcp-hints`、`perf/cls-hints`、`perf/ttfb`、`perf/render-blocking`、`perf/dom-size`、`perf/js-file-size`、`perf/compression` |
| `integrity` | 站点完整性 | `integrity/template-discontinuity`、`integrity/brand-impersonation`、`integrity/obfuscated-script`、`integrity/cloaking`、`integrity/kit-signature` |
| `security` | 传输与安全头 | `security/https`、`security/hsts`、`security/csp`、`security/x-frame-options`、`security/mixed-content`、`security/leaked-secrets`、`security/cookie-flags` |
| `legal` | 法律合规 | `legal/privacy-policy`、`legal/cookie-consent`、`legal/terms-of-service`、`legal/subprocessor-disclosure` |
| `adblock` | 被广告拦截器屏蔽 | `adblock/element-hiding`、`adblock/blocked-links`、`adblock/privacy-blocked` |
| `ax` | Agent 体验 | `ax/llms-txt`、`ax/agents-md`、`ax/ai-crawlers`、`ax/content-without-js`、`ax/token-weight`、`ax/markdown-response`、`ax/well-known-agent` |
| `ai` | AI 可解析性 | `ai/llm-parsability`、`ai/site-metadata`、`ai/page-type-match` |

> 未知类别名会在爬取前直接报错，并把合法代码列出来——这是好事，省得你白跑一趟。
> `--rule-include` 是**替换**本次要跑的类别；`--rule-exclude` 是在原本该跑的基础上**追加**跳过。

### 几个常用的裁剪配方

```bash
# SEO 回归专项（发版改动通常影响这几类）
squirrel audit <url> --rule-include crawl,core,links,content,schema

# 无障碍整改专项
squirrel audit <url> --rule-include a11y,mobile

# 上线前安全体检
squirrel audit <url> --rule-include security,integrity,legal

# 「我们的站要给 AI 读」专项
squirrel audit <url> --rule-include ax,ai

# 性能专项（后端 / 前端发版后各跑一次）
squirrel audit <url> --rule-include perf

# 比全量快得多：跳过最重的图片和社交
squirrel audit <url> --rule-exclude images,social
```

---

## 四、健康分怎么算

健康分是 0~100，公式（官方给出）：

```
基础分   = (挣到的权重 / 总权重) × 100
曲线分   = 基础分 ^ 1.2
密度扣分 = 问题单元超过 10 个后生效，最多 -45%
最终分   = 曲线分 × 各项惩罚乘数 × 密度惩罚乘数
```

三个要点：

1. **每条规则有权重（1~10）**，权重反映重要程度，不是每条规则等值。
2. **warning 只算 0.5 分**，不是 0 分也不是 1 分。
3. **曲线是指数放大的**（^1.2），越高分越难再往上爬——这是刻意设计的「奖励完美」。

**问题单元（issue unit）是体积感知的**：一条失败检查会按它标记的**元素个数**计数。某页 40 个按钮没有可访问名称 ≈ 40 个单元，不是 1 个。但每个检查、每页都有上限，所以单个烂页不会把分数打到 0。warning 每个检查只计一次。

密度扣分**同时作用于总分、每个分组分、每个分类分**，各自按自己那份计数独立计算。所以「分组分 100 而总分 D」这种自相矛盾的情况不会出现。

### 爬取类硬扣分（只作用于总分）

| 问题 | 扣分 | 对应规则 |
|---|---|---|
| 没有 robots.txt | -15% | `crawl/robots-txt` |
| robots.txt 屏蔽全站 | -50% | `crawl/robots-txt` |
| 没有 sitemap | -20% | `crawl/sitemap-exists` |
| 问题密度过高 | 最多 -45% | 任意规则（10+ 问题单元后生效） |

惩罚是**相乘**的。举例：基础 80 分、缺 robots.txt 又缺 sitemap：

```
80 × (1 - 0.15) × (1 - 0.20) = 80 × 0.85 × 0.80 = 54.4
```

这也是为什么**「没做 sitemap 和 robots.txt」的站分数会突然塌一档**——不是规则误判，是硬扣分。

### 分级

| 分数 | 等级 |
|---|---|
| 90-100 | A |
| 80-89 | B |
| 70-79 | C |
| 60-69 | D |
| 0-59 | F |

分组分用同一套公式与曲线，但**爬取类硬扣分只影响总分**，不影响分组分。

---

## 五、问题的排序规则

所有输出格式里，问题的顺序是一致的，**列表最上面就是最该动手的**：

1. **严重度**：errors → recommendations → warnings。
2. **类别**：同一严重度内，同类别的排在一起，优先级高的类别在前。
3. **规则权重**：同类别内，权重高的规则在前。

记住这点很重要：**不要从上往下照着修，要看第二层分类**。同一类别的三条 error 一起改，比跨三个类别各修一条省力得多。

---

## 六、7 种输出格式怎么选

| 格式 | 参数 | 给谁用 |
|---|---|---|
| `console` | 默认 | 人在终端看；有颜色、有分类进度条、有受影响页面 |
| `text` | `-f text` | 无颜色无格式，进日志、邮件、文本编辑器、`grep` |
| `json` | `-f json` | **CI/CD 与程序化处理**；门禁表达式、趋势追踪、喂监控 |
| `html` | `-f html` | 可视化报告，浏览器直接打开；含总分 + 4 个分组分 + 技术栈 |
| `markdown` | `-f markdown` | 进仓库 README、PR 描述、技术文档 |
| `xml` | `-f xml` | 冗长结构化 XML，企业集成与归档 |
| `llm` | `-f llm` | **编码 Agent 专用**，混合 XML/文本结构 |

`audit` 和 `report` 两个命令都支持全部 7 种。

### llm 格式为什么值得单独说

它是给模型省钱用的：比冗长 XML **小 40%~70%**（官方给的例子是 51 页审计 125KB vs 209KB）。压缩手法是「1 空格缩进 + 属性内联 + `Desc:`/`Fix:`/`Pages (n):` 前缀 + 逗号分隔列表」。

结构大致是这样（截断示意）：

```xml
<audit version="0.0.13">
<site url="https://example.com" crawled="42" date="2025-01-18T10:30:00Z"/>
<score overall="87" grade="B">
 <cat name="Core SEO" score="100"/>
 <cat name="Links" score="85"/>
</score>
<summary passed="83" warnings="13" failed="9"/>
<issues>
 <rule id="images/alt-text" severity="error" category="Images" group="seo" status="fail">
  Desc: 所有图片都要有描述性 alt 文本
  Fix: 给 img 标签补 alt 属性
  Items (6):
   - /products/widget.png (from: /products)
 </rule>
</issues>
<locked-rules count="7" audience="anonymous-upsell">
 ...未跑的云端规则，带解锁提示...
</locked-rules>
</audit>
```

**`<locked-rules>` 是最容易被忽略的一段**：它列出本次审计因为「未登录 / quick 档 / credits 不足」而**根本没跑**的检查。看到它就别把这次分数当成完整体检结果——那是「跑过的那部分」的分数。

---

## 七、JSON 报告的字段怎么读

```json
{
  "baseUrl": "https://example.com",
  "crawledAt": "2026-01-17T00:00:00Z",
  "totalPages": 42,
  "healthScore": {
    "overall": 87,
    "groups": [
      { "group": "seo", "name": "SEO", "score": 94,
        "passed": 120, "warnings": 8, "failed": 2, "total": 130 }
    ],
    "categories": [
      { "category": "core", "name": "Core SEO", "score": 100,
        "passed": 45, "warnings": 0, "failed": 0, "total": 45 }
    ],
    "errorCount": 9,
    "warningCount": 13,
    "passedCount": 83
  },
  "ruleResults": [
    {
      "id": "content/word-count",
      "name": "Word Count",
      "category": "content",
      "severity": "warning",
      "checks": [
        { "name": "min-words", "status": "fail",
          "message": "Low word count: 150 words (min: 300)",
          "pages": ["/blog/post-1", "/blog/post-2"] }
      ]
    }
  ]
}
```

取数时的三个惯例：

- **看总分用 `healthScore.overall`，看趋势用 `healthScore.groups[].score`**（四个分组分比总分更能说明「哪一块退步了」）。
- **一条规则可以有多条 check**（`checks[]`），每条 check 有自己的 `status`：`pass` / `warn` / `fail`。别把「一条规则失败」等同于「整个站都不合格」——看 `pages[]` 才知道影响面。
- **`failed` / `warnings` 是按检查数计的**，不是按页面数。一个失败检查可能只影响 1 页，也可能影响 40 页。

CI 里最常用的两个取数（jq）：

```bash
squirrel audit <url> -f json -o report.json --offline
jq '.healthScore.overall' report.json
jq '[.ruleResults[] | select(.severity=="error")] | length' report.json
```

### console 格式速读

```
SQUIRRELSCAN REPORT
https://example.com • 42 pages • 87/100 (B)

Health Score: 87/100 (B)

Category Breakdown:
--------------------------------------------------
Core SEO             ██████████ 100%
  Passed: 45 | Warnings: 0 | Failed: 0
Links                ████████░░ 85%
  Passed: 23 | Warnings: 5 | Failed: 3

Total: 83 passed, 13 warnings, 9 errors
```

- `42 pages` = 本次**真正审计到**的页数。用 `-m` 限过页数的话，这个数就是被限过的。
- 分类条按错误数排序，**满分类（100% 且无问题）排在最后**。
- 问题是全局分组展示的，同一类别可能出现在多个严重度下。

---

## 八、六个常见误读

1. **拿部分审计的分数和全量比。** 用了 `--rule-include` / `--rule-exclude` 后，分数只按跑过的规则重算，console 会在分数下打 `partial audit` 提示（别的格式只往 stderr 打警告）。这种分数**只能自己跟自己比**。
2. **把 `<locked-rules>` 当没这回事。** 匿名 / quick 档会跳过一批云端规则，看到这段就说明体检不完整。
3. **把 0 页当成「网站很干净」。** `totalPages: 0` 是**没抓到**，不是满分。先查 WAF / 请求头。
4. **按列表顺序从上往下修。** 应该按类别归组批量改。
5. **只看总分。** 总分 87 可能意味着 SEO 94 / Performance 60——后者才是要命的。四个分组分一起看。
6. **把 `warning` 当噪音。** warning 计 0.5 分且参与密度扣分；warning 密度高的站，总分一样会被压下来。

---

## 九、读完报告后的下一步

拿到报告只是开始。**修问题的优先级顺序、分批策略、以及怎么把它做成 CI 门禁**在 `ci-and-fix-loop.md`。
