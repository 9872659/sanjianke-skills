---
name: sanjianke-mindoc
slug: sanjianke-mindoc
displayName: 三剪客 · 团队文档管理系统
description: "MinDoc：Go 写的自托管文档管理系统，面向团队做接口文档、项目文档与知识库，支持多级目录、成员权限、私有项目 Token 访问与多格式导出。本文讲清它的编译与部署、conf/app.conf 配置、数据库初始化、导出依赖与高频坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "MinDoc 的落地指引：环境与 Go 版本要求、二进制与 Docker 两种部署、docker-compose 卷映射、conf/app.conf 真实配置键、mindoc install 初始化与 install.lock、Zip/Docx 导入与 PDF/EPUB/MOBI/DOCX/Markdown 导出、MySQL utf8mb4 字符集、二级目录部署与 Nginx 反代，以及默认密码、相对路径、CentOS 编译等高频坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
  - 文档管理
---

# 三剪客 · 团队文档管理系统

团队文档最尴尬的状态是"东西都写了，但谁也不知道在哪"。用一个代码仓库放 Markdown 对工程师友好，但产品、测试、运营同事用不了；用在线文档平台又常常卡在数据要放在自己服务器上。MinDoc 走的是中间路线：一个自托管的、按项目组织的文档系统，浏览器里写 Markdown 或富文本，带成员权限、私有项目和导出。

它最初是为了解决"接口文档该放哪儿"这件事做的，因此**按项目（project）组织、按文档树组织**是它的基本模型，适合接口文档、数据库字典、项目说明这类结构化文档，不适合当成博客或 Wiki 广场。

**上游项目**：`MinDoc`　**仓库**：https://github.com/mindoc-org/mindoc

## 什么时候用 / 不用

**用它**：

- "我们要一个能自己部署的团队文档站，数据必须留在内网。"——单二进制 + 单配置文件，可完全离线运行。
- "需要按项目分库、再按目录分章节，还要能控制谁能看哪个项目。"——内置项目管理、成员与角色权限、私有项目 Token 访问。
- "文档要能一键导出成 PDF 发给客户。"——支持 PDF / EPUB / MOBI / Word / Markdown 导出。
- "想把现成的 Word 文档或整包资料导进来。"——支持 Zip / Docx 导入项目。
- "团队不想学 Markdown，也想用富文本。"——同时提供 Markdown 与富文本编辑器。
- "想把文档接进 AI 工作流里让模型读。"——内置可选的 MCP 服务端能力。

**不要用它**：

- **想要开箱即用、零运维**——它是需要自己准备数据库、配置文件、初始化命令和进程守护的服务端程序，没有 SaaS 版可用。
- **只想要一个静态博客或单页文档站**——为几篇文档维护一套数据库 + 后台不划算，静态站点生成器更合适。
- **需要多人实时协同编辑**——它是"保存式"编辑器，不具备多人同时编辑同一篇文档的实时协作能力。
- **需要代码与文档同仓库、随提交自动发布**——它不集成代码托管，文档更新走它的后台界面。
- **需要严格的对外文档站 SEO、自定义域名与 CDN 深度定制**——官方明确说明它不支持绑定域名，要靠反向代理或独占端口。

## 安装

### 方式一：下载 release 二进制（推荐给非 Go 用户）

从 release 页下载对应平台的包，官方 Linux 文档里给的文件名形如 `mindoc_linux_amd64.tar.gz` 或 `mindoc_linux_amd64.zip`。注意 CentOS 一类的老系统要用 musl 编译版本（官方在 release 说明里明确：常规 gcc 编译版 **CentOS 不建议用**，musl 版 **CentOS 推荐用**）。

```bash
# 解压
tar -xzvf mindoc_linux_amd64.tar.gz
# 或 unzip mindoc_linux_amd64.zip

# 准备 MySQL 库（用 MySQL 时字符集必须 utf8mb4）
mysql -uroot -p -e "CREATE DATABASE mindoc_db DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_general_ci;"

# 生成配置文件（conf 目录下没有 app.conf 时，从模板复制一份）
cp conf/app.conf.example conf/app.conf

# 编辑 conf/app.conf，填好 db_* 配置

# 初始化数据库表结构（必须执行，成功后会生成 install.lock）
./mindoc_linux_amd64 install

# 赋予执行权限并启动
chmod +x mindoc_linux_amd64
./mindoc_linux_amd64
```

启动后浏览器访问 `http://localhost:8181`。默认会初始化一个超级管理员：账号 `admin`、密码 `123456`，**登录后第一件事就是改密码**。

### 方式二：从源码编译

官方要求 Go 版本不低于 1.23.0，且需要支持 CGO、`go mod`，并依赖 `import _ "time/tzdata"`（推荐 1.23.x）：

```bash
git clone https://github.com/mindoc-org/mindoc.git
cd mindoc
go mod tidy -v
# 编译（sqlite 支持需要 CGO）
go build -ldflags "-w" -o mindoc main.go
# 初始化数据库（执行前先配好 conf/app.conf）
./mindoc install
# 启动
./mindoc
```

开发阶段可以用 `bee run`。

如果目标机是 CentOS 7 这类 GLibC 版本较低的系统，常规编译产物不能直接用，需要用 musl 交叉编译：

```bash
# 先装 musl-gcc：源码编译，或 apt install musl-tools
go mod tidy -v
export GOARCH=amd64
export GOOS=linux
export CC=/usr/local/musl/bin/musl-gcc
export TRAVIS_TAG=temp-musl-v`date +%y%m%d`
go build -v -o mindoc_linux_musl_amd64 -ldflags="-linkmode external -extldflags '-static' -w -X 'github.com/mindoc-org/mindoc/conf.VERSION=$TRAVIS_TAG' -X 'github.com/mindoc-org/mindoc/conf.BUILD_TIME=`date`' -X 'github.com/mindoc-org/mindoc/conf.GO_VERSION=`go version`'"
# 验证
./mindoc_linux_musl_amd64 version
```

### 方式三：Docker

官方 README 给出的公开镜像启动方式（注意卷只挂了 `conf`）：

```bash
# Linux / macOS
export MINDOC=/home/ubuntu/mindoc-docker
docker run -it --name=mindoc --restart=always \
  -v "${MINDOC}/conf":"/mindoc/conf" \
  -p 8181:8181 \
  -e MINDOC_ENABLE_EXPORT=true \
  -d registry.cn-hangzhou.aliyuncs.com/mindoc-org/mindoc:v2.2-beta.2

# Windows
set MINDOC=//d/mindoc
docker run -it --name=mindoc --restart=always -v "%MINDOC%/conf":"/mindoc/conf" -p 8181:8181 -e MINDOC_ENABLE_EXPORT=true -d registry.cn-hangzhou.aliyuncs.com/mindoc-org/mindoc:v2.2-beta.2
```

**只挂 `conf` 会丢数据**。仓库里自带一份 `docker-compose.yml`，把六个目录都映射到宿主机，生产部署更稳妥：

```yaml
# 摘录自仓库 docker-compose.yml 的映射关系，按需改宿主机路径
volumes:
  - /var/www/mindoc/conf:/mindoc/conf
  - /var/www/mindoc/static:/mindoc/static
  - /var/www/mindoc/views:/mindoc/views
  - /var/www/mindoc/uploads:/mindoc/uploads
  - /var/www/mindoc/runtime:/mindoc/runtime
  - /var/www/mindoc/database:/mindoc/database
```

`uploads` 放上传的文件，`database` 在默认 SQLite 模式下放数据库文件——这两个不映射到宿主机，容器一删数据就没了。

```bash
docker-compose up -d          # 启动
docker-compose stop           # 停止
docker-compose restart        # 重启
docker-compose down           # 停止并删除容器
```

容器启动脚本会自动做三件事：把默认配置文件复制成 `conf/app.conf`、执行 `install` 初始化数据库、再启动程序。如果你要自己控制初始化时机，注意这一点。

用 MySQL 时，README 列出的常用环境变量是 `DB_ADAPTER`（默认 sqlite）、`MYSQL_PORT_3306_TCP_ADDR`、`MYSQL_PORT_3306_TCP_PORT`、`MYSQL_INSTANCE_NAME`、`MYSQL_USERNAME`、`MYSQL_PASSWORD`、`HTTP_PORT`、`MINDOC_ENABLE_EXPORT`。另外旧版本镜像（0.12 及以下）用的是 `DB_ADAPTER`/`MYSQL_INSTANCE_NAME`/`CACHE`/`ENABLE_EXPORT`/`BASEURL` 这套老名字，0.12 以上才改成 `MINDOC_*` 前缀。官方文档还提醒：**镜像请使用发布的版本号作为标签，非版本号的镜像是测试镜像**。

## 常用操作

**1. 配置数据库（`conf/app.conf`）**

```ini
# MySQL
db_adapter="${MINDOC_DB_ADAPTER||mysql}"
db_host="${MINDOC_DB_HOST||127.0.0.1}"
db_port="${MINDOC_DB_PORT||3306}"
db_database="${MINDOC_DB_DATABASE||mindoc_db}"
db_username="${MINDOC_DB_USERNAME||root}"
db_password="${MINDOC_DB_PASSWORD||123456}"

# SQLite（默认，无需额外服务）
# db_adapter=sqlite3
# db_database=./database/mindoc.db
```

配置模板里说明支持 MySQL、sqlite3、postgres 三种数据库。用 `${ENV_VAR||默认值}` 这种占位符写法时，**环境变量优先**，因此容器部署可以直接用环境变量覆盖配置文件，不用改文件。

**2. 改监听地址、端口与对外地址**

```ini
httpaddr="${MINDOC_ADDR}"                  # 留空监听所有网卡
httpport="${MINDOC_PORT||8181}"
baseurl="${MINDOC_BASE_URL}"               # 系统完整 URL，不设则从请求头推断
runmode="${MINDOC_RUN_MODE||dev}"          # 生产环境建议 prod
timezone=Asia/Shanghai
```

**3. 调整上传限制与允许的扩展名**

```ini
upload_file_ext=txt|doc|docx|xls|xlsx|ppt|pptx|pdf|7z|rar|jpg|jpeg|png|gif|mp4|webm|avi
upload_file_size=10MB
```

模板注释说明：`upload_file_size` 不填写时默认 1GB，想超过 1GB 必须带单位（TB / GB / MB / KB，不带单位表示字节）。

**4. 开启导出功能**

```ini
enable_export="${MINDOC_ENABLE_EXPORT||false}"
export_process_num="${MINDOC_EXPORT_PROCESS_NUM||1}"       # 1~4，越大越快也越吃资源
export_limit_num="${MINDOC_EXPORT_LIMIT_NUM||5}"
export_queue_limit_num="${MINDOC_EXPORT_QUEUE_LIMIT_NUM||100}"
export_output_path="${MINDOC_EXPORT_OUTPUT_PATH||./runtime/cache}"
```

导出走 URL 形式，项目标识在项目页面上可以看到：

```text
/export/<项目标识>?output=pdf
/export/<项目标识>?output=epub
/export/<项目标识>?output=mobi
/export/<项目标识>?output=docx
/export/<项目标识>?output=markdown
```

注意：PDF / EPUB / MOBI / DOCX 这几类导出依赖外部的 `ebook-convert`（Calibre）。官方镜像的 Dockerfile 里已经内置了 Calibre 并配好相关环境变量；自己手动部署时要另外装，否则日志里会看到 `转换PDF文档失败：exit status 2`。

**5. 初始化与重新初始化数据库**

```bash
./mindoc_linux_amd64 install     # 初始化表结构；已初始化时也用于升级表结构
./mindoc update                  # 旧版本的数据库配置更新命令
```

程序会自动创建表，不需要手工导入 SQL。根目录下的 `install.lock` 是"已初始化"的标记文件：**想重新初始化数据库，删掉它再重启程序即可**。

升级时（多个版本的 release 说明都要求）：替换二进制后执行一次 `install` 更新表结构，看到 `Install Successfully!` 表示成功。升级前务必先备份数据库。

**6. 用后台管理站配置登录与访问策略**

`enable_register`（启用注册）、`enable_anonymous_access`（启用匿名访问）、`enable_captcha`（启用验证码）、`enable_doc_his`（启用文档历史）这些不在 `app.conf` 里，属于可以在管理后台修改的少部分配置。

**7. 开启 MCP 服务端**

```ini
# MCP Server 功能
enable_mcp_server="${MINDOC_ENABLE_MCP_SERVER||true}"
mcp_api_key="${MINDOC_MCP_API_KEY||demo-mcp-api-key}"
```

对接侧（例如 AI 应用里的 MCP 配置）写：

```json
{
  "mindoc": {
    "transport": "streamable_http",
    "url": "http://127.0.0.1:8181/mcp/?api_key=demo-mcp-api-key",
    "headers": {},
    "timeout": 600
  }
}
```

`mcp_api_key` 的示例值就是 `demo-mcp-api-key`，**上线必须改掉**。

**8. 后台常驻与进程守护**

官方 Linux 文档提醒：后台运行方式下服务器重启后不会自动拉起服务，推荐用 supervisor 之类的进程管理工具。Windows 上可以用官方提供的 `mindoc-daemon` 工具，或编译成不带控制台窗口的程序。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 装完一直登不进后台，或者不知道账号密码 | 程序会初始化一个默认超级管理员 | 用 `admin` / `123456` 登录，**登录后立刻改密码**（官方在 README 与文档里都做了强调） |
| 启动报找不到配置文件，或数据库 / 日志 / 会话路径全失效 | `conf/app.conf` 不存在，且配置里大量路径是**相对工作目录**的（如 `./database/mindoc.db`、`./runtime/logs`、`./runtime/session`、`./runtime/cache`） | 先把 `conf/app.conf.example` 复制成 `conf/app.conf`；并且**始终在 MinDoc 根目录**下启动，不要换工作目录 |
| `go build` 报 CGO 或 gcc 相关错误 | 编译 sqlite 支持需要 CGO 和 gcc | 装好 gcc 并保证 `CGO_ENABLED=1`；官方 Dockerfile 里就是这个设置 |
| 在 CentOS 7 上二进制跑不起来 | GLibC 版本太低，常规 gcc 编译产物不可用 | 用 musl 编译版本（release 里的 `mindoc_linux_musl_amd64`），或自己用 musl-gcc 编译 |
| 建库后写入中文乱码或建表失败 | MySQL 字符集不对 | 建库时显式指定 `DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_general_ci`；官方明确要求 MySQL 编码必须是 `utf8mb4_general_ci` |
| 导出 PDF 失败，日志写 `转换PDF文档失败：exit status 2` | 缺少 `ebook-convert`（Calibre） | 自行安装 Calibre，或改用内置 Calibre 的官方镜像；注意早期基于 Alpine 的镜像不支持 PDF 导出 |
| 容器删了以后上传的文件和数据库都没了 | `uploads` / `database` 目录没映射到宿主机 | 用仓库自带的 compose 文件，把六个卷全部映射出去；`conf` 单独挂载是不够的 |
| 用反代 + 二级目录（如 `/docs`）时所有链接都打不开 | 应用不知道自己在子路径下，且前端脚本里有写死的绝对路径 | 按官方说明改 `conf/app.conf` 的 `baseurl="/yourpath"`，并改 `static/js/kancloud.js` 里两处评论接口 URL 拼接，Nginx 侧加 `rewrite ^/yourpath/(.*) /$1 break;` |
| 反代后登录状态丢失、跳转地址是内网 IP | 反代没有传递原始请求头 | Nginx 里补 `proxy_set_header X-Forwarded-For $remote_addr;`、`proxy_set_header Host $http_host;`、`proxy_set_header X-Forwarded-Proto $scheme;`（HTTPS 场景若后端拿到的不是 https 需手动设成 https） |
| 想绑域名却发现配置里没有域名项 | 官方说明 MinDoc 不支持绑定域名 | 让 MinDoc 独占 80 端口，或用 Nginx 反向代理对外提供域名 |
| 升级后后台某些页面空白，甚至数据异常 | 升级涉及数据库表结构变更 | 升级后必须执行一次 `install` 更新表结构；**升级前先备份数据库**，社区里出现过升级导致数据异常的情况 |
| 想彻底重来一遍安装流程却不生效 | 根目录存在 `install.lock` 标记 | 删掉 `install.lock` 再重启程序，程序会重新走初始化 |
| 服务器上没装 Go 时启动报时区相关错误 | 旧版本需要外部时区库，靠 `ZONEINFO` 环境变量指向 `lib/time/zoneinfo.zip` 的绝对路径 | 设置 `ZONEINFO` 环境变量；Windows 上若仍失败，可把该文件放到 `C:\go\lib\time\zoneinfo.zip`。注意新版 README 已把这条说明划掉，新版本可能已内置时区数据，优先按新版本说明处理 |
| 邮件配置写完不生效 | 配置模板里的邮件项本身有笔误（`smtp_host` 与 `smtp_port` 两行结尾多了一个引号），且发送人键名拼写为 `form_user_name` 而非 `from_user_name` | 照模板原样写并逐字核对；可以先看日志里 SMTP 连接报错再定位 |
| 老镜像里配的环境变量不生效 | 0.12 及以下版本用的是无前缀的旧变量名（`DB_ADAPTER`、`MYSQL_INSTANCE_NAME`、`CACHE`、`ENABLE_EXPORT`、`BASEURL`） | 确认镜像版本号与文档匹配：0.12 以上用 `MINDOC_*` 前缀；并且只用带版本号的镜像标签，不要用非版本标签 |
| 开启 MCP 后接口等于敞开 | `mcp_api_key` 默认是示例值 `demo-mcp-api-key` | 上线前改成自己的强随机密钥，并限制 `/mcp/` 路径的来源 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 容器部署时拉取镜像；启用邮件、LDAP、企业微信 / 钉钉登录时访问外部服务；配置了 CDN 时加载静态资源。纯内网单机部署可不开外网 |
| 读取文件 | 是 | 读取 `conf/app.conf`、`static` / `views` 模板资源、`uploads` 下的附件，以及 `runtime` 下的会话与缓存 |
| 写入文件 | 是 | 写入 `uploads` 附件、`runtime` 会话与日志、`database`（SQLite 模式）数据库文件、导出产物，以及根目录的 `install.lock` |
| 凭证 | 是 | 数据库账号密码、邮件 SMTP 账号、LDAP 绑定账号、钉钉 / 企业微信应用密钥、`mcp_api_key`。建议用环境变量注入，不要写死在版本库里的 `app.conf` |
| 子进程 / 后台常驻 | 是 | 本体是长期常驻的服务端进程，需要进程守护；导出 PDF / EPUB 等格式时会调用外部的 `ebook-convert` 子进程 |

## 触发场景

- "帮我在内网部署一个 MinDoc。"
- "MinDoc 装完了但后台一直登不进去。"
- "这个文档系统导出 PDF 报错，日志说 exit status 2。"
- "换服务器后 MinDoc 起不来，说是找不到数据库。"
- "想用 Nginx 把 MinDoc 挂到域名的二级目录下。"
- "MinDoc 和在线文档平台比，适合我们这种小团队吗？"

## 能力边界

**覆盖**：

- 项目管理：创建与编辑项目、项目成员添加、项目排序、公开/私有项目、私有项目 Token 访问
- 文档能力：多级目录树、Markdown 与富文本两种编辑器、文档历史、评论
- 用户与权限：用户管理（添加 / 禁用 / 资料修改）、角色变更、多语言界面
- 内容流转：Zip / Docx 导入项目；导出 PDF / EPUB / MOBI / DOCX / Markdown
- 站点配置：匿名访问、注册开关、验证码等；支持 CDN 加速静态资源
- 集成：LDAP / Active Directory 登录、钉钉与企业微信登录、自定义 HTTP 登录接口、可选的 MCP 服务端
- 三种数据库后端：MySQL、SQLite、Postgres

**不覆盖**：

- 多人实时协同编辑（不是"一起打字"那类编辑器）
- 与代码仓库联动、随提交自动同步文档
- 绑定域名（官方明确说明不支持，需要反代或独占端口）
- 屏幕录制、白板、流程图等富媒体创作工具
- 高可用集群与分布式部署方案（官方未提供）
- 向用户提供商业支持或 SLA（社区维护）

## 依赖条件

- 从源码编译：Go 不低于 1.23.0，需支持 CGO、`go mod`，并依赖 `time/tzdata`（推荐 1.23.x）
- 数据库三选一：MySQL（编码必须 `utf8mb4_general_ci`）、SQLite（默认，需 CGO）、Postgres
- 导出 PDF / EPUB / MOBI / DOCX 需要额外安装 Calibre 的 `ebook-convert`；官方镜像已内置
- Docker 部署：Docker + docker compose
- 可选集成项各自需要凭据：SMTP 账号、LDAP 绑定账号、钉钉 / 企业微信应用密钥
- 无需外部商业账号；MCP 功能自带示例密钥，上线需替换

## 已知限制

1. 项目已由原作者转交社区维护，迭代节奏以社区为准，不是商业级支持的产品。
2. Go 版本要求较新（官方要求不低于 1.23.0），老服务器上的 Go 需要先升级。
3. 官方没有提供安装向导网页，初始化只能靠命令行的 `install` 子命令。
4. 配置项里大量使用工作目录相对路径，移动目录或改变启动位置会直接影响运行。
5. 官方文档自身存在过时与不一致之处（例如后台运行示例里的二进制名、MCP 默认值在 README 与配置模板中不一致），关键参数请以当前版本的 `conf/app.conf.example` 与运行输出为准。
6. 导出功能依赖外部二进制，环境不满足时该功能整体不可用。

## 自检清单

执行前：

- [ ] 确认目标机架构与 GLibC 版本，CentOS 一类系统选用 musl 编译版本
- [ ] 用 MySQL 时已按 `utf8mb4_general_ci` 建库
- [ ] `conf/app.conf` 已从模板复制并填好 `db_*`，且知道要在根目录下启动
- [ ] `uploads`、`database`、`runtime`、`conf` 目录已规划好持久化（Docker 必须映射到宿主机）
- [ ] 需要导出 PDF 时已确认 `ebook-convert` 可用
- [ ] 已安排进程守护方式（supervisor 等），重启后能自动拉起

执行后：

- [ ] `install` 执行成功并看到成功提示，根目录生成 `install.lock`
- [ ] 用 `admin` 登录成功，并**立刻修改默认密码**
- [ ] 建一个测试项目，验证创建文档、上传附件、成员权限都正常
- [ ] 导出一次 Markdown（不依赖外部二进制）确认导出通道可用；再试一次 PDF
- [ ] 备份一次数据库与 `uploads` 目录，并确认恢复流程
- [ ] 若启用了 MCP，确认 `mcp_api_key` 已不是示例值

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/mindoc-org/mindoc | 上游仓库（安装与完整文档以它为准） |
| https://github.com/mindoc-org/mindoc/blob/master/conf/app.conf.example | 全部配置项与默认值的权威清单 |
| https://github.com/mindoc-org/mindoc/blob/master/docker-compose.yml | 官方 compose 文件：卷映射与默认环境变量 |
| https://demo.mindoc.cn/docs/mindochelp | 官方帮助文档总入口（安装、配置、Nginx、LDAP 等分册） |
| https://github.com/mindoc-org/mindoc/releases | 版本发布与升级说明（含每次是否需要执行 `install`） |

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
