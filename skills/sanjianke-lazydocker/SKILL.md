---
name: sanjianke-lazydocker
slug: sanjianke-lazydocker
displayName: 三剪客 · 终端 Docker 管理面板
description: "lazydocker：终端 Docker 管理面板 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "lazydocker：终端 Docker 管理面板 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · 终端 Docker 管理面板

排查容器问题最烦的不是命令难，而是来回切换窗口：`docker compose ps` 看一眼、`restart` 一下、再开一个窗口 `logs --follow`，服务一挂日志流也断了，还得重开。这个工具把容器、服务、镜像、卷、网络的状态、日志、指标图和常用动作收进**一个终端窗口**，每个动作一次按键；同时把「顺手执行的那条 docker 命令」放在设置里可改——工具栏上的 `docker compose` 用哪个写法、日志默认看多久，都由你定。

**上游项目**：`lazydocker`　**仓库**：https://github.com/jesseduffield/lazydocker

## 什么时候用 / 不用

**用它**：

- 用户说「容器又挂了，我得反复敲 docker 命令看状态和日志」，希望在一个界面里搞定看状态、看日志、重启、重建。
- 想在终端里看容器的 CPU / 内存曲线，而不是开一个浏览器面板或反复敲 `docker stats`。
- 在**远程服务器 / SSH 会话**里管 Docker：不想为看容器状态额外开 Web 端口、装图形面板。
- 需要频繁做这几件事：`up -d` / `restart` / `down` / `down --volumes` / `rebuild` / prune 清理磁盘。
- 想给团队固定一套运维动作：把常用操作写成自定义命令挂在面板里，避免每个人敲法不同、敲错环境。

**不要用它**：

- 目标环境没有 Docker（或 Docker 守护进程不可达）：这个工具本质是 Docker 的终端前端，没有 Docker 就没有任何内容可显示。
- 要管的是 **Kubernetes / Swarm 集群**、多节点编排、CI 流水线里的容器：它面向单机 Docker 与 docker compose，不解决集群场景。
- 需要多用户权限隔离、审计日志、RBAC 的团队面板：终端 TUI 做不到这些，浏览器侧的容器管理平台才是那类需求的答案。
- 想要在脚本 / CI 里自动化执行：TUI 需要交互式终端，非交互环境应直接用 `docker` / `docker compose` 命令。
- 只偶尔看一眼容器状态：直接敲 `docker ps` 更快，装个面板属于过度配置。

## 安装

前置：Docker 已安装且守护进程可访问；用 compose 功能需要 Compose（可选）。

**Windows**

```sh
scoop install lazydocker
# 或
choco install lazydocker
```

**macOS / Linux（Homebrew）**

```sh
brew install jesseduffield/lazydocker/lazydocker   # 官方 tap，更新更及时
# 或
brew install lazydocker                            # 核心仓库版本
```

**Linux 一键脚本**（默认装到 `$HOME/.local/bin`，可用 `DIR` 环境变量改目标目录）

```sh
curl https://raw.githubusercontent.com/jesseduffield/lazydocker/master/scripts/install_update_linux.sh | bash
```

拿到的脚本建议先看一眼内容再执行。

**Arch Linux（AUR）**

```sh
yay -S lazydocker
```

**有 Go 工具链时**

```sh
go install github.com/jesseduffield/lazydocker@latest
```

（源码方式：`git clone` 后进目录执行 `go install`，或用 `go run main.go` 直接编译并运行。）

**用容器跑它自己**（需要把宿主机 Docker 套接字挂进去）

```sh
docker run --rm -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /yourpath:/.config/jesseduffield/lazydocker \
  lazyteam/lazydocker
```

`/yourpath` 换成你实际用来存配置的目录。也可以做成别名：

```sh
echo "alias lzd='docker run --rm -it -v /var/run/docker.sock:/var/run/docker.sock -v /yourpath/config:/.config/jesseduffield/lazydocker lazyteam/lazydocker'" >> ~/.zshrc
```

## 常用操作

**1. 启动面板**

```sh
lazydocker
```

面板里所有操作都是「选中对象 + 一次按键」，键位随焦点面板变化；完整键位表以仓库 `docs/` 下的键位文档与界面底部提示行为准。养成习惯：`lazydocker` 本身太长，挂个别名。

```sh
echo "alias lzd='lazydocker'" >> ~/.zshrc
```

**2. 打开 / 定位配置文件**

在面板里选中左上角 project 面板，按 `o` 打开配置（如果你的默认编辑器是 vim，用 `e`）。配置路径按平台不同：

```text
Linux:   ~/.config/lazydocker/config.yml
macOS:   ~/Library/Application Support/jesseduffield/lazydocker/config.yml
Windows: C:\Users\<User>\AppData\Roaming\lazydocker\config.yml
```

**注意：改完配置必须关闭并重新打开 lazydocker 才生效。**

**3. 改「日志默认看多久 / 看多少行」**

默认只看最近一小时的日志，这是为了不给机器太大压力，也是「为什么我看不到容器日志」的最常见原因。在 `config.yml` 里放开：

```yaml
logs:
  timestamps: false
  since: '60m'   # 设成 '' 表示显示全部日志
  tail: ''       # 设成 200 表示只看最后 200 行
```

**4. 换掉底层 docker compose 命令**

有些环境里是 `docker compose`（插件式），有些是 `docker-compose`（独立二进制）。面板里所有 compose 动作都基于这一项：

```yaml
commandTemplates:
  dockerCompose: docker compose   # 独立二进制则写 docker-compose
```

**5. 加一条自定义命令（比如一键进容器 shell）**

```yaml
customCommands:
  containers:
    - name: bash
      attach: true
      command: 'docker exec -it {{ .Container.ID }} bash'
      serviceNames: []
```

可用模板变量包括 `{{ .DockerCompose }}`、`{{ .Container }}`（如 `{{ .Container.Container.ImageID }}`）、`{{ .Service }}`（如 `{{ .Service.Name }}`）。

**6. 界面适配：主面板换行、鼠标选中文字、屏幕模式**

```yaml
gui:
  wrapMainPanel: true          # 主面板自动换行（默认行为可能因 CPU 开销而关闭）
  ignoreMouseEvents: true      # 想用鼠标原生选中文字时打开
  screenMode: "normal"         # normal | half | fullscreen
  language: "auto"             # auto | en | pl | nl | de | tr
```

想临时用鼠标选中文字，也可以按住 option 再拖动。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 启动后看不到想要的容器日志 | 默认只显示最近一小时的日志（刻意设计，避免压力过大） | 在 `config.yml` 的 `logs` 段把 `since` 改大或设为 `''`（显示全部）；`tail` 控制行数 |
| 在容器里跑 lazydocker，日志和 CPU 占用看不到 | 已知问题：容器内的它在读取宿主指标/日志链路上受限 | 直接用宿主机二进制运行；或接受该限制，只在容器里做启停类操作 |
| 改了 `config.yml` 却没变化 | 配置只在启动时读取一次 | 关闭并重新打开 lazydocker |
| 所有 compose 操作报命令不存在或行为不对 | `commandTemplates.dockerCompose` 与实际环境不符（插件式 `docker compose` vs 独立 `docker-compose`） | 在 `config.yml` 里把 `dockerCompose` 改成你环境里真实可用的写法 |
| 鼠标一拖就变成点击、选不中文字 | 为了支持鼠标操作，拖拽被当成点击事件 | 按住 option 拖动选中；或在 `gui.ignoreMouseEvents` 里关掉鼠标事件 |
| 主面板长日志被截断不换行 | 换行会带来额外的 CPU 开销，所以默认不换行 | 设 `gui.wrapMainPanel: true` |
| 提示连不上 Docker / 面板空白 | Docker 守护进程没起、当前用户不在 docker 组、或 `DOCKER_HOST` 指向错误 | 先用 `docker ps` 验证宿主侧 Docker 可用，再排查套接字权限与 `DOCKER_HOST` |
| 用源码 `go run main.go` 跑起来很慢 | 每次都要现场编译 | 用 `go install` 装成二进制，或走包管理器安装 |
| Docker 自带二进制与宿主机版本不匹配（容器方式部署时） | 镜像里打包的 docker 客户端版本与宿主守护进程版本差异过大 | 官方建议：重建镜像时用 `--build-arg DOCKER_VERSION="v$(docker -v | cut -d" " -f3 | rev | cut -c 2- | rev)"` 让内置客户端版本与宿主一致 |
| 一键脚本装完找不到命令 | 默认装到 `$HOME/.local/bin`，该目录可能不在 `PATH` | 把 `$HOME/.local/bin` 加入 `PATH`，或安装时用 `DIR` 指定已有 `PATH` 目录 |
| prune 之后镜像/卷没了 | prune 类操作真的会删除容器、镜像、卷，用于回收磁盘空间 | 执行前确认选中范围；生产机器上先确认没有依赖该卷的数据 |
| 面板里某些键按了没反应 | 键位随当前焦点所在面板不同，且可在配置里自定义 | 看界面底部提示行，或查阅仓库 `docs/` 下的键位文档 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否（仅安装时） | 安装/更新需要联网；运行期不主动联网，只与本机 Docker 守护进程通信 |
| 读取文件 | 是 | 读取 `config.yml` 配置、读取容器内文件与日志、读取宿主机 Docker 套接字 |
| 写入文件 | 是 | 写入/更新 `config.yml`（面板内打开编辑时）；对容器、镜像、卷的写操作通过 Docker API 施加 |
| 凭证 | 否 | 不保存账号或 Key；继承宿主机 Docker 客户端的认证上下文（如已登录的镜像仓库凭据） |
| 子进程 / 后台常驻 | 是 | 按配置的 `commandTemplates` 调用 `docker` / `docker compose`（或 `docker-compose`）；前台 TUI，非常驻服务 |

## 触发场景

- 「Docker 容器太多了，终端里有没有类似 lazygit 的管理界面」
- 「怎么看某个容器的实时日志，不用一直敲命令」
- 「服务器上怎么看容器 CPU 内存占用」
- 「docker compose 命令到底是 `docker compose` 还是 `docker-compose`，工具能改吗」
- 「容器日志怎么看不到，是不是被截断了」
- 「磁盘被 Docker 占满了，怎么清」

## 能力边界

**覆盖**：

- 单机 Docker 与 docker compose 环境的状态总览、日志查看、指标曲线、容器/服务/镜像/卷/网络的常用操作与 prune 清理。
- attach 到容器/服务、查看镜像层关系、重启/移除/重建服务。
- 配置文件层面的行为定制：底层 compose 命令、日志时间窗与行数、界面主题与语言、屏幕模式、鼠标行为、自定义命令与镜像名前缀替换。
- Windows / macOS / Linux 平台的多途径安装，以及容器化运行方式。

**不覆盖**：

- Kubernetes、Docker Swarm 等集群编排的容器管理。
- 镜像构建流水线、CI/CD 集成；非交互环境请直接用 docker 命令行。
- 多用户权限隔离、审计日志、RBAC 等团队级权限能力。
- Web / 图形界面与远程访问：它是终端 TUI，不提供浏览器入口。
- 替代 Docker 本身的排错：网络、存储驱动、守护进程配置等底层问题仍需回到底层工具。

## 依赖条件

- 本机可用的 Docker，且当前用户有权限访问 Docker 守护进程（套接字权限/用户组）。
- 使用 compose 相关功能需要安装 Compose（可选组件）。
- 从源码构建时需要对应的 Go 工具链。
- 用容器方式运行时需要能挂载宿主机的 Docker 套接字，并准备一个存配置的目录。
- 无需任何账号、Key 或在线服务。

## 已知限制

- 只面向单机 Docker 与 docker compose，集群场景不适用。
- 在容器内运行时有已知缺陷：看不到日志与 CPU 占用。
- 配置改动只在启动时读取，修改后必须重启面板。
- 部分行为受宿主 Docker 客户端/守护进程版本差异影响，容器化部署时更明显。
- 界面是键盘驱动的 TUI，鼠标支持以牺牲原生文本选中为代价，需要按 option 拖动或关掉鼠标事件。

## 自检清单

- 执行前：确认 `docker ps` 在本机可用、当前用户有套接字权限；确认环境里 compose 的真实写法是 `docker compose` 还是 `docker-compose`。
- 执行中：涉及 prune / down / down --volumes 等破坏性操作时，先在面板里确认选中的对象范围；生产环境操作前确认有可用备份。
- 执行后：确认容器/服务状态符合预期；改过配置就重启面板再看效果；日志看不到时先检查 `logs.since` / `logs.tail`。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/jesseduffield/lazydocker | 上游仓库（安装与完整文档以它为准） |
| https://github.com/jesseduffield/lazydocker/blob/master/docs/Config.md | 配置项与自定义命令模板变量 |

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
