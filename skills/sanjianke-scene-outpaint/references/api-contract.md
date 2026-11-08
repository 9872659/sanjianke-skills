# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_0f14e4172da658bd5a5d` |
| 标题 | 场景扩图 |
| 类型 | 图片 |
| 上游报价 | ¥0.05 |
| 本站 | 7.5 点（¥0.075）|

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
| `n411_image` | 原图 | image_input | 是 |  |
| `n418_value` | 向左扩展 | int | 是 | 400 |
| `n420_value` | 向右扩展 | int | 是 | 400 |
| `n419_value` | 向上扩展 | int | 是 | 400 |
| `n421_value` | 向下扩展 | int | 是 | 400 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
