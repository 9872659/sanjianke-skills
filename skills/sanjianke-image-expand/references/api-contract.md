# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_f32767981004df73ace2` |
| 标题 | 图片扩充 |
| 类型 | 图片 |
| 上游报价 | ¥0.12 |
| 本站 | 18.0 点（¥0.18）|

## 四个端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材（免费）
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（6 个，必填 1 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n71_image` | 上传图片 | image_input | 是 |  |
| `n116_top` | 向上扩像素值 | int | - | 480 |
| `n116_bottom` | 向下扩像素值 | int | - | 480 |
| `n116_left` | 向左扩像素值 | int | - | 272 |
| `n116_right` | 向右扩像素值 | int | - | 272 |
| `n116_feathering` | 羽化值 | int | - | 40 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
