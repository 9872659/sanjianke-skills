---
name: sanjianke-agent-memory
slug: sanjianke-agent-memory
displayName: Agent长期记忆库·跨会话用户偏好事实检索接入指南
description: "给 Agent 接一层跨会话长期记忆：对话里的偏好、事实、决定抽成条目存好，下一轮按用户/会话维度搜回来拼进提示词。含完整操作文档、作用域与检索参数表、向量模型配置与零依赖客户端。模型侧改一个 base_url 走 OpenAI 兼容网关即可。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "把长期记忆接进你的 Agent：对话里的事实、偏好、决定自动抽成条目存好，下一轮按用户 / 会话 / Agent 维度用自然语言搜回来拼进提示词，跨会话不必再让用户重复自我介绍。模型侧统一走 OpenAI 兼容网关 —— 只改一个 base_url，同一把 Key 调 75 个在架模型（DeepSeek、通义千问、智谱 GLM、Kimi、腾讯混元等国产为主，含 OpenAI / Google / xAI 国际主流），不必自己部署模型或买显卡。含作用域设计、写入节流、检索提准与真实计费口径。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 长期记忆
  - 向量检索
  - OpenAI兼容
---

# Agent 长期记忆库 · 跨会话记忆层接入

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

大模型本身没有记忆 —— 上下文一关，上次聊过的偏好、约束、决定全没了。
记忆层的活儿是：把「值得记住的事实」抽成结构化条目存好，下一轮用一句自然语言搜回来，
再拼进提示词。

**它的价值是把记忆从业务代码里摘出来**：不用自己设计记忆表结构、不用自己写
「这条新信息和旧记忆冲突了怎么办」的逻辑。而它背后要的那几次模型调用，
**换成 api.a7w.cn 的 OpenAI 兼容入口，就是一个 base_url 的事**。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **按 tokens 计费**（点数/百万 tokens，输入输出分别计价），1 元 = 100 点；记忆写入比普通问答多几次调用 |
| 要多久 | 同步链路，单次写入通常几秒；批次回填按量线性增长 |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端，或者直接用 `curl` / 任意 OpenAI SDK |
| 模型从哪来 | **一个 base_url + 一个 Key**，可调 75 个在架模型，换 `model` 就是换模型 |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`），填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：先用一条 curl 确认网关通

记忆层最终落到两次模型调用：一次抽取、一次问答。先确认这条链路能走通：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role":"user","content":"把这句话抽成一条记忆：用户偏好深色模式和 vim 键位"}]
  }'
```

成功返回体形如 `{"code":1,"msg":"success","data":{...choices...}}`。
拿到 `choices[0].message.content` 就是一次可用的抽取结果。

### 第三步：把记忆层的模型入口指向它

任何兼容 OpenAI 协议的框架 / SDK，只改两个字段：

```python
# 原来：base_url="https://api.openai.com/v1"
BASE_URL = "https://api.a7w.cn/api/v1"
API_KEY  = "sk-你的key"          # 同一把 Key 同时供抽取模型与向量模型使用
```

记忆层的三个角色都指向同一个入口：

| 角色 | 走哪个接口 | 怎么填 |
|---|---|---|
| **抽取模型**（把对话抽成事实） | `POST /api/v1/chat/completions` | `model` 填模型清单里的文本模型 |
| **回答模型**（拿记忆生成回复） | `POST /api/v1/chat/completions` | 可与抽取用不同模型，账单仍是同一份 |
| **向量模型**（embedding） | 由框架的 embedder 配置项指定 | 把 embedder 的 `base_url` 同样指向本网关 |

### 第四步：零安装客户端也能直接跑

```bash
python3 scripts/a7w.py whoami                       # 验证 Key
python3 scripts/a7w.py call chat completions \
  --body '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

> 换模型只需改 `model` 字符串：**不用换 base_url、不用换 Key、账单还是同一份**。
> 想拿当前可用清单，读 `GET /api/v1/models`，或跑 `python3 scripts/a7w.py apps`。

---

## 二、包里有什么

```
sanjianke-agent-memory/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 记忆接入指南.md          作用域设计、写入节流、检索提准、批量回填
│   ├── api-openai-compat.md    OpenAI 兼容入口：base_url、鉴权、参数、流式、错误码
│   ├── api-apps-tasks.md       应用任务入口：/api/v1/apps/<应用>/<接口> 与异步生命周期
│   ├── getting-started.md      注册、领 Key、配置、配额与白名单
│   └── 通用说明.md              权限、计费口径、排错
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

python3 scripts/a7w.py whoami                     # 验证 Key 与可用插件数
python3 scripts/a7w.py apps                       # 列出全部能力
python3 scripts/a7w.py call chat completions \
  --body '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

---

## 三、三种接入姿势

### 姿势 A：框架的配置项（最省事）

记忆类框架通常把「LLM 段」与「embedder 段」拆开配置，两段都指向同一个网关即可：

```json
{
  "llm": {
    "provider": "openai",
    "config": {
      "model": "DeepSeek-V4-Flash",
      "base_url": "https://api.a7w.cn/api/v1",
      "api_key": "sk-你的key"
    }
  },
  "embedder": {
    "provider": "openai",
    "config": {
      "base_url": "https://api.a7w.cn/api/v1",
      "api_key": "sk-你的key"
    }
  }
}
```

> 具体键名以你所用框架的当前版本为准：Python 侧常见下划线（`base_url`、`api_key`），
> TypeScript 侧常见驼峰（`baseUrl`、`apiKey`）。**值都是同一个网关地址与同一把 Key。**

### 姿势 B：只用 OpenAI SDK，自己管记忆读写

```python
from openai import OpenAI

client = OpenAI(base_url="https://api.a7w.cn/api/v1", api_key="sk-你的key")

def extract(text: str) -> str:
    """把一段对话抽成一条可长期保存的事实。"""
    resp = client.chat.completions.create(
        model="DeepSeek-V4-Flash",
        messages=[
            {"role": "system",
             "content": "从对话中抽出一条最值得长期记住的用户事实，只输出这一条。"},
            {"role": "user", "content": text},
        ],
    )
    return resp.choices[0].message.content

def answer(question: str, memories: list) -> str:
    """把检索回来的记忆拼进 system prompt 再回答。"""
    system_prompt = (
        "你在回答时优先参考以下长期记忆；没有相关信息就正常回答。\n"
        + "\n".join("- " + m for m in memories)
    )
    resp = client.chat.completions.create(
        model="Qwen3.7-Plus",          # 与抽取用不同模型，账单仍是同一份
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
    )
    return resp.choices[0].message.content
```

### 姿势 C：走应用任务入口

除了 OpenAI 兼容的大模型网关，平台还有一条应用任务入口，用于生成类能力
（语音、图像、视频、文档问答等 21 个应用）：

```bash
# 看有哪些应用
python3 scripts/a7w.py apps

# 看某个应用有哪些接口、参数与真实价
python3 scripts/a7w.py schema voice_tts

# 调用（异步接口客户端会自动轮询到结束）
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好世界"}'
```

**路径统一是 `/api/v1/apps/<应用代号>/<接口代号>`**，两个代号都取自接口返回的
`code` 字段（是下划线，不是连字符）。不要拿平台返回的 `endpoint_path` 去拼 URL。

---

## 四、记忆工程要点

### 作用域：先把「谁记得谁」定清楚

| 维度 | 典型取值 | 说明 |
|---|---|---|
| `user_id` | 用户 / 客户 ID | 最常用的隔离维度，必须与业务账号体系对齐 |
| `agent_id` | 角色名 | 同一系统里多个助手各记各的 |
| `app_id` | 应用名 | 多产品共用一套记忆服务时区分 |
| `run_id` | 会话 / 工单 ID | 只在本轮对话内有效的事实 |

**生成作用域 ID 的逻辑要收在一个函数里**，别在两处手写 —— 写入用 `user_id=A`
而检索用 `user_id=a`，结果就是「明明存了却搜不到」。

### 写入节流：记忆是要花钱的

每次写入都是一次模型调用。只在高信息量事件上写：
**偏好、决定、目标、新实体、约束条件**。日常寒暄、确认语、纠错重述都不要写。

### 检索提准

1. 检索必须带作用域过滤，别全库向量搜。
2. `top_k` 从 3 起步，够用就别加 —— 召回太多会污染提示词，也更贵。
3. 召回后按语义去重：加法式存储会让同一事实沉淀多条。
4. 抽取值与检索值用同一套口径：**同一个事实不要一半存原文、一半存抽取结果**。

### 批量回填：把历史工单变成用户画像

已有历史工单 / 聊天记录时，按 `user_id` 分组、逐条抽取、批量写入。
写法与并发建议见 `references/记忆接入指南.md`。

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **把 Key 写进代码** | 泄漏即等于余额泄漏 | Key 只从环境变量或 `~/.a7w/config.json` 读；**Key 等同于余额** |
| **两处作用域 ID 写法不一致** | 写入成功但检索返回空 | 作用域 ID 交给一个函数统一生成 |
| **每轮闲聊都写入** | 账单和延迟一起涨 | 只在偏好 / 决定 / 目标 / 新实体出现时写 |
| **把记忆库当业务数据库** | 精确聚合与统计给不出结果 | 精确查询交给 SQL；记忆层只做语义召回 |
| **把「本轮上下文」当「长期记忆」** | 加了一层记忆反而更绕 | 先确认需求是**跨会话**，再上记忆层 |
| **推理模型 token 先花在思维链上** | `max_tokens` 给小了会拿到空 `content` | 给推理类模型留足 `max_tokens`；思维链字段名在不同线路上是 `reasoning` / `reasoning_content` |
| **网络抖动丢掉已付费的调用** | 长任务轮询被重置连接 | 自带客户端已做退避重试；自己写代码时同样加幂等与重试 |

---

## 六、计费

| 动作 | 口径 |
|---|---|
| 记忆抽取（`chat/completions`） | 按 **tokens** 计，输入与输出分别计价 |
| 生成回复（`chat/completions`） | 同上；换模型即换单价 |
| 向量化 | 由 embedder 配置的模型决定 |
| 应用任务类接口 | 按各接口口径（点数/次、点数/分钟、点数/张等） |

- **1 元 = 100 点，1 点 = ¥0.01。**
- **先冻结、后结算**：调用失败直接退款，异步任务失败冻结点数全额退回。
- 平台同时给出标准价与租户实际结算价，**以账号里实际扣费为准**；
  每次返回的 `data.usage` 就是本次真实用量，可直接对账。
- 实时查规则：先 `python3 scripts/a7w.py apps` 拿应用清单，再逐个 `schema <app>` 读 `tenant_*`。

> **省钱三件事**：抽取用小模型、回答用好模型；只在高信息量事件上写入；
> `top_k` 别开大。三件事做完，记忆层的成本通常比业务本身的推理成本低一个量级。

---

## 七、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的模型网关与应用接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件与 `--json-file` 请求体 | 作为接口入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |
| 子进程 / 后台常驻 | 不申请 | 脚本执行完即退出，不注册服务、不常驻 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代数据合规审查**：把对话内容送去抽取之前，请自行确认符合你的隐私与合规要求
- **不承诺模型清单**：模型上下架频繁，**调用前先读一次模型清单**

---

## 关于这个 Skill

**作者亲测实操后发布，下载后可直接使用，自用商用都可以。**

所有 AI 能力都走 [算力集市 api.a7w.cn](https://api.a7w.cn/) —— 一把 API Key 打通
大模型、语音、图像、视频、数字人等全部算力，注册即送点数，按量计费、没有月费。

| 你可能想问 | 答案 |
|---|---|
| 要不要额外部署 | 不用。**下载本包即可使用**，不必去别处找源码 |
| 怎么开始 | 到 api.a7w.cn 注册领 Key → 填进 `A7W_API_KEY` → 一条命令跑起来 |
| 能不能商用 | 可以 |
| 遇到问题找谁 | 见文末「联系我们」，作者本人答疑 |

> 使用中碰到任何问题 —— 报错、效果不理想、想省钱、想批量 —— 都欢迎加微信聊。
> 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的示例。

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
