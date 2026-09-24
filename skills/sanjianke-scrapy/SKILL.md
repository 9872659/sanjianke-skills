---
name: sanjianke-scrapy
slug: sanjianke-scrapy
displayName: 三剪客 · Python 网页抓取框架
description: "scrapy：Python 网页抓取框架 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "scrapy：Python 网页抓取框架 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 爬虫
  - 数据分析
---

# 三剪客 · Python 网页抓取框架

写爬虫最难的不是取数据，而是并发、重试、去重、限速、断点这些脏活。它把这些都做成了框架的一部分：你只写"抓哪个 URL、从哪里取字段、下一页在哪"，剩下的调度、并发、编码探测、结果落盘由框架负责。想批量抓一个站点、还要求抓得稳又有礼貌，它是 Python 里最省事的那条路。

**上游项目**：`scrapy`　**仓库**：https://github.com/scrapy/scrapy

## 什么时候用 / 不用

**用它**：

- 用户要写一个抓取任务，涉及的页面数量不是一两个，需要并发和失败重试。
- 需要遵循爬取礼仪：请求间隔、单域名并发上限、robots.txt、自动限速。
- 要把抓到的结构化数据导出成 JSON / JSONL / CSV / XML，或写进数据库。
- 需要 CSS / XPath 选择器提取，并用交互式 shell 现场试表达式。
- 任务是"从列表页翻到详情页"这种典型的多层爬取结构。
- 需要下载图片等媒体文件，或从 Sitemap、XML/CSV feed 复用现成的抓取器。
- 抓取逻辑要长期维护，希望有项目结构、可复用组件和契约测试。

**不要用它**：

- 只是要抓一两个页面取几个字段，写个 requests 脚本几十行就够了，引入框架反而重。
- 页面内容完全由浏览器 JS 动态渲染，且没有可用的接口——它本身不是浏览器，需要额外接渲染方案。
- 需要的是登录态的复杂交互、验证码、浏览器行为模拟——这类场景用浏览器自动化更直接。
- 部署环境不允许自由装依赖，或有严格的内存/进程限制——它依赖 Twisted、lxml、cryptography 等一整套。
- 目标站点明确禁止抓取，或抓取行为不合规——工具再顺手也不能改变这一点。
- 需要图形化配置、不想写代码——它是框架不是低代码采集器。

## 安装

要求 Python 3.10+，CPython 或 PyPy 均可。

**PyPI（推荐放进虚拟环境）**：

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install Scrapy
```

**conda（Windows 上更省事，官方推荐）**：

```bash
conda install -c conda-forge scrapy
```

**按需安装可选 extras**：

```bash
pip install scrapy[s3,images]     # 例：S3 存储 + 图片管道
```

可用的 extras 包括 `bpython`、`color`、`gcs`、`httpx`、`images`、`ipython`、`ptpython`、`robotparser`、`s3`、`twisted-http2`、`uvloop`。

**平台注意事项**：

- Windows 走 pip 需要 Microsoft Visual C++ 构建工具，磁盘占用明显高于 conda 方案。
- Ubuntu / Debian 需要先装非 Python 依赖：

```bash
sudo apt-get install python3 python3-dev python3-pip libxml2-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev
```

- macOS 需要 Xcode 命令行工具（`xcode-select --install`），并建议用 homebrew 装 Python 而不是系统 Python。
- 系统包管理器里那个老版本不要用，通常远落后于最新发布。
- 装完可以跑 `scrapy bench` 验证环境（PyPy 下若报 `got 2 unexpected keyword arguments`，需要 `pip install 'PyPyDispatcher>=2.1.0'`）。

## 常用操作

**1. 创建项目**

```bash
scrapy startproject myproject
cd myproject
```

生成的目录结构：`scrapy.cfg` 加项目包（内含 `items.py`、`middlewares.py`、`pipelines.py`、`settings.py`、`spiders/`）。

**2. 生成爬虫骨架**

```bash
scrapy genspider example example.com            # 默认 basic 模板
scrapy genspider -t crawl scrapyorg scrapy.org  # crawl 模板
scrapy genspider -l                             # 看有哪些模板：basic / crawl / csvfeed / xmlfeed
```

**3. 写一个最小爬虫并运行**

```python
import scrapy

class QuotesSpider(scrapy.Spider):
    name = "quotes"
    start_urls = ["https://quotes.toscrape.com/tag/humor/"]

    def parse(self, response):
        for quote in response.css("div.quote"):
            yield {
                "author": quote.xpath("span/small/text()").get(),
                "text": quote.css("span.text::text").get(),
            }
        next_page = response.css('li.next a::attr("href")').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse)
```

```bash
scrapy runspider quotes_spider.py -o quotes.jsonl   # 不需要项目
scrapy crawl quotes                                 # 在项目内按 name 跑
scrapy crawl -o myfile:csv quotes                   # 追加写入，指定格式
scrapy crawl -O myfile:json quotes                  # 覆盖写入
scrapy crawl -a category=humor quotes               # 传爬虫参数
```

**4. 交互式试选择器**

```bash
scrapy shell "https://quotes.toscrape.com/"
scrapy shell --nolog "https://example.com/" -c '(response.status, response.url)'
```

**5. 调试单个请求**

```bash
scrapy fetch --nolog --headers https://www.example.com/   # 看爬虫实际发出的请求头
scrapy view https://www.example.com/                       # 看爬虫"眼里"的页面
scrapy parse https://www.example.com/ -c parse_item --pipelines   # 用指定回调解析并过管道
scrapy check -l                                            # 列出契约测试
scrapy list                                                # 列出项目里的爬虫
scrapy settings --get BOT_NAME                             # 查某条配置生效值
scrapy version -v                                          # 版本 + Python/Twisted/平台信息
```

**6. 多项目共用一个根目录**

在 `scrapy.cfg` 的 `[settings]` 段里给多个 settings 模块起别名，然后用 `SCRAPY_PROJECT` 环境变量切换：

```bash
export SCRAPY_PROJECT=project2
scrapy settings --get BOT_NAME
```

更多命令与选项以 `scrapy <command> -h` 和官方命令行文档为准。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `AttributeError: 'module' object has no attribute 'OP_NO_TLSv1_1'` | 装/升级 Scrapy、Twisted 或 pyOpenSSL 后版本不匹配，pyOpenSSL 版本超出了 Twisted 支持范围 | 按官方说明重装：`pip install twisted[tls]` |
| Windows 上 pip 安装卡在编译 | 部分依赖没有现成 wheel，需要 C++ 构建工具 | 官方推荐改用 conda-forge 渠道安装；走 pip 就得先装 Microsoft C++ Build Tools（含 MSVC 与 Windows SDK） |
| `crawl` 之类命令报没有活动项目 | `crawl`、`check`、`list`、`edit`、`parse` 是项目内命令，必须在含 `scrapy.cfg` 的目录内跑 | `cd` 到项目根目录再执行；不想建项目就改用 `scrapy runspider <文件>` |
| `-o` 输出里数据越跑越多、重复累积 | `-o` 是追加语义，`-O` 才是覆盖 | 一次性结果用 `-O`；确实要分片追加再用 `-o` |
| 页面拿回来是空壳 / 抓不到内容 | 内容由 JS 动态渲染，HTML 里本来就没有 | 先确认有没有可直接调的接口；否则需要接浏览器渲染方案，别指望改选择器解决 |
| 抓取被站点限流、返回 403 或验证码 | 请求频率过高或行为太像爬虫 | 配 `DOWNLOAD_DELAY`、下调单域名并发、启用 AutoThrottle 扩展，并遵守 robots.txt |
| 自己写了 `parse` 之外的回调但没被调用 | 回调方法名拼错或没通过 `callback` 指定 | 用 `scrapy parse -c <方法名>` 单独验证；`CrawlSpider` 场景检查 `Rule` 配置 |
| 自定义爬虫设置不生效 | `TWISTED_REACTOR` 这类是"预爬虫设置"，在爬虫被加载前就要定好 | 需要换 reactor 时在项目级设置里配，必要时设 `FORCE_CRAWLER_PROCESS = True` |
| 改了模板但 `genspider` 生成的不变 | 自定义模板会整体替换内置模板，不是叠加 | 把要保留的内置模板一并复制到 `TEMPLATES_DIR` 指向的目录；或直接 `-t` 传 `.tmpl` 文件路径 |
| 在爬虫里用 `print` 调试，日志刷得看不清 | 框架自带 logging，调试输出混在日志里 | 用日志配置控制级别；结合 `scrapy shell` 先把表达式试对再写进爬虫 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 下载目标页面、媒体文件，以及导出到 S3 / GCS / FTP 等远端存储 |
| 读取文件 | 是 | 读取项目配置、爬虫代码、本地 Sitemap 与 feed 文件（含 `file://` 协议） |
| 写入文件 | 是 | 落盘抓取结果（JSON/JSONL/CSV/XML）、下载的图片与媒体、日志文件、缓存 |
| 凭证 | 视情况 | 访问需登录的目标站点、写入 S3/GCS 等云端存储时需要；应放在环境变量或本地配置里 |
| 子进程 / 后台常驻 | 是 | 爬取过程本身是常驻的异步进程；`view` 命令会拉起浏览器；部署时可挂到 scrapyd 长期运行 |

## 触发场景

- "帮我写个 scrapy 爬虫，把列表页和详情页的数据都抓下来"
- "scrapy 抓下来是空的，页面像是 JS 渲染的"
- "怎么给 scrapy 配限速和自动节流，别把对方站点打挂"
- "scrapy 的 shell 怎么试 xpath"
- "scrapy 抓到的数据想直接存进数据库"
- "scrapy 装不上 / 报 Twisted 和 pyOpenSSL 的错"

## 能力边界

**覆盖**：

- 异步并发抓取，带失败重试与容错
- CSS 选择器与 XPath 提取，配合正则辅助方法
- 交互式 shell 用于现场调试选择器
- 结果导出为 JSON / JSONL / CSV / XML，并可写到本地、FTP、S3、GCS
- 编码自动探测，能处理不规范或损坏的编码声明
- 中间件、扩展、管道、信号组成的扩展体系
- 内置 Cookie 与会话处理、压缩、认证、缓存、User-Agent、robots.txt、爬取深度限制
- 媒体管道自动下载图片等文件；支持从 Sitemap 与 XML/CSV feed 复用抓取器
- 断点续爬（jobs）、自动限速（AutoThrottle）等运维向能力
- 项目级与全局级命令、自定义命令扩展

**不覆盖**：

- 不内置浏览器内核，不负责执行页面 JS；动态渲染内容需要另接方案
- 不做验证码识别与反爬对抗
- 不做数据清洗、建模与可视化
- 不提供托管采集服务与图形化界面
- 不保证任何站点的抓取合规性，robots.txt 与法律法规的遵守由使用者负责
- 不做分布式集群本身（需要配合外部部署与调度方案）

## 依赖条件

- Python 3.10+（CPython 或 PyPy）
- 核心依赖：lxml、parsel、w3lib、Twisted、cryptography、pyOpenSSL
- 各平台非 Python 依赖：Windows 需 C++ 构建工具（走 pip 时）；Ubuntu 需 libxml2/libxslt/zlib/libffi/libssl 等开发包；macOS 需 Xcode 命令行工具
- 启用远端存储或图片管道等能力时，需装对应 extras
- 长期运行部署通常还需要额外的调度与监控方案

## 已知限制

- 页面渲染依赖浏览器时无能为力，必须自行引入渲染方案并承担额外复杂度
- 初始上手成本高于写一个单文件脚本，小任务用它不划算
- 部分设置是"预爬虫设置"，改换 reactor 之类的配置受加载顺序约束，容易踩坑
- Windows 上 pip 安装体验明显不如 conda 方案
- 系统包管理器提供的版本通常过旧，不建议使用
- 本包不包含框架源码，也不承诺对第三方站点抓取行为的合规性

## 自检清单

- 执行前：确认 Python 版本 >= 3.10，且已装在独立虚拟环境里
- 执行前：确认目标站点的 robots.txt 与使用条款允许抓取，并评估合规性
- 执行前：先用 `scrapy shell` 把选择器试对，再写进爬虫
- 执行前：配置合理的下载延迟与并发上限，必要时启用 AutoThrottle
- 执行后：用 `scrapy list` / `scrapy check` 验证爬虫定义没有问题
- 执行后：检查输出文件里字段是否完整、有没有大量空值或重复项
- 执行后：确认没有把频率打得太高导致对方站点异常或被封

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/scrapy/scrapy | 上游仓库（安装与完整文档以它为准） |

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
