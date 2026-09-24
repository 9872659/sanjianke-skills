# 三剪客 · 多模型网关聚合 Skill

One API：多模型网关聚合 的安装、常用命令与避坑要点

---

## 前置条件

- 本机已安装 Docker（推荐方式），或备好 Go + Node 工具链用于源码编译。
- 规划好持久化目录（如 `/home/ubuntu/data/one-api`），容器里的 `/data` 必须挂载到宿主机。
- 至少准备一个上游厂商的 API Key，否则建不了渠道。
- 并发量较大时提前准备 MySQL，不要用默认的 SQLite 硬扛。
- 对外开放前先确定域名与 HTTPS 方案。

---

## 使用

把本目录作为 Skill 交给 Agent，或直接对照 `SKILL.md` 操作。典型流程：

1. `docker run` 起服务，确认 `http://localhost:3000/` 能打开。
2. 用初始账号登录，**第一件事是改密码**。
3. 在渠道页添加上游 Key 并点测试，确认连通。
4. 在令牌页建一个访问令牌，把客户端的 API Base 指向 `http://<host>:3000/v1`。
5. 用 `curl` 打通一次 `/v1/chat/completions`，再重启容器验证数据持久化。

环境变量与命令行参数以 `--help` 和上游仓库文档为准；本 Skill 记录的是常用路径与已知坑位。

---

## 依赖

- Docker（容器方式）或 Go + Node（源码编译方式）。
- 可选 MySQL / PostgreSQL 作为生产数据库；可选 Redis 作缓存。
- 可选的出口代理（`RELAY_PROXY`），用于上游被 Cloudflare 拦截的场景。
- 需要至少一个上游厂商账号与 API Key，账号自行准备。

---

## 安全

- 不内嵌任何密钥
- 首次登录用的默认密码必须立即修改，否则网关等同对外开放。
- 上游厂商 Key 会落库保存，务必限制数据库访问权限并做好备份加密。
- 所有访问令牌按最小权限发放，给外部用的一律设额度上限与过期时间。
- 暴露到公网时前面加 Nginx 并启用 HTTPS，同时收紧 `GLOBAL_API_RATE_LIMIT`。
- 不要把 `.env`、数据库文件、日志目录提交进版本库。
- 只中继你有权使用的模型服务，遵守上游厂商条款与所在地法律法规。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`One API`
- 仓库：https://github.com/songquanpeng/one-api

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
