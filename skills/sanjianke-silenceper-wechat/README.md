# 三剪客 · Go 微信 SDK Skill

silenceper/wechat：Go 语言微信 SDK 的安装、常用命令与避坑要点

---

## 前置条件

- **Go 环境**，并使用 Go modules 管理依赖。
- **导入路径必须带 `/v2`**：`github.com/silenceper/wechat/v2`。不带 `/v2` 会拉到 1.x 系列，两个大版本 API 差异很大。
- 一个可用的微信主体与配套凭证：公众号 / 小程序 / 商户号 / 企业微信企业，以及对应的 `AppID`、`AppSecret`、`Token`、`EncodingAESKey`、支付 `ApiKey` 等。
- **接收消息需要一个能被公网访问的回调地址**，并在平台后台「服务器配置」里填好、通过验签。本地开发通常用内网穿透工具把端口映射出去。
- **多实例部署需要 Redis 或 memcache** 作为共享缓存，否则各实例的 `access_token` 会互相顶掉。
- 出口 IP 可能需要加入平台后台的 IP 白名单，否则接口会返回白名单类错误。

---

## 使用

最短跑通路径：

```bash
go mod init github.com/yourname/wechat-example
go get github.com/silenceper/wechat/v2
go mod tidy
```

写一个最小 `main.go`（完整可运行版本见 `SKILL.md`「常用操作」第 1 条）：

```go
wc := wechat.NewWechat()
memory := cache.NewMemory()
cfg := &offConfig.Config{
    AppID: "xxx", AppSecret: "xxx", Token: "xxx",
    Cache: memory,
}
officialAccount := wc.GetOfficialAccount(cfg)

server := officialAccount.GetServer(req, rw)
server.SetMessageHandler(func(msg message.MixMessage) *message.Reply {
    text := message.NewText(msg.Content)
    return &message.Reply{MsgType: message.MsgTypeText, MsgData: text}
})

if err := server.Serve(); err != nil {   // 先 Serve
    return
}
server.Send()                            // 再 Send
```

运行：

```bash
go run main.go
# 期望输出类似：wechat server listen at :8001
```

把内网穿透给出的公网地址填进公众号后台完成服务器配置后，给公众号发一条消息即可看到回复。

`SKILL.md` 里另有 8 组可直接套用的示例：Redis 缓存、手动取 token、接管 token 中台、菜单管理、用户管理与群发、小程序登录、企业微信与微信支付。

---

## 依赖

- **语言与工具链**：Go（支持 Go modules）
- **模块导入路径**：`github.com/silenceper/wechat/v2`（必须带 `/v2`）
- **本项目的直接依赖**：HTTP 层用 resty，日志用 logrus；均由 `go mod tidy` 自动拉齐
- **缓存后端**：Redis 或 memcache（生产环境必需，用于共享 `access_token`）；`cache.NewMemory()` 仅供本地调试
- **回调地址**：接收消息需要公网可达的 HTTP 地址；本地开发需内网穿透工具
- **平台侧依赖**：微信公众号 / 小程序 / 商户号 / 企业微信的可用主体与所需权限，以及 IP 白名单配置
- 各模块支持的具体接口范围以官方文档站与仓库 `doc/api` 目录为准

---

## 安全

- 不内嵌任何密钥。`AppID` / `AppSecret` / `Token` / `EncodingAESKey` / 支付 `ApiKey` 等一律从环境变量或配置中心读取，**绝不写进源码、绝不提交仓库**。
- SDK 内部使用 logrus 输出日志，默认打到 stdout 且为 Debug 级别。上线前请覆盖日志配置、调高级别并对敏感字段脱敏，避免凭证随日志进入采集系统。
- 本地联调时可能用到 `server.SkipValidate(true)` 跳过回调校验，**上线前必须关闭**，否则任何人都能伪造回调。
- 它会以你的公众号 / 小程序 / 商户身份真实地回复用户、群发、改菜单、发起支付。群发与支付这类有真实副作用的操作先在测试号或测试环境验证。
- 通过该 SDK 会拿到 openid、用户资料、消息内容等个人信息，属敏感数据；存储、导出与使用需自行承担合规责任。
- 回调地址与加密方式（`EncodingAESKey`）是平台侧强约束，配置不一致不仅保存失败，也可能导致消息无法解密。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`silenceper/wechat`
- 仓库：https://github.com/silenceper/wechat

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
