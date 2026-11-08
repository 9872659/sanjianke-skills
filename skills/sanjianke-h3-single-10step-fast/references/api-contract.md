# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_e699d1ee6be7a30936a3` |
| 名称 | H3最强单采10步极速版 |
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

## 参数（14 个，必填 14 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `node_228_aspect_ratio` | aspect_ratio | string | 是 | None |
| `node_228_megapixels` | megapixels | float | 是 | None |
| `node_227_value` | value | float | 是 | None |
| `node_238_value` | value | string | 是 | None |
| `node_199_image` | image | image_input | 是 | None |
| `node_188_image` | image | image_input | 是 | None |
| `node_148_save_output` | save_output | bool | 是 | None |
| `node_189_image` | image | image_input | 是 | None |
| `node_190_image` | image | image_input | 是 | None |
| `node_191_image` | image | image_input | 是 | None |
| `node_192_image` | image | image_input | 是 | None |
| `node_253_audio` | audio | audio_input | 是 | None |
| `node_254_audio` | audio | audio_input | 是 | None |
| `node_255_audio` | audio | audio_input | 是 | None |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
