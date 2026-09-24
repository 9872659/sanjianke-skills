# 三剪客 · 超轻量中文 OCR（命令行 + Web 服务） Skill

本地就能跑的中文 OCR：装法、命令行识别、网页服务启动、模型文件分布、多端集成路线，以及效果不对时该先调什么。

---

## 前置条件

- 一个可用的 Python 环境。上游 README 给出的推荐版本是 Python 3.6，实际可跑区间以仓库 `requirements.txt` 为准。
- Windows / Linux / macOS 均可，**纯 CPU 推理，不需要显卡，也不需要 CUDA**。
- 仓库自带的三个 ONNX 推理模型要在位：文字检测 `dbnet.onnx`、文字识别 `crnn_lite_lstm.onnx`、方向分类 `angle_net.onnx`（都在 `models/` 下）。
- 输入必须是**图片**（截图、扫描页、照片）。如果要处理 PDF，请先用别的工具把页面渲染成 PNG/JPG。
- 不需要账号、Token 或 API Key，也没有调用额度。
- 走 C++ / JVM / Android / .NET 集成时，额外需要对应语言的工具链与推理运行时。

---

## 使用

1. 按 `SKILL.md` 的「安装」一节装依赖；要当命令行工具用就 `pip install -e .`，让 `models/*.onnx` 一起进包。
2. 单张识别：`chineseocr <图片>` 直接打印 JSON（全文 + 文本块 + 置信度 + 四点框 + 耗时）；要落盘加 `--output`，要可视化加 `--draw`。
3. 大图先加 `--compress` 把检测短边压小，这是 CPU 上最有效的提速手段。
4. 给人用时起 `python backend/main.py`，浏览器打开终端打印的 `ip:8089` 地址上传图片。
5. 需要对段落、阅读顺序做还原时，用输出里的 `box` 坐标自己聚类重排，不要把 `blocks` 的顺序当阅读顺序。
6. 完整参数、示例与排错对照见 `SKILL.md`；参数名随版本会变，执行前用 `--help` 或仓库 README 核对。

---

## 依赖

- 上游仓库：https://github.com/DayBreak-u/chineseocr_lite
- Python 依赖：仓库 `requirements.txt`（推理运行时、数值计算、图像处理、Web 服务框架，以文件当前内容为准）。
- 推理模型：仓库 `models/` 下的 ONNX 文件；另有一份 `models_ncnn/` 仅供 NCNN 端侧示例使用，不是 CLI 必需资源。
- Web 服务：由仓库 `backend/` 提供，默认监听 8089 端口。
- 多端集成：C++（ONNX Runtime / NCNN / MNN）、JVM（JNI 封装）、Android、.NET 各自的工具链与运行时。
- 不依赖任何外部云服务或付费接口。

---

## 安全

- 不内嵌任何密钥；本 Skill 不需要账号或 API Key。
- 识别全程本地完成，图片不出机器，这正是它相对云端 OCR 的主要优势；仅在安装依赖与拉取仓库时需要联网。
- 网页服务会监听端口并接收上传文件：对外提供前请确认绑定地址、防火墙规则与访问范围，不要把内网服务无意中暴露到公网。
- 建议给上传目录设定期清理，避免历史图片长期滞留。
- 识别结果常含个人信息（证件、票据、联系方式）：按实际合规要求处理，不要随手外传或入库。
- 不要把训练权重、wheel 包、构建产物直接提交进 Git；大文件走 Releases、对象存储或 Git LFS。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`chineseocr_lite`
- 仓库：https://github.com/DayBreak-u/chineseocr_lite

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
