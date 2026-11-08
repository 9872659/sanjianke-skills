# 商品视频 —— 排错

**先跑 `python3 scripts/run.py doctor`** —— 免费、不扣费，4 个只读 GET 就能排掉大半问题。

---

## 一、Key 相关

### `失败：没有 API Key。三选一…`（exit 2）

三处都没读到。按优先级检查：

1. `--key sk-...`
2. `$env:A7W_API_KEY`（PowerShell）/ `$A7W_API_KEY`（bash）
3. `~/.a7w/config.json` 里的 `{"key": "sk-..."}`

最省事：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### `Key + 余额接口可达` 打 ×，HTTP 401 / 403

Key 本身的问题。到 [api.a7w.cn](https://api.a7w.cn/) 重新创建。

> 平台会直接 403 并告诉你该用哪个（`upstream_account_scope_blocked`）。

---

## 二、报错 → 原因 → 处理

### `{"code":0,"msg":"任务不存在","data":null}`（HTTP 200）

`status` 拿到的就是这个。两种可能：

1. `--task-id` 抄错了（`task_` 后面一长串，别漏字符）。
2. 任务属于**别的应用**（比如视频后处理任务要用 `/api/v1/video/viapi/result/<id>` 查，
   通用 `/tasks/<id>` 不认）。

`doctor` 就是拿假 id 验这条路由：返回「任务不存在」= 路由在且不扣费。

### `{"code":0,"msg":"当前请求未命中可用计费规格…"}`

参数组合没有对应价格档。常见于：`resolution` 传了普通模型没有的档（`nano-banana` 普通版只出 1K）、
`model` 名字拼错、`duration` 不在 4~15。`catalog` 会打出每个接口的可用档位。

### `{"code":0,"msg":"缺少必填参数…"}`

最少要给的字段：

| 子命令 | 必填 |
|---|---|
| `scene` | `--prompt` |
| `clip` | `--text` |
| `voice` | `--text` |
| `make` | `--image` + `--text` |
| `seedance --action create` | `--text` |
| `seedance --action group` | `--name` |
| `seedance --action asset` | `--url` + `--group-id` + `--asset-type` |
| `seedance --action get/delete` | `--asset-id` |
| `seedance --action update` | `--asset-id` + `--name` |

本包会先在本地拦下并退 `2`，不会白跑一次请求。

### `失败：--duration 取 4~15 的整数秒（当前 20）`（exit 2）

`full_video` 与 `seedance` 都只收 **4~15 的整数秒**。20 秒请拆成两条，或让成片循环。

### `失败：预计 11000 点超过 --budget 3000 点…一个请求都没发`（exit 5）

`seedance` 是 11,000 点/次，比默认预算高。真要用就：

```bash
python3 scripts/run.py seedance --action create --text "…" --budget 12000 --yes
```

素材管理 5 个接口也按 11,000 点/次保守估算（价目表 `/api/v1/apps/seedance/*` 通配），所以同样卡住。
只想看请求长什么样，加 `--dry-run`（两道闸门都放行，不发请求）。

### `失败：这会真实扣费约 168 点（1.68 元）…确认请加 --yes。`（exit 4）

不是报错，是第二道闸门。确认金额没问题再加 `--yes`。

### `失败：查不到任务 task_xxx：任务不存在`（exit 6）

任务 id 不存在或不属于当前 Key。用 `log` 看本地台账里记的 id，或者去控制台任务列表核对。

### `连不上 https://api.a7w.cn/…：timed out（已重试 2 次）`（exit 6）

网络或网关抖动。`http_json` 对 502/503/504 与连接重置退避重试 3 次（2s / 4s / 6s），
仍失败就是网关侧问题，隔一会儿再跑。**重试只发生在 GET / 提交成功后拿不到响应的情况**，
`task_id` 已经拿到时不要重新提交（会再扣一次）。

### `查不到任务，试过 N 条查询路由…`（视频后处理那类任务）

本包只用 `GET /api/v1/tasks/<id>`。如果 id 来自 `sanjianke-video-lab` 那类包，
要回那个包的 `status` 子命令查（`/api/v1/video/viapi/result/<id>`）。

---

## 三、形状类问题

### 成片出来了，但 `videoUrl` 是 `null`

任务可能还在跑。`status` 的 `status` 字段：`completed` / `failed` / `processing` / `SUCCESS`。
- `processing`：等 30 秒再查。
- `failed`：看 `message` / `fail_reason`；按秒档任务失败**全额退回**。
- `completed` 但没 URL：`status --json` 看 `raw`，把字段名反馈给我们。

`pick_asset` 会按扩展名（`.mp4/.mov/.webm/.m4v`、`.png/.jpg/…`、`.mp3/.wav/…`）找，
再按字段名含 `video`/`image`/`audio` 兜一层，所以不同应用的不同返回结构都能取到。

### 语音同步接口返回里没有 `audio_url`

`tts` 是同步接口，正常直接回 `data.audio_url`。如果走的是 `tts_async` / `tts_live`，
返回的是 `task_id`，要用 `status` 查。本包 `voice` 只用同步的 `tts`。

### 字幕时间和配音对不上

`script` 是按**字数比例**分配时间的估算，不是强制对齐。两种处理：

1. 口播文案本身分好句（每句 8~15 字），时间轴会更贴近实际停顿。
2. 先出配音，再用 `ffmpeg -i voice.mp3 -f srt` 之类的语音识别路线对齐（那是另一条链路）。

### `ffmpeg: command not found`

字幕与配音的**合成**在你本机跑，不在接口里。装 ffmpeg，或用剪映 / Premiere 导入
`clip.mp4` + `voice.mp3` + `shop.srt` 三条轨道。

---

## 四、编码类问题（Windows）

### 控制台里中文变成 `?` 或方块

本包已经做了两层兜底：`sys.stdout.reconfigure(errors="replace")`，并且**只用 `√` / `×` / `·` / `→`**
这些 cp936 里有对应码位的符号（没有 `✓` / `✗`）。如果还是花屏，是终端代码页的问题：

```powershell
chcp 65001
$env:PYTHONIOENCODING = "utf-8"
```

### 在 Git Bash / MSYS 下管道输出报 `UnicodeEncodeError`

同上，加 `PYTHONIOENCODING=utf-8`。本包自身不会因为编码崩，`errors="replace"` 已经把这条堵住。

---

## 五、费用类

### 想先确认「这条要花多少」

```bash
python3 scripts/run.py cost --duration 6 --resolution 768P --chars 24
python3 scripts/run.py make --image 商品图.jpg --text "…" --dry-run   # 把 3 个请求全打出来
```

### 钱花超了

`--budget` 是本地闸门：预计点数 > `--budget` 时**一个请求都不发**。默认 3000 点（30 元）。
按秒档提交时按 `duration` 预冻结，完成后按实际时长结算，任务失败全额退回。

### 想知道最近花了多少

```bash
python3 scripts/run.py log --limit 20
```

本地台账记的是**预估值**；真实扣费以 `GET /api/v1/tasks/<id>` 里的 `usage.points_cost` 与
余额流水为准（对账可用 `sanjianke-billing` 那套只读端点）。
