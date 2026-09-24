---
name: sanjianke-halo
slug: sanjianke-halo
displayName: 三剪客 · 自托管内容站点系统
description: "把内容站点托管在自己的服务器上：Halo 的安装（Docker / Docker Compose / JAR）、工作目录与数据持久化、外部访问地址与数据库配置、反向代理与升级备份，以及端口打不开、附件上传失败、初始化地址写错这类高频故障的排查。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "一个可以自己掌控的建站与内容管理系统：带可视化后台、可换主题、可装插件，从个人博客到企业官网都能落地。含三种部署路径、工作目录挂载、数据库切换、反向代理与升级流程，以及数据丢失、上传失败、外链地址错误等常见事故的规避办法。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 自托管内容站点系统

你要的不是「发一篇文章」，而是一个**长期存在、自己说了算的站点**：有自己的域名、自己的后台、自己决定什么时候升级，内容数据落在自己的机器上。Halo 就是补这一环的——它是一个自托管的内容站点系统，前台是给人看的网站，后台是给你写稿、管附件、配菜单、装插件的地方。

它的价值在于**把「建站」变成一件可运维的事**：一条 Docker 命令就能起来，装好之后支持换主题、装插件、多用户分角色协作，工作目录一挂就能整站搬迁。个人博客、作品集、技术文档站、企业官网都能落在同一套系统上。

**上游项目**：`Halo`　**仓库**：https://github.com/halo-dev/halo

## 什么时候用 / 不用

**用它**：

- 用户说「想搭一个自己掌控的官网 / 博客 / 内容站」，并且愿意在一台服务器上跑一个常驻服务。
- 需要**可视化后台**：不写代码就能写文章、排菜单、传附件、配站点设置。
- 需要**主题与插件生态**：页面样式想换、想要评论、搜索、存储对接这类可插拔能力。
- 需要**多人协作**：给同事开账号、分角色，各写各的稿，由管理员统一发布。
- 已有一台服务器和域名，希望数据、备份、升级节奏都由自己决定。

**不要用它**：

- **只想写静态博客、不愿运维**。Halo 是常驻服务 + 数据库，需要长期开机、备份和升级；纯静态方案更省心。
- **不做自托管，只想用现成 SaaS 建站**。本项目的重点就是自己部署自己掌握。
- **要做交易型业务系统**（订单、库存、结算这类重业务逻辑）。它是内容系统，不是业务中台。
- **公网高并发且没有运维投入**。对外暴露前必须自己补 HTTPS、反向代理、备份与访问控制。
- **要的是多人实时协同编辑文档**。它的编辑模型面向文章/页面这类内容，不是实时协作文档。

## 安装

**方式一：Docker（最快，官方 README 给出的体验方式）**

```bash
docker run -d --name halo -p 8090:8090 -v ~/.halo2:/root/.halo2 halohub/halo:2.26
```

官方文档里的完整形态还带了 JVM 内存参数与社区版/付费版的镜像区分：

```bash
docker run -it -d --name halo -p 8090:8090 -v ~/.halo2:/root/.halo2 -e JVM_OPTS="-Xmx256m -Xms256m" halohub/halo:2.26
```

镜像命名规则：社区版是 `halohub/halo:<version>`，付费版是 `halohub/halo-pro:<version>`；除了具体版本号，也提供 `:<major>` 与 `:<major>.<minor>` 这类浮动标签。官方文档另有备用镜像仓库地址，网络拉取缓慢时以官方 Docker 部署文档为准。

> ⚠️ 官方明确说明：**这种只带 `-v` 的 Docker 方式默认使用自带 H2 数据库，只适合体验和测试**。生产环境请改用 Docker Compose + PostgreSQL。

**方式二：Docker Compose（生产推荐，官方推荐用 PostgreSQL）**

```yaml
services:
  halo:
    image: halohub/halo:2.26
    restart: on-failure:3
    networks:
      halo_network:
    volumes:
      - ./halo2:/root/.halo2
    ports:
      - "8090:8090"
    command:
      - --spring.r2dbc.url=r2dbc:pool:postgresql://halodb/halo
      - --spring.r2dbc.username=halo
      - --spring.r2dbc.password=openpostgresql
      - --spring.sql.init.platform=postgresql
      - --halo.external-url=http://localhost:8090/
```

参数写法（`--spring.r2dbc.url` / `--spring.r2dbc.username` / `--spring.r2dbc.password` / `--spring.sql.init.platform` / `--halo.external-url`）来自官方配置说明；数据库连接串格式为 `r2dbc:pool:postgresql://{HOST}:{PORT}/{DATABASE}`，`spring.sql.init.platform` 支持 `postgresql`、`mysql`、`mariadb`、`h2`。

**方式三：JAR 包**

```bash
# 依赖：2.21 以上版本需要 JRE 21；2.20 及以下版本需要 JRE 17；另需 MySQL 5.7+ / MariaDB / PostgreSQL 之一
mkdir ~/.halo2 && cd ~/.halo2
vim application.yaml          # 至少配好 server.port / spring.r2dbc.* / spring.sql.init.platform / halo.work-dir / halo.external-url
cd ~/app && java -Dfile.encoding=UTF-8 -jar halo.jar --spring.config.additional-location=optional:file:$HOME/.halo2/
```

配置文件里的 `halo.work-dir` 默认是 `${user.home}/.halo2`，`server.port` 默认 `8090`。

官方另有 Podman、Helm、离线包等部署路径，具体命令以官方文档《快速安装》下各页面为准。

## 常用操作

**1. 起服务并进后台初始化**

```bash
docker ps                     # 确认容器在跑
docker logs -f halo           # 看启动日志
```

浏览器访问 `http://<ip>:8090/console` 进入管理后台，首次启动会进初始化页面。**建议先把反向代理和域名解析配好，再执行初始化**——初始化会把当时的访问地址写进站点。

**2. 明确配置外部访问地址**

```bash
docker run -it -d --name halo -p 8090:8090 -v ~/.halo2:/root/.halo2 \
  -e JVM_OPTS="-Xmx256m -Xms256m" halohub/halo:2.26 \
  --halo.external-url=https://www.example.com
```

不配 `halo.external-url` 时，初始化页面会根据当前请求地址预填；`halo.use-absolute-permalink` 设为 `true` 时更依赖这个地址正确。

**3. 改成 MySQL / MariaDB**

只要把启动参数换成对应组合即可（名称同样来自官方配置说明）：

```bash
--spring.r2dbc.url=r2dbc:pool:mysql://127.0.0.1:3306/halo
--spring.r2dbc.username=halo
--spring.r2dbc.password=******
--spring.sql.init.platform=mysql
```

数据库需要提前建好，官方给的建库语句是 `create database halo character set utf8mb4 collate utf8mb4_bin;`。

**4. 看服务健康状态**

官方 Docker Compose 示例用的探针地址是：

```bash
curl -f http://localhost:8090/actuator/health/readiness
```

**5. 反向代理（官方 Nginx 示例）**

```nginx
upstream halo {
  server 127.0.0.1:8090;
}
server {
  listen 80;
  server_name www.yourdomain.com;
  client_max_body_size 1024m;
  location / {
    proxy_pass http://halo;
    proxy_set_header HOST $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

**6. 升级**

```bash
docker pull halohub/halo:2.26     # 1. 拉新镜像
docker stop halo && docker rm halo # 2. 停掉并删除旧容器
docker run -it -d --name halo -p 8090:8090 -v ~/.halo2:/root/.halo2 \
  -e JVM_OPTS="-Xmx256m -Xms256m" halohub/halo:2.26   # 3. 用同样的参数重建容器
```

升级前先按官方《备份与恢复》做一次完整备份。JAR 方式的对应流程是：`service halo stop` → 下载新 JAR 覆盖 → `service halo start`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 重建容器后文章、附件、配置全没了 | 启动命令漏了 `-v ~/.halo2:/root/.halo2`，数据留在容器里随容器一起被删 | 必须做工作目录映射；**容器内的挂载点 `/root/.halo2` 是固定的，不能改成别的路径**，只能改冒号前面的宿主机路径 |
| 站点跑着跑着数据文件损坏、打不开 | 用了自带的 H2 数据库承接生产流量 | 官方明确不推荐生产用 H2；换成 PostgreSQL（推荐）或 MySQL / MariaDB |
| 附件图片链接指向 `localhost` 或内网 IP | 没配 `halo.external-url`，初始化时把当前请求地址写了进去 | 先配好域名解析与反向代理，再初始化；已初始化的用启动参数补上 `--halo.external-url=https://你的域名` |
| 后台上传大附件失败、反代返回 413 | Nginx 默认请求体限制太小 | 官方示例在 server 段写了 `client_max_body_size 1024m;`，按需调整 |
| `http://ip:8090` 打不开 | 云厂商安全组或本机防火墙没放行 8090 | 在服务器后台把端口加进安全组；用了 Linux 面板的要同时检查面板侧的安全组 |
| 换了数据库后启动报连接失败 | `spring.r2dbc.url`、`spring.sql.init.platform` 与实际数据库不匹配，或库还没建 | 四者要成套：连接串用 `r2dbc:pool:<db>://...`，`platform` 填 `postgresql`/`mysql`/`mariadb`/`h2`，并提前建好库 |
| 用 JAR 部署时启动直接报 Java 版本问题 | 版本线要求不同：2.21 以上要 JRE 21，2.20 及以下要 JRE 17 | 按自己下载的运行包版本准备对应 JRE |
| 升级后站点异常 | 直接删了旧容器重建、没备份工作目录 | 升级三步走（备份 → 拉镜像 → 重建容器）不能省；JAR 方式则是先停服务再覆盖运行包 |
| 直接用 root 跑 JAR 服务 | 官方不建议 | 按官方文档建一个专用系统用户来跑，并用 systemd 托管 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取镜像；对外提供 Web 服务与后台；访问外部存储、评论等服务时也需要出网 |
| 读取文件 | 是 | 读取工作目录下的配置、附件、主题与插件文件；JAR 方式还要读取 `application.yaml` |
| 写入文件 | 是 | 写入工作目录（`~/.halo2`）：数据库文件、附件、日志、主题与插件；上传附件本质上就是写文件 |
| 凭证 | 是 | 数据库账号密码、后台管理员账号、可选的对象存储密钥与许可证。部署参数里难免出现密码，**本 Skill 不内嵌任何密钥，请自行管理** |
| 子进程 / 后台常驻 | 是 | 以常驻服务形式运行：Docker 由容器承载（建议 `restart: on-failure:3` 或 `always`），JAR 方式建议用 systemd 托管并在开机自启 |

## 触发场景

- 「帮我搭一个自己的博客 / 官网」
- 「要能换主题、能装插件的内容站」
- 「用 Docker 起一个 Halo」
- 「后台要能多人分角色写稿」
- 「站点要能备份，以后能整体搬迁」
- 「Halo 的 8090 端口打不开 / 附件传不上去」

## 能力边界

**覆盖**：

- 自托管的内容站点：文章、页面、评论、附件、菜单、分类与标签这类基础内容模块。
- 可视化后台：站点设置、用户与权限、主题切换、插件安装、备份与恢复。
- 应用生态：主题与插件可通过应用市场获取并安装，插件可扩展站点能力。
- 数据可换：PostgreSQL（官方推荐）、MySQL、MariaDB、H2 四种数据库平台。
- 多种部署形态：Docker、Docker Compose、JAR + systemd、容器编排等方式。
- 站点级配置项：外部访问地址、永久链接形式、iframe 与 Referrer 安全策略、登录有效期、两步验证开关、附件缩略图等。

**不覆盖**：

- 不替你做公网安全加固：HTTPS 证书、WAF、限流、备份策略、监控告警都要自己规划。
- 不做业务系统：没有订单、库存、结算这类交易域逻辑（付费版本的商城能力另属其授权范围，本 Skill 不涉及）。
- 不提供模型与 AI 能力；不涉及视频剪辑、短剧出片这类内容生产工作流。
- 不提供托管云服务；本项目面向自托管部署。
- 付费版本与开源版本的功能差异以官方为准，本 Skill 只覆盖开源社区版的通用运维路径。

## 依赖条件

- Docker 方式：本机 Docker；官方 Docker 部署文档说明该方式默认使用 H2，仅适合体验测试。
- Docker Compose 方式：Docker + Compose，建议同时准备一个独立数据库（官方推荐 PostgreSQL）。
- JAR 方式：JRE（2.21 以上为 21，2.20 及以下为 17）+ 任一数据库（MySQL 5.7+ / MariaDB / PostgreSQL）。
- 生产环境强烈建议使用独立数据库，不要用 H2。
- 数据持久化：Docker 必须挂载 `-v <宿主机路径>:/root/.halo2`；JAR 方式要保证 `halo.work-dir` 所在目录可写。
- 公网访问：域名 + DNS 解析 + 反向代理（官方示例给了 Nginx 与 Caddy 配置），以及云安全组放行端口。
- 可选的付费能力（如 Redis 会话存储）需要许可证，属付费版本范围，社区版不需要也不会用到。

## 已知限制

- 端口在不同部署说明里都以 `8090` 为默认值，改过 `server.port` 或做过端口映射后，排障时要先确认自己实际暴露的是哪个端口。
- 工作目录在容器内的路径固定为 `/root/.halo2`，只能调整宿主机侧的挂载路径。
- H2 数据库只适合体验；生产误用会带来数据文件损坏风险，官方对此专门给出警告。
- 初始化会把当时的访问地址写进站点，事后再改域名需要重新配置 `halo.external-url` 并检查附件链接。
- 上游迭代较快，镜像标签、配置项与界面位置都可能变化；**执行前请以官方文档与当前版本的 `--help` / 官方配置说明为准**。
- 具体版本号、发布日期与 star 数请以仓库页面实时信息为准，本 Skill 不做断言。

## 自检清单

- [ ] 已选定部署方式（Docker / Compose / JAR），并确认实际访问端口。
- [ ] Docker 方式：命令里带了 `-v <宿主机路径>:/root/.halo2`，容器内路径没有被改动。
- [ ] 生产环境已换成 PostgreSQL / MySQL / MariaDB，没有继续用 H2。
- [ ] 数据库四项配置成套：`spring.r2dbc.url`、`username`、`password`、`spring.sql.init.platform`。
- [ ] 域名解析与反向代理已配好，并在**初始化之前**设置好 `halo.external-url`。
- [ ] 反向代理里按需设置了 `client_max_body_size`，否则大附件会失败。
- [ ] 云安全组 / 防火墙已放行端口。
- [ ] 已经做过一次完整备份，并知道备份文件在哪。
- [ ] 升级前备份过工作目录，升级用的是「拉镜像 → 停删旧容器 → 同参数重建」。
- [ ] 后台管理员账号已设置强密码，未把管理后台直接裸奔在公网。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/halo-dev/halo | 上游仓库（安装与完整文档以它为准） |
| https://docs.halo.run/guide/install/docker | 官方 Docker 部署文档（镜像说明、升级步骤） |
| https://docs.halo.run/guide/install/docker-compose | 官方 Docker Compose 部署文档（配置参数写法） |
| https://docs.halo.run/guide/install/config | 官方配置说明（完整配置项与数据库连接串格式） |

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
