---
name: sanjianke-pyspider
slug: sanjianke-pyspider
displayName: 三剪客 · 分布式爬虫调度系统
description: "pyspider：分布式爬虫调度系统的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "pyspider：分布式爬虫调度系统的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 爬虫
  - 数据分析
---

# 三剪客 · 分布式爬虫调度系统

它把「写爬虫」和「管爬虫」拆成两层：你只写一个 Python Handler 类，调度、去重、重试、定时重爬、
结果入库，以及一个带脚本编辑器、任务监控、项目管理、结果查看的网页控制台，都由它包掉。
要采的站多、要按天按周反复爬、还要在浏览器里看任务状态时，用它能省掉自己搭调度和界面那一大摊。

**上游项目**：`pyspider`　**仓库**：https://github.com/binux/pyspider

## 什么时候用 / 不用

**用它**：

- 你要一个自带网页控制台的爬虫系统：能在线写脚本、立刻试跑、看任务队列和抓到的结果。
- 你要按固定周期反复爬同一批站点，需要内置的定时、重试、优先级、按时间重爬这些调度能力。
- 你要把抓取节点横向扩出去，愿意接消息队列和数据库，把抓取、调度、结果落库拆成独立进程。
- 你手上有一个已经用它的团队或环境，需要有人在现有基础上加目标、改 Handler。
- 你要的是「写完就能在浏览器里盯着跑」的开发体验，而不是先花几天自建调度。

**不要用它**：

- 你新建项目、且可以自由选型。它已经多年没有更新，官方包的最后一次发布停在 2018 年，新项目从维护性更好的框架起步更稳。
- 你要求安全审计或对外发布访问。WebUI 默认没有认证且能执行命令，官方包还存在两个未修补的公开漏洞，暴露到公网等同于把机器交出去。
- 你跑在较新的 Python 上，又不愿意处理依赖版本冲突。它对运行环境有历史版本要求，装起来要额外做兼容工作。
- 你只需要抓几个静态页面。为这个部署控制台、数据库和消息队列，比直接写几十行 `requests` 重得多。
- 你指望它自动过验证码、过风控、过登录墙。这些都不在它的能力范围里。

## 安装

```bash
# 官方给的路径就两步：装包，起服务，开控制台
pip install pyspider
pyspider
# 浏览器打开 http://localhost:5000/
```

```bash
# 强烈建议装在独立虚拟环境里：它的依赖有历史版本约束，混进主环境容易和别的包打架
python -m venv .venv
.venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pyspider
```

```bash
# 生产 / 隔离环境用容器起（官方文档有专门的 Docker 运行页面）
# 具体镜像名与挂载方式以官方文档和仓库说明为准，不要照抄记忆里的参数
```

```bash
# 先看自己这版到底支持哪些开关——参数名以实际上这条命令的输出为准
pyspider --help
pyspider all --help
```

如果 `pip install` 因为依赖版本冲突装不上，官方包在 PyPI 上的最新版本是 0.3.10（2018 年 4 月发布），
对 Python 的支持范围写的是 2.6–3.6；具体某台机器能不能装通，以 `pip` 的实际报错和官方文档为准。

## 常用操作

```bash
# 1. 在一个进程里把所有组件跑起来（开发/单机用），默认 WebUI 在 5000 端口
pyspider all
```

```bash
# 2. 调试模式：不起 WebUI，结果直接打到标准输出，方便对着一个脚本调
pyspider one
pyspider one > result.txt

# 交互模式，可以手工指定要抓的 URL
pyspider one -i
```

```bash
# 3. 用配置文件把各个组件参数一次给全（JSON，键名即子命令名）
cat > config.json <<'EOF'
{
  "taskdb": "mysql+taskdb://user:passwd@host:port/taskdb",
  "projectdb": "mysql+projectdb://user:passwd@host:port/projectdb",
  "resultdb": "mysql+resultdb://user:passwd@host:port/resultdb",
  "message_queue": "redis://host:6379/db",
  "webui": {
    "username": "some_name",
    "password": "some_passwd",
    "need-auth": true
  }
}
EOF
pyspider -c config.json all
```

```bash
# 4. 分布式：调度器全局只允许一个，抓取/处理/结果落库可以多个
pyspider -c config.json scheduler
pyspider -c config.json fetcher --poolsize 100 --proxy "host:port"
pyspider -c config.json processor
pyspider -c config.json result_worker
```

```bash
# 5. 给 WebUI 加认证（务必开，默认是裸奔的）
pyspider -c config.json webui --need-auth --username some_name --password some_passwd
```

```python
# 6. Handler 的最小骨架：on_start 定时触发，self.crawl 指回调，回调里再翻页 / 返回结果
from pyspider.libs.base_handler import *


class Handler(BaseHandler):
    crawl_config = {
    }

    @every(minutes=24 * 60)
    def on_start(self):
        self.crawl('http://example.com/', callback=self.index_page)

    @config(age=10 * 24 * 60 * 60)
    def index_page(self, response):
        for each in response.doc('a[href^="http"]').items():
            self.crawl(each.attr.href, callback=self.detail_page)

    def detail_page(self, response):
        return {
            "url": response.url,
            "title": response.doc('title').text(),
        }
```

```bash
# 7. 压测模式：用内存 SQLite 跑基准，评估这台机器的抓取吞吐
pyspider bench --total 10000 --show 100
```

各子命令的可用选项以 `pyspider <子命令> --help` 的输出为准；上面没列到的选项不要凭记忆传。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 控制台在公网上能直接打开，且能执行命令 | WebUI 默认没有认证，官方在说明里直接写了这一点 | 只在内部网络使用，或必须打开需要认证的开关；绝不要直接暴露到公网 |
| 明明只跑在本地，仍被提示有漏洞 | 官方包最新版（0.3.10）存在两个未修补的公开漏洞：`/update` 的跨站脚本问题与 Flask 端点的跨站请求伪造问题 | 别把 WebUI 开放给不可信网络；需要长期使用就自己评审代码后再决定，官方没有修复版本 |
| 装到一半报依赖版本冲突 | 依赖有历史版本约束，主环境里的新版本会顶掉它需要的旧版本 | 用独立虚拟环境甚至容器隔离；不要为了装上而在主环境里乱降版本 |
| 单机能跑，多机扩不出去 | 默认用内存 SQLite 加内置进程内队列，只能在本进程内共享 | 显式配置 `taskdb` / `projectdb` / `resultdb` 与 `message_queue`，把各组件拆成独立进程 |
| 浏览器里看不到项目 / 跑完拿不到结果 | 结果库没配好，或抓取回调没有把数据交出去 | 检查 `resultdb` 连接串；确认脚本的 `detail_page` 之类回调确实 `return` 了数据 |
| 换了数据库的 URL 却仍在写本地文件 | 各数据库有固定 URL 写法，写错会退回默认存储 | 按官方命令行文档给的写法填；SQLite 的相对路径、绝对路径、内存库写法各不相同 |
| `one` 模式下打不开控制台 | `one` 模式为了调试把组件跑在一个进程里，官方明确说明不包含 WebUI | 要看控制台就用 `all`，或按组件分别启动 `scheduler` / `fetcher` / `processor` / `webui` |
| 页面里的动态内容抓不到 | 需要额外的渲染服务，它不会自动渲染 JavaScript | 按官方文档启用渲染相关组件；这条链路依赖的浏览器组件已经过时，请评估是否值得 |
| 调度器开了两个，任务状态错乱 | 调度器是全局唯一的，官方明确「只允许一个」 | 只保留一个 `scheduler`，横向扩的是抓取与处理进程 |
| 按 README 描述去找可视化抓取界面 | 官方把可视化抓取界面列在待办里，属于尚未实现的功能 | 只能自己写 Handler 脚本；别按截图去猜有这个功能 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 抓取目标站点；接入远程数据库与消息队列（MySQL / MongoDB / Redis / PostgreSQL / Elasticsearch / RabbitMQ 等） |
| 读取文件 | 是 | 读取配置文件、脚本文件、SQLite 数据文件与日志 |
| 写入文件 | 是 | 写结果库与任务库、导出结果、写日志与数据目录（`--data-path`） |
| 凭证 | 是 | 数据库与消息队列的连接串含账号密码；WebUI 认证另需用户名口令，务必开启 |
| 子进程 / 后台常驻 | 是 | 抓取、处理、结果落库、调度、WebUI 都是可独立常驻的组件；内置子进程模式与渲染组件都会拉起额外进程 |
| 执行任意脚本 | 是 | WebUI 的脚本编辑器可执行 Python 代码、可调用命令，权限等于运行它的系统账号——这是它最大的风险面 |

## 触发场景

- 「有没有带网页界面的爬虫框架，能在线写脚本、在线看结果」
- 「同一批站点要每天定时重爬，任务队列和重试帮我管起来」
- 「抓取量上来了，想加几台机器一起抓，怎么拆调度和抓取」
- 「我需要一个能看任务状态和抓取结果的控制台」
- 「现成项目里用的是这个爬虫系统，帮我加个新目标站」
- 「内存 SQLite 不够用了，帮我换成 MySQL / MongoDB 存任务和结果」

## 能力边界

**覆盖**：

- 用 Python 写抓取脚本：一个 Handler 类 + 回调函数，`self.crawl` 发任务，回调里翻页或返回数据。
- 自带网页控制台：脚本编辑器、任务监控、项目管理、结果查看。
- 调度能力：任务优先级、重试、周期性执行、按时间重爬。
- 可换存储后端：MySQL、MongoDB、Redis、SQLite、Elasticsearch，以及用 SQLAlchemy 接 PostgreSQL。
- 可换消息队列：RabbitMQ、Redis、Beanstalk、Kombu；默认是进程内队列。
- 分布式形态：调度、抓取、处理、结果落库可拆成独立进程分别部署。
- 静态页与动态页：内置 CSS 选择器与 XPath 风格的响应取数，另有渲染服务用于 JavaScript 页面。

**不覆盖**：

- 可视化抓取界面：官方把「类似可视化抓取工具」列在待办清单里，属于未实现功能。
- 长期安全维护：官方包最新版 0.3.10 停在 2018 年，且带两个未修补的公开漏洞（`/update` 跨站脚本、Flask 端点跨站请求伪造），没有修复版本。
- 现代 Python 的即装即用：对 Python 版本的支持写的是 2.6–3.6，新环境需要额外做兼容处理。
- 自动过验证码、绕过风控与登录墙：这些要你自己在脚本层解决。
- 浏览器渲染的开箱体验：渲染链路依赖的组件已经过时，需要自备并单独维护。
- 抓完之后的清洗、建模、可视化：结果只是存下来，后续处理不在范围内。

## 依赖条件

- Python 环境；官方包在 PyPI 上的最新版本是 0.3.10（发布于 2018 年 4 月），支持范围写的是 Python 2.6–3.6。
- 运行依赖有历史版本约束：直接装到较新的 Python 环境里常会遇到冲突，建议用独立虚拟环境或容器隔离。
- 默认零外部依赖也能跑：任务库 / 项目库 / 结果库用 SQLite，消息队列用进程内队列；但这只适合单机开发。
- 要分布式或要持久化，需要自备数据库（MySQL / MongoDB / Redis / SQLite / PostgreSQL / Elasticsearch）与消息队列（RabbitMQ / Redis / Kombu）。
- 要渲染 JavaScript 页面，需要按官方文档额外启用渲染组件并准备对应的浏览器运行环境。
- 官方文档站与仓库是参数与写法的唯一出处；具体选项以 `pyspider --help` 与各子命令 `--help` 为准。

## 已知限制

- 项目定位是 Beta 阶段且已停止更新：官方包最后一次发布在 2018 年 4 月，之后没有新版本。
- 两个公开漏洞没有修复版本：CVE-2024-39162（`/update` 跨站脚本）与 CVE-2024-39163（Flask 端点跨站请求伪造）。相关公告明确指出，这些漏洞影响的正是已不再被维护的产品。
- WebUI 默认无认证，且能拿来执行任意命令——它的定位是内部工具，不是能对外发布的系统。
- 对新版 Python 的支持没有保证，装通与否取决于依赖能否被解析。
- 分布式之前必须先配好数据库和消息队列，否则扩出来的进程之间没有共享状态。
- 官方 README 里的可视化抓取界面仍在待办清单中，不要按想象去找这个功能。

## 自检清单

- 这是新项目吗？如果是，先确认在维护性上能接受「多年未更新 + 无修复版本」这个前提。
- WebUI 会暴露给谁？只能内网访问，且必须打开认证开关。
- Python 版本是多少？装之前先建好独立虚拟环境，避免污染主环境。
- 单机还是分布式？要横向扩就必须先配 `taskdb` / `projectdb` / `resultdb` 和 `message_queue`。
- 数据库连接串是按官方文档写法填的吗？写错会退回默认本地存储。
- 调度器是不是只起了一个？它全局唯一。
- 目标页是 JavaScript 渲染的吗？如果是，先确认渲染链路能不能在你这台机器上跑起来。
- 抓不到结果时，检查过回调有没有真的 `return` 数据、结果库有没有写进去吗？
- 有没有把数据库密码、WebUI 口令写进了会进版本库的文件？

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/binux/pyspider | 上游仓库（安装与完整文档以它为准） |

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
