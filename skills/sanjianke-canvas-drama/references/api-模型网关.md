# API · 模型网关（OpenAI 兼容入口）

短剧流程里的**文本环节**全走这里：拆剧本、写人物小传、出分镜表、写提示词、审连贯。
一把 Key，OpenAI 协议，**换模型只改 `model` 字段**。

---

## 一、端点与鉴权

```
Base URL : https://api.a7w.cn/api/v1
Chat     : POST https://api.a7w.cn/api/v1/chat/completions
Models   : GET  https://api.a7w.cn/api/v1/models
Header   : Authorization: Bearer <你的 API Key>
           Content-Type: application/json
```

**与 OpenAI 官方接口的差别只有 `base_url` 和 `model` 名。**
不用换 Key、不用重新签名、不用改代码结构。

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

---

## 二、最小请求

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<先用 GET /api/v1/models 查到可用模型名>",
    "messages": [{"role":"user","content":"把这段剧情拆成 12 个分镜，每镜给：镜号、景别、运镜、时长、画面、台词。<剧情略>"}]
  }'
```

响应：

```json
{
  "id": "chatcmpl-xxx",
  "model": "deepseek-v4-flash",
  "choices": [
    { "index": 0,
      "message": { "role": "assistant", "content": "……" },
      "finish_reason": "stop" }
  ],
  "usage": { "prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46 }
}
```

> **模型名会被规范化**：请求 `DeepSeek-V4-Flash`，响应里 `model` 可能返回小写
> `deepseek-v4-flash`。**别拿响应的 `model` 去做精确匹配。**

---

## 三、查在架模型（**先查再猜**）

模型名**不要猜**，也不要抄别人的 —— 上下架会变。

```bash
curl -sS "https://api.a7w.cn/api/v1/models" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

返回的模型字段：

| 字段 | 含义 |
|---|---|
| `model_code` | **调用时填的模型名** |
| `model_name` | 展示名 |
| `call_type_desc` | 同步 / 异步 |
| `vendor_name` | 厂商 |
| `supports_vision` | 是否支持图片输入 |
| `supports_reasoning` | 是否推理模型 |

> 清单里的字段是 `model_code` / `model_name`（**不是** `model`）。
> 别用中文展示名去调用。

---

## 四、短剧流程里的四个用法

| 用途 | 温度 | 关键写法 |
|---|---|---|
| **拆剧本**（分场、情绪曲线） | 0.5~0.7 | 给它明确的输出结构，不要让它自由发挥 |
| **人物小传** | 0.6~0.8 | 每个角色固定字段：姓名 / 年龄 / 外形锚点 / 服装 / 说话方式 |
| **出分镜表** | **0.2~0.4** | 只输出 CSV，表头写死，见 `分镜方法.md` |
| **写提示词** | 0.3~0.5 | 给它八槽位模板（见 `提示词范式.md`），让它逐槽位填空 |
| **连贯性审校** | 0.1~0.3 | 把分镜表整段喂进去，让它只报问题不改写 |

### 4.1 出分镜表（最常用的一个）

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<在架模型名>",
    "temperature": 0.3,
    "max_tokens": 4000,
    "messages": [
      {"role":"system","content":"你是短剧分镜师。只输出 CSV，表头固定为 shot_id,shot_size,camera,duration,visual,dialogue,transition,characters,scene,sfx,recipe。不要解释，不要代码块围栏。"},
      {"role":"user","content":"把下面这段剧情拆成分镜：单镜 4~8 秒；对话戏用近景/特写；每镜只写一个动作；transition 只从「动作衔接/视线衔接/空间衔接/声音衔接」里选。<剧情略>"}
    ]
  }'
```

- 输出**直接存 `shots.csv`**，后面的自检脚本、配音、SRT 全部读它
- `max_tokens` 给足（分镜表很长），否则会被截断成半张表

### 4.2 让模型按 JSON 返回（便于程序处理）

```
只输出 JSON，结构为：
{"shots":[{"shot_id":"S01-001","shot_size":"远景","camera":"缓慢推进","duration":5,
"visual":"…","dialogue":"","transition":"视线衔接","characters":["LIN"],"scene":"SC-01","sfx":"…"}]}
不要输出 JSON 以外的任何字符。
```

---

## 五、常用参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `model` | string | **必填**。以 `GET /api/v1/models` 的结果为准 |
| `messages` | array | **必填**。`[{role, content}]`，role 取 `system` / `user` / `assistant` |
| `temperature` | number | 采样温度，越高越发散。结构化任务压到 0.2~0.4 |
| `max_tokens` | integer | 最大生成 tokens，**同时是控成本的主要旋钮** |
| `stream` | boolean | 流式返回（SSE） |
| `top_p` | number | 核采样 |

---

## 六、流式（SSE）

`stream: true` 时返回 `text/event-stream`，逐行 `data: {...}`，以 `data: [DONE]` 结束。
取增量文本的路径是 **`choices[0].delta.content`**（注意不是 `message.content`）。

```bash
curl -N -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"<在架模型名>","messages":[{"role":"user","content":"写一段 200 字的短剧开场钩子"}],"stream":true}'
```

**写长剧本时用流式**：边出边看，随时可以中断，不用等一整段。

---

## 七、SDK 接入

### Python

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",          # 或 os.environ["A7W_API_KEY"]
)

resp = client.chat.completions.create(
    model="<在架模型名>",
    temperature=0.3,
    messages=[
        {"role": "system", "content": "你是短剧分镜师，只输出 CSV。"},
        {"role": "user", "content": "把下面这段剧情拆成 12 个分镜：<剧情略>"},
    ],
)
print(resp.choices[0].message.content)
```

### Node

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.a7w.cn/api/v1",
  apiKey: process.env.A7W_API_KEY,
});

const r = await client.chat.completions.create({
  model: "<在架模型名>",
  temperature: 0.3,
  messages: [{ role: "user", content: "把这段剧情拆成 12 个分镜：<剧情略>" }],
});
console.log(r.choices[0].message.content);
```

---

## 八、推理模型的两个注意点

部分模型是**推理模型**：先花 token 产出思维链，再给正文。

| `max_tokens` | 结果 |
|---|---|
| 太小（如 8） | `content` 可能是 **`null`**，`finish_reason: "length"` —— token 全被思考过程吃掉了 |
| 给足（如 200 以上） | 正常返回正文，`finish_reason: "stop"` |

所以：

- **`content` 可能是 `null`**，代码里必须容错，不要假定它是字符串
- 看到 `finish_reason: "length"` 且正文为空，**先把 `max_tokens` 调大**
- 思维链字段名在不同线路上不一致（可能出现 `reasoning` 或 `reasoning_content`），两个都取一下
- 拆剧本、写分镜这类任务，**用非推理模型更快更省**；只有复杂的情节推演才需要推理模型

---

## 九、错误码与排错

| HTTP | code | 含义 | 处理 |
|---|---|---|---|
| 400 | `invalid_request` | 参数缺失或格式错误 | 核对 `messages` 结构、`model` 名 |
| 401 | `auth_failed` | API Key 缺失或无效 | 重建 Key 并重新配置 |
| 402 | `insufficient_points` | **账号**点数余额不足 | 充值；错误信息里有本次所需点数 |
| 402 | `key_quota_exceeded` | **该 Key 的**点数额度打满 | 调高 / 重置 Key 的 quota，**不用充值** |
| 403 | `permission_denied` | 该 Key 无权调用此模型 | 检查模型是否已开通，与余额无关 |
| 404 | `not_found` | 模型不存在 | `GET /api/v1/models` 拿真名 |
| 429 | `queue_limit_exceeded` | 并发达上限 | 退避后重试，降并发 |
| 5xx | `server_error` | 服务异常 | 退避重试；持续失败换模型 |

| 现象 | 原因 | 处理 |
|---|---|---|
| 报「模型不存在」 | 模型名是猜的 | 先 `GET /api/v1/models` |
| 正文为空 | `max_tokens` 被思考过程吃光 | 调大 `max_tokens` |
| 返回的不是合法 CSV | 模型加了代码块围栏或解释 | 在 system 里明确「不要解释，不要代码块围栏」 |
| 中文名当 model 用 | 用了展示名 | 用 `model_code` |

---

## 十、计费

- 文本生成按**点 / 百万 tokens** 计，**输入与输出分别计价**，流式与非流式同价
- **控成本先压 `max_tokens`**，其次是把 `temperature` 降低（少绕弯）
- 实测参考：一次普通问答约 **0.74~0.99 点**；极小的调用（`max_tokens=8`）为 0.00 点
- 拆一部剧的剧本与分镜通常十几到几十次调用，**总成本在几毛钱量级**
- **先冻结后结算，失败全额退回**；每次返回的 `data.usage.points_cost` 是本次真实扣费

> 文本成本在整部短剧里几乎可以忽略（图片与视频才是大头）。
> **不要在提示词上省钱** —— 分镜写得细一点，省下的是后面几倍的返工。

---

## 十一、和「生成应用」的边界

| | 模型网关 | 生成应用 |
|---|---|---|
| 路径 | `/api/v1/chat/completions` | `/api/v1/apps/{应用代号}/{接口代号}` |
| 入参 | `messages` 数组 | 业务参数（`prompt` / `text` / `image_urls` …） |
| 返回 | `choices` 同步返回 | 多为 `task_id` 异步 |
| 典型用途 | 拆剧本、出分镜、写提示词、审校 | 出图、出视频、配音、数字人、音乐 |

**别拿 `messages` 去调应用**，也别指望模型网关返回 `task_id`。
选错入口的报错通常是 400 或 404。应用接口的完整速查见 `api-生成应用.md`。
