# 三剪客 · 分布式爬虫管理平台 Skill

crawlab：分布式爬虫管理平台 的安装、常用命令与避坑要点

---

## 前置条件

- 一台能长期跑 Docker 的机器（Linux 服务器最省事），已安装 Docker 与 Docker Compose。
- 一个 MongoDB 实例；按示例 compose 随平台一起起最省事。
- 默认需要一个可被浏览器访问的端口（8080），端口冲突时在 compose 里改映射。
- 规划好数据落盘位置：数据库、任务日志、上传的爬虫文件都要持久化，否则重启可能丢数据。
- 要上传爬虫或让爬虫回写结果，需要 Python 3 环境并安装 SDK。
- 第一次启动需要等待初始化与数据迁移完成，不要在这一步反复重启容器。

---

## 使用

最短跑通路径（一条命令拉起主节点 + 工作节点 + 数据库）：

```bash
git clone https://github.com/crawlab-team/examples
cd examples/docker/basic
docker-compose up -d
```

浏览器打开 `http://localhost:8080`，默认账号密码 `admin / admin`。

最小自建 compose（单节点）：

```yaml
version: '3.3'
services:
  master:
    image: crawlabteam/crawlab:latest
    environment:
      CRAWLAB_NODE_MASTER: "Y"
      CRAWLAB_MONGO_HOST: "mongo"
    ports:
      - "8080:8080"
    depends_on:
      - mongo
  mongo:
    image: mongo:4.2
```

```bash
docker-compose up -d
```

上传本地爬虫并查看状态：

```bash
pip install crawlab-sdk
crawlab login -u admin -a http://localhost:8080/api
crawlab upload -d /path/to/my-spider -n my-spider
crawlab spiders
```

完整的三种部署方式（示例仓库一键起 / 自建 compose / 加工作节点扩容）、6 组常用操作、
11 条常见坑与排查办法，见 `SKILL.md`。

---

## 依赖

- **Docker 与 Docker Compose**：部署方式以容器为主。
- **MongoDB**：平台的运行数据库，存节点、爬虫、任务、定时任务等数据；示例 compose 用 `mongo:4.2`。
- **镜像**：平台镜像为 `crawlabteam/crawlab`，工作节点用同一个镜像、靠环境变量区分角色。
- **Python 3 + `crawlab-sdk`**：用于 CLI 上传爬虫，以及在爬虫里回写任务结果。
- **爬虫自身的依赖**：跑在节点容器内，需要你自行装进容器或做成自定义镜像。
- **不需要**：GPU、显存、模型权重、模型服务地址或任何模型 API Key。

---

## 安全

- 不内嵌任何密钥；平台账号、数据库账号、通知渠道凭证都由使用者自己配置。
- 默认账号 `admin / admin` 只能用于首次登录，部署到可被外部访问的网络前务必改掉。
- 控制台默认监听 8080，且能触发任意爬虫代码执行，不要直接暴露到公网；
  需要外网访问时放在反向代理与鉴权之后。
- 任务本质是执行 shell 命令，只上传你自己信任的爬虫代码。
- 持久化目录（MongoDB 数据、任务日志、上传的爬虫文件）包含业务数据与凭证，注意备份与访问权限。
- 爬虫自身的合规性由使用者负责：目标站点的抓取频率、robots 约定与数据使用边界不在本包范围内。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`crawlab`
- 仓库：https://github.com/crawlab-team/crawlab

---

## 许可证

MIT，见 `LICENSE.md`。

---

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
