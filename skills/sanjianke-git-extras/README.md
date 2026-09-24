# 三剪客 · Git 增强命令集 Skill

git-extras 是一组 git 子命令扩展，补齐 `git summary` / `git effort` / `git changelog` / `git release` / `git ignore` / `git squash` 等原生 git 没有的日常操作，本文给出安装、常用命令与避坑要点。

---

## 前置条件

- 本机已安装 `git`，且 `git` 在 `PATH` 上（`git --version` 有输出）。
- 从源码安装时需要 `make` 和 `bash`，以及一个**可写**的安装目标目录。默认安装位置在 git 自己的 `libexec/git-core` 下，通常要 `sudo`；不想动系统目录就用 `PREFIX=$HOME/.local make install`。
- 包管理器安装（Homebrew / apt 等）不需要额外工具链。
- Windows 上没有原生 apt / brew 路线：走 WSL 按 Linux 方式装，或在 Git Bash（自带 MSYS 工具链）里 `make install`。
- 使用 `release` / 推送类命令前，remote 与 git 凭据需已配置好。

---

## 使用

最短跑通路径：

```bash
# 1. 装
brew install git-extras          # macOS
# 或
sudo apt-get install git-extras  # Debian / Ubuntu

# 2. 进任意一个 git 仓库，确认能识别
cd /path/to/repo
git summary

# 3. 试一条写入类命令（安全的那种）
git ignore '*.log'
git status
```

然后按需要挑命令用，完整用法见 `SKILL.md` 的「常用操作」：仓库统计用 `git summary` / `git effort`，出变更日志用 `git changelog`，发版用 `git release`，压缩提交用 `git squash`。

需要先弄清的一点：extras 的每条命令都是**独立脚本**，只读统计和改写历史的命令混在一起。跑 `obliterate` / `reauthor` / `sed` 之前务必先读 `SKILL.md` 的「不要用它」与「常见坑」。

---

## 依赖

- **必需**：`git`。
- **安装期**：`make`、`bash`；源码安装时的写权限。
- **运行期**：部分子命令内部调用 `awk`、`sed`、`grep` 等 Unix 工具。Linux / macOS 自带；Windows 建议 WSL。
- **不依赖**：不需要 Rust / Go / Node / Python 工具链；不需要任何账号、Key 或在线服务。
- **联网**：仅安装时 `git clone` 需要网络；命令本身不上报数据，只有你显式推送时才走 remote。

---

## 安全

- 不内嵌任何密钥，也不需要用户提供任何凭证。
- 使用你已经配置好的 git 凭据，本 Skill 不读取、不保存、不转发密码或 token。
- **重写历史类命令（`obliterate`、`reauthor`、`sed`、`squash`、`undo`）会改动已有 commit**。执行前确认分支没有被别人依赖，执行后需要强推并通知协作者。
- `git ignore -g/--global` 会修改你的**全局** gitignore，影响机器上所有仓库；不加 `-g` 才是安全的默认行为。
- `git changelog --prune-old` 会用新内容整体替换已有日志文件，不是追加；先提交或备份。
- `git release` 会创建提交、打 tag 并**推送**到远端，属于对外可见操作，确认版本号无误再执行。
- 安装脚本会往 git 的安装目录写文件，这需要提权；不放心系统目录就用 `PREFIX` 装到用户目录。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`git-extras`
- 仓库：https://github.com/tj/git-extras

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
