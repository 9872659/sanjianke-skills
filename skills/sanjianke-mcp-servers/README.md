# 三剪客 · MCP 官方服务器集 Skill

MCP 官方 servers 仓库包含哪些参考服务器、各自包名与启动命令、Claude Desktop/VS Code/Codex 的配置写法、Windows 与安全避坑

---

## 前置条件

- **Node.js**：用 `npx` 跑 Node 系服务器时需要（Filesystem、Memory、Sequential Thinking、Everything）。
- **`uv` / `uvx`** 或 **`pip` + Python 环境**：跑 Python 系服务器时需要（Git、Fetch、Time）。
- **Docker**：走容器方式时需要本机 Docker 可用。
- **MCP Python SDK 1.x**（`mcp>=1.29.0,<2`）：Python 系服务器明确要求这个区间，SDK 2.0 改了它们用到的 API。
- **一个 MCP 客户端**：Claude Desktop、VS Code、Zed、Codex CLI，或你自己用官方 SDK 写的客户端。
- 系统 `git` 可执行文件（用 Git 服务器时）。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径（先验证服务器，再写进客户端）：

```bash
# 单独验证服务器能不能起来
npx @modelcontextprotocol/inspector uvx mcp-server-git

# Node 系：直接跑
npx -y @modelcontextprotocol/server-memory

# Python 系：uvx 直接跑
uvx mcp-server-fetch
```

写进 Claude Desktop 配置（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/username/Desktop"]
    }
  }
}
```

Windows 上所有 `npx` 项都要写成 `"command": "cmd"` + `"args": ["/c", "npx", ...]`；`uvx` 项不用改。

7 个参考服务器的逐个说明、归档清单与客户端配置矩阵见 `references/server-inventory.md`。包名与配置写法以各服务器目录下的 README 为准。

---

## 依赖

- Node.js（`npx` 方式）
- `uv` / `uvx`（官方推荐的 Python 方式）或 `pip`
- Docker（容器方式）
- MCP Python SDK 1.x（`mcp>=1.29.0,<2`，Python 系服务器）
- 系统 `git`
- 一个支持 MCP 的客户端

---

## 安全

- 不内嵌任何密钥
- 官方明确说明：这批服务器是**演示协议与 SDK 用法的参考实现，不是生产就绪方案**；上线前必须按自己的威胁模型做安全评估与加固
- Filesystem 服务器能写、能移动、能删文件，务必把允许目录收窄到最小；Docker 方式的只读挂载要加 `ro`
- Fetch 服务器官方明确警告：可访问本地/内网 IP 地址，存在安全风险，不要让它触达内网管理面或云元数据服务
- Memory 默认把知识图谱写成本地 jsonl 文件，文件路径与权限要自己管
- 配置里的 `env` 字段常用来承载第三方 token；不要把密钥提交到仓库或写进可分享的配置模板
- 服务器以客户端子进程或常驻容器方式运行，权限继承自启动它的进程

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`MCP Servers`
- 仓库：https://github.com/modelcontextprotocol/servers

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
