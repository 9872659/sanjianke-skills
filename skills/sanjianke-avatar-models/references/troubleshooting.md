# 排错：按报错找原因

先跑 `python3 scripts/run.py doctor`。11 项里有几项红，基本就定位到问题在哪一层。

---

## 一、提交类报错

### `404 {"error":{"code":"model_not_found",...}}`

**原因**：打到了 `POST /api/v1/videos`。

**修**：改用 `POST /api/v1/videos/generations`。8 个数字人 ID 全部只认这条；
`/videos` 只认 4 个裸视频 ID（muse-video / seedance 两个 / wan3.0-video）。
本包 `gen` 默认就是正确的那条，不用手改。

### `400 {"error":"prompt or content field is required"}`

**原因**：请求体缺 `prompt`。

**修**：`gen` 不带 `--prompt` 时本包会补一句默认提示词；
自己传了空字符串才会撞上这条。想自定义就写清「主体 + 怎么动 + 镜头」。

### `400` 里出现 `image_urls` / `image_url` / `audio_url`

**原因**：字段名给错。`omnihuman-2-0` 要 `image_urls`（数组），其余图驱动型号要 `image_url`（单值），
`volcengine-video-to-video-lip-sync` 要 `video_url`；音频统一 `audio_url`。

**修**：本包按型号自动切换，正常不会撞。手工调接口时对照
`references/api-contract.md` 第 1 节的字段表。

### `401` / `invalid api key`

**原因**：Key 没读到或已失效。

**修**：三选一 —— `--key sk-xxx`、环境变量 `A7W_API_KEY`、`python3 scripts/a7w.py login --key sk-xxx`。
`doctor` 第一项就是 Key + 模型目录，红了先修这个。

### `402 insufficient_points` / `key_quota_exceeded`

**原因**：余额不够或这把 Key 的额度用完。

**修**：`GET /user/balance` 看可用点数；到 [api.a7w.cn](https://api.a7w.cn/) 充值或换 Key。

---

## 二、任务类问题

### `status` 回 `{"code":0,"msg":"任务不存在"}`

**原因**：任务号写错，或任务还没落库（刚提交的几秒内）。

**修**：核对提交返回的 `id` / `task_id`；等 3–5 秒再查。查询本身 0 点，可以多查几次。

### 任务一直 `processing`

**原因**：数字人模型按音频时长跑，10 秒音频通常 1–3 分钟；长音频更久。

**修**：`status --task-id task_xxx` 继续查；`gen --wait` 默认最长等 15 分钟，
不够就把 `--limit` 调大。等待期间只发免费 GET。

### `gen` 提交成功但没拿到成片

**修**：隔 10 秒再 `status` 一次。`--wait --save` 会在拿到地址后自动下载，
下载失败只影响落盘，不影响任务本身。

### 批量横评只成功了一部分

**修**：看 `对比清单.md` 的「状态 / 报错」列；成功的条目照常落盘，
失败的条目用 `log` 对上界，再用 `gen --models 单个型号` 重跑那一条。

---

## 三、报价类问题

### 5 个模型全是 `source=baseline`

**原因**：你账号还没跑过这些型号，`/api/v1/me/tasks` 里没有它们的 `actualPrice`。

**修**：这是正常状态。先用基线报价跑一条，成功后再 `cost` 就会显示 `live`。

### `cost` 合计比实际扣费高

**原因**：`cost` 合计按每个型号的**上界**相加，是预算闸门用的；
实际扣费按音频时长与上游结算，通常低于上界。

**修**：以 `GET /api/v1/me/tasks` 的 `actualPrice` 或 `status` 里的点数为准。

### `--budget` 退 5，但我以为够

**原因**：预算是「每个型号上界相加」。5 个模型 × 10 秒 × 24 点/秒 = 1,200 点。

**修**：调大 `--budget`（单位：点，1 元 = 100 点），或减少 `--models`，或缩短 `--seconds`。
退 5 时一个出片请求都不发。

### 想只跑一条，不想横评

**修**：`gen --models omnihuman-2-0 ...`，一个型号就是一个请求，预算只算它一个。

### `doctor` 显示余额变了，但本包没花钱

**原因**：同一个账户还有别的任务在跑（外部 `gpu:prepay` 或其他会话的提交）。

**修**：看 `doctor` 最后两项：第 10 项报「本包视频线新增 0 条」，第 11 项报「余额变动 = 外部 N 条流水 + 本包 0 点」。本包自己的台账 `~/.a7w/avatar-models-ledger.json` 里没有对应记录，就是外部流水。

---

## 四、上传类问题

### `上传失败（HTTP 400）` / `data.url` 为空

**原因**：文件不存在、超过单文件上限（512 MB）、或网络中断。

**修**：确认路径与大小；重跑一次。上传 0 点，重试不花钱。

### 本地文件没加 `--upload`

**修**：加 `--upload`，本包会先 `POST /api/v1/upload` 换平台地址（oss.gpu.likeadmin.cn，24 小时有效）。
`--dry-run` 不会真上传，只打印占位。

---

## 五、编码类问题

### Windows 控制台里出现 `?` 或乱码

**原因**：stdout 被重定向到管道时，Python 用 cp936 编码；个别符号编不出来会被替换。

**修**：本包已用 `reconfigure(errors="replace")` 兜底，并且正文只用 cp936 覆盖得到的字符
（√ × · → 「」 与中文标点），金额写「元」。仍然看到问号时，显式指定编码：

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -u scripts\run.py doctor
```

或写文件再读：

```powershell
$env:PYTHONIOENCODING = "gbk"
python -u scripts\run.py doctor > doctor.txt 2>&1
```

### `--json` 输出里混了提示行

**原因**：进度提示走 stderr，本来就该分开。

**修**：只要 stdout：`python -u scripts/run.py --json cost ... 2>$null`。
stdout 只有一个 JSON 文档，失败时是 `{"ok": false, "exit": N, "error": {...}}`。

---

## 六、探针红线（花钱买来的）

| 调用 | 后果 |
|---|---|
| `GET /api/v1/apps/<app>` | 命中通配计价，`sync:` 即时扣费、不退 |
| `POST /api/v1/apps/<app>/query` | 每查一次就是一次的钱，历史烧过 15,552 点 |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先冻结再验参再退，净 0 但钱包被短暂动过 |
| `POST /api/v1/videos {"model":"wan3.0-video"}` 缺 prompt | 实测先冻 300 点再退 |

本包的安全区：

```
GET  /api/v1/models  /pricing  /me/tasks  /tasks/<id>  /user/balance  /user/balance/logs
POST /api/v1/upload
POST /api/v1/videos/generations  {}  或  {"model": 数字人 ID}   -> 400，不冻结
POST /api/v1/videos              {"model": 数字人 ID}            -> 404，不冻结
```

`doctor` 的 4 条 POST 探针全部落在这个区间；每次还会做余额前后对比与流水时间戳对比。

---

## 七、还是不通

把这三样发出来，定位最快：

1. `python3 scripts/run.py doctor` 的完整输出（哪几项是 ×）；
2. `python3 scripts/run.py cost --seconds 10` 的报价表；
3. `gen --dry-run` 打出的请求体（里面有端点与字段名，没有真实文件内容）。

Key、余额、任务号这类敏感信息发之前先打码。
