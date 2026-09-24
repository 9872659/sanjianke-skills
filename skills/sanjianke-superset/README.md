# 三剪客 · 企业级数据可视化与 BI 平台 Skill

superset：企业级数据可视化与 BI 平台 的安装、常用命令与避坑要点

---

## 前置条件

- 一台能跑容器的机器（本地试跑建议给足内存），或者一台自己维护 Python 环境的服务器
- 一个元数据库（Compose 编排里默认自带 PostgreSQL），以及一个 Redis
- 需要的端口：应用 8088、Nginx 80、Redis 6379、元数据库 5432（都可在 `.env-local` 里覆盖）
- 要查的数据库地址与只读账号（强烈建议只给只读权限，别把生产写账号填进去）
- 准备好 `SUPERSET_SECRET_KEY` 和一组强口令，不要沿用仓库示例值

---

## 使用

1. 按 `SKILL.md` 的「安装」一节选一条路线：本地试跑用 Docker Compose，生产看官方部署文档。
2. 首次启动前先完成元数据库迁移与角色初始化（`superset db upgrade` → `superset fab create-admin` → `superset init`）；用 Compose 时这三步由初始化服务自动跑。
3. 浏览器打开 `http://localhost:8088`，用刚建的管理员登录。
4. 在界面里添加数据库连接 → 建数据集 → 出图 → 存看板。
5. 需要脚本化时走 REST API；需要嵌进 K8s 时用仓库里的 Helm Chart。
6. 完整子命令与配置项以 `superset --help` 和官方文档为准。

---

## 依赖

- Docker 与 Docker Compose（容器路线），或 Python 虚拟环境（pip 路线）
- 元数据库：PostgreSQL / MySQL 等；缓存与消息队列：Redis
- 异步任务组件 Celery worker 与 beat（定时刷新、截图等依赖它）
- 想要连的数据源对应的 Python 驱动，需自行安装或打进自定义镜像
- Python 版本与各组件具体版本要求以仓库 `pyproject.toml` 和官方安装文档为准

---

## 安全

- 不内嵌任何密钥
- 仓库自带的 `docker/.env` 只用于本地试跑，其中的数据库口令与 `SUPERSET_SECRET_KEY` 都是公开示例值，上线必须整体替换
- 默认管理员口令是 `admin`，首次登录后立即修改或直接改成强口令创建
- 给数据库连接使用最小权限账号，避免平台侧误操作波及生产数据
- 对外暴露前配置好反向代理、HTTPS 与认证方式，不要直接把 8088 端口裸奔在公网
- 看板分享链接等于数据访问凭证，注意分享范围
- 缓存与结果表里可能残留查询结果，敏感数据场景要一并规划清理

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`superset`
- 仓库：https://github.com/apache/superset

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
