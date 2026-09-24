# 三剪客 · 企业 ERP 与 CRM Skill

Dolibarr：企业 ERP 与 CRM 的安装、常用命令与避坑要点

---

## 前置条件

- **运行形态**：一套常驻的 Web 服务 + 一个数据库。可以走 Docker，也可以走传统 LAMP / LEMP 部署。
- **PHP 环境**（传统部署）：需要 Web 服务器与 PHP 运行环境，具体最低版本、必需扩展与目录权限要求随版本变化，以官方站点 `https://www.dolibarr.org/` 的安装说明为准。
- **数据库**：MySQL / MariaDB 或 PostgreSQL。建库时请显式指定 UTF-8 字符集，否则中文容易乱码。
- **Docker 路线**：本机装好 Docker 与 Compose，能拉取官方镜像 `dolibarr/dolibarr`；数据库端口不要直接暴露到公网。
- **目录规划**：站点根目录指向 `htdocs/`；安装过程中需要 `htdocs/conf/` 可写，装完要收紧。
- **可选**：一个可用的 SMTP 账号（要发系统邮件时）、一台能跑 cron 的机器（要让计划作业按时触发）。

## 使用

最短跑通路径（Docker 试跑）：

```bash
# 1. 拉取并起一个容器（仅用于本地试跑）
docker pull dolibarr/dolibarr
docker run -d --name dolibarr -p 8080:80 dolibarr/dolibarr

# 2. 浏览器打开，走 Web 安装向导
#    http://localhost:8080/install/
```

正式部署建议用 `docker-compose.yml` 把数据库和 Dolibarr 放进同一网络：

```bash
docker compose up -d
docker compose logs -f          # 看启动与报错
docker compose down             # 停止
```

传统部署的五个关键动作：

1. 准备 PHP 环境与数据库，把安装包解压到站点目录。
2. 浏览器打开站点，进入 `/install/` 填数据库连通信息。
3. 向导生成 `htdocs/conf/conf.php`；该目录不可写时手工创建并临时授权。
4. 创建管理员账号完成安装。
5. **删除或移走安装目录**，然后按需启用模块（客户、报价、订单、发票、库存等）。

接口调用前的准备：在后台启用 Web 服务 / API 模块，为该用户生成 API Key，然后：

```bash
curl -s "https://<你的域名>/api/index.php/thirdparties?limit=5" \
  -H "DOLAPIKEY: <你的APIKEY>" \
  -H "Accept: application/json"
```

更多操作、备份命令与避坑要点见 `SKILL.md`。

## 依赖

- Web 服务器（Apache / Nginx 等）+ PHP 运行环境（扩展与版本要求以官方文档为准）。
- 数据库：MySQL / MariaDB 或 PostgreSQL。
- 可选：Docker 与 Docker Compose（走容器部署时）。
- 可选：SMTP 邮件服务（要发报价单、发票、提醒邮件时）。
- 可选：系统的 cron（计划作业、周期性提醒依赖它）。
- 无必需的外部 SaaS 账号，也不依赖任何付费授权。

## 安全

- 不内嵌任何密钥；本包只包含说明文字，不含上游项目源码。
- 安装完成后必须删除或移出安装目录，否则重装入口会留在线上。
- `htdocs/conf/conf.php` 含数据库口令，权限要收紧，且不要提交进版本控制。
- 目录权限遵循最小可用：程序代码只读，仅必要目录可写；不要图省事给 777。
- 数据库端口不要暴露到公网；后台管理入口建议加访问限制或置于内网 / VPN 之后。
- API Key 按用户发放并按最小权限授权，泄露后立即在后台重置。
- 备份文件含全部经营数据，存放位置同样要管控访问权限，并定期验证能否恢复。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Dolibarr`
- 仓库：https://github.com/Dolibarr/dolibarr

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
