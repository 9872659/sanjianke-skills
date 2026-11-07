---
name: sanjianke-oldfilm-restore
slug: sanjianke-oldfilm-restore
displayName: 老片转高清一条龙 · 60 秒 19.8 元出 1080P
description: "**一条 60 秒的模糊老片，19.8 元走完三步出 1080P** —— 超分 → 校色 → 增强串成一条命令，每步产物落盘，断在半路 `resume` 接着跑。走 api.a7w.cn 的视频后处理通道，7 档工序实测定价：校色 9 点/秒、超分 9、增强 15、修复 36，全部按秒（1 元 = 100 点）。三个真会白跑一趟的坑写进默认动作：`restore` 只有扁平 `/api/v1/video/restore` 通；`videoUrl` 要平台托管地址，每步产物先过一遍白名单（`upload` 免费）；查询只看 `GET /api/v1/video/viapi/result/<taskId>`（免费），应用层 `/query` 轮一次就是一次的钱。`cost` 先算钱，两道闸门兜底，`doctor` 零扣费自检。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "老片转高清的难点是四件事：链条怎么串、产物怎么喂、钱怎么冻、断了怎么接。实测结论做成了默认动作。**价目**（1 元 = 100 点，点/秒）：colorize 9、superres 9、enhance 15、superres2k 15、portrait 18、superres4k 20、restore 36。**5 套预设**（点/秒）：quick 24、standard 33、repair 54、portrait 48、cinema 71，先修、再分、后调。**路径**（空 body 探针）：`restore` 只走扁平 `/api/v1/video/restore`，`viapi/restore` 404；其余 6 档走 `/api/v1/video/viapi/<tier>`，全部 400 `empty_url`。**地址**：`videoUrl` 有白名单（vr.a7w.cn / cdn2 / oss），每步成片先落盘，名单内直接喂。**查询**：只看 `GET /api/v1/video/viapi/result/<taskId>`。**续跑**：`resume` 读 state.json，已完成的步跳过、已提交的只查不重提。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 视频修复
  - 视频超分
  - api.a7w.cn
---

# 老片转高清一条龙 · 60 秒 19.8 元出 1080P

> **本包不内嵌 Key**：用你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己的余额。
> 填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**一条 60 秒的模糊老片，19.8 元走完「超分 → 校色 → 增强」三步出 1080P。**
一条命令串起整条流水线，每步产物落盘，断在半路用 `resume` 接着跑。

## 价目表（1 元 = 100 点，单价取自 `GET /api/v1/pricing`）

| 工序 | `--tier` | 单价 | 60 秒 | 干什么 |
|---|---|---|---|---|
| 校色 / 黑白上色 | `colorize` | **9 点/秒** | 540 点 | 灰片、偏色、黑白片还原自然色调 |
| 标准超分 1080P | `superres` | **9 点/秒** | 540 点 | 480P / 720P 提到 1080P |
| 画质综合增强 | `enhance` | 15 点/秒 | 900 点 | 清晰度 / 对比度 / 细节提一档，收尾用 |
| 高清超分 2K | `superres2k` | 15 点/秒 | 900 点 | 2K 交付，顺带补帧到 60 |
| 人像增强 | `portrait` | 18 点/秒 | 1,080 点 | 只提人脸清晰度 |
| 超分 4K | `superres4k` | 20 点/秒 | 1,200 点 | 4K 交付 |
| 视频修复 | `restore` | **36 点/秒** | 2,160 点 | 去划痕 / 噪点 / 闪烁 / 压缩损伤 |

5 套预设就是 5 条串好的流水线（`--preset` 直接选）：

| `--preset` | 名字 | 每秒合计 | 60 秒 | 串了哪几步 |
|---|---|---|---|---|
| `quick` | 快修 | 24 点/秒 | **1,440 点 = 14.4 元** | `superres` → `enhance` |
| `standard` | 标准一条龙 | 33 点/秒 | **1,980 点 = 19.8 元** | `superres` → `colorize` → `enhance` |
| `repair` | 老片抢救 | 54 点/秒 | 3,240 点 = 32.4 元 | `restore` → `superres` → `colorize` |
| `portrait` | 人物特写 | 48 点/秒 | 2,880 点 = 28.8 元 | `portrait` → `superres2k` → `enhance` |
| `cinema` | 4K 交付 | 71 点/秒 | 4,260 点 = 42.6 元 | `restore` → `superres4k` → `enhance` |

10 分钟的老片按 `standard` 走是 19,800 点 = 198 元。`--steps` 可以自己拼，最多 4 步。

## 三条实测干货

### 1. `restore` 只有一条路，走错就白等

```
✅ POST /api/v1/video/restore          → 400 pixverse_empty_url（端点正确，空 body 停在校验层）
❌ POST /api/v1/video/viapi/restore    → 404 unknown_tool「未知的视频工具名: restore」
```

其余 6 档反过来：只有 `/api/v1/video/viapi/<tier>` 通，空 body 一律 400 `empty_url`。
`doctor` 把 7 条端点和 2 条查询路由逐条打出来，`catalog` 会标明每档实际走哪条。

### 2. 每一步的产物都要再过一次白名单

`videoUrl` 只收三种地址：本站 `vr.a7w.cn`、本站七牛 `cdn2.jiujiushuyuan.cn/vr/`、
上传接口返回的 `oss.gpu.likeadmin.cn/openapi/`。外站地址回 400 `url_not_allowed`。

所以本包每一步都「先落盘、再看链接」：成片链接在白名单内就直接喂给下一步，
不在就 `POST /api/v1/upload`（免费，multipart 字段名 `file`）换一个白名单地址。
`--reupload` 可以强制每步都重传，成片链接快过期时用。

### 3. 轮询只看 `result` 路由，一次不花一次的钱

`GET /api/v1/video/viapi/result/<taskId>` 与 `GET /api/v1/video/restore/<taskId>` 都是**免费**的，
用完还能拿到 `status` / `cost` / `refund`。应用层的 `/query` 不是这个性质：
历史流水里 `nano_banana/query` 记过 216 笔、每笔 72 点、合计 15,552 点 —— 轮一次就是一次的钱。
本包所有等待都走 `result` 路由，`--every` 只是间隔。

## 完整链路

```
老片.mp4
  │  ① POST /api/v1/upload（免费）→ oss.gpu.likeadmin.cn/openapi/…（白名单）
  ▼
[1] superres  9 点/秒  ──POST /api/v1/video/viapi/superres──▶ taskId
  │                      GET  /api/v1/video/viapi/result/<taskId>（免费）
  ▼  01-superres.mp4 落盘
[2] colorize  9 点/秒  ──────────────────────────────────────▶ 02-colorize.mp4
[3] enhance  15 点/秒  ──────────────────────────────────────▶ 03-enhance.mp4 ← 成片
```

状态写在 `oldfilm-work/state.json`：每一步的 `taskId` / `status` / 产物路径 / 点数。
断网、关机、Ctrl-C 之后 `resume` 从第一个没完成的步接着跑，已提交的 taskId 只查不重提。

## 和 sanjianke-video-lab 的分工

两个包共用同一个 Key、同一份价目、同一批端点，差别在「一步」和「一条」：

| 你要干的事 | 用哪个 | 它多做了什么 |
|---|---|---|
| 一条老片按顺序跑 3 步出高清，中途不用管 | **本包** `run --preset standard` | 自动串链、每步落盘、自动过白名单、断点续跑 |
| 断在半路要接着跑、还不想重复付费 | **本包** `resume` | 读 `state.json`，已提交的 taskId 只查不重提 |
| 片长不想手填秒数 | **本包** `run --file` | 直接读 MP4 头里的 `mvhd` 时长（零依赖） |
| 只想跑某一步、或要换脸 / 抠像 / 卡通化 / 擦台标 / 拆字幕 | `sanjianke-video-lab` | 11 档全开，`submit --tier` 一次一步 |
| 要按次计价的三档（`shot` / `castcrew` / `delogo`） | `sanjianke-video-lab` | 那三档在 11 档里，本包只做 7 档按秒的 |
| 要一张 11 档路径与单价的对照表 | `sanjianke-video-lab` `catalog` | 11 条路径 + 两种计价口径都打出来 |

一句话：**单步找 video-lab，成片找本包。** 重复的只有这 7 档按秒的工序。

## 三步上手

```bash
# 1) 自检（不扣费、0 冻结）：Key / 7 个端点 / 价目表 / 2 条查询路由 / 上传
python3 scripts/run.py doctor

# 2) 先看钱和计划（纯本地，不联网）
python3 scripts/run.py cost --seconds 60
python3 scripts/run.py plan --preset standard --file 老片.mp4

# 3) 真跑一条（不加 --yes 退 4，超 --budget 退 5 且一个请求都不发）
python3 scripts/run.py run --file 老片.mp4 --preset standard --yes
```

只想看会发出什么请求：`run --file 老片.mp4 --dry-run`（不上传、不提交、不冻结）。

## 常用命令

```bash
python3 scripts/run.py catalog                          # 7 档 + 5 套预设 + 实际路径（免费）
python3 scripts/run.py run --file 老片.mp4 --preset repair --yes     # 老胶片抢救
python3 scripts/run.py run --file 老片.mp4 --preset cinema --yes     # 4K 交付
python3 scripts/run.py run --steps colorize,superres --yes           # 自己拼 2 步
python3 scripts/run.py run --video-url "https://oss.gpu.likeadmin.cn/openapi/…" --preset quick --yes
python3 scripts/run.py run --file 老片.mp4 --preset standard --no-wait   # 只提交第一步
python3 scripts/run.py resume --workdir oldfilm-work    # 断点续跑（只查不重提）
python3 scripts/run.py status --task-id task_xxx --tier superres        # 查单个任务（免费）
python3 scripts/run.py log                              # 本地台账
```

## 规格

| 项 | 说明 |
|---|---|
| 依赖 | 只用 Python 3.7+ 标准库，`pip install` 一个都不用 |
| 端点 | 提交：`POST /api/v1/video/restore`（修复）+ `POST /api/v1/video/viapi/<tier>`（其余 6 档）；上传：`POST /api/v1/upload`；查询：`GET /api/v1/video/viapi/result/<taskId>` |
| 计费口径 | 全部按秒；先按 `duration` 冻结、完成后按实际时长结算，任务失败全额退回 |
| 时长 | 自动读 MP4/MOV 头里的 `mvhd`；读不到用 `--seconds`（默认 60） |
| 闸门 | 预计点数 > `--budget` → 退 5，**一个请求都不发**；缺 `--yes` → 退 4 并报要花多少；`--budget` 单位是「点」，默认 5000 |
| 退出码 | `0` 成功 / `2` 用法错 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断；`doctor` 不过给 `3` |
| `--json` | 写在子命令前后都行，stdout 只有一个 JSON：成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}`，`kind` 取 `usage｜gate｜confirm｜budget｜call｜interrupt｜internal` |
| 状态文件 | `oldfilm-work/state.json`，逐步记录 taskId / 状态 / 产物 / 点数；`resume` 靠它续跑 |
| 产物 | `oldfilm-work/01-<tier>.mp4`、`02-<tier>.mp4`…，最后一步就是成片 |

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
