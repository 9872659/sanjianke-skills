# 提交任务 · submit

> a7w 插件 `seedsvc` 的接口 `submit` · 平台官方文档

---

`POST /api/v1/apps/seedsvc/submit`

## 提交弹性任务

`POST /api/v1/apps/seedsvc/submit`

在平台「弹性部署」对应应用中配置默认策略后，调用本接口创建 `ai_elastic_task`。

返回示例：`{ "task_id": 123, "status": "pending" }`（task_id 为弹性任务主键）

## 参数（平台 schema 原文）

```json
{
  "mode": {
    "type": "string",
    "default": "async_query",
    "required": false,
    "description": "任务模式，默认 async_query"
  },
  "ref_audio": {
    "type": "string",
    "example": "https://example.com/target_voice.wav",
    "required": true,
    "description": "目标音色参考音频 URL"
  },
  "source_audio": {
    "type": "string",
    "example": "https://example.com/original_song.wav",
    "required": true,
    "description": "原始音频文件 URL，需要转换音色的音频"
  }
}
```

## 计费

- 平台字段价（**未必等于实际结算价**；真实扣费只看返回里的 `data.usage.points_cost`）：按次固定价 0.1 点（租户价）；标准价 100 点
- 标准价：`fixed_price=100.0000` / `input_price=0.000000`
- 租户价：`tenant_fixed_points=0.10` / `tenant_points_per_1k_input=0.0000`
