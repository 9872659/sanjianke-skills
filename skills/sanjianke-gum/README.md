# 三剪客 · Shell 脚本交互组件 Skill

gum：Shell 脚本交互组件 的安装、常用命令与避坑要点

---

## 前置条件

- 一个**交互式终端**。这是硬条件：CI、cron、被管道驱动的场景里交互子命令用不了。
- 建议用较新的终端（支持 ANSI 真彩色与常见边框字符），否则样式会退化。
- 装一个二进制即可，不需要账号、Key 或登录。
- 若脚本要在多台机器上跑，注意各机器装的版本可能不同；gum 有 v1 与 v2 两条模块线，参数会随版本变化，用前用 `gum <子命令> --help` 核对。

---

## 使用

1. 装：`brew install gum`（macOS / Linux）、`pacman -S gum`（Arch）、`winget install charmbracelet.gum`（Windows）、或按官方 apt / yum 源说明安装。
2. 确认：`gum --version`，再 `gum --help` 看子命令清单。
3. 最短跑通：`NAME=$(gum input --placeholder "你的名字")`，把结果接进变量。
4. 常用四件套：`gum choose` 选一个、`gum input` 收输入、`gum confirm` 做确认（看退出码）、`gum spin` 包长命令。
5. 美化：`gum style` 加边框颜色，`gum format` 渲染 Markdown / 代码 / emoji，`gum pager` 分页。
6. 定制：命令行参数优先，其次 `GUM_<子命令>_<参数>` 形式的环境变量；参数名一律以 `gum <子命令> --help` 为准。

完整参数表、坑位清单与能力边界见 `SKILL.md`。

---

## 依赖

- 运行期：无第三方运行时依赖，单个二进制。
- 用 Go 安装时：需要 Go 环境。
- 交互要求：调用方的 stdin / stdout 需为 TTY；`gum spin` 包的子命令由你自己提供。
- 样式表现取决于终端能力（颜色深度、流式字符支持）。
- 不需要任何账号或 Key。

---

## 安全

- 不内嵌任何密钥。
- 运行期不联网：不发起任何外部请求，不会上传输入内容。
- `gum input --password` **只是不回显输入**，不做加密、不做安全存储；需要保密的内容请由你自己的流程处理，不要把敏感值留在 shell 历史或日志里。
- `gum spin` 会以你的当前权限运行它包装的命令，因此不要用它去包来路不明的命令串。
- `gum file` 只做选择，不会修改文件；`gum table` 只读取你给的数据文件。
- 从非官方渠道安装二进制时请自行核对来源；本 Skill 只写文档，不含上游代码。
- Skill 本体只包含文档，不含上游项目的源代码；上游软件本身的问题请走上游仓库的 Issues。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`gum`
- 仓库：https://github.com/charmbracelet/gum

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
