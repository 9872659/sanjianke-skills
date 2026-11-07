# 排错：按报错找原因

先跑 `python3 scripts/run.py doctor`（0 点），8 条里有 × 就照下表对。

---

## 一、Key 与权限

### `失败：没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / a7w.py login --key …`（exit 2）

三种填法任一：`--key sk-…`、`export A7W_API_KEY=sk-…`（Windows `$env:A7W_API_KEY="sk-…"`）、
`python3 scripts/a7w.py login --key sk-…`。后两种会写进 `~/.a7w/config.json`。

### `HTTP 401` / `HTTP 403`

Key 失效或没有该模型权限。到 [api.a7w.cn](https://api.a7w.cn/) 重新创建 Key。
`doctor` 的第一条「Key + 余额接口可达」用 `GET /user/balance` 测，拿到非 200 就是这一条。

### `doctor` 第一条过、后面全 ×

大概率是 `--host` 写错。默认 `https://api.a7w.cn`，**不要**带 `/api/v1` 后缀（本包自己拼）。

---

## 二、出图（images/generations）

### `HTTP 422 · prompt: String should have at least 1 character`

`prompt` 是空字符串。这是 `doctor` 故意打出来的探针结果 —— 用户侧看到它，说明 `--prompt` 或
`--client` 没传进来。本包不给 prompt 时按行业话术本地拼，检查 `--kind` 是否在
`logo / card / rollup / packaging / avatar / cover / manual` 里。

### `HTTP 400` 且提到 16 / ratio / pixel

自定义 `--size` 撞四条硬约束。用 `catalog` 里给的七种物料尺寸最稳：

```
1024x1024  1536x1024  1024x2560  1536x864  1040x1472
```

本包在本地就校验，撞了直接 exit 2，不会发请求。

### 响应里没有图，`data` 是空数组

`returned = 0` 时 `gen` 退 6，并打印原始返回前 800 字符。三种常见原因：

- `prompt` 被上游安全策略拦（换描述性说法，去掉真人姓名与品牌词）
- `n` 与上游能力不匹配（1–4）
- 上游临时故障（重试一次，按实际返回张数计费，没出图不扣）

### 拿到的不是 URL 而是 `b64_json`

正常的。本包默认 `response_format=b64_json` 并自动解码落盘：
`<outdir>/<prefix>-01.png`。想要 URL 就自己拼请求体，链接约 3 小时过期。

---

## 三、改图（images/edits）

### `HTTP 500 · image is required`

multipart 里没有 `image[]`。本包 `edit` 缺 `--image` 时本地就退 2，看到这条说明文件路径
给了但读不到 —— 检查路径里的中文与空格，用相对路径试一次。

### `HTTP 400 · 参数不对`

`--size` 传了非法值，或 `--output-format` 不在 `png/jpeg/webp` 里。
透明背景只支持 `png` / `webp`。

### 改图后构图变了

`images/edits` 是重绘，不是图层编辑。要「只改一个字」的场景，把改动写进 prompt 的
**局部描述**里（「只把右下角那行字改成 XX，其余不动」），并多给一张参考图。

---

## 四、参考图派生（nano_banana）

### `失败：image_urls 要用平台托管的地址（当前 example.com）`（exit 2）

本包要求 `image_urls` 是平台地址。两种走法：

```bash
# 推荐：本地图直接给，refine 会自动 upload（0 点）
python3 scripts/run.py refine --ref ./logo-01.png --kind card --prompt "…" --yes

# 已经传过，直接给地址
python3 scripts/run.py refine --ref-url "https://oss.gpu.likeadmin.cn/openapi/…" \
    --kind card --prompt "…" --yes
```

白名单：`*.a7w.cn`、`cdn2.jiujiushuyuan.cn/vr/`、`oss.gpu.likeadmin.cn/openapi/`。

### `{"code":0,"msg":"当前请求未命中可用计费规格，请检查模型、分辨率是否在支持范围内。"}`

`model` 与 `resolution` 组合不在该模型的档位里。本包默认 `nano-banana` + `1K`，
是文档里的默认组合；要换模型先看 `a7w-nano-banana` 的模型表。

### 返回 `code:1` 但没有 `task_id`

看 `data.status`。有 `task_id` 就 `status --task-id` 轮询；**只用**
`GET /api/v1/tasks/{id}`（0 点）。`/api/v1/apps/nano_banana/query` 落在
`/apps/nano_banana/*` 的通配规则里，本包一律不用。

### `status` 一直 `pending` / 几分钟后 `failed`

`failed` 会全额退。重提一次；连续两次 `failed` 就换 `--resolution 1K` 或缩短派生描述。

---

## 五、钱

### `失败：… 预计 N 点，超过 --budget M 点（1 元 = 100 点），一个请求都没发。`（exit 5）

预算闸门。调大 `--budget`，或减 `--n`、把 `--set` 从 `pro` 降到 `standard`。
`--budget` 单位是**点**：3000 点 = 30 元。

### `失败：… 会真实扣约 N 点（0.06 元）。确认请加 --yes。`（exit 4）

第二道闸门。真跑加 `--yes`，先看请求加 `--dry-run`。

### 钱包被动过但任务没成

`reserve_sync` 的先冻后退。查 `GET /user/balance/logs?limit=20`，找 `reserve_sync:` 与
`refund:` 成对出现；净额为 0。

### 想核这一轮到底花了多少

用兄弟包 `sanjianke-billing` 的 `overview`（0 点），或直接看流水最后一条的时间戳 ——
`doctor` 的「花费复核」就是打这条，前后一致说明本轮没动账。

---

## 六、本地三项（palette / plan / qc）

### `qc` 报 `商标 / 名人词零出现` ×

prompt 里出现了词表里的词（耐克、苹果、迪士尼、春晚、奥运、名人姓名一类）。
改成描述性写法：「勾形运动标志」而不是品牌名。

### `qc` 报 `字体全部在可商用白名单内` ×

手改过 `plan.json` 里的字体。白名单：思源黑体 / 思源宋体 / 阿里巴巴普惠体 / MiSans /
OPPO Sans / HarmonyOS Sans / Noto Sans SC / Noto Serif SC / Inter / Roboto / Montserrat /
Source Han Sans / Source Han Serif。

### `qc` 报 `配色对比度` ×

某个底色配不出 4.5:1（正文）或 3.0:1（大字）的字色。换 `--hue` 或调 `plan.json` 里的 hex。

### `qc` 报 `命名统一` ×

文件名没按 `日期_客户_物料_尺寸或序号`。重新跑一次 `plan` 覆盖即可。

### `plan` 的目录在哪

`~/.a7w/brand-vi/<客户>-<日期>/`，5 个文件：`plan.json` `prompts.md` `delivery.md`
`palette.md` `type.md`。`qc` 不带 `--plan` 时取最近修改的一份。

---

## 七、Windows 控制台

### `UnicodeEncodeError: 'gbk' codec can't encode character …`

本包对 `sys.stdout / sys.stderr` 做了 `reconfigure(errors="replace")`，并且输出只用
`√ × ·` 这类 GBK 里有的符号，正常不会再崩。真崩了说明有人往输出里塞了 emoji。

### 输出里出现 `?` 而不是中文

`PYTHONIOENCODING=gbk` + 本地编码不认这个字。**实测**：`PYTHONIOENCODING=gbk python run.py doctor`
→ exit 0，输出无替换字符。要干净中文就 `chcp 65001` 或 `$env:PYTHONIOENCODING="utf-8"`。

### `--json` 的中文在管道里乱码

本包在 `--json` 时把 stdout 钉成 UTF-8，下游按 UTF-8 解就行。人读模式仍走本地编码。

### 跑一次就多出 `__pycache__`

每条命令前加 `$env:PYTHONDONTWRITEBYTECODE="1"`。本包 import 时也设了
`sys.dont_write_bytecode = True`，但父进程环境更早生效。

---

## 八、退出码速查

| 码 | 谁给的 | 怎么办 |
|---|---|---|
| `0` | 成功 | — |
| `1` | 内部错 | 把 traceback 全文贴出来 |
| `2` | 用法错 | 看消息里点名的那一个参数 |
| `3` | `doctor` / `qc` 没过 | 按上面第 1 / 6 节对 |
| `4` | 缺 `--yes` | 加 `--yes`，或先 `--dry-run` 看请求 |
| `5` | 超 `--budget` | 调大预算或减少量，**没有发请求** |
| `6` | 调用失败 | 看 HTTP 状态与 `error.message` |
| `130` | Ctrl-C | 重跑；已提交的派生用 `status` 查 |
