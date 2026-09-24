# 三剪客 · 开源无头电商平台 Skill

把「电商后端」这件事整个买下来自己跑：Spree 提供一套自托管的商品、订单、库存、支付、促销、税费与多渠道内核，通过 REST API 对外输出，前端由你决定用官方 Next.js 店面还是自己写。含两条安装路径（create-spree-app 一键起、Rails 手动装）、CLI 与管理 API 的常用命令、凭证的分层解析规则，以及只读密钥写不了数据这类高频卡点。

---

## 前置条件

- **走一键脚手架**：Node.js（官方安装文档写的是 20 以上，仓库另一处写 22 以上，以你实际拉到的版本要求为准）＋ 本机 Docker 正在运行。Docker 没起会直接失败。
- **走手动 Rails 安装**：Ruby、图像处理库 vips（`libvips`）、Rails，再加一个可连的关系型数据库。
- **想直连管理 API**：需要一个正在运行的 Spree 实例；远程店铺还需要一个带对应范围的 API 密钥。
- **想上线**：一台能跑 Docker 的主机（云主机 / 自建服务器 / 容器平台），以及前端要部署的目标环境。
- **做真实收款**：支付服务商的商户号，以及按需准备的税务、搜索、分析、营销等第三方账号。
- 磁盘与内存留余量：容器方式会同时拉起后端与数据库等若干服务。

---

## 使用

最短跑通路径（一键脚手架）：

```bash
npx create-spree-app@latest my-store
```

交互中选「后端 + Next.js 店面」或「只要后端」，可选是否灌入示例数据。完成后后台默认在 `http://localhost:3000/admin`，端口被占用时以命令输出为准。

进项目目录后的日常动作：

```bash
spree dev                                    # 起开发栈，Ctrl+C 停
spree stop                                   # 停服务
spree logs                                   # 看日志
spree api get /orders -q status_eq=complete --limit 10
spree api endpoints --search refund          # 离线看有哪些端点
spree api schema "POST /orders/{id}/refunds" # 看某个端点的请求体结构
spree generate api_resource Brand name:string description:rich_text
```

写数据前先确认密钥范围：本地自动生成的密钥只带只读范围，`post` / `patch` / `delete` 需要显式创建带写范围的密钥。远程店铺用 `spree auth login --profile <名字> --base-url <地址>` 保存凭证；脚本与 CI 环境走 `SPREE_API_KEY`，需要指向远程时再配 `SPREE_BASE_URL`。

完整的安装选项、数据库参数、部署方式与全部 CLI 子命令，以官方文档为准（见 `SKILL.md` 的参考文件表）。

---

## 依赖

- **运行时**：Node.js（一键路径）或 Ruby / Rails（手动路径）。
- **容器**：Docker，一键路径用它拉起后端栈。
- **图像处理**：vips，手动安装路径必需。
- **存储**：关系型数据库；容器方式会一并启动。
- **命令行工具**：`@spree/cli`（脚手架创建的项目已自带，也可全局安装或 `npx` 调用）。
- **可选**：支付、税务、搜索、分析、营销等第三方服务，按实际启用情况准备。
- **可选**：TypeScript 项目可接官方 SDK；前端可接官方独立的 Next.js 店面工程。

---

## 安全

- 不内嵌任何密钥
- API 密钥与主机是**成对解析**的：`SPREE_API_KEY` 单独用时默认指向本机 `http://localhost:3000`，指向远程必须配合 `SPREE_BASE_URL`，不要靠改地址来「换店铺」。
- 本地自动生成的密钥只带只读范围，保存在项目下被 gitignore 的凭证文件里，**不要提交到仓库**。
- 写操作密钥按最小范围创建（只给需要的写范围），不要图省事给全权限。
- 本地默认口令仅用于开发，上生产前必须全部替换；生产数据要落到持久化的数据库与存储卷。
- 支付、订单、退款属于资金相关操作，对真实数据批量写入前先做幂等与权限验证。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`spree`
- 仓库：https://github.com/spree/spree

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
