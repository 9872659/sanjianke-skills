# 三剪客 · 微服务电商商城系统 Skill

mall-swarm：微服务电商商城系统 的安装、常用命令与避坑要点

---

## 前置条件

- 一台 Linux 服务器。官方文档的部署示例以 **CentOS 7.6** 为例。
- **推荐 6G 以上内存**。这套系统要同时跑数据库、缓存、消息队列、搜索引擎、日志链路与注册配置中心，再加六个应用服务，内存不足会表现为容器被反复杀掉。
- 已安装 **Docker 与 Docker Compose**。
- 已安装 **JDK 与 Maven**，用于构建应用镜像；本地 Maven 仓库需可写。
- 宿主机上提前建好挂载目录（如 `/mydata/nginx/`、`/mydata/logstash`、`/mydata/elasticsearch/data`），并把 Nginx、Logstash 的配置文件放到位，否则容器会因为挂载源不存在而起不来。
- 调整过 Elasticsearch 需要的系统内核参数 `vm.max_map_count`。
- 一个可用的服务器 IP 或域名，供服务注册与控制台访问。
- 不需要第三方大模型或算力服务，纯自建中间件。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短跑通路径（官方文档给出的顺序）：

```bash
# 1. 起依赖的系统组件
docker-compose -f docker-compose-env.yml up -d

# 2. Elasticsearch 需要的系统参数（新机器上必做）
sysctl -w vm.max_map_count=262144
sysctl -p

# 3. Logstash 需要的挂载目录与插件
mkdir /mydata/logstash
logstash-plugin install logstash-codec-json_lines

# 4. 构建并推送 6 个应用镜像：mall-monitor / mall-gateway / mall-auth / mall-admin / mall-portal / mall-search

# 5. 把项目 config 目录下的配置逐条导入 Nacos，Data Id 要和文件名一一对应

# 6. 起应用服务
docker-compose -f docker-compose-app.yml up -d
```

两个 Compose 脚本与各配置文件都在仓库的 `document/` 目录下：

- `document/docker/docker-compose-env.yml`
- `document/docker/docker-compose-app.yml`
- `document/elk/logstash.conf`

启动完成后可以访问：

- API 文档：`http://<你的服务器IP>:8201/doc.html`
- 注册中心与配置中心（Nacos）：`http://<你的服务器IP>:8848/nacos/`
- 监控中心：`http://<你的服务器IP>:8101`
- 日志收集（Kibana）：`http://<你的服务器IP>:5601`

组件版本清单、打包注意事项与更深的使用方式，以 `SKILL.md` 和上游仓库当前文档为准。

---

## 依赖

- Docker、Docker Compose
- JDK、Maven
- 运行期系统组件（版本取自官方文档）：Mysql 5.7、Redis 7.0、MongoDb 4.x、RabbitMq 3.9、Nginx 1.22、Elasticsearch 7.17.3、Logstash 7.17.3、Kibana 7.17.3、Nacos 2.1.0
- Logstash 插件 `logstash-codec-json_lines`
- 可选：Portainer（图形化管理容器）
- 可选：前端工程（运营后台、商城前端）用于联调，但不在本包范围内

---

## 安全

- 不内嵌任何密钥
- 默认配置里的数据库口令、RabbitMQ 账号、对象存储密钥等都属于示例值，对外提供服务前必须全部替换，并改为从环境变量或密钥管理系统注入
- Nacos 控制台、监控中心、Kibana、RabbitMQ 管理端、Portainer 这些都是带管理权限的入口，未经加固不要直接暴露到公网；至少加访问控制并限制来源 IP
- 不要以 root 身份长期运行容器；生产环境按最小权限挂载卷与分配端口
- 端口映射尽量只绑定内网地址，搜索引擎、消息队列、数据库的端口不要对公网开放
- 官方给的演示口令（后台管理账号、监控中心账号等）只用于本地验证，不要带到线上，更不要把演示口令当成初始密码继续用
- 部署脚本会挂载宿主机目录，注意不要把敏感目录（如 `/`、`/etc`）误挂进容器
- 日志链路会把业务日志集中到 Kibana，其中的订单、会员等信息属于个人信息，收集前先确认合规要求并做脱敏

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`mall-swarm`
- 仓库：https://github.com/macrozheng/mall-swarm

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
