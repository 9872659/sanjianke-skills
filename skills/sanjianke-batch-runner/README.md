# 批量调度 一千条任务排队跑完

**1,000 条任务一条命令跑完，排队、体检、报价全程 0 点。** 走 [api.a7w.cn](https://api.a7w.cn/) 的提交与查询端点，零依赖，只用 Python 标准库。

这个包的位置很明确：**内容已经决定好、只差把它们送出去的那一刻**。清单里每一行是一份提交请求，本包负责并发、轮询、重试、落盘、算钱、守预算。

---

## 为什么需要这一层

一百条任务还能手点，一千条就只能靠脚本；脚本写到第三版一定会遇到这四件事：

- 中途断了，不知道哪几条跑过、哪几条没跑；
- 某一条 500，整批停在原地；
- 跑了半天才发现预算早超了；
- 想查进度，结果每查一次都在扣钱。

本包把这四件事做成默认动作：**断点落盘、失败退避重试、预算守卫、只打免费查询视图。**

---

## 断点续跑（核心）

```bash
python3 scripts/run.py run --file 1000条.jsonl --yes
# ... 跑到第 412 条断了 ...
python3 scripts/run.py run --file 1000条.jsonl --yes   # 自动从 413 接着跑
```

状态文件默认 `<清单名>.state.json`，每条记录 `taskId` / 状态 / 实扣点数 / 尝试次数。每完成一条用
「临时文件 + `os.replace` + `fsync`」原子重写，断电最多丢最后一条。

| 状态 | 含义 | 重跑时 |
|---|---|---|
| `done` | 查到完成 | 跳过 |
| `submitted` | 提交成功、结果交给后续包取 | 跳过 |
| `failed` | 提交失败 / 任务失败 | 跳过；加 `--retry-failed` 才补 |
| `unknown` | 上次中断时正在提交，可能已建任务 | 跳过；核对台账后加 `--retry-failed` |
| `running` | 本次在飞 | 进程内状态 |

Ctrl-C / SIGTERM 只置停止位，在飞的任务收尾、状态落盘、退出码 `130`。

---

## 预算守卫：两道闸门，一个请求都不多发

```
--yes 缺失        → exit 4，并告诉你这次要发几条、多少点
开跑前合计超预算   → exit 5，一个请求都不发
跑的过程中要超线   → 停手，状态落盘，剩下的留给下次（exit 5）
```

`--budget` 单位是**点**，1 元 = 100 点，默认 10000 点（100 元）。
预算按「已花 + 剩余预估」算：已花取响应里的 `cost`，没有就退回清单里的 `points`。

---

## 并发与重试

- `--concurrency` 默认 **4**，上限 16；先 4 路跑稳，再往上加。
- `--retry` 默认 2 次，退避 2s / 4s / 8s；参数类错误（400 / 401 / 403 / 404 / 409 / 422）当场记失败，重试不解决问题。
- 轮询间隔 `--poll-interval` 默认 5 秒，单条最多等 `--wait` 秒（默认 1800）。
- 进度每完成一条打一行到 stderr：`[12/1000] 1.2% · 完成 10 · 已提交 1 · 已用 72 点 · 4.5 条/分 · 剩余 3 小时 39 分`。

---

## 清单格式

JSONL，一行一个任务，空行与 `#` 开头的行忽略：

```json
{"id": "img-0001", "endpoint": "/api/v1/images/generations", "body": {"model": "gpt-image-2.6", "prompt": "分镜 1：雨夜街头", "n": 1}}
{"id": "enh-0001", "endpoint": "/api/v1/video/viapi/enhance", "body": {"videoUrl": "https://oss.gpu.likeadmin.cn/openapi/a.mp4", "duration": 15}}
{"id": "app-0001", "endpoint": "/api/v1/apps/nano_banana/submit", "body": {"prompt": "商品主图"}, "points": 72}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一名字；重复在体检时退 2 |
| `endpoint` | 是 | 只认 catalog 里的 72 个 POST 提交端点 |
| `body` | 是 | 原样发给上游；`videoUrl` 先过白名单本地预检 |
| `points` | 否 | 预估点数；不写按价目表现算（按秒 / 按张 / 按字） |
| `poll` | 否 | `tasks` / `video` / `none` |

**videoUrl 一定先过上传**：本地素材先 `upload --file 素材.mp4` 换 `oss.gpu.likeadmin.cn/openapi/…` 地址，再写进 `body.videoUrl`。外站地址在体检阶段就会被拦下，省一次 400 `url_not_allowed`。

---

## 快速开始

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"

# 2) 免费：自检
python3 scripts/run.py doctor

# 3) 免费：清单体检 + 报价 + 工期
python3 scripts/run.py plan --file 1000条.jsonl
python3 scripts/run.py cost --file 1000条.jsonl --concurrency 4

# 4) 开跑
python3 scripts/run.py run --file 1000条.jsonl --concurrency 4 --retry 2 --yes

# 5) 看断点
python3 scripts/run.py status --file 1000条.jsonl
```

---

## 用法示例

```bash
# 只看请求不花钱
python3 scripts/run.py run --file 1000条.jsonl --dry-run

# 只补失败 / 中断在飞的，顺手写报告
python3 scripts/run.py run --file 1000条.jsonl --retry-failed --report 报告 --yes

# 预算卡紧一点：预估 20,000 点，只批 5,000 点
python3 scripts/run.py run --file 1000条.jsonl --budget 5000 --yes

# 上传素材换托管地址（0 点）
python3 scripts/run.py upload --file 素材.mp4

# 机器可读
python3 scripts/run.py cost --file 1000条.jsonl --json
```

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | **0 点** | 72 个提交端点 + 单价 + 轮询方式 |
| `plan` | **0 点** | 清单逐行校验 + 打印请求 + 轮询地址 |
| `cost` | **0 点** | 合计点数 + 按端点分组 + 工期 + 余量 |
| `status` | **0 点** | 完成 / 已提交 / 失败 / 未开始 |
| `doctor` | **0 点** | Key、余额、115 条价目、22 应用、3 条提交探针、流水前后比对 |
| `upload` | **0 点** | 上传本地文件换托管地址 |
| `run` | **按点** | 并发提交 + 免费轮询 + 重试 + 断点 + 预算守卫 |

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--file` | — | JSONL 清单路径 |
| `--state` | `<清单>.state.json` | 状态文件路径 |
| `--concurrency` | 4 | 并发数，1~16 |
| `--retry` | 2 | 单条提交重试次数，退避 2s / 4s / 8s |
| `--retry-failed` | — | 连失败 / 中断在飞的一起补 |
| `--poll-interval` / `--wait` | 5 / 1800 | 轮询间隔 / 单条最多等多少秒 |
| `--report` | — | 结果表与失败清单写到哪个目录 |
| `--budget` | 10000 | 点数上限（单位：点，1 元 = 100 点） |
| `--yes` / `--dry-run` / `--json` | — | 确认 / 只打印 / 只输出一个 JSON 文档 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（清单格式 / 未知端点 / 缺 points / id 重复 / 选项缩写） |
| `3` | 自检未过 |
| `4` | 缺 `--yes` |
| `5` | 超 `--budget` —— **一个请求都不发** |
| `6` | 有任务失败（状态已落盘，补跑只补失败的） |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C / SIGTERM 中断 |

---

## `--json` 契约

```json
{"ok": true, "ran": 5, "skipped": 0, "counts": {"done": 4, "submitted": 1},
 "spentPoints": 534.0, "budget": 10000, "elapsed": 2.1,
 "state": "1000条.jsonl.state.json", "report": null}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…一个请求都没发。"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档，进度全部走 stderr。

---

## 实测记录

```
2026-11-08  真实环境 api.a7w.cn（只读探针，本轮花费 0 点）
  doctor        9 项全 √：115 条价目 16 档一致 · 22 应用 / 29 个音频接口 · 3 条提交探针 400
  流水          共 7,888 条；跑前跑后最近一笔都是 11-08 01:46:12 的 -6（sync:/images/generations）
  清单报价      8 条 = 1,806.32 点 = 18.06 元；4 并发 × 45 秒 ≈ 1 分 30 秒
  --help        父命令 + 7 个子命令全部 exit=0
  GBK 控制台    PYTHONIOENCODING=gbk python run.py doctor → exit=0

2026-11-08  本地 mock 网关（127.0.0.1，不碰 api.a7w.cn，费用为模拟值）
  5 条 / 2 并发  2 秒跑完：完成 4、已提交 1（应用层不自动轮询）
  500 重试       同一条第一次 500、第二次成功，状态里 attempts=2
  断点续跑       再跑同一条命令：跳过 5 条，exit 0
  中断收尾       停止位触发后 1.2 秒收尾落盘，exit 130，4 条里只发出 1 条
  预算守卫（跑中）预估 5 点/条、实际 100 点/条、预算 50 点：第 1 条后停手，exit 5，剩 3 条
```

---

## 文件结构

```
sanjianke-batch-runner/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       端点原文与实测结构
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 边界

- 应用层任务的查询接口按次计费，本包默认只提交、不轮询；出片后到 `sanjianke-billing` 或对应能力包取结果。
- 单条任务最多等 `--wait` 秒（默认 30 分钟），超时记为 `submitted`，不重复提交。
- 价目表里没有公开单价的端点（29 个音频接口、图片数字人、视频对口型）在清单这一行写 `points`，预算按它算。
- 真实扣费以响应里的 `cost` / `usage.points_cost` 与任务台账的 `actualPrice` 为准，`cost` 给的是预估。

---

## 免责

- 生成内容的合规责任在使用者：素材授权、肖像权、平台规则由执行方确认。

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
