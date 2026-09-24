# 三剪客 · 思源笔记本地知识库 Skill

思源笔记 siyuan：本地优先的块级知识库，自带内核 HTTP API 与命令行，能把笔记、搜索、导入导出接到自动化流水线里。

---

## 前置条件

- 桌面端：Windows / macOS / Linux 安装包，或应用商店版本；服务端：Docker（推荐）。
- 想用命令行，需要安装目录里的内核二进制在 `PATH` 上（Windows 安装包会自动加；macOS / Linux 需要自己建软链）。
- 想用 HTTP 接口，需要内核正在运行（默认端口 6806），并在「设置 - 鉴权 - API token」里拿到 token。
- Docker 部署必须准备一个锁屏密码（或配好 OIDC），并把工作空间目录挂载进容器。
- 批量写入或删除前，先备份一份工作空间。

---

## 使用

1. 先确定工作空间路径，命令行统一用 `-w` 传进去。
2. 用 `siyuan notebook list -w <工作空间>` 拿到笔记本 ID，后续操作基本都要靠它。
3. 只读类需求（搜索、导出、SQL 统计）直接用命令行；需要实时读写或跟界面联动时才走 6806 的 HTTP 接口。
4. 命令默认输出表格，接脚本时加 `-f json`。
5. 具体子命令的参数以 `siyuan <子命令> --help` 为准，不要跨版本照搬参数名。
6. 完整命令树看 `siyuan --help`。

---

## 依赖

- 思源笔记内核（随桌面安装包提供，或通过 `b3log/siyuan` Docker 镜像运行）。
- Docker / Docker Compose：仅在服务端部署时需要。
- curl 或等价 HTTP 客户端：仅在调用内核接口时需要。
- 可选：OIDC 身份提供方凭据；对象存储或 WebDAV 账号（用于同步到第三方存储）。

---

## 安全

- 不内嵌任何密钥，token 与密码都要在执行时提供。
- Docker 部署不要用 `SIYUAN_ACCESS_AUTH_CODE_BYPASS=true` 绕过访问授权；那会让知识库对任何能访问端口的人开放。
- 内核 API token 等同账号权限，不要写进脚本常量、日志或公开仓库。
- 工作空间的 `conf.json` 里含 token、同步凭据、OIDC client secret 等字段，共享或提交前先排查。
- 不要把工作空间放进第三方同步盘做同步，官方明确说明会导致数据损坏。
- 反代到公网时必须配上 HTTPS 和 `/ws` 的 WebSocket 转发。
- 批量写入、删除、重建索引都会改动真实数据；操作前先导出备份。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`思源笔记 siyuan`
- 仓库：https://github.com/siyuan-note/siyuan

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
