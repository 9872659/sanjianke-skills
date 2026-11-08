# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_03da6c3fc45f19e2c5c4` |
| 名称 | 动作表情迁移 |
| 类型 | 视频 |
| **每次** | **72.0 点（0.72 元）** |

## 端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（3 个，必填 3 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n57_image` | 参考图 | image_input | 是 | |
| `n255_video` | 视频 | video | 是 | |
| `n436_number` | 秒数 | string | 是 | 5 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
