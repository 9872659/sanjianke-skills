# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_2b40d7d3eee38e5b657f` |
| 标题 | Infinitetalk对口型数字人 |
| 类型 | 视频 |
| 上游报价 | ¥0.68 |
| 本站 | 102.0 点（¥1.02）|

## 四个端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材（免费）
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（5 个，必填 4 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n36_image` | 上传图片 | image_input | 是 |  |
| `n34_audio` | 上传音频 | audio | 是 |  |
| `n20_start_time` | 音频开始时间 | string | 是 | 0:00 |
| `n20_end_time` | 音频结束时间 | string | 是 | 0:18 |
| `n30_prompt` | 提示词描述 | string | - | 女人对着镜头讲话，表情动作自然
 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
