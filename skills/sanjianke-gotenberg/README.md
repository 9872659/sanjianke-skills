# 三剪客 · 文档转换 HTTP API Skill

Gotenberg 是一个 Docker 里跑起来的文档转换 API：发 multipart/form-data，拿回 PDF。它把 Chromium、LibreOffice 和一整套 PDF 引擎打包好，你不用自己装浏览器、字体和 Office 运行库，一个 curl 就能出 PDF。

---

## 前置条件

- **Docker**：Docker Engine 或 Docker Desktop。Gotenberg 只有 Docker 一种分发方式。
- **端口**：宿主 `3000` 空闲（或自行映射到别的端口）。
- **内存**：官方基线为 512Mi–1Gi，实际建议给到 1–2GB。
- **网络**：做 URL 转换或截图时，容器必须能出网访问目标站点。
- 不需要任何账号、API Key 或云端订阅——这是自托管软件。

---

## 使用

1. 先按 `SKILL.md` 的「安装」一节把容器拉起来，**务必绑到本机回环**（`-p "127.0.0.1:3000:3000"`），它默认没有任何鉴权。
2. 按「常用操作」挑最接近你任务的 curl 命令，改掉文件路径直接跑。
3. 拿不准路由路径或字段名时查 `references/routes.md`。
4. 要调超时、并发、镜像变体、Webhook 异步或云平台部署，查 `references/operations.md`。
5. 出问题先查 `references/pitfalls.md`，里面按现象分类，覆盖字体、渲染差异、超时并发、PDF 引擎能力差异与安全加固。

**最该记住的三条**：

- Chromium 默认按 `print` 媒体类型渲染，要还原屏幕效果得传 `emulatedMediaType=screen`，要背景得传 `printBackground=true`。
- 合并是按**文件名**排序，不是上传顺序。
- 请求默认 **30 秒**超时，大文档要先放大 `--api-timeout`。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| Docker | 唯一部署方式 |
| Chromium | 已内置在镜像中，负责 URL / HTML / Markdown 转 PDF 与截图 |
| LibreOffice | 已内置在镜像中（完整版与 `:8-libreoffice` 变体），负责 Office 文档转换与 PDF/A 转换 |
| PDF 引擎 | 已内置 ExifTool / PDFtk / pdfcpu / QPDF / UNO，按特性分工 |

调用侧不需要任何语言 SDK——它就是普通 HTTP 接口，curl、requests、fetch 都能打。官方另有 PHP 客户端等社区 SDK。

---

## 安全

- 不内嵌任何密钥。本 Skill 不含凭据、不代发请求。
- **Gotenberg 默认完全无鉴权**，且 `-p 3000:3000` 默认对所有网卡开放。请绑定 `127.0.0.1`，必须对外时开启 Basic Auth 或 OIDC，并在前面加反向代理解 TLS 与限流。
- 它是一个能出网、能拉任意 URL、能执行 JavaScript 的浏览器。配 `--chromium-deny-private-ips=true` 可以防止它被当作 SSRF 跳板扫内网。
- 官方 demo（`demo.gotenberg.dev`）有速率限制且**不应用于任何敏感文件**。
- 上传文档本身不可信：LibreOffice 侧从 8.34.0 起已禁止上传文档触发外链抓取，但升级前的老版本存在风险，请保持更新。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Gotenberg`
- 仓库：https://github.com/gotenberg/gotenberg

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
