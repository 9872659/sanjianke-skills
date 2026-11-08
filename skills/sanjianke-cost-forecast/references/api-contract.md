# 接口契约（2026-11-08 实测原文）

本包只读四个端点，全部 `GET`，全部 0 点。源码里没有 POST / PUT / DELETE。

| 端点 | 返回 | 用途 |
|---|---|---|
| `GET /api/v1/models` | `{object, code, msg, data[316]}` | 模型目录 + 模型层 ID |
| `GET /api/v1/apps` | `{code, msg, data[22]}` | 应用目录 + 接口清单 |
| `GET /api/v1/me/tasks?limit=2000&page=N` | `{tasks[20/页], total, sumPoints, ...}` | 模型层真实成交价 |
| `GET /api/v1/tasks/<id>` | 假 id → `200 {"code":0,"msg":"任务不存在"}` | 路由存在性判据 |
| `GET /user/balance` | 余额 | 自检 |
| `GET /user/balance/logs?limit=1` | 流水 | 前后比对，证明 0 点 |

---

## 1) `GET /api/v1/pricing`

**顶层是裸对象，不套 `code/data`。** 五个键：

```json
{
 "currency": "points",
 "site": "api",
 "pricing": { "/api/v1/...": { ...规则... }, ... }
}
```

`pricing` 共 **115 条**。键是路径：精确路径、`/apps/x/*` 通配尾、或顶层 `*`。

### 规则字段（115 条里出现过的全部字段）

| 字段 | 次数 | 类型 | 含义 |
|---|---|---|---|
| `mode` | 115 | str | `flat` / `per_second` / `per_module` |
| `note` | 115 | str | 人写的中文说明 |
| `cost` | 65 | int | `flat` 的一口价（点） |
| `perSecond` | 46 | int / float | 每秒点数 |
| `minPoints` | 23 | int | 单笔保底 |
| `provider` | 14 | str | `tencent` / `viapi` |
| `definition` | 11 | int | TSC 档位号（321001 / 322002 / 100910 …） |
| `sizeRates` | 4 | dict | 按尺寸分档价 |
| `resolutionRates` | 1 | dict | `full_video` 五档分辨率价 |
| `estimate` | 3 | int | 预冻结额 |
| `rateFrom` | 3 | str | `mode`（按请求体 mode 取费率） |
| `modelRates` | 3 | dict | **按 mode 参数的费率表**，不是模型价目 |
| `defaultModel` | 3 | str | `rateFrom` 的缺省档 |
| `unitFrom` | 1 | str | `module_codes`（`/api/v1/tasks` 按模块数计价） |

### 全局兜底

```json
```

`/api/v1/images/generations`、`/api/v1/images/edits`、`/api/v1/videos/generations`、
`/api/v1/videos`、`/api/v1/chat/completions`、`/api/v1/embeddings` 六条路径在 `pricing`
里**都没有专属键**，全部落这一条。`/api/v1/tasks` 有专属键，但那是 `per_module`。

### 视频档（`per_second`，单位点/秒）

```
restore 36   upscale 30   cartoon 24   interp 25   faceswap 20   shot 20
portrait 18  enhance 15   superres2k 15   superres 9   superres4k 20
colorize 9   subtitle 9   segment 9     castcrew 25   delogo 25
tencent1080 2  tencent2k 4  tencent4k 8      （minPoints 10，provider tencent）
tsc_common 3  tsc_common_hd 6  tsc_aigc 3  tsc_aigc_hd 6  tsc_shortplay 3
tsc_shortplay_hd 6  tsc_uhd 3  tsc_oldsd 3  tsc_oldsd_hd 6  tsc_teshd 2  tsc_quality 2
```

扁平与 viapi 两套同价（`/api/v1/video/restore` 与 `/api/v1/video/viapi/…`），本包按 viapi 报。

### 应用层一口价（节选）

| 路径 | 价（点） |
|---|---|
| `/api/v1/apps/seedance/submit` | 11,000 |
| `/api/v1/apps/wan/submit` | 800 |
| `/api/v1/apps/happy_horse/submit` | 650 |
| `/api/v1/apps/mmaudio/submit` | 495 |
| `/api/v1/apps/grok_video/submit` | 300 |
| `/api/v1/apps/seedsvc/submit` | 220 |
| `/api/v1/apps/aigc_wan_image/generate/index` | 203 |
| `/api/v1/apps/dressing_diffusion/submit` | 200 |
| `/api/v1/apps/aigc_photo_restore/*` | 105 |
| `/api/v1/apps/aigc_qwen_image_pro/generate/index` | 105 |
| `/api/v1/apps/watermark_removal/*` | 100 |
| `/api/v1/apps/aigc_qwen_image/generate/index` | 78 |
| `/api/v1/apps/nano_banana/submit` | 72 |
| `/api/v1/apps/smart_clip/submit` | 45 |
| `/api/v1/apps/music_search/*` | 30 |

### 按上游点数加成的（`cost: 0` + `Percent`）

|---|---|---|---|
| `/api/v1/apps/indextts/*` | 200 | — | 同上 |
| `/api/v1/apps/music_generation/*` | 200 | — | 同上 |
| `/api/v1/apps/lipsync/*` | 200 | 1 | 上游 ×3 |
| `/api/v1/apps/pic_lipsync/submit` | 400 | 50 | 上游 ×5 |
| `/api/v1/apps/person_replacement/*` | 100 | — | 上游 ×2 |
| `/api/v1/apps/action_transfer/*` | 100 | — | 上游 ×2 |

### 两条特殊结构

```json
"/api/v1/apps/full_video/submit": {
  "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80},
  "note": "2026-11-06 站内定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80，1 元=100 点"
}

"/api/v1/apps/image_human/submit": {
  "rateFrom": "mode", "defaultModel": "standard",
  "modelRates": {"fast": {"*": 10}, "standard": {"*": 15},
                 "2k": {"*": 30}, "4k": {"*": 60}},
  "note": "全驱数字人 快速 10 / 标准 15 / 2K 30 / 4K 60 点/输入秒"
}
```

`modelRates` 的含义是「**按请求体里的 `mode` 参数取费率**」，配合 `rateFrom: "mode"` 使用。
全表**没有** `modelPricing` 键，也没有「模型 code → 单价」的映射。

---

## 2) `GET /api/v1/models`

```json
{"object": "list", "code": 1, "msg": "success", "data": [ ...316 条... ]}
```

316 条分两类：

- **221 条目录模型**（带 `model_code`）：类型 `text` 92 / `image` 50 / `video` 47 / `other` 32；
- **95 条裸模型层 ID**（只有 `id` / `object` / `owned_by` / `created`，没有价格字段）。

```json
{"id": "volcengine/doubao-seedance-2-5-260628", "object": "model",
 "owned_by": "flagship", "created": 0}
```

**只有 92 条 `text` 带 `pricing`**，是「每百万 token」的模型层价目：

```json
"pricing": {
  "billing_type": 1,
  "per_1k_input": 500, "per_1k_output": 3000, "fixed_points": 3000,
  "pricing_v2": {
    "billing_mode": "usage",
    "items": [{"sku_key": "gpt_5_5_token", "title": "按百万 Token",
               "usage_unit": "token", "usage_unit_size": 1000000,
               "price": {"points": 3000, "unit": "token"},
               "effective_rate_config": {"input": 500, "cached_input": 50, "output": 3000}}],
    "price_view": {"title": "按用量计费", "summary": "按百万 Token 3000 点/百万 Token"}
  }
}
```

即 `pricing.pricing_v2.items[0].price.points` = 每百万 token 的点数。实测区间：
`claude-fable-5-official` 15,840 最高，`HY-MT2-7B` / `HY-MT1.5-7B` / `Hunyuan-MT-Chimera-7B` 40 最低。

**视频与图片模型的模型层单价，`/pricing` 和 `/models` 都不给** —— 本包从 `/me/tasks` 反推。

---

## 3) `GET /api/v1/apps`

```json
{"code": 1, "msg": "success", "data": [ ...22 个应用... ]}
```

```json
{
 "id": 19, "name": "人物替换", "code": "person_replacement",
 "driver_code": "elastic_gpu", "billing_mode": 1,
 "category_code": "other", "tenant_sort": 80,
 "apis": [{"id": 52, "code": "submit", "name": "提交任务",
           "category_code": "video", "call_type": 2, "method": "POST"}]
}
```

22 个应用合计 **100 个 api**。接口数分布：`media_services_33` 29、`music_generation` 13、
`watermark_removal` 8、`seedance` 7、`voice_tts` 6、`smart_clip` 5，其余多为 1~3 个。

`media_services_33` 的 29 个接口在 `pricing` 里**一条专属规则都没有**，全部落通配兜底。

---

## 4) `GET /api/v1/me/tasks`

```json
{
 "taskId": "task_7257444313a43caac40607bf",
 "model": "voice_tts", "type": "应用",
 "path": "/api/v1/apps/voice_tts/tts_async",
 "status": "refunded",
 "tokensIn": 0, "tokensOut": 0, "tokens": "0/0",
 "reservePrice": 150, "actualPrice": 150, "refund": 300,
 "frozenPoints": 150, "chargedPoints": 150, "refundedPoints": 150, "netPoints": 0,
 "rateNote": "官方价 × 2.00（≈ +100%）",
 "feeYuan": 1.5, "ms": 1573,
 "resultUrl": "", "moduleCount": null, "tool": ""
}
```

分页：`size` / `per_page` 无效，**每页恒 20 条**；`limit` 只影响统计窗口（`limit=2000` 覆盖全部 1,398 条）。

### 实测样本（2026-11-08，200 条任务里按 model 取最低 actualPrice）

| model | path | 最低 actualPrice |
|---|---|---|
| `gpt-image-2.6` | `/api/v1/images/generations` | 6.00（流水 `sync:` 每笔 −6） |
| `seedream-5-0-flash` | `/api/v1/tasks` | 15.60 |
| `gpt-image-2` | `/api/v1/tasks` | 26.00 |
| `gpt-image-2-pro` | `/api/v1/tasks` | 39.00（长样本里出现过 78 / 104） |
| `muse-video` | `/api/v1/videos` | 44.00 |
| `sd/doubao-seedance-2-0-260128` | `/api/v1/videos/generations` | 145.73 |
| `wan3.0-video` | `/api/v1/videos/generations` | 300.00 |
| `volcengine/doubao-seedance-2-5-260628` | `/api/v1/videos/generations` | 762.30 |
| `voice_tts` | `/api/v1/apps/voice_tts/tts_async` | 1.80（封顶 150） |
| `nano_banana` | `/api/v1/apps/nano_banana/submit` | 72.00 |
| `full-video` | `/api/v1/apps/full_video/submit` | 40.00（按秒，30 秒内的小段） |
| `image_human` | `/api/v1/apps/image_human/submit` | 3,279.60 |
| `smart_clip` | `/api/v1/apps/smart_clip/realman_broadcast` | 22.44 |

但 `minPoints: 50` 在模型层实测**没有落地**（15.60 / 26 / 44 点都低于 50）。

---

## 5) 五类陷阱的实测证据

| # | 证据 | 数字 |
|---|---|---|
| ① | `/api/v1/video/tsc_*` 11 条 `per_second`，带 `definition`，路由提交 404 | 2~6 点/秒，保底 10 |
| ② | `/api/v1/video/tencent1080|2k|4k` 路由在，上游 502 `InvalidMpsUser` | 2 / 4 / 8 点/秒，保底 10 |
| ③ | note 写「点/次」而 `mode` 是 `per_second` | 6 条：`shot` 20、`castcrew` 25、`delogo` 25，各扁平 + viapi |
| ⑤ | 应用层 vs 模型层 | Seedance 11,000 vs 145.73 = 75.5 倍；762.30 = 14.4 倍 |

免费判据（判断端点是否存在的四条）：

| 返回 | 含义 |
|---|---|
| `400` / `422` + 参数报错 | 存在，停在校验层 |
| `404` + HTML | 未注册 |
| `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术 |
| `502` + `InvalidMpsUser` | 路由存在，上游凭据坏 |

---

## 6) 任务清单与报价单的 JSON 契约

### 清单（`quote --file`）

```json
{
  "title": "短剧一集",
  "note": "可选说明",
  "items": [
    {"kind": "image", "target": "gpt-image-2.6", "count": 6, "label": "分镜图"},
    {"kind": "video", "target": "full_video", "resolution": "1080P", "seconds": 15},
    {"kind": "video", "target": "model:sd/doubao-seedance-2-0-260128", "seconds": 10, "count": 2},
    {"kind": "post",  "target": "restore", "seconds": 120},
    {"kind": "voice", "target": "voice_tts", "chars": 220},
    {"kind": "app",   "target": "seedance", "count": 1}
  ]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `kind` | 是 | `image` / `video` / `post` / `voice` / `app` |
| `target` | 是 | 模型名 / 档位名 / 应用名 / `model:<模型ID>` |
| `count` | 否 | 次数或条数，默认 1 |
| `seconds` | 按秒项必填 | 秒数 |
| `chars` | voice 必填 | 字数 |
| `resolution` | full_video 用 | `480P` / `768P` / `1080P` / `2K` / `4K`，默认 1080P |
| `mode` | image_human 用 | `fast` / `standard` / `2k` / `4k`，默认 standard |
| `label` | 否 | 打印用的中文名 |

### 报价单（`quote --json`）

```json
{
 "ok": true, "estimate": true,
 "title": "短剧一集",
 "items": [{
   "kind": "image", "target": "gpt-image-2.6", "count": 6,
   "unit": "per_call", "unitLabel": "点/张", "unitPoints": 6.0,
   "qty": "6 张", "rulePath": "/api/v1/images/generations",
   "src": "流水 sync 实测", "basis": "6 点/张 × 6 张",
   "pointsBase": 36.0, "rangeLow": 36.0, "rangeHigh": 43.2,
   "yuanBase": 0.36, "traps": [], "notes": []
 }],
 "total": {"pointsBase": 5587.06, "rangeLow": 5587.06, "rangeHigh": 7491.32,
           "yuanBase": 55.87, "rangeLowYuan": 55.87, "rangeHighYuan": 74.91},
 "traps": [{"kind": "wildcard", "text": "落通配：对外 = 上游×2、保底 50 点",
            "items": ["模型层补镜"]}],
 "source": "https://api.a7w.cn/api/v1/pricing（现查 115 条规则）",
 "tasksScanned": 20, "budget": 5000, "overBudget": false,
 "estimatedPoints": 0
}
```

`traps[].kind` 取 `route404` / `upstream502` / `unitMismatch` / `wildcard` / `appVsModel`。
