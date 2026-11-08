# 排错：按报错找原因

> 先跑 `python3 scripts/run.py doctor`。10 项全 √ 时 0 点、0 冻结，Key、应用、接口数、价目、端点、查询、上传都通了；
> 出现 × 的那一行就是问题所在，下面的表按「报错原文 / 现象」索引。

---

## 一、退出码先看

| 退出码 | 含义 | 处理 |
|---|---|---|
| `2` | 用法错 | 看 stderr 最后一行：缺 `--topic` / `--keyword` / `--material` / `--file`，秒数越界，或选项被缩写（`--templ` 这类，本包 `allow_abbrev=False`） |
| `3` | 自检或合规没过 | `doctor` 的 × 行；或 `qc` 列出的「要改的地方」 |
| `4` | 缺 `--yes` | 报错里已经写了这次要花多少点，确认后加 `--yes` |
| `5` | 超预算 | **一个请求都没发**。调大 `--budget`（单位：点，1 元 = 100 点） |
| `6` | 调用失败 | 看 HTTP 状态与上游 message，对下面的表 |
| `1` | 内部错 | 带 traceback，把最后 5 行发出来 |
| `130` | 被 Ctrl-C 中断 | 已提交的任务到控制台看结果，钱按实际结算 |

`--budget` 给 0 或负数时，只要有请求就退 5；`--budget 10` 配 18 点的三张图也退 5，一个请求都不发。

---

## 二、HTTP 报错对照

| 报错 / 现象 | 真实原因 | 处理 |
|---|---|---|
| `400 url_not_allowed` | 首帧图 / 混剪素材不是平台托管地址 | 本地文件直接给路径：`film --image cover.png`、`mix --material cover.png`（都会自动 upload）；或用 `upload` 拿到的 `oss.gpu.likeadmin.cn/openapi/…` |
| `422 prompt: String should have at least 1 character` | 出图 prompt 为空 | 这是 `doctor` 的正常探针结果，说明端点对了；真实出图把 `--topic` 与 `--kind` 填全 |
| `400 empty_url` | 视频线收到空 body | `doctor` 的正常探针结果；`film` 请给 `--text` 与 `--seconds` |
| `404` + HTML | 路径没注册 | 核对前缀：混剪是 `/api/v1/apps/smart_clip/news_mixcut`，成片是 `/api/v1/apps/full_video/submit`，出图是 `/api/v1/images/generations` |
| `401` / `invalid api key` | Key 错或没带 | `--key` / `A7W_API_KEY` / `~/.a7w/config.json` 三选一；`a7w.py login --key sk-…` 重填 |
| `402` / 余额不足 | 账户点数不够 | 到 api.a7w.cn 充值；先把深度换 `--resolution 480P` 跑通（一单 715.8 点） |
| `502 InvalidMpsUser` | 上游凭据坏了，路由本身在 | 换时段重试；持续出现就把接口名发出来 |
| `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，连假代号也这么回 | 以 `/api/v1/apps` 列表与 `/api/v1/pricing` 为准 |
| `429` / 频率限制 | 短时间请求太密 | 隔 30 秒重试；`mix` 与 `cover` 分开跑 |

---

## 三、任务层面的问题

### 任务一直 `pending` / `processing`

`status --task-id tsk_xxx` 只打 `GET /api/v1/tasks/<id>`（0 点），可以反复查。
30 秒混剪通常 2~6 分钟出结果；超过 20 分钟没动，先看返回里的 `message`。

### 任务 `failed`，钱退了

返回里 `refund` 与 `cost` 都有。失败全额退回，净额 0；把 `message` 发出来定位，常见是素材地址过期、素材重名、文本超长。

### 查不到任务

`GET /api/v1/tasks/<id>` 返回 `{"code":0,"msg":"任务不存在"}`：

1. `task_id` 抄错（`task_` / `tsk_` 开头，别把日志里的行号带上）；
2. 任务在另一个 Key 的账户下；
3. 该接口是同步返回，没有 `task_id`（采集与播报都是同步）。

### 轮询把余额烧掉了

用的是应用层 `/query` 而不是 `GET /tasks/<id>`。`nano_banana/query` 实测 72 点/次，轮询 200 次就是 14,400 点。本包所有查询都走 `GET /tasks/<id>`。

---

## 四、各工序的典型报错

### 采集参考（`hunt`）

| 现象 | 处理 |
|---|---|
| 扣了 100 点但返回空列表 | 关键词太窄。换成「城市 + 主体 + 动作」，例如「杭州 地铁 延长运营」 |
| 想翻第二页 | `--page 2`，但那是**又一次 100 点**；一页够用就别翻 |
| 提示「给 --keyword」 | 关键词是必填参数，采集接口没有默认值 |

### 配图（`cover`）

| 现象 | 处理 |
|---|---|
| 返回里没有 `data` | 看 `error.message`；`--n` 超过 4 会被本地夹到 4 |
| 尺寸报错 | 用默认 1024x1536（快讯）/ 1536x1024（深度），16 的倍数、长短边 ≤ 3:1 |
| 图片链接 404 | 返回的 url 原样使用，追加查询参数会失效；本包已自动落盘成 png |
| `--kind` 报错 | 取 `all` 或该模板的图种：快讯 cover / scene / chart，深度再加 people / timeline / ending |
| 封面不像这条新闻 | `--topic` 写细一点（「地铁 3 号线延长运营」比「地铁」好），或把交付单里的 prompt 手工补两句 |

### 播报（`voice`）

| 现象 | 处理 |
|---|---|
| `这条 N 字，同步 tts 建议 500 字内` | 按段拆成两三条，或改走 `tts_async`（长文） |
| 没有 `audio_url` | 看 `data` 里的 `usage` / `message`；音色 ID 写错也会走到这里 |
| 实际扣费比预估高 | 语音按上游真实点数 x 3，以 `usage.points_cost` 为准；0.18 点/字只是估值 |
| 念「1.2 万人次」像「一点二万」 | 数字前后加空格，或改写成「多运 1.2 万人次」这类短句，TTS 断句更稳 |

### 配乐（`music`）

| 现象 | 处理 |
|---|---|
| 只回 `task_id` 没有音频 | 正常，用 `status --task-id` 取；配乐是异步线 |
| 扣了 50 点但没声音 | 保底 50 点是下限；把返回原文发出来，看是不是 `instrumental` 与 `lyrics` 冲突 |
| 风格不像新闻片头 | `--style` 写具体乐器与速度：「短促电子鼓点加铜管重音，118 BPM」 |

### 补镜头（`film`）

| 现象 | 处理 |
|---|---|
| `full_video 单段 4~15 秒` | 15 秒上限，更长的镜头拆成多段提交，或改用 `mix` |
| 首帧图被拒 | 先 `upload --file cover.png`，把返回地址给 `--image` |
| 文本超长 | 768P 及以上 5,000 字符内，其他分辨率 7,000 字符内 |
| 画幅不对 | `--platform bilibili` 走 16:9；其余平台默认 9:16 |
| 出片带「AI 生成」字样 | 这是本包的默认（`aigc_watermark: true`），与合规标注一致 |

### 新闻体混剪（`mix`）

| 现象 | 处理 |
|---|---|
| `videoDuration 是 5~300 秒` | 30 秒快讯用 30，90 秒深度用 90；`--seconds` 越界在本地就退 2 |
| 报「素材会重名 / 渲染异常」 | 三个素材、背景音乐、封面图的地址**不能重名**；本包每个文件带不同后缀，手拼地址时保持一致 |
| 提交成功但没有 `task_id` | 看 `data` 里的字段名，把返回原文发出来 |
| 想要固定顺序的画面 | `--composition order`（默认就是 order）；随机是 `random` |
| 旁白对不上口型 | `news_mixcut` 不靠人声驱动，靠标题 + 素材；旁白另配 `voice`，进混剪当背景音轨 |
| 模板 ID 不对 | `--style-id` 用 `smart_clip/template` 查出来的真实 ID；默认值只是文档示例 |

### 上传（`upload`）

| 现象 | 处理 |
|---|---|
| 返回 `code 0` +「请使用 file 字段提交一个文件」 | 正常，说明上传口令在；真实上传要给 `--file` |
| 上传成功但 `film` / `mix` 仍报 `url_not_allowed` | 地址被手改过；用 upload 原样返回的 `data.url` |

---

## 五、控制台与编码

### Windows 下中文变成乱码或 `?`

本包启动时已对 stdout / stderr 做 `reconfigure(errors="replace")`，并把人民币符号统一写成「元」。仍要固定编码时：

```powershell
$env:PYTHONIOENCODING="utf-8"
python -u scripts\run.py doctor
```

GBK 控制台下 `$env:PYTHONIOENCODING="gbk"; python -u scripts\run.py doctor` 实测 `exit=0`，`√` / `×` 正常显示（源码与输出里没有 cp936 编不出的字符）。

### `--json` 解析失败

`--json` 只保证 stdout 是一个 JSON 文档；进度、告警都走 stderr。管道里请只取 stdout：

```bash
python3 scripts/run.py catalog --json 2>/dev/null | python3 -m json.tool
```

### 用了 `--dry-run` 还扣钱

`--dry-run` 一个请求都不发，只打印端点与请求体。真正扣钱的路径只有带 `--yes` 的那六个子命令；`plan` / `qc` / `cost` / `catalog` / `doctor` / `log` / `status` 都是 0 点。

### 预算是 0 点却被拦

`--budget` 单位是点，不是元。1 元 = 100 点；一天 8 条快讯加 2 条深度是 4,280 点，`--budget 100` 会直接退 5。

---

## 六、交付层面的返工

| 现象 | 原因 | 处理 |
|---|---|---|
| `qc` 报「来源标注写在口播与描述里」 | `--source` 还是「待填」，或只在描述里出现 | 补来源单位，口播收尾句与描述都要出现它 |
| `qc` 报「时间 / 地点 / 主体三要素齐全」 | `--when` / `--where` / `--subject` 有空值 | 补三项，事件段就是靠它们拼出来的 |
| `qc` 报「关键数字带单位与时间」 | 全篇没有数字 | 补 `--figure`，例如「日均多运 1.2 万人次」 |
| `qc` 报「AI 生成标注在描述与片尾」 | `--ai-label` 被清空 | 保留「AI 辅助生成」，描述与片尾字幕板都要有 |
| `qc` 报「播报语速在 X~Y 字/秒」 | 稿子太密或太空 | 快讯 30 秒按 150 字、深度 90 秒按 300 字；`plan` 出来的稿子改完重跑 `qc` |
| `qc` 报「标题三条且每条 ≤ 20 字」 | 手改标题超长 | 压到 20 字内，主体 + 动作在前、数字在后 |
| `qc` 报「无绝对化用语」 | 出现「最好 / 第一 / 唯一 / 顶级」 | 换可核对表述：「12.6 万人次，同比 3.2%」 |
| `qc` 报「无传闻与猜测词」 | 出现「据说 / 网传 / 疑似 / 内幕」 | 换成发布主体与时间：「据市地铁集团通报」 |
| `qc` 报「无夸张与情绪词」 | 出现「震惊 / 刷屏 / 史上最」 | 把情绪词换成现场动作：「站台排队到楼梯口」 |
| `qc` 报「字幕一行 ≤ 16 字」 | 手改 SRT 后一行太长 | 按 16 字重新断行，或重跑 `plan` 生成 SRT |
| `qc` 报「时长在模板上限内」 | `--seconds` 超过模板上限 | 快讯 60 秒、深度 180 秒；超了拆片 |
| 交付单里的文件名对不上 | 换过主体 / 平台后没重跑 | 重跑 `plan`，命名一次生成，别手改 |

---

## 七、还不行时，把这三样发出来

1. `python3 scripts/run.py doctor --json` 的完整输出；
2. 出错那条命令的**完整命令行**（Key 用 `sk-***` 代替）；
3. 返回体原文（`--json` 的 stdout，或 stderr 的「失败：…」一行）。
