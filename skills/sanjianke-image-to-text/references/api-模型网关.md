# 模型网关 · OpenAI 兼容入口（读图用这条）

> `api.a7w.cn` 的模型网关 · 一把 Key 调 75 个在架大模型

---

## 一、基本信息

| 字段 | 内容 |
|---|---|
| Base URL | `https://api.a7w.cn/api/v1` |
| 聊天补全 | `POST /api/v1/chat/completions` |
| 模型清单 | `GET /api/v1/models` |
| 鉴权 | `Authorization: Bearer <你的 API Key>` |
| 协议 | **OpenAI 兼容**：换 `base_url` 与 `model` 即可，SDK 代码基本不用改 |

> **模型清单会变。** 站内宣传的数字与实测数量常不一致，
> **调用前先跑 `GET /api/v1/models` 拿当期的准确清单**，不要照抄文档里的名字。

---

## 二、图片转文字：把图交给视觉模型

`messages[].content` 用**数组**形式，同时放文字指令与图片地址：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-VL-30B-A3B-Instruct",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "按阅读顺序提取全部文字，保留换行，不要翻译、不要解释"},
        {"type": "image_url", "image_url": {"url": "https://你的存储/截图.png"}}
      ]
    }]
  }'
```

文本在 `choices[0].message.content`。

### 参数要点

| 参数 | 说明 |
|---|---|
| `model` | 模型编码，从 `GET /api/v1/models` 里取 |
| `messages[].content` | 数组；每项是 `{"type":"text"}` 或 `{"type":"image_url"}` |
| `temperature` | 抽取类任务建议调低（如 `0.1`），减少自由发挥 |
| `max_tokens` | **推理模型会把 token 先花在思维链上**；设太小会只返回 `null`，抽取任务建议 ≥ 200 |

> 思维链字段在不同线路上分别为 `reasoning` 与 `reasoning_content`，
> 取正文一律用 `choices[0].message.content`。

---

## 三、Python SDK 接法

```python
from openai import OpenAI

client = OpenAI(base_url="https://api.a7w.cn/api/v1", api_key="sk-你的key")

resp = client.chat.completions.create(
    model="Qwen3-VL-30B-A3B-Instruct",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "提取图中所有文字，输出 JSON"},
        {"type": "image_url", "image_url": {"url": "https://你的存储/票据.jpg"}},
    ]}],
    temperature=0.1,
)
print(resp.choices[0].message.content)
```

---

## 四、适合读图的模型（实测在架）

| 模型编码 | 适合 |
|---|---|
| `Qwen3-VL-30B-A3B-Instruct` | **通用首选**：中文截图、表格、海报 |
| `PaddleOCR-VL-1.5` | **文字密集**：扫描件、说明书、长截图 |
| `ERNIE-4.5-Turbo-VL` | 图文混排、需要语义理解 |
| `qwen3.6-plus` | 看图 + 推理 + 写文案 |
| `gpt-5.6-*` 系列 | 需要更强通用理解时的国际模型线 |

**能力标记**：支持视觉的还有 `Qwen3-VL-30B-A3B-Instruct`、`qwen3.6-plus`、
`ERNIE-4.5-Turbo-VL`、`PaddleOCR-VL-1.5`；支持深度推理的有 `qwen3.6-plus`、
`ERNIE-5.0-Thinking`。

---

## 五、计费

- 文本与视觉模型按**点数/百万 Token** 计（输入输出分别计价，流式与非流式同价）
- **先冻结、后结算**：调用失败直接退款
- 1 元 = 100 点
- 实时查价：`GET /api/v1/pricing` 拉规则表；逐模型的真实价以返回的 `usage` 为准

---

## 六、错误码

| HTTP | code | 含义 | 处理 |
|---|---|---|---|
| 400 | `invalid_request` | 参数缺失或格式错误 | 核对 `model` 名与 `content` 数组结构 |
| 401 | `auth_failed` | Key 缺失或无效 | 重新配置 Key |
| 402 | `insufficient_points` | 点数余额不足 | 充值；错误里有本次所需点数 |
| 402 | `key_quota_exceeded` | 该 Key 的点数额度打满 | 去用户中心调高或重置 quota |
| 403 | `permission_denied` | 该 Key 无权调用此模型 | 检查模型是否已开通 |
| 404 | `not_found` | 模型不存在 | 用 `GET /api/v1/models` 拿真名 |
| 429 | `queue_limit_exceeded` | 排队任务达上限 | 降并发后重试 |
| 5xx | `server_error` | 服务异常 | 退避重试 |

> **HTTP 状态码不足以判断成败**，业务成败以响应体里的 `code` 为准
> （模型网关正常返回时结构里只有 `choices`，没有 `code` 字段）。

---

## 七、在其它 AI 工具里接入

任何支持「自定义 OpenAI 兼容端点」的工具都能直接接上：

| 工具 | 怎么填 |
|---|---|
| 通用 OpenAI SDK / 脚本 | `base_url = https://api.a7w.cn/api/v1`，`api_key = sk-你的key` |
| Chatbox / LobeChat 等桌面客户端 | API Host 填 `https://api.a7w.cn/api`（**注意是 `/api`，不是 `/api/v1`**） |
| Dify / n8n / Coze 等编排平台 | 模型供应商选「OpenAI 兼容」，Base URL 填 `https://api.a7w.cn/api/v1` |
