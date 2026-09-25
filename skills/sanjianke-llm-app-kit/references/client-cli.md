# scripts/a7w.py 零依赖客户端 · 用法

`a7w.py` 只用 Python 标准库（`urllib` / `json` / `mimetypes`），**不需要 `pip install` 任何东西**，
也**不内嵌任何密钥**。它既能当库用，也能直接当命令行工具。

## Key 读取顺序

1. `--key sk-xxxx`
2. 环境变量 `A7W_API_KEY`
3. `~/.a7w/config.json`

三种任选一种。到 **[api.a7w.cn](https://api.a7w.cn/)** 注册领 Key（新用户有赠送点数）。

## 子命令一览

| 命令 | 作用 |
|---|---|
| `login --key sk-xxx` | 验证 Key 并保存到 `~/.a7w/config.json` |
| `whoami` | 看这把 Key 能用的插件数 |
| `apps` | 列出全部应用（21 个） |
| `schema <app>` | 看某应用的接口、参数、同步/异步标记 |
| `call <app> <api>` | 调用接口，异步任务自动轮询到结束 |
| `task <task_id>` | 查异步任务 |
| `points` | 看最近的用量 |

全局参数：`--json` 输出原始 JSON。

`call` 的参数：

| 参数 | 说明 |
|---|---|
| `--body '{...}'` | 请求体 JSON |
| `--json '{...}'` | `--body` 的别名（兼容旧写法） |
| `--no-wait` | 只提交，不等结果 |
| `--out 文件` | 把结果 URL 下载到本地 |
| `--key sk-xxx` | 临时指定 Key |

## 常用写法

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"

# 验证并保存
python3 scripts/a7w.py login --key sk-你的key

# 列应用
python3 scripts/a7w.py apps

# 看某应用的完整接口与参数
python3 scripts/a7w.py schema file_qa

# 同步接口：直接拿结果
python3 scripts/a7w.py call file_qa ask \
  --body '{"file_url":"https://你的存储/合同.pdf","question":"付款条件是什么"}'

# 异步接口：只提交，稍后自己查
python3 scripts/a7w.py call voice_tts tts_async --body '{"text":"你好"}' --no-wait
python3 scripts/a7w.py task tsk_xxxxxxxx

# 复杂请求体走文件，避开 shell 引号地狱
python3 scripts/a7w.py call nano_banana generate --body (Get-Content body.json -Raw)
```

> Windows 上 `PowerShell` / `CMD` 会吃掉 JSON 里的双引号。
> 复杂请求体一律写进文件再读，或改用 `--param k=v` 逐个传（如客户端支持）。

## 当库用

```python
import sys
sys.path.insert(0, "scripts")
import a7w

# 纯 JSON 调用，异步自动轮询
res = a7w.call("file_qa", "ask", {"file_url": "https://…", "question": "核心条款是什么"})
print(res["result"])

# 带本地文件的多段上传
res = a7w.upload("voice_tts", "clone_voice", {"name": "我的音色"},
                 file_field="file", file_path="参考音频.mp3")

# 把结果 URL 落盘
a7w.save(res["result"]["audio_url"], "输出.mp3")

# 设 True 可关掉重试提示
a7w.QUIET = True
```

| 函数 | 签名 | 说明 |
|---|---|---|
| `call` | `(app, api, body=None, key=None, wait=True, timeout=1800, quiet=False)` | 纯 JSON 调用；有 `task_id` 时自动轮询 |
| `upload` | `(app, api, fields=None, file_field="file", file_path=None, key=None, wait=True, …)` | 多段上传本地文件 |
| `save` | `(url, path)` | 把结果 URL 下载到本地 |
| `load_key` | `(explicit=None)` | 按三级顺序读 Key |

## 已内置的容错

- **网络类错误退避重试 4 次**：视频与长异步任务的轮询会被网关重置连接，
  不重试的话一次抖动就会让已经预冻结点数的付费任务白丢。5xx 也重试，**4xx 是业务错误不重试**。
- **`401` / `402` 直接给可读提示**：告诉你 Key 无效或点数不足，以及去哪里充值。
- **`code` 判定为 `1` / `200` / 缺省**：原生支持平台的 `{"code":1,"msg":"success"}` 约定。
- **`params_schema` 两种形态都能解析**：带 `properties` 包装的与扁平字典的都认。

## 退出与排错

`call` 失败时抛 `A7wError`，消息里带 HTTP 状态与平台 `msg`，便于直接定位。
轮询超时不会丢任务：消息里会给出 `task_id`，用 `python3 scripts/a7w.py task <task_id>` 继续查。

> 想加自己的批量流程（并发提交、断点续跑、结果自动归档），加文末微信聊，给你配套示例。
