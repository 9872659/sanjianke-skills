# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_8c368ab7e0ba929295ce` |
| 标题 | Wan2.2-S2V+音频合成数字人 |
| 类型 | 视频 |
| 上游报价 | ¥0.23 |
| 本站 | 34.5 点（¥0.345）|

## 四个端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材（免费）
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（3 个，必填 2 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n126_image` | 上传人物图片 | image_input | 是 |  |
| `n141_prompt` | 提示词描述 | string | - | 人物讲话时轻松自然，身体略微放松，目光温 |
| `n185_audio` | 上传音频 | audio | 是 |  |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
