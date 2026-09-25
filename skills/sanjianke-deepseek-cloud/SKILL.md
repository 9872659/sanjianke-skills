---
name: sanjianke-deepseek-cloud
slug: sanjianke-deepseek-cloud
displayName: DeepSeek全系云端直连·免部署一个Key切换调用大模型
description: "直接用 api.a7w.cn 在架的 DeepSeek 全系大模型，不用自己部署、不用显卡、不用下模型文件。四款在架型号随任务切换，兼容 OpenAI 协议，只换 base_url 与 model。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。注册领 Key 见 https://api.a7w.cn/ 。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "不用自己部署，直接调 api.a7w.cn 在架的 DeepSeek 全系大模型：填两行配置就能用上 V4-Pro、V4-Flash、V3.2 与 R1-Distill-32B，免显卡、免运维、按量计费，调用失败直接退款。日常问答、推理、长文、代码与批量跑量都能按用途选档，接线三种任选：curl 直连、OpenAI SDK 只换 base_url 与 api_key、包内零依赖客户端。含流式示例、选型表、常见坑与真实计费口径。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 大模型
  - DeepSeek
  - OpenAI 兼容
  - 模型网关
  - 云端推理
---

# DeepSeek 全系云端直连 · 免部署调用

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

**不用自己部署，直接调 a7w 在架的 DeepSeek。** 不用下几百 GB 的模型文件、不用买多张显卡、
不用配推理环境——填两行配置，当天就能把 DeepSeek 接进你的项目。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **按量计费**，1 元 = 100 点，用完为止没有月费；**调用失败直接退款** |
| 要多久 | **秒级返回**，同步接口；流式可以边生成边吐字 |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端，或者直接用 `curl` |
| 能用几个模型 | 在架 **DeepSeek 全系 4 款**：`DeepSeek-V4-Pro` / `DeepSeek-V4-Flash` / `DeepSeek-V3.2` / `DeepSeek-R1-Distill-Qwen-32B`，换 `model` 就换模型 |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`），填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

基址与请求头固定就这两个值：

```
Base URL: https://api.a7w.cn/api/v1
Authorization: Bearer <你的 API Key>
```

> 宿主本身就带 `/v1` 后缀的（部分 SDK、部分客户端），基址填 `https://api.a7w.cn/api`。

### 第二步：先拉一遍在架模型清单

**不要照抄文章里的旧模型名**，现场拉一次最准：

```bash
curl -sS "https://api.a7w.cn/api/v1/models" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

### 第三步：发第一条对话

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

返回体里读 `choices[0].message.content` 就是回答。**成功看 `code == 1`**（见「常见坑」）。

### 第四步：要流式就加一个字段

```bash
curl -sS -N -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","stream":true,"messages":[{"role":"user","content":"用三句话介绍你自己"}]}'
```

流式返回是一行行 `data: {...}`，每行取 `choices[0].delta.content` 追加输出，遇到
`data: [DONE]` 结束：

```python
# 流式读取的核心逻辑（任何语言的 SDK 都是同一个字段路径）
# for chunk in stream:
#     piece = chunk["choices"][0]["delta"].get("content")   # 可能为 None，先判空再拼
#     if piece:
#         print(piece, end="", flush=True)
```

---

## 二、接线方式三选一

### 方式 A：curl 直连（零依赖，适合先验证通不通）

见上面的第三、第四步。请求体复杂时把 JSON 落成文件再 `-d @body.json` 传，
省掉 Windows 下引号被吃的问题：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d @body.json
```

### 方式 B：OpenAI SDK，只换两个值

**原来调 OpenAI 的代码基本不用改**，换 `base_url` 和 `api_key` 就行：

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",
)

resp = client.chat.completions.create(
    model="DeepSeek-V4-Pro",
    messages=[{"role": "user", "content": "把这段需求拆成开发任务清单"}],
)
print(resp.choices[0].message.content)

# 流式：同一个 client，多传一个 stream=True
stream = client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "写一个 Python 快排"}],
    stream=True,
)
for chunk in stream:
    piece = chunk.choices[0].delta.content
    if piece:
        print(piece, end="", flush=True)
```

Node 的接法完全一致：

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.a7w.cn/api/v1",   // 只改这一行
  apiKey: process.env.A7W_API_KEY,        // 只改这一行
});

const resp = await client.chat.completions.create({
  model: "DeepSeek-V4-Pro",
  messages: [{ role: "user", content: "你好" }],
});
console.log(resp.choices[0].message.content);
```

**换模型就是换 `model` 字符串**——不用换 base_url、不用换 Key、账单还是同一份。

### 方式 C：包内零依赖客户端 `scripts/a7w.py`

只用 Python 标准库（Python 3.8+），**不内嵌任何密钥**。Key 读取顺序：
`--key` 参数 → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。

```bash
export A7W_API_KEY=sk-你的key

python3 scripts/a7w.py login --key sk-xxx    # 验证并保存 Key
python3 scripts/a7w.py whoami                # 看当前 Key 能用的插件数
python3 scripts/a7w.py apps                  # 列出全部插件
python3 scripts/a7w.py schema <app>          # 看某插件的接口与参数
python3 scripts/a7w.py call <app> <api> --body '{"k":"v"}' [--no-wait] [--out 文件]
python3 scripts/a7w.py task <task_id>        # 查异步任务
python3 scripts/a7w.py points                # 看最近的用量
```

客户端对网络类错误与 5xx 做退避重试（4 次），4xx 是业务错误不重试；
`call` 遇到返回里有 `task_id` 会自动轮询到终态。

---

## 三、包里有什么

```
sanjianke-deepseek-cloud/
├── SKILL.md                     本文件
├── README.md
├── references/
│   ├── api-openai-compat.md     chat/completions 完整参数、流式、SDK、推理模型细节
│   └── 通用说明.md              鉴权、计费口径、错误码、异步与回调、自检清单
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 自检：Key 通不通，一次看清
python3 scripts/a7w.py whoami
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"

# 看 Key 能用的插件与接口
python3 scripts/a7w.py apps
```

---

## 四、在架 DeepSeek 型号怎么选

四款都在 `GET /api/v1/models` 里，编码逐字照抄如下（**以现场拉取为准**）：

| 编码 | 定位 | 适合 |
|---|---|---|
| `DeepSeek-V4-Pro` | 旗舰档 | 复杂改写、方案设计、难一点的分析与长输出 |
| `DeepSeek-V4-Flash` | 轻快档 | 日常问答、批量跑量、成本敏感的高频调用 |
| `DeepSeek-V3.2` | 通用档 | 通用对话、摘要、结构化抽取，稳且均衡 |
| `DeepSeek-R1-Distill-Qwen-32B` | 推理档 | 数学、逻辑、需要逐步思考的题 |

**按用途选哪个：**

| 你要做什么 | 建议用 | 为什么 |
|---|---|---|
| 日常问答 / 客服话术 | `DeepSeek-V4-Flash` | 快、便宜，量大也不心疼 |
| 高难推理 / 数学逻辑 | `DeepSeek-R1-Distill-Qwen-32B` | 先把 token 花在思考上，答案更稳 |
| 长文总结 / 长稿改写 | `DeepSeek-V4-Pro` | 上下文把握更好，长输出不散 |
| 代码生成 / 代码解释 | `DeepSeek-V4-Pro` | 复杂重构与多文件改动的首选 |
| 批量跑量 / 打标洗稿 | `DeepSeek-V4-Flash` | 单价低，并发友好，适合跑大数量 |
| 通用稳妥、不想纠结 | `DeepSeek-V3.2` | 均衡档，什么都能接 |

> **推理档记得给足 `max_tokens`**：思考过程自己就吃掉不少 token，
> 给太小会导致正文为空（见「常见坑」）。

---

## 五、不用自己部署 vs 走 api.a7w.cn

两条路都走得通，区别只在**门槛**和**适合谁**：

| 维度 | 自建部署（本地 / 自购服务器） | 走 api.a7w.cn |
|---|---|---|
| 起步准备 | 准备模型文件（数百 GB 量级）与配套环境 | 填 base_url + Key 两行配置 |
| 硬件 | 需要匹配的显卡与显存，多卡还要做并行 | 不需要显卡，普通笔记本即可 |
| 时间成本 | 环境搭建、调试、压测都要自己排 | 当天就能接到业务里跑 |
| 人力成本 | 需要有人盯运维、升级与并发扩容 | 平台侧维护，你只管调接口 |
| 成本形态 | 硬件一次性 + 电费与机时按小时烧 | 按量计费，用多少扣多少 |
| 失败成本 | 调不通也要付机时 | **调用失败直接退款**，异步任务失败冻结点数全额退回 |
| 合适谁 | 有明确数据不出域要求、有闲置算力、想把推理能力长期沉淀在自己机房里 | 想快速上线、想控制前期投入、想按用量弹性伸缩、不想养运维 |

**结论很直白：想当天用上 DeepSeek，就先走 api.a7w.cn；等量级和数据合规要求都明确了，
再评估要不要把一部分搬到自有算力。**

---

## 六、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 业务成功码是 **`code == 1`**（`{"code":1,"msg":"success"}`）；`code == 0` 是失败，但 **HTTP 仍可能是 200** |
| **`max_tokens` 给太小** | 推理模型正文为空，`content` 是 `null`、`finish_reason` 是 `length` | token 全被思维链吃掉。实测 `DeepSeek-V4-Flash` 在 `max_tokens=8` 时就是这个表现，**加到 256 以上**就正常 |
| **思维链字段只取一个** | 拿不到思考内容 | 字段名在不同线路上分别是 `reasoning` 与 `reasoning_content`，**两个都要取** |
| **拿响应里的 `model` 做精确匹配** | 匹配不上 | 响应里的 `model` 会被规范成**小写**（如 `deepseek-v4-flash`），别用大小写敏感的等值判断 |
| **照抄文章里的旧模型名** | 报 404 / 模型不存在 | **以 `GET /api/v1/models` 现场拉取为准**，编码逐字复制 |
| **`/v1` 层数搞错** | 404 | 完整基址是 `https://api.a7w.cn/api/v1`；宿主自带 `/v1` 的填 `https://api.a7w.cn/api` |
| **把生成应用当模型调** | 没有 `choices` | 模型网关是 `POST /api/v1/chat/completions`（同步、直接返回 `choices`）；生成应用是 `POST /api/v1/apps/<应用>/<接口>`（多为异步、返回 `task_id`）。**模型网关没有 `task_id`，应用任务也不吃 `messages` 数组** |
| **网络超时就直接重发** | 可能扣两次 | 先确认是不是已扣费，异步任务先拿 `task_id` 查状态再决定是否重提 |

### 错误码速查

| HTTP | code | 含义 | 怎么办 |
|---|---|---|---|
| 400 | `invalid_request` | 参数缺失或格式错误 | 核对参数名与必填项 |
| 401 | `auth_failed` | API Key 缺失或无效 | 重新复制 Key，确认 `Bearer ` 前缀 |
| 402 | `insufficient_points` | 账号点数余额不足 | 充值；错误里带本次所需点数 |
| 402 | `key_quota_exceeded` | 该 Key 自己的额度打满 | 去用户中心调高该 Key 的 quota，或换 Key |
| 403 | `permission_denied` | 该 Key 无权调用此模型 | 检查模型是否已开通、Key 是否被限权 |
| 404 | `not_found` | 模型 / 任务不存在 | 核对编码拼写；先怀疑 `/v1` 层数 |
| 429 | `queue_limit_exceeded` | 排队任务已达上限 | 降并发，等队列消化后重试 |
| 5xx | `server_error` | 服务异常 | 退避重试；仍失败换模型/线路 |

> **402 有两种**：账号没钱（`insufficient_points`）和 Key 自己的额度打满（`key_quota_exceeded`）。
> 先分清是哪一种，否则会去充一个根本不需要充的账户。

---

## 七、计费

- **1 元 = 100 点，1 点 = 0.01 元。** 点数永久有效。
- 体验包 ¥10 = 600 点（含 7 天会员权益），标准包 ¥99 = 10000 点。
- 文本按**点数 / 百万 tokens**（输入输出分别计价，**流式与非流式同价**）。
- **先冻结、后结算**：消费优先扣会员点数，不足再扣充值额度。
- **调用失败直接退款；异步任务失败，冻结点数全额退回。**
- 平台同时给两套价格字段：`fixed_price` / `input_price` 是**公示标准价**；
  `tenant_fixed_points` / `tenant_points_per_1k_input` 是**你所在租户的实际结算价**。
  **做预算一律用 `tenant_*`，最终以账号里实际扣费为准。**
- 查询任务状态**免费**。

### 一次问答大概花多少

按**点数 / 百万 tokens** 计价，粗算口径是这样：

| 一次调用的规模 | 大致 token 量 | 直觉 |
|---|---|---|
| 短问答（一两句提问，一两段回答） | 几百 token | 极低成本，可以忽略不计 |
| 正常问答 / 一段文案 | 一两千 token | 几分钱量级 |
| 长文总结 / 长稿改写 | 上万 token | 一毛到几毛量级 |
| 批量跑量（几百上千次短问答） | 累积起来 | 用轻快档跑，总账可控 |

> 真实扣费以返回里的用量与账号账单为准：**先跑几条小请求，看一眼 `points` / 余额变化，
> 再估算批量成本**，别拿别人的截图当预算。

---

## 八、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的模型接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅在读取你指定的输入文件时 | 作为请求体或素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON |
| 凭证 | 读取**你自己**提供的 API Key | 从 `--key`、环境变量 `A7W_API_KEY` 或 `~/.a7w/config.json` 读取 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不保证可用性**：模型上下架、限流与计费以站内为准
- **不替代内容合规审查**：生成内容的使用与合规责任由使用者承担
- **不要在代码里硬编 Key**，不要提交进仓库

---

## 关于这个 Skill

**作者亲测实操后发布，下载后可直接使用，自用商用都可以。**

所有 AI 能力都走 [算力集市 api.a7w.cn](https://api.a7w.cn/) —— 一把 API Key 打通
大模型、语音、图像、视频、数字人等全部算力，注册即送点数，按量计费、没有月费。

| 你可能想问 | 答案 |
|---|---|
| 要不要额外部署 | 不用。**下载本包即可使用**，不必去别处找源码 |
| 要不要显卡 / 要不要下模型文件 | 都不用。云端在架模型直接调 |
| 怎么开始 | 到 api.a7w.cn 注册领 Key → 填进 `A7W_API_KEY` → 一条 curl 跑起来 |
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
