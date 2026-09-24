# 三剪客 · Git 提交前钩子管理 Skill

pre-commit：Git 提交前钩子管理 的安装、常用命令与避坑要点

---

## 前置条件

- 先确认目标目录是一个 **Git 仓库**（`git rev-parse --show-toplevel` 能看到仓库根）。这个工具完全围绕 Git 工作，不在仓库里跑没有意义。
- 需要 Python 3.9 或更新版本（pip 安装方式的前提；支持的最低版本以官方文档为准）：`python --version`。
- **首次运行必须联网**：它要克隆钩子仓库，并为每个钩子创建对应语言的隔离环境（可能顺带下载 Node、Ruby 等运行时）。内网或离线环境请先在有网环境预热缓存，再持久化缓存目录。
- 如果打算用 Docker 类钩子，机器上要有可用的容器引擎。
- 钩子脚本会写进 `.git/hooks/`，该目录**不进版本控制**；每个协作者克隆后都需要自己跑一次安装。
- 如果仓库里已经有手写的钩子脚本，动手前先确认：默认安装是「迁移模式」，会保留原有钩子一起跑。

## 使用

最短跑通路径是四步：

```bash
# 1) 装管理器
pip install pre-commit
pre-commit --version

# 2) 生成一份最小配置
pre-commit sample-config > .pre-commit-config.yaml

# 3) 把所有已有文件先跑一遍（新加钩子时建议做，避免第一次提交时才发现满仓问题）
pre-commit run --all-files

# 4) 装进 Git 钩子，之后每次 git commit 自动执行
pre-commit install --install-hooks
```

一份最小配置长这样（`rev` 用 tag 或 commit 哈希，不要用分支名）：

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v2.3.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

日常最常用的几条：

```bash
pre-commit run                       # 只跑暂存区的文件（等于提交时会跑的检查）
pre-commit run --all-files           # 全仓库所有文件，CI 里常用
pre-commit run <hook-id>             # 只跑某一个钩子
pre-commit autoupdate                # 把配置里的 rev 升到最新 tag
pre-commit autoupdate --freeze       # 升版本并固定成 commit 哈希
pre-commit validate-config           # 校验配置合法性
pre-commit try-repo ../my-hooks foo --all-files    # 试跑还没写进配置的钩子
pre-commit clean                     # 清理缓存
SKIP=<hook-id> git commit -m "..."   # 只跳过某一个钩子
```

需要管理提交之外的阶段时：

```bash
pre-commit install --hook-type pre-commit --hook-type pre-push
```

配置项与命令行全集以官方文档为准：https://pre-commit.com/

## 依赖

- **运行时**：Python 3.9+（pip 安装方式）。
- **必需**：Git 仓库；配置放在仓库根目录。
- **首次运行必需**：可访问外网（克隆钩子仓库、下载语言运行时）。离线环境需要提前预热并持久化缓存。
- **按钩子类型按需**：容器引擎（Docker / docker_image 类钩子）、对应语言的工具链（它会在缓存目录里为钩子自行准备隔离环境，通常不污染全局）。
- **可选环境变量**：`PRE_COMMIT_HOME` 指定缓存目录（Windows 上路径过长时很有用）；`SKIP` 临时跳过指定钩子；`PRE_COMMIT_COLOR` 控制输出颜色；`PRE_COMMIT_USE_MAMBA` / `PRE_COMMIT_USE_MICROMAMBA` 用于 conda 类钩子。
- **不需要**：账号、API Key、GPU。

## 安全

- 不内嵌任何密钥：本 Skill 与脚本里没有 Token、密码或私钥。
- **会执行第三方代码**：跑钩子时它会克隆钩子仓库并按声明的方式建立环境、执行其中的可执行文件。请只使用可信来源，并尽量锁定到具体的 tag 或 commit 哈希。
- **会修改工作区文件**：格式化类钩子（尾随空格、文件末尾换行、代码格式化）是**直接改写文件**的，提交前请确认改动符合预期。
- **会写入两个位置**：`.git/hooks/` 下的钩子脚本，以及缓存目录（默认在用户级缓存路径下，可用 `PRE_COMMIT_HOME` 改）。缓存会随使用持续增长，建议定期 `pre-commit gc` 或 `pre-commit clean`。
- **不是强制门禁**：`git commit --no-verify` 可以跳过全部钩子。需要强制约束时请在 CI 或服务端钩子上落实。
- **私有仓库的凭据**：克隆私有钩子仓库时依赖 Git 自身的凭据配置，本工具不额外存储账号密码。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pre-commit`
- 仓库：https://github.com/pre-commit/pre-commit

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
