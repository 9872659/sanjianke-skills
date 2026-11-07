# 排错：按报错找原因

先按顺序跑这三条，90% 的问题会自己现形：

```bash
python3 scripts/run.py doctor                      # Key / 端点 / 价目表 / 余额没动
python3 scripts/run.py gen --plan ./out/plan.json --dry-run   # 不发请求，只看 body 对不对
python3 scripts/run.py check --dir ./out --platform taobao    # 产物像素、比例、命名
```

`doctor` 的每条检查前面是 `√` 或 `×`，`×` 的那行后面就是原因。

---

## 一、退出码对照

| 退出码 | 含义 | 你该做什么 |
|---|---|---|
| `0` | 成功 | — |
| `2` | 用法错 | 看 stderr 那句「失败：…」，通常是缺必填或尺寸/选项不合法 |
| `3` | `doctor` / `check` 有检查没通过 | 看打 `×` 的那几行；`check` 不花钱，改完再跑 |
| `4` | 需要 `--yes` | 消息里已经写了这一轮要花多少点，确认后加 `--yes` |
| `5` | 超预算 | 一个请求都没发。调大 `--budget`（单位是点）或减少位 |
| `6` | 调用失败 | 带上 HTTP 状态和上游原文，对照下面第二、三节 |
| `1` | 内部错 | 贴完整 traceback 给技术支持 |
| `130` | 被 Ctrl-C 中断 | 已出的图在 `--outdir` 里；异步任务可用 `status --task-id` 接着取 |

`--json` 时失败会是一个文档：
`{"ok": false, "exit": N, "error": {"kind": "…", "message": "…"}}`，
`kind` 取 `usage` / `gate` / `confirm` / `budget` / `call` / `interrupt` / `internal`。

---

## 二、按上游返回找

### `HTTP 422` `String should have at least 1 character`

`prompt` 是空字符串。`doctor` 用的就是这个探针（故意的），你手动调时给一句实际描述即可。

### `HTTP 400` 提到 size / 像素 / 倍数 / 3:1

尺寸不合 gpt-image 的四条硬约束。最常见的两个：

- `800x800`：640,000 像素 < 下限 655,360 → 用 `1024x1024`；
- `750x1000`：750 不是 16 的倍数 → 用 `768x1024`。

本包 `plan` 已经按平台换好，手工传 `--size` 时按第四节那张表来。

### `HTTP 400` / `404` 且返回 HTML

路径不对。图片线必须是 `/api/v1/images/generations`：

```text
✅ https://api.a7w.cn/api/v1/images/generations
❌ https://api.a7w.cn/v1/images/generations      ← 少了 /api，会被路由到默认应用
```

少一个 `/api` 时那台默认应用会**忽略你指定的 model**，照样返回图、照样扣钱。

### `HTTP 200` + `{"code": 0, "msg": "任务不存在"}`

`task_id` 不对或任务已过期。`status --task-id` 换一个 id 再试；`GET /api/v1/tasks/<id>`
本身免费，多查几次不花钱。

### `HTTP 200` + `{"code": 0, "msg": "应用或 API 不可用或未配置价格"}`

这是应用层兜底话术，**不可信**：假的应用代号也返回同一句。判断应用在不在架，
看 `GET /api/v1/apps` 里有没有这个 `code`（本包 `doctor` 就是这么判的）。

### `HTTP 502` + `InvalidMpsUser`

路由在，上游凭据坏了。等一会儿重试；持续这样请找技术支持。

### `WinError 10054` / `ConnectionResetError` / `RemoteDisconnected`

网关重置了空闲连接。本包对网络类和 5xx 都做了 3 次退避重试（`http_json`），
连续失败说明网络真的不通，先 `doctor` 看能不能拿到 200。

### `HTTP 401` / `403`

Key 不对或没读到：

```bash
python3 scripts/a7w.py login --key sk-你的key     # 写进 ~/.a7w/config.json
# 或者
export A7W_API_KEY=sk-你的key                      # Linux / macOS
$env:A7W_API_KEY="sk-你的key"                      # Windows PowerShell
```

优先级：`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。

---

## 三、按「钱」找

### 明明没出图，点数还是少了

先看流水，别猜：

```bash
GET https://api.a7w.cn/user/balance/logs?limit=50
```

`reference` 会告诉你是哪条路径：`sync:/api/v1/images/edits` 是改图（6 点/次），
`sync:/api/v1/apps/nano_banana/query` 是**应用层查询**（72 点/次，最贵的一脚）。

### 轮询把预算烧完了

应用层 `query` 每次 72 点；本包一律用 `GET /api/v1/tasks/<id>`。自己写脚本时也别走
`apps/<app>/query`。

### 想读应用 schema，一读就扣钱

`GET /api/v1/apps/<app>` 是按该应用单价即时结算的（换装 200、出图 72，`sync:` 不退）。
要判断端点存不存在，用免费三件套：`/api/v1/apps`、`/api/v1/pricing`、`/api/v1/models`。

### 冻结了但没扣

异步任务失败会全额退（`netPoints = 0`），冻结期间余额看起来少了，是正常的在途状态。

---

## 四、按「产物」找（`check` 的报错）

### `× 比例偏 2.70%（要 3:4）`

上游按 32 对齐给像素，所以请求 `3:4` 实际可能回 `864x1184`（偏差 2.70%）。
本包容差 3%，这一档算过；要像素级精确就本地裁一刀（裁完再跑 `check` 复核）。

### `× 文件名里没有位号（main/scene/detail）`

文件不是本包命名的。跑一次：

```bash
python3 scripts/run.py names --dir ./out --platform taobao --apply
```

### `× 文件名里的像素与真实像素不一致`

改名时手改了像素、或文件被外部工具重导出过。`names --apply` 会按**文件头**重写。

### `× 缺 main04, main05 …`

`plan.json` 里排了 10 个位，目录里只有一部分。补跑缺的位：

```bash
python3 scripts/run.py gen --plan ./out/plan.json --slot main04,main05 --outdir ./out --yes
```

### `× 3.41 MB 超过 3.0 MB`

图太大。加 `--max-mb 5` 放宽阈值，或出图时换 `--output-format jpeg` 重出一张
（重出会再扣一次点数，先确认预算）。

### 白底位背景是浅灰

`main01` 的提示词里写了「纯白背景」，但模型偶尔给浅灰。重出这一张（6 点），
或者本地抠背。`check` 把它列在「人工确认」里，就是因为像素判定做不了这件事。

---

## 五、Windows 控制台乱码

本包按 `sys.stdout.reconfigure(errors="replace")` 兜底，只用 `√` / `×`（这两个字符
cp936 编得出来），所以在 `chcp 936` 的控制台里不会崩。想彻底避免乱码：

```powershell
$env:PYTHONIOENCODING="utf-8"
chcp 65001
```

重定向到文件时同理；`--json` 输出的是纯 JSON，机器读不受影响。

---

## 六、`--json` 使用要点

- 写在子命令**前后都行**：`run.py --json catalog` 与 `run.py catalog --json` 等价；
- stdout **只有一个** JSON 文档，人读信息全部走 stderr，所以可以直接管道给 `jq`；
- 失败也会给 JSON（带 `exit` 与 `error`），脚本里按 `exit` 分支比按字符串匹配稳。

```bash
python3 scripts/run.py gen --plan ./out/plan.json --json | jq -r '.files[]'
```
