# 多智能体群聊协作 · 轮流发言与终止条件

一个 Agent 干不好的活，往往适合**拆给几个角色来回讨论**：写手出稿、评审挑刺、
写手改稿，直到评审说「通过」。模型入口统一走 OpenAI 兼容网关，
**改一个 `base_url` 就接完**，还能给每个角色单独指定模型。

---

## 这个包解决什么

这类框架把「多角色对话」当成一等公民：你定义几个带人设的 Agent，
配一个模型客户端，塞进一个「团队」里，它负责轮流发言、共享上下文、判断何时停下。

本包讲的是**怎么把 Agent 的模型客户端指向 `api.a7w.cn`**，以及发言策略、
终止条件、状态管理、工具轮数上限、成本估算这些工程要点。
**不涉及任何需要本地部署的模型权重。**

---

## 前置条件

- 一个 [api.a7w.cn](https://api.a7w.cn/) 账号，并已创建 API Key（新用户有赠送点数）。
- 能访问 `https://api.a7w.cn` 的网络出口（内网 / CI 需放行该域名）。
- **想跟着跑客户端脚本的话**：Python 3.8+，只用标准库，无需 `pip install`。
- 用多智能体框架自带 SDK 时：按该框架自己的要求准备运行环境。

---

## 快速开始

### 1. 配置 Key

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 2. 把模型客户端指向网关

```python
model_client = OpenAIChatCompletionClient(
    model="DeepSeek-V4-Flash",
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",
)
```

> 类名与参数名以你所用框架的当前版本为准。
> **值永远是同一个网关地址与同一把 Key。**

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
python3 scripts/a7w.py call chat completions \
  --body '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

---

## 使用建议

1. **双重终止条件**：关键词触发（如 `APPROVE`）+ 步数上限。两类都设。
2. **触发词写进角色设定**：评审角色不知道要输出什么词，终止条件永远不触发。
3. **工具调用设轮数上限**：不设的话 Agent 走完一轮就停，容易「以为做完了其实没做完」。
4. **按环节分档选模型**：出稿用快模型、评审用强模型，账单还是同一份。
5. **状态要显式管理**：不相关的任务先重置会话，相关的才续跑。
6. **从固定顺序起步**：动态点名每次多一次调用，流程稳定了再上。

细节见 `SKILL.md` 与 `references/群聊协作指南.md`。

---

## 依赖

- **Python 3.8+**（仅客户端脚本；只用 `urllib` 等标准库）。
- 一个可用的模型：由 `api.a7w.cn` 提供，**无需自备 GPU**。
- 网络：能访问 `https://api.a7w.cn`。

---

## 安全

- **不内嵌任何密钥。** Key 由使用者提供，从环境变量 `A7W_API_KEY` 或
  `~/.a7w/config.json` 读取；脚本只把 Key 发往 `api.a7w.cn`。
- **Key 等同于余额**，不要写进代码、不要提交进 Git 仓库。
- 请求只发往 `api.a7w.cn`，不发送到其他任何地址。
- **成本可控性**：多角色多轮会放大 token 消耗，**先设终止条件再跑长任务**。
- **合规**：生成内容的使用与合规责任由使用者承担。

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
