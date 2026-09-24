# `api.a7w.cn` · `flashvsr` 插件接口文档

> 平台：`api.a7w.cn` ｜ 应用代号：`flashvsr`
> 用途：视频超分辨率（超分 / 超清）

---

## 接口一览

| 接口 | 名称 | 模式 | 计费 |
|---|---|---|---|
| `submit` | 提交任务 | 异步（需轮询） | 按用量（租户价 **0.10 点**；标准价 3.0 点/单位） |
| `query` | 查询任务 | 同步 | 按次固定价 **0.10 点**（租户价） |

**请求地址**

```
POST /api/v1/apps/flashvsr/submit
POST /api/v1/apps/flashvsr/query
```

**鉴权**

```http
Authorization: Bearer <YOUR_API_KEY>
Content-Type: application/json
```

---

## `submit` · 提交任务

**模式**：异步（提交后轮询任务）
**计费**：按用量（租户价 0.10 点；标准价 3.0 点/单位）

创建一条弹性 GPU 任务，返回平台任务 id。

### 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `input_url` | string | **是** | 输入视频文件 URL，待超分辨率处理的视频。例：`https://example.com/low_res_video.mp4` |
| `duration` | number | 否 | 输入视频时长，单位秒；**未传时平台从 `input_url` 探测**。例：`15.695` |
| `mode` | string | 否 | 任务模式，默认 `async_query` |

### 调用示例

```bash
# 用本 Skill 自带的零依赖客户端（推荐）
python3 scripts/a7w.py call flashvsr submit \
  --json '{"input_url":"https://example.com/low_res_video.mp4"}'

# 或者只提交，不等结果
python3 scripts/a7w.py call flashvsr submit \
  --json '{"input_url":"https://example.com/low_res_video.mp4"}' --no-wait
```

```bash
# 直接 curl
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/flashvsr/submit" \
  -H "Authorization: Bearer $A7W_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input_url":"https://example.com/low_res_video.mp4"}'
```

### 返回

```json
{ "task_id": 123, "status": "pending" }
```

`task_id` 为弹性任务主键，拿它去 `query` 查状态，或直接查通用任务接口：

```
GET /api/v1/tasks/{task_id}
```

---

## `query` · 查询任务

**模式**：同步（直接返回结果）
**计费**：按次固定价 0.10 点（租户价）

按弹性任务 id 查询状态与结果。

### 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | integer | 否 | 同 `elastic_task_id` |
| `elastic_task_id` | integer | 否 | 弹性任务 id（与 `task_id` **二选一**） |

### 调用示例

```bash
python3 scripts/a7w.py call flashvsr query --json '{"task_id":123}'
```

---

## 平台官方文档原文

### 提交弹性任务

`POST /api/v1/apps/flashvsr/submit`

在平台「弹性部署」对应应用中配置默认策略后，调用本接口创建 `ai_elastic_task`。

返回示例：`{ "task_id": 123, "status": "pending" }`（task_id 为弹性任务主键）

### 查询弹性任务

`POST /api/v1/apps/flashvsr/query`

根据 `submit` 返回的 `task_id` 查询执行状态与结果。

---

## 使用要点

### 1. `input_url` 必须是公网地址

**不支持本地文件路径，也不支持 Base64。** 平台需要自己去拉这个地址。

本地文件要先传到一个公网可访问的地方（对象存储、CDN、你自己的服务器都行）。

> **这条是最常见的失败原因。** 传 `/Users/me/video.mp4` 或 `D:\video.mp4` 一定报参数错误。

### 2. `duration` 可以不传

不传时平台会从 `input_url` 探测时长。**但传了更稳**——省掉一次探测，也避免探测失败导致的计费偏差。

### 3. 异步任务会预冻结点数

提交时先冻结，完成后按实际用量结算。**不要重复提交同一个任务**——每次提交都可能产生费用。

### 4. 计费口径说明

平台同时给出两套价格字段：

- `fixed_price` / `input_price`：**标准价**，对外公示用
- `tenant_fixed_points` / `tenant_points_per_1k_input`：**你所在租户的实际结算价**

两者可能不一致，**以实际扣费为准**——每次调用返回或报错信息里会写明本次消耗点数，也可以去算力中心核对账单。

本插件实测：标准价 `input_price=3.0`，租户价 `tenant_fixed_points=0.10`。

### 5. 拿不到结果时的排查顺序

1. `GET /api/v1/tasks/{task_id}` 看 `status`
2. `status: failed` → 看 `error.message`，多半是 `input_url` 拉不到
3. 401 → Key 无效，重新 `login`
4. 402 / `code:402` → 点数不足，错误信息里有本次所需点数
