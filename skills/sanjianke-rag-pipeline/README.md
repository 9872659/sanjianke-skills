# 三剪客 · RAG 知识库流水线搭建 Skill

检索链路在本地跑，模型这一层全部走 `api.a7w.cn` 的 OpenAI 兼容网关：一个 base_url、一把 Key、75 个在架大模型，本地零显卡。

这个 Skill 解决的是**「我不想被框架替我做的决定绑住」**：文档怎么切、片段怎么召回、
上下文怎么拼、答案怎么控，每一环都显式可见、随时可换。模型侧只换一个 `model` 字符串，
检索侧先用纯 Python 标准库跑通，再按需要叠加语义检索。

---

## 前置条件

- **一个 `api.a7w.cn` 账号**，并已创建 API Key（新用户有赠送点数，可以先免费试跑几条）。
- **Python 3.8+**（`scripts/a7w.py` 只用标准库，无需安装任何第三方包）。
- 网络出口能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名）。
- 你的语料：PDF / Word / Markdown / 纯文本，**先转成纯文本再切分**最稳。

---

## 使用

```bash
# 1. 配上你自己的 Key（只做一次，也可以直接用环境变量）
export A7W_API_KEY=sk-你的key        # Windows: $env:A7W_API_KEY="sk-你的key"

# 2. 看平台上有哪些应用与接口——名字都别猜
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema file_qa

# 3. 免自建的文档问答（免费）：把公网文档地址丢进去直接问
python3 scripts/a7w.py call file_qa chat --json '{"...":"..."}'

# 4. 查模型清单（模型名以接口返回为准）
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

检索到的片段交给模型回答：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash",
       "messages":[{"role":"system","content":"只根据资料回答；资料里没有就说不知道。"},
                   {"role":"user","content":"资料：\n1) ……\n问题：……"}],
       "temperature":0.2,"max_tokens":512}'
```

用 OpenAI SDK 接进现有代码，只动两行：

```python
from openai import OpenAI
client = OpenAI(base_url="https://api.a7w.cn/api/v1", api_key="sk-你的key")
```

### 按需求找文档

| 你要什么 | 看哪份 |
|---|---|
| 切分、召回、拼 prompt 的完整写法与参数 | `references/流水线搭建.md` |
| 用 OpenAI 协议调模型、模型发现、流式、返回结构 | `references/api-openai-compat.md` |
| 注册、充值、创建 Key、配额 | `references/getting-started.md` |
| 权限、异步机制、错误码、计费口径 | `references/通用说明.md` |

---

## 依赖

- **Python 3.8+**，仅标准库（`urllib` / `json` / `argparse`）。不需要 `requests`，不需要任何第三方包。
- 无后台常驻、无守护进程；每次执行完即退出。
- 纯标准库的本地检索实现（切分 + BM25 打分 + 拼上下文）见 `references/流水线搭建.md`，复制即可运行。

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
