# 三剪客 · 聊天机器人接大模型 Skill

让机器人用国产大模型回话：一个 base_url、一把 api.a7w.cn 的 Key，DeepSeek 等 75 个在架模型随时切换。

这个 Skill 解决的是**机器人侧接模型的问题**：机器人框架负责平台协议与事件分发，大模型侧统一走
`api.a7w.cn` 的 OpenAI 兼容入口。一个 Key、一份账单，换 `model` 就是换模型。

---

## 前置条件

- **一个 `api.a7w.cn` 账号**，已完成实名认证并充过点数（体验包 ¥10 = 600 点）。
- **一个 API Key**：用户中心 → API 密钥 → 创建。
- 一个能正常收发消息的机器人（框架与平台自选）。
- **Python 3.8+**（只用标准库，无需安装任何第三方包）—— 只有在用包内零依赖客户端时才需要。
- 网络出口能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名）。

---

## 使用

先确认模型侧通，再接进机器人：

```bash
export A7W_API_KEY=sk-你的key

curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
```

机器人侧只要一步：取到消息文本 → 调上面这个接口 → 把 `choices[0].message.content` 发回去。
推荐用标准库 `urllib`，不引入额外依赖：

```python
import json, os, urllib.request

def ask(prompt, model="DeepSeek-V4-Flash", timeout=25):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
    }).encode()
    req = urllib.request.Request(
        "https://api.a7w.cn/api/v1/chat/completions", data=body,
        headers={"Authorization": "Bearer " + os.environ["A7W_API_KEY"],
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]
```

包内零依赖客户端（库 + 命令行）：

```bash
python3 scripts/a7w.py login --key sk-你的key     # 验证并保存 Key
python3 scripts/a7w.py whoami                     # Key 可用性自检
python3 scripts/a7w.py apps                       # 看 21 个生成应用与各自接口
python3 scripts/a7w.py schema voice_tts           # 看某应用的接口名与参数
python3 scripts/a7w.py call voice_tts tts --body '{"text":"群里好，我是机器人"}'
```

### 按需求找文档

| 你要什么 | 看哪份 |
|---|---|
| 机器人接大模型的三种接法、多轮上下文、并发与去重、降级、发图发语音 | `references/bot-llm-integration.md` |
| 鉴权、两条入口、计费口径、错误码、权限边界 | `references/通用说明.md` |

---

## 依赖

- **Python 3.8+**，仅标准库（`urllib` / `json` / `argparse`）。不需要 `requests`，不需要任何第三方包。
- 无后台常驻；`a7w.py` 每次执行完即退出。
- 机器人进程本身按你选用的框架自行部署与守护。

---

## 安全

- **不内嵌任何密钥**：Key 只从 `~/.a7w/config.json`（权限 600）或环境变量 `A7W_API_KEY` 读取。
- **只连一个域名**：所有请求只发往 `api.a7w.cn`，不发往任何其他地址。
- 机器人框架的平台 Token / AppID / AppSecret 建议用环境变量注入，不要写进会提交的配置文件。
- 给每个群一份独立 Key 并设消费上限（quota），某个群刷爆也不会拖垮整个账号。
- 机器人在群里说的话由部署方负责，请自行加敏感词与内容合规自检。

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

---

## 许可证

MIT，见 `LICENSE.md`。

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |