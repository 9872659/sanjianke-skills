---
name: sanjianke-crawlab
slug: sanjianke-crawlab
displayName: 三剪客 · 分布式爬虫管理平台
description: "crawlab：分布式爬虫管理平台 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "crawlab：分布式爬虫管理平台 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 爬虫
  - 数据分析
---

# 三剪客 · 分布式爬虫管理平台

当爬虫从「一个脚本」长成「几十个爬虫、多台机器、要定时跑、要看日志和结果」的时候，
单机计划任务就不够用了。Crawlab 用一套 Web 控制台把这些统一起来：爬虫文件集中管理、
任务分发到多个节点执行、日志和结果在界面上直接看。它不管你的爬虫怎么写——Python、Node、
Go、Java 都行，Scrapy、Puppeteer、Selenium 也都能接——它只负责「把爬虫放上去、跑起来、
盯住它、把数据收回来」。

**上游项目**：`crawlab`　**仓库**：https://github.com/crawlab-team/crawlab

## 什么时候用 / 不用

**用它**：

- 手上有一批不同语言、不同框架写的爬虫，想统一上传、统一在界面上触发、统一看日志。
- 要多机横向扩展：一台主节点 + 多台工作节点，任务自动分发，而不是每台机器各管各的。
- 需要平台级的运维能力：定时任务、任务重跑与停止、任务结果集中存储与导出、节点监控。
- 团队里非开发同学也要看抓取进度、跑任务、看结果。
- 想让爬虫代码和运行环境解耦：代码在平台上管，运行在节点容器里。

**不要用它**：

- 只有一个爬虫、一天跑一次——本机计划任务就够了，上平台纯属增加运维成本。
- 你要解决的问题是抓取本身：反爬对抗、代理池、验证码、浏览器指纹——这些它一概不管，
  还是要靠 Scrapy、Playwright 这类框架自己写。
- 只需要一次性抓几百页存成 CSV——直接写脚本更快。
- 手上没有 Docker 环境和长期可用的服务器——平台自身要吃 MongoDB、磁盘和内存。
- 想要的是开箱即用的托管云服务、不想碰运维——它是自部署平台，数据库、存储、升级都得自己管。

## 安装

**前置条件**：一台能跑 Docker 的机器（Linux 服务器最省事），并已安装 Docker 与 Docker Compose。
新版 Docker 用 `docker compose` 子命令，老版本是独立的 `docker-compose`，下面的命令参数一致，
按你自己环境的写法替换即可。

**方式一：用官方示例仓库一键起（推荐先用它跑通）**

```bash
git clone https://github.com/crawlab-team/examples
cd examples/docker/basic
docker-compose up -d
```

启动后浏览器打开 `http://localhost:8080`，默认账号密码是 `admin / admin`。

**方式二：自己写最小 compose（单节点，master + MongoDB）**

```yaml
version: '3.3'
services:
  master:
    image: crawlabteam/crawlab:latest
    container_name: crawlab_master
    environment:
      CRAWLAB_NODE_MASTER: "Y"
      CRAWLAB_MONGO_HOST: "mongo"
    volumes:
      - "./.crawlab/master:/root/.crawlab"
    ports:
      - "8080:8080"
    depends_on:
      - mongo

  mongo:
    image: mongo:4.2
    restart: always
```

```bash
docker-compose up -d
docker-compose ps          # 确认容器都起来了
```

**方式三：加工作节点扩容**

在上面的 compose 里再加一个 worker 服务，主节点和工作节点通过 gRPC 通信，
爬虫文件由主节点统一分发：

```yaml
  worker01:
    image: crawlabteam/crawlab:latest
    environment:
      CRAWLAB_NODE_MASTER: "N"
      CRAWLAB_GRPC_ADDRESS: "master"
      CRAWLAB_FS_FILER_URL: "http://master:8080/api/filer"
    volumes:
      - "./.crawlab/worker01:/root/.crawlab"
    depends_on:
      - master
```

```bash
docker-compose up -d
```

**命令行工具与 SDK（可选，用于上传爬虫、在爬虫里回写结果）**

```bash
pip install crawlab-sdk
```

爬虫要能把结果写进平台的结果集，需要在爬虫的运行环境里装上同一个 SDK：

```bash
pip install crawlab-sdk
```

> 各配置项随版本变化（例如主节点开关由 `CRAWLAB_SERVER_MASTER` 改为 `CRAWLAB_NODE_MASTER`），
> 拉镜像前先对照官方部署文档与示例仓库里的 `docker-compose.yml`，不要照抄旧教程的字段。

## 常用操作

**1）上传本地爬虫目录并查看平台状态**

```bash
crawlab login -u admin -a http://localhost:8080/api   # 按提示输入密码
crawlab upload -d /path/to/my-spider -n my-spider -N "我的爬虫"
crawlab spiders      # 爬虫列表
crawlab nodes        # 节点列表
crawlab tasks        # 任务列表
```

`upload` 还支持 `-m` 指定执行命令、`-c` 指定结果集、`-i` 指定爬虫 ID 覆盖上传，
完整参数以 `crawlab upload --help` 和官方文档为准。

**2）在通用 Python 爬虫里写入结果**

```python
from crawlab import save_item

result = {"name": "crawlab", "url": "https://example.com"}
save_item(result)
```

任务跑完在「任务详情 → 数据」里就能看到记录。

**3）接入 Scrapy 项目**

在项目的 `settings.py` 里加上：

```python
ITEM_PIPELINES = {
    'crawlab.scrapy.pipelines.CrawlabPipeline': 888,
}
```

**4）其它语言 / 框架的爬虫怎么关联结果**

任务本质上是执行一条 shell 命令，平台会把任务 ID 通过环境变量传进去：

```bash
echo $CRAWLAB_TASK_ID
```

用这个环境变量把数据关联到任务，再通过平台的接口回写。

**5）日常运维：看日志、升级**

```bash
docker-compose logs -f master                 # 盯主节点日志
docker-compose pull && docker-compose up -d   # 拉新镜像并重启
```

**6）用页面上的文件管理器直接改代码**

登录后进入爬虫详情的文件页，可以拖拽上传、选择目录上传、在线新建/重命名/删除文件。
新版本已经取消了 ZIP 打包上传，上传目录时注意保持项目根目录结构。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 打开 8080 是空白页或 502 | 主节点首次启动还在初始化数据库、做数据迁移 | `docker-compose logs -f master` 等到就绪，别反复重启容器 |
| 节点列表里工作节点一直离线 | 节点间地址配错，或容器不在同一网络 | 核对 `CRAWLAB_GRPC_ADDRESS: "master"`、`CRAWLAB_FS_FILER_URL: "http://master:8080/api/filer"`，保证同一 compose 网络 |
| 容器重启后爬虫、任务、结果全没了 | MongoDB 没挂数据卷，数据落在容器里 | 给 mongo 挂 volume；主/工作节点的 `/root/.crawlab` 也建议挂出来 |
| 默认 `admin / admin` 登录不进去 | 初始化未完成，或密码已被改过 | 等初始化结束再试；已改过就按官方文档重置，别急着重装 |
| 爬虫在平台上跑报缺依赖 | 爬虫跑在节点容器内，不是你本机的环境 | 在容器内装依赖，或基于镜像做自定义镜像，并保证每个节点一致 |
| Scrapy 上传后跑不起来 | 上传的目录层级不对，`scrapy.cfg` 不在被上传目录的根 | 上传整个项目根目录（以 `scrapy.cfg` 所在目录为根） |
| 任务一直排队不执行 | 没有可用工作节点，或并发数被占满 | 看节点状态与任务执行器并发配置，加工作节点或调并发 |
| 任务结果集里没有数据 | 爬虫没调用 `save_item`、没启用管道，或任务是手动在宿主机跑的 | 用 SDK 写入结果，并且让任务通过平台发起（这样才有任务 ID） |
| 8080 端口被占用 | 宿主机上已有服务占了该端口 | 改 compose 的端口映射，例如 `"18080:8080"` |
| 把主仓库根目录的 compose 当生产配置用 | 那只是最小示例（master + mongo） | 跑通体验可以，正式部署按官方部署文档补持久化、节点与资源配置 |
| 随手把 MongoDB 镜像换成最新版后起不来 | 平台与数据库版本之间存在兼容区间 | 按示例仓库给出的版本组合来，升级前先备份数据 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取镜像、浏览器访问控制台、节点间 gRPC 通信、爬虫请求目标站点 |
| 读取文件 | 是 | 读取挂载进来的爬虫代码、配置与任务日志 |
| 写入文件 | 是 | 保存上传的爬虫文件、任务日志与结果、MongoDB 数据目录 |
| 凭证 | 是 | 平台账号（默认 `admin / admin` 仅用于首次登录）、数据库账号、目标站点与通知渠道凭证 |
| 子进程 / 后台常驻 | 是 | 主节点、工作节点、数据库都是常驻容器；任务以子进程执行爬虫，并通过 `CRAWLAB_TASK_ID` 传给子进程 |

## 触发场景

- 「帮我搭一个爬虫管理平台，能多台机器一起跑」
- 「爬虫的定时任务、日志、结果想在一个界面里看」
- 「怎么把本地写好的爬虫传到平台上跑」
- 「爬虫抓到的数据怎么进 Crawlab 的结果集」
- 「Crawlab 起来了，但工作节点一直连不上 / 页面打不开」
- 「Crawlab 和 Scrapy 怎么接」

## 能力边界

**覆盖**：

- 多语言、多框架爬虫的集中管理：Python、Node、Go、Java 等，Scrapy、Puppeteer、Selenium 等均可接入。
- 分布式调度：主节点统一分发任务，工作节点横向扩容。
- 任务能力：手动触发、定时任务、日志查看、结果集存储与导出、任务停止与重跑。
- 文件管理：网页端在线编辑、拖拽与目录上传、CLI 上传。
- 节点管理：节点列表、节点状态监控、拓扑视图。
- 平台能力：用户与权限管理、消息通知（邮件、机器人）、Docker 化部署。

**不覆盖**：

- 不写爬虫逻辑，不做页面的结构化抽取规则配置——爬虫代码还是你自己写。
- 不做反爬对抗：代理池、验证码识别、浏览器指纹、请求频率治理都不在其中。
- 不提供托管云服务，不自带备份与容灾方案——运维、持久化、升级由你负责。
- 不做结果数据的清洗、建模与可视化，它只是把数据收进结果集。
- 官方说明中明确暂不提供爬虫代码的版本管理，别指望在这里做代码回滚。
- 不覆盖「让 Agent 直接驱动平台」的集成，那需要另外的消息服务端项目。

## 依赖条件

- Docker 与 Docker Compose（部署方式以容器为主）。
- 一个 MongoDB 实例（示例 compose 里用 `mongo:4.2` 随平台一起起）。
- 一个可被浏览器访问的端口（默认 8080）和一个长期在线的运行环境。
- 用 CLI 或让爬虫回写结果时，需要 Python 3 环境并 `pip install crawlab-sdk`。
- 不需要 GPU、不需要模型权重，也不需要任何模型服务地址或 Key。

## 已知限制

- 平台自身要长期占一台机器（数据库 + 磁盘 + 内存），不等于省运维。
- 数据持久化必须自己配卷，默认配置下容器重建可能丢数据。
- 节点环境一致性要自己保证：依赖装在容器里，节点之间不一致就会「这台能跑那台报错」。
- 爬虫在容器内执行，与宿主机的路径、环境变量、字体、浏览器依赖都不一致，是最常见的排错点。
- 版本间配置项变化较大，升级前必须先看变更说明，并备份 MongoDB 数据。

## 自检清单

- `docker-compose ps` 里主节点与数据库容器是否都是 Up。
- `docker-compose logs -f master` 有没有初始化完成、有没有连不上数据库的报错。
- 浏览器能否打开 `http://localhost:8080` 并用默认账号登录。
- 节点列表里工作节点是否在线，还是长期显示离线。
- 上传的爬虫目录结构是否正确（Scrapy 项目以 `scrapy.cfg` 所在目录为根）。
- 任务结果是否真的写进结果集：爬虫里有没有调用 `save_item` 或启用对应管道。
- MongoDB 与工作节点的数据卷是否已经挂上，重启会不会丢数据。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/crawlab-team/crawlab | 上游仓库（安装与完整文档以它为准） |
| https://github.com/crawlab-team/examples | 官方示例，含可直接 `docker-compose up -d` 的目录 |
| https://github.com/crawlab-team/crawlab-sdk | 各语言 SDK 与 CLI 命令行工具 |

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
