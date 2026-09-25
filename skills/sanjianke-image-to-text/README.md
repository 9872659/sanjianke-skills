# 图片与文档 · 一键转文字 Skill

把图片和文档里的文字变成可复制的文本：

- **图片**（截图 / 海报 / 票据 / 照片 / 商品标签 / 扫描图）→ 走 **OpenAI 兼容模型网关**，视觉大模型直读
- **文档**（PDF / DOC / DOCX / TXT / MD）→ 走平台 **`file_qa`** 接口，问答、摘要、字段抽取

**不用装 OCR 程序、不用下模型权重、不用显卡。** 所有 AI 能力都走
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

1. **先分路**：输入是图片还是文档 —— 图片走视觉模型，文档走 `file_qa`，别混用。
2. **确认是公网 URL**：本地文件先上传到对象存储或图床，拿到匿名可访问的直链。
3. **跑最小示例**：一张图 + 一条「按阅读顺序提取全部文字」指令，先看输出结构。
4. **按目标写指令**：要纯文字、要 Markdown 表格、要 JSON 字段，指令必须写死。
5. **批量时控制并发**：图片一次一张、文档一次最多 8 份，分批发稳过一把梭。
6. **关键字段人工复核**：金额、编号、专有名词抽 5% 核对，比调提示词划算。

```bash
# 看这个插件有哪些接口、参数是什么
python3 scripts/a7w.py schema file_qa

# 文档问答（同步返回）
python3 scripts/a7w.py call file_qa chat \
  --body '{"file_urls":["https://你的存储/报告.pdf"],"question":"把全文整理成结构化文本，表格转 Markdown，不要概括"}'

# 异步解析（拿 task_id）
python3 scripts/a7w.py call file_qa parse \
  --body '{"file_urls":["https://你的存储/剧本.docx"],"parse_mode":"screenplay_scenes"}' --no-wait
```

图片转文字走模型网关，用 `curl` 或任意 OpenAI SDK：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen3-VL-30B-A3B-Instruct","messages":[{"role":"user","content":[
        {"type":"text","text":"按阅读顺序提取全部文字，保留换行，不要翻译、不要解释"},
        {"type":"image_url","image_url":{"url":"https://你的存储/截图.png"}}]}]}'
```

完整说明见 [`SKILL.md`](SKILL.md)，细节在 `references/`。

---

## 目录结构

```
sanjianke-image-to-text/
├── SKILL.md                    主入口：两条路径、提示词模板、计费、常见坑
├── README.md                   本文件
├── LICENSE.md
├── references/
│   ├── 转文字指南.md            选路、指令模板、精度提升、批量脚本
│   ├── api-file_qa.md          chat / parse 完整参数与返回
│   ├── api-模型网关.md          chat/completions 与视觉模型清单
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

> 模型网关（`/chat/completions`）不走 `a7w.py`，用 `curl` 或任意 OpenAI SDK 即可。

---

## 计费速查

| 动作 | 口径 | 折合 |
|---|---|---|
| 文档问答 `file_qa/chat` | 输入 2,600 点/百万 Token | 一次 2,492 Token 实测 16.55 点 ≈ 0.17 元 |
| 图片视觉识别 | 按所选模型的 Token 规则扣点 | 以返回 `usage` 为准 |
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
- 处理他人文档与图片前，请自行确认授权

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
