# 接入与示例

> **读之前先看这条**：下面的示例写的是**结构与调用关系**，不是可以原样粘贴的成品。
> 类名与方法来自核对到的公开信息，但**签名可能随版本变化**；版本号统一写成 `<VERSION>`
> 占位，因为该填哪个值取决于你自己的核对结果（原因见第一步）。动手前请以本机实际拉到的
> 那个版本的源码为准。

---

## 第一步：接入前先核对坐标（最关键，别跳）

这是整份文档里唯一"跳过会浪费半天"的步骤。

### 1.1 核对中央仓库有哪些版本

```bash
# 方式一：打开网页按 groupId 过滤
#   https://search.maven.org/  →  搜索 groupId: com.agentsflex

# 方式二：命令行查（不需要登录）
curl -s "https://search.maven.org/solrsearch/select?q=g:%22com.agentsflex%22&rows=100&wt=json"

# 方式三：只查版本列表
curl -s "https://search.maven.org/solrsearch/select?q=g:%22com.agentsflex%22&core=gav&rows=200&wt=json"
```

### 1.2 核对上游仓库自己声明的版本

```bash
git clone --depth 1 https://gitee.com/agents-flex/agents-flex.git
# 版本写在根 pom 的 revision 属性里，直接看这个值
grep -n "<revision>" agents-flex/pom.xml
```

### 1.3 把两个结果对一下 —— 大概率不一致

核对时点的事实（**请自行复核，不要当成永久结论**）：

| 来源 | 结果 |
|---|---|
| Maven 中央仓库 `com.agentsflex` | 只有 `1.0.0-rc.1` ~ `1.0.0-rc.6`，最后一次发布在 2025-02 |
| 上游仓库根 pom 的 `revision` | 已到 `2.2.9` |

**所以会出现三种选择，各有代价**：

| 选择 | 做法 | 代价 |
|---|---|---|
| A. 用中央仓库能拉到的版本线 | 直接用 `1.0.0-rc.x` | 版本旧，模块命名是 1.x 那套；没有较新的 Agent 运行时等能力 |
| B. 自建 2.x | 克隆仓库 `mvn clean install` 装到本地库或私服 | 要自己承担构建、升级与版本管理 |
| C. 用上游另行提供的仓库 | 在 pom 里加对应 repository 配置，地址以上游说明为准 | 依赖外部仓库的可用性 |

先把这个决定做了，再往下走。**不要一边写代码一边试坐标。**

### 1.4 顺带核对 JDK

```bash
java -version
```

上游多数模块要求 **JDK 8+**，但 **MCP 模块要求 JDK 17+**。如果工程还在 8 上，引 MCP 模块
会在构建期或运行期炸 —— 这类问题报错信息通常不指向根因，容易查偏。

---

## 第二步：引入依赖

### 方式一：BOM 收口（多模块工程推荐）

BOM 只做版本管理，**本身不引入具体能力**。

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.agentsflex</groupId>
      <artifactId>agents-flex-bom</artifactId>
      <version>&lt;VERSION&gt;</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

之后引子模块就不用逐个写版本：

```xml
<dependency>
  <groupId>com.agentsflex</groupId>
  <artifactId>agents-flex-core</artifactId>
</dependency>
<dependency>
  <groupId>com.agentsflex</groupId>
  <artifactId>agents-flex-chat-openai</artifactId>
</dependency>
<dependency>
  <groupId>com.agentsflex</groupId>
  <artifactId>agents-flex-store-redis</artifactId>
</dependency>
```

> **1.x 与 2.x 的命名差异会在这里咬人**：1.x 时期的对话模型模块叫 `agents-flex-llm-*`，
> 2.x 是 `agents-flex-chat-*`；文档解析模块从 `agents-flex-document-parser*` 变成
> `agents-flex-doc-extractor`。**产物名和版本线必须配套**，混用必然 `Could not resolve`。

### 方式二：Spring Boot 启动器

```xml
<dependency>
  <groupId>com.agentsflex</groupId>
  <artifactId>agents-flex-spring-boot-starter</artifactId>
  <version>&lt;VERSION&gt;</version>
</dependency>
```

### 方式三：只引最小集合

单个服务接一个模型时最省事，也最不容易出依赖冲突：

```xml
<!-- 地基 -->
<dependency>
  <groupId>com.agentsflex</groupId>
  <artifactId>agents-flex-core</artifactId>
  <version>&lt;VERSION&gt;</version>
</dependency>
<!-- 你实际用的那一个模型适配 -->
<dependency>
  <groupId>com.agentsflex</groupId>
  <artifactId>agents-flex-chat-openai</artifactId>
  <version>&lt;VERSION&gt;</version>
</dependency>
```

**引完立刻验一次**：

```bash
mvn -q dependency:tree -Dincludes=com.agentsflex
mvn -q -o compile   # 离线编译，能快速暴露本地库缺失
```

---

## 第三步：最小可运行（对话）

任何一个 OpenAI 兼容端点，构造对话模型只需要四要素：**端点、供应商标识、模型名、API Key**。

```java
import com.agentsflex.core.model.chat.ChatModel;
import com.agentsflex.model.chat.openai.OpenAIChatConfig;

public class MinimalChat {
    public static void main(String[] args) {
        ChatModel chatModel = OpenAIChatConfig.builder()
                .endpoint(System.getenv("LLM_ENDPOINT"))   // 例如自建网关或厂商端点
                .provider(System.getenv().getOrDefault("LLM_PROVIDER", "OpenAI"))
                .model(System.getenv().getOrDefault("LLM_MODEL", "gpt-4o-mini"))
                .apiKey(System.getenv("LLM_API_KEY"))      // 绝不写进代码
                .buildModel();

        System.out.println(chatModel.chat("用一句话说明这个框架是干什么的"));
    }
}
```

**三条纪律**：

1. 密钥走环境变量。示例里也不写死。
2. `endpoint` 不要带多余路径，多数兼容实现要求的是基址而不是完整补全地址。
3. 第一次跑通先不看流式。同步跑通再动流式，能把"配置问题"和"流式解析问题"分开。

---

## 第四步：流式输出

同一套提示词与参数机制，只是换成带监听器的调用方式：

```java
import com.agentsflex.core.model.chat.StreamResponseListener;
import com.agentsflex.core.model.chat.response.AiMessageResponse;
import com.agentsflex.core.model.client.StreamContext;

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

**流式最容易出的三类问题**（详见排错文件）：

- 把每次回调当成完整回答 → 拼接顺序错、内容重复
- 结束条件判断错 → 流结束了还在等，或提前收尾
- 同步用的是拼好的提示词，流式用了另一套 → 两边行为不一致

---

## 第五步：Tool Calling（注解声明式）

### 5.1 把业务方法暴露成工具

```java
import com.agentsflex.core.model.chat.tool.annotation.ToolDef;
import com.agentsflex.core.model.chat.tool.annotation.ToolParam;

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

### 5.2 挂到提示词上，走完一次工具调用

```java
import com.agentsflex.core.prompt.SimplePrompt;
import com.agentsflex.core.model.chat.response.AiMessageResponse;

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

### 5.3 编程式构建工具

工具来自运行时配置、插件系统或工作流节点时，用构造器拼装，而不是写注解：

```java
// 结构示意：名、描述、参数 schema、执行体
Tool dynamicTool = Tool.builder()
        .name("tenant_lookup")
        .description("按租户名查询租户 ID")
        .addParameter("tenantName", "string", "租户名称", true)
        .handler(args -> tenantService.findIdByName((String) args.get("tenantName")))
        .build();
```

> 校验：`Tool.builder()` 的具体方法名以你引入的版本为准。编程式构建的价值在于
> **工具集合可以来自数据库或配置中心**，代价是描述质量没人替你保证。

---

## 第六步：工具组（按输入动态挂载）

工具多起来之后，全量挂载会同时推高成本和错误率。工具组让"只有相关的工具才进请求体"：

```java
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

**工具上百个时的替代方案**：用渐进式工具发现模块，让模型先检索再调用，而不是靠关键词命中。

---

## 第七步：拦截器

### 7.1 改参数（在 `proceed` 之前）

```java
ChatInterceptor auditInterceptor = new ChatInterceptor() {
    @Override
    public AiMessageResponse intercept(BaseChatModel<?> model, ChatContext context, SyncChain chain) {
        context.getOptions().setTemperature(0.2f);              // 影响最终请求参数
        context.getRequestSpec().addHeader("X-Tenant", tenantId); // 影响请求头
        return chain.proceed(model, context);
    }
};
```

**注意请求规格对象只含 URL、Header、重试配置，不暴露 Body**。想改请求内容，只能走提示词、
参数这类结构化信息。这是设计约束，不是缺陷。

### 7.2 条件激活 + 顺序

```java
chatModel.addInterceptorRegistration(
        ChatInterceptorRegistration.builder("premium-audit", new AuditChatInterceptor())
                .matcher(context -> "premium".equals(context.getAttribute("plan")))
                .order(0)
                .build()
);
```

- 条件是**运行到该注册项时**求值的，所以能读到前面拦截器改过的上下文
- order 升序稳定排序，相同 order 保持注册顺序
- 默认值只是推荐：可观测 `-1000`、普通 `0`、请求准备（工具组解析）`1000`
- 要给**之后创建的所有**模型挂条件拦截器，用全局注册入口

---

## 第八步：Spring Boot 接入

```xml
<dependency>
    <groupId>com.agentsflex</groupId>
    <artifactId>agents-flex-spring-boot-starter</artifactId>
    <version>&lt;VERSION&gt;</version>
</dependency>
```

自动配置覆盖范围（核对时点）：

| 类别 | 已覆盖 |
|---|---|
| 对话模型 | OpenAI、Qwen、Ollama、DeepSeek |
| 向量存储 | 阿里云、Chroma、Elasticsearch、OpenSearch、腾讯云 |

**配置键名不要照抄二手博客**。可靠做法是直接查你引的那个版本：

```bash
# 找到 starter jar
mvn -q dependency:build-classpath -Dmdep.outputFile=cp.txt
# 或在本地库里定位
#   ~/.m2/repository/com/agentsflex/agents-flex-spring-boot-starter/<VERSION>/
# 解压后读自动配置元数据（键名、类型、默认值都在里面）
#   META-INF/spring-configuration-metadata.json
```

**未覆盖的模型/向量库不等于不能用** —— 手动构造实例即可，只是没有自动配置帮忙读配置项。

---

## 第九步：MCP 接入

支持三类传输方式：**stdio**、**http-sse**、**http-stream**。加载方式是配置文件
（`mcp-servers.json`），然后把 MCP 工具转成本框架的工具，对上层业务就是普通 `Tool`。

接入步骤：

1. **确认 JDK 17+**（这个模块的硬要求）
2. 按你的传输方式准备 MCP Server：本地进程用 stdio，远程用 http-sse / http-stream
3. 在配置里声明 server 列表（**字段结构以上游该版本的说明为准**，各版本调整过）
4. 用客户端管理器建立连接
5. 把拉到的远程工具挂到提示词上 —— 从这一步开始，和本地工具没有区别

**排错要点**：

- stdio 方式启动失败，八成是**命令路径或工作目录**问题，先在 shell 里手跑一遍那条命令
- 远程方式连不上，先分清是**网络不通**还是**协议不对**（sse 与 stream 不是一回事）
- 工具名冲突：远程工具与本地工具重名时行为取决于实现，**先做一次名字盘点**

---

## 第十步：Skills 接入

Skills 是**基于文件系统**的技能加载 + 渐进式披露机制，用于封装重复性的专业任务
（代码审查、文档生成、文件处理、本地知识检索这类）。

落地要点：

1. 规划目录结构：一个技能一个目录，配一份说明文件（具体约定以上游该版本说明为准）
2. 用技能工具指向技能根目录，让它按需加载
3. 技能需要跑脚本时，**用沙箱模块隔离执行**，不要让模型直接在宿主机上跑任意脚本
   —— 沙箱模块有基于不同运行时实现的两种方案，按你有哪种运行时选

**安全底线**：Skills 会给模型"读说明 + 执行"的能力。生产环境务必配沙箱，且限制可访问的
目录范围；不要用管理员账号跑。

---

## 第十一步：智能问数（Text2SQL）

这个模块提供的能力组合是：**数据源列表、表字段查询、SQL 执行**三类工具，加一层安全约束。

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

**红线**：永远不要给这个模块一个可写账号。生成 SQL 的模型可能被提示词注入，只读 + 校验 +
限额是三重防线，缺一层都不行。

---

## 第十二步：RAG 与向量库

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

**验证召回是否真的工作**：拿一个答案明确的问题，把检索到的片段打印出来看。**只看最终回答
判断不出来** —— 模型可能靠自己的知识答对了，掩盖了检索为空的事实。

---

## 第十三步：Agent 运行时接入

出现下面任意一条才需要：多轮工具调用、工具审批、挂起恢复、重启不丢状态。

落地四步：

1. **先引运行层，再引存储层**。存储层是 JDBC 或 Redis 实现，两者选一，按现有运维栈定。
2. **初始化持久化表/结构**（JDBC 方式需要建表，脚本以上游该版本为准）。
3. **接审批环节**。哪些工具需要人工确认要显式列出来 —— 默认全放开等于没有审批。
4. **测重启恢复**：跑到一半把服务停掉，重启后确认能从快照恢复，且版本 CAS 没有冲突。

**并发注意**：版本 CAS 的意义是防并发覆盖。同一会话被两个请求同时推进时会有一方失败，
这是**正确行为**，不是 bug；上层要处理这个失败（提示重试或加会话级锁）。

---

## 第十四步：上线前配置清单

| 项 | 检查点 |
|---|---|
| 密钥 | 全部走环境变量或配置中心，仓库里 grep 不到明文 |
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

排查问题时不要在原工程上改。建一个最小工程，只引 `core` + 一个模型适配，跑通"一句问答"，
然后**一次只加一样**：加流式 → 加一个工具 → 加一个工具组 → 加一个拦截器。
哪一步坏了，问题就在那一步。这比在复杂工程里猜快十倍。
