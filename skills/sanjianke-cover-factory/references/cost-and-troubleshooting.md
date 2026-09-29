# 计费口径与排错手册

> 本文件是三剪客 · 封面图批量生成的对账依据。**只信任务返回的 `usage.points_cost`。**

## 一、实测单价

| 项 | 实测 | 备注 |
|---|---|---|
| `nano_banana` 1K 出图 | **24 点/张** | = **0.24 元**；两张共 48 点（本次真机实测） |
| 充值比例 | **1 元 = 100 点** | 平台口径 |
| 提交时冻结 | `frozen_points = 31.2` | **预冻结，不是最终扣费** |
| 完成后结算 | `usage.points_cost = 24` | ✅ 这才是结算价 |
| 失败 | 全额退回 | |
| `2K` / `4K` | **没有实测价** | 本包**拒绝估算**（退出码 3），想估要给 `--points-per-image` |
| 本地叠字 | **0 点** | 纯本地渲染，不联网 |

**换算**：`元 = 点 ÷ 100`。30 个标题 × 5 个平台 = 150 张 ≈ **3600 点 = 36 元**。

## 二、为什么只信 `usage.points_cost`

平台的 `pricing_matrix` / `tenant_*` 字段我们验证过**半数不可信**：

| 应用 | 字段写的 | 实测扣费 |
|---|---|---|
| `image_human` | 1.5 / 2 / 4 / 8 点每秒 | **2 / 3 / 6 / 12** |
| `voice_tts` / `stt` | 30 | **实扣 40** |
| `nano_banana` 提交响应 `frozen_points` | 31.2 | **实扣 24**（差 30%） |

所以那些字段只能当参考，**不能当结算价写进文档**，更不能拿它们算预算。

## 三、文本那一步为什么只报 token

`plan` 要调一次大模型。但**拿不到可信的文本模型单价**：

- `GET /api/v1/pricing` 只有 6 条规则（一条全局 `*` + `full_video` / `asr` / `flashvsr` /
  `action_transfer` / `person_replacement` 等特例），**不含文本大模型**
- `GET /api/v1/models` 的记录里**没有任何价格字段**
- `chat/completions` 的成功响应 `usage` 只有 `prompt_tokens` / `completion_tokens` /
  `total_tokens`（外加缓存命中统计），**没有点数**

所以本包**只报 token、不报金额** —— 不编单价。

本次真机实测（4 条方案，2 个标题 × 2 个平台）：

```
{"prompt_tokens": 679, "completion_tokens": 638, "total_tokens": 1317,
 "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 679}
```

第二次跑（2 个标题 × 2 个平台，`all` 的 plan 阶段）：
`prompt 678 + completion 799 = 1477`，其中 `prompt_cache_hit_tokens: 256`
（同一段系统提示词命中缓存）。**缓存统计不要拿去算钱**，算钱只看 `prompt_tokens`。

## 四、契约里的三个坑（都实测踩过并由本包修掉）

### 1. `code == 1` 才是成功，不是 `0`

生成应用的信封是 `{"code":1,"msg":"success","data":{…}}`。
而 `/chat/completions` 的成功响应**不带 `code`**（标准 OpenAI 形态）。
**别拿 `code` 判文本调用的成败。**

### 2. `status` 在 `data` 顶层，不在 `data.result` 里

平台文档写的是 `data.result.status`，**实测不对**。
照文档写会永远读不到状态、一路轮询到超时。实测完成态：

```json
{"code": 1, "msg": "success",
 "data": {"status": "completed", "task_id": "task_…",
          "usage": {"points_cost": 24},
          "result": {"image_url": "…", "success": true}}}
```

另外 `result.data[0].image_url` 与 `result.results[0].image_url` 也可能有图 ——
所以本包做**深度搜索**把所有 `image_url` 收齐，不只取第一处。

### 3. `a7w._request(..., raw=…)` 里的 `raw` 是**原始请求体**，不是"要原始响应"

拿它下 PNG 会连踩两个坑（本包实测踩全了）：

```python
a7w._request("GET", url, None, raw=True)     # ❌ 两个错
```

- `raw=True` → `headers["Content-Type"] = None` → `putheader` 抛
  `TypeError: expected string or bytes-like object, got 'NoneType'`
- 就算绕过去，`_request` 末尾做的是 **`json.loads(resp.read())`** —— **PNG 不是 JSON**
- `key=None` → `"Bearer " + None` → `TypeError: can only concatenate str (not "NoneType") to str`

**最亏的地方**：这两个错都发生在**图已经出好、24 点已经扣了之后**。
所以本包的 `download()` 自带一小段 urllib 下载（拿字节、不解析 JSON、Key 走
`a7w.load_key` 兜底、网络错误退避重试），**不污染共用的 `a7w.py`**。

并且断点里**先存 `task_id` 和 `image_url`、再下载** —— 于是"下载崩了"重跑会
**补下载**（0 点），而不是重新提交（再扣一次）。本次真机实测走过这条路：

```
#xiao-01 断点里已有 task_id=task_3085…（已提交，不重复提交），续查结果…
  #xiao-01 补下载成功（24.0 点，1616211 字节，**没有再提交、没有重复扣费**）
```

## 五、退出码

| 退出码 | 含义 | 花钱了吗 |
|---|---|---|
| `0` | 全部成功且闸门全绿 | 按实际出的图 |
| `1` | 没预料到的异常（代码 bug）；`--json` 下 `kind=internal` + stderr 完整栈 | 已提交的会扣 |
| `2` | 参数/配置错误（`--outdir` 在包内、没有字体、没有 PIL） | **没花** |
| `3` | 硬闸门命中（违禁词/占位符/照抄示例/比例/叠字可读性/超预算） | 多为**没花**；比例闸门是出图后判的 |
| `4` | **需要 `--yes`**（还没花钱、也没提交）；或调用失败（网络/鉴权/点数/模型名） | 前者**没花** |
| `5` | 达到 `--max-seconds` 上限中断（可续跑） | 已完成的算 |
| `130` | 用户中断（Ctrl+C） | 已提交的算 |

**注意闸门五（叠字可读性）与闸门六（成本上限）都在提交之前判 —— 命中时一分钱不花。**

## 六、排错表

| 现象 / 报错 | 原因 | 怎么办 |
|---|---|---|
| `鉴权失败（401）` | Key 无效 / 过期 / 写错 | 到 https://api.a7w.cn/ 重新领取；确认没把 `Bearer` 重复写进环境变量 |
| `点数不足（402）` | 点数用完 | 充值后重试 |
| 上游 `502` / `upstream timeout` | 网关到上游抖动，**实测很频繁** | 脚本内置退避重试；连续失败就换模型或降低批次 |
| 轮询一直 `processing` | 上游排队 | `--poll-timeout` 默认 600 秒；重跑会按 `task_id` **续查、不重新提交** |
| `当前请求未命中可用计费规格` | `model` 与 `resolution` 组合不支持 | 普通 `nano-banana` 只支持 `1K`；要高清换 `nano-banana-2:official` |
| `大字标题 N 字，超过 上限 M 字（多出 …）` | 叠字可读性闸门（exit 3） | 把超出的字移到正文或拆两张；**不接受 `--allow-prompt-hits` 放行** |
| `没有找到可用的中文字体` | 系统里没中文字体 | `--font` 指一个 `.ttf/.ttc/.otf`；`specs` 会打印可用字体表 |
| `本地叠字需要 PIL` | 没装 pillow | `pip install pillow` 后**原样重跑**（背景图不重出、不重复扣费） |
| `真实像素 864x1184 … 偏差 2.70%` | 上游按 32 对齐，**不是错误** | 加 `--snap`；容差内不会拦 |
| `2K 档没有实测单价，拒绝凭猜估算` | 我们没测过 2K/4K | 给 `--points-per-image`，或先用 1K |
| `输出目录 … 在 Skill 包内` | `--outdir` 指到包里了 | 换到包外 |
| `!! 已花 … 点，再出下一张会超过 --budget` | 真实扣费累计超了 | 已完成的产出仍在，从断点继续 |
| 重跑又扣了一次钱 | 提示词/叠字样式/分辨率改了 → 断点 key 变了 | 设计如此；想省钱就别改 |
| `Extra data: line N column 1`（消费 `--json` 时） | stdout 上出现了两个 JSON 文档 | 本包已修（结果吐过就不再补信封、人读文案全走 stderr）；升级到 1.0.0+ 即可 |
| Windows 下中文乱码 | 控制台代码页不是 UTF-8 | `chcp 65001`，或设 `PYTHONIOENCODING=utf-8` |

**收集排错信息时请附上**：完整命令、`plan --dry-run` 的输出、`--report` 产出的证据 JSON、退出码。
**不要在报错信息或截图里带上你的 API Key。**

## 七、本次真机实测的成本账（可对账）

| 步骤 | 花费 | 说明 |
|---|---|---|
| `specs` | 0 | 零网络 |
| `plan`（2 标题 × 2 平台 = 4 条） | 文本 1317 token | 金额需自填单价 |
| `images --count 2 --snap` | **48 点 = 0.48 元** | 两张各 24 点（`usage.points_cost`） |
| `overlay`（两张） | **0 点** | 纯本地 |
| 重跑 `images`（断点续跑） | **0 点** | 2 张全部跳过；另有 48 点来自上一轮 |
| 合计新增花费 | **48 点 = 0.48 元** | 预算 ≤ 1 元 |

（第一张图因为下载那一步的 bug 白扣过一次 24 点 —— 那个 bug 已修，
并补上了"按 `task_id` 补下载"的续跑路径，这类浪费以后不会再发生。）
