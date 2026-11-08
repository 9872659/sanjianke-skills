# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_3573f69dbd587a814192` |
| 名称 | 文生图 |
| 类型 | 文本 |
| **每次** | **15.0 点（0.15 元）** |

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
| `n57_27_text` | 提示词 | string | 是 | (杰作，最高品质，8K，超写实，逼真，电 |
| `n57_13_batch_size` | 批量大小 | int | 是 | 1 |
| `n57_13_height` | 高度 | int | 是 | 1280 |
| `n57_13_width` | 宽度 | int | 是 | 1280 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
