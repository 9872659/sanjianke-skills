# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_e1c496c48350d9c728ba` |
| 标题 | Bernini视频编辑-描述词编辑视频 |
| 类型 | 视频 |
| 上游报价 | ¥1.16 |
| 本站 | 174.0 点（¥1.74）|

## 四个端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材（免费）
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（4 个，必填 4 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n268_video` | 上传视频 | video | 是 |  |
| `n362_text` | 描述词 | string | 是 | 女生衣服变成白色连衣裙 |
| `n331_value` | 视频时长（s） | int | 是 | 5 |
| `n333_value` | 视频帧率 | int | 是 | 25 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
