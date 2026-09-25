# 文档转 Markdown Skill

把格式五花八门的资料统一成一份结构清晰的 **Markdown**，供大模型、RAG 切片与知识库消费。

上传公网文档地址（PDF / DOC / DOCX / TXT / MD），写清要保留什么结构，
几十秒拿回干净 Markdown —— 标题层级、列表、表格、链接都在，不是一坨无结构字符。
**一次最多同时处理 8 份**，可合并、可对比。

**不用装转换工具、不用配环境。** 所有能力都走
[算力集市 api.a7w.cn](https://api.a7w.cn/)，只需要一把你自己的 API Key。

---

## 前置条件

一把 **api.a7w.cn 的 API Key**。完整的注册、充值、取 Key 步骤见
[`references/getting-started.md`](references/getting-started.md)，
或直接去 [算力集市 · 注册领 API Key](https://api.a7w.cn/)（新用户送点数）。

```bash
python3 scripts/a7w.py login --key sk-你的key
python3 scripts/a7w.py whoami
```

---

## 使用

拿到这个 Skill 后，Agent 会按这套顺序干活：

1. **先问清用途**：给模型入库、给人归档、还是抽表格 —— 三种指令写法不同。
2. **确认是公网 URL**：本地文件先传到对象存储或网盘直链，拿到匿名可访问的地址。
3. **跑最小示例**：一份文档 + 一条「保留标题层级与表格、不要概括」指令，先看输出。
4. **按需补指令**：去页眉页脚、标点原样、按章节拆分 —— 都写进 `question`。
5. **批量时控并发**：2～4 路起步，结果写 JSONL，一行一份。
6. **入库前质检**：标题层级连续、表格管道符成对、无残留页码，再切片入库。

```bash
# 看这个插件有哪些接口、参数是什么
python3 scripts/a7w.py schema file_qa

# 转 Markdown（同步返回）
python3 scripts/a7w.py call file_qa chat \
  --body '{"file_urls":["https://你的存储/产品手册.pdf"],"question":"把全文整理成结构化 Markdown，保留标题层级、列表与表格，去掉页眉页脚与页码，不要概括、不要漏段"}'

# 超长文档走异步，先拿 task_id
python3 scripts/a7w.py call file_qa chat \
  --body '{"file_urls":["https://你的存储/白皮书.pdf"],"question":"整理成 Markdown","mode":"async"}' --no-wait

# 按 task_id 收结果（免费）
python3 scripts/a7w.py task <task_id>
```

完整说明见 [`SKILL.md`](SKILL.md)，细节在 `references/`。

---

## 目录结构

```
sanjianke-doc-to-markdown/
├── SKILL.md                    主入口：指令模板、转换清单、计费、常见坑
├── README.md                   本文件
├── LICENSE.md
├── references/
│   ├── 转Markdown指南.md        指令模板、质检清单、批量脚本、扫描件做法、入库流程
│   ├── api-file_qa.md          chat / parse 完整参数与返回
│   ├── getting-started.md      注册 / 充值 / 取 Key / 配置
│   └── 通用说明.md              响应信封、异步机制、错误码、计费口径
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行）
```

---

## 客户端命令

| 命令 | 作用 |
|---|---|
| `login --key sk-xxx` | 验证并保存 Key 到 `~/.a7w/config.json` |
| `whoami` | 验证 Key，看可用插件数 |
| `apps` | 列出这个 Key 能用的所有插件 |
| `schema <app>` | 看某插件的接口与参数 |
| `call <app> <api> --body '{...}'` | 调用接口（异步自动轮询） |
| `call ... --no-wait` | 只提交，不等结果 |
| `task <task_id>` | 查异步任务状态 |
| `points` | 看最近的用量 |

---

## 计费速查

| 动作 | 口径 | 折合 |
|---|---|---|
| 文档转 Markdown | 输入 2,600 点/百万 Token | 一份 20 页 PDF（约 30,000 Token）约 78 点 ≈ 0.78 元 |
| 结构化解析 `parse` | 同上（按 Token） | — |
| 查询任务 | 免费 | — |

1 元 = 100 点，按实际用量扣点、没有月费。实际扣费以 `data.usage.points_cost` 为准。

---

## 依赖

- Python 3.8+，**仅标准库**（urllib / json / mimetypes），无第三方包
- 需要能访问 `https://api.a7w.cn`

---

## 安全

- Key 存在本机 `~/.a7w/config.json`（权限 600）或环境变量 `A7W_API_KEY`
- 脚本只把 Key 发往 `api.a7w.cn`
- **不要**把 Key 提交到代码仓库
- 转换他人文档前，请自行确认授权

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
