---
name: sanjianke-text-models
slug: sanjianke-text-models
displayName: 文本模型台 · 92 个模型一句话横评，最便宜 0.40 元/百万 token
description: "**同一句话，92 个文本模型先报价再开口，最便宜的每百万 token 只要 0.40 元。** 实测 claude 13 个变体、kimi 5 个、通义千问 3.5/3.7/3.8 共 7 个、文心 3 个、DeepSeek 5 个，再加 gemma-4、MiMo、LegalOne、AutoGLM、KAT、Sinong1.0：每百万 token 输出 40 - 15,840 点（0.40 - 158.40 元）。三件事：①文本层只有一条入口 `POST /api/v1/chat/completions`，`/v1/messages` 实测 404；②单价不用反推，92 条文本模型自带 pricing，字段名叫 `per_1k_*`、单位其实是每百万 token；③`check` 用空 messages 免费验通不通，先冻 60 点全额退回。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "横评先解决「钱花在谁身上」。`catalog` 列全 92 个文本模型的每百万 token 单价与实测可调性；`cost` 用同一句话逐个报价：输出 100 万 token 时最便宜 40 点（0.40 元），最贵 15,840 点（158.40 元），差 396 倍。单价来源最硬：92 条 text 模型自带 `pricing.per_1k_*`，`usage_unit_size` 是 1,000,000 —— 字段名带 1k、数值是 1M，按 1K 算会错 1000 倍。价目表 115 条里没有这条路径，命中通配 `*`（上游点数 x 2、保底 50 点）；实测每次调用先冻 60 点，失败全额退回，所以 900 token 的一问一答下限就是 60 点。`check` 用空 messages 探针免费验通不通：kimi-k3、Qwen3.5-Flash、GLM-5.2、MiniMax-M3、LegalOne-8B、KAT-Dev 停在参数校验即通，claude 13 个变体回 `200 code 0 未上架`，gpt-5.5 回 403 上游欠费。`chat` 用同一句话逐个调用，落盘回答 + manifest.json + 对比清单.md；`doctor` 5 个只读端点 + 3 个探针。需要自备 api.a7w.cn 的 Key。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文本模型
  - 多模型横评
  - api.a7w.cn
---

# 文本模型台 · 92 个模型一句话横评，最便宜 0.40 元/百万 token

> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。
> 注册、充值、创建 Key 都在 [api.a7w.cn](https://api.a7w.cn/)；装好先跑 `python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**同一句话，92 个文本模型先报价再开口。** 每百万 token 输出最便宜 40 点（0.40 元）、最贵 15,840 点（158.40 元），
差 **396 倍**；而一次 900 token 的对话，每个模型都落在 60 点保底。

## 价目表（2026-11-08 实测，1 元 = 100 点）

| 模型 | 输入/百万 | 输出/百万 | 折算输出 | 这条路 |
|---|---|---|---|---|
| `HY-MT2-7B` | 40 | **40** | 0.40 元 | 未测，目录里最便宜的一档 |
| `gemma-4-26B-A4B-it` | 60 | 60 | 0.60 元 | 503 暂无可用渠道 |
| `GLM-5.2` | 800 | **105** | 1.05 元 | √ 能调（输出价写得比输入价低） |
| `Qwen3.5-Flash` | 30 | 210 | 2.10 元 | √ 能调，输入最便宜的一线 |
| `LegalOne-8B` | 210 | 210 | 2.10 元 | √ 能调 |
| `ERNIE-5.0-Thinking` | 410 | 1,610 | 16.10 元 | 401 未上架 |
| `MiniMax-M3` | 430 | 1,690 | 16.90 元 | √ 能调 |
| `MiMo-V2.5-Pro` | 710 | 2,110 | 21.10 元 | 404 站点首页 |
| `claude-sonnet-4-5` | 674 | 3,386 | 33.86 元 | 200 但 code 0，未上架 |
| `Qwen3.7-Max` | 1,200 | 3,600 | 36 元 | 404 未上架 |
| `claude-opus-5` | 1,584 | 7,920 | 79.20 元 | 只声明 anthropic_messages |
| `kimi-k3` | 2,000 | 10,000 | 100 元 | √ 能调 |
| `claude-fable-5-official` | 3,168 | **15,840** | 158.40 元 | 只声明 anthropic_messages |

`--budget` 单位是「点」，默认 600 点（6 元）。

## 三条干货

**一、文本层只有一条入口，`/v1/messages` 是空的。** 2026-11-08 用「合法参数 + 缺关键参数」逐个探，全部停在校验层、0 点：

```
POST /api/v1/chat/completions  {"model":"deepseek-chat"}  -> 422 missing field `messages`
POST /api/v1/messages          {"model":"claude-..."}     -> 404 站点首页 HTML
POST /v1/messages              {"model":"claude-..."}     -> 404 {"code":"unknown_endpoint"}
```

`claude-*` 的 13 个变体只声明 `anthropic_messages` 协议，也只能走 `/api/v1/chat/completions`；打进去回的是
`HTTP 200 {"code":0,"msg":"模型不存在或未上架"}` —— **状态码 200 不等于成功，`code` 是 0 就是没过**。

**二、字段名叫 per_1k，数值是每百万。** `GET /api/v1/models` 的 92 条 text 模型都带价：

```json
"pricing": {"per_1k_input": 1584, "per_1k_output": 7920,
            "pricing_v2": {"items": [{"usage_unit_size": 1000000,
              "effective_rate_config": {"input": 1584, "output": 7920}}]}}
```

`usage_unit_size` 是 1,000,000，`price_view` 也写「按百万 Token」—— 按 1K 算会错 1000 倍。同一段 `reference_price`
还给官方参考价：`claude-opus-5` 官方 $5 / $25，本站 1,584 / 7,920 点（15.84 / 79.20 元），省 53.4%。

**三、先冻 60 点，再谈 token。** 价目表 115 条规则里没有 `/api/v1/chat/completions`，命中通配 `*`：
`{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50}` = 上游点数 x 2、单笔保底 50 点。实测每次调用先冻 **60 点**：

```
11:27:20  charge  -60  reserve_sync:/api/v1/chat/completions
11:27:21  refund  +60  refund:sync:/api/v1/chat/completions
```

所以短对话比的不是单价，是谁答得好；单价差异要到几十万 token 才显形。`chat` 每次跑完都读
`GET /user/balance/logs`，把真实净额写进 `manifest.json`。

## 完整用法

```bash
# 1) 看全 92 个模型：单价 / 家族 / 实测可调性（免费，可离线）
python3 scripts/run.py catalog --limit 40
python3 scripts/run.py catalog --family claude
# 2) 免费验通不通：messages 为空，停在校验层，净 0 点
python3 scripts/run.py check --models kimi-k3,GLM-5.2,claude-opus-5,gpt-5.5
# 3) 先报价：同一句话，多个模型逐个报（免费）
python3 scripts/run.py cost --models kimi-k3,GLM-5.2,Qwen3.5-Flash --prompt "给一条 15 秒护肤口播写脚本"
# 4) 横评：同一句话跑 5 个模型（要 --yes，受 --budget 管）
python3 scripts/run.py chat --models kimi-k3,GLM-5.2,Qwen3.5-Flash,MiniMax-M3,LegalOne-8B \
    --prompt "给一条 15 秒护肤口播写脚本，三句话，最后一句带行动号召" --yes
# 5) 只打印请求，一分钱不花；再看本地台账
python3 scripts/run.py chat --models kimi-k3 --prompt "写一句广告语" --dry-run
python3 scripts/run.py log
```

## 三步上手

```bash
python3 scripts/run.py doctor      # 第 1 步：0 点自检（5 个只读端点 + 3 个探针 + 余额前后对比）
python3 scripts/run.py cost --prompt "你要问的那句话"     # 第 2 步：0 点报价，默认 5 个模型
python3 scripts/run.py chat --models GLM-5.2 --prompt "你要问的那句话" --yes   # 第 3 步：选一个开跑
```

跑完目录长这样：

```
text-models-20261108-113000/
├── 01-kimi_k3.md             序号-模型.md（问题 + 回答 + 用量）
├── manifest.json             结构化结果（含实际净额与 token 用量）
└── 对比清单.md               同一句话的五个模型，一张表看完
```

## 规格

| 项 | 值 |
|---|---|
| 文本入口 | `POST /api/v1/chat/completions`（唯一一条） |
| 单价来源 | `GET /api/v1/models` 的 `pricing`（每百万 token 的点数） |
| 模型数 | 92 个文本模型内置；`--models` 也接受目录外别名（如 `deepseek-chat`） |
| 输出上限 | `--out-tokens` 16 - 8192，默认 900 |
| 预算 | `--budget` 默认 600 点（6 元），单位是「点」；一次最多横评 8 个模型 |
| 计费口径 | 每次调用先冻 60 点；token 价按每百万算；失败全额退回 |

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 92 个文本模型 + 每百万 token 单价 + 实测可调性 |
| `check` | 免费 | 空 messages 探针验通不通（预冻 60 点，自动退回） |
| `cost` | 免费 | 同一句话多模型逐个报价 |
| `doctor` | 免费 | 5 个只读端点 + 3 个探针 + 流水净额 |
| `chat` | 按 token | 多模型横评，落盘 + manifest + 对比清单 |
| `log` | 免费 | 本地台账 |

退出码：`0` 成功 · `2` 用法错 · `4` 缺 `--yes`（说清要花多少）· `5` 超 `--budget`（一个请求都不发）· `6` 调用失败 · `1` 内部错 · `130` 中断。`--json` 契约：成功 `{"ok": true, …}`；失败 `{"ok": false, "exit": N, "error": {"kind": …, "message": …}}`；写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 和已有包的分工

| 你的需求 | 用哪个包 | 为什么 |
|---|---|---|
| 同一句话横评多个文本模型，挑一个或全跑 | **本包** | 92 个模型逐个报价 + 同 prompt 出回答 + 对比清单 |
| 通用 OpenAI 兼容接入：SDK、客户端、流式、base_url 怎么填 | `one-key-ai-gateway` | 协议层教程，一次配好所有客户端 |
| 用模型真写东西：课程讲义、解说稿、分镜、标题 | `sanjianke-course-outline` 等 | 单场景深度：提示词、校验、断点续跑 |
| 看应用层与模型层的差价排行、按意图挑最便宜的路 | `sanjianke-price-radar` | 115 条规则、app-vs-model 排行 |
| 对账：这个月到底花在哪 · 视频模型横评 | `sanjianke-billing` · `sanjianke-video-models` | 7 个只读端点按路径归集 · 13 个视频型号按条计价 |

本包管「选哪个模型」，上面几个包管「这个模型怎么用到极致」：本包报价选型，再用对应包跑完整产线。

## 免责

- 单价按「每百万 token」计，实际以 `GET /user/balance/logs` 的流水净额为准；上游按次预冻结，失败全额退回。
- 模型上下架由平台决定，`check` 随时可复核；生成内容的合规责任在使用者：用在合法、有授权的素材与用途上。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
