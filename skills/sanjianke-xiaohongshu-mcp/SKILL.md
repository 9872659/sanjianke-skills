---
name: sanjianke-xiaohongshu-mcp
slug: sanjianke-xiaohongshu-mcp
displayName: 三剪客 · 小红书 MCP 服务
description: "把小红书账号能力包成一个本地 MCP 服务，让 AI 客户端直接调工具完成扫码登录、发布图文/视频、搜索笔记、取帖子详情与评论、点赞收藏、回复评论、看用户主页。含二进制 / 源码 / Docker 三种部署、端口与鉴权配置、13 个 MCP 工具的参数速查与账号风控避坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "本地起一个 MCP 服务（默认 18060 端口），AI 客户端接上去就能操作小红书：先扫码登录，再发布、搜索、读评论、点赞收藏。含三种部署方式、可用工具清单、定时发布与可见范围参数、以及封号与风控边界。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 社媒
  - 营销
  - MCP
  - 小红书
---

# 三剪客 · 小红书 MCP 服务

想让 AI 助手替你操作小红书，通常得现写一套浏览器自动化：选元素、等加载、处理登录态、处理风控，换个页面结构就全废。xiaohongshu-mcp 把这个工作量收敛掉了——它在本地起一个 MCP 服务，把「登录、发布图文、发布视频、搜索、取帖子详情、发评论、点赞、收藏、看用户主页」这些动作直接暴露成标准 MCP 工具，任何支持 HTTP MCP 的客户端接上就能用自然语言调。

它的价值在两处：**一是协议标准化**，你的客户端换一个、模型换一个，服务端不用改；**二是登录态留在本地**，它用无头浏览器替你把 Cookie 存在本地数据目录，不用把账号密码交给第三方。

代价也要提前说清：它本质是**浏览器自动化**，跑得慢、会被平台风控看见、需要人工偶尔扫码续登录。把它当成「有人的账号、机器的手」，而不是「无人值守的批量发布机」。

**上游项目**：`xiaohongshu-mcp`　**仓库**：https://github.com/xpzouying/xiaohongshu-mcp

## 什么时候用 / 不用

**用它**：

- 用户说「让 AI 帮我发一篇小红书图文 / 视频」，或者「接力把这个标题和正文和小红书发了」，并且愿意自己做一次扫码登录。
- 用户想把自己的某个 AI 客户端（Claude Code、Cursor、VSCode、Cline、Gemini CLI、Open Code 等）接上小红书，做**单账号、低频次**的内容发布与互动。
- 需要**读取**小红书侧的数据喂给模型：按关键词搜索笔记、拉首页推荐流、取某篇帖子的互动数据与评论列表、看某个用户的主页与笔记。
- 需要做互动运营：给指定帖子点赞/取消点赞、收藏/取消收藏、发表评论、回复某条指定评论。
- 想在发布时用上定时发布（1 小时至 14 天内）、可见范围（公开 / 仅自己 / 仅互关好友）、话题标签、声明原创、绑定带货商品这些参数。

**不要用它**：

- **想不登录就白嫖数据**。所有能力都以登录态为前提，登录要么扫码、要么走 Cookie 文件；没有登录态，`check_login_status` 之后什么都做不了。
- **同一个账号还想在别的网页端登录**。这是最容易翻车的一条：同一个小红书账号不允许在多个网页端同时在线，它登进去之后你再用浏览器网页版登同一个号，会把这里踢下线。
- **要做批量矩阵、一天几十篇的无人值守发布**。这是浏览器自动化 + 平台风控的正面对撞，账号受限只是时间问题；真要做量，应该先解决合规与授权，而不是换个更快的工具。
- **要发搬运内容、要留联系方式引流**。这两类是平台明确的重点打击对象，工具能做不等于该做，遇到这类需求应当直接拒绝而不是换个参数绕。
- **要抓全量数据做数据集**。它只有搜索、推荐流、单帖详情、单用户主页这几个读取入口，没有全站爬取、没有历史归档、没有导出接口。
- **不接受「人工偶尔介入」**。Cookie 会过期、首次运行要下载约 150MB 的无头浏览器、新号可能被要求实名认证。要一个纯后台、装完不用管的服务，这不是它。

## 安装

它的安装方式按「你想省事还是想可控」分三档。**首次运行会自动下载无头浏览器（约 150MB）**，三档都一样，网络要能出去。

### 方式一：预编译二进制（最快，适合个人本机）

去 GitHub Releases 下载对应平台的两个文件——一个主程序（MCP 服务），一个登录工具：

| 平台 | 主程序 | 登录工具 |
|---|---|---|
| macOS Apple Silicon | `xiaohongshu-mcp-darwin-arm64` | `xiaohongshu-login-darwin-arm64` |
| Windows x64 | `xiaohongshu-mcp-windows-amd64.exe` | `xiaohongshu-login-windows-amd64.exe` |
| Linux x64 | `xiaohongshu-mcp-linux-amd64` | `xiaohongshu-login-linux-amd64` |

macOS Intel 与 Linux ARM64 没有官方预编译包。以 macOS 为例：

```bash
# 1) 先登录，把登录态存下来
chmod +x xiaohongshu-login-darwin-arm64
./xiaohongshu-login-darwin-arm64

# 2) 再起 MCP 服务（默认无头模式）
chmod +x xiaohongshu-mcp-darwin-arm64
./xiaohongshu-mcp-darwin-arm64
```

Windows 上把 `.exe` 直接双击或从 PowerShell 运行即可，例如：

```powershell
.\xiaohongshu-login-windows-amd64.exe
.\xiaohongshu-mcp-windows-amd64.exe
```

### 方式二：源码编译（要改代码、要排查问题就走这条）

需要 Go 环境。国内建议先设好模块代理：

```bash
# 三选一
go env -w GOPROXY=https://goproxy.cn,direct
go env -w GOPROXY=https://mirrors.aliyun.com/goproxy/,direct
go env -w GOPROXY=https://goproxy.io,direct
```

```bash
# 登录（第一次必须做）
go run cmd/login/main.go

# 启动 MCP 服务：默认无头
go run .

# 需要看到浏览器界面时
go run . -headless=false
```

### 方式三：Docker（部署最省事，推荐给要长期挂着的场景）

```bash
# 拉取预构建镜像
docker pull xpzouying/xiaohongshu-mcp

# 或者用仓库里配好的 compose 文件
wget https://raw.githubusercontent.com/xpzouying/xiaohongshu-mcp/main/docker/docker-compose.yml
cd docker
docker compose up -d
docker compose logs -f
docker compose stop
```

自己构建镜像（在项目根目录）：

```bash
docker build -t xpzouying/xiaohongshu-mcp .
```

Docker 版会自动配好内置浏览器与中文字体，挂载 `./data` 存 Cookie 与运行数据、挂载 `./images` 存要发布的图片，并暴露 **18060** 端口给 MCP 连接。

### 启动参数与鉴权（可选但生产必配）

```bash
# 代理：支持 HTTP / HTTPS / SOCKS5，日志里会自动隐藏认证信息
XHS_PROXY=http://user:pass@proxy:port ./xiaohongshu-mcp-darwin-arm64

# 鉴权：默认关闭；生产建议用环境变量
AUTH_TOKEN=your-secret-token ./xiaohongshu-mcp-darwin-arm64

# 非空启动参数优先于环境变量（注意：命令行参数可能被进程列表看到，优先用 AUTH_TOKEN）
./xiaohongshu-mcp-darwin-arm64 -token=your-secret-token
```

开了鉴权之后，**所有** MCP 客户端都必须带 `Authorization: Bearer <token>` 请求头，客户端的 MCP 配置也要跟着补上这个 header。

## 常用操作

服务起来之后固定监听 `http://localhost:18060/mcp`，下面都是可以直接跑的。

### 1) 起服务并确认它活着

```bash
# 默认无头模式
go run .

# 有界面模式，排查问题时用
go run . -headless=false

# 用 curl 探一下 MCP 端点（开了鉴权就带上 header）
curl -X POST http://localhost:18060/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

### 2) 用官方 Inspector 看工具清单

```bash
npx @modelcontextprotocol/inspector
```

打开它给出的链接，填 `http://localhost:18060/mcp` 点 Connect，再点 `List Tools`。连接正常时应当看到 13 个工具。

### 3) 把服务接进 AI 客户端

```bash
# Claude Code CLI：添加 HTTP MCP 服务器
claude mcp add --transport http xiaohongshu-mcp http://localhost:18060/mcp
claude mcp list

# Open Code CLI：交互式添加
opencode mcp add
opencode mcp list

# Gemini CLI 在 ~/.gemini/settings.json 里写
# { "mcpServers": { "xiaohongshu": { "httpUrl": "http://localhost:18060/mcp", "timeout": 30000 } } }
```

Cursor 写 `.cursor/mcp.json`、VSCode 写 `.vscode/mcp.json`，两者结构略有差别：

```json
{
  "mcpServers": {
    "xiaohongshu-mcp": {
      "url": "http://localhost:18060/mcp",
      "headers": { "Authorization": "Bearer your-secret-token" }
    }
  }
}
```

```json
{
  "servers": {
    "xiaohongshu-mcp": { "url": "http://localhost:18060/mcp", "type": "http" }
  },
  "inputs": []
}
```

### 4) 登录：扫码 / 查状态 / 重置

```bash
# 二进制方式登录
./xiaohongshu-login-darwin-arm64

# 源码方式登录
go run cmd/login/main.go
```

登录完成后，让客户端依次调 `check_login_status`（确认在线）→ 需要重新登录时调 `get_login_qrcode`（拿 Base64 二维码和超时时间）→ 状态彻底乱了就调 `delete_cookies`（清掉登录态，之后必须重新扫码）。

### 5) 发布一篇图文

对应工具 `publish_content`，必需参数是 `title`、`content`、`images`：

```json
{
  "title": "春天的第一杯手冲",
  "content": "把水温压到 92 度，风味会柔和很多。",
  "images": ["/home/user/Pictures/coffee-1.jpg", "/home/user/Pictures/coffee-2.jpg"],
  "tags": ["咖啡", "手冲", "生活"],
  "visibility": "公开可见",
  "is_original": true
}
```

`images` 支持 HTTP/HTTPS 链接和本地绝对路径，**官方推荐本地绝对路径**：不依赖网络、上传更快、不怕外链失效。可选参数还有 `schedule_at`（ISO8601，支持 1 小时至 14 天内）、`visibility`、`is_original`、`products`（商品关键词列表，需账号已开通商品功能）。

### 6) 发布一条视频

对应工具 `publish_with_video`，必需参数是 `title`、`content`、`video`：

```json
{
  "title": "三分钟学会冷萃",
  "content": "比例 1:10，冰箱里放 12 小时。",
  "video": "/home/user/Videos/coldbrew.mp4",
  "tags": ["咖啡", "冷萃"],
  "schedule_at": "2026-03-24T21:30:00+08:00",
  "visibility": "公开可见"
}
```

视频**只支持本地绝对路径**，不能给 HTTP 链接；建议单个文件不超过 1GB，处理时间较长，要等它把视频处理完才会真正发出去。

### 7) 搜索 / 推荐流 / 帖子详情

```json
{
  "keyword": "露营装备",
  "filters": {
    "sort_by": "最多点赞",
    "note_type": "图文",
    "publish_time": "一周内",
    "search_scope": "不限",
    "location": "同城"
  }
}
```

- `search_feeds` 必需 `keyword`，`filters` 可选，取值分别是：`sort_by` 取 `综合`/`最新`/`最多点赞`/`最多评论`/`最多收藏`；`note_type` 取 `不限`/`视频`/`图文`；`publish_time` 取 `不限`/`一天内`/`一周内`/`半年内`；`search_scope` 取 `不限`/`已看过`/`未看过`/`已关注`；`location` 取 `不限`/`同城`/`附近`。
- `list_feeds` 无参数，取首页推荐列表。
- `get_feed_detail` 必需 `feed_id` 和 `xsec_token`，**两个都不能少**；可选 `load_all_comments`、`limit`、`click_more_replies`、`reply_limit`、`scroll_speed`（`slow`/`normal`/`fast`）。

### 8) 互动：评论、回复、点赞、收藏

```json
{ "feed_id": "帖子ID", "xsec_token": "从搜索或推荐流里拿到的token", "content": "这个思路很实用，收藏了" }
```

- `post_comment_to_feed`：发评论到帖子，必需 `feed_id`、`xsec_token`、`content`。
- `reply_comment_in_feed`：回复指定评论，必需 `feed_id`、`xsec_token`、`content`，外加 `comment_id` 或 `user_id` **至少一个**。
- `like_feed`：默认点赞，传 `unlike: true` 取消点赞。
- `favorite_feed`：默认收藏，传 `unfavorite: true` 取消收藏。
- `user_profile`：看用户主页，必需 `user_id` 和 `xsec_token`。

点赞和收藏都会先检测当前状态，已经点过就跳过，不会重复操作。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 客户端里 `check_login_status` 返回的用户名看着不对 | 该字段在上游是写死的展示值，不是真实昵称 | 不要拿它做账号校验；要验证登录态就自己发一条仅自己可见的内容或读一次推荐流确认 |
| 提示发布成功，但小红书上刷不出这条 | 常见于账号被风控限制网页版发布、图片过大、图片路径含中文字符、外链图片不可访问 | 用 `-headless=false` 有界面模式重发一次；换完全不同的一条内容再试；登网页版看账号是否被限制发布；换图片、把路径改成纯英文、把外链图片下载到本地 |
| 服务跑起来但客户端连不上 `localhost:18060` | Docker 里连宿主机 localhost 走不到；或非 Docker 环境下 localhost 解析异常 | Docker 场景改连 `http://host.docker.internal:18060/mcp`；非 Docker 场景改成本机 IPv4 地址 |
| 程序在某些设备上闪退 | 预编译二进制与系统/依赖不匹配 | 优先改用源码编译安装；或直接改用 Docker 部署 |
| 登录报 `The type initializer for 'Gdip' threw an exception` | 缺少图形相关系统库（Linux 上常见） | 装齐系统图形依赖，或直接用 Docker 镜像（镜像里已经配好浏览器与字体）；以仓库 Issues 的处理为准 |
| 第一次启动卡很久、要下 150MB 左右的东西 | 首次运行会拉无头浏览器，之后不再重复下载 | 提前把网络准备好；容器/CI 场景把浏览器缓存目录挂出来持久化 |
| 客户端报 401 / 未授权 | 服务端开了 `AUTH_TOKEN`，客户端没带 `Authorization: Bearer <token>` 请求头 | 在客户端的 MCP 配置里补上 headers；同一个 token 同时配给所有客户端 |
| 网页版登录后，这个 MCP 服务突然掉线 | 同一账号不允许多个网页端同时在线，后登录的把先登录的踢掉 | 服务挂上之后只用移动 App 看账号信息，不要再用浏览器网页版登同一个号 |
| `get_feed_detail` 报参数错误 | 只传了 `feed_id` 没传 `xsec_token`，这两个是缺一不可的 | `xsec_token` 只能从搜索结果或推荐流列表里带出来，别自己拼；先 `search_feeds` 或 `list_feeds` 拿到成对的 ID + token 再用 |
| 新号收到实名认证提醒，以为被封号 | 未实名的新号容易触发实名提醒，不用这个工具也会被提醒 | 事先完成实名认证；这本身不是封号，认证后即恢复正常 |
| 视频传不上去，或一直等不到发布 | 视频发布只吃本地文件路径，不吃 HTTP 链接；大文件处理慢 | 把视频下到本地再传；控制文件体积（建议 1GB 以内），并留足处理时间 |
| 定时发布报时间非法 | `schedule_at` 是 ISO8601 格式，且只支持 1 小时至 14 天这个窗口 | 用带时区的完整写法（如 `2026-03-24T21:30:00+08:00`），并把目标时间排进窗口内 |
| Agent 只把二维码图片路径念给用户 | 二维码本身是给用户扫的，路径对人没用 | Agent 应当直接把生成的二维码图片展示/发给用户，路径只作补充 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 连接小红书站点完成登录、发布、搜索、读取；首次运行还要下载无头浏览器；如配了 `XHS_PROXY` 则经代理出网 |
| 读取文件 | 是 | 读取要发布的本地图片/视频（绝对路径）、读取本地 Cookie 与运行数据目录、读取 Docker 挂载的 `./images` |
| 写入文件 | 是 | 落地 Cookie / 登录态与运行数据（`./data`）、临时截图与二维码、Docker 场景写入挂载目录 |
| 凭证 | 是 | 小红书账号登录态（Cookie）；生产环境的 `AUTH_TOKEN` 服务鉴权令牌。两者都只能放本地，不要写进 Skill、不要提交进仓库 |
| 子进程 / 后台常驻 | 是 | 启动并驱动无头浏览器完成操作；服务本身需要常驻监听 18060 端口；Docker 以容器形式长期运行 |
| 平台账号操作 | 是 | 代表登录账号发布内容、发评论、点赞、收藏、关注类读取——这些都是会对外产生真实影响的操作，执行前要跟用户确认 |

## 触发场景

- 「帮我把这篇图文发到小红书，图片在这个目录里。」
- 「搜一下小红书上关于露营装备的高赞笔记，把标题和互动数据整理给我。」
- 「看一下这个小红书账号的主页，粉丝数和最近发的内容列出来。」
- 「把这批视频按每晚九点定时发到小红书。」
- 「这个帖子底下有几条问价格的评论，帮我统一回一下。」
- 「我的 AI 客户端能不能直接操作小红书？帮我接一下。」

## 能力边界

**覆盖**：

- 在本地起一个标准 HTTP MCP 服务（默认 `http://localhost:18060/mcp`），供任意支持 HTTP MCP 的客户端接入。
- 登录态管理：扫码登录、检查登录状态、获取登录二维码、清除 Cookie 重置登录。
- 内容发布：图文发布（标题 + 正文 + 多图 + 标签 + 可选定时/可见范围/原创声明/带货商品）、视频发布（本地视频 + 标题 + 正文 + 标签 + 可选定时/可见范围/带货商品）。
- 内容读取：关键词搜索（带排序、笔记类型、发布时间、搜索范围、位置距离筛选）、首页推荐流、帖子详情（含互动数据与评论、可控制加载评论数量与二级回复）、用户主页信息与笔记列表。
- 互动操作：发表评论、回复指定评论、点赞/取消点赞、收藏/取消收藏。
- 部署形态：预编译二进制、源码编译、Docker 容器三种；支持代理出网与 `AUTH_TOKEN` 访问鉴权。

**不覆盖**：

- **不做数据抓取/归档**。没有全站爬取、没有批量导出、没有历史数据回填，只有搜索、推荐流、单帖详情、单用户主页四个读取入口。
- **不保证发布一定成功**。浏览器自动化会被页面改版、风控策略、网络环境、图片规格影响；它只负责把动作做出去，不负责结果一定上线。
- **不做多账号自动轮换调度**。它是「一个服务对应一套登录态」，账号矩阵的排期、切号、限流要靠外部系统自己设计。
- **不做数据分析和内容生成**。不会替你写文案、选图、算投放效果；它只是把小红书变成模型能调的一组工具。
- **不提供合规与授权判断**。搬运、引流、违禁词、版权、平台规则的红线要你自己守；工具不会拦你。
- **不替代平台官方能力**。没有官方 API 的稳定性与 SLA，也没有评论/私信客服类的完整功能面。

## 依赖条件

- **运行环境**：二进制方式需要对应平台（macOS Apple Silicon / Windows x64 / Linux x64）；源码方式需要 Go 环境；Docker 方式需要能跑容器的 Docker 环境。
- **首次启动的网络**：要能下载约 150MB 的无头浏览器，之后不再重复下载。
- **小红书账号**：一个可以正常登录的账号，且**已完成实名认证**（新号/未实名号容易被要求实名，虽然不算封号，但会打断流程）。
- **端口**：本机 **18060** 要空闲，客户端按 `http://localhost:18060/mcp` 连接。
- **客户端**：任意支持 HTTP MCP 的客户端（Claude Code、Cursor、VSCode、Cline、Gemini CLI、Open Code、MCP Inspector 等）。
- **可选**：出网代理（`XHS_PROXY`，支持 HTTP/HTTPS/SOCKS5）、服务鉴权令牌（`AUTH_TOKEN`）。

## 已知限制

1. **平台官方未开放这类接口**，本项目基于浏览器自动化实现，页面结构变动或风控策略调整都可能导致某些工具失效。
2. **登录态会过期**，需要人工重新扫码；这不是可以完全无人值守的方案。
3. **同一账号不能在多个网页端同时在线**，服务在线期间不要再用浏览器网页版登录同一个号。
4. **视频只支持本地文件路径**，不支持直接给一个网络视频地址；大文件处理时间长，且建议控制在 1GB 以内。
5. **标题与正文有平台长度上限**（标题不超过 20 字、正文不超过 1000 字），超了会被平台侧拒绝，客户端不会替你截断。
6. **预编译包只覆盖三个平台**：macOS Apple Silicon、Windows x64、Linux x64；macOS Intel 与 Linux ARM64 需自行源码编译或走 Docker。
7. **访问鉴权默认是关闭的**，服务暴露在网络上而没配 `AUTH_TOKEN` 等于把账号操作权交出去。

## 自检清单

执行前：

- [ ] 确认用户**明确知道并同意**用 AI 代表他的账号做这次对外操作（发布 / 评论 / 点赞）。
- [ ] 确认 MCP 服务已经在跑，且 `http://localhost:18060/mcp` 可连接（Docker 场景用 `host.docker.internal`）。
- [ ] 确认 `check_login_status` 通过；不通就先走 `get_login_qrcode` 扫码，不要把二维码路径当答案丢给用户。
- [ ] 确认服务端是否开了 `AUTH_TOKEN`，客户端 MCP 配置里是否已经带上 `Authorization: Bearer <token>`。
- [ ] 要发布的话：图片/视频路径逐条核对过存在、是绝对路径、路径里没有中文字符；视频是本地文件而不是链接。
- [ ] 标题 ≤ 20 字、正文 ≤ 1000 字；用了 `schedule_at` 就核对格式是 ISO8601 且落在 1 小时至 14 天窗口内。
- [ ] 内容本身过一遍平台红线：不含搬运、不含联系方式引流、不含违禁词。

执行后：

- [ ] 用 `check_login_status` 或读一次推荐流，确认服务没有因为这次操作掉线。
- [ ] 发布类操作去平台侧复核内容是否真的可见；没出现就按「发布成功但不显示」的排查顺序走一遍。
- [ ] 互动类操作核对次数与目标（别点赞/收藏到错误的帖子，`feed_id` 和 `xsec_token` 必须成对使用）。
- [ ] 把这次的操作、目标、结果记下来，方便下次排期时避开同一时段的密集操作。
- [ ] 若过程中出现过登录态过期、风控提示、实名提醒，如实告知用户，不要当成技术故障悄悄重试。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/xpzouying/xiaohongshu-mcp | 上游仓库（安装与完整文档以它为准） |
| https://github.com/xpzouying/xiaohongshu-mcp/blob/main/docker/README.md | Docker 部署细节 |
| https://github.com/xpzouying/xiaohongshu-mcp/blob/main/docs/windows_guide.md | Windows 环境专项说明 |

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
