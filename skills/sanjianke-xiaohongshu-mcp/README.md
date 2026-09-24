# 三剪客 · 小红书 MCP 服务 Skill

把小红书账号能力包成一个本地 MCP 服务，让 AI 客户端直接调工具完成扫码登录、发布图文/视频、搜索笔记、取帖子详情与评论、点赞收藏、回复评论、看用户主页。含二进制 / 源码 / Docker 三种部署、端口与鉴权配置、13 个 MCP 工具的参数速查与账号风控避坑。

---

## 前置条件

**这台机器上要先有的东西**（按你选的部署方式）：

- Docker 方式：一个能跑容器的 Docker 环境，本机 **18060** 端口空闲。
- 二进制方式：对应平台的可执行文件权限（Linux/macOS 需要 `chmod +x`），仅覆盖 macOS Apple Silicon、Windows x64、Linux x64。
- 源码方式：Go 环境（国内建议先 `go env -w GOPROXY=...` 配好模块代理）。

**账号侧要先有的东西**：

- 一个小红书账号，并且**完成实名认证**。未实名的新号很容易被平台要求实名，那不算封号，但会直接打断你的自动化流程。
- 想清楚这个号的登录安排：服务挂上之后，**不要再用浏览器网页版登录同一个账号**，否则会把服务里的登录态踢下线。要看账号信息就用移动 App。

**其他**：

- 首次启动需要能访问网络下载无头浏览器（约 150MB），之后就本地缓存了。
- 要发布的图片/视频先落到这台机器上——视频只吃本地文件路径。
- 若打算把服务暴露到本机之外，先决定好 `AUTH_TOKEN`。

---

## 使用

**最短跑通路径**（以 Docker 为例，它把浏览器和中文字体都配好了）：

1. 拉起服务：`docker pull xpzouying/xiaohongshu-mcp`，或用仓库 `docker/docker-compose.yml` 执行 `docker compose up -d`。
2. 完成一次扫码登录：用对应的登录工具（二进制 `xiaohongshu-login-*`、源码 `go run cmd/login/main.go`），或在客户端里调 `get_login_qrcode` 拿二维码扫。
3. 验证服务在跑：`npx @modelcontextprotocol/inspector`，连接 `http://localhost:18060/mcp`，点 `List Tools`，正常应看到 13 个工具。
4. 把服务接进 AI 客户端：Claude Code 用 `claude mcp add --transport http xiaohongshu-mcp http://localhost:18060/mcp`；Cursor / VSCode / Cline / Gemini CLI 各自写配置文件，URL 都是 `http://localhost:18060/mcp`。
5. 先用只读工具验证链路：调 `check_login_status`，再 `list_feeds` 或 `search_feeds` 读一次数据。读通了再动发布类工具。

**Agent 使用这份 Skill 时的顺序**：先确认服务与登录态 → 确认用户同意这次对外操作 → 再执行发布/互动 → 执行后回平台侧复核结果。参数取值、工具清单和排查表都在 `SKILL.md` 里，本文件只讲怎么把环境搭起来。

**注意**：Docker 场景下，从客户端连服务要写 `http://host.docker.internal:18060/mcp`；非 Docker 场景遇到 `localhost` 连不上时，改成本机 IPv4 地址。

---

## 依赖

**运行时依赖**：

- 无头浏览器：首次运行自动下载（约 150MB），用于驱动登录与所有页面操作。
- 中文字体与图形库：Docker 镜像内已预置；源码/二进制方式在部分 Linux 环境需要自己补齐，否则登录环节可能报图形相关错误。
- 本机 18060 端口：MCP 服务固定监听在这里。

**部署方式对应依赖**：

| 方式 | 依赖 |
|---|---|
| Docker | Docker 环境 + 镜像 `xpzouying/xiaohongshu-mcp`，挂载 `./data`（登录态与运行数据）与 `./images`（待发布图片） |
| 预编译二进制 | 对应平台系统环境，仅覆盖 macOS Apple Silicon / Windows x64 / Linux x64 |
| 源码编译 | Go 环境 + 模块代理 |

**客户端依赖**：任意支持 HTTP MCP 的客户端。要图形化排查可用 `npx @modelcontextprotocol/inspector`（需要 Node 环境）。

**账号依赖**：一个小红书账号的合法登录态。

**可选依赖**：

- `XHS_PROXY`：出网代理，支持 HTTP / HTTPS / SOCKS5。
- `AUTH_TOKEN`：服务访问鉴权令牌；启用后所有客户端都必须带 `Authorization: Bearer <token>`。

**上游依赖关系**：本 Skill 只是操作说明，不含上游代码；实际安装与版本信息一律以 https://github.com/xpzouying/xiaohongshu-mcp 的 Releases 与文档为准。

---

## 安全

- 不内嵌任何密钥。Cookie、`AUTH_TOKEN` 都由你自己在本地配置，不写进这个 Skill 包。
- **登录态就是账号本身**。本地 `./data` 目录里的 Cookie 文件等于账号的登录凭证，不要提交进仓库、不要挂到共享盘、不要在截图里露出来。
- **`AUTH_TOKEN` 默认是关闭的**。只要服务监听能被别人访问到，而你又没配 token，等于把「用你的账号发内容、发评论」的能力开放出去。要长期挂着就务必配 `AUTH_TOKEN`，并用环境变量而不是命令行参数（命令行参数可能被进程列表看到）。
- **所有写操作都会对外产生真实影响**。发布、评论、点赞、收藏都是平台侧可见的行为。Agent 代替用户执行前必须得到明确同意，并注意平台对引流、搬运、违禁内容的打击口径。
- **账号风险如实告知**。同一账号多网页端同时在线会被踢下线；高频操作、搬运内容、留联系方式引流都可能触发平台限制。工具不会替你承担这个后果。
- **预先准备出网策略**。用代理时确认代理可信；服务自身日志会隐藏代理认证信息，但你自己的客户端配置不会。
- **来源可信**。从官方 Releases 或官方镜像仓库取值，别用来路不明的镜像或网盘包——它以你的账号身份在操作。
- 本 Skill 不提供上游项目的技术支持。软件本身的问题请走上游仓库的 Issues。

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
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这里 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
