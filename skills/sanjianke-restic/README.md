# 三剪客 · 去重加密备份工具 Skill

restic：去重加密备份工具 的安装、常用命令与避坑要点

---

## 前置条件

- 一台要备份的机器，以及一个**能放仓库的位置**：本地另一块盘 / 另一台机器（SFTP）/ 对象存储（S3 兼容等）/ REST 服务，或者通过 rclone 接入的其它远端。本地目录和远端仓库的命令只差一个 URL 前缀。
- **仓库密码**必须由你设定并妥善保存。它是唯一的解锁凭据，没有默认值，也**没有任何找回机制**。
- 备份系统文件、保留属主与权限信息，通常需要 root / 管理员权限；只备自己的家目录则普通用户即可。
- 远端后端要满足对应前提：`sftp:` 需要 SSH 客户端且**能公钥免密登录**（否则定时任务会卡在密码提示上）；对象存储需要有效的访问密钥；`rclone:` 需要先装并配置好 rclone。
- 想挂载仓库浏览，需要 FUSE 环境（Linux 要有 `fuse` 模块和 `fusermount`，macOS 需要 FUSE-T 或 FUSE for macOS）。
- Windows 上如果用 MSYS2 / Cygwin 这类终端，输入密码可能失败，需要 `winpty` 包一层；做系统级备份建议用管理员权限安装与运行。
- 定时能力由系统提供（cron / systemd timer / 计划任务），它自身没有内置调度器。
- 不需要任何账号或 API Key（对象存储的访问密钥是你自己云账号的）。

---

## 使用

最短跑通路径，四步：

**1. 建仓库**（会让你输两遍密码，务必先想好存哪儿）

```bash
restic init --repo /srv/restic-repo
```

远端仓库只是换个位置写法：

```bash
restic -r sftp:user@host:/srv/restic-repo init
restic -r rest:http://host:8000/ init
restic -r s3:s3.us-east-1.amazonaws.com/bucket_name init
```

**2. 备份**

```bash
restic -r /srv/restic-repo backup ~/work --exclude="*.tmp" --tag daily
```

先想清楚再动手时加 `--dry-run`。第二次跑同一个源会明显更快——大部分数据被去重了，仓库里只多出变化的部分。

**3. 看和对比**

```bash
restic -r /srv/restic-repo snapshots
restic -r /srv/restic-repo diff 5845b002 2ab627a6
```

**4. 恢复（**一定要真的演练一次**）**

```bash
restic -r /srv/restic-repo restore latest --target /tmp/restore
restic -r /srv/restic-repo check
```

清理旧快照并回收空间——记住 `forget` 删引用、`prune` 才真正腾空间：

```bash
restic -r /srv/restic-repo forget --keep-daily 7 --keep-weekly 5 --keep-monthly 12 --dry-run
restic -r /srv/restic-repo forget --keep-daily 7 --keep-weekly 5 --keep-monthly 12 --prune
```

非交互场景（定时任务、脚本）用环境变量传位置与密码：

```bash
export RESTIC_REPOSITORY=/srv/restic-repo
export RESTIC_PASSWORD_FILE=/etc/restic/password
restic backup ~/work
```

更多操作（`dump`、`mount`、`key add`、从命令输出直接备份、保留策略细节）与完整坑表见 `SKILL.md`。

---

## 依赖

| 依赖 | 必要性 | 说明 |
|---|---|---|
| 官方静态二进制 | 运行时 | 用包管理器或下载二进制装好后即可运行，不依赖系统库 |
| Go 工具链 | 仅源码编译需要 | 版本要求以官方安装页为准 |
| SSH 客户端 | `sftp:` 后端需要 | 且要能公钥免密登录；自动备份不能交互输密码 |
| rclone | `rclone:` 后端需要 | 要先安装并配置好远端 |
| FUSE | `restic mount` 需要 | Linux 需 `fuse` 模块与 `fusermount`；macOS 需 FUSE-T / FUSE for macOS |
| `winpty` | Windows + MSYS2/Cygwin | 用于解决密码提示不工作的问题 |
| cron / systemd / 计划任务 | 定时备份需要 | 它本身不带调度器 |
| 对象存储凭据 | 对应后端需要 | S3 用 `AWS_*`，Azure 用 `AZURE_*`，B2 用 `B2_*`，Swift 用 `OS_*` 等 |

---

## 安全

- 不内嵌任何密钥；仓库密码与云端密钥全部由使用者自己提供。
- **仓库密码是整个方案的单点**。丢了数据就打不开，且没有任何后门或恢复通道。请存进独立的密码管理器或密钥托管，并**验证过恢复流程之后再删原始数据**。
- 备份是**客户端侧加密**的：远端服务商看到的是密文。但这不意味着可以裸奔——仓库里的数据一旦被删除或损坏，加密也救不回来，所以远端权限同样要收紧。
- 凭据不要写在命令行里（会进 shell 历史和进程列表）。用 `RESTIC_PASSWORD_FILE`、`--password-file` 或 `--password-command` 从受权限保护的文件 / 密钥库读取，并确保那个文件的权限只有运行备份的账号可读。
- **`forget` 是有破坏性的操作**。正式执行前一律先加 `--dry-run` 看清楚要删哪些；在 append-only 仓库上优先用 `--keep-within` 而不是日历策略，避免被塞入的垃圾快照把合法快照挤掉。
- `--unsafe-recover-no-free-space`、`--group-by ''`、`--unsafe-allow-remove-all`、`--insecure-no-password` 这些都是**降低安全护栏的选项**，只在明确知道后果时使用。
- `restore --delete` 会删除目标目录里快照中没有的文件。先 `--dry-run -vv` 确认。
- `--password-command`、`--stdin-from-command`、`rclone:` 后端都会**执行外部程序**。命令内容来自你的配置，不要接受外部传入。
- 备份内容里可能包含密钥、凭据、个人信息；仓库落盘位置与访问权限要按敏感数据对待。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`restic`
- 仓库：https://github.com/restic/restic

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
