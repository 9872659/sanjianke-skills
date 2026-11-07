# 排错：按报错找原因

先看一条通则：**平台的参数错误也返回 HTTP 200**，只是 `{"code":0,"msg":"…","data":null}`。
所以判断成功要看 `code == 1` 且 `data` 非空，光看状态码会误判。

---

## 一、按报错原文找

| 报错原文（`msg`） | 出现在 | 原因 | 处理 |
|---|---|---|---|
| `请提供 image_url` | `pic_lipsync/submit` | 缺 `image_url` | `mouth --image` 给图；本地文件加 `--upload` |
| `text 模式请提供 audio_url 作为参考音色` | `pic_lipsync/submit` | `mode=text` 时缺参考音色 | `mouth --voice-ref` 给 3–10 秒单人清晰人声 |
| `无法从该地址下载媒体，请确认链接可公网访问、未过期，且允许本平台服务器拉取…` | `image_human/submit` | 平台拉不到 `file_url` / `ref_file_url` | 本地文件加 `--upload` 换成平台地址；公网图确认没有防盗链 |
| `任务不存在` | `GET /tasks/{id}` | `task_id` 写错，或任务已被清理 | `stitch` 看 `course.json` 里记的 `videoTaskId` / `voiceTaskId` 再查 |
| `当前请求未命中可用计费规格，请检查模型是否在支持范围内。` | 应用层 | 该应用先解析计费规格、后校验参数 | 看 `catalog` 里的端点与档位，用本包给的 `--mode` / `--quality` |
| `点数余额不足` | 任意付费调用 | 余额不够 | `doctor` 看余额；到 api.a7w.cn 充值 |
| `缺少必填参数` / `请提供 …` | `voice_tts/tts_async` | `text` 为空 | `plan` 生成讲稿后再跑 `voice`，`--only` 那几章确认有 `script` |
| `应用或 API 不可用或未配置价格` | 任意 `/apps/<app>/…` | 应用层兜底话术，**不可信**（假代号也返回同一句） | 用 `doctor` 的定价表判断链路是否已配价 |

---

## 二、按退出码找

| 退出码 | 含义 | 先看这里 |
|---|---|---|
| `2` | 用法错 | 报错里会点名缺哪个参数；`slide` 的 `--mode` 必填；选项**不能缩写**（`--jso` 会被拒） |
| `4` | 缺 `--yes` | 报错里已写好这次要花多少点，确认后加 `--yes` |
| `5` | 超 `--budget` | **一个请求都没发**，余额未动；调大 `--budget` 或减少章节/秒数 |
| `6` | 调用失败 / 自检没过 / 任务失败 | 看上一行 `status`；失败任务用 `status --task-id` 复查 |
| `1` | 内部错误 | 把 `--json` 打开再跑一次，把 `error.message` 贴出来 |
| `130` | 被 Ctrl-C 中断 | `course.json` 已落盘，重跑同一条命令会跳过已完成的章 |

---

## 三、最常见的四个现场

### 1. 自检里有一项是 `×`

```
× 速率卡一致（10/15/30/60 点/输入秒）   live={...} · defaultModel=...
```

说明网关的计费卡被改过。先跑 `cost` 看预估还对不对，再决定要不要按新价重算预算。
`口播口径一致（上游实际点数 ×5）` 这一项只核对 `markupPercent == 400`。

### 2. 配音好了，出片说「第 N 章还没有配音」

`slide` 只认 `course.json` 里每章的 `audioUrl`。两种修法：

```bash
# A. 先补齐配音（推荐）
python3 scripts/run.py voice --course course.json --yes

# B. 只补那几章
python3 scripts/run.py voice --course course.json --only 3,4 --yes
```

### 3. 出片按 fast 收钱、画面却像 standard

这就是 `image_human` 的默认档位自相矛盾：`params_schema` 默认 `standard`，计费卡默认 `fast`。
本包 `slide --mode` 必填，所以这个坑在本地就被堵住了 —— 如果账单和档位仍然对不上，先查 `cost --mode` 用的档位和实际下发的是不是同一个。

### 4. 轮询很久没动静

`GET /api/v1/tasks/{id}` 是只读的，查多少次都不花钱。等到超时（默认 900 秒）：

```bash
python3 scripts/run.py status --task-id task_xxx
```

任务还在跑就接着看。**同一条任务不要重新提交** —— 重新提交就是第二笔钱。

---

## 四、钱相关

### 为什么 `doctor` 一个 POST 都不发

实测：应用层 submit 会**先同步预扣再验参**。缺必填的请求照样产生一对流水：

```
12:01:41Z  冻结/预扣  -250  ref=reserve_sync:/api/v1/apps/image_human/submit
12:01:42Z  退款      +250  ref=refund:sync:/api/v1/apps/image_human/submit
```

`voice_tts/list_voices` 这种看着是「免费读取」的接口，也是每次 `-150 / +150`。
所以 `doctor` 只用 4 个只读 GET：`/apps`、`/pricing`、`/tasks/{id}`、`/user/balance`。

### 哪些接口是安全的

| 端点 | 实测 |
|---|---|
| `GET /api/v1/apps` · `/models` · `/pricing` | 免费 |
| `GET /api/v1/tasks/{id}` | 免费（本包唯一的轮询路径） |
| `GET /user/balance` · `/user/balance/logs` | 免费，`limit` 上限 1000 |
| `POST /api/v1/upload` | 免费（0 点/次） |
| `POST /api/v1/apps/{code}/query` | **每轮询一次就是一次的钱**，本包在 `http_json()` 里拦死 |

对照流水：`sync:/api/v1/apps/nano_banana/query` 108 次、每次 -72 点，合计 **-7,776 点**。

### 预算能算到个位吗

能，前提是带上 `duration`：

- `image_human` 带上 `duration` ⇒ 价格被费率卡锁死 = `rate × 秒数`
- 不带 ⇒ 平台按上游冻结点计费，估不准

所以 `slide` 永远把 `plan` 算出来的 `seconds` 显式传成 `duration`；平台探测的时长偶尔比你自己算的长一点，用 `--pad 10` 留 10% 余量。

---

## 五、中文控制台

Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）。cp936 编不出的字符
（对勾、叉号、人民币符号）会让脚本直接崩。

本包的处理：`sys.stdout.reconfigure(errors="replace")` 兜底，并且**输出只用 cp936 里有的符号**（`√` `×` `——` `·` `→`）。

自测有没有踩到：

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
$env:PYTHONIOENCODING="gbk"
python scripts\run.py doctor
echo $LASTEXITCODE   # 应为 0
```

如果看到 `UnicodeEncodeError`，说明有新的符号被写进了输出字符串，把那处换成 `√` / `×` 或纯 ASCII。

---

## 六、大纲解析

`plan` 只认三级结构：

```markdown
# 课程名            ← 一级标题，课程名
## 第 N 章 标题      ← 二级标题，一章一个
- 要点              ← 列表项，章下面的要点（`*` / `1.` 也认）
```

- 一个 `##` 都没有 → 退 `2`，提示大纲格式
- `###` 三级标题会被当一条要点收进当章，内容不丢
- 章节顺序 = 文件里出现的顺序，`index` 从 1 开始
- 每章秒数默认按 `字数 ÷ 4.5` 估；想统一成 60 秒就加 `--seconds 60`

---

## 七、还是不通

1. `python3 scripts/run.py doctor --json` —— 6 项检查的 json
2. `python3 scripts/run.py status --task-id <id> --json` —— 那条任务的原样返回
3. `python3 scripts/run.py log --limit 20` —— 本地台账，最近跑的几条和点数

三份贴出来就能定位。
