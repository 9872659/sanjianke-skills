---
name: sanjianke-ai-chat-ui
slug: sanjianke-ai-chat-ui
displayName: AI聊天客户端接国产大模型·一个Key换75个模型接入配置
description: "让 AI 聊天客户端用上 75 个在架大模型：填一个 base_url、一把 api.a7w.cn 的 Key，DeepSeek、通义千问、智谱 GLM、Kimi、混元、MiniMax 与 GPT 全部进同一个模型下拉框，换 model 就是换模型，不用逐家注册、不用改代码。另附出图、配音、视频、数字人等 21 个生成应用的接入口径、base_url 层数判断法与全套排错表。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "把 AI 聊天客户端接到算力集市 api.a7w.cn，一个 Key 用上 75 个在架大模型与 21 个生成应用。含客户端侧的 base_url / apiHost / 代理地址逐项填法对照、模型列表刷不出来的四类原因与手动添加模型的做法、流式与推理模型返回空正文的处理、多厂商模型在同一入口切换的配置方式、生成类应用（出图 / 配音 / 视频 / 数字人）的接入口径，以及 401 / 402 / 403 / 429 全套错误码排错表。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`），零安装、零第三方依赖。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI 客户端
  - 聊天界面
  - 模型网关
  - OpenAI 兼容
  - 多模型切换
---

# AI 聊天客户端接国产大模型

你手上有一个 AI 聊天界面（网页版、桌面版、自托管版都算），想问的模型却有一整排：
DeepSeek 写方案、通义千问读图、GLM 做检索、Kimi 啃长文、混元翻中英、MiniMax 出语音。

逐个去注册、逐个充值、逐个填 Key、逐个对账 —— 这件事本身没有任何产出。

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

**把聊天客户端指向 `api.a7w.cn`，一把 Key 就把 75 个在架模型装进同一个模型下拉框。**
换模型只是改一个字符串，不用换地址、不用换 Key、账单还是同一份。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **1 元 = 100 点**，文本按点数/百万 tokens 计，用多少扣多少，没有月费 |
| 要多久 | 模型网关**同步返回**，聊天界面秒级出字；生成类应用是异步任务 |
| 要装什么 | **什么都不用装**。客户端填两行配置即可；包里另附零依赖客户端与 `curl` 用法 |
| 能用几个模型 | **75 个在架大模型**（23 家厂商）+ **21 个生成应用**，同一个 Key、同一份账单 |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，在控制台创建一个 API Key（形如 `sk-...`），填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：先把客户端要填的两个值确认下来

这一步是全部的难点所在 —— **客户端要的「地址」到底填到哪一层**：

| 客户端里的字段 | 填什么 | 说明 |
|---|---|---|
| **API 地址 / Base URL**（OpenAI 兼容） | `https://api.a7w.cn/api/v1` | 绝大多数客户端、SDK 要的是**带 `/v1`** 的这一个 |
| **API Host / 服务器地址**（自带 `/v1` 后缀的客户端） | `https://api.a7w.cn/api` | 少数客户端会自己补 `/v1`，填成上一个会变成 `/api/v1/v1/...` |
| **API Key / 令牌** | `sk-你的key` | 与上面这把 Key 完全一致 |
| **模型名称** | `DeepSeek-V4-Flash` 等 | **必须与在架模型编码逐字一致**，客户端里手填 |

判断方法：看客户端文档给的示例地址。示例里已经带 `/v1`，就填 `https://api.a7w.cn/api/v1`；
示例里没有 `/v1`（说明它会自己拼），就填 `https://api.a7w.cn/api`。

### 第三步：用一条 `curl` 验证（不依赖任何客户端）

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
```

返回里 `choices[0].message.content` 就是模型回的话。这一步通了，说明 Key、地址、模型名三件事全对，
剩下只是把它抄进客户端的配置页。

### 第四步：把生成类应用也接进来（可选）

聊天客户端里能发消息，就一定能发图片、发语音 —— 因为生成类应用走的是同一把 Key。
真实接口路径一律是 **`/api/v1/apps/<应用代号>/<接口代号>`**：

```bash
# 出图（应用代号 nano_banana；异步任务：提交后拿 task_id）
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/nano_banana/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"一只在窗台晒太阳的橘猫，胶片质感"}'
```

```bash
# 文字转语音（应用代号 voice_tts）
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/voice_tts/tts" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，这是一段试听"}'
```

> **接口代号别猜**：先跑 `python3 scripts/a7w.py schema <应用代号>`，
> 它会把这个应用**实际可用**的接口名与参数逐条列出来（含哪个是异步、哪个必填）。

---

## 二、包里有什么

```
sanjianke-ai-chat-ui/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 客户端接入配置.md         base_url / apiHost 逐项填法、模型清单刷法、多入口并存
│   ├── api-openai-compat.md     chat/completions 完整参数、流式、SDK、推理模型细节
│   ├── api-apps-tasks.md        21 个生成应用怎么调、异步任务生命周期与回调
│   ├── getting-started.md       注册、领 Key、配置到本机
│   └── 通用说明.md              权限、错误码、计费口径、排错
└── scripts/
    └── a7w.py                   零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 看有哪些应用、各有哪些接口与参数
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema voice_tts

# 查现有音色 / 试听
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好，这是一段试听"}'

# 出图这类异步任务，客户端会自动轮询到出结果
python3 scripts/a7w.py call nano_banana submit \
  --body '{"prompt":"一只在窗台晒太阳的橘猫，胶片质感"}'
```

---

## 三、模型怎么选

**模型名以线上清单为准，不要抄文章里的**（上下架很频繁）：

```bash
python3 scripts/a7w.py whoami
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

| 你想干的事 | 优先试 |
|---|---|
| 通用问答、写作、总结 | `DeepSeek-V4-Flash`（便宜快）、`DeepSeek-V4-Pro`（质量高） |
| 复杂推理、算题、写代码 | `DeepSeek-R1-Distill-Qwen-32B`、`Qwen3-Coder-Next`、`kimi-k3` |
| 读图、看截图、识别票据 | `Qwen3-VL-30B-A3B-Instruct`、`ERNIE-4.5-Turbo-VL`、`qwen3.6-plus` |
| 超长文档、长报告 | `Kimi-K2.6`、`Qwen3.5-122B-A10B` |
| 中英互译 | `Hunyuan-MT-Chimera-7B`、`HY-MT2-7B` |
| 出图 | `nano-banana-pro`、`gpt-image-2.5`、`qwen-image-3.0-pro` |
| 出视频 | `wan3.0-video`、`h3-video`、`veo3.1-pro` |

**换模型就是换一个字符串。** 同一个客户端里，模型下拉框能加的条目没有上限，
所以「一家一个 App」这件事可以彻底省掉。

---

## 四、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **地址少填或多填一层 `/v1`** | 稳定 404，报错只说「连接失败」 | 通用客户端填 `https://api.a7w.cn/api/v1`；自带 `/v1` 的客户端填 `https://api.a7w.cn/api` |
| **模型名抄了文章里的旧名** | 404 / 403 | 用 `/api/v1/models` 现场拉真实编码，逐字复制 |
| **模型下拉框里只有几个模型** | 界面只展示它认识的模型 | 在客户端里**手动添加自定义模型**，把编码填进去即可 |
| **推理模型回复是空的** | `content` 为 `null`、`finish_reason` 是 `length` | 推理模型先花 token 出思维链，把 `max_tokens` 调到 256 以上立即正常 |
| **拿本地文件路径当入参** | 报参数错误 | 一律用**公网可访问的 URL**，不支持本地路径与 Base64 |
| **用 `endpoint_path` 字段拼 URL** | 打不通 | 生成类应用一律用 `/api/v1/apps/<应用代号>/<接口代号>`，两个代号都来自线上返回的 `code` |
| **重复提交异步任务** | 扣两次钱 | 先记 `task_id`，用查询接口（免费）确认状态 |
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **把 Key 写进会提交进 Git 的 `.env`** | Key 泄漏 = 余额泄漏 | Key 走环境变量；`.env` 必须进 `.gitignore` |
| **聊天客户端暴露到公网** | 等于把你的模型额度开放出去 | 加访问控制，或只监听 `127.0.0.1` |

---

## 五、计费

| 动作 | 怎么算 |
|---|---|
| **文本对话** | 按**点数 / 百万 tokens**，输入输出分别计价，流式与非流式同价 |
| 图像生成 | 按**点数 / 张**或分辨率档位 |
| 视频生成 / 超分 | 按**点数 / 秒**（分辨率分档） |
| 数字人 | 按**点数 / 次或时长** |
| TTS / 音色克隆 | 按**点数 / 千字** |
| 语音转文字 | 按**点数 / 分钟** |
| 查询任务状态 | **免费** |

**1 元 = 100 点，1 点 = 0.01 元。** 先冻结、后结算，**调用失败直接退款，异步任务失败冻结点数全额退回**。
每次返回的 `data.usage.points_cost` 就是本次真实扣费，可以直接对账。

> 平台同时给出标准价与租户实际结算价（`tenant_*`）。**做预算一律用实收价，最终以账号里实际扣费为准。**

**省钱三招**：① 压 `max_tokens`（它同时是质量旋钮和成本旋钮）；② 日常问答用 `-Flash` 线，
难题才切 `-Pro` 线；③ 长文档先摘要再入库，别每次把全文塞进上下文。

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
- **不替代内容合规审查**：生成内容的使用与合规责任由使用者承担
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