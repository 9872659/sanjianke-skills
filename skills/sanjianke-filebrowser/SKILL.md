---
name: sanjianke-filebrowser
slug: sanjianke-filebrowser
displayName: 三剪客 · 网页版文件管理器
description: "filebrowser：网页版文件管理器 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "filebrowser：网页版文件管理器 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文件管理
  - 转换
---

# 三剪客 · 网页版文件管理器

一个二进制文件丢到服务器上，指一个目录，打开浏览器就能上传、下载、预览、改名、删文件——这就是它的全部价值。
它把「我不想教同事用 SFTP」这件事解决了：给个网址和账号，对方就能拿到文件，还能按用户划分各自能看到的范围。
单个可执行文件、自带一个嵌入式数据库存用户和配置，不依赖外部数据库服务，所以部署成本极低。
**必须先说一件重要的事：上游项目已归档，不再发新版、也不再修安全问题。**用它可以，但要按「不维护软件」的前提来用。

**上游项目**：`filebrowser`　**仓库**：https://github.com/filebrowser/filebrowser

## 什么时候用 / 不用

**用它**：

- 要给非技术同事 / 客户一个**浏览器入口**去取放文件，不想让他们装客户端、也不想开 SFTP 账号。
- 在一台内网机器上快速搭一个文件共享页，要求**部署简单**、单文件、不额外装数据库。
- 需要**多用户 + 各自可见范围**：每个账号限制在自己的目录里，权限（下载、上传、删除、改、重命名）逐项开关。
- 需要在受限网络里做一个**轻量文件投递箱**（比如收素材、收日志），配好上传目录和权限就够了。
- 临时场景：今天要给人传一批文件，装个服务比配一堆 SSH 密钥快。

**不要用它**：

- 要**直接暴露到公网**。上游的收尾说明明确说了不要这么做——它有无法修复的会话/JWT 缺陷，泄漏的令牌在过期前一直有效，登出和改密码都吊销不掉。
- 需要**长期、有人维护、会跟安全补丁**的方案。它已归档，之后发现的漏洞不会再修。
- 需要**团队协作**功能（在线编辑、评论、版本历史、在线 Office），或者需要**桌面端自动双向同步**。它只是一个网页文件浏览器，不是协作套件也不是同步盘。
- 目标环境对合规要求高（金融/医疗等需要持续漏洞响应）。归档状态本身就是不合格项。
- 只是**自己一个人**在服务器上搬文件。终端工具更快，没必要起个 Web 服务。

## 安装

**macOS / Linux（Homebrew）**

```bash
brew tap filebrowser/tap
brew install filebrowser
filebrowser -r /path/to/your/files
```

**Linux / macOS（官方下载脚本，自动取对应平台最新版）**

```bash
curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash
filebrowser -r /path/to/your/files
```

**Windows（PowerShell）**

```powershell
iwr -useb https://raw.githubusercontent.com/filebrowser/get/master/get.ps1 | iex
filebrowser -r /path/to/your/files
```

**Docker（裸 Alpine 镜像，推荐用于隔离部署）**

```bash
docker run \
    -v filebrowser_data:/srv \
    -v filebrowser_database:/database \
    -v filebrowser_config:/config \
    -p 8080:80 \
    filebrowser/filebrowser
```

镜像里默认用户是 UID 1000、GID 1000。用 bind mount 把宿主目录挂进去时，**Docker 不会替你改权限**，宿主目录必须对该 UID 可读写，否则会各种报错。

**Docker（s6 overlay 镜像，可指定运行用户）**

```bash
docker run \
    -v /path/to/srv:/srv \
    -v /path/to/database:/database \
    -v /path/to/config:/config \
    -e PUID=$(id -u) -e PGID=$(id -g) \
    -p 8080:80 \
    filebrowser/filebrowser:s6
```

`/srv` 是要展示的文件根目录，`/config` 放 `settings.json`，`/database` 放 `filebrowser.db`；后两者不存在会自动初始化。

**手动下载二进制**

从发行版页面下载对应平台的文件，给可执行权限后直接运行即可，它没有运行时依赖。

**首次启动**

数据库不存在时会进「快速初始化」模式：自动建库、建一个初始用户，**随机密码只会在控制台打印一次**。地址和用户名密码都在启动日志里，务必第一时间记下来；错过了就只能删库重来。
更稳妥的做法是初始化前先用 `config init` 把配置定好（见下）。

## 常用操作

**1. 用命令行初始化配置与数据库（推荐，比快速初始化可控）**

```bash
filebrowser -d /etc/filebrowser/filebrowser.db config init
filebrowser -d /etc/filebrowser/filebrowser.db config set \
  --address 0.0.0.0 --port 8080 --root /srv/data --locale zh-cn
```

`config set` 只改你点名的项，其余保持不变；想看当前配置用 `config cat`，导出/导入用 `config export` / `config import`。

参数**不只有命令行形式**：除 `--config`（指定配置文件路径）之外，所有 flag 都能用环境变量给，前缀 `FB_` + flag 名的 UPPER_SNAKE_CASE。例如 `--disablePreviewResize` 对应 `FB_DISABLE_PREVIEW_RESIZE`。
取值优先级从高到低：命令行 flag > 环境变量 > 配置文件 > 数据库值 > 默认值。
配置文件不指定时，它会在 `./`、`$HOME/`、`/etc/filebrowser/` 里找 `.filebrowser.{json,toml,yaml,yml}`。

**2. 建用户，并按目录范围 + 权限逐项收口**

```bash
filebrowser -d /etc/filebrowser/filebrowser.db users add alice '一个足够长的密码' --perm.admin=false
filebrowser -d /etc/filebrowser/filebrowser.db users ls
filebrowser -d /etc/filebrowser/filebrowser.db users update alice --scope /srv/data/alice
```

`--scope` 决定这个账号能看到哪棵树；权限开关有 `--perm.create`、`--perm.delete`、`--perm.download`、`--perm.execute`、`--perm.modify`、`--perm.rename`、`--perm.share`、`--perm.admin`。
只让人下载、不给改的只读账号，就是把 `delete`/`modify`/`rename`/`create`/`execute` 都关掉。

**3. 起服务**

```bash
filebrowser -d /etc/filebrowser/filebrowser.db -r /srv/data -a 0.0.0.0 -p 8080
```

常用启动参数（完整清单见官方命令文档）：

| 参数 | 作用 |
|---|---|
| `-a, --address` | 监听地址，默认 `127.0.0.1` |
| `-p, --port` | 监听端口，默认 `8080` |
| `-r, --root` | 相对路径的根，默认 `.` |
| `-d, --database` | 数据库路径，默认 `./filebrowser.db` |
| `-c, --config` | 配置文件路径 |
| `-b, --baseURL` | 部署在子路径时用 |
| `-l, --log` | 日志输出，默认 `stdout` |
| `--disableExec` | 关掉命令执行功能，**默认就是 true** |
| `--tokenExpirationTime` | 会话超时，默认 `2h` |
| `--cacheDir` | 文件缓存目录 |
| `-t, --cert` / `-k, --key` | TLS 证书与私钥 |
| `--socket` | 用 unix socket 监听（不能与 address/port/cert/key 同用） |

**4. 哈希密码**

要给别的系统或配置里塞已经算好的密码哈希：

```bash
filebrowser -d /etc/filebrowser/filebrowser.db hash '你的密码'
```

**5. 用 systemd 常驻**

```ini
[Unit]
Description=filebrowser
After=network.target

[Service]
User=filesvc
ExecStart=/usr/local/bin/filebrowser -d /etc/filebrowser/filebrowser.db -r /srv/data -a 127.0.0.1 -p 8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

注意监听地址写 `127.0.0.1`，让它躲在反向代理后面，而不是自己直接对外。

**6. 备份与迁移**

它只要两样东西：数据库文件（`filebrowser.db`）和配置文件（`settings.json`）。定期复制这两个 + 你的数据目录即可完成迁移。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| **上游已归档，不再修安全问题** | 项目已于 2026-09-01 归档，最后一个计划中的版本已经发完 | 当成「无人维护软件」用：**不要直接暴露公网**，放到会终止 TLS 并自带认证的反向代理后面；用非特权账号跑；只挂载要对外的那一个目录 |
| 登出 / 改密码之后，旧会话仍然能用 | 会话是自包含 JWT 而不是服务端标识，**无法吊销**；刷新令牌还能重复兑换 | 这是已知且不会修的问题。把会话超时（`--tokenExpirationTime`）调短，把令牌当密码对待；发现泄漏就换密钥/重建账号，别指望登出能止损 |
| 开了命令执行功能后主机被拿下 | 命令执行 / runner / hooks 这个功能在历史上有大量漏洞，官方结论是需要重写才能安全 | **保持关闭**（`--disableExec` 默认就是 true，别用 `--disableExec=false` 打开）。一旦打开，等于给了对方一个 shell |
| 快速初始化时控制台一闪而过，密码没记住 | 随机生成的初始密码**只在控制台打印一次** | 没记住就只能删掉数据库重来。生产环境建议先用 `config init` + `users add` 显式建库建用户 |
| 容器起了但上传/删除都报错，日志是权限问题 | bind mount 的宿主目录权限不匹配容器内用户（默认 UID/GID 1000） | 用 `chown` 把宿主目录给到对应 UID/GID；或者用 s6 镜像并通过 `PUID`/`PGID` 指定用户 |
| 改了配置文件但没生效，或改了某项别的项被重置 | 取值优先级是 flag > 环境变量 > 配置文件 > 数据库 > 默认值；且只有一部分选项能走配置文件和环境变量，其余只存在于数据库里；`config init` 会整体重置 | 先 `config cat` 看实际生效值，确认没被 flag 或环境变量盖掉；只改点名项要用 `config set` 而不是 `config init`，数据库里的选项必须用 `config set` / `config import` 改 |
| 服务在子路径下打开白屏 / 静态资源 404 | 没设 `--baseURL` | 按实际挂载路径设置 `-b` |
| 反向代理后登录状态一直掉 | 代理没正确传头部，或者用了多个实例导致会话不共享 | 修正代理配置；多实例部署用 `--redisCacheUrl` 共享缓存 |
| `--followExternalSymlinks` 打开后能看到范围外的文件 | 该选项明确标注为不安全 | 除非完全清楚风险，否则保持关闭 |
| 缩略图/预览很吃 CPU，机器被打满 | 图片预处理是 CPU 密集的 | 调 `--imageProcessors`；或按需关掉 `--disableThumbnails` / `--disablePreviewResize` / `--disableImageResolutionCalc` |
| 修改了文件系统里的文件，页面没更新 | 文件缓存 | 清 `--cacheDir` 指定目录，或把缓存关掉（留空即禁用） |
| 大文件上传中断需要重传 | 分片上传参数不合适 | 调 `--tus.chunkSize` 与 `--tus.retryCount` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 它本身是 HTTP 服务，必须监听端口对外提供页面；反向代理场景下可只监听 127.0.0.1 |
| 读取文件 | 是 | 这是核心：读取被指定根目录下的文件用于列表、预览、下载、缩略图 |
| 写入文件 | 是 | 上传、新建、改名、移动、删除文件；写数据库（用户与配置）与缓存目录 |
| 凭证 | 是 | 用户密码以哈希形式存在自带数据库里；会话令牌（JWT）是访问凭据；可选 TLS 证书与私钥。**数据库文件等同于全部账号凭据，要按敏感文件保护** |
| 子进程 / 后台常驻 | 是 | 常驻进程提供 Web 服务；图片处理走内部协程/线程池；若启用命令执行功能还会拉起外部命令（**该项默认关闭且不建议开启**）；`--auth.method=hook` 时会调用外部认证程序 |

## 触发场景

- 「给个网址让我同事自己下载文件，别让我配 SFTP」
- 「怎么用浏览器管理服务器上的某个目录」
- 「filebrowser 怎么加用户、怎么限制每个人只能看自己的文件夹」
- 「filebrowser 的初始密码在哪看，忘了怎么办」
- 「Docker 起了 filebrowser 但上传报错 / 权限不对」
- 「有没有单文件就能跑起来的网盘页面」

## 能力边界

**覆盖**：

- 浏览器内的文件管理界面：列表、上传、下载、新建、改名、移动、复制、删除、预览。
- 多用户与按目录范围（`--scope`）、按操作维度的权限控制。
- 单文件交付：自带嵌入式数据库存用户与配置，不需要外部数据库服务。
- 命令行管理面：初始化配置、读写配置、增删改查用户、生成密码哈希、规则管理。
- 部署形态：二进制直跑、Homebrew、下载脚本、Docker（裸镜像与 s6 镜像）、unix socket 监听、TLS 直连或反代后置。
- 与外部认证挂钩（如 `auth.method` 的 hook / proxy 模式）。

**不覆盖**：

- **持续维护与安全响应**——项目已归档，这是它最大的边界。
- 桌面端 / 移动端的**自动同步**；它只有网页界面。
- 团队协作类功能：在线共同编辑、评论、审阅、版本历史、在线 Office。
- 文件内容处理：不转格式、不转码、不压缩打包。
- 细粒度的分享链接与过期控制、外部存储挂载这类能力（那是更重的方案才有的）。
- 高可用与集群：它面向的是单实例轻量部署。
- 本 Skill 不覆盖已归档版本的历史漏洞逐一排查——只给「如何安全地不维护使用」的边界。

## 依赖条件

- 运行环境：单文件可执行，无语言运行时依赖；几乎任何 Linux 发行版、macOS、Windows 都能跑。
- 存储：一个数据库文件（默认 `filebrowser.db`）与一个配置文件（`settings.json`）；不需要外部数据库。
- 一个要对外提供的目录，以及**符合容器/服务运行用户权限**的读写权限。
- Docker 方式：Docker 引擎 + 卷或 bind mount；bind mount 的宿主目录权限必须匹配容器内 UID/GID。
- 生产建议：一个会终止 TLS 并做认证的反向代理。
- 账号 / Key：不需要第三方 Key；初始管理员账号由快速初始化生成，或用 `users add` 自建。
- 可选：TLS 证书与私钥、Redis（多实例共享缓存）。

## 已知限制

1. **项目已归档**（2026-09-01），不再有功能更新与安全修复，最后一批计划中的版本已经发布完毕。
2. **会话不可吊销**：登出、改密码、续期都不会让已签发的令牌失效，同一刷新令牌可被重复兑换；泄漏的令牌在过期前一直有效。
3. **命令执行功能不安全**：历史上跨多个公告的漏洞都出在这里，官方结论是需要重写；默认关闭，请保持关闭。
4. 官方明确建议**不要直接暴露到互联网**，要放在做 TLS 终止与自身认证的反向代理后面，以非特权用户在容器内运行，只挂载必要目录。
5. 图片缩略图/预览计算是 CPU 密集的，大量图片的目录会明显吃 CPU，需要按需关闭或限制处理并发。
6. 会话是自包含的，多实例部署需要额外的共享缓存（Redis）才能一致。

## 自检清单

- [ ] 已确认可以接受「上游已归档、不再修安全问题」这一前提
- [ ] 服务**没有**直接监听公网，前面有反向代理做 TLS 与认证
- [ ] 运行在非特权账号（容器内非 root）下，且只挂载了要对外的那一个目录
- [ ] `--disableExec` 保持默认的关闭状态，没有改成 `false`
- [ ] `--tokenExpirationTime` 已按风险调短，团队知道令牌泄漏要按密码泄漏处理
- [ ] 已用 `config cat` 确认实际生效的 address / port / root / baseURL 与预期一致
- [ ] 初始管理员密码已记录；或已用 `config init` + `users add` 显式建库建用户
- [ ] 每个用户都用 `--scope` 圈定了可见目录，权限项按最小必要开启
- [ ] 数据库文件与配置文件已纳入备份，且权限仅服务账号可读
- [ ] bind mount 的宿主目录权限已匹配容器内 UID/GID

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/filebrowser/filebrowser | 上游仓库（安装与完整文档以它为准） |
| https://github.com/filebrowser/filebrowser/tree/master/docs | 官方文档目录（安装、部署、命令参考原文） |
| https://github.com/filebrowser/filebrowser/blob/master/docs/cli/filebrowser.md | 顶层命令与全部启动参数 |

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
