# occ 核心命令参考

`occ` 是这套服务端的命令行入口。主机安装时先切到程序目录、以 Web 用户身份执行；容器部署时统一走 `docker compose exec owncloud occ <命令>`，且**不要**加 `php` 前缀。

通用形态：

```
occ [options] command [arguments]
```

通用选项（所有命令都接受）：`-h/--help`、`-q/--quiet`、`-V/--version`、`-n/--no-interaction`、`--no-warnings`、`-v|-vv|-vvv/--verbose`，以及 `--ansi` 与 `--no-ansi`。

多数列表型命令支持 `--output=plain|json|json_pretty`，可覆盖的命令包括 `status`、`check`、`app:list`、`config:list`、`encryption:status`、`encryption:list-modules`。

运行身份对照（主机安装）：

| 发行版 | HTTP 用户 |
|---|---|
| Debian / Ubuntu | `www-data` |
| Fedora / CentOS | `apache` |
| Arch Linux | `http` |
| openSUSE | 用户 `wwwrun`，组 `www` |

Web 服务器如果用了非默认 PHP 版本，`occ` 必须用同一个版本执行。

---

## 状态与自检

```bash
occ check                 # 检查服务器环境的依赖是否齐全
occ status                # 安装状态与版本；可加 --output=json_pretty
occ -V                    # 只显示版本
occ list                  # 列出全部可用命令
occ help maintenance:mode --help    # 看单个命令的用法与选项
```

---

## 应用管理

```bash
occ app:list [搜索模式] [--enabled|--disabled] [--shipped=true|false] [-m]
occ app:enable <app>
occ app:disable <app>
occ app:getpath <app>
occ app:check-code <app>
```

`DAV`、`FederatedFileSharing`、`Files`、`Files_External` 这几个应用无法被禁用。

---

## 后台任务调度

```bash
occ background:ajax       # 用 ajax 跑后台任务
occ background:cron       # 用系统 cron 跑（生产推荐）
occ background:webcron    # 用外部 webcron 服务触发
```

---

## 配置读写

`system` 相关子命令读写配置文件，`app` 相关子命令读写数据库。

```bash
occ config:list [app] [--private]        # 默认隐藏密码等敏感值，--private 才显示
occ config:system:get <name>
occ config:system:set <name> [--value=...]
occ config:system:delete <name>
occ config:app:get <app> <name>
occ config:app:set <app> <name> --value=... [--type=boolean] [--update-only]
occ config:app:delete <app> <name> [--error-if-not-exists]
occ config:import <filename.json>        # 也可用管道：occ config:import < backup.json
```

---

## 用户管理

```bash
occ user:add [--password-from-env] [--display-name=...] [--email=...] [-g|--group=...] <uid>
occ user:list [搜索模式] [-a <属性>] [-s]
occ user:list-groups <uid>
occ user:delete <uid> [-f|--force]
occ user:disable <uid>
occ user:enable <uid>
occ user:modify <uid> <displayname|email> <value>
occ user:resetpassword [--password-from-env] [--send-email] [--output-link] <uid>
occ user:lastseen <uid>
occ user:inactive <天数>
occ user:report
occ user:setting <uid> [<app> [<key>]] [--value=...] [--delete]
occ user:sync [选项] [<后端类名>]
occ user:move-home <uid> <新位置的父目录>
occ user:home:list-dirs
occ user:home:list-users [path] [--all]
```

要点：

- `user:list` 的 `-a` 可用属性有 `uid`、`displayName`、`email`、`quota`、`enabled`、`lastLogin`、`home`、`backend`、`cloudId`、`searchTerms`；`-s` 表示全部属性。
- `--password-from-env` 从环境变量 `OC_PASS` 读密码，只有以真正的 root 运行才有效（`sudo` 会清掉环境变量）。
- `user:add` 的 uid 只允许字母、数字、`-`、`_`、`@`。
- 用户主目录不能迁到 `/tmp`、`/var/tmp` 这类临时目录；目标目录不能已经包含同名用户子目录。
- `user:sync` 的后端类名可以写短名：`ldap`、`samba`、`shibboleth`；`-m` 决定外部后端里已消失的账号是 `disable` 还是 `remove`。

---

## 组管理

组名区分大小写。

```bash
occ group:add <组名>
occ group:list [搜索模式]
occ group:add-member --member <用户> --member <用户> <组名>
occ group:list-members <组名>
occ group:remove-member --member <用户> <组名>
occ group:delete <组名>
```

重复添加或移除不存在的成员不会报错，方便写脚本。

---

## 文件操作

```bash
occ files:scan [--all] [--path=<路径>] [--group=<组>] [--groups=<组1,组2>|--groups=组] [--unscanned] [--repair] [--quiet] [<uid>...]
occ files:cleanup
occ files:check-cache <uid> <文件> [--remove]
occ files:checksums:verify [-r|--repair] [-u|--user=<用户>] [-p|--path=<路径>]
occ files:remove-storage [<storage-id>...] [--chunk-size=<值>] [--show-candidates]
occ files:transfer-ownership [--path=<路径>] [-s|--accept-skipped-shares] [--destination-use-user-folder] <原用户> <新用户>
occ files:troubleshoot-transfer-ownership [all|invalid-owner|invalid-initiator] [-f|--fix] [-u|--uid=<用户>]
```

要点：

- `files:scan` 的路径要写成 `"用户/files/路径"`、`"用户/files/挂载名"` 或 `"用户/files/挂载名/路径"` 之一；`--path`、`--all`、`--group`、`--groups` 与位置参数互斥，只能给一个。
- 扫描只适用于 POSIX 文件系统；对象存储（如 S3）以数据库为准，不能靠扫描同步。
- 这些命令在单用户维护模式下不可用。
- `files:transfer-ownership` 只转移发出的分享，收到的分享不转移；文件会落到新用户目录下形如 `transferred from <原用户> on <时间戳>` 的目录里，且只带最新版本。
- `files:remove-storage` 风险极高：先切单用户模式、先备份数据库、先用 `--show-candidates` 核对再删。

---

## 维护与升级

```bash
occ maintenance:mode --on|--off
occ maintenance:singleuser --on|--off
occ maintenance:repair [--list] [-s|--single=<步骤类名>] [--include-expensive]
occ maintenance:data-fingerprint
occ maintenance:update:htaccess
occ maintenance:mimetype:update-db [--repair-filecache]
occ maintenance:update-js
occ maintenance:install [--database=...] [--database-name=...] [--database-host=...] [--database-user=...] [--database-pass=...] [--database-table-prefix=...] [--admin-user=...] [--admin-pass=...] [--data-dir=...]
occ upgrade
```

要点：

- `maintenance:repair` 需要先进入维护模式；`--single` 的类名必须加引号，否则会报「找不到修复步骤」。
- `maintenance:install` 只在安装状态为 false 时可用，装完会自动变成不可用。
- `maintenance:data-fingerprint` 用于恢复备份之后，让客户端知道服务端回退了，从而重新比对文件。
- 容器部署启动时会自动执行升级流程；手工安装需要自己按顺序跑。

---

## 日志、安全与其他

```bash
occ log:manage --level <级别>
occ log:owncloud --path <日志路径>
occ integrity:check-core
occ security:certificates            # 列出已导入的证书
occ security:certificates:import <证书文件>
occ security:certificates:remove <证书名>
occ dav:sync-system-addressbook
occ db:convert-type <类型> <用户> <主机> [<数据库名>]
occ trashbin:cleanup [--all-users] [<用户>...]
occ versions:cleanup [<用户>...]
occ encryption:status
occ encryption:encrypt-all
occ encryption:decrypt-all
occ files_external:list [<用户>]
```

具体选项与默认值随版本变化，以 `occ help <命令>` 的实时输出为准。
