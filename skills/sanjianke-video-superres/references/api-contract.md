# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_42c5986f3781b6210c3e` |
| 标题 | 视频超分 |
| 类型 | 视频 |
| 上游报价 | ¥0.29 |
| 本站 | 43.5 点（¥0.435）|

## 四个端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材（免费）
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（4 个，必填 4 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n2_video` | video | video | 是 |  |
| `n26_boolean` | 有无音频 | bool | 是 | False |
| `n22_scale_to_length` | 视频实际分辨率 | int | 是 | 480 |
| `n18_resolution` | 超分目标分辨率 | int | 是 | 720 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
