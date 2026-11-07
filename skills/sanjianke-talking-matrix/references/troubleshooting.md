# 排错：按报错找原因

先看退出码，再看下一节的报错原文。

| 码 | 含义 | 先做什么 |
|---|---|---|
| `0` | 成功 | — |
| `2` | 用法错 | 报错里点名了缺哪个参数；改完重跑，零请求 |
| `4` | 缺 `--yes` | 报错里已经写清这次要花多少点；确认无误再加 |
| `5` | 超 `--budget` | 一个请求都没发。调大 `--budget`（单位：点）或减规模 |
| `6` | 调用失败 / 任务失败 / 有 `unknown` | 看下面「提交成功但没有 task_id」「unknown 对账」两节 |
| `1` | 内部错 | `--json` 下看 stacktrace；把 `--host` 打印出来核对 |
| `130` | Ctrl-C | 已完成的都在 `matrix-state.json` 里，重跑接着补 |

---

## 一、启动与 Key

### `失败：没有 API Key。三选一…`（exit 2）

```bash
export A7W_API_KEY=sk-你的key          # Linux / macOS
$env:A7W_API_KEY="sk-你的key"          # Windows PowerShell
python3 scripts/a7w.py login --key sk-你的key    # 存进 ~/.a7w/config.json
```

`--key` 优先级最高。`catalog` / `cost` / `log` 三个纯本地命令不需要 Key。

### `鉴权失败（401）`

Key 失效或被删。到 [api.a7w.cn](https://api.a7w.cn/) 重新创建一把。

### `点数不足（402）` / `insufficient_points`

余额不够这次预估。先用 `cost` 看数，再用 `--limit 1` 跑一条，或充值后重跑。
重跑不会重复扣已完成的部分，只补没做完的。

---

## 二、两道闸门

### `这会真实提交：… 预计 **N 点** 确认请加 --yes。`（exit 4）

这是第一道闸门在正常工作，还没有任何请求发出去。
先把点数和 `cost` 的输出对一下，再决定加不加 `--yes`。

### `本次预计 N 点，超过 --budget M 点。一个请求都没发。`（exit 5）

第二道闸门。`--budget` 的单位是**点**（1 元 = 100 点）。
`--budget 2564` 才够 3 形象 × 4 音色那段 60 字文案。

---

## 三、配音

### `文案 N 字，超过同步配音接口 500 字上限。拆段再跑。`（exit 2）

`voice_tts/tts` 是同步接口，上限 500 字。把文案切成几段，每段各自跑一次矩阵，
成片再在剪辑里拼。本包不替你切，是为了让「一段文案 = 一批成片」这件事保持简单可对照。

### `配音失败（model_xxx）：…`（exit 6）

先确认 `--voices` 给的是 `reference_id`（`list_voices` 返回的第一列，形如 `model_xxxxxxxx`），
不是音色名字。想确认有哪些音色：`python3 scripts/run.py voices --yes`
（这条会先冻 150 点、随即全额退，净 0）。

### `返回里没有 audio_url：…`

上游返回了 `code:1` 但字段名不同。把原始返回贴进 issue：
`python3 scripts/run.py tts --voices model_x --content "测试" --json`。

---

## 四、上传形象图

### `上传失败（HTTP 401/403）`

Key 没有上传权限，或 Key 已失效。

### `上传失败（HTTP 413）`

图片太大。单文件上限按网关文档走，压到 5 MB 以内最稳。

### `形象 a.png 既不是 http(s) 地址也不是本地文件`

`--images` 支持两种：本地路径（本包自动上传，0 点）、`http(s)://` 开头的地址。
相对路径按当前工作目录解析，`cd` 到图片目录再跑最省心。

---

## 五、提交与轮询

### `提交失败（HTTP 200）：请提供 image_url` / `text 模式请提供 audio_url 作为参考音色`

应用层校验报错，`code:0` 但 HTTP 是 200 —— 成功判据是 `code == 1`，不是状态码。
本包正常路径不会出现这两句；出现说明上传返回的地址没取到，重跑一次上传即可。

### `无法从该地址下载媒体，请确认链接可公网访问…Could not resolve host: …`

上游拉不到你的图/音频。最常见是给了站外地址或已过期的临时地址。
形象图请用本包自动上传得到的 `oss.gpu.likeadmin.cn/openapi/…`；音频请用配音返回的地址。

### `url_not_allowed`

图片/音频地址不在平台白名单。正确路径：先 `POST /upload` 拿地址，再提交（本包 `run` 自动做）。

### `提交成功但没有拿到 task_id`

响应里没有 `task_id`，这条不改 state。把原始返回贴出来：
`python3 scripts/run.py run … --json`。**不要手动重发** —— 先看 `status --workdir` 有没有这条。

### `状态 unknown` / `有 N 条提交结果未知`

提交时网络中断，网关那边可能已经建了任务。先对账：

```bash
python3 scripts/run.py status --workdir ./matrix      # 只走免费 GET /tasks
```

对账后仍是 `unknown`，才去掉 state 里那条再重跑（`--limit` 可以只补这一条）。

### `任务不存在`

两种情况：`task_id` 打错；或任务已被平台清理（保留期以网关为准）。
`status --workdir` 会把所有 task_id 重查一遍，不用一个个试。

### `等待超时（N 秒），任务可能仍在跑`

视频任务排队久了会这样。任务没丢：

```bash
python3 scripts/run.py status --task-id task_xxx
```

**不要重新提交** —— 重提就是再扣一次。

### `刚 completed 但成片地址是空串`

实测竞态（数字人、剪辑、TTS 都吃）。隔几秒再 `status --task-id` 一次，地址就出来了。

---

## 六、网络与并发

### `连不上 … （已重试 N 次）` / `WinError 10054 远程主机强迫关闭了一个现有的连接`

网关会重置空闲连接，视频类任务几乎必踩。本包对 `GET /tasks`、`POST /upload`、
`POST /tts` 做退避重试；付费 `submit` **只发一次**（5xx 时任务可能已建，重发等于再扣一次）。

### `HTTP 502 / 503 / 504`

上游抖动。等 1–2 分钟重跑，已完成的会跳过。并发压得太高也容易触发：
把 `--concurrency` 从 3 降到 1–2 再试。

### 轮询把控制台刷满

`--interval` 调大（默认 8 秒），或 `--no-wait` 只提交，之后用 `status` 批量对账。

---

## 七、文件与状态

### `这个 workdir 里没有矩阵记录：…/matrix-state.json`（exit 2）

`status --workdir` 要指向跑 `run` 时的同一个 `--workdir`。换过目录就用 `--state` 指过去。

### 成片名重复 / 覆盖

命名规则是 `{prefix}_{形象序号}-{形象名}_{音色}.mp4`，同一组参数重跑会覆盖同一位置（这是故意的）。
要保留多版就换 `--prefix` 或换 `--outdir`。

### 换了文案，旧成片还在目录里

state 的 key 里带文案指纹，换文案会按新指纹新建一批 combo；旧成片留在原目录，方便对比。
想干净重来就把整个 `--workdir` 换个新目录。
