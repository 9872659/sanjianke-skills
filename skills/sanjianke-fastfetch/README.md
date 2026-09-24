# 三剪客 · 终端系统信息速览 Skill

fastfetch：终端系统信息速览 的安装、常用命令与避坑要点

---

## 前置条件

- 任意主流系统：Linux、Android、FreeBSD、macOS、Windows 7 或更新。
- 各平台有官方包或预编译二进制，装了就能跑，**不需要账号或 Key**。
- 想改显示效果才需要配置文件；默认开箱即用。
- 图片类图标是否能用，取决于终端支持哪种图片协议，以及这份构建有没有编进对应后端——用 `fastfetch --list-features` 确认。
- 从源码构建需要 CMake 与 C 工具链。

---

## 使用

1. 装：Windows 用 `winget install -e --id Fastfetch-cli.Fastfetch`；macOS / Linux 用 `brew install fastfetch`；其余渠道以上游 README 为准。
2. 先看默认效果：直接敲 `fastfetch`。
3. 裁模块：`fastfetch --list-modules` 抄出模块名，再用 `fastfetch --structure title:os:kernel:memory` 定顺序。
4. 换图标：`fastfetch --list-logos` 挑名字，或 `--logo /path/to/pic.png --logo-type file`。
5. 接脚本：`fastfetch --format json`。
6. 固化配置：调好一串选项后加 `--gen-config` 写入 `~/.config/fastfetch/config.jsonc`；也可 `fastfetch --config neofetch` 用内置预设。
7. 排错：`fastfetch -h <选项名去掉横线>` 查单个选项，`--stat` 看模块耗时，`--show-errors` 打开错误输出。

完整命令、坑位清单与能力边界见 `SKILL.md`。

---

## 依赖

- 运行时无特殊依赖，单文件可执行程序。
- 源码构建依赖：CMake、C 工具链。
- 可选能力依赖（编译期决定）：图片渲染相关后端（如 chafa 之类）、部分平台库；用 `--list-features` 查当前构建实际支持哪些。
- 部分模块会调用系统命令或读取系统数据源，属系统自带能力。
- 不需要任何账号或 Key。

---

## 安全

- 不内嵌任何密钥。
- 默认只在本地采集并打印，不联网、不写盘；`--gen-config` 是唯一会主动写文件的路径（而且会先问你去哪写）。
- `--thread` 与少数需要联网取数的模块会发起网络请求；离线环境请在配置里避开这些模块。
- 配置用了 `$schema` 指向远端 URL 时，编辑器可能去拉取该 JSON Schema；这只是编辑器行为，不影响命令本身。
- 从非官方渠道安装二进制时请自行核对来源；本 Skill 只写文档，不含上游代码。
- Skill 本体只包含文档，不含上游项目的源代码；上游软件本身的问题请走上游仓库的 Issues。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`fastfetch`
- 仓库：https://github.com/fastfetch-cli/fastfetch

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
