# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_ee4fd4f17551c5357ce9` |
| 标题 | 【1080P】5+4返璞归真版 |
| 类型 | 音频 |
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

## 参数（12 个，必填 4 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `node_282_aspect_ratio` | 宽高比【竖屏格式写：9:16 (Portrait Widescreen)】 | string | 是 | 16:9 (Widescreen) |
| `node_284_Number` | 时间长【4-15S】 | string | 是 | 4 |
| `node_283_text` | 提示词 | string | 是 | 参考图中的所有人站在草地上条约，同时其中 |
| `node_269_image` | image | image_input | 是 | None |
| `node_270_image` | image | image_input | - | None |
| `node_271_image` | image | image_input | - | None |
| `node_272_image` | image | image_input | - | None |
| `node_273_image` | image | image_input | - | None |
| `node_274_image` | image | image_input | - | None |
| `node_248_audio` | audio | audio_input | - | None |
| `node_249_audio` | audio | audio_input | - | None |
| `node_250_audio` | audio | audio_input | - | None |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
