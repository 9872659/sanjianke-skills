# 三剪客 · 跨 Shell 提示符主题引擎 Skill

oh-my-posh：跨 Shell 提示符主题引擎 的安装、常用命令与避坑要点

---

## 前置条件

- 需要联网安装：Windows 走 winget，macOS 走 Homebrew，Linux 走官方安装脚本。
- Linux 安装脚本要求系统已有 `curl`、`unzip`、`realpath`、`dirname`，并建议先把 `curl` 与证书库更新到最新。
- **需要 Nerd Font 才能正常显示图标**，而且装完字体还要**在终端设置里选中它**，两步缺一不可。
- 需要能修改 shell 的启动文件（PowerShell 的 `$PROFILE`、`~/.bashrc`、`~/.zshrc`、fish 的 `config.fish` 等）。
- PowerShell 场景受本机执行策略约束，可能需要改策略或给 profile 签名。
- 不需要账号、Key 或注册。

---

## 使用

1. 装本体：Windows `winget install JanDeDobbeleer.OhMyPosh --source winget`；macOS `brew install jandedobbeleer/oh-my-posh/oh-my-posh`；Linux `curl -s https://ohmyposh.dev/install.sh | bash -s`。
2. 装字体：`oh-my-posh font install`，然后到终端设置里把字体改成刚装的那个。
3. 认 shell：`oh-my-posh get shell`。
4. 接上去：把 `oh-my-posh init <shell>` 那一行放到 shell 配置文件的**最后**。例如 PowerShell 是 `oh-my-posh init pwsh | Invoke-Expression`，bash / zsh 是 `eval "$(oh-my-posh init bash)"`。
5. 换主题：把 `--config` 指向本地主题文件（推荐），也可以给内置主题名或远程 URL。
6. 想改主题先导出：`oh-my-posh config export --config jandedobbeleer --output ~/.mytheme.omp.json`。
7. 调完预览与排错：`oh-my-posh print preview`、`oh-my-posh debug`；改配置后需要 `oh-my-posh enable reload` 或重开 shell 才生效。

完整命令、坑位清单与能力边界见 `SKILL.md`。

---

## 依赖

- 运行期无第三方运行时依赖，单个二进制。
- 联网：安装、下载主题/字体、升级检查需要网络；日常使用本地主题文件时不需要。
- Linux 安装脚本的依赖：`curl`、`unzip`、`realpath`、`dirname`。
- 显示依赖：Nerd Font（否则图标显示为方块），以及支持相应转义序列的终端。
- 渲染时会调用系统里的外部命令（如 `git`）来取值，缺哪个命令对应段就取不到值。
- 不需要任何账号或 Key。

---

## 安全

- 不内嵌任何密钥。
- 官方 Linux 安装方式是 `curl ... | bash`：这会**直接把远端脚本交给 shell 执行**。请确认来源是本工具官方域名，或在执行前先下载下来看一眼。
- `--config` 支持远程 URL，等于**每次开 shell 都下载并解析一份配置**；配置里可包含模板与外部命令调用，因此不要指向不可信的地址。
- `font install` 会下载并安装字体文件到系统字体目录。
- `oh-my-posh upgrade` 与自动升级会从官方源下载并替换可执行文件；官方说明自动升级不会跨大版本。
- 初始化会写入你的 shell 启动文件；改动前建议先备份（`config migrate` 之类的操作会自行留 `.bak`）。
- Skill 本体只包含文档，不含上游项目的源代码；上游软件本身的问题请走上游仓库的 Issues。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`oh-my-posh`
- 仓库：https://github.com/JanDeDobbeleer/oh-my-posh

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
