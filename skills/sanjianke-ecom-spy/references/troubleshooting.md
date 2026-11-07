# 带货素材侦察 —— 排错

**先跑 `python3 scripts/run.py doctor`** —— 免费、0 点、6 项一次排掉大半问题。

---

## 一、Key 相关

### `失败：没有 API Key`（exit 2）

三处都没读到。按优先级检查：

1. `--key sk-...`
2. `echo $env:A7W_API_KEY`（PowerShell） / `echo $A7W_API_KEY`（bash）
3. `~/.a7w/config.json` 里的 `{"key": "sk-..."}`

最省事：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### `Key 有效 + 余额接口可达` 打 ×，HTTP 401 / 403

Key 本身的问题。到 [api.a7w.cn](https://api.a7w.cn/) 重新创建。

> `/user/balance` 是免费的用户接口；上游账号级路径（`/user`、`/user/usage` 的某些形态）
> 平台会直接 403 并提示该用哪个，本包不碰。

---

## 二、报错 → 原因 → 处理

### `失败：抖音搜索（douyin_search_video）缺必填参数：--keyword`（exit 2）

必填没给。**本包在本地就退回，一个请求都没发，0 点。**
参数表看 `catalog`，或 `references/api-contract.md` 第二节。

### `失败：预计 100 点超过 --budget 0 点…一个请求都没发`（exit 5）

`--budget` 单位是**点**（1 元 = 100 点），默认 1000 = 10 次调用。
`--budget 0` 等于不授权任何调用。

### `失败：这会真实调用 …，扣 100 点（1.00 元…）`（exit 4）

缺 `--yes`。想先看请求：

```bash
python3 scripts/run.py hunt --platform dy --keyword "收纳盒" --dry-run
```

### `失败：…被上游拒绝（code=0）：…`（exit 6）

信封是 HTTP 200，但 `code` 不是 1 —— 业务层拒绝。常见原因：

| 上游 `msg` 里出现 | 原因 | 处理 |
|---|---|---|
| 参数 / 缺失 / required | 参数名或类型对不上 | 参数名大小写逐字照 `api-contract.md`（`videoId` 不是 `video_id`，`secUid` 不是 `secuid`） |
| 不存在 / not found | ID 打错，或内容已删 | 重新从分享链接里取 ID |
| 频繁 / 限流 / 稍后 | 上游限流 | 隔几十秒重试；一次调用 100 点，重试前先确认参数没问题 |
| 未配置 / 不可用 | 应用临时下线 | 跑 `doctor`，第 3 项会直接看出来 |

### `失败：…调用失败（HTTP 404）：网关回了 HTML…`

路径打错。本包不会走错（8 条路径写死），手工 `curl` 时记得是
`/api/v1/apps/watermark_removal/<code>`，**不是** `/api/v1/<code>`，
也**不是**上游内部路径 `/justone/<code>` / `/zyf.php`。

### `失败：…返回不是 JSON：…`

网关回了一段非 JSON（多为网关层 5xx 的 HTML）。`http_json` 已对 502/503/504 退避重试 2 次；
仍然如此就是网关侧问题，隔几分钟再来，`doctor` 能看到流水与余额是否正常。

### `失败：没有快照 / 快照里没有条目`（exit 2）

`rank` / `breakdown` / `clone` / `cover` 读的是**本地快照**，得先采一次：

```bash
python3 scripts/run.py hunt --platform dy --keyword "你的词" --yes   # 100 点
python3 scripts/run.py rank                                          # 之后 0 点
```

指定别的快照：`--snapshot ~/.a7w/ecom-spy/snapshots/20261107-215530-douyin_search_video.json`。

### 这次没解析出条目（打印了原始返回前 800 字）

选品词太偏、上游返回了空列表，或者返回结构里有本包还没认的字段名。
先看打印出来的 JSON：

- 里面**有**标题和点赞 → 是字段名没认出来，`--json` 拿完整 `raw`，
  按 `api-contract.md` 第四节改 `run.py` 的 `norm_item()`（一处即可）；
- 里面**是空数组 / `data:null`** → 这个词真没结果，换个词（一次 100 点，别硬试）。

---

## 三、钱相关

### 一次调用到底扣多少

**100 点 = ¥1.00**，flat，与返回条数无关。规则原文：

```
"/api/v1/apps/watermark_removal/*": {"mode":"flat","cost":100,
  "note":"去水印/分享链解析：固定 100 点/次（上游按请求 20 点，失败亦计）"}
```

### 失败了会退吗

规则 note 写「**失败亦计**」—— 按平台口径，失败的请求也算一次。
所以本包把「参数齐不齐」「预算够不够」「有没有 `--yes`」全部前置到本地，
把无效请求挡在发出去之前。

### 想确认自己到底花了多少

本地台账：

```bash
python3 scripts/run.py log
```

服务端流水（免费）：

```bash
curl -s "https://api.a7w.cn/user/balance/logs?limit=20" -H "Authorization: Bearer $A7W_API_KEY"
```

看 `sync:/api/v1/apps/watermark_removal/...` 的行，每行 `-100`。
**注意**：这里的 `-100` 是流水口径；`balanceMoving` 才是净变动。
（`netPoints` 会把预扣与退款来回都算进去，对账看 `balanceMoving`。）

### 想少花

| 目标 | 最省跑法 | 花费 |
|---|---|---|
| 只想看看有没有爆款 | `hunt --platform dy --keyword … --yes` | 100 点 |
| 要看 3 条详情 | 搜索 1 次 + `dy-video` 3 次 | 400 点 |
| 盘一个号的全部选题 | `dy-user` / `xhs-user-notes` 1 次 + 本地排序 | 100 点 |
| 要封面 | 本地 `cover` 出 prompt，再单独跑出图 | 0 点（出图另算 72 点/张） |

---

## 四、慢 / 超时

- 搜索类接口偶尔 20–40 秒（上游现抓）。`--timeout` 默认 120 秒，够用。
- 超时会抛 `连不上 …（已重试 2 次）`；**这时的调用可能已在上游扣过点**，
  先用 `log` 看有没有记录、用流水看有没有 `-100`，再决定要不要重发。
- 快照文件很大（一次搜索的原始 JSON 常见 100–300 KB），本地读写不影响速度。

---

## 五、输出与环境

### Windows 控制台里中文变问号 / 报 `UnicodeEncodeError`

本包已做 GBK 兜底：`sys.stdout.reconfigure(errors="replace")`，记号统一用
`√` / `×`（cp936 里有这两个字形）。真要在 GBK 控制台里跑：

```powershell
$env:PYTHONIOENCODING="gbk"
$env:PYTHONDONTWRITEBYTECODE="1"
python scripts\run.py doctor
```

`PYTHONDONTWRITEBYTECODE=1` 是防 `__pycache__`，装包后用不上，开发时有用。

### `--json` 里中文被转义

`json.dumps(..., ensure_ascii=False)` 已关掉转义。若在 PowerShell 里看到 `\u4e2d`，
是终端/管道另一层做的，把输出重定向到文件再看。

---

## 六、合规相关

- 分析结果用于**结构参考**：标题怎么写、钩子怎么起、节奏怎么排。
- 原片与图文的著作权归原作者；转载、二创、商用请在取得授权后进行。
- 带货内容按平台规则做真实性表述与广告标注。

---

## 七、联系

照 `SKILL.md` 末尾的「联系我们」找技术微信，附上：

1. `doctor` 的整屏输出；
2. `log` 里的那一行；
3. 出错命令的完整参数（Key 打码）。

基本一句话就能定位。
