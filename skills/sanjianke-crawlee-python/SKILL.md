---
name: sanjianke-crawlee-python
slug: sanjianke-crawlee-python
displayName: 三剪客 · Python 网页抓取框架
description: "crawlee-python：把网页抓取从手写请求循环升级成配置一个爬虫——HTTP 与无头浏览器统一接口、自动并发与重试、请求队列去重、代理轮换，抓到的数据按数据集落盘。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "crawlee-python 的安装与选型、BeautifulSoup / Parsel / Playwright 三种爬虫、路由与去重、数据集与键值存储、代理与会话、并发与限流配置，以及浏览器依赖、屏蔽、内存、断点续爬等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 爬虫
  - 数据分析
---

# 三剪客 · Python 网页抓取框架

抓一个站点的难点很少在"发请求"，而在后面那一长串脏活：链接去重、并发控制、失败重试、被封了换代理、抓到一半崩了不想从头再来、结果要规整地落盘。crawlee-python 就是把这堆事做成默认行为的抓取框架。

它提供三种爬虫类，**接口完全一致**：`BeautifulSoupCrawler`（HTTP + BeautifulSoup）、`ParselCrawler`（HTTP + Parsel，CSS 选择器风格）、`PlaywrightCrawler`（真无头浏览器）。这意味着你可以先用快的跑，遇到需要渲染 JS 的页面再换成 Playwright 版本，处理逻辑基本不用改。

爬虫跑起来时会在当前目录创建 `storage/`，数据默认落到 `storage/datasets/default/` 下一个一个 JSON 文件，队列和断点状态也在里面。

**上游项目**：`crawlee-python`　**仓库**：https://github.com/apify/crawlee-python

> 版本信息：PyPI 上当前包名为 `crawlee`，本 Skill 撰稿时 PyPI 元数据显示版本为 1.10.0、要求 Python 3.10+。文档站默认展示 1.10 一线。具体以你安装到的版本与官方文档为准。

## 什么时候用 / 不用

**用它**：

- "我要抓几百上千个页面，还要跟着链接递归爬。"——内置请求队列，`context.enqueue_links()` 把页面上的链接自动排队并去重。
- "有的页面静态 HTML 就够，有的是 JS 渲染的。"——三种爬虫同一套接口，静态页面用 `BeautifulSoupCrawler` / `ParselCrawler`，渲染页用 `PlaywrightCrawler`。
- "被限速 / 被封 IP 了。"——内置自动重试、会话与代理轮换的配置入口。
- "抓一半网络断了，不想从零重来。"——队列和已处理请求有持久化，重启后可以从已有状态继续。
- "不同页面要用不同解析逻辑。"——路由器（router）可以把 URL 模式映射到不同的处理器函数。
- "抓到的数据希望能直接给下游用。"——`context.push_data()` 写进数据集，同时还能用键值存储放截图、文件等非表格产物。

**不要用它**：

- **只抓一个固定 URL 的接口返回的 JSON**——直接 `httpx` / `requests` 一行就够，不必引入完整框架和 `storage/` 目录。
- **大规模分布式抓取、要自己管队列与调度**——crawlee-python 是单进程内的 asyncio 调度；跨机器的编排要靠外部平台或自己的调度层。
- **需要模拟复杂登录流程、验证码识别、指纹对抗到极致**——框架给了浏览器与代理能力，但验证码破解、商业级指纹伪装不在它范围内（有对手方指纹库的接入点，不保证过所有风控）。
- **要抓的目标站点明确禁止抓取，或数据涉及个人隐私、版权内容**——换什么框架都不该抓；先看目标站点条款与 robots、当地法规。
- **纯数据加工与分析**——爬完之后的清洗、聚合、建模请交给 pandas / polars / SQL 引擎。
- **只想要一个短生命周期的脚本、依赖越少越好**——`crawlee[all]` 会拉进浏览器与较多依赖；这种场景用轻量 HTTP 客户端更合适。

## 安装

要求 Python 3.10 或更高。

```bash
# 全功能安装（含浏览器、解析库等全部 extras）
python -m pip install 'crawlee[all]'

# 只装需要的部分（依赖更少、体积更小）
python -m pip install 'crawlee[beautifulsoup]'    # BeautifulSoupCrawler
python -m pip install 'crawlee[parsel]'           # ParselCrawler
python -m pip install 'crawlee[playwright]'       # PlaywrightCrawler
```

用浏览器爬虫还要单独装浏览器二进制：

```bash
playwright install
```

验证安装：

```bash
python -c 'import crawlee; print(crawlee.__version__)'
```

用官方 CLI 脚手架起模板项目（需要 `uv`）：

```bash
uvx 'crawlee[cli]' create my-crawler
# 已经装了 crawlee 的情况下
crawlee create my-crawler
```

## 常用操作

**1. 最小可跑：HTTP 爬虫抓标题（不需要浏览器）**

```python
import asyncio

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext


async def main() -> None:
    crawler = BeautifulSoupCrawler(max_requests_per_crawl=10)

    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        context.log.info(f'Processing {context.request.url} ...')
        await context.push_data({
            'url': context.request.url,
            'title': context.soup.title.string if context.soup.title else None,
        })
        await context.enqueue_links()

    await crawler.run(['https://crawlee.dev'])


if __name__ == '__main__':
    asyncio.run(main())
```

`max_requests_per_crawl` 是安全阀，测试时先给个小数字，别一上手就全站递归。

**2. 换成无头浏览器（页面内容靠 JS 生成时）**

```python
import asyncio

from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext


async def main() -> None:
    crawler = PlaywrightCrawler(max_requests_per_crawl=10)

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        await context.push_data({
            'url': context.request.url,
            'title': await context.page.title(),
        })
        await context.enqueue_links()

    await crawler.run(['https://crawlee.dev'])


if __name__ == '__main__':
    asyncio.run(main())
```

开发和调试时把窗口显示出来、或换浏览器内核：

```python
crawler = PlaywrightCrawler(
    headless=False,          # 显示浏览器窗口，方便观察卡在哪一步
    browser_type='firefox',  # 默认是 chromium
)
```

**3. 按 URL 模式分流到不同处理器（路由器）**

```python
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

crawler = BeautifulSoupCrawler()


@crawler.router.default_handler
async def default_handler(context: BeautifulSoupCrawlingContext) -> None:
    await context.enqueue_links()


@crawler.router.handler(label='detail')
async def detail_handler(context: BeautifulSoupCrawlingContext) -> None:
    await context.push_data({'url': context.request.url, 'html_len': len(str(context.soup))})
```

`Router.handler` 的签名是 `handler(label)`，所有请求会先找 label 完全一致的处理器，找不到才落到 `default_handler`。入队时给请求打标签（`Request.from_url(url, label='detail')` 或入队方法的 label 参数）。路由器还支持 `@router.use` 注册中间件，在每个请求进入处理器前执行。

**4. 精准入队、控制深度与范围**

```python
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

crawler = BeautifulSoupCrawler()


@crawler.router.default_handler
async def handler(context: BeautifulSoupCrawlingContext) -> None:
    # 只入队同域链接，避免爬出目标站点
    await context.enqueue_links(strategy='same-domain')
    # 也可以逐条精确入队（enqueue_links 的详细参数以官方 API 参考为准）
    await context.add_requests(['https://example.com/detail/1'])
```

过滤与去重交给框架，不要自己在处理器里维护 `set()` —— 那样重启就丢，也挡不住并发重复。`enqueue_links` 支持的策略名与全部参数、以及按 label 入队的确切写法，请以官方 API 参考页为准。

**5. 看抓到的结果**

```bash
cat ./storage/datasets/default/000000001.json
```

默认存储根目录是当前工作目录下的 `./storage`，要换位置设环境变量：

```bash
export CRAWLEE_STORAGE_DIR=/data/my-crawl-storage
```

**6. 代理与会话（被限速 / 需要保登录态时）**

代理轮换与浏览器指纹能力的接入点在对应的 extra 里，具体配置项按官方文档的 proxy / session 章节写，因为选项名与默认值随版本演进较快。实践上的顺序是：先确认真的是被限速（不是解析写错），再把并发降下来、加上请求间隔，最后才上代理。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `ImportError` / 提示缺少 beautifulsoup、parsel 或 playwright | `crawlee` 本体只装核心，解析与浏览器能力在 extras 里 | 按爬虫类型装对应 extra：`crawlee[beautifulsoup]`、`crawlee[parsel]`、`crawlee[playwright]`，或直接 `crawlee[all]` |
| `PlaywrightCrawler` 启动就报找不到浏览器可执行文件 | 装了 Python 包但没装浏览器二进制 | 在同一个环境里执行 `playwright install`（首次装会下载较大文件） |
| 抓到的 HTML 是对的，但目标数据是空的 | 页面靠 JS 渲染，HTTP 爬虫拿到的是初始骨架 | 换 `PlaywrightCrawler`；只有个别字段需要渲染时，也可以在主流程里用 HTTP 爬虫、仅对特定 URL 用浏览器 |
| 跑完发现重复数据 / 同一个 URL 抓了两遍 | 自己在处理器里入队时出现了不同形式的同一 URL（带不带尾斜杠、query 参数顺序不同），框架的默认去重判不出"逻辑上同一个" | 入队前统一 URL 规范化（`unique_key` 也可以自定义），不要在处理器里手动维护去重集合 |
| 重跑一次，`storage/` 里的旧数据还在，结果混在一起 | 默认存储是可持久化的，不是每次清空 | 需要干净结果时，跑前清掉对应目录或换 `CRAWLEE_STORAGE_DIR`；调试时可以给本次运行单独指定目录 |
| 开着浏览器并发一大就内存飙升、机器卡死 | 每个浏览器上下文都占内存，默认并发是按系统资源自动决定的 | 显式收紧并发与每爬请求数；先用小样本量测出单页内存占用，再算能开多少并发 |
| 目标站点返回 403 / 429 或跳验证码页 | 触发了风控：请求频率、IP、请求头特征被识别 | 降并发、加请求间隔、补正常请求头；仍不行再上代理轮换。**不要试图绕过依法受限的访问控制** |
| 爬虫停不下来 / 一直在抓外链 | 默认入队会把页面上找到的链接都排队，容易爬出目标站点 | 用入队时的范围策略把抓取限制在同域 / 同主机（策略名以官方 API 参考为准），并设置 `max_requests_per_crawl` 上限 |
| 程序被 Ctrl+C 杀掉后 `storage/` 状态混乱或下次启动行为异常 | asyncio 与浏览器进程没有走完正常的清理流程 | 让 `crawler.run()` 自然结束或用框架提供的停止方式；生产环境用信号处理优雅退出，别直接 kill |
| 脚本在 Windows 上跑起来各种奇怪报错，或在 IDE 里不执行 | asyncio 事件循环在 Windows 与某些交互式环境下的行为差异 | 入口统一写 `asyncio.run(main())` 放在 `if __name__ == '__main__':` 里；用 Playwright 时避免在不支持子进程的环境（如某些在线 notebook）里跑 |
| 请求偶发失败，日志里重试了好几次 | 框架会自动重试失败请求，这是设计行为不是故障 | 区分"会自愈的瞬时错误"和"必然失败的 404 / 解析错误"，把后者在处理器里显式标记为跳过，别让它一直重试 |
| 抓取结果的 JSON 里字段顺序或类型不稳定 | `push_data()` 支持字典或 Pydantic 模型；随手塞的 dict 没有 schema 约束 | 用 Pydantic 模型定义输出结构（框架支持），字段类型与必填项就固定了 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 抓取目标网页、下载资源；爬虫的核心能力 |
| 读取文件 | 是 | 从 `storage/` 读回队列状态与已有数据集（断点续爬） |
| 写入文件 | 是 | 结果数据集、请求队列、键值存储都写到本地 `storage/` 目录（位置可用 `CRAWLEE_STORAGE_DIR` 改） |
| 凭证 | 视情况 | 抓公开页面不需要。需要登录态、代理认证、或部署到云平台跑时，会用到账号与密钥，请走环境变量或密钥服务 |
| 子进程 / 后台常驻 | 是 | `PlaywrightCrawler` 会拉起浏览器进程；抓取任务通常长时间运行，需要并发与内存预算 |
| 执行本地代码 | 是 | 爬虫处理器是普通 Python 代码，运行在本地；只应执行你自己写的逻辑 |

## 触发场景

- "帮我写个爬虫，把这个站点的商品列表和详情都抓下来。"
- "这个列表页是 JS 渲染的，普通请求抓不到内容。"
- "抓了两千条就断了，能不能接着上次的位置继续。"
- "请求太快被限速了，怎么控制频率、换个 IP。"
- "抓到的字段想统一成固定结构再存成 JSON / 数据库。"
- "怎么把抓取结果直接输出成 csv / jsonl 给分析用。"
- "网页数据要定期抓，怎么做成能重复跑的任务。"

## 能力边界

**覆盖**：

- **抓取方式**：HTTP 抓取（`BeautifulSoupCrawler` / `ParselCrawler`）与无头浏览器抓取（`PlaywrightCrawler`，支持切换浏览器内核），三类爬虫共用同一套接口与上下文
- **调度与可靠性**：请求队列（含持久化）、URL 去重、自动并发控制、失败自动重试、状态保存与断点续爬
- **路由**：按 label 把请求分派到不同处理器，另有默认处理器兜底
- **数据落地**：数据集（表格型结果，默认逐条 JSON）、键值存储（文件类产物），存储位置与实现可配置
- **网络层**：会话与代理轮换的接入、请求头定制
- **工程化**：完整类型标注、官方的 CLI 模板脚手架、可选的 OpenTelemetry 接入
- 输出结构可以用 Pydantic 模型约束

**不覆盖**：

- **验证码识别、商业级反爬对抗**——框架提供浏览器与代理能力，但不提供验证码破解，也不保证通过所有风控
- **跨机器的分布式调度**——它是单进程 asyncio 内的调度；要分布式得靠外部平台或自建编排
- **数据清洗、聚合与建模**——抓完之后的加工不在范围内
- **HTML 之外的文档解析**——PDF、Word、Excel 之类要另外的库（`crawlee` 可以帮你把文件下下来，解析要你自己做）
- **数据库写入**——结果默认落 JSON 文件；写入数据库要自己在处理器里接驱动（有 SQL storage 相关 extra，但属于可选集成）
- **合法性审查**——不会替你判断目标站点是否允许抓取。robots、服务条款、个人信息保护、版权边界都需要使用者自己核

## 依赖条件

- Python 3.10 或更高（PyPI 元数据要求 `>=3.10`）
- `pip install 'crawlee[all]'`，或按需装 `beautifulsoup` / `parsel` / `playwright` 等 extra
- 用浏览器爬虫需额外执行 `playwright install` 安装浏览器二进制（磁盘占用较大）
- 用官方脚手架需先装 `uv`
- 不需要账号或 API Key；抓取公开页面无需任何凭证。要用代理或部署到云平台才涉及凭证

## 已知限制

1. 核心包不含解析与浏览器能力，必须选装 extras，装错 extra 会在导入或运行时才暴露。
2. `PlaywrightCrawler` 的资源开销远高于 HTTP 爬虫：内存、CPU、磁盘（浏览器二进制）都要按并发数规划。
3. 默认存储是可持久化的 `./storage`，重复运行会累积数据，需要自己管理目录生命周期。
4. 默认入队策略可能爬出目标站点范围，必须用策略参数与请求上限约束。
5. 它是单进程 asyncio 调度，不是分布式爬虫框架；横向扩展要在架构层解决。
6. 代理轮换、会话、指纹相关选项在版本间演进较快，具体参数名请以官方文档和你安装的版本为准。
7. 目标站点的反爬策略会变化，今天是可抓的明天可能要调整，这类维护成本无法被框架消除。

## 自检清单

执行前：

- [ ] 确认抓取行为合法合规：目标站点的服务条款、robots、版权与个人信息边界都核过
- [ ] 先只抓 1~5 个 URL 验证选择器与流程，再放开递归
- [ ] 给 `max_requests_per_crawl` 设了明确上限，并用 `strategy` 限制抓取范围（别爬出站）
- [ ] 用浏览器爬虫时确认 `playwright install` 已在同一环境执行过
- [ ] 想清楚 `storage/` 放在哪、要不要清空，避免污染上一次的结果
- [ ] 并发与内存预算评估过（尤其多浏览器实例的场景）

执行后：

- [ ] 检查数据集条数与预期量级是否一致，有没有明显缺失
- [ ] 抽查几条结果的字段是否完整、编码是否正常（中文页面特别注意）
- [ ] 看日志里的失败与重试情况，确认没有整类页面被静默跳过
- [ ] 确认浏览器 / 子进程都已经退出，没有残留进程占内存
- [ ] 确认落盘的数据里没有误抓到敏感信息

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/apify/crawlee-python | 上游仓库（安装与完整文档以它为准） |
| https://crawlee.dev/python/docs/quick-start | 官方快速上手：三种爬虫、安装、结果目录 |
| https://crawlee.dev/python/docs/examples | 官方示例集：各类抓取场景 |
| https://crawlee.dev/python/api | 官方 API 参考：爬虫类与上下文配置项 |

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
