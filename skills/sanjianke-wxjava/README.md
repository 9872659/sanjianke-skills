# 三剪客 · 微信生态 Java 服务端开发包 Skill

在 Java 服务端接微信各条业务线（公众号、小程序、支付、企业微信、开放平台、视频号小店）的选型、引入、配置与避坑要点。

---

## 前置条件

- JDK 8 及以上（当前主线；JDK 7 只能使用很早的旧版本）。
- Maven 或 Gradle 工程，能访问 Maven Central。
- 一个已在微信平台完成注册与配置的应用：公众号 / 小程序 / 商户号 / 企业微信 / 开放平台第三方平台，按业务线准备。
- 对应的密钥材料：AppID、Secret、Token、EncodingAESKey；支付还需商户号、API 密钥或 V3 密钥、API 证书与私钥文件。
- 使用 Spring Boot Starter 时需要一个 Spring Boot 工程。

---

## 使用

1. 先在 `SKILL.md` 的模块表里确定业务线对应的 artifactId，别一次把全部模块都引进来。
2. 多模块项目用 `wx-java-bom` 统一版本；单模块直接引 `weixin-java-*`。
3. Spring Boot 项目优先用 `wx-java-*-spring-boot-starter`（多账号场景选带 `multi` 的），写好 `wx.mp.*` 或 `wx.pay.*` 配置即可注入 `WxMpService`、`WxMpConfigStorage` 等对象。
4. 生产环境务必把令牌存储从默认内存切到 Redis，多实例部署还要自定义消息去重。
5. 被动消息用 `WxMpMessageRouter` 配规则，规则从细到粗、每条 `end()` 收尾，进程退出前关掉内部线程池。
6. 支付相关先确认证书路径在部署产物里存在，密钥与证书不要提交到代码仓库。

---

## 依赖

- JDK 8 及以上。
- Maven 或 Gradle。
- 可选：Redis（Jedis 依赖或 Spring Data Redis）——集中存储令牌时必需。
- 可选：lombok——仅阅读源码或从源码构建时需要，使用发布 jar 不受影响。
- 可选：Spring Boot——使用官方 starter 时需要。

---

## 安全

- 不内嵌任何密钥；AppID / Secret / API 密钥 / V3 密钥 / 证书序列号都由使用方自行配置与保管。
- 支付证书与私钥文件不要提交到代码仓库，通过挂载或构建时注入；容器镜像里也要确认带上。
- 推荐的 HTTP 客户端实现为 HttpComponents 5.x，其余实现按项目现状选择，避免混用多套 HTTP 客户端。
- 被动消息回调地址要做好来源校验，路由与业务处理里不要直接信任消息体里的用户输入。
- 多账号场景使用内置的账号切换能力，不要把不同主体的密钥混在一份全局配置里。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`WxJava`
- 仓库：https://github.com/binarywang/WxJava

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
