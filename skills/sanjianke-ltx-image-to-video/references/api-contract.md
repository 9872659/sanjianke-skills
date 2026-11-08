# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_c243ff0ff1655aae9210` |
| 名称 | LTX2.3图生视频 |
| 类型 | 视频 |
| **每次** | **30.0 点（0.3 元）** |

## 端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（4 个，必填 4 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n325_scale_to_length` | 长边长度 | int | 是 | 1280 |
| `n269_image` | 首帧图 | image_input | 是 | |
| `n324_string` | 描述 | string | 是 | 女人讲话 |
| `n320_301_value` | 秒数 | int | 是 | 5 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
