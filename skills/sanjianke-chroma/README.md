# 三剪客 · 轻量向量库 Skill

嵌入式向量库的选型、安装、集合增删改查、embedding 接入与服务端模式，以及数据留存、离线部署这类真实坑。

---

## 前置条件

- Python 环境与 pip（或 Node.js 与 npm，如果你用 JS 客户端）。
- 系统自带 `sqlite3` 版本要够新，否则启动直接失败。
- 用默认内置 embedding 时，首次运行需要联网下载模型文件；离线环境要提前准备本地 embedding。

## 使用

1. `pip install chromadb` 装客户端与 CLI。
2. 原型阶段用 `chromadb.Client()`；**一旦数据要留存，立刻换成持久化客户端或服务端模式**。
3. 建集合 → `add` 入库 → `query` 检索，需要时加 `where` 元数据过滤。
4. 要多进程 / 多机共享一份数据，就 `chroma run --path /db_path` 起服务端，客户端改用 `HttpClient` 连接。

完整示例、坑表与自检清单见 `SKILL.md`。

## 依赖

- Python（或 Node.js）运行环境。
- 较新版本的 `sqlite3`（由运行环境提供）。
- 可选：Chroma Cloud 账号（用托管服务时）、第三方 embedding 服务的 API Key。
- 可选：能常驻的进程与可访问端口（用服务端模式时，默认 8000）。
- 具体版本要求以包在 PyPI / npm 上的声明为准。

## 安全

- 不内嵌任何密钥
- 使用 Chroma Cloud 或第三方 embedding API 时，Key 一律通过环境变量传入，不要写进代码或提交到仓库。
- 持久化目录里就是你的全部向量数据，必须纳入备份；`delete_collection` 与 `collection.delete` 都是破坏性且无回收站的操作。
- 服务端模式默认监听本机；对外暴露前要自行加访问控制，`chroma run` 本身不负责鉴权与权限隔离。
- 能力边界见 SKILL.md 的「能力边界」一节。

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Chroma`
- 仓库：https://github.com/chroma-core/chroma

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
