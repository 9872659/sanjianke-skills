---
name: sanjianke-agent-orchestrator
slug: sanjianke-agent-orchestrator
displayName: 有状态Agent编排·状态图断点续跑与人工审批接统一模型网关
description: "把 Agent 写成显式的状态图：每一步是一个节点、跳转关系是边，于是「暂停、恢复、回放到某一步、换一条分支重跑」都成了框架能力。模型侧走 OpenAI 兼容网关，把 base_url 指向 https://api.a7w.cn/ ，同一把 Key 调 75 个在架模型，工具调用与结构化输出都用同一条链路；包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) 。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "普通的 Agent 循环是一个 while：调模型、看有没有工具调用、执行工具、再调模型。写起来快，但进程一挂整轮对话白跑，想在第 5 步插个人工确认就得自己造一套状态机。把那个隐式循环变成显式的图之后，暂停、恢复、回放、换分支重跑都成了框架能力。模型这一头同样收成一处：base_url 指向 https://api.a7w.cn/ ，用同一把 Key 调用 75 个在架大模型（23 家厂商）与 21 个生成应用，工具调用与结构化输出走同一条链路，换 model 字符串就是换模型。包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) ，注册即送点数、按量计费、失败全额退回。含最小可用接法、多语言 SDK 对照、异步任务生命周期、点数计费口径、错误码排查手册与零依赖客户端。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 开发编程
  - AI
  - LLM
  - Agent
  - 模型网关
---

# 有状态 Agent 编排 · 能中断、能恢复、能记住

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

普通的 Agent 循环是一个 `while`：调模型、看有没有工具调用、执行工具、再调模型。
写起来快，但出了问题很难救——进程一挂，整轮对话白跑；想在第 5 步插个人工确认，
得自己造一套状态机。

把那个隐式的循环变成**显式的图**之后，「暂停」「恢复」「回放到某一步」
就都是框架能力，而不是你自己攒的胶水代码。
而模型这一头，**一个 `base_url` 就够**。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **1 元 = 100 点**；文本按点数/百万 tokens，Agent 多轮调用按轮累计 |
| 要多久 | 模型调用同步返回；长任务靠状态图跑，**任务查询免费** |
| 要装什么 | **除运行环境外什么都不用装**；包里自带零依赖客户端，或者直接用 `curl` |
| 能接什么 | **75 个在架模型**（含支持工具调用的）+ **21 个生成应用** |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：把 Agent 的模型指向 a7w

```
Base URL: https://api.a7w.cn/api/v1
Authorization: Bearer <你的 API Key>
```

```python
import os
from openai import OpenAI

client = OpenAI(base_url="https://api.a7w.cn/api/v1", api_key=os.environ["A7W_API_KEY"])
print(client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "你好"}],
).choices[0].message.content)
```

### 第三步：命令行验一次，再进图编排

```bash
curl -sS "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

**先在命令行确认这一层通了**，再上状态图。否则报错时你分不清是编排写错还是端点配错。

### 第四步：工具调用与结构化输出，模型要选对

Agent 的两个关键能力是**工具调用**和**结构化输出**，并不是每个模型都稳。
选之前先用模型清单确认，再用最小示例试一次：

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

| 用途 | 建议 `model` |
|---|---|
| 工具调用、多步 Agent | `DeepSeek-V4-Flash`、`Qwen3.6-Flash`、`GLM-5` |
| 结构化输出（JSON） | `Kimi-K2.6`、`Qwen3.7-Max` |
| 复杂推理 | `DeepSeek-R1-Distill-Qwen-32B`、`ERNIE-5.0-Thinking` |

> **推理模型的 `max_tokens` 要给足**：token 先花在思维链上，给少了 `content` 会是 `null`、
> `finish_reason=length`。思维链字段名是 `reasoning` 或 `reasoning_content`，两个都读。

### 第五步：需要生成产物时走应用任务

Agent 要出图、出视频、配音、做文档问答，走统一应用入口：

```bash
python3 scripts/a7w.py apps                    # 21 个应用
python3 scripts/a7w.py schema nano_banana      # 接口、参数、同步/异步
python3 scripts/a7w.py call nano_banana generate --body '{"prompt":"赛博朋克城市夜景"}'
```

异步任务提交后拿 `task_id`，轮询 `GET /api/v1/tasks/{task_id}`，
或提交时带 `callback_url` 让平台回调。**不要重复提交** —— 每次提交都可能产生费用。

---

## 二、包里有什么

```
sanjianke-agent-orchestrator/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── a7w-接入指南.md          base_url / 鉴权 / SDK 写法 / 模型切换
│   ├── 框架接入对照.md          不同语言与低代码平台的接法
│   ├── api-应用与任务.md        21 个生成应用、异步任务、回调
│   ├── 计费与错误码.md          点数口径、两套价格字段、错误码排查手册
│   ├── client-cli.md            a7w.py 的子命令、参数与退出码
│   └── getting-started.md       注册、领 Key、配置到本机
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 验证 Key 并保存到 ~/.a7w/config.json
python3 scripts/a7w.py login --key sk-你的key

# 看这把 Key 能用的插件数
python3 scripts/a7w.py whoami

# 列出全部应用与模型
python3 scripts/a7w.py apps

# 看某应用的接口与参数（含同步/异步标记）
python3 scripts/a7w.py schema file_qa

# 调接口（异步自动轮询）
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好世界"}'
```

---

## 三、把状态图接上统一模型层

状态图的每个模型节点都指向同一个端点，于是**换模型是一次参数变更，不是一次重构**：

| 环节 | 怎么配 |
|---|---|
| **模型节点** | `base_url = https://api.a7w.cn/api/v1`，`model` 从 `/api/v1/models` 选 |
| **工具调用** | 用支持 `tools` 的模型，按 OpenAI 格式传工具定义 |
| **结构化输出** | 用支持 JSON 输出的模型，把 schema 写进提示词或请求参数 |
| **生成产物** | 走 `POST /api/v1/apps/{app}/{api}`，拿到 URL 后落盘 |

好处是**账单只有一份**：多轮 Agent 调用、工具链上的模型切换、生成应用，
全部记在同一把 Key 上，对账只有一处。

---

## 四、多语言与低代码接法

Python / Node / 任意 HTTP 运行时都只填这三个字段：

| 字段 | 填什么 |
|---|---|
| API Base / Base URL | `https://api.a7w.cn/api/v1` |
| API Key / 令牌 | 你自己的 `sk-...` |
| Model | 从 `/api/v1/models` 里选 |

```js
import OpenAI from "openai";
const client = new OpenAI({ baseURL: "https://api.a7w.cn/api/v1", apiKey: process.env.A7W_API_KEY });
```

**状态图的持久化、中断、恢复是编排层的事，跟模型端点无关** ——
所以「换掉模型供应商」在这个架构里不会牵动你的断点续跑逻辑。

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **HTTP 200 就以为成功** | 调不存在的接口也返回 200 | 业务成败看 `code`：`1` / `200` 成功，`0` 失败 |
| **base_url 漏了 `/api/v1`** | 404 或鉴权异常 | 必须是 `https://api.a7w.cn/api/v1` |
| **用 `endpoint_path` 拼 URL** | 应用怎么调都打不通 | 一律用 `/api/v1/apps/{app}/{code}` |
| **应用代号写成连字符** | 404 | API 里用下划线：`nano_banana`、`voice_tts` |
| **拿 `name` 当接口代号** | 调用失败 | 字段名是 `code`，不是 `api` |
| **工具调用返回空** | Agent 不调工具 | 换支持工具调用的模型，并确认请求里按 OpenAI 格式传了 `tools` |
| **推理模型 `max_tokens` 给小了** | `content` 返回 `null` | 推理模型先花思维链 token，给足 `max_tokens` |
| **思维链字段读不到** | 拿不到推理过程 | `reasoning` 与 `reasoning_content` 两个名字都读 |
| **重复提交异步任务** | 扣两次钱 | 先记 `task_id`，用任务查询（免费）确认状态；网络超时也一样 |
| **做预算用公示标准价** | 预算算错 | 一律用 `tenant_*`（实际结算价） |

---

## 六、计费

- 计价单位是**点数**，**1 元 = 100 点、1 点 = ¥0.01**。点数永久有效，没有月费。
- 计费口径随能力不同：文本按**点数/百万 tokens**（输入输出分别计价，流式与非流式同价）、
  图像按**点数/张或参数档位**、视频生成与超分按**点数/秒**、数字人按**点数/次或时长**、
  TTS 与克隆按**点数/千字**、ASR 按**点数/分钟**、工具类按**点数/次**。
- **先冻结、后结算**：消费优先扣会员点数，不足再扣充值额度；
  **调用失败直接退款，异步任务失败冻结点数全额退回**，只有成功产出才按实际用量结算。
  上游调价会同步调整，但**不影响已充值的点数余额**。

| 字段 | 含义 |
|---|---|
| `fixed_price` / `input_price` | **标准价**，对外公示用 |
| `tenant_fixed_points` / `tenant_points_per_1k_input` | **你所在租户的实际结算价** |

做预算一律用 `tenant_*`。每次返回的 `data.usage.points_cost` 就是本次真实扣费，可以直接对账。

---

## 七、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的网关与应用接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 作为接口的素材入参与请求体 |
| 写入文件 | 仅在传入 `--out` 时 | 保存接口返回的 JSON 或下载产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量 `A7W_API_KEY` 或 `~/.a7w/config.json` 读取 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代内容合规审查**：生成内容的使用与发布责任由使用者承担
- **不保证可用性**：模型与应用上下架、限流与计费以站内为准

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
