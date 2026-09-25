# Agent 长期记忆库 · 跨会话记忆层接入

把「值得记住的事实」抽成结构化条目存好，下一轮用一句自然语言搜回来拼进提示词。
模型与向量侧统一走 OpenAI 兼容网关，**改一个 `base_url` 就接完**。

---

## 这个包解决什么

大模型没有内置记忆，上下文一关就忘。要做跨会话的助手（客服、个人助理、教学陪练），
就得自己攒一层记忆库：写入时把对话抽成事实，读取时按用户召回相关条目。

本包讲的是**怎么把这一层的模型与向量入口指向 `api.a7w.cn`**，以及作用域、节流、
检索提准这些工程要点。**不涉及任何需要本地部署的模型权重。**

---

## 前置条件

- 一个 [api.a7w.cn](https://api.a7w.cn/) 账号，并已创建 API Key（新用户有赠送点数）。
- 能访问 `https://api.a7w.cn` 的网络出口（内网 / CI 需放行该域名）。
- **想跟着跑客户端脚本的话**：Python 3.8+，只用标准库，无需 `pip install`。
- 用记忆框架自带 SDK 时：按该框架自己的要求准备运行环境。

---

## 快速开始

### 1. 配置 Key

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 2. 把模型入口指向网关

```python
BASE_URL = "https://api.a7w.cn/api/v1"
API_KEY  = "sk-你的key"
```

| 角色 | 走哪个接口 |
|---|---|
| 抽取模型（对话 → 事实） | `POST /api/v1/chat/completions` |
| 回答模型（记忆 → 回复） | `POST /api/v1/chat/completions` |
| 向量模型（embedding） | 由框架 embedder 配置项指定，`base_url` 同样指向本网关 |

### 3. 验证一条调用

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

成功返回体是 `{"code":1,"msg":"success",...}` —— **成功码是 `1`，不是 `0`。**

### 4. 零依赖客户端

```bash
python3 scripts/a7w.py whoami      # 验证 Key
python3 scripts/a7w.py apps        # 列出全部能力
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py call chat completions \
  --body '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

---

## 使用建议

1. **先定作用域**：`user_id` / `agent_id` / `app_id` / `run_id` 四个维度按需取用，
   生成 ID 的逻辑收在一个函数里，写入与检索用同一套。
2. **写入节流**：只在偏好、决定、目标、新实体出现时写。每次写入都是一次模型调用。
3. **检索带过滤**：别全库搜；`top_k` 从 3 起步。
4. **召回后去重**：加法式存储会让同一事实沉淀多条。
5. **省钱**：抽取用小模型、回答用好模型，账单还是同一份。

细节见 `SKILL.md` 与 `references/记忆接入指南.md`。

---

## 依赖

- **Python 3.8+**（仅客户端脚本；只用 `urllib` 等标准库）。
- 一个可用的模型：由 `api.a7w.cn` 提供，**无需自备 GPU**。
- 一个可用的向量模型与向量存储：按你所用框架的配置项指定。
- 网络：能访问 `https://api.a7w.cn`。

---

## 安全

- **不内嵌任何密钥。** Key 由使用者提供，从环境变量 `A7W_API_KEY` 或
  `~/.a7w/config.json` 读取；脚本只把 Key 发往 `api.a7w.cn`。
- **Key 等同于余额**，不要写进代码、不要提交进 Git 仓库。
- 请求只发往 `api.a7w.cn`，不发送到其他任何地址。
- **数据合规**：把对话内容送去抽取之前，请自行确认符合你的隐私与合规要求。
- **版权与责任**：生成内容的使用与合规责任由使用者承担。

---

## 许可证

MIT，见 `LICENSE.md`。

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
