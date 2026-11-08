# 模型层定价方法 · 从 actualPrice 反推真实单价

这份文档解释：为什么 4 个超分模型在价目表里查不到单价，以及本包怎么在不花钱的前提下
给出一个可用的报价。

---

## 1. 价目表里没有模型层

`GET /api/v1/pricing` 返回 115 条规则，覆盖应用层和视频处理线：

```text
/api/v1/video/viapi/superres      per_second  9
/api/v1/video/viapi/superres2k    per_second 15
/api/v1/video/viapi/superres4k    per_second 20
/api/v1/video/tencent1080         per_second  2  minPoints 10
/api/v1/video/tencent2k           per_second  4  minPoints 10
/api/v1/video/tencent4k           per_second  8  minPoints 10
/api/v1/video/upscale             per_second 30
/api/v1/apps/flashvsr/submit      per_second 10  minPoints 20
```

模型层这 4 条路径**没有专属规则**：

```text
/api/v1/videos                     ← 没有
/api/v1/videos/generations         ← 没有
/api/v1/images/generations         ← 没有
/api/v1/tasks                      ← 只有 per_module：带 module_codes[] 时 50 点 x 模块数
```

它们命中通配键 `*`：

```json
{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
 "note":"未单独定价的接口：对外 = 上游实际点数 x 2，单笔保底 50 点"}
```

翻译成一句话：**模型层对外价 = 上游实际点数 x 2，单笔最低 50 点**。
`x 2` 是加价率，`50` 是保底。具体一个 Topaz 视频任务上游收多少点，价目表不写。

---

## 2. 为什么不能拿 /api/v1/models 的 pricing 当单价

`/api/v1/models` 有 316 条，其中 221 条目录模型、95 条裸模型 ID。

- 裸模型 ID 只有 `id / object / owned_by / created`，没有价格字段。
- 221 条目录模型里，92 条带 `pricing`，**全部是文本模型**，结构是
  `pricing_v2.items[0].price.points`，单位「每百万 token」。
- 4 个超分模型（topaz-video-upscale、topaz-image-upscale、recraft-crisp-upscale、
  grok-imagine-upscale）都**没有** `pricing` 字段。

所以「模型目录里的 pricing」不是模型层超分的价目表，不能拿来算钱。

---

## 3. 唯一可靠来源：自己的任务台账

`GET /api/v1/me/tasks?limit=2000&page=N` 每条任务带：

```json
{"taskId":"task_xxx","model":"muse-video","path":"/api/v1/videos",
 "status":"completed","reservePrice":55,"actualPrice":55,
 "refund":null,"chargedPoints":0,"refundedPoints":0,"netPoints":0,
 "rateNote":"官方价 x 2.00（约 +100%）"}
```

关键字段：

| 字段 | 含义 | 怎么用 |
|---|---|---|
| `model` | 模型 code | 按它归集 |
| `path` | 实际调用路径 | 排除 `/apps/` 应用层 |
| `actualPrice` | 标价（点） | 取最低 / 中位 / 最高 |
| `reservePrice` | 预冻结（点） | 只是估算，和 final 可能不同 |
| `refundedPoints` | 已退（点） | 失败任务看这里 |
| `netPoints` | 净额（点） | 真实花费看这个 |
| `rateNote` | 计费说明 | 常见「官方价 x 2.00」 |

### 归集算法（本包 `layer_prices()` 的实现）

```python
agg = {}
for page in range(1, pages + 1):
    d = GET("/api/v1/me/tasks?limit=2000&page=%d" % page)
    for t in d["tasks"]:
        path  = t.get("path") or ""
        model = (t.get("model") or "").strip()
        if not model or "/apps/" in path:     # 应用层不是模型层
            continue
        v = float(t.get("actualPrice") or 0)
        if v <= 0:                             # 失败 / 0 点任务跳过
            continue
        agg.setdefault(model, []).append(round(v, 2))
```

每个模型取 `min / median / max`，输出：

```json
{"model":"muse-video","route":"/api/v1/videos",
 "low":44.0,"high":260.0,"n":6,
 "samples":[44.0,44.0,55.0,55.0,55.0,260.0]}
```

### 本账号的真实样本（2026-11-07，500 条任务）

| model | route | 最低 | 最高 | 条数 |
|---|---|---|---|---|
| `sd/doubao-seedance-2-0-260128` | `/api/v1/videos/generations` | 145.73 | 3,000 | 5 |
| `volcengine/doubao-seedance-2-5-260628` | `/api/v1/videos/generations` | 762.30 | 3,045.71 | 3 |
| `wan3.0-video` | `/api/v1/videos/generations` | 300 | 300 | 2 |
| `muse-video` | `/api/v1/videos` | 44 | 260 | 6 |
| `gpt-image-2-pro` | `/api/v1/tasks` | 39 | 104 | 17 |
| `gpt-image-2` | `/api/v1/tasks` | 26 | 26 | 1 |
| `seedream-5-0-flash` | `/api/v1/tasks` | 15.60 | 15.60 | 1 |

这张表只说明「模型层价格怎么分布」，**不是超分模型的价**。

### 超分模型的样本：0 条

2026-11-08 全量扫描 1,398 条任务，14 条超分相关：

```text
flashvsr          2 条  settled   actualPrice 72.348 / 288.312
tencent4k         3 条  refunded  actualPrice 120 / 120 / 48（全退）
viapi/superres    2 条  refunded  actualPrice 18（净 0）
video/upscale     7 条  refunded  actualPrice 60 / 150（净 0）
topaz / recraft / grok / topaz-image   0 条
```

所以本包对 4 个模型层超分模型只能给 `source=baseline`。

---

## 4. 基线的定义（不编单价）

`MODEL_BASELINE` 只写「通配保底 50 点起」和「上游 x 2」，不写一个看起来很精确的数字：

```python
MODEL_BASELINE = {
  "topaz-video-upscale":  {"low": 50.0, "high": None, "n": 0,
                           "route": "/api/v1/videos"},
  "topaz-image-upscale":  {"low": 50.0, "high": None, "n": 0,
                           "route": "/api/v1/images/generations"},
  "recraft-crisp-upscale":{"low": 50.0, "high": None, "n": 0,
                           "route": "/api/v1/images/generations"},
  "grok-imagine-upscale": {"low": 50.0, "high": None, "n": 0,
                           "route": "/api/v1/videos"},
}
```

`low=50` 来自 `/api/v1/pricing` 的通配 `minPoints: 50`，不是猜的。
`high=None` 表示上限取决于上游实际点数，价目表没有封顶。

输出里会标：

```json
{"tier":"recraft-crisp-upscale","points":50,"source":"baseline",
 "span":"50 点起","note":"通配保底 50 点/次起"}
```

一旦你的账号跑过一单，`source` 自动切成 `live`，`span` 变成真实区间。

---

## 5. 为什么不做「按秒折算」

三条按秒线有明确的 `perSecond`，可以直接算 60 秒 / 600 秒。
模型层是 `per_call` + 上游动态价，硬折成「点/秒」会造出一个不存在的单价：

```text
错误示范：50 点 / 60 秒 = 0.83 点/秒   ← 没有任何依据
```

本包的做法：

- `cost` 里模型层 5 列都写 50，明确标注「按次保底，不是时长价」。
- `compare` 把模型层和按秒线并列展示，但结论里写「口径不同，不做大小比较」。
- `models` 横评只在模型层内部排序（都 50 时按可用状态排）。

---

## 6. 一次真实成交后怎么读

```bash
# 1) 跑一单（示例：Recraft 图像放大，要 --yes）
python3 scripts/run.py submit --tier recraft-crisp-upscale \
  --image-url "https://oss.gpu.likeadmin.cn/openapi/..." --yes

# 2) 查任务
python3 scripts/run.py status --task-id task_xxx --tier recraft-crisp-upscale

# 3) 看模型层真实价
python3 scripts/run.py models --pages 20
```

第 3 步会输出：

```text
recraft-crisp-upscale   /images/generations   72.00   live   ≈ 待验证
```

`source=live`、`span=72.00`，这就是你账号的真实成交价。
多个样本时取最低 / 中位 / 最高，`--stat` 由命令内部按最低价展示。

---

## 7. 三条硬规则

1. **价目表没有的单价，不从别处抄。** 不从文档、不从经验值、不从别的模型类推。
2. **没有成交样本就标 baseline。** 只报通配保底 50 点，并写明「未成交」。
3. **真实花费看 `netPoints`，不看 `actualPrice`。** 失败任务 `actualPrice` 可能非 0，
   但 `refundedPoints` 会把它退掉，`netPoints` 才是净支出。
