# 三剪客 · 开源项目协作与任务管理台 Skill

自托管项目协作台的落地指引：环境要求、Docker 与手动部署、安装向导、配置项、升级备份与高频坑

---

## 前置条件

- 一台能部署 PHP 应用的服务器（或支持 Docker 的机器），建议 2 核 4G 起步
- PHP 8.2+ 与所需扩展，或直接用官方 Docker 镜像省掉环境搭建
- MySQL 8.0+ / MariaDB 10.6+ 的空库，以及可用的数据库账号
- 域名与 TLS 证书（放公网时）；反向代理场景需要确定对外访问地址
- 如果要把登录接进企业目录，需要 LDAP / OIDC 的对接信息；要挂对象存储则需要 S3 密钥

---

## 使用

1. 按 `SKILL.md` 的「安装」一节选择 Docker 或手动方式部署，域名根目录必须指向 `public/`。
2. 启动后访问 `/install` 完成数据库初始化与首个账号创建。
3. 需要插件、S3 附件、LDAP / OIDC 登录时，按「常用操作」里的配置项逐项开启；容器部署优先用环境变量覆盖。
4. 升级前先备份数据库和文件，再走 `/update` 或 `php bin/leantime system:update`。
5. 遇到部署问题对照「常见坑」表逐条排查，官方排错条目见 `docs.leantime.io` 的 common-issues 页。

---

## 依赖

- PHP 8.2+；MySQL 8.0+ 或 MariaDB 10.6+；Apache / Nginx（IIS 需额外配置）
- PHP 扩展：bcmath、ctype、curl、dom、exif、fileinfo、filter、gd、hash、ldap、mbstring、mysql、opcache、openssl、pcntl、pcre、pdo、phar、session、tokenizer、zip、simplexml
- Docker 部署：Docker 与 docker compose；源码开发：make、composer、git、npm
- 无外部账号要求；S3 / SMTP / LDAP / OIDC 为可选项，各自需要对应凭据

---

## 安全

- 不内嵌任何密钥
- `config/.env` 内含数据库密码与会话加密串，需限制文件权限，不要提交进版本库
- 把 `LEAN_SESSION_PASSWORD` 从示例值替换为强随机值，避免会话被伪造
- 公网部署必须走 HTTPS，并正确设置 `LEAN_APP_URL`，否则重定向与邮件链接会泄漏内网地址
- 登录失败限流（`LEAN_RATELIMIT_AUTH`）不要为了省事关掉，它是暴力破解的第一道门槛
- 以 root 身份运行容器会放大风险，升级与运维请使用最小权限账号

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Leantime`
- 仓库：https://github.com/Leantime/leantime

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
