---
name: sanjianke-local-life
slug: sanjianke-local-life
displayName: 本地生活视频 一天 5 条门店矩阵
description: "**一天出 5 条门店探店片，76 元**：门头 3 秒 → 环境 → 招牌菜 → 价格 → 行动号召，五段结构、5 组标题、5 条团购文案、5 组同城标签、5 条口播、5 张封面一次生成，再按单条花钱。出图 6 点一张，成片 15 元一条 25 秒 1080P（full_video 60 点/秒，拆 15+10），口播约 0.18 点/字，配乐 50 点起，同城爆款参考 100 点一次。查进度只走 GET /api/v1/tasks/<id>（0 点），首帧图先走 POST /api/v1/upload（免费）。`plan` 与 `qc` 全在本地，0 点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "本包管的是「一个门店一天要交什么」。**一天 5 条 76 元**（1080P，25 秒一条）：成片 7,500 点、封面 30 点、口播 81 点、配乐 50 点。**价目**（1 元 = 100 点）：full_video 480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒；gpt-image-2.6 6 点/张；voice_tts 上游真实点数 x 3，按 0.18 点/字估；music_generate 上游 x 2、保底 50 点；watermark_removal flat 100 点/次。**流程**：plan 本地出结构、口播、标题、团购文案、标签、封面 prompt、命名与交付单（0 点）；qc 本地过五道合规（0 点）；ref 看爆款；shop 出图；voice 出口播；music 出配乐；film 出片；status 查进度。**三条规矩**：轮询只走 GET /tasks（0 点）；目录只看 /apps 列表与 /pricing；首帧图先 upload 换白名单地址。**闸门**：缺 --yes 退 4 并报金额，超 --budget 退 5 一个请求都不发。需要自备 api.a7w.cn 的 Key，注册见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 本地生活
  - 探店视频
  - api.a7w.cn
---

# 本地生活视频 一天 5 条门店矩阵

> **先申请你自己的 API Key。** 本包不内嵌任何 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**一天 5 条门店探店片，76 元。** 门头 3 秒抓同城刷到的人，环境交代「几个人来合适」，招牌菜怼馋点，价格摆出团购与单点的差，最后一句行动号召落到 POI 和团购链接。

## 这个包和底层能力包的分工

| 你手上要的东西 | 用哪个包 | 它交付什么 |
|---|---|---|
| 一张门店图 / 菜品图 | `sanjianke-gpt-image` | 6 点一张，文生图 / 图生图 / GIF |
| 一段 4~15 秒的镜头 | `a7w-full-video` | 首帧 + 运镜，按秒 x 分辨率计费 |
| 一条口播 | `a7w-voice-tts` | 同步 tts / 长文 tts_async / 克隆音色 |
| 一首配乐 | `a7w-music-generation` | Suno 线接口与参数表 |
| 同城爆款的结构拆解 | `sanjianke-ecom-spy` | 搜索 + 标题公式 + 分镜骨架 |
| **一个门店一天要交的 5 条片 + 5 张封面 + 5 条口播 + 团购文案 + 标签 + 交付单** | **本包** | 岗位流程、五段结构、文案模板、合规检查、成本单 |

底层包做单步，本包做「一个岗位一天要交的东西」：先在本地把 5 条的角度、口播、文案、标签、命名排好，再决定哪几条值得花钱。

## 交付清单（一个门店一天）

| # | 交付物 | 规格 | 数量 | 命名 |
|---|---|---|---|---|
| 1 | 竖版成片 | 1080x1920 / H.264 / 25 秒 / 9:16 | 5 | `20261108_老灶门火锅_01_门头_dy_25s.mp4` |
| 2 | 封面图 | 1080x1440 / 3:4 / png | 5 | `*_01_cover.png` |
| 3 | 口播音频 | mp3 / 44.1kHz / 单条 20~30 秒 | 5 | `*_01_voice.mp3` |
| 4 | 团购文案 | 标题 3 条 + 卖点 3 条 + 价格锚 1 条 | 5 组 | `文案.md` |
| 5 | 同城标签 | 抖音 6 个 / 小红书 6 个 | 5 组 | `文案.md` |
| 6 | 配乐 | 一首 30 秒循环 | 1 | `bgm.mp3` |
| 7 | 当天交付单 | 拍摄 / 剪辑 / 发布状态 | 1 | `当天交付单.md` |

## 探店 25 秒的五段结构

| 时间 | 段落 | 画面 | 口播干什么 |
|---|---|---|---|
| 0-3 秒 | 门头 | 街边推到招牌，门口排队或热气 | 一句话报店名和位置，让人知道在哪条街 |
| 3-8 秒 | 环境 | 推门进店，桌椅、明档、后厨窗口 | 说清楚几个人来合适、要不要等位 |
| 8-16 秒 | 招牌菜 | 出锅特写，筷子夹起、拉丝、汤滚 | 报菜名 + 份量，这一段决定完播 |
| 16-22 秒 | 价格 | 团购页 + 菜量对比 + 账单 | 报团购价与单点差价，差价就是转化理由 |
| 22-25 秒 | 行动号召 | 招牌定格 + POI 定位 | 报口令、指左下角、说可用时间窗 |

五个角度轮着发：门头钩子、招牌菜特写、价格锚点、老板出镜、老客回头。同一个门店一天正好五条，不重复不内耗。

## 价目表（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing`）

| 工序 | 接口 | 单价 |
|---|---|---|
| 同城参考 | `POST /api/v1/apps/watermark_removal/douyin_search_video` | **100 点/次**（flat，失败亦计） |
| 出图 | `POST /api/v1/images/generations` | **6 点/张** |
| 口播 | `POST /api/v1/apps/voice_tts/tts` | 约 **0.18 点/字** |
| 配乐 | `POST /api/v1/apps/media_services_33/music_generate` | **50 点起/首** |
| 成片 | `POST /api/v1/apps/full_video/submit` | 480P 14 / 768P 28 / **1080P 60** / 2K 80 / 4K 80 点/秒 |
| 查进度 | `GET /api/v1/tasks/<task_id>` | **0 点** |
| 传图 | `POST /api/v1/upload` | **0 点** |
| 脚本 / 检查 | `plan` / `qc`（纯本地） | **0 点** |

## 一条 25 秒多少钱

| 分辨率 | 单条成片 | 一天 5 条（含封面 + 口播 + 配乐） |
|---|---|---|
| 480P | 350 点 = 3.50 元 | 1,911 点 ≈ 19.11 元 |
| 768P | 700 点 = 7.00 元 | 3,661 点 ≈ 36.61 元 |
| **1080P** | **1,500 点 = 15.00 元** | **7,661 点 ≈ 76.61 元** |

`cost` 会把五档分辨率、门店数、每家几条一起算；`plan` 会把当天交付单和成本单一起写进 `~/.a7w/local-life/`。

## 三条干货（别人不写进文档的）

**一、轮询一次就是一次的钱。** 应用层的 `/query` 每查一次按该应用单价结算，`nano_banana/query` 实测 72 点/次。本包只打 `GET /api/v1/tasks/<id>`，价目表里这条是 cost:0，等十分钟也是 0 点。

**二、`GET /api/v1/apps/<app>` 是收费的。** 它命中 `/api/v1/apps/<app>/*` 的通配计价，按该应用 flat 单价即时扣费、不退（实测 dressing_diffusion 200 点、nano_banana 72 点各一笔）。要目录只看 `/api/v1/apps` 列表和 `/api/v1/pricing`，两条都是 cost:0。

**三、首帧图有域名白名单。** 外站地址一律 400 `url_not_allowed`，只认 vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。`film --image 本地图.png` 会自动先 `POST /api/v1/upload`（免费）换地址。

## 三步上手

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key

# 2) 免费：自检 + 算钱 + 出当天脚本与交付单 + 合规检查
python3 scripts/run.py doctor
python3 scripts/run.py cost --shops 1 --seconds 25 --resolution 1080P
python3 scripts/run.py plan --shop "老灶门火锅" --city 成都 --category 火锅 \
    --dish "牛油锅底" --price 88 --offer "双人餐"
python3 scripts/run.py qc --plan ~/.a7w/local-life/成都-20261108/plan.json

# 3) 按交付单花钱（每一步都能单跑、能续跑）
python3 scripts/run.py shop  --kind cover --shop "老灶门火锅" --dish "牛油锅底" --yes
python3 scripts/run.py voice --text "在成都春熙路，这家老灶门火锅……" --yes
python3 scripts/run.py music --style "轻快城市探店 vlog" --yes
python3 scripts/run.py film  --text "竖屏探店，门头推到招牌……" --image cover-01.png --yes
python3 scripts/run.py status --task-id tsk_xxx
```

## 常用命令

| 命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 八个动作 + 端点 + 现查单价 |
| `cost --shops 3 --per-shop 5` | 免费 | 三家店 15 条要多少钱 |
| `plan --shop "A" --shop "B"` | 免费 | 多店矩阵，一次出全部脚本与交付单 |
| `qc --plan plan.json` | 免费 | 五道合规：绝对化用语 / 价格 / 标签 / 行动号召 / 时长 |
| `ref --keyword "成都 火锅 探店"` | **100 点/次** | 同城爆款，看时长分布与钩子词 |
| `shop --kind dish --n 2` | **6 点/张** | 招牌菜图、门头图、团购封面 |
| `voice --script 口播.txt` | **约 0.18 点/字** | 口播，500 字内一条 |
| `music --style "…"` | **50 点起** | 30 秒循环配乐 |
| `film --seconds 15` | **按秒** | 单段成片，首帧图自动 upload |
| `log` | 免费 | 本地台账 |

## 合规检查（拍前过一遍，`qc` 已经做成默认动作）

- **宣传语用可验证描述**：「牛油锅底现熬 4 小时」比「全城第一」更稳，也更有画面。
- **价格三处对齐**：口播里的数字、团购标题、菜单实价保持一致。
- **门店信息对齐**：地址、营业时间、电话与平台 POI 一致，导航搜得到。
- **同城标签六个**：城市 + 商圈 + 品类 + 店名 + 招牌菜 + 团购，抖音与小红书各一组。
- **素材来源**：门店自有素材优先；同城爆款只借结构，画面自己拍。
- **背景音乐**：用授权曲库，或用本包 `music` 生成的配乐。

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--shop` | 必填（`plan`） | 门店名，可重复给多家店 |
| `--city` / `--district` / `--category` | 成都 / 春熙路 / 火锅 | 同城标签与文案的城市字段 |
| `--dish` / `--price` / `--offer` | 招牌锅底 / 88 / 双人餐 | 招牌菜、团购价（元）、团购内容 |
| `--per-shop` | 5 | 每家店几条（1~5） |
| `--seconds` | 25 | 单条时长；`film` 单段 4~15 |
| `--resolution` | 1080P | 480P / 768P / 1080P / 2K / 4K |
| `--budget` | 6000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

退出码：`0` 成功 / `2` 用法错 / `3` 自检或合规没过 / `4` 缺 `--yes` / `5` 超预算且一个请求都没发 / `6` 调用失败 / `1` 内部错 / `130` 中断。

`--json` 成功是 `{"ok": true, ...}`，失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，stdout 只有一个 JSON 文档；`--json` 写在子命令前后都可以。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
