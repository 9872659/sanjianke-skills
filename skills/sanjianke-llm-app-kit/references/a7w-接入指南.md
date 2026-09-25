# a7w 接入指南 · base_url / 鉴权 / SDK 写法

本 Skill 的所有模型能力都走 **算力集市 api.a7w.cn**。它兼容 OpenAI 协议，
所以**接进来的动作只有一个：改 `base_url`。**

## 两个值，记住就够

```
Base URL: https://api.a7w.cn/api/v1
Authorization: Bearer <你的 API Key>
```

**只有 `/api/v1` 这一层是网关。** 官方 SDK 会自己拼 `/chat/completions`，
所以 `base_url` 填 `https://api.a7w.cn/api/v1`；裸 `curl` 就写全路径
`https://api.a7w.cn/api/v1/chat/completions`。

## 鉴权

- Key 在 **[api.a7w.cn](https://api.a7w.cn/)** 用户中心 → API 密钥创建。
- 每个 Key 可以单独设**消费上限（quota）**，打满后这个 Key 就调不动了
  —— 这跟账号余额是两回事，报错码也不同。
- **Key 等同于余额**，不要写进代码、不要提交进 Git。本 Skill 从环境变量
  `A7W_API_KEY` 或 `~/.a7w/config.json` 读。

```bash
# 配一次，之后所有命令都不用再带 Key
python3 scripts/a7w.py login --key sk-你的key
```

## 最小可用调用

```bash
curl -sS "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

Python SDK 里就是换两个参数：

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
```

**原来的业务代码一行都不用动。**

## 模型清单以接口为准

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

- 实测 **75 个模型 / 23 家厂商**（文本 58 · 图片 12 · 视频 5），含 DeepSeek、通义千问、
  智谱 GLM、Kimi、文心、混元、MiniMax、小米 MiMo，以及 OpenAI GPT、Google nano-banana、xAI Grok 等。
- 换模型就是**换一个字符串**，不用换 base_url、不用换 Key、账单还是同一份。
- 站内宣传口径与实测口径不一致，**要准数现场跑接口**。
- 平台的 `vendor_name` 字段存在标注串味，**以 `model` 编码为准**，不要用厂商字段做精确匹配。
- 模型上下架很频繁，**不要把自己的逻辑绑在某个名字一定存在上**。

## 可以换的模型示例

| 场景 | 建议 `model` |
|---|---|
| 中文通用、性价比优先 | `DeepSeek-V4-Flash`、`Qwen3.6-Flash` |
| 复杂推理 | `DeepSeek-R1-Distill-Qwen-32B`、`ERNIE-5.0-Thinking` |
| 长文与代码 | `Kimi-K2.6`、`Qwen3-Coder-Next` |
| 视觉理解 | `qwen3.6-plus`、`Qwen3-VL-30B-A3B-Instruct`、`PaddleOCR-VL-1.5` |
| 出图 | `nano-banana-pro`、`gpt-image-2.5` |
| 出视频 | `veo3.1-pro`、`grok-video` |

> 这张表只是选型起点。**下发前用 `models` 接口核对一遍**。

## 流式与常用参数

```python
stream = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "用三句话解释量子计算"}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
```

| 参数 | 说明 |
|---|---|
| `model` | **必填**，值来自模型列表接口 |
| `messages` | 标准 OpenAI 消息数组 |
| `stream` | 流式；流式与非流式**同价** |
| `temperature` / `top_p` | 常规采样参数 |
| `max_tokens` | **推理模型要给足**，否则 token 先花在思维链上、`content` 会是 `null` |
| `tools` | 支持工具调用的模型可传，按 OpenAI 格式 |

> **推理模型的思维链字段名在不同线路上分别是 `reasoning` 和 `reasoning_content`。**
> 两种都读一下，比只读一个稳。

## 两条入口别选错

| 入口 | 路径 | 形态 |
|---|---|---|
| **模型网关** | `POST /api/v1/chat/completions` | 同步，返回 `choices` |
| **应用任务** | `POST /api/v1/apps/{app}/{api}` | 多为异步，返回 `task_id` |

生成类能力（出图 / 出视频 / 配音 / 数字人 / 文档问答）**不在模型网关里**，
它们走应用任务，见 `api-应用与任务.md`。

## 错误码

| HTTP | code | 含义 | 怎么处理 |
|---|---|---|---|
| 400 | `invalid_request` | 参数缺失或格式错误 | 用 `schema <app>` 核对参数名与必填项 |
| 401 | `auth_failed` | API Key 缺失或无效 | 重新 `login` |
| 402 | `insufficient_points` | 点数余额不足 | 充值；错误里有本次所需点数 |
| 402 | `key_quota_exceeded` | 该 Key 的点数额度打满 | 调高或重置 Key 的 quota，或换 Key |
| 403 | `permission_denied` | 该 Key 无权调用此模型/应用 | 检查模型是否已开通、Key 是否被限权 |
| 404 | `not_found` | 模型 / 应用 / 任务不存在 | 核对代码拼写，用 `apps`、`models` 拿真名 |
| 429 | `queue_limit_exceeded` | 排队任务已达上限 | 降并发，等队列消化后重试 |
| 5xx | `server_error` | 服务异常 | 退避重试；仍失败换模型 / 线路 |

**注意 402 有两种**：账号没钱（`insufficient_points`）和 Key 自己的额度打满
（`key_quota_exceeded`）。查错时先分清是哪一种，否则会去充一个根本不需要充的账户。
