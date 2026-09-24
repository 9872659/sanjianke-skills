---
name: sanjianke-nonebot2
slug: sanjianke-nonebot2
displayName: 三剪客 · 多平台聊天机器人框架
description: "NoneBot2：Python 异步聊天机器人框架，用适配器 + 驱动器把同一套插件跑到 QQ、Telegram、飞书、Discord 等多个平台。本文讲清脚手架建项目、手动最小实例、.env 与 pyproject.toml 配置、插件加载与部署方式，以及版本、驱动、Pydantic 等高频坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "NoneBot2 的落地指引：Python 版本要求与 pipx 安装脚手架、nb create/nb run 全流程、纯手动最小可运行实例、驱动器与适配器的选择与匹配、.env 与 .env.{环境} 加载优先级、pyproject.toml 插件注册、六种插件加载方式、容器化部署，以及事件循环、Pydantic 版本、插件重复加载等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 聊天机器人
---

# 三剪客 · 多平台聊天机器人框架

同一个机器人逻辑，想同时跑在 QQ 群、Telegram 频道和飞书上——如果每接一个平台就重写一遍业务代码，维护成本会失控。NoneBot2 的解法是**把"平台"和"业务"彻底拆开**：业务写成插件，平台差异由「适配器」吸收，收发数据的方式由「驱动器」决定。换平台时，插件一行不改。

说清楚它不做什么同样重要：它**不是任何平台或协议的具体实现**，只负责和已有的协议适配器通信并处理收到的事件。所以"NoneBot 支持不支持某平台某功能"这个问题本身就不该问它，而应该问对应适配器或平台自身的开放接口。

**上游项目**：`NoneBot2`　**仓库**：https://github.com/nonebot/nonebot2

## 什么时候用 / 不用

**用它**：

- "一套业务逻辑要同时跑在多个聊天平台上。"——适配器模型覆盖 OneBot、Telegram、飞书、GitHub、QQ 官方接口、Discord、钉钉、Matrix 等一大批协议。
- "团队会 Python，想要异步、类型友好的机器人框架。"——100% 类型注解覆盖，配合编辑器的类型推导能在写代码阶段挡掉大量低级错误。
- "想要现成的插件生态，不想什么都自己写。"——官方插件商店里有大量现成插件，一条命令安装并自动注册。
- "需要接入各种连接方式（反向 WS、HTTP 上报、正向 WS）。"——正好是适配器与驱动器的职责分工。
- "想拿它做定时任务、告警推送、群里接 AI 模型这类服务型机器人。"——异步框架天然适合这类场景。

**不要用它**：

- **只想做一个单文件小脚本、跑一条命令发个消息**——直接用平台的 HTTP 接口或轻量 SDK 更快，不必引入框架。
- **不会 Python / 不想写代码**——它是开发者框架，配置不能代替编程。
- **需要现成的可视化后台与图形化管理**——它没有 Web 管理面板，运行状态看日志。
- **要问"某平台有没有某功能"**——框架本身不实现平台能力，得看适配器与平台接口。
- **期望装上就自带协议端**——它需要另外的协议端（如 OneBot 实现）或平台官方接口配合才能连上聊天软件。

## 安装

### 方式一：脚手架（官方推荐）

官方强烈建议用虚拟环境；如果你之前装过第一代框架，务必先卸载，否则会冲突：

```bash
pip uninstall nonebot

# 1) 安装 pipx（用它隔离 CLI 环境，比直接 pip install 更干净）
python -m pip install --user pipx
python -m pipx ensurepath

# 2) 安装脚手架
pipx install nb-cli

# 3) 创建项目（按提示一步步选）
nb create

# 4) 在项目目录里运行
nb run
```

`nb create` 会依次问你项目模板、项目名称、适配器、驱动器、本地存储策略、是否立即安装依赖、是否创建虚拟环境、要哪些内置插件。几个要点：

- 模板选 `bootstrap`（面向使用者，能安装商店插件）还是 `simple`（要自己写插件）；
- 多选项用**空格**选中或取消，**回车**确认；
- 适配器可以先用 `Console`（终端交互），它不需要任何协议端就能验证机器人是否正常；验证方式是运行后输入 `/echo hello world`，能收到 `hello world` 就通了。

也可以用 uv 安装脚手架：

```bash
uv tool install nb-cli@latest
uvx --from nb-cli@latest nb
```

### 方式二：手动创建最小项目（官方不推荐，但值得知道）

官方原话是不推荐直接手搓项目，应优先用脚手架。但理解最小实例有助于排错，一个项目至少需要：入口文件、配置文件、插件。

```bash
python -m venv .venv --prompt nonebot2
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 安装框架 + 驱动器（方括号里是驱动器名，见官方驱动器商店）
pip install "nonebot2[fastapi]"

# 安装适配器（以控制台适配器为例，包名见官方适配器商店）
pip install nonebot-adapter-console
```

在项目目录里建 `.env`：

```dotenv
HOST=0.0.0.0
PORT=8080
COMMAND_START=["/"]
COMMAND_SEP=["."]
```

再建 `bot.py`：

```python
import nonebot
from nonebot.adapters.console import Adapter as ConsoleAdapter  # 避免重复命名

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(ConsoleAdapter)

nonebot.load_builtin_plugins("echo")

if __name__ == "__main__":
    nonebot.run()
```

运行：

```bash
python bot.py
```

注意：用脚手架创建的项目**不会生成入口文件**，那部分功能被 `nb run` 取代了。

### 方式三：安装适配器与插件

```bash
# 适配器（以 OneBot 为例）
nb adapter install nonebot-adapter-onebot

# 插件
nb plugin install nonebot_plugin_docs

# 只装了 pip 环境时也可以直接用 pip 安装
pip install nonebot-adapter-onebot
```

注册 OneBot 适配器时需要在入口文件里显式注册：

```python
import nonebot
from nonebot.adapters.onebot.v11 import Adapter

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(Adapter)
```

## 常用操作

**1. 运行机器人与热重载**

```bash
nb run                  # 在项目目录下运行，自动检测 bot.py
python bot.py           # 不用脚手架时的运行方式
nb run --reload         # 文件变化时自动重新加载（Windows 上推荐用这个而不是配置项）
```

**2. 项目的依赖与插件注册放在 `pyproject.toml`**

```toml
[tool.nonebot]
plugin_dirs = ["awesome_bot/plugins"]

[tool.nonebot.plugins]
"@local" = ["path.to.your.plugin"]
"nonebot-plugin-someplugin" = ["nonebot_plugin_someplugin"]
```

`plugin_dirs` 声明本地插件目录，`[tool.nonebot.plugins]` 里登记插件模块；新版脚手架会读取这份配置自行生成启动脚本并运行。

**3. 用 `.env` 与 `.env.{ENVIRONMENT}` 分层配置**

```dotenv
ENVIRONMENT=dev
COMMON_CONFIG=任何环境都会加载的值
```

框架启动时会读取 `ENVIRONMENT`（默认 `prod`），然后加载 `.env.{ENVIRONMENT}`。用脚手架创建的 `simple` 项目通常自带 `.env.dev` 和 `.env.prod` 两套预设。也可以在初始化时直接指定文件：

```python
nonebot.init(_env_file=".env.dev")
```

这条会忽略 `.env` 与环境变量里的 `ENVIRONMENT`。

**4. 常用配置项**

```dotenv
DRIVER=~fastapi+~httpx+~websockets
HOST=127.0.0.1
PORT=8080
LOG_LEVEL=DEBUG
SUPERUSERS=["123123123"]
NICKNAME=["bot"]
COMMAND_START=["/", ""]
COMMAND_SEP=[".", " "]
SESSION_EXPIRE_TIMEOUT=00:02:00
```

配置优先级由高到低是：**直接传入 > 系统环境变量 > dotenv 文件**。环境变量大小写不敏感，同名会覆盖 `.env` 里的值。复杂类型按 JSON 解析，嵌套字典用 `__` 分隔，例如 `WEATHER__API_KEY=123456`。

**5. 在插件里读取配置（推荐方式）**

```python
from pydantic import BaseModel
from nonebot import get_plugin_config


class ScopedConfig(BaseModel):
    api_key: str
    command_priority: int = 10


class Config(BaseModel):
    weather: ScopedConfig


plugin_config = get_plugin_config(Config).weather
```

用子模型（scope）时，配置文件里要写成 `WEATHER__API_KEY=xxx` 这种嵌套形式。

**6. 六种插件加载方式**

```python
import nonebot

nonebot.load_plugin("thirdparty_plugin")                  # 点分模块名
nonebot.load_plugins("awesome_bot/plugins")               # 目录，可传多个
nonebot.load_all_plugins(plugins, plugin_dirs)            # 列表批量
nonebot.load_from_json("plugin_config.json", encoding="utf-8")
nonebot.load_from_toml("plugin_config.toml", encoding="utf-8")
nonebot.load_builtin_plugin("echo")
nonebot.load_builtin_plugins("echo", "single_session")
```

所有加载都必须在 `nonebot.init()` 之后、`nonebot.run()` 之前。用脚手架时它会自动处理加载。

**7. 创建自定义插件**

```bash
nb plugin create
# [?] 插件名称: weather
# [?] 使用嵌套插件? (y/N) N
# [?] 请输入插件存储位置: awesome_bot/plugins
```

**8. 生产部署**

官方部署页覆盖的是依赖管理与容器化两条路：

```bash
# 依赖管理（三选一）
poetry init && poetry add nonebot2[fastapi]
pdm init && pdm add nonebot2[fastapi]
pip freeze > requirements.txt

# 容器化：装脚手架 Docker 插件后一键部署
nb self install nb-cli-plugin-docker
nb docker up
nb docker logs
nb docker down

# 或者自己生成并构建
nb docker generate
nb docker build
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 按文档写的 Python 3.9 建环境，结果装不上或装成旧版 | 官方文档说"支持 3.9 以上"，但包元数据是 `>=3.10, <4.0`，README 徽章写 3.10+，脚手架也要求 3.10+，官方两处口径不一致 | 一律按 **3.10 及以上**准备环境，文档里的 3.9 不要照抄 |
| 换了连接方式就连不上，提示无法使用 | 驱动器类型必须与适配器的连接方式匹配：反向 WebSocket 需要 `ReverseDriver`，HTTP 上报需要 `HTTPClient` + `ASGI`，正向 WebSocket 需要 `WebSocketClient` | 先确认连接方式，再按适配器文档选驱动器，然后改 `DRIVER` 配置 |
| 想同时用 FastAPI 和 Quart | 服务端型驱动器**只能选一个**，只有客户端型驱动器能作为混入类叠加 | 用 `<module>[:<Driver>][+<module>[:<Mixin>]]*` 语法组合：一个主驱动器 + 若干客户端混入 |
| 装完驱动器却还是用旧驱动 | 脚手架安装驱动器后**不会**自动修改项目使用的驱动器 | 手动改 `DRIVER` 配置项 |
| 插件加载报错，或者行为很怪 | 官方警告两点：不要在插件被加载前 `import` 插件模块；插件模块名不能相同且每个插件只能加载一次，重复加载会异常 | 加载路径要相对入口文件可导入；排查是否有重名模块或重复 `load_plugin` |
| `.env` 里改了值却不生效 | 加载优先级是"直接传入 > 环境变量 > dotenv"，环境变量同名会覆盖；而且非内置、非插件声明的环境变量框架根本不会读 | 检查系统里是否有同名环境变量；自定义配置项必须在 dotenv 文件里先声明 |
| 配置文件读的不是预期那份 | `ENVIRONMENT` 默认是 `prod`，写错环境名就会去读另一份文件 | 显式设置 `ENVIRONMENT`；临时调试用 `nonebot.init(_env_file=".env.dev")` 直接指定 |
| 装了商店插件后报 Pydantic 相关的 ValidationError | 部分第三方插件与 Pydantic v2 不兼容 | 官方给出的处置是按需降级：`pip install --force-reinstall 'pydantic~=1.10'`；框架自 2.2.0 起同时兼容 v1 与 v2 |
| 在 Windows 上开了 `fastapi_reload` 之后原本正常的代码开始报错 | 该配置会强制把事件循环从 `ProactorEventLoop` 换成 `SelectorEventLoop`，后者在 Windows 上不支持创建子进程、最多 512 个套接字，依赖 asyncio 的库可能抛 `NotImplementedError` | 官方明确不推荐开这个配置项，改用 `nb run --reload`；Quart 的同类配置项有一样的警告 |
| 反向 WS 连不上 | 上报地址是固定的 `ws://<HOST>:<PORT>/onebot/v11/`（也可以是 `/ws` 或 `/ws/`），路径、端口、主机任一不匹配就连不上；只监听 `127.0.0.1` 时外部访问不到 | 核对协议端侧的地址与框架的 `HOST` / `PORT`；需要外部连接时把 `HOST` 设为 `0.0.0.0` |
| 安装完脚手架却提示找不到 `nb` 命令 | pipx 安装的 CLI 不在当前环境的可执行路径里 | 按 pipx 文档检查环境变量；命令提示需要重开终端时一定要重开 |
| 装完框架后 API 全乱、报奇怪的导入错误 | 机器上还留着第一代框架，两者会冲突 | 官方要求先 `pip uninstall nonebot`，并始终在虚拟环境里开发 |
| 跟着教程手搓项目，越搓越乱 | 官方明确表示不推荐手动创建项目 | 需要自定义时也建议先 `nb create` 生成骨架，再在其上改 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 与协议端或平台开放接口通信（HTTP / WebSocket）、插件从商店或包索引下载、插件自身调用外部 API |
| 读取文件 | 是 | 读取 `.env` / `.env.{环境}` / `pyproject.toml` 配置、插件模块与资源文件、本地存储数据 |
| 写入文件 | 是 | 写入日志、本地存储策略产生的数据文件；容器化部署时写入构建产物 |
| 凭证 | 是 | 各平台的 Token / AppID / AppSecret 等由适配器或插件使用，通常写在 dotenv 文件或环境变量里。建议用环境变量注入并限制配置文件的读取权限 |
| 子进程 / 后台常驻 | 是 | 机器人是长期常驻进程，需要进程守护或容器编排；`nb docker` 相关命令会调用 Docker 子进程 |

## 触发场景

- "帮我用 NoneBot2 起一个机器人项目。"
- "机器人在群里没反应，怎么排查是适配器还是驱动器的问题？"
- "我想让同一套插件同时支持 QQ 和 Telegram，怎么组织？"
- ".env 里改了配置不生效。"
- "装了个插件以后报 Pydantic 错误。"
- "NoneBot2 怎么放到服务器上跑？"

## 能力边界

**覆盖**：

- 框架能力：异步事件驱动、类型注解全覆盖、插件加载与管理、依赖注入式的上下文获取、会话控制与状态、权限与响应规则、生命周期钩子、自定义服务端路由
- 平台接入：通过适配器支持 OneBot（v11 / v12）、各平台官方机器人接口、Telegram、飞书、GitHub、Discord、DoDo、Kritor、Mirai、Satori、Matrix 等一大批协议，以及社区贡献的更多适配器
- 数据传输：通过驱动器支持 FastAPI、Quart 等服务端框架与 aiohttp、httpx、websockets 等客户端方式，可组合使用
- 工程化：脚手架建项目 / 建插件 / 装适配器与插件、依赖管理兼容 Poetry / PDM / pip、容器化部署方案
- 插件生态：官方与社区插件商店，可按名安装、升级、卸载

**不覆盖**：

- 具体平台或协议的功能实现——框架只管和适配器通信，平台能力要问适配器与平台文档
- 任何图形化管理后台（没有 Web 控制台，状态靠日志与自身扩展）
- 协议端本身——要连聊天软件还需要另配协议端（如 OneBot 实现）或平台官方接口
- 消息内容的语义理解、AI 能力——那是插件的事，框架不提供
- 面向非开发者的低代码编排界面

## 依赖条件

- Python 3.10 ～ 3.13 一线（包元数据为 `>=3.10, <4.0`；官方文档另处写 3.9，以包元数据为准）
- 至少安装一个驱动器与一个适配器；采用 `pip install "nonebot2[fastapi]"` 这类可选依赖写法安装驱动器
- 强烈建议使用虚拟环境；曾装过第一代框架的必须先卸载
- 脚手架建议用 pipx 或 uv tool 隔离安装，要求 Python 3.10+
- 没有外部账号要求；各平台适配器 / 插件各自需要的凭据由它们负责

## 已知限制

1. 框架不实现任何平台能力，"某平台能不能做某事"取决于适配器与平台自身接口，框架层面无法回答。
2. 官方文档与包元数据在 Python 版本要求上不一致（文档写 3.9、元数据是 3.10+），以包元数据为准。
3. 服务端型驱动器只能选一个，混入类驱动器只能是客户端类型，组合方式有约束。
4. 官方部署文档未覆盖 supervisor / systemd 这类传统进程守护方案，需要自行设计。
5. 部分第三方插件与 Pydantic v2 不兼容，可能需要在 v1 / v2 之间做取舍。
6. 版本迭代较快，配置项与脚手架行为可能随版本变化；具体以本机 `nb --help` 与安装版本的文档为准。

## 自检清单

执行前：

- [ ] 确认 Python 版本 ≥ 3.10，且已在虚拟环境里
- [ ] 确认没有残留的第一代框架（有就先卸载）
- [ ] 明确通信方式，据此选定驱动器与适配器，并确认二者类型匹配
- [ ] `DRIVER` 配置项已与实际安装的驱动器一致（脚手架不会自动改它）
- [ ] 自定义配置项已在 dotenv 文件里声明，避免被环境变量静默覆盖
- [ ] Windows 上不要开 `fastapi_reload` / `quart_reload`，用 `nb run --reload`

执行后：

- [ ] 用 Console 适配器跑通 `/echo hello world`，确认框架本身没问题
- [ ] 目标平台上能收到事件并能回复，确认协议端地址与路径匹配
- [ ] 检查日志没有插件加载失败或 Pydantic 兼容性警告
- [ ] 重启进程后插件仍能正常加载（说明注册方式持久化正确）
- [ ] 生产环境确认进程守护或容器重启策略已生效

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/nonebot/nonebot2 | 上游仓库（安装与完整文档以它为准） |
| https://nonebot.dev/docs/quick-start | 官方快速上手：脚手架完整流程 |
| https://nonebot.dev/docs/appendices/config | 官方配置说明：加载优先级、内置配置项 |
| https://nonebot.dev/docs/advanced/driver | 官方驱动器说明：类型划分与配置语法 |
| https://nonebot.dev/docs/tutorial/create-plugin | 官方插件创建与六种加载方式 |
| https://nonebot.dev/docs/best-practice/deployment | 官方部署说明：依赖管理与容器化 |
| https://cli.nonebot.dev/ | 脚手架官方文档：安装、建项目、运行、项目管理 |

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
