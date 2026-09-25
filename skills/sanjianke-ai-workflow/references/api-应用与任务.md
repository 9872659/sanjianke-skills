# 生成应用与异步任务

模型网关（`/api/v1/chat/completions`）只解决「一段文本」。
出图、出视频、做数字人、配音、做音乐、文档问答属于**生成应用**，走另一条入口。

## 入口路径（唯一正确写法）

```
POST https://api.a7w.cn/api/v1/apps/<应用代号>/<接口代号>
```

> ⚠️ **不要用平台的 `endpoint_path` 字段拼 URL。** 它对某些应用是错的上游路径
> （如 `seedance` 给的是 `/ant/xxx`、`smart_clip` 给的是 `/v1/clip/xxx`），照着拼打不通。
> 两个代号都来自接口返回的 `code` 字段。

## 21 个生成应用

| 类别 | 应用代号 | 能干什么 |
|---|---|---|
| **文档** | `file_qa` | 长文档问答、要点抽取、条款比对 |
| **图片** | `nano_banana` | 文生图、图生图、改图 |
| **视频** | `full_video`、`happy_horse`、`grok_video`、`wan`、`seedance` | 文生视频、图生视频 |
| **数字人** | `image_human`、`pic_lipsync`、`lipsync` | 照片说话、口型对齐 |
| **剪辑** | `action_transfer`、`person_replacement`、`dressing_diffusion`、`smart_clip`、`flashvsr` | 动作迁移、换人、AI 换装、智能剪辑、超分 |
| **音频** | `voice_tts`、`music_generation`、`music_search`、`mmaudio`、`seedsvc` | 文字转语音、音色克隆、语音转文字、音乐生成与检索 |

```bash
# 实时清单与每个应用的接口、参数、同步/异步标记
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema nano_banana
```

## 异步任务的生命周期

标准四步：

```bash
# 1. 提交任务 → 拿到 task_id
python3 scripts/a7w.py call full_video generate \
  --body '{"prompt":"一只猫在窗台上晒太阳"}' --no-wait

# 2. 查任务（免费）
python3 scripts/a7w.py task tsk_xxxxxxxx

# 3. 也可以让客户端自动轮询到结束
python3 scripts/a7w.py call full_video generate --body '{"prompt":"…"}'

# 4. 产物落在 result 里，直接下载
python3 scripts/a7w.py call full_video generate --body '{"prompt":"…"}' --out 成片.mp4
```

提交成功返回：

```json
{ "task_id": "tsk_xxx", "status": "pending", "created_at": 1740000000 }
```

轮询 `GET /api/v1/tasks/{task_id}`，**终态看 `status`**：

| `status` | 含义 |
|---|---|
| `pending` / `running` | 还在跑，继续等 |
| `completed` | 成功，产物在 `result`，用量在 `usage` |
| `failed` | 失败，冻结点数全额退回 |
| `cancelled` | 已取消 |

## 回调替代轮询

提交时带 `callback_url`，任务完成后平台向该地址 POST JSON：

```json
{ "task_id": "tsk_xxx", "status": "completed", "result": { } }
```

你的接口返回 **2xx** 即算接收成功，否则按你在**用户中心 → 回调配置**里设的次数重试
（**1–10 次可配**）。

## 容错与幂等（重要）

- **异步任务在提交时就预冻结点数**，完成后按实际用量多退少补。
- **不要重复提交同一个任务** —— 每次提交都可能产生费用。
  网络超时先查 `task_id`，确认没在跑再决定要不要重提。
- **长任务轮询会被网关重置连接**（`WinError 10054`），这是长连接的正常现象。
  包里 `scripts/a7w.py` 已对网络类错误做**退避重试 4 次**，不必自己再包一层。
- **回调地址一定要返回 2xx**，否则平台按配置次数重试，容易重复消费。

## 任务列表与结算

```bash
python3 scripts/a7w.py points
```

- 任务列表的结算字段是 **`actual_points`**。
- **`page_size` 会被上游忽略**，翻页请用 `--page-no`。

## 参数从哪来

```bash
python3 scripts/a7w.py schema voice_tts
```

输出里每个接口都会标注：

- **`call_type`**：`1` = 同步，`2` = 异步
- **`method`**：`POST` 或 `GET`
- **参数**：名字、类型、必填与否

> **`params_schema` 有两种形态**：一种带 `properties` 包装，一种是扁平字典。
> 只认 `properties` 会把「有 6 个参数」误判成「无参数」。客户端已两种都解析。

## 结果转存

产物 URL 默认由平台提供。需要长期保存时：

- 用 `--out 文件` 直接落盘；
- 或由平台**转存到七牛 / 阿里云 OSS / 腾讯云 COS**，链接不过期，不用二次搬运。
