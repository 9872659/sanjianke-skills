# 三剪客 · 目录级环境变量自动加载 Skill

direnv：目录级环境变量自动加载 的安装、常用命令与避坑要点

---

## 前置条件

本 Skill 为工具类技能包，按 SKILL.md 的「安装」一节准备运行环境即可。

## 使用

正文的「安装」与「常用操作」两节是最短可用路径。

```bash
# 1) 最小闭环：建 .envrc → 被拦下 → 授权 → 变量生效 → 离开目录自动还原
mkdir -p ~/my-project && cd ~/my-project
echo 'export FOO=foo' > .envrc
#   此时 direnv 会提示 .envrc is not allowed
direnv allow .
echo ${FOO-nope}        # 输出 foo
cd ..                   # direnv: unloading
echo ${FOO-nope}        # 又变回 nope

# 2) 用 stdlib 函数写 PATH，而不是粗暴覆盖 PATH
cat > .envrc <<'EOF'
PATH_add bin                 # 前置 $PWD/bin，不破坏原 PATH
PATH_add node_modules/.bin
layout python3               # 在 .direnv/python-* 下建/用虚拟环境
dotenv_if_exists .env        # 有 .env 就加载，没有就跳过
watch_file requirements.txt  # 依赖文件变了就自动重载
EOF
direnv allow .

# 3) 授权状态管理
direnv status                # 看当前目录有没有 .envrc、是否已授权、走了哪些配置文件
direnv deny .                # 撤销授权（文件被改过之后 direnv 也会自动要求重新 allow）
direnv prune                 # 清掉 $XDG_DATA_HOME/direnv/allow 里已经过期的授权记录

# 4) 用 $EDITOR 改 .envrc，退出编辑器后自动重新授权 + 重载
direnv edit .

# 5) 不改当前目录，在指定目录的环境里执行命令
direnv exec ~/my-project python -c 'import os; print(os.environ.get("FOO"))'

# 6) 手动重载 / 看导出内容 / 看 stdlib
direnv reload                # 触发一次重载
direnv export bash           # 打印环境变量 diff（调试"为什么变量没生效"最有用）
direnv export json           # 同样的 diff，JSON 格式
direnv stdlib | head -n 40   # 打印 .envrc 可用的全部 stdlib 函数
```

## 依赖

- **操作系统**：官方前置条件是 Unix-like（macOS、Linux 等）；Windows 属受限/实验性支持，建议改用 WSL
- **shell**：需要是它支持的其中一种（bash、zsh、fish、tcsh、elvish、pwsh、murex、nushell），并完成 hook
- **bash**：`.envrc` 在 bash 子进程里求值，所以系统里必须有可用的 bash；PATH 可能被改写导致找不到 bash 时，可在 `direnv.toml` 里设置 `bash_path` 固定它
- **可选的配套工具**：用 `layout python` 需要相应 Python 工具链；`layout ruby` / `use rbenv` 需要对应版本管理器；`use nix` / `use guix` 需要装 nix / guix；`on_git_branch` 需要 git
- **不需要账号、Key 或在线服务**——除你自己在 `.envrc` 里调用的联网函数外
- 配置文件位置：`$XDG_CONFIG_HOME/direnv/direnv.toml`，授权记录在 `$XDG_DATA_HOME/direnv/allow`

## 安全

- 不内嵌任何密钥
- 不主动把任何内容发往外部地址
- 若正文涉及联网或读写文件，权限范围已在 SKILL.md 的「权限与用途说明」中逐项列明
- 能力边界见 SKILL.md 的「能力边界」一节

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`direnv`
- 仓库：https://github.com/direnv/direnv

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
