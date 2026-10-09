---
name: sanjianke-vr-segment
slug: sanjianke-vr-segment
displayName: 三剪客 · 人像抠像
description: "把 `api.a7w.cn` 在架的**「人像抠像」这一档**做成一个独立的命令行 Skill：`POST /api/v1/video/viapi/segment`，**按秒计费 9 点/秒（¥0.09/秒）**，单条上限 60s。输出是**人像 mask 视频**（不是透明背景 MP4），要自己做合成；单条上限只有 60 秒。库里自带免费 `info`（单价/上限/素材要求/输入规格）、`points`（查余额）、`doctor`（Key / 上传入口 / 素材入口判据 / 素材可达性 / 本机 ffprobe 体检，**零成本实测**）与 `cost`（**先算清这一条多少钱**，纯本地一次请求都不发），以及把扣费之前能验的全跑一遍的 `--dry-run`。两处实测坑已内置拦截：`duration` 不传时服务端探测失败会**按 5 秒收费**，所以本包一律先本地 ffprobe、拿不到就报错要求显式 `--duration`，**绝不静默按 5 秒提交**；提交前一定先探素材可达性，探不到就拒提交。素材先用本网关 `upload` 传上来即可，**不再需要任何第三方站点**。零依赖、只用 Python 标准库、不内嵌任何密钥（用你自己的 api.a7w.cn Key，注册领 Key 见 https://api.a7w.cn/ ）。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "视频增强不是「一个功能」，而是 **9 档按秒计费**的能力，选错档位要么白花钱要么白等。本包**只做 `segment`（人像抠像）这一档**：9 点/秒，单条上限 60s，输入规格 **总帧数 ≤2000**（30fps≈66s，本站收紧 60s）；**输出人像 mask 视频**。`cost <秒数>` 在花钱之前就告诉你这一条要多少点，`enhance --dry-run` 把素材入口判据（本档只收本网关素材（先 upload））、素材可达性、时长、上限、规格、预算全验一遍却**不提交**。**两处实测坑已内置拦截**：① `duration` 不传时服务端自己 ffprobe，探测不到就**按 5 秒收费** —— 本包一律先本地探测，拿不到就报错要求显式 `--duration`；② 本包在提交前一定先探素材可达性（输出是**人像 mask 视频**（不是透明背景 MP4），要自己做合成；单条上限只有 60 秒），探不到就拒提交。素材先用本网关 `upload` 上传、再用返回的地址提交，**不再需要任何第三方站点**；`doctor` 会**零成本实测**这道入口判据并如实报告。另有 `info` / `points` / `doctor` 体检与 `--json` 机读契约（成功 `{ok:true}`／失败 `{ok:false,exit,error.kind}`，exit 2 用法 / 3 闸门 / 4 需 --yes / 5 预算 / 130 中断）。零依赖、只用标准库、不内嵌密钥。包内含完整操作文档与零依赖客户端（`SKILL.md` + `references/`）。价格与规格以线上为准。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 人像抠像
  - mask视频
  - 视频增强
---

# 三剪客 · 人像抠像

`api.a7w.cn` 在架能力里的**「人像抠像」这一档**，独立成一个包：
只做这一件事，所以参数、提示、报错都收窄到这一档。

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或用 `login` 子命令保存，或直接传给 `--key`。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

---

## 这一档是什么

| 项 | 值 |
|---|---|
| 档位 id | `segment` |
| 中文名 | **人像抠像** |
| 提交路径 | `POST /api/v1/video/viapi/segment` |
| 上游动作 | `SegmentVideoBody` |
| 单价 | **9 点/秒**（¥0.09/秒） |
| 单条上限 | **60 秒** |
| 素材要求 | **本网关素材**（先 `upload`） |
| 输入规格 | **总帧数 ≤2000**（30fps≈66s，本站收紧 60s）；**输出人像 mask 视频** |
| 典型场景 | 人像分割/抠像，便于换背景与后期合成 |

> 💡 计费口径：`ceil(时长秒) × 9`，1 元 = 100 点。先用 `cost <秒数>` 看这条多少钱。

---

## ⚠️ 动手前必须知道的三件事

### 1. 这一档**只收「本网关素材」**（先 `upload`）

本档**只收「本网关素材」** —— 先用本网关的 `upload` 把本地文件传上来，再把返回的地址交给 `--url`。**不再需要任何第三方站点。**

```
POST api.a7w.cn/api/v1/upload      multipart/form-data，字段名 file
      ↓ 200 返回
https://oss.gpu.likeadmin.cn/openapi/…      ← 把这个地址原样交给 --url 即可
```

`upload` 子命令就是干这件事的：

```bash
python3 scripts/run.py upload 你的视频.mp4
# → url = https://oss.gpu.likeadmin.cn/openapi/…
python3 scripts/run.py doctor --url <上面那个 url>   # 免费确认能提交
```

任意第三方地址会被服务端在**扣费之前**拒掉（`400 url_not_allowed`，**不花钱**），本包还会**提前**在本地拦一道，让你不用白跑一次请求。

⚠️ **入口白名单以线上为准**：`doctor` 会**零成本实测**这道判据并如实报告（探针被 400 拒 = 该前缀当前未放行；被 502 挡在素材镜像 = 已放行，两者都不扣费）。若某天未放行，改走本站素材地址，或先用 `sanjianke-vr-upscale-4k`（不收白名单，收任意公网地址）。

### 2. `duration` 不传就会被「按 5 秒收费」

服务端逻辑是：

```js
let d = Math.ceil(Number(payload.duration) || 0);
if (!d) d = Math.ceil(await probeVideoDuration(url));   // 服务端自己 ffprobe
if (!(d > 0)) d = 5;                                    // ← 探测不到就按 5 秒
```

本包一律**先本地探测**；拿不到时长就**报错要求显式 `--duration`**，**绝不静默按 5 秒提交**（那等于为未知时长付费）。

### 3. 免鉴权的在线档位表当前**不可达**

`GET /api/v1/video/viapi/tools`（免鉴权价目表）早先免鉴权可读（200），后来变成 **401 / 404**。所以本包的单价取自 **`api.a7w.cn` 在架能力**（内置档位表），`info` 会**如实打印来源**；若在线源恢复，本包会自动采用线上值。**价格与规格以线上为准**，本包不假装内置值就是在线的权威值。


---

## 快速开始

```bash
# 0) 看这一档的单价、上限、素材要求、输入规格（免费、连 Key 都不用）
python3 scripts/run.py info

# 1) 配一次 Key（验证 + 保存到 ~/.a7w/config.json）
python3 scripts/run.py login --key sk-你的key

# 2) 环境体检（免费，不建任务）；它还会**零成本实测**素材入口判据
python3 scripts/run.py doctor
python3 scripts/run.py doctor --url <你的视频地址>

# 3) 先算钱：这条 12 秒的片子要多少钱（纯本地，一次请求都不发）
python3 scripts/run.py cost 12

# 4) 把本地素材传到本网关，拿一个可用地址（免费，不建任务）
python3 scripts/run.py upload 你的视频.mp4

# 5) 白验一遍：把能免费验的全验掉，但**不提交**
python3 scripts/run.py enhance \
    --url <第 4 步返回的地址> \
    --duration 12 --dry-run

# 6) 正式提交（--yes 才真花钱），并一次轮询到出片
python3 scripts/run.py enhance \
    --url <第 4 步返回的地址> \
    --duration 12 --budget 180 --yes --wait --out out.mp4

# 7) 也可以先提交、稍后再查
python3 scripts/run.py status task_xxxx --out out.mp4
python3 scripts/run.py tasks
python3 scripts/run.py points
```

> `--url` 的地址**来自第 4 步的 `upload`**（`oss.gpu.likeadmin.cn/openapi/…`），
> 原样贴进来即可 —— 本档不收第三方站点的地址。

---

## 闸门顺序（为什么 `--dry-run` 能免费验这么多）

线上服务端的判定顺序是：

```
空 URL  →  素材入口判据  →  素材可达性/转存  →  ffprobe 时长  →  单条上限
      →  输入规格预检  →  冻结扣费  →  提交上游
```

**扣费点很靠后**，所以参数错、地址不在入口判据内、规格不符，**全部在扣费之前返回，天然免费**。

| 闸门 | 内容 | 不过时 |
|---|---|---|
| [闸门1] 用法 | `--url` / `--duration` / `--budget` 合法性 | exit 2 |
| [闸门2] 素材入口 | 本档只收本网关素材（先 `upload`；本包提前拦，服务端也会拦） | exit 3 |
| [闸门3] 可达性 | 探素材 HTTP HEAD/GET（探不到就拒提交） | exit 3 |
| [闸门4] 时长 | 本地 ffprobe；拿不到就报错，**绝不静默按 5 秒** | exit 3 |
| [闸门5] 上限 | 单条时长上限 60s | exit 3 |
| [闸门6] 规格 | **总帧数 ≤2000**（30fps≈66s，本站收紧 60s）；**输出人像 mask 视频** | exit 3 |
| [闸门7] 预算 | `--budget`（**单位：点**） | exit 5 |
| [闸门8] 确认 | 不加 `--yes` 只报价，不提交 | exit 4 |
| → 真提交 | POST /api/v1/video/viapi/segment（**这一步之后才会花钱**） | — |

**唯一必须花钱才能知道的事**：上游到底能不能处理这条素材。

---

## 子命令一览

| 子命令 | 作用 | 花钱 |
|---|---|---|
| `info [--online]` | 看本档单价 / 上限 / 素材要求 / 输入规格 | 免费 |
| `login --key sk-x` | 验证并保存 Key 到 `~/.a7w/config.json` | 免费 |
| `whoami` | 确认 Key 有效 | 免费 |
| `points` | 查点数余额 | 免费 |
| `doctor [--url 地址]` | 体检：Key / 上传入口 / 素材入口判据 / 可达性 / ffprobe | 免费，不建任务 |
| `cost <秒数>` | 只算钱，一次请求都不发 | 免费 |
| `upload <文件>` | 把本地视频传到本网关，拿一个可用地址 | 免费，不建任务 |
| `enhance --url --duration` | 提交本档任务（`--dry-run` 白验 / `--wait` 等出片） | **真花钱** |
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

`--json` 写在子命令**前面或后面都可以**（`--json info` 与 `info --json` 等价）。

---

## 计费口径（必须与中继完全一致）

```
冻结 = ceil(输入秒数) × 单价        先向上取整到整秒，再乘费率
结算 = 完成后按实际时长结算，多退少补
失败 = 全额自动退回（有幂等保护）
1 元 = 100 点
```

例：12 秒 → `ceil(12)=12` × 9 = **108 点（¥1.08）**。

---

## 报错 → 人话

| 上游 code | 本包怎么说 |
|---|---|
| `empty_url` / `pixverse_empty_url` | 没给 `videoUrl` |
| `url_not_allowed` | 这一档只收本网关素材：先 `upload <文件>`，再用返回的地址；或换 `sanjianke-vr-upscale-4k` |
| `invalid_resolution` | `upscale` 目前只支持 `4k`（本包不涉及） |
| `superres_input_too_large` | 超分输入需 <1920×1080，先降分辨率 |
| `oss_mirror_failed` | 素材转存失败（**未扣费**）：地址取不到 / 不是视频 / 需要鉴权 |
| `insufficient_points` | 点数不足，去 https://api.a7w.cn/ 充值 |
| `tool_not_launched` | 该档位未开放 |
| `not_found` | 任务不存在（taskId 写错，或不是这个档位提交的） |
| `unauthorized` | Key 无效/缺失，用 `login` 保存或设 `A7W_API_KEY` |

---

## 查询为什么要带档位

查询接口是**路径形式**：

```
GET /api/v1/video/viapi/segment/<taskId>
```

本包提交过的任务会记进本地台账 `~/.a7w/video-vr-tasks.json`，`status` 会自己去找档位，不用你手动填。

⚠️ **不要用 `GET /api/v1/tasks/<id>` 查这一档** —— 那是网关自有层，返回 `{"code":0,"msg":"任务不存在"}`，查不到 relay 的任务。

---

## 和别的包的区别（避免重复劳动）

| 包 | 走什么 | 用途 |
|---|---|---|
| **本包** `sanjianke-vr-segment` | relay 的 `POST /api/v1/video/viapi/segment` | 只做「人像抠像」这一档 |
| `sanjianke-video-vr` | 同样这 10 档，**合一**的多档包 | 想在一处对比/切换档位时用 |
| `sanjianke-video-upscale` | `api.a7w.cn` 的 `flashvsr` 插件 + 本地 ffmpeg | 超分专题：糊片救 4K 的判断标准与两条路线 |
| `a7w-flashvsr` | 网关自有 app `flashvsr` | FlashVSR 超分插件 |

---

## 已知边界（如实说明）

- **素材入口判据以线上为准**：本档只收本网关素材（先 `upload` 拿地址）。`doctor` 会**零成本实测**这个前缀当前有没有被放行，并如实报告（400 = 未放行，502 = 已放行，两者都不扣费）。若某天未放行，改走本站素材地址，或先用 `sanjianke-vr-upscale-4k`。
- **`info` 的在线权威源不稳定**：线上 `GET /api/v1/video/viapi/tools` 早先免鉴权可读，后来变成 401/404。本包会自动退回内置档位表（单价取自 `api.a7w.cn` 在架能力），并把「在线源当前不可达」如实打出来。**价格与规格以线上为准。**
- **输入规格是上游限制**（**总帧数 ≤2000**（30fps≈66s，本站收紧 60s）；**输出人像 mask 视频**），本包只能**提前拦**，不能改变上游行为。

---

## 相关文件

- `references/api-contract.md` —— 本档完整契约：请求 / 查询 / 单价 / 上限 / 白名单 / 闸门顺序
- `references/cost-and-limits.md` —— 计费口径、单条上限、输入规格、成本与毛利
- `references/troubleshooting.md` —— 报错对照、排错顺序、`--json` 契约、真机实测记录

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
