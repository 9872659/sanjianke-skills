---
name: sanjianke-cost-forecast
slug: sanjianke-cost-forecast
displayName: 成本预估器 花之前先把这一单算清
description: "**一单 5,587 点 = 55.87 元，算这一单 0 点。** 给一份任务清单（几张图、几条视频几秒、几段配音几字、几次后处理几秒），`quote` 逐项报价、合计、给区间，并把这 5 类最容易算错的坑直接标在那一行上：价目表里 11 个 `tsc_*` 档路由 404、3 个腾讯档上游 502、6 条 note 写「点/次」而 rule 是 per_second、未单独定价的接口落通配（上游×2、保底 50 点，实测 15.60 / 26 / 44 点都没保底）、应用层与模型层同一件事差 2.7~75.5 倍。三个只读端点现查价目，模型层单价从你自己的 `GET /api/v1/me/tasks` 按 actualPrice 反推。`compare` 出差价排行，`budget` 给 10 元 / 100 元 / 1000 元三档各能做什么，`doctor` 前后各读一次流水证明本轮 0 点。缺 `--yes` 退 4，超 `--budget` 退 5 且一个请求都不发。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "本包管「花之前那一张报价单」。**一单 5,587 点 = 55.87 元**：6 张分镜图 36 + 15 秒 1080P 成片 900 + 2 条模型层 Seedance 291.46 + 2 分钟修复 4,320 + 220 字配音 39.60。**数据来源全是只读 GET**：`/api/v1/pricing`（115 条规则、裸对象、markupPercent 20）、`/api/v1/models`（316 条 = 221 目录 + 95 裸模型层 ID，带价的 92 条全是文本模型）、`/api/v1/apps`（22 应用 / 100 接口）、`/api/v1/me/tasks`（1,398 条历史 actualPrice，模型层单价只在这里反推得到）、`/api/v1/tasks/<假 id>`（200「任务不存在」）、`/user/balance` 与 `/user/balance/logs`。**六个免费子命令**：catalog 价目总表按计费口径分组；cost 常用四件事 + 三档单量；quote 按清单逐项报价 + 合计 + 区间（乐观 = 按次 / 实测最低，基准 = rule 口径，保守 = 基准 +30% 重跑余量）；compare 应用层 vs 模型层差价排行；traps 五类陷阱逐条摊开；budget 三档预算各能买什么。**闸门**：先用内置基线判一次预算，超 `--budget` 退 5、一个请求都不发；批量 ≥30 个只读请求缺 `--yes` 退 4。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 成本预估
  - 报价单
  - api.a7w.cn
---

# 成本预估器 花之前先把这一单算清

> **先申请你自己的 API Key。** 本包不内嵌任何 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

**一单 5,587 点 = 55.87 元，算这一单 0 点。** 把清单喂进去，明细、合计、区间、陷阱一起出来。

## 这一单的报价单（`quote --preset duanju` 真跑出来的）

| # | 项目 | 计费口径 | 数量 | 点数 | 元 |
|---|---|---|---|---|---|
| 1 | 分镜图 | 6 点/张（流水 sync 实测） | 6 张 | 36 | 0.36 |
| 2 | 成片 1080P | 60 点/秒（full_video） | 15 秒 | 900 | 9.00 |
| 3 | 模型层补镜 | 145.73 点/条（Seedance 2.0 实测） | 2 条 | 291.46 | 2.91 |
| 4 | 老素材修复 | 36 点/秒（restore） | 120 秒 | 4,320 | 43.20 |
| 5 | 旁白配音 | 0.18 点/字（voice_tts） | 220 字 | 39.60 | 0.40 |
| | **基准合计** | | | **5,587** | **55.87** |

区间 **5,587 ~ 7,491 点 = 55.87 ~ 74.91 元**：乐观按次 / 实测最低口径，基准按 rule 口径，保守加 30% 重跑余量。按秒档里 `restore` 36 点/秒最狠，两分钟 43.20 元，比 15 秒成片贵 4.8 倍。

## 和底层能力包的分工（谁干什么）

| 你要的答案 | 用哪个包 | 它交付什么 |
|---|---|---|
| **这一单多少钱、区间多少、哪一行最贵** | **本包** | 清单 → 逐项明细 + 合计 + 区间 + 陷阱标注 + 预算档位 |
| 已经花掉多少、退了多少、净花多少 | `sanjianke-billing` | 7 个只读端点对账，usage / billing / 流水三方口径 |
| 全站单价排行、同一件事哪条路便宜 | `sanjianke-price-radar` | 差价榜、最便宜路径、模型目录分组 |
| 一张图怎么出、参数怎么填 | `sanjianke-gpt-image` | 文生图 / 图生图 / GIF，6 点一张 |
| 一条成片 / 一段配音怎么出 | `a7w-full-video` `a7w-voice-tts` | 按秒 × 分辨率；tts / tts_async / clone_voice |

billing 管**事后**，price-radar 管**单价**，本包管**事前这一单**：还没花，先把「要几张图、几条视频几秒、几段配音几字、几次后处理几秒」换算成点数与元。

## 交付清单（一单 = 一份报价单，5 件）

| # | 交付物 | 规格 | 命名 |
|---|---|---|---|
| 1 | 任务清单 | JSON，`kind` ∈ image / video / post / voice / app | `20261108_项目_plan.json` |
| 2 | 报价单 JSON | `quote --json` 全文，机器可读，带每项 `rangeLow/rangeBase/rangeHigh` | `20261108_项目_quote.json` |
| 3 | 报价单 Markdown | 明细表 + 合计 + 区间 + 陷阱命中 + 来源 | `20261108_项目_quote.md` |
| 4 | 陷阱清单 | 本单命中的陷阱 + 命中行 + 处理办法 | 含在报价单「陷阱命中」一节 |
| 5 | 预算建议 | 本单落在 10 / 100 / 1000 元哪一档、余量多少 | 含在报价单末行 |

`quote --out 报价/` 一次把第 2、3 件写盘；第 1 件用 `sample --preset duanju --out .` 起个头。

## 报价岗一天怎么排

| 时间 | 干什么 | 命令 | 花费 |
|---|---|---|---|
| 09:30 | 收今天的活：几张图、几条片子几秒、配音多少字、要不要后处理 | — | 0 |
| 10:00 | 自检 Key / 价目 / 目录 / 流水，确认价目没动 | `doctor` | 0 点 |
| 10:20 | 起一份清单样例，按今天的量改；顺手报价 | `sample --out .` `quote --out 报价` | 0 点 |
| 11:10 | 同一件事比一比：应用层还是模型层；对预算 | `compare` `budget` | 0 点 |
| 14:00 | 甲方砍预算：改清单里的秒数与张数重报 | `quote --file 清单_v2.json` | 0 点 |

## 五类价格陷阱（报价里逐行标注）

| # | 陷阱 | 现查到的数字 | 报价里怎么体现 |
|---|---|---|---|
| ① | 价目表有、路由 404 | **11 个 `tsc_*` 档**，2~6 点/秒、保底 10 点 | 那一行标 `!`，提示换 viapi 同档 |
| ② | 路由在、上游 502 | **3 个腾讯档**：1080 2 / 2k 4 / 4k 8 点/秒 | 标注上游凭据问题、整批退款实扣 0 |
| ③ | note 写「点/次」、rule 是 per_second | **6 条**：`shot` `castcrew` `delogo` 各扁平 + viapi | 按秒报，区间下限用按次口径 |
| ④ | 落通配保底 | 未定价接口 = 上游×2、保底 50 点 | 标注来源「通配保底」，并提示实测 15.60 / 26 / 44 点都低于 50 |
| ⑤ | 应用层 vs 模型层 | Seedance 11,000 vs 145.73 = **75.5 倍** | 应用层那一行标 `!`，指向 `compare` |

`traps` 把五类逐条摊开；`doctor` 每次核对「①11 ②3 ③6 ④保底 50 ⑤配对 11 组」这组计数，价目一动就会变红。

## 价目表（2026-11-08 现查，1 元 = 100 点）

| 能力 | 单价 |
|---|---|
| 出图 · 模型层 | gpt-image-2.6 **6 点/张**、seedream-5-0-flash 15.60、gpt-image-2 26、gpt-image-2-pro 39 |
| 出图 · 应用层 | nano_banana 72、aigc_qwen_image 78、aigc_photo_restore 105、aigc_qwen_image_pro 105、dressing_diffusion 200、aigc_wan_image 203 |
| 视频 · 按秒 | restore 36、upscale 30、cartoon 24、interp 25、faceswap 20、shot 20、portrait 18、enhance 15、superres2k 15、superres 9、colorize 9、subtitle 9、segment 9 |
| 视频 · 应用层 | full_video 480P 14 / 768P 28 / **1080P 60** / 2K 80 / 4K 80 点/秒；flashvsr 10（保底 20）；image_human 快 10 / 标准 15 / 2K 30 / 4K 60；smart_clip 4.5 |
| 视频 · 一口价 | seedance 11,000、wan 800、happy_horse 650、mmaudio 495、grok_video 300、seedsvc 220 |
| 视频 · 模型层实测 | sd/doubao-seedance-2-0 145.73、volcengine/…2-5 762.30、muse-video 44、wan3.0-video 300 |
| 配音 | voice_tts 约 **0.18 点/字**（上游实际点数 ×3，单条随文本长度浮动） |
| 免费 | `GET /api/v1/tasks/<id>`、`POST /api/v1/upload`、本包全部子命令 |

## 一单多少钱（三个样例）

- **短剧一集**：6 图 + 15 秒 1080P + 2 条模型层 10 秒 + 2 分钟修复 + 220 字配音 = **5,587 点 = 55.87 元**
- **电商一条详情**：8 图 + 15 秒 1080P + 120 字配音 + 2 分钟超分 = **2,050 点 = 20.50 元**；**口播一条 60 秒** = **516 点 = 5.16 元**

## 预算档位（`budget` 现算）

| 预算 | 点数 | 能做什么 |
|---|---|---|
| **10 元** | 1,000 | 166 张图 / 16 秒 1080P / 111 秒超分 / 5,555 字配音 / 6 条模型层 Seedance |
| **100 元** | 10,000 | 1,666 张图 / 166 秒 1080P / 18 分钟超分 / 68 条模型层 Seedance |
| **1000 元** | 100,000 | 16,666 张图 / 1,666 秒 1080P / 686 条模型层 Seedance / 9 条应用层 Seedance |

## 三步上手

```bash
export A7W_API_KEY=sk-你的key        # Windows: $env:A7W_API_KEY="sk-你的key"
python3 scripts/run.py doctor                                    # 1) 自检，0 点
python3 scripts/run.py quote --preset duanju --out 报价          # 2) 出报价单，0 点
python3 scripts/run.py quote --file 20261108_项目_plan.json --budget 20000   # 3) 换成自己的单量
```

## 常用命令

| 命令 | 花费 | 干什么 |
|---|---|---|
| `quote --file / --preset` | 0 点 | 逐项报价 + 合计 + 区间 + 陷阱（本包核心） |
| `compare --pages 5` | 0 点 | 应用层 vs 模型层差价排行，最大 75.5 倍 |
| `traps` | 0 点 | 五类陷阱逐条摊开 |
| `budget` | 0 点 | 10 / 100 / 1000 元各能做什么 |
| `catalog [--models]` | 0 点 | 价目总表（按口径分组）+ 模型目录构成 |
| `doctor` | 0 点 | 7 个只读端点 + 价目一致性 + 流水前后比对 |

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--budget` | 5000 | 点数上限（**单位：点**，1 元 = 100 点）；本单超它退 5 |
| `--file` / `--preset` | — | 清单文件 / 内置样例 `duanju` `ecom` `koubo` |
| `--out` | — | 写盘目录（报价单 JSON + Markdown，或清单样例） |
| `--offline` | — | 完全不出网：本地缓存或内置基线，0 请求 |
| `--allow-over-budget` | — | 超预算也照报（仍然 0 点） |
| `--pages` / `--all` / `--yes` | 5 / — / — | 翻几页台账找模型层实测价；`--all` 约 70 页要 `--yes` |
| `--json` / `--dry-run` | — | 只输出一个 JSON 文档 / 只打印请求，一个都不发 |

## 退出码与 `--json` 契约

`0` 成功 · `2` 用法错（清单格式 / 未知对象 / 选项缩写）· `3` 自检未过 ·
`4` 缺 `--yes` · `5` 超 `--budget`（**一个请求都不发**）· `6` 调用失败 · `1` 内部错 · `130` 中断。

成功：`{"ok": true, "estimate": true, "items": [...], "total": {...}, "traps": [...]}`；
失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，
`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。stdout 只有一个 JSON 文档。

## 文件结构

正好 7 个文件：`SKILL.md` · `README.md` · `LICENSE.md` ·
`references/api-contract.md`（四个只读端点的原始结构）· `references/troubleshooting.md`（按报错找原因）·
`scripts/a7w.py`（零依赖客户端，全家族逐字节一致）· `scripts/run.py`（本包命令层）。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
