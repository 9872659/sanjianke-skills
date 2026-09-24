# 三剪客 · 自建私有云盘服务端 Skill

ownCloud Core：自建私有云盘服务端 的安装、常用命令与避坑要点

---

## 前置条件

- 一台 Linux 服务器；或者本机装好 Docker 与 Compose 先做验证（最快一条 `docker run` 就能起试用实例）。
- 数据库：MySQL、MariaDB、PostgreSQL 任选其一；SQLite 仅限试用，官方不支持生产。
- 主机手工安装还需要 PHP 运行环境与所需扩展、Apache 或 Nginx；具体最低版本以官方系统要求文档为准。
- 生产环境建议准备：Redis 缓存、HTTPS 证书、独立备份目标、足够的数据盘空间。
- 需要一个域名或 IP 用于对外访问；远端访问时受信任域名必须包含实际地址。

---

## 使用

最短跑通路径（容器）：

```bash
docker run --rm --name oc-eval -d -p8080:8080 owncloud/server:10.16.4
# 浏览器打开 http://localhost:8080，账号 admin / admin
docker compose exec owncloud occ status --output=json_pretty   # Compose 部署下的状态查询
```

生产向的 Compose 部署顺序：

1. 新建项目目录，准备好 `docker-compose.yml` 与 `.env`（钉死 `OWNCLOUD_VERSION`，配好域名与管理员账号密码）。
2. `docker compose up -d`，用 `docker compose ps` 确认应用、数据库、缓存三个容器都为 healthy。
3. `docker compose logs --follow owncloud`，等到出现启动完成提示再打开页面。
4. 需要命令行运维时统一走 `docker compose exec owncloud occ <命令>`，不要加 `php` 前缀。
5. 升级时：进维护模式、备份数据库、改版本号、重启容器、确认升级完成、退出维护模式。

什么时候该用、什么时候不该用、常见坑与能力边界，见同目录的 `SKILL.md`；核心命令清单见 `references/occ-commands.md`。

---

## 依赖

- 运行期：Linux 主机 + PHP 运行环境 + Web 服务器 + 数据库（MySQL/MariaDB/PostgreSQL）；容器方式下这些都封装在镜像里。
- 容器方式：Docker 与 Docker Compose；还需要能拉取镜像的网络。
- 缓存：生产建议启用 Redis（Compose 编排里通常是独立容器）。
- 存储：数据目录或数据卷必须持久化，且归属正确的 Web 用户。
- 备份：数据库与数据目录要能一起备份，缺一会导致恢复后状态不一致。
- 可选：反向代理与证书工具（对外提供 HTTPS）、`mysqldump` 或同类工具（升级前备份数据库）。
- 不需要任何模型的 Key。

---

## 安全

- 不内嵌任何密钥：管理员密码、数据库口令、邮件与外部存储凭证都由你在 `.env` 或配置文件里填，请勿把这些文件提交到代码仓库。
- 首次部署的 `ADMIN_USERNAME` 与 `ADMIN_PASSWORD` 会写进数据库卷，之后改 `.env` 不生效；想改账号只能清卷（会丢数据），请在上线前一次性定好。
- 试用实例用的是 SQLite 且预置 `admin` / `admin`，只能本机访问；绝不要把这种实例暴露到公网。
- 生产务必开 HTTPS 并把受信任域名收紧到实际使用的域名；反向代理场景要按官方文档设置覆盖 URL 与协议头。
- 删除用户会连带删除其文件与分享，删除前先用 `occ files:transfer-ownership` 转移并做好备份。
- `occ files:remove-storage` 会真正删除存储记录与相关文件缓存，必须先在单用户模式下用 `--show-candidates` 核对，并先备份数据库。
- 升级、修复、搬迁数据前先进入维护模式，避免用户写入与后台任务同时改数据。
- 文件权限归属必须由 Web 用户持有；用 root 直接操作数据目录是后续故障的常见根源。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`ownCloud Core`
- 仓库：https://github.com/owncloud/core

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
