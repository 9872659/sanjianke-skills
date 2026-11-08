# 文本模型台 · 92 个模型一句话横评，最便宜 0.40 元/百万 token

**同一句话，92 个文本模型先报价再开口。**
每百万 token 输出最便宜 40 点（0.40 元），最贵 15,840 点（158.40 元）—— 差 **396 倍**，看完价再决定跑一个还是全跑。

实测：`HY-MT2-7B` **40 点/百万**、`kimi-k3` **10,000 点/百万**、`claude-fable-5-official` **15,840 点/百万**；
而一次 900 token 的对话，每个模型都落在 **60 点**保底 —— 短对话比的是谁答得好，不是单价。

---

## 三条干货

### 一、文本层只有一条入口，`/v1/messages` 是空的

2026-11-08 用「合法参数 + 缺关键参数」的形态逐个探（全部停在校验层，0 点花费）：

```
POST /api/v1/chat/completions  {"model":"deepseek-chat"}   -> 422 missing field `messages`
POST /v1/chat/completions      {"model":"deepseek-chat"}   -> 422 同上（少 /api 也落到同一条）
POST /api/chat/completions     {"model":"deepseek-chat"}   -> 422 同上
POST /api/v1/messages          {"model":"claude-..."}      -> 404 站点首页 HTML
POST /v1/messages              {"model":"claude-..."}      -> 404 {"code":"unknown_endpoint"}
POST /api/v1/embeddings        {"model":"text-embedding-3-small"} -> 404 站点首页 HTML
```

所以 `claude-*` 的 13 个变体虽然只声明 `anthropic_messages` 协议，也只能走 `/api/v1/chat/completions`：

```
POST /api/v1/chat/completions  {"model":"claude-sonnet-4-5","messages":[]}
-> HTTP 200  {"code":0,"msg":"模型不存在或未上架","data":null}
```

**状态码 200 不等于成功，`code` 是 0 就是没过。**

### 二、字段名叫 per_1k，数值其实是每百万

`GET /api/v1/models` 的 316 条里，92 条 text 模型都自带价：

```json
"pricing": {
  "per_1k_input": 1584,
  "per_1k_output": 7920,
  "pricing_v2": {"items": [{"usage_unit_size": 1000000,
                  "effective_rate_config": {"input": 1584, "output": 7920}}],
                 "price_view": {"summary": "按百万 Token 7920 点/百万 Token"}}
}
```

`usage_unit_size` 是 1,000,000，`price_view` 也写「按百万 Token」—— 字段名带 `1k`、数值却是 1M 的价，
按 1K 算会错 1000 倍。同一段 `reference_price` 还给官方参考价与省钱比例：

| 模型 | 官方参考价 | 本站价（每百万 token） | 省 |
|---|---|---|---|
| `claude-opus-5` | $5 输入 / $25 输出 | 1,584 / 7,920 点（15.84 / 79.20 元） | 53.4% |
| `claude-sonnet-4-5` | $3 / $15 | 674 / 3,386 点（6.74 / 33.86 元） | 66.8% |
| `gemini-3-pro` | $2 / $12 | 396 / 2,772 点（3.96 / 27.72 元） | 66.0% |

### 三、先冻 60 点，再谈 token

`GET /api/v1/pricing` 的 **115 条规则**里没有 `/api/v1/chat/completions`，命中的是通配 `*`：

```json
```

实测每次调用都是先冻后结，失败自动全额退回：

```
11:27:20  charge  -60  reserve_sync:/api/v1/chat/completions
11:27:21  refund  +60  refund:sync:/api/v1/chat/completions
```

所以 900 token 的一问一答，按 token 算只有 0.1 - 9 点，真实下限就是这 60 点。
`chat` 每次跑完都读 `GET /user/balance/logs`，把**实际净额**写进 `manifest.json` 与 `对比清单.md`。

---

## 价目表（2026-11-08，1 元 = 100 点，单位：点/百万 token）

| 模型 | 输入 | 输出 | 折算输出 | 这条路 |
|---|---|---|---|---|
| `HY-MT2-7B`（腾讯混元翻译） | 40 | **40** | 0.40 元 | 未测，最便宜的一档 |
| `Qwen2.5-7B-Instruct` | 45 | 45 | 0.45 元 | 未测 |
| `gemma-4-26B-A4B-it` | 60 | 60 | 0.60 元 | 503 暂无可用渠道 |
| `GLM-5.2` | 800 | **105** | 1.05 元 | √ 能调 |
| `Qwen3.5-Flash` | 30 | 210 | 2.10 元 | √ 能调（输入最便宜的一线） |
| `LegalOne-8B` | 210 | 210 | 2.10 元 | √ 能调 |
| `KAT-Dev` | 110 | 410 | 4.10 元 | √ 能调 |
| `Sinong1.0-32B` | 810 | 810 | 8.10 元 | √ 能调 |
| `ERNIE-5.0-Thinking` | 410 | 1,610 | 16.10 元 | 401 未上架 |
| `MiniMax-M3` | 430 | 1,690 | 16.90 元 | √ 能调 |
| `MiMo-V2.5-Pro` | 710 | 2,110 | 21.10 元 | 404 站点首页 |
| `claude-sonnet-4-5` | 674 | 3,386 | 33.86 元 | 200 但 code 0 |
| `Qwen3.7-Max` | 1,200 | 3,600 | 36 元 | 404 未上架 |
| `claude-opus-5` | 1,584 | 7,920 | 79.20 元 | 只声明 anthropic_messages |
| `kimi-k3` | 2,000 | 10,000 | 100 元 | √ 能调 |
| `claude-fable-5-official` | 3,168 | **15,840** | 158.40 元 | 只声明 anthropic_messages |

家族覆盖：Claude 13 个变体、通义千问 17 个、Kimi 5 个、GPT 15 个、智谱 GLM 5 个、DeepSeek 5 个、
Gemini 7 个、MiniMax 4 个、腾讯混元 4 个、文心 ERNIE 3 个、Grok 3 个，以及 Gemma、MiMo、LegalOne、
AutoGLM、KAT、Sinong1.0、MAI、PaddleOCR 各 1 个。

`--budget` 单位是「点」，默认 600 点（6 元）。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 0 点自检（5 个只读端点 + 3 个探针 + 余额前后对比）
python3 scripts/run.py doctor

# 3) 0 点报价：同一句话，5 个模型逐个报
python3 scripts/run.py cost --prompt "给一条 15 秒护肤口播写脚本"

# 4) 横评：同一句话，5 个模型出回答，落盘 + 对比清单
python3 scripts/run.py chat --models kimi-k3,GLM-5.2,Qwen3.5-Flash,MiniMax-M3,LegalOne-8B \
    --prompt "给一条 15 秒护肤口播写脚本，三句话，最后一句带行动号召" --yes
```

---

## 用法示例

```bash
# 看 92 个模型的单价 / 家族 / 实测可调性（免费，可离线）
python3 scripts/run.py catalog --limit 40
python3 scripts/run.py catalog --family claude --limit 13

# 免费验通不通：messages 为空，停在校验层，净 0 点
python3 scripts/run.py check --models kimi-k3,GLM-5.2,claude-opus-5,gpt-5.5

# 只报 3 个模型（免费）
python3 scripts/run.py cost --models kimi-k3,GLM-5.2,Qwen3.5-Flash --out-tokens 1200

# 直接指定 token 估算（跳过按字数推算）
python3 scripts/run.py cost --models kimi-k3 --in-tokens 3000 --out-tokens 1500

# 先看请求，一分钱不花
python3 scripts/run.py chat --models kimi-k3 --prompt "写一句广告语" --dry-run

# 带系统提示词 + 低温度 + 更大输出
python3 scripts/run.py chat --models GLM-5.2 --system "你是短视频编导" \
    --prompt "给一条 30 秒口播脚本" --temperature 0.3 --out-tokens 2000 --yes

# 本地台账（免费）
python3 scripts/run.py log --limit 10
```

### 落盘规范

```
text-models-20261108-113000/
├── 01-kimi_k3.md             序号-模型.md：问题 + 回答 + token 用量 + 单价
├── 02-glm_5_2.md
├── manifest.json             结构化结果（含实际净额、流水明细、每个模型的判定）
└── 对比清单.md               同一句话的五个模型，一张表看完
```

型号里的 `.` 与 `/` 会换成 `_`，文件名全平台可用。

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--models` | 5 个默认模型 | 逗号分隔，一次最多 8 个；`check` 最多 12 个 |
| `--prompt` | 必填 | 所有模型共用同一句，≤8000 字 |
| `--system` | — | 系统提示词，所有模型共用 |
| `--out-tokens` | 900 | 每个模型的输出上限（16 - 8192） |
| `--in-tokens` | 按字数估 | 直接指定输入 token |
| `--temperature` | 0.7 | 采样温度 |
| `--extra` | — | 额外请求字段，JSON 对象，例如 `{"top_p":0.9}` |
| `--outdir` | `.` | 落盘根目录 |
| `--budget` | 600 | 点数上限（单位：点） |
| `--yes` | — | 确认真实调用 |
| `--dry-run` | — | 只打印请求 |
| `--json` | — | 只输出一个 JSON 文档 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 92 个文本模型 + 每百万 token 单价 + 家族 + 实测可调性 |
| `check` | 免费 | 空 messages 探针验通不通（预冻 60 点，自动退回） |
| `cost` | 免费 | 同一句话多模型逐个报价（60 点保底 + token 价） |
| `doctor` | 免费 | 5 个只读端点 + 3 个探针 + 余额与流水净额 |
| `chat` | 按 token | 多模型横评，落盘 + manifest + 对比清单 |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺 prompt / 模型数超限 / token 越界 / 命令行缩写） |
| `4` | 需要确认 —— 没给 `--yes`，会先告诉你这次要花多少 |
| `5` | 超预算 —— 一个请求都不发 |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "dir": "./text-models-20261108-113000",
 "models": [{"model": "kimi-k3", "ok": true, "http": 200,
             "usage": {"inTok": 21, "outTok": 380, "total": 401},
             "estimatePoints": 60, "file": "01-kimi_k3.md"}],
 "estimatePoints": 300, "actualPoints": -300, "actualYuan": -3.0}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "预计 60 点（0.60 元）超过 --budget 10 点，一个请求都不发。"}}
```

`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

---

## 和已有包的分工

| 你的需求 | 用哪个包 | 为什么 |
|---|---|---|
| 同一句话横评多个文本模型，挑一个或全跑 | **本包** | 92 个模型逐个报价 + 同 prompt 出回答 + 对比清单 |
| 通用 OpenAI 兼容接入：SDK、客户端、流式、base_url 怎么填 | `one-key-ai-gateway` | 协议层教程，一次配好所有客户端 |
| 用模型真写东西：课程讲义、解说稿、分镜、标题 | `sanjianke-course-outline` 等 | 单场景深度：提示词、校验、断点续跑 |
| 看应用层与模型层的差价排行、按意图挑最便宜的路 | `sanjianke-price-radar` | 115 条规则、app-vs-model 排行 |
| 对账：这个月到底花在哪 | `sanjianke-billing` | 7 个只读端点、按路径归集净额 |
| 视频模型横评 | `sanjianke-video-models` | 13 个视频型号、按条计价 |

---

## 文件结构

```
sanjianke-text-models/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测原文 + 计量口径 + 92 个模型价目）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，16,797 B 逐字节一致）
    └── run.py                本包命令层
```

---

## 实测记录

```
2026-11-08 doctor（5 个只读端点 + 3 个探针）
  √ Key + 余额       HTTP 200 · 可用 999,997,393,378.73 点 · 冻结 0 点 · 1 元 = 100 点
  √ 模型目录         HTTP 200 · 共 316 条 · 文本模型 92 个 · 计价单位 1M 的 92 个
  √ 价目表           HTTP 200 · 115 条规则 · 文本入口没有专属规则 · 通配保底 50 点
  √ 任务台账         HTTP 200 · 本页 20 条 · 累计 1,398 条
  √ 流水             HTTP 200 · 最近 100 条里文本线 80 笔 · 余额口径 -175,951.31 点
  √ 入口探针 1       HTTP 200 · model参数不能为空
  √ 入口探针 2       HTTP 422 · 422 缺 messages（入口在、模型未校验）
  √ /v1/messages     HTTP 404 · unknown_endpoint
  √ 余额前后对比      前 999,997,393,378.73 -> 后同值 · 差 0 点
  √ 流水净额         预扣 -120 点 · 退回 120 点 · 净 0 点（4 笔）
  本轮花费 0 点
```

```bash
$ python3 scripts/run.py check --models kimi-k3,claude-opus-5,gpt-5.5
  √ HTTP 400  停在参数校验：Role must be in ["user", "assistant", "system", ...
  × HTTP 200  200 但 code=0：模型不存在或未上架
  × HTTP 403  上游欠费：账户余额不足，如需继续使用请及时充值
  结论：1 / 3 个模型这条路能通
  预冻：3 个 x 60 点 = 180 点，流水净额 0 点（已全额退回）
```

```bash
$ python3 scripts/run.py cost --models kimi-k3,GLM-5.2 --prompt "给一条 15 秒护肤口播写脚本"
  合计（按闸门）：120 点 = 1.20 元
  同一句话，每个模型都落在 60 点保底 —— 短对话比的是谁答得好，不是单价
```

---

## 免责

- 单价按「每百万 token」计，实际以响应里的 `usage` 与 `GET /user/balance/logs` 的净额为准。
- 生成内容的合规责任在使用者：用在合法、有授权的素材与用途上。
## 许可证

MIT，见 `LICENSE.md`。

---

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
