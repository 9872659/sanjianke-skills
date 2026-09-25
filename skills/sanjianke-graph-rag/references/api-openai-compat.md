# 接入：OpenAI 兼容模型网关

## 1. 端点与鉴权

```
Base URL    : https://api.a7w.cn/api/v1
对话        : POST https://api.a7w.cn/api/v1/chat/completions
向量化      : POST https://api.a7w.cn/api/v1/embeddings
模型清单    : GET  https://api.a7w.cn/api/v1/models
应用清单    : GET  https://api.a7w.cn/api/v1/apps
应用接口    : POST https://api.a7w.cn/api/v1/apps/<应用代号>/<接口代号>
Header      : Authorization: Bearer <你的 API Key>
              Content-Type: application/json
```

**与 OpenAI 官方接口的差别只有 base_url 和 model 名。** 换模型不需要换 Key、
不需要重新签名、不需要重新对账 —— 同一把 Key、同一份账单。

## 2. 模型发现（**先查再猜**）

模型上下架很频繁，**模型名不要猜，也不要抄别人的**：

```bash
curl -sS "https://api.a7w.cn/api/v1/models" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

返回里每条记录的字段是 `model_code` / `model_name` / `vendor_name` /
`supports_vision` / `supports_reasoning` / `call_type_desc`。

- **调用时填 `model_code`。**
- 想找 embedding 模型：在清单里按关键词筛，**挑到之后记下它的输出维度**，这个维度决定你的向量库怎么建。
- **以 `model_code` 为准**，不要用厂商字段做精确匹配。

## 3. 最小对话请求

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

## 4. 向量化请求

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/embeddings" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<从 /api/v1/models 挑的 embedding 模型名>",
    "input": ["第一段文本", "第二段文本"]
  }'
```

返回 `data[].embedding` 是向量数组，顺序与 `input` 一一对应。
`input` 既可以是字符串数组（批量），也可以是单个字符串。

**三条纪律**：

1. **索引与查询必须用同一个模型**。换模型要重新向量化全部文本。
2. **维度一旦定了就别改**。向量库的维度、集合的维度都是按它建的。
3. **算过的向量落盘复用**，不要每次重算 —— 那是在重复付费。

## 5. Python SDK 接入

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",
)

resp = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)

vec = client.embeddings.create(
    model="<你挑的 embedding 模型名>",
    input=["要向量化的文本"],
)
print(len(vec.data[0].embedding))     # 维度
```

流式：

```python
stream = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "写一段 200 字的产品介绍"}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="", flush=True)
```

## 6. 纯标准库（不想装任何第三方包时）

```python
import json, os, urllib.request

HOST = "https://api.a7w.cn"
KEY = os.environ["A7W_API_KEY"]

def post(path, body):
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + KEY,
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))

def chat(model, messages, **kw):
    body = {"model": model, "messages": messages}
    body.update(kw)
    res = post("/api/v1/chat/completions", body)
    return res["choices"][0]["message"]["content"]

def embed(model, texts):
    res = post("/api/v1/embeddings", {"model": model, "input": texts})
    return [d["embedding"] for d in res["data"]]
```

## 7. 常用参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `model` | string | **必填**。以 `GET /api/v1/models` 的结果为准 |
| `messages` | array | **必填**。`[{role, content}]`，role 取 `system` / `user` / `assistant` |
| `temperature` | number | 采样温度。抽取类任务给 `0`，问答给 `0.2~0.3`，创意类再往上 |
| `max_tokens` | integer | 最大生成 tokens，**同时是控成本的主要旋钮** |
| `stream` | boolean | 流式返回（SSE） |
| `top_p` | number | 核采样 |

## 8. 响应结构

非流式响应与 OpenAI 一致：

```json
{
  "id": "chatcmpl-xxx",
  "model": "deepseek-v4-flash",
  "choices": [
    {"index": 0,
     "message": {"role": "assistant", "content": "..."},
     "finish_reason": "stop"}
  ],
  "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46}
}
```

- **模型名会被规范化**：请求 `DeepSeek-V4-Flash`，响应里可能返回全小写。
  **别拿响应的 `model` 去做精确匹配。**
- 流式时增量文本在 `choices[0].delta.content`（**不是** `message.content`），
  以 `data: [DONE]` 结束。

## 9. 推理模型的坑（实测）

部分模型是**推理模型**：会先花 token 产出思维链，再给正文。

| `max_tokens` | 结果 |
|---|---|
| 很小（如 `8`） | `content` 为 **`null`**，`finish_reason: "length"`（token 全被思维链吃掉） |
| 给足（如 `200`） | 正常返回 `content`，`finish_reason: "stop"` |

所以：

- **`content` 可能是 `null`**，代码里必须容错，不要假定它是字符串。
- 看到 `finish_reason: "length"` 且正文为空，**先把 `max_tokens` 调大**，不是接口坏了。
- 思维链字段名在不同线路上不一致 —— 实测出现过 `message.reasoning` 与
  `message.reasoning_content`，**两个都取一下**。

## 10. 与「应用任务」的边界

| | 模型网关 | 应用任务 |
|---|---|---|
| 路径 | `/api/v1/chat/completions`、`/api/v1/embeddings` | `/api/v1/apps/{应用代号}/{接口代号}` |
| 入参 | `messages` / `input` 数组 | 业务参数（文档地址、文本、时间戳…） |
| 返回 | `choices` / `data` 同步返回 | 多为 `task_id` 异步 |
| 典型用途 | 对话、抽取、分类、摘要、向量化 | 文档问答、语音、图像、视频、数字人 |

**别拿 `messages` 去调应用**，也别指望模型网关返回 `task_id`。
应用类接口的参数名**先查 `schema` 再写**：

```bash
python3 scripts/a7w.py schema <应用代号>
```

## 11. 计费与排错

- 对话与向量化都按**点数 / 百万 tokens** 计，输入输出分别计价。
- **控成本先压 `max_tokens`**，再减少一次请求里塞进去的文本量。
- 预算一律按**实收价**算，最终以返回里的 `usage` 与实际扣费为准。
- 报 402 先分清是账号没钱（`insufficient_points`）还是 Key 额度满（`key_quota_exceeded`）。
- 报 403 `permission_denied` 说明这个 Key 没有该模型的权限，**跟余额无关**。
- 报 404 先跑一次 `GET /api/v1/models`，**核对模型名拼写**。
