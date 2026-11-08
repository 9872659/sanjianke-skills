# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_b4d80189b80bc5e5e012` |
| 标题 | Bernini视频编辑-单图控制编辑视频 |
| 类型 | 视频 |
| 上游报价 | ¥0.63 |
| 本站 | 94.5 点（¥0.945）|

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
| `n340_image` | 上传物品（图1） | image_input | 是 |  |
| `n809_text` | 描述词 | string | 是 | 视频中的人物头上戴着参考图1的帽子，保持 |
| `n331_value` | 视频生成秒数 | int | 是 | 5 |
| `n333_value` | 视频帧率 | int | 是 | 25 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
