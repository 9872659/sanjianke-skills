# 自定义与排错

适用：换模型、接自己的技能包、导出成果物、出问题要快速定位。

## 1. 服务商接入：两套配法，二选一

### 写法一：环境变量（推荐起步）

每家服务商都是同一套三件套：`<前缀>_API_KEY`、`<前缀>_BASE_URL`、`<前缀>_MODELS`，再加上全局默认 `DEFAULT_MODEL`。

| 服务商 | 环境变量前缀 | 默认模型写法示例 |
|---|---|---|
| OpenAI | `OPENAI_` | `openai:gpt-5.5` |
| Azure OpenAI | `AZURE_OPENAI_` | `azure:<你的部署名>` |
| Anthropic | `ANTHROPIC_` | `anthropic:claude-sonnet-5` |
| Amazon Bedrock | `BEDROCK_`（配 `BEDROCK_REGION`、`BEDROCK_MODELS`） | `bedrock:us.anthropic.claude-sonnet-5` |
| Google Gemini | `GOOGLE_` | `google:gemini-3-flash-preview` |
| DeepSeek | `DEEPSEEK_` | `deepseek:deepseek-v4-pro` |
| 通义千问 | `QWEN_` | `qwen:qwen3.5-flash` |
| Kimi | `KIMI_` | `kimi:<模型名>` |
| MiniMax | `MINIMAX_` | `minimax:MiniMax-M2.7-highspeed` |
| 智谱 GLM | `GLM_` | `glm:glm-5.1` |
| Grok | `GROK_` | `grok:<模型名>` |
| 豆包 | `DOUBAO_` | `doubao:<模型名>` |
| 腾讯混元 / TokenHub | `TENCENT_` | `tencent:<模型名>` |
| 小米 MiMo | `XIAOMI_` 或 `MIMO_` | `xiaomi:mimo-v2.5-pro` |
| OpenRouter | `OPENROUTER_` | `openrouter:<模型名>` |
| 硅基流动 | `SILICONFLOW_` | `siliconflow:<模型名>` |
| Atlas Cloud | `ATLASCLOUD_` | `atlascloud:<模型名>` |
| Ollama（本地） | 走 OpenAI 兼容，指本机地址 | `openai:<本地模型名>` |
| Lemonade（本地） | `LEMONADE_` 系列 | `openai:<本地模型名>` |

以上共 19 家；任何兼容 OpenAI 接口的服务，把 `OPENAI_BASE_URL` 指过去也能用。

国内站与国际站要分清。以 GLM 为例：

```env
# 国内站
GLM_API_KEY=...
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
# 国际站
GLM_API_KEY=...
GLM_BASE_URL=https://api.z.ai/api/paas/v4
```

换服务商时**三处都要改**：Key、Base URL、`DEFAULT_MODEL` 前缀。只改 Key 不换前缀是最常见的 401 / 404 来源。

### 写法二：外部配置文件

想在不重建镜像的情况下换服务商，用 `server-providers.yml`：

```yaml
providers:
  openai:
    apiKey: sk-...
  azure:
    apiKey: ...
    baseUrl: https://YOUR-RESOURCE.openai.azure.com/openai
    models:
      - YOUR-DEPLOYMENT-NAME
  bedrock:
    models:
      - us.anthropic.claude-sonnet-5
```

容器路线要把这个文件挂进去（compose 里那一行默认是注释掉的）：

```yaml
volumes:
  - ./server-providers.yml:/app/server-providers.yml:ro
```

规则：环境变量与 YAML 同时存在时以服务端配置为准；被显式标 `disabled: true` 的服务商不参与能力位判断，也不参与路由。

### 媒体能力是分开配的

文本、语音合成（TTS）、语音识别（ASR）、出图、出视频、检索，各自有独立前缀（`TTS_`、`ASR_`、`IMAGE_`、`VIDEO_`、`WEB_SEARCH_`）。**文本模型能跑不代表语音能跑。**配完必须回 `/api/health` 看能力位。

## 2. 模型路由与分档

`DEFAULT_MODEL` 只是兜底，实际解析顺序是：**阶段级路由 > 请求头 `x-model`（客户端）> `DEFAULT_MODEL`**。所以出现「我明明改了默认模型却没生效」时，先查有没有配阶段路由或客户端在传 `x-model`。

服务端在启动时会校验路由与默认模型的合法性。**裸模型名（不带服务商前缀）在启动阶段就会被拒**，不会静默降级到某家厂商。

### 分档路由思路

课堂生成链路里，不同环节对模型的要求差别很大：

| 环节 | 建议档位 | 理由 |
|---|---|---|
| 大纲生成 | 强推理档 | 结构错了全盘重来，值得花 |
| 场景正文 | 中档 | 量大，质量够用就行 |
| 角色人设生成 | 中低档 | 短文本，任务简单 |
| 测验判分 | 中低档 | 需要稳定，不需要深度推理 |
| 交互 HTML 生成 | 强代码能力档 | 一次生成的可运行 HTML 对模型要求最高 |

### 后台智能体会话（实验特性）

要开启服务端托管的智能体会话，需要同时满足三个条件，缺一不可：

1. `OPENMAIC_AGENT_RUNTIME_ENABLED=true`（默认关，关着时 `/api/agent/sessions*` 直接 404）
2. 有可用的 `DATABASE_URL`（会话是服务端持久化的，没库就起不来）
3. `MODEL_ROUTES` 里为 `maic-agent-driver` 阶段显式指定路由，**没有兜底**：

```env
MODEL_ROUTES='{"maic-agent-driver":{"model":"openai:gpt-5.5","api":"openai-completions"}}'
```

路由对象里的 `api` 只能是 `openai-completions` 或 `openai-responses`，其他值会被拒；`model` 必须带服务商前缀。可选 `contextWindow` 用于压低于服务商目录值的有效上下文窗口。`thinking` 里**不要**设置 effort —— 该传输层上工具调用与 reasoning effort 不能共存。

其他可用旋钮（都有默认值，不开后台会话时无关）：

| 变量 | 默认 | 含义 |
|---|---|---|
| `OPENMAIC_AGENT_RUNTIME_SCAN_INTERVAL_MS` | 1000 | 扫描间隔 |
| `OPENMAIC_AGENT_RUNTIME_HEARTBEAT_MS` | 2000 | 心跳 |
| `OPENMAIC_AGENT_RUNTIME_LEASE_TTL_MS` | 10000 | 租约时长 |
| `OPENMAIC_AGENT_RUNTIME_MAX_CONCURRENT` | 2 | 并发会话数 |
| `OPENMAIC_AGENT_RUNTIME_MAX_ATTEMPTS` | 5 | 最大重试次数 |
| `OPENMAIC_AGENT_TOOL_TIMEOUT_MS` | 600000 | 单次工具调用上限（10 分钟） |

会话提示词与追问消息在服务端有**固定 10 万字符**上限，这是常量，改配置没用。

## 3. 内置技能包

仓库 `skills/agent-runtime/` 下是一批可复用的教学技能，每个是一个带 `SKILL.md` 的目录，目前有 **23 个**（上游 README 的口径是「20 个内置技能」，实际目录数更多）：

| 类别 | 技能目录 |
|---|---|
| 课程规划 | `curriculum-planner`、`spiral-curriculum`、`understanding-by-design`、`k12-core-literacy-planning`、`vocational` |
| 授课风格 | `lecture-style`、`workshop-style`、`feynman-learning`、`social-emotional-learning`、`learning-to-learn` |
| 生成与制作 | `stage-design`、`stage-dsl`、`slide-craft`、`slide-dsl`、`page-clone`、`pro-editing`、`pptx-import` |
| 风格迁移 | `style-clone`、`teacher-style-clone` |
| 质量与深度 | `deep-research`、`deep-interactive`、`fact-check` |
| 个性化 | `build-personal-skill` |

其中带 `outline-constraints.json` 的技能会给大纲生成加约束（例如 `deep-interactive`、`deep-research`、`pptx-import`、`vocational`），这类技能一挂上就会改变大纲的结构，不只是改措辞。

### 加一个自己的技能

1. 在 `skills/agent-runtime/` 下新建目录，目录名用 kebab-case。
2. 放一个 `SKILL.md`，写清：这个技能解决什么、什么时候用、产出的结构长什么样、有哪些硬约束。
3. 如果它需要约束大纲结构，同时放一个 `outline-constraints.json`。
4. 重启服务，再看设置里是否出现该技能。
5. 只对某一节课生效的自定义，走「会话级技能」而不是改仓库——会话级改动不会被上游更新覆盖。

写技能的三个要点：**触发条件写具体**（「当用户要讲数学公式推导时」比「用于数学」有用得多）、**输出结构写死**（否则每节课样式都不同）、**别写成长篇教程**（技能是给模型看的约束，不是给人看的文档）。

## 4. 导出

| 格式 | 用途 | 注意 |
|---|---|---|
| `.pptx` | 交给同事二次编辑 | 图片、图表、LaTeX 公式会尽量保留；公式错位时先查导出链路而非源幻灯片 |
| 交互式 `.html` | 单文件网页，带交互实验 | 自包含，可直接挂静态站 |
| `.maic.zip` | 整节课打包（结构 + 媒体） | 备份与迁移用这个 |

**离线/内网播放**：导出时会把交互场景引用的外部资源（数学排版库、3D 库、样式库、字体、图片）以 `data:` URI 内联进 HTML，之后在内网也能播。抓不到的资源（例如开了 CORS 限制的图床）会被记录并**保留原始 URL**，播放时仍要公网。该功能上线之前导出的课堂仍引用外部 CDN，需要重新导出才能离线播。

MP4 导出是另一条路，需要单独起渲染容器，见 `references/01-deploy-and-start.md` 第 7 节。

## 5. 界面与外观

- 界面本地化覆盖 12 个区域：简体中文、繁体中文、英文、日文、韩文、俄文、阿拉伯文、巴西葡萄牙文、墨西哥西班牙文、法文、越南文、德文。
- 主题、字体、形状、图表、快捷键等常量集中在 `configs/` 目录，改这些比改组件便宜。
- 深色模式已内置。
- 静态资源（头像、logo）在 `public/avatars/` 与 `public/`；换头像时注意默认头像表里每一个路径都必须真实存在，否则生成的角色会显示破图。

## 6. 排错速查

| 现象 | 最可能的原因 | 动作 |
|---|---|---|
| `pnpm install` 直接失败 | Node 版本 < 22.19 | `node -v` 升级到 22.19+ |
| 启动即报模型配置错误 | `DEFAULT_MODEL` 没带服务商前缀，或前缀与已配 Key 不匹配 | 改成 `服务商:模型名` |
| `/api/health` 返回 ok 但某能力位 false | 对应服务商未配置，或被 `disabled: true` 关掉 | 补 Key，检查是否被显式禁用 |
| 401 / 403 | Key 错、Key 与 Base URL 站点不匹配（国内站配了国际站地址） | 三件套一起核对 |
| 404 | Base URL 路径不对（少/多了 `/v1`），或模型名不属于该服务商 | 对照服务商文档路径 |
| 改了 `NEXT_PUBLIC_*` 没生效 | 编译期变量 | 重新 `pnpm build` 并重启 |
| 生成任务一直不结束 | 模型慢 / 上下文过长 / 上游限流 | 轮询 `pollUrl` 看 `step` 与 `message` 卡在哪一步；先降模型档位试 |
| 提交任务返回 400 | 缺 `requirement` | 请求体必须带非空 `requirement` |
| 前端提示持久化不可用但课程列表还在 | 构建期 `NEXT_PUBLIC_PERSISTENCE_TOKEN` 与服务端 token 不一致，或 `DATABASE_URL` 不可用 | 用同一个 token 重新构建 |
| MP4 导出不可用 | `render-service` 容器没起（未开 profile） | `docker compose --profile video-export up --build` |
| 渲染容器起来了但 Chromium 起不来 | 缺 `CAP_NET_ADMIN` 或共享内存太小 | 保留 `cap_add: NET_ADMIN` 与 `shm_size: 2gb` |
| 学生角色不翻页 | `role` 不是 `teacher`，没有幻灯片动作权限 | 改 `role`，不要手填 `allowedActions` |
| 某个智能体全程不说话 | `priority` 太低，或话题相关性不足 | 提高 `priority`，把 `persona` 写得更贴近当前话题 |
| 白板出现重复/覆盖 | 多个角色同时绘制的冲突未收敛 | 降低同屏发言人数，或提高主讲 `priority` |
| 后台智能体会话全部 404 | `OPENMAIC_AGENT_RUNTIME_ENABLED` 没开 | 打开开关并确认 `DATABASE_URL` 可用 |
| 后台会话启动即失败 | `MODEL_ROUTES` 没给 `maic-agent-driver` 配路由 | 按第 2 节示例补上，注意 `api` 取值受限 |
| 导出的课堂内网打不开 | 资源未内联，保留了原始 URL | 重新导出（旧包不含内联逻辑） |
| 生成的课堂内容跑偏 | 大纲阶段就偏了 | 先只调 `/api/generate/scene-outlines-stream` 看结构 |

### 定位顺序（照这个顺序走，不要跳）

1. `GET /api/health` —— 服务活着吗？能力位对吗？
2. 看服务端日志里第一条报错，而不是最后一条。
3. 单点打底层端点（`scene-outlines-stream` → `scene-content` → `scene-actions`），定位到具体环节。
4. 换一个已知可用的模型/服务商做对照实验，区分「配置问题」和「模型问题」。
5. 只有前四步都排除后，再怀疑代码或版本。
