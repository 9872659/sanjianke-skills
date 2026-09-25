# 模型网关：OpenAI 兼容层

聊天客户端要接上 75 个模型，靠的就是这一层：**协议与 OpenAI 完全一致**，所以你只需要改两个地方 —— `base_url` 和 `api_key`。客户端里原来填 OpenAI 的地方，换成下面这组值就能用。

## 一、端点与鉴权

```
Base URL : https://api.a7w.cn/api/v1
对话     : POST https://api.a7w.cn/api/v1/chat/completions
模型清单 : GET  https://api.a7w.cn/api/v1/models
鉴权头   : Authorization: Bearer <你自己的 API Key>
           Content-Type: application/json
```

Key 形如 `sk-...`，在 [算力集市](https://api.a7w.cn/) 用户中心创建。**注意 `Bearer ` 后面有一个空格**，少了这个空格就是 401。

## 二、最小请求

先用 `curl` 把地址、Key、模型名三件事一次验完，再去配客户端：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 256
  }'
```

返回里 `choices[0].message.content` 有内容，说明**鉴权、网络出口、模型名、点数余额四项全通**。后面客户端再出问题，就一定出在客户端配置那一层。

> Windows PowerShell 里 JSON 双引号容易被吃掉。要么把请求体写进 `body.json` 用 `-d "@body.json"`，要么用包内零依赖客户端。

## 三、Python SDK 接入

装官方 SDK 即可，只换 `base_url` 与 `api_key`：

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",          # 生产环境请从环境变量读
)

resp = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "你好"}],
    max_tokens=256,
)
print(resp.choices[0].message.content)
```

流式：

```python
stream = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "写一段 200 字的产品介绍"}],
    max_tokens=1024,
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="", flush=True)
```

## 四、Node SDK 接入

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.a7w.cn/api/v1",
  apiKey: process.env.A7W_API_KEY,
});

const r = await client.chat.completions.create({
  model: "DeepSeek-V4-Flash",
  messages: [{ role: "user", content: "你好" }],
  max_tokens: 256,
});
console.log(r.choices[0].message.content);
```

前后端同构的框架（Next.js、Nuxt、Electron）都按这套写。**Key 只放服务端**，不要打进浏览器包。

## 五、模型发现：先查再填，不要猜

模型名**大小写敏感、必须逐字一致**。上下架很频繁，文章里抄来的编码经常已经不在架上了。

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

**实测返回 75 个模型、23 家厂商。** 每条记录的字段是：

| 字段 | 含义 |
|---|---|
| `model_code` | **模型编码** —— 填进客户端的 `model` 字段就是这个 |
| `model_name` | 展示名 |
| `vendor_name` | 厂商 |
| `call_type_desc` | 调用形态（同步 / 异步） |
| `supports_vision` | 是否支持读图 |
| `supports_reasoning` | 是否为推理模型 |

> 字段名是 `model_code`，**不是 `model`**。写解析代码时按 `model_code` 取。

### 按用途选模型的对照表

| 你要做的事 | 用哪个编码 | 为什么 |
|---|---|---|
| 日常对话、客户端默认模型 | `DeepSeek-V4-Flash` | 快、便宜，中文稳 |
| 复杂推理、难题攻坚 | `DeepSeek-V4-Pro` | 同一家的加强档 |
| 性价比高的国产通用 | `Qwen3.6-Plus` / `Qwen3.6-Flash` | 通义千问中档，响应快 |
| 大参数通用 | `Qwen3.7-Max` / `Qwen3.7-Plus` | 长上下文、复杂任务 |
| 长文、长文档阅读 | `Kimi-K2.6` | 长上下文见长 |
| 代码补全与重构 | `Qwen3-Coder-Next` / `Kimi-K2.7-Code` | 代码专用线 |
| 读图、看图问答 | `Qwen3-VL-30B-A3B-Instruct` / `ERNIE-4.5-Turbo-VL` | `supports_vision` 为真 |
| 深度思考、慢但准 | `ERNIE-5.0-Thinking` / `DeepSeek-R1-Distill-Qwen-32B` | 推理模型，见第八节 |
| 轻量本地化场景 | `Qwen3.5-Flash` / `Qwen2.5-7B-Instruct` | 便宜、够用 |
| 翻译 | `Hunyuan-MT-Chimera-7B` / `Hy-MT2-30B-A3B` | 混元翻译线 |
| 智谱 GLM 系列 | `GLM-5.2` / `GLM-5` / `GLM-4.7` | 按档位挑 |
| 数学与推理 | `QwQ-32B` | 专门的推理线 |
| 国际模型 | `gpt-5.6-sol` / `gpt-5.5` / `gpt-5.4-mini` | 同一把 Key 一起用 |

**选型的方法论只有一条：先在客户端里手动加 2~3 个候选，用同一段真实 prompt 各跑一次，比较效果与点数消耗，再决定默认模型。** 别纠结参数表。

## 六、常用参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `model` | string | **必填**。以 `GET /api/v1/models` 返回的 `model_code` 为准 |
| `messages` | array | **必填**。`[{"role":..., "content":...}]`，role 取 `system` / `user` / `assistant` |
| `temperature` | number | 采样温度。闲聊 0.7~1.0，抽取/分类 0~0.3 |
| `max_tokens` | integer | 最大生成 tokens。**它同时是控成本最有效的旋钮** |
| `stream` | boolean | 流式返回（SSE），聊天客户端必须开 |
| `top_p` | number | 核采样。与 `temperature` 二选一调，别同时猛调 |

客户端里能填的字段通常只有 `temperature` 与 `max_tokens`，其余用默认值即可。

## 七、流式（SSE）

`stream: true` 时返回 `text/event-stream`，逐行 `data: {...}`，以 `data: [DONE]` 结束。

```
data: {"choices":[{"delta":{"content":"你"},"index":0}]}
data: {"choices":[{"delta":{"content":"好"},"index":0}]}
data: [DONE]
```

取增量文本的路径是 **`choices[0].delta.content`**，注意**不是** `message.content`——这是手写解析时最常见的错误，写成 `message` 会一直拿到空。

解析要点：

1. 按行读，跳过空行，`data: ` 前缀要去掉。
2. 遇到 `data: [DONE]` 立即停止，不要继续读流。
3. `delta.content` 可能为 `null`（尤其在思维链阶段），要容错。
4. 客户端的「流式输出」开关打开后如果一直不出字，先看它是不是把 `delta` 取成了 `message`。

## 八、响应结构

非流式响应与 OpenAI 一致：

```json
{
  "id": "chatcmpl-xxx",
  "model": "deepseek-v4-flash",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "你好，有什么可以帮你？" },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46 }
}
```

`finish_reason` 的取值含义：

| 值 | 含义 |
|---|---|
| `stop` | 正常结束 |
| `length` | 达到 `max_tokens` 被截断 |
| `content_filter` | 内容被拦 |

## 九、推理模型的实测细节（重点）

一批模型是**推理模型**（`supports_reasoning` 为真，如 `DeepSeek-V4-Flash`、`ERNIE-5.0-Thinking`）：它们先花 token 产出思维链，再给正文。由此带来三个实测行为，写进代码前必须知道。

### 9.1 `max_tokens` 太小会让正文为空

实测 `DeepSeek-V4-Flash`：

| `max_tokens` | 结果 |
|---|---|
| `8` | `content` 为 **`null`**，`finish_reason` 是 **`length`** —— token 全被思维链吃掉 |
| `256` | `content` 正常返回，`finish_reason` 是 `stop` |

所以：

- **`content` 可能是 `null`**，代码里必须容错，不要假定它是字符串。
- 看到 `finish_reason: "length"` 且正文为空，**先把 `max_tokens` 调大**，不是接口坏了。
- **客户端里给推理模型设 `max_tokens` 一律不低于 256。** 设成 64、32 这类值，等于让它只输出思维链。

### 9.2 思维链字段名有两个

不同线路上思维链分别放在 **`reasoning`** 与 **`reasoning_content`** 两个字段里。**两个都要取**：

```python
msg = resp["choices"][0]["message"]
reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
content = msg.get("content") or ""
```

想隐藏思考过程就整段丢弃；想展示就单独放一个折叠区。

### 9.3 响应里的 `model` 会被规范成小写

请求 `DeepSeek-V4-Flash`，响应里的 `model` 返回 **`deepseek-v4-flash`**（小写）。

> **别拿响应里的 `model` 做精确匹配** —— 会永远匹配不上。要做映射就用请求时自己记的那份编码。

## 十、与「应用任务」的边界对照

这是选错入口最集中的地方。两条路完全不同：

| | 模型网关 | 应用任务 |
|---|---|---|
| 路径 | `/api/v1/chat/completions` | `/api/v1/apps/<应用代号>/<接口代号>` |
| 入参 | `messages` 数组 | 业务参数（`text` / `image_url` / `video_url` …） |
| 返回 | `choices`，同步返回 | 多为 `task_id`，异步 |
| 用量 | 点数 / 百万 tokens | 点数 / 张、/ 秒、/ 千字、/ 次 |
| 典型用途 | 对话、写作、翻译、分类、抽取、代码 | 出图、出视频、配音、数字人、音乐、超分 |

**模型网关没有 `task_id`；应用任务也不吃 `messages` 数组。** 选错入口的报错通常是 400 `invalid_request` 或 404 `not_found`。

详细的应用清单、参数读法与异步生命周期见 `api-apps-tasks.md`。

## 十一、计费与排错要点

**计费口径**：

- 文本按**点数 / 百万 tokens**，**输入与输出分别计价**；**流式与非流式同价**。
- **1 元 = 100 点，1 点 = 0.01 元**。点数永久有效。
- 平台同时给两套价格字段：`fixed_price` / `input_price` 是公示标准价；`tenant_*` 是**你所在租户的实际结算价**。**做预算一律按 `tenant_*`，最终以账号里实际扣费为准。**
- 实测参考：`DeepSeek-V4-Flash` 一次普通问答约 **0.74 ~ 0.99 点**；极小调用（`max_tokens=8`）为 **0.00 点**。
- 控成本的第一手段是**压 `max_tokens`**，第二手段是**精简 system prompt**（它每次都随请求计费）。

**排错顺序**：

| 现象 | 真正的含义 | 怎么办 |
|---|---|---|
| 401 `auth_failed` | Key 缺失或无效 | 重新复制 Key；确认 `Bearer ` 前缀与那个空格 |
| 404 `not_found` | 路径或模型名不存在 | **先怀疑 `/v1` 层数**，再怀疑模型名大小写 |
| 402 `insufficient_points` | 账号余额不足 | 充值；错误里带本次所需点数 |
| 402 `key_quota_exceeded` | **这个 Key 的**额度打满 | 调高该 Key 的 quota，**不用充值** |
| 403 `permission_denied` | 该 Key 无权调用此模型 | 检查模型是否已开通，与余额无关 |
| 429 `queue_limit_exceeded` | 并发/排队达上限 | 降并发，退避重试 |
| `content` 为空且 `length` | `max_tokens` 太小 | 调到 256 以上 |
| `content` 一直为空，`stop` | 解析取错了字段 | 流式取 `delta.content`，非流式取 `message.content` |

**完整错误码表见 `通用说明.md`。**

## 十二、自检清单

- [ ] `curl` 直连 `/api/v1/chat/completions` 返回 200，才去配客户端
- [ ] `base_url` 填的是 `https://api.a7w.cn/api/v1`（自带 `/v1` 的客户端填 `https://api.a7w.cn/api`）
- [ ] 模型编码是从 `/api/v1/models` 现场拉的，逐字复制，没有抄文章里的旧名
- [ ] 推理模型的 `max_tokens` 不低于 256
- [ ] 代码里对 `content == null` 做了容错，`reasoning` 与 `reasoning_content` 都取了
- [ ] 流式解析取的是 `choices[0].delta.content`
- [ ] Key 走环境变量或 `.env`，`.env` 已在 `.gitignore` 里
- [ ] 预算按 `tenant_*` 算，不是按公示价算
