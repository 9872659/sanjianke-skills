# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_5792667b7a06ebabeb8d` |
| 名称 | H3视频 |
| 类型 | 视频 |
| **每次** | **13.5 点（0.135 元）** |

## 端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（12 个，必填 12 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `node_115_aspect_ratio` | 画面比例 | string | 是 | 16:9 (Widescreen) |
| `node_132_value` | 时长 | float | 是 | 10 |
| `node_138_value` | 提示词 | string | 是 | [Shot 1] High-contra |
| `node_137_image` | 加载图像1 | image_input | 是 | None |
| `node_139_image` | 加载图像2 | image_input | 是 | None |
| `node_146_image` | 加载图像3 | image_input | 是 | None |
| `node_159_image` | 加载图像4 | image_input | 是 | None |
| `node_160_image` | 加载图像5 | image_input | 是 | None |
| `node_161_image` | 加载图像6 | image_input | 是 | None |
| `node_282_audio` | 音频1 | audio_input | 是 | None |
| `node_283_audio` | 音频2 | audio_input | 是 | None |
| `node_284_audio` | 音频3 | audio_input | 是 | None |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
