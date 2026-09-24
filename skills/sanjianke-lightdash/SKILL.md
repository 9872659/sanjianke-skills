---
name: sanjianke-lightdash
slug: sanjianke-lightdash
displayName: 三剪客 · BI 即代码分析平台
description: "Lightdash：把 BI 当代码管——指标、维度、图表、看板都以文件形式进 Git，用 CLI 在本地预览、在 CI 里校验、走 PR 评审后发布，权限与业务口径统一收在语义层。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Lightdash 的部署与 CLI 用法：Cloud 与自托管两种路径、Docker Compose 与 Helm 部署、CLI 安装登录、deploy / preview / validate / generate / lint / sql / warehouse-catalog 等核心命令，以及 dbt 依赖、项目上下文、密钥丢失、环境变量等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - BI

---

# 三剪客 · BI 即代码分析平台

传统 BI 最痛的三个点：指标口径各写各的、看板改动没有评审记录、数据权限靠人肉管。Lightdash 的解法是把这些东西全部写成文件、进 Git，用跟代码一样的流程发布——本地预览、CI 校验、PR 评审、合并上线。

它的核心是**语义层**（context layer，也叫 semantic layer）：在 dbt 项目或 Lightdash 自己的 YAML 里定义指标、维度、join、描述、缓存与权限规则，之后看板、AI 问答、数据应用、嵌入式分析全都从这一层取数。换句话说，改一次口径，所有消费方一起生效。

**上游项目**：`lightdash`　**仓库**：https://github.com/lightdash/lightdash

> 关于名称与版本：官方文档会同时出现 "Lightdash Cloud"（托管服务）与自托管两条路线。CLI 命令与选项在版本间会增删（例如官方文档已明确说明 `PARTIAL_COMPILATION_ENABLED` 环境变量不再被支持），**具体命令与参数以官方 CLI 参考页和你本机 `lightdash --help` 为准**。

## 什么时候用 / 不用

**用它**：

- "指标口径总对不上，同一份数据三个部门三个数。"——指标与维度在语义层定义一次，所有看板与查询共用。
- "看板改动没人评审，改坏了不知道谁动的。"——内容以文件形式存在（YAML / 内容即代码），可以走 PR 评审与 CI 校验。
- "我们有 dbt 项目，想把 dbt 模型变成可探索的 BI 表格。"——在 dbt 模型上打标签，CLI 生成 YAML，按标签决定哪些表出现在 BI 里。
- "想在生产环境变更前先在本地预览一下。"——`lightdash preview` 起一个临时预览项目，验证完再 `deploy`。
- "要在 CI 里拦住坏的指标定义。"——`lightdash validate` / `lightdash lint` 可以在流水线里跑并返回非零退出码。
- "需要把人挡在敏感字段外面，而且不同客户看到的数据要不一样。"——行级权限、用户属性、面向客户的权限都建在语义层里，嵌入式分析也复用这套。
- "想让 AI 助手基于可信口径回答问题，而不是瞎猜表结构。"——官方提供 agent skills 与 MCP server，让编码助手在语义层上做变更。

**不要用它**：

- **没有数据仓库、数据还在业务库里零散放着**——它连的是分析型仓库（BigQuery、Snowflake、Redshift、Databricks、Postgres、Trino、ClickHouse 等），上游没有建模好的仓库就得先解决仓库问题。
- **没有 dbt 且不打算用**——虽然支持直接用 Lightdash YAML 指向仓库，但绝大多数用法与文档都围绕 dbt 项目展开，没有 dbt 会丢掉不少便利。
- **只想要一次性的图表导出或临时 SQL 查询**——直接用仓库客户端或 notebook 更快，不必上平台。
- **团队里没人管基础设施，也不想用托管服务**——自托管要管 K8s 或 Docker、元数据库、密钥、升级；不想管就走 Cloud。
- **要的是 Excel 式自由版式的复杂报表与套打打印**——这类固定版式报表不是它的定位（那是 JimuReport 一类的活）。
- **不需要治理、只想拖拽看图**——轻量看图工具上手更快，它的价值在口径治理与代码化流程，用不上就是负担。

## 安装

### 方式一：Cloud（最快路径）

注册官方托管服务即可获得工作区，不用自己运维，官方推荐的团队路径。适合想直接用 AI 助手、数据应用、定时投递、嵌入式分析等能力的场景。

### 方式二：自托管 · Docker Compose（本地概念验证）

前置：Docker 与 Docker Compose。

```bash
# 1. 取代码
git clone https://github.com/lightdash/lightdash
cd lightdash

# 2. 配 .env（关键项如下，其余按你的环境填）
#    PGHOST=db
#    PGPORT=5432
#    PGUSER=<用户名>
#    PGPASSWORD=<密码>
#    PGDATABASE=postgres
#    DBT_DEMO_DIR=<本地 dbt 项目路径>

# 3. 起容器（LIGHTDASH_SECRET 与 PGPASSWORD 必须设置）
export LIGHTDASH_SECRET="<换成一个你自己的高强度随机串>"
export PGPASSWORD="<元数据库密码>"
docker compose -f docker-compose.yml --env-file .env up --detach --remove-orphans
```

`LIGHTDASH_SECRET` 用于加密落库的数据，**丢了就再也解不开库里的加密数据**，务必提前用密钥管理服务存好。Windows 上如果报 `Error response from daemon: i/o timeout`，按官方说明在 Docker 设置里打开 "Expose daemon on tcp://localhost:2375 without TLS"。

### 方式三：自托管 · Kubernetes（生产）

用官方维护的 Helm chart 部署，前置需要可用的 K8s 集群、`kubectl` 与 `helm`。官方建议生产上线前先过一遍生产部署检查清单。企业版功能在自托管上需要 License Key。

### 方式四：CLI（把 BI 当代码用的入口）

CLI 依赖 Node、npm，以及 dbt Core 或 dbt Cloud 的 CLI（必须能在 `dbt` 命令下调用）。

```bash
# npm 全局安装
npm install -g @lightdash/cli

# macOS 推荐 Homebrew 安装（不用单独装 Node）
# 具体 formula 名以官方安装文档为准

# 登录并绑定实例
lightdash login https://your-instance.lightdash.cloud

# 验证
lightdash --version
lightdash --help
```

Windows 官方建议装在 WSL 里（CLI、Node、dbt 的行为与 Linux/macOS 一致）；不用 WSL 时按官方 PowerShell 说明安装。

## 常用操作

以下命令与选项取自官方 CLI 参考文档；全局选项为 `--version` / `--help` / `--verbose`，完整选项请用 `lightdash <命令> -h` 查。

**1. 登录与选定项目（大多数命令的前置）**

```bash
lightdash login https://app.lightdash.cloud
lightdash login https://custom.lightdash.domain --token <个人访问令牌>
lightdash config list-projects            # 列出组织内的非预览项目
lightdash config set-project --name "Healthcare Demo"
lightdash config get-project              # 确认当前生效的项目
```

**2. 编译并部署语义层变更**

```bash
lightdash compile                 # 用本地文件编译（dbt 项目会先跑 dbt compile）
lightdash deploy                  # 编译并部署到当前项目
lightdash deploy --create         # 创建新项目（dbt Cloud CLI 下仓库凭证需事后在设置页手动补）
lightdash compile -s accounts     # 只编译指定 dbt 模型（以及与之 join 的模型）
```

**3. 在本地起临时预览项目（改动前先看效果）**

```bash
lightdash preview                          # 临时预览项目，按任意键结束
lightdash start-preview --name my-preview  # 常驻预览，显式 stop
lightdash stop-preview                     # 关掉开着的预览项目
```

`preview` / `start-preview` 支持 dbt 的节点选择与标志（`--select`、`--exclude`、`--defer`、`--state` 等），也可以 `--skip-dbt-compile` 复用已有的 `target/manifest.json`。

**4. 校验：本地文件 vs 线上内容**

```bash
lightdash validate                # 用本地项目校验当前项目里的内容
lightdash validate -h             # 查看该命令支持的全部选项
lightdash lint                    # 按 JSON Schema 校验内容即代码文件（模型/图表/看板）
lightdash lint --path ./lightdash/charts/my-chart.yml
lightdash lint --format json      # SARIF 格式，便于接 CI
```

`lint` 里 schema 校验失败会以非零退出码结束（可以卡 CI），警告不影响退出码。

**5. 从 dbt 模型生成 YAML 骨架**

```bash
lightdash generate                                  # 给选中的模型生成/更新 schema.yml
lightdash generate -s mymodel                       # 只针对某个模型
lightdash dbt run                                   # 先跑 dbt，再生成 YAML
```

**6. 直接对仓库跑一句 SQL**

```bash
lightdash sql "SELECT * FROM users LIMIT 100" -o users.csv
lightdash sql "SELECT customer_id, SUM(amount) FROM orders GROUP BY 1" -o revenue.csv --limit 1000
```

用的是当前项目的仓库凭证，结果导出到 CSV。默认每页 500 行，最大 5000，可用 `--page-size` 调。

**7. 探索仓库结构（给脚本和 Agent 用）**

```bash
lightdash warehouse-catalog
lightdash warehouse-catalog --database jaffle --schema analytics
lightdash warehouse-catalog --database jaffle --schema analytics --table orders --include-fields
lightdash warehouse-catalog --refresh          # 仓库加了新表，刷新服务端缓存
lightdash warehouse-catalog --json             # 机器可读输出，便于管道处理
```

这个命令走服务端缓存的仓库元数据，不需要本地 `profiles.yml`，也不返回凭证信息。

**8. 内容即代码的下载 / 上传 / 重命名**

```bash
lightdash download                              # 把看板与图表下载成本地文件
lightdash upload                                # 把本地内容即代码上传回项目
lightdash rename --type field --from num_users --to count_distinct_user_id
lightdash rename --type model --from users_mart_v1 --to users --dry-run
lightdash slug-update --dry-run --from copy-of-orders --to orders
```

`rename` 会全量替换字段 / 模型引用（图表字段、看板筛选、自定义指标都会跟着改）；涉及线上内容时先用 `--dry-run` 看清改动范围。

**9. 让编码助手接上语义层**

```bash
lightdash install-skills        # 安装官方 agent skills
lightdash preview               # 改完先预览
lightdash validate              # 再校验，通过才提交 PR
```

**10. CI 里非交互执行**

```bash
CI=true lightdash deploy
CI=true lightdash validate
```

设了 `CI=true` 会静默所有交互式提示（确认框、项目选择器），缺必填输入时直接按默认值走或报错。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 跑任何命令都报找不到 `dbt` / dbt 相关错误 | CLI 依赖 dbt Core 或 dbt Cloud 的 CLI，必须能在 `dbt` 命令下调起来 | 先确认 `dbt --version` 能跑；用 dbt Cloud CLI 时注意部分命令（`generate`、`preview`、`start-preview`）依赖活动项目的仓库凭证 |
| 报 "No active Lightdash project" / 命令作用在错的项目上 | CLI 有"当前项目"上下文，没设过或设错了 | `lightdash config get-project` 先看，再 `lightdash config set-project` 设定；CI 里用 `LIGHTDASH_PROJECT` 环境变量指定（注意 `--project` 优先级高于它） |
| 连接报 `unable to get local issuer certificate` | 企业网络 / 代理下的证书链问题（官方在 Windows 部分列了这个坑） | 按官方 Windows 排错章节处理证书信任；代理环境可用 `LIGHTDASH_PROXY_AUTHORIZATION` 提供代理认证头 |
| 换了个终端就提示 `lightdash: command not found` | npm 全局 bin 目录没进那个终端的 PATH（官方把它列为常见问题） | 检查各终端的 PATH 与 npm prefix；Windows 上官方建议改用 WSL |
| `lightdash deploy --create` 建出来的新项目连不上仓库 | dbt Cloud CLI 不暴露凭证，新建（非预览）项目时仓库凭证不会自动填充 | 项目建好后到项目设置页手动补齐仓库凭证 |
| 登录用的浏览器回调一直不完成，或交互式选择器在 Agent / 编辑器里没反应 | OAuth 回调被拦，或运行环境没有交互式终端（官方明确说 Cursor / VS Code 的 Agent 里交互提示不工作） | 改用个人访问令牌登录（`lightdash login <url> --token <token>`）；CI 里设 `CI=true` 并全部用环境变量传参 |
| 自托管后重启容器，数据读不出来了 | `LIGHTDASH_SECRET` 变了。它是加密落库数据的密钥，**丢失或更换后旧数据无法解密** | 把它当成不可丢的密钥管理：写进密钥服务、备份、部署时用同一份；已经在跑的实例不要随手换 |
| 本地预览里的模型不完整，比生产少几张表 | `--no-combine` 会跳过拉取上游项目的 manifest，只预览本地仓库的模型 | 需要看到项目其它 dbt 来源的模型时，保持默认（会拉取并合并上游 manifest），或用 `--combine-manifest` 显式提供 manifest 路径 / URL |
| 配了 `PARTIAL_COMPILATION_ENABLED` 但行为没变 | 该环境变量官方已明确**不再支持**，不再控制服务端或 CLI 行为 | 从部署配置里删掉它；需要严格编译就用 `--no-partial-compilation`（支持 `compile` / `validate` / `deploy` / `preview` / `start-preview`） |
| PR 预览里改了模型却还是查到生产的老数据 | 给预览流程传了 `--favor-state`，会让选中的节点优先用生产关系，而不是刚构建的开发关系 | 预览工作流**不要**传 `--favor-state`（官方明确警告过） |
| `--select 'tag:lightdash,state:modified+'` 选出来的模型少得离谱 | dbt 的 `--select` 里逗号语义是 AND 不是 OR | 想要 OR 就用空格分隔多个选择器：`--select tag:lightdash state:modified+` |
| Windows 上 Docker Compose 起不来，报 `i/o timeout` | Docker Desktop 没开对应选项（官方文档里点名了这个错误） | 到 Docker 设置 → General，勾选 "Expose daemon on tcp://localhost:2375 without TLS" |
| `lightdash apps` 相关命令报 Node 版本不够 | 数据应用的脚手架会本地装 npm 包并生成前端组件，要求 Node.js 20+ | 升级 Node 到 20 以上再跑 `lightdash apps create` |
| 用 `--token` 传了 API Key，事后发现它留在 shell 历史里 | `--token` 会泄漏到命令历史（官方文档明确提示） | 优先用 `lightdash login` 或 `LIGHTDASH_API_KEY` 环境变量，只在无法避免时用 `--token` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | CLI 与 Lightdash 服务通信；服务端连数据仓库取数；Cloud 部署全程依赖网络 |
| 读取文件 | 是 | 读取本地 dbt 项目 / Lightdash YAML / 内容即代码文件；`sql` 命令写 CSV；Docker 部署要读 `.env` |
| 写入文件 | 是 | `generate` 写 schema.yml、`download` 写内容文件、`sql -o` 写 CSV；自托管还要写元数据库 |
| 凭证 | 是 | 需要 Lightdash 的 API Key / 登录态；数据仓库凭证（用 `lightdash login` 或 `LIGHTDASH_API_KEY`，不要用会留痕的 `--token`）；自托管的 `LIGHTDASH_SECRET` 与元数据库密码 |
| 子进程 / 后台常驻 | 是 | CLI 会调用 `dbt` 子进程；自托管时 Lightdash 服务、元数据库、调度 worker 都是常驻进程 |
| 读取数据仓库数据 | 是 | 语义层编译、`sql` 命令、看板与 AI 问答都要查询你的仓库，权限取决于所配的仓库账号 |
| 对外暴露分析界面 | 是 | 自托管要把服务开放给团队访问；嵌入到自有产品时注意行级权限与用户属性配置 |

## 触发场景

- "我们的指标口径对不上，想找个能把口径统一管起来的 BI。"
- "看板修改想走 PR 评审，能不能像代码一样管。"
- "我们有 dbt 项目，怎么让它变成业务能自助探索的看板。"
- "上线前想在本地先预览一下这次指标改动。"
- "CI 里怎么校验指标定义有没有写错。"
- "自托管的 Lightdash 怎么用 Docker 起一套。"
- "想让 AI 助手基于我们定义好的口径回答数据问题。"
- "要把看板嵌到我们自己的产品里，还要按客户隔离数据。"

## 能力边界

**覆盖**：

- **语义层 / 指标层**：指标、维度、join、描述、缓存、访问规则统一定义；支持在 dbt 项目上定义，也支持 Lightdash YAML 直接指向仓库
- **BI 即代码**：内容（模型、图表、看板）以文件形式存在，可下载 / 上传，可走 Git、PR 与 CI 流程
- **CLI**：登录与项目上下文管理、`compile` / `deploy` / `preview` / `start-preview` / `stop-preview` / `validate` / `lint` / `generate` / `dbt run` / `download` / `upload` / `rename` / `slug-update` / `sql` / `warehouse-catalog` / `diagnostics` / 预聚合审计等
- **仓库连接**：官方列出 BigQuery、Snowflake、Redshift、Databricks、Postgres、Trino、ClickHouse 等适配
- **权限与治理**：行级安全、用户属性、面向客户的权限，嵌入场景复用同一套
- **AI 与扩展**：对话式分析、Data Apps（数据应用）、agent skills、MCP server、SDK 与嵌入式分析
- **部署形态**：Cloud 托管；自托管支持 Docker Compose（概念验证）与 Kubernetes（Helm，生产），企业功能需 License Key

**不覆盖**：

- **数据仓库本身的建设与运维**——不建仓、不做 ETL、不做数据质量校验
- **替代 dbt 做数据建模**——它是 dbt 的消费方与协作层，转换逻辑仍在 dbt 里
- **Excel 式自由版式报表与套打打印**——不做固定版式单据、发票套打这类需求
- **仪表盘之外的通用数据采集**——它不是爬虫，也不做业务系统的数据录入
- **仓库账号的权限体系**——行级安全在 Lightdash 层实现，底层仓库账号该有的最小权限仍要你自己配
- **自托管的运维自动化**——K8s 集群、元数据库备份、升级窗口都要你自己负责（或走 Cloud）
- **数据合规判定**——把什么数据接进来、谁能看、留多久，需要按你所在行业与法规自行把关

## 依赖条件

- **Cloud 路径**：只需要浏览器与账号，无需自建基础设施
- **自托管 Docker 路径**：Docker + Docker Compose；一个 PostgreSQL 作为元数据库（与你的数据仓库是两回事）
- **自托管 K8s 路径**：可用的 Kubernetes 集群、`kubectl`、`helm`；生产上线先过官方检查清单
- **CLI 路径**：Node.js 与 npm；以及 dbt Core 或 dbt Cloud CLI（必须在 `dbt` 命令下可用）
- **数据应用相关命令**：Node.js 20+ 与 npm
- **必填密钥**：`LIGHTDASH_SECRET`（加密落库数据，丢了不可恢复）、元数据库 `PGPASSWORD`；CI 中常用 `LIGHTDASH_API_KEY`、`LIGHTDASH_URL`、`LIGHTDASH_PROJECT`
- **企业功能**：自托管上需要 License Key

## 已知限制

1. CLI 强依赖 dbt（Core 或 Cloud CLI），没有 dbt 的环境下大部分命令不可用。
2. 部分命令依赖"当前活动项目"上下文，项目选错会静默作用到错的对象上。
3. 用 dbt Cloud CLI 时有明确的能力缺口：`generate` / `preview` / `start-preview` 依赖活动项目的仓库凭证；`deploy --create` 建的新项目仓库凭证为空，需事后在设置页补。
4. 官方文档明确说明 `PARTIAL_COMPILATION_ENABLED` 已不再支持，升级时要从配置里清掉旧变量。
5. 全量 `rename` 是跨内容的查找替换，影响面大，务必先 `--dry-run`。
6. `--token` 会把 API Key 写进 shell 历史，属于官方点名的用法风险。
7. 命令与选项随版本增删较快，老教程里的参数可能已经变化或废弃。
8. 自托管的 `LIGHTDASH_SECRET` 一旦丢失，库里加密数据无法解密——这是一个不可逆的单点。
9. Windows 下 CLI 的原生支持体验不如 WSL，官方直接推荐换成 WSL。

## 自检清单

执行前：

- [ ] 确认走 Cloud 还是自托管；自托管要确认元数据库、密钥与升级方案
- [ ] `dbt --version` 能跑通，且 dbt 项目路径 / profiles 路径明确（必要时用 `--project-dir`、`--profiles-dir`）
- [ ] `lightdash config get-project` 确认当前项目是对的，避免改到生产
- [ ] CI 场景用 `LIGHTDASH_API_KEY` / `LIGHTDASH_URL` / `LIGHTDASH_PROJECT` + `CI=true`，不依赖交互提示
- [ ] 影响面大的命令（`rename`、`slug-update`、`deploy`）先 `--dry-run` 或先 `preview`
- [ ] 自托管的 `LIGHTDASH_SECRET` 已存入密钥管理并有备份，本次部署沿用同一份
- [ ] 涉及的仓库账号是最小权限，且不会把敏感字段暴露给不该看的人

执行后：

- [ ] `lightdash validate` / `lightdash lint` 通过（lint 非零退出码表示 schema 校验失败）
- [ ] 变更后的指标在看板与 AI 问答里取到的数一致，口径没跑偏
- [ ] 预览项目用完已 `stop-preview`，没有遗留临时项目
- [ ] 检查日志与命令行历史里没有泄漏 API Key 或仓库凭证
- [ ] 自托管实例重启后数据仍可访问（验证 `LIGHTDASH_SECRET` 没被换）

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/lightdash/lightdash | 上游仓库（安装与完整文档以它为准） |
| https://docs.lightdash.com/workflow/cli/reference | 官方 CLI 参考：全部命令、选项、环境变量 |
| https://docs.lightdash.com/workflow/cli/install | 官方 CLI 安装与 Windows 排错 |
| https://docs.lightdash.com/self-host/self-host-lightdash-docker-compose | 官方 Docker Compose 自托管步骤 |
| https://docs.lightdash.com/self-host/self-host-lightdash | 官方 Kubernetes / Helm 自托管步骤 |

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
