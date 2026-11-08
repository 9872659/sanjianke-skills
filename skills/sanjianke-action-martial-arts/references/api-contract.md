# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_9dbf70f6a4479ddcb762` |
| 标题 | 黄色的大宝剑专用武打流 |
| 类型 | 图片 |
| 上游报价 | ¥0.01 |
| 本站 | 1.5 点（¥0.015）|

## 四个端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材（免费）
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（9 个，必填 6 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `node_148_aspect_ratio` | 比例选择 | string | 是 | None |
| `node_148_megapixels` | 分辨率选择（0.4-2.0） | float | 是 | None |
| `node_132_value` | 视频时长（4-15） | float | 是 | None |
| `node_124_steps` | 一采步数 | int | 是 | None |
| `node_138_value` | 提示词输入 | string | 是 | None |
| `node_137_image` | 图片一 | image_input | 是 | None |
| `node_152_image` | 图片二 | image_input | - | None |
| `node_197_image` | 图片三 | image_input | - | None |
| `node_198_image` | 图片四 | image_input | - | None |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
