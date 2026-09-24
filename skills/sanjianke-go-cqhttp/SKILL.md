---
name: sanjianke-go-cqhttp
slug: sanjianke-go-cqhttp
displayName: 三剪客 · QQ 机器人协议端
description: "go-cqhttp：把 QQ 协议翻译成 OneBot v11 接口的中间层，机器人程序只用 HTTP/WebSocket 就能收发 QQ 消息。本文讲清它的当前维护状态、下载与部署、config.yml/device.json 结构、签名服务配置与高频坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "go-cqhttp 的落地指引：已停止维护的现状与迁移提示、各平台二进制与源码构建、config.yml 与 device.json 的真实结构、http/ws/ws-reverse 四种通信方式、access-token 与签名服务器设置、后台常驻方式，以及登录风控、协议限制、device.json 变更等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 聊天机器人
---

# 三剪客 · QQ 机器人协议端

想让自己的程序收发 QQ 消息，最省事的做法不是去啃协议，而是中间隔一层"翻译器"：程序这边只说 HTTP 或 WebSocket，翻译器那边负责和 QQ 通信。go-cqhttp 就是这层翻译器——它是 OneBot v11 标准的一个原生实现，把你的机器人框架和 QQ 彻底解耦。

关键前提必须放在最前面：**上游已经明确表示无力继续维护这个项目**。README「重要信息」一节的原文口径是，由于官方针对协议库不断更新加密方案，维护方已无力继续维护，并建议机器人开发者尽快迁移到无头 NTQQ 方案。上游还在 2023 年 10 月发布过一份迁移公告，说明在签名服务方案被彻底封堵之后本项目将无法继续使用，同期发布的版本也是最后一次更新——换句话说，这个项目实际上是停更状态。所以这份文档的定位是「维护存量部署 + 评估迁移」，不是「推荐新项目上手」。

**上游项目**：`go-cqhttp`　**仓库**：https://github.com/Mrs4s/go-cqhttp

## 什么时候用 / 不用

**用它**：

- "我手上已经跑着一套 go-cqhttp，现在要改配置 / 换端口 / 加个连接方式。"——存量运维是它现在最主要的使用场景。
- "我的机器人框架只实现了 OneBot v11，需要一端对接。"——它完整支持 OneBot v11 的绝大多数内容，并做了部分扩展。
- "我想同时提供 HTTP 接口和 WebSocket 推送。"——HTTP API、反向 HTTP POST、正向 WS、反向 WS 四种通信方式都支持，还能多条并存。
- "想发合并转发、回复、戳一戳、语音这类扩展消息。"——标准 CQ 码之外还实现了扩展 CQ 码和扩展 API。
- "想在自己机器上跑一个占用很小的常驻进程。"——官方给的数据是：关掉数据库时 25 好友 128 群挂 24 小时约 15MB 内存。

**不要用它**：

- **新项目选型**——上游已停止维护，官方口径就是建议迁移到无头 NTQQ 方案；新项目应优先评估仍在维护的协议端。
- **要做合规、稳定、可长期运营的商业机器人**——依赖非官方协议登录，账号本身有被风控甚至封禁的风险，且没有官方支持渠道。
- **目标是企业办公自动化**——这类需求应走各平台官方的开放接口（机器人开放平台），用官方能力换取稳定性与合规性。
- **只想跑一个本地测试机器人**——不需要 QQ 协议端，用聊天框架自带的控制台适配器就够了。
- **需要协议端自行实现你的业务逻辑**——它只做协议翻译，业务逻辑必须写在你的机器人程序里。

## 安装

### 方式一：下载 release 二进制（最省事）

从 release 页下载对应平台的压缩包，命名规律是 `go-cqhttp_<系统>_<架构>.tar.gz`（或 Windows 的 `.zip` / `.exe`）。同目录的 `go-cqhttp_checksums.txt` 里有 `SHA-256`，可用于校验文件完整性。

```bash
# Linux 解压（Windows 用解压软件直接解压）
tar -xzvf go-cqhttp_linux_amd64.tar.gz

# 首次运行：会提示找不到 config.yml，并自动生成一份默认配置
./go-cqhttp

# 编辑 config.yml 填账号与连接方式后再次运行
./go-cqhttp
```

首次登录成功后，同目录会生成 `device.json`（虚拟设备信息）。

### 方式二：从源码构建

需要 Go 环境，在仓库根目录执行：

```bash
go build -ldflags "-s -w -extldflags '-static'"
```

国内拉依赖慢的话可以先设代理：

```bash
go env -w GOPROXY=https://goproxy.cn,direct
```

需要自定义核心或加插件模块时，官方提供了 `xgo-cqhttp` 这个构建工具：

```bash
go install github.com/RomiChan/xgo-cqhttp/cmd/xgo-cqhttp@latest

# 只构建默认核心
xgo-cqhttp build --output ./go-cqhttp

# 以某个版本为核心并附加数据库插件
xgo-cqhttp build v1.0.0-rc1 --with github.com/Mrs4s/go-cqhttp/db/mongodb
```

### 方式三：容器部署

官方镜像托管在 GitHub 的容器仓库，把配置和设备文件挂载进去即可：

```bash
docker pull ghcr.io/mrs4s/go-cqhttp:master

docker run \
  -v /path/to/config.yml:/data/config.yml \
  -v /path/to/device.json:/data/device.json \
  -p 2333:8080 \
  -d \
  --name cqhttp \
  ghcr.io/mrs4s/go-cqhttp:master
```

`-p 2333:8080` 是把容器内 8080 端口映射到主机 2333；如果你只用反向连接（由 go-cqhttp 主动连出去），这一行可以去掉。第一次登录可能要扫码，用 `docker container logs cqhttp` 看日志里的二维码。

### 后台常驻

官方明确提醒：断开 SSH 后进程会退出，需要配合 `screen` 之类的工具保证持续运行。生产环境建议改用 systemd 之类的进程管理器，并配置开机自启与崩溃重启。

```bash
# 快速实验用
screen -S gocq
./go-cqhttp
# Ctrl+A D 脱离，screen -r gocq 回到会话
```

## 常用操作

**1. 启动参数**

官方文档给出的参数里，日常最常用的是这几个（完整列表以本机 `-h` 输出为准）：

```bash
./go-cqhttp -faststart        # 跳过启动时的 5 秒延时
./go-cqhttp -c my-config.yml  # 指定配置文件，默认 config.yml
./go-cqhttp -d                # 以守护进程方式运行
./go-cqhttp -w /data/gocq     # 指定工作目录
./go-cqhttp -update-protocol  # 提示版本过低时尝试更新协议
```

另有两个非选项形式的子命令：`./go-cqhttp update [镜像URL]` 用于自更新（国内可指定镜像源加速），`./go-cqhttp key <key>` 用于处理密码加密相关的密钥。

**2. 最小可用的 config.yml**

首次运行生成的文件里在 `account` 和 `servers` 两处填内容即可。`account.password` 留空时走扫码登录：

```yaml
account:
  uin: 1233456          # QQ 账号
  password: ''          # 留空则扫码登录
  status: 0             # 在线状态，0 = 在线
  relogin:
    delay: 3
    interval: 3
    max-times: 0        # 0 表示无限重连

message:
  post-format: string   # string 或 array，取决于你的框架要哪种

servers:
  - http:
      address: 0.0.0.0:5700
      middlewares:
        <<: *default
```

**3. 四种通信方式怎么填**

```yaml
servers:
  # 1) HTTP API：你的程序主动调 http://ip:5700/send_group_msg
  - http:
      address: 0.0.0.0:5700

  # 2) 正向 WebSocket：你的程序连过去
  - ws:
      address: 0.0.0.0:8080

  # 3) 反向 WebSocket：go-cqhttp 主动连你的框架（NoneBot2 等推荐）
  - ws-reverse:
      universal: ws://127.0.0.1:8080/onebot/v11/ws
      reconnect-interval: 3000
```

不需要的连接方式可以注释掉，或在该段加 `disabled: true` 关掉。

**4. 给接口加访问密钥**

公网服务器上强烈建议设置。`access-token` 在默认中间件锚点里定义，`servers` 各段用 `<<: *default` 引用：

```yaml
default-middlewares: &default
  access-token: '换成你自己的长随机串'
```

**5. 配置签名服务器**

遇到登录报错 45 或发消息被风控时，需要填签名服务地址：

```yaml
account:
  sign-servers:
    - url: 'http://127.0.0.1:8080'   # 主签名服务器，必填
      key: '114514'
      authorization: '-'
    - url: 'https://signserver.example.com'  # 备用
      key: '114514'
      authorization: '-'
  sign-server-timeout: 60
  refresh-interval: 40               # 定时刷新 token，建议 30~40 分钟，不可超过 60
```

官方建议主备各一个即可，配超过 5 个只会取前 5 个；如果签名服务版本在 1.1.0 及以下，要把 `is-below-110` 设为 `true`。

**6. 用环境变量注入敏感项**

配置文件支持占位符读取环境变量，账号密码可以不写死在文件里：

```yaml
account:
  uin: ${CQ_UIN}
  password: ${CQ_PWD:默认值}
```

**7. 用 HTTP 接口自测**

配好 HTTP 通信后，直接发一条私聊消息验证链路：

```bash
# 没设访问密钥时直接调
curl 'http://127.0.0.1:5700/send_private_msg?user_id=10001&message=test'

# 设了 access-token 时带上
curl 'http://127.0.0.1:5700/send_private_msg?user_id=10001&message=test&access_token=你的密钥'
```

返回 `{"status":"ok","retcode":0,...}` 说明 HTTP 通道已经通了。常用的还有 `send_group_msg`、`get_group_list`、`get_login_info`、`delete_msg`、`set_group_ban`。

**8. 修改在线状态与设备协议**

`account.status` 是在线状态码（0 在线、1 离开、2 隐身、3 忙、4 听歌中……以官方配置页的状态表为准）。`device.json` 里的 `protocol` 决定虚拟设备类型，常见值 1 是 Android 手机、5 是 iPad、2 是 Android 手表（手表协议收不到通知类事件、收不到口令红包与撤回消息）。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 项目已经无人维护，出新问题没人管 | 上游在 README 中明确说明：由于官方不断更新加密方案，已无力继续维护，并建议迁移到无头 NTQQ 方案 | 新项目直接选别的协议端；存量部署要接受"自己扛"的现实，并尽早规划迁移 |
| 登录报错误码 45，或发消息提示被风控 | QQ 侧的加密与风控策略变化，需要签名服务参与 | 在 `account.sign-servers` 里填主备签名服务地址与 key；签名服务版本低于 1.1.0 时记得把 `is-below-110` 设为 `true` |
| 挂一段时间后提示"消息发送失败，账号可能被风控" | 官方 FAQ 的说法：新账号需要一个"养"的过程 | 官方建议刚开始使用时连续挂机 3~7 天再观察；期间不要高频群发 |
| 换了 `device.json`、账号或协议类型后就要重新验证设备 | 登录态与虚拟设备信息绑定，设备指纹变化会被要求重新认证。官方文档与 README 没有专门写"改 `device.json` 必然要重登"，但认证提示与设备恢复逻辑都指向这一点 | 登录成功后把 `device.json` 一起纳入备份；不要随手删除或替换它；真要改就先接受需要重新认证 |
| 重启后提示缓存里的 QQ 号和配置里的不一致 | 工作目录下的 `session.token`（会话缓存）记录的是上次登录的账号，与 `config.yml` 的 `uin` 不是同一个 | 按提示二选一：继续用会话缓存，或删掉会话缓存重启；换账号时务必删缓存，否则会一直登不上新号 |
| 提示"版本过低" | 客户端协议版本落后于 QQ 侧 | 启动时加 `-update-protocol`；如果还在用会话缓存，需要先删掉缓存再让它更新协议 |
| 原来能登录，重启后账号掉线且无法自动恢复 | 数据库关闭时部分上下文功能不可用；或登录态本身失效 | 别关 `database.leveldb`（关掉会增加内存但保留撤回/回复/`get_msg` 等能力）；掉线后检查是否需要重新扫码 |
| 发长消息失败或客户端显示异常 | 分片发送是旧方案的兼容手段，在限频群里可能发不出去；关掉分片则发送更慢、老客户端可能解析不了 | 按目标群情况调 `message.force-fragment`，不要盲目开或关 |
| 后台跑着跑着就没了 | 直接在前台或 SSH 会话里运行，连接断开进程即退出 | 官方建议用 `screen` 之类的工具保持常驻；生产环境用 systemd 管理并配置自动重启 |
| 服务器上连接质量差、频繁掉线 | 官方提示 `use-sso-address` 在海外服务器上可能让连接更差；也可能是 DNS 链路问题 | 把 `account.use-sso-address` 设为 `false` 试试；必要时在工作目录建 `address.txt` 手动指定服务器 `IP:PORT` |
| 心跳一关就断线 | 官方明确提示关闭心跳服务可能引起断线 | 保持 `heartbeat.interval` 为正常秒数（`-1` 才是关闭），不要随意关 |
| 接口被公网扫到，被人拿去发消息 | HTTP 监听在 `0.0.0.0` 且没有设置访问密钥 | 设置 `access-token`，并用防火墙限制来源 IP；能用反代就只对反代开端口 |
| 自定义构建或插件加载失败 | 模块版本与核心版本不匹配 | 用 `xgo-cqhttp build` 显式指定核心版本与 `--with` 的模块版本，必要时用本地替换调试 |
| 构建出的二进制约 0 字节或缺少版本信息 | 构建命令与官方给的不一致 | 官方文档给出的构建命令是 `go build -ldflags "-s -w -extldflags '-static'"`，先按原样跑通再改 |
| 发图片或表情包失败 | 官方 CQ 码页面写明的媒体限制：图片不能超过 30MB，GIF 动图总帧数不能超过 300 张 | 发送前压缩或裁剪；注意 PNG 不会被压缩、非动图 GIF 会被转成 PNG，体积会变 |
| 用 `[CQ:xml]` 发卡片消息时失败 | 官方提示 XML 类消息本身存在风控风险 | 不要依赖它做关键通知，并在业务侧处理发送失败后的兜底 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 与 QQ 服务器建立长连接、拉取或上传图片语音等资源、连接签名服务、向配置的上报地址推送事件 |
| 读取文件 | 是 | 读取 `config.yml`、`device.json`、日志目录、filter 过滤器配置，以及待发送的本地文件 |
| 写入文件 | 是 | 生成并写入 `config.yml`、`device.json`、日志文件；开启内置数据库后写入 LevelDB / SQLite 数据目录 |
| 凭证 | 是 | QQ 账号密码或登录 token、签名服务 key、接口 `access-token`。强烈建议用环境变量占位符注入而不是明文写在 `config.yml` 里，并限制该文件权限 |
| 子进程 / 后台常驻 | 是 | 本身就是一个需要 7×24 常驻的进程，且需要被进程管理器守护；`update` 等操作会触发自更新 |

## 触发场景

- "我的 go-cqhttp 登录报 45，怎么办？"
- "config.yml 里反向 WebSocket 怎么写？"
- "机器人接不上 QQ，帮我查一下是端口问题还是协议问题。"
- "想把 QQ 机器人换成还在维护的方案，有哪些选择？"
- "go-cqhttp 内存占用大不大，能跑在小机器上吗？"
- "怎么给 go-cqhttp 的接口加个访问密钥？"

## 能力边界

**覆盖**：

- 协议转换：实现 OneBot v11 的绝大多数内容，并提供扩展 CQ 码与扩展 API
- 通信方式：HTTP API、反向 HTTP POST（支持多点上报）、正向 WebSocket、反向 WebSocket（支持多点连接）
- 消息能力：文本、图片、语音、短视频、@、表情、链接分享、音乐分享、回复、合并转发、XML/JSON 消息等
- 管理与查询：好友/群列表、群成员信息、群荣誉、禁言踢人、设置群名片与群名、加好友与加群请求处理、撤回消息、`get_msg`、`get_status`
- 运维相关：在线状态设置、虚拟设备协议切换、重连参数、心跳、日志等级与保留天数、内置 LevelDB/SQLite 上下文数据库、自定义构建

**不覆盖**：

- 业务逻辑：不解析你的指令、不做对话、不管插件，一切业务都在你的机器人程序里
- 新协议支持：不跟进 QQ 官方新协议与官方机器人开放平台
- 账号安全兜底：不对账号被风控、被限制、被封禁提供任何保障
- 持续维护：不再修复新的协议变化导致的问题
- 多平台：只面向 QQ 一侧，其他平台需要各自的协议端 / 适配器

## 依赖条件

- 无需运行时依赖即可运行（release 为静态链接的单文件二进制，构建命令里也带 `-static`）
- 从源码构建需要 Go 工具链（仓库声明的 Go 版本以 `go.mod` 为准）；自定义构建的 `xgo-cqhttp` 同样需要 Go
- 想发送任意格式语音，需要额外安装 `ffmpeg` 并加入 `PATH`
- 需要一个可用的 QQ 账号，以及（新版本风控环境下）一个可用的签名服务
- 登录时可能需要人工完成设备验证 / 扫码；扫码登录只支持手表类设备协议，而该协议收不到通知类事件、口令红包和撤回消息
- 官方口径：内存小于 128M 的机器建议关闭内置数据库运行

## 已知限制

1. 上游已停止维护：README 中明确说明无力继续跟进，并建议迁移到无头 NTQQ 方向的项目；2023 年 10 月的迁移公告同时说明签名服务方案被封堵后本项目将无法继续使用，此后没有新版本发布。
2. 依赖非官方协议登录，账号存在被风控、限制甚至封禁的风险，且无官方支持渠道。
3. 签名服务是登录与发消息的关键外部依赖，其可用性不受本项目控制；签名服务版本过低时账号会频繁被冻结。
4. 工作目录下的 `session.token`、`device.json`、内置数据库等状态文件与登录态强绑定，迁移或误删会导致需要重新登录。
5. 版本与参数会随发布变化，本文中的键名以官方文档站当前内容为准；执行前请对照本机生成的 `config.yml` 注释确认。
6. 该项目本体采用 AGPL-3.0 许可；官方文档站是另一套许可，二次分发时需分别确认。
7. 不建议用于对稳定性、合规性有硬要求的商业场景。

## 自检清单

执行前：

- [ ] 已确认这是存量运维需求；若是新项目，先评估仍在维护的替代方案
- [ ] 使用场景与账号风险已评估，账号有被风控的预期
- [ ] `config.yml` 中的 `servers` 只保留真正需要的方式，其余已注释或加 `disabled: true`
- [ ] 公网可达的接口已经设置 `access-token`，并用防火墙限制来源
- [ ] 需要签名时 `sign-servers` 已配好主备与 `key`，并设置了合理的 `refresh-interval`
- [ ] `device.json` 与 `config.yml` 已纳入备份，并确认文件权限不含他人可读
- [ ] 进程已交给 `screen` / systemd 之类的守护方式，不会随 SSH 断开而退出

执行后：

- [ ] 日志出现"登录成功"，且 `device.json` 已生成
- [ ] 用一条测试接口（如发私聊消息）验证通信链路，返回 `retcode: 0`
- [ ] 反向 WS / 反向 HTTP 的上报地址能收到事件推送
- [ ] 观察一段时间没有"登录态失效"与"被风控"提示
- [ ] 确认内存占用在机器可承受范围内（数据库开启会额外占用 10~20MB）

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/Mrs4s/go-cqhttp | 上游仓库（README 首屏的维护状态说明必读） |
| https://github.com/Mrs4s/go-cqhttp/issues/2471 | 上游发布的迁移公告：为何停止维护、建议迁往何处 |
| https://docs.go-cqhttp.org/guide/config.html | 官方配置说明：`config.yml` 全部字段、在线状态表、`device.json` 结构 |
| https://docs.go-cqhttp.org/guide/quick_start.html | 官方开始使用：下载命名规律、各平台启动方式、构建与更新 |
| https://docs.go-cqhttp.org/guide/docker.html | 官方容器部署：镜像地址与挂载方式 |
| https://docs.go-cqhttp.org/cqcode/ | 官方 CQ 码说明：各消息类型与媒体体积限制 |
| https://docs.go-cqhttp.org/faq/ | 官方常见问题 |
| https://docs.go-cqhttp.org/advanced/ | 自定义构建（`xgo-cqhttp`）用法 |

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
