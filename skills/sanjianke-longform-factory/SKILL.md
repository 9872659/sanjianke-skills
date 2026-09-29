---
name: sanjianke-longform-factory
slug: sanjianke-longform-factory
displayName: 三剪客 · 长文自动生产线
description: "给一个主题，一条链路产出**可发布的长文**：选题角度 → 大纲 → 正文（3000 字级）→ 配图（自动决定画什么、几张）→ 平台适配（公众号 / 头条 / 知乎）。不是单点生成，是**多步流水线**：`outline` 出角度与大纲，`write` 写正文，`images` 先报价再出图，`adapt` 改平台版，`all` 串全链路并**断点续跑**。走 api.a7w.cn 的 OpenAI 兼容端点，零依赖。八道本地闸门都是**拦截**：违禁词、占位符、照抄示例、字数区间、结构、比例真伪、成本、包内 outdir。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.4
summary: "单点生成一段文字容易，难的是「一条链路跑完还能直接发」。本包把长文生产拆成可单独交付的步骤，每步都做**本地闸门**。链路：`outline` 给 4 个不重叠的选题角度并展开成带计划字数的分节大纲；`write` 写 2500~4500 字正文（标题 + 摘要 + 正文 + 结尾引导）；`images` 读正文决定画什么、几张、什么比例，先报价再出图；`adapt` 改写成公众号 / 头条 / 知乎版；`all` 串全链路并**断点续跑**。接入走 api.a7w.cn 的 OpenAI 兼容端点；出图走 `POST /api/v1/apps/nano_banana/submit` 加 `GET /api/v1/tasks/<task_id>` 轮询。实测口径：文本成功响应**不带 `code`**；出图 `status` 在 **`data` 顶层**（文档写错）；上游按 32 对齐，只认**真实像素**、容差 3%。成本：出图实测 1K = 24 点/张；文本**只出 token**，金额要你自己传 `--yuan-per-ktok`。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 长文
  - 新媒体
  - api.a7w.cn
---

# 三剪客 · 长文自动生产线

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几次）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

## 能做什么

给一个**主题**，**一条链路跑完一篇可发布的长文**：选题角度 → 大纲 → 正文 → 配图 → 平台适配。

它替代的不是"写不出来"，而是**"写之前先想清楚"和"写完之后还要改三遍"**这两段：
想不清角度，写出来的就是一篇正确但没人转发的文章；
不做平台适配，同一篇稿子发到头条和知乎就是两个效果。

七个**独立子命令**，每一步的产出都能单独拿去用：

| 子命令 | 做什么 | 产出 |
|---|---|---|
| `outline` | 出选题角度 + 大纲 | 4 个互不重叠的角度（受众 / 钩子 / 凭什么）+ 选定角度 + 分节大纲（每节计划字数与要点） |
| `write` | 按大纲写正文 | 标题 + 摘要 + 2500~4500 字正文 + 结尾引导 |
| `images` | 按正文出配图方案 + 出图 | 自动决定**画什么、几张、什么比例**，先报价再出图 |
| `adapt` | 长文改写成平台版 | 公众号 / 头条 / 知乎版（各自字数区间与结构要求不同） |
| `all` | 串起全链路 | `outline.md` + `article.md` + `images/` + `adapt-*.json` + 合并稿 + 质检报告 |
| `cost` | 只算钱 | 预估 token 与点数，一次调用都不发 |
| `models` | 现查在架模型 | 模型清单（免费） |

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 出图有**实测价**（1K = 24 点/张）；文本**只出 token**，金额要你自己传 `--yuan-per-ktok` |
| 要多久 | 实测：大纲 ~8s、正文 ~12~17s、一张图 ~40s、一个平台版 ~10s |
| 要装什么 | **什么都不用装**。只用 Python 标准库 |
| 中断了怎么办 | **断点续跑**：已完成的步骤直接跳过，重跑不重复扣费；**但出图断点按「分辨率 + 提示词内容」判定——提示词改一个字、或 `--resolution` 换一档就重出重扣**（是不是真花这笔钱由你决定，成本警告见排错表末） |
| 会瞎编数据吗 | 提示词写死了"不编数据、不编人名机构、不做效果承诺"，并用合规闸门兜底 |
| 配图比例准不准 | **只认文件头里的真实像素**，不信接口自报；容差 3%，容差内也打印偏差 |

### 一篇长文的四件套

`write` 产出的每一篇都必须齐这四件，缺一项会被闸门标红：

1. **标题** —— 要具体，不许是「关于 XX 的思考」这类泛题
2. **摘要** —— 一句话说清"读完能拿走什么"（30~70 字）
3. **正文** —— Markdown，3~6 个小标题分节，含至少一处具体例子与一处常见误区
4. **结尾引导** —— 最后两段里要有具体的关注 / 在看 / 收藏 / 评论动作

第 4 项是"能发的文章"与"写完的草稿"的分水岭。没有结尾引导，读者读完就走。

## 怎么用（命令行）

### 第 0 步：获取 API Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`）。

### 第 1 步：装依赖

**零依赖。** 不需要 `pip install` 任何东西，只要机器上有 Python 3.7+：

```bash
python3 --version
```

包里自带的 `scripts/a7w.py` 是零依赖客户端（只用 `urllib` / `json` / `mimetypes`），
`scripts/run.py` 与 `scripts/imgprobe.py` 也只用标准库。

> **约定**：`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端，我们靠
> 「包内副本 SHA256 == 规范版」批量校验各包的客户端有没有被意外改坏。
> 所以本包**没有**为了自己的业务去改它——长文生产线需要的东西全写在 `run.py` 里，
> 读图片像素的能力放在独立的 `imgprobe.py` 里。

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
python3 scripts/run.py models --type text
```

这个命令打的是 `GET https://api.a7w.cn/api/v1/models`，会列出当前在架的模型。

> **模型名会变，一定用 `models` 子命令现查，别写死在脚本里。**
> 但要注意：`deepseek-chat` 这个别名**实测可用**（会路由到 `deepseek-flash`），
> 而它**不在** `/api/v1/models` 的返回列表里 —— 所以"列表里没有"不等于"不能用"。

### 第 4 步：先算钱（不出网，不花钱）

```bash
python3 scripts/run.py cost --platform wechat --sections 5
```

输出会告诉你：几次调用、预估 token、预估出图点数，以及**这个金额是怎么估出来的**。

### 第 5 步：出选题角度与大纲

```bash
python3 scripts/run.py outline --topic "短视频二创批量出片的产能瓶颈" \
    --platform wechat --angles 4 --sections 5 --json --out outline.json
```

先看不花钱的提示词：

```bash
python3 scripts/run.py outline --topic "短视频二创批量出片的产能瓶颈" --dry-run
```

### 第 6 步：写正文

```bash
python3 scripts/run.py write --outline outline.json --json --out article.json
```

### 第 7 步：配图（真花钱，先报价）

```bash
# 不加 --yes 时：只出方案 + 报价，**不提交任何任务**
python3 scripts/run.py images --article article.json --platform wechat --count 2

# 确认后加 --yes 才真的出图
python3 scripts/run.py images --article article.json --platform wechat --count 2 \
    --budget 50 --yes --outdir "%TEMP%\longform-images"
```

### 第 8 步：平台适配

```bash
python3 scripts/run.py adapt --article article.json --platform toutiao
python3 scripts/run.py adapt --article article.json --all-platforms
```

### 第 9 步（推荐）：一条命令跑完整条链路

```bash
python3 scripts/run.py all --topic "短视频二创批量出片的产能瓶颈" \
    --platform wechat --adapt-all --images 2 --budget 50 --yes \
    --outdir "%TEMP%\longform-out"
```

产出目录长这样：

```
%TEMP%\longform-out/
├── outline.md / outline.json      选题角度 + 分节大纲
├── article.md / article.json      正文（四件套）
├── images-plan.json               配图方案（画什么、几张、为什么）
├── images/                        真图（**在包外**）+ 出图断点
│   ├── 1-cover-16x9-….png
│   └── images-summary.json        每张的真实像素 vs 请求比例
├── adapt-wechat.json              平台版（--adapt-all 时才有）
├── adapt-toutiao.json
├── adapt-zhihu.json
├── longform.md                    合并稿，可直接发
├── AUDIT.md / audit.json          质量与合规自检报告
└── longform-state.json            断点文件
```

**输出目录一定要指到包外**（`%TEMP%\...`）。Skill 包的上传白名单只收
`.md .py .txt .json .sh .js .yaml .yml .csv`，包内塞图片会让上传 400 ——
所以脚本把「`--outdir` 落在包内」做成**硬闸门（退出码 2）**，在花钱之前就拦下。

中断了就**原样重跑**，内容没变的部分不会重复扣费（**出图的断点里含提示词内容，改提示词会重出重扣**，见排错表末的成本警告）：

```bash
python3 scripts/run.py all --topic "短视频二创批量出片的产能瓶颈" --outdir "%TEMP%\longform-out"
# [1/4] 大纲已完成，跳过（断点续跑，不再重复扣费）
# [2/4] 正文已完成，跳过（2541 字，已复检 ok）
# [3/4] … 已完成的图跳过
# 已用 0 次文本调用 · token prompt=0 completion=0 total=0
```

> **断点命中要同时满足两个条件**：状态标记 `ok`，且**产出文件里的内容本身也合格**。
> 只信状态的话，手工改坏 `article.json` 之后重跑会被当成"已完成"直接跳过，
> 闸门就变成假绿了。

### 直接用 curl 调（不依赖本包脚本）

底层就是一个标准的 OpenAI 兼容调用（域名来自**算力集市 api.a7w.cn**）：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "给「短视频二创产能瓶颈」出 4 个选题角度，只输出 JSON"}],
    "temperature": 0.7,
    "max_tokens": 4096,
    "response_format": {"type": "json_object"}
  }'
```

> 算力网关里**成功响应不带 `code` 字段**——直接看 `choices[0].message.content`。
> 带 `code == 1` 的那层信封（`{"code":1,"data":{...}}`）是给生成应用的，
> 本包两种形态都认，但**不要**改成用 `code == 0` 判成功。

出图是异步的，两步走：

```bash
# 1) 提交，拿到 task_id
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/nano_banana/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" -H "Content-Type: application/json" \
  -d '{"prompt":"极简信息图风，圆形节点与色块表示流程，无任何文字","action":"generate",
       "model":"nano-banana","resolution":"1K","aspect_ratio":"16:9"}'

# 2) 轮询任务（⚠️ status 在 data 顶层，不在 data.result 里）
curl -sS "https://api.a7w.cn/api/v1/tasks/<task_id>" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

## 参数说明

### 全局

| 参数 | 说明 |
|---|---|
| `--key` | 临时指定 Key；优先级最高。**别把它写进脚本或文档** |
| `--model` | 模型名，默认 `deepseek-chat`（实测可用）。用 `models` 现查在架模型 |
| `--temperature` | 采样温度，默认 `0.7` |
| `--max-tokens` | 最大输出 token，默认 `8192`；正文一次几千字，别调太低 |
| `--budget` | 成本上限。出图按**点**、文本按 `--yuan-per-ktok` 折算成元；超了就地停，退出码 3 |
| `--yuan-per-ktok` | 文本单价（元/千 token）。**默认不折算金额**（网关不公布文本单价）；填了才出金额，且只是估算 |
| `--json` | 以 JSON 输出，**写在子命令前面或后面都可以**；JSON 模式下 stdout 只有一个完整 JSON，进度走 stderr |
| `--out <文件>` | 把结果写到文件（**是文件，不是目录**） |
| `--dry-run` | 只打印将发送的提示词，**不调模型、不花钱** |
| `--no-json-mode` | 不要求上游返回 JSON 对象（个别模型不支持 `response_format` 时用） |

### `outline` —— 选题角度 + 大纲

| 参数 | 说明 |
|---|---|
| `--topic` | **必填**。文章主题 |
| `--platform` | `wechat`(公众号，默认) / `toutiao`(头条) / `zhihu`(知乎)，决定字数区间与结构口径 |
| `--angles` | 要几个选题角度，默认 `4`。脚本按实际解析出的个数核对，对不上标红 |
| `--sections` | 正文分几节，默认 `5` |
| `--audience` | 受众补充说明（写给谁、什么场景） |
| `--requirements` | 必须覆盖的硬性要求，会原样给到模型 |
| `--tone` | 语气/调性，例如「克制、少形容词」 |

### `write` —— 写正文

| 参数 | 说明 |
|---|---|
| `--outline` | **必填**。`outline --json --out` 产出的文件 |
| `--platform` | 目标平台；给了 `--outline` 时**以大纲里的 platform 为准** |
| `--from-file` | **闸门复检用**：不调模型，直接拿一份返回 JSON 过闸门（见「排错」最后一节） |
| `--trust-chars` | **闸门自检用**：采信产出侧声明的 `chars` 而不是本地数字数 |

### `images` —— 配图方案 + 出图

| 参数 | 说明 |
|---|---|
| `--article` | `write --json --out` 产出的文件 |
| `--platform` | 目标平台，默认 `wechat`（决定配图比例：公众号/头条 16:9、知乎 4:3） |
| `--count` | 最多出几张（**真闸门**，少花钱）。不传就是方案里的实际张数 |
| `--ratio` | 出图比例，默认按平台。可选 `1:1 / 16:9 / 9:16 / 4:3 / 3:4 / 3:2 / 2:3 / 5:4 / 4:5 / 21:9` |
| `--resolution` | `1K`(默认) / `2K` / `4K`。**只有 1K 有实测价 24 点/张**。**这一维进了出图断点 key**：换了档位重跑会重出（否则你要 4K 却拿到 1K 的图） |
| `--points-per-image` | 单张点数（覆盖实测价）。2K/4K 必须传它才给估算 |
| `--budget` | 出图成本上限（**点**）。超了不提交任何任务，退出码 3 |
| `--yes` | 确认真的花钱。**不加就只报价**（退出码 4，不提交任务） |
| `--outdir` | 出图输出目录，默认 `%TEMP%\longform-images`。**必须在包外**（包内 exit=2） |
| `--snap` | 出图后按请求比例精确裁剪（本地裁，裁完读文件头复核） |
| `--ratio-tolerance` | 比例容差，默认 `0.03`（3%）；地板 `0.0025` |
| `--poll-timeout` / `--poll-interval` | 单张轮询上限（默认 600s）与间隔（默认 5s） |
| `--allow-prompt-hits` | 允许带违禁词/占位符的出图提示词（默认拦截） |
| `--allow-article-hits` | 正文命中闸门也继续配图（默认拦截） |
| `--local-image` | **比例闸门自检用**：拿本地图跑「真实像素 vs 请求比例」判定，不出网不花钱 |
| `--force` | 忽略出图断点重出（**会重复扣费**） |

### `adapt` —— 平台适配

| 参数 | 说明 |
|---|---|
| `--article` | **必填**。`write --json --out` 产出的文件 |
| `--platform` | 目标平台，默认 `wechat` |
| `--all-platforms` | 三个平台版都出 |
| `--chars-min` / `--chars-max` | 覆盖字数区间（默认按平台口径） |
| `--from-file` | 同 `write` |

### `all` —— 串起全链路（断点续跑）

| 参数 | 说明 |
|---|---|
| `--topic` | **必填**。文章主题 |
| `--outdir` | 输出目录，默认 `%TEMP%\longform-out`；**必须在包外** |
| `--img-outdir` | 配图目录，默认 `<outdir>/images`；**必须在包外** |
| `--platform` / `--angles` / `--sections` / `--audience` / `--requirements` / `--tone` | 同 `outline` |
| `--images` | 出几张图；传 `0` 表示完全跳过配图（不出网、不花钱） |
| `--adapt-all` | 末端把三个平台版都出一遍 |
| `--yes` | 确认配图花钱（`--images 0` 时不需要） |
| `--force` | 忽略断点全部重跑（**会重复扣费**，只在确实要重做时用） |

### `cost` —— 只算钱

| 参数 | 说明 |
|---|---|
| `--platform` | 目标平台，默认 `wechat` |
| `--sections` | 分节数，默认 `5` |
| `--images` | 配图张数，默认取平台建议中值；`0` 表示不算配图 |
| `--all-platforms` / `--adapt-off` | 算不算平台适配的钱 |
| `--points-per-image` | 单张出图点数（覆盖实测价 24 点/张） |
| `--budget` | 出图预算上限（**点**），超了退出码 3 |

### 各平台口径（`--platform` 到底改了什么）

| 平台 | 正文字数区间 | 建议配图 | 出图比例 | 结构口径 |
|---|---|---|---|---|
| `wechat` 公众号 | 2500~4500 | 2~5 张 | 16:9 | 开头钩子 + 3~6 个小标题分节 + 结尾引导 |
| `toutiao` 头条 | 1800~3500 | 3~6 张 | 16:9 | 结论前置 + 分点展开 + 结尾引导 |
| `zhihu` 知乎 | 2500~6000 | 1~4 张 | 4:3 | 先给判断 + 依据与边界 + 结尾引导 |

字数口径是**去掉 Markdown 符号与空白后的字符数**，中英文都按字符算。
不按"汉字数"算，是因为长文里中英混排、数字、代码都很常见，
只数汉字会把 400 字的英文段落当 0 字，判定会比实际宽松得多。

## 八道本地硬闸门

闸门都是**拦截 + 标红 + stderr 汇总 + 退出码非 0**，不是"提示一下"。
文章是要挂在你账号下面被人读的，缺陷出了这道门的代价是你的号。

| # | 闸门 | 拦什么 | 判据 |
|---|---|---|---|
| 1 | 合规 | 广告法违禁词 + 站外导流 / 标题党 | 本地正则表（`BANNED_PATTERNS`），模型自评不采信 |
| 2 | 占位符残留 | `{}` / `[待填]` / `XXX` / `（此处省略）` | 六条正则，括号那条只认枚举占位词 |
| 3 | `prompt_echo` | 照抄提示词示例 | 去标点后相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60 |
| 4 | 字数区间 | 不在平台区间 | 产出侧数字数，超出的**不替你截断** |
| 5 | 结构完整性 | 缺标题 / 缺正文 / 没分节 / 缺结尾引导 | 逐项校验，缺项标红 |
| 6 | 出图比例真伪 | 接口自报与真实像素不符 | 读**文件头**的宽高，容差 3%，容差内也打印偏差 |
| 7 | 成本上限 | 超 `--budget` | 出图前先报价，提交任何任务之前判 |
| 8 | `--outdir` 落包内 | 产出图进包 | 包路径判定，退出码 2（用法错） |

### 闸门一的「最」字豁免（可枚举、可复核）

「最 X」在正常中文里到处都是，一刀切会把好文章全拦下。所以加了一层上下文豁免：
「最 X」后面紧跟（允许夹一个「的」）

`不同 / 区别 / 差异 / 共同 / 相同 / 相似 / 常见 / 容易 / 重要 / 关键 / 主要 / 先 / 后 /
基本 / 简单 / 难 / 麻烦 / 省事 / 常用 / 合适 / 适合 / 保险 / 稳妥`

→ 判为普通用法，放行。`最好的工具` / `最强` / `最高级` / `最大优惠` 仍然照拦。

**⚠️ 句首不许误豁免。** 命中处前面只有空白、或前一个非空白字符是句末标点时，
视为句首 → **不豁免**。因为「最大区别是……」这种句首写法经常正是标题式的最高级宣称。

### 闸门为什么必须自己在产出侧数字数

`write` / `adapt` 都是大模型一次吐几千字。**只要采信产出侧自报的字数，闸门就会变假绿**：
一份声明 `chars: 4000`、实际只有几十字的产出会顺利过关。
所以字数字段一律由脚本自己数（`count_chars`），产出侧的 `chars` 只用于对照。
`--trust-chars` 这个开关存在的唯一目的，就是**故意采信自报值**来演示这道闸门真的会拦。

### 闸门六为什么必须读文件头

教训来自同族包的实测：只信模型自报字段的闸门变成假绿。出图场景的形态是
「接口说 `aspect_ratio=16:9`，真实像素却是别的」。
所以这里**只认文件头里的宽高**（`imgprobe.image_size`），不采信任何返回字段。

顺带记一条**上游特性**（必须写进文档，否则闸门天天误报）：上游不是按比例给像素，
而是先定总像素、再把每边向下取整到 32 的倍数，所以 10 种比例里有 5 种给不出像素级精确比例：

| 请求 | 实测像素 | 实得比例 | 偏差 |
|---|---|---|---|
| `1:1` | 1024x1024 | 1.0000 | 0.00% |
| `4:3` | 1184x864 | 1.3704 | 0.00% |
| `3:2` | 1248x832 | 1.5000 | 0.00% |
| `2:3` | 832x1248 | 0.6667 | 0.00% |
| `21:9` | 1536x672 | 2.2857 | 0.00% |
| `16:9` | 1344x768 | 1.7500 | **1.56%** |
| `9:16` | 768x1344 | 0.5714 | **1.56%** |
| `3:4` | 864x1184 | 0.7297 | **2.70%** |
| `4:5` | 896x1152 | 0.7778 | **2.78%** |
| `5:4` | 1152x896 | 1.2857 | **2.86%** |

这**不是**网关 bug，是扩散模型按 32 对齐的常规做法。处理方式三条一起用：
① 默认容差 3%（容差内不算假，但**明确打印真实像素与偏差**，不藏）；
② 超容差 → 标红 + 计入闸门失败 + 退出码 3；
③ `--snap` 按请求比例本地裁准，裁完再读文件头复核，裁成功才记 exact。

## 实测记录

以下都是本包上线前真跑出来的数（模型 `deepseek-chat`，主题"短视频二创批量出片的产能瓶颈"）：

| 动作 | token（prompt / completion） | 耗时 | 结果 |
|---|---|---|---|
| `outline` 4 角度 / 5 节 | 755 / 1272（total 2027） | 8.9s | 结构校验 11 项全过，计划 3500 字 |
| `outline` 重跑 | 755 / 866（total 1621） | 7.3s | 同上（prompt 命中 512 缓存 token） |
| `write` 一篇 | 1293 / 2611（total 3904） | 17.1s | 3223 字 |
| `write` 一篇 | 1293 / 1966（total 3259） | 11.5s | **2400 字 → 被闸门四拦下**（低于 2500） |
| `adapt` → 头条 | 2802 / 2147（total 4949） | 9.3s | 2632 字，落 1800~3500 区间 |
| `images` 2 张（16:9 / 1K） | 方案 2935 / 513 | 提交后约 40s/张 | **真实像素 1344x768，偏差 1.56%（容差内）**，扣费 **24 点/张** |
| `all` 全链路（2 图 + 3 平台版） | 11309 / 10291（total 21600） | —— | 产出全部落盘，闸门汇总见 `AUDIT.md` |

**关于字数的实测提醒**：只写"落在区间内"时，模型会习惯性贴下限，甚至写下限少 10%。
本包在 `write` 提示词里明确写了"瞄准区间中上段、宁可比下限多两百字"，
但实测仍偶有偏短 —— 这时**闸门会拦下并如实报出字数**，不会替你硬凑。
偏短就重跑一次（成本约 4000 token），或手工补两句。

## 排错

| 现象 / 报错 | 原因 | 怎么办 |
|---|---|---|
| `Missing or invalid relay API key`（HTTP 401） | Key 无效、已过期或写错 | 重新到 https://api.a7w.cn/ 领取；确认没把 `Bearer` 重复写进环境变量 |
| 点数不足（HTTP 402） | 账号点数用完 | 到 https://api.a7w.cn/ 充值后重试 |
| 模型不存在（HTTP 404） | 模型名写错或已下架 | `python3 scripts/run.py models --type text` 现查在架模型名 |
| 上游 `502` / `upstream timeout` | 网关到上游的瞬时抖动，**实测很常见** | 脚本已内置退避重试（最多 4 次）。连续失败就换模型，或分批跑 |
| 模型返回的不是合法 JSON | 模型在 JSON 前后多吐了字符或解释 | 脚本已用 `json.JSONDecoder().raw_decode()` 扫描第一个完整对象。仍失败就加 `--no-json-mode` 并换模型 |
| 正文命中违禁词 / 字数越界（退出码 3） | 模型写了「最好」这类词，或字数不在区间 | 命中项会在 stderr 与 JSON 里逐条列出。是误伤就改对应那句重跑；字数不够就让模型重写，脚本**不会**替你截断 |
| `有结尾引导` 被判不合格 | 正文最后几段与 `ending` 字段里都没有引导词 | 让模型重写结尾，或在 `--from-file` 复检前手工补一句 |
| 出图比例不合格（退出码 3） | 真实像素与请求比例偏差超容差 | 看 stderr 打印的真实像素与偏差。加 `--snap` 本地裁准，或调 `--ratio-tolerance` |
| `预估 N 点超过 --budget` | 超了出图成本上限 | 提预算、减 `--count`，或先 `cost` 试算 |
| `这是一次真花钱的操作，确认后加 --yes 重跑`（退出码 4） | 出图没给 `--yes` | 先看报价，确认后加 `--yes`；只想看正文用 `--images 0` |
| `输出目录 … 在 Skill 包内`（退出码 2） | `--outdir` 指到了包内 | 换到包外，例如 `%TEMP%\longform-out` |
| 重跑又扣了一次钱 | 那次要出的图，提示词变了（**正文的断点 key 与提示词无关**，改正文本身不会因此重出图） | 出图断点按提示词内容判定，内容变了就该重做——这是设计如此。想省钱就别改，直接重跑即可跳过 |
| 升级到 1.0.3 后第一次重跑，图好像全重出了 | 旧断点文件的 key 与新算法对不上（这正是修掉静默复用旧图的那一步） | 已实测：**升级后第一次重跑会重新出图**，先 `cost` 看预估、必要时才加 `--yes`；之后就正常续跑了 |
| 提示词改了、却像是复用了旧图 | 1.0.2 及更早的版本判定断点时，没有把提示词的后半段算进去 —— 只改后半段就会被当成同一张图 | 已修：本版按**完整提示词**判定，改一个字就重出、不再静默复用 |
| 改了 `--resolution`（1K→4K）、图却还是 1K 的 | 1.0.3 及更早的断点 key 里没有分辨率这一维，key 不变 → 命中旧图 | 已修：本版把 `resolution` 也进 key，且记录里的档位与本次不一致时强制重出。命中 1.0.3 旧断点会重跑一次，之后正常 |
| 升级到 1.0.4 后第一次重跑，图好像全重出了 | 旧断点文件的 key 与新算法（多了分辨率这一维）对不上 | 这是修掉「要 4K 拿到 1K」的代价：先 `cost` 看预估、必要时才加 `--yes`；之后就正常续跑了 |
| Windows 下中文乱码 | 控制台代码页不是 UTF-8 | 脚本已把 stdout/stderr 切成 UTF-8；仍有问题先 `chcp 65001` 或设 `PYTHONIOENCODING=utf-8` |
| 想复核一份已有产出，但不想再花钱 | —— | 用 `--from-file`：`write --outline outline.json --from-file 某份返回.json` 只跑闸门、不调模型 |

**出图断点按提示词内容与分辨率判定，改提示词或换档位会重复扣费**：出图的断点 key 由
「图号 + 分辨率 + 提示词」算出来，
提示词变一个字、或 `--resolution` 换一档，key 就变，已完成记录不匹配，**会重新出图并再次扣费**。实测有人连跑 5 次付费出图
会话（约 240 点 ≈ 2.4 元），**超出预算 5 倍**。重跑前请先确认提示词与分辨率都没变，或先用 `cost` 核对预估花费。

> 反过来说：**本包的断点不会拿旧图糊弄你**。改过提示词、或换过分辨率就一定重出，
> 改没改以提示词内容与档位为准，
> 不会出现「以为重出了、其实拿到旧图」这种不打一声招呼的复用。

**收集排错信息时请附上**：完整命令、`--dry-run` 的输出、`AUDIT.md` 内容、原始报错文本。
**不要在报错信息或截图里带上你的 API Key。**

### 退出码（可直接用于流水线）

| 退出码 | 含义 |
|---|---|
| `0` | 全部干净，闸门全绿 |
| `2` | **用法错误**（`--outdir` 落在包内 / 参数写错） |
| `3` | **被闸门拦下**（违禁词 / 占位符 / 照抄示例 / 字数越界 / 结构残缺 / 比例不符 / 超预算） |
| `4` | 调用失败（网络 / 鉴权 / 点数 / 模型名），或出图没给 `--yes` |
| `130` | 用户中断（Ctrl+C） |

`3` 与 `4` 分开是有意的：`3` = "上游没问题，是被本地规则拦了"，
`4` = "上游/网络有问题，或者你还没确认花钱"。CI 里这两种要采取完全不同的动作。

**`--json` 输出契约**（给流水线与 agent 消费，**只在 `--json` 下生效**）：

- 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
- 失败：**如果本次有产出要报**，就把错误**并入**结果主体
  （`"ok": false` + `"exit": <码>` + `"error": {"kind":…,"message":…}`），
  这样正文、逐条闸门命中原因、配图真实像素这些失败时最需要机读的东西不会丢；
  **如果本次没有任何产出**，则只发一个独立信封
  `{"ok": false, "exit": 3, "error": {"kind": "gate", "message": "…"}}`
- 两种情况都保证：**stdout 只有一个完整 JSON 文档**，`json.loads` 一次通过；
  `exit` 就是本次真实退出码；`kind` 取 `gate` / `usage` / `budget` / `call` / `interrupt` / `internal`
- `internal` 是**没预料到的异常**（代码 bug）的兜底：stdout 给信封、
  **完整 traceback 原样打到 stderr**、退出码固定 1 —— 报 bug，不藏 bug
- 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出与以前完全一致
- `--json` 写在子命令**前面或后面都可以**

## 文件结构

```
sanjianke-longform-factory/
├── SKILL.md                            本文件
├── README.md                           给人看的说明
├── LICENSE.md                          MIT，署名三剪客
├── references/
│   ├── longform-writing-method.md      长文写作方法与判定口径
│   ├── platform-specs.md               三个平台的字数 / 结构 / 配图规格
│   └── compliance-and-gates.md         合规红线与八道闸门的判据
└── scripts/
    ├── a7w.py                          api.a7w.cn 零依赖客户端（**逐字节等于规范版，本包不改它**）
    ├── imgprobe.py                     图片头探针：读真实像素（只读，纯标准库）
    └── run.py                          outline / write / images / adapt / all / cost / models
```

## 端点速查

本包全部能力都走 api.a7w.cn（下面几行的域名都来自算力集市 api.a7w.cn）：

| 用途 | 方法与路径 |
|---|---|
| 选题角度 / 大纲 / 正文 / 平台适配（算力集市 api.a7w.cn） | `POST https://api.a7w.cn/api/v1/chat/completions` |
| 在架模型清单（算力集市 api.a7w.cn） | `GET https://api.a7w.cn/api/v1/models` |
| 提交出图任务（算力集市 api.a7w.cn） | `POST https://api.a7w.cn/api/v1/apps/nano_banana/submit` |
| 轮询任务（算力集市 api.a7w.cn） | `GET https://api.a7w.cn/api/v1/tasks/<task_id>` |

文本协议是 **OpenAI 兼容**：`Authorization: Bearer <Key>`，请求体用
`model` / `messages` / `temperature` / `max_tokens` / `response_format`。

三条实测记下来的口径：

1. **走 `/chat/completions` 的成功响应不带 `code` 字段**，直接读
   `choices[0].message.content`；`{"code":1,"data":{...}}` 那层信封是给生成应用的。
2. **出图任务的 `status` 在 `data` 顶层，不在 `data.result` 里**。平台文档写的是
   `data.result.status`，照文档写会永远读不到状态、一路轮询到超时。
   实际扣费只信 `data.usage.points_cost`。
3. **`deepseek-chat` 不在 `/api/v1/models` 的返回列表里，但实测可用**（路由到
   `deepseek-flash`）。所以"列表里没有"不等于"不能用"。

## 联系我们

遇到问题可加技术微信 9872659。

## 相关链接

- 算力集市 api.a7w.cn（注册领 Key）：https://api.a7w.cn/
- 长文写作方法与判定口径：`references/longform-writing-method.md`
- 三个平台的字数 / 结构 / 配图规格：`references/platform-specs.md`
- 合规红线与八道闸门的判据：`references/compliance-and-gates.md`

---

> **免责声明**：本包内置的违禁词表与判定口径是**启发式自检工具**，来自公开经验整理，
> 不构成法律意见，也不代表任何平台的官方审核标准。
> 文章内容的准确性、版权、以及宣发物料的合规责任由使用者承担；
> 医疗健康、金融投资、母婴、特殊化妆品等高风险类目必须人工复核后再使用。
> 正文与配图由大模型生成，**发布前请至少通读一遍**——脚本能拦下违禁词、占位符、
> 照抄示例、字数越界、结构残缺与比例不符，拦不住事实性错误。
