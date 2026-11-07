---
name: sanjianke-video-lab
slug: sanjianke-video-lab
displayName: 视频后处理台 11 个能力一个命令
description: "**一条老片，去台标、擦字幕、校色、增强，11 个工序一条命令跑完 —— 最便宜的一档 9 点一秒（¥0.09）。** 走 api.a7w.cn 的视频后处理通道，异步两步、零依赖。本包把三件真会白跑一趟的事写进了默认动作：一是 11 档能力**不是同一条路径**（restore 只在 `/api/v1/video/restore`，换脸/抠像/卡通化只在 `/api/v1/video/viapi/`），二是 `videoUrl` 要**平台托管**的地址（`upload` 上传后拿到的 `oss.gpu.likeadmin.cn/openapi/…` 或本站 `vr.a7w.cn` 成片），三是 `shot`/`castcrew`/`delogo` 的价签写「点/次」而引擎按秒 —— `cost` 先算钱、`--budget` 与 `--yes` 两道闸门、`doctor` 用空 body 把 11 个端点全验一遍（400 即正确，0 条任务、0 点冻结）。`catalog` 会逐档打出实际路径与单价。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "视频后处理的调用说明本身是散的：11 个能力写在 11 个页面里，价格在 `/api/v1/pricing`，路径却分扁平与 viapi 两套。本包把实测结论做成默认动作。**价目**（1 元 = 100 点）：colorize / segment / subtitle 9 点/秒、enhance 15、portrait 18、faceswap 20、shot 20 点/次、cartoon 24、castcrew 25 点/次、delogo 25 点/次、restore 36 点/秒。**路径**（空 body 探针实测）：`restore` 走扁平，`/api/v1/video/viapi/restore` 会返回 404 `unknown_tool`；`faceswap` / `segment` / `cartoon` 的扁平路径是 404（SPA 兜底），只能走 viapi；其余 7 档两条都通，本包统一走 viapi。**地址**：`videoUrl` 有白名单，实测外站地址返回 400 `url_not_allowed`，原文是「必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）」，所以配了免费的 `upload` 子命令先把本地片子传上去。**查询**：`GET /api/v1/video/viapi/result/{taskId}` 免费，直接给 `status` / `message` / `refund`（通用 `/api/v1/tasks/{taskId}` 只服务模型与应用任务，实测查不到后处理任务）。按秒档先按秒数冻结、完成后按实际时长结算，任务失败全额退回。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 视频后处理
  - 视频修复
  - api.a7w.cn
---

# 视频后处理台 11 个能力一个命令

> **本包不内嵌 Key**：用你自己在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**9 点一秒起，11 个视频工序一条命令。** 去台标、擦字幕、校色、增强、修复、换脸、抠像、卡通化、提人像、认字幕、找镜头 —— 全部走 `api.a7w.cn`，异步两步、零依赖。

## 价目表（按点/秒从低到高，1 元 = 100 点）

| 能力 | `--tier` | 单价 | 10 分钟 | 干什么 |
|---|---|---|---|---|
| 校色 / 黑白上色 | `colorize` | **9 点/秒** | 5,400 点 | 黑白片自动上色，还原自然色调 |
| 人像抠像 / 绿幕 | `segment` | **9 点/秒** | 5,400 点 | 输出人像 mask 视频，换背景用 |
| 字幕擦除 | `subtitle` | **9 点/秒** | 5,400 点 | 擦掉硬字幕，二创换字幕的第一步 |
| 画质综合增强 | `enhance` | 15 点/秒 | 9,000 点 | 清晰度 / 对比度 / 细节整体提一档 |
| 人像增强 | `portrait` | 18 点/秒 | 10,800 点 | 只提人脸清晰度，GPEN 路线 |
| 换脸 / 人脸融合 | `faceswap` | 20 点/秒 | 12,000 点 | 视频里最大的人脸换成你的人脸图 |
| 镜头检测 | `shot` | 20 点/次 | 20 点 | 按镜头切分，返回切点帧号 |
| 人像卡通化 | `cartoon` | 24 点/秒 | 14,400 点 | 真人转动漫风 |
| 硬字幕 / 演职员表 OCR | `castcrew` | 25 点/次 | 25 点 | 抽硬字幕与滚动演职员表，附 SRT |
| 台标 / Logo 擦除 | `delogo` | 25 点/次 | 25 点 | 擦台标、平台 logo（最多 2 个区域） |
| 视频修复 | `restore` | 36 点/秒 | 21,600 点 | 去划痕 / 噪点 / 闪烁，老片抢救 |

`shot` / `castcrew` / `delogo` 的价签写「点/次」，引擎规则却是 `per_second` —— **本包按价签收一次**，`cost` 会把两种口径都打出来，最终以账单为准。

## `--tier` 怎么选

| 你要干什么 | 用哪个 |
|---|---|
| 老片发灰、偏色、黑白片要上色 | `colorize`（9 点/秒，最便宜） |
| 二创要换字幕，先把原字幕抹掉 | `subtitle`（9 点/秒） |
| 换背景 / 做绿幕素材 | `segment`（9 点/秒，输出人像 mask） |
| 片子糊、要整体提一档 | `enhance`；只想把人脸提清楚用 `portrait` |
| 画面有划痕、噪点、闪烁 | `restore`（36 点/秒，修复强度最高） |
| 视频里换一张脸 | `faceswap`（还要 `--face-url` 人脸图） |
| 真人转动漫风 | `cartoon` |
| 去台标 / 平台 logo | `delogo`（25 点/次） |
| 要分镜点、要按镜头切片 | `shot`（20 点/次，纯结构化结果） |
| 要硬字幕文本、要演职员表 SRT | `castcrew`（25 点/次） |

## 三步上手

```bash
# 1) 自检：Key / 11 个端点 / 价目表 / 查询 / 上传，全免费
python3 scripts/run.py doctor

# 2) 上传本地片子，拿一个能直接提交的地址（免费，单文件默认 512 MB）
python3 scripts/run.py upload --file input.mp4
#    → https://oss.gpu.likeadmin.cn/openapi/18/20261107/xxxx.mp4   （最长 24 小时）

# 3) 先算钱，再提交，再查
python3 scripts/run.py cost --tier delogo
python3 scripts/run.py submit --tier delogo --video-url "https://oss.gpu.likeadmin.cn/openapi/18/20261107/xxxx.mp4" --yes
python3 scripts/run.py status --task-id task_xxx
```

## 三条别人不会告诉你的

**一、11 档走的不是同一条路径。** 空 body 实测：`/api/v1/video/viapi/restore` 返回 404 `unknown_tool`（「未知的视频工具：restore」）—— 修复只有扁平那条 `/api/v1/video/restore`。反过来 `faceswap` / `segment` / `cartoon` 的扁平路径是 404（落到 SPA 首页），只有 viapi 那条通。路径表写死在包里，`catalog` 逐档打出来，`doctor` 逐档探一遍。

**二、`videoUrl` 用平台托管的地址。** 外站地址会被挡在门口：400 `url_not_allowed`，原文三选一 —— 本站 `vr.a7w.cn`、本站七牛 `cdn2.jiujiushuyuan.cn/vr/`、本站上传接口 `oss.gpu.likeadmin.cn/openapi/`。所以 `upload` 是标配：传完拿 `data.url` 直接喂 `submit`，全程免费，只受 512 MB 单文件上限约束。

**三、按秒档「先冻结、后结算」。** 提交时按 `duration` 预冻结（缺省 5 秒），完成后按**实际时长**结算，任务失败**全额退回**。`submit` 不传 `--duration` 也能跑，`cost` 就按 5 秒估；想算准就显式传秒数。

## 常用命令

```bash
python3 scripts/run.py catalog                                    # 11 档 + 路径 + 单价
python3 scripts/run.py cost                                       # 全档 1/10/30 分钟价目
python3 scripts/run.py submit --tier restore --video-url "..." --duration 180 --budget 8000 --yes
python3 scripts/run.py submit --tier faceswap --video-url "..." --face-url "..." --yes
python3 scripts/run.py submit --tier colorize --video-url "..." --dry-run   # 只看请求
python3 scripts/run.py status --task-id task_xxx --tier colorize
python3 scripts/run.py log --limit 10
```

**不加 `--yes` 退 `4`** 并告诉你这次要花多少点；**预计点数 > `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 5000 = 50 元）。

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--tier` | 必填 | 11 档之一，见 `catalog` |
| `--video-url` | 必填 | 平台托管的视频地址（先 `upload`） |
| `--duration` | 5 | 视频秒数，用于预冻结；按次档不需要 |
| `--face-url` | — | 人脸参考图，任意 http(s) 图片地址（只 `faceswap`） |
| `--seed` / `--callback-url` | — | 只 `restore` 用 |
| `--file` | — | `upload` 用，本地文件路径 |
| `--route` / `--allow-any-url` | `auto` / — | 强制路径 / 跳过本地白名单预检 |
| `--budget` | 5000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实提交 / 只打印请求 |

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 11 档能力 + 每档实际路径 + 单价 |
| `cost` | 免费 | 1 / 10 / 30 分钟价目 |
| `doctor` | 免费 | 自检 Key / 11 个端点 / 价目表 / 查询 / 上传 |
| `upload` | 免费 | 上传本地视频，拿可提交的地址 |
| `submit` | **按档计费** | 提交任务（要 `--yes`） |
| `status` | 免费 | 查任务（`video/viapi/result/{id}`，带 `refund`） |
| `log` | 免费 | 本地台账 |

## 退出码

| 码 | 含义 |
|---|---|
| `0` / `2` | 成功 / 用法错（参数缺失、地址预检没过、选项缩写） |
| `3` / `4` | `doctor` 出现 × / 没给 `--yes` |
| `5` / `6` | 预算不足（**一个请求都不发**）/ 调用失败 |
| `1` / `130` | 内部错误 / 被 Ctrl-C 中断 |

## `--json` 契约

```json
{"ok": true, "tier": "colorize", "taskId": "task_xxx", "status": "PENDING",
 "duration": 30, "cost": 270, "balance": 999999, "estimatedPoints": 270}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`；`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 文件结构

```
sanjianke-video-lab/{SKILL.md, README.md, LICENSE.md,
  references/{api-contract.md, troubleshooting.md},
  scripts/{a7w.py, run.py}}
```

## 计费口径与保底

- 成品链接有效期约 **30 分钟**，`status` 拿到就转存。
- `shot` / `castcrew` / `delogo` 按次结算，与素材时长无关；按秒档最小计 1 秒。
- `portrait` 价签写 18 点/秒、注里写「公测免费」，以实际账单为准。
- `--budget` 与 `--yes` 是本地闸门：预算内才发请求，`--yes` 到了才提交。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
