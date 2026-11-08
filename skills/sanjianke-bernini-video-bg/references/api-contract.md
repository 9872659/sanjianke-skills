# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_7f52b44d480a8476f7bf` |
| 标题 | Bernini视频换背景 |
| 类型 | 视频 |
| 上游报价 | ¥1.69 |
| 本站 | 253.5 点（¥2.535）|

## 四个端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材（免费）
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（5 个，必填 5 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n268_video` | 上传视频 | video | 是 |  |
| `n340_image` | 上传背景图片 | image_input | 是 |  |
| `n356_text` | 描述词 | string | 是 | 将视频背景替换成参考图中的卧室。 |
| `n331_value` | 视频秒数 | int | 是 | 5 |
| `n333_value` | 视频帧率 | int | 是 | 25 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
