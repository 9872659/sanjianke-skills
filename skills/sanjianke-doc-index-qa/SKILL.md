---
name: sanjianke-doc-index-qa
slug: sanjianke-doc-index-qa
displayName: 文档索引与知识检索·数据接进模型接OpenAI兼容网关统一计费
description: "模型本身不认识你的文件。这个 Skill 讲的是中间缺的那一层：把 PDF、Word、表格、接口返回的数据接成可检索、可问答的知识库，并把模型侧整排指向 https://api.a7w.cn/ ——一个 base_url、一把 Key，现场可查 75 个在架模型与 21 个生成应用（含文档问答 file_qa）；包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) 。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "模型本身不认识你的文件。想让它回答「我们公司这份规范里怎么写的」，中间缺的就是一层：把文档切成片、算成向量、存起来，提问时先捞出相关片段再交给模型。这个 Skill 讲的就是这一层的落地：加载、切分、索引、检索、问答，每一段都可替换。模型侧同样收成一处——把 base_url 指向 https://api.a7w.cn/ ，用同一把 Key 调用 75 个在架大模型（23 家厂商，国产为主 + 国际主流）与 21 个生成应用，文档问答走 file_qa、语音转写走 voice_tts，账单只有一份。包内含完整操作文档说明，所有能力走 [算力集市 api.a7w.cn](https://api.a7w.cn/) ，注册即送点数、按量计费、失败全额退回。含最小可用接法、多语言 SDK 对照、素材要求、点数计费口径、错误码排查手册与零依赖客户端。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 知识管理
  - AI
  - LLM
  - 文档索引
  - 检索问答
---

# 文档索引与知识问答 · 把数据接进模型

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

模型本身不认识你的文件。

你想让它回答「我们公司这份规范里怎么写的」，中间缺的就是一层：
**把 PDF、Word、表格、接口返回的数据切成片、算成向量、存起来，提问时先捞出相关片段再交给模型。**

而这一层用到的模型能力——生成回答、文档问答、语音转写——可以只指向**一个 base_url**。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **1 元 = 100 点**；文本按点数/百万 tokens，文档问答按点数/次 |
| 要多久 | 模型调用同步返回；长文档问答是异步任务，**查询免费** |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端，或者直接用 `curl` |
| 能接什么 | **75 个在架模型** + **21 个生成应用**（含 `file_qa` 文档问答） |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：把模型侧指向 a7w

```
Base URL: https://api.a7w.cn/api/v1
Authorization: Bearer <你的 API Key>
```

```python
import os
from openai import OpenAI

client = OpenAI(base_url="https://api.a7w.cn/api/v1", api_key=os.environ["A7W_API_KEY"])
print(client.chat.completions.create(
    model="DeepSeek-V4-Flash",
    messages=[{"role": "user", "content": "你好"}],
).choices[0].message.content)
```

### 第三步：最省事的一条路——直接用文档问答应用

**不用自己搭切片与索引**，`file_qa` 就是现成的文档问答入口：

```bash
# 看这个应用有哪些接口、参数、是同步还是异步
python3 scripts/a7w.py schema file_qa

# 直接问一份文档
python3 scripts/a7w.py call file_qa ask \
  --body '{"file_url":"https://你的存储/规范.pdf","question":"报销流程是怎样的"}'
```

**路径永远是 `/api/v1/apps/<应用代号>/<接口代号>`。**
⚠️ 不要用平台的 `endpoint_path` 字段拼 URL —— 对某些应用那是错的上游路径，打不通。

> 素材一律用**公网可访问的 URL**；本地文件先传到对象存储 / 图床拿到链接。

### 第四步：自建索引时，模型这一端怎么选

```bash
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

| 用途 | 建议 `model` |
|---|---|
| 回答生成、性价比优先 | `DeepSeek-V4-Flash`、`Qwen3.6-Flash` |
| 长上下文（整篇文档塞进去） | `Kimi-K2.6` |
| 复杂推理 | `DeepSeek-R1-Distill-Qwen-32B`、`ERNIE-5.0-Thinking` |
| 扫描件、含表格的文档 | `qwen3.6-plus`、`Qwen3-VL-30B-A3B-Instruct`、`PaddleOCR-VL-1.5` |

> 实测 75 个模型 / 23 家厂商。**清单会变，调用前现场跑一次**，
> 不要把自己的逻辑绑在某个名字一定存在上。

### 第五步：语音类素材也能一条链走完

素材是会议录音、播客、视频时，转写同样在这套体系里：

```bash
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py call voice_tts stt \
  --body '{"audio_url":"https://你的存储/会议录音.mp3"}'
```

转写结果落进索引，就跟文档走同一条检索链路——**同一个 base_url、同一把 Key**。

---

## 二、包里有什么

```
sanjianke-doc-index-qa/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── a7w-接入指南.md          base_url / 鉴权 / SDK 写法 / 模型切换
│   ├── 框架接入对照.md          不同语言与低代码平台的接法
│   ├── api-应用与任务.md        21 个生成应用、异步任务、回调
│   ├── 计费与错误码.md          点数口径、两套价格字段、错误码排查手册
│   ├── client-cli.md            a7w.py 的子命令、参数与退出码
│   └── getting-started.md       注册、领 Key、配置到本机
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 验证 Key 并保存到 ~/.a7w/config.json
python3 scripts/a7w.py login --key sk-你的key

# 看这把 Key 能用的插件数
python3 scripts/a7w.py whoami

# 列出全部应用与模型
python3 scripts/a7w.py apps

# 看某应用的接口与参数（含同步/异步标记）
python3 scripts/a7w.py schema file_qa

# 调接口（异步自动轮询）
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好世界"}'
```

---

## 三、一条完整的索引问答链路

| 环节 | 做什么 | 走哪 |
|---|---|
| **加载** | 把 PDF / Word / 表格 / 接口数据变成文本 | 你的读取器，或直接上传公网 URL |
| **切分** | 按语义完整度切块，块太小会丢上下文、太大检索会飘 | 你的流程 |
| **索引** | 存成可检索结构（向量库 / 平台知识库） | 你的存储，或平台知识库 |
| **回答** | 捞出相关片段 + 问题交给模型 | `POST /api/v1/chat/completions` |
| **省事路线** | 不想自己搭上面四步 | 应用 `file_qa` 一条接口 |

**先跑通「一份文档 → 一个问题 → 一段带出处的答案」，再去上量。**
一上来就灌几百份文件，出了问题是定位不到的。

---

## 四、能接到的能力清单

| 类别 | 代表能力（`model` / 应用代号） |
|---|---|
| 中文长文与性价比 | `DeepSeek-V4-Flash`、`Qwen3.6-Flash`、`GLM-5` |
| 长上下文 | `Kimi-K2.6`、`Qwen3-Coder-Next` |
| 视觉 / OCR 理解 | `qwen3.6-plus`、`Qwen3-VL-30B-A3B-Instruct`、`PaddleOCR-VL-1.5` |
| **文档问答** | 应用 `file_qa` |
| 语音转写 | 应用 `voice_tts`（含语音转文字） |
| 出图 / 视频 / 数字人 | 应用 `nano_banana`、`full_video`、`image_human` 等 |

**清单以实时接口为准**：模型跑 `GET /api/v1/models`，应用跑 `python3 scripts/a7w.py apps`。

---

## 五、素材与配置要求

| 要求 | 说明 |
|---|---|
| 网络 | 需要能访问 `https://api.a7w.cn` 的出口（内网 / CI 需放行该域名） |
| Python | **3.8+**，只用标准库；不跑脚本的话连 Python 都不需要 |
| 文档格式 | PDF / Word / 表格 / 纯文本等常见格式；扫描件先确认有没有文本层 |
| 素材入参 | 文档 / 音频 / 图片一律用**公网可访问的 URL**，不支持本地路径、不支持 Base64 |
| 凭证 | 只需**你自己**的 API Key；包里不内嵌任何密钥 |

---

## 六、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |
| **HTTP 200 就以为成功** | 调不存在的接口也返回 200 | 业务成败看 `code`：`1` / `200` 成功，`0` 失败 |
| **把本地路径当文档入参** | 报参数错误 | 一律用**公网可访问的 URL** |
| **用 `endpoint_path` 拼 URL** | 某些应用怎么调都打不通 | 一律用 `/api/v1/apps/{app}/{code}` |
| **应用代号写成连字符** | 404 | API 里用下划线：`file_qa`、`voice_tts` |
| **拿 `name` 当接口代号** | 调用失败 | 字段名是 `code`，不是 `api`；`name` 是中文展示名 |
| **扫描件检索不到内容** | 提问答不出来 | 扫描件先确认有文本层；需要版面理解时换视觉类模型 |
| **检索到的内容答不准** | 回答跑偏 | 把问题问具体、把块切成语义完整的，再考虑换更大的模型 |
| **整篇文档每次都重跑** | 又慢又贵 | 索引建好后持久化；新增文档走增量，不要全量重跑 |
| **做预算用公示标准价** | 预算算错 | 一律用 `tenant_*`（实际结算价） |

---

## 七、计费

- 计价单位是**点数**，**1 元 = 100 点、1 点 = ¥0.01**。点数永久有效，没有月费。
- 计费口径随能力不同：文本按**点数/百万 tokens**（输入输出分别计价，流式与非流式同价）、
  图像按**点数/张或参数档位**、视频生成与超分按**点数/秒**、数字人按**点数/次或时长**、
  TTS 与克隆按**点数/千字**、ASR 按**点数/分钟**、工具类按**点数/次**。
- **先冻结、后结算**：消费优先扣会员点数，不足再扣充值额度；
  **调用失败直接退款，异步任务失败冻结点数全额退回**，只有成功产出才按实际用量结算。
  上游调价会同步调整，但**不影响已充值的点数余额**。

| 字段 | 含义 |
|---|---|
| `fixed_price` / `input_price` | **标准价**，对外公示用 |
| `tenant_fixed_points` / `tenant_points_per_1k_input` | **你所在租户的实际结算价** |

做预算一律用 `tenant_*`。每次返回的 `data.usage.points_cost` 就是本次真实扣费，可以直接对账。

---

## 八、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的网关与应用接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 作为接口的素材入参与请求体 |
| 写入文件 | 仅在传入 `--out` 时 | 保存接口返回的 JSON 或下载产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量 `A7W_API_KEY` 或 `~/.a7w/config.json` 读取 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代内容合规审查**：生成内容的使用与发布责任由使用者承担
- **不保证可用性**：模型与应用上下架、限流与计费以站内为准

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
