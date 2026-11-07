---
name: sanjianke-mps-upscale
slug: sanjianke-mps-upscale
displayName: 腾讯云超分台 · 2 点一秒，4K 也能提
description: "**4K 超分 8 点/秒（¥0.08）——一条 10 分钟的片子 48 块提满 4K**；1080P 更狠，2 点/秒，10 分钟 12 块。走 api.a7w.cn 的腾讯云 MPS 音视频增强，和阿里 VIAPI 同一条产线，价格是它的 1/4.5（1080P 9→2、2K 15→4、4K 20→8 点/秒）。本包把两件真会花错钱的事做成了默认路径：一是 `duration` 要你自己给（平台自动探测失败会直接拒单，实测 `400 duration_unknown`），二是按**输入秒数**而不是输出秒数计费。`cost` 先报钱、`--budget` 是第一道闸门（一个请求都不发）、`--yes` 是第二道，`doctor` 用「带视频地址但缺时长」探三档端点（上游规定 400，零扣费）。一条命令完成提交 → 自动轮询 → 拿成片地址，失败全额退回。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "腾讯云超分（MPS 音视频增强）三档：1080P **2 点/秒**、2K **4 点/秒**、4K **8 点/秒**，单笔**保底 10 点**，1 元 = 100 点。按**输入视频秒数**计费（不是输出），任务失败**全额退回**，查询接口不扣费，成品链接保留 **24 小时**。对比阿里 VIAPI 的 9 / 15 / 20 点/秒：1080P 便宜 **4.5 倍**、2K 便宜 **3.75 倍**、4K 便宜 **2.5 倍**。三个接口分别是 `POST /api/v1/video/tencent1080`、`/tencent2k`、`/tencent4k`，提交返回 `task_id`，再 `GET /api/v1/video/{tier}/{task_id}` 取 `status` / `video_url` / `points`。**关键一条：`duration` 必须显式传** —— 平台拿 `video_url` 自己 ffprobe 探测，探测失败就拒单（实测 `400 duration_unknown`「无法探测视频时长，请显式传 duration（秒）」），所以本包把 `--duration` 做成必填，先在本地算好点数再提交，既省钱也避免「提交了才发现时长错了」。`doctor` 的三档探针一律用「合法地址 + 缺时长」，停在上游参数校验，零扣点；`submit` 结束打印任务号、实际秒数、实际点数与成片地址，`status` 支持文档路由 `/video/{tier}/{id}`、统一任务路由 `/videos/{id}` 与本人台账三级回退。价目表里 `tsc_*` 那 11 档（短剧增强等）暂未开放路由，网关一开就接。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 视频超分
  - 腾讯云MPS
  - api.a7w.cn
---

# 腾讯云超分台 · 2 点一秒，4K 也能提

**一句话：1080P 2 点/秒、2K 4 点/秒、4K 8 点/秒**，走 `api.a7w.cn` 的腾讯云 MPS 音视频增强，
异步任务（提交拿 `task_id` → 轮询取成片）。一条 10 分钟的片子提满 4K，**48 块**。

> **先申请你自己的 API Key**：本包不内嵌 Key，用的是你**自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。一条命令存好：`python3 scripts/a7w.py login --key sk-你的key`

## 价目表

| 档位 | 接口 | 单价 | 保底 | 10 分钟 | 30 分钟 |
|---|---|---|---|---|---|
| **1080P** | `POST /api/v1/video/tencent1080` | **2 点/秒（¥0.02）** | 10 点 | 1200 点 = **¥12** | 3600 点 = ¥36 |
| **2K** | `POST /api/v1/video/tencent2k` | **4 点/秒（¥0.04）** | 10 点 | 2400 点 = **¥24** | 7200 点 = ¥72 |
| **4K** | `POST /api/v1/video/tencent4k` | **8 点/秒（¥0.08）** | 10 点 | 4800 点 = **¥48** | 14400 点 = ¥144 |

- **按输入视频秒数计费**（不是输出），1 元 = 100 点；**单笔保底 10 点**（2 秒 4K 也只收 10 点）
- 任务失败 **全额退回**；查询接口 **不扣费**；成品链接保留 **24 小时**
- 选档：1080P 走老片 / 录屏 / 竖屏短剧；2K 上大屏投影；4K 交付级母版

## 为什么选腾讯线

同一条产线（阿里 VIAPI）的报价是 1080P **9** 点/秒、2K **15** 点/秒、4K **20** 点/秒：

| 档位 | 腾讯 MPS | 阿里 VIAPI | 便宜 |
|---|---|---|---|
| 1080P | 2 点/秒 | 9 点/秒 | **4.5 倍** |
| 2K | 4 点/秒 | 15 点/秒 | **3.75 倍** |
| 4K | 8 点/秒 | 20 点/秒 | **2.5 倍** |

10 分钟 4K：VIAPI 12000 点（¥120），这里 4800 点（**¥48**），一条片子省 72 块。
10 分钟 1080P 差得更多：¥54 → **¥12**。

## 干货一：`duration` 必须显式传

平台会拿 `video_url` 自己 ffprobe 探时长，探不到就**直接拒单**。实测原样：

```json
POST /api/v1/video/tencent1080   {"videoUrl": "https://example.invalid/x.mp4"}
400 {"error":{"code":"duration_unknown","message":"无法探测视频时长，请显式传 duration（秒）","type":"relay"}}
```

所以本包把 `--duration` 做成**必填**，`--url` 只收 `http(s)://` 公网地址。
缺 `--duration` 直接退 `2`，一个请求都不发；给了就先按 `duration × 单价` 算点数过闸门，
**提交前你就知道这一单多少钱**，不用等账单。`duration` 接受小数（实测 `"12.5"` 被当成 12.5 秒）。

## 干货二：计费按输入秒数、失败全退

按**输入秒数**算钱，不是输出秒数 —— 4K 输出体积是 1080P 的几倍，秒单价只差 4 倍，
不存在「清晰度越高越亏」的隐藏倍率。任务失败（含上游报错）**全额退回**，`status` 有 `netPoints` 可对账。

## 干货三：查询三级回退，全都免费

`status` 依次试 `GET /api/v1/video/{tier}/{task_id}`（文档写的）、
`GET /api/v1/videos/{task_id}`（统一任务对象，实测通）、`/api/v1/me/tasks`（本人台账）。
三条都是只读、不扣费；`tasks` 直接把最近任务连 `netPoints` 一起列出来。

## 三步上手

```bash
# 1) 自检（不扣费）  2) 先算钱（不扣费）
python3 scripts/run.py doctor
python3 scripts/run.py cost --tier 4k --duration 600
#   算账：600 秒 × 8 点/秒 = 4800 点  →  **4800 点 = 48.00 元**

# 3) 提交 + 自动等结果
python3 scripts/run.py submit --url https://example.com/low.mp4 --tier 4k \
    --duration 600 --yes
```

## 常用命令

```bash
python3 scripts/run.py catalog                       # 三档清单 + 单价 + 保底
python3 scripts/run.py submit --url ... --tier 2k --duration 300 --yes
python3 scripts/run.py submit --url ... --tier 4k --duration 600 --no-wait   # 只提交
python3 scripts/run.py submit --url ... --duration 600 --dry-run             # 只看请求
python3 scripts/run.py status task_xxx --tier 4k     # 查一个任务（免费）
python3 scripts/run.py tasks --limit 10              # 我最近的任务（免费）
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--url` | 必填 | 公网可访问的 `http(s)` 视频地址 |
| `--tier` | `4k` | `1080p` / `2k` / `4k` |
| `--duration` | 必填 | 视频秒数（按它计费） |
| `--callback-url` | — | 任务完成回调地址 |
| `--wait` / `--no-wait` | 等 | 提交后是否轮询到完成 |
| `--interval` / `--timeout` | `10` / `3600` | 轮询间隔 / 总超时（秒） |
| `--out` | — | 把成片下载到这个本地路径 |
| `--budget` | `6000` | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` | — | 确认真实扣费 |

## 子命令

`catalog` 三档清单 + 单价 + 保底（免费）· `cost` 先算钱（免费）· `doctor` 自检 Key / 余额 / 三档端点 / 查询路由（免费）·
`submit` 提交任务（**按秒计费**，要 `--yes`）· `status` 查一个任务（免费）· `tasks` 我最近的任务（免费）· `log` 本地台账（免费）。

## 退出码

| 码 | 含义 |
|---|---|
| `0` 成功 · `2` 用法错（缺 `--url` / `--duration`、档位错、选项缩写）· `4` 缺 `--yes` |
| `5` 预算不足（**一个请求都不发**）· `6` 调用失败 / 任务失败 · `1` 内部错 · `130` 中断 |

## `--json` 契约

```json
{"ok": true, "tier": "tencent4k", "resolution": "4K", "taskId": "task_xxx",
 "status": "success", "seconds": 600, "points": 4800, "yuan": 48.0,
 "videoUrl": "https://.../superres/xxx.mp4", "route": "/api/v1/videos/task_xxx"}
```

失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`。
`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

## 实测记录（2026-11-07）

```
提交    POST /api/v1/video/tencent1080   {"video_url": "...", "duration": "12.5"}
返回    502 {"error":{"code":"FailedOperation.InvalidMpsUser",
             "message":"腾讯云超分提交失败：[FailedOperation.InvalidMpsUser] invalid mps user"}}
```

这是本次唯一触到上游提交的探针（`duration` 传字符串 `"12.5"`，平台照收并转发给腾讯云），被**上游凭据侧**拦下 —— 报错即不建单、不扣点；平台侧配通后本包代码零改动即可用。三档端点与查询路由也都用零成本探针验过（详见 `references/api-contract.md`）：`400 duration_unknown` = 端点对了，`400 task_not_exist` = 查询路由对了。

## 关于 `tsc_*` 系列

价目表里还有 `tsc_teshd`（短剧增强）、`tsc_shortplay` 等 **11 个 `tsc_*` 档位**，
路由尚未开放（实测 `/api/v1/video/tsc_teshd`、`/video/tencent/tsc_teshd`、
`/apps/media_services_33/teshd` 等路径变体都是 404）。本包先把 1080P / 2K / 4K 做扎实，
网关开放后第一时间接上。

## 文件结构

正好 7 个文件：`SKILL.md` · `README.md` · `LICENSE.md` · `references/api-contract.md` ·
`references/troubleshooting.md` · `scripts/a7w.py`（全家族逐字节一致）· `scripts/run.py`（本包命令层）。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
