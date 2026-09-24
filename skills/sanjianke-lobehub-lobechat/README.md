# 三剪客 · 现代 AI 聊天界面 Skill

LobeHub（原 LobeChat）：自托管一个现代 AI 聊天界面与 Agent 工作台——部署方式、模型接入配置、插件扩展与避坑要点。

---

## 前置条件

- 一个**真实可用的模型服务 Key**，或一个 OpenAI 兼容的中转 / 自建推理端点。没有它，界面部署起来也发不出消息。
- 按落地方式准备环境：
  - **Docker 方式**：本机或服务器已装 Docker 与 Docker Compose。
  - **一键部署方式**：Vercel / Zeabur / Sealos / 阿里云计算巢 账号之一。
  - **本地开发方式**：Node.js + pnpm（官方 README 明确列出），Bun 亦可走只起 SPA 的路径。
- Windows 用户注意：官方 Docker 引导脚本用的是 bash 进程替换语法，PowerShell / cmd 跑不了，需要 WSL 或 Git Bash。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径（Docker 自托管）：

```bash
mkdir lobehub-db && cd lobehub-db
bash <(curl -fsSL https://lobe.li/setup.sh) -l zh_CN
docker compose up -d
```

本地开发：

```bash
git clone https://github.com/lobehub/lobehub.git
cd lobehub
pnpm install
pnpm run dev          # 全栈开发（Next.js + Vite SPA）
bun run dev:spa       # 仅 SPA 前端（端口 9876）
```

模型接入三个关键环境变量：

| 环境变量 | 是否必填 | 作用 |
|---|---|---|
| `OPENAI_API_KEY` | 必填 | 模型服务密钥 |
| `OPENAI_PROXY_URL` | 可选 | 覆盖默认 API 基础地址，中转 / 自建推理必设 |
| `OPENAI_MODEL_LIST` | 可选 | `+` 增、`-` 隐、`模型=展示名`，英文逗号分隔 |

部署脚本、环境变量与目录结构随版本演进，落地前以官方自托管文档与仓库当前 README 为准。

---

## 依赖

- Docker + Docker Compose（容器部署路径）
- Node.js + pnpm（本地开发路径）；Bun（仅 SPA 路径）
- 一个可用的模型服务 Key；使用中转或自建推理时另需端点地址
- 服务端模式建议配数据库，具体存储方案以官方自托管文档为准

---

## 安全

- 不内嵌任何密钥
- `OPENAI_API_KEY` 只放在环境变量或 `.env` 里，且确认 `.env` 不会被提交进 Git
- 容器与数据目录按最小权限挂载，别把宿主机敏感目录整盘映射进去
- 自托管实例一旦暴露到公网，等于把你的模型额度开放出去，务必先配好访问控制
- 上游采用社区许可（LobeHub Community License，以仓库 `LICENSE` 为准），商用前先读条款

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LobeHub (LobeChat)`
- 仓库：https://github.com/lobehub/lobehub

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
