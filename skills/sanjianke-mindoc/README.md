# 三剪客 · 团队文档管理系统 Skill

自托管团队文档站的落地指引：部署、配置、初始化、导出与高频坑

---

## 前置条件

- 一台可长期在线的服务器；项目本体是常驻服务端进程，需要进程守护
- 数据库三选一：MySQL（必须 `utf8mb4_general_ci`）、SQLite（默认）、Postgres
- 从源码编译时需要 Go 不低于 1.23.0，且环境支持 CGO 与 `go mod`
- 需要导出 PDF / EPUB / MOBI / DOCX 时，额外安装 Calibre 的 `ebook-convert`（官方镜像已内置）
- Docker 部署需要 Docker 与 docker compose
- 可选的邮件、LDAP、钉钉 / 企业微信登录各自需要对应凭据

---

## 使用

1. 装好二进制或拉起容器，`conf/app.conf` 不存在时先从 `conf/app.conf.example` 复制一份并填好 `db_*`。
2. 执行一次 `./mindoc install` 初始化数据库表结构，成功后根目录会出现 `install.lock`。
3. 用默认账号 `admin` / `123456` 登录，**立刻改密码**，再建项目、加成员。
4. 需要导出时开启 `enable_export`，并确认 `ebook-convert` 可用。
5. 升级时先备份数据库，替换程序后按 release 说明执行一次 `install` 更新表结构。
6. 二级目录部署、反代、邮件、LDAP 等场景对照 `SKILL.md` 的「常用操作」与「常见坑」逐条配置。

---

## 依赖

- 运行本体无额外系统依赖（单二进制）
- 数据库：MySQL / SQLite / Postgres，SQLite 与 MySQL 均需 CGO 编译支持
- 导出功能依赖外部 `ebook-convert`（Calibre）
- 配置支持 `${ENV||默认值}` 占位符，容器部署可用环境变量覆盖配置
- 过程管理建议使用 supervisor 等工具保证重启后自动拉起

---

## 安全

- 不内嵌任何密钥
- 初始化的 `admin` / `123456` 是公开的默认口令，必须立即修改
- `app.conf` 内含数据库密码与集成密钥，需限制文件权限，不要提交进版本库
- MCP 功能的 `mcp_api_key` 默认是示例值，上线前必须替换为强随机串并限制访问来源
- `uploads` 与 `database` 目录包含全部业务数据，需纳入备份并限制宿主机的访问权限
- 私有项目靠 Token 访问，Token 泄露等同于文档泄露，需按项目定期轮换

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`MinDoc`
- 仓库：https://github.com/mindoc-org/mindoc

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
