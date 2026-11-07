# 排错：按现象找原因

先跑一条命令，90% 的问题它能自己说清楚：

```bash
python3 scripts/run.py doctor
```

---

## 一、跑不起来

### `失败：没有 API Key。三选一…`（exit 2）

按顺序查：

1. `--key sk-...` 有没有写对（要连同 `sk-` 前缀）
2. 环境变量：Linux/macOS `echo $A7W_API_KEY`；Windows `$env:A7W_API_KEY`
3. 配置文件 `~/.a7w/config.json` 是否存在、`key` 字段是否为空

存起来最省事：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### `run.py: error: unrecognized arguments: --pag`（exit 2）

`allow_abbrev=False`，选项不能缩写，写全 `--pages`。

### `run.py: error: unrecognized arguments`

子命令名写错了。可用：`overview` / `by-path` / `tasks` / `logs` / `balance` / `doctor`。

### `SyntaxError: invalid syntax` 出现在 f-string 或 `match` 上

Python 版本太低。要求 **Python 3.7+**，`python3 --version` 确认一下。

---

## 二、闸门与退出码

### `失败：--budget 是 0 点…`（exit 5）

你把预算压到 0 了。本包每个请求扣 0 点，但 `--budget 0` 等价于「不授权任何调用」。
改成 `--budget 1` 就放行。

### `失败：本次要连发 N 个只读请求（花费 0 点，不会扣款）。确认请加 --yes。`（exit 4）

`--all`（约 70 个请求）或把 `--pages` 调得很大（合计 30 个请求以上）会触发批量扫描确认。
这些请求全是 GET，**扣 0 点**，加 `--yes` 继续。

### `失败：…拉取失败（HTTP 401 / 403 / 429）`（exit 6）

- **401**：Key 无效或已注销，去 [api.a7w.cn](https://api.a7w.cn/) 重新创建一个。
- **403**：这个 Key 没被授权访问该端点，换主账号 Key 再试。
- **429**：翻页太快被限流，把 `--pages` 调小（比如 `--pages 5`），或过一两分钟再来。

---

## 三、数据看着不对

### `by-path` 的覆盖率只有百分之十几

正常。`/api/v1/me/tasks` 每页固定 20 条，`--pages` 默认 25（500 条）。
想让表更全：

```bash
python3 scripts/run.py by-path --all --yes     # 全量 1389 条，仍然 0 点
```

实测 500 条时覆盖 **73.1%** 的权威净花 —— 因为头部几个路径的条数少、金额大，早就全进来了。

### 覆盖率永远到不了 100%

`/api/v1/me/tasks` 最多回 **1389 条**（`limit=2000` 时的 `total`）。
更早的调用、以及直连接口（不走任务台账）的消费只存在总账里。
想按路径看到「全部」，以 `/user/usage` 的 `netPoints` 为准，`by-path` 只是下界。

### `overview` 的「花掉」比「净花」大两三倍

正常。`chargedPoints` 是预扣口径，异步任务先冻全额、结算时再退差额。
**对账认 `netPoints`**，那是真花。

### 某一行「净花」是负数

异步任务跨期结算的冲回：上一期冻结的钱这一期才退回来，退款落在本期、扣费落在上期。
负值不代表「赚了」，只是这一行的钱在时间上错开。

### `refunded` 状态的任务，`actualPrice` 还是 72

`actualPrice` 是标价 / 预留，任务失败后走 `netPoints = 0`。判断「钱退没退」看 `netPoints` 和 `refundedPoints`。

### `sumPoints` 和 `/user/usage` 的 `chargedPoints` 对不上

两个端点的窗口不同：`me/tasks` 的 `sumPoints` 是「最近 `limit` 条任务」的合计，
`/user/usage` 是「最近 N 天」的合计。要比就比 `/user/usage`、`/api/v1/me/billing`、流水 `balanceMoving` 这三方。

### `balance` 里 `expected` 和 `actual` 差了几十亿

那是 `check` 的验算：`expected = 充值 + 赠送 − 净消费`，不含充值以外的额度
（活动赠送 / 测试额度 / 历史手工调整）。余额远大于 `expected` 就是账户里有这类额度。

### `logs` 里 `path` 一片空

`path` 字段实测 100 条里只有 7 条有值，路径藏在 `reference` 里。
本包 `logs` 命令已经自动从 `reference` 里抽出路径（`reserve_sync:<path>` / `refund:sync:<path>`）。

---

## 四、网络

### `失败：连不上 …：[WinError 10054] 远程主机强迫关闭了一个现有的连接`

网关在长翻页时会掐连接。本包已内置 **3 次重试**（退避 0.5s / 1.2s），重试的也全是 GET。
连续失败时把 `--pages` 调小再跑。

### `失败：请求异常：TimeoutError`

网络慢。翻页批量扫描时改用 `--pages 5` 分批跑。

### 公司代理 / 自建网关

```bash
python3 scripts/run.py overview --host https://你的网关地址
```

`--host` 只影响请求地址，不改变路径规则（都是 `<host>/api/v1/...` 和 `<host>/user/...`）。

---

## 五、输出

### 中文在 Windows 控制台是乱码

```powershell
$env:PYTHONIOENCODING="utf-8"
python -u scripts\run.py overview
```

### 表格没对齐

中文字符是双宽字符，终端字体不统一时会错位。用 `--json` 取数，自己排版最稳。

### 想把结果存成文件

```bash
python3 scripts/run.py by-path --json > billing.json
```

`--json` 时 stdout 只有一个 JSON 文档，进度和错误都走 stderr。

### 跑完目录里多出 `__pycache__`

本包已设 `sys.dont_write_bytecode = True`。若仍出现，是别的脚本生成的，直接删掉即可。
最省事的做法是每次先 `export PYTHONDONTWRITEBYTECODE=1`（Windows：`$env:PYTHONDONTWRITEBYTECODE="1"`）。
