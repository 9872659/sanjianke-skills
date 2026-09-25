# 模型 provider 配置专题

这份文档只解决一件事：**Agent 平台的模型 provider 那一栏，到底该怎么填、怎么配降级、怎么接线。** 所有字段名按你实际使用的平台命名，这里给的是通用形态与判断依据。

## 一、provider 字段怎么填

一个 provider 条目，实质只有四样东西：

| 字段（通用叫法） | 填什么 | 要点 |
|---|---|---|
| `base_url` / `api_base` / `baseURL` | `https://api.a7w.cn/api/v1` | **层数看第二节** |
| `api_key` / `apiKey` / `token` | 不要填明文 | 填**环境变量名**，见第五节 |
| `model` / `model_id` / `default_model` | `DeepSeek-V4-Flash` | 以 `GET /api/v1/models` 的 `model_code` 为准 |
| fallback / 降级模型 | `DeepSeek-V4-Pro`、`Qwen3.6-Plus` | 主模型不可用时自动切 |

### JSON 配置示意

```jsonc
{
  "providers": {
    "a7w": {
      "type": "openai-compatible",
      "baseUrl": "https://api.a7w.cn/api/v1",
      "apiKeyEnv": "A7W_API_KEY",          // 只写变量名，不写 Key 本身
      "model": "DeepSeek-V4-Flash",        // 默认模型
      "fallbackModels": [                  // 降级顺序，自上而下
        "DeepSeek-V4-Pro",
        "Qwen3.6-Plus"
      ],
      "timeout": 120,                      // 秒；推理模型要给够
      "maxTokens": 1024                    // 默认输出上限，别低于 256
    }
  },
  "agents": {
    "assistant": { "provider": "a7w", "model": "DeepSeek-V4-Flash" },
    "coder":     { "provider": "a7w", "model": "Qwen3-Coder-Next" },
    "reader":    { "provider": "a7w", "model": "Qwen3-VL-30B-A3B-Instruct" },
    "thinker":   { "provider": "a7w", "model": "ERNIE-5.0-Thinking" }
  }
}
```

### YAML 形态（很多平台用这个）

```yaml
providers:
  a7w:
    type: openai-compatible
    base_url: https://api.a7w.cn/api/v1
    api_key: ${A7W_API_KEY}        # 引用环境变量，不要写明文
    model: DeepSeek-V4-Flash
    fallback:
      - DeepSeek-V4-Pro
      - Qwen3.6-Plus
    max_tokens: 1024
    timeout: 120
```

> **一个 provider 就够。** 平台里不要为每一家模型厂商各建一个条目 —— 75 个模型都在同一个 `base_url` 下，换个 `model` 值就是换模型。

### 配好之后的验收动作

```bash
# 1) 平台外先验通
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'

# 2) 平台内发一句「你好」，确认走通
# 3) 看平台的请求日志：实际打到哪个 URL。出现 /api/v1/v1 就是层数错了
```

## 二、`/api/v1` 与 `/api` 两种填法的判断方法

两个地址都对，区别只在**你的平台会不会自己补 `/v1`**。

| 判断依据 | 结论 |
|---|---|
| 平台文档示例写的是 `.../v1/chat/completions` 或 `.../v1` | 填 **`https://api.a7w.cn/api/v1`** |
| 表单标题是「Base URL / 接口地址 / API 地址」 | 填 **`https://api.a7w.cn/api/v1`** |
| 平台文档示例写的是 `.../chat/completions`（不带 `v1`） | 填 **`https://api.a7w.cn/api`** |
| 表单标题是「API Host / 服务器地址 / 域名」 | 填 **`https://api.a7w.cn/api`** |
| 平台源码里能看到 `base_url + "/v1/chat/completions"` | 填 **`https://api.a7w.cn/api`** |

### 三分钟判断法

1. **先填 `https://api.a7w.cn/api/v1`，发一句「你好」。**
2. 成功 → 结束，你不需要往下看了。
3. 报 **404** → 换 `https://api.a7w.cn/api` 再发一次。
4. 仍然 404 → 那问题不在层数，去核对模型编码与 Key 权限。

**最快的证据在平台日志里**：如果实际请求 URL 里出现了 `/api/v1/v1/` 或 `/api/api/`，就是重复拼接，改成少一层的写法即可。

| 填法 | 平台行为 | 实际请求 | 结果 |
|---|---|---|---|
| `https://api.a7w.cn/api/v1` | 不补 | `/api/v1/chat/completions` | ✅ |
| `https://api.a7w.cn/api/v1` | 补 `/v1` | `/api/v1/v1/chat/completions` | ❌ 404 |
| `https://api.a7w.cn/api` | 补 `/v1` | `/api/v1/chat/completions` | ✅ |
| `https://api.a7w.cn/api` | 不补 | `/api/chat/completions` | ❌ 404 |

> **记忆口诀：示例带 `/v1` 就填 `/api/v1`，示例不带就填 `/api`。** 只有这两种情况。

## 三、多模型与主备降级

### 推荐配置

| 位置 | 模型 | 理由 |
|---|---|---|
| **主模型** | `DeepSeek-V4-Flash` | 快、便宜、中文稳，日常任务成功率最高 |
| **降级 1** | `DeepSeek-V4-Pro` | 同一家的加强档，接口行为一致，切换风险最低 |
| **降级 2** | `Qwen3.6-Plus` | 换厂商线，能覆盖单家线路抖动的情况 |

**降级链的设计原则：先同家加强档，再跨家。** 同家切换的接口行为最接近；跨家切换能兜住线路级故障，但要注意字段差异（见第三节末尾）。

### 平台里的两种降级方式

| 方式 | 触发时机 | 适用 |
|---|---|---|
| **自动降级** | 主模型报错（5xx / 超时 / 429）时平台自动切下一个 | 生产环境的兜底 |
| **手动切换** | 由 Agent 或用户按任务类型指定 `model` | 分场景选型，例如代码任务固定用 `Qwen3-Coder-Next` |

**两者都要配。** 自动降级保证可用性，手动切换保证效果 —— 只配一个都会难受。

### 降级链要注意的三件事

1. **触发条件要明确。** 建议只在 **5xx / 超时 / 429** 时降级；**401 / 402 / 403 / 404 不要降级** —— 那是 Key、余额、权限、编码的问题，换模型一样失败，反而把真实原因盖住了。
2. **降级要记日志。** 每次降级都记「原模型 → 实际模型 → 触发错误码」。不记日志，你会分不清「效果变差了」是因为降级还是别的原因。
3. **降级模型的 `max_tokens` 要单独给。** 不要复用主模型的值 —— 推理模型的输出预算和普通模型不一样。

> **降级不是免费的**：切到更强的模型，点数消耗也更高。降级链只放两个候选就够，别把 75 个模型全排上。

### 按场景分 Agent 用模型

同一把 Key 下，让不同 Agent 用不同模型，是最省心也最省钱的用法：

| Agent 角色 | 模型 | 说明 |
|---|---|---|
| 日常对话 / 助手 | `DeepSeek-V4-Flash` | 默认档 |
| 代码 / 重构 | `Qwen3-Coder-Next` | 代码专用线 |
| 长文阅读 / 总结 | `Kimi-K2.6` | 长上下文 |
| 读图 / 截图理解 | `Qwen3-VL-30B-A3B-Instruct` | 视觉 |
| 规划 / 深度推理 | `ERNIE-5.0-Thinking` | 推理 |
| 翻译 | `Hunyuan-MT-Chimera-7B` | 翻译专用 |
| 轻量批处理 | `Qwen3.5-Flash` | 便宜 |

## 四、Key 轮换与环境变量注入

### 注入方式（按优先级推荐）

| 方式 | 适用 | 说明 |
|---|---|---|
| **环境变量**（`${A7W_API_KEY}`） | 生产、容器、CI | **首选**，配置文件里只有变量名 |
| 平台 secret / keyring | 有密钥管理能力的平台 | 次选，同样不落明文 |
| 本机 `~/.a7w/config.json` | 本机自用脚本 | 权限收紧到 `600` |
| `--key` 参数 | 临时验证 | 会进 shell history，仅用于一次性排查 |

**永远不要**：写进 provider 配置文件、写进 Dockerfile 的 `ENV`、写进前端代码、提交进版本库。

```bash
# Linux / macOS
export A7W_API_KEY=sk-你的key

# Windows PowerShell
$env:A7W_API_KEY="sk-你的key"

# 持久化（Windows 用户级，重启仍有效）
[Environment]::SetEnvironmentVariable("A7W_API_KEY","sk-你的key","User")
```

### 轮换步骤（不中断服务）

平台侧支持多 Key 时，按这个顺序换：

1. **在用户中心新建一把 Key**，设好 quota 与 IP 白名单。
2. **把它配到平台的环境变量或 secret 里**（新增一份，先不要把旧的删掉）。
3. **滚动重启平台**，让新 Key 生效。
4. **观察 `GET /api/v1/tasks` 与用户中心流水**，确认新 Key 有正常用量、没有 401。
5. **确认无异常后，在用户中心删除旧 Key。**

### Key 分级建议

| 用途 | 建议 |
|---|---|
| 平台主服务 | 一把 Key，绑生产 IP，设足额 quota |
| 工具 / 脚本 | 另一把 Key，低 quota，用完即删 |
| CI / 临时环境 | 一次性 Key，跑完就删 |
| 本地开发 | 单独一把，低 quota |

**每把 Key 一个用途**，这样：出问题时影响面可控、看用量就知道是谁在花、轮换时不用一次全换。

> **Key 等同于余额。** 外泄立刻到用户中心删除并重建，别犹豫。

## 五、视觉模型与推理模型：区别与接线注意

这两类是**接线时最容易出问题**的两类，因为它们的请求与响应形态和普通文本模型不同。

### 5.1 区别速查

| | 视觉模型 | 推理模型 |
|---|---|---|
| 代表编码 | `Qwen3-VL-30B-A3B-Instruct`、`ERNIE-4.5-Turbo-VL` | `ERNIE-5.0-Thinking`、`DeepSeek-R1-Distill-Qwen-32B` |
| 清单标识 | `supports_vision` 为真 | `supports_reasoning` 为真 |
| 入参特点 | `messages` 里要带 **图片内容** | 只用文本，但**先出思维链再出正文** |
| 主要风险 | 图片怎么传、传多大 | `max_tokens` 给小了正文为空 |
| 计费特点 | 图片也占 token，图越大越贵 | 思维链 token **同样计费** |

### 5.2 视觉模型的接线注意

**① 清单里先确认 `supports_vision`。** 不支持视觉的模型收到图片内容会报 400 `invalid_request`，而不是「我看不懂」。

**② 图片在 `messages` 里是内容数组，不是纯字符串。** 形态示意：

```jsonc
{
  "model": "Qwen3-VL-30B-A3B-Instruct",
  "messages": [
    { "role": "user",
      "content": [
        { "type": "text", "text": "这张图里有什么？" },
        { "type": "image_url", "image_url": { "url": "https://你的存储/图.png" } }
      ] }
  ]
}
```

**③ 图片尽量用公网可访问的 URL**，或按平台支持的方式传。**不要把整张图做 Base64 塞进请求体** —— 请求体会膨胀到几十 MB，超时和 413 都容易撞上。

**④ 图片计入 token。** 高分辨率图的 token 消耗可能远超你的文字部分，**成本估算时不能只算文本**。

**⑤ 分 Agent 使用。** 让「读图」这个 Agent 固定用视觉模型，其他 Agent 用文本模型 —— 不要让所有请求都往视觉模型上打，那样又慢又贵。

### 5.3 推理模型的接线注意

**① `max_tokens` 不低于 256。** 实测 `DeepSeek-V4-Flash`：

| `max_tokens` | 结果 |
|---|---|
| `8` | `content` 为 **`null`**，`finish_reason` 是 **`length`** |
| `256` | `content` 正常返回，`finish_reason` 是 `stop` |

**② 代码必须对 `content == null` 容错。** 不要假定它是字符串，写 `content.strip()` 会直接崩。

**③ 思维链字段名有两个，都要取：**

```python
msg = resp["choices"][0]["message"]
reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
content = msg.get("content") or ""
```

**④ 超时要给宽。** 推理模型慢是正常的，超时设 30 秒会把正常的慢思考切成失败。**建议 120 秒起**，同时配合降级链。

**⑤ 思维链也计费。** 同样一个问题，推理模型的 token 消耗可能是普通模型的几倍。**只在真的需要深度推理的任务上用**，别让它当默认模型。

**⑥ 响应里的 `model` 会规范成小写。** 请求 `DeepSeek-V4-Flash`，响应返回 `deepseek-v4-flash`。**不要拿响应的 `model` 做精确匹配或路由键。**

### 5.4 一张接线对照表

| 检查项 | 视觉模型 | 推理模型 | 普通文本模型 |
|---|---|---|---|
| 清单字段 | `supports_vision` | `supports_reasoning` | 都不为真 |
| `max_tokens` 下限 | 512 | **256** | 128 |
| 建议超时 | 120s | **120s** | 60s |
| `content` 可能为 null | 否 | **是** | 否 |
| 需要取思维链字段 | 否 | **是** | 否 |
| 图片入 token | **是** | 否 | 否 |
| 适合当默认模型 | 否 | 否 | **是** |

## 六、用量与成本观测

### 6.1 三个数据源

| 数据源 | 看什么 | 用途 |
|---|---|---|
| `GET /api/v1/tasks/<task_id>` | `status`、`result`、`usage`、`actual_points` | 单次任务的**真实消耗** |
| `GET /api/v1/tasks` | 最近任务列表 | 批量对账、估算日均消耗 |
| 用户中心流水 | 实际扣点 | **最终权威口径** |

```bash
# 最近任务的真实消耗
python3 scripts/a7w.py points

# 单个任务详情
python3 scripts/a7w.py task tsk_xxxxxxxx
```

### 6.2 字段含义

| 字段 | 含义 |
|---|---|
| `actual_points` | **本次结算点数** —— 任务列表里的真实字段名 |
| `usage` | 用量明细（tokens / 秒 / 千字 / 张，随能力类型不同） |
| `status` | `pending` / `processing` / `completed` / `failed` / `cancelled` |

### 6.3 关于 `points_cost`

平台在部分接口的响应里会给 `data.usage.points_cost`，表示**本次调用的计费点数**。

> **两个字段名都要认**：任务列表里是 **`actual_points`**，调用响应里是 **`usage.points_cost`**。写对账脚本时两个都取，不要只找其中一个。

### 6.4 观测节奏建议

| 频率 | 动作 |
|---|---|
| 每天 | 看一次 `GET /api/v1/tasks`，扫一眼异常消耗（个位数点数的正常，几百点的要查） |
| 每周 | 按 Agent / 按模型汇总一次点数，找出最贵的那个 |
| 每次调价或换模型 | 用同一批任务重跑一次，比较点数与效果 |
| 每月 | 与用户中心流水对账，核对总消耗 |

### 6.5 控成本的三招

1. **压 `max_tokens`** —— 尤其是推理模型，它是隐形大头。
2. **精简 system prompt** —— 它每次都随请求计费，长系统提示的年化开销很可观。
3. **长对话做摘要** —— 不要每次把几十轮历史原样发上去。

### 6.6 实测消耗参考

| 场景 | 消耗 |
|---|---|
| `DeepSeek-V4-Flash` 一次普通问答 | 约 **0.74 ~ 0.99 点** |
| 极小调用（`max_tokens=8`） | **0.00 点** |
| 查询任务状态 | **免费** |

> **预算一律按 `tenant_*` 字段算**（`fixed_price` / `input_price` 是公示标准价，可能和你的实际结算价差很多），**最终以账号里实际扣费为准**。

## 七、排错：404 / 401 / 402（两种）/ 403 / 429

按错误码对号入座，命中率最高。

### 404 `not_found` —— 地址层数或模型编码

**两种原因，先查第一个：**

| 原因 | 怎么确认 |
|---|---|
| **`base_url` 层数错了**（多填或少填 `/v1`） | 看平台请求日志里实际打到的 URL，是否出现 `/api/v1/v1/` |
| 模型编码不存在或大小写不一致 | `curl /api/v1/models` 现场核对 `model_code` |

**处理**：先按第二节的层数表改 `base_url`；405/404 依旧，再核对模型编码。

### 401 `auth_failed` —— Key 缺失或无效

| 原因 | 怎么确认 |
|---|---|
| 环境变量名写错（配置文件写 `A7W_API_KEY`，实际注入的是别的名字） | 在平台进程里打印一次变量是否存在（**不要打印值**） |
| `Bearer ` 前缀缺了或没空格 | 手工 `curl` 一次对比 |
| Key 已被删除或过期 | 用 `python3 scripts/a7w.py whoami` 验一次 |

**处理**：重新复制 Key；确认前缀。**与余额、权限无关。**

### 402 `insufficient_points` —— 账号余额不足

**含义**：账号点数不够了。

**处理**：充值。错误信息里会带本次所需点数。用 `GET /api/v1/user/balance` 看 `available_points`。

### 402 `key_quota_exceeded` —— 这把 Key 的额度满了

**含义**：**账号还有钱**，但你给这把 Key 设的 quota 打满了。

**处理**：去用户中心调高 / 重置**这把 Key 的 quota**，或换一把 Key。**不用充值。**

> **这两个 402 是最容易搞混的一对。** 看到 402 先去用户中心看一眼：余额是够的，那就是 quota 问题，充值没用。

### 403 `permission_denied` —— 权限问题，和余额无关

| 原因 | 怎么确认 |
|---|---|
| 这把 Key 没有该模型的权限 | 换主模型试一次 |
| Key 绑了 **IP 白名单**，当前出网 IP 不在名单里 | 对比平台部署的出口 IP 与白名单 |
| 该模型未开通 | 用户中心看该模型的可用状态 |

**处理**：按上面三类分别修。**不要充值，充值不解决 403。**

### 429 `queue_limit_exceeded` —— 并发或排队达上限

**含义**：请求量超过了当前允许的并发 / 队列容量。

**处理**：

| 措施 | 做法 |
|---|---|
| 全局并发闸门 | provider 层加信号量，总并发控制在 **3~5** |
| 指数退避 + 抖动 | 1s → 2s → 4s → 8s，上限 5 次 |
| 异步任务单独排队 | 生成类任务与对话走不同队列，别互相挤 |
| 单会话串行 | 同一会话保持顺序，避免上下文错乱 |

**注意区分**：**同步接口的 429 是请求被拒，退避重试即可；异步任务的 429 是队列满了，要降并发。** 处理方式不同。

### 排错顺序速查

```
provider 报错
├─ 404 → ① base_url 层数（看请求日志里的 /api/v1/v1）② 模型编码（现场拉清单）
├─ 401 → Key 没读到 / 前缀错 / Key 已删
├─ 402 → 先看用户中心余额：
│        余额够 → key_quota_exceeded，调 quota
│        余额不够 → insufficient_points，充值
├─ 403 → 模型权限 / IP 白名单，与余额无关
├─ 429 → 降并发 + 退避重试
├─ 5xx → 退避重试；持续失败触发降级链
└─ 200 但没内容 → max_tokens 太小（推理模型调到 256 以上）
```

## 八、自检清单

- [ ] provider 只有一个（`a7w`），类型是 `openai-compatible`
- [ ] `base_url` 层数按第二节判断过，平台日志里没有 `/api/v1/v1/`
- [ ] 配置文件里**没有明文 Key**，只有环境变量名
- [ ] `model` 是从 `/api/v1/models` 现场拉的 `model_code`，逐字一致
- [ ] 降级链只有 2 个候选，且只在 5xx / 超时 / 429 时触发
- [ ] 降级触发了日志（记录原模型、实际模型、触发错误码）
- [ ] 推理模型 `max_tokens` 不低于 256，超时给了 120s
- [ ] 视觉模型走独立的 Agent，图片用 URL 而不是 Base64
- [ ] 代码里 `content == null` 与 `reasoning` / `reasoning_content` 都处理了
- [ ] 平台侧有全局并发闸门（3~5），429 有指数退避
- [ ] 每把 Key 一个用途，各自设 quota；生产 Key 绑了 IP 白名单
- [ ] 成本观测同时看 `actual_points` 与 `usage.points_cost`，并按 `tenant_*` 做预算
