---
name: sanjianke-java-agent-kit
slug: sanjianke-java-agent-kit
displayName: Java接大模型与Agent·OpenAI兼容网关直连75模型包
description: "把大模型与 Agent 能力接进你自己的 Java 工程：一个 Key、一个 base_url 统一调用 75 个在架模型，兼容 OpenAI 协议，换 model 就是换模型。从模块分层、工具声明两条路径、拦截器 order 语义、Agent 运行时到 RAG、MCP 全链路，一次配齐。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "Java 团队把大模型与 Agent 能力接进自己工程的成品指南：模块分层、工具声明的注解式与编程式两条路径、工具组动态挂载与工具泄漏、拦截器责任链 order 语义、Agent 运行时（工具审批 / 挂起恢复 / 快照）、RAG 全链路、MCP 与 Skills 定位、模型路由与熔断半开、OpenTelemetry 可观测。全部走 api.a7w.cn 的 OpenAI 兼容入口，一个 Key 可调 75 个在架模型。含计费口径与常见坑排错表。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/` + `scripts/a7w.py`）。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - Java
  - AI Agent
  - Agent 框架
  - 模型网关
  - OpenAI 兼容
  - 大模型接入
  - 开发编程
---

# Java 工程接入大模型与 Agent 能力

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

给现有的 Java 工程加装「会思考、会用工具」的那一层 —— 不用另起一个平台，不用把业务迁走。

**一个 API Key、一个 base_url，统一调用 75 个在架模型。** 工具声明、Agent 运行时、
RAG、MCP、可观测都有现成件，按需取用，能拆能换。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **按量计费**，1 元 = 100 点；文本按点数/百万 tokens，用多少扣多少，没有月费 |
| 要多久 | 接一个模型到跑通第一条回复，**30 分钟内**；换模型只改一个字符串 |
| 要装什么 | Java 工程原有构建工具即可；包里另附零依赖 Python 客户端，`curl` 也能直接调 |
| 能用几个模型 | **75 个在架模型 / 23 家厂商**。同一个 Key，换 `model` 就换模型，账单还是同一份 |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`），填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：先确认入口是通的

```bash
curl -sS "https://api.a7w.cn/api/v1/models" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

返回里是当前在架的全部模型编码。**模型名一律以这个接口为准，不要猜、不要抄旧文档。**

### 第三步：打第一条对话

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role": "user", "content": "用一句话说明什么是 Agent"}],
    "max_tokens": 256
  }'
```

拿到 `choices[0].message.content` 就算通了。**注意把 `max_tokens` 给足**，
推理模型会把 token 先花在思维链上（见「常见坑」）。

---

## 二、模型侧：把 api.a7w.cn 接进 Java 工程

### 2.1 基址与鉴权

| 项 | 值 |
|---|---|
| OpenAI 兼容基址 | `https://api.a7w.cn/api/v1` |
| 自带 `/v1` 后缀的宿主填 | `https://api.a7w.cn/api` |
| 鉴权头 | `Authorization: Bearer <你的 API Key>` |
| Key 来源 | 环境变量 `A7W_API_KEY` 注入，**不要写进代码或提交进仓库** |
| 对话端点 | `POST /api/v1/chat/completions` |
| 模型清单 | `GET /api/v1/models`（实测 75 个模型 / 23 家厂商） |

**一个 Key 可调 75 个在架大模型，换 `model` 就是换模型** —— 不用换 base_url、
不用换 Key、账单还是同一份。

> 有些客户端（含各类 OpenAI SDK 与中间件）会自己再拼一层 `/v1`。
> 遇到 404 先怀疑层数：那种宿主就把 base_url 填成 `https://api.a7w.cn/api`。

### 2.2 Java 侧接入（OpenAI 兼容客户端）

任何说 OpenAI 协议的 Java 客户端（官方 `openai-java` SDK，或框架自带的
OpenAI 兼容适配模块）都只需要改两处 —— base_url 与 model：

```java
import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.models.chat.completions.ChatCompletion;
import com.openai.models.chat.completions.ChatCompletionCreateParams;

public class FirstCall {
    public static void main(String[] args) {
        String apiKey = System.getenv("A7W_API_KEY");   // 从环境变量注入，别硬编码

        OpenAIClient client = OpenAIOkHttpClient.builder()
                .baseUrl("https://api.a7w.cn/api/v1")   // 只改这一行
                .apiKey(apiKey)
                .build();

        ChatCompletionCreateParams params = ChatCompletionCreateParams.builder()
                .model("DeepSeek-V4-Flash")             // 换模型就是换这个字符串
                .maxCompletionTokens(256L)              // 推理模型别给太小
                .addUserMessage("用一句话说明什么是 Agent")
                .build();

        ChatCompletion resp = client.chat().completions().create(params);
        System.out.println(resp.choices().get(0).message().content().orElse(""));
    }
}
```

要点：

- **接口层收口**：工程里只暴露一个 `ChatModel` 门面，业务代码永远不直接 new 客户端。
  这样以后换线路、加降级、加拦截器都只动一处。
- **同步与流式共用同一套提示词、参数、拦截器与上下文机制**，不是两套 API。
- **Embedding / Rerank 也走同一套地址与同一把 Key**，不用再开第二个账号。

### 2.3 按用途选模型（实测在架编码）

| 用途 | 推荐 `model` 编码 |
|---|---|
| 日常对话 / 高并发轻任务 | `DeepSeek-V4-Flash`、`Qwen3.6-Flash`、`GLM-5`、`MiniMax-M2.5` |
| 复杂推理 / 难题拆解 | `DeepSeek-V4-Pro`、`DeepSeek-R1-Distill-Qwen-32B`、`QwQ-32B`、`ERNIE-5.0-Thinking` |
| 长上下文长文档 | `Qwen3.7-Max`、`Kimi-K2.6`、`kimi-k3`、`DeepSeek-V3.2` |
| 代码生成 / 代码评审 | `Qwen3-Coder-Next`、`Kimi-K2.7-Code`、`KAT-Dev`、`Qwen3-Coder-30B-A3B-Instruct` |
| 图像理解（截图 / 票据 / 表格） | `Qwen3-VL-30B-A3B-Instruct`、`ERNIE-4.5-Turbo-VL`、`PaddleOCR-VL-1.5` |
| 工具调用 / Agent 主控 | `DeepSeek-V4-Pro`、`Qwen3.7-Max`、`GLM-5.2`、`gpt-5.6-sol` |
| 极致性价比批处理 | `Qwen2.5-7B-Instruct`、`Qwen3.5-Flash`、`GLM-4-32B`、`gemma-4-26B-A4B-it` |
| 垂直行业（金融 / 法律 / 农学） | `Fin-R1`、`DianJin-R1-32B`、`LegalOne-8B`、`Sinong1.0-32B` |
| 翻译类 | `Hy-MT2-30B-A3B`、`HY-MT2-7B`、`Hunyuan-MT-Chimera-7B` |
| 需要出图 / 出视频 | `qwen-image-3.0-pro`、`gpt-image-2.5`、`nano-banana-pro`、`wan3.0-video`、`veo3.1-pro` |

> 清单会变。**调用前先跑一次 `GET /api/v1/models`**，拿返回的 `model` 编码为准。

### 2.4 生成类应用走另一条入口

模型网关之外，平台还有 21 个生成类应用（语音 / 图像 / 视频 / 数字人 / 文档问答等），
路径**永远**是 `/api/v1/apps/<应用代号>/<接口代号>`：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/voice_tts/tts" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，这是一条测试配音"}'
```

两条入口的区别要记牢：**模型网关是同步的，直接返回 `choices`，没有 `task_id`；
应用任务多为异步，返回 `task_id`，也不吃 `messages` 数组。** 选错入口是最常见的踩坑。

---

## 三、包里有什么

```
sanjianke-java-agent-kit/
├── SKILL.md                              本文件：接入主线与判断标准
├── README.md                             前置条件、依赖、安全与版权说明
├── references/
│   ├── core-concepts.md                  模块分层、工具、拦截器 order、运行时、RAG、MCP、路由熔断
│   ├── integration.md                    接入十一步：坐标核对 → 模型 → 工具 → 拦截器 → MCP → Skills → RAG → 运行时
│   └── selection-and-troubleshooting.md  选型判断维度 + 按症状定位的排错手册
└── scripts/
    └── a7w.py                            零依赖客户端（只用 Python 标准库，不内嵌任何密钥）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 验证并保存 Key
python3 scripts/a7w.py login --key sk-你的key

# 看当前 Key 能用的插件数
python3 scripts/a7w.py whoami

# 列出全部插件（21 个生成类应用）
python3 scripts/a7w.py apps

# 看某个插件的接口与参数
python3 scripts/a7w.py schema voice_tts

# 调接口：返回里有 task_id 会自动轮询到终态
python3 scripts/a7w.py call voice_tts tts --body '{"text":"你好世界"}'

# 只提交不等待，稍后自己查
python3 scripts/a7w.py call voice_tts tts_async --body '{"text":"你好世界"}' --no-wait
python3 scripts/a7w.py task tsk_xxxxxxxx

# 看最近的用量
python3 scripts/a7w.py points
```

- 只用 Python 标准库，**Python 3.8+**，不需要安装任何第三方包 任何东西。
- Key 读取顺序：`--key` 参数 → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
- 请求体用 `--body`；客户端对网络类错误与 5xx 做退避重试（4 次），4xx 是业务错误不重试。

### 可用性自检

```bash
export A7W_API_KEY=sk-你的key
python3 scripts/a7w.py whoami
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

---

## 四、核心概念

### 4.1 模块分层

```
运行层     Agent 运行时：推进轮次、审批、挂起恢复、持久化
能力层     Tool / ToolGroup / MCP / Skills / Text2SQL / 搜索 / Wiki
模型层     ChatModel / EmbeddingModel / ImageModel / RerankModel
提示词层   Prompt / Message / Memory / 拦截器
存储层     Store（向量库 / JDBC / Redis）
```

**关键约束**：能力层的东西最终都要落到模型层的 `Tool` 抽象上 —— MCP 来的工具、
Skills 加载的能力、Text2SQL 的工具集，在模型眼里是同一类东西。这是它能「组合」的原因。

**拆得开**：LLM 调用、工具、Agent 运行时、RAG、向量存储、图像、音频、MCP、Skills、
Text2SQL 各自独立成模块；**不强制**：核心模块在普通 Java 程序里就能用，不是必须挂在
Spring 容器里；**可替换**：模型、向量库、搜索引擎都以接口形式接入。

### 4.2 工具声明的两条路径

| 路径 | 写法 | 用在什么场合 |
|---|---|---|
| **注解式** | 方法上标 `@ToolDef(name = "...", description = "...")`，参数标 `@ToolParam(name = "...", required = true)` | 工具数量少、逻辑就在本地方法里，最省事 |
| **编程式** | 自己实现 `Tool` 接口，显式给出 name / description / 参数 schema / 执行函数 | 动态生成工具、参数随运行时变化、要从配置或远端拉工具定义 |

```java
@ToolDef(name = "query_order_status", description = "按订单号查询订单当前状态")
public String queryOrderStatus(
        @ToolParam(name = "orderNo", description = "订单号，纯数字", required = true) String orderNo) {
    return orderService.statusOf(orderNo);
}
```

### 4.3 工具组动态挂载与工具泄漏

工具组（`ToolGroup`）让「哪一轮带哪些工具」变成可编程的：按租户、按角色、按会话阶段
动态挂载与卸载。

**工具泄漏**指工具被带到了不该出现的轮次里 —— 模型看到了它不该看到的工具，于是答非所问
或者乱调。排查三步：

1. **盘点全量工具名**：本地 + MCP + Skills 一起盘，**重名的先改名**。
2. **做启动期校验**：重名、缺 description、参数 schema 非法，开机就报出来，别等线上。
3. **逐层关扩展点**：先关拦截器、再关工具组、最后关工具 —— 回到「裸问答」还能跑，
   说明问题在扩展点配置而不是模型。

### 4.4 拦截器：责任链与 order 语义

拦截器是这套体系里最容易被误用的部分，四个要点：

- **Chat 请求的 Body 是在所有拦截器都执行到责任链末端之后才拼出来的。**
  所以拦截器改不了原始 Body —— 要影响内容就得走提示词、参数这类结构化信息。
  看到「改了 Body 但没生效」，先回想这条设计约束。
- **order 只是排序，不是边界**。常见约定值：可观测性类给 `-1000`，普通拦截器给 `0`，
  请求准备类给更大的值；应用可以用任意整数，把拦截器放到可观测之前或请求准备之后。
- **条件拦截器在运行到该注册项时求值**，所以它能读到前面拦截器改过的上下文。
- **要给「之后创建的所有模型」挂条件拦截器，必须用全局注册入口**；只给单个实例注册
  只对该实例生效 —— 这是排查「拦截器不生效」的第二个高频原因。

### 4.5 Agent 运行时：审批、挂起恢复、快照

| 能力 | 解决什么 |
|---|---|
| 工具审批 | 危险动作（下单、退款、发消息）先停下来等人工确认 |
| 挂起与恢复 | 中途停下、之后接着跑；长任务不用一直占着连接 |
| 快照与版本 CAS | 状态可快照；用版本比对（CAS）避免并发推进同一会话时互相覆盖 |
| 事件与 Middleware | 运行时事件可订阅，扩展点不侵入业务 |

**判断该不该上运行时**：出现下面任意一条才需要 —— 多轮工具调用、工具审批、挂起恢复、
重启不丢状态。只调一次模型拿个回答，**不需要**。

### 4.6 RAG 全链路

```
文档加载 → 解析 → 切分 → Embedding → 写入向量库 → 按问题检索 →（可选）Rerank → 交给对话模型
```

- **召回优化**：切分策略 + 混合检索（关键词 + 向量）。
- **排序优化**：接 Rerank 模型。**召回一堆不如召回准**，Rerank 对答案质量的提升通常比
  继续调切分参数更直接。
- **路线不互斥**：Wiki、RAG、网络搜索、Skills 可以一起用，让模型自己决定查哪一路。

### 4.7 MCP 与 Skills 的定位

| 机制 | 一句话定位 |
|---|---|
| **MCP 客户端** | 连外部 MCP Server，把远程工具包装成本框架的 `Tool`。传输方式：本地进程用 stdio，远程用 http-sse / http-stream |
| **Skills** | 基于文件系统的技能加载 + **渐进式披露**，封装重复性的专业任务；模型先读说明，再按需展开细节 |
| **Skills 沙箱** | 隔离执行技能脚本的运行时聚合，含多种沙箱实现 —— **生产必须开** |

**安全底线**：Skills 会给模型「读说明 + 执行」的能力。生产环境务必配沙箱，
并限制可访问的目录与网络出口。

### 4.8 模型路由与熔断

一个服务同时接多家模型时，路由层负责：**负载均衡、重试、熔断与半开恢复**。

- 配了熔断**必须同时配半开探测**；探测失败要能再回到熔断，否则永远不会恢复。
- 降级要有出口：准备降级模型或降级话术，别让一次线路抖动变成一次全站 500。

### 4.9 OpenTelemetry 可观测

模型调用、工具调用、RAG 检索都导出 **Span 与 Metric**，支持把数据落到 JDBC。
把可观测拦截器放在责任链最前面（order `-1000`），保证「被拦掉的请求」也留痕。

---

## 五、工作流路由

| 你要什么 | 看哪份 |
|---|---|
| 接之前核对该框架的 Maven 坐标、版本来源、依赖树 | `references/integration.md` 第一步 |
| 模块分层、能力边界、拦截器语义、运行时、RAG、MCP | `references/core-concepts.md` |
| 十一步接入顺序：模型 → 工具 → 拦截器 → MCP → Skills → RAG → 运行时 | `references/integration.md` |
| 选型判断维度、按症状定位的排错手册 | `references/selection-and-troubleshooting.md` |
| 模型清单、插件清单、接口参数、异步任务、用量 | `scripts/a7w.py`（`models` / `apps` / `schema` / `task` / `points`） |
| 计费口径、错误码、失败重试 | 本文「七、计费」+ `references/selection-and-troubleshooting.md` |

---

## 六、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 业务成功码是 **`code == 1`**（`{"code":1,"msg":"success"}`）；`code == 0` 是失败，**但 HTTP 仍可能是 200**，不能只看状态码 |
| **`max_tokens` 给太小，推理模型正文为空** | `content` 返回 `null`、`finish_reason=length` | `DeepSeek-V4-Flash` 在 `max_tokens=8` 时 token 全被思维链吃掉；**加到 256 就正常返回** |
| **思维链字段只取一个** | 换条线路就读不到思考过程 | 字段名在不同线路上分别是 `reasoning` 与 `reasoning_content`，**两个都要取** |
| **拿响应里的 `model` 做精确匹配** | 请求 `DeepSeek-V4-Flash` 却匹配不上 | 响应会规范成小写 `deepseek-v4-flash`，**用请求侧的值做键** |
| **应用路径拼错 / 用 `endpoint_path` 拼 URL** | 404 或打不通 | 应用路径**一律** `/api/v1/apps/<应用代号>/<接口代号>`，两个代号都取自线上返回的 `code` 字段；**绝对不要用 `endpoint_path` 拼 URL** |
| **应用代号用连字符** | 404 | 用**下划线**：`voice_tts` 可以，`voice-tts` 会 404 |
| **把 `name` 当接口名传** | 调用失败 | 接口定义字段名是 `code`（不是 `api`），参数定义在 `params_schema`（不是 `schema`）；`name` 是中文展示名 |
| **只认 `properties` 形态的 schema** | 明明有 6 个参数却判成「无参数」 | `params_schema` 有带 `properties` 包装与扁平字典两种形态，**两种都要认** |
| **选错入口** | 模型网关没有 `task_id`；应用任务不吃 `messages` | 先想清楚要的是「一段推理结果」还是「一个生成产物」 |
| **拦截器里改 Body** | 改了不生效 | Body 在责任链末端才构建；**走提示词与参数这类结构化信息** |
| **只给单实例注册条件拦截器** | 别的模型上不生效 | 要给「之后创建的所有模型」挂，必须用**全局注册入口** |
| **工具重名** | 工具不触发或乱调 | 本地 + MCP + Skills 全量工具名做一次**启动期重名校验** |
| **只配熔断不配半开** | 熔断后再也不恢复 | 配**半开探测**，探测失败能再回到熔断 |
| **重复提交异步任务** | 扣两次钱 | 提交时就预冻结点数；超时先查 `task_id` 再决定是否重提 |
| **回调地址没返回 2xx** | 平台按 1–10 次重试，重复消费 | 回调接口按 `task_id` **幂等**，并确保返回 2xx |

### 错误码速查

| HTTP | code | 含义 | 怎么办 |
|---|---|---|---|
| 400 | `invalid_request` | 参数缺失或格式错误 | 用 `schema <app>` 核对参数名与必填项 |
| 401 | `auth_failed` | API Key 缺失或无效 | 重新复制 Key，确认 `Bearer ` 前缀 |
| 402 | `insufficient_points` | 账号点数余额不足 | 充值；错误里带本次所需点数 |
| 402 | `key_quota_exceeded` | 该 Key 自己的额度打满 | 去用户中心调高该 Key 的 quota，或换 Key |
| 403 | `permission_denied` | 该 Key 无权调用此模型 / 应用 | 检查模型是否已开通、Key 是否被限权 |
| 404 | `not_found` | 模型 / 应用 / 任务不存在 | 核对代码拼写；**先怀疑 `/v1` 层数** |
| 429 | `queue_limit_exceeded` | 排队任务已达上限 | 降并发，等队列消化后重试 |
| 5xx | `server_error` | 服务异常 | 退避重试；仍失败换模型 / 线路 |

**402 有两种**：账号没钱（`insufficient_points`）和 Key 自己的额度打满
（`key_quota_exceeded`）。先分清是哪一种，否则会去充一个根本不需要充的账户。

### 逐层加回法（排错主线）

加流式 → 加一个工具 → 加一个工具组 → 加一个拦截器。**哪一步坏了，问题就在那一步。**
反过来也成立：关掉所有扩展点，回到「裸问答」还能跑，说明框架本身没问题。

---

## 七、计费

- **1 元 = 100 点，1 点 = 0.01 元。** 点数永久有效。
- 体验包 ¥10 = 600 点（含 7 天会员权益），标准包 ¥99 = 10000 点。
- **先冻结、后结算**：消费优先扣会员点数，不足再扣充值额度。
- **调用失败直接退款；异步任务失败，冻结点数全额退回。**
- **查询任务状态免费。**

| 能力类型 | 计费口径 |
|---|---|
| 文本对话 | 点数 / 百万 tokens（输入输出分别计价，流式与非流式同价） |
| 图像 | 点数 / 张 或分辨率档位 |
| 视频生成 / 超分 | 点数 / 秒（分辨率分档） |
| 数字人 | 点数 / 次 或时长 |
| TTS / 克隆 | 点数 / 千字 |
| ASR | 点数 / 分钟 |
| 工具类应用 | 点数 / 次 |

> **两套价格字段，做预算一律用后者**：`fixed_price` / `input_price` 是**公示标准价**；
> `tenant_fixed_points` / `tenant_points_per_1k_input` 是**你所在租户的实际结算价**。
> 最终以账号里实际扣费为准。

### 异步任务与回调

- 提交返回 `{"task_id":"tsk_xxx","status":"pending","created_at":...}`，
  轮询 `GET /api/v1/tasks/<task_id>`。
- 终态：`completed` / `failed` / `cancelled`；产物在 `result`，用量在 `usage`。
- 也可提交时带 `callback_url`，平台完成后 POST JSON；你的接口返回 **2xx** 才算接收成功，
  否则按「用户中心 → 回调配置」里设的次数（**1–10 次**）重试 ——
  **消费端必须按 `task_id` 幂等**。

---

## 八、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的网关接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 用作素材入参与请求参数 |
| 写入文件 | 仅在传入 `--out` 时 | 保存接口返回的 JSON 结果 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量 `A7W_API_KEY` 或 `~/.a7w/config.json` 读取 |
| 子进程 / 后台常驻 | 不申请 | 脚本执行完即退出，不注册服务、不常驻 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代内容合规审查**：生成内容与生成结果的使用责任由使用者承担
- **不保证可用性**：模型上下架、限流与计费以站内为准，**调用前先跑 `models` / `apps` 拿准数**
- **Skills 生产必配沙箱**：Skill 会给模型「读说明 + 执行」的能力，务必限制目录与出口

---

## 关于这个 Skill

**作者亲测实操后发布，下载后可直接使用，自用商用都可以。**

所有 AI 能力都走 [算力集市 api.a7w.cn](https://api.a7w.cn/) —— 一把 API Key 打通
大模型、语音、图像、视频、数字人等全部算力，注册即送点数，按量计费、没有月费。

| 你可能想问 | 答案 |
|---|---|
| 要不要额外部署 | 不用。**下载本包即可使用**，不必去别处找源码 |
| 怎么开始 | 到 api.a7w.cn 注册领 Key → 填进 `A7W_API_KEY` → 改一行 `base_url` 跑起来 |
| 能不能商用 | 可以 |
| 遇到问题找谁 | 见文末「联系我们」，作者本人答疑 |

> 使用中碰到任何问题 —— 报错、效果不理想、想省钱、想批量 —— 都欢迎加微信聊。
> 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的示例。

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
