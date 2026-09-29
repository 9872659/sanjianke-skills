# 提交任务 · submit

> a7w 插件 `image_human` 的接口 `submit` · 平台官方文档

---

`POST /api/v1/apps/image_human/submit`

## 提交任务

`POST /api/v1/apps/image_human/submit`

全驱动数字人任务，提供人物图片、驱动音频、可选用户提示词和生成模式。mode 支持 fast、standard、2k、4k；resolution 仅作为兼容别名；submit 按输入音频时长计费。

返回示例：`{ "task_id": 123, "status": "pending" }`

## 参数（平台 schema 原文）

```json
{
  "mode": {
    "enum": [
      "fast",
      "standard",
      "2k",
      "4k"
    ],
    "type": "string",
    "default": "standard",
    "required": false,
    "description": "生成模式/清晰度档位：fast 快速模式，standard 标准模式，2k 高清模式，4k 超清模式"
  },
  "prompt": {
    "type": "string",
    "default": "人物说话自然，面对镜头，肢体语言自然，人物清晰可鉴。",
    "example": "人物说话自然，面对镜头，肢体语言自然，人物清晰可鉴。",
    "required": false,
    "description": "用户提示词；未传时使用默认提示词"
  },
  "duration": {
    "type": "number",
    "required": false,
    "description": "输入音频时长，单位秒；未传时平台从 ref_file_url 探测"
  },
  "file_url": {
    "type": "string",
    "example": "https://example.com/person.png",
    "required": true,
    "description": "输入图片 URL"
  },
  "resolution": {
    "enum": [
      "2k",
      "4k"
    ],
    "type": "string",
    "required": false,
    "description": "兼容字段；传 2k 或 4k 时等同于 mode=2k 或 mode=4k。新接入建议直接使用 mode"
  },
  "ref_file_url": {
    "type": "string",
    "example": "https://example.com/audio.wav",
    "required": true,
    "description": "输入音频 URL，用于驱动数字人；平台按该音频时长计费"
  }
}
```

## 能力限制（平台字段原文）

| 字段 | 值 | 含义 |
|---|---|---|
| `max_reference_images` | **1** | 参考图**最多 1 张** |
| `max_reference_audios` | 0 | 不接受参考音频列表 |
| `max_reference_videos` | 0 | 不接受参考视频 |
| `default_params` | `{"mode": "standard"}` | 不传 `mode` 时按 `standard` 计费 |
| `call_type` | 2 | 异步：返回 `task_id`，需轮询 |

## 计费

**这个接口按输入音频的时长计费，单价随 `mode` 档位变化。**

平台字段给出的 `pricing_matrix`（点/秒，1 元 = 100 点）：

```json
{
  "fast":     { "with_video": 1.5, "without_video": 1.5 },
  "standard": { "with_video": 2,   "without_video": 2   },
  "2k":       { "with_video": 4,   "without_video": 4   },
  "4k":       { "with_video": 8,   "without_video": 8   }
}
```

> ⚠️ **上面这组字段价是错的，不要拿它做预算** —— 四个档位实测结算价全部更高：

| `mode` | 平台字段价（点/秒） | **实测结算价（点/秒）** | 元/秒 | 60 秒 | 120 秒 |
|---|---|---|---|---|---|
| `fast` | 1.5 | **2** | 0.02 | 120 点 / 1.20 元 | 240 点 / 2.40 元 |
| `standard` | 2 | **3** | 0.03 | 180 点 / 1.80 元 | 360 点 / 3.60 元 |
| `2k` | 4 | **6** | 0.06 | 360 点 / 3.60 元 | 720 点 / 7.20 元 |
| `4k` | 8 | **12** | 0.12 | 720 点 / 7.20 元 | 1440 点 / 14.40 元 |

**计算公式**：`费用（点） = 音频时长（秒） × 该档单价`

**实测口径（2026-09，真花钱打出来的）**：

- 同一张人物图 + 同一段 **12.75 秒**驱动音频：`fast` 扣 **28.32 点**、`standard` 扣 **42.48 点**
  （平台返回的 `duration` 记为 **14.16 秒**），折算恰为 **2 / 3 点每秒**；
- 同一张图 + **2.64 秒**音频：`fast` 5.28 点、`standard` 7.92 点、`2k` 15.74 点、`4k` 31.49 点，
  四档折算恰为 2 / 3 / 6 / 12；
- 长段与短段的比值完全一致 → **按秒线性计费，没有最低消费**（2.64 秒不会被抬高到某个下限）；
- 但**平台返回的 `duration` 可能略大于你手上音频的真实时长**（本次 14.16 秒 vs 12.75 秒），
  **做预算留 10% 余量**，并一律以返回里的 `usage.points_cost` 为准。

> 平台调价后本表即失效，请重新真打一次核对。

其它价格字段（原样保留，供对账）：

- 标准价：`fixed_price=0.0000` / `input_price=2.000000`
- 租户价：`tenant_fixed_points=0.00` / `tenant_points_per_1k_input=2.0000`（**字段价，不等于实际结算价**）
- `billing_type = 5`

> `input_price = 2.0` / `tenant_points_per_1k_input = 2.0` 都只是**基础参考价**，
> **不等于任何档位的实际结算价** —— 实测 `standard` 档按 **3 点/秒** 结算，比这两个字段都高。
> 平台还有智能路由（`smart_route`，取值 `on` / `auto` / `off`），主线路故障时会降级到其它线路，
> **最终按实际成功线路的计费规则结算**，所以**一切以返回的 `usage.points_cost` 为准**。

