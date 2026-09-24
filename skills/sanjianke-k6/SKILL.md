---
name: sanjianke-k6
slug: sanjianke-k6
displayName: 三剪客 · k6 负载测试
description: "{desc}。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "{summary}。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
  - 性能测试
---

# 三剪客 · k6 负载测试

想看接口在 100 个并发下会不会垮、想量化一次改动的响应时间退化、想让每次上线的性能问题自动拦住——这些都需要"可重复地打流量并拿到数字"。k6 把这件事收敛成**一个 Go 写的单文件二进制 + 一段 JavaScript 脚本**：脚本里声明并发模型和阈值，命令行一条 `k6 run` 就能跑，判据不达标直接给非零退出码，天然适合塞进 CI。

脚本用 JS 写，但**不是 Node**：没有 npm 生态，没有浏览器 API，文件读取、并发模型、指标聚合都由 k6 自己提供。理解这一点，后面一半的坑就不会踩。

**上游项目**：`k6`　**仓库**：https://github.com/grafana/k6

## 什么时候用 / 不用

**用它**：

- "这个接口压到 200 并发，p95 会不会破 300ms？"——`options.thresholds` 写 `p(95)<300`，跑完直接给结论和退出码。
- "把压测接进 CI，性能退化了就卡住合并。"——阈值失败返回非零退出码，流水线判一个码即可。
- "我要模拟真实用户路径：登录、拿 token、下单，中间思考 1 秒。"——脚本里顺序写请求 + `sleep(1)`，比压测工具的录制回放可读得多。
- "先固定 50 并发跑 1 分钟，再看阶梯加压到 200 是什么时候开始出错。"——`vus`/`duration` 换成 `stages` 或用 `scenarios` 描述。
- "结果要进 Prometheus / InfluxDB / Datadog 看实时曲线。"——`--out` 直接推给外部存储，不用自己转数据。

**不要用它**：

- **想测浏览器里的真实渲染**——默认 runtime 没有 DOM。需要浏览器交互得用带浏览器的 k6 镜像和 Browser 模块，这是另一套用法和资源开销，普通 HTTP 压测别掺进来。
- **想在脚本里跑 Node 生态**——`require` 是 k6 自己实现的，Node 内置模块和 npm 包基本用不了。算法依赖重的话换 Node + autocannon / artillery。
- **想直接复用录制的浏览器操作**——k6 不做录制回放；这类需求看 Playwright / Selenium 或它们的压测封装。
- **只想要一次性的简单并发请求、脚本都不想写**——`ab`、`hey`、`wrk` 更快，或者直接 `xargs -P` 也行。
- **没有阈值就当成"性能门禁"**——k6 在没有 threshold 时**总是退出 0**，跑失败也不会让 CI 红。要门禁必须显式写阈值。

## 安装

包管理器是最省事的路子（官方也这么推荐）。Debian / Ubuntu：

```bash
curl -fsSL https://dl.k6.io/key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

Fedora / CentOS：

```bash
sudo dnf install https://dl.k6.io/rpm/repo.rpm
sudo dnf install k6
```

macOS（Homebrew）：

```bash
brew install k6
```

Windows：

```powershell
choco install k6
winget install k6 --source winget
```

Docker（三种常见用法，注意容器里看不到宿主机文件）：

```bash
docker pull grafana/k6

# 生成一个脚本骨架到当前目录
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/app" -w /app grafana/k6 new

# 脚本通过 stdin 喂进容器跑（最常用）
docker run --rm -i grafana/k6 run - < script.js

# 挂载脚本目录 + 输出目录
docker run -it --rm -v "$PWD:/scripts" -v "$PWD/out:/jsonoutput" \
  grafana/k6 run --out json=/jsonoutput/result.json /scripts/script.js
```

也提供 MSI 安装包与 GitHub Releases 的二进制压缩包；具体地址随版本变化，以官方文档的安装页为准。装完确认：

```bash
k6 version
```

## 常用操作

**1. 生成骨架，然后跑第一个压测**

```bash
k6 new                     # 生成 script.js
k6 new my-test.js          # 指定文件名
k6 run script.js
```

**2. 最小可跑的压测脚本（直接抄这份改）**

```js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],      // 错误率低于 1%
    http_req_duration: ['p(95)<200'],    // 95 分位低于 200ms
  },
};

export default function () {
  const res = http.get('https://example.com/');
  check(res, { 'status was 200': (r) => r.status === 200 });
  sleep(1);
}
```

`vus` 是并发虚拟用户数，`duration` 是总时长；`check` 只记录成功/失败，**本身不影响退出码**，要门禁得配 `checks: ['rate>0.9']` 这类阈值。

**3. 用 stages 做阶梯加压与退坡**

```bash
k6 run -s 30s:10 -s 1m:50 -s 30s:0 script.js
```

对应脚本内写法：

```js
export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m',  target: 50 },
    { duration: '30s', target: 0 },
  ],
};
```

CLI 上的长名是 `--stage`（可重复），没有 `--stages`，也没有 `--ramp-up`。

**4. 一条命令临时覆盖并发与时长，并给脚本传变量**

```bash
k6 run -u 100 -d 3m script.js
k6 run -e BASE_URL=https://staging.example.com -e TOKEN=abc script.js
```

脚本里用 `__ENV.BASE_URL` 取值。注意 `-e` 只给脚本传变量，**不配置 k6 自身的选项**：`-e K6_ITERATIONS=120` 不会改迭代数，要改得写成环境变量前缀 `K6_ITERATIONS=120 k6 run script.js`。

**5. 推指标到外部存储，并自定义摘要输出**

```bash
# 输出到 JSON 文件
k6 run --out json=result.json script.js

# Prometheus remote write（实验模块，靠环境变量配地址）
K6_PROMETHEUS_RW_SERVER_URL=http://localhost:9090/api/v1/write \
  k6 run -o experimental-prometheus-rw script.js

# 常用开关
k6 run --summary-mode=full script.js       # compact（默认）/ full / disabled
k6 run --summary-export=summary.json script.js
k6 run --quiet script.js
```

脚本内接管摘要（导出 `handleSummary` 后默认摘要不再打印）：

```js
export function handleSummary(data) {
  return {
    stdout: JSON.stringify(data, null, 2),
    'summary.json': JSON.stringify(data),
  };
}
```

**6. 先干跑一次配置自检，再真正压**

```bash
k6 inspect script.js                       # 打印解析后的完整配置，确认参数生效
k6 run --no-setup --no-teardown script.js  # 跳过 setup/teardown，只跑主流程
k6 run --paused script.js                  # 用 REST API 控制时需要显式开启地址
```

**7. 配置文件与环境变量**

```bash
k6 run --config options.json script.js
K6_VUS=10 K6_DURATION=10s k6 run script.js
```

优先级从低到高：默认值 → `--config` 配置文件 → 脚本内 `options` → 环境变量 → 命令行 flag（flag 最高）。默认配置文件位置：Linux/macOS 是 `~/.config/k6/config.json`、`~/Library/Application Support/k6/config.json`，Windows 是 `%AppData%/k6/config.json`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 阈值明明失败了，CI 还是绿的 | 脚本里**根本没写 thresholds**——没有阈值时 k6 总是退出 0 | 必须显式声明 `thresholds`；阈值失败时退出码是 `99`，别只判"非 0 就算崩" |
| `check` 全部失败但退出码仍是 0 | `check` 只统计不判定 | 加一条 `checks: ['rate>0.9']` 阈值，把 check 成功率变成门禁条件 |
| 脚本在 init 阶段发 HTTP 请求直接报错 | init 上下文每个 VU 都会执行一次，且**不允许发请求** | init 只做静态准备（常量、`open()` 读文件、构造 SharedArray）；请求放到 `default` 函数里 |
| VU 之间共享的计数器不生效 / 状态互相串 | 每个 VU 是独立的 JS 虚拟机，**不共享状态**；且每次迭代会重置 VU（清 cookie、可能断连接） | 需要跨 VU 只读共享就用 `SharedArray`；需要读写共享状态用 setup/teardown 或外部存储，别指望模块级变量 |
| 报 `new SharedArray must be called in the init context` | `SharedArray` 只能在 init 上下文构造 | 把构造语句提到文件顶层（`default` 函数外） |
| SharedArray 反而更吃内存 / 行为和普通数组一样 | 对它调 `.filter()`/`.map()`、`JSON.stringify` 整体、或从 `setup()` 返回，都会退化成普通数组 | 只在 init 构造并在 VU 里按下标读取；派生数据在 init 里一次性算好 |
| 想开 REST API / 外部控制，发现连不上 | 较新版本（v2 起）REST API **默认关闭** | 显式加 `--address`（短名 `-a`）或设 `K6_ADDRESS`；被移除的 `pause`/`resume`/`scale`/`status` 子命令不要再用 |
| 升级后发现 `k6 login`、`k6 cloud script.js`、`--upload-only` 全都不认识 | 云相关命令已迁移：`k6 login` 变 `k6 cloud login`，位置参数变 `k6 cloud run`，上传变 `k6 cloud upload`；所有 `k6 cloud` 子命令都要求先配好 stack | 按新形式改写命令；`K6_CLOUD_TOKEN` / `K6_CLOUD_STACK_ID` 配好；InfluxDB 登录无替代，改走 `K6_INFLUXDB_ADDR` 环境变量 + `--out influxdb` |
| `--no-summary`、`--summary-mode=legacy` 报未知参数 | 这两个写法已被移除，摘要模式现在只有 compact（默认）/ full / disabled | 用 `--summary-mode=disabled` 关摘要 |
| Docker 里跑 `k6 run script.js` 报找不到文件 | 容器里没有宿主机的文件系统 | 要么挂载目录并给容器内路径，要么 `docker run --rm -i grafana/k6 run - < script.js` 走 stdin |
| 命令行设了 `K6_VUS` 却不生效 / 优先级混乱 | 选项来源有固定优先级，环境变量高于脚本 `options`、低于 CLI flag | 记住从低到高：默认值 → 配置文件 → 脚本 options → 环境变量 → CLI flag；调试时先 `k6 inspect` 看最终解析结果 |
| `setup()` 卡住或超时 | setup 默认超时 60s | 把耗时初始化拆出去或调大超时（云上另有上限）；另外 setup 抛异常时 `teardown()` **不会**执行，清理逻辑别只写在 teardown 里 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 压测本身就是对目标地址发大量并发请求；安装与 `--out` 推指标时也需联网 |
| 读取文件 | 是 | `open()` 读取 init 阶段的数据文件；`--config`、脚本文件本身 |
| 写入文件 | 是 | `--out json=...`、`--summary-export`、`handleSummary` 写出的报告文件 |
| 凭证 | 视情况 | 纯自建地址压测无需凭证；云服务需要 `K6_CLOUD_TOKEN` / stack 配置；压测受保护接口时 token 通过 `-e` 或环境变量传入 |
| 子进程 / 后台常驻 | 否 | k6 是单次执行的前台命令，跑完即退；没有需要长期常驻的守护进程 |

## 触发场景

- "帮我写个压测脚本，压这个接口。"
- "这个接口 100 并发下 p95 是多少？"
- "压测接进 CI，性能不达标就让流水线失败。"
- "模拟用户登录后下单的完整链路，加上思考时间。"
- "阶梯加压，看多少并发开始出错。"
- "把压测指标推到 Prometheus / InfluxDB。"
- "我升级了 k6，原来那条 `k6 login` 命令怎么不能用了？"

## 能力边界

**覆盖**：

- 用 JavaScript（也支持 TypeScript 脚本，类型检查不是它的职责）描述并发模型：`vus`/`duration`、`iterations`、`stages` 阶梯、`scenarios` 多场景组合
- 内置 HTTP/HTTPS、gRPC、WebSocket、Redis 等协议模块，以及 `check`、`group`、`sleep`、`fail` 等脚本函数
- 指标聚合与阈值判定：Counter / Gauge / Rate / Trend 四类指标的聚合器与阈值表达式，支持标签维度和 `abortOnFail`
- 结果输出：JSON / CSV 文件，以及实时推送到 Prometheus remote write、InfluxDB、Datadog、New Relic、OpenTelemetry、StatsD、Kafka 等外部系统
- `handleSummary` 自定义摘要、`--summary-mode` 控制默认摘要、`setup`/`teardown` 与 `handleSummary` 生命周期钩子
- 通过 xk6 用扩展模块自建二进制，补充官方版没有的能力
- 退出码语义可做自动化门禁（阈值失败为 99）

**不覆盖**：

- 浏览器真实渲染与前端性能指标（需要带浏览器的镜像 + Browser 模块，属另一套用法）
- 录制回放式脚本生成（不提供录制器）
- Node.js 生态：npm 包与 Node 内置模块基本不可用，`require()` 是自定义实现
- GUI 报告与长期数据留存（要图形化与历史趋势得自己接外部时序库或云端服务）
- 被压服务的调优与容量规划结论——k6 只给数据，不给根因
- 非 HTTP 类的冷门协议，除非有对应扩展并经 xk6 编译

## 依赖条件

- 单文件二进制，无运行时依赖；包管理器、MSI、Docker 镜像、Release 压缩包均可安装
- 脚本语言是 k6 内嵌的 JS 运行时，**不需要装 Node.js**
- 运行环境：Linux / macOS / Windows 都有官方构建；Docker 方式额外需要 Docker
- 纯本地压测不需要账号或 API Key；使用云服务需要 token 与 stack 配置
- 用 xk6 自建扩展二进制时，本机需要有 Go 工具链（或用 xk6 的 Docker 镜像规避）

## 已知限制

1. 没有阈值时 k6 退出码恒为 0，不能当性能门禁用——这是最容易误判的一条。
2. VU 之间互不共享状态，跨 VU 通信要靠外部系统；模块级变量不能当共享计数器。
3. 每次迭代会重置 VU 上下文，cookie 与连接不保证在迭代之间保留。
4. init 上下文每个 VU 执行一次且禁止发请求，重初始化逻辑会成倍放大开销。
5. 命令行各版本间存在破坏性变更：云命令迁移、`pause`/`resume`/`scale`/`status` 被移除、REST API 默认关闭、`--no-summary` 与 `--summary-mode=legacy` 被删。以本机 `k6 --help` 与子命令 `--help` 为准。
6. 官方文档站点给出的版本号会持续前进，本文提到"v2 起"的行为变化请以本机实际版本核对。
7. Prometheus remote write 输出被官方标注为实验性质，参数与稳定性可能变化。
8. 部分能力（如某些协议扩展）不在官方二进制里，需要 xk6 自建。

## 自检清单

执行前：

- [ ] `k6 version` 确认版本，并据此核对下文命令形式（云命令、REST API、摘要参数在不同版本差异大）
- [ ] 脚本里确实写了 `thresholds`——否则这次压测不会给出失败信号
- [ ] 目标地址与压测环境已确认：**别把压测流量打到生产**
- [ ] 并发量与时长量级先小后大（先 `-u 1 -d 10s` 验证脚本，再放大）
- [ ] `k6 inspect script.js` 看一遍最终生效的配置，确认命令行参数与脚本 `options` 的合并结果符合预期
- [ ] 需要读数据文件时，确认文件在 init 阶段用 `open()` 读，并考虑用 `SharedArray` 避免每个 VU 各读一份
- [ ] 接 CI 时确认退出码判定包含 `99`（阈值失败）而不是只判非 0

执行后：

- [ ] 记录 p95/p99、错误率与 RPS 的基线数字，便于下次对比
- [ ] 检查 `http_req_failed` 与 `checks` 失败率，确认失败是压测目标的问题还是脚本写错
- [ ] 确认退出码含义（0 通过 / 99 阈值失败 / 其他为中断或错误），并在 CI 日志里保留摘要
- [ ] 若用 `--out` 推外部存储，确认数据真的落库而不是只打印到 stdout
- [ ] 压测产生的测试数据与残留资源（订单、账号、文件）清理掉

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/grafana/k6 | 上游仓库（安装与完整文档以它为准） |
| https://grafana.com/docs/k6/latest/ | 官方文档：CLI 参数参考、阈值语法、结果输出、各版本迁移说明 |

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
