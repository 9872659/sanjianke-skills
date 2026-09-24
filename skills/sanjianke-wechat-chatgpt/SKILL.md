---
name: sanjianke-wechat-chatgpt
slug: sanjianke-wechat-chatgpt
displayName: 三剪客 · 微信接入 ChatGPT 自动回复
description: "把个人微信接到大模型上做自动回复：基于 Node.js + Wechaty 扫码登录，支持私聊/群聊触发规则、关键词与双向屏蔽词、Docker 与 docker compose 部署。含环境变量清单、真实命令与扫码登录避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "让微信在收到消息时自动调用大模型作答：一条命令扫码登录、一份 .env 控制触发规则，覆盖 Docker、docker compose、源码、PaaS 四种跑法与常见坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 社媒
  - 营销
---

# 三剪客 · 微信接入 ChatGPT 自动回复

想让微信变成一个会自动回消息的助手：朋友问你问题，它替你答；群里被提到，它接话。这个项目做的就是这件事——用 Wechaty 拿到微信消息流，再转发给大模型接口，把回答发回原会话。它不只是一个"接通了就算完"的玩具，触发规则、屏蔽词、prompt、会话记忆都是可配的，所以它更像一台**消息路由与自动应答的机器**，而不是一个聊天窗口。

**上游项目**：`wechat-chatgpt`　**仓库**：https://github.com/fuergaosi233/wechat-chatgpt

> ⚠️ 上游仓库已归档（Archived），代码冻结、不再接收更新。下面的命令对冻结的这份代码成立；由于微信侧协议与登录策略一直在变，**实际能否登录成功要以你当前环境实测为准**。

## 什么时候用 / 不用

**用它**：

- 要在一台常驻机器上跑一个"微信自动答话"的服务，扫码登录、长期在线、自己托管。
- 需要按规则收紧触发面：只在私聊里回、只带某个关键词才回、或者干脆关掉群聊，避免机器人到处抢话。
- 想用 Docker / docker compose 一次性部署，不想在本机装 Node 环境。
- 要一个带会话上下文的助手（连续追问能记住前文），而不是每条消息独立作答。
- 需要把大模型接到**自己可控的 API 端点**上（自建代理、兼容接口），只改 `API` 环境变量。

**不要用它**：

- **不接受账号风险**。基于网页版协议的第三方登录是微信明确不鼓励的用法，存在被限流、警告乃至封号的可能；账号越重要越不该碰。要合规触达客户请走企业微信、公众号或官方客服接口。
- **要做群发营销 / 批量加好友 / 拉群导流**。这类行为是封号高发区，本项目也不提供这些能力，用法上就不该往这个方向走。
- **需要长期维护、跟进上游更新**。仓库已归档，微信协议变了不会有人修；把它当一次性实验或内部小工具可以，当长期生产基座不行。
- **只想要一个"一键托管"的成品**。扫码登录需要人工在终端看二维码，掉线后还要重扫，不存在完全无人值守。
- **要的是企业级 CRM / 线索打分 / 多渠道路由**。那是营销自动化平台的活，不是一个微信机器人项目能承接的。

## 安装

四种跑法，按"手上有多少台机器"来选。**所有方式都需要一个可用的模型 API Key。**

### 方式一：Docker（最省事）

```bash
# 拉镜像
docker pull holegots/wechat-chatgpt

# 起容器（把 OPENAI_API_KEY 换成你自己的）
docker run -d --name wechat-chatgpt \
    -e OPENAI_API_KEY=<YOUR OPENAI API KEY> \
    -e MODEL="gpt-3.5-turbo" \
    -e CHAT_PRIVATE_TRIGGER_KEYWORD="" \
    -v $(pwd)/data:/app/data/wechat-assistant.memory-card.json \
    holegots/wechat-chatgpt:latest

# 看日志里的二维码，用微信扫
docker logs -f wechat-chatgpt
```

### 方式二：docker compose（配置想存文件时用）

```bash
# 按模板复制配置文件
cp .env.example .env
# 编辑配置
vim .env
# 启动
docker-compose up -d
# 看二维码
docker logs -f wechat-chatgpt
```

### 方式三：源码跑（要改代码时用）

官方要求 **Node.js 18.0.0 及以上**。

```bash
# 克隆并进入目录
git clone https://github.com/fuergaosi233/wechat-chatgpt.git && cd wechat-chatgpt
# 装依赖
npm install
# 复制并编辑配置
cp .env.example .env
vim .env
# 启动
npm run dev
```

### 方式四：PaaS 部署（Fly.io 为例）

```bash
# 装 CLI（macOS 用 brew，Windows 用 scoop，Linux 用官方脚本）
brew install flyctl                     # macOS
scoop install flyctl                    # Windows
curl https://fly.io/install.sh | sh     # Linux

git clone https://github.com/fuergaosi233/wechat-chatgpt.git && cd wechat-chatgpt
flyctl launch                           # 按提示填 App 名和区域，先不要部署
flyctl secrets set OPENAI_API_KEY="<YOUR OPENAI API KEY>" MODEL="<CHATGPT-MODEL>"
flyctl deploy
```

> 官方提示：Fly.io 上给这个应用**至少 512MB 内存**，否则跑不起来。PaaS 平台的免费额度、计费方式随时会变，以平台当页说明为准。

## 常用操作

**1. 查到二维码并登录**

```bash
docker logs -f wechat-chatgpt      # Docker 部署
npm run dev                        # 源码部署，二维码直接打在终端
```

扫码后账号即上线；微信侧若强制下线或长时间掉线，需要重新扫码。

**2. 最小可用配置（`.env`）**

```dotenv
API=                            # 大模型接口地址，留空用默认
OPENAI_API_KEY=<YOUR OPENAI API KEY>
MODEL=gpt-3.5-turbo
TEMPERATURE=0.8
CHAT_PRIVATE_TRIGGER_KEYWORD=   # 私聊触发词，留空表示私聊全回
CHAT_TRIGGER_RULE=              # 私聊触发规则
DISABLE_GROUP_MESSAGE=true      # 关掉群聊自动回复
BLOCK_WORDS=                    # 触发屏蔽词，多个用英文逗号分隔
CHATGPT_BLOCK_WORDS=            # 命中就丢弃的回答屏蔽词，多个用英文逗号分隔
```

环境变量含义（上游 README 给出的完整清单）：

| 变量 | 作用 |
|---|---|
| `API` | 大模型的接口端点 |
| `OPENAI_API_KEY` | 调用凭证 |
| `MODEL` | 使用的模型 ID；上游 README 说明当前只支持 `gpt-3.5-turbo` 与 `gpt-3.5-turbo-0301` |
| `TEMPERATURE` | 采样温度，0~2；越大越发散，越小越确定 |
| `CHAT_TRIGGER_RULE` | 私聊触发规则 |
| `DISABLE_GROUP_MESSAGE` | 禁止在群聊里使用 |
| `CHAT_PRIVATE_TRIGGER_KEYWORD` | 私聊中触发回复的关键词 |
| `BLOCK_WORDS` | 聊天屏蔽词，私聊群聊都生效，英文逗号分隔 |
| `CHATGPT_BLOCK_WORDS` | 模型答话里出现就丢弃的词，私聊群聊都生效，英文逗号分隔 |

**3. 在微信聊天框里用内置指令**

```text
/cmd help              # 显示帮助
/cmd prompt <PROMPT>   # 设置 prompt
/cmd clear             # 清空本次启动以来的所有会话
```

这些指令**直接发在微信聊天框里**，不是发在终端。

**4. 换成自己的模型端点**

把 `API` 指向任何兼容的接口即可，例如自建反向代理后的地址：

```dotenv
API=https://your-own-endpoint.example/v1
OPENAI_API_KEY=<你的 Key>
MODEL=<你的模型 ID>
```

上游另有一个配套的代理部署方案（仓库 `openai-proxy`），流程是克隆项目 → `npm install && npm install -g wrangler && npm run build` → `npm run deploy` 部署到 Cloudflare Workers；需要自定义域名时在 `wrangler.toml` 里加 `routes` 配置。

**5. 保留会话记忆文件**

Docker 那条命令里的 `-v $(pwd)/data:/app/data/wechat-assistant.memory-card.json` 就是挂载记忆文件。**不挂这个卷**，容器重建后会话上下文就没了。

**6. 改完配置重启生效**

```bash
docker restart wechat-chatgpt          # Docker
docker-compose restart                 # compose
# 源码方式 Ctrl+C 后重新 npm run dev
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 扫码后提示无法登录、或二维码刷新不出来 | 网页版微信协议对账号有准入限制，部分账号根本不允许登录网页版 | 先用该账号直接访问网页版微信确认能否登录；不能就换账号，或改用企业微信等官方通道 |
| 登录成功但过一阵子掉线，且要人工重扫 | 网页版会话本身不稳定，掉线后不会自动恢复登录态 | 把"看日志重扫"列为运维动作；不要把它当成能无人值守的服务 |
| 账号被警告或限制登录 | 第三方协议登录属于高风险用法 | 用小号、控制回复频率、只在自己能承担风险的场景用；重要账号不要接 |
| 群里到处回话、刷屏 | 默认没有把群聊关掉，或触发条件写得太宽 | 设 `DISABLE_GROUP_MESSAGE=true`；私聊用 `CHAT_PRIVATE_TRIGGER_KEYWORD` 收窄触发面 |
| `.env` 改了但行为没变 | Docker 方式下环境变量是 `docker run -e` 传进去的，改宿主机的 `.env` 文件没用；容器也没重启 | Docker 方式改 `docker run` 的 `-e` 参数后重建容器；compose 方式改 `.env` 后 `docker-compose up -d` 重建 |
| 报模型调用失败 / 请求超时 | Key 无效、账号没余额、或网络到不了模型服务 | 先在终端单独验证 Key 与网络连通性，再排查机器人；本项目没有"模型不可用时的离线兜底" |
| `MODEL` 换成别的名字就报错 | 上游 README 明确当前只支持 `gpt-3.5-turbo` 与 `gpt-3.5-turbo-0301` | 用这两个之一；想用其它模型就靠 `API` 指向兼容端点，但上游未承诺兼容性 |
| `npm install` 卡住或装不上依赖 | 网络问题、Node 版本低于 18、或依赖树与当前 registry 不匹配 | 确认 `node -v` ≥ 18.0.0；换 registry 或加代理后重装；仍不行就改用 Docker 方式绕开本机环境 |
| 容器跑起来但一直不出二维码 | 应用启动失败或内存不足（PaaS 上尤其常见） | `docker logs -f` 看完整报错；Fly.io 上把内存提到 512MB |
| 想长期接着用，但上游不再更新 | 仓库已归档，微信协议变化不会有人适配 | 把它定位成一次性的内部小工具或实验；要长期方案就换官方开放接口或受维护的同类项目 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 连微信侧服务完成登录与收发消息，并调用大模型接口 |
| 读取文件 | 是 | 读取 `.env` 配置文件与会话记忆文件 |
| 写入文件 | 是 | 写入会话记忆文件（`wechat-assistant.memory-card.json`）与运行日志 |
| 凭证 | 是 | 需要大模型 API Key（`OPENAI_API_KEY`）；微信侧凭证来自扫码登录产生的会话票据。本 Skill 不内嵌任何密钥，Key 一律由使用者自己填进 `.env` 或容器环境变量 |
| 子进程 / 后台常驻 | 是 | 机器人必须常驻在线才能收消息；Docker 与 compose 方式都是后台服务形态 |

## 触发场景

- 「帮我把微信接上大模型，让它自动回消息」
- 「我有一个小号，想挂个自动答话的机器人」
- 「用 Docker 起一个微信 AI 助手，给我 compose 配置」
- 「群里不想让它乱回，怎么只让它认关键词」
- 「怎么让机器人答话时带上前面的上下文」
- 「把这个机器人的 API 换成我自己的接口地址」

## 能力边界

**覆盖**：

- 扫码登录微信，接管消息收取与回复。
- 私聊与群聊两条链路的触发控制：触发规则、触发关键词、群聊开关。
- 双向屏蔽词：命中用户消息不回（`BLOCK_WORDS`），命中模型答话丢弃（`CHATGPT_BLOCK_WORDS`）。
- 会话上下文（conversation 支持），以及 `/cmd help`、`/cmd prompt`、`/cmd clear` 三个会话内指令。
- 可替换的模型端点（`API`）与模型 ID（`MODEL`）、采样温度（`TEMPERATURE`）。
- 四种部署形态：Docker、docker compose、源码 Node.js、PaaS（Fly.io / Railway 这类）。

**不覆盖**：

- 不提供任何官方接入资质；它走的是第三方协议路径，合规与账号风险由使用者自行承担。
- 不做群发营销、批量加好友、自动拉群这类增长动作。
- 不含管理后台、数据看板、线索评分、多渠道编排等营销自动化能力。
- 项目已归档，不跟进微信协议变更，也不接受功能新增。
- 图片、语音的完整处理链路以上游当前代码为准，不要预设可用；README 中代理相关支持标注为开发中。

## 依赖条件

- Node.js **18.0.0 或更高**（源码方式硬性要求；Docker 方式由镜像自带）。
- 一个可扫码登录网页版微信的微信号；不能登录网页版的账号用不了。
- 一个大模型 API Key，以及能访问该服务的网络（云端模型常需代理）。
- Docker / docker compose 方式需要本机有 Docker；PaaS 方式需要对应平台的账号。
- 常驻机器：进程停了就不收消息，微信掉线要人工重扫。

## 已知限制

- **仓库已归档**，代码不再演进；微信侧策略变化可能导致功能整体失效，官方 README 也把第三方协议用法标注为有账号风险。
- 上游 README 说明 `MODEL` 只支持 `gpt-3.5-turbo` 与 `gpt-3.5-turbo-0301` 两个值，模型可选范围很窄。
- README 中标注代理（proxy）相关支持为开发中，不要依赖。
- 扫码登录无法脚本化，掉线恢复需要人工介入，达不到无人值守。
- 具体版本号、发布日期、star 数请以仓库页面实时信息为准，此处不做断言。

## 自检清单

- [ ] 已确认这个微信号**能登录网页版微信**，并已评估账号风险。
- [ ] Node.js 版本 ≥ 18.0.0（源码方式），或已准备好 Docker。
- [ ] `OPENAI_API_KEY` 是有效的、有余额的 Key，且本机网络能访问目标模型服务。
- [ ] `.env` / `-e` 里已按需要设置 `DISABLE_GROUP_MESSAGE`、`CHAT_PRIVATE_TRIGGER_KEYWORD`，避免机器人到处抢话。
- [ ] Docker 方式已挂载记忆文件卷 `-v $(pwd)/data:/app/data/wechat-assistant.memory-card.json`。
- [ ] 已用 `docker logs -f` 看到二维码并完成扫码，确认账号上线。
- [ ] 已实测一次私聊触发与一次群聊不被触发，确认触发规则符合预期。
- [ ] 已把"看日志重扫二维码"写进日常运维动作。
- [ ] 已把 `.env` 排除在版本控制之外，Key 不会随代码一起提交。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/fuergaosi233/wechat-chatgpt | 上游仓库（安装与完整文档以它为准） |

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
