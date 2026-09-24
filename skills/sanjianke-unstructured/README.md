# 三剪客 · 多格式文档解析 Skill

unstructured：多格式文档解析 的安装、常用命令与避坑要点

---

## 前置条件

- Python 环境，能 `pip install`
- 按要解析的格式装 extras：`unstructured[all-docs]` 全装，或 `unstructured[docx,pptx]` 这样按需装
- 系统级依赖（pip 装不了，缺一个对应格式就报错）：
  - `libmagic-dev`（文件类型探测）
  - `poppler-utils`（PDF 与图片）
  - `tesseract-ocr`（OCR；多语言再装 `tesseract-lang`）
  - `libreoffice`（MS Office 文档）
  - `pandoc` 无需系统安装，已由 `pypandoc-binary` 打包
- 不想装系统依赖：用官方容器
  `docker pull downloads.unstructured.io/unstructured-io/unstructured:latest`
- 合规敏感环境：导入前设 `DO_NOT_TRACK` 或 `SCARF_NO_ANALYTICS`（非空值）关掉默认匿名统计

---

## 使用

主入口是分区函数，进去是文件，出来是一串带类型标签的元素：

```python
from unstructured.partition.auto import partition
elements = partition(filename="example.pdf")
print("\n\n".join(str(el) for el in elements))
```

| 目标 | 入口 |
|---|---|
| 不确定格式 | `from unstructured.partition.auto import partition` |
| 指定格式 | `unstructured.partition.pdf` / `.docx` / `.pptx` / `.xlsx` / `.html` / `.md` / `.email` / `.image` … |
| PDF 要表格/版面 | `partition_pdf(..., strategy="hi_res", infer_table_structure=True)` |
| 扫描件 OCR | `strategy="ocr_only"` 或 `hi_res`，并用 `languages=[...]` 指定语言 |
| 切成 RAG 的块 | `chunk_by_title(elements, max_characters=1500)`，或分区时传 `chunking_strategy="by_title"` |
| 存/读结果 | `elements_to_json` / `elements_from_json`（`unstructured.staging.base`） |

完整参数、元素字段与常见坑见 `SKILL.md` 和 `references/` 下两份速查。

---

## 依赖

- `unstructured` 及其 extras（视文档类型而定）
- 系统工具：poppler、tesseract、libreoffice、libmagic
- hi_res 路线会用到随 extras 安装的推理依赖，CPU 可跑但慢
- 本地开发用 `uv` + `make`（`make install` / `uv sync --extra pdf`）

---

## 安全

- 不内嵌任何密钥
- 库默认发送匿名使用统计（不含文档内容与文件名），用 `DO_NOT_TRACK` 或
  `SCARF_NO_ANALYTICS` 任意非空值即可完全关闭
- 本地解析不联网、不上传文档；只有 `url=` 形式或托管 API 才走外网
- 解析不可信来源的文档时，注意调用系统工具（poppler/tesseract/libreoffice）的已知风险，
  建议在容器里跑并限制资源
- 开源版本地解析不需要任何账号或 Key；若改用托管服务，密钥不要写进代码库

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`unstructured`
- 仓库：https://github.com/Unstructured-IO/unstructured

---

## 许可证

MIT，见 `LICENSE.md`。

---

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
