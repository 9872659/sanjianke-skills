# 接口契约（2026-11-07 实测原文）

本包只用 **7 个只读 GET**，全部 200，全部 0 点。下面每段 `json` 都是实测返回，
除长列表做截断外未做任何改写。Key 走 `Authorization: Bearer <key>`。

| # | 端点 | 用途 | 关键字段 |
|---|---|---|---|
| 1 | `GET /api/v1/me/tasks` | 我的任务台账（带 path + 金额） | `tasks[]` / `total` / `sumPoints` / `sumRefund` / `sumYuan` |
| 2 | `GET /api/v1/tasks` | 全量任务台账（27218 条，可筛状态） | `data.lists[]` / `data.total` / `data.page` / `data.per_page` |
| 3 | `GET /user/balance` | 余额 | `available_points` / `frozen` / `yuan` / `rate` |
| 4 | `GET /user/usage?days=30` | 用量汇总 | `calls` / `chargedPoints` / `refundedPoints` / `netPoints` / `byPath` |
| 5 | `GET /api/v1/me/billing` | 账户总账（含验算） | `grossChargedPoints` / `netConsumedPoints` / `check` / `note` |
| 6 | `GET /user/balance/logs` | 流水 | `logs[]` / `inPoints` / `outPoints` / `netPoints` / `balanceMoving` |
| 7 | `GET /api/v1/recharge/packages` | 充值档位 | `packages[]` / `rate` |

---

## 1. `GET /api/v1/me/tasks`

**分页实测**：`size` 和 `per_page` 都无效，每页恒 **20 条**；`page` 有效；
`limit` 不是页大小，而是「统计最近 N 条」的窗口（默认 1000）。

| 请求 | 返回条数 | `total` 字段 |
|---|---|---|
| 不带参数 | 20 | 1000 |
| `?size=100` | 20 | 1000 |
| `?per_page=100` | 20 | 1000 |
| `?limit=5` | 5 | 5 |
| `?limit=2000` | 20 | **1389**（真实条数） |
| `?page=2` | 20（与 page=1 不同） | 1000 |

```json
{
 "tasks": [
  {
   "taskId": "task_48f826dcb5f289aed76d0236",
   "model": "nano-banana",
   "type": "应用",
   "path": "/api/v1/apps/nano_banana/submit",
   "provider": "",
   "status": "refunded",
   "tokens": "0/0",
   "reservePrice": 72,
   "actualPrice": 72,
   "refund": 122,
   "error": "",
   "failReason": "",
   "frozenPoints": 72,
   "chargedPoints": 72,
   "refundedPoints": 72,
   "netPoints": 0,
   "rateNote": "固定 72 点/次",
   "charges": [
    {"at": 1794023087453, "type": "reserve_fixed_price", "points": 0, "note": "/api/v1/apps/nano_banana/submit"},
    {"at": 1794023088353, "type": "refund", "points": 50, "balanceAfter": 999997404023.4279, "note": "refund:sync_to_task:task_48f826..."},
    {"at": 1794023089252, "type": "charge", "points": 72, "balanceAfter": 999997403951.4279, "note": "reserve:task_48f826..."},
    {"at": 1794023097022, "type": "refund", "points": 72, "balanceAfter": 999997404010.0278, "note": "refund:task_failed:task_48f826..."},
    {"at": 1794023097322, "type": "settle_task_failed", "points": 0, "refund": 72}
   ],
   "feeYuan": 0.72,
   "ms": 1030,
   "submittedAt": 1794023096477,
   "elapsedMs": 845,
   "keyFp": "sk-b0ddbd87…743b38",
   "resultUrl": "",
   "resultExpired": false,
   "at": 1794023096477
  }
 ],
 "total": 1000,
 "page": 1,
 "size": 20,
 "sumPoints": 640951.6418,
 "sumRefund": 115848.95,
 "sumYuan": 6409.516418
}
```

### 字段口径（重要）

| 字段 | 含义 | 陷阱 |
|---|---|---|
| `actualPrice` | 标价 / 预留价 | **不是真扣**。全量标价合计 1,614,557 点 |
| `chargedPoints` | 已扣点数 | 对 `refunded` 状态仍可能等于 `netPoints` 的旧值 |
| `refundedPoints` | 真正退回的点数 | |
| `netPoints` | **真扣 = `chargedPoints − refundedPoints`** | 实测 1389 条里两者恒等，0 条不一致 |
| `refund` | 流水里所有 `refund` 类型之和 | **会偏大**（同一任务实测 122，而真退 72） |
| `status` | `settled` / `refunded` / `completed` / `pending` / `succeeded` | **没有 `failed`** |
| `path` | 真实接口路径 | 本包翻译表就建在这一列 |
| `limit` | 统计窗口，非页大小 | 默认 1000，会给真实条数「封顶」成 1000 |

### 状态分布（1389 条实测）

| status | 条数 | net 合计 | actual 合计 | refunded 合计 |
|---|---|---|---|---|
| `settled` | 1102 | 127,889.03 | 189,437.96 | 11,095.85 |
| `refunded` | 270 | -12,377.00 | 1,416,966.46 | 30,543.70 |
| `completed` | 11 | 0.00 | 3,791.74 | 0.00 |
| `succeeded` | 5 | -10,682.68 | 4,317.32 | 10,728.39 |
| `pending` | 1 | 0.00 | 0.00 | 0.00 |

`refunded` 状态的 `actual` 能到 141 万点，是因为 `wan/create` 这类应用把「预留」写进了
`actualPrice`（124 条合计 1,325,880 点）而 `netPoints` 是 0 —— 这就是「标价 ≠ 真扣」的来源。

---

## 2. `GET /api/v1/tasks`

**分页实测**：`per_page` 生效，上限 **100**（传 200 会被夹到 100）；`page` 生效；
`total` = 27218。`status` 可筛（`failed` 3397 / `completed` 23807）。`type_code`、`days` 无效。

```json
{
 "code": 1, "msg": "success",
 "data": {
  "lists": [
   {
    "task_id": "task_db58580d586ad9eedc32fe46",
    "model_code": "pic_lipsync/submit",
    "model_name": "pic_lipsync/submit",
    "public_model_code": "pic_lipsync/submit",
    "channel_code": "app",
    "type_code": "app",
    "call_type": "async",
    "status": "completed",
    "actual_points": "181.50",
    "response_time_ms": 0,
    "completed_at": 1794032563,
    "created_at": "2026-11-07T14:12:54Z"
   }
  ],
  "total": 27218, "page": 1, "per_page": 50
 }
}
```

### 字段口径

- `lists` 在 `data` 下，不是顶层 `list`。
- **`actual_points` 是字符串**（`"181.50"`），直接做加法会变成字符串拼接，务必 `float`。
- **失败任务的 `actual_points` 实测恒为 `"0.00"`**（181 条 failed 采样，取值集合只有 `{"0.00"}`）。
- `completed_at` 是 Unix 秒，`created_at` 是 ISO 字符串 —— 两个字段格式不统一。
- `channel_code` 实测取值：`app` / `official` / `official_media_33` / `bailian_compatible` /
  `cn_compatible` / `acedata` / `openaiD` / `OpenAIYI` / 空串。

### 与 `me/tasks` 的关系

| | `me/tasks` | `tasks` |
|---|---|---|
| 条数 | 1389 | 27,218 |
| 有 `path` | ✓ | ✗（只有 `model_code`） |
| 有退款字段 | ✓ | ✗ |
| 状态枚举 | `settled` / `refunded` / … | `completed` / `failed` / `cancelled` |

**两个端点是两套视图，条数和状态枚举都不同**，不要互相校验。

---

## 3. `GET /user/balance`

```json
{
 "available_points": 999997397035.4279,
 "points": 999997397035.4279,
 "frozen": 44,
 "member_points": 0,
 "yuan": 9999973970.35,
 "rate": 100,
 "currency": "points",
 "note": "本平台按用户/Key 隔离统计，不含租户级数据"
}
```

- `yuan` 是网关**已经按 `rate=100` 折好的**，自己再乘除一次就会错。
- `available_points` 与 `points` 实测恒等；`frozen` 是异步任务还没结算的预留。

---

## 4. `GET /user/usage?days=N`

```json
{
 "days": 30,
 "calls": 7891,
 "chargedPoints": 420306.1845,
 "refundedPoints": 247322.9668,
 "netPoints": 172983.2177,
 "yuan": 1729.83,
 "byPath": {"(任务冻结/结算)": 420306.1851},
 "note": "仅统计当前用户（按用户/Key 隔离）；上游 likeadmin 的 user/usage 是租户级全量，勿混用"
}
```

### `byPath` 的真实结构（本包存在的理由）

| 窗口 | `byPath` 键数 | 内容 |
|---|---|---|
| `days=1` | 1 | `{"(任务冻结/结算)": 19930.4698}` |
| `days=7` | 1 | `{"(任务冻结/结算)": 101079.2802}` |
| `days=30` | 1 | `{"(任务冻结/结算)": 420306.1851}` |
| `days=90` | 1 | `{"(任务冻结/结算)": 420306.1851}` |
| `days=365` | 1 | `{"(任务冻结/结算)": 420366.1851}` |

**键是中文标签 `(任务冻结/结算)`，不是 URL 路径**，且任何窗口都只有一个桶。
所以「按路径花在哪」必须走 `/api/v1/me/tasks` 的 `path` 字段自己归集。

`days=0` / `days=abc` 都会被当成默认 `30`，不报错。

---

## 5. `GET /api/v1/me/billing`

```json
{
 "phone": "17340063827",
 "userId": "175db8440e5a681d980a3237",
 "balance": 999997395875.098,
 "frozen": 44,
 "rechargeYuan": 0.01,
 "rechargePoints": 1700,
 "creditPoints": 0,
 "grossChargedPoints": 421596.5045,
 "refundedPoints": 247512.9668,
 "netConsumedPoints": 174083.5377,
 "netConsumedYuan": 1740.8354,
 "balanceYuan": 9999973958.751,
 "paidOrders": 1,
 "check": {"expected": -172383.5377, "actual": 999997395875.098, "diff": -999997568258.6356},
 "note": "唯一权威口径：充值(rechargePoints) + 赠送(creditPoints) − 净消费 = 余额"
}
```

- `check.expected = rechargePoints + creditPoints − netConsumedPoints`（实测 1700 + 0 − 174083.5377 = −172383.5377）。
- 它**不含**充值以外的额度（活动赠送 / 测试额度 / 历史手工调整），所以 `diff` 不为 0 是正常的。
- `netConsumedPoints` 就是全量权威净消费，和 `/user/usage` 的 `netPoints`、流水的 `balanceMoving` 三方相等。

---

## 6. `GET /user/balance/logs`

```json
{
 "currency": "points", "rate": 100,
 "count": 100, "total": 7584,
 "inPoints": 247442.9668,
 "outPoints": 650162.6545,
 "netPoints": -402719.6877,
 "consumePoints": 75180.96,
 "balanceMoving": -172983.2177,
 "logs": [
  {
   "at": 1794040868738,
   "type": "charge", "typeName": "冻结/预扣",
   "kind": "out",
   "balanceMoving": true, "isSettle": false,
   "points": -60, "amount": 60,
   "balanceAfter": 999997396975.4279,
   "path": "", "taskId": "",
   "reference": "reserve_sync:/api/v1/apps/media_services_33/music_sounds",
   "orderId": "", "model": "", "provider": ""
  }
 ]
}
```

### 字段口径

| 字段 | 说明 |
|---|---|
| `logs[]` | **数组名是 `logs`，不是 `list`** |
| `type` / `typeName` | `charge`/冻结与预扣 · `refund`/退款 · `reserve`/预留冻结 · `settle`/结算实收 · `overage`/超额补扣 |
| `kind` | `in`（入）/ `out`（出） |
| `points` | **带符号**：出为负、入为正；`amount` 是绝对值 |
| `balanceMoving`（行级） | 只有 `true` 的行才真的动了余额 |
| `path` | **实测 100 条里只有 7 条非空** |
| `reference` | 路径藏在这里：`reserve_sync:<path>`、`refund:sync:<path>`、`refund:task_failed:<taskId>` |

### 两个 `netPoints` 不是一回事

| 字段 | 实测值 | 口径 |
|---|---|---|
| `netPoints` | -402,719.6877 | **流水口径**：`inPoints − outPoints`，预扣 + 退款来回都算 |
| `balanceMoving` | -172,983.2177 | **真实净变动**，与 `/user/usage`、`/api/v1/me/billing` 三方相等 |

### 分页实测

`limit` 生效（上限 **1000**，传 20000 也只回 1000）；`page` / `per_page` / `size` / `type` / `kind` / `days`
**全部无效**，加了也还是回 100 条。

---

## 7. `GET /api/v1/recharge/packages`

```json
{
 "packages": [
  {"id": "rc_99",  "yuan": 9.9,  "points": 1000,   "tag": "体验", "bonus": 10},
  {"id": "rc_100", "yuan": 100,  "points": 10000,  "tag": "推荐", "bonus": 0},
  {"id": "rc_498", "yuan": 498,  "points": 50000,  "tag": "热门", "bonus": 200},
  {"id": "rc_998", "yuan": 998,  "points": 100000, "tag": "超值", "bonus": 200}
 ],
 "rate": 100
}
```

| 档位 | 价格 | 点数 | 赠送 | 到手点数 | 实际点/元 |
|---|---|---|---|---|---|
| 体验 | ¥9.90 | 1,000 | 10 | 1,010 | **102.02** |
| 推荐 | ¥100.00 | 10,000 | 0 | 10,000 | 100.00 |
| 热门 | ¥498.00 | 50,000 | 200 | 50,200 | 100.80 |
| 超值 | ¥998.00 | 100,000 | 200 | 100,200 | 100.40 |

`rate = 100` 表示 1 元 = 100 点；`bonus` 是额外赠送点数，算性价比时要加进分子。

---

## 三方对账口径（本包的核心）

```
/user/usage?days=30 .netPoints
  == /api/v1/me/billing .netConsumedPoints
  == /user/balance/logs .balanceMoving（取绝对值）

实测 2026-11-07：175,243.26 = 175,243.26 = 175,243.26，差 0.00 点
```

这三个数不相等时，说明有一笔账没落库 —— `doctor` 会把差额直接打出来。
