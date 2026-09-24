# 三剪客 · 微信接入 ChatGPT 自动回复 Skill

让微信在收到消息时自动调用大模型作答：扫码登录、按规则触发、可选 Docker 部署

---

## 前置条件

- **一个能登录网页版微信的微信号**。请先用该账号直接访问网页版微信确认能进；不能进网页版的账号，本方案用不了。
- **一个大模型 API Key**（例如 OpenAI 兼容接口的 Key），且账号有余量、本机网络能访问该服务；云端服务通常需要代理。
- **Node.js 18.0.0 或更高**（源码方式）；或本机已装 **Docker / docker compose**（容器方式）。
- 一台**常驻在线的机器**：进程停了就不收消息，微信掉线后需要人工重新扫码。
- 一份 `.env` 配置（从仓库的 `.env.example` 复制），至少要填 `OPENAI_API_KEY`。
- **风险确认**：本项目走第三方网页协议登录，微信侧可能给出警告或限制登录。请只在你明确接受该风险的账号与场景上使用。

---

## 使用

1. **先决定跑法**：
   - 想省事 → Docker：`docker pull holegots/wechat-chatgpt`，然后用 `docker run -d` 带 `-e OPENAI_API_KEY=... -e MODEL="gpt-3.5-turbo"` 起容器，并把记忆文件挂出来 `-v $(pwd)/data:/app/data/wechat-assistant.memory-card.json`。
   - 想让配置落在文件里 → `cp .env.example .env` 编辑后 `docker-compose up -d`。
   - 想改代码 → `git clone` 后 `npm install`，编辑 `.env`，`npm run dev`。
   - 想放到 PaaS → 用 `flyctl launch` 建应用、`flyctl secrets set` 注入 Key、`flyctl deploy` 部署（官方提示内存至少 512MB）。
2. **看二维码并扫码**：Docker/compose 用 `docker logs -f wechat-chatgpt`，源码方式二维码直接打在终端。扫码后账号上线。
3. **按需收紧触发面**：不想让它进群就把 `DISABLE_GROUP_MESSAGE=true`；只想私聊按关键词触发就设 `CHAT_PRIVATE_TRIGGER_KEYWORD`；要过滤敏感内容就用 `BLOCK_WORDS` 和 `CHATGPT_BLOCK_WORDS`（多个词英文逗号分隔）。
4. **在微信聊天框里下指令**：发 `/cmd help` 看帮助，`/cmd prompt <PROMPT>` 改人格，`/cmd clear` 清空会话。
5. **确认生效**：用一个允许的联系人发一条消息，观察是否按规则回复；再在不该触发的群里发一条，确认它保持沉默。

最短路径：`docker run`（带 Key 与记忆卷）→ `docker logs -f` 扫码 → 私聊测试 → 调 `.env` 收紧触发规则。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| Node.js | 源码方式要求 **18.0.0 及以上** |
| Docker / docker compose | 容器方式需要；镜像由上游发布 |
| Wechaty | 消息通道底层，登录能力受微信侧策略影响 |
| 大模型接口 | 需要 API Key；`API` 变量可指向自建或兼容端点 |
| 会话记忆文件 | `wechat-assistant.memory-card.json`，建议用卷挂载持久化 |
| PaaS 账号（可选） | Fly.io / Railway 这类平台，用于托管运行 |

---

## 安全

- 不内嵌任何密钥：`OPENAI_API_KEY` 等凭证一律由使用者自己在 `.env` 或容器环境变量中提供。
- **`.env` 不要提交进版本库**，也注意 `.gitignore` 是否已覆盖它。
- **账号风险需自行评估**：本项目基于第三方网页协议登录微信，可能触发警告、限流或限制登录。不要用重要账号，不要用于群发、批量加好友等高风险行为。
- 会话记忆文件里会留存聊天内容，属于敏感数据，请限制该目录的访问权限。
- 机器人以你的身份自动对外发言，建议先用 `DISABLE_GROUP_MESSAGE=true` 与触发关键词把发言范围压到最小，确认行为符合预期后再逐步放宽。
- `BLOCK_WORDS` / `CHATGPT_BLOCK_WORDS` 只能做粗粒度词面过滤，不能替代内容审核；对外场景请自行加审核环节。
- 本项目已归档且不再更新，安全性与协议兼容性不会有人跟进，请勿用于对稳定性有要求的生产环境。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`wechat-chatgpt`
- 仓库：https://github.com/fuergaosi233/wechat-chatgpt

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
