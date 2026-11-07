# 老片转高清一条龙 · 60 秒 19.8 元出 1080P

**一条 60 秒的模糊老片，19.8 元走完「超分 → 校色 → 增强」三步出 1080P。**

超分、校色、增强、修复串成一条命令；每一步的产物落盘，下一步自动接着喂；
断在半路用 `resume` 接着跑，已完成的步不重跑、已提交的任务不重提。
接 `api.a7w.cn` 的视频后处理通道，7 档工序全部实测定价，零依赖，只用 Python 标准库。

---

## 为什么值得用

自己修一条老片，最耗时间的从来不是「点哪个按钮」：

- **不知道该串几步** —— 先超分还是先校色？顺序反了，噪点会被一起放大；
- **每一步都要手工搬地址** —— 上一步的成片链接贴给下一步，格式不对就被 400 挡回来；
- **修到一半断了** —— 前面花的钱已经扣了，接着跑还得重新提交一次；
- **不知道一条要花多少钱** —— 跑到第三步才发现预算不够。

本包把这四件事做成了命令：`plan` 排链条、`cost` 报价、`run` 跑完整条、`resume` 续跑。

---

## 价目表（1 元 = 100 点，单价取自 `GET /api/v1/pricing`）

| 工序 | `--tier` | 单价 | 60 秒 | 干什么 |
|---|---|---|---|---|
| 校色 / 黑白上色 | `colorize` | **9 点/秒** | 540 点 | 灰片、偏色、黑白片还原自然色调 |
| 标准超分 1080P | `superres` | **9 点/秒** | 540 点 | 480P / 720P 提到 1080P |
| 画质综合增强 | `enhance` | 15 点/秒 | 900 点 | 清晰度 / 对比度 / 细节提一档 |
| 高清超分 2K | `superres2k` | 15 点/秒 | 900 点 | 2K 交付，顺带补帧到 60 |
| 人像增强 | `portrait` | 18 点/秒 | 1,080 点 | 只提人脸清晰度 |
| 超分 4K | `superres4k` | 20 点/秒 | 1,200 点 | 4K 交付 |
| 视频修复 | `restore` | **36 点/秒** | 2,160 点 | 去划痕 / 噪点 / 闪烁 / 压缩损伤 |

5 套预设（`--preset` 直接选，不用记顺序）：

| `--preset` | 名字 | 每秒合计 | 60 秒 | 串了哪几步 |
|---|---|---|---|---|
| `quick` | 快修 | 24 点/秒 | **1,440 点 = 14.4 元** | `superres` → `enhance` |
| `standard` | 标准一条龙 | 33 点/秒 | **1,980 点 = 19.8 元** | `superres` → `colorize` → `enhance` |
| `repair` | 老片抢救 | 54 点/秒 | 3,240 点 = 32.4 元 | `restore` → `superres` → `colorize` |
| `portrait` | 人物特写 | 48 点/秒 | 2,880 点 = 28.8 元 | `portrait` → `superres2k` → `enhance` |
| `cinema` | 4K 交付 | 71 点/秒 | 4,260 点 = 42.6 元 | `restore` → `superres4k` → `enhance` |

10 分钟的老片按 `standard` 走是 19,800 点 = 198 元。全部按秒计费，
先按 `duration` 冻结、完成后按实际时长结算，任务失败全额退回。

---

## 三条实测干货

### 1. `restore` 只有一条路

```
✅ POST /api/v1/video/restore          → 400 pixverse_empty_url（端点正确）
❌ POST /api/v1/video/viapi/restore    → 404 unknown_tool
```

其余 6 档反过来：只有 `/api/v1/video/viapi/<tier>` 通，空 body 一律 400 `empty_url`。
`doctor` 把 7 条端点和 2 条查询路由逐条打出来。

### 2. 每一步的产物都要再过一次白名单

`videoUrl` 只收三种地址：本站 `vr.a7w.cn`、本站七牛 `cdn2.jiujiushuyuan.cn/vr/`、
上传接口返回的 `oss.gpu.likeadmin.cn/openapi/`。外站地址回 400 `url_not_allowed`。

本包每一步都「先落盘、再看链接」：链接在白名单内直接喂下一步，
不在就 `POST /api/v1/upload`（免费，字段名 `file`）换一个白名单地址。

### 3. 轮询只看 `result` 路由

`GET /api/v1/video/viapi/result/<taskId>` 与 `GET /api/v1/video/restore/<taskId>` 都免费，
还顺带给 `status` / `cost` / `refund`。应用层 `/query` 轮一次就是一次的钱
（历史流水里 `nano_banana/query` 记过 216 笔、每笔 72 点、合计 15,552 点）。

---

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

状态写在 `oldfilm-work/state.json`，`resume` 从第一个没完成的步接着跑。

---

## 五分钟上手

```bash
# 1) 填 Key（也可以 export A7W_API_KEY，或 --key）
python3 scripts/a7w.py login --key sk-你的key

# 2) 自检：Key / 7 个端点 / 价目表 / 2 条查询路由 / 上传，全免费
python3 scripts/run.py doctor

# 3) 先看钱与计划（纯本地，不联网）
python3 scripts/run.py cost --seconds 60
python3 scripts/run.py plan --preset standard --file 老片.mp4

# 4) 真跑一条
python3 scripts/run.py run --file 老片.mp4 --preset standard --yes

# 5) 断了接着跑（已完成的步不重跑、已提交的任务不重提）
python3 scripts/run.py resume --workdir oldfilm-work
```

不放心的先看一遍会发出什么请求：

```bash
python3 scripts/run.py run --file 老片.mp4 --preset standard --dry-run
```

不加 `--yes` 会退 `4` 并告诉你这次要花多少点；预计点数超 `--budget` 退 `5`，
**一个请求都不发**。

---

## 和 sanjianke-video-lab 的分工

两个包共用同一个 Key、同一份价目、同一批端点，差别在「一步」和「一条」：

| 你要干的事 | 用哪个 | 它多做了什么 |
|---|---|---|
| 一条老片按顺序跑 3 步出高清 | **本包** `run --preset standard` | 自动串链、每步落盘、自动过白名单、断点续跑 |
| 断在半路接着跑、还不重复付费 | **本包** `resume` | 读 `state.json`，已提交的 taskId 只查不重提 |
| 片长不想手填秒数 | **本包** `run --file` | 直接读 MP4 头里的 `mvhd` 时长（零依赖） |
| 只想跑某一步，或要换脸 / 抠像 / 卡通化 / 擦台标 / 拆字幕 | `sanjianke-video-lab` | 11 档全开，`submit --tier` 一次一步 |
| 要按次的三档（`shot` / `castcrew` / `delogo`） | `sanjianke-video-lab` | 那三档在 11 档里，本包只做 7 档按秒的 |

一句话：**单步找 video-lab，成片找本包。**

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 7 档工序 + 5 套预设 + 每档实际路径 |
| `cost` | 免费 | 5 套预设与 7 档单步的价目 |
| `plan` | 免费 | 打印流水线计划与每一步的请求体（纯本地） |
| `doctor` | 免费 | 自检 Key / 7 个端点 / 价目表 / 查询路由 / 上传 |
| `upload` | 免费 | 上传本地片子，拿一个能直接提交的地址 |
| `run` | **按预设计费** | 起一条流水线（要 `--yes`，受 `--budget` 管） |
| `resume` | 只补没跑的步 | 断点续跑（已提交的任务只查不重提） |
| `status` | 免费 | 查单个任务（走 `result` 路由） |
| `log` | 免费 | 本地台账（`~/.a7w/oldfilm-ledger.json`） |

---

## 文件结构

```
sanjianke-oldfilm-restore/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测原文 + 请求体）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致）
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
