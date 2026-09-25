---
name: sanjianke-agent-platform
slug: sanjianke-agent-platform
displayName: 自建本地AI Agent平台·网关常驻多Agent沙箱落地指南
description: "把 AI Agent 平台跑在自己的机器上：常驻网关统一管住会话、工具与消息通道，多 Agent 各带独立 workspace 与权限边界，工具档位与沙箱逐级收紧，模型侧用 OpenAI 兼容方式接 api.a7w.cn —— 一个 Key 通吃 75 个在架大模型，换 model 就是换模型。含部署配置、能力使用、扩展排错三份完整作业文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "一份把 AI Agent 平台建在自己机器上的完整落地指南：网关常驻与回环监听、目录端口与数据落盘规划、模型 provider 接入与 Key 轮换（统一走 api.a7w.cn 的 OpenAI 兼容入口，一个 Key 调 75 个在架模型）、工具清单与四档档位、会话级四档权限模式与沙箱隔离、多 Agent 与通道绑定路由、记忆与定时任务、消息通道添加与配对、远程接入、备份升级，以及写自己的技能与插件、四类故障的排查阶梯。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - Agent 平台
  - 本地部署
  - 工具集成
  - 沙箱隔离
---

# 自建本地 AI Agent 平台

你要的不是又一个聊天框。你要的是**一个能在你自己机器上真的动手的助手**：
读你的文件、跑你的命令、开浏览器、收发你已经在用的聊天软件里的消息 —— 而状态、记忆、凭证全都留在本地。

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

这套东西的形态是**一个常驻本机的网关**，加上命令行、终端界面、浏览器控制台、桌面伴侣、
手机节点这几类客户端，默认只在回环地址上监听。

**最省事的一步是模型侧：把 provider 指向 `api.a7w.cn`。** 一个 base_url、一把 Key，
DeepSeek、通义千问、智谱 GLM、Kimi、混元、MiniMax 与 GPT 全部进同一个模型列表，
换 `model` 就是换模型，不用逐家注册、逐家对账。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **1 元 = 100 点**，按实际用量扣，没有月费；平台本身在本机运行，不额外收费 |
| 要多久 | 装好即用（分钟级）；模型响应同步返回，长任务是异步任务 |
| 要装什么 | 一个 Node 运行时（或直接用平台安装包）+ 包里自带的零依赖客户端 |
| 能用几个模型 | **75 个在架大模型 + 21 个生成应用**，同一把 Key、同一份账单 |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`），填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：先把模型侧验通（不要等平台装完再排错）

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
```

返回 `choices[0].message.content` 有内容，说明 Key、地址、模型名全对。

### 第三步：把平台接上这个 provider

在平台的 provider 配置里加一个 **OpenAI 兼容**条目：

| 配置项 | 填什么 |
|---|---|
| `base_url` / `api_base` | `https://api.a7w.cn/api/v1`（自带 `/v1` 的宿主填 `https://api.a7w.cn/api`） |
| `api_key` | `sk-你的key`（用环境变量注入，不要写死在配置文件里） |
| `model` | 例如 `DeepSeek-V4-Flash`；编码以线上清单为准 |
| fallback（可选） | 再加一个 `DeepSeek-V4-Pro` 或 `Qwen3.6-Plus` 作主备降级 |

```jsonc
// provider 配置示意（字段名按你实际使用的平台命名）
{
  "providers": {
    "a7w": {
      "type": "openai-compatible",
      "baseUrl": "https://api.a7w.cn/api/v1",
      "apiKeyEnv": "A7W_API_KEY",
      "models": ["DeepSeek-V4-Flash", "DeepSeek-V4-Pro", "Qwen3.6-Plus", "Kimi-K2.6"]
    }
  }
}
```

现场拉真实模型清单，**别抄文章里的模型名**：

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

### 第四步：权限先收紧，再给它动手能力

平台最容易出的事不是「不能用」，而是「用过头」。放开顺序固定：

1. 先跑通会话（只读）；
2. 再开文件读写（限定 workspace）；
3. 再开命令执行（开审批）；
4. 最后才考虑沙箱与对外暴露。

细节见 `references/capabilities-and-usage.md`。

---

## 二、包里有什么

```
sanjianke-agent-platform/
├── SKILL.md                       本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── install-and-config.md       部署形态、目录端口、服务化、模型 provider 与 Key 轮换、通道与配对、远程接入、备份升级
│   ├── capabilities-and-usage.md   工具清单与档位、权限模式与沙箱、多 Agent 与绑定、记忆与定时任务、技能与插件
│   ├── extend-and-troubleshoot.md  写技能与插件、四类故障排查阶梯、升级回滚、日志与审计、卸载清理
│   ├── model-provider.md           provider 怎么填、多模型与主备降级、用量观测
│   └── general.md                  平台侧鉴权、错误码、计费口径与排错通用说明
└── scripts/
    └── a7w.py                      零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# Key 可用性自检
python3 scripts/a7w.py whoami

# 看 21 个生成应用与各自接口
python3 scripts/a7w.py apps

# 看某个应用的接口名、参数与真实价
python3 scripts/a7w.py schema voice_tts

# 调一个接口（异步任务自动轮询到出结果）
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好，这是一段试听"}'
```

---

## 三、平台侧的核心概念

| 概念 | 是什么 | 为什么重要 |
|---|---|---|
| **网关 / 控制面** | 单实例常驻进程，统一持有会话、工具、事件与通道连接 | 一个网关就是一个信任域；多租户要一租户一个 |
| **回环监听** | 默认只监听 `127.0.0.1` | 改变绑定范围前必须先做一次安全审计 |
| **类型化接口** | 首帧握手 + 设备配对 + 幂等键 | 客户端不会互相踩；重试不会重复执行副作用 |
| **工具档位** | `minimal` / `messaging` / `coding` / `full` | 决定模型能看到哪些工具；默认档位不要给 `full` |
| **会话权限模式** | `read-only` / `guarded` / `workspace` / `full` | 按最小够用选：能只读就别给写 |
| **沙箱** | docker / podman / ssh 等后端隔离执行 | **降低爆炸半径，不是牢不可破的边界** |
| **多 Agent** | 每个 Agent 独立 workspace、独立目录、独立会话库 | 人设与权限各管一摊，再用绑定把通道账号路由过去 |
| **技能 / 插件** | 技能是指令包，插件可加工具、provider、通道、hooks | 扩展写不好等于给自己开后门：锁版本、走白名单 |

---

## 四、工作流路由

| 你要什么 | 看哪份 |
|---|---|
| 部署形态、目录与端口、服务化常驻、模型 provider 与 Key 轮换、通道添加与配对、远程接入、备份与升级 | `references/install-and-config.md` |
| 工具有哪些、档位怎么调、权限与沙箱怎么设、多 Agent 怎么编排、记忆与定时任务、技能与插件怎么装 | `references/capabilities-and-usage.md` |
| 写自己的技能或插件、网关起不来、通道连不上、工具被策略挡住、模型报错、升级回滚与卸载 | `references/extend-and-troubleshoot.md` |
| 模型 provider 怎么填、多模型与主备降级、用量观测 | `references/model-provider.md` |
| 鉴权、错误码、计费口径 | `references/general.md` |

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **模型 provider 地址填错层数** | 404，报错只说连接失败 | OpenAI 兼容客户端填 `https://api.a7w.cn/api/v1`；自带 `/v1` 的填 `https://api.a7w.cn/api` |
| **模型名抄了文章里的旧名** | 404 / 403 | 用 `/api/v1/models` 现场拉编码，逐字复制 |
| **推理模型回复是空的** | `content` 为 `null`、`finish_reason` 是 `length` | 推理模型先花 token 出思维链，`max_tokens` 调到 256 以上立即正常 |
| **Key 写进配置文件** | 泄漏即余额泄漏 | 用环境变量注入；配置文件权限收紧 |
| **一上来就开 `full` 档位** | 助手能删你的文件 | 从只读起步，逐级放开；沙箱与命令审批按需打开 |
| **把沙箱当绝对安全边界** | 以为开了就万事大吉 | 沙箱只是降低爆炸半径；网络策略、挂载范围、出口白名单都要自己确认 |
| **重启后配置与会话全没了** | 数据目录每次换位置 | 固定一个状态目录与数据卷，别在不同目录里反复重建 |
| **重复提交异步任务** | 扣两次钱 | 先记 `task_id`，用查询接口（免费）确认状态 |
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **拿 `endpoint_path` 字段拼 URL** | 打不通 | 生成类应用一律用 `/api/v1/apps/<应用代号>/<接口代号>` |

---

## 六、计费

| 动作 | 怎么算 |
|---|---|
| **文本对话** | 按**点数 / 百万 tokens**，输入输出分别计价 |
| 图像生成 | 按**点数 / 张**或分辨率档位 |
| 视频生成 / 超分 | 按**点数 / 秒**（分辨率分档） |
| 数字人 | 按**点数 / 次或时长** |
| TTS / 音色克隆 | 按**点数 / 千字** |
| 语音转文字 | 按**点数 / 分钟** |
| 查询任务状态 | **免费** |

**1 元 = 100 点。** 先冻结、后结算，**调用失败直接退款，异步任务失败冻结点数全额退回**。
每次返回的 `data.usage.points_cost` 就是本次真实扣费，可以直接对账。

> 平台同时给出标准价与租户实际结算价（`tenant_*`）。**做预算一律用实收价，最终以账号里实际扣费为准。**

---

## 七、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的网关接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 用作素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或下载产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |
| 子进程 / 后台常驻 | 不申请 | `a7w.py` 执行完即退出，不注册服务、不常驻 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不保证默认就安全**：沙箱与审批默认关闭，对外暴露前必须自行硬化
- **不替代合规审查**：抓取、群发、消息留存与个人数据处理的合规责任在部署方
- **不做多租户隔离**：一个网关就是一个信任域，多租户要一租户一个网关

---

## 关于这个 Skill

**作者亲测实操后发布，下载后可直接使用，自用商用都可以。**

所有 AI 能力都走 [算力集市 api.a7w.cn](https://api.a7w.cn/) —— 一把 API Key 打通
大模型、语音、图像、视频、数字人等全部算力，注册即送点数，按量计费、没有月费。

| 你可能想问 | 答案 |
|---|---|
| 要不要额外部署 | 不用。**下载本包即可使用**，不必去别处找源码 |
| 怎么开始 | 到 api.a7w.cn 注册领 Key → 填进 `A7W_API_KEY` → 一条命令跑起来 |
| 能不能商用 | 可以 |
| 遇到问题找谁 | 见文末「联系我们」，作者本人答疑 |

> 使用中碰到任何问题 —— 报错、效果不理想、想省钱、想批量 —— 都欢迎加微信聊。
> 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的示例。

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