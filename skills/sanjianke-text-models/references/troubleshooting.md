# 排错：按报错找原因

先跑一次免费自检，多数问题它会直接指出来：

```bash
python3 scripts/run.py doctor
```

---

## 一、先认出这五种「看起来成功、其实没通」

文本线最坑的地方：网关有三种完全不同的失败形态，状态码各不相同。

| 你看到的 | 直译 | 实际含义 | 怎么办 |
|---|---|---|---|
| `HTTP 200` + `{"code":0,"msg":"模型不存在或未上架"}` | 200 应该是成功 | **这个模型没挂到 chat 入口** | 换模型；`check` 逐个复核；claude 13 变体都是这一档 |
| `HTTP 200` + `{"code":0,"msg":"model参数不能为空"}` | 同上 | 请求体里没有 `model` 字段 | 补 `--models`；这是 doctor 的探针 1 的正常返回 |
| `HTTP 404` + 一大段 `<!DOCTYPE html>` | 404 找不到 | 请求落到了**站点首页**，这条路没配模型 | 换模型；或确认路径拼写（多写 `/v1` 会 400） |
| `HTTP 422` + `missing field 'messages'` | 参数校验 | 入口是通的，只是缺 `messages` | 正常调用会带 messages，无需处理 |
| `HTTP 502/503` + 站点首页 HTML | 网关抖动 | 负载均衡临时挂了 | 等 1 秒重跑；`doctor` 已内置一次重试 |

**判断口诀**：看 `code`，不看状态码。`code == 0` 就是没过；`choices` 里有内容才是成功。

---

## 二、按报错原文查

### `模型不存在或未上架`（HTTP 200，code 0）

```
{"code":0,"msg":"模型不存在或未上架","data":null}
```

- 实测：`claude-sonnet-4-5`、`claude-opus-5` 等 13 个 claude 变体全部如此
- 原因：它们目录里只声明 `anthropic_messages` 协议，而本网关没有 `/v1/messages` 端点
- 处理：换 `p` 为 `chat` 的模型（`catalog` 里标 `√ 能调` 的那批），或先 `check --models 型号` 验一遍

### `The model ... does not exist or you do not have access to it.`（HTTP 404，JSON）

```
{"code":0,"msg":"The model `Qwen3.7-Max` does not exist or you do not have access to it."}
```

- 实测：`Qwen3.7-Max`
- 处理：换 `Qwen3.7-Plus` / `Qwen3.5-Flash` 等能调的一档

### `invalid_model`（HTTP 401）

```
{"error":{"message":"The model does not exist or you do not have access to it.",
          "type":"invalid_model","code":"invalid_model"}}
```

- 实测：`ERNIE-5.0-Thinking`
- 处理：同上一档，换型号

### `该模型已停用`（HTTP 400）

```
{"error":{"message":"该模型已停用，请更换或升级为其他模型版本。","type":"400","code":"400"}}
```

- 实测：`DeepSeek-V3.2`
- 处理：换 `DeepSeek-V4-Pro` 或历史别名 `deepseek-chat`

### `INSUFFICIENT_BALANCE`（HTTP 403）

```
{"error":{"message":"账户余额不足，如需继续使用请及时充值",
          "type":"INSUFFICIENT_BALANCE","code":"INSUFFICIENT_BALANCE"}}
```

- 实测：`gpt-5.5`
- 处理：换模型；同一个包内其他模型不受影响

### `当前暂无可用渠道` / `service_rejected`（HTTP 503）

```
{"error":{"message":"当前暂无可用渠道","type":"http_503","code":"http_503"}}
{"error":{"message":"服务暂不可用，请稍后重试","type":"service_rejected","code":"service_rejected"}}
```

- 实测：`gemma-4-26B-A4B-it`、`gemini-3-pro`
- 处理：过几分钟再试；`chat` 会把这档记为「没出话」并继续跑下一个，不中断整批

### `list index out of range`（HTTP 400）

- 实测：`LegalOne-8B`、`AutoGLM-Phone-9B-Multilingual`、`KAT-Dev`、`Sinong1.0-32B`
- 处理：正常带 messages 调用即可；这条也是 `check` 判定「能调」的依据之一

### `Role must be in [...]` / `Empty input messages` / `messages is empty`（HTTP 400）

- 实测：`kimi-k3`、`Kimi-K2.6`、`GLM-5.2`、`Qwen3.5-Flash`、`Qwen3.8-Omni-Flash`、`deepseek-chat`、`MiniMax-M3`
- 处理：无需处理

### `unknown_endpoint`（HTTP 404）

- `POST /v1/messages` 的固定回话；Anthropic 专线没有独立端点
- 处理：claude 系模型也走 `/api/v1/chat/completions`

### `RemoteDisconnected` / `Remote end closed connection without response`

- 原因：网关偶发掐连接，拉 522 KB 的 `/api/v1/models` 时最容易撞上
- 处理：`run.py` 的只读 GET 已内置 3 次重试（退避 0.6s / 1.4s）；POST **不重发**，避免二次预冻

---

## 三、钱相关的三个疑问

### 余额没变化，但流水里有 -60 / +60

正常。每次调用先 `reserve_sync` 冻 60 点，结束后按结果退回：

```
charge -60  reserve_sync:/api/v1/chat/completions
refund +60  refund:sync:/api/v1/chat/completions
```

余额显示到 4 位小数，单看余额看不出这 60 点动过。**净额 = charge + refund**，`chat` 的
`actualPoints` 就用这个口径。

### 为什么一次 900 token 的对话要 60 点，明明按 token 算只有 0.1 点

价目表的通配规则是「对外 = 上游点数 x 2、单笔保底 50 点」，实测预冻 60 点。
短对话的真实下限就是这 60 点；要摊薄单价，把 `--out-tokens` 提到几千、或一次问长问题。

### `--budget 50` 直接退 5，一个请求都没发

设计如此。闸门在发请求之前算：`预计点数 > --budget` 就 `exit 5`。
`check` 的预冻总量也算进闸门（每个模型 60 点），所以 `check --models a,b,c` 至少要 `--budget 180`。

---

## 四、闸门与退出码

| 退出码 | 什么时候出现 | 提示里有什么 |
|---|---|---|
| `2` | 缺 `--prompt`、模型数超限、`--out-tokens` 越界、命令行缩写 | 具体哪一条不合格 |
| `4` | 没加 `--yes` 就真调 | 会告诉你要调几个、预计多少点、多少元 |
| `5` | 预计点数超 `--budget` | **一个请求都不发**，并给出建议的 `--budget` |
| `6` | 全部模型都没出话 | 每个模型的判定与原文 |
| `1` | 内部异常 | traceback |
| `130` | Ctrl-C | 已中断 |

`--json` 模式下失败也只输出一个 JSON 文档：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`kind` 取值：`usage` / `gate` / `confirm` / `budget` / `call` / `interrupt` / `internal`。

---

## 五、Windows 控制台中文乱码

现象：输出里出现 `?` 或 `UnicodeEncodeError: 'gbk' codec can't encode ...`。

- 原因：stdout 被重定向时 Python 用本地编码（cp936），`√` `×` 之外的个别符号编不出来
- 处理：`run.py` 已对 stdout/stderr 调 `reconfigure(errors="replace")`，全文只用
  cp936 覆盖得到的字符（`√ × · → ★ 「」`），金额一律写「元」
- 自测：`PYTHONIOENCODING=gbk python scripts/run.py doctor`，退出码应为 `0`，输出严格按 GBK 解码通过

其它小毛病：

| 现象 | 原因 | 处理 |
|---|---|---|
| 目录里冒出 `__pycache__` | 没设 `PYTHONDONTWRITEBYTECODE` | 删掉；命令前加 `PYTHONDONTWRITEBYTECODE=1` |
| 表格中文列错位 | 字体把全角当半角 | 代码里按「东亚宽字符算 2 列」补齐，换个等宽字体即可 |
| `--json` 里混进别的行 | 把 `--json` 和别的输出混看 | stdout 只有一个 JSON 文档；进度信息都走 stderr |
| 想跑目录外的型号 | 内置快照只有 92 条 | 直接写型号名，本包按 60 点保底报；`check` 先验 |

---

## 六、最省事的排查顺序

```bash
python3 scripts/run.py doctor                       # 1. 端点 / Key / 余额 / 流水净额
python3 scripts/run.py check --models 你的型号        # 2. 这个型号到底通不通（净 0 点）
python3 scripts/run.py cost --models 你的型号 --prompt "…"   # 3. 要花多少（免费）
python3 scripts/run.py chat --models 你的型号 --prompt "…" --dry-run   # 4. 请求长什么样
python3 scripts/run.py chat --models 你的型号 --prompt "…" --yes      # 5. 真跑
```

每一步都能单独停下来；前 4 步合计 0 点花费。
