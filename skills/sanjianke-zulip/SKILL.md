---
name: sanjianke-zulip
slug: sanjianke-zulip
displayName: 三剪客 · 话题制团队聊天服务器
description: "自己托管一套团队聊天服务：Ubuntu/Debian 一键安装器、证书与端口要求、组织创建链接、manage.py 管理命令、备份与升级回滚，以及 REST API / 机器人 / 入站 Webhook 的接入要点。含 epmd 端口、配置被覆盖、内存与 swap 这些高频翻车点。遇到问题可加技术微信 9872659。"
summary: "群聊里三件事同时在刷，讨论一小时后谁也翻不到结论——Zulip 用「频道 + 话题」把每件事拆成独立线索，可以逐个跟进、逐个标记已读。它是自己托管的实时聊天服务，装一台机器就能给全公司用，也提供 REST API、机器人框架与 Webhook，适合把通知和自动化接进来。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 聊天
---

# 三剪客 · 话题制团队聊天服务器

团队聊天的真正问题不是「发不出去」，而是「找不回来」：一个群里同时聊着排期、故障和午饭，两小时后要翻某条结论得滚几百条消息。Zulip 换了个组织方式——所有消息都归到「频道 + 话题」下，一个话题就是一条独立线索，可以单独跟进、单独静音、单独标已读，追一个讨论不会被别的对话打断。

它是一套**完整的自托管服务**：装在一台干净的 Linux 机器上，自带 Web 界面、桌面与移动客户端、邮件通知、全文检索、机器人框架和 REST API。代价是它比较「重」——安装器会调用系统包管理器装上数据库、缓存、队列和反向代理并替你把它们配好，官方明确希望这台机器**只跑它一个**。

**上游项目**：`Zulip`　**仓库**：https://github.com/zulip/zulip

## 什么时候用 / 不用

**用它**：

- 团队说「群里太吵，重要讨论被刷没了」，需要一个能按话题归档、新人也能回看历史讨论的沟通工具。
- 要把聊天服务**自己托管**：数据、账号、备份都留在自己机器上。
- 需要把系统通知接进聊天：入站 Webhook、机器人、REST API 都能用。
- 组织规模从十几人到上千人，想先小规模上线再按官方扩容路径放大。
- 需要多组织共存（同一台服务器用不同子域承载多个组织）。

**不要用它**：

- 需要**端到端加密的私密通信**。它是服务端存储消息的团队协作工具，不是加密 IM。
- 想要**零运维的托管服务**。虽然有托管方案，但这个 Skill 面向自托管；不想管机器就别自建。
- 机器的用途不单一。安装器会接管系统包并配置数据库、缓存与反向代理，官方不支持与其他服务混部。
- 主要诉求是**音视频会议**（它只做会议工具的集成入口），或要的是**客户支持工单台**（客户会话收件箱、坐席分配）——这两类都不在它的职责范围内。
- 服务器是 Windows 或非 x86-64 / aarch64 架构。原生安装只覆盖特定 Linux 发行版；其他平台只能走容器，而官方说明容器方式会**增加**安装、维护与升级的工作量。

## 安装

**先确认硬件与系统**（官方要求）：

| 项目 | 要求 |
|---|---|
| 操作系统 | Ubuntu 22.04 / 24.04 / 26.04 或 Debian 12 / 13 |
| CPU 架构 | x86-64 或 aarch64 |
| 内存 | 至少 2GB；不足 5GB 时**必须**配 swap，官方建议 2GB swap；预计 100+ 用户时用 4GB 内存 + 2 核 |
| 磁盘 | 至少 10GB 专用空闲空间（算上系统约 25GB 盘），建议 SSD |
| 网络 | 一个能解析的域名；可出网（拉依赖、站点预览、推送）；一个可用的发信 SMTP |
| 其他 | 机器上不要跑别的东西；Ubuntu 需要启用 universe 仓库 |

```bash
# Ubuntu 需要先启用 universe 仓库
sudo add-apt-repository universe
sudo apt update
```

**标准安装器（推荐的路径）**

```bash
# 1. 下载并解压最新发行包
cd $(mktemp -d)
curl -fLO https://download.zulip.com/server/zulip-server-latest.tar.gz
tar -xf zulip-server-latest.tar.gz

# 2. 切到 root
[ "$(whoami)" != "root" ] && sudo -s

# 3. 跑安装器：填维护者邮箱和用户访问用的域名
./zulip-server-*/scripts/setup/install --push-notifications --certbot \
    --email=YOUR_EMAIL --hostname=YOUR_HOSTNAME
```

安装过程会装依赖，需要几分钟。官方说明这个脚本是**幂等**的：失败后修好原因直接重跑即可。

常用安装选项（不加 `--certbot` 就要自己提供证书）：

| 选项 | 作用 |
|---|---|
| `--email=` | 维护者真实邮箱，会出现在自动邮件、帮助页与错误页上 |
| `--hostname=` | 用户访问的域名，会成为 `EXTERNAL_HOST` |
| `--certbot` | 自动申请证书并配置定时续期 |
| `--push-notifications` / `--no-push-notifications` | 是否注册移动推送服务；开启会立即要求同意服务条款 |
| `--no-submit-usage-statistics` | 开启推送时，不提交聚合使用统计 |
| `--agree-to-terms-of-service` | 配合推送选项在脚本里无人值守执行 |
| `--self-signed-cert` | 生成自签证书，仅适合测试或放在反向代理之后 |

**容器方式**：官方提供 Docker 镜像，支持 Docker Compose（单机）与 Helm（Kubernetes）。官方口径是：除非组织本身偏好容器化部署，否则优先用标准安装器，因为容器方式会明显增加安装、维护与升级的工作量。容器里执行管理命令的方式与宿主机安装不同，要按官方容器文档操作。

## 常用操作

**1. 创建组织并登录**

安装完成后，脚本会打印一个**一次性**的组织创建链接，浏览器打开它按提示建组织和管理员账号即可。链接失效或需要重开时：

```bash
cd /home/zulip/deployments/current
./manage.py generate_realm_creation_link
```

**2. 跑管理命令（以 `zulip` 用户登录服务器后执行）**

```bash
cd /home/zulip/deployments/current

./manage.py help                 # 列出所有可用命令（重点看 zerver 段）
./manage.py <命令> --help        # 每个命令都自带文档

./manage.py list_realms          # 看这台服务器上有哪些组织及其 string_id
./manage.py show_admins -r ''    # 单组织部署时 string_id 是空字符串；多组织填子域
```

常用命令举例：

```bash
./manage.py change_user_role <email> <role>       # 调整角色（UI 里也能做）
./manage.py change_user_email <old> <new>         # 改邮箱
./manage.py change_realm_subdomain                # 换子域
./manage.py deactivate_user <email>               # 停用用户（比删除安全）
./manage.py delete_user <email>                   # 彻底删除（会影响历史，慎用）
./manage.py send_password_reset_email <email>     # 手动触发密码重置邮件
./manage.py export_single_user <email>            # 导出某个用户可见的消息
./manage.py unarchive_channel                     # 恢复已归档的频道
./manage.py reset_authentication_attempt_count    # 给被限流锁住的账号解锁
```

需要直查数据库时，官方给的是 Django 管理 shell，而不是直接改表：

```bash
./manage.py shell      # 项目模型已自动导入，可直接用
./manage.py dbshell    # 想要原始 SQL 时用；直接改数据容易绕过缓存与通知逻辑
```

**3. 备份**

```bash
/home/zulip/deployments/current/manage.py backup --output=/home/zulip/backup.tar.gz
```

官方还提供把数据库备份流式推到 S3、以及只备份数据库的工具，还支持用备份在容器安装与标准安装之间迁移。

**4. 升级**

```bash
# 下载新发行包后，以 root 执行
/home/zulip/deployments/current/scripts/upgrade-zulip zulip-server-latest.tar.gz
```

升级做了什么：`apt-get upgrade` → 更新依赖 → 停服务 → 跑配置管理 → 执行数据库迁移 → 起新版本。官方说停机通常**不到 30 秒**，除非遇到耗时的数据库迁移。

从 Git 分支升级（拿未发布修复或维护自己的分支）：

```bash
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git main
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git 11.x
```

**5. 回滚（仅限同一大版本的小版本）**

升级会在 `/home/zulip/deployments/` 下留下完整代码目录，并移动 `current` / `last` / `next` 符号链接，所以可以切回上一版：

```bash
/home/zulip/deployments/last/scripts/restart-server
```

跨大版本回滚需要额外处理数据库迁移，官方明确说更复杂。

**6. 用 REST API 发消息（把通知接进聊天）**

接口基址是 `https://<你的域名>/api/v1/`，认证用「账号邮箱 : API Key」做 HTTP Basic：

```bash
# 发到频道（stream）下的某个话题
curl -X POST https://your-org.example.com/api/v1/messages \
    -u EMAIL_ADDRESS:API_KEY \
    --data-urlencode type=stream \
    --data-urlencode 'to="Denmark"' \
    --data-urlencode topic=Castle \
    --data-urlencode 'content=部署完成，用时 42 秒'

# 发私聊（direct），to 可以是用户 ID 列表
curl -X POST https://your-org.example.com/api/v1/messages \
    -u EMAIL_ADDRESS:API_KEY \
    --data-urlencode type=direct \
    --data-urlencode 'to=[9]' \
    --data-urlencode 'content=有空看下这条'
```

Python 绑定与命令行工具：

```bash
pip install zulip

# 用 zuliprc 配置文件
# client = zulip.Client(config_file="~/zuliprc")

# 命令行直接发
zulip-send --stream Denmark --subject Castle \
    --user bot@example.com --api-key <key> \
    --message '你好，这是一条来自脚本的消息'
```

返回体里 `result` 是 `success` 或 `error`；失败会带 `code`（例如 `STREAM_DOES_NOT_EXIST`）。客户端应先调 `POST /register` 拿到 `max_message_length` 与 `max_topic_length`，不要把长度写死。官方还给出 JavaScript 等语言的绑定与更多客户端库。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 装在一台已有业务的机器上，装完别的服务受影响 | 安装器按「整机独占」设计，会装上并配置数据库、缓存、队列与反向代理 | 官方口径就是给它一台干净机器或全新虚拟机；已混部的环境不受支持，官方另有现状说明文档 |
| 安装过程中系统包管理器报找不到依赖 | Ubuntu 没启用 universe 仓库 | `sudo add-apt-repository universe && sudo apt update` 后重跑安装器（它是幂等的） |
| 低内存机器上升级时卡在构建前端资源并报内存不足 | 官方指出内存最小配置的机器在升级过程中可能 OOM（通常是构建那一步） | 先 `scripts/stop-server` 释放内存再升级；内存低于 5GB 的机器官方要求配 swap，建议 2GB |
| 手动改过的 nginx 等配置文件升级后消失了 | 升级会执行配置管理，覆盖它托管的服务配置文件 | 不要直接改被托管的文件；用官方提供的 include 目录扩展配置，改前先用 `scripts/zulip-puppet-apply`（不带 `-f`）试跑看看会改什么 |
| 升级后新版本的功能在配置里找不到 | `/etc/zulip/settings.py` 不会随升级自动更新，它是基于旧版本模板生成的 | 用 `scripts/setup/compare-settings-to-template` 看自己的改动，参照当前模板 `zproject/prod_settings_template.py` 手工合并，改完 `scripts/restart-server` |
| 升级后异常想退回去 | 跨大版本回滚要处理数据库迁移 | 小版本用 `/home/zulip/deployments/last/scripts/restart-server`；大版本别硬回滚，按官方排障与回滚章节走 |
| 安全扫描报 4369 端口暴露 | 队列依赖的 Erlang 端口映射守护进程不支持只绑本机 | 官方明确要求用防火墙挡住 4369；它不是给外部访问的端口 |
| 移动端收不到推送 | 安装时没开推送注册，或没同意服务条款 | 安装时用 `--push-notifications`（脚本化再加 `--agree-to-terms-of-service`）；已装好的服务器按官方推送服务文档补注册 |
| 用户收不到确认邮件 / 通知邮件 | 没配可用的发信 SMTP | 官方要求准备 SMTP 凭据；装完先把发信打通再邀请用户 |
| 用 `manage.py shell` 直接 `save()` 改数据，界面不刷新、缓存不一致 | 很多对象除了写库还要刷缓存、通知客户端、写审计日志 | 优先用 `zerver.actions` 里的 `do_change_*` 类函数，或直接用管理命令与界面；`dbshell` 里改数据同理 |
| API 报「频道不存在」或用户无效 | 频道传了名字而不是 ID，或用户邮箱/ID 不对；参数取值随版本演进 | 看返回体的 `code` 与 `msg`；用官方接口文档核对 `type` / `to` / `topic`，频道名建议先换成 ID 再发 |
| 导出数据发现范围不对 | 导出工具分「整组织导出」「单用户导出」等不同范围 | 迁服务器走官方导出/导入流程，并按文档要求在导出期间阻止写入 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 安装与升级时拉取发行包与系统依赖；对外提供 HTTPS 服务；站点预览与移动推送需出网；对接外部 SMTP |
| 读取文件 | 是 | 读取 `/etc/zulip/` 下的配置、备份文件与部署目录中的代码 |
| 写入文件 | 是 | 写入配置与部署目录、日志（`/var/log/zulip/`）、上传附件与备份产物 |
| 凭证 | 是 | 需要维护者邮箱、SMTP 凭据、SSL 证书（或由 `--certbot` 申请）；调用 API 需要账号或机器人的 API Key。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | 以多服务常驻形态运行（应用、实时推送、队列、缓存、数据库、反向代理），由进程管理器统一托管 |

## 触发场景

- 「群聊太乱，重要讨论被刷没了，有没有按话题归档的」
- 「想自己搭一套团队聊天服务，数据放自己机器上」
- 「这个聊天服务怎么装、要什么配置的机器」
- 「要把监控告警发到聊天频道里」
- 「怎么备份、怎么升级这套聊天服务」
- 「用 API 让机器人自动回消息」

## 能力边界

**覆盖**：

- 频道（公开或私有）与话题两层结构；话题可单独静音、跟进、标记已读。
- 消息组织与检索：全文检索、@提及、表情回应、消息编辑历史、草稿、定时发送、消息提醒。
- 富文本消息、代码块、公式、附件上传（本地磁盘或对象存储后端）。
- 组织与权限：组织管理员、用户角色、用户组、可配置的邀请与加入策略、账号安全设置。
- 客户端：Web 界面、桌面客户端、移动客户端，支持多组织共存（子域方式）。
- 通知：站内、邮件通知，以及移动推送（需注册官方推送服务）。
- 自动化与集成：REST API、实时事件队列、机器人框架、入站 Webhook、出站 Webhook，以及大量现成的第三方服务集成。
- 运维配套：一键安装器、幂等安装、备份与导出导入工具、升级与回滚脚本、监控与 Nagios 配置、独立数据库部署与热备、多组织托管。
- 可选能力：入站邮件网关（把邮件变成消息）、多种视频会议服务集成、单点登录与 SCIM 开通、AI 相关功能（需自行配置外部模型服务与 API Key）。

**不覆盖**：

- 不做端到端加密；消息需要在服务端以可检索形式存储，管理员与审计场景可见。
- 不做音视频会议本身，只做第三方会议服务的接入入口。
- 不做面向外部客户的客服工单 / 会话收件箱。
- 不代管服务器与证书：域名、DNS、证书续期、备份策略、监控告警都要自己落地。
- 托管方案的具体条款与价格不在本 Skill 范围内。
- 原生安装只覆盖特定 Linux 发行版与架构；其他环境只能走容器，且官方认为容器路径运维成本更高。

## 依赖条件

- 一台**专用**机器或虚拟机（官方要求不要把其他服务混布上去）。
- 受支持的 Linux：Ubuntu 22.04 / 24.04 / 26.04 或 Debian 12 / 13；架构 x86-64 或 aarch64。
- 至少 2GB 内存；不足 5GB 需配 swap（建议 2GB）；预计 100+ 用户时 4GB 内存 + 2 核。更大规模按官方扩容建议（例如 25+ 日活用 4GB、100+ 日活用 8GB……）。
- 至少 10GB 专用空闲磁盘，官方建议用 SSD。
- 一个在 DNS 里可解析的域名。
- 可用的发信 SMTP 凭据（注册确认、通知、密码重置都靠它）。
- 入站网络：443（端口可配置）；80 可选；要用入站邮件集成时开 25；4369 必须被防火墙挡住。
- 出站网络：80/443（站点预览与推送），以及到 SMTP 服务器（通常 587）。不需要出网时可以关掉相关功能。
- 用 API 或机器人时：账号或机器人的 API Key（可选用 `~/.zuliprc` 配置文件）。

## 已知限制

- 安装器要求整机独占，已经跑着别的服务的机器官方不支持。
- 升级虽然通常只停几十秒，但**数据库迁移耗时无法预估**，官方建议先在备份上演练或安排在低峰期。
- 回滚只对小版本友好；跨大版本回滚涉及数据库迁移，代价高。
- `/etc/zulip/settings.py` 不会随升级自动更新，跨大版本后要人工比对模板。
- 手改被配置管理接管的文件会在升级时被覆盖，扩展配置要走官方 include 目录。
- 容器方式增加维护与升级复杂度；容器与宿主机安装的管理命令入口不同。
- 移动推送依赖官方推送服务的注册与条款同意；不开就没有移动端推送。
- 文档、配置项与发行版本持续演进；命令与参数请以官方文档站当前内容为准，本文不对版本号做断言。

## 自检清单

- [ ] 机器是干净专用的，系统版本与架构在官方支持列表内。
- [ ] 内存与磁盘满足最低要求；内存不足 5GB 时已配好 swap。
- [ ] 域名已解析到这台机器；端口规划清楚（443 对外开放，80 按需，25 仅入站邮件需要，4369 已用防火墙挡住）。
- [ ] 已准备好发信 SMTP 凭据，并在装完后实测能发出确认邮件。
- [ ] 安装命令里的 `--email` 是真实维护者邮箱，`--hostname` 是用户实际访问的域名。
- [ ] 证书方案已确定（`--certbot` 或自备 / 自签），且续期机制有效。
- [ ] 是否启用移动推送已按需决定；启用则确认条款与统计选项。
- [ ] 已用一次性链接创建组织与管理员账号并成功登录。
- [ ] 已配置备份，并**验证过**备份能恢复（不是只跑通命令）。
- [ ] 升级前已读对应版本的升级说明，并在备份上演练过。
- [ ] 自定义的服务配置放在官方 include 目录里，而不是直接改被接管的文件。
- [ ] 调用 API 用的是机器人或专用账号的 Key，且 Key 不写进代码仓库。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/zulip/zulip | 上游仓库（安装与完整文档以它为准） |
| https://zulip.readthedocs.io/en/latest/production/install.html | 官方生产安装步骤与安装器选项（本文安装命令来源） |
| https://zulip.readthedocs.io/en/latest/production/requirements.html | 官方系统、硬件与网络端口要求 |
| https://zulip.readthedocs.io/en/latest/production/upgrade.html | 官方升级、设置比对与回滚流程（本文升级命令来源） |
| https://zulip.readthedocs.io/en/latest/production/management-commands.html | 官方管理命令清单（本文控制台命令来源） |
| https://zulip.com/api/send-message | 官方发消息接口说明与示例（本文 API 示例来源） |

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
