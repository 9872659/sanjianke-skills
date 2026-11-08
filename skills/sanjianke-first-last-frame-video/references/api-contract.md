# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_ec81456a33e84f6e7a4b` |
| 标题 | 首尾帧视频 |
| 类型 | 视频 |
| 上游报价 | ¥0.4 |
| 本站 | 60.0 点（¥0.6）|

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
| `n110_image` | 上传首帧图片 | image_input | 是 |  |
| `n111_image` | 上传尾帧图片 | image_input | 是 |  |
| `n131_text` | 填写描述词 | string | 是 | 女人挥手变换动作 |
| `n101_value` | 时长 | int | 是 | 8 |
| `n104_value` | 最长边 | int | 是 | 832 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
