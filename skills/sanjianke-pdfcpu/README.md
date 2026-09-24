# 三剪客 · Go PDF 处理 CLI Skill

pdfcpu：Go PDF 处理 CLI 的安装、常用命令与避坑要点

---

## 前置条件

- 本机已安装 `pdfcpu` 可执行文件，并已加入 `PATH`（`pdfcpu version` 能输出）。
- 准备好待处理的 PDF 文件；加密文件需要已知打开密码。
- 加中文水印/戳记时，先安装一个含中文字形的字体。

---

## 使用

把本目录作为 Skill 交给 Agent，或直接对照 `SKILL.md` 操作。典型流程：

1. 先 `pdfcpu validate` 体检，确认文件可用。
2. 按需要执行合并 / 拆分 / 裁剪 / 加注 / 加密。
3. 对输出再做一次 `validate` 与 `info` 复核。

命令与参数以 `pdfcpu --help` 和上游文档为准；本 Skill 记录的是常用路径与已知坑位。

---

## 依赖

- `pdfcpu` 本体（静态可执行，无运行时依赖）。
- 选装：Go 工具链（源码安装方式）、Docker（容器方式）。
- 无 Python / Node / JVM 依赖，无云端账号，无 API Key。

---

## 安全

- 不内嵌任何密钥
- 运行期默认不联网；需要断网可显式加 `--offline`。
- 密码只通过命令行参数或环境变量传入，不要把密码写进脚本文件或提交进仓库。
- 省略 outFile 时 pdfcpu 会就地覆盖输入文件，脚本里务必先备份或显式指定输出路径。
- 只处理你有权处理的 PDF：加密、去签名、改权限都可能涉及合规问题。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pdfcpu`
- 仓库：https://github.com/pdfcpu/pdfcpu

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
