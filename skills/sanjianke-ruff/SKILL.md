---
name: sanjianke-ruff
slug: sanjianke-ruff
displayName: 三剪客 · 极速 Python Linter 与格式化器
description: "ruff：极速 Python Linter 与格式化器 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "ruff：极速 Python Linter 与格式化器 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · 极速 Python Linter 与格式化器

Python 项目里的静态检查长期以来是一叠工具：一个查未用导入、一个排 import 顺序、一个管代码风格、一个改老语法，每个都要单独装、单独配、单独跑一遍，CI 里排成一长串。ruff 把这些检查收进一个命令 `ruff check`，格式化收进 `ruff format`；规则按 Flake8 那套字母前缀编号（`E`、`F`、`I`、`UP`…），选择与忽略都写在一处配置里。它的定位是「够快，所以可以放心每次保存都跑」，代价是目前不支持类型检查那类需要跨文件推导的规则。

**上游项目**：`ruff`　**仓库**：https://github.com/astral-sh/ruff

## 什么时候用 / 不用

**用它**：

- 用户说「CI 里 lint 太慢 / 工具太多」，想把 Flake8 + isort + pyupgrade + autoflake 那一串合成一个。
- 新项目要一套能直接跑的 lint + format 配置，希望配置集中、跑得够快。
- 想拿它替换既有的 Black 工作流：`ruff format` 面向 Black 兼容设计，对已格式化的项目改动很小。
- 需要自动修一批机械性问题（未用导入、老式类型注解、import 顺序），并区分「安全修复」与「可能改变行为的不安全修复」；也需要能写人类可读的抑制注释（如 `# ruff: ignore[...]`）。
- 要在保存即检查的编辑器钩子或预提交里跑，等待时间必须压到很短。

**不要用它**：

- 需要**类型检查**（`mypy` / `pyright` 那类跨文件类型推导）：ruff 的规则集不覆盖这个层面，它只做 lint 与格式化。
- 团队已经深度绑定 Black 的预览特性且不想改：两者风格高度接近但不完全一致，混着用会出现来回改动的 diff。
- 依赖重量级 Flake8 插件生态里未在本工具中实现的第三方插件：不是所有 Flake8 插件都有等价规则，迁移前需要核对规则清单。
- 只想跑一次、不打算加配置的项目：默认规则集与项目既有风格大概率冲突，会一次报出大量结果。
- 期待「格式化顺手把 import 也排好」：排序属于 linter 的 `I` 规则，需要先 `ruff check --select I --fix`，格式化本身不排序导入。

## 安装

**通用方式（有 uv 时最省事，无需先装到环境里）**

```bash
uvx ruff check    # 运行而不是安装
uvx ruff format

# 装成全局工具
uv tool install ruff@latest
# 或加进项目
uv add --dev ruff
```

**pip / pipx**

```bash
pip install ruff
pipx install ruff
```

**独立安装脚本（无需 Python 环境管理）**

```bash
# macOS / Linux
curl -LsSf https://astral.sh/ruff/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/ruff/install.ps1 | iex"
```

**包管理器**

```bash
brew install ruff                       # macOS / Linuxbrew
conda install -c conda-forge ruff       # Conda
sudo pacman -S ruff                     # Arch
sudo apk add ruff                       # Alpine
sudo zypper install python3-ruff        # openSUSE Tumbleweed
```

**Docker**

```bash
docker run -v .:/io --rm ghcr.io/astral-sh/ruff check
# SELinux 上的 Podman 需要加 :Z
docker run -v .:/io:Z --rm ghcr.io/astral-sh/ruff check
```

装完验证：

```bash
ruff --version
ruff check --help
ruff format --help
```

## 常用操作

**1. 检查与自动修复**

```bash
ruff check                  # 检查当前目录
ruff check --fix            # 检查并应用所有「安全」修复
ruff check --watch          # 监听文件变化，改动即重新检查
ruff check path/to/code/    # 只检查指定目录
```

**2. 格式化（Black 兼容风格）**

```bash
ruff format                  # 就地格式化当前目录
ruff format path/to/file.py  # 格式化单个文件
ruff format --check          # 只检查、不写回；有未格式化文件时以非零退出
```

**3. 选择规则集（写在配置里，别全靠命令行）**

```toml
# pyproject.toml
[tool.ruff.lint]
select = [
    "E",    # pycodestyle
    "F",    # Pyflakes
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "I",    # isort
]
ignore = ["F401"]
```

独立的 `ruff.toml` 里则写成顶层 `[lint]` 段，`select` / `ignore` 内容一致。

**4. 命令行临时改规则（优先级高于配置文件）**

```bash
ruff check --select F401              # 只跑 F401，忽略配置里其它 select
ruff check --extend-select B          # 在配置基础上追加 B 组
ruff check --extend-select RUF100     # 顺带找出「没起作用」的抑制注释
ruff check --extend-select RUF100 --fix   # 并删掉这些无用抑制注释
```

**5. 不安全修复：先看、再应用**

```bash
ruff check --unsafe-fixes                # 只展示不安全修复，不应用
ruff check --fix --unsafe-fixes          # 应用不安全修复（可能改变运行时行为）
ruff check --no-unsafe-fixes             # 关掉「有不安全修复可用」的提示
```

**6. 迁移存量项目：批量加抑制注释**

```bash
ruff check /path/to/file.py --add-noqa      # 给违规行加 # noqa
ruff check /path/to/file.py --add-ignore    # 给违规行加 # ruff: ignore[...]
```

**7. 配置格式化器行为**

```toml
# pyproject.toml
[tool.ruff]
line-length = 100

[tool.ruff.format]
quote-style = "single"
indent-style = "tab"
docstring-code-format = true
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 一上来就报出成百上千条结果 | 默认规则集与项目既有风格不一致；或用了 `ALL` | 先用小集合起步（如 `select = ["E", "F"]`），稳定后一次加一组；`ALL` 要克制，升级时会连带启用新规则 |
| CI 里 `ruff check --fix` 之后仍然退出码非 0 | 默认行为：只要发现过违规就返回 1，即使都已自动修掉 | 需要「修完即通过」时显式确认语义；想强制「修过也要失败」，用 `--exit-non-zero-on-fix`；想一律不因违规失败，用 `--exit-zero`（仅异常时才返回 2） |
| 以为 `ruff format` 会顺手排序 import | 格式化器目前不做 import 排序 | 两条命令连着跑：`ruff check --select I --fix` 然后 `ruff format` |
| `ruff check --fix` 没修某条违规 | 该规则只有「不安全修复」，默认不应用 | 用 `--unsafe-fixes` 先展示、确认后再 `--fix --unsafe-fixes`；或按规则用 `extend-safe-fixes` / `extend-unsafe-fixes` 单条调整安全性 |
| 格式化后 lint 又报新错 | 启用了与格式化器冲突的风格类规则 | 官方建议避免 `W191`、`E111`、`E114`、`E117`、`D203`、`D206`、`D300`、`Q000`–`Q004`、`COM812`、`COM819` 等；把它们加进 `lint.ignore`。`ruff format` 会在检测到冲突时给出警告，没有警告即为干净 |
| 行宽设了 88/100，格式化后仍有更长的行 | 格式化器只在尽力而为的前提下折行；`E501` 仍可能触发 | 这是预期行为；要么放宽 `line-length`，要么把 `E501` 排除 |
| `--select` 之后配置里的 `ignore` 全失效了 | CLI 的 `select` 优先级最高，会成为新的规则集基准 | 需要「在配置基础上追加」时用 `--extend-select`，不要用 `--select` |
| `# noqa` 写在多行语句的某一行上不起作用 | 行级抑制的覆盖范围按逻辑行/物理行区分 | 多行语句想整段抑制，把 `# ruff: ignore[...]` 写在首行上方；`# noqa` 对 docstring 要写在闭合三引号之后 |
| 用 `disable` 忘了写对应的 `enable` | 会被当作隐式范围，一直延伸到缩进更浅处 | 显式成对写 `# ruff: disable[...]` / `# ruff: enable[...]`；隐式范围会产生 `RUF104` 诊断 |
| 抑制注释越积越多、有的早已失效 | 没有检查「无用抑制」 | 用 `--extend-select RUF100` 找出来，再加 `--fix` 删除 |
| `ruff format --check` 退出码看不懂 | 三种退出码语义不同 | `0` = 无需格式化；`1` = 有文件需要格式化；`2` = 配置/参数非法或内部错误。`ruff check` 的 `1` 则是「发现违规」 |
| 项目里同时启用了 isort 的非常规设置 | 部分 isort 设置与格式化器对导入语句的处理不兼容 | 官方建议避免把 `force-single-line`、`force-wrap-aliases`、`lines-after-imports`、`lines-between-types`、`split-on-trailing-comma` 设为非默认值 |
| Markdown 里的代码块被意外格式化 | 格式化器会处理 `.md` 中带 `python` / `py` / `pyi` / `pycon` 等标记的围栏代码块 | 需要保留原样就加 `<!-- fmt:off -->` / `<!-- fmt:on -->` 包裹；或把 `*.md` 加进 `extend-exclude` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（仅安装时） | 安装脚本 / 包管理器需要联网；运行期不联网、不上报 |
| 读取文件 | 是 | 读取待检查的源码、项目配置（`pyproject.toml` / `ruff.toml`）与编辑器的继承配置 |
| 写入文件 | 是（仅在加 `--fix` / 不加 `--check` 时） | `ruff check --fix` 修改源码、`ruff format` 就地写回、`--add-noqa` / `--add-ignore` 插入抑制注释 |
| 凭证 | 否 | 不需要任何账号或 Key |
| 子进程 / 后台常驻 | 是（仅 `--watch`） | `ruff check --watch` 会常驻监听文件变化；其余命令都是一次性前台执行 |

## 触发场景

- 「Python 项目 ESLint 那种东西有没有，一个工具搞定 lint 和格式化」
- 「Flake8 太慢了，CI 里 lint 要等好几分钟」
- 「怎么把 Black 和 isort 合成一条命令」
- 「`ruff check --fix` 之后 CI 还是红的，为什么」
- 「怎么批量给老项目加 noqa 注释做迁移」
- 「ruff 能不能做类型检查」

## 能力边界

**覆盖**：

- 静态 lint（`ruff check`）：按 Flake8 风格编号的规则集，含大量对常见插件规则的等价实现；规则可按前缀、全码或（预览模式下的）人类可读名选择。
- 自动修复：区分安全修复与不安全修复，可按规则调整安全性、限制可修范围。
- 格式化（`ruff format`）：面向 Black 兼容的代码风格，可配置行宽、引号风格、缩进风格、docstring 内示例代码格式化。
- 抑制机制：行级 `# noqa`、逻辑行 `# ruff: ignore[...]`、块级 `disable` / `enable`、文件级 `# ruff: noqa` / `file-ignore`，以及无用抑制检测（`RUF100`）。
- 与 isort 兼容的导入排序与 action comments。
- 多平台安装：PyPI、独立脚本、Homebrew、Conda、各发行版包管理器、官方容器镜像。

**不覆盖**：

- 类型检查：跨文件类型推导不在它的规则集内，需要另配类型检查工具。
- 全面替代所有 Flake8 第三方插件：只有被实现为等价规则的插件才可用。
- 运行时行为检测、安全扫描、性能剖析：它是静态检查与格式化工具。
- 依赖管理、虚拟环境管理、测试运行：这些属于其他工具的职责。
- 保证格式化结果与 Black 100% 一致：目标是高度接近，存在少量有意为之的偏差。

## 依赖条件

- 通过 pip / pipx / uv 安装时需要一个 Python 环境；独立安装脚本与包管理器安装方式不依赖项目内的 Python 环境。
- 用 Docker 方式运行时需要可用的容器运行时；SELinux 环境下挂载需加 `:Z`。
- 配置文件放在项目根目录：`pyproject.toml`（`[tool.ruff]`）或独立的 `ruff.toml`。
- 无需任何账号、Key 或在线服务。

## 已知限制

- 不做类型检查；不要把它当成 `mypy` / `pyright` 的替代品。
- 默认只应用安全修复；不安全修复需要显式开启，且开启前应逐条确认语义变化。
- 格式化只尽力折行，格式化后的代码仍可能超出 `line-length`（因此 `E501` 可能继续报错）。
- 部分 isort 设置与风格类规则和格式化器冲突，需要主动排除。
- 迁移既有项目时不可避免要处理一批存量违规，`--add-noqa` 只是把它变成技术债而不是消除它。
- 规则集合会随版本演进（预览模式下的规则名、分类选择器都在变化），升级前建议看变更说明。

## 自检清单

- 执行前：确认 `ruff --version` 与 `ruff check --help` 可用；确认配置文件位置（`pyproject.toml` 还是 `ruff.toml`）；确认当前规则集规模，避免首次引入就报出海量问题。
- 执行中：改代码前先跑 `ruff check`（只读）看范围，再决定 `--fix`；涉及 `--unsafe-fixes` 时先不加 `--fix` 展示一遍；格式化前后确认在版本控制里、可回滚。
- 执行后：`ruff check` 与 `ruff format --check` 各自退出码符合预期；CI 中确认 `--fix` 与退出码的组合语义；检查是否残留无用抑制注释（`--extend-select RUF100`）。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/astral-sh/ruff | 上游仓库（安装与完整文档以它为准） |
| https://docs.astral.sh/ruff/linter/ | lint 命令、规则选择、修复与抑制机制的官方说明 |
| https://docs.astral.sh/ruff/formatter/ | 格式化命令、配置项与冲突规则的官方说明 |

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
