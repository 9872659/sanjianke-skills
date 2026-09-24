# 三剪客 · 万能格式转换 Skill

教你用 pandoc 在不同文档格式之间互转：装哪个包、常用命令怎么写、中文 PDF 怎么出、以及哪些东西转换后一定会丢。

---

## 前置条件

- 安装 pandoc 本体即可，它是单一可执行文件，**没有运行时依赖**，也不需要账号或 Key。
- 要输出 PDF，需要额外安装排版引擎（LaTeX 系如 TeX Live / MiKTeX / BasicTeX，或其它 `--pdf-engine` 支持的引擎）。
- 中文 PDF 建议直接用 `--pdf-engine=xelatex` 并指定系统里真实存在的 CJK 字体。
- 用 Lua filter 时注意：官方与 Conda Forge 的静态链接版本**不支持依赖 C 模块的 Lua filter**。
- 多套安装方式并存会出现两个 pandoc，换方式前先卸干净，再用 `pandoc --version` 确认 PATH 命中的是哪一份。

---

## 使用

1. 确认版本与能力：`pandoc --version`、`pandoc --list-input-formats`、`pandoc --list-output-formats`。
2. 普通转换：`pandoc input.md -o output.docx`；要完整独立文档加 `-s`。
3. 从 Word 转 Markdown：`pandoc -s input.docx -t markdown --extract-media=./media -o output.md`。
4. 出 PDF：`pandoc input.md --pdf-engine=xelatex -o output.pdf`，中文再加 `-V CJKmainfont="字体名"`。
5. 批处理与流水线：pandoc 是纯 CLI，直接放进脚本或 CI；需要改 AST 用 `--lua-filter`。
6. 选项与格式名查 `references/options-and-formats.md`。

完整操作步骤、常见坑、能力边界见 `SKILL.md`。

---

## 依赖

- pandoc 本体（官方安装包 / winget / Chocolatey / Homebrew / MacPorts / 发行版仓库 / deb / tarball / Conda / 官方 Docker 镜像）。
- 出 PDF：外部排版引擎。
- 过滤器：Lua filter 用内置 Lua；`--filter` 形式的外部过滤器需要可执行程序（常用 Python）。
- SVG 等图片处理：需要 `rsvg-convert` 之类的外部工具。

---

## 安全

- 不内嵌任何密钥。
- 默认全部在本地完成，不联网；只有输入写成 URL（如 `pandoc -f html https://...`）或文档引用远程资源时才会发起网络请求。
- 不要对来源不明的文档直接使用 `--filter` / `--lua-filter`：过滤器是可执行代码，等同运行第三方程序。
- 转换会在磁盘上写出目标文件与 `--extract-media` 抽出的媒体，注意清理中间产物。
- Skill 本体只包含文档，不含上游项目的源代码；上游代码的问题请走上游仓库的 Issues。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pandoc`
- 仓库：https://github.com/jgm/pandoc

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
