# 三剪客 · 智能目录跳转 Skill

zoxide：记住你去过的目录，之后用 `z` 加一两个关键词就跳过去，不用再一层层 cd 或者翻 history

---

## 前置条件

- 装好 zoxide 二进制：走官方安装脚本、包管理器或 `cargo install` 都可以（Windows 上官方推荐 winget）
- **必须做一次 shell 初始化**，否则只有 `zoxide` 命令，没有 `z`：`z` 是由 `zoxide init` 生成的 shell 函数
- 初始化行要写进**当前 shell 真正加载**的配置文件（bash 是 `~/.bashrc`，zsh 是 `~/.zshrc`，fish 是 `config.fish`，PowerShell 是 `$PROFILE`），并建议放在靠后位置，避免被后续别名覆盖
- 想用 `zi` 或 `zoxide query --interactive`，需要额外装一个模糊选择器（如 fzf），且版本要满足官方最低要求
- 不需要账号、Key 或网络服务

---

## 使用

最短跑通路径（三步验证，缺哪一步补哪一步）：

```bash
zoxide --version       # 1. 二进制在 PATH 里吗
type z                 # 2. shell 函数生成了吗
zoxide query --list    # 3. 数据库里有东西吗
```

然后做一次端到端测试：

```bash
mkdir -p "$HOME/projects/zoxide-demo"
zoxide add "$HOME/projects/zoxide-demo"
cd "$HOME"
z zoxide-demo          # 应该跳到刚建的目录
pwd
```

日常最高频的几条：

```bash
z project                  # 跳到排名最高的匹配目录
z client portal            # 多关键词收窄
zi project                 # 交互式挑选（需要模糊选择器）
zoxide query --list --score  # 看它都学了什么、各自得分多少
zoxide remove ~/code/old   # 删掉过期条目
```

排错顺序：`zoxide` 找不到 → 查 PATH（官方脚本装到 `~/.local/bin`，cargo 装到 `~/.cargo/bin`）；`z` 找不到 → 补 shell 初始化；`no match found` → 先用完整路径 `cd` 进去一次，或 `zoxide add` 手动补。

---

## 依赖

- **运行环境**：Linux / macOS / Windows（含 WSL、Android），官方提供各架构预编译包与安装脚本
- **安装途径**：官方安装脚本（Linux / WSL 推荐）、apt / pacman / brew、winget（Windows 推荐）、`cargo install zoxide --locked`
- **shell 支持**：bash、zsh、fish、PowerShell、Nushell 等，通过 `zoxide init <shell>` 生成对应初始化代码
- **可选依赖**：模糊选择器（如 fzf）——只有 `zi` 和 `query --interactive` 需要，且对版本有最低要求
- **数据存放**：目录数据库在本地按用户存放，随访问持续更新
- **环境变量**：`_ZO_EXCLUDE_DIRS`、`_ZO_MAXAGE`、`_ZO_ECHO`、`_ZO_RESOLVE_SYMLINKS`、`_ZO_FZF_OPTS` 等，必须在初始化之前设置才生效
- **注意事项**：`_ZO_EXCLUDE_DIRS` 的列表分隔符按操作系统不同（Unix 与 Windows 不一致）

---

## 安全

- 不内嵌任何密钥：本 Skill 不包含账号、token 或任何凭据
- **数据库包含你的目录访问历史**：zoxide 会持续记录你去过的目录路径与访问频次。这份数据是本地隐私信息，分享截图或同步 dotfiles 时注意别把数据库一起带走
- **`_ZO_ECHO=1` 会打印跳转目标**：在共享屏幕或录屏场景下会把你常去的路径暴露在终端里
- **`--cmd cd` 会顶替 `cd`**：这是对自己日常习惯的实质性改动，官方建议先在临时 shell 里试验，不要直接写进主配置
- **`import` 会读取其它工具的历史文件**：迁移前先备份原数据，确认导入结果符合预期后再考虑清理原工具
- **`_ZO_EXCLUDE_DIRS` 要在初始化前设置**：忘了顺序的话，敏感目录（临时目录、网络挂载、含机密的路径）会被悄悄记进数据库
- **无常驻服务、无网络请求**：zoxide 本身不监听端口、不上传数据，日常跳转全程本地

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`zoxide`
- 仓库：https://github.com/ajeetdsouza/zoxide

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
