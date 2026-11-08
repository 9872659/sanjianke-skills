# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_87b1e4094cdf7834addf` |
| 名称 | 熟颜世绘 |
| 类型 | 文本 |
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
| `node_251_value` | 值 | int | 是 | 1280 |
| `node_250_value` | 值 | int | 是 | 720 |
| `node_242_text` | 文本 | string | 是 | 一个东亚长发美女，带着泪滴状的耳饰，水晶 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
