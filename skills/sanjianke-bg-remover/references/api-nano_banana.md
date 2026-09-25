# 图片接口 · submit 与 query

> `api.a7w.cn` 应用 `nano_banana` · 去背景 / 换底就是它的 `edit` 用法

---

## 一、提交任务

`POST /api/v1/apps/nano_banana/submit`

```http
POST /api/v1/apps/nano_banana/submit
Authorization: Bearer <YOUR_API_KEY>
Content-Type: application/json
```

| 字段 | 内容 |
|---|---|
| 应用编码 | `nano_banana` |
| API 编码 | `submit` |
| 请求方式 | `POST` |
| 调用模式 | 异步（返回 `task_id`） |
| 默认模型 | `nano-banana` |
| 默认分辨率 | `1K` |

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `prompt` | string | 是 | - | 你要什么底、主体怎么保留，就写在这 |
| `action` | string | 否 | `generate` | **去背景必须传 `edit`**（基于参考图编辑）；`generate` 是纯文生图 |
| `model` | string | 否 | `nano-banana` | 见下方模型表，影响价格与可用分辨率 |
| `image_urls` | array | `edit` 必填 | - | 参考图公网 URL 数组；换底场景传 1 张原图 |
| `resolution` | string | 否 | `1K` | `1K` / `2K` / `4K`；官方模型按该字段分档计费 |
| `aspect_ratio` | string | 否 | `auto` | `auto` / `1:1` / `16:9` / `9:16` / `4:3` / `3:4` / `3:2` / `2:3` / `5:4` / `4:5` / `21:9` |
| `callback_url` | string | 否 | - | 任务终态时平台主动 POST 通知的 HTTPS 地址 |

### 模型与价格

| 模型 | 分辨率 | 价格 | 说明 |
|---|---|---|---|
| `nano-banana` | `1K` | 24 点/次 | 默认规格，去背景首选，最省 |
| `nano-banana-2` | `1K` | 38 点/次 | 升级版，主体一致性更稳 |
| `nano-banana-2-lite` | `1K` | 24 点/次 | 轻量规格 |
| `nano-banana-pro` | `1K` | 45 点/次 | 专业规格 |
| `nano-banana:official` | `1K` | 28.03 点/次 | 官方模型 |
| `nano-banana-2-lite:official` | `1K` | 28.03 点/次 | 官方轻量 |
| `nano-banana-2:official` | `1K` / `2K` / `4K` | 35.76 点/次起 | 官方高清，按分辨率计费 |
| `nano-banana-pro:official` | `1K` / `2K` / `4K` | 61.52 点/次起 | 官方高清专业规格 |

> 1 元 = 100 点。价格以当前租户配置为准，**实际扣费看返回里的 `data.usage.points_cost`**。

### 请求示例 · 去背景换白底

```json
{
  "action": "edit",
  "prompt": "去掉背景，主体保留完整，换成纯白背景 #FFFFFF，边缘干净，商品居中",
  "model": "nano-banana",
  "image_urls": ["https://你的存储/商品图.jpg"],
  "aspect_ratio": "1:1"
}
```

### 成功响应

```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "task_id": "task_xxxxxxxxxxxx",
    "status": "pending",
    "app": "nano_banana",
    "api": "submit",
    "frozen_points": 24
  }
}
```

提交时会**预冻结点数**，完成后按实际用量结算。

### 失败响应

```json
{
  "code": 0,
  "msg": "当前请求未命中可用计费规格，请检查模型、分辨率是否在支持范围内。",
  "data": [],
  "show": 1
}
```

常见失败原因：`prompt` 为空、`action` 非法、`model` 不支持、
**普通模型传了非 `1K` 分辨率**、点数不足、Key 无权限。

---

## 二、查询任务

`POST /api/v1/apps/nano_banana/query`

| 字段 | 内容 |
|---|---|
| API 编码 | `query` |
| 请求方式 | `POST`（也支持 `GET` 带 query string） |
| 调用模式 | 同步 |
| 是否计费 | **否** |

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | string | 是 | `submit` 返回的平台任务 ID |

### 处理中响应

```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "result": { "status": "processing" },
    "usage": { "points_cost": 0, "actual_points": 0 }
  }
}
```

### 完成响应

```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "result": {
      "status": "completed",
      "task_id": "task_xxxxxxxxxxxx",
      "image_url": "https://example.com/output.png",
      "actual_points": 24
    },
    "usage": { "points_cost": 24, "actual_points": 24 }
  }
}
```

### 轮询建议

每 3～5 秒查一次即可。提交时传了 `callback_url` 的话，
平台也会在任务终态时主动通知该地址，可以不用轮询。

### 统一任务查询

也可以直接用平台通用任务接口，任何应用的异步任务都吃：

```http
GET /api/v1/tasks/{task_id}
Authorization: Bearer <YOUR_API_KEY>
```

终态看 `status`（`completed` / `failed` / `cancelled`），产物在 `result`，用量在 `usage`。

---

## 三、客户端调用

```bash
# 提交（自动轮询到结束，并落盘）
python3 scripts/a7w.py call nano_banana submit \
  --body '{"action":"edit","prompt":"去掉背景，换成纯白背景 #FFFFFF，主体保留完整，边缘干净","image_urls":["https://你的存储/商品图.jpg"]}' \
  --out 白底图.png

# 只提交，不等结果
python3 scripts/a7w.py call nano_banana submit --body '{...}' --no-wait

# 按 task_id 查
python3 scripts/a7w.py task <task_id>
```
