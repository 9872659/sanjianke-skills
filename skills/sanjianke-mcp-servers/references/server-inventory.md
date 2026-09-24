# MCP 参考服务器逐个说明 + 归档清单 + 客户端配置矩阵

本文件是 `SKILL.md` 的展开。服务器数量与包名以主仓库当前 README 与各子目录 README 为准，包名会随版本变，装之前建议核对一次。

---

## 一、7 个现行参考服务器

### 1. Everything（协议特性演示 / 客户端自测）

- **定位**：把 MCP 协议的特性尽量都跑一遍的测试服务器，官方明说它「不是有用的服务器」，而是给**写 MCP 客户端的人**用的。
- **能力**：实现 prompts、tools、resources、sampling 等；注册的协议原语完整清单在它自己的 `docs/features.md`。
- **启动**：
  ```bash
  npx -y @modelcontextprotocol/server-everything
  npx @modelcontextprotocol/server-everything stdio       # 显式指定 stdio
  npx @modelcontextprotocol/server-everything sse         # HTTP+SSE（已被协议标记为废弃）
  npx @modelcontextprotocol/server-everything streamableHttp
  npm install -g @modelcontextprotocol/server-everything@latest
  ```
- **从源码跑 HTTP 传输**：`cd src/everything && npm install && npm run start:streamableHttp`（或 `npm run start:sse`）。
- **什么时候用**：你在写客户端，要做协议覆盖度回归。

### 2. Fetch（网页抓取转 Markdown）

- **包**：`mcp-server-fetch`（Python）。工具只有一个 `fetch`。
- **参数**：`url`（必填）、`max_length`（默认 5000）、`start_index`（默认 0，用于分块续读）、`raw`（不转 Markdown 取原始内容）。
- **还提供 prompt**：`fetch`（给一个 URL，抓回来转 Markdown）。
- **启动**：`uvx mcp-server-fetch`，或 `pip install mcp-server-fetch` + `python -m mcp_server_fetch`；Docker 镜像 `mcp/fetch`。
- **可调项**：`--ignore-robots-txt`、`--user-agent=...`、`--proxy-url`；Windows 上设 `PYTHONIOENCODING=utf-8` 解决超时。
- **风险**：官方 CAUTION 原文指出它能访问本地/内网 IP 地址，可能造成安全问题。

### 3. Filesystem（受限目录内的文件操作）

- **包**：`@modelcontextprotocol/server-filesystem`（Node）。Docker 镜像 `mcp/filesystem`。
- **工具**：`read_text_file`、`read_media_file`、`read_multiple_files`、`write_file`、`edit_file`（支持 dryRun 预览与 diff）、`create_directory`、`list_directory`、`list_directory_with_sizes`、`move_file`、`search_files`、`directory_tree`、`get_file_info`、`list_allowed_directories`。
- **授权模型**：两条路——命令行参数指定允许目录，或客户端通过 **Roots** 动态下发。**客户端下发的 Roots 会完全替换命令行给的目录**。官方强调：既没有命令行目录、客户端又不支持 Roots 时，初始化就会报错。
- **工具注解**：它给每个工具打了 MCP ToolAnnotations（是否只读、是否幂等、是否有破坏性）；写操作里 `write_file` 与 `edit_file`、`move_file` 被标为可能有破坏性，`edit_file` 不幂等。客户端可据此做确认提示。
- **启动**：
  ```bash
  npx -y @modelcontextprotocol/server-filesystem /path/to/dir1 /path/to/dir2
  ```
  Docker 方式所有目录必须挂到 `/projects` 下，加 `ro` 变只读。
- **构建镜像**：`docker build -t mcp/filesystem -f src/filesystem/Dockerfile .`

### 4. Git（仓库读取与操作）

- **包**：`mcp-server-git`（Python）。Docker 镜像 `mcp/git`。
- **依赖约束**：需要 MCP Python SDK 1.x（`mcp>=1.29.0,<2`）。
- **工具（12 个）**：`git_status`、`git_diff_unstaged`、`git_diff_staged`、`git_diff`、`git_commit`、`git_add`、`git_reset`、`git_log`（支持 `max_count` 与起止时间过滤）、`git_create_branch`、`git_checkout`、`git_show`、`git_branch`。
- **启动**：
  ```bash
  uvx mcp-server-git --repository path/to/git/repo
  pip install mcp-server-git && python -m mcp_server_git --repository path/to/git/repo
  ```
- **状态**：官方标注该服务器仍处早期开发，工具集可能变动。
- **构建镜像**：`cd src/git && docker build -t mcp/git .`

### 5. Memory（知识图谱持久记忆）

- **包**：`@modelcontextprotocol/server-memory`（Node）。Docker 镜像 `mcp/memory`。
- **模型**：实体（Entity：唯一名称 + 类型 + 观察列表）、关系（Relation：`from` / `to` / `relationType`，主动语态）、观察（Observation：原子化的事实字符串）。
- **工具**：`create_entities`、`create_relations`、`add_observations`、`delete_entities`、`delete_observations`、`delete_relations`、`read_graph`、`search_nodes`、`open_nodes`。
- **资源**：`memory://knowledge-graph`（MIME `application/json`）；写操作会向订阅者发 `notifications/resources/updated`，客户端能看到实时变化。
- **存储位置**：环境变量 `MEMORY_FILE_PATH` 指定 jsonl 路径；默认是服务器目录下的 `memory.jsonl`。
- **Docker 注意**：官方提醒旧 `mcp/memory` 卷里存在一个 `index.js`，可能被新容器覆盖，用卷存储时要先删掉它。
- **用法提示**：官方 README 给了一段「怎么让模型持续写记忆」的系统提示示例，本质是要求模型开场先读图、对话中按身份/行为/偏好/目标/关系分类写回。想让它真的记住，人设提示词要配合写。

### 6. Sequential Thinking（分步思考 / 可回退 / 可分支）

- **包**：`@modelcontextprotocol/server-sequential-thinking`（Node）。Docker 镜像 `mcp/sequentialthinking`。
- **工具**：只有一个 `sequential_thinking`。入参包含 `thought`、`nextThoughtNeeded`、`thoughtNumber`、`totalThoughts`，以及修订与分支相关字段 `isRevision`、`revisesThought`、`branchFromThought`、`branchId`、`needsMoreThoughts`。
- **怎么算生效**：宿主会在一次任务里**反复调用**这个工具（而不是一次性给答案）；宿主/Inspector 里能看到 repeated calls。装完要重启或重载宿主，并确认工具出现在清单里。
- **可调项**：环境变量 `DISABLE_THOUGHT_LOGGING=true` 关掉思考内容日志。
- **注意**：正常使用是「把服务器接上，然后让模型自己多步思考」，而不是人手去调工具。

### 7. Time（当前时间与时区换算）

- **包**：`mcp-server-time`（Python）。Docker 镜像 `mcp/time`。
- **工具**：`get_current_time`（`timezone`，IANA 名称如 `Asia/Tokyo`）、`convert_time`（`source_timezone` / `time` / `target_timezone`）。
- **时区来源**：默认自动探测系统时区，可用 `--local-timezone=America/New_York` 覆盖。
- **启动**：`uvx mcp-server-time` 或 `python -m mcp_server_time`。
- **返回**：时间戳带偏移与 `is_dst` 标记；换算还给出 `time_difference`。

---

## 二、已归档（不要作为新接入的首选）

以下参考服务器已移入 `servers-archived` 仓库，主仓库不再维护：

AWS KB Retrieval、Brave Search、EverArt、GitHub、GitLab、Google Drive、Google Maps、PostgreSQL、Puppeteer、Redis、Sentry、Slack、SQLite。

其中至少有一条明确的替代关系：**Brave Search 已被官方服务器取代**（npm 包 `@brave/brave-search-mcp-server`）。其余请到 MCP Registry 找当前维护的实现。

> 主仓库 README 里的示例仍会出现 `mcpServers` 中的 `github` / `postgres` 片段，那只是配置写法示范，不代表这两个服务器还在主仓库维护。

---

## 三、客户端配置矩阵

| 客户端 | 配置位置 | 顶层键 | 备注 |
|---|---|---|---|
| Claude Desktop | `claude_desktop_config.json` | `mcpServers` | Windows 上 `npx` 项要用 `cmd` + `/c` |
| VS Code | 用户级配置（命令面板 `MCP: Open User Configuration`）或 `.vscode/mcp.json` | `servers`（`.vscode/mcp.json` 里再套 `mcp`） | 部分服务器有官方一键安装按钮 |
| Zed | `settings.json` | `context_servers` | 例：`"mcp-server-git": {"command": {"path": "uvx", "args": ["mcp-server-git"]}}` |
| Codex CLI | 命令行添加 | — | `codex mcp add sequential-thinking npx -y @modelcontextprotocol/server-sequential-thinking` |
| 自建客户端 | 你自己实现 | — | 用官方 SDK；参考 Everything 服务器做协议回归 |

其他支持 MCP 的客户端，加自定义服务器的做法大同小异：填一个名称、给一份「命令 + 参数 + 可选环境变量」的启动配置，然后确认工具列表里出现目标工具。具体入口以各客户端文档为准。

---

## 四、自建客户端的三个决定

| 决定 | 选项 | 说明 |
|---|---|---|
| 传输 | stdio / Streamable HTTP | 参考服务器基本都用 stdio（客户端起子进程）；HTTP+SSE 已被协议标记废弃 |
| SDK 语言 | C#、Go、Java、Kotlin、PHP、Python、Ruby、Rust、Swift、TypeScript | 用哪门语言写客户端就选哪门；官方文档站有入门指引 |
| 工具暴露策略 | 全量 / 白名单 / 按需 | 参考服务器里 Filesystem 的写操作带破坏性注解，适合据此做确认或名单控制 |

---

## 五、本文件不覆盖

- 各语言 SDK 的完整 API（在各自 SDK 仓库）。
- MCP 协议的完整规范（在 `modelcontextprotocol.io`）。
- 社区与第三方服务器清单（在 MCP Registry）。
- 具体包版本号与发布时间：上游变动频繁，请以 npm / PyPI / 仓库 releases 为准。
