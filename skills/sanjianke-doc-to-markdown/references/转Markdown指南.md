# 文档转 Markdown 指南

本文只说**怎么转得干净、怎么进知识库**。接口参数看 `api-file_qa.md`，
计费口径看 `通用说明.md`。

---

## 一、转换前先想清三件事

| 要想清 | 为什么 | 怎么定 |
|---|---|---|
| **给谁看** | 给人看的要保留措辞，给模型看的可以压 | 入库/喂模型 → 保留结构、可压缩正文；归档留存 → 原文照搬 |
| **结构多重要** | 标题层级决定后面怎么切片 | 要切片就必须保留 `#` / `##` 层级 |
| **表格要不要** | 表格最容易被压散 | 有表格就明确要求转 Markdown 表格 |

---

## 二、指令模板（直接抄）

**1）全文文字化 · 保留结构（最常用）**

```
把全文整理成结构化 Markdown：
- 保留标题层级（用 # / ## / ###）
- 保留有序与无序列表
- 表格统一转成 Markdown 表格，列名原样保留
- 保留超链接的锚文本与地址
不要概括、不要漏段、不要改写措辞。
```

**2）大纲化 · 只要主干**

```
输出 Markdown 大纲：只保留标题层级与每节 2～3 句要点，删掉例子、脚注与附录。
```

**3）表格优先**

```
把文档里所有表格转成 Markdown 表格，列名原样保留，空单元格留空。
表格之外的正文只保留表题与所在章节标题。
```

**4）多份合并**

```
把这几份文档合并成一份 Markdown：按主题分节，重复内容去重，
每节末尾用 > 引用标注内容来自哪一份文档。
```

**5）按章节拆文件**

```
按顶层章节拆成多个 Markdown 文件，每个文件以 `# 章节标题` 开头，
文件之间用相对链接互相引用。
```

---

## 三、转换质量检查清单

拿到 Markdown 后，本地过一遍这几条再入库：

- [ ] 标题从 `#` 开始，层级连续（没有从 `#` 直接跳到 `###`）
- [ ] 表格管道符 `|` 成对，分隔行 `|---|---|` 存在
- [ ] 列表缩进一致（同级列表缩进相同）
- [ ] 没有残留的页眉页脚、页码、「第 X 页 共 Y 页」
- [ ] 没有整段空白或明显截断
- [ ] 中英文标点没有被误替换
- [ ] 文件非空，且长度在原文档的合理比例内

> **页眉页脚与页码**是最常见的噪音。指令里加一句
> 「去掉页眉、页脚与页码」能省掉大量后期清理。

---

## 四、批量转换

```python
import json, os, time, urllib.request

API = "https://api.a7w.cn/api/v1/apps/file_qa/chat"
KEY = os.environ["A7W_API_KEY"]
PROMPT = ("把全文整理成结构化 Markdown：保留标题层级、有序与无序列表、"
          "表格转 Markdown 表格，去掉页眉页脚与页码，不要概括、不要漏段。")


def conv(url, retries=3):
    body = {"file_urls": [url], "question": PROMPT}
    for i in range(retries):
        try:
            req = urllib.request.Request(
                API, data=json.dumps(body).encode(), method="POST",
                headers={"Authorization": "Bearer " + KEY,
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
            return d["data"]["result"]["answer"]
        except Exception as e:                      # 网络抖动退避重试
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


os.makedirs("md", exist_ok=True)
with open("urls.txt", encoding="utf-8") as f:
    for n, url in enumerate((l.strip() for l in f if l.strip()), 1):
        url = url.strip()
        text = conv(url)
        name = "md/%03d.md" % n
        with open(name, "w", encoding="utf-8") as out:
            out.write(text)
        print(n, name, len(text))
```

**并发建议**：文档转换是重 Token 操作，建议 **2～4 路并发**起步，
跑稳了再加。一次并发太多既容易触发排队上限，也不省时间。

**超长文档**：先按章节拆成几份分别转，再本地拼接 ——
比一次塞一整本快，也更省钱。

---

## 五、扫描件（图片型 PDF）怎么办

扫描件里的文字是「画上去的」，走视觉大模型那条路：

1. 用本地工具把 PDF 每页导成图片（`pdftoppm` / 各类 PDF 工具的导出图片功能）
2. 每张图调 `POST /api/v1/chat/completions`，用视觉模型提取文字
3. 把各页文本拼起来，再让模型统一整理成 Markdown

```bash
# 第 2 步的调用形态
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"PaddleOCR-VL-1.5","messages":[{"role":"user","content":[
        {"type":"text","text":"提取本页全部文字，保留标题层级与列表，表格转 Markdown 表格，去掉页眉页脚与页码"},
        {"type":"image_url","image_url":{"url":"https://你的存储/page-01.png"}}]}]}'
```

---

## 六、进知识库之前

| 动作 | 要点 |
|---|---|
| **切片** | 优先按标题层级切；没有层级再按固定长度切，留 10%～15% 重叠 |
| **加元数据** | 每片带上来源文件名、章节路径、更新时间，检索时能溯源 |
| **去重** | 多份文档合并后先做一次近似去重，避免同段落反复入库 |
| **保留原文** | 同时存一份原始 Markdown，切片只是索引，别只留切片 |

---

## 七、常见问题快查

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 拿回一篇摘要 | 没写「不要概括」 | 指令里明确「保留原文、不要概括、不要漏段」 |
| 表格散架 | 没要求转 Markdown 表格 | 点名「表格转 Markdown 表格，列名原样保留」 |
| 正文里混着页码 | 没要求去页眉页脚 | 加一句「去掉页眉、页脚与页码」 |
| 报参数错误 | 用了本地路径 / 超过 8 份 | 换公网直链，或分批调用 |
| 等了很久没返回 | 文档太长走了同步 | `mode` 传 `async`，拿 `task_id` 再查 |
| 中英文标点变了 | 模型顺手规范化 | 指令里加「标点原样保留，不要规范化」 |
