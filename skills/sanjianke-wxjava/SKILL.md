---
name: sanjianke-wxjava
slug: sanjianke-wxjava
displayName: 三剪客 · 微信生态 Java 服务端开发包
description: "在 Java 服务端接微信各条业务线：公众号、小程序、微信支付、企业微信、开放平台、视频号小店。含 Maven/Gradle 与 Spring Boot Starter 两种引入方式、access_token 集中存储、被动消息路由、支付证书配置，以及签名验签与多账号场景的避坑要点。遇到问题可加技术微信 9872659。"
summary: "WxJava 把微信各业务线的 HTTP 调用、签名验签、消息加解密、令牌管理都封成 Java 方法，省掉自己啃协议的一周。这个 Skill 讲清该选哪个模块、怎么引依赖、怎么在 Spring Boot 里自动装配、令牌怎么落 Redis、被动消息怎么路由，以及版本号与证书这些高频翻车点。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 微信
---

# 三剪客 · 微信生态 Java 服务端开发包

在 Java 服务端接微信，麻烦的从来不是「调一个 HTTP 接口」，而是围着它转的一圈杂活：access_token 什么时候刷新、签名怎么算、回调消息怎么解密、支付证书怎么加载、多个公众号/商户怎么隔离。每家都自己写一遍，就是重复造轮子还容易在验签上出错。

WxJava 把这些杂活封成一套 Java API：公众号、小程序、微信支付、企业微信、开放平台、视频号小店各有独立模块，可以按需只引一个，也能用 BOM 或多个模块一起引。它**只提供 SDK，不提供 Web 界面**——你的项目负责暴露接口，它负责把微信那侧的协议细节处理干净。

**上游项目**：`WxJava`　**仓库**：https://github.com/binarywang/WxJava

## 什么时候用 / 不用

**用它**：

- Java / Spring Boot 项目要接**公众号**：自定义菜单、被动消息回复、模板消息、网页授权、素材管理。
- 小程序服务端要做 `code2Session`、订阅消息、内容安全等需要服务端密钥的调用。
- 要接**微信支付**（含 V3 与服务商模式）、**企业微信**、**开放平台**第三方平台或**视频号小店**，不想自己处理证书加载、签名与回调验签。
- 有多个公众号 / 多个商户，需要统一的令牌缓存与账号切换，而不是散落一堆静态变量。
- 需要**被动消息路由**：按消息类型、事件、关键词分发给不同的处理类，并做重复消息去重。

**不要用它**：

- **技术栈不是 JVM**。它是 Java 库，Node / Python / PHP / Go 各有自己的生态。
- **移动端 App 里的微信登录、分享 UI**。客户端那部分必须用微信官方移动端 SDK，本库只在服务端处理 OAuth 与支付逻辑。
- 想要**开箱即用的后台管理系统**。它不含 Web 实现，没有页面、没有数据库表结构。
- 只有 **JDK 6/7**。当前主线要求 JDK 8 及以上，老 JDK 只能用很早的旧版本。
- 想绕过微信官方接口的调用限制（频率、资质、类目），或指望完全免服务器的**小程序云开发**——前者 SDK 改变不了平台规则，后者属于平台侧能力而非服务端 SDK 的职责。

## 安装

**模块选择**（先定业务线，再定 artifactId）：

| 业务场景 | 模块 | artifactId |
|---|---|---|
| 微信公众号 | MP | `weixin-java-mp` |
| 微信小程序 | MiniApp | `weixin-java-miniapp` |
| 微信支付 | Pay | `weixin-java-pay` |
| 企业微信 | CP | `weixin-java-cp` |
| 微信开放平台（第三方平台） | Open | `weixin-java-open` |
| 视频号 / 微信小店 | Channel | `weixin-java-channel` |
| 公共依赖（一般由上面模块传递引入） | Common | `weixin-java-common` |

**方式一：BOM 统一管版本（多模块推荐）**

`wx-java-bom` 从 `4.8.3.B` 起提供，版本号只需写一处：

```xml
<properties>
  <wx-java.version>4.8.3.B</wx-java.version>
</properties>

<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.github.binarywang</groupId>
      <artifactId>wx-java-bom</artifactId>
      <version>${wx-java.version}</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>

<dependencies>
  <dependency>
    <groupId>com.github.binarywang</groupId>
    <artifactId>weixin-java-mp</artifactId>
  </dependency>
  <dependency>
    <groupId>com.github.binarywang</groupId>
    <artifactId>weixin-java-pay</artifactId>
  </dependency>
</dependencies>
```

**方式二：单独引一个模块**

```xml
<dependency>
  <groupId>com.github.binarywang</groupId>
  <artifactId>weixin-java-mp</artifactId>
  <version>4.8.0</version>
</dependency>
```

Gradle 等价写法：

```groovy
implementation 'com.github.binarywang:weixin-java-mp:4.8.0'
```

> 最新版本（含测试版）以 Maven Central 上该模块的版本列表为准；上面只是引法示例，别照抄版本号。正式版形如 `X.X.0`，测试版形如 `3.6.8.B`，另外还有每次提交自动构建的 `x.x.x-时间戳` 版本——**后者不要上生产**。

**方式三：Spring Boot Starter（最省事）**

官方为各模块提供了 starter，包含单账号与多账号两类：

```xml
<dependency>
  <groupId>com.github.binarywang</groupId>
  <artifactId>wx-java-mp-spring-boot-starter</artifactId>
  <version>${version}</version>
</dependency>
```

已有的 starter 覆盖：小程序（含多账号）、公众号（含多账号）、支付（含多账号）、开放平台（含多账号）、企业微信（含多账号、第三方多账号）、视频号/小店（含多账号）、企点、Store。多账号场景选带 `multi` 的那个。

**JDK 要求**：当前主线要求 JDK 8 及以上（上游模块的编译目标就是 1.8）。仍在使用 JDK 7 的项目只能用很早的旧版本，JDK 6 及更早需要自行改造。

## 常用操作

**1. 纯 Java 方式初始化公众号服务并拿令牌**

```java
WxMpDefaultConfigImpl config = new WxMpDefaultConfigImpl();
config.setAppId("your-app-id");
config.setSecret("your-secret");

WxMpService wxMpService = new WxMpServiceImpl();
wxMpService.setWxMpConfigStorage(config);

String accessToken = wxMpService.getAccessToken();
System.out.println(accessToken);
```

**2. 小程序服务端换取会话信息**

```java
WxMaDefaultConfigImpl config = new WxMaDefaultConfigImpl();
config.setAppid("your-app-id");
config.setSecret("your-secret");

WxMaService wxMaService = new WxMaServiceImpl();
wxMaService.setWxMaConfig(config);

WxMaJscode2SessionResult result = wxMaService.getUserService().getSessionInfo("js-code");
System.out.println(result.getOpenid());
```

**3. Spring Boot 里写配置就自动装配**

`application.properties`（字段来自官方 starter 说明）：

```properties
# 公众号配置（必填）
wx.mp.app-id=appId
wx.mp.secret=your-secret
wx.mp.token=your-token
wx.mp.aes-key=your-aes-key

# 令牌等配置的存储方式：Memory（默认）/ Jedis / RedisTemplate
wx.mp.config-storage.type=Jedis
wx.mp.config-storage.key-prefix=wx
wx.mp.config-storage.redis.host=127.0.0.1
wx.mp.config-storage.redis.port=6379

# HTTP 客户端类型：HttpComponents（Apache HttpClient 5.x，推荐）/ HttpClient（4.x）/ OkHttp / JoddHttp
wx.mp.config-storage.http-client-type=HttpComponents
```

配好之后可以直接注入，不需要自己 new：

```java
@Autowired
private WxMpService wxMpService;

@Autowired
private WxMpConfigStorage wxMpConfigStorage;
```

需要走代理或自建网关时，用 `wx.mp.hosts.api-host` / `wx.mp.hosts.open-host` / `wx.mp.hosts.mp-host` 覆盖默认域名。

**4. 被动消息路由（公众号）**

路由器按规则把消息分发给处理类，规则要**从细到粗**排列，且每条规则必须以 `end()` 收尾：

```java
WxMpMessageRouter router = new WxMpMessageRouter(wxMpService);

router
  .rule()
      .msgType("text").content("帮助")
      .handler((wxMessage, context, service, sessionManager) ->
          WxMpXmlOutMessage.TEXT().content("这是帮助信息").fromUser(wxMessage.getToUser())
              .toUser(wxMessage.getFromUser()).build())
  .end()
  .rule()
      .event("subscribe")
      .handler(subscribeHandler)
  .end();

// 收到回调后交给路由器，返回的 XML 直接回给微信
WxMpXmlOutMessage outMessage = router.route(wxMessage);
```

要点：默认每条消息只被处理一次；想让后面的规则继续处理要用 `next()` 而不是 `end()`；进程退出前应调用 `router.shutDownExecutorService()` 收掉内部线程池。

**5. 微信支付（V3）配置**

`application.yml`（字段来自官方 starter 说明）：

```yaml
wx:
  pay:
    appId: xxxxxxxxxxx
    mchId: 15xxxxxxxxx
    apiV3Key: your-api-v3-key
    certSerialNo: your-cert-serial-no
    privateKeyPath: classpath:cert/apiclient_key.pem   # 也支持绝对路径
    privateCertPath: classpath:cert/apiclient_cert.pem
```

服务商模式用 `configs` 列表分别配服务商与子商户（`mchId` / `subMchId` / `subAppId` 等）。V2 版本只需 `appId` / `mchId` / `mchKey` / `keyPath` 四项。走代理时加 `apiHostUrl` 与可选的 `apiHostUrlPath`。

**6. 多账号切换**

多账号不用自己维护 Map，路由时把 appId 传进去即可切换上下文：

```java
WxMpXmlOutMessage out = router.route(appId, wxMessage);
// 或者手动切换
wxMpService.switchoverTo(appId);
```

**7. 从源码构建 / 二次开发**

```bash
git clone https://github.com/binarywang/WxJava.git
cd WxJava
mvn -DskipTests install
```

源码中大量使用了 `lombok` 注解，阅读或改造源码前需要先在 IDE 里装好 lombok 插件；只引 jar 使用则不需要。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 按 starter 说明配了 Redis 存储但令牌仍在内存里、多实例各刷各的 | 说明里 `wx.mp.config-storage.type` 那一行的示例值有笔误（写成了 `edis`），照抄会填错类型名 | 按同段注释里给出的类型名填写：`Memory`（默认）/ `Jedis` / `RedisTemplate`，填错时不会报错但存储不生效 |
| 消息路由规则写了却完全不生效 | 规则没有以 `end()`（或 `next()`）收尾 | 每条规则都必须显式结束；需要继续匹配后续规则时用 `next()` |
| 关键词规则被更宽的规则先吃掉 | 规则排列顺序不对 | 按「从细到粗」排列：先精确内容/事件，再宽泛的类型兜底 |
| 消息偶尔被处理两次或重复回复 | 默认的重复消息检查器是进程内内存实现，多实例部署时各存一份 | 多实例场景自定义去重实现（如基于 Redis），并替换 `WxMessageDuplicateChecker` |
| 服务优雅下线时卡住或线程泄漏 | 路由器内部有固定大小线程池，默认不会自己关 | 退出前调用 `shutDownExecutorService()`，需要限时用带秒数参数的重载 |
| 线上频繁触发令牌刷新限制 | 使用默认的 Memory 存储，实例多、重启多，令牌各存一份且互相覆盖 | 生产环境把配置存储切到 Redis（Jedis 或 RedisTemplate），并设置统一的 key 前缀 |
| 老项目升级后编译不过 | 当前主线要求 JDK 8 及以上 | 升级 JDK；确实只能停在 JDK 7 的项目用很早的旧版本，新接口用不了 |
| 移动端 App 里做微信登录 / 分享，用这个库搞不定 | 客户端能力不在服务端 SDK 范围内 | 客户端集成微信官方移动端 SDK；服务端只用本库处理 OAuth 授权码与支付 |
| 支付 V3 启动即报证书相关错误 | 证书路径写错，或用了 `classpath:` 前缀但证书没打进包 | 确认 `privateKeyPath` / `privateCertPath` 指向真实存在的文件，容器镜像里也要带上证书；或改用绝对路径挂载 |
| 把自动构建版本当成正式版发到生产 | 版本号形态不同：正式版 `X.X.0`，测试版形如 `3.6.8.B`，每次提交还有 `x.x.x-时间戳` 的自动构建 | 生产只锁定正式版或自己验证过的版本，别用带时间戳的快照 |
| 自己写业务代码时 IDE 报找不到 getter/setter | 源码依赖 lombok 生成方法 | 使用发布 jar 不受影响；读源码或本地构建时先装 lombok 插件 |
| 某些接口调用报错但看不出原因 | 微信官方接口调整后，SDK 可能尚未同步 | 先在仓库的 Issues 里搜同类问题，再看该模块最新版本是否已适配；不要自行魔改签名逻辑 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 调用微信公众平台 / 支付 / 企业微信等官方接口；可选走自定义代理域名 |
| 读取文件 | 是 | 读取支付证书与私钥文件（`apiclient_key.pem` / `apiclient_cert.pem`）；源码构建时读取工程文件 |
| 写入文件 | 是 | Maven/Gradle 写入本地仓库与构建产物；如需下载素材、生成二维码等会落盘 |
| 凭证 | 是 | 需要 AppID / Secret / Token / EncodingAESKey、商户号与 API 密钥、V3 密钥与证书序列号。这些都由项目自行管理，本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 否 | 它是被引入的类库，不常驻、不自己起进程；被动消息场景下由你的 Web 应用承载 |

## 触发场景

- 「用 Java 接微信公众号，有现成的 SDK 吗」
- 「小程序登录要服务端换 openid，怎么写」
- 「微信支付 V3 的签名和证书太麻烦，有没有封装」
- 「多个公众号的 access_token 怎么统一管到 Redis」
- 「公众号被动消息怎么按关键词分发」
- 「Spring Boot 引哪个 starter、配置怎么写」

## 能力边界

**覆盖**：

- 公众号（MP）：令牌与各类票据管理、用户与标签、素材、自定义菜单、模板消息、网页授权、二维码、被动消息与事件的接收与回复。
- 小程序（MiniApp）：登录换取会话、订阅消息、内容安全、客服消息、码与链接生成等。
- 微信支付（Pay）：V2 与 V3 接口、统一下单与查询、退款、账单、回调验签，服务商与子商户模式。
- 企业微信（CP）：应用管理、通讯录、消息推送、第三方服务商模式。
- 开放平台（Open）：第三方平台代公众号/小程序开发与授权管理。
- 视频号 / 微信小店（Channel）与相关 Store 模块。
- 工程化配套：BOM 统一版本、Spring Boot Starter 自动装配、单账号与多账号两套形态、令牌可换 Redis 存储、HTTP 客户端可换实现（HttpComponents 5.x / HttpClient 4.x / OkHttp / JoddHttp）、可配置代理与自定义域名。

**不覆盖**：

- 不提供 Web 界面、管理后台或数据库表结构，只有 SDK。
- 不做客户端（iOS / Android / 小程序前端）能力：微信登录、分享、拉起支付的客户端部分必须用官方对应 SDK。
- 不替使用者处理微信平台的资质、类目、接口权限申请与频率限制。
- 不保证覆盖微信官方全部接口，也不保证新接口第一时间跟进；缺失接口需要自行调用或按贡献流程补充。
- 不提供托管服务与技术支持，使用问题走向上游仓库的 Issues / Wiki。
- 非 JVM 技术栈不在适用范围内。

## 依赖条件

- JDK 8 及以上（当前主线；JDK 7 只能用很早的旧版本）。
- Maven 或 Gradle 构建工具，能访问 Maven Central。
- 使用 Spring Boot Starter 时需要一个 Spring Boot 工程；starter 自身的自动配置依赖按上游 pom 管理，遇到自动装配不生效先核对依赖版本是否被覆盖。
- 可选：Redis（Jedis 或 Spring Data Redis 的 RedisTemplate）用于集中存放令牌；使用 Jedis / RedisTemplate 类型存储时需引入对应依赖。
- 可选：lombok（仅在阅读或从源码构建时需要）。
- 支付相关：商户号、API 密钥 / V3 密钥、API 证书与私钥文件。
- 其他模块按平台要求提供 AppID / Secret / Token / EncodingAESKey、企业微信 CorpID 与 Secret 等。

## 已知限制

- 只是 SDK：所有 HTTP 入口、回调地址、鉴权与业务逻辑都要自己写。
- 令牌默认存在内存里，单机使用没问题，多实例必须换成集中存储。
- 被动消息的默认去重是进程内实现，多实例部署需要自行替换。
- 消息路由器内部有固定线程池，长时间运行的服务需要关注退出时的清理。
- 源码依赖 lombok，参与开发或本地构建需要处理环境。
- 版本号存在多种形态（正式版 / 测试版 / 自动构建），选版本时容易看错。
- 微信官方接口会调整，SDK 适配存在滞后；文档主要在仓库 Wiki，个别页可能未及时更新。
- 具体可用版本、发布日期与 star 数请以仓库与中央仓库的实时信息为准，这里不做断言。

## 自检清单

- [ ] 已按业务线选对模块与 artifactId，没有把多账号场景配成单账号 starter。
- [ ] 依赖版本来自中央仓库真实存在的版本，且不是带时间戳的自动构建版。
- [ ] JDK 版本满足要求（8 及以上）。
- [ ] 令牌存储已从默认内存切到 Redis（多实例或频繁重启的部署必做），且类型名填写正确。
- [ ] HTTP 客户端类型按需要选好（推荐 HttpComponents 5.x），有代理时已配对应项。
- [ ] 被动消息路由的规则已按从细到粗排列，每条都以 `end()` 或 `next()` 收尾。
- [ ] 多实例部署时已自定义消息去重实现。
- [ ] 服务退出路径里会调用路由器的线程池关闭方法。
- [ ] 支付证书文件路径有效且已随部署产物一起发布；密钥与证书不进代码仓库。
- [ ] 多账号场景用的是 `switchoverTo` / `route(appid, msg)`，没有自己维护一堆全局配置。
- [ ] AppID、密钥、证书序列号等敏感信息通过配置或环境变量注入，不硬编码。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/binarywang/WxJava | 上游仓库（安装与完整文档以它为准） |
| https://github.com/binarywang/WxJava/tree/develop/spring-boot-starters | 各模块 Spring Boot Starter 的配置说明（本文配置项来源） |
| https://github.com/binarywang/WxJava/blob/develop/demo.md | 官方汇总的各业务线示例工程索引 |
| https://github.com/binarywang/WxJava/wiki | 开发文档与常见问题 |

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
