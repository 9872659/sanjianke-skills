---
name: sanjianke-ai-workflow
slug: sanjianke-ai-workflow
displayName: 可视化AI工作流编排·OpenAI兼容网关接21个生成应用
description: "不写编排代码，用画布把「输入 → 检索 → 模型 → 工具 → 输出」串成一条可调试、可发布的 AI 工作流，再一键接上 21 个生成应用（出图 / 视频 / 数字人 / 配音 / 音乐 / 文档问答）。模型侧走 OpenAI 兼容网关，把 base_url 指向 https://api.a7w.cn/ 就能调 75 个在架模型，一把 Key 通吃、换 model 即换模型；包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) 。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "把「输入 → 检索 → 模型 → 工具 → 输出」这条链路从代码里搬到画布上：拖节点、连线、实时调试，改一版试一版，不用为了改一行提示词就重新发版。模型提供方不再逐家注册——把 base_url 指向 https://api.a7w.cn/ ，用同一把 Key 调用 75 个在架大模型（23 家厂商，国产为主 + 国际主流）与 21 个生成应用，换 model 字符串就是换模型，账单只此一份。包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) ，注册即送点数、按量计费、失败全额退回。含最小可用写法、框架与 SDK 对照、异步任务生命周期、点数计费口径、错误码排查手册与零依赖客户端。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - AI
  - LLM
  - 工作流编排
  - 模型网关
---

# 可视化 AI 工作流编排 · 一把 Key 接全模型

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

你要做的是一件正经事：**把「输入 → 检索 → 模型 → 工具 → 输出」这条链路搭出来，并且能随时改。**
如果纯写代码，光是串节点、管状态、做重试就够折腾半天；画布的价值是让这件事变成拖拽 + 连线。

而模型这一头，**你不需要逐家注册、逐家充值、逐家对账**。

`api.a7w.cn`（算力集市）把模型提供方收成**一个 base_url、一个 Key、一份账单**：
模型侧兼容 OpenAI 协议，换 `model` 就是换模型；生成类能力侧走统一的
「提交任务 → 拿 `task_id` → 轮询或收回调」。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **1 元 = 100 点**；文本按点数/百万 tokens、应用按次或按秒。先冻结后结算，**失败全额退回** |
| 要多久 | 文本同步返回；生成应用是异步任务，**查询免费** |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端，或者直接用 `curl` |
| 能接什么 | **75 个在架模型**（23 家厂商）+ **21 个生成应用** |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`），填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：把模型提供方指向 a7w（只改一行）

**画布里模型节点的「API Base / 自定义 OpenAI 端点」就填这两行：**

```
Base URL: https://api.a7w.cn/api/v1
Authorization: Bearer <你的 API Key>
```

先确认这把 Key 通不通——通了就说明模型侧已经接好：

```bash
curl -sS "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

返回里 `choices[0].message.content` 就是答案。

### 第三步：模型名以接口为准，不要猜

站内宣传口径与实测口径不一致（宣传 87+/89+，**实测 75 个模型 / 21 个应用**）。
要准数现场跑：

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
python3 scripts/a7w.py apps
```

**换模型就是换一个 `model` 字符串** —— 不用换 base_url、不用换 Key、账单还是同一份。
所以「A 模型效果不行想换 B 试」在画布里只是改一个参数，不是一次改版。

### 第四步：需要生成类能力时走应用任务

出图、出视频、做数字人、配音、做音乐、文档问答这些**不在** `chat/completions` 里，
走统一的应用入口（画布上用 HTTP 请求节点打过去，或直接由 Skill 脚本产出后回填）：

```bash
# 看平台上有哪些应用（21 个）
python3 scripts/a7w.py apps

# 看某个应用有哪些接口、参数与真实价
python3 scripts/a7w.py schema voice_tts

# 提交任务，异步接口会自动轮询到结束
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好世界"}'
```

**接口路径永远是 `/api/v1/apps/<应用代号>/<接口代号>`**，两个代号都来自接口返回的 `code` 字段。

> ⚠️ **不要用平台的 `endpoint_path` 字段拼 URL** —— 它对某些应用是错的上游路径
> （如 `seedance` 给的是 `/ant/xxx`、`smart_clip` 给的是 `/v1/clip/xxx`），照着拼打不通。

---

## 二、包里有什么

```
sanjianke-ai-workflow/
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

## 三、两条调用入口怎么选

平台把能力分成两类，**共用同一套鉴权与同一份账单**，但调用姿势不同：

| 入口 | 谁在用 | 怎么调 | 形态 |
|---|---|---|---|
| **模型网关**（OpenAI 兼容） | DeepSeek / 千问 / 智谱 / Kimi 等主流大模型 | `POST /api/v1/chat/completions` | 同步，返回 `choices` |
| **应用任务** | 出图、视频、数字人、超分、换装、TTS、音乐、文档问答等 21 个生成应用 | `POST /api/v1/apps/{app}/{api}` | 多为异步，返回 `task_id` |

选错入口是最常见的踩坑：**模型网关没有 `task_id`，应用任务也基本不吃 `messages` 数组**。
先想清楚你要的是「一段推理结果」还是「一个生成产物」。

异步任务的标准节奏：提交拿到 `task_id` → 轮询 `GET /api/v1/tasks/{task_id}` →
终态看 `status`（`completed` / `failed` / `cancelled`），产物在 `result`，用量在 `usage`。
不想轮询就在提交时带 `callback_url`。

---

## 四、能接到的能力清单

**模型侧**（代表项，实测 75 个 / 23 家厂商）：

| 类别 | 代表模型（`model` 编码） |
|---|---|
| 国产文本 | `DeepSeek-V4-Pro`、`DeepSeek-V4-Flash`、`Qwen3.7-Max`、`GLM-5.2`、`Kimi-K2.6`、`ERNIE-5.0-Thinking`、`MiniMax-M3` |
| 国际文本 | `gpt-5.6-sol`、`gpt-5.5`、`gemma-4-26B-A4B-it` |
| 图像 | `nano-banana-pro`、`gpt-image-2.5`、`qwen-image-3.0-pro` |
| 视频 | `veo3.1-pro`、`veo3.1-fast`、`grok-video`、`wan3.0-video` |

**应用侧**（21 个生成应用，按类别）：

| 类别 | 应用代号 |
|---|---|
| 文档 | `file_qa` |
| 音频 | `voice_tts`、`music_generation`、`music_search`、`mmaudio`、`seedsvc` |
| 图片 | `nano_banana` |
| 视频 | `full_video`、`happy_horse`、`grok_video`、`wan`、`seedance` |
| 数字人 | `image_human`、`pic_lipsync`、`lipsync` |
| 剪辑 | `action_transfer`、`person_replacement`、`dressing_diffusion`、`smart_clip`、`flashvsr` |

**清单以 `python3 scripts/a7w.py apps` 的实时返回为准。**

> 平台的 `vendor_name` 字段存在标注串味，**以 `model` 编码为准**，
> 不要用厂商字段做精确匹配。

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **HTTP 200 就以为成功** | 调不存在的接口也返回 200 | 业务成败看 `code`：`1` / `200` 为成功，`0` 为失败 |
| **用 `endpoint_path` 拼 URL** | 某些应用怎么调都打不通 | 一律用 `/api/v1/apps/{app}/{code}` |
| **应用代号写成连字符** | 404 | API 里用下划线：`voice_tts`、`file_qa`、`nano_banana` |
| **把 `name` 当接口代号** | 调用失败 | 字段名是 `code`，不是 `api`；`name` 是中文展示名 |
| **重复提交异步任务** | 扣两次钱 | 先记 `task_id`，用任务查询（免费）确认状态 |
| **裸对象端点按外壳解析** | 把可用端点误判为不可用 | `balance` / `pricing` 直接返回裸对象，没有 `code/msg/data` 外壳 |
| **推理模型 `max_tokens` 给小了** | `content` 返回 `null`、`finish_reason=length` | 推理模型的 token 先花在思维链上，给足 `max_tokens` |
| **Shell 吃掉 JSON 双引号** | 请求体被截断 | 复杂请求体写进文件用 `--json-file`，或 `--param k=v` 逐个传 |
| **做预算用公示标准价** | 预算算错 | 一律用 `tenant_*`（你所在租户的实际结算价） |

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
