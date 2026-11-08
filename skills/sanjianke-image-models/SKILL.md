---
name: sanjianke-image-models
slug: sanjianke-image-models
displayName: 文生图模型台 · 6 点一张图，多模型横评
description: "**6 点一张图，一条命令横评 3 个出图模型。** 同一句 prompt 先逐个报价：gpt-image-2.6 6 点、Seedream 5.0 Flash 15.60 点、GPT Image 2 26 点，最贵与最便宜差 4.3 倍，看完价再决定跑一个还是全跑。图片线单价不在 `GET /api/v1/pricing` 里（115 条规则没有 `/api/v1/images/*`），本包按 `GET /api/v1/me/tasks` 的 actualPrice 归集：跑过用你的成交价，没跑过用同路 70 笔流水的 4 - 13.78 点区间标基线，不编单价。`catalog` 把 49 个图片型号分成 14 个可调用与 35 个待验证，`gen` 预检先拦住。出图落盘带命名规范，并生成 manifest.json 与「对比清单.md」。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "多模型出图先解决「先花谁的钱」：先报价，再出图。`cost` 用同一句 prompt 逐个报价 —— gpt-image-2.6 6 点/张、Seedream 5.0 Flash 15.60 点/张、GPT Image 2 26 点/张，最贵与最便宜差 4.3 倍。`gen` 按同一句 prompt 逐个出图，落盘带命名，并写 manifest.json 与「对比清单.md」。单价来源最硬：`GET /api/v1/pricing` 的 115 条规则里没有 `/api/v1/images/*`，图片线按型号计次，真实单价只在 `GET /api/v1/me/tasks` 的 actualPrice 里；本包按 model 归集，跑过标 source=live，没跑过用同路 70 笔流水的 4 - 13.78 点区间标 source=baseline，不编单价。`catalog` 分出 49 个图片型号里 14 个已上架、35 个待验证（channel=official，实测返回 404 HTML），`gen` 预检先拦住这批。`doctor` 只探 gpt-image-2.6 一条（422 停在参数校验，0 点）并做余额前后对比。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 图片生成
  - 多模型横评
  - api.a7w.cn
---

# 文生图模型台 · 6 点一张图，多模型横评

> ## 先申请你自己的 API Key
>
> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，
> 扣的是你自己账户的余额。注册、充值、创建 Key 都在 [api.a7w.cn](https://api.a7w.cn/)。
>
> ```bash
> python3 scripts/a7w.py login --key sk-你的key
> ```

## 一句话

**6 点一张图，先报价再选模型。** 同一句 prompt 给 3 个型号各报一次价，最贵与最便宜差 **4.3 倍**。

## 价目表（按上界，2026-11-08 实测）

| 型号 | 单价（点/张） | 折合 | 来源 |
|---|---|---|---|
| `gpt-image-2.6` | **6** | 0.06 元 | 本账号流水 43 笔各 -6 |
| `seedream-5-0-flash` | 15.60 | 0.16 元 | me/tasks actualPrice |
| `gpt-image-2` | 26 | 0.26 元 | me/tasks actualPrice |
| `gpt-image-2-pro` | 39 - 104 | 0.39 - 1.04 元 | me/tasks 17 笔 |
| `nano-banana-pro` | 72 | 0.72 元 | 应用层同型号成交价 |

1 元 = 100 点。以上 5 个都是「已上架」；目录里另有 35 个型号待验证，`catalog --all` 能看到。

## 三条干货

**一、单价不在价目表里。** `GET /api/v1/pricing` 的 115 条规则里没有 `/api/v1/images/*`，
图片线按型号计次。同一条路径最近 1000 条流水里有 71 笔结算，70 笔落在 4 - 13.78 的 7 个价位上：
`-4 / -6 / -7.8 / -10.54 / -10.6 / -12 / -13.78`，而流水条目不记 model。
所以单价只能从 `GET /api/v1/me/tasks` 的 actualPrice 按 model 归集 —— 这是本包报价的来源。

**二、49 个图片型号，14 个真能打。** 目录里 35 个型号的 `channel_code` 是 `official`，
描述写着「同步后请先验证并完成上架」。实测 `flux-2-flex` 空 prompt 打到出图端点，
返回的是 **404 HTML**（网关 SPA 兜底：目录里有、路由没有）。
`catalog` 默认只列 14 个可调用的，`gen` 预检会把待验证的型号挡在发请求之前。

**三、空 prompt 探针只对部分型号停在扣费前。** `gpt-image-2.6` 空 prompt → **422**
`prompt: String should have at least 1 character`，0 点；`qwen-image-3.0` 空 prompt → 502 百炼提交失败，
但流水里先 `reserve_sync -20` 再 `refund +20`，净 0、钱包动过。
所以 `doctor` 只探 `gpt-image-2.6` 一条，并把余额前后对比一起打出来。

## 完整用法

```bash
# 1) 看目录：单价 / 来源 / 是否已上架（免费）
python3 scripts/run.py catalog
python3 scripts/run.py catalog --all --json

# 2) 先报价：同一句 prompt，多个型号逐个报（免费）
python3 scripts/run.py cost --models gpt-image-2.6,seedream-5-0-flash,gpt-image-2 --n 2

# 3) 出图：选一个，或者全跑（要 --yes，受 --budget 管）
python3 scripts/run.py gen --models gpt-image-2.6 --prompt "雨夜街头，霓虹灯下撑伞的女孩" --yes
python3 scripts/run.py gen --models gpt-image-2.6,seedream-5-0-flash,gpt-image-2 \
    --prompt "雨夜街头，霓虹灯下撑伞的女孩" --n 1 --yes

# 4) 只打印请求，一分钱不花
python3 scripts/run.py gen --models gpt-image-2.6 --prompt "一只橘猫" --dry-run

# 5) 异步任务查询（免费，只走 GET /api/v1/tasks/<id>）
python3 scripts/run.py status --task-id task_xxx

# 6) 用 manifest 重新生成对比清单（免费）
python3 scripts/run.py sheet --run ./run-20261108-093000
```

## 三步上手

```bash
# 第 1 步：0 点自检
python3 scripts/run.py doctor

# 第 2 步：0 点报价（默认 3 个型号）
python3 scripts/run.py cost --n 1

# 第 3 步：选一个开跑，落盘 + 对比清单
python3 scripts/run.py gen --models gpt-image-2.6 --prompt "白底商品图，一只黄色音箱" --yes
```

出图后目录长这样：

```
run-20261108-093000/
├── 01-gpt_image_2_6-01.png      序号-型号-张序.png
├── 02-seedream_5_0_flash-01.png
├── manifest.json                结构化结果（含实际点数）
└── 对比清单.md                  一张表看完成本与产出
```

## 规格

| 项 | 值 |
|---|---|
| 出图端点 | `POST /api/v1/images/generations`（JSON，同步） |
| 查询端点 | `GET /api/v1/tasks/<id>`（免费） |
| 型号上限 | 一次 `--models` 建议 2 - 4 个，逐个串行出图 |
| 张数 | `--n` 1 - 4，每个型号各 n 张 |
| 尺寸 | `auto` / `1k` / `2k` / `4k` / 宽x高（gpt-image 系在本地校验四条硬约束） |
| 预算 | `--budget` 默认 200 点（2 元），单位是「点」 |

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 图片型号 + 单价 + 来源 + 是否已上架 |
| `cost` | 免费 | 同一句 prompt 多型号逐个报价 |
| `doctor` | 免费 | 7 个只读端点 + 1 个 422 探针 + 余额对比 |
| `gen` | 按张 | 多型号出图，落盘 + manifest + 对比清单 |
| `status` | 免费 | 查异步任务 |
| `sheet` | 免费 | 用 manifest 重出对比清单 |
| `log` | 免费 | 本地台账 |

退出码：`0` 成功 · `2` 用法错 · `4` 缺 `--yes` · `5` 超 `--budget`（不发一个出图请求）· `6` 调用失败 · `1` 内部错 · `130` 中断。

`--json` 契约：成功 `{"ok": true, …}`；失败 `{"ok": false, "exit": N, "error": {"kind": …, "message": …}}`。
`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 和已有包的分工

| 你的需求 | 用哪个包 | 为什么 |
|---|---|---|
| 同一句 prompt 横评几个模型，选一个或全跑 | **本包** | 多型号报价 + 同 prompt 出图 + 对比清单 |
| 只跑 gpt-image-2.6 出图 / 改图 / GIF | `sanjianke-gpt-image` | 单模型深度：图生图 multipart、尺寸校验、GIF |
| 一套电商素材（白底 / 场景 / 细节 / 详情页） | `sanjianke-ecom-picset` | 按位分配 prompt、平台尺寸换算、批量铺图 |
| 看全站应用层与模型层的差价排行 | `sanjianke-price-radar` | 6 个只读子命令、115 条规则、app-vs-model 排行 |
| 一个角色跨多格保持一致 | `sanjianke-storyboard-art` | 设定卡 + 参考图锁定 + 跨格自检 |

本包管「选哪个模型」，上面几个包管「这个模型怎么用到极致」。两边可以串起来：
本包报价选型，再用对应包跑完整产线。

## 免责

- 单价按「点/张」计，实际以响应里的 `usage` 与 `GET /user/balance/logs` 为准。
- 图片链接约 3 小时有效；本包默认把 `b64_json` 直接落成文件，不受过期影响。
- 生成内容的合规责任在使用者：请用在合法、有授权的素材与用途上。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
