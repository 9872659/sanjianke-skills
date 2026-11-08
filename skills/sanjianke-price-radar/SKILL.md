---
name: sanjianke-price-radar
slug: sanjianke-price-radar
displayName: 模型比价器 同一个模型差 75 倍
description: "**同一个 Seedance，走应用层 11,000 点（¥110），走模型层 762 点（¥7.62）—— 差 14.4 倍。** 这条命令帮你把全站这种差价一次翻出来，按倍数排序。控制台的价目表只写应用层一口价，模型层那批接口（`/videos/generations`、`/images/generations`、`/tasks`）在价目表里根本没有专属规则，命中的是通配 `*`，所以单价只能从自己的流水反推 —— 本包就是干这个的：`app-vs-model` 把 `/api/v1/pricing` 的实时价和你 `/api/v1/me/tasks` 的真实成交价配成对，同族 Seedance 2.0 甚至到 **75.5 倍**；`traps` 摊开价目表里「看着有、实际不通」的 11 个 `tsc_*` 档位；`cheapest --for image|video|voice|upscale` 直接给最便宜那条路；`budget` 按「一条 10 秒视频 / 一张图 / 一分钟语音」换算成钱。三个只读端点、零依赖、全程 0 点花费。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 比价
  - 价目表
  - api.a7w.cn
---

# 模型比价器 同一个模型差 75 倍

> ## 先申请你自己的 API Key
>
> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key。
>
> ```bash
> python3 scripts/a7w.py login --key sk-你的key
> ```

## 一句话

**同一个 Seedance，应用层 11,000 点，模型层 762 点 —— 差 14.4 倍。**

## 差价表（`app-vs-model` 真跑出来的，2026-11-07）

| # | 能力 | 应用层路径 | 应用层价 | 模型层模型 | 模型层实测 | 倍数 |
|---|---|---|---|---|---|---|
| 1 | 出视频 | `/apps/seedance/submit` | 11,000 | `sd/doubao-seedance-2-0-260128` | 145.73 | **75.5×** |
| 2 | 出视频 | `/apps/seedance/submit` | 11,000 | `volcengine/doubao-seedance-2-5-260628` | 762.30 | **14.4×** |
| 3 | 出图 | `/apps/aigc_wan_image/generate/index` | 203 | `gpt-image-2` | 26 | 7.8× |
| 4 | 出图 | `/apps/aigc_photo_restore/*` | 105 | `seedream-5-0-flash` | 15.60 | 6.7× |
| 5 | 出图 | `/apps/dressing_diffusion/submit` | 200 | `gpt-image-2-pro` | 39 | 5.1× |
| 6 | 出图 | `/apps/nano_banana/submit` | 72 | `seedream-5-0-flash` | 15.60 | 4.6× |
| 7 | 出图 | `/apps/aigc_qwen_image/generate/index` | 78 | `gpt-image-2` | 26 | 3.0× |
| 8 | 出图 | `/apps/nano_banana/submit` | 72 | `gpt-image-2` | 26 | 2.8× |
| 9 | 出视频 | `/apps/wan/submit` | 800 | `wan3.0-video` | 300 | 2.7× |
| 10 | 出图 | `/apps/aigc_qwen_image_pro/generate/index` | 105 | `gpt-image-2-pro` | 39 | 2.7× |

前两条是**同一个模型**（`sd/doubao-seedance-2-0-260128` 与 `volcengine/doubao-seedance-2-5-260628`
都是 Seedance），第 3 条起是**同一件事**（出一张图），两条口径在表里都标了。

## 价目表陷阱清单（`traps` 全查）

| # | 陷阱 | 数字 |
|---|---|---|
| ① | 价目表里有、路由 404 | **11 个 `tsc_*` 档位**：`tsc_common` / `tsc_common_hd` / `tsc_aigc` / `tsc_aigc_hd` / `tsc_shortplay` / `tsc_shortplay_hd` / `tsc_uhd` / `tsc_oldsd` / `tsc_oldsd_hd` / `tsc_teshd` / `tsc_quality`，写着 2~6 点/秒、保底 10 点 |
| ② | 路由在、上游凭据坏 | `/video/tencent1080`（2 点/秒）/ `tencent2k`（4）/ `tencent4k`（8）→ 502 `InvalidMpsUser`；本账号腾讯 4K 任务全部 `refunded`，实扣 0 点 |
| ③ | 应用层 vs 模型层 | seedance 11,000 点 vs 762.30 点 = **14.4 倍**；同族 2.0 更低到 145.73 点 = **75.5 倍** |
| ④ | 单位混用 | `shot` 20 / `castcrew` 25 / `delogo` 25（含 viapi 版共 6 条）note 写「点/次」，rule 是 `per_second` → 10 秒素材按 10 倍扣 |
| ⑤ | 通配保底 | 未单独定价的接口 = 上游点数 × 2、单笔保底 50 点；模型层四条路径里三条落在这一条下面 |

## 我要做 X，最便宜怎么走（`cheapest`）

| 我要 | 最便宜的路 | 价 |
|---|---|---|
| 一张图 | `gpt-image-2`（模型层 `/tasks`） | 26 点 / ¥0.26 |
| 一条视频 | `muse-video`（模型层 `/videos`） | 44 点 / ¥0.44 |
| 超分 1 分钟 | VIAPI 超分·标准 | 9 点/秒 = 540 点 |

对照最贵那条：Seedance 应用层 11,000 点（¥110）、`/video/upscale` 30 点/秒 = 1,800 点（¥18）。

## 三步上手

```bash
python3 scripts/a7w.py login --key sk-你的key     # 1. 填 Key（零依赖，Python 3.7+）
python3 scripts/run.py doctor                     # 2. 自检三个只读端点，0 点
python3 scripts/run.py app-vs-model               # 3. 看差价排行，0 点
```

## 常用命令

| 命令 | 干什么 | 花费 |
|---|---|---|
| `app-vs-model` | 应用层 vs 模型层差价排行（本包核心） | 0 点 |
| `cheapest --for image\|video\|voice\|upscale` | 按意图给最便宜的路 | 0 点 |
| `traps` | 价目表「看着有、实际不通」清单 | 0 点 |
| `budget` | 按典型用量算预算 | 0 点 |
| `catalog --type video\|image\|text` | 模型清单（按类型分组） | 0 点 |
| `doctor` | 自检三个只读端点 + 应用层定价覆盖率 | 0 点 |

```bash
python3 scripts/run.py app-vs-model --all --yes       # 翻完 70 页台账（仍 0 点）
python3 scripts/run.py cheapest --for video --live     # 把模型层实测价排进来
python3 scripts/run.py budget                          # 10 秒视频 / 一张图 / 一分钟语音
python3 scripts/run.py catalog --type image --limit 20
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--budget` | 50 | 点数上限（**单位：点**，1 元 = 100 点）；给 0 直接退 5 |
| `--pages` | 10 | 翻几页任务台账找模型层实测价（每页 20 条） |
| `--all` | — | 翻完全部台账（约 70 页，要 `--yes`） |
| `--stat` | `min` | 模型层取 `min` / `median` / `max` |
| `--live` | — | `cheapest` 把模型层实测价一起排进来 |
| `--json` | — | 只输出一个 JSON 文档 |
| `--dry-run` | — | 只打印请求，一个都不发 |
| `--yes` | — | 确认大批量只读扫描（花费仍是 0 点）|

## 退出码

`0` 成功 · `2` 用法错 · `4` 需要 `--yes` · `5` 预算不足（一个请求都不发） ·
`6` 调用失败 · `1` 内部错 · `130` 中断

## `--json` 契约

成功：`{"ok": true, ...}`；失败：`{"ok": false, "exit": N, "error": {"kind": "...", "message": "..."}}`，
`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。stdout 只有一个 JSON 文档。

## 文件结构

```
sanjianke-price-radar/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       三个端点的原始结构（实测原文）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致）
    └── run.py                本包命令层
```

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
