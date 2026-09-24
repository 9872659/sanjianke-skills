---
name: sanjianke-pre-commit
slug: sanjianke-pre-commit
displayName: 三剪客 · Git 提交前钩子管理
description: "pre-commit：Git 提交前钩子管理 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "pre-commit：Git 提交前钩子管理 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · Git 提交前钩子管理

团队里想统一格式化和基础检查，通常的结局是：有人手写一个 `.git/hooks/pre-commit` 脚本，只在他自己机器上有效；`.git/hooks` 不进版本控制，新人克隆下来什么都没有；想让没装 Node 的同事跑 ESLint，还得先劝他装 Node。这个工具把这件事变成一个可提交进仓库的配置文件：`.pre-commit-config.yaml` 里写清要用哪些钩子、锁定到哪个版本，它负责在每次提交前把对应语言的运行环境拉起来、跑完、清理干净。

它解决的是「让提交前的检查跟代码一起被版本控制，并且对所有人一致」这个问题。

**上游项目**：`pre-commit`　**仓库**：https://github.com/pre-commit/pre-commit

## 什么时候用 / 不用

**用它**：

- 要在仓库里统一代码检查与格式化（尾随空格、文件末尾换行、YAML 语法、格式化器、lint），并且希望这套配置对所有协作者生效。
- 团队里的钩子用多种语言写（Python、Node、Go、Ruby、Rust…），且不希望要求每个开发者预装这些运行时。
- 要在 CI 里跑同一套检查，而不只是本地靠自觉。
- 要周期性把钩子版本升上去：用它的自动更新命令把 `rev` 统一提到最新 tag，或者冻结成 commit 哈希。
- 要开发或试用一个新的钩子仓库，在正式写进配置之前先跑一遍试试。

**不要用它**：

- 要抓「绕过检查强行提交」的人：`git commit --no-verify` 能跳过所有钩子，这属于本地约定，不是强制门禁。
- 要跑跑得很久的重型检查（全量测试、全量构建、整库静态分析）：提交前钩子应该是秒级的，长任务放进 CI，用 `pre-push` 或 `manual` 阶段承接。
- 要管理不是 Git 仓库的项目，或者要做不带版本控制的通用任务编排：它的配置、缓存、阶段全部围绕 Git 仓库。
- 要在完全离线的环境里首次运行：第一次跑每个钩子都要联网拉取仓库和运行时，断网会直接失败。
- 要改代码逻辑或做代码修复：它只负责「调用别人写的检查工具并按退出码裁决」，自己不做代码分析。

## 安装

它的安装分两步：先装管理器本身，再把它挂进 Git 钩子。

```bash
# 1) 装管理器本身
pip install pre-commit
# 或者用 0 依赖的 zipapp：从发行页下载 .pyz 文件，然后用它替代 pre-commit 命令
# python pre-commit-#.#.#.pyz ...

# 确认版本
pre-commit --version

# 2) 在仓库里生成配置、并把钩子脚本挂进 .git/hooks
cd /path/to/your/repo
pre-commit sample-config > .pre-commit-config.yaml   # 生成一份最小配置
pre-commit install                                    # 之后每次 git commit 都会自动跑
pre-commit install --install-hooks                    # 顺手把各钩子的环境也提前装好

# 3) 可选：对所有已有文件跑一遍（新加钩子时建议先跑这个）
pre-commit run --all-files

# 4) 可选：把钩子脚本装进 Git 模板目录，让新克隆的仓库自带钩子
git config --global init.templateDir ~/.git-template
pre-commit init-templatedir ~/.git-template
```

Windows 下的模板目录写法：

```powershell
pre-commit init-templatedir $HOME\.git-template      # PowerShell
```

```bat
pre-commit init-templatedir %HOMEPATH%\.git-template
```

一份最小可用的 `.pre-commit-config.yaml`：

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v2.3.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

参数与配置项的完整清单以官方文档为准：https://pre-commit.com/

## 常用操作

```bash
# 1) 装钩子（幂等地替换掉已有脚本、并提前装好环境）
pre-commit install --install-hooks --overwrite

# 2) 手动跑：不给参数时默认只跑暂存区里的文件
pre-commit run
pre-commit run --all-files              # 全仓库所有文件（CI 里常用）
pre-commit run trailing-whitespace      # 只跑某一个钩子
pre-commit run --files a.py b/c.yaml    # 只跑指定文件

# 3) 只跑某次改动范围（pre-receive 之类场景很有用）
pre-commit run --from-ref HEAD^^^ --to-ref HEAD

# 4) 失败时顺便把差异打出来，方便直接看改了什么
pre-commit run --all-files --show-diff-on-failure

# 5) 自动把配置里的 rev 更新到最新 tag（--freeze 会写成 commit 哈希）
pre-commit autoupdate
pre-commit autoupdate --freeze
pre-commit autoupdate --bleeding-edge --repo https://github.com/pre-commit/pre-commit-hooks

# 6) 校验配置与钩子清单的合法性（CI 里当门禁用）
pre-commit validate-config
pre-commit validate-manifest

# 7) 开发新钩子：直接对本地目录或远程仓库试跑，不必先写进配置
pre-commit try-repo ../my-hook-repo my-hook-id --verbose --all-files
pre-commit try-repo https://github.com/pre-commit/pre-commit-hooks

# 8) 清理缓存（缓存会随使用越来越大）
pre-commit clean            # 清空缓存目录
pre-commit gc               # 只清掉不再被使用的仓库缓存

# 9) 临时跳过单个钩子（比整次提交都不检查更细）
SKIP=flake8 git commit -m "foo"

# 10) 卸载，恢复安装前的钩子状态
pre-commit uninstall
```

它把不同阶段的 Git 钩子都纳入了管理，例如：

```bash
# 同时装 pre-commit 和 pre-push 两个阶段
pre-commit install --hook-type pre-commit --hook-type pre-push
```

也可以在配置顶层声明默认要装哪些阶段：

```yaml
default_install_hook_types: [pre-commit, pre-push, commit-msg]
```

退出码约定：`1` 表示检测到的预期错误（钩子失败），`3` 表示意外错误，`130` 表示被 `^C` 中断。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 明明把问题改好了，钩子还是报错 | 钩子只看**暂存区**（`git add` 之后的内容），工作区里改了但没暂存，它看到的还是旧版本 | 先 `git add` 再提交；或直接 `pre-commit run --all-files` 看全仓状态 |
| 改动后钩子提示「文件被修改了」并失败 | 这是格式化类钩子的正常行为：它改好了文件，需要你重新暂存 | 把改动 `git add` 进去，再 `git commit` 一次；不要反复重试同一条命令 |
| 第一次跑特别慢，像卡住了 | 首次运行要下载钩子仓库并为每种语言创建独立环境（可能连 Node、Ruby 之类一起装） | 正常现象。可以提前 `pre-commit install --install-hooks` 预热；CI 里做好缓存 |
| 断网或内网环境直接失败 | 它需要从远端克隆钩子仓库并下载运行时 | 先在有网环境预热缓存并持久化缓存目录；或把钩子仓库镜像到内网并改 `repo` 地址 |
| `git commit --no-verify` 把检查全绕过了 | 这是 Git 自身的能力，任何本地钩子都拦不住 | 别把它当强制门禁；真正的门禁要在 CI 或服务端钩子上落实 |
| 报错说找不到配置文件 | 配置必须在**仓库根目录**，且运行时代码会把工作目录切到仓库根 | 把 `.pre-commit-config.yaml` 放在仓库根；配置文件在子目录里时用 `-c` 显式指定路径 |
| `autoupdate` 报 `rev` 解析失败 / 更新失败 | `rev` 必须是 tag 或 commit 哈希，分支名会导致解析不稳定 | 用 tag 或哈希；想让 `rev` 固定成哈希就加 `--freeze` |
| 安装后原来自己写的钩子失效了 | 默认是「迁移模式」，会把你原有的钩子包一层一起跑；但你没意识到行为变了 | 想完全替换用 `pre-commit install --overwrite`；想还原用 `pre-commit uninstall` |
| 钩子只在本地生效，同事克隆下来不跑 | 钩子脚本在 `.git/hooks` 里，不进版本控制 | 让每个人克隆后跑一次 `pre-commit install`；或用 `init-templatedir` 做全局模板 |
| 配了 `stages: [manual]` 的钩子从来不跑 | `manual` 阶段不会由任何 Git 钩子自动触发 | 手动触发：`pre-commit run --hook-stage manual <钩子id>` |
| 某个钩子总是被跳过，显示 `(no files to check)` | 它的 `files` / `types` 过滤条件不匹配任何暂存文件 | 检查该钩子的 `files` / `types` 配置，必要时用 `--files` 显式传入，或临时加 `-v` 看细节 |
| `post-commit` / `post-checkout` 这类钩子从不执行 | 这些阶段不针对文件操作，默认没有匹配文件就被跳过 | 给钩子加 `always_run: true` |
| 只想装 pre-push，结果只装了 pre-commit | 不显式指定时，安装类型取自 `default_install_hook_types`（默认只有 `pre-commit`） | 安装时加 `--hook-type pre-push`，或在配置顶层声明 `default_install_hook_types` |
| Windows 上缓存路径过长导致报错，或磁盘被缓存吃满 | 缓存目录会累积各语言环境与多份钩子仓库 | 用 `PRE_COMMIT_HOME` 把缓存指到短路径或独立盘；定期 `pre-commit gc` / `pre-commit clean` |
| 校验时报「不认识的配置键」 | 大多是缩进或键名拼错（YAML 对缩进敏感） | `pre-commit validate-config` 定位；注意 `repos` 下每一项的 `repo` / `rev` / `hooks` 三层缩进 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 首次运行与更新时克隆钩子仓库、下载各语言运行时与依赖。离线环境必须先预热缓存 |
| 读取文件 | 是 | 读取仓库内被钩子匹配到的文件内容，以及配置与钩子清单 |
| 写入文件 | 是 | 写入 `.git/hooks/` 下的钩子脚本；格式化类钩子会**直接修改**工作区文件；缓存写入 `PRE_COMMIT_HOME` 指向的目录 |
| 凭证 | 按需 | 克隆私有钩子仓库时依赖 Git 自身的凭据配置；本工具不额外存储账号密码 |
| 子进程 / 后台常驻 | 是 | 会以子进程方式调用每个钩子的可执行文件，并按需拉起语言运行环境（Docker 钩子还会调用容器引擎）。不驻留、不监听端口 |

## 触发场景

- 「提交前自动跑格式化和 lint，别再靠人工记得」
- 「这个 `.git/hooks` 脚本没法提交进仓库，换一个团队都能用的方案」
- 「同事机器上没装 Node，但要用 ESLint，能不能别让他手动装」
- 「CI 里也想跑同一套检查」
- 「这批钩子版本太旧了，帮我把 rev 统一升上去」
- 「我写了个新钩子，先在本地试跑一下，别急着写进配置」

## 能力边界

**覆盖**：

- 用一个配置文件声明钩子来源、版本与参数，把钩子安装进 Git 的多个阶段（pre-commit、pre-push、commit-msg、post-checkout 等）。
- 多语言钩子环境管理：Python、Node、Go、Rust、Ruby、Docker、docker_image、golang、dotnet、swift 等，按需建立隔离环境，不污染全局。
- 版本管理：`autoupdate` 升到最新 tag、`--freeze` 固定为 commit 哈希、`--bleeding-edge` 取默认分支最新。
- 筛选与调度：按 `files` / `exclude` / `types` / `types_or` 过滤，`always_run`、`require_serial`、`fail_fast`、`stages` 控制执行方式。
- 仓库本地钩子（`repo: local`）与元钩子（`repo: meta`），以及 `fail` / `pygrep` / `unsupported` / `unsupported_script` 这类轻量语言，用于不写复杂脚本就实现简单检查。
- 开发辅助：`try-repo` 直接试跑本地或远端钩子仓库并打印生成的配置。

**不覆盖**：

- 不做强制门禁：`--no-verify` 可以绕过，真正的强制要靠 CI 或服务端钩子。
- 不做代码检查本身：具体的 lint、格式化、静态分析能力来自被调用的钩子项目，它只负责调度与裁决。
- 不做全量测试编排、不做构建、不做部署。
- 不管理非 Git 仓库，不支持脱离 Git 使用。
- 不替你解决离线环境的依赖分发问题（镜像、内网源需要自己准备）。

## 依赖条件

- Python 3.9 及以上（pip 安装方式的前提；具体支持的最低版本以官方文档为准）。
- 一个 Git 仓库，且配置放在仓库根目录。
- 首次运行需要网络：拉取钩子仓库 + 下载对应语言的运行时。
- 用 Docker 类钩子时，需要有可用的容器引擎。
- 可选：`PRE_COMMIT_HOME` 指定缓存目录；`SKIP` 环境变量临时跳过钩子；`PRE_COMMIT_COLOR` 控制输出颜色。
- 不需要账号或 API Key，除非钩子仓库本身是私有的。

## 已知限制

- 只对暂存区内容生效，未 `git add` 的改动不会被检查（这是为了避免误报/漏报，属于设计取舍）。
- 首次运行与每次新增钩子都要联网下载，冷启动可能耗时数分钟。
- 缓存会持续增长，需要定期 `gc` / `clean`，Windows 上还要留意路径长度与磁盘占用。
- 本地钩子可被 `--no-verify` 绕过，不能当作安全边界。
- 语义上仍依赖 Git 的行为与阶段划分，某些阶段（如 post-commit）需要额外配置 `always_run` 才会执行。

## 自检清单

执行前：

- [ ] 已确认当前目录确实是 Git 仓库，且配置文件放在仓库根目录。
- [ ] 已确认这次是「安装钩子」还是「试跑」，别在用户只想试一下时直接改动 `.git/hooks`。
- [ ] 如果仓库里已有自定义钩子脚本，先提醒用户默认是迁移模式，需要完全替换就加 `--overwrite`。
- [ ] 涉及离线/内网环境时，先确认缓存是否已预热，避免直接失败。

执行后：

- [ ] 钩子失败时先分清是「真的有问题」还是「钩子自动改了文件需要重新暂存」，再决定下一步。
- [ ] 涉及 `autoupdate` 的操作，检查 `rev` 是否真的被改成了预期的 tag 或哈希。
- [ ] 提醒用户：钩子脚本不进版本控制，其他协作者克隆后需要各自跑一次安装。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/pre-commit/pre-commit | 上游仓库（源码与发行包） |
| https://pre-commit.com/ | 官方文档：安装、配置项、命令行与支持的钩子列表 |
| https://pre-commit.com/hooks.html | 官方索引的可用钩子清单 |

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
