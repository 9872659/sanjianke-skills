# 三剪客 · 图谱增强检索 Skill

先把整批文档读成一张实体关系图，再切成多级社区并逐层写摘要，让「主题、趋势、概览」这类全局性问题有答案。

这个 Skill 解决的是**「没有一段话在讲主题」**的问题：向量检索只能回答「哪几段话和问题像」，
所以问「这本书的主要主题是什么」它给不出答案。做法是让模型把文档读成实体关系图，
再切成一层层社区、给每个社区写摘要 —— **摘要本身就是在讲主题**，全局问题终于有答案。
局部问题仍可顺着实体与关系追问。

抽图、写摘要、回答问题全部走 `api.a7w.cn` 的 OpenAI 兼容网关，本地零显卡。

---

## 前置条件

- **一个 `api.a7w.cn` 账号**，并已创建 API Key（新用户有赠送点数，可以先免费试跑几条）。
- **Python 3.8+**（`scripts/a7w.py` 只用标准库，无需安装任何第三方包）。
- 网络出口能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名）。
- **叙事类或档案类文本**：报告、卷宗、访谈记录、工单、会议纪要最合适。
- **成本意识**：索引阶段要反复调用模型，**先拿几页小样本跑通再全量**。

---

## 使用

```bash
# 1. 配上你自己的 Key（只做一次，也可以直接用环境变量）
export A7W_API_KEY=sk-你的key        # Windows: $env:A7W_API_KEY="sk-你的key"

# 2. 看平台上有哪些应用与接口——名字都别猜
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema file_qa

# 3. 免自建的文档问答（免费），用来给自建图谱做效果对照
python3 scripts/a7w.py call file_qa chat --json '{"...":"..."}'

# 4. 查模型清单（模型名以接口返回为准）
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

抽图（**先用 10 个块试**）：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash",
       "messages":[{"role":"system","content":"你是信息抽取器。只输出 JSON，不要解释、不要代码块围栏。格式：{\"entities\":[{\"name\":\"\",\"type\":\"\",\"description\":\"\"}],\"relations\":[{\"source\":\"\",\"target\":\"\",\"relation\":\"\",\"description\":\"\"}],\"claims\":[{\"subject\":\"\",\"statement\":\"\"}]}"},
                   {"role":"user","content":"文本：<你的一个文本块，300~500 字>"}],
       "temperature":0,"max_tokens":1500}'
```

社区摘要与全局问答的完整调度见 `references/社区摘要与全局问答.md`。

### 按需求找文档

| 你要什么 | 看哪份 |
|---|---|
| 抽图、社区划分、分层摘要、全局/局部问答、成本控制 | `references/社区摘要与全局问答.md` |
| 用 OpenAI 协议调模型、模型发现、流式、返回结构 | `references/api-openai-compat.md` |
| 注册、充值、创建 Key、配额 | `references/getting-started.md` |
| 权限、异步机制、错误码、计费口径 | `references/通用说明.md` |

---

## 依赖

- **Python 3.8+**，仅标准库（`urllib` / `json` / `argparse`）。不需要 `requests`，不需要任何第三方包。
- 图、社区与摘要都存成 JSON，社区划分与调度用纯标准库即可完成。
- 无后台常驻、无守护进程；每次执行完即退出。

---

## 安全

- **不内嵌任何密钥**：Key 只从 `~/.a7w/config.json` 或环境变量 `A7W_API_KEY` 读取。
- **只连一个域名**：所有请求只发往 `api.a7w.cn`，不发往任何其他地址。
- **不写入业务数据**：仅在显式传 `--out` 时写文件。
- **不提供 API Key、不代付费用**：Key 与点数必须是你自己的账号。
- 入库语料与生成内容的合规责任由使用者承担。

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文与脚本均为原创内容，不包含第三方项目的源代码。

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
