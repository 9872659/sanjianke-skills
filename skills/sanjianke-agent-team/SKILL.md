---
name: sanjianke-agent-team
slug: sanjianke-agent-team
displayName: 多智能体软件开发团队·一句话需求生成项目文档与代码骨架
description: "一句话需求进去，一整套东西出来：用户故事、需求拆解、数据结构、接口设计、文档，最后落到一个能打开的项目仓库。含角色分工与产出清单、模型接入配置、需求写法与零依赖客户端。模型侧改一个 base_url 走 OpenAI 兼容网关即可，一把 Key 调 75 个在架模型、按角色分档指定。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "给一句需求，想要的不只是一段代码，而是一整套东西：用户故事、竞品分析、需求拆解、数据结构、接口设计、文档，最后落到一个能打开的仓库。本包讲怎么把这种多角色流水线的模型入口统一指向一个 OpenAI 兼容网关 —— 只改一个 base_url，同一把 Key 调 75 个在架模型（DeepSeek、通义千问、智谱 GLM、Kimi、腾讯混元等国产为主），并且能给不同角色分配不同档位：拆需求用快模型、写架构用强模型，账单还是同一份。含角色分工与产出清单、需求写法、产物目录说明与真实计费口径。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 多智能体
  - 需求拆解
  - OpenAI兼容
---

# 多智能体软件开发团队 · 一句话需求生成项目骨架

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

给一句需求，想要的不只是「一段代码」，而是一整套东西：
用户故事、竞品分析、需求拆解、数据结构、接口设计、文档，
最后落到一个能打开的项目仓库。

这类框架把**一家软件公司的分工与流程**搬到模型上：产品经理、架构师、项目经理、
工程师各司其职，按流程把需求一层层往下传。

**而它背后要的那几十次模型调用，换成 api.a7w.cn 的 OpenAI 兼容入口，就是一个 base_url 的事**——
你还能按角色分档选模型：拆需求用快模型、写架构用强模型，**账单还是同一份**。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **按 tokens 计费**（点数/百万 tokens，输入输出分别计价），1 元 = 100 点；一条需求会触发多次调用 |
| 要多久 | 多角色多轮流水线，一条需求通常要跑几分钟到十几分钟 |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端，或者直接用 `curl` / 任意 OpenAI SDK |
| 模型从哪来 | **一个 base_url + 一个 Key**，可调 75 个在架模型，**不同角色可分档指定** |
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

### 第三步：把流水线的模型入口指向它

这类框架的模型配置一般落在一个 YAML 或环境变量里，把 `base_url` 与 `api_key` 改成网关：

```yaml
llm:
  api_type: "openai"                       # 走 OpenAI 兼容协议
  model: "DeepSeek-V4-Pro"                 # 主链路用强模型
  base_url: "https://api.a7w.cn/api/v1"
  api_key: "sk-你的key"
```

或者用环境变量：

```bash
export OPENAI_API_KEY=sk-你的key
export OPENAI_BASE_URL=https://api.a7w.cn/api/v1
```

> **键名与配置文件名以你所用框架的当前版本为准。**
> **值永远是同一个网关地址与同一把 Key。**

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
sanjianke-agent-team/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 团队流水线指南.md        角色分工、产出清单、需求写法、产物目录、成本估算
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

### 姿势 A：框架的模型配置（最省事）

```yaml
llm:
  api_type: "openai"
  model: "DeepSeek-V4-Pro"
  base_url: "https://api.a7w.cn/api/v1"
  api_key: "sk-你的key"
```

按角色分档时，在角色定义处覆盖模型即可：

| 角色 | 建议档位 | 例子 |
|---|---|---|
| 需求拆解 / 文档整理 | 快模型（便宜） | `DeepSeek-V4-Flash`、`Qwen3.6-Flash` |
| 方案设计 / 内容撰写 | 中档模型 | `Qwen3.7-Plus`、`GLM-5`、`MiniMax-M3` |
| 架构设计 / 核心实现 | 强模型 | `DeepSeek-V4-Pro`、`GLM-5.2`、`Kimi-K2.6` |

### 姿势 B：纯 Python，自己串角色

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key=os.environ["A7W_API_KEY"],
)

ROLES = [
    {"name": "需求", "model": "DeepSeek-V4-Flash",
     "system": "把一句话需求拆成用户故事与验收标准，输出 Markdown 清单。"},
    {"name": "架构", "model": "DeepSeek-V4-Pro",
     "system": "基于需求清单给出数据结构与接口设计，输出 Markdown。"},
    {"name": "实现", "model": "Qwen3.7-Plus",
     "system": "基于前两份文档给出可运行的最小实现，按文件分块输出。"},
]

def run_pipeline(requirement: str) -> dict:
    """按 SOP 顺序执行，每个角色读到前面所有产出。"""
    docs = {}
    for role in ROLES:
        context = "\n\n".join("## %s\n%s" % (k, v) for k, v in docs.items())
        resp = client.chat.completions.create(
            model=role["model"],
            messages=[
                {"role": "system", "content": role["system"]},
                {"role": "user",
                 "content": "需求：%s\n\n已有产出：\n%s" % (requirement, context)},
            ],
        )
        docs[role["name"]] = resp.choices[0].message.content
    return docs
```

**两个要点**：

1. **角色顺序就是 SOP**，产出按顺序往下传，别让模型自己找上下文。
2. **产物落盘到独立目录**，不要写进源码目录。

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

## 四、团队流水线要点

### 角色分工与产出

| 角色 | 产出 |
|---|---|
| 产品 | 用户故事、竞品分析、需求清单与优先级 |
| 架构 | 数据结构、模块划分、接口设计 |
| 项目 | 任务拆解、排期、里程碑 |
| 实现 | 代码骨架、目录结构、可运行的最小闭环 |
| 测试 / 复核 | 用例清单、边界条件、验收结论 |

**每个角色的产出都要落成文件**，这样进度可见、可回溯、可交接。

### 需求怎么写

| 写得好的需求 | 写得糟的需求 |
|---|---|
| 「做一个命令行待办工具，支持增删改查，数据存本地 JSON 文件」 | 「做个有用的工具」 |
| 「一个小游戏：2048，键盘方向键操作，显示分数与最高分」 | 「做个游戏」 |

**判断口径**：需求里能不能看出**验收标准**？看不出来就先补需求，再跑流水线。

### 产物目录

产物统一落在工作目录下的一个独立子目录（常见是 `workspace/` 一类），
**不要直接写进源码目录**。跑之前先确认：

- 产物根目录在哪
- 磁盘够不够（一个项目就是一堆文件）
- 这个目录有没有被你自己的版本控制忽略

### 成本估算

```
单次任务调用数 ≈ 角色数 × 每个角色的平均调用次数
单次任务成本   ≈ 调用数 × 单次调用 tokens × 对应模型的单价
```

**先拿一个小需求试跑**（命令行小工具、小游戏这类边界清晰的），
看一次消耗多少点，再决定要不要上更大的需求。

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **把 Key 写进代码 / 配置文件提交进仓库** | 泄漏即等于余额泄漏 | Key 从环境变量读；配置文件加进 `.gitignore` |
| **模型配置没初始化** | 报模型调用失败 / 认证失败 | 先初始化配置文件，再填 `base_url` 与 `api_key` |
| **需求太模糊就开跑** | 产出飘、返工，钱白花 | 需求里写清验收标准；先拿小需求试跑 |
| **所有角色都用最强模型** | 成本翻几倍 | 按角色分档：拆解用快模型、架构用强模型 |
| **容器 / 多环境配置路径不一致** | 改了配置不生效 | 确认配置实际生效的路径，必要时用挂载或环境变量统一 |
| **产物写进源码目录** | 版本控制被污染 | 指定独立产物目录，并加进忽略规则 |
| **一次跑大需求** | 耗时长、消耗高、中途看不清进度 | 从小需求起步，确认链路与成本后再放大 |
| **生成的代码直接上生产** | 边界处理、测试覆盖不足 | 把产出当**起步骨架 + 设计文档**，接手后自行补测试与边界 |
| **网络抖动丢掉已付费的调用** | 重试一次扣两次 | 自己做幂等：先记请求状态再决定是否重试 |

---

## 六、计费

| 动作 | 口径 |
|---|---|
| 每个角色的一次调用 | 按 **tokens** 计，输入与输出分别计价 |
| 换角色模型 | 换 `model` 即换单价；账单仍是同一份 |
| 应用任务类接口 | 按各接口口径（点数/次、点数/分钟、点数/张等） |

- **1 元 = 100 点，1 点 = ¥0.01。**
- **先冻结、后结算**：调用失败直接退款，异步任务失败冻结点数全额退回。
- 平台同时给出标准价与租户实际结算价，**以账号里实际扣费为准**；
  每次返回的 `data.usage` 就是本次真实用量，可直接对账。
- 实时查规则：先 `python3 scripts/a7w.py apps` 拿应用清单，再逐个 `schema <app>` 读 `tenant_*`。

> **省钱三件事**：按角色分档选模型；需求写清楚少返工；
> 先用小需求试跑校准单次成本。

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
