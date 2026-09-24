# 三剪客 · 知识库问答平台 Skill

把企业文档变成一个可私有化部署的问答服务的完整操作路径：部署 → 改密钥 → 接模型 → 建知识库 → 编排工作流 → 对外提供 API。

---

## 前置条件

- 一台能跑多容器的机器（Docker + Docker Compose），内存磁盘按数据量预留。
- 一套模型服务：至少一个对话模型 + 一个 embedding 模型（知识库必需），重排模型可选但建议配。
- 一个对象存储：官方 compose 默认 MinIO，也支持 S3 / 腾讯云 COS / 阿里云 OSS。
- 打算对外提供服务时，需要一个客户端能访问到的域名或地址（用于 `FE_DOMAIN`）。

---

## 使用

1. `bash <(curl -fsSL https://doc.fastgpt.io/deploy/install.sh)` 拉取部署配置，再 `docker compose up -d` 起服务。
2. 访问 `http://localhost:3000`，用默认 `root` / `1234` 登录，**立刻改密码并同步改掉 `DEFAULT_ROOT_PSW`**。
3. 在界面里配置对话模型与 embedding 模型，然后新建知识库并导入文档。
4. 新建对话工作流，接上知识库搜索节点与模型节点，先用「知识库单点搜索测试」验证检索。
5. 需要被外部系统调用时，走系统 OpenAPI（鉴权用 `ROOT_KEY`），接口细节以官方 OpenAPI 文档为准。

完整步骤、常见坑与自检清单见 `SKILL.md`。

---

## 依赖

- Docker / Docker Compose（社区自托管方式的硬前提）。
- 上游随编排一起提供的服务：MongoDB（副本集模式）、Redis、对象存储、向量库、插件服务、代码沙箱等。
- 可选：Sealos（一键部署）、Node.js + pnpm（仅本地开发方式需要）。
- 上游项目自身依赖与版本要求以仓库与官方文档为准。

---

## 安全

- 不内嵌任何密钥
- 官方 compose 模板里的 `ROOT_KEY`、`FILE_TOKEN_KEY`、`AES256_SECRET_KEY`、`INVOKE_TOKEN_SECRET`、数据库口令、对象存储密钥**全部是占位值**，对外暴露前必须逐个替换。
- 默认 root 密码 `1234` 是公开值；`DEFAULT_ROOT_PSW` 会在重启时强制重置密码，改密码时两个地方都要改。
- `FE_DOMAIN` 必须是客户端真实访问地址，填错会导致文件资源 404 或指向错误主机。
- MinIO 控制台（9001）、代码沙箱等内部端口不要直接开放到公网。
- 升级前先备份 MongoDB 与对象存储；`docker compose down -v` 会删数据卷，不要顺手加 `-v`。
- 上游许可证**不允许提供 SaaS 服务**，对外商用前请自行确认用法合规。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`FastGPT`
- 仓库：https://github.com/labring/FastGPT

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
