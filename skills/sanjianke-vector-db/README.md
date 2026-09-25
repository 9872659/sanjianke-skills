# 三剪客 · 分布式向量数据库 Skill

把向量存起来并做规模化相似度检索：向量与标量一起存，支持元数据过滤、范围检索与稠密叠加全文的混合检索；embedding 走 `api.a7w.cn` 兼容网关，本地零显卡。

这个 Skill 解决的是**「同一套接口覆盖三种规模」**：本机一个文件就能试、一台机器起容器能干正经活、
向量到几十亿条再换成集群。模型侧不用自己操心 —— embedding 与生成都在 `api.a7w.cn`，
一个 base_url、一把 Key、75 个在架模型。

---

## 前置条件

- **一个 `api.a7w.cn` 账号**，并已创建 API Key（新用户有赠送点数，可以先免费试跑几条）。
- **Python 3.8+**（`scripts/a7w.py` 只用标准库，无需安装任何第三方包）。
- 网络出口能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名）。
- **先定 embedding 模型与维度**：集合的维度创建后无法修改。
- 按规模准备运行环境：本机文件形态零依赖；单机服务与集群形态需要相应的容器或编排环境。

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

# 4. 免自建的文档问答（免费）：先确认「答得上来」，再决定自建规模
python3 scripts/a7w.py call file_qa chat --json '{"...":"..."}'
```

向量化 —— 客户端里 `base_url` 就填这个，Key 用同一把：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/embeddings" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"<上一步挑的 embedding 模型名>",
       "input":["Who is Alan Turing?","What is AI?"]}'
```

检索到片段后的答案生成走同一个网关：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash",
       "messages":[{"role":"system","content":"只根据资料回答；资料里没有就说不知道。"},
                   {"role":"user","content":"资料：\n1) ……\n问题：……"}],
       "temperature":0.2,"max_tokens":800}'
```

### 按需求找文档

| 你要什么 | 看哪份 |
|---|---|
| 索引选型、混合检索、多租户、加载与健康检查、备份监控 | `references/规模化运维要点.md` |
| 用 OpenAI 协议调模型与 embedding、模型发现、返回结构 | `references/api-openai-compat.md` |
| 注册、充值、创建 Key、配额 | `references/getting-started.md` |
| 权限、异步机制、错误码、计费口径 | `references/通用说明.md` |

---

## 依赖

- **Python 3.8+**，仅标准库（`urllib` / `json` / `argparse`）。不需要 `requests`，不需要任何第三方包。
- 向量数据库本体按你选的规模自行准备运行环境（本机文件 / 单机容器 / 集群）。
- 无后台常驻、无守护进程；`a7w.py` 每次执行完即退出。

---

## 安全

- **不内嵌任何密钥**：Key 只从 `~/.a7w/config.json` 或环境变量 `A7W_API_KEY` 读取。
- **只连一个域名**：所有请求只发往 `api.a7w.cn`，不发往任何其他地址。
- **连接信息从配置读**：向量数据库的 URI 与 token 不要硬编码进代码。
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
