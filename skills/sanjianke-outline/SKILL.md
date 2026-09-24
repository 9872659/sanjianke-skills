---
name: sanjianke-outline
slug: sanjianke-outline
displayName: 三剪客 · Outline 团队知识库
description: "Outline：面向团队的知识库与文档协作服务，自建时用 Docker 起一套，文档全部以 Markdown 存储并可通过 RPC 接口批量读写。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Outline：面向团队的知识库与文档协作服务，自建时用 Docker 起一套，文档全部以 Markdown 存储并可通过 RPC 接口批量读写。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · Outline 团队知识库

Outline 是给团队用的知识库：文档按集合归类，有搜索、有权限、有历史版本，界面响应快。文档底层全部以 Markdown 存储，这一点让它在自动化场景里很好用——可以程序化地建文档、追加内容、批量开通账号。

它有两种用法，**先分清再动手**：直接用官方托管版，不需要跑任何代码；或者自建，此时你面对的是一个 Node.js 服务加 Postgres 加 Redis 的组合，官方推荐用 Docker 部署。

对自建场景来说，最需要提前知道的两件事：一是它**没有内置账号密码登录**，必须接一个第三方身份提供方（Slack / Google / Microsoft / Discord / 通用 OIDC 之一）；二是授权是商业许可证，自建前先确认许可范围。

**上游项目**：`Outline`　**仓库**：https://github.com/outline/outline

## 什么时候用 / 不用

**用它**：

- 「团队的文档要集中管起来，还要能按集合分权限、能全文搜索。」
- 「文档要能程序化生成」——比如把发布说明、接口文档自动同步进知识库。
- 「要自己掌控文档数据落在哪个数据库、哪个对象存储里。」
- 「要给外部用户开只读的分享页，而不是把整站权限给出去。」
- 「想把已有文档批量迁移进来」，或者反过来把知识库内容批量导出去做二次处理。

**不要用它**：

- 只是自己一个人记笔记——它是为团队协作和权限设计的，个人用属于杀鸡用牛刀。
- 期望自建后能用账号密码登录——它不提供这种登录方式，**必须**配一个第三方身份提供方，否则没人能登进去。
- 给资料敏感度极高、要求完全离线隔离的环境用——它对外部身份提供方和前端资源有依赖，纯离线部署不在它顺畅的路径上。
- 需要一个能离线打包分发的桌面文档工具——它是服务端应用。
- 对许可证有严格要求（例如必须只用 OSI 认可的开源许可）——它的授权是商业许可证，自建前先确认合规。
- 只是想找个 Markdown 编辑器——本地编辑器加 Git 更轻。

## 安装

自建有两种路径，**官方文档是权威来源**，下面是命令骨架。

**Docker Compose（官方推荐）**：

先按 `.env.sample` 准备一个 `docker.env`，**`URL`、`DATABASE_URL`、`REDIS_URL`、`SECRET_KEY` 是最低要求**；缺哪些变量启动时会提示出来。

```yaml
services:
  outline:
    image: docker.getoutline.com/outlinewiki/outline:latest
    env_file: ./docker.env
    expose:
      - "3000"
    volumes:
      - storage-data:/var/lib/outline/data
    depends_on:
      - postgres
      - redis

  redis:
    image: redis
    env_file: ./docker.env
    expose:
      - "6379"
    command: ["redis-server", "/redis.conf"]

  postgres:
    image: postgres:18
    env_file: ./docker.env
    expose:
      - "5432"
    volumes:
      - database-data:/var/lib/postgresql
    environment:
      POSTGRES_USER: 'user'
      POSTGRES_PASSWORD: 'pass'
      POSTGRES_DB: 'outline'

volumes:
  storage-data:
  database-data:
```

```bash
# 起服务（先确认当前目录就是放 docker-compose.yml 的地方）
docker compose up -d

# 看启动日志，重点排查数据库和 Redis 连接报错
docker compose logs -f outline
```

**用官方单容器镜像**（Postgres / Redis / 存储都在云端时可以直接跑）：

```bash
docker run -d --name outline \
  --env-file ./docker.env \
  -p 3000:3000 \
  -v /var/lib/outline/data:/var/lib/outline/data \
  docker.getoutline.com/outlinewiki/outline:latest
```

**升级**：

```bash
# 1. 先备份数据库（官方单独有一篇备份说明）
# 2. 拉新镜像
docker pull docker.getoutline.com/outlinewiki/outline:latest
# 3. 重建容器；数据库迁移默认在容器启动时自动跑
docker compose up -d
```

数据库迁移默认随容器启动自动执行，想改成手动跑就在启动命令上加 `--no-migrate`。**官方建议固定镜像版本标签而不是用 `latest`**，这样升级节奏可控。

## 常用操作

```bash
# 1. 起停与看日志
docker compose up -d
docker compose logs -f outline

# 2. 排查：打开 HTTP 日志
#    在 docker.env 里设 DEBUG=http；要看全部类别用 DEBUG=*，
#    或按类别开，例如 DEBUG=database 配 LOG_LEVEL=debug，更啰嗦用 LOG_LEVEL=silly

# 3. 关掉匿名统计上报
#    在 docker.env 里设 ENABLE_UPDATES=false

# 4. 用接口建一篇文档（RPC 风格，POST + JSON）
curl -XPOST -H "Content-type: application/json" -d '{
  "title": "我的第一篇文档",
  "text": "来自接口的问候",
  "collectionId": "<集合ID>",
  "token": "<API_TOKEN>",
  "publish": true
}' 'https://<你的域名>/api/documents.create'
```

说明几点：

- `collectionId` 在浏览器地址栏里能直接看到；`token` 在账号设置里的接口 token 页面生成。
- 接口是 RPC 风格的，一个动作一个端点，建文档、追加内容、开通账号都各有端点。
- **完整的端点清单与字段含义以官方开发者文档为准**，本 Skill 不逐个罗列，避免版本漂移后误导。
- 自建的域名换成你自己的；托管版则是 `https://www.getoutline.com/api/...`。

**开发与测试相关命令**（要改代码或跑测试时才用）：

```bash
# 跑全部测试
make test

# 新建一个数据库迁移
yarn db:create-migration --name my-migration
# 执行迁移 / 回滚
yarn db:migrate
yarn db:rollback
# 对测试库执行迁移
yarn db:migrate --env test
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 服务起来了但登录页没有任何可用的登录方式 | 它不自带账号密码登录，**必须**至少配一个第三方身份提供方（Slack / Google / Microsoft Entra / Discord / 通用 OIDC 之一） | 在 `docker.env` 里配好至少一组身份提供方的 client id 与 secret；官方表示缺关键变量时启动会提示 |
| 容器启动直接失败，日志提示缺变量 | `URL`、`DATABASE_URL`、`REDIS_URL`、`SECRET_KEY` 是必需项 | 按 `.env.sample` 逐项补齐，特别是 `SECRET_KEY` 要用 `openssl rand -hex 32` 这类方式生成随机值 |
| 用了默认的 `SECRET_KEY` 或占位值 | 示例文件里的值只是占位，直接用于生产会危及会话安全 | 生成一次自己的随机密钥并妥善保存；换密钥会让现有会话失效，属预期行为 |
| 上传的附件重启后丢失 | 存储目录没挂持久化卷 | 挂上 `storage-data` 卷；用对象存储时确认 `FILE_STORAGE=s3` 及相关配置项都填了 |
| 用户点了登录，回调后报错或跳回首页 | 身份提供方的回调地址没配成 Outline 的对外地址 | 把 `URL` 设成用户实际访问的完整地址，并在身份提供方后台把回调地址配成一致的值 |
| 分享链接、邮件里的链接指向内网地址或 `localhost` | `URL` 没有设成对外可访问的正式地址 | 部署前先把 `URL` 定下来；前面有代理时填代理对外暴露的地址 |
| 反代之后部分请求被限流，或拿不到真实客户端 IP | 全局限流器默认开启，且客户端 IP 依赖代理头 | 按需调 `RATE_LIMITER_ENABLED` / `RATE_LIMITER_REQUESTS` / `RATE_LIMITER_DURATION_WINDOW`，并确认代理头配置与 `PROXY_IP_HEADER` 设置一致 |
| 升级后起不来或数据异常 | 数据库迁移在容器启动时自动执行，跳版本升级可能出问题 | 严格按官方的更新流程：**先备份数据库 → 拉新镜像 → 启动**；跨大版本时逐版本升 |
| 把 `docker.env` 提交进了仓库 | 里面是数据库密码、`SECRET_KEY`、各家 client secret | 加进 `.gitignore`；支持文件式密钥的环境可以用变量名加 `_FILE` 后缀的方式从文件读取密钥 |
| 自建后拿它做商业用途前没确认许可 | 它的授权是商业许可证，不是常见的宽松开源许可 | 自建或二次分发前先读仓库里的许可文件，确认自己的使用方式在许可范围内 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取镜像与前端资源；监听对外端口；与身份提供方、对象存储、SMTP、各类集成服务通信 |
| 读取文件 | 是 | 读取 `docker.env` 配置、TLS 证书（如用）、本地上传的附件与头像、反向代理配置与日志 |
| 写入文件 | 是 | 本地存储模式下写入上传的附件与图片；容器日志；数据库卷的持久化写入 |
| 凭证 | 是 | Postgres 账号密码、Redis 连接串、`SECRET_KEY`、身份提供方 client id / secret、接口 token、S3 密钥、SMTP 凭据。**全部按密钥管理，`.env` 不进版本库** |
| 子进程 / 后台常驻 | 是 | Outline 服务容器长期常驻；Postgres 与 Redis 作为依赖服务常驻；启动时自动执行数据库迁移 |

## 触发场景

- 「帮我把 Outline 用 Docker 自建起来，配好 Postgres 和 Redis。」
- 「自建完了怎么没人能登录？该配哪个身份提供方？」
- 「怎么用接口把一批内容批量建成 Outline 文档？」
- 「Outline 升级的正确顺序是什么？迁移会自动跑吗？」
- 「上传的图片重启之后丢了，是哪里没配？」
- 「怎么打开 Outline 的详细日志来排查问题？」

## 能力边界

**覆盖**：

- 自建部署：Docker Compose 组合、单容器模式、必需环境变量的判断、持久化卷、更新与迁移顺序。
- 身份接入：无内置密码登录这一硬约束，以及可选身份提供方的种类和配置方向。
- 接口调用：RPC 风格接口的调用形态、token 来源、建文档的可用示例。
- 存储配置：本地存储与 S3 兼容存储的选择及关键变量。
- 辅助配置：日志级别与调试类别、匿名统计上报开关、限流参数、文件大小上限。
- 开发相关命令：测试、数据库迁移的创建与执行回滚。

**不覆盖**：

- 接口的完整字段级清单——动作端点很多，**以官方开发者文档为准**。
- 前端与后端的代码架构细节、迁移脚本的内部实现。
- 身份提供方各自的申请流程（各家控制台的注册步骤）。
- 官方托管版的计费、套餐与账号管理。
- 具体部署形态的容量规划与性能调优结论。
- 许可授权的法律判断——自建或商用前请自行确认许可范围。

## 依赖条件

- Docker 与 Docker Compose（官方推荐的自建方式），或一个可跑容器的主机。
- PostgreSQL（必需）与 Redis（必需）。
- 一个第三方身份提供方账号（至少一个，否则无人能登录）。
- 对外访问时的域名与反向代理 / TLS 证书。
- 持久化存储：数据库卷 + 附件存储（本地卷或 S3 兼容对象存储）。
- 可选：SMTP 账号（邮件通知与邮件登录）、各类集成凭据、Sentry 等错误上报。

## 已知限制

- 没有内置的账号密码登录方式，自建必须接第三方身份提供方。
- 授权是商业许可证，不是常见宽松开源许可，使用前需确认合规。
- 数据库迁移默认在容器启动时自动执行，`--no-migrate` 可改为手动，但升级顺序不能乱。
- 官方建议固定镜像版本标签，用 `latest` 会让升级不可控。
- 部分能力（如实时协作的水平扩展）依赖额外的 Redis 配置。
- 上游对 AI 生成的批量低质量代码贡献有明确限制，这会影响你向上游提 PR 的方式，但不影响自建使用。

## 自检清单

执行前：

- [ ] 确认走托管版还是自建；自建的话是否具备容器与数据库的运维能力。
- [ ] 已确认许可范围允许自己的使用方式。
- [ ] `URL` 已设成对外正式地址。
- [ ] `SECRET_KEY` 用的是自己生成的随机值，不是示例占位值。
- [ ] `DATABASE_URL`、`REDIS_URL` 指向真实可连的实例。
- [ ] 已配好至少一个身份提供方，且回调地址与 `URL` 一致。
- [ ] 附件存储已挂持久化卷，或已配好对象存储。
- [ ] `.env` 已加入 `.gitignore`。

执行后：

- [ ] 日志里没有数据库或 Redis 连接报错。
- [ ] 能通过身份提供方实际登录，并建一篇文档、传一张图。
- [ ] 重启容器后文档与附件都还在。
- [ ] 用接口建一篇测试文档，确认 token 与 `collectionId` 有效。
- [ ] 升级场景下确认迁移已执行完成，且升级前有可用备份。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/outline/outline | 上游仓库（安装与完整文档以它为准） |
| https://github.com/outline/outline/blob/main/.env.sample | 全部环境变量样例与注释 |
| https://docs.getoutline.com/s/hosting | 自建安装与运维文档 |

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
