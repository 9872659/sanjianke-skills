# 三剪客 · Agent 长期记忆层 Skill

把对话里的偏好、决定、事实抽成可检索的长期记忆，下次会话按用户 / 会话 / Agent 维度搜回来——Mem0 的安装、四种形态选型、核心调用与避坑要点。

---

## 前置条件

- Python **3.10 及以上**（上游要求）；Node 版本另算一套包。
- 一个可用的 LLM：默认 OpenAI，需要 `OPENAI_API_KEY`。不想用 OpenAI 就换成 Anthropic / Ollama / 本地模型。
- 一个可用的 embedding 模型与向量库：默认 OpenAI `text-embedding-3-small` + 磁盘版 Qdrant。
- 自托管形态需要 Docker 与 `docker compose`；云平台形态需要注册账号拿 API Key。
- 想要混合检索（BM25 + 实体）时，额外装 `mem0ai[nlp]` 并下载 spaCy 英文模型。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径（本地库）：

```bash
pip install mem0ai
export OPENAI_API_KEY="your-api-key"
```

```python
from mem0 import Memory

m = Memory()
m.add([{"role": "user", "content": "I love basketball and gaming."}], user_id="alex")
print(m.search("What do you know about me?", filters={"user_id": "alex"}))
```

自托管最短路径：

```bash
cd server && make bootstrap
```

CLI 最短路径：

```bash
pip install mem0-cli      # 或 npm install -g @mem0/cli
mem0 init
mem0 add "Prefers dark mode" --user-id alice
mem0 search "What does Alice prefer?" --user-id alice
```

API 细节、配置项与集成方式以 https://docs.mem0.ai 的当前内容为准。

---

## 依赖

- `mem0ai`（Python）/ `mem0ai`（npm）/ `mem0-cli` 或 `@mem0/cli`（命令行）
- 可选的 `mem0ai[nlp]` + `en_core_web_sm`（混合检索）
- 一个 LLM 与一个 embedding 服务（默认 OpenAI）
- 一个向量库（默认磁盘 Qdrant）；生产建议 pgvector / Qdrant 服务端 / Milvus 等
- 自托管额外需要 Docker、`docker compose`、`make`

---

## 安全

- 不内嵌任何密钥
- 模型侧密钥（如 `OPENAI_API_KEY`）与 Mem0 API Key 一律走环境变量或密钥管理，不要写进代码和仓库
- 记忆里会沉淀用户偏好、工单内容这类个人信息；上线前确认对话内容发往哪个模型服务、是否符合数据合规要求
- 多租户场景必须严格隔离作用域 ID，任何由外部传入的 `user_id` / `agent_id` 都要做校验，避免越权检索到别人的记忆
- 自托管的 `AUTH_DISABLED=true` 只允许本地开发使用，不要带到线上
- 记忆是加法式累积的，删除与清理要有明确策略，避免过期与敏感信息长期留存

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Mem0`
- 仓库：https://github.com/mem0ai/mem0

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
