# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_4670182d4948bec8d79c` |
| 名称 | 男装开车变装（视频生成） |
| 类型 | 视频 |
| **每次** | **15.0 点（0.15 元）** |

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
| `n2800_value` | 动作 | string | 是 | |
| `n2799_value` | 风景 | string | 是 | |
| `n2853_image` | 预览图 | image_input | 是 | |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
