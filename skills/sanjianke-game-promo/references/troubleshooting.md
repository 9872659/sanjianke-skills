# 排错：按报错找原因

> 先跑 `python3 scripts/run.py doctor`。11 项全 √ 时 0 点、0 冻结：Key、4 个应用、接口数、
> 价目、出图端点、视频线、任务查询、上传口、流水前后一致都通了；出现 `×` 的那一行就是问题所在。

---

## 一、退出码先看

| 退出码 | 含义 | 处理 |
|---|---|---|
| `2` | 用法错 | 看 stderr 最后一行：缺 `--game` / `--text` / `--file`，秒数越界，或选项被缩写（本包 `allow_abbrev=False`） |
| `3` | `qc` 没过 | 输出里「要改的地方」逐条列了，改完重跑 |
| `4` | 缺 `--yes` | 报错里已经写了这次要花多少点，确认后加 `--yes` |
| `5` | 超预算 | **一个请求都没发**。调大 `--budget`（单位：点，1 元 = 100 点） |
| `6` | 调用失败 | 看 HTTP 状态与上游 message，对下面的表 |
| `1` | 内部错 | 带 traceback，把最后 5 行发出来 |

---

## 二、HTTP 报错对照

| 报错 / 现象 | 真实原因 | 处理 |
|---|---|---|
| `400 url_not_allowed` | 首帧 / 参考图不是平台托管地址 | 本地图直接给路径（`--image kv.png` / `--ref 草稿.png`，自动 upload）；或用 `upload` 拿到的 `oss.gpu.likeadmin.cn/openapi/…` |
| `422 prompt: String should have at least 1 character` | 出图 prompt 为空 | 这是 `doctor` 的正常探针结果，说明端点对了；真实出图把 `--game` 或 `--prompt` 填上 |
| `400 empty_url` | 视频线收到空 body | `doctor` 的正常探针结果；`film` 请给 `--text` 或 `--asset` |
| `404` + HTML | 路径没注册 | 核对前缀：出图是 `/api/v1/images/generations`，买量片是 `/api/v1/apps/full_video/submit`，预告片是 `/api/v1/apps/seedance/create` |
| `401` / `invalid api key` | Key 错或没带 | `--key` / `A7W_API_KEY` / `~/.a7w/config.json` 三选一；`a7w.py login --key sk-…` 重填 |
| `402` / 余额不足 | 账户点数不够 | 到 api.a7w.cn 充值；先把 `--resolution 480P` 跑通 |
| `502 InvalidMpsUser` | 上游凭据坏了，路由本身在 | 换 480P 或换个时段重试；持续出现就把接口名发出来 |
| `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，连假代号也这么回 | 以 `/api/v1/apps` 列表与 `/api/v1/pricing` 为准 |
| `429` / 频率限制 | 短时间请求太密 | 隔 30 秒重试；`music` 与 `film` 分开跑 |

---

## 三、尺寸与平台

### `qc` 报「宽高都要是 16 的倍数」/「总像素不在区间」

五档尺寸的请求值都是算好的：9x16 用 `720x1280`、16:9 用 `1280x720`、1:1 用 `1024x1024`、
3:4 用 `1152x1536`、4:5 用 `1024x1280`。改尺寸时守住四条：16 的倍数、长短边 3:1 内、
单边 3840 内、总像素 655,360~8,294,400。

### `qc` 报「B站 这一版出图只走 16x9 / 3x4 / 1x1」

平台与比例的对应关系写死在 `PLATFORMS` 里。要给某个平台加新比例，改 `run.py` 的
`PLATFORMS[平台]["sizes"]`，同时确认那个比例在 `SIZES` 里、请求尺寸合法。

### 上架尺寸和请求尺寸不一样

请求尺寸决定生成成本与清晰度，上架尺寸是平台要求。例如 9:16 请求 `720x1280`，上架 `1080x1920`
（后期放大）。`plan` 的矩阵里两列都写清楚，交付时按「上架尺寸」那一列交。

---

## 四、seedance 相关

### `--action query` 为什么不打接口

`seedance/query` 落在 `/api/v1/apps/seedance/*` 通配价上，一次 **11,000 点**。本包把
`--action query` 直接转成 `GET /api/v1/tasks/<task_id>`（0 点）。带 `--task-id` 时就是把
`status` 的结果报给你；不带就只提示这条口径。

### `seedance --action group --dry-run` 退 5

素材托管 5 个接口在价目表里落 11,000 点通配，默认 `--budget 8000` 装不下。真要用：

```bash
python3 scripts/run.py seedance --action group --name gl-assets --budget 12000 --yes
```

`--dry-run` 同样受预算闸门管，所以干跑也要把 `--budget` 调到 12000。

### `create` 报模型名不认识

`--model` 取 `seedance-2-text-2-video`（纯文/图）、`seedance-2-video-2-video`（含视频输入）、
`seedance-2-fast-text-2-video`、`seedance-2-fast-video-2-video` 四个之一。

### 素材入库后怎么在 `create` 里引用

`content` 里给 `{"type": "image_url", "image_url": {"url": "asset://<ASSET_ID>"}}`。
`getAsset` 的 `Result.Status` 是 `Active` 才算可用，`Processing` 时继续等。

---

## 五、多语言相关

### 某个语种少了一条素材

`plan` 按 `--locale` 逐语种复制整套矩阵；`qc` 的「多语言覆盖」会比较各语种的
`(素材, 平台, 尺寸, 序号)` 集合。少一条通常是手改了 `plan.json`，重新跑一遍 `plan` 即可。

### 日文 / 韩文窗口显示成问号

**文件本身是 UTF-8，没有问题**；是 Windows 控制台代码页不认。用
`chcp 65001` 或在 PowerShell 里 `[Console]::OutputEncoding=[Text.Encoding]::UTF8` 再看。
本包已经在 `stdout` / `stderr` 上做了 `errors="replace"` 兜底，编码不认时也不会中断。

### 配音和文案对不上

配音按语种分别合成，`voice --locale ja-JP --text "…"` 时文本要自己换成日文；
`plan` 生成的主标 / 副标 / 行动号召是分语种的，直接从 `交付单.md` 里取。

---

## 六、`qc` 九项逐条

| 检查项 | 常见触发 | 怎么改 |
|---|---|---|
| 版号与适龄 | `plan --license-no` 没给 | 补 `--license-no "ISBN …"`，`--rating` 取 all / 12+ / 16+ / 18+ |
| 概率公示 | 文案里有「抽卡 / 十连 / 概率 / 保底」却没有「公示」 | 加一句「概率公示见游戏内公告」 |
| 买量话术 | 出现「最 / 第一 / 100% / 稳赚」 | 换成可验证结果，例如「首周预约 120 万」 |
| 行动号召 | `--cta` 给了空串 | 给一句完整号召，或去掉 `--cta` 用内置分语种默认值 |
| 命名规范 | 文件名被手改 | 回到 `游戏码-素材_平台_尺寸_语种_v版本`，重新跑 `plan` |
| 尺寸与平台 | 尺寸代号与平台不匹配 | 按 `catalog` 的平台表选尺寸 |
| 多语言覆盖 | 各语种条数不一致 | 重新跑 `plan`，别手删行 |
| 阶段口径 | 预约期写了「已上线」，或上线后写了「立即预约」 | 按 `--phase` 换当期说法 |
| 矩阵与版本 | 同一批混了 v1 / v2 | 统一 `--version`，A/B 另开一批 |

---

## 七、任务层面

### 任务一直 `pending` / `processing`

`status --task-id tsk_xxx` 只打 `GET /api/v1/tasks/<id>`（0 点），可以反复查。
15 秒视频通常 1~4 分钟出结果；超过 15 分钟没动，先看返回里的 `message`。

### 任务 `failed`，钱退了

返回里 `refund` 与 `cost` 都有。失败全额退回，净额 0；把 `message` 发出来定位，
常见是首帧图地址过期（`oss.gpu.likeadmin.cn` 链接约 24 小时）或文本超长。

### 查不到任务

`GET /api/v1/tasks/<id>` 返回 `{"code":0,"msg":"任务不存在"}`：

1. `task_id` 抄错（`tsk_` 开头，别把日志里的行号带上）；
2. 任务在另一个 Key 的账户下；
3. 该接口是同步返回，没有 `task_id`（配音 `tts`、出图 `images/generations` 都是同步）。

### 轮询把余额烧掉了

用的是应用层 `/query` 而不是 `GET /tasks/<id>`。`seedance/query` 一次 11,000 点，
轮询 10 次就是 110,000 点。本包所有查询都走 `GET /tasks/<id>`。

---

## 八、预算与闸门

### 为什么 `--budget` 单位是「点」

1 元 = 100 点。默认 8000 点 = 80 元，够一个上线期双语包（5,748 点）加余量；
seedance 预告片 11,000 点，要显式 `--budget 12000 --yes`。

### `--dry-run` 也退 5

闸门顺序是「先看预算、再看 `--yes`」：`--dry-run` 会跳过确认，但预算不够照样退 5。
这是为了让「干跑通过」等于「真跑也装得下预算」。

### 怎么证明这一轮是 0 点

`doctor` 第 11 项就是证据：自检前后各读一次 `/user/balance/logs?limit=1`，比对
`at` / `points` / `reference` 三元组。两次一致 = 中间没有新流水。本账号实测最新一笔是
`2026-11-07 23:54:08 · refund · +300 · refund:submit_failed:/api/v1/videos`，自检前后一致。
