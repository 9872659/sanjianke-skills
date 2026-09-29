---
name: sanjianke-storyboard-art
slug: sanjianke-storyboard-art
displayName: 三剪客 · 漫画分镜出图
description: "把剧本变成**漫画分镜序列**：抽角色设定卡（外貌/服装/配色/特征词）→ 出分镜表（景别/机位/画面/对白）→ 逐格出图 → 跨格一致性自检 → 本地拼页。难点：**同一角色在 N 格里长得一样**：用「设定卡 + 硬约束提示词 + 多参考图（action=edit 传上一格/锚点）」三道一起压，且不替你补词——哪格漏了哪条特征词就报出来。走 api.a7w.cn 的 nano_banana，零依赖。七道硬闸门：合规、占位符、照抄示例、比例真伪（--snap-exact 裁准）、分镜结构、角色一致性、成本与位置。断点 key 含八维，改一维就重出。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "「每格长得不一样」最翻车：同一个主角在第 1 格和第 12 格是两张脸。本包六个子命令：`characters` 抽角色设定卡（features 是跨格复述凭据）、`shots` 出分镜表、`images` 逐格出图（先报价）、`consistency` 零成本跨格自检、`sheet` 本地拼页。压一致性三道一起上：设定卡写死可视觉特征、每格提示词逐字复述这些特征、再用 action=edit 加 image_urls 把上一格或锚点图当参考。一致性闸门**不替你补词**：逐字核对每格提示词，报出「第几格 · 哪个角色 · 漏了哪个词」。实测：nano_banana 1K = 24 点/张，冻结 31.2 点、实扣 24 点，只信 usage.points_cost；上游按 32 对齐，3:4 实测给 864x1184（偏差 2.70%），要精确就 --snap-exact 裁到 864x1152。拼页内置纯标准库 PNG 解码/缩放/合成；图上不渲染文字（零依赖做不了字形光栅化，AI 出的文字也必错），对白另出 dialogue.md。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 漫画
  - 分镜
  - api.a7w.cn
---

# 三剪客 · 漫画分镜出图

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

## 能做什么

给一个剧本或小说片段，**产出漫画分镜序列**：角色设定卡 → 分镜表 → 逐格出图 →
跨格一致性自检 → 拼页排版。

它替代的是漫画/条漫/分镜稿流程里最耗人的那一段：不是"画不出图"，
而是**"同一角色在第 1 格和第 12 格是两张脸"**、以及"每格该用什么景别、机位、什么比例"。

| 子命令 | 做什么 | 花钱吗 |
|---|---|---|
| `characters` | 从剧本抽**角色设定卡**（外貌/服装/配色/特征词） | **只花文本钱**（实测 ~1.4k token / 3~4 秒） |
| `shots` | 出**分镜表**：每格景别 / 机位 / 画面描述 / 对白 / 出图提示词 | **只花文本钱**（实测 ~5 秒） |
| `images` | 按分镜表**逐格出图**，支持参考图传递 | **真花钱**，先报价，要 `--yes` 才提交 |
| `consistency` | **跨格一致性自检**：特征词覆盖率 / 配色漂移 | **零成本**（一次接口都不调） |
| `sheet` | **拼页排版**（条漫 / 页漫网格），本地渲染 | **零成本**（纯本地） |
| `all` | 串全链路 + 断点续跑 | 文本 + 出图 |
| `cost` | 只算钱不出图 | 免费 |

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 实测 **24 点/张**（1K）= **0.24 元/张**，1 元 = 100 点；`images` 跑之前会先把总价打出来 |
| 要多久 | 单张实测 **60 秒级**（含排队）；文本两步 ~3~6 秒 |
| 要装什么 | **什么都不用装**，只用 Python 标准库。装了 Pillow 拼页更清晰（走 LANCZOS） |
| 角色怎么保证一样 | 三道一起上，见下面「角色一致性到底怎么做」——这是本包的核心 |
| 中断了怎么办 | **断点续跑**：已完成的格直接跳过、已提交未完成的用 `task_id` 续查；**断点 key 含八维**（提示词全文摘要 / 比例 / resolution / 模型 / action / 角色设定卡 / 参考图 / 格号） |
| 会瞎编吗 | 提示词写死"不编剧本里没有的数字与人名"，并用合规闸门兜底 |

### 与同族包的分工（别把本包做成「给小说出配图」）

| 包 | 产物 | 与本包的关系 |
|---|---|---|
| 新媒体配图工厂 | **文章配图**（封面/内文），格与格之间没有角色关系 | 本包要的是**分镜**：每格有景别机位、同一角色跨格一致 |
| 长文自动生产线 | **长文 + 配图** | 同上 |
| 短剧出片类包 | **成片（视频）** | 本包产物是**静态分镜图序列 + 拼好的漫画页**，不出视频 |
| **本包** | **分镜图序列 + 拼页（漫画页 / 条漫）** | 交付物能直接进漫画排版流程 |

## 怎么用（命令行）

### 第 0 步：获取 API Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`）。

### 第 1 步：装依赖

**零依赖。** 不需要 `pip install` 任何东西，只要机器上有 Python 3.7+：

```bash
python3 --version
```

> **约定**：`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端，我们靠
> 「包内副本 SHA256 == 规范版」批量校验各包的客户端有没有被意外改坏。
> 所以本包**没有**为了自己的业务去改它——需要读图片像素就独立出 `imgprobe.py`，
> 拼页需要解 PNG 就写在 `run.py` 里。

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

### 第 3 步：开工前先现查接口与在架模型（免费）

```bash
python3 scripts/a7w.py schema nano_banana
python3 scripts/run.py models
```

`schema` 会打出 `submit` 的真实参数名与 `query` 的调用方式。
**参数名别凭记忆写**——本包用到的字段是
`prompt / action / model / image_urls / resolution / aspect_ratio / callback_url`，
且 schema 里 `caps.max_reference_images = 12`（参考图上限，本包按硬约束用）。

### 第 4 步：抽角色设定卡（只花文本钱）

```bash
python3 scripts/run.py characters 剧本.md --max-chars 6 --out characters.json
```

想先看不花钱的提示词：

```bash
python3 scripts/run.py characters 剧本.md --dry-run
```

产出长这样（`features` 是全篇一致性的**唯一凭据**）：

```
# chen       陈默（主角）
     特征词：黑色短碎发、深棕瞳色、窄长脸、右手背机油污渍、左眉尾一道浅疤
     配色：深蓝 #2B3A55、灰白 #D9D9D2、暗棕 #5A3E2B
     服装：深蓝色棉布工作围裙配灰白衬衫，袖口卷至小臂
```

### 第 5 步：出分镜表（只花文本钱）

```bash
python3 scripts/run.py shots 剧本.md --characters characters.json \
    --count 12 --per-page 4 --out shots.json
```

`shots` 出完就会**顺手跑一遍一致性闸门**：哪一格漏了哪条特征词，当场报出来。

### 第 6 步：先算钱（不出图）

```bash
python3 scripts/run.py cost --count 12
# 预估成本：12 张 × 24 点 = 288 点 = 2.88 元

python3 scripts/run.py cost --count 12 --budget 200
# 超预算 → 打印「images 会被拦下」并返回退出码 3
```

### 第 7 步：逐格出图（真花钱）

```bash
# 先不带 --yes 跑一次：只报价，不提交
python3 scripts/run.py images --shots shots.json --characters characters.json \
    --outdir ./out

# 确认了再加 --yes（--snap-exact 让每格比例像素级精确，拼页才对得齐）
python3 scripts/run.py images --shots shots.json --characters characters.json \
    --outdir ./out --budget 300 --yes --snap-exact --ref-mode prev \
    --report evidence.json
```

**参考图**（压一致性的主要手段）由 `--ref-mode` 决定：

| 值 | 含义 | action |
|---|---|---|
| `prev`（默认） | 每一格把**上一格已经出好的图**当参考图（用任务返回的 `image_url`） | 第 1 格 `generate`，其余 `edit` |
| `anchor` | 用**角色锚点图**（设定卡里的 `anchor_urls`，或 `--anchor chen=<URL>`） | 有锚点就 `edit` |
| `both` | 锚点图 + 上一格都给 | `edit` |
| `none` | 纯文生图 | `generate` |

> **参考图必须是公网可访问的 HTTP/HTTPS 地址**（上游 `image_urls` 的口径），
> 本地文件传不上去。本包**不做上传**：schema 里没有实测过的图片上传路径，
> 与其编一个，不如把边界写清楚。想给角色做锚点图，可以先用本包出一张
> 角色设定图，再把它返回的 `image_url` 当锚点。

### 第 8 步：跨格一致性自检（零成本）

```bash
python3 scripts/run.py consistency --shots shots.json --characters characters.json
```

```
  ✓ chen       出场  4 格，特征词 5 条，漏词的格：无
  ✓ woman      出场  2 格，特征词 5 条，漏词的格：无
  结论：通过
```

漏了就长这样（**明确指出是哪一格漏了哪个词**）：

```
  ✗ chen       出场  3 格，特征词 5 条，漏词的格：3
     !! 第 3 格 · 陈默（chen）漏了特征词「左眉尾一道浅疤」
  结论：不通过（漏词如上）
```

### 第 9 步：拼页排版（零成本，本地渲染）

```bash
# 条漫：单列竖排
python3 scripts/run.py sheet --shots shots.json \
    --state ./out/storyboard-state.json --outdir ./pages \
    --layout strip --rows 4 --panel-w 620

# 页漫：2 列 x 2 行一格一页
python3 scripts/run.py sheet --shots shots.json \
    --state ./out/storyboard-state.json --outdir ./pages \
    --layout grid --cols 2 --rows 2 --panel-w 580 --panel-h 620 --fit contain
```

产出 `page-01.png`、`page-02.png`… 与 `dialogue.md`（逐格对白/旁白清单）。
**每一页的真实像素会读回复核**（不信自己写的尺寸变量）。

### 一条命令跑完整条链路

```bash
python3 scripts/run.py all 剧本.md --outdir ./storyboard --count 12 \
    --ref-mode prev --budget 300 --yes --snap-exact \
    --layout grid --cols 2 --rows 2
```

产出目录长这样：

```
./storyboard/
├── characters.json              角色设定卡（含 version 摘要）
├── shots.json                   分镜表
├── consistency.json             跨格一致性自检明细
├── images/                      逐格分镜图（**在包外**）+ 出图断点
│   ├── 1-p01-3x4-prev-<key>.png
│   └── storyboard-state.json    断点文件（八维 key）
├── pages/                       拼好的页
│   ├── page-01.png
│   └── dialogue.md              对白清单（字另外加）
└── storyboard-state.json        全链路断点（文本步骤 + 出图步骤）
```

中断了就**原样重跑**：文本步骤按「剧本摘要 + 模型 + 风格 + 格数」判定，
出图按八维 key 判定，都没变就不会重复扣费。

### 直接用 curl 调（不依赖本包脚本）

底层就是算力集市 api.a7w.cn 的标准两步异步任务。
**注意没有 `/generate` 这个端点**——"文生图"是 `submit` 的 `action=generate` **参数**：

```bash
# 文生图（第 1 格）
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/nano_banana/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"…分镜提示词…","action":"generate","model":"nano-banana",
       "resolution":"1K","aspect_ratio":"3:4"}'

# 参考上一格（第 2 格起）：action=edit + image_urls
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/nano_banana/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"…分镜提示词…","action":"edit","model":"nano-banana",
       "resolution":"1K","aspect_ratio":"3:4",
       "image_urls":["https://…/上一格返回的 image_url.png"]}'
```

拿 `data.task_id` 去轮询（**`status` 在 `data` 顶层**，不在 `data.result` 里）：

```bash
curl -sS "https://api.a7w.cn/api/v1/tasks/task_xxxxxxxxxxxx" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

## 参数说明

### 全局

| 参数 | 说明 |
|---|---|
| `--key` | 临时指定 Key；优先级最高。**别把它写进脚本或文档** |
| `--json` | 以 JSON 输出，**写在子命令前面或后面都可以**；JSON 模式下 stdout 只有一个完整 JSON，报价与进度走 stderr |

### `characters` —— 抽角色设定卡

| 参数 | 说明 |
|---|---|
| 位置参数 / `--script` | 剧本文件（可多份，会拼起来） |
| `--max-chars` | 最多抽几个角色，默认 `8` |
| `--style` | 全篇画风口径（会给到模型） |
| `--title` | 剧本标题（可选，帮模型定调） |
| `--out` | 把设定卡写成 JSON，`shots` 要用它 |
| `--dry-run` | 只打印提示词，**不调模型、不花钱** |

### `shots` —— 出分镜表

| 参数 | 说明 |
|---|---|
| `--characters` | **必填**。`characters` 产出的设定卡 JSON |
| `--count` | 最多几格（截断） |
| `--per-page` | 每页几格，默认 `4`（决定 `page` / `panel` 字段） |
| `--style` | 覆盖全篇画风（不传就用设定卡里的 `style_bible`） |
| `--min-feature-ratio` | 特征词覆盖率下限，默认 `1.0`（**全部必须出现**） |
| `--min-palette-ratio` | 配色覆盖率下限，默认 `0.0`（只报告不拦） |
| `--out` | 把分镜表写成 JSON，`images` 要用它 |

### `images` —— 逐格出图

| 参数 | 说明 |
|---|---|
| `--shots` / `--characters` | **必填**。分镜表与设定卡 |
| `--outdir` | 图片输出目录，默认 `%TEMP%\storyboard-images`；**不可是包内目录** |
| `--count` | 最多出几格（**真闸门**：在报价与提交之前就截断，少花钱） |
| `--ref-mode` | `prev`（默认）/ `anchor` / `both` / `none`，见上表 |
| `--anchor ID=URL` | 角色锚点图，可重复；URL 必须公网可访问 |
| `--ref-urls URL` | 额外参考图，可重复 |
| `--resolution` | `1K`（默认）/ `2K` / `4K`。**只有 1K 有实测单价** |
| `--model` | 出图模型，默认 `nano-banana`。换模型就没有实测单价了，要给 `--points-per-image` |
| `--budget` | 成本上限（**点**）。预估超了直接停；每格提交前还会再核一次 |
| `--yes` | 确认真的花钱。**不加就只报价、一个任务都不提交** |
| `--snap` | 出图后按请求比例裁剪，**超容差才裁** |
| `--snap-exact` | **只要不是像素级精确就裁准**（拼页必需：格子比例不齐整页留白就不齐） |
| `--ratio-tolerance` | 比例容差，默认 `0.03`（实测最大偏差 2.86%）；有 0.0025 的量化地板 |
| `--poll-timeout` | 单格轮询超时秒数，默认 `600`（**上限，不是期望时长**） |
| `--max-seconds` | 整批最长耗时，到点中断（退出码 5），已完成都在断点里，重跑可续 |
| `--state` | 断点文件路径，默认 `<outdir>/storyboard-state.json` |
| `--force` | 忽略断点全部重出（**会重复扣费**） |
| `--stop-on-error` | 一格失败就整体停 |
| `--allow-prompt-hits` | 提示词命中违禁词/占位符/照抄示例也出图（默认**拦截**） |
| `--allow-gate-hits` | 分镜结构/角色一致性不合格也出图（默认**拦截**） |
| `--report` | 把本次证据（请求参数 / 任务原文 / 真实像素 / 一致性）写成 JSON |

### `consistency` / `sheet` / `cost` / `models`

| 子命令 | 关键参数 |
|---|---|
| `consistency` | `--shots` / `--characters` / `--min-feature-ratio` / `--min-palette-ratio` / `--report` |
| `sheet` | `--shots` / `--state`（或 `--imgdir`）/ `--outdir` / `--layout strip\|grid` / `--cols` / `--rows` / `--panel-w` / `--panel-h` / `--gutter` / `--margin` / `--fit contain\|cover` / `--bg` |
| `cost` | `--count`（必填）/ `--resolution` / `--model` / `--points-per-image` / `--budget` |
| `models` | 无（免费） |

## 七道本地硬闸门

闸门都是**拦截 + 标红 + stderr 汇总 + 非 0 退出码**，不是"提示一下"。
因为出图是**按次扣费**的，事后发现问题的代价是真金白银；
而分镜场景更贵——一致性崩了要整批重画。

### 1. 合规：广告法违禁词（「最X」有可枚举豁免，**句首不豁免**）

绝对化用语（最/第一/国家级/100%）、虚构权威背书、医疗功效、投资承诺、站外导流，命中即拦。

但**「最X」有一层上下文豁免**，因为剧本与分镜说明里到处是这种正常写法：
「这一幕**最**重要的是沉默」「新手**最**容易踩的坑」。豁免规则是：
命中处**后面**接的必须是可枚举的比较/程度词（不同、区别、共同、常见、容易、重要…，
允许一个「的」），**且命中处不在句首/行首**。两条缺一不可：

| 输入 | 结果 |
|---|---|
| `最大的区别是这只表…`（句首） | **拦** —— 句首的最高级写法经常正是标题式宣称 |
| `这是两种走时最大的区别所在` | 放行 —— 后文是「（的）区别」，且不在句首 |
| `本市最好的钟表铺` | **拦** —— 后文「好的钟表铺」不在豁免表里 |

豁免表**写死在代码里、可枚举、可复核**，不是一句"人工判断"了事。
已知保守行为：「占比最高、且最容易改」这种**顿号后接豁免词**的写法仍会被拦
（不给标点开豁免，否则「最好的工具，值得买」也会被放行）。改文案解决，不放松规则。

### 2. 占位符残留

`{}` / `{{角色}}`、`[待填]` / `[待补充]`、`XXX` / `xxx`、`（此处省略）`、`待补充` 类字样，
命中即拦。`[1]`（序号）、`[图 2]`（配图位）是正常写法，不误伤。

### 3. `prompt_echo` —— 照抄提示词示例

**这条是从标题工坊的事故来的**：提示词里写过的示例，哪怕明确标着"这是错的写法"，
模型照样照抄——那一轮最高分 89.0 的标题**一字不差就是提示词里的示例**。

分镜场景下它更隐蔽：一格长得跟示例一样你不会发现，等到拼页才看出
"怎么每格都是同一张脸同一个构图"——而那正是本包要防的事。

三条判据（任一命中即拦）：

| 判据 | 阈值 | 抓什么 |
|---|---|---|
| 去标点后**完全相同** | — | 最直接的照抄 |
| 字符二元组 **Jaccard** | ≥ 0.75 | 长度相当的同构改写 |
| 示例二元组**覆盖度** | ≥ 0.60 | 把示例**夹带**进更长的提示词 |

第三条是补漏：出图提示词动辄 60~140 字而示例只有 25 字，Jaccard 的分母是两份二元组的
**并集**，示例那一侧被长提示词摊薄得极狠——示例原样嵌进 102 字的提示词里只有 0.245（放行），
而覆盖度是 **1.000**（拦下）。覆盖度只看"示例被抄了多少"，不看提示词有多长。

另加**相对**长度守卫：目标长度 < `max(6, len(示例)//2)` 就不比相似度与覆盖度
（短串的二元组集合太小，指标会虚高）。

### 4. 比例真伪：读回真实像素，不信自报字段

**不信接口返回里的任何比例字段**，把图下载回来读文件头，用真实宽高算比例。

实测到的上游特性（这决定了容差怎么定）：上游不是按比例给像素，而是先定总像素、
再把每边向下对齐到 **32 的倍数**。所以 10 种比例里有 5 种拿不到像素级精确比例：

| 请求 | 实测像素 | 实际比例 | 偏差 |
|---|---|---|---|
| 3:4 | 864x1184 | 0.7297 | **2.70%** |
| 16:9 | 1344x768 | 1.7500 | 1.56% |
| 9:16 | 768x1344 | 0.5714 | 1.56% |
| 4:5 | 896x1152 | 0.7778 | 2.78% |
| 5:4 | 1152x896 | 1.2857 | 2.86% |
| 1:1 / 4:3 / 21:9 / 2:3 / 3:2 | 1024x1024 等 | 精确 | 0% |

所以默认容差 **3%**（容差内不算"假"，但真实像素与偏差**照样打印出来，不藏**）。

**拼页场景要加 `--snap-exact`**：容差内不代表比例齐。
实测 3:4 → 864x1184，`--snap-exact` 裁到 **864x1152（偏差 0.0000%）**，
裁完**再读一次文件头复核**，只会把真正裁准的记成合格。
优先用 PIL；没有 PIL 时回落到内置的 8 位 PNG 裁剪器（只用 `zlib` + `struct`），
两条路都走不通时**如实报告"没能裁"**，不假装成功。

### 5. 分镜结构：每格必须有景别 + 画面描述

- **景别**必填，且要能归一化到枚举：大远景 / 远景 / 全景 / 中景 / 中近景 / 近景 / 特写 / 大特写
  （口语化写法给别名表兜住：半身→中近景、全身→全景、大全→远景…）
- **画面描述**必填，且不能短于 8 个字（短于 8 字基本等于没写）
- 出场角色的 `id` 必须存在于设定卡（指向不存在的角色 = 拼页时没人知道画谁）
- **格数为 0 → 拦**（退出码 3）

这条闸门是"漫画"与"配图"的分界线：景别决定读者离人物多远，机位决定读者站在哪，
缺了这一格，拼出来就是"插图集"而不是"漫画"。

### 6. 角色一致性（**本包重点**）

见下一节。

### 7. 成本上限 + 产出位置

- 提交任何任务**之前**先算总价；超 `--budget` 直接停，一个任务都不提交
- 每一格提交前**再核一次**：前面真实扣费可能比预估高，超了就就地停
- `2K` / `4K`、以及**没有实测过的模型** → **拒绝估算**，退出码 3。宁可拒绝也不编一个数
  （想估就给 `--points-per-image`）
- `--outdir` / `sheet --outdir` 落在 Skill 包内 → **退出码 2**（包内不许有任何图片）

## 角色一致性到底怎么做

问题形态：同一个角色在 N 格里要长得一样，不做约束就是 N 张脸。

**三道一起上，少一道都压不住：**

1. **角色设定卡**（`characters`）：把角色的可视觉特征写成 `features` 列表，
   3~6 条、每条 4~12 字，只写看得见的东西（发型发色、瞳色、疤痕位置、固定配饰）。
   自检标准：一个画师只看这几条，画 10 次都能画出同一张脸。
   写"性格冷酷""眼神深邃"是没用的——那些画不出来。
2. **硬约束提示词**（`shots`）：每格的出图提示词里必须**逐字写出**该格出场角色的全部特征词。
   `shots` 的提示词里明确要求了这一点，模型不写全，脸就会自己长。
3. **多参考图**（`images --ref-mode`）：`action=edit` + `image_urls`，
   把**上一格**或**角色锚点图**当参考。这是把"同一场景/同一画风"钉住的主要手段。
   参考图必须是公网可访问的 HTTP/HTTPS 地址。

### 闸门做什么、**不做什么**

闸门逐字核对每格的出图提示词，报出「第几格 · 哪个角色 · 漏了哪个词」。

⚠️ **它不替模型补特征词。** 如果脚本自动把特征词拼进提示词，闸门就永远是绿的——
那是**假绿闸门**，比没有闸门更危险（同族事故：只信模型自报的字段，真该判命的恰好漏判）。
所以本包只核对、不代写：漏了就是漏了，重出或手改分镜表。

⚠️ **核对范围刻意排除画风块**：`style_bible` 是全篇共用的，如果特征词能靠它满足，
某一格漏写特征也照样绿。所以特征词只在**该格自己的 `prompt`** 里找。

### 配色漂移

设定卡里的配色（`name` + `hex`）如果某一格一个都没出现，记一处**配色漂移**并标红。
默认 `--min-palette-ratio 0`（**只报告不拦**），因为配色是风格软约束；
要当硬约束用就把它调到 0 以上（例如 `0.5`）。

### `--ref-mode prev` 实测到的边界

实测（2 格：第 1 格 `generate`，第 2 格 `edit` + 第 1 格的 `image_url`）：
**场景、画风、光线、道具连续性非常好**——同一间钟表铺、同一盏台灯、同一个窗口；
但**多角色同框这件事它压不住**：第 2 格的提示词里写了两个人，产出仍是单人主体。
所以口径是：

- 要压**同场景/同画风连续** → `prev` 很有效
- 要压**同一个角色的脸** → 靠 `features` + 角色锚点图（`--ref-mode anchor`）
- 要**多人同框** → 老老实实把这一格当独立镜头写清楚站位，别指望上一格带出来

## 拼页排版：为什么图上不带字

`sheet` 只做**几何**：解码每一格、按比例缩放、排进网格或竖排、留出装订留白，
然后写出 PNG。画质口径：

| 情况 | 缩放方式 |
|---|---|
| 装了 Pillow | 缩小 LANCZOS / 放大 BICUBIC，PNG 也用 Pillow 写 |
| 没装 Pillow | 缩小走**盒式均值**、放大走**最近邻**（内置纯标准库实现） |

两条路都在产出里**标注用了哪一个**，不假装两者一样。

**为什么不把对白烧进图里**：零依赖做不了字体栅格化（标准库没有字库解析与字形光栅化），
而且 AI 出图的文字基本都是错的——实测提示词里写了"不要文字"，门上还是长出了
`TIME REPAIR` 和镜像的 `OPENING`（同族包也踩过同一个坑：光写一句"不要字幕"压不住）。
所以本包的口径是**图不带字，字另外给**：`sheet` 产出 `dialogue.md`
（逐格对白/旁白/画面描述），交给后期或设计工具加字。这是**明确的设计取舍**，不是遗漏。

## 排错

| 现象 / 报错 | 原因 | 怎么办 |
|---|---|---|
| `鉴权失败（401）` | Key 无效、过期或写错 | 到 https://api.a7w.cn/ 重新领取；确认没把 `Bearer` 重复写进环境变量 |
| 点数不足（HTTP 402） | 账号点数用完 | 到 https://api.a7w.cn/ 充值后重试 |
| `code: 0` 但 HTTP 是 200 | **网关信封里 `code == 1` 才是成功，不是 0** | 看 body 里的 `msg`；脚本已按这个口径判断，别改成 `code == 0` |
| 轮询一直读不到状态 | **`status` 在 `data` 顶层**，不在 `data.result` 里（平台文档写错） | 脚本按实测结构取；自己写脚本时别照文档写 |
| `当前请求未命中可用计费规格` | `model` 与 `resolution` 组合不支持（如普通模型传 `2K`） | 普通 `nano-banana` 只支持 `1K`；要高清档换 `nano-banana-2:official` 之类 |
| 上游 `502` / `upstream timeout` | 网关到上游的瞬时抖动，**实测很频繁** | 脚本已内置退避重试（4 次）。连续失败就换模型或降低批次 |
| 一格卡在 `processing` | 任务卡住了 | 已设 `--poll-timeout`（默认 600 秒）；超时会报出来并保留 `task_id`，可 `python3 scripts/a7w.py task <task_id>` 续查 |
| 真实像素和请求比例差 1%~3% | **上游按 32 对齐**，不是 bug | 拼页用 `--snap-exact` 裁准；或把 `--ratio-tolerance` 放宽 |
| `读不出真实像素` | 下载被截断，或不是图片 | 删掉那条断点记录重出（`--force`），或检查网络 |
| `第 N 格 · X（id）漏了特征词「…」` | 模型没把设定卡里的特征词写进这一格的提示词 | 重跑 `shots`；或手改 `shots.json` 里那一格的 `prompt` 补上（改一个字 key 就变，会重出这一格） |
| `第 N 格结构问题：景别 … 不在枚举里` | 模型写了"看得见人"这种非景别写法 | 改成枚举里的景别；别名表已兜住"半身/全身/大全"这类常见写法 |
| `预估 N 点超过预算上限` | 超了 `--budget` | 提高预算、用 `--count` 少出几格，或先 `cost` 试算 |
| `2K 档没有实测单价，拒绝凭猜估算` | 我们没有 2K/4K 的实测价 | 给 `--points-per-image` 指定单价，或先用 1K 出 |
| `模型 nano-banana-2:official 没有实测单价` | 换模型就没实测价了 | 同上，给 `--points-per-image` |
| `输出目录 ... 在 Skill 包内` | `--outdir` 指到了包里的目录 | 换到包外（`./out`、`%TEMP%\...`）。包内放图片会让上传 400 |
| `参考图最多 12 张` | 超过了 schema 的 `max_reference_images` | 减少 `--anchor` / `--ref-urls` |
| `--anchor` 报 URL 不是 http/https | 上游只收公网地址，本地路径传不上去 | 先把锚点图放到公网可访问的地址（例如用本包出一张设定图，拿它的 `image_url`） |
| 重跑又扣了一次钱 | 提示词/比例/分辨率/模型/action/角色设定卡/参考图**任一维改了** → 断点 key 变了 | 这是设计如此（输入变了就该重画）。想省钱就别改输入，直接重跑会跳过 |
| 改了 `--snap` 配置但产物没变 | 旧版断点里没存原始下载文件 | 脚本会**明确警告**"无法本地重裁"；要对这几格加 `--force`（会重新扣费）。新版断点会自动**本地重裁（零成本）** |
| `sheet` 报「缺图的分镜格：3、4」 | 那几格还没出图 | 先 `images` 把缺的补出来（断点续跑，已有的不重复扣费） |
| `sheet` 报「读不进来」 | 内置解码器只支持 8 位非隔行 PNG | 装 Pillow（能读 JPEG/WebP），或换用 PNG 档出图 |
| `没有找到 API Key` | 三种方式都没配 | `--key` / `A7W_API_KEY` / `python3 scripts/a7w.py login --key sk-xxx` |
| Windows 下中文乱码 | 控制台代码页不是 UTF-8 | 先 `chcp 65001`，或设 `PYTHONIOENCODING=utf-8` |

**收集排错信息时请附上**：完整命令、`--report` 产出的证据 JSON、
`consistency --report` 的明细、原始报错文本。
**不要在报错信息或截图里带上你的 API Key。**

### 退出码（可直接用于流水线）

| 退出码 | 含义 |
|---|---|
| `0` | 全部成功且闸门全绿 |
| `2` | 调用失败（网络 / 鉴权 / 点数 / 模型名 / 输出目录不合法 / 输入文件坏了） |
| `3` | **闸门拦下**：合规、占位符、照抄示例、比例不符、分镜结构、角色一致性、超预算、无实测单价 |
| `4` | 需要 `--yes` 确认（还没花钱，也没提交） |
| `5` | 达到 `--max-seconds` 上限中断（可续跑） |
| `130` | 用户中断（Ctrl+C） |
| `1` | 未预料的内部错误（代码 bug）——`--json` 下给 `kind: "internal"` 信封 + 完整 traceback |

**`--json` 输出契约**（给流水线与 agent 消费，**只在 `--json` 下生效**）：

- 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
- 失败：stdout 输出一个 JSON 信封，形如
  `{"ok": false, "exit": 3, "error": {"kind": "gate", "message": "…"}}`（`exit` 就是本次真实退出码），
  `kind` 取 `gate` / `usage` / `budget` / `call` / `interrupt` / `internal`
- `internal` 是**没预料到的异常**（代码 bug）的兜底：stdout 给信封、
  **完整 traceback 原样打到 stderr**、退出码固定 `1` —— 报 bug，不藏 bug
- 只有在**本次还没吐过任何 JSON 结果**时才补信封；已经吐过结果时，
  `ok` 就写在那个结果里，退出码不变
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
| 2K / 4K · 其它模型 | **没有实测价 → 拒绝估算（退出码 3）** |
| 文本（抽卡/分镜） | 平台不公开大模型单价，本包**只报 token 数，不报金额** |

**只信 `usage.points_cost`。** 平台的 `pricing_matrix` / `tenant_*` / `fixed_price` 字段
我们验证过**半数不可信**（`image_human` 字段写 1.5/2/4/8 点/秒、实测 2/3/6/12；
`voice_tts/stt` 字段写 30、实扣 40）。schema 的 `api_doc` 里列了官方模型的文档价
（28.03 / 35.76 / 61.52 点起），但**那是文档价，不是我们实扣的数**，
所以本包不拿它当结算价，也不敢用它做成本前置。

## 文件结构

```
sanjianke-storyboard-art/
├── SKILL.md                              本文件
├── README.md                             给人看的说明
├── LICENSE.md                            MIT，署名三剪客
├── references/
│   ├── storyboard-method.md              分镜方法：景别/机位/格页/节奏/比例
│   ├── character-consistency.md          角色一致性与画风：设定卡、硬约束、参考图
│   └── cost-and-troubleshooting.md       计费口径、实测数据与排错
└── scripts/
    ├── a7w.py                            api.a7w.cn 零依赖客户端（**逐字节等于规范版，本包不改它**）
    ├── imgprobe.py                       图片头探针：读真实像素 PNG/JPEG/GIF/WebP（只读，纯标准库）
    └── run.py                            characters / shots / images / consistency / sheet / all / cost / models
```

## 端点速查

算力集市（api.a7w.cn）的能力全部走下面这些端点（域名都来自算力集市 api.a7w.cn）：

| 用途 | 方法与路径 |
|---|---|
| 提交出图/改图任务 | `POST https://api.a7w.cn/api/v1/apps/nano_banana/submit` |
| 查任务结果（统一入口，本包用它） | `GET https://api.a7w.cn/api/v1/tasks/<task_id>` |
| 查任务结果（应用级，备用） | `GET https://api.a7w.cn/api/v1/apps/nano_banana/query?task_id=<task_id>` |
| 看某应用的接口与参数 | `GET https://api.a7w.cn/api/v1/apps/nano_banana` |
| 在架应用清单 | `GET https://api.a7w.cn/api/v1/apps` |
| 在架模型清单 | `GET https://api.a7w.cn/api/v1/models` |
| 抽设定卡 / 出分镜表用的大模型 | `POST https://api.a7w.cn/api/v1/chat/completions` |

`submit` 的参数名（用 `python3 scripts/a7w.py schema nano_banana` 实查，别猜）：
`prompt` / `action`(generate\|edit) / `model` / `image_urls` / `resolution`(1K\|2K\|4K) /
`aspect_ratio` / `callback_url`。

**没有 `/generate` 这个端点。** 「文生图」是 `submit` 的 `action=generate` **参数**，
不是独立的 api 路径——我们之前凭记忆写错过，被实测纠正，这里留个记号。

## 联系我们

遇到问题可加技术微信 9872659。

## 相关链接

- 算力集市 api.a7w.cn（注册领 Key）：https://api.a7w.cn/
- 分镜方法与格页比例：`references/storyboard-method.md`
- 角色一致性与画风：`references/character-consistency.md`
- 计费口径与排错：`references/cost-and-troubleshooting.md`

---

> **免责声明**：本包内置的违禁词表与判定口径是**启发式自检工具**，来自公开经验整理，
> 不构成法律意见，也不代表任何平台的官方审核标准。
> 分镜图与漫画成品的版权、肖像权、商标权与合规责任由使用者承担；
> 提示词里不要要求生成具体品牌 logo、真实人物姓名或受保护的既有角色形象，
> 涉及真人、品牌 logo、医疗健康、金融等高风险内容必须人工复核后再发布。
