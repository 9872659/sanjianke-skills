# 三剪客 · 分布式爬虫调度系统 Skill

pyspider：分布式爬虫调度系统的安装、常用命令与避坑要点

---

## 前置条件

- 一个能装 Python 包的环境。强烈建议用独立虚拟环境或容器：它的依赖有历史版本约束，装进主环境容易和别的包冲突。
- 先确认在维护性上能接受这个前提：官方包在 PyPI 上的最新版本是 0.3.10（2018 年 4 月发布），支持范围写的是 Python 2.6–3.6，之后没有新版本。
- WebUI 默认没有认证，且能执行任意命令。上线前必须打开认证开关，并且只允许内网访问。
- 要分布式部署，先准备好数据库（MySQL / MongoDB / Redis / SQLite / PostgreSQL / Elasticsearch 之一或多种）和消息队列（RabbitMQ / Redis / Kombu）。
- 要抓 JavaScript 渲染的页面，先按官方文档确认渲染组件能不能在你的机器上跑起来。

---

## 使用

1. `pip install pyspider` 之后直接执行 `pyspider`，浏览器打开 `http://localhost:5000/` 就能看到控制台。
2. 单机开发用 `pyspider all`；只想调一个脚本、不起控制台时用 `pyspider one`（结果打到标准输出）。
3. 参数多了就写一份 JSON 配置，用 `-c config.json` 喂给全局或某个子命令；子命令名就是配置里的子字典键名。
4. 分布式时拆成 `scheduler`（全局唯一）、`fetcher`、`processor`、`result_worker`，它们通过数据库与消息队列共享状态。
5. 抓取逻辑写成一个 Handler 类：`on_start` 用 `@every` 定时触发，`self.crawl(..., callback=...)` 串下一步，回调里 `return` 字典作为结果。
6. 扩展组件、服务器形态的部署方式（含容器）以官方文档站与仓库说明为准。

---

## 依赖

- Python 运行环境（官方声明支持 2.6–3.6；新版本环境需要自行处理依赖兼容）。
- 零外部依赖也能跑：默认用 SQLite 存任务 / 项目 / 结果，消息队列用进程内队列，但只适合单机开发。
- 生产或分布式需要自备数据库：MySQL、MongoDB、Redis、SQLite、Elasticsearch，或通过 SQLAlchemy 接 PostgreSQL。
- 分布式需要自备消息队列：RabbitMQ、Redis、Beanstalk、Kombu。
- JavaScript 渲染需要按官方文档额外启用渲染组件，并准备相应的浏览器运行环境（该链路依赖的组件已经过时）。

---

## 安全

- 不内嵌任何密钥；数据库、消息队列、WebUI 的凭证都由使用者自己配置。
- **WebUI 默认没有认证，并且可以用来执行任意命令**。官方明确要求只在内部网络使用，或打开需要认证的开关。
- 官方包最新版（0.3.10）存在两个未修补的公开漏洞：CVE-2024-39162（`/update` 跨站脚本）与 CVE-2024-39163（Flask 端点跨站请求伪造）。相关公告明确指出，这些漏洞影响的正是已不再被维护的产品。
- 请勿把控制台暴露到公网或不可信网络；需要长期使用请自行做代码评审与加固。
- 数据库连接串里含账号密码，别把它写进会进版本库的文件或共享脚本。
- 抓取频率与目标站点的条款、robots 约定、当地法规需要使用者自行确认。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pyspider`
- 仓库：https://github.com/binux/pyspider

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
