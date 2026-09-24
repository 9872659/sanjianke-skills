# 三剪客 · 开源自建营销自动化 Skill

Mautic：开源自建营销自动化 的安装、常用命令与避坑要点

---

## 前置条件

- 一台能长期运行的服务器，以及一个能托管 PHP 应用的 Web 服务器（Apache / Nginx + PHP-FPM 等）。
- **PHP 8.1.0 ~ 8.3.99**（Mautic 6.0 元数据区间，随大版本变化，以官方 requirements 页为准）；`max_execution_time` 建议不低于 240 秒，内存上限按官方建议调高。
- **MySQL ≥ 5.7.14 或 MariaDB ≥ 10.2.7**，以及一个有建库建表权限的数据库账号。
- **Composer**：走 Recommended Project 或从 GitHub 安装时需要。本地测试开发建议再装 DDEV 与 Docker。
- 一个可用的**发信通道**（SMTP 或邮件服务商的 API）及其凭证。Mautic 自身不提供发信能力。
- 服务器上有可用的**定时任务调度**（crontab 或等价物），用来跑分群、活动、邮件等必需任务。

## 使用

最短跑通路径（Composer 方式）：

```bash
composer create-project mautic/recommended-project:^5 some-dir --no-interaction
```

> 版本约束以官方安装文档当前给的为准，上面只是官方文档里的命令形式，不要照抄就当作最新版。

这套模板会把核心文件放进 `docroot` 子目录，**Web 根目录必须指向该目录**。之后二选一完成初始化：

- 浏览器打开站点，走 Web 安装向导（环境检查 → 数据库 → 管理员账号 → 邮件设置）；
- 或命令行安装：

```bash
path/to/php bin/console mautic:install --help
path/to/php bin/console mautic:install https://m.example.com \
  --db_driver="pdo_mysql" --db_host="db" --db_port="3306" \
  --db_name="db" --db_user="db" --db_password="db" \
  --db_backup_tables="false" \
  --admin_email="admin@mautic.local" --admin_password="<强口令>"
```

装完的第一件正事是配好三个必需 cron（**务必错开分钟**）：

```bash
php /path/to/mautic/bin/console mautic:segments:update --no-interaction --no-ansi
php /path/to/mautic/bin/console mautic:campaigns:update --no-interaction --no-ansi
php /path/to/mautic/bin/console mautic:campaigns:trigger --no-interaction --no-ansi
```

需要在后台邮件队列、导入导出、Webhook 时，再按需补上对应命令。完整命令清单直接跑 `bin/console`（必须在 Mautic 根目录下执行）。

## 依赖

- **PHP 运行时**：版本区间见上；需要 Composer 管理依赖时另需 Composer。
- **数据库**：MySQL 或 MariaDB，版本见上；账号需具备建表与读写权限。
- **Web 服务器**：能运行 PHP 应用并正确指向站点根目录（Composer 方式下是 `docroot`）。
- **系统调度器**：crontab 或等价的定时任务系统，用于分群 / 活动 / 邮件 / 导入导出 / Webhook 等任务。
- **邮件服务商**：SMTP 或 API 形式的发信通道及其凭证。
- **可选组件**：DDEV + Docker（本地测试开发）；GeoLite2 IP 库（由 `mautic:iplookup:download` 拉取，用于 IP 归属地）；集成插件（CRM、社交、存储等，按需从 Marketplace 或手工安装）。
- **磁盘与内存**：数据库与 `media` 资源会持续增长；大批量任务对内存较敏感，必要时给单条命令单独提高内存上限。

## 安全

- 不内嵌任何密钥
- 数据库口令、管理员账号口令、邮件服务商凭证、集成插件的 API Key 一律由使用者填入本机配置文件，本 Skill 与包内文件不含任何真实凭证。
- 后台管理员口令必须够强（Mautic 5.1 起强制复杂口令），不要让后台直接暴露在公网而不加访问控制。
- 站点应启用 HTTPS（官方安装向导也会提示非 SSL 连接的风险）。
- 注意文件属主与权限：Web 服务器进程需要读写安装目录、缓存、日志与 `media`，但不要让这些路径被公开下载到（尤其是配置与日志文件）。
- `mautic:maintenance:cleanup` 会**永久删除**数据，执行前必须确认数据库备份；先用 `--dry-run` 看影响范围，需要满足 GDPR 场景时再用 `--gdpr`。
- 升级前备份数据库与文件，按官方更新流程操作；源码 / 数据库结构与发行版不同步时更新器可能失效。
- 生产环境使用 tagged release 或生产包 / Composer 安装的版本；GitHub 上非 tagged release 的代码被官方定义为 alpha，可能含 bug 甚至导致数据损坏。
- 定时任务建议把输出重定向到受限目录的日志文件，便于排错，也避免把库凭证等内容打印到可公开访问的位置。

## 上游项目

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Mautic`
- 仓库：https://github.com/mautic/mautic

---

## 许可证

MIT，见 `LICENSE.md`。

---

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
