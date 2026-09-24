# 三剪客 · 自建网盘与在线协作 Skill

Nextcloud Server：自建网盘与在线协作 的安装、常用命令与避坑要点

---

## 前置条件

- 一台能长期开机的 Linux 服务器（或 NAS / 虚拟机），磁盘容量按你要存的数据量准备。
- **Web 服务器**：Apache（官方有配置示例）或 NGINX（官方有独立配置页）。
- **PHP**：版本与必需扩展随 Nextcloud 版本变化，**以官方 system requirements 页为准**。推荐启用 opcache；命令行侧要能跑 `php`，且版本与 Web 端一致。多机部署还需要 Redis 之类的分布式缓存。
- **数据库**：MySQL / MariaDB、PostgreSQL、SQLite（不建议生产）、Oracle 之一，并建好库与库用户。
- **HTTPS 证书**：生产必须上 TLS；自签证书能用但客户端会告警，建议用免费证书。
- **定时任务能力**：cron 或 systemd timer，用来跑后台任务。
- **数据目录**：必须放在 Web 根目录**之外**，并且属主/权限匹配 Web 用户（Debian/Ubuntu 是 `www-data`，RHEL 系是 `apache`，Arch 是 `http`，openSUSE 是 `wwwrun`）。
- **权限**：装包、改 Web 服务器配置、跑 `occ` 都需要 root 或 sudo。
- 不需要任何第三方开发者 Key；需要你自己设定数据库凭据和管理员账号。

---

## 使用

三条最短路径，按你的运维意愿挑：

**A. 一体化容器（最省心）**

```bash
docker run \
  --init --sig-proxy=false \
  --name nextcloud-aio-mastercontainer --restart always \
  --publish 8080:8080 \
  --volume nextcloud_aio_mastercontainer:/mnt/docker-aio-config \
  --volume /var/run/docker.sock:/var/run/docker.sock:ro \
  nextcloud/all-in-one:latest
```

然后浏览器打开 `http://<主机>:8080` 按向导走。

**B. Snap（Ubuntu 上两条命令）**

```bash
sudo snap install nextcloud
sudo snap connect nextcloud:removable-media   # 只有要挂 /media 或 /mnt 外置盘时才需要
```

**C. 源码 tarball + LAMP（可控性最高）**

解包到 `/var/www/nextcloud`，配好 Apache 站点与必需模块，然后命令行完成安装：

```bash
sudo a2enmod rewrite headers env dir mime
sudo a2ensite nextcloud.conf
sudo service apache2 restart
sudo chown -R www-data:www-data /var/www/nextcloud/

sudo -E -u www-data php /var/www/nextcloud/occ maintenance:install \
  --database mysql --database-name nextcloud \
  --database-user nextcloud --admin-user admin
```

装完先自查：

```bash
sudo -E -u www-data php occ status
sudo -E -u www-data php occ app:list
```

之后所有运维动作都走 `occ`，**必须以 Web 用户身份运行**：

```bash
sudo -E -u www-data php occ files:scan --all
sudo -E -u www-data php occ maintenance:mode --on
sudo -E -u www-data php occ upgrade
```

参数不确定就用 `occ help <命令名>` 问它自己。完整操作、坑表与自检清单见 `SKILL.md`。

---

## 依赖

| 类别 | 依赖 | 说明 |
|---|---|---|
| Web 服务器 | Apache 或 NGINX | Apache 需要 `rewrite`；用 FPM 时还要 `proxy` / `proxy_fcgi`；必须**禁用** `mod_webdav`（与内置 WebDAV 冲突） |
| 运行时 | PHP + 必需扩展 | 版本与扩展清单以官方 system requirements 为准；CLI 下要开 `apc.enable_cli` |
| 数据库 | MySQL / MariaDB、PostgreSQL、SQLite、Oracle | 对应 PHP 扩展或驱动必须启用；生产不建议 SQLite |
| 缓存 | APCu（单机）、Redis（多机） | 缺失会在概览页报警告 |
| 定时任务 | cron 或 systemd timer | 不配会导致页面一直提示后台任务用 Ajax |
| 外部工具 | 可选 | 缩略图、预览、全文检索等能力依赖外部程序，缺了对应功能不工作 |
| 命令行 | `php` CLI | 版本必须与 Web 端一致，否则 `occ` 行为不一致 |
| 证书 | TLS 证书 | 生产必需；可用免费证书并配自动续期 |

---

## 安全

- 不内嵌任何密钥；所有凭据由使用者自己在部署时生成并保管。
- **必须保护的文件**：`config/config.php`（数据库口令、实例密钥、各类 secret）与数据库本体。这两个丢了等于数据丢了，泄露了等于门户大开。
- **数据目录必须放在 Web 根目录之外**，否则可能被直接下载。Web 服务器配置里不要 Alias 到 `data/`。
- **不要用 777 解决权限问题**。正确的做法是让 Web 用户成为属主（或加入属组并保证组可写）。权限过宽会让同机其他账号读到全部用户文件。
- **生产必须启用 HTTPS**。明文 HTTP 下登录凭据、同步流量都是裸奔。
- **不要把服务直接怼在公网上不做加固**：按官方加固指引做，限制访问来源、开双因素、关掉不需要的应用。
- **`occ` 必须用 Web 用户跑**。用 root 跑会改变文件属主，后续 Web 端读写就可能失败；这既是安全问题也是可用性问题。
- **升级前必须备份**数据库与 `config/`。跨大版本升级不可回退，应用不兼容会直接把实例卡在维护模式。
- 沙箱化装法（Snap 等）默认限制访问宿主路径，这是保护机制；授权的接口要按需最小化开启。
- 应用市场装的应用拥有服务端代码执行权限，**只装可信来源**。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Nextcloud Server`
- 仓库：https://github.com/nextcloud/server

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
