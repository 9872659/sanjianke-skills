# 接口契约（实测）

> 来源：`GET /api/v1/gpu/apps` 返回的 69 个应用之一（`total: 69`，`markup: 1.5`）。

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_f5b5964ba0d16e5b1b84` |
| 标题 | 智能重绘 |
| 类型 | 图片 |
| 上游报价 | ¥0.01 |
| 本站 | 1.5 点（¥0.015）|

## 四个端点

```
GET  /api/v1/gpu/apps                        应用清单（69 个）
GET  /api/v1/gpu/apps/<workflow_id>/schema    参数
POST /api/v1/gpu/assets                       上传素材（免费）
POST /api/v1/gpu/apps/<workflow_id>/run       提交 {"inputs":{...}}
GET  /api/v1/gpu/workflows/execution?run_order_id=...   轮询
```

## 参数（6 个，必填 6 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n255_image` | image | image_input | 是 |  |
| `n1_ckpt_name` | ckpt_name | string | 是 | 超美写实.safetensors |
| `n2_sampler_name` | sampler_name | string | 是 | euler |
| `n2_scheduler` | scheduler | string | 是 | normal |
| `n2_denoise` | denoise | float | 是 | 0.1 |
| `n259_size` | size | int | 是 | 512 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
