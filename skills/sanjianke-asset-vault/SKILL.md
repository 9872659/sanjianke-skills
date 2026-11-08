---
name: sanjianke-asset-vault
slug: sanjianke-asset-vault
displayName: 素材库管家 · 上传 0 点，11 个应用的素材一表管到底
description: "**上传一个素材 0 点，11 个应用的 22 条 create/remove 入口 + 24 小时到期时间，一张表全看清。** 素材这一层所有生成类 Skill 都缺：传完就忘、地址过期、同一个文件传三遍、清理时才发现 remove 也要钱。本包把它补齐：`upload` 批量上传（`/api/v1/upload` 规则 cost=0）→ 台账记 url / 大小 / 到期时间 / sha256 → 同文件再传自动复用 → `ls` 看剩余小时与标签 → `bind` 登记进 11 个应用之一，先 `cost` 比价，45 点还是 11,000 点一目了然。三条实测硬事实：一、`remove` 不是免费动作，10 个应用按上游点数 ×2 动态计价，`watermark_removal/remove` 更是 100 点/次的去水印主业务；二、价目表里有 create 规则不等于应用目录登记了 create，只有 happy_horse / wan / seedance 登记了；三、seedance 的素材入库三件套按价目表字面命中 `/api/v1/apps/seedance/*` 的 11,000 点/次。7 个免费命令 + 2 个付费命令，付费的缺 `--yes` 退 4、超 `--budget` 退 5 且一个请求都不发。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "素材管理是一条被忽略的底座：所有生成类包都在教怎么出片，没有一个包管「素材在哪、还能用几小时、这个文件是不是传过、清理要花多少钱」。本包只做这一层，并把免费和付费切干净。免费部分：`upload` 走 `POST /api/v1/upload`（multipart 字段名 file，单文件上限 512 MB，规则 cost=0 明文写着不计费），返回 url / path / size / mime_type / type，地址最长 24 小时；台账落在 `~/.a7w/asset-vault/ledger.json`，每条记 id / 文件名 / 大小 / sha256 / url / 到期时间 / 标签 / 绑定历史；同一个文件在有效期内再传直接复用，不再发请求。`ls` 打印剩余小时数，6 小时内到期单独提醒；`tag` 打标签；`prune` 只清本地过期记录。`catalog` 把 11 个应用 × create/remove 共 22 条规则的价格、口径、应用目录登记情况逐条摆出来；`cost` 支持 `--apps` 多应用横评；`doctor` 用 9 个探针自检。付费部分只有两个：`bind` 把素材登记进应用（默认打应用目录真正登记的入口，wan / seedance 这类数组字段强制用 --param 明确给，避免白扣一次钱）、`release` 调 remove 做远端清理。两道闸门：缺 `--yes` 退 4 并说清要花多少点，超过 `--budget` 退 5 且一个请求都不发；`--budget 0` 对只读命令也直接退 5。`--dry-run` 打印完整请求体，`--json` 成功 {\"ok\":true,...}、失败 {\"ok\":false,\"exit\":N,\"error\":{\"kind\":\"...\",\"message\":\"...\"}}。零依赖，只用 Python 标准库。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 素材管理
  - 上传复用
  - api.a7w.cn
---

# 素材库管家 · 上传 0 点，11 个应用的素材一表管到底

> ## 先申请你自己的 API Key
> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的账户；注册、充值、创建 Key 都在 [api.a7w.cn](https://api.a7w.cn/)。
> 拿到 Key 后跑 `python3 scripts/a7w.py login --key sk-你的key`。

**上传一个素材 0 点，11 个应用的 22 条 create/remove 入口和 24 小时到期时间一张表看清。**
这是「素材管理」不是「生成」：7 个免费命令，只有 `bind` / `release` 会动钱，且必须先 `--yes`。

## 价目表：create 从 45 点到 11,000 点

`GET /api/v1/pricing` 现查（2026-11-08 实测，115 条规则里的 22 条）：

| 应用 | create 价 | remove 价 | 默认入口 |
|---|---|---|---|
| smart_clip 智能剪辑 | 45 点/次 | 动态 ×2 | broadcast_mixcut |
| nano_banana 出图 | 72 点/次（带 views 时 25 点/视角） | 动态 ×2 | submit |
| image_human 数字人 | 10 / 15 / 30 / 60 点/输入秒 | 动态 ×2 | submit |
| dressing_diffusion 换装 | 200 点/次 | 动态 ×2 | submit |
| seedsvc 翻唱 | 220 点/次 | 动态 ×2 | submit |
| grok_video | 300 点/次 | 动态 ×2 | submit |
| happy_horse | 650 点/次 | 动态 ×2 | create |
| lipsync 对口型 | 动态 ×3（保底 1 点） | 动态 ×3（保底 1 点） | submit |
| wan 万相视频 | 动态 ×3（保底 1 点） | 动态 ×2 | create |
| watermark_removal | 动态 ×2 | **100 点/次** | remove |
| seedance | **11,000 点/次** | 动态 ×2 | create |

上传是这套流程里唯一的免费写接口：`/api/v1/upload` 的规则是 `{"mode":"flat","cost":0,"markupPercent":0}`，返回地址最长 24 小时。

## 三条别人不会告诉你的

### 一、`remove` 清理不是免费动作
10 个应用的 remove 是 `cost:0 + markupPercent:100`，意思是「按上游实际点数 ×2」——价目表不写死单价，清一次才知道多少钱。
`watermark_removal/remove` 更特殊：它是这个应用的**主业务**「去水印 / 分享链解析」，固定 **100 点/次**。
所以本包把「本地清台账」和「远端清理」分成两条命令：`prune` 免费只动本地，`release` 计费且必须 `--yes`。

### 二、价目表里有 create 规则 ≠ 应用目录登记了 create
`GET /api/v1/apps` 的 22 个应用里，只有 **happy_horse / wan / seedance** 登记了 `create`，只有 **watermark_removal** 登记了 `remove`；
其余应用的入口是 `submit`。价目表给每条 `create` 都写了价（规则按路径前缀匹配），真正能打的是应用目录里那份清单。
`catalog` 把两个来源并排打出来，`bind` 默认走「目录登记的那个入口」，你指定一个不存在的接口时它会直接拒绝并列出可用入口。

### 三、seedance 的素材三件套按价目表字面是 11,000 点/次
`createGroup` / `createAsset` / `deleteAsset` 在应用目录里登记了，但 `/pricing` 里**没有专属规则**，会命中 `/api/v1/apps/seedance/*` 这条通配规则 = 固定 11,000 点/次。
真正入库的字段也是文档级的：`createAsset` 要 `URL` + `GroupId` + `AssetType`，先 `createGroup` 拿 `GroupId`。
本包把这三条单独列在 `catalog` 末尾，通配规则原文写进 `references/api-contract.md`。

## 实测成交价（`GET /api/v1/me/tasks`，免费，全量 1398 条）

| 路径 | 笔数 | actualPrice 区间 |
|---|---|---|
| `/api/v1/apps/nano_banana/submit` | 165 | 72 - 72 |
| `/api/v1/apps/wan/create` | 124 | 120 - 2,400（另有三笔 108,000 / 162,000 / 270,000） |
| `/api/v1/apps/smart_clip/realman_broadcast` | 163 | 8.78 - 1,476 |
| `/api/v1/apps/seedance/create` | 7 | 388 - 11,000 |

`cost --live` 把这些真实成交价排进表里（source=live），没有历史成交的标 source=pricing。
`actualPrice` 是预扣/标价，退款后以 `netPoints` 为准 —— 这条口径 `sanjianke-billing` 讲得最细。

## 完整用法

```bash
# 1) 上传：一个文件 0 点，批量也能一次给
python3 scripts/run.py upload --file 产品图.png --tag product --note "白底主图"
python3 scripts/run.py upload --dir ./素材 --tag 双11
# 2) 台账：id / 剩余小时数 / 标签 / 绑定过哪些应用
python3 scripts/run.py ls
python3 scripts/run.py tag --id e424e6c0 --tag cover --note "主图"
# 3) 比价：同一份素材投给谁最便宜
python3 scripts/run.py cost --apps smart_clip,wan,seedance --seconds 10
# 4) 登记：先干跑看请求体，再 --yes 真提交
python3 scripts/run.py bind --app nano_banana --id e424e6c0 --dry-run
python3 scripts/run.py bind --app nano_banana --id e424e6c0 --yes
# 5) 清理：本地免费，远端计费
python3 scripts/run.py prune
python3 scripts/run.py release --app watermark_removal --param url=https://v.douyin.com/xxx/ --yes
```

`bind` 把素材地址注入到该应用文档里的字段：nano_banana / dressing_diffusion 等用 `image_url`，happy_horse 用 `media`，watermark_removal 用 `url`。
wan / seedance 的素材在数组里，本包不猜，要求你用 `--param` 明确给，例如 `--param 'image_urls=["https://..."]'`（wan）或 `--param 'content=[{"type":"image_url","image_url":{"url":"..."}}]'`（seedance）。

## 和 sanjianke-price-radar / billing / video-lab 的分工

| 你要干的事 | 用哪个 | 它管的是 |
|---|---|---|
| 素材传上去、打标签、复用、看还剩几小时 | **本包** `upload` / `ls` / `tag` | 素材的生命周期 |
| 同一份素材投给 11 个应用，先看谁便宜 | **本包** `cost --apps` | 应用层 create 报价 |
| 把素材登记进某个应用、或从应用清理 | **本包** `bind` / `release` | 素材 → 应用的这一步 |
| 同一个模型走应用层还是模型层、差几倍 | `sanjianke-price-radar` | 定价层，不碰文件 |
| 已经花出去的钱按路径拆开对账 | `sanjianke-billing` | 事后账本 |
| 视频后处理 11 档 / 老片成片流水线 | `sanjianke-video-lab` / `sanjianke-oldfilm-restore` | 生成与后处理 |

一句话：**素材找本包，定价找 price-radar，对账找 billing，生成找 video-lab。** 本包不发一条生成任务。

## 三步上手

```bash
# 第 1 步：自检（9 个只读探针 + 1 次缺参上传，0 点、不建任务）
python3 scripts/run.py doctor
# 第 2 步：看价（免费，两个应用起就能横评）
python3 scripts/run.py catalog
python3 scripts/run.py cost --apps nano_banana,smart_clip,grok_video
# 第 3 步：传一个素材，登记进最便宜的那个
python3 scripts/run.py upload --file 首图.png --tag cover
python3 scripts/run.py bind --app smart_clip --id <id> --param ... --yes
```

`doctor` 实测：`√` 余额可用（冻结 0）· `√` 115 条规则 / 22 条 create+remove 全在 · `√` 22 个应用 / 11 个目标应用全在 · `√` 上传规则 cost=0 ·
`√` 上传探针 HTTP 200 code=0 · `√` 任务查询 · `√` 我的任务台账可读 · `√` 流水可读。

## 常用命令

```bash
python3 scripts/run.py upload --file a.png --file b.mp4   # 一次传多个
python3 scripts/run.py prune --older-than 24 --dry-run     # 先看会清哪几条
python3 scripts/run.py cost --offline                      # 不联网，用内置基线价
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--budget` | 5000 | 点数上限（**单位：点**，1 元 = 100 点）；给 0 直接退 5 |
| `--file` / `--dir` | — | `upload` 的文件，可重复给，或整目录 |
| `--apps` / `--seconds` | 全部 / 10 | 横评哪些应用、按秒计价的应用按多少秒估 |
| `--mode` / `--views` | fast / 0 | image_human 档位；nano_banana 视角数（25 点/视角） |
| `--entry` / `--param` | auto / — | `bind` 打哪个接口；请求体参数 `key=value`（值可以是 JSON） |
| `--dry-run` / `--yes` | — / — | 只打印请求 / 付费确认开关 |

## 退出码与 `--json`

`0` 成功 · `2` 用法错 · `4` 需要 `--yes`（会说清要花多少点）· `5` 预算不足（一个请求都不发）· `6` 调用失败 · `1` 内部错 · `130` 中断。
成功 `{"ok": true, "count": 11, "apps": [...], "estimatedPoints": 0}`；失败 `{"ok": false, "exit": 4, "error": {"kind": "confirm", "message": "…"}}`。
`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 文件结构

`sanjianke-asset-vault/` = `SKILL.md` · `README.md` · `LICENSE.md` ·
`references/`（`api-contract.md` 端点实测原文、`troubleshooting.md` 按现象找原因）·
`scripts/`（`a7w.py` 零依赖客户端、`run.py` 本包命令层）。台账在 `~/.a7w/asset-vault/ledger.json`。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
