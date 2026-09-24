---
name: sanjianke-web-audit-kit
slug: sanjianke-web-audit-kit
displayName: 三剪客 · 网站质量审计
description: "一条命令审完网站的 SEO、性能、安全与 AI 可读性。 遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "squirrelscan 是单文件二进制的网站质量审计 CLI：抓站后按近 300 条规则查 SEO、性能、安全、无障碍与 Agent 可读性，可用 --fail-on 卡住 CI，也可作 MCP 服务供编码 Agent 调用。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - IT 运维与安全
  - 网站审计
  - 性能
---

# 三剪客 · 网站质量审计

一条命令审完网站的 SEO、性能、安全与 AI 可读性

网站上线前后真正难的不是「写了没写 meta description」这种单点，而是**你根本不知道哪些页面坏了**：首页标题超长、某个栏目 40 张图缺 `alt`、sitemap 里躺着十几个 404、HTTPS 页面还在加载 `http://` 的脚本、`/llms.txt` 被 SPA 兜底页面顶掉、页脚版权年份停在两年前。人工一页页点又慢又漏。squirrelscan 把这件事压成一条命令：抓取目标站点 → 跑规则 → 给你一个 0~100 的健康分、一份按严重度排好序的问题清单，以及每条问题的修复方向。

**先把它的定位说清楚，不夸大也不贬低。** 这个上游项目自身热度一般（GitHub 上约 268 stars），但它是那批热门 Skill 里 `audit-website` 的底层工具——`npx skills add squirrelscan/squirrelscan` 一次会装下两个 Skill：`squirrelscan` 负责操作命令行，`audit-website` 负责「审计 → 定位到源文件 → 批量修 → 重审」的闭环。换句话说，绝大多数人是**通过那个大 Skill 间接用到了它**，单独提起它的反而少。它属于典型的「被大 Skill 依赖的小工具」：体量小、能力实，官方自己就是把它当作编码 Agent 的地基在维护。

技术上它是**零依赖的单文件二进制**，命令行叫 `squirrel`（`squirrelscan` 是包名，Node 18+ 环境也能 `npm i -g squirrelscan`）。**纯本地审计免费、不限次数、不需要注册账号**；只有云端增强（浏览器渲染 JS 重的页面、AI 分析、技术栈识别、发布可分享报告）才按 credits 计费。所以「审自己的站」这件事边际成本基本是零。

## 权限与用途说明

⚠️ 第一条最重要：**这是一个主动爬虫工具，不是只读一个 URL 的工具。** 它会从种子页出发，顺着站内链接、`sitemap.xml`、`robots.txt` 一路抓下去，还会去取页面上引用的 CSS / JS / 图片，并检查页面里的站外链接。**目标站点的访问日志里会实打实留下这些请求。**

**授权前提（硬性）**：只对你自己拥有、或已获得书面授权的站点运行。默认配置 `respect_robots = false`，官方的理由是「审计由站主发起」——这个前提对自建站成立，对别人的站就是越界的自证。审任何非自有站点之前：拿到授权、把 `respect_robots` 改回 `true`、把 `max_pages` 和 `delay_ms` 调保守、必要时先小范围试跑。

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问（出网爬取目标站） | 是（必需） | `squirrel` 进程直接出网：抓首页、站内链接、`robots.txt`、`sitemap.xml`、页面引用的 CSS/JS/图片，并核查站外链接。这是**主动爬取**，不是被动读取 |
| 网络访问（云端增强，可选） | 视需要 | 登录后由云端代为渲染页面、做 AI 分析与技术栈识别、发布报告；`--offline` 可一次性全部关掉 |
| 读取文件 | 视需要 | 读项目里的 `squirrel.toml`、`.squirrel/settings.json`、用户级 `~/.squirrel/settings.json`；对比历史报告时读既有的 JSON/HTML 报告 |
| 写入文件 | 是 | 本地 SQLite 缓存与审计历史（保留份数由 `[storage] keep_audits` 决定）、`.squirrel/` 目录，以及 `-o report.json` / `report.html` 等输出文件 |
| 凭证 | 视需要 | 仅在使用云端功能时需要 `SQUIRRELSCAN_API_KEY`。纯本地审计**不需要账号、不需要 Key** |
| 子进程 / 后台常驻 | 是 | 执行 `squirrel` 二进制；`squirrel mcp` 会作为常驻 stdio 进程被编码 Agent 拉起；站点大时审计应放后台跑 |
| 自定义请求头 | 视需要 | `-H "Authorization: Bearer …"` 用于 staging 站、Basic Auth 或 bot 墙；值在输出中会被脱敏 |

**密钥与费用**：本 Skill 不内嵌任何密钥，不代理转发你的请求，也不代收任何费用。云端 credits 的消耗由使用者自己的上游账号承担，Key 从上游控制台自行获取（`squirrel keys create`）。请勿把 Key 写进 SKILL.md、脚本源码或提交记录，一律走环境变量。纯本地审计不产生任何费用。

## 触发场景

- 「网站要上线了，帮我整体体检一遍，别等上线才发现一堆问题」——全站首次审计，拿健康分和问题总表。
- 「Google 收录很差 / 有些页面搜不到」——看 crawlability、core、content 三类，重点查 noindex、canonical、sitemap 覆盖。
- 「审计结果出来了，帮我按优先级修」——进入「报告 → 定位代码 → 分批修 → 重审」的闭环。
- 「每次发版都有人把 SEO 弄坏，能不能自动拦住」——用 `--fail-on` 把审计做成 CI 门禁。
- 「我们的站要给 AI Agent 读，但现在抓不到内容」——查 Agents 组规则：`llms.txt`、`AGENTS.md`、`Content-Signal`、无 JS 时的纯文本占比。
- 「staging 站有 Basic Auth 密码，工具抓不进去」——用 `-H` 传自定义请求头。
- 「本地 dev server 也要审」——直接指向 `http://localhost:3000`，本地审计不花钱也不上云。

## 快速开始

### 1. 装 CLI

```bash
# macOS / Linux
curl -fsSL --connect-timeout 10 --max-time 120 https://install.squirrelscan.com | bash

# Windows PowerShell
iwr -useb https://install.squirrelscan.com/install.ps1 | iex

# 或者走 npm（Node 18+）
npm i -g squirrelscan
```

装完二进制落在 `~/.local/bin/squirrel` 并加进 PATH。遇到 GitHub 拉不通的网络，在管道右侧加环境变量强制走官方镜像：

```bash
curl -fsSL https://install.squirrelscan.com | SQUIRREL_FORCE_MIRROR=1 bash
```

```powershell
$env:SQUIRREL_FORCE_MIRROR='1'; iwr -useb https://install.squirrelscan.com/install.ps1 | iex
```

### 2. 自检，然后跑第一次审计

```bash
squirrel self doctor            # 确认二进制、PATH、缓存都正常
squirrel self version

squirrel audit https://你的站.example.com
```

本地审计不用登录、不花 credits。终端会打出健康分、分组/分类得分条、按严重度排序的问题清单，每条问题带受影响页面路径。**先跑 `-C quick`（默认 25 页）确认链路通不通，再放开页数**：

```bash
# 快速体检：只看首页 + sitemap，不发现链接，不调云端
squirrel audit https://你的站.example.com -C quick

# 收紧范围，避免打扰目标站
squirrel audit https://你的站.example.com -m 30 --max-depth 2 --concurrency 3
```

### 3. 拿到能直接喂给 Agent 的报告

```bash
# 给编码 Agent 用：紧凑的 token 优化格式
squirrel audit https://你的站.example.com -f llm -o report.xml

# 给 CI 用：机器可读
squirrel audit https://你的站.example.com -f json -o report.json

# 给人看：可视化 HTML
squirrel audit https://你的站.example.com -f html -o report.html
```

### 4. 让编码 Agent 自己驱动（可选）

```bash
npx skills add squirrelscan/squirrelscan   # 装官方两个 Skill
squirrel mcp                               # 或在 Agent 里挂本地 MCP，无需账号
```

接好之后，Agent 就能把审计、规则、问题、报告当成原生工具调用，自己跑「审 → 修 → 重审」。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 怎么装、装了怎么验、第一次审计怎么跑、结果在哪 | `references/install-and-first-audit.md` |
| 规则分哪几类、`--rule-include` 怎么用、报告每个数字什么意思 | `references/rules-and-reports.md` |
| 接进 GitHub Actions / GitLab / 通用 runner、`--fail-on` 怎么写、按优先级修问题 | `references/ci-and-fix-loop.md` |

## 能力边界

**覆盖**：

- 主动抓取目标站点并建立页面清单（站内链接 + `robots.txt` + `sitemap.xml` 三条发现路径）。
- 近 300 条规则、横跨 4 个评分组：**SEO**（可抓取性、核心 SEO、内容、链接、结构化数据、图片、社交、无障碍、移动端、URL、国际化、E-E-A-T、本地 SEO、视频、统计）、**Performance**（页面加载性能）、**Security**（HTTPS 与安全响应头、站点完整性/被挂马、法律合规、被广告拦截器屏蔽的内容）、**Agents**（AI Agent 可读性与可操作性）。
- 输出 0~100 健康分 + 4 个分组分 + 每个分类分 + 分级（A/B/C/D/F），以及按「严重度 → 分类 → 规则权重」排序的问题清单。
- 7 种输出格式：`console` / `text` / `json` / `html` / `markdown` / `xml` / `llm`，后两者可直接进流水线。
- CI 门禁：`--fail-on` 支持 `score<90`、`score:perf<80`、`severity>=error`、`errors>0`、`warnings>0` 与逗号组合，门槛触发时退出码为 `2`。
- Agent 接入三条路：官方 Skill、本地 MCP（`squirrel mcp`，无需账号）、管道（`--format llm | <agent>`）。
- 本地 `/localhost`、内网地址、staging 站（含 Basic Auth / Bearer 头）都能审，且这类目标永远不会被上传到云端。

**不覆盖**：

- **不改你的代码。** 它只给问题和修复方向，改 `title`、补 `alt`、写 `llms.txt` 都得你自己或你的编码 Agent 动手。
- **不是搜索引擎排名工具。** 没有关键词排名、外链权重、竞品分析（Gap Analysis 类规则需要云端与实时搜索数据，默认不跑）。
- **不做运行时性能测量。** 静态抓取拿不到 LCP/CLS/INP 的真实数值，只能给「可能影响 LCP 的写法」这类结构性提示；真指标请另配 Lighthouse / CrUX。规则 `perf/browser-required` 本身就是在明说这个缺口。
- **不抓登录后才可见的内容。** 需要登录态的页面要自己用 `-H` 带凭证，且工具不做表单登录。
- **不替代专业安全测试。** 安全类规则是配置与暴露面检查（头部、混合内容、泄漏密钥、挂马特征），不是渗透测试或漏洞扫描。
- **不保证抓取到 JS 渲染后的内容**（除非开云端渲染，按页计费）。
- **不是全站爬虫框架。** 它按页数/深度上限采样，不做百万页归档。

## 依赖条件

| 项 | 要求 |
|---|---|
| 操作系统 | macOS / Linux / Windows，x64 或 arm64 |
| 运行时 | 直接装二进制则零依赖；走 npm 需要 Node 18+ |
| Alpine / musl Linux | 需要 `libstdc++`（root 下安装脚本会自动补，否则先 `apk add libstdc++`） |
| 磁盘 | 本地 SQLite 缓存与审计历史，默认每个项目保留最近 3 次审计 |
| 出网 | 能访问目标站点；安装阶段需要能访问 GitHub release 或官方镜像 |
| 账号 / Key | **纯本地审计：不需要**。云端渲染 / AI 分析 / 技术栈识别 / 发布报告才需要账号，凭证走 `SQUIRRELSCAN_API_KEY` |
| 配置（可选） | 项目根目录的 `squirrel.toml`，用 `squirrel init` 生成 |

## 已知限制

- **规则条数各出口口径不一致。** npm 包描述写 260+，官网支持页写 260+，文档站规则页写 295 条，首页宣传语写「270+」。这是版本迭代与文案没同步的结果，别把它当硬指标——以你本地实际装的版本为准。

  ```bash
  squirrel self version        # 看你装的是哪一版
  squirrel config show         # 看当前生效的规则开关
  ```

- **默认 `respect_robots = false`。** 见「权限与用途说明」，自建站无所谓，非自有站点必须改。
- **被 WAF / bot 防护拦住时会返回 0 页或首个请求就失败。** 用 `-H` 补上站点期望的头部；站点不欢迎自动流量时它有权拒绝，这不是工具 bug。
- **`--rule-include` / `--rule-exclude` 会让报告变成「部分审计」。** 分数只按实际跑过的规则重算，**不能和全量审计的分数横向比较**；console 会在分数下打 `partial audit` 提示，其它格式只往 stderr 打一行警告。
- **`--summary` 只对 `console` 格式有效**，与非 console 的 `--format` 组合会直接报错退出。
- **登录且在线时审计默认自动发布为 unlisted 报告。** 不想发布就加 `--no-publish`，或在 `squirrel.toml` 里写 `[cloud] publish = false`。
- **credits 不够不会让审计失败**：云端规则标 `skipped`，渲染退回纯 HTTP，审计用本地规则跑完并给一行警告。
- **内网 / localhost 永远不上云**：`localhost`、回环、私有网段（如 `192.168.x.x`）、`.local` / `.internal` 这类主机既不会被渲染也不会被发布。反过来，这也意味着这些站点拿不到云端增强能力。
- **`-C quick` 会主动跳过全部联网的云端增强。** 想知道完整规则集的效果，得登录跑 `surface` 或 `full`。

## 自检清单

- [ ] **授权已确认**：这是自有站点或已获书面授权；非自有站点已把 `respect_robots` 改回 `true`。
- [ ] 目标站已告知/已知情（必要时提前打招呼，避免被当成攻击流量）。
- [ ] `squirrel self doctor` 通过，`squirrel self version` 记下版本号。
- [ ] 第一次审计先用 `-C quick` 或 `-m` 小上限跑通，再放宽到 `surface` / `full`。
- [ ] 页数、并发、`delay_ms` 对目标站的承受力是合理的；生产站没被打出告警。
- [ ] 报告格式选对了：给人看用 `html`/`console`，给 CI 用 `json`，给 Agent 用 `llm`。
- [ ] 分数被 `--rule-include/exclude` 影响过的话，没有拿它和全量分数作比较。
- [ ] 接进 CI 前本地先手跑一遍同样的 `--fail-on` 表达式，确认门槛不会一上来就红。
- [ ] 用了云端功能的话，Key 只在环境变量里，仓库 `git grep` 不到明文。
- [ ] 审计完的问题清单有明确的负责人和优先级，不是只存一份报告了事。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/install-and-first-audit.md` | 三种安装方式与验证、第一次审计怎么收窄范围、输出落在哪、staging 与 localhost 怎么审、命令速查 |
| `references/rules-and-reports.md` | 规则按 4 个评分组 + 20 多个类别的分法、常用类别代码、健康分算法与扣分项、7 种报告格式怎么选、JSON 报告字段怎么读 |
| `references/ci-and-fix-loop.md` | 退出码语义、GitHub Actions / GitLab / 通用 runner 三套配置、`--fail-on` 表达式大全、修问题的优先级顺序与分批策略、`squirrel.toml` 推荐配置 |

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
