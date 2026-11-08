# 接口契约

## 应用

| 字段 | 值 |
|---|---|
| workflow_id | `wf_b972fe24e79cafd7f47d` |
| 名称 | IndexTTS_2声音克隆-支持各种情绪编辑 |
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

## 参数（11 个，必填 2 个）

| 参数名 | 含义 | 类型 | 必填 | 默认 |
|---|---|---|---|---|
| `n12_audio` | 音色参考 | audio | 是 | |
| `n18_audio` | 情感参考 | audio | - | |
| `n3_text` | 输入文本 | string | 是 | I can't believe what |
| `n8_afraid` | 害怕 | float | - | 0 |
| `n8_angry` | 生气 | float | - | 0 |
| `n8_calm` | 平静 | float | - | 0 |
| `n8_disgusted` | 厌恶的 | float | - | 0 |
| `n8_happy` | 快乐 | float | - | 0 |
| `n8_melancholic` | 忧郁的 | float | - | 0 |
| `n8_sad` | 悲伤 | float | - | 0 |
| `n8_surprised` | 惊讶 | float | - | 0 |

## 返回

提交成功返回 `data.run_order_id`；轮询 `execution?run_order_id=` 拿 `status` 与产物列表。
