# 排错：按报错找原因

> 先跑 `python3 scripts/run.py doctor`。10 项全 √ 时 0 点、0 冻结：Key、应用、价目、出图端点、
> 视频线、任务查询、上传口、流水前后一致都通了；出现 × 的那一行就是问题所在。

---

## 一、退出码先看

| 退出码 | 含义 | 处理 |
|---|---|---|
| `2` | 用法错 | 看 stderr 最后一行：缺 `--sell` / `--text` / `--file`，秒数越界，或选项被缩写（本包 `allow_abbrev=False`） |
| `3` | `qc` 没过 | 输出里「要改的地方」逐条列了，改完重跑 |
| `4` | 缺 `--yes` | 报错里已经写了这次要花多少点，确认后加 `--yes` |
| `5` | 超预算 | **一个请求都没发**。调大 `--budget`（单位：点，1 元 = 100 点） |
| `6` | 调用失败 | 看 HTTP 状态与上游 message，对下面的表 |
| `1` | 内部错 | 带 traceback，把最后 5 行发出来 |

---

## 二、HTTP 报错对照

| 报错 / 现象 | 真实原因 | 处理 |
|---|---|---|
| `400 url_not_allowed` | 首帧 / 参考图不是平台托管地址 | 本地图直接给路径（`--image a.png` / `--ref a.jpg`，自动 upload）；或用 `upload` 拿到的 `oss.gpu.likeadmin.cn/openapi/…` |
| `422 prompt: String should have at least 1 character` | 出图 prompt 为空 | 这是 `doctor` 的正常探针结果，说明端点对了；真实出图把 `--sell` 或 `--prompt` 填上 |
| `400 empty_url` | 视频线收到空 body | `doctor` 的正常探针结果；`film` 请给 `--text` 或 `--sell` |
| `404` + HTML | 路径没注册 | 核对前缀：出图是 `/api/v1/images/generations`，视频是 `/api/v1/apps/full_video/submit` |
| `401` / `invalid api key` | Key 错或没带 | `--key` / `A7W_API_KEY` / `~/.a7w/config.json` 三选一；`a7w.py login --key sk-…` 重填 |
| `402` / 余额不足 | 账户点数不够 | 到 api.a7w.cn 充值；先把 `--resolution 480P` 跑通 |
| `502 InvalidMpsUser` | 上游凭据坏了，路由本身在 | 换 480P 或换个时段重试；持续出现就把接口名发出来 |
| `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，连假代号也这么回 | 以 `/api/v1/apps` 列表与 `/api/v1/pricing` 为准 |
| `429` / 频率限制 | 短时间请求太密 | 隔 30 秒重试；`music` 与 `film` 分开跑 |
| 出图返回 422 但 prompt 明明写了 | prompt 里只有空格 / 全角空格 | 先 `qc --text "..."` 确认文案非空再出图 |

---

## 三、尺寸相关

### `size 不是 16 的倍数` / `总像素不在区间`

`qc` 的「尺寸合规」会先拦。五档尺寸的请求值都是算好的：9x16 用 `720x1280`、1:1 用 `1024x1024`、
16:9 用 `1280x720`、3:4 用 `1152x1536`、4:5 用 `1024x1280`。改尺寸时守住四条：16 的倍数、
长短边 3:1 内、单边 3840 内、总像素 655,360~8,294,400。

### 上架尺寸和请求尺寸不一样

请求尺寸决定生成成本与清晰度，上架尺寸是平台要求。例如 9:16 请求 `720x1280`，上架 `1080x1920`
（后期放大）。`plan` 的矩阵里两列都写清楚，交付时按「上架尺寸」那一列交。

---

## 四、任务层面的问题

### 任务一直 `pending` / `processing`

`status --task-id tsk_xxx` 只打 `GET /api/v1/tasks/<id>`（0 点），可以反复查。
15 秒的视频素材通常 1~4 分钟出结果；超过 15 分钟没动，先看返回里的 `message`。

### 任务 `failed`，钱退了

返回里 `refund` 与 `cost` 都有。失败全额退回，净额 0；把 `message` 发出来定位，常见是首帧图地址过期或文本超长。

### 查不到任务

`GET /api/v1/tasks/<id>` 返回 `{"code":0,"msg":"任务不存在"}`：

1. `task_id` 抄错（`tsk_` 开头，别把日志里的行号带上）；
2. 任务在另一个 Key 的账户下；
3. 该接口是同步返回，没有 `task_id`（口播 `tts`、出图 `images/generations` 都是同步）。

### 轮询把余额烧掉了

用的是应用层 `/query` 而不是 `GET /tasks/<id>`。`nano_banana/query` 实测 72 点/次，轮询 30 次就是 2,160 点。
本包所有查询都走 `GET /tasks/<id>`。

---

## 五、各工序的典型报错

### 出图（`img`）

| 现象 | 处理 |
|---|---|
| 返回里没有图 | 看 `error.message`；`n` 超过 4 会被本地夹到 4 |
| 图不像是这个卖点 | `--prompt` 覆盖内置模板，把产品、场景、光线写具体 |
| 商品走样 | 加 `--ref 实拍.jpg` 走改图线（`/images/edits`，同样 6 点/张） |
| 图片链接 404 | 返回的 url 原样使用，追加查询参数会失效；本包已自动落盘成 png |

### 参考图（`img --engine nano`）

| 现象 | 处理 |
|---|---|
| 只回 `task_id` 没有图 | 正常，异步线；用 `status --task-id` 取 |
| 72 点扣了但没出图 | 看 `status` 里的 `message`；参考图地址过期也会这样，重新 `upload` |
| 想要多角度 | 请求体带 `views[]` 时按 25 点 x 视角数计价，本包 `--engine nano` 走单次 72 点 |

### 视频素材（`film`）

| 现象 | 处理 |
|---|---|
| `full_video 单段 4~15 秒` | 20 秒分 15 + 5 两次提交，或直接 `--seconds 15` 出片段再本地拼 |
| 首帧图被拒 | 先 `upload --file cover.png`，把返回地址给 `--image` |
| 文本超长 | 768P 及以上 5,000 字符内，其他分辨率 7,000 字符内 |
| 出片糊 / 不像素材 | prompt 里补「竖屏投放素材、真实质感、画面无文字」，`--resolution` 提到 1080P |

### 口播（`voice`）

| 现象 | 处理 |
|---|---|
| `这条 N 字，同步 tts 建议 500 字内` | 按 3 秒 / 9 秒拆成两三条口播 |
| 没有 `audio_url` | 看 `data` 里的 `usage` / `message`；音色 ID 写错也会走到这里 |
| 实际扣费比预估高 | 语音按上游真实点数 x 3，以 `usage.points_cost` 为准；0.18 点/字只是估值 |

### 配乐（`music`）

| 现象 | 处理 |
|---|---|
| 只回 `task_id` 没有音频 | 正常，用 `status --task-id` 取；配乐是异步线 |
| 扣了 50 点但没声音 | 保底 50 点是下限；把返回原文发出来，看是不是 `instrumental` 与 `lyrics` 冲突 |
| 风格不对 | `--style` 写具体乐器与速度：「电子鼓点 + 贝斯，120 BPM，明亮」 |

---

## 六、交付层面的返工（`qc` 报什么改什么）

| `qc` 报的 | 原因 | 处理 |
|---|---|---|
| 绝对化用语 | 文案里有「最 / 第一 / 全网 / 100%」 | 换成可验证描述：「洗 30 次仍凉感」「券后 79 元」 |
| 没看到具体价格 | 这个卖点一条价格锚都没有 | 价格钩的 `line` 或 `subline` 补「N 元 / 券后」 |
| 钩子重复 / 前 3 秒太长 | 三条素材说了同一句，或台词超过 24 字 | 重跑 `plan`，或手改 `plan.json` 的 `line` |
| 缺行动号召 | 结尾没有动作词 | 补「点击 / 领券 / 下单 / 立即 / 查看」之一 |
| 命名不规范 | 手改名破坏了 `卖点码-钩子_尺寸_v版本` | 按 `SP01-H1_9x16_v1.png` 改回来 |
| 缺一条 | 删了某个尺寸或钩子 | 重跑 `plan`，或把 `--sizes` / `--hooks` 补齐 |
| 混了版本 | 一批里 v1 和 v2 混着 | 统一 `--version` 重跑，v2 单独一批 |

---

## 七、控制台与编码

### Windows 下中文变成乱码或 `?`

本包启动时已对 stdout / stderr 做 `reconfigure(errors="replace")`，货币符号统一写成「元」。仍要固定编码时：

```powershell
$env:PYTHONIOENCODING="utf-8"
python -u scripts\run.py doctor
```

GBK 控制台下 `set PYTHONIOENCODING=gbk && python -u scripts\run.py doctor` 实测 `exit=0`，
输出按 GBK 解码 0 个替换字符，`√` / `×` 正常显示。

### `--json` 解析失败

`--json` 只保证 stdout 是一个 JSON 文档；进度、告警都走 stderr。管道里只取 stdout：

```bash
python3 scripts/run.py cost --json 2>/dev/null | python3 -m json.tool
```

### 用了 `--dry-run` 还扣钱

`--dry-run` 一个请求都不发，只打印端点与请求体。真正扣钱的只有带 `--yes` 的 `img` / `film` / `voice` / `music`；
`plan` / `qc` / `cost` / `catalog` / `doctor` / `log` / `status` 都是 0 点。

---

## 八、还不行时，把这三样发出来

1. `python3 scripts/run.py doctor --json` 的完整输出；
2. 出错那条命令的**完整命令行**（Key 用 `sk-***` 代替）；
3. 返回体原文（`--json` 的 stdout，或 stderr 的「失败：…」一行）。
