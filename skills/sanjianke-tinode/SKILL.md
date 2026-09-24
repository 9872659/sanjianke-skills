---
name: sanjianke-tinode
slug: sanjianke-tinode
displayName: 三剪客 · 可自托管的即时通讯服务端
description: "Tinode：可自托管的即时通讯服务端 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Tinode：可自托管的即时通讯服务端 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 可自托管的即时通讯服务端

想在自己服务器上跑一套「能聊天的东西」，又希望它带现成的手机端和网页端，而不是只有一堆接口——Tinode 是这类需求里比较少见的完整栈：后端是单个 Go 服务，配套 Android、iOS、网页三端客户端，另外提供 Python 写的命令行客户端用来做脚本化和运维。

它和你熟悉的那套 XMPP 体系**不兼容**，作者的目标就是做一个替代方案；它更像"可自托管的 WhatsApp / Telegram"，而不是"又一个 Slack"。单聊、群聊、频道（不限人数的只读订阅者）、语音视频通话、消息同步到多设备、服务端权限控制这些都在，但要提醒的是：官方自己把它标为 beta 质量——功能完整、大体稳定，但可能仍有 bug 或缺失特性。

**上游项目**：`Tinode`　**仓库**：https://github.com/tinode/chat

## 什么时候用 / 不用

**用它**：

- 需要一个能自己托管、并且**现成就有 Android / iOS / 网页三端可用**的即时通讯服务端（网页端可由服务进程直接托管），不想只拿到裸协议再自己写三端。
- 需要"频道"这种不限订阅人数的只读广播形态（公告、推送、订阅号式场景）。
- 需要按话题粒度做细粒度权限控制，并能服务端阻断不受欢迎的通信。
- 需要匿名用户能力（例如技术支持在线咨询那种先聊后注册的场景）。
- 需要脚本化运维：用命令行客户端批量建号、改密码、查用户、灌测试数据。
- 想接自己的鉴权体系（支持自定义认证后端）或写插件扩展功能（审核、机器人）。

**不要用它**：

- 组织内需要的是即时通讯的**成品**、期望装上就能让全员日常办公——它是给开发者做集成用的底座，不是办公套件。
- 环境里已经有 XMPP 存量系统并希望互通——它明确不与 XMPP 兼容，不要指望桥接。
- 只需要端到端加密的强隐私场景——加密相关能力在其规划清单里尚未落地，当前不要按"已具备端到端加密"来设计。
- 想要的是音视频会议、屏幕共享、群视频通话——这些在其规划列表中，当前不具备。
- 不想维护数据库（MySQL / PostgreSQL / MongoDB 之一必须自备）——它不提供内嵌存储。

## 安装

**以官方安装说明与 `--help` 为准。** 官方给了三条路（二进制、源码、Docker），下面都是仓库里真实存在的入口与参数。

### 方式一：下载现成二进制

从 Releases 页挑与你数据库匹配的那一份（MySQL / PostgreSQL / MongoDB / RethinkDB 各有单独构建），解压后进入目录：

```bash
# 1) 确认数据库已启动且允许本机连接
#    MySQL 默认以 root 无密码连接；PostgreSQL 默认以 postgres/postgres 连接

# 2) 初始化数据库（每个安装只需跑一次）
./init-db -data=data.json

# 3) 启动服务（不带参数即可运行）
./tinode
```

跑完用浏览器打开 `http://localhost:6060/` 验证。Windows 上对应可执行文件是 `init-db.exe` 与 `tinode.exe`。

数据库版本门槛（官方明示，低于此版本不可用）：MySQL 5.7 或以上（须用 InnoDB，MyISAM 会出问题，8.x 更佳）；PostgreSQL 13 或以上；MongoDB 4.4 或以上（8.x 更佳）。RethinkDB 支持已弃用。

### 方式二：Docker

先建一张桥接网络，让服务容器能连到数据库容器：

```bash
docker network create tinode-net
```

起数据库容器（按你选的后端挑一条，`--name` 的名字很重要，其他容器按这个名字找数据库）：

```bash
# MySQL
docker run --name mysql --network tinode-net --restart always --env MYSQL_ALLOW_EMPTY_PASSWORD=yes -d mysql:5.7

# PostgreSQL
docker run --name postgres --network tinode-net --restart always --env POSTGRES_PASSWORD=postgres -d postgres:13

# MongoDB（需要初始化成单节点副本集）
docker run --name mongodb --network tinode-net --restart always -d mongo:latest --replSet "rs0"
docker exec -it mongodb mongosh
# 在 mongo shell 里执行：
#   rs.initiate( {"_id": "rs0", "members": [ {"_id": 0, "host": "mongodb:27017"} ]} )
#   quit()
```

再起服务容器：

```bash
docker run -p 6060:6060 -d --name tinode-srv --network tinode-net tinode/tinode-mysql:latest
```

换成 `tinode/tinode-postgres:latest` / `tinode/tinode-mongodb:latest` 对应其他后端。也可以用集成了全部适配器的 `tinode/tinode:latest`，这时用 `STORE_USE_ADAPTER` 环境变量指定后端（例如 `-e STORE_USE_ADAPTER mysql`）。容器首次运行会自动用测试数据初始化数据库。可用环境变量（连接串、适配器、TLS 域名、SMTP、FCM、ICE 服务器等）见官方 Docker 说明里的变量表。

### 方式三：从源码编译

需要 Go 1.18 及以上，并按数据库选对应的构建标签：

```bash
go install -tags mysql github.com/tinode/chat/server@latest
go install -tags mysql github.com/tinode/chat/tinode-db@latest
```

把 `mysql` 换成 `postgres` / `mongodb` / `rethinkdb` 即可；也可一次打包多个适配器：

```bash
go install -tags "mysql rethinkdb mongodb postgres" github.com/tinode/chat/server@latest
go install -tags "mysql rethinkdb mongodb postgres" github.com/tinode/chat/tinode-db@latest
```

然后按源码目录里的 `tinode.conf` 核对数据库连接参数，并确认 `store_config.use_adapter` 写的是你要用的适配器名，再按"运行单机服务"一节启动。

## 常用操作

```bash
# 1. 启动服务（二进制方式，配置文件与静态资源目录按实际路径填）
./tinode -config=./server/tinode.conf -static_data=$HOME/tinode/webapp/

# 2. 只跑数据库初始化，并顺手灌入示例数据
$GOPATH/bin/tinode-db -config=./tinode-db/tinode.conf -data=./tinode-db/data.json

# 3. 用命令行客户端以用户名口令登录（默认连 gRPC 的 localhost:16060）
python tn-cli.py --login-basic=alice:alice123

# 4. 把一段命令序列喂给命令行客户端批跑
python tn-cli.py < sample-script.txt

# 5. 连启用 TLS 的服务，并在本机用域名做 SNI
python tn-cli.py --host=localhost:6001 --ssl --ssl-host=my-server.example.com

# 6. Docker 方式重置或升级数据库结构（先停并删旧容器再带变量重跑）
docker stop tinode-srv && docker rm tinode-srv
docker run -p 6060:6060 -d --name tinode-srv --network tinode-net --env UPGRADE_DB=true tinode/tinode-mysql:latest
```

命令行客户端的可用参数与命令以 `python tn-cli.py --help` 及 `<命令> -h` 输出为准，包括 `--host`、`--web-host`、`--ssl`、`--ssl-host`、`--login-basic`、`--login-token`、`--login-cookie`、`--api-key`、`--load-macros`、`--verbose`、`--background` 等；常用命令有 `acc`、`login`、`sub`、`leave`、`pub`、`get`、`set`、`del`、`note`、`file`，以及 `useradd`、`passwd`、`resolve`、`chacs` 等宏。依赖安装：

```bash
python -m pip install -r requirements.txt
```

还可以直接拿官方沙箱环境练手：登录名 `alice` / `bob` / `carol` / `dave` / `frank`，口令是登录名加 `123`；注册时的验证码可用 `123456`（仅沙箱如此，因为配置里留了调试用响应码）。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 服务起不来，或连不上数据库 | 配置里 `store_config.use_adapter` 没填，或填写与二进制编译时的构建标签不一致 | 确认 `use_adapter` 与所选数据库匹配，且用的是带对应 `-tags` 编译出来的二进制 |
| MySQL 连接报错或时间字段异常 | 连接串缺少 `parseTime=true` | 按官方示例把 `parseTime=true` 加到 DSN 里；MySQL 同时确认使用 InnoDB |
| 线上被人不用密码就登录进来了 | 配置里的令牌签名密钥、用户 ID 加密密钥等仍是模板默认值 | 上线前全部换成自己生成的随机值并妥善保管，官方在配置里已标注必须修改 |
| 客户端报 `User not found or offline` | 连的是沙箱服务，而沙箱每天凌晨会清库 | 重新登录；沙箱只用于测试，不要放真实数据 |
| 生产环境被别人用假邮箱随便注册 | 配置里留着调试用的通用验证码 | 移除调试响应码，并配置真实的邮件校验服务 |
| 上传稍大的图片/文件失败 | 单条消息体积上限默认较小，超出部分需走出带外传输；同时媒体处理器自身也有大小上限 | 检查消息体积上限与媒体处理器的大小设置，按业务需要调整，别盲目调得很大 |
| 视频通话接不通 | 未配置 ICE（STUN/TURN）服务器——官方不提供，配置示例里是假地址 | 自备 TURN/STUN 服务并把配置填进 `webrtc` 段，同时打开 `webrtc.enabled` |
| 推送收不到 | 推送通知默认关闭，且需要推送服务的凭证 | 按官方说明获取并填入推送凭证后再启用对应通知器 |
| 用 `nohup` 放后台，SSH 一断服务就退出 | 服务会拦截 `SIGHUP` 并当作关闭请求 | `nohup` 之后立刻 `exit` 关闭前台会话；更稳妥的是用 systemd 之类的进程管理器托管 |
| 数据库升级后服务报版本不匹配 | 数据库结构版本落后于二进制 | 按官方说明做升级或重置（Docker 方式对应 `UPGRADE_DB` / `RESET_DB` 变量） |
| 集群没生效 | 节点名未提供，聚类因此被禁用 | 通过配置或命令行提供节点名；集群至少两个节点，建议三个 |
| 反代部署后 WebSocket 异常 | 静态资源与接口未从同一个对外地址加载，或代理未正确转发 | 从服务对外提供的地址加载客户端，并核对反向代理的转发规则 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 客户端 WebSocket / 长轮询连接、gRPC 调用、拉取依赖与镜像、调用邮件与推送服务 |
| 读取文件 | 是 | 读取配置文件、静态资源目录、媒体上传目录、邮件模板 |
| 写入文件 | 是 | 数据库写入、上传的媒体文件落盘、服务日志 |
| 凭证 | 是 | 数据库口令、令牌签名密钥、第三方认证与推送凭证；配置里带默认值，上线前必须替换 |
| 子进程 / 后台常驻 | 是 | 作为常驻服务进程运行，需由 systemd 等外部工具托管 |

## 触发场景

- "想在自己服务器上搭一套带手机端和网页端的聊天服务"
- "需要一个只读频道，订阅人数不设上限，用来做公告或推送"
- "想按话题分配权限，并且能服务端拦截骚扰消息"
- "要给客服场景做匿名会话：先聊起来，之后才注册"
- "用命令行批量建用户、改密码、灌测试数据"
- "Tinode 客户端连不上 / 数据库初始化失败，帮我定位"

## 能力边界

**覆盖**：

- 服务端的三种部署方式（现成二进制、源码编译、Docker）与数据库后端选择（MySQL / PostgreSQL / MongoDB / RethinkDB，后者已弃用）。
- 服务端功能：单聊与群聊、频道（不限人数只读订阅）、消息多设备同步、细粒度访问权限、用户搜索与发现、消息状态通知、已读与输入中提示、消息编辑与转发回复、置顶、匿名用户。
- 媒体与大文件：本地文件系统或对象存储的带外传输与媒体处理扩展。
- 管理能力：自定义认证后端、服务端阻断、插件扩展（审核、机器人）、命令行运维客户端。
- 客户端：Android、iOS、网页端，以及多语言绑定（JS、Java、Swift、gRPC 多语言）。
- 协议与部署形态：JSON over WebSocket（也支持长轮询）、protobuf + gRPC、分片集群与故障转移、TLS。

**不覆盖**：

- 不与 XMPP/Jabber 兼容，也不提供互通桥接。
- 不提供端到端加密（在规划中，当前不具备）。
- 不提供音视频会议、屏幕共享、群视频通话（在规划中）。
- 不自带 ICE（STUN/TURN）服务器，也不自带推送通道。
- 不做办公套件（文档、审批、日程），官方明确不以替代同类团队协作工具为目标。

## 依赖条件

- 一个数据库后端并已启动：MySQL 5.7+（InnoDB）、PostgreSQL 13+、MongoDB 4.4+（须单节点副本集），或已弃用的 RethinkDB。
- 现成二进制方式：从 Releases 下载与数据库匹配的构建，无需自备编译环境。
- 源码方式：Go 1.18 及以上；要改协议还需 protobuf 与 gRPC 工具链。
- Docker 方式：Docker 1.8 及以上；先建好桥接网络。
- 命令行客户端：Python 2.7 或 3.4+、PIP 9.0.1+，并安装对应版本的 gRPC 客户端包（版本号需与服务端一致）。
- 音视频通话：自备 TURN/STUN 服务；推送：自备推送服务凭证；邮件校验：自备 SMTP 账号。

## 已知限制

- 官方标注为 beta 质量：功能完整且大体稳定，但仍可能存在缺陷或缺失特性。
- 加密能力（端到端加密、静态加密、消息留存策略）与音视频增强能力仍在规划中，不能按已具备来设计。
- RethinkDB 支持已弃用，官方计划在 2027 年移除。
- Go 进程无法自行守护化，必须依赖外部工具做后台运行与开机自启。
- 配置文件使用带注释的 JSON，官方提示注释解析比较脆弱，不适合写得过于花哨。
- 集群与故障转移功能需要至少两个节点（建议三个），单机无法验证这部分行为。

## 自检清单

执行前：

- [ ] 确认数据库版本达到门槛，且允许来自服务所在主机的连接。
- [ ] 确认所选二进制/镜像的数据库适配器与你的数据库一致。
- [ ] 确认配置里 `use_adapter` 已填写，数据库连接参数与实际环境一致。
- [ ] 确认令牌签名密钥、用户 ID 加密密钥等已由自己生成并妥善保存。
- [ ] 明确是否需要音视频、推送、邮件校验，需要则先把外部服务准备好。

执行后：

- [ ] 浏览器打开 `http://<主机>:6060/` 能看到网页端。
- [ ] 在网页端注册或登录成功，并成功发出/收到一条消息。
- [ ] 多端登录同一账号，消息能同步。
- [ ] 上传一张图片或一个文件，对端能正常收到。
- [ ] 生产环境已移除调试用验证码，并已替换全部默认密钥。
- [ ] 用 systemd 或等效方式托管进程，重启机器后服务自动恢复。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/tinode/chat | 上游仓库（安装与完整文档以它为准） |

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
