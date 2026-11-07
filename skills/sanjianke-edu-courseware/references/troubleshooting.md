# 排错：按报错找原因

先跑一次免费自检，多数问题它能直接指出来：

```bash
python3 scripts/run.py doctor
```

---

## 一、Key 与权限

| 现象 | 原因 | 处理 |
|---|---|---|
| `没有 API Key`（exit 2） | 三个来源都没取到 | `--key` / `$env:A7W_API_KEY` / `python3 scripts/a7w.py login --key sk-…` |
| `HTTP 401` / `Unauthorized` | Key 错、过期、带空格 | 重新复制 Key，`a7w.py login` 覆盖 |
| `HTTP 403` | Key 没有该应用权限 | 到 [api.a7w.cn](https://api.a7w.cn/) 控制台看应用授权 |
| `{"error":{"message":"点数余额不足"}}` | 余额不够这一次冻结 | 充值，或把 `--budget` 调到真实余额以内先跑小样 |

---

## 二、两道闸门主动拦下（不是故障）

| 退出码 | 报错 | 含义 |
|---|---|---|
| `4` | `… 预计 N 点（M 元）。确认请加 --yes` | 少了确认；看清点数再补 `--yes` |
| `5` | `… 超过 --budget N 点。一个请求都没发` | 预算不够；调大 `--budget` 或缩秒数 / 张数 |
| `2` | `unrecognized arguments` / 缺参数 | 参数名写错、选项缩写被拒；看 `--help` |

`--dry-run` 只打印请求体，不提交、不冻结、不扣费，适合先对一遍参数。

---

## 三、四个接口的典型报错

### 1. 文生图 422 / 400

```
422 {"error":{"message":"prompt: String should have at least 1 character"}}
```

- 空 prompt 的 422 是 `doctor` 故意探出来的，属于正常。
- 尺寸不合规返回 400：宽高都要 16 的倍数、长短边不超过 3:1、单边不超过 3840、
  总像素 655,360–8,294,400。本包默认 `1536x864` 已在这条线内。

### 2. 配音

| 报错 | 原因 | 处理 |
|---|---|---|
| `text 不能为空` / 缺 text | 既没给 `--text`，`--lesson` 里也没有讲稿 | 先 `lesson` 生成，或直接 `--text` |
| `reference_id 不存在` | 音色 ID 抄错 / 不是本账户 | 用克隆接口返回的 `model_id` |
| 任务一直 `pending` | 长文本排队 | 继续 `status`，不要改用应用层 `/query` |

### 3. 一图口播（pic_lipsync）

| 报错原文 | 原因 | 处理 |
|---|---|---|
| `请提供 image_url` | 少图 | `--image-url`，本地图先 `upload` |
| `text 模式请提供 audio_url 作为参考音色` | 以为文案驱动就不用音频 | `--audio-url` 给 3–10 秒清晰人声 |
| 任务失败且已退款 | 图片人脸不清晰 / 多人 / 侧脸 | 换单人正脸图，`quality=standard` 重试 |
| 账单比预估高 | 没传 quality，按 standard 3 点/秒 ×5 | `--quality` 显式给，`cost` 再核对 |

### 4. 课件出片（image_human）

```
{"code":0,"msg":"无法从该地址下载媒体，请确认链接可公网访问、未过期，且允许本平台服务器拉取（防盗链/OSS 权限需放行）。 详情：Could not resolve host: example.invalid"}
```

- 地址必须公网可拉：本地文件先 `upload`，拿到 `oss.gpu.likeadmin.cn/openapi/…` 再提交。
- 输出比预期贵一档：检查 `--mode` 是否显式给了；省略时出片 standard、计费 fast。
- 180 秒以上建议分节提交：一节一条任务，失败只重跑一节。

---

## 四、轮询与「越查越贵」

| 现象 | 原因 | 处理 |
|---|---|---|
| 余额莫名下降，任务却没多 | 用了应用层 `/query` 轮询 | 只走 `GET /api/v1/tasks/{id}`；本包已把 `/query` 拦死 |
| `查询失败 404` 且返回 HTML | 路径前缀不对 | 用 `status --task-id`，不要手拼 URL |
| `查不到任务` | task_id 抄错 / 任务属于另一个 Key | 核对 `log` 里的 taskId |

---

## 五、课件文件与拆课

| 现象 | 原因 | 处理 |
|---|---|---|
| `大纲里没有 ## 分节 标题` | 大纲用了 `###` 或纯文本 | 每节用 `## 第N节 标题` 起一行 |
| 某节讲稿为空 | 该节只有知识点 | 本包会用知识点拼一句；想更自然就补 `- 讲稿：` |
| 时长算出来偏短 | 没写 `- 时长：` | 加 `- 时长：180`，或全局 `--seconds` |
| 文件名全是 `edu-` | 课程名是中文，`--slug` 没给 | 加 `--slug buoyancy` 之类英文短名 |
| 配图提示词重复度高 | 每节都写同一句 `- 配图：` | 每节写不同的画面描述，风格前缀由 `deck` 统一加 |

---

## 六、Windows 控制台

| 现象 | 原因 | 处理 |
|---|---|---|
| 输出里出现 `?` 或个别符号变方框 | 控制台是 cp936，个别字符编不出 | 本包已 `reconfigure(errors="replace")`；想全对就 `chcp 65001` |
| 跑一次多出 `__pycache__` | 没设环境变量 | 每条命令前 `$env:PYTHONDONTWRITEBYTECODE="1"` |
| 中文路径传参被截断 | PowerShell 引号 | 路径加双引号，整条命令用单引号包 |

---

## 七、`--json` 读法

```json
{"ok": true, "taskId": "task_xxx", "estimatedPoints": 1800}
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

- `kind`：`usage` / `gate` / `confirm` / `budget` / `call` / `interrupt` / `internal`
- 失败时 `exit` 与进程退出码一致，脚本里可以直接判断 `ok`
- `--json` 放子命令前后都行，stdout 只有一个 JSON 文档，日志走 stderr
