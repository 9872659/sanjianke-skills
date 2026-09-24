# 三剪客 · 全网数据采集引擎 Skill

网页搜索、抓取与交互一体化的数据采集 API 与命令行工具

---

## 前置条件

- 能访问上游 HTTP 接口：云端 `https://api.firecrawl.dev`，或你自托管的 `http://localhost:3002`。
- 云端模式需要一个 `FIRECRAWL_API_KEY`（形如 `fc-...`），放在环境变量里，不要写进文件。
- 自托管模式需要 Git、Docker Engine 或 Docker Desktop、Docker Compose v2（命令是 `docker compose`），宿主 `3002` 端口空闲。
- CLI 与 Node SDK 需要 Node.js 18+；Python SDK 为 `pip install firecrawl-py`，需要 Python 3.9+。

---

## 使用

最小可用路径（云端，单页抓取）：

```bash
export FIRECRAWL_API_KEY=fc-你的Key

curl -s -X POST https://api.firecrawl.dev/v2/scrape \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["markdown"],"onlyMainContent":true,"maxAge":3600000}'
```

三条常用路径：

| 目标 | 命令 |
|---|---|
| 已知 URL 取一页 | `firecrawl scrape https://example.com` |
| 只给关键词 | `firecrawl search "关键词" --limit 5 --pretty` |
| 先看有哪些 URL 再决定抓什么 | `firecrawl map https://example.com --limit 500 -o urls.txt` |

读完 SKILL.md 后按需深入：`references/quickstart.md`（部署与首次调用）、`references/api-playbook.md`（接口参数与返回）、`references/pitfalls.md`（反爬、限流、成本、报错）。

---

## 依赖

| 项 | 说明 |
|---|---|
| 网络 | 出网访问上游 API；自托管节点还须能出网访问目标站点 |
| 凭据 | 云端模式需 `FIRECRAWL_API_KEY`；自托管 `USE_DB_AUTHENTICATION=false` 可免 Key |
| Node.js | 18+，用于 CLI 与 Node SDK |
| Python | 3.9+，用于 `firecrawl-py` |
| Docker | 自托管模式的 Docker Engine / Desktop + Compose v2 |
| 模型服务 | 自托管下 `json` 抽取、`summary`、`/agent` 需自接 OpenAI 兼容端点或 Ollama |

---

## 安全

- 不内嵌任何密钥
- 所有请求由使用者自己的 Key 或自托管实例承担，本 Skill 不代理转发、不代收费用。
- 抓取前请确认目标站点的 robots.txt、使用条款与所在地法规；上游默认遵守 robots.txt。
- 需要登录态的内容必须自行取得合法授权，本 Skill 不提供任何绕过登录的手段。
- 自托管栈默认**无鉴权**，暴露到不可信网络前必须补齐身份方案、TLS 与网络策略。
- 自托管注意上游主项目为 AGPL-3.0，对外提供修改过的服务前需评估传染性条款。

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：Firecrawl（AGPL-3.0）

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
