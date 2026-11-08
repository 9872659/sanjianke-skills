# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_bf111e9c5269b06d40b4` |
| 名称 | 视频换背景 |
| 类型 | 视频 |
| **每次** | **79.5 点（0.795 元）** |

## 端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（2 个，必填 2 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n148_image` | 上传背景图片 | image_input | 是 | |
| `n147_video` | 上传人物视频（注：如果视频过长，为了保证正常生成，会截取视频前8秒来生成） | video | 是 | |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
