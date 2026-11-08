# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_12eb46eb87a314966c40` |
| 名称 | LTX2.3文生视频 |
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

## 参数（4 个，必填 4 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n267_258_value` | 高 | int | 是 | 720 |
| `n267_257_value` | 宽 | int | 是 | 1280 |
| `n267_225_value` | 秒数 | int | 是 | 5 |
| `n267_266_value` | 描述词 | string | 是 | Dynamic cinematic cl |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
