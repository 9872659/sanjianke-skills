# 接入与示例

> **读之前先看这条**：下面的示例写的是**结构与调用关系**，不是可以原样粘贴的成品。
> 类名与接口名是这一类 Java Agent 框架里常见的概念标识，**签名可能与你手上的实现有出入**；
> 版本号统一写成 `<VERSION>` 占位。动手前请以本机实际引入的那个版本的源码为准。
>
> **坐标书写约定**：本文所有 `groupId` / `artifactId` 都是占位 —— `<your-groupId>`、
> `<your-artifactId>`，**填你实际使用的那套框架的真实坐标**。包名同理，用 `<base-pkg>`
> 代表你自己的包名根（例如 `com.example.agent`）。

---

## 第一步：接入前先核对坐标（最关键，别跳）

这是整份文档里唯一"跳过会浪费半天"的步骤。核对的是**你选的那套框架在你团队的实际获取渠道上能不能解析通过**。

### 1.1 查一个坐标到底存不存在、有哪些版本

方法一：看构建工具自己的解析结果，这是唯一有权威性的答案。

```bash
# 全量依赖树，看这个 group 下解析到了什么
mvn -q dependency:tree -Dincludes=<your-groupId>

# 只要某一条依赖的版本
mvn -q dependency:list -DincludeGroupIds=<your-groupId>

# 离线编译：能最快暴露本地库缺哪个构件
mvn -q -o compile
```

方法二：查公开仓库的检索接口，确认这个 group 在公共仓库里到底发布过哪些版本。
把 `<your-groupId>` 换成你实际的 group 再去查：

```bash
# 按 groupId 搜构件（把 <your-groupId> 换成实际值）
curl -s "https://search.maven.org/solrsearch/select?q=g:%22<your-groupId>%22&rows=100&wt=json"

# 只要版本列表（core=gav）
curl -s "https://search.maven.org/solrsearch/select?q=g:%22<your-groupId>%22&core=gav&rows=200&wt=json"
```

> **这里只写方法，不写任何具体 group 名。** 你换成自己的坐标去查。
> 注意检索接口的返回有缓存延迟，**最终以 `mvn` 实际解析结果为准**。

### 1.2 三种版本来源，先确认你用的是哪一种

| 来源 | 判定方式 | 后续责任 |
|---|---|---|
| 公共仓库已发布版本 | 1.1 的方法二能查到 | 直接写版本号即可，升级是你自己的节奏 |
| 团队私服 / 镜像代理 | 私服上能搜到 | 确认镜像同步策略覆盖了这个 group，否则会漏 |
| 团队自建并 install 到本地库 | 只有本机或私服有 | 你要承担构建、发布与升级回归（谁构建、谁发版、怎么回归） |

**先把这一格填了，再往下走。不要一边写代码一边试坐标。**

### 1.3 顺带核对 JDK

```bash
java -version
mvn -v
```

**JDK 要按"模块"核对，不按"框架"核对**：同一套框架里，多数模块 JDK 8+ 能跑，
但涉及 MCP 这类较新的模块往往要求 JDK 17+。如果工程还在 8 上，引这类模块会在构建期或
运行期炸 —— 而且报错信息通常不指向根因，容易查偏。

---

## 第二步：引入依赖

### 方式一：BOM 收口（多模块工程推荐）

BOM 只做版本管理，**本身不引入具体能力**。

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>&lt;your-groupId&gt;</groupId>
      <artifactId>&lt;your-artifactId&gt;-bom</artifactId>
      <version>&lt;VERSION&gt;</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

之后引子模块就不用逐个写版本：

```xml
<!-- 核心抽象 -->
<dependency>
  <groupId>&lt;your-groupId&gt;</groupId>
  <artifactId>&lt;your-artifactId&gt;-core</artifactId>
</dependency>
<!-- 对话模型适配（按你实际用的那一个） -->
<dependency>
  <groupId>&lt;your-groupId&gt;</groupId>
  <artifactId>&lt;your-artifactId&gt;-chat-openai</artifactId>
</dependency>
<!-- 向量存储适配（按你实际用的那一个） -->
<dependency>
  <groupId>&lt;your-groupId&gt;</groupId>
  <artifactId>&lt;your-artifactId&gt;-store-redis</artifactId>
</dependency>
```

> **产物名和版本线必须配套。** 同一套框架换大版本时，模块命名常常整体改过一次
> （对话模型模块可能从 `*-llm-*` 变成 `*-chat-*`，文档解析可能从 `*-document-parser*`
> 变成 `*-doc-extractor`）。**照抄一份和你版本线不匹配的示例，必然 `Could not resolve`**，
> 而且很容易被误判成镜像或网络问题。核对方式：在你的版本线上直接看该 group 下的产物清单。

### 方式二：Spring Boot 启动器

```xml
<dependency>
  <groupId>&lt;your-groupId&gt;</groupId>
  <artifactId>&lt;your-artifactId&gt;-spring-boot-starter</artifactId>
  <version>&lt;VERSION&gt;</version>
</dependency>
```

### 方式三：只引最小集合

单个服务接一个模型时最省事，也最不容易出依赖冲突：

```xml
<dependency>
  <groupId>&lt;your-groupId&gt;</groupId>
  <artifactId>&lt;your-artifactId&gt;-core</artifactId>
  <version>&lt;VERSION&gt;</version>
</dependency>
<dependency>
  <groupId>&lt;your-groupId&gt;</groupId>
  <artifactId>&lt;your-artifactId&gt;-chat-openai</artifactId>
  <version>&lt;VERSION&gt;</version>
</dependency>
```

**引完立刻验一次**：

```bash
mvn -q dependency:tree -Dincludes=<your-groupId>
mvn -q -o compile
```

---

## 第三步：最小可运行（对话）

任何一个 OpenAI 兼容端点，构造对话模型只需要四要素：**端点、供应商标识、模型名、API Key**。

```java
// 把 <base-pkg> 换成你自己的包名根，例如 com.example.agent
import <base-pkg>.core.model.chat.ChatModel;
import <base-pkg>.model.chat.openai.OpenAiChatConfig;

public class MinimalChat {
    public static void main(String[] args) {
        ChatModel chatModel = OpenAiChatConfig.builder()
                // 模型侧统一指向算力网关（OpenAI 兼容）
                .endpoint("https://api.a7w.cn/api/v1")
                // 填你的 Key；示例里也不写死，走环境变量
                .apiKey(System.getenv("A7W_API_KEY"))
                // 换模型就是换这个字符串
                .model(System.getenv().getOrDefault("LLM_MODEL", "DeepSeek-V4-Flash"))
                .buildModel();

        System.out.println(chatModel.chat("用一句话说明这个服务是干什么的"));
    }
}
```

**三条纪律**：

1. 密钥走环境变量。示例里也不写死，仓库里 grep 不到明文。
2. `endpoint` 填**基址**（`https://api.a7w.cn/api/v1`），不要在基址上再手工拼
   `/chat/completions` —— 多数兼容实现自己会补路径，你补一次就变成两层。
3. 第一次跑通先不看流式。同步跑通再动流式，能把"配置问题"和"流式解析问题"分开。

---

## 第四步：把模型侧指向 api.a7w.cn（本节是重点）

### 4.1 为什么这一个地址就够

算力集市 `api.a7w.cn` 的模型侧**兼容 OpenAI 协议**：它把多家厂商的模型收口在同一个
`base_url` 后面，用同一把 Key、同一份账单。对 Java 侧的实际含义是：

| 事实 | 对你的意义 |
|---|---|
| Base URL 固定为 `https://api.a7w.cn/api/v1` | 框架里所有"自定义 OpenAI 端点"的配置项都填这一个值 |
| 鉴权统一为 `Authorization: Bearer <你的 API Key>` | 不需要为每家厂商维护一套签名逻辑 |
| **一个 Key 可切换 75 个在架模型** | 换模型 = 换 `model` 字符串，不用换 Key、不用换 base_url、账单还是同一份 |
| 模型清单可现场拉取 | 不要猜模型名，上下架很频繁 |

### 4.2 三个必需值

| 配置项 | 值 |
|---|---|
| base_url | `https://api.a7w.cn/api/v1` |
| Authorization | `Bearer <你的 API Key>` |
| model | 从模型清单接口里取的真实编码 |

本文示例用的模型编码（都是可用值，实际以清单为准）：

- `DeepSeek-V4-Flash`
- `Qwen3.6-Plus`
- `Kimi-K2.6`

```bash
# 先确认网络与鉴权通（返回 200 即通）
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'

# 拿在架模型清单（字段含模型编码、厂商、能力标记），不要靠猜
curl -s "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"
```

### 4.3 在框架里怎么落

三条路，按你手上框架给的配置形态挑一条：

**A. 框架的模型配置项直接填 base_url（首选）**

```java
ChatModel chatModel = OpenAiChatConfig.builder()
        .endpoint("https://api.a7w.cn/api/v1")   // base_url
        .apiKey(System.getenv("A7W_API_KEY"))    // Bearer <你的 API Key>
        .model("Qwen3.6-Plus")                   // 换这一行就是换模型
        .buildModel();
```

**B. 走框架约定的环境变量（多数 OpenAI 兼容实现都认这两个）**

```bash
# JVM 启动参数或部署环境里注入
OPENAI_BASE_URL=https://api.a7w.cn/api/v1
OPENAI_API_KEY=<你的 API Key>
```

**C. Spring Boot 配置**

```yaml
# 键名以你依赖里那个版本的自动配置元数据为准，下面是形状示意
your-framework:
  chat:
    openai:
      base-url: https://api.a7w.cn/api/v1
      api-key: ${A7W_API_KEY}
      model: Kimi-K2.6
```

### 4.4 换模型：只有一行会变

```java
// 调研用快的
ChatModel fast = OpenAiChatConfig.builder()
        .endpoint("https://api.a7w.cn/api/v1")
        .apiKey(System.getenv("A7W_API_KEY"))
        .model("DeepSeek-V4-Flash")
        .buildModel();

// 评审用强的
ChatModel strong = OpenAiChatConfig.builder()
        .endpoint("https://api.a7w.cn/api/v1")
        .apiKey(System.getenv("A7W_API_KEY"))
        .model("Qwen3.6-Plus")
        .buildModel();
```

**关键性质**：`endpoint` 和 `apiKey` 一个字都不用改。这意味着你可以把"用哪个模型"
做成配置项甚至数据库字段，并按场景分级 —— 摘要用快的、推理用强的、批量兜底用便宜的，
账单仍然是同一份。多实例如何组合（负载均衡、重试、熔断）见第九步与 `core-concepts.md` 第九节。

### 4.5 三个高频坑

| 坑 | 症状 | 正确做法 |
|---|---|---|
| 基址上又拼了一次路径 | 404，且路径出现 `/v1/v1/` | **填基址**（`.../api/v1`），把路径拼接交给框架 |
| 模型名靠猜 | 报模型不存在之类的错误 | 现场拉 `/api/v1/models`，取真实的模型编码 |
| Key 写进代码或配置文件 | 仓库里 grep 得到明文 | 走环境变量或配置中心；本文所有示例都用 `System.getenv` |

> **Embedding / Rerank 是否同一个地址**：这些能力也走 OpenAI 兼容风格的路径，
> 但**具体在架哪些模型、编码叫什么，以你现场拉到的模型清单为准**，不要假设某个 embedding
> 模型一定在架。核对不通过时，Embedding 可以退回本地部署的模型，上层向量库与检索代码不变。
> 换 embedding 模型会改维度，这一点见第十三步。

---

## 第五步：流式输出

同一套提示词与参数机制，只是换成带监听器的调用方式：

```java
import <base-pkg>.core.model.chat.StreamResponseListener;
import <base-pkg>.core.model.chat.response.AiMessageResponse;
import <base-pkg>.core.model.client.StreamContext;

chatModel.chatStream("解释一下责任链模式在网关里的作用", new StreamResponseListener() {
    @Override
    public void onMessage(StreamContext context, AiMessageResponse response) {
        // 逐段取增量内容
        String piece = response.getMessage().getContent();
        if (piece != null) {
            System.out.print(piece);
        }
    }
});
```

**流式最容易出的三类问题**（详见排错文件第三类）：

- 把每次回调当成完整回答 → 拼接顺序错、内容重复
- 结束条件判断错 → 流结束了还在等，或提前收尾
- 同步用的是框架拼好的提示词，流式自己另拼了一套 → 两边行为不一致

---

## 第六步：Tool Calling（注解声明式）

### 6.1 把业务方法暴露成工具

```java
import <base-pkg>.core.model.chat.tool.annotation.ToolDef;
import <base-pkg>.core.model.chat.tool.annotation.ToolParam;

public class OrderTools {

    @ToolDef(name = "query_order_status", description = "按订单号查询订单当前状态")
    public static String queryOrderStatus(
            @ToolParam(name = "orderNo", description = "订单号，纯数字", required = true) String orderNo) {
        // 这里换成真实业务查询
        return "{\"orderNo\":\"" + orderNo + "\",\"status\":\"SHIPPED\"}";
    }
}
```

**工具描述的质量直接决定模型调不调、调得对不对**。三条经验：

- 描述里写清**什么时候该用**，不只写"这个工具做什么"
- 参数写清**格式与示例**（"纯数字"、"ISO-8601 日期"）
- 返回结构化 JSON 字符串，别返回给人看的长段落

### 6.2 挂到提示词上，走完一次工具调用

```java
import <base-pkg>.core.prompt.SimplePrompt;
import <base-pkg>.core.model.chat.response.AiMessageResponse;

SimplePrompt prompt = new SimplePrompt("帮我查一下订单 20260101001 现在到哪了");
prompt.addToolsFromClass(OrderTools.class);   // 扫描类上的工具注解

AiMessageResponse first = chatModel.chat(prompt);

if (first.hasToolCalls()) {
    // 执行模型要求的工具，把结果包成工具消息塞回提示词
    prompt.setToolMessages(first.executeToolCallsAndGetToolMessages());
    // 再请求一次，这次模型拿到工具结果后给最终回答
    System.out.println(chatModel.chat(prompt).getMessage().getContent());
}
```

**这是必须理解的循环**：模型不会自己执行工具。你的代码负责"模型要求 → 你执行 → 结果回传 →
再问一次"。**要设最大循环次数**，否则工具反复失败时可能空转烧钱。

### 6.3 编程式构建工具

工具来自运行时配置、插件系统或工作流节点时，用构造器拼装，而不是写注解：

```java
import <base-pkg>.core.model.chat.tool.Tool;

// 结构示意：名、描述、参数 schema、执行体
Tool dynamicTool = Tool.builder()
        .name("tenant_lookup")
        .description("按租户名查询租户 ID")
        .addParameter("tenantName", "string", "租户名称", true)
        .handler(args -> tenantService.findIdByName((String) args.get("tenantName")))
        .build();
```

> `Tool.builder()` 的具体方法名以你引入的版本为准。编程式构建的价值在于
> **工具集合可以来自数据库或配置中心**，代价是描述质量没人替你保证。

---

## 第七步：工具组（按输入动态挂载）

工具多起来之后，全量挂载会同时推高成本和错误率。工具组让"只有相关的工具才进请求体"：

```java
import <base-pkg>.core.prompt.MemoryPrompt;
import <base-pkg>.core.model.chat.tool.ToolGroup;
import <base-pkg>.core.model.chat.tool.ToolScanner;
import <base-pkg>.core.model.chat.tool.ToolGroupMatchers;

ToolGroup orderGroup = ToolGroup.builder("order")
        .addTools(ToolScanner.scan(OrderTools.class))
        .systemPrompt("涉及订单状态、物流、退款的问题必须使用订单工具。")
        .matcher(ToolGroupMatchers.promptContains("订单", "物流", "退款"))
        .build();

MemoryPrompt prompt = new MemoryPrompt();
prompt.addToolGroup(orderGroup);
prompt.addUserMessage("我上周买的东西到哪了");
chatModel.chat(prompt);
```

关键机制（也是排查工具泄漏问题的依据）：

- **每一轮都基于最后一条用户消息重新匹配**，上一轮命中的工具不会留到下一轮
- 未命中的组**不进请求体** —— 省 token 是真实的
- 匹配条件除了"包含关键词"、"匹配模式"，还能用自定义策略（按用户属性、时间、租户等）

**工具上百个时的替代方案**：用渐进式工具发现，让模型先检索再调用，而不是靠关键词命中。

---

## 第八步：拦截器

### 8.1 改参数（在 `proceed` 之前）

```java
import <base-pkg>.core.model.chat.interceptor.ChatInterceptor;
import <base-pkg>.core.model.chat.ChatContext;
import <base-pkg>.core.model.chat.SyncChain;

ChatInterceptor auditInterceptor = new ChatInterceptor() {
    @Override
    public AiMessageResponse intercept(BaseChatModel<?> model, ChatContext context, SyncChain chain) {
        context.getOptions().setTemperature(0.2f);                 // 影响最终请求参数
        context.getRequestSpec().addHeader("X-Tenant", tenantId);  // 影响请求头
        return chain.proceed(model, context);
    }
};
```

**注意请求规格对象只含 URL、Header、重试配置，不暴露 Body**。想改请求内容，只能走提示词、
参数这类结构化信息。这是设计约束，不是缺陷。

### 8.2 条件激活 + 顺序

```java
import <base-pkg>.core.model.chat.interceptor.ChatInterceptorRegistration;

chatModel.addInterceptorRegistration(
        ChatInterceptorRegistration.builder("premium-audit", new AuditChatInterceptor())
                .matcher(context -> "premium".equals(context.getAttribute("plan")))
                .order(0)
                .build()
);
```

- 条件是**运行到该注册项时**求值的，所以能读到前面拦截器改过的上下文
- order 升序稳定排序，相同 order 保持注册顺序
- 约定值只是推荐：可观测 `-1000`、普通 `0`、请求准备（工具组解析）`1000`
- 要给**之后创建的所有**模型挂条件拦截器，用全局注册入口

---

## 第九步：Spring Boot 接入

```xml
<dependency>
  <groupId>&lt;your-groupId&gt;</groupId>
  <artifactId>&lt;your-artifactId&gt;-spring-boot-starter</artifactId>
  <version>&lt;VERSION&gt;</version>
</dependency>
```

自动配置通常覆盖"最常用"的一档（对话模型与几种向量存储）。

**配置键名不要照抄二手博客**。可靠做法是直接查你引的那个版本：

```bash
# 找到 starter 的实际位置
mvn -q dependency:build-classpath -Dmdep.outputFile=cp.txt

# 解压对应 jar，读自动配置元数据（键名、类型、默认值都在里面）
#   META-INF/spring-configuration-metadata.json
```

**未覆盖的模型/向量库不等于不能用** —— 手动构造实例即可，只是没有自动配置帮忙读配置项。
把 base_url 指向 `https://api.a7w.cn/api/v1` 这种接法，本来就属于"手动构造"，
不依赖自动配置覆盖到哪一档。

---

## 第十步：MCP 接入

支持三类传输方式：**stdio**、**http-sse**、**http-stream**。加载方式通常是配置文件
（例如 `mcp-servers.json`），然后把 MCP 工具转成本框架的工具 —— 对上层业务就是普通 `Tool`。

接入步骤：

1. **确认 JDK 17+**（这类模块的常见硬要求）
2. 按你的传输方式准备 MCP Server：本地进程用 stdio，远程用 http-sse / http-stream
3. 在配置里声明 server 列表（**字段结构以你引入的那个版本的说明为准**，各版本调整过）
4. 用客户端管理器建立连接
5. 把拉到的远程工具挂到提示词上 —— 从这一步开始，和本地工具没有区别

**排错要点**：

- stdio 方式启动失败，八成是**命令路径或工作目录**问题，先在 shell 里手跑一遍那条命令
- 远程方式连不上，先分清是**网络不通**还是**协议不对**（sse 与 stream 不是一回事）
- 工具名冲突：远程工具与本地工具重名时行为取决于实现，**先做一次名字盘点**

---

## 第十一步：Skills 接入

Skills 是**基于文件系统**的技能加载 + 渐进式披露机制，用于封装重复性的专业任务
（代码审查、文档生成、文件处理、本地知识检索这类）。

落地要点：

1. 规划目录结构：一个技能一个目录，配一份说明文件（具体约定以你手上的实现为准）
2. 用技能工具指向技能根目录，让它按需加载
3. 技能需要跑脚本时，**用沙箱模块隔离执行**，不要让模型直接在宿主机上跑任意脚本
   —— 沙箱通常有多种基于不同运行时的实现，按你有哪种运行时选

**安全底线**：Skills 会给模型"读说明 + 执行"的能力。生产环境务必配沙箱，且限制可访问的
目录范围；不要用管理员账号跑。

---

## 第十二步：智能问数（Text2SQL）

能力组合是：**数据源列表、表字段查询、SQL 执行**三类工具，加一层安全约束。

安全约束包含：

- 只读 SQL 校验
- 参数化查询约束
- `LIMIT` 控制
- 租户隔离
- 审计扩展点

接入顺序建议：

1. 先只给**表结构查询**能力，让模型学会"看表"（渐进式披露，别一次灌全库 schema）
2. 再开 SQL 执行，但**必须**配只读账号 —— 校验层是兜底，不是唯一防线
3. 加 `LIMIT` 上限与超时，避免大表全扫
4. 多租户场景接上租户隔离，否则会串数据
5. 审计扩展点接上日志，便于事后追责

**红线**：永远不要给这个模块一个可写账号。生成 SQL 的模型可能被提示词注入，
只读 + 校验 + 限额是三重防线，缺一层都不行。

---

## 第十三步：RAG 与向量库

标准链路（六步）：

```
加载文档 → 解析 → 切分 → 生成 Embedding → 写入向量库 → 检索（可选 Rerank）→ 交给对话模型
```

接入顺序：

1. **选向量库**。已有 Redis 就用 Redis 适配；已有 Elasticsearch/OpenSearch 也一样；
   全新起步、只做小规模知识库可以用本地轻量方案。**不要为了 RAG 新建一套中间件**，
   能用现有的就用现有的。
2. **确认 Embedding 模型与向量库维度一致**。这是最经典的坑：换 Embedding 模型后维度变了，
   老数据检索不出来也不会报错，只是召回为 0。
3. **切分策略先粗后细**。按标题层级切比按固定字数切好，先跑通再调粒度。
4. **接 Rerank**。召回一堆不如召回准，Rerank 对答案质量的提升通常比调切分参数更明显。
5. **文档提取**用专门的提取模块，PDF / Office / HTML / 邮件 / 压缩包 / URL 都能转成
   Markdown 风格文本，比自己写解析稳。

**向量化侧怎么接**：Embedding 走同一个 OpenAI 兼容网关是最省事的做法 ——
把 embedder 的 base_url 也指向 `https://api.a7w.cn/api/v1`，和对话模型用同一把 Key。
但**前提是模型清单里确实有你要用的 embedding 模型**：现场拉一次清单确认，
没有就退回本地部署的 embedding，上层的向量库与检索代码不变。

**验证召回是否真的工作**：拿一个答案明确的问题，把检索到的片段打印出来看。**只看最终回答
判断不出来** —— 模型可能靠自己的知识答对了，掩盖了检索为空的事实。

---

## 第十四步：Agent 运行时接入

出现下面任意一条才需要：多轮工具调用、工具审批、挂起恢复、重启不丢状态。

落地四步：

1. **先引运行层，再引存储层**。存储层是 JDBC 或 Redis 实现，两者选一，按现有运维栈定。
2. **初始化持久化表/结构**（JDBC 方式需要建表，脚本以你引入的那个版本为准）。
3. **接审批环节**。哪些工具需要人工确认要显式列出来 —— 默认全放开等于没有审批。
4. **测重启恢复**：跑到一半把服务停掉，重启后确认能从快照恢复，且版本 CAS 没有冲突。

**并发注意**：版本 CAS 的意义是防并发覆盖。同一会话被两个请求同时推进时会有一方失败，
这是**正确行为**，不是 bug；上层要处理这个失败（提示重试或加会话级锁）。

---

## 第十五步：上线前配置清单

| 项 | 检查点 |
|---|---|
| 密钥 | 全部走环境变量或配置中心，仓库里 grep 不到明文 |
| 模型入口 | base_url 指向 `https://api.a7w.cn/api/v1`；模型编码从清单接口现场取，不是猜的 |
| 版本 | 用 BOM 或 `dependencyManagement` 统一，没有散落的版本号 |
| 超时 | 连接、读写、整体请求三层超时都设了，别用无限等待 |
| 重试 | 只对幂等操作重试；重试次数与退避策略明确 |
| 工具 | 最大调用轮次设了上限；高危工具走审批 |
| 限流降级 | 路由层配了熔断与半开；有降级模型或降级话术 |
| 可观测 | OTel 开关放在 JVM 启动参数里；导出间隔评估过开销 |
| 日志 | 不打印密钥与完整用户输入；工具入参与结果按需脱敏 |
| 回滚 | 依赖版本可退回、配置可回切、持久化结构变更可兼容旧版本 |

---

## 附：最小验证工程的做法

排查问题时不要在原工程上改。建一个最小工程，只引 `core` + 一个模型适配，端点填
`https://api.a7w.cn/api/v1`，跑通"一句问答"，然后**一次只加一样**：
加流式 → 加一个工具 → 加一个工具组 → 加一个拦截器。哪一步坏了，问题就在那一步。
这比在复杂工程里猜快十倍。
