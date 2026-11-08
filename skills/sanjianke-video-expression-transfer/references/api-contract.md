# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_d9e58934f4fe91e28467` |
| 标题 | 视频表情迁移 |
| 类型 | 视频 |
| 上游报价 | ¥0.35 |
| 本站 | 52.5 点（¥0.525）|

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
| `n143_image` | 上传图片 | image_input | 是 |  |
| `n160_video` | 上传视频 | video | 是 |  |
| `n222_value` | 视频帧数 | int | - | 113 |
| `n223_value` | 宽度 | int | 是 | 480 |
| `n224_value` | 高度 | int | 是 | 832 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
