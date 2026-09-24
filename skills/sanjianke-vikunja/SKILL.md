---
name: sanjianke-vikunja
slug: sanjianke-vikunja
displayName: 三剪客 · 开源任务与项目管理
description: "Vikunja：自己部署、数据自己拿着的任务与项目管理工具。含 Docker / Docker Compose / 发行版软件包 / 二进制四种装法、文件权限与公网地址两个必设项、命令行工具（诊断、备份还原、迁移、修复、建用户）、API v1 与 v2 的差异、过滤器语法、Webhook 签名校验与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "自托管的待办与项目管理服务：前后端打包成一个二进制或容器，支持项目层级、多人协作、CalDAV 与 API 对接。含安装、必须配置的几项、CLI 运维命令、v1/v2 接口差异、Webhook 与数据备份还原，以及权限、CORS、Webhook 出网等常见坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 开源任务与项目管理

团队需要一个「事情记在哪、谁负责、什么时候到期」的地方，但把任务清单交给外部服务，就意味着数据在别人机器上，也意味着哪天对方涨价、改规则、停服你都得跟着走。Vikunja 的定位就是这件事的反面：装在你自己的服务器上，数据存在你自己的数据库和文件夹里，想拿走随时导出。

它的形态很省事——接口和前端被打包进**一个可部署的二进制或容器**，所以只需要装一样东西。对外是网页应用，对内提供数据库、附件、评论、提醒、多视图、标签、团队协作这些常规能力，同时开放 API、CalDAV 和 Webhook，方便接进你已有的工具链。

**上游项目**：`Vikunja`　**仓库**：https://github.com/go-vikunja/vikunja

## 什么时候用 / 不用

**用它**：

- 用户说「想自己搭一个任务 / 待办 / 项目管理服务」，要求数据落在自己的服务器上。
- 需要一个能被程序驱动的任务系统：要调 API 建任务、要 Webhook 在任务变化时通知你的服务、要 CalDAV 让日历客户端同步。
- 团队原来用在线看板 / 待办工具，现在想要可控、可迁移、能自己备份的方案，并且需要从旧工具把数据搬过来。
- 要按项目层级组织工作（父项目套子项目）、要标签、要负责人和截止日期这类基础协作要素，但不想要一套重型的企业平台。
- 运维一台服务器就够了，希望「一个二进制 + 一个数据库」这种简单结构，而不是拆成七八个服务。
- 需要一个**不依赖第三方账号**的登录体系，同时保留接入统一身份认证（OpenID 等）的余地。

**不要用它**：

- **只要个人记几条待办**。为一个清单去维护数据库、备份、域名和证书，运维成本远高于收益，手机上装个本地待办应用更合适。
- **要求实时协同编辑**。它是任务管理，不是文档协作；像在线文档那样的多人同时打字、光标跟随这类能力不在它的范围里。
- **要开箱的企业级管控**。管理面板、审计日志、时间追踪这类能力不属于开源版本，需要单独的商业授权。
- **团队小到用表格就够，且没人愿意维护服务器**。托管版或直接用表格，都比「自建但没人管」的结果好。
- **期望它替代即时通讯或会议**。它没有聊天、音视频、日程排会这类能力。
- **指望它自带全文检索增强**。默认的检索能力有限，想要更强的全文搜索需要换用带扩展的数据库镜像，这属于额外部署决策。

## 安装

### 方式一：Docker（最快跑起来）

Vikunja 以一个容器提供接口和前端，默认监听 `3456`。先用最简单的形态验证跑不跑得通：

```bash
mkdir $PWD/files $PWD/db
chown 1000 $PWD/files $PWD/db
docker run -p 3456:3456 -v $PWD/files:/app/vikunja/files -v $PWD/db:/db vikunja/vikunja
```

**两个必设项**：默认配置开了 CORS，而 CORS 需要知道你的公网地址，所以要么设置公网地址环境变量，要么关掉 CORS：

```bash
# 二选一
VIKUNJA_SERVICE_PUBLICURL=http://<你的公网地址>/
VIKUNJA_CORS_ENABLE=false
```

`files` 目录必须让容器内的进程可写。容器默认以用户 `1000`、无属组运行；`PUID` / `PGID` 这类其他镜像的惯例在这里**没有任何作用**，要换运行用户就用 Docker 的 `--user` / compose 的 `user:`。

### 方式二：Docker Compose + 数据库（推荐给生产）

把数据库放到独立容器里，配上健康检查与自动重启，是最常用的形态：

```yaml
services:
  vikunja:
    image: vikunja/vikunja
    environment:
      VIKUNJA_SERVICE_PUBLICURL: http://<the public ip or host where Vikunja is reachable>
      VIKUNJA_DATABASE_HOST: db
      VIKUNJA_DATABASE_PASSWORD: changeme
      VIKUNJA_DATABASE_TYPE: postgres
      VIKUNJA_DATABASE_USER: vikunja
      VIKUNJA_DATABASE_DATABASE: vikunja
      VIKUNJA_SERVICE_SECRET: <a super secure random secret>
    ports:
      - 3456:3456
    volumes:
      - ./files:/app/vikunja/files
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
  db:
    image: postgres:18
    environment:
      POSTGRES_PASSWORD: changeme
      POSTGRES_USER: vikunja
    volumes:
      - ./db:/var/lib/postgresql
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h localhost -U $$POSTGRES_USER"]
      interval: 2s
      start_period: 30s
```

```bash
mkdir $PWD/files $PWD/db
chown 1000 $PWD/files $PWD/db
docker compose up          # 前台跑，先看日志确认起来了
docker compose up -d       # 确认无误后转后台
docker compose logs        # 之后查日志
docker compose down        # 停掉整套
```

换成 MySQL / MariaDB：把 `db` 服务替换成对应镜像（MariaDB 需要显式指定 utf8mb4 字符集与排序规则），并把数据库类型环境变量改为 `mysql`。换成 SQLite：去掉 db 服务，把 `/db` 挂出来持久化即可（官方镜像已把 SQLite 路径预置为容器内的 `/db/vikunja.db`），数据库类型改为 `sqlite`。

用配置文件也可以，把它挂进容器：

```yaml
    volumes:
      - ./path/to/config.yml:/etc/vikunja/config.yml
```

注意官方镜像预置了两个环境变量（`VIKUNJA_SERVICE_ROOTPATH` 与 `VIKUNJA_DATABASE_PATH`），而**环境变量优先于配置文件**，所以在挂进去的 `config.yml` 里写 `service.rootpath` 或 `database.path` 不会生效——要改数据库位置就改宿主侧的挂载点，或直接覆盖环境变量。

### 方式三：发行版软件包

官方为 Debian 系、RPM 系（Fedora / RHEL 等）、Arch Linux、Alpine 提供仓库。以 Debian 系为例：

```bash
# 导入签名密钥
curl -fsSL https://dl.vikunja.io/repos/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/vikunja.gpg

# 添加仓库
echo "deb [signed-by=/usr/share/keyrings/vikunja.gpg] https://dl.vikunja.io/repos/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/vikunja.list

sudo apt update && sudo apt install vikunja
```

RPM 系写 `/etc/yum.repos.d/vikunja.repo` 后 `sudo dnf install vikunja`；Arch 在 `/etc/pacman.conf` 加仓库段并签名密钥；Alpine 加 apk 仓库后 `apk add vikunja`。安装后配置文件位于 `/etc/vikunja/config.yml`。

### 方式四：二进制 + systemd

从官方下载页取对应架构的压缩包，校验 GPG 签名（发布用密钥指纹 `FF054DACD908493A`）后解压：

```bash
mkdir -p /opt/vikunja
unzip <vikunja-zip-file> -d /opt/vikunja
chmod +x /opt/vikunja
sudo ln -s /opt/vikunja/vikunja /usr/bin/vikunja
```

然后写一个 systemd 服务单元，工作目录指向 `/opt/vikunja`，`ExecStart=/usr/bin/vikunja`，`Restart=always`，再 `sudo systemctl enable --now vikunja`。要绑定 1024 以下端口需要额外授予绑定特权的能力位。

### 桌面端

官方另有把网页前端打包好的桌面应用，便于在桌面设备上直接使用；它本质上还是连你自己的实例。

## 常用操作

**1. 先做一次自检，别靠猜**

```bash
vikunja doctor
```

它会依次检查系统信息、配置（配置文件路径、公网地址、JWT 密钥、CORS 来源）、数据库连通性与版本、文件存储路径与可写性、磁盘空间，以及启用后的 Redis / 邮件 / LDAP / OpenID 等可选服务。退出码 `0` 表示全部通过，`1` 表示有检查项失败。在容器里跑是：

```bash
docker exec <容器名> /app/vikunja/vikunja doctor
```

要做一串命令的话先建个别名：`alias vikunja-docker='docker exec <容器名> /app/vikunja/vikunja'`。

**2. 指向一个确定的配置文件**

从别的工作目录执行命令时，不带参数可能一个配置文件都找不到，于是回落到默认值，还按当前目录解析相对路径，看起来就像实例坏了。用 `--config` 钉住：

```bash
vikunja doctor --config /opt/vikunja/config.yml
vikunja migrate --config /opt/vikunja/config.yml
```

`--config` 对每条子命令都有效且没有简写；文件读不到会直接报错退出，而不是静默用默认值。

**3. 跑数据库迁移与回滚**

```bash
vikunja migrate                    # 执行所有未执行过的迁移
vikunja migrate list               # 列出全部迁移
vikunja migrate rollback -n <迁移 ID>   # 回滚到指定迁移
```

升级二进制后重启会自动跑必要迁移，但**升级前先看变更日志**，确认有没有需要手工处理的步骤。

**4. 备份与还原**

```bash
vikunja dump                                  # 打包配置、版本信息、全部文件与完整数据库
vikunja dump -p /backup -f my-dump.zip        # 指定目录与文件名（不以 .zip 结尾会自动补上）
vikunja restore /backup/my-dump.zip           # 从备份包还原
vikunja restore --preserve-config /backup/my-dump.zip   # 保留当前配置（换环境迁移时很有用）
```

不想用 dump 也可以按数据库类型各自导出：PostgreSQL 用 `pg_dump`、MySQL 用 `mysqldump`、SQLite 直接拷数据库文件；附件另行拷贝文件存储目录。

**5. 建用户与日常账号维护**

```bash
vikunja user create -u alice -e alice@example.com        # 不传密码会交互式询问
vikunja user list                                        # 列出所有用户
vikunja user change-status <用户 id> --disable           # 启用 / 停用账号
vikunja user reset-password <用户 id>                    # 发重置邮件
vikunja user reset-password <用户 id> --direct -p <新密码>   # 直接重置
vikunja user set-admin <用户名或 id> --admin             # 提升为实例管理员（需商业授权）
```

**6. 修复数据一致性问题**

```bash
vikunja repair projects --dry-run          # 先预演：把父项目已不存在的项目重新挂到顶层
vikunja repair task-positions --dry-run    # 预演：修复同一视图内重复的任务排序值
vikunja repair orphan-positions --dry-run  # 预演：清掉指向已删除任务 / 视图的排序记录
vikunja repair file-mime-types --dry-run   # 预演：为早期版本留下 MIME 为空的附件补类型
```

所有 `repair` 子命令都支持 `--dry-run`，把 `--dry-run` 去掉才会真正改数据。

**7. 用 API 建一个任务（v2）**

鉴权用 API 令牌（在网页端「设置 → API Tokens」创建，`tk_` 前缀）或登录得到的 JWT，放在请求头：

```bash
curl -X POST 'https://<你的实例>/api/v2/projects/1/tasks' \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "把季度复盘写完"}'
```

v2 用标准动词：创建 `POST`（返回 201）、整体更新 `PUT`、局部更新 `PATCH`、删除 `DELETE`（返回 204 且空响应体）。列表接口返回 `{"items": [...], "total": ..., "page": ..., "per_page": ..., "total_pages": ...}` 这样的信封结构。实例自己会提供接口文档：`/api/v2/docs`（交互式）与 `/api/v2/openapi.json` / `.yaml`。

**8. 过滤与排序任务**

筛选走查询参数 `filter`，字段名用下划线风格（网页界面里显示的是驼峰）：

```bash
curl -G 'https://<你的实例>/api/v1/projects/1/views/5/tasks' \
  -H "Authorization: Bearer <token>" \
  --data-urlencode 'filter=due_date < now && done = false' \
  --data-urlencode 'sort_by=priority' \
  --data-urlencode 'order_by=desc'
```

常用参数还有：`filter_include_nulls`（是否包含该字段没值的任务，默认不含）、`filter_timezone`（解析 `now` 这类相对时间用的时区）、`per_page`。支持日期运算，例如 `now+7d`、`now/d`、`now-1M/M`、`2024-03-11||+1w`。**简单文本搜索参数与 filter 互斥，不能同时用。** 通过接口引用标签和项目要用数字 ID，不能写名称；按创建者筛选时用用户名即可。

**9. 配 Webhook 把任务变化推给你的服务**

项目级 Webhook：`GET|PUT /api/v1/projects/{id}/webhooks`，删除与更新分别是 `DELETE` / `POST /api/v1/projects/{id}/webhooks/{webhookID}`。用户级 Webhook 在 `/api/v1/user/settings/webhooks` 下。

每次投递都是一条 POST，请求体形如：

```json
{
  "event_name": "task.created",
  "time": "2023-10-17T19:39:32.924194436+02:00",
  "data": { "task": {}, "doer": {} }
}
```

创建 Webhook 时设了密钥的话，请求会带 `X-Vikunja-Signature` 头，值是**原始请求体**的 HMAC-SHA256。校验步骤是：读原始 body（先别解析 JSON）→ 用密钥算 HMAC-SHA256 → 与头里值比对。分享链接令牌不能创建或管理 Webhook。

**10. 反向代理**

实例默认监听 3456，通常交给反代处理域名和证书。nginx 最小配置：

```
server {
    listen       80;
    server_name  localhost;

    location / {
        proxy_pass http://localhost:3456;
        client_max_body_size 20M;
    }
}
```

Caddy 一行就够：`vikunja.example.com { reverse_proxy 127.0.0.1:3456 }`。Apache 需要 `proxy`、`proxy_http`、`rewrite` 模块。**如果你在 Vikunja 里改了最大上传大小，反代的 `client_max_body_size` 要同步改**，否则大附件会先在代理层被拒。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 上传附件报 `open /app/vikunja/files/1: permission denied` | `files` 目录对容器内的进程不可写。容器默认以 uid 1000 运行 | 启动前 `mkdir $PWD/files && chown 1000 $PWD/files`；目录里已有文件要用 `chown -R`；用自定义用户时同步调整属主 |
| 设了 `PUID` / `PGID` 但属主没变 | 这两个环境变量是别的镜像生态的惯例，本镜像不支持 | 改用 Docker 的 `--user` 或 compose 的 `user:` 指令；官方镜像基于 scratch，没有 shell，别指望进容器里改 |
| 建账号时提示未授权，或前端调不通接口 | 默认开了 CORS，而 CORS 要求配置公网地址 | 把公网地址环境变量 / `service.publicurl` 设成浏览器真正访问的地址（带协议、带端口、结尾带斜杠），或者显式关闭 CORS |
| 首次启动就退出，日志里有 `connection refused` | 数据库容器还没就绪，Vikunja 连不上就直接退出了 | compose 里给应用服务加 `restart: unless-stopped`，它会自己重试；同时给数据库加健康检查并用 `depends_on` 的 `service_healthy` 条件 |
| 日志里出现 `Config File "config" Not Found ... Using default config.` | 它按 rootpath、`/etc/vikunja`、`~/.config/vikunja`、当前工作目录的顺序找配置，没找到 | 要么把配置放在这些位置之一，要么用 `--config` 显式钉住；注意 pin 住配置后 rootpath 默认变成该配置所在目录 |
| 挂了 `config.yml` 进去，改 `service.rootpath` / `database.path` 却没效果 | 官方镜像预置了对应环境变量，环境变量优先级高于配置文件 | 改宿主侧挂载点，或直接覆盖环境变量；别指望配置文件赢过环境变量 |
| 从别的目录执行 CLI 命令，实例看起来「空的」或报配置问题 | 没找到配置文件就回落默认值，并按当前目录解析相对路径 | 一律带上 `--config /路径/config.yml` |
| 数据导出失败，报 `mkdir .../user-export-tmp/: permission denied` 或 `/tmp/... no such file or directory` | 同样是无写权限；后一种情况是容器缺可写的 `/tmp` | 确保文件存储目录可写；必要时把宿主 `/tmp` 挂到容器 `/tmp` |
| MySQL 下迁移报 `commands out of sync. Did you run multiple statements at once?` | MySQL 后端的已知问题，官方给出的办法是重来 | `docker compose down`，删掉 `db/` 目录，再 `docker compose up -d`。这也是为什么要先在测试环境验一遍的原因 |
| `testmail` 报「not connected to SMTP server」但参数看起来没错 | 它发 SMTP `NOOP` 探活，部分极简中继不支持这个命令 | 换功能完整的 SMTP 服务器或中继；另外确认 SMTP 只在一处配置（环境变量与配置文件同时存在时，环境变量胜出） |
| 启动时看到 `failed to create modcache index dir: mkdir /.cache: permission denied` | 上游运行时的一条已知告警 | 无害，可以忽略 |
| 同机跑多个实例 / 反向代理后拿不到真实客户端 IP | IP 提取方式默认只看 TCP 对端地址 | 在代理后面把提取方式改为读取转发头，并把代理的 CIDR 段填进可信代理列表，否则限流会把所有人算成一个来源 |
| Webhook 收不到 / 只收到一次就没了 | 投递只做一次，返回 4xx、5xx 或超时都不会重试；默认超时 30 秒 | 接收端要快速应答并把后续处理异步化；需要重试就自己在接收端补队列。另外 Webhook 需要全局开启（默认开启） |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 对外提供网页与接口服务；连接受支持的数据库与缓存；发送提醒邮件；投递 Webhook 到你的服务；使用对象存储作为附件后端 |
| 读取文件 | 是 | 读取 `config.yml`、数据库文件（SQLite 时）、附件与项目背景图、日志；支持从文件读取配置值（如密码文件） |
| 写入文件 | 是 | 写入数据库、附件目录、日志；数据导出与 `dump` 会写压缩包；`restore` 会覆盖数据 |
| 凭证 | 是（环境相关） | 需要数据库口令、实例签名密钥（用于签发令牌）、可选的 SMTP 口令与对象存储密钥。这些由使用者自备；本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | 它是常驻服务：Docker 由容器托管，裸机部署通常交给 systemd；CLI 子命令为一次性执行 |
| 监听端口 | 是 | 默认监听 3456，对外发布前应放在反向代理之后 |
| 出站请求（Webhook） | 是 | 启用了 Webhook 时，实例会主动向配置的地址发起请求。多用户实例上这可能被用来探测内网服务 |

## 触发场景

- 「帮我搭一个自己托管的待办 / 任务管理服务」
- 「有没有能自己部署、数据不外流的项目管理工具」
- 「怎么把原来工具里的任务迁到自建系统」
- 「任务有变化时怎么通知我的服务 / 怎么接 Webhook」
- 「Vikunja 装完上传附件失败，报权限错误」
- 「自建实例怎么备份、怎么升级、怎么排查」
- 「怎么用 API 批量建任务、按条件筛任务」

## 能力边界

**覆盖**：

- 后端存储：PostgreSQL、MySQL / MariaDB、SQLite 三种数据库可选；可用 Redis 做缓存；换用带全文检索扩展的数据库镜像可获得更强的搜索能力（实例会自动识别）。
- 部署形态：单容器快速启动、compose 编排（应用 + 数据库 + 可选反代）、发行版软件包（Debian 系 / RPM 系 / Arch / Alpine）、二进制 + systemd、桌面端应用。
- 任务与项目：项目层级（父项目套子项目）、任务、附件、评论、提醒、标签、负责人、截止与起止时间、完成度、优先级、排序、保存的筛选器（在列表接口里表现为负数 ID 的伪项目）。
- 协作：团队与项目共享、链接分享（可关闭）、权限分级、邀请与账号管理。
- 身份认证：本地账号、TOTP 双因素、可接入 OpenID Connect、可配置 LDAP。
- 集成：REST API（v1 与 v2 两版并行）、CalDAV、Webhook（带 HMAC-SHA256 签名）、内置的若干迁移器（从其他待办服务导入）。
- 运维：CLI 提供诊断（`doctor`）、全量备份 / 还原（`dump` / `restore`）、数据库迁移与回滚、数据修复子命令、用户管理；配置支持多种文件格式与环境变量，密码等敏感值可来自文件。
- 界面与文案：多语言、可换图标与自定义 Logo、可设置的提示信息与合规链接。

**不覆盖**：

- 不提供实时协同编辑类能力（多人同时编辑同一文档那种），它的对象是任务与项目，不是文档。
- 不提供聊天、音视频会议、日历排会等服务。
- 管理面板、审计日志、时间追踪这类管控能力属于商业版本范围，开源版本不含。
- 不替你做运维：备份策略、保留周期、证书续期、升级窗口都要自己定；而且**项目删除是永久且不可撤销的**，没有回收站。
- 不自带托管服务；不想自己维护就得选择第三方托管方案。
- 移动端的支持范围有限（官方说明移动应用目前只覆盖较基础的功能）；Web 前端与桌面端是完整形态。

## 依赖条件

- **部署环境**：Docker / Docker Compose（容器方式），或一台 Linux 服务器（软件包 / 二进制方式）；官方同时提供 Windows 与 macOS 的发行包，但作为 Web 应用更适合服务器托管。
- **数据库**：PostgreSQL 12+、MySQL 8.0+ / MariaDB 10.2+ 或 SQLite 之一。默认是 SQLite；用户量上去以后官方建议改用 PostgreSQL 或 MySQL。**若用 MySQL / MariaDB 且内容含非拉丁字符，必须把数据库按 utf8 兼容配置**。
- **文件存储**：附件与背景图需要一个可写目录；也可切换到兼容 S3 的对象存储后端。
- **缓存（可选）**：Redis，用户量少时不必开。
- **邮件（可选）**：SMTP 服务，用于提醒、注册确认、密码重置。**不开邮件则所有用户都会被直接激活，且无法走密码重置流程**。
- **反向代理（可选但常用）**：nginx / Caddy / Apache 或面板类代理，用于域名与 TLS。
- **必备配置**：公网地址（或用关闭 CORS 代替）、实例签名密钥（不设则每次启动随机生成，重启后此前签发的令牌全部失效）。
- **账号与凭据**：无需第三方账号；数据库口令、SMTP 口令、对象存储密钥均由使用者自备。

## 已知限制

- **项目删除不可逆**，没有回收站或撤销机制，因此备份策略不是可选项而是必需品。
- Webhook 投递**只做一次、失败不重试**，需要可靠投递就自行在接收端做队列与重试。
- 多用户实例上，Webhook 的出站请求存在被用来探测内网的隐患；官方建议通过代理收敛出站流量。
- 配置文件与环境变量同时存在时**环境变量优先**，容器镜像又预置了部分环境变量，容易造成「改了配置不生效」的错觉。
- v1 接口在 2.4.0 后被冻结（新功能只落在 v2），按官方路线图后续大版本会先弃用再移除；新写的集成应直接基于 v2。
- 不同发布通道的定位不同：稳定版按语义化版本号发布、更新频率不固定；滚动构建包含最新开发代码、可能带缺陷，从滚动版退回稳定版官方并不推荐。
- 具体版本号、可用迁移器列表与接口字段以你的实例页面（如信息接口与 `/api/v2/docs`）和官方文档为准，此处不对版本做断言。

## 自检清单

- [ ] 已确定部署方式，并准备好对应的数据库（SQLite 还是 PostgreSQL / MySQL）。
- [ ] 启动前已创建 `files`（以及 SQLite 时的 `db`）目录并设置好属主，确认容器内用户可写。
- [ ] 已设置公网地址（含协议、端口、结尾斜杠），或明确关闭了 CORS。
- [ ] 已设置固定的实例签名密钥，避免每次重启导致所有令牌失效。
- [ ] 若使用 MySQL / MariaDB 且内容含非拉丁字符，已确认数据库字符集为 utf8 兼容。
- [ ] compose 中已配置健康检查与自动重启，避免数据库未就绪导致的应用启动失败。
- [ ] 已跑 `vikunja doctor` 且无失败项；需要时用 `--config` 钉住配置文件。
- [ ] 已明确注册策略：注册完用户后按需关闭自助注册。
- [ ] 需要邮件功能时已配置 SMTP，并用 `vikunja testmail` 验证过一次。
- [ ] 已用 `vikunja dump` 或数据库导出 + 附件拷贝跑通一次备份，并验证过还原流程。
- [ ] 升级前已阅读目标版本的变更日志，并按需备份。
- [ ] 放在反向代理后面时，已同步上传大小限制，并正确配置真实 IP 提取与可信代理段。
- [ ] 启用 Webhook 时，接收端已实现签名校验与快速应答，并考虑过重试与出站安全。
- [ ] 新写集成基于 v2 接口；仍在用 v1 的客户端已评估迁移计划。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/go-vikunja/vikunja | 上游仓库（安装与完整文档以它为准） |

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
