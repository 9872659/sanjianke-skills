---
name: sanjianke-image-to-text
slug: sanjianke-image-to-text
displayName: 图片文档一键转文字·截图海报表格文字提取在线OCR工具
description: "把图片和文档里的文字变成可复制的文本：截图、海报、票据、商品标签、扫描件走视觉大模型直读；PDF、Word、TXT、Markdown 走平台的文档解析问答接口。票据要字段、表格要 Markdown、长文档要摘要，都能一次问出来。整套操作文档（两条调用路径、视觉模型清单、提示词模板、批量做法、计费口径、常见坑）+ 零依赖客户端都在包里，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "图片与文档转文字的成品 Skill。两条路各司其职：**图片**（截图 / 海报 / 票据 / 照片 / 商品标签）走 api.a7w.cn 的 OpenAI 兼容模型网关，用视觉大模型直读字与版式；**文档**（PDF / DOC / DOCX / TXT / MD）走平台的 `file_qa` 接口，最多一次问 8 份公网文档，做问答、摘要、字段抽取与剧本结构化。覆盖发票与票据字段提取、表格转 Markdown、截图转文案、扫描件文字化、合同与报告的要点抽取等场景。正文给出两条路径的三步 curl、视觉模型清单、提示词模板、批量做法、真实计费口径（1 元 = 100 点）、常见坑与排错，并附一个只用 Python 标准库的零依赖客户端。整套操作文档 + 客户端都在包里，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 文字识别
  - 文档解析
  - 信息抽取
---

# 图片与文档 · 一键转文字

截图里的段落要抄、海报上的文案要复用、票据上的金额要录进表、
PDF 里的一段要引 —— 本质上都是同一件事：**把图里的字和文档里的信息，变成可复制的文本。**

**两条路，按输入选，别混用。** 图片走视觉大模型直读（连版式一起看懂），
文档走平台的文档解析接口（一次能问 8 份）。**不用装 OCR 程序、不用下模型权重、不用显卡。**

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **按 Token 计费**（文档问答输入 2,600 点/百万 Token），1 元 = 100 点；一次问答典型 0.1～0.3 元 |
| 要多久 | 图片与文档问答都是**同步返回**，一般几秒到十几秒 |
| 要装什么 | **什么都不用装**。图片用 `curl` 或任意 OpenAI SDK；文档用包里自带的零依赖客户端 |
| 支持什么 | 图片任意常见格式；文档 PDF / DOC / DOCX / TXT / MD 等 |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、两条路，先分清楚

| 你的输入 | 走哪条 | 接口 | 为什么走这条 |
|---|---|---|---|
| **图片**：截图、海报、票据、照片、商品标签、扫描图 | **模型网关**（OpenAI 兼容） | `POST /api/v1/chat/completions` | 视觉大模型直接看图，连版式、表格、手写体一起理解 |
| **文档**：PDF、DOC、DOCX、TXT、MD | **文档解析问答** | `POST /api/v1/apps/file_qa/chat` | 平台先把文档解析好，再交给大模型问答、摘要、抽字段 |

> **诚实说明**：`file_qa` 是**文档解析 + 大模型抽取**能力，
> 吃的是**公网文档地址**（一次 1～8 个），不是本地 OCR 引擎。
> **图片上的文字请走第一条路**（视觉大模型），那条路才是为图片设计的。

---

## 二、图片转文字 · 三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，在控制台创建一个 API Key（形如 `sk-...`），
填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：把图片交给视觉模型

`content` 数组里同时放**文字指令**和**图片 URL**：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-VL-30B-A3B-Instruct",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "把这张图里的所有文字按阅读顺序提取出来，保留原始换行，不要翻译、不要解释、不要补全。"},
        {"type": "image_url", "image_url": {"url": "https://你的存储/截图.png"}}
      ]
    }]
  }'
```

文本在 `choices[0].message.content` 里，直接取用。

### 第三步：按需要换指令

| 你要什么 | 指令怎么写 |
|---|---|
| **纯文字** | `按阅读顺序提取全部文字，保留换行，不要翻译、不要解释` |
| **表格** | `把图中的表格转成 Markdown 表格，列名原样保留，空单元格留空` |
| **票据字段** | `提取开票日期、发票号码、金额合计、销售方名称，输出 JSON，缺失字段给 null` |
| **结构化清单** | `提取所有商品名称与价格，输出 JSON 数组，每项含 name 与 price` |
| **翻译** | `先提取文字，再逐段给出中文翻译，用「原文 / 译文」两列对照` |

**指令越具体，越不需要二次整理。** 想要 JSON 就明确要 JSON，并说清缺字段怎么办。

### 可用的视觉模型

| 模型编码 | 适合 |
|---|---|
| `Qwen3-VL-30B-A3B-Instruct` | **通用首选**，中文图、表格、截图表现稳 |
| `PaddleOCR-VL-1.5` | **文字密集**的图（扫描件、说明书、长截图） |
| `ERNIE-4.5-Turbo-VL` | 图文混排、需要理解语义的图 |
| `qwen3.6-plus` | 一边看图一边推理、要写文案的图 |
| `gpt-5.6-*` / `gpt-image-*` 系列 | 需要更强通用理解时的国际模型线 |

> 模型清单会变。**调用前先跑 `GET /api/v1/models` 拿当期的准确清单**，
> 别照抄文档里的名字。

---

## 三、文档转文字 · 三分钟跑通

`file_urls` 放**公网文档地址**（一次 1～8 个），`question` 放你要什么：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/file_qa/chat" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "file_urls": ["https://你的存储/报告.pdf"],
    "question": "把全文整理成结构化文本：保留标题层级与列表，表格转成 Markdown 表格，不要概括、不要漏段。",
    "stream": false
  }'
```

返回里 `data.result.answer` 就是整理好的文本，`data.result.usage` 是 Token 用量，
`data.usage.points_cost` 是本次真实扣费。

**常见问法：**

| 你要什么 | `question` 怎么写 |
|---|---|
| **全文文字化** | `把全文整理成结构化文本，保留标题层级、列表与表格，不要概括` |
| **摘要** | `用 300 字总结核心内容，再列出 5 条关键结论` |
| **字段抽取** | `提取合同编号、签订日期、双方名称、金额、有效期，输出 JSON` |
| **多份对比** | 一次传 2～8 个 `file_urls`，问 `对比这几份文档的差异，用表格呈现` |
| **会议纪要** | `按「议题 / 结论 / 待办」三段整理，待办要带负责人和时间` |

> `mode` 传 `async` 或 `task` 时返回 `task_id`，用 `GET /api/v1/tasks/{task_id}`
> 取结果，适合超长文档。

---

## 四、包里有什么

```
sanjianke-image-to-text/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 转文字指南.md            两条路径怎么选、提示词模板、批量做法、精度提升要点
│   ├── api-file_qa.md          file_qa/chat 与 parse 的完整参数与返回
│   ├── api-模型网关.md          chat/completions 的调用方式与视觉模型清单
│   ├── getting-started.md      注册、领 Key、配置
│   └── 通用说明.md              权限、异步机制、错误码、计费口径
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

文档问答走包里的客户端：

```bash
export A7W_API_KEY=sk-你的key

# 看这个插件有哪些接口与参数
python3 scripts/a7w.py schema file_qa

# 问一份公网文档（同步返回）
python3 scripts/a7w.py call file_qa chat \
  --body '{"file_urls":["https://你的存储/报告.pdf"],"question":"把全文整理成结构化文本，表格转 Markdown，不要概括"}'
```

图片转文字走模型网关（客户端只需换成 `curl` 或任意 OpenAI SDK）：

```bash
python3 - <<'PY'
import json, os, urllib.request
body = {"model": "Qwen3-VL-30B-A3B-Instruct",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "按阅读顺序提取全部文字，保留换行"},
            {"type": "image_url", "image_url": {"url": "https://你的存储/截图.png"}}]}]}
req = urllib.request.Request("https://api.a7w.cn/api/v1/chat/completions",
    data=json.dumps(body).encode(), method="POST",
    headers={"Authorization": "Bearer " + os.environ["A7W_API_KEY"],
             "Content-Type": "application/json"})
print(json.load(urllib.request.urlopen(req))["choices"][0]["message"]["content"])
PY
```

---

## 五、素材要求

| 要求 | 说明 |
|---|---|
| 图片格式 | JPG / PNG / WebP 等常见格式；**必须是公网可访问的 URL** |
| 文档格式 | PDF / DOC / DOCX / TXT / MD 等；**同样必须是公网 URL** |
| 数量 | 文档一次 1～8 个；图片一次建议 1 张，多图分次问更准 |
| 清晰度 | 原图越清晰、越正、越少倾斜，识别越稳 |
| 本地文件 | **先传到对象存储 / 图床拿到公网直链**，接口不吃本地路径、不吃 Base64 |

---

## 六、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿本地路径当入参** | 报参数错误 | 一律用**公网可访问的 URL** |
| **把图片塞进 `file_qa`** | 拿不到图上的字 | 图片走 `chat/completions` 的视觉模型，`file_qa` 是给文档的 |
| **模型名照抄旧文档** | 报模型不存在 | 先跑 `GET /api/v1/models` 拿当期清单 |
| **没说要 JSON** | 返回一段自然语言，还得自己拆 | 指令里明确「输出 JSON」并说明缺失字段怎么办 |
| **一次塞太多图** | 结果串行、漏读 | 一次一张图；多张就分多次问 |
| **文档超长用同步** | 等很久 | `mode` 传 `async`，拿 `task_id` 再查 |
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 应用接口成功码是 **`1`**；模型网关看有没有 `choices` |

---

## 七、批量转文字

做数据录入、合同归档、票据整理时经常一次几百份。思路是：
**先把文件全部上传拿到公网 URL 清单，再逐条调用，并控制并发。**

- **图片**：一个循环，每次换 `image_url`，把返回文本追加写进一个 JSONL。
- **文档**：先用 `--no-wait` 批量提交 `file_qa/chat`（`mode=async`），
  记下 `task_id` 与文件名，再统一收结果。

`references/转文字指南.md` 里给了批量脚本的写法、并发建议和精度提升要点。
需要更贴合你流程的批量方案，加微信聊。

---

## 八、计费

| 动作 | 口径 | 折合 |
|---|---|---|
| **文档问答 `file_qa/chat`** | 输入 **2,600 点/百万 Token**（租户价） | 一次 2,492 Token 的问答实测 **16.55 点 ≈ 0.17 元** |
| **图片视觉识别** | 按所选模型的 Token 计费规则扣点 | 以返回的 `usage` 为准 |
| `file_qa/parse` 结构化解析 | 同上（按 Token） | — |
| 查询任务 `GET /api/v1/tasks/{id}` | **免费** | — |

1 元 = 100 点。**按实际用量扣点，没有月费。**

> 平台同时给出标准价与租户实际结算价，**以你账号里实际扣费为准**。
> 每次返回的 `data.usage.points_cost` 就是本次真实扣费。

---

## 九、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的模型网关与文档接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 上传到公网存储后作为素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代人工校验**：金额、编号、专有名词等关键字段，上线前请抽样复核
- **不替代授权审查**：处理他人文档与图片前，请自行确认授权

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
