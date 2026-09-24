# 三剪客 · 极速 Python Linter 与格式化器 Skill

ruff：极速 Python Linter 与格式化器 的安装、常用命令与避坑要点

---

## 前置条件

- 通过 pip / pipx / uv 安装时需要一个 Python 环境；用独立安装脚本、包管理器或 Docker 镜像则不需要项目内的 Python 环境。
- 项目里最好已有 `pyproject.toml`（配置写在 `[tool.ruff]`）或愿意新建一个 `ruff.toml`。
- 迁移既有项目前，先在版本控制里提交一次干净状态——`--fix` 与格式化都会直接改写源码。
- 用 Docker 方式运行时需要可用的容器运行时；SELinux 环境下挂载目录要加 `:Z`。
- 不需要任何账号、Token 或 API Key。

---

## 使用

最短跑通路径：

```bash
# 1) 安装（选一种）
uv tool install ruff@latest      # 有 uv 时推荐
pip install ruff                 # 或
brew install ruff                # macOS / Linuxbrew

# 2) 先只读地看一眼现状
ruff check

# 3) 应用安全修复
ruff check --fix

# 4) 格式化
ruff format
```

配规则集（写在项目根目录的 `pyproject.toml`）：

```toml
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

[tool.ruff]
line-length = 100

[tool.ruff.format]
quote-style = "single"
```

改成独立的 `ruff.toml` 时，把 `[tool.ruff]` 去掉、直接用顶层 `[lint]` 与 `[format]` 段，
`select` / `ignore` 内容一致。

import 排序要单独跑一次（格式化器不排序导入）：

```bash
ruff check --select I --fix
ruff format
```

CI 里做「只检查不改写」的门禁：

```bash
ruff check
ruff format --check
```

注意退出码语义：`ruff check` 为 `0` = 无违规（或全部已自动修掉）、`1` = 发现违规、`2` = 配置或参数非法/内部错误；
`ruff format --check` 为 `0` = 无需格式化、`1` = 有文件需要格式化、`2` = 异常。

存量项目迁移可以批量补抑制注释，但这是把问题变成技术债而不是消除它：

```bash
ruff check path/to/code --add-noqa
```

更多规则选择、抑制语法与冲突规则清单见 SKILL.md 与官方文档。

---

## 依赖

- pip / pipx / uv 安装路径需要 Python 环境；独立脚本与包管理器路径无此要求。
- Docker 路径需要容器运行时；SELinux 下挂载加 `:Z`。
- 配置文件读取 `pyproject.toml` 或 `ruff.toml`；两者同时存在时以就近/优先级规则为准。
- 无网络依赖（运行期不联网），无第三方服务，无 API Key。
- 不做类型检查：需要类型层面的检查要另配工具。

---

## 安全

- 不内嵌任何密钥。
- 运行期不联网、不上报任何代码或统计信息。
- 只读模式（`ruff check`、`ruff format --check`）不改动任何文件。
- 会写文件的情况都要显式触发：`ruff check --fix` 改写源码、`ruff format` 就地写回、`--add-noqa` / `--add-ignore` 插入注释。执行前请确保改动可回滚（已提交或已备份）。
- `--unsafe-fixes` 可能改变运行时行为（例如异常类型变化、注释被删除），建议先用不带 `--fix` 的形式浏览一遍再决定是否应用。
- `--watch` 会常驻监听文件变化，在共享环境里注意不要让它意外长时间运行。
- 用 `curl ... | sh` 或 `powershell -c "irm ... | iex"` 形式安装等于执行远端脚本，条件允许时优先用包管理器或先下载查看脚本内容。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`ruff`
- 仓库：https://github.com/astral-sh/ruff

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
