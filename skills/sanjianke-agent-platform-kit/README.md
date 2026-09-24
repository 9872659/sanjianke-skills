# 三剪客 · 全能 AI Agent 平台 Skill

把 AI 助手跑在自己设备上的开源 Agent 平台。

本 Skill 介绍上游项目 OpenClaw 的形态、安装方式、模型与通道接入、核心能力面与扩展体系，并给出四类故障的排查顺序。正文为原创整理，不包含上游源码。

---

## 前置条件

- 目标机器需要 Node.js `>=24.16.0 <25` 或 `>=26.1.0`；官方安装脚本可在缺失时自动补装。
- 支持 macOS、Linux、Windows（原生伴侣 App / PowerShell 安装器 / WSL2）与移动端节点。
- 至少准备一个模型 provider 的 API Key，或机器上可复用的 CLI / OAuth 登录态。
- 想接聊天通道的话，再准备对应平台的 Bot Token 或可扫码登录的账号。
- 本 Skill 本身不需要额外环境；它描述的是上游产品的操作方式，不代跑任何服务。

---

## 使用

1. 先看 `SKILL.md` 的「快速开始」，用最小路径把 Gateway 跑起来并确认控制台能对话。
2. 安装路线、目录与端口、模型与通道配置、Docker 与远程接入，见 `references/install-and-config.md`。
3. 工具档位、会话权限与沙箱、多 Agent、记忆与定时任务、技能与插件，见 `references/capabilities-and-usage.md`。
4. 写自己的技能或插件、遇到故障按阶梯排查、升级回滚与卸载，见 `references/extend-and-troubleshoot.md`。

命令都以 `openclaw` 开头。落到具体版本时以 `<命令> --help` 的实时输出为准。

---

## 依赖

- **被介绍的产品**：OpenClaw（本 Skill 不打包、不修改、不代理它）。
- **运行时**：Node.js 24.16+ / 26.1+；从源码构建需 Corepack 与 pnpm 12.3.4。
- **可选**：Docker Engine 或 Desktop + Compose v2（容器化部署）、Tailscale 或 SSH（远程接入）。
- **凭证**：模型 provider 的 Key 或 OAuth 登录态、聊天通道的 Bot Token、Gateway 共享密钥。全部由使用者自备。

---

## 安全

- 不内嵌任何密钥，也不代管使用者的凭证。
- 不主动把任何内容发往外部地址；所有出网行为都来自使用者自己安装并运行的被介绍产品。
- 若正文涉及联网或读写文件，权限范围已在 `SKILL.md` 的「权限与用途说明」中逐项列明。
- 能力边界见 `SKILL.md` 的「能力边界」一节；上游产品的沙箱与执行审批默认关闭，对外暴露前必须自行完成硬化配置。

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：OpenClaw

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
