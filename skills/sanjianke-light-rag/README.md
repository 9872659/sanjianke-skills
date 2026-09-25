# 三剪客 · 轻量图谱知识库 Skill

在向量检索之外再建一层知识图谱：用 `api.a7w.cn` 的兼容网关从文档里抽实体与关系，检索时既看具体实体也看全局关系链。

这个 Skill 解决的是**「向量检索答不了关系型问题」**：文档被切成块、算成向量之后，
「这几个业务板块之间是什么关系」这类问题没有答案 —— 因为关系从来不在任何一个块里。
做法是**双层级**：一边保留向量检索，一边用大模型把文档抽成实体—关系图，
查询时既能在图上找具体实体，也能顺着关系链看全局。

抽图与回答都走网关，**本地只留图谱与索引，零显卡、不部署模型**。

---

## 前置条件

- **一个 `api.a7w.cn` 账号**，并已创建 API Key（新用户有赠送点数，可以先免费试跑几条）。
- **Python 3.8+**（`scripts/a7w.py` 只用标准库，无需安装任何第三方包）。
- 网络出口能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名）。
- **垂直领域长文档**：法律条文、金融研报、学术论文、操作规范、访谈记录最合适。

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

抽实体与关系（图谱层唯一的模型调用，**先用 10 个块试**）：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash",
       "messages":[{"role":"system","content":"你是信息抽取器。只输出 JSON，不要解释、不要代码块围栏。格式：{\"entities\":[{\"name\":\"\",\"type\":\"\"}],\"relations\":[{\"source\":\"\",\"target\":\"\",\"relation\":\"\"}]}"},
                   {"role":"user","content":"文本：<你的一个文本块，300~500 字>"}],
       "temperature":0,"max_tokens":1200}'
```

把每个块的结果合并成一张图（实体去重、边累加权重），**存成 JSON 就是你的图谱**。

### 按需求找文档

| 你要什么 | 看哪份 |
|---|---|
| 抽图提示词、图合并、邻域召回、多跳关系链、增量更新 | `references/图谱检索.md` |
| 用 OpenAI 协议调模型、模型发现、流式、返回结构 | `references/api-openai-compat.md` |
| 注册、充值、创建 Key、配额 | `references/getting-started.md` |
| 权限、异步机制、错误码、计费口径 | `references/通用说明.md` |

---

## 依赖

- **Python 3.8+**，仅标准库（`urllib` / `json` / `argparse`）。不需要 `requests`，不需要任何第三方包。
- 图存成 JSON，遍历与邻域召回用纯标准库即可完成，见 `references/图谱检索.md`。
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
