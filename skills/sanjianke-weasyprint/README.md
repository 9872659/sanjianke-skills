# 三剪客 · HTML/CSS 转 PDF Skill

WeasyPrint：HTML/CSS 转 PDF 的安装、常用命令与避坑要点

---

## 前置条件

- Python ≥ 3.10（WeasyPrint 70 的要求）
- 系统库 **Pango ≥ 1.44**（含 HarfBuzz、fontconfig 等）——这是最常见的安装卡点
- 系统里要有覆盖目标语言的字体；输出中文 PDF 必须确认中文字体可用
- 不需要账号或 API Key
- Windows 上优先用官方 releases 的可执行文件；作为 Python 库用需 MSYS2 + Pango

---

## 使用

```bash
# Linux（最省事）
apt install weasyprint

# 或 pip（先确认 pango-view --version ≥ 1.44）
python3 -m venv venv && source venv/bin/activate
pip install weasyprint
weasyprint --info
```

```bash
# HTML → PDF
weasyprint document.html document.pdf

# 纸张与边距走 CSS @page，命令行没有这些参数
weasyprint input.html output.pdf -s <(echo "@page { size: A3 landscape; margin: 3cm }")
```

```python
from weasyprint import HTML, CSS

HTML(string="<h1>标题</h1>").write_pdf("out.pdf")
HTML("report.html").write_pdf("out.pdf", pdf_variant="pdf/a-3u")
```

完整的「什么时候用 / 不用、安装、常用操作、常见坑、能力边界」见 `SKILL.md`。

---

## 依赖

| 依赖 | 是否必须 | 用途 |
|---|---|---|
| Python ≥ 3.10 | 必须 | 运行环境 |
| Pango ≥ 1.44 | 必须 | 文本排版（系统库，pip 装不上） |
| pydyf | 必须 | PDF 写出 |
| tinyhtml5、tinycss2、cssselect2 | 必须 | HTML / CSS 解析 |
| Pyphen | 必须 | 断词连字 |
| Pillow、fontTools | 必须 | 图片与字体处理 |
| CFFI | 必须 | 调用 Pango 等 C 库 |
| 中文字体 | 按需 | 输出中文文档必须有 |
| 社区 Docker 镜像 | 可选 | 容器化（非官方测试路径，建议自建镜像） |

---

## 安全

- 不内嵌任何密钥
- **渲染不可信 HTML/CSS 有明确风险**：可构造死循环、超大值导致 CPU / 内存耗尽，
  可用 `file://` 读本地文件，还能把本地文件作为附件打进 PDF（部分阅读器可执行附件）
- 生产环境务必：降权运行、容器或 `ulimit` 限内存、限渲染时长、截断清洗输入
- 用自定义 URL fetcher 或 `--allowed-protocols` 限制可访问的协议与路径
- 传文件名写出 PDF 时会**静默覆盖**已有文件，注意输出路径

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`WeasyPrint`
- 仓库：https://github.com/Kozea/WeasyPrint

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
