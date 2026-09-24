# 三剪客 · 开源库存与物料管理系统 Skill

InvenTree：开源库存与物料管理系统 的安装、常用命令与避坑要点

---

## 前置条件

- **运行形态**：一套常驻服务 + 数据库。官方主推 Docker 生产部署，也支持裸机与开发环境部署。
- **Docker 路线**：本机装好 Docker 与 Docker Compose，能拉取官方镜像；建议给数据库与附件单独挂宿主机卷。
- **裸机路线**：自备 Python 环境与数据库，并安装 `invoke` 作为任务入口；前端相关任务还需要 Node.js 构建环境。
- **`.env` 配置**：部署前必须改掉模板里的数据库密码等默认值，并确认对外服务端口。
- **磁盘与网络**：留足数据库与附件空间；系统需要能常驻运行 Web 服务、数据库与后台任务进程。
- **可选**：标签打印机或扫码设备（要用条码功能时）、可用的邮件服务（要发通知时）。

## 使用

最短跑通路径（Docker）：

```bash
# 1. 取得官方 docker 部署配置与 .env 模板（见官方文档的 Docker 安装章节），放在同一目录
# 2. 编辑 .env：改掉数据库密码，确认对外端口

# 3. 初始化数据库结构 + 创建管理员账号
docker compose run --rm inventree-server invoke update
docker compose run --rm inventree-server invoke superuser

# 4. 启动服务
docker compose up -d
```

然后浏览器打开服务地址，用上一步创建的管理员账号登录。

**升级时的顺序很重要**：先更新镜像，再跑一次 `invoke update`，最后启动服务。

```bash
docker compose pull
docker compose run --rm inventree-server invoke update
docker compose up -d
```

常用运维动作：

```bash
docker compose logs -f --tail=200 inventree-server   # 看日志
docker compose config --services                     # 确认实际服务名
docker compose down                                  # 停止
```

用 API 取数据前，先在 Web 界面里为账号生成 API Token，然后：

```bash
curl -s "http://<你的地址>/api/part/?limit=10" \
  -H "Authorization: Token <你的TOKEN>" \
  -H "Accept: application/json"
```

更多操作、备份做法与避坑要点见 `SKILL.md`。

## 依赖

- Docker 与 Docker Compose（容器部署），或 Python 环境 + 数据库 + `invoke`（裸机部署）。
- 数据库：官方支持的数据库类型以官方文档为准；容器部署时由 compose 一并提供。
- 可选：Node.js 构建环境（开发模式或自定义前端时）。
- 可选：标签打印机 / 扫码设备（条码与标签功能）。
- 可选：SMTP 等邮件服务（系统通知邮件）。
- 无必需的外部 SaaS 账号与付费授权。

## 安全

- 不内嵌任何密钥；本包只包含说明文字，不含上游项目源码。
- `.env` 里的数据库密码、应用密钥必须改掉默认值，文件权限收紧，且不要提交进版本控制。
- 数据库端口不要暴露到公网；对外只暴露 Web 端口，并置于反向代理与 HTTPS 之后。
- 用户 API Token 按人发放、按最小权限授权；离职或泄露后立即吊销。
- 数据库数据目录与附件目录都要持久化到宿主机卷，并纳入备份；只备份数据库会丢附件。
- 升级前先做一次完整备份（数据库 + 附件），再执行数据库迁移。
- 系统可按权限开放给外部客户，但务必先核对各角色的可见范围，避免泄露成本与供应商信息。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`InvenTree`
- 仓库：https://github.com/inventree/InvenTree

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
