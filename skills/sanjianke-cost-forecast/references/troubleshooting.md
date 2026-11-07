# 排错：按报错找原因

先跑一遍自检，90% 的问题它都会直接点名：

```bash
python3 scripts/run.py doctor
```

---

## 一、退出码对照

| 码 | 现象 | 原因 | 做法 |
|---|---|---|---|
| `0` | 正常 | — | — |
| `2` | `用法错` / `不认识的对象` | 清单字段写错、`kind` 不在五种里、选项被缩写（如 `--bud`） | 按提示改；`allow_abbrev=False` 已关掉缩写 |
| `3` | 自检未过 | 某个只读端点不通、价目与基线不一致、流水读不到 | 看 `doctor` 里打 `×` 的那一行 |
| `4` | `要连发 N 个只读 GET…确认请加 --yes` | 批量只读扫描 ≥30 个请求 | 加 `--yes`（花费仍是 0 点） |
| `5` | `超过 --budget` | 本单报价超预算，或 `--budget 0` | 调大 `--budget`，或 `--allow-over-budget` |
| `6` | `拉取失败（HTTP …）` | 网络抖动、Key 失效、网关 5xx | 重跑；连不上看 `--host` |
| `1` | 内部错误 | 没预料到的异常 | 把 traceback 与 `doctor --json` 一起发出来 |
| `130` | 已中断 | Ctrl-C | — |

---

## 二、按报错原文找

### `失败：没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / …`

Key 没落到这三个来源。三种写法：

```bash
python3 scripts/run.py doctor --key sk-你的key              # 本次
export A7W_API_KEY=sk-你的key                               # 环境变量
python3 scripts/a7w.py login --key sk-你的key               # 写进 ~/.a7w/config.json
```

Windows PowerShell：`$env:A7W_API_KEY="sk-你的key"`。

### `拉取失败（HTTP 401）` / `HTTP 403`

Key 无效、被吊销、或与 `--host` 不匹配。先用 `doctor` 确认 `/user/balance` 是否 200。

### `拉取失败（HTTP 404）` 且响应是 HTML

路径前缀写错。本包所有端点都带 `/api/v1` 前缀，余额与流水例外（`/user/balance`、`/user/balance/logs`）。

### `清单文件不存在` / `清单不是合法 JSON`

`--file` 用了相对路径但工作目录不在包目录。两种写法都稳：

```bash
python3 scripts/run.py quote --file "$(pwd)/清单.json"
python3 scripts/run.py quote --file C:\路径\清单.json
```

JSON 里用双引号，`kind` 只有 `image` / `video` / `post` / `voice` / `app` 五种。

### `不认识的出图对象` / `不认识的视频对象` / `不认识的应用`

`target` 拼错或不在当前价目表里。`catalog` 会打印全部可用名字：

```bash
python3 scripts/run.py catalog
python3 scripts/run.py catalog --models
```

档位名是小写短名（`restore` / `superres` / `shot`），模型层要写 `model:<模型ID>`。

### `配音项要给 chars（多少字）`

voice 项缺 `chars`。补上字数（不是段数）：

```json
{"kind": "voice", "target": "voice_tts", "chars": 220, "count": 2}
```

### `这单基线价 … 超过 --budget …，一个请求都没发`

这是第一道闸门，跑在任何请求之前，用内置基线算的。两条路：

1. 调大预算：`--budget 20000`；
2. 只想看全表：加 `--allow-over-budget`（仍然 0 点、仍然只发只读 GET）。

### `现查价后这单 … 超过 --budget …`

第一道闸门用的是本地基线，现查价目后总量才涨上去（价目表上次更新之后涨过价）。
同样两条路：调 `--budget`，或 `--allow-over-budget`。此时只发过只读 GET，账单 0 点。

### `--budget 是 0 点…给 1 点以上就放行`

`--budget 0` 等于不授权任何调用。给个正数就放行（本包每个请求 0 点）。

### `要连发 70 个只读 GET（花费 0 点，扣不到钱）。确认请加 --yes。`

`compare --all` 或 `--pages` ≥ 30 会触发。加 `--yes`；这仍然是 0 点操作。

### 报价行标了 `!`

对应五类陷阱之一，往下翻「明细（口径与来源）」，每行都写了规则路径与来源：

| 标记 | 含义 | 处理 |
|---|---|---|
| `!` + `route404` | 这一档路由 404 | 换同能力的 viapi 档，价格相同 |
| `!` + `upstream502` | 上游凭据坏、整批退款 | 这一档先按 0 结算，换档再报 |
| `!` + `unitMismatch` | note 写点/次、rule 是按秒 | 区间下限按次、基准按秒，报给甲方用基准 |
| `!` + `wildcard` | 落通配兜底（上游×2、保底 50） | 有实测记录就按实测，没有就按保底报上界 |
| `!` + `appVsModel` | 应用层一口价比模型层贵 | 跑 `compare` 看差几倍，换模型层 |

### 模型层价格看起来偏高

没有你这个模型的成交记录时，本包按通配保底 50 点/条报上界，来源字段写「通配保底」。
跑一次 `compare --pages 10` 或真正跑过该模型后，`/me/tasks` 里有 `actualPrice`，报价就会自动换成实测最低价。

### 配音金额跟实际账单差一点

`voice_tts` 按「上游实际点数 ×3」结算，本包用 0.18 点/字 的实测基线。文案长短、模型不同都会浮动；
要更准就在清单项里写 `"pointsPerChar": 0.25` 覆盖。

### 报价里的「区间」怎么来的

- 乐观：按次 / 实测最低口径（按秒档取 rule，按次项取 note）；
- 基准：价目表 rule 口径；
- 保守：基准 +30% 重跑余量；按次与按秒混用的档位按 rule ×2。

报给甲方用基准，自己排期留保守。

---

## 三、Windows 上的编码

本包对 `sys.stdout` / `sys.stderr` 都做了 `reconfigure(errors="replace")`，状态符号只用 `√` 与 `×`，
金额单位写「元」，所以 `PYTHONIOENCODING=gbk` 下也能完整跑完：

```powershell
$env:PYTHONIOENCODING="gbk"
$env:PYTHONDONTWRITEBYTECODE="1"
python -u scripts\run.py doctor
```

`PYTHONDONTWRITEBYTECODE=1` 是为了不在包里留 `__pycache__`。

把输出重定向到文件时，用 UTF-8 读就不会出现乱码：

```powershell
$env:PYTHONIOENCODING="utf-8"
python -u scripts\run.py quote --preset duanju | Out-File -Encoding utf8 报价.txt
```

---

## 四、离线与缓存

| 场景 | 行为 |
|---|---|
| 正常联网 | 现查 `/api/v1/pricing`，并写缓存到 `~/.a7w/cost-forecast-cache.json` |
| 现查失败 | 自动退回缓存；缓存也没有就用内置基线（2026-11-08 快照） |
| `--offline` | 完全不出网：先缓存、再内置基线，请求数 0 |
| 缓存想重置 | 删掉 `~/.a7w/cost-forecast-cache.json` 即可，下次自动重建 |

`doctor` 会把线上价与 30 个视频档的基线逐档比对，价目一动就会提示。

---

## 五、报价落地时的地址白名单

本包只算钱、不提交任务，所以清单里写的是「几张图、几条几秒」，不是具体 URL。
等你按报价单真正去跑时，凡是带 `videoUrl` / 参考视频的接口（视频后处理、视频生成、人物替换等）
只收**平台托管**的地址：

```
✅ POST /api/v1/upload（multipart，字段名 file，免费）→ data.url
   形如 https://oss.gpu.likeadmin.cn/openapi/…（最长 24 小时有效）
✅ 本站成片：https://vr.a7w.cn/…
✅ 本站七牛：https://cdn2.jiujiushuyuan.cn/vr/…
❌ https://example.invalid/x.mp4 → 400 url_not_allowed
```

所以「先生成 / 上传，再提交」是唯一稳妥的顺序：本地素材先 `POST /api/v1/upload` 换地址，
再把它填进 `videoUrl`。这一步 0 点，本包的成本预估里也不占预算。

`GET /api/v1/apps/<app>` 这类「读应用详情」的路径命中 `/apps/<app>/*` 通配计价，会即时扣费；
看应用与接口清单走 `GET /api/v1/apps` 列表 + `GET /api/v1/pricing`，两条都是 `cost: 0`。

---

## 六、怎么证明「这一轮真的 0 点」

`doctor` 在第 2 步读一次 `/user/balance/logs?limit=1`，第 11 步再读一次，比对最近一笔的
时间、点数、`reference`：**两次完全相同**，就说明这段时间没有任何扣费或冻结发生。

自己动手也能验：

```bash
curl -s -H "Authorization: Bearer $A7W_API_KEY" \
  "https://api.a7w.cn/user/balance/logs?limit=1"
```

跑 `doctor` 前后各执行一次，最近一笔不变即证。本包源码里没有任何 POST / PUT / DELETE，
所有上行都是 `GET`，所以不存在「探针把钱包动一下」的情况。
