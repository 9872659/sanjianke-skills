# 三剪客 · 多平台 IM 智能回复机器人 Skill

wechat-bot：多平台 IM 智能回复机器人 的安装、常用命令与避坑要点

---

## 前置条件

本 Skill 为工具类技能包，按 SKILL.md 的「安装」一节准备运行环境即可。

## 使用

正文的「安装」与「常用操作」两节是最短可用路径。

```bash
BOT_NAME='@你的微信昵称'
ALIAS_WHITELIST='允许私聊的好友别名1,好友昵称2'
ROOM_WHITELIST='允许触发的群名1,群名2'
AUTO_REPLY_PREFIX=''
WECHAT_DATA_DIR='.data/wechat'
WECHAT_STORE_MESSAGES='true'
PI_BIN='pi'
PI_AGENT_ARGS='--print --no-session'
```

## 依赖

- **Node.js ≥ v18.0**（建议 LTS）。
- 一个可扫码登录的微信号（走微信通道时）；能登录网页版的账号才可用，且需接受账号风险。
- 所选模型服务对应的 Key / token 与网络可达性；用 Ollama 时需本机跑着 Ollama 服务。
- 飞书通道：需要在开发者后台开启 `im.message.receive_v1` 事件并配置 IM 权限范围。
- Telegram 通道：需要 `TELEGRAM_BOT_TOKEN`。
- WhatsApp 通道：需要访问令牌、`phone_number_id`、验证 token，以及**公网可达的 HTTPS 地址**用于 webhook。
- Docker 方式需要本机 Docker；`wb wx ...` 依赖外部 OpenCLI `wx-cli` 能力读取本机微信缓存。

## 安全

- 不内嵌任何密钥
- 不主动把任何内容发往外部地址
- 若正文涉及联网或读写文件，权限范围已在 SKILL.md 的「权限与用途说明」中逐项列明
- 能力边界见 SKILL.md 的「能力边界」一节

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`wechat-bot`
- 仓库：https://github.com/wangrongding/wechat-bot

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
