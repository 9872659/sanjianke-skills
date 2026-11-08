---
name: sanjianke-model-video
slug: sanjianke-model-video
displayName: 视频生成台·模型层（同一条片便宜 75 倍）
description: "**同一段提示词：应用层 11,000 点，模型层 145.73 点 —— 一条片子省 75 倍。** 走 api.a7w.cn 模型层视频接口 `POST /api/v1/videos`，一条命令出片。模型层单价不在 `/pricing` 里，`cost` 先读你 `/me/tasks` 的真实成交价，没跑过就退到本机基线并标 `baseline`；四个 ID 都验过（Seedance 2.0 145.73 / Seedance 2.5 762.30 / Wan 3.0 300 / muse-video 11 点每秒）。轮询只走免费 GET（`/tasks`、`/videos`、`/videos/generations`），应用层 `/query` 每查一次就是一次的钱。缺 `--yes` 退 4、超 `--budget` 退 5 且不发请求。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 视频生成
  - 模型层
  - api.a7w.cn
---

# 视频生成台 · 模型层

> **本包不内嵌 Key**：用你自己在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**一条 Seedance 片子，应用层 11,000 点，模型层 145.73 点。** 同一段提示词、同一个模型，走 `POST /api/v1/videos` 就是省 75 倍；Seedance 2.5 省 14 倍，Wan 3.0 省 2.7 倍。异步两步、零依赖。

## 价目表（模型层实测 vs 应用层一口价，1 元 = 100 点）

| 模型（模型层 ID） | 实测成交 | 应用层一口价 | 倍数 | 干什么 |
|---|---|---|---|---|
| `sd/doubao-seedance-2-0-260128` | **145.73 点** | 11,000 点 | **75.5 倍** | Seedance 2.0 标准版，同族最便宜 |
| `volcengine/doubao-seedance-2-5-260628` | 762.30 点 | 11,000 点 | 14.4 倍 | Seedance 2.5 旗舰版，画质最强 |
| `wan3.0-video` | 300 点 | 800 点 | 2.7 倍 | Wan 3.0，8 条成交全是 300 点 |
| `muse-video` | 11 点/秒（5 秒 55 点） | 无同款 | — | 720P 带声音，4–180 秒 |

- 以上「实测成交」来自 `GET /api/v1/me/tasks` 的 `actualPrice`：5 条 / 3 条 / 8 条 / 8 条样本。
- `cost` 会先读**你自己**的流水：跑过就按你的成交价报价（`live`），没跑过退到本机基线（`baseline`）。

## 三条别人不会告诉你的

**一、模型层单价不在价目表里。** `GET /api/v1/pricing` 115 条规则没有一条写模型层单价，全表没有 `modelPricing` 键；`modelRates` 只出现在 3 条 `image_human` 规则上，含义是「按请求体 `mode` 取费率」（fast 10 / standard 15 / 2k 30 / 4k 60），不是模型价目表。所以本包读你自己的 `GET /api/v1/me/tasks`：每条任务带 `actualPrice` / `reservePrice` / `rateNote`（模型层恒为「官方价 × 2.00」），按 model 归集就是真实成交价。

**二、轮询一次就是一次的钱。** 应用层的 `POST /api/v1/apps/<app>/query` 是**按次计费**的（nano_banana/query 72 点/次，历史上光轮询烧掉 15,552 点）。模型层不用它，三条查询都免费，本包自动按顺序试：

| 路由 | 认哪种 id | 给什么 |
|---|---|---|
| `GET /api/v1/tasks/{id}` | `task_` 开头 | `status` / `progress` / `finished_at` |
| `GET /api/v1/videos/{id}` | `task_` 开头（Muse 族） | `video_url` / `expires_at` / `size` |
| `GET /api/v1/videos/generations/{id}` | **UUID 形式（Seedance 族）** | `generation_status` / `video_url` / `video_url_expires_at` |

同一个 UUID 打到 `/tasks` 会回 `404 page not found`、打到 `/videos` 会回 400 `task_not_exist` —— 只有 `/videos/generations/{id}` 能拿到它，`status` 与 `wait` 已经把这三种都试过了。

## 完整链路（提交 → 查询 → 下载）

```bash
# 1) 提交：模型层 ID 直接在 model 里
POST /api/v1/videos
{"model": "sd/doubao-seedance-2-0-260128", "prompt": "山间的雾慢慢飘过松林，镜头缓慢推进", "seconds": 5}
# → {"id": "task_xxx", "object": "video", "status": "queued"}

# 2) 查询（都免费，三种 id 形态都认）
GET /api/v1/tasks/task_xxx                  # task_ 开头：状态 / 进度
GET /api/v1/videos/task_xxx                 # Muse 族：成片 video_url 与 expires_at
GET /api/v1/videos/generations/<uuid>       # Seedance 族：generation_status 与 video_url

# 3) 下载
curl -o out.mp4 "<video_url>"
```

图片输入：`input_reference`（首帧，URL 或 data URL）、`images`（多图参考）。本地图 `gen --first-frame 首帧.jpg` 会自动转 data URL。成品链接有期限（实测 Muse 的 `expires_at` 在 7 天后、Seedance 的 `video_url_expires_at` 是 24 小时），以返回值为准，拿到就转存。

## 三步上手

```bash
# 1) 自检：Key / 模型目录 / 价目通配 / 3 个零扣费探针 / 2 条查询 / 报价数据源
python3 scripts/run.py doctor

# 2) 先算钱（读你自己的成交价，这次不花一分）
python3 scripts/run.py cost --model sd/doubao-seedance-2-0-260128 --seconds 5

# 3) 先看请求再真跑（不提交用一个请求都不发的那种方式看）
python3 scripts/run.py gen --prompt "山间的雾慢慢飘过松林，镜头缓慢推进" --seconds 5 --dry-run
python3 scripts/run.py gen --prompt "山间的雾慢慢飘过松林，镜头缓慢推进" --seconds 5 --yes --wait
```

## 常用命令

```bash
python3 scripts/run.py catalog                                   # 4 个模型 + 报价来源 + 应用层对照
python3 scripts/run.py cost                                      # 4 档报价区间与闸门
python3 scripts/run.py gen --prompt "…" --seconds 5 --dry-run     # 只打印请求
python3 scripts/run.py gen --model muse-video --prompt "…" --seconds 8 --size 720x1280 --yes --wait
python3 scripts/run.py gen --prompt "…" --seconds 5 --first-frame 首帧.jpg --yes
python3 scripts/run.py gen --prompt "…" --extra '{"ratio":"9:16","resolution":"720p"}' --yes
python3 scripts/run.py status task_xxx                           # 三条免费查询合并
python3 scripts/run.py wait task_xxx --outdir .                  # 等完成并下载
python3 scripts/run.py log --limit 10
```

**不含 `--yes` 退 `4`** 并告诉你这次报价多少；**报价上限超 `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 3500 = 35 元）。

## 规格

| 项 | 说明 |
|---|---|
| 依赖 | 只用 Python 3.7+ 标准库，`pip install` 一个都不用 |
| 提交 | `POST /api/v1/videos`（与 `/api/v1/videos/generations` 等价，OpenAI 视频接口形态） |
| 查询 | `GET /api/v1/tasks/{id}` · `GET /api/v1/videos/{id}` · `GET /api/v1/videos/generations/{id}`，都免费 |
| 报价 | `GET /api/v1/me/tasks`（每页恒 20 条，`--pages` 控制读几页，默认 2 页） |
| 闸门 | 报价上限 > `--budget` → 退 5（一个请求都不发）；缺 `--yes` → 退 4 |
| 退出码 | `0` 成功 / `2` 用法错 / `3` 自检不过 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断 |
| `--json` | 写在子命令前后都行，stdout 只有一个 JSON：成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}` |
| 参数顺序 | `--json` / `--key` / `--host` / `--budget` / `--pages` 放前后都认；缩写一律拒绝 |
| 文件 | `references/api-contract.md` 契约原文 + 实测返回；`references/troubleshooting.md` 按报错找原因 |

## 和 sanjianke-muse-video 的分工

两个包打的是**同一个端点** `POST /api/v1/videos`，差别在「一个模型」和「一条最省的路」：

| 你要干的事 | 用哪个 | 它多做了什么 |
|---|---|---|
| 在 4 个模型层模型里挑最便宜的那条 | **本包** `cost` / `catalog` | 读你的 `actualPrice` 报价，并给出应用层 11,000 点的对照倍数 |
| 要 Seedance 2.0 / 2.5 / Wan 3.0 的模型层 ID | **本包** `gen --model …` | 记住 4 个 ID、各自的实测区间与预冻结额 |
| 要把花费卡死在某个点数内 | **本包** `--budget` | 按报价上限判定，超了退 5 且一个请求都不发 |
| 只做 Muse Video（720P 带声音、4–180 秒） | `sanjianke-muse-video` | 按 11 点/秒精算、multipart 传首帧、`--wait` 自动下载、过期时间提醒 |
| 要一条龙比价（应用层 vs 模型层 9 组） | `sanjianke-price-radar` | 全站差价排行、陷阱清单、按意图给最便宜的路 |

一句话：**只做 Muse 找 muse-video，要在模型层里挑最省的找本包。** 两个包共用 `scripts/a7w.py`（逐字节一致）与同一个 Key。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
