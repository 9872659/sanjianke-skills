# AI 配乐 —— 排错：按报错找原因

**先跑 `python3 scripts/run.py doctor`** —— 免费、0 个 POST、0 冻结，能一次排掉一半问题。

---

## 一、Key 相关

### `失败：没有 API Key`（exit 2）

三处都没读到，按优先级查：

1. `--key sk-...`
2. `echo $env:A7W_API_KEY`（PowerShell） / `echo $A7W_API_KEY`（bash）
3. `~/.a7w/config.json` 里的 `{"key": "sk-..."}`

最省事：`python3 scripts/a7w.py login --key sk-你的key`。

### `doctor` 第一项 `Key 有效 + 模型目录可达` 是 `×`

`GET /api/v1/models` 拿不到 200。Key 失效或没权限，去 [api.a7w.cn](https://api.a7w.cn/) 重新创建。

### `doctor` 第二项 `应用在架 + 4 个配乐接口齐全` 是 `×`

`GET /api/v1/apps` 里没找到 `media_services_33`，或 4 个接口码有缺失。
先 `catalog` 看在线接口码，再确认没把 `--host` 指到别的网关。

---

## 二、提交被拒绝（HTTP 200 但 `code:0`）

**这是最常见的形态**：网关校验失败也返回 HTTP 200，只有 `code` 是 0，`msg` 里写清缺什么。

```
{"code":0,"msg":"input.custom_mode: 缺少必填参数；input.instrumental: 缺少必填参数；input.model: 缺少必填参数","data":null}
```

| `msg` 里出现 | 原因 | 处置 |
|---|---|---|
| `input.model: 缺少必填参数` | body 里没 `model` | 本包总会传；出现在手写 curl 时 |
| `input.custom_mode / instrumental` | 少了这两个必填布尔 | 同上，本包恒传 |
| `input.audio_id: 缺少必填参数` | `extend` 没给 `--audio-id` | 从 `gen` 或 `task` 的输出里取 |
| `input.task_id: 缺少必填参数` | `lyrics` 没给 `--task-id` | 同上 |
| `input.sound_tempo: 类型不正确` | 省掉了 `sound_tempo` | 见下一节 |
| `不在允许选项内` | `sound_key` 写了枚举外的值 | 用 `catalog` 里的 25 个调性 |

### `input.sound_tempo: 类型不正确`

schema 里 `sound_tempo` 标「可选、默认 Auto」，真省掉它上游就报这句。
**本包的 `sound` 子命令总是显式传** `--tempo`（默认 120），所以正常不会遇到；
手写调用时把 `sound_tempo: 120` 补上。

### 参数报错之后钱还在不在

在。`reserve_sync` 会先冻 60 点，校验失败再全额退回，**净 0、余额不变**，只是调用数 +1。
想看这一刻的钱包状态：

```bash
curl -H "Authorization: Bearer $A7W_API_KEY" https://api.a7w.cn/api/v1/user/balance
curl -H "Authorization: Bearer $A7W_API_KEY" https://api.a7w.cn/user/usage
```

---

## 三、任务相关

### `任务 … 查不到（返回为空）`（exit 6）

`GET /api/v1/tasks/<id>` 返回 `{"code":0,"msg":"任务不存在"}`。三种可能：

1. `task_id` 抄错了（`task_` 前缀别丢）
2. 任务已过期，需要重新提交（会再冻结一次）
3. 用的是别的端的 `task_id`（本包只认这个网关的）

### 轮询超时 `等了 N 秒还没完成`（exit 6）

**任务没丢。** 接着取，不要重新提交：

```bash
python3 scripts/run.py task --task-id <那个 task_id>
```

`gen --wait 1200` 可以把等待上限拉长；`--no-wait` 提交完立刻走人，后面免费查。

### 任务 `failed`

`task` 会打印 `error` / `failReason`。常见是内容审核或风格标签被拒，换一版 `--prompt` 重提。
失败的任务不计费（冻结会退）。

---

## 四、花钱相关

### `失败：下限就要 60 点，超过 --budget 10 点。一个请求都没发。`（exit 5）

第一道闸门在工作。`--budget` 的**单位是「点」**，1 元 = 100 点。
调大预算或减少次数：`gen --budget 200 --yes`。

### `失败：这会真实提交 1 次配乐生成，下限 60 点（0.60 元）`（exit 4）

没给 `--yes`。**故意的**：花钱的动作必须显式确认。

想看要发什么请求而不花钱：

```bash
python3 scripts/run.py gen --prompt "紧张弦乐" --duration 180 --dry-run
```

### 实际扣费比 `cost` 多

`cost` 给的是**下限**：`max(50, 上游 x 2)`。上游真实点数只有跑完才看得到，按任务详情结算。
用你观察到的数字换算：`cost --upstream 65 --calls 2`。

### 为什么一次配乐就冻 60 点，规则写的是 50 点

`pricing` 的 `*` 规则写 `minPoints: 50`，但上游这一档的冻结基数是 30 点，x2 之后就是 60。
本包按 60 点/次给估算，比按 50 点更接近真账单。

---

## 五、`plan` 相关

### `给个视频时长：--duration 180（秒）`

`plan` 不读视频文件（零依赖，不调 ffprobe）。先自己拿时长：

```bash
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 input.mp4
```

### `--shots 要逗号分隔的秒数`

`--shots "14,47,96"`。写成 `--shots 14 47 96` 会被当成多余的位置参数。

### 卡点偏移看着不对

偏移 = 小节边界 − 你的切点，正数表示边界在切点之后（把切点往后吸）。
BPM 换一下整张表都会变：`plan --duration 180 --bpm 128`。

### `对齐 差 0.52 秒`

正常。小节长度除不尽视频时长，方案给的是「最接近的小节边界」，剪辑时按这个收口。

---

## 六、`mix` 相关

### `找不到音频 seg-1.mp3`（exit 2）

`mix` 默认校验文件存在。要么先把音频下载到当前目录，要么加 `--allow-missing` 只出清单。

### 成片没声音 / 声音被截断

三条常见原因：

1. 音频总长比视频短——`aloop` 已经补循环，检查 `--duration` 是不是填小了
2. `--level` 太低（默认 0.35），提到 0.5 试试
3. 原视频本身有音轨：本包的命令是 `-map 0:v -map "[aout]"`，**原声被丢掉了**。
   要保留原声做混音，用 `amix` 把 `[0:a]` 一起并进来

### 想调音量包络 / 侧链压人声

在 `mix` 出的命令里，`[am]` 之后就是最终配乐轨。加一段
`[am][3:a]sidechaincompress=threshold=0.05:ratio=8[ad]`，把人声当触发轨，解说一起来配乐自动让路。

---

## 七、中文与控制台

### Windows 控制台里 `√` 变成问号 / 直接报 `UnicodeEncodeError`

本包已经把 `sys.stdout` / `sys.stderr` 都设成 `errors="replace"`，并且只用 `√` `×` `元` 这些 cp936 里有的字符，
正常不会再崩。真要看干净中文：

```powershell
$env:PYTHONIOENCODING = "utf-8"; chcp 65001
```

### 命令里带中文参数被吃掉

PowerShell 里给含中文/空格的值**加引号**：`--prompt "雨夜霓虹，慢板合成器"`。
批量脚本建议写成 `.py` 文件再跑，别用内联 `python -c`。

---

## 八、还想更省事

```bash
python3 scripts/run.py doctor && python3 scripts/run.py plan --duration 180
```

`doctor` 通过、`plan` 看着顺，再决定跑 `gen`。这样最多只花一次 60 点。

---

## 九、联系

加技术微信时说一下是从 `sanjianke-ai-soundtrack` 找过来的，直接给你配套的 API Key 与能跑的示例
（微信号见 `SKILL.md` 末尾「联系我们」）。
