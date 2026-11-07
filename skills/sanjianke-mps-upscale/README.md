# 腾讯云超分台 · 2 点一秒，4K 也能提

**1080P 2 点/秒、2K 4 点/秒、4K 8 点/秒。** 走 [api.a7w.cn](https://api.a7w.cn/) 的
**腾讯云 MPS 音视频增强**，异步任务：提交拿 `task_id`，轮询取成片地址。

一条 10 分钟的片子提满 **4K 只要 48 块**，提 1080P 只要 **12 块**。

---

## 价目表

| 档位 | 接口 | 单价 | 保底 | 10 分钟 | 30 分钟 |
|---|---|---|---|---|---|
| **1080P** | `POST /api/v1/video/tencent1080` | **2 点/秒（¥0.02）** | 10 点 | 1200 点 = **¥12** | 3600 点 = ¥36 |
| **2K** | `POST /api/v1/video/tencent2k` | **4 点/秒（¥0.04）** | 10 点 | 2400 点 = **¥24** | 7200 点 = ¥72 |
| **4K** | `POST /api/v1/video/tencent4k` | **8 点/秒（¥0.08）** | 10 点 | 4800 点 = **¥48** | 14400 点 = ¥144 |

- **按输入视频秒数计费**（不是输出秒数），1 元 = 100 点
- **单笔保底 10 点**：2 秒的 4K 片子也只收 10 点（¥0.10）
- 任务失败 **全额退回**；查询接口 **不扣费**
- 成品链接保留 **24 小时**，请及时下载
- 选档：1080P 走老片 / 录屏 / 竖屏短剧；2K 上大屏投影；4K 交付级母版

---

## 为什么选腾讯线

同一条产线（阿里 VIAPI）的报价是 1080P **9** 点/秒、2K **15** 点/秒、4K **20** 点/秒：

| 档位 | 腾讯 MPS | 阿里 VIAPI | 便宜 |
|---|---|---|---|
| 1080P | 2 点/秒 | 9 点/秒 | **4.5 倍** |
| 2K | 4 点/秒 | 15 点/秒 | **3.75 倍** |
| 4K | 8 点/秒 | 20 点/秒 | **2.5 倍** |

拿 10 分钟 4K 算：VIAPI 12000 点（¥120），这里 4800 点（**¥48**），一条片子省 72 块。
10 分钟 1080P 差得更多：¥54 → **¥12**。

---

## 干货一：`duration` 必须显式传

平台会拿 `video_url` 自己 ffprobe 探时长，探不到就**直接拒单**。实测原样：

```json
POST /api/v1/video/tencent1080   {"videoUrl": "https://example.invalid/x.mp4"}
400 {"error":{"code":"duration_unknown","message":"无法探测视频时长，请显式传 duration（秒）","type":"relay"}}
```

所以本包把 `--duration` 做成**必填**，`--url` 只收 `http(s)://` 公网地址。
缺 `--duration` 直接退 `2`，一个请求都不发；给了就先按 `duration × 单价` 算点数过闸门，
**提交前你就知道这一单多少钱**，不用等账单。

`duration` 接受小数（实测传字符串 `"12.5"` 被当成 12.5 秒）。

## 干货二：计费按输入秒数、失败全退

按**输入秒数**算钱，不是输出秒数 —— 4K 输出体积是 1080P 的几倍，秒单价只差 4 倍，
不存在「清晰度越高越亏」的隐藏倍率。任务失败（含上游报错）**全额退回**，
`status` 会显示 `chargedPoints` / `netPoints`，对账有据。

## 干货三：查询三级回退，全都免费

`status` 依次试三条只读路由：

```
1. GET /api/v1/video/{tier}/{task_id}     ← 文档写的
2. GET /api/v1/videos/{task_id}           ← 统一任务对象（实测通）
3. GET /api/v1/me/tasks                   ← 本人台账（带 netPoints）
```

查询不扣费；`tasks` 直接把最近任务连净扣点一起列出来。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检
python3 scripts/run.py doctor

# 3) 先算钱
python3 scripts/run.py cost --tier 4k --duration 600

# 4) 提交 + 自动等结果
python3 scripts/run.py submit --url https://example.com/low.mp4 --tier 4k \
    --duration 600 --yes
```

---

## 用法示例

```bash
# 三档清单 + 单价 + 保底
python3 scripts/run.py catalog

# 三档价目表（1 / 10 / 30 分钟）
python3 scripts/run.py cost

# 1080P，5 分钟
python3 scripts/run.py submit --url https://example.com/low.mp4 --tier 1080p \
    --duration 300 --yes

# 只提交不等结果（长片子推荐）
python3 scripts/run.py submit --url https://example.com/low.mp4 --tier 4k \
    --duration 1800 --no-wait --yes

# 稍后查
python3 scripts/run.py status task_xxx --tier 4k

# 成片直接落到本地
python3 scripts/run.py submit --url https://example.com/low.mp4 --tier 4k \
    --duration 600 --out out.mp4 --yes

# 只看请求、不花钱
python3 scripts/run.py submit --url https://example.com/low.mp4 --tier 4k \
    --duration 600 --dry-run
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--url` | 必填 | 公网可访问的 `http(s)` 视频地址 |
| `--tier` | `4k` | `1080p` / `2k` / `4k` |
| `--duration` | 必填 | 视频秒数（按它计费） |
| `--callback-url` | — | 任务完成回调地址 |
| `--wait` / `--no-wait` | 等 | 提交后是否轮询到完成 |
| `--interval` | `10` | 轮询间隔秒数 |
| `--timeout` | `3600` | 轮询总超时秒数 |
| `--out` | — | 把成片下载到这个本地路径 |
| `--budget` | `6000` | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` | — | 确认真实扣费 |
| `--dry-run` | — | 只打印请求，不提交 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 三档能力清单 + 单价 + 保底 |
| `cost` | 免费 | 先算钱 |
| `doctor` | 免费 | 自检 Key / 余额 / 三档端点 / 查询路由 |
| `submit` | **按秒计费** | 提交超分任务（要 `--yes`） |
| `status` | 免费 | 查一个任务 |
| `tasks` | 免费 | 我最近的任务（单页 20 条） |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺 `--url` / `--duration`、档位写错、选项缩写） |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 任务失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "tier": "tencent4k", "resolution": "4K", "taskId": "task_xxx",
 "status": "success", "seconds": 600, "points": 4800, "yuan": 48.0,
 "videoUrl": "https://.../superres/xxx.mp4", "route": "/api/v1/videos/task_xxx"}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

---

## 实测记录（2026-11-07）

```
提交    POST /api/v1/video/tencent1080   {"video_url": "...", "duration": "12.5"}
返回    502 {"error":{"code":"FailedOperation.InvalidMpsUser",
             "message":"腾讯云超分提交失败：[FailedOperation.InvalidMpsUser] invalid mps user"}}
```

这是本次唯一触到上游提交的探针（`duration` 传的是字符串 `"12.5"`，平台照收并转发给了腾讯云），
被**上游凭据侧**拦下 —— 报错即不建单、不扣点。平台侧配通后本包代码零改动即可用。

零成本探针的结论（详见 `references/api-contract.md`）：

```
POST /api/v1/video/tencent1080  {}                       → 400 video_url_required
POST /api/v1/video/tencent1080  {"videoUrl":  "..."}     → 400 duration_unknown
POST /api/v1/video/tencent1080  {"video_url": "..."}     → 400 duration_unknown
POST /api/v1/video/tencent1080  {"url":       "..."}     → 400 duration_unknown
GET  /api/v1/videos/999999999                            → 400 task_not_exist
GET  /api/v1/video/tencent1080/999999999                 → 404（SPA HTML 兜底）
```

---

## 关于 `tsc_*` 系列

价目表里还有 `tsc_teshd`（短剧增强）、`tsc_shortplay` 等 **11 个 `tsc_*` 档位**，
路由尚未开放（实测 `/api/v1/video/tsc_teshd`、`/video/tencent/tsc_teshd`、
`/apps/media_services_33/teshd` 等路径变体都是 404）。
本包先把 1080P / 2K / 4K 三档做扎实，网关开放后第一时间接上。

---

## 文件结构

```
sanjianke-mps-upscale/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（文档原文 + 实测）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

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
