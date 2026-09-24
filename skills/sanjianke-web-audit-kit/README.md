# 三剪客 · 网站质量审计 Skill

一条命令审完网站的 SEO、性能、安全与 AI 可读性

---

## 前置条件

- **授权优先**：squirrelscan 是主动爬虫，会从种子页顺着站内链接、`robots.txt`、`sitemap.xml` 抓下去，还会取页面引用的 CSS/JS/图片并核查站外链接，目标站的访问日志会留下这些请求。**只对自有站点或已获书面授权的站点运行。** 审非自有站点前必须把 `respect_robots` 改回 `true`、并把页数与并发压到最低。
- 能出网的机器；安装阶段需要能访问 GitHub release 或官方镜像。
- macOS / Linux / Windows（x64 或 arm64）。走 npm 安装需要 Node 18+；直接装二进制则零依赖。
- **纯本地审计不需要注册账号、不需要 API Key、不产生费用。**

---

## 使用

装好命令行后，最短路径是：

```bash
# 1. 装（三选一）
curl -fsSL --connect-timeout 10 --max-time 120 https://install.squirrelscan.com | bash   # macOS / Linux
iwr -useb https://install.squirrelscan.com/install.ps1 | iex                             # Windows PowerShell
npm i -g squirrelscan                                                                    # 已有 Node 18+

# 2. 自检
squirrel self doctor

# 3. 第一次审计：先用最小代价跑通
squirrel audit https://你的站.example.com -C quick -m 25

# 4. 拿到能喂给 Agent 或 CI 的报告
squirrel audit https://你的站.example.com -f llm  -o report.xml    # 编码 Agent
squirrel audit https://你的站.example.com -f json -o report.json   # CI
squirrel audit https://你的站.example.com -f html -o report.html   # 给人看
```

接进 CI 做发版门禁：

```bash
squirrel audit https://staging.example.com -C quick -m 40 \
  --fail-on 'score<90,severity>=error,score:perf<80'
# 退出码：0 通过 / 2 门槛触发（质量回归）/ 1 运维性错误
```

让编码 Agent 自己驱动「审 → 修 → 重审」：

```bash
npx skills add squirrelscan/squirrelscan   # 装官方 Skill
squirrel mcp                               # 或挂本地 MCP，无需账号
```

详细步骤按下面三份参考文件分工：

| 文件 | 内容 |
|---|---|
| `references/install-and-first-audit.md` | 安装与验证、第一次审计怎么收窄范围、输出落在哪、staging/localhost/staging 鉴权、命令速查 |
| `references/rules-and-reports.md` | 规则按 4 个评分组 + 20 多个类别的分法、类别代码、健康分算法与扣分项、7 种报告格式、JSON 字段解读 |
| `references/ci-and-fix-loop.md` | 退出码语义、GitHub Actions / GitLab / 通用 runner 配置、`--fail-on` 表达式、修复分批策略、推荐 `squirrel.toml` |

---

## 依赖

| 项 | 说明 |
|---|---|
| 命令行 | `squirrel`（包名 `squirrelscan`），零依赖单文件二进制；或 Node 18+ 环境下的 npm 包 |
| 操作系统 | macOS / Linux / Windows，x64 或 arm64 |
| Alpine / musl Linux | 需要 `libstdc++`，root 下安装脚本会自动补，否则先 `apk add libstdc++` |
| 磁盘 | 本地 SQLite 缓存与审计历史，默认每项目保留最近 3 次审计（`[storage] keep_audits`） |
| 账号 / Key | 纯本地审计不需要；云端渲染 / AI 分析 / 技术栈识别 / 发布报告才需要账号，凭证走 `SQUIRRELSCAN_API_KEY` |
| 上游仓库 | https://github.com/squirrelscan/squirrelscan （MIT，独立于本 Skill 的第三方项目） |

本 Skill 只提供使用说明与流程编排，**不打包、不修改、不重新分发上游的任何代码或二进制**。

---

## 安全

- 不内嵌任何密钥。使用云端功能时的 API Key 请放在环境变量 `SQUIRRELSCAN_API_KEY`，不要写进 SKILL.md、脚本源码或提交记录。
- **主动爬取**：工具会对目标站点发起真实请求（首页、站内链接、`robots.txt`、`sitemap.xml`、页面引用的静态资源、站外链接）。请在授权范围内使用，并给目标站设定合理的页数、深度、并发与 `delay_ms`。
- **默认不遵守 robots.txt**（`respect_robots = false`），官方理由是「审计由站主发起」。对非自有站点，这个默认值不成立，必须先改回 `true`。
- `-H` 传入的请求头值在输出中会被脱敏，但仍会留在你的 shell 历史里；生产凭证建议用环境变量拼接。
- 登录且在线时审计**默认自动发布为 unlisted 报告**；CI 与 Agent 场景建议 `--no-publish` 或在配置里写 `[cloud] publish = false`。`--offline` 可一次性关掉全部云端调用、发布与遥测。
- `localhost`、回环、私有网段与 `.local` / `.internal` 这类内部主机**永远不会被上传到云端**——云端既够不到也渲染不了。
- 安全类规则是配置与暴露面检查（响应头、混合内容、泄漏密钥、挂马特征等），**不构成渗透测试或漏洞扫描**，不能作为安全合规的唯一依据。

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：squirrelscan（MIT）

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
