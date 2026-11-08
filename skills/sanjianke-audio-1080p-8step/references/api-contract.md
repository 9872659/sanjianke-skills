# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_8d601e151bf6704d7153` |
| 名称 | 1080P八步双采 |
| 类型 | 音频 |
| **每次** | **13.5 点（0.135 元）** |

## 端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（12 个，必填 4 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `node_39_aspect_ratio` | 宽高比【长条填9:16 (Portrait Widescreen)】 | string | 是 | 16:9 (Widescreen) |
| `node_44_Number` | 时间长【填4-15S】 | string | 是 | 5 |
| `node_45_text` | 提示词【建议使用H3模板】 | string | 是 | 5 |
| `node_54_image` | image | image_input | 是 | {'asset_id': 'asset_ |
| `node_57_image` | image | image_input | - | {'asset_id': 'asset_ |
| `node_55_image` | image | image_input | - | {'asset_id': 'asset_ |
| `node_58_image` | image | image_input | - | {'asset_id': 'asset_ |
| `node_56_image` | image | image_input | - | {'asset_id': 'asset_ |
| `node_59_image` | image | image_input | - | {'asset_id': 'asset_ |
| `node_60_audio` | audio | audio_input | - | {'asset_id': 'asset_ |
| `node_61_audio` | audio | audio_input | - | {'asset_id': 'asset_ |
| `node_62_audio` | audio | audio_input | - | {'asset_id': 'asset_ |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
