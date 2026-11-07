# 接口契约（2026-11-07 实测原文）

本包只读四个端点，全部 `GET`，全部 0 点。

| 端点 | 返回 | 用途 |
|---|---|---|
| `GET /api/v1/pricing` | `{currency, markupPercent, note, site, pricing{...}}` | 应用层与视频档单价 |
| `GET /api/v1/models` | `{object, data[316], code, msg}` | 模型目录 + 模型层 ID |
| `GET /api/v1/apps` | `{code, msg, data[22]}` | 应用目录 + 接口清单 |
| `GET /api/v1/me/tasks?limit=2000&page=N` | `{tasks[20/页], total, sumPoints, ...}` | 模型层真实成交价 |

---

## 1) `GET /api/v1/pricing`

**顶层是裸对象，不套 `code/data`。** 五个键：

```json
{
 "currency": "points",
 "markupPercent": 20,
 "note": "User price = upstream points x (1 + markup%). 实际成本以上游响应标记为准。",
 "site": "api",
 "pricing": { "/api/v1/...": { ...规则... }, ... }
}
```

`pricing` 共 **115 条**规则。键是路径，可以是精确路径、`*` 通配尾（`/apps/x/*`）、
或顶层 `*`（全局兜底）。

### 规则字段（115 条里出现过的全部字段）

| 字段 | 出现次数 | 类型 | 含义 |
|---|---|---|---|
| `mode` | 115 | str | `flat` / `per_second` / `per_module` |
| `markupPercent` | 115 | int(114) / float(1) | 加价率；`cost:0` + 非 0 表示「按上游实际点数 × (1+n%)」 |
| `note` | 115 | str | 人写的中文说明，最长的一条 600+ 字 |
| `cost` | 65 | int | `flat` 的一口价（点） |
| `perSecond` | 46 | int(45) / float(1) | 每秒点数 |
| `minPoints` | 23 | int | 单笔保底 |
| `provider` | 14 | str | 上游供应商标记（`tencent` / `viapi` …） |
| `definition` | 11 | int | TSC 档位号（321001 / 321003 …） |
| `sizeRates` | 4 | dict | 按尺寸分档价（`{"1K":105,"2K":203}`） |
| `resolutionRates` | 1 | dict | 按分辨率分档价（`full_video`：480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80） |
| `estimate` | 3 | int | 预冻结额（真正结算另算） |
| `rateFrom` | 3 | str | `mode`（按请求体 mode 取费率） |
| `modelRates` | 3 | dict | **按 mode 参数的费率表**，见下 |
| `defaultModel` | 3 | str | `rateFrom` 的缺省档 |
| `unitFrom` | 1 | str | `module_codes`（`/api/v1/tasks` 按模块数计价） |

### 关键更正：`modelRates` 不是「模型层价目表」

`modelRates` 只出现在 3 条 `image_human` 规则上（`/apps/image_human/*`、`/submit`、`/create`），
内容是：

```json
"/api/v1/apps/image_human/submit": {
  "mode": "per_second",
  "markupPercent": 400,
  "rateFrom": "mode",
  "defaultModel": "fast",
  "modelRates": {
    "fast":     {"*": 10},
    "standard": {"*": 15},
    "2k":       {"*": 30},
    "4k":       {"*": 60}
  },
  "note": "...全驱数字人 快速 10 / 标准 15 / 2K 30 / 4K 60 点/输入秒（= 上游成本 2/3/6/12 ×5，毛利 80%）..."
}
```

含义是「**按请求体里的 `mode` 参数取费率**」，配合 `rateFrom: "mode"` + `defaultModel` 使用。
它是应用层内部的分档，不是「模型 code → 单价」。

**全表没有 `modelPricing` 这个键**，也没有任何形如
`"volcengine/doubao-seedance-2-5-260628": 762` 的映射。

### 通配兜底

```json
"*": {
  "mode": "flat",
  "cost": 0,
  "markupPercent": 100,
  "minPoints": 50,
  "note": "未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"
}
```

`/api/v1/videos`、`/api/v1/videos/generations`、`/api/v1/images/generations`
三条模型层路径在 `pricing` 里**都没有专属键**，因此全部落在这一条下面。
（`/api/v1/tasks` 有专属键，但那是 `per_module`：带 `module_codes[]` 时 50 点 × 模块数，
不带则退回模型线。）

### 应用层一口价（节选，全部现查）

| 路径 | mode | 价 |
|---|---|---|
| `/api/v1/apps/seedance/submit` | flat | `cost: 11000`「固定 11000 点/次（上游约 5500 点 ×2）」 |
| `/api/v1/apps/wan/submit` | flat | 800 |
| `/api/v1/apps/happy_horse/submit` | flat | 650 |
| `/api/v1/apps/mmaudio/*` | flat | 495 |
| `/api/v1/apps/grok_video/submit` | flat | 300 |
| `/api/v1/apps/seedsvc/*` | flat | 220 |
| `/api/v1/apps/dressing_diffusion/submit` | flat | 200 |
| `/api/v1/apps/aigc_wan_image/generate/index` | flat | 203（2K 档）|
| `/api/v1/apps/aigc_photo_restore/*` | flat | 105 / `sizeRates{1K:105, 2K:203}` |
| `/api/v1/apps/nano_banana/submit` | flat | 72 |
| `/api/v1/apps/aigc_qwen_image/generate/index` | flat | 78 |
| `/api/v1/apps/voice_tts/*` | flat | `cost: 0` + `markupPercent: 200`（上游实际点数 × 3）|
| `/api/v1/apps/indextts/*` | flat | `cost: 0` + `markupPercent: 200` |
| `/api/v1/apps/full_video/submit` | per_second | `resolutionRates` 14 / 28 / 60 / 80 / 80 |
| `/api/v1/apps/flashvsr/submit` | per_second | 10 点/秒，保底 20 |
| `/api/v1/apps/smart_clip/*` | per_second | 4.5 点/秒，`estimate: 45` |
| `/api/v1/apps/pic_lipsync/submit` | flat | `cost: 0`, `minPoints: 50` |
| `/api/v1/tasks` | per_module | 50 点 × 模块数 |

### 视频档（节选）

`/video/restore` 36 · `/video/upscale` 30 · `/video/faceswap` 20 · `/video/delogo` 25 ·
`/video/castcrew` 25 · `/video/shot` 20 · `/video/cartoon` 24 · `/video/enhance` 15 ·
`/video/colorize` 9 · `/video/segment` 9 · `/video/subtitle` 9（全部 `per_second`，单位点/秒）。

`/video/viapi/superres` 9 · `superres2k` 15 · `superres4k` 20 · `interp` 25 · `portrait` 18。

`/video/tencent1080` 2 · `tencent2k` 4 · `tencent4k` 8（`minPoints: 10`，`provider: tencent`）。

`tsc_*` 11 档：`tsc_common` 3 · `tsc_common_hd` 6 · `tsc_aigc` 3 · `tsc_aigc_hd` 6 ·
`tsc_shortplay` 3 · `tsc_shortplay_hd` 6 · `tsc_uhd` 3 · `tsc_oldsd` 3 · `tsc_oldsd_hd` 6 ·
`tsc_teshd` 2 · `tsc_quality` 2（`minPoints: 10`，`provider: tencent`）。

---

## 2) `GET /api/v1/models`

```json
{"object": "list", "code": 1, "msg": "success", "data": [ ...316 条... ]}
```

316 条分成两类：

### (a) 221 条「目录模型」——带 `model_code`

```json
{
 "model_code": "muse-video",
 "model_name": "Muse Video",
 "description": "参考图视频生成，当前开放 10 秒、720p，支持横屏和竖屏。",
 "call_type": 2,
 "max_tokens": 1,
 "supports_vision": 1,
 "supports_reasoning": 0,
 "max_reference_images": 8,
 "max_reference_audios": 0,
 "max_reference_videos": 0,
 "channel_code": "xAIQ", "channel_name": "xAIQ",
 "vendor_code": "xAI", "vendor_name": "xAI",
 "type_code": "video", "type_name": "视频生成",
 "id": "muse-video", "name": "Muse Video", "display_name": "Muse Video",
 "object": "model", "created": 1794055764, "owned_by": "xAI",
 "call_type_desc": "异步",
 "capabilities": {"supports_vision": true, "supports_reasoning": false,
                  "max_reference_images": 8, "max_reference_audios": 0,
                  "max_reference_videos": 0},
 "smart_route_supported": false,
 "smart_route_enabled": false,
 "smart_route_billing_rule": "final_success_target",
 "smart_route_tooltip": "智能路由编排只在内部执行……实际扣费按最终成功线路的计费规则结算，因此可能与当前展示的基础参考价不同。",
 "smart_route_strategy_id": 0, "smart_route_strategy_version": 0
}
```

按类型：`text` 92 条 / `image` 50 条 / `video` 47 条 / `other` 32 条。

**只有 92 条 `text` 带 `pricing`**，那是文本模型的模型层价目：

```json
"pricing": {
  "billing_type": 1,
  "per_1k_input": 500, "per_1k_output": 3000, "fixed_points": 3000,
  "pricing_v2": {
    "billing_mode": "usage",
    "items": [{
      "sku_key": "gpt_5_5_token",
      "title": "按百万 Token",
      "usage_unit": "token", "usage_unit_size": 1000000,
      "price": {"points": 3000, "unit": "token"},
      "effective_rate_config": {"input": 500, "cached_input": 50, "output": 3000}
    }],
    "price_view": {"title": "按用量计费", "summary": "按百万 Token 3000 点/百万 Token"}
  },
  "billing_sku": {"user_sale_points": 3000, "effective_points": 3000,
                  "pricing_source": "租户基础价"}
}
```

即 `pricing.pricing_v2.items[0].price.points` = 每百万 token 的点数。
92 条里最高 `claude-fable-5-official` 15,840，最低 `Qwen2.5-7B-Instruct` 45。

### (b) 95 条「裸模型层 ID」——没有 `model_code`

```json
{"id": "volcengine/doubao-seedance-2-5-260628", "object": "model",
 "owned_by": "flagship", "created": 0}
```

只有四个字段：`id` / `object` / `owned_by` / `created`。**没有价格字段。**

部分 ID：

```
volcengine/doubao-seedance-2-5-260628
volcengine/doubao-seedance-2-0-fast-260128
volcengine/doubao-seedance-1-5-pro-251215
sd/doubao-seedance-2-0-260128
volcengine-idle/doubao-seedance-2-0-fast-idle-260128
volcengine/doubao-seedream-5-0-lite-260128
volcengine/doubao-seedream-4-5-251128
volcengine-speech/seed-tts-2.0
wan3.0-video / wan3.0-video-prime
```

**结论**：视频与图片模型的模型层单价，`/pricing` 和 `/models` 都不给。

---

## 3) `GET /api/v1/apps`

```json
{"code": 1, "msg": "success", "data": [ ...22 个应用... ]}
```

```json
{
 "id": 19, "name": "人物替换", "code": "person_replacement",
 "description": "人物替换，基于参考图片和输入视频生成替换后的视频结果。",
 "icon": "", "driver_code": "elastic_gpu", "billing_mode": 1,
 "category_id": 5, "category_name": "其他", "category_code": "other",
 "tenant_sort": 80,
 "apis": [
   {"id": 52, "code": "submit", "name": "提交任务",
    "category_id": 3, "category_name": "视频生成", "category_code": "video",
    "call_type": 2, "method": "POST",
    "max_reference_images": 1, "max_reference_videos": 1,
    "smart_route_billing_rule": "final_success_target"}
 ]
}
```

22 个应用：`person_replacement` / `action_transfer` / `full_video` / `pic_lipsync` /
`happy_horse` / `media_services_33`（29 个 api）/ `file_qa` / `music_search` / `grok_video` /
`nano_banana` / `music_generation`（13）/ `smart_clip`（5）/ `image_human` / `wan` /
`seedance`（7）/ `lipsync` / `dressing_diffusion` / `mmaudio` / `flashvsr` / `seedsvc` /
`watermark_removal`（8）/ `voice_tts`（6）。

合计 **100 个 api**。其中 21 / 22 个应用在 `pricing` 里有专属规则，
`media_services_33` 没有（会掉进通配 `*`）。

---

## 4) `GET /api/v1/me/tasks?limit=2000&page=N`

本包用这个端点反推**模型层真实单价**。

```json
{
 "taskId": "1666cb7e-db58-40f9-a9f1-79cf30a0c305",
 "model": "volcengine/doubao-seedance-2-5-260628",
 "type": "模型",
 "path": "/api/v1/videos/generations",
 "provider": "",
 "status": "succeeded",
 "reservePrice": 3000.000003,
 "actualPrice": 762.3,
 "refund": 0,
 "frozenPoints": 3000.000003,
 "chargedPoints": 762.3,
 "refundedPoints": 0,
 "netPoints": 762.3,
 "rateNote": "官方价 × 2.00（≈ +100%）",
 "feeYuan": 7.62,
 "moduleCount": null,
 "tool": "",
 "charges": [ ... ]
}
```

`rateNote` 是网关算这笔账时命中的规则说明。模型层任务的 `rateNote` 恒为
**「官方价 × 2.00（≈ +100%）」**，正好对应通配 `*` 的 `markupPercent: 100`。

分页：`size` / `per_page` 无效，**每页恒 20 条**；`limit` 只影响统计窗口（给 2000 覆盖全部）。

### 实测样本（2026-11-07，500 条任务里筛出来的）

| model | path | actualPrice |
|---|---|---|
| `volcengine/doubao-seedance-2-5-260628` | `/api/v1/videos/generations` | 762.30 / 3000 / 3045.71 |
| `sd/doubao-seedance-2-0-260128` | `/api/v1/videos/generations` | 145.73 / 181.79 / 3000 |
| `wan3.0-video` | `/api/v1/videos/generations` | 300 |
| `muse-video` | `/api/v1/videos` | 44 / 55 / 260 |
| `gpt-image-2-pro` | `/api/v1/tasks` | 39 / 78 / 104 |
| `gpt-image-2` | `/api/v1/tasks` | 26 |
| `seedream-5-0-flash` | `/api/v1/tasks` | 15.60 |

对照同一个应用层的 `seedance` 一口价 11,000 点：

```
11,000 / 145.73 = 75.5 倍   (sd/doubao-seedance-2-0-260128)
11,000 / 762.30 = 14.4 倍   (volcengine/doubao-seedance-2-5-260628)
```
