# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_0f4af3b82f6470d2a144` |
| 名称 | 【MINIMAX-H3教学】全能参考视频官方工作流 |
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

## 参数（5 个，必填 5 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `node_132_value` | value | float | 是 | None |
| `node_115_aspect_ratio` | aspect_ratio | string | 是 | None |
| `node_115_megapixels` | megapixels | float | 是 | None |
| `node_138_value` | value | string | 是 | None |
| `node_137_image` | image | image_input | 是 | None |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
