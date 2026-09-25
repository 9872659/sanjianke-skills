# DeepSeek 系列：模型网关 OpenAI 兼容层

这份文档是 `SKILL.md`「接线」两节的**展开版**：端点、鉴权、SDK 写法、模型发现、流式解析、
推理模型的实测行为与排错，都在这里逐条写清。**只想先跑通一条请求的话，看 `SKILL.md` 的前三节就够；
本文写给要把它接进正式业务、并且主要跑 DeepSeek 系列的人。**

## 一、端点与鉴权

全部对话请求都打这一个地址，没有第二种写法：

```
Base URL : https://api.a7w.cn/api/v1
Chat     : POST https://api.a7w.cn/api/v1/chat/completions
Header   : Authorization: Bearer <你的 API Key>
           Content-Type: application/json
```

| 项 | 值 | 说明 |
|---|---|---|
| 协议 | HTTPS | 请求只发往 `api.a7w.cn` |
| 鉴权 | `Authorization: Bearer sk-...` | **`Bearer ` 后面有一个空格**，掉了就是 401 |
| 请求体 | JSON | `model` 与 `messages` 必填 |
| 宿主自带 `/v1` 时 | Base URL 填 `https://api.a7w.cn/api` | 判断方法只有一条：看它给的示例地址里有没有 `/v1`。填错的典型症状是路径里出现 `/api/v1/v1/` 然后 404 |

**从 OpenAI 迁过来的改动量就是两个字符串：`base_url` 与 `model`。**
Key 换成你在 api.a7w.cn 申请的那把，账单也只记在你这一个账号上——
不需要另开账号、不需要重新签名、不需要为每个模型单独对账。

## 二、最小请求（curl）

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

读回答的字段路径是 `choices[0].message.content`。

两个实操建议：

- **请求体复杂时落成文件**，用 `-d @body.json`，省掉 Windows 下引号被 shell 吃掉的问题。
- **判断成败看 `code == 1`**（`{"code":1,"msg":"success"}`）。`code == 0` 是失败，但 **HTTP 状态码仍可能是 200** ——
  只看 HTTP 会漏掉一整类失败。

## 三、SDK 接入：Python 与 Node

**Python**——`base_url` 写全，含 `/v1`：

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",   # 只改这一行
    api_key="sk-你的key",                    # 只改这一行
)

resp = client.chat.completions.create(
    model="DeepSeek-V4-Pro",
    messages=[{"role": "user", "content": "把这段需求拆成开发任务清单"}],
)
print(resp.choices[0].message.content)
```

**Node**——注意是大写 URL 结尾的 `baseURL`：

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.a7w.cn/api/v1",   // 只改这一行
  apiKey: process.env.A7W_API_KEY,        // 只改这一行
});

const r = await client.chat.completions.create({
  model: "DeepSeek-V4-Pro",
  messages: [{ role: "user", content: "你好" }],
});
console.log(r.choices[0].message.content);
```

**换成任何一个在架模型都只是改 `model` 字符串**：base_url 不动、Key 不动、客户端实例可以复用。

## 四、模型发现与选型

### 4.1 先拉清单，不要猜编码

```bash
curl -sS "https://api.a7w.cn/api/v1/models" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

**实测返回 75 个模型 / 23 家厂商**（这个数字会随上下架变化，以你现场拉到的为准）。
清单里的字段名是 `model_code`（编码）与 `model_name`（显示名）——**填进请求的是 `model_code`，逐字照抄、大小写别改**。

### 4.2 在架 DeepSeek 四个编码

| 编码（逐字照抄） | 定位 | 一句话判断依据 |
|---|---|---|
| `DeepSeek-V4-Pro` | 旗舰档 | 复杂改写、方案设计、长输出；**难一点的活就切它** |
| `DeepSeek-V4-Flash` | 轻快档 | 日常问答与批量跑量；**单价低、并发友好，是默认档** |
| `DeepSeek-V3.2` | 通用档 | 摘要、结构化抽取、通用对话；稳且均衡，不想纠结就选它 |
| `DeepSeek-R1-Distill-Qwen-32B` | 推理档 | 数学、逻辑、需要逐步思考的题；**先花 token 想再答，记得给足 `max_tokens`** |

### 4.3 按用途选哪个

| 你要做什么 | 建议用 | 为什么 |
|---|---|---|
| 日常问答 / 客服话术 / 打标 | `DeepSeek-V4-Flash` | 快、便宜，量大不心疼 |
| 高难推理 / 数学逻辑 / 逐步求解 | `DeepSeek-R1-Distill-Qwen-32B` | 思维链换准确率，这类题值得多花 token |
| 长文总结 / 长稿改写 / 报告起草 | `DeepSeek-V4-Pro` | 上下文把握更好，长输出不散 |
| 代码生成 / 代码解释 / 重构 | `DeepSeek-V4-Pro` | 复杂改动的首选 |
| 批量跑量（几千上万次短调用） | `DeepSeek-V4-Flash` | 单价低，总账可控 |
| 通用稳妥、什么都接一点 | `DeepSeek-V3.2` | 均衡档，不用逐场景调 |

**默认策略：日常全走 `DeepSeek-V4-Flash`，只有判断「这条答不好会返工」时才切 `DeepSeek-V4-Pro`。**
这一条能省掉大部分预算，见 `通用说明.md` 的成本一节。

### 4.4 同场其它值得一起用的模型

同一个 Key、同一个 base_url，换 `model` 就能把下面这些一起用起来（编码同样逐字照抄）：

| 编码 | 补的是哪块能力 | 典型用法 |
|---|---|---|
| `Qwen3-VL-30B-A3B-Instruct` | **视觉理解** | 截图问答、票据与表单识别、图里取字段 |
| `Kimi-K2.6` | **超长文** | 整本稿件、长报告一次读完再总结 |
| `Qwen3-Coder-Next` | **代码补强** | 大仓改动、跨文件重构时和 `DeepSeek-V4-Pro` 交叉验证 |
| `Hunyuan-MT-Chimera-7B` | **翻译** | 多语种互译、字幕本地化 |
| `ERNIE-5.0-Thinking` | **深度思考** | 难题换一条线路再答一遍，取更稳的结果 |
| `MiniMax-M3` | **长文本创作** | 长篇连载、长文案的另一种文风 |

> 选型不要背表。**先 `GET /api/v1/models` 看当前在架，再按上表挑一个跑三条真实请求对比效果**，
> 效果和价格都满意就固定下来。

## 五、常用参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | **是** | 用 `GET /api/v1/models` 返回的 `model_code` |
| `messages` | array | **是** | `[{"role": ..., "content": ...}]`，role 取 `system` / `user` / `assistant` |
| `temperature` | number | 否 | 采样温度，越高越发散。抽取 / 分类用 0~0.3，创作 0.7~1.0 |
| `max_tokens` | integer | 否 | 最大生成 tokens，**同时是控成本的主旋钮**；推理模型不低于 256 |
| `stream` | boolean | 否 | `true` 走 SSE 流式 |
| `top_p` | number | 否 | 核采样，一般与 `temperature` 二选一调，不要同时大动 |

### 为什么说 `max_tokens` 是主旋钮

文本按**点数 / 百万 tokens** 计费，输出部分按实际生成量算。`max_tokens` 不是「预扣这么多」，
而是**给这次生成画一条上限**：上限给大了，模型在开放式问题上就可能一路写下去，费用跟着涨；
上限给得太小，又会把正文挤掉（见第八节）。判断依据很简单——
**你知道答案大概多长，就把上限卡在它的 1.5 倍左右**，别一律给 4096。

## 六、流式（SSE）

`stream: true` 时返回 `Content-Type: text/event-stream`，响应体是一行行 `data: {...}`，
以 `data: [DONE]` 结束。**取增量文本的路径是 `choices[0].delta.content`（不是 `message.content`）**
—— 这一条写错的表现是「什么都不打印」，很多流式接不通都是这个原因。

```python
import json, urllib.request

key = "sk-你的key"
body = {
    "model": "DeepSeek-V4-Flash",
    "stream": True,
    "max_tokens": 512,
    "messages": [{"role": "user", "content": "用三句话讲讲流式输出的好处"}],
}
req = urllib.request.Request(
    "https://api.a7w.cn/api/v1/chat/completions",
    data=json.dumps(body).encode("utf-8"),
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as resp:
    for raw in resp:                       # 逐行读 SSE
        line = raw.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        chunk = json.loads(payload)
        piece = chunk["choices"][0]["delta"].get("content")   # 注意：delta，不是 message
        if piece:
            print(piece, end="", flush=True)
```

用 SDK 时同一件事更短：

```python
stream = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "写一个 Python 快排"}],
    stream=True,
)
for chunk in stream:
    piece = chunk.choices[0].delta.content or ""   # 可能为 None，先兜底
    print(piece, end="", flush=True)
```

三个实现要点：

1. **每个 chunk 的 `content` 都可能为 `null`**（例如末尾只带 `finish_reason` 的那一片），先判空再拼。
2. **不要靠超时判结束**，读到 `data: [DONE]` 才是正常收尾。
3. **流式与非流式同价**，所以选流式只看体验（边生成边显示）和首字延迟，不用为价格纠结。

## 七、响应结构

非流式响应与 OpenAI 的结构一致，读 `id` / `model` / `choices` / `usage` 四个字段即可：

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

| 字段 | 怎么用 |
|---|---|
| `choices[0].message.content` | 正文，**可能为 `null`**，代码要容错 |
| `choices[0].finish_reason` | `stop` 是正常结束；`length` 表示撞到了 `max_tokens` 上限 |
| `usage` | 本次用量，核对预算就靠它 |
| `model` | 回显的模型名，**已被规范成小写**，别拿它做精确匹配 |

> 平台可能在 OpenAI 结构外再包一层 `{code, msg, data}`。解析时先看有没有 `choices`，
> 没有再往 `data` 里找一层；两者都没有时，**把原始响应原样落盘**再排查，不要静默丢数据。

## 八、推理模型的实测细节（重点）

DeepSeek 的推理型号会**先花 token 产出思维链，再给正文**。不理解这一点，会以为接口坏了。
以下是真实请求跑出来的行为：

### 8.1 `max_tokens` 太小，正文会是 `null`

| `max_tokens` | 实测结果 |
|---|---|
| `8` | `content` 为 **`null`**，`finish_reason` 为 **`length`** —— token 全被思维链吃掉，正文一个字没写 |
| `256` | 正常返回正文 |

所以：

- **看到 `content: null` 且 `finish_reason: "length"`，先把 `max_tokens` 调大**，这是唯一要做的事。
- **推理型号的 `max_tokens` 起步给 256**；正式业务给 512~1024 更稳。
- 代码里对 `content` 一律按「可能为 None」处理，别假定它是字符串。

### 8.2 思维链字段名有两条线路，两个都要取

实测中，思维链分别出现在 `reasoning` 与 `reasoning_content` 两个字段名下（不同线路不一样）：

```python
msg = resp.choices[0].message
thinking = (
    getattr(msg, "reasoning", None)
    or getattr(msg, "reasoning_content", None)
    or ""
)
# 字典写法同理：msg.get("reasoning") or msg.get("reasoning_content")
```

**只取一个字段的后果是「有时能拿到思考内容、有时拿不到」**，而且很难复现。
两个都取，成本只是多一行。

### 8.3 响应里的 `model` 会被规范成小写

请求 `DeepSeek-V4-Flash`，响应里回来的 `model` 是 `deepseek-v4-flash`。
**不要拿响应的 `model` 做精确匹配**（路由判断、日志归类、缓存键都别用它），
要比对就统一转小写再比。

## 九、多轮对话与上下文裁剪

`messages` 是**全量**发上去的，**历史越长，每次调用越贵、也越慢**。做法：

| 场景 | 做法 |
|---|---|
| 短会话（两三回合） | 原样带上全部历史即可 |
| 长会话（十几轮以上） | **只带最近 N 轮**（N 取 6~10）**+ 一条 system 提示** |
| 需要长期记忆的会话 | **先把早期历史摘要成一段文字**，作为 system 或首条消息带上，再拼最近几轮原文 |
| 固定知识（人设、规则、字段定义） | 放 `system`，但**写短**：它每次请求都计费 |

判断依据：**裁剪的目标不是「不丢信息」，而是「不重复付钱」。**
被裁掉的历史如果还重要，就摘要成一句话，而不是原样留着。

```python
# 只带最近 8 条 + 系统提示的裁剪骨架
messages = [{"role": "system", "content": "你是一个简洁的中文客服助手"}] + history[-8:]
```

## 十、与「应用任务」的边界

这是两条完全不同的入口，**选错是最高频的踩坑**：

| | 模型网关 | 应用任务 |
|---|---|---|
| 路径 | `POST /api/v1/chat/completions` | `POST /api/v1/apps/<应用代号>/<接口代号>` |
| 入参 | `messages` 数组 | 业务参数（`text` / `image_url` / `audio_url` …） |
| 返回 | **同步**，直接给 `choices` | **多为异步**，返回 `task_id` |
| 典型用途 | 对话、写作、翻译、分类、抽取、代码 | 出图、出视频、配音、数字人、音乐、超分 |
| 查结果 | 不用查，本次响应就是结果 | `GET /api/v1/tasks/<task_id>` |

三条硬记忆：

- **模型网关没有 `task_id`。**
- **应用任务不吃 `messages` 数组。**
- 应用任务的两个代号**都取自线上返回的 `code` 字段**（应用代号用下划线，`voice_tts` 而不是 `voice-tts`），
  **绝对不要用 `endpoint_path` 字段去拼 URL**。

## 十一、排错

| HTTP | code | 什么意思 | 怎么查 |
|---|---|---|---|
| 401 | `auth_failed` | Key 缺失或无效 | 重新复制 Key；确认 `Bearer ` 前缀与那个空格；`python3 scripts/a7w.py whoami` 复核 |
| 402 | `insufficient_points` | **账号**点数余额不足 | 这是真没钱，去充值；错误里会带本次所需点数。`GET /api/v1/user/balance` 看余额 |
| 402 | `key_quota_exceeded` | **这把 Key 自己的**额度打满 | **别去充值**。到用户中心调高该 Key 的 quota，或换一把 Key |
| 403 | `permission_denied` | 该 Key 无权调用这个模型 | 与余额无关。检查模型是否已开通、Key 是否被限权、IP 白名单是否匹配 |
| 404 | `not_found` | 模型不存在或路径不对 | 先怀疑 `/v1` 层数（是不是 `/api/v1/v1/`）；再用 `GET /api/v1/models` 核对 `model_code` 拼写与大小写 |
| 429 | `queue_limit_exceeded` | 排队任务已达上限 | 降并发，指数退避后重试；批量任务改成有限并发（3~5 路） |
| 5xx | `server_error` | 服务异常 | 退避重试（1s → 2s → 4s → 8s）；持续失败就换模型或换线路 |
| 400 | `invalid_request` | 参数缺失或格式错误 | 核对 `model` / `messages` 是否都在，role 是否写成了别的值 |

**两个 402 一定要分清**：一个是账号没钱，一个是这把 Key 的额度满了。
分不清的代价是**去充一个根本不需要充的账户**。

### 重试与重复计费

| 情况 | 重试吗 | 说明 |
|---|---|---|
| 400 / 401 / 402 / 403 / 404 | **不重试** | 重试只是浪费请求，先把参数、权限、余额修好 |
| 429 / 5xx | 重试 | 指数退避 + 抖动 |
| 请求超时、没收到响应 | **先确认再决定** | 同步接口重发前先看余额与用量变化；异步任务先拿 `task_id` 查状态 |

包内 `scripts/a7w.py` 已经把这套策略编进去了：**网络类错误与 5xx 退避重试 4 次，4xx 是业务错误不重试**。

### 三条自检命令

```bash
# ① Key 通不通、能用多少插件
python3 scripts/a7w.py whoami

# ② 当前在架模型（编码以此为准）
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"

# ③ 最近的用量，核对预算
python3 scripts/a7w.py points
```

计费口径、Key 管理与异步任务机制见 `通用说明.md`。

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
