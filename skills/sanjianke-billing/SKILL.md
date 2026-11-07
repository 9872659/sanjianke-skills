---
name: sanjianke-billing
slug: sanjianke-billing
displayName: 对账台 · 我的钱花在哪一查就清
description: "**跑了 100 次调用，账户少了 300 块 —— 到底花在哪了？一条命令摊开给你看，扣 0 点。** 本包只用 7 个只读 GET，把 api.a7w.cn 已经记好的账全部读出来、算清、摆成表：30 天花了多少、退了多少、净花多少、日均多少，按 32 个真实接口路径排序算占比，并把 `/api/v1/apps/pic_lipsync/submit` 这种路径翻成人话「图片对口型（照片开口说话）」。实测踩出来的三个口径坑都做成了默认动作：一、`/user/usage` 的 `byPath` 只回**一个桶** `{\"(任务冻结/结算)\": 420306}`，按路径分组必须自己从任务台账的 `path` 字段归集；二、`refunded` 不等于没花钱、`netPoints` 也不等于标价 —— 全量实测标价合计 1,614,557 点而真扣只有 104,785 点，差 15 倍；三、流水页的 `netPoints` 是流水口径（-404,408，预扣+退款来回都算），`balanceMoving` 才是真净（-175,243）。`doctor` 每次都会验 `usage.netPoints = billing.netConsumedPoints = logs.balanceMoving` 三方一致，实测差 0.00 点。6 个子命令全部只读，任何情况下扣 0 点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "对账这件事难在「口径」，不难在接口。a7w 网关把每一笔都记好了，7 个只读 GET 就能拿到：`/user/usage?days=30`（calls / chargedPoints / refundedPoints / netPoints / byPath）、`/api/v1/me/billing`（grossChargedPoints / refundedPoints / netConsumedPoints / check 验算 / 唯一权威口径的 note）、`/user/balance`（available_points / frozen / yuan / rate=100，1 元 = 100 点）、`/user/balance/logs`（logs[] 流水，typeName 是中文、reference 里带路径）、`/api/v1/me/tasks`（带 path / actualPrice / refundedPoints / netPoints；每页固定 20 条，`size`/`per_page` 无效，`limit` 决定统计最近 N 条，实测真实条数 1389）、`/api/v1/tasks`（全量 27218 条，`per_page` 最大 100，`status=failed` 可筛，实测 3397 条 failed）、`/api/v1/recharge/packages`（4 档，9.9 元含 10 点赠送，折 102.02 点/元，比 100 元档的 100.00 更划算）。本包把它们拼成六件事：`overview` 一张表说清 30 天花了/退了/净花/日均；`by-path` 按 32 个真实路径排序算占比，并给出「这张表覆盖权威净花多少」；`tasks --status failed` 逐条列出失败任务，实测 `actual_points` 恒为 `0.00`，钱没扣；`logs` 把流水翻成中文类型 + 路径；`balance` 给余额、冻结、折合元与充值档位性价比；`doctor` 验 7 个端点 + 三方口径一致性。全部只读，任何情况下扣 0 点，`--budget 0` 会直接退 5、一个请求都不发。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 对账计费
  - 用量分析
  - api.a7w.cn
---

# 对账台 · 我的钱花在哪一查就清

> ## 先申请你自己的 API Key
> 本包不内嵌任何 Key，读的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的账户的账；注册、充值、创建 Key 都在 [api.a7w.cn](https://api.a7w.cn/)。
> 拿到 Key 后跑 `python3 scripts/a7w.py login --key sk-你的key`。

**账户少了 300 块，钱花在哪？** 7 个只读 GET，6 条命令，把 30 天的账摊成表 —— **扣 0 点**。

## 一张表：30 天的钱去哪了

实测（2026-11-07，本包作者的账户，30 天窗口）：

| 口径 | 点数 | 折合 | 说明 |
|---|---|---|---|
| 调用次数 | **7,990 次** | — | 含成功与失败 |
| 花掉 `chargedPoints` | **425,674.83** | ¥4,256.75 | 预扣口径，看着最吓人 |
| 退回 `refundedPoints` | **250,431.57** | ¥2,504.32 | 失败 / 少算的自动退回 |
| 净花 `netPoints` | **175,243.26** | ¥1,752.43 | **这才是真花** |
| 日均 | **5,841.44** | ¥58.41 | 净花 ÷ 30 |
| 余额 | 999,997,394,498 | — | 可用点，冻结 0 点 |

**三方校验**：`usage.netPoints` 175,243.26 = `billing.netConsumedPoints` 175,243.26 = 流水 `balanceMoving` 175,243.26，**差 0.00 点**。这三个数永远该相等，不等就是有笔账没落库。

按路径拆开（全量 1389 条任务、32 个路径、覆盖权威净花 **73.0%**）：

| # | 路径（人话） | 次数 | 净花 | 占比 |
|---|---|---|---|---|
| 1 | 图片对口型（照片开口说话） | 120 | 54,907.01 | 42.89% |
| 2 | 图片数字人（照片生成数字人） | 14 | 35,532.00 | 27.76% |
| 3 | 真人播报（数字人口播成片） | 163 | 27,943.42 | 21.83% |
| 4 | 语音合成·长文本（异步） | 125 | 3,130.00 | 2.45% |
| 5 | nano-banana 出图 | 165 | 2,376.00 | 1.86% |

## 三个别人不会告诉你的口径

**一、`byPath` 只回一个桶，所以「按路径」得自己算。** 1 天、7 天、30 天、90 天、365 天，`byPath` 都只有一个键 `{"(任务冻结/结算)": 420306.1851}` —— 一个中文标签，不是 URL 路径。想按路径看，只能翻 `/api/v1/me/tasks` 的 `path` 字段自己归集，本包的 `by-path` 就干这个。

**二、`refunded` 不等于没花钱，`netPoints` 也不等于标价。** 实测一个任务 `{"actualPrice":72,"refund":122,"chargedPoints":72,"refundedPoints":72,"netPoints":0}`：**真扣**是 `netPoints`（0），**标价 / 预留**是 `actualPrice`（72），**`refund`**（122）是流水里所有 refund 类型之和，连别的任务的同步退款也算进来，会偏大。全量对比：标价合计 **1,614,557 点**，真扣只有 **104,785 点** —— 差 15 倍。

**三、流水页的 `netPoints` 是流水口径，`balanceMoving` 才是真净。** `logs.netPoints = -404,408.72`（预扣 -60、退款 +60 来回都算，翻了一倍），`logs.balanceMoving = -175,243.26`（真实净变动，和 `/user/usage` 完全对得上）。

## 路径翻译表（32 个真实路径）

| 接口路径 | 人话 |
|---|---|
| `/api/v1/apps/pic_lipsync/submit` | 图片对口型（照片开口说话） |
| `/api/v1/apps/lipsync/submit` | 视频对口型（换成别人的嘴型） |
| `/api/v1/apps/image_human/submit` | 图片数字人（照片生成数字人） |
| `/api/v1/apps/smart_clip/realman_broadcast` | 真人播报（数字人口播成片） |
| `/api/v1/apps/smart_clip/broadcast_mixcut` | 播报混剪 |
| `/api/v1/apps/voice_tts/tts_async` | 语音合成·长文本（异步） |
| `/api/v1/apps/voice_tts/tts_live` | 语音合成·实时（流式） |
| `/api/v1/apps/voice_tts/clone_voice` | 音色克隆 |
| `/api/v1/apps/indextts/submit` | IndexTTS 配音 |
| `/api/v1/apps/nano_banana/submit` | nano-banana 出图 |
| `/api/v1/apps/aigc_photo_restore/generate/index` | 老照片修复 |
| `/api/v1/apps/dressing_diffusion/submit` | AI 换装 |
| `/api/v1/apps/full_video/submit` | 一键成片（全流程） |
| `/api/v1/apps/wan/create` | 通义万相·视频创作 |
| `/api/v1/apps/seedance/create` | 豆包 Seedance·视频创作 |
| `/api/v1/apps/grok_video/submit` | Grok 视频生成 |
| `/api/v1/apps/action_transfer/submit` | 动作迁移（把 A 的动作搬到 B） |
| `/api/v1/apps/person_replacement/submit` | 人物替换（换人 / 换脸） |
| `/api/v1/apps/flashvsr/submit` | FlashVSR 视频超分 |
| `/api/v1/videos` | 视频任务（参考图生视频） |
| `/api/v1/videos/generations` | 视频生成·多模态（万相 / 豆包） |
| `/api/v1/video/tencent4k` | 腾讯 4K 超分 |
| `/api/v1/video/viapi/superres` | 视频超分·标准 |
| `/api/v1/tasks` | 通用任务入口（文生图 / 图片编辑） |
| `/v1/videos` | 视频任务（少了 `/api` 前缀，网关照样记账） |

没收录的路径按前缀兜底（`/api/v1/apps/<名字>` → 「应用 · 名字」）。

## 失败任务对账

`python3 scripts/run.py tasks --status failed --pages 2`

```
任务台账 · 本次 100 条（全账 3,397 条） · status=failed
  2026-11-07T12:06:31Z  flashvsr/submit     failed  0.00  app  task_d774cfb6a85804c745b9f123
  2026-11-07T11:44:47Z  nano_banana/submit  failed  0.00  app  task_48f826dcb5f289aed76d0236
  2026-11-07T05:24:51Z  gpt-5.4             failed  0.00  -    task_2a710884268ea466b596b9d2
  未完成（status≠completed）100 条，合计 0.00 点 —— 失败任务 actual_points 恒为 0.00，钱没扣。
```

**3397 条失败，合计 0.00 点。** 失败不扣钱，账面上「少了」的那些都在成功任务里。

## 三步上手

```bash
python3 scripts/run.py doctor                 # 第 1 步：7 个端点 + 三方口径，免费
python3 scripts/run.py overview               # 第 2 步：一张表看 30 天
python3 scripts/run.py by-path --all --yes    # 第 3 步：按路径拆到最细（仍 0 点）
```

`doctor` 实测：`✓` 我的任务 1389 条 · 全量任务 27218 条 · 余额可用（冻结 0）· 用量 175,243.26 点 ·
总账 175,243.26 点 · 流水 7,692 条 · 充值 4 档 rate=100 · **三方口径一致，最大差 0.00 点**。

## 常用命令

```bash
python3 scripts/run.py overview --days 7   # 只看最近 7 天
python3 scripts/run.py by-path --pages 8   # 只扫 160 条，快
python3 scripts/run.py logs --limit 30     # 最近 30 条流水
python3 scripts/run.py balance             # 余额 / 冻结 / 充值档位
```

## 充值的性价比（实测 `/api/v1/recharge/packages`）：**9.9 元体验档含 10 点赠送，折 102.02 点/元，四档里最划算**

| 档位 | 价格 | 点数 | 赠送 | 实际点/元 |
|---|---|---|---|---|
| 体验 | ¥9.90 | 1,000 | 10 | **102.02** |
| 推荐 | ¥100.00 | 10,000 | 0 | 100.00 |
| 热门 | ¥498.00 | 50,000 | 200 | 100.80 |
| 超值 | ¥998.00 | 100,000 | 200 | 100.40 |

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--days` | 30 | 统计窗口（`overview` / `by-path` 对账用） |
| `--pages` | 5 / 25 | 翻几页任务台账（每页固定 20 条） |
| `--all` | — | 翻完全部 1389 条（约 70 个请求，要 `--yes`，**仍然 0 点**） |
| `--status` | — | `tasks` 状态筛选：`completed` / `failed` / `cancelled` |
| `--limit` | 20 | `logs` 取最近多少条，上限 1000 |
| `--budget` | 50 | 点数上限（**单位：点**，1 元 = 100 点）；给 0 直接退 5 |
| `--dry-run` | — | 只打印将要发出的请求，一个都不发 |

## 退出码与 `--json`

`0` 成功 · `2` 用法错 · `4` 需要确认（批量扫描缺 `--yes`）· `5` 预算不足（`--budget 0`，一个请求都不发）· `6` 调用失败（HTTP 非 200 / 网络断开，已自动重试 3 次）· `1` 内部错误 · `130` 被 Ctrl-C 中断。

成功 `{"ok": true, "days": 30, "tasksScanned": 1389, "pathCount": 32, "paths": [...], "spendInTable": 128009.03, "authoritativeNet": 175243.26, "coveragePct": 73.0, "estimatedPoints": 0}`；失败 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`。`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

## 文件结构

`sanjianke-billing/` = `SKILL.md` · `README.md` · `LICENSE.md` · `references/`（`api-contract.md` 7 个端点实测原文、`troubleshooting.md` 按现象找原因）· `scripts/`（`a7w.py` 零依赖客户端、`run.py` 本包命令层，只发 GET）。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
