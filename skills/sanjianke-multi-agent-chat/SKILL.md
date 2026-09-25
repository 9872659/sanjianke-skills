---
name: sanjianke-multi-agent-chat
slug: sanjianke-multi-agent-chat
displayName: 多智能体群聊协作·多角色轮流发言与终止条件接入指南
description: "用对话的方式组织多个 Agent 协作：给每个 Agent 一个名字、一段人设、一个模型客户端，再放进群聊里轮流发言或按需发言，靠终止条件收口。含发言策略与终止条件参数表、状态管理写法、工具轮数上限与零依赖客户端。模型侧改一个 base_url 走 OpenAI 兼容网关即可，一把 Key 调 75 个在架模型。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "一个 Agent 干不好的活，往往适合拆给几个角色来回讨论：写手出稿、评审挑刺、写手改稿，直到评审说通过。本包讲怎么把这种多角色群聊的模型入口统一指向一个 OpenAI 兼容网关 —— 只改一个 base_url，同一把 Key 调 75 个在架模型（DeepSeek、通义千问、智谱 GLM、Kimi、腾讯混元等国产为主），并且能给每个发言角色分别指定模型：出稿用快的、评审用强的，账单还是同一份。含发言策略选择、终止条件设计、状态与重置、工具调用轮数上限与真实计费口径。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 多智能体
  - 群聊协作
  - OpenAI兼容
---

# 多智能体群聊协作 · 轮流发言与终止条件

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

一个 Agent 干不好的活，往往不是模型不够强，而是任务本身适合**拆给几个角色来回讨论**：
写手出稿、评审挑刺、写手改稿，直到评审说「通过」。

这类框架把这种**「多角色对话」当成一等公民**：你定义几个带人设的 Agent，
配一个模型客户端，塞进一个「团队」里，它负责轮流发言、共享上下文、判断何时停下。

**而它背后要的模型调用，换成 api.a7w.cn 的 OpenAI 兼容入口，就是一个 base_url 的事**——
你还能给每个角色分别指定模型，**账单还是同一份**。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **按 tokens 计费**（点数/百万 tokens，输入输出分别计价），1 元 = 100 点；多角色多轮消耗高于单次问答 |
| 要多久 | 每条发言就是一次模型调用，耗时按发言轮数线性增长 |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端，或者直接用 `curl` / 任意 OpenAI SDK |
| 模型从哪来 | **一个 base_url + 一个 Key**，可调 75 个在架模型，**每个角色可单独指定** |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`），填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：先用一条 curl 确认网关通

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

成功返回体形如 `{"code":1,"msg":"success","data":{...choices...}}`。

### 第三步：把 Agent 的模型客户端指向它

任何兼容 OpenAI 协议的框架 / SDK，只改两个字段：

```python
BASE_URL = "https://api.a7w.cn/api/v1"
API_KEY  = "sk-你的key"
```

框架里的模型客户端通常长这样（示意）：

```python
# 只换 base_url 与 api_key，其余调用方式不变
model_client = OpenAIChatCompletionClient(
    model="DeepSeek-V4-Flash",
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",
)
```

**然后按角色分配模型**：

| 角色 | 建议模型档位 | 例子 |
|---|---|---|
| 出稿 / 执行 | 快模型（便宜） | `DeepSeek-V4-Flash`、`Qwen3.6-Flash` |
| 讨论 / 分析 | 中档模型 | `Qwen3.7-Plus`、`GLM-5` |
| 评审 / 定稿 | 强模型 | `DeepSeek-V4-Pro`、`GLM-5.2`、`Kimi-K2.6` |

### 第四步：零安装客户端也能直接跑

```bash
python3 scripts/a7w.py whoami                       # 验证 Key
python3 scripts/a7w.py call chat completions \
  --body '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

> 换模型只需改 `model` 字符串：**不用换 base_url、不用换 Key、账单还是同一份**。

---

## 二、包里有什么

```
sanjianke-multi-agent-chat/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 群聊协作指南.md          发言策略、终止条件、状态管理、成本估算
│   ├── api-openai-compat.md    OpenAI 兼容入口：base_url、鉴权、参数、流式、错误码
│   ├── api-apps-tasks.md       应用任务入口：/api/v1/apps/<应用>/<接口> 与异步生命周期
│   ├── getting-started.md      注册、领 Key、配置、配额与白名单
│   └── 通用说明.md              权限、计费口径、排错
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

python3 scripts/a7w.py whoami                     # 验证 Key 与可用能力数
python3 scripts/a7w.py apps                       # 列出全部能力
python3 scripts/a7w.py call chat completions \
  --body '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

---

## 三、三种接入姿势

### 姿势 A：框架的配置（最省事）

把模型客户端的 `base_url` 与 `api_key` 换成网关即可：

```python
model_client = OpenAIChatCompletionClient(
    model="DeepSeek-V4-Flash",
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",
)
```

> 类名与参数名以你所用框架的当前版本为准（有些框架写作 `base_url`，
> 有些写作 `base_url` + `api_key` 传进一个字典）。**值永远是同一个网关地址与同一把 Key。**

### 姿势 B：纯 Python，自己写群聊循环

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key=os.environ["A7W_API_KEY"],
)

AGENTS = [
    {"name": "写手", "model": "DeepSeek-V4-Flash",
     "system": "你负责出稿。先给一版完整的内容。"},
    {"name": "评审", "model": "DeepSeek-V4-Pro",
     "system": "你负责挑毛病。认可时在回复里写出 APPROVE。"},
]

def group_chat(task: str, max_rounds: int = 6, stop_word: str = "APPROVE") -> str:
    """轮流发言 + 双重终止条件（关键词 + 步数上限）。"""
    history = [{"role": "user", "content": task}]
    for i in range(max_rounds):
        agent = AGENTS[i % len(AGENTS)]                 # 轮流
        resp = client.chat.completions.create(
            model=agent["model"],
            messages=[{"role": "system", "content": agent["system"]}] + history,
        )
        content = resp.choices[0].message.content
        history.append({"role": "assistant", "content": "[%s] %s" % (agent["name"], content)})
        if stop_word in content:                        # 关键词终止
            return content
    return history[-1]["content"]                       # 步数上限兜底
```

**两件事必须做对**：

1. **双重终止条件** —— 关键词负责正常收口，步数上限负责异常兜底。
   只设关键词，一旦触发词写错就是无限循环。
2. **角色系统提示里写死触发词** —— 评审角色不知道要输出 `APPROVE`，
   终止条件永远不会触发。

### 姿势 C：走应用任务入口

除了 OpenAI 兼容的大模型网关，平台还有一条应用任务入口，用于生成类能力
（语音、图像、视频、文档问答等 21 个应用）：

```bash
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好世界"}'
```

**路径统一是 `/api/v1/apps/<应用代号>/<接口代号>`**，两个代号都取自接口返回的
`code` 字段（是下划线，不是连字符）。不要拿平台返回的 `endpoint_path` 去拼 URL。

---

## 四、群聊协作要点

### 发言策略怎么选

| 策略 | 什么时候用 | 代价 |
|---|---|---|
| **固定顺序轮流** | 角色少、流程确定（写 → 审 → 改） | 便宜、可预测；但顺序不灵活 |
| **模型动态点名** | 角色多、该谁说话要看内容 | 每次多一次「点名」调用，更贵 |
| **交接式** | 像「转专员」那样把活交给下一个角色 | 适合有明确升级路径的流程 |

**从固定顺序起步**：确定、便宜、好排查。等流程稳定了再上动态点名。

### 工具调用的轮数上限

Agent 挂工具后，**一定要设调用轮数上限**（常见参数名 `max_tool_iterations` 一类）。
不设的话，Agent 走完一轮工具调用就停，很容易「以为它做完了其实没做完」。

```python
# 示意：给要多次调工具的 Agent 设轮数上限
agent = {"name": "执行", "model": "DeepSeek-V4-Flash",
         "system": "...", "max_tool_iterations": 10}
```

### 状态与重置

多角色会话**是有状态的**：跑完一次直接再跑，就是**接着上次的上下文继续**。

- 下一个任务和上一个**不相关** → 先重置，再跑。
- 下一个任务是上一个的**延续** → 直接续跑，让它带着上下文。

**判断口径**：第二个任务需不需要第一个任务的产出？不需要就重置。

### 成本估算

```
单次任务调用数 ≈ 角色数 × 平均轮数（动态点名策略还要 + 轮数）
单次任务成本   ≈ 调用数 × 单次调用 tokens × 对应模型的单价
```

**例**：2 个角色、评审循环 3 轮 ≈ 6 次调用。

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **把 Key 写进代码** | 泄漏即等于余额泄漏 | Key 只从环境变量或 `~/.a7w/config.json` 读 |
| **没设终止条件** | 角色一直聊下去，账单失控 | 关键词触发 + 步数上限，两类都设 |
| **评审角色没被告知触发词** | 终止条件永远不触发 | 把触发词（如 `APPROVE`）写进评审的角色设定 |
| **工具调用只走一轮就停** | 「以为做完了其实没做完」 | 设工具调用轮数上限 |
| **所有角色都用一个强模型** | 成本翻几倍，效果提升有限 | 按环节分档：出稿用快模型、评审用强模型 |
| **不相关任务直接续跑** | 第二个任务结果被上一个上下文带偏 | 不相关先重置会话；相关才续跑 |
| **顶层 `await` 写在脚本里** | 报语法错误 | 包进 `async def main()` 再启动 |
| **忘记关闭模型客户端** | 程序不退出、提示连接未关闭 | 结束时显式关闭客户端，或用上下文管理器 |
| **挂了来源不明的外部工具** | 本机行为不可控 | 只连可信来源的工具，能限权就限权 |
| **`model` 名靠猜** | 报 404 模型不存在 | 调用前读一次模型清单，取值以接口返回为准 |

---

## 六、计费

| 动作 | 口径 |
|---|---|
| 角色的一条发言 | 按 **tokens** 计，输入与输出分别计价 |
| 动态点名 | 每次点名也是一次模型调用 |
| 换角色模型 | 换 `model` 即换单价；账单仍是同一份 |
| 应用任务类接口 | 按各接口口径（点数/次、点数/分钟、点数/张等） |

- **1 元 = 100 点，1 点 = ¥0.01。**
- **先冻结、后结算**：调用失败直接退款，异步任务失败冻结点数全额退回。
- 平台同时给出标准价与租户实际结算价，**以账号里实际扣费为准**；
  每次返回的 `data.usage` 就是本次真实用量，可直接对账。
- 实时查规则：先 `python3 scripts/a7w.py apps` 拿应用清单，再逐个 `schema <app>` 读 `tenant_*`。

> **省钱三件事**：按环节分档选模型；把终止条件设对（少转两轮最省钱）；
> 用固定顺序起步（动态点名每次都多一次调用）。

---

## 七、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的模型网关与应用接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件与 `--json-file` 请求体 | 作为接口入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |
| 子进程 / 后台常驻 | 不申请 | 脚本执行完即退出，不注册服务、不常驻 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代内容合规审查**：生成内容的使用与合规责任由使用者承担
- **不承诺模型清单**：模型上下架频繁，**调用前先读一次模型清单**

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
