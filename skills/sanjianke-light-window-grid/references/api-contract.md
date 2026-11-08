# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_06c8d1487e07eeef4fb7` |
| 名称 | 窗格光影氛围 |
| 类型 | 图片 |
| **每次** | **52.5 点（0.525 元）** |

## 端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（1 个，必填 1 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n191_image` | 原图 | image_input | 是 | |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
