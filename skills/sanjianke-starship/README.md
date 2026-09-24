# 三剪客 · 跨 Shell 提示符引擎 Skill

starship：跨 Shell 提示符引擎 的安装、常用命令与避坑要点

---

## 前置条件

- 一个受支持的 Shell：Bash / Zsh / Fish / PowerShell / Nushell（v0.96+）/ Elvish（v0.18+）等。
- 建议先安装一款 Nerd Font 并在终端里启用，否则提示符中的图标字形会显示成方框。
- Windows 上如果坚持使用传统 Cmd，需要额外安装 Clink（v1.2.30+）才能加载 starship。
- 安装阶段需要联网（走安装脚本或包管理器）；提示符运行期不需要网络。
- 不需要任何账号、Token 或 API Key。

---

## 使用

最短跑通路径（以 Zsh 为例）：

```bash
# 1) 安装（选一种）
brew install starship                  # macOS / Linuxbrew
curl -sS https://starship.rs/install.sh | sh   # 通用脚本
cargo install starship --locked        # 有 Rust 工具链时

# 2) 在 Shell 启动文件末尾初始化
echo 'eval "$(starship init zsh)"' >> ~/.zshrc

# 3) 重开终端（或 exec zsh），应当立即看到新提示符
```

PowerShell：

```powershell
winget install --id Starship.Starship
Add-Content $PROFILE 'Invoke-Expression (&starship init powershell)'
```

改样式：建 `~/.config/starship.toml`，按需增删模块。

```bash
mkdir -p ~/.config && touch ~/.config/starship.toml
```

```toml
"$schema" = 'https://starship.rs/config-schema.json'
add_newline = true

[character]
success_symbol = '[➜](bold green)'
error_symbol = '[✗](bold red)'

[package]
disabled = true
```

或先用官方预设起步（`-o` 会整份覆盖目标文件，先备份）：

```bash
starship preset --list
starship preset nerd-font-symbols -o ~/.config/starship.toml
```

配置路径可用环境变量覆盖，便于在 dotfiles 仓库里按场景切换：

```bash
export STARSHIP_CONFIG=~/dotfiles/starship.work.toml
```

完整的模块清单、每个模块的可配置项与示例，见 SKILL.md 与官方配置文档。

---

## 依赖

- 运行期：仅依赖一个受支持的 Shell 与（可选的）Nerd Font；无 Python/Node 运行时依赖。
- 信息采集：按需调用系统上已存在的外部命令（如 `git`、`node`、`python`）取版本与状态，命令不存在时对应模块自动不显示。
- 安装期：走安装脚本或包管理器需要网络；`cargo install` 路径需要 Rust 工具链，并留意 `~/.cargo/bin` 是否在 `PATH` 中。
- 无第三方服务依赖，无 API Key，无数据库。

---

## 安全

- 不内嵌任何密钥。
- 提示符运行期不联网，不会把目录名、分支名、主机名等渲染内容上传到任何地方。
- 会读取本机文件用于渲染：`starship.toml` 配置、当前目录文件列表、`~/.gitconfig` 等；只读，不改动这些文件。
- 会为模块信息启动外部子进程（`git`、语言运行时等）；`command_timeout`（默认 500ms）是硬超时，可用 `disabled = true` 关掉任何不想执行的模块。
- 唯一会写文件的行为是显式使用 `starship preset -o <文件>` 时覆盖写出配置，以及运行期把警告写入缓存目录日志（可用 `STARSHIP_CACHE` 改路径）。
- `STARSHIP_CONFIG` 指向的文件如果来自不可信来源，等于让对方决定你的提示符里执行什么命令，请只使用自己的配置文件。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`starship`
- 仓库：https://github.com/starship/starship

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
