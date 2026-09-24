# 三剪客 · 纯 Python PDF 操作 Skill

pypdf：纯 Python PDF 操作 的安装、常用命令与避坑要点

---

## 前置条件

- Python 3.9 及以上（具体下限以 PyPI 页面 Requires-Python 为准）
- 能执行 `pip install`（安装阶段需要联网，之后运行不需要）
- 纯 Python 实现，**不需要** Poppler / Ghostscript / Java 等外部 PDF 组件

---

## 使用

```bash
pip install pypdf
pip install "pypdf[crypto]"   # 需要处理 AES 加密 PDF 时
pip install pillow            # 需要抽 PDF 内嵌图片时
```

最小可用示例：

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("in.pdf")
print(len(reader.pages), reader.metadata)

writer = PdfWriter()
writer.append("a.pdf")
writer.append("b.pdf", (0, 3))
writer.write("out.pdf")
writer.close()
```

完整的「什么时候用 / 不用、安装、常用操作、常见坑、能力边界」见 `SKILL.md`。

---

## 依赖

| 依赖 | 是否必须 | 用途 |
|---|---|---|
| Python 3.9+ | 必须 | 运行环境 |
| `pypdf` | 必须 | 核心库 |
| `cryptography` 或 `pycryptodome`（`pypdf[crypto]`） | 按需 | AES 加密 / 解密 |
| `Pillow` | 按需 | 抽取 PDF 内嵌图片并保存 |
| `pdfly` | 可选 | 需要命令行时使用；pypdf 本身只提供库 API |

---

## 安全

- 不内嵌任何密钥
- PDF 密码由调用方临时传入，不要硬编码进脚本、不要写进日志或提交到仓库
- 写出操作会**直接覆盖**同名文件，批量处理前先备份源文件
- 加密时显式指定 AES 算法；省略 `algorithm` 时默认用 RC4，安全强度不足
- 处理来源不可信的 PDF 时注意资源上限（官方提供 `maximum_declared_stream_length` 等配置项）

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pypdf`
- 仓库：https://github.com/py-pdf/pypdf

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
