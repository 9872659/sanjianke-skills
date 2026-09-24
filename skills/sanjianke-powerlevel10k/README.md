# 三剪客 · Zsh 极速提示符主题 Skill

powerlevel10k：Zsh 极速提示符主题 的安装、常用命令与避坑要点

---

## 前置条件

- **必须是 Zsh**。Bash、Fish、PowerShell、Nushell 等不受支持，装了也不会生效。
- 建议 Zsh 版本较新；个别样式（Pure + Snazzy 配色）要求 Zsh ≥ 5.7.1。
- 终端建议支持 256 色以上；要用 truecolor 样式需终端支持 truecolor（`COLORTERM` 为 `24bit` 或 `truecolor`）。
- 强烈建议先安装一款 Nerd Font，否则配置向导不会提供图标类样式，提示符也会缺字形。
- 系统需要可用的 UTF-8 locale，且 Zsh 的 `MULTIBYTE` 选项不要被关闭。
- 不需要任何账号、Token 或 API Key。

---

## 使用

最短跑通路径（手动安装，与任何插件管理器都能共存）：

```zsh
# 1) 拉取主题
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ~/powerlevel10k

# 2) 在 ~/.zshrc 里加载主题（如果插件管理器里已有别的主题，先关掉它）
echo 'source ~/powerlevel10k/powerlevel10k.zsh-theme' >>~/.zshrc

# 3) 重启 Zsh
exec zsh

# 4) 向导没自动出现就手动跑
p10k configure
```

安装方式选一种即可：上面的手动方式是官方推荐的稳妥路径；用 Oh My Zsh 时把主题 clone 到
`"${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k"`，再把 `ZSH_THEME` 改成
`"powerlevel10k/powerlevel10k"`；Homebrew 用户装完 source
`$(brew --prefix)/share/powerlevel10k/powerlevel10k.zsh-theme`。

配置：向导会把结果写进 `~/.p10k.zsh`（文件名固定），后续所有定制都在这个文件里改，搜索
`POWERLEVEL9K_` 前缀的参数即可。改完**用 `exec zsh` 生效，不要 `source ~/.zshrc`**。
只改了 `POWERLEVEL9K_*` 参数时，也可以在当前会话里 `p10k reload` 热重载。

```zsh
p10k reload            # 热重载主题配置
p10k help segment      # 查看自定义分段的 API
```

想临时绕过配置向导启动 Zsh（排查 `~/.zshrc` 报错时很有用）：

```zsh
POWERLEVEL9K_DISABLE_CONFIGURATION_WIZARD=true zsh
```

更多分段与参数说明见 SKILL.md 与上游仓库文档。

---

## 依赖

- 运行期：Zsh 本身；无 Python/Node 运行时依赖，无需数据库或后台服务。
- 外观：一款 Nerd Font（推荐）、支持足够颜色数的终端、UTF-8 locale。
- 信息采集：按需调用系统上已存在的命令（如 `git`、`kubectl`、各类语言运行时）；命令不存在时对应分段不显示。
- 安装期：走 `git clone` 或包管理器需要网络；运行期不联网。

---

## 安全

- 不内嵌任何密钥。
- 提示符渲染期不联网，不会上传目录名、分支名、主机名等任何内容。
- 会读取本机文件用于渲染：`~/.zshrc`、`~/.p10k.zsh`、当前目录与 Git 仓库状态等；日常运行只读。
- 唯一写文件的行为是 `p10k configure`——它会写出 `~/.p10k.zsh` 并往 `~/.zshrc` 追加一行 source；运行该向导前建议先备份这两个文件。
- 会启动外部子进程采集分段信息；不想要某些分段，可在 `~/.p10k.zsh` 里不启用对应参数。
- `~/.p10k.zsh` 等同于会被 Zsh 执行的代码，请只使用自己生成或自己审阅过的文件。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`powerlevel10k`
- 仓库：https://github.com/romkatv/powerlevel10k

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
