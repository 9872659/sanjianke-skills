# 视频生成台（模型层）—— 排错

**先跑 `python3 scripts/run.py doctor`** —— 免费、不扣费，10 项一次排掉大半问题。
它只发「缺 prompt 的 POST」和只读 GET，全部停在 400，不建任务、不动余额。

---

## 一、Key 相关

### `失败：没有 API Key`（exit 2）

三处都没读到，按优先级查：

1. `--key sk-...`
2. `$env:A7W_API_KEY`（PowerShell） / `$A7W_API_KEY`（bash）
3. `~/.a7w/config.json` 里的 `{"key": "sk-...", "host": "https://api.a7w.cn"}`

最省事：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### `Key 有效 + 余额接口可达` 打 ×，HTTP 401 / 403

Key 本身的问题，到 [api.a7w.cn](https://api.a7w.cn/) 重新创建。

> 只有 `/api/v1/user/balance` 与 `/user/balance/logs` 这两个余额口是通的。
> `/api/v1/user/balance/logs` 会回一个 164 B 的余额对象（没有 `logs` 字段），
> 流水要走**不带 `/api/v1`** 的那条。

---

## 二、提交类报错 → 原因 → 处理

### `{"message":"Model name not specified, model name cannot be empty …"}`（HTTP 400）

`model` 没传。空 body 就长这样。本包的 `gen` 会先本地拦（exit 2），走不到这一步。

### `{"code":"plugin_request_invalid","message":"field prompt is required"}`（HTTP 400）

`muse-video` 缺 `prompt`。这条正好是 `doctor` 的探针之一：**看到它说明端点通、钱包不动**。

### `{"error":"prompt or content field is required","type":"invalid_request_error"}`（HTTP 400）

Seedance 族（`sd/…`、`volcengine/…`）缺 `prompt` / `content`。同样停在参数校验层，不扣费。

### HTTP 502 `百炼提交失败：Access denied …`（只出现在 `wan3.0-video`）

上游阿里云百炼账号没有开通这个模型，或账号欠费。实测这条**会先冻 300 点再退回**：

```
charge -300  reserve_sync:/api/v1/videos
refund +300  refund:submit_failed:/api/v1/videos
```

净 0 点。处理：换 `sd/doubao-seedance-2-0-260128`（实测 145.73 点那条），
或去百炼控制台的「模型广场」把该模型开通。

### `402` / `insufficient balance`

余额不够预冻结。Seedance 两档预冻结 **3,000 点**，Wan 3.0 预冻结 **300 点**。
先看 `cost`，再看 `gen` 的 `--budget` 是否够。

### `失败：报价上限 N 点超过 --budget M 点`（exit 5）

闸门在工作，**一个请求都没发**。`--budget` 单位是**点**（1 元 = 100 点），默认 3500。

```bash
python3 scripts/run.py cost --model sd/doubao-seedance-2-0-260128   # 先看区间
python3 scripts/run.py gen --prompt "…" --seconds 5 --budget 3200 --yes
```

闸门按**区间上限**判定，因为上游的预冻结也是按上限冻的（Seedance 冻 3,000 点）。
报价区间是 145.73 – 3,000 时，`--budget 500` 依然会被拦住 —— 这是故意的。

### `失败：这会真实出片：报价 …`（exit 4）

缺 `--yes`。先看请求：

```bash
python3 scripts/run.py gen --prompt "…" --seconds 5 --dry-run
```

### 提交返回 200 但没 `id`

先看原始返回：本包会把前 600 字打出来。两种常见情况：

1. 返回套了 `{"code":1,"data":{...}}` —— 本包会自动拆一层，不用管；
2. `code:0` + `msg` —— 上游拒了，`msg` 就是原因（余额、模型未开通、内容不合规）。

---

## 三、查询类报错

### `{"code":"task_not_exist","message":"task_not_exist"}`（HTTP 400，`/api/v1/videos/{id}`）

三个可能：id 打错、任务属于别的 Key、这条任务不是视频生成任务的 id。

### `{"code":0,"msg":"任务不存在","data":null}`（HTTP 200，`/api/v1/tasks/{id}`）

通用任务查询没这条记录。先确认 id 没丢字符；本包的 `status` 会把三条路由都试一遍，
三条都空才退 6 并把你试过的三条打出来。

### `404 page not found`（裸文本，不是 JSON）

id 是 **UUID 形态**（Seedance 族），而 `/api/v1/tasks/{id}` 只认 `task_` 开头那种。
换这条：

```bash
curl -s "https://api.a7w.cn/api/v1/videos/generations/<uuid>" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

返回里有 `generation_status`（`succeeded` / `failed` / …）、`delivery_status`、
`video_url`、`video_url_expires_at`，还有 `result.usage.total_tokens`。
本包的 `status` / `wait` 已经自动按「`/tasks` → `/videos` → `/videos/generations`」顺序试。

### `{"error":"task not found","type":"not_found"}`（HTTP 404）

`task_` 开头的 Muse 任务打到了 `/videos/generations/{id}`。这是 Seedance 族的路由，
Muse 任务走 `/videos/{id}` 或 `/tasks/{id}`。

### `status` 一直 `queued` / `in_progress`

正常。视频任务一般 1–15 分钟；`wait --every 15 --limit 3600` 是默认节奏。
到上限还没完成，用 `wait <id>` 接着查 —— **同一个 id 只查不重提**，重提就是再花一次。

### `失败：等了 N 分钟还没完成`（exit 6）

任务没丢，继续 `wait` 同一条即可。任务一旦创建就会跑完，客户端断开不影响它。

---

## 四、钱相关

### 报价显示 `baseline` 是什么意思

`baseline` = 你这套账号**没有**这个模型的成交记录，本包退到本机 2026-11-07 的实测基线
（样本条数写在括号里）。跑过一次之后自动变 `live`，用你自己 `actualPrice` 的区间。

想让报价更快命中 `live`：多读几页台账。

```bash
python3 scripts/run.py cost --pages 40          # 每页 20 条，40 页 = 800 条
python3 scripts/run.py cost --pages 0           # 一页都不读，纯基线，最快
```

### 报价区间为什么是 145.73 – 3,000 这么宽

模型层单价不在价目表里（`/api/v1/pricing` 没有 `modelPricing` 键），
所以只能给区间，没法给一个准数。`cost --model … --seconds …` 会把这个区间、
闸门点数和应用层对照一起打出来。

### 实际扣费比报价低/高

- 低：低秒数、低分辨率那次结得更少（预冻结会退回差额）。

### 失败了会扣钱吗

**不扣。** 文档写明「任务失败全额退回」，实测流水里也能看到
`refund:task_failed:` / `refund:submit_failed:` 把冻结额退回。

### 想确认自己到底花没花

```bash
python3 scripts/run.py log            # 本地台账
curl -s "https://api.a7w.cn/user/balance/logs?limit=50" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

`type=charge` 是扣/冻，`refund` 是退回；`reference` 里带路径，
`reserve_sync:/api/v1/videos` 就是这条模型层线。

---

## 五、`--json` 与退出码

| 现象 | 含义 |
|---|---|
| `{"ok":false,"exit":5,"error":{"kind":"budget",…}}` | 报价上限超预算，一个请求都没发 |
| `{"ok":false,"exit":4,"error":{"kind":"confirm",…}}` | 缺 `--yes` |
| `{"ok":false,"exit":2,"error":{"kind":"usage",…}}` | 参数问题（缺 `--prompt`、秒数越界、缩写） |
| `{"ok":false,"exit":6,"error":{"kind":"call",…}}` | 上游拒绝 / 等待超时 |
| `exit 3`（`doctor`） | 自检出现 ×，看那一行的 HTTP 与错误码 |

`--json` 写在子命令前后都认（`--json gen …` 与 `gen … --json` 等价）；
stdout 只有一个 JSON 文档，进度类文字都走 stderr。

---

## 六、Windows 控制台

输出里出现 `?` 而不是 `√` / `×` / `→`，是这个终端的编码不认这几个符号。
本包已经做了两层兜底：

1. `sys.stdout.reconfigure(errors="replace")`，任何编码下都不会崩；
2. 全文只用 cp936 覆盖得到的符号（`√` `×` `·` `→` `「」` `–`）。

真要看原样，指定编码：

```powershell
$env:PYTHONIOENCODING="utf-8"; python scripts\run.py doctor
```

`PYTHONIOENCODING=gbk` 下 `doctor` 实测 `exit=0`，10 行 `√` 完整打印。

---

## 七、想更省事

```bash
python3 scripts/run.py doctor \
  && python3 scripts/run.py gen --prompt "…" --seconds 5 --yes --wait
```

`doctor` 通过才继续 —— 省掉一次白跑。

---

## 八、联系

照 `SKILL.md` 末尾的「联系我们」找技术微信，附上 `doctor` 的整屏输出和 `log` 里的那一行，
基本一句话就能定位。
