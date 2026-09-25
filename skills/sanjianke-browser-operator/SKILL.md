---
name: sanjianke-browser-operator
slug: sanjianke-browser-operator
displayName: 浏览器自动化操作员·一句话任务让Agent自己点填翻页抓取
description: "一句话任务描述，让 Agent 自己开着浏览器把网页上的活干完：点按钮、填表单、翻页、把结果取回来。写的是任务，不是选择器，页面改版也不容易整条断掉。含任务描述写法、模型挑选依据、真实浏览器与无头环境说明、步数上限与零依赖客户端。模型侧改一个 base_url 走 OpenAI 兼容网关即可，一把 Key 调 75 个在架模型，含支持视觉的模型可直接看截图决策。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "让 Agent 自己去操作网页：你写一句任务，它看着页面决定下一步点哪、填什么、翻到第几页，最后把结果交回来。适合那些没有 API、只有网页界面的场景 —— 后台系统、比价、批量填表、数据抄录。本包讲怎么把这类浏览器自动化的模型入口统一指向一个 OpenAI 兼容网关：只改一个 base_url，同一把 Key 调 75 个在架模型（DeepSeek、通义千问、智谱 GLM 等国产为主），并且能挑支持视觉的模型直接读页面截图做判断，账单还是同一份。含任务描述写法、模型挑选依据、步数上限与真实计费口径。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 浏览器自动化
  - 网页操作
  - OpenAI兼容
---

# 浏览器自动化操作员 · 一句话任务操控网页

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

它解决的是「这个网页上的活儿，你帮我干完」——**不是让你写选择器**，
而是你写一句任务描述，Agent 自己看着页面决定下一步点哪、填什么、翻到第几页，
最后把结果交回来。

适合那些**没有 API、只有网页界面**的场景：后台系统、比价、批量填表、数据抄录。

**它跟固定脚本最大的区别是抗变化**：页面改版不会像写死的选择器那样整条流水线断掉。
而它背后每一步要的模型调用，**换成 api.a7w.cn 的 OpenAI 兼容入口，就是一个 base_url 的事**。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **按 tokens 计费**（点数/百万 tokens，输入输出分别计价），1 元 = 100 点；每一步页面操作都是一次调用 |
| 要多久 | 每步一次模型调用，一个多步任务通常几十秒到几分钟 |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端，或者直接用 `curl` / 任意 OpenAI SDK |
| 模型从哪来 | **一个 base_url + 一个 Key**，可调 75 个在架模型，**含支持视觉的模型可直接看截图** |
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

### 第三步：把 Agent 的模型入口指向它

任何兼容 OpenAI 协议的框架 / SDK，只改两个字段：

```python
BASE_URL = "https://api.a7w.cn/api/v1"
API_KEY  = "sk-你的key"
```

框架里的模型对象通常长这样（示意）：

```python
# 只换 base_url 与 api_key，其余调用方式不变
llm = ChatOpenAI(
    model="DeepSeek-V4-Flash",
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",
)
```

### 第四步：挑模型 —— 这一步决定成功率

浏览器任务里模型要**看懂页面**，所以模型选择比别的场景更关键：

| 任务类型 | 建议 | 例 |
|---|---|---|
| **纯文本 DOM 抽取**（结构化列表、表格） | 快模型就够 | `DeepSeek-V4-Flash`、`Qwen3.6-Flash` |
| **要看截图判断**（布局复杂、图形化按钮） | **支持视觉的模型** | `Qwen3-VL-30B-A3B-Instruct`、`ERNIE-4.5-Turbo-VL`、`qwen3.6-plus` |
| **多步规划、长链路** | 强模型 | `DeepSeek-V4-Pro`、`GLM-5.2`、`Kimi-K2.6` |

### 第五步：零安装客户端也能直接跑

```bash
python3 scripts/a7w.py whoami                       # 验证 Key
python3 scripts/a7w.py call chat completions \
  --body '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

> 换模型只需改 `model` 字符串：**不用换 base_url、不用换 Key、账单还是同一份**。

---

## 二、包里有什么

```
sanjianke-browser-operator/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 网页操作指南.md          任务描述写法、模型挑选、真实浏览器与无头差异、成本估算
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

### 姿势 A：框架的模型对象（最省事）

```python
llm = ChatOpenAI(
    model="Qwen3-VL-30B-A3B-Instruct",       # 浏览器任务建议上视觉模型
    base_url="https://api.a7w.cn/api/v1",
    api_key="sk-你的key",
)
```

> 类名与参数名以你所用框架的当前版本为准（有些写作 `ChatOpenAI`，
> 有些写作 `ChatOpenAI` + `base_url` 字典）。**值永远是同一个网关地址与同一把 Key。**

### 姿势 B：纯 Python，用 OpenAI SDK 驱动「看页面 → 决定 → 执行」

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key=os.environ["A7W_API_KEY"],
)

SYSTEM = (
    "你是一个网页操作员。根据当前页面内容，输出下一步动作，"
    "格式为 JSON：{\"action\":\"click|type|scroll|extract|done\","
    "\"target\":\"...\",\"value\":\"...\",\"result\":\"...\"}。"
    "不要输出任何解释。"
)

def next_step(page_text: str, task: str, history: list) -> str:
    resp = client.chat.completions.create(
        model="Qwen3-VL-30B-A3B-Instruct",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",
             "content": "任务：%s\n已执行：%s\n当前页面：\n%s"
                        % (task, history, page_text)},
        ],
    )
    return resp.choices[0].message.content

def run(task: str, max_steps: int = 15) -> str:
    """主循环：看页面 → 让模型决定 → 执行 → 直到 done 或到步数上限。"""
    history, page_text = [], ""
    for _ in range(max_steps):
        action = next_step(page_text, task, history)
        history.append(action)
        if "\"done\"" in action:                 # 模型说干完了
            return action
        page_text = your_browser_execute(action) # 由你接的浏览器执行并回传新页面
    return "达到步数上限，已停止"
```

**三件事必须做对**：

1. **步数上限** —— 没有它，任务失败时模型会一直试，账单一直涨。
2. **只读优先** —— 任务描述里写清「不要点击提交 / 支付 / 删除类按钮」。
3. **结构化动作** —— 让模型输出 JSON 动作，你的代码负责执行，
   比让模型自由发挥稳定得多。

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

## 四、网页操作要点

### 任务描述怎么写

| 写得好的任务 | 写得糟的任务 |
|---|---|
| 「打开后台的订单页，把本月所有订单号与金额抄下来，输出成表格；只读不点任何提交按钮」 | 「看看后台」 |
| 「在这个比价页找到价格最低的那一项，把名称、价格、链接取回来」 | 「找最便宜的」 |
| 「把这页表格的 3 列数字抄下来，输出 JSON」 | 「抓一下数据」 |

**四要素**：**目标 + 边界 + 输出格式 + 只读/可写**。

- **目标**：要拿到什么。
- **边界**：只在哪几页 / 哪几个区域操作。
- **输出格式**：JSON、表格还是纯文本。
- **只读/可写**：明确「不要点提交、支付、删除」。

### 模型挑选依据

浏览器任务的模型分工很明确：

| 页面形态 | 需要什么 | 建议 |
|---|---|---|
| 结构化 DOM（列表、表格、表单） | 文本理解 | 快模型即可 |
| 图形化界面、复杂布局 | **视觉理解** | 支持视觉的模型 |
| 多步跳转、需要规划 | 推理与长上下文 | 强模型 |

**落地建议**：**先用快模型跑，失败率高的步骤再换视觉模型或强模型**。
两个阶段可以在同一个任务里混用，账单还是同一份。

### 真实浏览器与无头环境的差异

| 环境 | 适用 | 注意 |
|---|---|---|
| **本机带界面的浏览器** | 需要你已登录的后台、复杂交互 | 登录态来自你自己的浏览器配置 |
| **无头浏览器（服务器 / CI）** | 公开页面、批量任务 | 没有显示器；复杂页面渲染可能不同 |
| **云端浏览器** | 需要固定出口环境、批量并发 | 属于额外服务，注意成本 |

**本地跑通、服务器跑不起来**是最常见的一类问题：先确认目标环境里有没有显示器与浏览器依赖，
没有就走无头模式或把浏览器放到云端。

### 成本估算

```
单次任务调用数 ≈ 页面步数
单次任务成本   ≈ 步数 × 单步 tokens（含页面内容）× 模型单价
```

**页面内容是大头**：一页 HTML 可能几千到上万 tokens。
**缩小范围**（只传目标区域）、**限制步数**、**先把任务描述写精确**，三招一起用最省。

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **把 Key 写进代码** | 泄漏即等于余额泄漏 | Key 只从环境变量或 `~/.a7w/config.json` 读 |
| **没设步数上限** | 任务失败时一直重试，账单失控 | 设最大步数，到顶就停并报告 |
| **任务描述含糊** | Agent 乱点、结果不对 | 写清目标、边界、输出格式与只读约束 |
| **让 Agent 执行不可逆操作** | 误提交、误支付 | 只读优先；写操作必须人工确认 |
| **所有步骤都用强模型** | 成本翻几倍，效果提升有限 | 先快模型；难点再换视觉 / 强模型 |
| **页面内容整页塞进提示** | 单步 tokens 爆炸 | 只传目标区域或精简后的页面文本 |
| **本地能跑、服务器不能跑** | 无头环境没有显示器或浏览器依赖 | 改无头模式，或把浏览器放到云端 |
| **要登录的页面卡在登录框** | 新开的浏览器是干净配置 | 用你本机已登录的浏览器配置，或先在目标环境完成一次登录 |
| **`model` 名靠猜** | 报 404 模型不存在 | 调用前读一次模型清单，取值以接口返回为准 |
| **合规没确认就开跑** | 违反目标站点条款或数据合规要求 | 跑之前确认授权与站点规则；只用自有或已授权的账号与数据 |

---

## 六、计费

| 动作 | 口径 |
|---|---|
| Agent 的每一步 | 按 **tokens** 计，输入与输出分别计价；**页面内容是输入大头** |
| 换模型 | 换 `model` 即换单价；账单仍是同一份 |
| 应用任务类接口 | 按各接口口径（点数/次、点数/分钟、点数/张等） |

- **1 元 = 100 点，1 点 = ¥0.01。**
- **先冻结、后结算**：调用失败直接退款，异步任务失败冻结点数全额退回。
- 平台同时给出标准价与租户实际结算价，**以账号里实际扣费为准**；
  每次返回的 `data.usage` 就是本次真实用量，可直接对账。
- 实时查规则：先 `python3 scripts/a7w.py apps` 拿应用清单，再逐个 `schema <app>` 读 `tenant_*`。

> **省钱三件事**：页面内容只传目标区域；步数上限设小；先用快模型、难点再上强模型。

---

## 七、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的模型网关，并访问你要操作的目标网页 |
| 读取文件 | 仅读取你指定的输入文件与 `--json-file` 请求体 | 作为接口入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |
| 子进程 / 后台常驻 | 视情况 | 本地模式会拉起浏览器进程 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn` 与你要操作的目标站点，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代授权与合规审查**：只在**自有账号**或**已获授权**的页面上操作；
  目标站点的服务条款、robots 与数据合规由使用者自行确认
- **写操作要人工确认**：提交、支付、删除一类不可逆动作不要交给 Agent 自动执行
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
