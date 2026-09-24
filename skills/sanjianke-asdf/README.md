# 三剪客 · 多语言运行时版本管理 Skill

asdf：多语言运行时版本管理 的安装、常用命令与避坑要点

---

## 前置条件

- 目标环境是 **Linux 或 macOS**。Windows 请走 **WSL**，不要指望在纯 Windows 原生环境下顺畅使用。
- 本体依赖 `git`，官方建议同时准备 `bash`。用 `go install` 方式装需要 Go，从源码构建需要 `make`。
- 需要把 `~/.asdf/shims`（或 `$ASDF_DATA_DIR/shims`）加进 `PATH`，这一步不做的话装了也不生效。
- 每个插件有**自己的**系统依赖，装之前先看该插件仓库列的清单。
- 不需要账号、Key 或登录。

---

## 使用

1. 装本体：`brew install asdf`（Homebrew），或下载预编译二进制放进 `PATH`，或 `go install github.com/asdf-vm/asdf/cmd/asdf@v0.20.0`。
2. 配 shell：把 `export PATH="${ASDF_DATA_DIR:-$HOME/.asdf}/shims:$PATH"` 写进对应启动文件（Bash 用 `~/.bash_profile`，ZSH 用 `~/.zshrc`，POSIX sh 用 `~/.profile`），Fish / Nushell / PowerShell Core 用官方文档给的片段。重启 shell。
3. 加插件：`asdf plugin add nodejs https://github.com/asdf-vm/asdf-nodejs.git`。
4. 装版本：`asdf list all nodejs` 看可选项，再 `asdf install nodejs latest`。
5. 定版本：在项目目录里 `asdf set nodejs 20.11.1`，会生成当前目录的 `.tool-versions`，把它提交进 Git。
6. 核对：`asdf current` 看解析结果，`asdf which node` 看实际命中路径。
7. 排错第一步固定跑 `asdf info`。

完整操作、坑位清单与能力边界见 `SKILL.md`；命令全集见 <https://asdf-vm.com/manage/commands.html>。

---

## 依赖

- 运行时依赖：`git`；官方建议 `bash`。
- 可选依赖：`bash-completion`（用 Bash 补全时）；Go（用 `go install` 装时）；`make` 与 C 工具链（从源码构建时）。
- 插件级依赖：由各插件自行声明，常见有 `curl`、`gawk`、`gpg`、编译器等 —— 不在本 Skill 的依赖范围内。
- 不需要任何账号或 Key。

---

## 安全

- 不内嵌任何密钥。
- 安装阶段会联网：从插件仓库拉插件、从各工具官方渠道下载运行时；命令补全脚本会写入 shell 的补全目录。
- **插件是可执行代码**：`asdf plugin add <name>` 等同于引入一份第三方脚本，它会在你的用户权限下运行。只添加能确认来源的插件，不要照抄来路不明的插件地址。
- 版本安装会写入数据目录（默认 `~/.asdf`）并在其中执行插件的安装脚本；把 `ASDF_DATA_DIR` 指到共享或不受控目录前请先想清楚权限。
- `.tool-versions` 是纯文本配置，但它决定你执行的是哪个二进制；改动它等于改动后续所有命令的运行时来源，提交进仓库前先确认内容。
- Skill 本体只包含文档，不含上游项目的源代码；上游软件本身的问题请走上游仓库的 Issues。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`asdf`
- 仓库：https://github.com/asdf-vm/asdf

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
