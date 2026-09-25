---
name: sanjianke-llm-app-kit
slug: sanjianke-llm-app-kit
displayName: LLM应用开发套件·统一接口接OpenAI兼容网关换模型只改一行
description: "用一套统一接口把模型、工具、记忆、检索串成能跑完的 LLM 应用：把模型提供方的 base_url 指向 https://api.a7w.cn/ ，同一把 Key 调用 75 个在架模型，换 model 字符串就是换模型，业务代码不用动；包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) 。生成内容的使用与合规责任由使用者承担。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "写 LLM 应用最烦的不是模型不够强，是每换一个供应商就得重写一层胶水：一家一套参数、一家一套消息格式、一家一份账单。这个 Skill 讲的就是把这层胶水标准化之后，把模型提供方整个指向 https://api.a7w.cn/ —— 一个 base_url、一把 Key，现场可查 75 个在架模型（23 家厂商，国产为主 + 国际主流）与 21 个生成应用。换模型就是换一个字符串，不用换端点、不用换凭证、账单还是同一份。包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) ，注册即送点数、按量计费、失败全额退回。含最小可用写法、流式输出、结构化输出、多模型横评脚本、异步任务生命周期、点数计费口径、错误码排查手册与零依赖客户端。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 开发编程
  - AI
  - LLM
  - 模型网关
  - 应用开发
---

# LLM 应用开发套件 · 换模型只改一行

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

写 LLM 应用最烦的不是模型不够强，是**每换一个供应商就得重写一层胶水**：
OpenAI 一套参数、另一家一套消息格式、本地服务又是另一套。

真正该做的是**把这层胶水标准化**：同一套调用接口，底下换成哪家模型都不动业务代码。
而模型提供方整排，可以只用一个 `base_url` 收下来 —— **换模型就是换一个字符串。**

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **1 元 = 100 点**；文本按点数/百万 tokens（输入输出分别计价），流式与非流式同价 |
| 要多久 | 文本同步返回；生成应用是异步任务，**查询免费** |
| 要装什么 | **除运行环境外什么都不用装**；包里自带零依赖客户端，或者直接用 `curl` |
| 能接什么 | **75 个在架模型**（23 家厂商）+ **21 个生成应用** |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：换成 a7w 端点（两个值）

```
Base URL: https://api.a7w.cn/api/v1
Authorization: Bearer <你的 API Key>
```

Python SDK 里就是换两个参数，**其余代码一行都不用动**：

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key=os.environ["A7W_API_KEY"],
)
resp = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)
```

### 第三步：多模型横评，只换字符串

同一个问题丢给三家的模型，代码结构完全一样——**这是统一路由最直接的价值**：

```python
for name in ("DeepSeek-V4-Flash", "Qwen3.6-Flash", "GLM-5"):
    r = client.chat.completions.create(
        model=name, messages=[{"role": "user", "content": "用一句话解释 RAG"}])
    print(name, "→", r.choices[0].message.content[:60])
```

**换 model 不用换 base_url、不用换 Key、账单还是同一份。** 比价与灰度从工程活变成参数变更。

### 第四步：模型名以接口为准

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

实测 **75 个模型 / 23 家厂商**（文本 58 · 图片 12 · 视频 5）。
站内宣传口径与实测口径不一致，**要准数现场跑接口，别把示例里的名字当永久契约**。

| 场景 | 建议 `model` |
|---|---|
| 中文通用、性价比优先 | `DeepSeek-V4-Flash`、`Qwen3.6-Flash` |
| 复杂推理 | `DeepSeek-R1-Distill-Qwen-32B`、`ERNIE-5.0-Thinking` |
| 长文与代码 | `Kimi-K2.6`、`Qwen3-Coder-Next` |
| 视觉理解 | `qwen3.6-plus`、`Qwen3-VL-30B-A3B-Instruct`、`PaddleOCR-VL-1.5` |

### 第五步：生成类能力走应用任务

出图、出视频、配音、数字人、文档问答不在 `chat/completions` 里：

```bash
python3 scripts/a7w.py apps                 # 21 个应用
python3 scripts/a7w.py schema file_qa       # 接口、参数、同步/异步、真实价
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好世界"}' --out 试听.mp3
```

**路径永远是 `/api/v1/apps/<应用代号>/<接口代号>`。**
⚠️ 不要用平台的 `endpoint_path` 字段拼 URL —— 对某些应用那是错的上游路径，打不通。

---

## 二、包里有什么

```
sanjianke-llm-app-kit/
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

## 三、流式与常用参数

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

---

## 四、各语言与低代码接法

Node / TypeScript：

```js
import OpenAI from "openai";
const client = new OpenAI({ baseURL: "https://api.a7w.cn/api/v1", apiKey: process.env.A7W_API_KEY });
```

不带 SDK 的运行时（定时任务、HTTP 工具节点、低代码平台）按标准 OpenAI HTTP 形态：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

| 界面字段 | 填什么 |
|---|---|
| API Base / Base URL | `https://api.a7w.cn/api/v1` |
| API Key / 令牌 | 你自己的 `sk-...` |
| Model | 从 `/api/v1/models` 里选 |

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`** |
| **HTTP 200 就以为成功** | 不存在的接口也返回 200 | 业务成败看 `code`：`1` / `200` 成功，`0` 失败 |
| **base_url 填成裸域** | 404 | 必须是 `https://api.a7w.cn/api/v1`，带 `/api/v1` |
| **base_url 末尾多一个斜杠** | 路径拼成 `//chat/completions` | 去掉末尾斜杠 |
| **拿 `name` 当接口代号** | 调用失败 | 字段名是 `code`，不是 `api`；`name` 是中文展示名 |
| **用 `endpoint_path` 拼 URL** | 应用怎么调都打不通 | 一律用 `/api/v1/apps/{app}/{code}` |
| **推理模型 `max_tokens` 给小了** | `content` 返回 `null`、`finish_reason=length` | 推理模型先花思维链 token，给足 `max_tokens` |
| **思维链字段读不到** | 拿不到推理过程 | `reasoning` 与 `reasoning_content` 两个名字都读 |
| **把 Key 硬编码进代码** | 凭证泄漏 | 走环境变量或 `~/.a7w/config.json`，不要提交进 Git |
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
