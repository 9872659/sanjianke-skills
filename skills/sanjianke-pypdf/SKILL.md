---
name: sanjianke-pypdf
slug: sanjianke-pypdf
displayName: 三剪客 · 纯 Python PDF 操作
description: "pypdf：纯 Python PDF 操作 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "pypdf：纯 Python PDF 操作 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - PDF
  - 文档处理
---

# 三剪客 · 纯 Python PDF 操作

一堆 PDF 要合并、拆页、抽文字、加密码、盖水印，但你不想装 Ghostscript、不想调外部二进制、
更不想为了“拆个页”去开商业软件——`pypdf` 就是干这个的：一个纯 Python 的 PDF 读写库，
`pip install` 完就能用，不依赖任何系统级 PDF 组件。

它最常出现在两类场合：一是在 Agent 或脚本里做**批量 PDF 预处理**（合并、按页拆分、
旋转、压缩、去空白页、抽文本喂给后续流程），二是在服务端做**文件收口**
（统一加密码、写元数据、盖水印、去掉敏感批注）。

**上游项目**：`pypdf`　**仓库**：https://github.com/py-pdf/pypdf

## 什么时候用 / 不用

**用它**：

- 用户说「把这几份 PDF 合成一份」「把这个 PDF 按页拆成 20 个文件」「删掉第 3 页」。
- 需要把 PDF 里的文字抽出来做检索、摘要、比对、翻译（文本层是电子版的 PDF）。
- 要给 PDF 加统一密码、统一水印、统一页眉，或者批量清理元数据、删除批注。
- 要读 PDF 的页数、页面尺寸、元数据、表单字段、书签（outline）做文件核验。
- 要在一段 Python 流程里就地处理 PDF，不想引入 subprocess、不想依赖外部 CLI。

**不要用它**：

- PDF 是扫描件 / 图片版，需要 OCR——pypdf 不做 OCR，抽出来是空字符串，
  这种要换成 OCR 链路（PaddleOCR、MinerU 之类）。
- 要做 PDF 转 Word / 转 Markdown / 版面还原——pypdf 只抽扁平文本，
  不还原表格、公式、分栏顺序。
- 要生成排版精良的 PDF（报表、发票、图书）——用 HTML/CSS 排版引擎（WeasyPrint 之类）
  或 LaTeX，pypdf 只能拼装现成页面，不能排版。
- 要保证「所见即所得」的渲染、页面转图片、高清预览——pypdf 不做栅格化，
  需要 PyMuPDF / pdf2image 这类渲染库。
- 要深度编辑已有页面内容（改字、改图、重排段落的原始 PDF）——pypdf 面向页面级
  增删与对象级操作，不适合做内容级重写。

## 安装

```bash
# 基础安装（纯 Python，无外部依赖）
pip install pypdf

# 需要处理 AES 加密/解密的 PDF（加了密码、AES-128/AES-256）时装加密后端
pip install "pypdf[crypto]"

# 抽图片时需要 Pillow
pip install pillow

# 需要命令行工具（pypdf 本身是库，CLI 由同组织的 pdfly 提供）
pip install pdfly
```

其它包管理器（以官方文档为准，命令形式一致）：

```bash
uv add pypdf                 # uv
poetry add pypdf             # Poetry
conda install -c conda-forge pypdf
python -m pip install pypdf  # 系统里 pip 不在 PATH 时用这个
```

官方未提供 Docker 镜像；在容器里就是 `pip install pypdf` 这一条。

## 常用操作

**1. 读页数、页面尺寸、元数据**

```python
from pypdf import PdfReader

reader = PdfReader("example.pdf")
print(len(reader.pages))
print(reader.pages[0].mediabox)          # RectangleObject([0.0, 0.0, 595, 842])
print(reader.metadata)                    # {'/Title': ..., '/Author': ...}
```

**2. 抽文本（逐页抽，自己拼）**

```python
from pypdf import PdfReader

reader = PdfReader("example.pdf")
text = "\n".join(page.extract_text() or "" for page in reader.pages)
print(text[:500])
```

**3. 合并多个 PDF，并按页区间取子集**

```python
from pypdf import PdfWriter

writer = PdfWriter()
writer.append("a.pdf")                    # 整个文件追加
writer.append("b.pdf", (0, 3))            # 只取 b.pdf 的第 0~2 页
writer.merge(position=1, fileobj="c.pdf", pages=(0, 1))  # 插到第 1 页之后
writer.write("out-merged.pdf")
writer.close()
```

**4. 拆页 / 抽单页 / 删页**

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("in.pdf")

# 每页存成一个文件
for i, page in enumerate(reader.pages):
    w = PdfWriter()
    w.add_page(page)
    w.write(f"page-{i + 1:03d}.pdf")

# 删掉第 2 页（索引 1），其余原样导出
w = PdfWriter()
for i, page in enumerate(reader.pages):
    if i != 1:
        w.add_page(page)
w.write("no-page-2.pdf")
```

**5. 旋转页面 + 改元数据 + 加密**

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("in.pdf")
writer = PdfWriter(clone_from=reader)

writer.pages[0].rotate(90)                # 顺时针 90°，负值逆时针
writer.add_metadata({"/Title": "季度报告", "/Author": "运营组"})
writer.encrypt("my-secret-password", algorithm="AES-256")

writer.write("out.pdf")
```

**6. 解密一个已有密码的 PDF**

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("encrypted.pdf")
if reader.is_encrypted:
    reader.decrypt("test")        # 返回非 0 表示成功

writer = PdfWriter(clone_from=reader)
writer.write("decrypted.pdf")
```

**7. 压缩体积、去掉批注**

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("big.pdf")
writer = PdfWriter(clone_from=reader)
writer.compress_identical_objects()          # 合并重复对象
writer.remove_annotations("/Text")           # 去掉指定类型的批注（'/Text'、'/Link'、'/Widget'…）
writer.write("small.pdf")
```

**8. 命令行（走 pdfly，不是 pypdf 自带）**

```bash
pip install -U pdfly
pdfly extract-text in.pdf              # 抽文本到终端
pdfly cat a.pdf b.pdf -o out.pdf       # 按页抽取拼接成一份 PDF
pdfly compress in.pdf out.pdf          # 压缩体积
pdfly rotate -o rotated.pdf in.pdf 90 :3   # 前 3 页转 90°（页码索引从 0 开始）
pdfly meta in.pdf --output json        # 看元数据（默认 text）
pdfly --help                           # 全部 17 个子命令以 pdfly 当前版本为准
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `extract_text()` 返回 `''` 或全空白 | 该 PDF 没有文本层（扫描件 / 图片版），或用了自定义编码字体 | 先确认页面上能不能选中文字；不能就转 OCR 链路，别在 pypdf 上耗 |
| 抽出的中文是乱码或方块 | 字体缺少 ToUnicode 映射表 | 换别的样本验证；这种情况 pypdf 能做的有限，需要 OCR 或原始文档 |
| 抽出的文字顺序全乱 | 多栏排版、文本框，PDF 里没有「阅读顺序」概念，pypdf 按内容流顺序返回 | 版面复杂的文档改用版面分析类工具（先把每栏裁出来再抽） |
| 合并大文件时 `RecursionError` | 对象克隆递归过深 | `import sys; sys.setrecursionlimit(sys.getrecursionlimit() * 5)`，或分批合并 |
| 加了密码的文件打不开 | 不传 `algorithm` 时 pypdf 默认用 RC4（兼容性优先，但不安全） | 显式写 `writer.encrypt(pw, algorithm="AES-256")`；官方推荐 `AES-256-R5` |
| AES PDF 报缺少加密库 | AES 依赖外部加密后端，不在基础安装里 | `pip install "pypdf[crypto]"` |
| 合并后页面方向不对 | 源页面带 `/Rotate` 旋转标记，合并时被保留，再叠加水印就歪了 | 合并前对每页调 `page.transfer_rotation_to_content()` |
| 同样一页被合并进来两次，改一页两页都变 | 同一个源对象被复用，cloning 会命中缓存 | 调 `writer.reset_translation(reader)` 重置克隆映射 |
| 从旧代码迁过来大量报错 | `PyPDF2` 在 3.0 起停止维护，pypdf 是它的正式后继，API 有变 | 装 `pypdf` 而不是 `PyPDF2`，按官方 migration 指南改导入名 |
| 抽出来的图片文件名很怪 / 覆盖了 | PDF 内部资源名可含任意字符且不保证唯一 | 自己重命名（如 `f"out-{i}.png"`），不要直接用 `image_file_object.name` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 运行期不需要联网；只有 `pip install` 装包时联网 |
| 读取文件 | 是 | 读取待处理的 PDF（`PdfReader("in.pdf")`） |
| 写入文件 | 是 | 写出合并 / 拆分 / 加密后的 PDF；**注意会覆盖同名文件** |
| 凭证 | 否 | 不涉及任何 API Key；PDF 密码是用户当场提供的入参，不要写进代码或日志 |
| 子进程 / 后台常驻 | 否 | 纯库调用，不启子进程、不常驻 |

## 触发场景

- 「把 `a.pdf`、`b.pdf`、`c.pdf` 合成一个文件」
- 「这个 PDF 有 80 页，按页拆开，或者只要第 5 到第 12 页」
- 「帮我把这个 PDF 的文字提取出来」
- 「给这些 PDF 统一加上密码 `xxxx`」
- 「读一下这个 PDF 有多少页、标题是什么」
- 「这份 PDF 里有些批注 / 元数据要清掉再发出去」

## 能力边界

**覆盖**：

- 页面级操作：合并、拆分、抽取页区间、插入、删除、旋转、缩放、裁切（crop）、页面叠加水印
- 文本与元数据：逐页抽文本、读/写文档信息（`/Title`、`/Author` 等）、读书签与表单字段
- 安全相关：读加密 PDF、写密码保护（RC4 / AES 系列算法）、去除批注
- 对象级：合并重复对象压缩体积、克隆控制、低级 PDF 对象（`pypdf.generic`）访问
- 附件、批注、outline 的读取与基础写入

**不覆盖**：

- OCR（不做图像识别，扫描件抽不出文字）
- 渲染 / 栅格化（不把 PDF 转成图片，也不做预览）
- 版面分析与结构化还原（不还原表格、公式、分栏阅读顺序）
- 内容级编辑（不能改页面里已有的文字、图片，只能换页）
- 排版生成（不能从零设计版式；要生成排版精良的 PDF 请用 HTML/CSS 或 LaTeX 方案）
- 图片格式的深度处理（只做提取，转码依赖 Pillow）

## 依赖条件

- Python 3.9 及以上（官方包声明支持当前主流 3.x 版本，具体下限以 PyPI 页面的 Requires-Python 为准）
- 纯 Python 实现，**不需要** Poppler、Ghostscript、Java 等外部组件
- 抽图片需额外装 `Pillow`；处理 AES 加密的 PDF 需 `pypdf[crypto]`
- 不需要账号、不需要 API Key、不需要网络（安装阶段除外）

## 已知限制

1. 文本抽取质量完全取决于源 PDF 有没有文本层；扫描件、纯图片 PDF 结果为空。
2. 复杂版式（多栏、表格、公式）的文字顺序不可靠，pypdf 不做阅读顺序推断。
3. 加密默认算法是 RC4，不改参数会生成安全强度不足的文件，必须显式指定 AES。
4. 极大文件合并可能触发 Python 递归限制，需要上调 `sys.setrecursionlimit`。
5. 写文件时若目标路径已存在会直接覆盖，没有任何确认或备份机制。
6. `pypdf` 是被维护的库，`PyPDF2` 已停止维护；网上老教程的 `PyPDF2` 写法不能照搬。

## 自检清单

执行前：

- [ ] 确认目标 PDF 有文本层（能选中文字）——没有就改走 OCR
- [ ] 确认源文件已备份，pypdf 写出会覆盖同名文件
- [ ] 确认要用的加密算法（默认 RC4 不安全，显式指定 AES 系列）
- [ ] 需要抽图片时确认已装 `Pillow`，处理 AES 时确认装了 `pypdf[crypto]`

执行后：

- [ ] 核对输出页数是否等于预期（合并 / 拆分 / 删页最容易差一页）
- [ ] 抽样打开输出的 PDF，确认没有空白页、方向正确
- [ ] 加密输出确认密码可解、权限位符合预期
- [ ] 检查是否残留元数据（作者、软件名等敏感信息）
- [ ] 大批量任务统计成功 / 失败文件，不要让个别损坏文件静默吞掉

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/py-pdf/pypdf | 上游仓库（安装与完整文档以它为准） |
| https://pypdf.readthedocs.io/en/stable/ | 官方文档：抽取文本、合并、加解密、图片抽取等专题 |
| https://github.com/py-pdf/pdfly | 配套命令行工具，需要 CLI 时用它 |

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
