# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_00622c7d05abcc7d9e4c` |
| 名称 | Minimax-H3文生视频 |
| 类型 | 视频 |
| **每次** | **60.0 点（0.6 元）** |

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
| `n105_104_prompt` | 提示词 | string | 是 | Realistic live-actio |
| `n115_aspect_ratio` | 比例 | string | 是 | 16:9 (Widescreen) |
| `n115_megapixels` | 像素数量（百万） | float | 是 | 0.4 |
| `n105_111_value` | 秒数 | float | 是 | 5 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
