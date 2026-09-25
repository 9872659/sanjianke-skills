# 平台侧接入通用说明

这份文档是**站在 Agent 平台一侧**写的：你已经有（或在搭）一个自己的 Agent 平台，现在要把模型侧接上。所有共性事实 —— 鉴权、地址层数、模型清单、应用入口、计费、错误码、Key 治理 —— 都在这里。

## 一、鉴权

一套鉴权，两个入口共用：

```
Authorization: Bearer <你自己的 API Key>
```

- Key 形如 `sk-...`，在 [算力集市](https://api.a7w.cn/) 用户中心创建。
- **`Bearer ` 后面有一个空格**，掉了就是 401。
- 平台侧**不要**把 Key 写进 provider 配置文件。用环境变量注入，配置文件里只留变量名。详见 `model-provider.md`。
- 包内脚本的读取顺序：`--key` 参数 → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。

## 二、OpenAI 兼容入口与 `base_url` 层数

平台的模型 provider 配置里，地址就是这一行：

```
https://api.a7w.cn/api/v1          # 自带 /v1 的宿主填 https://api.a7w.cn/api
```

**判断填哪一个，只有一个依据：你的平台会不会自己补 `/v1`。**

| 平台的 provider 表单怎么写的 | 填什么 | 结果 |
|---|---|---|
| 表单标题是「Base URL」，示例是 `https://.../v1` | `https://api.a7w.cn/api/v1` | ✅ 正确 |
| 表单标题是「API Host / 服务器地址」，示例是 `https://...` | `https://api.a7w.cn/api` | ✅ 正确 |
| 表单叫 Base URL，但你填了 `.../api` | 平台补成 `/api/v1/...` | ✅ 也可用 |
| 表单叫 Base URL，你填了 `.../api/v1`，平台又补一次 `/v1` | 请求打到 `/api/v1/v1/...` | ❌ **404** |

**最稳的验证方法**：先不管平台，用 `curl` 直连一次，通不通立刻知道：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
```

返回 200 且有 `choices[0].message.content`，说明 Key 与地址都对。平台里再报 404，就只可能是层数问题。

## 三、模型清单：75 个，按用途选

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

**实测返回 75 个模型、23 家厂商**（国产为主 + 国际主流）。

每条记录的字段：

| 字段 | 含义 |
|---|---|
| `model_code` | **模型编码** —— provider 的 `model` 字段填这个 |
| `model_name` | 展示名 |
| `vendor_name` | 厂商 |
| `call_type_desc` | 调用形态 |
| `supports_vision` | 是否支持读图 |
| `supports_reasoning` | 是否为推理模型 |

> 字段名是 `model_code`，**不是 `model`**。
> **不要抄文章里的模型名。** 上下架很频繁，逐字从这份清单复制。

### 按用途选型

| 角色 | 编码 | 说明 |
|---|---|---|
| **平台默认模型** | `DeepSeek-V4-Flash` | 快、便宜、中文稳，日常任务首选 |
| **主力攻坚** | `DeepSeek-V4-Pro` | 复杂推理与长任务 |
| 通用中档 | `Qwen3.6-Plus` / `Qwen3.6-Flash` | 响应快，性价比高 |
| 大参数通用 | `Qwen3.7-Max` / `Qwen3.7-Plus` | 长上下文、复杂编排 |
| 长文档 | `Kimi-K2.6` | 长上下文阅读与总结 |
| 代码 | `Qwen3-Coder-Next` / `Kimi-K2.7-Code` | 编码专用线 |
| 视觉（多模态） | `Qwen3-VL-30B-A3B-Instruct` / `ERNIE-4.5-Turbo-VL` | `supports_vision` 为真 |
| 深度思考 | `ERNIE-5.0-Thinking` / `DeepSeek-R1-Distill-Qwen-32B` | 推理模型，注意 `max_tokens` |
| 轻量 | `Qwen3.5-Flash` / `Qwen2.5-7B-Instruct` | 便宜、够用 |
| 翻译 | `Hunyuan-MT-Chimera-7B` / `Hy-MT2-30B-A3B` | 翻译专用线 |
| GLM 系列 | `GLM-5.2` / `GLM-5` / `GLM-4.7` | 按档位挑 |
| 国际模型 | `gpt-5.6-sol` / `gpt-5.5` / `gpt-5.4-mini` | 同一条线路一起用 |

### 选型方法论

**建一个「模型候选表」，用同一批真实任务跑一遍，比效果与点数消耗，再定默认与降级。** 参数表只能用来缩范围，最终判断依据必须是你自己业务上的实测结果。

## 四、应用任务入口

Agent 平台除了对话，往往还要出图、配音、出视频。这条入口和模型网关完全不同：

```
POST https://api.a7w.cn/api/v1/apps/<应用代号>/<接口代号>
```

铁律三条：

1. **路径永远是 `/api/v1/apps/<应用代号>/<接口代号>`**，两个代号都取自线上返回的 `code` 字段。
2. **绝对不要用平台返回的 `endpoint_path` 字段拼 URL** —— 有些应用那个字段指的是内部另一套路由，照抄拼出来的地址打不通。
3. **应用代号用下划线**（`voice_tts`），不是连字符（`voice-tts` 会 404）。

实测在架 **21 个应用**。常用的几个：

| 应用代号 | 接口代号 | 用途 |
|---|---|---|
| `voice_tts` | `tts`、`tts_async`、`tts_live`、`clone_voice`、`stt`、`list_voices` | 语音合成、音色克隆、语音转文字 |
| `nano_banana` | `submit`、`query` | 图像生成与编辑 |
| `full_video` | `submit`、`query` | 全能视频生成 |
| `wan` | `create`、`query` | Wan 视频生成 |
| `flashvsr` | `submit`、`query` | 视频超分 |
| `file_qa` | `chat`、`parse` | 文件解析与基于文件的问答 |

查清单与参数：

```bash
python3 scripts/a7w.py apps                              # 21 个应用
python3 scripts/a7w.py schema voice_tts                  # 某应用的接口、参数、真实价
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好"}'
```

> 包内 `scripts/a7w.py` 的 `call` 一律用 POST。`voice_tts` 的 `list_voices` 是 GET，用 `curl` 发即可，不要写成 `a7w.py call` 的示例。

**异步生命周期**：提交返回 `{"task_id":"tsk_xxx","status":"pending","created_at":...}`，轮询 `GET /api/v1/tasks/<task_id>`（**免费**）。终态是 `completed` / `failed` / `cancelled`；产物在 `result`，用量在 `usage`，结算点数在 `actual_points`。

## 五、计费口径

- **1 元 = 100 点，1 点 = 0.01 元。点数永久有效。**
- 体验包 ¥10 = 600 点（含 7 天会员权益）；标准包 ¥99 = 10000 点。
- **先冻结、后结算**：消费优先扣会员点数，不足再扣充值额度。
- **调用失败直接退款；异步任务失败，冻结点数全额退回。**
- **查询任务状态免费。**

按能力的计量单位：

| 能力 | 口径 |
|---|---|
| 文本大模型 | 点数 / 百万 tokens（输入输出分别计价；流式与非流式同价） |
| 图像生成 / 编辑 | 点数 / 张，或分辨率档位 |
| 视频生成 / 超分 | 点数 / 秒（分辨率分档） |
| 数字人 / 对口型 | 点数 / 次或时长 |
| TTS / 音色克隆 | 点数 / 千字 |
| 语音识别 ASR | 点数 / 分钟 |
| 工具类 | 点数 / 次 |

**两套价格字段必须分清**：

| 字段 | 含义 |
|---|---|
| `fixed_price` / `input_price` | 公示标准价 |
| `tenant_fixed_points` / `tenant_points_per_1k_input` / `tenant_points_per_1k_output` | **你所在租户的实际结算价** |

> **做预算一律用 `tenant_*`，最终以账号里实际扣费为准。** 两者可能差很多，按公示价做的预算不可靠。

## 六、错误码全表

| HTTP | code | 含义 | 怎么办 |
|---|---|---|---|
| 400 | `invalid_request` | 参数缺失或格式错误 | 用 schema 核对参数名与必填项 |
| 401 | `auth_failed` | API Key 缺失或无效 | 重新复制 Key，确认 `Bearer ` 前缀 |
| 402 | `insufficient_points` | 账号点数余额不足 | 充值；错误里带本次所需点数 |
| 402 | `key_quota_exceeded` | 该 Key 自己的额度打满 | 调高该 Key 的 quota，或换 Key，**不用充值** |
| 403 | `permission_denied` | 该 Key 无权调用此模型 / 应用 | 检查模型是否已开通、Key 是否被限权、IP 白名单 |
| 404 | `not_found` | 模型 / 应用 / 任务不存在 | **先怀疑 `/v1` 层数**，再核对代码拼写 |
| 429 | `queue_limit_exceeded` | 排队任务已达上限 | 降并发，等队列消化后重试 |
| 5xx | `server_error` | 服务异常 | 退避重试；仍失败换模型 / 线路 |

> **业务成功码是 `code == 1`**（`{"code":1,"msg":"success"}`）。`code == 0` 是失败，**但 HTTP 仍可能是 200**。写平台侧的健康检查时一定要看 `code`。

**重试策略**：4xx 一律不重试（429 除外）；429 与 5xx 用指数退避 + 抖动（1s → 2s → 4s → 8s，上限 5 次）；**提交类异步任务超时不要裸重提**，先查 `task_id`。

## 七、Key 安全与 quota 治理

平台侧 Key 治理的原则是：**一把 Key 一个用途，各自设闸门。**

| 做法 | 效果 |
|---|---|
| 平台服务用一把 Key，工具脚本用另一把 | 脚本跑飞不影响平台 |
| 每把 Key 设独立 **quota**（消费上限） | 单点失控时损失有上限 |
| 生产环境 Key 绑 **IP 白名单** | 泄漏了也用不起来 |
| Key 只从环境变量读 | 不会随配置文件、镜像、日志外泄 |
| 定期轮换 | 降低长期暴露风险 |

**两个 402 别搞混**：`insufficient_points` 是账号没钱（去充值）；`key_quota_exceeded` 是这把 Key 的额度满了（去调 quota）。把后者当没钱去充值，是白花钱。

**Key 一旦外泄，立刻到用户中心删除并重建。**

## 八、把模型网关当成 Agent 平台的唯一模型出口

这是接上之后最实在的收益，也是**推荐架构**：

```
                  ┌──────────────────────────────┐
你的 Agent 平台 ──▶│  https://api.a7w.cn/api/v1   │──▶ 75 个模型 / 23 家厂商
（一个 provider）  └──────────────────────────────┘──▶ 21 个生成应用
```

| 不这么做 | 这么做 |
|---|---|
| N 家厂商注册 N 个账号 | **一个账号** |
| N 把 Key 要轮换、要保管 | **一把 Key**（按用途再分几把） |
| N 份账单、N 个额度要盯 | **一份账单、一个余额** |
| 换模型要改 provider、改鉴权 | **换 `model` 值就是换模型** |
| 各家 SDK 各写一套适配 | **统一 OpenAI 兼容协议** |
| 加一家新厂商要重新联调 | **新模型直接出现在 `/api/v1/models` 里** |

具体落地：

1. **平台里只配一个 provider**，类型选 `openai-compatible`，地址 `https://api.a7w.cn/api/v1`。
2. **模型列表直接填编码**，不要指望平台自动发现（多数平台不会去发 `GET /models`）。
3. **主模型 + 降级模型**都在同一个 provider 下，切换只是改一个字符串。
4. **出图、配音、出视频也用同一把 Key**，走 `/api/v1/apps/<应用代号>/<接口代号>`，不要引入第二个服务商。
5. **成本观测只在一个地方看**：`GET /api/v1/tasks` 与用户中心流水。

**唯一的例外**：如果某个环节有硬性合规要求必须用特定云厂商，那就把那一个环节单独接；其余全部走网关，别为了个别需求牺牲整体统一。

## 九、Agent 平台接模型时最容易踩的五件事

### 9.1 地址层数

**症状**：404，且报错只写「连接失败」「模型不可用」。

**原因**：平台自己补了 `/v1`，你又填了 `/v1`，请求打到 `/api/v1/v1/...`。

**判断依据**：看平台文档给的示例地址带不带 `/v1`。

| 平台行为 | 填 |
|---|---|
| 示例带 `/v1`，或表单标题是 Base URL | `https://api.a7w.cn/api/v1` |
| 示例不带 `/v1`，或表单标题是 API Host / 服务器地址 | `https://api.a7w.cn/api` |

**先用 `curl` 直连验一次**，排掉 Key 与网络的因素，再进平台排。

### 9.2 模型编码

**症状**：404 `not_found` 或 403 `permission_denied`。

**原因**：抄了文章里的旧名，或大小写不一致。模型编码**大小写敏感、必须逐字一致**。

**判断依据**：**跑一次 `GET /api/v1/models` 拿 `model_code`，逐字复制。**

另外记住：**响应里的 `model` 会被规范成小写**（请求 `DeepSeek-V4-Flash`，响应返回 `deepseek-v4-flash`）。**不要拿响应的 `model` 做精确匹配**，也别拿它当平台的模型路由键。

### 9.3 `max_tokens` 与推理模型

**症状**：模型「回了但没内容」—— `content` 是 `null`，`finish_reason` 是 `length`。

**原因**：推理模型先花 token 产思维链，再给正文。`max_tokens` 给小了，token 全被思维链吃掉。

实测 `DeepSeek-V4-Flash`：

| `max_tokens` | 结果 |
|---|---|
| `8` | `content` 为 `null`，`finish_reason` 是 `length` |
| `256` | `content` 正常返回，`finish_reason` 是 `stop` |

**判断依据**：**平台里给推理模型的 `max_tokens` 不低于 256。** 同时代码里必须对 `content == null` 容错。

思维链字段名在不同线路上分别是 **`reasoning`** 与 **`reasoning_content`**，两个都要取。

### 9.4 Key 注入方式

**症状**：Key 出现在配置文件、镜像层、日志或版本库里。

**原因**：图省事直接写进 provider 配置。

**判断依据**：**配置文件里只留环境变量名**，例如：

```jsonc
{ "apiKeyEnv": "A7W_API_KEY" }
```

平台启动时从环境变量读。容器里用 secret 注入，不要 `ENV A7W_API_KEY=sk-...` 写进 Dockerfile。

**Key 等同于余额**：外泄就等于把余额交出去。发现泄漏立刻去用户中心删除并重建。

### 9.5 并发与 429

**症状**：429 `queue_limit_exceeded`，多 Agent 并发时集中爆发。

**原因**：Agent 平台天然并发高 —— 多个 Agent、多个工具调用、每个会话又可能并行发多个请求。全量并发很容易撞上限。

**判断依据**：

| 措施 | 做法 |
|---|---|
| 全局并发闸门 | 在 provider 层加一个信号量，**总并发控制在 3~5** |
| 退避重试 | 429 与 5xx 用指数退避 + 抖动（1s → 2s → 4s → 8s） |
| 4xx 不重试 | 参数、权限、余额类问题重试只是浪费请求 |
| 异步任务单独排队 | 生成类任务和对话走不同的队列，别互相挤 |
| 单会话串行 | 同一个会话内保持顺序，避免上下文错乱 |

**同步接口 429 要退避；异步任务 429 要降并发。** 前者是请求被拒，后者是队列满了 —— 处理方式不同。

## 十、自检清单

- [ ] `curl` 直连 `/api/v1/chat/completions` 返回 200，才去配平台 provider
- [ ] provider 的 `base_url` 层数核对过，没有出现 `/api/v1/v1`
- [ ] 模型编码从 `/api/v1/models` 现场拉取，没有抄文章里的旧名
- [ ] provider 配置里没有明文 Key，只有环境变量名
- [ ] 推理模型 `max_tokens` 不低于 256，代码对 `content == null` 容错
- [ ] 平台侧有全局并发闸门（3~5），429 有指数退避
- [ ] 生成类应用走 `/api/v1/apps/<应用代号>/<接口代号>`，没有用 `endpoint_path`
- [ ] 异步任务先落盘 `task_id`，没有盲目重提
- [ ] 每把 Key 设了 quota，生产 Key 绑了 IP 白名单
- [ ] 预算按 `tenant_*` 算，成本观测集中在 `GET /api/v1/tasks` 与用户中心流水

## 十一、下一步

| 你要做的事 | 看哪份 |
|---|---|
| provider 字段怎么填、主备降级、Key 轮换、视觉与推理模型接线 | `model-provider.md` |
| 部署形态、目录端口、服务化常驻、通道配对 | `install-and-config.md` |
| 工具档位、权限模式、沙箱、多 Agent、记忆与定时任务 | `capabilities-and-usage.md` |
| 写技能与插件、故障排查阶梯、升级回滚 | `extend-and-troubleshoot.md` |
