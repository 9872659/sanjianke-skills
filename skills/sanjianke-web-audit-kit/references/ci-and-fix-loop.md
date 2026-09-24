# 接进 CI 与修复流程

本文分两半：前半是如何把审计做成**发版门禁**（退出码、`--fail-on`、三套 CI 配置），后半是如何把一份报告变成**真正改完的代码**（分批、映射、重审）。规则分类与报告解读见 `rules-and-reports.md`。

---

## 〇、前提

CI 里跑审计同样是**主动爬取**，而且比本地跑更频繁、更无人值守。两件事必须先定：

1. **只审自有站点或已获授权的环境**（通常是 staging / preview 域名）。
2. **给 CI 专用的目标站限流**：`-m`、`--max-depth`、`--concurrency` 全部显式收窄。别让流水线每次 push 都去全量轰一遍生产站。

---

## 一、退出码：CI 判断「回归」还是「跑挂了」

`squirrel audit` 用三个不同退出码，让流水线能区分这两件事：

| 退出码 | 含义 | CI 该怎么处理 |
|---|---|---|
| `0` | 审计跑完，且所有 `--fail-on` 门槛都通过 | 绿灯放行 |
| `2` | 审计跑完，但**有门槛被触发** | 红灯，这是「质量回归」 |
| `1` | 运维性错误（参数写错、网络失败、表达式非法等） | 红灯，但这是「工具/配置问题」，不是内容回归 |

**这个区分很值钱**：`1` 去查配置和网络，`2` 去查页面和代码。混在一起排查会浪费大量时间。

```bash
squirrel audit https://staging.example.com --fail-on 'score<90'
echo $?     # 0 / 2 / 1
```

---

## 二、`--fail-on`：门槛表达式

```bash
squirrel audit https://example.com --fail-on 'score<90' --fail-on 'severity>=error'
```

**表达式必须加引号**：shell 会把裸露的 `<` `>` 当成重定向，不加引号命令会被静默改写成别的东西。这是实战里最常见的坑。

可重复传，也可逗号合并：

```bash
squirrel audit https://example.com --fail-on 'score<90,score:perf<80,warnings>0'
```

### 支持的指标

| 表达式 | 什么情况下触发 |
|---|---|
| `score<N` | 总分低于 N |
| `score:<category><N` | 某个**分类**分低于 N，例如 `score:perf<80`、`score:a11y<85` |
| `severity>=error` | 存在 error 级问题（`>=warning` 同理） |
| `errors>0` | 至少一个 error 级问题 |
| `warnings>0` | 至少一个 warning 级问题 |

运算符有五种：`<`、`<=`、`>`、`>=`、`=`，全部可用于数值指标（`score`、`score:<category>`、`errors`、`warnings`）。

**`severity` 的 `=` 是精确匹配**：`severity=warning` 只在「有 warning 但没有 error」时触发；想要「至少 warning」必须写 `severity>=warning`。这个语义反直觉，写错了门槛会形同虚设。

### 四个必须知道的边界

1. **门槛摘要写到 stderr**，所以 `--format json` 的 stdout 依然干净、可以直接 `| jq` 或重定向成文件。
2. **表达式非法会在爬取前就失败退出（`1`）**，不会白跑一趟。
3. **`--fail-on score:<category>` 引用一个被 `--rule-exclude` 排除掉的类别会直接报错**——因为它永远不可能触发。这是刻意的保护。
4. **部分审计的分数不能当门槛基准**。如果你在 CI 里用了 `--rule-include`，门槛值要按那部分规则重新标定，别沿用全量分数。

### 门槛值怎么定

第一次接 CI 时**不要凭感觉**，按这条路径标定：

```bash
# 第 1 步：在当前主干上跑 3 次，记下总分与分组分的实际水平
for i in 1 2 3; do
  squirrel audit https://staging.example.com -C quick -m 30 \
    -f json -o /tmp/base-$i.json --offline
  jq '.healthScore.overall' /tmp/base-$i.json
done

# 第 2 步：门槛定在「当前水平 - 3~5 分」，先只拦断崖式回归
# 第 3 步：跑两周没问题，再逐步抬高
```

一开始就把门槛定在 90 分的结果通常是：流水线长期红着，然后所有人学会忽略它。

---

## 三、GitHub Actions

### 路线 A：官方 Action（最短）

```yaml
name: Audit
on: [pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: squirrelscan/audit-action@v1
        with:
          url: https://staging.example.com
          fail-on: "score<90,severity>=error"
          token: ${{ secrets.SQUIRRELSCAN_API_KEY }}   # 可选，云端增强用
          github-token: ${{ secrets.GITHUB_TOKEN }}    # 可选，让它在 PR 上留言
```

`token` 不填照样能跑：**本地审计不需要登录**，只是拿不到云端增强。

### 路线 B：手装 CLI（可控性更好）

```yaml
name: Audit
on:
  pull_request:
  schedule:
    - cron: '0 3 * * 1'        # 每周一凌晨三点全量跑一次

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - name: 安装 squirrelscan
        run: |
          curl -fsSL --connect-timeout 10 --max-time 120 https://install.squirrelscan.com | bash
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"   # 自托管 runner 必须，让后续步骤能找到 squirrel

      - name: 审计并卡门禁
        run: |
          squirrel self version
          squirrel audit https://staging.example.com \
            -C quick -m 40 --concurrency 3 \
            --fail-on 'score<90,severity>=error,score:perf<80' \
            -f json -o audit.json
        env:
          SQUIRRELSCAN_API_KEY: ${{ secrets.SQUIRRELSCAN_API_KEY }}

      - name: 上传报告
        if: always()                                    # 门禁失败时也要留证据
        uses: actions/upload-artifact@v4
        with:
          name: squirrelscan-report
          path: audit.json
```

两个细节：

- **`if: always()`** 很关键。门禁失败后默认后续步骤跳过，报告就丢了——而那正是你最需要看的时候。
- **`echo "$HOME/.local/bin" >> "$GITHUB_PATH"`** 在 GitHub 托管 runner 上通常可以省，在自托管 runner 上不能省。

---

## 四、GitLab CI

```yaml
audit:
  image: ubuntu:latest
  script:
    - apt-get update && apt-get install -y curl
    - curl -fsSL --connect-timeout 10 --max-time 120 https://install.squirrelscan.com | bash
    - export PATH="$HOME/.local/bin:$PATH"
    - squirrel audit "$AUDIT_URL" -C quick -m 40 --fail-on 'score<90,severity>=error'
  artifacts:
    when: always
    paths:
      - audit.json
  variables:
    AUDIT_URL: "https://staging.example.com"
    SQUIRRELSCAN_API_KEY: $SQUIRRELSCAN_API_KEY   # 可选，在 CI/CD 变量里设为 masked
```

`export PATH` 必须和审计在同一条 `script:` 里完成——GitLab 每条 `script` 行虽然共享 shell 环境，但显式写出来更不容易踩坑。

---

## 五、通用 runner

任何能跑 shell 的 runner 都行：

```bash
curl -fsSL --connect-timeout 10 --max-time 120 https://install.squirrelscan.com | bash
export PATH="$HOME/.local/bin:$PATH"

squirrel audit https://example.com \
  --format json --output report.json \
  --fail-on 'score<90,score:perf<80'
# 门槛触发时退出码为 2，脚本会在此中断
```

**JSON 报告写 stdout 时是干净的**（门禁摘要走 stderr），所以下面这种写法是安全的：

```bash
squirrel audit https://example.com -f json --fail-on 'score<90' > report.json || echo "门禁触发，见 report.json"
```

---

## 六、认证：什么时候才需要 Key

**本地审计是确定性运行，不需要登录。** 只有在用云端功能（浏览器渲染、AI 摘要、技术栈识别、发布报告）时才需要凭证。

```bash
# 一次性签发（在能登录的机器上）
squirrel keys create

# CI 里作为 secret 暴露
export SQUIRRELSCAN_API_KEY=...
```

各平台放法：

| 平台 | 放哪 |
|---|---|
| GitHub Actions | repo / org secret → `env: SQUIRRELSCAN_API_KEY: ${{ secrets.SQUIRRELSCAN_API_KEY }}` |
| GitLab | masked CI/CD variable `SQUIRRELSCAN_API_KEY` |
| 其它 | 在 job 环境里 export |

设了 `SQUIRRELSCAN_API_KEY` 后 CLI 自动使用它；旧名字 `SQUIRREL_API_TOKEN` 仍可用作兼容别名。**两个都不设，审计照样跑**，只是跳过云端增强。

另外：**登录且在线时审计默认自动发布为 unlisted 报告**。CI 里如果要严格避免发布，加 `--no-publish`（保持在线但不出报告），或直接 `--offline`（连云端增强也一起关）。

---

## 七、CI 策略：跑什么、跑多密

| 触发时机 | 建议审计范围 | 建议门槛 |
|---|---|---|
| PR / MR | `-C quick -m 30`，只审 preview 或 staging | `severity>=error` 先跑起来 |
| 合并到主干 | `-C quick -m 60` | 加 `score<N`（N = 当前水平 - 3） |
| 每日定时 | `-C surface -m 100` | `score<90,score:perf<80` |
| 每周定时 | `-C full -m 500`，可带云端渲染 | 与上周报告对比，看趋势不看单点 |

三条经验：

- **PR 阶段别跑全量。** 每次 commit 全站爬一遍，既慢又容易被目标站限流，还会逼得团队把门禁关掉。
- **门槛看「回归」不看「绝对值」。** 一个长期 72 分的站，把门槛定在 70 才有意义。
- **报告要留档。** 至少存 JSON，才能做 `jq` 对比和趋势图；`if: always()` / `when: always` 别忘了。

---

## 八、从报告到代码：修复流程

### 第 1 步：按「类别 × 严重度」重排，不要按列表顺序修

报告的顺序（严重度 → 类别 → 规则权重）回答的是「多紧急」，但**修复效率取决于「同一处代码能改掉多少条」**。

```bash
squirrel audit https://staging.example.com -f json -o report.json

# 按类别聚合 error 数量，找出改动收益最高的地方
jq -r '.ruleResults[] | select(.severity=="error") | .category' report.json \
  | sort | uniq -c | sort -rn
```

一个模板文件里的 `title`、`description`、`og:image` 往往一次改三处，而三条规则各自报错。**按模板/组件归组，不按规则归组。**

### 第 2 步：把每条问题映射到源文件

报告给的是**受影响 URL 路径**（`/blog/post-1`），不是文件路径。中间那一步必须你自己或 Agent 走：

| 站点类型 | 从 URL 找代码的思路 |
|---|---|
| Next.js / Nuxt / Astro | 路由目录 → 页面组件；`title`/meta 通常在页面的 metadata 导出或布局组件 |
| 模板引擎（Django / Rails / Laravel / Hugo） | 对应模板文件 + `base.html` / `layout` 布局 |
| CMS（WordPress 等） | 主题模板 + SEO 插件配置；全局项在插件设置里 |
| 静态站生成器 | 布局模板 + 内容 frontmatter |

**先修「全站级」问题，再修「单页级」问题。** 全站级（缺 robots.txt、缺 sitemap、全站缺 `og:image`、字段拼错的 canonical）通常改一个文件或一处配置就能清掉几十条检查，单页级（某篇文章太短）改起来费时且收益低。

### 第 3 步：分批改，每批都重审

```
第 1 批：可抓取性 + 硬扣分（robots.txt / sitemap / noindex / canonical）
   → 重审 → 总分应该跳一档（硬扣分是乘法）
第 2 批：全站级模板问题（title / description / og / h1 / alt）
   → 重审
第 3 批：图片与性能（尺寸属性 / 现代格式 / srcset / 懒加载）
   → 重审
第 4 批：无障碍（对比度 / 表单标签 / 无障碍名称 / 焦点）
   → 重审
第 5 批：内容与结构化数据（薄内容 / 重复标题 / schema 必填项）
   → 重审
```

每批之后重审的理由：**分数是加权 + 曲线 + 乘法扣分的组合，凭直觉猜不到改动的实际收益**。而且有些「修好的问题」会因为改动引入新问题（补 alt 补错了、canonical 改出新形式漂移），只有重审能发现。

### 第 4 步：验证分数确实动了

```bash
squirrel audit https://staging.example.com -f json -o before.json
# ...改代码、部署...
squirrel audit https://staging.example.com --refresh -f json -o after.json

diff <(jq '.healthScore.groups' before.json) <(jq '.healthScore.groups' after.json)
```

**`--refresh` 不要省**，否则可能命中缓存拿到旧结果，白高兴一场。

---

## 九、给编码 Agent 的修复循环

### 一次性搭好

```bash
npx skills add squirrelscan/squirrelscan   # 装 squirrelscan + audit-website 两个 Skill
squirrel mcp                               # 或者挂本地 MCP，无需账号
```

### 修复循环的提示词范式

```
用 audit-website 审一下 https://staging.example.com，范围限制在 /blog/*，最多 20 页。
按「类别 × 严重度」把问题分组，给出修复计划：
每条问题指出对应的源文件、需要改什么、以及预计能消掉几条检查。
先不要动代码，等我看完计划。
```

拿到的计划确认后再放行：

```
按计划修第 1 批和第 2 批。每批改完重新审计一次，把前后分组分对比给我。
如果某个问题在代码里找不到对应位置，单独列出来，不要猜。
```

**在 Agent 支持 plan 模式时务必先用 plan 模式。** 让它先把问题映射到文件、给出方案，再动手——直接让它「审完就改」很容易改出一堆无关 diff。

### 让 Agent 的每次运行都用同一套参数

项目根放 `squirrel.toml`，人和 Agent 共用：

```toml
[project]
name = "our-site"
domains = ["staging.example.com"]

[crawler]
max_pages = 50
respect_robots = false        # 仅自有站点可这样写
delay_ms = 100
concurrency = 3

[rules]
enable = ["*"]
disable = ["content/word-count", "content/reading-level"]   # 这两条我们先不追求

[external_links]
enabled = true
cache_ttl_days = 7

[output]
format = "console"

[cloud]
publish = false               # 不让 CI / Agent 顺手把报告发出去
```

约定：**能靠配置固化的，不要靠提示词。** Agent 每次记得写 `-m 50` 是不可靠的，写进 `squirrel.toml` 才可靠。

---

## 十、三份可直接抄的配置

### A. 本地开发档（快、不打扰、不发布）

```toml
[crawler]
max_pages = 25
coverage = "quick"
concurrency = 3

[cloud]
publish = false

[output]
format = "console"
```

### B. CI 门禁档（确定性、只拦回归）

```toml
[crawler]
max_pages = 40
coverage = "quick"
concurrency = 3
timeout_ms = 30000

[cloud]
publish = false

[external_links]
enabled = false        # CI 里关掉站外链接检查，避免拖慢与误报
```

```bash
squirrel audit "$AUDIT_URL" -f json -o audit.json \
  --fail-on 'score<90,severity>=error,score:perf<80'
```

### C. 审他人站点档（保守优先）

```toml
[crawler]
max_pages = 20
max_depth = 2
concurrency = 1
per_host_concurrency = 1
delay_ms = 1000
respect_robots = true      # 关键：非自有站点必须为 true
timeout_ms = 30000

[external_links]
enabled = false            # 别替对方去敲第三方的门

[cloud]
publish = false
render = "off"             # 别让云端去渲染别人的站
```

---

## 十一、CI 排错表

| 症状 | 大概率原因 | 处置 |
|---|---|---|
| 退出码 `1` | 参数写错 / 表达式非法 / 网络不通 | 看 stderr 第一条错误；先把 `--fail-on` 表达式单独在本地跑一遍 |
| 退出码 `2` 但报告看起来没问题 | 门槛值定得比当前水平高 | 按第 2 节的方法重新标定，门槛下调 |
| `totalPages: 0` | WAF / bot 防护挡了 `403`/`429` | 用 `-H` 补头部；确认不是登录墙；站点不欢迎自动流量就停手 |
| 每次 push 都超时 | 全量审计 + 高并发 | 降到 `-C quick -m 30 --concurrency 2`；PR 阶段不跑全量 |
| JSON 解析失败 | 门槛摘要把 stdout 弄脏了 | 摘要本来走 stderr；检查是不是自己 `2>&1` 合并了流 |
| `squirrel: command not found` | PATH 没带上 | 加 `echo "$HOME/.local/bin" >> "$GITHUB_PATH"` 或 `export PATH="$HOME/.local/bin:$PATH"` |
| 本地过、CI 不过 | CI 目标是 staging、本地是 dev | 统一 `AUDIT_URL`；staging 常缺 sitemap 或带 noindex（这是真问题，不是误报） |
| 分数忽高忽低 | 页数上限导致每次抓到的页面不同 | 固定 `-m` 与覆盖档；开 `smart_audits` 让未重爬页面沿用上次状态 |
| 报告被自动发布了 | 登录状态下默认发布 unlisted | 加 `--no-publish`，或配置 `[cloud] publish = false` |

---

## 十二、上线前自检

- [ ] CI 里审计的目标是**自有或有授权的环境**，且已限流（`-m` / `--max-depth` / `--concurrency`）。
- [ ] `--fail-on` 表达式**加了引号**，本地手跑过一次同样的表达式。
- [ ] 门槛值是**按当前基线标定的**，不是拍的理想值。
- [ ] 已确认退出码 `2`（回归）和 `1`（故障）在流水线里被分开告警。
- [ ] 报告用 `if: always()` / `when: always` 留档，失败时也拿得到证据。
- [ ] `SQUIRRELSCAN_API_KEY` 只存在于 CI secret，仓库里 grep 不到明文。
- [ ] 明确了要不要发布报告（`--no-publish` 或 `[cloud] publish = false`）。
- [ ] 修复按「全站级 → 单页级」「模板 → 内容」分批推进，每批都重审且带 `--refresh`。
- [ ] `squirrel.toml` 已入库，人和 Agent 共用同一套参数。
