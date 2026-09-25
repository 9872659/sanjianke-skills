# OpenAI 兼容入口（模型网关）

本网关的模型侧**兼容 OpenAI 协议**：换 `base_url` 和 `model` 即可，SDK 代码基本不用改。

---

## 一、地址与鉴权

```
Base URL: https://api.a7w.cn/api/v1
Authorization: Bearer <你的 API Key>
```

- Key 在 **用户中心 → API 密钥** 创建（需完成实名认证）。
- 每个 Key 可以单独设**消费上限（quota）**，打满后这个 Key 就调不动了 ——
  这跟账号余额是两回事，报错码也不同。
- **Key 等同于余额**，不要写进代码、不要提交进 Git。

配一次，之后所有命令都不用再带 Key：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

---

## 二、最小调用

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

Python SDK：

```python
from openai import OpenAI

client = OpenAI(base_url="https://api.a7w.cn/api/v1", api_key="sk-你的key")
resp = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)
```

---

## 三、模型清单（实测在架 75 个 / 23 家厂商）

### 国产大模型

| 厂商 | 在架代表模型（`model` 编码） |
|---|---|
| **DeepSeek 深度求索** | `DeepSeek-V4-Pro`、`DeepSeek-V4-Flash`、`DeepSeek-V3.2`、`DeepSeek-R1-Distill-Qwen-32B` |
| **通义千问 Qwen** | `Qwen3.7-Max`、`Qwen3.7-Plus`、`Qwen3.6-Plus`、`Qwen3.6-Flash`、`Qwen3.6-35B-A3B`、`Qwen3.6-27B`、`Qwen3.5-122B-A10B`、`Qwen3.5-35B-A3B`、`Qwen3.5-27B`、`Qwen3.5-Flash`、`Qwen3-Coder-Next`、`Qwen3-Next-80B-A3B-Instruct`、`Qwen3-VL-30B-A3B-Instruct`、`Qwen3-32B`、`QwQ-32B` |
| **智谱 GLM** | `GLM-5.2`、`GLM-5.1`、`GLM-5`、`GLM-4.7`、`GLM-4-32B`、`AutoGLM-Phone-9B-Multilingual` |
| **月之暗面 Kimi** | `Kimi-K2.7-Code`、`Kimi-K2.6`、`Kimi-K2.5`、`kimi-k3` |
| **百度文心 ERNIE** | `ERNIE-5.0-Thinking`、`ERNIE-4.5-Turbo`、`ERNIE-4.5-Turbo-VL` |
| **腾讯混元** | `Hy-MT2-30B-A3B`、`HY-MT2-7B`、`HY-MT1.5-7B` |
| **MiniMax** | `MiniMax-M3`、`MiniMax-M2.7`、`MiniMax-M2.5`、`MiniMax-M2.1` |
| **阿里云百炼** | `qwen-image-3.0`、`qwen3.6-plus`、`wan3.0-video` |
| **小米 MiMo** | `MiMo-V2.5-Pro` |
| **垂类专业模型** | `Fin-R1`、`DianJin-R1-32B`（金融）、`LegalOne-8B`（法律）、`KAT-Dev`（开发） |

### 国际主流大模型

| 厂商 | 在架代表模型 |
|---|---|
| **OpenAI（文本）** | `gpt-5.6-sol`、`gpt-5.6-luna`、`gpt-5.6-terra`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini` |
| **OpenAI（图像）** | `gpt-image-2.5-sunburst`、`gpt-image-2.5`、`gpt-image-2-pro`、`gpt-image-2-fast` |
| **Google** | `nano-banana-pro`、`nano-banana-2`、`gemma-4-26B-A4B-it` |
| **xAI** | `grok-video`、`veo3.1-pro`、`veo3.1-fast` |

**能力标记**：支持视觉 `qwen3.6-plus`、`Qwen3-VL-30B-A3B-Instruct`、`ERNIE-4.5-Turbo-VL`；
支持深度推理 `qwen3.6-plus`、`ERNIE-5.0-Thinking`。

> **清单会变。** 模型上下架频繁，**调用前先读一次清单**：
> `python3 scripts/a7w.py apps`，或直接请求 `GET /api/v1/models`。
> 以接口返回为准，不要用宣传页上的数字做参数校验。

---

## 四、常用参数

| 参数 | 说明 |
|---|---|
| `model` | 必填。取值来自模型清单，**不要猜** |
| `messages` | 必填。标准 OpenAI 结构，支持 `system` / `user` / `assistant` |
| `stream` | 流式输出；SSE 形式返回增量 |
| `temperature` / `top_p` | 采样参数，按模型支持情况传 |
| `max_tokens` | **推理类模型要留足** —— 思维链也占 token，给小了 `content` 会是空的 |
| `response_format` | 需要结构化输出时，按模型支持情况传 JSON 模式 |

**推理模型注意**：思维链字段名在不同线路上分别是 `reasoning` 和 `reasoning_content`，
取值时两个都兜一下。

---

## 五、错误码

| HTTP | code | 含义 | 怎么处理 |
|---|---|---|---|
| 400 | `invalid_request` | 参数缺失或格式错误 | 核对参数名与必填项 |
| 401 | `auth_failed` | API Key 缺失或无效 | 重新 `login` |
| 402 | `insufficient_points` | 点数余额不足 | 充值；错误里有本次所需点数 |
| 402 | `key_quota_exceeded` | 该 Key 的点数额度打满 | 去用户中心调高 / 重置 Key 的 quota，或换 Key |
| 403 | `permission_denied` | 该 Key 无权调用此模型 | 检查模型是否已开通、Key 是否被限权 |
| 404 | `not_found` | 模型 / 应用 / 任务不存在 | 核对拼写，用接口拿真名 |
| 429 | `queue_limit_exceeded` | 排队任务已达上限 | 降并发，等队列消化后重试 |
| 5xx | `server_error` | 服务异常 | 退避重试；仍失败换模型 / 线路 |

**注意 402 有两种**：账号没钱（`insufficient_points`）和 Key 自己的额度打满
（`key_quota_exceeded`）。查错时先分清是哪一种。

**业务成功码是 `1`**（`{"code":1,"msg":"success"}`），不是 `0`。

---

## 六、接线检查

- [ ] `base_url` 是 `https://api.a7w.cn/api/v1`
- [ ] Key 从环境变量或配置文件读，**没有硬编码**
- [ ] `model` 取值来自接口清单，不是猜的
- [ ] 推理类模型留足了 `max_tokens`
- [ ] 网络超时后没有直接重提付费请求，而是先查状态
