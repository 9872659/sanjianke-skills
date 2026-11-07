# 排错：按报错找原因

**先跑 `python3 scripts/run.py doctor`** —— 免费、0 个 POST、0 点，能一次排掉一半问题。

---

## 一、Key 与鉴权

### `失败：没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / …`（exit 2）

三处都没读到。按优先级检查：

1. `--key sk-...`
2. `echo $env:A7W_API_KEY`（PowerShell）/ `echo $A7W_API_KEY`（bash）
3. `~/.a7w/config.json` 里的 `{"key": "sk-..."}`

最省事：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### `HTTP 401` / `Missing or invalid relay API key`

Key 无效、过期或写错。到 [api.a7w.cn](https://api.a7w.cn/) 重新创建。
确认没把 `Bearer ` 重复写进环境变量。

### `点数不足（402）`

账号点数用完。到 [api.a7w.cn](https://api.a7w.cn/) 充值后重试。

---

## 二、配音（`voice`）

### `--voice 要音色 ID（67 个枚举之一），不是任意名字。xxx`

`schema` 的 `voice.enum` 是固定 67 个 ID。本包支持填名字，但**本地精确且唯一**才转：

```bash
python3 scripts/run.py catalog --voices     # 全列 ID / 名字 / 特点
```

`Brian` -> `nPczCjzI2devNBz1zQrb`、`Bella` -> `hpp4J3VqNfWAUOO0d1Us` 这类唯一名字可以直接填；
重名的（两个 `Mark`、两个 `Hope`、两个 `Viraj`）请填 ID。

### `input.text: … 超过最大长度` / 长文本被上游拒

一条请求的 `text` 上限是 **5000 字**。本包按行自动切块，一请求一块（`-dub-01` / `-dub-02` …）。
想让条数变少：先精简译文（字幕本来就该短），或把 `--ratio` 调准让预算估得准。

### `input.voice: 不在允许选项内`

ID 写错了（多一个字符、大小写不对，或者你把名字直接塞给了上游）。
本包在本地就校验，正常走不到这一步；如果走到了，说明 `--voice` 绕过了本地解析。

### 带上 `language_code` 报错

`multilingual_v2` 不用这个字段：schema 原文写明只有 Turbo v2.5 / Flash v2.5 支持语言强制，
其他模型带上会返回错误。本包不传它，配音语言由翻译稿本身决定。

### 提交成功但返回里没有音频地址

任务可能还在跑，或上游换了键名。先查任务：

```bash
python3 scripts/run.py task --task-id task_xxx --json
```

本包的解析器对 `audio_url` / `audioUrl` / `url` / `result.*` 递归兜底；
`voice --json` 会把原始返回结构打出来，把那段贴出来就能定位。

### 多块配音只有多个 mp3

正常：每条请求各出一个文件（`-dub-01` / `-dub-02` …）。拼接与混轨交给剪辑软件或 ffmpeg：

```bash
ffmpeg -f concat -safe 0 -i list.txt -c copy dub.mp3
```

---

## 三、转写（`transcribe`）

### 字幕没有标点

`stt` 的字级 segment 本身不带标点，标点只在 `result.text`。本包按序回填；
**两边对不齐时原样返回**（宁可不补，也不补错位）。字级与全文差太多时就会这样，
此时字幕仍然可用，只是标点少。

### 字幕一行字太多 / 太碎

调两个参数：

```bash
--max-chars 14     # 单行最多多少字（默认 18）
--gap 1.0          # 停顿超过多少秒断行（默认 0.7）
```

### `转写没返回可用时间轴`

返回里没有 `segments`。常见原因：传的其实是**纯音频但格式不被识别**、或上游只回了 `text`。
先看原始返回（报错里带了前 300 字），必要时重跑一次。

### 本地文件传不上去

`stt` 的 multipart 字段名是 **`audio`**（本包已按此发送）。
文件超过网关体积上限时改用 `--audio-url`（先把文件放到可公网访问的地址）。

---

## 四、翻译（`translate`）

### `翻译返回的条数对不上（要 N 条，解析到 M 条）`

模型没按 JSON 数组回。本包会先按括号配平切数组，切不出来再按行兜底；
两种都对不上就报错（不猜，错一行整条字幕就错位）。

怎么办：换模型（`--model deepseek-chat`）、把长片拆短、或直接 `--script` 自带台词稿。

### 翻译要花多少点？

平台不公布文本模型点数，本包只报 token。`usage` 里 `prompt_tokens` / `completion_tokens` /
`total_tokens` 会出现在 `--json` 输出里；金额按你自己的单价算。

---

## 五、字幕（`subtitle`）

### `--align dub 要给 --dub（voice 产出的 -dub-01.timestamps.json）`

用配音时间轴重排，前提是配音时加了 `--timestamps`：

```bash
python3 scripts/run.py voice … --timestamps --outdir ./出片 --yes
python3 scripts/run.py subtitle --in ./出片/localize-ja.json --to ja \
    --align dub --dub ./出片/localize-dub-01.timestamps.json --outdir ./出片
```

### 中文字幕在播放器里乱码

本包固定写 UTF-8 无 BOM。个别老播放器只认 GBK：用编辑器另存为 GBK 再挂载，
或用 VLC 手动指定 UTF-8。

---

## 六、钱相关

### `失败：… 预计 N 点，超过 --budget M 点（1 元 = 100 点）。一个请求都没发。`（exit 5）

闸门在工作。`--budget` 单位是**点**（1 元 = 100 点），默认 600。调大或缩短片子。

### `失败：… 会真实计费：预计 N 点（X 元）… 确认请加 --yes。`（exit 4）

缺 `--yes`。故意的：转写和配音都花钱，必须显式确认。想先看请求：

```bash
python3 scripts/run.py run --input 片子.mp4 --to en --dry-run
```

### `run` 在转写之后停下来说超预算

转写已完成（这 120 点花掉了），翻译与配音没发。这是**保护**：宁可停在便宜的步骤之后，
也不让昂贵的配音请求冲出去。用 `--minutes` / `--chars` 把估算给准，或调大 `--budget`。

### 实际扣费比 `cost` 多

`cost` 给的是**下限**：配音每条按 60 点保底算，成交价 = 上游实际点数 x 2。
以 `/user/balance/logs` 的结算记录为准。

### 请求失败了会扣钱吗？

- `voice_tts/stt`：失败全额退（预扣 150 会回来）。
- `elevenlabs` 配音：失败全额退（预扣 60 会回来）。
- 任务跑起来之后失败：按 `refund:task_failed:<task_id>` 退。

---

## 七、超时 / 轮询

### `等了 N 秒还没完成`

任务没丢。**不要重新提交**（会再扣一次），接着取：

```bash
python3 scripts/run.py task --task-id task_xxx
```

或者调大 `--wait`（默认 300 秒）/ `--every`（默认 3 秒）。

### 为什么不自动重试 POST

一次提交就是一次扣费，网络抖动后重试等于再扣一次。本包只对**只读 GET** 退避重试；
POST 失败会带着 `task_id`（如果有）报出来，让你自己决定。

### 为什么轮询不用 `/query`

应用层 `/query` 是**计费接口**：一次轮询就是一次的钱（历史上 nano_banana/query 72 点/次）。
本包只用 `GET /api/v1/tasks/<task_id>`，免费。

---

## 八、`--json` 与退出码

### `unrecognized arguments: --out`

本包不允许长选项前缀缩写（`allow_abbrev=False`，父命令与每个子命令都关了）。写全称。

### `--json` 模式下 stdout 不是 JSON

`--json` 时 stdout 只有一个 JSON 文档；进度与提示都走 stderr。
如果你把 `2>&1` 混进同一个流，看到的就是「JSON + 提示」——分开重定向即可。

```bash
python3 scripts/run.py doctor --json > out.json      # 提示留在屏幕
```

### Windows 控制台中文乱码

脚本已做两件事：`sys.stdout.reconfigure(errors="replace")`，以及所有输出只用
`√` / `×`（cp936 都有）、金额写「元」。仍有乱码时：

```powershell
$env:PYTHONIOENCODING="gbk"     # 或 chcp 65001 后用 utf-8
```

### 退出码速查

| 码 | 含义 | 先看哪 |
|---|---|---|
| `2` | 用法错 | 报错里的参数名；`--help` |
| `4` | 缺 `--yes` | 加 `--yes`，或先 `--dry-run` |
| `5` | 超 `--budget` | 调大预算或缩短片子 |
| `6` | 调用失败 | 报错里的上游原文；`task --task-id` |
| `1` | 内部错 | 带完整 traceback（stderr）报给维护者 |

---

## 九、还想更省事

```bash
python3 scripts/run.py doctor && \
python3 scripts/run.py cost --minutes 10 && \
python3 scripts/run.py run --input 片子.mp4 --to en --outdir ./出片 --yes
```

`doctor` 通过才继续 —— 省掉一次白跑。

更多资料：`references/api-contract.md`（端点、参数、67 音色、价目原文）。
