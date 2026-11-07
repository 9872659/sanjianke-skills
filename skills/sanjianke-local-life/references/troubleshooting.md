# 排错：按报错找原因

> 先跑 `python3 scripts/run.py doctor`。10 项全 √ 时 0 点、0 冻结，Key、应用、价目、端点、查询、上传都通了；
> 出现 × 的那一行就是问题所在，下面的表按「报错原文 / 现象」索引。

---

## 一、退出码先看

| 退出码 | 含义 | 处理 |
|---|---|---|
| `2` | 用法错 | 看 stderr 最后一行：缺 `--shop` / `--text` / `--file`，秒数越界，或选项被缩写（`--bud` 这类，本包 `allow_abbrev=False`） |
| `3` | 自检或合规没过 | `doctor` 的 × 行；或 `qc` 列出的「要改的地方」 |
| `4` | 缺 `--yes` | 报错里已经写了这次要花多少点，确认后加 `--yes` |
| `5` | 超预算 | **一个请求都没发**。调大 `--budget`（单位：点，1 元 = 100 点） |
| `6` | 调用失败 | 看 HTTP 状态与上游 message，对下面的表 |
| `1` | 内部错 | 带 traceback，把最后 5 行发出来 |

---

## 二、HTTP 报错对照

| 报错 / 现象 | 真实原因 | 处理 |
|---|---|---|
| `400 url_not_allowed` | 首帧 / 参考图不是平台托管地址 | 本地图直接给路径：`film --image cover.png`（自动 upload）；或用 `upload` 拿到的 `oss.gpu.likeadmin.cn/openapi/…` |
| `422 prompt: String should have at least 1 character` | 出图 prompt 为空 | 这是 `doctor` 的正常探针结果，说明端点对了；真实出图时把 `--kind` 和 `--shop` 填全 |
| `400 empty_url` | 视频线收到空 body | `doctor` 的正常探针结果；`film` 请给 `--text` 和 `--seconds` |
| `404` + HTML | 路径没注册 | 核对前缀：出图是 `/api/v1/images/generations`，成片是 `/api/v1/apps/full_video/submit` |
| `401` / `invalid api key` | Key 错或没带 | `--key` / `A7W_API_KEY` / `~/.a7w/config.json` 三选一；`a7w.py login --key sk-…` 重填 |
| `402` / 余额不足 | 账户点数不够 | 到 api.a7w.cn 充值；先把 `--resolution 480P` 跑通 |
| `502 InvalidMpsUser` | 上游凭据坏了，路由本身在 | 换 480P 或换个时段重试；持续出现就把该接口名发出来 |
| `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，连假代号也这么回 | 以 `/api/v1/apps` 列表与 `/api/v1/pricing` 为准，别按这句话判断接口是否存在 |
| `429` / 频率限制 | 短时间请求太密 | 隔 30 秒重试；`music` 与 `film` 分开跑 |

---

## 三、任务层面的问题

### 任务一直 `pending` / `processing`

`status --task-id tsk_xxx` 只打 `GET /api/v1/tasks/<id>`（0 点），可以反复查。
15 秒的片子通常 1~4 分钟出结果；超过 15 分钟没动，先看返回里的 `message`。

### 任务 `failed`，钱退了

返回里 `refund` 与 `cost` 都有。失败全额退回，净额 0；把 `message` 发出来定位，常见是首帧图地址过期或文本超长。

### 查不到任务

`GET /api/v1/tasks/<id>` 返回 `{"code":0,"msg":"任务不存在"}`：

1. `task_id` 抄错（`tsk_` 开头，别把日志里的行号带上）；
2. 任务在另一个 Key 的账户下；
3. 该接口是同步返回，没有 `task_id`（参考搜索、口播 `tts` 都是同步）。

### 轮询把余额烧掉了

用的是应用层 `/query` 而不是 `GET /tasks/<id>`。`nano_banana/query` 实测 72 点/次，轮询 200 次就是 14,400 点。本包所有查询都走 `GET /tasks/<id>`。

---

## 四、各工序的典型报错

### 出图（`shop`）

| 现象 | 处理 |
|---|---|
| 返回里没有 `data` | 看 `error.message`；`n` 超过 4 会被本地夹到 4 |
| 尺寸报错 | 用默认 `1024x1536`（16 的倍数、2:3、总像素在区间内） |
| 图片链接 404 | 返回的 url 原样使用，追加查询参数会失效；本包已自动落盘成 png |

### 口播（`voice`）

| 现象 | 处理 |
|---|---|
| `这条 N 字，同步 tts 建议 500 字内` | 按五段拆成两三条口播，或改用 `tts_async`（长文） |
| 没有 `audio_url` | 看 `data` 里的 `usage` / `message`；音色 ID 写错也会走到这里 |
| 实际扣费比预估高 | 语音按上游真实点数 x 3，以 `usage.points_cost` 为准；本包的 0.18 点/字只是估值 |

### 配乐（`music`）

| 现象 | 处理 |
|---|---|
| 只回 `task_id` 没有音频 | 正常，用 `status --task-id` 取；配乐是异步线 |
| 扣了 50 点但没声音 | 保底 50 点是下限；把返回原文发出来，看是不是 `instrumental` 与 `lyrics` 冲突 |
| 风格不像探店 | `--style` 写具体乐器与速度：「木吉他 + 轻鼓，100 BPM，明亮」 |

### 成片（`film`）

| 现象 | 处理 |
|---|---|
| `full_video 单段 4~15 秒` | 20 秒分 15 + 5 两次提交，或直接 `--seconds 15` 出片段再本地拼 |
| 首帧图被拒 | 先 `upload --file cover.png`，把返回地址给 `--image` |
| 文本超长 | 768P 及以上 5,000 字符内，其他分辨率 7,000 字符内 |
| 出片糊 / 不像门店 | prompt 里补「手机竖屏实拍、暖黄灯光、真实探店质感、画面无文字」，并把 `--resolution` 提到 1080P |

### 同城参考（`ref`）

| 现象 | 处理 |
|---|---|
| 100 点扣了但没条目 | 换更短的关键词（「成都 火锅」而不是一整句）；`--json` 里有 `raw` 原文 |
| 关键词太长没结果 | 城市 + 品类两段式：`成都 火锅`、`成都 春熙路 串串` |
| 搜索结果不能当素材 | 同城爆款只借结构（钩子词、时长、标题公式），画面自己拍 |

---

## 五、控制台与编码

### Windows 下中文变成乱码或 `?`

本包启动时已对 stdout / stderr 做 `reconfigure(errors="replace")`，并把人民币符号统一写成「元」。仍要固定编码时：

```powershell
$env:PYTHONIOENCODING="utf-8"
python -u scripts\run.py doctor
```

GBK 控制台下 `python -u scripts/run.py doctor` 实测 `exit=0`，`√` / `×` 正常显示。

### `--json` 解析失败

`--json` 只保证 stdout 是一个 JSON 文档；进度条、告警都走 stderr。管道里请只取 stdout：

```bash
python3 scripts/run.py catalog --json 2>/dev/null | python3 -m json.tool
```

### 用了 `--dry-run` 还扣钱

`--dry-run` 一个请求都不发，只打印端点与请求体。真正扣钱的路径只有 `--yes` 的那几个子命令；`plan` / `qc` / `cost` / `catalog` / `doctor` / `log` / `status` 都是 0 点。

---

## 六、交付层面的返工

| 现象 | 原因 | 处理 |
|---|---|---|
| `qc` 报「绝对化用语」 | 文案里有「最 / 第一 / 顶级 / 唯一」 | 换成可验证描述：「现熬 4 小时」「人均 44 元」 |
| `qc` 报「没看到具体价格」 | 只写了「很划算」 | 补上「88 元」这类数字 |
| `qc` 报「同城标签少于 3 个」 | 标签没生成或手删了 | 重新 `plan`，或手补城市 + 商圈 + 品类 |
| `qc` 报「缺行动号召」 | 结尾没有到店 / 团购 / 导航 | 补一句「左下角团购，到店出示核销码」 |
| `qc` 报「单条超过 60 秒」 | 时长设太长 | 同城流量池里 25 秒最稳，改 `--seconds 25` |

---

## 七、还不行时，把这三样发出来

1. `python3 scripts/run.py doctor --json` 的完整输出；
2. 出错那条命令的**完整命令行**（Key 用 `sk-***` 代替）；
3. 返回体原文（`--json` 的 stdout，或 stderr 的「失败：…」一行）。
