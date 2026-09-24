# 三剪客 · Python 网页抓取框架 Skill

把网页抓取从"手写请求循环"升级成"配一个爬虫"：HTTP 与无头浏览器统一接口、自动并发与重试、请求队列去重、结果自动落盘。

---

## 前置条件

- Python 3.10 或更高（PyPI 元数据要求 `>=3.10`）
- `pip` 可用；用官方脚手架还需先安装 `uv`
- 按爬虫类型选装 extras，核心包不含解析与浏览器能力
- 用 `PlaywrightCrawler` 需额外执行 `playwright install` 安装浏览器二进制
- 抓取公开页面不需要账号或 API Key；用代理或部署到云平台才涉及凭证
- **合规前置**：目标站点的服务条款、robots、版权与个人信息边界需自行核实

---

## 使用

```bash
python -m pip install 'crawlee[all]'
playwright install
python -c 'import crawlee; print(crawlee.__version__)'
```

```python
import asyncio

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext


async def main() -> None:
    crawler = BeautifulSoupCrawler(max_requests_per_crawl=10)

    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        await context.push_data({
            'url': context.request.url,
            'title': context.soup.title.string if context.soup.title else None,
        })
        await context.enqueue_links()

    await crawler.run(['https://crawlee.dev'])


if __name__ == '__main__':
    asyncio.run(main())
```

结果默认写到 `./storage/datasets/default/` 下的 JSON 文件；目录位置可用 `CRAWLEE_STORAGE_DIR` 环境变量改。

`SKILL.md` 里有三种爬虫的选型、Playwright 用法、标签路由、范围控制、代理与会话，以及完整的避坑表。

---

## 依赖

- 运行依赖：`crawlee`（核心）
- 能力型 extras（按需选装）：`beautifulsoup`、`parsel`、`playwright`，或一次性 `all`
- 浏览器二进制：`PlaywrightCrawler` 需要 `playwright install` 下载（磁盘占用较大）
- 脚手架工具：`uv`（用 `uvx 'crawlee[cli]' create` 时）
- 可选集成：Redis、SQL（sqlite / mysql / postgres）存储、OpenTelemetry 可观测性等额外 extras
- 不需要账号、Key 或在线服务即可抓取公开页面

---

## 安全

- 不内嵌任何密钥
- 只在你有权抓取的范围内使用：遵守目标站点服务条款与 robots，不抓取个人信息与受版权保护的内容
- 需要登录态、代理认证或云平台部署时，凭证走环境变量或密钥服务，不要写在脚本里
- 爬虫处理器是本地执行的 Python 代码，只运行你自己写的逻辑，不要执行从网页取回的内容
- `storage/` 会保存抓取结果与队列状态，可能含敏感数据；共享机器上注意目录权限与清理
- 控制并发与请求频率，避免对目标站点造成压力：先小样本验证，再逐步放量，始终设置请求上限
- 不要用本工具绕过依法受限的访问控制

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`crawlee-python`
- 仓库：https://github.com/apify/crawlee-python

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
