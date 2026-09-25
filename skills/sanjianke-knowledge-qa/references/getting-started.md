# 快速开始 · 注册、领 Key、配置到本机

## 1. 注册并领取 API Key

1. 打开 **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册账号（新用户有**赠送点数**，可以先免费试跑几条）。
2. 进**用户中心 → API 密钥**，创建一个 Key，形如 `sk-...`。
3. 每个 Key 可以单独设**消费上限（quota）**，也可以配 IP 白名单。**Key 等同于余额**，
   不要写进代码、不要提交进 Git。

## 2. 配到本机（三种任选）

```bash
# 方式一：环境变量（临时，当前终端有效）
export A7W_API_KEY=sk-你的key          # Windows PowerShell: $env:A7W_API_KEY="sk-你的key"

# 方式二：让客户端帮你存（推荐，写进 ~/.a7w/config.json，权限 600）
python3 scripts/a7w.py login --key sk-你的key

# 方式三：命令行临时指定
python3 scripts/a7w.py call file_qa ask --key sk-你的key --body '{...}'
```

Key 读取顺序是 **`--key` → `A7W_API_KEY` → `~/.a7w/config.json`**。

## 3. 验证通了没

```bash
# 只看这把 Key 能不能用
python3 scripts/a7w.py whoami

# 最直接的验签方式：让模型回一句话
curl -sS "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

看到 `choices[0].message.content` 有内容就通了。

## 4. 看有什么能用

```bash
# 21 个生成应用
python3 scripts/a7w.py apps

# 75 个在架模型 / 23 家厂商
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"

# 某个应用有哪些接口、参数、真实价
python3 scripts/a7w.py schema voice_tts
```

## 5. 接到自己项目里

```
Base URL: https://api.a7w.cn/api/v1
Authorization: Bearer <你的 API Key>
```

任何支持「OpenAI 兼容 / 自定义 OpenAI 端点」的框架、SDK、低代码平台，
把这两行填进去就能用。详细对照见 `a7w-接入指南.md` 与 `框架接入对照.md`。

## 6. 跑通第一条真实调用

```bash
# 文档问答（同步接口，直接拿结果）
python3 scripts/a7w.py call file_qa ask \
  --body '{"file_url":"https://你的存储/说明.pdf","question":"这份文档讲了什么"}'

# 文字转语音（异步接口，客户端自动轮询到结束）
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好，这是第一段测试"}' --out 试听.mp3
```

## 7. 环境要求

| 项目 | 要求 |
|---|---|
| Python | **3.8+**，只用标准库，**不需要 `pip install` 任何东西** |
| 网络 | 能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名） |
| 密钥 | **你自己**的 API Key；包里不内嵌任何密钥 |
| 素材 | 需要上传的图片 / 音频 / 视频一律用**公网可访问的 URL** |

## 8. 出问题先看这四条

1. **401** → Key 错了或过期，重新 `login`。
2. **402** → 看是 `insufficient_points`（账号没钱）还是 `key_quota_exceeded`（Key 额度满）。
3. **返回 `code: 0`** → 平台失败码是 `0`，成功码是 `1`，别反着判。
4. **某应用怎么调都不通** → 多半是拿了 `endpoint_path` 拼 URL，改用
   `/api/v1/apps/{app}/{code}`。

> 还有别的报错，把请求和返回一并发给文末微信，直接给你定位。
