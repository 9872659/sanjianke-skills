# 分块、元素与序列化

## 为什么它的分块和别家不一样

常见做法是先抽纯文本，再按 `"\n\n"` 之类的字符切；这个库是**先分区成语义元素，再合并成块**。
所以除了「单个元素本身就超长」这一种情况，块里装的都是完整元素，不会把一句话从中间劈开。
分块出来的东西只有三种：`CompositeElement`、`Table`、`TableChunk`。

## 分块参数

| 参数 | 默认 | 含义 |
|---|---|---|
| `max_characters` | 500 | 硬上限，任何块都不会超过；单个超长元素会被文本切分 |
| `new_after_n_chars` | 等于 `max_characters` | 软上限，块一旦超过它就不再并入下一个元素 |
| `overlap` | 0 | 仅在因超长而做文本切分时，从前一块尾部借这些字符做前缀 |
| `overlap_all` | False | 普通块之间也做重叠；会「污染」本来边界干净的块，慎用 |

想要「块大概 1000 字，实在不行到 1500」这种效果：
`max_characters=1500, new_after_n_chars=1000`。

## 两种分块策略

- `basic`：只按上面的长度参数拼块，不看标题结构。
- `by_title`：按标题元素切分章节，在同一章节内再按长度拼块；对有大纲的文档效果明显更好，
  对纯散文会退化。

两种调用方式：

```python
# 1) 分区时一步到位
from unstructured.partition.html import partition_html
chunks = partition_html(url=url, chunking_strategy="basic")   # 或 "by_title"

# 2) 先分区再分块（推荐：调参数时反馈更快，分区往往是最慢的一步）
from unstructured.chunking.basic import chunk_elements
from unstructured.chunking.title import chunk_by_title

chunks = chunk_elements(elements, max_characters=1200, overlap=100)
chunks = chunk_by_title(elements, max_characters=1500, new_after_n_chars=1000)
```

## 元素

每个元素有两个关键属性：

- `category`：元素类型标签（字符串）
- `metadata`：元数据对象；还有 `text` / `str(el)` 拿文本，`el.to_dict()` 拿字典

常见 `category` 取值：`Title`、`NarrativeText`、`ListItem`、`Table`、`Image`、
`FigureCaption`、`Header`、`Footer`、`PageBreak`、`Formula`、`CodeSnippet`、
`Address`、`EmailAddress`、`UncategorizedText`。
完整类在 `unstructured.documents.elements` 里，可以直接 `isinstance` 判断：

```python
from unstructured.documents.elements import NarrativeText, Title, Table

titles = [el for el in elements if isinstance(el, Title)]
body = [el for el in elements if isinstance(el, NarrativeText)]
```

## 元数据

`el.metadata` 里常见的字段（随格式与策略不同，缺失即该格式不提供）：

| 字段 | 说明 |
|---|---|
| `filename` / `file_directory` / `filetype` | 来源文件信息 |
| `page_number` | 页码（PDF、PPT 等有分页概念时） |
| `coordinates` | 坐标信息（含版面宽高），hi_res 路线下才有 |
| `text_as_html` | 表格元素的 HTML 表示（需要开表格结构推断） |
| `languages` | 探测到的语言 |

用之前先 `print(el.metadata.to_dict().keys())` 看看实际有哪些，
不要假定某个字段一定存在。

## 序列化与还原

```python
from unstructured.staging.base import elements_to_json, elements_from_json

# 存
elements_to_json(elements, filename="elements.json")
# 或者自己处理： [el.to_dict() for el in elements]

# 读回（JSON 里保留了元素类型，还原后 isinstance 判断依旧有效）
restored = elements_from_json(filename="elements.json")
```

写进向量库前的常见加工：

```python
docs = []
for el in chunks:
    if not str(el).strip():
        continue
    docs.append({
        "text": str(el),
        "category": el.category,
        "page": getattr(el.metadata, "page_number", None),
        "source": getattr(el.metadata, "filename", None),
    })
```

## 输出质量自查

- 元素类型分布是否合理：全是 `UncategorizedText` 说明解析没识别出结构
- 有没有整页空白：扫描件走了 `fast` 就会这样
- 表格元素是否带 `text_as_html`
- 分块后块长分布：大量贴到 `max_characters` 说明元素太长，考虑先调分区策略；
  大量十几字的块说明元素切得太碎
- 页码是否连续：缺页往往意味着解析中途失败
