# 三剪客 · 扫描件叠加 OCR 层 Skill

OCRmyPDF：扫描件叠加 OCR 层 的安装、常用命令与避坑要点

---

## 前置条件

- 一个能装系统包的环境（Debian/Ubuntu、Fedora、macOS、Windows+WSL，或直接用 Docker）。
- 识别引擎 Tesseract 4.1.1+ 以及你需要的语言包；PDF 处理侧需要 Ghostscript 9.54+ 或 pypdfium2。
- Python 3.11+（走 pip/pipx/uv 安装时）；官方推荐 3.12+。
- 明确输入是**扫描件 PDF**，且不需要保留数字签名。

---

## 使用

主体是 `SKILL.md`，建议按顺序读：

1. **什么时候用 / 不用** —— 先判断任务是「加文字层」还是「识别图片/抽取表格」，后者不归它。
2. **安装** —— 各平台一条命令、官方 Docker 镜像、Windows 的分步安装，以及 pip 装不出来的外部依赖。
3. **常用操作** —— 基础 OCR、原地替换、指定语言、纠偏去噪、PDF/A 归档、侧车文本、页范围、批量、Python 调用。
4. **常见坑** —— 已有文字层的退出码 6、默认输出类型的版本差异、语言包、内存与并发、体积膨胀、签名与加密。

最短的一次调用：

```bash
ocrmypdf -l chi_sim+eng --deskew input.pdf output.pdf
```

---

## 依赖

- 外部程序（必须由系统包管理器提供）：Tesseract 4.1.1+ 与语言包；Ghostscript 9.54+ 或 pypdfium2；PDF/A 校验用 Ghostscript 9.54+ 或 verapdf；`--clean` 需要 unpaper 6.1+。
- Python 侧：Python 3.11+、fpdf2 2.8+、uharfbuzz；建议安装 fonts-noto 或同类字体。
- 可选：jbig2enc 0.29+、pngquant 2.5+。
- Docker：官方镜像已含上述依赖，服务器上优先用它。

---

## 安全

- 不内嵌任何密钥、Token 或 Cookie。
- 只读写用户指定的文件，中间文件落在系统临时目录，可用 `TMPDIR`（Windows 为 `TEMP`）指到受控位置。
- 不破解、不解密：证书加密的 PDF 直接处理不了；带数字签名的文件默认拒绝修改，需要显式开关才会动它。
- 官方说明该工具**不是**为对抗恶意 PDF 设计的，不要把不可信来源的文件直接丢进生产流程，先隔离环境跑。
- 集成进闭源产品前确认许可证影响：本体为 MPL-2.0，Ghostscript 与镜像内的 Web 服务包装为 AGPLv3。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`OCRmyPDF`
- 仓库：https://github.com/ocrmypdf/OCRmyPDF

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
