# 三剪客 · 现代化 ls 替代品 Skill

lsd：现代化 ls 替代品 的安装、常用命令与避坑要点

---

## 前置条件

- 系统里有可用的终端；Windows 上 PowerShell、cmd、Windows Terminal 都可以。
- **推荐**：安装一个 Nerd Font（或 font-awesome 一类打过补丁的字体），并在终端里选中它。不装也能用，但图标会显示成方块或问号。
- 用预编译二进制或包管理器安装：不需要额外运行时。
- 用 `cargo install` 从源码安装：需要可用的 Rust 工具链与 Cargo。
- 想要自定义配色（尤其是 Windows）：需要能设置 `LS_COLORS` 环境变量。

## 使用

最短跑通路径：

```bash
# 1) 装（按自己的平台选一条）
brew install lsd                 # macOS / Linuxbrew
scoop install lsd                # Windows
sudo pacman -S lsd               # Arch
cargo install lsd                # 从源码

# 2) 先验证图标字体是否可用——打印出文件夹图标才算配好
echo $'\uf115'

# 3) 日常用法
lsd -la                          # 长格式 + 隐藏文件
lsd --tree --depth 2             # 树形，限两层
lsd -l --git                     # 长格式里带 git 状态
lsd --icon never                 # 字体没配好时的保底用法
```

配成 `ls` 的替代（写进 `~/.bashrc` / `~/.zshrc`）：

```bash
alias ls='lsd'
alias l='lsd -l'
alias la='lsd -a'
alias lla='lsd -la'
alias lt='lsd --tree'
```

自定义外观：在配置目录里创建 `config.yaml`、`colors.yaml`、`icons.yaml` 中的**任意一份或几份**即可，不必三份齐全。

- Unix：`$HOME/.config/lsd/` 或 `$XDG_CONFIG_HOME/lsd`
- Windows：优先 `%USERPROFILE%\.config\lsd`，其次 `%APPDATA%\lsd`
- 临时试配置：`lsd --config-file ./my-config.yaml`（注意接收的是文件路径，不是目录）

参数全集以 `lsd --help` 与上游文档为准：https://github.com/lsd-rs/lsd

## 依赖

- **运行时**：无（预编译二进制 / 包管理器安装）。从源码安装需要 Rust 工具链。
- **显示层依赖**：Nerd Font 一类 patched 字体 + 终端选中该字体。缺失时不会报错，只会显示成方块。
- **可选依赖**：
  - `LS_COLORS` 环境变量 —— 决定文件名配色；Windows 上自定义配色必须显式设置。
  - `SHELL_COMPLETIONS_DIR` 或 `OUT_DIR` —— 只有需要生成补全脚本时才用到。
  - `git` —— 仅在使用 `--git` 查看仓库状态时相关（读的是工作区状态）。
- **不需要**：网络、账号、API Key、GPU。

## 安全

- 不内嵌任何密钥：本 Skill 与脚本里没有 Token、密码或私钥。
- **只读工具**：它只读取目录内容与文件元数据，不修改、不删除、不移动任何被列出的文件。
- **会读取的内容范围**：目录项、文件元数据（大小/权限/时间/链接目标），以及 `--git` 时的仓库状态。`--total-size` 会递归遍历子目录统计大小，在超大目录上有明显 IO 开销。
- **唯一的写入场景**：生成 shell 补全脚本时会写入 `SHELL_COMPLETIONS_DIR` 或 `OUT_DIR` 指定的目录；不设这两个变量就不会写任何文件。
- **输出不要用于解析**：带颜色和图标、列宽随终端变化，机器可读场景请勿依赖；给脚本用时至少加 `--icon never --color never -1`。
- **不要对不熟悉的巨型目录裸跑 `--tree`**：会把整棵树连同 `.git`、依赖目录一起渲染出来，既慢又刷屏；请配 `--depth` 与 `--ignore-glob`。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`lsd`
- 仓库：https://github.com/lsd-rs/lsd

---

## 许可证

MIT，见 `LICENSE.md`。

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
