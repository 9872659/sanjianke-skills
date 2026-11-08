---
name: sanjianke-video-models
slug: sanjianke-video-models
displayName: 文生视频模型台 · 一句话横评 5 个模型，最低 0.44 元一条
description: "**同一句话，5 个视频模型先报价再出片，最低 0.44 元一条。** 实测 muse-video 44 点、Seedance 2.0 145.73 点、2.5 762.30 点，最贵上界与最便宜差 11.7 倍 —— 看完价再跑。两件事：①目录里的 kling-4-0、veo3.1-pro、hailuo-02-standard 打 `POST /api/v1/videos` 会 404 `model_not_found`，真正的提交端点是 `POST /api/v1/videos/generations`（13 个型号实测停在参数校验）；②单价不在 115 条价目表里，本包按 `me/tasks` 的 actualPrice 归集，跑过标 live、没跑过标 baseline，不编单价。`gen` 用同一句话逐个提交，落盘并生成「五个模型」对比清单。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "横评先解决「先花谁的钱」。`cost --models a,b,c` 逐个报价并按上界排序：muse-video 44 - 260 点（官方 11 点/秒）、Seedance 2.0 145.73 - 3,000 点、Seedance 2.5 762.30 - 3,045.71 点、Wan 3.0 300 点；kling / veo / hailuo / vidu / runway / pixverse 这 9 个本账号 0 笔成交，按同路 16 笔区间标 baseline，预算按上界 3,045.71 点算。单价来源最硬：`/api/v1/pricing` 里没有模型层路径，命中通配「上游点数 x 2、保底 50 点」，真实单价只在 `me/tasks` 的 actualPrice 里；跑过一次就变 live。`catalog` 列 13 个型号的报价 / 来源 / 提交路径；kling 家族 14 个，本包挑最新的，其余写型号名就能跑。`gen` 用同一句话逐个提交，默认走 `/api/v1/videos/generations`，落盘并写 manifest.json 与「对比清单.md」。`doctor` 只发会 400 的探针，做余额前后对比与流水净额，本轮 0 点。需要自备 api.a7w.cn 的 API Key。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 视频生成
  - 多模型横评
  - api.a7w.cn
---

# 文生视频模型台 · 一句话横评 5 个模型，最低 0.44 元一条

> ## 先申请你自己的 API Key
>
> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，
> 扣的是你自己账户的余额。注册、充值、创建 Key 都在 [api.a7w.cn](https://api.a7w.cn/)。
>
> ```bash
> python3 scripts/a7w.py login --key sk-你的key
> ```

## 一句话

**同一句话，5 个模型先报价再出片。** 最便宜 44 点（0.44 元），最贵上界 3,045.71 点（30.46 元），差 **11.7 倍**。

## 价目表（2026-11-08 实测，1 元 = 100 点）

| 型号 | 报价（点/条） | 折合 | 来源 |
|---|---|---|---|
| `muse-video` | **44 - 260** | 0.44 - 2.60 元 | 本账号 8 笔成交；官方 11 点/秒 |
| `sd/doubao-seedance-2-0-260128` | **145.73 - 3,000** | 1.46 - 30 元 | 本账号 5 笔成交 |
| `wan3.0-video` | **300** | 3 元 | 本账号 8 笔成交，全是 300 |
| `volcengine/doubao-seedance-2-5-260628` | **762.30 - 3,045.71** | 7.62 - 30.46 元 | 本账号 3 笔成交 |
| `kling-4-0` / `veo3.1-pro` / `veo3.1-fast` / `hailuo-02-standard` / `hailuo-02-pro` / `vidu-q4` / `runway` / `pixverse-v6` / `pixverse-v6-max` | 44 - 3,045.71（同路区间） | 0.44 - 30.46 元 | 本账号 0 笔成交，标 baseline，保底 50 点 |

## 三条干货

**一、提交端点分两条，走错就是 404。** 目录里 47 个视频型号，`POST /api/v1/videos` 只认 4 个裸模型层 ID
（`muse-video`、`sd/doubao-seedance-2-0-260128`、`volcengine/doubao-seedance-2-5-260628`、`wan3.0-video`）。
拿目录型号去打这条：

```
POST /api/v1/videos  {"model":"kling-4-0"}
-> HTTP 404  {"error":{"code":"model_not_found","message":"The model `kling-4-0` does not exist ..."}}

POST /api/v1/videos/generations  {"model":"kling-4-0"}
-> HTTP 400  {"error":"prompt or content field is required"}
```

同一个型号名，一条 404、一条 400 —— **`/api/v1/videos/generations` 才是横评的提交端点**。本包按型号的历史成功路径分流（muse-video 走 `/videos`，其余 12 个走 `/videos/generations`），`--route` 可强制。

**二、kling 家族是 14 个型号，不是一个。** `GET /api/v1/models` 里 `kling-4-0`、`kling-v2-1-pro`、
`kling-2-6`、`kling-3.0-video`、`kling-3-0-omni`、`kling-3.0-motion-control` 等 14 条都在架，
14 条全部在 `/videos/generations` 上停在 `400 prompt is required`（实测）。本包默认横评最新的一档，
想跑别的档直接写型号名：`--models kling-3-0-omni`。

**三、单价只能反推，价目表里没有。** `GET /api/v1/pricing` 的 115 条规则里没有
`/api/v1/videos/generations`，整张表没有 `modelPricing` 键；模型层命中的是通配
`*`：对外 = 上游实际点数 x 2、单笔保底 50 点。所以真实单价只在
`GET /api/v1/me/tasks` 的 `actualPrice` 里 —— 按 `model` 归集，跑过标 `source=live`，
没跑过用同路 16 笔区间标 `source=baseline`，**不编单价**。

## 完整用法

```bash
# 1) 看 13 个模型：报价 / 来源 / 提交路径（免费）
python3 scripts/run.py catalog

# 2) 先报价：同一句话，多个模型逐个报（免费）
python3 scripts/run.py cost --models muse-video,kling-4-0,veo3.1-pro --seconds 5

# 3) 横评出片：同一句话跑 5 个模型（要 --yes，受 --budget 管）
python3 scripts/run.py gen \
    --models muse-video,sd/doubao-seedance-2-0-260128,kling-4-0,veo3.1-pro,hailuo-02-standard \
    --prompt "雨夜街头，霓虹灯下撑伞的女孩回头，镜头缓慢推近" --seconds 5 --yes

# 4) 只打印请求，一分钱不花
python3 scripts/run.py gen --models muse-video,kling-4-0 --prompt "一只橘猫跳上桌子" --dry-run

# 5) 查询 / 取片（免费）
python3 scripts/run.py status --task-id task_xxx
python3 scripts/run.py wait task_xxx --outdir .
```

## 三步上手

```bash
# 第 1 步：0 点自检（6 个只读端点 + 3 个 400 探针 + 余额前后对比）
python3 scripts/run.py doctor
# 第 2 步：0 点报价（默认 5 个模型）
python3 scripts/run.py cost
# 第 3 步：选一个开跑，或者全跑做横评
python3 scripts/run.py gen --models muse-video --prompt "海边日落，浪花慢镜头" --seconds 5 --yes
```

出片后目录长这样：

```
run-20261108-101500/
├── 01-muse_video.mp4        序号-型号.mp4
├── manifest.json            结构化结果（含实际点数）
└── 对比清单.md              同一句话的五个模型，一张表看完
```

## 规格

| 项 | 值 |
|---|---|
| 提交端点 | `POST /api/v1/videos/generations`（12 个型号）· `POST /api/v1/videos`（muse-video） |
| 查询端点 | `GET /api/v1/tasks/<id>`（免费，轮询只走这条） |
| 型号 | 13 个内置；`--allow-any-model` 可试目录里另外 34 个 |
| 时长 | `--seconds` 1 - 180，默认 5（按型号支持范围为准） |
| 尺寸 | `--size` 宽x高，例如 `1280x720` / `720x1280`，默认模型默认 |
| 预算 | `--budget` 默认 12,500 点（125 元），单位是「点」；一次最多横评 8 个型号 |

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 13 个型号 + 报价 + 来源 + 提交路径 |
| `cost` | 免费 | 同一句话多模型逐个报价，按上界排序 |
| `doctor` | 免费 | 6 个只读端点 + 3 个 400 探针 + 余额/流水对比 |
| `gen` | 按条 | 多模型横评出片，落盘 + manifest + 对比清单 |
| `status` | 免费 | 查任务 |
| `wait` | 免费 | 等任务完成并下载 |
| `sheet` | 免费 | 用 manifest 重出对比清单 |
| `log` | 免费 | 本地台账 |

退出码：`0` 成功 · `2` 用法错 · `4` 缺 `--yes`（说清要花多少）· `5` 超 `--budget`（一个请求都不发）· `6` 调用失败 · `1` 内部错 · `130` 中断。

`--json` 契约：成功 `{"ok": true, …}`；失败 `{"ok": false, "exit": N, "error": {"kind": …, "message": …}}`。
`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 和已有包的分工

| 你的需求 | 用哪个包 | 为什么 |
|---|---|---|
| 同一句话横评几个视频模型，选一个或全跑 | **本包** | 13 个型号逐个报价 + 同 prompt 出片 + 对比清单 |
| 只要 muse-video：4 - 180 秒、按秒计费、凑档不加钱 | `sanjianke-muse-video` | 单模型深度：秒数档位、首帧/多图参考、3 分钟长片 |
| 只要 Seedance / Wan 模型层，含应用层比价 | `sanjianke-model-video` | 单家族深度：4 个模型、应用层 11,000 点对照 |
| 看全站应用层与模型层的差价排行 | `sanjianke-price-radar` | 6 个只读子命令、115 条规则、app-vs-model 排行 |
| 视频后处理（超分 / 去字幕 / 换脸 / 擦 logo） | `sanjianke-video-lab` | 11 档后处理能力，按秒/按次计价 |

本包管「选哪个模型」，上面几个包管「这个模型怎么用到极致」。两边可以串起来：
本包报价选型，再用对应包跑完整产线。

## 免责

- 单价按「点/条」计，实际以 `GET /user/balance/logs` 与 `me/tasks` 的 `actualPrice` 为准。
- 上游按模型预冻结，任务失败全额退回；成片链接约 30 分钟有效，`--wait` 会直接下载到本地。
- 生成内容的合规责任在使用者：用在合法、有授权的素材与用途上。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
