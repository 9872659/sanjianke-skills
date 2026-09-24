# 三剪客 · 可视化 Agent 工作流 Skill

在可视化画布上搭建大模型应用，并通过内置 API 接进业务系统的操作指引

---

## 前置条件

- 装好 Docker，且 Docker Compose 版本 ≥ 2.24.0。
- 机器满足官方最低要求：CPU ≥ 2 Core、RAM ≥ 4 GiB。
- 磁盘空间要能容纳数据库、向量库、上传文件与容器镜像。
- 至少准备一个可用的大模型来源：外部供应商 API Key，或可被容器网络访问的自托管模型服务。
- 服务器能联网拉取镜像（离线部署需自行准备镜像）。

---

## 使用

1. 在仓库 `docker/` 目录下复制 `.env.example` 为 `.env`，按需修改。
2. `docker compose up -d` 启动，用 `docker compose ps` 确认所有服务正常。
3. 浏览器打开 `http://localhost/install` 完成管理员初始化。
4. 在界面里配置模型供应商并测试连通。
5. 按应用类型创建应用，在画布上拖节点编排，右侧实时调试。
6. 需要 RAG 就上传文档建知识库，在工作流里挂检索节点。
7. 发布应用，拿到 API 凭证，按官方 API 文档接入业务系统。
8. 升级走 `docker compose pull` + `docker compose up -d`，升级前先备份数据库与数据卷。

详细命令与避坑见 `SKILL.md`。

---

## 依赖

- Docker 与 Docker Compose 2.24.0+。
- `docker/docker-compose.yaml` 定义的多容器栈（后端、worker、前端、数据库、缓存、向量库等）。
- 官方镜像组织为 `langgenius`。
- 一个可用的大模型来源。
- 上游文档：<https://docs.dify.ai/>

---

## 安全

- 不内嵌任何密钥；模型供应商的 API Key 由使用者在界面中自行配置。
- 默认通过反向代理对宿主机暴露服务，生产环境必须自行加上 HTTPS、访问控制与网络隔离。
- 数据都在 Docker 数据卷里，升级或迁移前务必先备份；不要执行会移除数据卷的清理操作。
- 若正文涉及联网或读写文件，权限范围已在 SKILL.md 的「权限与用途说明」中逐项列明。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Dify`
- 仓库：https://github.com/langgenius/dify

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
