# 安装与首次审计

本文只负责一件事：把「装好 → 跑出第一份报告 → 确认报告可信」这条最短路径走通。规则分类与报告解读见 `rules-and-reports.md`，接 CI 与修问题见 `ci-and-fix-loop.md`。

---

## 〇、动手前先确认授权

squirrelscan 是主动爬虫：它从种子页出发，顺着站内链接、`robots.txt`、`sitemap.xml` 抓下去，还会取页面引用的 CSS / JS / 图片，并核查站外链接。目标站的访问日志里会留下这些请求。

- **自有站点**：直接开始。
- **客户 / 第三方站点**：先拿到书面授权，把域名和页数上限写进授权范围；同时把 `respect_robots` 改回 `true`。
- **只是好奇别人的站**：不要跑。默认 `respect_robots = false` 的官方理由是「审计由站主发起」，对别人的站这个理由不成立。

---

## 一、装之前：二进制还是 npm

| 判断条件 | 官方二进制（推荐） | npm |
|---|---|---|
| 需要 Node.js | **不需要** | 需要 Node 18+ |
| 依赖 | 零依赖单文件 | 走 npm 依赖树 |
| 升级 | `squirrel self update` 自更新 | `npm update -g squirrelscan` |
| 卸载 | `squirrel self uninstall`（连缓存一起清） | `npm uninstall -g squirrelscan` |
| 适合谁 | 绝大多数人、CI runner、不想装 Node 的机器 | 已有 Node 工具链、想统一版本管理的团队 |

命令行叫 `squirrel`，包名是 `squirrelscan`，别把两者搞混——很多 404 是搜 `squirrel` 这个包名搜出来的。

---

## 二、安装

### 路线 A：官方安装脚本（macOS / Linux）

```bash
curl -fsSL --connect-timeout 10 --max-time 120 https://install.squirrelscan.com | bash
```

### 路线 B：Windows PowerShell

```powershell
iwr -useb https://install.squirrelscan.com/install.ps1 | iex
```

脚本把二进制放到 `~/.local/bin/squirrel` 并加进 PATH。

### 路线 C：npm

```bash
npm i -g squirrelscan
```

### 安装脚本可调的环境变量

| 变量 | 作用 |
|---|---|
| `SQUIRREL_VERSION` | 装指定 release 而不是最新，例如 `v0.0.94`——**生产环境建议钉版本** |
| `SQUIRREL_CHANNEL` | `stable`（默认）或 `beta` |
| `SQUIRREL_BIN_DIR` | 符号链接落点，默认取 PATH 上第一个可写目录，回退 `~/.local/bin` |
| `SQUIRREL_FORCE_MIRROR` | 跳过 GitHub，直接走官方镜像 |
| `NO_TELEMETRY` | 任意非空值可关掉安装失败时的匿名上报 |

### GitHub 拉不通怎么办

国内网络常见。安装脚本自己会兜底：GitHub 下载失败后自动改从 `install.squirrelscan.com` 取同样的字节，校验和两份都验。不想等超时就直接强制镜像：

```bash
curl -fsSL https://install.squirrelscan.com | SQUIRREL_FORCE_MIRROR=1 bash
```

```powershell
$env:SQUIRREL_FORCE_MIRROR='1'; iwr -useb https://install.squirrelscan.com/install.ps1 | iex
```

变量要给到执行脚本的那个 shell，所以放在管道右侧。两个源都不通时，脚本会把试过的两个 URL 打出来——把 `github.com` 或 `install.squirrelscan.com` 任一加进白名单即可。注意**返回登录页的拦截代理也算「不可达」**，脚本会自己切下一个源。

### Alpine / musl Linux

二进制需要 `libstdc++`。以 root 跑安装脚本会自动补上，否则先装：

```sh
apk add libstdc++          # 需要 root 就用 sudo apk add libstdc++
```

---

## 三、装完必做：两条验证

```bash
squirrel self doctor      # 二进制、PATH、缓存、权限，一把过
squirrel self version     # 记下版本号，报告口径和规则条数都跟版本走
squirrel --help           # 确认命令面
```

`self doctor` 不通过时按提示逐条处理，别跳过——它报的问题后面一定会以更难懂的形式再出现一次。

日常维护：

```bash
squirrel self update      # 原地升级到最新 release
squirrel self uninstall   # 解链二进制并清缓存
```

---

## 四、第一次审计：先收窄，再放开

### 第 1 步：最小代价跑通链路

```bash
squirrel audit https://你的站.example.com -C quick
```

`quick` 是**默认 25 页**的快速扫描：只看种子 URL + sitemap，不做链接发现，也**主动跳过全部联网的云端增强**。匿名（未登录）状态下它本来就是默认档。这一步只回答一个问题：能不能抓到页面。

同时把打扰降到最低：

```bash
squirrel audit https://你的站.example.com -m 30 --max-depth 2 --concurrency 3
```

| 参数 | 含义 | 建议 |
|---|---|---|
| `-m, --max-pages` | 最多抓多少页 | **永远显式写**，别吃默认值 |
| `--max-depth` | 从种子页算起的最大深度（种子页 = 0） | 大站先压到 2~3 |
| `--concurrency` | 全局抓取工作池大小（默认 5） | 生产站降到 2~3 |
| `--per-host` | 单主机并发上限（默认 5） | 同上 |

### 第 2 步：确认真抓到了

终端顶部会打出 `Coverage`（档位与页数上限）、`Config`、`Account`、`Dashboard` 几行，然后是一句 `✓ Audited N pages`。

**如果 N = 0 或第一个请求就失败**，几乎可以确定是 WAF / bot 防护在门口挡了 `403` / `429`。依次试：

1. 自己用浏览器打开目标 URL，确认不是登录墙。
2. 用 `-H` 补上站点期望的头部：

   ```bash
   squirrel audit https://staging.example.com -H "Authorization: Bearer <token>"
   # 或站点 Basic Auth
   squirrel audit https://staging.example.com -H "Authorization: Basic <base64>"
   ```

3. 站点要求签名爬虫身份的话，配置 Web Bot Auth 头。
4. 站点明确不欢迎自动流量——停手，这是它的权利。

### 第 3 步：放开到有意义的范围

```bash
# 登录后默认档：每个 URL 模板抽一页，跑云端规则，最多 100 页
squirrel audit https://你的站.example.com -C surface

# 全量：最多 500 页，尽量抓全
squirrel audit https://你的站.example.com -C full -m 500
```

覆盖档对照：

| 档位 | 默认页数 | 做什么 | 要不要账号 |
|---|---|---|---|
| `quick` | 25 | 种子页 + sitemap，不做链接发现，**不调云端** | 不要 |
| `surface` | 100 | 每个 URL 模式抽一页，跑云端规则 + 摘要 | 登录后为默认 |
| `full` | 500 | 在上限内尽量抓全，跑云端规则 + 摘要 | 建议登录 |

**默认档是「看登录状态」的**：任何已登录账号（免费档也算）默认 `surface`；纯匿名默认 `quick`。想跑完整规则集，登录或显式传 `-C surface` / `-C full`。

### 第 4 步：缓存与重跑

| 场景 | 行为 |
|---|---|
| 首次运行 | 建新爬取 |
| 重跑（上次已完成） | 新建爬取，靠条件请求吃 304 缓存 |
| 重跑（上次中断） | 从断点续 |
| 影响范围的配置变了（`include` / `exclude` / `allow_query_params` / `drop_query_prefixes`） | 强制全量重爬 |

```bash
squirrel audit https://你的站.example.com --refresh         # 无视缓存，全部重取
squirrel audit https://你的站.example.com --no-incremental  # 每页都完整拉，禁用条件请求
squirrel audit https://你的站.example.com --resume          # 续跑中断的爬取
```

---

## 五、输出落在哪，怎么快速确认它对

```bash
# 终端直接看（默认 console）
squirrel audit https://你的站.example.com

# 落盘
squirrel audit https://你的站.example.com -f json -o report.json
squirrel audit https://你的站.example.com -f llm  -o report.xml
squirrel audit https://你的站.example.com -f html -o report.html

# 事后不看原始输出，直接查已存的报告
squirrel report
squirrel report -f llm
squirrel report -f json -o report.json
```

审计历史存在本地 SQLite 里，**默认每个项目保留最近 3 次**，超出且在下次成功运行后淘汰。想多留几次：

```toml
[storage]
keep_audits = 10
```

两分钟验收法：

```bash
squirrel audit https://你的站.example.com -C quick -f json -o /tmp/a.json
# 看三个数：totalPages 是否 > 0、healthScore.overall、errorCount
```

`totalPages` 为 0 就是没抓到（回到上一步查 WAF）；页面数明显少于预期就调 `-m` 和 `--max-depth`。

---

## 六、staging、localhost 与内网

```bash
# 本地 dev server
squirrel audit http://localhost:3000

# 内网 / 私有网段
squirrel audit http://192.168.1.10:8080

# 带预览口令的 staging
squirrel audit https://staging.example.com -H "Authorization: Bearer <token>"
```

**这类目标永远不会上云**：`localhost`、回环、私有网段（如 `192.168.1.10`）、`.local` / `.internal` 这类内部名，云端既够不到也渲染不了、发布不了，所以审计全程本地完成、也不花钱。代价是**拿不到浏览器渲染和 AI 分析**——这正是本地目标的固有限制。

注意 `-H` 的值会在输出里被脱敏，但它仍然出现在你的 shell 历史里。生产凭证建议用环境变量拼：

```bash
squirrel audit https://staging.example.com -H "Authorization: Bearer $STAGING_TOKEN"
```

---

## 七、接进编码 Agent（三条路）

### 路 1：官方 Skill（推荐，带修复闭环）

```bash
npx skills add squirrelscan/squirrelscan
```

装到 `.agents/skills/`，一次得到两个 Skill：`squirrelscan`（操作 CLI）和 `audit-website`（审计 + 修复循环）。之后直接对 Agent 说：

```
用 audit-website 审一下 example.com，把发现的问题按优先级修掉
```

站点大的话再加范围约束：`只审 /blog/*，最多 20 页`。Agent 支持 plan 模式时**先用 plan 模式**，让它把问题映射到源文件、给出方案后再动手改。

### 路 2：本地 MCP（无需账号）

```bash
squirrel mcp
```

由 Agent 的 MCP 配置拉起这个 stdio 服务。审计、规则、问题、报告会变成 Agent 的原生工具，不用再管道传文本。本地 MCP 跑本地审计，不花 credits。

### 路 3：纯管道（零集成）

```bash
squirrel audit https://你的站.example.com --format llm | claude "分析并按优先级给出修复方案"
```

`--format llm` 是专门为模型压缩过的格式，比原始 XML 小 40%~70%，同一份报告少花不少 token。

### 给 Agent 一份固定配置

项目根放一个 `squirrel.toml`，让每次 Agent 跑都是同一套参数：

```toml
[crawler]
max_pages = 50
respect_robots = false        # 仅限自有站点

[rules]
disable = ["content/word-count", "content/reading-level"]
```

---

## 八、命令速查

| 想干什么 | 命令 |
|---|---|
| 装（macOS/Linux） | `curl -fsSL https://install.squirrelscan.com \| bash` |
| 装（Windows） | `iwr -useb https://install.squirrelscan.com/install.ps1 \| iex` |
| 自检 | `squirrel self doctor` |
| 看版本 / 升级 / 卸载 | `squirrel self version` · `squirrel self update` · `squirrel self uninstall` |
| 快速体检（25 页内） | `squirrel audit <url> -C quick` |
| 抽样式审计（每模板一页） | `squirrel audit <url> -C surface` |
| 全量审计 | `squirrel audit <url> -C full -m 500` |
| 只管网络不管分析 | `squirrel crawl <url>` |
| 对已有爬取数据重跑规则 | `squirrel analyze` |
| 查已存报告 | `squirrel report` |
| 查结构化数据实体图 | `squirrel entities` |
| 生成配置 | `squirrel init` |
| 看/改/校验配置 | `squirrel config show` · `config set` · `config validate` |
| 完全离线 | `squirrel audit <url> --offline` |
| 强制纯 HTTP（不渲染、不烧渲染 credits） | `squirrel audit <url> --http` |
| 云端登录 | `squirrel auth login` |
| 签发 API Key（供 CI） | `squirrel keys create` |
| 看 credits 余额与计费 | `squirrel credits` |
| 起本地 MCP 服务 | `squirrel mcp` |

---

## 九、首次接入自检

- [ ] 授权已确认并留痕（自有 or 书面许可）；非自有站点已把 `respect_robots` 改回 `true`。
- [ ] `squirrel self doctor` 全绿，版本号已记录。
- [ ] 第一次跑的是 `-C quick` 或带 `-m` 小上限，没有一上来就 `full`。
- [ ] `totalPages` 大于 0；如果是 0，已经排查过 WAF / 请求头。
- [ ] `-m`、`--max-depth`、`--concurrency` 是显式写的，没吃默认值。
- [ ] 报告格式和目标匹配（人看 html、CI 用 json、Agent 用 llm）。
- [ ] 本地 / staging 目标确认不需要云端能力，或已明确知道缺了什么。
- [ ] 用了云端的话，Key 只在环境变量，`git grep` 不到明文。
- [ ] 审计历史保留份数（`keep_audits`）符合团队的对比需求。
