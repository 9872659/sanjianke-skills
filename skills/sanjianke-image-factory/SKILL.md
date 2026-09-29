---
name: sanjianke-image-factory
slug: sanjianke-image-factory
displayName: 三剪客 · 新媒体配图工厂
description: "给一篇文稿或一个主题，自动产出整套新媒体配图：先出配图方案（几张、每张画什么、什么比例、放哪），确认成本后按平台比例批量出图——小红书 3:4、公众号 2.35:1、抖音 9:16、头条 16:9。走 api.a7w.cn 的 nano_banana，零依赖，成本前置（跑之前先告诉你花多少钱），断点续跑能跳过已完成的图，但断点 key 含提示词——提示词一改就重出重扣，四道本地硬闸门：比例真伪（读回真实像素，不信自报字段）、成本上限、违禁词、照抄提示词示例检测。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.8
summary: "写完稿子，配图往往最拖时间：不是画不出来，是要为每个平台分别想「画什么、什么比例、放哪里」，再一张张生成。本包把这步做成两个命令：`plan` 出方案（只花文本钱），`gen` 出图（真花钱，先报价）。方案按你要投放的平台给出每张图的角色（封面/内文/步骤/对比/数据/金句/结尾）、出图提示词、目标比例与摆放位置，同一套图强制视觉统一（同色板、同光线方向、同画风）。出图走算力集市 api.a7w.cn：POST /api/v1/apps/nano_banana/submit 提交异步任务，GET /api/v1/tasks/<task_id> 轮询结果。实测 1K 出图 24 点/张（= 0.24 元），只信任务返回的 usage.points_cost。四道闸门都是硬拦不是警告：比例真伪（读文件头真实像素，实测上游按 32 对齐、10 种比例里 5 种给不出像素级精确比例，配 --snap 本地裁准）、成本上限（超 --budget 不提交）、违禁词、以及 prompt_echo——模型会照抄提示词里的示例，哪怕标着「这是错的写法」。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 配图
  - 新媒体
  - api.a7w.cn
---

# 三剪客 · 新媒体配图工厂

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

## 能做什么

给一篇文稿或一个主题，**自动产出一整套配图**：先出方案，确认成本，再按各平台比例批量出图。

它替代的是运营每天最琐碎的那一步：不是"没有图"，而是"每张图该画什么、什么比例、放哪一段"。

两个命令，两步花的钱不一样，这是刻意的：

| 命令 | 做什么 | 花钱吗 |
|---|---|---|
| `plan` | 出一份配图方案（几张、每张画什么、什么比例、放哪里） | **只花文本钱**（几千 token） |
| `gen` | 按方案批量出图 | **真花钱**，先报价，要 `--yes` 才提交 |

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 实测 **24 点/张**（1K）= **0.24 元/张**，1 元 = 100 点；`gen` 跑之前会先把总价打出来 |
| 要多久 | 单张实测 **5~30 秒**完成；轮询有超时上限，不会无限等 |
| 要装什么 | **什么都不用装**，只用 Python 标准库 |
| 支持哪些比例 | 小红书 3:4 / 公众号 2.35:1 / 抖音 9:16 / 头条 16:9 / 通用 1:1 |
| 中断了怎么办 | **断点续跑**：已完成的图直接跳过，已提交未完成的用 `task_id` 续查，不重复扣费；**但断点 key 含提示词——提示词一改就重出重扣**，见排错表「重跑又扣了一次钱」 |
| 会瞎编吗 | 方案阶段就写死"不许编文稿里没有的数字、人名、品牌、检测结论" |

## 怎么用（命令行）

### 第 0 步：获取 API Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`）。

### 第 1 步：装依赖

**零依赖。** 不需要 `pip install` 任何东西，只要机器上有 Python 3.7+：

```bash
python3 --version
```

`scripts/a7w.py` 是零依赖客户端（只用 `urllib` / `json` / `mimetypes`），
`scripts/imgprobe.py` 是图片头探针（只用 `struct` / `zlib`），`scripts/run.py` 同样只用标准库。
**PIL 不是必需的**——它的存在只会让 `--snap` 支持更多图片格式。

> **约定**：`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端，我们靠
> 「包内副本 SHA256 == 规范版」批量校验各包的客户端有没有被意外改坏。
> 所以本包**没有**为了自己的业务去改它——需要读图片像素就独立出 `imgprobe.py`，
> 需要应用专属接口就写在 `run.py` 里。

### 第 2 步：填 Key

```bash
# Linux / macOS
export A7W_API_KEY=sk-你的key

# Windows PowerShell
$env:A7W_API_KEY="sk-你的key"
```

也可以存进配置文件反复用（推荐）：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### 第 3 步：先确认网关通（免费，不花点数）

```bash
python3 scripts/run.py models
```

`models` 会打两个端点：`GET https://api.a7w.cn/api/v1/apps`（在架应用，21 个）
与 `GET https://api.a7w.cn/api/v1/models`（在架模型，按类型分）。本包用其中的 `nano_banana`。

> **模型名会变，别写死在脚本里。** 出图模型的可选值也可以现查：
> `python3 scripts/a7w.py schema nano_banana`

### 第 4 步：出方案（只花文本钱）

```bash
python3 scripts/run.py plan --topic "便携榨汁杯" \
    --platform xiaohongshu --platform wechat \
    --count 6 --out plan.json
```

也可以直接喂文稿：

```bash
python3 scripts/run.py plan 文章.md --platform xiaohongshu --count 8 --out plan.json
```

想先看不花钱的提示词：

```bash
python3 scripts/run.py plan --topic "便携榨汁杯" --dry-run
```

### 第 5 步：先算钱（不出图）

```bash
python3 scripts/run.py cost --count 6
# 预估成本：6 张 × 24 点 = 144 点 = 1.44 元

python3 scripts/run.py cost --count 6 --budget 100
# 超预算 → 打印「gen 会被拦下」并返回退出码 3
```

### 第 6 步：出图（真花钱）

```bash
# 先不带 --yes 跑一次：只报价，不提交
python3 scripts/run.py gen --plan plan.json --outdir ./out

# 确认了再加 --yes
python3 scripts/run.py gen --plan plan.json --outdir ./out --yes --snap --report evidence.json
```

**图片一定要输出到包外**（比如 `./out`、`%TEMP%\...`）。Skill 包的上传白名单只收
`.md .py .txt .json .sh .js .yaml .yml .csv`，图片会让上传 400；脚本也会拒绝把 `--outdir`
指到包内（退出码 2）。

中断了就原样重跑，**提示词没变就不会重复扣费**（断点 key 含提示词，改了会重出重扣）：

```bash
python3 scripts/run.py gen --plan plan.json --outdir ./out --yes
# [1/3] #1 已完成，跳过（上次扣费 24.0 点，不再重复扣）
# [2/3] #3 发现未完成的 task_id=task_xxx，续查而不重新提交
```

### 完整工作流

```bash
# 0) 认平台与模型
python3 scripts/run.py models

# 1) 出方案（只花文本钱）
python3 scripts/run.py plan 文章.md --platform xiaohongshu --platform douyin \
    --count 8 --out plan.json --json

# 2) 算钱 + 设预算
python3 scripts/run.py cost --count 8
python3 scripts/run.py cost --count 8 --budget 200

# 3) 真出图（报价 → 确认）
python3 scripts/run.py gen --plan plan.json --outdir ./out
python3 scripts/run.py gen --plan plan.json --outdir ./out --yes --snap \
    --budget 200 --report evidence.json
```

### 直接用 curl 调（不依赖本包脚本）

本包底层就是算力集市 api.a7w.cn 的标准两步异步任务。提交（**注意没有 `/generate`
这个端点**，"文生图"是 `submit` 的 `action=generate` 参数）：

```bash
# 算力集市 api.a7w.cn · nano_banana 提交出图（真花钱，1K 约 24 点/张）
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/nano_banana/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "窗边木桌上的一杯手冲咖啡特写，晨光斜射，暖色调，浅景深，无文字",
    "action": "generate",
    "model": "nano-banana",
    "resolution": "1K",
    "aspect_ratio": "3:4"
  }'
```

拿 `data.task_id` 去轮询：

```bash
curl -sS "https://api.a7w.cn/api/v1/tasks/task_xxxxxxxxxxxx" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

## 参数说明

### 全局

| 参数 | 说明 |
|---|---|
| `--key` | 临时指定 Key；优先级最高。**别把它写进脚本或文档** |
| `--json` | 以 JSON 输出，**写在子命令前面或后面都可以**（`plan --json --out plan.json` 可直接喂给 `gen`）；JSON 模式下 stdout 只有一个完整 JSON，报价与进度走 stderr |

### `plan` —— 出配图方案

| 参数 | 说明 |
|---|---|
| `--topic` | 主题（没文稿时用），或用位置参数 / `--article` 给文稿文件 |
| `--platform` | 投放平台，**可重复**：`xiaohongshu` / `wechat` / `douyin` / `toutiao` / `square` |
| `--count` | 要几张图，默认 `8` |
| `--style` | 视觉风格统一口径（会给到模型），默认「2 主色 + 1 点缀色、同光线方向、同画风」 |
| `--out` | 把方案写成 JSON，`gen` 要用它 |
| `--dry-run` | 只打印将发送的提示词，**不调模型、不花钱** |

### `gen` —— 按方案批量出图

| 参数 | 说明 |
|---|---|
| `--plan` | **必填**。`plan` 产出的方案 JSON |
| `--platform` | 只出指定平台的比例 preset，可重复 |
| `--outdir` | 图片输出目录，默认 `%TEMP%\image-factory-out`；**不可是包内目录** |
| `--budget` | 成本上限（**点**）。预估超了直接停；跑的过程中每次提交前还会再核一次 |
| `--yes` | 确认真的花钱。**不加就只报价、一个任务都不提交** |
| `--snap` | 出图后按请求比例精确裁剪（见下面「比例那件事」） |
| `--snap-on-design` | 按平台设计比例裁（如公众号 2.35:1），而不是按生成比例 |
| `--ratio-tolerance` | 比例容差，默认 `0.03`（实测最大偏差 2.9%）；有 0.0025 的量化地板 |
| `--poll-timeout` | 单张轮询超时秒数，默认 `600`（**上限，不是期望时长**；实测 5~30 秒完成） |
| `--max-seconds` | 整批最长耗时，到点中断（退出码 5），已完成的都在断点文件里，重跑可续 |
| `--state` | 断点文件路径，默认 `<outdir>/image-factory-state.json` |
| `--force` | 忽略断点全部重出（**会重复扣费**，只在确实要重画时用） |
| `--stop-on-error` | 一张失败就整体停 |
| `--report` | 把本次证据（请求参数 / 任务原文 / 真实像素）写成 JSON，便于对账 |
| `--allow-prompt-hits` | 即使提示词命中闸门也出图（默认**拦截**） |

### `cost` —— 只算钱不出图

| 参数 | 说明 |
|---|---|
| `--count` | **必填**。要出几张 |
| `--resolution` | `1K`（默认）/ `2K` / `4K` |
| `--points-per-image` | 覆盖单张单价（点）。**2K/4K 必须给**，见下 |
| `--budget` | 预算上限（点），超了退出码 3 |

### 比例 preset（`--platform`）

| preset | 平台 | 设计比例 | 生成用的 aspect_ratio | 目标像素 |
|---|---|---|---|---|
| `xiaohongshu` | 小红书 | 3:4 | `3:4` | 1080x1440 |
| `wechat` | 公众号 | **2.35:1** | `21:9` | 900x383 |
| `douyin` | 抖音 | 9:16 | `9:16` | 1080x1920 |
| `toutiao` | 头条 | 16:9 | `16:9` | 1280x720 |
| `square` | 通用方图 | 1:1 | `1:1` | 1024x1024 |

**公众号的 2.35:1 上游给不了**：`nano_banana` 的 `aspect_ratio` 可选值最宽只到 `21:9`
（= 2.333:1）。所以本包用 `21:9` 生成、再让 `--snap --snap-on-design` 精确裁到 2.35:1。
这是明确的设计取舍，不是遗漏。

## 四道本地硬闸门

闸门都是**拦截 + 标红 + 退出码非 0**，不是"提示一下"。因为配图是**按次扣费**的，
事后发现问题的代价是真金白银。

### 1. 比例真伪 —— 读回真实像素，不信自报字段

**不信接口返回里的任何比例字段**，把图下载回来读文件头，用真实宽高算比例。

为什么必须这样：标题工坊上一版只信模型自报的 `formula` 字段做模板污染判定，
结果那个真该被判命的标题恰好漏判——**闸门是假绿的**。同一个错误在出图场景的形态是：
自报 `aspect_ratio=3:4`，真实像素却是 `1024x1024`。

**实测到的上游特性（重要，这决定了容差怎么定）**：上游不是按比例给像素，
而是先定总像素、再把每边向下对齐到 32 的倍数。所以 10 种比例里有 5 种拿不到像素级精确比例：

| 请求 | 实测像素 | 实际比例 | 偏差 |
|---|---|---|---|
| 3:4 | 864x1184 | 0.7297 | 2.70% |
| 16:9 | 1344x768 | 1.7500 | 1.56% |
| 9:16 | 768x1344 | 0.5714 | 1.56% |
| 4:5 | 896x1152 | 0.7778 | 2.78% |
| 5:4 | 1152x896 | 1.2857 | 2.86% |
| 1:1 / 4:3 / 21:9 / 2:3 / 3:2 | 1024x1024 等 | 精确 | 0% |

所以默认容差是 **3%**（容差内不算"假"，但真实像素与偏差**照样打印出来，不藏**）。

要拿到像素级精确比例就加 `--snap`：按请求比例居中裁剪，裁完**再读一次文件头复核**，
只会把真正裁准的记成合格。优先用 PIL；没有 PIL 时回落到内置的 8 位 PNG 裁剪器
（只用 `zlib` + `struct`），两条路都走不通时**如实报告"没能裁"**，不假装成功。

读像素这件事由独立模块 `scripts/imgprobe.py` 负责（PNG / JPEG / GIF / WebP 四种文件头解析，
只读、纯标准库）。做成独立模块而不是塞进 `a7w.py`，是因为 `a7w.py` 是所有包共用的客户端，
靠 SHA256 校验一致性，不许被单个包的私有需求污染。

### 2. 成本上限

- 提交任何任务**之前**先算总价；超 `--budget` 直接停，一个任务都不提交
- 每张提交前**再核一次**：前面真实扣费可能比预估高，超了就就地停
- `2K` / `4K` 没有实测单价 → **拒绝估算**，退出码 3。宁可拒绝也不编一个数
  （想估就给 `--points-per-image`）

### 3. 广告法违禁词

绝对化用语（最/第一/国家级/100%）、虚构权威背书、医疗功效、投资承诺、站外导流，
命中即拦。这一条对**出图提示词**同样适用——提示词里写了"全国最好的咖啡杯"，
图上的字和物料大概率也是这个调性。

### 4. `prompt_echo` —— 照抄提示词示例

**这条是从标题工坊的事故来的**：提示词里写过的示例，哪怕明确标着"这是错的写法"，
模型照样照抄——公众号那一轮最高分 89.0 的标题**一字不差就是提示词里的示例**，
最高分变成"抄标准答案"，排序就废了。

出图场景更隐蔽：你不会一眼看出这张图和测试用例长得一样，而是"看起来挺正常"，
直到发现整套配图是同一个模子。

判定：把提示词里出现过的示例存成常量 `PROMPT_SAMPLES`，生成的出图提示词若
**去标点后相等**、或**字符二元组 Jaccard ≥ 0.75**、或**示例二元组的覆盖度 ≥ 0.60**
（长度门槛是相对的 `max(6, 示例长度/2)`，示例 25 字 → 门槛 12），就拦下。

第三条是补漏：出图提示词动辄 60~120 字而示例只有 25 字，Jaccard 的分母是两份二元组的
**并集**，示例那一侧被长提示词摊薄得极狠——示例原样嵌进去也照样放行。实测：

| 输入 | Jaccard | 覆盖度 | 结果 |
|---|---|---|---|
| 示例原样嵌入 + 补 9 个字（34 字） | 0.727 | **1.000** | 旧口径放行 ❌ → 新口径拦 ✓ |
| 示例原样嵌进 102 字的六段结构提示词 | 0.245 | **1.000** | 旧口径放行 ❌ → 新口径拦 ✓ |

覆盖度只看"示例被抄了多少"，不看提示词有多长，所以摊薄对它无效。

阈值 0.75 的标定依据（实测）：

| 输入 | Jaccard | 结果 |
|---|---|---|
| 逐字照抄示例 | 1.000 | 拦 |
| 只改标点 | 1.000 | 拦 |
| 少两个字 | 0.840 | 拦 |
| 加一个尾巴 | 0.857 | 拦 |
| 同构照抄（换一个词） | 0.778 | 拦 |
| 英文示例的近亲 | 0.766 | 拦 |
| **真实业务提示词** | **0.042** | 放行 |
| **另一条业务提示词** | **0.000** | 放行 |

真实产出与示例之间 Jaccard 有 **17 倍以上**的安全距离，所以 0.75 既能兜住轻改写，又不会误伤。

**已知边界（口径变更）**：判据 3（覆盖度 ≥ 0.60）会把"换两个词"也拦下
（Jaccard 0.714 但覆盖度 **0.833**）——25 字的示例里 83% 的二元组都被抄走，
落进产出里就是同一个模子，所以判定为拦是合理的。误伤侧的实测代价是 0：
17 条真实/正常提示词里覆盖度最大只有 0.547。

## 排错

| 现象 / 报错 | 原因 | 怎么办 |
|---|---|---|
| `鉴权失败（401）` | Key 无效、过期或写错 | 到 https://api.a7w.cn/ 重新领取；确认没把 `Bearer` 重复写进环境变量 |
| 点数不足（HTTP 402） | 账号点数用完 | 到 https://api.a7w.cn/ 充值后重试 |
| `code: 0` 但 HTTP 是 200 | **网关信封里 `code == 1` 才是成功，不是 0** | 看 body 里的 `msg`；脚本已按这个口径判断，别改成 `code == 0` |
| `当前请求未命中可用计费规格` | `model` 与 `resolution` 组合不支持（如普通模型传 `2K`） | 普通 `nano-banana` 只支持 `1K`；要高清档换 `nano-banana-2:official` 之类 |
| 上游 `502` / `upstream timeout` | 网关到上游的瞬时抖动，**实测很频繁** | 脚本已内置退避重试（4 次）。连续失败就换模型或降低批次 |
| 轮询一直 `processing` | 任务卡住了 | 已经设了 `--poll-timeout`（默认 600 秒）上限；超时会报出来并保留 `task_id`，可 `python3 scripts/a7w.py task <task_id>` 续查 |
| 图片真实像素和请求比例对不上（差 1%~3%） | **上游按 32 对齐**，不是 bug | 加 `--snap` 精确裁；或把 `--ratio-tolerance` 放宽 |
| `读不出真实像素` | 下载被截断，或不是图片 | 删掉那条断点记录重出（`--force`），或检查网络 |
| `预估 N 点超过预算上限` | 超了 `--budget` | 提高预算、减少 `--count`，或先 `cost` 试算 |
| `2K 档没有实测单价，拒绝凭猜估算` | 我们没有 2K/4K 的实测价 | 给 `--points-per-image` 指定单价，或先用 1K 出 |
| `输出目录 ... 在 Skill 包内` | `--outdir` 指到了包里的目录 | 换到包外（`./out`、`%TEMP%\...`）。包内放图片会让上传 400 |
| `提示词命中闸门 ... 已拦截，未提交任何任务` | 违禁词 / 照抄示例 / 占位符残留 | 改提示词后重跑；确实要带违禁词才加 `--allow-prompt-hits` |
| 重跑又扣了一次钱 | 提示词改了 → 断点 key 变了，被当成新的一项 | 这是设计如此（改了提示词就该重画）。想省钱就别改提示词，直接重跑即可跳过；重跑前先确认提示词没变，或先用 `cost` 核对预估花费 |
| `没有找到 API Key` | 三种方式都没配 | `--key` / `A7W_API_KEY` / `python3 scripts/a7w.py login --key sk-xxx` |
| Windows 下中文乱码 | 控制台代码页不是 UTF-8 | 先 `chcp 65001`，或设 `PYTHONIOENCODING=utf-8` |

**收集排错信息时请附上**：完整命令、`plan --dry-run` 的输出、`--report` 产出的证据 JSON、原始报错文本。
**不要在报错信息或截图里带上你的 API Key。**

### 退出码（可直接用于流水线）

| 退出码 | 含义 |
|---|---|
| `0` | 全部成功且闸门全绿 |
| `2` | 调用失败（网络 / 鉴权 / 点数 / 模型名 / 输出目录不合法） |
| `3` | **闸门拦下**：比例不符、超预算、违禁词、照抄示例、无实测单价 |
| `4` | 需要 `--yes` 确认（还没花钱，也没提交） |
| `5` | 达到 `--max-seconds` 上限中断（可续跑） |
| `130` | 用户中断（Ctrl+C） |

**`--json` 输出契约**（给流水线与 agent 消费，**只在 `--json` 下生效**）：

- 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
- 失败：stdout 输出一个 JSON 信封，形如
  `{"ok": false, "exit": 3, "error": {"kind": "gate", "message": "…"}}`（`exit` 就是本次真实退出码），
  `kind` 取 `gate` / `usage` / `budget` / `call` / `interrupt` / `internal`。
  `internal` 是**没预料到的异常**（代码 bug）的兜底：此时 stdout 给信封、
  **完整 traceback 原样打到 stderr**、退出码固定 1 —— 报 bug，不藏 bug
  —— 只有在**本次还没吐过任何 JSON 结果**时才补这个信封；已经吐过结果时
  （例如跑到一半才发现比例不合格），`ok` 就写在那个结果里，退出码不变
- 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出与以前完全一致
- `--json` 写在子命令**前面或后面都可以**


## 成本口径

| 项 | 实测 |
|---|---|
| `nano_banana` 1K 出图 | **24 点/张** = 0.24 元 |
| 充值比例 | 1 元 = 100 点 |
| 提交时冻结 | 实测 `frozen_points = 31.2`（**预冻结，不是最终扣费**） |
| 完成后结算 | `usage.points_cost = 24` |
| 失败 | 全额退回 |

**只信 `usage.points_cost`。** 平台的 `pricing_matrix` / `tenant_*` 字段我们验证过**半数不可信**：
`image_human` 字段写 1.5/2/4/8 点/秒、实测 2/3/6/12；`voice_tts/stt` 字段写 30、实扣 40。
那些字段只能当参考，不能当结算价写进文档。

`frozen_points` 也**不是**最终扣费：实测冻结 31.2、实扣 24，差 30%。

## 文件结构

```
sanjianke-image-factory/
├── SKILL.md                          本文件
├── README.md                         给人看的说明
├── LICENSE.md                        MIT，署名三剪客
├── references/
│   ├── platform-specs.md             各平台尺寸规范与安全区
│   ├── prompt-writing.md             出图提示词写法与各平台视觉风格
│   └── cost-and-troubleshooting.md   计费口径、实测数据与排错
└── scripts/
    ├── a7w.py                        api.a7w.cn 零依赖客户端（**逐字节等于规范版，本包不改它**）
    ├── imgprobe.py                   图片头探针：读真实像素 PNG/JPEG/GIF/WebP（只读，纯标准库）
    └── run.py                        plan / gen / cost / models
```

## 端点速查

算力集市（api.a7w.cn）的出图是**两步异步任务**（下面每一行的域名都来自算力集市 api.a7w.cn）：

| 用途 | 方法与路径 |
|---|---|
| 提交出图任务（算力集市 api.a7w.cn） | `POST https://api.a7w.cn/api/v1/apps/nano_banana/submit` |
| 查任务结果（本包用它） | `GET https://api.a7w.cn/api/v1/tasks/<task_id>` |
| 查任务结果（应用级，备用；同属算力集市 nano_banana） | `GET https://api.a7w.cn/api/v1/apps/nano_banana/query?task_id=<task_id>` |
| 看某应用的接口与参数 | `GET https://api.a7w.cn/api/v1/apps/nano_banana` |
| 在架应用清单 | `GET https://api.a7w.cn/api/v1/apps` |
| 在架模型清单 | `GET https://api.a7w.cn/api/v1/models` |
| 出方案用的大模型 | `POST https://api.a7w.cn/api/v1/chat/completions` |

**没有 `/generate` 这个端点。** 「文生图」是 `submit` 的 `action=generate` **参数**，
不是独立的 api 路径——我们之前凭记忆写错过，被实测纠正，这里留个记号。

`submit` 的参数名（用 `python3 scripts/a7w.py schema nano_banana` 实查，别猜）：
`prompt` / `action`(generate|edit) / `resolution`(1K|2K|4K) / `aspect_ratio` / `image_urls` / `model` / `callback_url`

## 联系我们

遇到问题可加技术微信 9872659。

## 相关链接

- 算力集市 api.a7w.cn（注册领 Key）：https://api.a7w.cn/
- 各平台尺寸规范：`references/platform-specs.md`
- 出图提示词写法：`references/prompt-writing.md`
- 计费口径与排错：`references/cost-and-troubleshooting.md`

---

> **免责声明**：本包内置的违禁词表与判定口径是**启发式自检工具**，来自公开经验整理，
> 不构成法律意见，也不代表任何平台的官方审核标准。
> 配图的版权、肖像权、商标权与合规责任由使用者承担；
> 涉及真人、品牌 logo、医疗健康、金融等高风险内容必须人工复核后再发布。
