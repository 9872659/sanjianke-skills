# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_c7ca744bd7c516536796` |
| 名称 | 修改发型 |
| 类型 | 图片 |
| **每次** | **16.5 点（0.165 元）** |

## 端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（3 个，必填 2 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n205_image` | 原图 | image_input | 是 | |
| `n488_value` | 预设发色 | float | 是 | 3 |
| `n467_text` | 自定义发型 | string | - | |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
