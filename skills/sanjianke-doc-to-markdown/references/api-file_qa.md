# 文档接口 · file_qa

> `api.a7w.cn` 应用 `file_qa` · 公网文档的问答、摘要、字段抽取与结构化解析

---

## 一、文件问答 chat

`POST /api/v1/apps/file_qa/chat`

对一个或多个公网文档进行问答、摘要和信息提取。
**客户端只能提交 URL，不能上传文件、Base64 或本地路径。**

### 请求参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `file_urls` | string[] | **是** | - | 1～8 个公网 HTTP/HTTPS 文档地址，支持 PDF、DOC、DOCX、TXT、MD 等格式 |
| `question` | string | **是** | - | 针对文件内容的问题，最长 20,000 字符 |
| `mode` | string | 否 | `sync` | 传 `async` 或 `task` 时返回 `task_id`，改用任务查询接口取结果 |
| `stream` | boolean | 否 | `false` | 是否返回 SSE 流式响应；**仅同步模式生效** |
| `callback_url` | string | 否 | - | 异步模式完成 / 失败的回调地址 |
| `metadata` | object | 否 | - | 业务关联字段，平台仅记录 |

### 请求示例

```json
{
  "file_urls": ["https://example.com/document.docx"],
  "question": "请总结核心内容，并列出主要人物",
  "stream": false
}
```

### 成功响应

```json
{
  "code": 1,
  "data": {
    "result": {
      "answer": "文档主要介绍……",
      "usage": { "input_tokens": 1524, "output_tokens": 968, "total_tokens": 2492 }
    },
    "usage": { "points_cost": 16.5464, "actual_points": 16.5464 }
  }
}
```

| 字段 | 说明 |
|---|---|
| `code` | 平台响应码，**`1` 表示成功** |
| `data.result.answer` | 模型生成的回答正文 |
| `data.result.usage` | 上游模型用量统计（`input_tokens` / `output_tokens` / `total_tokens`） |
| `data.usage.points_cost` | 本次真实扣费点数 |

### 计费

- 租户价：**输入 2,600 点/百万 Token**
- 1 元 = 100 点；一次 2,492 Token 的问答约 16.55 点 ≈ 0.17 元
- 实际扣费以 `data.usage.points_cost` 为准

---

## 二、结构化解析 parse

`POST /api/v1/apps/file_qa/parse`

提交公网剧本、小说或故事大纲地址，返回平台 `task_id`，
用 `GET /api/v1/tasks/{task_id}` 查询结果。

### 请求参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `file_urls` | string[] | **是** | - | 1～8 个公网 HTTP/HTTPS 文档地址 |
| `parse_mode` | string | 否 | `auto` | `auto` / `existing_episodes` / `screenplay_scenes` / `novel` / `outline` / `split_by_ai` |
| `preserve_original` | boolean | 否 | `true` | 固定为 `true`；传 `false` 会被拒绝，保证每集都有与行号对应的原文 `content` |
| `callback_url` | string | 否 | - | 任务终态时接收 POST 通知的地址 |
| `metadata` | object | 否 | - | 业务关联字段 |

### 解析模式

| `parse_mode` | 适用输入 | 切分与输出规则 |
|---|---|---|
| `auto` | 文档类型不确定，或混合了标题、场次、章节与大纲 | 依次尝试识别已有集标题、场次剧本、小说章节，最后按大纲结构判断；识别类型在 `detected_type` 返回 |
| `existing_episodes` | 原文已有「第一集」「第 1 集」「EP01」等明确分集标题 | 以已有分集标题和原文边界切分，不重新规划集数、不改写剧情 |
| `screenplay_scenes` | 有场景标记、时间、人物、动作和对白，但没有正式分集标题 | 以场次、冲突推进和转场聚合为剧集；生成连续集号、集标题、单集大纲、冲突与结尾钩子 |
| `novel` | 小说、连载正文、章节体故事 | 以章节、段落、人物目标和剧情节点切分，不把单纯字数作为切分依据 |
| `outline` | 大纲、梗概、分集简介 | 按大纲条目与结构切分 |
| `split_by_ai` | 想要平台自行判断切分点 | 由平台模型决定切分位置 |

### 计费

同上，按 Token 计（输入 2,600 点/百万 Token）。任务查询免费。

---

## 三、客户端调用

```bash
# 看接口与参数
python3 scripts/a7w.py schema file_qa

# 同步问答（默认自动取回结果）
python3 scripts/a7w.py call file_qa chat \
  --body '{"file_urls":["https://你的存储/报告.pdf"],"question":"把全文整理成结构化文本，表格转 Markdown"}'

# 异步解析（拿 task_id）
python3 scripts/a7w.py call file_qa parse \
  --body '{"file_urls":["https://你的存储/剧本.docx"],"parse_mode":"screenplay_scenes"}' --no-wait

# 按 task_id 收结果
python3 scripts/a7w.py task <task_id>
```

---

## 四、注意

- **只吃公网 HTTP(S) 地址**：本地文件先上传到对象存储或任何可公开访问的位置
- **文档里夹着的图片文字**：`file_qa` 主要处理文档文本内容；
  扫描件与图片型 PDF 的取字做法见 `转Markdown指南.md` 的「扫描件怎么办」一节
- **一次最多 8 份文档**：要对比更多份，分几批问
- 平台接口可能调整，动手前先跑 `python3 scripts/a7w.py schema file_qa` 核对
