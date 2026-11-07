---
name: sanjianke-shortdrama-mass
slug: sanjianke-shortdrama-mass
displayName: 短剧量产 · 一天 10 条日更的排产台
description: "**一天 10 条短剧日更，从排产到交付验收一条命令：8,580 点 = 85.80 元，单条 8.58 元。** 8 个工位一张排产单：`plan` 出单、`run` / `batch` 出片、`check` 验交付清单，命名规范一次定死。口播 15 点/秒占全条 79%，秒数是唯一的大杠杆；media_services_33 的 29 个接口都没配价，每次先冻 60 点；应用层 query 按次计费（nano_banana/query 72 点/次），所以查任务只走免费的 `GET /tasks/{id}`。缺 `--yes` 退 4 报要花多少点，超 `--budget` 退 5 且一个请求都不发。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "短剧日更的难点不在拍，在「一天 10 条怎么排」。本包把 voice_tts 配音、pic_lipsync 口播、media_services_33 配乐与时间戳、full_video 成片四条线按 8 个工位重排，付费的只有 4 个。价目（1 元 = 100 点）：配音 0.18 点/字（上游 ×3）、口播 15 点/秒（上游 3 点/秒 ×5）、配乐与卡点各 60 点/条、full_video 480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒。一条 45 秒 350 字 = 858 点 = 8.58 元，一天 10 条 = 8,580 点 = 85.80 元。三条实测口径做成默认：① 口播占全条 79%，45 秒降到 30 秒一天省 2,250 点；② media_services_33 的 29 个接口都没配价，每次先冻 60 点（4 条流水各 60 冻 60 退），按 60 点/条入账；③ 应用层 query 按次计费（nano_banana/query 72 点/次），轮询只走 GET /api/v1/tasks/{id}。`plan` 与 `check` 纯本地 0 点。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 短剧
  - 日更排产
  - 数字人口播
  - api.a7w.cn
---

# 短剧量产 · 一天 10 条日更的排产台

> ## 先申请你自己的 API Key
>
> 本包不内嵌 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己账户的余额。
> 新用户有赠送点数，可以先免费自检再排产：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**一天 10 条短剧日更：8 个工位一张排产单，8,580 点 = 85.80 元，单条 8.58 元。**
选题、脚本、分镜在本地出；配音、口播、配乐、卡点四条线各一次请求；封面本地截帧 0 点。
同一套配置换几个参数就是另一种账：只口播 6,750 点/天（67.50 元）、口播 30 秒 6,330 点/天（63.30 元）、
封面走 full_video 480P 4 秒 9,140 点/天（91.40 元）、加一条 15 秒 1080P 预告片 17,580 点/天。

## 一天的账（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing`）

| 工位 | `--step` | 走哪条线 | 单价 | 一条 | 一天 10 条 |
|---|---|---|---|---|---|
| 选题 | `topic` | 本地钩子池（12 个钩子类型） | 免费 | 0 | 0 |
| 脚本 | `script` | 本地分镜模板（5 段时间轴） | 免费 | 0 | 0 |
| 旁白配音 | `voice` | `voice_tts/tts_async` | 0.18 点/字（上游 ×3） | 350 字 = **63** | 630 |
| 数字人口播 | `avatar` | `pic_lipsync/submit`（mode=text） | **15 点/秒**（上游 3 点/秒 ×5） | 45 秒 = **675** | 6,750 |
| 配乐 | `music` | `media_services_33/music_generate` | 60 点/条（未配价，按预冻口径） | **60** | 600 |
| 卡点字幕 | `beat` | `media_services_33/music_timestamped_lyrics` | 60 点/条 | **60** | 600 |
| 封面 / 片头 | `cover` | 本地截帧，或 `full_video/submit` | 0 点 / 14–80 点/秒 | 0 | 0 |
| 分发交付 | `deliver` | 本地改名 + `check` 验收 | 免费 | 0 | 0 |
| **合计** | | | | **858 点 = 8.58 元** | **8,580 点 = 85.80 元** |

`full_video` 的专属定价按分辨率走：**480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80** 点/秒，时长只收 4–15 秒整数。
`cost` 会把上面五条走法的总账一条命令全打出来。

## 三条别人不会告诉你的

**一、口播 15 点/秒是全条 79% 的成本，秒数是唯一的大杠杆。**
一条 858 点里 675 点是口播。45 秒砍到 30 秒，一天 10 条省 **2,250 点（22.50 元）**；
砍到 24 秒省 3,150 点。先把时长定死，再谈别的优化 —— 其余三个工位合起来只有 183 点。

**二、`media_services_33` 的 29 个接口，一条都没配价。**
这个应用（ElevenLabs 配音 / `music_generate` 配乐 / `music_timestamped_lyrics` 时间戳）
在 `GET /api/v1/pricing` 里**一条规则都没有**，每次调用按默认预冻 60 点。
实测 4 条流水：`music_generate` / `music_extend` / `music_sounds` /
`music_timestamped_lyrics` 各 `reserve_sync` 冻 60、`refund:sync` 退 60。
所以本包把配乐与卡点按 **60 点/条** 入账，多跑一条就是 60 点 —— 它是按条计费的接口，不是免费的查询口。

**三、应用层 `query` 按次计费，本包只走 `GET /tasks/{id}`。**
`nano_banana/query` 实测每次扣 **72 点**，轮询一次就是一张图的钱。所以本包 `status`
只打免费的 `GET /api/v1/tasks/{task_id}`，一次应用层 query 都不发。
同一条逻辑也用在 `doctor` 上：它只发 7 个免费请求（5 个只读 GET + 空表单上传 + 余额复采），
**一次 `list_voices` 都不碰** —— 那个口子文档写「免费」，实测每次先冻 150 点再全额退。

## 交付清单（这个行业一天要交的东西）

一条 5 件必交 + 1 件选交，一天 10 条 = **50 件必交 + 10 件选交**：

| 工位 | 说明 | 必交 | 规格 | 命名 |
|---|---|---|---|---|
| `avatar` | 口播成片 | 是 | 1080×1920，≤200 MB | `SD_S01E03_avatar_1080x1920_v01.mp4` |
| `voice` | 旁白音轨 | 是 | mp3，≤20 MB | `SD_S01E03_voice_v01.mp3` |
| `music` | 配乐 | 是 | mp3，≤20 MB | `SD_S01E03_music_v01.mp3` |
| `beat` | 卡点字幕 | 是 | SRT / UTF-8，≤2 MB | `SD_S01E03_beat_v01.srt` |
| `cover` | 封面 | 是 | 1080×1920，≤2 MB | `SD_S01E03_cover_1080x1920_v01.jpg` |
| `promo` | 预告片 | 选 | 1080×1920，≤200 MB | `SD_S01E03_promo_1080x1920_v01.mp4` |

**命名规范：`<项目>_S<季两位>E<集两位>_<工位>_<规格>_v<版本两位>.<扩展名>`。**
`plan` 按这套把 60 个文件名字写进排产单，`check` 按这套验 —— 改名在流水线里，不是人的习惯；
`check` 用文件头读真实像素，封面 1080×1920、体积、SRT 编码逐条对。

## 这个包和底层能力包的分工

能力包做「单步调通一个接口」，本包做「一个岗位一天要交的东西」。

| | 能力包（`a7w-*` / `sanjianke-*`） | 本包 `sanjianke-shortdrama-mass` |
|---|---|---|
| 形态 | 单步：一次提交、一次查询、一次落盘 | 排产 → 出片 → 交付 → 验收，一天 10 条打成一单 |
| 入口 | 每个包只认自己的端点与参数 | 一张 `plan.json` 管 10 条 × 8 工位 |
| 交付物 | 一条任务的结果 | 50 件必交文件 + 命名规范 + 交付清单 |
| 谁在用 | 工程师调接口、验价格 | 制片 / 编导 / 运营排产、验收、对账 |
| 价格视角 | 单个接口的单价 | 一条 / 一天 / 五种走法的总账 |

同赛道三个包一句话分清：

| 你要什么 | 用哪个 |
|---|---|
| 一条 60 秒素材做二创（去台标 → 擦硬字幕 → 提画质 → 换解说 → 套模板） | `sanjianke-shortdrama-remix` |
| 一张图 + 一段文案，出一张口播 | `sanjianke-digital-host` |
| 一张图 + 一段文字，全流程出一条成片（含字级字幕与 AI 封面） | `avatar-autoclip` |
| 一天 10 条的排产、命名、批量出片、交付验收 | **本包** |

## 三步上手

```bash
python3 scripts/a7w.py login --key sk-你的key                  # 1) 填 Key
python3 scripts/run.py doctor                                  # 2) 自检（0 点，7 个免费请求）
python3 scripts/run.py plan --project SD --episodes 10 --write --outdir ./out
```

`plan` 会写出 `plan.json`（机器读）和 `slate.md`（人读，可直接打印贴排产板）。

## 常用命令

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 8 工位 + 4 条能力线 + 单价 + 一条/一天总账 |
| `cost` | 免费 | 算钱：一条、一天、五种走法对照 |
| `plan` | 免费 | 出排产单：钩子 + 5 段分镜 + 8 工位 + 60 个文件名 + 点数 |
| `doctor` | 免费 | 7 个免费请求自检，含「余额前后一致 = 本轮 0 点」 |
| `upload` | 免费 | 本地素材传平台，拿 `oss.gpu.likeadmin.cn` 白名单地址 |
| `check` | 免费 | 交付清单验收：齐不齐 / 命名 / 封面像素 / 体积 / SRT 编码 |
| `run` | **按工位计价**（一条全跑 858 点） | 跑一条：`--step voice\|avatar\|music\|beat\|cover` 或 `--all` |
| `batch` | **×条数** | 跑一天：`--episodes all\|1-10\|1,3,5`，可 `--keep-going` |
| `status` | 免费 | 查任务（只走 `GET /api/v1/tasks/{id}`） |
| `log` | 免费 | 本地台账（`~/.a7w/shortdrama-mass-ledger.json`） |

```bash
python3 scripts/run.py cost --episodes 10 --seconds 45 --chars 350
python3 scripts/run.py run --plan ./out/plan.json --ep S01E03 --step avatar \
  --image-url "https://oss.gpu.likeadmin.cn/openapi/..." --voice-ref "https://oss.gpu.likeadmin.cn/openapi/..." \
  --text "她扫了三年地，转身在董事会上叫出了所有人的名字" --yes
python3 scripts/run.py batch --plan ./out/plan.json --episodes 1-10
python3 scripts/run.py check --dir ./out --plan ./out/plan.json
```

## 规格

| 项 | 说明 |
|---|---|
| 依赖 | 只用 Python 3.7+ 标准库，`pip install` 一个都不用 |
| 能力线 | `voice_tts/tts_async` · `pic_lipsync/submit`（mode=text）· `media_services_33/music_generate` · `media_services_33/music_timestamped_lyrics` · `full_video/submit` · `POST /api/v1/upload` |
| 轮询 | 只走 `GET /api/v1/tasks/{task_id}`；应用层 `query` 按次计费，本包一次都不发 |
| 计费口径 | 配音上游 ×3、口播上游 ×5、media33 未配价按 60 点/条、full_video 按分辨率 14–80 点/秒、上传 0 点 |
| 闸门 | 缺 `--yes` → **4** 并报出要花多少点；预计 > `--budget` → **5**，一个请求都不发；`--budget` 单位是「点」，默认 10000 = 100 元；付费命令加 `--dry-run` 只看请求 |
| 退出码 | `0` 成功 / `2` 用法错 / `3` 自检或验收没过 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断 |
| `--json` | 写在子命令前后都行，stdout 只有一个 JSON 文档：成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}`，`kind` 取 `usage｜gate｜confirm｜budget｜call｜interrupt｜internal` |

排错见 `references/troubleshooting.md`，接口原文见 `references/api-contract.md`。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
