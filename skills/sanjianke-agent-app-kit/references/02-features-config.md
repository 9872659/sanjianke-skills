# 功能与配置

面向「它有什么能力、怎么接模型、资源怎么寻址、哪些值要在构建期填」。

## 1. 能力总览

| 能力 | 实际含义 |
|---|---|
| 自带模型 | 支持 Claude、GPT、Gemini 等多家供应商，走你自己的 API Key 或账号登录 |
| 真实 Linux shell | 设备上运行一个沙箱化的 Alpine Linux，Agent 可以装包、跑脚本、操作真实文件 |
| 设备能力集成 | 健康、日历、提醒事项、通讯录、HomeKit、蓝牙、剪贴板、媒体、闹钟等，以工具形式暴露给 Agent |
| 浏览器自动化 | Agent 代你浏览并与网页交互 |
| 技能与记忆 | 可扩展的技能包，加上跨会话的持久记忆 |
| 工作区 | 把工作切成互不干扰的上下文，通过 `minis://workspace/` 寻址 |
| 原生卸载 | 重活或平台相关的活交给原生代码，而不是沙箱 |

一句话概括架构取向：**沙箱负责通用计算，原生卸载负责平台能力**。当某项操作在沙箱里做不划算（性能、系统 API 不可达），就走原生通道。

## 2. 模型接入

### 2.1 供应商组织方式

`src/ios/Providers/` 是双端共享的供应商层，从目录结构可以直接读出支持的家族：

| 目录 / 文件 | 说明 |
|---|---|
| `Anthropic/`、`OpenAI/`、`Gemini/`、`xAI/`、`Kimi/`、`OpenRouter/`、`Antigravity/` | 各供应商实现 |
| `Voice/` | 语音相关供应商 |
| `Thinking/` | 思考等级目录（`ThinkingLevelCatalog.swift`） |
| `LLMProvider.swift`、`LLMProviderFactory.swift` | 供应商抽象与工厂 |
| `ProviderConfigStore.swift`、`ProviderConfigDB.swift` | 配置存储与持久化 |
| `ProviderInstance.swift`、`ProviderMigration.swift` | 实例管理与配置迁移 |
| `ModelEntry.swift`、`ModelGroup.swift`、`ModelGroupRouter.swift` | 模型条目、分组与路由 |
| `ModelsDevAPI.swift`、`ModelReleaseIndex.swift` | 模型清单来源与发布索引 |
| `OAuthRefreshCoordinator.swift`、`OAuthRefreshSingleFlight.swift` | OAuth 刷新协调（单飞，避免并发重复刷新） |
| `VisionGroupResolver.swift` | 视觉能力分组解析 |

`ModelGroupRouter` + `ModelReleaseIndex` + `ModelsDevAPI` 这三个文件说明模型清单不是写死的，而是**按来源动态解析并可按分组路由**。要接自建网关，通常从这里和 `ProviderConfigStore` 入手。

### 2.2 两条登录路径

1. **API Key** —— 最简路径，全程不需要任何构建期定制。
2. **账号登录（OAuth）** —— 以 Claude OAuth 凭证为例，需要构建期变量，见第 4 节。

## 3. `minis://` 资源寻址

`minis://` 是一套**会话作用域**的统一资源定位符，把三层打通：AI Agent、iSH Linux shell、iOS 宿主 App。同一个 URL 字符串在工具返回值、Markdown 渲染和组件间引用中都能用。

### 3.1 格式

```
minis://<namespace>/<path>
```

| 部分 | 说明 |
|---|---|
| `minis://` | 协议头，始终小写 |
| `<namespace>` | 顶层分类，映射到 URL 的 host |
| `<path>` | 命名空间内的相对路径，可含子目录，映射到 URL 的 path |

示例：

```
minis://attachments/screenshot.png
minis://attachments/photos/vacation/img_001.jpg
minis://workspace/report.csv
minis://workspace/project/src/main.py
minis://offloads/shell_execute_1707000000_abc12345.txt
minis://browser/snapshot_1707000000.jpg
```

### 3.2 会话语义

**URL 里故意不含会话 ID。** 原因是每一层都天然只有一个会话的视野：Agent 只在一个会话里工作，shell 的 `/var/minis/` 一次只挂载当前会话的文件，UI 按消息所属会话渲染。塞进会话 ID 反而会诱导出「跨会话引用」这种不被支持、也不该被支持的用法。

| 层 | 会话上下文来自哪 |
|---|---|
| Agent（工具执行） | 会话加载时设置的会话 ID |
| Shell（iSH 文件系统） | `/var/minis/` 挂载自当前会话的持久化存储 |
| Chat UI（Markdown 渲染） | 消息归属于某会话，渲染器用当前会话解析 |
| 持久化存储 | `Library/MinisChat/minis/<sessionId>/`，每会话一棵目录树 |

因此：

- **没有跨会话读**，也不存在 `minis://other-session/...` 这种写法。
- **没有跨会话写**，写 `/var/minis/` 永远落到当前会话。
- **会话删除即资源永久失效**，整棵 `Library/MinisChat/minis/<sessionId>/` 被移除。
- 回看历史会话时，URL 针对**那个会话**持久化的文件解析。

### 3.3 命名空间

**`attachments`** —— 媒体与可内联显示的文件

| 属性 | 值 |
|---|---|
| Linux 路径 | `/var/minis/attachments/<path>` |
| 持久化位置 | `Library/MinisChat/minis/<sessionId>/attachments/<path>` |
| 可写入者 | Agent（`file_write`、`shell_execute`）、宿主 App、用户输入附件 |
| 内联渲染 | 是 |

支持内联的类型：

- 图片：`.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` `.tiff` `.svg`
- 音频：`.mp3` `.m4a` `.wav` `.aac` `.ogg` `.flac`
- 视频：`.mp4` `.mov` `.m4v` `.avi` `.mkv` `.webm`

```markdown
![description](minis://attachments/filename.png)
![audio](minis://attachments/recording.mp3)
![video](minis://attachments/demo.mp4)
```

**`workspace`** —— 通用工作文件

| 属性 | 值 |
|---|---|
| Linux 路径 | `/var/minis/workspace/<path>` |
| 持久化位置 | `Library/MinisChat/minis/<sessionId>/workspace/<path>` |
| 可写入者 | Agent（`file_write`、`shell_execute`） |
| 内联渲染 | 否，只作为文本链接 |

```markdown
[report.csv](minis://workspace/report.csv)
```

此外还有 `offloads`（原生卸载产出，如 shell 执行记录）与 `browser`（浏览器快照）两个命名空间。

### 3.4 设计约束（写技能包时会用到）

- **Agent-first**：工具产出的每一个持久化资源，都**必须**以 `minis://` URL 形式回传给模型，否则后续轮次无法引用。
- **Render-ready**：聊天 UI 内联解析 `minis://`，图片/音频/视频在 Markdown 里原生渲染。
- **Bidirectional**：shell 写的文件和宿主 App 写的文件走同一套寻址。
- **会话内持久**：资源能扛住 App 重启；会话加载时挂载到 `/var/minis/`。

## 4. 构建期配置项

被注入的值不在仓库里，需从 `.example` 模板复制（见 `01-build-deploy.md` 第 2 节）。留空不影响编译与运行；某个功能需要它而它为空时，该功能在运行时报错。

### `ANTHROPIC_OAUTH_IDENTIFIER_PROMPT`

**只在你用 Claude OAuth 凭证登录时才相关。**

用 OAuth 认证的请求，Anthropic 端点要求 system prompt 以某个标识行开头（也就是 Claude Code 自己会发的那一行），缺了会被拒绝。构建会把这一行从这个值注入进去，所以它为空时 OAuth 登录在运行时失败。

上游**不提供该值**，需要自行准备。其它所有路径——Anthropic API Key，以及所有其它供应商——都不受此项影响。

> 提醒：直接照搬别处的标识行属于你自己的合规判断，本 Skill 不提供该内容。

## 5. 本地化

iOS 侧带 10 套本地化资源：`zh-Hans`、`zh-Hant`、`en`、`ja`、`ko`、`ru`、`es`、`fr`、`de`。字符串资源为 `.xcstrings`。`scripts/` 下有配套的本地化脚本（见 `03-extend-troubleshoot.md`）。

## 6. 技能包机制

**技能 = 一个含 `SKILL.md` 的文件夹**，可附带脚本、参考文件与素材。元数据常驻上下文用于触发判断；正文与随附资源只在技能真正被使用时加载。

关键兼容性事实：**它不是只认自己那套工具。** 为 Claude、Codex、OpenClaw 或 Hermes Agent 写的技能通常可以原样运行；针对本项目工具适配过的技能只是**跑得更好**——它们能直接触达 Linux shell、设备集成与原生卸载。

写技能包时按第 3.4 节的三条约束回传 `minis://` URL，是让它「跑得更好」的最简单一步。
