---
name: sanjianke-llm-flow-builder
slug: sanjianke-llm-flow-builder
displayName: 拖拽式LLM流程编排·画布搭Agent接OpenAI兼容模型网关
description: "把「模型 + 提示词 + 检索 + 工具」画成流程图，连好线点运行就得到一个带界面的流程应用，同时对外暴露一套 HTTP 接口供程序调用。模型侧走 OpenAI 兼容网关，把 base_url 指向 https://api.a7w.cn/ 就能用同一把 Key 调 75 个在架模型，换 model 即换模型；包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) 。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "把「模型、提示词、知识库检索、工具调用」做成画布上的节点：连好线、点运行，立刻得到一个带界面的服务，同时对外暴露 HTTP 接口供程序调用——改流程不用改代码，业务同学在画布上调整分支和提示词，后端同学只负责调接口。模型提供方不再逐家注册：把 base_url 指向 https://api.a7w.cn/ ，用同一把 Key 调用 75 个在架大模型（23 家厂商，国产为主 + 国际主流）与 21 个生成应用，换 model 字符串就是换模型。包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) ，注册即送点数、按量计费、失败全额退回。含 OpenAI 兼容接入写法、多语言 SDK 对照、异步任务生命周期、点数计费口径、错误码排查手册与零依赖客户端。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - AI
  - LLM
  - 流程编排
  - 模型网关
---

# 拖拽式 LLM 流程编排 · 画布即应用

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

你想把一个想法做成能跑、能给同事用的 LLM 流程，但不想为了改一行提示词就重新发版。
那就把「模型、提示词、知识库检索、工具调用」做成画布上的节点：**连好线、点运行**，
立刻得到一个带界面的服务，同时对外暴露一套 HTTP 接口供程序调用。

它真正的价值是**改流程不用改代码**。而模型这一头，你只需要改一个 `base_url`。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **1 元 = 100 点**；文本按点数/百万 tokens，流式与非流式同价 |
| 要多久 | 文本同步返回；生成应用是异步任务，**查询免费** |
| 要装什么 | **除运行环境外什么都不用装**；包里自带零依赖客户端，或者直接用 `curl` |
| 能接什么 | 画布节点 + **75 个在架模型** + **21 个生成应用** |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`）：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：把模型节点指向 a7w

画布里添加一个模型节点，在**凭据 / API Base** 处填：

```
Base URL: https://api.a7w.cn/api/v1
API Key : <你自己的 sk-...>
Model   : 从 /api/v1/models 里选
```

**只有 `/api/v1` 这一层是网关**，SDK 会自己拼 `/chat/completions`；
裸 `curl` 就把全路径写全：

### 第三步：命令行验一次，别在界面上摸黑

```bash
curl -sS "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

命令行通了，界面里不通，问题就只剩「字段填错位置」这一种可能——排查范围直接砍一半。

### 第四步：多模型横评，改一个字符串就行

**换模型不用换 base_url、不用换 Key、账单还是同一份。** 实测 75 个在架模型 / 23 家厂商：

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

| 常见场景 | 建议 `model` |
|---|---|
| 中文通用、性价比优先 | `DeepSeek-V4-Flash`、`Qwen3.6-Flash` |
| 复杂推理 | `DeepSeek-R1-Distill-Qwen-32B`、`ERNIE-5.0-Thinking` |
| 长文与代码 | `Kimi-K2.6`、`Qwen3-Coder-Next` |
| 视觉理解 | `qwen3.6-plus`、`Qwen3-VL-30B-A3B-Instruct` |

> 这张表只是选型起点，**下发前用 `models` 接口核对一遍**。

### 第五步：生成类能力走应用任务

出图、出视频、配音、数字人、文档问答不在模型网关里，走统一应用入口：

```bash
python3 scripts/a7w.py apps                    # 21 个应用
python3 scripts/a7w.py schema nano_banana      # 接口、参数、同步/异步
python3 scripts/a7w.py call nano_banana generate --body '{"prompt":"赛博朋克城市夜景"}'
```

**路径永远是 `/api/v1/apps/<应用代号>/<接口代号>`。**
⚠️ 不要用平台的 `endpoint_path` 字段拼 URL —— 对某些应用那是错的上游路径。

---

## 二、包里有什么

```
sanjianke-llm-flow-builder/
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

## 三、流程与应用怎么分工

| 你要的 | 放在哪一层 | 怎么调 |
|---|---|
| 一段推理 / 一段文本 | 画布上的模型节点 | `POST /api/v1/chat/completions` |
| 一个生成产物（图 / 视频 / 语音 / 数字人 / 文档问答） | HTTP 请求节点打到应用入口，或由 Skill 脚本产出后回填 | `POST /api/v1/apps/{app}/{api}` |
| 一次要跑很久的任务 | 提交时带 `callback_url`，别把画布卡在轮询上 | `GET /api/v1/tasks/{task_id}` |

**两条链路共用同一套鉴权与同一份账单**，但形态不同：模型网关没有 `task_id`，
应用任务也基本不吃 `messages` 数组。先想清楚你要的是「一段结果」还是「一个产物」。

---

## 四、多语言与低代码接法

Python：

```python
import os
from openai import OpenAI

client = OpenAI(base_url="https://api.a7w.cn/api/v1", api_key=os.environ["A7W_API_KEY"])
print(client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "你好"}],
).choices[0].message.content)
```

Node / TypeScript：

```js
import OpenAI from "openai";
const client = new OpenAI({ baseURL: "https://api.a7w.cn/api/v1", apiKey: process.env.A7W_API_KEY });
```

在任何图形化配置里，对应的就是三个字段：

| 字段 | 填什么 |
|---|---|
| API Base / Base URL | `https://api.a7w.cn/api/v1` |
| API Key / 令牌 | 你自己的 `sk-...` |
| Model | 从 `/api/v1/models` 里选 |

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`** |
| **HTTP 200 就以为成功** | 不存在的接口也返回 200 | 业务成败看 `code`，404 时先确认是路径拼错还是接口问题 |
| **用 `endpoint_path` 拼 URL** | 某些应用怎么调都打不通 | 一律用 `/api/v1/apps/{app}/{code}` |
| **应用代号写成连字符** | 404 | API 里用下划线：`voice_tts`、`file_qa` |
| **画布节点挂在错误的层级** | 界面里报鉴权失败 | Base URL 必须含 `/api/v1`；漏了会把 `/chat/completions` 拼到错误位置 |
| **重复提交异步任务** | 扣两次钱 | 先记 `task_id`，用任务查询（免费）确认状态 |
| **推理模型 `max_tokens` 给小了** | `content` 返回 `null` | 推理模型先花思维链 token，给足 `max_tokens` |
| **思维链字段读不到** | 拿不到推理过程 | 字段名在不同线路上是 `reasoning` 与 `reasoning_content`，两个都读 |
| **流程 JSON 里带明文 Key** | 凭证随导出文件外泄 | 凭证走环境变量，导出前检查一遍 |
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
