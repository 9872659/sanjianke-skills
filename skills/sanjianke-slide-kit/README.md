# 三剪客 · 课件配图与排版

给一份**讲义 / 大纲**，一条链路产出**一份能直接上课的课件**：

```
outline   →   pages    →   images    →   render
分页方案      每页内容      按页配图      本地排版
页型/标题/     成稿要点/     真花钱·先报价· 逐页 PNG + notes.md
配图意图       讲稿备注      断点续跑       + 可选 deck.html（零成本）
（文本钱）     （文本钱）                  （零网络，需要 PIL）
```

面向**知识付费、企业内训与录课老师**。**跑之前先告诉你花多少钱**，
一页放不下、图上要写字这种"上讲台才会发现"的问题，在报价阶段就拦下。

```
outline →  分页方案（每页页型 / 标题 / 粗要点 / 配图意图）只花文本钱
pages   →  成稿（每页 1~6 条要点 + 80~400 字讲稿备注）只花文本钱
images  →  按页出配图（**画面里不许有文字**），先报价、断点续跑
render  →  本地排版成逐页 PNG + notes.md + deck.html（零成本、零网络，需要 PIL）
all     →  串起全流程，断点续跑
cost    →  只算钱，一次调用都不发
models  →  列出在架模型与应用
```

## 30 秒上手

```bash
# 1) 拿 Key（新用户有赠送点数）
#    到 https://api.a7w.cn/ 注册，创建一个 API Key

# 2) 配 Key
export A7W_API_KEY="<你的Key>"          # Windows: $env:A7W_API_KEY="<你的Key>"

# 3) 装 pillow（**只有 render 需要**，其余全零依赖）
pip install pillow

# 4) 先算钱（不出网）
python3 scripts/run.py cost --pages 12 --every 2

# 5) 分页方案 + 成稿（只花文本钱）
python3 scripts/run.py outline 讲义.md --pages 12 --level basic --outdir D:/slides/ep01
python3 scripts/run.py pages --outdir D:/slides/ep01

# 6) 出配图：先报价（不加 --yes 也不给 --budget，在报价阶段就停）
python3 scripts/run.py images --outdir D:/slides/ep01 --every 2

# 7) 确认了再出（--budget 本身就是"确认"，会花到上限为止）
python3 scripts/run.py images --outdir D:/slides/ep01 --every 2 --yes

# 8) 本地排版（零成本、零网络）
python3 scripts/run.py render --outdir D:/slides/ep01

# 9) 想一条命令跑完
python3 scripts/run.py all 讲义.md --pages 12 --outdir D:/slides/ep01 --budget 5
```

**零第三方依赖**：只要 Python 3.7+。`scripts/a7w.py` 与 `scripts/imgprobe.py` 只用标准库。
唯一的例外是 `render` 需要 `pillow`；没有的话它**明确报错退出（`exit=2`）**，
而不是假装成功、更不是产出一份没有版式的"课件"。

`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端（我们靠 SHA256 校验各包副本
是否一致），本包**逐字节没有改它**；本包的业务逻辑全在 `scripts/run.py` 里。

## 能做什么

给一份**讲义 / 大纲**，一条链路产出**一份能直接上课的课件**，
并保证"每一页都讲得清、图上的字一定清晰"。

它替代的是备课里**最后也最容易翻车**的那一步：不是"写不出讲义"，
而是"讲师站在投影前发现这一页讲不清"——一页塞了三个概念、图上写着错字、
要点长到看不清、备注没写所以讲师临场编。

| 子命令 | 干什么 | 花钱吗 |
|---|---|---|
| `outline` | 读讲义 → 分页方案（页型 / 标题 / 粗要点 / 配图意图） | **只花文本钱** |
| `pages` | 展开成成稿（1~6 条要点 + 80~400 字讲稿备注） | **只花文本钱** |
| `images` | 按页出**配图** | **真花钱**，实测 **24 点/张 = 0.24 元**（1K），先报价 |
| `render` | **本地排版**成逐页 PNG + `notes.md` + `deck.html` | **零成本、零网络** |
| `all` | 串起全流程，**断点续跑** | 按阶段花钱 |
| `cost` / `models` | 只算钱 / 现查在架模型 | 零成本 |

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 出图实测 **24 点/张**（1K）= **0.24 元/张**，1 元 = 100 点，跑之前先把总价打出来 |
| 要多久 | 分页方案 5.8 秒 / 成稿 11.9 秒 / 出图单张 5~40 秒 / **本地排版 7 页 0.7 秒** |
| 要装什么 | **零第三方依赖**；`render` 需要 `pillow`，没有就**明确报降级（exit=2）** |
| 图上文字会不会糊 | **不会**：出图提示词里不许出现任何文字，页上的字全部由本地排版压上去 |
| 一页讲不完怎么办 | **拦截**，并报出实际像素与可用像素；**绝不静默截断、也不自动缩字号** |
| 中断了怎么办 | **断点续跑**：已完成的跳过、已提交的用 `task_id` 续查（不重复扣费） |
| 改了版式要重出图吗 | **不用**。文字版式与出图是两条独立断点，只改版式就只重渲（实测精确重渲 3/7 页） |
| 有 PPTX 吗 | **没有**。给的是逐页 PNG + `deck.html`（HTML 可直接打印或导进 PPT） |
| 输出放哪 | `--outdir` **必须在包外**；指到包内直接 `exit=2` |

### 它和同族 L2 各包不是一回事

| | 输入 | 产出 | 最小单位 | 有版式引擎吗 |
|---|---|---|---|---|
| `sanjianke-course-outline` | 一个主题 | 大纲 / 讲义 / 习题（**纯文本**） | **节**（1500~3000 字散文） | 无 |
| `sanjianke-image-factory` | 一篇文章稿 | 文章各段的**配图** | **图** | 无 |
| `sanjianke-cover-factory` | 一批标题 | 同一标题 × N 平台的**封面** | **封面**（图 + 一行大字） | 有，但**单张** |
| **本包** | **一份讲义** | **一份课件**（逐页 PNG + 备注） | **页**（页型 + 标题 + 要点 + 备注 + 配图意图） | 有，**多页** |

四个包里只有本包有「**页**」这个数据结构，也只有本包会问"这一页放不放得下"，
并用**真实字体排版后**给出像素级的结论。

> **与「给讲义配图」的区别**：配图只是本链条里的**一步**，而且产出的图**不含任何文字**
> ——字全部由本地排版压上去。同族的 `image-factory` 是把文字交给模型"画"进画面，
> 本包刻意反过来做，因为出图模型画中文大字基本是错的。

### 四种页型

| 页型 | 用途 | 版式 |
|---|---|---|
| `cover` 封页 | 第一页 | 配图整幅铺底 + 压暗 + 标题居中（92px） |
| `section` 章节页 | 章节切换 | 同封页，标题略小（71px） |
| `content` 内容页 | 绝大多数页 | **左文右图**；无图时文字限宽 70% |
| `summary` 小结页 | 最后一页 | 同封页，居中 |

**无图版式是设计内的一等公民**：`--every 2` 表示每 2 页配一张图，
没配图的页用「文字限宽版式」渲染（不是留白凑数、也不复用上一页的图）。

### 三个配色主题

`ink`（默认，浅底深字，适合投影与打印）/ `night`（深底浅字，适合录屏）/
`warm`（米底暖字，适合知识付费）。

## 怎么用（命令行）

### 第 0 步：获取 API Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`）。
**本包不内嵌任何密钥，也不代付费用。**

### 第 1 步：装依赖

```bash
python3 --version      # 需要 3.7+
pip install pillow     # 只有 render 需要；其余命令零依赖
```

`render` 还需要一个能渲染中文的**系统字体**（会自动在
`msyhbd.ttc` / `msyh.ttc` / `simhei.ttf` / `PingFang.ttc` / `NotoSansCJK` 等里找），
找不到就用 `--font <路径>` 指定。**包内不打包字体**（授权问题）。

### 第 2 步：填 Key

```bash
export A7W_API_KEY=sk-你的key              # Windows: $env:A7W_API_KEY="sk-你的key"
python3 scripts/a7w.py login --key sk-你的key   # 或存进 ~/.a7w/config.json 反复用
```

### 第 3 步：确认网关通（免费）

```bash
python3 scripts/run.py models
python3 scripts/run.py models --type text
python3 scripts/a7w.py schema nano_banana     # 出图参数现查，别凭记忆
```

### 第 4 步：算钱 + 出分页方案 + 展开成稿

```bash
python3 scripts/run.py cost --pages 12 --every 2
python3 scripts/run.py outline 讲义.md --pages 12 --level basic --outdir D:/slides/ep01
python3 scripts/run.py pages --outdir D:/slides/ep01
```

想先看不花钱的提示词：`outline 讲义.md --pages 12 --dry-run`。

### 第 5 步：出配图（真花钱）

```bash
python3 scripts/run.py images --outdir D:/slides/ep01 --every 2            # 只报价
python3 scripts/run.py images --outdir D:/slides/ep01 --every 2 --yes      # 确认后出
```

> ⚠️ **`--budget` 本身就是确认。** `need_yes = 不加 --yes 且 没给 --budget`。
> 给了 `--budget` 就会真的出图，花到上限为止。只想看价钱就**两个都不加**。

### 第 6 步：本地排版

```bash
python3 scripts/run.py render --outdir D:/slides/ep01
python3 scripts/run.py render --outdir D:/slides/ep01 --theme night --no-html
```

产出目录：

```
D:/slides/ep01/
├── deck.json                  分页方案 + 成稿（含不可变的 skeleton_pages）
├── deck.md                    人读的分页稿
├── images/p01.png ...         配图（**无字**，比例已复核）
├── slides/slide-01.png ...    **成片课件**（逐页 PNG，1920x1080）
├── slides/deck.html           可选：自包含 HTML，可直接打印 / 导进 PPT
├── notes.md                   讲稿备注单独成册
├── AUDIT.md                   自检报告（逐页像素 / 字节 / 比例复核 / 告警）
└── slide-kit-state.json       断点文件（重跑不重复扣费）
```

**输出一定要指到包外**（`D:/slides/...`、`%TEMP%\...`）。包内白名单只收
`.md .py .txt .json .sh .js .yaml .yml .csv`，塞图片会让上传 400。

中断了就**原样重跑**，不会重复扣费：

```bash
python3 scripts/run.py pages  --outdir D:/slides/ep01
# [1/3] 已有成稿，跳过（断点续跑，不再重复扣费）
# 页内容已写出：…（7 页；0 次调用，跳过 3 批）

python3 scripts/run.py render --outdir D:/slides/ep01
# [1/7] #p01 已渲染，跳过（断点续跑）
# 课件已排版完成：…（7 页，跳过 7 页）
```

### 直接用 curl 调文本端点

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"把这份讲义拆成 6 页课件方案，只输出 JSON"}],"temperature":0.7,"max_tokens":8192,"response_format":{"type":"json_object"}}'
```

## 参数说明

### 全局

| 参数 | 说明 |
|---|---|
| `--key` | 临时指定 Key；优先级最高。**别把它写进脚本或文档** |
| `--json` | 以 JSON 输出，**写在子命令前后都可以**；stdout 只有一个 JSON，进度走 stderr |
| `--budget` | 成本上限（**元**），超了退出码 3。**它本身就是出图的确认** |
| `--yuan-per-ktok` | 文本单价（元/千 token），默认 `0.02`。**只是估算口径，不是账单** |
| `--model` / `--temperature` / `--max-tokens` | 默认 `deepseek-chat` / `0.7` / `8192` |
| `--no-json-mode` | 不要求上游返回 JSON（个别模型不支持 `response_format` 时用） |

### `outline` —— 读讲义 → 分页方案

| 参数 | 说明 |
|---|---|
| `<讲义文件>` | 位置参数（Markdown / 纯文本）。也可用 `--text` 直接给正文 |
| `--pages` | 目标页数，默认 `12`。脚本核对实际页数，差超过 1 页就拦 |
| `--level` | `zero` / `basic`(默认) / `advanced` |
| `--audience` / `--topic` | 受众补充说明 / 课程主题 |
| `--outdir` / `--out` | 产出目录（默认 `slide-out`）/ 额外写一份方案 JSON |
| `--from-file` | **零成本闸门自检**：拿一份返回 JSON 过闸门，不调模型 |
| `--dry-run` / `--embed` | 只打提示词 / JSON 输出里嵌入完整 deck |

> **讲义超过 24000 字直接报错（`exit=2`），不会静默截断**——截掉的内容你永远不知道少了什么。

### `pages` —— 展开成成稿

| 参数 | 说明 |
|---|---|
| `--outdir` / `--deck` | 产出目录 / 分页方案文件（默认 `<outdir>/deck.json`） |
| `--only` / `--count` | 只处理这些页（`p03,p05`）/ 最多处理几页 |
| `--style` | 讲课风格补充说明 |
| `--strict-notes` | 缺讲稿备注也算闸门失败（默认只告警） |
| `--from-file` / `--force` | 零成本闸门自检 / 忽略断点全部重跑（**会重复扣费**） |

### `images` —— 按页出配图

| 参数 | 说明 |
|---|---|
| `--every` | 每 N 页配一张图（`1`=每页一图，`2`=数页一图），默认 `1` |
| `--resolution` | `1K`(默认) / `2K` / `4K`。**只有 1K 有实测价**，2K/4K 拒绝估算（`exit=3`） |
| `--ratio` | 出图比例，默认按分页方案（`16:9`） |
| `--snap` | 出图后按请求比例**居中裁准**（上游按 32 对齐，5/10 种比例不精确） |
| `--ratio-tolerance` | 比例容差，默认 `0.03`（实测最大偏差 2.9%） |
| `--points-per-image` | 覆盖单张单价（点） |
| `--poll-timeout` | 单张出图轮询上限（秒），默认 `600` |
| `--yes` / `--dry-run` | 确认花钱 / 只报价 |
| `--only` / `--count` | 只出这些页的图 / 最多出几张 |
| `--allow-prompt-hits` | 放行**出图提示词**的闸门命中（页面内容闸门**永远不放行**） |

### `render` —— 本地排版

| 参数 | 说明 |
|---|---|
| `--theme` | `ink`(默认) / `night` / `warm` |
| `--font` | 中文字体文件路径（默认从系统字体里找） |
| `--no-html` | 不导出 `deck.html` |
| `--strict-notes` | 缺讲稿备注也算闸门失败 |
| `--ratio-tolerance` / `--force` | 配图比例容差 / 忽略断点全部重渲 |

### `cost` —— 只算钱

`--pages` / `--every` / `--images`（直接指定张数）/ `--no-images` / `--no-text` /
`--no-outline` / `--no-pages` / `--resolution` / `--points-per-image` / `--budget`。

### `models` —— 列出在架模型

`--type text|image|all`（默认 `all`）。

## 八道硬闸门

命中即**标红 + stderr 汇总 + 退出码非 0**，可以直接进 CI。

| # | 闸门 | 拦什么 |
|---|---|---|
| 1 | 合规 | 广告法违禁词 + **教育类效果承诺**（保过 / 包学会 / 保证提分，**无豁免**） |
| 2 | 占位符残留 | `{}` / `[待填]` / `XXX` / `（此处省略）` / `TODO` |
| 3 | `prompt_echo` | 照抄提示词示例（去标点相等 / Jaccard ≥ 0.75 / **覆盖度 ≥ 0.60**） |
| 4 | 出图比例真伪 | 读**文件头真实像素**，容差 3%，`--snap` 裁准 |
| 5 | 每页内容完整性 | 空页 / 零页 / 缺标题 / 单条要点超长 |
| 6 | 文字溢出 | **真实字体排版后**量像素；超了报出实际像素与可用像素 |
| 7 | 成本上限 | 超 `--budget` 停；2K/4K **拒绝估算** |
| 8 | 产出不许进包 | `--outdir` 在包内 → `exit=2` |

**闸门在花钱之前就判**：页面缺要点、单条要点超长、标题断行过多、比例不对，
一律在报价阶段拦下——免得钱花了才发现这一页根本不能用。

**页面内容闸门永远不放行**（没有 `--allow-*` 开关）；只有"出图提示词"这一层
仿同族留了 `--allow-prompt-hits`。

### 真机上抓到的三条（不是想出来的）

1. **教育类效果承诺单列一档。** 知识付费最常见的违规不是"最"字，是效果承诺。
   `保过 / 包过 / 包学会 / 保证提分 / 保就业 / 包分配` 全部高风险拦截。
2. **裸的「特效」把 VFX 打成医疗宣称，已收紧。** 实测被拦下的原文是
   「很多人以为剪辑是学**特效**、学转场」与「一上手就拖转场**特效**」——
   在影视 / 剪辑语境里 `特效` 就是 VFX。口径与同族修 `唯一` 完全一样：
   **把裸词收紧成可枚举的搭配**，改成 `特效(药|疗法|配方|偏方|治疗|作用|成分|功效)`。
3. **普通中文里的「最」做了可枚举豁免，但句首不豁免。**
   「做菜和剪辑**最大**的共同点是……」放行；`最好的课程` / `最强` 照拦；
   而「最大的区别是……」这种**句首**写法**不豁免**——课件页标题几乎全在句首，
   这条对本包比对同族更关键。

**已知的保守行为**：`加微信 / 私信我 / vx` 这类站外导流词照拦，
哪怕课件主题就是教「私域运营怎么引导加微信」。**靠改文案解决，不要改闸门。**

## 排错

| 现象 / 报错 | 原因 | 怎么办 |
|---|---|---|
| `没有 PIL：本地排版成逐页 PNG 需要 PIL`（`exit=2`） | 没装 pillow | `pip install pillow` 后**原样重跑**（不重复扣钱） |
| `系统里找不到可用的中文字体`（`exit=2`） | 系统没中文字体 | `--font <字体文件路径>` |
| `输出目录 … 在 Skill 包内`（`exit=2`） | `--outdir` 指到包内 | 换到包外，如 `D:/slides/x`、`%TEMP%\slides` |
| `讲义原文 … 超过上限`（`exit=2`） | 讲义 > 24000 字 | 拆成两半（**故意不截断**） |
| `page_count` / `no_image_intent`（`exit=3`） | 页数对不上 / 某页缺配图意图 | 改 `--pages` 重跑，或手工补 `deck.json` |
| `empty_page`（`exit=3`） | 某页一条要点都没有 | 脚本**不会**拿粗要点兜底（那会掩盖失败），补内容后重跑 |
| `bullet_too_long` / `title_too_long`（`exit=3`） | 要点 > 48 字 / 标题 > 30 字 | 拆条或压缩（**不截断**） |
| `text_overflow`（`exit=3`） | 标题 + 要点超过版心 | 报里给了**实际像素与可用像素**，减内容，别改闸门 |
| `ratio_fake`（`exit=3`） | 真实像素与请求比例差 > 3% | `images --snap` 重跑该页 |
| 命中违禁词 / 占位符 / 照抄示例（`exit=3`） | 文本违规或模型照抄示例 | 命中项逐条打在 stderr；改文案重跑，或 `--from-file` 零成本复核 |
| `2K 档没有实测单价，拒绝凭猜估算`（`exit=3`） | 2K/4K 没实测价 | 先用 1K，或 `--points-per-image` 自填单价 |
| `预估 … 超过预算上限`（`exit=3`） | 超 `--budget` | 提预算、减页数，或先 `cost` 试算 |
| 重跑又扣了一次钱 | 断点 key 的某一维变了（文案 / resolution / 模型） | 设计如此。**只改版式不会重出图** |
| 换了主题再换回来，却报"跳过"，磁盘上却是另一个主题的图 | 两个主题写同一文件名，旧断点记录仍命中 | **已修**：命中后再核**产物身份**（字节数 + mtime），对不上就重做并打印原因 |
| 改了画法但图没变 | 没 bump `LAYOUT_VERSION` | 把它 +1（源码里有醒目注释） |
| 上游 `502` / `upstream timeout` | 网关到上游瞬时抖动，**实测常见** | 已内置退避重试（最多 4 次）；连续失败换模型或 `--count` 分批 |
| `任务未完成（timeout）`（`exit=4`） | 出图卡在 processing | `task_id` 已进断点，**重跑续查而不是重新提交（不重复扣费）**；或调大 `--poll-timeout` |
| Windows 中文乱码 | 控制台代码页不是 UTF-8 | 脚本已切 UTF-8；仍是先 `chcp 65001` 或设 `PYTHONIOENCODING=utf-8` |
| 想复核产出但不想再花钱 | —— | `outline --from-file` / `pages --from-file` 只跑闸门、不调模型 |

**收集排错信息时请附上**：完整命令、`--dry-run` 输出、`AUDIT.md` 内容、原始报错文本。
**不要在报错信息或截图里带上你的 API Key。**

### 退出码

| 码 | 含义 |
|---|---|
| `0` | 全部干净，闸门全绿 |
| `2` | 用法错误（参数 / 文件 / 没 PIL / 没字体 / **`--outdir` 在包内**） |
| `3` | **被闸门拦下**（违禁词 / 占位符 / 照抄 / 比例不符 / 空页 / 溢出 / 超预算 / 拒绝估算 / 零页） |
| `4` | 调用失败（网络 / 鉴权 / 点数 / 模型名 / 任务未完成） |
| `130` | 用户中断（Ctrl+C） |
| `1` | 未预料异常：`--json` 下给 `internal` 信封 + **完整 traceback 到 stderr** |

`2 / 3 / 4` 分开是有意的：`2` = 你命令用错了；`3` = 上游没问题、被本地规则拦了；
`4` = 上游 / 网络有问题。CI 里三种要采取完全不同的动作。

### `--json` 契约

- 成功：结果对象里多一个 `"ok": true`
- 失败有**两种合法形态**，消费方都要处理：
  1. **信封** `{"ok": false, "exit": 3, "error": {"kind": …}}` —— 本次还没吐过结果时用
  2. **结果** `{"ok": false, "stage": "gate", "blocked": [...]}` —— 已经跑完、
     只是闸门判定不合格时用；此时**绝不再补信封**（否则 stdout 上会有两个 JSON 文档）
- `kind` 取 `usage` / `gate` / `budget` / `call` / `interrupt` / `internal`
- stdout **永远只有一个 JSON**；人读文案全部走 stderr；退出码语义不变
- `--json` 写在子命令**前面或后面都可以**

## 实测记录

| 动作 | 结果 | 耗时 |
|---|---|---|
| `schema nano_banana`（现查） | 7 个入参，见 `references/cost-and-troubleshooting.md` | <1s |
| `outline` 讲义 → 7 页 | `usage` = prompt 1186 / completion 780 / **total 1966** | 5.8s |
| `pages` 7 页（3 批） | 闸门全绿 | 11.9s |
| `pages` 原样重跑 | **0 次调用、0 元** | 0.1s |
| `images` `--every 3` → 3 张 | **`points_cost` 24.0 点/张，合计 72.00 点 = 0.72 元** | 每张 5~20s |
| 出图真实像素 | **1344x768**（请求 16:9，实际 1.7500，**偏差 1.56%**，容差 3%） | — |
| `render` 7 页 | 逐页 PNG **1920x1080**，共 **3.8 MB** | **0.7s** |
| `render` 只改 3 页页型 | **精确重渲 3/7 页**（其余跳过） | 0.2s |
| 闸门自检 | **32 个用例全过**（每道闸门各喂坏数据 + 用法错误） | <60s |
| `--json` 契约 | 成功 / 失败 × 前后两位置 + `internal`，**全部 `json.loads` 通过** | <20s |

出图实测 1K = **24 点/张**（1 元 = 100 点）。**2K / 4K 没实测过，脚本拒绝估算**。
文本金额一律是**估算口径**，**账单以 api.a7w.cn 控制台为准**。

## 端点速查

全部能力都走 api.a7w.cn（下面几行的域名都来自**算力集市 api.a7w.cn**）：

| 用途 | 方法与路径 |
|---|---|
| 分页方案 / 每页内容（文本） | `POST https://api.a7w.cn/api/v1/chat/completions` |
| 在架模型清单 | `GET  https://api.a7w.cn/api/v1/models` |
| 在架生成应用 | `GET  https://api.a7w.cn/api/v1/apps` |
| 出配图（异步提交） | `POST https://api.a7w.cn/api/v1/apps/nano_banana/submit` |
| 出图任务轮询 | `GET  https://api.a7w.cn/api/v1/tasks/<task_id>` |

协议是 **OpenAI 兼容**：`Authorization: Bearer <Key>`，请求体用
`model` / `messages` / `temperature` / `max_tokens` / `response_format`。

四条实测记下来的口径：

1. **走 `/chat/completions` 的成功响应不带 `code` 字段**，直接读
   `choices[0].message.content`；`{"code":1,"data":{...}}` 那层信封是给生成应用的。
   **不要**改成用 `code == 0` 判成功。
2. **`deepseek-chat` 不在 `/api/v1/models` 的返回列表里，但实测可用**（路由到
   `deepseek-flash`）。所以"列表里没有"不等于"不能用"。
3. **异步任务的 `status` 在 `data` 顶层**，不在 `data.result` 里（平台文档写错了）。
   照文档写会永远读不到状态、一路轮询到超时。实测原文：
   `data.status = 'completed'`、`data.result.status = None`。
4. **请求体字段必须现查**：`python3 scripts/a7w.py schema nano_banana`。
   本包用到的 7 个字段全部来自现查结果，不凭记忆 ——
   `model` / `action` / `prompt` / `image_urls` / `resolution` / `aspect_ratio` / `callback_url`。

## 文档

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 完整说明：能力、命令、参数、八道闸门、排错、已知取舍 |
| `references/slide-design-method.md` | 课件设计方法论：怎么分页、要点怎么写、备注写什么 |
| `references/layout-specs.md` | 版式与规格：画布 / 版心 / 字号 / 上限的自洽性推导 |
| `references/cost-and-troubleshooting.md` | 实测单价、报价口径与排错手册 |

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
