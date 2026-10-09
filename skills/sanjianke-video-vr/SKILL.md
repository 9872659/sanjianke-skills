---
name: sanjianke-video-vr
slug: sanjianke-video-vr
displayName: 三剪客 · 视频增强台
description: "把 api.a7w.cn 在架的那 10 档视频增强能力做成一个命令行台子：4K旗舰版 / 标准超分1080P / 高清超分2K / 超清超分4K / 人像增强 / 字幕擦除 / 人像卡通化 / 人像抠像 / 画质综合增强 / 视频校色，共用同一套「上传 → 提交 → 轮询 → 下载」流程，只是路径与单价不同。**按秒计费**，所以包内自带免费 `tiers`（10 档与单价）与 `cost`（先算这一条多少钱）、`doctor`（Key/档位/上传/素材入口判据（零成本实测）/ffprobe 体检），以及把免费闸门全跑一遍的 `--dry-run`。两处实测坑已内置拦截：`upscale` 档**不校验素材可达性**（传 404 地址也会扣费），且不传 `duration` 时服务端探测失败会**按 5 秒收费**。素材先用本网关 `upload` 传上来即可，**不再需要任何第三方站点**。零依赖、只用 Python 标准库，不内嵌任何密钥（用你自己的 api.a7w.cn Key）。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。价格与规格以线上为准。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "视频增强不是「一个功能」，是 10 档按秒计费的能力，选错档位要么白花钱要么白等。本包把它们收成一个台子：`tiers` 一屏看完 10 档单价与单条上限，`cost` 在花钱之前告诉你「这条 12 秒的片子要 108 点（¥1.08）」，`enhance --dry-run` 把白名单、素材可达性、时长、上限、规格、预算全验一遍却不提交。**两处实测坑已内置拦截**：① `upscale`（4K旗舰版 30 点/秒）**完全不校验素材可达性**，喂一个 404 地址它照样建任务并扣费——本包对每一档都先探素材可达性再提交；② `duration` 不传时服务端自己 ffprobe，探测不到就**按 5 秒收费**——本包一律先本地探测，拿不到就报错要求显式 `--duration`，绝不静默按 5 秒。另有 `doctor` 体检与 `--json` 机读契约（成功 `{ok:true}`／失败 `{ok:false,exit,error.kind}`，exit 2 用法 / 3 闸门 / 4 需 --yes / 5 预算 / 130 中断）。零依赖、只用标准库、不内嵌密钥。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 视频增强
  - 视频超分
  - 字幕擦除
  - api.a7w.cn
---

# 三剪客 · 视频增强台

`api.a7w.cn` 在架的那 10 档视频增强能力，共用一个「上传 → 提交 → 轮询 → 下载」流程，
只是路径和单价不同 —— 所以做成**一个台子**，而不是 10 个包。

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或用 `login` 子命令保存，或直接传给 `--key`。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

---

## 10 档（单价 = 点/秒，1 元 = 100 点）

| 档位 id | 中文名 | 路径 | 点/秒 | 元/秒 | 单条上限 | 素材要求 |
|---|---|---|---|---|---|---|
| `upscale` | 4K旗舰版 | `POST /api/v1/video/upscale` | 30 | ¥0.30 | **30 秒** | 任意公网地址 |
| `superres` | 标准超分 1080P | `POST /api/v1/video/viapi/superres` | 9 | ¥0.09 | 600 秒 | **本站素材** |
| `superres2k` | 高清超分 2K | `.../viapi/superres2k` | 15 | ¥0.15 | 600 秒 | **本站素材** |
| `superres4k` | 超清超分 4K | `.../viapi/superres4k` | 20 | ¥0.20 | 600 秒 | **本站素材** |
| `portrait` | 人像增强 | `.../viapi/portrait` | 18 | ¥0.18 | 600 秒 | **本站素材** |
| `subtitle` | 字幕擦除 | `.../viapi/subtitle` | 9 | ¥0.09 | 600 秒 | **本站素材** |
| `cartoon` | 人像卡通化 | `.../viapi/cartoon` | 24 | ¥0.24 | 600 秒 | **本站素材** |
| `segment` | 人像抠像 | `.../viapi/segment` | 9 | ¥0.09 | **60 秒** | **本站素材** |
| `enhance` | 画质综合增强 | `.../viapi/enhance` | 15 | ¥0.15 | 600 秒 | **本站素材** |
| `colorize` | 视频校色 | `.../viapi/colorize` | 9 | ¥0.09 | 600 秒 | **本站素材** |

**`portrait` 值得优先试**：上游当前**公测免费**（成本 0），售价 18 点/秒是纯毛利档；
但它有输入门槛 —— **输入需 <1920×1080**。

---

## ⚠️ 三件事必须在动手前知道

### 1. `upscale` 档**不校验素材可达性** —— 这是最容易白花钱的一档

给它一个 404 的地址，它**照样返回 201 并冻结点数**（30 点/秒，2 秒就 60 点）。
所以：**本包对每一档都先探素材可达性 + 本地 ffprobe，探不到就拒绝提交**，
要强行绕过必须显式 `--force`。

### 2. `duration` 不传就会被「按 5 秒收费」

服务端逻辑是：

```js
let d = Math.ceil(Number(payload.duration) || 0);
if (!d) d = Math.ceil(await probeVideoDuration(url));   // 服务端自己 ffprobe
if (!(d > 0)) d = 5;                                    // ← 探测不到就按 5 秒
```

本包一律**先本地探测**；拿不到时长就**报错要求显式 `--duration`**，
**绝不静默按 5 秒提交**（那等于为未知时长付费）。

### 3. `viapi/*` 那 9 档**只收「本网关素材」** —— 先 `upload`

**素材通道只有一条：用本网关的 `upload` 把本地文件传上来，再把返回的地址交给 `--url`。**
**不再需要任何第三方站点。**

```
POST api.a7w.cn/api/v1/upload      multipart/form-data，字段名 file
      ↓ 200 返回
https://oss.gpu.likeadmin.cn/openapi/…      ← 把这个地址原样交给 --url 即可
```

```bash
python3 scripts/run.py upload 你的视频.mp4       # 免费，不建任务
python3 scripts/run.py doctor                    # 零成本实测线上入口判据
python3 scripts/run.py enhance --tier colorize --url <上面返回的地址> \
    --duration 12 --budget 200 --yes --wait --out out.mp4
```

| 你的素材地址 | `upscale` | 其余 9 档 |
|---|---|---|
| 本网关 `upload` 返回的 `oss.gpu.likeadmin.cn/openapi/…` | ✅ 可用 | 由线上入口判据决定（跑 `doctor` 实测） |
| 任意第三方公网地址 | ✅ 可用 | ❌ 400 `url_not_allowed`（**未扣费**） |
| 本站素材地址 | ✅ 可用 | ✅ 可用 |

⚠️ **入口判据以线上为准。** `doctor` 的「入口白名单」一项会**零成本实测**：
拿一个上传域里**根本不存在的地址**去打这一档 ——
**未放行 → 400 `url_not_allowed`；已放行 → 502 `oss_mirror_failed`**。
两条路都在**冻结扣费之前**返回，所以不建任务、不扣费。

**本包还会在本地提前用人话拦住**，不会让你白撞一次请求：

```
✗ **标准超分 1080P**（`superres`）只收**本网关素材**，你的地址不在入口判据内；提交必然被拒
  （好在服务端是在扣费之前拒的，不会花钱）。
      → 先把本地文件用本网关 `upload` 传上来，再用它返回的地址：
          python3 scripts/run.py upload 你的视频.mp4
      → 或换 `sanjianke-vr-upscale-4k`（4K旗舰版，不需要判据，收任意公网地址）；
      → 或跑 `doctor` 看「入口白名单」这一项的零成本实测结果。
```

### ⚖️ 字幕擦除（`subtitle`）的合规边界

`subtitle` 档做的是**去除画面上的硬字幕 / 文字**。使用它意味着你承诺：

- **你对素材拥有合法权利** —— 是你自己拍摄/制作的，或已获得权利人明确授权；
- **不得用于去除他人作品的权利管理信息**（水印、署名、版权标识等），
  也不得用于规避平台原创声明、盗用他人内容后伪装成原创；
- 需要保留原始素材与授权凭证，以备平台或权利人核查。

**本包不判断你的授权，授权责任在使用者。** 拿不准就不要做这一档。

---

## 快速开始

```bash
# 0) 看看有哪些档位、各多少钱（免费、连 Key 都不用）
python3 scripts/run.py tiers

# 1) 配一次 Key（验证 + 保存到 ~/.a7w/config.json）
python3 scripts/run.py login --key sk-你的key

# 2) 环境体检：Key / 档位表 / 上传入口 / 素材白名单 / 本机 ffprobe（免费，不建任务）
python3 scripts/run.py doctor

# 3) 先算钱：这条 12 秒的片子要多少钱（纯本地，一次请求都不发）
python3 scripts/run.py cost --for superres:12
python3 scripts/run.py cost --for upscale:10 --for subtitle:120

# 4) 白验一遍：把能免费验的全验掉，但**不提交**
python3 scripts/run.py enhance --tier superres \
    --url https://cdn2.jiujiushuyuan.cn/vr/demo/your.mp4 \
    --duration 12 --dry-run

# 5) 正式提交（--yes 才真花钱），并一次轮询到出片
python3 scripts/run.py enhance --tier superres \
    --url https://cdn2.jiujiushuyuan.cn/vr/demo/your.mp4 \
    --duration 12 --budget 500 --yes --wait --out out.mp4

# 6) 也可以先提交、稍后再查
python3 scripts/run.py enhance --tier upscale --url <地址> --duration 8 --yes
python3 scripts/run.py status task_xxxx --out out.mp4
python3 scripts/run.py tasks
```

---

## 闸门顺序（为什么 `--dry-run` 能免费验这么多）

线上服务端的判定顺序是：

```
空 URL  →  素材白名单  →  素材可达性/转存  →  ffprobe 时长  →  单条上限
        →  输入规格预检  →  冻结扣费  →  提交上游
```

**扣费点很靠后**，所以参数错、地址不在白名单、规格不符，**全部在扣费之前返回，天然免费**。
本包再在此之上补了「素材可达性」（替 `upscale` 补课）、「本机 ffprobe」、「预算」三道，
全部发生在提交之前：

```
[闸门1] 用法      --url / --tier / --duration / --budget 合法性                  exit 2
[闸门2] 白名单    9 档要求本站素材（本包提前拦，服务端也会拦）                   exit 3
[闸门3] 可达性    探素材 HTTP（**替 upscale 补的课**，它自己不看）               exit 3
[闸门4] 时长      本地 ffprobe；拿不到就报错，绝不静默 5 秒                      exit 3
[闸门5] 上限      单条时长上限（upscale 30s / segment 60s / 其余 600s）          exit 3
[闸门6] 规格      超分与人像增强输入需 <1920×1080                                exit 3
[闸门7] 预算      --budget（**单位：点**）                                       exit 5
[闸门8] 确认      不加 --yes 只报价，不提交                                      exit 4
                   ↓
              才真正 POST 提交（这一步之后才会花钱）
```

**唯一必须花钱才能知道的事**：上游到底能不能处理这条素材。

---

## 子命令一览

| 子命令 | 作用 | 花钱 |
|---|---|---|
| `tiers` | 列出 10 档：单价 / 单条上限 / 素材要求 | 免费 |
| `login --key sk-x` | 验证并保存 Key 到 `~/.a7w/config.json` | 免费 |
| `whoami` | 确认 Key 有效 | 免费 |
| `doctor` | 体检：Key / 档位表 / 上传入口 / 白名单 / ffprobe | 免费，不建任务 |
| `cost [秒数] --tier X` / `--for X:秒` | 只算钱，一次请求都不发 | 免费 |
| `upload <文件>` | 把本地视频传到本站，拿地址 | 免费，不建任务 |
| `enhance --tier --url --duration` | 提交增强任务（`--dry-run` 白验 / `--wait` 等出片） | **真花钱** |
| `status <taskId> [--out]` | 查状态；成片转存完成后可下载 | 免费 |
| `tasks` | 列出本包提交过的任务（本地台账） | 免费 |

---

## `--json` 机读契约

```json
// 成功
{"ok": true, ...}
// 失败
{"ok": false, "exit": 3, "error": {"kind": "gate", "message": "..."}}
```

| exit | 含义 | `error.kind` |
|---|---|---|
| 0 | 成功 | — |
| 1 | 内部错误 | `internal` |
| 2 | 用法错误 | `usage` |
| 3 | 闸门没过（白名单 / 可达性 / 时长 / 上限 / 规格） | `gate` |
| 4 | 需要 `--yes`（报价已打印，未提交） | `confirm` |
| 5 | 预算超限 | `budget` / `insufficient_points` |
| 130 | 被中断 | `interrupt` |

`--json` 写在子命令**前面或后面都可以**（`--json tiers` 与 `tiers --json` 等价）。

---

## 计费口径（必须与中继完全一致）

```
冻结 = ceil(输入秒数) × 单价        先向上取整到整秒，再乘费率
结算 = 完成后按实际时长结算，多退少补
失败 = 全额自动退回（有幂等保护）
1 元 = 100 点
```

例：12 秒 → `superres` 108 点（¥1.08）／`upscale` 360 点（¥3.60）／`subtitle` 108 点（¥1.08）。

---

## 报错 → 人话

| 上游 code | 本包怎么说 |
|---|---|
| `empty_url` / `pixverse_empty_url` | 没给 `videoUrl` |
| `url_not_allowed` | 这一档只收本站素材；改用 `upscale`，或把素材放到本站/本站七牛 |
| `invalid_resolution` | `upscale` 目前只支持 `4k` |
| `superres_input_too_large` | 超分输入需 <1920×1080，先降分辨率或改用 `upscale` |
| `oss_mirror_failed` | 素材转存失败（**未扣费**）：地址取不到 / 不是视频 / 需要鉴权 |
| `insufficient_points` | 点数不足，去 https://api.a7w.cn/ 充值 |
| `tool_not_launched` | 该档位未开放（例如插帧档已下线） |
| `not_found` | 任务不存在（taskId 写错，或不是这个档位提交的） |
| `unauthorized` | Key 无效/缺失，用 `login` 保存或设 `A7W_API_KEY` |

---

## 查询为什么要带档位

查询接口是**路径形式**：

```
GET /api/v1/video/upscale/<taskId>
GET /api/v1/video/viapi/<tier>/<taskId>
```

所以 `status` 需要知道档位（`--tier`）。本包提交过的任务会记进本地台账
`~/.a7w/video-vr-tasks.json`，`status` 会自己去找，不用你手动填。

⚠️ **不要用 `GET /api/v1/tasks/<id>` 查这 10 档** —— 那是网关自有层，
返回 `{"code":0,"msg":"任务不存在"}`，查不到 relay 的任务。

---

## 和其它超分包的区别（避免重复劳动）

| 包 | 走什么 | 用途 |
|---|---|---|
| **本包** `sanjianke-video-vr` | relay 的 `/api/v1/video/*`（`api.a7w.cn` 在架的 10 档） | 按秒计费的多档视频增强，含字幕擦除/抠像/卡通化/校色 |
| `sanjianke-video-upscale` | `api.a7w.cn` 的 `flashvsr` 插件 + 本地 ffmpeg | 超分专题：糊片救 4K 的判断标准与两条路线 |
| `a7w-flashvsr` | 网关自有 app `flashvsr` | FlashVSR 超分插件 |

**别的包都没有的**：字幕擦除、人像抠像（mask 视频）、人像卡通化、视频校色、
画质综合增强，以及**按秒计费 + 免费档位/报价/白验**这一套成本控制。

---

## 已知边界（如实说明）

- **9 档只收本网关素材**：先用 `upload <文件>` 上传、再用返回的地址提交（见上文 §3）。
  **入口判据以线上为准** —— `doctor` 会**零成本实测**并如实报告（400 = 未放行，502 = 已放行，
  两条路都在扣费之前，都不花钱）。不需要任何第三方站点。
- **`tiers` 的在线权威源不稳定**：线上 `GET /api/v1/video/viapi/tools` 早先免鉴权可读，
  后来变成 401/404。本包会自动退回内置档位表（单价取自 `api.a7w.cn` 在架能力），
  并把「在线源当前不可达」如实打出来。**价格与规格以线上为准。**
- **输入规格是上游限制**（超分 <1920×1080、卡通化画面人数 ≤5、抠像总帧数 ≤2000 等），
  本包只能**提前拦**，不能改变上游行为。

---

## 相关文件

- `references/api-contract.md` —— 10 档完整契约：请求/查询/单价/上限/白名单/闸门顺序
- `references/cost-and-limits.md` —— 计费口径、各档上限、输入规格、成本与毛利
- `references/troubleshooting.md` —— 报错对照、排错顺序、`--json` 契约、真机实测记录

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
