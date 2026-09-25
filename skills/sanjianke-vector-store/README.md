# 三剪客 · 轻量向量库 Skill

像用 SQLite 一样用一个向量库：向量库存本地，向量化交给 `api.a7w.cn` 的兼容网关，一个 base_url、一把 Key，本地零显卡。

这个 Skill 解决的是**「按意思搜」的起步成本**：给一批文本做语义检索，
不需要先起一套分布式基础设施，也不需要在自己机器上跑 embedding 模型、下载模型权重。
本地只留向量与元数据，离线也能检索；什么时候该换更大的库，这份文档里也写了。

---

## 前置条件

- **一个 `api.a7w.cn` 账号**，并已创建 API Key（新用户有赠送点数，可以先免费试跑几条）。
- **Python 3.8+**（`scripts/a7w.py` 只用标准库，无需安装任何第三方包）。
- 网络出口能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名）。
- 一份**已转成纯文本**的语料（PDF / Word 的解析是上游工序）。
- 想完全离线时：先联网把向量算好落盘，或改用纯本地的关键词检索。

---

## 使用

```bash
# 1. 配上你自己的 Key（只做一次，也可以直接用环境变量）
export A7W_API_KEY=sk-你的key        # Windows: $env:A7W_API_KEY="sk-你的key"

# 2. 先定 embedding 模型与维度——模型名不要猜
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"

# 3. 看平台上有哪些应用与接口
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema file_qa

# 4. 免自建的文档问答（免费）：把公网文档地址丢进去直接问
python3 scripts/a7w.py call file_qa chat --json '{"...":"..."}'
```

向量化 —— 一个 base_url，一把 Key：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/embeddings" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"<上一步挑的 embedding 模型名>",
       "input":["退款需在收货后 7 天内发起","生鲜类不支持无理由退款"]}'
```

写入、检索、元数据过滤都在本地完成，完整可运行实现见 `references/本地向量库.md`。

### 按需求找文档

| 你要什么 | 看哪份 |
|---|---|
| 纯 Python 的向量库实现、相似度与过滤、离线做法 | `references/本地向量库.md` |
| 用 OpenAI 协议调模型与 embedding、模型发现、返回结构 | `references/api-openai-compat.md` |
| 注册、充值、创建 Key、配额 | `references/getting-started.md` |
| 权限、异步机制、错误码、计费口径 | `references/通用说明.md` |

---

## 依赖

- **Python 3.8+**，仅标准库（`urllib` / `json` / `argparse`）。不需要 `requests`，不需要任何第三方包。
- `references/本地向量库.md` 里的向量库实现只用 `json` / `math` / `urllib`，复制即可运行。
- 无后台常驻、无守护进程；每次执行完即退出。

---

## 安全

- **不内嵌任何密钥**：Key 只从 `~/.a7w/config.json` 或环境变量 `A7W_API_KEY` 读取。
- **只连一个域名**：所有请求只发往 `api.a7w.cn`，不发往任何其他地址。
- **数据留在本地**：向量与元数据落在你指定的文件里，不经过平台。
- **不写入业务数据**：仅在显式传 `--out` 时写文件。
- **不提供 API Key、不代付费用**：Key 与点数必须是你自己的账号。
- 入库内容与生成内容的合规责任由使用者承担。

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
