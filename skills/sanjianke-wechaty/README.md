# 三剪客 · 微信聊天机器人框架 Skill

Wechaty 的安装（npm / Docker）、六行机器人、Puppet 协议切换、消息与群/好友事件处理、插件写法，以及 Web 协议登录不上、v0.x 与 v1.x 不兼容、文档新旧 API 混用等高频坑。

---

## 前置条件

- Node.js 16+、NPM 7+；用 TypeScript 时 4.4+（以仓库 README 的 Requirements 一节为准）
- 该包发布为 ES Module，CommonJS 老项目需先改造模块体系
- 一个可用来做机器人的聊天账号；注意 2017 年之后注册的微信账号**无法通过 Web 协议登录**
- 走 Web 协议无需 Token；走 Pad / Windows / Service 协议需要向服务商申请 Token
- 安装与长连都需要网络；官方建议使用境外 VPS 跑 npm / Docker 方式

---

## 使用

本 Skill 面向「让 Agent 会装、会用、知道什么时候不该用」，正文覆盖：

1. **什么时候用 / 不用**——包括不该用 Wechaty 的典型场景（如要接公众号客服、只做单向通知、对稳定性要求金融级、不能接受账号风险）
2. **安装**——官方入门模板、npm 装依赖、Docker 两种运行方式
3. **常用操作**——六行机器人、扫码登录、ding-dong 事件骨架、群内 @ 处理、群与好友管理、协议切换、Plugin 写法
4. **常见坑**——Web 协议登录限制、v0.x/v1.x 不兼容、旧文档 API 混用、ESM 报错、自问自答、Windows 构建工具、Docker 登录态丢失、Puppet Service 连接变更
5. **能力边界**——覆盖的事件与对象模型、协议可插拔范围；不覆盖的部分（不代办授权、不做存储检索、不做可视化面板、不内置 AI）

最直接的起点是官方入门模板：`git clone https://github.com/wechaty/wechaty-getting-started.git`，`npm install` 后按 README 设定 `WECHATY_PUPPET` 再启动。

---

## 依赖

- 运行时：Node.js 16+ / NPM 7+
- 主依赖：`wechaty`
- 协议依赖：按需安装具体 Puppet 模块（例如 `wechaty-puppet-wechat`、`wechaty-puppet-service`），其大版本号必须与 `wechaty` 保持一致
- 可选依赖：`qrcode-terminal`（在终端直接画二维码）、`dotenv`（官方示例用它加载 `.env`）
- 部署依赖：Docker 方式需 `wechaty/wechaty` 镜像，并挂载代码目录与数据目录

---

## 安全

- 不内嵌任何密钥；Puppet Token 一律通过环境变量传入（如 `WECHATY_PUPPET_PADLOCAL_TOKEN`）
- Token 等同于聊天账号的控制权，泄露等于把账号交出去；不要写进源码、不要提交进仓库、不要打进镜像
- 机器人以你的真实账号身份操作，发消息、加好友、拉群都会真实生效；上线前先在测试账号与测试群里验证
- 使用第三方协议适配属于模拟客户端行为，存在账号被平台限制的风险，请自行评估并遵守目标平台的服务条款
- 登录态缓存目录包含会话信息，同样不应提交到仓库或公开分享
- 处理他人消息内容时注意隐私与合规，不要用机器人抓取、留存、外发未获授权的聊天内容

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Wechaty`
- 仓库：https://github.com/wechaty/wechaty

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
