# 三剪客 · PDF 文本布局解析 Skill

用 pdfminer.six 从 PDF 里取出文字，以及每个字符的坐标、字号与字体；纯 Python、离线、不改原文件。

---

## 前置条件

- Python 3.10 或更新版本，且 `pip` 可用
- 待解析的 PDF 是**有文本层**的文档；扫描件与图片版 PDF 不适用
- 需要抽取内嵌图片时，额外安装 `pdfminer.six[image]`
- 加密 PDF 需自备打开密码

---

## 使用

装好之后，命令行与 Python 两条路都能走：

```bash
pip install pdfminer.six
pdf2txt.py -o out.txt input.pdf           # 抽全篇文本
pdf2txt.py --page-numbers 1 3 5 input.pdf # 只抽指定页
pdf2txt.py input.pdf --output-dir images  # 抽内嵌图片（需 [image] 依赖）
```

Python 里最小用法：

```python
from pdfminer.high_level import extract_text
print(extract_text("input.pdf"))
```

`SKILL.md` 里有完整的参数说明、`LAParams` 调参思路与避坑表。

---

## 依赖

- 运行依赖：`pdfminer.six`（会自动带上 `charset-normalizer`、`cryptography` 等依赖）
- 抽图可选依赖：`pdfminer.six[image]`（Pillow 等）
- 不需要 poppler、Ghostscript、Java 等任何外部二进制
- 不需要账号、Key 或任何在线服务

---

## 安全

- 不内嵌任何密钥
- 解析全程本地离线进行，PDF 内容不会外传
- 加密 PDF 的密码只在本机命令行/Python 调用中传递，不要写进脚本、日志或提交到仓库
- 不修改源 PDF：只读解析，输出写到独立文件或标准输出

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pdfminer.six`
- 仓库：https://github.com/pdfminer/pdfminer.six

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
