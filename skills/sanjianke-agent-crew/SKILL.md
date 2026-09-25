---
name: sanjianke-agent-crew
slug: sanjianke-agent-crew
displayName: 多角色Agent协作编排·角色分工与流程控制接入指南
description: "把一段活儿拆成几个有岗位、有目标、有背景故事的角色，让它们按顺序或按层级协作完成多步骤任务；需要精确控制时再用事件驱动流程把角色串起来。含角色建模与流程参数表、数据流声明写法与零依赖客户端。模型侧改一个 base_url 走 OpenAI 兼容网关即可，一把 Key 调 75 个在架模型、每个角色可分别指定。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "多角色协作最难的不是调模型，而是描述分工：给每个角色一个岗位、一个目标、一段背景故事，再把任务派下去，让它们按顺序或按层级把一段多步骤工作干完。本包讲怎么把角色的模型入口统一指向一个 OpenAI 兼容网关 —— 只改一个 base_url，同一把 Key 调 75 个在架模型（DeepSeek、通义千问、智谱 GLM、Kimi、腾讯混元等国产为主），并且能给每个角色单独指定模型：调研用快的、评审用强的，账单还是同一份。含角色建模、任务依赖与产出落盘、流程选择与真实计费口径。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 多智能体
  - 角色编排
  - OpenAI兼容
---

# 多角色 Agent 协作编排 · 角色分工与流程控制

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

多角色协作最难的不是「怎么调模型」，而是**「怎么描述分工」**。

答案是用招聘的思路描述角色：给它一个 `role`（岗位）、一个 `goal`（目标）、
一段 `backstory`（背景故事），再把任务派给它。角色写得像人，模型的表现就更像那个岗位的人。

**而它背后要的模型调用，换成 api.a7w.cn 的 OpenAI 兼容入口，就是一个 base_url 的事**——
并且你能给每个角色分别指定模型：调研用快模型、评审用强模型，**账单还是同一份**。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **按 tokens 计费**（点数/百万 tokens，输入输出分别计价），1 元 = 100 点；多角色多轮消耗高于单次问答 |
| 要多久 | 每个角色一轮就是一次模型调用，任务耗时按调用轮数线性增长 |
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

### 第三步：把角色的模型入口指向它

任何兼容 OpenAI 协议的框架 / SDK，只改两个字段：

```python
BASE_URL = "https://api.a7w.cn/api/v1"
API_KEY  = "sk-你的key"
```

**然后按角色分配模型** —— 这是本包最值钱的一步：

| 角色 | 建议模型档位 | 例子 |
|---|---|---|
| 调研 / 检索 / 摘要 | 快模型（便宜） | `DeepSeek-V4-Flash`、`Qwen3.6-Flash` |
| 撰写 / 分析 | 中档模型 | `Qwen3.7-Plus`、`GLM-5`、`MiniMax-M3` |
| 评审 / 定稿 / 复杂推理 | 强模型 | `DeepSeek-V4-Pro`、`GLM-5.2`、`Kimi-K2.6` |
| 看图的角色 | 视觉模型 | `Qwen3-VL-30B-A3B-Instruct`、`ERNIE-4.5-Turbo-VL` |

```python
# 一个角色一个模型，账单还是同一份
researcher = {"role": "调研员", "model": "DeepSeek-V4-Flash"}
analyst    = {"role": "分析师", "model": "Qwen3.7-Plus"}
reviewer   = {"role": "评审",  "model": "DeepSeek-V4-Pro"}
```

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
sanjianke-agent-crew/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 角色编排指南.md          角色建模、任务依赖、流程选择与成本估算
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

### 姿势 A：框架的配置文件（最省事）

多角色框架通常有一处集中声明「模型入口」，把 `base_url` 与 `api_key` 改成网关即可：

```bash
# .env（几乎所有框架都认这个文件）
OPENAI_API_KEY=sk-你的key
OPENAI_BASE_URL=https://api.a7w.cn/api/v1
```

> **键名以你所用框架的当前版本为准**（常见写法还有 `OPENAI_API_BASE`、
> `LLM_BASE_URL` 等）。**值永远是同一个网关地址与同一把 Key。**

### 姿势 B：纯 Python，自己管角色与调用

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key=os.environ["A7W_API_KEY"],
)

ROLES = [
    {"name": "调研员", "model": "DeepSeek-V4-Flash",
     "system": "你负责找事实、列要点，只输出事实清单，不做判断。"},
    {"name": "分析师", "model": "Qwen3.7-Plus",
     "system": "你基于上一位的事实清单做分析，输出结论与依据。"},
    {"name": "评审", "model": "DeepSeek-V4-Pro",
     "system": "你负责挑毛病。认可时在回复里写出 APPROVE。"},
]

def run_crew(task: str) -> str:
    """顺序执行：每个角色读到前面所有角色的产出。"""
    transcript = []
    for role in ROLES:
        context = "\n\n".join(
            "【%s】\n%s" % (t["name"], t["content"]) for t in transcript
        )
        resp = client.chat.completions.create(
            model=role["model"],
            messages=[
                {"role": "system", "content": role["system"]},
                {"role": "user",
                 "content": "任务：%s\n\n已有产出：\n%s" % (task, context)},
            ],
        )
        content = resp.choices[0].message.content
        transcript.append({"name": role["name"], "content": content})
        if "APPROVE" in content:
            break                      # 终止条件：评审说了 APPROVE
    return transcript[-1]["content"]
```

**两个必须设的东西**：

1. **终止条件** —— 没有它就停不下来，会一直烧 token。让评审角色在系统提示里
   明确写出触发词（如 `APPROVE`），代码里匹配它。
2. **数据流** —— 谁读谁的产出要显式声明（上面的 `transcript`），
   不要让模型「自己想起来」。

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

## 四、角色编排要点

### 角色建模：三件套写具体

| 字段 | 写什么 | 反例 → 正例 |
|---|---|---|
| `role` | 岗位名 | 「助手」→「资深数据分析师」 |
| `goal` | 这一步要产出什么 | 「帮忙分析」→「找出 3 个可落地的增长点，各附数据依据」 |
| `backstory` | 这个岗位的人怎么想事 | 「你很聪明」→「你在消费品牌做了 8 年，习惯先看复购再看拉新」 |

**审核类角色还要把「什么算通过」写进 `backstory` 或系统提示**，
否则终止条件永远触发不了。

### 分层：自主与确定的边界

| 环节性质 | 交给谁 |
|---|---|
| 需要判断、需要写、需要评价 | 角色（自主协作） |
| 审批、分支、状态管理、失败重试 | 确定性流程（事件驱动编排） |

**能上生产的用法基本都是「确定性流程里嵌角色协作」**：
该自由的地方给模型，该确定的地方用代码。

### 任务依赖与产出落盘

- 任务之间的数据流用显式依赖声明（谁读谁的产出），别靠模型自己接。
- 需要给下游程序消费的产出，**优先用结构化输出**（JSON / Pydantic 模型），
  或直接把结果写到文件。
- 产出落盘时注意工作目录边界，别把中间产物写进源码目录。

### 成本估算

多角色一轮任务 ≈ **角色数 × 平均轮数 × 单次调用 tokens**。

举例：3 个角色、评审循环 2 轮 = 约 5–6 次调用。
**按 `tenant_*` 实收价算，再乘上你的日任务量**，就能估出日预算。

> 拿到一手单价：`python3 scripts/a7w.py schema <app>` 读 `tenant_*` 字段；
> 模型侧则按 tokens 计价，输入输出分别算。

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **把 Key 写进代码** | 泄漏即等于余额泄漏 | Key 只从环境变量或 `~/.a7w/config.json` 读 |
| **没设终止条件** | 角色一直讨论下去，账单失控 | 设终止条件，并确认它在正常路径下**真的会被触发** |
| **评审角色的系统提示没写触发词** | 终止条件形同虚设 | 把触发词（如 `APPROVE`）写进评审角色的系统提示 |
| **所有角色都用一个强模型** | 成本翻几倍，效果提升有限 | 按环节分档：调研用快模型、评审用强模型 |
| **任务依赖靠模型「自己想起来」** | 产出接不上，下游拿到空上下文 | 依赖与数据流显式声明在代码里 |
| **两轮任务之间上下文串味** | 第二个任务结果怪怪的 | 多角色会话是有状态的；不相关的任务先重置会话 |
| **忘记关详细日志** | 排查期有用，生产期拖慢还费 token | 生产运行关掉 `verbose` 类开关 |
| **`model` 名靠猜** | 报 404 模型不存在 | 调用前读一次模型清单，`model` 取值以接口返回为准 |
| **网络超时后直接重提** | 扣两次钱 | 先记 `task_id` / 请求 id，查状态再决定是否重提 |

---

## 六、计费

| 动作 | 口径 |
|---|---|
| 角色的一轮发言 | 按 **tokens** 计，输入与输出分别计价 |
| 换角色模型 | 换 `model` 即换单价；账单仍是同一份 |
| 应用任务类接口 | 按各接口口径（点数/次、点数/分钟、点数/张等） |

- **1 元 = 100 点，1 点 = ¥0.01。**
- **先冻结、后结算**：调用失败直接退款，异步任务失败冻结点数全额退回。
- 平台同时给出标准价与租户实际结算价，**以账号里实际扣费为准**；
  每次返回的 `data.usage` 就是本次真实用量，可直接对账。
- 实时查规则：先 `python3 scripts/a7w.py apps` 拿应用清单，再逐个 `schema <app>` 读 `tenant_*`。

> **省钱三件事**：按环节分档选模型；把终止条件设对（少转两轮最省钱）；
> 结构化输出别让模型自由发挥（返工一次就是一次全链路重跑）。

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
