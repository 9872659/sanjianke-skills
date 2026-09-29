# 成本与排错

> 这份文档给的是**实测单价、报价口径与排错手册**。
> 命令与参数见 `SKILL.md`；版式数字见 `layout-specs.md`。

## 一、实测单价

### 1.1 出图（nano_banana）

| 项 | 值 | 来源 |
|---|---|---|
| 1K | **24 点/张** | **真机实测**（`usage.points_cost = 24.0`） |
| 2K | **未知** | **没实测过 → 脚本拒绝估算（exit=3）** |
| 4K | **未知** | 同上 |
| 换算 | **1 元 = 100 点** | 算力集市的充值比例 |

所以 **1K 出图 = 0.24 元/张**。7 页课件按 `--every 3` 出 3 张 = **72 点 = 0.72 元**。

⚠️ **为什么 2K/4K 拒绝估算**：平台文档只说"官方高清模型按 1K、2K、4K 分档计费"，
**没有给倍率**。凭"大概是 2 倍"去猜，用户就会按错的预算下单——
同族的教训是"编单价"比"不给价"危害大得多。所以：

```bash
python3 scripts/run.py images --outdir D:/slides/ep01 --resolution 2K
# !! 2K 档没有实测单价，**拒绝凭猜估算**（只有 1K 有实测价 24 点/张）。
#    给 --points-per-image 指定单价，或先用 1K 出。
# 退出码 3，一分钱都没花
```

要跑 2K 就自己给单价：`--points-per-image 48`（你自己的估值）。

### 1.2 文本（`deepseek-chat`）

网关**不公布文本模型单价**：
- `/api/v1/models` 的返回里**没有价格字段**；
- `/api/v1/pricing` 之类的表**不含文本模型**；
- `/chat/completions` 的 `usage` 里**没有 `points_cost`**（只有 token 数）。

所以本包**只给估算口径**：`--yuan-per-ktok`（默认 **0.02 元/千 token**），
输出里一律标成"**估算**"。**账单以 api.a7w.cn 控制台为准。**

要按自己的实际单价算，就传：

```bash
python3 scripts/run.py cost --pages 12 --every 2 --yuan-per-ktok 0.015
```

### 1.3 只信 `usage.points_cost`

出图任务返回里有好几个看起来像"费用"的字段，**只有 `usage.points_cost` 可信**：

| 字段 | 可信吗 | 为什么 |
|---|---|---|
| `usage.points_cost` | ✅ **只信它** | 实际扣费 |
| `usage.actual_points` | ✅ 次选 | 同义字段，取不到上面那个时用它 |
| `result.actual_points` | ✅ 兜底 | 再取不到就用它 |
| `frozen_points` | ❌ | **预冻结**，不是最终扣费（实测出现过 31.2，失败全额退回） |
| `pricing_matrix` / `tenant_*` | ❌ | 同族验证过**半数不可信**：`image_human` 字段写 1.5/2/4/8 点/秒、实测 2/3/6/12；`voice_tts`/`stt` 字段写 30、实扣 40 |

## 二、`cost` 是怎么估的

```bash
python3 scripts/run.py cost --pages 12 --every 2
```

```
=== 课件成本预估（一次调用都不发）===
规模：12 页，每 2 页一张配图 → 6 张
出图：6 张 × 24 点/张（1K，实测价）= **144 点 = 1.44 元**
文本（**估算口径**，不是账单）：
  outline          prompt≈1500 tok + completion≈2400 tok
  pages(3 页/次)     prompt≈6400 tok + completion≈4080 tok × 4 次
  合计 ≈ 14380 token ≈ 0.2876 元（按 0.0200 元/千 token）

合计 ≈ 1.7276 元（出图实测价 + 文本估算，账单以 api.a7w.cn 控制台为准）
```

估算模型（源码里的常量，都可复核）：

| 阶段 | prompt 估算 | completion 估算 |
|---|---|---|
| `outline` | 1500 tok / 次 | 200 tok × 页数 |
| `pages` | 1600 tok × 批数（**3 页一批**） | 340 tok × 页数 |

**这是估算，不是账单。** 真机实测一套 7 页课件的实际用量见下一节。

## 三、真机实测记录

### 3.1 一套 7 页课件的完整账单

| 阶段 | 实测 | 耗时 |
|---|---|---|
| `outline` | `prompt_tokens 1186` / `completion_tokens 780` / **`total_tokens 1966`** | 5.8s |
| `pages`（7 页 = 3 批） | 闸门全绿 | 11.9s |
| `images`（3 张，`--every 3`） | **`points_cost` 24.0 点/张 = 合计 72.00 点 = 0.72 元** | 每张 5~20s |
| `render`（7 页） | 7 张 1920×1080，合计 3.8 MB | **0.7s** |

**真实 `usage` 原文**（`outline`）：

```json
{"prompt_tokens": 1186, "completion_tokens": 780, "total_tokens": 1966,
 "prompt_tokens_details": {"cached_tokens": 0},
 "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1186}
```

**真实任务结构原文**（出图）：`status` 在 `data` **顶层**，
`data.result.status` 是 `None`（**平台文档写错了**）：

```
data.status = 'completed'
data.result.status = None
```

**出图真实像素 vs 请求比例**：

| 请求 | 真实像素 | 实际比例 | 偏差 | 容差 | 结论 |
|---|---|---|---|---|---|
| `16:9` | **1344×768** | 1.7500 | **1.56%** | 3% | ✅ 放行，但**如实报出偏差** |
| （伪造测试）`16:9` | 1024×1024 | 1.0000 | **43.75%** | 3% | ❌ 退出码 3 |

### 3.2 断点续跑省下的钱

| 场景 | 结果 |
|---|---|
| `pages` 原样重跑 | **0 次调用、0 元**（批级断点全跳过，0.1s） |
| `render` 原样重跑 | 7 页全跳过（0.1s） |
| `render` 只改了 3 页的页型 | **精确重渲 3/7 页**，其余 4 页跳过 |
| `pages` 的闸门判定失败后修好闸门重跑 | **0 次调用**（成稿已在断点里，只重跑闸门） |

### 3.3 文本金额的换算

7 页课件：`outline` 1966 tok + `pages` 3 批（约 7000~9000 tok）
≈ **10000~11000 tok**，按 0.02 元/千 token ≈ **0.20~0.22 元**。
加上出图 0.72 元，一套 7 页课件（3 张图）**约 0.9 元**。

## 四、排错手册

### 4.1 环境类（都是 exit=2，不花一分钱）

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `没有 PIL：本地排版成逐页 PNG 需要 PIL` | 没装 pillow | `pip install pillow`，**原样重跑**（断点续跑不重复扣钱） |
| `系统里找不到可用的中文字体` | 系统没中文字体 | `--font <字体文件路径>`；脚本找过 `msyhbd.ttc` / `msyh.ttc` / `simhei.ttf` / `Deng.ttf` / `simsun.ttc` / `PingFang.ttc` / `NotoSansCJK` / `wqy-zenhei` |
| `输出目录 … 在 Skill 包内` | `--outdir` 指到包内 | 换到包外：`D:/slides/x`、`%TEMP%\slides` |
| `讲义原文 … 超过上限 24000 字` | 讲义太长 | 拆成两半分开跑。**故意不截断**——截掉的内容你永远不知道少了什么 |
| `--theme 只能是 ink / night / warm` | 主题名写错 | 用三个内置主题之一 |
| `Missing or invalid relay API key`（HTTP 401） | Key 无效 / 过期 / 写错 | 到 https://api.a7w.cn/ 重新领取；确认没把 `Bearer` 重复写进环境变量 |
| 点数不足（HTTP 402） | 账号点数用完 | 到 https://api.a7w.cn/ 充值后重试 |
| `模型不存在`（HTTP 404） | 模型名写错或已下架 | `python3 scripts/run.py models` 现查 |

### 4.2 闸门类（都是 exit=3，也都不花钱）

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `no_pages` | 分页方案一页都没有 | 先跑 `outline`；或看 `deck.json` 是不是被手工改坏了 |
| `page_count` | 实际页数与 `--pages` 差 > 1 | 改 `--pages` 重跑，或手工调整 `deck.json` |
| `empty_title` / `no_image_intent` | 某页缺标题 / 缺配图意图 | 重跑该批，或手工补 `deck.json` |
| `empty_page` | 某页一条要点都没有 | **脚本不会拿粗要点兜底**（那会掩盖"展开失败"），补内容后重跑 |
| `bullet_too_long` | 单条要点 > 48 字 | 拆成两条或压缩。**不截断** |
| `title_too_long` / `title_too_many_lines` | 标题 > 30 字 / 断成 3 行以上 | 缩短标题 |
| `too_many_bullets` | 一页 > 6 条要点 | 拆成两页（改 `deck.json`，或让 `outline` 多分几页） |
| `text_overflow` | 标题 + 要点超过版心 | 报里给了**实际像素与可用像素**与具体是哪条要点太长；减内容，**别改闸门** |
| `ratio_fake` | 真实像素与请求比例差 > 3% | `images --snap` 重跑该页 |
| `banned_word` | 命中广告法违禁词 / 教育类效果承诺 | 命中项逐条打在 stderr；改文案重跑，或 `--from-file` 零成本复核 |
| `placeholder` | 残留 `{}` / `[待填]` / `XXX` / `TODO` | 改文案；这通常是模型把模板写进正文了 |
| `prompt_echo` | 照抄了提示词里的示例 | 改文案；或检查是不是提示词里放了可直接复制的产出 |
| `预估 … 超过预算上限` | 超 `--budget` | 提预算、减页数，或先 `cost` 试算 |
| `2K 档没有实测单价，拒绝凭猜估算` | 2K/4K 无实测价 | 先用 1K，或 `--points-per-image` 自填 |

### 4.3 花钱类（exit=4，或"重跑又扣了钱"）

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 上游 `502` / `upstream timeout` | 网关到上游的瞬时抖动，**实测很常见** | 已内置退避重试（最多 4 次）；连续失败就换模型或 `--count` 分批 |
| `任务未完成（timeout）` | 出图卡在 processing | `task_id` 已进断点文件，**重跑会续查而不是重新提交（不重复扣费）**；也可调大 `--poll-timeout` |
| 提交后没拿到 `task_id` | 返回结构变了 | 把原始返回贴出来报 bug（本包不吞异常） |
| 任务完成但没有图片地址 | 返回结构变了 | 同上；`find_image_urls()` 是深度搜索，结构一变就会暴露 |
| **重跑又扣了一次钱** | 断点 key 的某一维变了：改了文案 / 换了 `--resolution` / 换了模型 | **设计如此**（内容变了就该重做）。注意：**只改版式不会重出图** |
| **换了主题再换回来，却报"已渲染，跳过"，磁盘上却是另一个主题的图** | 两个主题写**同一个文件名**，旧断点记录仍然命中 | **已修**：断点命中后会再核**产物身份**（字节数 + mtime），对不上就重做并打印原因 |
| 改了主题/字号但图没变 | 改了画法却没 bump `LAYOUT_VERSION` | 把源码里那个常量 +1（有醒目注释） |
| 下载图片失败 | 网络抖动 | `download()` 自带退避重试 3 次；它**不走** `a7w._request`（见下） |

### 4.4 三个"为什么这么写"（改代码前必读）

**① `download()` 为什么不用 `a7w._request`。**
`_request(..., raw=X)` 里的 `raw` 是**原始请求体**，**不是**"要原始响应"。
传 `raw=True` 会让 `headers["Content-Type"] = None`，`putheader` 直接抛
`TypeError: expected string or bytes-like object, got 'NoneType'`；
就算绕过去，`_request` 末尾做的是 `json.loads(resp.read())` —— **PNG 不是 JSON**。
另外传 `key=None` 时它会做 `"Bearer " + key` → `TypeError`，
而这发生在**图已经出好、钱已经扣了**之后，最亏。
所以 `download()` 自带一小段 urllib：拿字节、不解析 JSON、Key 走 `a7w.load_key` 兜底。

**② `status` 为什么从 `data` 顶层取。**
平台文档写的是 `data.result.status`，**实测不对**。照文档写会永远读不到状态、
一路轮询到超时。

**③ `--json` 为什么有两种失败形态。**
- **信封** `{"ok": false, "exit": N, "error": {"kind": …}}`：本次还没吐过任何结果时用。
- **结果** `{"ok": false, "stage": "gate", "blocked": [...]}`：命令已经跑完、产出也给了，
  只是闸门判定不合格时用。此时**绝不再补信封** ——
  实测踩过：报价阶段"先吐报价 JSON、再补失败信封"，于是 stdout 上出现**两个 JSON 文档**，
  消费方 `json.loads` 直接 `Extra data: line N column 1`，把
  「stdout 只有一个 JSON」这条不变量打破了。

### 4.5 零成本自查

复核一份已有产出、又不想再花钱：

```bash
# 拿一份模型返回的 JSON 直接过闸门，不调模型
python3 scripts/run.py outline 讲义.md --pages 6 --dry-run          # 只打提示词
python3 scripts/run.py outline --outdir D:/slides/x --pages 6 --from-file 返回.json
python3 scripts/run.py pages   --outdir D:/slides/x --from-file 返回.json

# 只看钱
python3 scripts/run.py cost --pages 12 --every 2

# 只渲染（渲染是零成本的）
python3 scripts/run.py render --outdir D:/slides/x

# 出图只报价：**不要加 --yes，也不要加 --budget**
python3 scripts/run.py images --outdir D:/slides/x --every 2
# 或
python3 scripts/run.py images --outdir D:/slides/x --every 2 --dry-run
```

> ⚠️ **`--budget` 本身就是出图的确认**（`need_yes = 不加 --yes 且 没给 --budget`）。
> 也就是说**给了 `--budget` 就会真的出图**，花到上限为止。
> 只想看价钱，请**两个都不加**。

## 五、收集排错信息时请附上

1. 完整命令（**不要带 `--key`**）
2. `--dry-run` 的输出
3. `AUDIT.md` 的内容
4. 原始报错文本（`--json` 下还有那个 JSON 信封）

**不要在报错信息或截图里带上你的 API Key。**
