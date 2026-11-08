# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_3df3b000e2109fc94cd2` |
| 标题 | LTX2.3图生视频对口型 |
| 类型 | 视频 |
| 上游报价 | ¥0.26 |
| 本站 | 39.0 点（¥0.39）|

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
| `n73_audio` | 音频 | audio | 是 |  |
| `n96_image` | 图片 | image_input | 是 |  |
| `n72_value` | 长边 | int | 是 | 720 |
| `n121_text` | 辅助描述 | string | 是 | 固定镜头，男人不屑的讲话 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
