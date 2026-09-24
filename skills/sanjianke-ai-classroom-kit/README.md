# 三剪客 · 多智能体互动课堂 Skill

把主题或文档一键变成多智能体互动课堂

---

## 前置条件

- **Node.js ≥ 22.19**、**pnpm ≥ 10**（低于 22.19 会在安装阶段直接失败）
- 至少一个模型服务商的 API Key，自己申请、自己付费
- 可选：TTS 的 Key（要语音讲解）、检索的 Key（要联网）、Docker Engine + Compose v2（走容器路线）

---

## 使用

1. 取代码并安装依赖：

   ```bash
   git clone https://github.com/THU-MAIC/OpenMAIC.git
   cd OpenMAIC
   pnpm install
   cp .env.example .env.local
   ```

2. 在 `.env.local` 里至少填一组 Key 与默认模型（`DEFAULT_MODEL` 必须带服务商前缀）：

   ```env
   OPENAI_API_KEY=sk-...
   DEFAULT_MODEL=openai:gpt-5.5
   ```

3. 起服务并自检：

   ```bash
   pnpm dev
   curl -s http://localhost:3000/api/health
   ```

4. 打开 `http://localhost:3000` 输入主题，或直接调异步生成接口：

   ```bash
   curl -s -X POST http://localhost:3000/api/generate-classroom \
     -H 'Content-Type: application/json' \
     -d '{"requirement":"用 20 分钟讲清傅里叶变换的直觉","agentMode":true}'
   ```

详细路线见 `SKILL.md` 的「工作流路由」，以及 `references/` 下的三份文件。

---

## 依赖

| 项目 | 要求 |
|---|---|
| 运行时 | Node.js ≥ 22.19；pnpm ≥ 10 |
| 服务商 | 19 家 LLM 服务商任选其一，或任何兼容 OpenAI 接口的服务 |
| 容器路线 | Docker Engine + Compose v2 |
| 服务端持久化 | PostgreSQL 16（`--profile server-persistence`） |
| MP4 导出 | 独立渲染容器（`--profile video-export`），标准档 8 GiB 内存上限 |

---

## 安全

- 不内嵌任何密钥
- 所有 API Key 由使用者本人写进本机 `.env.local` 或 `server-providers.yml`，本 Skill 不代填、不回显
- `ACCESS_CODE` 只是单口令门禁，不等同于账号体系；对外服务时必须设置
- 服务端持久化的开发令牌会被编译进浏览器 bundle，仅适用于本机或可信内网的单用户部署，生产必须替换为真正的会话校验
- 生成的课程内容需由使用者自行审核学科正确性与版权归属

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：OpenMAIC（MIT）

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
