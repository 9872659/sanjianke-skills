# 三剪客 · AI 聊天客户端接国产大模型 Skill

一个 Key、一个地址，把 75 个在架大模型接进你的 AI 聊天客户端；生成类应用走同一把 Key。

这个 Skill 解决的是**客户端侧的接入问题**：你已经有聊天界面了，但模型只有一家的、或者要挨个填好几家的 Key。
把地址指向 `api.a7w.cn`，**换 `model` 就是换模型**，账单收敛成一份，模型下拉框可以一直加。

---

## 前置条件

- **一个 `api.a7w.cn` 账号**，已完成实名认证并充过点数（体验包 ¥10 = 600 点）。
- **一个 API Key**：用户中心 → API 密钥 → 创建。
- 一个能用的 AI 聊天客户端（网页版 / 桌面版 / 自托管版均可）。
- **Python 3.8+**（只用标准库，无需安装任何第三方包）—— 只有在用包内零依赖客户端时才需要。
- 网络出口能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名）。

---

## 使用

客户端里只要填两个值：

| 客户端字段 | 填什么 |
|---|---|
| API 地址 / Base URL | `https://api.a7w.cn/api/v1` |
| API Host（自带 `/v1` 的客户端） | `https://api.a7w.cn/api` |
| API Key | 你自己的 `sk-...` |
| 模型名称 | 例如 `DeepSeek-V4-Flash`（与线上编码逐字一致） |

先用 `curl` 验证一次，再抄进客户端：

```bash
export A7W_API_KEY=sk-你的key

curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
```

包内零依赖客户端（库 + 命令行）：

```bash
python3 scripts/a7w.py login --key sk-你的key     # 验证并保存 Key
python3 scripts/a7w.py whoami                     # Key 可用性自检
python3 scripts/a7w.py apps                       # 看 21 个生成应用与各自接口
python3 scripts/a7w.py schema voice_tts           # 看某应用的接口名与参数
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好，这是一段试听"}'
```

### 生成类应用：路径口径

真实接口路径一律是 **`/api/v1/apps/<应用代号>/<接口代号>`**，两个代号都来自线上返回的 `code` 字段：

```bash
# 出图（异步，先拿 task_id）
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/nano_banana/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" -H "Content-Type: application/json" \
  -d '{"prompt":"一只在窗台晒太阳的橘猫，胶片质感"}'

# 查任务（免费）
curl -sS "https://api.a7w.cn/api/v1/tasks/<task_id>" -H "Authorization: Bearer $A7W_API_KEY"
```

平台返回的 `endpoint_path` 字段**不要拿来拼 URL**，它不是可调用的路径族。接口代号先用 `schema` 查。

### 按需求找文档

| 你要什么 | 看哪份 |
|---|---|
| 客户端里 base_url / apiHost 到底填到哪一层、模型清单刷不出来 | `references/客户端接入配置.md` |
| OpenAI 协议细节：参数、流式、SDK、推理模型返回空正文 | `references/api-openai-compat.md` |
| 21 个生成应用怎么调、异步任务生命周期、回调与结果转存 | `references/api-apps-tasks.md` |
| 注册、充值、创建 Key、配额与 IP 白名单 | `references/getting-started.md` |
| 权限、错误码、计费口径、排错 | `references/通用说明.md` |

---

## 依赖

- **Python 3.8+**，仅标准库（`urllib` / `json` / `argparse`）。不需要 `requests`，不需要任何第三方包。
- 无后台常驻、无守护进程；每次执行完即退出。
- 只把地址填进现成客户端时，**连 Python 都不需要**。

---

## 安全

- **不内嵌任何密钥**：Key 只从 `~/.a7w/config.json`（权限 600）或环境变量 `A7W_API_KEY` 读取。
- **只连一个域名**：所有请求只发往 `api.a7w.cn`，不发往任何其他地址。
- 填进客户端 `.env` 的 Key 必须先加进 `.gitignore`，别提交进版本库。
- 自托管的聊天界面一旦暴露到公网，等于把你的模型额度开放出去 —— 先配访问控制。
- 生成内容的合规责任由使用者承担。

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