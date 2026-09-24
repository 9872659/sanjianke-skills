# 三剪客 · 实时分析型数据库 Skill

MPP 架构的实时分析型数据库：Docker 五分钟起集群、本机 FE/BE 部署、MySQL 协议接入、建表分桶与数据导入、集群健康检查，以及单副本、WSL2 网段、系统参数这些必踩的坑。

---

## 前置条件

- 先决定形态：**本地体验**（Docker 一条命令）还是**生产部署**（本机集群 / K8s）。两者不能混。
- 本机部署要求：主流 AMD / ARM Linux 环境、**JDK 17+**、一个专用系统用户（不要用 root）。
- 系统参数要调整：最大文件句柄数（`nofile`）与虚拟内存区域上限（`vm.max_map_count`）。
- 网络要规划：FE 与 BE 的 `priority_networks` 必须在同一网段，BE 相关端口要在防火墙里放通。
- 一个兼容 MySQL 协议的客户端（示例使用 `mysql` 命令行）。
- K8s 路线需要一个可用的集群与 Doris Operator；存算分离路线还需要共享对象存储及凭证。

---

## 使用

本地体验（仅限开发测试）：

```bash
curl -fsSL https://doris.apache.org/files/start-doris.sh | bash
```

本机部署的大致流程：

```bash
# 调整系统参数后，分别配置并启动 FE / BE
apache-doris/fe/bin/start_fe.sh --daemon
apache-doris/be/bin/start_be.sh --daemon

# 把 BE 注册进集群（在 mysql 客户端里执行）
# ALTER SYSTEM ADD BACKEND "127.0.0.1:9050";
```

连接与验证：

```bash
mysql -uroot -P9030 -h127.0.0.1
mysql -uroot -P9030 -h127.0.0.1 -e "show frontends;"
mysql -uroot -P9030 -h127.0.0.1 -e "show backends;"
```

看到所有节点的存活列都正常，就可以建库建表、用 Stream Load 一类的正式通道导数据了。完整步骤、排障表与自检清单见 `SKILL.md`。

---

## 依赖

- 官方二进制包（从官方下载页获取），或 Docker / K8s 部署方式。
- **JDK 17+**：FE 是 Java 进程，`fe.conf` 里要指定 `JAVA_HOME`。
- 系统内核参数：提高文件句柄上限、提高虚拟内存区域上限。
- 一个 MySQL 协议客户端。
- 存算分离形态额外需要共享对象存储（S3 / HDFS / OSS 等）及访问凭证。
- 走湖仓查询时需要能访问对应的数据湖存储。

---

## 安全

- 不内嵌任何密钥。
- 默认账号是给刚起步用的：生产环境必须改密码、建业务账号、限定来源网段；不要把查询端口直接暴露到公网。
- 部署进程不要用 root 跑；官方要求建专用用户。
- 数据目录、日志目录、元数据目录的权限要收紧到该专用用户。
- 访问对象存储或数据湖的 AK/SK 等凭证走配置文件或环境变量注入，不要写进版本管理的文件里。
- 部分第三方依赖的许可证与 Apache 2.0 不兼容，官方说明需关闭部分功能才能满足合规；上线前查阅仓库的第三方许可证清单。


---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`doris`
- 仓库：https://github.com/apache/doris

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
