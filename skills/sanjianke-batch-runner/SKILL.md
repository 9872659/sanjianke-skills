---
name: sanjianke-batch-runner
slug: sanjianke-batch-runner
displayName: 批量调度 一千条任务排队跑完
description: "**1,000 条任务一条命令跑完，排队、体检、报价全程 0 点。** 把清单写成 JSONL（一行一个任务），`run` 负责 4 路并发提交、免费轮询、失败重试（退避 2s/4s/8s）、断点续跑：每完成一条就把 taskId 与实扣点数原子落盘，Ctrl-C 或断电之后重跑同一条命令自动跳过已完成的。`--budget` 是硬闸门：开跑前合计超线退 5、一个请求都不发；跑的过程中累计要超线就停手、把剩下的留给下次。放行表只有 POST 提交端点（72 个，含 29 个音频接口），`GET /apps/<app>`、应用层 `/query`、`/api/v1/tasks` 这类一次一扣的路径在清单里会被当场拒掉。`catalog` / `cost` / `plan` / `doctor` 四个免费子命令先把价目、工期与 Key 状态看清。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "它不产生内容，只把别人的任务跑完：清单里每一行是一个已经决定好的提交请求（端点 + body + 预估点数），本包管排队、并发、轮询、重试、落盘、算钱、守预算，内容的参数与提示词归各能力包。**72 个放行端点**：16 个视频后处理档、2 个图片端点（6 点/张）、21 个应用提交、4 个语音提交、29 个 media_services_33 音频接口；单价与 `GET /api/v1/pricing` 的 115 条规则逐档对齐，`doctor` 每次核对 16 档不漂移。**轮询只打免费视图**：`GET /api/v1/tasks/<id>` 与 `GET /api/v1/video/viapi/result/<id>`，应用层 `/query` 一次一扣所以默认不自动轮询，提交成功即记 submitted、出片后去 billing 台账取。**断点续跑**：状态文件每完成一条原子重写，重跑跳过 done/submitted，失败与中断在飞的用 `--retry-failed` 补。**双闸门**：缺 `--yes` 退 4 并报出这次要发几条、多少点；合计超 `--budget` 退 5，一个请求都不发。默认 4 并发。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 批量调度
  - 任务队列
  - api.a7w.cn
---

# 批量调度 一千条任务排队跑完

> **先申请你自己的 API Key。** 本包不内嵌任何 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

**1,000 条任务一条命令跑完，排队、体检、报价、断点全程 0 点。** 出图用什么提示词、成片什么分辨率、配音什么音色，都是别人的事；本包只认清单里那一行 `{"id", "endpoint", "body", "points"}`，负责送出去、等回来、记下来。

## 和底层能力包的分工（谁干什么）

| 你要的答案 | 用哪个包 | 它交付什么 |
|---|---|---|
| **1,000 条任务排队跑完、断了接着跑** | **本包** | 并发提交、免费轮询、失败重试、断点状态、预算守卫 |
| 这一单跑之前要多少钱 | `sanjianke-cost-forecast` | 逐项报价单 + 区间 + 陷阱标注 |
| 一张图 / 一条片 / 一段配音怎么出 | `sanjianke-gpt-image` `a7w-full-video` `a7w-voice-tts` | 各自的参数、提示词、调用示例 |
| 跑完到底花了多少、退了多少 | `sanjianke-billing` | 7 个只读端点对账，三方口径一致 |
| 同一件事哪条路便宜 | `sanjianke-price-radar` | 单价排行、最便宜路径 |

一句话：**billing 管跑完以后，cost-forecast 管跑之前，本包管跑的过程。**

## 一份清单跑一天（JSONL，一行一个任务）

```json
{"id": "img-0001", "endpoint": "/api/v1/images/generations", "body": {"model": "gpt-image-2.6", "prompt": "分镜 1：雨夜街头", "n": 1}}
{"id": "enh-0001", "endpoint": "/api/v1/video/viapi/enhance", "body": {"videoUrl": "https://oss.gpu.likeadmin.cn/openapi/a.mp4", "duration": 15}}
{"id": "app-0001", "endpoint": "/api/v1/apps/nano_banana/submit", "body": {"prompt": "商品主图"}, "points": 72}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一名字，状态文件按它落盘；重复会在体检时退 2 |
| `endpoint` | 是 | 只认 catalog 里的 72 个 POST 提交端点 |
| `body` | 是 | 原样发给上游；`videoUrl` 先过白名单本地预检 |
| `points` | 否 | 预估点数；不写就按价目表现算：按秒 × `duration`、按张 × `n`、按字 × `chars` |
| `poll` | 否 | `tasks` / `video` / `none`，默认按端点自动选 |

价目表里没公开单价的端点（29 个音频接口、图片数字人、视频对口型）在清单这一行写上 `points`，预算守卫就用它。

## 断点续跑怎么工作

```
每完成一条 → 状态文件原子重写（临时文件 + os.replace + fsync），记 taskId / 状态 / 实扣点数
Ctrl-C     → 只置停止位，在飞的任务收尾后落盘，退出码 130
重跑同一条  → done / submitted 直接跳过，从断点接着跑
```

状态文件默认 `<清单名>.state.json`。上次中断时正在提交的那条标成 `unknown`（可能已经建了任务），默认不重发；核对 billing 台账后加 `--retry-failed` 补。

## 三层控制：先看清，再开跑

| 子命令 | 花费 | 看什么 |
|---|---|---|
| `catalog` | 0 点 | 72 个端点、单价、轮询方式，一眼挑出最便宜的档 |
| `plan` | 0 点 | 逐行校验清单，打印前几条将发出的请求与轮询地址 |
| `cost` | 0 点 | 合计点数、按端点分组、并发下的预计耗时、预算余量 |
| `doctor` | 0 点 | Key、余额、115 条价目、22 个应用目录、3 条提交探针、流水前后比对 |

`cost` 跑出来的样子（8 条任务）：`合计 1,806.32 点 = 18.06 元`，`4 并发 × 45 秒/条 ≈ 1 分 30 秒`，余量 8,193.68 点。

## 交付清单（一单 = 6 件，跑完就交这几样）

| # | 交付物 | 规格 | 命名 |
|---|---|---|---|
| 1 | 任务清单 | JSONL，一行一个任务，1,000 行约 300 KB | `20261108_项目_batch.jsonl` |
| 2 | 断点状态 | `run` 自动维护，原子写，带 taskId 与实扣点数 | `20261108_项目_batch.jsonl.state.json` |
| 3 | 运行报告 | `--report` 写出的结果表（逐条状态 + 点数） | `20261108_项目_batch.result.json` |
| 4 | 失败清单 | 只含失败条目，补跑依据 | `20261108_项目_batch.failed.jsonl` |
| 5 | 报价单 | `cost --json` 全文，报给甲方用 | `20261108_项目_batch.cost.json` |
| 6 | 对账单 | `sanjianke-billing` 的 overview，证明真花多少 | `20261108_项目_billing.md` |

## 批量岗一天怎么排

| 时间 | 干什么 | 命令 | 花费 |
|---|---|---|---|
| 09:00 | 收单：多少张图、多少条片、素材在哪 | — | 0 |
| 09:20 | 体检清单：端点、id、videoUrl、缺 points 的行一次挑出来 | `plan --file 单.jsonl` | 0 点 |
| 09:40 | 报价 + 排工期，报给甲方或主管 | `cost --file 单.jsonl` | 0 点 |
| 10:00 | 开跑，4 路并发，边跑边看进度与剩余时间 | `run --file 单.jsonl --yes` | 按点结算 |
| 每小时 | 看断点：完成 / 已提交 / 失败 / 未开始 | `status --file 单.jsonl` | 0 点 |
| 18:00 | 出报告 + 补跑失败的 + 交对账 | `run --retry-failed --report 报告` | 按点结算 |

## 把一次一扣的路径挡在清单外

| 路径 | 为什么在放行表外 |
|---|---|
| `GET /api/v1/apps/<app>` | 命中通配计价，按该应用 flat 单价 sync 扣，无退款 |
| `POST /api/v1/apps/<app>/query` | 应用层查询一次就是一次的钱，10 条任务轮 30 次就是 30 次 |
| `POST /api/v1/apps/<app>/submit` 缺参 | 先 reserve_sync 冻结、再校验、再退，钱包被短暂动过 |
| `POST /api/v1/tasks` | 通配入口按 per_module 50 点计，属于查询不属于提交 |

清单里写了这些路径，`plan` 当场退 2 并指到正确写法：**提交只走 `/apps/<app>/submit` 这类子路径，查询只走两条免费视图。**

## 价目锚点（2026-11-08 现查，1 元 = 100 点）

- 文生图 **6 点/张**：1,000 张 = 6,000 点 = 60 元；nano-banana 72 点/次，1,000 张 = 72,000 点
- 视频校色 / 字幕擦除 / 抠像 **9 点/秒**：1,000 条 15 秒 = 135,000 点 = 1,350 元
- 画质增强 **15 点/秒**：1,000 条 15 秒 = 225,000 点 = 2,250 元；视频修复 36 点/秒，同量 540,000 点
- 语音合成 **0.18 点/字**：1,000 条 × 24 字 = 4,320 点 = 43.20 元；音色克隆 600 点/次

## 三步上手

```bash
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"
python3 scripts/run.py doctor                                      # 1) 自检，0 点
python3 scripts/run.py cost --file 单.jsonl                        # 2) 报价 + 工期，0 点
python3 scripts/run.py run --file 单.jsonl --concurrency 4 --yes   # 3) 开跑
```

## 常用命令

| 命令 | 花费 | 干什么 |
|---|---|---|
| `run --file F --yes` | 按点 | 开跑，默认 4 并发、重试 2 次 |
| `run --file F --retry-failed --yes` | 按点 | 只补失败与中断在飞的 |
| `status --file F` | 0 点 | 完成 / 已提交 / 失败 / 未开始，逐条看 |
| `cost --file F` | 0 点 | 合计点数 + 工期 + 余量 |
| `catalog` | 0 点 | 72 个端点与单价 |
| `doctor` | 0 点 | 9 项自检，跑前跑后流水比对 |
| `upload --file 素材.mp4` | 0 点 | 换平台托管地址，喂给 `body.videoUrl` |

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--file` / `--state` | — / `<清单>.state.json` | 清单路径 / 状态文件路径 |
| `--concurrency` | 4 | 并发数，1~16；先 4，稳了再往上加 |
| `--retry` / `--retry-failed` | 2 / — | 单条重试次数（退避 2s / 4s / 8s）/ 连失败的一起补 |
| `--budget` | 10000 | 点数上限（单位：点，1 元 = 100 点） |
| `--poll-interval` / `--wait` | 5 / 1800 | 轮询间隔秒数 / 单条最多等多少秒 |
| `--report` | — | 结果表与失败清单写到哪个目录 |
| `--yes` / `--dry-run` / `--json` | — | 确认 / 只打印 / 只输出一个 JSON 文档 |

## 退出码与 `--json` 契约

`0` 成功 · `2` 用法错（清单格式 / 未知端点 / 缺 points / 选项缩写）· `3` 自检未过 · `4` 缺 `--yes` · `5` 超 `--budget`（**一个请求都不发**）· `6` 有任务失败 · `1` 内部错 · `130` 中断。

成功：`{"ok": true, "ran": 5, "counts": {...}, "spentPoints": 534, "state": "..."}`；失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。stdout 只有一个 JSON 文档，进度走 stderr。

## 文件结构

正好 7 个文件：`SKILL.md` · `README.md` · `LICENSE.md` · `references/api-contract.md`（端点原文与实测结构）· `references/troubleshooting.md`（按报错找原因）· `scripts/a7w.py`（零依赖客户端，全家族逐字节一致）· `scripts/run.py`（本包命令层）。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
