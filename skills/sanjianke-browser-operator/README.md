# 浏览器自动化操作员 · 一句话任务操控网页

一句话任务描述，让 Agent 自己开着浏览器把网页上的活干完：**点按钮、填表单、翻页、
把结果取回来**。写的是任务，不是选择器。模型入口统一走 OpenAI 兼容网关，
**改一个 `base_url` 就接完**。

---

## 这个包解决什么

适合那些**没有 API、只有网页界面**的场景：后台系统、比价、批量填表、数据抄录。

本包讲的是**怎么把这类浏览器自动化的模型入口指向 `api.a7w.cn`**，以及任务描述写法、
模型挑选、真实浏览器与无头环境差异、步数上限与成本估算这些工程要点。
**不涉及任何需要本地部署的模型权重。**

---

## 前置条件

- 一个 [api.a7w.cn](https://api.a7w.cn/) 账号，并已创建 API Key（新用户有赠送点数）。
- 能访问 `https://api.a7w.cn` 的网络出口（内网 / CI 需放行该域名）。
- **想跟着跑客户端脚本的话**：Python 3.8+，只用标准库，无需 `pip install`。
- 用浏览器自动化框架时：按该框架自己的版本要求准备运行环境（解释器版本、浏览器运行时等）。

---

## 快速开始

### 1. 配置 Key

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 2. 把模型对象指向网关

```python
llm = ChatOpenAI(
    model="Qwen3-VL-30B-A3B-Instruct",       # 浏览器任务建议上视觉模型
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

1. **任务描述写四要素**：目标 + 边界 + 输出格式 + 只读/可写。
2. **只读优先**：提交、支付、删除这类不可逆动作必须人工确认。
3. **必设步数上限**：没有它，任务失败时模型会一直试，账单一直涨。
4. **模型分档**：结构化页面用快模型，图形化界面用支持视觉的模型，长链路用强模型。
5. **页面内容只传目标区域**：整页 HTML 是 tokens 大头。
6. **合规前置**：只在自有账号或已获授权的页面上操作。

细节见 `SKILL.md` 与 `references/网页操作指南.md`。

---

## 依赖

- **Python 3.8+**（仅客户端脚本；只用 `urllib` 等标准库）。
- 一个可用的模型：由 `api.a7w.cn` 提供，**无需自备 GPU**。
- 网络：能访问 `https://api.a7w.cn` 与你要操作的目标站点。
- 用浏览器自动化框架时：按框架当前文档准备浏览器运行时。

---

## 安全

- **不内嵌任何密钥。** Key 由使用者提供，从环境变量 `A7W_API_KEY` 或
  `~/.a7w/config.json` 读取。
- **Key 等同于余额**，不要写进代码、不要提交进 Git 仓库。
- 请求只发往 `api.a7w.cn` 与你要操作的目标站点，不发送到其他任何地址。
- **写操作要人工确认**：提交、支付、删除一类不可逆动作不要交给 Agent 自动执行。
- **授权与合规**：只在自有账号或已获授权的页面上操作；
  目标站点的服务条款、robots 与数据合规由使用者自行确认。
- **成本可控性**：每一步都是一次模型调用，**先设步数上限再跑长任务**。

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
