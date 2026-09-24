# 三剪客 · 免费代理 IP 池服务 Skill

把公开免费代理自动采集、校验、入库，再用一个本地 HTTP 接口把当下可用的代理发给爬虫。本 Skill 覆盖本地 / Docker 两种部署、接口调用、爬虫接入与高频故障排查。

---

## 前置条件

- 先把代码拉到本地：这个项目没有发布成 pip 包，必须 `git clone` 或下载 release 后运行
- Python 3 环境，用 `pip install -r requirements.txt` 装依赖
- 一个可用的 **Redis 或 SSDB**：项目不自带存储，`setting.py` 里的 `DB_CONN` 必须指向真实存在的实例。图省事可直接用仓库自带的 `docker-compose.yml`，它会把 Redis 一起拉起来
- 能访问外网：既要爬公开代理站，也要访问代理校验地址
- Docker 路线需要 Docker；compose 路线需要 Docker Compose
- 准备好接受"后台常驻"：调度进程、API 进程、数据库三者长期运行
- Windows 原生环境没有 `proxy_pool.sh` 可用，改走 `python proxyPool.py schedule` / `server`

---

## 使用

1. **改配置**：编辑项目根目录 `setting.py`，至少确认 `HOST`、`PORT`（默认 5010）、`DB_CONN` 三项。
2. **启动**：`./proxy_pool.sh start` 后台起全部服务；排障时用 `./proxy_pool.sh start --fg` 前台看日志；容器里统一用前台模式。
3. **等第一轮采集**：刚启动池子是空的，要等调度器跑完采集与校验才会开始供血。
4. **验证**：`curl http://127.0.0.1:5010/count/` 看规模与来源分布，`curl http://127.0.0.1:5010/get/` 取一个代理。
5. **接入爬虫**：调 `/get` 拿地址 → 带超时请求 → 失败调 `/delete` 归还。要 HTTPS 代理加 `?type=https`。
6. **扩展来源**：在 `fetcher/sources/` 下新建继承 `BaseFetcher` 的 `.py` 文件，实现 `fetch()` 并 yield `"host:port"`；用 `python proxyPool.py fetcher` 确认已被加载。
7. **停服**：`./proxy_pool.sh stop`；停不掉就按 PID 文件手工处理（见 `SKILL.md` 的「常见坑」）。

完整命令、参数与排查表见 `SKILL.md`。

---

## 依赖

- Python 3 与 `requirements.txt` 内的依赖（Web 框架、调度器、Redis 客户端等）
- Redis 或 SSDB 之一，作为代理存储后端
- `proxy_pool.sh` 需要 POSIX shell 环境
- Docker / Docker Compose（走容器路线时）
- 外网可达性：代理源站点与 `HTTP_URL` / `HTTPS_URL` 两个校验地址
- 无账号与 API Key 要求

---

## 安全

- 不内嵌任何密钥
- API 接口**没有鉴权**，`HOST` 默认是 `0.0.0.0`。只给自己用的场景应改成 `127.0.0.1`；必须远程访问就套一层反向代理加认证与访问白名单，不要直接暴露 5010
- `DB_CONN` 里通常带数据库密码；用 `docker run --env` 传参时注意别把密码留进 shell 历史与 CI 日志
- 池中的代理是公开来源，流量经由不受信任的第三方出口，**不要用它传输任何凭证或私密数据**
- 使用代理访问目标站前，先确认目标站的服务条款与 robots 约定；本项目只提供技术手段，不构成合规许可
- 免费源站点可能限频或封禁采集方，`HTTP_URL` 默认指向的公共校验服务也不适合高频压测

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`proxy_pool`
- 仓库：https://github.com/jhao104/proxy_pool

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
