# 三剪客 · PDF 表格抽取 Skill

tabula：PDF 表格抽取的安装、常用命令与避坑要点

---

## 前置条件

- 本机已安装 Java 运行时（Java 8+），`java -version` 能正常输出。
- 用 Python 时：已 `pip install tabula-py`（Python 3.9+）。
- 用命令行时：已下载带依赖的 tabula-java jar，或自行用 Maven 构建。
- 目标 PDF **有文字层**；扫描件需先做 OCR。

---

## 使用

把本目录作为 Skill 交给 Agent，Agent 会按 `SKILL.md` 中的示例选择路线与参数。
常见任务：

- 单份 PDF 抽表并导出 CSV / Excel 可读格式；
- 批量目录转换；
- 指定页范围、区域、列边界；
- 在 lattice / stream 两种模式之间做取舍；
- 用 Tabula App 模板固定抽取口径。

---

## 依赖

- **Java 运行时 8+**（两条路线都必须）。
- Python 路线：`tabula-py`（自带 pandas、numpy）。
- 选装：`jpype`（`pip install tabula-py[jpype]`）以获得更快执行。
- Java 路线：JRE 跑 jar；从源码构建需要 JDK 与 Maven。
- 无账号、无 API Key。

---

## 安全

- 不内嵌任何密钥
- 输入的 PDF 与抽出的表格都可能含敏感数据，注意落盘位置与权限。
- 加密文档的打开密码通过参数传入，不要写进脚本文件或提交进仓库。
- 只处理你有权处理的文档；批量转换会遍历输入目录，先确认目录范围。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`tabula`
- 仓库：https://github.com/tabulapdf/tabula-java

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
