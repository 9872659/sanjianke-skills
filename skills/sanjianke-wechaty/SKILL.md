---
name: sanjianke-wechaty
slug: sanjianke-wechaty
displayName: 三剪客 · 微信聊天机器人框架
description: "Wechaty 是会话式 RPA SDK：写一份代码就能让机器人接管微信 / WhatsApp / 企业微信等聊天账号，收发消息、管理群与好友。这里讲清 Puppet 协议选择、安装与扫码登录、事件编程模型，以及 Web 协议登录受限等实战坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Wechaty 的安装（npm / Docker）、六行机器人、Puppet 协议切换、消息与群/好友事件处理、插件写法，以及 Web 协议登录不上、v0.x 与 v1.x 不兼容、文档新旧 API 混用等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 聊天机器人
  - IM 自动化
---

# 三剪客 · 微信聊天机器人框架

想让一个聊天账号自己回消息、自己拉群、自己处理好友申请，难点从来不是"写业务逻辑"，而是**怎么把消息接出来、怎么把消息发回去**。各家的聊天协议五花八门，自己啃一遍等于重写一遍轮子。

Wechaty 把这层封成一套统一接口：同一份业务代码，换个环境变量就能从微信 Web 协议切到 Pad 协议、切到企业微信或 WhatsApp。它自己不是协议实现，协议实现叫 **Puppet**（可插拔的协议适配模块），Wechaty 只负责把 Puppet 上报的事件翻译成人能读的对象——消息、联系人、群、好友申请。

**上游项目**：`Wechaty`　**仓库**：https://github.com/wechaty/wechaty

## 什么时候用 / 不用

**用它**：

- "让我的微信号自动回消息 / 自动通过好友申请 / 自动拉群。"——`message`、`friendship`、`room-invite` 等事件就是为这些场景准备的。
- "同一套机器人逻辑，我要能在微信、企业微信、WhatsApp 之间换协议。"——代码不动，只换 `WECHATY_PUPPET` 环境变量。
- "我要在群里做关键词监控与提醒，@ 到我就处理。"——`msg.mentionSelf()`、`msg.room()`、`Room.find()` 直接可用。
- "要把机器人做成可插拔的模块，别人能二次组装。"——Wechaty Plugin 就是一个接收 wechaty 实例的函数，天然适合拆包。
- "本地开发时不想连真协议，想跑单元测试。"——`wechaty-puppet-mock` 是官方提供的 Mock 协议。

**不要用它**：

- **你要接的是微信「公众号」客服消息**——那条路走公众号 API 与官方鉴权体系，不要拿个人号 RPA 方案硬套（Wechaty 另有 Official Account 的 Puppet，但业务形态完全不同，别混）。
- **你的主体是"给用户发通知"而不是"陪用户对话"**——短信、邮件、App 推送、企业微信应用消息这类有官方 API 的通道更稳、更快、更不容易掉线，没必要用 RPA 去模拟人操作。
- **账号注册于 2017 年之后却指望用 Web 协议登录**——官方 FAQ 明确说明这类账号无法通过 Web API 登录，Web 协议这条路直接堵死，只能换 Pad / Windows 等协议（通常要付费 Token）。
- **对稳定性要求是"金融级不能掉线"**——RPA 协议本质是模拟客户端行为，平台侧策略一变就可能失效，它不是官方开放接口，没有 SLA。
- **只是想「一次性导出聊天记录」**——那是一次性数据提取，写个脚本或用现成导出工具更直接，不需要常驻机器人框架。
- **不能接受账号风险**——拿主号跑第三方协议有被限制的可能，官方也把这类风险留给你自己判断。

## 安装

前置要求（以仓库 README 的 Requirements 一节为准）：Node.js 16+、NPM 7+、TypeScript 4.4+。注意包本身是 **ES Module**（`"type": "module"`），CommonJS 项目直接 `require` 会踩坑。

```bash
# 1. 用官方入门模板（推荐第一次使用，clone 完就能跑）
git clone https://github.com/wechaty/wechaty-getting-started.git
cd wechaty-getting-started
npm install

# 2. 在自己的项目里加依赖
npm init
npm install wechaty

# 3. 装一个具体协议的 Puppet（按需，例如 Web 协议）
npm install wechaty-puppet-wechat
```

Docker 方式（官方镜像同时支持 JavaScript 与 TypeScript，TypeScript 文件用 `ts-node` 直接跑，不用先编译）：

```bash
# 跑 JavaScript
docker run -ti --rm --volume="$(pwd)":/bot wechaty/wechaty bot.js

# 跑 TypeScript
docker run -ti --rm --volume="$(pwd)":/bot wechaty/wechaty bot.ts
```

官方建议把 npm / Docker 方式跑在境外 VPS 上，理由是 `npm install` 与 `docker pull` 更顺；如果你在国内，把镜像源与网络代理配好再装，能省很多时间。装完验证：

```bash
node -v      # 需 >= 16
npm -v       # 需 >= 7
```

## 常用操作

**1. 六行机器人（当前 v1.x 的正确写法）**

```javascript
import { WechatyBuilder } from 'wechaty'

const bot = WechatyBuilder.build()
bot
  .on('scan',    (qrcode, status) => console.log(`扫码登录：${status}`))
  .on('login',   user => console.log(`已登录：${user}`))
  .on('message', message => console.log(`收到：${message}`))
bot.start()
```

**2. 跑起来并扫码**

```bash
# 先设定用哪个协议，再启动
export WECHATY_PUPPET=wechaty-puppet-wechat
node bot.js
```

程序会在终端打印扫码链接（形如 `https://wechaty.js.org/qrcode/<二维码内容>`）；想让二维码直接画在终端里，装 `qrcode-terminal` 后调用 `qrcodeTerminal.generate(qrcode, { small: true })`，官方入门示例就是这么做的。

**3. 收到 ding 回 dong（事件处理的标准骨架）**

```javascript
import { WechatyBuilder, log } from 'wechaty'

const bot = WechatyBuilder.build({ name: 'ding-dong-bot' })

bot.on('scan',    (qrcode, status) => log.info('Bot', 'onScan: %s', status))
bot.on('login',   user    => log.info('Bot', '%s 已登录', user))
bot.on('logout',  user    => log.info('Bot', '%s 已登出', user))
bot.on('message', async message => {
  if (message.text() === 'ding') {
    await message.say('dong')
  }
})

bot.start()
```

**4. 只处理群里 @ 我的消息，并区分是不是自己发的**

```javascript
bot.on('message', async message => {
  if (message.self()) return                     // 过滤机器人自己发的，防止自问自答死循环
  const room = message.room()
  if (!room) return                              // 不是群消息
  if (!(await message.mentionSelf())) return     // 没 @ 我
  await room.say(`收到，来自 ${message.from()}`)
})
```

**5. 按名字找群 / 找人，并做群管理**

```javascript
import { Room, Contact } from 'wechaty'

const room = await Room.find({ topic: '项目群' })   // 找不到返回 null
if (room) {
  await room.say('机器人已上线')
  const members = await room.memberAll()
  console.log(`群里有 ${members.length} 人，群主是 ${room.owner()}`)
  await room.add(await Contact.find({ name: '张三' }))
}
```

**6. 处理好友申请**

```javascript
bot.on('friendship', async friendship => {
  console.log(`收到好友申请：${friendship.hello()}`)
  if (friendship.type() === Friendship.Type.Receive) {
    await friendship.accept()
  }
})
```

**7. 切换协议：换环境变量，代码不动**

```bash
# Web 协议，不需要 Token
export WECHATY_PUPPET=wechaty-puppet-wechat

# Pad 协议（需要向服务商申请 Token），Token 放在专属环境变量里
export WECHATY_PUPPET=wechaty-puppet-padlocal
export WECHATY_PUPPET_PADLOCAL_TOKEN='你的-token'

# 连远程 Puppet 服务（gRPC），同样走 Token
export WECHATY_PUPPET=wechaty-puppet-service
```

也可以在代码里硬编码，等效：

```javascript
const bot = WechatyBuilder.build({
  puppet: 'wechaty-puppet-service',
  puppetOptions: { token: '你的-token' },
})
```

**8. 写一个可复用的 Plugin**

```javascript
// my-plugin.js
export const MyPlugin = (wechaty) => {
  wechaty.on('message', async (message) => {
    /* 在这里挂你的逻辑 */
  })
}
```

Plugin 就是一个「接收 wechaty 实例、返回空」的函数，用户 `use` 上去即可，配置项通过闭包或额外参数传。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 扫码后一直登录不上，或提示 Web 协议不可用 | 官方 FAQ 明确：2017 年之后注册的微信账号**无法通过 Web API 登录** | 换非 Web 协议（Pad / Windows 等），这些通常需要申请 Token；别在 Web 协议上反复试 |
| 装完 `wechaty@1.x` 后各种 `wechaty-puppet-*` 报类型错、运行时报模块不匹配 | 官方 breaking changes 写明 **v1.x 与 v0.x 模块互不兼容**：`wechaty@1.x` 必须配 `wechaty-*@1.x`，v0.x 同理 | 把所有 `wechaty` 与 `wechaty-puppet-*` 的版本对齐到同一个大版本，别一个升级一个不升 |
| 照着旧教程写 `Wechaty.instance()`，运行报没有这个方法 | 官方文档站里不少页面仍是旧 API 写法，当前版本用的是 `WechatyBuilder.build()` | 以 README 与 API 参考里的 `WechatyBuilder` 写法为准；旧文档页面只能当概念参考 |
| `require('wechaty')` 报 `ERR_REQUIRE_ESM` | 该包是 ES Module（`"type": "module"`） | 改成 `import`，或把项目设成 `"type": "module"`；用 `ts-node` 跑 TypeScript 时注意 loader 配置，官方示例用的是 `--loader ts-node/esm` |
| 机器人把自己刚发出去的消息又处理一遍，陷入自问自答 | 事件回调里没过滤机器人自身的消息 | 在回调开头判断 `message.self()` 后直接 return |
| 群里机器人像是不响应 @ | 被 @ 的判断方式和普通文本不同，且部分协议对 @ 的解析有差异 | 用 `await message.mentionSelf()` 判断，不要自己用文本包含 `@名字` 硬匹配；同时确认该协议支持群内 @ 解析 |
| Windows 下 `npm install` 编译失败 | 原生模块需要构建工具链 | 官方入门文档的排查建议是安装 `windows-build-tools` 后再重装依赖 |
| Docker 里跑的机器人无法持久化登录状态 | 容器 `--rm` 退出即删，登录态与缓存目录没挂出来 | 用 `--volume` 把机器人数据目录一起挂到宿主机，别只挂代码目录 |
| Puppet 服务连不上，日志里全是 TLS / 连接错误 | 官方 breaking changes 记录过 Puppet Service 客户端启用 TLS、服务发现字段由 `ip` 改为 `host` 等变更 | 把 `wechaty-puppet-service` 与 `wechaty` 一起升到最新同版本；老 Token 或老文档里的地址格式可能已失效 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 机器人需要长连聊天协议服务端；npm 安装与 Docker 拉镜像也要联网。境外 VPS 体验更好 |
| 读取文件 | 是 | 读取你的机器人源码、`.env`（官方示例用 `dotenv`）、登录态缓存；发送图片/文件时读取待发送的媒体文件 |
| 写入文件 | 是 | 写入登录态与本地缓存（`WechatyBuilder.build({ name })` 的 name 决定缓存目录）；保存收到的媒体文件时也要写盘 |
| 凭证 | 是 | Web 协议只需扫码，无需 Token；Pad / Windows / Service 协议需要服务商 Token（如 `WECHATY_PUPPET_PADLOCAL_TOKEN`）。Token 等同于账号控制权，必须放环境变量，绝不写进源码或提交到仓库 |
| 子进程 / 后台常驻 | 是 | 机器人是常驻进程，通常用 systemd / pm2 / Docker 守护；底层协议模块（如基于浏览器的实现）会拉起子进程 |
| 账号操作 | 是 | 机器人会以你的账号身份发消息、加好友、拉群、改群公告。这是该工具的用途本身，也意味着这些动作都会真实发生在你的账号上 |

## 触发场景

- "帮我写个微信机器人，有人发 ding 就回 dong。"
- "这个机器人我想同时支持微信和 WhatsApp，代码不想改两遍。"
- "群里有人 @ 机器人就回复，别的消息不要理。"
- "自动通过好友申请，并把申请人拉进某个群。"
- "把机器人打包成公司内部能复用的插件。"
- "机器人扫码登录不上，帮我看看是协议问题还是账号问题。"

## 能力边界

**覆盖**：

- 统一事件模型：`scan` / `login` / `logout` / `message` / `friendship` / `room-join` / `room-topic` / `room-leave` / `room-invite`
- 核心对象操作：`Message` 的文本读取、回复、转发、取媒体；`Contact` 的查找、别名、头像；`Room` 的建群、拉人、踢人、改群名、发公告、查成员；`Friendship` 与 `RoomInvitation` 的接受
- 协议可插拔：换 `WECHATY_PUPPET` 即换协议，官方列出的协议方向包括微信 Web / Pad / Windows、WhatsApp Web、企业微信、Lark、Gitter、公众号、Mock 等
- 多语言客户端：除 TypeScript 外还有 Python / Go / Java / Scala / PHP / .NET 版本，接口语义一致
- 可扩展：Wechaty Plugin 机制，以及官方的插件合集仓库
- 部署形态：npm 与 Docker 两种，另外有配套的入门模板仓库、Docker 入门模板、线上 IDE（Gitpod / Cloud Shell）快速体验路径

**不覆盖**：

- 不提供聊天协议的官方授权，任何协议适配都是模拟客户端行为，平台策略变更即可能失效
- 不代办账号资质与风控问题，账号被限制的风险由使用者承担
- 不做消息的长期存储、检索、分析，没有内置数据库
- 不做可视化面板，没有开箱即用的管理后台
- 不做 AI 能力本身，接大模型要自己写进 `message` 事件里
- 不保证第三方 Puppet 的质量与可用性，官方只提供目录与兼容性说明

## 依赖条件

- Node.js 16+、NPM 7+；用 TypeScript 时 4.4+
- 该包发布为 ES Module，CommonJS 项目需改造
- Web 协议类 Puppet 无需 Token；Pad / Windows / Service 类协议需向服务商申请 Token，并放进对应环境变量
- 微信账号需能通过所选协议登录（2017 年后注册的账号走不通 Web 协议）
- Docker 部署需挂载代码目录与数据目录；`docker run` 官方示例是 `-ti --rm --volume="$(pwd)":/bot`
- 具体协议模块的支持范围与稳定性以官方 Puppet 目录页和各自仓库为准，官方把不同协议的成熟度标注为 Alpha / Beta 不等

## 已知限制

1. v1.x 与 v0.x 生态不兼容，混版会报错；文档站上不少页面停留在旧 API（如 `Wechaty.instance()`），照抄可能与当前版本对不上。
2. Web 协议对 2017 年后注册的账号不可用，这不是配置问题，是平台侧限制。
3. RPA 协议依赖模拟客户端，没有官方 SLA，长跑需要自己做掉线重连与监控。
4. 官方明确建议境外 VPS 部署 npm / Docker 方式，国内网络的安装与长连体验需要额外处理。
5. 不同 Puppet 覆盖的能力不同（例如群内 @ 解析、发送媒体、部分管理操作的支持程度不一致），换协议时要逐项回归验证。
6. 本 Skill 里的参数名与事件名以抓到的官方 README / 文档为准，具体版本差异请以本机 `node_modules` 里的类型定义与官方 API 参考页为准。

## 自检清单

执行前：

- [ ] `node -v` ≥ 16、`npm -v` ≥ 7，且项目模块体系与 ES Module 兼容
- [ ] `wechaty` 与全部 `wechaty-puppet-*` 版本大版本号一致
- [ ] 确认目标账号能否用所选协议登录（Web 协议对 2017 年后注册的账号不可用）
- [ ] 需要 Token 的协议，Token 已放环境变量，未硬编码、未提交
- [ ] 事件回调里已加 `message.self()` 过滤，避免自问自答
- [ ] Docker 部署已挂出数据目录，重启不丢登录态

执行后：

- [ ] 日志里能看到 `scan` → `login` 的完整链路，确认真的登上了
- [ ] 用一条测试消息验证收发，并确认机器人没有把这条消息当成新消息再处理一遍
- [ ] 群相关操作在测试群里先验证再加到生产群
- [ ] 机器人进程被 kill 后能否自动拉起，守护进程（systemd / pm2 / Docker restart policy）已配好
- [ ] 确认没有把含 Token 的日志或 `.env` 提交进仓库

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/wechaty/wechaty | 上游仓库（安装与完整文档以它为准） |
| https://wechaty.js.org/docs/ | 官方文档站：入门、Puppet 协议目录、API 参考、Breaking Changes |
| https://github.com/wechaty/wechaty-getting-started | 官方入门模板，含可直接运行的 ding-dong 示例 |

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
