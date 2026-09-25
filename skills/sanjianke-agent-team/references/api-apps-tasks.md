# 应用任务入口与异步生命周期

平台的能力分成两类，**共用同一套鉴权与同一份账单**：

| 入口 | 谁在用 | 怎么调 | 形态 |
|---|---|---|---|
| **模型网关**（OpenAI 兼容） | 各类大模型 | `POST /api/v1/chat/completions` | 同步，直接返回 `choices` |
| **应用任务**（插件） | 语音、图像、视频、数字人、音乐、文档等 21 个生成应用 | `POST /api/v1/apps/<应用代号>/<接口代号>` | 多为异步，返回 `task_id` |

> **路径铁律**：一律用 `/api/v1/apps/<应用代号>/<接口代号>`，两个代号都取自接口
> 返回的 `code` 字段（**是下划线，不是连字符**）。
> **不要拿 `endpoint_path` 字段去拼 URL** —— 它给的是另一套路由族，拼出来打不通。

---

## 一、发现能力

```bash
# 列出全部应用
python3 scripts/a7w.py apps

# 看某个应用有哪些接口、参数与真实价
python3 scripts/a7w.py schema voice_tts
```

`schema` 输出里：

- `code` 是**接口代号**（调用时用它），`name` 是中文展示名（**不能拿去调用**）。
- `call_type`：`1` = 同步，`2` = 异步。
- 参数定义在 `params_schema`，它有**两种形态**：带 `properties` 包装的，和扁平字典的。
  只认 `properties` 会把「有 6 个参数」误判成「无参数」。

---

## 二、可用应用（21 个）

| 类别 | 应用代号 |
|---|---|
| 图片 | `nano_banana` |
| 视频 | `full_video`、`happy_horse`、`grok_video`、`wan`、`seedance` |
| 数字人 | `image_human`、`pic_lipsync`、`lipsync` |
| 剪辑 | `action_transfer`、`person_replacement`、`dressing_diffusion`、`smart_clip`、`flashvsr` |
| 音频 | `voice_tts`、`music_generation`、`music_search`、`mmaudio`、`seedsvc` |
| 文档 | `file_qa` |

---

## 三、调用与轮询

```bash
# 同步接口：直接拿结果
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好世界"}'

# 异步接口：客户端自动轮询到结束
python3 scripts/a7w.py call full_video create --body '{...}'

# 只提交，不等结果
python3 scripts/a7w.py call full_video create --json-file body.json --no-wait

# 拿 task_id 单独查
python3 scripts/a7w.py task tsk_xxxxxxxx
```

提交成功返回：

```json
{ "task_id": "tsk_xxx", "status": "pending", "created_at": 1740000000 }
```

轮询 `GET /api/v1/tasks/{task_id}`，终态看 `status`
（`completed` / `failed` / `cancelled`），产物在 `result`，用量在 `usage`。

---

## 四、回调（不轮询的替代方案）

提交时带 `callback_url`，任务完成后平台向该地址 POST JSON：

```json
{ "task_id": "tsk_xxx", "status": "completed", "result": { } }
```

你的接口返回 **2xx** 即算接收成功，否则按你在 **用户中心 → 回调配置** 里设的次数
（1–10 次）重试。

---

## 五、异步任务的三条纪律

1. **提交时就预冻结点数**，完成后按实际用量多退少补。**失败全额退回。**
2. **不要重复提交同一个任务** —— 每次提交都可能产生费用。
   网络超时也先查 `task_id` 再决定要不要重提。
3. **降并发**。队列有上限，一次全发出去更容易撞 429。

---

## 六、计费口径

| 能力 | 计价单位 |
|---|---|
| 文本 | 点数 / 百万 tokens（输入输出分别计价，流式与非流式同价） |
| 图像 | 点数 / 张或参数档位 |
| 视频生成 / 超分 | 点数 / 秒（按分辨率档位） |
| 数字人 | 点数 / 次或时长 |
| TTS / 音色克隆 | 点数 / 千字 |
| 语音识别 | 点数 / 分钟 |
| 工具类 | 点数 / 次 |

- **1 元 = 100 点、1 点 = ¥0.01。**
- 平台同时给出**两套价格字段**：
  `fixed_price` / `input_price` 是**标准价**，
  `tenant_fixed_points` / `tenant_points_per_1k_input` 是**你所在租户的实际结算价**。
  **做预算一律用 `tenant_*`，最终以账号里实际扣费为准。**
- **实时查价**：逐个 `schema <app>` 读 `tenant_*`。

---

## 七、任务自检

- [ ] 调用前跑过 `apps` / `schema`，应用代号与接口代号都来自接口返回
- [ ] 用的是 `/api/v1/apps/<应用>/<接口>`，**没有拿 `endpoint_path` 拼 URL**
- [ ] 异步任务用 `task_id` 去重，网络超时后没有直接重提
- [ ] 回调地址会返回 2xx
- [ ] 预算是按 `tenant_*` 算的
