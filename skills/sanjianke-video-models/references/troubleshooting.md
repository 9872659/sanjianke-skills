# 排错：按报错找原因

先跑一遍自检，多数问题它会直接指出来：

```bash
python3 scripts/run.py doctor
```

`doctor` 发 6 个只读 GET + 3 个必然 400 的探针（空 body、缺 prompt、走错路由），
不建任务、不冻结，输出末尾还会给你余额前后对比与流水净额。

---

## 一、提交阶段的 404

### `404 {"error":{"code":"model_not_found","message":"The model \`xxx\` does not exist or you do not have access to it."}}`

**原因**：型号打到了 `POST /api/v1/videos`。这条路由只认 4 个裸模型层 ID：
`muse-video`、`sd/doubao-seedance-2-0-260128`、`volcengine/doubao-seedance-2-5-260628`、`wan3.0-video`。

**修**：目录型号（kling / veo / hailuo / vidu / runway / pixverse / grok / minimax）走
`POST /api/v1/videos/generations`。本包默认就是这条，`--route auto` 会按型号的历史成功路径分流。

```bash
python3 scripts/run.py gen --models kling-4-0 --prompt "…" --route generations --yes
```

### `404` + HTML（`<!DOCTYPE html>` / SPA 兜底）

**原因**：这个前缀下根本没有注册路由，返回的是前端单页兜底页。

**修**：核对路径拼写。视频生成只有两条：`/api/v1/videos`、`/api/v1/videos/generations`；
任务查询是 `/api/v1/tasks/<id>`。

---

## 二、提交阶段的 400

### `400 {"error":"model field is required"}`

**原因**：`/videos/generations` 的 body 里没有 `model`。

**修**：`--models` 至少给一个，例如 `--models muse-video`。

### `400 {"error":{"message":"Model name not specified, model name cannot be empty ..."}}`

**原因**：`/videos` 的 body 里没有 `model`（这条路由先查 model，再查 prompt）。

**修**：同上。只给了 `{"prompt": …}` 也会得到这一句。

### `400 {"error":"prompt or content field is required"}`

**原因**：型号已解析，缺 `prompt`。这是「型号在这条路由上可用」的正常返回，**没有扣费**。

**修**：补 `--prompt`。写清三件事：主体是什么、怎么动、镜头怎么走。

### `400 {"code":"plugin_request_invalid","message":"field prompt is required","data":null}`

**原因**：`muse-video` 在 `/videos/generations` 上走的是插件通道，缺 prompt 时用这个句式报错。
含义和上一条一样：型号认了、缺 prompt、0 点。

**修**：补 `--prompt`。

### `400 url_not_allowed` / `videoUrl 必须是本站…`

**原因**：把外站地址塞进了 `videoUrl`（视频后处理线才会遇到）。

**修**：先 `POST /api/v1/upload`（免费）拿 `data.url`，再提交。本包做文生视频不涉及这个字段。

### `401` / `403`

**原因**：Key 无效、被禁用，或余额为 0。

**修**：`python3 scripts/a7w.py login --key sk-你的key`，或用 `--key` / 环境变量 `A7W_API_KEY` 覆盖；
`GET /user/balance` 看一眼 `available_points`。

### `429`

**原因**：短时间提交太密。

**修**：本包在 `gen` 里是串行提交，间隔几秒再试；或减少 `--models` 个数。

### `502` / `503` / `504`

**原因**：上游通道抖动。`gen` 已经对 502/503/504 做过一次退避重试。

**修**：重跑同一个命令。已经拿到 `taskId` 的任务**不要重提** —— 重提就是再花一次钱，
用 `status` / `wait` 接着取。

---

## 三、查询阶段的报错

### `{"code":0,"msg":"任务不存在"}`

**原因**：三种可能 —— ① id 写错；② 任务还在排队、查询路由暂时没有；③ 这个 id 属于另一条业务线。

**修**：`taskId` 原样复制（不要去掉前缀）；`wait` 会按间隔重试到超时；
再不行用提交时返回的完整 id 去 `status` 查。

### 成片链接打不开（403 / 404 / 过期）

**原因**：成片地址约 30 分钟有效。

**修**：重新 `status` 一次拿新链接，或者一开始就加 `--wait`，本包会在完成时直接下载到本地。

### `wait` 一直等到 `timeout`

**原因**：长片（秒数大）耗时更久，也可能排队。

**修**：任务本身不会因为超时而失败，接着等：

```bash
python3 scripts/run.py wait task_xxx --outdir . --limit 3600
```

---

## 四、本包自己抛的错

| 提示 | 原因 | 修 |
|---|---|---|
| `预计 X 点超过 --budget Y 点`（exit 5） | 上界合计超预算，**一个请求都没发** | 调大 `--budget`（单位：点）或减型号 |
| `这会真实出片：N 个模型，按上界约 X 点`（exit 4） | 没给 `--yes` | 确认金额后加 `--yes`；只想看请求用 `--dry-run` |
| `本包还没有这些型号的基线：…`（exit 2） | 型号不在 13 个内置名单里 | 用 `catalog` 里的名字；确要试就加 `--allow-any-model` |
| `一次最多横评 8 个型号`（exit 2） | `--models` 太长 | 拆成两次 |
| `--size 写成 宽x高`（exit 2） | 尺寸格式不对 | `1280x720` / `720x1280` |
| `没有 API Key`（exit 2） | 三处都没配 | `a7w.py login` / `A7W_API_KEY` / `--key` |
| `--extra 要是 JSON 对象`（exit 2） | 透传字段写错 | `--extra '{"ratio":"9:16"}'` |

---

## 五、报价相关的疑问

### 为什么 `cost` 里有的型号是「基线 / 同路区间」而不是一个数

`GET /api/v1/pricing` 的 115 条规则里没有模型层路径，模型层真实单价只在
`GET /api/v1/me/tasks` 的 `actualPrice` 里。你账号没跑过的型号就没有样本，
本包只能用同路 16 笔成交区间（44 - 3,045.71 点）估，并标 `source=baseline`。
跑成功一次之后，下一次 `cost` 就会变成 `实测`（`source=live`）。

### 为什么闸门按上界判定

上游按模型预冻结，冻结额通常贴着上界。按上界判定，最坏情况也是「刚好不超支」。

### 报价看着像缓存没更新

本机价格缓存 6 小时。加 `--refresh` 强制重扫；`--pages` 加大扫描窗口
（每页 20 条，`--pages 70` 覆盖全部 1,398 条台账）。

### 为什么 `--seconds` 改了价格却没变

只有写死单价的档按秒结算（`muse-video`：11 点/秒）。其余型号的 `actualPrice`
是整条成交价，`--seconds` 只影响请求参数，不参与本包报价。

---

## 六、中文乱码

```powershell
# Windows 管道/重定向时 Python 用 cp936，个别符号编不出来就会崩
$env:PYTHONIOENCODING = "gbk"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -u scripts\run.py doctor
```

本包脚本已 `reconfigure(errors="replace")` 兜底，全文只用 cp936 覆盖得到的
`√ × · → 「」` 与中文标点；金额一律写「元」。实测 `PYTHONIOENCODING=gbk` 下
`doctor` / `cost` / `catalog` 全部 exit 0，严格解码 0 个问号。

---

## 七、还搞不定时，把这些贴出来

```bash
python3 scripts/run.py doctor --json          # 10 项自检 + 余额 + 流水净额
python3 scripts/run.py cost --json            # 报价明细与来源
python3 scripts/run.py log --limit 20         # 本地台账（含失败原因）
```

`log` 里每条都带 `status` / `taskId` / `上界` / `实际点数` / `error`。
失败记录不会丢，方便对账。
