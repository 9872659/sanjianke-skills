# 排错：按报错找原因

## 一、跑不起来的

### `失败：没有 API Key。三选一：...`（exit 2）

Key 没给到。三条路任选一条：

```bash
python3 scripts/a7w.py login --key sk-你的key     # 存到 ~/.a7w/config.json
export A7W_API_KEY=sk-你的key                     # Linux / macOS
$env:A7W_API_KEY="sk-你的key"                     # Windows PowerShell
```

### `run.py: error: unrecognized arguments: --js`（exit 2）

本包父子 parser 都开了 `allow_abbrev=False`，选项写全：`--json` 而不是 `--js`，
`--budget` 而不是 `--bud`。

### `失败：--budget 是 0 点`（exit 5）

`--budget 0` 等于「不授权任何调用」。本包每个请求 0 点，给 `--budget 1` 就放行。

### `失败：本次要连发 N 个只读 GET（花费 0 点，不会扣款）`（exit 4）

一次请求数 ≥ 30（典型是 `--all` 翻 70 页台账）。加 `--yes` 确认即可，**仍然是 0 点**。

---

## 二、数据看着不对的

### 模型层那一列全是基线值，不是我账号的价

`app-vs-model` 的模型层价来自 `/api/v1/me/tasks`。你的账号还没跑过模型层任务时，
本包回落到团队实测基线（2026-11-07），输出末尾会写「团队实测基线」。

跑过之后自动切 live。想确认读到了什么：

```bash
python3 scripts/run.py app-vs-model --json | python3 -m json.tool | grep modelSource
```

`modelSource` 是 `live` 就是你账号的真实成交价，是 `baseline` 就是回落了。

### 模型层价看着特别高（比如 3,000 点）

模型层是**按次浮动**的：同一条 `seedance` 流水里既有 762.30，也有 3,000 和 3,045.71
（分辨率 / 时长不同）。本包默认取 `--stat min` = 实测最低那一笔，
所以显示 762.30。想看区间：

```bash
python3 scripts/run.py app-vs-model --json | python3 -m json.tool | grep -A1 modelSpan
```

或者换统计口径：

```bash
python3 scripts/run.py app-vs-model --stat median
python3 scripts/run.py app-vs-model --stat max
```

### `cheapest` 里一条模型层的路都没有

默认只排「价目表里直接查得到」的路。加 `--live`：

```bash
python3 scripts/run.py cheapest --for video --live
```

### 语音 TTS 显示「动态计价」，没有具体价

并给出实测区间（本账号 111 条 `tts_async` 实扣 1~240 点，多数 1~66 点）。

---

## 三、价目表里查不到单价，是不是 bug

不是。模型层四条路径（`/videos`、`/videos/generations`、`/images/generations`、`/tasks`）
里三条没有专属规则，命中通配 `*`：

```json
```

所以单价不可能是固定值 —— 只能事后从 `/api/v1/me/tasks` 的 `actualPrice` 反推。
这正是本包存在的理由。

---

## 四、`/api/v1/pricing` 里的 `modelRates` 是不是模型层价目

不是。它只出现在 3 条 `image_human` 规则上，含义是「按请求体里的 `mode` 参数取费率」：

```json
"rateFrom": "mode", "defaultModel": "fast",
"modelRates": {"fast":{"*":10}, "standard":{"*":15}, "2k":{"*":30}, "4k":{"*":60}}
```

配合 `defaultModel` 使用，属于应用层内部的分档。全表**没有** `modelPricing` 键，
也没有「模型 code → 单价」的映射。

用 `doctor` 每次都能验到这一点：

```
√ 模型层单价不在价目表里   3 / 4 条模型层路径没有专属规则；modelRates 只出现在 3 条规则上（image_human）
```

---

## 五、价目表上写着价、跑起来不对的

### `tsc_*` 档位返回 404

11 个 `tsc_*` 档位（`tsc_common` / `tsc_common_hd` / `tsc_aigc` / `tsc_aigc_hd` /
`tsc_shortplay` / `tsc_shortplay_hd` / `tsc_uhd` / `tsc_oldsd` / `tsc_oldsd_hd` /
`tsc_teshd` / `tsc_quality`）在 `pricing` 里都写着 2~6 点/秒、保底 10 点，
但路由没有注册，`GET` / `POST` 都是 404。`traps` 会把这 11 条按现查结果列出来。

### `tencent1080` / `tencent2k` / `tencent4k` 返回 502 `InvalidMpsUser`

路由在，上游腾讯云 MPS 的凭据坏了。本账号跑过的腾讯 4K 任务全部 `status: refunded`，
`chargedPoints: 0`，钱没扣，但活儿也没干成。`traps` 会标出来，
`cheapest --for upscale` 也会提示「能跑通的最便宜档是 VIAPI 超分·标准 9 点/秒」。

### 按 note 算成一次，账单却是秒数

`/video/shot`（20）、`/video/castcrew`（25）、`/video/delogo`（25）以及它们的
`/video/viapi/*` 版共 6 条规则，`note` 写「点/次」，`mode` 却是 `per_second`。
10 秒素材按 200 / 250 / 250 点扣，不是 20 / 25 / 25。

---

## 六、想自己复核本包的结论

```bash
# 1. 三个端点都通、价目表 115 条、模型层价目确实不在表里
python3 scripts/run.py doctor

# 2. 五个陷阱逐条现查
python3 scripts/run.py traps

# 3. 差价排行（含每行的实测区间与来源）
python3 scripts/run.py app-vs-model --json

# 4. 直接看原始价目表（本包不做任何改写）
curl -s -H "Authorization: Bearer $A7W_API_KEY" https://api.a7w.cn/api/v1/pricing
```

本包对 `/api/v1/pricing` 只做两件事：按路径取规则、把 `mode` 换算成一次的点数。
`note` 原文一字不改地透传在 `--json` 里。
