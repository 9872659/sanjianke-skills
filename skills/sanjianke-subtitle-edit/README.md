# 三剪客 · 字幕编辑与时间轴校对工具 Skill

Subtitle Edit：字幕编辑与时间轴校对工具 的安装、常用命令与避坑要点

---

## 前置条件

- **系统版本**（上游 README 要求先确认这一项）：
  - Windows：Windows 10 22H2（build 19045）或更新，且打全系统更新；更老的 Win10 版本可能以 .NET 运行时错误启动失败
  - macOS：macOS 12（Monterey）起，官方推荐 macOS 14（Sonoma）或更新
  - Linux：Flatpak 包最省事（自带 mpv 与 ffmpeg）；原生包需自行安装 mpv 与 ffmpeg
- 上游说明发布的构建是自包含的，**不需要另外安装 .NET**；但只单独使用命令行转换器 `seconv` 时仍需要 .NET 运行时
- 图形界面的播放与波形依赖 libmpv（推荐）或 VLC，波形与音频提取需要 ffmpeg
- 要做在线翻译 / 在线 OCR / 云端语音识别时，先申请好对应的 Key（Google 语音识别 v2 需要服务账号 JSON 密钥文件，不接受普通 API Key）
- 批量任务与 OCR 前，先备份原始字幕文件

---

## 使用

这个 Skill 教 Agent 做四件事：

1. **判断该不该用**——只改一条 srt 用文本编辑器就行；要剪片子请换剪辑工具，这不是它的活
2. **分清两条路**：桌面上用图形界面（波形对轴、OCR 导入、批量转换菜单）；服务器和脚本里用 `seconv` 无头命令行
3. **命令行怎么下笔**——先 `seconv --version` / `formats` / `list-ocr-engines` 摸清环境，再按"转格式 → 批量 → 时间轴修正 → 文本清洗 → OCR / 翻译"的顺序用参数
4. **避开典型坑**——`seconv --settings` 与图形界面配置不是同一套 schema；`seconv` 不会自动下载引擎与 OCR 数据库；在线引擎的数据外发与 Key 依赖

典型请求：

- "把这些 srt 批量转成 vtt"
- "字幕时间轴整体偏了，帮我修"
- "内嵌图形字幕要扒成文本"
- "给这批字幕加英文，保留时间轴"
- "服务器上没有桌面，只要命令行转格式"
- "从视频直接生成字幕"

具体命令见 `SKILL.md` 的「安装」「常用操作」「常见坑」三节。所有命令、文件名与参数取自上游仓库 README、官方文档站与 Releases 页面；**下载请以仓库 Releases 为准**（上游官网页面的下载内容是脚本渲染的，抓不到可读文本）。

---

## 依赖

- 本工具本体：从仓库 Releases 按平台下载安装包（Windows x64 / ARM64、macOS x64 / ARM64、Linux x64 / ARM64 与 Flatpak）
- 只跑命令行：Releases 里的 `SeConv-*` 独立包，或从源码 `dotnet build src/seconv/SeConv.csproj -c Release` 构建
- 播放与音频：libmpv（推荐）或 VLC；ffmpeg（波形与音频提取必需，Flatpak 与 macOS 包里已自带）
- 可选 OCR 引擎：Tesseract、nOCR、BinaryOCR、Ollama、llama.cpp、PaddleOCR，以及若干在线服务
- 可选语音识别引擎：多种本地与在线方案（含 Whisper 系列、本地大模型类引擎）
- 可选翻译引擎：本地（llama.cpp / Ollama / LM Studio / LibreTranslate 等）与在线（多个云服务）
- 账号 / Key：本地功能不需要；在线翻译 / OCR / 语音识别按引擎需要各自的 Key 或服务账号凭据
- 上游 README 与文档中未提供 winget / choco / scoop 安装方式

---

## 安全

- 不内嵌任何密钥：本 Skill 只记录命令与参数，Key 由使用者自行申请与保管
- 上游说明本工具是离线应用：不收集、不存储、不传输你的字幕与媒体内容；本地自动备份也在本机完成
- **但可选的在线功能例外**：使用在线翻译 / 在线 OCR / 云端语音识别时，会把完成该请求所需的最少内容直接发给你选定的服务商，并受该服务商隐私政策约束。涉及未公开素材或敏感内容时请改用本地引擎
- 批量修正类参数（合并、删除、重排、修常见错误）会改动字幕内容，执行前务必备份原件
- 数据目录是平台相关位置；便携版会把数据放在可执行文件旁边，交付或拷贝该目录时注意其中可能含有配置与数据库
- 配置与 OCR 数据库可能包含路径、账号标识等信息，分享截图或目录前先检查

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Subtitle Edit`
- 仓库：https://github.com/SubtitleEdit/subtitleedit

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
