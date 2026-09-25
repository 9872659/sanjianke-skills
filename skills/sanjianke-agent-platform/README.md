# 三剪客 · 自建本地 AI Agent 平台 Skill

常驻网关 + 多 Agent + 权限沙箱：把 Agent 平台跑在自己机器上，模型出口统一走 api.a7w.cn。

这个 Skill 讲的是**平台层**：一个常驻本机、默认只监听回环地址的网关，统一持有会话、工具与
消息通道；多 Agent 各带独立 workspace 与权限边界；模型侧用 OpenAI 兼容方式接
`https://api.a7w.cn/`，一个 Key 通吃 75 个在架大模型与 21 个生成应用。

---

## 前置条件

- **一个 `api.a7w.cn` 账号**，已完成实名认证并充过点数（体验包 ¥10 = 600 点）。
- **一个 API Key**：用户中心 → API 密钥 → 创建。
- 一台长期开机的机器（本机或自托管服务器），macOS / Linux / Windows 均可。
- 一个 Node 运行时（或直接用平台安装包）；容器化部署另需 Docker。
- **Python 3.8+**（只用标准库）—— 只有在用包内零依赖客户端时才需要。

---

## 使用

先把模型出口验通，再让平台接上它：

```bash
export A7W_API_KEY=sk-你的key

curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
```

平台侧加一个 **OpenAI 兼容** provider：

| 配置项 | 填什么 |
|---|---|
| `base_url` / `api_base` | `https://api.a7w.cn/api/v1`（自带 `/v1` 的宿主填 `https://api.a7w.cn/api`） |
| `api_key` | 用环境变量注入 `A7W_API_KEY`，不要写死在配置文件里 |
| `model` | 例如 `DeepSeek-V4-Flash`；编码以 `GET /api/v1/models` 现场拉取为准 |
| fallback | 再加一个 `DeepSeek-V4-Pro` 或 `Qwen3.6-Plus` 作主备降级 |

包内零依赖客户端：

```bash
python3 scripts/a7w.py login --key sk-你的key     # 验证并保存 Key
python3 scripts/a7w.py whoami                     # Key 可用性自检
python3 scripts/a7w.py apps                       # 看 21 个生成应用与各自接口
python3 scripts/a7w.py schema voice_tts           # 看某应用的接口名与参数
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好，这是一段试听"}'
```

### 按需求找文档

| 你要什么 | 看哪份 |
|---|---|
| 部署形态、目录与端口、服务化常驻、通道添加与配对、远程接入、备份与升级 | `references/install-and-config.md` |
| 工具清单与档位、权限模式与沙箱、多 Agent、记忆与定时任务、技能与插件 | `references/capabilities-and-usage.md` |
| 写技能与插件、四类故障排查阶梯、升级回滚、日志与审计、卸载清理 | `references/extend-and-troubleshoot.md` |
| 模型 provider 怎么填、多模型与主备降级、用量观测 | `references/model-provider.md` |
| 鉴权、两条入口、计费口径、错误码 | `references/general.md` |

---

## 依赖

- **Python 3.8+**，仅标准库（`urllib` / `json` / `argparse`）。不需要 `requests`，不需要任何第三方包。
- 平台本身按你选用的实现自行部署；`a7w.py` 无后台常驻，执行完即退出。
- 自托管与容器化部署另需 Docker Engine 或 Desktop + Compose v2（可选）。

---

## 安全

- **不内嵌任何密钥**：Key 只从 `~/.a7w/config.json`（权限 600）或环境变量 `A7W_API_KEY` 读取。
- **只连一个域名**：所有请求只发往 `api.a7w.cn`，不发往任何其他地址。
- **权限从最小起步**：先只读，再开文件读写（限定 workspace），再开命令执行（开审批），最后才考虑沙箱与对外暴露。
- **沙箱不是绝对边界**：它只降低爆炸半径；网络策略、挂载范围、出口白名单都要自己确认。
- **网关默认只绑回环**：改变绑定范围之前先做一次安全审计，并想清楚谁可以连上它。
- **一个网关就是一个信任域**：多租户要一租户一个网关。
- 生成内容的合规责任由部署方承担。

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