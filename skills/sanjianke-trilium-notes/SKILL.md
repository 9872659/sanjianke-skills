---
name: sanjianke-trilium-notes
slug: sanjianke-trilium-notes
displayName: 三剪客 · 自托管层级知识库笔记
description: "把零散笔记养成一座能长期用的知识库：Trilium Notes 的桌面版安装、服务器版 Docker 部署、数据目录与权限、反向代理与同步、备份升级，以及 ETAPI 自动化读写笔记。含镜像标签、属主、跨版本迁移与配置优先级这些容易踩的点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "笔记按树状无限分层，同一条笔记还能同时挂在多个位置；正文、代码、画布、思维导图、关系图、地图都能记，还带全文搜索、版本历史、单条加密与对外分享。可单机当桌面应用用，也可以自建服务器后用浏览器和手机访问，并且开放 REST 接口方便自动化。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 自托管层级知识库笔记

笔记软件用久了会发现一个问题：随手记的东西越来越多，但再也找不回来。Trilium Notes 的思路是**用层级结构把笔记养成体系**——一条笔记可以放在树里的任意深度，还可以同时挂在多个位置；配套全文搜索、笔记提升（hoisting）和版本历史，让「一万条笔记」仍然可用。

它同时是一座**属于你自己的知识库**：桌面版就是一个本地应用，数据在你自己的磁盘上；想多设备用，就在服务器上跑一份，用浏览器和手机访问，并配一个同步服务器。对需要自动化的人来说，它开放了 REST 接口——批量导入、批量导出、和别的系统对接都能写脚本完成。

**上游项目**：`Trilium Notes`　**仓库**：https://github.com/TriliumNext/Trilium

## 什么时候用 / 不用

**用它**：

- 用户说「笔记太乱，想整理成一个知识库」「要能长期用下去，最好数据在自己手里」。
- 需要**层级 + 多归属 + 可检索**：同一条笔记可以同时挂在多个主题下，而不是只能塞进一个文件夹；笔记堆多之后靠全文搜索、笔记提升与属性查询仍然找得回来，官方说明可支撑十万条量级的规模。
- 想要**多种笔记类型混排**：正文（含表格、图片、公式与 Markdown 自动格式化）、代码、思维导图、关系图 / 链接图、画布、地图、表格集合。
- 需要**自建服务器多端使用**：服务器版 + 浏览器访问 + 手机浏览器访问 + 自建同步服务。
- 需要**自动化**：用 REST 接口批量读写笔记、导出归档，或者用内置脚本能力做扩展；对隐私与加密有要求时（按笔记加密、TOTP 多因素、OpenID 登录）也能满足。

**不要用它**：

- **要的是多人实时协同编辑**。它面向个人知识库，分享与同步不等于多人同时编辑同一篇文档。
- **想直接当网站 / 博客系统用**。它能把笔记分享到公网，但那是「发布笔记」，不是内容管理系统。
- **要项目管理与任务编排**。有清单与待办能力，但不做看板、甘特图、团队排期这类项目管理。
- **不想装任何东西、只要在线笔记**。桌面版需要安装，服务器版需要一台机器和运维投入。
- **需要把笔记数据交给别人托管**。本项目的重点就是自己掌握数据；要托管服务就不该选它。

## 安装

**方式一：桌面版（Windows / macOS）**

从仓库的 Releases 页面下载对应平台的二进制包，解压后运行 `trilium` 可执行文件。上游同时提供稳定版与每日构建的 nightly 版，日常使用选稳定版。Linux 下可以使用发行版包管理器提供的版本，也可以下载二进制包运行；上游说明该应用也以 Flatpak 形式提供，但尚未发布到 Flathub。

**方式二：Docker Compose（服务器版，官方文档推荐路径）**

```bash
# 1. 取官方的 compose 文件
wget https://raw.githubusercontent.com/TriliumNext/Trilium/master/docker-compose.yml

# 2. 可按需先编辑 compose 文件；默认数据目录是 ~/trilium-data，服务端口 8080
# 3. 后台启动
docker compose up -d
```

启动后访问 `http://<主机>:8080` 使用浏览器界面（与桌面版基本一致）。

**方式三：不用 Compose，直接跑容器**

```bash
# 拉取指定版本；官方明确建议避免 latest 标签
docker pull triliumnext/trilium:v0.91.6

# 只允许本机访问（适合放在反向代理后面）
sudo docker run -t -i -p 127.0.0.1:8080:8080 -v ~/trilium-data:/home/node/trilium-data triliumnext/trilium:v0.91.6

# 允许任意来源访问
docker run -d -p 0.0.0.0:8080:8080 -v ~/trilium-data:/home/node/trilium-data triliumnext/trilium:v0.91.6
```

官方镜像覆盖 AMD64、ARMv7 与 ARM64/v8 三种架构。

**方式四：源码运行（开发用途）**

```bash
git clone https://github.com/TriliumNext/Trilium.git
cd Trilium
pnpm install
pnpm run server:start        # 默认 http://localhost:8080
```

**移动端**

官方说明：手机 / 平板可以直接用移动浏览器访问服务器版的移动界面；仓库里另有 Android 与 iOS 的第三方原生客户端可供选择，使用前请自行评估。

## 常用操作

**1. 起服务并确认入口**

```bash
docker compose up -d
docker ps
```

默认端口 `8080`，默认数据目录 `~/trilium-data`；两者都能在 compose 文件里调整。

**2. 自定义数据目录与属主**

rootful 镜像里的数据目录是 `/home/node/trilium-data`：

```bash
docker run -d -p 0.0.0.0:8080:8080 -v ~/YourOwnDirectory:/home/node/trilium-data triliumnext/trilium:v0.91.6
```

要让落盘文件的 uid/gid 与宿主机用户一致，用 `USER_UID` / `USER_GID` 环境变量——**官方说明 rootful 镜像不支持 `--user` 指令**：

```bash
docker run -d -p 8080:8080 -e "USER_UID=1001" -e "USER_GID=1001" -v ~/trilium-data:/home/node/trilium-data triliumnext/trilium:v0.91.6
```

如果时区不对，非 compose 部署还需要加上 `TZ` 环境变量。

**3. 用无 root 镜像运行（更小的权限面）**

```bash
docker pull triliumnext/trilium:rootless           # 基于 Debian 的默认无 root 镜像
docker pull triliumnext/trilium:rootless-alpine    # 体积更小的 Alpine 版本

docker run -d --name trilium -p 8080:8080 -v ~/trilium-data:/home/trilium/trilium-data triliumnext/trilium:rootless

# 需要指定 UID/GID 时
docker run -d --name trilium -p 8080:8080 --user $(id -u):$(id -g) \
  -v ~/trilium-data:/home/trilium/trilium-data triliumnext/trilium:rootless
```

注意：**无 root 镜像里的数据目录是 `/home/trilium/trilium-data`**，不是 rootful 镜像的 `/home/node/trilium-data`。用 Compose 时官方给了 `docker-compose.rootless.yml`，并支持 `TRILIUM_UID` / `TRILIUM_GID` / `TRILIUM_DATA_DIR` 三个变量。

**4. 改端口、开 HTTPS、配同步服务器**

配置既可以用数据目录下的 `config.ini`，也可以用环境变量；**优先级是环境变量 > config.ini > 默认值**。常见项（默认值取自官方配置文档）：

```bash
TRILIUM_NETWORK_PORT=8080               # 服务端口，默认 8080
TRILIUM_NETWORK_HOST=0.0.0.0            # 绑定地址，默认 0.0.0.0
TRILIUM_NETWORK_HTTPS=true              # 开启 HTTPS
TRILIUM_NETWORK_CERTPATH=/path/to/cert.pem
TRILIUM_NETWORK_KEYPATH=/path/to/key.pem
TRILIUM_NETWORK_TRUSTEDREVERSEPROXY=true
TRILIUM_NETWORK_CORSALLOWORIGIN=https://myapp.com
TRILIUM_SYNC_SYNCSERVERHOST=https://sync.example.com
TRILIUM_GENERAL_NOBACKUP=false          # 关闭自动备份
TRILIUM_LOGGING_RETENTIONDAYS=30        # 日志保留天数，默认 90
```

**5. 用 ETAPI 读写笔记**

先在界面的「设置 → ETAPI」里生成 token，然后：

```bash
TOKEN=<你的 ETAPI token>
SERVER=http://localhost:8080

# 读一条笔记的 HTML 内容
curl "$SERVER/etapi/notes/<NOTE_ID>/content" -H "Authorization: $TOKEN"

# 把一条笔记导出成 zip
curl -H "Authorization: $TOKEN" -X GET "$SERVER/etapi/notes/<NOTE_ID>/export" --output "out/<NOTE_ID>.zip"
```

官方说明：认证头除了 `ETAPITOKEN` 这种写法，从 0.93.0 起也支持 `Bearer ETAPITOKEN`；从 v0.56 起还支持 Basic 认证，用户名固定为 `etapi`、密码就是那个 token。token 也可以在服务端用 `/auth/login` 接口获取。

**6. 找内置帮助与升级**

在应用里按 `F1` 可以直接打开与在线文档一致的内置帮助。升级到新版本时，官方单独有一页升级指引；用容器化部署时，思路是拉取目标版本镜像后以相同的卷与参数重建容器——**跨版本升级前先备份数据目录**。

**7. 从旧血统迁移**

官方说明：从旧仓库迁移到当前仓库**没有特殊迁移步骤**，按常规方式安装后它会直接使用你已有的数据库。但版本兼容有分界——**到 v0.90.4（含）为止的版本与旧血统兼容，之后的版本递增了同步版本，因此无法直接迁移**。跨越这条线的场景要先确认版本关系。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 更新镜像后同步失效、或多端出现异常 | 用了 `latest` 标签，官方明确警告它可能把实例自动升到新的次版本，进而打乱同步 | 生产与多端同步场景**固定具体版本标签**（官方示例形如 `v0.91.6`），不要用 `latest` |
| `--user` 指定用户不生效或报错 | 官方说明 **rootful 镜像不支持 `--user` 指令** | 改用 `USER_UID` / `USER_GID` 环境变量；只有无 root 镜像才用 `--user` |
| 数据目录挂在 SMB/CIFS 共享上后出现异常 | 网络文件系统的锁与权限语义与本地盘不同 | 按官方提示在挂载时加上 `nobrl` 与 `noperm` 两个挂载选项 |
| 容器起不来、数据目录不可写 | 宿主目录属主与容器内运行用户的 UID/GID 不一致 | rootful 用 `USER_UID` / `USER_GID`；无 root 用 `TRILIUM_UID` / `TRILIUM_GID`，并把两者设成宿主目录的属主 |
| 换了无 root 镜像后找不到数据 | 无 root 镜像的数据目录是 `/home/trilium/trilium-data`，与 rootful 的 `/home/node/trilium-data` 不同 | 按镜像变体改成正确的容器内路径，或用 `TRILIUM_DATA_DIR` 显式指定 |
| 重建容器后笔记全没了 | 没有把数据目录映射到宿主机 | 必须做卷映射；`docker stop` 再重建容器不会丢数据，但删掉未映射的容器就会 |
| 改了 `config.ini` 却不生效 | 配置优先级是环境变量 > `config.ini` > 默认值，环境变量把文件值盖掉了 | 先确认有没有同名环境变量；两者只保留一个来源 |
| 找不到 `config.ini` | 它不在应用安装目录，而在**数据目录**里，且要首次启动创建数据库之后才会出现 | 到数据目录（默认 `~/trilium-data`）里找；首次启动前不存在是正常的 |
| 跨大版本迁移后同步版本不匹配 | v0.90.4 之后的版本递增了同步版本，无法与旧血统直接互迁 | 先确认两端版本关系，按官方升级 / 迁移文档处理，迁移前备份数据目录 |
| 直接把服务暴露在公网 | 服务器版默认开启认证，但公网暴露仍需要 HTTPS 与访问控制 | 别把 `TRILIUM_GENERAL_NOAUTHENTICATION` 设成 `true`；用反向代理 + HTTPS，并参考官方的反向代理与信任代理配置 |
| 端口 8080 被别的服务占用 | 默认端口是 `8080` | 改 `TRILIUM_NETWORK_PORT` 或调整容器端口映射，并同步修改反向代理配置 |
| 非 Compose 部署时时间显示不对 | 容器时区与宿主不一致 | 加 `TZ` 环境变量（取值形如 `Asia/Shanghai`） |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 服务器版对外提供 Web 界面与 ETAPI；自建同步服务需要出网访问同步端点；桌面版与同步 / 分享功能同样需要网络 |
| 读取文件 | 是 | 读取数据目录中的数据库与配置；导入 Markdown / 笔记归档时读取源文件；读取 TLS 证书与私钥 |
| 写入文件 | 是 | 写入数据目录（数据库、日志、自动备份、附件）；导出与导入功能会写文件；`TRILIUM_GENERAL_NOBACKUP` 为 `false` 时会自动生成备份 |
| 凭证 | 是 | ETAPI token、服务登录账号与密码、开启 TOTP 或 OpenID 时的对应密钥与客户端凭据。**本 Skill 不内嵌任何密钥**，token 请自行生成并按密钥管理 |
| 子进程 / 后台常驻 | 是 | 服务器版是常驻进程（容器承载），需要开机自启与重启策略；桌面版为图形应用；源码方式运行需要 Node 与 pnpm 环境 |

## 触发场景

- 「笔记太乱，想搭一个自己的知识库」
- 「要用 Docker 部署 Trilium，手机也能看」
- 「笔记数据要留在自己机器上」
- 「想用接口批量导出 / 导入笔记」
- 「多设备同步怎么配」
- 「容器起不来 / 数据目录不对，帮我看看」

## 能力边界

**覆盖**：

- 笔记组织：任意深度的树状结构，单条笔记可克隆到多个位置；属性（标签 / 关系）用于组织、查询与脚本化；笔记提升与快速跳转。
- 笔记类型：所见即所得正文（表格、图片、公式、Markdown 自动格式化）、源代码笔记（语法高亮）、思维导图、关系图与链接图、画布、地图（含坐标点与轨迹）、表格集合。
- 检索与历史：全文搜索、笔记版本历史（可回溯 revisions）。
- 安全：按笔记粒度的加密（受保护笔记）、TOTP 多因素、OpenID Connect 登录。
- 同步与分享：与自建同步服务器同步，也支持第三方托管同步服务；笔记可对外分享发布。
- 迁移与互通：支持从 Evernote 导入，支持 Markdown 的导入与导出；提供网页剪藏工具。
- 自动化：ETAPI（REST 接口，自 v0.50 起）用于批量读写与导出；内置脚本能力可做自定义扩展；另有指标导出便于接入监控面板。
- 部署形态：桌面应用（Windows / macOS / Linux）、服务器 + 浏览器、移动浏览器界面、容器化（含无 root 镜像变体）。
- 界面：内置深色主题并支持用户自定义主题；界面提供包括简体中文、繁体中文在内的多种语言。
- 规模：官方说明在可用性与性能上可支撑十万条量级的笔记。
- 可定制：侧边栏按钮、自定义组件等界面级定制。

**不覆盖**：

- 不做多人实时协同编辑；分享与同步都不等于多人同时编辑同一篇笔记。
- 不做内容管理系统 / 博客平台；「分享笔记」与「运营一个网站」是两件事。
- 不做项目管理（看板、甘特图、团队排期、工时）这类协作排期能力。
- 不提供托管服务；服务器、域名、证书、备份策略都由使用方自备。
- 不提供模型能力；界面里即便有与 AI 相关的入口，也需要你自己接入外部服务。
- 不保证第三方客户端与第三方同步托管服务的可用性与安全性，需使用方自行评估。
- 不提供数据的合规托管承诺；自行部署意味着合规责任也在使用方。

## 依赖条件

- 桌面版：Windows / macOS / Linux 桌面环境；从 Releases 下载对应平台包。
- 服务器版（容器）：Docker；镜像覆盖 AMD64、ARMv7、ARM64/v8。
- 服务器版（源码）：Node 环境与 pnpm。
- 数据目录：必须映射到宿主机并纳入备份，默认 `~/trilium-data`；容器内路径随镜像变体不同（rootful 为 `/home/node/trilium-data`，无 root 为 `/home/trilium/trilium-data`）。
- 端口：默认 `8080`。
- 浏览器：官方说明当前只对最新版本的 Chrome 与 Firefox 做过支持与测试。
- 多端同步：需要一个同步服务器（可自建）；官方提示使用第三方客户端时注意同步版本必须匹配。
- 可选：反向代理与 TLS 证书（对外提供 HTTPS）、OpenID 身份提供方（启用 OpenID 登录时）。

## 已知限制

- 官方明确警告不要使用 `latest` 标签：它可能把实例自动升到新的次版本，从而打乱同步配置。
- 版本兼容有分界：到 v0.90.4（含）为止与旧血统兼容，之后的版本递增了同步版本，不能直接互迁。
- rootful 镜像不支持 `--user` 指令，需要改用 `USER_UID` / `USER_GID`；rootful 与无 root 镜像的数据目录路径也不相同，切换时容易配错。
- `config.ini` 位于数据目录且首次启动后才生成，配置优先级是环境变量 > 文件 > 默认值，排查「改了没生效」要先看环境变量。
- 浏览器支持范围较窄，官方只对最新版本的 Chrome 与 Firefox 做过测试。
- 上游迭代很快，镜像标签、环境变量与界面位置都可能变化；**执行前请以官方文档与当前版本的配置说明为准**。
- 具体版本号、发布日期与 star 数请以仓库页面实时信息为准，本 Skill 不做断言。

## 自检清单

- [ ] 已确定部署形态：桌面版还是服务器版（容器 / 源码）。
- [ ] 容器部署使用了**具体版本标签**，没有用 `latest`。
- [ ] 数据目录已映射到宿主机，并已加入备份计划。
- [ ] 宿主目录属主与容器内 UID/GID 一致：rootful 用 `USER_UID`/`USER_GID`，无 root 用 `TRILIUM_UID`/`TRILIUM_GID`。
- [ ] 确认了当前镜像变体对应的容器内数据目录路径（`/home/node/...` 还是 `/home/trilium/...`）。
- [ ] 端口无冲突；对外访问时反向代理与 HTTPS 已配好，且没有把免认证开关打开。
- [ ] 需要多端同步时，同步服务器地址与版本关系已确认（`v0.90.4` 这条分界线要留意）。
- [ ] 使用第三方客户端时，已确认其同步版本与服务端匹配。
- [ ] 用 ETAPI 前已生成 token，并确认认证头写法（`ETAPITOKEN` / `Bearer` / Basic）。
- [ ] 升级前已备份数据目录，并知道跨版本升级需要额外确认版本关系。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/TriliumNext/Trilium | 上游仓库（安装与完整文档以它为准） |
| https://docs.triliumnotes.org/user-guide/setup/server/installation/docker | 官方 Docker 安装文档（镜像变体、数据目录与权限、环境变量的出处） |
| https://docs.triliumnotes.org/user-guide/advanced-usage/etapi | 官方 ETAPI 文档（token 获取、认证方式与示例命令的出处） |

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
