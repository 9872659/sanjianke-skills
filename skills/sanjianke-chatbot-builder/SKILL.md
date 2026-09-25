---
name: sanjianke-chatbot-builder
slug: sanjianke-chatbot-builder
displayName: 聊天机器人接大模型·多平台机器人用国产模型回话方案
description: "让聊天机器人真正会说话：群里收到消息，用 api.a7w.cn 的 OpenAI 兼容接口让 DeepSeek、通义千问、智谱 GLM、Kimi、混元等 75 个在架大模型回话，同一把 Key 还能发图、发语音、转写群里的语音。含多轮上下文裁剪、并发与 429 处理、消息去重、超时降级、模型选型与控成本口径，以及零依赖客户端与排错表。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "把大模型接进聊天机器人的完整落地方案：框架侧负责平台协议与事件分发，大模型侧统一走 api.a7w.cn 的 OpenAI 兼容入口，一个 Key 调 75 个在架大模型与 21 个生成应用。覆盖多轮上下文裁剪、同群串行与并发控制、429 退避重试、消息幂等去重、回复分段、超时降级到更快的模型、群里 @ 才触发、内容合规自检；并给出用同一把 Key 发图（nano_banana）、发语音（voice_tts/tts）、转写语音（voice_tts/stt）的接法与按用途选模型表、控成本口径。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 聊天机器人
  - 大模型接入
  - OpenAI 兼容
  - 模型网关
  - 群机器人
---

# 聊天机器人接大模型

机器人框架能收发消息了，但它还只会念固定的几句话。你想让它在群里**真的能答** ——
问天气、聊商品、答客服问题、总结今天群里聊了什么。

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

**要接的不是一家模型，是 75 个。** 把大模型侧指向 `api.a7w.cn`：
一个 base_url、一把 Key，DeepSeek、通义千问、智谱 GLM、Kimi、混元、MiniMax 全进同一个入口，
换 `model` 就是换模型 —— 群里要快就切 Flash 线，要深就切 Pro 线。

框架侧你继续用自己的，本 Skill 只管**把大模型这一侧的接线、并发、降级、控成本做对**。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **1 元 = 100 点**，文本按点数/百万 tokens 计；一次群聊问答通常几分钱以内 |
| 要多久 | 模型网关**同步返回**，通常 1~3 秒；群内建议设 20~30 秒超时并降级 |
| 要装什么 | **什么都不用装**。零依赖客户端只用 Python 标准库，也可以直接 `curl` |
| 能用几个模型 | **75 个在架大模型** + **21 个生成应用**（发图 / 语音 / 转写），同一把 Key |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`），填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：先用 `curl` 确认「模型能回话」

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
```

`choices[0].message.content` 就是模型回的话。

### 第三步：在机器人里换成零依赖调用

不用引入任何第三方包（`urllib` 就是标准库）：

```python
import json, os, urllib.request

def ask(prompt, model="DeepSeek-V4-Flash", timeout=25):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
    }).encode()
    req = urllib.request.Request(
        "https://api.a7w.cn/api/v1/chat/completions", data=body,
        headers={"Authorization": "Bearer " + os.environ["A7W_API_KEY"],
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]
```

### 第四步：按平台推回去

把你机器人框架里「收到消息」的处理器改成：**取文本 → 调上面的 `ask()` → 发回去**。
剩下的工程细节（多轮上下文、并发、去重、降级）在 `references/bot-llm-integration.md` 里逐项给方案。

---

## 二、包里有什么

```
sanjianke-chatbot-builder/
├── SKILL.md                        本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── bot-llm-integration.md      机器人接大模型：三种接法、并发与去重、降级、选型、发图发语音
│   └── 通用说明.md                  鉴权、两条入口、计费口径、错误码、权限边界
└── scripts/
    └── a7w.py                      零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# Key 可用性自检
python3 scripts/a7w.py whoami

# 看 21 个生成应用与各自接口
python3 scripts/a7w.py apps

# 看某应用的接口名与参数（接口代号不要猜）
python3 scripts/a7w.py schema voice_tts

# 让机器人发语音（异步任务，客户端自动轮询到出结果）
python3 scripts/a7w.py call voice_tts tts --body '{"text":"群里好，我是机器人"}'
```

---

## 三、机器人侧的关键决定

| 决定 | 建议 |
|---|---|
| 用哪个模型 | 日常闲聊 `DeepSeek-V4-Flash`；群内问答 `Qwen3.6-Flash`；长文总结 `Kimi-K2.6`；翻译 `Hunyuan-MT-Chimera-7B` |
| 带多少上下文 | 只带**最近 N 轮** + 一条系统提示；长对话先做摘要，别把整段历史全塞进去 |
| 并发怎么控 | **同一个群串行**（一把锁），不同群之间限总并发；收到 429 就退避重试 |
| 超时设多久 | 20~30 秒；超时后**降级到更快的模型**再试一次，而不是干等 |
| 消息怎么去重 | 按平台给的 `message_id` 记一份，只回一次（重连 / 重投很常见） |
| 什么时候回 | 群里 @ 机器人才回；私聊直接回。**不要对每条消息都回**，会被踢 |
| 回复太长怎么办 | 超过平台上限就按标点分段发，别硬塞一条 |
| Key 放哪 | 环境变量 `A7W_API_KEY`；**绝不写进代码或提交进 Git** |

---

## 四、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **推理模型回复是空的** | `content` 为 `null`、`finish_reason` 是 `length` | 推理模型先花 token 出思维链，`max_tokens` 调到 256 以上立即正常 |
| **模型名抄了文章里的旧名** | 404 / 403 | 用 `/api/v1/models` 现场拉编码，逐字复制 |
| **地址少填或多填一层 `/v1`** | 404，报错只说连接失败 | 通用客户端填 `https://api.a7w.cn/api/v1`；自带 `/v1` 的填 `https://api.a7w.cn/api` |
| **同一条消息反复回复** | 群里刷屏 | 按 `message_id` 去重；网络重试时也要判重 |
| **上下文越滚越大** | 越来越慢、越来越贵 | 只带最近 N 轮；超长先摘要 |
| **同步阻塞把机器人卡死** | 一个人提问，全群都没响应 | 模型调用要走事件循环 / 线程池，不要阻塞主循环 |
| **拿本地文件路径当入参** | 报参数错误 | 一律用**公网可访问的 URL**，不支持本地路径与 Base64 |
| **拿 `endpoint_path` 字段拼 URL** | 打不通 | 生成类应用一律用 `/api/v1/apps/<应用代号>/<接口代号>` |
| **重复提交异步任务** | 扣两次钱 | 先记 `task_id`，用查询接口（免费）确认状态 |

---

## 五、计费

| 动作 | 怎么算 |
|---|---|
| **文本对话** | 按**点数 / 百万 tokens**，输入输出分别计价 |
| 图形生成 | 按**点数 / 张**或分辨率档位 |
| TTS / 音色克隆 | 按**点数 / 千字** |
| 语音转文字 | 按**点数 / 分钟** |
| 查询任务状态 | **免费** |

**1 元 = 100 点。** 先冻结、后结算，**调用失败直接退款，异步任务失败冻结点数全额退回**。
每次返回的 `data.usage.points_cost` 就是本次真实扣费，可以直接对账。

> 平台同时给出标准价与租户实际结算价（`tenant_*`）。**做预算一律用实收价，最终以账号里实际扣费为准。**

**群里控成本三招**：① 日常问答用 Flash 线，难题才切 Pro 线；② 压 `max_tokens`；
③ 按群设配额（给每个群一把独立 Key 并设 quota，打满就调不动，不会拖垮整个账号）。

---

## 六、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的网关接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 用作素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或下载产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代内容合规审查**：机器人在群里说的话由部署方负责，请自行加敏感词与合规自检
- **不保证模型长期在架**：模型上下架频繁，调用前先拉一次模型清单

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