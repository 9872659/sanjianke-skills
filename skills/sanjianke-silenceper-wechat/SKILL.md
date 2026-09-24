---
name: sanjianke-silenceper-wechat
slug: sanjianke-silenceper-wechat
displayName: 三剪客 · Go 微信 SDK
description: "silenceper/wechat：Go 语言微信 SDK 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "silenceper/wechat：Go 语言微信 SDK 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 社媒
  - 营销
---

# 三剪客 · Go 微信 SDK

用 Go 写公众号或小程序后端时，真正烦人的不是业务代码，而是微信那套**既多又碎**的接口：`access_token` 要自己缓存刷新、消息要验签要解密要按顺序回、菜单与素材是一层层嵌套的结构体。每接一个能力就抄一遍这些样板，抄错一处就是线上 40164 或者回调验签失败。

这个 SDK 把微信各条产品线拆成互相独立的模块，统一从一个 `Wechat` 实例上取：公众号、小程序、小游戏、微信支付、开放平台、企业微信、智能对话。每个模块自己管好 token 与请求签名，业务侧只需要把 `AppID` / `AppSecret` 这类配置传进去，然后调方法。

**上游项目**：`silenceper/wechat`　**仓库**：https://github.com/silenceper/wechat

## 什么时候用 / 不用

**用它**：

- "我用 Go 写公众号后端，要收用户消息并按内容回复。"——`GetOfficialAccount` + `GetServer(req, rw)` + `SetMessageHandler` 就是为这个流程准备的。
- "多台机器跑同一个公众号，`access_token` 老是互相顶掉。"——SDK 把 token 交给 `cache.Cache` 接口管理，换成 Redis 即可共享。
- "小程序登录换 openid、解密加密数据、生成小程序码。"——`GetMiniProgram` 下的 `auth` / `encryptor` / `qrcode` 模块直接对应。
- "要调微信支付的下单、退款、通知回调。"——`GetPay` 下的 `order` / `refund` / `notify` 已经封装。
- "公司已经有自己的 token 中台，不想让 SDK 再管一份。"——实现 `AccessTokenHandle` 接口并挂到实例上即可接管。

**不要用它**：

- **你要做的是微信**个人号**自动化（自动回消息、拉群）**——那是客户端接管类工具的领域，跟这套官方接口 SDK 完全不是一条路，别混。
- **你的技术栈不是 Go**——它是纯 Go 库，没有跨语言绑定；其他语言找各自的 SDK 或直接调 HTTP API。
- **你要的是抖音、小红书这类非微信渠道**——渠道不对，接口体系也不通用。
- **你只想做"发个通知"**——短信、邮件、App 推送这类通道比走公众号模板消息更直接，不必引入整套微信鉴权。
- **你希望它替你处理平台资质与审核，或者以为它覆盖微信**全部**接口**——它只做接口封装，账号资质、类目申请、模板报备都要你自己在微信侧办完；未实现的接口也得自己按官方文档补或直接发 HTTP 请求。

## 安装

用 Go modules 管理依赖，**导入路径必须带 `/v2`**：

```bash
# 初始化自己的项目（路径换成你自己的模块名）
go mod init github.com/yourname/wechat-example

# 拉取 SDK
go get github.com/silenceper/wechat/v2

# 整理依赖
go mod tidy
```

如果只需要校验依赖能不能拉齐、编译能不能过：

```bash
go build ./...
go vet ./...
```

**版本与导入路径的对应关系**：`github.com/silenceper/wechat/v2` 是 2.x 系列；**不带 `/v2` 的导入路径会拉到 1.x 系列**，两者 API 差别很大，抄代码时先看清导入路径。

最短跑通：写一个 `main.go`（下面「常用操作」第 1 条就是可运行的最小版本），然后：

```bash
go run main.go
# 期望输出类似：wechat server listen at :8001
```

启动后用 `http://127.0.0.1:8001/` 自测应在本地即可访问。要真正收到微信推来的消息，还需要一个能被公网访问的地址（本地调试常用内网穿透工具把端口映射出去），并在公众号后台把该地址填进「服务器配置」。

本包不涉及大模型调用或 GPU 算力（纯 CPU 的 Go HTTP 库），因此不附带算力接入说明。

## 常用操作

**1. 最小可运行：接收公众号消息并回复**

```go
package main

import (
    "fmt"
    "net/http"

    wechat "github.com/silenceper/wechat/v2"
    "github.com/silenceper/wechat/v2/cache"
    offConfig "github.com/silenceper/wechat/v2/officialaccount/config"
    "github.com/silenceper/wechat/v2/officialaccount/message"
)

func serveWechat(rw http.ResponseWriter, req *http.Request) {
    wc := wechat.NewWechat()
    memory := cache.NewMemory()          // 仅适合本地调试，生产见第 2 条
    cfg := &offConfig.Config{
        AppID:     "xxx",
        AppSecret: "xxx",
        Token:     "xxx",
        // EncodingAESKey: "xxxx",       // 填了才走 AES 加解密
        Cache: memory,
    }
    officialAccount := wc.GetOfficialAccount(cfg)

    server := officialAccount.GetServer(req, rw)
    server.SetMessageHandler(func(msg message.MixMessage) *message.Reply {
        text := message.NewText(msg.Content)   // 演示：原样回显
        return &message.Reply{MsgType: message.MsgTypeText, MsgData: text}
    })

    if err := server.Serve(); err != nil {     // 先 Serve 处理请求
        fmt.Println(err)
        return
    }
    server.Send()                              // 再 Send 发出回复
}

func main() {
    http.HandleFunc("/", serveWechat)
    fmt.Println("wechat server listen at", ":8001")
    if err := http.ListenAndServe(":8001", nil); err != nil {
        fmt.Printf("start server error, err=%v", err)
    }
}
```

**2. 把 token 缓存换成 Redis（多实例部署必须做）**

```go
import (
    wechat "github.com/silenceper/wechat/v2"
    "github.com/silenceper/wechat/v2/cache"
    offConfig "github.com/silenceper/wechat/v2/officialaccount/config"
)

wc := wechat.NewWechat()
redisOpts := &cache.RedisOpts{
    Host:        "127.0.0.1:6379",   // 注意要带端口
    Password:    "",
    Database:    0,
    MaxActive:   10,
    MaxIdle:     10,
    IdleTimeout: 60,                 // 单位：秒
}
redisCache := cache.NewRedis(redisOpts)

cfg := &offConfig.Config{
    AppID:     "xxx",
    AppSecret: "xxx",
    Token:     "xxx",
    Cache:     redisCache,
}
officialAccount := wc.GetOfficialAccount(cfg)
```

三种现成缓存：`cache.NewRedis(redisOpts)`、`cache.NewMemcache("127.0.0.1:11211")`、`cache.NewMemory()`。

**3. 手动取 access_token**

```go
ak, err := officialAccount.GetAccessToken()
if err != nil {
    // 常见失败：IP 不在白名单、AppSecret 错、额度超限
}
fmt.Println(ak)
```

**4. 自己去中台取 token（接管刷新逻辑）**

```go
type myTokenHandle struct{}

func (h *myTokenHandle) GetAccessToken() (string, error) {
    return "从中台拿到的-token", nil
}

officialAccount.SetAccessTokenHandle = &myTokenHandle{}
```

接口定义只有一个方法：

```go
type AccessTokenHandle interface {
    GetAccessToken() (accessToken string, err error)
}
```

**5. 菜单管理**

```go
import "github.com/silenceper/wechat/v2/officialaccount/menu"

m := officialAccount.GetMenu()

// 查询当前菜单
res, err := m.GetMenu()

// 用 struct 方式设置菜单
buttons := []*menu.Button{
    {Name: "首页", Type: "view", URL: "https://example.com"},
}
err = m.SetMenu(buttons)

// 也可以直接传 JSON
err = m.SetMenuByJSON(`{"button":[{"type":"view","name":"首页","url":"https://example.com"}]}`)

err = m.DeleteMenu()
```

`Button` 结构体的字段名（如 `Name` / `Type` / `URL`）以本机依赖里的类型定义与官方文档为准。

**6. 用户管理与群发**

```go
u := officialAccount.GetUser()
info, err := u.GetUserInfo("openid-xxxx")            // 用户基本信息
err = u.UpdateRemark("openid-xxxx", "备注名")
list, err := u.ListUserOpenIDs()                     // 用户列表，翻页用 NextOpenID

bd := officialAccount.GetBroadcast()
err = bd.SendText(nil, "发给所有人的文本")            // 第一个参数为 nil 表示发给所有人
err = bd.SendText(&broadcast.User{TagID: 1}, "只发给某个标签")
err = bd.SendText(&broadcast.User{OpenID: []string{"openid-1", "openid-2"}}, "只发给指定 openid")
```

群发还有 `SendNews(user, mediaID, ignoreReprint)`、`SendImage(user, images)`、`SendVoice(user, mediaID)`、`SendVideo(user, mediaID, title, description)`。

**7. 小程序：登录换 openid、生成小程序码**

```go
mini := wc.GetMiniProgram(&miniConfig.Config{
    AppID:     "xxx",
    AppSecret: "xxx",
    Cache:     redisCache,
})

// 用 code 换 session
result, err := mini.GetAuth().Code2Session("js_code")
```

小程序码、订阅消息、云开发等能力分布在 `miniprogram` 下的 `qrcode` / `subscribe` / `tcb` 等子包，具体方法与参数以官方文档对应页面为准。

**8. 企业微信与微信支付**

```go
// 企业微信
work := wc.GetWork(&workConfig.Config{CorpID: "xxx", CorpSecret: "xxx", Cache: redisCache})

// 微信支付
pay := wc.GetPay(&payConfig.Config{AppID: "xxx", MchID: "xxx", ApiKey: "xxx", Cache: redisCache})
```

两个模块内部还各自细分成 `addresslist` / `appchat` / `kf` 与 `order` / `refund` / `notify` / `redpacket` / `transfer` 等子包，按需取用。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 引用回来的类型、方法名跟示例完全对不上 | 导入路径漏了 `/v2`，拉到了 1.x 系列，两个大版本 API 差异很大 | 统一写成 `github.com/silenceper/wechat/v2`；`go.mod` 里确认依赖版本是 `v2.x` |
| 多实例部署时 `access_token` 频繁互相顶掉，接口随机报错 | 默认或 `cache.NewMemory()` 是进程内内存缓存，每个实例各存一份，刷新即失效 | 换成 `cache.NewRedis(...)` 或 `cache.NewMemcache(...)`，让所有实例共享同一份 token；`NewMemory()` 官方明确标注**不推荐用于生产** |
| Redis 缓存怎么都连不上，或读不到 key | `RedisOpts.Host` 只写了 IP、没带端口 | `Host` 写成 `127.0.0.1:6379` 这种「主机:端口」格式 |
| 公众号后台保存服务器配置时一直提示失败 | 回调验签没通过。Token 不一致、`EncodingAESKey` 与加密模式不匹配、或地址根本不可达 | 先在本地用内网穿透把端口暴露出去；核对 Token 与加密方式；本地联调阶段可以 `server.SkipValidate(true)` 先跳过校验（**上线前务必关掉**） |
| 启用了安全模式抓不到消息内容 | 只填了 `EncodingAESKey` 但没把消息加解密链路走通，或者漏了该字段导致按明文处理 | 加密模式要把 `EncodingAESKey` 填上；确认回调地址与后台配置的加密方式一致 |
| 收不到回复，或日志里报发送顺序不对 | 收到了请求但没按「先 `Serve()` 处理、再 `Send()` 回复」的顺序调用 | 严格按顺序：`Serve()` 完成后立即 `Send()`；`Serve()` 返回错误时直接 return，不要再 `Send()` |
| 日志里能看到 AppSecret、token 之类的敏感值 | SDK 内部用 logrus 输出日志，默认会打到 stdout 且为 Debug 级别 | 在自己的 `main` 里覆盖 logrus 配置，把级别调高并对敏感字段做脱敏，别让原始日志进生产采集 |
| `GetUserInfo` 之类的接口报 IP 不在白名单 | 公众号后台配置了 IP 白名单，而这是微信平台侧的限制 | 到公众号后台把服务器出口 IP 加进白名单；IP 会变的环境要提前规划固定出口 |
| 自己实现的 Cache 编译不过 | 接口方法签名没对齐 | 完整实现四个方法：`Get(key string) interface{}`、`Set(key string, val interface{}, timeout time.Duration) error`、`IsExist(key string) bool`、`Delete(key string) error` |
| 群发接口调用返回权限类错误 | 群发有平台侧的频率与权限限制，且不同账号类型可用能力不同 | 以微信官方文档与后台实际权限为准，不要按示例直接对生产账号压测 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | SDK 全部能力都是向微信服务器发 HTTP 请求；`go get` / `go mod tidy` 拉依赖也需要联网。注意出口 IP 可能要加进公众号后台白名单 |
| 读取文件 | 是 | 发送或上传素材、图片、视频、语音时需要读取本地文件；读取项目里的配置（AppID / AppSecret 等） |
| 写入文件 | 否 | SDK 本身不写业务数据到磁盘；token 缓存写在 Redis / memcache 中。下载媒体素材时会按你的代码写盘 |
| 凭证 | 是 | 需要公众号 / 小程序 / 商户的 `AppID`、`AppSecret`、`Token`、`EncodingAESKey`、支付 `ApiKey` 等。这些等同于账号控制权，必须放环境变量或配置中心，**绝不写进源码、绝不提交仓库** |
| 子进程 / 后台常驻 | 是 | 接收消息需要一个常驻的 HTTP 服务进程对外提供回调地址；通常用 systemd / 容器 / 进程管理器守护 |
| 账号操作 | 是 | 会以你的公众号 / 小程序 / 商户身份真实地回复用户消息、群发、改菜单、调支付。这些动作会真实触达用户，先在小号或测试号验证 |
| 用户数据处理 | 是 | 会拿到 openid、用户资料、消息内容等个人信息，属敏感数据；存储、导出与使用需自行承担合规责任 |

## 触发场景

- "我用 Go 写公众号后端，用户发消息要自动回复。"
- "公众号部署了多个实例，access_token 老是冲突怎么办。"
- "帮我用这个 SDK 把公众号自定义菜单设置好。"
- "小程序用 code 换 openid 该调哪个方法。"
- "公司有自己的 token 中台，怎么让这个 SDK 用我的 token。"
- "回调地址在微信后台一直保存失败，帮我看看是不是验签的问题。"

## 能力边界

**覆盖**：

- 实例与配置：`wechat.NewWechat()`，以及 `SetCache`（全局缓存）、`SetHTTPClient`（自定义 HTTP 客户端）
- 公众号（`GetOfficialAccount`）：`GetServer` 消息接收与回复、`GetMenu` 菜单管理与个性化菜单、`GetUser` 用户资料与备注、`GetBroadcast` 群发、`GetMaterial` 素材、`GetBasic` 获取微信服务器 IP 与清理调用频次、`GetAccessToken`、`SetAccessTokenHandle` 自定义 token；另有 `draft` 草稿、`freepublish` 发布、`datacube` 数据统计、`js` JSSDK、`oauth` 网页授权、`customerservice` 客服消息、`ocr` 等子包
- 小程序（`GetMiniProgram`）：登录 `auth`、消息解密 `encryptor`、小程序码 `qrcode` 与 `urllink`、订阅消息 `subscribe`、云开发 `tcb`、内容安全 `security`、数据分析 `analysis`、虚拟支付 `virtualpayment` 等
- 小游戏、微信支付（`GetPay`：`order` / `refund` / `notify` / `redpacket` / `transfer`）、开放平台（`GetOpenPlatform`：第三方平台代公众号/小程序）、企业微信（`GetWork`：通讯录 `addresslist`、群聊 `appchat`、客服 `kf`、外部联系人 `externalcontact`、打卡 `checkin`、发票 `invoice`、JSAPI 等）
- 智能对话（`GetAISpeech`）
- 缓存抽象：内置 Redis / Memcache / Memory，也可实现 `cache.Cache` 接口自定义
- 日志：接入 logrus，可自行覆盖输出与级别

**不覆盖**：

- 不做微信个人号自动化，那属于客户端接管类方案，与本 SDK 无关
- 不代办账号资质、类目申请、模板报备与 IP 白名单，这些都在微信平台侧办
- 不保证覆盖微信全部开放接口；未实现的接口需要自己按官方文档补，或直接发 HTTP 请求
- 不提供消息持久化、检索、可视化后台，业务数据要自己落库
- 不做频率限制与重试策略的兜底，平台侧的调用配额要自己控制
- 不内置大模型能力；`aispeech` 是封装微信侧的接口，不是通用模型网关

## 依赖条件

- Go 环境（支持 Go modules），导入路径必须带 `/v2`
- 一个已认证可用对应能力的微信公众号 / 小程序 / 商户号 / 企业微信企业，以及配套的 `AppID`、`AppSecret` 等凭证
- 接收消息需要：一个能被公网访问的回调地址（本地开发用内网穿透映射），且该地址已在平台后台完成服务器配置
- 多实例部署需要 Redis 或 memcache 作为共享缓存
- HTTP 层依赖 resty 与 logrus 等第三方库，由 `go mod tidy` 自动拉齐
- 各模块支持的具体接口范围以官方文档站与 `doc/api` 目录为准

## 已知限制

1. 这是按需实现的 SDK，不是微信开放接口的完整映射；找不到的方法就回到官方文档自己发请求。
2. 1.x 与 2.x 是两个不兼容的大版本，导入路径漏了 `/v2` 会拿到旧系列，报错信息往往很隐晦。
3. 官方文档站上的部分页面仍停留在旧版写法（例如消息处理回调的签名在不同页面不一致），**以本机依赖里的类型定义与 README 为准**。
4. `cache.NewMemory()` 官方标注不推荐用于生产，多实例下会出现 token 互顶。
5. 回调地址与加密方式是平台侧强约束，配置不匹配时保存就失败，属于必须提前规划的部署条件。
6. 本 Skill 里的类型名、方法名与参数名以抓到的官方文档为准；不同版本可能存在差异，请以本机实际依赖的签名为准。

## 自检清单

执行前：

- [ ] 导入路径带 `/v2`，`go.mod` 里依赖是 `v2.x`
- [ ] `AppID` / `AppSecret` / `Token` 等凭证来自环境变量或配置中心，未硬编码、未提交
- [ ] 生产环境已把缓存换成 Redis 或 memcache，不再是 `NewMemory()`
- [ ] 回调地址可被公网访问，且已在平台后台完成服务器配置
- [ ] 加密方式与 `EncodingAESKey` 的填写情况一致
- [ ] 出口 IP 已加入平台后台白名单
- [ ] 日志级别与脱敏已配置，不会把 AppSecret / token 原样打出来

执行后：

- [ ] 服务能正常启动并监听端口，`go build ./...` 与 `go vet ./...` 无报错
- [ ] 用测试号的真实消息验证「收到 → 回复」完整链路
- [ ] 多实例场景下验证 token 共享有效，没有互相顶掉
- [ ] 群发、菜单、支付这类有真实副作用的操作先在测试环境验证
- [ ] 本地联调时开的 `SkipValidate(true)` 已确认在上线前关闭
- [ ] 确认没有把含凭证的日志或配置文件提交进仓库

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/silenceper/wechat | 上游仓库（安装与完整文档以它为准） |
| https://silenceper.com/wechat/ | 官方文档站：各模块用法（公众号、小程序、开放平台） |
| https://pkg.go.dev/github.com/silenceper/wechat/v2 | API 参考：`Wechat` 实例类型与各模块入口方法 |

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
