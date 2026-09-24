---
name: sanjianke-restic
slug: sanjianke-restic
displayName: 三剪客 · 去重加密备份工具
description: "restic：去重加密备份工具 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "restic：去重加密备份工具 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文件管理
  - 转换
---

# 三剪客 · 去重加密备份工具

它解决的问题很朴素：**把数据完整地备出去，而且下次只传变化的部分，存到哪儿都行、存进去还是加密的**。
工作方式是内容寻址 + 去重：文件被切成块、算指纹，只存没见过的块，所以同一份内容在多个快照里只占一份空间。
仓库位置可以是一个本地目录，也可以是 SFTP、REST 服务、对象存储，甚至通过 rclone 走几十种远端；客户端侧加密，服务端看到的永远是密文。
对人来说，它的价值在「一次备份 = 一个快照」，回滚到某一天就是恢复那个快照，不用自己拼增量链。

**上游项目**：`restic`　**仓库**：https://github.com/restic/restic

## 什么时候用 / 不用

**用它**：

- 要**定期备份**一批目录（代码、文档、数据库导出），希望第二次之后只传增量，不想每次全量。
- 要把备份**存到远端**：SFTP、S3 兼容对象存储、REST 服务、或者别的云存储，并且希望传输前后都是加密的。
- 需要**按时间点回滚**：保留最近 N 天 / N 周 / N 月各一份，其余自动淘汰。
- 要**校验备份可信**：定期检查仓库内部结构有没有坏，确认能恢复。
- 做**迁移或临时取文件**：把仓库挂载成文件系统浏览，或者把单个文件/整目录导出来。

**不要用它**：

- 要的是**实时同步**而不是备份（多台机器之间保持一致）。它不做双向同步，两边的删改不会互相传播。
- 要的是**块级 / 整机镜像**级别的灾备（裸机恢复、引导扇区）。它是文件级备份，装不了操作系统。
- 目标是**给别人共享文件 / 提供下载**。它没有 Web 服务端，仓库也不是给人直接看的。
- 要的是**持续增量复制到另一个在线目录**（比如 rsync 那样的镜像）。它的仓库是自有格式，不能当普通目录用。
- 只是想把一个文件复制到隔壁目录。用 `cp`。

## 安装

**Linux（发行版包管理器）**

```bash
apk add restic            # Alpine
sudo pacman -S restic     # Arch
apt-get install restic    # Debian / Ubuntu
sudo dnf install restic   # Fedora
emerge restic             # Gentoo
sudo zypper install restic   # openSUSE
```

RHEL / CentOS Stream 走 EPEL：

```bash
sudo dnf install epel-release
sudo dnf install restic
```

**macOS**

```bash
brew install restic
pkgx install restic        # 或者
sudo port install restic   # MacPorts
```

**Windows**

```powershell
scoop install restic
winget install --exact --id restic.restic --scope Machine
```

`--scope Machine` 会装到 `%ProgramFiles%`，需要管理员权限；不加则装到用户目录。做系统级备份时建议用 Machine 作用域。

**跨平台通用（Mise）**

```bash
mise use -g restic@latest
```

**Docker**

```bash
docker pull restic/restic
docker pull ghcr.io/restic/restic
```

容器方式有两个必须注意的点：一是**必须给固定主机名**（`--hostname`），否则每次随机主机名会让快照分组、增量判断全乱；二是容器支持用 `NICE`、`IONICE_CLASS`、`IONICE_PRIORITY` 环境变量降优先级：

```bash
docker run --hostname backup-host \
  -e NICE=20 -e IONICE_CLASS=2 -e IONICE_PRIORITY=7 \
  -v /host/data:/data -v /host/repo:/repo \
  ghcr.io/restic/restic snapshots -r /repo
```

**官方二进制**

从发行版页面下载对应平台的文件即可直接运行，可以原地自升级：

```bash
restic self-update
```

`self-update` 会用发布页上的签名校验下载文件，但**执行者必须有权替换那个二进制文件**；想存到别的文件名用 `--output`。

**源码编译**（需要 Go，版本要求见官方文档）

```bash
git clone https://github.com/restic/restic
cd restic
go run build.go
```

交叉编译（生成的都是静态链接、不依赖系统库的单文件）：

```bash
go run build.go --goos windows --goarch amd64
go run build.go --goos linux --goarch arm --goarm 6
```

**补全脚本**（bash / zsh / fish / powershell 都支持）

```bash
sudo ./restic generate --bash-completion /etc/bash_completion.d/restic
sudo ./restic generate --zsh-completion /usr/local/share/zsh/site-functions/_restic
```

powershell 的补全路径要按本机 `$PROFILE` 位置调整，见官方安装页示例。

## 常用操作

以下示例统一用 `/srv/restic-repo` 作为仓库、`~/work` 作为数据源，换成你自己的路径即可。

**1. 建仓库（初始化）**

```bash
restic init --repo /srv/restic-repo
```

它会让你输两遍密码。**这个密码丢了，数据就永久打不开了**——仓库里没有任何后门。
远端仓库只是换个 URL 前缀：

```bash
restic -r sftp:user@host:/srv/restic-repo init
restic -r rest:http://host:8000/ init
restic -r s3:s3.us-east-1.amazonaws.com/bucket_name init
```

对象存储的凭据走环境变量，例如 S3 兼容服务：

```bash
export AWS_ACCESS_KEY_ID=<访问密钥ID>
export AWS_SECRET_ACCESS_KEY=<密钥>
restic -r s3:https://server:port/bucket_name init
```

**2. 备份一个目录（带排除）**

```bash
restic -r /srv/restic-repo backup ~/work --exclude="*.c" --exclude-file=excludes.txt --tag daily
```

排除文件一行一个模式，`#` 开头的行和空行会被忽略，支持 `**` 跨目录通配（但 `**` 必须是完整路径分量，写 `foo/**/bar` 而不是 `foo**`）。
想先看会做什么、不实际写仓库，加 `--dry-run`。

**3. 看有哪些快照、以及两个快照相差什么**

```bash
restic -r /srv/restic-repo snapshots
restic -r /srv/restic-repo diff 5845b002 2ab627a6
restic -r /srv/restic-repo diff 5845b002:/restic 2ab627a6:/restic   # 只比某个子目录
```

`diff` 默认只比内容，比元数据要加 `--metadata`；输出左侧的 `+` `-` `M` `T` `U` 分别表示新增、删除、内容变化、类型变化、元数据变化。

**4. 恢复**

```bash
restic -r /srv/restic-repo restore 79766175 --target /tmp/restore
restic -r /srv/restic-repo restore latest --path /home/user/work --host myhost --target /tmp/restore
restic -r /srv/restic-repo restore 79766175 --target /tmp/restore --include /home/user/work/foo
```

只恢复某个子目录时用 `<快照ID>:<子目录>` 语法，此时 `--include` / `--exclude` 的路径要**相对于子目录**写。
恢复行为由 `--overwrite` 控制：`always`（默认，内容一致就只补差异部分）、`if-changed`（大小和 mtime 一致就当没变，更快）、`if-newer`、`never`。
`--delete` 会删掉目标目录里快照中没有的文件——**先跑 `--dry-run -vv` 看清楚再动手**。

**5. 取单个文件 / 挂载浏览**

```bash
restic -r /srv/restic-repo dump latest production.sql > production.sql
restic -r /srv/restic-repo dump latest /home/other/work > restore.tar
restic -r /srv/restic-repo dump -a zip latest /home/other/work > restore.zip
mkdir /mnt/restic && restic -r /srv/restic-repo mount /mnt/restic
```

`dump` 也可以把数据库导出直接喂给下一个程序：`restic -r /srv/restic-repo dump latest production.sql | mysql`。
`mount` 只在 Linux / macOS / FreeBSD 可用，且**挂载点不能与仓库目录重叠**（会让 FUSE 读自己的后端文件而卡死）。

**6. 按保留策略清理，并回收空间**

```bash
restic -r /srv/restic-repo forget --keep-daily 7 --keep-weekly 5 --keep-monthly 12 --dry-run
restic -r /srv/restic-repo forget --keep-daily 7 --keep-weekly 5 --keep-monthly 12 --prune
```

`forget` 只是删快照记录，**真正回收空间要靠 `prune`**；加 `--prune` 可以在删了快照时自动跑一次。
`prune` 期间仓库被锁定，备份跑不进来，要留出时间窗口。
仓库爆满导致 `prune` 腾不出空间时，用 `prune --max-repack-size 0` 尽量少用临时空间。

**7. 校验仓库**

```bash
restic -r /srv/restic-repo check
```

建议定期跑（比如每次 `prune` 之后），确认内部结构没坏。

**8. 给仓库加多个密码（多人 / 多机访问）**

```bash
restic -r /srv/restic-repo key add
```

**9. 非交互场景传密码**

```bash
export RESTIC_REPOSITORY=/srv/restic-repo
export RESTIC_PASSWORD_FILE=/etc/restic/password
restic backup ~/work
```

也可以用 `--password-command` / `RESTIC_PASSWORD_COMMAND` 指定一个外部程序去取密码。

**10. 从命令输出直接备份（推荐）**

```bash
restic -r /srv/restic-repo backup --stdin-from-command -- mysqldump --host example mydb
restic -r /srv/restic-repo backup --stdin-filename production.sql --stdin-from-command -- mysqldump --host example mydb
```

它会把命令的退出码当结果：命令失败就取消备份、**不生成快照**。这就是它比管道写法强的地方。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 备份成功但空间没释放，或仓库满了 `prune` 腾不出空间 | `forget` 只是丢掉快照引用，数据还在仓库里；`prune` 需要临时空间才能搬数据 | 必须跑 `prune`（或 `forget --prune`）且别和备份撞时间；空间紧张时用 `prune --max-repack-size 0`，只有在无计可施时才用 `--unsafe-recover-no-free-space`（失败会让仓库暂时不可用，可能要清空 `index/` 后 `restic repair index`） |
| 密码丢了，数据彻底打不开 | 仓库是端到端加密的，没有任何找回机制 | 没有救。把密码存进独立的密码管理器 / 密钥库，并**验证一次恢复流程**再删原始数据 |
| 第二次备份没有变快，反而全量重扫；换了挂载点之后又开始全量扫 | 前后用了不同的路径写法（绝对 vs 相对）、mtime/ctime/inode 变了，或挂载点路径变了——容器挂载点的设备号从不参与判断，但路径变化仍会被当成新文件 | 固定用同一种写法（建议进到目录里 `backup .`）并保持挂载点稳定；必要时用 `--parent` 显式指定父快照，或用 `--group-by` 调整分组口径 |
| 传了 `--exclude` 但某个文件还是被备进去了 | 显式写在命令行上的备份源**不受排除规则约束** | 排除只作用于目录**内部**的内容。想让某个文件也被排除，就不要把它作为命令行参数直接传（用 `--files-from` 之类的清单方式） |
| 备份跑完退出码是 3，脚本以为失败了 | 3 表示「有源文件读不了」，但仍会生成一份**不完整**的快照 | 0 成功、1 致命错误（没快照）、3 部分文件读不了（有快照）。脚本要分别处理，别把 3 当 1 |
| Windows 上用 MSYS2 / Cygwin 输入密码报错，且 Windows 上 `--ignore-*` 系列选项无效 | 它只支持 Windows 默认控制台交互；Windows 上变更检测只认路径、大小与修改时间 | 用 `winpty restic ...` 包一层；Windows 上想让文件被重扫只有 `--force` 有效，其余忽略类选项会被接受但不起作用 |
| `check` / `prune` 说仓库被锁 | 有另一个进程正在操作，或上次异常中断留下了锁 | 确认没有并发进程后按提示解锁；不要让备份和 `prune` 同时跑 |
| 用 `--stdin` 管道备份，数据库连不上却"成功"了 | 它无法判断 stdin 数据是否完整，上游命令失败会被吞掉 | 改用 `--stdin-from-command`；若坚持用 `--stdin`，必须开 `set -o pipefail` 并自己检查管道退出码 |
| 远端是 S3 兼容存储但列举对象报错，或用虚拟主机风格的 S3 地址连不上 | 部分实现对 `ListObjectsV2` 支持不完整；且它只认 path-style 地址 | 临时用 `-o s3.list-objects-v1=true` 走旧接口；把 `bucket.s3.region.amazonaws.com` 改写成 `s3.region.amazonaws.com/bucket` |
| 想删光所有快照却删不掉，或用 `--unsafe-allow-remove-all` 删过头 | 出于安全，它拒绝执行「空策略」；该选项又必须配合过滤条件 | `--keep-last 0` 不会删任何东西；要全删就 `--keep-last 1` 再手工删最后一个，或用 `--unsafe-allow-remove-all` 并同时带上主机/路径/标签过滤条件，执行前先 `--dry-run` |
| append-only 仓库上跑保留策略，合法快照被误删 | 攻击者可以塞入时间戳更新的垃圾快照，把策略"挤"掉合法快照 | append-only 场景优先用 `--keep-within` 而不是 `--keep-daily` 之类的日历策略 |
| CIFS/SMB 上放仓库或从 SMB 备数据出问题，或在容器里用 `rclone:` 后端被拒绝执行 | 老内核与该共享方式有兼容问题；出于安全考虑不做隐式执行当前目录里的程序 | SMB 场景换个后端，或按官方说明设置 `GODEBUG=asyncpreemptoff=1`；rclone 用 `-o rclone.program=/绝对路径/rclone` 显式指定 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（仅远端仓库时） | 访问 SFTP / REST / S3 / 对象存储等远端仓库；本地目录仓库不需要网络 |
| 读取文件 | 是 | 扫描并读取要备份的文件与元数据；恢复和校验时读仓库 |
| 写入文件 | 是 | 写仓库目录（本地时）、写缓存、恢复到目标目录、写锁文件与索引 |
| 凭证 | 是 | 仓库密码（`RESTIC_PASSWORD*`）；远端后端的访问密钥（`AWS_*`、`AZURE_*`、`B2_*`、Swift 的 `OS_*` 等）；这些必须放在权限受控的文件或环境里 |
| 子进程 / 后台常驻 | 是 | 不常驻，但会拉起外部程序：SFTP 后端会调 `ssh`，`rclone:` 后端会拉起 rclone，`--password-command` 会执行你指定的命令，`--stdin-from-command` 会执行备份命令，`restic mount` 会启动 FUSE 服务 |

## 触发场景

- 「怎么把服务器上的数据定期备份到对象存储 / 另一台机器」
- 「备份只传增量怎么做，不要每次全量」
- 「恢复到昨天的版本怎么操作」
- 「备份占的空间越来越大，怎么清理旧快照」
- 「这个备份能不能验证是好的 / 能不能真的恢复」
- 「仓库密码忘了怎么办」

## 能力边界

**覆盖**：

- 文件级备份与恢复：目录、单文件、符号链接、设备文件、FIFO，保留属主/权限/时间戳等元数据。
- 内容去重与压缩（仓库版本 2 起支持压缩），多主机共用一个仓库以提升去重率。
- 客户端侧加密与完整性校验；`check` 校验仓库内部结构。
- 多种后端：本地目录、SFTP、REST 服务、S3 及 S3 兼容存储、Azure Blob、Google Cloud Storage、Swift、B2，以及通过 rclone 接入的其它服务。
- 快照管理：标签、`diff` 对比、保留策略、`prune` 回收空间、`forget` 删快照。
- 灵活取数据：`restore` 恢复、`dump` 导出到标准输出、`mount` 挂载浏览、按 `<快照>:<子目录>` 粒度操作。
- 从命令输出或标准输入创建快照（含数据库导出这类场景），并支持 Windows 卷影复制（VSS）。

**不覆盖**：

- **双向同步**或多机在线镜像；它不传播删除，不做冲突合并。
- **块级 / 裸机镜像备份**，不能用来还原操作系统分区。
- 把仓库当普通目录直接使用——仓库是自有格式，别手工改动里面的文件。
- **调度**：它没有内置定时器，定时要交给系统的 cron / systemd / 计划任务，或第三方配置管理工具。官方也提醒**重复调度时要自己防止实例重叠**。
- 决定「该备份什么、保留多久」这类策略判断；策略要你自己定并用 `--keep-*` 表达。
- 加密之外的数据脱敏、合规审查等安全治理工作。

## 依赖条件

- 运行时：官方二进制是静态链接的，不依赖系统库；用包管理器装时按发行版依赖自动解决。
- 源码编译：需要 Go 工具链，版本要求以官方安装页为准。
- `restic mount`：Linux 需要 `fuse` 内核模块且 `fusermount` 在 `PATH` 里；macOS 需要 FUSE-T 或 FUSE for macOS；FreeBSD 可能要先装 FUSE 并 `kldload fuse`。
- 远端后端：`sftp:` 需要 SSH 客户端且**能用公钥免密登录**（自动备份场景不能交互输密码）；`rclone:` 需要装并配好 rclone。
- 凭据：仓库密码必须存在（没有默认值）；对象存储后端需要对应的访问密钥环境变量。
- 权限：备份系统文件、保留属主与权限信息通常需要 root / 管理员；Windows 上完整备份安全描述符需要 `SeBackupPrivilege` 或以管理员运行。

## 已知限制

1. **密码不可找回**。仓库密码丢失等于数据丢失，这是设计使然。
2. 变更检测依赖路径、mtime、ctime、inode 等元数据；路径写法变化、跨挂载点、基于 FUSE 的文件系统都可能让增量判断失效并重扫。
3. `prune` 是有成本的操作：会锁仓库、可能需要把部分数据下载回来重打包，远端仓库尤其耗时；用 `--max-unused` / `--repack-cacheable-only` 可以在空间与时间之间取舍。
4. `forget` 的策略按 host / paths 分组生效；用 `--group-by ''` 会关闭分组，风险更高，要清楚自己在做什么。
5. Windows 上的元数据能力受系统限制：完整安全描述符、符号链接恢复都需要特定特权。
6. 仓库版本影响兼容性：仓库版本 2 需要较新的客户端才能访问（版本对应关系以官方仓库版本表为准）。
7. 它假设仓库有足够空间完成本次操作；空间不足时不会生成快照，但仓库里可能留下额外数据。

## 自检清单

- [ ] `restic version` 可用，版本满足你要用的仓库版本要求
- [ ] 仓库已 `init`，且**密码已存进独立的凭据管理位置**（不是只记在脑子里）
- [ ] 远端后端已实测过连通（SFTP 免密登录通了 / 对象存储凭据能列举桶）
- [ ] 先跑一次 `--dry-run` 确认排除规则和新增内容符合预期
- [ ] 备份后 `restic snapshots` 能看到新快照，`restic check` 通过
- [ ] **做过一次真实恢复演练**：恢复到一个临时目录，确认文件内容和权限正确
- [ ] 保留策略在正式执行前用 `--dry-run` 过一遍，确认要删的是哪些
- [ ] 定时任务里**不会出现两个实例并发**，且 `prune` 与备份不撞时间
- [ ] 脚本正确区分退出码 0 / 1 / 3，没有把「部分文件读不了」当成完全成功

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/restic/restic | 上游仓库（安装与完整文档以它为准） |
| https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html | 建仓库与各后端 URL 写法 |
| https://restic.readthedocs.io/en/stable/040_backup.html | 备份、排除规则、变更检测、退出码 |
| https://restic.readthedocs.io/en/stable/050_restore.html | 恢复、dump、mount 与覆盖行为 |
| https://restic.readthedocs.io/en/stable/060_forget.html | 保留策略、prune 与 append-only 注意事项 |

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
