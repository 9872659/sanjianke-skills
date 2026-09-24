# 三剪客 · BI 即代码分析平台 Skill

把 BI 当代码管：指标与看板以文件形式进 Git，用 CLI 本地预览、CI 校验、走 PR 评审后发布，权限与业务口径统一收在语义层。

---

## 前置条件

- 一个分析型数据仓库（官方列出 BigQuery、Snowflake、Redshift、Databricks、Postgres、Trino、ClickHouse 等适配）
- **CLI 路径**：Node.js 与 npm，且 dbt Core 或 dbt Cloud CLI 能在 `dbt` 命令下调用
- **自托管 Docker 路径**：Docker + Docker Compose，另需一个 PostgreSQL 存元数据（与数据仓库是两回事）
- **自托管 K8s 路径**：可用的 Kubernetes 集群、`kubectl`、`helm`
- 必填密钥：`LIGHTDASH_SECRET`（加密落库数据，**丢失不可恢复**）、元数据库 `PGPASSWORD`；CI 中常用 `LIGHTDASH_API_KEY` / `LIGHTDASH_URL` / `LIGHTDASH_PROJECT`
- 数据应用相关命令需要 Node.js 20+
- 不想自建基础设施可直接用官方托管服务

---

## 使用

```bash
# CLI 安装与登录
npm install -g @lightdash/cli
lightdash login https://your-instance.lightdash.cloud
lightdash config get-project

# 从 dbt 模型生成 YAML → 本地预览 → 校验 → 部署
lightdash generate -s mymodel
lightdash preview
lightdash validate
lightdash deploy
```

```bash
# 自托管（Docker Compose，本地概念验证）
git clone https://github.com/lightdash/lightdash && cd lightdash
export LIGHTDASH_SECRET="<换成你自己的高强度随机串>"
export PGPASSWORD="<元数据库密码>"
docker compose -f docker-compose.yml --env-file .env up --detach --remove-orphans
```

`SKILL.md` 里有完整的 CLI 命令表、四种部署方式、环境变量说明，以及 dbt 依赖、项目上下文、密钥丢失、预览排除状态等完整避坑表。

---

## 依赖

- CLI：`@lightdash/cli`（npm 全局安装；macOS 走 Homebrew）
- CLI 外部依赖：Node.js、npm、dbt Core 或 dbt Cloud CLI
- 自托管：Docker / Docker Compose 或 Kubernetes + Helm；PostgreSQL 作为元数据库
- 仓库适配：BigQuery、Snowflake、Redshift、Databricks、Postgres、Trino、ClickHouse 等
- 数据应用脚手架：Node.js 20+ 与 npm
- 企业版功能在自托管上需要 License Key
- 不内嵌任何密钥；仓库凭证与 API Key 由使用者自行配置

---

## 安全

- 不内嵌任何密钥
- `LIGHTDASH_SECRET` 用于加密落库数据，**丢失后旧数据无法解密**：请存入密钥管理服务并备份，运行中的实例不要更换
- API Key 优先用 `lightdash login` 或 `LIGHTDASH_API_KEY` 环境变量；`--token` 会留在 shell 历史里（官方文档明确提示）
- CI 里不要明文打印凭证；用平台提供的 secret 机制注入
- 行级安全与用户属性配置好之前，不要把看板开放给业务方
- `rename` / `slug-update` / `deploy` 会影响线上内容，先 `--dry-run` 或先 `preview` 验证
- 仓库账号按最小权限授予；查询权限范围决定看板能看到的数据边界
- 嵌入到自有产品时，确认客户隔离与权限配置正确，避免跨客户数据泄漏

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`lightdash`
- 仓库：https://github.com/lightdash/lightdash

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
