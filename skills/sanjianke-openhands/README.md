# 三剪客 · 自主编码 Agent Skill

OpenHands Agent Canvas 的安装（npm/Docker/源码）、agent-canvas 常用命令、VM 自托管加固、nginx 反代与多后端切换、权限边界

---

## 前置条件

- Node.js **22.12.x 或更高**（三种跑法都需要）。
- `uv`：Agent Server 通过 `uvx` 运行，必须安装。
- Docker：走 Docker 沙箱方式时需要（macOS/Windows 用 Docker Desktop，Linux 用 Docker Engine 或 Docker Desktop）。
- 一个宿主目录用于 `PROJECTS_PATH`，**必须在启动容器前创建好**。
- 一个可用的 LLM（自备 Key）或可达的模型服务。
- 公网自托管额外需要：可控的网络防火墙、可选域名 + nginx + certbot。
- 常驻场景建议准备 tmux 或 systemd。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径（本地评估，注意官方 WARNING：Agent 对宿主机文件系统有完整访问权）：

```bash
npm install -g @openhands/agent-canvas
agent-canvas
# 打开 http://localhost:8000
```

想收紧到指定项目目录，就换 Docker 沙箱方式：

```bash
export PROJECTS_PATH="$HOME/projects"
mkdir -p "$PROJECTS_PATH" "$HOME/.openhands"

docker run -it --rm -p 8000:8000 \
  -v "$HOME/.openhands:/home/openhands/.openhands" \
  -v "${PROJECTS_PATH}:/projects" \
  ghcr.io/openhands/agent-canvas:1.18.0
# 打开 http://localhost:8000/canvas
```

VM 自托管（公网模式）：

```bash
export LOCAL_BACKEND_API_KEY=$(openssl rand -base64 32)
npx @openhands/agent-canvas --public
```

组件与端口拓扑、加固顺序、systemd/tmux、nginx 反代与信任边界说明见 `references/self-hosting.md`。镜像版本号以仓库 releases 与官方文档当前内容为准。

---

## 依赖

- Node.js ≥ 22.12.x
- `uv`（Agent Server 通过 `uvx` 运行）
- Docker（沙箱方式）
- tmux 或 systemd（常驻）
- nginx + certbot（可选，挂域名与 TLS 时）
- 一个 LLM 服务与对应 API Key

---

## 安全

- 不内嵌任何密钥
- 无沙箱跑法（`agent-canvas` 直跑、源码 `npm run dev`）**直接在宿主机运行 agent-server**，官方用 WARNING 标注：Agent 对你的文件系统有完整访问权。要隔离就用 Docker 沙箱，只挂 `PROJECTS_PATH`
- 公网部署必须：生成并 `export LOCAL_BACKEND_API_KEY`、命令带 `--public`（否则 Key 会被打包进前端）、每个 `/api/*` 请求都校验 `X-Session-API-Key`
- 先把网络锁死再启动服务：入站只留自己 IP 的 SSH；agent server（18000）、automation（18001）、静态服务（3001）不得对外暴露
- 反代必须转发 WebSocket / SSE 所需的头，并放宽 read/send timeout，否则界面实时事件会断
- 内置编辑器与 Canvas 共享同一浏览器 origin，`localStorage` 里保存着该浏览器中**所有已注册后端**的 session key（官方 issue #16492）；不要在同一浏览器里混入不受信任的后端或编辑器扩展
- 项目务必有版本控制与备份：Agent 会真的改文件

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`OpenHands`
- 仓库：https://github.com/OpenHands/OpenHands

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
