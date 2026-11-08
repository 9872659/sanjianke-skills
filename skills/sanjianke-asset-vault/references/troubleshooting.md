# 排错：按现象找原因

先跑一次 `python3 scripts/run.py doctor`。它会把 Key、余额、价目表、应用目录、上传、任务查询、我的任务、流水
8 个只读探针 + 1 次缺参上传探针全部打勾或打叉，并告诉你是哪一层坏了。**doctor 永远 0 点，可以放心反复跑。**

---

## 一、上传（`upload`）

### `{"code":0,"msg":"请使用 file 字段提交一个文件"}`

字段名必须叫 **`file`**。本包已经用对了；这句话是 `doctor` 的探针返回，说明接口活着、参数校验在工作，不是错误。

### `GET /api/v1/upload` 回 404 HTML

上传只有 POST。`GET` 会掉进前端 SPA 兜底页，返回 `<!DOCTYPE html>`。用 `POST`，`multipart/form-data`。

### 上传成功但 `data.url` 打不开

地址**最长 24 小时**，平台可提前回收（存储回收 / 容量治理 / 安全策略）。
台账里 `ls` 会显示「剩余 x.x 小时」，6 小时内到期会单独提醒。要长期保存就下载转存，别把临时地址写进订单或素材库。

### 同一个文件传了两遍，第二遍没发请求

这是**故意的**：`upload` 按 `sha256 + 大小` 在台账里找未过期的同文件，直接复用地址（0 请求、0 点）。
要强制重传加 `--force`。

### 上传报 `超过单文件 512 MB 上限`

文档默认单文件 512 MB，平台可用 `storage.openapi_upload.max_bytes` 调整。先切分文件，或问服务方当前上限。

### 上传很慢 / 超时

`--timeout` 默认 600 秒（单文件）。大文件或弱网把它调大，例如 `--timeout 1800`。

### Windows 路径带空格

用引号：`--file "D:\素材\产品 图.png"`。`upload` 内部会 `abspath` 规整，不存在路径会退 2。

---

## 二、价格（`catalog` / `cost`）

### 「动态」是什么，为什么不给数字

`cost` 表里的「预算预留」是按规则 `minPoints`（没有就用全局通配保底 50 点）算的，**不是报价**。
真实成交价看 `GET /api/v1/me/tasks` 的 `actualPrice`：`cost --live` 会把它排进表里（source=live）。

### `cost --apps seedance` 显示 11,000 点，超预算

默认 `--budget 5000`（50 元）。`seedance` 固定 11,000 点/次，所以默认会被第二道闸门拦下（退 5，一个请求都不发）。
确认要用就显式加 `--budget 20000`，再 `--yes`。

### `source=baseline` 是什么意思

线上价目表里缺这条键（或你加了 `--offline`），用的是本包内置的 2026-11-08 基线价。联网跑一次就会变成 `source=pricing`。

### `remove` 为什么也要钱

要**免费清理**就用 `prune`：它只删本地台账记录，不碰远端。

### `catalog` 说某应用「应用目录未登记 create」

价目表按路径前缀匹配，所以 `/apps/<app>/create` 都能查到价；但 `GET /api/v1/apps` 里真正登记 `create` 的只有
`happy_horse` / `wan` / `seedance`。其余应用用 `submit`，本包 `bind` 默认就走目录登记的那个入口。

---

## 三、登记（`bind`）

### `失败：这会真实提交素材登记：预计 72 点（0.72 元）… 确认请加 --yes。`（exit 4）

这是第一道闸门，**还没发请求**。确认金额后加 `--yes`；想先看请求体就先 `--dry-run`。

### `失败：预计 11,000 点超过 --budget 5,000 点… 一个请求都没发。`（exit 5）

第二道闸门。调大 `--budget`，或换更便宜的应用（`cost --apps smart_clip,nano_banana,grok_video`）。

### `失败：素材 xxx 的地址已过期…`

台账里这条 `expires` 已过（上传后最长 24 小时）。重新 `upload` 同一个文件（`--force` 可不复用旧地址）再 `bind`。

### `失败：wan 的素材要放进数组 / 对象字段，不能自动注入`

`wan` 的素材字段是 `image_urls[]` / `image_with_roles[]`，`seedance` 是 `content[]`。本包不猜数组结构，要求显式给：

```bash
--param 'image_urls=["https://..."]'
--param 'content=[{"type":"image_url","image_url":{"url":"https://..."}}]'
```

### `失败：<app> 在应用目录里没有 <entry> 这个接口。它有：…`（exit 2）

`--entry` 指定的接口不在该应用的目录清单里。按提示换成列出的某个 code，例如 `smart_clip` 用 `broadcast_mixcut`。

### 提交回 4xx / 422：字段不对

`--dry-run` 先把完整请求体打出来，对照该应用文档（`wan` 要 `model` + `prompt`；`seedance` 要 `content` 或 `model` + 提示词）。
`err_text` 会把上游的 `error.message` / `msg` 原样带出来。

### 提交回 402

点数不足。到 [api.a7w.cn](https://api.a7w.cn/) 充值后重试；本包不会自动重试 POST（避免重复扣费）。

### 提交成功但没看到 `task_id`

不同应用的字段名不统一，本包依次回退 `task_id` / `taskId` / `id` / `TaskId` / `RequestId`。
`--json` 里的 `raw` 是上游原始返回，直接看它。

---

## 四、远端清理（`release`）

### 404 / `not_found`

只有 `watermark_removal` 在应用目录里登记了 `remove`；其余 10 个的 `/remove` 只在价目表里有规则，路由是否可通没有验证。
`release --dry-run` 会明确告诉你「这个应用的 remove 在应用目录里没有登记」。

### 清理一次扣了 100 点

### 我只想清本地记录

用 `prune`（免费）：`prune` 只删台账，`prune --older-than 24` 连超过 24 小时的一起删，`--dry-run` 先看会删哪几条。

---

## 五、本地台账（`ls` / `tag` / `prune`）

### 台账在哪

`~/.a7w/asset-vault/ledger.json`（Windows 是 `C:\Users\<你>\.a7w\asset-vault\ledger.json`）。
只存本机，不上传任何地方；最多保留最近 500 条。

### `本地台账写不进去（…）`

目录权限或磁盘问题。本包会打印警告但**不中断**，本次上传的结果仍然可用（`--json` 里能拿到 url）。
检查 `~/.a7w` 是否可写。

### `找不到这些 id：xxxx`（exit 2）

`tag` / `bind --id` 用的是台账 id（8 位十六进制）。`ls` 第一列就是它；`ls --all` 能看到已过期的条目。

### `ls` 里看不到刚传的文件

默认只列**未过期**的。加 `ls --all`。

### 中文表格错位

`ls` / `catalog` / `cost` 用 `unicodedata.east_asian_width` 按显示宽度补齐（中文算 2 列）。若你的终端把某些字符算成 1 列，
属于终端字体问题，`--json` 不受影响。

---

## 六、Windows / GBK

### 输出里出现 `?`，或 `UnicodeEncodeError: 'gbk' codec can't encode`

本包已做两层防护：`sys.stdout.reconfigure(errors="replace")`，并且全部输出只用 cp936 编得出的字符
（`√` `×` `·` `→` `「」`，不用 `✓` `✗` `¥` `★` `█`）。金额一律写「元」不写符号。
如果仍然出现问号，说明你的终端编码不是 cp936：

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts\run.py doctor
```

### `python` 找不到

用 `py -3 scripts\run.py …` 或把 Python 3.7+ 加进 PATH。零依赖，不需要 `pip install`。

### 每跑一次多出 `__pycache__`

本包在文件里设了 `sys.dont_write_bytecode = True`；命令行前面再加 `$env:PYTHONDONTWRITEBYTECODE="1"` 就彻底不生成。

---

## 七、网络与网关

### `网关 502` / `502 Bad Gateway`

网关或上游临时故障。**只读 GET 会自动退避重试 3 次**（0.8s / 1.6s）；POST 只发 1 次，避免重复扣费。
502 出现在翻页扫描时最正常，隔几十秒再跑即可。

### `连不上 https://api.a7w.cn：…`

DNS / 代理 / 防火墙。先 `curl -I https://api.a7w.cn/api/v1/pricing` 验证网络，再跑 doctor。

### 401

Key 无效或过期。`python3 scripts/a7w.py login --key sk-你的key` 重新绑定，或 `--key` 临时指定。

### 429 / 队列满

应用层排队上限。等一会儿再提交；这是上游限流，不是本包的重试能解决的。

---

## 八、退出码速查

| 退出码 | 含义 | 你要做什么 |
|---|---|---|
| 0 | 成功 | — |
| 1 | 内部错 | 看 stderr 的 traceback，把命令和报错发给技术支持 |
| 2 | 用法错 | 看提示：缺参数 / id 不存在 / 文件不存在 / --param 格式不对 |
| 4 | 需要 `--yes` | 提示里写了要花多少点，确认后加 `--yes` |
| 5 | 预算不足 | 调大 `--budget`，**一个请求都没发** |
| 6 | 调用失败 | 网关/上游返回错误，看原始 message |
| 130 | 被 Ctrl-C 中断 | 已提交的任务用 `GET /api/v1/tasks/<id>` 查，不会重复扣费 |

---

## 九、三个常见误解

1. **「上传免费 = 生成免费」** —— 上传 0 点，`bind` / `release` 照价计费。价目表见 `catalog`。
2. **「remove 就是清理，应该免费」** —— 10 个应用动态 ×2，`watermark_removal/remove` 100 点/次。免费清理只有 `prune`（本地）。
3. **「价目表里有 create，就能直接调 create」** —— 只有 3 个应用登记了 create。`catalog` 会把两个来源并排打出来。

---

## 十、还是要人工看

把这三样发出去，基本能一眼定位：

```bash
python3 scripts/run.py doctor --json
python3 scripts/run.py bind --app <app> --id <id> --dry-run --json
python3 scripts/run.py ls --json
```

`--json` 的失败结构统一是 `{"ok": false, "exit": N, "error": {"kind": "...", "message": "..."}}`，
`kind` 取 `usage` / `gate` / `confirm` / `budget` / `call` / `interrupt` / `internal`。
