---
name: sanjianke-proxy-pool
slug: sanjianke-proxy-pool
displayName: 三剪客 · 免费代理 IP 池服务
description: "proxy_pool：把网上免费代理自动采集、校验、入库，再用一个本地 HTTP 接口把可用代理发给爬虫。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "proxy_pool 的部署与接入：Python 本地运行或 Docker 一条命令起服务，定时采集校验免费代理并提供 /get、/pop、/all、/count、/delete 接口，含 Redis 依赖、免费源可用率、校验地址超时等实战坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 爬虫
  - 数据分析
  - 代理池
  - 反爬
---

# 三剪客 · 免费代理 IP 池服务

爬虫上量之后最常见的一道坎是：单 IP 请求太密，很快被目标站限流或封禁，于是需要一堆轮换的代理。手工去免费代理站抄 IP 不现实——抄下来的大多已经失效，而且过几小时全换一批。

这个项目把这件事做成了服务：后台进程定时去若干公开代理站采集，逐个校验可用性，把通过的塞进 Redis 或 SSDB；你的爬虫只要向本机一个 HTTP 接口要一个 IP 就行，用完或失败再调接口把它删掉，池子会自己补货。

**上游项目**：`proxy_pool`　**仓库**：https://github.com/jhao104/proxy_pool

## 什么时候用 / 不用

**用它**：

- "爬虫单 IP 被限流了，想搞个能自动换 IP 的中间层。"——它对外就是一个 `/get` 接口，接入成本极低。
- "不想每次手工整理免费代理列表。"——调度器自动采集 + 校验 + 淘汰，池子自己维持数量。
- "想要一个 HTTP 形式的统一出口，多个爬虫共用同一批代理。"——`server` 起一个端口，团队里谁都能用。
- "临时压一下某个公开数据源，需要点抗封手段。"——Docker 起一个容器就够，不污染本机环境。
- "要按 HTTP / HTTPS 区分代理。"——接口带 `?type=https` 过滤参数。
- "想自己加代理来源，或接付费代理 API。"——代理源是插件式目录，丢一个 `.py` 文件进去就会被自动扫描到。

**不要用它**：

- **做需要长期稳定、高成功率的生产采集**——池子里装的是免费公开代理，官方自己就说明"免费的质量有限，直接跑可能不理想"。生产环境该买商业代理或走自建出口，这个项目只适合当兜底或过渡。
- **做需要固定地区 / 固定出口 IP 的业务**——免费代理的地理位置、运营商都无法保证，`PROXY_REGION` 只是尽力解析归属地，不等于可指定地区。
- **做需要登录态或强一致来源的业务**——代理出口会变，依赖会话粘性的场景（登录后带 cookie 连续操作）很容易断在换 IP 上。
- **不想维护后台常驻进程**——它必须长期跑着一个调度进程 + 一个 API 进程 + 一个 Redis，属于标准的有状态服务，不是一次性命令。
- **把它当爬虫框架用**——它只解决"提供一个可用出口"，不负责解析、调度你的采集任务、去重、入库；采集逻辑还得你自己写。
- **目标站明确禁止代理访问**——技术上能用不等于合规，使用前先看目标站的服务条款与 robots 约定。

## 安装

### 方式一：本地 Python 运行

需要先把代码拉到本地（这个项目没有发布成 pip 包）：

```bash
git clone https://github.com/jhao104/proxy_pool.git
cd proxy_pool
pip install -r requirements.txt
```

需要一个可用的 Redis 或 SSDB，然后在 `setting.py` 里改这几项：

```python
HOST = "0.0.0.0"                              # API 监听地址，只本机用就写 127.0.0.1
PORT = 5010                                   # API 监听端口
DB_CONN = 'redis://:pwd@127.0.0.1:6379/0'     # 支持 redis:// 与 ssdb:// 两种后缀
```

启动（两部分要都起来）：

```bash
# 方式一：用脚本统一管理（推荐）
./proxy_pool.sh start          # 后台启动所有服务
./proxy_pool.sh status
./proxy_pool.sh stop
./proxy_pool.sh restart

# 方式二：用 Python CLI 入口分别启动
python proxyPool.py schedule   # 采集与校验调度器
python proxyPool.py server     # API 服务
```

### 方式二：Docker

```bash
docker pull jhao104/proxy_pool:latest
docker run --env DB_CONN=redis://:password@ip:port/0 -p 5010:5010 jhao104/proxy_pool:latest
```

`DB_CONN` 环境变量会覆盖 `setting.py` 里的数据库配置。

### 方式三：docker-compose（自带 Redis，最省事）

项目根目录的 `docker-compose.yml` 里定义了代理池和 Redis 两个服务，端口映射 5010：

```bash
docker-compose up -d
```

compose 场景下服务用 `DB_CONN: "redis://@proxy_redis:6379/0"` 指向内置 Redis。

### 装完自检

```bash
curl -s http://127.0.0.1:5010/count/
curl -s http://127.0.0.1:5010/get/
```

第一条能返回计数、第二条能返回一个 `host:port`，就说明链路通了。刚启动时池子是空的，要等调度器跑完第一轮采集校验。

## 常用操作

**1. 看当前启用了哪些代理源**

```bash
python proxyPool.py fetcher
```

用于确认自己新加的源有没有被扫到，以及哪些源被黑名单挡住了。

**2. 取一个代理（最常用）**

```bash
curl -s http://127.0.0.1:5010/get/
curl -s "http://127.0.0.1:5010/get/?type=https"    # 只要支持 HTTPS 的
```

**3. 取走并删除（适合"用完即弃"）**

```bash
curl -s http://127.0.0.1:5010/pop/
```

和 `/get` 的区别是取出来就从池子里删了，适合你不打算做失败归还的场景。

**4. 看池子规模与分布**

```bash
curl -s http://127.0.0.1:5010/count/
```

返回里同时给出总数、HTTP/HTTPS 类型分布和按代理源统计的来源分布，用来判断到底是哪个源在供血。

**5. 手动删掉一个坏代理**

```bash
curl -s "http://127.0.0.1:5010/delete/?proxy=127.0.0.1:8080"
```

**6. 在爬虫里接入（带失败重试与归还）**

```python
import requests

API = "http://127.0.0.1:5010"

def get_proxy():
    return requests.get(f"{API}/get/").json()

def delete_proxy(proxy):
    requests.get(f"{API}/delete/", params={"proxy": proxy})

def fetch(url, retry=5):
    proxy = get_proxy().get("proxy")
    while retry > 0:
        try:
            return requests.get(url, timeout=10,
                                proxies={"http": f"http://{proxy}",
                                         "https": f"http://{proxy}"})
        except Exception:
            retry -= 1
            delete_proxy(proxy)          # 失败的代理立刻移出池子
            proxy = get_proxy().get("proxy")
    return None
```

**7. 不加自己的代理源，直接读库拿代理**

Redis / SSDB 里用 hash 结构存放，hash 名就是 `setting.py` 里的 `TABLE_NAME`（默认 `use_proxy`）。如果你的采集程序不方便走 HTTP，也可以直接连库读这个 hash。

**8. 新增一个自己的代理源**

在 `fetcher/sources/` 下建一个 `.py` 文件，继承 `BaseFetcher`，声明 `name` / `url` / `enabled`，实现 `fetch()` 并以 `"host:port"` 字符串形式 yield：

```python
from fetcher.baseFetcher import BaseFetcher
from util.webRequest import WebRequest

class MySourceFetcher(BaseFetcher):
    name = "mysource"
    url = "https://example.com/proxy"
    enabled = True

    def fetch(self):
        r = WebRequest().get(self.url, timeout=10)
        for proxy in self.parseProxiesFromText(r.text):
            yield proxy
```

单独调试这个源：

```bash
python -m fetcher.sources.mySource
```

调度器下一轮采集会自动扫到新文件并启用，不需要改配置。想禁用某个源，把它的 `enabled` 改成 `False`，或把**类名**加进 `PROXY_FETCHER_EXCLUDE`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 启动报连不上数据库 / 池子永远是空的 | 项目不内置数据库，`DB_CONN` 指向的 Redis 或 SSDB 必须先存在 | 先起 Redis 再起服务；图省事直接用仓库自带 `docker-compose.yml`，它会把 Redis 一起拉起来 |
| 服务起不来但看不到原因 | 后台模式把日志吞掉了 | 用 `./proxy_pool.sh start --fg` 前台启动看实时日志；容器环境本来也推荐前台模式（镜像的 ENTRYPOINT 就是前台启动） |
| `./proxy_pool.sh stop` 停不掉，或提示已在运行 | 脚本靠项目根目录的 `proxy_pool.pid` 文件识别进程 | 按官方给的顺序处理：`cat proxy_pool.pid` 看 PID → `kill <PID>` → `rm proxy_pool.pid`，再重启 |
| 拿到的代理大量请求失败、成功率很低 | 自由代理本身就是低质量来源，官方也明确说"质量有限，直接跑可能不理想" | 别指望它达到商业代理的成功率：降低单代理使用频率、每次请求都带超时、失败立刻 `/delete` 归还，必要时接自己的付费代理源 |
| 池子里代理数量始终很少 | 校验地址取不到响应，导致所有候选代理都被判为不可用 | `HTTP_URL`（默认 httpbin.org）与 `HTTPS_URL`（默认 www.qq.com）是判定基准，外网不稳或被墙就会全灭；换成你自己能稳定访问的校验地址，并按网络情况调 `VERIFY_TIMEOUT`（默认 10 秒） |
| 明明代理只失败一次就被踢了 | `MAX_FAIL_COUNT` 默认值为 `0`，即失败一次即删除 | 免费代理抖动大，想让某个代理多试几次就把这个值调大 |
| 虚拟机上启动报 `ValueError: Timezone offset does not match system offset` | 调度器时区与系统时区对不上 | 改 `setting.py` 里的 `TIMEZONE`（默认 `Asia/Shanghai`）与系统时区保持一致 |
| 新加的代理源没生效 | 源文件没被识别，或名字在黑名单里 | 用 `python proxyPool.py fetcher` 确认是否被加载；检查类名是否写进了 `PROXY_FETCHER_EXCLUDE`，以及文件里的 `enabled` 是否为 `True`；调度器是每轮重新扫描目录，等下一轮或重启调度进程 |
| 端口起不来 | 5010 被占用 | 改 `setting.py` 的 `PORT`；镜像跑的话同步改 `-p` 的映射 |
| 在容器里跑后台模式，进程莫名其妙退出 | 后台模式依赖 init 行为，容器里主进程一退容器就结束 | 容器里统一用前台模式 `./proxy_pool.sh start --fg` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 核心功能：向公开代理站抓取候选 IP，并向校验地址发起探测请求判断代理是否可用 |
| 读取文件 | 是 | 读取项目目录下的 `setting.py`、`fetcher/sources/` 下的代理源文件、`proxy_pool.pid` |
| 写入文件 | 是 | 服务启动后会在项目根目录生成 `proxy_pool.pid` 记录子进程；运行日志会落盘；代理数据写入 Redis / SSDB |
| 凭证 | 是 | `DB_CONN` 里通常含 Redis / SSDB 密码；用 `docker run` 时通过 `DB_CONN` 环境变量传入，注意不要留在命令历史里 |
| 子进程 / 后台常驻 | 是 | `proxy_pool.sh start` 会拉起调度器与 API 两个长期运行的子进程；同时依赖一个常驻的 Redis / SSDB |

## 触发场景

- "我的爬虫被封 IP 了，怎么自动换 IP？"
- "帮我搭个免费代理池，爬虫直接调接口取代理。"
- "起一个代理池服务，Docker 部署。"
- "代理池里的 IP 全是坏的，帮我看为什么。"
- "怎么给这个代理池加一个自己的代理来源？"
- "代理池服务起不来 / 停不掉。"

## 能力边界

**覆盖**：

- 代理采集：插件式代理源目录，内置多个公开免费源，支持新增自定义源，调度器自动扫描并热加载
- 代理校验：用可配置的 HTTP / HTTPS 校验地址逐个探测，按 `VERIFY_TIMEOUT` 判超时、按 `MAX_FAIL_COUNT` 判淘汰
- 存储：Redis 与 SSDB 两种后端，hash 结构，表名可配
- 服务接口：`/` 列表、`/get` 随机取、`/pop` 取出即删、`/all` 全量、`/count` 统计、`/delete` 指定删除，`/get` `/pop` `/all` 支持 `?type=https` 过滤
- 部署形态：本地 Python 运行、Docker 单容器、docker-compose 带 Redis 编排
- 运维：`proxy_pool.sh` 的 start / stop / restart / status，PID 文件管理，前台模式
- 调度：基于 APScheduler 的定时采集与校验，池子低于下限时先补货

**不覆盖**：

- 采集业务本身：不负责抓取目标站、不解析页面、不做去重与入库，你拿到的只是一个代理地址
- 代理质量保证：不保证成功率、延迟、地区、匿名等级，免费源质量由其来源决定
- 高匿名 / 住宅 / 数据中心代理的采购：项目只做"汇集与校验"，付费代理需要你自己接成代理源
- 认证与配额：API 本身没有鉴权，谁都能调，不能直接暴露到公网
- 分布式一致性调度：多个调度实例同时跑可能重复采集同一批源，官方没提供集群协调
- 反爬对抗策略：不做 UA 轮换、验证码识别、请求指纹伪装，这些要你自己在爬虫侧解决

## 依赖条件

- Python 3（仓库存档徽标显示支持 3.8 / 3.9 / 3.10 / 3.11，具体以仓库当前说明为准）
- Python 依赖：`pip install -r requirements.txt`；跑测试另需 `pip install -r requirements-test.txt`
- 一个 Redis 或 SSDB 实例，连接串写在 `setting.py` 的 `DB_CONN`
- 能访问外网：既为了爬公开代理站，也为了访问代理校验地址
- Docker 路线需要 Docker；docker-compose 路线需要 Docker Compose
- 无账号与 API Key 要求（除非你自己接的代理源需要）
- `proxy_pool.sh` 是 shell 脚本，Windows 原生环境请用 `python proxyPool.py schedule` / `server` 两个命令代替

## 已知限制

1. 内置来源是公开免费代理，可用率与稳定性天然有限，官方文档也直言"质量有限"。
2. API 没有内置鉴权机制，`HOST` 默认监听 `0.0.0.0`，部署时务必自己加网络层访问控制。
3. 校验的判定基准是 `HTTP_URL` / `HTTPS_URL` 两个固定地址，这两个地址的可达性直接决定池子存活率。
4. `MAX_FAIL_COUNT` 默认为 `0`，免费代理抖动一次就会被移除，池子规模会比较颠簸。
5. 代理源的两个 API 版本口径曾变化（早期为 `fetcher/proxyFetcher.py` 集中定义，现为 `fetcher/sources/` 插件目录），老教程里的写法不一定适用，以本机仓库结构为准。
6. README 与站点文档在个别细节上表述不同（例如黑名单填 `name` 还是类名），以本机 `setting.py` 与 `python proxyPool.py fetcher` 的实际输出为准。
7. 采集间隔、池子下限等调度细节以 `setting.py` 与仓库文档为准，不同版本可能调整。

## 自检清单

执行前：

- [ ] Redis 或 SSDB 已经起来且 `DB_CONN` 能连（这是最常见的启动失败原因）
- [ ] 确认 `HOST`：只给自己用就设 `127.0.0.1`，不要一上来就 `0.0.0.0` 暴露到公网
- [ ] 确认服务器能访问 `HTTP_URL` / `HTTPS_URL` 这两个校验地址，否则池子会一直空
- [ ] 需要 HTTPS 代理的场景，确认取代理时带上 `?type=https`
- [ ] 使用 Docker 时确认 `DB_CONN` 指向的是容器能解析到的地址（compose 内用服务名，不是 127.0.0.1）

执行后：

- [ ] `curl http://127.0.0.1:5010/count/` 能看到总数与来源分布，且等第一轮采集后数字在涨
- [ ] `curl http://127.0.0.1:5010/get/` 能返回 `host:port`
- [ ] 拿这个代理实际请求一次目标站，确认它真的能用（池里有记录 ≠ 当下可用）
- [ ] 爬虫侧确认：每次请求带超时、失败会调 `/delete` 归还
- [ ] `./proxy_pool.sh status` 显示两个进程都在，日志无持续报错
- [ ] 确认没有把 5010 端口直接暴露到公网

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/jhao104/proxy_pool | 上游仓库（安装与完整文档以它为准） |
| https://jhao104.github.io/proxy_pool/getting-started/ | 官方快速开始：依赖安装、配置、启动与故障排除 |
| https://jhao104.github.io/proxy_pool/configuration/ | 官方配置参考：HOST / PORT / DB_CONN / 校验与调度项 |
| https://jhao104.github.io/proxy_pool/api/ | 官方 API 说明：接口列表与调用示例 |
| https://jhao104.github.io/proxy_pool/docker/ | 官方 Docker 部署：镜像、compose、容器注意事项 |
| https://jhao104.github.io/proxy_pool/extending/fetcher/ | 官方扩展说明：自定义代理源与 BaseFetcher 约定 |

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
