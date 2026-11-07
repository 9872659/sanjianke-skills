# 对账台 · 我的钱花在哪一查就清

**账户少了 300 块，钱花在哪？** 7 个只读 GET，6 条命令，把 [api.a7w.cn](https://api.a7w.cn/) 的账摊成表 —— **扣 0 点**。

实测（2026-11-07，30 天窗口）：调用 **7,990 次**，花掉 **425,674.83 点**，退回 **250,431.57 点**，
**净花 175,243.26 点（¥1,752.43）**，日均 **5,841.44 点**。

---

## 三个别人不会告诉你的口径

### 一、`byPath` 只回一个桶，所以「按路径」得自己算

拉 1 天、7 天、30 天、90 天、365 天，`/user/usage` 的 `byPath` **都只有一个键**：

```json
{"days":30,"calls":7891,"chargedPoints":420306.1845,"refundedPoints":247322.9668,
 "netPoints":172983.2177,"yuan":1729.83,
 "byPath":{"(任务冻结/结算)":420306.1851}}
```

`(任务冻结/结算)` 是一个中文标签，不是 URL 路径。想要「按路径看钱花在哪」，
只能翻 `/api/v1/me/tasks` 的 `path` 字段自己归集 —— 本包的 `by-path` 就干这个，
外加一张 32 条路径的中文翻译表。

### 二、`refunded` 不等于没花钱，`netPoints` 也不等于标价

实测一个任务：

```json
{"actualPrice":72,"refund":122,"chargedPoints":72,"refundedPoints":72,"netPoints":0}
```

- **真扣** = `netPoints`（0）
- **标价 / 预留** = `actualPrice`（72）
- **`refund`**（122）= 流水里所有 refund 类型之和，连别的任务同步过来的退款也算，**会偏大**

全量实测：标价合计 **1,614,557 点**，真扣只有 **104,785 点** —— 差 15 倍。

### 三、流水页的 `netPoints` 是流水口径，`balanceMoving` 才是真净

```
logs.netPoints      = -404,408.72   ← 预扣 -60、退款 +60 来回都算，翻了一倍
logs.balanceMoving  = -175,243.26   ← 真实净变动
```

而 `usage.netPoints` = `billing.netConsumedPoints` = `logs.balanceMoving` 三方永远该相等，
`doctor` 每次都会验，实测差 **0.00 点**。

---

## 一张表：30 天的钱去哪了

| 口径 | 点数 | 折合 | 说明 |
|---|---|---|---|
| 调用次数 | **7,990 次** | — | 含成功与失败 |
| 花掉 `chargedPoints` | **425,674.83** | ¥4,256.75 | 预扣口径，看着最吓人 |
| 退回 `refundedPoints` | **250,431.57** | ¥2,504.32 | 失败 / 少算的自动退回 |
| 净花 `netPoints` | **175,243.26** | ¥1,752.43 | **这才是真花** |
| 日均 | **5,841.44** | ¥58.41 | 净花 ÷ 30 |

按路径拆开（全量 1389 条任务、32 个真实路径、覆盖权威净花 **73.0%**）：

| # | 路径（人话） | 次数 | 净花 | 占比 |
|---|---|---|---|---|
| 1 | 图片对口型（照片开口说话） | 120 | 54,907.01 | 42.89% |
| 2 | 图片数字人（照片生成数字人） | 14 | 35,532.00 | 27.76% |
| 3 | 真人播报（数字人口播成片） | 163 | 27,943.42 | 21.83% |
| 4 | 语音合成·长文本（异步） | 125 | 3,130.00 | 2.45% |
| 5 | nano-banana 出图 | 165 | 2,376.00 | 1.86% |

---

## 路径翻译表

本包把实测出现过的 32 个接口路径全翻成了人话，下面是最常用的 25 条：

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
| `/api/v1/viapi/superres` 同族 | 视频超分·标准 / 视频上色 |
| `/api/v1/tasks` | 通用任务入口（文生图 / 图片编辑） |
| `/v1/videos` | 视频任务（少了 `/api` 前缀，网关照样记账） |

没收录的路径按前缀兜底（`/api/v1/apps/<名字>` → 「应用 · 名字」）。

---

## 失败任务对账

`python3 scripts/run.py tasks --status failed --pages 2`

```
任务台账 · 本次 100 条（全账 3,397 条） · status=failed
  2026-11-07T12:06:31Z  flashvsr/submit     failed  0.00  app  task_d774cfb6a85804c745b9f123
  2026-11-07T11:44:47Z  nano_banana/submit  failed  0.00  app  task_48f826dcb5f289aed76d0236
  未完成（status≠completed）100 条，合计 0.00 点 —— 失败任务 actual_points 恒为 0.00，钱没扣。
```

**3397 条失败，合计 0.00 点。** 失败不扣钱，账面上「少了」的那些都在成功任务里。

---

## 六条命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `overview` | 0 点 | 30 天总览：花了 / 退了 / 净花 / 日均 / 余额 / Top5 路径 |
| `by-path` | 0 点 | 按路径分组排序 + 中文翻译 + 占比 + 覆盖率 |
| `tasks` | 0 点 | 任务台账，`--status failed` 逐条对账 |
| `logs` | 0 点 | 流水明细：中文类型 / 点数 / 路径 / 余额 |
| `balance` | 0 点 | 余额 / 冻结 / 折合元 / 充值档位性价比 |
| `doctor` | 0 点 | 自检 7 个只读端点 + 三方口径一致性 |

---

## 三步上手

```bash
# 第 1 步：自检（免费，7 个端点 + 三方口径）
python3 scripts/run.py doctor

# 第 2 步：一张表看 30 天
python3 scripts/run.py overview

# 第 3 步：按路径拆到最细（全量 1389 条，仍然 0 点）
python3 scripts/run.py by-path --all --yes
```

```
✓ 我的任务 1389 条   ✓ 全量任务 27218 条   ✓ 余额 可用 / 冻结 0
✓ 用量 175,243.26 点  ✓ 总账 175,243.26 点  ✓ 流水 7,692 条   ✓ 充值 4 档·rate=100
✓ 三方口径一致（usage = billing = 流水）  最大差 0.00 点
```

---

## 零依赖、零花费

- **零依赖**：只要 Python 3.7+，不装任何第三方包。
- **零花费**：`run.py` 里只有 `GET`，没有任何 `POST` / `PUT` / `DELETE`，网关侧扣 0 点。
- **两道闸门**：`--budget 0` 直接退 `5`，一个请求都不发；`--all` 这类批量扫描要 `--yes`，确认信息里写明「花费 0 点」。
- **Key 三选一**：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。

---

## 充值的性价比（实测 `/api/v1/recharge/packages`）

| 档位 | 价格 | 点数 | 赠送 | 实际点/元 |
|---|---|---|---|---|
| 体验 | ¥9.90 | 1,000 | 10 | **102.02** |
| 推荐 | ¥100.00 | 10,000 | 0 | 100.00 |
| 热门 | ¥498.00 | 50,000 | 200 | 100.80 |
| 超值 | ¥998.00 | 100,000 | 200 | 100.40 |

**9.9 元体验档含 10 点赠送，折 102.02 点/元，是四档里最划算的。**

---

## 目录结构

```
sanjianke-billing/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       7 个端点实测原文与字段表
│   └── troubleshooting.md    排错：按现象找原因
└── scripts/
    ├── a7w.py                零依赖客户端（家族逐字节一致）
    └── run.py                本包命令层（只发 GET）
```

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
