# 接口契约（2026-11-08 实测原文）

网关：`https://api.a7w.cn`，认证 `Authorization: Bearer <Key>`。
所有金额单位是「点」，**1 元 = 100 点**（`GET /user/balance` 的 `rate: 100`）。

---

## 1. 入口矩阵：文本只有一条路

| 方法 | 路径 | 实测返回 | 结论 |
|---|---|---|---|
| POST | `/api/v1/chat/completions` | `422 missing field \`messages\`` | **唯一可用入口** |
| POST | `/v1/chat/completions` | `422` 同上 | 少 `/api` 也落到同一条处理链 |
| POST | `/api/chat/completions` | `422` 同上 | 少 `/v1` 也一样 |
| POST | `/api/v1/messages` | `404` + 站点首页 HTML | Anthropic 专线没有独立端点 |
| POST | `/v1/messages` | `404 {"code":"unknown_endpoint"}` | 同上 |
| POST | `/api/v1/embeddings` | `404` + 站点首页 HTML | 向量化这条路本轮没开 |
| POST | `/api/v1/v1/chat/completions` | `400 {"code":0,"msg":"该端点在...不存在"}` | 多写一层 `/v1` 就是 400 |

原始返回（逐字）：

```
POST /api/v1/chat/completions   {}
-> HTTP 200  {"code":0,"msg":"model参数不能为空","data":null}

POST /api/v1/chat/completions   {"model":"deepseek-chat"}
-> HTTP 422  {"error":{"message":"Failed to deserialize the JSON body into the target type:
   missing field `messages` at line 1 column 26 (request_id: 9fd56902-...)",
   "type":"invalid_request_error","param":null,"code":"invalid_request_error"}}

POST /v1/messages               {"model":"claude-3-5-sonnet"}
-> HTTP 404  {"error":{"message":"unknown endpoint","type":"invalid_request_error",
   "code":"unknown_endpoint","param":null}}
```

**判定要点**：`/v1/chat/completions` 的 422 和 `/api/v1/chat/completions` 一模一样，
说明网关按最后一段路由，前缀写不写 `/api` 都能到；而 `/messages` 是彻底没有的。

---

## 2. 模型目录：92 条文本模型自带价目

```
GET /api/v1/models
-> HTTP 200  522,714 字节 · 316 条
   316 = 221 条目录模型（带 model_code）+ 95 条裸模型层 ID（只有 id/object/owned_by）
   221 条里按 type_code 分：text 92 · image 50 · video 47 · other 32
   92 条 text 全部带 pricing（这也是本包能直接标价的依据）
```

单条 text 模型的结构（`claude-opus-5`，节选）：

```json
{
  "model_code": "claude-opus-5", "model_name": "Claude Opus 5",
  "vendor_code": "official", "type_code": "text", "type_name": "文本生成",
  "protocols": "anthropic_messages",
  "context_length": 0, "max_tokens": 0,
  "supports_vision": 0, "supports_reasoning": 1,
  "pricing": {
    "per_1k_input": 1584, "per_1k_output": 7920, "fixed_points": 7920,
    "pricing_v2": {
      "resource_type": "factory_model", "billing_mode": "usage",
      "items": [{
        "sku_key": "official_token", "title": "按百万 Token",
        "billing_mode": "usage", "usage_unit": "token", "usage_unit_size": 1000000,
        "price": {"points": 7920, "unit": "token"},
        "effective_rate_config": {"input": 1584, "cached_input": 0, "output": 7920},
        "reference_price": {"rates": [
          {"rate_label": "输入", "currency": "USD", "amount_usd": "5",
           "comparison": {"sale_points": "1584", "sale_cny": "15.84",
                          "reference_cny": "34.00", "saving_percent": "53.4117"}},
          {"rate_label": "输出", "currency": "USD", "amount_usd": "25",
           "comparison": {"sale_points": "7920", "sale_cny": "79.20",
                          "reference_cny": "170.00", "saving_percent": "53.4117"}}]}]
    },
    "pricing_version": "v2"
  }
}
```

### 2.1 单位口径（最容易算错的一处）

| 字段 | 名字暗示 | 实际含义 |
|---|---|---|
| `per_1k_input` | 每 1K token | **每 1,000,000 token** 的点数 |
| `per_1k_output` | 每 1K token | **每 1,000,000 token** 的点数 |
| `usage_unit_size` | — | `1000000`，这才是权威单位 |
| `price_view.summary` | — | `按百万 Token 7920 点/百万 Token` |

按 `per_1k_*` 当「每千 token」用，报价会小 1000 倍。

### 2.2 目录价里的三处异常（照原样收录，不修数据）

- `Qwen3.7-Plus`：输入 200 / 输出 105（输出比输入低）
- `GLM-5.2`：输入 800 / 输出 105
- `MiniMax-M2.7`：输入 210 / 输出 105

这三条按目录价直接算，本包不做「纠正」；实际结算以流水为准。

---

## 3. 价目表：文本入口不在里面

```
GET /api/v1/pricing
-> HTTP 200 · 21,201 字节 · 115 条规则
```

逐条确认：`/api/v1/chat/completions`、`/v1/chat/completions`、`/api/v1/messages`、
`/v1/messages`、`/api/v1/embeddings` **五条都不在** `pricing` 里，全部命中通配 `*`。

所以文本线的计费 = `max`，且每次调用**先冻 60 点**（见第 4 节）。

---

## 4. 预扣与退回：每次调用都动一次钱包

```
GET /user/balance/logs?limit=200
-> HTTP 200 · 每笔含 at / type / points / balanceAfter / reference / path

11:24:09  charge  -60  reserve_sync:/api/v1/chat/completions
11:24:11  refund  +60  refund:sync:/api/v1/chat/completions
11:24:14  charge  -60  reserve_sync:/api/v1/chat/completions
11:24:16  refund  +60  refund:sync_error:/api/v1/chat/completions
```

- `charge` 类型是「冻结/预扣」，`points` 为负数；`refund` 为正数，类型「退款」
- **净额永远是 charge + refund 的和**，不是「余额变没变」的直觉判断
- 余额可用位是 4 位小数，单看余额会以为「没动」，看流水才看得出预扣发生过

`run.py` 的 `settle` 就是按这个口径统计：只取 `reference` 含 `chat/completions`、
且 `at >= 本次开始时间` 的记录求和，作为「本次实际花费」。

---

## 5. 成功响应的形状

本轮 **0 点**，没有发出一次带 `messages` 的真实生成（见 SKILL.md 的红线与 README 的实测记录）。
本包按 OpenAI 兼容形态解析，并为 Anthropic 形态留了兼容分支：

```json
{
  "id": "chatcmpl-...", "object": "chat.completion", "model": "kimi-k3",
  "choices": [{"index": 0, "finish_reason": "stop",
               "message": {"role": "assistant", "content": "…回答正文…"}}],
  "usage": {"prompt_tokens": 21, "completion_tokens": 380, "total_tokens": 401}
}
```

解析规则（`answer_of` / `usage_of`）：

| 取值 | 依次尝试 |
|---|---|
| 正文 | `choices[0].message.content` → `choices[0].text` → `choices[0].content` → `content` → `data.content` → 字符串列表拼接 |
| 输入 token | `usage.prompt_tokens` → `usage.input_tokens` → 0 |
| 输出 token | `usage.completion_tokens` → `usage.output_tokens` → 0 |
| 总量 | `usage.total_tokens` → 输入 + 输出 |

**成功响应不带 `code` 字段**（OpenAI 兼容层的既有约定，站内多个包都记过同一条）。
所以判定成功的依据是「`choices` 有内容」，而不是 `code == 1`。

---

## 6. 免费端点清单（本包只用这些）

| 端点 | 用途 | 扣费 |
|---|---|---|
| `GET /api/v1/models` | 92 条文本模型 + 价目 | 0 |
| `GET /api/v1/pricing` | 115 条规则 + 通配 | 0 |
| `GET /api/v1/tasks/<id>` | 异步任务查询（文本同步，一般用不到） | 0 |
| `GET /api/v1/me/tasks` | 任务台账（含 model / actualPrice） | 0 |
| `GET /user/balance` | 余额 / 冻结 / 1 元 = 100 点 | 0 |
| `GET /user/balance/logs` | 流水（`limit` 上限 1000） | 0 |
| `POST /api/v1/chat/completions` + 缺 `messages` | 参数校验探针 | 预冻 60 点，自动退回 |

---

## 7. 本包的内置价目快照

`scripts/run.py` 里 `TEXT_MODELS` 是 92 条 text 模型的快照（`code -> {fam, i, o, ctx, vis, rsn, p, st, note}`）：

- `i` / `o`：输入 / 输出每百万 token 的点数
- `p`：目录协议，`chat`（含 openai_chat，66 个）/ `anthropic`（13 个）/ `responses`（13 个）

`catalog --live` 会用 `GET /api/v1/models` 的现查值覆盖 `i` / `o`，`st` 不受影响（那是实测结论）。
