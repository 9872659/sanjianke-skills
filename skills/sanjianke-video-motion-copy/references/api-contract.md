# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_33844ef5f01b4ff0f425` |
| 名称 | 视频动作复刻 |
| 类型 | 视频 |
| **每次** | **55.5 点（0.555 元）** |

## 端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（4 个，必填 2 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n55_image` | 上传图片 | image_input | 是 | |
| `n72_video` | 上传视频 | video | 是 | |
| `n72_frame_load_cap` | 视频帧数（默认0实为视频总帧数，谨慎修改） | int | - | 0 |
| `n151_text` | 提示词 | string | - | |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
