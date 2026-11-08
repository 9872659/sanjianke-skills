# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_fb72fb12968cbf5aff33` |
| 名称 | 自动修脸 |
| 类型 | 图片 |
| **每次** | **13.5 点（0.135 元）** |

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
| `n1_image` | image | image_input | 是 | |
| `n9_denoise` | denoise | float | 是 | 0.1 |
| `n12` | 最大边长 | int | 是 | 1728 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
