# 让聊天机器人用大模型回话

这是本包的核心文档。目标一句话：

> **机器人收到群消息 → 调 `api.a7w.cn` 的 OpenAI 兼容接口拿到回复 → 把回复发回原会话。**

三步都通了，你的机器人就从「关键词复读机」变成了「真的会聊」。下面按三种接法各给一套完整可跑的示例，再补机器人侧必须处理的工程问题。

## 一、整体链路

```
群消息 ──▶ 机器人框架 ──▶ ① 取文本、去重、判断要不要回
                            │
                            ▼
                    ② POST https://api.a7w.cn/api/v1/chat/completions
                       Authorization: Bearer $A7W_API_KEY
                            │
                            ▼
                    ③ choices[0].message.content 发回群里
```

**关键点：你的机器人只需要一个 Key、一个地址。** 75 个模型的差别只在 `model` 这个字符串上 —— 今天用 `DeepSeek-V4-Flash`，明天想换 `Qwen3.6-Flash`，改一个值就行，不用重新注册、不用改鉴权、不用换账单。

## 二、接法一：curl

最短的验证路径。先用它确认 Key、地址、模型名三件事都对，再去写机器人代码。

```bash
export A7W_API_KEY=sk-你的key

curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [
      {"role": "system", "content": "你是群里的助手，回答简短、口语化，不超过 80 字。"},
      {"role": "user", "content": "今天天气怎么样"}
    ],
    "max_tokens": 256,
    "temperature": 0.8
  }'
```

返回里取 `choices[0].message.content`，那就是要发回群里的文本。

**流式（打字机效果）**，群里如果有「正在输入」体验需求就用这个：

```bash
curl -sS -N -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role": "user", "content": "讲个冷笑话"}],
    "stream": true,
    "max_tokens": 256
  }'
```

返回是 SSE，逐行 `data: {...}`，取增量文本的路径是 **`choices[0].delta.content`**（**不是** `message.content`），以 `data: [DONE]` 结束。

> **机器人不建议直接用流式发消息。** 多数聊天平台的发送接口是「一次发一条完整消息」，改成流式要不停地编辑同一条消息，很容易触发平台的风控与限频。**先把流式关掉，用非流式 + 一次性发送，稳得多。**

## 三、接法二：Python

### 3.1 `urllib` 零依赖写法（推荐给机器人）

只用标准库，**不需要安装任何第三方包 任何东西** —— 机器人部署环境往往很干净，少一个依赖就少一类故障。

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""群机器人调用大模型的最小实现：只用 Python 标准库。"""

import json
import os
import urllib.error
import urllib.request

API = "https://api.a7w.cn/api/v1/chat/completions"
KEY = os.environ.get("A7W_API_KEY", "").strip()

SYSTEM_PROMPT = "你是群里的 AI 助手。回答简短、口语化，不超过 80 字，不要用 Markdown 标题。"


def ask(prompt, model="DeepSeek-V4-Flash", history=None, timeout=60):
    """发一句话给模型，返回回复文本。失败时返回一句友好提示，不抛异常。"""
    if not KEY:
        return "（机器人还没配 API Key，请管理员检查环境变量 A7W_API_KEY）"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)          # 只带最近几轮，见第六节
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 256,                # 控成本的主要旋钮
        "temperature": 0.8,
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        API, data=body, method="POST",
        headers={
            "Authorization": "Bearer " + KEY,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        code = e.code
        if code == 402:
            return "（额度用完了，请联系管理员充值或调高 Key 额度）"
        if code == 429:
            return "（问的人太多啦，稍等一下再问我）"
        if code == 403:
            return "（这个模型当前没开通，请联系管理员）"
        return "（模型服务暂时不可用，错误码 %s）" % code
    except Exception:
        return "（网络不太好，稍后再试）"

    choices = payload.get("choices") or []
    if not choices:
        return "（模型没有返回内容，请稍后再试）"

    message = choices[0].get("message") or {}
    # 推理模型的 content 可能是 null，必须容错
    content = message.get("content") or ""
    if not content:
        reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
        content = reasoning.strip() or "（这次没想出答案，再问我一次）"
    return content.strip()


if __name__ == "__main__":
    print(ask("用一句话介绍你自己"))
```

**这个函数已经处理了机器人侧最要命的四件事：**

| 处理 | 为什么 |
|---|---|
| `max_tokens=256` | 推理模型给小了正文会是空的 |
| `content or ""` | 推理模型的 `content` 可能是 `null` |
| `reasoning` / `reasoning_content` 都取 | 不同线路思维链字段名不一样 |
| 异常包装成友好文案 | 机器人不能因为一次 API 报错就沉默或崩掉 |

### 3.2 `openai` SDK 写法

如果你已经在用 SDK、不介意多一个依赖：

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key=os.environ["A7W_API_KEY"],
)

resp = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[
        {"role": "system", "content": "你是群里的 AI 助手，回答简短口语化。"},
        {"role": "user", "content": "今天有什么新鲜事"},
    ],
    max_tokens=256,
    timeout=60,
)
print(resp.choices[0].message.content)
```

流式：

```python
stream = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "讲个冷笑话"}],
    max_tokens=256,
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="", flush=True)
```

**两种写法唯一的区别就是 `base_url` 和 `api_key`。** 其余代码与接 OpenAI 时完全一样。

> **机器人优先用 3.1 的 `urllib` 写法。** 只差十几行代码，换来的是「换台机器就能跑」，不用管 pip 源、不用管依赖冲突。

## 四、接法三：包内零依赖客户端

包里自带 `scripts/a7w.py`，只用 Python 标准库（Python 3.8+），**不内嵌任何密钥**。Key 读取顺序是 `--key` 参数 → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。

```bash
# 验证并保存 Key
python3 scripts/a7w.py login --key sk-xxx

# 看当前 Key 能用的插件数
python3 scripts/a7w.py whoami

# 列出全部插件（21 个）
python3 scripts/a7w.py apps

# 看某插件的接口与参数
python3 scripts/a7w.py schema voice_tts

# 调用接口（遇到 task_id 会自动轮询到终态，间隔 5 秒，上限 30 分钟）
python3 scripts/a7w.py call <app> <api> --body '{"k":"v"}' [--no-wait] [--out 文件]

# 查异步任务
python3 scripts/a7w.py task <task_id>

# 看最近的用量
python3 scripts/a7w.py points
```

**它的定位是应用任务**（出图、语音、视频）**，所以子命令里没有 `chat`。** 模型对话走第二、三节的写法，机器人要发图 / 发语音时再用它 —— 见第八节。

两个实用特性：

- `call` 遇到返回里有 `task_id` 会**自动轮询到终态**，不用自己写轮询循环。
- 客户端对**网络类错误与 5xx 退避重试 4 次**，4xx 是业务错误不重试（不会白烧请求）。

## 五、模型选型表

| 机器人在干什么 | 用哪个编码 |
|---|---|
| **日常闲聊、默认回复** | `DeepSeek-V4-Flash` |
| **群内问答、快问快答** | `Qwen3.6-Flash` |
| **长文总结、长文档解读** | `Kimi-K2.6` |
| **翻译** | `Hunyuan-MT-Chimera-7B` |
| **代码助手** | `Qwen3-Coder-Next` |
| 难题攻坚 | `DeepSeek-V4-Pro` |
| 读图（群里发截图问问题） | `Qwen3-VL-30B-A3B-Instruct` |
| 深度思考 | `ERNIE-5.0-Thinking` |

**选型方法论：给机器人配一个「默认模型」+ 一个「降级模型」，就够用了。**

```
默认：DeepSeek-V4-Flash     ← 便宜、快、中文稳，90% 的群消息都用它
降级：DeepSeek-V4-Pro       ← 默认模型报错时切过去，保证机器人永远有反应
```

**不要按关键词给不同群消息分发不同模型。** 那样维护成本远大于收益 —— 先把默认模型定下来，只有在「长文总结效果不够」这类明确反馈出现时，才为那一个场景单独指定模型。

## 六、机器人侧的工程要点

这一节是「能跑」和「能长期稳定跑」的分界线。

### 6.1 多轮上下文怎么裁剪

**不要把所有历史都发上去。** 两个原因：token 消耗随轮数线性增长；太长的上下文会让模型跑偏。

推荐做法：

```python
MAX_TURNS = 6          # 只保留最近 6 轮（12 条消息）
MAX_CHARS = 4000       # 或按字符数封顶

def trim(history):
    """只留最近 N 轮，并保证第一条是 user（避免奇偶错位）。"""
    h = history[-MAX_TURNS * 2:]
    while h and h[0]["role"] != "user":
        h.pop(0)
    # 再按字符数兜底
    while h and sum(len(m["content"]) for m in h) > MAX_CHARS:
        h.pop(0)
        while h and h[0]["role"] != "user":
            h.pop(0)
    return h
```

三条经验：

| 做法 | 效果 |
|---|---|
| **只带最近 6 轮** | 覆盖绝大多数「刚才说的那个」类追问 |
| **系统提示固定在第一条** | 人设与规则每次都生效 |
| **上下文里塞一份「对话摘要」** | 超长会话时用摘要替代早期原文，比全丢更好 |

会话状态按群 / 按用户分别存（`{chat_id: history}`），并**定期清理** —— 否则机器人跑一个月，内存里全是历史。

### 6.2 并发与 429

机器人的并发模型和 Web 服务不一样：**同一个群里的话是天然串行的**（大家按顺序说），但**不同群之间会并发**。

| 场景 | 做法 |
|---|---|
| **同一个群** | **串行**。同一个会话同时发两个请求，上下文会错乱，回复也会乱序 |
| **不同群** | 可以并发，但**设全局并发上限（3~5）** |
| **收到 429** | 指数退避 + 抖动：1s → 2s → 4s → 8s，上限 5 次 |
| **超时** | 同样退避重试；两次都失败就回一句「稍后再问我」 |
| **4xx** | **不重试**。参数、权限、余额类问题重试只是浪费请求 |

```python
import random, time

def with_retry(fn, attempts=4):
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            if i == attempts - 1:
                raise
            if getattr(e, "code", None) in (400, 401, 402, 403, 404):
                raise                      # 业务错误，重试没意义
            time.sleep((2 ** i) + random.random())
```

**同群串行的实现方式**：给每个 `chat_id` 配一把锁（asyncio 里用 `asyncio.Lock()` 放进字典；多线程里用 `threading.Lock()`）。这是最简单也最有效的做法。

### 6.3 消息去重与幂等（同一 `message_id` 只回一次）

聊天平台普遍会**重投消息**：网络抖动、机器人重启、ACK 超时，都会让你收到同一条消息两次。不去重，机器人就会回两遍。

**规则：用平台给的 `message_id` 做去重键，处理过的直接跳过。**

```python
import time

_seen = {}          # message_id -> 处理时间
TTL = 600           # 10 分钟

def already_handled(message_id):
    now = time.time()
    # 顺手清理过期记录，防止字典无限增长
    for k in [k for k, t in _seen.items() if now - t > TTL]:
        _seen.pop(k, None)
    if message_id in _seen:
        return True
    _seen[message_id] = now
    return False
```

三个要点：

1. **去重键一定是平台消息 ID**，不要用消息文本 —— 群里「哈哈哈哈」会重复出现。
2. **去重要在处理之前做**，不要等回复完了才记。
3. **TTL 别设太短**（建议 10 分钟），平台的重复投递可能隔几分钟才来。

如果你的机器人框架支持「消息队列 + 消费确认」，**在发送回复成功之后再 ACK**，能从源头减少重投。

### 6.4 回复太长怎么分段

模型可能一次吐几百字，多数聊天平台对单条消息有长度上限。

```python
def split_reply(text, limit=800):
    """按段落切分，尽量不切断句子。"""
    if len(text) <= limit:
        return [text]
    parts, buf = [], ""
    for para in text.split("\n"):
        if len(buf) + len(para) + 1 > limit:
            if buf:
                parts.append(buf.rstrip())
            while len(para) > limit:            # 单段就超长，硬切
                parts.append(para[:limit])
                para = para[limit:]
            buf = para + "\n"
        else:
            buf += para + "\n"
    if buf.strip():
        parts.append(buf.rstrip())
    return parts
```

**更好的做法是别让它长。** 在 system prompt 里直接写死：「回答不超过 80 字」。**控住长度比事后分段便宜得多。** 真正需要长文时（总结、翻译），再分段发，并在第一段前面加一句「（长文分 N 条发）」让人有预期。

### 6.5 Markdown 与换行在各平台的差异

**这是最容易让「好好的回复」变成「一坨乱码」的地方。**

| 平台类型 | Markdown | 换行 | 建议 |
|---|---|---|---|
| 支持 Markdown 的（部分 IM、Telegram） | 支持一部分 | `\n` 基本可用 | 可以用 `**加粗**`、代码块 |
| 不支持的 IM（多数国内群聊） | **不支持**，会原样显示 `**` 和 `##` | 需要看平台，有的要 `\n`，有的要 `<br>` | **纯文本输出**，用 emoji 或「」做层次 |
| 网页聊天窗口 | 通常支持 | `\n` + CSS `white-space` | 可以用 Markdown |

**最稳的做法：在 system prompt 里明确禁止 Markdown。**

```
你是群聊助手。输出纯文本，不要使用 Markdown 语法（不要用 #、*、`、表格）。
分段用空行，列举用「1. 2. 3.」。
```

这样无论发到哪个平台都不会乱。如果确定目标平台支持 Markdown，再单独放开。

### 6.6 超时与降级

| 参数 | 建议值 | 理由 |
|---|---|---|
| 请求超时 | **60 秒**（推理模型 120 秒） | 太短会把正常的慢响应切成失败 |
| 重试次数 | 2~4 次 | 再多只是拖长用户等待 |
| 降级模型 | `DeepSeek-V4-Flash` | 主模型失败时切过去 |

**降级逻辑**：

```python
MODELS = ["Qwen3.6-Flash", "DeepSeek-V4-Flash"]   # 依次尝试，最后一个兜底

def ask_with_fallback(prompt, history=None):
    for m in MODELS[:-1]:
        try:
            return ask(prompt, model=m, history=history, timeout=60)
        except Exception:
            continue
    return ask(prompt, model=MODELS[-1], history=history, timeout=120)
```

三条注意：

1. **只在连接失败 / 5xx / 超时 / 429 时降级。** 401、402、403、404 换模型一样失败，降级只会把真实原因盖住。
2. **降级要记日志**（原模型 → 实际模型 → 触发原因）。不记日志，你分不清「回复变差了」是因为降级还是因为别的。
3. **降级不是免费的** —— 切到更强的模型，点数也更高。降级链放 2~3 个就够。

### 6.7 群聊里 @ 机器人才触发

群里最容易被踢的功能就是「机器人抢话」。规则：

| 情况 | 要不要回 |
|---|---|
| **被 @ 了** | **回** |
| 私聊 | 回 |
| 未 @ 但消息以机器人名字开头 | 回（相当于被叫了） |
| 普通群聊，没 @ | **不回**（除非该群明确开了「随便聊」模式） |
| 机器人自己发的消息 | **绝对不回**（否则会自己跟自己聊起来） |
| 其他机器人发的消息 | 不回（避免两个机器人互相刷屏） |

```python
def should_reply(event, bot_id, bot_name):
    if event.sender_id == bot_id:
        return False                                    # 自己发的，不回
    if event.is_private:
        return True
    if bot_id in event.mentions:
        return True
    if event.text.startswith(bot_name):
        return True
    return False
```

再补两条实战规则：

- **每个群设一条冷却线**：同一群 3 秒内最多回一条，防刷。
- **给群管理员一个开关**：某些群只想让机器人安静待着。宁可少回，不要抢话。

### 6.8 敏感词与内容合规自检

机器人是**你的账号在说话**，内容不合规的后果由账号承担。建议三层把关：

| 层 | 做什么 |
|---|---|
| **入口层** | 群消息里出现明显的黑灰产、违法内容 → 直接不理，不送模型 |
| **提示层** | system prompt 里写明「拒绝生成违法、色情、暴力、欺诈类内容」 |
| **出口层** | 模型回复发出前，过一遍你自己的关键词表；命中就替换成「这个问题我不方便回答」 |

**出口层的过滤表要可配置、可热更新**，不要硬编进代码 —— 平台规则会变，你不想为了改一个词就重启机器人。

另外，在群里回复时**加一个「AI 生成」的标识**（例如回复末尾带「—— AI 助手」），既符合多数平台的内容标注要求，也让人知道这不是真人在说话。

### 6.9 把 Key 放环境变量，不要写进代码

**Key 等同于你的余额。** 拿到 Key 的人就能花你的点数。

| 做 | 不要做 |
|---|---|
| `os.environ["A7W_API_KEY"]` | `KEY = "sk-xxxx"` 写死在代码里 |
| 服务器的环境变量 / secret 管理 | 提交进版本库 |
| `.env` + `.gitignore` | 放进配置文件后一起打包分发 |
| 每台机器人一把独立 Key | 所有机器共用一把主 Key |

**多机器人部署时特别重要**：给每台机器人 / 每个群机器人一把独立 Key，各自设 quota。这样某个机器人跑飞了，损失被限制在那把 Key 的上限里，也不会影响其他机器人。

> **Key 一旦外泄，立刻到用户中心删除并重建。** 删除比重置快，别犹豫。

## 七、计费与控成本

**计费口径**：

- **1 元 = 100 点，1 点 = 0.01 元。点数永久有效。**
- 文本按**点数 / 百万 tokens**，**输入与输出分别计价，流式与非流式同价**。
- **先冻结、后结算**；**调用失败直接退款**；异步任务失败冻结点数全额退回。
- 平台同时给两套价格字段：`fixed_price` / `input_price` 是公示标准价；**`tenant_*` 是你所在租户的实际结算价**。做预算一律用 `tenant_*`，最终以账号实际扣费为准。

**实测参考**：`DeepSeek-V4-Flash` 一次普通问答约 **0.74 ~ 0.99 点**。

**机器人控成本四招**：

| 招 | 做法 | 省在哪 |
|---|---|---|
| **压 `max_tokens`** | 闲聊 256、总结 1024 | 输出 token 是主要成本 |
| **精简 system prompt** | 人设别写小作文 | 系统提示每次都随请求计费 |
| **长对话做摘要** | 超长会话用摘要替代早期原文 | 输入 token 不随轮数爆炸 |
| **给每个群设配额** | 每群每日点数上限，超了就只读不回 | 防止某个群刷爆 |

**给每个群设配额的具体做法**：本地维护 `{chat_id: (日期, 已用点数)}`，超过阈值就回一句「今天这个群的额度用完了，明天再聊」。这样既能服务好，也不会被单个群拖垮预算。

**对账**：每天看一眼 `GET /api/v1/tasks` 或 `python3 scripts/a7w.py points`，扫一遍异常消耗 —— 个位数点数正常，几百点的要查来源。

## 八、不止文字：同一把 Key 还能发图、发语音、转写语音

机器人不只能回文字。用**同一把 Key**，走应用任务入口就能发图、发语音、把群里的语音转成文字。

**路径规则（必记）**：

```
POST https://api.a7w.cn/api/v1/apps/<应用代号>/<接口代号>
```

三个铁律：

1. 两个代号都取自线上返回的 **`code`** 字段。
2. **绝对不要用 `endpoint_path` 字段拼 URL** —— 有些应用那个字段指的是内部另一套路由，照抄拼出来的地址打不通。
3. 应用代号用**下划线**（`voice_tts`），不是连字符（`voice-tts` 会 404）。

### 8.1 发图：`nano_banana`

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/nano_banana/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"一只戴墨镜的橘猫，扁平插画风格"}'
```

返回里带 `task_id`，轮询 `GET /api/v1/tasks/<task_id>` 拿图片 URL，再把 URL 发到群里。

### 8.2 发语音：`voice_tts`

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/voice_tts/tts" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"欢迎来到本群，有问必答"}'
```

同一应用下还有 `tts_async`（异步合成）、`tts_live`（实时合成）、`clone_voice`（音色克隆）。**音色克隆让你可以用自己的声音回话** —— 群里体验会好很多，但要先确认素材授权。

### 8.3 转写群里的语音：`voice_tts` 的 `stt`

群里有人发语音、机器人想「听懂」，先拿到音频的公网 URL，再调 `stt`：

```bash
python3 scripts/a7w.py call voice_tts stt --body '{"audio_url":"https://你的存储/语音.m4a"}'
```

> **`voice_tts` 的 `list_voices` 是 GET**，包内 `a7w.py call` 一律用 POST，所以查音色列表时用 `curl` 发 GET。

**用包内客户端做这些更省事** —— 异步任务会自动轮询到出结果：

```bash
# 出图
python3 scripts/a7w.py call nano_banana submit --body '{"prompt":"一只戴墨镜的橘猫"}'

# 合成语音
python3 scripts/a7w.py call voice_tts tts --body '{"text":"欢迎来到本群"}'
```

### 8.4 组合玩法

| 群里发生了什么 | 机器人可以做什么 |
|---|---|
| 有人发语音 | `voice_tts/stt` 转文字 → 大模型理解 → 文字回复 |
| 有人要图 | 大模型润色 prompt → `nano_banana/submit` 出图 → 发图 |
| 有人要听 | 大模型写稿 → `voice_tts/tts` 合成 → 发语音 |
| 有人发长文档 | `file_qa/parse` 解析 → 大模型总结 → 分段回复 |

**这些都在同一把 Key、同一份账单下。** 不需要为每一种能力再接一个平台。

## 九、排错表

### 平台错误码

| HTTP | code | 含义 | 怎么办 |
|---|---|---|---|
| 400 | `invalid_request` | 参数缺失或格式错误 | 核对 `messages` 结构与参数名 |
| 401 | `auth_failed` | API Key 缺失或无效 | 重新复制 Key，确认 `Bearer ` 前缀与空格 |
| 402 | `insufficient_points` | 账号点数余额不足 | 充值；错误里带本次所需点数 |
| 402 | `key_quota_exceeded` | 该 Key 自己的额度打满 | 调高该 Key 的 quota，**不用充值** |
| 403 | `permission_denied` | 该 Key 无权调用此模型 / 应用 | 检查模型是否已开通、Key 是否被限权 |
| 404 | `not_found` | 模型 / 应用 / 任务不存在 | 核对代码拼写；**先怀疑 `/v1` 层数** |
| 429 | `queue_limit_exceeded` | 排队任务已达上限 | 降并发，等队列消化后重试 |
| 5xx | `server_error` | 服务异常 | 退避重试；仍失败切降级模型 |

**两个 402 别搞混**：`insufficient_points` 是账号没钱（去充值）；`key_quota_exceeded` 只是这把 Key 的额度满了（去调 quota）。

### 机器人侧特有的问题

这四个是**平台错误码表里没有的**，但机器人上线后一定会遇到。

| 现象 | 真正的原因 | 怎么修 |
|---|---|---|
| **机器人完全没反应，日志里也没有请求记录** | **事件循环被阻塞**。同步的 `urllib` 调用写在 `async def` 里，把整个事件循环卡住了，连收消息都停了 | 把模型调用丢到线程池（`asyncio.to_thread` / `run_in_executor`），或者改用异步 HTTP 客户端。**这是机器人最容易出、也最难查的一类问题** |
| **响应超时（平台侧正常，机器人报超时）** | 超时设太短（30 秒常见），推理模型跟不上；或网络出口不稳 | 普通模型超时设 **60 秒**，推理模型 **120 秒**；失败后退避重试 2~4 次 |
| **同一条消息被回了两遍** | 平台重投消息，你没按 `message_id` 去重 | 加去重表（TTL 建议 10 分钟），**在处理之前就记下 `message_id`** |
| **上下文爆炸：越聊越慢、越聊越贵，最后报错** | 把整段历史每次都发上去，token 随轮数线性增长 | 只带最近 **6 轮**；超长会话用一份摘要替代早期原文；按字符数再兜一层 |

### 一张排错决策树

```
机器人不回话
├─ 日志里连「收到消息」都没有
│    → 事件循环被阻塞：同步 HTTP 调用没丢线程池
├─ 收到消息了，但没发请求
│    → @ 触发条件没命中 / 被去重表挡了 / 被冷却线挡了
├─ 发请求了，报 401
│    → 环境变量没注入到机器人进程（注意容器与 systemd 的环境隔离）
├─ 发请求了，报 404
│    → base_url 层数错了（是不是填成了 /api/v1 而框架又补 /v1）
├─ 发请求了，报 402
│    → 先去用户中心看余额：够 → 调 Key quota；不够 → 充值
├─ 发请求了，报 429
│    → 同群没串行 + 全局并发太高
├─ 拿到 200，但回复是空的
│    → max_tokens 太小（推理模型调到 256 以上），或解析取错了字段
├─ 回复发不出去
│    → 单条太长被平台拒；改成分段发送
└─ 回复重复了两遍
     → 没按 message_id 去重
```

## 十、上线前自检清单

- [ ] `curl` 直连 `/api/v1/chat/completions` 返回 200，才去改机器人代码
- [ ] `base_url` 是 `https://api.a7w.cn/api/v1`（框架自带 `/v1` 的用 `https://api.a7w.cn/api`），日志里没有 `/api/v1/v1`
- [ ] 模型编码从 `/api/v1/models` 现场拉取，没有抄文章里的旧名
- [ ] `max_tokens` 不低于 256；`content == null` 有容错；`reasoning` / `reasoning_content` 都取了
- [ ] 只带最近 6 轮上下文，system prompt 固定在第一条
- [ ] **同一个群串行**处理，全局并发不超过 5
- [ ] 429 与超时有指数退避；4xx 不重试
- [ ] 按 `message_id` 去重，TTL 10 分钟，去重在处理之前
- [ ] 长回复会分段；system prompt 里禁止了 Markdown（或已确认平台支持）
- [ ] 配了降级模型，且只在连接失败 / 5xx / 超时 / 429 时触发
- [ ] 只在被 @ 或私聊时回复；机器人自己的消息不回
- [ ] 出口层有敏感词过滤，且过滤表可配置
- [ ] Key 走环境变量，每个机器人一把独立 Key，各自设 quota
- [ ] 每个群设了每日点数配额，异常消耗有人看

## 十一、下一步

| 你要做的事 | 看哪份 |
|---|---|
| 注册、充值、创建 Key 并把 Key 配到机器人进程 | 本包 `SKILL.md` 的「三分钟跑通」 |
| 鉴权、计费口径、错误码全表、权限边界 | `通用说明.md` |
